#!/bin/bash

# --- CONFIGURATION ---
RESOURCES_DIR="../../resources"
DB_COMPOSE="db.compose.yml"
MINIO_COMPOSE="minio.compose.yml"
VLLM_COMPOSE="vllm.compose.yml"
DOWN_ON_EXIT=0

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --down-on-exit) DOWN_ON_EXIT=1 ;;
    esac
    shift
done

# Get absolute paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ABS_RESOURCES_DIR="$(cd "$SCRIPT_DIR/$RESOURCES_DIR" && pwd)"
ABS_BACKEND_DIR="$SCRIPT_DIR"

# Detect Python path (Linux vs Windows)
if [ -f "$ABS_BACKEND_DIR/.venv/bin/python" ]; then
    PYTHON_PATH="$ABS_BACKEND_DIR/.venv/bin/python"
elif [ -f "$ABS_BACKEND_DIR/.venv/Scripts/python.exe" ]; then
    PYTHON_PATH="$ABS_BACKEND_DIR/.venv/Scripts/python.exe"
else
    PYTHON_PATH="$(command -v python3 || command -v python)"
fi

echo "!!! AGGRESSIVE BACKEND RECOVERY & INFRA ORCHESTRATION STARTING !!!"
echo "Resources dir: $ABS_RESOURCES_DIR"
echo "Backend dir: $ABS_BACKEND_DIR"
echo "Python path: $PYTHON_PATH"

# 1. Force kill all stale python / backend instances
echo "[1/6] Terminating all stale Python / backend processes on port 8000..."
if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -Command "Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force" 2>/dev/null || true
else
    fuser -k 8000/tcp 2>/dev/null || true
    pkill -f "uvicorn.*app.main:app" 2>/dev/null || true
fi

# 2. Infrastructure Setup (Podman / Docker)
echo "[2/6] Orchestrating Database Infrastructure..."

CONTAINER_AVAILABLE=0
COMPOSE_CMD=""

if command -v podman-compose >/dev/null 2>&1; then
    CONTAINER_AVAILABLE=1
    COMPOSE_CMD="podman-compose"
elif podman compose version >/dev/null 2>&1; then
    CONTAINER_AVAILABLE=1
    COMPOSE_CMD="podman compose"
elif docker compose version >/dev/null 2>&1; then
    CONTAINER_AVAILABLE=1
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    CONTAINER_AVAILABLE=1
    COMPOSE_CMD="docker-compose"
fi

if [ "$CONTAINER_AVAILABLE" -eq 0 ]; then
    echo "WARNING: Neither Podman nor Docker is available. Assuming external PostgreSQL."
    SKIP_CONTAINER=1
fi

# Define cleanup function for trap
cleanup() {
    echo ""
    echo "!!! TERMINATION DETECTED !!!"
    if [ "$DOWN_ON_EXIT" -eq 1 ]; then
        echo "!!! TEARING DOWN INFRASTRUCTURE !!!"
        if [ -z "$SKIP_CONTAINER" ]; then
            cd "$ABS_RESOURCES_DIR" 2>/dev/null && $COMPOSE_CMD -f "$DB_COMPOSE" stop db 2>/dev/null || true
        fi
    else
        echo "!!! PRESERVING DATABASE CONTAINER (use --down-on-exit to teardown) !!!"
    fi
    echo "!!! CLEANUP COMPLETE. EXITING. !!!"
}

# Trap SIGINT (Ctrl+C), SIGTERM, and EXIT
trap cleanup SIGINT SIGTERM EXIT

if [ -z "$SKIP_CONTAINER" ]; then
    cd "$ABS_RESOURCES_DIR" || { echo "ERROR: Could not find resources directory: $ABS_RESOURCES_DIR"; exit 1; }
    echo " - Ensuring Database Service (nexus_db) is running..."
    $COMPOSE_CMD -f "$DB_COMPOSE" up -d db
fi

# 3. Wait for PostgreSQL Readiness
echo "[3/6] Waiting for PostgreSQL (Port 5432) to be ready..."

"$PYTHON_PATH" -c "
import socket
import time
import sys

def check_port(host, port, timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                print(f'\n[SUCCESS] PostgreSQL is reachable on {host}:{port}')
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            sys.stdout.write('.')
            sys.stdout.flush()
            time.sleep(1)
    print(f'\n[ERROR] Timeout waiting for PostgreSQL on {host}:{port}')
    return False

if not check_port('localhost', 5432):
    sys.exit(1)
" || { echo "CRITICAL: Database connection failed. Aborting startup."; exit 1; }

# 4. Initialize Database & Populate Seed Data
echo "[4/6] Verifying schemas, tables, and seeding data..."
cd "$ABS_BACKEND_DIR" || exit
"$PYTHON_PATH" scripts/populate_db.py

# 5. Final startup sequence
echo "[5/6] Waiting for memory and ports to stabilize..."
sleep 2

echo "[6/6] Initiating fresh backend start..."
cd "$ABS_BACKEND_DIR" || exit
"$PYTHON_PATH" main.py

echo "Backend stopped."
