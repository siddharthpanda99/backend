import os
import random

def save_txt(path, values):
    with open(path, 'w', encoding='utf-8') as f:
        f.write("\n".join(values))

def expand(base_list, count=300):
    unique_base = list(dict.fromkeys(base_list))
    if len(unique_base) >= count:
        return unique_base[:count]
    
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
    rng = random.Random(42)
    
    while len(expanded) < count:
        d = rng.choice(descriptors)
        v = rng.choice(unique_base)
        new_v = f"{d} {v}"
        if new_v not in expanded:
            expanded.append(new_v)
            
    return expanded

# --- DATA ---
cyberware = ["Neural link", "BCI", "synaptic booster", "overclocked cortex", "datajack", "skillchip socket", "memory shunt", "cognitive accelerator", "empathy damper", "tactical computer", "encephalon rig", "wired reflexes", "neuro-processor", "subliminal inducer", "dream weaver", "focus enhancer", "Bionic eye", "thermal vision", "multi-spectral lens", "HUD overlay", "iris projector", "smartlink", "ultrasound sensor", "radar spike", "cyberears", "acoustic dampener", "olfactory sensor", "taste-modulator", "motion tracker", "night-vision implant", "telescopic optic", "Subdermal armor", "titanium bone lacing", "muscle replacement", "reaction enhancers", "internal router", "cybernetic limb", "hydraulic joint", "prehensile tail", "retractable claws", "foot spikes", "balance augmenter", "dermal plating", "artificial heart", "cyber-liver", "lung-filter", "nano-blood", "Hidden compartment", "finger toolset", "voice modulator", "pheromone dispenser", "auto-injector", "chemical gland", "adrenaline pump", "magnetic palm", "micro-drone launcher", "grapple-wire", "internal battery", "solar-skin", "kinetic generator", "holographic projector"]

steampunk = ["Analytical engine", "difference engine", "steam-boiler", "brass piston", "clockwork heart", "aether-generator", "tesla coil", "voltaic pile", "magnetic induction loop", "pressurized tank", "copper piping", "coal-fed furnace", "winding key", "torsion spring", "Chronometer", "brass sextant", "steam-gauge", "monocle-analyzer", "telescoping lens", "drafting automaton", "aether-spectrograph", "telegraph-earpiece", "pneumatic stylus", "gear-driven compass", "microscopic-loupe", "mechanical typewriter", "Aether-raygun", "tesla rifle", "steam-powered saw", "harpoon-cannon", "clockwork shield", "brass knuckles (pneumatic)", "steam-jet launcher", "gear-mace", "bolt-action blunderbuss", "ornate flintlock", "lightning-rod staff", "Steam-dirigible", "zeppelin gondola", "clockwork horse", "ornithopter", "steam-cycle", "pneumatic lift", "brass submersible", "walking-platform", "aether-skiff", "mechanical wings", "steam-jetpack"]

alchemy = ["Nightshade petal", "dragon-breath orchid", "glow-moss", "mandrake root", "phoenix-feather fern", "silver-leaf clover", "blood-rose", "frost-berry", "void-fungus", "mana-lily", "whispering willow bark", "iron-wood sap", "sun-flower seed (celestial)", "Powdered moonstone", "brimstone", "dragon-scale dust", "pulverized obsidian", "star-metal filings", "saltpeter", "quicksilver", "amber-resin", "crystallized aether", "void-salt", "glowing phosphorus", "crushed emerald", "magnetic ore", "Dragon gall", "unicorn horn shavings", "phoenix ash", "griffin claw", "basilisk eye", "mermaid scales", "vampire blood", "werewolf fur", "imp feces", "chittering paw", "zombie drake eye", "wraith essence", "banshee tear", "Distilled starlight", "liquid fire", "bottled shadow", "ethereal vapor", "holy water", "necrotic ichor", "prismatic oil", "volatile mercury", "bubbling acid", "gaseous sulfur", "frozen mist", "glowing plasma"]

spells = ["Fractal energy", "ethereal vapor", "prismatic light", "void-fire", "celestial radiance", "necrotic rot", "psychic static", "arcane sparks", "temporal ripples", "gravity-distortion", "magnetic flux", "sonic vibration", "plasma arcs", "Geometric sigils", "recursive fractals", "swirling vortex", "blooming nebula", "crystalline shards", "liquid-light drips", "jagged lightning", "soft aurora", "billowing smoke", "iridescent bubbles", "spinning rings", "cascading sparks", "Chrono-distortion", "mana-burn", "soul-shred", "frost-bite", "flame-lick", "earth-quake", "sky-tear", "void-pull", "light-blast", "shadow-creep", "spirit-echo"]

