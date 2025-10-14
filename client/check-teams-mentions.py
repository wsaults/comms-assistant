#!/usr/bin/env python3
"""
Teams Mention Notifier with Monitoring
Checks for @mentions in Microsoft Teams and shows macOS notifications
Reports to monitoring server for dashboard display
Uses Teams MCP server via Model Context Protocol
"""

import json
import os
import subprocess
import sys
import socket
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("ERROR: mcp not installed")
    print("Install with: pip3 install mcp")
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
LOG_FILE = HOME / "Library/Logs/teams-mentions.log"
STATE_FILE = HOME / ".teams-mentions-state"
MONITOR_SERVER = os.getenv("MONITOR_SERVER_URL", "http://localhost:8000")
CLIENT_ID = os.getenv("CLIENT_ID", socket.gethostname())


def log(message):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)

    # Also write to log file
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(log_line + "\n")


def load_teams_mcp_config():
    """Load Teams MCP config"""
    try:
        with open(MCP_CONFIG) as f:
            config = json.load(f)
            teams_config = config["mcpServers"]["teams-mcp"]
            return teams_config
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        log(f"ERROR: Could not load Teams MCP config from {MCP_CONFIG}: {e}")
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


def filter_recent_mentions(mentions, hours=1):
    """Filter mentions from last N hours"""
    cutoff_time = datetime.now() - timedelta(hours=hours)

    recent = []
    for msg in mentions:
        try:
            # Parse ISO timestamp from Teams
            timestamp_str = msg.get("createdDateTime", "")
            if timestamp_str:
                # Handle both with and without 'Z' suffix
                timestamp_str = timestamp_str.replace('Z', '+00:00')
                msg_time = datetime.fromisoformat(timestamp_str).replace(tzinfo=None)

                if msg_time > cutoff_time:
                    recent.append(msg)
        except Exception as e:
            log(f"  Warning: Could not parse timestamp: {e}")
            continue

    return recent


def format_mention(msg):
    """Format mention for display"""
    sender = msg.get("from", {}).get("user", {}).get("displayName", "Unknown")
    text = msg.get("body", {}).get("content", "")[:100]  # First 100 chars

    # Extract channel/chat name
    channel = "Teams"
    if "channelIdentity" in msg:
        channel = msg["channelIdentity"].get("displayName", "Teams")

    return f"@{sender} in {channel}: {text}"


def report_to_server(mentions):
    """Send mention data to monitoring server"""
    if not httpx:
        return False

    try:
        client = httpx.Client(timeout=10.0)

        # Report each recent mention
        for msg in mentions:
            # Parse timestamp
            timestamp_str = msg.get("createdDateTime", "")
            timestamp_str = timestamp_str.replace('Z', '+00:00')
            timestamp = datetime.fromisoformat(timestamp_str)

            # Extract sender
            sender = msg.get("from", {}).get("user", {}).get("displayName", "unknown")

            # Extract text (Teams uses HTML, strip tags for now)
            body = msg.get("body", {})
            text = body.get("content", "")

            # Simple HTML tag removal
            import re
            text = re.sub(r'<[^>]+>', '', text)[:200]

            # Extract channel name
            channel = "teams-dm"
            if "channelIdentity" in msg:
                channel = msg["channelIdentity"].get("displayName", "teams")

            mention_data = {
                "timestamp": timestamp.isoformat(),
                "channel": channel,
                "user": sender,
                "text": text,
                "is_question": "?" in text,
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
        channel_names = []
        for msg in mentions:
            if "channelIdentity" in msg:
                channel_names.append(msg["channelIdentity"].get("displayName", "teams"))

        stats_data = {
            "client_id": CLIENT_ID,
            "unread_count": len(mentions),
            "messages_last_hour": len(mentions),
            "active_channels": list(set(channel_names)) if channel_names else ["teams"],
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


async def check_teams_mentions():
    """Check Teams for mentions using MCP"""
    # Load Teams MCP config
    teams_config = load_teams_mcp_config()
    if not teams_config:
        log("ERROR: No Teams MCP config found")
        return []

    # Extract command and args
    command = teams_config.get("command", "npx")
    args = teams_config.get("args", ["-y", "@floriscornel/teams-mcp@latest"])

    log(f"Connecting to Teams MCP: {command} {' '.join(args)}")

    # Create server parameters
    server_params = StdioServerParameters(
        command=command,
        args=args,
        env=None
    )

    mentions = []

    try:
        # Connect to MCP server
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the session
                await session.initialize()
                log("✓ Connected to Teams MCP")

                # List available tools (for debugging)
                tools_result = await session.list_tools()
                tool_names = [tool.name for tool in tools_result.tools]
                log(f"Available tools: {', '.join(tool_names)}")

                # Call get_my_mentions tool
                if "get_my_mentions" in tool_names:
                    log("Calling get_my_mentions...")
                    result = await session.call_tool("get_my_mentions", arguments={})

                    # Parse the result
                    if hasattr(result, 'content') and result.content:
                        for content_item in result.content:
                            if hasattr(content_item, 'text'):
                                # The result is JSON text
                                mentions_data = json.loads(content_item.text)
                                if isinstance(mentions_data, list):
                                    mentions = mentions_data
                                elif isinstance(mentions_data, dict) and "value" in mentions_data:
                                    mentions = mentions_data["value"]

                                log(f"Found {len(mentions)} total mentions")
                else:
                    log("ERROR: get_my_mentions tool not available")

    except Exception as e:
        log(f"ERROR connecting to Teams MCP: {e}")
        import traceback
        log(traceback.format_exc())

    return mentions


async def main_async():
    log("=" * 60)
    log("Teams Mention Check Started")

    # Get last check time
    last_check = get_last_check_time()
    if last_check:
        log(f"Last check: {last_check}")

    # Check Teams for mentions
    all_mentions = await check_teams_mentions()

    if not all_mentions:
        log("No mentions found or error occurred")
        save_check_time()
        log("Check completed")
        log("=" * 60)
        return 0

    # Filter to recent (last hour)
    recent_mentions = filter_recent_mentions(all_mentions, hours=1)
    log(f"Found {len(recent_mentions)} mentions in last hour")

    # Show notification if new mentions
    if recent_mentions:
        count = len(recent_mentions)
        show_notification(
            "Teams Mentions",
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
        report_to_server(recent_mentions)
    else:
        log("No new mentions")

        # Still report zero stats to server
        if httpx:
            log("\nReporting to monitoring server...")
            report_to_server([])

    # Save check time
    save_check_time()

    log("Check completed")
    log("=" * 60)

    return 0


def main():
    """Entry point"""
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        log("\nInterrupted by user")
        return 1
    except Exception as e:
        log(f"ERROR: Unexpected error: {e}")
        import traceback
        log(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
