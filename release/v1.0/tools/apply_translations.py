# -*- coding: utf-8 -*-
"""
應用翻譯到資料庫和 Python 字典檔案
Apply Translations to Database and Python Dictionary Files
"""

import sys
import os
import json
import io
import sqlite3

# 設定標準輸出為 UTF-8 編碼
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_translation_json(json_path):
    """載入翻譯 JSON 檔案"""
    if not os.path.exists(json_path):
        logger.warning(f"翻譯檔案不存在: {json_path}")
        return {}

    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def apply_cereal_translations(conn, translations):
    """應用 Cereal 訊號翻譯到資料庫"""
    cursor = conn.cursor()
    updated_count = 0

    for signal_name, trans in translations.items():
        # 跳過註解欄位（如 _README, _說明, _NOTE 等）
        if signal_name.startswith('_'):
            continue

        # 跳過非字典類型的值
        if not isinstance(trans, dict):
            continue

        try:
            # 更新資料庫
            cursor.execute("""
                UPDATE cereal_signal_definitions
                SET name_cn = ?,
                    description_cn = ?,
                    unit_cn = ?
                WHERE signal_name = ? OR full_name = ?
            """, (
                trans.get('name_cn', ''),
                trans.get('description_cn', ''),
                trans.get('unit_cn', ''),
                signal_name,
                signal_name
            ))

            if cursor.rowcount > 0:
                updated_count += cursor.rowcount
                logger.info(f"✓ 更新 Cereal 訊號: {signal_name} -> {trans.get('name_cn', '')}")

        except Exception as e:
            logger.error(f"更新失敗 {signal_name}: {e}")

    conn.commit()
    return updated_count


def apply_can_translations(conn, translations):
    """應用 CAN 訊號翻譯到資料庫"""
    cursor = conn.cursor()
    updated_count = 0

    for signal_name, trans in translations.items():
        # 跳過註解欄位（如 _README, _說明, _NOTE 等）
        if signal_name.startswith('_'):
            continue

        # 跳過非字典類型的值
        if not isinstance(trans, dict):
            continue

        try:
            # 更新資料庫（可能匹配 signal_name 或 full_name）
            cursor.execute("""
                UPDATE can_signal_definitions
                SET signal_name_cn = ?,
                    description_cn = ?,
                    unit_cn = ?
                WHERE signal_name = ? OR full_name LIKE ?
            """, (
                trans.get('name_cn', ''),
                trans.get('description_cn', ''),
                trans.get('unit_cn', ''),
                signal_name,
                f"%{signal_name}%"
            ))

            if cursor.rowcount > 0:
                updated_count += cursor.rowcount
                logger.info(f"✓ 更新 CAN 訊號: {signal_name} -> {trans.get('name_cn', '')}")

        except Exception as e:
            logger.error(f"更新失敗 {signal_name}: {e}")

    conn.commit()
    return updated_count


