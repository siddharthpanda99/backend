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

# --- DATA: ANIMALS ---
mammals_predators = ["Lion", "Tiger", "Leopard", "Jaguar", "Cheetah", "Snow Leopard", "Clouded Leopard", "Gray Wolf", "Grizzly Bear", "Polar Bear", "Black Bear", "Cougar", "Lynx", "Bobcat", "Wolverine", "Hyena", "African Wild Dog", "Coyote", "Red Fox", "Arctic Fox", "Fennec Fox", "Badger", "Honey Badger", "Mongoose", "Ocelot", "Serval", "Caracal", "Komodo Dragon", "Tasmanian Devil", "Fisher"]
mammals_herbivores = ["Elephant", "Giraffe", "White Rhino", "Black Rhino", "Hippopotamus", "Water Buffalo", "Cape Buffalo", "Bison", "Moose", "Elk", "Red Deer", "Fallow Deer", "Reindeer", "Caribou", "Zebra", "Wildebeest", "Gazelle", "Impala", "Oryx", "Kudu", "Eland", "Okapi", "Camel", "Llama", "Alpaca", "Guanaco", "Vicuna", "Tapir", "Capybara", "Beaver"]
birds_of_prey = ["Golden Eagle", "Bald Eagle", "Peregrine Falcon", "Gyrfalcon", "Red-tailed Hawk", "Cooper's Hawk", "Osprey", "Harpy Eagle", "Great Horned Owl", "Snowy Owl", "Barn Owl", "Barred Owl", "Screech Owl", "Kestrel", "Merlin", "Goshawk", "Secretary Bird", "Andean Condor", "California Condor", "Vulture", "Buzzard", "Kite", "Sparrowhawk", "Saker Falcon", "Prairie Falcon"]
birds_song_tropical = ["Nightingale", "Robin", "Cardinal", "Blue Jay", "Goldfinch", "Scarlet Macaw", "Blue and Gold Macaw", "Hyacinth Macaw", "Toucan", "Cockatoo", "African Gray Parrot", "Budgerigar", "Kingfisher", "Hummingbird", "Sunbird", "Lyrebird", "Woodpecker", "Cuckoo", "Oriole", "Warbler", "Thrush", "Lark", "Swallow", "Swift", "Mockingbird"]
snakes_serpents = ["King Cobra", "Black Mamba", "Green Mamba", "Rattlesnake", "Copperhead", "Cottonmouth", "Gaboon Viper", "Russell's Viper", "Inland Taipan", "Coastal Taipan", "Tiger Snake", "Brown Snake", "Anaconda", "Reticulated Python", "Burmese Python", "Boa Constrictor", "Emerald Tree Boa", "Corn Snake", "King Snake", "Garter Snake", "Sea Snake", "Coral Snake", "Death Adder", "Boomslang", "Python"]
lizards_crocodilians = ["Komodo Dragon", "Gila Monster", "Bearded Dragon", "Green Iguana", "Chameleon", "Gecko", "Monitor Lizard", "Skink", "Anole", "Thorny Devil", "Frilled Lizard", "Saltwater Crocodile", "Nile Crocodile", "American Alligator", "Caiman", "Gharial", "Leatherback Sea Turtle", "Galapagos Tortoise", "Snapping Turtle", "Box Turtle"]
amphibians = ["Bullfrog", "Tree Frog", "Poison Dart Frog", "Wood Frog", "Leopard Frog", "African Clawed Frog", "Common Toad", "Fire-bellied Toad", "Cane Toad", "Axolotl", "Fire Salamander", "Spotted Salamander", "Newt", "Caecilian", "Mudpuppy", "Hellbender", "Siren", "Proteus", "Triturus", "Ranitomeya"]
fish_freshwater = ["Largemouth Bass", "Smallmouth Bass", "Rainbow Trout", "Brown Trout", "Brook Trout", "Atlantic Salmon", "Chinook Salmon", "Sockeye Salmon", "Northern Pike", "Muskellunge", "Walleye", "Yellow Perch", "Catfish", "Carp", "Goldfish", "Koi", "Arowana", "Arapaima", "Piranha", "Electric Eel", "Sturgeon", "Paddlefish", "Gars", "Bowfin", "Discus"]
fish_saltwater_sharks = ["Great White Shark", "Tiger Shark", "Hammerhead Shark", "Whale Shark", "Bull Shark", "Mako Shark", "Blue Shark", "Nurse Shark", "Thresher Shark", "Manta Ray", "Stingray", "Eagle Ray", "Blue Marlin", "Swordfish", "Sailfish", "Yellowfin Tuna", "Bluefin Tuna", "Barracuda", "Grouper", "Snapper", "Mahi-mahi", "Clownfish", "Angelfish", "Lionfish", "Moray Eel"]
marine_mammals = ["Blue Whale", "Humpback Whale", "Fin Whale", "Sperm Whale", "Orca", "Bottlenose Dolphin", "Spinner Dolphin", "Beluga Whale", "Narwhal", "Harbor Porpoise", "Manatee", "Dugong", "Walrus", "Elephant Seal", "Harbor Seal", "California Sea Lion", "Stellar Sea Lion", "Fur Seal", "Sea Otter", "Polar Bear (Marine)"]
cephalopods_deepsea = ["Giant Squid", "Colossal Squid", "Humboldt Squid", "Common Octopus", "Blue-ringed Octopus", "Mimic Octopus", "Vampire Squid", "Cuttlefish", "Nautilus", "Deep Sea Anglerfish", "Fangtooth Fish", "Gulper Eel", "Blobfish", "Frilled Shark", "Giant Isopod", "Oarfish", "Dumbo Octopus", "Glass Squid", "Hatchetfish", "Barreleye Fish"]
insects_flying = ["Monarch Butterfly", "Swallowtail Butterfly", "Honeybee", "Bumblebee", "Hornet", "Wasp", "Dragonfly", "Damselfly", "Cicada", "Moth", "Luna Moth", "Atlas Moth", "Firefly", "Ladybug", "Mosquito", "Housefly", "Fruit Fly", "Grasshopper", "Locust", "Praying Mantis", "Mayfly", "Lacewing", "Caddisfly", "Stonefly", "Gnat"]
insects_crawling = ["Ant", "Carpenter Ant", "Fire Ant", "Bullet Ant", "Beetle", "Stag Beetle", "Hercules Beetle", "Scarab Beetle", "Dung Beetle", "Cockroach", "Termite", "Earwig", "Silverfish", "Centipede", "Millipede", "Walking Stick", "Leaf Insect", "Cricket", "Bedbug", "Louse", "Flea", "Tick", "Mite", "Pillbug", "Woodlouse"]
arachnids_scorpions = ["Tarantula", "Black Widow", "Brown Recluse", "Orb Weaver", "Jumping Spider", "Wolf Spider", "Huntsman Spider", "Crab Spider", "Trapdoor Spider", "Water Spider", "Emperor Scorpion", "Deathstalker Scorpion", "Bark Scorpion", "Whip Scorpion", "Pseudoscorpion", "Harvestman", "Camel Spider", "Tick", "Mite", "Amblypygid"]
primates_prosimians = ["Gorilla", "Chimpanzee", "Bonobo", "Orangutan", "Gibbon", "Mandrill", "Baboon", "Rhesus Macaque", "Japanese Macaque", "Spider Monkey", "Howler Monkey", "Capuchin", "Marmoset", "Tamarin", "Squirrel Monkey", "Proboscis Monkey", "Langur", "Colobus", "Lemur", "Ring-tailed Lemur", "Aye-aye", "Loris", "Tarsier", "Galago", "Bushbaby"]
rodents_lagomorphs = ["Rat", "Mouse", "Squirrel", "Chipmunk", "Groundhog", "Prairie Dog", "Beaver", "Porcupine", "Guinea Pig", "Hamster", "Gerbil", "Chinchilla", "Degu", "Capybara", "Mara", "Agouti", "Paca", "Vole", "Lemming", "Muskrat", "Rabbit", "Hare", "Jackrabbit", "Cottontail", "Pika"]
marsupials_monotremes = ["Kangaroo", "Wallaby", "Wallaroo", "Koala", "Wombat", "Opossum", "Sugar Glider", "Tasmanian Devil", "Quokka", "Bandicoot", "Bilby", "Numbat", "Quoll", "Tree-kangaroo", "Phascogale", "Possum", "Platypus", "Short-beaked Echidna", "Long-beaked Echidna"]
prehistoric_extinct = ["Tyrannosaurus Rex", "Triceratops", "Velociraptor", "Stegosaurus", "Brachiosaurus", "Spinosaurus", "Diplodocus", "Ankylosaurus", "Pterodactyl", "Plesiosaur", "Mosasaur", "Woolly Mammoth", "Saber-toothed Tiger", "Giant Ground Sloth", "Dire Wolf", "Megatherium", "Doedicurus", "Irish Elk", "Dodo", "Moa", "Thylacine", "Passenger Pigeon", "Quagga", "Great Auk", "Steller's Sea Cow"]
fantasy_mythological = ["Dragon", "Griffin", "Phoenix", "Unicorn", "Pegasus", "Hippogriff", "Chimera", "Hydra", "Manticore", "Sphinx", "Basilisk", "Cockatrice", "Cerberus", "Kraken", "Leviathan", "Behemoth", "Minotaur", "Centaur", "Satyr", "Faun", "Kelpie", "Selkie", "Kappa", "Tengu", "Kitsune"]
domestic_farm = ["Dog", "Cat", "Horse", "Cow", "Bull", "Sheep", "Goat", "Pig", "Chicken", "Rooster", "Duck", "Goose", "Turkey", "Donkey", "Mule", "Rabbit", "Ferret", "Hamster", "Guinea Pig", "Llama", "Alpaca", "Yak", "Water Buffalo", "Camel", "Reindeer"]

