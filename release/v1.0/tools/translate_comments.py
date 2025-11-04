# -*- coding: utf-8 -*-
"""
Batch translate Chinese comments to English in Python files
批量將 Python 檔案中的中文註解翻譯為英文
"""
import re
from pathlib import Path

# Translation dictionary for common terms
TRANSLATIONS = {
    # Docstrings
    "主視窗": "Main Window",
    "訊號選擇器": "Signal Selector",
    "圖表區元件": "Chart Widget",
    "資料表區元件": "Data Table Widget",
    "影片播放器": "Video Player",
    "資料庫管理器": "Database Manager",
    "訊號計算引擎": "Signal Calculator",
    "翻譯管理器": "Translation Manager",

    # Common method descriptions
    "建立 UI": "Setup UI",
    "初始化": "Initialize",
    "設定": "Set/Configure",
    "載入": "Load",
    "儲存": "Save",
    "更新": "Update",
    "刪除": "Delete",
    "開啟": "Open",
    "關閉": "Close",
    "切換": "Toggle",
    "顯示": "Show/Display",
    "隱藏": "Hide",

    # UI Elements
    "選單列": "Menu bar",
    "狀態列": "Status bar",
    "工具列": "Toolbar",
    "對話框": "Dialog",
    "按鈕": "Button",
    "標籤": "Label",
    "輸入框": "Input field",
    "下拉選單": "Dropdown menu",
    "核取方塊": "Checkbox",
    "樹狀結構": "Tree structure",

    # Database
    "資料庫": "Database",
    "連接": "Connection/Connect",
    "查詢": "Query",
    "插入": "Insert",
    "刪除": "Delete",
    "資料表": "Table",

    # Signals
    "訊號": "Signal",
    "自訂計算訊號": "Custom calculated signal",
    "選中": "Selected",
    "勾選": "Checked",

    # Video
    "影片": "Video",
    "播放": "Play",
    "暫停": "Pause",
    "幀": "Frame",

    # Time
    "時間": "Time",
    "秒": "second(s)",
    "分鐘": "minute(s)",

    # Common actions
    "管理": "Manage",
    "編輯": "Edit",
    "瀏覽": "Browse",
    "匯入": "Import",
    "匯出": "Export",
    "重置": "Reset",
    "清除": "Clear",
    "搜尋": "Search",
    "篩選": "Filter",

    # Status
    "成功": "Success",
    "失敗": "Failed",
    "錯誤": "Error",
    "警告": "Warning",
    "資訊": "Information",

    # Common phrases
    "取得": "Get",
    "返回": "Return",
    "參數": "Parameter/Argument",
    "範例": "Example",
    "注意": "Note",
    "說明": "Description",
}

def translate_docstring(docstring: str) -> str:
    """Translate Chinese docstring to English"""
    # Simple keyword-based translation
    result = docstring
    for zh, en in TRANSLATIONS.items():
        result = result.replace(zh, en)
    return result

def process_file(filepath: Path):
    """Process a single Python file"""
    print(f"Processing: {filepath}")

    content = filepath.read_text(encoding='utf-8')
    original = content

    # Pattern for docstrings in triple quotes
    pattern = r'"""([^"]+)"""'

    def replace_docstring(match):
        orig_text = match.group(1)
        # Check if contains Chinese
        if re.search(r'[\u4e00-\u9fff]', orig_text):
            translated = translate_docstring(orig_text)
            return f'"""{translated}"""'
        return match.group(0)

    content = re.sub(pattern, replace_docstring, content, flags=re.MULTILINE)

    if content != original:
        filepath.write_text(content, encoding='utf-8')
        print(f"  ✓ Updated")
        return True
    else:
        print(f"  - No changes")
        return False

def main():
    """Main function"""
    src_path = Path(__file__).parent.parent / 'src'

    # Find all Python files
    py_files = list(src_path.rglob('*.py'))

    print(f"Found {len(py_files)} Python files\n")

    updated_count = 0
    for filepath in py_files:
        if process_file(filepath):
            updated_count += 1

    print(f"\n完成！更新了 {updated_count} 個檔案")

if __name__ == '__main__':
    main()
