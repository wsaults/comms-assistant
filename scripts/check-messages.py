#!/usr/bin/env python3
"""
Unified Messages Checker
Checks mentions and monitored channels across all platforms (Slack, Teams)
Gracefully handles unavailable platforms
Supports optional server reporting via --notify flag

Usage:
    check-messages.py              # Check with server reporting (default)
    check-messages.py --no-notify  # Check without server reporting
    check-messages.py --hours 24   # Check last 24 hours
"""

import argparse
import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Configuration
HOME = Path.home()
CONFIG_FILE = HOME / ".mentions-assistant-config"
MCP_CONFIG = HOME / ".claude" / "mcp-servers.json"
SCRIPT_DIR = Path(__file__).parent
LOG_FILE = HOME / "Library/Logs/check-messages.log"


def log(message):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)

    # Also write to log file
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(log_line + "\n")


def load_config():
    """Load configuration file"""
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
            return config
    except FileNotFoundError:
        log(f"WARNING: Config file not found: {CONFIG_FILE}")
        log("Using default configuration (all available platforms)")
        return None
    except json.JSONDecodeError as e:
        log(f"ERROR: Invalid JSON in config file: {e}")
        return None


def is_slack_configured():
    """Check if Slack is configured in MCP"""
    try:
        with open(MCP_CONFIG) as f:
            config = json.load(f)
            for key in config.get("mcpServers", {}).keys():
                if key.startswith("slack") and key != "slack-sdk":
                    return True
        return False
    except Exception:
        return False


def is_teams_configured():
    """Check if Teams is configured in MCP"""
    try:
        with open(MCP_CONFIG) as f:
            config = json.load(f)
            return "teams-mcp" in config.get("mcpServers", {})
    except Exception:
        return False


def is_teams_local_available():
    """Check if Teams local database exists"""
    teams_db_path = HOME / "Library/Containers/com.microsoft.teams2/Data/Library/Application Support/Microsoft/MSTeams/EBWebView/WV2Profile_tfw/IndexedDB/https_teams.microsoft.com_0.indexeddb.leveldb"
    return teams_db_path.exists()


def count_slack_workspaces():
    """Count how many Slack workspaces are configured"""
    try:
        with open(MCP_CONFIG) as f:
            config = json.load(f)
            count = 0
            for key in config.get("mcpServers", {}).keys():
                if key.startswith("slack") and key != "slack-sdk":
                    count += 1
            return count
    except Exception:
        return 0


def check_slack(hours, notify):
    """Check Slack for mentions and channel messages"""
    log("\n" + "=" * 60)
    log("Checking Slack...")
    log("=" * 60)

    # Determine which checker to use
    workspace_count = count_slack_workspaces()

    if workspace_count == 0:
        log("⚠  Slack not configured - skipping")
        return None
    elif workspace_count == 1:
        log("→ Single workspace detected")
        slack_script = SCRIPT_DIR / "check-mentions-notify.py"
    else:
        log(f"→ Multiple workspaces detected ({workspace_count})")
        slack_script = SCRIPT_DIR / "check-multi-slack.py"

    if not slack_script.exists():
        log(f"⚠  Slack checker not found: {slack_script} - skipping")
        return None

    try:
        # Build command
        cmd = [sys.executable, str(slack_script), "--hours", str(hours)]
        if not notify:
            cmd.append("--no-notify")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )

        # Print output
        if result.stdout:
            print(result.stdout, end='')

        if result.returncode != 0:
            log(f"⚠  Slack checker exited with code {result.returncode}")
            if result.stderr:
                log(f"   Error: {result.stderr}")
            return False

        return True

    except subprocess.TimeoutExpired:
        log("⚠  Slack checker timed out")
        return False
    except Exception as e:
        log(f"⚠  Error running Slack checker: {e}")
        return False


def check_teams(hours, notify):
    """Check Teams for mentions"""
    log("\n" + "=" * 60)
    log("Checking Teams (MCP)...")
    log("=" * 60)

    teams_script = SCRIPT_DIR / "check-teams-mentions.py"

    if not teams_script.exists():
        log(f"⚠  Teams checker not found - skipping")
        return None

    try:
        # Build command
        cmd = [sys.executable, str(teams_script), "--hours", str(hours)]
        if not notify:
            cmd.append("--no-notify")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        # Print output
        if result.stdout:
            print(result.stdout, end='')

        if result.returncode != 0:
            log(f"⚠  Teams checker exited with code {result.returncode}")
            if result.stderr:
                log(f"   Error: {result.stderr}")
            return False

        return True

    except subprocess.TimeoutExpired:
        log("⚠  Teams checker timed out")
        return False
    except Exception as e:
        log(f"⚠  Error running Teams checker: {e}")
        return False


