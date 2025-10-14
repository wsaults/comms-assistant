#!/usr/bin/env python3
"""
Unified Mentions Checker
Checks all configured platforms (Slack, Teams, etc.) for mentions
Reads configuration from ~/.mentions-assistant-config
"""

import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Configuration
HOME = Path.home()
CONFIG_FILE = HOME / ".mentions-assistant-config"
SCRIPT_DIR = Path(__file__).parent
LOG_FILE = HOME / "Library/Logs/mentions-assistant.log"


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
        log(f"ERROR: Config file not found: {CONFIG_FILE}")
        log("Run setup-client.sh to create configuration")
        return None
    except json.JSONDecodeError as e:
        log(f"ERROR: Invalid JSON in config file: {e}")
        return None


def check_slack():
    """Check Slack for mentions"""
    log("\n" + "=" * 60)
    log("Checking Slack...")
    log("=" * 60)

    slack_script = SCRIPT_DIR / "check-mentions-notify.py"

    if not slack_script.exists():
        log(f"ERROR: Slack checker not found: {slack_script}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(slack_script)],
            capture_output=True,
            text=True,
            timeout=60
        )

        # Print output
        if result.stdout:
            print(result.stdout, end='')

        if result.returncode != 0:
            log(f"ERROR: Slack checker failed with code {result.returncode}")
            if result.stderr:
                log(f"STDERR: {result.stderr}")
            return False

        return True

    except subprocess.TimeoutExpired:
        log("ERROR: Slack checker timed out")
        return False
    except Exception as e:
        log(f"ERROR running Slack checker: {e}")
        return False


def check_teams():
    """Check Teams for mentions"""
    log("\n" + "=" * 60)
    log("Checking Teams...")
    log("=" * 60)

    teams_script = SCRIPT_DIR / "check-teams-mentions.py"

    if not teams_script.exists():
        log(f"ERROR: Teams checker not found: {teams_script}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(teams_script)],
            capture_output=True,
            text=True,
            timeout=60
        )

        # Print output
        if result.stdout:
            print(result.stdout, end='')

        if result.returncode != 0:
            log(f"ERROR: Teams checker failed with code {result.returncode}")
            if result.stderr:
                log(f"STDERR: {result.stderr}")
            return False

        return True

    except subprocess.TimeoutExpired:
        log("ERROR: Teams checker timed out")
        return False
    except Exception as e:
        log(f"ERROR running Teams checker: {e}")
        return False


def main():
    log("=" * 60)
    log("Unified Mentions Checker Started")
    log("=" * 60)

    # Load configuration
    config = load_config()
    if not config:
        return 1

    platforms = config.get("platforms", [])
    if not platforms:
        log("ERROR: No platforms configured")
        log("Edit ~/.mentions-assistant-config and add platforms")
        return 1

    log(f"Configured platforms: {', '.join(platforms)}")

    # Check each platform
    results = {}

    for platform in platforms:
        if platform == "slack":
            results["slack"] = check_slack()
        elif platform == "teams":
            results["teams"] = check_teams()
        else:
            log(f"WARNING: Unknown platform: {platform}")
            results[platform] = False

    # Summary
    log("\n" + "=" * 60)
    log("Summary")
    log("=" * 60)

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
