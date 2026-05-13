import os
import sys
from pathlib import Path

# Add project roots to path
repo_root = Path(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo")
sys.path.append(str(repo_root / "Backend"))
sys.path.append(str(repo_root / "Python Libs" / "common_lib" / "src"))

from common_lib.modules.orchestration.infrastructure.sd.models import SdModelRecord
from common_lib.modules.data_storage.database.connection import get_session

def update_dreamshaper_metadata():
    model_id = "checkpoints/sd15/dreamshaper_8"
    
    metadata = {
        "description": "DreamShaper 8 is a general-purpose Stable Diffusion model designed to be a versatile alternative to MidJourney. Improved photorealism, LoRA handling, and anatomical accuracy for NSFW content.",
        "recommended_settings": {
            "sampler": "DPM++ SDE Karras",
            "cfg_scale": 7.5,
            "steps": 25,
            "clip_skip": 2,
            "vae": "vae-ft-mse-840000-ema-pruned"
        },
        "base_model": "SD 1.5",
        "tags": ["Anime", "Landscapes", "3D Art", "Photorealistic", "Fantasy", "Character", "NSFW"],
        "civitai_url": "https://civitai.com/models/4384/dreamshaper?modelVersionId=128713",
        "category": "sd15"
    }
    
    trigger_words = ["realistic", "masterpiece", "cinematic lighting", "portrait"]

    with next(get_session()) as session:
        model = session.get(SdModelRecord, model_id)
        if not model:
            print(f"Model {model_id} not found in database. Searching by name...")
            from sqlmodel import select
            stmt = select(SdModelRecord).where(SdModelRecord.name.ilike("%dreamshaper%"))
            model = session.execute(stmt).scalars().first()
            
        if model:
            print(f"Updating metadata for: {model.id} ({model.name})")
            model.metadata_json = metadata
            model.trigger_words = trigger_words
            session.add(model)
            session.commit()
            print("Successfully updated metadata.")
        else:
            print("Could not find Dreamshaper model in database.")

if __name__ == "__main__":
    update_dreamshaper_metadata()
