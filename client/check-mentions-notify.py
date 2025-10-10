#!/usr/bin/env python3
"""
Slack Mention Notifier with Monitoring
Checks for @mentions and shows macOS notifications
Reports to monitoring server for dashboard display
Uses existing Slack token from MCP config
"""

import json
import os
import subprocess
import sys
import socket
from datetime import datetime, timedelta
from pathlib import Path

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError:
    print("ERROR: slack_sdk not installed")
    print("Install with: pip3 install slack-sdk")
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("WARNING: httpx not installed - monitoring disabled")
    print("Install with: pip3 install httpx")
    httpx = None


# Configuration
HOME = Path.home()
MCP_CONFIG = HOME / ".claude" / "mcp-servers.json"
LOG_FILE = HOME / "Library/Logs/slack-mentions.log"
STATE_FILE = HOME / ".slack-mentions-state"
MONITOR_SERVER = os.getenv("MONITOR_SERVER_URL", "http://localhost:8000")
CLIENT_ID = os.getenv("CLIENT_ID", socket.gethostname())


def log(message):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)

    # Also write to log file
    with open(LOG_FILE, "a") as f:
        f.write(log_line + "\n")


def load_slack_token():
    """Load Slack token from MCP config"""
    try:
        with open(MCP_CONFIG) as f:
            config = json.load(f)
            token = config["mcpServers"]["slack"]["env"]["SLACK_BOT_TOKEN"]
            return token
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        log(f"ERROR: Could not load Slack token from {MCP_CONFIG}: {e}")
        return None


def get_last_check_time():
    """Get timestamp of last check"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return f.read().strip()
        except Exception:
            pass
    return None


def save_check_time():
    """Save current timestamp"""
    with open(STATE_FILE, "w") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def show_notification(title, message, sound=True):
    """Show macOS notification"""
    script = f'display notification "{message}" with title "{title}"'
    if sound:
        script += ' sound name "default"'

    subprocess.run(["osascript", "-e", script], capture_output=True)


def get_user_id(client):
    """Get authenticated user's ID"""
    try:
        auth = client.auth_test()
        return auth['user_id']
    except SlackApiError as e:
        log(f"ERROR: Auth error: {e.response['error']}")
        return None

def search_mentions(client, user_id):
    """Search for mentions using Slack API"""
    try:
        # Search for messages mentioning the authenticated user
        # Slack mentions appear as <@USER_ID> in message text
        result = client.search_messages(
            query=f"<@{user_id}>",  # Messages mentioning me
            sort="timestamp",
            sort_dir="desc",
            count=20  # Check last 20 mentions
        )

        return result

    except SlackApiError as e:
        log(f"ERROR: Slack API error: {e.response['error']}")
        return None


def filter_recent_mentions(messages, hours=1):
    """Filter mentions from last N hours"""
    cutoff_time = datetime.now() - timedelta(hours=hours)
    cutoff_timestamp = cutoff_time.timestamp()

    recent = []
    for msg in messages:
        # Slack timestamps are strings like "1234567890.123456"
        msg_timestamp = float(msg.get("ts", "0"))
        if msg_timestamp > cutoff_timestamp:
            recent.append(msg)

    return recent


def format_mention(msg):
    """Format mention for display"""
    user = msg.get("username", "Unknown")
    text = msg.get("text", "")[:100]  # First 100 chars
    channel = msg.get("channel", {}).get("name", "unknown")

    return f"@{user} in #{channel}: {text}"


def clean_slack_mentions(text):
    """Remove Slack user ID format from text"""
    import re
    # Replace <@USER_ID|username> with username
    # Replace <@USER_ID> with @USER_ID
    text = re.sub(r'<@[A-Z0-9]+\|([^>]+)>', r'\1', text)
    text = re.sub(r'<@([A-Z0-9]+)>', r'@\1', text)
    return text


def report_to_server(mentions, all_mentions):
    """Send mention data to monitoring server"""
    if not httpx:
        return False

    try:
        client = httpx.Client(timeout=10.0)

        # Report each recent mention
        for msg in mentions:
            timestamp = datetime.fromtimestamp(float(msg.get("ts", "0")))
            raw_text = msg.get("text", "")
            clean_text = clean_slack_mentions(raw_text)

            mention_data = {
                "timestamp": timestamp.isoformat(),
                "channel": msg.get("channel", {}).get("name", "unknown"),
                "user": msg.get("username", "unknown"),
                "text": clean_text[:200],
                "is_question": "?" in clean_text,
                "responded": False,  # Assume new mentions are unresponded
                "client_id": CLIENT_ID
            }

            try:
                response = client.post(
                    f"{MONITOR_SERVER}/api/mention",
                    json=mention_data
                )
                if response.status_code == 200:
                    log(f"  ✓ Reported to monitoring server")
            except Exception as e:
                log(f"  ✗ Failed to report mention: {e}")

        # Report stats
        stats_data = {
            "client_id": CLIENT_ID,
            "unread_count": len(mentions),
            "messages_last_hour": len(mentions),
            "active_channels": list(set(
                m.get("channel", {}).get("name", "unknown")
                for m in mentions
            )),
            "timestamp": datetime.now().isoformat()
        }

        try:
            response = client.post(
                f"{MONITOR_SERVER}/api/stats",
                json=stats_data
            )
            if response.status_code == 200:
                log(f"  ✓ Reported stats to server")
                return True
        except Exception as e:
            log(f"  ✗ Failed to report stats: {e}")

        client.close()
        return False

    except Exception as e:
        log(f"ERROR reporting to server: {e}")
        return False


def main():
    log("=" * 60)
    log("Slack Mention Check Started")

    # Load Slack token
    token = load_slack_token()
    if not token:
        log("ERROR: No Slack token found")
        sys.exit(1)

    # Create Slack client
    client = WebClient(token=token)

    # Get authenticated user ID
    user_id = get_user_id(client)
    if not user_id:
        log("ERROR: Could not get user ID")
        sys.exit(1)

    # Get last check time
    last_check = get_last_check_time()
    if last_check:
        log(f"Last check: {last_check}")

    # Search for mentions
    log("Searching for mentions...")
    result = search_mentions(client, user_id)

    if result is None:
        log("ERROR: Failed to search mentions")
        sys.exit(1)

    # Get messages
    all_mentions = result.get("messages", {}).get("matches", [])
    log(f"Found {len(all_mentions)} total mentions")

    # Filter to recent (last hour)
    recent_mentions = filter_recent_mentions(all_mentions, hours=1)
    log(f"Found {len(recent_mentions)} mentions in last hour")

    # Show notification if new mentions
    if recent_mentions:
        count = len(recent_mentions)
        show_notification(
            "Slack Mentions",
            f"You have {count} new mention(s)!",
            sound=True
        )

        # Log details
        log("\nNew mentions:")
        for mention in recent_mentions[:5]:  # Show first 5
            log(f"  - {format_mention(mention)}")

        if len(recent_mentions) > 5:
            log(f"  ... and {len(recent_mentions) - 5} more")

        # Report to monitoring server
        log("\nReporting to monitoring server...")
        report_to_server(recent_mentions, all_mentions)
    else:
        log("No new mentions")

        # Still report zero stats to server
        if httpx:
            log("\nReporting to monitoring server...")
            report_to_server([], all_mentions)

    # Save check time
    save_check_time()

    log("Check completed")
    log("=" * 60)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        log(f"ERROR: Unexpected error: {e}")
        import traceback
        log(traceback.format_exc())
        sys.exit(1)
