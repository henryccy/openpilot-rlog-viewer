# -*- coding: utf-8 -*-
"""
Route/Segment Manager Dialog - Integrated management for routes and segments
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QSplitter, QWidget, QFileDialog, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from typing import Optional, Dict, List
from pathlib import Path
import logging
import os

logger = logging.getLogger(__name__)


class RouteManagerDialog(QDialog):
    """
    Route/Segment Manager Dialog

    Features:
    - View all Routes and Segments
    - Import new Segments (multi-select supported)
    - Delete Segments
    - Delete Routes
    - Load Segment to main window
    """

    # Signal: (route_id, segment_id, segment_num)
    segment_loaded = pyqtSignal(str, int, int)

    def __init__(self, db_manager, parent=None, translation_manager=None):
        """
        Args:
            db_manager: DatabaseManager instance
            parent: Parent widget
            translation_manager: TranslationManager instance
        """
        super().__init__(parent)

        self.db_manager = db_manager
        self.translation_manager = translation_manager
        self.selected_route_id = None

        t = self.translation_manager.t if self.translation_manager else lambda x: x

        self.setWindowTitle(t("Route / Segment Manager"))
        self.setMinimumSize(1200, 700)

        self.setup_ui()
        self.load_routes()

    def setup_ui(self):
        """Setup UI"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # ============================================================
        # Main content area: Route table (left) + Segment table (right)
        # ============================================================
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(main_splitter)

        # ============================================================
        # Left side: Route list + Route action buttons
        # ============================================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        route_label = QLabel(t("Route List"))
        route_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        left_layout.addWidget(route_label)

        # Route table
        self.route_table = QTableWidget()
        self.route_table.setColumnCount(5)
        self.route_table.setHorizontalHeaderLabels([
            t("Route ID"), t("Record Time"), t("Segments"), t("DBC"), t("Total Events")
        ])
        self.route_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.route_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.route_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Set highlight color for selected rows
        self.route_table.setStyleSheet("""
            QTableWidget::item:selected {
                background-color: #0078D7;
                color: white;
            }
        """)

        self.route_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.route_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.route_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.route_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.route_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        # Connect selection event
        self.route_table.itemSelectionChanged.connect(self.on_route_selected)

        left_layout.addWidget(self.route_table)

        # Route action buttons
        route_button_layout = QHBoxLayout()

        self.delete_route_btn = QPushButton(t("Delete Route"))
        self.delete_route_btn.setEnabled(False)
        self.delete_route_btn.clicked.connect(self.delete_route)
        route_button_layout.addWidget(self.delete_route_btn)

        route_button_layout.addStretch()

        left_layout.addLayout(route_button_layout)

        main_splitter.addWidget(left_widget)

        # ============================================================
        # Right side: Segment list + Segment action buttons
        # ============================================================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        segment_label = QLabel(t("Segment List"))
        segment_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        right_layout.addWidget(segment_label)

        # Segment table
        self.segment_table = QTableWidget()
        self.segment_table.setColumnCount(5)
        self.segment_table.setHorizontalHeaderLabels([
            t("Segment"), t("Start Time"), "End Time", t("Duration"), t("Events")
        ])
        self.segment_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.segment_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)  # Multi-select enabled
        self.segment_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Set highlight color for selected rows
        self.segment_table.setStyleSheet("""
            QTableWidget::item:selected {
                background-color: #0078D7;
                color: white;
            }
        """)

        self.segment_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.segment_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.segment_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.segment_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.segment_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        # Enable sorting
        self.segment_table.setSortingEnabled(True)

        # Connect selection event
        self.segment_table.itemSelectionChanged.connect(self.on_segment_selected)

        # Double-click Segment to load directly
        self.segment_table.itemDoubleClicked.connect(self.load_segment)

        right_layout.addWidget(self.segment_table)

        # Segment action buttons
        segment_button_layout = QHBoxLayout()

        self.import_segment_btn = QPushButton(t("Import Segment"))
        self.import_segment_btn.setEnabled(True)  # Always enabled, can import new Routes
        self.import_segment_btn.clicked.connect(self.import_segments)
        segment_button_layout.addWidget(self.import_segment_btn)

        self.delete_segment_btn = QPushButton(t("Delete Selected Segments"))
        self.delete_segment_btn.setEnabled(False)
        self.delete_segment_btn.clicked.connect(self.delete_segments)
        segment_button_layout.addWidget(self.delete_segment_btn)

        segment_button_layout.addStretch()

        self.load_segment_btn = QPushButton(t("Load Selected Segment"))
        self.load_segment_btn.setEnabled(False)
        self.load_segment_btn.clicked.connect(self.load_segment)
        segment_button_layout.addWidget(self.load_segment_btn)

        right_layout.addLayout(segment_button_layout)

        main_splitter.addWidget(right_widget)

        # Set splitter ratio (Route 40%, Segment 60%)
        main_splitter.setSizes([480, 720])

        # ============================================================
        # Bottom buttons
        # ============================================================
        bottom_button_layout = QHBoxLayout()
        bottom_button_layout.addStretch()

        refresh_btn = QPushButton(t("Refresh"))
        refresh_btn.clicked.connect(self.refresh_all)
        bottom_button_layout.addWidget(refresh_btn)

        close_btn = QPushButton(t("Close"))
        close_btn.clicked.connect(self.close)
        bottom_button_layout.addWidget(close_btn)

        layout.addLayout(bottom_button_layout)

    def load_routes(self):
        """Load all Routes"""
        try:
            routes = self.db_manager.get_routes_with_time()

            self.route_table.setRowCount(len(routes))

            for i, route in enumerate(routes):
                # Route ID
                self.route_table.setItem(i, 0, QTableWidgetItem(route['route_id']))

                # Record time (SQLite returns string, PostgreSQL returns datetime object)
                record_time_raw = route['record_time']
                if record_time_raw:
                    # If string, use directly; if datetime object, format it
                    if isinstance(record_time_raw, str):
                        record_time = record_time_raw
                    else:
                        record_time = record_time_raw.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    record_time = "N/A"
                self.route_table.setItem(i, 1, QTableWidgetItem(record_time))

                # Segment count
                seg_count = route['total_segments'] if route['total_segments'] else 0
                self.route_table.setItem(i, 2, QTableWidgetItem(str(seg_count)))

                # DBC file
                dbc_file = route['dbc_file'] if route['dbc_file'] else "N/A"
                self.route_table.setItem(i, 3, QTableWidgetItem(dbc_file))

                # Total events
                total_events = route['total_events'] if route['total_events'] else 0
                self.route_table.setItem(i, 4, QTableWidgetItem(f"{total_events:,}"))

            logger.info(f"Loaded {len(routes)} routes")

            # Clear Segment table
            self.segment_table.setRowCount(0)

        except Exception as e:
            logger.error(f"Failed to load routes: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load route list: {e}")

    def refresh_all(self):
        """Refresh Route and Segment lists"""
        # Reload Route list
        self.load_routes()

        # If a Route is selected, reload its Segment list
        if self.selected_route_id:
            self.load_segments(self.selected_route_id)

    def get_available_dbcs(self):
        """Query available DBC files from database"""
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                SELECT DISTINCT dbc_file
                FROM can_signal_definitions
                WHERE dbc_file IS NOT NULL AND dbc_file != ''
                ORDER BY dbc_file
            """)
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Failed to get available DBCs: {e}")
            return []

    def resolve_dbc_path(self, dbc_name: str) -> Optional[str]:
        """
        Resolve DBC file name to actual file path

        Args:
            dbc_name: DBC file name (e.g., 'vw_mqb.dbc')

        Returns:
            Full path to DBC file, or None if file does not exist
        """
        if not dbc_name:
            return None

        # Try to read from data/dbc/ directory
        dbc_path = Path('data/dbc') / dbc_name
        if dbc_path.exists():
            logger.info(f"Found DBC file: {dbc_path}")
            return str(dbc_path)

        logger.warning(f"DBC file not found: {dbc_path}")
        return None

    def on_route_selected(self):
        """Load Segments when Route is selected"""
        selected_rows = self.route_table.selectedIndexes()
        if not selected_rows:
            self.segment_table.setRowCount(0)
            self.delete_route_btn.setEnabled(False)
            # import_segment_btn remains enabled, can import new Routes
            return

        # Get selected Route ID
        row = selected_rows[0].row()
        route_id = self.route_table.item(row, 0).text()
        self.selected_route_id = route_id

        # Enable buttons
        self.delete_route_btn.setEnabled(True)
        # import_segment_btn is already always enabled

        # Load all Segments for this Route
        self.load_segments(route_id)

    def load_segments(self, route_id: str):
        """Load all Segments for specified Route"""
        try:
            segments = self.db_manager.get_segments_with_time(route_id)

            # Temporarily disable sorting to avoid flicker during insertion
            self.segment_table.setSortingEnabled(False)
            self.segment_table.setRowCount(len(segments))

            for i, seg in enumerate(segments):
                # Segment number
                seg_item = QTableWidgetItem(str(seg['segment_num']))
                seg_item.setData(Qt.ItemDataRole.UserRole, seg['segment_id'])  # Store segment_id
                self.segment_table.setItem(i, 0, seg_item)

                # Start time (SQLite returns string, PostgreSQL returns datetime object)
                start_time_raw = seg['start_time']
                if start_time_raw:
                    if isinstance(start_time_raw, str):
                        start_time = start_time_raw
                    else:
                        start_time = start_time_raw.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    start_time = "N/A"
                self.segment_table.setItem(i, 1, QTableWidgetItem(start_time))

                # End time (SQLite returns string, PostgreSQL returns datetime object)
                end_time_raw = seg['end_time']
                if end_time_raw:
                    if isinstance(end_time_raw, str):
                        end_time = end_time_raw
                    else:
                        end_time = end_time_raw.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    end_time = "N/A"
                self.segment_table.setItem(i, 2, QTableWidgetItem(end_time))

                # Duration
                duration = f"{seg['duration_sec']:.1f}"
                self.segment_table.setItem(i, 3, QTableWidgetItem(duration))

                # Event count
                total_events = seg['total_events'] if seg['total_events'] else 0
                self.segment_table.setItem(i, 4, QTableWidgetItem(f"{total_events:,}"))

            # Re-enable sorting and set default sort (ascending by start time)
            self.segment_table.setSortingEnabled(True)
            self.segment_table.sortItems(1, Qt.SortOrder.AscendingOrder)  # Sort by column 1 (start time) ascending

            logger.info(f"Loaded {len(segments)} segments for route {route_id}")

        except Exception as e:
            logger.error(f"Failed to load segments: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load segment list: {e}")

    def on_segment_selected(self):
        """When Segment selection changes"""
        selected_segments = self.segment_table.selectedIndexes()
        if selected_segments:
            self.delete_segment_btn.setEnabled(True)
            # Can only load when one is selected
            selected_rows = set(index.row() for index in selected_segments)
            self.load_segment_btn.setEnabled(len(selected_rows) == 1)
        else:
            self.delete_segment_btn.setEnabled(False)
            self.load_segment_btn.setEnabled(False)

    def import_segments(self):
        """Import Segments (multi-select supported) - Auto-create or use existing Route"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        # Use new Segment selector dialog (shows GPS time)
        from .segment_selector_dialog import SegmentSelectorDialog

        # Get default scan directory
        default_dir = str(Path.cwd() / "raw")

        selector_dialog = SegmentSelectorDialog(self, default_dir=default_dir, db_manager=self.db_manager, translation_manager=self.translation_manager)

        if selector_dialog.exec() == QDialog.DialogCode.Accepted:
            selected_files = selector_dialog.get_selected_segments()

            if not selected_files:
                return

            # Import Segments
            from .import_progress_dialog import ImportProgressDialog
            from src.core.segment_importer import SegmentImporter

            # First analyze all segments, group by route_id
            importer_temp = SegmentImporter(self.db_manager, translation_manager=self.translation_manager)
            route_groups = {}  # {route_id: [segment_paths]}

            for rlog_path in selected_files:
                try:
                    route_id, _, _, _, _ = importer_temp.parse_segment_path(rlog_path)
                    if route_id not in route_groups:
                        route_groups[route_id] = []
                    route_groups[route_id].append(rlog_path)
                except Exception as e:
                    logger.error(f"Failed to parse {rlog_path}: {e}")
                    continue

            # Check which are new routes and which already exist
            new_routes = []
            existing_routes = {}  # {route_id: dbc_file}

            for route_id in route_groups.keys():
                route_info = self.db_manager.get_route(route_id)
                if route_info:
                    # Existing route
                    existing_routes[route_id] = route_info.get('dbc_file', 'vw_mqb.dbc')
                else:
                    # New route
                    new_routes.append(route_id)

            # If there are new routes, let user select DBC from database (mandatory selection)
            new_route_dbc = None
            if new_routes:
                # Query available DBC list from database
                available_dbcs = self.get_available_dbcs()

                if not available_dbcs:
                    # No DBCs imported, prompt user to import first
                    reply = QMessageBox.warning(
                        self,
                        t("DBC Not Found"),
                        t("No imported DBC files found in database.\n\n"
                          "You need to import DBC files first using \"Tools → Import Signal Definitions\".\n\n"
                          "Continue importing Segment without CAN signal parsing?"),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                    # User chose to continue, use None (don't parse CAN)
                    new_route_dbc = None
                else:
                    # Display new Route information
                    msg = f"Detected {len(new_routes)} new Routes:\n"
                    for route_id in new_routes[:5]:  # Only show first 5
                        msg += f"  • {route_id}\n"
                    if len(new_routes) > 5:
                        msg += f"  ... and {len(new_routes) - 5} others\n"
                    msg += "\nPlease select DBC file for these new Routes:"

                    QMessageBox.information(self, "New Routes", msg)

                    # Use QInputDialog to select from list
                    from PyQt6.QtWidgets import QInputDialog
                    dbc_name, ok = QInputDialog.getItem(
                        self,
                        "Select DBC File",
                        "Please select from imported DBCs:",
                        available_dbcs,
                        0,  # Default to first one
                        False  # Not editable
                    )

                    if not ok or not dbc_name:
                        # User cancelled selection, abort import
                        QMessageBox.warning(
                            self,
                            t("Import Cancelled"),
                            t("Must select a DBC file to import new Route's Segments.\nImport cancelled.")
                        )
                        return

                    new_route_dbc = dbc_name
                    logger.info(f"New Route using DBC: {dbc_name}")

            progress_dialog = ImportProgressDialog(self, title=t("Import Segment"), translation_manager=self.translation_manager)
            progress_dialog.set_status(t("Preparing import..."))
            progress_dialog.set_progress(0)

            importer = SegmentImporter(self.db_manager, translation_manager=self.translation_manager)

            # Set callbacks
            importer.set_progress_callback(progress_dialog.set_progress)
            importer.set_log_callback(progress_dialog.append_log)

            # Enable logging capture
            progress_dialog.enable_logging()

            # Show dialog
            progress_dialog.show()
            QApplication.processEvents()  # Ensure dialog shows immediately

            # Show DBC usage info
            if new_routes and new_route_dbc:
                progress_dialog.append_log(t("New Route using DBC: {0}").format(new_route_dbc))
            if existing_routes:
                progress_dialog.append_log(t("Existing Route count: {0}").format(len(existing_routes)))
                for route_id, dbc in list(existing_routes.items())[:3]:
                    progress_dialog.append_log(f"  • {route_id}: {dbc}")

            QApplication.processEvents()

            # Import files
            success_count = 0
            imported_route_ids = set()  # Track imported route_ids

            for i, rlog_path in enumerate(selected_files):
                progress_dialog.set_status(t("Importing {0}/{1}: {2}").format(i+1, len(selected_files), os.path.basename(rlog_path)))
                QApplication.processEvents()

                try:
                    # Parse route_id from path
                    route_id, _, _, _, _ = importer.parse_segment_path(rlog_path)
                    imported_route_ids.add(route_id)

                    # Decide which DBC to use
                    if route_id in existing_routes:
                        # Existing route, use its original DBC
                        dbc_name = existing_routes[route_id]
                    else:
                        # New route, use user-selected DBC (mandatory selection, must have value)
                        dbc_name = new_route_dbc

                    # Resolve DBC name to actual file path
                    dbc_path = None
                    if dbc_name:
                        dbc_path = self.resolve_dbc_path(dbc_name)
                        if not dbc_path:
                            progress_dialog.append_log(t("⚠ Warning: DBC file {0} not found, CAN signals will not be parsed").format(dbc_name))

                    if importer.import_segment(rlog_path, dbc_path=dbc_path):
                        success_count += 1
                except Exception as e:
                    logger.error(f"Failed to import {rlog_path}: {e}")
                    progress_dialog.append_log(t("✗ Import failed: {0} - {1}").format(os.path.basename(rlog_path), str(e)))

            # Complete
            progress_dialog.set_complete(t("Import Completed"))
            progress_dialog.append_log(t("\nImport completed: {0}/{1} successful").format(success_count, len(selected_files)))

            # Disable logging capture
            progress_dialog.disable_logging()

            # Wait for user to close dialog
            progress_dialog.exec()

            # Reload Route list (because new Routes may have been created)
            self.load_routes()

            # Refresh Segment list
            route_to_refresh = None

            # If only imported Segments from one Route, auto-select that Route
            if len(imported_route_ids) == 1:
                imported_route_id = list(imported_route_ids)[0]
                route_to_refresh = imported_route_id
                # Find and select that Route in the table
                for row in range(self.route_table.rowCount()):
                    if self.route_table.item(row, 0).text() == imported_route_id:
                        self.route_table.selectRow(row)
                        break
            elif self.selected_route_id and self.selected_route_id in imported_route_ids:
                # If previously selected Route has newly imported Segments, reload its Segment list
                route_to_refresh = self.selected_route_id

            # In any case, if there's a route to refresh, load its segments
            if route_to_refresh:
                self.load_segments(route_to_refresh)

    def delete_segments(self):
        """Delete selected Segments"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        if not self.selected_route_id:
            return

        # Get selected Segments
        selected_rows = set(index.row() for index in self.segment_table.selectedIndexes())

        if not selected_rows:
            return

        segment_ids = []
        segment_nums = []
        for row in selected_rows:
            seg_id = self.segment_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            seg_num = int(self.segment_table.item(row, 0).text())
            segment_ids.append(seg_id)
            segment_nums.append(seg_num)

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            t("Confirm Delete"),
            t("Are you sure you want to delete the following Segments?\n\n"
              "Route: {0}\n"
              "Segments: {1}\n\n"
              "This cannot be undone!").format(self.selected_route_id, ', '.join(map(str, segment_nums))),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Show progress dialog
            from .import_progress_dialog import ImportProgressDialog

            progress_dialog = ImportProgressDialog(self, title="Delete Segment", translation_manager=self.translation_manager)
            progress_dialog.set_status(f"Preparing to delete {len(segment_ids)} Segments...")
            progress_dialog.set_progress(0)
            progress_dialog.show()
            QApplication.processEvents()  # Ensure dialog shows immediately

            progress_dialog.set_status(f"Deleting {len(segment_ids)} Segments...")
            progress_dialog.set_progress(30)
            QApplication.processEvents()  # Ensure status update shows (before deletion)

            # Delete Segments (this may take some time)
            self.db_manager.delete_segments(segment_ids)

            progress_dialog.set_progress(80)
            progress_dialog.append_log(f"Deleted {len(segment_ids)} Segments")
            QApplication.processEvents()

            # Reload Segment list
            self.load_segments(self.selected_route_id)

            progress_dialog.set_progress(100)
            progress_dialog.set_complete("Delete Complete")
            progress_dialog.append_log(f"✓ Successfully deleted {len(segment_ids)} Segments")

            # Auto-close after 0.5 seconds
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, progress_dialog.accept)

        except Exception as e:
            logger.error(f"Failed to delete segments: {e}")
            QMessageBox.critical(self, "Error", f"Failed to delete Segments: {e}")

    def delete_route(self):
        """Delete selected Route"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        if not self.selected_route_id:
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            t("Confirm Delete"),
            t("Are you sure you want to delete this Route?\n\n"
              "Route ID: {0}\n\n"
              "This will delete all Segments and data for this Route!\n"
              "This cannot be undone!").format(self.selected_route_id),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Show progress dialog
            from .import_progress_dialog import ImportProgressDialog

            progress_dialog = ImportProgressDialog(self, title="Delete Route", translation_manager=self.translation_manager)
            progress_dialog.set_status("Preparing to delete...")
            progress_dialog.set_progress(0)
            progress_dialog.show()
            QApplication.processEvents()  # Ensure dialog shows immediately

            progress_dialog.set_status(f"Deleting Route: {self.selected_route_id}")
            progress_dialog.append_log(f"Preparing to delete Route and all Segments...")
            progress_dialog.set_progress(20)
            QApplication.processEvents()  # Ensure status update shows (before deletion)

            # Delete Route (CASCADE will auto-delete all related Segments, this may take some time)
            route_id_to_delete = self.selected_route_id
            self.db_manager.delete_route(route_id_to_delete)

            progress_dialog.set_progress(80)
            progress_dialog.append_log(f"Deleted Route: {route_id_to_delete}")
            QApplication.processEvents()

            # Reload Route list
            self.selected_route_id = None
            self.load_routes()

            progress_dialog.set_progress(100)
            progress_dialog.set_complete("Delete Complete")
            progress_dialog.append_log(f"✓ Successfully deleted Route and all Segments")

            # Auto-close after 0.5 seconds
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, progress_dialog.accept)

        except Exception as e:
            logger.error(f"Failed to delete route: {e}")
            QMessageBox.critical(self, "Error", f"Failed to delete Route: {e}")

    def load_segment(self):
        """Load selected Segment to main window"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        # Get selected Segment (can only select one)
        selected_rows = set(index.row() for index in self.segment_table.selectedIndexes())

        if len(selected_rows) != 1:
            QMessageBox.warning(self, t("Warning"), t("Please select one Segment to load"))
            return

        row = list(selected_rows)[0]
        segment_id = self.segment_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        segment_num = int(self.segment_table.item(row, 0).text())

        logger.info(f"Loading: Route={self.selected_route_id}, Segment={segment_num}")

        # Emit signal
        self.segment_loaded.emit(
            self.selected_route_id,
            segment_id,
            segment_num
        )

        # Close dialog
        self.accept()
