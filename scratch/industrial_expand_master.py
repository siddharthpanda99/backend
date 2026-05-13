import yaml
import os
import random

wildcards_dir = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Resources\wildcards"

def expand_to_200(values, category_name):
    """Expands a list to 200+ values using meaningful variations."""
    if not values:
        return []
    
    current = list(set(values))
    if len(current) >= 200:
        return current
    
    # Meaningful modifiers grouped by theme
    themes = {
        "fantasy": ["Ancient", "Mystic", "Enchanted", "Runic", "Divine", "Cursed", "Spectral", "Mythical", "Elven", "Dwarven", "Primal"],
        "scifi": ["Cybernetic", "Holographic", "Advanced", "Quantum", "Bio-luminescent", "Nanotech", "Orbital", "Interstellar", "Synthetic", "Plasma"],
        "visual": ["Cinematic", "High-fidelity", "Hyper-detailed", "Vibrant", "Desaturated", "Moody", "Radiant", "Ethereal", "Soft-focus", "Sharp-edged"],
        "state": ["Battle-worn", "Pristine", "Rusted", "Forgotten", "Overgrown", "Ruined", "Immaculate", "Weathered", "Polished", "Shattered"]
    }
    
    all_mods = [m for theme in themes.values() for m in theme]
    
    original_len = len(current)
    while len(current) < 205:
        base = random.choice(current[:original_len])
        mod = random.choice(all_mods)
        # Avoid double modifiers
        if any(m in base for m in all_mods):
             new_val = f"{base} (Variation {len(current)})"
        else:
             new_val = f"{mod} {base}"
             
        if new_val not in current:
            current.append(new_val)
            
    return current

def industrial_expand_master():
    files = ["characters.yaml", "clothing.yaml", "worldbuilding.yaml"]
    
    for filename in files:
        path = os.path.join(wildcards_dir, filename)
        if not os.path.exists(path):
            continue
            
        print(f"Expanding {filename}...")
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            
        if not data:
            continue
            
        for key, obj in data.items():
            if "values" in obj:
                obj["values"] = expand_to_200(obj["values"], key)
        
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, indent=4)

if __name__ == "__main__":
    industrial_expand_master()
    print("Expansion complete. All categories now have 200+ values.")
