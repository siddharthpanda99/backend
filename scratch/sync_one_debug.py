import os
import sys
from pathlib import Path

# Add project roots to path
repo_root = Path(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo")
sys.path.append(str(repo_root / "Backend"))
sys.path.append(str(repo_root / "Python Libs" / "common_lib" / "src"))

print("DEBUG: Importing container...")
from common_lib.modules.ai_models.container import AIModelsContainer

def sync_one():
    print("DEBUG: Initializing container...")
    container = AIModelsContainer()
    print("DEBUG: Loading models from YAML...")
    models = container.registry_loader.load_models()
    print(f"DEBUG: Loaded {len(models)} models.")
    
    dreamshaper = next((m for m in models if m.id == "civitai-4384"), None)
    
    if dreamshaper:
        print(f"DEBUG: Registering {dreamshaper.id}...")
        print(f"DEBUG: Metadata: {dreamshaper.metadata}")
        container.registry_service.register_model(dreamshaper)
        print("DEBUG: Register complete.")
    else:
        print("DEBUG: DreamShaper not found.")

if __name__ == "__main__":
    sync_one()
