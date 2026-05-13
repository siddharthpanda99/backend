import os
import json
import sys

# Set up paths
repo_root = r"c:\Users\91797\Documents\Dev\JS\Monorepo"
common_lib_path = os.path.join(repo_root, "Backend Monorepo", "Python Libs", "common_lib", "src")
backend_path = os.path.join(repo_root, "Backend Monorepo", "Backend")

sys.path.append(common_lib_path)
sys.path.append(backend_path)

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.orchestration.infrastructure.sd.models import SdPresetRecord

def slugify(text):
    import re
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = text.strip('-')
    return text

def seed_presets():
    config_path = os.path.join(backend_path, "app", "modules", "vision", "prompts_config.json")
    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found")
        return
        
    with open(config_path, "r", encoding="utf-8") as f:
        configs = json.load(f)
        
    session = next(get_session())
    count = 0
    for cfg in configs:
        name = cfg.get("name", "Untitled Preset")
        preset_id = cfg.get("id") or slugify(name)
        
        # Check if already exists
        existing = session.query(SdPresetRecord).filter_by(id=preset_id).first()
        if not existing:
            preset = SdPresetRecord(
                id=preset_id,
                name=name,
                prompt=cfg.get("prompt", ""),
                negative_prompt=cfg.get("negative_prompt", cfg.get("negativePrompt", "")),
                sampler=cfg.get("sampler", "euler"),
                steps=cfg.get("steps", 25),
                cfg=cfg.get("cfg", 7.0),
                width=cfg.get("width", 512),
                height=cfg.get("height", 512),
                seed=cfg.get("seed", -1),
                denoise=cfg.get("denoise", 0.5),
                scheduler=cfg.get("scheduler", "normal"),
                metadata_json=cfg.get("metadata", {})
            )
            session.add(preset)
            count += 1
            print(f"Adding preset: {preset_id}")
            
    session.commit()
    print(f"Successfully seeded {count} presets")


if __name__ == "__main__":
    seed_presets()
