# -*- coding: utf-8 -*-
"""
Signal Selector Widget - Tree view for selecting signals and CAN messages
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QPushButton, QLabel, QHeaderView, QTreeWidgetItemIterator,
    QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtGui import QColor, QBrush, QPixmap, QIcon
import logging
from typing import List, Dict, Set

logger = logging.getLogger(__name__)


class SignalSelector(QWidget):
    """
    Signal Selector Widget

    Features:
    - Display cereal signals / CAN signals / custom calculated signals
    - Tree structure
    - Multi-selection (checkbox)
    - Search
    - Color marking
    """

    # Signals
    signals_changed = pyqtSignal(list)  # List of selected signal names

    # Predefined colors (for charts)
    SIGNAL_COLORS = [
        '#FF6B6B',  # Red (紅) - 高對比
        '#45B7D1',  # Blue (藍) - 高對比
        '#52B788',  # Green (綠) - 高對比
        '#F8B739',  # Orange (橙) - 高對比
        '#BB8FCE',  # Purple (紫) - 高對比
        '#F7DC6F',  # Yellow (黃) - 高對比
        '#4ECDC4',  # Teal (青綠)
        '#FFA07A',  # Light Salmon (淺鮭魚色)
        '#85C1E2',  # Light Blue (淺藍)
        '#98D8C8',  # Mint (薄荷綠)
    ]


    def __init__(self, parent=None, translation_manager=None):
        super().__init__(parent)

        self.current_segment_id = None
        self.db_manager = None
        self.selected_signals: Set[str] = set()
        self.signal_colors: Dict[str, str] = {}  # signal_name -> color
        self.color_index = 0

        # Signal catalog
        self.cereal_signals: Dict[str, List[str]] = {}  # message_type -> signal names
        self.can_signals: Dict[str, List[str]] = {}  # address -> signal names
        self.custom_signals: List[Dict] = []
        self.signal_definitions: Dict[str, Dict] = {}  # signal_name -> signal_info
        self.signals_with_data: Set[str] = set()  # 有資料的訊號

        # Chart visibility state
        self.cereal_chart_visible = True
        self.can_chart_visible = True

        # Language setting - whether to show Chinese translations
        self.show_chinese_translation = False  # Default: English mode, no Chinese

        # Translation manager
        self.translation_manager = translation_manager

        # Load settings: whether to show DEPRECATED signals
        settings = QSettings('OpenpilotLogViewer', 'SignalSelector')
        self.show_deprecated = settings.value('show_deprecated', False, type=bool)

        self.setup_ui()

    def setup_ui(self):
        """Create UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # ============================================================
        # Search bar
        # ============================================================
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search signals...")
        self.search_input.textChanged.connect(self.on_search_changed)
        search_layout.addWidget(self.search_input)

        clear_search_btn = QPushButton("✕")
        clear_search_btn.setMaximumWidth(30)
        clear_search_btn.clicked.connect(lambda: self.search_input.clear())
        search_layout.addWidget(clear_search_btn)

        layout.addLayout(search_layout)

        # ============================================================
        # Options area
        # ============================================================
        options_layout = QHBoxLayout()

        self.show_deprecated_checkbox = QCheckBox("Show DEPRECATED signals")
        self.show_deprecated_checkbox.setChecked(self.show_deprecated)
        self.show_deprecated_checkbox.toggled.connect(self.on_show_deprecated_toggled)

        # Set style: enhance checkbox visibility (adapt to light and dark themes)
        self.show_deprecated_checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked {
                background-color: transparent;
                border: 2px solid #666666;
            }
            QCheckBox::indicator:unchecked:hover {
                border: 2px solid #4CAF50;
                background-color: rgba(76, 175, 80, 0.1);
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border: 2px solid #4CAF50;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #66BB6A;
                border: 2px solid #66BB6A;
            }
        """)

        options_layout.addWidget(self.show_deprecated_checkbox)

        options_layout.addStretch()
        layout.addLayout(options_layout)

        # ============================================================
        # Signal tree structure
        # ============================================================
        self.signal_tree = QTreeWidget()
        self.signal_tree.setHeaderLabels(["Signal Name", "Color", "Unit"])
        self.signal_tree.setColumnWidth(0, 200)
        self.signal_tree.setColumnWidth(1, 100)  # Increase width to accommodate QComboBox
        self.signal_tree.itemChanged.connect(self.on_item_changed)

        # Set style: enhance checkbox and selection visibility
        self.signal_tree.setStyleSheet("""
            QTreeWidget {
                outline: 0;
            }
            /* Unchecked checkbox - transparent background adapts to light and dark themes */
            QTreeWidget::indicator:unchecked {
                width: 18px;
                height: 18px;
                background-color: transparent;
                border: 2px solid #666666;
                border-radius: 3px;
            }
            QTreeWidget::indicator:unchecked:hover {
                border: 2px solid #4CAF50;
                background-color: rgba(76, 175, 80, 0.1);
            }
            /* Checked checkbox - filled with bright green */
            QTreeWidget::indicator:checked {
                width: 18px;
                height: 18px;
                background-color: #4CAF50;
                border: 2px solid #4CAF50;
                border-radius: 3px;
            }
            QTreeWidget::indicator:checked:hover {
                background-color: #66BB6A;
                border: 2px solid #66BB6A;
            }
            /* Indeterminate state (some child items selected) */
            QTreeWidget::indicator:indeterminate {
                width: 18px;
                height: 18px;
                background-color: #FFA726;
                border: 2px solid #FFA726;
                border-radius: 3px;
            }
            /* Selected item background (list item selected, not checkbox) */
            QTreeWidget::item:selected {
                background-color: #1976D2;
                color: white;
            }
        """)

        layout.addWidget(self.signal_tree)

        # ============================================================
        # Statistics info
        # ============================================================
        self.stats_label = QLabel("Selected: 0 / 0")
        self.stats_label.setStyleSheet("color: #666; font-size: 10pt;")
        layout.addWidget(self.stats_label)

    def load_segment(self, db_manager, segment_id: int):
        """
        Load signals for Segment

        Args:
            db_manager: DatabaseManager instance
            segment_id: Segment ID
        """
        self.current_segment_id = segment_id
        self.db_manager = db_manager

        try:
            # Get list of signals with data for current segment (this is the only source of truth)
            available_signals = db_manager.get_available_signals(segment_id)
            self.signals_with_data = set(available_signals)

            # Get signal definitions (for Chinese translations, etc.)
            self.signal_definitions = db_manager.get_all_defined_signals()

            # Categorize signals (based on signals with actual data)
            self.cereal_signals = {}  # {message_type: [signal_names]}
            self.can_signals = {}     # {address: [signal_names]}

            for signal_name in available_signals:
                # Determine signal type
                if signal_name.startswith('CAN_'):
                    # CAN signal
                    parts = signal_name.split('_')
                    if len(parts) >= 2 and parts[1].startswith('0x'):
                        address = parts[1]
                        if address not in self.can_signals:
                            self.can_signals[address] = []
                        self.can_signals[address].append(signal_name)
                else:
                    # Cereal signal (format: carState.vEgo or carState.cruiseState.enabled)
                    if '.' in signal_name:
                        msg_type = signal_name.split('.')[0]
                        if msg_type not in self.cereal_signals:
                            self.cereal_signals[msg_type] = []
                        self.cereal_signals[msg_type].append(signal_name)

            # Load custom calculated signals
            self.load_custom_signals()

            # Update tree structure
            self.populate_tree()

        except Exception as e:
            logger.error(f"Failed to load signal definitions: {e}")

    def _parse_signal_path(self, signal_name: str) -> list:
        """
        Parse signal path into hierarchy list

        carState.vEgo → ['carState', 'vEgo']
        carState.cruiseState.enabled → ['carState', 'cruiseState', 'enabled']
        carState.events[0].name → ['carState', 'events', '[0]', 'name']
        """
        import re
        parts = []
        current = ""

        for char in signal_name:
            if char == '.':
                if current:
                    parts.append(current)
                    current = ""
            elif char == '[':
                if current:
                    parts.append(current)
                    current = "["
            elif char == ']':
                current += ']'
                parts.append(current)
                current = ""
            else:
                current += char

        if current:
            parts.append(current)

        return parts


    def _build_tree_recursive(self, parent_item: QTreeWidgetItem, path_parts: list, signal_name: str, depth: int = 0):
        """
        Recursively build tree structure

        Args:
            parent_item: Parent node
            path_parts: List of path parts
            signal_name: Full signal name
            depth: Current depth
        """
        if not path_parts:
            return

        current_part = path_parts[0]
        remaining_parts = path_parts[1:]

        # Check if this node already exists
        existing_child = None
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child_text = child.text(0).split(' ')[0]  # Remove "✓ " marker
            if child_text == current_part or child_text == f"{current_part} (":
                existing_child = child
                break

        if remaining_parts:
            # Not last level, create/use intermediate node
            if not existing_child:
                # Create new intermediate node (folder)
                child_item = QTreeWidgetItem(parent_item, [current_part, "", ""])
                child_item.setData(0, Qt.ItemDataRole.UserRole, None)  # Mark as category
                child_item.setCheckState(0, Qt.CheckState.Unchecked)
                # Set bold
                font = child_item.font(0)
                font.setBold(True)
                child_item.setFont(0, font)
                existing_child = child_item

            # Recursively process remaining path
            self._build_tree_recursive(existing_child, remaining_parts, signal_name, depth + 1)
        else:
            # Last level, create signal item
            signal_info = self.signal_definitions.get(signal_name, {})
            name_cn = signal_info.get('name_cn', '')
            unit_cn = signal_info.get('unit_cn', '')

            # Display name (only add Chinese translation in Chinese mode)
            if name_cn and self.show_chinese_translation:
                display_name = f"{current_part} ({name_cn})"
            else:
                display_name = current_part

            # Mark as having data
            display_name = "✓ " + display_name

            item = QTreeWidgetItem(parent_item, [display_name, "", unit_cn])
            item.setCheckState(0, Qt.CheckState.Unchecked)
            item.setData(0, Qt.ItemDataRole.UserRole, signal_name)  # Store full name

            # Don't preset color, only create color selector when checked

            # Set tooltip
            tooltip = signal_name
            if name_cn:
                tooltip += f" - {name_cn}"
            item.setToolTip(0, tooltip)

    def set_chart_visibility(self, cereal_visible: bool = True, can_visible: bool = True):
        """
        Set chart visibility and update signal selector display

        Args:
            cereal_visible: Whether Cereal chart is visible
            can_visible: Whether CAN chart is visible
        """
        self.cereal_chart_visible = cereal_visible
        self.can_chart_visible = can_visible

    def set_language(self, language_code: str):
        """
        Set language, determine whether to show Chinese translation

        Args:
            language_code: Language code ('en_US' or 'zh_TW')
        """
        self.show_chinese_translation = (language_code == 'zh_TW')
        logger.info(f"SignalSelector language set to {language_code}, show_chinese_translation={self.show_chinese_translation}")

        # Reload current segment to update display
        if self.current_segment_id and self.db_manager:
            self.load_segment(self.db_manager, self.current_segment_id)

        # Repopulate tree structure (automatically filters by visibility)
        self.populate_tree()

    def populate_tree(self):
        """Populate tree structure"""
        self.signal_tree.clear()

        # Get translation function
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        # ============================================================
        # Cereal Signals - 樹狀層級結構
        # ============================================================
        if self.cereal_signals and self.cereal_chart_visible:
            total_cereal = sum(len(signals) for signals in self.cereal_signals.values())
            cereal_root = QTreeWidgetItem(self.signal_tree, [t("Cereal Signals"), "", f"({total_cereal})"])
            cereal_root.setExpanded(True)

            # 按 message_type 排序
            for msg_type in sorted(self.cereal_signals.keys()):
                signals = self.cereal_signals[msg_type]

                # 建立 message_type 根節點
                msg_type_item = QTreeWidgetItem(cereal_root, [msg_type, "", f"({len(signals)})"])
                msg_type_item.setExpanded(False)
                msg_type_item.setCheckState(0, Qt.CheckState.Unchecked)
                msg_type_item.setData(0, Qt.ItemDataRole.UserRole, None)
                font = msg_type_item.font(0)
                font.setBold(True)
                msg_type_item.setFont(0, font)

                # 為每個訊號建立層級結構
                for signal_name in sorted(signals):
                    # 過濾 DEPRECATED 訊號（如果選項未勾選）
                    if not self.show_deprecated and 'DEPRECATED' in signal_name:
                        continue

                    # 解析路徑 (移除 message_type 前綴)
                    path_without_prefix = signal_name[len(msg_type)+1:]  # 移除 "carState."
                    path_parts = self._parse_signal_path(path_without_prefix)

                    # 遞迴建立樹狀結構
                    self._build_tree_recursive(msg_type_item, path_parts, signal_name)

        # ============================================================
        # CAN Signals - 顯示訊息名稱的中文註解
        # ============================================================
        if self.can_signals and self.can_chart_visible:
            can_root = QTreeWidgetItem(self.signal_tree, [t("CAN Messages"), "", f"({sum(len(v) for v in self.can_signals.values())})"])
            can_root.setExpanded(True)

            for address in sorted(self.can_signals.keys()):
                # 取得該 Address 的第一個訊號，從中提取 message_name_cn
                first_signal = self.can_signals[address][0] if self.can_signals[address] else None
                message_name_cn = ""

                if first_signal and self.db_manager:
                    try:
                        cursor = self.db_manager.conn.cursor()
                        cursor.execute("""
                            SELECT message_name_cn
                            FROM can_signal_definitions
                            WHERE full_name = ?
                            LIMIT 1
                        """, (first_signal,))
                        result = cursor.fetchone()
                        cursor.close()
                        if result and result[0]:
                            message_name_cn = result[0]
                    except Exception as e:
                        logger.debug(f"Failed to get message name for {address}: {e}")

                # 顯示 Address + 訊息中文名稱（只有中文模式才顯示）
                address_display = f"Address {address}"
                if message_name_cn and self.show_chinese_translation:
                    address_display = f"{address} - {message_name_cn}"

                address_item = QTreeWidgetItem(can_root, [address_display, "", f"({len(self.can_signals[address])})"])
                address_item.setExpanded(False)
                address_item.setCheckState(0, Qt.CheckState.Unchecked)  # 添加 checkbox
                address_item.setData(0, Qt.ItemDataRole.UserRole, None)  # 標記為分類項目（不是訊號）
                # 設定粗體字體
                font = address_item.font(0)
                font.setBold(True)
                address_item.setFont(0, font)

                for signal_name in sorted(self.can_signals[address]):
                    # 過濾 DEPRECATED 訊號（如果選項未勾選）
                    if not self.show_deprecated and 'DEPRECATED' in signal_name:
                        continue

                    # 取得訊號定義資訊
                    signal_info = self.signal_definitions.get(signal_name, {})
                    name_cn = signal_info.get('name_cn', '')
                    desc_cn = signal_info.get('description_cn', '')
                    unit_cn = signal_info.get('unit_cn', '')

                    # 顯示名稱（只有中文模式才加中文翻譯）
                    if name_cn and self.show_chinese_translation:
                        display_name = f"{signal_name} ({name_cn})"
                    else:
                        display_name = signal_name

                    # 如果這個訊號有資料，加上標記
                    has_data = signal_name in self.signals_with_data
                    if has_data:
                        display_name = "✓ " + display_name

                    item = QTreeWidgetItem(address_item, [display_name, "", unit_cn])
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                    item.setData(0, Qt.ItemDataRole.UserRole, signal_name)

                    # 如果沒有資料，使用灰色字體
                    if not has_data:
                        item.setForeground(0, QBrush(QColor("#999")))

                    # 不再預先設定顏色，只在勾選時才創建顏色選擇器

                    # 設置 tooltip：中文名稱 - 描述 (單位)
                    tooltip_parts = []
                    if name_cn:
                        tooltip_parts.append(name_cn)
                    if desc_cn:
                        tooltip_parts.append(desc_cn)
                    if unit_cn:
                        tooltip_parts.append(f"({unit_cn})")

                    if tooltip_parts:
                        tooltip = " - ".join(tooltip_parts[:2])  # 名稱 - 描述
                        if len(tooltip_parts) > 2:
                            tooltip += " " + tooltip_parts[2]  # + 單位
                        item.setToolTip(0, tooltip)

        # ============================================================
        # Custom Signals
        # ============================================================
        if self.custom_signals:
            custom_root = QTreeWidgetItem(self.signal_tree, [t("Custom Calculated Signals"), "", f"({len(self.custom_signals)})"])
            custom_root.setExpanded(True)

            for custom_signal in self.custom_signals:
                signal_name = custom_signal['name']
                name_cn = custom_signal.get('name_cn', '')
                formula = custom_signal.get('formula', '')
                unit = custom_signal.get('unit', '')
                unit_cn = custom_signal.get('unit_cn', '')

                # 顯示名稱（只有中文模式才加中文翻譯）
                if name_cn and self.show_chinese_translation:
                    display_name = f"{signal_name} ({name_cn})"
                else:
                    display_name = signal_name

                # 檢查是否有資料並加上標記
                has_data = signal_name in self.signals_with_data
                if has_data:
                    display_name = "✓ " + display_name

                item = QTreeWidgetItem(custom_root, [display_name, "", unit_cn])
                item.setCheckState(0, Qt.CheckState.Unchecked)
                item.setData(0, Qt.ItemDataRole.UserRole, signal_name)

                # 如果沒有資料，使用灰色字體
                if not has_data:
                    item.setForeground(0, QBrush(QColor("#999")))

                # Tooltip：顯示公式
                tooltip = f"{signal_name}"
                if name_cn:
                    tooltip += f" - {name_cn}"
                if formula:
                    tooltip += f"\n公式: {formula}"
                if unit_cn:
                    tooltip += f"\n單位: {unit_cn}"
                elif unit:
                    tooltip += f"\n單位: {unit}"

                item.setToolTip(0, tooltip)

                # 不再預先分配顏色，只在選中時分配

        # 恢復已選訊號的勾選狀態和顏色選擇器
        self._restore_selected_signals()

        self.update_stats()

    def _restore_selected_signals(self):
        """恢復已選訊號的勾選狀態和顏色選擇器"""
        # 遍歷樹狀結構，找到已選訊號並恢復
        iterator = QTreeWidgetItemIterator(self.signal_tree)
        while iterator.value():
            item = iterator.value()
            signal_name = item.data(0, Qt.ItemDataRole.UserRole)

            if signal_name and signal_name in self.selected_signals:
                # 設定勾選狀態（不觸發 on_item_changed）
                self.signal_tree.blockSignals(True)
                item.setCheckState(0, Qt.CheckState.Checked)
                self.signal_tree.blockSignals(False)

                # 創建顏色選擇器
                color_combo = self._create_color_combo(signal_name)
                self.signal_tree.setItemWidget(item, 1, color_combo)

            iterator += 1

    def _get_signal_color(self, signal_name: str) -> str:
        """
        取得訊號顏色，如果沒有則分配一個

        Args:
            signal_name: 訊號名稱

        Returns:
            顏色 hex 值
        """
        if signal_name not in self.signal_colors:
            self.signal_colors[signal_name] = self.SIGNAL_COLORS[self.color_index % len(self.SIGNAL_COLORS)]
            self.color_index += 1
        return self.signal_colors[signal_name]

    def _create_color_combo(self, signal_name: str) -> QComboBox:
        """
        創建顏色選擇 ComboBox

        Args:
            signal_name: 訊號名稱

        Returns:
            QComboBox 實例
        """
        combo = QComboBox()
        combo.setMaximumWidth(90)

        # 為每個顏色創建一個圖標
        for color in self.SIGNAL_COLORS:
            # 創建顏色圖標
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(color))
            icon = QIcon(pixmap)
            combo.addItem(icon, "", color)  # text 為空，只顯示圖標

        # 設定當前顏色
        current_color = self.signal_colors.get(signal_name, self.SIGNAL_COLORS[0])
        try:
            index = self.SIGNAL_COLORS.index(current_color)
            combo.setCurrentIndex(index)
        except ValueError:
            combo.setCurrentIndex(0)
            self.signal_colors[signal_name] = self.SIGNAL_COLORS[0]

        # 連接顏色改變事件
        combo.currentIndexChanged.connect(
            lambda idx: self._on_color_changed(signal_name, self.SIGNAL_COLORS[idx])
        )

        return combo

    def _on_color_changed(self, signal_name: str, color: str):
        """
        顏色改變時的回調

        Args:
            signal_name: 訊號名稱
            color: 新顏色
        """
        self.signal_colors[signal_name] = color
        # 發送訊號變更事件，讓圖表更新顏色
        self.signals_changed.emit(list(self.selected_signals))

    def on_item_changed(self, item: QTreeWidgetItem, column: int):
        """Tree item 狀態改變"""
        if column != 0:
            return

        # 暫時阻止信號，避免遞迴觸發
        self.signal_tree.blockSignals(True)

        signal_name = item.data(0, Qt.ItemDataRole.UserRole)

        if signal_name:
            # 這是訊號項目
            if item.checkState(0) == Qt.CheckState.Checked:
                self.selected_signals.add(signal_name)
                # 只在選中時才分配顏色並創建顏色選擇器
                if signal_name not in self.signal_colors:
                    self._get_signal_color(signal_name)

                # 創建並設定顏色選擇 ComboBox
                color_combo = self._create_color_combo(signal_name)
                self.signal_tree.setItemWidget(item, 1, color_combo)
            else:
                self.selected_signals.discard(signal_name)
                # 取消選中時移除顏色選擇器
                self.signal_tree.removeItemWidget(item, 1)
                # 保留顏色設定，以便再次選中時使用相同顏色

            # 更新父節點狀態
            self._update_parent_check_state(item.parent())
        else:
            # 這是分類項目（message_type 或 address）
            check_state = item.checkState(0)
            if check_state != Qt.CheckState.PartiallyChecked:
                # 全選或取消全選該分類下所有有資料的訊號
                self._check_all_children(item, check_state == Qt.CheckState.Checked)

        self.signal_tree.blockSignals(False)
        self.update_stats()
        self.signals_changed.emit(list(self.selected_signals))

    def _check_all_children(self, parent_item: QTreeWidgetItem, checked: bool):
        """
        勾選或取消勾選該項目下所有有資料的訊號

        Args:
            parent_item: 父項目
            checked: True=勾選，False=取消勾選
        """
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            signal_name = child.data(0, Qt.ItemDataRole.UserRole)

            if signal_name:
                # 這是訊號項目
                # 只處理有資料的訊號（灰色訊號不處理）
                has_data = signal_name in self.signals_with_data
                if has_data:
                    child.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                    if checked:
                        self.selected_signals.add(signal_name)
                        # 分配顏色並創建顏色選擇器
                        if signal_name not in self.signal_colors:
                            self._get_signal_color(signal_name)
                        color_combo = self._create_color_combo(signal_name)
                        self.signal_tree.setItemWidget(child, 1, color_combo)
                    else:
                        self.selected_signals.discard(signal_name)
                        # 移除顏色選擇器
                        self.signal_tree.removeItemWidget(child, 1)
            else:
                # 這是子分類項目（遞迴處理）
                self._check_all_children(child, checked)

    def _update_parent_check_state(self, parent_item: QTreeWidgetItem):
        """
        更新父項目的勾選狀態（根據子項目狀態）

        Args:
            parent_item: 父項目
        """
        if not parent_item:
            return

        # 檢查所有子項目的狀態
        checked_count = 0
        unchecked_count = 0
        total_with_data = 0

        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            signal_name = child.data(0, Qt.ItemDataRole.UserRole)

            if signal_name:
                # 只計算有資料的訊號
                has_data = signal_name in self.signals_with_data
                if has_data:
                    total_with_data += 1
                    if child.checkState(0) == Qt.CheckState.Checked:
                        checked_count += 1
                    else:
                        unchecked_count += 1

        # 設定父項目狀態
        if total_with_data == 0:
            # 沒有有資料的子項目
            parent_item.setCheckState(0, Qt.CheckState.Unchecked)
        elif checked_count == total_with_data:
            # 全部勾選
            parent_item.setCheckState(0, Qt.CheckState.Checked)
        elif unchecked_count == total_with_data:
            # 全部未勾選
            parent_item.setCheckState(0, Qt.CheckState.Unchecked)
        else:
            # 部分勾選
            parent_item.setCheckState(0, Qt.CheckState.PartiallyChecked)

    def on_show_deprecated_toggled(self, checked: bool):
        """顯示/隱藏 DEPRECATED 訊號"""
        self.show_deprecated = checked

        # 儲存設定
        settings = QSettings('OpenpilotLogViewer', 'SignalSelector')
        settings.setValue('show_deprecated', checked)

        # 重新填充樹狀結構
        if self.current_segment_id is not None:
            self.populate_tree()

    def on_search_changed(self, text: str):
        """搜尋文字改變"""
        text = text.lower().strip()

        if not text:
            # 空白搜尋，顯示所有項目
            iterator = QTreeWidgetItemIterator(self.signal_tree)
            while iterator.value():
                item = iterator.value()
                item.setHidden(False)
                # 收合所有父項目
                signal_name = item.data(0, Qt.ItemDataRole.UserRole)
                if not signal_name:  # 這是父項目
                    item.setExpanded(False)
                iterator += 1
            return

        # 第一步：先隱藏所有項目，並收集匹配的訊號
        matched_items = []  # 記錄匹配的訊號項目
        iterator = QTreeWidgetItemIterator(self.signal_tree)
        while iterator.value():
            item = iterator.value()
            signal_name = item.data(0, Qt.ItemDataRole.UserRole)

            if signal_name:
                # 這是訊號項目
                if text in signal_name.lower():
                    item.setHidden(False)
                    matched_items.append(item)
                else:
                    item.setHidden(True)
            else:
                # 先隱藏所有父項目
                item.setHidden(True)

            iterator += 1

        # 第二步：顯示並展開所有匹配項目的祖先節點
        for item in matched_items:
            # 遞迴向上顯示所有父節點
            parent = item.parent()
            while parent:
                parent.setHidden(False)
                parent.setExpanded(True)  # 展開以顯示匹配的子項
                parent = parent.parent()  # 繼續向上

    def select_all(self):
        """全選所有訊號"""
        iterator = QTreeWidgetItemIterator(self.signal_tree)
        while iterator.value():
            item = iterator.value()
            signal_name = item.data(0, Qt.ItemDataRole.UserRole)

            if signal_name and not item.isHidden():
                # 只處理有資料的訊號
                has_data = signal_name in self.signals_with_data
                if has_data:
                    item.setCheckState(0, Qt.CheckState.Checked)
                    # on_item_changed 會自動創建顏色選擇器

            iterator += 1

    def deselect_all(self):
        """取消全選"""
        iterator = QTreeWidgetItemIterator(self.signal_tree)
        while iterator.value():
            item = iterator.value()
            signal_name = item.data(0, Qt.ItemDataRole.UserRole)

            if signal_name:
                item.setCheckState(0, Qt.CheckState.Unchecked)
                # on_item_changed 會自動移除顏色選擇器

            iterator += 1

    def select_signal(self, signal_name: str):
        """
        選擇特定訊號

        Args:
            signal_name: 要選擇的訊號名稱
        """
        # 遍歷所有項目尋找匹配的訊號
        iterator = QTreeWidgetItemIterator(self.signal_tree)
        while iterator.value():
            item = iterator.value()
            item_signal_name = item.data(0, Qt.ItemDataRole.UserRole)

            if item_signal_name == signal_name:
                # 檢查是否有資料
                has_data = signal_name in self.signals_with_data
                if has_data:
                    item.setCheckState(0, Qt.CheckState.Checked)
                    # on_item_changed 會自動創建顏色選擇器和更新狀態
                else:
                    logger.warning(f"Signal {signal_name} has no data in current segment")
                break

            iterator += 1

    def update_stats(self):
        """更新統計資訊"""
        total = len(self.cereal_signals) + sum(len(v) for v in self.can_signals.values()) + len(self.custom_signals)
        selected = len(self.selected_signals)
        if self.translation_manager:
            text = self.translation_manager.t("Selected: {0} / {1}").replace("{0}", str(selected)).replace("{1}", str(total))
        else:
            text = f"Selected: {selected} / {total}"
        self.stats_label.setText(text)

    def update_ui_text(self):
        """Update UI text based on current language"""
        if not self.translation_manager:
            return

        t = self.translation_manager.t

        # Update search placeholder
        self.search_input.setPlaceholderText(t("Search signals..."))

        # Update checkbox text
        self.show_deprecated_checkbox.setText(t("Show DEPRECATED signals"))

        # Update tree header labels
        self.signal_tree.setHeaderLabels([
            t("Signal Name"),
            t("Color"),
            t("Unit")
        ])

        # Update stats label
        self.update_stats()

        # Reload tree to update category names (Cereal Signals, CAN Messages, etc.)
        if self.current_segment_id and self.db_manager:
            self.populate_tree()

    def get_selected_signals(self) -> List[str]:
        """取得選中的訊號列表"""
        return list(self.selected_signals)

    def get_signal_color(self, signal_name: str) -> str:
        """取得訊號顏色"""
        return self.signal_colors.get(signal_name, '#000000')

    def load_custom_signals(self):
        """從資料庫載入自訂計算訊號"""
        if not self.db_manager:
            return

        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                SELECT signal_name, signal_name_cn, formula, unit, unit_cn
                FROM custom_signals
                ORDER BY signal_name
            """)

            self.custom_signals = []
            rows = cursor.fetchall()
            cursor.close()

            for signal_name, signal_name_cn, formula, unit, unit_cn in rows:
                self.custom_signals.append({
                    'name': signal_name,
                    'name_cn': signal_name_cn,
                    'formula': formula,
                    'unit': unit,
                    'unit_cn': unit_cn
                })

        except Exception as e:
            logger.error(f"Failed to load custom signals: {e}")
            self.custom_signals = []

    def add_custom_signal(self, name: str, formula: str, unit: str = ""):
        """
        新增自訂計算訊號

        Args:
            name: 訊號名稱
            formula: 計算公式 (e.g., "vEgo * 3.6")
            unit: 單位
        """
        self.custom_signals.append({
            'name': name,
            'formula': formula,
            'unit': unit
        })
        self.populate_tree()
