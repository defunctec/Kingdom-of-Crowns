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
RPC_PASSWORD = 'rpcpassword'

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