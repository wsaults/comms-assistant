# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Mac automation tool that checks Slack mentions using Claude Code via MCP (Model Context Protocol). It provides two interaction modes:
1. **Manual**: Keyboard shortcut (Cmd+Shift+S) triggers on-demand checks
2. **Automated**: LaunchD agent runs hourly checks during work hours (9 AM - 5 PM)

The system is designed to run cost-free by using Claude Code subscriptions instead of API calls.

## Architecture

### Core Components

**Scripts (`~/scripts/slack-assistant/`):**
- `check-slack-mentions.sh` - Manual checker triggered by hotkey, prompts Claude for interactive mention review
- `check-slack-automated.sh` - Automated checker that auto-responds to mentions and logs to files

**Automation Layer:**
- LaunchD plist (`~/Library/LaunchAgents/com.user.slack-mention-check.plist`) - Schedules automated checks
- Automator Quick Action (`~/Library/Services/Check Slack Mentions.workflow`) - Enables hotkey trigger

**Configuration:**
- MCP config (`~/.claude/mcp-servers.json`) - Connects Claude Code to Slack via MCP server
- Uses Slack User Token (`xoxp-*`) and Team ID for authentication

**Logging:**
- `~/Library/Logs/slack-mentions.log` - Standard output
- `~/Library/Logs/slack-mentions-error.log` - Error output

### Data Flow

1. **Trigger** → LaunchD schedule OR keyboard hotkey
2. **Execute** → Shell script invokes `claude code` with heredoc prompt
3. **Process** → Claude Code uses Slack MCP to query mentions
4. **Respond** → Interactive (manual) or automated (scheduled)
5. **Notify** → macOS notifications via `osascript`
6. **Log** → File-based logging for audit trail

### Key Design Decisions

- **User Token vs Bot Token**: Uses Slack user tokens to search mentions of the actual user
- **Heredoc Prompts**: Prompts are embedded in shell scripts using heredoc (`<< 'CLAUDE_EOF'`) for easy customization
- **No API Costs**: Leverages Claude Code subscription instead of Claude API
- **Work Hours Only**: Default schedule runs 9 AM - 5 PM to avoid off-hours notifications

## Development Commands

### Testing Scripts

```bash
# Test manual check script
~/scripts/slack-assistant/check-slack-mentions.sh

# Test automated check script (logs to files)
~/scripts/slack-assistant/check-slack-automated.sh

# Test MCP connection
claude code "list my slack channels"
```

### Managing LaunchD Automation

```bash
# Load agent (enable)
launchctl load ~/Library/LaunchAgents/com.user.slack-mention-check.plist

# Unload agent (disable)
launchctl unload ~/Library/LaunchAgents/com.user.slack-mention-check.plist

# Start agent manually (one-time run)
launchctl start com.user.slack-mention-check

# Stop running agent
launchctl stop com.user.slack-mention-check

# Check if agent is loaded
launchctl list | grep slack-mention

# View launchd logs
log show --predicate 'subsystem == "com.apple.launchd"' --last 1h | grep slack
```

### Viewing Logs

```bash
# Tail all logs live
tail -f ~/Library/Logs/slack-mentions.log

# View last 50 lines
tail -50 ~/Library/Logs/slack-mentions.log

# View errors
tail -50 ~/Library/Logs/slack-mentions-error.log

# Search logs for specific date
grep "2025-10-10" ~/Library/Logs/slack-mentions.log
```

### Installation

```bash
# Run automated installer
cd scripts
chmod +x install.sh
./install.sh

# Validate plist syntax
plutil ~/Library/LaunchAgents/com.user.slack-mention-check.plist
```

## Configuration Modifications

### Customizing Claude Prompts

Edit the heredoc sections in shell scripts:

```bash
# For manual checks
nano ~/scripts/slack-assistant/check-slack-mentions.sh
# Modify content between 'CLAUDE_EOF' delimiters

# For automated checks
nano ~/scripts/slack-assistant/check-slack-automated.sh
# Modify content between 'CLAUDE_EOF' delimiters
```

### Changing Schedule

Edit LaunchD plist to adjust automation schedule:

```bash
nano ~/Library/LaunchAgents/com.user.slack-mention-check.plist
```

Common schedule modifications:
- **Every 30 minutes**: Replace `StartCalendarInterval` with `<key>StartInterval</key><integer>1800</integer>`
- **Custom hours**: Modify or add `<dict>` blocks with `<key>Hour</key>` and `<key>Minute</key>` entries
- **Weekend runs**: Remove weekday restrictions (not present by default)

After editing, reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.user.slack-mention-check.plist
launchctl load ~/Library/LaunchAgents/com.user.slack-mention-check.plist
```

### Updating MCP Configuration

```bash
# Edit MCP servers config
nano ~/.claude/mcp-servers.json

# Test changes
claude code "list my slack channels"
```

Required Slack User Token Scopes:
- `channels:history`, `channels:read`, `chat:write`, `users:read`, `search:read`, `groups:history`, `im:history`

## Important File Paths

When editing scripts, these paths must be absolute (not relative):

- **Scripts directory**: `~/scripts/slack-assistant/` (expand `~` to full path in LaunchD)
- **Logs directory**: `~/Library/Logs/`
- **MCP config**: `~/.claude/mcp-servers.json`
- **Codebase path**: Line 543 in `check-slack-automated.sh` - must be customized per installation

## Troubleshooting

### "claude: command not found"

Find claude binary and use full path in scripts:
```bash
which claude
# Replace "claude code" in scripts with full path like "/opt/homebrew/bin/claude code"
```

### LaunchD not running

```bash
# Check agent status
launchctl list | grep slack-mention

# Validate plist
plutil ~/Library/LaunchAgents/com.user.slack-mention-check.plist

# Check PATH in plist includes homebrew
# Default: /usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin
```

### No notifications appearing

Grant notification permissions:
1. System Settings → Notifications → Script Editor
2. Enable "Allow Notifications"

### MCP not connecting

```bash
# Test MCP manually
export SLACK_BOT_TOKEN="xoxp-..."
export SLACK_TEAM_ID="T..."
npx -y @modelcontextprotocol/server-slack
```

## Security Notes

- Slack tokens (`xoxp-*`) are user tokens with full account access - treat as passwords
- Tokens stored in `~/.claude/mcp-servers.json` should have restricted permissions (600)
- Logs may contain message content - review `~/Library/Logs/slack-mentions.log` permissions
- Never commit MCP config files to version control

## Extending Functionality

### Adding new shell scripts

1. Create script in `~/scripts/slack-assistant/`
2. Make executable: `chmod +x script-name.sh`
3. Test manually first
4. Add to Automator/Shortcuts for hotkey access OR modify LaunchD plist for scheduling

### Modifying automated responses

Edit `check-slack-automated.sh` line 538-553 to change Claude's behavior:
- Search different timeframes (change "last hour")
- Adjust auto-response confidence threshold
- Add custom codebase search paths
- Change notification format (line 562)

### Changing notification behavior

Edit `osascript` commands in scripts:
```bash
# Current format
osascript -e 'display notification "message" with title "Slack Assistant"'

# Add sound
osascript -e 'display notification "message" with title "Slack Assistant" sound name "default"'

# Change icon (requires app bundle)
osascript -e 'display notification "message" with title "Slack Assistant" sound name "default"'
```
