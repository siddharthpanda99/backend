import os
from common_lib.core.di_container import bridge
from common_lib.modules.orchestration.context.memory.services import (
    SQLAlchemyMemoryStore,
)
from common_lib.modules.orchestration.infrastructure.sync.manager import (
    EntitySyncManager,
)
from common_lib.paths import TEMPLATES_DIR, COMMON_LIB_TEMPLATES

from app.core.settings import get_settings

# Establish integration with common_lib's independent database via its own MemoryStore
settings = get_settings()
common_memory = SQLAlchemyMemoryStore(db_url=settings.SQLALCHEMY_DATABASE_URI)

# We also instantiate the sync manager to trigger file system syncs when the API creates/updates entities
sync_manager = EntitySyncManager(
    memory_store=common_memory, templates_root=str(COMMON_LIB_TEMPLATES)
)


def sync_entity_to_fs(entity_type: str, entity_id: str):
    """Utility wrapper to export a database entity back to the file system format."""
    try:
        sync_manager.export_to_file(entity_type, entity_id, force=True)
    except Exception as e:
        print(f"Warning: Failed to sync {entity_type} {entity_id} to file system: {e}")


# ── Wire the DI container ───────────────────────────────────────────
# Export common_memory, sync_manager, and sync_entity_to_fs into the
# AppBridge so that common_lib modules can access them without
# importing from app.core directly.
bridge.initialize(
    memory_store=common_memory,
    sync_manager=sync_manager,
    sync_entity_to_fs=sync_entity_to_fs,
)
