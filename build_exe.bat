@echo off
chcp 65001 > nul
REM ============================================================
REM 編譯 openpilot Log Viewer 為 Windows 執行檔
REM ============================================================

echo ========================================
echo 開始編譯 openpilot Log Viewer
echo ========================================
echo.

REM 檢查是否在虛擬環境中
if not defined VIRTUAL_ENV (
    echo 警告: 未偵測到虛擬環境
    echo 建議先啟動虛擬環境: venv\Scripts\activate
    echo.
    pause
)

REM 檢查 PyInstaller 是否安裝
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo 未安裝 PyInstaller，正在安裝...
    pip install pyinstaller
    echo.
)

REM 清理舊的編譯檔案
if exist "build" (
    echo 清理舊的 build 目錄...
    rmdir /s /q build
)
if exist "dist" (
    echo 清理舊的 dist 目錄...
    rmdir /s /q dist
)

echo.
echo ========================================
echo 開始執行 PyInstaller...
echo ========================================
echo.

REM 使用 spec 檔案編譯
pyinstaller build_exe.spec --clean

if errorlevel 1 (
    echo.
    echo ========================================
    echo 編譯失敗！
    echo ========================================
    pause
    exit /b 1
)

echo.
echo ========================================
echo 編譯完成！
echo ========================================
echo.
echo 執行檔位置: dist\OpenpilotLogViewer\OpenpilotLogViewer.exe
echo.
echo ============================================================
echo 重要！部署步驟：
echo ============================================================
echo 1. 將 dist\OpenpilotLogViewer\ 目錄複製到發布位置
echo 2. 將以下檔案/目錄複製到 OpenpilotLogViewer.exe 的同一層：
echo    - src\         (Python 源碼，可修改)
echo    - tools\       (工具程式，可修改)
echo    - data\        (DBC、翻譯等資料)
echo    - i18n\        (UI 翻譯)
echo    - *.capnp      (Schema 檔案)
echo.
echo 最終發布結構：
echo release\
echo ├── OpenpilotLogViewer.exe
echo ├── _internal\
echo ├── src\
echo ├── tools\
echo ├── data\
echo ├── i18n\
echo └── *.capnp
echo.
echo 用戶可以直接修改 src\ 和 data\ 中的檔案，不需要重新編譯！
echo ============================================================
echo.

pause
