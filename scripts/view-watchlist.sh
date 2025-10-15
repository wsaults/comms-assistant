#!/bin/bash
# View current channel monitoring watchlist
# Usage: ./view-watchlist.sh [workspace]

CONFIG_FILE="$HOME/.mentions-assistant-config"
WORKSPACE="${1:-all}"  # Default to showing all workspaces

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found at $CONFIG_FILE"
    echo "Run setup-client.sh first"
    exit 1
fi

echo "Channel Monitoring Watchlist"
echo "============================"
echo ""

# Use Python to parse and display the config
python3 - "$CONFIG_FILE" "$WORKSPACE" <<'EOF'
import json
import sys
from pathlib import Path

config_file = Path(sys.argv[1])
filter_workspace = sys.argv[2] if len(sys.argv) > 2 else "all"

# Load config
with open(config_file) as f:
    config = json.load(f)

monitor_channels = config.get("monitor_channels", {})

if not monitor_channels:
    print("No channels configured for monitoring.")
    print("")
    print("To add channels:")
    print("  ./add-channels-to-watchlist.sh C07FFABCDEF")
    sys.exit(0)

# Show total
total_channels = sum(len(channels) for channels in monitor_channels.values())
print(f"Total: {total_channels} channel(s) across {len(monitor_channels)} workspace(s)")
print("")

# Show per workspace
for workspace, channels in sorted(monitor_channels.items()):
    if filter_workspace != "all" and workspace != filter_workspace:
        continue

    print(f"📁 {workspace}")
    if channels:
        for channel in channels:
            print(f"   • {channel}")
    else:
        print("   (no channels)")
    print("")

if filter_workspace != "all" and filter_workspace not in monitor_channels:
    print(f"⚠ Workspace '{filter_workspace}' not found in config")
    print("")
    print("Available workspaces:")
    for ws in sorted(monitor_channels.keys()):
        print(f"  • {ws}")
EOF

echo ""
echo "To add channels:"
echo "  ./add-channels-to-watchlist.sh CHANNEL_ID [workspace]"
echo ""
echo "To test monitoring:"
echo "  python3 ~/scripts/check-mentions-notify.py --hours 24"
