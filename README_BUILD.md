# openpilot Log Viewer - 編譯與部署指南

## 編譯架構說明

本專案採用**最小化編譯**策略：
- ✅ **只編譯 `main.py`** 成 exe
- ✅ **所有其他 Python 檔案保持源碼** 形式
- ✅ **所有資料檔案放在外部**

### 設計理念

```
main.py (編譯成 exe)
    ↓ 呼叫
src/app.py (源碼，可修改)
    ↓ 呼叫
src/ui/*, src/core/*, tools/* (源碼，可修改)
```

**好處：**
1. 修改應用程式邏輯不需要重新編譯
2. 使用者可以自訂和擴展功能
3. 編譯速度快
4. 完全透明

---

## 開發者編譯步驟

### 1. 建立虛擬環境（首次）

```bash
# 建立虛擬環境
python -m venv venv

# 啟動虛擬環境
venv\Scripts\activate

# 安裝依賴
pip install -r requirements.txt

# 安裝 PyInstaller
pip install pyinstaller
```

### 2. 編譯 EXE

```bash
# 確保已啟動虛擬環境
venv\Scripts\activate

# 執行編譯
build_exe.bat
```

### 3. 部署發布

編譯完成後，需要將以下內容複製到發布目錄：

```
發布目錄/
├── dist\OpenpilotLogViewer\      # 從編譯結果複製
│   ├── OpenpilotLogViewer.exe    # 編譯的 exe
│   └── _internal\                # PyInstaller 依賴庫
├── src\                          # 從專案根目錄複製（源碼）
├── tools\                        # 從專案根目錄複製（源碼）
├── data\                         # 從專案根目錄複製（資料檔案）
│   ├── dbc\
│   └── translations\
├── i18n\                         # 從專案根目錄複製（UI 翻譯）
├── log.capnp                     # 從專案根目錄複製
├── car.capnp                     # 從專案根目錄複製
├── custom.capnp                  # 從專案根目錄複製
└── legacy.capnp                  # 從專案根目錄複製
```

**簡化部署腳本（可選）：**

```bat
@echo off
REM 複製所有需要的檔案到發布目錄
xcopy /E /I /Y dist\OpenpilotLogViewer release\
xcopy /E /I /Y src release\src\
xcopy /E /I /Y tools release\tools\
xcopy /E /I /Y data release\data\
xcopy /E /I /Y i18n release\i18n\
copy /Y *.capnp release\
echo 部署完成！
pause
```

---

## 使用者修改指南

### 不需要重新編譯的修改

✅ **可以直接修改的檔案：**
- `src/**/*.py` - 所有應用程式邏輯
- `tools/**/*.py` - 工具程式
- `data/dbc/*.dbc` - DBC 檔案
- `data/translations/*.json` - 訊號中文翻譯
- `i18n/*.json` - UI 介面翻譯
- `*.capnp` - Schema 檔案

**修改後直接執行 `OpenpilotLogViewer.exe` 即可！**

### 需要重新編譯的修改

❌ **如果修改了以下檔案，需要重新編譯：**
- `main.py` - 主程式入口（但通常不需要改）

**重新編譯步驟：**
1. 安裝 Python 3.10+
2. 建立虛擬環境並安裝依賴（見上方）
3. 執行 `build_exe.bat`
4. 重新部署

---

## 常見問題

### Q1: 為什麼編譯這麼慢？
A: 第一次編譯會比較慢（需要分析所有依賴）。後續編譯會快很多。

### Q2: exe 檔案很大怎麼辦？
A: 正常。PyInstaller 會打包整個 Python 運行環境和所有依賴庫。如果需要減小體積，可以使用 UPX 壓縮（已啟用）。

### Q3: 用戶可以看到源碼嗎？
A: 可以。`src/` 和 `tools/` 都是完整的 Python 源碼，用戶可以閱讀和修改。

### Q4: 修改了 src/app.py 需要重新編譯嗎？
A: **不需要！** `src/app.py` 是源碼形式，修改後直接執行 exe 即可生效。

### Q5: 如何打包成單一 exe 檔案？
A: 修改 `build_exe.spec`，將 `exclude_binaries=True` 改為 `False`，並使用 `onefile` 模式。但**不建議**，因為：
- 啟動速度慢
- 無法讓用戶修改源碼和資料檔案
- 檔案超大

---

## 技術細節

### 編譯配置

- **spec 檔案**: `build_exe.spec`
- **編譯腳本**: `build_exe.bat`
- **Python 版本**: 3.10+
- **打包工具**: PyInstaller

### 依賴庫

主要依賴：
- PyQt6 - GUI 框架
- pyqtgraph - 圖表繪製
- numpy - 數值計算
- av (PyAV) - 影片解碼
- opencv-python - 影像處理
- cantools - CAN 訊號解析
- pandas - 資料處理
- pyarrow - Parquet 格式支援

### 為什麼不用 auto-py-to-exe？

可以用，但 `build_exe.bat` 已經提供了自動化流程，更方便。

---

## 授權

本專案遵循原 openpilot 專案的開源授權。
