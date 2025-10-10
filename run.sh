#!/bin/bash

# Slack Monitor - Unified Launcher
# Starts server, ngrok, and dashboard in one command

set -e

PROJECT_DIR="/Users/will/Projects/Saults/slack-mentions-assistant"
cd "$PROJECT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           Slack Monitor - Starting Everything               ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}✗ Virtual environment not found${NC}"
    echo "  Run ./setup.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# ============================================================================
# START SERVER
# ============================================================================

# Check if server is already running
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Server already running on port 8000${NC}"
    read -p "  Kill existing server and restart? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}→ Stopping existing server...${NC}"
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
        sleep 2
    else
        echo -e "${GREEN}✓ Using existing server${NC}"
    fi
fi

# Start server in background if not running
if ! lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}→ Starting FastAPI server...${NC}"

    # Start server with output to log files
    nohup uvicorn server.main:app --host 0.0.0.0 --port 8000 \
        > "$HOME/Library/Logs/slack-monitor-server.log" 2>&1 &

    SERVER_PID=$!
    echo "  PID: $SERVER_PID"

    # Save PID for later
    echo $SERVER_PID > /tmp/slack-monitor-server.pid

    # Wait for server to be ready
    echo -e "${YELLOW}→ Waiting for server to start...${NC}"
    for i in {1..10}; do
        if curl -s http://localhost:8000/health >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Server is ready${NC}"
            break
        fi
        sleep 1
    done

    if ! curl -s http://localhost:8000/health >/dev/null 2>&1; then
        echo -e "${RED}✗ Server failed to start${NC}"
        echo "  Check logs: tail -f $HOME/Library/Logs/slack-monitor-server.log"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Server is running${NC}"
fi

# Get server status
SERVER_STATUS=$(curl -s http://localhost:8000/ | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Clients: {len(data[\"active_clients\"])}, Mentions: {data[\"total_mentions\"]}')" 2>/dev/null || echo "Status unavailable")
echo "  $SERVER_STATUS"
echo ""

# ============================================================================
# START NGROK
# ============================================================================

# Check and start ngrok if needed
if command -v ngrok >/dev/null 2>&1; then
    echo -e "${YELLOW}→ Checking ngrok status...${NC}"

    # Check if ngrok is already running
    if curl -s http://localhost:4040/api/tunnels >/dev/null 2>&1; then
        NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; data=json.load(sys.stdin); tunnels=data.get('tunnels',[]); print(tunnels[0]['public_url'] if tunnels else '')" 2>/dev/null)
        if [ -n "$NGROK_URL" ]; then
            echo -e "${GREEN}✓ ngrok is already running${NC}"
            echo -e "  Public URL: ${BLUE}$NGROK_URL${NC}"
        fi
    else
        # Start ngrok
        echo -e "${YELLOW}→ Starting ngrok tunnel...${NC}"
        nohup ngrok http 8000 --log=stdout > /tmp/ngrok.log 2>&1 &
        NGROK_PID=$!
        echo "  PID: $NGROK_PID"

        # Wait for ngrok to initialize
        echo -e "${YELLOW}→ Waiting for ngrok to start...${NC}"
        sleep 3

        # Verify ngrok started
        if curl -s http://localhost:4040/api/tunnels >/dev/null 2>&1; then
            NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; data=json.load(sys.stdin); tunnels=data.get('tunnels',[]); print(tunnels[0]['public_url'] if tunnels else '')" 2>/dev/null)
            if [ -n "$NGROK_URL" ]; then
                echo -e "${GREEN}✓ ngrok tunnel started${NC}"
                echo -e "  Public URL: ${BLUE}$NGROK_URL${NC}"
            fi
        else
            echo -e "${YELLOW}⚠ ngrok may not have started properly${NC}"
            echo "  Check logs: tail -f /tmp/ngrok.log"
        fi
    fi
else
    echo -e "${YELLOW}⚠ ngrok not installed (optional)${NC}"
    echo "  Install: brew install ngrok"
fi
echo ""

# ============================================================================
# LAUNCH DASHBOARD
# ============================================================================

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              🎉 Launching Dashboard...                       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Controls:${NC}"
echo "  Press 'q' to quit dashboard"
echo "  Press 'r' to refresh data"
echo ""
echo -e "${YELLOW}Note: Server will keep running in background after you quit${NC}"
echo -e "${YELLOW}      Use ./stop.sh to stop the server${NC}"
echo ""

# Small delay so user can read the messages
sleep 2

# Run dashboard in foreground
cd dashboard
python main.py
