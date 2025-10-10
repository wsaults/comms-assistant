#!/bin/bash

# Slack Monitor Stop Script
# Cleanly shuts down the monitoring server

PROJECT_DIR="/Users/will/Projects/Saults/slack-mentions-assistant"
cd "$PROJECT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║             Slack Monitor - Shutting Down                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if server is running
if ! lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Server is not running${NC}"
    exit 0
fi

# Stop server using PID file
if [ -f /tmp/slack-monitor-server.pid ]; then
    PID=$(cat /tmp/slack-monitor-server.pid)
    echo -e "${YELLOW}→ Stopping server (PID: $PID)...${NC}"

    if kill -0 $PID 2>/dev/null; then
        kill $PID

        # Wait for graceful shutdown
        for i in {1..5}; do
            if ! kill -0 $PID 2>/dev/null; then
                break
            fi
            sleep 1
        done

        # Force kill if still running
        if kill -0 $PID 2>/dev/null; then
            echo -e "${YELLOW}  Force killing...${NC}"
            kill -9 $PID
        fi
    fi

    rm /tmp/slack-monitor-server.pid
fi

# Fallback: kill any process on port 8000
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}→ Killing process on port 8000...${NC}"
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
fi

# Wait a moment
sleep 1

# Verify server is stopped
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}✗ Failed to stop server${NC}"
    exit 1
else
    echo -e "${GREEN}✓ Server stopped${NC}"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                  Monitor Stopped                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Note: Dashboard window is still open - close it manually"
echo ""
