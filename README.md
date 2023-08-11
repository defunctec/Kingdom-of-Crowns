# Kingdom of Crowns - Discord RPG Bot

## Description

Kingdom of Crowns is a Discord bot that enables a emote/text-based RPG experience directly in Discord. Traverse through a vast, intricate world, challenge ferocious monsters, gather exclusive loot, and interact in an engaging community. With a tile map design, players can move right with the game becoming progressively difficult. Confront mobs and bosses to level up, collect gold and pick up items. The game comes with a basic inventory and "residential storage" which can also be used to equip items. As a player levels up, their attributes increase providing more Health, Mana and damage. Attributes are

1. Strength - Provides Health points and contributes to Damage points
2. Agility - Increases chances of dodging attacks
3. Intelligence - Provides Mana points and contributes to Damage points
4. Stamina - Higher Stamina reduces damage reduction due to multiple attacks during battle

## Table of Contents

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [Database](#database)
4. [Usage](#usage)
5. [Contributing](#contributing)

## Installation
[Back to top](#top)
#### Server setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python
sudo apt-get install python3.11
sudo apt-get install python3-dev default-libmysqlclient-dev libssl-dev libcairo2-dev pkg-config -y
sudo apt install pip -y
pip install pycairo

# Install php
sudo apt install php libapache2-mod-php -y
sudo systemctl restart apache2

# Install the database
sudo apt install mysql-server -y
sudo mysql_secure_installation

# Install phpmyadmin for database management
sudo apt install phpmyadmin -y

# Open this file
nano /etc/apache2/apache2.conf
# And add this to the bottom
Include /etc/phpmyadmin/apache.conf
```
#### Game setup
```bash
# Clone the repository:
git clone https://github.com/defunctec/Kingdom-of-Crowns.git /home/Kingdom-of-Crowns

# Change directory into the project:
cd /home/Kingdom-of-Crowns

# Install the requirements:
pip install -r requirements.txt
```

#### Add database tables
[Database](#database)

#### Download the Crown(CRW) client
```bash
wget "https://github.com/Crowndev/crown-core/releases/download/v0.14.0.4/Crown-0.14.0.4-Linux64.zip" -O $dir/crown.zip
```

#### Download the watchdog script to help maintain the Crown client.
```bash
wget "https://raw.githubusercontent.com/Crowndev/crowncoin/master/scripts/crownwatch.sh" -O $dir/crownwatch.sh
```

#### Unzip and install the Crown package
```bash
sudo apt install unzip -y
sudo unzip -qd $dir/crown $dir/crown.zip
sudo cp -f $dir/crown/*/bin/* /usr/local/bin/
sudo cp -f $dir/crown/*/lib/* /usr/local/lib/
sudo chmod +x $dir/crownwatch.sh
sudo cp -f $dir/crownwatch.sh /usr/local/bin
```

#### First run the Crown client to create files, it will fail
```bash
sudo crownd
```
#### Create or edit the Crown config file
```bash
nano .crown/crown.conf
```
#### Add this with your client detailss
```bash
rpcuser=rpcusername
rpcpassword=rpcpassword
walletnotify=/usr/bin/python3 /home/Kingdom-of-Crowns/transaction_handler.py %s
maxtxfee=0.1
```
#### Run the Crown client again, leave to sync.
```bash
sudo crownd
```

#### You should obtain a new address to use as the admin address for any change transactions
```bash
sudo crown-cli getnewaddress koc_admin
```

#### Optional - Create crontab entries to restart the Crown client and game
```bash
sudo crontab -e
```

```bash
@reboot /usr/bin/python3 /home/Kingdom-of-Crowns/gameBot.py > /home/Kingdom-of-Crowns/cron.log 2>&1
@reboot crownd -daemon
```


## Configuration
[Back to top](#top)
#### Change the config.py to reflect your credentials

```

################################################
################################################
    88888888888888888 CORE 88888888888888888
################################################
################################################

# Database configuration
DB_HOST = 'localhost'
DB_USER = 'yourusername'
DB_PASSWORD = 'yourpassword'
DB_NAME = 'kingdom_of_crowns'

# Force script to hold for a duration of time to allow database to start 
SLEEP_TIME = 60

# The Discord channel in which the bot will listen to commands
CHANNEL_ID = yourchannelid

# The total amount of game tiles
TOTAL_TILES = 103

#Discord Bot token, private
BOT_TOKEN = 'yourdiscordbottoken'

# Time before game thread closes
INACTIVE_TIME = 300

################################################
################################################
    88888888888888888 CROWN 8888888888888888
################################################
################################################

# RPC Details
RPC_USER = 'rpcuser'
RPC_PASSWORD = 'RPC_PASSWORD = 'rpcpassword'

# Return address for change (Admin owned address)(Example address, please change)
CHANGE_ADDRESS = 'CRWDv7Hu412jEGyswZSqD9PGPH2ajM5wGhP2'

# Confirmations needed to approve a transaction
CONFS_NEEDED = 6

################################################
################################################
    8888888888888 MECHANICS 8888888888888
################################################
################################################

# Battle timeout
BATTLE_TIMEOUT = 600

# The single item which a player starts with, default "Filthy Peasant Cloth"
STARTING_ARMOUR_ID = 1
STARTING_ARMOUR_CLASS = 'armour'

# Set the default reduction in damage, agility lowers the reduction
DEFAULT_AGILITY_REDUCTION = 0.15

# Boss Chance of Spawning
DODGE_PER_AGILITY = 0.003

# Boss Chance of Spawning (Default = 0.02)
SPAWN_BOSS_CHANCE = 0.02

# Drop chances
BOSS_DROP_CHANCE = 0.99
MOB_DROP_CHANCE = 0.65

# Rarity Weights
RARITY_WEIGHTS = {
    'Common': 0.7,
    'Rare': 0.2,
    'Epic': 0.05,
    'Legendary': 0.03
    }

# Player default conversions
HEALTH_PER_STRENGTH = 3
MANA_PER_INTELLIGENCE = 2

# Player default conversions
DAMAGE_PER_STRENGTH = 1
DAMAGE_PER_INTELLIGENCE = 1

# How much gold to drop per strength of the mob/boss
MIN_GOLD_PER_STRENGTH = 0
MAX_GOLD_PER_STRENGTH = 3
```

## Database
[Back to top](#top)
#### Insert into MYSQL database

```

CREATE DATABASE IF NOT EXISTS kingdom_of_crowns;

USE kingdom_of_crowns;

CREATE TABLE IF NOT EXISTS players (
    id INT AUTO_INCREMENT PRIMARY KEY,
    discord_id BIGINT NOT NULL UNIQUE,
    crw_address VARCHAR(255) NOT NULL,
    crw_balance DECIMAL(18, 2) DEFAULT 0.00,
    current_gold INT DEFAULT 0,
    player_rank VARCHAR(255) DEFAULT 'Squire',
    activated BOOLEAN DEFAULT FALSE,
    payment_address VARCHAR(255),
    tier INT DEFAULT 0,
    current_health INT DEFAULT 0,
    current_mana INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS player_attributes (
    discord_id BIGINT PRIMARY KEY,
    strength INT DEFAULT 5,
    agility INT DEFAULT 4,
    intelligence INT DEFAULT 1,
    stamina INT DEFAULT 3,
    health INT DEFAULT 0,
    mana INT DEFAULT 0,
    xp INT DEFAULT 0,
    level INT DEFAULT 1,
    FOREIGN KEY (discord_id) REFERENCES players(discord_id)
);

CREATE TABLE weapons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    town VARCHAR(100),
    name VARCHAR(100),
    weapon_type VARCHAR(100),
    class VARCHAR(100),
    rarity VARCHAR(100),
    strength INT,
    agility INT,
    intelligence INT,
    stamina INT,
    price DECIMAL(10, 2),
    description TEXT
);

CREATE TABLE IF NOT EXISTS armour (
    id INT AUTO_INCREMENT PRIMARY KEY,
    town VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(255) NOT NULL,
    class VARCHAR(255) NOT NULL,
    strength INT NOT NULL,
    agility INT NOT NULL,
    intelligence INT NOT NULL,
    stamina INT NOT NULL,
    rarity VARCHAR(255) NOT NULL,
    price DECIMAL(10, 2),
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    class VARCHAR(255) NOT NULL,
    strength INT DEFAULT 0,
    agility INT DEFAULT 0,
    intelligence INT DEFAULT 0,
    stamina INT DEFAULT 0,
    rarity VARCHAR(255) NOT NULL,
    price DECIMAL(10, 2),
    description TEXT
);

CREATE TABLE IF NOT EXISTS map_tiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    area_name VARCHAR(255) NOT NULL,
    tile_name VARCHAR(255) NOT NULL,
    tile_type VARCHAR(255) NOT NULL,
    description TEXT,
    chance_mob_encounter FLOAT DEFAULT 0.0,
    UNIQUE (tile_name)
);

CREATE TABLE IF NOT EXISTS player_inventory (
    id INT AUTO_INCREMENT PRIMARY KEY,
    discord_id BIGINT NOT NULL,
    equipped_weapon_id INT,
    equipped_weapon_class VARCHAR(20),
    equipped_helmet_id INT,
    equipped_helmet_class VARCHAR(20),
    equipped_chest_id INT,
    equipped_chest_class VARCHAR(20),
    equipped_legs_id INT,
    equipped_legs_class VARCHAR(20),
    equipped_feet_id INT,
    equipped_feet_class VARCHAR(20),
    equipped_amulet_id INT,
    equipped_amulet_class VARCHAR(20),
    equipped_ring1_id INT,
    equipped_ring1_class VARCHAR(20),
    equipped_ring2_id INT,
    equipped_ring2_class VARCHAR(20),
    equipped_charm_id INT,
    equipped_charm_class VARCHAR(20),
    item_slot1_id INT,
    item_slot1_class VARCHAR(20),
    item_slot2_id INT,
    item_slot2_class VARCHAR(20),
    item_slot3_id INT,
    item_slot3_class VARCHAR(20),
    item_slot4_id INT,
    item_slot4_class VARCHAR(20),
    item_slot5_id INT,
    item_slot5_class VARCHAR(20),
    item_slot6_id INT,
    item_slot6_class VARCHAR(20),
    item_slot7_id INT,
    item_slot7_class VARCHAR(20),
    item_slot8_id INT,
    item_slot8_class VARCHAR(20),
    total_strength INT DEFAULT 0,
    total_agility INT DEFAULT 0,
    total_intelligence INT DEFAULT 0,
    total_stamina INT DEFAULT 0,
    total_health INT DEFAULT 0,
    total_mana INT DEFAULT 0,
    FOREIGN KEY (discord_id) REFERENCES players(discord_id),
    FOREIGN KEY (equipped_weapon_id) REFERENCES weapons(id),
    FOREIGN KEY (equipped_helmet_id) REFERENCES armour(id),
    FOREIGN KEY (equipped_chest_id) REFERENCES armour(id),
    FOREIGN KEY (equipped_legs_id) REFERENCES armour(id),
    FOREIGN KEY (equipped_feet_id) REFERENCES armour(id),
    FOREIGN KEY (equipped_amulet_id) REFERENCES items(id),
    FOREIGN KEY (equipped_ring1_id) REFERENCES items(id),
    FOREIGN KEY (equipped_ring2_id) REFERENCES items(id),
    FOREIGN KEY (equipped_charm_id) REFERENCES items(id)
);

CREATE TABLE residential_storage (
    id INT PRIMARY KEY AUTO_INCREMENT,
    discord_id BIGINT NOT NULL,
    item_slot1_id INT,
    item_slot1_class VARCHAR(20),
    item_slot2_id INT,
    item_slot2_class VARCHAR(20),
    item_slot3_id INT,
    item_slot3_class VARCHAR(20),
    item_slot4_id INT,
    item_slot4_class VARCHAR(20),
    item_slot5_id INT,
    item_slot5_class VARCHAR(20),
    item_slot6_id INT,
    item_slot6_class VARCHAR(20),
    item_slot7_id INT,
    item_slot7_class VARCHAR(20),
    item_slot8_id INT,
    item_slot8_class VARCHAR(20),
    gold_storage INT,
    FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS player_location (
    discord_id BIGINT PRIMARY KEY,
    tile_id INT DEFAULT 1,
    FOREIGN KEY (discord_id) REFERENCES players(discord_id),
    FOREIGN KEY (tile_id) REFERENCES map_tiles(id)
);

CREATE TABLE IF NOT EXISTS mobs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    town VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    strength INT DEFAULT 0,
    agility INT DEFAULT 0,
    intelligence INT DEFAULT 0,
    stamina INT DEFAULT 0,
    description TEXT
);

CREATE TABLE IF NOT EXISTS player_mob_kills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    discord_id BIGINT NOT NULL,
    mob_id INT NOT NULL,
    mob_type VARCHAR(255),
    kill_date DATETIME,
    experience_gained INT,
    items_dropped TEXT,
    FOREIGN KEY (discord_id) REFERENCES players(discord_id),
    FOREIGN KEY (mob_id) REFERENCES mobs(id)
);

CREATE TABLE IF NOT EXISTS bosses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    town VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    strength INT DEFAULT 0,
    agility INT DEFAULT 0,
    intelligence INT DEFAULT 0,
    stamina INT DEFAULT 0,
    description TEXT
);

CREATE TABLE battles (
    id INT PRIMARY KEY AUTO_INCREMENT,
    discord_id BIGINT,
    opponent_name VARCHAR(255),
    opponent_type VARCHAR(255),
    opponent_health INT,
    opponent_dodge_chance FLOAT,
    player_health INT,
    player_mana INT,
    player_dodge_chance FLOAT,
    current_location VARCHAR(255),
    battle_started_at DATETIME,
    battle_ended_at DATETIME
);
```

#### Mob information
```
INSERT INTO mobs (town, name, strength, agility, intelligence, stamina, description)
VALUES
    ('The Gloaming Vale', 'Shadow Stalker', 6, 10, 2, 6, 'Spectral entities that blend with the shadows. Known for their swift, agile attacks that target adventurers wandering too far from the town.'),
    ('The Gloaming Vale', 'Nocturnal Beast', 6, 5, 3, 8, 'These formidable creatures, armed with sharp fangs and claws, prowl the darkness outside Shadowhaven. They have a preference for surprise attacks.'),
    ('The Gloaming Vale', 'Voidcaster', 4, 5, 8, 6, 'These sorcerous beings harness the arcane forces of darkness. They prefer to stay back and cast devastating spells from a distance.'),
    ('The Gloaming Vale', 'Twilight Sprite', 4, 9, 9, 8, 'These diminutive beings are known for their mischievous behavior and clever tactics, using their high intelligence and agility to outwit foes.'),
    ('Scorched Plains', 'Iron Golem', 10, 13, 4, 15, 'Massive constructs made from the ruins of ancient fortifications, these golems exhibit immense strength but lack speed.'),
    ('Scorched Plains', 'Steel Mantis', 10, 18, 5, 18, 'Resembling oversized predatory insects made of hardened steel, they display a deadly blend of strength and agility.'),
    ('Scorched Plains', 'Siege Wraith', 14, 20, 8, 22, 'Spirits of warriors who perished during ancient sieges, they harness powerful spells and strategize their attacks to wear down the enemy.'),
    ('Scorched Plains', 'Flame Djinn', 15, 25, 13, 22, 'These supernatural beings are made of pure fire and use their high intelligence and magical abilities to burn their enemies to cinders.'),
    ('Tide Whisper Coves', 'Sea Serpent', 20, 22, 12, 27, 'Gigantic creatures emerging from the depths of the sea, they pose a major threat to those braving the churning waters near Havenreach.'),
    ('Tide Whisper Coves', 'Storm Harpy', 18, 28, 16, 26, 'Vicious winged creatures that ride the tempestuous winds, capable of launching rapid airborne attacks.'),
    ('Tide Whisper Coves', 'Kraken Spawn', 24, 25, 18, 28, 'Offsprings of legendary sea monsters, their massive size, strength, and intelligence make them a formidable foe to all near the coast.'),
    ('Tide Whisper Coves', 'Spectral Pirate', 28, 16, 14, 30, 'The undying spirits of pirates who''ve lost their lives in the treacherous waters. They use their agility and cunning to surprise their foes.'),
    ('Shadowmire', 'Mist Wraith', 32, 18, 20, 30, 'Ethereal beings that use the mist as a cloak, they are adept at both physical and magical attacks.'),
    ('Shadowmire', 'Thorned Beast', 35, 36, 22, 34, 'Creatures covered in a carapace of thorns, they lurk in the shadows and ambush their prey with deadly force.'),
    ('Shadowmire', 'Eldritch Shade', 32, 20, 24, 38, 'These malevolent spirits possess deep knowledge of dark magics and can employ a variety of strategies to overwhelm their enemies.'),
    ('Shadowmire', 'Mire Stalker', 32, 50, 15, 42, 'Stealthy predators that blend perfectly with their gloomy surroundings, attacking with deadly precision.'),
    ('The Ember Barrens', 'Wasteland Behemoth', 45, 34, 32, 44, 'Enormous creatures that roam the barren wastes, their raw power and endurance make them a daunting challenge.'),
    ('The Ember Barrens', 'Ashen Wraith', 52, 22, 32, 46, 'Ghostly beings formed from the ashes of the wasteland, they''re agile and skilled at using the harsh environment to their advantage.'),
    ('The Ember Barrens', 'Ember Drake', 63, 42, 43, 48, 'These draconic creatures, born of fire and ash, are cunning adversaries capable of devastating fiery attacks and formidable magic.'),
    ('The Ember Barrens', 'Barrens Goliath', 75, 54, 34, 50, 'Imposing stone-skinned beasts known for their resilience and strength. Despite their size, they can deliver swift, powerful attacks.');
```

#### Boss information
```
INSERT INTO bosses (town, name, strength, agility, intelligence, stamina, description)
VALUES
    ('The Gloaming Vale', 'Night Whisper', 15, 30, 15, 45, 'This entity is a synthesis of perpetual darkness and arcane power, commanding shadow magic and nightmare creatures.'),
    ('Scorched Plains', 'Steel Behemoth', 25, 53, 25, 42, 'An enormous construct forged from the remnants of ancient warfare. Built with unyielding iron, it bears formidable siege weaponry.'),
    ('Tide Whisper Coves', 'Deepmaw', 50, 43, 40, 55, 'A tremendous sea beast that has assailed Havenreach''s coasts for centuries. Its strength and fury echo the tempestuous seas it emerges from.'),
    ('Shadowmire', 'Mistweaver', 65, 55, 67, 60, 'An ancient entity from the cursed woods, it manipulates forbidden magics and the surrounding mists to ensnare its enemies.'),
    ('The Ember Barrens', 'Cinderbound', 120, 76, 86, 78, 'Born from fire and devastation, this gargantuan creature rules the barren landscapes surrounding Ashenfell. Its fiery breath and raw strength challenge even the bravest adventurers.');
```

#### Items information
```
INSERT INTO items (name, class, strength, agility, intelligence, stamina, price, rarity, description)
VALUES
    ('Health Potion', 'Consumable', 0, 0, 0, 1, 50, 'Common', 'Restores a moderate amount of health to the player upon consumption.'),
    ('Mana Elixir', 'Consumable', 0, 0, 0, 1, 50, 'Common', 'Restores a moderate amount of mana to the player upon consumption.'),
    ('Scroll of Teleportation', 'Consumable', 0, 0, 0, 1, 150, 'Rare', 'Allows the player to teleport to a previously visited town.'),

    ('Ring of Power', 'Ring', 5, 5, 5, 5, 0, 'Legendary', 'A legendary ring that empowers all attributes of the wearer to extraordinary levels.'),
    ('Ring of Agility', 'Ring', 0, 10, 0, 0, 0, 'Legendary', 'A ring that enhances the wearer''s agility, greatly improving their movement speed and dexterity.'),
    ('Ring of Intellect', 'Ring', 0, 0, 8, 0, 0, 'Legendary', 'A ring that enhances the wearer''s intellect, greatly improving their magical prowess and knowledge.'),
    ('Ring of Vitality', 'Ring', 0, 0, 0, 10, 0, 'Legendary', 'A ring that enhances the wearer''s vitality, greatly boosting their maximum health and endurance.'),
    ('Ring of Strength', 'Ring', 5, 0, 0, 0, 0, 'Legendary', 'A ring that enhances the wearer''s strength, significantly augmenting their melee attack power and physical capabilities.'),
    ('Ring of Wisdom', 'Ring', 0, 0, 8, 0, 0, 'Legendary', 'A legendary ring that enhances the wearer''s wisdom, greatly improving their magical abilities and perception.'),
    ('Ring of Protection', 'Ring', 7, 0, 0, 0, 0, 'Legendary', 'A legendary ring that enhances the wearer''s defense, providing unparalleled protection against all forms of attack.'),

    ('Amulet of Wisdom', 'Amulet', 0, 0, 5, 0, 0, 'Epic', 'An amulet that enhances the wearer''s intelligence, significantly boosting their magical prowess and knowledge.'),
    ('Amulet of Balance', 'Amulet', 7, 7, 7, 7, 0, 'Legendary', 'An amulet that brings balance to the wearer''s attributes, providing significant improvements to strength, agility, intelligence, and stamina.'),
    ('Amulet of Protection', 'Amulet', 10, 0, 0, 0, 0, 'Legendary', 'An amulet that enhances the wearer''s defense, significantly reducing incoming damage and improving their survivability.'),
    ('Amulet of Sorcery', 'Amulet', 0, 0, 10, 0, 0, 'Legendary', 'An amulet that enhances the wearer''s sorcery, significantly amplifying their magical spells and abilities.'),
    ('Amulet of Power', 'Amulet', 5, 5, 5, 5, 0, 'Legendary', 'A legendary amulet that empowers all attributes of the wearer to extraordinary levels.'),

    ('Charm of Agility', 'Charm', 0, 10, 0, 0, 0, 'Legendary', 'A charm that enhances the wearer''s agility, significantly improving their movement speed and dexterity.'),
    ('Charm of Intellect', 'Charm', 0, 0, 7, 0, 0, 'Epic', 'A charm that enhances the wearer''s intellect, significantly improving their magical prowess and knowledge.'),
    ('Charm of Endurance', 'Charm', 0, 0, 0, 10, 0, 'Legendary', 'A charm that enhances the wearer''s endurance, significantly boosting their maximum health and endurance.'),
    ('Charm of Strength', 'Charm', 7, 0, 0, 0, 0, 'Legendary', 'A charm that enhances the wearer''s strength, significantly augmenting their melee attack power and physical capabilities.'),
    ('Charm of Wisdom', 'Charm', 0, 0, 8, 0, 0, 'Legendary', 'A legendary charm that enhances the wearer''s wisdom, greatly improving their magical abilities and perception.'),
    ('Charm of Stamina', 'Charm', 0, 0, 0, 15, 0, 'Legendary', 'A legendary charm that enhances the wearer''s stamina');

UPDATE items
SET price = 
    CASE rarity
        WHEN 'Common' THEN 5
        WHEN 'Rare' THEN 15
        WHEN 'Epic' THEN 50
        WHEN 'Legendary' THEN 100
    END
    + CASE
        WHEN (strength + agility + intelligence + stamina) = 0 THEN 0
        ELSE (strength + agility + intelligence + stamina) * 5
    END;
```

#### Weapons information
```
INSERT INTO weapons (town, name, weapon_type, class, rarity, strength, agility, intelligence, stamina, price, description)
VALUES
    ('Shadowhaven', 'Twilight Blade', 'One-Handed Sword', 'weapon', 'Common', 1, 4, 0, 0, 0, 'A standard one-handed sword.'),
    ('Shadowhaven', 'Voidcaster Staff', 'Staff', 'weapon', 'Common', 1, 2, 1, 0, 0, 'A basic staff.'),
    ('Shadowhaven', 'Moonshadow Bow', 'Bow', 'weapon', 'Common', 1, 5, 1, 2, 0, 'A standard bow.'),
    ('Shadowhaven', 'Shadebane Blade', 'One-Handed Sword', 'weapon', 'Rare', 2, 6, 0, 4, 0, 'A finely crafted one-handed sword that enhances the wielder''s strength and agility.'),
    ('Shadowhaven', 'Soulreaper Scythe', 'Two-Handed Scythe', 'weapon', 'Rare', 2, 4, 1, 3, 0, 'A powerful scythe that drains the life essence of enemies, boosting the wielder''s strength and intelligence.'),
    ('Shadowhaven', 'Ethereal Wand', 'Wand', 'weapon', 'Epic', 0, 5, 4, 3, 0, 'A mystical wand that channels ethereal energies, enhancing intelligence and stamina.'),
    ('Shadowhaven', 'Nightshade Bow', 'Bow', 'weapon', 'Epic', 2, 6, 1, 5, 0, 'A bow infused with deadly nightshade toxins, granting bonuses to agility and stamina.'),
    ('Ironkeep', 'Ironclad Warhammer', 'Two-Handed Hammer', 'weapon', 'Common', 2, 5, 0, 3, 0, 'A standard two-handed hammer'),
    ('Ironkeep', 'Flameforged Battle Axe', 'One-Handed Axe', 'weapon', 'Common', 3, 3, 0, 0, 0, 'A basic one-handed axe'),
    ('Ironkeep', 'Steelheart Crossbow', 'Crossbow', 'weapon', 'Common', 2, 7, 2, 4, 0, 'A standard crossbow with'),
    ('Ironkeep', 'Inferno Maul', 'Two-Handed Hammer', 'weapon', 'Rare', 5, 0, 0, 5, 0, 'A mighty hammer imbued with the power of fire, providing a bonus to strength and stamina.'),
    ('Ironkeep', 'Thunderstrike Greataxe', 'Two-Handed Greataxe', 'weapon', 'Rare', 5, 8, 1, 6, 0, 'A formidable greataxe that crackles with lightning, increasing the wielder''s strength and agility.'),
    ('Ironkeep', 'Dwarven Warhammer', 'Two-Handed Hammer', 'weapon', 'Epic', 7, 0, 0, 0, 0, 'A massive warhammer forged by skilled Dwarven craftsmen, granting a substantial boost to strength.'),
    ('Ironkeep', 'Stormguard Crossbow', 'Crossbow', 'weapon', 'Epic', 3, 8, 6, 4, 0, 'A crossbow infused with storm energy, enhancing agility and intelligence.'),
    ('Havenreach', 'Tidebreaker Trident', 'Spear', 'weapon', 'Rare', 6, 15, 0, 10, 0, 'A spear empowered by the raging tempests, granting bonuses to agility and stamina.'),
    ('Havenreach', 'Stormcaller Cutlass', 'One-Handed Sword', 'weapon', 'Rare', 5, 5, 5, 6, 0, 'A razor-sharp cutlass infused with the power of the storm, enhancing strength and intelligence.'),
    ('Havenreach', 'Harpoon Launcher', 'Ranged Harpoon Launcher', 'weapon', 'Rare', 5, 15, 0, 10, 0, 'A harpoon launcher designed for ranged attacks, granting bonuses to agility and stamina.'),
    ('Havenreach', 'Tempest Pike', 'Spear', 'weapon', 'Epic', 9, 20, 0, 10, 0, 'A mighty pike empowered by the tempests, granting substantial bonuses to agility and stamina.'),
    ('Havenreach', 'Maelstrom Saber', 'One-Handed Sword', 'weapon', 'Epic', 8, 7, 5, 5, 0, 'A fearsome saber infused with the power of the maelstrom, enhancing strength and intelligence.'),
    ('Havenreach', 'Oceandream Trident', 'Spear', 'weapon', 'Epic', 8, 10, 2, 8, 0, 'A legendary trident forged from the dreams of ancient sea gods, bestowing remarkable agility and stamina.'),
    ('Havenreach', 'Thunderstorm Cutlass', 'One-Handed Sword', 'weapon', 'Legendary', 13, 20, 2, 5, 0, 'A cutlass crackling with thunderstorms, empowering both strength and agility.'),
    ('Grimhold', 'Eldritch Wand', 'Wand', 'weapon', 'Rare', 0, 7, 18, 15, 0, 'A mysterious wand that channels eldritch energies, enhancing intelligence and stamina.'),
    ('Grimhold', 'Cursed Scythe', 'Two-Handed Scythe', 'weapon', 'Rare', 4, 6, 12, 13, 0, 'A fearsome scythe cursed with dark magic, enhancing intelligence and stamina.'),
    ('Grimhold', 'Shadowbound Dagger', 'Dagger', 'weapon', 'Rare', 4, 9, 10, 10, 0, 'A dagger shrouded in shadow, granting bonuses to agility and stamina.'),
    ('Grimhold', 'Sorrowsong Staff', 'Staff', 'weapon', 'Epic', 2, 6, 20, 15, 0, 'A staff that emanates a mournful melody, amplifying intelligence and stamina.'),
    ('Grimhold', 'Nightshade Blade', 'One-Handed Sword', 'weapon', 'Epic', 12, 6, 3, 10, 0, 'A deadly sword infused with toxic nightshade, granting bonuses to strength and stamina.'),
    ('Grimhold', 'Voidcaster Tome', 'Tome', 'weapon', 'Epic', 0, 0, 25, 25, 0, 'A forbidden tome of void magic, enhancing intelligence and stamina.'),
    ('Grimhold', 'Thornspike Dagger', 'Dagger', 'weapon', 'Legendary', 10, 40, 5, 20, 0, 'A wicked dagger adorned with thorns, increasing agility and stamina.'),
    ('Ashenfell', 'Blazing Greatsword', 'Two-Handed Greatsword', 'weapon', 'Rare', 15, 5, 4, 14, 0, 'A greatsword wreathed in blazing flames, granting bonuses to strength and stamina.'),
    ('Ashenfell', 'Desertwind Dual Blades', 'Dual Swords', 'weapon', 'Rare', 12, 15, 15, 8, 0, 'Dual blades swift as the desert wind, enhancing agility and intelligence.'),
    ('Ashenfell', 'Sandstorm Longbow', 'Bow', 'weapon', 'Rare', 8, 25, 15, 20, 0, 'A longbow designed to withstand sandstorms, granting bonuses to agility and stamina.'),
    ('Ashenfell', 'Infernal Executioner', 'Two-Handed Greatsword', 'weapon', 'Epic', 20, 20, 2, 4, 0, 'A mighty greatsword forged in infernal flames, empowering both strength and agility.'),
    ('Ashenfell', 'Duneblight Blades', 'Dual Swords', 'weapon', 'Epic', 18, 25, 2, 20, 0, 'Dual blades infused with the essence of the arid dunes, granting substantial bonuses to agility and stamina.'),
    ('Ashenfell', 'Scorching Longbow', 'Bow', 'weapon', 'Epic', 15, 35, 15, 4, 0, 'A longbow imbued with scorching flames, augmenting agility and intelligence.'),
    ('Ashenfell', 'Ashfire Greatsword', 'Two-Handed Greatsword', 'weapon', 'Legendary', 25, 0, 0, 25, 0, 'A greatsword wreathed in fiery ashes, empowering both strength and stamina.');

UPDATE weapons
SET price = 
    CASE rarity
        WHEN 'Common' THEN 5
        WHEN 'Rare' THEN 15
        WHEN 'Epic' THEN 50
        WHEN 'Legendary' THEN 100
    END
    + CASE
        WHEN (strength + agility + intelligence + stamina) = 0 THEN 0
        ELSE (strength + agility + intelligence + stamina) * 5
    END;
```

#### Armour information
```
INSERT INTO armour (town, name, type, class, strength, agility, intelligence, stamina, price, rarity, description)
VALUES
    ('Shadowhaven', 'Filthy Peasant Cloth', 'Chest Armor', 'armour', 1, 2, 0, 2, 0, 'Common', 'A tattered and dirty piece of cloth that barely offers any protection. Only suitable for desperate peasants.'),
    ('Shadowhaven', 'Ragged Rags', 'Chest Armor', 'armour', 0, 1, 1, 2, 0, 'Common', 'A set of ragged and torn rags stitched together. It provides minimal defense but is better than nothing.'),
    ('Shadowhaven', 'Patchwork Tunic', 'Chest Armor', 'armour', 1, 0, 2, 1, 0, 'Common', 'A tunic made from assorted patches of fabric. While it lacks style, it provides basic protection.'),
    ('Shadowhaven', 'Threadbare Garment', 'Chest Armor', 'armour', 0, 2, 1, 1, 0, 'Common', 'A worn-out garment with frayed edges. It offers limited defense but is lightweight and easy to move in.'),
    ('Shadowhaven', 'Shabby Vest', 'Chest Armor', 'armour', 1, 1, 0, 2, 0, 'Common', 'A shabby vest made from cheap materials. It provides minimal protection, but at least it covers the torso.'),
    ('Shadowhaven', 'Worn-out Chestpiece', 'Chest Armor', 'armour', 1, 1, 1, 1, 0, 'Common', 'A heavily used and worn-out chestpiece. Its protective capabilities are questionable, but it might still offer some resistance.'),
    ('Shadowhaven', 'Umbra Helm', 'Helmet', 'armour', 1, 2, 2, 3, 0, 'Rare', 'Forged from the rare Shadow Iron found deep within the abyss, this helm provides reliable protection in the dark realm of Shadowhaven.'),
    ('Shadowhaven', 'Nightseer Circlet', 'Helmet', 'armour', 1, 4, 4, 2, 0, 'Rare', 'A circlet carved from the gnarled trees of Shadowhaven, it enhances the wearer\'s insight into the arcane arts.'),
    ('Shadowhaven', 'Veil of the Shadow Walker', 'Helmet', 'armour', 2, 6, 2, 8, 0, 'Epic', 'Crafted from the rare Shade Silk, this veil grants the wearer enhanced agility and the ability to blend into the shadows.'),
    ('Shadowhaven', 'Nightguard Helm', 'Helmet', 'armour', 2, 4, 1, 8, 0, 'Epic', 'A robust helm favored by the guards of Shadowhaven. It\'s made from Blackened Steel and reinforced with Shadow Leather, providing optimal protection against the creatures of the night.'),
    ('Shadowhaven', 'Eclipse Diadem', 'Helmet', 'armour', 3, 3, 6, 5, 0, 'Legendary', 'An ornate diadem made of precious Star Silver, often used by the magic-wielders of Shadowhaven. It is said to amplify the wearer\'s dark magic spells.'),
    
    ('Shadowhaven', 'Ebonplate Cuirass', 'Chest Armor', 'armour', 2, 2, 2, 5, 0, 'Rare', 'This chest armor made from Shadow Iron is sturdy and reliable, providing decent protection against the dark forces in Shadowhaven.'),
    ('Shadowhaven', 'Nightweave Robe', 'Chest Armor', 'armour', 2, 6, 4, 4, 0, 'Rare', 'A lightweight robe crafted from the rare Shade Silk. It offers increased spell casting speed and comfort to magic users.'),
    ('Shadowhaven', 'Chestguard of the Night Stalker', 'Chest Armor', 'armour', 3, 6, 1, 6, 0, 'Epic', 'This chestguard, reinforced with Darkwood and padded with Shadow Leather, provides stealth and durability for scouts and rogues in Shadowhaven.'),
    ('Shadowhaven', 'Shadowhaven Hauberk', 'Chest Armor', 'armour', 3, 4, 4, 6, 0, 'Epic', 'A traditional armor of Shadowhaven\'s guardians, this hauberk made of blackened chainmail offers superior protection and resilience against physical threats.'),
    ('Shadowhaven', 'Starglow Mantle', 'Chest Armor', 'armour', 4, 4, 4, 4, 0, 'Legendary', 'A symbol of high status among Shadowhaven\'s magic users, this mantle of Star Silver and Shade Silk enhances the wearer\'s dark magic potency and aids in quicker mana regeneration.'),
    
    ('Shadowhaven', 'Shadowhide Greaves', 'Leg Armor', 'armour', 1, 6, 1, 5, 0, 'Rare', 'These greaves, made from tough Shadow Leather, are designed to be sturdy yet flexible, allowing for swift movements in the cover of darkness.'),
    ('Shadowhaven', 'Abyssal Plate Leggings', 'Leg Armor', 'armour', 2, 0, 0, 3, 0, 'Rare', 'Forged from the unique Shadow Iron, these hefty leggings offer superb protection against the dark creatures lurking in the town\'s vicinity.'),
    ('Shadowhaven', 'Nightweave Trousers', 'Leg Armor', 'armour', 1, 7, 2, 4, 0, 'Rare', 'Preferred by the mages of Shadowhaven, these trousers enhance the wearer\'s connection to the arcane, facilitating faster mana regeneration.'),
    ('Shadowhaven', 'Starlight Chausses', 'Leg Armor', 'armour', 2, 5, 2, 8, 0, 'Epic', 'These intricate chausses are not only sturdy but also provide the wearer with increased resistance to arcane attacks, making them a prized possession among the warriors of Shadowhaven.'),
    ('Shadowhaven', 'Shadowstep Leggings', 'Leg Armor', 'armour', 2, 8, 1, 12, 0, 'Epic', 'Designed for the scouts and rogues, these leggings offer enhanced stealth abilities and increase the wearer\'s evasion rate.'),
    ('Shadowhaven', 'Shadowfall Greaves', 'Leg Armor', 'armour', 3, 12, 1, 6, 0, 'Epic', 'These greaves, forged with the essence of shadows, provide unmatched protection and enhance the wearer\'s agility and stamina.'),
    ('Shadowhaven', 'Darkstar Plate Leggings', 'Leg Armor', 'armour', 4, 10, 4, 10, 0, 'Legendary', 'Leggings crafted from the legendary Darkstar Metal, known for its impenetrable defense against even the most powerful dark magic.'),
    ('Shadowhaven', 'Ethereal Leggings', 'Leg Armor', 'armour', 3, 15, 6, 4, 0, 'Legendary', 'Leggings woven from ethereal strands, granting the wearer exceptional speed, magical prowess, and resistance against all elements.'),
    
    ('Shadowhaven', 'Shadowswift Boots', 'Footwear', 'armour', 1, 6, 2, 4, 0, 'Rare', 'Crafted from the unique Shadow Leather, these boots are light yet robust, offering increased speed to their wearer when in dimly lit environments.'),
    ('Shadowhaven', 'Ebonplate Sabatons', 'Footwear', 'armour', 1, 4, 2, 8, 0, 'Rare', 'These solid sabatons provide sturdy footing in any battle, reducing knockback from enemy strikes.'),
    ('Shadowhaven', 'Nightweave Slippers', 'Footwear', 'armour', 1, 8, 4, 5, 0, 'Rare', 'Preferred by spellcasters, these slippers are not only comfortable but also provide the wearer with protection against spellcasting interruptions.'),
    ('Shadowhaven', 'Starglow Sandals', 'Footwear', 'armour', 2, 8, 4, 4, 0, 'Epic', 'These finely crafted sandals offer a balance between comfort and protection, boosting the wearer\'s resistance to dark magic attacks.'),
    ('Shadowhaven', 'Silent Striders', 'Footwear', 'armour', 4, 8, 0, 10, 0, 'Epic', 'Made for those who prefer to avoid detection, these boots grant the wearer near-silent movements, making them ideal for scouting and ambushes.'),
    ('Shadowhaven', 'Voidstride Boots', 'Footwear', 'armour', 4, 10, 5, 8, 0, 'Legendary', 'Boots infused with the essence of the void, granting the wearer unparalleled agility, the ability to traverse dimensions, and immunity to magical disturbances.');

INSERT INTO armour (town, name, type, class, strength, agility, intelligence, stamina, price, rarity, description)
VALUES
    ('Ironkeep', 'Ironforge Helm', 'Helmet', 'armour', 2, 6, 2, 15, 0, 'Rare', 'A sturdy, well-crafted iron helm made by Ironkeep\'s finest smiths. The wearer of this helm can expect significant protection in battle.'),
    ('Ironkeep', 'Firescale Coif', 'Helmet', 'armour', 2, 10, 2, 10, 0, 'Rare', 'This helmet, made from the rare scales of a fire dragon, not only provides substantial physical protection but also grants increased resistance to fire damage.'),
    ('Ironkeep', 'Battleworn Cap', 'Helmet', 'armour', 2, 8, 3, 8, 0, 'Rare', 'Though it looks simple, this hardened leather cap is favored by seasoned warriors for its ability to turn an ordinary attack into a deadly blow.'),
    ('Ironkeep', 'Mithril Helm', 'Helmet', 'armour', 3, 8, 3, 12, 0, 'Rare', 'A helm forged from the legendary Mithril, known for its unmatched strength and durability. It provides superior protection and instills fear in the hearts of enemies.'),
    ('Ironkeep', 'Dragonbone Coif', 'Helmet', 'armour', 3, 7, 4, 10, 0, 'Epic', 'This coif is made from the bones of a powerful dragon, granting the wearer enhanced physical defense and resistance against elemental attacks.'),
    ('Ironkeep', 'Champion\'s Cap', 'Helmet', 'armour', 4, 10, 3, 9, 0, 'Epic', 'A cap worn by renowned champions, it channels their legendary prowess into every strike, increasing the chance of delivering devastating blows.'),
    ('Ironkeep', 'Adamantine Helm', 'Helmet', 'armour', 4, 10, 3, 20, 0, 'Epic', 'Forged from the rare and indestructible Adamantine, this helm offers unmatched defense, instilling fear in the hearts of even the mightiest foes.'),
    ('Ironkeep', 'Wyrmfire Coif', 'Helmet', 'armour', 4, 40, 5, 40, 0, 'Legendary', 'Crafted from the scales of a powerful wyrm, this coif grants the wearer extraordinary resistance to fire and other elemental attacks.'),
    ('Ironkeep', 'Exalted Crown', 'Helmet', 'armour', 5, 15, 6, 8, 0, 'Legendary', 'A crown worn only by those who have ascended to the pinnacle of power. It enhances the wearer\'s strength, agility, and intelligence to godlike levels.'),

    ('Ironkeep', 'Mithril Cuirass', 'Chest Armor', 'armour', 3, 6, 2, 15, 0, 'Rare', 'The pinnacle of armor craftsmanship, this cuirass made from pure Mithril provides unparalleled protection and becomes an impenetrable barrier against all attacks.'),
    ('Ironkeep', 'Dragonbone Hauberk', 'Chest Armor', 'armour', 3, 15, 2, 15, 0, 'Rare', 'Forged from the bones of a fearsome dragon, this hauberk grants extraordinary defense and amplifies the wearer\'s natural resistance to all forms of damage.'),
    ('Ironkeep', 'Champion\'s Jerkin', 'Chest Armor', 'armour', 3, 12, 2, 12, 0, 'Rare', 'Worn by legendary champions, this jerkin harnesses their indomitable spirit, enhancing agility, strength, and granting the ability to unleash devastating attacks.'),
    ('Ironkeep', 'Adamantine Cuirass', 'Chest Armor', 'armour', 4, 4, 5, 15, 0, 'Epic', 'This adamantine cuirass is said to be impervious to any weapon. It grants unparalleled protection and turns the wearer into an unstoppable force on the battlefield.'),
    ('Ironkeep', 'Wyrmfire Hauberk', 'Chest Armor', 'armour', 5, 15, 0, 15, 0, 'Epic', 'Made from the scales of an ancient wyrm, this hauberk grants immense physical and elemental defense, rendering the wearer nearly invulnerable to all forms of attack.'),
    ('Ironkeep', 'Exalted Tunic', 'Chest Armor', 'armour', 6, 15, 5, 10, 0, 'Legendary', 'This tunic, worn only by the most esteemed champions, channels the power of the gods, amplifying the wearer\'s strength, agility, and unlocking their true potential.'),

    ('Ironkeep', 'Mithril Greaves', 'Leg Armor', 'armour', 2, 7, 1, 10, 0, 'Rare', 'These Mithril greaves offer unparalleled protection and allow the wearer to move swiftly and effortlessly on the battlefield.'),
    ('Ironkeep', 'Dragonbone Chausses', 'Leg Armor', 'armour', 2, 8, 2, 8, 0, 'Rare', 'Crafted from the bones of a mighty dragon, these chausses grant incredible defense and fortify the wearer against all forms of elemental attacks.'),
    ('Ironkeep', 'Champion\'s Leggings', 'Leg Armor', 'armour', 3, 5, 2, 5, 0, 'Rare', 'The legendary leggings of a renowned champion, they are light, flexible, and bolster the wearer\'s strength and agility, allowing for swift, devastating strikes.'),
    ('Ironkeep', 'Adamantine Greaves', 'Leg Armor', 'armour', 3, 8, 5, 15, 0, 'Epic', 'These adamantine greaves provide unparalleled defense, allowing the wearer to move with grace and agility while shrugging off even the most devastating blows.'),
    ('Ironkeep', 'Wyrmfire Chausses', 'Leg Armor', 'armour', 4, 15, 3, 15, 0, 'Epic', 'Fashioned from the scales of a legendary wyrm, these chausses offer extraordinary protection against all forms of damage, making the wearer an indomitable force on the battlefield.'),
    ('Ironkeep', 'Exalted Leggings', 'Leg Armor', 'armour', 5, 15, 5, 15, 0, 'Legendary', 'Worn only by the chosen few, these leggings bestow immense strength, agility, and intellect upon the wearer, transforming them into an unstoppable warrior.'),
    
    ('Ironkeep', 'Mithril Sabatons', 'Footwear', 'armour', 1, 6, 4, 6, 0, 'Rare', 'Crafted from Mithril, these sabatons provide exceptional protection to the wearer\'s feet and enhance their speed and agility.'),
    ('Ironkeep', 'Dragonbone Boots', 'Footwear', 'armour', 2, 10, 1, 10, 0, 'Rare', 'Made from the bones of a formidable dragon, these boots offer exceptional defense and grant the wearer enhanced resistance against elemental forces.'),
    ('Ironkeep', 'Champion\'s Boots', 'Footwear', 'armour', 2, 15, 2, 0, 0, 'Rare', 'The boots of a revered champion, they increase the wearer\'s speed, agility, and ensure their every step is precise, making them a formidable force on the battlefield.'),
    ('Ironkeep', 'Adamantine Sabatons', 'Footwear', 'armour', 2, 4, 6, 15, 0, 'Epic', 'These adamantine sabatons grant unparalleled protection and allow the wearer to move with unmatched speed and grace, striking fear into the hearts of their enemies.'),
    ('Ironkeep', 'Wyrmfire Boots', 'Footwear', 'armour', 3, 6, 4, 20, 0, 'Epic', 'Forged from the scales of a legendary wyrm, these boots offer unparalleled defense and empower the wearer to traverse the battlefield with unmatched agility and ferocity.'),
    ('Ironkeep', 'Exalted Boots', 'Footwear', 'armour', 4, 10, 3, 5, 0, 'Legendary', 'The boots of a true champion, they enhance the wearer\'s strength, agility, and intellect to divine levels, making them an embodiment of sheer power and skill.');


INSERT INTO armour (town, name, type, class, strength, agility, intelligence, stamina, price, rarity, description) VALUES
    ('Havenreach', 'Mariner\'s Hood', 'Helmet', 'armour', 4, 18, 6, 9, 0, 'Epic', 'This reinforced canvas hood is favored by Havenreach\'s seasoned sailors. It provides reliable protection against the elements and potential threats.'),
    ('Havenreach', 'Stormshell Helm', 'Helmet', 'armour', 4, 10, 8, 10, 0, 'Epic', 'Crafted from the carapace of a storm-inducing sea monster, this helm offers exceptional physical protection and resilience against adverse weather conditions.'),
    ('Havenreach', 'Tidecaller\'s Circlet', 'Helmet', 'armour', 4, 20, 9, 20, 0, 'Legendary', 'A circlet formed from enchanted coral. Its elegant design symbolizes the wearer\'s connection to the sea, enhancing their affinity for water-based magic.'),
    
    ('Havenreach', 'Mariner\'s Cloak', 'Chest Armor', 'armour', 6, 15, 8, 15, 0, 'Epic', 'This reinforced canvas cloak provides substantial defense while allowing for ease of movement during maritime activities.'),
    ('Havenreach', 'Stormshell Cuirass', 'Chest Armor', 'armour', 7, 10, 8, 10, 0, 'Epic', 'Forged from the carapace of a storm-inducing sea monster, this cuirass combines exceptional protection with increased resistance against lightning-based attacks.'),
    ('Havenreach', 'Tidecaller\'s Robe', 'Chest Armor', 'armour', 7, 10, 12, 15, 0, 'Legendary', 'A finely crafted robe woven with enchanted coral threads. It channels the power of the sea, augmenting the wearer\'s water-based magical abilities.'),
    
    ('Havenreach', 'Mariner\'s Trousers', 'Leg Armor', 'armour', 4, 15, 4, 12, 0, 'Epic', 'These reinforced canvas trousers are designed to withstand the rigors of maritime environments, providing both comfort and protection.'),
    ('Havenreach', 'Stormshell Greaves', 'Leg Armor', 'armour', 4, 18, 7, 7, 0, 'Epic', 'Crafted from the durable carapace of a sea monster, these greaves offer formidable defense and agility, making them ideal for maritime combat.'),
    ('Havenreach', 'Tidecaller\'s Leggings', 'Leg Armor', 'armour', 5, 15, 8, 16, 0, 'Legendary', 'Infused with the essence of enchanted coral, these leggings empower the wearer with heightened magical prowess in water-based spells.'),
    
    ('Havenreach', 'Mariner\'s Boots', 'Footwear', 'armour', 3, 22, 6, 15, 0, 'Epic', 'Sturdy and reliable, these reinforced canvas boots provide excellent traction on wet surfaces and protect against water-based attacks.'),
    ('Havenreach', 'Stormshell Boots', 'Footwear', 'armour', 3, 18, 5, 23, 0, 'Epic', 'Fashioned from the resilient carapace of a sea monster, these boots offer exceptional defense and lightning resistance, ensuring the wearer can traverse any terrain.'),
    ('Havenreach', 'Tidecaller\'s Sandals', 'Footwear', 'armour', 4, 20, 10, 15, 0, 'Legendary', 'Adorned with enchanted coral, these sandals enhance the wearer\'s connection to the sea, enabling mastery of water-based magical energies.');

INSERT INTO armour (town, name, type, class, strength, agility, intelligence, stamina, price, rarity, description) VALUES
    ('Grimhold', 'Veil of Shadows', 'Helmet', 'armour', 6, 22, 8, 12, 0, 'Epic', 'This mysterious veil, woven from shadow silk, provides additional protection and enhances the user\'s affinity for shadow magic.'),
    ('Grimhold', 'Thorn Crown', 'Helmet', 'armour', 4, 15, 13, 15, 0, 'Epic', 'A dangerous and intimidating headpiece, this crown of twisted thorns increases the wearer\'s defense and reflects a portion of melee damage back to the attacker.'),
    ('Grimhold', 'Whispering Hood', 'Helmet', 'armour', 5, 20, 27, 19, 0, 'Legendary', 'Crafted from ghost leather, this hood allows the user to hear whispers from the spirit realm, uncovering hidden secrets and knowledge.'),
    
    ('Grimhold', 'Robes of Shadow', 'Chest Armor', 'armour', 6, 22, 10, 23, 0, 'Epic', 'Flowing robes made from shadow silk, these garments enhance the power of the user\'s shadow magic and provide additional protection.'),
    ('Grimhold', 'Thorned Vest', 'Chest Armor', 'armour', 7, 16, 12, 18, 0, 'Epic', 'This dangerous vest made from thorned vines offers enhanced defense and reflects a portion of melee damage back to the attacker.'),
    ('Grimhold', 'Whispering Tunic', 'Chest Armor', 'armour', 9, 15, 14, 20, 0, 'Legendary', 'Crafted from ghost leather, this tunic allows the user to hear whispers from the spirit realm, revealing hidden secrets and paths unseen to others.'),
    
    ('Grimhold', 'Shadow\'s Greaves', 'Leg Armor', 'armour', 5, 27, 12, 12, 0, 'Epic', 'Woven from shadow silk, these greaves enhance the power of the user\'s shadow magic and provide additional protection.'),
    ('Grimhold', 'Thorned Leggings', 'Leg Armor', 'armour', 6, 20, 10, 20, 0, 'Epic', 'These intimidating leggings made from thorned vines increase the wearer\'s defense and reflect a portion of melee damage back to the attacker.'),
    ('Grimhold', 'Whispering Pants', 'Leg Armor', 'armour', 7, 25, 17, 19, 0, 'Legendary', 'Crafted from ghost leather, these pants allow the user to hear whispers from the spirit realm, uncovering hidden secrets and knowledge.'),
    
    ('Grimhold', 'Shadow\'s Slippers', 'Foot Armor', 'armour', 4, 17, 12, 12, 0, 'Epic', 'Woven from shadow silk, these slippers enhance the power of the user\'s shadow magic and provide additional protection.'),
    ('Grimhold', 'Thorned Boots', 'Foot Armor', 'armour', 4, 19, 14, 25, 0, 'Epic', 'These intimidating boots made from thorned vines increase the wearer\'s defense and reflect a portion of melee damage back to the attacker.'),
    ('Grimhold', 'Whispering Shoes', 'Foot Armor', 'armour', 5, 25, 14, 19, 0, 'Legendary', 'Crafted from ghost leather, these shoes allow the user to hear whispers from the spirit realm, uncovering hidden secrets and knowledge.');

INSERT INTO armour (town, name, type, class, strength, agility, intelligence, stamina, price, rarity, description) VALUES
    ('Ashenfell', 'Wastelander\'s Cowl', 'Helmet', 'armour', 7, 25, 10, 27, 0, 'Rare', 'Made from the hide of the wasteland drakes, this cowl provides superior protection against fire.'),
    ('Ashenfell', 'Wastelander\'s Mask', 'Helmet', 'armour', 12, 28, 13, 30, 0, 'Epic', 'Carved from ironwood, this mask protects its wearer from the harsh elements of the wasteland.'),
    ('Ashenfell', 'Emberforged Helm', 'Helmet', 'armour', 11, 30, 15, 30, 0, 'Epic', 'Forged in the heart of Ashenfell, this helm made from ember steel can turn the flames of an enemy against them.'),
    ('Ashenfell', 'Emberforged Visor', 'Helmet', 'armour', 15, 19, 15, 27, 0, 'Legendary', 'This visor, made from ember steel, provides exceptional protection against physical attacks.'),
    ('Ashenfell', 'Spirit Warden\'s Hood', 'Helmet', 'armour', 16, 30, 18, 25, 0, 'Legendary', 'This hood, woven from spirit cloth, enhances the power of protective and restorative spells.'),
    ('Ashenfell', 'Spirit Warden\'s Diadem', 'Helmet', 'armour', 15, 25, 22, 18, 0, 'Legendary', 'Crafted from a single spirit stone, this diadem grants the user the ability to see the spirits that roam Ashenfell.'),
    
    ('Ashenfell', 'Wastelander\'s Vest', 'Chest Armor', 'armour', 10, 20, 13, 15, 0, 'Rare', 'This sturdy vest made from the hide of the wasteland drakes offers superior protection against fire.'),
    ('Ashenfell', 'Wastelander\'s Cuirass', 'Chest Armor', 'armour', 13, 28, 15, 30, 0, 'Epic', 'This cuirass, carved from ironwood, shields its wearer from the harsh elements of the wasteland.'),
    ('Ashenfell', 'Emberforged Plate', 'Chest Armor', 'armour', 14, 25, 15, 20, 0, 'Epic', 'This chestplate, forged from ember steel in the heart of Ashenfell, can turn the flames of an enemy against them.'),
    ('Ashenfell', 'Emberforged Mail', 'Chest Armor', 'armour', 20, 25, 19, 20, 0, 'Legendary', 'This chainmail, woven from ember steel, offers extraordinary protection against physical attacks.'),
    ('Ashenfell', 'Spirit Warden\'s Robes', 'Chest Armor', 'armour', 22, 30, 20, 24, 0, 'Legendary', 'These robes, spun from spirit cloth, magnify the power of protective and restorative spells.'),
    ('Ashenfell', 'Spirit Warden\'s Tunic', 'Chest Armor', 'armour', 22, 25, 22, 22, 0, 'Legendary', 'This tunic, made from spectral leather, allows the user to perceive whispers from the spirit realm, revealing hidden secrets and paths unseen to the common eye.'),
    
    ('Ashenfell', 'Wastelander\'s Leggings', 'Leg Armor', 'armour', 7, 22, 13, 25, 0, 'Rare', 'These rugged leggings, made from the hide of the wasteland drakes, offer exceptional protection against fire.'),
    ('Ashenfell', 'Wastelander\'s Greaves', 'Leg Armor', 'armour', 9, 26, 15, 22, 0, 'Epic', 'Crafted from ironwood, these greaves protect the wearer\'s legs from the unforgiving elements of the wasteland.'),
    ('Ashenfell', 'Emberforged Legplates', 'Leg Armor', 'armour', 9, 23, 15, 19, 0, 'Epic', 'These legplates, forged from ember steel, channel the flames of an enemy\'s attack back towards them.'),
    ('Ashenfell', 'Emberforged Greaves', 'Leg Armor', 'armour', 12, 27, 17, 34, 0, 'Legendary', 'These greaves, made from resilient ember steel, offer exceptional protection against physical assaults.'),
    ('Ashenfell', 'Spirit Warden\'s Leggings', 'Leg Armor', 'armour', 13, 21, 18, 23, 0, 'Legendary', 'These ethereal leggings, woven from spirit cloth, enhance the power of healing and protective spells.'),
    ('Ashenfell', 'Spirit Warden\'s Pants', 'Leg Armor', 'armour', 13, 30, 25, 31, 0, 'Legendary', 'These pants, embedded with spirit stones, grant the ability to perceive and interact with the spirits of Ashenfell.'),
    
    ('Ashenfell', 'Wastelander\'s Boots', 'Foot Armor', 'armour', 6, 23, 14, 21, 0, 'Rare', 'These boots, crafted from the hide of the wasteland drakes, grant the wearer superior protection against fire-based threats.'),
    ('Ashenfell', 'Wastelander\'s Footguards', 'Foot Armor', 'armour', 8, 31, 19, 32, 0, 'Epic', 'These footguards, hewn from ironwood, shield the feet from the hazardous conditions of the wasteland.'),
    ('Ashenfell', 'Emberforged Sabatons', 'Foot Armor', 'armour', 9, 19, 15, 22, 0, 'Epic', 'These sabatons, forged from ember steel, reflect the flames of enemies, turning their own attacks against them.'),
    ('Ashenfell', 'Emberforged Boots', 'Foot Armor', 'armour', 9, 28, 20, 69, 0, 'Legendary', 'These resilient boots, constructed from ember steel, provide exceptional protection against physical strikes.'),
    ('Ashenfell', 'Spirit Warden\'s Boots', 'Foot Armor', 'armour', 10, 28, 18, 32, 0, 'Legendary', 'These ethereal boots, woven from spirit cloth, amplify the strength of healing and protective spells.'),
    ('Ashenfell', 'Spirit Warden\'s Sandals', 'Foot Armor', 'armour', 11, 32, 20, 34, 0, 'Legendary', 'These sandals, adorned with embedded spirit stones, enable the wearer to perceive and communicate with the spirits that haunt Ashenfell');

UPDATE armour
SET price = 
    CASE rarity
        WHEN 'Common' THEN 5
        WHEN 'Rare' THEN 15
        WHEN 'Epic' THEN 50
        WHEN 'Legendary' THEN 100
    END
    + CASE
        WHEN (strength + agility + intelligence + stamina) = 0 THEN 0
        ELSE (strength + agility + intelligence + stamina) * 5
    END;
```

#### Map tile information
```
INSERT INTO map_tiles (area_name, tile_name, tile_type, description, chance_mob_encounter)
VALUES
    ('Shadowhaven', 'Shadowhaven Town Center', 'Town', 'The heart of Shadowhaven, bustling with activity and trade.', 0.0),
    ('Shadowhaven', 'Shadowhaven Residential Area', 'Town', 'Quaint houses where residents of Shadowhaven reside.', 0.0),
    ('Shadowhaven', 'Shadowhaven Marketplace', 'Town', 'A lively market where various goods are bought and sold.', 0.0),
    ('Shadowhaven', 'Shadowhaven Training Grounds', 'Town', 'A dedicated area for honing combat skills and techniques.', 0.0),
    ('The Gloaming Vale', 'Enchanted Grove', 'Forest', 'A serene grove filled with mystical energy and ancient trees.', 0.15),
    ('The Gloaming Vale', 'Moonlit Clearing', 'Forest', 'A peaceful clearing bathed in the gentle light of the moon.', 0.15),
    ('The Gloaming Vale', 'Forgotten Ruins', 'Dungeon', 'Decaying ruins that hold secrets of the past and hidden dangers.', 0.3),
    ('The Gloaming Vale', 'Cursed Caverns', 'Dungeon', 'A network of treacherous caverns with a dark and ominous aura.', 0.45),
    ('The Gloaming Vale', 'Twilight Path', 'Path', 'A winding path embraced by the mysterious twilight ambiance.', 0.15),
    ('The Gloaming Vale', 'Misty Hollow', 'Path', 'A mist-covered hollow that creates an eerie atmosphere.', 0.15),
    ('The Gloaming Vale', 'Shadowed Trail', 'Path', 'A trail shrouded in shadows, giving an air of foreboding.', 0.15),
    ('The Gloaming Vale', 'Eerie Glade', 'Forest', 'A glade emanating an eerie presence, home to supernatural phenomena.', 0.21),
    ('The Gloaming Vale', 'Haunted Grove', 'Forest', 'A grove rumored to be haunted by vengeful spirits and restless souls.', 0.3),
    ('The Gloaming Vale', 'Spectral Thicket', 'Forest', 'A dense thicket teeming with spectral entities and ghostly phenomena.', 0.36),
    ('The Gloaming Vale', 'Gloomwood Path', 'Path', 'A path enveloped in a perpetual gloom, invoking a sense of unease.', 0.15),
    ('The Gloaming Vale', 'Shrouded Clearing', 'Path', 'A clearing where an otherworldly mist obscures the surroundings.', 0.15),
    ('The Gloaming Vale', 'Forsaken Bridge', 'Path', 'A crumbling bridge that carries an aura of abandonment and tragedy.', 0.15),
    ('The Gloaming Vale', 'Ruined Tower', 'Dungeon', 'A tower in ruins, said to be haunted by the spirits of long-dead sorcerers.', 0.24),
    ('The Gloaming Vale', 'Dark Catacombs', 'Dungeon', 'A labyrinthine catacomb filled with cryptic markings and restless undead.', 0.36),
    ('The Gloaming Vale', 'Cursed Pathway', 'Path', 'A pathway said to be cursed, attracting malevolent creatures and ill fortune.', 0.18),
    ('Ironkeep', 'Ironkeep Town Center', 'Town', 'The heart of Ironkeep, bustling with activity and trade.', 0.0),
    ('Ironkeep', 'Ironkeep Residential Area', 'Town', 'Quaint houses where residents of Ironkeep reside.', 0.0),
    ('Ironkeep', 'Ironkeep Marketplace', 'Town', 'A lively market where various goods are bought and sold.', 0.0),
    ('Ironkeep', 'Ironkeep Training Grounds', 'Town', 'A dedicated area for honing combat skills and techniques.', 0.0),
    ('Scorched Plains', 'Charred Fields', 'Grassland', 'A desolate expanse of burnt grassland, scarred by past battles.', 0.27),
    ('Scorched Plains', 'Ruined Battlements', 'Grassland', 'The remnants of ancient fortifications, now serving as a reminder of lost glory.', 0.21),
    ('Scorched Plains', 'Blazing Plateau', 'Grassland', 'A high plateau where intense heat radiates from the scorched earth.', 0.36),
    ('Scorched Plains', 'Lava Flows', 'Grassland', 'Rivers of molten lava that cut through the barren landscape, threatening all who venture near.', 0.45),
    ('Scorched Plains', 'Searing Dunes', 'Desert', 'Endless dunes of scorching sand, where heatwaves distort the horizon.', 0.27),
    ('Scorched Plains', 'Furnace Gorge', 'Desert', 'A deep gorge filled with searing heat and suffocating hot air.', 0.36),
    ('Scorched Plains', 'Obsidian Quarry', 'Desert', 'An abandoned quarry where obsidian shards lie scattered, shimmering in the sun.', 0.45),
    ('Scorched Plains', 'Scorched Rock', 'Rock', 'Large, blackened rocks that dot the landscape.', 0.18),
    ('Scorched Plains', 'Blistering Sands', 'Desert', 'Sands that radiate intense heat, burning the feet of unsuspecting travelers.', 0.24),
    ('Scorched Plains', 'Brimstone Crater', 'Desert', 'A massive crater filled with sulfurous gases and bubbling lava.', 0.3),
    ('Scorched Plains', 'Ashen Oasis', 'Desert', 'An oasis with dry, ash-filled pools and withered palm trees.', 0.15),
    ('Scorched Plains', 'Cinder Ruins', 'Rock', 'The remains of structures reduced to cinders by scorching fires.', 0.21),
    ('Scorched Plains', 'Solar Flare Basin', 'Desert', 'A basin where intense solar flares scorch the earth intermittently.', 0.18),
    ('Scorched Plains', 'Blazing Thornbush', 'Flora', 'Thorny bushes that radiate heat and deter exploration.', 0.40),
    ('Scorched Plains', 'Cracked Ground', 'Rock', 'The ground is cracked and parched, splitting from the intense heat.', 0.12),
    ('Scorched Plains', 'Fiery Ridge', 'Rock', 'A ridge with flames flickering along its jagged edges.', 0.15),
    ('Scorched Plains', 'Ember Valley', 'Grassland', 'A valley filled with smoldering embers and glowing ash.', 0.18),
    ('Scorched Plains', 'Scorching Winds', 'Desert', 'Hot, scorching winds that buffet travelers relentlessly.', 0.15),
    ('Scorched Plains', 'Molten Flow', 'Rock', 'A slow-moving stream of molten lava carving its path through the plains.', 0.33),
    ('Scorched Plains', 'Volcanic Vents', 'Rock', 'Vents spewing lava and gouts of fire into the air.', 0.15),
    ('Scorched Plains', 'Blasted Ridge', 'Rock', 'A ridge blasted by volcanic eruptions, with scattered debris.', 0.38),
    ('Scorched Plains', 'Crimson Sands', 'Desert', 'Sands stained crimson from the intense heat and volcanic minerals.', 0.15),
    ('Scorched Plains', 'Smoldering Thicket', 'Flora', 'A thicket of plants that smolder with ember-like sparks.', 0.15),
    ('Scorched Plains', 'Ashen Crags', 'Rock', 'Craggy rocks covered in layers of ashen residue.', 0.45),
    ('Scorched Plains', 'Erupting Caldera', 'Desert', 'A caldera periodically erupting with bursts of fiery magma.', 0.15),
    ('Havenreach', 'Havenreach Town Center', 'Town', 'The heart of Havenreach, bustling with activity and trade.', 0.0),
    ('Havenreach', 'Havenreach Residential Area', 'Town', 'Quaint houses where residents of Havenreach reside.', 0.0),
    ('Havenreach', 'Havenreach Marketplace', 'Town', 'A lively market where various goods are bought and sold.', 0.0),
    ('Havenreach', 'Havenreach Training Grounds', 'Town', 'A dedicated area for honing combat skills and techniques.', 0.0),
    ('Tide Whisper Coves', 'Rocky Shore', 'Coast', 'A rocky shore where the relentless waves crash against the rugged cliffs.', 0.15),
    ('Tide Whisper Coves', 'Sandy Beach', 'Coast', 'A peaceful sandy beach stretching along the coastline, inviting relaxation.', 0.15),
    ('Tide Whisper Coves', 'Tidal Pools', 'Coast', 'Natural pools formed by the ebb and flow of the tides, teeming with marine life.', 0.3),
    ('Tide Whisper Coves', 'Cave Entrance', 'Coast', 'A mysterious cave entrance leading to hidden chambers beneath the cliffs.', 0.45),
    ('Tide Whisper Coves', 'Sea Cliffs', 'Coast', 'Sheer cliffs that offer breathtaking views of the churning sea below.', 0.15),
    ('Tide Whisper Coves', 'Secluded Cove', 'Coast', 'A secluded cove hidden away from prying eyes, providing solitude and tranquility.', 0.12),
    ('Tide Whisper Coves', 'Sunken Shipwreck', 'Coast', 'The remnants of a shipwreck, a haunting reminder of past maritime tragedies.', 0.15),
    ('Tide Whisper Coves', 'Underwater Cave', 'Coast', 'An underwater cave system filled with bioluminescent wonders and hidden treasures.', 0.21),
    ('Tide Whisper Coves', 'Sea Arch', 'Coast', 'A natural arch carved by the relentless power of the ocean waves.', 0.3),
    ('Tide Whisper Coves', 'Tidecarvers Retreat', 'Coast', 'A hidden retreat where weary travelers find respite and share tales of the sea.', 0.36),
    ('Tide Whisper Coves', 'Coral Reef', 'Coast', 'A vibrant coral reef teeming with colorful marine life and hidden treasures.', 0.15),
    ('Tide Whisper Coves', 'Whale Watching Point', 'Coast', 'A prime vantage point for observing majestic whales as they migrate through the waters.', 0.15),
    ('Tide Whisper Coves', 'Treacherous Currents', 'Coast', 'Dangerous currents that pose a challenge for even the most skilled swimmers.', 0.15),
    ('Tide Whisper Coves', 'Mystic Tidal Pools', 'Coast', 'Enchanted tidal pools with mystical properties and hidden magical artifacts.', 0.24),
    ('Tide Whisper Coves', 'Hidden Grotto', 'Coast', 'A hidden grotto accessible only during low tide, concealing secrets of the sea.', 0.36),
    ('Tide Whisper Coves', 'Shipwreck Graveyard', 'Coast', 'A haunting graveyard of shipwrecks, where tales of lost treasures and tragic fates linger.', 0.18),
    ('Grimhold', 'Grimhold Town Center', 'Town', 'The heart of Grimhold, a somber town protected by a network of thorny vines and shadowy guardians.', 0.0),
    ('Grimhold', 'Grimhold Residential Area', 'Town', 'Houses where the scarred residents of Grimhold dwell, carrying an uncanny connection to dark magic.', 0.0),
    ('Grimhold', 'Grimhold Black Market', 'Town', 'A hidden market in the shadows, where forbidden alliances and forbidden knowledge thrive.', 0.0),
    ('Grimhold', 'Grimhold Spellbound Library', 'Town', 'A repository of forbidden tomes and eldritch mysteries, tempting adventurers seeking dark power.', 0.0),
    ('Shadowmire', 'Misty Bog', 'Marsh', 'A mist-covered bog where eerie lights dance and dangerous creatures lurk.', 0.15),
    ('Shadowmire', 'Quagmire', 'Marsh', 'A treacherous quagmire with unstable ground and hidden sinkholes.', 0.15),
    ('Shadowmire', 'Witchs Hut', 'Marsh', 'A decrepit hut inhabited by witches who dabble in dark magic and forbidden potions.', 0.3),
    ('Shadowmire', 'Blighted Grove', 'Forest', 'A blighted grove where twisted trees and poisonous flora thrive.', 0.45),
    ('Shadowmire', 'Enchanted Path', 'Forest', 'A path infused with enchantments, leading to mysterious and dangerous destinations.', 0.15),
    ('Shadowmire', 'Foggy Clearing', 'Forest', 'A clearing perpetually enveloped in a thick, oppressive fog.', 0.12),
    ('Shadowmire', 'Haunted Ruins', 'Dungeon', 'Ruins haunted by malevolent spirits, echoing with whispers of forgotten atrocities.', 0.15),
    ('Shadowmire', 'Necrotic Crypt', 'Dungeon', 'A crypt tainted by necrotic energies, home to undead abominations and restless souls.', 0.21),
    ('Shadowmire', 'Spectral Woods', 'Forest', 'A dense woods teeming with spectral entities and ghostly phenomena.', 0.3),
    ('Shadowmire', 'Cursed Road', 'Path', 'A road said to be cursed, attracting malevolent creatures and ill fortune.', 0.36),
    ('Shadowmire', 'Misty Clearing', 'Path', 'A clearing where an otherworldly mist obscures the surroundings.', 0.15),
    ('Shadowmire', 'Lost Bridge', 'Path', 'A crumbling bridge that carries an aura of abandonment and tragedy.', 0.15),
    ('Shadowmire', 'Battle Tower', 'Dungeon', 'A Dungeon left in ruins form decades of war.', 0.15),
    ('Shadowmire', 'Grim Catacombs', 'Dungeon', 'A labyrinthine catacomb filled with cryptic markings and restless undead.', 0.24),
    ('Shadowmire', 'Dark Pathway', 'Path', 'A pathway said to be cursed, attracting malevolent creatures and ill fortune.', 0.36),
    ('Ashenfell', 'Ashenfell Town Center', 'Town', 'The heart of Ashenfell, a remote outpost surrounded by charred earth and jagged, lifeless peaks.', 0.0),
    ('Ashenfell', 'Ashenfell Residential Area', 'Town', 'Houses where the scarred inhabitants of Ashenfell find respite from the unforgiving wilderness.', 0.0),
    ('Ashenfell', 'Ashenfell Outpost Market', 'Town', 'A makeshift market where rugged adventurers trade tales and essential supplies.', 0.0),
    ('Ashenfell', 'Ashenfell Training Grounds', 'Town', 'A desolate area where warriors and survivors sharpen their skills against the harsh environment.', 0.0),
    ('The Ember Barrens', 'Scorched Wastes', 'Wasteland', 'Endless stretches of scorched earth, devoid of life and ravaged by constant firestorms.', 0.50),
    ('The Ember Barrens', 'Volcanic Ridge', 'Wasteland', 'A jagged ridge formed by ancient volcanic activity, belching out noxious fumes and lava.', 0.50),
    ('The Ember Barrens', 'Burning Sands', 'Desert', 'Endless dunes of scorching sand, where heatwaves distort the horizon.', 0.50),
    ('The Ember Barrens', 'Molten Crater', 'Wasteland', 'A massive crater spewing molten lava and intense heat, forming a deadly landscape.', 0.50),
    ('The Ember Barrens', 'Searing Canyons', 'Wasteland', 'Deep canyons filled with searing heat and treacherous terrain.', 0.50),
    ('The Ember Barrens', 'Smoldering Woods', 'Forest', 'A charred forest with smoldering trees, where flames lick at the remnants of life.', 0.50),
    ('The Ember Barrens', 'Ashen Plateau', 'Wasteland', 'A desolate plateau covered in layers of fine ash, carried by the wind from distant fires.', 0.50),
    ('The Ember Barrens', 'Ember Marsh', 'Marsh', 'A marshland where flickering embers dance atop murky waters, casting an eerie glow.', 0.18),
    ('The Ember Barrens', 'Blazing Ruins', 'Dungeon', 'Ruins engulfed in flames, housing ancient secrets and unimaginable dangers.', 0.50),
    ('The Ember Barrens', 'Cinder Path', 'Path', 'A path littered with blackened cinders, radiating intense heat and an ominous aura.', 0.50),
    ('The Ember Barrens', 'Charred Grove', 'Forest', 'A grove of twisted, charred trees that stand as a testament to the destructive power of fire.', 0.75);

```

## Usage
[Back to top](#top)
#### Use this from the server console to start the game bot
```
/usr/bin/python3 /home/Kingdom-of-Crowns/gameBot.py
```

#### Use *help to see all commands. *join to create an account and *play to open a game thread

```
# See all commands
*help

# Create an account
*join

# Open a game thread
*play

```
#### When using *join you will be asked to provide a Crown address and to pay a joining fee in Crown(CRW). This is to help fund the economy, fees etc
#### If a player sends an incorrect amount when joining, the script will return funds to the player minus a fee.
```bash
if return_amount < 0.01:
    fee_percentage = 20
elif return_amount < 0.10:
    fee_percentage = 10
elif return_amount <= 1.00:
    fee_percentage = 5
else:
    fee_percentage = 1
```

## Contributing
[Back to top](#top)
#### Please create an issue or feature request if you have ideas or have found a bug
#### Some issues which would greatly improve the game
```
1. Code management (Separate files for functions and variables/constants)
2. Function recycling
3. Data structuring
4. Conventions and rules, not just naming but code style in general
```

#### Some features which would improve gameplay
```
1. PvP interactions. Players drops everything if they lose to a player. A player can choose not to battle
2. End game dimension. Once a player reaches the very end they're "teleported" to another dimension, where the player is in a while loop of mob battles, the player can choose to leave the dimension after winning a battle. Mobs in this dimension will drop ultra rare items.
3. Crown NFT achivement rewards.
4. Crown(CRW) rewards.
5. Item NFT Collection/Burn system. A kind of sticker book in which the player collections items in game, returns back to town to burn it into an NFT. This now becomes the "sticker", and the player has effectively "got" that item in their "sticker book"
```

[🔝](#top)