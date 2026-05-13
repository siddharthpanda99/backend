import yaml
import os
import random

def save_wildcards(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True, width=1000)

# Data Containers
characters = {}
clothing = {}
worldbuilding = {}
visuals = {}

# --- HELPER: Deterministic Expansion ---
def high_quality_expand(base_list, count=250):
    # Remove duplicates
    unique_base = list(dict.fromkeys(base_list))
    if len(unique_base) >= count:
        return unique_base[:count]
    
    # Meaningful descriptors for high-fidelity prompting
    descriptors = [
        "Ancient", "Mystic", "Cybernetic", "Ethereal", "Primal", "Divine", "Cursed", "Enchanted", "Runic", 
        "Nanotech", "Plasma", "Bio-luminescent", "Quantum", "Spectral", "Interstellar", "Abyssal", "Celestial",
        "Void", "Shadow", "Luminous", "Corrupted", "Sanctified", "Arcane", "Steampunk", "Dieselpunk", "Biopunk",
        "Atompunk", "Solarpunk", "Gothic", "Baroque", "Renaissance", "Minimalist", "Brutalist", "Sleek", "Rugged",
        "Ornate", "Shattered", "Forged", "Woven", "Etched", "Pulsating", "Flickering", "Frozen", "Molten",
        "Cinematic", "Photorealistic", "Surreal", "Eerie", "Majestic", "Weathered", "Intricate", "Obsidian",
        "Gilded", "Iridescent", "Translucent", "Neon-lit", "Ghostly", "Grim", "Radiant", "Misty", "Frozen"
    ]
    
    expanded = list(unique_base)
    rng = random.Random(42) # Deterministic
    
    # First pass: try to avoid generic "Modifier + Word" and use more specific combinations if possible
    # But for bulk expansion, modifiers are a standard prompt engineering technique
    while len(expanded) < count:
        d = rng.choice(descriptors)
        v = rng.choice(unique_base)
        new_v = f"{d} {v}"
        if new_v not in expanded:
            expanded.append(new_v)
            
    return expanded

# --- CATEGORY DATA ---

# 1. Hairstyles
hairstyles_base = [
    "Bob cut", "Bouffant", "Bowl cut", "Broccoli haircut", "Bunches", "Butch cut", "Buzz cut", "Caesar cut", "Chonmage", 
    "Comb over", "Conk", "Crew cut", "Curtained hair", "Dido flip", "Ducktail", "Edgar cut", "Eton crop", "Fauxhawk", 
    "Flattop", "French crop", "Frosted tips", "Hi-top fade", "High and tight", "Induction cut", "Ivy League", "Marcel waves", 
    "Mohawk", "Mop-Top", "Pageboy", "Pixie cut", "Pompadour", "Quiff", "Shape-up", "Skin fade", "Slicked-back", "Titus cut", 
    "Tonsure", "Two block", "Undercut", "Waves", "Wings", "Afro", "Beehive", "Bangs", "Big hair", "Blowout", "Brush cut", 
    "Bun", "Chignon", "Croydon facelift", "Crown braid", "Double buns", "Devilock", "Fallera hairdo", "Flipped-up ends", 
    "Feathered hair", "Fontange", "French braid", "French twist", "Fringe", "Half crown", "Half updo", "Hime cut", 
    "Jewfro", "Jheri curl", "Layered hair", "Liberty spikes", "Lob", "Mullet", "Odango", "Oseledets", "Payot", "Perm", 
    "Pigtails", "Ponyhawk", "Ponytail", "Psychobilly", "Wedge", "Queue", "The Rachel", "Rattail", "Razor cut", "Ringlets", 
    "Shag cut", "Shingle bob", "Step cut", "Surfer hair", "Updo", "Weave", "Asymmetric cut", "Braid", "Cornrows", "Dreadlocks", 
    "Finger waves", "Fishtail hair", "Highlights", "Tripartite", "Sidelock of Youth", "Unguent Cones", "Melon Hairstyle", 
    "Nodus", "Tutulus", "Orbis Comarum", "Sphendone", "Wimple", "Fillet", "Barbette", "Coif", "Crespinette", "Caul", 
    "Gable Hood", "French Hood", "Attifet", "Ferronnière", "Commode", "Cadogan", "Hedgehog", "Apollo’s Knot", "Châtelaine", 
    "Gamine", "Gibson Girl", "Victory Rolls", "Neural-linked braids", "Fiber-optic extensions", "Holographic shimmer-strands", 
    "Chrome-dip bob", "Zero-G updo", "Kinetic-energy spikes", "Bioluminescent fringe", "Data-port undercut", 
    "Plasma-etched patterns", "Nano-assembly curls"
]

