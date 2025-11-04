# -*- coding: utf-8 -*-
"""
Signal Definition Import Dialog
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QTextEdit, QGroupBox, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import logging
import os

logger = logging.getLogger(__name__)


class SignalImportWorker(QThread):
    """Signal import worker thread"""
    progress = pyqtSignal(int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, db_manager, capnp_path='log.capnp', dbc_path='vw_mqb.dbc', translation_manager=None):
        super().__init__()
        self.db_manager = db_manager
        self.capnp_path = capnp_path
        self.dbc_path = dbc_path
        self.translation_manager = translation_manager

    def run(self):
        """Execute import"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        try:
            # Import tool (SQLite version)
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

            from tools.import_signal_definitions_sqlite import SignalDefinitionImporter

            importer = SignalDefinitionImporter(self.db_manager)

            # Import Cereal signals (including custom.capnp and legacy.capnp)
            self.log_message.emit(t("Importing Cereal signal definitions..."))
            self.log_message.emit(t("Includes: log.capnp, car.capnp, custom.capnp, legacy.capnp"))
            self.progress.emit(10)

            cereal_count = importer.import_cereal_signals()
            self.log_message.emit(t("✓ Successfully imported {0} Cereal signals").format(cereal_count))
            self.progress.emit(50)

            # Import CAN signals
            can_count = 0
            if self.dbc_path and os.path.exists(self.dbc_path):
                self.log_message.emit(t("Importing CAN signal definitions..."))
                self.log_message.emit(t("This may take 1-2 minutes..."))
                self.progress.emit(60)

                can_count = importer.import_can_signals(self.dbc_path)
                self.log_message.emit(t("✓ Successfully imported {0} CAN signals").format(can_count))
                self.progress.emit(100)
            else:
                self.log_message.emit(t("No DBC file specified, skipping CAN signal import"))
                self.progress.emit(100)

            # Complete
            summary = t("Import completed!\n")
            summary += t("Cereal signals: {0}\n").format(cereal_count)
            summary += t("CAN signals: {0}\n").format(can_count)
            summary += t("Total: {0}").format(cereal_count + can_count)

            self.finished.emit(True, summary)

        except Exception as e:
            error_msg = t("Import failed: {0}").format(str(e))
            self.log_message.emit(f"✗ {error_msg}")
            self.finished.emit(False, error_msg)


