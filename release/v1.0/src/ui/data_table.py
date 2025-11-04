# -*- coding: utf-8 -*-
"""
Data Table Widget - Shows statistics for selected signals in ±10s window
資料表區元件 - 顯示選中訊號在±10秒視窗的統計資料
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QComboBox, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class DataTable(QWidget):
    """
    資料表區 Widget

    功能:
    - 顯示系統日誌訊息
    - 載入時顯示整個 Segment 的所有日誌
    - 可篩選類型、Daemon、函數
    """

    # 信號：資料更新完成
    data_updated = pyqtSignal()

    def __init__(self, parent=None, translation_manager=None):
        super().__init__(parent)

        self.db_manager = None
        self.current_segment_id = None
        self.segment_start_time_ns = 0  # Segment 的起始時間（用於計算相對時間）
        self.all_log_messages = []  # 存儲所有日誌訊息
        self.filtered_log_messages = []  # 篩選後的日誌訊息

        # 篩選條件
        self.filter_log_type = None  # None, 'log', 'error'
        self.filter_daemon = None
        self.filter_function = None
        self.filter_keyword = ""  # 關鍵字搜尋

        # Translation manager
        self.translation_manager = translation_manager

        self.setup_ui()

    def setup_ui(self):
        """建立 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Get translation function
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        # ============================================================
        # 標題與篩選器
        # ============================================================
        header_layout = QHBoxLayout()

        self.title_label = QLabel(t("System Log Messages"))
        self.title_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        # 類型篩選
        self.type_label = QLabel(t("Type:"))
        header_layout.addWidget(self.type_label)
        self.filter_type_combo = QComboBox()
        self.filter_type_combo.addItems([t("All"), t("Log"), t("Error")])
        self.filter_type_combo.currentTextChanged.connect(self.on_filter_changed)
        header_layout.addWidget(self.filter_type_combo)

        # Daemon 篩選
        self.daemon_label = QLabel(t("Daemon:"))
        header_layout.addWidget(self.daemon_label)
        self.filter_daemon_combo = QComboBox()
        self.filter_daemon_combo.addItem(t("All"))
        self.filter_daemon_combo.setMinimumWidth(150)  # 設定最小寬度以顯示完整文字
        self.filter_daemon_combo.currentTextChanged.connect(self.on_filter_changed)
        header_layout.addWidget(self.filter_daemon_combo)

        # 關鍵字搜尋
        self.keyword_label = QLabel(t("Keyword:"))
        header_layout.addWidget(self.keyword_label)
        from PyQt6.QtWidgets import QLineEdit
        self.filter_keyword_input = QLineEdit()
        self.filter_keyword_input.setPlaceholderText(t("Search messages..."))
        self.filter_keyword_input.setMinimumWidth(150)
        self.filter_keyword_input.textChanged.connect(self.on_filter_changed)
        header_layout.addWidget(self.filter_keyword_input)

        # 重置篩選按鈕
        self.reset_btn = QPushButton(t("Reset"))
        self.reset_btn.clicked.connect(self.reset_filters)
        header_layout.addWidget(self.reset_btn)

        layout.addLayout(header_layout)

        # ============================================================
        # 統計標籤
        # ============================================================
        self.stats_label = QLabel(t("Total: {0} entries").replace("{0}", "0"))
        self.stats_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(self.stats_label)

        # ============================================================
        # 資料表
        # ============================================================
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            t("Time"), t("Type"), t("Daemon"), t("Function"), t("Message")
        ])

        # 設定欄位寬度
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # 時間
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # 類型
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Daemon
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 函數
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # 訊息

        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)

        layout.addWidget(self.table)

    def set_database_manager(self, db_manager):
        """設定資料庫管理器"""
        self.db_manager = db_manager

    def set_segment(self, segment_id: int):
        """設定當前 Segment 並載入所有日誌"""
        self.current_segment_id = segment_id

        # 取得 segment 的起始時間
        if self.db_manager:
            try:
                segment = self.db_manager.get_segment_by_id(segment_id)
                if segment:
                    self.segment_start_time_ns = segment['start_time_ns']
                    logger.info(f"📊 Segment start_time_ns: {self.segment_start_time_ns:,} ns")
                else:
                    self.segment_start_time_ns = 0
                    logger.warning(f"📊 Segment not found, using start_time = 0")
            except Exception as e:
                logger.error(f"Failed to get segment info: {e}")
                self.segment_start_time_ns = 0
        else:
            self.segment_start_time_ns = 0

        # 載入所有日誌訊息（異步避免阻塞）
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self.load_all_logs)

    def set_signals(self, signal_names: List[str], signal_colors: Dict[str, str] = None):
        """
        設定要顯示的訊號（保留此方法以保持相容性，但日誌顯示不需要訊號信息）

        Args:
            signal_names: 訊號名稱列表（未使用）
            signal_colors: 訊號顏色映射（未使用）
        """
        pass  # 日誌顯示不需要訊號信息

    def update_time_window(self, time_ns: int):
        """
        更新時間視窗（不再重新載入日誌，僅保留此方法以保持相容性）

        日誌訊息不會跟著播放更新，在載入 Segment 時已經全部載入
        但仍需發送信號以避免阻塞播放
        """
        # 立即發送信號表示"更新完成"（實際上沒有更新）
        self.data_updated.emit()

    def load_all_logs(self):
        """載入當前 Segment 的所有日誌訊息"""
        if not self.db_manager or not self.current_segment_id:
            self.all_log_messages = []
            self.filtered_log_messages = []
            self.update_table()
            # 發送信號表示更新完成
            self.data_updated.emit()
            return

        try:
            logger.info(f"📊 Loading all logs for Segment {self.current_segment_id}...")

            # 查詢該 segment 的所有日誌（不限制時間範圍）
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                SELECT
                    time_ns, log_type, daemon, levelnum, filename,
                    funcname, lineno, message, dongle_id, version, branch, "commit"
                FROM log_messages
                WHERE segment_id = ?
                ORDER BY time_ns
            """, (self.current_segment_id,))

            rows = cursor.fetchall()
            cursor.close()

            # 轉換為字典列表
            self.all_log_messages = [
                {
                    'time_ns': row[0],
                    'log_type': row[1],
                    'daemon': row[2],
                    'levelnum': row[3],
                    'filename': row[4],
                    'funcname': row[5],
                    'lineno': row[6],
                    'message': row[7],
                    'dongle_id': row[8],
                    'version': row[9],
                    'branch': row[10],
                    'commit': row[11]
                }
                for row in rows
            ]

            logger.info(f"📊 Loaded {len(self.all_log_messages)} log messages")

            # 更新 Daemon 篩選下拉選單
            self.update_daemon_filter_options()

            # 重置篩選並更新顯示
            self.reset_filters()

            # 發送信號表示更新完成
            self.data_updated.emit()

        except Exception as e:
            logger.error(f"Failed to load log messages: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.all_log_messages = []
            self.filtered_log_messages = []
            self.update_table()
            # 即使失敗也發送信號
            self.data_updated.emit()

    def update_daemon_filter_options(self):
        """更新 Daemon 篩選選項"""
        # 取得所有唯一的 daemon
        daemons = set()
        for log in self.all_log_messages:
            daemon = log.get('daemon', '')
            if daemon:
                daemons.add(daemon)

        # 更新下拉選單
        current = self.filter_daemon_combo.currentText()
        self.filter_daemon_combo.clear()
        self.filter_daemon_combo.addItem("All")
        for daemon in sorted(daemons):
            self.filter_daemon_combo.addItem(daemon)

        # 恢復選擇
        index = self.filter_daemon_combo.findText(current)
        if index >= 0:
            self.filter_daemon_combo.setCurrentIndex(index)

    def apply_filters(self):
        """應用篩選條件"""
        # 根據篩選條件過濾日誌
        self.filtered_log_messages = []

        for log in self.all_log_messages:
            # 類型篩選
            if self.filter_log_type:
                if log['log_type'] != self.filter_log_type:
                    continue

            # Daemon 篩選
            if self.filter_daemon:
                if log.get('daemon', '') != self.filter_daemon:
                    continue

            # 關鍵字篩選
            if self.filter_keyword:
                keyword_lower = self.filter_keyword.lower()
                # 搜尋訊息內容、daemon、函數名稱
                message = log.get('message', '') or ''
                daemon = log.get('daemon', '') or ''
                funcname = log.get('funcname', '') or ''

                # 檢查關鍵字是否出現在任一欄位（不分大小寫）
                if (keyword_lower not in message.lower() and
                    keyword_lower not in daemon.lower() and
                    keyword_lower not in funcname.lower()):
                    continue

            # 通過所有篩選
            self.filtered_log_messages.append(log)

        # 更新表格
        self.update_table()

    def on_filter_changed(self):
        """篩選條件改變"""
        # 更新篩選條件
        type_text = self.filter_type_combo.currentText()
        if type_text == "All":
            self.filter_log_type = None
        elif type_text == "Log":
            self.filter_log_type = 'log'
        elif type_text == "Error":
            self.filter_log_type = 'error'

        daemon_text = self.filter_daemon_combo.currentText()
        if daemon_text == "All":
            self.filter_daemon = None
        else:
            self.filter_daemon = daemon_text

        # 更新關鍵字篩選
        self.filter_keyword = self.filter_keyword_input.text().strip()

        # 應用篩選
        self.apply_filters()

    def reset_filters(self):
        """重置所有篩選"""
        self.filter_type_combo.setCurrentIndex(0)  # All
        self.filter_daemon_combo.setCurrentIndex(0)  # All
        self.filter_keyword_input.clear()  # 清空關鍵字
        self.filter_log_type = None
        self.filter_daemon = None
        self.filter_keyword = ""
        self.apply_filters()

    def update_ui_text(self):
        """Update UI text based on current language"""
        if not self.translation_manager:
            return

        t = self.translation_manager.t

        # Update title
        self.title_label.setText(t("System Log Messages"))

        # Update filter labels
        self.type_label.setText(t("Type:"))
        self.daemon_label.setText(t("Daemon:"))
        self.keyword_label.setText(t("Keyword:"))

        # Update filter combo items
        current_type = self.filter_type_combo.currentIndex()
        self.filter_type_combo.blockSignals(True)
        self.filter_type_combo.clear()
        self.filter_type_combo.addItems([t("All"), t("Log"), t("Error")])
        self.filter_type_combo.setCurrentIndex(current_type)
        self.filter_type_combo.blockSignals(False)

        # Update daemon combo "All" item
        current_daemon = self.filter_daemon_combo.currentText()
        items = [self.filter_daemon_combo.itemText(i) for i in range(self.filter_daemon_combo.count())]
        if items and items[0] in ["All", "全部"]:  # Replace "All" with translated version
            self.filter_daemon_combo.blockSignals(True)
            self.filter_daemon_combo.setItemText(0, t("All"))
            # Restore selection if it was "All"
            if current_daemon in ["All", "全部"]:
                self.filter_daemon_combo.setCurrentIndex(0)
            self.filter_daemon_combo.blockSignals(False)

        # Update keyword placeholder
        self.filter_keyword_input.setPlaceholderText(t("Search messages..."))

        # Update reset button
        self.reset_btn.setText(t("Reset"))

        # Update table headers
        self.table.setHorizontalHeaderLabels([
            t("Time"), t("Type"), t("Daemon"), t("Function"), t("Message")
        ])

        # Update stats label
        self.update_stats_label()

    def update_stats_label(self):
        """Update stats label with current language"""
        if not self.translation_manager:
            self.stats_label.setText(f"Total: {len(self.filtered_log_messages)} entries (All: {len(self.all_log_messages)} entries)")
            return

        t = self.translation_manager.t
        text = t("Total: {0} entries (All: {1} entries)").replace("{0}", str(len(self.filtered_log_messages))).replace("{1}", str(len(self.all_log_messages)))
        self.stats_label.setText(text)

    def update_table(self):
        """更新資料表內容 - 顯示篩選後的日誌訊息"""
        try:
            log_messages = self.filtered_log_messages

            # 更新統計標籤
            self.update_stats_label()

            # 禁用排序以避免更新時閃爍
            self.table.setSortingEnabled(False)
            self.table.setRowCount(len(log_messages))

            from PyQt6.QtGui import QColor, QBrush

            for i, log in enumerate(log_messages):
                # 計算相對時間（從 segment 開始），與影片和圖表一致
                relative_time_ns = log['time_ns'] - self.segment_start_time_ns
                time_s = relative_time_ns / 1e9

                # 格式化為 MM:SS.mmm 格式
                minutes = int(time_s // 60)
                seconds = time_s % 60
                time_str = f"{minutes:02d}:{seconds:06.3f}"

                # 日誌類型
                if self.translation_manager:
                    t = self.translation_manager.t
                    log_type = t("Error") if log['log_type'] == 'error' else t("Log")
                else:
                    log_type = "Error" if log['log_type'] == 'error' else "Log"

                # Daemon
                daemon = log.get('daemon', '') or ''

                # 函數資訊
                funcname = log.get('funcname', '') or ''
                filename = log.get('filename', '') or ''
                lineno = log.get('lineno', None)

                if funcname:
                    if lineno:
                        func_str = f"{funcname}:{lineno}"
                    else:
                        func_str = funcname
                else:
                    func_str = ''

                # 訊息內容
                message = log.get('message', '') or ''

                # 創建表格項目
                time_item = QTableWidgetItem(time_str)
                type_item = QTableWidgetItem(log_type)
                daemon_item = QTableWidgetItem(daemon)
                func_item = QTableWidgetItem(func_str)
                msg_item = QTableWidgetItem(message)

                # 錯誤訊息用紅色顯示
                if log['log_type'] == 'error':
                    error_color = QBrush(QColor(220, 50, 50))
                    time_item.setForeground(error_color)
                    type_item.setForeground(error_color)
                    daemon_item.setForeground(error_color)
                    func_item.setForeground(error_color)
                    msg_item.setForeground(error_color)

                # 設置 tooltip 顯示完整資訊
                tooltip = f"Time: {time_str}\nType: {log_type}\nDaemon: {daemon}\n"
                if filename:
                    tooltip += f"File: {filename}\n"
                if funcname:
                    tooltip += f"Function: {funcname}\n"
                if lineno:
                    tooltip += f"Line: {lineno}\n"
                tooltip += f"\nMessage:\n{message}"

                for item in [time_item, type_item, daemon_item, func_item, msg_item]:
                    item.setToolTip(tooltip)

                self.table.setItem(i, 0, time_item)
                self.table.setItem(i, 1, type_item)
                self.table.setItem(i, 2, daemon_item)
                self.table.setItem(i, 3, func_item)
                self.table.setItem(i, 4, msg_item)

            # 重新啟用排序
            self.table.setSortingEnabled(True)

        except Exception as e:
            logger.error(f"Failed to update data table: {e}")
            import traceback
            logger.error(traceback.format_exc())
