#!/bin/bash

# Slack Monitor Client Setup
# Copies client files and configures this machine to report to the dashboard server

set -e

# Parse arguments
RESET_MODE=false
if [ "$1" = "--reset" ] || [ "$1" = "-r" ]; then
    RESET_MODE=true
    shift
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Cleanup function for --reset mode
cleanup_client_setup() {
    echo ""
    echo -e "${YELLOW}Starting cleanup...${NC}"
    echo ""

    # Stop and unload LaunchD agent
    PLIST_FILE="$HOME/Library/LaunchAgents/com.user.mentions-assistant.plist"
    if launchctl list | grep -q "com.user.mentions-assistant"; then
        echo -e "${YELLOW}→ Stopping LaunchD agent...${NC}"
        launchctl stop com.user.mentions-assistant 2>/dev/null || true
        launchctl unload "$PLIST_FILE" 2>/dev/null || true
        echo -e "${GREEN}✓ LaunchD agent stopped and unloaded${NC}"
    fi

    # Remove LaunchD plist
    if [ -f "$PLIST_FILE" ]; then
        echo -e "${YELLOW}→ Removing LaunchD plist...${NC}"
        rm -f "$PLIST_FILE"
        echo -e "${GREEN}✓ LaunchD plist removed${NC}"
    fi

    # Remove old scripts directory (from previous installation pattern)
    OLD_INSTALL_DIR="$HOME/scripts"
    if [ -d "$OLD_INSTALL_DIR" ]; then
        echo -e "${YELLOW}→ Removing old scripts directory...${NC}"
        rm -rf "$OLD_INSTALL_DIR"
        echo -e "${GREEN}✓ Old scripts directory removed${NC}"
    fi

    # Remove configuration file
    CONFIG_FILE="$HOME/.mentions-assistant-config"
    if [ -f "$CONFIG_FILE" ]; then
        echo -e "${YELLOW}→ Removing configuration file...${NC}"
        rm -f "$CONFIG_FILE"
        echo -e "${GREEN}✓ Configuration file removed${NC}"
    fi

    # Remove state files
    echo -e "${YELLOW}→ Removing state files...${NC}"
    rm -f "$HOME/.slack-mentions-state" 2>/dev/null || true
    rm -f "$HOME/.slack-mentions-state-"* 2>/dev/null || true
    rm -f "$HOME/.teams-mentions-state" 2>/dev/null || true
    echo -e "${GREEN}✓ State files removed${NC}"

    # Remove MCP entries (carefully - only slack and teams)
    MCP_CONFIG="$HOME/.claude/mcp-servers.json"
    if [ -f "$MCP_CONFIG" ]; then
        echo -e "${YELLOW}→ Removing Slack/Teams entries from MCP config...${NC}"

        # Check if jq is available
        if command -v jq &> /dev/null; then
            # Create backup
            cp "$MCP_CONFIG" "$MCP_CONFIG.backup"

            # Remove all slack-* entries and teams-mcp
            TEMP_CONFIG=$(mktemp)
            jq 'if .mcpServers then
                    .mcpServers |= with_entries(select(.key | test("^slack") | not)) |
                    .mcpServers |= with_entries(select(.key != "teams-mcp"))
                else . end' "$MCP_CONFIG" > "$TEMP_CONFIG"

            # Check if mcpServers is now empty
            if jq -e '.mcpServers | length == 0' "$TEMP_CONFIG" >/dev/null 2>&1; then
                # If empty, remove the file entirely
                rm -f "$MCP_CONFIG"
                rm -f "$MCP_CONFIG.backup"
                echo -e "${GREEN}✓ MCP config removed (was empty)${NC}"
            else
                # Otherwise, replace with cleaned version
                mv "$TEMP_CONFIG" "$MCP_CONFIG"
                chmod 600 "$MCP_CONFIG"
                rm -f "$MCP_CONFIG.backup"
                echo -e "${GREEN}✓ Slack/Teams entries removed from MCP config${NC}"
            fi
        else
            echo -e "${YELLOW}⚠ jq not available - skipping MCP config cleanup${NC}"
            echo "  Manually remove slack-* and teams-mcp from ~/.claude/mcp-servers.json"
        fi
    fi

    # Ask about log files
    echo ""
    echo -e "${YELLOW}Log files:${NC}"
    echo "  ~/Library/Logs/mentions-assistant.log"
    echo "  ~/Library/Logs/mentions-assistant-error.log"
    echo "  ~/Library/Logs/slack-mentions*.log"
    echo "  ~/Library/Logs/teams-mentions.log"
    echo ""
    read -p "Remove log files? (y/n) " -n 1 -r
    echo
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}→ Removing log files...${NC}"
        rm -f "$HOME/Library/Logs/mentions-assistant.log" 2>/dev/null || true
        rm -f "$HOME/Library/Logs/mentions-assistant-error.log" 2>/dev/null || true
        rm -f "$HOME/Library/Logs/slack-mentions.log" 2>/dev/null || true
        rm -f "$HOME/Library/Logs/slack-mentions-multi.log" 2>/dev/null || true
        rm -f "$HOME/Library/Logs/teams-mentions.log" 2>/dev/null || true
        echo -e "${GREEN}✓ Log files removed${NC}"
    else
        echo -e "${YELLOW}⚠ Log files preserved${NC}"
    fi

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║            ✅ Cleanup Complete!                              ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Show warning and get confirmation for reset
show_reset_warning() {
    echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                    ⚠️  WARNING ⚠️                            ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}This will remove ALL mentions assistant configuration:${NC}"
    echo ""
    echo "  📁 Scripts directory: ~/scripts/"
    echo "  ⚙️  LaunchD automation"
    echo "  📝 Configuration file: ~/.mentions-assistant-config"
    echo "  💾 All state files"
    echo "  🔗 Slack/Teams entries in MCP config"
    echo "  📊 Log files (optional)"
    echo ""
    echo -e "${RED}This action cannot be undone!${NC}"
    echo ""
    read -p "Type 'yes' to confirm reset: " -r
    echo

    if [ "$REPLY" != "yes" ]; then
        echo -e "${YELLOW}Reset cancelled.${NC}"
        exit 0
    fi
}

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      Mentions Assistant - Client Setup                      ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "This will set up this machine to report mentions to"
echo "your centralized monitoring dashboard."
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is required but not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"

