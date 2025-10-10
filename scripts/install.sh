#!/bin/bash

# Slack Assistant Installer
# Automates the setup process

set -e  # Exit on error

echo "======================================"
echo "Slack Assistant Installer"
echo "======================================"
echo ""

# Get current user and home directory
CURRENT_USER=$(whoami)
HOME_DIR=$(eval echo ~$CURRENT_USER)

echo "Installing for user: $CURRENT_USER"
echo "Home directory: $HOME_DIR"
echo ""

# Detect claude binary location
CLAUDE_PATH=$(which claude 2>/dev/null || echo "")
if [ -z "$CLAUDE_PATH" ]; then
    echo "⚠️  Warning: 'claude' command not found in PATH"
    echo "   You may need to install Claude Code or update your PATH"
    echo "   Common locations: /opt/homebrew/bin/claude, /usr/local/bin/claude"
    echo ""
else
    echo "✓ Found claude at: $CLAUDE_PATH"
    echo ""
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "Project directory: $PROJECT_DIR"
echo ""

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p "$HOME_DIR/scripts/slack-assistant"
mkdir -p "$HOME_DIR/Library/LaunchAgents"
mkdir -p "$HOME_DIR/Library/Logs"
mkdir -p "$HOME_DIR/.claude"

# Copy scripts
echo "📄 Installing scripts..."
cp "$SCRIPT_DIR/check-slack-mentions.sh" "$HOME_DIR/scripts/slack-assistant/"
cp "$SCRIPT_DIR/check-slack-automated.sh" "$HOME_DIR/scripts/slack-assistant/"

# Make scripts executable
chmod +x "$HOME_DIR/scripts/slack-assistant/check-slack-mentions.sh"
chmod +x "$HOME_DIR/scripts/slack-assistant/check-slack-automated.sh"

echo "✓ Scripts installed"

# Install LaunchAgent with proper path substitution
echo ""
echo "⚙️  Installing LaunchAgent..."

# Copy and replace $HOME with actual path, and set CODEBASE_PATH
sed -e "s|\$HOME|$HOME_DIR|g" \
    -e "s|CODEBASE_PATH_PLACEHOLDER|$PROJECT_DIR|g" \
    "$PROJECT_DIR/launchd/com.user.slack-mention-check.plist" > "$HOME_DIR/Library/LaunchAgents/com.user.slack-mention-check.plist"

echo "✓ LaunchAgent installed"
echo "  Codebase path set to: $PROJECT_DIR"

# Check if MCP config exists
echo ""
if [ -f "$HOME_DIR/.claude/mcp-servers.json" ]; then
    echo "ℹ️  MCP config already exists at ~/.claude/mcp-servers.json"
    echo "   Verifying it contains Slack configuration..."
    if grep -q "slack" "$HOME_DIR/.claude/mcp-servers.json"; then
        echo "   ✓ Slack MCP server found in config"
    else
        echo "   ⚠️  Slack MCP server not found in config"
        echo "   Please add Slack configuration (see config/mcp-servers.example.json)"
    fi
else
    echo "⚠️  MCP config not found"
    echo "   Copy config/mcp-servers.example.json to ~/.claude/mcp-servers.json"
    echo "   and add your Slack tokens"
fi

echo ""
echo "======================================"
echo "✅ Installation Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo ""

if [ ! -f "$HOME_DIR/.claude/mcp-servers.json" ]; then
    echo "1. Configure MCP:"
    echo "   cp $PROJECT_DIR/config/mcp-servers.example.json ~/.claude/mcp-servers.json"
    echo "   nano ~/.claude/mcp-servers.json  # Add your Slack tokens"
    echo ""
fi

echo "2. Load LaunchAgent:"
echo "   launchctl load ~/Library/LaunchAgents/com.user.slack-mention-check.plist"
echo ""
echo "3. Set up keyboard shortcut:"
echo "   See $PROJECT_DIR/automator/WORKFLOW_INSTRUCTIONS.md"
echo ""
echo "4. Test manual check:"
echo "   ~/scripts/slack-assistant/check-slack-mentions.sh"
echo ""
echo "5. Check logs:"
echo "   tail -f ~/Library/Logs/slack-mentions.log"
echo ""

if [ -z "$CLAUDE_PATH" ]; then
    echo "⚠️  IMPORTANT: Install Claude Code before testing"
    echo "   Visit: https://claude.ai/download"
    echo ""
fi
