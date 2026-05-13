import os
import sys
from pathlib import Path

# Add project roots to path
repo_root = Path(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo")
sys.path.append(str(repo_root / "Backend"))
sys.path.append(str(repo_root / "Python Libs" / "common_lib" / "src"))

from common_lib.modules.ai_models.container import AIModelsContainer
from common_lib.modules.ai_models.registry.sync import RegistrySync

def run_sync():
    container = AIModelsContainer()
    sync_manager = RegistrySync(container.registry_loader, container.registry_service)
    print("Starting sync...")
    try:
        results = sync_manager.sync()
        print(f"Sync Results: {results}")
    except Exception as e:
        print(f"Sync failed with error: {e}")

if __name__ == "__main__":
    run_sync()