# --- DATA: SPORTS & MARTIAL ARTS ---
striking = ["Boxing", "Muay Thai", "Lethwei", "Savate", "Karate", "Taekwondo", "Kickboxing", "Sanshou", "Wing Chun", "Tang Soo Do", "Capoeira", "Pencak Silat", "Panantukan", "Burmese Boxing", "Khmer Boxing", "Yaw-Yan", "Muay Boran", "Bajiquan", "Choy Li Fut", "Hung Ga", "Jeet Kune Do", "Kajukenbo", "Krav Maga", "Pradal Serey", "Shaolin Kung Fu"]
grappling = ["Bokh", "Brazilian Jiu-Jitsu", "Catch Wrestling", "Danzan Ryu", "Judo", "Jujutsu", "Luta Livre", "Sambo", "Schwingen", "Shuai Jiao", "Sumo", "Wrestling", "Aikido", "Hapkido", "Shooto", "Vale Tudo", "Dumog", "Glima", "Malla-yuddha", "Pehlwani", "Ssireum", "Ya\u011fl\u0131 g\u00fcre\u015f", "Gouren", "Cornish Wrestling", "Khuresh"]
weaponry = ["Arnis", "Eskrima", "Kali", "Bojutsu", "Canne de Combat", "Fencing", "Gatka", "Gungsol", "Haidong Gumdo", "Hanbojutsu", "HEMA", "Iaido", "Itto-Ryu", "Jodo", "Jukendo", "Kendo", "Kenjutsu", "Kobudo", "Kyudo", "Mau Rakau", "Naginatajutsu", "Silambam", "Sojutsu", "Krabi-Krabong", "Singlestick"]
internal = ["Tai Chi", "Baguazhang", "Xingyiquan", "Liuhebafa", "Yiquan", "Ziranmen", "Qigong", "Neigong", "Aikido", "Hapkido", "Judo", "Jujutsu", "Baji Quan", "Bak Mei", "Southern Praying Mantis", "Wudang Sword", "Fujian White Crane", "Wing Chun", "Kalaripayattu", "Silat", "Systema", "Ki Aikido", "Wad\u014d-ry\u016b", "Shorinji Kempo", "Yoseikan Budo"]
combat_sports = ["MMA", "Kickboxing", "Muay Thai", "Boxing", "Sport BJJ", "Combat Sambo", "Vale Tudo", "Shooto", "Pankration", "Sanda", "Lethwei", "Savate", "Karate Combat", "Taekwondo", "Judo", "Wrestling", "Submission Grappling", "Bare Knuckle Boxing", "BKFC", "Slap Fighting"]
team_ball = ["Soccer", "Basketball", "American Football", "Rugby Union", "Rugby League", "Cricket", "Baseball", "Softball", "Field Hockey", "Lacrosse", "Handball", "Volleyball", "Water Polo", "Beach Volleyball", "Australian Rules Football", "Gaelic Football", "Hurling", "Bandy", "Floorball", "Netball", "Sepak Takraw", "Ultimate Frisbee", "Korfball", "Polo"]
racket_net = ["Tennis", "Badminton", "Squash", "Table Tennis", "Volleyball", "Beach Volleyball", "Racquetball", "Padel", "Pickleball", "Real Tennis", "Basque Pelota", "Jai Alai", "Frontenis", "Speed-ball", "Soft Tennis", "Racketlon", "Crossminton", "Ball Badminton", "Biribol", "Footvolley"]
water_sports = ["Surfing", "Diving", "Swimming", "Water Polo", "Artistic Swimming", "Kayaking", "Canoeing", "Rowing", "Sailing", "Kitesurfing", "Windsurfing", "Wakeboarding", "Waterskiing", "Paddleboarding", "Free-diving", "Scuba Diving", "Snorkeling", "Bodyboarding", "Skimboarding", "Jet Skiing"]
winter_sports = ["Alpine Skiing", "Snowboarding", "Cross-country Skiing", "Ice Hockey", "Figure Skating", "Speed Skating", "Short Track Speed Skating", "Curling", "Bobsleigh", "Luge", "Skeleton", "Biathlon", "Freestyle Skiing", "Ski Jumping", "Nordic Combined", "Bandy", "Ice Climbing", "Sled Dog Racing", "Snowshoeing", "Snowmobiling"]
motorsport = ["Formula 1", "Formula E", "IndyCar", "NASCAR", "WRC", "MotoGP", "WSBK", "Isle of Man TT", "Motocross", "Supercross", "Dakar Rally", "Le Mans", "GT World Challenge", "Formula 2", "Formula 3", "Karting", "NHRA", "Formula Drift", "Stock Car Racing", "BTCC"]
athletics = ["Sprinting", "Middle-distance Running", "Long-distance Running", "Marathon", "Hurdles", "Steeplechase", "Relay", "Racewalking", "High Jump", "Pole Vault", "Long Jump", "Triple Jump", "Shot Put", "Discus Throw", "Hammer Throw", "Javelin Throw", "Decathlon", "Heptathlon", "Cross Country", "Trail Running"]
extreme_urban = ["Parkour", "Freerunning", "Skateboarding", "BMX", "Aggressive Inline", "Scooter", "Rock Climbing", "Free Soloing", "Base Jumping", "Skydiving", "Bungee Jumping", "Caving", "Urban Exploration", "Slacklining", "Highlining", "Buildering", "Sandboarding", "Street Sledding", "Mountain Boarding", "Drift Triking"]
precision_target = ["Archery", "Golf", "Shooting", "Bowling", "Darts", "Billiards", "Croquet", "Petanque", "Bocce", "Curling", "Horseshoes", "Quoits", "Axe Throwing", "Knife Throwing", "Disc Golf", "Footgolf", "Miniature Golf", "Slingshot Shooting", "Crossbow Shooting", "Airsoft Target"]
strength_power = ["Powerlifting", "Olympic Weightlifting", "Strongman", "CrossFit", "Bodybuilding", "Arm Wrestling", "Mas-wrestling", "Highland Games", "Tug of War", "Kettlebell Lifting", "Stone Lifting", "Grip Strength", "Log Lifting", "Beer Stein Holding", "Functional Fitness", "Calisthenics", "Street Workout", "Caber Toss", "Weight for Height", "Log Rolling"]
fantasy_sports = ["Quidditch", "Podracing", "Blitzball", "Grifball", "Rocket League", "Zero-G Football", "Rollerball", "The Hunger Games", "Lightcycle Racing", "Blood Bowl", "Huttball", "Pyramid", "Anbo-jyutsu", "Parrises Squares", "Robot Combat", "Mech Fighting", "Speeder Bike Racing", "Floater Racing", "Holo-Chess", "Grav-Ball"]

