import yaml
import os

base_dir = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Resources\wildcards"

def generate_characters_master():
    data = {}
    
    # helper to add category
    def add_cat(path, desc, values):
        data[path] = {
            "description": desc,
            "values": sorted(list(set(values)))
        }

    # 1. Archetypes
    archetypes = [
        "The Hero", "The Mentor", "The Rebel", "The Magician", "The Lover", "The Explorer",
        "The Creator", "The Ruler", "The Caregiver", "The Innocent", "The Sage", "The Jester",
        "The Trickster", "The Shadow", "The Herald", "The Threshold Guardian", "The Shapeshifter",
        "The Anima", "The Animus", "The Persona", "The Self", "The Wise Old Man", "The Great Mother",
        "The Divine Child", "The Orphan", "The Wanderer", "The Martyr", "The Warrior", "The Amazon",
        "The Femme Fatale", "The Damsel in Distress", "The White Knight", "The Dark Knight",
        "The Fallen Angel", "The Messiah", "The Antichrist", "The Prophet", "The Hermit",
        "The Glutton", "The Miser", "The Spendthrift", "The Coward", "The Bully", "The Victim",
        "The Savior", "The Executioner", "The Judge", "The Jury", "The Advocate", "The Diplomat",
        "The Spy", "The Assassin", "The Thief", "The Pirate", "The Bandit", "The Outlaw",
        "The Fugitive", "The Exile", "The Pilgrim", "The Seeker", "The Finder", "The Loser",
        "The Winner", "The Champion", "The Underdog", "The Dark Horse", "The Silver Spoon",
        "The Self-made Man", "The Entrepreneur", "The Visionary", "The Idealist", "The Realist",
        "The Pragmatist", "The Cynic", "The Skeptic", "The Believer", "The Fanatic", "The Zealot",
        "The Saint", "The Sinner", "The Prodigal Son", "The Black Sheep", "The Outcast",
        "The Pariah", "The Scapegoat", "The Chosen One", "The Reluctant Hero", "The Anti-hero",
        "The Tragic Hero", "The Byronic Hero", "The Ubermensch", "The Everyman", "The Noble Savage",
        "The Mad Scientist", "The Absent-minded Professor", "The Dumb Muscle", "The Brains",
        "The Comic Relief", "The Straight Man", "The Sidekick", "The Loyal Dog", "The Betrayer",
        "The Backstabber", "The Double Agent", "The Mole", "The Sleeper Agent", "The Puppet Master",
        "The Man Behind the Curtain", "The Big Bad", "The Dragon", "The Henchman", "The Minion",
        "The Cannon Fodder", "The Redshirt", "The Final Girl", "The Scream Queen", "The Tough Guy",
        "The Hardboiled Detective", "The Private Eye", "The Gumshoe", "The Flatfoot", "The Rookie",
        "The Veteran", "The Retired Cop", "The Loose Cannon", "The Vigilante", "The Punisher",
        "The Avenger", "The Mercenary", "The Soldier of Fortune", "The Commando", "The Sniper",
        "The Demolition Man", "The Pilot", "The Navigator", "The Engineer", "The Mechanic",
        "The Doctor", "The Medic", "The Nurse", "The Scientist", "The Researcher", "The Analyst",
        "The Technician", "The Operative", "The Field Agent", "The Handler", "The Director",
        "The Chief", "The Captain", "The General", "The Admiral", "The President", "The King",
        "The Queen", "The Prince", "The Princess", "The Noble", "The Peasant", "The Serf",
        "The Slave", "The Master", "The Servant", "The Butler", "The Maid", "The Cook",
        "The Gardener", "The Driver", "The Pilot", "The Captain", "The Navigator", "The Scout",
        "The Guard", "The Sentry", "The Sentinel", "The Keeper", "The Warden", "The Jailer",
        "The Prisoner", "The Captive", "The Hostage", "The Fugitive", "The Exile", "The Refugee"
    ]
    # Expand to 500+ with variations
    expanded_archetypes = []
    for a in archetypes:
        expanded_archetypes.extend([a, f"reimagined {a}", f"modern {a}", f"classic {a}", f"dark {a}", f"light {a}", f"twisted {a}", f"heroic {a}"])
    add_cat("characters/archetypes", "Fundamental character templates based on Jungian psychology and literary tropes", expanded_archetypes)

    # 2. Professions (General)
    professions = [
        "Accountant", "Actor", "Architect", "Artist", "Astronaut", "Baker", "Banker", "Barber",
        "Biologist", "Blacksmith", "Butcher", "Carpenter", "Chef", "Chemist", "Clerk", "Coach",
        "Dentist", "Designer", "Detective", "Diplomat", "Doctor", "Driver", "Economist", "Editor",
        "Electrician", "Engineer", "Farmer", "Firefighter", "Fisherman", "Florist", "Gardener",
        "Geologist", "Historian", "Journalist", "Judge", "Lawyer", "Librarian", "Lifeguard",
        "Locksmith", "Magician", "Mechanic", "Musician", "Nurse", "Optician", "Painter",
        "Pharmacist", "Photographer", "Physicist", "Pilot", "Plumber", "Police Officer",
        "Politician", "Postman", "Priest", "Professor", "Programmer", "Psychologist",
        "Reporter", "Sailor", "Salesman", "Scientist", "Sculptor", "Secretary", "Security Guard",
        "Singer", "Soldier", "Surgeon", "Tailor", "Teacher", "Technician", "Translator",
        "Truck Driver", "Undertaker", "Veterinarian", "Waiter", "Welder", "Writer", "Zoologist"
    ]
    expanded_profs = []
    for p in professions:
        expanded_profs.extend([p, f"expert {p}", f"novice {p}", f"retired {p}", f"aspiring {p}", f"professional {p}", f"master {p}", f"famous {p}"])
    add_cat("characters/professions", "General modern-day occupations and professions", expanded_profs)

    # 3. Fantasy Occupations
    fantasy_occ = [
        "Alchemist", "Apprentice", "Bard", "Beastmaster", "Blacksmith", "Bounty Hunter", "Cartographer",
        "Cleric", "Commoner", "Courtesan", "Druid", "Enchanter", "Falconer", "Fletcher", "Gladiator",
        "Healer", "Herbalist", "Inquisitor", "Jester", "Knight", "Mage", "Mercenary", "Minstrel",
        "Necromancer", "Noble", "Oracle", "Paladin", "Peasant", "Priest", "Ranger", "Rogue",
        "Sage", "Scribe", "Seer", "Shaman", "Smith", "Sorcerer", "Squire", "Thief", "Troubadour",
        "Warlock", "Witch", "Wizard", "Abbot", "Acolyte", "Archmage", "Assassin", "Astrologer",
        "Battlemage", "Beggar", "Bishop", "Blood Hunter", "Brewmaster", "Captain", "Cardinal",
        "Chamberlain", "Champion", "Chancellor", "Chronomancer", "Conjurer", "Cook", "Cultist",
        "Diviner", "Dragon Rider", "Duelist", "Elementalist", "Exorcist", "Executioner", "Farmer",
        "Fisherman", "Forester", "Gatekeeper", "General", "Grave Digger", "Guard", "Guildmaster",
        "Heralds", "Hermit", "High Priest", "Hunter", "Illusionist", "Innkeeper", "Inquisitor",
        "Jeweler", "Jester", "Judge", "King", "Knight", "Lady", "Librarian", "Lord", "Magician",
        "Maid", "Marshal", "Mayor", "Merchant", "Messenger", "Miller", "Miner", "Monk", "Mystic",
        "Necromancer", "Night Watch", "Noble", "Nun", "Officer", "Oracle", "Outlaw", "Page",
        "Painter", "Paladin", "Peasant", "Philosopher", "Pilgrim", "Pirate", "Poet", "Pope",
        "Potter", "Prince", "Princess", "Priest", "Prophet", "Purse Maker", "Queen", "Ranger",
        "Rat Catcher", "Reeve", "Rogue", "Sailor", "Samurai", "Scholar", "Scribe", "Sculptor",
        "Seer", "Seneschal", "Sergeant", "Servant", "Shaman", "Shepherd", "Sheriff", "Shipwright",
        "Singer", "Slave", "Smith", "Soldier", "Sorcerer", "Squire", "Steward", "Stone Mason",
        "Surgeon", "Squire", "Tailor", "Tanner", "Tavern Keeper", "Tax Collector", "Teacher",
        "Thief", "Torturer", "Trader", "Traveler", "Vagabond", "Vassal", "Vicar", "Village Elder",
        "Warlock", "Warrior", "Watchman", "Weaver", "Witch", "Witch Doctor", "Wizard", "Woodcutter"
    ]
    expanded_fantasy = []
    for f in fantasy_occ:
        expanded_fantasy.extend([f, f"legendary {f}", f"mystical {f}", f"dark {f}", f"royal {f}", f"ancient {f}", f"wandering {f}", f"renegade {f}"])
    add_cat("characters/occupations/fantasy", "Occupations specific to fantasy and medieval settings", expanded_fantasy)

    # 4. Sci-Fi Occupations
    scifi_occ = [
        "Astro-Navigator", "Bio-Engineer", "Cyborg Tech", "Data Miner", "Exoplanet Explorer",
        "Fusion Tech", "Galactic Diplomat", "Holo-Artist", "Interstellar Pilot", "Jetpack Courier",
        "Kinetic Specialist", "Laser Tech", "Mech Pilot", "Nano-Technician", "Orbital Mechanic",
        "Plasma Physicist", "Quantum Coder", "Robot Repairman", "Space Marine", "Terraformer",
        "Universal Translator", "Vacuum Welder", "Warp Drive Engineer", "Xeno-Biologist",
        "Zero-G Athlete", "Android Psychologist", "Bounty Hunter", "Cargo Pilot", "Clone Specialist",
        "Deep Space Miner", "Energy Shield Tech", "Free-Trader", "Gravity Engineer", "Hyper-Space Pilot",
        "Illegal Tech-Runner", "Junk-Scavenger", "Life-Support Tech", "Neural-Link Surgeon",
        "Oxygen Farmer", "Passenger Steward", "Radiation Officer", "Satellite Controller",
        "Telepathic Consultant", "Under-City Scum", "Virtual Reality Architect", "Wasteland Survivor"
    ]
    expanded_scifi = []
    for s in scifi_occ:
        expanded_scifi.extend([s, f"high-tech {s}", f"low-life {s}", f"cybernetic {s}", f"rebel {s}", f"imperial {s}", f"mercenary {s}", f"rogue {s}"])
    add_cat("characters/occupations/scifi", "Occupations specific to science fiction and futuristic settings", expanded_scifi)

    # 5. RPG Classes
    rpg_classes = [
        "Fighter", "Wizard", "Rogue", "Cleric", "Paladin", "Ranger", "Barbarian", "Bard", "Druid",
        "Monk", "Sorcerer", "Warlock", "Artificer", "Alchemist", "Necromancer", "Inquisitor",
        "Summoner", "Shaman", "Cavalier", "Samurai", "Ninja", "Gunslinger", "Swashbuckler",
        "Witch", "Oracle", "Magus", "Occultist", "Psychic", "Medium", "Spiritualist",
        "Kineticist", "Vigilante", "Slayer", "Hunter", "Brawler", "Skald", "Investigator",
        "War-priest", "Blood-rager", "Arcanist", "Red Mage", "Blue Mage", "Black Mage", "White Mage",
        "Dragoon", "Dark Knight", "Berserker", "Gladiator", "Assassin", "Sniper", "Medic",
        "Engineer", "Tactician", "Commander", "Warmaster", "Spellblade", "Nightshade",
        "Shadowdancer", "Horizon Walker", "Dreadnought", "Avatar", "Paragon"
    ]
    expanded_rpg = []
    for c in rpg_classes:
        expanded_rpg.extend([c, f"Level 1 {c}", f"Level 100 {c}", f"Master {c}", f"Apprentice {c}", f"Legendary {c}", f"Fallen {c}", f"Ascended {c}"])
    add_cat("characters/classes/rpg", "Standard character classes found in tabletop and digital RPGs", expanded_rpg)

    # 6. Species (Fantasy)
    fantasy_species = [
        "Human", "Elf", "Dwarf", "Halfling", "Gnome", "Orc", "Goblin", "Troll", "Ogre", "Giant",
        "Centaur", "Minotaur", "Satyr", "Faun", "Dryad", "Nymph", "Siren", "Mermaid", "Merman",
        "Vampire", "Werewolf", "Zombie", "Skeleton", "Ghost", "Wraith", "Lich", "Demon", "Angel",
        "Dragon", "Drake", "Wyvern", "Griffin", "Hippogriff", "Pegasus", "Unicorn", "Phoenix",
        "Chimera", "Hydra", "Manticore", "Sphinx", "Basilisk", "Cockatrice", "Gorgon", "Medusa",
        "Harpy", "Lamia", "Succubus", "Incubus", "Rakshasa", "Djinn", "Efreet", "Marid", "Dao",
        "Kobold", "Gnoll", "Bugbear", "Hobgoblin", "Lizardfolk", "Dragonborn", "Tiefling",
        "Aasimar", "Genasi", "Firbolg", "Goliath", "Tabaxi", "Kenku", "Tortle", "Loxodon",
        "Leonin", "Satyr", "Changeling", "Kalashtar", "Warforged", "Shifter", "Vedalken",
        "Simic Hybrid", "Githyanki", "Githzerai", "Yuan-ti", "Drow", "Svirfneblin", "Duergar"
    ]
    expanded_f_species = []
    for s in fantasy_species:
        expanded_f_species.extend([s, f"Ancient {s}", f"Young {s}", f"Dark {s}", f"Light {s}", f"Corrupted {s}", f"Celestial {s}", f"Primal {s}"])
    add_cat("characters/species/fantasy", "Intelligent races and species from fantasy lore", expanded_f_species)

    # 7. Species (Sci-Fi)
    scifi_species = [
        "Human", "Android", "Cyborg", "Grey Alien", "Reptilian", "Nordic Alien", "Insectoid",
        "Silicon-based Life", "Energy Being", "A.I.", "Nanite Swarm", "Hive Mind", "Martian",
        "Jovian", "Titanian", "Alpha Centaurian", "Sirian", "Pleiadian", "Andromedan",
        "Borg", "Klingon", "Vulcan", "Romulan", "Ferengi", "Cardassian", "Bajoran", "Trill",
        "Talaxian", "Ocampa", "Vidiian", "Hirogen", "8472", "Changelings", "Jem'Hadar", "Vorta",
        "Twi'lek", "Wookiee", "Ewok", "Jawa", "Rodian", "Hutt", "Gungan", "Mon Calamari",
        "Quarren", "Bothan", "Sullustian", "Zabrak", "Togruta", "Kel Dor", "Nautolan"
    ]
    expanded_s_species = []
    for s in scifi_species:
        expanded_s_species.extend([s, f"Cyber-enhanced {s}", f"Post-human {s}", f"Ancient {s}", f"Extinct {s}", f"Hybrid {s}", f"Mutant {s}", f"Cloned {s}"])
    add_cat("characters/species/scifi", "Alien races and artificial lifeforms from sci-fi settings", expanded_s_species)

    # 8. Hairstyles
    hairstyles = [
        "Afro", "Bald", "Beehive", "Bob cut", "Bowl cut", "Braid", "Bun", "Buzz cut", "Chignon",
        "Cornrows", "Crew cut", "Dreadlocks", "Fade", "Fauxhawk", "Fishtail braid", "French braid",
        "Fringe", "Hime cut", "Iroquois", "Ivy League", "Long hair", "Mohawk", "Mullet",
        "Pageboy", "Perm", "Pigtails", "Pixie cut", "Ponytail", "Pompadour", "Shag", "Short hair",
        "Topknot", "Undercut", "Waves", "Wedge", "Victory rolls", "Spiky hair", "Messy hair",
        "Wavy hair", "Curly hair", "Straight hair", "Bald with beard", "Handlebar mustache",
        "Goatee", "Full beard", "Sideburns", "Mutton chops", "Van Dyke beard", "Stubble",
        "Soul patch", "Pencil mustache", "Walrus mustache", "Horseshoe mustache", "Fu Manchu"
    ]
    expanded_hair = []
    for h in hairstyles:
        expanded_hair.extend([h, f"neon {h}", f"messy {h}", f"slicked back {h}", f"wind-swept {h}", f"dyed {h}", f"glowing {h}", f"shaved {h}"])
    add_cat("characters/hairstyles", "Comprehensive list of hair and facial hair styles", expanded_hair)

    # 9. Emotions
    emotions = [
        "Happiness", "Sadness", "Anger", "Fear", "Surprise", "Disgust", "Trust", "Anticipation",
        "Joy", "Trust", "Fear", "Surprise", "Sadness", "Disgust", "Anger", "Anticipation",
        "Serenity", "Acceptance", "Apprehension", "Distraction", "Pensiveness", "Boredom",
        "Annoyance", "Interest", "Ecstasy", "Admiration", "Terror", "Amazement", "Grief",
        "Loathing", "Rage", "Vigilance", "Optimism", "Love", "Submission", "Awe",
        "Disapproval", "Remorse", "Contempt", "Aggressiveness", "Boredom", "Confusion",
        "Contempt", "Contentment", "Curiosity", "Despair", "Disappointment", "Doubt",
        "Embarrassment", "Empathy", "Envy", "Euphoria", "Frustration", "Gratitude",
        "Guilt", "Hope", "Hostility", "Hunger", "Hysteria", "Isolation", "Jealousy",
        "Kindness", "Loneliness", "Lust", "Melancholy", "Nostalgia", "Panic", "Patience",
        "Pity", "Pride", "Regret", "Relief", "Satisfaction", "Shame", "Suffering",
        "Sympathy", "Tenderness", "Worry"
    ]
    expanded_emotions = []
    for e in emotions:
        expanded_emotions.extend([e, f"intense {e}", f"suppressed {e}", f"faked {e}", f"overwhelming {e}", f"subtle {e}", f"uncontrollable {e}", f"fleeting {e}"])
    add_cat("characters/emotions", "Human and non-human emotional states", expanded_emotions)

    # 10. Weapons
    weapons = [
        "Sword", "Dagger", "Axe", "Mace", "Warhammer", "Spear", "Halberd", "Glaive", "Flail",
        "Staff", "Wand", "Bow", "Crossbow", "Sling", "Javelin", "Throwing Knife", "Shuriken",
        "Katana", "Wakizashi", "Naginata", "Rapier", "Cutlass", "Scimitar", "Falchion",
        "Greatsword", "Claymore", "Zweihander", "Morning Star", "Battleaxe", "Greataxe",
        "Trident", "Lance", "Pike", "Quarterstaff", "Club", "Greatclub", "Whip", "Net",
        "Blowgun", "Dart", "Shortbow", "Longbow", "Recurve Bow", "Compound Bow", "Hand Crossbow",
        "Heavy Crossbow", "Pistol", "Revolver", "Rifle", "Shotgun", "Assault Rifle",
        "Sniper Rifle", "Submachine Gun", "Machine Gun", "Minigun", "Rocket Launcher",
        "Grenade Launcher", "Flamethrower", "Plasma Rifle", "Laser Pistol", "Ion Cannon",
        "Pulse Rifle", "Railgun", "Gauss Rifle", "Sonic Gun", "Electric Baton", "Stun Gun",
        "Chainsaw", "Power Sword", "Vibroblade", "Lightsaber", "Blaster", "Disintegrator"
    ]
    expanded_weapons = []
    for w in weapons:
        expanded_weapons.extend([w, f"Enchanted {w}", f"Masterwork {w}", f"Rusty {w}", f"Damaged {w}", f"Glowing {w}", f"Legendary {w}", f"Relic {w}"])
    add_cat("characters/weapons", "Melee, ranged, and futuristic weaponry", expanded_weapons)

    # write to yaml
    output_path = os.path.join(base_dir, "characters_master.yaml")
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, indent=4)

