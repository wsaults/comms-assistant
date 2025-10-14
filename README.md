# Mentions Assistant

Centralized Slack and Microsoft Teams mentions monitoring with real-time dashboard and multi-client support.

## Features

- 🎯 **Multi-Platform** - Monitor Slack, Teams, or both
- 📊 **Real-time Textual Dashboard** - Live TUI showing mentions across all clients
- 🌐 **ngrok Integration** - Auto-starts public tunnel for remote access
- 👥 **Multi-client Support** - Monitor from multiple machines
- 📈 **Activity Graphs** - Visualize mentions per client over time
- ⏰ **Automated Checks** - Hourly monitoring during work hours (8 AM - 7 PM)
- 🔔 **macOS Notifications** - Native alerts when mentions found
- 💰 **Zero Cost** - Uses platform SDKs, no API charges
- 🔐 **Secure Authentication** - Slack tokens & Teams OAuth

## Architecture

```
┌─────────────────┐           ┌──────────────────────┐
│  Client Machine │           │   Server Machine     │
│                 │           │                      │
│  Checks:        │──HTTP────▶│  FastAPI Server      │
│   - Slack       │           │  (port 8000)         │
│   - Teams       │           │         │            │
│   - Both        │           │         ▼            │
└─────────────────┘           │  Textual Dashboard   │
                              │  (real-time TUI)     │
┌─────────────────┐           └──────────────────────┘
│  Client Machine │──HTTP────▶          │
│                 │                     │
│  Platform Mix   │              ngrok (optional)
└─────────────────┘                     │
                            https://abc123.ngrok.io
```

## Quick Start

### Server Setup (One Machine)

```bash
# Clone or navigate to the project directory
cd slack-mentions-assistant

# One-time setup
./setup.sh

# Start server + ngrok + dashboard
./run.sh
```

The dashboard will show:
- 📊 Stats (unread mentions, active channels, platform breakdown)
- 💬 Recent mentions from all clients and platforms
- 📈 Activity graph per client
- 🌐 Public ngrok URL (if installed)

### Client Setup (Any Machine)

```bash
# Option 1: Clone from GitHub
git clone https://github.com/wsaults/comms-assistant.git
cd comms-assistant
./setup-client.sh

# Option 2: Quick Teams-only setup
./setup-teams.sh

# Option 3: Copy via SCP (if not using GitHub)
scp -r slack-mentions-assistant user@newmachine:~/
cd ~/slack-mentions-assistant
./setup-client.sh
```

#### Interactive Platform Selection

During `./setup-client.sh`, you'll be asked:

```
Which messaging platforms do you want to monitor?
  1) Slack only
  2) Teams only
  3) Both Slack and Teams
```

Setup will then:
1. Install platform-specific dependencies
2. Configure authentication (Slack token OR Teams OAuth)
3. Ask for server URL (ngrok URL from dashboard)
4. Set up hourly automated checks (8 AM - 7 PM)

## Project Structure

```
slack-mentions-assistant/
├── setup.sh                   # Server setup (one-time)
├── setup-client.sh            # Client setup with platform selection
├── setup-teams.sh             # Quick Teams-only setup
├── run.sh                     # Start everything
├── stop.sh                    # Stop server
├── requirements.txt           # All dependencies
│
├── server/
│   ├── main.py                # FastAPI server
│   └── __init__.py
│
├── dashboard/
│   ├── main.py                # Textual TUI
│   └── __init__.py
│
├── scripts/slack-assistant/   # Client scripts
│   ├── check-mentions-notify.py       # Slack checker
│   ├── check-teams-mentions.py        # Teams checker
│   ├── check-all-mentions.py          # Unified checker
│   ├── check-mentions-unified.sh      # Wrapper script
│   └── find-team-id.py
│
└── launchd/
    ├── com.user.mentions-assistant.plist    # Unified agent
    └── com.user.teams-mentions.plist        # Teams-only agent
```

## Usage

### Server Commands

```bash
# Start everything
./run.sh

# Start with mock data (for testing/demo)
./run.sh --mock    # Generates fresh data from TODAY

# Stop server
./stop.sh

# View server logs
tail -f ~/Library/Logs/slack-monitor-server.log
```