def check_teams_local(hours, notify):
    """Check Teams mentions from local database"""
    log("\n" + "=" * 60)
    log("Checking Teams (Local Database)...")
    log("=" * 60)

    teams_local_script = SCRIPT_DIR / "check-teams-local.py"

    if not teams_local_script.exists():
        log(f"⚠  Teams local checker not found - skipping")
        return None

    try:
        # Build command
        cmd = [sys.executable, str(teams_local_script), "--hours", str(hours)]
        # Note: check-teams-local doesn't report to server yet, so --notify is informational

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120  # Longer timeout for database parsing
        )

        # Print output
        if result.stdout:
            print(result.stdout, end='')

        if result.returncode != 0:
            log(f"⚠  Teams local checker exited with code {result.returncode}")
            if result.stderr:
                log(f"   Error: {result.stderr}")
            return False

        return True

    except subprocess.TimeoutExpired:
        log("⚠  Teams local checker timed out (database parsing can take 30-60 seconds)")
        return False
    except Exception as e:
        log(f"⚠  Error running Teams local checker: {e}")
        return False


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Unified messages checker - checks mentions and channels across all platforms',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Check with server reporting (default)
  %(prog)s --no-notify        # Check without server reporting
  %(prog)s --hours 24         # Check last 24 hours with reporting
  %(prog)s --hours 4 --no-notify   # Check last 4 hours without reporting
        """
    )
    parser.add_argument('--hours', type=int, default=1,
                        help='Check messages from last N hours (default: 1)')
    parser.add_argument('--notify', dest='notify', action='store_true', default=True,
                        help='Send results to monitoring server (default)')
    parser.add_argument('--no-notify', dest='notify', action='store_false',
                        help='Skip sending results to monitoring server')
    args = parser.parse_args()

    log("=" * 60)
    log("Unified Messages Checker Started")
    log("=" * 60)
    log(f"Time window: Last {args.hours} hour(s)")
    log(f"Server reporting: {'Enabled' if args.notify else 'Disabled'}")

    # Load configuration
    config = load_config()

    # Determine which platforms to check
    if config:
        configured_platforms = config.get("platforms", [])
        log(f"Configured platforms: {', '.join(configured_platforms) if configured_platforms else 'none'}")
    else:
        # Auto-detect available platforms
        configured_platforms = []
        if is_slack_configured():
            configured_platforms.append("slack")
        if is_teams_configured():
            configured_platforms.append("teams")
        if is_teams_local_available():
            configured_platforms.append("teams-local")

        if configured_platforms:
            log(f"Auto-detected platforms: {', '.join(configured_platforms)}")
        else:
            log("WARNING: No platforms configured or detected")
            log("Please run setup-client.sh to configure platforms")
            return 1

    # Check each platform
    results = {}

    for platform in configured_platforms:
        if platform == "slack":
            result = check_slack(args.hours, args.notify)
            if result is not None:
                results["slack"] = result
        elif platform == "teams":
            if is_teams_configured():
                result = check_teams(args.hours, args.notify)
                if result is not None:
                    results["teams"] = result
            else:
                log(f"\n⚠  Teams MCP not configured - skipping")
        elif platform == "teams-local":
            if is_teams_local_available():
                result = check_teams_local(args.hours, args.notify)
                if result is not None:
                    results["teams-local"] = result
            else:
                log(f"\n⚠  Teams local database not found - skipping")
        else:
            log(f"\n⚠  Unknown platform: {platform} - skipping")

    # Summary
    log("\n" + "=" * 60)
    log("Summary")
    log("=" * 60)

    if not results:
        log("No platforms were checked")
        log("Please configure platforms in ~/.mentions-assistant-config")
        return 1

    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    for platform, success in results.items():
        status = "✓" if success else "✗"
        log(f"{status} {platform}: {'Success' if success else 'Failed'}")

    log(f"\nChecked {total_count} platform(s), {success_count} succeeded")
    log("=" * 60)

    # Return 0 if at least one platform succeeded
    return 0 if success_count > 0 else 1


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