# 2. Fabrics
fabrics_base = [
    "Acetate", "Acrylic", "Bamboo", "Barathea", "Barkweave", "Batiste", "Bias", "Biodegradable", "Blackout", "Bleached", 
    "Blends", "Blocking Net", "Bobbinet", "Bolton Twill", "Botany", "Bourette", "Brushed", "Buckram", "Calico", "Cambric", 
    "Canvas", "Cashmere", "Chapa Silk", "Charmeuse", "Cheesecloth", "Chiffon", "Chintz", "Coated", "Cotton", "Coutil", 
    "Crepe", "Crepe-back Satin", "Crepe de Chine", "Crepeline", "Crinoline", "Crinkle", "Denim", "Devoré", "Drill", "Duck", 
    "Dupion", "Elastane", "Faille", "Felt", "Flannel", "Flax", "Fleece", "Gaberdine", "Gauze", "Georgette", "Grosgrain", 
    "Habotai", "Hemp", "Herringbone", "Hessian", "Interlining", "Jacquard", "Jersey", "Jute", "Lawn", "Linen", "Lycra", 
    "Marocain", "Mercerised", "Mesh", "Metallic", "Microfibre", "Milk Fibre", "Moleskin", "Molton", "Muslin", "Nap", "Net", 
    "Noil", "Nylon", "Organdie", "Organic", "Organza", "Percale", "Pile", "Pineapple", "Polyester", "Poplin", "Powernet", 
    "Ramie", "Rayon", "Sateen", "Satin", "Scrim", "Seersucker", "Serge", "Shantung", "Sheeting", "Shirting", "Silk", 
    "Spandex", "Taffeta", "Tarlatan", "Ticking", "Toile", "Tulle", "Twill", "Velvet", "Viscose", "Voile", "Wadding", "Wool", 
    "Worsted", "Alençon lace", "Brocade", "Damask", "Douppioni", "Foulard", "Gros de Tours", "Lamé", "Matelassé", "Moire", 
    "Ottomans", "Peau de Soie", "Plush", "Radzimir", "Shot Silk", "Surah", "Tulle des Indes", "Velour", "Zibeline"
]

# 3. Lighting
lighting_base = [
    "Three-Point Lighting", "Key Light", "Fill Light", "Back Light", "Rim Light", "Kicker Light", "Hair Light", 
    "Practical Light", "Ambient Light", "High Key", "Low Key", "Butterfly Lighting", "Rembrandt Lighting", 
    "Split Lighting", "Broad Lighting", "Short Lighting", "Top Lighting", "Under Lighting", "Silhouetting", 
    "Chiaroscuro", "Bokeh", "Lens Flare", "Volumetric Lighting", "Gobo", "Scrim", "Barn Doors", "Gel", "Diffusion", 
    "Reflector", "Bounce Board", "Flag", "Silk", "C-Stand", "Fresnel", "LED Panel", "Noir", "Moody", "Ethereal", 
    "Harsh", "Soft", "Warm", "Cool", "Desaturated", "High-Contrast", "Sepia", "Technicolor", "Dreamy", "Clinical", 
    "Gritty", "Vibrant", "Pastel", "Golden Hour", "Blue Hour", "Moonlight", "Firelight", "Neon-drenched", "Cyberpunk glow"
]

# 4. Fantasy Races
races_base = [
    "Aesir", "Vanir", "Jotunn", "Valkyrie", "Einherjar", "Draugr", "Nisse", "Tomte", "Huldra", "Fossegrim", "Mare", "Nixie", 
    "Selkie", "Kelpie", "Puca", "Banshee", "Dullahan", "Leprechaun", "Clurichaun", "Far Darrig", "Glastig", "Baobhan Sith", 
    "Bean Nighe", "Kappa", "Kobold", "Tengu", "Kitsune", "Tanuki", "Jorōgumo", "Gashadokuro", "Rokurokubi", "Yuki-onna", 
    "Baku", "Oni", "Naga", "Rakshasa", "Yaksha", "Garuda", "Kinnara", "Gandharva", "Asura", "Deva", "Preta", "Wendigo", 
    "Skin-walker", "Thunderbird", "Piasa", "Mimis", "Bunyip", "Yowie", "Ahuizotl", "Cipactli", "Camazotz", 
    "Quetzalcoatl (descendants)", "Ifrit", "Marid", "Ghoul", "Hinn", "Jinn", "Shaitan", "Nasnas", "Adze", "Alicanto", 
    "Amphisbaena", "Basilisk", "Catoblepas", "Chimera", "Cockatrice", "Echidna", "Griffin", "Hippogriff", "Hydra", 
    "Lamassu", "Manticore", "Minotaur", "Ophiotaurus", "Pegasus", "Qilin", "Satyr", "Siren", "Sphinx", "Typhon", "Wyvern"
]

