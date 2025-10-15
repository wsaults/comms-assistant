#!/bin/bash

# Teams Assistant Setup
# Simplified setup for Teams-only monitoring

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
INSTALL_DIR="$HOME/scripts"
MCP_CONFIG="$HOME/.claude/mcp-servers.json"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Microsoft Teams - Quick Setup                       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "This will set up Microsoft Teams mention monitoring."
echo ""

# Check prerequisites
echo -e "${YELLOW}→ Checking prerequisites...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is required but not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 found${NC}"

if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is required for Teams MCP${NC}"
    echo "  Install from: https://nodejs.org/"
    exit 1
fi
echo -e "${GREEN}✓ Node.js found${NC}"

# Check for jq
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
echo -e "${GREEN}✓ jq found${NC}"

echo ""

# Create installation directory
echo -e "${YELLOW}→ Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"

# Copy scripts
echo -e "${YELLOW}→ Copying client files...${NC}"
for file in "$PROJECT_DIR"/scripts/*.py "$PROJECT_DIR"/scripts/*.sh; do
    if [ -f "$file" ]; then
        cp "$file" "$INSTALL_DIR/"
    fi
done
chmod +x "$INSTALL_DIR"/*.py "$INSTALL_DIR"/*.sh 2>/dev/null || true
echo -e "${GREEN}✓ Files copied${NC}"
echo ""

# Install dependencies
echo -e "${YELLOW}→ Installing Python dependencies...${NC}"
pip3 install --break-system-packages mcp httpx 2>/dev/null || pip3 install mcp httpx
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Teams authentication
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Teams Authentication${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if Teams MCP is already configured
if [ -f "$MCP_CONFIG" ] && grep -q "teams-mcp" "$MCP_CONFIG"; then
    echo -e "${GREEN}✓ Teams MCP already configured${NC}"
else
    echo "Setting up Microsoft Teams MCP server..."
    echo ""
    echo "This will:"
    echo "  1. Install the Teams MCP server"
    echo "  2. Run OAuth authentication (opens browser)"
    echo "  3. Add Teams to your MCP configuration"
    echo ""

    # Authenticate Teams MCP
    echo "Follow the prompts to authenticate with Microsoft Teams."
    echo "This will open your browser for OAuth authentication."
    echo ""
    read -p "Press Enter to continue..."
    echo ""

    npx @floriscornel/teams-mcp@latest authenticate

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Teams authentication successful${NC}"

        # Update MCP config
        mkdir -p "$HOME/.claude"

        if [ -f "$MCP_CONFIG" ]; then
            # Merge with existing config
            echo -e "${YELLOW}→ Updating MCP configuration...${NC}"

            python3 <<EOF
import json

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
        echo -e "${GREEN}✓ Teams MCP configured${NC}"
    else
        echo -e "${RED}✗ Teams authentication failed${NC}"
        exit 1
    fi
fi

echo ""

# Get monitoring server URL (optional)
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Monitoring Server (Optional)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Enter the monitoring server URL (leave blank for local-only):"
read -p "Server URL: " SERVER_URL

if [ -z "$SERVER_URL" ]; then
    SERVER_URL="http://localhost:8000"
    echo -e "${YELLOW}→ Using default: $SERVER_URL${NC}"
fi

echo ""

# Create configuration
echo -e "${YELLOW}→ Creating configuration file...${NC}"

cat > "$HOME/.mentions-assistant-config" <<EOF
{
  "platforms": ["teams"],
  "monitor_server_url": "$SERVER_URL",
  "client_id": "$(hostname)",
  "check_interval_hours": 1
}
EOF

chmod 600 "$HOME/.mentions-assistant-config"
echo -e "${GREEN}✓ Configuration saved${NC}"
echo ""

# Set up automation
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Automation (Optional)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
read -p "Set up hourly automated checks? (y/n) " -n 1 -r
echo
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    PLIST_FILE="$HOME/Library/LaunchAgents/com.user.teams-mentions.plist"

    cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.teams-mentions</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$HOME/scripts/check-teams-mentions.py</string>
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
    <string>$HOME/Library/Logs/teams-mentions.log</string>

    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/teams-mentions-error.log</string>

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
    echo ""
fi

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              ✅ Teams Setup Complete!                        ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}To test manually:${NC}"
echo "  python3 $INSTALL_DIR/check-teams-mentions.py"
echo ""
echo -e "${YELLOW}To view logs:${NC}"
echo "  tail -f ~/Library/Logs/teams-mentions.log"
echo ""
echo -e "${YELLOW}To disable automation:${NC}"
echo "  launchctl unload ~/Library/LaunchAgents/com.user.teams-mentions.plist"
echo ""
