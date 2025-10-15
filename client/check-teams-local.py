#!/usr/bin/env python3
"""
Check Microsoft Teams mentions by reading local IndexedDB directly
No API or organizational access required!
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
import re
from html.parser import HTMLParser

# Teams IndexedDB path for Teams v2
TEAMS_DB_PATH = Path.home() / "Library/Containers/com.microsoft.teams2/Data/Library/Application Support/Microsoft/MSTeams/EBWebView/WV2Profile_tfw/IndexedDB/https_teams.microsoft.com_0.indexeddb.leveldb"

# dfindexeddb binary path
DFINDEXEDDB_BIN = Path.home() / "Library/Python/3.9/bin/dfindexeddb"


class HTMLTextExtractor(HTMLParser):
    """Extract plain text from HTML, preserving mention markers"""
    def __init__(self):
        super().__init__()
        self.text = []
        self.in_mention = False

    def handle_starttag(self, tag, attrs):
        if tag == 'span':
            # Check if this is a mention span
            attrs_dict = dict(attrs)
            if attrs_dict.get('itemtype') == 'http://schema.skype.com/Mention':
                self.in_mention = True
                self.text.append('@')

    def handle_endtag(self, tag):
        if tag == 'span' and self.in_mention:
            self.in_mention = False

    def handle_data(self, data):
        self.text.append(data.strip())

    def get_text(self):
        return ' '.join(self.text).strip()


def parse_teams_database():
    """Parse the Teams IndexedDB database and return mentions with messages"""

    if not TEAMS_DB_PATH.exists():
        print(f"❌ Teams database not found at: {TEAMS_DB_PATH}", file=sys.stderr)
        return []

    if not DFINDEXEDDB_BIN.exists():
        print(f"❌ dfindexeddb not found. Install: pip3 install dfindexeddb", file=sys.stderr)
        return []

    # Parse database to JSON
    print("📖 Parsing Teams database (this may take 30-60 seconds)...", file=sys.stderr)
    try:
        result = subprocess.run(
            [str(DFINDEXEDDB_BIN), 'db', '-s', str(TEAMS_DB_PATH), '--format', 'chromium', '-o', 'jsonl'],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            print(f"❌ Error parsing database: {result.stderr}", file=sys.stderr)
            return []

        db_output = result.stdout

    except subprocess.TimeoutExpired:
        print("❌ Database parsing timed out", file=sys.stderr)
        return []
    except Exception as e:
        print(f"❌ Error running dfindexeddb: {e}", file=sys.stderr)
        return []

    # Parse the output
    mentions = []
    messages_by_reply_chain = {}

    print("🔍 Extracting mentions and messages...", file=sys.stderr)

    for line in db_output.split('\n'):
        if not line.strip():
            continue

        try:
            record = json.loads(line)
            key_prefix = record.get('key', {}).get('key_prefix', {})
            db_id = key_prefix.get('database_id')
            value = record.get('value', {}).get('value', {})

            if not isinstance(value, dict):
                continue

            # Database 25: Mentions/Activities
            if db_id == 25:
                if value.get('activityType') == 'mention':
                    mentions.append({
                        'activityId': value.get('activityId'),
                        'threadId': value.get('sourceThreadId'),
                        'messageId': value.get('sourceMessageId'),
                        'timestamp': value.get('timestamp'),
                        'isRead': value.get('isRead'),
                        'subtype': value.get('activitySubtype')
                    })

            # Database 15: Reply chains with messages
            elif db_id == 15:
                conv_id = value.get('conversationId')
                reply_chain_id = value.get('replyChainId')
                msg_map = value.get('messageMap', {})

                if conv_id and reply_chain_id and msg_map:
                    key = f"{conv_id}:{reply_chain_id}"
                    messages_by_reply_chain[key] = {
                        'conversationId': conv_id,
                        'replyChainId': reply_chain_id,
                        'messages': msg_map
                    }

        except json.JSONDecodeError:
            continue
        except Exception as e:
            # Skip malformed records
            continue

    print(f"✅ Found {len(mentions)} mentions", file=sys.stderr)
    print(f"✅ Found {len(messages_by_reply_chain)} message threads", file=sys.stderr)

    # Match mentions to messages
    matched_mentions = []

    for mention in mentions:
        thread_id = mention['threadId']
        msg_id = str(mention['messageId'])

        # The message ID is actually the reply chain ID
        key = f"{thread_id}:{msg_id}"

        if key in messages_by_reply_chain:
            thread_data = messages_by_reply_chain[key]
            msg_map = thread_data['messages']

            # Get the root message (parent message)
            for msg_key, msg_data in msg_map.items():
                if not isinstance(msg_data, dict):
                    continue

                # Find the message that matches the timestamp
                if str(msg_data.get('id')) == msg_id:
                    # Extract text from HTML content
                    content_html = msg_data.get('content', '')
                    extractor = HTMLTextExtractor()
                    try:
                        extractor.feed(content_html)
                        content_text = extractor.get_text()
                    except:
                        content_text = re.sub(r'<[^>]+>', '', content_html)

                    matched_mentions.append({
                        'timestamp': mention['timestamp'],
                        'timestamp_dt': datetime.fromtimestamp(mention['timestamp'] / 1000),
                        'threadId': thread_id,
                        'messageId': msg_id,
                        'from': msg_data.get('imDisplayName', 'Unknown'),
                        'from_id': msg_data.get('creator', ''),
                        'content_html': content_html,
                        'content_text': content_text,
                        'is_read': mention['isRead'],
                        'mention_type': mention['subtype']
                    })
                    break

    return matched_mentions


def filter_recent_mentions(mentions, hours=1):
    """Filter mentions from the last N hours"""
    cutoff = datetime.now() - timedelta(hours=hours)

    recent = [m for m in mentions if m['timestamp_dt'] >= cutoff]
    return recent


def main():
    """Main function to check for recent Teams mentions"""

    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Check Teams mentions from local database')
    parser.add_argument('--hours', type=float, default=1.0, help='Check mentions from last N hours')
    parser.add_argument('--all', action='store_true', help='Show all mentions (ignore time filter)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()

    # Parse database
    all_mentions = parse_teams_database()

    if not all_mentions:
        print("No mentions found in database", file=sys.stderr)
        return 0

    # Filter by time
    if args.all:
        mentions = all_mentions
    else:
        mentions = filter_recent_mentions(all_mentions, hours=args.hours)

    # Output results
    if args.json:
        output = [{
            'timestamp': m['timestamp_dt'].isoformat(),
            'channel': m['threadId'],
            'user': m['from'],
            'text': m['content_text'],
            'is_read': m['is_read'],
            'mention_type': m['mention_type']
        } for m in mentions]
        print(json.dumps(output, indent=2))
    else:
        print(f"\n📬 Found {len(mentions)} mention(s) in the last {args.hours} hour(s):\n")

        for i, mention in enumerate(mentions, 1):
            status = "✓ Read" if mention['is_read'] else "⚠ Unread"
            print(f"{i}. [{status}] {mention['timestamp_dt'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   From: {mention['from']}")
            print(f"   Type: {mention['mention_type']}")
            print(f"   Thread: {mention['threadId']}")
            print(f"   Message: {mention['content_text'][:200]}")
            print()

    return len(mentions)


if __name__ == "__main__":
    try:
        count = main()
        sys.exit(0 if count >= 0 else 1)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
