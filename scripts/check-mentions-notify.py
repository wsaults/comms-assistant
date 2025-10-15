#!/usr/bin/env python3
"""
Slack Mention Notifier with Monitoring
Checks for @mentions and shows macOS notifications
Reports to monitoring server for dashboard display
Uses existing Slack token from MCP config
"""

import argparse
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
CONFIG_FILE = HOME / ".mentions-assistant-config"
LOG_FILE = HOME / "Library/Logs/slack-mentions.log"
STATE_FILE = HOME / ".slack-mentions-state"

# Load configuration with priority: config file > env var > default
def _load_monitor_config():
    """Load monitor server URL and client ID from config file or env vars"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                config = json.load(f)
                server_url = config.get("monitor_server_url", os.getenv("MONITOR_SERVER_URL", "http://localhost:8000"))
                client_id = config.get("client_id", os.getenv("CLIENT_ID", socket.gethostname()))
                return server_url, client_id
    except Exception:
        pass
    # Fallback to env vars or defaults
    return os.getenv("MONITOR_SERVER_URL", "http://localhost:8000"), os.getenv("CLIENT_ID", socket.gethostname())

MONITOR_SERVER, CLIENT_ID = _load_monitor_config()


def log(message):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)

    # Also write to log file
    with open(LOG_FILE, "a") as f:
        f.write(log_line + "\n")


def load_slack_config():
    """Load Slack token and org name from MCP config"""
    try:
        with open(MCP_CONFIG) as f:
            config = json.load(f)
            slack_env = config["mcpServers"]["slack"]["env"]
            token = slack_env["SLACK_BOT_TOKEN"]
            org_name = slack_env.get("SLACK_ORG_NAME")  # Optional
            return token, org_name
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        log(f"ERROR: Could not load Slack config from {MCP_CONFIG}: {e}")
        return None, None


def load_monitored_channels():
    """Load list of channels to monitor from config file"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                config = json.load(f)
                monitor_channels = config.get("monitor_channels", {})
                # Return channels for "slack" workspace
                return monitor_channels.get("slack", [])
    except Exception as e:
        log(f"Warning: Could not load monitored channels: {e}")
    return []


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


def get_user_id(client, configured_org_name=None):
    """Get authenticated user's ID and workspace name"""
    try:
        auth = client.auth_test()
        user_id = auth['user_id']

        # Use configured org name if available
        if configured_org_name:
            workspace_name = configured_org_name
            log(f"Using configured workspace name: {workspace_name}")
        else:
            # Try multiple fields to get the workspace name
            workspace_name = auth.get('team', None)
            if not workspace_name or workspace_name == 'unknown':
                # Try team_id as fallback, or get from team.info
                team_id = auth.get('team_id')
                if team_id:
                    try:
                        team_info = client.team_info(team=team_id)
                        workspace_name = team_info.get('team', {}).get('name', 'Slack')
                    except:
                        workspace_name = 'Slack'
            log(f"Auto-detected workspace name: {workspace_name}")

        return user_id, workspace_name
    except SlackApiError as e:
        log(f"ERROR: Auth error: {e.response['error']}")
        return None, None

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


def fetch_channel_messages(client, channel_id, hours=1):
    """Fetch recent messages from a specific channel"""
    try:
        # Calculate oldest timestamp to fetch
        cutoff_time = datetime.now() - timedelta(hours=hours)
        oldest_timestamp = str(cutoff_time.timestamp())

        # Fetch channel history
        result = client.conversations_history(
            channel=channel_id,
            oldest=oldest_timestamp,
            limit=100  # Fetch up to 100 recent messages
        )

        messages = result.get("messages", [])

        # Get channel info to include channel name
        try:
            channel_info = client.conversations_info(channel=channel_id)
            channel_name = channel_info.get("channel", {}).get("name", channel_id)
        except:
            channel_name = channel_id

        # Add channel info to each message
        for msg in messages:
            msg["channel_name"] = channel_name
            msg["channel_id"] = channel_id

        return messages, channel_name

    except SlackApiError as e:
        log(f"ERROR: Failed to fetch channel {channel_id}: {e.response['error']}")
        return [], None


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


