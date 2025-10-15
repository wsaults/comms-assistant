# Teams Local Integration - Quick Reference

## Overview

Check Microsoft Teams mentions by reading directly from the local Teams database.
**No API access or organizational permissions required!**

## Setup (One-Time)

```bash
# Install the IndexedDB parser
pip3 install dfindexeddb

# Test it works
python3 client/check-teams-local.py --all
```

That's it! No webhooks, no ngrok, no Power Automate flows.

## Daily Use

### Check for Mentions

```bash
# Last hour (default)
python3 client/check-teams-local.py

# Last 24 hours
python3 client/check-teams-local.py --hours 24

# All mentions in database
python3 client/check-teams-local.py --all

# JSON output for integration
python3 client/check-teams-local.py --json
```

### Example Output

```
📖 Parsing Teams database (this may take 30-60 seconds)...
🔍 Extracting mentions and messages...
✅ Found 3 mentions
✅ Found 340 message threads

📬 Found 1 mention(s) in the last 24.0 hour(s):

1. [✓ Read] 2025-10-14 10:03:34
   From: Starr Frampton
   Type: channel
   Thread: 19:e6621eae3a894050bb6efc0ba2721672@thread.skype
   Message: Hi @General We have a new job opportunity...
```

## Monitoring Server Integration

### Start Monitoring Server

```bash
# Start server and dashboard
./scripts/run.sh

# Dashboard opens at http://localhost:3000
```

### Send Teams Mentions to Server

```bash
# Get mentions as JSON and send to server
python3 client/check-teams-local.py --json > /tmp/teams-mentions.json

# Or integrate directly in your scripts
python3 -c "
import subprocess
import json
import requests

result = subprocess.run(
    ['python3', 'client/check-teams-local.py', '--json'],
    capture_output=True,
    text=True
)

mentions = json.loads(result.stdout)
for mention in mentions:
    requests.post('http://localhost:8000/api/mention', json=mention)
"
```

## Performance

- **Parse time:** 30-60 seconds
- **Database size:** ~13MB (20,000+ records)
- **Messages scanned:** 340+ threads
- **Output:** Instant after parsing

## How It Works

### Database Location

```
~/Library/Containers/com.microsoft.teams2/Data/Library/Application Support/Microsoft/MSTeams/EBWebView/WV2Profile_tfw/IndexedDB/https_teams.microsoft.com_0.indexeddb.leveldb
```

### What's Extracted

- **Database 25:** Mention activities (when you were @mentioned)
- **Database 15:** Message content (actual text of mentions)
- **Database 13:** Conversation metadata (channels, threads)

The script matches mentions to their message content and outputs in a standard format.

## Advantages

✅ **No setup complexity** - Just one pip install
✅ **No external services** - No webhooks, ngrok, or cloud dependencies
✅ **Works offline** - Read directly from local files
✅ **Historical data** - Access all cached mentions
✅ **No permissions needed** - Your own local data

## Limitations

⚠️ **Only cached messages** - Limited to what Teams has stored locally (typically recent weeks)
⚠️ **Parse time** - Takes 30-60 seconds (not instant like webhooks)
⚠️ **Poll-based** - Need to run periodically, not real-time push
⚠️ **Teams v2 only** - Requires New Teams (most users have this)

## Automation

### Run Periodically with LaunchD

Create a LaunchD agent to check every hour:

```bash
cat > ~/Library/LaunchAgents/com.user.teams-local-check.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.teams-local-check</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/YOUR_USERNAME/Downloads/slack-mentions-assistant/client/check-teams-local.py</string>
        <string>--hours</string>
        <string>1</string>
    </array>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/Library/Logs/teams-local-check.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/Library/Logs/teams-local-check-error.log</string>
</dict>
</plist>
EOF

# Replace YOUR_USERNAME with your actual username
# Then load it:
launchctl load ~/Library/LaunchAgents/com.user.teams-local-check.plist
```

## Troubleshooting

### "Database not found"

```bash
# Check Teams is installed
ls "/Applications/Microsoft Teams.app"

# Check database exists
ls ~/Library/Containers/com.microsoft.teams2/Data/Library/Application\ Support/Microsoft/MSTeams/EBWebView/WV2Profile_tfw/IndexedDB/
```

### "dfindexeddb not found"

```bash
# Install it
pip3 install dfindexeddb

# Verify
~/Library/Python/3.9/bin/dfindexeddb --help
```

### "No mentions found"

- Try `--all` flag to see all historical mentions
- Check if you've been mentioned recently in Teams
- Verify Teams has been running and syncing

### Parse takes too long

- Normal: 30-60 seconds
- Large databases may take up to 2 minutes
- Consider caching results if running frequently

## File Locations

```
Project:
├── client/check-teams-local.py          # Main parser script
├── TEAMS_LOCAL_ACCESS.md                # Detailed technical docs
└── QUICK_REFERENCE.md                   # This file

Logs (if using LaunchD):
└── ~/Library/Logs/teams-local-check.log

Database:
└── ~/Library/Containers/com.microsoft.teams2/.../IndexedDB/https_teams.microsoft.com_0.indexeddb.leveldb
```

## Key Facts

- **Parse time:** 30-60 seconds
- **No external dependencies** (except dfindexeddb)
- **100% local operation**
- **Read-only** (never modifies Teams database)

## Next Steps

1. **Read full docs:** `cat TEAMS_LOCAL_ACCESS.md`
2. **Test it:** `python3 client/check-teams-local.py --all`
3. **Set up automation:** Create LaunchD agent for periodic checks
4. **Integrate with monitoring:** Send results to dashboard

## Help

For detailed technical information:
```bash
cat TEAMS_LOCAL_ACCESS.md
```

For script help:
```bash
python3 client/check-teams-local.py --help
```
