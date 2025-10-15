#!/usr/bin/env python3
"""
Analyze Microsoft Teams v2 IndexedDB structure to find message data
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

DUMP_FILE = "teams-db-dump.jsonl"

def analyze_database_structure():
    """Analyze the structure of the Teams database"""

    # Track database structure
    databases = defaultdict(lambda: defaultdict(set))
    database_records = defaultdict(lambda: defaultdict(list))

    # Track interesting records
    potential_messages = []

    print("=" * 80)
    print("ANALYZING TEAMS DATABASE STRUCTURE")
    print("=" * 80)

    with open(DUMP_FILE, 'r') as f:
        for line_num, line in enumerate(f):
            try:
                record = json.loads(line)

                # Extract structure info
                key_prefix = record.get('key', {}).get('key_prefix', {})
                db_id = key_prefix.get('database_id')
                obj_store_id = key_prefix.get('object_store_id')

                # Get the value
                value = record.get('value', {}).get('value', {})

                if db_id and obj_store_id:
                    # Track which object stores exist in each database
                    databases[db_id]['object_stores'].add(obj_store_id)

                    # Sample a few records from each object store
                    if len(database_records[db_id][obj_store_id]) < 3:
                        database_records[db_id][obj_store_id].append({
                            'line': line_num,
                            'key': record.get('key', {}).get('encoded_user_key', {}).get('value'),
                            'value_type': type(value).__name__,
                            'value_keys': list(value.keys()) if isinstance(value, dict) else None,
                            'value_sample': str(value)[:200] if value else None
                        })

                    # Look for potential message indicators
                    if isinstance(value, dict):
                        value_str = json.dumps(value).lower()

                        # Check for message-like content
                        if any(keyword in value_str for keyword in [
                            'messageid', 'conversationid', 'chatmessage',
                            'mention', 'notification', 'content',
                            'displayname', 'sendername', 'timestamp'
                        ]):
                            potential_messages.append({
                                'line': line_num,
                                'db_id': db_id,
                                'obj_store_id': obj_store_id,
                                'key': record.get('key', {}).get('encoded_user_key', {}).get('value'),
                                'value': value
                            })

            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"Error on line {line_num}: {e}")
                continue

    # Print database structure
    print(f"\n📊 DATABASE STRUCTURE")
    print(f"Found {len(databases)} databases\n")

    for db_id in sorted(databases.keys()):
        obj_stores = sorted(databases[db_id]['object_stores'])
        print(f"Database {db_id}:")
        print(f"  Object Stores: {obj_stores}")

        # Show sample records from each object store
        for obj_store_id in obj_stores[:5]:  # Show first 5 object stores
            samples = database_records[db_id][obj_store_id]
            if samples:
                print(f"  \n  Object Store {obj_store_id} samples:")
                for sample in samples[:2]:  # Show 2 samples per store
                    print(f"    Line {sample['line']}: key={sample['key']}")
                    if sample['value_keys']:
                        print(f"      Fields: {sample['value_keys'][:10]}")
                    if sample['value_sample']:
                        print(f"      Sample: {sample['value_sample'][:150]}")
        print()

    # Print potential messages
    print(f"\n🔍 POTENTIAL MESSAGE RECORDS")
    print(f"Found {len(potential_messages)} potential message records\n")

    if potential_messages:
        for i, msg in enumerate(potential_messages[:10]):  # Show first 10
            print(f"Record {i+1} (line {msg['line']}):")
            print(f"  Database: {msg['db_id']}, Object Store: {msg['obj_store_id']}")
            print(f"  Key: {msg['key']}")
            print(f"  Fields: {list(msg['value'].keys())[:15]}")
            print(f"  Value: {json.dumps(msg['value'], indent=2)[:500]}")
            print()

    return databases, potential_messages

def search_for_specific_patterns():
    """Search for specific patterns that might indicate messages"""

    print("=" * 80)
    print("SEARCHING FOR SPECIFIC PATTERNS")
    print("=" * 80)

    patterns = {
        'timestamps': [],
        'user_data': [],
        'conversation_data': [],
        'large_text': []
    }

    with open(DUMP_FILE, 'r') as f:
        for line_num, line in enumerate(f):
            try:
                record = json.loads(line)
                value = record.get('value', {}).get('value', {})

                if not isinstance(value, dict):
                    continue

                value_str = json.dumps(value)

                # Look for timestamps (messages usually have timestamps)
                if any(k in value for k in ['timestamp', 'createdDateTime', 'lastModifiedDateTime', 'composedTime']):
                    patterns['timestamps'].append({
                        'line': line_num,
                        'keys': list(value.keys()),
                        'sample': value_str[:300]
                    })

                # Look for user/sender information
                if any(k in value for k in ['from', 'sender', 'displayName', 'userPrincipalName']):
                    patterns['user_data'].append({
                        'line': line_num,
                        'keys': list(value.keys()),
                        'sample': value_str[:300]
                    })

                # Look for conversation/thread info
                if any(k in value for k in ['conversationId', 'threadId', 'chatId']):
                    patterns['conversation_data'].append({
                        'line': line_num,
                        'keys': list(value.keys()),
                        'sample': value_str[:300]
                    })

                # Look for large text blocks (might be message content)
                for key, val in value.items():
                    if isinstance(val, str) and len(val) > 100 and not val.startswith('http'):
                        patterns['large_text'].append({
                            'line': line_num,
                            'field': key,
                            'length': len(val),
                            'sample': val[:200]
                        })

            except:
                continue

    # Print findings
    for pattern_name, matches in patterns.items():
        print(f"\n{pattern_name.upper()}: {len(matches)} matches")
        for match in matches[:5]:  # Show first 5
            print(f"  Line {match['line']}: {match}")
            print()

if __name__ == "__main__":
    if not Path(DUMP_FILE).exists():
        print(f"Error: {DUMP_FILE} not found")
        print("Run dfindexeddb first to create the dump")
        sys.exit(1)

    databases, potential_messages = analyze_database_structure()
    search_for_specific_patterns()

    print("=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print("1. Examine blob storage directory")
    print("2. Try closing Teams and re-reading database")
    print("3. Check for encrypted/binary data")
    print("4. Look at WebStorage databases")