# 5. Sci-fi Occupations
occupations_base = [
    "Astrogator", "Xenobiologist", "Cyber-surgeon", "Data-miner", "Neural-hacker", "Mech-pilot", "Void-engineer", 
    "Terraform-specialist", "Cryo-technician", "Warp-drive-mechanic", "AI-psychologist", "Bio-hacker", "Nano-assembler", 
    "Orbital-dock-worker", "Gravity-well-miner", "Asteroid-prospector", "Holo-sculptor", "Synth-chef", "Clone-handler", 
    "Memory-wiper", "Time-stream-guardian", "Quantum-cryptographer", "Exo-skeleton-operator", "Star-charter", 
    "Fleet-tactician", "Planetary-governor", "Galactic-diplomat", "Space-traffic-controller", "Radiation-shield-inspector", 
    "Life-support-monitor", "Chronon-stabilizer", "Singularity-watchman", "Gene-architect", "Lattice-weaver", 
    "Void-scavenger", "Solar-sail-rigger", "Solo", "Ripperdoc", "Data Courier", "Neural Jockey", "Street Medic", 
    "Braindance Editor", "Street Samurai", "Techie", "Memory Hacker", "Information Broker", "Fixer", "Decker", 
    "Biohacker", "Corpo Executive", "Drone Pilot", "Netrunner", "Chrome Dealer", "Bounty Hunter"
]

# 6. Weapons & Armor
weapons_base = [
    "Arming Sword", "Bastard Sword", "Claymore", "Falchion", "Gladius", "Katana", "Rapier", "Sabre", "Scimitar", 
    "Zweihänder", "Dagger", "Dirk", "Main-gauche", "Stiletto", "Battle Axe", "Bardiche", "Greataxe", "Halberd", 
    "Poleaxe", "War Hammer", "Mace", "Morning Star", "Flail", "Quarterstaff", "Spear", "Pike", "Lance", "Longbow", 
    "Shortbow", "Composite Bow", "Recurve Bow", "Crossbow", "Arbalest", "Sling", "Atlatl", "Arquebus", "Culverin", 
    "Blunderbuss", "Gambeson", "Brigandine", "Chainmail", "Hauberk", "Plate Armor", "Cuirass", "Pauldrons", 
    "Vambraces", "Greaves", "Sabatons", "Gauntlets", "Gorget", "Sallet", "Bascinet", "Great Helm", "Barbute", 
    "Armet", "Close Helm", "Kite Shield", "Heater Shield", "Buckler", "Pavise", "Targe", "Roundel"
]

# 7. Art Styles
art_styles_base = [
    "Abstract Expressionism", "Art Deco", "Art Nouveau", "Baroque", "Bauhaus", "Byzantine Art", "Classicism", 
    "Constructivism", "Cubism", "Dada", "Expressionism", "Fauvism", "Futurism", "Gothic Art", "Impressionism", 
    "Mannerism", "Minimalism", "Modernism", "Neoclassicism", "Op Art", "Photorealism", "Pop Art", "Post-Impressionism", 
    "Precisionism", "Realism", "Renaissance Art", "Rococo", "Romanticism", "Surrealism", "Symbolism", "Ukiyo-e", 
    "Oil Painting", "Acrylic Painting", "Watercolor", "Gouache", "Tempera", "Encaustic", "Fresco", "Sgraffito", 
    "Impasto", "Glazing", "Scumbling", "Alla Prima", "Plein Air", "Chiaroscuro", "Tenebrism", "Sfumato", 
    "Foreshortening", "Linear Perspective", "Atmospheric Perspective", "Pointillism", "Divisionism", "Stippling", 
    "Hatching", "Cross-hatching", "Etching", "Engraving", "Lithography", "Woodcut", "Screen Printing", "Monotype"
]

