# openpilot Windows Log Viewer - User Guide

[中文版](USER_GUIDE_zh-TW.md) | English

This guide will help you get started with the openpilot Windows Log Viewer and make the most of its features.

**Signal Definitions**: Based on [FrogPilot](https://github.com/FrogAi/FrogPilot) signal definitions (openpilot 0.9.7 compatible)

## Table of Contents

1. [Installation](#installation)
2. [Getting Logs from C3/C3X](#getting-logs-from-c3c3x)
3. [Importing Data](#importing-data)
4. [Navigating the Interface](#navigating-the-interface)
5. [Analyzing Data](#analyzing-data)
6. [Video Playback](#video-playback)
7. [Exporting Data](#exporting-data)
8. [Keyboard Shortcuts](#keyboard-shortcuts)
9. [Tips and Tricks](#tips-and-tricks)

---

## Installation

### End Users (Recommended)

1. Download the release package from the `release/v1.0/` folder
2. Extract to your preferred location (e.g., `C:\openpilot-viewer\`)
3. That's it! No Python installation required.

### Developers

1. Ensure Python 3.10+ is installed
2. Clone the repository
3. Create virtual environment: `python -m venv venv`
4. Activate: `venv\Scripts\activate`
5. Install dependencies: `pip install -r requirements.txt`
6. Run: `python main.py`

---

## Getting Logs from C3/C3X

There are two main methods to transfer logs from your comma device to your Windows PC:

### Method 1: SSH/SCP (Recommended)

⚠️ **Important**: Modern C3/C3X devices require SSH key authentication (no password login).

**Requirements:**
- SSH client (built-in on Windows 10+, or use PuTTY)
- C3/C3X and PC on the same network
- **SSH key configured** on your comma device (search online for "comma 3 SSH key setup" or "comma 3X SSH access")

**Steps:**

1. **Setup SSH Access** (First Time Only)
   - Search online for: "comma 3 SSH key setup" or "comma 3X SSH access"
   - You'll need to configure your GitHub SSH key with your comma device
   - Refer to comma.ai documentation or community guides for detailed steps

2. **Find your device's IP address**
   - On C3/C3X, go to Settings → Network
   - Note the IP address (e.g., `192.168.1.100`)

3. **Connect via SSH**
   ```bash
   # After SSH key is configured
   ssh comma@192.168.1.100
   ```

4. **Navigate to logs directory**
   ```bash
   cd /data/media/0/realdata/
   ls -lt  # List logs by modification time
   ```

5. **Copy logs to Windows**

   From Windows command prompt or PowerShell:
   ```bash
   # Copy entire segment directory (IMPORTANT: Must copy the whole folder)
   # The segment directory contains:
   #   - rlog or rlog.bz2 (log file)
   #   - fcamera.hevc, ecamera.hevc, dcamera.hevc (video files)
   #   - Other related files
   scp -r comma@192.168.1.100:/data/media/0/realdata/2024-01-01--12-00-00 C:\logs\
   ```

   **Important**: Always copy the entire segment directory, not individual files. The segment structure includes both log and video files needed for complete analysis.

### Method 2: FTP Client (Easier for Beginners)

⚠️ **Important**: You need to configure SSH key authentication first (see Method 1, Step 1).

**Recommended Tools:**
- WinSCP (Free, Windows)
- FileZilla (Free, Cross-platform)

**Steps using WinSCP:**

1. Download and install [WinSCP](https://winscp.net/)
2. Launch WinSCP and create a new connection:
   - **Protocol**: SCP or SFTP
   - **Host**: Your C3/C3X IP (e.g., `192.168.1.100`)
   - **Username**: `comma`
   - **Authentication**: Configure SSH private key (required!)
3. Click "Login"
4. Navigate to `/data/media/0/realdata/`
5. Drag and drop folders to your Windows location

---

## Importing Data

### Step 1: Import Signal Definitions (First Time and After Updates)

Before importing any logs, you need to import signal definitions:

1. Click **Tools → Import Signal Definitions**
2. The dialog shows what will be imported:
   - Cereal signals from `log.capnp` (FrogPilot definitions, openpilot 0.9.7 compatible) - 300-500 signals
   - CAN signals from DBC files in `data/dbc/` folder
3. Click **Start Import**
4. Wait for completion (typically 30-60 seconds)

**Required Files**:
- `log.capnp` (main schema file - from FrogPilot)
- `car.capnp`, `legacy.capnp`, `custom.capnp`, `maptile.capnp` (dependency files - must be in the same directory as log.capnp)
- DBC files in `data/dbc/` folder

Note: When importing, you only need to select `log.capnp`. The other 4 dependency files will be automatically loaded from the same directory.

⚠️ **When to Re-import**:
- **First time** using the application
- **After updating signal definition files** (log.capnp or DBC files)
- **When using logs from different openpilot/FrogPilot versions**

### Step 2: Import Segment

Now you can import log data:

1. Click **Tools → Import Segment**
2. In the import dialog:
   - **Route Name**: Optional, e.g., "Highway Test Drive"
   - **rlog Path**: Browse to your rlog file (e.g., `C:\logs\2024-01-01--12-00-00\0\rlog`)
   - **DBC Files**: Select which DBC files to use for CAN parsing (or leave default)
3. Click **Start Import**

⚠️ **Note**: Only uncompressed `.rlog` files are supported. If you have `.bz2` compressed files, decompress them first:
```bash
bzip2 -d rlog.bz2
```
4. Monitor progress in the log window
5. When complete, the segment appears in the main window

**Import Time**: Depends on log size, typically 1-5 minutes for a 1-minute segment.

### Important: File Management After Import

After importing a segment, you need to understand which files can be deleted and which must be kept:

- ✅ **Video files** (fcamera.hevc, ecamera.hevc, dcamera.hevc):
  - **Must remain in original location**
  - The database stores the video file paths
  - If you move or delete these files, video playback will not work
  - Data charts and signal analysis will still function normally

- ✅ **rlog files** (rlog or rlog.bz2):
  - **Can be deleted after import** to save disk space
  - All signal data has been imported into the database
  - Only delete if you're certain you won't need to re-import

⚠️ **Best Practice**: Keep video files in the same location you imported from. If you need to reorganize files, consider re-importing the segment after moving.

---

## Navigating the Interface

### Main Window Layout

```
┌─────────────────────────────────────────────────────────┐
│ Menu Bar                                                │
├──────────────┬──────────────────────────────────────────┤
│              │                                          │
│  Segment     │                                          │
│  List        │        Video Player                      │
│  (Left)      │        (Top Right)                       │
│              │                                          │
├──────────────┼──────────────────────────────────────────┤
│              │                                          │
│  Signal      │        Chart Area                        │
│  Selector    │        (Bottom Right)                    │
│  (Left)      │                                          │
│              │                                          │
└──────────────┴──────────────────────────────────────────┘
```

### Segment List (Left Panel)

- Shows all imported segments
- **Double-click** a segment to load it
- Right-click for options:
  - Delete segment
  - Export data
  - View segment info

### Signal Selector (Left Panel, Bottom)

- **Search box**: Type to search signals (supports English/Chinese)
- **Checkbox**: Select/deselect signals to plot
- **Color indicator**: Shows the color used in chart
- **Signal categories**:
  - 📡 Cereal signals (from schema)
  - 🚗 CAN signals (from DBC)

### Video Player (Top Right)

- Displays camera footage (fcamera, ecamera, dcamera)
- Timeline synced with chart
- Controls: Play, Pause, Seek, Frame-by-frame

### Chart Area (Bottom Right)

- Multi-signal plotting
- **X-axis**: Time (seconds)
- **Y-axis**: Signal value
- **Mouse interactions**:
  - **Scroll**: Zoom in/out
  - **Click and drag**: Pan
  - **Right-click**: Reset view
  - **Hover**: Show signal value

---

## Analyzing Data

### Searching for Signals

1. Use the **search box** in the Signal Selector
2. Type keywords:
   - English: `speed`, `steering`, `acceleration`
   - Chinese: `速度`, `轉向`, `加速度`
3. Fuzzy search is supported: `spd` matches `vEgo` (vehicle speed)

### Plotting Signals

1. **Check the box** next to signal names to plot them
2. Signals appear in the chart with different colors
3. **Uncheck** to remove from chart

### Understanding Signal Categories

- **carState.vEgo**: Vehicle speed (cereal signal)
- **steeringAngleDeg**: Steering angle (CAN signal from DBC)
- **carControl.actuators**: Control outputs (cereal signal)

### Comparing Signals

- Plot multiple signals simultaneously
- Different signals may have different scales - this is normal
- Use the chart legend to identify signals by color

### Time Navigation

- **Click on chart**: Video jumps to that timestamp
- **Drag timeline**: Scrub through video and data simultaneously
- **Keyboard shortcuts**: See [Keyboard Shortcuts](#keyboard-shortcuts)

---

## Video Playback

### Selecting Camera

1. Go to **View → Camera**
2. Choose:
   - **fcamera** (front camera, default)
   - **ecamera** (wide camera)
   - **dcamera** (driver camera)

### Playback Controls

- **Spacebar**: Play/Pause
- **Left/Right Arrow**: Previous/Next frame
- **Up/Down Arrow**: Jump ±5 seconds
- **Click on timeline**: Jump to specific time

### Synchronized Viewing

- Video timeline is linked to chart X-axis
- When you click on a data point in the chart, video jumps to that frame
- When you scrub the video, a vertical line in the chart shows current time

---

## Exporting Data

### Export to CSV

1. Right-click on segment in Segment List
2. Select **Export to CSV**
3. Choose location and filename
4. CSV includes:
   - Timestamp
   - All available signal values
   - One row per time sample

### Export to Parquet

1. Right-click on segment in Segment List
2. Select **Export to Parquet**
3. Choose location and filename
4. Parquet format:
   - Smaller file size than CSV
   - Preserves data types
   - Faster to load in pandas/Python

### Using Exported Data

**Python example:**

```python
import pandas as pd

# Load CSV
df = pd.read_csv('segment_export.csv')

# Load Parquet
df = pd.read_parquet('segment_export.parquet')

# Analyze
print(df['carState.vEgo'].describe())
print(df['steeringAngleDeg'].max())
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **Spacebar** | Play/Pause video |
| **Left Arrow** | Previous frame |
| **Right Arrow** | Next frame |
| **Up Arrow** | Jump +5 seconds |
| **Down Arrow** | Jump -5 seconds |
| **Ctrl+O** | Open Import Segment dialog |
| **Ctrl+S** | Save/Export current segment |
| **Ctrl+F** | Focus search box |
| **Ctrl+W** | Close current segment |
| **Ctrl+Q** | Quit application |
| **F11** | Toggle fullscreen |

---

## Custom Signals (Signal Calculator)

In addition to cereal and CAN signals, you can define your own calculated signals using Python expressions.

### How to Use

1. Click `Tools → Signal Calculator`
2. Create a new custom signal:
   - **Signal Name**: e.g., "speedKmh", "accelG", "followDistance"
   - **Expression**: Use Python syntax to calculate the signal value
   - **Unit**: Optional, e.g., "km/h", "G", "m"
   - **Description**: Optional, explain what this signal represents

3. Save the signal - it will appear in the signal selector
4. You can plot and analyze custom signals just like regular signals

### Expression Examples

**Speed Conversion** (m/s to km/h):
```python
carState.vEgo * 3.6
```

**Acceleration in G-force**:
```python
carState.aEgo / 9.81
```

**Relative Distance Between Lead Vehicles**:
```python
radarState.leadOne.dRel - radarState.leadTwo.dRel
```

**Conditional Logic** (Speed threshold indicator):
```python
1 if carState.vEgo > 30 else 0
```

**Complex Calculations** (Stopping distance estimate):
```python
(carState.vEgo ** 2) / (2 * abs(carState.aEgo)) if carState.aEgo < 0 else 0
```

**Multiple Signal Operations**:
```python
(carState.vEgo * 3.6) - (radarState.leadOne.vRel * 3.6)
```

### Available Functions

You can use Python's built-in math functions:
- `abs()`, `max()`, `min()`
- `round()`, `int()`, `float()`
- Mathematical operators: `+`, `-`, `*`, `/`, `**` (power), `%` (modulo)
- Comparison: `>`, `<`, `>=`, `<=`, `==`, `!=`
- Logical: `and`, `or`, `not`
- Conditional: `x if condition else y`

### Important Notes

- Expressions must be valid Python syntax
- You can reference any imported signal from the database
- Custom signals are stored in the database and can be reused across segments
- Invalid expressions will show an error message
- Signal values are evaluated at each timestamp

### Managing Custom Signals

- **Edit**: Click on an existing custom signal to modify it
- **Delete**: Remove custom signals you no longer need
- **Export/Import**: Custom signals are stored in `oplog.db` - backup this file to preserve your custom signals

---

## Tips and Tricks

### 1. Faster Log Transfer

- Use a **USB cable** connection to C3/C3X for faster transfer (requires SSH over USB setup)
- Compress logs before transfer: `tar czf logs.tar.gz 2024-01-01--12-00-00/`

### 2. Organizing Logs

Create a folder structure:
```
C:\openpilot-logs\
├── 2024-01\
│   ├── 2024-01-01--12-00-00\
│   └── 2024-01-02--08-30-00\
└── 2024-02\
    └── 2024-02-05--15-45-00\
```

### 3. Custom Signal Translations

Edit `data/translations/signals_zh_TW.json` to add your own translations:

```json
{
  "carState.vEgo": "車速",
  "carState.aEgo": "加速度",
  "myCustomSignal": "我的自訂訊號"
}
```

Restart the application to see changes.

### 4. Adding Custom DBC Files

1. Place your `.dbc` file in `data/dbc/` folder
2. Restart application
3. Go to **Tools → Import Signal Definitions**
4. Your DBC signals will be imported

### 5. Performance Optimization

- Close unused segments to free memory
- Limit the number of signals plotted simultaneously (max 10 recommended)
- Use Parquet export for large datasets

### 6. Troubleshooting Import Errors

If import fails:
1. Check `oplog_viewer.log` in the application directory
2. Verify rlog file is not corrupted (must be uncompressed `.rlog` format)
3. If you have a `.bz2` file, decompress it first: `bzip2 -d rlog.bz2`
4. Ensure DBC files are valid
5. Try importing a smaller segment first

### 7. Working Offline

- No internet connection required!
- All processing is local
- Database is stored in `oplog.db` (SQLite)

### 8. Backup Your Database

- Copy `oplog.db` to backup location
- Contains all imported segments and signal definitions
- Restore by replacing the file

---

## Advanced Features

### Database Management

- **View → Signal Database Manager**: Browse all signal definitions
- **Tools → Reset Database**: Clear all data (use with caution!)

### Route Management

- **Tools → Route Manager**: Organize segments by route
- Group related segments together
- Add notes and metadata

### Multi-Language Support

- **View → Language**: Switch between English and 繁體中文
- Signal names are automatically translated where available

---

## Getting Help

- **Help → User Manual**: This document
- **Help → Keyboard Shortcuts**: Quick reference
- **Help → About**: Version and license info

---

## Feedback and Contributions

Found a bug or have a feature request? Please open an issue on GitHub!

Happy analyzing! 🚗📊
