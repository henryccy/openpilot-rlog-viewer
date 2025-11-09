# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for openpilot Log Viewer
用於編譯 Windows 執行檔
"""

block_cipher = None

# 資料檔案打包設定
# 所有檔案都打包進 EXE（包括 src/），確保穩定性
datas = [
    # capnp include 目錄（必須包含，log.capnp 需要）
    ('include', 'include'),
    # 完整的 capnp Python 套件（從 venv 複製）
    ('venv/Lib/site-packages/capnp', 'capnp'),
    # src 目錄作為資料檔案（不編譯成 pyc）
    ('src', 'src'),
    # tools 目錄（單位定義等工具）
    ('tools', 'tools'),
]

# 打包所有必要的資料檔案和 Python 原始碼
# 雖然這樣會讓 EXE 變大，但確保了穩定性
# 注意：capnp 檔案、LICENSE 等會在編譯後手動複製到外部

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

        # pycapnp 相關（匯入訊號定義時需要）
        'capnp',
        'capnp.lib.capnp',

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
        # 排除 src 避免被編譯（改用 datas 打包）
        'src',
        'src.*',
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
    console=True,  # 顯示命令列視窗以便除錯
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
