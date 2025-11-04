# -*- coding: utf-8 -*-
"""
Configuration Manager Dialog - Manage layout and signal presets
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QInputDialog, QHeaderView, QTextEdit, QLabel
)
from PyQt6.QtCore import Qt
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ConfigManagerDialog(QDialog):
    """Configuration Manager Dialog"""

    def __init__(self, parent=None, translation_manager=None):
        super().__init__(parent)
        self.parent_window = parent
        self.translation_manager = translation_manager
        self.config_dir = Path("data/configs")
        self.config_dir.mkdir(parents=True, exist_ok=True)

        t = self.translation_manager.t if self.translation_manager else lambda x: x

        self.setWindowTitle(t("Configuration Manager"))
        self.setModal(True)
        self.resize(700, 500)

        self.setup_ui()
        self.load_config_list()

    def setup_ui(self):
        """Setup UI"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        layout = QVBoxLayout(self)

        # Info label
        info_label = QLabel(
            "配置可以儲存當前的訊號選擇、視窗佈局和顯示設定。\n"
            "儲存配置後可以快速切換到不同的工作環境。"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(info_label)

        # Config list
        self.config_table = QTableWidget()
        self.config_table.setColumnCount(3)
        self.config_table.setHorizontalHeaderLabels([t("Config Name"), t("Signal Count"), t("Description")])
        self.config_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.config_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.config_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Set column widths
        header = self.config_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        # Double-click to load config
        self.config_table.itemDoubleClicked.connect(self.load_config)

        layout.addWidget(self.config_table)

        # Button area
        button_layout = QHBoxLayout()

        save_btn = QPushButton(t("Save Current Config"))
        save_btn.clicked.connect(self.save_current_config)
        button_layout.addWidget(save_btn)

        load_btn = QPushButton(t("Load Selected Config"))
        load_btn.clicked.connect(self.load_config)
        button_layout.addWidget(load_btn)

        delete_btn = QPushButton(t("Delete Config"))
        delete_btn.clicked.connect(self.delete_config)
        button_layout.addWidget(delete_btn)

        button_layout.addStretch()

        close_btn = QPushButton(t("Close"))
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def load_config_list(self):
        """Load config list"""
        try:
            self.config_table.setRowCount(0)

            # Read all config files
            config_files = list(self.config_dir.glob("*.json"))

            for config_file in sorted(config_files):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)

                    row = self.config_table.rowCount()
                    self.config_table.insertRow(row)

                    # Config name
                    name_item = QTableWidgetItem(config.get('name', config_file.stem))
                    name_item.setData(Qt.ItemDataRole.UserRole, str(config_file))
                    self.config_table.setItem(row, 0, name_item)

                    # Signal count
                    signal_count = len(config.get('signals', []))
                    self.config_table.setItem(row, 1, QTableWidgetItem(str(signal_count)))

                    # Description
                    description = config.get('description', '')
                    self.config_table.setItem(row, 2, QTableWidgetItem(description))

                except Exception as e:
                    logger.error(f"Failed to load config {config_file}: {e}")

            logger.info(f"Loaded {len(config_files)} configurations")

        except Exception as e:
            logger.error(f"Failed to load config list: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load config list: {e}")

    def save_current_config(self):
        """Save current configuration"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        if not self.parent_window:
            QMessageBox.warning(self, t("Warning"), "Cannot get main window info")
            return

        # Ask for config name
        name, ok = QInputDialog.getText(
            self,
            t("Save Config"),
            t("Enter Config Name") + ":"
        )

        if not ok or not name:
            return

        # Ask for description (optional)
        description, ok = QInputDialog.getText(
            self,
            t("Config Description"),
            "Enter config description (optional):"
        )

        if not ok:
            description = ""

        try:
            # Collect current configuration
            config = {
                'name': name,
                'description': description,
                'signals': self.parent_window.signal_selector.get_selected_signals(),
                'view_states': {
                    'video': self.parent_window.view_video_action.isChecked(),
                    'data_table': self.parent_window.view_data_table_action.isChecked(),
                    'signal_selector': self.parent_window.view_signal_selector_action.isChecked(),
                    'cereal_chart': self.parent_window.view_cereal_chart_action.isChecked(),
                    'can_chart': self.parent_window.view_can_chart_action.isChecked(),
                },
                'splitter_sizes': {
                    'main': self.parent_window.main_splitter.sizes(),
                    'left': self.parent_window.left_splitter.sizes(),
                    'right': self.parent_window.right_splitter.sizes(),
                }
            }

            # Save to file
            config_file = self.config_dir / f"{name}.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved configuration: {name}")
            QMessageBox.information(self, t("Success"), t("Config '{0}' saved successfully").format(name))

            # Reload list
            self.load_config_list()

        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            QMessageBox.critical(self, t("Error"), f"Failed to save config: {e}")

    def load_config(self):
        """Load selected configuration"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        selected_rows = self.config_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.information(self, t("Information"), t("Please select a config to load"))
            return

        row = selected_rows[0].row()
        config_file = Path(self.config_table.item(row, 0).data(Qt.ItemDataRole.UserRole))
        config_name = self.config_table.item(row, 0).text()

        try:
            # Read config
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # Confirmation dialog
            reply = QMessageBox.question(
                self,
                t("Load Config"),
                f"確定要載入配置 '{config_name}' 嗎？\n\n"
                f"這將會：\n"
                f"• 更改訊號選擇（{len(config.get('signals', []))} 個訊號）\n"
                f"• 調整視窗佈局和顯示設定\n",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # Apply config
            self.apply_config(config)

            logger.info(f"Loaded configuration: {config_name}")
            QMessageBox.information(self, t("Success"), t("Config '{0}' loaded successfully").format(config_name))

        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            QMessageBox.critical(self, t("Error"), f"Failed to load config: {e}")

    def apply_config(self, config: dict):
        """Apply config to main window"""
        if not self.parent_window:
            return

        try:
            # Apply window display states
            view_states = config.get('view_states', {})

            if 'video' in view_states:
                self.parent_window.view_video_action.setChecked(view_states['video'])
            if 'data_table' in view_states:
                self.parent_window.view_data_table_action.setChecked(view_states['data_table'])
            if 'signal_selector' in view_states:
                self.parent_window.view_signal_selector_action.setChecked(view_states['signal_selector'])
            if 'cereal_chart' in view_states:
                self.parent_window.view_cereal_chart_action.setChecked(view_states['cereal_chart'])
            if 'can_chart' in view_states:
                self.parent_window.view_can_chart_action.setChecked(view_states['can_chart'])

            # Apply splitter sizes
            splitter_sizes = config.get('splitter_sizes', {})

            if 'main' in splitter_sizes:
                self.parent_window.main_splitter.setSizes(splitter_sizes['main'])
            if 'left' in splitter_sizes:
                self.parent_window.left_splitter.setSizes(splitter_sizes['left'])
            if 'right' in splitter_sizes:
                self.parent_window.right_splitter.setSizes(splitter_sizes['right'])

            # Apply signal selection (only if segment is loaded)
            if self.parent_window.current_segment_id:
                signals = config.get('signals', [])
                # First deselect all
                self.parent_window.signal_selector.deselect_all()
                # Select signals from config
                for signal_name in signals:
                    self.parent_window.signal_selector.select_signal(signal_name)

        except Exception as e:
            logger.error(f"Failed to apply config: {e}")
            raise

    def delete_config(self):
        """Delete selected configuration"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        selected_rows = self.config_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.information(self, t("Information"), t("Please select a config to delete"))
            return

        row = selected_rows[0].row()
        config_file = Path(self.config_table.item(row, 0).data(Qt.ItemDataRole.UserRole))
        config_name = self.config_table.item(row, 0).text()

        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            t("Confirm Delete Config"),
            f"確定要刪除配置 '{config_name}' 嗎？\n\n此操作無法復原。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Delete file
            config_file.unlink()

            logger.info(f"Deleted configuration: {config_name}")
            QMessageBox.information(self, t("Success"), t("Config '{0}' deleted successfully").format(config_name))

            # Reload list
            self.load_config_list()

        except Exception as e:
            logger.error(f"Failed to delete config: {e}")
            QMessageBox.critical(self, t("Error"), f"Failed to delete config: {e}")
