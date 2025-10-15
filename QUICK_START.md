# Quick Start Guide - Slack Monitor Dashboard

## What Was Built

You now have a complete **Slack monitoring system** with:

### 1. **FastAPI Server** (`server/main.py`)
   - Receives mention reports from clients
   - Stores data in memory (up to 1000 mentions)
   - Broadcasts updates via WebSocket
   - REST API for data access

### 2. **Python Client** (`client/mention_reporter.py`)
   - Uses Claude Code CLI to check Slack mentions
   - Extracts structured data (mentions, stats, conversations)
   - Reports to monitoring server
   - Works with your existing MCP Slack setup

### 3. **Textual Dashboard** (`dashboard/main.py`)
   - Beautiful terminal UI with reactive widgets
   - Real-time updates via WebSocket
   - Shows stats, mentions, charts, and clients
   - Keyboard shortcuts: `q` to quit, `r` to refresh

## File Structure

```
slack-mentions-assistant/
├── server/                  # FastAPI monitoring server
│   ├── main.py             # Server implementation
│   └── requirements.txt    # Server dependencies
├── client/                  # Client reporter
│   ├── mention_reporter.py # Claude Code integration
│   ├── .env                # Client configuration
│   └── requirements.txt    # Client dependencies
├── dashboard/               # Textual TUI dashboard
│   ├── main.py             # Dashboard implementation
│   ├── .env                # Dashboard configuration
│   └── requirements.txt    # Dashboard dependencies
├── requirements.txt         # All dependencies
├── setup.sh                # Installation script
└── test_client.py          # Integration test
```

## How to Use

### First Time Setup (Already Done!)

```bash
./setup.sh  # Creates venv and installs all dependencies
```

### Running the System (Easy Way!) ⭐

#### Launch Everything at Once

```bash
./start-monitor.sh
```

This will:
- Start the FastAPI server in the background
- Open the dashboard in a new Terminal window
- Show you the server status

#### Stop Everything

```bash
./stop-monitor.sh
```

### Running the System (Manual Way)

#### Terminal 1: Start the Server

```bash
source venv/bin/activate
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Server will run at `http://localhost:8000`

#### Terminal 2: Run the Dashboard

```bash
source venv/bin/activate
cd dashboard
python main.py
```

You'll see a beautiful TUI with:
- Stats overview (top left)
- Connected clients (bottom left)
- Recent mentions (top right)
- Messages per hour chart (bottom right)
- Connection status bar (bottom)

Press `q` to quit, `r` to refresh

#### Terminal 3: Test the Client

```bash
# Quick test with sample data
source venv/bin/activate
python test_client.py
```

Or run the real client:

```bash
source venv/bin/activate
cd client
python mention_reporter.py
```

This will:
1. Use Claude Code CLI to check Slack mentions
2. Parse the response into structured JSON
3. Send mentions and stats to the server
4. Dashboard will update in real-time!

## Integration with LaunchD ✅

The system integrates with LaunchD for automated hourly checks using Python scripts in `~/scripts/`.

When your LaunchD automation runs (configured via setup-client.sh), it will:
1. Run `check-messages.py` to check configured platforms (Slack, Teams, etc.)
2. Send data to the monitoring server
3. Show updates in the dashboard in real-time
4. Send macOS notifications for unread mentions

Key scripts:
- `check-messages.py` - Unified checker for all platforms (mentions + channels)
- `check-mentions-notify.py` - Slack-specific checker (single workspace)
- `check-multi-slack.py` - Slack checker for multiple workspaces
- `check-teams-local.py` - Teams local database checker (no API)
- `check-teams-mentions.py` - Teams MCP-based checker

LaunchD management:
```bash
# Check if loaded
launchctl list | grep mentions

# Load/unload
launchctl load ~/Library/LaunchAgents/com.user.mentions-assistant.plist
launchctl unload ~/Library/LaunchAgents/com.user.mentions-assistant.plist

# Trigger manually
launchctl start com.user.mentions-assistant
```

## Testing Right Now

### 1. Start the server:

```bash
source venv/bin/activate
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

### 2. In another terminal, run the test:

```bash
source venv/bin/activate
python test_client.py
```

You should see:
```
============================================================
Testing Slack Monitor Client-Server Integration
============================================================
Server: http://localhost:8000

1. Testing server health...
   ✓ Server is healthy

2. Posting sample mention...
   ✓ Mention posted successfully

...

============================================================
✅ All tests passed!
============================================================
```

### 3. In a third terminal, run the dashboard:

```bash
source venv/bin/activate
cd dashboard
python main.py
```

You'll see the test data appear in the dashboard!

## API Endpoints

- `GET /health` - Server health check
- `GET /` - Server status and stats
- `POST /api/mention` - Report a mention
- `POST /api/stats` - Report client stats
- `POST /api/conversation` - Report conversation summary
- `GET /api/mentions?hours=24` - Get recent mentions
- `GET /api/mentions/unread` - Get unread mentions
- `GET /api/stats` - Get all client stats
- `GET /api/messages-per-hour` - Get hourly distribution
- `WebSocket /ws` - Real-time updates

## Dashboard Features

### Stats Widget (Top Left)
- 🔔 Unread mentions count
- 💬 Messages in last hour
- 📺 Active channels
- 💻 Connected clients
- 📝 Total mentions
- 🕐 Last update time

### Mentions Table (Top Right)
- Last 10 mentions across all clients
- Shows: time, channel, user, message preview
- Status indicators:
  - ✓ = Responded
  - ? = Question
  - • = Unread

### Messages Chart (Bottom Right)
- 24-hour bar chart
- Hourly message distribution
- Aggregated across all clients

### Clients Panel (Bottom Left)
- All connected clients
- Per-client unread count
- Per-client hourly messages

### Connection Status (Bottom)
- Real-time connection status
- Green = Connected and receiving live updates
- Yellow = Reconnecting
- Red = Error

## Next Steps

1. **Test the client with real Slack data:**
   ```bash
   cd client
   python mention_reporter.py
   ```

2. **Run the dashboard to see real-time updates:**
   ```bash
   cd dashboard
   python main.py
   ```

3. **Integrate with LaunchD** to run hourly checks automatically

4. **Optional enhancements:**
   - Add authentication to server
   - Persist data to SQLite
   - Email/SMS alerts for urgent mentions
   - Deploy server to always-on machine

## Troubleshooting

### Server won't start
```bash
# Check if port 8000 is in use
lsof -i :8000

# Use different port
uvicorn server.main:app --host 0.0.0.0 --port 8080
```

### Dashboard can't connect
```bash
# Test server
curl http://localhost:8000/health

# Should return: {"status":"healthy"}
```

### Client errors
```bash
# Verify Claude Code is available
which claude

# Test MCP connection
claude code "list my slack channels"
```

## Documentation

- **MONITOR_README.md** - Comprehensive monitoring system documentation
- **README.md** - Original shell script automation docs
- **CLAUDE.md** - Project overview for Claude Code
- **SETUP.md** - Original setup instructions

## What Makes This Special

✨ **Key Features:**
- Uses **Textual** (not Rich) for a modern, reactive TUI
- Real-time WebSocket updates - no polling needed
- Multi-client support - monitor multiple machines
- Zero API costs - uses Claude Code subscription
- Beautiful terminal UI with CSS-like styling
- Integrates seamlessly with existing MCP setup

🎯 **Perfect For:**
- Monitoring Slack mentions from multiple machines
- Tracking response metrics
- Visualizing activity patterns
- Centralizing Slack notifications

Enjoy your new Slack monitoring dashboard! 🎉