# Check Node.js (needed for Teams MCP)
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✓ Node.js $NODE_VERSION found${NC}"
    HAS_NODE=true
else
    echo -e "${YELLOW}⚠ Node.js not found (required for Teams support)${NC}"
    HAS_NODE=false
fi

# Check jq (needed for JSON manipulation)
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}⚠ jq not found - installing...${NC}"
    if command -v brew &> /dev/null; then
        # Disable auto-update and install jq
        echo "  This may take a moment..."
        HOMEBREW_NO_AUTO_UPDATE=1 brew install jq || {
            echo -e "${RED}✗ Failed to install jq${NC}"
            echo "  Please install manually: brew install jq"
            echo "  Then run this setup script again"
            exit 1
        }
    else
        echo -e "${RED}✗ Homebrew not found${NC}"
        echo "  Install jq manually: https://jqlang.github.io/jq/download/"
        echo "  Or install Homebrew: https://brew.sh"
        exit 1
    fi
fi

echo ""

# Handle reset mode if requested
if [ "$RESET_MODE" = true ]; then
    show_reset_warning
    cleanup_client_setup
    echo ""
    echo -e "${GREEN}✓ Cleanup complete. Proceeding with fresh setup...${NC}"
    echo ""
    sleep 1
fi

# Platform Selection
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Platform Selection${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Which messaging platforms do you want to monitor?"
echo ""
echo "  1) Slack only"
echo "  2) Teams only"
if [ "$HAS_NODE" = true ]; then
    echo "  3) Both Slack and Teams"
else
    echo "  3) Both Slack and Teams (requires Node.js - not available)"
fi
echo ""
read -p "Enter your choice (1-3): " PLATFORM_CHOICE

case $PLATFORM_CHOICE in
    1)
        PLATFORMS=("slack")
        echo -e "${GREEN}✓ Will monitor: Slack${NC}"
        ;;
    2)
        if [ "$HAS_NODE" = false ]; then
            echo -e "${RED}✗ Teams requires Node.js. Please install Node.js first.${NC}"
            exit 1
        fi
        PLATFORMS=("teams")
        echo -e "${GREEN}✓ Will monitor: Teams${NC}"
        ;;
    3)
        if [ "$HAS_NODE" = false ]; then
            echo -e "${RED}✗ Teams requires Node.js. Please install Node.js first.${NC}"
            exit 1
        fi
        PLATFORMS=("slack" "teams")
        echo -e "${GREEN}✓ Will monitor: Slack and Teams${NC}"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac
echo ""

