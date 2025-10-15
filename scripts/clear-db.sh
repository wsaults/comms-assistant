#!/bin/bash

# Clear Slack Monitor Database
# Removes all mentions and activity data from the database

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Slack Monitor - Clear Database                     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if server is running
if ! curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo -e "${RED}✗ Server is not running${NC}"
    echo "  Start the server first: ./run.sh"
    exit 1
fi

echo -e "${YELLOW}This will delete all mentions and activity data from the database.${NC}"
echo -e "${YELLOW}Are you sure? (y/N)${NC}"
read -r response

if [[ ! "$response" =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Cancelled${NC}"
    exit 0
fi

echo ""
echo -e "${YELLOW}→ Clearing database...${NC}"

CLEAR_RESPONSE=$(curl -s -X DELETE "http://localhost:8000/api/debug/clear")

# Parse response
STATUS=$(echo "$CLEAR_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('status', 'unknown'))" 2>/dev/null)

if [ "$STATUS" = "success" ]; then
    echo -e "${GREEN}✓ Database cleared successfully${NC}"
    echo ""

    MENTIONS=$(echo "$CLEAR_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('cleared', {}).get('mentions', 0))" 2>/dev/null)
    ACTIVITY=$(echo "$CLEAR_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('cleared', {}).get('channel_activity', 0))" 2>/dev/null)

    echo "  Mentions removed: $MENTIONS"
    echo "  Activity records removed: $ACTIVITY"
    echo ""
    echo -e "${GREEN}✓ Database is now empty${NC}"
else
    echo -e "${RED}✗ Failed to clear database${NC}"
    echo "  Response: $CLEAR_RESPONSE"
    exit 1
fi
