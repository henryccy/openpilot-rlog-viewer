# -*- coding: utf-8 -*-
"""
Export Data Dialog - Export signal data to CSV or Parquet
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QRadioButton, QButtonGroup, QGroupBox,
    QLineEdit, QFileDialog, QCheckBox, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import logging
from typing import List, Dict
import csv
from pathlib import Path

logger = logging.getLogger(__name__)


class ExportWorker(QThread):
    """Export data worker thread"""
    progress = pyqtSignal(int, str)  # Progress percentage, status message
    finished = pyqtSignal(bool, str)  # Success status, message

    def __init__(self, db_manager, segment_id, signal_names, time_range,
                 export_path, export_format):
        super().__init__()
        self.db_manager = db_manager
        self.segment_id = segment_id
        self.signal_names = signal_names
        self.time_range = time_range  # (start_ns, end_ns) or None for all
        self.export_path = export_path
        self.export_format = export_format  # 'csv' or 'parquet'

    def run(self):
        """Execute export"""
        try:
            self.progress.emit(0, "準備匯出資料...")

            # Get segment info
            segment = self.db_manager.get_segment_by_id(self.segment_id)
            if not segment:
                self.finished.emit(False, "找不到 Segment 資料")
                return

            segment_start_time_ns = segment['start_time_ns']

            self.progress.emit(10, f"查詢 {len(self.signal_names)} 個訊號資料...")

            # Query data
            all_data = {}
            for i, signal_name in enumerate(self.signal_names):
                # Get signal data
                data = self.db_manager.get_signal_data(
                    self.segment_id,
                    signal_name,
                    self.time_range[0] if self.time_range else None,
                    self.time_range[1] if self.time_range else None
                )

                all_data[signal_name] = data

                # Update progress
                progress_pct = 10 + int((i + 1) / len(self.signal_names) * 40)
                self.progress.emit(progress_pct, f"已查詢 {i+1}/{len(self.signal_names)} 個訊號")

            self.progress.emit(50, "整理資料格式...")

            # Find all unique time points
            all_times = set()
            for signal_data in all_data.values():
                for time_ns, _ in signal_data:
                    all_times.add(time_ns)

            sorted_times = sorted(all_times)

            if not sorted_times:
                self.finished.emit(False, "沒有資料可以匯出")
                return

            self.progress.emit(60, f"準備匯出 {len(sorted_times)} 筆資料...")

            # Export based on format
            if self.export_format == 'csv':
                self._export_csv(all_data, sorted_times, segment_start_time_ns)
            elif self.export_format == 'parquet':
                self._export_parquet(all_data, sorted_times, segment_start_time_ns)

            self.progress.emit(100, "匯出完成！")
            self.finished.emit(True, f"成功匯出 {len(sorted_times)} 筆資料")

        except Exception as e:
            logger.error(f"Export data failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.finished.emit(False, f"匯出失敗: {str(e)}")

    def _export_csv(self, all_data, sorted_times, segment_start_time_ns):
        """Export to CSV format"""
        self.progress.emit(70, "寫入 CSV 檔案...")

        with open(self.export_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)

            # Write header row
            header = ['time_ns', 'relative_time_s'] + self.signal_names
            writer.writerow(header)

            # Create time->value mapping for each signal
            signal_maps = {}
            for signal_name, data in all_data.items():
                signal_maps[signal_name] = {time_ns: value for time_ns, value in data}

            # Write data rows
            total = len(sorted_times)
            for i, time_ns in enumerate(sorted_times):
                relative_time_s = (time_ns - segment_start_time_ns) / 1e9

                row = [time_ns, f"{relative_time_s:.6f}"]
                for signal_name in self.signal_names:
                    value = signal_maps[signal_name].get(time_ns, '')
                    row.append(value if value != '' else '')

                writer.writerow(row)

                # Update progress
                if i % 1000 == 0:
                    progress_pct = 70 + int((i + 1) / total * 25)
                    self.progress.emit(progress_pct, f"寫入中... {i+1}/{total}")

        logger.info(f"CSV export complete: {self.export_path}")

    def _export_parquet(self, all_data, sorted_times, segment_start_time_ns):
        """Export to Parquet format"""
        try:
            import pandas as pd
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as e:
            raise ImportError(
                "需要安裝 pandas 和 pyarrow 才能匯出 Parquet 格式\n"
                "請執行: pip install pandas pyarrow"
            ) from e

        self.progress.emit(70, "準備 DataFrame...")

        # Create data dictionary
        data_dict = {
            'time_ns': sorted_times,
            'relative_time_s': [(t - segment_start_time_ns) / 1e9 for t in sorted_times]
        }

        # 為每個訊號建立時間->值的映射
        signal_maps = {}
        for signal_name, data in all_data.items():
            signal_maps[signal_name] = {time_ns: value for time_ns, value in data}

        # Fill data for each signal
        for signal_name in self.signal_names:
            signal_map = signal_maps[signal_name]
            data_dict[signal_name] = [signal_map.get(t, None) for t in sorted_times]

        self.progress.emit(80, "建立 DataFrame...")
        df = pd.DataFrame(data_dict)

        self.progress.emit(90, "寫入 Parquet 檔案...")
        df.to_parquet(self.export_path, compression='snappy', index=False)

        logger.info(f"Parquet export complete: {self.export_path}")


class ExportDataDialog(QDialog):
    """Export Data Dialog"""

    def __init__(self, parent=None, db_manager=None, segment_id=None,
                 current_signals=None, translation_manager=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.segment_id = segment_id
        self.current_signals = current_signals or []
        self.translation_manager = translation_manager

        self.export_worker = None

        t = self.translation_manager.t if self.translation_manager else lambda x: x
        self.setWindowTitle(t("Export Data"))
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self.setup_ui()

    def setup_ui(self):
        """Setup UI"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x
        layout = QVBoxLayout(self)

        # ============================================================
        # Export format selection
        # ============================================================
        format_group = QGroupBox(t("Export Format"))
        format_layout = QVBoxLayout(format_group)

        self.format_button_group = QButtonGroup(self)

        self.csv_radio = QRadioButton(t("CSV Format (Universal, larger file size)"))
        self.csv_radio.setChecked(True)
        self.format_button_group.addButton(self.csv_radio, 1)
        format_layout.addWidget(self.csv_radio)

        self.parquet_radio = QRadioButton(t("Parquet Format (Efficient compression, smaller file size)"))
        self.format_button_group.addButton(self.parquet_radio, 2)
        format_layout.addWidget(self.parquet_radio)

        layout.addWidget(format_group)

        # ============================================================
        # Signal selection
        # ============================================================
        signal_group = QGroupBox(t("Select Signals"))
        signal_layout = QVBoxLayout(signal_group)

        # Option: Use currently selected signals
        self.use_current_signals_checkbox = QCheckBox(
            t("Use currently selected signals ({0} signals)").format(len(self.current_signals))
        )
        self.use_current_signals_checkbox.setChecked(True)
        self.use_current_signals_checkbox.toggled.connect(self.on_signal_mode_changed)
        signal_layout.addWidget(self.use_current_signals_checkbox)

        # Hint label
        hint_label = QLabel(t("(Uncheck to manually select signals)"))
        hint_label.setStyleSheet("color: gray; font-size: 9pt;")
        signal_layout.addWidget(hint_label)

        # Manual signal selection list
        self.signal_list = QListWidget()
        self.signal_list.setEnabled(False)
        self.signal_list.setMinimumHeight(120)
        self.signal_list.setMaximumHeight(180)
        signal_layout.addWidget(self.signal_list)

        # Load available signals
        if self.db_manager and self.segment_id:
            available_signals = self.db_manager.get_available_signals(self.segment_id)
            for signal in available_signals:
                item = QListWidgetItem(signal)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.signal_list.addItem(item)

        # Shortcut buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.select_all_btn = QPushButton(t("Select All"))
        self.select_all_btn.setEnabled(False)
        self.select_all_btn.clicked.connect(self.select_all_signals)
        button_layout.addWidget(self.select_all_btn)

        self.clear_all_btn = QPushButton(t("Clear"))
        self.clear_all_btn.setEnabled(False)
        self.clear_all_btn.clicked.connect(self.clear_all_signals)
        button_layout.addWidget(self.clear_all_btn)

        signal_layout.addLayout(button_layout)

        layout.addWidget(signal_group)

        # ============================================================
        # Time range selection
        # ============================================================
        time_group = QGroupBox(t("Time Range"))
        time_layout = QVBoxLayout(time_group)

        self.full_segment_checkbox = QCheckBox(t("Export all data from entire Segment"))
        self.full_segment_checkbox.setChecked(True)
        self.full_segment_checkbox.setEnabled(False)  # Currently only supports full export
        time_layout.addWidget(self.full_segment_checkbox)

        # Description text
        time_hint = QLabel(t("(Currently only supports exporting full Segment)"))
        time_hint.setStyleSheet("color: gray; font-size: 9pt;")
        time_layout.addWidget(time_hint)

        layout.addWidget(time_group)

        # ============================================================
        # File path
        # ============================================================
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel(t("Save Location:")))

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText(t("Click 'Browse' to select save location..."))
        self.path_input.setReadOnly(True)
        path_layout.addWidget(self.path_input)

        browse_btn = QPushButton(t("Browse..."))
        browse_btn.clicked.connect(self.browse_save_path)
        path_layout.addWidget(browse_btn)

        layout.addLayout(path_layout)

        # ============================================================
        # Progress label
        # ============================================================
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(self.progress_label)

        # ============================================================
        # Buttons
        # ============================================================
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.export_btn = QPushButton(t("Start Export"))
        self.export_btn.clicked.connect(self.start_export)
        button_layout.addWidget(self.export_btn)

        cancel_btn = QPushButton(t("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def on_signal_mode_changed(self, checked):
        """Signal mode changed"""
        # checked=True means use currently selected signals, disable manual selection
        manual_mode = not checked
        self.signal_list.setEnabled(manual_mode)
        self.select_all_btn.setEnabled(manual_mode)
        self.clear_all_btn.setEnabled(manual_mode)

    def select_all_signals(self):
        """Select all signals"""
        for i in range(self.signal_list.count()):
            item = self.signal_list.item(i)
            item.setCheckState(Qt.CheckState.Checked)

    def clear_all_signals(self):
        """Clear all signal selections"""
        for i in range(self.signal_list.count()):
            item = self.signal_list.item(i)
            item.setCheckState(Qt.CheckState.Unchecked)

    def browse_save_path(self):
        """Browse save path"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        # Determine file extension based on selected format
        if self.csv_radio.isChecked():
            filter_str = t("CSV Files (*.csv)")
            default_ext = ".csv"
        else:
            filter_str = t("Parquet Files (*.parquet)")
            default_ext = ".parquet"

        # Default filename
        segment = self.db_manager.get_segment_by_id(self.segment_id) if self.db_manager else None
        if segment:
            route = self.db_manager.get_route_by_id(segment['route_id'])
            default_name = f"{route['route_name']}_{segment['segment_number']:02d}{default_ext}"
        else:
            default_name = f"export{default_ext}"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            t("Select Save Location"),
            default_name,
            filter_str
        )

        if file_path:
            self.path_input.setText(file_path)

    def start_export(self):
        """Start export"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        # Check if save path is selected
        export_path = self.path_input.text()
        if not export_path:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, t("Error"), t("Please select save location"))
            return

        # Get signals to export
        if self.use_current_signals_checkbox.isChecked():
            signal_names = self.current_signals
        else:
            signal_names = []
            for i in range(self.signal_list.count()):
                item = self.signal_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    signal_names.append(item.text())

        if not signal_names:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, t("Error"), t("Please select at least one signal"))
            return

        # Get export format
        export_format = 'csv' if self.csv_radio.isChecked() else 'parquet'

        # Get time range
        time_range = None  # None = all

        # Disable export button
        self.export_btn.setEnabled(False)
        self.progress_label.setText(t("Preparing..."))

        # Create worker thread
        self.export_worker = ExportWorker(
            self.db_manager,
            self.segment_id,
            signal_names,
            time_range,
            export_path,
            export_format
        )

        self.export_worker.progress.connect(self.on_export_progress)
        self.export_worker.finished.connect(self.on_export_finished)
        self.export_worker.start()

    def on_export_progress(self, percent, message):
        """Export progress update"""
        self.progress_label.setText(f"[{percent}%] {message}")

    def on_export_finished(self, success, message):
        """Export finished"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x
        self.export_btn.setEnabled(True)

        from PyQt6.QtWidgets import QMessageBox
        if success:
            QMessageBox.information(self, t("Success"), message)
            self.accept()
        else:
            QMessageBox.critical(self, t("Failed"), message)
            self.progress_label.setText(t("Export failed: {0}").format(message))
