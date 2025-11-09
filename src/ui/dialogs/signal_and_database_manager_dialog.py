# -*- coding: utf-8 -*-
"""
Signal and Database Manager Dialog

Integrated features:
1. Cereal signal translation editing
2. CAN signal translation editing
3. DBC management (view/switch/re-import)
4. Database management (connection/table operations/database operations)
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QLabel,
    QMessageBox, QHeaderView, QGroupBox, QSplitter, QFileDialog,
    QTextEdit, QScrollArea, QCheckBox
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QFont
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class SignalAndDatabaseManagerDialog(QDialog):
    """Signal and Database Manager Dialog"""

    def __init__(self, db_manager, parent=None, translation_manager=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.translation_manager = translation_manager
        self.test_connection = None  # Temporary connection for testing

        # Load settings: whether to show DEPRECATED signals
        settings = QSettings('OpenpilotLogViewer', 'SignalTranslationEditor')
        self.show_deprecated = settings.value('show_deprecated', False, type=bool)

        t = self.translation_manager.t if self.translation_manager else lambda x: x

        self.setWindowTitle(t("Signal && Database Manager"))
        self.setGeometry(50, 50, 1400, 900)

        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        """Setup user interface"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        layout = QVBoxLayout()

        # Tab widget
        self.tab_widget = QTabWidget()

        # Tab 1: Cereal signal translation
        self.setup_cereal_tab()

        # Tab 2: CAN signal translation
        self.setup_can_tab()

        # Tab 3: Cereal signal management - Removed (duplicate functionality, use "Tools → Import Signal Definitions")
        # self.setup_cereal_management_tab()

        # Tab 4: DBC management - Removed (duplicate functionality, use "Tools → Import Signal Definitions")
        # self.setup_dbc_tab()

        # Tab 3 (formerly Tab 5): Database management
        self.setup_database_tab()

        layout.addWidget(self.tab_widget)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton(t("Close"))
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    # ========================================================================
    # Tab 1: Cereal Signal Translation
    # ========================================================================
    def setup_cereal_tab(self):
        """Setup Cereal signal translation tab"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        cereal_widget = QWidget()
        cereal_layout = QVBoxLayout()

        # Search box and options
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel(t("Search:")))
        self.cereal_search_edit = QLineEdit()
        self.cereal_search_edit.setPlaceholderText(t("Enter signal name, message type, unit or translation..."))
        self.cereal_search_edit.textChanged.connect(self.filter_cereal_table)
        search_layout.addWidget(self.cereal_search_edit)

        # DEPRECATED display option
        self.cereal_show_deprecated_checkbox = QCheckBox(t("Show DEPRECATED signals"))
        self.cereal_show_deprecated_checkbox.setChecked(self.show_deprecated)
        self.cereal_show_deprecated_checkbox.toggled.connect(self.on_cereal_show_deprecated_toggled)

        # Set style: theme-adaptive checkbox (visible in both light and dark themes)
        self.cereal_show_deprecated_checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked {
                background-color: transparent;
                border: 2px solid #666666;
            }
            QCheckBox::indicator:unchecked:hover {
                border: 2px solid #4CAF50;
                background-color: rgba(76, 175, 80, 0.1);
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border: 2px solid #4CAF50;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #66BB6A;
                border: 2px solid #66BB6A;
            }
        """)

        search_layout.addWidget(self.cereal_show_deprecated_checkbox)

        cereal_layout.addLayout(search_layout)

        # Table
        self.cereal_table = QTableWidget()
        self.cereal_table.setColumnCount(6)
        self.cereal_table.setHorizontalHeaderLabels([
            t("Message Type"), t("Full Name"), t("Data Type"), t("Unit (EN)"), t("Unit (CN)"), t("Chinese Translation")
        ])
        self.cereal_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.cereal_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.cereal_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.cereal_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.cereal_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.cereal_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.cereal_table.setAlternatingRowColors(True)
        cereal_layout.addWidget(self.cereal_table)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cereal_save_btn = QPushButton(t("Save Translations"))
        self.cereal_save_btn.clicked.connect(self.save_cereal_translations)
        btn_layout.addWidget(self.cereal_save_btn)
        cereal_layout.addLayout(btn_layout)

        cereal_widget.setLayout(cereal_layout)
        self.tab_widget.addTab(cereal_widget, t("Cereal Signal Translation"))

    # ========================================================================
    # Tab 2: CAN Signal Translation
    # ========================================================================
    def setup_can_tab(self):
        """Setup CAN signal translation tab"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        can_widget = QWidget()
        can_layout = QVBoxLayout()

        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel(t("Search:")))
        self.can_search_edit = QLineEdit()
        self.can_search_edit.setPlaceholderText(t("Enter signal name, CAN ID, unit or translation..."))
        self.can_search_edit.textChanged.connect(self.filter_can_table)
        search_layout.addWidget(self.can_search_edit)
        can_layout.addLayout(search_layout)

        # Table
        self.can_table = QTableWidget()
        self.can_table.setColumnCount(7)
        self.can_table.setHorizontalHeaderLabels([
            t("Bus ID"), t("Message Name"), t("Full Name"), t("Signal Name"), t("Unit (EN)"), t("Unit (CN)"), t("Chinese Translation")
        ])
        self.can_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.can_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.can_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.can_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.can_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.can_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.can_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.can_table.setAlternatingRowColors(True)
        can_layout.addWidget(self.can_table)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.can_save_btn = QPushButton(t("Save Translations"))
        self.can_save_btn.clicked.connect(self.save_can_translations)
        btn_layout.addWidget(self.can_save_btn)
        can_layout.addLayout(btn_layout)

        can_widget.setLayout(can_layout)
        self.tab_widget.addTab(can_widget, t("CAN Signal Translation"))

    # ========================================================================
    # Tab 3: Cereal Signal Management
    # ========================================================================
    def setup_cereal_management_tab(self):
        """Setup Cereal signal management tab"""
        cereal_mgmt_widget = QWidget()
        cereal_mgmt_layout = QVBoxLayout()

        # Current Cereal signal info
        info_group = QGroupBox("Current Cereal Signal Info")
        info_layout = QGridLayout()

        info_layout.addWidget(QLabel("log.capnp Path:"), 0, 0)
        self.capnp_log_path_label = QLabel("Not set")
        self.capnp_log_path_label.setStyleSheet("padding: 5px; background-color: #f0f0f0; border-radius: 3px;")
        info_layout.addWidget(self.capnp_log_path_label, 0, 1, 1, 2)

        info_layout.addWidget(QLabel("car.capnp Path:"), 1, 0)
        self.capnp_car_path_label = QLabel("Not set")
        self.capnp_car_path_label.setStyleSheet("padding: 5px; background-color: #f0f0f0; border-radius: 3px;")
        info_layout.addWidget(self.capnp_car_path_label, 1, 1, 1, 2)

        info_layout.addWidget(QLabel("Message Types:"), 2, 0)
        self.cereal_message_count_label = QLabel("-")
        info_layout.addWidget(self.cereal_message_count_label, 2, 1)

        info_layout.addWidget(QLabel("Signal Count:"), 3, 0)
        self.cereal_signal_count_label = QLabel("-")
        info_layout.addWidget(self.cereal_signal_count_label, 3, 1)

        info_group.setLayout(info_layout)
        cereal_mgmt_layout.addWidget(info_group)

        # Cereal signal operations
        ops_group = QGroupBox("Cereal Signal Operations")
        ops_layout = QVBoxLayout()

        # Select capnp directory
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("capnp File Directory:"))
        self.capnp_dir_edit = QLineEdit()
        self.capnp_dir_edit.setPlaceholderText("Click 'Browse' to select directory containing log.capnp and car.capnp...")
        self.capnp_dir_edit.setReadOnly(True)
        select_layout.addWidget(self.capnp_dir_edit)

        browse_capnp_btn = QPushButton("Browse...")
        browse_capnp_btn.clicked.connect(self.browse_capnp_directory)
        select_layout.addWidget(browse_capnp_btn)
        ops_layout.addLayout(select_layout)

        # Import button
        import_btn_layout = QHBoxLayout()
        import_btn_layout.addStretch()

        self.reimport_cereal_btn = QPushButton("Re-import Cereal Signal Definitions")
        self.reimport_cereal_btn.setToolTip("Will delete existing Cereal signal definitions and re-import from log.capnp")
        self.reimport_cereal_btn.clicked.connect(self.reimport_cereal_signals)
        import_btn_layout.addWidget(self.reimport_cereal_btn)

        ops_layout.addLayout(import_btn_layout)

        ops_group.setLayout(ops_layout)
        cereal_mgmt_layout.addWidget(ops_group)

        # Status display
        status_group = QGroupBox("Operation Log")
        status_layout = QVBoxLayout()

        self.cereal_status_text = QTextEdit()
        self.cereal_status_text.setReadOnly(True)
        self.cereal_status_text.setMaximumHeight(250)
        status_layout.addWidget(self.cereal_status_text)

        status_group.setLayout(status_layout)
        cereal_mgmt_layout.addWidget(status_group)

        cereal_mgmt_layout.addStretch()
        cereal_mgmt_widget.setLayout(cereal_mgmt_layout)
        self.tab_widget.addTab(cereal_mgmt_widget, "Cereal Signal Management")

    # ========================================================================
    # Tab 4: DBC Management
    # ========================================================================
    def setup_dbc_tab(self):
        """Setup DBC management tab"""
        dbc_widget = QWidget()
        dbc_layout = QVBoxLayout()

        # Current DBC file info
        info_group = QGroupBox("Current DBC File Info")
        info_layout = QGridLayout()

        info_layout.addWidget(QLabel("DBC File Path:"), 0, 0)
        self.dbc_path_label = QLabel("Not set")
        self.dbc_path_label.setStyleSheet("padding: 5px; background-color: #f0f0f0; border-radius: 3px;")
        info_layout.addWidget(self.dbc_path_label, 0, 1, 1, 2)

        info_layout.addWidget(QLabel("Message Count:"), 1, 0)
        self.dbc_message_count_label = QLabel("-")
        info_layout.addWidget(self.dbc_message_count_label, 1, 1)

        info_layout.addWidget(QLabel("Signal Count:"), 2, 0)
        self.dbc_signal_count_label = QLabel("-")
        info_layout.addWidget(self.dbc_signal_count_label, 2, 1)

        info_group.setLayout(info_layout)
        dbc_layout.addWidget(info_group)

        # DBC file operations
        ops_group = QGroupBox("DBC File Operations")
        ops_layout = QVBoxLayout()

        # Select DBC file
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("Select DBC File:"))
        self.dbc_file_edit = QLineEdit()
        self.dbc_file_edit.setPlaceholderText("Click 'Browse' to select DBC file...")
        self.dbc_file_edit.setReadOnly(True)
        select_layout.addWidget(self.dbc_file_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_dbc_file)
        select_layout.addWidget(browse_btn)
        ops_layout.addLayout(select_layout)

        # Import button
        import_btn_layout = QHBoxLayout()
        import_btn_layout.addStretch()

        self.reimport_dbc_btn = QPushButton("Re-import DBC Signal Definitions")
        self.reimport_dbc_btn.setToolTip("Will delete existing CAN signal definitions and re-import from selected DBC file")
        self.reimport_dbc_btn.clicked.connect(self.reimport_dbc_signals)
        import_btn_layout.addWidget(self.reimport_dbc_btn)

        ops_layout.addLayout(import_btn_layout)

        ops_group.setLayout(ops_layout)
        dbc_layout.addWidget(ops_group)

        # Status display
        status_group = QGroupBox("Operation Log")
        status_layout = QVBoxLayout()

        self.dbc_status_text = QTextEdit()
        self.dbc_status_text.setReadOnly(True)
        self.dbc_status_text.setMaximumHeight(200)
        status_layout.addWidget(self.dbc_status_text)

        status_group.setLayout(status_layout)
        dbc_layout.addWidget(status_group)

        dbc_layout.addStretch()
        dbc_widget.setLayout(dbc_layout)
        self.tab_widget.addTab(dbc_widget, "DBC Management")

    # ========================================================================
    # Tab 3: Database Management
    # ========================================================================
    def setup_database_tab(self):
        """Setup database management tab (SQLite version)"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        db_widget = QWidget()
        db_layout = QVBoxLayout()

        # Use splitter to separate top and bottom sections
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Top section: Database information
        top_widget = QGroupBox(t("Database Info"))
        top_layout = QVBoxLayout()

        # Database file information
        info_layout = QGridLayout()

        info_layout.addWidget(QLabel(t("Database Path:")), 0, 0)
        self.db_path_label = QLabel("N/A")
        self.db_path_label.setStyleSheet("color: #666;")
        info_layout.addWidget(self.db_path_label, 0, 1)

        info_layout.addWidget(QLabel(t("Database Size:")), 1, 0)
        self.db_size_label = QLabel("N/A")
        self.db_size_label.setStyleSheet("color: #666;")
        info_layout.addWidget(self.db_size_label, 1, 1)

        info_layout.addWidget(QLabel(t("Table Count:")), 2, 0)
        self.table_count_label = QLabel("N/A")
        self.table_count_label.setStyleSheet("color: #666;")
        info_layout.addWidget(self.table_count_label, 2, 1)

        top_layout.addLayout(info_layout)

        # Database operation buttons
        db_ops_layout = QHBoxLayout()

        self.refresh_db_info_btn = QPushButton(t("Refresh"))
        self.refresh_db_info_btn.clicked.connect(self.refresh_database_info)
        db_ops_layout.addWidget(self.refresh_db_info_btn)

        self.vacuum_btn = QPushButton(t("Vacuum Database"))
        self.vacuum_btn.clicked.connect(self.vacuum_database)
        db_ops_layout.addWidget(self.vacuum_btn)

        db_ops_layout.addStretch()
        top_layout.addLayout(db_ops_layout)

        top_widget.setLayout(top_layout)

        # Bottom section: Table list and operations
        bottom_widget = QGroupBox(t("Table Statistics"))
        bottom_layout = QVBoxLayout()

        # Refresh button
        refresh_layout = QHBoxLayout()
        refresh_layout.addStretch()
        self.refresh_btn = QPushButton(t("Refresh"))
        self.refresh_btn.clicked.connect(self.refresh_table_list)
        refresh_layout.addWidget(self.refresh_btn)
        bottom_layout.addLayout(refresh_layout)

        # Table list
        self.table_list = QTableWidget()
        self.table_list.setColumnCount(2)
        self.table_list.setHorizontalHeaderLabels(["Table Name", "Record Count"])
        self.table_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_list.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_list.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_list.setAlternatingRowColors(True)
        bottom_layout.addWidget(self.table_list)

        # Table operation buttons
        table_ops_layout = QHBoxLayout()

        self.view_table_btn = QPushButton("View Table Contents")
        self.view_table_btn.clicked.connect(self.view_table_data)
        table_ops_layout.addWidget(self.view_table_btn)

        self.truncate_table_btn = QPushButton("Clear Table...")
        self.truncate_table_btn.setStyleSheet("QPushButton { background-color: #ffc107; }")
        self.truncate_table_btn.clicked.connect(self.truncate_table)
        table_ops_layout.addWidget(self.truncate_table_btn)

        table_ops_layout.addStretch()
        bottom_layout.addLayout(table_ops_layout)

        bottom_widget.setLayout(bottom_layout)

        # Add to splitter
        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        db_layout.addWidget(splitter)
        db_widget.setLayout(db_layout)
        self.tab_widget.addTab(db_widget, t("Database Management"))

    # ========================================================================
    # Data Loading
    # ========================================================================
    def load_data(self):
        """Load data"""
        # Load signal translation data
        self.load_cereal_signals()
        self.load_can_signals()

        # Don't load Cereal/DBC management data (tabs removed)
        # self.load_cereal_info()     # Removed
        # self.load_dbc_info()        # Removed

        # Load database information (SQLite version)
        if self.db_manager and self.db_manager.conn:
            self.refresh_database_info()
            self.refresh_table_list()

    def on_cereal_show_deprecated_toggled(self, checked: bool):
        """Show/hide DEPRECATED signals"""
        self.show_deprecated = checked

        # Save settings
        settings = QSettings('OpenpilotLogViewer', 'SignalTranslationEditor')
        settings.setValue('show_deprecated', checked)

        # Reload signals
        self.load_cereal_signals()

    def load_cereal_signals(self):
        """Load Cereal signals"""
        if not self.db_manager or not self.db_manager.conn:
            return

        try:
            cursor = self.db_manager.conn.cursor()

            # Filter DEPRECATED signals based on option
            if self.show_deprecated:
                cursor.execute("""
                    SELECT signal_id, message_type, full_name, data_type, unit, unit_cn, name_cn
                    FROM cereal_signal_definitions
                    ORDER BY message_type, full_name
                """)
            else:
                cursor.execute("""
                    SELECT signal_id, message_type, full_name, data_type, unit, unit_cn, name_cn
                    FROM cereal_signal_definitions
                    WHERE full_name NOT LIKE '%DEPRECATED%'
                    ORDER BY message_type, full_name
                """)

            rows = cursor.fetchall()
            self.cereal_table.setRowCount(len(rows))

            for row_idx, row_data in enumerate(rows):
                signal_id, message_type, full_name, data_type, unit, unit_cn, name_cn = row_data

                # Store ID
                id_item = QTableWidgetItem(message_type or '')
                id_item.setData(Qt.ItemDataRole.UserRole, signal_id)
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.cereal_table.setItem(row_idx, 0, id_item)

                # Full signal name
                name_item = QTableWidgetItem(full_name or '')
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.cereal_table.setItem(row_idx, 1, name_item)

                # Data type
                type_item = QTableWidgetItem(data_type or '')
                type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.cereal_table.setItem(row_idx, 2, type_item)

                # Unit (editable)
                self.cereal_table.setItem(row_idx, 3, QTableWidgetItem(unit or ''))

                # Chinese unit (editable)
                self.cereal_table.setItem(row_idx, 4, QTableWidgetItem(unit_cn or ''))

                # Chinese name (editable)
                self.cereal_table.setItem(row_idx, 5, QTableWidgetItem(name_cn or ''))

            logger.info(f"Loaded {len(rows)} Cereal signals")

        except Exception as e:
            logger.error(f"Failed to load Cereal signals: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load Cereal signals: {e}")

    def load_can_signals(self):
        """Load CAN signals"""
        if not self.db_manager or not self.db_manager.conn:
            return

        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                SELECT signal_id, can_id, message_name_cn, full_name, signal_name, unit, unit_cn, signal_name_cn
                FROM can_signal_definitions
                ORDER BY can_id, full_name
            """)

            rows = cursor.fetchall()
            self.can_table.setRowCount(len(rows))

            for row_idx, row_data in enumerate(rows):
                signal_id, can_id, message_name_cn, full_name, signal_name, unit, unit_cn, signal_name_cn = row_data

                # CAN ID
                id_item = QTableWidgetItem(f"0x{can_id:03X}" if can_id is not None else '')
                id_item.setData(Qt.ItemDataRole.UserRole, signal_id)
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.can_table.setItem(row_idx, 0, id_item)

                # Message name
                msg_item = QTableWidgetItem(message_name_cn or '')
                msg_item.setFlags(msg_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.can_table.setItem(row_idx, 1, msg_item)

                # Full signal name
                full_name_item = QTableWidgetItem(full_name or '')
                full_name_item.setFlags(full_name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.can_table.setItem(row_idx, 2, full_name_item)

                # Signal name
                sig_name_item = QTableWidgetItem(signal_name or '')
                sig_name_item.setFlags(sig_name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.can_table.setItem(row_idx, 3, sig_name_item)

                # Unit (editable)
                self.can_table.setItem(row_idx, 4, QTableWidgetItem(unit or ''))

                # Chinese unit (editable)
                self.can_table.setItem(row_idx, 5, QTableWidgetItem(unit_cn or ''))

                # Chinese name (editable)
                self.can_table.setItem(row_idx, 6, QTableWidgetItem(signal_name_cn or ''))

            logger.info(f"Loaded {len(rows)} CAN signals")

        except Exception as e:
            logger.error(f"Failed to load CAN signals: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load CAN signals: {e}")

    def load_cereal_info(self):
        """Load Cereal signal information"""
        if not self.db_manager:
            return

        try:
            # Query capnp file paths
            log_capnp_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'log.capnp')
            car_capnp_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'car.capnp')

            if os.path.exists(log_capnp_path):
                self.capnp_log_path_label.setText(log_capnp_path)
                self.capnp_dir_edit.setText(os.path.dirname(log_capnp_path))
            else:
                self.capnp_log_path_label.setText("Cannot find log.capnp file")

            if os.path.exists(car_capnp_path):
                self.capnp_car_path_label.setText(car_capnp_path)
            else:
                self.capnp_car_path_label.setText("Cannot find car.capnp file")

            # Query signal statistics
            cursor = self.db_manager.cursor
            cursor.execute("SELECT COUNT(DISTINCT message_type) FROM cereal_signal_definitions")
            message_count = cursor.fetchone()[0] or 0
            self.cereal_message_count_label.setText(f"{message_count}")

            cursor.execute("SELECT COUNT(*) FROM cereal_signal_definitions")
            signal_count = cursor.fetchone()[0] or 0
            self.cereal_signal_count_label.setText(f"{signal_count}")

        except Exception as e:
            logger.error(f"Failed to load Cereal info: {e}")

    def load_dbc_info(self):
        """Load DBC information"""
        if not self.db_manager:
            return

        try:
            # Query DBC path (from config or database)
            dbc_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'vw_mqb.dbc')
            if os.path.exists(dbc_path):
                self.dbc_path_label.setText(dbc_path)
                self.dbc_file_edit.setText(dbc_path)
            else:
                self.dbc_path_label.setText("Cannot find default DBC file")

            # Query signal statistics
            cursor = self.db_manager.cursor
            cursor.execute("SELECT COUNT(DISTINCT can_id) FROM can_signal_definitions")
            message_count = cursor.fetchone()[0] or 0
            self.dbc_message_count_label.setText(f"{message_count}")

            cursor.execute("SELECT COUNT(*) FROM can_signal_definitions")
            signal_count = cursor.fetchone()[0] or 0
            self.dbc_signal_count_label.setText(f"{signal_count}")

        except Exception as e:
            logger.error(f"Failed to load DBC info: {e}")

    def load_current_config(self):
        """Load current database configuration (SQLite version - display database info)"""
        # SQLiteManager doesn't need config, directly display database info
        if self.db_manager and self.db_manager.conn:
            self.refresh_database_info()
            self.refresh_table_list()

    # ========================================================================
    # Filter Functionality
    # ========================================================================
    def filter_cereal_table(self, text: str):
        """Filter Cereal table"""
        text = text.lower()
        for row in range(self.cereal_table.rowCount()):
            show = False
            for col in range(self.cereal_table.columnCount()):
                item = self.cereal_table.item(row, col)
                if item and text in item.text().lower():
                    show = True
                    break
            self.cereal_table.setRowHidden(row, not show)

    def filter_can_table(self, text: str):
        """Filter CAN table"""
        text = text.lower()
        for row in range(self.can_table.rowCount()):
            show = False
            for col in range(self.can_table.columnCount()):
                item = self.can_table.item(row, col)
                if item and text in item.text().lower():
                    show = True
                    break
            self.can_table.setRowHidden(row, not show)

    # ========================================================================
    # Save Translations
    # ========================================================================
    def save_cereal_translations(self):
        """Save Cereal translations"""
        if not self.db_manager or not self.db_manager.conn:
            return

        try:
            cursor = self.db_manager.conn.cursor()
            update_count = 0

            for row in range(self.cereal_table.rowCount()):
                signal_id = self.cereal_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                unit = self.cereal_table.item(row, 3).text().strip()
                unit_cn = self.cereal_table.item(row, 4).text().strip()
                name_cn = self.cereal_table.item(row, 5).text().strip()

                cursor.execute("""
                    UPDATE cereal_signal_definitions
                    SET unit = ?, unit_cn = ?, name_cn = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE signal_id = ?
                """, (unit if unit else None,
                      unit_cn if unit_cn else None,
                      name_cn if name_cn else None,
                      signal_id))

                # SQLite rowcount may be -1 after UPDATE, count directly
                update_count += 1

            self.db_manager.conn.commit()

            QMessageBox.information(
                self,
                "Save Success",
                f"Updated {update_count} Cereal signal translations and units"
            )
            logger.info(f"Updated {update_count} Cereal signal translations")

        except Exception as e:
            self.db_manager.conn.rollback()
            logger.error(f"Failed to save Cereal translations: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def save_can_translations(self):
        """Save CAN translations"""
        if not self.db_manager or not self.db_manager.conn:
            return

        try:
            cursor = self.db_manager.conn.cursor()
            update_count = 0

            for row in range(self.can_table.rowCount()):
                signal_id = self.can_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                unit = self.can_table.item(row, 4).text().strip()
                unit_cn = self.can_table.item(row, 5).text().strip()
                signal_name_cn = self.can_table.item(row, 6).text().strip()

                cursor.execute("""
                    UPDATE can_signal_definitions
                    SET unit = ?, unit_cn = ?, signal_name_cn = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE signal_id = ?
                """, (unit if unit else None,
                      unit_cn if unit_cn else None,
                      signal_name_cn if signal_name_cn else None,
                      signal_id))

                # SQLite rowcount may be -1 after UPDATE, count directly
                update_count += 1

            self.db_manager.conn.commit()

            QMessageBox.information(
                self,
                "Save Success",
                f"Updated {update_count} CAN signal translations and units"
            )
            logger.info(f"Updated {update_count} CAN signal translations")

        except Exception as e:
            self.db_manager.conn.rollback()
            logger.error(f"Failed to save CAN translations: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    # ========================================================================
    # Cereal Signal Management Functions
    # ========================================================================
    def browse_capnp_directory(self):
        """Browse capnp file directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select directory containing log.capnp and car.capnp",
            ""
        )

        if dir_path:
            log_capnp = os.path.join(dir_path, 'log.capnp')
            car_capnp = os.path.join(dir_path, 'car.capnp')

            # Check if files exist
            if not os.path.exists(log_capnp):
                QMessageBox.warning(self, "File Not Found", "Cannot find log.capnp file in selected directory")
                return

            if not os.path.exists(car_capnp):
                QMessageBox.warning(self, "File Not Found", "Cannot find car.capnp file in selected directory")
                return

            # Update UI
            self.capnp_dir_edit.setText(dir_path)
            self.capnp_log_path_label.setText(log_capnp)
            self.capnp_car_path_label.setText(car_capnp)
            self.cereal_status_text.append(f"Selected directory: {dir_path}")
            self.cereal_status_text.append(f"✓ log.capnp: {log_capnp}")
            self.cereal_status_text.append(f"✓ car.capnp: {car_capnp}")

    def reimport_cereal_signals(self):
        """Re-import Cereal signal definitions"""
        if not self.db_manager:
            QMessageBox.warning(self, "Not Connected", "Please connect to database first")
            return

        capnp_dir = self.capnp_dir_edit.text().strip()
        if not capnp_dir or not os.path.exists(capnp_dir):
            QMessageBox.warning(self, "Directory Error", "Please select a valid capnp file directory first")
            return

        log_capnp_path = os.path.join(capnp_dir, 'log.capnp')
        car_capnp_path = os.path.join(capnp_dir, 'car.capnp')

        if not os.path.exists(log_capnp_path) or not os.path.exists(car_capnp_path):
            QMessageBox.warning(self, "File Not Found", "log.capnp or car.capnp file does not exist")
            return

        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            "Confirm Re-import",
            "This operation will delete all existing Cereal signal definitions and re-import them.\n\n"
            "Note: Translations and unit settings will be preserved (if signal names match).\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.cereal_status_text.clear()
            self.cereal_status_text.append("Starting to import Cereal signal definitions...")

            # Use import_signal_definitions logic
            import sys
            import capnp

            # Load capnp files
            self.cereal_status_text.append(f"Loading {log_capnp_path}...")
            old_dir = os.getcwd()
            os.chdir(capnp_dir)  # Change to capnp directory to load dependent files correctly

            try:
                capnp_log = capnp.load('log.capnp')
                car_capnp = capnp.load('car.capnp')
                self.cereal_status_text.append("✓ Successfully loaded capnp files")
            finally:
                os.chdir(old_dir)  # Restore original directory

            # Delete old definitions
            cursor = self.db_manager.cursor
            cursor.execute("DELETE FROM cereal_signal_definitions")
            self.db_manager.conn.commit()
            self.cereal_status_text.append("✓ Cleared old Cereal signal definitions")

            # Get all signal types from Event union
            event_schema = capnp_log.Event.schema
            union_fields = event_schema.union_fields

            self.cereal_status_text.append(f"Found {len(union_fields)} message types")

            # Import unit definitions
            try:
                # 支援 PyInstaller 打包環境
                if getattr(sys, 'frozen', False):
                    # 如果是 PyInstaller 打包的執行檔
                    tools_path = os.path.join(sys._MEIPASS, 'tools')
                else:
                    # 開發環境
                    tools_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'tools')

                sys.path.insert(0, tools_path)
                from extract_cereal_units import CEREAL_SIGNAL_UNITS, UNIT_CN_MAP
            except Exception as e:
                CEREAL_SIGNAL_UNITS = {}
                UNIT_CN_MAP = {}
                self.cereal_status_text.append(f"⚠ Cannot load unit definition file: {e}")

            # Define basic translations
            cereal_translations = {
                'vEgo': 'Vehicle Speed', 'aEgo': 'Acceleration', 'steeringAngleDeg': 'Steering Angle',
                'steeringTorque': 'Steering Torque', 'gas': 'Throttle', 'brake': 'Brake Pressure',
                'enabled': 'Enabled', 'active': 'Active', 'curvature': 'Curvature',
            }

            cereal_categories = {
                'carState': 'vehicle_state', 'carControl': 'control',
                'controlsState': 'control', 'liveParameters': 'control',
                'radarState': 'sensor', 'model': 'model', 'modelV2': 'model',
            }

            imported_count = 0

            # Iterate through all signal types
            for msg_type in union_fields:
                # Skip unwanted types
                if 'DEPRECATED' in msg_type or msg_type in ['initData', 'can', 'sendcan', 'logMessage', 'androidLog']:
                    continue

                try:
                    # Get signal type schema
                    msg_schema = None
                    msg_class_name = msg_type[0].upper() + msg_type[1:]

                    try:
                        msg_class = getattr(capnp_log, msg_class_name)
                        msg_schema = msg_class.schema
                    except:
                        try:
                            msg_class = getattr(car_capnp, msg_class_name)
                            msg_schema = msg_class.schema
                        except:
                            continue

                    if msg_schema is None:
                        continue

                    # Get all fields
                    fields = msg_schema.non_union_fields
                    category = cereal_categories.get(msg_type, 'sensor')

                    # Process each field
                    for field_name in fields:
                        if 'DEPRECATED' in field_name:
                            continue

                        full_signal_name = f"{msg_type}.{field_name}"
                        name_cn = cereal_translations.get(field_name, '')

                        # Get data type
                        data_type = 'Unknown'
                        is_numeric = False
                        try:
                            field_proto = msg_schema.fields[field_name].proto
                            type_enum = field_proto.slot.type.which()

                            type_map = {
                                'bool': ('Bool', False), 'int8': ('Int8', True), 'int16': ('Int16', True),
                                'int32': ('Int32', True), 'int64': ('Int64', True), 'uint8': ('UInt8', True),
                                'uint16': ('UInt16', True), 'uint32': ('UInt32', True), 'uint64': ('UInt64', True),
                                'float32': ('Float32', True), 'float64': ('Float64', True),
                                'text': ('Text', False), 'data': ('Data', False), 'list': ('List', False),
                                'enum': ('Enum', False), 'struct': ('Struct', False),
                            }

                            if type_enum in type_map:
                                data_type, is_numeric = type_map[type_enum]
                        except:
                            pass

                        # Get units
                        unit = CEREAL_SIGNAL_UNITS.get(field_name, '')
                        unit_cn = UNIT_CN_MAP.get(unit, '') if unit else ''

                        # Insert to database (SQLite syntax)
                        try:
                            cursor.execute("""
                                INSERT OR REPLACE INTO cereal_signal_definitions
                                (message_type, signal_name, full_name, data_type,
                                 name_cn, unit, unit_cn)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (msg_type, field_name, full_signal_name, data_type,
                                  name_cn, unit, unit_cn))

                            imported_count += 1
                            self.db_manager.conn.commit()  # SQLite needs commit each time
                        except Exception as e:
                            logger.debug(f"Failed to insert signal {full_signal_name}: {e}")
                            self.db_manager.conn.rollback()

                except Exception as e:
                    logger.warning(f"Error processing message type {msg_type}: {e}")

            self.db_manager.conn.commit()

            self.cereal_status_text.append(f"✓ Successfully imported {imported_count} Cereal signal definitions")
            self.cereal_status_text.append("✓ Complete!")

            QMessageBox.information(self, "Import Success", f"Successfully imported {imported_count} Cereal signal definitions")

            # Reload Cereal info and signal translation table
            self.load_cereal_info()
            self.load_cereal_signals()

        except Exception as e:
            self.db_manager.conn.rollback()
            logger.error(f"Failed to reimport Cereal signals: {e}")
            self.cereal_status_text.append(f"✗ Error: {str(e)}")
            import traceback
            self.cereal_status_text.append(traceback.format_exc())
            QMessageBox.critical(self, "Import Failed", f"Failed to re-import Cereal signals: {e}")

    # ========================================================================
    # DBC Management Functions
    # ========================================================================
    def browse_dbc_file(self):
        """Browse DBC file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select DBC File",
            "",
            "DBC Files (*.dbc);;All Files (*.*)"
        )

        if file_path:
            self.dbc_file_edit.setText(file_path)
            self.dbc_status_text.append(f"Selected: {file_path}")

    def reimport_dbc_signals(self):
        """Re-import DBC signal definitions"""
        if not self.db_manager:
            QMessageBox.warning(self, "Not Connected", "Please connect to database first")
            return

        dbc_file = self.dbc_file_edit.text().strip()
        if not dbc_file or not os.path.exists(dbc_file):
            QMessageBox.warning(self, "File Error", "Please select a valid DBC file first")
            return

        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            "Confirm Re-import",
            "This operation will delete all existing CAN signal definitions and re-import them.\n\n"
            "Note: Translations and unit settings will be preserved (if signal names match).\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.dbc_status_text.clear()
            self.dbc_status_text.append("Starting to import DBC signal definitions...")

            # Import DBC
            from src.core.dbc_parser import DBCParser

            parser = DBCParser(dbc_file)
            self.dbc_status_text.append(f"✓ Successfully loaded DBC file")
            self.dbc_status_text.append(f"  Message count: {len(parser.db.messages)}")

            # Count total signals
            total_signals = sum(len(msg.signals) for msg in parser.db.messages)
            self.dbc_status_text.append(f"  Signal count: {total_signals}")

            # Delete old definitions
            cursor = self.db_manager.cursor
            cursor.execute("DELETE FROM can_signal_definitions")
            self.dbc_status_text.append(f"✓ Cleared old CAN signal definitions")

            # Import new definitions
            import_count = 0
            for message in parser.db.messages:
                message_name = message.name
                message_name_cn = parser.translate(message_name)
                can_id = message.frame_id

                for signal in message.signals:
                    signal_name = signal.name
                    full_signal_name = f"can.{can_id:03x}.{signal_name}"
                    signal_name_cn = parser.translate(signal_name)

                    # Units
                    unit = signal.unit if signal.unit else None
                    unit_cn = parser.translate(signal.unit) if signal.unit else None

                    cursor.execute("""
                        INSERT OR REPLACE INTO can_signal_definitions
                        (dbc_file, can_id, message_name, message_name_cn, signal_name, signal_name_cn,
                         full_name, unit, unit_cn)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (dbc_file_name, can_id, message_name, message_name_cn, signal_name, signal_name_cn,
                          full_signal_name, unit, unit_cn))

                    import_count += 1
                    self.db_manager.conn.commit()

            self.db_manager.conn.commit()

            self.dbc_status_text.append(f"✓ Successfully imported {import_count} CAN signal definitions")
            self.dbc_status_text.append("✓ Complete!")

            QMessageBox.information(self, "Import Success", f"Successfully imported {import_count} CAN signal definitions")

            # Reload DBC info and CAN table
            self.load_dbc_info()
            self.load_can_signals()

        except Exception as e:
            self.db_manager.conn.rollback()
            logger.error(f"Failed to reimport DBC: {e}")
            self.dbc_status_text.append(f"✗ Error: {str(e)}")
            QMessageBox.critical(self, "Import Failed", f"Failed to re-import DBC: {e}")

    # ========================================================================
    # ========================================================================
    # Database Management Functions (SQLite version)
    # ========================================================================

    def refresh_database_info(self):
        """Refresh database information"""
        if not self.db_manager:
            return

        try:
            # Display database file path
            self.db_path_label.setText(str(self.db_manager.db_path))

            # Display file size
            import os
            if self.db_manager.db_path.exists():
                size_bytes = os.path.getsize(self.db_manager.db_path)
                size_mb = size_bytes / (1024 * 1024)
                self.db_size_label.setText(f"{size_mb:.2f} MB")
            else:
                self.db_size_label.setText("File does not exist")

            # Display table count
            cursor = self.db_manager.cursor
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            self.table_count_label.setText(str(table_count))

        except Exception as e:
            logger.error(f"Failed to refresh database info: {e}")
            QMessageBox.critical(self, "Error", f"Failed to refresh database info: {e}")

    def vacuum_database(self):
        """Compact database"""
        if not self.db_manager:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Compaction",
            "Database compaction will reclaim unused space. This may take some time.\n\nAre you sure you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.db_manager.conn.execute("VACUUM")
                self.db_manager.conn.commit()
                QMessageBox.information(self, "Complete", "Database compaction complete!")
                self.refresh_database_info()
            except Exception as e:
                logger.error(f"Failed to vacuum database: {e}")
                QMessageBox.critical(self, "Error", f"Failed to compact database: {e}")

    # ========================================================================
    # Old PostgreSQL methods (SQLite doesn't need these functions)
    # ========================================================================
    def test_connection_clicked(self):
        """Test database connection (SQLite doesn't need)"""
        pass

    def create_database(self, *args, **kwargs):
        """Create new database (SQLite doesn't need)"""
        pass

    def save_config_clicked(self):
        """Save settings and reconnect (SQLite doesn't need)"""
        pass

    def refresh_table_list(self):
        """Refresh table list (SQLite version)"""
        if not self.db_manager or not self.db_manager.conn:
            self.table_list.setRowCount(0)
            return

        try:
            cursor = self.db_manager.conn.cursor()

            # Use SQLite's sqlite_master table to query all tables
            cursor.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                    AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)

            tables = cursor.fetchall()
            self.table_list.setRowCount(len(tables))

            for i, (table_name,) in enumerate(tables):
                # Table name
                name_item = QTableWidgetItem(table_name)
                self.table_list.setItem(i, 0, name_item)

                # Record count
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                    count = cursor.fetchone()[0]
                    count_item = QTableWidgetItem(f"{count:,}")
                except:
                    count_item = QTableWidgetItem("N/A")

                self.table_list.setItem(i, 1, count_item)

            logger.info(f"Refreshed table list: {len(tables)} tables")

        except Exception as e:
            logger.error(f"Failed to refresh table list: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load table list:\n{str(e)}")

    def view_table_data(self):
        """View table contents"""
        selected_rows = self.table_list.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, "Not Selected", "Please select a table first")
            return

        table_name = self.table_list.item(selected_rows[0].row(), 0).text()

        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute(f'SELECT * FROM "{table_name}" LIMIT 100')

            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

            # Create new dialog to display data
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Table Contents - {table_name} (first 100 rows)")
            dialog.setGeometry(100, 100, 1000, 600)

            layout = QVBoxLayout()

            table = QTableWidget()
            table.setColumnCount(len(columns))
            table.setHorizontalHeaderLabels(columns)
            table.setRowCount(len(rows))

            for row_idx, row_data in enumerate(rows):
                for col_idx, value in enumerate(row_data):
                    table.setItem(row_idx, col_idx, QTableWidgetItem(str(value) if value is not None else ''))

            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            layout.addWidget(table)

            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.close)
            layout.addWidget(close_btn)

            dialog.setLayout(layout)
            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to view table:\n{str(e)}")

    def truncate_table(self):
        """Clear table"""
        selected_rows = self.table_list.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, "Not Selected", "Please select a table first")
            return

        table_name = self.table_list.item(selected_rows[0].row(), 0).text()

        reply = QMessageBox.warning(
            self,
            "Confirm Clear",
            f"Are you sure you want to clear all data from table '{table_name}'?\n\nThis operation cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            cursor = self.db_manager.conn.cursor()
            # SQLite doesn't support TRUNCATE, use DELETE FROM
            cursor.execute(f'DELETE FROM "{table_name}"')
            self.db_manager.conn.commit()

            QMessageBox.information(self, "Clear Success", f"Table '{table_name}' has been cleared")
            self.refresh_table_list()

        except Exception as e:
            self.db_manager.conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed to clear table:\n{str(e)}")

    def drop_table(self):
        """Delete table"""
        selected_rows = self.table_list.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, "Not Selected", "Please select a table first")
            return

        table_name = self.table_list.item(selected_rows[0].row(), 0).text()

        reply = QMessageBox.critical(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete table '{table_name}'?\n\nThis operation will permanently delete the table and all its data. This cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            cursor = self.db_manager.conn.cursor()
            # SQLite doesn't support CASCADE, but automatically handles FOREIGN KEY constraints
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            self.db_manager.conn.commit()

            QMessageBox.information(self, "Delete Success", f"Table '{table_name}' has been deleted")
            self.refresh_table_list()

        except Exception as e:
            self.db_manager.conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed to delete table:\n{str(e)}")

    def create_or_update_schema(self):
        """Create or update database schema"""
        if not self.db_manager or not self.db_manager.conn:
            QMessageBox.warning(self, "Not Connected", "Please connect to database first")
            return

        reply = QMessageBox.question(
            self,
            "Create/Update Database Schema",
            "This will execute database_schema.sql to create or update the database schema.\n\n"
            "This operation will:\n"
            "• Create missing tables\n"
            "• Create indexes and triggers\n"
            "• Not delete existing data\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            schema_file = os.path.join(
                os.path.dirname(__file__), '..', '..', '..', 'database_schema_sqlite.sql'
            )

            if not os.path.exists(schema_file):
                QMessageBox.critical(self, "Error", "Cannot find database_schema_sqlite.sql file")
                return

            with open(schema_file, 'r', encoding='utf-8') as f:
                schema_sql = f.read()

            # Split and execute SQL statements
            statements = []
            current_statement = []

            for line in schema_sql.split('\n'):
                line = line.strip()
                if line.startswith('--') or not line:
                    continue

                current_statement.append(line)

                if line.endswith(';'):
                    statements.append('\n'.join(current_statement))
                    current_statement = []

            if current_statement:
                statements.append('\n'.join(current_statement))

            success_count = 0
            error_count = 0
            cursor = self.db_manager.conn.cursor()

            for statement in statements:
                if not statement.strip():
                    continue

                try:
                    cursor.execute(statement)
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    logger.debug(f"Statement error: {e}")

            self.db_manager.conn.commit()

            result_msg = f"Database schema update complete!\n\n"
            result_msg += f"Successfully executed: {success_count} statements\n"

            if error_count > 0:
                result_msg += f"Ignored errors: {error_count} (usually existing objects)\n"

            QMessageBox.information(self, "Update Complete", result_msg)
            self.refresh_table_list()

        except Exception as e:
            self.db_manager.conn.rollback()
            logger.error(f"Failed to update database schema: {e}")
            QMessageBox.critical(self, "Update Failed", f"Failed to update database structure:\n{str(e)}")

    def delete_database(self):
        """Delete database (SQLite doesn't need - just delete .db file directly)"""
        pass
