import sys
import os
from pathlib import Path

# Add common_lib to sys.path
sys.path.append(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Python Libs\common_lib\src")

try:
    from common_lib.modules.ai_models.registry.loader import RegistryLoader
    
    registry_path = Path(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Python Libs\common_lib\src\common_lib\modules\ai_models\resources\registry_audio.yaml")
    loader = RegistryLoader([str(registry_path)])
    
    print(f"Loading models from {registry_path}...")
    models = loader.load_models()
    
    print(f"Successfully loaded {len(models)} audio models.")
    for model in models:
        print(f" - {model.id} ({', '.join(model.tasks)})")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
