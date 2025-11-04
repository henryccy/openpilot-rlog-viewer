# -*- coding: utf-8 -*-
"""
Import segment rlog data to PostgreSQL database
"""
import os
import sys
import time
import capnp
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import DatabaseManager
from src.utils.capnp_annotation_extractor import CapnpAnnotationExtractor

# Load Cap'n Proto schema
capnp_log = capnp.load('log.capnp')


def parse_segment_path(segment_path: str):
    """
    Parse segment directory name to extract route info

    Args:
        segment_path: e.g., "raw/00000001--31002a7aac--0"

    Returns:
        (route_id, dongle_id, timestamp, segment_num)
    """
    segment_name = os.path.basename(segment_path)
    parts = segment_name.split('--')

    if len(parts) != 3:
        raise ValueError(f"Invalid segment path format: {segment_name}")

    dongle_id = parts[0]
    timestamp_hex = parts[1]
    segment_num = int(parts[2])

    # Route ID = dongle_id--timestamp
    route_id = f"{dongle_id}--{timestamp_hex}"

    # Convert hex timestamp to int
    timestamp = int(timestamp_hex, 16)

    return route_id, dongle_id, timestamp, segment_num


def extract_numeric_value(obj, field_name: str):
    """
    Safely extract numeric value from capnp object

    Returns:
        float value or None
    """
    try:
        value = getattr(obj, field_name)
        if isinstance(value, (int, float)):
            return float(value)
        return None
    except:
        return None


