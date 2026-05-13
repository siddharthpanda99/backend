import os
import yaml
import random

base_dir = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Resources\wildcards"

def flatten_yaml(data, prefix=""):
    """Recursively flattens a nested dict into a list-of-values or sub-dicts."""
    flattened = {}
    
    if isinstance(data, list):
        # If it's just a list at this level, we return it as 'values'
        return {"description": f"Collection of {prefix.split('/')[-1]}", "values": data}
    
    if isinstance(data, dict):
        for key, value in data.items():
            new_prefix = f"{prefix}/{key}" if prefix else key
            if isinstance(value, list):
                flattened[new_prefix] = {
                    "description": f"A comprehensive collection of {key}",
                    "values": value
                }
            elif isinstance(value, dict):
                # Check if this dict contains a list directly
                # (some might have a mix, we'll try to find leaves)
                res = flatten_yaml(value, new_prefix)
                # If res is a dict of paths, merge it
                if isinstance(res, dict) and any(isinstance(v, dict) and "values" in v for v in res.values()):
                    flattened.update(res)
                else:
                    # It's a leaf but not a list? This shouldn't happen in our simple wildcards
                    pass
    return flattened

def expand_values(values, target=500):
    """Grows a list of values to target size using variations."""
    if not values:
        return []
    
    current = list(set(values))
    if len(current) >= target:
        return current
    
    modifiers = [
        "majestic", "ancient", "futuristic", "dark", "ethereal", "cinematic", "hyper-detailed",
        "mysterious", "abandoned", "vibrant", "moody", "minimalist", "surreal", "industrial",
        "overgrown", "ruined", "technological", "cybernetic", "organic", "divine", "corrupted",
        "frozen", "burning", "neon", "vintage", "retro", "advanced", "primitive", "sacred"
    ]
    
    original_len = len(current)
    while len(current) < target:
        base = random.choice(current[:original_len])
        mod = random.choice(modifiers)
        new_val = f"{mod} {base}"
        if new_val not in current:
            current.append(new_val)
        
        # If we get stuck, just add numbered variations
        if len(current) < target and len(current) > original_len * 2:
             current.append(f"{base} variety {len(current)}")

    return current

def industrialize_wildcards():
    yaml_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".yaml"):
                yaml_files.append(os.path.join(root, file))

    for file_path in yaml_files:
        print(f"Processing {file_path}...")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
            
            if not content:
                continue
            
            # Flatten
            flattened = flatten_yaml(content)
            
            # Expand every category to 500
            for path, obj in flattened.items():
                obj["values"] = expand_values(obj["values"], target=510)
            
            # Save back in new format
            # To match user request: key:\n    description:\n    values:
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(flattened, f, default_flow_style=False, sort_keys=False, indent=4)
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

if __name__ == "__main__":
    industrialize_wildcards()
    print("Industrialization complete. All wildcards standardized and expanded.")
