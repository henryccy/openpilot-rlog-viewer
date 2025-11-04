# -*- coding: utf-8 -*-
"""
DBC Parser for CAN message decoding
Parses VW MQB DBC file and provides Chinese translations
"""
import cantools
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class DBCParser:
    """Parse DBC file and decode CAN messages with Chinese descriptions"""

    # German to Chinese translation for common automotive terms
    TRANSLATIONS = {
        # Dashboard system
        'Anzeige': '顯示',

        # Others
        'Anforderung': '請求',
        'Signal': '訊號',
        'Status': '狀態',

        # Powertrain
        'Drehzahl': '轉速',
        'Fahrpedal': '油門踏板',
        'Gang': '檔位',
        'Gas': '油門',
        'Getriebe': '變速箱',
        'Kupplung': '離合器',
        'Motor': '引擎',

        # Sensors
        'Druck': '壓力',
        'Temperatur': '溫度',

        # Brake system
        'Bremsdruck': '煞車壓力',
        'Bremse': '煞車',

        # Diagnostics
        'Diagnose': '診斷',
        'Fehler': '故障',

        # Steering system
        'Lenkmoment': '方向盤扭矩',
        'Lenkung': '方向盤',
        'Lenkwinkel': '方向盤角度',

        # Speed
        'Geschwindigkeit': '速度',

        # Electrical system
        'Spannung': '電壓',
        'Strom': '電流',

    }

    def __init__(self, dbc_path: str):
        """
        Initialize DBC parser

        Args:
            dbc_path: Path to DBC file
        """
        self.dbc_path = dbc_path
        self.db = None
        self.load_dbc()

    def load_dbc(self):
        """Load DBC file"""
        try:
            self.db = cantools.database.load_file(self.dbc_path)
            logger.info(f"Loaded DBC file: {self.dbc_path}")
            logger.info(f"  Messages: {len(self.db.messages)}")
            logger.info(f"  Nodes: {len(self.db.nodes)}")
        except Exception as e:
            logger.error(f"Failed to load DBC file: {e}")
            raise

    def translate_to_chinese(self, text: str) -> str:
        """
        Translate German/English text to Chinese

        Args:
            text: Original text

        Returns:
            Translated text (or original if no translation found)
        """
        if not text:
            return text

        # Try exact match first
        if text in self.TRANSLATIONS:
            return self.TRANSLATIONS[text]

        # Try partial match (find German words in the text)
        translated = text
        for german, chinese in self.TRANSLATIONS.items():
            if german in text:
                translated = translated.replace(german, chinese)

        return translated

    def get_message_by_id(self, can_id: int):
        """Get message definition by CAN ID"""
        try:
            return self.db.get_message_by_frame_id(can_id)
        except KeyError:
            return None

    def decode_message(self, can_id: int, data: bytes) -> Optional[Dict]:
        """
        Decode CAN message

        Args:
            can_id: CAN message ID
            data: CAN message data bytes

        Returns:
            Dictionary of signal_name: value, or None if decode failed
        """
        try:
            msg = self.get_message_by_id(can_id)
            if msg is None:
                return None

            decoded = msg.decode(data)
            return decoded
        except Exception as e:
            logger.debug(f"Failed to decode CAN ID {can_id:03X}: {e}")
            return None

    def get_signal_info(self, can_id: int, signal_name: str) -> Optional[Dict]:
        """
        Get signal information including Chinese description

        Args:
            can_id: CAN message ID
            signal_name: Signal name

        Returns:
            Dictionary with signal info: name, unit, description_cn, min, max, etc.
        """
        try:
            msg = self.get_message_by_id(can_id)
            if msg is None:
                return None

            signal = msg.get_signal_by_name(signal_name)

            # Build info dictionary
            info = {
                'name': signal.name,
                'name_cn': self.translate_to_chinese(signal.name),
                'unit': signal.unit if signal.unit else '',
                'unit_cn': self.translate_to_chinese(signal.unit) if signal.unit else '',
                'min': signal.minimum,
                'max': signal.maximum,
                'scale': signal.scale,
                'offset': signal.offset,
                'description': signal.comment if signal.comment else '',
                'description_cn': self.translate_to_chinese(signal.comment) if signal.comment else ''
            }

            return info

        except Exception as e:
            logger.debug(f"Failed to get signal info: {e}")
            return None

    def get_all_messages(self) -> List[Dict]:
        """
        Get all CAN messages with Chinese descriptions

        Returns:
            List of message dictionaries
        """
        messages = []
        for msg in self.db.messages:
            msg_info = {
                'id': msg.frame_id,
                'id_hex': f"0x{msg.frame_id:03X}",
                'name': msg.name,
                'name_cn': self.translate_to_chinese(msg.name),
                'length': msg.length,
                'comment': msg.comment if msg.comment else '',
                'comment_cn': self.translate_to_chinese(msg.comment) if msg.comment else '',
                'signals': []
            }

            # Add signals
            for signal in msg.signals:
                signal_info = {
                    'name': signal.name,
                    'name_cn': self.translate_to_chinese(signal.name),
                    'unit': signal.unit if signal.unit else '',
                    'unit_cn': self.translate_to_chinese(signal.unit) if signal.unit else '',
                }
                msg_info['signals'].append(signal_info)

            messages.append(msg_info)

        return messages

    def get_message_description(self, can_id: int) -> str:
        """
        Get human-readable message description in Chinese

        Args:
            can_id: CAN message ID

        Returns:
            Chinese description string
        """
        msg = self.get_message_by_id(can_id)
        if msg is None:
            return f"未知訊息 (ID: 0x{can_id:03X})"

        name_cn = self.translate_to_chinese(msg.name)
        if name_cn == msg.name:
            # No translation, return both
            return f"{msg.name} (ID: 0x{can_id:03X})"
        else:
            return f"{name_cn} / {msg.name} (ID: 0x{can_id:03X})"
