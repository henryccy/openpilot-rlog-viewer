# -*- coding: utf-8 -*-
"""
翻譯管理器
Translation Manager

提供應用程式的多語言支援 (JSON-based)
"""
from PyQt6.QtCore import QLocale, QSettings
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class TranslationManager:
    """管理應用程式的翻譯 (使用 JSON 檔案)"""

    SUPPORTED_LANGUAGES = {
        'zh_TW': '繁體中文 (Traditional Chinese)',
        'en_US': 'English'
    }

    def __init__(self):
        self.current_language = 'en_US'
        self.translations = {}  # 翻譯字典

        # i18n 目錄路徑 - 支援開發模式和編譯後的 EXE
        import sys
        if getattr(sys, 'frozen', False):
            # 編譯後的 EXE：i18n 在 exe 同級目錄
            exe_dir = Path(sys.executable).parent
            self.i18n_dir = exe_dir / 'i18n'
        else:
            # 開發模式：從當前檔案路徑計算
            self.i18n_dir = Path(__file__).parent.parent.parent / 'i18n'

        # 確保目錄存在
        self.i18n_dir.mkdir(exist_ok=True)

    def load_language(self, language_code: str) -> bool:
        """
        載入指定語言

        Args:
            language_code: 語言代碼 (e.g., 'zh_TW', 'en_US')

        Returns:
            bool: 是否成功載入
        """
        if language_code not in self.SUPPORTED_LANGUAGES:
            logger.warning(f"Unsupported language: {language_code}")
            return False

        # 如果是英文，不需要載入翻譯檔（使用源碼中的英文）
        if language_code == 'en_US':
            self.current_language = language_code
            self.translations = {}  # 清空翻譯
            logger.info("Using default English (source language)")
            return True

        # 載入 JSON 翻譯檔
        json_file = self.i18n_dir / f"{language_code}.json"
        if json_file.exists():
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    self.translations = json.load(f)
                self.current_language = language_code
                logger.info(f"Loaded language: {language_code} ({len(self.translations)} translations)")
                return True
            except Exception as e:
                logger.error(f"Failed to load translation file {json_file}: {e}")
                self.translations = {}
                self.current_language = 'en_US'
                return False
        else:
            logger.warning(f"Translation file not found: {json_file}")
            self.translations = {}
            self.current_language = 'en_US'
            return False

    def t(self, key: str) -> str:
        """
        取得翻譯文字

        Args:
            key: 英文原文

        Returns:
            str: 翻譯後的文字，如果找不到則返回原文
        """
        # 如果是英文模式或找不到翻譯，返回原文
        return self.translations.get(key, key)

    def get_system_language(self) -> str:
        """
        取得系統預設語言

        Returns:
            str: 語言代碼
        """
        locale = QLocale.system().name()  # 例如: zh_TW, en_US

        # 如果系統語言在支援列表中，直接使用
        if locale in self.SUPPORTED_LANGUAGES:
            return locale

        # 否則根據語言代碼匹配
        lang_code = locale.split('_')[0]
        if lang_code == 'zh':
            return 'zh_TW'
        elif lang_code == 'en':
            return 'en_US'

        # 預設使用英文（國際化版本）
        return 'en_US'

    def save_language_preference(self, language_code: str):
        """
        儲存語言偏好到設定檔

        Args:
            language_code: 語言代碼
        """
        settings = QSettings('OpenpilotViewer', 'Application')
        settings.setValue('language', language_code)
        logger.info(f"Saved language preference: {language_code}")

    def load_language_preference(self) -> str:
        """
        載入語言偏好

        Returns:
            str: 語言代碼，如果沒有儲存則返回系統語言
        """
        settings = QSettings('OpenpilotViewer', 'Application')
        language = settings.value('language', None)

        if language and language in self.SUPPORTED_LANGUAGES:
            return language

        # 如果沒有儲存或不支援，使用系統語言
        return self.get_system_language()

    def get_available_languages(self) -> dict:
        """
        取得可用的語言列表

        Returns:
            dict: {語言代碼: 語言名稱}
        """
        return self.SUPPORTED_LANGUAGES.copy()

    def get_current_language(self) -> str:
        """
        取得當前語言代碼

        Returns:
            str: 語言代碼
        """
        return self.current_language

    def get_current_language_name(self) -> str:
        """
        取得當前語言的名稱

        Returns:
            str: 語言名稱
        """
        return self.SUPPORTED_LANGUAGES.get(self.current_language, 'Unknown')
