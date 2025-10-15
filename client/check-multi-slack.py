#!/usr/bin/env python3
"""
Multi-Workspace Slack Mention Checker
Checks for @mentions across multiple Slack workspaces/organizations
Reports to monitoring server with unique client IDs per workspace
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
    httpx = None


# Configuration
HOME = Path.home()
MCP_CONFIG = HOME / ".claude" / "mcp-servers.json"
CONFIG_FILE = HOME / ".mentions-assistant-config"
LOG_FILE = HOME / "Library/Logs/slack-mentions-multi.log"

# Load configuration with priority: config file > env var > default
def _load_monitor_config():
    """Load monitor server URL from config file or env vars"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                config = json.load(f)
                server_url = config.get("monitor_server_url", os.getenv("MONITOR_SERVER_URL", "http://localhost:8000"))
                return server_url
    except Exception:
        pass
    # Fallback to env var or default
    return os.getenv("MONITOR_SERVER_URL", "http://localhost:8000")

MONITOR_SERVER = _load_monitor_config()
HOSTNAME = socket.gethostname()


def log(message):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)

    # Also write to log file
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(log_line + "\n")


def find_slack_workspaces():
    """Find all slack-* entries in MCP config"""
    try:
        with open(MCP_CONFIG) as f:
            config = json.load(f)

        workspaces = {}
        for key, server_config in config.get("mcpServers", {}).items():
            # Match entries starting with "slack" (but not "slack-sdk" or similar)
            if key.startswith("slack") and key != "slack-sdk":
                workspaces[key] = server_config

        return workspaces

    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        log(f"ERROR: Could not load MCP config from {MCP_CONFIG}: {e}")
        return {}


