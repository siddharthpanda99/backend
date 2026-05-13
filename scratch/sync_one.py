import os
import sys
from pathlib import Path

# Add project roots to path
repo_root = Path(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo")
sys.path.append(str(repo_root / "Backend"))
sys.path.append(str(repo_root / "Python Libs" / "common_lib" / "src"))

from common_lib.modules.ai_models.container import AIModelsContainer

def sync_one():
    container = AIModelsContainer()
    print("Loading models...")
    models = container.registry_loader.load_models()
    dreamshaper = next((m for m in models if m.id == "civitai-4384"), None)
    
    if dreamshaper:
        print(f"Registering {dreamshaper.id}...")
        print(f"Metadata to save: {dreamshaper.metadata}")
        container.registry_service.register_model(dreamshaper)
        print("Done.")
    else:
        print("DreamShaper not found in YAML.")

if __name__ == "__main__":
    sync_one()
