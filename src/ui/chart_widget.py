# -*- coding: utf-8 -*-
"""
Chart Widget - Multi-signal overlay chart
圖表區元件 - 多訊號疊加圖表
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel,
                             QMenu, QInputDialog)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
import logging
from typing import List, Dict

try:
    import pyqtgraph as pg
    import numpy as np
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    logging.warning("pyqtgraph not available, charts will not work")

logger = logging.getLogger(__name__)


class ChartWidget(QWidget):
    """
    圖表區 Widget

    功能:
    - 單一圖表
    - 多訊號疊加
    - 不同顏色
    - ±10 秒視窗
    - 滑鼠 hover 顯示數值
    - 當前位置垂直線
    """

    # 信號：圖表更新完成
    charts_updated = pyqtSignal()

    def __init__(self, parent=None, translation_manager=None):
        super().__init__(parent)

        self.db_manager = None
        self.current_segment_id = None
        self.current_time_ns = 0
        self.segment_start_time_ns = None  # Segment 起始時間（理論值，從 segments 表）
        self.segment_end_time_ns = None    # Segment 結束時間（理論值，從 segments 表）
        self.actual_data_end_time_ns = None  # 實際數據的結束時間（從 timeseries_data 查詢）
        self.segment_start_timestamp = None  # Segment 的實際起始時間（Unix timestamp）
        self.selected_signals: List[str] = []
        self.signal_colors: Dict[str, str] = {}
        # 存儲當前繪製的資料，用於滑鼠 hover 查找
        self.plot_data: Dict[str, List[tuple]] = {}  # {signal_name: [(time_ns, value)]}

        # 主題設定
        self.is_dark_theme = False

        # 播放狀態（用於控制十字線顯示）
        self.is_playing = False

        # 播放優化：跳幀更新（每 N 幀更新一次圖表）
        self.frame_skip_interval = 3  # 每 3 幀更新一次
        self.frame_counter = 0

        # 雙 Y 軸設定
        self.use_dual_y_axis = True  # 預設啟用自動雙 Y 軸
        self.viewbox_right = None  # 右側 Y 軸的 ViewBox

        # Translation manager
        self.translation_manager = translation_manager

        # Chart name (will be set by set_chart_name)
        self.chart_name = "Signals"

        self.setup_ui()

    def setup_ui(self):
        """建立 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        if not PYQTGRAPH_AVAILABLE:
            error_label = QLabel("pyqtgraph 未安裝，無法顯示圖表\n\n請執行: pip install pyqtgraph")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setStyleSheet("color: red; font-size: 12pt;")
            layout.addWidget(error_label)
            return

        # 標題
        self.title_label = QLabel("Signals (±10 s)")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        layout.addWidget(self.title_label)

        # pyqtgraph PlotWidget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('left', 'Value')
        self.plot_widget.setLabel('bottom', 'Time', units='s')

        # 啟用滑鼠互動功能
        self.plot_widget.setMouseEnabled(x=False, y=True)  # X 軸固定，Y 軸可縮放
        self.plot_widget.enableAutoRange(axis='y')  # Y 軸自動範圍
        self.plot_widget.disableAutoRange(axis='x')  # 禁用 X 軸自動範圍
        vb = self.plot_widget.getPlotItem().getViewBox()
        vb.setMouseMode(vb.RectMode)

        # 當前位置垂直線（紅色）
        self.vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('r', width=2))
        self.plot_widget.addItem(self.vline)

        # Crosshair 十字線（黑色虛線）
        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False,
                                          pen=pg.mkPen('k', width=1, style=Qt.PenStyle.DashLine))
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False,
                                          pen=pg.mkPen('k', width=1, style=Qt.PenStyle.DashLine))
        self.plot_widget.addItem(self.crosshair_v, ignoreBounds=True)
        self.plot_widget.addItem(self.crosshair_h, ignoreBounds=True)
        # 初始化時移到範圍外（隱藏）
        self.crosshair_v.setPos(-1000)
        self.crosshair_h.setPos(-1000)

        # 數值標籤（anchor=(0, 0) 表示左上角對齊，這樣 label 會從設定位置向下延伸）
        self.label = pg.TextItem(anchor=(0, 0), color='k', fill=(255, 255, 255, 200))
        self.plot_widget.addItem(self.label, ignoreBounds=True)  # 不影響圖表範圍
        self.label.setVisible(False)

        # 滑鼠移動事件
        self.plot_widget.scene().sigMouseMoved.connect(self.on_mouse_moved)
        self.plot_widget.setMouseTracking(True)

        layout.addWidget(self.plot_widget)

        # 設定右鍵選單
        self.setup_context_menu()

    def set_database_manager(self, db_manager):
        """設定資料庫管理器"""
        self.db_manager = db_manager

    def set_playing_state(self, is_playing: bool):
        """
        設定播放狀態

        Args:
            is_playing: True=播放中，False=暫停
        """
        self.is_playing = is_playing
        # 如果正在播放，立即隱藏十字線和 tooltip
        if is_playing and PYQTGRAPH_AVAILABLE:
            self.crosshair_v.setPos(-1000)
            self.crosshair_h.setPos(-1000)
            self.label.setVisible(False)

    def set_chart_name(self, name: str):
        """設定圖表名稱"""
        self.chart_name = name
        if self.translation_manager:
            t = self.translation_manager.t
            self.title_label.setText(f"{name} {t('(±10 s)')}")
        else:
            self.title_label.setText(f"{name} (±10 s)")

    def update_ui_text(self):
        """Update UI text based on current language"""
        if not self.translation_manager:
            return

        t = self.translation_manager.t

        # Update chart title
        self.title_label.setText(f"{self.chart_name} {t('(±10 s)')}")

    def set_segment(self, segment_id: int):
        """設定當前 Segment"""
        self.current_segment_id = segment_id

        # 取得 segment 的時間範圍和實際時間
        segment = self.db_manager.get_segment_by_id(segment_id) if self.db_manager else None
        if segment:
            self.segment_start_time_ns = segment['start_time_ns']
            self.segment_end_time_ns = segment['end_time_ns']

            # 診斷日誌：輸出 segment 時間範圍
            logger.info(f"📊 Segment {segment_id} time range:")
            logger.info(f"   start_time_ns: {self.segment_start_time_ns}")
            logger.info(f"   end_time_ns: {self.segment_end_time_ns}")
            logger.info(f"   duration: {(self.segment_end_time_ns - self.segment_start_time_ns) / 1e9:.2f} 秒")

            # 獲取 route 的 start_timestamp 來計算實際時間
            try:
                cursor = self.db_manager.conn.cursor()
                cursor.execute("""
                    SELECT r.start_timestamp, s.segment_number
                    FROM routes r
                    JOIN segments s ON r.route_id = s.route_id
                    WHERE s.segment_id = ?
                """, (segment_id,))
                result = cursor.fetchone()
                cursor.close()
                if result and result[0]:
                    route_start_timestamp, segment_num = result
                    # 計算此 segment 的實際起始時間
                    self.segment_start_timestamp = route_start_timestamp + (segment_num * 60)
                else:
                    self.segment_start_timestamp = None
            except Exception as e:
                logger.error(f"Failed to get segment actual time: {e}")
                self.segment_start_timestamp = None
        else:
            self.segment_start_time_ns = None
            self.segment_end_time_ns = None
            self.actual_data_end_time_ns = None
            self.segment_start_timestamp = None

        # 設置初始播放時間（使用實際數據的開始時間，但不覆蓋 segment 的時間範圍）
        if self.db_manager:
            try:
                # 查詢實際數據的最小和最大時間戳記（用於診斷）
                cursor = self.db_manager.conn.cursor()
                cursor.execute("""
                    SELECT MIN(time_ns), MAX(time_ns)
                    FROM timeseries_data
                    WHERE segment_id = ?
                """, (segment_id,))
                result = cursor.fetchone()
                cursor.close()
                if result and result[0]:
                    data_start_ns = result[0]
                    data_end_ns = result[1]

                    # 保存實際數據的結束時間
                    self.actual_data_end_time_ns = data_end_ns

                    # 診斷日誌：輸出實際數據的時間範圍
                    logger.info(f"📈 Actual data time range:")
                    logger.info(f"   data_start_ns: {data_start_ns}")
                    logger.info(f"   data_end_ns: {data_end_ns}")
                    logger.info(f"   data duration: {(data_end_ns - data_start_ns) / 1e9:.2f} 秒")

                    # 檢查數據是否超出 segment 範圍
                    if self.segment_start_time_ns and data_start_ns < self.segment_start_time_ns:
                        logger.warning(f"⚠️  Data start time is {(self.segment_start_time_ns - data_start_ns) / 1e9:.2f} seconds earlier than segment start time")
                    if self.segment_end_time_ns and data_end_ns > self.segment_end_time_ns:
                        logger.warning(f"⚠️  Data end time is {(data_end_ns - self.segment_end_time_ns) / 1e9:.2f} seconds later than segment end time")
                    elif self.segment_end_time_ns and data_end_ns < self.segment_end_time_ns:
                        logger.warning(f"⚠️  Data end time is {(self.segment_end_time_ns - data_end_ns) / 1e9:.2f} seconds earlier than segment theoretical end time")

                    # 設置為實際數據開始時間（但保持 segment 的時間範圍不變）
                    self.current_time_ns = data_start_ns
                else:
                    # 如果沒有數據，使用 segment 的時間
                    if segment:
                        self.current_time_ns = segment['start_time_ns']
            except Exception as e:
                logger.error(f"Failed to get data time range: {e}")
                # 錯誤時使用 segment 的時間
                if segment:
                    self.current_time_ns = segment['start_time_ns']

    def set_signals(self, signal_names: List[str], signal_colors: Dict[str, str]):
        """
        設定要顯示的訊號

        Args:
            signal_names: 訊號名稱列表
            signal_colors: 訊號顏色對應 {signal_name: color_hex}
        """
        self.selected_signals = signal_names
        self.signal_colors = signal_colors
        self.update_charts()

    def get_current_signals(self) -> List[str]:
        """取得當前顯示的訊號列表"""
        return self.selected_signals.copy() if self.selected_signals else []

    def update_time_window(self, time_ns: int):
        """更新時間視窗"""
        self.current_time_ns = time_ns

        if PYQTGRAPH_AVAILABLE:
            # 更新垂直線位置 (相對於視窗中心)
            self.vline.setPos(0)

        # 播放時跳幀更新（優化效能）
        if self.is_playing:
            self.frame_counter += 1
            if self.frame_counter >= self.frame_skip_interval:
                self.frame_counter = 0
                self.update_charts()
            # 即使跳過更新也發送信號，避免阻塞播放
            self.charts_updated.emit()
        else:
            # 暫停時正常更新
            self.frame_counter = 0  # 重置計數器
            self.update_charts()
            self.charts_updated.emit()

    def _should_use_dual_y_axis(self, signal_data: Dict[str, List[tuple]]) -> bool:
        """
        判斷是否應該使用雙 Y 軸

        Args:
            signal_data: {signal_name: [(time_ns, value), ...]}

        Returns:
            True 如果應該使用雙 Y 軸
        """
        # 播放時減少 logging（優化效能）
        verbose_log = not self.is_playing

        if not self.use_dual_y_axis:
            if verbose_log:
                logger.info(f"Dual Y-axis feature disabled")
            return False

        if len(signal_data) < 2:
            if verbose_log:
                logger.info(f"Signal count < 2, not using dual Y-axis")
            return False

        # 計算每個訊號的數值範圍
        ranges = {}
        for signal_name, data in signal_data.items():
            if data:
                values = [v for _, v in data]
                value_min = min(values)
                value_max = max(values)
                value_range = value_max - value_min
                ranges[signal_name] = (value_min, value_max)
                if verbose_log:
                    logger.info(f"📊 Signal {signal_name}: min={value_min:.3f}, max={value_max:.3f}, range={value_range:.3f}")

        if len(ranges) < 2:
            if verbose_log:
                logger.info(f"Valid signal ranges < 2, not using dual Y-axis")
            return False

        # 計算全局範圍（所有訊號合併後的範圍）
        global_min = min(r[0] for r in ranges.values())
        global_max = max(r[1] for r in ranges.values())
        global_range = global_max - global_min

        if verbose_log:
            logger.info(f"📊 Global range: min={global_min:.3f}, max={global_max:.3f}, range={global_range:.3f}")

        if global_range == 0:
            if verbose_log:
                logger.info(f"Global range is 0, not using dual Y-axis")
            return False

        # 檢查每個訊號的範圍佔全局範圍的比例
        # 如果某個訊號的範圍佔比太小（< 10%），則應該用雙 Y 軸避免被壓縮
        for signal_name, (vmin, vmax) in ranges.items():
            signal_range = vmax - vmin
            ratio = signal_range / global_range
            if verbose_log:
                logger.info(f"📊 Signal {signal_name} range ratio: {ratio*100:.1f}%")

            if ratio < 0.1:  # 佔比小於 10%
                if verbose_log:
                    logger.info(f"✅ Enabling dual Y-axis: signal {signal_name} range ratio only {ratio*100:.1f}%, would be compressed")
                return True

        if verbose_log:
            logger.info(f"❌ Not using dual Y-axis: all signal range ratios >= 10%")
        return False

    def update_charts(self):
        """更新圖表內容"""
        if not PYQTGRAPH_AVAILABLE:
            return

        if not self.db_manager or not self.current_segment_id or not self.selected_signals:
            self.plot_widget.clear()
            return

        try:
            # ±10 秒視窗
            window_ns = 10 * 1_000_000_000
            start_time_ns = self.current_time_ns - window_ns
            end_time_ns = self.current_time_ns + window_ns

            # 限制查詢範圍不超過 segment 的實際時間範圍
            if self.segment_start_time_ns is not None:
                start_time_ns = max(start_time_ns, self.segment_start_time_ns)
            if self.segment_end_time_ns is not None:
                end_time_ns = min(end_time_ns, self.segment_end_time_ns)

            # 清空圖表
            self.plot_widget.clear()

            # 移除舊的右側 ViewBox（如果存在）
            if self.viewbox_right is not None:
                self.plot_widget.getPlotItem().scene().removeItem(self.viewbox_right)
                self.viewbox_right = None

            # 重新加入所有永久元素
            self.plot_widget.addItem(self.vline, ignoreBounds=True)  # 紅色垂直線不影響範圍
            self.plot_widget.addItem(self.crosshair_v, ignoreBounds=True)
            self.plot_widget.addItem(self.crosshair_h, ignoreBounds=True)
            self.plot_widget.addItem(self.label, ignoreBounds=True)

            # 清空存儲的資料
            self.plot_data = {}

            # 批次查詢所有訊號的資料（優化：一次查詢而非多次）
            all_data = self.db_manager.get_timeseries_data(
                self.current_segment_id,
                self.selected_signals,  # 傳入列表
                start_time_ns,
                end_time_ns
            )

            # 轉換資料格式
            all_signal_data = {}
            for signal_name, data in all_data.items():
                if data:
                    # 轉換為相對時間 (秒，相對於當前時間)，並過濾 None 值
                    times = []
                    values = []
                    raw_data = []  # 存儲原始資料 (time_ns, value)
                    for row in data:
                        if row[1] is not None:
                            times.append((row[0] - self.current_time_ns) / 1e9)
                            values.append(row[1])
                            raw_data.append((row[0], row[1]))

                    if times and values:
                        all_signal_data[signal_name] = {
                            'times': times,
                            'values': values,
                            'raw_data': raw_data
                        }
                        # 存儲原始資料供 hover 使用
                        self.plot_data[signal_name] = raw_data

            # 判斷是否使用雙 Y 軸
            use_dual = self._should_use_dual_y_axis(self.plot_data)

            if use_dual and len(all_signal_data) >= 2:
                # 使用雙 Y 軸
                self._plot_with_dual_y_axis(all_signal_data)
            else:
                # 使用單 Y 軸
                self._plot_with_single_y_axis(all_signal_data)

            # 設定 X 軸範圍
            self._set_x_axis_range()

        except Exception as e:
            logger.error(f"Failed to update charts: {e}")

    def _plot_with_single_y_axis(self, signal_data: Dict):
        """使用單 Y 軸繪製所有訊號"""
        for signal_name, data in signal_data.items():
            color = self.signal_colors.get(signal_name, '#000000')
            pen = pg.mkPen(color=color, width=2)
            self.plot_widget.plot(data['times'], data['values'], pen=pen, name=signal_name)

        # 隱藏右側 Y 軸
        self.plot_widget.showAxis('right', False)

    def _plot_with_dual_y_axis(self, signal_data: Dict):
        """使用雙 Y 軸繪製訊號"""
        signal_names = list(signal_data.keys())

        # 計算每個訊號的數值範圍，找出範圍最大的訊號
        ranges = {}
        for name, data in signal_data.items():
            values = data['values']
            ranges[name] = max(values) - min(values)

        # 將範圍最大的訊號放在左側 Y 軸，其他放在右側
        sorted_signals = sorted(signal_names, key=lambda x: ranges[x], reverse=True)
        left_signals = [sorted_signals[0]]
        right_signals = sorted_signals[1:]

        # 繪製左側 Y 軸的訊號
        for signal_name in left_signals:
            data = signal_data[signal_name]
            color = self.signal_colors.get(signal_name, '#000000')
            pen = pg.mkPen(color=color, width=2)
            self.plot_widget.plot(data['times'], data['values'], pen=pen, name=signal_name)

        # 設定左側 Y 軸標籤
        if len(left_signals) == 1:
            self.plot_widget.setLabel('left', left_signals[0], color='k')

        # 創建右側 Y 軸
        self.viewbox_right = pg.ViewBox()
        self.plot_widget.showAxis('right')
        self.plot_widget.scene().addItem(self.viewbox_right)
        self.plot_widget.getPlotItem().getAxis('right').linkToView(self.viewbox_right)
        self.viewbox_right.setXLink(self.plot_widget.getPlotItem())

        # 繪製右側 Y 軸的訊號
        for signal_name in right_signals:
            data = signal_data[signal_name]
            color = self.signal_colors.get(signal_name, '#000000')
            pen = pg.mkPen(color=color, width=2)
            curve = pg.PlotCurveItem(data['times'], data['values'], pen=pen, name=signal_name)
            self.viewbox_right.addItem(curve)

        # 設定右側 Y 軸標籤
        if len(right_signals) == 1:
            self.plot_widget.setLabel('right', right_signals[0], color='k')
        else:
            self.plot_widget.setLabel('right', f'{len(right_signals)} 個訊號', color='k')

        # 同步更新右側 ViewBox 的大小
        def update_views():
            # 檢查 viewbox_right 是否存在（防止切換到單 Y 軸後仍觸發此函數）
            if self.viewbox_right is not None:
                self.viewbox_right.setGeometry(self.plot_widget.getPlotItem().vb.sceneBoundingRect())
                self.viewbox_right.linkedViewChanged(self.plot_widget.getPlotItem().vb, self.viewbox_right.XAxis)

        update_views()
        self.plot_widget.getPlotItem().vb.sigResized.connect(update_views)

        # 啟用右側 Y 軸的自動範圍
        self.viewbox_right.enableAutoRange(axis=pg.ViewBox.YAxis)

    def _set_x_axis_range(self):
        """設定 X 軸範圍"""
        # 計算實際的 X 軸範圍（基於實際數據範圍）
        x_min = -10.0
        x_max = 10.0

        # 如果接近 segment 開始，調整左邊界
        if self.segment_start_time_ns is not None:
            time_from_start = (self.current_time_ns - self.segment_start_time_ns) / 1e9
            if time_from_start < 10:
                x_min = -time_from_start

        # 如果接近 segment 結束，調整右邊界
        # 優先使用實際數據的結束時間，如果沒有則使用 segment 的理論結束時間
        effective_end_time_ns = self.actual_data_end_time_ns if self.actual_data_end_time_ns else self.segment_end_time_ns

        if effective_end_time_ns is not None:
            time_to_end = (effective_end_time_ns - self.current_time_ns) / 1e9
            if time_to_end < 10:
                x_max = time_to_end

        # 診斷日誌：輸出 X 軸範圍計算
        logger.info(f"📐 X-axis range calculation:")
        logger.info(f"   current_time_ns: {self.current_time_ns}")
        logger.info(f"   segment_start_time_ns: {self.segment_start_time_ns}")
        logger.info(f"   segment_end_time_ns: {self.segment_end_time_ns}")
        logger.info(f"   actual_data_end_time_ns: {self.actual_data_end_time_ns}")
        logger.info(f"   effective_end_time_ns: {effective_end_time_ns}")
        if self.segment_start_time_ns:
            logger.info(f"   time_from_start: {(self.current_time_ns - self.segment_start_time_ns) / 1e9:.2f} 秒")
        if effective_end_time_ns:
            logger.info(f"   time_to_end: {(effective_end_time_ns - self.current_time_ns) / 1e9:.2f} 秒")
        logger.info(f"   x_min: {x_min:.2f}, x_max: {x_max:.2f}")

        # 設定 X 軸範圍（padding=0 確保精確範圍，不會有額外空間）
        self.plot_widget.setXRange(x_min, x_max, padding=0)

    def on_mouse_moved(self, pos):
        """滑鼠移動事件處理"""
        if not PYQTGRAPH_AVAILABLE:
            return

        # 只在暫停時顯示十字線和 tooltip
        if self.is_playing:
            return

        try:
            vb = self.plot_widget.plotItem.vb
            if vb.sceneBoundingRect().contains(pos):
                mouse_point = vb.mapSceneToView(pos)
                x = mouse_point.x()  # 相對時間（秒）

                # 更新十字線位置（只顯示垂直線）
                self.crosshair_v.setPos(x)
                self.crosshair_h.setVisible(False)

                # 計算絕對時間
                hover_time_ns = self.current_time_ns + int(x * 1e9)

                # 建立標籤文字
                label_lines = []

                # 顯示完整時間
                if self.segment_start_timestamp:
                    from datetime import datetime
                    # 計算實際時間
                    offset_from_segment_start = (hover_time_ns - self.segment_start_time_ns) / 1e9
                    actual_timestamp = self.segment_start_timestamp + offset_from_segment_start
                    dt = datetime.fromtimestamp(actual_timestamp)
                    time_str = dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                else:
                    time_str = f"{x:+.2f}s"

                label_lines.append(f"<b>{time_str}</b>")

                # 查找所有訊號在該時間點的數值
                for signal_name, data in self.plot_data.items():
                    # 找最接近的點
                    closest_value = None
                    min_diff = float('inf')
                    for time_ns, value in data:
                        diff = abs(time_ns - hover_time_ns)
                        if diff < min_diff:
                            min_diff = diff
                            closest_value = value

                    if closest_value is not None and min_diff < 1e9:  # 1秒內
                        color = self.signal_colors.get(signal_name, '#000000')
                        label_lines.append(f"<span style='color: {color};'>{signal_name}: {closest_value:.3f}</span>")

                # 組合標籤
                if len(label_lines) > 1:
                    label_text = "<div style='background-color: rgba(255, 255, 255, 200); padding: 4px; border: 1px solid black;'>" + "<br>".join(label_lines) + "</div>"
                else:
                    label_text = f"<div style='background-color: rgba(255, 255, 255, 200); padding: 4px; border: 1px solid black;'><b>{time_str}</b></div>"

                # 設定 label 位置（使用滑鼠 Y 座標）
                y = mouse_point.y()

                self.label.setHtml(label_text)
                self.label.setPos(x, y)  # 跟隨滑鼠位置
                self.label.setVisible(True)
            else:
                # 滑鼠移出圖表範圍，隱藏十字線
                self.crosshair_v.setPos(-1000)
                self.crosshair_h.setPos(-1000)
                self.label.setVisible(False)
        except Exception as e:
            logger.error(f"❌ Mouse event error: {e}")
            self.crosshair_v.setPos(-1000)
            self.crosshair_h.setPos(-1000)
            self.label.setVisible(False)

    def setup_context_menu(self):
        """設定圖表右鍵選單"""
        if not PYQTGRAPH_AVAILABLE:
            return

        # 禁用 pyqtgraph 預設的右鍵選單
        self.plot_widget.getPlotItem().getViewBox().setMenuEnabled(False)

        # 設定自訂右鍵選單
        self.plot_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.plot_widget.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        """顯示圖表右鍵選單"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        menu = QMenu()

        # 切換雙 Y 軸
        toggle_dual_y_action = QAction(t("Enable Auto Dual Y-Axis"), self)
        toggle_dual_y_action.setCheckable(True)
        toggle_dual_y_action.setChecked(self.use_dual_y_axis)
        toggle_dual_y_action.triggered.connect(self.toggle_dual_y_axis)
        menu.addAction(toggle_dual_y_action)

        menu.addSeparator()

        # 設定 Y 軸範圍
        set_y_range_action = QAction(t("Set Y-Axis Range..."), self)
        set_y_range_action.triggered.connect(self.set_y_range_dialog)
        menu.addAction(set_y_range_action)

        # 自動 Y 軸範圍
        auto_y_range_action = QAction(t("Auto Y-Axis Range"), self)
        auto_y_range_action.triggered.connect(
            lambda: self.plot_widget.enableAutoRange(axis='y')
        )
        menu.addAction(auto_y_range_action)

        menu.addSeparator()

        # 重置視圖
        reset_view_action = QAction(t("Reset View"), self)
        reset_view_action.triggered.connect(self.reset_view)
        menu.addAction(reset_view_action)

        # 顯示選單
        menu.exec(self.plot_widget.mapToGlobal(pos))

    def toggle_dual_y_axis(self):
        """切換雙 Y 軸模式"""
        self.use_dual_y_axis = not self.use_dual_y_axis
        logger.info(f"Dual Y-axis mode: {'enabled' if self.use_dual_y_axis else 'disabled'}")
        # 重新繪製圖表
        self.update_charts()

    def set_y_range_dialog(self):
        """顯示設定 Y 軸範圍對話框"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        # 取得當前 Y 軸範圍
        view_range = self.plot_widget.viewRange()
        current_min, current_max = view_range[1]

        # 輸入最小值
        y_min, ok1 = QInputDialog.getDouble(
            self,
            t("Set Y-Axis Range..."),
            t("Minimum:"),
            value=current_min,
            decimals=3
        )

        if not ok1:
            return

        # 輸入最大值
        y_max, ok2 = QInputDialog.getDouble(
            self,
            t("Set Y-Axis Range..."),
            t("Maximum:"),
            value=current_max,
            decimals=3
        )

        if not ok2:
            return

        # 設定 Y 軸範圍
        if y_min < y_max:
            self.plot_widget.setYRange(y_min, y_max, padding=0)
        else:
            logger.warning(f"Invalid Y range: min={y_min}, max={y_max}")

    def reset_view(self):
        """重置視圖"""
        # X 軸固定在 ±10 秒
        self.plot_widget.setXRange(-10, 10)
        # Y 軸自動範圍
        self.plot_widget.enableAutoRange(axis='y')

    def set_theme(self, is_dark: bool):
        """
        設定圖表主題

        Args:
            is_dark: True=暗色主題，False=淺色主題
        """
        if not PYQTGRAPH_AVAILABLE:
            return

        self.is_dark_theme = is_dark

        if is_dark:
            # 暗色主題
            bg_color = '#1e1e1e'
            fg_color = '#cccccc'
            grid_alpha = 0.2
        else:
            # 淺色主題
            bg_color = 'w'
            fg_color = 'k'
            grid_alpha = 0.3

        # 設定背景色
        self.plot_widget.setBackground(bg_color)

        # 更新十字線顏色
        self.crosshair_v.setPen(pg.mkPen(fg_color, width=1, style=Qt.PenStyle.DashLine))
        self.crosshair_h.setPen(pg.mkPen(fg_color, width=1, style=Qt.PenStyle.DashLine))

        # 更新標籤顏色
        self.label.setColor(fg_color)

        # 更新網格透明度
        self.plot_widget.showGrid(x=True, y=True, alpha=grid_alpha)

        # 更新軸標籤顏色
        self.plot_widget.getAxis('left').setPen(fg_color)
        self.plot_widget.getAxis('left').setTextPen(fg_color)
        self.plot_widget.getAxis('bottom').setPen(fg_color)
        self.plot_widget.getAxis('bottom').setTextPen(fg_color)
