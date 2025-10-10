# Slack Monitor - Client Scripts

These scripts run on **client machines** to report Slack mentions to the centralized dashboard.

## Files

| File | Purpose |
|------|---------|
| `setup-client.sh` | Interactive setup for new client machines |
| `check-mentions-notify.py` | Reports Slack mentions to the server |
| `check-mentions-with-monitor.sh` | Wrapper that uses the correct venv |
| `find-team-id.py` | Helper to find your Slack Team ID |

## Quick Setup (New Client Machine)

```bash
# 1. Copy these files to the new machine
scp ~/scripts/slack-assistant/*.py ~/scripts/slack-assistant/*.sh user@newmachine:~/scripts/slack-assistant/

# 2. On the new machine, run setup
cd ~/scripts/slack-assistant
./setup-client.sh
```

The setup script will:
- Install dependencies (slack-sdk, httpx)
- Ask for the server URL (ngrok or local IP)
- Optionally use Slack credentials from ~/.claude/mcp-servers.json
- Set up hourly automated checks (8 AM - 7 PM)

## Manual Testing

Test the client manually before setting up automation:

```bash
cd ~/scripts/slack-assistant
./check-mentions-with-monitor.sh
```

This should:
1. Check Slack for mentions
2. Report them to the server
3. Show macOS notifications

## View Logs

```bash
# Live tail
tail -f ~/Library/Logs/slack-monitor-client.log

# Last 50 lines
tail -50 ~/Library/Logs/slack-monitor-client.log
```

## Server Setup

The centralized server/dashboard runs on **one machine only**:

```bash
# On the main monitoring machine
cd slack-mentions-assistant  # or comms-assistant if cloned from GitHub
./setup.sh   # One-time setup
./run.sh     # Start server, ngrok, and dashboard
```

## How It Works

```
┌─────────────────┐           ┌──────────────────┐
│  Client Machine │           │  Server Machine  │
│                 │           │                  │
│  check-mentions │──HTTP────▶│  FastAPI Server  │
│  -notify.py     │           │  (port 8000)     │
│                 │           │        │         │
│  Checks Slack   │           │        ▼         │
│  every hour     │           │  Textual Dashboard
└─────────────────┘           │  (shows mentions) │
                              └──────────────────┘
                                       │
                              ngrok (optional)
                                       │
                         https://abc123.ngrok.io
```

## Troubleshooting

### "Cannot reach server"
- Make sure server is running: `./run.sh`
- Check server URL is correct
- Verify firewall allows connections
- Test: `curl http://SERVER_URL/health`

### "slack_sdk not installed"
```bash
pip3 install --break-system-packages slack-sdk httpx
```

### No notifications appearing
1. Grant notification permissions: System Settings → Notifications → Script Editor
2. Test manually: `./check-mentions-with-monitor.sh`
3. Check logs: `tail ~/Library/Logs/slack-monitor-client.log`

## Uninstall

```bash
# Stop automation
launchctl unload ~/Library/LaunchAgents/com.user.slack-monitor-client.plist
rm ~/Library/LaunchAgents/com.user.slack-monitor-client.plist

# Remove scripts
rm -rf ~/scripts/slack-assistant

# Remove logs
rm ~/Library/Logs/slack-monitor-client*.log
rm ~/.slack-mentions-state
```
