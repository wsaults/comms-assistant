#!/usr/bin/env python3
"""
Test script to read Microsoft Teams IndexedDB database using dfindexeddb
"""

import os
import sys
from pathlib import Path

# Teams New (v2) database path
TEAMS_DB_PATH = Path.home() / "Library/Containers/com.microsoft.teams2/Data/Library/Application Support/Microsoft/MSTeams/EBWebView/WV2Profile_tfw/IndexedDB/https_teams.microsoft.com_0.indexeddb.leveldb"

def test_database_access():
    """Test if we can access the Teams database"""
    print("=" * 60)
    print("Teams Local Database Test")
    print("=" * 60)

    # Check if database exists
    if not TEAMS_DB_PATH.exists():
        print(f"❌ Database not found at: {TEAMS_DB_PATH}")
        return False

    print(f"✅ Database found at: {TEAMS_DB_PATH}")

    # Check if it's a directory
    if not TEAMS_DB_PATH.is_dir():
        print("❌ Database path is not a directory")
        return False

    # List database files
    db_files = list(TEAMS_DB_PATH.glob("*"))
    print(f"\n📁 Database contains {len(db_files)} files:")
    for f in sorted(db_files)[:10]:
        size = f.stat().st_size if f.is_file() else 0
        print(f"  - {f.name} ({size:,} bytes)")

    if len(db_files) > 10:
        print(f"  ... and {len(db_files) - 10} more files")

    # Try to import dfindexeddb
    print("\n🔧 Testing dfindexeddb import...")
    try:
        import dfindexeddb
        print("✅ dfindexeddb imported successfully")
        print(f"   Version: {getattr(dfindexeddb, '__version__', 'unknown')}")
    except ImportError as e:
        print(f"❌ Failed to import dfindexeddb: {e}")
        return False

    # Try to read the database
    print("\n📖 Attempting to read database...")
    try:
        from dfindexeddb import indexeddb

        # Read the LevelDB database
        db = indexeddb.IndexedDb(str(TEAMS_DB_PATH))

        print(f"✅ Database opened successfully")
        print(f"   Database names: {list(db.database_names)}")

        # Try to list some records
        record_count = 0
        for db_name in list(db.database_names)[:3]:  # Check first 3 databases
            print(f"\n📚 Database: {db_name}")
            try:
                for obj_store_name in db[db_name].object_store_names:
                    print(f"   Object Store: {obj_store_name}")
                    try:
                        store = db[db_name][obj_store_name]
                        records = list(store.records)[:5]  # First 5 records
                        print(f"      Records: {len(records)} (showing first 5)")
                        record_count += len(records)

                        for i, record in enumerate(records[:3]):
                            print(f"         Record {i+1}: {type(record).__name__}")
                    except Exception as e:
                        print(f"      Error reading records: {e}")
            except Exception as e:
                print(f"   Error accessing object stores: {e}")

        if record_count > 0:
            print(f"\n✅ Successfully read {record_count} records from database!")
        else:
            print("\n⚠️  No records found (database might be empty or encrypted)")

        return True

    except Exception as e:
        print(f"❌ Error reading database: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_database_access()
    sys.exit(0 if success else 1)
