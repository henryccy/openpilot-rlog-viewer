# -*- coding: utf-8 -*-
"""
openpilot Windows Viewer - Application Logic
openpilot Windows 查看器 - 應用程式邏輯

這個檔案包含主要的應用程式邏輯，可以直接修改而不需要重新編譯 exe
"""
import sys
import os
import logging
from pathlib import Path

# 確保 _internal 目錄在 sys.path 中（給打包後的 EXE 使用）
# 這樣外部 src/ 程式碼才能找到 PyQt6, capnp 等依賴
# 檢查是否有 _internal 目錄（判斷是否為打包後的 EXE 環境）
current_dir = Path(__file__).parent.parent  # src/ 的上一層
internal_dir = current_dir / "_internal"
if internal_dir.exists() and str(internal_dir) not in sys.path:
    sys.path.insert(0, str(internal_dir))
    # print(f"DEBUG: Added {internal_dir} to sys.path")

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


def run_app():
    """運行應用程式 - 所有主要邏輯都在這裡"""
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
    # Translation system is initialized in MainWindow.__init__
    window = MainWindow()
    window.show()

    # Run event loop
    sys.exit(app.exec())