# --- EXECUTION ---
root_dir = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Resources\wildcards\collections"
animal_dir = os.path.join(root_dir, "animals")
sports_dir = os.path.join(root_dir, "sports_and_martial_arts")

os.makedirs(animal_dir, exist_ok=True)
os.makedirs(sports_dir, exist_ok=True)

# Animals
save_txt(os.path.join(animal_dir, "mammals_predators.txt"), expand(mammals_predators, 300))
save_txt(os.path.join(animal_dir, "mammals_herbivores.txt"), expand(mammals_herbivores, 300))
save_txt(os.path.join(animal_dir, "birds_of_prey.txt"), expand(birds_of_prey, 300))
save_txt(os.path.join(animal_dir, "birds_song_tropical.txt"), expand(birds_song_tropical, 300))
save_txt(os.path.join(animal_dir, "snakes_serpents.txt"), expand(snakes_serpents, 300))
save_txt(os.path.join(animal_dir, "lizards_crocodilians.txt"), expand(lizards_crocodilians, 300))
save_txt(os.path.join(animal_dir, "amphibians.txt"), expand(amphibians, 300))
save_txt(os.path.join(animal_dir, "fish_freshwater.txt"), expand(fish_freshwater, 300))
save_txt(os.path.join(animal_dir, "fish_saltwater_sharks.txt"), expand(fish_saltwater_sharks, 300))
save_txt(os.path.join(animal_dir, "marine_mammals.txt"), expand(marine_mammals, 300))
save_txt(os.path.join(animal_dir, "cephalopods_deepsea.txt"), expand(cephalopods_deepsea, 300))
save_txt(os.path.join(animal_dir, "insects_flying.txt"), expand(insects_flying, 300))
save_txt(os.path.join(animal_dir, "insects_crawling.txt"), expand(insects_crawling, 300))
save_txt(os.path.join(animal_dir, "arachnids_scorpions.txt"), expand(arachnids_scorpions, 300))
save_txt(os.path.join(animal_dir, "primates_prosimians.txt"), expand(primates_prosimians, 300))
save_txt(os.path.join(animal_dir, "rodents_lagomorphs.txt"), expand(rodents_lagomorphs, 300))
save_txt(os.path.join(animal_dir, "marsupials_monotremes.txt"), expand(marsupials_monotremes, 300))
save_txt(os.path.join(animal_dir, "prehistoric_extinct.txt"), expand(prehistoric_extinct, 300))
save_txt(os.path.join(animal_dir, "fantasy_mythological.txt"), expand(fantasy_mythological, 300))
save_txt(os.path.join(animal_dir, "domestic_farm.txt"), expand(domestic_farm, 300))

