# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2024-11-03

### Added
- **Windows Native Application**: No Linux/WSL required
- **Direct C3/C3X Access**: SSH/FTP support for local log analysis
- **Synchronized Video Playback**: Multi-camera support (fcamera, ecamera, dcamera)
- **Multi-Signal Plotting**: Visualize 300+ cereal signals + CAN signals
- **Database Management**: SQLite-based storage for segments and signals
- **DBC Support**: Import custom DBC files for CAN signal parsing
- **Multilingual UI**: English and Traditional Chinese (繁體中文)
- **Signal Translation**: Auto-translate signal names and descriptions
- **Data Export**: Export to CSV and Parquet formats
- **Signal Search**: Fuzzy search with English/Chinese translation
- **Route Management**: Organize segments by route
- **Keyboard Shortcuts**: Efficient navigation and control
- **Signal Color Allocation**: High-contrast color scheme for better visibility

### Features
- Real-time chart plotting with pyqtgraph
- Frame-by-frame video control
- Time-synchronized video and data playback
- Signal database manager
- Configurable UI language switching
- Modifiable source code without recompilation
- External data files (DBC, translations) for easy customization

### Technical Details
- Built with PyQt6
- SQLite database for efficient data storage
- Capnp schema parsing for cereal signals
- Cantools for DBC parsing
- PyAV for video decoding
- Minimal compilation strategy (main.py only)

### Documentation
- English and Chinese README
- Comprehensive user guide
- Build instructions for developers
- Keyboard shortcuts reference

---

## Future Plans

### Planned Features
- Additional video codecs support
- Custom signal calculations
- Advanced data filtering
- Export to more formats (Excel, JSON)
- Plugin system for extensibility
- Performance optimizations for large logs
- More UI themes

### Known Limitations
- Windows 10/11 only (Linux/Mac support planned)
- rlog format only (no support for other log formats yet)
- Single segment loading (no multi-segment comparison yet)

---

**Note**: This is the initial release. Feedback and contributions are welcome!
