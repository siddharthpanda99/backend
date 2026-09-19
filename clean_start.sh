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

# Use Unix path directly for Git Bash
PYTHON_PATH="$ABS_BACKEND_DIR/.venv/Scripts/python.exe"

echo "!!! AGGRESSIVE BACKEND RECOVERY & INFRA ORCHESTRATION STARTING !!!"
echo "Resources dir: $ABS_RESOURCES_DIR"
echo "Backend dir: $ABS_BACKEND_DIR"
echo "Python path: $PYTHON_PATH"

# 1. Force kill all python instances
echo "[1/6] Terminating all stale Python processes..."
powershell.exe -Command "Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force" 2>/dev/null || true

# 2. Infrastructure Setup (Lifecycle Management)
echo "[2/6] Orchestrating Infrastructure (Docker)..."

# Check if Docker is running
DOCKER_AVAILABLE=0
if docker info >/dev/null 2>&1; then
    DOCKER_AVAILABLE=1
elif [ -f "/c/Program Files/Docker/Docker/Docker Desktop.exe" ]; then
    echo "WARNING: Docker is not running."
    echo "Attempting to start Docker Desktop..."
    
    # Try to start Docker Desktop
    "/c/Program Files/Docker/Docker/Docker Desktop.exe" >/dev/null 2>&1 &
    DOCKER_START_PID=$!
    
    # Wait for Docker to start (max 60 seconds)
    for i in $(seq 1 30); do
        sleep 2
        if docker info >/dev/null 2>&1; then
            echo "Docker Desktop started successfully."
            DOCKER_AVAILABLE=1
            break
        fi
        if [ $i -eq 30 ]; then
            echo "WARNING: Docker Desktop failed to start."
        fi
    done
fi

if [ "$DOCKER_AVAILABLE" -eq 0 ]; then
    echo "WARNING: Docker is not available. Skipping infrastructure setup."
    SKIP_DOCKER=1
fi

# Define cleanup function for trap
cleanup() {
    echo ""
    echo "!!! TERMINATION DETECTED !!!"
    if [ "$DOWN_ON_EXIT" -eq 1 ]; then
        echo "!!! TEARING DOWN INFRASTRUCTURE !!!"
        if [ -z "$SKIP_DOCKER" ] && docker info >/dev/null 2>&1; then
            cd "$ABS_RESOURCES_DIR" 2>/dev/null && docker compose -f "$DB_COMPOSE" -f "$MINIO_COMPOSE" -f "$VLLM_COMPOSE" down --remove-orphans 2>/dev/null || true
        fi
    else
        echo "!!! SKIPPING DOCKER TEARDOWN (use --down-on-exit to teardown) !!!"
    fi
    echo "!!! CLEANUP COMPLETE. EXITING. !!!"
}

# Trap SIGINT (Ctrl+C), SIGTERM, and EXIT
trap cleanup SIGINT SIGTERM EXIT

if [ -z "$SKIP_DOCKER" ]; then
    # Navigate to resources directory
    cd "$ABS_RESOURCES_DIR" || { echo "ERROR: Could not find resources directory: $ABS_RESOURCES_DIR"; exit 1; }

    echo " - Ensuring clean state (down)..."
    # Stop and remove containers (but preserve volumes for data persistence)
    docker compose -f "$DB_COMPOSE" -f "$MINIO_COMPOSE" -f "$VLLM_COMPOSE" down --remove-orphans 2>/dev/null || true

    echo " - Starting Core Services (DB, MinIO)..."
    docker compose -f "$DB_COMPOSE" -f "$MINIO_COMPOSE" up -d
    
    # Wait for containers to be fully up
    echo " - Waiting for containers to stabilize..."
    sleep 8

    # 3. Conditional vLLM Startup
    VLLM_MODEL=$(grep "vllm_model_file" config.ini 2>/dev/null | cut -d '=' -f2 | tr -d '[:space:]' | tr -d '\r')
    if [ "$VLLM_MODEL" != "none" ] && [ -n "$VLLM_MODEL" ]; then
        echo " - Detected configured model ($VLLM_MODEL). Starting vLLM..."
        docker compose -f "$VLLM_COMPOSE" up -d || echo "WARNING: vLLM failed to start. Continuing..."
    else
        echo " - vLLM skipped (vllm_model_file is 'none')."
    fi
else
    echo " - Skipping Docker (not running)"
fi

# 4. Wait for PostgreSQL Readiness
echo "[3/6] Waiting for PostgreSQL (Port 5432) to be ready..."

# Use python from venv
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

# 5. Final startup sequence
echo "[4/6] Waiting for memory and ports to stabilize..."
sleep 2

echo "[5/6] Initiating fresh backend start..."
cd "$ABS_BACKEND_DIR" || exit
"$PYTHON_PATH" main.py

# 6. Teardown happens automatically via trap on script exit
echo "[6/6] Backend stopped."
