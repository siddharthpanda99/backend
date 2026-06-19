#!/usr/bin/env python3
"""Fix knowledge/routes/router.py - remove learning_routes import that moved to __init__.py"""

import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

import os

path = os.path.join(os.path.dirname(__file__), "..", "app", "modules", "knowledge", "routes", "router.py")
path = os.path.normpath(path)

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = (
    "from app.modules.knowledge.learning_routes import router as learning_router\n"
    "\n"
    "router.include_router(learning_router)\n"
    "\n"
    "\n"
    "@router.post(\"/learning/quality-log\")"
)

new = '@router.post("/learning/quality-log")'

if old in content:
    content = content.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] Removed learning_routes import from {path}")
else:
    print("[ERR] Could not find the exact text to replace")
    # Find approximate location
    idx = content.find("learning_routes")
    if idx >= 0:
        start = max(0, idx - 100)
        end = min(len(content), idx + 200)
        print(f"Context around 'learning_routes':\n{content[start:end]}")
    else:
        print("'learning_routes' not found in file")
