import os
import random

def save_txt(path, values):
    with open(path, 'w', encoding='utf-8') as f:
        f.write("\n".join(values))

def expand(base_list, count=300):
    unique_base = list(dict.fromkeys(base_list))
    if len(unique_base) >= count:
        return unique_base[:count]
    
    descriptors = ["Ancient", "Mystic", "Cybernetic", "Ethereal", "Primal", "Divine", "Cursed", "Enchanted", "Runic", "Nanotech", "Plasma", "Bio-luminescent", "Quantum", "Spectral", "Interstellar", "Abyssal", "Celestial", "Void", "Shadow", "Luminous", "Corrupted", "Sanctified", "Arcane", "Steampunk", "Dieselpunk", "Biopunk", "Atompunk", "Solarpunk", "Gothic", "Baroque", "Renaissance", "Minimalist", "Brutalist", "Sleek", "Rugged", "Ornate", "Shattered", "Forged", "Woven", "Etched", "Pulsating", "Flickering", "Frozen", "Molten", "Cinematic", "Photorealistic", "Surreal", "Eerie", "Majestic", "Weathered", "Intricate", "Obsidian", "Gilded", "Iridescent", "Translucent", "Neon-lit", "Ghostly", "Grim", "Radiant", "Misty", "Frozen"]
    
    expanded = list(unique_base)
    rng = random.Random(42)
    while len(expanded) < count:
        d = rng.choice(descriptors)
        v = rng.choice(unique_base)
        new_v = f"{d} {v}"
        if new_v not in expanded:
            expanded.append(new_v)
    return expanded

# --- DATA ---
eye_patterns = ["Sharingan (1-tomoe)", "Sharingan (2-tomoe)", "Sharingan (3-tomoe)", "Mangekyō Sharingan", "Eternal Mangekyō Sharingan", "Byakugan", "Rinnegan", "Tenseigan", "Geass", "Miko eyes", "Soulless void", "Dilated black", "Constricted pinprick", "Bionic iris", "Multi-pupil (polycoria)", "Clouded nebula", "Crystalline structure", "Demonic red sclera", "Angelic gold sclera", "Clockwork gears", "Whirlpool pattern", "Kaleidoscope", "Shifting iris", "Multi-colored iris", "Galaxy iris", "Obsidian mirror", "Burning embers", "Frozen ice", "Electric spark", "Liquid mercury", "Golden sand", "Star-filled", "Spider-web iris", "Horizontal slit", "Vertical slit", "Heart-shaped pupil", "Star-shaped pupil", "Square pupil", "Goat-eye", "Dragon-eye", "Reptilian yellow", "Amethyst purple", "Emerald green", "Sapphire blue", "Ruby red"]

skin_tones = ["Obsidian black", "Pearlescent white", "Translucent blue", "Glowing bioluminescent", "Copper metallic", "Silver chrome", "Gold gilded", "Emerald green (reptilian)", "Ashen gray", "Crimson red (demonic)", "Violet purple", "Indigo blue", "Marble white", "Charcoal matte", "Iron rusted", "Glass-like", "Holographic shifting", "Crystalline skin", "Bark-like", "Scaly texture", "Feathered skin", "Iridescent oil-slick", "Shadowy vapor", "Liquid metal", "Stardust infused", "Cracked porcelain", "Lichen covered", "Neon-veined", "Molten lava veins", "Frozen frost-covered"]

wings = ["Seraphic (6 wings)", "Angelic (white feathers)", "Archangel (gold feathers)", "Fallen (black feathers)", "Demon (leathery)", "Dragon (scaled)", "Wyvern (membranous)", "Bat-like", "Insectoid (transparent)", "Butterfly (vibrant)", "Moth (dusty)", "Fairy (gossamer)", "Mechanical (steampunk)", "Plasma (energy)", "Bone (skeletal)", "Ethereal (transparent)", "Shadow (smoke)", "Ice (crystalline)", "Fire (burning)", "Nebula (cosmic)"]

horns = ["Ram (curled)", "Antelope (straight)", "Demonic (obsidian)", "Satanic (large curved)", "Unicorn (single spiral)", "Bicorn (dual)", "Deer (antlers)", "Moose (palmate)", "Rhino (stout)", "Dragon (spiked)", "Crystalline horns", "Mechanical horns", "Bioluminescent horns", "Bone spurs", "Crown of horns"]

# --- EXECUTION ---
target_dir = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Resources\wildcards\collections\themartiantourist"

save_txt(os.path.join(target_dir, "eye_patterns.txt"), expand(eye_patterns, 300))
save_txt(os.path.join(target_dir, "skin_tones_exotic.txt"), expand(skin_tones, 300))
save_txt(os.path.join(target_dir, "wings_types.txt"), expand(wings, 300))
save_txt(os.path.join(target_dir, "horns_types.txt"), expand(horns, 300))

print("Expansion Complete.")
