# -*- coding: utf-8 -*-
"""
Clear segment data from database
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import DatabaseManager

if len(sys.argv) < 2:
    print("Usage: python clear_segment.py <route_id>")
    print("")
    print("Example:")
    print("  python tools/clear_segment.py 00000001--31002a7aac")
    sys.exit(1)

route_id = sys.argv[1]

print("=" * 60)
print(f"Clearing data for route: {route_id}")
print("=" * 60)

db = DatabaseManager()
db.connect()

try:
    # Check if route exists
    route = db.get_route(route_id)
    if not route:
        print(f"\n[ERROR] Route not found: {route_id}")
        sys.exit(1)

    # Get segments
    segments = db.get_segments(route_id)
    print(f"\nFound {len(segments)} segments for this route")

    if len(segments) == 0:
        print("\nNothing to delete.")
        sys.exit(0)

    for seg in segments:
        print(f"  Segment {seg['segment_num']}: {seg['total_events']} events")

    # Confirm deletion
    print("\n" + "=" * 60)
    print("WARNING: This will delete:")
    print(f"  - {len(segments)} segments")
    print(f"  - All timeseries data")
    print(f"  - All CAN messages")
    print(f"  - The route record")
    print("=" * 60)

    response = input("\nAre you sure? Type 'DELETE' to confirm: ")

    if response != 'DELETE':
        print("\nCancelled.")
        sys.exit(0)

    # Delete route (CASCADE will delete segments and related data)
    print("\nDeleting route and all related data...")
    db.cursor.execute("DELETE FROM routes WHERE route_id = %s", (route_id,))
    db.conn.commit()

    print("\n[OK] Deleted successfully!")

finally:
    db.disconnect()
