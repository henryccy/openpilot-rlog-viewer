# Translation Files / 翻譯檔案

This directory contains translation files for the openpilot Log Viewer application.

本目錄包含 openpilot Log Viewer 應用程式的翻譯檔案。

## File Structure / 檔案結構

```
i18n/
├── README.md           # This file / 本檔案
├── zh_TW.ts            # Traditional Chinese translation source (XML)
├── zh_TW.qm            # Traditional Chinese compiled translation (binary)
├── en_US.ts            # English translation source (XML)
└── en_US.qm            # English compiled translation (binary)
```

## Supported Languages / 支援的語言

- **zh_TW**: 繁體中文 (Traditional Chinese)
- **en_US**: English (United States)

## Working with Translations / 翻譯工作流程

### 1. Extract Translatable Strings / 提取可翻譯字串

Extract all strings marked with `tr()` from source code:

從源代碼提取所有標記為 `tr()` 的字串：

```bash
# Extract for all languages / 為所有語言提取
python tools/update_translations.py extract

# Extract for specific language / 為特定語言提取
python tools/update_translations.py extract -l zh_TW
```

### 2. Translate Strings / 翻譯字串

#### Method 1: Use Qt Linguist (Recommended) / 方法一：使用 Qt Linguist（推薦）

Qt Linguist is a graphical tool for editing translation files:

Qt Linguist 是用於編輯翻譯檔案的圖形工具：

```bash
# Open translation file in Qt Linguist
linguist i18n/zh_TW.ts
```

**Qt Linguist Features** / **Qt Linguist 功能**：
- Context view / 上下文檢視
- Translation suggestions / 翻譯建議
- Validation / 驗證
- Search and replace / 搜尋與取代

**Download Qt Linguist** / **下載 Qt Linguist**：
- Windows/macOS/Linux: https://www.qt.io/download

#### Method 2: Edit XML Directly / 方法二：直接編輯 XML

Translation files (.ts) are XML files that can be edited manually:

翻譯檔案（.ts）是 XML 檔案，可以手動編輯：

```xml
<message>
    <source>Open Route</source>
    <translation>開啟路徑</translation>
</message>

<message>
    <source>Import Progress</source>
    <translation type="unfinished"></translation>
</message>
```

**Status Attributes** / **狀態屬性**：
- No attribute: Translated / 無屬性：已翻譯
- `type="unfinished"`: Translation incomplete / 翻譯未完成
- `type="obsolete"`: No longer used / 不再使用

### 3. Compile Translations / 編譯翻譯

Compile .ts files to .qm (binary format) for application use:

將 .ts 檔案編譯為 .qm（二進位格式）供應用程式使用：

```bash
# Compile all languages / 編譯所有語言
python tools/update_translations.py compile

# Compile specific language / 編譯特定語言
python tools/update_translations.py compile -l zh_TW
```

### 4. Update (Extract + Compile) / 更新（提取 + 編譯）

Shortcut to extract and compile in one step:

一步完成提取和編譯的快捷方式：

```bash
python tools/update_translations.py update
```

### 5. Check Statistics / 檢查統計

View translation progress:

檢視翻譯進度：

```bash
python tools/update_translations.py stats
```

## Translation Guidelines / 翻譯指南

### General Principles / 一般原則

1. **Consistency** / **一致性**
   - Use consistent terminology throughout
   - 在整個應用程式中使用一致的術語

2. **Clarity** / **清晰度**
   - Keep translations clear and concise
   - 保持翻譯清晰簡潔

3. **Context** / **上下文**
   - Consider the UI context when translating
   - 翻譯時考慮 UI 上下文

4. **Length** / **長度**
   - Try to keep similar length to original (for UI layout)
   - 盡量保持與原文相似的長度（為了 UI 佈局）

### Common Terms / 常用術語

| English | 繁體中文 | Notes / 備註 |
|---------|---------|--------------|
| Route | 路徑 | openpilot route / openpilot 路徑 |
| Segment | 片段 | Route segment / 路徑片段 |
| Signal | 訊號 | Data signal / 資料訊號 |
| Chart | 圖表 | Data visualization / 資料視覺化 |
| Log | 日誌 | Log message / 日誌訊息 |
| Import | 匯入 | Data import / 資料匯入 |
| Export | 匯出 | Data export / 資料匯出 |
| Database | 資料庫 | - |
| Settings | 設定 | Application settings / 應用程式設定 |
| Loading | 載入中 | Loading state / 載入狀態 |

### Button Labels / 按鈕標籤

| English | 繁體中文 |
|---------|---------|
| OK | 確定 |
| Cancel | 取消 |
| Apply | 套用 |
| Close | 關閉 |
| Save | 儲存 |
| Load | 載入 |
| Delete | 刪除 |
| Edit | 編輯 |
| Add | 新增 |
| Remove | 移除 |
| Browse | 瀏覽 |
| Search | 搜尋 |

## Adding a New Language / 新增語言

To add support for a new language:

若要新增對新語言的支援：

1. Create new .ts file:
   ```bash
   python tools/update_translations.py extract -l xx_YY
   ```
   Replace `xx_YY` with language code (e.g., `ja_JP` for Japanese)

2. Add language to `TranslationManager.SUPPORTED_LANGUAGES`:
   ```python
   SUPPORTED_LANGUAGES = {
       'zh_TW': '繁體中文 (Traditional Chinese)',
       'en_US': 'English',
       'xx_YY': 'Your Language'  # Add here
   }
   ```

3. Translate strings using Qt Linguist or text editor

4. Compile translation:
   ```bash
   python tools/update_translations.py compile -l xx_YY
   ```

5. Test in application

## Testing Translations / 測試翻譯

1. Compile translations:
   ```bash
   python tools/update_translations.py compile
   ```

2. Run application:
   ```bash
   python main.py
   ```

3. Go to **Settings → Language** / 前往**設定 → 語言**

4. Select language and restart application / 選擇語言並重啟應用程式

## Troubleshooting / 疑難排解

### Translation Not Showing / 翻譯未顯示

1. Make sure .qm file is compiled:
   ```bash
   python tools/update_translations.py compile
   ```

2. Check if language is selected in settings

3. Restart application

### Missing Strings / 缺少字串

1. Extract strings from source:
   ```bash
   python tools/update_translations.py extract
   ```

2. Check if strings are marked with `tr()` in source code

3. Recompile after adding translations

### Encoding Issues / 編碼問題

- All .ts files should be UTF-8 encoded
- Use Qt Linguist to avoid encoding problems
- Check file encoding if editing manually

## Resources / 資源

### Qt Documentation / Qt 文檔
- Internationalization with Qt: https://doc.qt.io/qt-6/internationalization.html
- Qt Linguist Manual: https://doc.qt.io/qt-6/qtlinguist-index.html

### Tools / 工具
- Qt Linguist: Graphical translation editor / 圖形翻譯編輯器
- pylupdate6: Extract strings from Python code / 從 Python 代碼提取字串
- lrelease: Compile .ts to .qm files / 編譯 .ts 為 .qm 檔案

## Contributing / 貢獻

Contributions to translations are welcome! / 歡迎貢獻翻譯！

1. Fork the repository / Fork 儲存庫
2. Add/update translations / 新增/更新翻譯
3. Test your changes / 測試您的變更
4. Submit a pull request / 提交 pull request

See [CONTRIBUTING.md](../CONTRIBUTING.md) for more details.

---

**Note** / **備註**: .qm files are compiled binary files and should not be edited directly. Always edit .ts files and then compile.

.qm 檔案是已編譯的二進位檔案，不應直接編輯。請始終編輯 .ts 檔案，然後進行編譯。
