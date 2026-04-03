"""
agents/runtime/core/bootstrap.py
----------------------------------
Startup utilities: key loader + deferred agent initialisation.
"""
from __future__ import annotations

import os

from app.modules.agents.runtime.utils.logging import get_logger

logger = get_logger(__name__)


# load_keys() removed as it is no longer used.
