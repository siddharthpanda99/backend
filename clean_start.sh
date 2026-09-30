#!/usr/bin/env bash

# --- CONFIGURATION ---
RESOURCES_DIR="../../resources"
DB_COMPOSE="db.compose.yml"
MINIO_COMPOSE="minio.compose.yml"
VLLM_COMPOSE="vllm.compose.yml"
DOWN_ON_EXIT=0

# `set -e` is deliberately NOT enabled. This script is a linear orchestration of steps
# that are individually allowed to fail on a developer machine — no container runtime,
# `populate_db.py` warning about an already-seeded DB, `pkill` finding nothing. With
# `-e` the script would abort at the first tolerated hiccup, which is a behaviour change
# for every existing invocation. Every step that genuinely must succeed checks its own
# exit status explicitly. `-u` and `pipefail` are on: they only catch real bugs
# (unexpanded variables, a swallowed failure in a pipeline).
set -uo pipefail

# Initialised here so `cleanup`'s `[ -z "$SKIP_CONTAINER" ]` is safe under `set -u`.
SKIP_CONTAINER=""

FEATURE_CONFIG=""
SHOW_FEATURE_CONFIG=0

usage() {
    cat <<'USAGE'
Usage: ./clean-start.sh [OPTIONS] [CONFIG_PATH]

Start the backend API server on :8000 with watchfiles reload, optionally driven by a
per-instance feature-flag config.

Options:
  -c, --config PATH   Per-instance feature config to apply (JSON).
      --show-config   Print the resolved config path + boot summary and exit.
  -h, --help          Show this help.

Precedence for the config (highest first):
  1. CONFIG_PATH / --config PATH
  2. $PLATFORM_FEATURE_CONFIG
  3. the shipped reference (resources/feature_flags.reference.json, every flag on)

With no arguments the reference is used, so an unchanged invocation behaves exactly as
before this feature existed. See docs/duplication-audit/FEATURE-CONFIG.md.
USAGE
}

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --down-on-exit) DOWN_ON_EXIT=1 ;;
        -c|--config)
            if [[ "$#" -lt 2 ]]; then
                echo "ERROR: $1 requires a path argument" >&2
                exit 2
            fi
            FEATURE_CONFIG="$2"
            shift
            ;;
        --config=*) FEATURE_CONFIG="${1#*=}" ;;
        --show-config) SHOW_FEATURE_CONFIG=1 ;;
        -h|--help) usage; exit 0 ;;
        -*) echo "ERROR: unknown option '$1'" >&2; usage >&2; exit 2 ;;
        *)
            if [[ -n "$FEATURE_CONFIG" ]]; then
                echo "ERROR: more than one config path given ('$FEATURE_CONFIG' and '$1')" >&2
                exit 2
            fi
            FEATURE_CONFIG="$1"
            ;;
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

# ── Feature config resolution ──────────────────────────────────────────────────
# Python is the single source of truth for the precedence chain (resolve_config_path),
# so this script never re-implements it. Run from the backend dir so `common_lib`
# resolves the same way it does at runtime.
resolve_config() {
    if [[ -n "$FEATURE_CONFIG" ]]; then
        # Resolve to an absolute path so the value handed to the server does not depend
        # on the working directory the server happens to start in.
        (cd "$(dirname "$FEATURE_CONFIG")" 2>/dev/null && printf '%s/%s\n' "$(pwd)" "$(basename "$FEATURE_CONFIG")") \
            || printf '%s\n' "$FEATURE_CONFIG"
        return
    fi
    (cd "$ABS_BACKEND_DIR" && "$PYTHON_PATH" -c \
        'from common_lib.modules.common.feature_config import resolve_config_path; print(resolve_config_path(None))' \
        2>/dev/null)
}

FEATURE_CONFIG_RESOLVED="$(resolve_config)"
if [[ -z "$FEATURE_CONFIG_RESOLVED" ]]; then
    echo "ERROR: could not resolve a feature config path (is common_lib importable?)" >&2
    exit 1
fi
export PLATFORM_FEATURE_CONFIG="$FEATURE_CONFIG_RESOLVED"

if [[ ! -f "$FEATURE_CONFIG_RESOLVED" ]]; then
    echo "ERROR: feature config not found: $FEATURE_CONFIG_RESOLVED" >&2
    echo "       create it by copying resources/feature_flags.reference.json," >&2
    echo "       or run './clean-start.sh' with no argument to use the shipped reference." >&2
    exit 1
fi

# Validate BEFORE launching. Structural problems abort; unknown flag paths are printed
# as warnings only (flag registration is import-time, so a document from a newer
# checkout legitimately names flags this build has not registered yet).
echo "Feature config: $FEATURE_CONFIG_RESOLVED"
if ! (cd "$ABS_BACKEND_DIR" && "$PYTHON_PATH" -m common_lib.modules.common.feature_config "$FEATURE_CONFIG_RESOLVED"); then
    echo "" >&2
    echo "CRITICAL: feature config is invalid — refusing to start." >&2
    echo "          Fix the file above, or unset PLATFORM_FEATURE_CONFIG to use the" >&2
    echo "          shipped reference. See docs/duplication-audit/FEATURE-CONFIG.md." >&2
    exit 1
fi

# One-line boot summary: path used, flags loaded, modules disabled.
FEATURE_SUMMARY="$(cd "$ABS_BACKEND_DIR" && "$PYTHON_PATH" -m common_lib.modules.common.feature_config \
    --summary "$FEATURE_CONFIG_RESOLVED" 2>/dev/null)" || FEATURE_SUMMARY=""
if [[ -n "$FEATURE_SUMMARY" ]]; then
    echo "Boot summary: $FEATURE_SUMMARY"
else
    echo "Boot summary: $FEATURE_CONFIG_RESOLVED (details unavailable — server will print its own)"
fi

if [[ "$SHOW_FEATURE_CONFIG" -eq 1 ]]; then
    echo "Resolved config: $FEATURE_CONFIG_RESOLVED"
    exit 0
fi

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