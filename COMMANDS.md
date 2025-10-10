# Quick Command Reference

## 🚀 Start & Stop

```bash
# Start server (and try to auto-launch dashboard)
./start-monitor.sh

# If auto-launch fails, open a NEW TERMINAL and run:
./run-dashboard.sh

# Stop server
./stop-monitor.sh
```

## 🧪 Testing

```bash
# Test with sample data
source venv/bin/activate && python test_client.py

# Test with real Slack data
source venv/bin/activate && cd client && python mention_reporter.py

# Test automation script
~/scripts/slack-assistant/check-slack-automated.sh
```

## 📊 Monitoring

```bash
# View server logs (live)
tail -f ~/Library/Logs/slack-monitor-server.log

# View automation logs (live)
tail -f ~/Library/Logs/slack-mentions.log

# Check server status
curl http://localhost:8000/ | python3 -m json.tool

# Check server health
curl http://localhost:8000/health
```

## 🔧 Manual Control

```bash
# Start server only
source venv/bin/activate
uvicorn server.main:app --host 0.0.0.0 --port 8000

# Start dashboard only
source venv/bin/activate
cd dashboard && python main.py

# Kill server on port 8000
kill $(lsof -ti:8000)
```

## 📋 LaunchD Management

```bash
# Check if automation is loaded
launchctl list | grep slack-mention

# Manually trigger automation
launchctl start com.user.slack-mention-check

# View launchd logs
log show --predicate 'subsystem == "com.apple.launchd"' --last 1h | grep slack
```

## 📚 Documentation

- `LAUNCHER_GUIDE.md` - Launcher reference
- `QUICK_START.md` - Getting started
- `MONITOR_README.md` - Full documentation
- `CLAUDE.md` - Project overview
- `README.md` - Original automation
