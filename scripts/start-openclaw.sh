#!/bin/bash
# OpenClaw with GitHub Models Proxy - Startup Script
# This script starts both the GitHub proxy and OpenClaw gateway

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
OPENCLAW_DIR="${OPENCLAW_DIR:-$HOME/socialagent/openclaw}"
PROXY_PORT="${PROXY_PORT:-8000}"
GATEWAY_PORT="${GATEWAY_PORT:-18789}"
LOG_DIR="${LOG_DIR:-/tmp/openclaw}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create log directory
mkdir -p "$LOG_DIR"

echo -e "${BLUE}🦞 OpenClaw with GitHub Models Proxy${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to cleanup processes on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"
    
    # Kill proxy
    if [ -n "$PROXY_PID" ] && kill -0 "$PROXY_PID" 2>/dev/null; then
        kill "$PROXY_PID" 2>/dev/null
        echo -e "${GREEN}✓ GitHub proxy stopped${NC}"
    fi
    
    # Kill gateway
    if [ -n "$GATEWAY_PID" ] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
        kill "$GATEWAY_PID" 2>/dev/null
        echo -e "${GREEN}✓ OpenClaw gateway stopped${NC}"
    fi
    
    exit 0
}

# Set up cleanup trap
trap cleanup SIGINT SIGTERM EXIT

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command_exists python3; then
    echo -e "${RED}✗ Python 3 is required but not installed${NC}"
    exit 1
fi

if ! command_exists node; then
    echo -e "${RED}✗ Node.js is required but not installed${NC}"
    exit 1
fi

if ! command_exists pnpm; then
    echo -e "${RED}✗ pnpm is required but not installed${NC}"
    exit 1
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${RED}✗ GITHUB_TOKEN environment variable is not set${NC}"
    echo -e "${YELLOW}  Set it with: export GITHUB_TOKEN=your_token${NC}"
    exit 1
fi

if [ ! -d "$OPENCLAW_DIR" ]; then
    echo -e "${RED}✗ OpenClaw directory not found: $OPENCLAW_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All prerequisites met${NC}"
echo ""

# Kill any existing processes on required ports
echo -e "${YELLOW}Cleaning up existing processes...${NC}"

# Kill proxy port
if lsof -ti:$PROXY_PORT >/dev/null 2>&1; then
    lsof -ti:$PROXY_PORT | xargs kill -9 2>/dev/null || true
    echo -e "${GREEN}✓ Cleared port $PROXY_PORT${NC}"
    sleep 1
fi

# Kill gateway port and any moltbot processes
if lsof -ti:$GATEWAY_PORT >/dev/null 2>&1; then
    lsof -ti:$GATEWAY_PORT | xargs kill -9 2>/dev/null || true
    echo -e "${GREEN}✓ Cleared port $GATEWAY_PORT${NC}"
    sleep 1
fi

# Stop any launchd managed gateway
launchctl stop bot.molt.gateway 2>/dev/null || true
launchctl remove bot.molt.gateway 2>/dev/null || true

# Kill any lingering moltbot-gateway processes
pkill -9 -f "moltbot-gateway" 2>/dev/null || true

sleep 2
echo ""

# Find the proxy script
PROXY_SCRIPT=""
if [ -f "$SCRIPT_DIR/github_proxy.py" ]; then
    PROXY_SCRIPT="$SCRIPT_DIR/github_proxy.py"
elif [ -f "$OPENCLAW_DIR/scripts/github_proxy.py" ]; then
    PROXY_SCRIPT="$OPENCLAW_DIR/scripts/github_proxy.py"
else
    echo -e "${RED}✗ github_proxy.py not found${NC}"
    echo -e "${YELLOW}  Expected at: $SCRIPT_DIR/github_proxy.py${NC}"
    echo -e "${YELLOW}  Or at: $OPENCLAW_DIR/scripts/github_proxy.py${NC}"
    exit 1
fi

# Start the GitHub proxy
echo -e "${YELLOW}Starting GitHub Models proxy on port $PROXY_PORT...${NC}"
python3 "$PROXY_SCRIPT" > "$LOG_DIR/github-proxy.log" 2>&1 &
PROXY_PID=$!

# Wait for proxy to start
sleep 2

if ! kill -0 "$PROXY_PID" 2>/dev/null; then
    echo -e "${RED}✗ GitHub proxy failed to start${NC}"
    echo -e "${YELLOW}Check logs: $LOG_DIR/github-proxy.log${NC}"
    cat "$LOG_DIR/github-proxy.log"
    exit 1
fi

# Verify proxy is responding
if curl -s "http://localhost:$PROXY_PORT/health" | grep -q "ok"; then
    echo -e "${GREEN}✓ GitHub proxy running (PID: $PROXY_PID)${NC}"
else
    echo -e "${RED}✗ GitHub proxy not responding${NC}"
    exit 1
fi
echo ""

# Start the OpenClaw gateway
echo -e "${YELLOW}Starting OpenClaw gateway on port $GATEWAY_PORT...${NC}"
(
    cd "$OPENCLAW_DIR"
    OPENCLAW_TS_COMPILER=tsc pnpm openclaw gateway
) > "$LOG_DIR/openclaw-gateway.log" 2>&1 &
GATEWAY_PID=$!

# Wait for gateway to start
sleep 5

if ! kill -0 "$GATEWAY_PID" 2>/dev/null; then
    echo -e "${RED}✗ OpenClaw gateway failed to start${NC}"
    echo -e "${YELLOW}Check logs: $LOG_DIR/openclaw-gateway.log${NC}"
    tail -20 "$LOG_DIR/openclaw-gateway.log"
    exit 1
fi

# Verify gateway is listening
if lsof -i:$GATEWAY_PORT >/dev/null 2>&1; then
    echo -e "${GREEN}✓ OpenClaw gateway running (PID: $GATEWAY_PID)${NC}"
else
    echo -e "${RED}✗ OpenClaw gateway not listening on port $GATEWAY_PORT${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}🦞 All services started successfully!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo -e "Services:"
echo -e "  ${BLUE}GitHub Proxy:${NC}    http://localhost:$PROXY_PORT"
echo -e "  ${BLUE}OpenClaw Gateway:${NC} ws://127.0.0.1:$GATEWAY_PORT"
echo ""
echo -e "Logs:"
echo -e "  ${BLUE}Proxy:${NC}   $LOG_DIR/github-proxy.log"
echo -e "  ${BLUE}Gateway:${NC} $LOG_DIR/openclaw-gateway.log"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for gateway process (keeps script running)
wait $GATEWAY_PID
