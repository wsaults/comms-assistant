#!/bin/bash

# Automated Slack Mention Checker
# Runs via launchd on schedule
# Logs to file and sends notifications

LOG_FILE="$HOME/Library/Logs/slack-mentions.log"
ERROR_LOG="$HOME/Library/Logs/slack-mentions-error.log"
STATE_FILE="$HOME/.slack-mentions-state"

# Create log directory if it doesn't exist
mkdir -p "$HOME/Library/Logs"

# Redirect output to log files
exec 1>>"$LOG_FILE"
exec 2>>"$ERROR_LOG"

echo "====================================="
echo "Slack Mention Check: $(date)"
echo "====================================="

# Check if claude command exists
if ! command -v claude &> /dev/null; then
    echo "ERROR: 'claude' command not found"
    echo "Please install Claude Code or update PATH in LaunchAgent plist"
    exit 1
fi

# Check if MCP config exists
if [ ! -f "$HOME/.claude/mcp-servers.json" ]; then
    echo "ERROR: MCP configuration not found at ~/.claude/mcp-servers.json"
    echo "Please create config file with Slack credentials. See SETUP.md"
    exit 1
fi

# Get current directory (codebase path) - fallback to home if not set
CODEBASE_PATH="${CODEBASE_PATH:-$HOME}"

# Load last check timestamp (for state tracking)
LAST_CHECK_TIME=""
if [ -f "$STATE_FILE" ]; then
    LAST_CHECK_TIME=$(cat "$STATE_FILE")
    echo "Last check was at: $LAST_CHECK_TIME"
fi

# Run Claude Code in print mode and capture output
OUTPUT=$(echo "Check Slack for any mentions of me from the last hour.

If there are NEW mentions (not ones we've already seen):
1. Show me who mentioned me and what they said
2. Analyze if they need responses
3. For technical questions, search the codebase at $CODEBASE_PATH if helpful
4. Draft suggested responses
5. Log everything to the output

DO NOT post any responses automatically - just notify me about new mentions.

At the end, output EXACTLY one line in this format:
MENTIONS_FOUND: <number>

Where <number> is the count of new mentions found (0 if none)." | claude code --print)

CLAUDE_EXIT_CODE=$?

echo "$OUTPUT"

# Save current timestamp for next run
date "+%Y-%m-%d %H:%M:%S" > "$STATE_FILE"

# Check if mentions were found and send notification
MENTION_COUNT=$(echo "$OUTPUT" | grep "MENTIONS_FOUND:" | cut -d: -f2 | tr -d ' ')

if [ $CLAUDE_EXIT_CODE -ne 0 ]; then
    echo "WARNING: Claude Code exited with code $CLAUDE_EXIT_CODE"
fi

if [ ! -z "$MENTION_COUNT" ] && [ "$MENTION_COUNT" -gt 0 ]; then
    osascript -e "display notification \"Found $MENTION_COUNT new mention(s) in Slack\" with title \"Slack Assistant\" sound name \"default\""
    echo "Sent notification for $MENTION_COUNT mention(s)"
elif [ -z "$MENTION_COUNT" ]; then
    echo "WARNING: Could not parse MENTIONS_FOUND count from output"
else
    echo "No new mentions found"
fi

echo ""
echo "Check completed at $(date)"
echo "====================================="
echo ""
