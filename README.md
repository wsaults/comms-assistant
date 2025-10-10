# Slack Monitor

Centralized Slack mentions monitoring with real-time dashboard and multi-client support.

## Features

- 📊 **Real-time Textual Dashboard** - Live TUI showing mentions across all clients
- 🌐 **ngrok Integration** - Auto-starts public tunnel for remote access
- 👥 **Multi-client Support** - Monitor Slack from multiple machines
- 📈 **Activity Graphs** - Visualize mentions per client over time
- ⏰ **Automated Checks** - Hourly monitoring during work hours (8 AM - 7 PM)
- 🔔 **macOS Notifications** - Native alerts when mentions found
- 💰 **Zero Cost** - Uses Slack SDK, no API charges

## Architecture

```
┌─────────────────┐           ┌──────────────────────┐
│  Client Machine │           │   Server Machine     │
│                 │           │                      │
│  Checks Slack   │──HTTP────▶│  FastAPI Server      │
│  Reports Data   │           │  (port 8000)         │
└─────────────────┘           │         │            │
                              │         ▼            │
┌─────────────────┐           │  Textual Dashboard   │
│  Client Machine │──HTTP────▶│  (real-time TUI)     │
│                 │           └──────────────────────┘
│  Checks Slack   │                     │
└─────────────────┘              ngrok (optional)
                                        │
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
- 📊 Stats (unread mentions, active channels, etc.)
- 💬 Recent mentions from all clients
- 📈 Activity graph per client
- 🌐 Public ngrok URL (if installed)

### Client Setup (Any Machine)

```bash
# Option 1: Clone from GitHub
git clone https://github.com/wsaults/comms-assistant.git
cd comms-assistant
./setup-client.sh

# Option 2: Copy via SCP (if not using GitHub)
# On source machine:
scp -r slack-mentions-assistant user@newmachine:~/

# On new machine:
cd ~/slack-mentions-assistant
./setup-client.sh
```

Client setup will:
1. Install dependencies (slack-sdk, httpx, python-dotenv)
2. Ask for server URL (ngrok URL from dashboard)
3. Configure Slack credentials (auto-detects Team ID from token)
4. Set up hourly automated checks (8 AM - 7 PM)

## Project Structure

```
slack-mentions-assistant/
├── setup.sh              # Server setup (one-time)
├── run.sh                # Start everything
├── stop.sh               # Stop server
├── setup-client.sh       # Client setup
├── requirements.txt      # All dependencies
│
├── server/
│   ├── main.py           # FastAPI server
│   └── __init__.py
│
├── dashboard/
│   ├── main.py           # Textual TUI
│   └── __init__.py
│
├── client/               # Client scripts (source of truth)
│   ├── check-mentions-notify.py
│   ├── check-mentions-with-monitor.sh
│   ├── find-team-id.py
│   └── README.md
│
├── scripts/              # LaunchD integration
│   ├── check-slack-mentions.sh
│   └── check-slack-automated.sh
│
└── launchd/
    └── com.user.slack-mention-check.plist
```

## Usage

### Server Commands

```bash
# Start everything
./run.sh

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
# Manual test
cd ~/scripts/slack-assistant
./check-mentions-with-monitor.sh

# View logs
tail -f ~/Library/Logs/slack-monitor-client.log

# Disable automation
launchctl unload ~/Library/LaunchAgents/com.user.slack-monitor-client.plist
```

## Requirements

- **macOS** 13.0 (Ventura) or later
- **Python** 3.10+
- **Slack User Token** (xoxp-...) with scopes:
  - `channels:history`, `channels:read`
  - `groups:history`, `im:history`
  - `search:read`, `users:read`
- **ngrok** (optional, for remote access): `brew install ngrok`

## Configuration

### Server

Edit `~/.claude/mcp-servers.json` for Slack credentials (created by `setup.sh`):

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
    }
  }
}
```

### Client

**Setup automatically detects Team ID:**
- If you have MCP config (`~/.claude/mcp-servers.json`), it uses those credentials
- Otherwise, enter your Slack token and Team ID is auto-detected via API
- Fallback to manual entry if auto-detection fails

LaunchD agent runs hourly from 8 AM - 7 PM. To customize:

```bash
nano ~/Library/LaunchAgents/com.user.slack-monitor-client.plist
# Modify StartCalendarInterval hours

launchctl unload ~/Library/LaunchAgents/com.user.slack-monitor-client.plist
launchctl load ~/Library/LaunchAgents/com.user.slack-monitor-client.plist
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

### No mentions appearing
```bash
# Check Slack credentials
cat ~/.claude/mcp-servers.json

# Test client manually
cd ~/scripts/slack-assistant
./check-mentions-with-monitor.sh
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
# Already initialized with git
# Repository: https://github.com/wsaults/comms-assistant

# To push changes:
git add .
git commit -m "Your commit message"
git push origin main
```

`.gitignore` excludes:
- `venv/`, `.env` files
- Logs and temporary files
- Sensitive config (tokens, PIDs)

## Deployment

### Share with team:
1. Push to GitHub/GitLab
2. Team members clone and run `./setup-client.sh`
3. They point to your ngrok URL

### Multi-machine personal use:
1. Clone to each machine
2. Run `./run.sh` on main machine (server)
3. Run `./setup-client.sh` on other machines (clients)

## Cost

**$0/month** - Uses Slack SDK directly, no API charges

Optional ngrok free tier provides public URL (changes on restart).

## License

MIT License - Feel free to modify and distribute

## Support

- **Server logs:** `~/Library/Logs/slack-monitor-server.log`
- **Client logs:** `~/Library/Logs/slack-monitor-client.log`
- **Dashboard logs:** `textual.log` (in dashboard/ directory with `--dev` flag)

For detailed client documentation, see `client/README.md`
