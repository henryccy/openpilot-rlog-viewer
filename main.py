# -*- coding: utf-8 -*-
"""
openpilot Windows Viewer - Main Entry Point
openpilot Windows 查看器 - 主程式入口

這個檔案會被編譯成 exe，只包含最小的啟動代碼
所有應用程式邏輯都在 src/app.py，可以直接修改而不需要重新編譯

重要：使用動態 import 避免 PyInstaller 打包 src/ 目錄
"""
import sys
import os
from pathlib import Path
import importlib.util

if __name__ == "__main__":
    # 取得 EXE 所在目錄（執行時的實際位置）
    if getattr(sys, 'frozen', False):
        # 如果是打包後的 exe
        app_dir = Path(sys.executable).parent
    else:
        # 如果是直接執行 python main.py
        app_dir = Path(__file__).parent

    # 確保 src 目錄在路徑中
    sys.path.insert(0, str(app_dir))

    # 動態載入 src.app 模組（PyInstaller 無法追蹤）
    app_module_path = app_dir / "src" / "app.py"

    if not app_module_path.exists():
        print(f"錯誤：找不到 {app_module_path}")
        print(f"當前目錄：{app_dir}")
        print(f"請確保 src/app.py 存在於 EXE 的同一層目錄")
        input("按任意鍵退出...")
        sys.exit(1)

    # 使用 importlib 動態載入模組
    spec = importlib.util.spec_from_file_location("src.app", app_module_path)
    app_module = importlib.util.module_from_spec(spec)
    sys.modules["src.app"] = app_module
    spec.loader.exec_module(app_module)

    # 執行主程式
    app_module.run_app()
