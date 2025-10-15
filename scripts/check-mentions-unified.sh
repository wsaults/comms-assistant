#!/bin/bash

# Unified Mentions Checker Wrapper
# Runs from the project directory - no installation/copying needed

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Set environment variables (config file takes priority, these are fallbacks)
export MONITOR_SERVER_URL="${MONITOR_SERVER_URL:-http://localhost:8000}"
export CLIENT_ID="${CLIENT_ID:-$(hostname)}"

# Try to use project venv if available, otherwise use system Python
if [ -d "$PROJECT_DIR/venv" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
    python3 "$SCRIPT_DIR/check-messages.py"
    deactivate
else
    python3 "$SCRIPT_DIR/check-messages.py"
fi
