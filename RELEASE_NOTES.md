# Release Notes - v1.0.0

**Compatibility**: Tested with openpilot 0.9.7 and forks (FrogPilot, comma, custom builds, etc.)
**Note**: openpilot 0.10+ untested - rlog format may have changed
**Included log.capnp**: From FrogPilot (but you can use any version)

## Quick Start for End Users

### Download and Run

1. **Download** from [GitHub Releases](https://github.com/YOUR_USERNAME/openpilot-rlog-viewer/releases)
   - Download `OpenpilotLogViewer-v1.0.0-Windows-x64.zip` (316 MB)
2. **Extract** the ZIP file to any location (e.g., `C:\openpilot-viewer\`)
3. **Double-click** `OpenpilotLogViewer.exe` to start
4. No installation or Python required!

### First Time Setup

1. **Setup SSH Access to C3/C3X** (first time only)
   - ⚠️ Modern C3/C3X devices require SSH key authentication (no password login)
   - Search online for: "comma 3 SSH key setup" or "comma 3X SSH access"
   - Configure your GitHub SSH key with your comma device

2. **Import Signal Definitions** (first time and after updates)
   - Go to `Tools → Import Signal Definitions`
   - **Required files**:
     - `log.capnp` (main schema - included version is from FrogPilot, but you can use any version)
     - `car.capnp`, `legacy.capnp`, `custom.capnp`, `maptile.capnp` (dependencies - must be in same directory as log.capnp)
     - DBC files in `data/dbc/`
   - When importing, you only need to select `log.capnp`. The other 4 dependency files will be automatically loaded from the same directory.
   - Click "Start Import"
   - Wait for completion (~30-60 seconds)
   - Re-import when updating signal definition files or using logs from different versions

3. **Get Logs from C3/C3X**
   - ⚠️ **Important**: Must copy the entire segment directory (e.g., `2024-01-01--12-00-00/`), not individual files
   - The segment directory contains:
     - `rlog` or `rlog.bz2` (log file)
     - `fcamera.hevc`, `ecamera.hevc`, `dcamera.hevc` (video files)
     - Other related files
   - Use SSH/SCP: `scp -r comma@192.168.x.x:/data/media/0/realdata/2024-01-01--12-00-00 C:\logs\`
   - Or use WinSCP/FileZilla with SSH key authentication

4. **Import Segment**
   - Go to `Tools → Import Segment`
   - Browse to your rlog file (uncompressed `.rlog` only)
   - Click "Start Import"

   ⚠️ **Note**: Only uncompressed `.rlog` files are supported. If you have `.bz2` compressed files, decompress them first: `bzip2 -d rlog.bz2`

   **Important: File Management After Import**:
   - ✅ **Video files**: Must remain in original location (database stores video file paths)
   - ✅ **rlog files**: Can be deleted to save space (data is imported to database)
   - ⚠️ If you move or delete video files, video playback will not work (but data charts remain functional)

5. **Analyze!**
   - Search and select signals
   - Watch synchronized video
   - Export data for further analysis

### Full Documentation

- **User Guide**: See `docs/USER_GUIDE.md` (English) or `docs/USER_GUIDE_zh-TW.md` (中文)
- **README**: See `README.md` (English) or `README_zh-TW.md` (中文)

---

## For Developers

### Source Code

The complete source code is available in the root directory:
- `src/` - Application source code
- `tools/` - Utility scripts
- `data/` - DBC files and translations
- `i18n/` - UI translations
- `main.py` - Entry point
- `requirements.txt` - Python dependencies

### Building from Source

See `README_BUILD.md` for detailed instructions:

1. Create virtual environment
2. Install dependencies
3. Run `build_exe.bat`
4. Deploy according to instructions

### Modifying the Application

**No recompilation needed for:**
- All files in `src/`
- All files in `tools/`
- DBC files in `data/dbc/`
- Translations in `data/translations/`
- UI translations in `i18n/`
- Schema files (`*.capnp`)

Just edit and restart the exe!

**Recompilation needed only for:**
- Changes to `main.py` (but you rarely need to change this)

---

## What's Included in v1.0

### Core Features
- ✅ Windows native application
- ✅ Direct C3/C3X log access via SSH/FTP
- ✅ Synchronized video playback (fcamera, ecamera, dcamera)
- ✅ Multi-signal plotting (300+ cereal + CAN signals)
- ✅ Custom signal calculator (create calculated signals with Python expressions)
- ✅ SQLite database management
- ✅ DBC file support
- ✅ Multilingual UI (English / 繁體中文)
- ✅ Signal translation
- ✅ Data export (CSV / Parquet)
- ✅ Fuzzy signal search
- ✅ Route management
- ✅ Keyboard shortcuts

### Files in Release Package

```
release/v1.0/
├── OpenpilotLogViewer.exe    # Main application (7.8 MB)
├── _internal/                 # PyInstaller dependencies (307 MB)
├── src/                       # Python source code (1.2 MB, modifiable)
├── tools/                     # Utility scripts (168 KB, modifiable)
├── data/                      # DBC files and translations (modifiable)
│   ├── dbc/                   # DBC files
│   ├── translations/          # Signal translations
│   └── configs/               # Configuration files
├── i18n/                      # UI translations (modifiable)
├── *.capnp                    # Schema files
└── LICENSE                    # License file

Total size: ~316 MB
```

---

## System Requirements

- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **RAM**: 4 GB minimum, 8 GB recommended
- **Disk Space**: 500 MB (application + database)
- **Display**: 1920×1080 or higher recommended
- **Python**: Not required for end users

---

## Known Issues and Limitations

### Current Limitations
- Windows only (Linux/Mac support planned for future)
- Uncompressed `.rlog` format only (`.bz2` compressed files not supported - decompress them first)
- Single segment loading (no multi-segment comparison)
- No custom signal calculations yet
- Limited video codec support (HEVC only)

### Known Issues
- None reported yet (this is v1.0!)

---

## Differences from plotjuggler/cabana

| Feature | plotjuggler/cabana | openpilot Windows Viewer |
|---------|-------------------|--------------------------|
| Platform | Linux only | ✅ Windows native |
| Installation | Complex | ✅ Download and run |
| Data Access | Upload to connect.comma.ai | ✅ Direct SSH/FTP |
| Privacy | Cloud upload | ✅ Local only |
| Video Sync | Limited | ✅ Full synchronization |
| Multilingual | English only | ✅ English + 中文 |
| Compatibility | openpilot | ✅ All versions and forks |

---

## Privacy and Security

- **No cloud upload required**: All data stays on your local machine
- **No telemetry**: This application does not send any data to external servers
- **No internet required**: Works completely offline
- **Database**: Stored locally as `oplog.db` (SQLite)

---

## Feedback and Support

- **Bug Reports**: Open an issue on GitHub
- **Feature Requests**: Open an issue with the `enhancement` label
- **Questions**: Open an issue with the `question` label
- **Documentation Issues**: Submit a PR to improve docs

---

## Changelog

See `CHANGELOG.md` for detailed version history.

---

## License

This project is based on openpilot and follows its open-source license. See `LICENSE` file for details.

## Acknowledgments

- **openpilot** team for the amazing self-driving platform
- **FrogPilot** ([FrogAi/FrogPilot](https://github.com/FrogAi/FrogPilot)) - Included log.capnp is from FrogPilot
- **comma.ai** for C3/C3X devices and logging infrastructure

---

**Enjoy analyzing your openpilot logs!** 🚗📊
