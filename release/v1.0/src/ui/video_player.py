# -*- coding: utf-8 -*-
"""
Video Player Widget - Supports ecamera/fcamera (HEVC via PyAV) and qcamera (H.264 via OpenCV)
影片播放器元件 - 支援三種相機格式
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSlider, QComboBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
import numpy as np

# Video decoding imports
try:
    import av  # PyAV for HEVC
    PYAV_AVAILABLE = True
except ImportError:
    PYAV_AVAILABLE = False
    logging.warning("PyAV not available, HEVC videos won't play")

try:
    import cv2  # OpenCV for H.264/TS
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logging.warning("OpenCV not available, H.264 videos won't play")

# 不再需要 Cap'n Proto - 幀時間戳記已存在資料庫中

logger = logging.getLogger(__name__)


class VideoPlayer(QWidget):
    """
    影片播放器 Widget

    支援:
    - ecamera: HEVC (PyAV)
    - fcamera: HEVC (PyAV)
    - qcamera: H.264/TS (OpenCV)
    """

    # Signals
    time_changed = pyqtSignal('qint64')  # Current time (ns) - 使用 64 位元整數避免溢位
    frame_changed = pyqtSignal(int)  # Current frame index
    playing_state_changed = pyqtSignal(bool)  # Playing state (True=playing, False=paused)

    def __init__(self, parent=None, db_manager=None, translation_manager=None):
        super().__init__(parent)

        # Database manager (用於讀取幀時間戳記)
        self.db_manager = db_manager

        # Translation manager
        self.translation_manager = translation_manager

        # Video state
        self.camera_paths = {}  # {camera_name: path}
        self.current_camera = None
        self.frames = []  # Preloaded frames
        self.current_frame_idx = 0
        self.fps = 20.0
        self.is_playing = False
        self.sync_mode = True  # 同步模式：等待資料查詢完成才進入下一幀

        # Time synchronization
        self.start_time_ns = 0
        self.wall_time_offset = 0
        self.segment_start_timestamp = None  # Segment 的正確起始時間（Unix timestamp 秒，從 GPS 推算）
        self.segment_num = 0  # Segment 編號
        self.segment_id = None  # Segment ID（從資料庫查詢幀時間戳記用）
        self.frame_timestamps = []  # 每一幀的實際時間戳記（從資料庫讀取）
        self.rlog_path = None  # rlog 檔案路徑（保留以相容性，但不再用於讀取 EncodeIndex）

        # Playback timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.on_timer_tick)

        self.setup_ui()

    def setup_ui(self):
        """建立 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Get translation function
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        # ============================================================
        # 影片顯示區
        # ============================================================
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("border: 1px solid #CCC; background: #000;")
        self.video_label.setMinimumHeight(150)
        self.video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.video_label)

        # ============================================================
        # 時間顯示
        # ============================================================
        time_layout = QHBoxLayout()
        self.time_label = QLabel(t("Time: --"))
        self.time_label.setStyleSheet("font-family: monospace;")
        time_layout.addWidget(self.time_label)

        self.frame_label = QLabel(t("Frame: 0 / 0"))
        self.frame_label.setStyleSheet("font-family: monospace;")
        time_layout.addWidget(self.frame_label)

        time_layout.addStretch()
        layout.addLayout(time_layout)

        # ============================================================
        # 時間軸滑桿
        # ============================================================
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setMinimum(0)
        self.timeline_slider.setMaximum(0)
        self.timeline_slider.valueChanged.connect(self.on_slider_changed)
        layout.addWidget(self.timeline_slider)

        # ============================================================
        # 控制按鈕
        # ============================================================
        control_layout = QHBoxLayout()

        # 相機選擇
        self.camera_label = QLabel(t("Camera:"))
        control_layout.addWidget(self.camera_label)
        self.camera_combo = QComboBox()
        self.camera_combo.addItems(["ecamera", "fcamera", "qcamera"])
        self.camera_combo.setCurrentText("fcamera")  # 預設使用 fcamera
        self.camera_combo.currentTextChanged.connect(self.on_camera_changed)
        control_layout.addWidget(self.camera_combo)

        control_layout.addStretch()

        # 播放/暫停按鈕
        self.play_button = QPushButton(t("Play"))
        self.play_button.clicked.connect(self.toggle_play)
        self.play_button.setEnabled(False)
        control_layout.addWidget(self.play_button)

        # 前一幀
        self.prev_frame_btn = QPushButton(t("◀ 1 Frame"))
        self.prev_frame_btn.clicked.connect(lambda: self.step_frame(-1))
        control_layout.addWidget(self.prev_frame_btn)

        # 後一幀
        self.next_frame_btn = QPushButton(t("1 Frame ▶"))
        self.next_frame_btn.clicked.connect(lambda: self.step_frame(1))
        control_layout.addWidget(self.next_frame_btn)

        # 後退 5 秒
        self.back_5s_btn = QPushButton(t("◀◀ 5s"))
        self.back_5s_btn.clicked.connect(lambda: self.step_time(-5.0))
        control_layout.addWidget(self.back_5s_btn)

        # 前進 5 秒
        self.forward_5s_btn = QPushButton(t("5s ▶▶"))
        self.forward_5s_btn.clicked.connect(lambda: self.step_time(5.0))
        control_layout.addWidget(self.forward_5s_btn)

        control_layout.addStretch()

        layout.addLayout(control_layout)

    def load_segment(self, db_manager, segment_id: int):
        """
        載入指定 Segment 的影片

        Args:
            db_manager: DatabaseManager instance
            segment_id: Segment ID
        """
        try:
            # 儲存 segment_id 和 db_manager（用於讀取幀時間戳記）
            self.segment_id = segment_id
            self.db_manager = db_manager

            # 取得 segment 資訊
            segment = db_manager.get_segment_by_id(segment_id)

            if not segment:
                logger.error(f"Segment {segment_id} not found")
                self.video_label.setText(f"Segment {segment_id} not found")
                return

            # 儲存 segment 編號（支援兩種字段名）
            self.segment_num = segment.get('segment_num') or segment.get('segment_number', 0)

            # 計算 segment 時長（用於修正 FPS）
            segment_start_ns = segment['start_time_ns']
            segment_end_ns = segment['end_time_ns']
            self.segment_duration_sec = (segment_end_ns - segment_start_ns) / 1e9

            # 儲存時間資訊 - 使用實際數據的時間範圍
            try:
                # 查詢實際數據的時間範圍
                cursor = db_manager.conn.cursor()
                cursor.execute("""
                    SELECT MIN(time_ns)
                    FROM timeseries_data
                    WHERE segment_id = ?
                """, (segment_id,))
                result = cursor.fetchone()
                cursor.close()
                if result and result[0]:
                    self.start_time_ns = result[0]
                    logger.info(f"Using actual data start time: {self.start_time_ns:,} ns")
                else:
                    # 沒有數據時使用 segment 的時間
                    self.start_time_ns = segment['start_time_ns']
                    logger.warning(f"No data found, using segment start time: {self.start_time_ns:,} ns")
            except Exception as e:
                logger.error(f"Failed to get data start time: {e}")
                self.start_time_ns = segment['start_time_ns']

            self.wall_time_offset = segment['wall_time_offset']

            # 取得 route 的正確起始時間（從 GPS 推算）
            try:
                cursor = db_manager.conn.cursor()
                cursor.execute("""
                    SELECT start_timestamp
                    FROM routes
                    WHERE route_id = ?
                """, (segment['route_id'],))
                result = cursor.fetchone()
                cursor.close()
                if result and result[0]:
                    route_start_timestamp = result[0]
                    # 計算此 segment 的正確起始時間
                    self.segment_start_timestamp = route_start_timestamp + (self.segment_num * 60)
                    logger.info(f"✓ Using GPS-based start time: {self.segment_start_timestamp} (route: {route_start_timestamp} + {self.segment_num}×60)")
                else:
                    self.segment_start_timestamp = None
                    logger.warning("⚠ Route start_timestamp not set, will use wallTimeNanos (may be inaccurate)")
            except Exception as e:
                logger.error(f"Failed to get route start_timestamp: {e}")
                self.segment_start_timestamp = None

            # 儲存影片路徑和 rlog 路徑
            self.camera_paths = {
                'ecamera': segment.get('ecamera_path'),
                'fcamera': segment.get('fcamera_path'),
                'qcamera': segment.get('qcamera_path')
            }
            self.rlog_path = segment.get('rlog_path')

            logger.info(f"Loaded segment {segment_id} video paths")
            logger.info(f"rlog path: {self.rlog_path}")

            # 先嘗試載入當前選擇的相機，如果不可用則按照 fcamera > ecamera > qcamera 順序尋找
            current_camera = self.camera_combo.currentText()
            if self.camera_paths.get(current_camera) and Path(self.camera_paths[current_camera]).exists():
                self.load_video(current_camera)
            else:
                # 當前選擇不可用，按照優先順序尋找可用的相機
                for camera in ['fcamera', 'ecamera', 'qcamera']:
                    if self.camera_paths.get(camera) and Path(self.camera_paths[camera]).exists():
                        self.camera_combo.setCurrentText(camera)
                        self.load_video(camera)
                        break

        except Exception as e:
            logger.error(f"Failed to load segment: {e}")
            self.video_label.setText(f"Load failed: {e}")

    def load_video(self, camera: str):
        """
        載入影片檔案並預載所有幀

        Args:
            camera: 相機類型 ('ecamera', 'fcamera', 'qcamera')
        """
        video_path = self.camera_paths.get(camera)

        if not video_path or not Path(video_path).exists():
            logger.error(f"Video file not found: {video_path}")
            self.video_label.setText(f"找不到影片檔案\n{camera}")
            self.frames = []
            self.play_button.setEnabled(False)
            return

        self.video_label.setText(f"Loading... {camera}")
        self.frames = []
        self.current_frame_idx = 0
        self.current_camera = camera

        # 根據相機類型選擇解碼器
        if camera in ['ecamera', 'fcamera']:
            success = self._load_with_pyav(video_path)
        elif camera == 'qcamera':
            success = self._load_with_opencv(video_path)
        else:
            logger.error(f"Unknown camera type: {camera}")
            return

        if success and self.frames:
            self.timeline_slider.setMaximum(len(self.frames) - 1)
            self.play_button.setEnabled(True)

            # 讀取 EncodeIndex 以取得每一幀的實際時間戳記
            self._load_frame_timestamps(camera)

            self.display_frame(0)
            logger.info(f"Loaded video: {camera}, {len(self.frames)} frames @ {self.fps} FPS")
        else:
            self.video_label.setText(f"無法載入影片\n{camera}")
            self.play_button.setEnabled(False)

    def _load_with_pyav(self, video_path: str) -> bool:
        """使用 PyAV 載入 HEVC 影片並預載所有幀"""
        if not PYAV_AVAILABLE:
            logger.error("PyAV not available")
            return False

        try:
            container = av.open(video_path)
            video_stream = container.streams.video[0]

            self.fps = float(video_stream.average_rate) if video_stream.average_rate else 20.0

            # 預載所有幀
            logger.info(f"Loading video frames with PyAV...")
            frame_count = 0
            for frame in container.decode(video=0):
                img = frame.to_ndarray(format='rgb24')
                self.frames.append(img)
                frame_count += 1

                if frame_count % 100 == 0:
                    self.video_label.setText(f"Loading... {frame_count} frames")

            container.close()

            # 診斷：檢查視頻元數據的 FPS 是否正確
            video_metadata_fps = self.fps
            frame_count = len(self.frames)

            # 如果知道 segment 的實際時長，計算實際 FPS
            if hasattr(self, 'segment_duration_sec') and self.segment_duration_sec and self.segment_duration_sec > 0:
                calculated_fps = frame_count / self.segment_duration_sec
                logger.info(f"📹 Video FPS check:")
                logger.info(f"   Metadata FPS: {video_metadata_fps:.2f}")
                logger.info(f"   Frame count: {frame_count}")
                logger.info(f"   Segment duration: {self.segment_duration_sec:.2f} seconds")
                logger.info(f"   Calculated FPS: {calculated_fps:.2f}")

                # 如果差異超過 10%，使用計算的 FPS
                fps_diff_percent = abs(calculated_fps - video_metadata_fps) / video_metadata_fps * 100
                if fps_diff_percent > 10:
                    logger.warning(f"⚠️  Video metadata FPS ({video_metadata_fps:.2f}) differs from actual FPS ({calculated_fps:.2f}) by {fps_diff_percent:.1f}%")
                    logger.warning(f"⚠️  Using calculated FPS: {calculated_fps:.2f}")
                    self.fps = calculated_fps

            logger.info(f"PyAV loaded: {len(self.frames)} frames @ {self.fps} FPS")
            return True

        except Exception as e:
            logger.error(f"Failed to load with PyAV: {e}")
            return False

    def _load_with_opencv(self, video_path: str) -> bool:
        """使用 OpenCV 載入 H.264/TS 影片並預載所有幀"""
        if not CV2_AVAILABLE:
            logger.error("OpenCV not available")
            return False

        try:
            cap = cv2.VideoCapture(video_path)

            if not cap.isOpened():
                logger.error("OpenCV failed to open video")
                return False

            self.fps = cap.get(cv2.CAP_PROP_FPS)

            # 預載所有幀
            logger.info(f"Loading video frames with OpenCV...")
            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Convert BGR to RGB
                img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.frames.append(img)
                frame_count += 1

                if frame_count % 100 == 0:
                    self.video_label.setText(f"Loading... {frame_count} frames")

            cap.release()

            logger.info(f"OpenCV loaded: {len(self.frames)} frames @ {self.fps} FPS")
            return True

        except Exception as e:
            logger.error(f"Failed to load with OpenCV: {e}")
            return False

    def _load_frame_timestamps(self, camera: str):
        """
        從資料庫讀取影片幀時間戳記

        Args:
            camera: 相機類型 ('ecamera', 'fcamera', 'qcamera', 'dcamera')
        """
        self.frame_timestamps = []

        # 如果沒有資料庫管理器或 segment_id，跳過
        if not self.db_manager or not self.segment_id:
            logger.warning("Cannot load frame timestamps: missing db_manager or segment_id, will use calculated time")
            return

        try:
            logger.info(f"Reading frame timestamps for {camera} from database...")

            # 從資料庫讀取幀時間戳記
            self.frame_timestamps = self.db_manager.get_video_timestamps(self.segment_id, camera)

            logger.info(f"Read {len(self.frame_timestamps)} frame timestamps from database")

            if len(self.frame_timestamps) != len(self.frames):
                logger.warning(f"Database frame count ({len(self.frame_timestamps)}) does not match video frame count ({len(self.frames)})")
                # 如果數量不符，清空時間戳記，回退到計算時間
                self.frame_timestamps = []

        except Exception as e:
            logger.error(f"Failed to read frame timestamps from database: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.frame_timestamps = []

    def display_frame(self, idx: int):
        """顯示指定幀"""
        if idx < 0 or idx >= len(self.frames):
            return

        self.current_frame_idx = idx
        frame = self.frames[idx]

        try:
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            # 轉換 memoryview 為 bytes (PyQt6 需要)
            frame_bytes = bytes(frame.data)
            q_image = QImage(frame_bytes, width, height, bytes_per_line, QImage.Format.Format_RGB888)

            # 縮放到 label 大小
            pixmap = QPixmap.fromImage(q_image)
            scaled_pixmap = pixmap.scaled(
                self.video_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            self.video_label.setPixmap(scaled_pixmap)

        except Exception as e:
            logger.error(f"Failed to display frame: {e}")

        # 更新 UI
        self.update_time_display()
        self.timeline_slider.blockSignals(True)
        self.timeline_slider.setValue(idx)
        self.timeline_slider.blockSignals(False)

        # 計算當前時間
        if self.frame_timestamps and idx < len(self.frame_timestamps):
            # 使用從 EncodeIndex 讀取的實際時間戳記
            current_time_ns = self.frame_timestamps[idx]
            logger.info(f"📹 Frame {idx}: using actual timestamp = {current_time_ns:,}")
        else:
            # 回退到計算時間（當 EncodeIndex 不可用時）
            frame_time_sec = idx / self.fps
            frame_time_ns = int(frame_time_sec * 1e9)
            current_time_ns = self.start_time_ns + frame_time_ns
            logger.info(f"📹 Frame {idx}: using calculated time = start_time_ns({self.start_time_ns:,}) + {frame_time_ns:,} = {current_time_ns:,}")

        # 發送信號
        self.time_changed.emit(current_time_ns)
        self.frame_changed.emit(idx)

    def update_ui_text(self):
        """Update UI text based on current language"""
        if not self.translation_manager:
            return

        t = self.translation_manager.t

        # Update camera label
        self.camera_label.setText(t("Camera:"))

        # Update control buttons
        if self.is_playing:
            self.play_button.setText(t("Pause"))
        else:
            self.play_button.setText(t("Play"))

        self.prev_frame_btn.setText(t("◀ 1 Frame"))
        self.next_frame_btn.setText(t("1 Frame ▶"))
        self.back_5s_btn.setText(t("◀◀ 5s"))
        self.forward_5s_btn.setText(t("5s ▶▶"))

        # Update time display
        self.update_time_display()

    def update_time_display(self):
        """更新時間顯示"""
        t = self.translation_manager.t if self.translation_manager else lambda x: x

        # Frame info
        frame_text = t("Frame: 0 / 0").replace("0 / 0", f"{self.current_frame_idx} / {len(self.frames)}")
        self.frame_label.setText(frame_text)

        # 計算當前時間
        if self.frame_timestamps and self.current_frame_idx < len(self.frame_timestamps):
            # 使用實際時間戳記
            current_time_ns = self.frame_timestamps[self.current_frame_idx]
        else:
            # 使用計算時間
            frame_time_sec = self.current_frame_idx / self.fps
            frame_time_ns = int(frame_time_sec * 1e9)
            current_time_ns = self.start_time_ns + frame_time_ns

        # Real time - 優先使用 GPS 推算的正確時間
        if self.segment_start_timestamp is not None:
            # 使用正確的 segment 起始時間 + 當前播放位置
            frame_time_sec = self.current_frame_idx / self.fps
            real_timestamp = self.segment_start_timestamp + frame_time_sec
            real_time = datetime.fromtimestamp(real_timestamp)
        else:
            # Fallback: 使用 wallTimeNanos（可能不準確）
            real_time_ns = current_time_ns + self.wall_time_offset
            real_time = datetime.fromtimestamp(real_time_ns / 1e9)

        time_text = t("Time: --").replace("--", real_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
        self.time_label.setText(time_text)

    def toggle_play(self):
        """切換播放/暫停"""
        if not self.frames:
            return

        if self.is_playing:
            self.stop()
        else:
            self.play()

    def play(self):
        """開始播放"""
        if not self.frames:
            return

        self.is_playing = True
        t = self.translation_manager.t if self.translation_manager else lambda x: x
        self.play_button.setText(t("Pause"))
        self.playing_state_changed.emit(True)  # 發送播放狀態改變信號

        # 計算 timer 間隔 (毫秒)
        interval_ms = int(1000 / self.fps)
        self.timer.start(interval_ms)

        # 同步模式下，手動觸發第一次時間更新來啟動循環
        if self.sync_mode:
            if self.frame_timestamps and self.current_frame_idx < len(self.frame_timestamps):
                current_time_ns = self.frame_timestamps[self.current_frame_idx]
            else:
                frame_time_sec = self.current_frame_idx / self.fps
                frame_time_ns = int(frame_time_sec * 1e9)
                current_time_ns = self.start_time_ns + frame_time_ns
            self.time_changed.emit(current_time_ns)

    def stop(self):
        """停止播放"""
        self.is_playing = False
        t = self.translation_manager.t if self.translation_manager else lambda x: x
        self.play_button.setText(t("Play"))
        self.playing_state_changed.emit(False)  # 發送播放狀態改變信號
        self.timer.stop()

    def on_timer_tick(self):
        """Timer 觸發，前進一幀（僅在非同步模式）"""
        # 同步模式下，不由 timer 自動前進，而是等待外部 advance_frame() 調用
        if self.sync_mode:
            return

        if self.current_frame_idx < len(self.frames) - 1:
            self.display_frame(self.current_frame_idx + 1)
        else:
            # 播放結束
            self.stop()

    def advance_frame(self):
        """
        前進到下一幀（同步模式使用）

        Returns:
            bool: 是否成功前進（False 表示已到結尾）
        """
        if not self.frames or not self.is_playing:
            return False

        if self.current_frame_idx < len(self.frames) - 1:
            self.display_frame(self.current_frame_idx + 1)
            return True
        else:
            # 播放結束
            self.stop()
            return False

    def step_frame(self, delta: int):
        """前進/後退指定幀數"""
        if not self.frames:
            return

        new_frame = self.current_frame_idx + delta
        new_frame = max(0, min(new_frame, len(self.frames) - 1))
        self.display_frame(new_frame)

    def step_time(self, delta_sec: float):
        """前進/後退指定秒數"""
        if not self.frames:
            return

        delta_frames = int(delta_sec * self.fps)
        self.step_frame(delta_frames)

    def on_slider_changed(self, value: int):
        """時間軸滑桿改變"""
        if not self.is_playing and self.frames:
            self.display_frame(value)

    def on_camera_changed(self, camera: str):
        """相機選擇改變"""
        if self.is_playing:
            self.stop()

        logger.info(f"Camera changed to: {camera}")
        self.load_video(camera)
