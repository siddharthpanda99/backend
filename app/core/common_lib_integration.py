import os
from common_lib.modules.orchestration.memory.services import SQLAlchemyMemoryStore
from common_lib.modules.orchestration.sync.manager import EntitySyncManager
from common_lib.paths import TEMPLATES_DIR, COMMON_LIB_TEMPLATES

# Establish integration with common_lib's independent database via its own MemoryStore
common_memory = SQLAlchemyMemoryStore()

# We also instantiate the sync manager to trigger file system syncs when the API creates/updates entities
sync_manager = EntitySyncManager(memory_store=common_memory, templates_root=str(COMMON_LIB_TEMPLATES))

def sync_entity_to_fs(entity_type: str, entity_id: str):
    """Utility wrapper to export a database entity back to the file system format."""
    try:
        sync_manager.export_to_file(entity_type, entity_id, force=True)
    except Exception as e:
        print(f"Warning: Failed to sync {entity_type} {entity_id} to file system: {e}")
