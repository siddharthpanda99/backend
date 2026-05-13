import os

base_dir = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Resources\wildcards"

def expand_people_extras():
    archetypes_path = os.path.join(base_dir, "people", "archetypes.yaml")
    roles_path = os.path.join(base_dir, "people", "roles.yaml")
    
    archetypes = [
        "the hero", "the mentor", "the rebel", "the magician", "the lover", "the explorer",
        "the creator", "the ruler", "the caregiver", "the innocent", "the sage", "the jester",
        "the trickster", "the shadow", "the herald", "the threshold guardian", "the shapeshifter",
        "the anima", "the animus", "the persona", "the self", "the wise old man", "the great mother",
        "the divine child", "the orphan", "the wanderer", "the martyr", "the warrior", "the amazon",
        "the femme fatale", "the damsel in distress", "the white knight", "the dark knight",
        "the fallen angel", "the messiah", "the antichrist", "the prophet", "the hermit",
        "the glutton", "the miser", "the spendthrift", "the coward", "the bully", "the victim",
        "the savior", "the executioner", "the judge", "the jury", "the advocate", "the diplomat",
        "the spy", "the assassin", "the thief", "the pirate", "the bandit", "the outlaw",
        "the fugitive", "the exile", "the wanderer", "the pilgrim", "the seeker", "the finder",
        "the loser", "the winner", "the champion", "the underdog", "the dark horse",
        "the silver spoon", "the self-made man", "the entrepreneur", "the visionary",
        "the idealist", "the realist", "the pragmatist", "the cynic", "the skeptic",
        "the believer", "the fanatic", "the zealot", "the martyr", "the saint", "the sinner"
    ]
    
    roles = [
        "king", "queen", "prince", "princess", "duke", "duchess", "count", "countess", "baron", "baroness",
        "knight", "squire", "page", "lord", "lady", "vassal", "serf", "peasant", "merchant", "artisan",
        "cleric", "monk", "nun", "abbot", "abbess", "bishop", "cardinal", "pope", "emperor", "empress",
        "tsar", "tsarina", "pharaoh", "shogun", "samurai", "ninja", "ronin", "viking", "berserker",
        "druid", "shaman", "witch doctor", "oracle", "seer", "prophet", "priest", "priestess",
        "alchemist", "necromancer", "sorcerer", "sorceress", "wizard", "warlock", "mage", "enchanter",
        "paladin", "ranger", "thief", "assassin", "bard", "monk", "cleric", "druid", "barbarian",
        "fighter", "warlock", "sorcerer", "wizard", "artificer", "gunslinger", "cowboy", "sheriff",
        "outlaw", "bandit", "bounty hunter", "mercenary", "soldier", "officer", "general", "admiral",
        "pilot", "astronaut", "space marine", "cyborg", "android", "robot", "alien", "mutant",
        "superhero", "supervillain", "sidekick", "vigilante", "detective", "inspector", "agent",
        "spy", "operative", "hacker", "netrunner", "technomancer", "biopunk", "steampunk",
        "dieselpunk", "cyberpunk", "vaporwave", "synthwave", "retrowave", "outrun"
    ]
    
    with open(archetypes_path, 'w', encoding='utf-8') as f:
        f.write("archetypes:\n")
        for item in archetypes:
            f.write(f"  - {item}\n")
            
    with open(roles_path, 'w', encoding='utf-8') as f:
        f.write("roles:\n")
        for item in roles:
            f.write(f"  - {item}\n")

expand_people_extras()
print("Expanded people extras (archetypes and roles).")
