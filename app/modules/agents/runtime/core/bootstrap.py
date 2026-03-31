"""
agents/runtime/core/bootstrap.py
----------------------------------
Startup utilities: key loader + deferred agent initialisation.
"""
from __future__ import annotations

import os

from app.modules.agents.runtime.utils.logging import get_logger

logger = get_logger(__name__)


def load_keys() -> None:
    """
    Load API keys from resources/keys.txt into the environment.
    Tries three candidate paths relative to the working directory.
    """
    cwd = os.getcwd()
    candidates = [
        os.path.abspath(os.path.join(cwd, "..",             "resources", "keys.txt")),
        os.path.abspath(os.path.join(cwd,                   "resources", "keys.txt")),
        os.path.abspath(os.path.join(cwd, "Backend Monorepo", "resources", "keys.txt")),
    ]
    keys_path = next((p for p in candidates if os.path.exists(p)), None)

    if not keys_path:
        logger.warning("Keys file not found. Checked: %s", candidates)
        return

    try:
        count = 0
        with open(keys_path) as fh:
            for line in fh:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()
                    count += 1
        logger.info("Loaded %d API keys from %s", count, keys_path)
    except Exception as exc:
        logger.error("Error loading keys from %s: %s", keys_path, exc)