### Dashboard Controls

- **q** - Quit dashboard (server keeps running)
- **r** - Refresh data manually

### Client Commands

```bash
# Manual test (unified checker)
cd ~/scripts/slack-assistant
./check-mentions-unified.sh

# Test individual platforms
python3 ~/scripts/slack-assistant/check-mentions-notify.py  # Slack
python3 ~/scripts/slack-assistant/check-teams-mentions.py   # Teams

# Test with specific platforms
python3 ~/scripts/slack-assistant/check-all-mentions.py --platforms slack teams

# View logs
tail -f ~/Library/Logs/mentions-assistant.log        # Unified
tail -f ~/Library/Logs/slack-mentions.log            # Slack-specific
tail -f ~/Library/Logs/teams-mentions.log            # Teams-specific

# Disable automation
launchctl unload ~/Library/LaunchAgents/com.user.mentions-assistant.plist
```

## Requirements

- **macOS** 13.0 (Ventura) or later
- **Python** 3.10+
- **Node.js** 18+ (required for Teams MCP)
- **jq** (for JSON manipulation): `brew install jq`
- **ngrok** (optional, for remote access): `brew install ngrok`

### Platform-Specific Requirements

**Slack:**
- Slack User Token (xoxp-...) with scopes:
  - `channels:history`, `channels:read`
  - `groups:history`, `im:history`
  - `search:read`, `users:read`

**Teams:**
- Microsoft 365 account with Teams access
- OAuth permissions (granted during setup):
  - User.Read, Chat.Read, ChannelMessage.Read.All, Sites.Read.All

## Configuration

### Platform Configuration

Platform selection is stored in `~/.mentions-assistant-config`:

```json
{
  "platforms": ["slack", "teams"],
  "monitor_server_url": "http://localhost:8000",
  "client_id": "hostname",
  "check_interval_hours": 1
}
```

To change platforms:
```bash
nano ~/.mentions-assistant-config
# Update platforms array: ["slack"], ["teams"], or ["slack", "teams"]

# Restart automation
launchctl unload ~/Library/LaunchAgents/com.user.mentions-assistant.plist
launchctl load ~/Library/LaunchAgents/com.user.mentions-assistant.plist
```

### MCP Configuration

Edit `~/.claude/mcp-servers.json` for platform credentials:

```json
{
  "mcpServers": {
    "slack": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "xoxp-your-token",
        "SLACK_TEAM_ID": "T-your-team-id"
      }
    },
    "teams-mcp": {
      "command": "npx",
      "args": ["-y", "@floriscornel/teams-mcp@latest"]
    }
  }
}
```

**Slack Setup:**
- Token auto-detected from existing MCP config, or
- Prompt for token during setup, Team ID auto-detected

**Teams Setup:**
- Run OAuth authentication: `npx @floriscornel/teams-mcp@latest authenticate`
- Browser opens for Microsoft login
- Permissions granted, tokens stored securely

### Automation Schedule

LaunchD agent runs hourly from 8 AM - 7 PM. To customize:

```bash
nano ~/Library/LaunchAgents/com.user.mentions-assistant.plist
# Modify StartCalendarInterval hours

launchctl unload ~/Library/LaunchAgents/com.user.mentions-assistant.plist
launchctl load ~/Library/LaunchAgents/com.user.mentions-assistant.plist
```

## ngrok Setup

For remote access (clients on different networks):

1. **Install ngrok:**
   ```bash
   brew install ngrok
   ```

2. **Authenticate** (one-time):
   ```bash
   ngrok config add-authtoken YOUR_TOKEN
   ```
   Get token from: https://dashboard.ngrok.com/get-started/your-authtoken

3. **Start server:**
   ```bash
   ./run.sh
   ```
   ngrok starts automatically and URL appears in dashboard

4. **Configure clients** with the ngrok URL shown in dashboard

## Development & Testing

### Mock Data

The dashboard can be tested with mock data without real Slack/Teams connections:

