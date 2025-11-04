# -*- coding: utf-8 -*-
"""
openpilot Windows Viewer - Main Entry Point
openpilot Windows 查看器 - 主程式入口

這個檔案會被編譯成 exe，只包含最小的啟動代碼
所有應用程式邏輯都在 src/app.py，可以直接修改而不需要重新編譯
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import and run the main application logic
from src.app import run_app

if __name__ == "__main__":
    run_app()
