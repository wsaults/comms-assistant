#!/bin/bash

# Wrapper for check-mentions-notify.py that uses monitoring project's venv
# This provides access to httpx for reporting to the monitoring server

PROJECT_DIR="/Users/will/Projects/Saults/slack-mentions-assistant"

# Check if virtual environment exists
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "ERROR: Virtual environment not found at $PROJECT_DIR/venv"
    echo "Run $PROJECT_DIR/setup.sh first"
    exit 1
fi

# Activate virtual environment
source "$PROJECT_DIR/venv/bin/activate"

# Set monitoring server URL
export MONITOR_SERVER_URL="http://localhost:8000"
export CLIENT_ID="$(hostname)"

# Run the Python script
python3 /Users/will/scripts/slack-assistant/check-mentions-notify.py

# Deactivate when done
deactivate
