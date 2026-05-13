import os
import sys
from pathlib import Path

# Add project roots to path
repo_root = Path(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo")
sys.path.append(str(repo_root / "Backend"))
sys.path.append(str(repo_root / "Python Libs" / "common_lib" / "src"))

import os
from common_lib.modules.orchestration.infrastructure.sd.models import SdModelRecord
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.paths import IMAGE_MODELS_ROOT

def sync_sd_models():
    """
    Sync models from filesystem to database.
    """
    print(f"Scanning: {IMAGE_MODELS_ROOT}")
    if not IMAGE_MODELS_ROOT.exists():
        print(f"Path not found: {IMAGE_MODELS_ROOT}")
        return

    extensions = [".safetensors", ".ckpt", ".pt", ".pth"]
    
    type_mapping = {
        "checkpoints": "checkpoint",
        "loras": "lora",
        "embeddings": "embedding",
        "vae": "vae",
        "controlnet": "controlnet",
        "ipadapter": "ipadapter",
        "upscale": "upscale",
        "detailing": "detailing",
        "ultralytics": "ultralytics",
        "reactor": "reactor",
        "facerestore": "facerestore",
        "facedetection": "facedetection",
        "insightface": "insightface",
        "sam": "sam",
        "grounding_dino": "grounding_dino"
    }

    count_added = 0
    count_updated = 0
    
    with next(get_session()) as session:
        for subdir in IMAGE_MODELS_ROOT.iterdir():
            if not subdir.is_dir():
                continue
                
            folder_name = subdir.name.lower()
            model_type = type_mapping.get(folder_name, folder_name)
            
            print(f"Processing folder: {folder_name} as type: {model_type}")
            
            for root, dirs, files in os.walk(subdir):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in extensions):
                        file_path = os.path.join(root, file)
                        # Generate a unique ID: rel_path stem
                        rel_path = os.path.relpath(file_path, IMAGE_MODELS_ROOT)
                        model_id = os.path.splitext(rel_path.replace("\\", "/"))[0]
                        
                        category = "default"
                        parts = rel_path.replace("\\", "/").split("/")
                        if len(parts) > 2:
                            category = parts[1]
                        
                        existing = session.get(SdModelRecord, model_id)
                        if existing:
                            existing.fs_path = str(os.path.abspath(file_path))
                            existing.type = model_type
                            existing.metadata_json = {**existing.metadata_json, "category": category}
                            count_updated += 1
                        else:
                            new_model = SdModelRecord(
                                id=model_id,
                                name=os.path.splitext(file)[0],
                                type=model_type,
                                fs_path=str(os.path.abspath(file_path)),
                                metadata_json={"category": category},
                                is_active=True
                            )
                            session.add(new_model)
                            count_added += 1
                            print(f"  Added: {model_id}")
        
        session.commit()
    
    print(f"Sync completed: {count_added} added, {count_updated} updated")

if __name__ == "__main__":
    sync_sd_models()