def import_segment(segment_path: str, db: DatabaseManager):
    """
    Import a single segment to database

    Args:
        segment_path: Path to segment directory
        db: DatabaseManager instance
    """
    print("=" * 60)
    print(f"Importing segment: {segment_path}")
    print("=" * 60)

    # Parse segment info
    route_id, dongle_id, timestamp, segment_num = parse_segment_path(segment_path)
    print(f"Route ID: {route_id}")
    print(f"Dongle ID: {dongle_id}")
    print(f"Timestamp: {timestamp}")
    print(f"Segment: {segment_num}")

    # Check files
    rlog_path = os.path.join(segment_path, 'rlog')
    ecamera_path = os.path.join(segment_path, 'ecamera.hevc')
    fcamera_path = os.path.join(segment_path, 'fcamera.hevc')
    qcamera_path = os.path.join(segment_path, 'qcamera.ts')

    if not os.path.exists(rlog_path):
        raise FileNotFoundError(f"rlog not found: {rlog_path}")

    print(f"\nFiles:")
    print(f"  rlog: {os.path.exists(rlog_path)}")
    print(f"  ecamera: {os.path.exists(ecamera_path)}")
    print(f"  fcamera: {os.path.exists(fcamera_path)}")
    print(f"  qcamera: {os.path.exists(qcamera_path)}")

    # Read rlog file
    print(f"\nReading rlog file...")
    start_time = time.time()

    with open(rlog_path, 'rb') as f:
        data = f.read()

    read_time = time.time() - start_time
    print(f"  File size: {len(data):,} bytes")
    print(f"  Read time: {read_time:.2f}s")

    # Parse events
    print(f"\nParsing Cap'n Proto events...")
    parse_start = time.time()

    events = list(capnp_log.Event.read_multiple_bytes(data))

    parse_time = time.time() - parse_start
    print(f"  Total events: {len(events):,}")
    print(f"  Parse time: {parse_time:.2f}s")

    # Extract wall time offset from initData
    wall_time_offset = 0
    init_data_found = False

    for event in events[:100]:  # Check first 100 events
        try:
            if event.which() == 'initData':
                init_data = event.initData
                wall_time_ns = init_data.wallTimeNanos
                wall_time_offset = wall_time_ns - event.logMonoTime
                init_data_found = True
                print(f"\nFound initData:")
                print(f"  wallTimeNanos: {wall_time_ns}")
                print(f"  logMonoTime: {event.logMonoTime}")
                print(f"  wall_time_offset: {wall_time_offset} ns")

                # Convert to real datetime
                from datetime import datetime, timezone
                real_time_sec = wall_time_ns / 1e9
                dt = datetime.fromtimestamp(real_time_sec, tz=timezone.utc)
                print(f"  Real time (UTC): {dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                print(f"  Real time (Local): {dt.astimezone().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                break
        except:
            pass

    if not init_data_found:
        print(f"\n[WARNING] initData not found, wall_time_offset = 0")

    # Get time range
    start_time_ns = events[0].logMonoTime if events else 0
    end_time_ns = events[-1].logMonoTime if events else 0
    duration_sec = (end_time_ns - start_time_ns) / 1e9

    print(f"\nTime range (logMonoTime):")
    print(f"  Start: {start_time_ns} ns ({start_time_ns / 1e9:.3f}s)")
    print(f"  End: {end_time_ns} ns ({end_time_ns / 1e9:.3f}s)")
    print(f"  Duration: {duration_sec:.2f}s")

    # Check if segment already exists
    existing = db.cursor.execute("""
        SELECT segment_id FROM segments
        WHERE route_id = %s AND segment_num = %s
    """, (route_id, segment_num))
    existing_row = db.cursor.fetchone()

    if existing_row:
        print(f"\n[WARNING] Segment already exists (ID: {existing_row[0]})")
        print(f"[WARNING] Please delete existing data first or use ON CONFLICT UPDATE")
        response = input("\nDo you want to overwrite existing data? (yes/no): ")
        if response.lower() != 'yes':
            print("Import cancelled.")
            return

    # Insert route
    print(f"\nInserting route...")
    db.insert_route(route_id, dongle_id, timestamp)

    # Insert segment
    print(f"\nInserting segment...")
    segment_id = db.insert_segment(
        route_id=route_id,
        segment_num=segment_num,
        duration_sec=duration_sec,
        start_time_ns=start_time_ns,
        end_time_ns=end_time_ns,
        total_events=len(events),
        wall_time_offset=wall_time_offset,
        rlog_path=os.path.abspath(rlog_path),
        ecamera_path=os.path.abspath(ecamera_path) if os.path.exists(ecamera_path) else None,
        fcamera_path=os.path.abspath(fcamera_path) if os.path.exists(fcamera_path) else None,
        qcamera_path=os.path.abspath(qcamera_path) if os.path.exists(qcamera_path) else None
    )
    print(f"  Segment ID: {segment_id}")

    # Process events
    print(f"\nProcessing events...")
    import_start = time.time()

    timeseries_batch = []
    can_batch = []
    processed_count = 0
    signal_types = set()

    # Common carState fields to extract
    CAR_STATE_FIELDS = [
        'vEgo', 'aEgo', 'steeringAngleDeg', 'steeringTorque',
        'gas', 'gasPressed', 'brake', 'brakePressed',
        'leftBlinker', 'rightBlinker', 'gearShifter'
    ]

    # Common controlsState fields
    CONTROLS_STATE_FIELDS = [
        'enabled', 'active', 'longControlState', 'vCruise'
    ]

    for i, event in enumerate(events):
        try:
            msg_type = event.which()
            log_time_ns = event.logMonoTime

            # Extract carState data
            if msg_type == 'carState':
                car_state = event.carState
                for field in CAR_STATE_FIELDS:
                    value = extract_numeric_value(car_state, field)
                    if value is not None:
                        signal_name = f"carState.{field}"
                        timeseries_batch.append((log_time_ns, signal_name, value, None))
                        signal_types.add(signal_name)

            # Extract controlsState data
            elif msg_type == 'controlsState':
                controls_state = event.controlsState
                for field in CONTROLS_STATE_FIELDS:
                    value = extract_numeric_value(controls_state, field)
                    if value is not None:
                        signal_name = f"controlsState.{field}"
                        timeseries_batch.append((log_time_ns, signal_name, value, None))
                        signal_types.add(signal_name)

            # Extract CAN messages
            elif msg_type == 'can':
                can_msgs = event.can
                for can_msg in can_msgs:
                    can_batch.append((
                        log_time_ns,
                        can_msg.address,
                        bytes(can_msg.dat),
                        can_msg.src
                    ))

            processed_count += 1

            # Batch insert every 5000 events
            if len(timeseries_batch) >= 5000:
                db.insert_timeseries_batch(segment_id, timeseries_batch)
                timeseries_batch = []

            if len(can_batch) >= 5000:
                db.insert_can_batch(segment_id, can_batch)
                can_batch = []

            # Progress indicator
            if (i + 1) % 10000 == 0:
                print(f"  Processed: {i + 1:,} / {len(events):,} events...")

        except Exception as e:
            print(f"  [WARNING] Failed to process event {i}: {e}")
            continue

    # Insert remaining data
    if timeseries_batch:
        db.insert_timeseries_batch(segment_id, timeseries_batch)

    if can_batch:
        db.insert_can_batch(segment_id, can_batch)

    import_time = time.time() - import_start

    print(f"\nImport complete:")
    print(f"  Processed events: {processed_count:,}")
    print(f"  Unique signals: {len(signal_types)}")
    print(f"  Import time: {import_time:.2f}s")
    print(f"  Speed: {processed_count / import_time:.0f} events/s")

    # List extracted signals
    print(f"\nExtracted signals:")
    for signal_name in sorted(signal_types):
        print(f"  - {signal_name}")

    # Update signal catalog with descriptions
    print(f"\nUpdating signal catalog with descriptions...")
    extractor = CapnpAnnotationExtractor(capnp_directory=".")
    extractor.load_all_annotations()

    updated_count = 0
    for signal_name in signal_types:
        # Parse signal name (e.g., "carState.vEgo" -> type="carState", field="vEgo")
        parts = signal_name.split('.')
        if len(parts) == 2:
            signal_type, field_name = parts
            description = extractor.get_signal_description(signal_type, field_name, translate=True)

            if description:
                db.update_signal_catalog(
                    signal_name=signal_name,
                    signal_type=signal_type,
                    description=description
                )
                updated_count += 1

    print(f"  Updated {updated_count} signal descriptions")

    print("\n" + "=" * 60)
    print("Success!")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_segment.py <segment_path>")
        print("")
        print("Example:")
        print("  python tools/import_segment.py raw/00000001--31002a7aac--0")
        sys.exit(1)

    segment_path = sys.argv[1]

    if not os.path.exists(segment_path):
        print(f"[ERROR] Segment path not found: {segment_path}")
        sys.exit(1)

    # Connect to database
    print("Connecting to database...")
    db = DatabaseManager()
    db.connect()

    try:
        import_segment(segment_path, db)
    except Exception as e:
        print(f"\n[ERROR] Import failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.disconnect()