def report_to_server(mentions, all_mentions, workspace_name="Slack"):
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
                "client_id": CLIENT_ID,
                "workspace": workspace_name
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


def report_channel_messages(messages, workspace_name="Slack"):
    """Send channel messages to monitoring server"""
    if not httpx or not messages:
        return False

    try:
        client = httpx.Client(timeout=10.0)

        # Report each channel message
        for msg in messages:
            timestamp = datetime.fromtimestamp(float(msg.get("ts", "0")))
            raw_text = msg.get("text", "")
            clean_text = clean_slack_mentions(raw_text)

            # Get user info from message
            user = msg.get("user", "unknown")
            # Try to get username if available
            username = msg.get("username", user)

            mention_data = {
                "timestamp": timestamp.isoformat(),
                "channel": msg.get("channel_name", "unknown"),
                "user": username,
                "text": clean_text[:200],
                "is_question": "?" in clean_text,
                "responded": False,
                "client_id": CLIENT_ID,
                "workspace": workspace_name,
                "message_type": "channel"  # Tag as channel message vs mention
            }

            try:
                response = client.post(
                    f"{MONITOR_SERVER}/api/mention",
                    json=mention_data
                )
                if response.status_code == 200:
                    log(f"  ✓ Reported channel message to server")
            except Exception as e:
                log(f"  ✗ Failed to report channel message: {e}")

        client.close()
        return True

    except Exception as e:
        log(f"ERROR reporting channel messages: {e}")
        return False


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Check Slack mentions and notify')
    parser.add_argument('--hours', type=int, default=1,
                        help='Check mentions from last N hours (default: 1)')
    parser.add_argument('--notify', dest='notify', action='store_true', default=True,
                        help='Send results to monitoring server (default)')
    parser.add_argument('--no-notify', dest='notify', action='store_false',
                        help='Skip sending results to monitoring server')
    args = parser.parse_args()

    log("=" * 60)
    log("Slack Mention Check Started")

    # Load Slack config
    token, configured_org_name = load_slack_config()
    if not token:
        log("ERROR: No Slack token found")
        sys.exit(1)

    # Create Slack client
    client = WebClient(token=token)

    # Get authenticated user ID and workspace name
    user_id, workspace_name = get_user_id(client, configured_org_name)
    if not user_id:
        log("ERROR: Could not get user ID")
        sys.exit(1)

    log(f"Workspace: {workspace_name}")

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

    # Filter to recent
    recent_mentions = filter_recent_mentions(all_mentions, hours=args.hours)
    time_window = f"last {args.hours} hour{'s' if args.hours != 1 else ''}"
    log(f"Found {len(recent_mentions)} mentions in {time_window}")

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
        if args.notify:
            log("\nReporting to monitoring server...")
            report_to_server(recent_mentions, all_mentions, workspace_name)
    else:
        log("No new mentions")

        # Still report zero stats to server
        if args.notify and httpx:
            log("\nReporting to monitoring server...")
            report_to_server([], all_mentions, workspace_name)

    # Check monitored channels
    monitored_channels = load_monitored_channels()
    if monitored_channels:
        log(f"\n{'=' * 60}")
        log(f"Checking {len(monitored_channels)} monitored channel(s)...")
        log(f"{'=' * 60}")

        all_channel_messages = []
        for channel_id in monitored_channels:
            log(f"\nFetching messages from {channel_id}...")
            messages, channel_name = fetch_channel_messages(client, channel_id, hours=args.hours)

            if messages:
                log(f"Found {len(messages)} message(s) in #{channel_name}")
                all_channel_messages.extend(messages)
            else:
                log(f"No recent messages in #{channel_name if channel_name else channel_id}")

        # Show notification for channel messages
        if all_channel_messages:
            count = len(all_channel_messages)
            channel_count = len(set(m.get("channel_name") for m in all_channel_messages))
            show_notification(
                "Monitored Channels",
                f"{count} new message(s) in {channel_count} channel(s)",
                sound=False  # Less intrusive than mentions
            )

            # Report to monitoring server
            if args.notify:
                log(f"\nReporting {count} channel message(s) to monitoring server...")
                report_channel_messages(all_channel_messages, workspace_name)

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