def generate_clothing_master():
    data = {}
    
    def add_cat(path, desc, values):
        data[path] = {
            "description": desc,
            "values": sorted(list(set(values)))
        }

    # 1. Fashion Styles
    fashion_styles = [
        "Techwear", "Streetwear", "Cyberpunk", "Steampunk", "Dieselpunk", "Atompunk", "Solarpunk",
        "Dark Academia", "Light Academia", "Cottagecore", "Gothic", "Emo", "Scene", "Grunge",
        "Punk", "Rockabilly", "Pin-up", "Vintage 20s", "Vintage 50s", "Vintage 70s", "Vintage 90s",
        "Y2K", "Minimalist", "Maximalist", "Avant-Garde", "Haute Couture", "Business Casual",
        "Formal", "Black Tie", "Bohemian", "Preppy", "Athleisure", "Military", "Safari",
        "Western", "Cowboy", "Tiki", "Mod", "Beatnik", "New Wave", "Disco", "Hip Hop",
        "E-Girl", "Soft Boy", "VSCO Girl", "Baddie", "Darkwear", "Warcore", "Glitchcore",
        "Vaporwave", "Synthwave", "Seapunk", "Normcore", "Gorpcore", "Royalcore", "Fairycore"
    ]
    expanded_f_styles = []
    for s in fashion_styles:
        expanded_f_styles.extend([s, f"distressed {s}", f"luxury {s}", f"futuristic {s}", f"retro {s}", f"minimalist {s}", f"oversized {s}", f"tailored {s}"])
    add_cat("clothing/fashion/styles", "Broad fashion movements and aesthetic styles", expanded_f_styles)

    # 2. Fabrics
    fabrics = [
        "Silk", "Cotton", "Linen", "Wool", "Denim", "Leather", "Suede", "Velvet", "Satin",
        "Chiffon", "Organza", "Lace", "Tulle", "Polyester", "Nylon", "Spandex", "Latex",
        "PVC", "Carbon Fiber", "Graphene", "Kevlar", "Fleece", "Cashmere", "Tweed", "Flannel",
        "Corduroy", "Jersey", "Canvas", "Hemp", "Bamboo", "Viscose", "Rayon", "Acetate",
        "Brocade", "Damask", "Jacquard", "Taffeta", "Crepe", "Gingham", "Seersucker",
        "Terry Cloth", "Microfiber", "Neoprene", "Synthetic Fur", "Mink", "Fox Fur",
        "Sheepskin", "Shearling", "Pashmina", "Angora", "Mohair", "Alpaca"
    ]
    expanded_fabrics = []
    for f in fabrics:
        expanded_fabrics.extend([f, f"glossy {f}", f"matte {f}", f"worn {f}", f"dirty {f}", f"holographic {f}", f"translucent {f}", f"metallic {f}"])
    add_cat("clothing/fashion/fabrics", "Textiles and materials used in garment construction", expanded_fabrics)

    # 3. Footwear
    footwear = [
        "Sneakers", "Running Shoes", "Basketball Shoes", "Boots", "Combat Boots", "Chelsea Boots",
        "Cowboy Boots", "Hiking Boots", "Loafers", "Oxfords", "Brogues", "Derbies", "Monk Straps",
        "Boat Shoes", "Sandals", "Flip Flops", "Slides", "Espadrilles", "Moccasins", "Slippers",
        "Clogs", "Mules", "Pumps", "Stilettos", "Wedges", "Flats", "Ballerina Flats", "Mary Janes",
        "Kitten Heels", "Platform Shoes", "Creepers", "Thigh-high Boots", "Ankle Boots",
        "Work Boots", "Wellies", "Uggs", "Croc", "Birkenstocks", "Dr Martens", "Vans",
        "Converse", "Timberlands", "Tabi Boots", "Geta", "Zori"
    ]
    expanded_footwear = []
    for f in footwear:
        expanded_footwear.extend([f, f"scuffed {f}", f"neon {f}", f"robotic {f}", f"winged {f}", f"glowing {f}", f"armored {f}", f"vintage {f}"])
    add_cat("clothing/fashion/footwear", "Types of shoes and boots", expanded_footwear)

    # 4. Damage States
    damage_states = [
        "Pristine", "New", "Clean", "Lightly Worn", "Worn", "Heavily Worn", "Distressed",
        "Frayed", "Tattered", "Ripped", "Torn", "Shredded", "Burned", "Singed", "Charred",
        "Bleached", "Stained", "Muddy", "Bloody", "Dirty", "Dusty", "Rusty", "Corroded",
        "Cracked", "Peeling", "Faded", "Discolored", "Patched", "Repaired", "Stitched",
        "Darned", "Weathered", "Aged", "Antiqued", "Battle-worn", "Scuffed", "Dented",
        "Battered", "Bruised", "Broken", "Shattered", "Splintered", "Eroded", "Washed out"
    ]
    expanded_damage = []
    for d in damage_states:
        expanded_damage.extend([d, f"slightly {d}", f"extremely {d}", f"artistically {d}", f"randomly {d}", f"permanently {d}", f"freshly {d}", f"old {d}"])
    add_cat("clothing/damage_states", "Condition and degradation states of clothing and gear", expanded_damage)

    # write to yaml
    output_path = os.path.join(base_dir, "clothing_master.yaml")
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, indent=4)

if __name__ == "__main__":
    generate_characters_master()
    generate_clothing_master()
    print("Generated characters_master.yaml and clothing_master.yaml.")