# Sports
save_txt(os.path.join(sports_dir, "martial_arts_striking.txt"), expand(striking, 300))
save_txt(os.path.join(sports_dir, "martial_arts_grappling.txt"), expand(grappling, 300))
save_txt(os.path.join(sports_dir, "martial_arts_weaponry.txt"), expand(weaponry, 300))
save_txt(os.path.join(sports_dir, "martial_arts_internal.txt"), expand(internal, 300))
save_txt(os.path.join(sports_dir, "modern_combat_sports.txt"), expand(combat_sports, 300))
save_txt(os.path.join(sports_dir, "sports_team_ball.txt"), expand(team_ball, 300))
save_txt(os.path.join(sports_dir, "sports_racket_net.txt"), expand(racket_net, 300))
save_txt(os.path.join(sports_dir, "sports_water.txt"), expand(water_sports, 300))
save_txt(os.path.join(sports_dir, "sports_winter.txt"), expand(winter_sports, 300))
save_txt(os.path.join(sports_dir, "sports_motorsport.txt"), expand(motorsport, 300))
save_txt(os.path.join(sports_dir, "sports_athletics.txt"), expand(athletics, 300))
save_txt(os.path.join(sports_dir, "sports_extreme_urban.txt"), expand(extreme_urban, 300))
save_txt(os.path.join(sports_dir, "sports_precision_target.txt"), expand(precision_target, 300))
save_txt(os.path.join(sports_dir, "sports_strength_power.txt"), expand(strength_power, 300))
save_txt(os.path.join(sports_dir, "sports_fantasy_futuristic.txt"), expand(fantasy_sports, 300))

print("Expansion Complete.")
