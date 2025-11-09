# Changelog

All notable changes to this project will be documented in this file.

## [1.0.1] - 2025-11-08

### Bug Fixes
- **Fixed Re-import Segment Failure**: Resolved `NOT NULL constraint failed` error when re-importing existing segments
  - `insert_segment` now detects existing segments and updates them instead of failing
  - Automatically cleans up old associated data before re-import
- **Optimized Route Deletion Performance**: Dramatically improved deletion speed
  - Changed from CASCADE deletion to batch deletion
  - Reduced deletion time from minutes to seconds for routes with many segments
- **Fixed UI Update After Route Deletion**: Route list now refreshes correctly
  - Clears selection state after deletion
  - Allows consecutive deletions without closing window

### Database Changes
- Added `gps_timestamp` field to segments table (BIGINT)
  - Stores segment's accurate GPS time for future features
- Added `thumbnail_path` field to segments table (TEXT)
  - Prepares for video thumbnail preview feature

### Migration
For existing databases, run:
```sql
ALTER TABLE segments ADD COLUMN gps_timestamp BIGINT;
ALTER TABLE segments ADD COLUMN thumbnail_path TEXT;
```

### Technical Improvements
- Batch deletion optimization using `IN (...)` clause
- Temporary foreign key constraint disabling during batch operations
- Better error handling for constraint violations
- Improved database operation logging

### Files Modified
- `src/core/sqlite_manager.py`: insert_segment, delete_route
- `src/core/segment_importer.py`: segment_id validation
- `src/ui/dialogs/route_manager_dialog.py`: UI refresh logic
- `database_schema_sqlite.sql`: schema updates

See [CHANGELOG_2025-11-08.md](CHANGELOG_2025-11-08.md) for complete technical details.

---

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
