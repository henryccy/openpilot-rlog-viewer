# -*- coding: utf-8 -*-
"""
Cap'n Proto Annotation Extractor
Extracts field comments from .capnp schema files
"""
import re
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class CapnpAnnotationExtractor:
    """
    Extracts field annotations from Cap'n Proto schema files
    """

    # English to Chinese translations for common signal descriptions
    TRANSLATIONS = {
        # Speed and motion
        'best estimate of speed': '速度最佳估計值',
        'best estimate of acceleration': '加速度最佳估計值',
        'unfiltered speed from CAN sensors': '來自 CAN 感測器的未過濾速度',
        'best estimate of speed shown on car\'s instrument cluster, used for UI': '儀表板顯示速度（用於 UI）',
        'best estimate of yaw rate': '偏航率最佳估計值',

        # Pedals
        'this is user pedal only': '僅為使用者踏板',
        'gas pedal': '油門踏板',
        'brake pedal': '煞車踏板',

        # Steering
        'steering wheel': '方向盤',
        'Offset betweens sensors in case there multiple': '多個感測器間的偏移',
        'if the user is using the steering wheel': '使用者是否正在使用方向盤',
        'temporary EPS fault': '暫時 EPS 故障',
        'permanent EPS fault': '永久 EPS 故障',

        # Cruise control
        'actual set speed': '實際設定速度',
        'set speed to display in the UI': 'UI 顯示的設定速度',
        'can OP be engaged?': 'OP 可否啟動？',

        # CAN health
        'invalid counter/checksums': '無效的計數器/校驗和',
        'CAN bus dropped out': 'CAN 匯流排斷線',

        # Faults
        'some ECU is faulted, but car remains controllable': '某個 ECU 故障，但車輛仍可控制',

        # Path and control
        'path curvature from vehicle model': '車輛模型的路徑曲率',
        'lag adjusted curvatures used by lateral controllers': '橫向控制器使用的延遲調整曲率',

        # UI alerts
        'UI alerts': 'UI 警報',
    }

    def __init__(self, capnp_directory: str = "."):
        """
        Initialize annotation extractor

        Args:
            capnp_directory: Directory containing .capnp files
        """
        self.capnp_directory = Path(capnp_directory)
        self.annotations: Dict[str, Dict[str, str]] = {}

    def extract_struct_fields(self, file_path: Path, struct_name: str) -> Dict[str, str]:
        """
        Extract field annotations from a specific struct

        Args:
            file_path: Path to .capnp file
            struct_name: Name of the struct (e.g., "CarState")

        Returns:
            Dictionary mapping field names to their comments
        """
        annotations = {}

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Find the struct start line
            struct_start = -1
            for i, line in enumerate(lines):
                if re.match(rf'struct {struct_name}\s+', line):
                    struct_start = i
                    break

            if struct_start == -1:
                logger.warning(f"Struct {struct_name} not found in {file_path}")
                return annotations

            # Find matching closing brace using brace counting
            brace_count = 0
            struct_end = -1
            started = False

            for i in range(struct_start, len(lines)):
                line = lines[i]

                # Count braces
                for char in line:
                    if char == '{':
                        brace_count += 1
                        started = True
                    elif char == '}':
                        brace_count -= 1
                        if started and brace_count == 0:
                            struct_end = i
                            break

                if struct_end != -1:
                    break

            if struct_end == -1:
                logger.warning(f"Could not find end of struct {struct_name}")
                return annotations

            # Extract only top-level fields (ignore nested structs/enums)
            in_nested_block = False
            nested_brace_count = 0

            for i in range(struct_start + 1, struct_end):
                line = lines[i].strip()

                # Skip empty lines and section comments
                if not line or line.startswith('#'):
                    continue

                # Check if entering nested struct/enum
                if 'struct ' in line or 'enum ' in line or 'union ' in line:
                    in_nested_block = True
                    nested_brace_count = 0

                # Track nested braces
                if in_nested_block:
                    for char in line:
                        if char == '{':
                            nested_brace_count += 1
                        elif char == '}':
                            nested_brace_count -= 1
                            if nested_brace_count == 0:
                                in_nested_block = False
                                break
                    continue

                # Extract top-level field with pattern: fieldName @number :Type;  # comment
                field_match = re.match(r'(\w+)\s+@\d+\s*:[^;]+;\s*(?:#\s*(.+?))?$', line)

                if field_match:
                    field_name = field_match.group(1)
                    comment = field_match.group(2)

                    if comment:
                        # Clean up the comment
                        comment = comment.strip()
                        annotations[field_name] = comment
                    else:
                        # No comment, just note the field exists
                        annotations[field_name] = ""

            logger.info(f"Extracted {len(annotations)} fields from {struct_name}")

        except Exception as e:
            logger.error(f"Failed to extract annotations from {file_path}: {e}")

        return annotations

    def translate_comment(self, comment: str) -> str:
        """
        Translate English comment to Chinese

        Args:
            comment: Original English comment

        Returns:
            Chinese translation or original if no translation found
        """
        if not comment:
            return comment

        # Try exact match first
        if comment in self.TRANSLATIONS:
            return self.TRANSLATIONS[comment]

        # Try partial match
        translated = comment
        for english, chinese in self.TRANSLATIONS.items():
            if english.lower() in comment.lower():
                translated = chinese
                break

        return translated

    def load_all_annotations(self):
        """
        Load annotations from common openpilot structs
        """
        # Load CarState from car.capnp
        car_capnp = self.capnp_directory / 'car.capnp'
        if car_capnp.exists():
            car_state = self.extract_struct_fields(car_capnp, 'CarState')
            self.annotations['CarState'] = car_state
            logger.info(f"Loaded {len(car_state)} CarState fields")

        # Load ControlsState from log.capnp
        log_capnp = self.capnp_directory / 'log.capnp'
        if log_capnp.exists():
            controls_state = self.extract_struct_fields(log_capnp, 'ControlsState')
            self.annotations['ControlsState'] = controls_state
            logger.info(f"Loaded {len(controls_state)} ControlsState fields")

    def get_signal_description(self, signal_type: str, field_name: str,
                               translate: bool = True) -> Optional[str]:
        """
        Get description for a signal

        Args:
            signal_type: Type of signal (e.g., "carState", "controlsState")
            field_name: Field name (e.g., "vEgo")
            translate: Whether to translate to Chinese

        Returns:
            Description string (English or Chinese)
        """
        # Map signal types to struct names
        type_mapping = {
            'carState': 'CarState',
            'controlsState': 'ControlsState',
        }

        struct_name = type_mapping.get(signal_type)
        if not struct_name or struct_name not in self.annotations:
            return None

        comment = self.annotations[struct_name].get(field_name)
        if not comment:
            return None

        if translate:
            return self.translate_comment(comment)
        else:
            return comment

    def get_all_descriptions(self, translate: bool = True) -> Dict[str, Dict[str, str]]:
        """
        Get all signal descriptions

        Args:
            translate: Whether to translate to Chinese

        Returns:
            Nested dictionary: {signal_type: {field_name: description}}
        """
        result = {}

        for struct_name, fields in self.annotations.items():
            # Convert struct name to signal type
            signal_type = struct_name[0].lower() + struct_name[1:]  # CarState -> carState

            result[signal_type] = {}
            for field_name, comment in fields.items():
                if translate and comment:
                    result[signal_type][field_name] = self.translate_comment(comment)
                else:
                    result[signal_type][field_name] = comment

        return result

    def export_to_dict(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """
        Export all annotations in a structured format

        Returns:
            Dictionary with both English and Chinese descriptions
        """
        result = {}

        for struct_name, fields in self.annotations.items():
            signal_type = struct_name[0].lower() + struct_name[1:]
            result[signal_type] = {}

            for field_name, comment in fields.items():
                result[signal_type][field_name] = {
                    'description_en': comment,
                    'description_cn': self.translate_comment(comment) if comment else ""
                }

        return result
