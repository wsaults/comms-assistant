# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Mac automation tool that checks mentions across **Slack and Microsoft Teams** using Claude Code via MCP (Model Context Protocol). It provides two interaction modes:
1. **Manual**: Run scripts on-demand to check for mentions
2. **Automated**: LaunchD agent runs hourly checks during work hours (8 AM - 7 PM)

Users can choose to monitor **Slack only**, **Teams only**, or **both platforms** during setup.

The system is designed to run cost-free by using Claude Code subscriptions instead of API calls.

## Architecture

### Core Components

**Scripts (`~/scripts/`):**
- `check-messages.py` - **Unified checker** - checks mentions AND channels, supports `--no-notify` flag
- `check-mentions-notify.py` - Slack mention checker with monitoring integration (single workspace)
- `check-multi-slack.py` - Slack mention checker for multiple workspaces
- `check-teams-mentions.py` - Teams mention checker with monitoring integration (MCP-based)
- `check-teams-local.py` - Teams mention checker using local database (no API required)
- `check-mentions-unified.sh` - Wrapper script for unified checker (used by LaunchD)

**Setup Scripts:**
- `setup-client.sh` - Interactive setup with platform selection
- `setup-teams.sh` - Quick Teams-only setup

**Automation Layer:**
- LaunchD plist (`~/Library/LaunchAgents/com.user.mentions-assistant.plist`) - Unified checker for selected platforms
- LaunchD plist (`~/Library/LaunchAgents/com.user.teams-mentions.plist`) - Teams-only alternative

**Configuration:**
- MCP config (`~/.claude/mcp-servers.json`) - Connects Claude Code to messaging platforms via MCP servers
  - Slack: `@modelcontextprotocol/server-slack` - Uses Slack User Token (`xoxp-*`) and Team ID
  - Teams: `@floriscornel/teams-mcp` - Uses OAuth authentication (browser-based)
- Platform config (`~/.mentions-assistant-config`) - Stores platform selection and settings
- Teams Local: No configuration needed - reads directly from Teams IndexedDB database

**Logging:**
- `~/Library/Logs/mentions-assistant.log` - Unified checker output
- `~/Library/Logs/slack-mentions.log` - Slack-specific output
- `~/Library/Logs/teams-mentions.log` - Teams-specific output
- Corresponding `-error.log` files for errors

### Data Flow

1. **Trigger** → LaunchD schedule OR manual execution
2. **Execute** → Python script queries MCP servers
3. **Process** →
   - Slack: Direct API calls via slack-sdk
   - Teams (MCP): Claude Code MCP queries via `get_my_mentions` tool
   - Teams (Local): Read directly from Teams IndexedDB database (30-60s parse time)
4. **Filter** → Recent mentions (last hour by default)
5. **Notify** → macOS notifications via `osascript`
6. **Report** → Send data to monitoring server (optional)
7. **Log** → File-based logging for audit trail

### Key Design Decisions

- **Platform Selection**: Users choose Slack, Teams, or both during setup
- **MCP-based**: All platform integrations use Model Context Protocol for consistency
- **User Token vs Bot Token**: Uses Slack user tokens to search mentions of the actual user
- **OAuth for Teams**: Teams uses browser-based OAuth authentication for security
- **Unified Checker**: Single script checks all selected platforms for efficiency
- **No API Costs**: Leverages Claude Code subscription instead of Claude API
- **Work Hours Only**: Default schedule runs 8 AM - 7 PM to avoid off-hours notifications

## Development Commands

### Testing Scripts

```bash
# Unified checker - checks mentions AND channels
python3 ~/scripts/check-messages.py              # With server reporting
python3 ~/scripts/check-messages.py --no-notify  # Without server reporting
python3 ~/scripts/check-messages.py --hours 24   # Last 24 hours

# Individual platform checkers
python3 ~/scripts/check-mentions-notify.py       # Slack (single workspace)
python3 ~/scripts/check-multi-slack.py           # Slack (multi-workspace)
python3 ~/scripts/check-teams-mentions.py        # Teams MCP only
python3 ~/scripts/check-teams-local.py --hours 24   # Teams local only

# Test MCP connections
claude code "list my slack channels"          # Test Slack MCP
claude code "get my Teams mentions"           # Test Teams MCP
```

