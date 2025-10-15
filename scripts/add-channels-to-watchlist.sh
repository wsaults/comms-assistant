#!/bin/bash
# Add Slack channels to monitoring watchlist
# Usage: ./add-channels-to-watchlist.sh C07FFABCDEF C123456789 [workspace]

set -e

CONFIG_FILE="$HOME/.mentions-assistant-config"
WORKSPACE="${3:-slack}"  # Default to "slack" workspace

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found at $CONFIG_FILE"
    echo "Run setup-client.sh first"
    exit 1
fi

# Check if at least one channel ID provided
if [ -z "$1" ]; then
    echo "Usage: $0 CHANNEL_ID [CHANNEL_ID2...] [workspace]"
    echo ""
    echo "Examples:"
    echo "  $0 C07FFABCDEF              # Add one channel to 'slack' workspace"
    echo "  $0 C07FF C123 slack-aligned # Add two channels to 'slack-aligned'"
    echo ""
    echo "To find channel IDs:"
    echo "  Right-click channel → View channel details → scroll to bottom"
    exit 1
fi

# Collect all channel IDs (all args except possibly the last one if it's a workspace name)
CHANNEL_IDS=()
for arg in "$@"; do
    # If it starts with 'slack', it's probably a workspace name
    if [[ "$arg" == slack* ]]; then
        WORKSPACE="$arg"
    else
        # Validate channel ID format (should start with C)
        if [[ ! "$arg" =~ ^C[A-Z0-9]+ ]]; then
            echo "WARNING: '$arg' doesn't look like a valid channel ID (should start with C)"
            echo "Continuing anyway..."
        fi
        CHANNEL_IDS+=("$arg")
    fi
done

if [ ${#CHANNEL_IDS[@]} -eq 0 ]; then
    echo "ERROR: No channel IDs provided"
    exit 1
fi

echo "Adding ${#CHANNEL_IDS[@]} channel(s) to workspace '$WORKSPACE'..."
echo ""

# Create Python script to update JSON
python3 - "$CONFIG_FILE" "$WORKSPACE" "${CHANNEL_IDS[@]}" <<'EOF'
import json
import sys
from pathlib import Path

config_file = Path(sys.argv[1])
workspace = sys.argv[2]
new_channels = sys.argv[3:]

# Load existing config
with open(config_file) as f:
    config = json.load(f)

# Ensure monitor_channels exists
if "monitor_channels" not in config:
    config["monitor_channels"] = {}

# Get existing channels for this workspace
existing = config["monitor_channels"].get(workspace, [])
print(f"Current channels in '{workspace}': {len(existing)}")

# Add new channels (avoid duplicates)
added_count = 0
for channel in new_channels:
    if channel not in existing:
        existing.append(channel)
        added_count += 1
        print(f"  ✓ Added {channel}")
    else:
        print(f"  - {channel} (already in list)")

# Update config
config["monitor_channels"][workspace] = existing

# Save back to file
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)

print(f"\n✓ Added {added_count} new channel(s)")
print(f"Total channels monitored in '{workspace}': {len(existing)}")
EOF

echo ""
echo "Configuration updated!"
echo ""
echo "Test with:"
echo "  python3 ~/scripts/check-mentions-notify.py --hours 24"
echo ""
echo "View config:"
echo "  cat $CONFIG_FILE"
