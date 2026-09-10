#!/usr/bin/env bash
# ==============================================================================
# SIH26158: Tactical Drone Video to 3D Model Generation System
# Single-Command Launcher for Backend (FastAPI) & Frontend (Next.js)
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for Tactical Terminal Output
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo -e "${CYAN}${BOLD}"
echo "=============================================================================="
echo "    NTRO SIH26158: TACTICAL DRONE 3D RECONSTRUCTION PLATFORM"
echo "=============================================================================="
echo -e "${NC}"

# 1. Clean up any previous dangling processes on ports 8000 and 3000
echo -e "${YELLOW}[*] Checking port availability (8000, 3000)...${NC}"
for PORT in 8000 3000; do
    PID=$(lsof -ti :"$PORT" 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo -e "${YELLOW}[!] Port $PORT is occupied by PID(s): $PID. Cleaning up...${NC}"
        kill -15 $PID 2>/dev/null || kill -9 $PID 2>/dev/null || true
        sleep 1
    fi
done

# 2. Verify Python environment
echo -e "${CYAN}[*] Verifying Python backend dependencies...${NC}"
if [ -d "$SCRIPT_DIR/.venv" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
    PYTHON_BIN="python"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
else
    echo -e "${RED}[ERROR] python3 could not be found. Please install Python 3.10+.${NC}"
    exit 1
fi

# Ensure essential python packages are importable
"$PYTHON_BIN" -c "import fastapi, uvicorn, trimesh" 2>/dev/null || {
    echo -e "${YELLOW}[!] Installing / checking backend python requirements...${NC}"
    "$PYTHON_BIN" -m pip install -r backend/requirements.txt
}

# 3. Verify Frontend package manager
FRONTEND_DIR="$SCRIPT_DIR/compute-the-platform-to-build-and-ship-ai-agents"
if [ ! -d "$FRONTEND_DIR" ]; then
    echo -e "${RED}[ERROR] Frontend directory not found at: $FRONTEND_DIR${NC}"
    exit 1
fi

if command -v pnpm &>/dev/null; then
    PM_CMD="pnpm"
elif command -v npm &>/dev/null; then
    PM_CMD="npm"
else
    echo -e "${RED}[ERROR] Neither pnpm nor npm was found. Please install Node.js & pnpm/npm.${NC}"
    exit 1
fi

# 4. Prepare log directory
LOG_DIR="$SCRIPT_DIR/.logs"
mkdir -p "$LOG_DIR"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

# 5. Trap cleanup on exit / interrupt
cleanup() {
    echo ""
    echo -e "${YELLOW}[*] Shutting down SIH26158 services...${NC}"
    if [ -n "${BACKEND_PID:-}" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill -15 "$BACKEND_PID" 2>/dev/null || kill -9 "$BACKEND_PID" 2>/dev/null
    fi
    if [ -n "${FRONTEND_PID:-}" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill -15 "$FRONTEND_PID" 2>/dev/null || kill -9 "$FRONTEND_PID" 2>/dev/null
    fi
    echo -e "${GREEN}[✓] All services cleanly stopped.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 6. Start FastAPI Backend
echo -e "${CYAN}[*] Starting FastAPI Backend on http://0.0.0.0:8000 ...${NC}"
$PYTHON_BIN -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

# Wait for backend health check
BACKEND_READY=false
for i in {1..30}; do
    if curl -s "http://127.0.0.1:8000/healthz" | grep -q "status"; then
        BACKEND_READY=true
        break
    fi
    sleep 0.5
done

if [ "$BACKEND_READY" = true ]; then
    echo -e "${GREEN}[✓] Backend operational: http://localhost:8000${NC}"
    echo -e "${GREEN}    API Docs: http://localhost:8000/docs${NC}"
else
    echo -e "${RED}[!] Backend health check timed out. Check logs at: $BACKEND_LOG${NC}"
fi

# 7. Start Next.js Frontend
echo -e "${CYAN}[*] Starting Next.js Command Center on http://localhost:3000 using $PM_CMD ...${NC}"
(
    cd "$FRONTEND_DIR"
    $PM_CMD run dev > "$FRONTEND_LOG" 2>&1
) &
FRONTEND_PID=$!

# Wait for frontend readiness
FRONTEND_READY=false
for i in {1..30}; do
    if curl -s -I "http://127.0.0.1:3000" 2>/dev/null | grep -q "HTTP"; then
        FRONTEND_READY=true
        break
    fi
    sleep 0.5
done

if [ "$FRONTEND_READY" = true ]; then
    echo -e "${GREEN}[✓] Tactical Command Center operational: http://localhost:3000${NC}"
else
    echo -e "${YELLOW}[!] Frontend compiling... Accessible shortly at http://localhost:3000${NC}"
fi

echo -e "${CYAN}${BOLD}"
echo "=============================================================================="
echo -e "${GREEN}  ✓ FASTAPI BACKEND:     http://localhost:8000"
echo -e "${GREEN}  ✓ SWAGGER API DOCS:    http://localhost:8000/docs"
echo -e "${GREEN}  ✓ COMMAND CENTER UI:   http://localhost:3000"
echo -e "${CYAN}=============================================================================="
echo -e "${YELLOW}Logs:${NC}"
echo -e "  Backend:  tail -f $BACKEND_LOG"
echo -e "  Frontend: tail -f $FRONTEND_LOG"
echo -e "${YELLOW}Press [Ctrl+C] to gracefully stop both services.${NC}"
echo "=============================================================================="
echo -e "${NC}"

# Keep script running and forward logs or wait
wait
