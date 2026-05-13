import os

base_dir = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Resources\wildcards"

def expand_fashion():
    file_path = os.path.join(base_dir, "clothing", "fashion.yaml")
    
    styles = [
        "techwear", "streetwear", "formal wear", "victorian fashion", "cyberpunk clothing", "steampunk gear",
        "dieselpunk outfits", "atompunk clothes", "vintage 1920s", "vintage 1940s", "vintage 1950s",
        "vintage 1960s", "vintage 1970s", "vintage 1980s", "vintage 1990s", "y2k style", "cottagecore",
        "dark academia", "light academia", "gothic lolita", "punk rock", "grunge", "minimalist",
        "maximalist", "avant-garde", "high fashion", "haute couture", "sportswear", "athleisure",
        "military uniform", "tactical gear", "scout outfit", "explorer clothes", "safari wear",
        "bohemian", "hippie style", "preppy", "tomboy", "feminine", "masculine", "androgynous",
        "traditional japanese kimono", "traditional chinese hanfu", "traditional indian saree",
        "traditional korean hanbok", "traditional scottish kilt", "traditional mexican poncho",
        "medieval tunic", "renaissance gown", "pirate attire", "royal regalia", "peasant clothes",
        "sci-fi jumpsuit", "mecha pilot suit", "cybernetic enhancement integrated clothing",
        "holographic fabric dress", "liquid metal suit", "light-emitting fiber optics clothing",
        "shape-shifting smart fabric", "invisibility cloak material", "space suit", "diver suit",
        "hazmat suit", "laboratory coat", "medical scrubs", "chef uniform", "firefighter gear",
        "police uniform", "pilot uniform", "flight attendant suit", "business suit", "tuxedo",
        "evening gown", "cocktail dress", "wedding dress", "bridesmaid dress", "summer dress",
        "sundress", "maxi dress", "midi dress", "mini dress", "bodycon dress", "slip dress",
        "wrap dress", "shirt dress", "tunic dress", "kaftan", "jumpsuit", "romper", "overalls",
        "dungarees", "jeans", "trousers", "slacks", "chinos", "cargo pants", "sweatpants",
        "leggings", "shorts", "bermuda shorts", "skirt", "pencil skirt", "a-line skirt",
        "pleated skirt", "maxi skirt", "midi skirt", "mini skirt", "tutu", "kilt", "sarong",
        "t-shirt", "polo shirt", "button-down shirt", "blouse", "tank top", "crop top",
        "hoodie", "sweatshirt", "sweater", "cardigan", "turtleneck", "vest", "waistcoat",
        "jacket", "blazer", "coat", "overcoat", "trench coat", "parka", "bomber jacket",
        "leather jacket", "denim jacket", "windbreaker", "raincoat", "poncho", "cape",
        "cloak", "shawl", "scarf", "gloves", "mittens", "belt", "braces", "suspenders",
        "tie", "bowtie", "cravat", "handkerchief", "socks", "tights", "stockings",
        "lingerie", "underwear", "swimwear", "bikini", "swimsuit", "trunks", "rash guard",
        "wetsuit", "bathrobe", "pajamas", "nightgown", "onesie", "activewear", "yoga wear",
        "cycling jersey", "football jersey", "basketball jersey", "baseball jersey",
        "hockey jersey", "soccer jersey", "rugby jersey", "cricket whites", "tennis whites",
        "golf attire", "equestrian gear", "ski suit", "snowboard gear", "climbing gear",
        "hiking boots", "running shoes", "sneakers", "loafers", "oxfords", "brogues",
        "derbies", "monk straps", "chelsea boots", "combat boots", "cowboy boots",
        "wellies", "sandals", "flip flops", "slides", "espadrilles", "moccasins",
        "slippers", "clogs", "mules", "pumps", "stilettos", "wedges", "flats", "ballerina flats",
        "mary janes", "monk shoes", "boat shoes", "deck shoes", "espadrilles", "huaraches",
        "jandals", "khussa", "mojari", "padukas", "peshawari chappal", "valenki", "waraji",
        "zori", "geta", "tabi", "birkenstocks", "crocs", "dr martens", "timberlands",
        "converse", "vans", "nike", "adidas", "puma", "reebok", "new balance", "asics",
        "saucony", "mizuno", "skechers", "under armour", "hoka", "on running", "salomon",
        "merrell", "keen", "teva", "chaco", "vibram fivefingers", "la sportiva", "scarpa",
        "black diamond", "petzl", "arcteryx", "patagonia", "the north face", "columbia",
        "mammut", "millet", "haglofs", "fjallraven", "jack wolfskin", "berghaus",
        "helly hansen", "musto", "gill", "dubarry", "hunter", "barbour", "belstaff",
        "filson", "ll bean", "eddie bauer", "lands end", "orvis", "woolrich", "pendleton",
        "carhartt", "dickies", "levis", "wrangler", "lee", "diesel", "g-star", "replay",
        "lucky brand", "ag jeans", "j brand", "paige", "frame", "mother", "moussy",
        "r13", "ksubi", "neuw", "dr denim", "nudie jeans", "apc", "acne studios",
        "saint laurent", "celine", "dior", "chanel", "hermes", "louis vuitton",
        "gucci", "prada", "fendi", "valentino", "versace", "armani", "dolce & gabbana",
        "balenciaga", "givenchy", "burberry", "alexander mcqueen", "stella mccartney",
        "vivienne westwood", "jean paul gaultier", "thierry mugler", "azzedine alaia",
        "yohji yamamoto", "issey miyake", "rei kawakubo", "comme des garcons",
        "junia watanabe", "sacai", "undercover", "visvim", "neighborhood", "wtaps",
        "sophnet", "uniform experiment", "bape", "stussy", "supreme", "off-white",
        "fear of god", "essentials", "palm angels", "amiri", "rhude", "casablanca",
        "jacquemus", "loewe", "bottega veneta", "miu miu", "chloe", "lanvin",
        "rochas", "schiaparelli", "courreges", "paco rabanne", "emilio pucci",
        "missoni", "etro", "marni", "msgm", "n21", "alberta ferretti", "philosophy",
        "moschino", "dsquared2", "diesel", "fiorucci", "benetton", "sisley",
        "max mara", "sportmax", "weekend max mara", "marella", "i blues", "pennyblack",
        "marina rinaldi", "persona by marina rinaldi", "elena miro", "caractere",
        "pinko", "liu jo", "patrizia pepe", "twinset", "elisabetta franchi",
        "gaelle paris", "gum gianni chiarini", "save the duck", "herno", "moncler",
        "canada goose", "moose knuckles", "mackage", "nobis", "parajumpers",
        "woolrich", "barbour", "belstaff", "matchless", "aeropostale", "american eagle",
        "hollister", "abercrombie & fitch", "gap", "old navy", "banana republic",
        "j crew", "madewell", "everlane", "reformation", "realisation par", "rouje",
        "sezane", "bash", "sandro", "maje", "claudie pierlot", "the kooples",
        "zadig & voltaire", "isabel marant", "jerome dreyfuss", "vanessa bruno",
        "sessun", "american vintage", "hartford", "bellerose", "closed", "drykorn",
        "tiger of sweden", "filippa k", "hope", "whyred", "cheap monday", "monki",
        "weekday", "cos", "arket", "other stories", "h&m", "zara", "pull & bear",
        "bershka", "stradivarius", "oysho", "massimo dutti", "uterque", "mango",
        "desigual", "springfield", "cortefiel", "pedro del hierro", "women secret",
        "parfois", "bimba y lola", "aristocrazy", "tous", "uno de 50", "suarez",
        "rabat", "joyeria yolanda", "joyeria suarez", "joyeria lorenzo", "joyeria marcos"
    ]
    
    fabrics = [
        "silk", "leather", "denim", "velvet", "latex", "carbon fiber", "cotton", "wool",
        "linen", "polyester", "nylon", "spandex", "acrylic", "rayon", "viscose", "acetate",
        "chiffon", "organza", "tulle", "lace", "satin", "crepe", "taffeta", "brocade",
        "damask", "jacquard", "tweed", "flannel", "jersey", "fleece", "canvas", "corduroy",
        "suede", "nubuck", "patent leather", "faux leather", "faux fur", "mink fur",
        "fox fur", "rabbit fur", "shearling", "cashmere", "mohair", "alpaca", "angora",
        "merino wool", "pashmina", "hemp", "jute", "bamboo fabric", "soy fabric",
        "kombucha leather", "mycelium leather", "pineapple leather", "apple leather",
        "cactus leather", "grape leather", "corn leather", "recycled polyester",
        "recycled nylon", "ocean plastic fabric", "bioplastic fabric", "spider silk",
        "synthetic spider silk", "graphene fabric", "kevlar", "nomex", "spectra",
        "dyneema", "cordura", "gore-tex", "event", "sympatex", "dermizax", "pertex",
        "polartec", "coolmax", "thermolite", "thinsulate", "primaloft", "down feathers",
        "synthetic down", "reflective fabric", "chromic fabric", "thermochromic fabric",
        "photochromic fabric", "electrochromic fabric", "piezoelectric fabric",
        "conductive fabric", "memory fabric", "shape memory alloy fabric", "3d printed fabric",
        "knitted metal", "chainmail", "scale mail", "plate armor material", "ceramic plates",
        "liquid armor", "non-newtonian fluid fabric", "aerogel insulation", "vacuum insulation",
        "phase change material", "microencapsulated fabric", "antibacterial fabric",
        "anti-uv fabric", "fire retardant fabric", "waterproof fabric", "breathable fabric",
        "moisture wicking fabric", "quick dry fabric", "stretch fabric", "compression fabric",
        "holographic foil", "iridescent sequins", "metallic threads", "gold leaf fabric",
        "silver thread fabric", "copper mesh", "fiber optic weave", "led integrated fabric",
        "flexible screen fabric", "tactile feedback fabric", "haptic fabric", "smart skin",
        "biometric sensing fabric", "energy harvesting fabric", "solar cell fabric",
        "kinetic energy fabric", "thermal energy fabric", "radio frequency shielding fabric"
    ]
    
    accessories = [
        "sunglasses", "cybernetic headset", "glowing jewelry", "tactical mask", "hat",
        "cap", "beanie", "beret", "fedora", "panama hat", "sombrero", "turban",
        "hijab", "niqab", "burqa", "chador", "shayla", "al-amira", "khimar",
        "crown", "tiara", "diadem", "circlet", "headband", "hair clip", "hair pin",
        "scrunchie", "ribbon", "veil", "mask", "balaclava", "bandana", "neck gaiter",
        "earrings", "ear cuffs", "nose ring", "lip ring", "tongue ring", "eyebrow ring",
        "belly button ring", "necklace", "pendant", "choker", "locket", "chains",
        "bracelet", "bangle", "cuff", "wristband", "watch", "smartwatch", "ring",
        "signet ring", "engagement ring", "wedding ring", "eternity ring", "cocktail ring",
        "brooch", "pin", "badge", "medal", "belt", "buckle", "wallet", "purse",
        "handbag", "clutch", "tote bag", "backpack", "messenger bag", "briefcase",
        "suitcase", "trunk", "umbrella", "parasol", "walking stick", "cane", "crutches",
        "wheelchair", "glasses", "spectacles", "monocle", "lorgnette", "binoculars",
        "telescope", "microscope", "magnifying glass", "compass", "sextant", "astrolabe",
        "pocket watch", "hourglass", "sundial", "fan", "hand fan", "muff", "parasol",
        "gloves", "gauntlets", "bracers", "pauldrons", "gorget", "cuirass", "greaves",
        "sabatons", "shield", "buckler", "scabbard", "holster", "sheath", "quiver",
        "pouch", "satchel", "haversack", "knapsack", "bandolier", "utility belt",
        "harness", "collar", "leash", "handcuffs", "shackles", "chains", "keychain",
        "key ring", "lanyard", "whistle", "flashlight", "torch", "lantern", "candle",
        "lighter", "matches", "pipe", "cigar", "cigarette", "vape", "snuff box",
        "perfume bottle", "lipstick tube", "compact mirror", "comb", "brush",
        "toothbrush", "razor", "scissors", "needle", "thread", "thimble", "pincushion",
        "measuring tape", "ruler", "pen", "pencil", "quill", "inkwell", "scroll",
        "book", "journal", "diary", "ledger", "map", "chart", "blueprint", "document",
        "letter", "envelope", "stamp", "seal", "wax", "coin", "token", "medal",
        "talisman", "amulet", "charm", "relic", "idol", "totem", "fetish", "juju",
        "mojo", "gris-gris", "dreamcatcher", "rosary", "prayer beads", "mala",
        "crucifix", "cross", "star of david", "crescent and star", "om", "yin yang",
        "ankh", "eye of horus", "scarab", "phoenix", "dragon", "unicorn", "griffin",
        "basilisk", "manticore", "chimera", "hydra", "kraken", "leviathan",
        "behemoth", "ziz", "roc", "thunderbird", "quetzalcoatl", "garuda",
        "naga", "kappa", "kitsune", "tanuki", "oni", "tengu", "yokai", "bakemono"
    ]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("styles:\n")
        for item in styles:
            f.write(f"  - {item}\n")
        f.write("fabrics:\n")
        for item in fabrics:
            f.write(f"  - {item}\n")
        f.write("accessories:\n")
        for item in accessories:
            f.write(f"  - {item}\n")

