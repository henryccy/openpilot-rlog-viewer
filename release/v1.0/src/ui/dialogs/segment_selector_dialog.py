# -*- coding: utf-8 -*-
"""
Segment Selector Dialog - Select segments to import
Display actual recording time for each segment
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QFileDialog,
    QLabel, QProgressBar, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap, QImage
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import capnp
import logging
import av  # PyAV for video decoding

logger = logging.getLogger(__name__)

# Load schema
try:
    capnp_log = capnp.load('log.capnp')
except Exception as e:
    logger.error(f"Failed to load log.capnp: {e}")
    capnp_log = None


class SegmentScanner(QThread):
    """Background thread to scan segments and retrieve time information"""
    segment_found = pyqtSignal(dict)  # Found a segment
    scan_finished = pyqtSignal(int)  # Scan finished, parameter is total count

    def __init__(self, root_dir: str, db_manager=None):
        super().__init__()
        self.root_dir = Path(root_dir)
        self.db_manager = db_manager
        self.running = True

    def stop(self):
        """Stop scanning"""
        self.running = False

    def run(self):
        """Scan all segments under root_dir"""
        count = 0

        try:
            # Recursively search for all rlog files
            for rlog_path in self.root_dir.rglob('rlog'):
                if not self.running:
                    break

                # Parse path
                segment_info = self.parse_segment(rlog_path)
                if segment_info:
                    self.segment_found.emit(segment_info)
                    count += 1

        except Exception as e:
            logger.error(f"Error scanning segments: {e}")

        self.scan_finished.emit(count)

    def _get_video_thumbnail(self, segment_dir: Path) -> Optional[QPixmap]:
        """
        Read first frame of video as thumbnail

        Args:
            segment_dir: Segment directory path

        Returns:
            QPixmap thumbnail, None if failed
        """
        try:
            # Try fcamera (front view) first, then ecamera (wide angle)
            video_files = ['fcamera.hevc', 'ecamera.hevc']

            for video_file in video_files:
                video_path = segment_dir / video_file
                if not video_path.exists():
                    continue

                # Use PyAV to read first frame
                try:
                    container = av.open(str(video_path))
                    stream = container.streams.video[0]

                    # Read only first frame
                    for frame in container.decode(stream):
                        # Convert to RGB
                        img = frame.to_ndarray(format='rgb24')
                        height, width, channel = img.shape

                        # Convert to QImage
                        bytes_per_line = 3 * width
                        q_img = QImage(bytes(img.data), width, height, bytes_per_line, QImage.Format.Format_RGB888)

                        # Scale to thumbnail (width 100 px)
                        pixmap = QPixmap.fromImage(q_img)
                        thumbnail = pixmap.scaledToWidth(100, Qt.TransformationMode.SmoothTransformation)

                        container.close()
                        return thumbnail

                    container.close()
                except Exception as e:
                    logger.debug(f"Failed to read {video_file}: {e}")
                    continue

            return None

        except Exception as e:
            logger.debug(f"Error generating thumbnail: {e}")
            return None

    def parse_segment(self, rlog_path: Path) -> Optional[Dict]:
        """Parse segment and get time information"""
        # Basic information - must succeed
        try:
            # Parse directory name: 00000009--f5d34548e1--33
            dir_name = rlog_path.parent.name
            parts = dir_name.split('--')
            if len(parts) != 3:
                logger.warning(f"Invalid directory format: {dir_name}")
                return None

            segment_num = int(parts[2])
            route_hex = parts[1]
            dongle_id = parts[0]

            # Build route_id (format: dongle_id--route_hex, consistent with segment_importer)
            route_id = f"{dongle_id}--{route_hex}"

            # Get file size - critical information
            file_size = 0
            try:
                if rlog_path.exists():
                    file_size = rlog_path.stat().st_size
            except Exception as e:
                logger.error(f"Error getting file size for {rlog_path}: {e}")

        except Exception as e:
            logger.error(f"Error parsing basic segment info {rlog_path}: {e}", exc_info=True)
            return None

        # Optional: Query database first (if already imported)
        gps_time = None
        wall_time = None

        if self.db_manager:
            try:
                # Query route timestamp from database
                cursor = self.db_manager.conn.cursor()
                cursor.execute("""
                    SELECT timestamp
                    FROM routes
                    WHERE route_id = ?
                """, (route_id,))
                result = cursor.fetchone()

                if result and result[0]:
                    # Calculate this segment's time
                    route_start_time = result[0]
                    gps_time = route_start_time + (segment_num * 60)
            except Exception as e:
                logger.debug(f"Failed to query database: {e}")

        # Optional: If not in database, try to get GPS time from rlog
        if not gps_time:
            try:
                with open(rlog_path, 'rb') as f:
                    data = f.read()  # Read entire file (consistent with segment_importer)

                if capnp_log and data:
                    events = list(capnp_log.Event.read_multiple_bytes(data))

                    # Find first liveLocationKalman (scan all events)
                    for event in events:
                        try:
                            if event.which() == 'liveLocationKalman':
                                llk = event.liveLocationKalman
                                if hasattr(llk, 'unixTimestampMillis') and llk.unixTimestampMillis > 0:
                                    # GPS time (milliseconds)
                                    gps_timestamp = int(llk.unixTimestampMillis / 1000)
                                    # Backtrack to route start time (consistent with segment_importer)
                                    gps_time = gps_timestamp - (segment_num * 60)
                                    break
                        except:
                            pass

                    # If no GPS found, use first event's wallTimeNanos
                    if not gps_time and events:
                        first_event = events[0]
                        if hasattr(first_event, 'logMonoTime'):
                            log_time_ns = first_event.logMonoTime

                            # Try to find initData to get wallTimeNanos
                            for event in events[:100]:
                                if event.which() == 'initData':
                                    init_data = event.initData
                                    if hasattr(init_data, 'wallTimeNanos'):
                                        wall_time_ns = init_data.wallTimeNanos
                                        if wall_time_ns > 0:
                                            # Calculate time offset
                                            offset = wall_time_ns - log_time_ns
                                            # Segment first event's wallTime
                                            wall_time = int((log_time_ns + offset) / 1e9)
                                            break

            except Exception as e:
                logger.debug(f"Error reading segment time: {e}")

        # Optional: If neither available, use directory hex
        if not gps_time and not wall_time:
            try:
                wall_time = int(route_hex, 16)
            except:
                pass

        # Optional: Read video first frame as thumbnail
        thumbnail = None
        try:
            thumbnail = self._get_video_thumbnail(rlog_path.parent)
        except Exception as e:
            logger.debug(f"Error getting thumbnail: {e}")

        # Return segment info - guaranteed to have basic fields
        return {
            'path': str(rlog_path),
            'dir_name': dir_name,
            'segment_num': segment_num,
            'route_hex': route_hex,
            'gps_time': gps_time,
            'wall_time': wall_time,
            'file_size': file_size,
            'thumbnail': thumbnail  # QPixmap or None
        }


class SegmentSelectorDialog(QDialog):
    """Segment selector dialog - Display actual recording time"""

    def __init__(self, parent=None, default_dir: str = None, db_manager=None, translation_manager=None):
        super().__init__(parent)
        self.selected_segments: List[str] = []
        self.default_dir = default_dir or str(Path.cwd() / "raw")
        self.db_manager = db_manager
        self.translation_manager = translation_manager
        self.scanner_thread = None

        t = self.translation_manager.t if self.translation_manager else lambda x: x

        self.setWindowTitle(t("Select Segments to Import"))
        self.resize(1000, 600)
        self.setup_ui()

    def setup_ui(self):
        """Setup UI"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        layout = QVBoxLayout(self)

        # Top: Select directory
        top_layout = QHBoxLayout()
        self.dir_label = QLabel(t("Scan Directory:") + f" {self.default_dir}")
        top_layout.addWidget(self.dir_label)

        change_dir_btn = QPushButton(t("Change Directory"))
        change_dir_btn.clicked.connect(self.change_directory)
        top_layout.addWidget(change_dir_btn)

        scan_btn = QPushButton(t("Rescan"))
        scan_btn.clicked.connect(self.start_scan)
        top_layout.addWidget(scan_btn)

        layout.addLayout(top_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Segment list table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            t("Preview"), t("Directory"), t("Segment"), t("GPS Time"),
            t("Wall Time"), t("File Size"), t("Path")
        ])

        # Set table properties
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # Sorting will be enabled after scanning completes
        self.table.setSortingEnabled(False)

        # Set clear selection color
        self.table.setStyleSheet("""
            QTableWidget::item:selected {
                background-color: #0078D7;
                color: white;
            }
        """)

        # Set fixed row height (for thumbnail space)
        self.table.verticalHeader().setDefaultSectionSize(80)

        # Adjust column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # Preview image fixed width
        self.table.setColumnWidth(0, 120)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table)

        # Bottom buttons
        button_layout = QHBoxLayout()

        select_all_btn = QPushButton(t("Select All"))
        select_all_btn.clicked.connect(self.table.selectAll)
        button_layout.addWidget(select_all_btn)

        deselect_all_btn = QPushButton(t("Deselect All"))
        deselect_all_btn.clicked.connect(self.table.clearSelection)
        button_layout.addWidget(deselect_all_btn)

        button_layout.addStretch()

        self.status_label = QLabel(t("Ready to scan..."))
        button_layout.addWidget(self.status_label)

        button_layout.addStretch()

        cancel_btn = QPushButton(t("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton(t("Import Selected Segments"))
        ok_btn.clicked.connect(self.accept_selection)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

        # Auto start scanning
        self.start_scan()

    def change_directory(self):
        """Change scan directory"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        dir_path = QFileDialog.getExistingDirectory(
            self, t("Select Segment Root Directory"), self.default_dir
        )

        if dir_path:
            self.default_dir = dir_path
            self.dir_label.setText(t("Scan Directory:") + f" {dir_path}")
            self.start_scan()

    def start_scan(self):
        """Start scanning segments"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        # Stop previous scan
        if self.scanner_thread and self.scanner_thread.isRunning():
            self.scanner_thread.stop()
            self.scanner_thread.wait()

        # Disable sorting while inserting data to prevent row index mismatch
        self.table.setSortingEnabled(False)

        # Clear table
        self.table.setRowCount(0)
        self.status_label.setText(t("Scanning..."))
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress bar

        # Start new scan
        self.scanner_thread = SegmentScanner(self.default_dir, self.db_manager)
        self.scanner_thread.segment_found.connect(self.add_segment)
        self.scanner_thread.scan_finished.connect(self.scan_finished)
        self.scanner_thread.start()

    def add_segment(self, segment_info: Dict):
        """Add a segment to table"""
        try:
            t = self.translation_manager.t if self.translation_manager else lambda x: x

            row = self.table.rowCount()
            self.table.insertRow(row)

            # Column 0: Preview image
            try:
                thumbnail_item = QTableWidgetItem()
                if segment_info.get('thumbnail'):
                    # If has thumbnail, set as icon
                    thumbnail_item.setData(Qt.ItemDataRole.DecorationRole, segment_info['thumbnail'])
                else:
                    # No thumbnail, display text
                    thumbnail_item.setText(t("No Preview"))
                    thumbnail_item.setForeground(QColor(150, 150, 150))
                thumbnail_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 0, thumbnail_item)
            except Exception as e:
                logger.error(f"Error setting preview for row {row}: {e}")

            # Column 1: Directory name
            try:
                self.table.setItem(row, 1, QTableWidgetItem(segment_info.get('dir_name', '')))
            except Exception as e:
                logger.error(f"Error setting directory for row {row}: {e}")

            # Column 2: Segment number
            try:
                seg_item = QTableWidgetItem(str(segment_info.get('segment_num', '')))
                seg_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 2, seg_item)
            except Exception as e:
                logger.error(f"Error setting segment number for row {row}: {e}")

            # Column 3: GPS time (display this segment's actual start time)
            try:
                if segment_info.get('gps_time'):
                    try:
                        # gps_time is route start time, need to add segment offset
                        segment_start_time = segment_info['gps_time'] + (segment_info['segment_num'] * 60)
                        gps_str = datetime.fromtimestamp(segment_start_time).strftime('%Y-%m-%d %H:%M:%S')
                        gps_item = QTableWidgetItem(gps_str)
                        gps_item.setBackground(QColor(200, 255, 200))  # Light green background
                    except:
                        gps_item = QTableWidgetItem(t("No GPS"))
                        gps_item.setForeground(QColor(150, 150, 150))
                else:
                    gps_item = QTableWidgetItem(t("No GPS"))
                    gps_item.setForeground(QColor(150, 150, 150))
                gps_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 3, gps_item)
            except Exception as e:
                logger.error(f"Error setting GPS time for row {row}: {e}")

            # Column 4: Wall time (only display when no GPS)
            try:
                if segment_info.get('wall_time') and not segment_info.get('gps_time'):
                    try:
                        wall_str = datetime.fromtimestamp(segment_info['wall_time']).strftime('%Y-%m-%d %H:%M:%S')
                        wall_item = QTableWidgetItem(wall_str)
                        wall_item.setBackground(QColor(255, 255, 200))  # Light yellow background
                    except:
                        wall_item = QTableWidgetItem(t("No Time"))
                        wall_item.setForeground(QColor(150, 150, 150))
                else:
                    wall_item = QTableWidgetItem("--")
                    wall_item.setForeground(QColor(200, 200, 200))
                wall_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 4, wall_item)
            except Exception as e:
                logger.error(f"Error setting wall time for row {row}: {e}")

            # Column 5: File size
            try:
                file_size = segment_info.get('file_size', 0)
                size_mb = file_size / (1024 * 1024)
                size_item = QTableWidgetItem(f"{size_mb:.1f} MB")
                size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, 5, size_item)
            except Exception as e:
                logger.error(f"Error setting file size for row {row}: {e}")

            # Column 6: Path
            try:
                path = segment_info.get('path', '')
                self.table.setItem(row, 6, QTableWidgetItem(path))
            except Exception as e:
                logger.error(f"Error setting path for row {row}: {e}")

        except Exception as e:
            logger.error(f"Error adding segment to table: {e}", exc_info=True)

    def scan_finished(self, count: int):
        """Scan finished"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        self.progress_bar.setVisible(False)
        self.status_label.setText(t("Found {0} Segments").format(count))

        # Enable sorting after all data is inserted
        self.table.setSortingEnabled(True)

        # Sort by GPS time (column 3, put non-GPS segments at end)
        self.table.sortItems(3, Qt.SortOrder.DescendingOrder)

    def accept_selection(self):
        """Confirm selection"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        selected_rows = set(item.row() for item in self.table.selectedItems())

        if not selected_rows:
            self.status_label.setText(t("Please select at least one Segment"))
            return

        self.selected_segments = []
        for row in selected_rows:
            path_item = self.table.item(row, 6)  # Fix: Column 6 is path (Column 5 is file size)
            if path_item:
                self.selected_segments.append(path_item.text())

        self.accept()

    def get_selected_segments(self) -> List[str]:
        """Get selected segment path list"""
        return self.selected_segments

    def closeEvent(self, event):
        """Stop scanner thread when closing window"""
        if self.scanner_thread and self.scanner_thread.isRunning():
            self.scanner_thread.stop()
            self.scanner_thread.wait()
        super().closeEvent(event)
