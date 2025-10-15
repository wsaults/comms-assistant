#!/bin/bash
# Remove Slack channels from monitoring watchlist
# Usage: ./remove-channels-from-watchlist.sh C07FFABCDEF [workspace]

set -e

CONFIG_FILE="$HOME/.mentions-assistant-config"
WORKSPACE="${2:-slack}"  # Default to "slack" workspace

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found at $CONFIG_FILE"
    exit 1
fi

# Check if channel ID provided
if [ -z "$1" ]; then
    echo "Usage: $0 CHANNEL_ID [workspace]"
    echo ""
    echo "Examples:"
    echo "  $0 C07FFABCDEF              # Remove from 'slack' workspace"
    echo "  $0 C123456 slack-aligned    # Remove from 'slack-aligned'"
    echo ""
    echo "View current watchlist:"
    echo "  ./view-watchlist.sh"
    exit 1
fi

CHANNEL_ID="$1"

echo "Removing channel '$CHANNEL_ID' from workspace '$WORKSPACE'..."
echo ""

# Create Python script to update JSON
python3 - "$CONFIG_FILE" "$WORKSPACE" "$CHANNEL_ID" <<'EOF'
import json
import sys
from pathlib import Path

config_file = Path(sys.argv[1])
workspace = sys.argv[2]
channel_to_remove = sys.argv[3]

# Load existing config
with open(config_file) as f:
    config = json.load(f)

# Check if monitor_channels exists
if "monitor_channels" not in config:
    print(f"ERROR: No monitoring configured")
    sys.exit(1)

# Get existing channels for this workspace
existing = config["monitor_channels"].get(workspace, [])

if not existing:
    print(f"ERROR: Workspace '{workspace}' has no monitored channels")
    sys.exit(1)

# Remove channel
if channel_to_remove in existing:
    existing.remove(channel_to_remove)
    print(f"✓ Removed {channel_to_remove}")

    # Update config
    config["monitor_channels"][workspace] = existing

    # Save back to file
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"\nRemaining channels in '{workspace}': {len(existing)}")
else:
    print(f"ERROR: Channel {channel_to_remove} not found in '{workspace}' watchlist")
    print(f"\nCurrent channels:")
    for ch in existing:
        print(f"  • {ch}")
    sys.exit(1)
EOF

echo ""
echo "View updated watchlist:"
echo "  ./view-watchlist.sh"