def expand_lighting():
    file_path = os.path.join(base_dir, "lighting", "schemes.yaml")
    schemes = [
        "golden hour", "blue hour", "high contrast", "cinematic lighting", "soft bokeh", "neon glow",
        "dramatic shadows", "volumetric fog", "rim lighting", "backlit", "moody lighting", "studio lighting",
        "natural sunlight", "overcast", "moonlight", "starlight", "firelight", "candlelight", "torchlight",
        "bioluminescent", "phosphorescent", "fluorescent", "incandescent", "halogen", "led", "laser",
        "holographic", "iridescent", "pearlized", "metallic", "glossy", "matte", "velvet", "satin",
        "textured", "patterned", "gradient", "solid", "transparent", "translucent", "opaque",
        "refractive", "reflective", "dispersive", "diffractive", "interferometric", "polarized",
        "thermal", "infrared", "ultraviolet", "x-ray", "gamma ray", "radio wave", "microwave",
        "acoustic", "ultrasonic", "infrasonic", "magnetic", "electric", "gravitational",
        "quantum", "astral", "ethereal", "celestial", "infernal", "divine", "arcane",
        "mystical", "magical", "enchanted", "cursed", "blessed", "holy", "unholy",
        "dark", "light", "shadow", "radiance", "brilliance", "splendor", "glory",
        "majesty", "power", "energy", "force", "spirit", "soul", "mind", "heart",
        "breath", "life", "death", "void", "chaos", "order", "time", "space",
        "reality", "dream", "nightmare", "vision", "illusion", "mirage", "phantom",
        "specter", "ghost", "spirit", "wraith", "shade", "shadow", "echo", "reflection",
        "resonance", "vibration", "frequency", "wavelength", "amplitude", "phase",
        "coherence", "entanglement", "superposition", "tunneling", "decay", "growth",
        "evolution", "entropy", "singularity", "infinity", "eternity", "absolute",
        "nothingness", "everything", "oneness", "duality", "trinity", "quaternity"
    ]
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("schemes:\n")
        for item in schemes:
            f.write(f"  - {item}\n")

