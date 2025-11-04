"""
將 rlog segment 匯入 SQLite 資料庫
"""
import sys
import os
from pathlib import Path

# 加入專案路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

import capnp
import time
import logging
from src.core.sqlite_manager import SQLiteManager

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 載入 Cap'n Proto schema
capnp.remove_import_hook()
log_capnp = capnp.load('log.capnp')
car_capnp = capnp.load('car.capnp')


def extract_init_data(rlog_path):
    """從 rlog 提取 initData（用於時間轉換）"""
    with open(rlog_path, 'rb') as f:
        for event in log_capnp.Event.read_multiple(f):
            if event.which() == 'initData':
                wall_time_nanos = event.initData.wallTimeNanos
                return wall_time_nanos
    return None


def import_segment(rlog_path: str, db_path: str = None, dbc_file: str = None):
    """
    匯入一個 rlog segment 到 SQLite

    Args:
        rlog_path: rlog 檔案路徑
        db_path: SQLite 資料庫路徑
        dbc_file: DBC 檔案名稱
    """
    rlog_path = Path(rlog_path)

    if not rlog_path.exists():
        logger.error(f"rlog file not found: {rlog_path}")
        return False

    # 從路徑解析 route_id 和 segment_number
    # 格式: raw/00000009--f5d34548e1--0/rlog
    parts = rlog_path.parts
    if len(parts) >= 2:
        route_segment = parts[-2]  # "00000009--f5d34548e1--0"
        if '--' in route_segment:
            route_parts = route_segment.split('--')
            if len(route_parts) == 3:
                segment_number = int(route_parts[2])
                route_id = '--'.join(route_parts[:2])
            else:
                logger.error(f"Invalid route-segment format: {route_segment}")
                return False
        else:
            logger.error(f"Invalid route-segment format: {route_segment}")
            return False
    else:
        logger.error(f"Cannot parse route_id from path: {rlog_path}")
        return False

    logger.info("=" * 80)
    logger.info(f"Importing rlog to SQLite")
    logger.info("=" * 80)
    logger.info(f"rlog path:    {rlog_path}")
    logger.info(f"Route ID:     {route_id}")
    logger.info(f"Segment:      {segment_number}")
    logger.info(f"Database:     {db_path or 'data/openpilot.db'}")
    logger.info("=" * 80)

    # 連接資料庫
    db = SQLiteManager(db_path)
    if not db.connect():
        logger.error("Failed to connect to database")
        return False

    try:
        # 確保資料表存在
        db.create_tables()

        # 提取 initData
        logger.info("Extracting initData...")
        wall_time_nanos = extract_init_data(rlog_path)

        if wall_time_nanos is None:
            logger.error("Cannot find initData in rlog")
            return False

        # 第一次掃描：取得時間範圍
        logger.info("Scanning rlog for time range...")
        min_time_ns = None
        max_time_ns = None

        with open(rlog_path, 'rb') as f:
            for event in log_capnp.Event.read_multiple(f):
                time_ns = event.logMonoTime
                if min_time_ns is None or time_ns < min_time_ns:
                    min_time_ns = time_ns
                if max_time_ns is None or time_ns > max_time_ns:
                    max_time_ns = time_ns

        # 計算 wall_time_offset
        wall_time_offset = wall_time_nanos - min_time_ns

        logger.info(f"Time range: {min_time_ns} - {max_time_ns}")
        logger.info(f"Wall time offset: {wall_time_offset}")

        # 計算真實時間
        from datetime import datetime
        real_time_start = datetime.fromtimestamp((min_time_ns + wall_time_offset) / 1e9)
        real_time_end = datetime.fromtimestamp((max_time_ns + wall_time_offset) / 1e9)
        logger.info(f"Real time: {real_time_start} ~ {real_time_end}")

        # 查找影片檔案
        segment_dir = rlog_path.parent
        ecamera_path = str(segment_dir / "ecamera.hevc") if (segment_dir / "ecamera.hevc").exists() else None
        fcamera_path = str(segment_dir / "fcamera.hevc") if (segment_dir / "fcamera.hevc").exists() else None
        qcamera_path = str(segment_dir / "qcamera.ts") if (segment_dir / "qcamera.ts").exists() else None

        # 插入 route（如果不存在）
        db.insert_route(route_id, dbc_file)

        # 檢查 segment 是否已存在
        existing_segments = db.get_segments_with_time(route_id)
        existing_segment = next((s for s in existing_segments if s['segment_number'] == segment_number), None)

        if existing_segment:
            logger.warning(f"Segment {segment_number} already exists for route {route_id}")
            logger.info(f"Deleting old segment {existing_segment['segment_id']}")
            db.delete_segments([existing_segment['segment_id']])

        # 插入 segment
        segment_id = db.insert_segment(
            route_id=route_id,
            segment_number=segment_number,
            start_time_ns=min_time_ns,
            end_time_ns=max_time_ns,
            wall_time_offset=wall_time_offset,
            ecamera_path=ecamera_path,
            fcamera_path=fcamera_path,
            qcamera_path=qcamera_path
        )

        if segment_id is None:
            logger.error("Failed to insert segment")
            return False

        logger.info(f"Created segment with ID: {segment_id}")

        # 第二次掃描：匯入資料
        logger.info("Importing data...")

        start_time = time.time()

        # 批次資料
        timeseries_batch = []
        can_batch = []
        log_batch = []

        batch_size = 5000
        event_count = 0
        timeseries_count = 0
        can_count = 0
        log_count = 0

        # 訊號定義追蹤（用於自動建立 signal definitions）
        signal_defs = set()

        with open(rlog_path, 'rb') as f:
            for event in log_capnp.Event.read_multiple(f):
                event_count += 1
                which = event.which()
                time_ns = event.logMonoTime

                # === carState ===
                if which == 'carState':
                    car_state = event.carState
                    signals = [
                        ('carState.vEgo', car_state.vEgo),
                        ('carState.aEgo', car_state.aEgo),
                        ('carState.steeringAngleDeg', car_state.steeringAngleDeg),
                        ('carState.steeringRateDeg', car_state.steeringRateDeg),
                        ('carState.gas', car_state.gas),
                        ('carState.brake', car_state.brake),
                        ('carState.brakePressed', float(car_state.brakePressed)),
                        ('carState.gasPressed', float(car_state.gasPressed)),
                        ('carState.leftBlinker', float(car_state.leftBlinker)),
                        ('carState.rightBlinker', float(car_state.rightBlinker)),
                        ('carState.vEgoRaw', car_state.vEgoRaw),
                        ('carState.standstill', float(car_state.standstill)),
                    ]

                    for signal_name, value in signals:
                        timeseries_batch.append((segment_id, time_ns, signal_name, value))
                        signal_defs.add(('carState', signal_name.split('.')[1]))
                        timeseries_count += 1

                # === controlsState ===
                elif which == 'controlsState':
                    controls = event.controlsState
                    signals = [
                        ('controlsState.aTarget', controls.aTarget),
                        ('controlsState.vCruise', controls.vCruise),
                        ('controlsState.vTargetLead', controls.vTargetLead),
                        ('controlsState.enabled', float(controls.enabled)),
                        ('controlsState.active', float(controls.active)),
                        ('controlsState.vPid', controls.vPid),
                        ('controlsState.upAccelCmd', controls.upAccelCmd),
                        ('controlsState.uiAccelCmd', controls.uiAccelCmd),
                    ]

                    for signal_name, value in signals:
                        timeseries_batch.append((segment_id, time_ns, signal_name, value))
                        signal_defs.add(('controlsState', signal_name.split('.')[1]))
                        timeseries_count += 1

                # === CAN messages ===
                elif which == 'can':
                    for can_msg in event.can:
                        can_batch.append((segment_id, time_ns, can_msg.address, bytes(can_msg.dat)))
                        can_count += 1

                # === logMessage ===
                elif which == 'logMessage':
                    log_batch.append((segment_id, time_ns, 'log', event.logMessage))
                    log_count += 1

                # === errorLogMessage ===
                elif which == 'errorLogMessage':
                    log_batch.append((segment_id, time_ns, 'error', event.errorLogMessage))
                    log_count += 1

                # 批次插入
                if len(timeseries_batch) >= batch_size:
                    db.insert_timeseries_batch(timeseries_batch)
                    timeseries_batch = []

                if len(can_batch) >= batch_size:
                    db.insert_can_batch(can_batch)
                    can_batch = []

                if len(log_batch) >= batch_size:
                    db.insert_log_messages_batch(log_batch)
                    log_batch = []

                # 顯示進度
                if event_count % 10000 == 0:
                    elapsed = time.time() - start_time
                    rate = event_count / elapsed if elapsed > 0 else 0
                    logger.info(f"Processed {event_count:,} events ({rate:.0f} events/sec)")

        # 插入剩餘資料
        if timeseries_batch:
            db.insert_timeseries_batch(timeseries_batch)
        if can_batch:
            db.insert_can_batch(can_batch)
        if log_batch:
            db.insert_log_messages_batch(log_batch)

        # 更新事件計數
        db.update_segment_event_count(segment_id, event_count)

        # 插入訊號定義
        for message_type, signal_name in signal_defs:
            db.insert_cereal_signal_definition(message_type, signal_name)

        elapsed_time = time.time() - start_time

        logger.info("=" * 80)
        logger.info("Import completed!")
        logger.info("=" * 80)
        logger.info(f"Total events:        {event_count:,}")
        logger.info(f"Timeseries records:  {timeseries_count:,}")
        logger.info(f"CAN messages:        {can_count:,}")
        logger.info(f"Log messages:        {log_count:,}")
        logger.info(f"Time taken:          {elapsed_time:.2f} sec")
        logger.info(f"Speed:               {event_count / elapsed_time:.0f} events/sec")
        logger.info(f"Segment ID:          {segment_id}")
        logger.info("=" * 80)

        # 顯示資料庫統計
        stats = db.get_database_stats()
        logger.info(f"Database size:       {stats.get('db_size_mb', 0):.2f} MB")
        logger.info(f"Total routes:        {stats.get('routes', 0)}")
        logger.info(f"Total segments:      {stats.get('segments', 0)}")

        return True

    except Exception as e:
        logger.error(f"Error during import: {e}", exc_info=True)
        return False

    finally:
        db.disconnect()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import rlog segment to SQLite")
    parser.add_argument('rlog', help='Path to rlog file')
    parser.add_argument('--db', help='SQLite database path', default=None)
    parser.add_argument('--dbc', help='DBC file name', default=None)

    args = parser.parse_args()

    success = import_segment(args.rlog, args.db, args.dbc)
    sys.exit(0 if success else 1)
