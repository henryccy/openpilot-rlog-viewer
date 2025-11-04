# -*- coding: utf-8 -*-
"""
檢查資料庫中缺少中文翻譯的訊號
Check Missing Translations in Database
"""

import sys
import os
import io

# 設定標準輸出為 UTF-8 編碼
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_missing_translations(db_path='data/oplog.db'):
    """檢查缺少翻譯的訊號"""

    if not os.path.exists(db_path):
        print(f"錯誤：資料庫檔案不存在: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    if not conn:
        print(f"錯誤：無法連接資料庫: {db_path}")
        return

    try:
        cursor = conn.cursor()

        print("=" * 80)
        print("訊號翻譯檢查報告")
        print("=" * 80)
        print()

        # ================================================================
        # 檢查 Cereal 訊號
        # ================================================================
        print("【Cereal 訊號】")
        print("-" * 80)

        # 總數
        cursor.execute("SELECT COUNT(*) FROM cereal_signal_definitions")
        total_cereal = cursor.fetchone()[0]

        # 缺少 name_cn
        cursor.execute("""
            SELECT COUNT(*) FROM cereal_signal_definitions
            WHERE name_cn IS NULL OR name_cn = ''
        """)
        missing_name_cn = cursor.fetchone()[0]

        # 缺少 description_cn
        cursor.execute("""
            SELECT COUNT(*) FROM cereal_signal_definitions
            WHERE description_cn IS NULL OR description_cn = ''
        """)
        missing_desc_cn = cursor.fetchone()[0]

        # 缺少 unit_cn (但有 unit 的)
        cursor.execute("""
            SELECT COUNT(*) FROM cereal_signal_definitions
            WHERE (unit IS NOT NULL AND unit != '')
            AND (unit_cn IS NULL OR unit_cn = '')
        """)
        missing_unit_cn = cursor.fetchone()[0]

        print(f"總計: {total_cereal} 個訊號")
        print(f"缺少中文名稱 (name_cn): {missing_name_cn} 個 ({missing_name_cn/total_cereal*100:.1f}%)")
        print(f"缺少中文描述 (description_cn): {missing_desc_cn} 個 ({missing_desc_cn/total_cereal*100:.1f}%)")
        print(f"缺少中文單位 (unit_cn): {missing_unit_cn} 個")
        print()

        # 列出缺少翻譯的訊號（前 20 個）
        cursor.execute("""
            SELECT full_name, message_type, signal_name, unit
            FROM cereal_signal_definitions
            WHERE name_cn IS NULL OR name_cn = ''
            ORDER BY message_type, signal_name
            LIMIT 20
        """)

        missing_signals = cursor.fetchall()
        if missing_signals:
            print("缺少翻譯的訊號範例（前 20 個）:")
            for row in missing_signals:
                full_name, msg_type, sig_name, unit = row
                unit_str = f" ({unit})" if unit else ""
                print(f"  - {full_name}{unit_str}")
        print()

        # ================================================================
        # 檢查 CAN 訊號
        # ================================================================
        print("【CAN 訊號】")
        print("-" * 80)

        # 總數
        cursor.execute("SELECT COUNT(*) FROM can_signal_definitions")
        total_can = cursor.fetchone()[0]

        # 缺少 signal_name_cn
        cursor.execute("""
            SELECT COUNT(*) FROM can_signal_definitions
            WHERE signal_name_cn IS NULL OR signal_name_cn = ''
        """)
        missing_can_name = cursor.fetchone()[0]

        # 缺少 description_cn
        cursor.execute("""
            SELECT COUNT(*) FROM can_signal_definitions
            WHERE description_cn IS NULL OR description_cn = ''
        """)
        missing_can_desc = cursor.fetchone()[0]

        # 缺少 unit_cn (但有 unit 的)
        cursor.execute("""
            SELECT COUNT(*) FROM can_signal_definitions
            WHERE (unit IS NOT NULL AND unit != '')
            AND (unit_cn IS NULL OR unit_cn = '')
        """)
        missing_can_unit = cursor.fetchone()[0]

        print(f"總計: {total_can} 個訊號")
        print(f"缺少中文名稱 (signal_name_cn): {missing_can_name} 個 ({missing_can_name/total_can*100:.1f}%)")
        print(f"缺少中文描述 (description_cn): {missing_can_desc} 個 ({missing_can_desc/total_can*100:.1f}%)")
        print(f"缺少中文單位 (unit_cn): {missing_can_unit} 個")
        print()

        # 列出缺少翻譯的訊號（前 20 個）
        cursor.execute("""
            SELECT full_name, signal_name, message_name, unit
            FROM can_signal_definitions
            WHERE signal_name_cn IS NULL OR signal_name_cn = ''
            ORDER BY can_id, signal_name
            LIMIT 20
        """)

        missing_can_signals = cursor.fetchall()
        if missing_can_signals:
            print("缺少翻譯的訊號範例（前 20 個）:")
            for row in missing_can_signals:
                full_name, sig_name, msg_name, unit = row
                unit_str = f" ({unit})" if unit else ""
                print(f"  - {sig_name} [{msg_name}]{unit_str}")
        print()

        # ================================================================
        # 匯出缺少翻譯的訊號到檔案
        # ================================================================
        print("【匯出訊號清單】")
        print("-" * 80)

        # 匯出 Cereal 訊號
        output_dir = 'data/translations'
        os.makedirs(output_dir, exist_ok=True)

        cereal_output = os.path.join(output_dir, 'missing_cereal_signals.txt')
        cursor.execute("""
            SELECT full_name, message_type, signal_name, data_type, unit
            FROM cereal_signal_definitions
            WHERE name_cn IS NULL OR name_cn = ''
            ORDER BY message_type, signal_name
        """)

        with open(cereal_output, 'w', encoding='utf-8') as f:
            f.write("# Cereal 訊號缺少翻譯清單\n")
            f.write(f"# 總計: {missing_name_cn} 個\n")
            f.write("# 格式: 完整名稱 | 訊息類型 | 訊號名稱 | 資料型態 | 單位\n\n")
            for row in cursor.fetchall():
                f.write(" | ".join([str(x) if x else "" for x in row]) + "\n")

        print(f"✓ Cereal 訊號清單已匯出: {cereal_output}")

        # 匯出 CAN 訊號
        can_output = os.path.join(output_dir, 'missing_can_signals.txt')
        cursor.execute("""
            SELECT full_name, can_id_hex, message_name, signal_name, unit
            FROM can_signal_definitions
            WHERE signal_name_cn IS NULL OR signal_name_cn = ''
            ORDER BY can_id, signal_name
        """)

        with open(can_output, 'w', encoding='utf-8') as f:
            f.write("# CAN 訊號缺少翻譯清單\n")
            f.write(f"# 總計: {missing_can_name} 個\n")
            f.write("# 格式: 完整名稱 | CAN ID | 訊息名稱 | 訊號名稱 | 單位\n\n")
            for row in cursor.fetchall():
                f.write(" | ".join([str(x) if x else "" for x in row]) + "\n")

        print(f"✓ CAN 訊號清單已匯出: {can_output}")
        print()

        # ================================================================
        # 統計總結
        # ================================================================
        print("【總結】")
        print("-" * 80)
        total_missing = missing_name_cn + missing_can_name
        total_signals = total_cereal + total_can
        print(f"總訊號數: {total_signals} 個")
        print(f"缺少中文名稱: {total_missing} 個 ({total_missing/total_signals*100:.1f}%)")
        print(f"")
        print(f"下一步:")
        print(f"1. 查看匯出的訊號清單")
        print(f"2. 使用 AI 搜尋並翻譯")
        print(f"3. 編輯 data/translations/cereal_translations.json 和 can_translations.json")
        print(f"4. 執行 python tools/apply_translations.py 更新資料庫")
        print("=" * 80)

    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='檢查缺少翻譯的訊號')
    parser.add_argument('--db', default='data/oplog.db', help='資料庫路徑')

    args = parser.parse_args()

    check_missing_translations(args.db)
