# -*- coding: utf-8 -*-
"""
Segment Importer - Import segment rlog data to database
"""
import os
import time
import json
import capnp
from pathlib import Path
from typing import Callable, Optional, Dict, List
import logging
from cantools.database.namedsignalvalue import NamedSignalValue
import av
from PIL import Image

logger = logging.getLogger(__name__)

# Load Cap'n Proto schema
try:
    capnp_log = capnp.load('log.capnp')
except Exception as e:
    logger.error(f"Failed to load log.capnp: {e}")
    capnp_log = None


class SegmentImporter:
    """Segment importer - handles rlog file parsing and data import"""

    def __init__(self, db_manager, dbc_parser=None, translation_manager=None):
        """
        Initialize importer

        Args:
            db_manager: DatabaseManager instance
            dbc_parser: DBCParser instance (optional, for CAN signal parsing)
            translation_manager: TranslationManager instance (optional)
        """
        self.db_manager = db_manager
        self.dbc_parser = dbc_parser
        self.translation_manager = translation_manager
        self.progress_callback: Optional[Callable] = None
        self.log_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable):
        """Set progress callback"""
        self.progress_callback = callback

    def set_log_callback(self, callback: Callable):
        """Set log callback"""
        self.log_callback = callback

    def _log(self, message: str):
        """Output log message"""
        logger.info(message)
        if self.log_callback:
            self.log_callback(message)

    def _progress(self, value: int):
        """Update progress"""
        if self.progress_callback:
            self.progress_callback(value)

    def generate_thumbnail(self, video_path: str, output_path: str, width: int = 320, height: int = 180) -> bool:
        """
        Generate preview thumbnail from video

        Args:
            video_path: Video file path
            output_path: Output thumbnail path
            width: Thumbnail width
            height: Thumbnail height

        Returns:
            True if successful, False otherwise
        """
        try:
            # Open video file
            container = av.open(video_path)

            # Get first video frame
            for frame in container.decode(video=0):
                # Convert to PIL Image
                img = frame.to_image()

                # Resize
                img.thumbnail((width, height), Image.Resampling.LANCZOS)

                # Save thumbnail
                img.save(output_path, 'JPEG', quality=85)

                container.close()
                return True

            container.close()
            return False

        except Exception as e:
            logger.warning(f"Failed to generate thumbnail from {video_path}: {e}")
            return False

    def parse_segment_path(self, rlog_path: str):
        """
        Parse segment information from rlog path

        Args:
            rlog_path: rlog file path

        Returns:
            (route_id, dongle_id, timestamp, segment_num, segment_dir)
        """
        segment_dir = os.path.dirname(rlog_path)
        segment_name = os.path.basename(segment_dir)
        parts = segment_name.split('--')

        if len(parts) != 3:
            raise ValueError(f"Invalid segment directory format: {segment_name}")

        dongle_id = parts[0]
        timestamp_hex = parts[1]
        segment_num = int(parts[2])

        route_id = f"{dongle_id}--{timestamp_hex}"
        timestamp = int(timestamp_hex, 16)

        return route_id, dongle_id, timestamp, segment_num, segment_dir

    def _parse_log_message(self, segment_id: int, time_ns: int, log_type: str, log_text: str):
        """
        Parse JSON format of logMessage or errorLogMessage

        Args:
            segment_id: Segment ID
            time_ns: Timestamp (nanoseconds)
            log_type: Log type ('log' or 'error')
            log_text: JSON formatted log text

        Returns:
            Tuple with format:
                (segment_id, time_ns, log_type, daemon, levelnum, filename,
                 funcname, lineno, message, dongle_id, version, branch, commit)
            or None (if parsing failed)
        """
        try:
            log_dict = json.loads(log_text)

            # Extract fields
            daemon = log_dict.get('ctx', {}).get('daemon', None)
            levelnum = log_dict.get('levelnum', None)
            filename = log_dict.get('filename', None)
            funcname = log_dict.get('funcname', None)
            lineno = log_dict.get('lineno', None)

            # Message content
            msg = log_dict.get('msg', '')
            if isinstance(msg, dict):
                # If msg is an object (like car fingerprint), convert to JSON string
                msg = json.dumps(msg, ensure_ascii=False)
            else:
                msg = str(msg)

            # Context
            ctx = log_dict.get('ctx', {})
            dongle_id = ctx.get('dongle_id', None)
            version = ctx.get('version', None)
            branch = ctx.get('branch', None)
            commit = ctx.get('commit', None)

            return (
                segment_id, time_ns, log_type,
                daemon, levelnum, filename, funcname, lineno,
                msg,
                dongle_id, version, branch, commit
            )

        except json.JSONDecodeError:
            # If not JSON, store raw text directly
            return (
                segment_id, time_ns, log_type,
                None, None, None, None, None,
                log_text,
                None, None, None, None
            )
        except Exception as e:
            logger.warning(f"Failed to parse log message: {e}")
            return None

    def extract_numeric_value(self, obj, field_name: str):
        """
        Safely extract numeric value (including enums)

        Args:
            obj: Cereal object
            field_name: Field name

        Returns:
            Numeric value (float) or None
        """
        try:
            value = getattr(obj, field_name)
            if isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, bool):
                return float(1 if value else 0)
            elif hasattr(value, '__class__') and hasattr(value.__class__, '__name__'):
                # Handle enum types (like GearShifter)
                if 'Enum' in str(type(value)):
                    # capnp enums use .raw attribute to get integer value
                    if hasattr(value, 'raw'):
                        return float(value.raw)
            return None
        except:
            return None

    def extract_all_fields(self, obj, prefix: str, max_array_depth: int = 10) -> List[tuple]:
        """
        Extract all numeric fields from object (including structs and arrays)

        Args:
            obj: Cereal object
            prefix: Signal name prefix (e.g. "carState")
            max_array_depth: Maximum array index (to avoid infinite expansion)

        Returns:
            List of [(signal_name, value), ...]
        """
        results = []
        try:
            # Check if object has schema (exclude arrays and other types)
            if not hasattr(obj, 'schema'):
                return results

            # Get all attributes
            schema = obj.schema
            # schema.non_union_fields returns a list of strings, not objects
            for field_name in schema.non_union_fields:
                try:
                    field_value = getattr(obj, field_name)

                    # Try to extract numeric value directly (including enums)
                    numeric_value = self.extract_numeric_value(obj, field_name)
                    if numeric_value is not None:
                        signal_name = f"{prefix}.{field_name}"
                        results.append((signal_name, numeric_value))
                        continue

                    # Check if it's a struct (has schema attribute)
                    if hasattr(field_value, 'schema'):
                        # Recursively expand struct
                        struct_results = self.extract_all_fields(field_value, f"{prefix}.{field_name}", max_array_depth)
                        results.extend(struct_results)
                        continue

                    # Check if it's an array (List)
                    # Cap'n Proto's _DynamicListReader doesn't have __iter__, so check type name
                    is_list = 'List' in str(type(field_value)) or (hasattr(field_value, '__iter__') and not isinstance(field_value, (str, bytes)))
                    if is_list:
                        try:
                            # Try to get array length
                            array_length = len(field_value)
                            # Limit array expansion count
                            for i in range(min(array_length, max_array_depth)):
                                try:
                                    item = field_value[i]

                                    # If array element is struct, recursively expand
                                    if hasattr(item, 'schema'):
                                        item_results = self.extract_all_fields(item, f"{prefix}.{field_name}[{i}]", max_array_depth)
                                        results.extend(item_results)
                                    else:
                                        # If it's a simple numeric value
                                        if isinstance(item, (int, float)):
                                            signal_name = f"{prefix}.{field_name}[{i}]"
                                            results.append((signal_name, float(item)))
                                        elif isinstance(item, bool):
                                            signal_name = f"{prefix}.{field_name}[{i}]"
                                            results.append((signal_name, float(1 if item else 0)))
                                        elif 'Enum' in str(type(item)) and hasattr(item, 'raw'):
                                            # If it's an enum
                                            signal_name = f"{prefix}.{field_name}[{i}]"
                                            results.append((signal_name, float(item.raw)))
                                except Exception as e:
                                    logger.debug(f"Failed to extract array item {prefix}.{field_name}[{i}]: {e}")
                        except Exception as e:
                            logger.debug(f"Failed to process array {prefix}.{field_name}: {e}")

                except Exception as e:
                    logger.debug(f"Failed to extract {prefix}.{field_name}: {e}")
        except Exception as e:
            logger.warning(f"Failed to get schema for {prefix}: {e}")
        return results

    def get_route_start_time(self, route_dir: str, route_id: str) -> int:
        """
        Scan all segments in route to find correct start time

        Args:
            route_dir: route directory path (parent directory containing all segments)
            route_id: route ID (format: dongle_id--hex)

        Returns:
            Route start time as Unix timestamp (seconds), or 0 if not found
        """
        import os
        from pathlib import Path

        logger.info(f"Scanning all segments in route {route_id} to get correct time")

        # List all segment directories
        try:
            route_path = Path(route_dir)
            if not route_path.exists():
                logger.warning(f"Route directory does not exist: {route_dir}")
                return 0

            # Find all segment directories belonging to this route (format: dongle_id--hex--segment_num)
            segment_dirs = []
            for item in route_path.iterdir():
                if item.is_dir():
                    parts = item.name.split('--')
                    if len(parts) == 3:
                        # Check if it belongs to this route
                        item_route_id = f"{parts[0]}--{parts[1]}"
                        if item_route_id == route_id:
                            try:
                                seg_num = int(parts[2])
                                rlog = item / 'rlog'
                                if rlog.exists():
                                    segment_dirs.append((seg_num, str(rlog)))
                            except:
                                pass

            if not segment_dirs:
                logger.warning("No segments found")
                return 0

            # Sort by segment number
            segment_dirs.sort(key=lambda x: x[0])
            logger.info(f"Found {len(segment_dirs)} segments")

            # Scan each segment to find the first one with GPS time
            for seg_num, rlog_path in segment_dirs:
                try:
                    with open(rlog_path, 'rb') as f:
                        data = f.read()

                    events = list(capnp_log.Event.read_multiple_bytes(data))

                    # Find liveLocationKalman.unixTimestampMillis
                    for event in events:
                        try:
                            if event.which() == 'liveLocationKalman':
                                llk = event.liveLocationKalman
                                if hasattr(llk, 'unixTimestampMillis'):
                                    unix_ts_ms = llk.unixTimestampMillis
                                    if unix_ts_ms > 0:
                                        # Found it! Calculate segment 0 time
                                        segment_time = int(unix_ts_ms / 1000)
                                        route_start_time = segment_time - (seg_num * 60)

                                        logger.info(f"Found GPS time in segment {seg_num}: {segment_time}")
                                        logger.info(f"Calculated route start time: {route_start_time}")

                                        return route_start_time
                        except:
                            pass

                except Exception as e:
                    logger.warning(f"Cannot read segment {seg_num}: {e}")
                    continue

            logger.warning("No GPS time found in any segment")
            return 0

        except Exception as e:
            logger.error(f"Failed to scan route: {e}")
            return 0

    def import_segment(self, rlog_path: str, dbc_path: str = None) -> bool:
        """
        Import a single segment, processing all Cereal and CAN signals

        Args:
            rlog_path: rlog file path
            dbc_path: DBC file path (optional)

        Returns:
            Success status
        """
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        if not capnp_log:
            self._log(t("Error: Cap'n Proto schema not loaded"))
            return False

        try:
            self._progress(0)
            self._log(t("Starting import: {0}").format(rlog_path))

            # If DBC path is provided, load DBC
            if dbc_path and os.path.exists(dbc_path):
                try:
                    from .dbc_parser import DBCParser
                    self.dbc_parser = DBCParser(dbc_path)
                    self._log(t("Loaded DBC: {0}").format(dbc_path))
                except Exception as e:
                    logger.warning(f"Failed to load DBC: {e}")

            # Parse path
            route_id, dongle_id, timestamp, segment_num, segment_dir = self.parse_segment_path(rlog_path)
            self._log(t("Route ID: {0}, Segment: {1}").format(route_id, segment_num))

            # Check files
            ecamera_path = os.path.join(segment_dir, 'ecamera.hevc')
            fcamera_path = os.path.join(segment_dir, 'fcamera.hevc')
            qcamera_path = os.path.join(segment_dir, 'qcamera.ts')

            self._progress(5)

            # Read rlog file
            self._log(t("Reading rlog file..."))
            with open(rlog_path, 'rb') as f:
                data = f.read()
            self._log(t("File size: {0:,} bytes").format(len(data)))

            self._progress(10)

            # Parse events
            self._log(t("Parsing Cap'n Proto events..."))
            events = list(capnp_log.Event.read_multiple_bytes(data))
            self._log(t("Total events: {0:,}").format(len(events)))

            self._progress(20)

            # Extract wall_time_offset
            wall_time_offset = 0
            for event in events[:100]:
                try:
                    if event.which() == 'initData':
                        init_data = event.initData
                        wall_time_ns = init_data.wallTimeNanos
                        wall_time_offset = wall_time_ns - event.logMonoTime
                        self._log(t("Found wallTimeOffset: {0} ns").format(wall_time_offset))
                        break
                except:
                    pass

            self._progress(25)

            # Extract correct recording time
            # Workflow:
            # 1. First check if current segment has correct GPS time
            # 2. If yes, use GPS time and check if need to update route's start_timestamp
            # 3. If no, check if database has route's start_timestamp
            # 4. If database also doesn't have it, scan entire route to calculate time

            self._log(t("Checking current segment GPS time..."))
            current_gps_timestamp = None
            for event in events:
                try:
                    if event.which() == 'liveLocationKalman':
                        llk = event.liveLocationKalman
                        if hasattr(llk, 'unixTimestampMillis'):
                            unix_ts_ms = llk.unixTimestampMillis
                            if unix_ts_ms > 0:  # Ensure it's not 0 (GPS not locked)
                                current_gps_timestamp = int(unix_ts_ms / 1000)  # Convert to seconds
                                self._log(t("✓ Current segment has correct GPS time: {0}").format(current_gps_timestamp))
                                break
                except:
                    pass

            # First check if database already has route's start_timestamp
            route_info = self.db_manager.get_route(route_id)
            route_start_time_from_db = route_info.get('start_timestamp') if route_info else None

            # Variable to store calculated route start time (if any)
            route_start_time_to_save = None

            if current_gps_timestamp:
                # Case 1: Current segment has correct GPS time
                timestamp = current_gps_timestamp
                self._log(t("Using current segment GPS time: {0}").format(timestamp))

                # If database doesn't have route start_timestamp yet, calculate from current GPS and update
                if not route_start_time_from_db:
                    route_start_time_to_save = timestamp - (segment_num * 60)
                    self._log(t("Calculated route start time: {0} - ({1} × 60) = {2}").format(timestamp, segment_num, route_start_time_to_save))
                    self._log(t("Will update route start_timestamp in database"))

            else:
                # Case 2: Current segment doesn't have GPS time
                self._log(t("⚠ Current segment does not have GPS time"))

                if route_start_time_from_db:
                    # Case 2a: Database has route start_timestamp, calculate directly
                    timestamp = route_start_time_from_db + (segment_num * 60)
                    self._log(t("✓ Calculated from route start time in database: {0} + ({1} × 60) = {2}").format(route_start_time_from_db, segment_num, timestamp))

                else:
                    # Case 2b: Database doesn't have it either, need to scan entire route
                    self._log(t("No route start time in database, scanning entire route..."))
                    route_parent_dir = os.path.dirname(segment_dir)
                    route_start_time_scanned = self.get_route_start_time(route_parent_dir, route_id)

                    if route_start_time_scanned > 0:
                        # Successfully calculated route start time
                        route_start_time_to_save = route_start_time_scanned
                        timestamp = route_start_time_scanned + (segment_num * 60)
                        self._log(t("✓ Using calculated time: {0} + ({1} × 60) = {2}").format(route_start_time_scanned, segment_num, timestamp))

                    else:
                        # Fallback: Use alternative method
                        self._log(t("⚠ Unable to calculate time from route, using fallback method"))
                        if wall_time_offset > 0:
                            wall_time_s = wall_time_offset / 1e9
                            timestamp = int(wall_time_s)
                            self._log(t("Using wallTimeNanos: {0}").format(timestamp))
                        else:
                            self._log(t("Warning: Using timestamp from directory name (may be inaccurate)"))

            # Time range
            start_time_ns = events[0].logMonoTime if events else 0
            end_time_ns = events[-1].logMonoTime if events else 0
            duration_sec = (end_time_ns - start_time_ns) / 1e9
            self._log(t("Duration: {0:.2f} seconds").format(duration_sec))

            self._progress(30)

            # Insert route (including start_timestamp and dbc_file)
            self._log(t("Inserting Route..."))
            # Get DBC file name (filename only, without path)
            dbc_file_name = os.path.basename(dbc_path) if dbc_path else None
            self.db_manager.insert_route(route_id, dongle_id, timestamp, start_timestamp=route_start_time_to_save, dbc_file=dbc_file_name)

            # Generate video thumbnail
            thumbnail_path = None
            if os.path.exists(fcamera_path):
                thumbnail_filename = f"thumbnail_{segment_num}.jpg"
                thumbnail_path = os.path.join(segment_dir, thumbnail_filename)
                self._log(t("Generating video thumbnail..."))
                if self.generate_thumbnail(fcamera_path, thumbnail_path):
                    self._log(t("✓ Thumbnail generated: {0}").format(thumbnail_filename))
                    thumbnail_path = os.path.abspath(thumbnail_path)
                else:
                    thumbnail_path = None
            elif os.path.exists(ecamera_path):
                thumbnail_filename = f"thumbnail_{segment_num}.jpg"
                thumbnail_path = os.path.join(segment_dir, thumbnail_filename)
                self._log(t("Generating video thumbnail..."))
                if self.generate_thumbnail(ecamera_path, thumbnail_path):
                    self._log(t("✓ Thumbnail generated: {0}").format(thumbnail_filename))
                    thumbnail_path = os.path.abspath(thumbnail_path)
                else:
                    thumbnail_path = None

            # Insert segment
            self._log(t("Inserting Segment..."))
            segment_id = self.db_manager.insert_segment(
                route_id=route_id,
                segment_num=segment_num,
                duration_sec=duration_sec,
                start_time_ns=start_time_ns,
                end_time_ns=end_time_ns,
                total_events=len(events),
                wall_time_offset=wall_time_offset,
                rlog_path=os.path.abspath(rlog_path),
                ecamera_path=os.path.abspath(ecamera_path) if os.path.exists(ecamera_path) else None,
                fcamera_path=os.path.abspath(fcamera_path) if os.path.exists(fcamera_path) else None,
                qcamera_path=os.path.abspath(qcamera_path) if os.path.exists(qcamera_path) else None,
                gps_timestamp=current_gps_timestamp,  # Store segment's own GPS time (if available)
                thumbnail_path=thumbnail_path  # Store thumbnail path
            )

            # Check if segment_id is valid
            if segment_id is None:
                raise Exception("Failed to insert segment: segment_id is None")

            self._log(t("Segment ID: {0}").format(segment_id))

            self._progress(40)

            # Optimize SQLite performance settings
            self._log(t("Optimizing database performance settings..."))
            cursor_perf = self.db_manager.conn.cursor()
            cursor_perf.execute("PRAGMA synchronous = OFF")  # Disable synchronous writes
            cursor_perf.execute("PRAGMA journal_mode = MEMORY")  # Use memory journal
            cursor_perf.execute("PRAGMA temp_store = MEMORY")  # Store temporary data in memory
            cursor_perf.execute("PRAGMA cache_size = -128000")  # 128MB cache
            cursor_perf.close()

            # Process events
            self._log(t("Processing events (Cereal + CAN + Log + Video Timestamps)..."))
            timeseries_batch = []
            can_batch = []
            log_batch = []
            video_timestamps_batch = []  # Video frame timestamps
            catalog_updates = {}  # {signal_name: (signal_type, unit, description)}

            # Statistics dictionaries
            event_type_counts = {}  # {msg_type: count}
            cereal_field_counts = {}  # {msg_type: field_count}
            video_frame_counts = {}  # {camera: frame_count}

            # Load Cereal signal types from signal definitions table
            self._log(t("Loading Cereal signal types from signal definitions table..."))
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                SELECT DISTINCT message_type
                FROM cereal_signal_definitions
                ORDER BY message_type
            """)
            cereal_types_result = cursor.fetchall()
            cursor.close()
            CEREAL_TYPES_TO_EXTRACT = [row[0] for row in cereal_types_result]

            if not CEREAL_TYPES_TO_EXTRACT:
                error_msg = t("Error: Signal definitions table is empty. Please import Cereal signal definitions using \"Tools → Import Signal Definitions\" first")
                self._log(error_msg)
                raise RuntimeError(error_msg)

            self._log(t("✓ Loaded {0} Cereal signal types").format(len(CEREAL_TYPES_TO_EXTRACT)))
            logger.info(f"CEREAL_TYPES_TO_EXTRACT: {CEREAL_TYPES_TO_EXTRACT[:10]}...")
            self._log(t("Starting to process {0:,} events...").format(len(events)))

            for i, event in enumerate(events):
                # Output progress periodically (every 10000 events)
                if i > 0 and i % 10000 == 0:
                    progress = 40 + int((i / len(events)) * 50)
                    self._progress(progress)
                    self._log(t("Processing progress: {0:,}/{1:,} ({2:.1f}%)").format(i, len(events), i/len(events)*100))

                try:
                    msg_type = event.which()
                    log_time_ns = event.logMonoTime

                    # Count event types
                    event_type_counts[msg_type] = event_type_counts.get(msg_type, 0) + 1

                    # Process Cereal signals
                    if msg_type in CEREAL_TYPES_TO_EXTRACT:
                        try:
                            obj = getattr(event, msg_type)
                            # Extract all numeric fields
                            fields = self.extract_all_fields(obj, msg_type)

                            # Record number of extracted fields
                            if msg_type not in cereal_field_counts:
                                cereal_field_counts[msg_type] = 0
                            cereal_field_counts[msg_type] += len(fields)

                            for signal_name, value in fields:
                                timeseries_batch.append((log_time_ns, signal_name, value, None))
                                # Record to catalog
                                if signal_name not in catalog_updates:
                                    catalog_updates[signal_name] = ('cereal', '', f'{msg_type} signal')
                        except Exception as e:
                            logger.warning(f"Failed to extract {msg_type} at event {i}: {e}")

                    # Process CAN signals
                    elif msg_type == 'can':
                        can_msgs = event.can
                        for can_msg in can_msgs:
                            can_id = can_msg.address
                            can_data = bytes(can_msg.dat)
                            can_src = can_msg.src

                            # Store raw CAN data
                            can_batch.append((log_time_ns, can_id, can_data, can_src))

                            # If DBC parser exists, decode CAN signals
                            if self.dbc_parser:
                                try:
                                    decoded = self.dbc_parser.decode_message(can_id, can_data)
                                    if decoded:
                                        for signal_name, signal_value in decoded.items():
                                            # Create full signal name: CAN_0xID_SignalName
                                            full_signal_name = f"CAN_0x{can_id:03X}_{signal_name}"

                                            # Process signal value: support int, float, NamedSignalValue
                                            numeric_value = None
                                            if isinstance(signal_value, (int, float)):
                                                numeric_value = float(signal_value)
                                            elif isinstance(signal_value, NamedSignalValue):
                                                # NamedSignalValue: extract raw numeric value
                                                numeric_value = float(signal_value.value)

                                            # Store to timeseries (only numeric values)
                                            if numeric_value is not None:
                                                timeseries_batch.append((log_time_ns, full_signal_name, numeric_value, None))

                                                # Record to catalog (with Chinese descriptions)
                                                if full_signal_name not in catalog_updates:
                                                    signal_info = self.dbc_parser.get_signal_info(can_id, signal_name)
                                                    if signal_info:
                                                        unit = signal_info.get('unit_cn', signal_info.get('unit', ''))
                                                        desc_cn = signal_info.get('name_cn', signal_name)
                                                        desc = signal_info.get('description_cn', '')
                                                        if desc:
                                                            full_desc = f"{desc_cn} - {desc}"
                                                        else:
                                                            full_desc = desc_cn
                                                        catalog_updates[full_signal_name] = ('can', unit, full_desc)
                                                    else:
                                                        catalog_updates[full_signal_name] = ('can', '', signal_name)
                                except Exception as e:
                                    logger.debug(f"Failed to decode CAN 0x{can_id:03X}: {e}")

                    # Process logMessage
                    elif msg_type == 'logMessage':
                        try:
                            log_text = event.logMessage
                            parsed = self._parse_log_message(segment_id, log_time_ns, 'log', log_text)
                            if parsed:
                                log_batch.append(parsed)
                        except Exception as e:
                            logger.debug(f"Failed to parse logMessage at event {i}: {e}")

                    # Process errorLogMessage
                    elif msg_type == 'errorLogMessage':
                        try:
                            error_text = event.errorLogMessage
                            parsed = self._parse_log_message(segment_id, log_time_ns, 'error', error_text)
                            if parsed:
                                log_batch.append(parsed)
                        except Exception as e:
                            logger.debug(f"Failed to parse errorLogMessage at event {i}: {e}")

                    # Process EncodeIndex (video frame timestamps)
                    elif msg_type in ['roadEncodeIdx', 'qRoadEncodeIdx', 'wideRoadEncodeIdx', 'driverEncodeIdx']:
                        try:
                            encode_idx = getattr(event, msg_type)
                            if hasattr(encode_idx, 'frameId') and hasattr(encode_idx, 'timestampSof'):
                                frame_id = encode_idx.frameId
                                timestamp_sof = encode_idx.timestampSof

                                # Determine camera type
                                camera = None
                                if msg_type == 'roadEncodeIdx':
                                    camera = 'fcamera'  # Both fcamera and ecamera use roadEncodeIdx
                                elif msg_type == 'qRoadEncodeIdx':
                                    camera = 'qcamera'
                                elif msg_type == 'wideRoadEncodeIdx':
                                    camera = 'ecamera'
                                elif msg_type == 'driverEncodeIdx':
                                    camera = 'dcamera'

                                if camera:
                                    video_timestamps_batch.append((segment_id, camera, frame_id, timestamp_sof))
                                    video_frame_counts[camera] = video_frame_counts.get(camera, 0) + 1
                        except Exception as e:
                            logger.debug(f"Failed to parse {msg_type} at event {i}: {e}")

                    # Batch insert (significantly increased batch size for better performance)
                    if len(timeseries_batch) >= 50000:
                        self._log(t("Batch inserting {0:,} timeseries data points...").format(len(timeseries_batch)))
                        self.db_manager.insert_timeseries_batch(segment_id, timeseries_batch)
                        timeseries_batch = []

                    if len(can_batch) >= 50000:
                        self._log(t("Batch inserting {0:,} CAN messages...").format(len(can_batch)))
                        self.db_manager.insert_can_batch(segment_id, can_batch)
                        can_batch = []

                    if len(log_batch) >= 5000:
                        self._log(t("Batch inserting {0:,} log messages...").format(len(log_batch)))
                        self.db_manager.insert_log_messages_batch(log_batch)
                        log_batch = []

                except Exception as e:
                    logger.error(f"Error processing event {i}: {e}")

            # Insert remaining data
            self._log(t("Inserting remaining data..."))
            if timeseries_batch:
                self._log(t("Batch inserting {0:,} timeseries data points...").format(len(timeseries_batch)))
                self.db_manager.insert_timeseries_batch(segment_id, timeseries_batch)
            if can_batch:
                self._log(t("Batch inserting {0:,} CAN messages...").format(len(can_batch)))
                self.db_manager.insert_can_batch(segment_id, can_batch)
            if log_batch:
                self._log(t("Batch inserting {0:,} log messages...").format(len(log_batch)))
                self.db_manager.insert_log_messages_batch(log_batch)
            if video_timestamps_batch:
                self._log(t("Batch inserting {0:,} video frame timestamps...").format(len(video_timestamps_batch)))
                self.db_manager.insert_video_timestamps_batch(video_timestamps_batch)

            # Commit all data at once
            self._log(t("Committing data to database..."))
            self.db_manager.conn.commit()

            # Auto-create missing signal definitions
            self._log(t("Checking and auto-creating missing signal definitions..."))
            created_count = self.db_manager.auto_create_missing_signal_definitions(segment_id)
            if created_count > 0:
                self._log(t("✓ Auto-created {0} new signal definitions").format(created_count))

            self._progress(95)

            # Output statistics
            self._log("=" * 60)
            self._log(t("Event Type Statistics:"))
            for msg_type, count in sorted(event_type_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
                self._log(f"  {msg_type}: {count:,}")

            if cereal_field_counts:
                self._log("=" * 60)
                self._log(t("Cereal Signal Field Extraction Statistics:"))
                for msg_type, field_count in sorted(cereal_field_counts.items()):
                    self._log(f"  {msg_type}: {field_count:,}")
            else:
                self._log("=" * 60)
                self._log(t("Warning: No Cereal signal fields extracted!"))
                self._log(t("Loaded signal types count: {0}").format(len(CEREAL_TYPES_TO_EXTRACT)))
                # Check which types appear in rlog
                found_types = [t for t in CEREAL_TYPES_TO_EXTRACT if t in event_type_counts]
                self._log(t("Signal types found in rlog: {0}/{1}").format(len(found_types), len(CEREAL_TYPES_TO_EXTRACT)))
                if found_types:
                    self._log(t("Found types: {0}").format(', '.join(found_types[:10])))

            if video_frame_counts:
                self._log("=" * 60)
                self._log(t("Video Frame Timestamp Statistics:"))
                for camera, frame_count in sorted(video_frame_counts.items()):
                    self._log(t("  {0}: {1:,} frames").format(camera, frame_count))

            self._log("=" * 60)

            # Note: SQLite version doesn't use signal_catalog table
            # Signal definitions already exist in cereal_signal_definitions and can_signal_definitions tables

            # Update segment's actual time range (query from timeseries_data)
            self._log(t("Updating Segment time range..."))
            try:
                cursor = self.db_manager.conn.cursor()
                cursor.execute("""
                    SELECT MIN(time_ns), MAX(time_ns)
                    FROM timeseries_data
                    WHERE segment_id = ?
                """, (segment_id,))
                row = cursor.fetchone()
                actual_start, actual_end = row if row else (None, None)

                if actual_start and actual_end:
                    actual_duration = (actual_end - actual_start) / 1e9
                    cursor.execute("""
                        UPDATE segments
                        SET start_time_ns = ?,
                            end_time_ns = ?,
                            duration_seconds = ?
                        WHERE segment_id = ?
                    """, (actual_start, actual_end, actual_duration, segment_id))
                    self._log(t("Updated time range: {0:.2f} seconds").format(actual_duration))
                cursor.close()
            except Exception as e:
                logger.warning(f"Failed to update segment time range: {e}")

            self.db_manager.conn.commit()

            # Restore normal database settings
            self._log(t("Restoring database settings..."))
            cursor_restore = self.db_manager.conn.cursor()
            cursor_restore.execute("PRAGMA synchronous = NORMAL")
            cursor_restore.execute("PRAGMA journal_mode = WAL")
            cursor_restore.close()

            self._progress(100)
            self._log(t("Import completed!"))
            self._log(t("Processed {0} signals").format(len(catalog_updates)))
            return True

        except Exception as e:
            self._log(t("Import failed: {0}").format(str(e)))
            logger.error(f"Import failed: {e}", exc_info=True)
            return False