def expand_camera():
    file_path = os.path.join(base_dir, "camera", "settings.yaml")
    settings = [
        "8k uhd", "highly detailed", "masterpiece", "raytraced", "unreal engine 5", "octane render",
        "wide angle", "macro lens", "fisheye lens", "tilt-shift", "telephoto lens", "prime lens",
        "zoom lens", "anamorphic lens", "vintage lens", "pinhole camera", "polaroid", "film grain",
        "35mm film", "70mm imax", "dslr", "mirrorless", "medium format", "large format",
        "action cam", "drone shot", "satellite imagery", "microscopic", "telescopic",
        "infrared camera", "thermal camera", "night vision", "x-ray imaging", "ultrasound",
        "mri", "ct scan", "pet scan", "spectroscopy", "interferometry", "holography",
        "stereoscopic 3d", "virtual reality", "augmented reality", "mixed reality",
        "360 degree video", "panoramic shot", "timelapse", "slow motion", "high speed",
        "stop motion", "claymation", "rotoscoping", "motion capture", "facial capture",
        "performance capture", "virtual production", "volume stage", "green screen",
        "blue screen", "chroma key", "compositing", "matte painting", "deep fake",
        "neural rendering", "generative adversarial network", "diffusion model",
        "transformer model", "large language model", "multimodal model", "agentic model",
        "autonomous system", "robotics", "cybernetics", "artificial intelligence",
        "machine learning", "deep learning", "computer vision", "natural language processing",
        "speech recognition", "synthesis", "translation", "summarization", "reasoning",
        "planning", "decision making", "problem solving", "creativity", "intuition",
        "empathy", "consciousness", "sentience", "sapience", "transcendence",
        "singularity", "posthumanism", "transhumanism", "extropianism", "cosmism"
    ]
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("settings:\n")
        for item in settings:
            f.write(f"  - {item}\n")

expand_fashion()
expand_lighting()
expand_camera()

print("Expanded fashion, lighting, and camera.")