```bash
# Start with fresh mock data from today
./run.sh --mock

# Or seed data manually after server is running
curl -X POST "http://localhost:8000/api/debug/seed?scenario=default"

# Different scenarios
curl -X POST "http://localhost:8000/api/debug/seed?scenario=high_activity"
curl -X POST "http://localhost:8000/api/debug/seed?scenario=multi_job"

# Clear all data
curl -X DELETE "http://localhost:8000/api/debug/clear"
```

**Note**: Mock data is ALWAYS generated from today's date to ensure realistic testing.

## Troubleshooting

### Server won't start
```bash
# Check if port 8000 is in use
lsof -i :8000

# View server logs
tail -f ~/Library/Logs/slack-monitor-server.log
```

### Client can't connect
```bash
# Test server connection
curl http://SERVER_URL/health

# Should return: {"status":"healthy"}
```

### Slack: No mentions appearing
```bash
# Check Slack credentials
cat ~/.claude/mcp-servers.json

# Test manually
python3 ~/scripts/slack-assistant/check-mentions-notify.py

# View logs
tail -50 ~/Library/Logs/slack-mentions.log
```

### Teams: Authentication issues
```bash
# Re-authenticate Teams
npx @floriscornel/teams-mcp@latest authenticate

# Check Node.js is installed
which node

# Verify Teams MCP in config
cat ~/.claude/mcp-servers.json | grep teams-mcp

# View logs
tail -50 ~/Library/Logs/teams-mentions.log
```

### Teams: No mentions found
```bash
# Verify Claude Code can access Teams MCP
claude code "get my Teams mentions"

# Check OAuth permissions were granted
# Re-run authentication if needed
npx @floriscornel/teams-mcp@latest authenticate
```

### LaunchD not running
```bash
# Check agent status
launchctl list | grep mentions

# View agent errors
tail -f ~/Library/Logs/mentions-assistant-error.log

# Validate plist
plutil ~/Library/LaunchAgents/com.user.mentions-assistant.plist
```

### ngrok URL not showing
```bash
# Check if ngrok is installed
command -v ngrok

# Check ngrok is running
curl http://localhost:4040/api/tunnels

# Install if needed
brew install ngrok
```

## Version Control

This project is ready for version control:

```bash
# Repository: https://github.com/wsaults/comms-assistant

# To push changes:
git add .
git commit -m "Your commit message"
git push origin main
```

`.gitignore` excludes:
- `venv/`, `.env` files
- Logs and temporary files
- Sensitive config (tokens, PIDs, MCP configs)

## Deployment

### Share with team:
1. Push to GitHub/GitLab
2. Team members clone and run `./setup-client.sh`
3. They select their platform(s) during setup
4. They point to your ngrok URL

### Multi-machine personal use:
1. Clone to each machine
2. Run `./run.sh` on main machine (server)
3. Run `./setup-client.sh` on other machines (clients)
4. Each machine can monitor different platforms

## Platform-Specific Notes

### Slack
- Uses Slack Web API via `slack-sdk` Python package
- Direct API calls, no Claude Code required for runtime
- User tokens provide access to personal mentions
- Requires `search:read` scope for mention search

### Microsoft Teams
- Uses Teams MCP server via Claude Code
- Requires Claude Code installed and in PATH
- OAuth provides secure, long-lived access
- Tokens auto-refresh through MCP server
- Browser authentication required during setup

### Multi-Platform
- Each platform checked independently
- Aggregate notifications show total across platforms
- Platform-specific error handling
- Monitoring server tracks per-platform metrics

## Cost

**$0/month** - Uses platform SDKs directly, no API charges

Optional ngrok free tier provides public URL (changes on restart).

## Security

- **Slack tokens** (`xoxp-*`) are user tokens - treat as passwords
- **Teams tokens** stored securely by MCP server, auto-refreshed
- All config files protected with 600 permissions
- Logs may contain message content - review permissions
- Never commit tokens or MCP configs to version control

## License

MIT License - Feel free to modify and distribute

## Support

- **Unified logs:** `~/Library/Logs/mentions-assistant.log`
- **Slack logs:** `~/Library/Logs/slack-mentions.log`
- **Teams logs:** `~/Library/Logs/teams-mentions.log`
- **Server logs:** `~/Library/Logs/slack-monitor-server.log`

For detailed documentation, see `CLAUDE.md`
