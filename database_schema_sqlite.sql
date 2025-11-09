-- SQLite Schema for openpilot Windows Viewer
-- 設計原則：單一 .db 檔案包含所有資料，易於分享和部署

-- ============================================================================
-- 1. Routes 表：記錄 route 資訊
-- ============================================================================
CREATE TABLE IF NOT EXISTS routes (
    route_id TEXT PRIMARY KEY,
    timestamp BIGINT,  -- 記錄時間（從第一個 segment 計算）
    start_timestamp BIGINT,  -- Route 起始時間（Unix timestamp，用於準確計算各 segment 時間）
    dbc_file TEXT,
    total_segments INTEGER DEFAULT 0,
    total_events INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 2. Segments 表：記錄每個 segment 資訊
-- ============================================================================
CREATE TABLE IF NOT EXISTS segments (
    segment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id TEXT NOT NULL,
    segment_number INTEGER NOT NULL,

    -- 時間資訊
    start_time_ns BIGINT NOT NULL,
    end_time_ns BIGINT NOT NULL,
    wall_time_offset BIGINT NOT NULL,  -- 用於轉換 logMonoTime 到真實時間
    duration_seconds REAL,
    gps_timestamp BIGINT,  -- Segment's own GPS time (Unix timestamp in seconds), if available

    -- 檔案路徑
    rlog_path TEXT,
    ecamera_path TEXT,
    fcamera_path TEXT,
    qcamera_path TEXT,
    thumbnail_path TEXT,  -- Video preview thumbnail path

    -- 統計資訊
    total_events INTEGER DEFAULT 0,

    -- 元資料
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (route_id) REFERENCES routes(route_id) ON DELETE CASCADE,
    UNIQUE(route_id, segment_number)
);

CREATE INDEX IF NOT EXISTS idx_segments_route ON segments(route_id);

-- ============================================================================
-- 3. Timeseries Data 表：時序資料（carState, controlsState 等）
-- ============================================================================
CREATE TABLE IF NOT EXISTS timeseries_data (
    data_id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id INTEGER NOT NULL,
    time_ns BIGINT NOT NULL,
    signal_name TEXT NOT NULL,
    value REAL,

    FOREIGN KEY (segment_id) REFERENCES segments(segment_id) ON DELETE CASCADE
);

-- 關鍵索引：時間範圍查詢
CREATE INDEX IF NOT EXISTS idx_timeseries_segment_time
    ON timeseries_data(segment_id, time_ns);

-- 訊號名稱索引
CREATE INDEX IF NOT EXISTS idx_timeseries_signal
    ON timeseries_data(signal_name);

-- 複合索引：訊號 + 時間
CREATE INDEX IF NOT EXISTS idx_timeseries_signal_time
    ON timeseries_data(segment_id, signal_name, time_ns);

-- ============================================================================
-- 4. CAN Messages 表：原始 CAN 訊息
-- ============================================================================
CREATE TABLE IF NOT EXISTS can_messages (
    can_id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id INTEGER NOT NULL,
    time_ns BIGINT NOT NULL,
    address INTEGER NOT NULL,  -- CAN ID
    data BLOB NOT NULL,  -- CAN data (最多 8 bytes)

    FOREIGN KEY (segment_id) REFERENCES segments(segment_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_can_segment_time
    ON can_messages(segment_id, time_ns);

CREATE INDEX IF NOT EXISTS idx_can_address
    ON can_messages(address);

-- ============================================================================
-- 5. Log Messages 表：logMessage 和 errorLogMessage
-- ============================================================================
CREATE TABLE IF NOT EXISTS log_messages (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id INTEGER NOT NULL,
    time_ns BIGINT NOT NULL,
    log_type TEXT NOT NULL CHECK(log_type IN ('log', 'error')),  -- 'log' 或 'error'

    -- 基本欄位
    daemon TEXT,
    levelnum INTEGER,
    filename TEXT,
    funcname TEXT,
    lineno INTEGER,

    -- 訊息內容
    message TEXT NOT NULL,

    -- 上下文資訊
    dongle_id TEXT,
    version TEXT,
    branch TEXT,
    "commit" TEXT,  -- 使用引號因為 commit 是 SQLite 保留關鍵字

    FOREIGN KEY (segment_id) REFERENCES segments(segment_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_log_segment_time
    ON log_messages(segment_id, time_ns);

CREATE INDEX IF NOT EXISTS idx_log_type
    ON log_messages(segment_id, log_type);

CREATE INDEX IF NOT EXISTS idx_log_daemon
    ON log_messages(daemon);

-- ============================================================================
-- 6. Cereal Signal Definitions 表：Cereal 訊號定義
-- ============================================================================
CREATE TABLE IF NOT EXISTS cereal_signal_definitions (
    signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_type TEXT NOT NULL,  -- 'carState', 'controlsState', etc.
    signal_name TEXT NOT NULL,  -- 'vEgo', 'aEgo', etc.
    full_name TEXT NOT NULL,  -- 'carState.vEgo'
    data_type TEXT,  -- 'float', 'int', 'bool'
    unit TEXT,
    unit_cn TEXT,
    name_cn TEXT,
    description_cn TEXT,

    UNIQUE(message_type, signal_name)
);

CREATE INDEX IF NOT EXISTS idx_cereal_full_name
    ON cereal_signal_definitions(full_name);

-- ============================================================================
-- 7. CAN Signal Definitions 表：CAN 訊號定義
-- ============================================================================
CREATE TABLE IF NOT EXISTS can_signal_definitions (
    signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dbc_file TEXT NOT NULL,
    can_id INTEGER NOT NULL,
    can_id_hex TEXT,
    message_name TEXT NOT NULL,
    message_name_cn TEXT,
    signal_name TEXT NOT NULL,
    full_name TEXT,  -- 'CAN_0x123_SignalName'
    start_bit INTEGER,
    length INTEGER,
    byte_order TEXT,
    is_signed INTEGER,
    factor REAL,
    offset REAL,
    min_value REAL,
    max_value REAL,
    unit TEXT,
    unit_cn TEXT,
    signal_name_cn TEXT,
    description_cn TEXT,
    comment TEXT,

    UNIQUE(dbc_file, can_id, signal_name)
);

CREATE INDEX IF NOT EXISTS idx_can_def_full_name
    ON can_signal_definitions(full_name);

CREATE INDEX IF NOT EXISTS idx_can_def_can_id
    ON can_signal_definitions(can_id);

-- ============================================================================
-- 8. Custom Signals 表：自訂計算訊號
-- ============================================================================
CREATE TABLE IF NOT EXISTS custom_signals (
    custom_id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_name TEXT NOT NULL UNIQUE,
    signal_name_cn TEXT,
    description_cn TEXT,
    formula TEXT NOT NULL,
    unit TEXT,
    unit_cn TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 8.5. Video Frame Timestamps 表：影片幀時間戳記
-- ============================================================================
CREATE TABLE IF NOT EXISTS video_frame_timestamps (
    frame_id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id INTEGER NOT NULL,
    camera TEXT NOT NULL,  -- 'ecamera', 'fcamera', 'qcamera'
    frame_number INTEGER NOT NULL,
    timestamp_sof BIGINT NOT NULL,  -- 幀的實際時間戳記（從 EncodeIndex 讀取）

    FOREIGN KEY (segment_id) REFERENCES segments(segment_id) ON DELETE CASCADE,
    UNIQUE(segment_id, camera, frame_number)
);

CREATE INDEX IF NOT EXISTS idx_video_frames_segment_camera
    ON video_frame_timestamps(segment_id, camera);

CREATE INDEX IF NOT EXISTS idx_video_frames_segment_camera_frame
    ON video_frame_timestamps(segment_id, camera, frame_number);

-- ============================================================================
-- 9. DBC Files 表：可用的 DBC 檔案
-- ============================================================================
CREATE TABLE IF NOT EXISTS dbc_files (
    dbc_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL UNIQUE,
    file_path TEXT NOT NULL,
    description TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 視圖：完整的 route 資訊（含第一個 segment 的真實時間）
-- ============================================================================
CREATE VIEW IF NOT EXISTS routes_with_info AS
SELECT
    r.route_id,
    r.dbc_file,
    r.total_segments,
    r.total_events,
    MIN(s.start_time_ns + s.wall_time_offset) as timestamp_ns,
    datetime(MIN(s.start_time_ns + s.wall_time_offset) / 1000000000, 'unixepoch') as record_time,
    r.created_at
FROM routes r
LEFT JOIN segments s ON r.route_id = s.route_id
GROUP BY r.route_id;

-- ============================================================================
-- 視圖：完整的 segment 資訊（含真實時間）
-- ============================================================================
CREATE VIEW IF NOT EXISTS segments_with_info AS
SELECT
    s.segment_id,
    s.route_id,
    s.segment_number,
    s.start_time_ns,
    s.end_time_ns,
    s.wall_time_offset,
    datetime((s.start_time_ns + s.wall_time_offset) / 1000000000, 'unixepoch') as start_time,
    datetime((s.end_time_ns + s.wall_time_offset) / 1000000000, 'unixepoch') as end_time,
    ROUND((s.end_time_ns - s.start_time_ns) / 1000000000.0, 2) as duration_seconds,
    s.total_events,
    s.ecamera_path,
    s.fcamera_path,
    s.qcamera_path,
    s.created_at
FROM segments s;

-- ============================================================================
-- 應用程式版本資訊
-- ============================================================================
CREATE TABLE IF NOT EXISTS app_version (
    version_id INTEGER PRIMARY KEY CHECK (version_id = 1),
    schema_version INTEGER NOT NULL,
    app_version TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入初始版本
INSERT OR IGNORE INTO app_version (version_id, schema_version, app_version)
VALUES (1, 1, '2.0.0-sqlite');

-- ============================================================================
-- 完成
-- ============================================================================
-- Schema 版本：1
-- 設計日期：2025-10-27
-- 特點：
--   - 單一檔案，易於分享
--   - 優化的索引，查詢速度快
--   - 支援所有現有功能
--   - 支援未來擴展（感測器資料、規劃資料等）
-- ============================================================================
