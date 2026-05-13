import os
import yaml
from pathlib import Path

root_dir = Path(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Resources\wildcards")

masters = {
    "characters.yaml": {},
    "clothing.yaml": {},
    "worldbuilding.yaml": {},
    "visuals.yaml": {}
}

def get_target_master(path_key):
    pk = path_key.lower()
    if "character" in pk or "people" in pk or "anatomy" in pk or "archetype" in pk or "role" in pk or "profession" in pk:
        return "characters.yaml"
    if "clothing" in pk or "fashion" in pk or "fabric" in pk or "jewelry" in pk or "mask" in pk or "armor" in pk:
        return "clothing.yaml"
    if "lighting" in pk or "camera" in pk or "art" in pk or "style" in pk or "medium" in pk or "visual" in pk:
        return "visuals.yaml"
    # Default to worldbuilding for places, nature, objects, etc.
    return "worldbuilding.yaml"

def consolidate():
    # 1. Load current masters
    for m in masters:
        p = root_dir / m
        if p.exists():
            with open(p, 'r', encoding='utf-8') as f:
                masters[m] = yaml.safe_load(f) or {}

    # 2. Scan all subdirectories for YAML files
    for path in root_dir.rglob("*.yaml"):
        if path.name in masters:
            continue
        if "industrial_wildcards_master.yaml" in path.name:
            continue
            
        print(f"Consolidating {path}...")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not data:
                continue
                
            # Flatten or parse
            for key, val in data.items():
                target = get_target_master(key)
                if key not in masters[target]:
                    masters[target][key] = val
                else:
                    # Merge values
                    if isinstance(val, dict) and "values" in val:
                         existing_vals = set(masters[target][key].get("values", []))
                         new_vals = val["values"]
                         masters[target][key]["values"] = sorted(list(existing_vals.union(set(new_vals))))
                    elif isinstance(val, list):
                         existing_vals = set(masters[target][key].get("values", []))
                         masters[target][key]["values"] = sorted(list(existing_vals.union(set(val))))
                         
        except Exception as e:
            print(f"Error in {path}: {e}")

    # 3. Save masters
    for m, content in masters.items():
        print(f"Saving master {m} with {len(content)} categories...")
        with open(root_dir / m, 'w', encoding='utf-8') as f:
            yaml.dump(content, f, default_flow_style=False, sort_keys=False, indent=4)

if __name__ == "__main__":
    consolidate()
    print("Consolidation complete.")
