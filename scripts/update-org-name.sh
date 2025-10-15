#!/bin/bash

# Update Organization Name for Slack Workspace
# Allows changing the display name without re-running full setup

set -e

MCP_CONFIG="$HOME/.claude/mcp-servers.json"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      Update Slack Organization Name                         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if MCP config exists
if [ ! -f "$MCP_CONFIG" ]; then
    echo -e "${RED}✗ MCP config not found: $MCP_CONFIG${NC}"
    echo "  Run ./setup-client.sh first"
    exit 1
fi

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo -e "${RED}✗ jq is required but not installed${NC}"
    echo "  Install with: brew install jq"
    exit 1
fi

# List available Slack workspaces
echo "Available Slack workspaces:"
echo ""

WORKSPACES=$(jq -r '.mcpServers | keys[] | select(startswith("slack"))' "$MCP_CONFIG" 2>/dev/null)

if [ -z "$WORKSPACES" ]; then
    echo -e "${RED}✗ No Slack workspaces found in MCP config${NC}"
    exit 1
fi

# Display workspaces with current org names
i=1
declare -a WORKSPACE_ARRAY
while IFS= read -r workspace; do
    ORG_NAME=$(jq -r ".mcpServers.\"$workspace\".env.SLACK_ORG_NAME // \"(not set)\"" "$MCP_CONFIG")
    echo "  $i) $workspace - Current: $ORG_NAME"
    WORKSPACE_ARRAY[$i]=$workspace
    ((i++))
done <<< "$WORKSPACES"

echo ""
read -p "Select workspace to update (1-$((i-1))): " CHOICE

if [[ ! "$CHOICE" =~ ^[0-9]+$ ]] || [ "$CHOICE" -lt 1 ] || [ "$CHOICE" -ge "$i" ]; then
    echo -e "${RED}✗ Invalid choice${NC}"
    exit 1
fi

SELECTED_WORKSPACE="${WORKSPACE_ARRAY[$CHOICE]}"
echo -e "${GREEN}✓ Selected: $SELECTED_WORKSPACE${NC}"
echo ""

# Get current org name
CURRENT_ORG=$(jq -r ".mcpServers.\"$SELECTED_WORKSPACE\".env.SLACK_ORG_NAME // \"\"" "$MCP_CONFIG")

if [ -n "$CURRENT_ORG" ]; then
    echo "Current organization name: $CURRENT_ORG"
else
    echo "No organization name currently set"
fi
echo ""

# Prompt for new name
echo "Enter new organization name (or press Enter to auto-detect):"
echo -e "${YELLOW}Examples:${NC} 'ACME Corp', 'Startup Inc', 'My Team'"
echo ""
read -p "New organization name: " NEW_ORG_NAME

if [[ -z "$NEW_ORG_NAME" ]]; then
    # Auto-detect
    echo -e "${YELLOW}→ Auto-detecting organization name...${NC}"

    # Get token from config
    TOKEN=$(jq -r ".mcpServers.\"$SELECTED_WORKSPACE\".env.SLACK_BOT_TOKEN" "$MCP_CONFIG")

    NEW_ORG_NAME=$(python3 -c "
from slack_sdk import WebClient
import sys

try:
    client = WebClient('$TOKEN')
    response = client.team_info()
    print(response.get('team', {}).get('name', 'Slack'))
except Exception as e:
    print('Slack', file=sys.stderr)
    sys.exit(0)
" 2>&1)

    if [[ -n "$NEW_ORG_NAME" ]] && [[ "$NEW_ORG_NAME" != "Slack" ]]; then
        echo -e "${GREEN}✓ Found organization name: $NEW_ORG_NAME${NC}"
    else
        NEW_ORG_NAME="Slack"
        echo -e "${YELLOW}⚠ Could not auto-detect, using default: $NEW_ORG_NAME${NC}"
    fi
else
    echo -e "${GREEN}✓ Using organization name: $NEW_ORG_NAME${NC}"
fi

echo ""
echo -e "${YELLOW}→ Updating MCP config...${NC}"

# Create backup
cp "$MCP_CONFIG" "$MCP_CONFIG.backup"

# Update config
TEMP_CONFIG=$(mktemp)
jq ".mcpServers.\"$SELECTED_WORKSPACE\".env.SLACK_ORG_NAME = \"$NEW_ORG_NAME\"" "$MCP_CONFIG" > "$TEMP_CONFIG"

if [ $? -eq 0 ]; then
    mv "$TEMP_CONFIG" "$MCP_CONFIG"
    chmod 600 "$MCP_CONFIG"
    rm -f "$MCP_CONFIG.backup"
    echo -e "${GREEN}✓ Organization name updated${NC}"
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                  ✅ Update Complete!                         ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "The new name will be used on the next mention check."
else
    echo -e "${RED}✗ Failed to update config${NC}"
    mv "$MCP_CONFIG.backup" "$MCP_CONFIG"
    exit 1
fi
