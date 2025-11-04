# -*- coding: utf-8 -*-
"""
Import Progress Dialog - Shows progress while importing segments
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QTextEdit, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal
import logging

logger = logging.getLogger(__name__)


class ProgressDialogLogHandler(logging.Handler):
    """Custom logging handler that outputs log messages to progress dialog"""

    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
        self.setLevel(logging.INFO)
        # Set log format
        formatter = logging.Formatter('[%(name)s] %(message)s')
        self.setFormatter(formatter)

    def emit(self, record):
        """Send log record to dialog"""
        try:
            msg = self.format(record)
            # Use Qt's signal mechanism to safely update UI
            self.dialog.append_log(msg)
        except Exception:
            self.handleError(record)


class ImportProgressDialog(QDialog):
    """Import/Load progress dialog"""

    def __init__(self, parent=None, title="Import Segment", translation_manager=None):
        super().__init__(parent)
        self.translation_manager = translation_manager

        # Setup translation function
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        self.setWindowTitle(t(title))
        self.setModal(True)
        self.resize(600, 400)

        # Set initial status text based on title
        self.initial_status = t("Processing...")

        # Logging handler
        self.log_handler = None

        self.setup_ui()

    def setup_ui(self):
        """Build UI"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        layout = QVBoxLayout(self)

        # Status label
        self.status_label = QLabel(self.initial_status)
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Detail information
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        layout.addWidget(self.detail_text)

        # Close button
        self.close_button = QPushButton(t("Close"))
        self.close_button.clicked.connect(self.accept)
        self.close_button.setEnabled(False)
        layout.addWidget(self.close_button)

    def set_status(self, text: str):
        """Set status"""
        self.status_label.setText(text)

    def set_progress(self, value: int):
        """Set progress"""
        self.progress_bar.setValue(value)

    def append_log(self, text: str):
        """Append log"""
        self.detail_text.append(text)

    def set_complete(self, message="Completed"):
        """Set completion status"""
        self.close_button.setEnabled(True)
        self.set_status(message)

    def enable_logging(self):
        """Enable logging capture"""
        if not self.log_handler:
            self.log_handler = ProgressDialogLogHandler(self)
            # Add handler to root logger
            logging.getLogger().addHandler(self.log_handler)

    def disable_logging(self):
        """Disable logging capture"""
        if self.log_handler:
            logging.getLogger().removeHandler(self.log_handler)
            self.log_handler = None

    def closeEvent(self, event):
        """Clean up logging handler when closing dialog"""
        self.disable_logging()
        super().closeEvent(event)