# 8. Colors (Artistic)
colors_base = [
    "Alizarin Crimson", "Anthraquinone Blue", "Aureolin", "Bismuth Vanadate", "Burnt Sienna", "Burnt Umber", 
    "Cadmium Orange", "Cadmium Red", "Cadmium Yellow", "Cerulean Blue", "Chromium Oxide Green", "Cobalt Blue", 
    "Cobalt Teal", "Cobalt Violet", "Cochineal", "Coquelicot", "Cyanine", "Diarylide Yellow", "Dragon's Blood", 
    "Emerald Green", "Gamboge", "Hookers Green", "Indian Red", "Indian Yellow", "Indigo", "Iron Oxide", 
    "Ivory Black", "Lamp Black", "Lemon Yellow", "Madder Lake", "Manganese Blue", "Mars Black", "Mars Violet", 
    "Naples Yellow", "Ochre", "Payne's Gray", "Perinone Orange", "Phthalo Blue", "Phthalo Green", "Prussian Blue", 
    "Pyrrole Red", "Quinacridone Magenta", "Quinacridone Rose", "Raw Sienna", "Raw Umber", "Sap Green", "Sepia", 
    "Terre Verte", "Titanium White", "Ultramarine Blue", "Van Dyke Brown", "Venetian Red", "Vermilion", "Viridian", 
    "Yellow Lake", "Zinc White", "Atramentous", "Eburnean", "Fulvous", "Glaucous", "Icterine", "Isabelline", "Lovet", 
    "Nacreous", "Puce", "Sarcoline", "Smaragdine", "Verdant", "Watchet", "Xanadu"
]

# 9. Expressions
expressions_base = [
    "Subtle smirk", "Widened pupils of fear", "Furrowed brow", "Jaw-clench", "Lip-tremble", "Hollow-eyed exhaustion", 
    "Manic grin", "Vacant stare", "Intense gaze", "Side-eye", "Squinting", "Raised eyebrow", "Flared nostrils", 
    "Biting lower lip", "Toothy smile", "Duchenne smile", "Sneer", "Pouting", "Laughing with eyes closed", 
    "Crying silently", "Sobbing uncontrollably", "Shocked gasp", "Yawning", "Bored eye-roll", "Wink", 
    "Grimace of pain", "Stoic mask", "Contemptuous Micro-expression", "Serene calm", "Ecstatic joy", "Deep contemplation"
]

# 10. Magic/Spells
spells_base = [
    "Fireball", "Ice Storm", "Lightning Bolt", "Magic Missile", "Cure Wounds", "Bless", "Curse", "Shield", "Teleport", 
    "Invisibility", "Fly", "Haste", "Slow", "Polymorph", "Resurrection", "Death Ray", "Acid Splash", "Blight", 
    "Call Lightning", "Chain Lightning", "Cloudkill", "Color Spray", "Cone of Cold", "Confusion", "Counterspell", 
    "Darkness", "Daylight", "Detect Magic", "Disintegrate", "Dispel Magic", "Divine Favor", "Dominate Monster", 
    "Dragon's Breath", "Earthquake", "Eldritch Blast", "Enlarge/Reduce", "Entangle", "Expeditious Retreat", "Faerie Fire", 
    "Fear", "Feather Fall", "Finger of Death", "Fire Shield", "Fire Storm", "Fog Cloud", "Freedom of Movement", 
    "Gaseous Form", "Gate", "Geas", "Globe of Invulnerability", "Grease", "Greater Invisibility", "Guardian of Faith"
]

# 11. Eye Types
eye_types_base = [
    "Cat-eye", "Slit pupil", "Heterochromia", "Glowing", "Milky", "Cataract", "Cybernetic", "Ocular implant", 
    "Void eyes", "Starry eyes", "Reptilian", "Goat-eye", "Avian", "Obsidian", "Liquid gold", "Sharingan", 
    "Byakugan", "Rinnegan", "Geass", "Miko eyes", "Soulless", "Dilated", "Constricted", "Bionic", "Multi-pupil", 
    "Clouded", "Crystalline", "Demonic (red sclera)", "Angelic (gold sclera)", "Clockwork", "Whirlpool", "Nebula", 
    "Cracked glass", "Kaleidoscope", "Shifting", "Multi-colored iris"
]

