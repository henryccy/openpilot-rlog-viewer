# openpilot Windows Log Viewer

[中文說明](README_zh-TW.md) | English

A native Windows application for viewing and analyzing openpilot logs locally, without the need for Linux environment or uploading to connect.comma.ai.

**Signal Definitions**: Based on [FrogPilot](https://github.com/FrogAi/FrogPilot) signal definitions (openpilot 0.9.7 compatible)

## Why This Tool?

### Differences from plotjuggler and cabana

openpilot officially provides **plotjuggler** and **cabana** for log analysis, but they have limitations:

| Feature | plotjuggler/cabana | **openpilot Windows Viewer** |
|---------|-------------------|------------------------------|
| **Platform** | Linux only (requires WSL on Windows) | ✅ Native Windows application |
| **Installation** | Complex setup with dependencies | ✅ Download and run (no Python required) |
| **Data Access** | Upload to connect.comma.ai first | ✅ **Direct local analysis** via SSH/FTP |
| **Workflow** | C3/C3X → upload → download → analyze | ✅ C3/C3X → SSH/FTP → analyze immediately |
| **Privacy** | Upload required | ✅ All data stays local |
| **Speed** | Wait for upload/download | ✅ Instant analysis |

### Key Advantages

- **🪟 Windows Native**: No Linux VM, no WSL, no Docker
- **🚀 Direct C3/C3X Access**: SSH or FTP to copy logs directly to local disk
- **🔒 Privacy First**: No cloud upload required - analyze locally
- **⚡ Fast Workflow**: Skip upload/download steps
- **🎨 Rich Features**: Synchronized video/data playback, signal search, multilingual support

## Quick Start

### For End Users (No Programming Required)

1. **Download Release**
   - Download `release/v1.0.zip` from the release folder
   - Extract to any location (e.g., `C:\openpilot-viewer\`)

2. **Setup SSH Access to C3/C3X** (First Time Only)

   ⚠️ **Important**: Modern C3/C3X devices require SSH key authentication (no password login).

   To configure SSH access:
   - Search online for: "comma 3 SSH key setup" or "comma 3X SSH access"
   - You'll need to configure your GitHub SSH key with your comma device
   - Refer to comma.ai documentation or community guides for detailed steps

3. **Get Logs from C3/C3X**

   **Option A: SSH/SCP (Recommended)**
   ```bash
   # After SSH key is configured, connect to your C3/C3X
   ssh comma@192.168.x.x

   # Find your log file (typically in /data/media/0/realdata/)
   cd /data/media/0/realdata/
   ls -lt

   # Copy entire segment directory to Windows using SCP
   # IMPORTANT: Must copy the entire segment folder, not just individual files
   # The segment contains rlog + video files (fcamera.hevc, ecamera.hevc, etc.)
   scp -r comma@192.168.x.x:/data/media/0/realdata/2024-01-01--12-00-00 C:\logs\
   ```

   **Option B: FTP Client with SSH Key**
   - Use WinSCP or FileZilla (configure SSH key authentication)
   - Connect to C3/C3X at `192.168.x.x`
   - Navigate to `/data/media/0/realdata/`
   - Download the segment folder to local disk

4. **Run the Application**
   - Double-click `OpenpilotLogViewer.exe`

5. **First Time Setup: Import Signal Definitions**
   - Go to `Tools → Import Signal Definitions`
   - This imports cereal signals from `log.capnp` (FrogPilot definitions, openpilot 0.9.7 compatible) and CAN signals from DBC files
   - **Required files**:
     - `log.capnp` (main schema file - from FrogPilot)
     - `car.capnp`, `legacy.capnp`, `custom.capnp`, `maptile.capnp` (dependency files - must be in the same directory as log.capnp)
     - DBC files in `data/dbc/` folder
   - When importing, you only need to select `log.capnp`. The other 4 dependency files will be automatically loaded from the same directory.
   - Click "Start Import" and wait for completion (~30-60 seconds)

   ⚠️ **When to Re-import**:
   - First time using the application
   - After updating signal definition files (log.capnp or DBC files)
   - When using logs from different openpilot/FrogPilot versions

6. **Import and Analyze Segments**
   - Use `Tools → Import Segment` to load your rlog file
   - Analyze data with synchronized video playback!

   **Important: File Management After Import**:
   - ✅ **Video files**: Must remain in original location (database stores video file paths)
   - ✅ **rlog files**: Can be deleted to save space (data is imported to database)
   - ⚠️ If you move or delete video files, video playback will not work (but data charts remain functional)

### For Developers

1. **Clone Repository**
   ```bash
   git clone https://github.com/yourusername/openpilot-log-viewer.git
   cd openpilot-log-viewer
   ```

2. **Install Dependencies**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Run from Source**
   ```bash
   python main.py
   ```

4. **Build EXE (Optional)**
   ```bash
   build_exe.bat
   ```
   See [README_BUILD.md](README_BUILD.md) for detailed build instructions.

## Features

### 📊 Data Analysis
- **Signal Browsing**: Browse 300+ cereal signals + CAN signals
- **Real-time Search**: Fuzzy search with English/Chinese translation
- **Chart Visualization**: Multi-signal synchronized plotting with pyqtgraph
- **Custom Signals**: Create calculated signals with Python expressions (e.g., speed conversion, G-force)
- **Data Export**: Export to CSV/Parquet for further analysis

### 🎥 Video Playback
- **Synchronized Playback**: Video timeline synced with data charts
- **Multi-camera Support**: fcamera, ecamera, dcamera
- **Frame Control**: Play, pause, seek, frame-by-frame navigation

### 🗄️ Database Management
- **SQLite Storage**: Efficient local database
- **Quick Access**: Browse previously imported segments
- **DBC Support**: Import custom DBC files for CAN signal parsing

### 🌍 Multilingual
- **English** and **繁體中文** (Traditional Chinese)
- Auto-translate signal names and descriptions
- Switch language on-the-fly

## System Requirements

- **OS**: Windows 10/11 (64-bit)
- **RAM**: 4GB minimum, 8GB+ recommended
- **Disk**: 100MB for application + space for log files
- **Python**: Not required for end users (included in exe)

## File Structure

```
openpilot-log-viewer-release/
├── README.md                    # This file (English)
├── README_zh-TW.md              # Chinese documentation
├── README_BUILD.md              # Build instructions for developers
│
├── release/
│   └── v1.0/                    # Ready-to-run release
│       ├── OpenpilotLogViewer.exe
│       ├── _internal/           # PyInstaller dependencies
│       ├── src/                 # Python source code (modifiable)
│       ├── tools/               # Utility scripts (modifiable)
│       ├── data/                # DBC files, translations (modifiable)
│       ├── i18n/                # UI translations (modifiable)
│       └── *.capnp              # Schema files
│
└── (source code files)          # Full source for developers
```

## Workflow Example

### Traditional Way (plotjuggler/cabana)
```
1. Drive with C3/C3X
2. Wait for upload to connect.comma.ai (automatic, may take hours)
3. Download from connect.comma.ai to local machine
4. Install Linux/WSL environment
5. Setup plotjuggler dependencies
6. Finally analyze the log
```

### With openpilot Windows Viewer
```
1. Drive with C3/C3X
2. SSH/FTP to copy log files directly (takes minutes)
3. Double-click OpenpilotLogViewer.exe
4. Analyze immediately!
```

**Time saved**: Hours → Minutes
**Privacy**: Cloud upload → Local only

## FAQ

### Q: Do I need to upload logs to connect.comma.ai?
**A**: No! This tool works entirely offline. Copy logs directly from C3/C3X via SSH/FTP.

### Q: Can I modify the source code?
**A**: Yes! The `src/`, `tools/`, `data/`, and `i18n/` folders contain editable Python source code. Modify them directly without recompiling the exe. See [README_BUILD.md](README_BUILD.md) for details.

### Q: Does this replace plotjuggler/cabana?
**A**: Not entirely. This tool focuses on Windows users and local analysis. plotjuggler/cabana have their own strengths in the Linux ecosystem.

### Q: What log format is supported?
**A**: Currently supports openpilot rlog format (uncompressed `.rlog` files only). The log should contain cereal messages. Compatible with openpilot 0.9.7 and FrogPilot.

Note: `.bz2` compressed files are not supported. Please decompress them first using: `bzip2 -d rlog.bz2`

### Q: Do I need to re-import signal definitions?
**A**: Yes, re-import when:
- First time using the application
- After updating signal definition files (log.capnp or DBC files)
- When switching between different openpilot/FrogPilot versions

Make sure all 5 capnp files (`log.capnp`, `car.capnp`, `legacy.capnp`, `custom.capnp`, `maptile.capnp`) are in the same directory. You only need to select `log.capnp` when importing - the other 4 files will be automatically loaded from the same location.

### Q: Which openpilot version is this compatible with?
**A**: This release uses signal definitions from FrogPilot (based on openpilot 0.9.7). It should work with most openpilot 0.9.x and FrogPilot logs.

### Q: How do I setup SSH access to C3/C3X?
**A**: Modern comma devices require SSH key authentication. Search for "comma 3 SSH key setup" or "comma 3X SSH access GitHub key" for detailed guides.

### Q: Can I use custom DBC files?
**A**: Yes! Place DBC files in `data/dbc/` folder and use `Tools → Import Signal Definitions` to import them.

### Q: How do I add more CAN signal translations?
**A**: Edit `data/translations/signals_zh_TW.json` and restart the application. No recompilation needed!

## Troubleshooting

### "Cannot connect to database"
- Ensure you have write permissions in the application directory
- Check if `oplog.db` is not opened by another program

### "Failed to import segment"
- Verify the rlog file is not corrupted
- Check if you have imported DBC files (for CAN signal parsing)
- Look at `oplog_viewer.log` for detailed error messages

### "Video playback not working"
- Ensure the segment contains video files (e.g., `fcamera.hevc`)
- Install latest graphics drivers
- Check if av (PyAV) library is properly installed (for developers)

## License

This project is based on openpilot and follows its open-source license.

## Acknowledgments

- **openpilot** team for the amazing self-driving platform
- **FrogPilot** ([FrogAi/FrogPilot](https://github.com/FrogAi/FrogPilot)) - Signal definitions based on FrogPilot
- **comma.ai** for C3/C3X devices and logging infrastructure
- **PyQt6** for the GUI framework
- **pyqtgraph** for high-performance plotting

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Links

- [openpilot](https://github.com/commaai/openpilot) - openpilot 0.9.7
- [FrogPilot](https://github.com/FrogAi/FrogPilot) - Signal definitions source
- [comma.ai](https://comma.ai/)
- [Build Instructions](README_BUILD.md)

---

**Note**: This is an unofficial community tool and is not affiliated with comma.ai or FrogPilot. Always follow local laws when using openpilot.