armor_materials = ["Mithril", "Adamantine", "Orichalcum", "Uru", "Valyrian Steel", "Beskar", "Darksteel", "Celestial Bronze", "Shadesteel", "Void-steel", "Frost-iron", "Cold-iron", "Star-metal", "Meteoric iron", "Sun-gold", "Voidstone", "Nullstone", "Ambrite", "Aeonite", "Photite", "Lightrock", "Dianium", "Blood-ore", "Esperglass", "Tenebrium", "Dragon-crystal", "Mana-shard", "Dragon-bone", "Dragon-scale", "Ironwood", "Liftwood", "Angelskin", "Darkwood", "Chitin", "Kraken-shell", "Gorgon-hide", "Phoenix-plate", "Vibranium", "Nth Metal", "Carolium", "Transparisteel", "Ceramite", "Duranium", "Liquid-metal", "Plasma-weave", "Force-field plating"]

architecture = ["Flying buttress", "gargoyle", "lancet window", "rib vault", "rose window", "spire", "crenellation", "portcullis", "moat", "drawbridge", "cloisters", "nave", "apse", "transept", "narthex", "Neon cornice", "plasma conduit", "gravity well", "shard-spire", "void-arch", "aether-dome", "obsidian monolith", "bioluminescent alcove", "crystalline buttress", "floating pagoda", "recursive balcony", "impossible geometry", "Corinthian column", "ionic capital", "doric frieze", "metope", "pediment", "architrave", "balustrade", "baluster", "finial", "lintel", "jamb", "mullion", "transom", "Steam-vent", "pneumatic shaft", "brass pipe", "riveted plate", "iron girder", "gear-mechanism", "exposed wiring", "cooling fan", "exhaust port"]

biopunk = ["Synaptic mesh", "subdermal neural network", "bioluminescent nerve", "regenerating tissue", "stem-cell graft", "ocular upgrade", "compound eye", "organic lens", "sensing antenna", "pheromone detector", "Memory worm", "symbiotic spine", "neural parasite", "thought-recording node", "wetware processor", "cultured synaptic tissue", "bio-cortex", "living data storage", "Chitinous plating", "dermal armor", "insectoid carapace", "hardened bio-armor", "skin-grafted plating", "vascular vein", "glowing bio-energy line", "pulsing vein pattern", "Extra appendage", "articulated biomechanical limb", "arachnid-like enhancement", "prehensile hair", "chameleon skin", "electrochromic skin", "fiber-optic vein"]

lovecraftian = ["Amorphous blight", "eldritch abomination", "cosmic entity", "star-born monstrosity", "dimensional shifter", "sleeping god", "biomechanical horror", "void-dweller", "geometric abstraction", "Cyclopean architecture", "non-Euclidean geometry", "jagged void", "ashen chamber", "sunken city", "Cimmerian void", "liminal space", "fractal landscape", "inky blackness", "Cosmic dread", "existential terror", "unknowable madness", "forbidden knowledge", "apotheosis", "time-lapse metamorphosis", "ancient ritual", "chromatic aberration", "iridescent slime", "Tentacled mass", "pulsating mass", "shifting shadow", "void-eye", "thousand-mouthed beast", "star-spawn", "elder thing", "shoggoth-like form", "nyarlathotep-mask"]

# --- EXECUTION ---
target_dir = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Resources\wildcards\collections\themartiantourist"
os.makedirs(target_dir, exist_ok=True)

save_txt(os.path.join(target_dir, "cyberware.txt"), expand(cyberware, 300))
save_txt(os.path.join(target_dir, "steampunk_gadgets.txt"), expand(steampunk, 300))
save_txt(os.path.join(target_dir, "alchemical_ingredients.txt"), expand(alchemy, 300))
save_txt(os.path.join(target_dir, "spell_effects.txt"), expand(spells, 300))
save_txt(os.path.join(target_dir, "armor_materials.txt"), expand(armor_materials, 300))
save_txt(os.path.join(target_dir, "architectural_elements.txt"), expand(architecture, 300))
save_txt(os.path.join(target_dir, "organic_augmentations.txt"), expand(biopunk, 300))
save_txt(os.path.join(target_dir, "lovecraftian_horrors.txt"), expand(lovecraftian, 300))

print("Expansion Complete.")
