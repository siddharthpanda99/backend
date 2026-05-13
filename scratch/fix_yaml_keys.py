import yaml
import os

def fix_file(path, prefix):
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    new_data = {}
    for k, v in data.items():
        if k.startswith(f"{prefix}/"):
            new_key = k[len(prefix)+1:]
            new_data[new_key] = v
        else:
            new_data[k] = v
            
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(new_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True, width=1000)
    print(f"Fixed {path}")

wildcards_dir = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Resources\wildcards"
fix_file(os.path.join(wildcards_dir, "characters.yaml"), "characters")
fix_file(os.path.join(wildcards_dir, "clothing.yaml"), "clothing")
fix_file(os.path.join(wildcards_dir, "worldbuilding.yaml"), "worldbuilding")
fix_file(os.path.join(wildcards_dir, "visuals.yaml"), "visuals")
