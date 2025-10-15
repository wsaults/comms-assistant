#!/bin/bash

# Add Slack Workspace Script
# Interactive helper to add additional Slack workspaces to MCP config

set -e

MCP_CONFIG="$HOME/.claude/mcp-servers.json"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      Add Additional Slack Workspace                         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if MCP config exists
if [ ! -f "$MCP_CONFIG" ]; then
    echo -e "${RED}ERROR: MCP config not found at $MCP_CONFIG${NC}"
    echo "Run setup-client.sh first to create initial configuration"
    exit 1
fi

# Check for required tools
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: python3 is required${NC}"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}Installing jq...${NC}"
    if command -v brew &> /dev/null; then
        brew install jq
    else
        echo -e "${RED}ERROR: jq is required. Install with: brew install jq${NC}"
        exit 1
    fi
fi

# Check for slack-sdk
if ! python3 -c "import slack_sdk" 2>/dev/null; then
    echo -e "${YELLOW}Installing slack-sdk...${NC}"
    pip3 install --break-system-packages slack-sdk 2>/dev/null || pip3 install slack-sdk
fi

# List existing Slack workspaces
echo -e "${BLUE}Current Slack workspaces in MCP config:${NC}"
echo ""
jq -r '.mcpServers | to_entries[] | select(.key | startswith("slack")) | "  - \(.key)"' "$MCP_CONFIG"
echo ""

# Get workspace name
echo -e "${YELLOW}Workspace Name${NC}"
echo "Enter a short name for this workspace (e.g., 'companyA', 'personal', 'clientX')"
echo "This will be used as: slack-<name>"
echo ""
read -p "Workspace name: " WORKSPACE_NAME

# Validate workspace name
if [[ -z "$WORKSPACE_NAME" ]]; then
    echo -e "${RED}ERROR: Workspace name cannot be empty${NC}"
    exit 1
fi

# Remove "slack-" prefix if user included it
WORKSPACE_NAME="${WORKSPACE_NAME#slack-}"