# If Slack is selected, ask about workspace count
SLACK_WORKSPACE_COUNT=0
if [[ " ${PLATFORMS[@]} " =~ " slack " ]]; then
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Slack Workspace Configuration${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "How many Slack workspaces/organizations do you want to monitor?"
    echo "You can monitor multiple separate Slack organizations from this machine."
    echo ""
    read -p "Number of workspaces (1-5): " SLACK_WORKSPACE_COUNT

    # Validate input
    if [[ ! "$SLACK_WORKSPACE_COUNT" =~ ^[1-5]$ ]]; then
        echo -e "${RED}Error: Please enter a number between 1 and 5${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ Will configure $SLACK_WORKSPACE_COUNT Slack workspace(s)${NC}"
fi
echo ""

# Ensure scripts are executable
echo -e "${YELLOW}→ Making scripts executable...${NC}"
chmod +x "$PROJECT_DIR"/scripts/*.py "$PROJECT_DIR"/scripts/*.sh 2>/dev/null || true
echo -e "${GREEN}✓ Scripts ready in $PROJECT_DIR/scripts/${NC}"
echo ""

# Install dependencies
echo -e "${YELLOW}→ Installing dependencies...${NC}"
pip3 install --break-system-packages slack-sdk httpx python-dotenv 2>/dev/null || {
    echo -e "${YELLOW}  Trying without --break-system-packages...${NC}"
    pip3 install slack-sdk httpx python-dotenv
}
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Get server URL
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Server Configuration${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Enter the server URL (with ngrok or local IP):"
echo -e "${YELLOW}Examples:${NC}"
echo "  - https://abc123.ngrok.io (if using ngrok)"
echo "  - http://192.168.1.100:8000 (local network)"
echo ""
read -p "Server URL: " SERVER_URL

# Validate URL
if [[ ! $SERVER_URL =~ ^https?:// ]]; then
    echo -e "${RED}Error: URL must start with http:// or https://${NC}"
    exit 1
fi

# Configure Slack workspaces if selected
if [[ " ${PLATFORMS[@]} " =~ " slack " ]]; then
    MCP_CONFIG="$HOME/.claude/mcp-servers.json"

    # Check if MCP config already has Slack configured
    if [ -f "$MCP_CONFIG" ] && grep -q "slack" "$MCP_CONFIG"; then
        echo ""
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${BLUE}Slack Credentials${NC}"
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo -e "${GREEN}✓ Found existing MCP Slack configuration${NC}"
        echo "  Using credentials from ~/.claude/mcp-servers.json"
        SLACK_CONFIGURED=true
    else
        # Loop through each workspace
        for (( i=1; i<=SLACK_WORKSPACE_COUNT; i++ )); do
            echo ""
            echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            if [ $SLACK_WORKSPACE_COUNT -eq 1 ]; then
                echo -e "${BLUE}Slack Credentials${NC}"
                WORKSPACE_KEY="slack"
            else
                echo -e "${BLUE}Slack Workspace $i of $SLACK_WORKSPACE_COUNT${NC}"
                echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
                echo ""
                echo "Enter a name for this workspace (e.g., 'acme', 'startup'):"
                read -p "Workspace name: " WORKSPACE_NAME

                # Clean workspace name (lowercase, alphanumeric and hyphens only)
                WORKSPACE_NAME=$(echo "$WORKSPACE_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g')

                if [[ -z "$WORKSPACE_NAME" ]]; then
                    echo -e "${RED}Error: Workspace name is required${NC}"
                    exit 1
                fi

                WORKSPACE_KEY="slack-${WORKSPACE_NAME}"
                echo -e "${GREEN}✓ Workspace key: $WORKSPACE_KEY${NC}"
            fi
            echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo ""

            echo "You need a Slack User Token (starts with xoxp-)."
            echo "Get one at: https://api.slack.com/apps"
            echo ""
            read -p "Enter your Slack User Token (xoxp-...): " SLACK_TOKEN

            if [[ -z "$SLACK_TOKEN" ]]; then
                echo -e "${RED}Error: Token is required${NC}"
                exit 1
            fi

            # Auto-detect team ID from token
            echo ""
            echo -e "${YELLOW}→ Auto-detecting Slack Team ID...${NC}"

            TEAM_ID=$(python3 -c "
from slack_sdk import WebClient
import sys

try:
    client = WebClient('$SLACK_TOKEN')
    response = client.auth_test()
    print(response.get('team_id'))
except Exception as e:
    print('ERROR', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null)

            if [[ -z "$TEAM_ID" ]] || [[ ! "$TEAM_ID" =~ ^T ]]; then
                echo -e "${RED}✗ Failed to auto-detect Team ID${NC}"
                echo "  Make sure slack-sdk is installed: pip3 install slack-sdk"
                echo "  Or check that your token is valid"
                echo ""
                read -p "Enter your Slack Team ID manually (T...): " TEAM_ID

                if [[ ! "$TEAM_ID" =~ ^T ]]; then
                    echo -e "${RED}Error: Team ID should start with 'T'${NC}"
                    exit 1
                fi
            else
                echo -e "${GREEN}✓ Found Team ID: $TEAM_ID${NC}"
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

            # Create or update MCP config
            echo ""
            echo -e "${YELLOW}→ Updating MCP config...${NC}"
            mkdir -p "$HOME/.claude"

            # Use jq to safely add workspace to config
            if [ -f "$MCP_CONFIG" ]; then
                # Update existing config
                TEMP_CONFIG=$(mktemp)
                jq ".mcpServers.\"$WORKSPACE_KEY\" = {
                    \"command\": \"npx\",
                    \"args\": [\"-y\", \"@modelcontextprotocol/server-slack\"],
                    \"env\": {
                        \"SLACK_BOT_TOKEN\": \"$SLACK_TOKEN\",
                        \"SLACK_TEAM_ID\": \"$TEAM_ID\",
                        \"SLACK_ORG_NAME\": \"$ORG_NAME\"
                    }
                }" "$MCP_CONFIG" > "$TEMP_CONFIG" && mv "$TEMP_CONFIG" "$MCP_CONFIG"
            else
                # Create new config
                cat > "$MCP_CONFIG" <<EOF
{
  "mcpServers": {
    "$WORKSPACE_KEY": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "$SLACK_TOKEN",
        "SLACK_TEAM_ID": "$TEAM_ID",
        "SLACK_ORG_NAME": "$ORG_NAME"
      }
    }
  }
}
EOF
            fi

            chmod 600 "$MCP_CONFIG"
            echo -e "${GREEN}✓ Workspace '$WORKSPACE_KEY' added to MCP config${NC}"
        done

        SLACK_CONFIGURED=true
    fi
fi

# Configure Teams if selected
if [[ " ${PLATFORMS[@]} " =~ " teams " ]]; then
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Teams Configuration${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    # Check if Teams MCP is already configured
    if [ -f "$MCP_CONFIG" ] && grep -q "teams-mcp" "$MCP_CONFIG"; then
        echo -e "${GREEN}✓ Found existing Teams MCP configuration${NC}"
        TEAMS_CONFIGURED=true
    else
        echo "Setting up Microsoft Teams integration..."
        echo ""
        echo "This will:"
        echo "  1. Install the Teams MCP server"
        echo "  2. Run OAuth authentication (opens browser)"
        echo "  3. Add Teams to your MCP configuration"
        echo ""
        read -p "Continue with Teams setup? (y/n) " -n 1 -r
        echo
        echo

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}→ Installing Teams MCP server...${NC}"

            # Authenticate Teams MCP
            echo ""
            echo "Follow the prompts to authenticate with Microsoft Teams."
            echo "This will open your browser for OAuth authentication."
            echo ""

            npx @floriscornel/teams-mcp@latest authenticate

            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✓ Teams authentication successful${NC}"

                # Update MCP config to add Teams
                mkdir -p "$HOME/.claude"

                if [ -f "$MCP_CONFIG" ]; then
                    # Merge with existing config
                    echo -e "${YELLOW}→ Updating MCP configuration...${NC}"

                    # Create temporary Python script to merge JSON
                    python3 <<EOF
import json
import sys

try:
                    with open("$MCP_CONFIG", "r") as f:
                        config = json.load(f)
except:
                    config = {"mcpServers": {}}

if "mcpServers" not in config:
                    config["mcpServers"] = {}

config["mcpServers"]["teams-mcp"] = {
                    "command": "npx",
                    "args": ["-y", "@floriscornel/teams-mcp@latest"]
}

with open("$MCP_CONFIG", "w") as f:
                    json.dump(config, f, indent=2)

print("Configuration updated")
EOF
                else
                    # Create new config
                    cat > "$MCP_CONFIG" <<EOF
{
  "mcpServers": {
    "teams-mcp": {
      "command": "npx",
      "args": ["-y", "@floriscornel/teams-mcp@latest"]
    }
  }
}
EOF
                fi

                chmod 600 "$MCP_CONFIG"
                echo -e "${GREEN}✓ Teams MCP added to configuration${NC}"
                TEAMS_CONFIGURED=true
            else
                echo -e "${RED}✗ Teams authentication failed${NC}"
                echo "  You can retry later by running:"
                echo "  npx @floriscornel/teams-mcp@latest authenticate"
                TEAMS_CONFIGURED=false
            fi
        else
            echo -e "${YELLOW}⚠ Skipped Teams setup${NC}"
            TEAMS_CONFIGURED=false
        fi
    fi
fi

# Create configuration file
echo ""
echo -e "${YELLOW}→ Creating configuration file...${NC}"

# Convert bash array to JSON array
PLATFORMS_JSON=$(printf '%s\n' "${PLATFORMS[@]}" | jq -R . | jq -s .)

cat > "$HOME/.mentions-assistant-config" <<EOF
{
  "platforms": $PLATFORMS_JSON,
  "monitor_server_url": "$SERVER_URL",
  "client_id": "$(hostname)",
  "check_interval_hours": 1
}
EOF

chmod 600 "$HOME/.mentions-assistant-config"
echo -e "${GREEN}✓ Configuration saved${NC}"

echo ""

# Wrapper script already exists in repo - no need to create
echo -e "${GREEN}✓ Using wrapper script from repo${NC}"
echo ""

# Set up LaunchD (optional)
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Automation (Optional)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
read -p "Set up hourly automated checks? (y/n) " -n 1 -r
echo
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    PLIST_FILE="$HOME/Library/LaunchAgents/com.user.mentions-assistant.plist"

    cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.mentions-assistant</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$PROJECT_DIR/scripts/check-mentions-unified.sh</string>
    </array>

    <!-- Run every hour during work hours (8 AM - 7 PM) -->
    <key>StartCalendarInterval</key>
    <array>
$(for hour in {8..19}; do
    echo "        <dict>"
    echo "            <key>Hour</key>"
    echo "            <integer>$hour</integer>"
    echo "            <key>Minute</key>"
    echo "            <integer>0</integer>"
    echo "        </dict>"
done)
    </array>

    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/mentions-assistant.log</string>

    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/mentions-assistant-error.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin</string>
        <key>MONITOR_SERVER_URL</key>
        <string>$SERVER_URL</string>
        <key>CLIENT_ID</key>
        <string>$(hostname)</string>
    </dict>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

    # Load LaunchD agent
    launchctl load "$PLIST_FILE" 2>/dev/null || true

    echo -e "${GREEN}✓ LaunchD automation configured${NC}"
    echo "  Runs hourly from 8 AM to 7 PM"
    PLATFORMS_STR=$(printf " and %s" "${PLATFORMS[@]}" | sed 's/^ and //' | sed 's/ and \(.*\)/ and \1/')
    echo "  Monitoring: $PLATFORMS_STR"
    echo ""
fi

# Test connection
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Testing Connection${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}→ Testing connection to $SERVER_URL...${NC}"

if curl -s "$SERVER_URL/health" >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Server is reachable!${NC}"
else
    echo -e "${RED}✗ Cannot reach server${NC}"
    echo "  Make sure the server is running on the main machine"
    echo "  Run: ./scripts/run.sh (from the project directory)"
fi

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  ✅ Setup Complete!                          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Scripts location:${NC}"
echo "  $PROJECT_DIR/scripts/"
echo ""
echo -e "${YELLOW}To test manually:${NC}"
echo "  cd $PROJECT_DIR"
echo "  ./scripts/check-mentions-unified.sh"
echo ""
echo "  Or test individual platforms:"
if [[ " ${PLATFORMS[@]} " =~ " slack " ]]; then
    if [ $SLACK_WORKSPACE_COUNT -gt 1 ]; then
        echo "    python3 scripts/check-multi-slack.py    # Multiple workspaces"
    else
        echo "    python3 scripts/check-mentions-notify.py    # Single workspace"
    fi
fi
if [[ " ${PLATFORMS[@]} " =~ " teams " ]]; then
    echo "    python3 scripts/check-teams-mentions.py"
fi
echo ""
echo -e "${YELLOW}To view logs:${NC}"
echo "  tail -f ~/Library/Logs/mentions-assistant.log"
echo ""
echo -e "${YELLOW}To disable automation:${NC}"
echo "  launchctl unload ~/Library/LaunchAgents/com.user.mentions-assistant.plist"
echo ""
echo -e "${YELLOW}To reconfigure from scratch:${NC}"
echo "  ./setup-client.sh --reset"
echo ""