### Managing LaunchD Automation

```bash
# Unified mentions assistant
launchctl load ~/Library/LaunchAgents/com.user.mentions-assistant.plist
launchctl unload ~/Library/LaunchAgents/com.user.mentions-assistant.plist
launchctl start com.user.mentions-assistant

# Teams-only (if using separate agent)
launchctl load ~/Library/LaunchAgents/com.user.teams-mentions.plist
launchctl unload ~/Library/LaunchAgents/com.user.teams-mentions.plist

# Check if agent is loaded
launchctl list | grep mentions

# View launchd logs
log show --predicate 'subsystem == "com.apple.launchd"' --last 1h | grep mentions
```

### Viewing Logs

```bash
# Unified logs
tail -f ~/Library/Logs/mentions-assistant.log

# Platform-specific logs
tail -f ~/Library/Logs/slack-mentions.log
tail -f ~/Library/Logs/teams-mentions.log

# View last 50 lines
tail -50 ~/Library/Logs/mentions-assistant.log

# View errors
tail -50 ~/Library/Logs/mentions-assistant-error.log

# Search logs for specific date
grep "2025-10-13" ~/Library/Logs/mentions-assistant.log
```

### Installation

```bash
# Interactive setup with platform selection
./setup-client.sh

# Quick Teams-only setup
./setup-teams.sh

# Validate plist syntax
plutil ~/Library/LaunchAgents/com.user.mentions-assistant.plist
```

## Configuration Modifications

### Changing Platform Selection

Edit the configuration file:

```bash
nano ~/.mentions-assistant-config
```

Update the platforms array:
```json
{
  "platforms": ["slack", "teams", "teams-local"],
  "monitor_server_url": "http://localhost:8000",
  "client_id": "hostname",
  "check_interval_hours": 1
}
```

Note: You can use "teams" (MCP-based) OR "teams-local" (local database), or both if you want redundancy.

Then restart the LaunchD agent:
```bash
launchctl unload ~/Library/LaunchAgents/com.user.mentions-assistant.plist
launchctl load ~/Library/LaunchAgents/com.user.mentions-assistant.plist
```

### Changing Schedule

Edit LaunchD plist to adjust automation schedule:

```bash
nano ~/Library/LaunchAgents/com.user.mentions-assistant.plist
```

Common schedule modifications:
- **Every 30 minutes**: Replace `StartCalendarInterval` with `<key>StartInterval</key><integer>1800</integer>`
- **Custom hours**: Modify or add `<dict>` blocks with `<key>Hour</key>` and `<key>Minute</key>` entries
- **Weekend runs**: Works by default (no weekday restrictions)

After editing, reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.user.mentions-assistant.plist
launchctl load ~/Library/LaunchAgents/com.user.mentions-assistant.plist
```

### Updating MCP Configuration

```bash
# Edit MCP servers config
nano ~/.claude/mcp-servers.json
```

Example configuration with both platforms:
```json
{
  "mcpServers": {
    "slack": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "xoxp-...",
        "SLACK_TEAM_ID": "T..."
      }
    },
    "teams-mcp": {
      "command": "npx",
      "args": ["-y", "@floriscornel/teams-mcp@latest"]
    }
  }
}
```

**Slack Configuration:**
```bash
# Test Slack MCP
claude code "list my slack channels"
```

Required Slack User Token Scopes:
- `channels:history`, `channels:read`, `chat:write`, `users:read`, `search:read`, `groups:history`, `im:history`

**Teams Configuration:**
```bash
# Authenticate Teams MCP
npx @floriscornel/teams-mcp@latest authenticate

# Test Teams MCP
claude code "get my Teams mentions"
```

Required Teams Permissions (granted during OAuth):
- User.Read, Chat.Read, ChannelMessage.Read.All, Sites.Read.All

## Important File Paths

When editing scripts, these paths must be absolute (not relative):

- **Scripts directory**: `~/scripts/` (expand `~` to full path in LaunchD)
- **Logs directory**: `~/Library/Logs/`
- **MCP config**: `~/.claude/mcp-servers.json`
- **Platform config**: `~/.mentions-assistant-config`

## Troubleshooting

### "claude: command not found"

Find claude binary and use full path:
```bash
which claude
# Update PATH in LaunchD plist to include /opt/homebrew/bin
```

### LaunchD not running

```bash
# Check agent status
launchctl list | grep mentions