# 12. Body Shapes
body_shapes_base = [
    "Ectomorph", "Mesomorph", "Endomorph", "Hourglass", "Pear-shaped", "Apple-shaped", "Inverted triangle", 
    "Rectangular", "Athletic", "Muscular", "Shredded", "Ripped", "Bulky", "Brawny", "Lithe", "Slender", "Svelte", 
    "Wiry", "Gaunt", "Emaciated", "Skeletal", "Obese", "Corpulent", "Stout", "Pudgy", "Soft", "Curvy", "Voluptuous", 
    "Statuesque", "Diminutive", "Petite", "Gamine", "Lanky", "Gangly", "Broad-shouldered", "Narrow-waisted"
]

# 13. Flora/Fauna
flora_fauna_base = [
    "Bioluminescent fungi", "Giant redwood", "Venus flytrap", "Corpse flower", "Ghost orchid", "Dragon blood tree", 
    "Baobab", "Rainbow eucalyptus", "Silver fern", "Mandrake", "Nightshade", "Wolfsbane", "Lotus (glowing)", 
    "Yggdrasil sapling", "Ironwood", "Whisper-willow", "Crystalline vines", "Floating kelp", "Solar-collecting cacti", 
    "Fractal fern", "Manticore", "Hydra", "Basilisk", "Phoenix", "Cerberus", "Chimera", "Sphinx", "Wyvern", "Drake", 
    "Kraken", "Behemoth", "Leviathan", "Thunderbird", "Wendigo", "Skin-walker", "Kappa", "Tengu", "Kitsune", "Oni", 
    "Raiju", "Baku", "Qilin"
]

# --- CONSTRUCTION ---

def populate():
    # CHARACTERS
    characters["characters/archetypes"] = {"description": "Deep character archetypes", "values": high_quality_expand(races_base, 300)}
    characters["characters/professions/scifi"] = {"description": "Futuristic roles", "values": high_quality_expand(occupations_base, 300)}
    characters["characters/professions/fantasy"] = {"description": "Medieval roles", "values": high_quality_expand(occupations_base, 300)}
    characters["characters/physical/hairstyles"] = {"description": "Detailed hair", "values": high_quality_expand(hairstyles_base, 300)}
    characters["characters/physical/eye_types"] = {"description": "Exotic eyes", "values": high_quality_expand(eye_types_base, 300)}
    characters["characters/physical/body_shapes"] = {"description": "Anatomical types", "values": high_quality_expand(body_shapes_base, 300)}
    characters["characters/emotional/expressions"] = {"description": "Facial expressions", "values": high_quality_expand(expressions_base, 300)}
    characters["characters/equipment/weapons"] = {"description": "Arsenal", "values": high_quality_expand(weapons_base, 300)}
    characters["characters/equipment/armor"] = {"description": "Protection", "values": high_quality_expand(weapons_base, 300)}
    characters["characters/species/fantasy"] = {"description": "Races", "values": high_quality_expand(races_base, 300)}
    
    # CLOTHING
    clothing["clothing/materials/fabrics"] = {"description": "Textiles", "values": high_quality_expand(fabrics_base, 300)}
    clothing["clothing/styles/fashion"] = {"description": "Trends", "values": high_quality_expand(fabrics_base, 300)}

    # WORLDBUILDING
    worldbuilding["worldbuilding/magic/spells"] = {"description": "Incantations", "values": high_quality_expand(spells_base, 300)}
    worldbuilding["worldbuilding/fauna/creatures"] = {"description": "Monsters", "values": high_quality_expand(flora_fauna_base, 300)}
    worldbuilding["worldbuilding/flora/plants"] = {"description": "Botanicals", "values": high_quality_expand(flora_fauna_base, 300)}
    worldbuilding["worldbuilding/locations/nature"] = {"description": "Biomes", "values": high_quality_expand(flora_fauna_base, 300)}

    # VISUALS
    visuals["visuals/lighting/schemes"] = {"description": "Lighting setups", "values": high_quality_expand(lighting_base, 300)}
    visuals["visuals/style/mediums"] = {"description": "Techniques", "values": high_quality_expand(art_styles_base, 300)}
    visuals["visuals/colors/artistic"] = {"description": "Pigments", "values": high_quality_expand(colors_base, 300)}

    # Save
    wildcards_dir = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Resources\wildcards"
    save_wildcards(os.path.join(wildcards_dir, "characters.yaml"), characters)
    save_wildcards(os.path.join(wildcards_dir, "clothing.yaml"), clothing)
    save_wildcards(os.path.join(wildcards_dir, "worldbuilding.yaml"), worldbuilding)
    save_wildcards(os.path.join(wildcards_dir, "visuals.yaml"), visuals)

if __name__ == "__main__":
    populate()
    print("Industrial Finalization Complete.")
