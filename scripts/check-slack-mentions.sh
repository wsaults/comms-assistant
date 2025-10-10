#!/bin/bash

# Manual Slack Mention Checker
# Triggered by keyboard shortcut
# Uses Claude Code (no API costs)

# Check if claude command exists
if ! command -v claude &> /dev/null; then
    echo "❌ Error: 'claude' command not found"
    echo ""
    echo "Please install Claude Code or use the full path to the claude binary."
    echo "Find your claude path with: which claude"
    echo ""
    osascript -e 'display notification "claude command not found. Please check installation." with title "Slack Assistant Error"'
    exit 1
fi

# Check if MCP config exists
if [ ! -f "$HOME/.claude/mcp-servers.json" ]; then
    echo "❌ Error: MCP configuration not found"
    echo ""
    echo "Please create ~/.claude/mcp-servers.json with your Slack credentials."
    echo "See SETUP.md for instructions."
    echo ""
    osascript -e 'display notification "MCP config not found. See SETUP.md" with title "Slack Assistant Error"'
    exit 1
fi

echo "🔍 Checking Slack for mentions..."
echo "================================"
echo ""

# Run Claude Code with the check command
claude code << 'CLAUDE_EOF'
Check Slack for any mentions of me from the last 2 hours.

For each mention found:
1. Tell me who mentioned me
2. Which channel it was in
3. What they said
4. Whether it looks like a question that needs a response

If there are technical questions:
- Search my codebase for relevant information
- Draft helpful responses
- Ask me if I want to post them

Use the Slack MCP tools to search and post messages.
CLAUDE_EOF

CLAUDE_EXIT_CODE=$?

echo ""
echo "================================"

if [ $CLAUDE_EXIT_CODE -eq 0 ]; then
    echo "✅ Check complete!"
    osascript -e 'display notification "Slack mention check complete!" with title "Slack Assistant"'
else
    echo "⚠️  Check completed with errors (exit code: $CLAUDE_EXIT_CODE)"
    osascript -e 'display notification "Check completed with errors" with title "Slack Assistant"'
fi
