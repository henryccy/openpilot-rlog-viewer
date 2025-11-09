# Changelog - November 8, 2025

## Bug Fixes 🐛

### Bug Fix 1: Re-import Segment Failure

**Problem**:
```
NOT NULL constraint failed: timeseries_data.segment_id
```

**Root Cause**:
- Segments table has `UNIQUE(route_id, segment_number)` constraint
- Re-importing the same segment violates the constraint
- `insert_segment` returns None, causing subsequent timeseries_data inserts to fail with NULL segment_id

**Solution**:
1. `insert_segment` now checks if segment already exists
2. If exists: delete old associated data (timeseries_data, can_messages, log_messages, video_frame_timestamps) and update segment info
3. If not exists: insert new segment
4. Add segment_id validation in segment_importer

**Modified Files**:
- `src/core/sqlite_manager.py`: insert_segment supports re-importing
- `src/core/segment_importer.py`: check if segment_id is None

**Note**: Initial version had thumbnail display issue in segment selector (using DecorationRole), fixed to use QLabel with proper scaling.

---

### Bug Fix 2: Slow Route Deletion and UI Not Updating

**Problem**:
1. Deleting Route takes very long time
2. After deletion, UI doesn't update properly - need to close window to delete another Route

**Root Cause**:
1. CASCADE deletion triggers multiple foreign key checks, inefficient
2. route_table selection state not cleared after deletion
3. Button states not updated

**Solution**:
1. Use manual batch deletion (temporarily disable foreign key checks):
   - Get all segment_ids first
   - Use `IN (...)` for batch deletion
   - Delete in order: timeseries_data → can_messages → log_messages → video_frame_timestamps → segments → routes
2. `load_routes()` clears selection state
3. Clear segment table after deletion

**Modified Files**:
- `src/core/sqlite_manager.py`: optimize delete_route with batch deletion
- `src/ui/dialogs/route_manager_dialog.py`: clear selection state and segment table

**Note**: Fixed table name from `video_timestamps` to `video_frame_timestamps`

---

## Database Schema Updates 🗄️

### Added Fields to segments Table

```sql
-- Added fields
ALTER TABLE segments ADD COLUMN gps_timestamp BIGINT;  -- Segment's own GPS time (Unix timestamp in seconds)
ALTER TABLE segments ADD COLUMN thumbnail_path TEXT;   -- Video preview thumbnail path
```

**Purpose**:
- `gps_timestamp`: Store segment's accurate GPS time for better time display
- `thumbnail_path`: Prepare for future thumbnail preview feature

---

## Database Migration

For existing databases, run:
```sql
ALTER TABLE segments ADD COLUMN gps_timestamp BIGINT;
ALTER TABLE segments ADD COLUMN thumbnail_path TEXT;
```

---

## Version Information

- Update Date: November 8, 2025
- Version: v1.1.0 (Feature Release)
- Backward Compatible: Yes (with database migration)

---

## Release Checklist

Before building:
- [x] Confirm database_schema_sqlite.sql is updated
- [x] Confirm database migration is applied
- [x] Test re-importing segments
- [x] Test deleting routes with many segments
- [x] Test UI updates after route deletion

---

## Performance Improvements ⚡

- **Route Deletion**: Dramatically improved speed (from minutes to seconds for routes with many segments)
- **Database Operations**: Better handling of constraint violations during re-import

---

## Technical Details

### Re-import Logic
When re-importing a segment:
1. Check if segment exists (by route_id and segment_number)
2. If exists:
   - Delete all related data from child tables
   - Update segment record with new information
   - Reuse same segment_id
3. If not exists:
   - Insert as new segment

### Batch Deletion Optimization
```sql
-- Temporarily disable foreign keys
PRAGMA foreign_keys = OFF;

-- Batch delete with IN clause
DELETE FROM timeseries_data WHERE segment_id IN (?, ?, ...);
DELETE FROM can_messages WHERE segment_id IN (?, ?, ...);
DELETE FROM log_messages WHERE segment_id IN (?, ?, ...);
DELETE FROM video_frame_timestamps WHERE segment_id IN (?, ?, ...);

-- Delete segments and route
DELETE FROM segments WHERE route_id = ?;
DELETE FROM routes WHERE route_id = ?;

-- Re-enable foreign keys
PRAGMA foreign_keys = ON;
```

---

## Notes

- This release focuses on stability and performance improvements
- Future releases will add thumbnail preview and caching features
- All changes are backward compatible with existing data
