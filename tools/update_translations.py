# -*- coding: utf-8 -*-
"""
更新翻譯檔案工具
Translation Update Tool

用於提取和編譯翻譯檔案
"""
import subprocess
import sys
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TranslationUpdater:
    """翻譯檔案更新器"""

    def __init__(self, project_root: Path = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent
        self.project_root = project_root
        self.i18n_dir = project_root / 'i18n'
        self.src_dir = project_root / 'src'

        # 確保 i18n 目錄存在
        self.i18n_dir.mkdir(exist_ok=True)

    def extract_strings(self, language_code: str = None):
        """
        從源代碼提取可翻譯的字串

        Args:
            language_code: 語言代碼，如 'zh_TW'，如果為 None 則處理所有語言
        """
        if language_code:
            languages = [language_code]
        else:
            languages = ['zh_TW', 'en_US']

        for lang in languages:
            ts_file = self.i18n_dir / f"{lang}.ts"

            # 收集所有 Python 檔案
            py_files = list(self.src_dir.rglob('*.py'))

            if not py_files:
                logger.warning(f"No Python files found in {self.src_dir}")
                continue

            # 執行 pylupdate6
            try:
                cmd = ['pylupdate6'] + [str(f) for f in py_files] + ['-ts', str(ts_file)]
                logger.info(f"Extracting strings for {lang}...")
                logger.info(f"Command: {' '.join(cmd)}")

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8'
                )

                if result.returncode == 0:
                    logger.info(f"✓ Successfully extracted to {ts_file}")
                    if result.stdout:
                        logger.info(result.stdout)
                else:
                    logger.error(f"✗ Failed to extract strings for {lang}")
                    logger.error(result.stderr)

            except FileNotFoundError:
                logger.error(
                    "pylupdate6 not found. Please install PyQt6 development tools:\n"
                    "pip install PyQt6-tools"
                )
                sys.exit(1)
            except Exception as e:
                logger.error(f"Error extracting strings: {e}")

    def compile_translations(self, language_code: str = None):
        """
        編譯翻譯檔案 (.ts -> .qm)

        Args:
            language_code: 語言代碼，如 'zh_TW'，如果為 None 則編譯所有語言
        """
        if language_code:
            languages = [language_code]
        else:
            languages = ['zh_TW', 'en_US']

        for lang in languages:
            ts_file = self.i18n_dir / f"{lang}.ts"
            qm_file = self.i18n_dir / f"{lang}.qm"

            if not ts_file.exists():
                logger.warning(f"Translation source file not found: {ts_file}")
                continue

            # 執行 lrelease (嘗試使用 PyQt6 內建的)
            try:
                # 先嘗試使用 PyQt6 內建的 lrelease
                cmd = [sys.executable, '-m', 'PyQt6.lrelease_main', str(ts_file), '-qm', str(qm_file)]
                logger.info(f"Compiling {lang}...")
                logger.info(f"Command: {' '.join(cmd)}")

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8'
                )

                if result.returncode == 0:
                    logger.info(f"✓ Successfully compiled to {qm_file}")
                    if result.stdout:
                        logger.info(result.stdout)
                else:
                    # 如果 PyQt6 內建方法失敗，嘗試使用系統的 lrelease
                    cmd = ['lrelease', str(ts_file), '-qm', str(qm_file)]
                    logger.info(f"Trying system lrelease...")

                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        encoding='utf-8'
                    )

                    if result.returncode == 0:
                        logger.info(f"✓ Successfully compiled to {qm_file}")
                        if result.stdout:
                            logger.info(result.stdout)
                    else:
                        logger.error(f"✗ Failed to compile {lang}")
                        logger.error(result.stderr)

            except Exception as e:
                logger.error(f"Error compiling translations: {e}")

    def show_statistics(self):
        """顯示翻譯統計資訊"""
        import xml.etree.ElementTree as ET

        logger.info("\n" + "=" * 60)
        logger.info("Translation Statistics")
        logger.info("=" * 60)

        for lang in ['zh_TW', 'en_US']:
            ts_file = self.i18n_dir / f"{lang}.ts"

            if not ts_file.exists():
                logger.warning(f"{lang}: Translation file not found")
                continue

            try:
                tree = ET.parse(ts_file)
                root = tree.getroot()

                total = 0
                translated = 0
                unfinished = 0

                for message in root.findall('.//message'):
                    total += 1
                    translation = message.find('translation')
                    if translation is not None:
                        if translation.get('type') == 'unfinished':
                            unfinished += 1
                        elif translation.text:
                            translated += 1

                percentage = (translated / total * 100) if total > 0 else 0

                logger.info(f"\n{lang}:")
                logger.info(f"  Total strings: {total}")
                logger.info(f"  Translated: {translated} ({percentage:.1f}%)")
                logger.info(f"  Unfinished: {unfinished}")
                logger.info(f"  Missing: {total - translated - unfinished}")

            except Exception as e:
                logger.error(f"Error parsing {ts_file}: {e}")

        logger.info("=" * 60)


def main():
    """主函數"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Update translation files for openpilot Log Viewer'
    )
    parser.add_argument(
        'action',
        choices=['extract', 'compile', 'update', 'stats'],
        help='Action to perform: extract strings, compile translations, update (extract+compile), or show stats'
    )
    parser.add_argument(
        '-l', '--language',
        help='Language code (e.g., zh_TW, en_US). If not specified, all languages will be processed.'
    )

    args = parser.parse_args()

    updater = TranslationUpdater()

    if args.action == 'extract':
        updater.extract_strings(args.language)
    elif args.action == 'compile':
        updater.compile_translations(args.language)
    elif args.action == 'update':
        updater.extract_strings(args.language)
        updater.compile_translations(args.language)
    elif args.action == 'stats':
        updater.show_statistics()


if __name__ == '__main__':
    main()
