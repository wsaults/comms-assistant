#!/bin/bash

# Slack Monitor Setup Script
# Sets up server, dashboard, and MCP Slack integration

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Slack Monitor Setup${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is required but not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"

# Create virtual environment
echo ""
echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
python3 -m venv venv

# Activate virtual environment
echo -e "${YELLOW}📦 Activating virtual environment...${NC}"
source venv/bin/activate

# Install dependencies
echo ""
echo -e "${YELLOW}📥 Installing dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Configure MCP Slack Server
echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}MCP Slack Configuration${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo "This will create ~/.claude/mcp-servers.json with Slack credentials."
echo ""
echo -e "${YELLOW}You need:${NC}"
echo "  1. Slack User Token (starts with xoxp-)"
echo "  2. Slack Team ID (starts with T)"
echo ""
echo "See QUICK_START.md for how to get these credentials."
echo ""

read -p "Do you want to configure MCP Slack now? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    read -p "Enter your Slack User Token (xoxp-...): " SLACK_TOKEN
    read -p "Enter your Slack Team ID (T...): " TEAM_ID

    # Create ~/.claude directory if it doesn't exist
    mkdir -p ~/.claude

    # Create mcp-servers.json
    cat > ~/.claude/mcp-servers.json <<EOF
{
  "mcpServers": {
    "slack": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-slack"
      ],
      "env": {
        "SLACK_BOT_TOKEN": "$SLACK_TOKEN",
        "SLACK_TEAM_ID": "$TEAM_ID"
      }
    }
  }
}
EOF

    echo ""
    echo -e "${GREEN}✓ MCP Slack configuration created at ~/.claude/mcp-servers.json${NC}"
else
    echo ""
    echo -e "${YELLOW}⚠ Skipping MCP configuration. You'll need to set this up manually.${NC}"
fi

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo -e "${YELLOW}Quick Start:${NC}"
echo ""
echo -e "Run the Slack Monitor:"
echo -e "   ${GREEN}./scripts/run.sh${NC}"
echo ""
echo -e "${BLUE}This will:${NC}"
echo "  • Start the FastAPI server in background"
echo "  • Auto-start ngrok tunnel (if installed)"
echo "  • Launch the dashboard with real-time updates"
echo ""
echo -e "${BLUE}Controls:${NC}"
echo "  • Press 'q' to quit dashboard (server keeps running)"
echo "  • Press 'r' to refresh data"
echo "  • Run ${GREEN}./scripts/stop.sh${NC} to stop the server"
echo ""
echo -e "${YELLOW}Optional - Install ngrok for remote access:${NC}"
echo "  brew install ngrok"
echo ""
echo -e "For more info, see ${BLUE}QUICK_START.md${NC}"
echo ""
