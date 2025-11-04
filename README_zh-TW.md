# openpilot Windows 記錄檔查看器

[English](README.md) | 中文說明

一個原生的 Windows 應用程式，用於在本地查看和分析 openpilot 記錄檔，無需 Linux 環境，也不需要上傳到 connect.comma.ai。

**訊號定義**：使用 [FrogPilot](https://github.com/FrogAi/FrogPilot) 的訊號定義（相容 openpilot 0.9.7）

## 為什麼要用這個工具？

### 與 plotjuggler 和 cabana 的差異

openpilot 官方提供了 **plotjuggler** 和 **cabana** 用於記錄檔分析，但它們有一些限制：

| 功能 | plotjuggler/cabana | **openpilot Windows 查看器** |
|------|-------------------|------------------------------|
| **平台** | 僅限 Linux（Windows 需要 WSL） | ✅ 原生 Windows 應用程式 |
| **安裝** | 複雜的設定和依賴 | ✅ 下載即用（無需安裝 Python） |
| **資料存取** | 需先上傳到 connect.comma.ai | ✅ **直接本地分析**，透過 SSH/FTP |
| **工作流程** | C3/C3X → 上傳 → 連線到connect.comma.ai → 分析 | ✅ C3/C3X → SSH/FTP下載 → 匯入 → 立即分析 |
| **隱私** | 需要上傳 | ✅ 所有資料留在本地 |
| **速度** | 等待上傳/下載 | ✅ 即時分析 |

### 主要優勢

- **🪟 Windows 原生**：無需 Linux VM、WSL 或 Docker
- **🚀 直接存取 C3/C3X**：透過 SSH 或 FTP 直接複製記錄檔到本地磁碟
- **🔒 隱私優先**：無需雲端上傳 - 本地分析
- **⚡ 快速工作流程**：跳過上傳/下載步驟
- **🎨 豐富功能**：同步影片/資料播放、訊號搜尋、多語言支援

## 快速開始

### 一般使用者（無需程式設計）

1. **下載發行版**
   - 從 release 資料夾下載 `release/v1.0.zip`
   - 解壓縮到任意位置（例如 `C:\openpilot-viewer\`）

2. **設定 C3/C3X SSH 存取**（僅首次）

   ⚠️ **重要**：現代 C3/C3X 設備需要 SSH 金鑰認證（無密碼登入）。

   設定 SSH 存取：
   - 請自行搜尋：「comma 3 SSH key 設定」或「comma 3X SSH 存取」
   - 您需要在 comma 設備上配置 GitHub SSH 金鑰
   - 詳細步驟請參考 comma.ai 文件或社群指南

3. **從 C3/C3X 取得記錄檔**

   **方法 A：SSH/SCP（推薦）**
   ```bash
   # SSH 金鑰配置完成後，連接到你的 C3/C3X
   ssh comma@192.168.x.x

   # 找到你的記錄檔（通常在 /data/media/0/realdata/）
   cd /data/media/0/realdata/
   ls -lt

   # 從 Windows 端使用 SCP 複製整個 segment 目錄
   # 重要：必須複製整個 segment 資料夾，不是只複製單一檔案
   # segment 包含 rlog + 影片檔案（fcamera.hevc、ecamera.hevc 等）
   scp -r comma@192.168.x.x:/data/media/0/realdata/2024-01-01--12-00-00 C:\logs\
   ```

   **方法 B：使用 SSH 金鑰的 FTP 客戶端**
   - 使用 WinSCP 或 FileZilla（配置 SSH 金鑰認證）
   - 連接到 C3/C3X（IP：`192.168.x.x`）
   - 瀏覽到 `/data/media/0/realdata/`
   - 下載 segment 資料夾到本地磁碟

4. **執行應用程式**
   - 雙擊 `OpenpilotLogViewer.exe`

5. **首次設定：匯入訊號定義**
   - 前往 `工具 → 匯入訊號定義`
   - 這會從 `log.capnp`（FrogPilot 定義檔，相容 openpilot 0.9.7）匯入 cereal 訊號，從 DBC 檔案匯入 CAN 訊號
   - **必要檔案**：
     - `log.capnp`（主要 schema 檔案 - 來自 FrogPilot）
     - `car.capnp`、`legacy.capnp`、`custom.capnp`、`maptile.capnp`（依賴檔案 - 必須與 log.capnp 在同一目錄）
     - `data/dbc/` 資料夾中的 DBC 檔案
   - 匯入時只需選擇 `log.capnp`，其他 4 個依賴檔案會自動從相同位置載入
   - 點擊「開始匯入」並等待完成（約 30-60 秒）

   ⚠️ **何時需要重新匯入**：
   - 首次使用應用程式
   - 更新訊號定義檔後（log.capnp 或 DBC 檔案）
   - 使用不同 openpilot/FrogPilot 版本的記錄檔時

6. **匯入與分析 Segment**
   - 使用 `工具 → 匯入 Segment` 載入你的 rlog 檔案
   - 開始分析，享受同步影片播放！

   **重要：匯入後的檔案管理**：
   - ✅ **影片檔案**：必須保留在原位置（資料庫記錄了影片檔案路徑）
   - ✅ **rlog 檔案**：可以刪除以節省空間（資料已匯入資料庫）
   - ⚠️ 如果移動或刪除影片檔案，將無法播放影片（但資料圖表仍可正常使用）

### 開發者

1. **複製儲存庫**
   ```bash
   git clone https://github.com/yourusername/openpilot-log-viewer.git
   cd openpilot-log-viewer
   ```

2. **安裝依賴**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **從源碼執行**
   ```bash
   python main.py
   ```

4. **編譯 EXE（可選）**
   ```bash
   build_exe.bat
   ```
   詳細編譯說明請參閱 [README_BUILD.md](README_BUILD.md)。

## 功能特色

### 📊 資料分析
- **訊號瀏覽**：瀏覽 300+ cereal 訊號 + CAN 訊號
- **即時搜尋**：模糊搜尋，支援中英文翻譯
- **圖表視覺化**：使用 pyqtgraph 進行多訊號同步繪圖
- **自定義訊號**：使用 Python 運算式建立計算訊號（例如：速度轉換、G 值）
- **資料匯出**：匯出為 CSV/Parquet 供進一步分析

### 🎥 影片播放
- **同步播放**：影片時間軸與資料圖表同步
- **多鏡頭支援**：fcamera、ecamera、dcamera
- **影格控制**：播放、暫停、跳轉、逐影格瀏覽

### 🗄️ 資料庫管理
- **SQLite 儲存**：高效的本地資料庫
- **快速存取**：瀏覽先前匯入的 segment
- **DBC 支援**：匯入自訂 DBC 檔案進行 CAN 訊號解析

### 🌍 多語言
- **English** 和 **繁體中文**
- 自動翻譯訊號名稱和描述
- 即時切換語言

## 系統需求

- **作業系統**：Windows 10/11（64 位元）
- **記憶體**：最少 4GB，建議 8GB 以上
- **磁碟空間**：應用程式 100MB + 記錄檔空間
- **Python**：一般使用者不需要（已包含在 exe 中）

## 檔案結構

```
openpilot-log-viewer-release/
├── README.md                    # 英文說明
├── README_zh-TW.md              # 本文件（中文說明）
├── README_BUILD.md              # 開發者編譯說明
│
├── release/
│   └── v1.0/                    # 可直接執行的發行版
│       ├── OpenpilotLogViewer.exe
│       ├── _internal/           # PyInstaller 依賴庫
│       ├── src/                 # Python 源碼（可修改）
│       ├── tools/               # 工具程式（可修改）
│       ├── data/                # DBC 檔案、翻譯（可修改）
│       ├── i18n/                # UI 翻譯（可修改）
│       └── *.capnp              # Schema 檔案
│
└── （源碼檔案）                  # 完整源碼供開發者使用
```

## 工作流程範例

### 傳統方式（plotjuggler/cabana）
```
1. 使用 C3/C3X 駕駛
2. 等待上傳到 connect.comma.ai（自動，可能需要數小時）
3. 從 connect.comma.ai 下載到本地機器
4. 安裝 Linux/WSL 環境
5. 設定 plotjuggler 依賴
6. 終於可以分析記錄檔
```

### 使用 openpilot Windows 查看器
```
1. 使用 C3/C3X 駕駛
2. 透過 SSH/FTP 直接複製記錄檔（幾分鐘）
3. 雙擊 OpenpilotLogViewer.exe
4. 立即開始分析！
```

**節省時間**：數小時 → 數分鐘
**隱私保護**：雲端上傳 → 僅限本地

## 常見問題

### Q：我需要上傳記錄檔到 connect.comma.ai 嗎？
**A**：不需要！此工具完全離線運作。透過 SSH/FTP 直接從 C3/C3X 複製記錄檔即可。

### Q：我可以修改源碼嗎？
**A**：可以！`src/`、`tools/`、`data/` 和 `i18n/` 資料夾包含可編輯的 Python 源碼。直接修改即可，無需重新編譯 exe。詳見 [README_BUILD.md](README_BUILD.md)。

### Q：這會取代 plotjuggler/cabana 嗎？
**A**：不完全是。此工具專注於 Windows 使用者和本地分析。plotjuggler/cabana 在 Linux 生態系統中有其優勢。

### Q：支援什麼記錄檔格式？
**A**：目前僅支援 openpilot rlog 格式（未壓縮的 `.rlog` 檔案）。記錄檔應包含 cereal 訊息。相容 openpilot 0.9.7 和 FrogPilot。

注意：不支援 `.bz2` 壓縮檔。請先解壓縮：`bzip2 -d rlog.bz2`

### Q：我需要重新匯入訊號定義嗎？
**A**：是的，以下情況需要重新匯入：
- 首次使用應用程式
- 更新訊號定義檔後（log.capnp 或 DBC 檔案）
- 切換不同 openpilot/FrogPilot 版本時

確保所有 5 個 capnp 檔案（`log.capnp`、`car.capnp`、`legacy.capnp`、`custom.capnp`、`maptile.capnp`）都在同一目錄中。匯入時只需選擇 `log.capnp`，其他 4 個檔案會自動從相同位置載入。

### Q：這個工具相容哪個 openpilot 版本？
**A**：本發行版使用 FrogPilot 的訊號定義（基於 openpilot 0.9.7）。應該可以處理大多數 openpilot 0.9.x 和 FrogPilot 的記錄檔。

### Q：如何設定 C3/C3X SSH 存取？
**A**：現代 comma 設備需要 SSH 金鑰認證。請搜尋「comma 3 SSH key 設定」或「comma 3X SSH 存取 GitHub key」以獲取詳細指南。

### Q：我可以使用自訂 DBC 檔案嗎？
**A**：可以！將 DBC 檔案放在 `data/dbc/` 資料夾中，然後使用 `工具 → 匯入訊號定義` 匯入。

### Q：如何新增更多 CAN 訊號翻譯？
**A**：編輯 `data/translations/signals_zh_TW.json` 並重新啟動應用程式。無需重新編譯！

## 疑難排解

### 「無法連接到資料庫」
- 確保應用程式目錄有寫入權限
- 檢查 `oplog.db` 是否被其他程式開啟

### 「匯入 segment 失敗」
- 驗證 rlog 檔案沒有損壞
- 檢查是否已匯入 DBC 檔案（用於 CAN 訊號解析）
- 查看 `oplog_viewer.log` 以獲取詳細錯誤訊息

### 「影片播放無法運作」
- 確保 segment 包含影片檔案（例如 `fcamera.hevc`）
- 安裝最新的顯示卡驅動程式
- 檢查 av（PyAV）函式庫是否正確安裝（開發者）

## 授權

本專案基於 openpilot 並遵循其開源授權。

## 致謝

- **openpilot** 團隊提供的優秀自動駕駛平台
- **FrogPilot** ([FrogAi/FrogPilot](https://github.com/FrogAi/FrogPilot)) - 訊號定義基於 FrogPilot
- **comma.ai** 提供 C3/C3X 設備和記錄基礎設施
- **PyQt6** GUI 框架
- **pyqtgraph** 高效能繪圖庫

## 貢獻

歡迎貢獻！請隨時提交 issue 或 pull request。

## 相關連結

- [openpilot](https://github.com/commaai/openpilot) - openpilot 0.9.7
- [FrogPilot](https://github.com/FrogAi/FrogPilot) - 訊號定義來源
- [comma.ai](https://comma.ai/)
- [編譯說明](README_BUILD.md)

---

**注意**：這是非官方的社群工具，與 comma.ai 和 FrogPilot 無關。使用 openpilot 時請務必遵守當地法律。
