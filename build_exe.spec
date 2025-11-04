# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for openpilot Log Viewer
用於編譯 Windows 執行檔
"""

block_cipher = None

# 資料檔案打包設定
# 策略：只編譯 main.py，所有其他檔案都保持外部，方便修改
datas = []

# 以下檔案**全部不打包**，保留在專案目錄外面，方便修改：
# - src/**/*.py（Python 源碼，可隨時修改）
# - tools/**/*.py（工具程式源碼，可隨時修改）
# - data/dbc/*.dbc（DBC 檔案，用戶可自行添加修改）
# - data/translations/*.json（訊號翻譯，可隨時更新）
# - i18n/*.json（UI 翻譯，可隨時更新）
# - *.capnp（Schema 檔案，用戶可更新）
#
# 發布結構：
# release/
# ├── OpenpilotLogViewer.exe  ← 編譯後的 main.py
# ├── _internal/              ← PyInstaller 的依賴庫
# ├── src/                    ← 外部，可直接修改
# ├── tools/                  ← 外部，可直接修改
# ├── data/                   ← 外部，可直接修改
# ├── i18n/                   ← 外部，可直接修改
# └── *.capnp                 ← 外部
#
# 好處：
# 1. 修改任何 Python 檔案或資料檔案都不需要重新編譯
# 2. exe 只是替代 python.exe，其他都是源碼
# 3. 用戶可以自己修改和擴展功能

# 收集所有原始碼
# 注意：只編譯 main.py，其他 Python 檔案保持源碼形式
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # PyQt6 相關
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.sip',

        # pyqtgraph 相關
        'pyqtgraph',
        'pyqtgraph.graphicsItems',
        'pyqtgraph.exporters',

        # numpy 相關
        'numpy',
        'numpy.core',
        'numpy.core._multiarray_umath',

        # 注意：不再需要 pycapnp！
        # 幀時間戳記已在匯入時儲存到資料庫

        # av 相關
        'av',
        'av.audio',
        'av.video',
        'av.container',

        # opencv 相關
        'cv2',

        # cantools 相關
        'cantools',
        'cantools.database',
        'cantools.database.can',

        # 其他
        'sqlite3',
        'json',
        'pathlib',
        'logging',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的模組以減少體積
        'matplotlib',
        'IPython',
        'jupyter',
        'notebook',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OpenpilotLogViewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不顯示命令列視窗（GUI 程式）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 如果有 icon，在這裡指定: icon='icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='OpenpilotLogViewer',
)