# Validate plist
plutil ~/Library/LaunchAgents/com.user.mentions-assistant.plist

# Check PATH in plist includes both /opt/homebrew/bin and /usr/local/bin
# Default: /usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin
```

### No notifications appearing

Grant notification permissions:
1. System Settings → Notifications → Terminal (or Script Editor)
2. Enable "Allow Notifications"

### Slack MCP not connecting

```bash
# Test MCP manually
export SLACK_BOT_TOKEN="xoxp-..."
export SLACK_TEAM_ID="T..."
npx -y @modelcontextprotocol/server-slack
```

### Teams MCP not connecting

```bash
# Re-authenticate Teams MCP
npx @floriscornel/teams-mcp@latest authenticate

# Check if Node.js is installed
which node

# Verify Teams MCP is in config
cat ~/.claude/mcp-servers.json | grep teams-mcp
```

### Teams authentication failed

Common issues:
- **Browser didn't open**: Check firewall/pop-up blocker settings
- **Permissions denied**: Ensure your Microsoft 365 account has access to Teams
- **Token expired**: Re-run `npx @floriscornel/teams-mcp@latest authenticate`

### No mentions found

For Slack:
```bash
# Verify token has search permissions
# Check logs for API errors
tail -50 ~/Library/Logs/slack-mentions.log
```

For Teams (MCP):
```bash
# Verify OAuth permissions were granted
# Check logs for MCP errors
tail -50 ~/Library/Logs/teams-mentions.log
```

For Teams (Local):
```bash
# Check database exists
ls ~/Library/Containers/com.microsoft.teams2/Data/Library/Application\ Support/Microsoft/MSTeams/EBWebView/WV2Profile_tfw/IndexedDB/

# Try viewing all mentions (not just recent)
python3 client/check-teams-local.py --all

# Check if dfindexeddb is installed
pip3 show dfindexeddb
```

### Teams Local database not found

**Check Teams v2 is installed:**
```bash
ls "/Applications/Microsoft Teams.app"
```

**Verify database path exists:**
```bash
ls ~/Library/Containers/com.microsoft.teams2/Data/Library/Application\ Support/Microsoft/MSTeams/EBWebView/WV2Profile_tfw/IndexedDB/
```

**Ensure Teams has been used recently** - the database needs to be populated with cached data

### Teams Local parse too slow

- Normal parse time: 30-60 seconds
- Large databases: up to 2 minutes
- This is expected behavior for database parsing
- Consider running less frequently (hourly instead of every 15 minutes)
- Not suitable for real-time notifications

### dfindexeddb not found

```bash
# Install it
pip3 install dfindexeddb

# Verify installation
~/Library/Python/3.9/bin/dfindexeddb --help

# Add to PATH if needed
export PATH="$PATH:$HOME/Library/Python/3.9/bin"
```

## Security Notes

- **Slack tokens** (`xoxp-*`) are user tokens with full account access - treat as passwords
- **Teams tokens** are stored securely by the Teams MCP server and auto-refreshed
- Tokens stored in `~/.claude/mcp-servers.json` should have restricted permissions (600)
- Configuration file `~/.mentions-assistant-config` should have restricted permissions (600)
- Logs may contain message content - review log file permissions
- Never commit MCP config files or platform config to version control

## Extending Functionality

### Adding new platforms

1. Find or create an MCP server for the platform
2. Add MCP server to `~/.claude/mcp-servers.json`
3. Create a platform-specific checker script (e.g., `check-discord-mentions.py`)
4. Add platform to `check-messages.py` logic (add a new check function and platform case)
5. Update `setup-client.sh` to include new platform option

### Modifying notification behavior

Edit notification calls in Python scripts:
```python
# Current format
show_notification("Teams Mentions", f"You have {count} new mention(s)!")

