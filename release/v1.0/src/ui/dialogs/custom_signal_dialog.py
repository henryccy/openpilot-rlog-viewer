# -*- coding: utf-8 -*-
"""
Custom Signal Dialog
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QTextEdit, QListWidget,
    QMessageBox, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import logging
import re
import math

logger = logging.getLogger(__name__)


class CustomSignalDialog(QDialog):
    """Custom Signal Dialog"""

    def __init__(self, db_manager, segment_id=None, parent=None, translation_manager=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.segment_id = segment_id
        self.available_signals = []  # Available signal list
        self.translation_manager = translation_manager

        t = self.translation_manager.t if self.translation_manager else lambda x: x
        self.setWindowTitle(t("Add Computed Signal"))
        self.setGeometry(100, 100, 900, 600)

        self.setup_ui()
        self.load_available_signals()

    def setup_ui(self):
        """Setup user interface"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x
        layout = QVBoxLayout()

        # Use splitter to separate left and right areas
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ============================================================
        # Left side: Signal definition form
        # ============================================================
        left_widget = QGroupBox(t("Signal Definition"))
        left_layout = QVBoxLayout()

        # Form
        form_layout = QGridLayout()

        # Signal name (English)
        form_layout.addWidget(QLabel(t("Signal Name (English):")), 0, 0)
        self.signal_name_edit = QLineEdit()
        self.signal_name_edit.setPlaceholderText(t("e.g.: speed_kmh, accel_mps2"))
        form_layout.addWidget(self.signal_name_edit, 0, 1)

        # Chinese name
        form_layout.addWidget(QLabel(t("Chinese Name:")), 1, 0)
        self.signal_name_cn_edit = QLineEdit()
        self.signal_name_cn_edit.setPlaceholderText(t("e.g.: Speed (km/h)"))
        form_layout.addWidget(self.signal_name_cn_edit, 1, 1)

        # Description
        form_layout.addWidget(QLabel(t("Description:")), 2, 0)
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText(t("Optional, brief description"))
        form_layout.addWidget(self.description_edit, 2, 1)

        # Unit
        form_layout.addWidget(QLabel(t("Unit:")), 3, 0)
        unit_layout = QHBoxLayout()
        self.unit_edit = QLineEdit()
        self.unit_edit.setPlaceholderText(t("English unit"))
        unit_layout.addWidget(self.unit_edit)
        self.unit_cn_edit = QLineEdit()
        self.unit_cn_edit.setPlaceholderText(t("Chinese unit"))
        unit_layout.addWidget(self.unit_cn_edit)
        form_layout.addLayout(unit_layout, 3, 1)

        left_layout.addLayout(form_layout)

        # Formula
        formula_label = QLabel(t("Formula:"))
        formula_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        left_layout.addWidget(formula_label)

        self.formula_edit = QTextEdit()
        self.formula_edit.setPlaceholderText(
            "範例:\n"
            "  carState.vEgo * 3.6\n"
            "  sqrt(carState.aEgo ** 2 + lateralPlan.curvature ** 2)\n"
            "  abs(controlsState.steeringTorque)\n\n"
            "支援運算：+, -, *, /, **, sqrt(), abs(), sin(), cos(), tan()\n"
            "訪問訊號：訊號完整名稱（見右側列表）"
        )
        self.formula_edit.setMaximumHeight(150)
        left_layout.addWidget(self.formula_edit)

        # Test button
        test_btn_layout = QHBoxLayout()
        test_btn_layout.addStretch()
        self.test_btn = QPushButton(t("Test Formula"))
        self.test_btn.clicked.connect(self.test_formula)
        test_btn_layout.addWidget(self.test_btn)
        left_layout.addLayout(test_btn_layout)

        # Test result
        self.test_result_label = QLabel("")
        self.test_result_label.setStyleSheet(
            "padding: 5px; background-color: #f0f0f0; border-radius: 3px; min-height: 60px;"
        )
        self.test_result_label.setWordWrap(True)
        left_layout.addWidget(self.test_result_label)

        left_layout.addStretch()
        left_widget.setLayout(left_layout)

        # ============================================================
        # Right side: Available signal list
        # ============================================================
        right_widget = QGroupBox(t("Available Signals"))
        right_layout = QVBoxLayout()

        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel(t("Search:")))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(t("Search signals..."))
        self.search_edit.textChanged.connect(self.filter_signals)
        search_layout.addWidget(self.search_edit)
        right_layout.addLayout(search_layout)

        # Signal list
        self.signal_list = QListWidget()
        self.signal_list.itemDoubleClicked.connect(self.insert_signal_name)
        right_layout.addWidget(self.signal_list)

        # Hint
        hint_label = QLabel(t("Double-click signal name to insert into formula"))
        hint_label.setStyleSheet("color: #666; font-size: 10pt;")
        right_layout.addWidget(hint_label)

        right_widget.setLayout(right_layout)

        # Add to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

        # ============================================================
        # Bottom buttons
        # ============================================================
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton(t("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton(t("Save"))
        save_btn.clicked.connect(self.save_signal)
        save_btn.setDefault(True)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def load_available_signals(self):
        """Load available signal list"""
        if not self.db_manager or not self.db_manager.conn:
            return

        try:
            cursor = self.db_manager.conn.cursor()
            self.available_signals = []

            # Load Cereal signals
            cursor.execute("""
                SELECT full_name, name_cn, unit, unit_cn
                FROM cereal_signal_definitions
                ORDER BY full_name
            """)
            cereal_signals = cursor.fetchall()

            for signal_name, name_cn, unit, unit_cn in cereal_signals:
                display_unit = unit_cn if unit_cn else (unit if unit else "")
                display_name = f"{signal_name}"
                if name_cn:
                    display_name += f" ({name_cn})"
                if display_unit:
                    display_name += f" [{display_unit}]"

                self.available_signals.append({
                    'name': signal_name,
                    'display': display_name,
                    'type': 'cereal'
                })

            # Load CAN signals
            cursor.execute("""
                SELECT full_name, signal_name_cn, unit, unit_cn
                FROM can_signal_definitions
                ORDER BY full_name
            """)
            can_signals = cursor.fetchall()

            for signal_name, name_cn, unit, unit_cn in can_signals:
                display_unit = unit_cn if unit_cn else (unit if unit else "")
                display_name = f"{signal_name}"
                if name_cn:
                    display_name += f" ({name_cn})"
                if display_unit:
                    display_name += f" [{display_unit}]"

                self.available_signals.append({
                    'name': signal_name,
                    'display': display_name,
                    'type': 'can'
                })

            # Populate list
            self.populate_signal_list()

            logger.info(f"Loaded {len(self.available_signals)} available signals")

        except Exception as e:
            logger.error(f"Failed to load available signals: {e}")

    def populate_signal_list(self):
        """Populate signal list"""
        self.signal_list.clear()
        for signal in self.available_signals:
            self.signal_list.addItem(signal['display'])

    def filter_signals(self, text):
        """Filter signal list"""
        self.signal_list.clear()
        text = text.lower()

        for signal in self.available_signals:
            if text in signal['display'].lower():
                self.signal_list.addItem(signal['display'])

    def insert_signal_name(self, item):
        """Double-click to insert signal name into formula"""
        # Extract signal name from display text
        display_text = item.text()

        # Find corresponding signal
        for signal in self.available_signals:
            if signal['display'] == display_text:
                signal_name = signal['name']

                # Insert at cursor position
                cursor = self.formula_edit.textCursor()
                cursor.insertText(signal_name)
                self.formula_edit.setFocus()
                break

    def test_formula(self):
        """Test formula"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x
        formula = self.formula_edit.toPlainText().strip()

        if not formula:
            self.test_result_label.setText(t("Please enter formula"))
            self.test_result_label.setStyleSheet(
                "padding: 5px; background-color: #fff3cd; border-radius: 3px; min-height: 60px;"
            )
            return

        if not self.segment_id:
            self.test_result_label.setText(t("Test requires a Segment to be selected"))
            self.test_result_label.setStyleSheet(
                "padding: 5px; background-color: #fff3cd; border-radius: 3px; min-height: 60px;"
            )
            return

        try:
            # Extract signal names used in formula
            signal_names = self.extract_signal_names(formula)

            if not signal_names:
                self.test_result_label.setText(t("No valid signal names found in formula"))
                self.test_result_label.setStyleSheet(
                    "padding: 5px; background-color: #f8d7da; border-radius: 3px; min-height: 60px;"
                )
                return

            # Query signal data (first 10 records)
            signal_data = {}
            for sig_name in signal_names:
                cursor = self.db_manager.conn.cursor()
                cursor.execute("""
                    SELECT value
                    FROM timeseries_data
                    WHERE segment_id = ? AND signal_name = ?
                    AND value IS NOT NULL
                    LIMIT 10
                """, (self.segment_id, sig_name))
                rows = cursor.fetchall()

                if rows:
                    signal_data[sig_name] = [row[0] for row in rows]
                else:
                    self.test_result_label.setText(t("Signal '{0}' has no data").format(sig_name))
                    self.test_result_label.setStyleSheet(
                        "padding: 5px; background-color: #f8d7da; border-radius: 3px; min-height: 60px;"
                    )
                    return

            # Calculate formula (using first record)
            test_values = {name: values[0] for name, values in signal_data.items()}
            result = self.evaluate_formula(formula, test_values)

            # Show result
            result_text = f"✓ 公式測試成功\n\n"
            result_text += f"Signals used: {', '.join(signal_names)}\n"
            result_text += f"測試數值: {test_values}\n"
            result_text += f"Result: {result:.6f}"

            self.test_result_label.setText(result_text)
            self.test_result_label.setStyleSheet(
                "padding: 5px; background-color: #d4edda; color: #155724; border-radius: 3px; min-height: 60px;"
            )

        except Exception as e:
            self.test_result_label.setText(f"✗ 公式測試失敗\n\n錯誤: {str(e)}")
            self.test_result_label.setStyleSheet(
                "padding: 5px; background-color: #f8d7da; color: #721c24; border-radius: 3px; min-height: 60px;"
            )

    def extract_signal_names(self, formula):
        """Extract signal names from formula"""
        # Signal name format: messageType.fieldName or CAN_0xXXX_SignalName
        pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*|CAN_0x[0-9A-Fa-f]+_[a-zA-Z_][a-zA-Z0-9_]*)\b'
        matches = re.findall(pattern, formula)

        # Verify if valid signals
        valid_signals = []
        available_names = {sig['name'] for sig in self.available_signals}

        for match in matches:
            if match in available_names:
                valid_signals.append(match)

        return list(set(valid_signals))  # Remove duplicates

    def evaluate_formula(self, formula, signal_values):
        """
        Evaluate formula result

        Args:
            formula: Formula string
            signal_values: Signal value dictionary {signal_name: value}

        Returns:
            Calculation result
        """
        # Replace signal names with actual values
        eval_formula = formula
        for sig_name, value in signal_values.items():
            # Use regex to ensure complete signal name matching
            pattern = r'\b' + re.escape(sig_name) + r'\b'
            eval_formula = re.sub(pattern, str(value), eval_formula)

        # Safe math functions
        safe_dict = {
            'sqrt': math.sqrt,
            'abs': abs,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'asin': math.asin,
            'acos': math.acos,
            'atan': math.atan,
            'atan2': math.atan2,
            'exp': math.exp,
            'log': math.log,
            'log10': math.log10,
            'pow': pow,
            'pi': math.pi,
            'e': math.e,
            '__builtins__': {}
        }

        # Evaluate formula
        try:
            result = eval(eval_formula, safe_dict)
            return float(result)
        except Exception as e:
            raise ValueError(f"公式計算錯誤: {str(e)}")

    def save_signal(self):
        """Save computed signal"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x
        signal_name = self.signal_name_edit.text().strip()
        signal_name_cn = self.signal_name_cn_edit.text().strip()
        description = self.description_edit.text().strip()
        formula = self.formula_edit.toPlainText().strip()
        unit = self.unit_edit.text().strip()
        unit_cn = self.unit_cn_edit.text().strip()

        # Validate required fields
        if not signal_name:
            QMessageBox.warning(self, t("Input Error"), t("Please enter signal name"))
            return

        if not formula:
            QMessageBox.warning(self, t("Input Error"), t("Please enter formula"))
            return

        # Validate signal name format (only letters, numbers, underscores allowed)
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', signal_name):
            QMessageBox.warning(
                self,
                t("Input Error"),
                t("Signal name can only contain letters, numbers, and underscores, and must start with a letter or underscore")
            )
            return

        # Validate if signals in formula are valid
        signal_names = self.extract_signal_names(formula)
        if not signal_names:
            reply = QMessageBox.question(
                self,
                t("Confirm"),
                t("No valid signal names found in formula, save anyway?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            cursor = self.db_manager.conn.cursor()

            # Check if signal name already exists
            cursor.execute("""
                SELECT custom_id FROM custom_signals WHERE signal_name = ?
            """, (signal_name,))

            if cursor.fetchone():
                QMessageBox.warning(self, t("Error"), t("Signal name '{0}' already exists").format(signal_name))
                return

            # Insert new signal
            cursor.execute("""
                INSERT INTO custom_signals
                (signal_name, signal_name_cn, description_cn, formula, unit, unit_cn)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (signal_name, signal_name_cn if signal_name_cn else None,
                  description if description else None, formula,
                  unit if unit else None, unit_cn if unit_cn else None))

            self.db_manager.conn.commit()

            QMessageBox.information(
                self,
                t("Save Successful"),
                f"計算訊號 '{signal_name}' 已成功儲存！\n\n"
                f"You can find this signal in the signal selector."
            )

            logger.info(f"Created custom signal: {signal_name} = {formula}")

            self.accept()

        except Exception as e:
            self.db_manager.conn.rollback()
            logger.error(f"Failed to save custom signal: {e}")
            QMessageBox.critical(self, t("Save Failed"), t("Failed to save calculated signal:\n{0}").format(str(e)))
