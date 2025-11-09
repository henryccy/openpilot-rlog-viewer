# -*- coding: utf-8 -*-
"""
Main Window - openpilot Windows Viewer
"""
import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QMenuBar, QMenu, QStatusBar, QMessageBox, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
import logging

# Import widgets
from .video_player import VideoPlayer
from .signal_selector import SignalSelector
from .data_table import DataTable
from .chart_widget import ChartWidget

from .dialogs.route_manager_dialog import RouteManagerDialog
from .dialogs.import_progress_dialog import ImportProgressDialog
from .dialogs.signal_and_database_manager_dialog import SignalAndDatabaseManagerDialog
from .dialogs.custom_signal_dialog import CustomSignalDialog
from .dialogs.config_manager_dialog import ConfigManagerDialog
from .dialogs.export_data_dialog import ExportDataDialog
from ..core.sqlite_manager import SQLiteManager
from ..i18n.translator import TranslationManager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    Main Window Class

    Layout:
    - Left: Signal selector (15%)
    - Right: Main content area (85%)
      - Top: Video player (20%)
      - Middle: Data table (30%)
      - Bottom: Chart area (50%)
    """

    # Signals
    route_changed = pyqtSignal(str)  # Route ID changed
    time_changed = pyqtSignal('qint64')   # Current time (ns) changed - Use 64-bit integer to avoid overflow

    def __init__(self):
        super().__init__()

        # Window properties
        self.setWindowTitle("openpilot Windows Viewer")
        self.setGeometry(100, 100, 1600, 900)

        # Current state
        self.current_route_id = None
        self.current_segment_id = None
        self.current_segment_num = None
        self.current_time_ns = 0

        # Translation manager
        self.translation_manager = TranslationManager()
        # Load saved language preference (defaults to system language, or English)
        preferred_language = self.translation_manager.load_language_preference()
        self.translation_manager.load_language(preferred_language)
        logger.info(f"Language loaded: {preferred_language}")

        # Database manager
        self.db_manager = None
        self.init_database()

        # Setup UI
        self.setup_menubar()
        self.setup_central_widget()
        self.setup_statusbar()
        self.setup_shortcuts()  # Setup global shortcuts

        # Load settings
        self.load_settings()

        # Set initial chart visibility for signal selector
        # Set which charts' signals should be displayed in the signal selector based on menu checked state
        self.signal_selector.set_chart_visibility(
            cereal_visible=self.view_cereal_chart_action.isChecked(),
            can_visible=self.view_can_chart_action.isChecked()
        )

        # Apply initial language translations
        self.update_ui_text()
        # Update language menu checkmarks based on current language
        current_lang = self.translation_manager.get_current_language()
        self.language_english_action.setChecked(current_lang == 'en_US')
        self.language_chinese_action.setChecked(current_lang == 'zh_TW')

        # Set language for signal selector (to control Chinese translation display)
        self.signal_selector.set_language(current_lang)

    def init_database(self):
        """Initialize database connection"""
        t = self.translation_manager.t

        try:
            # Use SQLite, default database path is data/openpilot.db
            self.db_manager = SQLiteManager()
            if not self.db_manager.connect():
                raise Exception(t("Unable to connect to SQLite database"))

            # Ensure tables exist
            self.db_manager.create_tables()
            logger.info("SQLite database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            QMessageBox.critical(
                self,
                t("Database Connection Failed"),
                t("Unable to connect to SQLite database: {0}\n\nPlease ensure the database file can be created properly.").format(str(e))
            )
            # Don't exit program, allow user to retry later

    def setup_menubar(self):
        """Setup menu bar"""
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")

        # Route/Segment Manager
        manager_action = QAction("Route / Segment &Manager...", self)
        manager_action.setShortcut(QKeySequence("Ctrl+M"))
        manager_action.triggered.connect(self.open_route_manager)
        file_menu.addAction(manager_action)

        reset_action = QAction("&Reset Signal Selection", self)
        reset_action.setShortcut(QKeySequence("Ctrl+R"))
        reset_action.setToolTip("Clear all selected signals (keep current segment)")
        reset_action.triggered.connect(self.reset_signal_selection)
        file_menu.addAction(reset_action)

        file_menu.addSeparator()

        export_action = QAction("&Export Data...", self)
        export_action.triggered.connect(self.export_data_dialog)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Alt+F4"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View Menu
        view_menu = menubar.addMenu("&View")

        self.view_signal_selector_action = QAction("Signal Selector", self, checkable=True)
        self.view_signal_selector_action.setShortcut(QKeySequence("F1"))
        self.view_signal_selector_action.setChecked(True)
        self.view_signal_selector_action.triggered.connect(self.toggle_signal_selector)
        view_menu.addAction(self.view_signal_selector_action)

        self.view_data_table_action = QAction("Data Table", self, checkable=True)
        self.view_data_table_action.setShortcut(QKeySequence("F2"))
        self.view_data_table_action.setChecked(True)
        self.view_data_table_action.triggered.connect(self.toggle_data_table)
        view_menu.addAction(self.view_data_table_action)

        self.view_cereal_chart_action = QAction("Cereal Chart", self, checkable=True)
        self.view_cereal_chart_action.setShortcut(QKeySequence("F3"))
        self.view_cereal_chart_action.setChecked(True)
        self.view_cereal_chart_action.triggered.connect(self.toggle_cereal_chart)
        view_menu.addAction(self.view_cereal_chart_action)

        self.view_can_chart_action = QAction("CAN Chart", self, checkable=True)
        self.view_can_chart_action.setShortcut(QKeySequence("F4"))
        self.view_can_chart_action.setChecked(False)  # Default unchecked
        self.view_can_chart_action.triggered.connect(self.toggle_can_chart)
        view_menu.addAction(self.view_can_chart_action)

        self.view_video_action = QAction("Video Player", self, checkable=True)
        self.view_video_action.setShortcut(QKeySequence("F5"))
        self.view_video_action.setChecked(True)
        self.view_video_action.triggered.connect(self.toggle_video)
        view_menu.addAction(self.view_video_action)

        view_menu.addSeparator()

        self.view_dark_theme_action = QAction("Dark Theme", self, checkable=True)
        self.view_dark_theme_action.setShortcut(QKeySequence("F6"))
        self.view_dark_theme_action.setChecked(False)  # Default light theme
        self.view_dark_theme_action.triggered.connect(self.toggle_dark_theme)
        view_menu.addAction(self.view_dark_theme_action)

        view_menu.addSeparator()

        # Language submenu
        language_menu = view_menu.addMenu("&Language")
        self.language_english_action = QAction("English", self, checkable=True)
        self.language_english_action.setChecked(True)
        self.language_english_action.triggered.connect(lambda: self.switch_language('en_US'))
        language_menu.addAction(self.language_english_action)

        self.language_chinese_action = QAction("繁體中文", self, checkable=True)
        self.language_chinese_action.triggered.connect(lambda: self.switch_language('zh_TW'))
        language_menu.addAction(self.language_chinese_action)

        # Tools Menu
        tools_menu = menubar.addMenu("&Tools")

        # Import Signal Definitions
        import_signals_action = QAction("&Import Signal Definitions...", self)
        import_signals_action.triggered.connect(self.import_signal_definitions)
        tools_menu.addAction(import_signals_action)

        # Signal & Database Manager
        manager_action = QAction("Signal && Database &Manager...", self)
        manager_action.setShortcut(QKeySequence("Ctrl+M"))
        manager_action.triggered.connect(self.open_signal_and_database_manager)
        tools_menu.addAction(manager_action)

        tools_menu.addSeparator()

        # Config Manager
        config_action = QAction("&Config Manager...", self)
        config_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        config_action.triggered.connect(self.open_config_manager)
        tools_menu.addAction(config_action)

        tools_menu.addSeparator()

        new_signal_action = QAction("&New Calculated Signal...", self)
        new_signal_action.setShortcut(QKeySequence("Ctrl+N"))
        new_signal_action.triggered.connect(self.new_calculated_signal_dialog)
        tools_menu.addAction(new_signal_action)

        # Help Menu
        help_menu = menubar.addMenu("&Help")

        manual_action = QAction("User &Manual", self)
        manual_action.setShortcut(QKeySequence("F1"))
        manual_action.triggered.connect(self.show_manual)
        help_menu.addAction(manual_action)

        shortcuts_action = QAction("&Keyboard Shortcuts", self)
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)

        help_menu.addSeparator()

        about_action = QAction("&About...", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        github_action = QAction("&GitHub Project", self)
        github_action.triggered.connect(self.open_github)
        help_menu.addAction(github_action)

    def switch_language(self, language_code: str):
        """Switch application language"""
        # Load the new language
        if self.translation_manager.load_language(language_code):
            # Save preference
            self.translation_manager.save_language_preference(language_code)

            # Update all UI text
            self.update_ui_text()

            # Update language menu checkmarks
            self.language_english_action.setChecked(language_code == 'en_US')
            self.language_chinese_action.setChecked(language_code == 'zh_TW')

            # Update signal selector language (controls Chinese translation display)
            self.signal_selector.set_language(language_code)

            logger.info(f"Language switched to: {language_code}")

            # Show message to user
            QMessageBox.information(
                self,
                self.translation_manager.t("Language"),
                self.translation_manager.t("Language changed to {0}. Please restart the application for changes to take effect.").replace(
                    "{0}", self.translation_manager.get_current_language_name()
                )
            )
        else:
            QMessageBox.warning(
                self,
                self.translation_manager.t("Error"),
                f"Failed to load language: {language_code}"
            )

    def update_ui_text(self):
        """Update all UI text with current language translations"""
        t = self.translation_manager.t

        # Update menu bar
        # File Menu
        self.menuBar().actions()[0].setText(t("&File"))
        file_menu = self.menuBar().actions()[0].menu()
        file_menu.actions()[0].setText(t("Route / Segment &Manager..."))
        file_menu.actions()[1].setText(t("&Reset Signal Selection"))
        file_menu.actions()[1].setToolTip(t("Clear all selected signals (keep current segment)"))
        file_menu.actions()[3].setText(t("&Export Data..."))
        file_menu.actions()[5].setText(t("E&xit"))

        # View Menu
        self.menuBar().actions()[1].setText(t("&View"))
        view_menu = self.menuBar().actions()[1].menu()
        view_menu.actions()[0].setText(t("Signal Selector(&1)"))
        view_menu.actions()[1].setText(t("Data Table(&2)"))
        view_menu.actions()[2].setText(t("Cereal Chart(&3)"))
        view_menu.actions()[3].setText(t("CAN Chart(&4)"))
        view_menu.actions()[4].setText(t("Video Player(&5)"))
        view_menu.actions()[6].setText(t("Dark Theme(&6)"))

        # Language submenu
        language_menu = view_menu.actions()[8].menu()
        language_menu.setTitle(t("&Language"))

        # Tools Menu
        self.menuBar().actions()[2].setText(t("&Tools"))
        tools_menu = self.menuBar().actions()[2].menu()
        tools_menu.actions()[0].setText(t("&Import Signal Definitions..."))
        tools_menu.actions()[1].setText(t("Signal & Database &Manager..."))
        tools_menu.actions()[3].setText(t("&Config Manager..."))
        tools_menu.actions()[5].setText(t("&New Calculated Signal..."))

        # Help Menu
        self.menuBar().actions()[3].setText(t("&Help"))
        help_menu = self.menuBar().actions()[3].menu()
        help_menu.actions()[0].setText(t("User Manual(&H)"))
        help_menu.actions()[1].setText(t("&Keyboard Shortcuts"))
        help_menu.actions()[3].setText(t("&About..."))
        help_menu.actions()[4].setText(t("&GitHub Project"))

        # Update UI components
        self.signal_selector.update_ui_text()
        self.data_table.update_ui_text()
        self.cereal_chart_widget.update_ui_text()
        self.can_chart_widget.update_ui_text()
        self.video_player.update_ui_text()

    def setup_central_widget(self):
        """Create central widget layout"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout (horizontal split)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Main splitter (left: video+selector, right: table+chart)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # ============================================================
        # Left side: Video + Signal selector (vertical split)
        # ============================================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.left_splitter = QSplitter(Qt.Orientation.Vertical)
        left_layout.addWidget(self.left_splitter)

        # Video player (top, ~30% of left side)
        self.video_player = VideoPlayer(db_manager=self.db_manager, translation_manager=self.translation_manager)
        self.video_player.time_changed.connect(self.on_video_time_changed)
        self.video_player.playing_state_changed.connect(self.on_playing_state_changed)
        self.left_splitter.addWidget(self.video_player)

        # Signal selector (bottom, ~70% of left side)
        self.signal_selector = SignalSelector(translation_manager=self.translation_manager)
        self.signal_selector.signals_changed.connect(self.on_signals_changed)
        self.left_splitter.addWidget(self.signal_selector)

        # Set left splitter sizes (video 30%, selector 70%)
        self.left_splitter.setSizes([270, 630])  # Total 900 height

        self.main_splitter.addWidget(left_widget)

        # ============================================================
        # Right side: Data table + Charts (vertical split)
        # ============================================================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_layout.addWidget(self.right_splitter)

        # Data table (top, ~20%)
        self.data_table = DataTable(translation_manager=self.translation_manager)
        self.data_table.data_updated.connect(self.on_data_table_updated)
        self.right_splitter.addWidget(self.data_table)

        # Cereal Chart (middle, ~40%)
        self.cereal_chart_widget = ChartWidget(translation_manager=self.translation_manager)
        self.cereal_chart_widget.set_chart_name("Cereal Signals")
        self.cereal_chart_widget.charts_updated.connect(self.on_charts_updated)
        self.right_splitter.addWidget(self.cereal_chart_widget)

        # CAN Chart (bottom, ~40%)
        self.can_chart_widget = ChartWidget(translation_manager=self.translation_manager)
        self.can_chart_widget.set_chart_name("CAN Signals")
        self.can_chart_widget.charts_updated.connect(self.on_charts_updated)
        self.can_chart_widget.hide()  # Default: hide CAN chart area
        self.right_splitter.addWidget(self.can_chart_widget)

        # Synchronized playback: track update completion status
        self._data_table_ready = False
        self._cereal_chart_ready = False
        self._can_chart_ready = False

        # Set right splitter sizes (table 20%, cereal chart 40%, can chart 40%)
        self.right_splitter.setSizes([180, 360, 360])  # Total 900 height

        self.main_splitter.addWidget(right_widget)

        # ============================================================
        # Set initial main splitter sizes
        # Left (video+selector): 20% of width
        # Right (table+charts): 80% of width
        # ============================================================
        self.main_splitter.setSizes([320, 1280])  # Total 1600 width

        # ============================================================
        # Set initial chart visibility (after menu actions are created)
        # Note: This is called after setup_menubar, so view actions are already created
        # ============================================================
        # Not set here temporarily, will be set after __init__ completes

    def setup_statusbar(self):
        """Create status bar"""
        t = self.translation_manager.t

        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage(t("Ready"))

    def setup_shortcuts(self):
        """Setup global shortcuts (not affected by focus)"""
        # Space: Play/Pause
        shortcut_space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        shortcut_space.activated.connect(self.video_player.toggle_play)

        # Left: Step back 1 frame
        shortcut_left = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        shortcut_left.activated.connect(lambda: self.video_player.step_frame(-1))

        # Right: Step forward 1 frame
        shortcut_right = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        shortcut_right.activated.connect(lambda: self.video_player.step_frame(1))

        # Shift + Left: Step back 5 seconds
        shortcut_shift_left = QShortcut(QKeySequence("Shift+Left"), self)
        shortcut_shift_left.activated.connect(lambda: self.video_player.step_time(-5.0))

        # Shift + Right: Step forward 5 seconds
        shortcut_shift_right = QShortcut(QKeySequence("Shift+Right"), self)
        shortcut_shift_right.activated.connect(lambda: self.video_player.step_time(5.0))

    # ============================================================
    # Menu Actions (Placeholders)
    # ============================================================

    def open_route_manager(self):
        """Open Route/Segment Manager"""
        if not self.db_manager:
            QMessageBox.warning(self, "Warning", "Database not connected, cannot open manager")
            return

        try:
            dialog = RouteManagerDialog(self.db_manager, self, self.translation_manager)
            dialog.segment_loaded.connect(self.on_segment_loaded)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Segment loaded, status bar message already set in on_segment_loaded
                pass

        except Exception as e:
            logger.error(f"Failed to open route manager: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open manager: {e}")

    def reset_signal_selection(self):
        """Reset signal selection (deselect all signals, keep current Segment)"""
        t = self.translation_manager.t

        if not self.current_segment_id:
            QMessageBox.information(
                self,
                t("Cannot Reset"),
                t("No Segment currently loaded")
            )
            return

        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            t("Confirm Reset"),
            t("Are you sure you want to clear all selected signals?\n\n"
              "This operation will:\n"
              "• Deselect all signals\n"
              "• Clear charts and statistics table\n"
              "• Keep current loaded Segment\n"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Clear signal selection
        self.signal_selector.deselect_all()

        logger.info("Signal selection reset")
        self.statusbar.showMessage(t("Cleared all signal selections"), 3000)

    def export_data_dialog(self):
        """Export data dialog"""
        # Check if segment is loaded
        if not self.current_segment_id:
            QMessageBox.warning(self, "Error", "Please load Segment first")
            return

        # Get currently selected signals (merge both chart areas)
        cereal_signals = self.cereal_chart_widget.get_current_signals()
        can_signals = self.can_chart_widget.get_current_signals()
        current_signals = cereal_signals + can_signals

        if not current_signals:
            QMessageBox.warning(self, "Error", "Please select at least one signal")
            return

        # Open export dialog
        dialog = ExportDataDialog(
            self,
            db_manager=self.db_manager,
            segment_id=self.current_segment_id,
            current_signals=current_signals,
            translation_manager=self.translation_manager
        )
        dialog.exec()

    def new_calculated_signal_dialog(self):
        """New calculated signal dialog"""
        if not self.db_manager:
            QMessageBox.warning(self, "Database Not Connected", "Please connect to database first to add calculated signals")
            return

        dialog = CustomSignalDialog(self.db_manager, self.current_segment_id, self, self.translation_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Reload signal selector to show new signal
            if self.current_segment_id:
                self.signal_selector.load_segment(self.db_manager, self.current_segment_id)

    def show_manual(self):
        """Show user manual"""
        t = self.translation_manager.t
        current_lang = self.translation_manager.get_current_language()

        if current_lang == 'zh_TW':
            manual_text = """
<h2>openpilot 資料查看器 - 使用說明</h2>

<h3>📂 匯入資料</h3>
<ol>
<li>點擊「檔案」→「Route / Segment 管理器」</li>
<li>點擊「匯入 Segment」選擇 rlog 檔案</li>
<li>等待匯入完成（會自動解析影片、訊號、日誌）</li>
</ol>

<h3>▶️ 播放與查看</h3>
<ol>
<li>在 Route / Segment 管理器中雙擊要查看的 Segment</li>
<li>左側勾選要顯示的訊號（Cereal / CAN / 自訂）</li>
<li>使用播放控制：
  <ul>
  <li><b>空白鍵</b>：播放/暫停</li>
  <li><b>方向鍵 ←/→</b>：前進/後退 5 秒</li>
  <li><b>拖曳時間軸</b>：跳到指定時間</li>
  </ul>
</li>
</ol>

<h3>📊 圖表操作</h3>
<ul>
<li><b>滑鼠滾輪</b>：縮放 Y 軸範圍</li>
<li><b>滑鼠移動</b>：顯示當前位置的訊號值</li>
<li><b>右鍵選單</b>：切換雙 Y 軸、重置視圖、設定範圍</li>
<li>圖表顯示 ±10 秒時間視窗</li>
</ul>

<h3>🎨 自訂訊號</h3>
<ol>
<li>點擊「工具」→「新增計算訊號」</li>
<li>輸入訊號名稱、單位、公式（支援 Python 運算式）</li>
<li>例如：<code>carState.vEgo * 3.6</code> 將 m/s 轉為 km/h</li>
<li>訊號會出現在左側「自訂訊號」分類中</li>
</ol>

<h3>💾 匯出資料</h3>
<ol>
<li>選擇要匯出的訊號並顯示在圖表中</li>
<li>點擊「檔案」→「匯出資料」</li>
<li>選擇格式（CSV 或 Parquet）並儲存</li>
</ol>

<h3>⚙️ 配置管理</h3>
<ul>
<li>「工具」→「配置管理」可儲存當前的訊號選擇和視窗布局</li>
<li>快速切換不同的分析配置</li>
</ul>

<h3>💡 快捷鍵</h3>
<ul>
<li><b>F1-F5</b>：切換各區域顯示</li>
<li><b>F6</b>：切換暗色主題</li>
<li><b>Ctrl+M</b>：訊號與資料庫管理</li>
<li><b>Ctrl+N</b>：新增計算訊號</li>
<li><b>Ctrl+Shift+C</b>：配置管理</li>
</ul>

<p style="color: gray; margin-top: 20px;">
提示：將滑鼠停留在訊號名稱上可查看中文說明
</p>
            """
        else:
            manual_text = """
<h2>openpilot Data Viewer - User Manual</h2>

<h3>📂 Import Data</h3>
<ol>
<li>Click "File" → "Route / Segment Manager"</li>
<li>Click "Import Segment" to select rlog files</li>
<li>Wait for import to complete (automatically parses video, signals, logs)</li>
</ol>

<h3>▶️ Playback & Viewing</h3>
<ol>
<li>Double-click a Segment in Route / Segment Manager to view</li>
<li>Check signals on the left to display (Cereal / CAN / Custom)</li>
<li>Use playback controls:
  <ul>
  <li><b>Spacebar</b>: Play/Pause</li>
  <li><b>Arrow keys ←/→</b>: Step forward/backward 5 seconds</li>
  <li><b>Drag timeline</b>: Jump to specific time</li>
  </ul>
</li>
</ol>

<h3>📊 Chart Operations</h3>
<ul>
<li><b>Mouse wheel</b>: Zoom Y-axis range</li>
<li><b>Mouse move</b>: Display signal values at current position</li>
<li><b>Right-click menu</b>: Toggle dual Y-axis, reset view, set range</li>
<li>Chart displays ±10 second time window</li>
</ul>

<h3>🎨 Custom Signals</h3>
<ol>
<li>Click "Tools" → "Add Computed Signal"</li>
<li>Enter signal name, unit, formula (supports Python expressions)</li>
<li>Example: <code>carState.vEgo * 3.6</code> converts m/s to km/h</li>
<li>Signal appears in "Custom Signals" category on the left</li>
</ol>

<h3>💾 Export Data</h3>
<ol>
<li>Select signals to export and display in chart</li>
<li>Click "File" → "Export Data"</li>
<li>Choose format (CSV or Parquet) and save</li>
</ol>

<h3>⚙️ Configuration Management</h3>
<ul>
<li>"Tools" → "Configuration Manager" saves current signal selection and window layout</li>
<li>Quickly switch between different analysis configurations</li>
</ul>

<h3>💡 Shortcuts</h3>
<ul>
<li><b>F1-F5</b>: Toggle area visibility</li>
<li><b>F6</b>: Toggle dark theme</li>
<li><b>Ctrl+M</b>: Signal & Database Manager</li>
<li><b>Ctrl+N</b>: Add Computed Signal</li>
<li><b>Ctrl+Shift+C</b>: Configuration Manager</li>
</ul>

<p style="color: gray; margin-top: 20px;">
Tip: Hover mouse over signal names to view Chinese descriptions
</p>
            """

        # Use QMessageBox HTML support
        msg = QMessageBox(self)
        msg.setWindowTitle(t("User Manual"))
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(manual_text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setMinimumWidth(600)
        msg.exec()

    def show_shortcuts(self):
        """Show keyboard shortcuts list"""
        t = self.translation_manager.t
        current_lang = self.translation_manager.get_current_language()

        if current_lang == 'zh_TW':
            shortcuts_text = """
快捷鍵列表：

播放控制：
  空白鍵 - 播放/暫停
  ← / → - 前進/後退 1 幀
  Shift+← / → - 前進/後退 5 秒

檔案：
  Ctrl+M - Route/Segment 管理器
  Ctrl+R - 重設訊號選擇
  Alt+F4 - 離開

檢視：
  F1 - 切換訊號選擇器
  F2 - 切換資料表區
  F3 - 切換 Cereal 圖表區
  F4 - 切換 CAN 圖表區
  F5 - 切換影片播放器
  F6 - 切換暗色主題

工具：
  Ctrl+M - 訊號與資料庫管理
  Ctrl+Shift+C - 配置管理
  Ctrl+N - 新增計算訊號
            """
        else:
            shortcuts_text = """
Keyboard Shortcuts:

Playback Control:
  Spacebar - Play/Pause
  ← / → - Step forward/backward 1 frame
  Shift+← / → - Step forward/backward 5 seconds

File:
  Ctrl+M - Route/Segment Manager
  Ctrl+R - Reset Signal Selection
  Alt+F4 - Exit

View:
  F1 - Toggle Signal Selector
  F2 - Toggle Data Table
  F3 - Toggle Cereal Chart Area
  F4 - Toggle CAN Chart Area
  F5 - Toggle Video Player
  F6 - Toggle Dark Theme

Tools:
  Ctrl+M - Signal & Database Manager
  Ctrl+Shift+C - Configuration Manager
  Ctrl+N - Add Computed Signal
            """
        QMessageBox.information(self, t("Keyboard Shortcuts"), shortcuts_text)

    def show_about(self):
        """Show about dialog"""
        t = self.translation_manager.t
        current_lang = self.translation_manager.get_current_language()

        if current_lang == 'zh_TW':
            about_text = """
<h2>openpilot Windows 資料查看器</h2>
<p style="color: gray;">版本 2.0</p>

<p>用於查看和分析 openpilot 記錄資料的 Windows 應用程式</p>

<h3>✨ 主要功能</h3>
<ul>
<li>📹 <b>多相機影片播放</b> - 支援 HEVC (ecamera/fcamera) 和 H.264 (qcamera)</li>
<li>📊 <b>即時訊號圖表</b> - ±10 秒滾動視窗，支援雙 Y 軸</li>
<li>🚗 <b>CAN 訊息解析</b> - DBC 檔案支援，自動翻譯為中文</li>
<li>🧮 <b>自訂計算訊號</b> - Python 公式運算，動態計算新訊號</li>
<li>📝 <b>系統日誌查看</b> - 完整的 logMessage 和 errorLogMessage</li>
<li>💾 <b>資料匯出</b> - CSV 和 Parquet 格式，支援批次匯出</li>
<li>⚙️ <b>配置管理</b> - 儲存和載入訊號選擇與視窗布局</li>
<li>🎨 <b>暗色主題</b> - 支援淺色/暗色主題切換</li>
</ul>

<h3>🔧 技術資訊</h3>
<p>
• <b>開發環境</b>：Python 3.10+ / PyQt6<br>
• <b>資料庫</b>：SQLite 3<br>
• <b>影片解碼</b>：PyAV / OpenCV<br>
• <b>資料格式</b>：Cap'n Proto (rlog)
</p>

<p style="color: gray; margin-top: 20px; font-size: 9pt;">
© 2024 openpilot Data Viewer<br>
按 F1 查看使用說明
</p>
            """
        else:
            about_text = """
<h2>openpilot Windows Data Viewer</h2>
<p style="color: gray;">Version 2.0</p>

<p>Windows application for viewing and analyzing openpilot recorded data</p>

<h3>✨ Key Features</h3>
<ul>
<li>📹 <b>Multi-camera Video Playback</b> - Supports HEVC (ecamera/fcamera) and H.264 (qcamera)</li>
<li>📊 <b>Real-time Signal Charts</b> - ±10 second rolling window, dual Y-axis support</li>
<li>🚗 <b>CAN Message Parsing</b> - DBC file support, automatic Chinese translation</li>
<li>🧮 <b>Custom Computed Signals</b> - Python formula calculations, dynamic new signals</li>
<li>📝 <b>System Log Viewing</b> - Complete logMessage and errorLogMessage</li>
<li>💾 <b>Data Export</b> - CSV and Parquet formats, batch export support</li>
<li>⚙️ <b>Configuration Management</b> - Save and load signal selections and window layouts</li>
<li>🎨 <b>Dark Theme</b> - Light/dark theme switching support</li>
</ul>

<h3>🔧 Technical Information</h3>
<p>
• <b>Development Environment</b>: Python 3.10+ / PyQt6<br>
• <b>Database</b>: SQLite 3<br>
• <b>Video Decoding</b>: PyAV / OpenCV<br>
• <b>Data Format</b>: Cap'n Proto (rlog)
</p>

<p style="color: gray; margin-top: 20px; font-size: 9pt;">
© 2024 openpilot Data Viewer<br>
Press F1 to view user manual
</p>
            """

        msg = QMessageBox(self)
        msg.setWindowTitle(t("About openpilot Data Viewer"))
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(about_text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setMinimumWidth(500)
        msg.exec()

    def open_github(self):
        """Open GitHub project"""
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl("https://github.com/commaai/openpilot"))

    # ============================================================
    # Tools Menu Actions
    # ============================================================

    def import_signal_definitions(self):
        """Open signal definition import dialog"""
        if not self.db_manager:
            QMessageBox.warning(
                self,
                "資料庫未連接",
                "請先連接資料庫才能匯入訊號定義"
            )
            return

        from .dialogs.signal_import_dialog import SignalImportDialog
        dialog = SignalImportDialog(self.db_manager, self, self.translation_manager)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            logger.info("Signal definitions import complete")
            # Reload signal selector to show new signals
            if self.current_segment_id:
                self.signal_selector.load_segment(self.db_manager, self.current_segment_id)

    def open_signal_and_database_manager(self):
        """Open Signal & Database Manager dialog (integrated: signal translation, DBC management, database management)"""
        if not self.db_manager:
            QMessageBox.warning(
                self,
                "資料庫未連接",
                "請先連接資料庫才能使用管理功能"
            )
            return

        dialog = SignalAndDatabaseManagerDialog(self.db_manager, self, self.translation_manager)
        dialog.exec()

        # If database manager was updated, reset it
        if hasattr(dialog, 'db_manager') and dialog.db_manager:
            self.db_manager = dialog.db_manager

        # Reload signal selector after editing to show updated Chinese names
        if self.current_segment_id:
            self.signal_selector.load_segment(self.db_manager, self.current_segment_id)

    def open_config_manager(self):
        """Open config manager dialog"""
        dialog = ConfigManagerDialog(self, self.translation_manager)
        dialog.exec()

    # ============================================================
    # View Toggle Actions
    # ============================================================

    def toggle_signal_selector(self, checked):
        """Toggle signal selector display"""
        if checked:
            self.signal_selector.show()
        else:
            self.signal_selector.hide()

    def toggle_data_table(self, checked):
        """Toggle data table display"""
        if checked:
            self.data_table.show()
        else:
            self.data_table.hide()

    def toggle_cereal_chart(self, checked):
        """Toggle Cereal chart display"""
        if checked:
            self.cereal_chart_widget.show()
        else:
            self.cereal_chart_widget.hide()

        # Update signal selector visibility
        self.signal_selector.set_chart_visibility(
            cereal_visible=self.view_cereal_chart_action.isChecked(),
            can_visible=self.view_can_chart_action.isChecked()
        )

    def toggle_can_chart(self, checked):
        """Toggle CAN chart display"""
        if checked:
            self.can_chart_widget.show()
        else:
            self.can_chart_widget.hide()

        # Update signal selector visibility
        self.signal_selector.set_chart_visibility(
            cereal_visible=self.view_cereal_chart_action.isChecked(),
            can_visible=self.view_can_chart_action.isChecked()
        )

    def toggle_video(self, checked):
        """Toggle video player display"""
        if checked:
            self.video_player.show()
        else:
            self.video_player.hide()

    def toggle_dark_theme(self, checked):
        """Toggle dark theme"""
        if checked:
            self.apply_dark_theme()
            logger.info("Switched to dark theme")
        else:
            self.apply_light_theme()
            logger.info("Switched to light theme")

        # Update chart theme
        self.cereal_chart_widget.set_theme(checked)
        self.can_chart_widget.set_theme(checked)

        # Save theme preference
        self.save_theme_preference(checked)

    # ============================================================
    # Theme Styles
    # ============================================================

    def apply_light_theme(self):
        """Apply light theme"""
        light_style = """
            QMainWindow {
                background-color: #f0f0f0;
                color: #000000;
            }

            QWidget {
                background-color: #ffffff;
                color: #000000;
            }

            QMenuBar {
                background-color: #f0f0f0;
                color: #000000;
                border-bottom: 1px solid #d0d0d0;
            }

            QMenuBar::item {
                background-color: transparent;
                padding: 4px 8px;
            }

            QMenuBar::item:selected {
                background-color: #e0e0e0;
            }

            QMenu {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #d0d0d0;
            }

            QMenu::item:selected {
                background-color: #e0e0e0;
            }

            QTreeWidget {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #d0d0d0;
                alternate-background-color: #f8f8f8;
            }

            QTreeWidget::item:selected {
                background-color: #0078d7;
                color: #ffffff;
            }

            QTableWidget {
                background-color: #ffffff;
                color: #000000;
                gridline-color: #d0d0d0;
                border: 1px solid #d0d0d0;
                alternate-background-color: #f8f8f8;
            }

            QTableWidget::item:selected {
                background-color: #0078d7;
                color: #ffffff;
            }

            QHeaderView::section {
                background-color: #f0f0f0;
                color: #000000;
                padding: 4px;
                border: 1px solid #d0d0d0;
            }

            QPushButton {
                background-color: #e0e0e0;
                color: #000000;
                border: 1px solid #a0a0a0;
                border-radius: 3px;
                padding: 5px 15px;
            }

            QPushButton:hover {
                background-color: #d0d0d0;
            }

            QPushButton:pressed {
                background-color: #c0c0c0;
            }

            QPushButton:disabled {
                background-color: #f0f0f0;
                color: #a0a0a0;
            }

            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                padding: 3px;
            }

            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
                border: 1px solid #0078d7;
            }

            QLabel {
                color: #000000;
                background-color: transparent;
            }

            QStatusBar {
                background-color: #f0f0f0;
                color: #000000;
                border-top: 1px solid #d0d0d0;
            }

            QTabWidget::pane {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
            }

            QTabBar::tab {
                background-color: #e0e0e0;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-bottom: none;
                padding: 5px 10px;
                margin-right: 2px;
            }

            QTabBar::tab:selected {
                background-color: #ffffff;
                border-bottom: 1px solid #ffffff;
            }

            QTabBar::tab:hover {
                background-color: #d0d0d0;
            }

            QComboBox {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                padding: 3px;
            }

            QComboBox:hover {
                border: 1px solid #0078d7;
            }

            QComboBox::drop-down {
                border: none;
            }

            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #d0d0d0;
                selection-background-color: #0078d7;
                selection-color: #ffffff;
            }

            QCheckBox {
                color: #000000;
                spacing: 5px;
            }

            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #a0a0a0;
                border-radius: 3px;
                background-color: #ffffff;
            }

            QCheckBox::indicator:checked {
                background-color: #0078d7;
                border: 1px solid #0078d7;
            }

            QRadioButton {
                color: #000000;
                spacing: 5px;
            }

            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #a0a0a0;
                border-radius: 8px;
                background-color: #ffffff;
            }

            QRadioButton::indicator:checked {
                background-color: #0078d7;
                border: 1px solid #0078d7;
            }

            QSpinBox, QDoubleSpinBox {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                padding: 3px;
            }

            QSlider::groove:horizontal {
                border: 1px solid #d0d0d0;
                height: 4px;
                background-color: #e0e0e0;
                border-radius: 2px;
            }

            QSlider::handle:horizontal {
                background-color: #0078d7;
                border: 1px solid #0078d7;
                width: 12px;
                margin: -5px 0;
                border-radius: 6px;
            }

            QProgressBar {
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                background-color: #f0f0f0;
                text-align: center;
            }

            QProgressBar::chunk {
                background-color: #0078d7;
                border-radius: 2px;
            }

            QScrollBar:vertical {
                border: none;
                background-color: #f0f0f0;
                width: 12px;
                margin: 0px;
            }

            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                min-height: 20px;
                border-radius: 6px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }

            QScrollBar:horizontal {
                border: none;
                background-color: #f0f0f0;
                height: 12px;
                margin: 0px;
            }

            QScrollBar::handle:horizontal {
                background-color: #c0c0c0;
                min-width: 20px;
                border-radius: 6px;
            }

            QScrollBar::handle:horizontal:hover {
                background-color: #a0a0a0;
            }

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                border: none;
                background: none;
            }

            QSplitter::handle {
                background-color: #d0d0d0;
            }

            QSplitter::handle:hover {
                background-color: #b0b0b0;
            }
        """
        self.setStyleSheet(light_style)

    def apply_dark_theme(self):
        """Apply dark theme"""
        dark_style = """
            QMainWindow {
                background-color: #1e1e1e;
                color: #ffffff;
            }

            QWidget {
                background-color: #2d2d2d;
                color: #ffffff;
            }

            QMenuBar {
                background-color: #2d2d2d;
                color: #ffffff;
                border-bottom: 1px solid #3e3e3e;
            }

            QMenuBar::item {
                background-color: transparent;
                padding: 4px 8px;
            }

            QMenuBar::item:selected {
                background-color: #3e3e3e;
            }

            QMenu {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3e3e3e;
            }

            QMenu::item:selected {
                background-color: #3e3e3e;
            }

            QTreeWidget {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3e3e3e;
                alternate-background-color: #2d2d2d;
            }

            QTreeWidget::item:selected {
                background-color: #094771;
                color: #ffffff;
            }

            QTableWidget {
                background-color: #252526;
                color: #cccccc;
                gridline-color: #3e3e3e;
                border: 1px solid #3e3e3e;
                alternate-background-color: #2d2d2d;
            }

            QTableWidget::item:selected {
                background-color: #094771;
                color: #ffffff;
            }

            QHeaderView::section {
                background-color: #2d2d2d;
                color: #cccccc;
                padding: 4px;
                border: 1px solid #3e3e3e;
            }

            QPushButton {
                background-color: #3e3e3e;
                color: #ffffff;
                border: 1px solid #5e5e5e;
                border-radius: 3px;
                padding: 5px 15px;
            }

            QPushButton:hover {
                background-color: #4e4e4e;
            }

            QPushButton:pressed {
                background-color: #2e2e2e;
            }

            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #6e6e6e;
            }

            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #1e1e1e;
                color: #cccccc;
                border: 1px solid #3e3e3e;
                border-radius: 3px;
                padding: 3px;
            }

            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
                border: 1px solid #007acc;
            }

            QLabel {
                color: #cccccc;
                background-color: transparent;
            }

            QStatusBar {
                background-color: #007acc;
                color: #ffffff;
                border-top: 1px solid #005a9e;
            }

            QTabWidget::pane {
                border: 1px solid #3e3e3e;
                background-color: #2d2d2d;
            }

            QTabBar::tab {
                background-color: #2d2d2d;
                color: #cccccc;
                border: 1px solid #3e3e3e;
                border-bottom: none;
                padding: 5px 10px;
                margin-right: 2px;
            }

            QTabBar::tab:selected {
                background-color: #1e1e1e;
                border-bottom: 1px solid #1e1e1e;
            }

            QTabBar::tab:hover {
                background-color: #3e3e3e;
            }

            QComboBox {
                background-color: #1e1e1e;
                color: #cccccc;
                border: 1px solid #3e3e3e;
                border-radius: 3px;
                padding: 3px;
            }

            QComboBox:hover {
                border: 1px solid #007acc;
            }

            QComboBox::drop-down {
                border: none;
            }

            QComboBox QAbstractItemView {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3e3e3e;
                selection-background-color: #094771;
                selection-color: #ffffff;
            }

            QCheckBox {
                color: #cccccc;
                spacing: 5px;
            }

            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #5e5e5e;
                border-radius: 3px;
                background-color: #1e1e1e;
            }

            QCheckBox::indicator:checked {
                background-color: #007acc;
                border: 1px solid #007acc;
            }

            QRadioButton {
                color: #cccccc;
                spacing: 5px;
            }

            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #5e5e5e;
                border-radius: 8px;
                background-color: #1e1e1e;
            }

            QRadioButton::indicator:checked {
                background-color: #007acc;
                border: 1px solid #007acc;
            }

            QSpinBox, QDoubleSpinBox {
                background-color: #1e1e1e;
                color: #cccccc;
                border: 1px solid #3e3e3e;
                border-radius: 3px;
                padding: 3px;
            }

            QSlider::groove:horizontal {
                border: 1px solid #3e3e3e;
                height: 4px;
                background-color: #2d2d2d;
                border-radius: 2px;
            }

            QSlider::handle:horizontal {
                background-color: #007acc;
                border: 1px solid #007acc;
                width: 12px;
                margin: -5px 0;
                border-radius: 6px;
            }

            QProgressBar {
                border: 1px solid #3e3e3e;
                border-radius: 3px;
                background-color: #2d2d2d;
                text-align: center;
                color: #cccccc;
            }

            QProgressBar::chunk {
                background-color: #007acc;
                border-radius: 2px;
            }

            QScrollBar:vertical {
                border: none;
                background-color: #1e1e1e;
                width: 12px;
                margin: 0px;
            }

            QScrollBar::handle:vertical {
                background-color: #4e4e4e;
                min-height: 20px;
                border-radius: 6px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #5e5e5e;
            }

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }

            QScrollBar:horizontal {
                border: none;
                background-color: #1e1e1e;
                height: 12px;
                margin: 0px;
            }

            QScrollBar::handle:horizontal {
                background-color: #4e4e4e;
                min-width: 20px;
                border-radius: 6px;
            }

            QScrollBar::handle:horizontal:hover {
                background-color: #5e5e5e;
            }

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                border: none;
                background: none;
            }

            QSplitter::handle {
                background-color: #3e3e3e;
            }

            QSplitter::handle:hover {
                background-color: #5e5e5e;
            }
        """
        self.setStyleSheet(dark_style)

    # ============================================================
    # Settings
    # ============================================================

    def load_settings(self):
        """Load settings"""
        settings = QSettings("OpenpilotViewer", "MainWindow")

        # Load theme preference
        is_dark_theme = settings.value("theme/dark_mode", False, type=bool)
        self.view_dark_theme_action.setChecked(is_dark_theme)

        # Apply theme
        if is_dark_theme:
            self.apply_dark_theme()
        else:
            self.apply_light_theme()

        # Update chart theme
        self.cereal_chart_widget.set_theme(is_dark_theme)
        self.can_chart_widget.set_theme(is_dark_theme)

        logger.info(f"Settings loaded: dark theme = {is_dark_theme}")

    def save_settings(self):
        """Save settings"""
        settings = QSettings("OpenpilotViewer", "MainWindow")

        # Save theme preference
        settings.setValue("theme/dark_mode", self.view_dark_theme_action.isChecked())

        logger.info("Settings saved")

    def save_theme_preference(self, is_dark: bool):
        """Save theme preference"""
        settings = QSettings("OpenpilotViewer", "MainWindow")
        settings.setValue("theme/dark_mode", is_dark)
        logger.info(f"Theme preference saved: dark theme = {is_dark}")

    def on_segment_loaded(self, route_id: str, segment_id: int, segment_num: int):
        """
        Segment 被載入時的回調

        Args:
            route_id: Route ID
            segment_id: Segment ID
            segment_num: Segment 號碼
        """
        self.current_route_id = route_id
        self.current_segment_id = segment_id
        self.current_segment_num = segment_num

        # Update status bar
        self.statusbar.showMessage(f"已載入: {route_id} / Segment {segment_num}")

        # Load segment data
        self.load_segment_data(segment_id)

        # Send route_changed signal
        self.route_changed.emit(route_id)

    def load_segment_data(self, segment_id: int):
        """Load all segment data (video, signals, etc.)"""
        if not self.db_manager:
            return

        # Create progress dialog
        progress_dialog = ImportProgressDialog(self, title=self.translation_manager.t("Load Segment"), translation_manager=self.translation_manager)
        progress_dialog.set_status(self.translation_manager.t("Preparing to load..."))
        progress_dialog.set_progress(0)
        progress_dialog.enable_logging()  # Enable logging capture
        progress_dialog.show()

        # Force event processing to ensure dialog is displayed
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        try:

            # Clear previous selection and data
            progress_dialog.set_status(self.translation_manager.t("Clearing previous data..."))
            progress_dialog.set_progress(5)
            QApplication.processEvents()  # Ensure status update is displayed

            self.signal_selector.deselect_all()  # Clear signal selection
            self.data_table.set_signals([], {})  # Clear data table
            self.cereal_chart_widget.set_signals([], {})  # Clear chart
            self.can_chart_widget.set_signals([], {})  # Clear chart

            # Load video (automatically select first available camera)
            progress_dialog.set_status(self.translation_manager.t("Loading video..."))
            progress_dialog.set_progress(20)
            QApplication.processEvents()  # Ensure status update is displayed (before loading video)

            self.video_player.load_segment(self.db_manager, segment_id)

            # Load signal data
            progress_dialog.set_status(self.translation_manager.t("Loading signal data..."))
            progress_dialog.set_progress(40)
            QApplication.processEvents()

            self.signal_selector.load_segment(self.db_manager, segment_id)

            # Set segment for data table and charts
            progress_dialog.set_status(self.translation_manager.t("Setting up data table..."))
            progress_dialog.set_progress(60)
            QApplication.processEvents()

            self.data_table.set_database_manager(self.db_manager)
            self.data_table.set_segment(segment_id)

            progress_dialog.set_status(self.translation_manager.t("Setting up charts..."))
            progress_dialog.set_progress(80)
            QApplication.processEvents()

            self.cereal_chart_widget.set_database_manager(self.db_manager)
            self.cereal_chart_widget.set_segment(segment_id)
            self.can_chart_widget.set_database_manager(self.db_manager)
            self.can_chart_widget.set_segment(segment_id)

            progress_dialog.set_progress(100)
            QApplication.processEvents()
            progress_dialog.set_complete(self.translation_manager.t("Load completed"))

        except Exception as e:
            logger.error(f"Load failed: {e}")
            progress_dialog.set_complete(self.translation_manager.t("Load failed"))
            QMessageBox.critical(self, "Error", f"Failed to load Segment: {e}")

        finally:
            # Disable logging capture
            progress_dialog.disable_logging()

    def on_video_time_changed(self, time_ns: int):
        """
        影片時間改變時的回調

        Args:
            time_ns: 當前時間 (nanoseconds)
        """
        self.current_time_ns = time_ns

        # Update data table and charts (±10s window)
        self.data_table.update_time_window(time_ns)
        self.cereal_chart_widget.update_time_window(time_ns)
        self.can_chart_widget.update_time_window(time_ns)

        # Send time_changed signal
        self.time_changed.emit(time_ns)

    def on_playing_state_changed(self, is_playing: bool):
        """
        播放狀態改變時的回調

        Args:
            is_playing: True=播放中，False=暫停
        """
        # Notify all charts to update playing state
        self.cereal_chart_widget.set_playing_state(is_playing)
        self.can_chart_widget.set_playing_state(is_playing)

    def on_signals_changed(self, signal_names: list):
        """
        選擇的訊號改變時的回調

        Args:
            signal_names: List of selected signal names
        """
        # Separate Cereal and CAN signals
        cereal_signals = []
        can_signals = []
        cereal_colors = {}
        can_colors = {}

        for signal_name in signal_names:
            color = self.signal_selector.get_signal_color(signal_name)

            # Determine signal type (CAN signals start with "can.")
            if signal_name.startswith("can."):
                can_signals.append(signal_name)
                can_colors[signal_name] = color
            else:
                # Cereal signals or custom signals
                cereal_signals.append(signal_name)
                cereal_colors[signal_name] = color

        # Update data table (show all signals)
        all_colors = {**cereal_colors, **can_colors}
        self.data_table.set_signals(signal_names, all_colors)

        # Update charts (display separately)
        self.cereal_chart_widget.set_signals(cereal_signals, cereal_colors)
        self.can_chart_widget.set_signals(can_signals, can_colors)

    def on_data_table_updated(self):
        """Data table update completed"""
        self._data_table_ready = True
        self._check_all_updated()

    def on_charts_updated(self):
        """Chart update completed"""
        sender = self.sender()
        if sender == self.cereal_chart_widget:
            self._cereal_chart_ready = True
        elif sender == self.can_chart_widget:
            self._can_chart_ready = True

        self._check_all_updated()

    def _check_all_updated(self):
        """Check if all data updates are complete, advance to next frame if so"""
        # All components must complete before advancing
        if self._data_table_ready and self._cereal_chart_ready and self._can_chart_ready:
            # Reset flags
            self._data_table_ready = False
            self._cereal_chart_ready = False
            self._can_chart_ready = False

            # Only auto-advance in sync mode
            if self.video_player.sync_mode and self.video_player.is_playing:
                # Use singleShot(0) to defer to next event loop, avoid recursion
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, self.video_player.advance_frame)


    def closeEvent(self, event):
        """Window close event"""
        self.save_settings()

        # Close database connection
        if self.db_manager:
            try:
                self.db_manager.disconnect()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database: {e}")

        event.accept()
