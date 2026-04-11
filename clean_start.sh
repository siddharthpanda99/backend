#!/bin/bash

# --- CONFIGURATION ---
RESOURCES_DIR="../../resources"
DB_COMPOSE="db.compose.yml"
MINIO_COMPOSE="minio.compose.yml"
VLLM_COMPOSE="vllm.compose.yml"
PYTHON_CMD="./.venv/Scripts/python.exe"

# Absolute paths for reliability in trap
ABS_RESOURCES_DIR="c:/Users/91797/Documents/Dev/JS/Monorepo/resources"

echo "!!! AGGRESSIVE BACKEND RECOVERY & INFRA ORCHESTRATION STARTING !!!"

# 1. Force kill all python instances
echo "[1/6] Terminating all stale Python processes..."
taskkill.exe -F -IM python.exe -T 2>/dev/null || true

# 2. Infrastructure Setup (Lifecycle Management)
echo "[2/6] Orchestrating Infrastructure (Docker)..."

# Define cleanup function for trap
cleanup() {
    echo ""
    echo "!!! TERMINATION DETECTED - TEARING DOWN INFRASTRUCTURE !!!"
    # Navigate to resources directory using absolute path to ensure reliability
    cd "$ABS_RESOURCES_DIR" || exit
    docker compose -f "$DB_COMPOSE" -f "$MINIO_COMPOSE" -f "$VLLM_COMPOSE" down
    echo "!!! CLEANUP COMPLETE. EXITING. !!!"
}

# Trap SIGINT (Ctrl+C), SIGTERM, and EXIT
trap cleanup SIGINT SIGTERM EXIT

# Navigate to resources directory
cd "$RESOURCES_DIR" || { echo "ERROR: Could not find resources directory"; exit 1; }

echo " - Ensuring clean state (down)..."
# Explicitly stop and REMOVE any rogue containers that might conflict (especially minio)
docker stop minio monorepo-minio-1 nexus_db nexus_pgadmin 2>/dev/null || true
docker rm -f minio monorepo-minio-1 nexus_db nexus_pgadmin 2>/dev/null || true
docker compose -f "$DB_COMPOSE" -f "$MINIO_COMPOSE" -f "$VLLM_COMPOSE" down

echo " - Starting Core Services (DB, MinIO)..."
docker compose -f "$DB_COMPOSE" -f "$MINIO_COMPOSE" up -d

# 3. Conditional vLLM Startup
VLLM_MODEL=$(grep "vllm_model_file" config.ini | cut -d '=' -f2 | tr -d '[:space:]' | tr -d '\r')
if [ "$VLLM_MODEL" != "none" ] && [ -n "$VLLM_MODEL" ]; then
    echo " - Detected configured model ($VLLM_MODEL). Starting vLLM..."
    docker compose -f "$VLLM_COMPOSE" up -d || echo "WARNING: vLLM failed to start. Continuing..."
else
    echo " - vLLM skipped (vllm_model_file is 'none')."
fi

# 4. Wait for PostgreSQL Readiness
echo "[3/6] Waiting for PostgreSQL (Port 5432) to be ready..."
cd "../Backend Monorepo/Backend" || exit

$PYTHON_CMD -c "
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
# Use EXEC to hand over control to python, but then the trap won't fire on script exit if python exits?
# No, we want the script to wait for python.
$PYTHON_CMD main.py

# 6. Teardown happens automatically via trap on script exit
echo "[6/6] Backend stopped."
