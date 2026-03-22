#!/bin/bash

echo "!!! AGGRESSIVE BACKEND RECOVERY STARTING !!!"

# 1. Force kill all python instances
echo "[1/3] Terminating all stale Python processes..."
taskkill.exe -F -IM python.exe -T || true

# 2. Pause to clear ports
echo "[2/3] Waiting for memory and ports to clear..."
sleep 2

# 3. Start with explicit VENV
echo "[3/3] Initiating fresh backend start..."
./.venv/Scripts/python.exe main.py

echo "!!! RECOVERY COMPLETE !!!"
