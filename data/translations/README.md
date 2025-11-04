# 訊號翻譯補全 - 快速使用指南

## 🚀 快速開始

### 步驟 1：檢查缺少翻譯的訊號

```bash
python tools/check_missing_translations.py
```

這會生成兩個清單檔案：
- `data/translations/missing_cereal_signals.txt` - 缺少翻譯的 Cereal 訊號
- `data/translations/missing_can_signals.txt` - 缺少翻譯的 CAN 訊號

### 步驟 2：編輯翻譯 JSON 檔案

編輯以下兩個檔案，加入新的翻譯：
- `data/translations/cereal_translations.json`
- `data/translations/can_translations.json`

**JSON 格式範例**：
```json
{
  "訊號名稱": {
    "name_cn": "中文名稱",
    "description_cn": "詳細描述",
    "unit": "英文單位",
    "unit_cn": "中文單位",
    "category": "分類（CAN 訊號用）"
  }
}
```

### 步驟 3：應用翻譯

```bash
python tools/apply_translations.py
```

這會自動：
1. ✅ 更新資料庫中的中文欄位
2. ✅ 更新 Python 字典檔案：
   - `tools/import_signal_definitions_sqlite.py`
   - `src/core/dbc_parser.py`

## 📋 使用 AI 協助翻譯

詳細說明請參閱：`訊號翻譯補全指南.md`

### AI 提示詞範本

```
請幫我翻譯以下汽車/自動駕駛相關訊號為繁體中文：

訊號: [訊號名稱]
類型: [Cereal / CAN]
原始語言: [英文 / 德文]

請提供：
1. 專業的中文名稱（不超過 10 字）
2. 簡短說明（1-2 句話）
3. 單位的中文翻譯（如果有）

這是用於 openpilot 自動駕駛系統的資料分析工具。
```

## 📁 檔案說明

| 檔案 | 說明 |
|------|------|
| `cereal_translations.json` | Cereal 訊號翻譯（手動編輯） |
| `can_translations.json` | CAN 訊號翻譯（手動編輯） |
| `missing_cereal_signals.txt` | 缺少翻譯的 Cereal 訊號清單（自動生成） |
| `missing_can_signals.txt` | 缺少翻譯的 CAN 訊號清單（自動生成） |
| `README.md` | 本說明檔 |

## 🎯 常見問題

### Q: 如何搜尋德文汽車術語的中文翻譯？

A: 建議搜尋關鍵字：
- "[德文術語] automotive Chinese"
- "[德文術語] 汽車 中文"
- 參考 VW/Audi/BMW 中文技術文件

### Q: 翻譯後需要重新匯入訊號定義嗎？

A: 不需要！執行 `apply_translations.py` 會直接更新現有資料庫和程式碼。

### Q: 如何確認翻譯已經套用？

A: 重新啟動程式，查看訊號選擇器中的 tooltip 應該會顯示中文。

## 📝 更新記錄範本

每次更新翻譯後，請在 `訊號翻譯補全指南.md` 底部記錄：

```markdown
### 2024-10-30 - [您的名字]
- 新增翻譯：50 個 Cereal 訊號
- 新增翻譯：100 個 CAN 訊號
- 修正翻譯：vEgo - 速度 → 車速
```

---

**詳細文檔**: 請參閱 `訊號翻譯補全指南.md`