# Customize message
show_notification("Teams", f"{count} mentions in {channel_count} channels")
```

### Changing check interval

Option 1: Edit LaunchD plist schedule (see "Changing Schedule" above)

Option 2: Modify `check_interval_hours` in config:
```json
{
  "check_interval_hours": 2
}
```

### Custom monitoring server

Update server URL in config:
```bash
nano ~/.mentions-assistant-config
```

```json
{
  "monitor_server_url": "https://your-server.com",
  "platforms": ["slack", "teams"]
}
```

## Platform-Specific Notes

### Slack

- Uses Slack Web API via `slack-sdk` Python package
- Searches mentions using `search.messages` API endpoint
- Filters results by timestamp for recent mentions
- Requires user token (not bot token) to search user mentions

### Microsoft Teams (MCP)

- Uses Teams MCP server via Claude Code
- Queries mentions using `get_my_mentions` tool
- OAuth authentication provides secure, long-lived access
- Tokens auto-refresh through MCP server
- Requires Node.js 18+ for MCP server

### Microsoft Teams (Local)

**Overview:**
- Reads mentions directly from Teams v2 local IndexedDB database
- **No API access or organizational permissions required**
- Completely offline operation
- Parse time: 30-60 seconds per check

**How it works:**
- Teams v2 stores data in IndexedDB at: `~/Library/Containers/com.microsoft.teams2/Data/Library/Application Support/Microsoft/MSTeams/EBWebView/WV2Profile_tfw/IndexedDB/https_teams.microsoft.com_0.indexeddb.leveldb`
- Uses `dfindexeddb` tool to parse LevelDB format
- Extracts mentions from Database 25 (activities) and matches with Database 15 (message content)
- Parses HTML message content to extract plain text

**Installation:**
```bash
pip3 install dfindexeddb
```

**Usage:**
```bash
# Check last hour
python3 client/check-teams-local.py

# Check last 24 hours
python3 client/check-teams-local.py --hours 24

# View all cached mentions
python3 client/check-teams-local.py --all

# JSON output for integration
python3 client/check-teams-local.py --json
```

**Advantages:**
- ✅ No setup complexity (one pip install)
- ✅ No external services or webhooks needed
- ✅ Works completely offline
- ✅ Access to historical data (all cached mentions)
- ✅ No organizational permissions needed

**Limitations:**
- ⚠️ Only cached messages (typically recent weeks)
- ⚠️ Parse time of 30-60 seconds (not suitable for real-time)
- ⚠️ Requires Teams v2 (New Teams)
- ⚠️ Poll-based (must run periodically)

**Best for:**
- Hourly or daily automated checks
- Situations where API access is not available
- Privacy-focused users who want local-only operation
- Historical mention analysis

**Documentation:**
- `TEAMS_LOCAL_ACCESS.md` - Complete technical documentation
- `QUICK_REFERENCE.md` - Quick start guide

**Utilities (in `scripts/`):**
- `analyze-teams-db.py` - Database structure analyzer
- `test-teams-db.py` - Database access test utility
- `add-slack-workspace.sh` - Add Slack workspace to MCP config
- `add-channels-to-watchlist.sh` - Add channels to watchlist
- `remove-channels-from-watchlist.sh` - Remove channels from watchlist
- `view-watchlist.sh` - View current watchlist
- `update-org-name.sh` - Update workspace display name
- `clear-db.sh` - Clear local monitoring database
- `run.sh` - Start monitoring server
- `stop.sh` - Stop monitoring server

## Quick Usage

**Recommended:** Use the unified `check-messages.py` script:
```bash
# Check everything (mentions + channels) with server reporting
python3 ~/scripts/check-messages.py

# Check without reporting to server
python3 ~/scripts/check-messages.py --no-notify

# Check last 24 hours
python3 ~/scripts/check-messages.py --hours 24
```

This script:
- ✅ Checks mentions across all platforms
- ✅ Checks monitored channels (from watchlist)
- ✅ Gracefully skips unavailable platforms
- ✅ Supports `--no-notify` flag to disable server reporting
- ✅ Auto-detects single vs multi-workspace Slack

### Multi-Platform Support

- Unified checker runs platform checks in sequence
- Each platform has independent error handling
- Aggregate notifications show total across all platforms
- Monitoring server tracks platform-specific metrics
