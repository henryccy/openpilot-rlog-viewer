"""
SQLite Database Manager for openpilot logs
Handles connection and operations with SQLite database
"""
import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from contextlib import contextmanager
from .signal_calculator import SignalCalculator

logger = logging.getLogger(__name__)


class SQLiteManager:
    """SQLite database manager"""

    def __init__(self, db_path: str = None):
        """
        Initialize SQLite manager

        Args:
            db_path: Database file path (if None, use default path)
        """
        if db_path is None:
            db_path = "oplog.db"

        self.db_path = Path(db_path)
        # Only create parent directory if it doesn't exist
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = None
        self.cursor = None  # Add cursor attribute for compatibility
        self.signal_calculator = None

    def connect(self):
        """Connect to database"""
        try:
            self.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False  # Allow multi-threaded access
            )
            # Enable foreign key constraints
            self.conn.execute("PRAGMA foreign_keys = ON")
            # Optimize performance
            self.conn.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging
            self.conn.execute("PRAGMA synchronous = NORMAL")
            self.conn.execute("PRAGMA cache_size = -64000")  # 64MB cache

            # Create cursor attribute for DatabaseManager compatibility
            self.cursor = self.conn.cursor()

            logger.info(f"Connected to SQLite database: {self.db_path}")

            # Check and fix table structure on each connection
            self._check_and_fix_tables()

            # Initialize signal calculator (after table structure confirmed)
            try:
                self.signal_calculator = SignalCalculator(self)
                logger.info("SignalCalculator initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize SignalCalculator: {e}")
                self.signal_calculator = None

            return True

        except sqlite3.Error as e:
            logger.error(f"Error connecting to database: {e}")
            return False

    def disconnect(self):
        """Disconnect from database"""
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Disconnected from database")

    def __enter__(self):
        """Context manager support"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support"""
        self.disconnect()

    @contextmanager
    def get_cursor(self):
        """Get cursor with context manager"""
        cur = self.conn.cursor()
        try:
            yield cur
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cur.close()

    def _check_and_fix_tables(self):
        """Check and fix table structure (executed on each connection)"""
        try:
            cursor = self.conn.cursor()

            # Check log_messages table
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='log_messages'
            """)
            log_table_exists = cursor.fetchone() is not None

            if log_table_exists:
                cursor.execute("PRAGMA table_info(log_messages)")
                columns = cursor.fetchall()
                column_names = {col[1] for col in columns}

                # Required fields
                required = {'log_id', 'segment_id', 'time_ns', 'log_type', 'daemon',
                           'levelnum', 'filename', 'funcname', 'lineno', 'message',
                           'dongle_id', 'version', 'branch', 'commit'}

                # Check if fix is needed
                if 'message_type' in column_names or not required.issubset(column_names):
                    logger.warning("Detected incorrect log_messages table structure, starting auto-repair...")
                    self._fix_log_messages_table()
                    logger.info("log_messages table structure repaired")

            cursor.close()

        except Exception as e:
            logger.error(f"Error checking tables: {e}")

    def _fix_log_messages_table(self):
        """Fix log_messages table structure"""
        cursor = self.conn.cursor()

        # Check if data needs to be preserved
        cursor.execute("SELECT COUNT(*) FROM log_messages")
        count = cursor.fetchone()[0]
        has_data = count > 0

        if has_data:
            logger.info(f"Preserving {count} existing log entries")

        # Get existing columns
        cursor.execute("PRAGMA table_info(log_messages)")
        old_columns = {col[1] for col in cursor.fetchall()}

        # Create new table
        cursor.execute("""
            CREATE TABLE log_messages_new (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                segment_id INTEGER NOT NULL,
                time_ns BIGINT NOT NULL,
                log_type TEXT NOT NULL CHECK(log_type IN ('log', 'error')),

                daemon TEXT,
                levelnum INTEGER,
                filename TEXT,
                funcname TEXT,
                lineno INTEGER,

                message TEXT NOT NULL,

                dongle_id TEXT,
                version TEXT,
                branch TEXT,
                "commit" TEXT,

                FOREIGN KEY (segment_id) REFERENCES segments(segment_id) ON DELETE CASCADE
            )
        """)

        # Copy data (if any)
        if has_data:
            if 'message_type' in old_columns:
                # Old structure (message_type)
                cursor.execute("""
                    INSERT INTO log_messages_new (segment_id, time_ns, log_type, message)
                    SELECT segment_id, time_ns, message_type, message
                    FROM log_messages
                """)
            elif 'log_type' in old_columns:
                # New structure but possibly incomplete
                common = old_columns & {'segment_id', 'time_ns', 'log_type', 'daemon',
                                       'levelnum', 'filename', 'funcname', 'lineno',
                                       'message', 'dongle_id', 'version', 'branch', 'commit'}
                if common:
                    cols = ', '.join(common)
                    cursor.execute(f"""
                        INSERT INTO log_messages_new ({cols})
                        SELECT {cols}
                        FROM log_messages
                    """)

        # Drop old table
        cursor.execute("DROP TABLE log_messages")

        # Rename new table
        cursor.execute("ALTER TABLE log_messages_new RENAME TO log_messages")

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_log_segment_time
            ON log_messages(segment_id, time_ns)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_log_type
            ON log_messages(segment_id, log_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_log_daemon
            ON log_messages(daemon)
        """)

        self.conn.commit()
        cursor.close()

    def create_tables(self):
        """Create all tables"""
        schema_path = Path(__file__).parent.parent.parent / "database_schema_sqlite.sql"

        if not schema_path.exists():
            logger.error(f"Schema file not found: {schema_path}")
            return False

        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()

            # Execute schema
            self.conn.executescript(schema_sql)
            self.conn.commit()

            # Perform database migration (add missing columns)
            self._migrate_database()

            logger.info("Database tables created successfully")
            return True

        except sqlite3.Error as e:
            logger.error(f"Error creating tables: {e}")
            return False

    def _migrate_database(self):
        """Database migration: add missing columns"""
        try:
            cursor = self.conn.cursor()

            # Check if can_signal_definitions table is missing columns
            cursor.execute("PRAGMA table_info(can_signal_definitions)")
            columns = {row[1] for row in cursor.fetchall()}

            # List of required columns
            required_columns = {
                'can_id_hex': 'TEXT',
                'message_name_cn': 'TEXT',
                'byte_order': 'TEXT',
                'is_signed': 'INTEGER',
                'description_cn': 'TEXT',
                'comment': 'TEXT',
            }

            # Add missing columns
            for col_name, col_type in required_columns.items():
                if col_name not in columns:
                    logger.info(f"Adding missing column to can_signal_definitions: {col_name}")
                    cursor.execute(f"ALTER TABLE can_signal_definitions ADD COLUMN {col_name} {col_type}")

            # Check if log_messages table needs migration
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='log_messages'
            """)
            log_table_exists = cursor.fetchone() is not None

            needs_migration = False
            has_old_data = False

            if log_table_exists:
                cursor.execute("PRAGMA table_info(log_messages)")
                log_columns = {row[1] for row in cursor.fetchall()}

                logger.info(f"log_messages table existing columns: {log_columns}")

                # Check if there is old data
                cursor.execute("SELECT COUNT(*) FROM log_messages")
                count = cursor.fetchone()[0]
                has_old_data = count > 0

                # List of required columns
                required_columns = {'log_id', 'segment_id', 'time_ns', 'log_type', 'daemon',
                                   'levelnum', 'filename', 'funcname', 'lineno', 'message',
                                   'dongle_id', 'version', 'branch', 'commit'}

                # Check if migration is needed
                if 'message_type' in log_columns:
                    # Old column name (message_type instead of log_type)
                    needs_migration = True
                    logger.info("Detected old column name 'message_type', migration required")
                elif not required_columns.issubset(log_columns):
                    # Incomplete columns
                    missing = required_columns - log_columns
                    needs_migration = True
                    logger.info(f"log_messages table columns incomplete, missing: {missing}, migration required")

            if needs_migration:
                logger.info("Migrating log_messages table structure...")
                # Need to rebuild table to support new columns and CHECK constraints
                cursor.execute("""
                    CREATE TABLE log_messages_new (
                        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        segment_id INTEGER NOT NULL,
                        time_ns BIGINT NOT NULL,
                        log_type TEXT NOT NULL CHECK(log_type IN ('log', 'error')),

                        daemon TEXT,
                        levelnum INTEGER,
                        filename TEXT,
                        funcname TEXT,
                        lineno INTEGER,

                        message TEXT NOT NULL,

                        dongle_id TEXT,
                        version TEXT,
                        branch TEXT,
                        "commit" TEXT,

                        FOREIGN KEY (segment_id) REFERENCES segments(segment_id) ON DELETE CASCADE
                    )
                """)

                # Copy old data (if any)
                if has_old_data:
                    # Check which columns old table has to determine how to copy
                    if 'message_type' in log_columns:
                        # Old structure: message_type -> log_type
                        cursor.execute("""
                            INSERT INTO log_messages_new (segment_id, time_ns, log_type, message)
                            SELECT segment_id, time_ns, message_type, message
                            FROM log_messages
                        """)
                        logger.info(f"Copied {cursor.rowcount} entries from old table (message_type -> log_type)")
                    elif 'log_type' in log_columns:
                        # New column name but incomplete structure, only copy existing columns
                        # Find common columns between new and old tables
                        common_cols = log_columns & {'segment_id', 'time_ns', 'log_type', 'daemon',
                                                      'levelnum', 'filename', 'funcname', 'lineno',
                                                      'message', 'dongle_id', 'version', 'branch', 'commit'}
                        if common_cols:
                            cols_str = ', '.join(common_cols)
                            cursor.execute(f"""
                                INSERT INTO log_messages_new ({cols_str})
                                SELECT {cols_str}
                                FROM log_messages
                            """)
                            logger.info(f"Copied {cursor.rowcount} entries from old table (common columns: {common_cols})")
                else:
                    logger.info("Old table has no data, skipping copy")

                # Drop old table, rename new table
                cursor.execute("DROP TABLE log_messages")
                cursor.execute("ALTER TABLE log_messages_new RENAME TO log_messages")

                # Rebuild indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_log_segment_time
                    ON log_messages(segment_id, time_ns)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_log_type
                    ON log_messages(segment_id, log_type)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_log_daemon
                    ON log_messages(daemon)
                """)

                logger.info("log_messages table migrated successfully")

            self.conn.commit()
            logger.info("Database migration completed")

        except sqlite3.Error as e:
            logger.error(f"Error during migration: {e}")
            # Don't interrupt, continue execution

    # ========================================================================
    # Route Operations
    # ========================================================================

    def insert_route(self, route_id: str, dongle_id: str = None, timestamp: int = None,
                     start_timestamp: int = None, dbc_file: str = None) -> bool:
        """
        Insert or update route

        Args:
            route_id: Route ID
            dongle_id: Dongle ID (not stored in database, kept for compatibility)
            timestamp: Recording time (Unix timestamp)
            start_timestamp: Route start time (Unix timestamp)
            dbc_file: DBC file name
        """
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    INSERT INTO routes (route_id, timestamp, start_timestamp, dbc_file)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(route_id) DO UPDATE SET
                        timestamp = COALESCE(excluded.timestamp, routes.timestamp),
                        start_timestamp = COALESCE(excluded.start_timestamp, routes.start_timestamp),
                        dbc_file = COALESCE(excluded.dbc_file, routes.dbc_file)
                """, (route_id, timestamp, start_timestamp, dbc_file))
            return True
        except sqlite3.Error as e:
            logger.error(f"Error inserting route: {e}")
            return False

    def get_routes_with_time(self) -> List[Dict]:
        """Get all routes with their recording times"""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    SELECT
                        r.route_id,
                        r.start_timestamp,
                        r.total_segments,
                        r.dbc_file,
                        r.total_events,
                        MIN(s.start_time_ns + s.wall_time_offset) as fallback_timestamp_ns
                    FROM routes r
                    LEFT JOIN segments s ON r.route_id = s.route_id
                    GROUP BY r.route_id
                    ORDER BY COALESCE(r.start_timestamp, fallback_timestamp_ns / 1000000000) DESC
                """)
                rows = cur.fetchall()

            result = []
            for row in rows:
                route_id, start_timestamp, total_segments, dbc_file, total_events, fallback_timestamp_ns = row

                # Prioritize start_timestamp (accurate time calculated from GPS)
                if start_timestamp:
                    # start_timestamp is Unix timestamp (seconds)
                    from datetime import datetime
                    record_time = datetime.fromtimestamp(start_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                elif fallback_timestamp_ns:
                    # Use wallTimeNanos calculation (may be inaccurate)
                    from datetime import datetime
                    record_time = datetime.fromtimestamp(fallback_timestamp_ns / 1000000000).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    record_time = "N/A"

                result.append({
                    'route_id': route_id,
                    'record_time': record_time,
                    'total_segments': total_segments if total_segments else 0,
                    'dbc_file': dbc_file,
                    'total_events': total_events if total_events else 0
                })

            return result
        except sqlite3.Error as e:
            logger.error(f"Error getting routes: {e}")
            return []

    def get_route(self, route_id: str) -> Optional[Dict]:
        """Get single route information"""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    SELECT
                        route_id,
                        timestamp,
                        start_timestamp,
                        dbc_file,
                        total_segments,
                        total_events,
                        created_at
                    FROM routes
                    WHERE route_id = ?
                """, (route_id,))
                row = cur.fetchone()

            if row:
                return {
                    'route_id': row[0],
                    'timestamp': row[1],
                    'start_timestamp': row[2],
                    'dbc_file': row[3],
                    'total_segments': row[4],
                    'total_events': row[5],
                    'created_at': row[6]
                }
            return None
        except sqlite3.Error as e:
            logger.error(f"Error getting route {route_id}: {e}")
            return None

    def delete_route(self, route_id: str) -> bool:
        """Delete route and all related data (manual batch delete for performance)"""
        try:
            # First get all segment_id
            with self.get_cursor() as cur:
                cur.execute("SELECT segment_id FROM segments WHERE route_id = ?", (route_id,))
                segment_ids = [row[0] for row in cur.fetchall()]

            if segment_ids:
                logger.info(f"Deleting {len(segment_ids)} segments for route {route_id}")

                # Temporarily disable foreign key checks for performance
                with self.get_cursor() as cur:
                    cur.execute("PRAGMA foreign_keys = OFF")

                    # Batch delete related data
                    placeholders = ','.join('?' * len(segment_ids))

                    # Delete timeseries_data
                    cur.execute(f"DELETE FROM timeseries_data WHERE segment_id IN ({placeholders})", segment_ids)
                    logger.debug(f"Deleted timeseries_data for {len(segment_ids)} segments")

                    # Delete can_messages
                    cur.execute(f"DELETE FROM can_messages WHERE segment_id IN ({placeholders})", segment_ids)
                    logger.debug(f"Deleted can_messages for {len(segment_ids)} segments")

                    # Delete log_messages
                    cur.execute(f"DELETE FROM log_messages WHERE segment_id IN ({placeholders})", segment_ids)
                    logger.debug(f"Deleted log_messages for {len(segment_ids)} segments")

                    # Delete video_frame_timestamps
                    cur.execute(f"DELETE FROM video_frame_timestamps WHERE segment_id IN ({placeholders})", segment_ids)
                    logger.debug(f"Deleted video_frame_timestamps for {len(segment_ids)} segments")

                    # Delete segments
                    cur.execute("DELETE FROM segments WHERE route_id = ?", (route_id,))
                    logger.debug(f"Deleted segments for route {route_id}")

                    # Delete route
                    cur.execute("DELETE FROM routes WHERE route_id = ?", (route_id,))
                    logger.debug(f"Deleted route {route_id}")

                    # Restore foreign key checks
                    cur.execute("PRAGMA foreign_keys = ON")
            else:
                # No segments, delete route directly
                with self.get_cursor() as cur:
                    cur.execute("DELETE FROM routes WHERE route_id = ?", (route_id,))

            logger.info(f"Successfully deleted route: {route_id}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error deleting route: {e}")
            return False

    # ========================================================================
    # Segment Operations
    # ========================================================================

    def insert_segment(self, route_id: str, segment_num: int = None, segment_number: int = None,
                       start_time_ns: int = 0, end_time_ns: int = 0,
                       wall_time_offset: int = 0,
                       duration_sec: float = None,
                       rlog_path: str = None,
                       ecamera_path: str = None,
                       fcamera_path: str = None,
                       qcamera_path: str = None,
                       total_events: int = 0,
                       gps_timestamp: int = None,
                       thumbnail_path: str = None) -> Optional[int]:
        """
        Insert segment

        Args:
            route_id: Route ID
            segment_num: Segment number (alias, kept for compatibility)
            segment_number: Segment number
            start_time_ns: Start time (nanoseconds)
            end_time_ns: End time (nanoseconds)
            wall_time_offset: Wall time offset
            duration_sec: Duration (seconds)
            rlog_path: rlog file path
            ecamera_path: ecamera file path
            fcamera_path: fcamera file path
            qcamera_path: qcamera file path
            total_events: Total number of events
            gps_timestamp: Segment's GPS time (Unix timestamp in seconds), if available
            thumbnail_path: Video preview thumbnail path
        """
        # Support both parameter names
        if segment_number is None and segment_num is not None:
            segment_number = segment_num

        try:
            with self.get_cursor() as cur:
                # Check if segment already exists
                cur.execute("""
                    SELECT segment_id FROM segments
                    WHERE route_id = ? AND segment_number = ?
                """, (route_id, segment_number))
                existing = cur.fetchone()

                if existing:
                    # Segment already exists, delete old data and re-insert
                    segment_id = existing[0]
                    logger.warning(f"Segment {route_id}/{segment_number} already exists (ID: {segment_id}), deleting old data...")

                    # Delete associated timeseries_data, can_messages, log_messages, video_frame_timestamps
                    cur.execute("DELETE FROM timeseries_data WHERE segment_id = ?", (segment_id,))
                    cur.execute("DELETE FROM can_messages WHERE segment_id = ?", (segment_id,))
                    cur.execute("DELETE FROM log_messages WHERE segment_id = ?", (segment_id,))
                    cur.execute("DELETE FROM video_frame_timestamps WHERE segment_id = ?", (segment_id,))

                    # Update segment information
                    cur.execute("""
                        UPDATE segments SET
                            start_time_ns = ?,
                            end_time_ns = ?,
                            wall_time_offset = ?,
                            duration_seconds = ?,
                            total_events = ?,
                            rlog_path = ?,
                            ecamera_path = ?,
                            fcamera_path = ?,
                            qcamera_path = ?,
                            gps_timestamp = ?,
                            thumbnail_path = ?
                        WHERE segment_id = ?
                    """, (start_time_ns, end_time_ns, wall_time_offset,
                          duration_sec, total_events,
                          rlog_path, ecamera_path, fcamera_path, qcamera_path,
                          gps_timestamp, thumbnail_path,
                          segment_id))
                else:
                    # Insert new segment
                    cur.execute("""
                        INSERT INTO segments (
                            route_id, segment_number,
                            start_time_ns, end_time_ns, wall_time_offset,
                            duration_seconds, total_events,
                            rlog_path, ecamera_path, fcamera_path, qcamera_path,
                            gps_timestamp, thumbnail_path
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (route_id, segment_number,
                          start_time_ns, end_time_ns, wall_time_offset,
                          duration_sec, total_events,
                          rlog_path, ecamera_path, fcamera_path, qcamera_path,
                          gps_timestamp, thumbnail_path))

                    segment_id = cur.lastrowid

                # Update route segment count
                cur.execute("""
                    UPDATE routes
                    SET total_segments = (
                        SELECT COUNT(*) FROM segments WHERE route_id = ?
                    )
                    WHERE route_id = ?
                """, (route_id, route_id))

            return segment_id

        except sqlite3.Error as e:
            logger.error(f"Error inserting segment: {e}")
            return None

    def get_segments_with_time(self, route_id: str) -> List[Dict]:
        """Get all segments for specified route"""
        try:
            with self.get_cursor() as cur:
                # Query route's start_timestamp
                cur.execute("""
                    SELECT start_timestamp
                    FROM routes
                    WHERE route_id = ?
                """, (route_id,))
                route_row = cur.fetchone()
                route_start_timestamp = route_row[0] if route_row else None

                # Query all segments
                cur.execute("""
                    SELECT
                        segment_id,
                        segment_number,
                        start_time_ns,
                        end_time_ns,
                        wall_time_offset,
                        ROUND((end_time_ns - start_time_ns) / 1000000000.0, 2) as duration_seconds,
                        total_events,
                        gps_timestamp,
                        thumbnail_path
                    FROM segments
                    WHERE route_id = ?
                    ORDER BY segment_number
                """, (route_id,))
                rows = cur.fetchall()

            from datetime import datetime
            result = []

            for row in rows:
                segment_id, segment_number, start_time_ns, end_time_ns, wall_time_offset, duration_seconds, total_events, gps_timestamp, thumbnail_path = row

                # Prioritize segment's own GPS timestamp
                if gps_timestamp:
                    # Use segment's own GPS timestamp (segment start time)
                    segment_start_timestamp = gps_timestamp
                    segment_end_timestamp = segment_start_timestamp + duration_seconds

                    start_time = datetime.fromtimestamp(segment_start_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    end_time = datetime.fromtimestamp(segment_end_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                elif route_start_timestamp:
                    # Calculate from route's start_timestamp (accurate time calculated from GPS)
                    segment_start_timestamp = route_start_timestamp + (segment_number * 60)
                    segment_end_timestamp = segment_start_timestamp + duration_seconds

                    start_time = datetime.fromtimestamp(segment_start_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    end_time = datetime.fromtimestamp(segment_end_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    # Use wallTimeNanos calculation (may be inaccurate)
                    start_timestamp_ns = start_time_ns + wall_time_offset
                    end_timestamp_ns = end_time_ns + wall_time_offset

                    start_time = datetime.fromtimestamp(start_timestamp_ns / 1000000000).strftime('%Y-%m-%d %H:%M:%S')
                    end_time = datetime.fromtimestamp(end_timestamp_ns / 1000000000).strftime('%Y-%m-%d %H:%M:%S')

                result.append({
                    'segment_id': segment_id,
                    'segment_num': segment_number,
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration_sec': duration_seconds,
                    'total_events': total_events if total_events else 0,
                    'thumbnail_path': thumbnail_path
                })

            return result
        except sqlite3.Error as e:
            logger.error(f"Error getting segments: {e}")
            return []

    def get_segment_by_id(self, segment_id: int) -> Optional[Dict]:
        """Get segment information by ID"""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    SELECT
                        segment_id, route_id, segment_number,
                        start_time_ns, end_time_ns, wall_time_offset,
                        ecamera_path, fcamera_path, qcamera_path,
                        total_events
                    FROM segments
                    WHERE segment_id = ?
                """, (segment_id,))
                row = cur.fetchone()

            if row:
                return {
                    'segment_id': row[0],
                    'route_id': row[1],
                    'segment_number': row[2],
                    'start_time_ns': row[3],
                    'end_time_ns': row[4],
                    'wall_time_offset': row[5],
                    'ecamera_path': row[6],
                    'fcamera_path': row[7],
                    'qcamera_path': row[8],
                    'total_events': row[9]
                }
            return None

        except sqlite3.Error as e:
            logger.error(f"Error getting segment: {e}")
            return None

    def delete_segments(self, segment_ids: List[int]) -> bool:
        """Delete multiple segments"""
        try:
            with self.get_cursor() as cur:
                placeholders = ','.join('?' * len(segment_ids))
                cur.execute(
                    f"DELETE FROM segments WHERE segment_id IN ({placeholders})",
                    segment_ids
                )
            logger.info(f"Deleted {len(segment_ids)} segments")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error deleting segments: {e}")
            return False

    # ========================================================================
    # Timeseries Data Operations
    # ========================================================================

    def insert_timeseries_batch(self, segment_id: int, batch: List[Tuple[int, str, float, Any]]):
        """Batch insert timeseries data (no auto commit, controlled by caller)

        Args:
            segment_id: Segment ID
            batch: List of (time_ns, signal_name, value, _unused)
        """
        try:
            # Convert format: add segment_id to each row
            data = [(segment_id, time_ns, signal_name, value)
                    for time_ns, signal_name, value, _ in batch]

            # Use conn.cursor() directly, not context manager to avoid auto commit
            cur = self.conn.cursor()
            cur.executemany("""
                INSERT INTO timeseries_data (segment_id, time_ns, signal_name, value)
                VALUES (?, ?, ?, ?)
            """, data)
            cur.close()
        except sqlite3.Error as e:
            logger.error(f"Error inserting timeseries data: {e}")
            raise

    def get_timeseries_data(self, segment_id: int, signal_names,
                            start_time_ns: int, end_time_ns: int):
        """Query timeseries data

        Args:
            segment_id: Segment ID
            signal_names: Signal name (single string) or list of signal names
            start_time_ns: Start time
            end_time_ns: End time

        Returns:
            If single string passed: List[(time_ns, value)]
            If list passed: Dict[signal_name, List[(time_ns, value)]]
        """
        # Handle backward compatibility: if string, convert to list
        if isinstance(signal_names, str):
            signal_names = [signal_names]
            return_single = True
        else:
            return_single = False

        result = {name: [] for name in signal_names}

        # Separate regular signals and custom calculated signals
        regular_signals = []
        custom_signals = []

        for signal_name in signal_names:
            if self.signal_calculator and self.signal_calculator.is_custom_signal(signal_name):
                custom_signals.append(signal_name)
            else:
                regular_signals.append(signal_name)

        # Query regular signals
        if regular_signals:
            try:
                with self.get_cursor() as cur:
                    placeholders = ','.join('?' * len(regular_signals))
                    cur.execute(f"""
                        SELECT signal_name, time_ns, value
                        FROM timeseries_data
                        WHERE segment_id = ?
                          AND time_ns BETWEEN ? AND ?
                          AND signal_name IN ({placeholders})
                        ORDER BY time_ns
                    """, (segment_id, start_time_ns, end_time_ns, *regular_signals))

                    for row in cur.fetchall():
                        signal_name, time_ns, value = row
                        result[signal_name].append((time_ns, value))

            except sqlite3.Error as e:
                logger.error(f"Error getting timeseries data: {e}")

        # Calculate custom signals
        if custom_signals and self.signal_calculator:
            for signal_name in custom_signals:
                try:
                    custom_data = self.signal_calculator.calculate_signal(
                        signal_name, segment_id, start_time_ns, end_time_ns
                    )
                    result[signal_name] = custom_data
                except Exception as e:
                    logger.error(f"Error calculating custom signal {signal_name}: {e}")

        # If original input was single string, only return that signal's data
        if return_single:
            return result[list(result.keys())[0]]
        return result

    def get_available_signals(self, segment_id: int) -> List[str]:
        """Get all available signals for specified segment (including custom signals)"""
        try:
            # Get regular signals
            with self.get_cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT signal_name
                    FROM timeseries_data
                    WHERE segment_id = ?
                    ORDER BY signal_name
                """, (segment_id,))
                signals = [row[0] for row in cur.fetchall()]

            # Add custom calculated signals (custom signals are always available since they're dynamically calculated)
            if self.signal_calculator and hasattr(self.signal_calculator, 'custom_signals'):
                custom_signal_names = list(self.signal_calculator.custom_signals.keys())
                signals.extend(custom_signal_names)
                logger.debug(f"Added {len(custom_signal_names)} custom signals to available signals")

            return signals
        except sqlite3.Error as e:
            logger.error(f"Error getting available signals: {e}")
            return []

    def get_all_defined_signals(self) -> Dict[str, Dict]:
        """
        取得所有訊號定義（從 Cereal 和 CAN 訊號定義表）

        Returns:
            Dict of {signal_name: signal_info}
            signal_info contains: name_cn, description_cn, unit_cn, unit
        """
        signals = {}

        try:
            with self.get_cursor() as cur:
                # Get Cereal signal definitions
                cur.execute("""
                    SELECT full_name, name_cn, description_cn, unit, unit_cn
                    FROM cereal_signal_definitions
                    ORDER BY message_type, signal_name
                """)

                for row in cur.fetchall():
                    signal_name = row[0]
                    signals[signal_name] = {
                        'name_cn': row[1],
                        'description_cn': row[2],
                        'unit': row[3],
                        'unit_cn': row[4]
                    }

                # Get CAN signal definitions
                cur.execute("""
                    SELECT full_name, signal_name_cn, description_cn, unit, unit_cn
                    FROM can_signal_definitions
                    ORDER BY can_id, signal_name
                """)

                for row in cur.fetchall():
                    signal_name = row[0]
                    signals[signal_name] = {
                        'name_cn': row[1],
                        'description_cn': row[2],
                        'unit': row[3],
                        'unit_cn': row[4]
                    }

            logger.info(f"Loaded {len(signals)} signal definitions")

        except sqlite3.Error as e:
            logger.warning(f"Failed to load signal definitions: {e}")

        return signals

    # ========================================================================
    # CAN Messages Operations
    # ========================================================================

    def insert_can_batch(self, segment_id: int, batch: List[Tuple[int, int, bytes, Any]]):
        """Batch insert CAN messages (no auto commit, controlled by caller)

        Args:
            segment_id: Segment ID
            batch: List of (time_ns, address, data, _unused)
        """
        try:
            # Convert format: add segment_id to each row, ignore 4th column (can_src)
            data = [(segment_id, time_ns, address, can_data)
                    for time_ns, address, can_data, _ in batch]

            # Use conn.cursor() directly, not context manager to avoid auto commit
            cur = self.conn.cursor()
            cur.executemany("""
                INSERT INTO can_messages (segment_id, time_ns, address, data)
                VALUES (?, ?, ?, ?)
            """, data)
            cur.close()
        except sqlite3.Error as e:
            logger.error(f"Error inserting CAN messages: {e}")
            raise

    def get_can_messages(self, segment_id: int, start_time_ns: int, end_time_ns: int,
                         can_ids: List[int] = None) -> List[Tuple]:
        """Query CAN messages

        Returns:
            List of (time_ns, address, data)
        """
        try:
            with self.get_cursor() as cur:
                if can_ids:
                    placeholders = ','.join('?' * len(can_ids))
                    cur.execute(f"""
                        SELECT time_ns, address, data
                        FROM can_messages
                        WHERE segment_id = ?
                          AND time_ns BETWEEN ? AND ?
                          AND address IN ({placeholders})
                        ORDER BY time_ns
                    """, (segment_id, start_time_ns, end_time_ns, *can_ids))
                else:
                    cur.execute("""
                        SELECT time_ns, address, data
                        FROM can_messages
                        WHERE segment_id = ?
                          AND time_ns BETWEEN ? AND ?
                        ORDER BY time_ns
                    """, (segment_id, start_time_ns, end_time_ns))

                return cur.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Error getting CAN messages: {e}")
            return []

    # ========================================================================
    # Log Messages Operations
    # ========================================================================

    def insert_log_messages_batch(self, data: List[Tuple]):
        """Batch insert log messages (no auto commit, controlled by caller)

        Args:
            data: List of tuples with format:
                  (segment_id, time_ns, log_type, daemon, levelnum, filename,
                   funcname, lineno, message, dongle_id, version, branch, commit)
        """
        try:
            # Use conn.cursor() directly, not context manager to avoid auto commit
            cur = self.conn.cursor()
            cur.executemany("""
                INSERT INTO log_messages (
                    segment_id, time_ns, log_type,
                    daemon, levelnum, filename, funcname, lineno,
                    message,
                    dongle_id, version, branch, "commit"
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
            cur.close()
        except sqlite3.Error as e:
            logger.error(f"Error inserting log messages: {e}")
            raise

    def get_log_messages(self, segment_id: int, start_time_ns: int, end_time_ns: int,
                         log_type: str = None) -> List[Dict]:
        """Query log messages

        Args:
            segment_id: Segment ID
            start_time_ns: Start time (nanoseconds)
            end_time_ns: End time (nanoseconds)
            log_type: Log type filter ('log' or 'error', None means all)

        Returns:
            List of log message dicts with keys:
                time_ns, log_type, daemon, levelnum, filename, funcname, lineno,
                message, dongle_id, version, branch, commit
        """
        try:
            with self.get_cursor() as cur:
                if log_type:
                    cur.execute("""
                        SELECT
                            time_ns, log_type, daemon, levelnum, filename,
                            funcname, lineno, message, dongle_id, version, branch, "commit"
                        FROM log_messages
                        WHERE segment_id = ?
                          AND time_ns BETWEEN ? AND ?
                          AND log_type = ?
                        ORDER BY time_ns
                    """, (segment_id, start_time_ns, end_time_ns, log_type))
                else:
                    cur.execute("""
                        SELECT
                            time_ns, log_type, daemon, levelnum, filename,
                            funcname, lineno, message, dongle_id, version, branch, "commit"
                        FROM log_messages
                        WHERE segment_id = ?
                          AND time_ns BETWEEN ? AND ?
                        ORDER BY time_ns
                    """, (segment_id, start_time_ns, end_time_ns))

                return [
                    {
                        'time_ns': row[0],
                        'log_type': row[1],
                        'daemon': row[2],
                        'levelnum': row[3],
                        'filename': row[4],
                        'funcname': row[5],
                        'lineno': row[6],
                        'message': row[7],
                        'dongle_id': row[8],
                        'version': row[9],
                        'branch': row[10],
                        'commit': row[11]
                    }
                    for row in cur.fetchall()
                ]
        except sqlite3.Error as e:
            logger.error(f"Error getting log messages: {e}")
            return []

    # ========================================================================
    # Video Frame Timestamps Operations
    # ========================================================================

    def insert_video_timestamps_batch(self, data: List[Tuple]):
        """Batch insert video frame timestamps (no auto commit, controlled by caller)

        Args:
            data: List of tuples with format:
                  (segment_id, camera, frame_number, timestamp_sof)
        """
        try:
            # Use conn.cursor() directly, not context manager to avoid auto commit
            cur = self.conn.cursor()
            cur.executemany("""
                INSERT OR REPLACE INTO video_frame_timestamps (
                    segment_id, camera, frame_number, timestamp_sof
                )
                VALUES (?, ?, ?, ?)
            """, data)
            cur.close()
            logger.info(f"Inserted {len(data)} video frame timestamps")
        except sqlite3.Error as e:
            logger.error(f"Error inserting video timestamps: {e}")
            raise

    def get_video_timestamps(self, segment_id: int, camera: str) -> List[int]:
        """Query all frame timestamps for specified segment and camera

        Args:
            segment_id: Segment ID
            camera: Camera type ('ecamera', 'fcamera', 'qcamera', 'dcamera')

        Returns:
            List of timestamp_sof values, ordered by frame_number
        """
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    SELECT timestamp_sof
                    FROM video_frame_timestamps
                    WHERE segment_id = ? AND camera = ?
                    ORDER BY frame_number
                """, (segment_id, camera))
                return [row[0] for row in cur.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error getting video timestamps: {e}")
            return []

    # ========================================================================
    # Signal Definitions Operations
    # ========================================================================

    def insert_cereal_signal_definition(self, message_type: str, signal_name: str,
                                        data_type: str = None, unit: str = None,
                                        unit_cn: str = None, name_cn: str = None):
        """Insert Cereal signal definition"""
        full_name = f"{message_type}.{signal_name}"
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    INSERT OR REPLACE INTO cereal_signal_definitions
                    (message_type, signal_name, full_name, data_type, unit, unit_cn, name_cn)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (message_type, signal_name, full_name, data_type, unit, unit_cn, name_cn))
        except sqlite3.Error as e:
            logger.error(f"Error inserting cereal signal definition: {e}")

    def get_signal_unit(self, signal_name: str) -> Tuple[Optional[str], Optional[str]]:
        """Get signal unit (English, Chinese)"""
        try:
            with self.get_cursor() as cur:
                # First check cereal signals
                cur.execute("""
                    SELECT unit, unit_cn
                    FROM cereal_signal_definitions
                    WHERE full_name = ?
                """, (signal_name,))
                row = cur.fetchone()

                if row:
                    return row[0], row[1]

                # Then check CAN signals
                cur.execute("""
                    SELECT unit, unit_cn
                    FROM can_signal_definitions
                    WHERE full_name = ?
                """, (signal_name,))
                row = cur.fetchone()

                if row:
                    return row[0], row[1]

                # Finally check custom signals
                cur.execute("""
                    SELECT unit, unit_cn
                    FROM custom_signals
                    WHERE signal_name = ?
                """, (signal_name,))
                row = cur.fetchone()

                if row:
                    return row[0], row[1]

            return None, None

        except sqlite3.Error as e:
            logger.error(f"Error getting signal unit: {e}")
            return None, None

    # ========================================================================
    # Statistics Operations
    # ========================================================================

    def update_segment_event_count(self, segment_id: int, count: int):
        """Update segment event count"""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    UPDATE segments
                    SET total_events = ?
                    WHERE segment_id = ?
                """, (count, segment_id))

                # Update route's total event count
                cur.execute("""
                    UPDATE routes
                    SET total_events = (
                        SELECT SUM(total_events)
                        FROM segments
                        WHERE route_id = routes.route_id
                    )
                    WHERE route_id = (
                        SELECT route_id FROM segments WHERE segment_id = ?
                    )
                """, (segment_id,))
        except sqlite3.Error as e:
            logger.error(f"Error updating event count: {e}")

    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        try:
            with self.get_cursor() as cur:
                # Count records in each table
                cur.execute("SELECT COUNT(*) FROM routes")
                routes_count = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM segments")
                segments_count = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM timeseries_data")
                timeseries_count = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM can_messages")
                can_count = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM log_messages")
                log_count = cur.fetchone()[0]

                # Database file size
                db_size = self.db_path.stat().st_size / (1024 * 1024)  # MB

                return {
                    'routes': routes_count,
                    'segments': segments_count,
                    'timeseries_data': timeseries_count,
                    'can_messages': can_count,
                    'log_messages': log_count,
                    'db_size_mb': round(db_size, 2)
                }
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}

    # ========================================================================
    # Auto-create Missing Signal Definitions
    # ========================================================================

    def auto_create_missing_signal_definitions(self, segment_id: int = None) -> int:
        """
        自動創建缺失的訊號定義
        從 timeseries_data 中查找沒有定義的訊號，並自動創建定義

        Args:
            segment_id: 如果指定，只處理該 segment 的訊號；否則處理所有訊號

        Returns:
            創建的訊號定義數量
        """
        try:
            with self.get_cursor() as cur:
                # 查找缺失的訊號定義
                if segment_id is not None:
                    cur.execute("""
                        SELECT DISTINCT t.signal_name
                        FROM timeseries_data t
                        LEFT JOIN cereal_signal_definitions d ON t.signal_name = d.full_name
                        WHERE t.segment_id = ? AND d.full_name IS NULL AND t.signal_name NOT LIKE 'CAN_%'
                    """, (segment_id,))
                else:
                    cur.execute("""
                        SELECT DISTINCT t.signal_name
                        FROM timeseries_data t
                        LEFT JOIN cereal_signal_definitions d ON t.signal_name = d.full_name
                        WHERE d.full_name IS NULL AND t.signal_name NOT LIKE 'CAN_%'
                    """)

                missing_signals = [row[0] for row in cur.fetchall()]

                if not missing_signals:
                    return 0

                logger.info(f"發現 {len(missing_signals)} 個缺失的訊號定義，開始自動創建...")

                created_count = 0

                for full_signal_name in missing_signals:
                    # 從訊號名稱推斷資訊
                    parts = full_signal_name.split('.')
                    if len(parts) < 2:
                        continue

                    msg_type = parts[0]
                    signal_name = full_signal_name[len(msg_type) + 1:]  # 移除 "msgType."

                    # 根據訊號名稱推測資料類型
                    lower_name = full_signal_name.lower()
                    if any(x in lower_name for x in ['type', 'state', 'mode', 'name', 'ecu', 'event']):
                        data_type = 'Int32'  # 枚舉類型
                    elif any(x in lower_name for x in ['index', 'count', 'id', 'frame']):
                        data_type = 'Int32'
                    elif 'bool' in lower_name or any(x in lower_name for x in ['pressed', 'active', 'valid', 'enabled', 'detected']):
                        data_type = 'Bool'
                    else:
                        data_type = 'Float32'  # 預設為浮點數

                    # 根據訊號名稱推測單位
                    unit = ''
                    unit_cn = ''
                    if 'speed' in lower_name or 'velocity' in lower_name:
                        unit = 'm/s'
                        unit_cn = '公尺/秒'
                    elif 'accel' in lower_name:
                        unit = 'm/s²'
                        unit_cn = '公尺/秒²'
                    elif 'angle' in lower_name and 'deg' in lower_name:
                        unit = 'deg'
                        unit_cn = '度'
                    elif 'rate' in lower_name and ('deg' in lower_name or 'yaw' in lower_name or 'pitch' in lower_name):
                        unit = 'deg/s'
                        unit_cn = '度/秒'
                    elif 'distance' in lower_name or 'drel' in lower_name or 'wheelbase' in lower_name:
                        unit = 'm'
                        unit_cn = '公尺'
                    elif 'torque' in lower_name:
                        unit = 'Nm'
                        unit_cn = '牛頓·公尺'
                    elif 'temp' in lower_name or 'temperature' in lower_name:
                        unit = '°C'
                        unit_cn = '攝氏度'
                    elif 'percent' in lower_name:
                        unit = '%'
                        unit_cn = '%'
                    elif 'voltage' in lower_name:
                        unit = 'V'
                        unit_cn = '伏特'
                    elif 'current' in lower_name:
                        unit = 'A'
                        unit_cn = '安培'
                    elif 'power' in lower_name and 'w' in lower_name:
                        unit = 'W'
                        unit_cn = '瓦特'
                    elif 'time' in lower_name and ('ms' in lower_name or 'milli' in lower_name):
                        unit = 'ms'
                        unit_cn = '毫秒'
                    elif 'time' in lower_name:
                        unit = 's'
                        unit_cn = '秒'
                    elif 'rpm' in lower_name:
                        unit = 'rpm'
                        unit_cn = '轉/分'

                    # 中文名稱（目前留空，可以後續手動補充）
                    name_cn = ''

                    # 插入資料庫
                    try:
                        cur.execute("""
                            INSERT OR REPLACE INTO cereal_signal_definitions
                            (message_type, signal_name, full_name, data_type, unit, unit_cn, name_cn)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (msg_type, signal_name, full_signal_name, data_type, unit, unit_cn, name_cn))
                        created_count += 1
                    except Exception as e:
                        logger.error(f"創建訊號定義失敗 {full_signal_name}: {e}")

                logger.info(f"成功創建 {created_count} 個訊號定義")
                return created_count

        except sqlite3.Error as e:
            logger.error(f"自動創建訊號定義時發生錯誤: {e}")
            return 0
