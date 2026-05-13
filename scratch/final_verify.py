import os
import sys
from pathlib import Path

# Add project roots to path
repo_root = Path(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo")
sys.path.append(str(repo_root / "Backend"))
sys.path.append(str(repo_root / "Python Libs" / "common_lib" / "src"))

from common_lib.modules.ai_models.container import AIModelsContainer

def verify():
    container = AIModelsContainer()
    model = container.registry_service.get_model("civitai-4384")
    print(f"ID: {model.id}")
    print(f"Parameters: {model.parameters}")
    print(f"Metadata: {model.metadata}")
    
    if model.metadata.get("recommended_settings"):
        print("SUCCESS: Recommended settings found in metadata!")
    else:
        print("FAILURE: Recommended settings NOT found in metadata.")

if __name__ == "__main__":
    verify()
