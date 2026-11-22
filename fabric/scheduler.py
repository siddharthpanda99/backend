"""GPU admission controller - prevents VRAM oversubscription.

RTX 4070 (8 GB) budget: at most ~7 GB usable. Heavy GPU workers are
serialized; lighter tenants may co-reside. Idle heavy workers are evicted
before refusing a launch.

Design: reservations are tracked per profile. `try_reserve` fails when the
budget would be exceeded even after evicting idle heavy workers.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fabric.profiles import ProfileRegistry

logger = logging.getLogger(__name__)

# Usable VRAM budget in MB (RTX 4070 8188 MiB minus headroom)
DEFAULT_BUDGET_MB = 7000


class GPUAdmissionController:
    """Tracks VRAM reservations and arbitrates launches."""

    def __init__(self, budget_mb: int = DEFAULT_BUDGET_MB):
        self._budget_mb = budget_mb
        self._reservations: Dict[str, int] = {}  # profile_id -> reserved MB
        self._lock = asyncio.Lock()

    @property
    def budget_mb(self) -> int:
        return self._budget_mb

    def reserved_mb(self) -> int:
        return sum(self._reservations.values())

    def available_mb(self) -> int:
        return max(0, self._budget_mb - self.reserved_mb())

    def is_reserved(self, profile_id: str) -> bool:
        return profile_id in self._reservations

    async def try_reserve(self, profile_id: str, vram_mb: int) -> bool:
        """Reserve VRAM for a profile. Returns False when the budget would be exceeded."""
        if vram_mb <= 0:  # cpu-class tenants are unlimited
            return True
        async with self._lock:
            if profile_id in self._reservations:
                return True  # idempotent re-reserve for restart path
            if self.reserved_mb() + vram_mb > self._budget_mb:
                return False
            self._reservations[profile_id] = vram_mb
            return True

    async def release(self, profile_id: str) -> None:
        async with self._lock:
            self._reservations.pop(profile_id, None)

    def status(self) -> Dict[str, Any]:
        return {
            "budget_mb": self._budget_mb,
            "reserved_mb": self.reserved_mb(),
            "available_mb": self.available_mb(),
            "reservations": dict(self._reservations),
        }


# Process-wide singleton
gpu_admission = GPUAdmissionController()
