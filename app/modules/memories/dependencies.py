from common_lib.modules.memory.service import MemoryService
from common_lib.modules.memory.memory_storage.repositories.memory_repository import MemoryRepository
from common_lib.modules.memory.memory_storage.adapters.relational_adapter import RelationalStorageAdapter
import os

# For now, we use the RelationalStorageAdapter with a dummy connection string 
# as the adapter itself is currently a mock. 
# This will be replaced with a real SQLAlchemy-based adapter once finalized.
_memory_service = None

def get_memory_service() -> MemoryService:
    global _memory_service
    if _memory_service is None:
        adapter = RelationalStorageAdapter(os.environ.get("DATABASE_URL", "sqlite:///test.db"))
        repository = MemoryRepository(adapter)
        _memory_service = MemoryService(repository=repository)
    return _memory_service
