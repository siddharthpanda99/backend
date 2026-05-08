
import os
import asyncio
import sys

# Add common_lib to path
sys.path.append("../Python Libs/common_lib/src")

from common_lib.modules.memory.service import MemoryService
from common_lib.modules.memory.memory_storage.repositories.memory_repository import MemoryRepository
from common_lib.modules.memory.memory_storage.adapters.relational_adapter import RelationalStorageAdapter

async def test_memory_service():
    print("Testing MemoryService initialization...")
    try:
        connection_string = os.environ.get("DATABASE_URL", "sqlite:///test.db")
        print(f"Connection string: {connection_string}")
        
        adapter = RelationalStorageAdapter(connection_string)
        print("Adapter initialized.")
        
        repository = MemoryRepository(adapter)
        print("Repository initialized.")
        
        service = MemoryService(repository=repository)
        print("Service initialized.")
        
        stats = await service.get_stats()
        print(f"Stats: {stats}")
        
    except Exception as e:
        print(f"Error during initialization: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_memory_service())