class SignalImportDialog(QDialog):
    """Signal definition import dialog"""

    def __init__(self, db_manager, parent=None, translation_manager=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.translation_manager = translation_manager
        self.worker = None

        t = self.translation_manager.t if self.translation_manager else lambda x: x

        self.setWindowTitle(t("Import Signal Definitions"))
        self.setModal(True)
        self.resize(700, 500)

        self.setup_ui()

    def setup_ui(self):
        """Build UI"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        layout = QVBoxLayout(self)

        # ============================================================
        # Description
        # ============================================================
        info_group = QGroupBox(t("Description"))
        info_layout = QVBoxLayout(info_group)

        current_lang = self.translation_manager.get_current_language() if self.translation_manager else 'en'

        if current_lang == 'zh_TW':
            info_text_content = (
                "此工具會解析 log.capnp 和 DBC 檔案，將所有訊號定義匯入資料庫。\n\n"
                "包含：\n"
                "• Cereal 訊號（預計 300-500 個）：carState, controlsState, FrogPilot 等\n"
                "  - log.capnp 會自動載入 car.capnp, custom.capnp, legacy.capnp\n"
                "  - 支援嵌套結構（wheelSpeeds, cruiseState, actuators）\n"
                "• CAN 訊號（約 1300+ 個）：所有 DBC 定義的 CAN 訊號\n"
                "  - 包含中文翻譯和單位資訊\n\n"
                "請選擇要使用的 log.capnp 和 DBC 檔案。\n"
                "匯入後，訊號選擇器會顯示完整的訊號列表和中文註解。"
            )
        else:
            info_text_content = (
                "This tool parses log.capnp and DBC files, importing all signal definitions into the database.\n\n"
                "Contains:\n"
                "• Cereal signals (approx. 300-500): carState, controlsState, FrogPilot, etc.\n"
                "  - log.capnp automatically loads car.capnp, custom.capnp, legacy.capnp\n"
                "  - Supports nested structures (wheelSpeeds, cruiseState, actuators)\n"
                "• CAN signals (approx. 1300+): All CAN signals defined in DBC\n"
                "  - Includes Chinese translations and unit information\n\n"
                "Please select the log.capnp and DBC files to use.\n"
                "After import, the signal selector will display the complete signal list and Chinese annotations."
            )

        info_text = QLabel(info_text_content)
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        layout.addWidget(info_group)

        # ============================================================
        # File selection
        # ============================================================
        file_group = QGroupBox(t("Definition Files"))
        file_layout = QVBoxLayout(file_group)

        # Cap'n Proto file
        capnp_layout = QHBoxLayout()
        capnp_layout.addWidget(QLabel("log.capnp:"))
        self.capnp_path = "log.capnp"  # Default path
        self.capnp_label = QLabel(self.capnp_path)
        self.capnp_label.setStyleSheet("color: #666;")
        capnp_layout.addWidget(self.capnp_label, 1)
        browse_capnp_btn = QPushButton(t("Browse..."))
        browse_capnp_btn.clicked.connect(self.browse_capnp_file)
        capnp_layout.addWidget(browse_capnp_btn)
        file_layout.addLayout(capnp_layout)

        # DBC file
        dbc_layout = QHBoxLayout()
        dbc_layout.addWidget(QLabel(t("DBC File:")))
        self.dbc_path = "vw_mqb.dbc"  # Default path
        self.dbc_label = QLabel(self.dbc_path)
        self.dbc_label.setStyleSheet("color: #666;")
        dbc_layout.addWidget(self.dbc_label, 1)
        browse_dbc_btn = QPushButton(t("Browse..."))
        browse_dbc_btn.clicked.connect(self.browse_dbc_file)
        dbc_layout.addWidget(browse_dbc_btn)
        file_layout.addLayout(dbc_layout)

        layout.addWidget(file_group)

        # ============================================================
        # Progress
        # ============================================================
        progress_group = QGroupBox(t("Import Progress"))
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        layout.addWidget(progress_group)

        # ============================================================
        # Log
        # ============================================================
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group)

        # ============================================================
        # Buttons
        # ============================================================
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.start_button = QPushButton(t("Start Import"))
        self.start_button.clicked.connect(self.start_import)
        button_layout.addWidget(self.start_button)

        self.close_button = QPushButton(t("Close"))
        self.close_button.clicked.connect(self.accept)
        self.close_button.setEnabled(False)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def append_log(self, message: str):
        """Append log message"""
        self.log_text.append(message)

    def browse_capnp_file(self):
        """Browse and select Cap'n Proto file"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("Select log.capnp File"),
            "",
            "Cap'n Proto Files (*.capnp);;All Files (*.*)"
        )
        if file_path:
            self.capnp_path = file_path
            self.capnp_label.setText(file_path)

    def browse_dbc_file(self):
        """Browse and select DBC file"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("Select DBC File"),
            "",
            "DBC Files (*.dbc);;All Files (*.*)"
        )
        if file_path:
            self.dbc_path = file_path
            self.dbc_label.setText(file_path)

    def start_import(self):
        """Start import"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        self.start_button.setEnabled(False)
        self.log_text.clear()
        self.progress_bar.setValue(0)

        self.append_log(t("Starting to import signal definitions..."))
        self.append_log("")

        # Check if files exist
        if not os.path.exists(self.capnp_path):
            self.append_log(t("✗ Error: File not found {0}").format(self.capnp_path))
            self.start_button.setEnabled(True)
            return

        if not os.path.exists(self.dbc_path):
            self.append_log(t("✗ Error: File not found {0}").format(self.dbc_path))
            self.start_button.setEnabled(True)
            return

        self.append_log(f"Cap'n Proto: {self.capnp_path}")
        self.append_log(t("DBC File: {0}").format(self.dbc_path))
        self.append_log("")

        # Start worker thread
        self.worker = SignalImportWorker(self.db_manager, self.capnp_path, self.dbc_path, self.translation_manager)
        self.worker.progress.connect(self.on_progress)
        self.worker.log_message.connect(self.append_log)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, value: int):
        """Update progress"""
        self.progress_bar.setValue(value)

    def on_finished(self, success: bool, message: str):
        """Import finished"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        self.append_log("")
        self.append_log("=" * 50)
        self.append_log(message)
        self.append_log("=" * 50)

        self.close_button.setEnabled(True)

        if success:
            self.append_log("")
            self.append_log(t("You can now start importing Segment data!"))