# Sanitize workspace name (only alphanumeric and hyphens)
WORKSPACE_NAME=$(echo "$WORKSPACE_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g')

WORKSPACE_KEY="slack-${WORKSPACE_NAME}"

echo ""
echo -e "${GREEN}Will create workspace: $WORKSPACE_KEY${NC}"
echo ""

# Check if workspace already exists
if jq -e ".mcpServers.\"$WORKSPACE_KEY\"" "$MCP_CONFIG" >/dev/null 2>&1; then
    echo -e "${RED}ERROR: Workspace '$WORKSPACE_KEY' already exists in config${NC}"
    exit 1
fi

# Get Slack user token
echo -e "${YELLOW}Slack User Token${NC}"
echo "You need a Slack User Token (starts with xoxp-)"
echo "Get one at: https://api.slack.com/apps"
echo ""
echo "Required scopes: channels:history, channels:read, chat:write, users:read, search:read"
echo ""
read -p "Enter Slack User Token (xoxp-...): " SLACK_TOKEN

if [[ -z "$SLACK_TOKEN" ]]; then
    echo -e "${RED}ERROR: Token is required${NC}"
    exit 1
fi

if [[ ! "$SLACK_TOKEN" =~ ^xoxp- ]]; then
    echo -e "${RED}ERROR: Token should start with 'xoxp-'${NC}"
    exit 1
fi

# Auto-detect Team ID
echo ""
echo -e "${YELLOW}→ Auto-detecting Team ID...${NC}"

TEAM_ID=$(python3 <<EOF
from slack_sdk import WebClient
import sys

try:
    client = WebClient('$SLACK_TOKEN')
    response = client.auth_test()
    team_id = response.get('team_id')
    team_name = response.get('team', 'Unknown')
    print(f"TEAM_ID:{team_id}")
    print(f"TEAM_NAME:{team_name}", file=sys.stderr)
except Exception as e:
    print(f"ERROR:{str(e)}", file=sys.stderr)
    sys.exit(1)
EOF
)

if [[ $? -ne 0 ]]; then
    echo -e "${RED}✗ Failed to validate token${NC}"
    echo "Make sure the token is valid and has required scopes"
    exit 1
fi

# Extract team ID from output
TEAM_ID=$(echo "$TEAM_ID" | grep "^TEAM_ID:" | cut -d: -f2)

if [[ -z "$TEAM_ID" ]] || [[ ! "$TEAM_ID" =~ ^T ]]; then
    echo -e "${RED}✗ Failed to auto-detect Team ID${NC}"
    read -p "Enter Team ID manually (T...): " TEAM_ID

    if [[ ! "$TEAM_ID" =~ ^T ]]; then
        echo -e "${RED}ERROR: Team ID should start with 'T'${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Detected Team ID: $TEAM_ID${NC}"
fi

# Get organization/workspace name
echo ""
echo -e "${YELLOW}→ Organization Name${NC}"
echo "Enter a display name for this organization (or press Enter to auto-detect):"
echo -e "${YELLOW}Examples:${NC} 'ACME Corp', 'Startup Inc', 'My Team'"
echo ""
read -p "Organization name (optional): " ORG_NAME

if [[ -z "$ORG_NAME" ]]; then
    # Try to auto-detect org name
    echo -e "${YELLOW}→ Auto-detecting organization name...${NC}"

    ORG_NAME=$(python3 -c "
from slack_sdk import WebClient
import sys

try:
    client = WebClient('$SLACK_TOKEN')
    response = client.team_info()
    print(response.get('team', {}).get('name', 'Slack'))
except Exception as e:
    print('Slack', file=sys.stderr)
    sys.exit(0)
" 2>&1)

    if [[ -n "$ORG_NAME" ]] && [[ "$ORG_NAME" != "Slack" ]]; then
        echo -e "${GREEN}✓ Found organization name: $ORG_NAME${NC}"
    else
        ORG_NAME="Slack"
        echo -e "${YELLOW}⚠ Could not auto-detect name, using default: $ORG_NAME${NC}"
    fi
else
    echo -e "${GREEN}✓ Using organization name: $ORG_NAME${NC}"
fi

# Update MCP config
echo ""
echo -e "${YELLOW}→ Updating MCP configuration...${NC}"

# Create backup
cp "$MCP_CONFIG" "$MCP_CONFIG.backup"
echo -e "${GREEN}✓ Created backup: $MCP_CONFIG.backup${NC}"

# Add new workspace using jq
jq ".mcpServers.\"$WORKSPACE_KEY\" = {
  \"command\": \"npx\",
  \"args\": [\"-y\", \"@modelcontextprotocol/server-slack\"],
  \"env\": {
    \"SLACK_BOT_TOKEN\": \"$SLACK_TOKEN\",
    \"SLACK_TEAM_ID\": \"$TEAM_ID\",
    \"SLACK_ORG_NAME\": \"$ORG_NAME\"
  }
}" "$MCP_CONFIG" > "$MCP_CONFIG.tmp"

mv "$MCP_CONFIG.tmp" "$MCP_CONFIG"

echo -e "${GREEN}✓ Added workspace to MCP config${NC}"

# Test the configuration
echo ""
echo -e "${YELLOW}→ Testing configuration...${NC}"

TEST_RESULT=$(python3 <<EOF
from slack_sdk import WebClient
import sys

try:
    client = WebClient('$SLACK_TOKEN')
    response = client.auth_test()
    user = response.get('user', 'unknown')
    team = response.get('team', 'Unknown')
    print(f"SUCCESS:{user}@{team}")
except Exception as e:
    print(f"ERROR:{str(e)}")
    sys.exit(1)
EOF
)

if [[ $? -eq 0 ]]; then
    USER_INFO=$(echo "$TEST_RESULT" | grep "^SUCCESS:" | cut -d: -f2)
    echo -e "${GREEN}✓ Configuration validated: $USER_INFO${NC}"
else
    echo -e "${RED}✗ Configuration test failed${NC}"
    echo "Restoring backup..."
    mv "$MCP_CONFIG.backup" "$MCP_CONFIG"
    exit 1
fi

# Success
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         ✅ Slack Workspace Added Successfully!               ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Workspace: $WORKSPACE_KEY${NC}"
echo -e "${GREEN}Team ID: $TEAM_ID${NC}"
echo ""
echo -e "${YELLOW}The mentions checker will now automatically check this workspace.${NC}"
echo ""
echo -e "${YELLOW}To test:${NC}"
echo "  python3 ~/scripts/check-multi-slack.py"
echo ""
echo -e "${YELLOW}To remove this workspace:${NC}"
echo "  Edit $MCP_CONFIG and remove the '$WORKSPACE_KEY' entry"
echo ""
