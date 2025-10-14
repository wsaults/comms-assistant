#!/bin/bash

# Slack Monitor Client Setup
# Copies client files and configures this machine to report to the dashboard server

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
INSTALL_DIR="$HOME/scripts/slack-assistant"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

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
        brew install jq
    else
        echo -e "${RED}✗ Could not install jq automatically${NC}"
        echo "  Install it manually: brew install jq"
        exit 1
    fi
fi

echo ""

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

# Create installation directory
echo -e "${YELLOW}→ Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"

# Copy client files from project (copy all scripts)
echo -e "${YELLOW}→ Copying client files...${NC}"
for file in "$PROJECT_DIR"/scripts/slack-assistant/*.py "$PROJECT_DIR"/scripts/slack-assistant/*.sh; do
    if [ -f "$file" ]; then
        cp "$file" "$INSTALL_DIR/"
    fi
done

chmod +x "$INSTALL_DIR"/*.py "$INSTALL_DIR"/*.sh 2>/dev/null || true

echo -e "${GREEN}✓ Files copied to $INSTALL_DIR${NC}"
echo ""

# Install dependencies
echo -e "${YELLOW}→ Installing dependencies...${NC}"
pip3 install --break-system-packages mcp slack-sdk httpx python-dotenv 2>/dev/null || {
    echo -e "${YELLOW}  Trying without --break-system-packages...${NC}"
    pip3 install mcp slack-sdk httpx python-dotenv
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

# Configure Slack if selected
if [[ " ${PLATFORMS[@]} " =~ " slack " ]]; then
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Slack Credentials${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    # Check if MCP config exists
    MCP_CONFIG="$HOME/.claude/mcp-servers.json"
    if [ -f "$MCP_CONFIG" ] && grep -q "slack" "$MCP_CONFIG"; then
        echo -e "${GREEN}✓ Found existing MCP Slack configuration${NC}"
        echo "  Using credentials from ~/.claude/mcp-servers.json"
        SLACK_CONFIGURED=true
else
    echo "No MCP configuration found."
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

    # Create MCP config on this machine so check-mentions-notify.py can find it
    echo ""
    echo -e "${YELLOW}→ Creating MCP config...${NC}"
    mkdir -p "$HOME/.claude"

    cat > "$MCP_CONFIG" <<EOF
{
  "mcpServers": {
    "slack": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "$SLACK_TOKEN",
        "SLACK_TEAM_ID": "$TEAM_ID"
      }
    }
  }
}
EOF

        chmod 600 "$MCP_CONFIG"
        echo -e "${GREEN}✓ MCP config created at ~/.claude/mcp-servers.json${NC}"

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

# Create unified checker wrapper
cat > "$INSTALL_DIR/check-mentions-unified.sh" <<EOF
#!/bin/bash

# Unified Mentions Checker Wrapper
# Uses virtual environment if available, otherwise uses system Python

PROJECT_DIR="$PROJECT_DIR"

# Set environment variables
export MONITOR_SERVER_URL="\${MONITOR_SERVER_URL:-http://localhost:8000}"
export CLIENT_ID="\$(hostname)"

# Try to use project venv if available, otherwise use system Python
if [ -d "\$PROJECT_DIR/venv" ]; then
    source "\$PROJECT_DIR/venv/bin/activate"
    python3 "\$HOME/scripts/slack-assistant/check-all-mentions.py"
    deactivate
else
    python3 "\$HOME/scripts/slack-assistant/check-all-mentions.py"
fi
EOF

chmod +x "$INSTALL_DIR/check-mentions-unified.sh"

echo -e "${GREEN}✓ Configuration updated${NC}"
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
        <string>$HOME/scripts/slack-assistant/check-mentions-unified.sh</string>
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
    echo "  Run: ./run.sh (from the project directory)"
fi

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  ✅ Setup Complete!                          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Installed to:${NC}"
echo "  $INSTALL_DIR"
echo ""
echo -e "${YELLOW}To test manually:${NC}"
echo "  cd $INSTALL_DIR"
echo "  ./check-mentions-unified.sh"
echo ""
echo "  Or test individual platforms:"
if [[ " ${PLATFORMS[@]} " =~ " slack " ]]; then
    echo "    python3 $INSTALL_DIR/check-mentions-notify.py"
fi
if [[ " ${PLATFORMS[@]} " =~ " teams " ]]; then
    echo "    python3 $INSTALL_DIR/check-teams-mentions.py"
fi
echo ""
echo -e "${YELLOW}To view logs:${NC}"
echo "  tail -f ~/Library/Logs/mentions-assistant.log"
echo ""
echo -e "${YELLOW}To disable automation:${NC}"
echo "  launchctl unload ~/Library/LaunchAgents/com.user.mentions-assistant.plist"
echo ""
