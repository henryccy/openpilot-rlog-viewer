# -*- coding: utf-8 -*-
"""
openpilot Windows Viewer - Main Entry Point
openpilot Windows 查看器 - 主程式入口
"""
import sys
import os
from pathlib import Path
import logging

# Suppress Qt screen detection warnings on Windows
os.environ['QT_LOGGING_RULES'] = 'qt.qpa.screen=false'

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from src.ui.main_window import MainWindow


def setup_logging():
    """設定 logging 系統"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('oplog_viewer.log', encoding='utf-8')
        ]
    )

    # 捕捉所有未處理的異常到 log
    def exception_handler(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = exception_handler


def main():
    """主程式"""
    try:
        # Setup logging
        setup_logging()

        # Enable high DPI scaling
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        # Create application
        app = QApplication(sys.argv)
        app.setApplicationName("openpilot Windows Viewer")
        app.setOrganizationName("openpilot")

        # Create and show main window
        window = MainWindow()
        window.show()

        # Run event loop
        sys.exit(app.exec())

    except Exception as e:
        logging.critical(f"Fatal error in main: {e}", exc_info=True)
        import traceback
        with open('crash.log', 'w', encoding='utf-8') as f:
            f.write(f"Fatal error:\n")
            f.write(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
