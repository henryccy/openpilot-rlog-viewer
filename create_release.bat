@echo off
chcp 65001 > nul
REM ============================================================
REM 建立發布版本 - openpilot Log Viewer v1.1.0
REM ============================================================

set VERSION=1.1.0
set RELEASE_NAME=OpenpilotLogViewer-v%VERSION%-Windows-x64

echo ========================================
echo 建立發布版本 v%VERSION%
echo ========================================
echo.

REM 檢查編譯結果是否存在
if not exist "dist\OpenpilotLogViewer\OpenpilotLogViewer.exe" (
    echo 錯誤: 找不到編譯結果！
    echo 請先執行 build_exe.bat 進行編譯
    pause
    exit /b 1
)

REM 清理舊的 release 目錄
if exist "release" (
    echo 清理舊的 release 目錄...
    rmdir /s /q release
)

REM 建立 release 目錄
echo 建立 release 目錄...
mkdir release\%RELEASE_NAME%

REM 複製編譯結果
echo 複製編譯結果...
xcopy /E /I /Y dist\OpenpilotLogViewer\* release\%RELEASE_NAME%\ >nul

echo.
echo ========================================
echo 發布目錄建立完成！
echo ========================================
echo.
echo 路徑: release\%RELEASE_NAME%\
echo.
echo 接下來將壓縮成 ZIP 檔案...
echo.

REM 使用 PowerShell 壓縮
echo 正在壓縮...
powershell -Command "Compress-Archive -Path 'release\%RELEASE_NAME%' -DestinationPath 'release\%RELEASE_NAME%.zip' -Force"

if errorlevel 1 (
    echo.
    echo 壓縮失敗！請檢查 PowerShell 是否可用
    pause
    exit /b 1
)

echo.
echo ========================================
echo 發布檔案建立完成！
echo ========================================
echo.
echo 輸出檔案: release\%RELEASE_NAME%.zip
echo.
echo 可以上傳到 GitHub Releases 了！
echo ========================================
echo.

pause