def update_python_dict_cereal(translations, py_file_path):
    """更新 Python 字典檔案 - Cereal 訊號"""
    try:
        with open(py_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 找到 cereal_translations 字典的位置
        dict_start = content.find('self.cereal_translations = {')
        if dict_start == -1:
            logger.error(f"找不到 cereal_translations 字典: {py_file_path}")
            return False

        # 找到字典的結束位置
        brace_count = 0
        dict_end = dict_start
        for i, char in enumerate(content[dict_start:], dict_start):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    dict_end = i + 1
                    break

        # 生成新的字典內容
        new_dict = "self.cereal_translations = {\n"

        # 按字母順序排序
        sorted_keys = sorted(translations.keys())

        for i, key in enumerate(sorted_keys):
            # 跳過註解欄位
            if key.startswith('_'):
                continue

            trans = translations[key]

            # 跳過非字典類型的值
            if not isinstance(trans, dict):
                continue

            name_cn = trans.get('name_cn', '')
            if name_cn:  # 只加入有翻譯的
                new_dict += f"            '{key}': '{name_cn}',\n"

        new_dict += "        }"

        # 替換內容
        new_content = content[:dict_start] + new_dict + content[dict_end:]

        # 寫回檔案
        with open(py_file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        logger.info(f"✓ 更新 Python 字典: {py_file_path}")
        return True

    except Exception as e:
        logger.error(f"更新 Python 字典失敗: {e}")
        return False


def update_python_dict_can(translations, py_file_path):
    """更新 Python 字典檔案 - CAN 訊號"""
    try:
        with open(py_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 找到 TRANSLATIONS 字典的位置
        dict_start = content.find('TRANSLATIONS = {')
        if dict_start == -1:
            logger.error(f"找不到 TRANSLATIONS 字典: {py_file_path}")
            return False

        # 找到字典的結束位置
        brace_count = 0
        dict_end = dict_start
        for i, char in enumerate(content[dict_start:], dict_start):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    dict_end = i + 1
                    break

        # 生成新的字典內容
        new_dict = "TRANSLATIONS = {\n"

        # 按字母順序排序
        sorted_keys = sorted(translations.keys())

        # 分類顯示（保留原有註解結構）
        categories = {}
        for key in sorted_keys:
            # 跳過註解欄位
            if key.startswith('_'):
                continue

            trans = translations[key]

            # 跳過非字典類型的值
            if not isinstance(trans, dict):
                continue

            name_cn = trans.get('name_cn', '')
            if name_cn:
                # 嘗試從 description_cn 提取分類
                category = trans.get('category', '其他')
                if category not in categories:
                    categories[category] = []
                categories[category].append((key, name_cn))

        # 輸出分類
        for category, items in sorted(categories.items()):
            new_dict += f"        # {category}\n"
            for key, name_cn in items:
                new_dict += f"        '{key}': '{name_cn}',\n"
            new_dict += "\n"

        new_dict += "    }"

        # 替換內容
        new_content = content[:dict_start] + new_dict + content[dict_end:]

        # 寫回檔案
        with open(py_file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        logger.info(f"✓ 更新 Python 字典: {py_file_path}")
        return True

    except Exception as e:
        logger.error(f"更新 Python 字典失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def apply_all_translations(db_path='data/oplog.db'):
    """應用所有翻譯"""

    print("=" * 80)
    print("應用翻譯到資料庫和 Python 字典")
    print("=" * 80)
    print()

    # 載入翻譯檔案
    cereal_trans_path = 'data/translations/cereal_translations.json'
    can_trans_path = 'data/translations/can_translations.json'

    cereal_translations = load_translation_json(cereal_trans_path)
    can_translations = load_translation_json(can_trans_path)

    print(f"載入 Cereal 翻譯: {len(cereal_translations)} 個")
    print(f"載入 CAN 翻譯: {len(can_translations)} 個")
    print()

    # 連接資料庫
    if not os.path.exists(db_path):
        print(f"錯誤：資料庫檔案不存在: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    if not conn:
        print(f"錯誤：無法連接資料庫: {db_path}")
        return

    try:
        # 應用 Cereal 翻譯到資料庫
        print("【更新資料庫】")
        print("-" * 80)
        cereal_count = apply_cereal_translations(conn, cereal_translations)
        print(f"✓ Cereal 訊號: 更新 {cereal_count} 筆")

        can_count = apply_can_translations(conn, can_translations)
        print(f"✓ CAN 訊號: 更新 {can_count} 筆")
        print()

        # 更新 Python 字典檔案
        print("【更新 Python 字典檔案】")
        print("-" * 80)

        cereal_py = 'tools/import_signal_definitions_sqlite.py'
        if os.path.exists(cereal_py):
            update_python_dict_cereal(cereal_translations, cereal_py)
        else:
            logger.warning(f"找不到檔案: {cereal_py}")

        can_py = 'src/core/dbc_parser.py'
        if os.path.exists(can_py):
            update_python_dict_can(can_translations, can_py)
        else:
            logger.warning(f"找不到檔案: {can_py}")

        print()
        print("=" * 80)
        print("完成！")
        print(f"資料庫更新: {cereal_count + can_count} 筆訊號")
        print("Python 字典已更新")
        print("=" * 80)

    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='應用翻譯到資料庫和 Python 字典')
    parser.add_argument('--db', default='data/oplog.db', help='資料庫路徑')

    args = parser.parse_args()

    apply_all_translations(args.db)
