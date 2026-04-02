import json
import os
import yaml

def migrate_vision_presets():
    source_path = r"Backend Monorepo/Backend/app/modules/vision/prompts_config.json"
    target_dir = r"Backend Monorepo/Python Libs/common_lib/src/common_lib/templates/configs/instances/vision"
    
    if not os.path.exists(source_path):
        print(f"Source not found: {source_path}")
        return

    os.makedirs(target_dir, exist_ok=True)
    
    with open(source_path, 'r', encoding='utf-8') as f:
        presets = json.load(f)
        
    for p in presets:
        name = p.get('name', 'unnamed_preset')
        # Create a safe filename
        safe_name = name.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('|', '_')
        target_path = os.path.join(target_dir, f"{safe_name}.yaml")
        
        instance_data = {
            "template_id": "vision_sd15",
            "data_config": {
                "prompt": p.get('prompt'),
                "negative_prompt": p.get('negative_prompt'),
                "cfg_scale": p.get('cfg'),
                "steps": p.get('steps'),
                "sampler": p.get('sampler'),
                "width": p.get('width'),
                "height": p.get('height')
            },
            "metadata": {
                "legacy_name": name,
                "category": "vision_preset"
            }
        }
        
        with open(target_path, 'w', encoding='utf-8') as tf:
            yaml.dump(instance_data, tf, default_flow_style=False, sort_keys=False)
        print(f"Migrated: {name} -> {target_path}")

if __name__ == "__main__":
    migrate_vision_presets()
