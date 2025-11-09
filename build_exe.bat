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
echo 編譯完成！正在複製必要檔案...
echo ========================================
echo.

REM 複製 capnp 檔案
echo 複製 capnp schema 檔案...
copy /Y *.capnp dist\OpenpilotLogViewer\ >nul

REM 複製 DBC 檔案
echo 複製 DBC 檔案...
copy /Y vw_mqb.dbc dist\OpenpilotLogViewer\ >nul

REM 複製空資料庫
echo 複製空資料庫...
copy /Y oplog.db dist\OpenpilotLogViewer\ >nul

REM 複製 include 目錄到主目錄（log.capnp 需要）
echo 複製 include 目錄...
xcopy /Y /E /I dist\OpenpilotLogViewer\_internal\include dist\OpenpilotLogViewer\include >nul

echo.
echo 執行檔位置: dist\OpenpilotLogViewer\OpenpilotLogViewer.exe
echo.
echo ============================================================
echo 部署準備完成！
echo ============================================================
echo 已自動複製以下檔案：
echo ✓ 5 個 .capnp schema 檔案
echo ✓ vw_mqb.dbc 資料庫定義檔
echo ✓ oplog.db 空資料庫
echo ✓ include 目錄 (log.capnp 需要)
echo.
echo 最終發布結構：
echo dist\OpenpilotLogViewer\
echo ├── OpenpilotLogViewer.exe
echo ├── _internal\           (PyInstaller 內部檔案)
echo │   ├── src\            (Python 源碼，已打包)
echo │   ├── tools\          (工具程式，已打包)
echo │   ├── capnp\          (pycapnp 套件)
echo │   └── include\        (c++.capnp)
echo ├── include\            (log.capnp 引用用)
echo ├── *.capnp             (5 個 schema 檔案)
echo ├── vw_mqb.dbc
echo └── oplog.db
echo.
echo 現在可以直接發布 dist\OpenpilotLogViewer\ 整個目錄！
echo ============================================================
echo.

pause
