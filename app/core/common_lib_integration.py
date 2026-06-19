"""
App-level common_lib integration shim.

All business logic and singleton instantiation now lives in
``common_lib.core.memory``.  This module:

1. Wires Backend-specific ConfigProvider and StorageProvider (app concerns).
2. Re-exports ``common_memory``, ``sync_manager``, and ``sync_entity_to_fs``
   under their existing names so that every existing app-level import continues
   to work with zero changes.

Any new code should import directly from ``common_lib.core.memory``.
"""

# Wire app-specific providers before anything else runs that might call into
# ConfigProvider / StorageProvider.
from app.core.providers import wire_providers

wire_providers()

# All singletons are owned by common_lib — no instantiation here.
from common_lib.core.memory import (  # noqa: E402
    memory_store as common_memory,
    sync_manager,
    sync_entity_to_fs,
)

__all__ = ["common_memory", "sync_manager", "sync_entity_to_fs"]
