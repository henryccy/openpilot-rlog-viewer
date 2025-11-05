# -*- coding: utf-8 -*-
"""
openpilot Windows Viewer - Main Entry Point
openpilot Windows 查看器 - 主程式入口
"""
import sys
from pathlib import Path
import logging

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


def main():
    """主程式"""
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


if __name__ == "__main__":
    main()