def load_monitored_channels(workspace_name):
    """Load list of channels to monitor for a specific workspace"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                config = json.load(f)
                monitor_channels = config.get("monitor_channels", {})
                # Return channels for the specified workspace
                return monitor_channels.get(workspace_name, [])
    except Exception as e:
        log(f"Warning: Could not load monitored channels: {e}")
    return []


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


def report_channel_messages(slack_client, messages, client_id, workspace_name):
    """Send channel messages to monitoring server

    Args:
        slack_client: Slack WebClient for username lookups
        messages: List of channel messages to report
        client_id: Client ID for tracking
        workspace_name: Name of the Slack workspace
    """
    if not httpx or not messages:
        return False

    try:
        http_client = httpx.Client(timeout=10.0)
        username_cache = {}  # Cache for user ID -> username lookups

        # Report each channel message
        for msg in messages:
            timestamp = datetime.fromtimestamp(float(msg.get("ts", "0")))
            raw_text = msg.get("text", "")
            clean_text = clean_slack_mentions(raw_text)

            # Get user ID and resolve to username
            user_id = msg.get("user", "unknown")
            username = get_username(slack_client, user_id, username_cache)

            mention_data = {
                "timestamp": timestamp.isoformat(),
                "channel": msg.get("channel_name", "unknown"),
                "user": username,
                "text": clean_text[:200],
                "is_question": "?" in clean_text,
                "responded": False,
                "client_id": client_id,
                "workspace": workspace_name,
                "message_type": "channel"  # Tag as channel message vs mention
            }

            try:
                response = http_client.post(
                    f"{MONITOR_SERVER}/api/mention",
                    json=mention_data
                )
                if response.status_code == 200:
                    log(f"  ✓ Reported channel message to server")
            except Exception as e:
                log(f"  ✗ Failed to report channel message: {e}")

        http_client.close()
        return True

    except Exception as e:
        log(f"ERROR reporting channel messages: {e}")
        return False


def get_last_check_time(workspace_name):
    """Get timestamp of last check for this workspace"""
    state_file = HOME / f".slack-mentions-state-{workspace_name}"
    if state_file.exists():
        try:
            with open(state_file) as f:
                return f.read().strip()
        except Exception:
            pass
    return None


def save_check_time(workspace_name):
    """Save current timestamp for this workspace"""
    state_file = HOME / f".slack-mentions-state-{workspace_name}"
    with open(state_file, "w") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def clean_slack_mentions(text):
    """Remove Slack user ID format from text"""
    import re
    text = re.sub(r'<@[A-Z0-9]+\|([^>]+)>', r'\1', text)
    text = re.sub(r'<@([A-Z0-9]+)>', r'@\1', text)
    return text


def get_username(client, user_id, cache=None):
    """Get username from user ID using Slack API

    Args:
        client: Slack WebClient
        user_id: User ID to lookup
        cache: Dictionary for caching user ID -> username mappings

    Returns:
        Username string (display name, real name, or @handle)
    """
    if cache is None:
        cache = {}

    # Check cache first
    if user_id in cache:
        return cache[user_id]

    # Handle special cases
    if not user_id or user_id == "unknown":
        return "unknown"

    try:
        # Call Slack users.info API
        response = client.users_info(user=user_id)
        user_info = response.get("user", {})
        profile = user_info.get("profile", {})

        # Priority: display_name > real_name > name
        username = (
            profile.get("display_name") or
            profile.get("real_name") or
            user_info.get("name") or
            user_id
        )

        # Cache the result
        cache[user_id] = username
        return username

    except SlackApiError as e:
        # Handle deleted users, deactivated accounts, etc.
        log(f"  Warning: Could not get username for {user_id}: {e.response.get('error', 'unknown error')}")
        cache[user_id] = user_id  # Cache the ID to avoid repeated failures
        return user_id
    except Exception as e:
        log(f"  Warning: Unexpected error getting username for {user_id}: {e}")
        return user_id


def check_workspace(workspace_name, workspace_config, hours=1):
    """Check one Slack workspace for mentions"""
    log(f"\n{'=' * 60}")
    log(f"Checking workspace: {workspace_name}")
    log(f"{'=' * 60}")

    # Extract credentials and optional org name
    try:
        token = workspace_config["env"]["SLACK_BOT_TOKEN"]
        team_id = workspace_config["env"].get("SLACK_TEAM_ID", "unknown")
        configured_org_name = workspace_config["env"].get("SLACK_ORG_NAME")
    except KeyError as e:
        log(f"ERROR: Missing credential in config: {e}")
        return []

    # Create unique client ID
    # Remove "slack-" prefix for cleaner names
    workspace_suffix = workspace_name.replace("slack-", "").replace("slack", "default")
    client_id = f"{HOSTNAME}-{workspace_suffix}"

    log(f"Client ID: {client_id}")
    log(f"Team ID: {team_id}")

    # Create Slack client
    client = WebClient(token=token)

    # Get authenticated user ID and workspace display name
    try:
        auth = client.auth_test()
        user_id = auth['user_id']

        # Use configured org name if available
        if configured_org_name:
            workspace_display_name = configured_org_name
            log(f"Using configured workspace name: {workspace_display_name}")
        else:
            # Try to get workspace name from auth response
            workspace_display_name = auth.get('team', None)
            if not workspace_display_name or workspace_display_name == 'unknown':
                # Try team_id as fallback
                team_id_from_auth = auth.get('team_id')
                if team_id_from_auth:
                    try:
                        team_info = client.team_info(team=team_id_from_auth)
                        workspace_display_name = team_info.get('team', {}).get('name', workspace_name)
                    except:
                        workspace_display_name = workspace_name
                else:
                    workspace_display_name = workspace_name
            log(f"Auto-detected workspace name: {workspace_display_name}")

        log(f"Authenticated as user {user_id} in {workspace_display_name}")
    except SlackApiError as e:
        log(f"ERROR: Auth error: {e.response['error']}")
        return []

    # Get last check time
    last_check = get_last_check_time(workspace_name)
    if last_check:
        log(f"Last check: {last_check}")

    # Search for mentions
    log("Searching for mentions...")
    try:
        result = client.search_messages(
            query=f"<@{user_id}>",
            sort="timestamp",
            sort_dir="desc",
            count=20
        )
    except SlackApiError as e:
        log(f"ERROR: Slack API error: {e.response['error']}")
        return []

    # Get messages
    all_mentions = result.get("messages", {}).get("matches", [])
    log(f"Found {len(all_mentions)} total mentions")

    # Filter to recent
    cutoff_time = datetime.now() - timedelta(hours=hours)
    cutoff_timestamp = cutoff_time.timestamp()

    recent_mentions = []
    for msg in all_mentions:
        msg_timestamp = float(msg.get("ts", "0"))
        if msg_timestamp > cutoff_timestamp:
            recent_mentions.append(msg)

    time_window = f"last {hours} hour{'s' if hours != 1 else ''}"
    log(f"Found {len(recent_mentions)} mentions in {time_window}")

    # Report to monitoring server
    if recent_mentions and httpx:
        log("Reporting to monitoring server...")
        try:
            http_client = httpx.Client(timeout=10.0)

            # Report each mention
            for msg in recent_mentions:
                timestamp = datetime.fromtimestamp(float(msg.get("ts", "0")))
                raw_text = msg.get("text", "")
                clean_text = clean_slack_mentions(raw_text)

                mention_data = {
                    "timestamp": timestamp.isoformat(),
                    "channel": msg.get("channel", {}).get("name", "unknown"),
                    "user": msg.get("username", "unknown"),
                    "text": clean_text[:200],
                    "is_question": "?" in clean_text,
                    "responded": False,
                    "client_id": client_id,
                    "workspace": workspace_display_name
                }

                try:
                    response = http_client.post(
                        f"{MONITOR_SERVER}/api/mention",
                        json=mention_data
                    )
                    if response.status_code == 200:
                        log(f"  ✓ Reported mention to server")
                except Exception as e:
                    log(f"  ✗ Failed to report mention: {e}")

            # Report stats
            stats_data = {
                "client_id": client_id,
                "unread_count": len(recent_mentions),
                "messages_last_hour": len(recent_mentions),
                "active_channels": list(set(
                    m.get("channel", {}).get("name", "unknown")
                    for m in recent_mentions
                )),
                "timestamp": datetime.now().isoformat()
            }

            try:
                response = http_client.post(
                    f"{MONITOR_SERVER}/api/stats",
                    json=stats_data
                )
                if response.status_code == 200:
                    log(f"  ✓ Reported stats to server")
            except Exception as e:
                log(f"  ✗ Failed to report stats: {e}")

            http_client.close()

        except Exception as e:
            log(f"ERROR reporting to server: {e}")
    elif httpx:
        # Still report zero stats
        log("Reporting zero stats to monitoring server...")
        try:
            http_client = httpx.Client(timeout=10.0)
            stats_data = {
                "client_id": client_id,
                "unread_count": 0,
                "messages_last_hour": 0,
                "active_channels": [],
                "timestamp": datetime.now().isoformat()
            }
            http_client.post(f"{MONITOR_SERVER}/api/stats", json=stats_data)
            http_client.close()
        except Exception as e:
            log(f"  ✗ Failed to report stats: {e}")

    # Check monitored channels for this workspace
    monitored_channels = load_monitored_channels(workspace_name)
    if monitored_channels:
        log(f"\nChecking {len(monitored_channels)} monitored channel(s)...")

        all_channel_messages = []
        for channel_id in monitored_channels:
            log(f"Fetching messages from {channel_id}...")
            messages, channel_name = fetch_channel_messages(client, channel_id, hours=hours)

            if messages:
                log(f"Found {len(messages)} message(s) in #{channel_name}")
                all_channel_messages.extend(messages)
            else:
                log(f"No recent messages in #{channel_name if channel_name else channel_id}")

        # Report channel messages to monitoring server
        if all_channel_messages and httpx:
            log(f"\nReporting {len(all_channel_messages)} channel message(s) to monitoring server...")
            report_channel_messages(client, all_channel_messages, client_id, workspace_display_name)

    # Save check time
    save_check_time(workspace_name)

    # Return mentions with workspace info for notification
    for mention in recent_mentions:
        mention['_workspace_name'] = workspace_display_name
        mention['_workspace_key'] = workspace_name

    return recent_mentions


def show_notification(title, message, sound=True):
    """Show macOS notification"""
    # Escape quotes in message
    message = message.replace('"', '\\"')
    script = f'display notification "{message}" with title "{title}"'
    if sound:
        script += ' sound name "default"'

    subprocess.run(["osascript", "-e", script], capture_output=True)


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Check mentions across multiple Slack workspaces')
    parser.add_argument('--hours', type=int, default=1,
                        help='Check mentions from last N hours (default: 1)')
    args = parser.parse_args()

    log("=" * 60)
    log("Multi-Workspace Slack Mention Check Started")
    log("=" * 60)

    # Find all Slack workspaces
    workspaces = find_slack_workspaces()

    if not workspaces:
        log("ERROR: No Slack workspaces found in MCP config")
        log("Add Slack workspace entries to ~/.claude/mcp-servers.json")
        log('Format: "slack-workspacename" with SLACK_BOT_TOKEN and SLACK_TEAM_ID')
        return 1

    log(f"Found {len(workspaces)} Slack workspace(s):")
    for name in workspaces.keys():
        log(f"  - {name}")

    # Check each workspace
    all_mentions = []
    workspace_summaries = []

    for workspace_name, workspace_config in workspaces.items():
        mentions = check_workspace(workspace_name, workspace_config, hours=args.hours)
        if mentions:
            all_mentions.extend(mentions)
            workspace_summaries.append((workspace_name, len(mentions)))

    # Show combined notification
    if all_mentions:
        total_count = len(all_mentions)

        # Build notification message
        if len(workspace_summaries) == 1:
            workspace_name, count = workspace_summaries[0]
            message = f"You have {count} new mention(s) in {workspace_name}!"
        else:
            message = f"You have {total_count} new mention(s) across {len(workspace_summaries)} workspaces!"

        show_notification("Slack Mentions", message, sound=True)

        # Log summary
        log(f"\n{'=' * 60}")
        log("Summary:")
        log(f"{'=' * 60}")
        log(f"Total new mentions: {total_count}")
        for workspace_name, count in workspace_summaries:
            log(f"  - {workspace_name}: {count} mention(s)")
    else:
        log("\nNo new mentions across all workspaces")

    log(f"{'=' * 60}")
    log("Multi-workspace check completed")
    log(f"{'=' * 60}")

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
