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
echo -e "${BLUE}║         Slack Monitor - Client Setup                        ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "This will set up this machine to report Slack mentions to"
echo "your centralized monitoring dashboard."
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is required but not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"
echo ""

# Create installation directory
echo -e "${YELLOW}→ Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"

# Copy client files from project
echo -e "${YELLOW}→ Copying client files...${NC}"
cp "$PROJECT_DIR/client/check-mentions-notify.py" "$INSTALL_DIR/"
cp "$PROJECT_DIR/client/check-mentions-with-monitor.sh" "$INSTALL_DIR/"
cp "$PROJECT_DIR/client/find-team-id.py" "$INSTALL_DIR/"
cp "$PROJECT_DIR/client/README.md" "$INSTALL_DIR/"

chmod +x "$INSTALL_DIR"/*.{py,sh}

echo -e "${GREEN}✓ Files copied to $INSTALL_DIR${NC}"
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

# Get Slack credentials (optional - can use MCP config)
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Slack Credentials${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if MCP config exists
MCP_CONFIG="$HOME/.claude/mcp-servers.json"
if [ -f "$MCP_CONFIG" ]; then
    echo -e "${GREEN}✓ Found existing MCP Slack configuration${NC}"
    echo "  Using credentials from ~/.claude/mcp-servers.json"
    USE_MCP=true
else
    echo "No MCP configuration found."
    echo ""
    echo "You need a Slack User Token (starts with xoxp-) and Team ID."
    echo "See: https://api.slack.com/apps"
    echo ""
    read -p "Enter your Slack User Token (xoxp-...): " SLACK_TOKEN
    read -p "Enter your Slack Team ID (T...): " TEAM_ID
    USE_MCP=false
fi

echo ""

# Update check-mentions-with-monitor.sh with paths
cat > "$INSTALL_DIR/check-mentions-with-monitor.sh" <<EOF
#!/bin/bash

# Wrapper for check-mentions-notify.py that uses monitoring project's venv
# This provides access to httpx for reporting to the monitoring server

PROJECT_DIR="$PROJECT_DIR"

# Check if virtual environment exists
if [ ! -d "\$PROJECT_DIR/venv" ]; then
    echo "ERROR: Virtual environment not found at \$PROJECT_DIR/venv"
    echo "Run \$PROJECT_DIR/setup.sh first"
    exit 1
fi

# Activate virtual environment
source "\$PROJECT_DIR/venv/bin/activate"

# Set monitoring server URL from environment or use default
export MONITOR_SERVER_URL="\${MONITOR_SERVER_URL:-http://localhost:8000}"
export CLIENT_ID="\$(hostname)"

# Run the Python script
python3 "\$HOME/scripts/slack-assistant/check-mentions-notify.py"

# Deactivate when done
deactivate
EOF

chmod +x "$INSTALL_DIR/check-mentions-with-monitor.sh"

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
    PLIST_FILE="$HOME/Library/LaunchAgents/com.user.slack-monitor-client.plist"

    cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.slack-monitor-client</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$HOME/scripts/slack-assistant/check-mentions-with-monitor.sh</string>
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
    <string>$HOME/Library/Logs/slack-monitor-client.log</string>

    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/slack-monitor-client-error.log</string>

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
echo "  ./check-mentions-with-monitor.sh"
echo ""
echo -e "${YELLOW}To view logs:${NC}"
echo "  tail -f ~/Library/Logs/slack-monitor-client.log"
echo ""
echo -e "${YELLOW}To disable automation:${NC}"
echo "  launchctl unload ~/Library/LaunchAgents/com.user.slack-monitor-client.plist"
echo ""
