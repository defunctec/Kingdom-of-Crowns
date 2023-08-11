import discord
import signal
import sys
import aiomysql
import asyncio
import datetime
import time
import threading
import aiohttp
import math
import io
import os
import logging
import random
import traceback
from asyncio import Lock
from config import SLEEP_TIME, DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, RPC_USER, RPC_PASSWORD, CHANNEL_ID, TOTAL_TILES, BOT_TOKEN, HEALTH_PER_STRENGTH, MANA_PER_INTELLIGENCE, DAMAGE_PER_STRENGTH, DAMAGE_PER_INTELLIGENCE, SPAWN_BOSS_CHANCE, DODGE_PER_AGILITY, INACTIVE_TIME, BATTLE_TIMEOUT, BOSS_DROP_CHANCE, MOB_DROP_CHANCE, RARITY_WEIGHTS, STARTING_ARMOUR_ID, STARTING_ARMOUR_CLASS, MIN_GOLD_PER_STRENGTH, MAX_GOLD_PER_STRENGTH, DEFAULT_AGILITY_REDUCTION 
from crownConn import is_valid_crw_address, generate_payment_address, get_block_count, is_crown_wallet_online
from discord import Intents, Embed
from discord.ext import commands
from riddles import riddles
from puzzles import word_puzzles

# Define the global scheduler_thread variable
scheduler_thread = None
exit_event = threading.Event()  # Event to signal thread exit

# Create a MySQL pool connection
pool = None  # We will initialize this in the main function

async def create_pool():
    global pool
    if pool is None:
        pool = await aiomysql.create_pool(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            db=DB_NAME,
        )
    return pool

# Function to ping the MySQL connection
async def ping_mysql_connection():
    while True:
        pool = await create_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                await cur.fetchone()  # Consume and discard the result
        logging.info("MySQL connection pinged successfully.")
        await asyncio.sleep(3600)  # Delay for 1 hour

# Define the signal handler function
def signal_handler(signal, frame):
    # Perform any cleanup or necessary actions before exiting
    logging.info("Exiting...")
    loop = asyncio.get_event_loop()
    tasks = asyncio.all_tasks(loop=loop)

    for task in tasks:
        task.cancel()

    # Create a new asyncio task to handle cleanup rather than running a new event loop
    asyncio.ensure_future(asyncio.gather(*tasks))

# Register the signal handler for the SIGINT and SIGTERM signal (Ctrl+C)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Configure logging
logging.basicConfig(filename='koc_error_log.txt', level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')

# Global to check command cooldown
player_cooldowns = {}
battle_message_id = None

open_area_storage = set()
open_town_center = set()
open_shops = set()
deposit_items = set()
depositing_items = set()
equipping_items = set()
taken_items = set()
open_selling_menus = set()

# Create a dictionary to hold the locks for each user
user_locks = {}

# Initialize Discord bot
try:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.reactions = True
    bot = commands.Bot(command_prefix='*', intents=intents)
except Exception as e:
    logging.error("Error occurred while initializingBot: %s", e)

# Set a global empty dictionary array for thread deletion
active_threads = {}

async def create_pool_connection():
    global pool
    pool = await create_pool()

# Define the main asynchronous function
async def main():
    try:
        await asyncio.sleep(SLEEP_TIME)
        await create_pool_connection()
        await run_bot()
    except asyncio.exceptions.CancelledError:
        # Suppress the CancelledError when the asyncio loop is stopped
        pass

async def run_scheduler():
    while True:
        await ping_mysql_connection()
        await asyncio.sleep(3600)  # Delay for 1 hour

# Run the bot
async def run_bot():
    # Start the scheduler in the background
    asyncio.create_task(run_scheduler())

    # Start the bot
    await bot.start(BOT_TOKEN)
    
# Run the ping function as an asyncio task when the bot is ready
@bot.event
async def on_ready():
    await create_pool_connection()

@bot.command(name='join', aliases=['jo', 'j'], help='Join the game using your Crown address.', usage='*join YOURADDRESS or *jo/*j')
async def join(ctx, crw_address=None):

    # Get players discord ID
    discord_id = ctx.author.id

    # Check command cooldown
    if not await check_cooldown(ctx, discord_id):
        return

    # Check if the Crown wallet is not online
    elif not await is_crown_wallet_online():
        await ctx.send('The Crown wallet is currently offline. Please try again later.')
        return

    elif crw_address is None:
        await ctx.send('Please provide a CRW address.')
        return

    elif not is_valid_crw_address(crw_address):
        await ctx.send('Invalid CRW address! Please enter a valid CRW address.')
        return

    else:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:  # Using aiomysql.DictCursor to get results as dictionaries
                try:

                    # Check if the player is already in the database
                    await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                    await cursor.execute("SELECT * FROM players WHERE discord_id = %s", (discord_id,))
                    result = await cursor.fetchone()

                    # Check if player info was obtained from the players table
                    if result:
                        # Check if the account is activated
                        if result['activated']:
                            await ctx.send('You are already registered and your account is activated.')
                            return
                        else:
                            # Player has registered but not yet activated

                            # Get the payment address from the database
                            payment_address = result['payment_address']

                            # Send payment instruction to player using discord embed
                            embed = discord.Embed(
                                title='Account Activation',
                                description='Your account is not yet activated yet. Please follow the instructions below.',
                                color=discord.Color.red())

                            fees = '''
                                Tier 1: 10.10 CRW
                                Tier 2: 50.50 CRW
                                Tier 3: 100.10 CRW
                                Tier 4: 500.50 CRW
                                Tier 5: 1000.10 CRW
                            '''
                            embed.add_field(
                                name='Instructions',
                                value='Please complete your registration or wait for 6 confirmations:\n' + fees,
                                inline=False)

                            embed.add_field(
                                name='Payment Address',
                                value=payment_address,
                                inline=False)

                            await ctx.send(embed=embed)
                            return
                    else:
                        # Completely new player, provide them with instructions on how to pay the joining fee

                        # Generate a payment address for the user
                        payment_address = await generate_payment_address()

                        # Check if the address was created correctly
                        if not payment_address:
                            raise ValueError('No payment address was generated.')

                        # Attempt to create a new player in the database
                        if await register_new_player(discord_id, crw_address, payment_address) is True:

                            # If creation of new player is successful, notify the player with an embed
                            embed = discord.Embed(
                                title='Account Activation',
                                description='Paying a joining fee allows us to maintain Crown rewards',
                                color=discord.Color.red()
                            )

                            fees = '''
                                Tier 1: 10.10 CRW
                                Tier 2: 50.50 CRW
                                Tier 3: 100.10 CRW
                                Tier 4: 500.50 CRW
                                Tier 5: 1000.10 CRW
                            '''

                            embed.add_field(
                                name='Instructions',
                                value='Please send the exact amount of CRW according to your desired tier:\n' + fees,
                                inline=False
                            )

                            embed.add_field(
                                name='Payment Address',
                                value=payment_address,
                                inline=False
                            )

                            await ctx.send(embed=embed)

                            # Essential logging line for debugging and monitoring
                            logging.info(f"Payment instructions sent to the player with discord_id: {discord_id}")

                            return
                except Exception as e:
                    logging.error(f"An error occurred while joining the game: {e}")
                    await ctx.send('An error occurred while joining the game. Please try again later.')

# Open a new game thread
@bot.command(name='play', aliases=['pl', 'p'], help='Open a new game thread', usage='*play or *pl/*p')
async def play(ctx):
    logging.info(f"Received command to play from Discord ID {ctx.author.id}")

    try:
        # Check if MYSQL is connected
        if pool is None:
            await ctx.send('The database cannot establish connection, please try again later')
            logging.error("MySQL connection is not active.")
            return

        # Get the users discord ID
        discord_id = ctx.author.id

        # Check command cooldown
        if not await check_cooldown(ctx, discord_id):
            logging.warning(f"Command cooldown check failed for Discord ID {discord_id}")
            return

        # Check if the Crown wallet is online
        elif not await is_crown_wallet_online():
            await ctx.send('The Crown wallet is currently offline. Please try again later.')
            logging.warning("Crown wallet is offline.")
            return

        else:
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # start a new transaction

                    # Execute SQL queries
                    await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                    await cursor.execute("SELECT activated FROM players WHERE discord_id = %s", (discord_id,))
                    result = await cursor.fetchone()

                    # Player checks before game thread is opened
                    if not result:
                        await ctx.send('You are not registered. Please use the `*join YOURADDRESS` command to register.')
                        logging.info("Player not registered.")
                    elif result[0] == 0:
                        await ctx.send('Your account is not activated. Please complete the registration process by using `*join YOURADDRESS`')
                        logging.info("Player account not activated.")
                    elif discord_id in active_threads:
                        await ctx.send('You are already in a game. Please finish your current game before starting a new one.')
                        logging.info("Player already in a game.")
                        return
                    else:
                        # Get the game interaction channel or create a new one if it doesn't exist
                        game_interaction_channel = ctx.channel
                        if not game_interaction_channel.permissions_for(ctx.guild.me).manage_channels:
                            await ctx.send("I don't have the required permissions to manage channels.")
                            logging.warning("Bot lacks permission to manage channels.")
                            return

                        try:
                            # Get battle information from battles table
                            await cursor.execute("SELECT opponent_name, opponent_type, opponent_health, player_health, current_location FROM battles WHERE discord_id = %s AND battle_ended_at IS NULL ORDER BY battle_ended_at ASC LIMIT 1", (discord_id,))
                            battle_info = await cursor.fetchone()
                            # If player is in battle, proceed with last battle
                            if battle_info:
                                # Get the variables from battle_info
                                opponent_name, opponent_type, opponent_health, player_health, current_location = battle_info

                                try:
                                    # Open a new game thread 
                                    thread_name = f"{ctx.author.name}'s Game Interaction"
                                    thread = await game_interaction_channel.create_thread(
                                        name=thread_name,
                                        auto_archive_duration=None,
                                    )

                                except Exception as e:
                                    logging.error(f"An error occurred while creating the game interaction thread: {e}")
                                    await ctx.send('An error occurred while creating your game interaction thread. Please try again later.')
                                    return

                                try:
                                    # Continue with battle
                                    await handle_continue_mob_battle(discord_id, thread)

                                    # Delete the command message
                                    await ctx.message.delete()
                                    logging.info(f"Deleted play command message for Discord ID {discord_id}")

                                    # Player Cooldown
                                    player_cooldowns[discord_id] = {'last_time': time.time()}
                                    # Start the timer to check for inactivity and delete the thread
                                    await manage_thread_activity(discord_id, thread, active_threads)

                                    return
                                except Exception as e:
                                    logging.error(f"An error occurred while handling the battle or managing the thread activity: {e}")
                                    await ctx.send('An error occurred during your battle. Please try again later.')
                                    return
                            else:
                                try:
                                    # Retrieve the player's current tile ID from the player_location table
                                    await cursor.execute("SELECT tile_id FROM player_location WHERE discord_id = %s", (discord_id,))
                                    tile_id = await cursor.fetchone()

                                    if tile_id:

                                        # Retrieve the tile and area information from the map_tiles table
                                        await cursor.execute("SELECT tile_name, area_name, description FROM map_tiles WHERE id = %s", (tile_id[0],))
                                        tile_info = await cursor.fetchone()

                                        # If tile info is found, proceed with game
                                        if tile_info:
                                            # Get variables from tile_info
                                            tile_name, area_name, description = tile_info

                                            # Create a new game thread
                                            thread_name = f"{ctx.author.name}'s Game Interaction"

                                            thread = await game_interaction_channel.create_thread(
                                                name=thread_name,
                                                auto_archive_duration=None
                                            )

                                            await thread.send(f"<@{discord_id}>")

                                            # Create an embed message for the move notification
                                            if 'Residential Area' in tile_name:
                                                # This is a residential area
                                                embed = discord.Embed(
                                                    title=f"Continuing from {tile_name} in {area_name}",
                                                    description="Choose a direction to move:",
                                                    color=discord.Color.green()
                                                )
                                                embed.add_field(name="Left", value=":arrow_left:", inline=True)
                                                embed.add_field(name="Right", value=":arrow_right:", inline=True)
                                                embed.add_field(name="Storage", value=":house:", inline=True)

                                                # Mention the user
                                                embed.set_footer(text=f"Requested by @{ctx.author.name}")

                                                # Send the embed message to the thread
                                                message = await thread.send(embed=embed)
                                                await message.add_reaction('⬅️')
                                                await message.add_reaction('➡️')
                                                await message.add_reaction('🏠')
                                            elif 'Town Center' in tile_name:
                                                # This is a town center
                                                embed = discord.Embed(
                                                    title=f"Continuing from {tile_name} in {area_name}",
                                                    description="Choose a direction to move or access the bank:",
                                                    color=discord.Color.green()
                                                )
                                                embed.add_field(name="Left", value=":arrow_left:", inline=True)
                                                embed.add_field(name="Right", value=":arrow_right:", inline=True)
                                                embed.add_field(name="Bank", value=":bank:", inline=True)

                                                # Mention the user
                                                embed.set_footer(text=f"Requested by @{ctx.author.name}")

                                                # Send the embed message to the thread
                                                message = await thread.send(embed=embed)
                                                await message.add_reaction('⬅️')
                                                await message.add_reaction('➡️')
                                                await message.add_reaction('🏦')
                                            elif any(tile_name.endswith(market) for market in ('Marketplace', 'Black Market', 'Outpost Market')):
                                                # This is a Marketplace
                                                embed = discord.Embed(
                                                    title=f"Welcome to {tile_name} in {area_name}",
                                                    description="You are now in the marketplace. Here you can buy and sell goods.",
                                                    color=discord.Color.green()
                                                )
                                                embed.add_field(name="Left", value=":arrow_left:", inline=True)
                                                embed.add_field(name="Right", value=":arrow_right:", inline=True)
                                                embed.add_field(name="Shop", value=":shopping_cart:", inline=True)

                                                # Send the embed message to the thread
                                                message = await thread.send(embed=embed)
                                                await message.add_reaction('⬅️')
                                                await message.add_reaction('➡️')
                                                await message.add_reaction('🛒')
                                            elif 'Training Grounds' in tile_name or 'Spellbound Library' in tile_name:
                                                # This is a special area
                                                embed = discord.Embed(
                                                    title=f"Welcome to {tile_name} in {area_name}",
                                                    description="You are now in a special training area. Here you can train and improve your skills.",
                                                    color=discord.Color.green()
                                                )
                                                embed.add_field(name="Left", value=":arrow_left:", inline=True)
                                                embed.add_field(name="Right", value=":arrow_right:", inline=True)
                                                embed.add_field(name="Train", value=":dart:", inline=True)

                                                # Send the embed message to the thread
                                                message = await thread.send(embed=embed)
                                                await message.add_reaction('⬅️')
                                                await message.add_reaction('➡️')
                                                await message.add_reaction('🎯')  # Train
                                            else:
                                                # This is a normal area
                                                embed = discord.Embed(
                                                    title=f"Moved to {tile_name} in {area_name}.",
                                                    description=f"{description}",
                                                    color=discord.Color.green()
                                                )
                                                embed.add_field(name="Left", value=":arrow_left:", inline=True)
                                                embed.add_field(name="Right", value=":arrow_right:", inline=True)

                                                # Mention the user
                                                embed.set_footer(text=f"Requested by @{ctx.author.name}")

                                                # Send the embed message to the thread
                                                message = await thread.send(embed=embed)
                                                await message.add_reaction('⬅️')
                                                await message.add_reaction('➡️')

                                            # Consume unread results (Better code required)
                                            await cursor.fetchall()  

                                            # Delete the command message
                                            await ctx.message.delete()
                                            logging.info(f"Deleted play command message for Discord ID {discord_id}")

                                            # Player Cooldown
                                            player_cooldowns[discord_id] = {'last_time': time.time()}
                                            # Start the timer to check for inactivity and delete the thread
                                            await manage_thread_activity(discord_id, thread, active_threads)
                                        else:
                                            # No tile info found for the player
                                            await ctx.send("There is an issue with your gamestate, please contact @defunctec")
                                            logging.error("No tile_info found for the player")
                                            return
                                    else:
                                        # No tile info found for the player
                                        await ctx.send("There is an issue with your gamestate, please contact @defunctec")
                                        logging.error("No tile_id info found for the player")
                                        return

                                except Exception as e:
                                    # error getting player information
                                    logging.error(f"An error occurred while getting player information: {e}")
                                    return
                        except Exception as e:
                            # Opening game thread failed
                            logging.error(f"An error occurred while creating the thread: {e}")
                            return

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        await ctx.send('An unexpected error occurred. Please try again later.')
        return

# Open the player's inventory
@bot.command(name='inventory', aliases=['inv', 'i'], help='View your inventory', usage='*inventory or *inv/*i')
async def inventory(ctx):
    # Get the user's discord ID and thread
    discord_id = ctx.author.id
    thread = ctx.channel

    if not isinstance(thread, discord.Thread):
        await ctx.send("This command can only be run from a thread.")
        return
    else:
        try:
            # Check if MYSQL is connected
            if pool is None:
                await ctx.send('The database cannot establish a connection, please try again later')
                logging.info("MySQL connection is not active.")
                return

            # Check command cooldown
            if not await check_cooldown(ctx, discord_id):
                return

            # Check if the Crown wallet is online
            elif not await is_crown_wallet_online():
                await ctx.send('The Crown wallet is currently offline. Please try again later.')
                return

            elif discord_id in open_shops:
                await thread.send("You cannot access your inventory while in the shop.")
                return

            else:
                # Function to show inventory embed.
                await get_player_inventory_embed(ctx, discord_id)

        except Exception as e:
            logging.error(f"An error occurred while viewing the inventory: {str(e)}")
            await ctx.send('An error occurred while viewing the inventory. Please try again later.')
        # Player Cooldown
        player_cooldowns[discord_id] = {'last_time': time.time()}
        # Start the timer to check for inactivity and delete the thread
        await manage_thread_activity(discord_id, thread, active_threads)

# View user's stats
@bot.command(name='stats', aliases=['st', 's'], help='View your current stats', usage='*stats or *st/*s')
async def stats(ctx):
    # Get the user's discord ID and thread
    discord_id = ctx.author.id
    thread = ctx.channel

    if not isinstance(thread, discord.Thread):
        await ctx.send("This command can only be run from a thread.")
        return
    else:
        try:
            # Check if MYSQL is connected
            if pool is None:
                await ctx.send('The database cannot establish a connection, please try again later')
                logging.error("MySQL connection is not active.")
                return

            # Check command cooldown
            if not await check_cooldown(ctx, discord_id):
                logging.warning(f"Command cooldown in effect for user {discord_id}.")
                return

            # Check if the Crown wallet is online
            elif not await is_crown_wallet_online():
                await ctx.send('The Crown wallet is currently offline. Please try again later.')
                return

            else:
                async with pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cursor:
                        
                        try:
                            # Get the player's base stats from player_attributes
                            base_stats = await fetch_base_stats(ctx, discord_id)

                            if base_stats is not None:
                                # Build the embed to display to players
                                embed_message = Embed(title=f"Stats for {ctx.author.name}", color=0x00ff00)
                                await add_base_stats_to_embed(embed_message, base_stats)

                                # Inspect player's equipped items and return stats
                                equipped_stats, inventory = await fetch_equipped_stats(ctx, discord_id)

                                if inventory is not None:
                                    # Add equipped and base stats together
                                    total_stats = await calculate_total_stats(ctx, discord_id, base_stats, equipped_stats)

                                    await add_total_stats_to_embed(embed_message, total_stats)
                                    # Obtain health and mana based on total stats
                                    health_and_mana = await fetch_health_and_mana(ctx, cursor, discord_id, total_stats)
                                    if health_and_mana is not None:
                                        await add_health_and_mana_to_embed(embed_message, health_and_mana)

                                        await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                                        # Fetch the XP from player_attributes table
                                        await cursor.execute("SELECT xp FROM player_attributes WHERE discord_id = %s", (discord_id,))
                                        xp_result = await cursor.fetchone()
                                        if xp_result:
                                            xp = xp_result["xp"]
                                            embed_message.add_field(name="XP", value=f"{xp}", inline=True)

                                        # Fetch the player's rank from players table
                                        await cursor.execute("SELECT player_rank FROM players WHERE discord_id = %s", (discord_id,))
                                        rank_result = await cursor.fetchone()
                                        if rank_result:
                                            rank = rank_result["player_rank"]
                                            embed_message.add_field(name="Rank", value=f"{rank}", inline=True)

                                        # Fetch the player's level from player_attributes table
                                        await cursor.execute("SELECT level FROM player_attributes WHERE discord_id = %s", (discord_id,))
                                        level_result = await cursor.fetchone()
                                        if level_result:
                                            level = level_result["level"]
                                            embed_message.add_field(name="Level", value=f"{level}", inline=True)

                                    await ctx.send(embed=embed_message)
                                else:
                                    await ctx.send("Your base stats are not available.")
                            else:
                                await ctx.send("An error occurred while viewing the stats. Please try again later.")

                        except Exception as e:
                            raise e

                        # Player Cooldown
                        player_cooldowns[discord_id] = {'last_time': time.time()}
                        # Start the timer to check for inactivity and delete the thread
                        await manage_thread_activity(discord_id, thread, active_threads)

        except Exception as e:
            logging.error(f"An error occurred while viewing the stats: {str(e)}")
            await ctx.send('An error occurred while viewing the stats. Please try again later.')

@bot.command(name='search', aliases=['sr', 'se'], help='Get info about an item using the item\'s name.', usage='*search <item_name>  or *sr/*se')
async def search(ctx, *search_term: str):
    # Extract the necessary information from the Discord context
    discord_id = ctx.author.id
    thread = ctx.channel

    if not isinstance(thread, discord.Thread):
        await ctx.send("This command can only be run from a thread.")
        return
    else:
        try:
            # Check if MYSQL is connected
            if pool is None:
                await ctx.send('The database cannot establish a connection, please try again later')
                logging.error("MySQL connection is not active.")
                return

            # Check command cooldown
            if not await check_cooldown(ctx, discord_id):
                return

            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:

                    try:
                        # Join the terms back into a single string. This handles item names with more than one word
                        search_term = ' '.join(search_term)

                        # Search the items, weapons, and armour tables
                        await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                        await cursor.execute(
                            "SELECT id, name, class, rarity, strength, agility, intelligence, stamina, description, 'item' AS table_name FROM items WHERE name = %s "
                            "UNION "
                            "SELECT id, name, class, rarity, strength, agility, intelligence, stamina, description, 'weapon' AS table_name FROM weapons WHERE name = %s "
                            "UNION "
                            "SELECT id, name, class, rarity, strength, agility, intelligence, stamina, description, 'armour' AS table_name FROM armour WHERE name = %s",
                            (search_term, search_term, search_term)
                        )

                        search_results = await cursor.fetchall()

                        # Process and display the search results
                        await display_search_results(discord_id, thread, search_results)

                    except Exception as e:
                        raise e

        except Exception as e:
            logging.error(f"An error occurred during item search: {str(e)}", exc_info=True)
            await ctx.send('An error occurred during item search. Please try again later.')

@bot.command(name='quit', aliases=['q', 'exit'], help='Manually delete the current thread.')
async def quit_cmd(ctx):
    """
    Command to manually delete the current thread the user is in.
    """
    # Get the users discord ID
    discord_id = ctx.author.id
    thread = ctx.channel
    logging.info(f"Checking active_threads for discord_id: {discord_id}")
    # Check if the command is invoked in a thread
    if not isinstance(thread, discord.Thread):
        await ctx.send("This command can only be run from a thread.")
        return

    # Prompt the user for confirmation
    await ctx.send("Are you sure you want to delete this thread? (Yes/No)")

    def check(message):
        return message.author == ctx.author and message.content.lower() in ['yes', 'no']

    try:
        msg = await bot.wait_for('message', timeout=60, check=check)  # Wait for user response or timeout after 60 seconds
        if msg.content.lower() == 'no':
            await ctx.send("Thread deletion cancelled.")
            return
    except asyncio.TimeoutError:
        await ctx.send("Confirmation timed out. Thread deletion cancelled.")
        return

    # Continue with thread deletion if 'yes' was the response
    if discord_id in active_threads:
        # Cancel the existing task for this thread to avoid interference
        task, _, _ = active_threads[discord_id]
        task.cancel()

        # Manual cleanup before thread deletion
        del active_threads[discord_id]
        user_lock = user_locks.get(discord_id)
        if user_lock and user_lock.locked():
            user_lock.release()
            logging.info(f"User lock for discord_id {discord_id} released due to manual quit.")

        # NOTE: Add any other cleanups here

        await thread.delete()
        logging.info(f"Player {discord_id} manually quit thread")
    else:
        await ctx.send(f"You don't have an active thread to delete.")

# Command to change CRW address
@bot.command(name='change_address', aliases=['ca'], help='Change your CRW address', usage='*change_address <new_CRW_address>  or *ca')
async def change_address(ctx, crw_address=None):
    # Check if MYSQL is connected
    if pool is None:
        await ctx.send('The database cannot establish connection, please try again later')
        logging.error("MySQL connection is not active.")
        return

    # Get the user's discord ID
    discord_id = ctx.author.id

    if not isinstance(ctx.channel, discord.Thread):
        await ctx.send("This command can only be run from a thread.")
        return

    # Check command cooldown
    if not await check_cooldown(ctx, discord_id):
        return
    elif not await is_crown_wallet_online():
        await ctx.send('The Crown wallet is currently offline. Please try again later.')
        return
    elif crw_address is None:
        await ctx.send('Please provide a CRW address.')
        return
    elif not is_valid_crw_address(crw_address):
        await ctx.send('Invalid CRW address! Please enter a valid CRW address.')
        return

    try:
        # Check if MYSQL is connected
        if pool is None:
            await ctx.send('The database cannot establish a connection, please try again later')
            logging.error("MySQL connection is not active.")
            return

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await conn.begin()  # Begin the transaction

                try:
                    # Update the player's CRW address in the database
                    await cursor.execute("UPDATE players SET crw_address = %s WHERE discord_id = %s", (crw_address, discord_id))
                    await conn.commit()

                    if cursor.rowcount > 0:
                        await ctx.send(f'Your CRW address has been updated to: {crw_address}')
                    else:
                        await ctx.send('No account found for the associated Discord ID. Please check and try again.')

                except Exception as e:
                    await conn.rollback()  # Rollback the transaction in case of an error
                    raise e

    except Exception as e:
        await ctx.send('An error occurred while updating the CRW address. Please try again later.')
        logging.error(f"An error occurred while updating the CRW address: {str(e)}")

@bot.command(name='blockcount', aliases=['bc'], help='Get the block count', usage='*blockcount or *bc')
async def blockcount(ctx):
    # Check if MYSQL is connected
    if pool is None:
        await ctx.send('The database cannot establish connection, please try again later')
        logging.error("MySQL connection is not active.")
        return
    # Get the user's discord ID
    discord_id = ctx.author.id

    # Check command cooldown
    if not await check_cooldown(ctx, discord_id):
        return
    elif not await is_crown_wallet_online():
        await ctx.send('The Crown wallet is currently offline. Please try again later.')
        return

    try:
        # Check if MYSQL is connected
        if pool is None:
            await ctx.send('The database cannot establish a connection, please try again later')
            logging.error("MySQL connection is not active.")
            return

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                block_count = await get_block_count()
                await ctx.send(f"Block count: {block_count}")

    except Exception as e:
        await ctx.send("Error in getting block count")
        logging.error(f"An error occurred while getting the block count: {str(e)}")

# Command to start a riddle task
#@bot.command(name='riddle', help='Start a riddle task')
#async def riddle(ctx):
    #if player["task"] is not None:
        #await ctx.send('You are already working on a task!')
        #return
    #riddle = random.choice(riddles)
    #player["task"] = {"type": "riddle", "answer": riddle[1]}
    #await ctx.send(f'Riddle for {ctx.author.name}: {riddle[0]}')

# Command to submit an answer to a riddle
#@bot.command(name='answer', help='Submit an answer to a riddle')
#async def answer(ctx, *, player_answer):
    #if player["task"] is None:
        #await ctx.send('You are not currently working on a task!')
    #elif player["task"]["type"] != "riddle":
        #await ctx.send('Your current task is not a riddle!')
    #elif player_answer.lower() not in player["task"]["answer"]:
        #await ctx.send('Incorrect answer. Try again!')
    #else:
        #player["task"] = None
        #player["CRW"] += 10
        #await ctx.send('Correct answer! You earned 10 CRW.')

# Command to start a word puzzle task
#@bot.command(name='word_puzzle', help='Start a word puzzle task')
#async def word_puzzle(ctx):
    #if player["task"] is not None:
        #await ctx.send('You are already working on a task!')
        #return
    #word_puzzle = random.choice(word_puzzles)
    #player["task"] = {"type": "word_puzzle", "answer": word_puzzle[1]}
    #await ctx.send(f'Word puzzle for {ctx.author.name}: {word_puzzle[0]}')

# Command to submit an answer to a word puzzle
#@bot.command(name='solve_word', help='Submit an answer to a word puzzle')
#async def solve_word(ctx, *, player_answer):
    #if player["task"] is None:
        #await ctx.send('You are not currently working on a task!')
    #elif player["task"]["type"] != "word_puzzle":
        #await ctx.send('Your current task is not a word puzzle!')
    #elif player_answer.lower() != player["task"]["answer"]:
        #await ctx.send('Incorrect answer. Try again!')
    #else:
        #player["task"] = None
        #player["CRW"] += 15  # Assuming word puzzles are worth 15 CRW
        #await ctx.send('Correct answer! You earned 15 CRW.')

async def get_reaction_payload(bot, message, discord_id, timeout=BATTLE_TIMEOUT):
    battle_message_id = message.id

    for emoji in ('⚔️', '🔴', '🔵', '📜'):
        await message.add_reaction(emoji)

    def check(payload):
        return payload.user_id == discord_id and payload.message_id == battle_message_id and str(payload.emoji) in ('⚔️', '🔴', '🔵', '📜')

    try:
        payload = await bot.wait_for('raw_reaction_add', timeout=timeout, check=check)
        return payload
    except asyncio.TimeoutError:
        # Handle the timeout error (player went AFK)
        logging.info(f"Battle timed out for discord id: {discord_id}")
        return None
    except Exception as e:
        # Handle other exceptions
        logging.error(f"An error occurred during the battle: {str(e)}")
        return None

@bot.event
async def on_raw_reaction_add(payload):
    try:
        global battle_message_id
        # Check if the reaction is from the bot itself
        if payload.member.bot:
            return

        # Fetch the channel and thread information
        channel = await bot.fetch_channel(payload.channel_id)
        thread = None

        # If the user reacted to the battle message
        if payload.message_id == battle_message_id:
            thread = await channel.fetch_thread(payload.message_id)

        # Check if the reaction is within a thread
        if isinstance(channel, discord.Thread):
            thread = channel

        # Check if the thread is a private thread
        if thread and thread.parent.id == CHANNEL_ID:  # Replace with the ID of the parent channel of private threads
            emoji = payload.emoji.name
            # Determine the possible directions based on the current tile ID
            discord_id = payload.user_id

            # Check if the player is in a battle
            if await is_player_in_battle(discord_id):
                logging.info("Player is in battle, cannot use...")
                return

            # Check if the player is in a menu
            if discord_id in open_area_storage:
                logging.info("Player is in a menu, cannot use...")
                return

            # Check if the player is in a shop menu
            if discord_id in open_shops:
                logging.info("Player is in a shop menu, cannot use...")
                return

            # Check if the player is in a shop selling menu
            if discord_id in open_selling_menus:
                logging.info("Player is in a shop selling menu, cannot use...")
                return

            # Add handling for the new inventory actions
            if emoji == '🔴':
                # Handle heal action
                heal_result, total_health = await use_health_potion(discord_id)
                if heal_result == "success":
                    player_health = total_health
                    await asyncio.sleep(1)
                    await thread.send(f"You used a health potion. Your health has been fully restored to {total_health}!")
                else:
                    await asyncio.sleep(1)
                    await thread.send(heal_result)
            elif emoji == '🔵':
                # Handle mana action
                mana_result, total_mana = await use_mana_potion(discord_id)
                if mana_result == "success":
                    current_mana = total_mana
                    await asyncio.sleep(1)
                    await thread.send(f"You used a mana potion. Your mana has been fully restored to {total_mana}!")
                else:
                    await thread.send(mana_result)
            elif emoji == '📜':
                # Handle teleport action
                teleport_result = await use_teleport_scroll(discord_id, thread)
                if teleport_result == "success":
                    await asyncio.sleep(1)
                    await thread.send("You used a teleport scroll. You have been teleported to your last residential tile!")
                else:
                    await asyncio.sleep(1)
                    await thread.send(teleport_result)
                return

            try:
                async with pool.acquire() as conn:
                    async with conn.cursor() as cursor:

                        user_lock = user_locks.get(discord_id)
                        if user_lock and user_lock.locked():
                            logging.info(f"User is locked: {user_lock}")
                            return

                        try:
                            # Retrieve the player's current tile from the database
                            tile_id = await get_current_tile_id(discord_id)
                        except Exception as e:
                            logging.error(f"An error occurred while retrieving tile ID: {str(e)}")
                            await thread.send("An error occurred while retrieving your location. Please try again later.")
                            return
                    
                        if tile_id:
                            await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                            await cursor.execute("SELECT tile_name, tile_type, area_name FROM map_tiles WHERE id = %s", (tile_id,))
                            tile_info = await cursor.fetchone()

                            if tile_info:
                                current_tile_name = tile_info[0]
                                current_tile_type = tile_info[1]
                                current_area_name = tile_info[2]

                                # Check if the player's reaction is a valid direction
                                if emoji == '⬅️':  # Move back
                                    if tile_id > 1:
                                        if await move_to_tile(discord_id, tile_id - 1, thread) is True:
                                            return
                                    else:
                                        await thread.send("Invalid direction!")
                                        return True
                                elif emoji == '➡️':  # Move forward
                                    if tile_id < TOTAL_TILES:
                                        if await move_to_tile(discord_id, tile_id + 1, thread) is True:
                                            return
                                    else:
                                        await thread.send("Invalid direction!")
                                        return
                                elif emoji == '🏠':  # Access Residential Area storage
                                    await handle_residential_area_storage(discord_id, thread)
                                    return
                                elif emoji == '🏦':  # Access Town Center🛒
                                    await handle_town_center(discord_id, thread)
                                    return
                                elif emoji == '🎯': # Access training grounds
                                    await handle_training_grounds(discord_id, thread)
                                    return
                                elif emoji == '🛒':  # Access Town Center
                                    await handle_shop(discord_id, thread)
                                    return
                                else:
                                    logging.error(f"Issue with handling emote for movement and storage, tile_id: {tile_id}")
                                    return

                            else:
                                logging.warning(f"Unable to find tile_info for tile_id {tile_id} for player {discord_id}")
                                await thread.send("Player location not found, please try again")
                                return

                        else:
                            logging.warning(f"Unable to find tile_id for player {discord_id}")
                            await thread.send("Player tile ID not found, please try again")
                            return

                
            except Exception as e:
                logging.error(f"An error occurred during database operations: {str(e)}")
                await thread.send("An error occurred during database operations. Please try again later.")
        # If no return comes before then we need to return false   
        return False
    except Exception as e:
        logging.error(f"An error occurred during on_raw_reaction_add: {str(e)}")
        # Handle error accordingly

async def get_current_tile_id(discord_id):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
            await cursor.execute("SELECT tile_id FROM player_location WHERE discord_id = %s", (discord_id,))
            tile_id_tuple = await cursor.fetchone()
            return tile_id_tuple[0] if tile_id_tuple else None

async def register_new_player(discord_id, crw_address, payment_address):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await conn.begin()
                # Insert the player's CRW address, payment address, and rank into the database
                await cursor.execute(
                    "INSERT INTO players (discord_id, crw_address, player_rank, payment_address) VALUES (%s, %s, 'Squire', %s)",
                    (discord_id, crw_address, payment_address)
                )
                logging.info(f"New player added to the players table with discord_id: {discord_id}")

                # Insert the player's attributes into the player_attributes table
                await cursor.execute("INSERT INTO player_attributes (discord_id) VALUES (%s)", (discord_id,))
                logging.info(f"Attributes for player with id: {discord_id} added to player_attributes table")

                # Insert the player's inventory entry with NULL values
                await cursor.execute("INSERT INTO player_inventory (discord_id) VALUES (%s)", (discord_id,))
                logging.info(f"Inventory entry created for player with id: {discord_id}")
                
                await cursor.execute("UPDATE player_inventory SET equipped_chest_id = %s, equipped_chest_class = %s WHERE discord_id = %s", (STARTING_ARMOUR_ID, STARTING_ARMOUR_CLASS, discord_id,))

                # Insert the player's residential storage entry with NULL values
                await cursor.execute("INSERT INTO residential_storage (discord_id) VALUES (%s)", (discord_id,))
                logging.info(f"Residential storage entry created for player with id: {discord_id}")

                # Insert the player's location into the player_location table
                tile_id = 1
                await cursor.execute("INSERT INTO player_location (discord_id, tile_id) VALUES (%s, %s)",
                                     (discord_id, tile_id))
                await conn.commit()

            if await calculate_base_health_and_mana(discord_id):
                async with conn.cursor() as cursor:
                    # Retrieve the health and mana from player_attributes table
                    await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                    await cursor.execute("SELECT health, mana FROM player_attributes WHERE discord_id = %s", (discord_id,))
                    attributes = await cursor.fetchone()

                    if attributes:
                        current_health = attributes[0]
                        current_mana = attributes[1]
                        await conn.begin()
                        # Update the current_health and current_mana columns in the players table
                        await cursor.execute("UPDATE players SET current_health = %s, current_mana = %s WHERE discord_id = %s",
                                             (current_health, current_mana, discord_id))
                        # Commit the changes
                        await conn.commit()

                return True

    except Exception as e:
        logging.error(f"An error occurred while registering the player: {e}")
        await conn.rollback()

    return False

async def display_search_results(discord_id, thread, search_results):
    if not search_results:
        await thread.send(f"<@{discord_id}>, No results found for your search.")
        return

    embed_message = discord.Embed(title="Search Results", color=discord.Color.blue())

    for result in search_results:
        table_name = result['table_name']
        name = result['name']
        item_class = result['class']
        Item_description = result['description']
        stats = f"Strength: {result['strength']}\nAgility: {result['agility']}\nIntelligence: {result['intelligence']}\nStamina: {result['stamina']}"
        rarity = result['rarity']
        
        embed_message.add_field(name="Name", value=name, inline=True)
        embed_message.add_field(name="Class", value=item_class, inline=True)
        embed_message.add_field(name="Rarity", value=rarity, inline=True)
        embed_message.add_field(name="Description", value=Item_description, inline=False)
        embed_message.add_field(name="Stats", value=stats, inline=False)

    await thread.send(embed=embed_message)

# Function to get the player's current location
async def get_player_location(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:

                try:
                    # Fetch the tile_id from the player_location table
                    await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                    await cursor.execute("SELECT tile_id FROM player_location WHERE discord_id = %s", (discord_id,))
                    result = await cursor.fetchone()
                    if result:
                        tile_id = result[0]

                        # Fetch the location details from the map_tiles table
                        await cursor.execute("SELECT area_name FROM map_tiles WHERE id = %s", (tile_id,))
                        location_result = await cursor.fetchone()
                        if location_result:
                            current_location = location_result[0]

                            return current_location
                        else:
                            logging.warning(f"Location details not found for tile_id: {tile_id}.")

                    else:
                        logging.warning(f"Player location not found for discord_id: {discord_id}.")

                except Exception as e:
                    raise e

    except Exception as e:
        logging.error(f"An error occurred while getting player location: {str(e)}")

    return None

# Function to get the player's current location
async def get_player_location_tile_name(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:

                try:
                    # Fetch the tile_id from the player_location table
                    await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                    await cursor.execute("SELECT tile_id FROM player_location WHERE discord_id = %s", (discord_id,))
                    result = await cursor.fetchone()
                    if result:
                        tile_id = result[0]

                        # Fetch the location details from the map_tiles table
                        await cursor.execute("SELECT tile_name FROM map_tiles WHERE id = %s", (tile_id,))
                        location_result = await cursor.fetchone()
                        if location_result:
                            current_location = location_result[0]

                            return current_location
                        else:
                            logging.warning(f"Location details not found for tile_id: {tile_id}.")

                    else:
                        logging.warning(f"Player location not found for discord_id: {discord_id}.")

                except Exception as e:
                    raise e

    except Exception as e:
        logging.error(f"An error occurred while getting player location: {str(e)}")

    return None

async def handle_residential_area_storage(discord_id, thread):
    try:
        # Check the player's current location tile name
        current_location = await get_player_location_tile_name(discord_id)
        if current_location and "Residential Area" in current_location:
            # Check if the player already has an open deposit item menu
            if discord_id in open_area_storage:
                return

            # Mark the player as having an open deposit item menu
            open_area_storage.add(discord_id)

            # Create an embed message for the storage menu
            embed = discord.Embed(
                title="Residential Area Storage",
                description="Choose an option:",
                color=discord.Color.green()
            )

            embed.add_field(name="1. Deposit Item", value=":inbox_tray: Deposit an item to the storage.", inline=False)
            embed.add_field(name="2. Take Item", value=":outbox_tray: Take an item from the storage.", inline=False)
            embed.add_field(name="3. Armour Menu", value="🛡️ Equip or unequip armour.", inline=False)
            embed.add_field(name="4. View Stored Items", value=":mag: View the items stored in the storage.", inline=False)
            embed.add_field(name="5. Exit", value=":x: Exit the storage menu.", inline=False)

            # Send the storage menu embed message to the thread
            message = await thread.send(embed=embed)

            # Add reaction emojis to the message for menu navigation
            await message.add_reaction('📥')  # Deposit Item
            await message.add_reaction('📤')  # Take Item
            await message.add_reaction('🛡️')  # Armour Menu
            await message.add_reaction('🔍')  # View Stored Items
            await message.add_reaction('❌')  # Exit

            # Wait for the player's reaction
            def reaction_check(reaction, user):
                return (
                    user.id == discord_id
                    and str(reaction.emoji) in ['📥', '📤', '🛡️', '🔍', '❌']
                    and reaction.message.id == message.id
                    and current_location and "Residential Area" in current_location
                    and str(reaction.emoji) not in ['\u2190', '\u2192']  # Unicode representation of '⬅️' and '➡️'
                )

            while True:
                try:
                    reaction, _ = await bot.wait_for('reaction_add', timeout=60.0, check=reaction_check)

                    if str(reaction.emoji) == '📥':
                        # Player selected to deposit an item
                        await handle_deposit_items(discord_id, thread)
                        
                    elif str(reaction.emoji) == '📤':
                        # Player selected to take an item
                        await handle_take_item(discord_id, thread)

                    elif str(reaction.emoji) == '🛡️':
                        # Player selected the armour menu
                        armour_embed = discord.Embed(
                            title="Armour Menu",
                            description="Choose an option:",
                            color=discord.Color.green()
                        )
                        armour_embed.add_field(name="1. Unequip Armour", value="📥 Unequip armour from your inventory.", inline=False)
                        armour_embed.add_field(name="2. Equip Armour", value="📤 Equip armour from storage.", inline=False)
                        armour_embed.add_field(name="3. Exit", value=":x: Exit the equip menu.", inline=False)

                        armour_message = await thread.send(embed=armour_embed)
                        await armour_message.add_reaction('📥')  # Unequip Armour
                        await armour_message.add_reaction('📤')  # Equip Armour
                        await armour_message.add_reaction('❌')  # Exit
                        

                        def armour_reaction_check(reaction, user):
                            return (
                                user.id == discord_id
                                and str(reaction.emoji) in ['📥', '📤', '❌']
                                and reaction.message.id == armour_message.id
                                and current_location and "Residential Area" in current_location
                            )

                        while True:
                            try:
                                armour_reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=armour_reaction_check)

                                if str(armour_reaction.emoji) == '📥':
                                    # Player selected to equip armour
                                    await handle_deposit_equipped(discord_id, thread)

                                elif str(armour_reaction.emoji) == '📤':
                                    # Player selected to unequip armour
                                    await handle_equip_armour(discord_id, thread)

                                elif str(armour_reaction.emoji) == '❌':
                                    # Exit armour menu
                                    # Delete the message after breaking the loop
                                    await armour_message.delete()
                                    # Remove the specific reaction from the main menu
                                    await message.remove_reaction('🛡️', user)
                                    break

                            except asyncio.TimeoutError:
                                await thread.send("Armour menu timed out.")
                                break
        
                    elif str(reaction.emoji) == '🔍':
                        # Player selected to view stored items
                        await handle_view_stored_items(discord_id, thread)
                        
                    elif str(reaction.emoji) == '❌':
                        await reaction.message.delete()
                        break

                    # Remove the player's reaction
                    await message.remove_reaction(reaction, discord.Object(discord_id))

                except asyncio.TimeoutError:
                    await thread.send("Residential menu timed out.")
                    break

            # Remove the player from the open deposit menus set
            open_area_storage.remove(discord_id)
            await start_game(discord_id, thread)
            return True
        else:
            await thread.send("You are not currently in the Residential Area.")
            return False

        # Player Cooldown
        player_cooldowns[discord_id] = {'last_time': time.time()}
        # Start the timer to check for inactivity and delete the thread
        await manage_thread_activity(discord_id, thread, active_threads)

    except Exception as e:
        open_area_storage.remove(discord_id)
        logging.error(f"An error occurred while handling the Residential Area storage: {str(e)}")
        await thread.send("An error occurred while accessing the storage. Please try again later.")

async def handle_town_center(discord_id, thread):
    try:
        current_location = await get_player_location_tile_name(discord_id)
        if current_location and "Town Center" in current_location:
            if discord_id in open_town_center:
                return
            open_town_center.add(discord_id)

            player_bank_gold = await get_player_bank_gold(discord_id)
            player_gold = await get_player_gold(discord_id)
            embed = discord.Embed(
                title=f"Town Center Bank\nBank Balance: {player_bank_gold}\nInventory Balance: {player_gold}",
                description="Choose an option:",
                color=discord.Color.green()
            )
            embed.add_field(name="1. Deposit Gold", value=":moneybag: Deposit gold to the bank.", inline=False)
            embed.add_field(name="2. Withdraw Gold", value=":money_with_wings: Take gold from the bank.", inline=False)
            embed.add_field(name="3. Exit", value=":x: Exit the bank menu.", inline=False)

            message = await thread.send(embed=embed)
            await message.add_reaction('💰')  # Deposit Gold
            await message.add_reaction('💸')  # Withdraw Gold
            await message.add_reaction('❌')  # Exit

            def reaction_check(reaction, user):
                return (
                    user.id == discord_id
                    and str(reaction.emoji) in ['💰', '💸', '❌']
                    and current_location and "Town Center" in current_location
                    and str(reaction.emoji) not in ['\u2190', '\u2192']  # Unicode representation of '⬅️' and '➡️'
                )

            while True:
                try:
                    reaction, _ = await bot.wait_for('reaction_add', timeout=60.0, check=reaction_check)

                    if str(reaction.emoji) == '💰':
                        # Player selected to deposit gold
                        player_gold = await get_player_gold(discord_id)
                        if player_gold > 0:
                            await handle_deposit_gold(discord_id, thread)
                        else:
                            await thread.send("You don't have any gold to deposit.")
                            continue

                    elif str(reaction.emoji) == '💸':
                        # Player selected to take gold
                        player_bank_gold = await get_player_bank_gold(discord_id)
                        if player_bank_gold is not None and player_bank_gold > 0:
                            await handle_take_gold(discord_id, thread)
                        else:
                            await thread.send("You don't have any gold in the bank to withdraw.")
                            continue
                        
                    elif str(reaction.emoji) == '❌':
                        await reaction.message.delete()
                        break

                    # Remove the player's reaction
                    await message.remove_reaction(reaction, discord.Object(discord_id))

                except asyncio.TimeoutError:
                    await thread.send("Town Center Bank menu timed out.")
                    break
            
            open_town_center.remove(discord_id)
            await start_game(discord_id, thread)
            return True
        else:
            await thread.send("You are not currently in the Town Center.")
            return False

        player_cooldowns[discord_id] = {'last_time': time.time()}
        await manage_thread_activity(discord_id, thread, active_threads)

    except Exception as e:
        open_town_center.remove(discord_id)
        logging.error(f"An error occurred while handling the Town Center Bank: {str(e)}")
        await thread.send("An error occurred while accessing the bank. Please try again later.")

async def handle_training_grounds(discord_id, thread, message=None):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
            
            # Get the player's level and current gold
            await cursor.execute(
                "SELECT level, xp FROM player_attributes WHERE discord_id = %s", (discord_id,)
            )
            player_level_result = await cursor.fetchone()
            if player_level_result is None:
                await thread.send("Player level not found.")
                return
            player_level = player_level_result['level']

            await cursor.execute(
                "SELECT current_gold FROM players WHERE discord_id = %s", (discord_id,)
            )
            player_gold_result = await cursor.fetchone()
            if player_gold_result is None:
                await thread.send("Player gold not found.")
                return
            player_gold = player_gold_result['current_gold']

            # Determine cost multiplier and XP multiplier based on player level
            if player_level < 4:
                cost_multiplier = 10
                xp_multiplier = 5
            elif player_level < 7:
                cost_multiplier = 8
                xp_multiplier = 6
            elif player_level < 10:
                cost_multiplier = 6
                xp_multiplier = 7
            elif player_level < 14:
                cost_multiplier = 5
                xp_multiplier = 8
            else:
                cost_multiplier = 3
                xp_multiplier = 9

            # Calculate XP gain
            xp_gain = round(xp_multiplier * math.log(player_level + 1), 2)

            # Calculate cost
            cost = cost_multiplier * player_level

            # Create an embed to show the training info only if we don't have a message already
            if message is None:
                embed = discord.Embed(
                    title="Training Grounds",
                    description=f"It will cost you {cost} gold to train here. If you train, you will gain {xp_gain} XP.",
                    color=discord.Color.green()
                )

                # Send the embed message to the thread
                message = await thread.send(embed=embed)

                # Add the target and exit reactions to the message
                await message.add_reaction('🎯')
                await message.add_reaction('❌')

            def check(reaction, user):
                return user.id == discord_id and reaction.message.id == message.id and str(reaction.emoji) in ['🎯', '❌']

            while True:
                try:
                    reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
                    
                    if str(reaction.emoji) == '🎯':
                        # Proceed with training
                        if player_gold < cost:
                            await thread.send("You don't have enough gold to train.")
                            await message.delete()
                            break

                        # Remove the reaction the player clicked on
                        await message.remove_reaction('🎯', user)  # Removing '🎯' reaction for the user
                        
                        await conn.begin()

                        # Update player's XP and gold
                        await cursor.execute(
                            "UPDATE player_attributes SET xp = xp + %s WHERE discord_id = %s",
                            (xp_gain, discord_id)
                        )
                        await cursor.execute(
                            "UPDATE players SET current_gold = current_gold - %s WHERE discord_id = %s",
                            (cost, discord_id)
                        )

                        await conn.commit()

                        await thread.send(f"You have gained {xp_gain} XP for {cost} gold.")

                        try:
                            # Check the player's level after the mob kill
                            result = await check_player_level(discord_id)
                            if result is True:
                                await thread.send(f"<@{discord_id}>, Congratulations, you leveled up!")
                            elif result is None:
                                continue
                            else:
                                await thread.send(f"<@{discord_id}>, {result}")

                        except Exception as e:
                            logging.error("Error occurred while checking player level: %s", e)
                            return False

                    elif str(reaction.emoji) == '❌':
                        await message.remove_reaction('❌', user)  # Removing '❌' reaction for the user
                        # Exit the training
                        await message.delete()
                        break

                except asyncio.TimeoutError:
                    await message.delete()  # Clean up the message if no reaction is added within the timeout period
                    return

        player_cooldowns[discord_id] = {'last_time': time.time()}
        await manage_thread_activity(discord_id, thread, active_threads)

async def handle_shop(discord_id, thread):
    open_shops.add(discord_id)

    items_for_sale = [
        {"name": "Health Potion", "item_id": 1, "class": "Consumable", "price": 50, "emoji": "1️⃣"},
        {"name": "Mana Potion", "item_id": 2, "class": "Consumable", "price": 50, "emoji": "2️⃣"},
        {"name": "Teleportation Scroll", "item_id": 3, "class": "Consumable", "price": 150, "emoji": "3️⃣"},
        {"name": "Sell Items", "item_id": 4, "class": "Control", "emoji": "💰"},
        {"name": "Exit Shop", "item_id": 5, "class": "Control", "emoji": "❌"}
    ]

    player_cooldowns[discord_id] = {'last_time': time.time()}
    await manage_thread_activity(discord_id, thread, active_threads)

    # Create the embed message outside of the purchase cycle loop
    embed = discord.Embed(
        title="Shop",
        description="Welcome to the Shop!",
        color=discord.Color.green()
    )

    try:
        for item in items_for_sale:
            if item['name'] not in ('Exit Shop', 'Sell Items'):
                embed.add_field(name=f"{item['emoji']} {item['name']}", value=f"Price: {item['price']} Gold", inline=False)
            else:
                embed.add_field(name=f"{item['emoji']} {item['name']}", value="", inline=False)
    except Exception as e:
        logging.error(f"An error occurred while processing items for sale: {str(e)}")

    # Send the embed message to the thread
    message = await thread.send(embed=embed)

    # Add the corresponding emoji to each item as a reaction
    for item in items_for_sale:
        await message.add_reaction(item['emoji'])

    while discord_id in open_shops:  # Loop until the user is no longer in the shop
        try:
            # Process user reactions here
            def check(reaction, user):
                return user.id == discord_id and str(reaction.emoji) in [item['emoji'] for item in items_for_sale]

            reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
            item_to_purchase = next((item for item in items_for_sale if item['emoji'] == str(reaction.emoji)), None)

            if item_to_purchase is None:
                logging.error(f"Could not find item with reaction emoji {reaction.emoji} for user with ID {discord_id}")
                continue

            if item_to_purchase['name'] == 'Exit Shop':
                await message.delete()
                break
            elif item_to_purchase['name'] == 'Sell Items':
                open_shops.remove(discord_id)
                # Open selling menu here
                await open_selling_menu(discord_id, thread, message)
                open_shops.add(discord_id)
                continue

            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                    # Fetch the player's current gold
                    await cursor.execute("SELECT current_gold FROM players WHERE discord_id = %s", (discord_id,))

                    try:
                        result = await cursor.fetchone()
                        current_gold = result['current_gold']
                    except Exception as e:
                        logging.error(f"An error occurred during fetch operation for user {discord_id}: {str(e)}")
                        current_gold = 0  # fallback value

                    # Check if the player has enough gold
                    if current_gold < item_to_purchase['price']:
                        await thread.send(f"You do not have enough gold to purchase the {item_to_purchase['name']}. You need {item_to_purchase['price']} Gold but you only have {current_gold} Gold.")
                        await message.remove_reaction(reaction.emoji, user)
                    else:
                        # Fetch the player's inventory
                        await cursor.execute("SELECT * FROM player_inventory WHERE discord_id = %s", (discord_id,))
                        inventory = await cursor.fetchone()

                        # Check if there's an available slot
                        for slot in range(1, 9):  # Slots 1 to 8
                            if inventory[f'item_slot{slot}_id'] is None:
                                # Available slot found, proceed with purchase
                                await conn.begin()
                                await cursor.execute(
                                    f"UPDATE player_inventory SET item_slot{slot}_id = %s, item_slot{slot}_class = %s WHERE discord_id = %s",
                                    (item_to_purchase['item_id'], item_to_purchase['class'], discord_id,)
                                )
                                await cursor.execute(
                                    "UPDATE players SET current_gold = current_gold - %s WHERE discord_id = %s",
                                    (item_to_purchase['price'], discord_id,)
                                )
                                await conn.commit()
                                await thread.send(f"You have successfully purchased the {item_to_purchase['name']} for {item_to_purchase['price']} Gold.")
                                logging.info(f"User with ID {discord_id} purchased {item_to_purchase['name']} for {item_to_purchase['price']} Gold")
                                break
                        else:
                            # If no available slot was found
                            await thread.send("You do not have any free item slots in your inventory.")
                            logging.info(f"User with ID {discord_id} attempted to buy {item_to_purchase['name']}, but no free item slots were available.")
                            await message.remove_reaction(reaction.emoji, user)

        except asyncio.TimeoutError:
            logging.info(f"User with ID {discord_id} didn't respond in time")
            await message.delete()
            break
        except Exception as e:
            logging.error(f"An error occurred while processing shop for user with ID {discord_id}: {str(e)}")
            break
    # Always remove the user from the open_shops set when we're done
    open_shops.remove(discord_id)

async def handle_deposit_items(discord_id, thread):
    # Declare message_data as an empty dictionary
    message_data = {}

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:

                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute(
                    "SELECT item_slot1_id, item_slot2_id, item_slot3_id, item_slot4_id, item_slot5_id, item_slot6_id, item_slot7_id, item_slot8_id, item_slot1_class, item_slot2_class, item_slot3_class, item_slot4_class, item_slot5_class, item_slot6_class, item_slot7_class, item_slot8_class FROM player_inventory WHERE discord_id = %s",
                    (discord_id,),
                )
                inventory = await cursor.fetchone()

                item_slots = [str(item) for item in inventory[:8]]
                item_slot_classes = [str(item) for item in inventory[8:]]

                # Create list of items along with their respective slots
                item_slot_pairs = [(item, slot) for item, slot in zip(item_slots, range(1, len(item_slots) + 1)) if item is not None and item != 'None']
                item_slot_pairs_classes = [(item_class, slot) for item_class, slot in zip(item_slot_classes, range(1, len(item_slot_classes) + 1)) if item_class is not None and item_class != 'None']

                if any(item for item in item_slots if item != 'None'):
                    # Create an embed for inventory slots
                    inventory_slots_embed = discord.Embed(
                        title="Inventory Slots",
                        description="Please select an item from your inventory to deposit:",
                        color=discord.Color.blue(),
                    )

                    # Generate the list of item names for the embed message
                    item_names = []
                    item_class_names = []
                    for (item, slot), (item_class, item_class_slot) in zip(item_slot_pairs, item_slot_pairs_classes):
                        try:
                            item_name = await fetch_item(item_class, item)
                            if item_name:
                                item_names.append(item_name)
                                item_class_names.append(item_class)
                        except discord.HTTPException:
                            await thread.send(f"Failed to fetch item: {item}. Please try again later.")
                        except Exception as e:
                            logging.error(f"An error occurred while fetching item: {str(e)}")

                    inventory_slots_text = "".join(f"{i}\u20e3 {item}\n" for i, item in enumerate(item_names, start=1))
                    inventory_slots_embed.add_field(name="Inventory Slots", value=inventory_slots_text, inline=False)

                    # Send the inventory slots embed to the thread
                    inventory_slots_message = await thread.send(embed=inventory_slots_embed)

                    # Add reactions for inventory slots
                    for i in range(1, len(item_names) + 1):
                        number_emoji = f"{i}\u20e3"  # Construct the number emoji
                        await inventory_slots_message.add_reaction(number_emoji)
                    # Add exit emoji
                    await inventory_slots_message.add_reaction('❌')

                    # Create the item_ids list from item_slot_pairs
                    item_ids = [item for item, slot in item_slot_pairs]

                    # Store the slot number along with each item
                    message_data[inventory_slots_message.id] = {
                        "type": "deposit",
                        "discord_id": discord_id,
                        "item_names": item_names,
                        "item_ids": item_ids,
                        "item_slots": [slot for item, slot in item_slot_pairs],
                        "item_slot_classes": [slot for item_class, slot in item_slot_pairs_classes],
                    }
                else:
                    await thread.send("You don't have any items to deposit.")
                    await handle_residential_area_storage(discord_id, thread)
                    return

                # Inside your while loop
                while True:
                    # Wait for the player's reaction
                    def reaction_check(reaction, user):
                        return user.id == discord_id and reaction.message.id in message_data

                    reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=reaction_check)
                    emoji = str(reaction.emoji)

                    valid_emojis = {'1⃣', '2⃣', '3⃣', '4⃣', '5⃣', '6⃣', '7⃣', '8⃣'}

                    if emoji in valid_emojis:
                        message_id = reaction.message.id
                        message_info = message_data[message_id]
                        item_names = message_info["item_names"]
                        item_slots = message_info["item_slots"]
                        item_slot_classes = message_info["item_slot_classes"]

                        # Use the slot number to identify the item in the player's inventory
                        index = int(emoji[0]) - 1
                        if index < len(item_names):
                            item_name = item_names[index]
                            item_slot = message_info["item_slots"][index]
                            item_class = item_class_names[index]  # Get the item class name
                            item_class_slot = message_info["item_slot_classes"][index]

                            # Get the item ID
                            item_id = message_info["item_ids"][index]  # add this line

                            # Check if this item from this slot is already being deposited
                            if (item_id, item_slot) in deposit_items:
                                await thread.send(f"You are already depositing {item_name}.")
                                continue

                            # If it's not being deposited, add it to the set
                            deposit_items.add((item_id, item_slot))

                            # Get the corresponding column names for the item ID and class
                            item_id_column = f"item_slot{item_slot}_id"
                            item_class_column = f"item_slot{item_slot}_class"

                            # Pass the slot numbers to the add_item_to_storage function
                            try:
                                if await add_item_to_storage(discord_id, item_id, item_class, item_id_column, item_class_column) is True:
                                    await thread.send(f"You have successfully deposited {item_name} to the storage.")
                                    deposit_items.remove((item_id, item_slot))
                                else:
                                    await thread.send("Your storage is full.")
                            except Exception as e:
                                logging.error(f"An error occurred while depositing the item: {str(e)}")
                                await thread.send("An error occurred while processing the deposit item request. Please try again later.")

                        else:
                            await thread.send("Invalid item selection.")

                    elif emoji == '❌':
                        await reaction.message.delete()
                        break

                    else:
                        await thread.send("Invalid reaction. Please select a number or the '❌' emoji.")

                return

    except Exception as e:
        deposit_items.remove((item_id, item_slot))
        logging.error(f"An error occurred while handling the deposit item: {str(e)}")
        await thread.send("An error occurred while processing the deposit item request. Please try again later.")

async def handle_deposit_equipped(discord_id, thread):
    try:
        message_data = {}
        processing = True

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:

                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute(
                    "SELECT * FROM player_inventory WHERE discord_id = %s",
                    (discord_id,),
                )
                inventory = await cursor.fetchone()

                equipped_slots = ['equipped_weapon_id', 'equipped_helmet_id', 'equipped_chest_id', 'equipped_legs_id', 'equipped_feet_id', 'equipped_amulet_id', 'equipped_ring1_id', 'equipped_ring2_id', 'equipped_charm_id']
                equipped_slot_classes = ['equipped_weapon_class', 'equipped_helmet_class', 'equipped_chest_class', 'equipped_legs_class', 'equipped_feet_class', 'equipped_amulet_class', 'equipped_ring1_class', 'equipped_ring2_class', 'equipped_charm_class']

                # Retrieve only equipped items and classes from the inventory
                equipped_items = [inventory[i] for i in range(2, 19, 2)]
                equipped_classes = [inventory[i] for i in range(3, 20, 2)]

                equipped_pairs = [(item, slot, item_class) for item, slot, item_class in zip(equipped_items, equipped_slots, equipped_classes) if item is not None]

                if not equipped_pairs:
                    await thread.send("You do not have anything equipped in your inventory to deposit.")
                    return
                    
                equipped_embed = discord.Embed(
                    title="Equipped Items",
                    description="Please select an equipped item to deposit:",
                    color=discord.Color.blue(),
                )

                equipped_item_names = []
                equipped_item_classes = []
                for item_tuple in equipped_pairs:
                    item_equipped, column_name, item_class = item_tuple
                    if item_equipped is None:
                        continue
                    try:
                        table_name = await get_table_name(column_name)
                        item_name = await fetch_item(table_name, item_equipped)
                        if item_name:
                            equipped_item_names.append(item_name)
                            equipped_item_classes.append(table_name)
                    except discord.HTTPException:
                        logging.error(f"Failed to fetch equipped item: {item_equipped} for user {discord_id}.")
                        await thread.send(f"Failed to fetch equipped item: {item_equipped}. Please try again later.")
                        processing = False
                    except Exception as e:
                        logging.error(f"An error occurred while fetching equipped item for user {discord_id}: {str(e)}")
                        processing = False

                if processing:
                    equipped_text = "".join(f"{i}\u20e3 {item}\n" for i, item in enumerate(equipped_item_names, start=1))
                    equipped_embed.add_field(name="Equipped Items", value=equipped_text, inline=False)
                    equipped_message = await thread.send(embed=equipped_embed)

                    for i in range(1, len(equipped_item_names) + 1):
                        number_emoji = f"{i}\u20e3"
                        await equipped_message.add_reaction(number_emoji)
                    await equipped_message.add_reaction('❌')

                    message_data[equipped_message.id] = {
                        "type": "deposit",
                        "discord_id": discord_id,
                        "item_names": equipped_item_names,
                        "item_slots": [pair[1] for pair in equipped_pairs],
                        "item_ids": [int(pair[0]) for pair in equipped_pairs if pair[0] is not None],
                        "item_classes": equipped_item_classes,
                        "item_slot_classes": [pair[2] for pair in equipped_pairs],
                    }
                    while processing:
                        try:
                            def reaction_check(reaction, user):
                                return user.id == discord_id and reaction.message.id in message_data
                            reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=reaction_check)
                            if str(reaction) == '❌':
                                await equipped_message.clear_reactions()
                                await equipped_message.delete()
                                break

                            reaction_number = int(str(reaction)[0])

                            item_to_deposit = message_data[equipped_message.id]["item_ids"][reaction_number - 1]
                            item_slot_to_deposit = message_data[equipped_message.id]["item_slots"][reaction_number - 1]
                            item_slot_class_to_deposit = message_data[equipped_message.id]["item_slot_classes"][reaction_number - 1]

                            depositing_items.add((item_to_deposit, item_slot_to_deposit, item_slot_class_to_deposit))

                            if depositing_items:
                                for item_tuple in depositing_items:
                                    item_id, item_id_column, item_class_column = item_tuple
                                    try:
                                        item_name = await fetch_item(item_class_column, item_id)
                                        logging.info(f"Item name fetched: {item_name} using item_class_column: {item_class_column} and item_id: {item_id}")
                                        item_class = item_class_column
                                        logging.info(f"Attempting to add item: {item_id} with class: {item_class} or column class {item_class_column} to storage for user {discord_id}")
                                        result = await add_item_to_storage(discord_id, item_id, item_class, item_id_column, item_class_column)

                                        if result is True:
                                            if await calculate_base_health_and_mana(discord_id) is True:
                                                if await recalculate_player_inventory_attributes(discord_id) is True:
                                                    if await update_current_health_and_mana_equip(discord_id) is True:
                                                        logging.info(f"Unequip - updated current health and mana")
                                                    else:
                                                        logging.error("Error updating health and mana for player {discord_id} in unequip")
                                                else:
                                                    logging.error("Error recalculating base health and mana for player {discord_id} in unequip")
                                            else:
                                                logging.error("Error calculating base health and mana for player {discord_id} in unequip")

                                            logging.info(f"Successfully deposited {item_name} into the storage for user {discord_id}.")
                                            await thread.send(f"You have successfully deposited {item_name} into the storage.")
                                        else:
                                            logging.warning(f"Residential storage is full for user {discord_id}. Attempted to deposit item: {item_id}")
                                            await thread.send("Your residential storage is full.")
                                    except Exception as e:
                                        logging.error(f"An error occurred while depositing the item for user {discord_id}. Error: {type(e).__name__}, Args: {e.args}")
                                        await thread.send("An error occurred while processing the deposit item request. Please try again later.")

                            depositing_items.remove((item_to_deposit, item_slot_to_deposit, item_slot_class_to_deposit))
                        except asyncio.TimeoutError:
                            depositing_items.remove((item_to_deposit, item_slot_to_deposit, item_slot_class_to_deposit))
                            await equipped_message.clear_reactions()
                            await equipped_message.delete()
                            logging.warning(f"User {discord_id} took too long to react. The operation has been cancelled.")
                            await thread.send("You took too long to react. The operation has been cancelled.")
                            return

        player_cooldowns[discord_id] = {'last_time': time.time()}
        await manage_thread_activity(discord_id, thread, active_threads)
    except asyncio.TimeoutError:
        depositing_items.remove((item_to_deposit, item_slot_to_deposit, item_slot_class_to_deposit))
        await equipped_message.clear_reactions()
        await equipped_message.delete()
        logging.warning(f"User {discord_id} took too long to react. The operation has been cancelled.")
        return
    except Exception as e:
        depositing_items.remove((item_to_deposit, item_slot_to_deposit, item_slot_class_to_deposit))
        logging.error(f"Error in handle_deposit_equipped for user {discord_id}: {str(e)}")
        await thread.send("An error occurred while processing your request. Please try again later.")

async def handle_equip_armour(discord_id, thread):
    try:
        message_data = {}
        processing = True

        item_class_to_equip_slot = {
            "weapon": "equipped_weapon_id",
            "Amulet": "equipped_amulet_id",
            "Ring": ["equipped_ring1_id", "equipped_ring2_id"],
            "Charm": "equipped_charm_id",
            "armour": None,
        }

        armour_type_to_equip_slot = {
            "Helmet": "equipped_helmet_id",
            "Chest Armor": "equipped_chest_id",
            "Leg Armor": "equipped_legs_id",
            "Footwear": "equipped_feet_id",
            "Foot Armor": "equipped_feet_id",
        }

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:

                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute(
                    "SELECT * FROM residential_storage WHERE discord_id = %s",
                    (discord_id,),
                )
                storage = await cursor.fetchone()

                if not storage:
                    await thread.send("You do not have anything in your storage to equip.")
                    return

                storage_embed = discord.Embed(
                    title="Storage Items",
                    description="Please select an item to equip:",
                    color=discord.Color.blue(),
                )

                storage_items = [(storage[i], storage[i+1]) for i in range(2, len(storage)-1, 2) if i+1 < len(storage)]
                storage_item_ids = []
                storage_item_classes = []
                storage_item_types = []
                storage_item_names = []
                for item_id, item_class in storage_items:
                    if item_id is None or item_class == "Consumable" or item_class == "items":
                        continue
                    try:
                        item_name = await fetch_item(item_class, item_id)
                        item_type = await fetch_item_class(item_class, item_id)

                        if item_name:
                            storage_item_ids.append(item_id)
                            storage_item_names.append(item_name)
                            storage_item_classes.append(item_class)
                            storage_item_types.append(item_type)

                    except discord.HTTPException:
                        logging.error(f"Failed to fetch storage item: {item_id} for user {discord_id}.")
                        await thread.send(f"Failed to fetch storage item: {item_id}. Please try again later.")
                        processing = False
                    except Exception as e:
                        logging.error(f"An error occurred while fetching storage item for user {discord_id}: {str(e)}")
                        processing = False

                if processing:
                    storage_text = "".join(f"{i}\u20e3 {item}\n" for i, item in enumerate(storage_item_names, start=1))
                    storage_embed.add_field(name="Storage Items", value=storage_text, inline=False)
                    storage_message = await thread.send(embed=storage_embed)

                    for i in range(1, len(storage_item_ids) + 1):
                        number_emoji = f"{i}\u20e3"
                        await storage_message.add_reaction(number_emoji)
                    await storage_message.add_reaction('❌')

                    message_data[storage_message.id] = {
                        "type": "equip",
                        "discord_id": discord_id,
                        "item_ids": storage_item_ids,
                        "item_classes": storage_item_classes,
                        "item_types": storage_item_types,
                    }

                    while processing:
                        try:
                            def reaction_check(reaction, user):
                                return user.id == discord_id and reaction.message.id in message_data
                            reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=reaction_check)

                            if str(reaction) == '❌':
                                await storage_message.clear_reactions()
                                await storage_message.delete()
                                break

                            reaction_number = int(str(reaction)[0])

                            item_to_equip = message_data[storage_message.id]["item_ids"][reaction_number - 1]
                            item_class_to_equip = message_data[storage_message.id]["item_classes"][reaction_number - 1]

                            # Fetch item type
                            item_type = await fetch_item_class(item_class_to_equip, item_to_equip)
                            logging.info(f"DUMP item_type: {item_type}")

                            if item_type is None:
                                logging.error("Failed to fetch item type")
                                await thread.send("Could not fetch item details. Please try again.")
                                return
                            logging.info(f"DUMP item_class_to_equip: {item_class_to_equip} and item_type: {item_type}")
                            # Get the appropriate equipment slot based on the item class or type
                            equip_slot = item_class_to_equip_slot.get(item_class_to_equip)
                            logging.info(f"DUMP equip_slot: {equip_slot}")

                            if isinstance(equip_slot, list):  # if the item is a ring
                                # fetch current rings
                                await cursor.execute(
                                    "SELECT equipped_ring1_id, equipped_ring2_id FROM player_inventory WHERE discord_id = %s",
                                    (discord_id,),
                                )
                                current_rings = await cursor.fetchone()

                                if current_rings[0] is None:  # if ring1 slot is empty
                                    equip_slot = equip_slot[0]
                                elif current_rings[1] is None:  # if ring2 slot is empty
                                    equip_slot = equip_slot[1]
                                else:
                                    await thread.send("Both ring slots are occupied. Please unequip a ring before equipping a new one.")
                                    return
                            elif equip_slot is None:
                                equip_slot = armour_type_to_equip_slot.get(item_type)

                                try:
                                    await cursor.execute(
                                        f"SELECT {equip_slot} FROM player_inventory WHERE discord_id = %s",
                                        (discord_id,),
                                    )

                                    current_equipment = await cursor.fetchone()

                                    if current_equipment[0] is not None:  # We need to check the first element of the tuple returned by fetchone()
                                        await thread.send(f"You already have an item equipped in the {equip_slot} slot. Please unequip it before equipping a new item.")
                                        continue

                                except Exception as e:
                                    logging.error(f"An error occurred while checking if item slot is occupied for user {discord_id}. Error: {type(e).__name__}, Args: {e.args}")
                                    await thread.send("An error occurred while processing the equip item request. Please try again later.")
                            elif item_class_to_equip == 'weapon' or item_class_to_equip == 'weapons':
                                # fetch current weapon
                                await cursor.execute(
                                    f"SELECT {equip_slot} FROM player_inventory WHERE discord_id = %s",
                                    (discord_id,),
                                )
                                current_weapon = await cursor.fetchone()

                                if current_weapon[0] is not None:  # We need to check the first element of the tuple returned by fetchone()
                                    await thread.send("You are already holding a weapon. Please unequip it before equipping a new one.")
                                    continue

                            elif item_class_to_equip in ['Charm', 'Amulet', 'Ring', 'item', 'items']:
                                # fetch current item
                                await cursor.execute(
                                    f"SELECT {equip_slot} FROM player_inventory WHERE discord_id = %s",
                                    (discord_id,),
                                )
                                current_item = await cursor.fetchone()

                                if current_item[0] is not None:  # We need to check the first element of the tuple returned by fetchone()
                                    await thread.send("You already have an item equipped. Please unequip it before equipping a new one.")
                                    continue

                            # If equip_slot is still None, handle this case
                            if equip_slot is None:
                                logging.error(f"Unrecognized equip_slot: {equip_slot} and item type: {item_type}. Cannot determine equip slot.")
                                continue  # Skip this item

                            equipping_items.add((item_to_equip, item_class_to_equip))

                            if equipping_items:
                                for item_tuple in equipping_items:
                                    item_id, item_class = item_tuple
                                    try:
                                        item_name = await fetch_item(item_class, item_id)

                                        # Get the storage record
                                        await cursor.execute("SELECT * FROM residential_storage WHERE discord_id = %s", (discord_id,))
                                        storage_record = await cursor.fetchone()
                                        item_in_storage = False
                                        storage_slot = None

                                        if storage_record is not None:
                                            # Start from index 2 and step 2 positions each time, because id columns are at even indices starting from 2
                                            for i in range(2, len(storage_record), 2):
                                                if storage_record[i] == item_to_equip:
                                                    item_in_storage = True
                                                    # Calculate the slot number
                                                    storage_slot = i // 2  # The // operator ensures that the result is an integer
                                                    break

                                        result = None  # Initialize result here

                                        logging.info(f"Attempting to add item: {item_id}, item class: {item_class}, equip_slot: {equip_slot} and item_slot{storage_slot} to inventory for user {discord_id}")
                                        
                                        result = await add_equip_to_inventory(discord_id, item_id, item_class, equip_slot, f"item_slot{storage_slot}")

                                        if result is True:
                                            if await calculate_base_health_and_mana(discord_id) is True:
                                                if await recalculate_player_inventory_attributes(discord_id) is True:
                                                    if await update_current_health_and_mana_equip(discord_id) is True:
                                                        logging.info(f"Equip - updated current health and mana")
                                                    else:
                                                        logging.error("Error updating health and mana for player {discord_id} in equip")
                                                else:
                                                    logging.error("Error recalculating base health and mana for player {discord_id} in equip")
                                            else:
                                                logging.error("Error calculating base health and mana for player {discord_id} in equip")

                                            logging.info(f"Successfully equipped {item_name} from the storage for user {discord_id}.")
                                            await thread.send(f"You have successfully equipped {item_name} from the storage.")
                                        else:
                                            logging.warning(f"Player inventory is full for user {discord_id}. Attempted to equip item: {item_id}")
                                            await thread.send("Your player inventory is full.")
                                    except Exception as e:
                                        logging.error(f"An error occurred while equipping the item for user {discord_id}. Error: {type(e).__name__}, Args: {e.args}")
                                        await thread.send("An error occurred while processing the equip item request. Please try again later.")


                            equipping_items.remove((item_to_equip, item_class_to_equip))
                        except asyncio.TimeoutError:
                            equipping_items.remove((item_to_equip, item_class_to_equip))
                            await storage_message.clear_reactions()
                            await storage_message.delete()
                            logging.warning(f"User {discord_id} took too long to react. The operation has been cancelled.")
                            await thread.send("You took too long to react. The operation has been cancelled.")
                            return

        player_cooldowns[discord_id] = {'last_time': time.time()}
        await manage_thread_activity(discord_id, thread, active_threads)
    except asyncio.TimeoutError:
        equipping_items.remove((item_to_equip, item_class_to_equip))
        await storage_message.clear_reactions()
        await storage_message.delete()
        logging.warning(f"User {discord_id} took too long to react. The operation has been cancelled.")
        return
    except Exception as e:
        equipping_items.remove((item_to_equip, item_class_to_equip))
        logging.error(f"Error in handle_equip_armour for user {discord_id}: {str(e)}")
        await thread.send("An error occurred while processing your request. Please try again later.")

async def handle_take_item(discord_id, thread):
    # Declare message_data as an empty dictionary
    message_data = {}

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:

                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute(
                    "SELECT item_slot1_id, item_slot2_id, item_slot3_id, item_slot4_id, item_slot5_id, item_slot6_id, item_slot7_id, item_slot8_id, item_slot1_class, item_slot2_class, item_slot3_class, item_slot4_class, item_slot5_class, item_slot6_class, item_slot7_class, item_slot8_class FROM residential_storage WHERE discord_id = %s",
                    (discord_id,),
                )
                storage = await cursor.fetchone()

                item_slots = [str(item) for item in storage[:8]]
                item_slot_classes = [str(item) for item in storage[8:]]

                # Create list of items along with their respective slots
                item_slot_pairs = [(item, slot) for item, slot in zip(item_slots, range(1, len(item_slots) + 1)) if item is not None and item != 'None']
                item_slot_pairs_classes = [(item_class, slot) for item_class, slot in zip(item_slot_classes, range(1, len(item_slot_classes) + 1)) if item_class is not None and item_class != 'None']

                if any(item for item in item_slots if item != 'None'):
                    # Create an embed for storage slots
                    storage_slots_embed = discord.Embed(
                        title="Storage Slots",
                        description="Please select an item from your storage to take:",
                        color=discord.Color.blue(),
                    )

                    # Generate the list of item names for the embed message
                    item_names = []
                    item_class_names = []
                    for (item, slot), (item_class, item_class_slot) in zip(item_slot_pairs, item_slot_pairs_classes):
                        try:
                            item_name = await fetch_item(item_class, item)
                            if item_name:
                                item_names.append(item_name)
                                item_class_names.append(item_class)
                        except discord.HTTPException:
                            await thread.send(f"Failed to fetch item: {item}. Please try again later.")
                        except Exception as e:
                            logging.error(f"An error occurred while fetching item: {str(e)}")

                    storage_slots_text = "".join(f"{i}\u20e3 {item}\n" for i, item in enumerate(item_names, start=1))
                    storage_slots_embed.add_field(name="Storage Slots", value=storage_slots_text, inline=False)

                    # Send the storage slots embed to the thread
                    storage_slots_message = await thread.send(embed=storage_slots_embed)

                    # Add reactions for storage slots
                    for i in range(1, len(item_names) + 1):
                        number_emoji = f"{i}\u20e3"  # Construct the number emoji
                        await storage_slots_message.add_reaction(number_emoji)
                    # Add exit emoji
                    await storage_slots_message.add_reaction('❌')

                    # Create the item_ids list from item_slot_pairs
                    item_ids = [item for item, slot in item_slot_pairs]

                    # Store the slot number along with each item
                    message_data[storage_slots_message.id] = {
                        "type": "take",
                        "discord_id": discord_id,
                        "item_names": item_names,
                        "item_ids": item_ids,
                        "item_slots": [slot for item, slot in item_slot_pairs],
                        "item_slot_classes": [slot for item_class, slot in item_slot_pairs_classes],
                    }
                else:
                    await thread.send("You don't have any items to take.")
                    await handle_residential_area_storage(discord_id, thread)
                    return

                # Inside your while loop
                while True:
                    # Wait for the player's reaction
                    def reaction_check(reaction, user):
                        return user.id == discord_id and reaction.message.id in message_data

                    reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=reaction_check)
                    emoji = str(reaction.emoji)
                    valid_emojis = {'1⃣', '2⃣', '3⃣', '4⃣', '5⃣', '6⃣', '7⃣', '8⃣'}

                    if emoji in valid_emojis:
                        message_id = reaction.message.id
                        message_info = message_data[message_id]
                        item_names = message_info["item_names"]
                        item_slots = message_info["item_slots"]
                        item_slot_classes = message_info["item_slot_classes"]

                        # Use the slot number to identify the item in the player's inventory
                        index = int(emoji[0]) - 1
                        if index < len(item_names):
                            item_name = item_names[index]
                            item_slot = message_info["item_slots"][index]
                            item_class = item_class_names[index]  # Get the item class name
                            item_class_slot = message_info["item_slot_classes"][index]

                            # Get the item ID
                            item_id = message_info["item_ids"][index]

                            # Check if this item from this slot is already being taken
                            if (item_id, item_slot) in taken_items:
                                await thread.send(f"You are already taking {item_name}.")
                                continue

                            # If it's not being taken, add it to the set
                            taken_items.add((item_id, item_slot))

                            # Get the corresponding column names for the item ID and class
                            item_id_column = f"item_slot{item_slot}_id"
                            item_class_column = f"item_slot{item_slot}_class"

                            # Pass the slot numbers to the add_item_to_inventory function
                            try:
                                if await add_item_to_inventory(discord_id, item_id, item_class, item_id_column, item_class_column) is True:
                                    await thread.send(f"You have successfully taken {item_name} from the storage.")
                                else:
                                    await thread.send("Your inventory is full.")
                            except Exception as e:
                                logging.error(f"An error occurred while taking the item: {str(e)}")
                                await thread.send("An error occurred while processing the take item request. Please try again later.")

                        else:
                            await thread.send("Invalid selection. Please try again.")
                    elif emoji == '❌':
                        await reaction.message.delete()
                        break
                    else:
                        await thread.send("Invalid selection. Please try again.")

    except asyncio.TimeoutError:
        taken_items.remove((item_id, item_slot))  # Clear the taken_items set
        return
    except Exception as e:
        taken_items.remove((item_id, item_slot))  # Clear the taken_items set
        logging.error(f"An error occurred while handling the take item request: {str(e)}")
        await thread.send("An error occurred while processing the take item request. Please try again later.")

    # Player Cooldown
    player_cooldowns[discord_id] = {'last_time': time.time()}
    # Start the timer to check for inactivity and delete the thread
    await manage_thread_activity(discord_id, thread, active_threads)

async def open_selling_menu(discord_id, thread, shop_message):
    open_selling_menus.add(discord_id)
    sold_items = set()
    
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
            await cursor.execute("SELECT * FROM player_inventory WHERE discord_id = %s", (discord_id,))
            inventory = await cursor.fetchone()

            # We need to prepare the list of items and their emojis
            items_in_inventory = []

            emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]  # You may need to extend this list if you have more slots

            # Let's fetch items from inventory and add them to the list
            for i in range(1, 9):  # I'm assuming you have 8 slots, change this range if it's different
                slot_id = f'item_slot{i}_id'
                slot_class = f'item_slot{i}_class'
                if inventory[slot_id] is not None:
                    item_id = inventory[slot_id]
                    item_class = inventory[slot_class]

                    item_name = await fetch_item(item_class, item_id)
                    item_price = await fetch_price(item_class, item_id)

                    items_in_inventory.append({"name": item_name, "item_id": item_id, "class": item_class, "price": item_price, "emoji": emojis[i-1], "slot": i})


            # Add an option to exit selling menu
            items_in_inventory.append({"name": "Exit Selling Menu", "item_id": 9, "class": "Control", "emoji": "❌"})

            # Then, similar to handle_shop, you create the embed and add reactions
            embed = discord.Embed(
                title="Sell to Shop",
                description="Select the item you want to sell.",
                color=discord.Color.gold()
            )

            for item in items_in_inventory:
                if item['name'] != 'Exit Selling Menu':
                    embed.add_field(name=f"{item['emoji']} {item['name']}", value=f"Selling price: {item['price']} Gold", inline=False)
                else:
                    embed.add_field(name=f"{item['emoji']} {item['name']}", value="", inline=False)

            # Send the embed message to the thread
            message = await thread.send(embed=embed)

            # Add the corresponding emoji to each item as a reaction
            for item in items_in_inventory:
                await message.add_reaction(item['emoji'])

            # Wait for the user's reaction
            while discord_id in open_selling_menus:
                try:
                    def check(reaction, user):
                        return user.id == discord_id and str(reaction.emoji) in [item['emoji'] for item in items_in_inventory]
                        
                    reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
                    emoji = str(reaction.emoji)
                    item_to_sell = next((item for item in items_in_inventory if item['emoji'] == str(reaction.emoji)), None)

                    if item_to_sell is None or item_to_sell['slot'] in sold_items:
                        if item_to_sell['slot'] in sold_items:
                            await thread.send(f"You've already sold this item.")
                        else:
                            await thread.send(f"An error occurred while selecting the item.")
                        continue

                    if item_to_sell['name'] == 'Exit Selling Menu':
                        open_selling_menus.remove(discord_id)
                        await message.delete()  # Delete the selling menu
                        await thread.send(f"You've exited the selling menu.")
                        break

                    try:
                        await conn.begin()
                        # Update gold
                        await cursor.execute("UPDATE players SET current_gold = current_gold + %s WHERE discord_id = %s", (item_to_sell['price'], discord_id,))

                        # Remove item from inventory
                        await cursor.execute("UPDATE player_inventory SET item_slot%s_id = NULL, item_slot%s_class = NULL WHERE discord_id = %s", (item_to_sell['slot'], item_to_sell['slot'], discord_id,))
                        await conn.commit()

                        # If the sale is successful, add the sold item to the set:
                        sold_items.add(item_to_sell['slot'])

                        await thread.send(f"You've sold {item_to_sell['name']} for {item_to_sell['price']} gold.")
                        logging.info(f"User with ID {discord_id} sold {item_to_sell['name']} for {item_to_sell['price']} gold")
                    except Exception as e:
                        logging.error(f"An error occurred while processing the sale for user with ID {discord_id}: {str(e)}")
                        await conn.rollback()
                    
                    # Player Cooldown
                    player_cooldowns[discord_id] = {'last_time': time.time()}
                    # Start the timer to check for inactivity and delete the thread
                    await manage_thread_activity(discord_id, thread, active_threads)            

                except asyncio.TimeoutError:
                    open_selling_menus.remove(discord_id)
                    await message.delete()  # Delete the selling menu
                    break
                except Exception as e:
                    logging.error(f"An error occurred while processing selling menu for user with ID {discord_id}: {str(e)}")
                    open_selling_menus.remove(discord_id)
                    await message.delete()  # Delete the selling menu
                    break

async def handle_deposit_gold(discord_id, thread):
    try:
        # Fetch current player's gold
        current_gold = await get_player_gold(discord_id)

        while True:
            deposit_msg = await thread.send(f"You are currently carrying {current_gold} gold. How much do you want to deposit? You can type 'exit' to cancel the process.")

            def check(m):
                # Check if the message is from the right user
                return m.author.id == discord_id

            # Wait for a message from the user
            msg = await bot.wait_for('message', check=check)

            if msg.content.lower() in ['exit', 'quit']:
                await thread.send("Exiting gold deposit.")
                return

            try:
                deposit_amount = int(msg.content)
                if deposit_amount > current_gold:
                    await thread.send(f"You do not have enough gold. You only have {current_gold} gold.")
                elif deposit_amount <= 0:
                    await thread.send("The amount must be greater than 0.")
                else:
                    break  # Correctly used 'break' inside a loop
            except ValueError:
                await thread.send("Please enter a valid number.")

        # Now that we have a valid deposit_amount, we can update the gold in the database
        is_deposit_successful = await process_gold_deposit(discord_id, deposit_amount)
        if is_deposit_successful:
            await thread.send(f"Successfully deposited {deposit_amount} gold.")
        else:
            await thread.send("An error occurred while trying to deposit gold. Please try again later.")

    except Exception as e:
        logging.error(f"An error occurred while depositing gold: {str(e)}")
        await thread.send("An error occurred while trying to deposit gold. Please try again later.")

async def process_gold_deposit(discord_id, deposit_amount):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            try:
                await conn.begin()
                await cursor.execute(
                    "UPDATE players SET current_gold = current_gold - %s WHERE discord_id = %s",
                    (deposit_amount, discord_id)
                )
                await cursor.execute(
                    "UPDATE residential_storage SET gold_storage = COALESCE(gold_storage, 0) + %s WHERE discord_id = %s",
                    (deposit_amount, discord_id)
                )
                await conn.commit()
                return True
            except Exception as e:
                logging.error(f"An error occurred while depositing gold: {str(e)}")
                await conn.rollback()
                return False

async def get_player_bank_gold(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute("SELECT gold_storage FROM residential_storage WHERE discord_id = %s", (discord_id,))
                result = await cursor.fetchone()
                if result:
                    gold_storage = result['gold_storage']

                    # Check for various representations of None
                    if gold_storage is None or str(gold_storage).lower() in ["none", "null"]:
                        return 0  # Return 0 if the gold_storage field is None or "none" or "null"
                    
                    return gold_storage
                else:
                    logging.error(f"No residential storage found with discord_id {discord_id}")
                    return 0
    except Exception as e:
        logging.error(f"An error occurred while getting the bank gold of the player {discord_id}: {str(e)}")
        return 0

async def get_player_gold(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute("SELECT current_gold FROM players WHERE discord_id = %s", (discord_id,))
                result = await cursor.fetchone()
                if result:
                    current_gold = result['current_gold']

                    # Check for various representations of None
                    if current_gold is None or str(current_gold).lower() in ["none", "null"]:
                        return 0  # Return 0 if the current_gold field is None or "none" or "null"
                    
                    return current_gold
                else:
                    logging.error(f"No player found with discord_id {discord_id}")
                    return 0
    except Exception as e:
        logging.error(f"An error occurred while getting the gold of the player {discord_id}: {str(e)}")
        return 0

async def handle_take_gold(discord_id, thread):
    try:
        # Fetch current player's storage gold
        current_gold_storage = await get_storage_gold(discord_id)
        while True:
            take_msg = await thread.send(f"You currently have {current_gold_storage} gold in your storage. How much do you want to withdraw? You can type 'exit' to cancel the process.")

            def check(m):
                # Check if the message is from the right user
                return m.author.id == discord_id

            # Wait for a message from the user
            msg = await bot.wait_for('message', check=check)

            if msg.content.lower() in ['exit', 'quit']:
                await thread.send("Exiting gold withdrawal.")
                return

            try:
                take_amount = int(msg.content)
                if take_amount > current_gold_storage:
                    await thread.send(f"You do not have enough gold in your storage. You only have {current_gold_storage} gold.")
                elif take_amount <= 0:
                    await thread.send("The amount must be greater than 0.")
                else:
                    break  # Correctly used 'break' inside a loop
            except ValueError:
                await thread.send("Please enter a valid number.")

        # Now that we have a valid take_amount, we can update the gold in the database
        is_take_successful = await process_gold_take(discord_id, take_amount)
        if is_take_successful:
            await thread.send(f"Successfully withdrew {take_amount} gold.")
        else:
            await thread.send("An error occurred while trying to withdraw gold. Please try again later.")

    except Exception as e:
        logging.error(f"An error occurred while withdrawing gold: {str(e)}")
        await thread.send("An error occurred while trying to withdraw gold. Please try again later.")

async def process_gold_take(discord_id, take_amount):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            try:
                await conn.begin()
                await cursor.execute(
                    "UPDATE residential_storage SET gold_storage = COALESCE(gold_storage, 0) - %s WHERE discord_id = %s",
                    (take_amount, discord_id)
                )
                await cursor.execute(
                    "UPDATE players SET current_gold = COALESCE(current_gold, 0) + %s WHERE discord_id = %s",
                    (take_amount, discord_id)
                )
                await conn.commit()
                return True
            except Exception as e:
                logging.error(f"An error occurred while withdrawing gold: {str(e)}")
                await conn.rollback()
                return False

async def get_storage_gold(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute("SELECT gold_storage FROM residential_storage WHERE discord_id = %s", (discord_id,))
                result = await cursor.fetchone()
                if result:
                    return result['gold_storage']
                else:
                    logging.error(f"No player found with discord_id {discord_id}")
                    return None

    except Exception as e:
        logging.error(f"An error occurred while getting the storage gold of the player {discord_id}: {str(e)}")
        return None

async def handle_view_stored_items(discord_id, thread):
    try:
        # Create a new connection and a new cursor
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute(
                    "SELECT item_slot1_id, item_slot2_id, item_slot3_id, item_slot4_id, item_slot5_id, item_slot6_id, item_slot7_id, item_slot8_id, item_slot1_class, item_slot2_class, item_slot3_class, item_slot4_class, item_slot5_class, item_slot6_class, item_slot7_class, item_slot8_class, gold_storage FROM residential_storage WHERE discord_id = %s",
                    (discord_id,),
                )
                storage = await cursor.fetchone()

                if storage:
                    item_ids = [str(item) for item in storage[:8]]
                    item_classes = [str(item_class) for item_class in storage[8:16]]
                    gold_storage = storage[16]

                    # Create list of items along with their respective slots
                    item_id_class_pairs = [(item_id, item_class) for item_id, item_class in zip(item_ids, item_classes) if item_id != 'None' and item_class != 'None']

                    # Calculate the total number of slots and how many are taken
                    total_slots = 8
                    taken_slots = len(item_id_class_pairs)
                    remaining_slots = total_slots - taken_slots

                    # Create an embed for stored items
                    storage_embed = discord.Embed(
                        title="Residential Storage",
                        description=f"Your items held in Residential Storage:\n**Slots Used: {taken_slots}/{total_slots}**\n**Slots Remaining: {remaining_slots}**\n\n**Gold Stored: {gold_storage}**",
                        color=discord.Color.blue(),
                    )

                    if item_id_class_pairs:
                        # Generate the list of item names for the embed message
                        item_names = []
                        for item_id, item_class in item_id_class_pairs:
                            try:
                                item_name = await fetch_item(item_class, item_id)
                                if item_name:
                                    item_names.append(item_name)
                            except discord.HTTPException:
                                await thread.send(f"Failed to fetch item: {item_id}. Please try again later.")
                            except Exception as e:
                                logging.error(f"An error occurred while fetching item: {str(e)}")

                        item_storage_text = "\n".join(f"{i+1}. {item}" for i, item in enumerate(item_names))
                        storage_embed.add_field(name="Stored Items", value=item_storage_text, inline=False)
                    else:
                        storage_embed.add_field(name="Stored Items", value="Your residential storage is empty.", inline=False)

                    # Send the stored items embed to the thread
                    await thread.send(embed=storage_embed)
                    return
                else:
                    await thread.send("You don't have any items in your residential storage.")
                    return
    except Exception as e:
        logging.error(f"An error occurred while fetching stored items: {str(e)}")
        await thread.send("An error occurred while processing your request. Please try again later.")
    # Player Cooldown
    player_cooldowns[discord_id] = {'last_time': time.time()}
    # Start the timer to check for inactivity and delete the thread
    await manage_thread_activity(discord_id, thread, active_threads)

async def get_table_name(column_name):
    if column_name in ['equipped_weapon_id']:
        return 'weapons'
    elif column_name in ['equipped_helmet_id', 'equipped_chest_id', 'equipped_legs_id', 'equipped_feet_id']:
        return 'armour'
    elif column_name in ['equipped_amulet_id', 'equipped_ring1_id', 'equipped_ring2_id', 'equipped_charm_id']:
        return 'items'
    else:
        return None

async def get_player_inventory_embed(ctx, discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:

                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")

                await cursor.execute("SELECT current_gold FROM players WHERE discord_id = %s", (discord_id,))
                gold_result = await cursor.fetchone()
                if gold_result is not None:
                    current_gold = gold_result['current_gold']
                else:
                    current_gold = 0  # Default to 0 if no result is found

                await cursor.execute("SELECT * FROM player_inventory WHERE discord_id = %s", (discord_id,))
                inventory = await cursor.fetchone()

                if inventory:
                    # Create the embed message
                    embed_message = Embed(title=f"Inventory for {ctx.author.name}", color=0x00ff00)
                    embed_message.add_field(name="Gold", value=str(current_gold), inline=False)

                    for i in range(1, 9):
                        item_id = inventory[f'item_slot{i}_id']
                        item_class = inventory[f'item_slot{i}_class']

                        if item_id is not None and item_class is not None:
                            try:
                                item_name = await fetch_item(item_class, item_id)
                                if item_name:
                                    embed_message.add_field(name=f"Inventory Slot {i}", value=item_name, inline=False)
                            except Exception as e:
                                logging.error(f"Failed to fetch item in inventory: {str(e)}", exc_info=True)

                    armour_types = {
                        'helmet': 'Helmet',
                        'chest': 'Chest Armour',
                        'legs': 'Leg Armour',
                        'feet': 'Footwear'
                    }
                    for item_type, armour_type in [('weapon', 'Weapon')] + list(armour_types.items()) + [('amulet', 'Amulet'), ('ring1', 'Ring'), ('ring2', 'Ring'), ('charm', 'Charm')]:
                        equipped_id = inventory[f'equipped_{item_type}_id']
                        if equipped_id is not None:
                            table_name = 'weapons' if item_type == 'weapon' else 'armour' if item_type in armour_types else 'items'
                            await cursor.execute(f"SELECT name FROM {table_name} WHERE id = %s", (equipped_id,))
                            item_name = await cursor.fetchone()
                            if item_name:
                                embed_message.add_field(name=f"Equipped {armour_type}", value=item_name['name'], inline=False)

                    # Add emotes to inventory embed
                    inventory_msg = await ctx.send(embed=embed_message)
                    await inventory_msg.add_reaction('🔴')  # For healing
                    await inventory_msg.add_reaction('🔵')  # For mana refill
                    await inventory_msg.add_reaction('📜')  # For teleportation

                    return
                else:
                    await ctx.send("Your inventory is empty.")
                    return
    except Exception as e:
        logging.error(f"An error occurred while retrieving player inventory: {str(e)}")
        await ctx.send("An error occurred while retrieving player inventory. Please try again later.")

async def update_current_health_and_mana(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                
                # Initialize total_health and total_mana to 0
                total_health = total_mana = 0
                
                # Attempt to retrieve the total health and total mana of the player from the player_inventory table.
                await cursor.execute("SELECT total_health, total_mana FROM player_inventory WHERE discord_id = %s", (discord_id,))
                result_inv = await cursor.fetchone()
                
                # If the player has an inventory entry and total_health or total_mana are greater than 0, add them to variables.
                if result_inv and (result_inv['total_health'] > 0 or result_inv['total_mana'] > 0):
                    total_health += result_inv['total_health']
                    total_mana += result_inv['total_mana']

                # Retrieve the health and mana attributes of the player from the player_attributes table.
                await cursor.execute("SELECT health, mana FROM player_attributes WHERE discord_id = %s", (discord_id,))
                result_attr = await cursor.fetchone()
                
                # If the player has an entry in the player_attributes table, add the health and mana values to the total_health and total_mana variables.
                if result_attr:
                    total_health += result_attr['health']
                    total_mana += result_attr['mana']

                # Retrieve current_health and current_mana from the players table
                await cursor.execute("SELECT current_health, current_mana FROM players WHERE discord_id = %s", (discord_id,))
                current_values = await cursor.fetchone()

                # If current_health or current_mana are greater than total_health or total_mana, set them equal to total_health or total_mana
                if current_values['current_health'] > total_health:
                    current_values['current_health'] = total_health
                else:
                    current_values['current_health'] = total_health
                if current_values['current_mana'] > total_mana:
                    current_values['current_mana'] = total_mana
                else:
                    current_values['current_mana'] = total_mana

                # Update the current health and mana of the player in the players table using the values retrieved above.
                await conn.begin()
                await cursor.execute("UPDATE players SET current_health = %s, current_mana = %s WHERE discord_id = %s", (current_values['current_health'], current_values['current_mana'], discord_id))
                await conn.commit()

            # If the update operation is successful, return True to signify a successful update.
            return True

    except Exception as e:
        # If an exception occurs during the update operation, log the error and print a message.
        logging.error(f"Failed to update current health and mana for Discord ID {discord_id}: {e}")
        print(f"Failed to update current health and mana for Discord ID {discord_id}: {e}")

        # Return False to signify a failure to update.
        return False

async def update_current_health_and_mana_equip(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                
                # Initialize total_health and total_mana to 0
                total_health = total_mana = 0
                
                # Attempt to retrieve the total health and total mana of the player from the player_inventory table.
                await cursor.execute("SELECT total_health, total_mana FROM player_inventory WHERE discord_id = %s", (discord_id,))
                result_inv = await cursor.fetchone()
                
                # If the player has an inventory entry and total_health or total_mana are greater than 0, add them to variables.
                if result_inv and (result_inv['total_health'] > 0 or result_inv['total_mana'] > 0):
                    total_health += result_inv['total_health']
                    total_mana += result_inv['total_mana']

                # Retrieve the health and mana attributes of the player from the player_attributes table.
                await cursor.execute("SELECT health, mana FROM player_attributes WHERE discord_id = %s", (discord_id,))
                result_attr = await cursor.fetchone()
                
                # If the player has an entry in the player_attributes table, add the health and mana values to the total_health and total_mana variables.
                if result_attr:
                    total_health += result_attr['health']
                    total_mana += result_attr['mana']

                # Retrieve current_health and current_mana from the players table
                await cursor.execute("SELECT current_health, current_mana FROM players WHERE discord_id = %s", (discord_id,))
                current_values = await cursor.fetchone()

                # If current_health or current_mana are greater than total_health or total_mana, set them equal to total_health or total_mana
                if current_values['current_health'] > total_health:
                    current_values['current_health'] = total_health
                else:
                    pass
                if current_values['current_mana'] > total_mana:
                    current_values['current_mana'] = total_mana
                else:
                    pass

                # Update the current health and mana of the player in the players table using the values retrieved above.
                await conn.begin()
                await cursor.execute("UPDATE players SET current_health = %s, current_mana = %s WHERE discord_id = %s", (current_values['current_health'], current_values['current_mana'], discord_id))
                await conn.commit()

            # If the update operation is successful, return True to signify a successful update.
            return True

    except Exception as e:
        # If an exception occurs during the update operation, log the error and print a message.
        logging.error(f"Failed to update current health and mana for Discord ID {discord_id}: {e}")
        print(f"Failed to update current health and mana for Discord ID {discord_id}: {e}")

        # Return False to signify a failure to update.
        return False


async def calculate_base_health_and_mana(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:

                # Retrieve the player's default attributes
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute("SELECT strength, intelligence FROM player_attributes WHERE discord_id = %s", (discord_id,))
                attributes = await cursor.fetchone()

                if attributes:
                    strength = attributes[0]
                    intelligence = attributes[1]

                    # Calculate the base health and mana using the default attribute values
                    base_health = strength * HEALTH_PER_STRENGTH
                    base_mana = intelligence * MANA_PER_INTELLIGENCE

                    # Update the player's base health and mana in the player_attributes table
                    await conn.begin()  # Begin the transaction
                    await cursor.execute("UPDATE player_attributes SET health = %s, mana = %s WHERE discord_id = %s", (base_health, base_mana, discord_id))
                    await conn.commit()
                    logging.info(f"Successfully updated health and mana for {discord_id}")
                    return True
                else:
                    logging.warning(f"No attributes found for {discord_id}")
                    return False

    except Exception as e:
        logging.error(f"An error occurred while calculating base health and mana for {discord_id}: {str(e)}")
        return False

async def recalculate_player_inventory_attributes(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:

                # Check if the player has an inventory entry
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                # Retrieve the equipped item IDs for the player
                await cursor.execute("SELECT equipped_weapon_id, equipped_helmet_id, equipped_chest_id, equipped_legs_id, equipped_feet_id, equipped_amulet_id, equipped_ring1_id, equipped_ring2_id, equipped_charm_id FROM player_inventory WHERE discord_id = %s", (discord_id,))
                equipped_items = await cursor.fetchone()

                if equipped_items is None:
                    return True

                # Extract the equipped item IDs
                equipped_weapon_id, equipped_helmet_id, equipped_chest_id, equipped_legs_id, equipped_feet_id, equipped_amulet_id, equipped_ring1_id, equipped_ring2_id, equipped_charm_id = equipped_items

                # Initialize attribute totals
                total_strength = 0
                total_agility = 0
                total_intelligence = 0
                total_stamina = 0

                # Helper function to calculate attribute totals
                async def calculate_attributes(item_id, table):
                    nonlocal total_strength, total_agility, total_intelligence, total_stamina
                    if item_id:
                        await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                        await cursor.execute(f"SELECT strength, agility, intelligence, stamina FROM {table} WHERE id = %s", (item_id,))
                        item_stats = await cursor.fetchone()
                        if item_stats:
                            total_strength += item_stats[0]
                            total_agility += item_stats[1]
                            total_intelligence += item_stats[2]
                            total_stamina += item_stats[3]

                # Calculate attributes for each equipped item
                await calculate_attributes(equipped_weapon_id, 'weapons')
                await calculate_attributes(equipped_helmet_id, 'armour')
                await calculate_attributes(equipped_chest_id, 'armour')
                await calculate_attributes(equipped_legs_id, 'armour')
                await calculate_attributes(equipped_feet_id, 'armour')
                await calculate_attributes(equipped_amulet_id, 'items')
                await calculate_attributes(equipped_ring1_id, 'items')
                await calculate_attributes(equipped_ring2_id, 'items')
                await calculate_attributes(equipped_charm_id, 'items')

                # Calculate health and mana based on attributes
                total_health = total_strength * HEALTH_PER_STRENGTH
                total_mana = total_intelligence * MANA_PER_INTELLIGENCE

                await conn.begin()  # Begin the transaction
                # Update the attribute totals in the player_inventory table
                await cursor.execute("UPDATE player_inventory SET total_strength = %s, total_agility = %s, total_intelligence = %s, total_stamina = %s, total_health = %s, total_mana = %s WHERE discord_id = %s", (total_strength, total_agility, total_intelligence, total_stamina, total_health, total_mana, discord_id))
                await conn.commit()  # Commit the transaction

                logging.info(f"Successfully recalculated player inventory for user {discord_id}")

                return True
    except Exception as e:
        logging.error(f"Failed to recalculate player attributes for Discord ID {discord_id}: {str(e)}")
        if conn:
            await conn.rollback()

        return False

async def move_to_tile(discord_id, tile_id, thread):
    user_lock = user_locks.setdefault(discord_id, asyncio.Lock())
    async with user_lock:
        try:
            # Player thread activity bumper
            player_cooldowns[discord_id] = {'last_time': time.time()}
            await manage_thread_activity(discord_id, thread, active_threads)

            # Check if the Crown wallet is online
            if not await is_crown_wallet_online():
                await thread.send('The Crown wallet is currently offline. Please try again later.')
                return

            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:

                    await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                    await cursor.execute("SELECT * FROM map_tiles WHERE id = %s", (tile_id,))
                    result = await cursor.fetchone()

                    if result:
                        try:
                            # Begin the transaction
                            await conn.begin()
                            await cursor.execute("UPDATE player_location SET tile_id = %s WHERE discord_id = %s", (result['id'], discord_id))
                            await conn.commit()
                        except Exception as e:
                            await conn.rollback()
                            logging.error(f"An error occurred while updating the tile ID for player {discord_id}: {str(e)}")

                        if 'Residential Area' in result['tile_name']:
                            # This is a residential area
                            embed = discord.Embed(
                                title=f"Welcome to {result['tile_name']} in {result['area_name']}",
                                description="You are now in a residential area. Here you can interact with the locals, rest at an inn, or explore the town.",
                                color=discord.Color.green()
                            )
                            embed.add_field(name="Left", value=":arrow_left:", inline=True)
                            embed.add_field(name="Right", value=":arrow_right:", inline=True)
                            embed.add_field(name="Storage", value=":house:", inline=True)

                            # Send the embed message to the thread
                            message = await thread.send(embed=embed)
                            await message.add_reaction('⬅️')
                            await message.add_reaction('➡️')
                            await message.add_reaction('🏠')
                            
                            return
                        elif 'Town Center' in result['tile_name']:
                            # This is a Town Center
                            embed = discord.Embed(
                                title=f"Welcome to {result['tile_name']} in {result['area_name']}",
                                description="You are now in the town center. Here you can deposit and withdraw from the bank and interact with the townsfolk.",
                                color=discord.Color.green()
                            )
                            embed.add_field(name="Left", value=":arrow_left:", inline=True)
                            embed.add_field(name="Right", value=":arrow_right:", inline=True)
                            embed.add_field(name="Bank", value=":bank:", inline=True)

                            # Send the embed message to the thread
                            message = await thread.send(embed=embed)
                            await message.add_reaction('⬅️')
                            await message.add_reaction('➡️')
                            await message.add_reaction('🏦')

                            return
                        elif any(result['tile_name'].endswith(market) for market in ('Marketplace', 'Black Market', 'Outpost Market')):
                            # This is a Marketplace
                            embed = discord.Embed(
                                title=f"Welcome to {result['tile_name']} in {result['area_name']}",
                                description="You are now in the marketplace. Here you can buy and sell goods.",
                                color=discord.Color.green()
                            )
                            embed.add_field(name="Left", value=":arrow_left:", inline=True)
                            embed.add_field(name="Right", value=":arrow_right:", inline=True)
                            embed.add_field(name="Shop", value=":shopping_cart:", inline=True)

                            # Send the embed message to the thread
                            message = await thread.send(embed=embed)
                            await message.add_reaction('⬅️')
                            await message.add_reaction('➡️')
                            await message.add_reaction('🛒')

                            return
                        elif 'Training Grounds' in result['tile_name'] or 'Spellbound Library' in result['tile_name']:
                            # This is a special area
                            embed = discord.Embed(
                                title=f"Welcome to {result['tile_name']} in {result['area_name']}",
                                description="You are now in a special training area. Here you can train and improve your skills.",
                                color=discord.Color.green()
                            )
                            embed.add_field(name="Left", value=":arrow_left:", inline=True)
                            embed.add_field(name="Right", value=":arrow_right:", inline=True)
                            embed.add_field(name="Train", value=":dart:", inline=True)

                            # Send the embed message to the thread
                            message = await thread.send(embed=embed)
                            await message.add_reaction('⬅️')
                            await message.add_reaction('➡️')
                            await message.add_reaction('🎯')  # Train

                            return
                        else:
                            # This is a normal area
                            embed = discord.Embed(
                                title=f"Moved to {result['tile_name']} in {result['area_name']}.",
                                description=f"{result['description']}",
                                color=discord.Color.green()
                            )
                            embed.add_field(name="Left", value=":arrow_left:", inline=True)
                            embed.add_field(name="Right", value=":arrow_right:", inline=True)

                            # Send the embed message to the thread
                            message = await thread.send(embed=embed)
                            await message.add_reaction('⬅️')
                            await message.add_reaction('➡️')

                        if random.random() <= result['chance_mob_encounter']:
                            logging.info(f"Player {discord_id} has encountered a mob at tile {result['tile_name']}")
                            await spawn_mob_or_boss(discord_id, result, thread)
                        return
                    else:
                        logging.warning(f"Player {discord_id} attempted to move to non-existing tile {tile_id}")
                        await thread.send(f"Tile with ID {tile_id} does not exist.")
                        return

        except Exception as e:
            logging.error(f"An error occurred while player {discord_id} tried moving: {str(e)}")
            await thread.send("An error occurred while moving. Please try again later.")

async def move_to_residential(discord_id, tile_id, thread):
        try:
            # Player thread activity bumper
            player_cooldowns[discord_id] = {'last_time': time.time()}
            await manage_thread_activity(discord_id, thread, active_threads)

            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:

                    await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                    await cursor.execute("SELECT * FROM map_tiles WHERE id = %s", (tile_id,))
                    result = await cursor.fetchone()

                    if result:
                        try:
                            # Begin the transaction
                            await conn.begin()
                            await cursor.execute("UPDATE player_location SET tile_id = %s WHERE discord_id = %s", (result['id'], discord_id))
                            await conn.commit()
                        except Exception as e:
                            await conn.rollback()
                            logging.error(f"An error occurred while updating the tile ID for player {discord_id}: {str(e)}")

                        # This is a residential area
                        embed = discord.Embed(
                            title=f"Welcome to {result['tile_name']} in {result['area_name']}",
                            description="You are now in a residential area. Here you can interact with the locals, rest at an inn, or explore the town.",
                            color=discord.Color.green()
                        )
                        embed.add_field(name="Left", value=":arrow_left:", inline=True)
                        embed.add_field(name="Right", value=":arrow_right:", inline=True)
                        embed.add_field(name="Storage", value=":house:", inline=True)

                        # Send the embed message to the thread
                        message = await thread.send(embed=embed)
                        await message.add_reaction('⬅️')
                        await message.add_reaction('➡️')
                        await message.add_reaction('🏠')
                        
                        return True

                    else:
                        logging.warning(f"Player {discord_id} attempted to respawn to non-existing tile {tile_id}")
                        await thread.send(f"Tile with ID {tile_id} does not exist.")
                        return

        except Exception as e:
            logging.error(f"An error occurred while player {discord_id} tried moving: {str(e)}")
            await thread.send("An error occurred while moving. Please try again later.")

async def use_health_potion(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                
                await cursor.execute("SELECT current_health FROM players WHERE discord_id = %s", (discord_id,))
                current_health = await cursor.fetchone()

                await cursor.execute("SELECT total_health FROM player_inventory WHERE discord_id = %s", (discord_id,))
                total_health = await cursor.fetchone()

                if current_health["current_health"] == total_health["total_health"]:
                    return "Your health is already full!", None

                await cursor.execute("SELECT * FROM player_inventory WHERE discord_id = %s", (discord_id,))
                player_inventory = await cursor.fetchone()

                if player_inventory is None:
                    return "You have no items in your inventory.", None

                item_slot_ids = [player_inventory[f"item_slot{i+1}_id"] for i in range(8)]
                item_slot_classes = [player_inventory[f"item_slot{i+1}_class"] for i in range(8)]

                for i in range(8):
                    if item_slot_ids[i] == 1 and item_slot_classes[i] == "Consumable":
                        await conn.begin()  # Begin the transaction
                        await cursor.execute(f"UPDATE player_inventory SET item_slot{i+1}_id = NULL, item_slot{i+1}_class = NULL WHERE discord_id = %s", (discord_id,))
                        await cursor.execute("UPDATE players SET current_health = %s WHERE discord_id = %s", (total_health["total_health"], discord_id))
                        await conn.commit()  # Commit the transaction
                        logging.info(f"Successfully used health potion for user {discord_id}")
                        return "success", total_health["total_health"]

                return "You don't have any health potions in your inventory.", None

    except Exception as e:
        logging.error(f"An error occurred while trying to use a health potion for user {discord_id}: {str(e)}")
        if conn:
            conn.rollback()
        return "An error occurred while trying to use a health potion.", None

async def use_mana_potion(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                
                await cursor.execute("SELECT current_mana FROM players WHERE discord_id = %s", (discord_id,))
                current_mana = await cursor.fetchone()

                await cursor.execute("SELECT total_mana FROM player_inventory WHERE discord_id = %s", (discord_id,))
                total_mana = await cursor.fetchone()

                if current_mana["current_mana"] == total_mana["total_mana"]:
                    return "Your mana is already full!", None

                await cursor.execute("SELECT * FROM player_inventory WHERE discord_id = %s", (discord_id,))
                player_inventory = await cursor.fetchone()

                if player_inventory is None:
                    return "You have no items in your inventory.", None

                item_slot_ids = [player_inventory[f"item_slot{i+1}_id"] for i in range(8)]
                item_slot_classes = [player_inventory[f"item_slot{i+1}_class"] for i in range(8)]

                for i in range(8):
                    if item_slot_ids[i] == 2 and item_slot_classes[i] == "Consumable":
                        await conn.begin()  # Begin the transaction
                        await cursor.execute(f"UPDATE player_inventory SET item_slot{i+1}_id = NULL, item_slot{i+1}_class = NULL WHERE discord_id = %s", (discord_id,))
                        await cursor.execute("UPDATE players SET current_mana = %s WHERE discord_id = %s", (total_mana["total_mana"], discord_id))
                        await conn.commit()  # Commit the transaction
                        logging.info(f"Successfully used mana potion for user {discord_id}")
                        return "success", total_mana["total_mana"]

                return "You don't have any mana potions in your inventory.", None

    except Exception as e:
        logging.error(f"An error occurred while trying to use a mana potion for user {discord_id}: {str(e)}")
        if conn:
            conn.rollback()
        return "An error occurred while trying to use a mana potion.", None

async def use_teleport_scroll(discord_id, thread):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:

                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute("SELECT * FROM player_inventory WHERE discord_id = %s", (discord_id,))
                player_inventory = await cursor.fetchone()

                if player_inventory is None:
                    return "You have no items in your inventory."

                item_slot_ids = [player_inventory[f"item_slot{i+1}_id"] for i in range(8)]
                item_slot_classes = [player_inventory[f"item_slot{i+1}_class"] for i in range(8)]

                for i in range(8):
                    if item_slot_ids[i] == 3 and item_slot_classes[i] == "Consumable":
                        await conn.begin()  # Begin the transaction
                        await cursor.execute("UPDATE player_inventory SET item_slot{}_id = NULL, item_slot{}_class = NULL WHERE discord_id = %s".format(i+1, i+1), (discord_id,))
                        await conn.commit()  # Commit the transaction

                        current_location = await get_player_location(discord_id)

                        if current_location is not None:
                            town_residential_area = await get_residential_area(current_location)

                            if town_residential_area is not None:
                                logging.info(f"Residential area tile id fetched for location {current_location}: {town_residential_area}.")
                                await thread.send("Woosh...")
                                await asyncio.sleep(1)
                                if await move_to_residential(discord_id, town_residential_area, thread) is True:
                                    return "success"
                            else:
                                logging.warning(f"Residential tile not found for location: {current_location}.")
                                await conn.rollback()  # Rollback the transaction
                                return "Could not find the residential tile to teleport to. Please try again."
                        else:
                            logging.warning(f"Player location not found for discord_id: {discord_id}.")
                            await conn.rollback()  # Rollback the transaction
                            return "Could not find your current location. Please try again."

                await conn.rollback()  # Rollback the transaction
                return "You don't have any teleport scrolls in your inventory."

    except Exception as e:
        logging.error(f"An error occurred while trying to use a teleport scroll: {str(e)}, Type: {type(e)}")
        return "An error occurred while trying to use a teleport scroll."

# Function to handle spawning a mob for a player
async def spawn_mob_or_boss(discord_id, result, thread):
    try:
        if result:
            area_name = result['area_name']

            if area_name == 'The Gloaming Vale':
                # Get the mobs and boss for The Gloaming Vale
                mobs = await get_mobs_for_gloaming_vale()
                boss = await get_boss_for_area(area_name)
            elif area_name == 'Scorched Plains':
                # Get the mobs and boss for the Scorched Plains
                mobs = await get_mobs_for_scorched_plains()
                boss = await get_boss_for_area(area_name)
            elif area_name == 'Tide Whisper Coves':
                # Get the mobs and boss for Tide Whisper Coves
                mobs = await get_mobs_for_tide_whisper_coves()
                boss = await get_boss_for_area(area_name)
            elif area_name == 'Shadowmire': # New area
                mobs = await get_mobs_for_shadowmire()
                boss = await get_boss_for_area(area_name)
            elif area_name == 'The Ember Barrens':
                # Get the mobs and boss for The Ember Barrens
                mobs = await get_mobs_for_ember_barrens()
                boss = await get_boss_for_area(area_name)
            else:
                # Handle the case when the area name is not recognized
                logging.warning(f"Unknown area: {area_name}. No mob encountered.")
                return

            # Determine whether a boss or regular mob will spawn based on chance
            spawn_boss = random.random() <= await get_boss_spawn_chance(area_name)

            if spawn_boss and boss:
                logging.info("Spawning boss")
                await handle_spawn_boss(discord_id, boss, thread)
                return
            else:
                logging.info("Spawning mob")
                await spawn_mob(discord_id, mobs, thread)
                return
        else:
            logging.warning("Tile information not found.")
            await thread.send(f"<@{discord_id}>, Tile information not found.")
            return

    except Exception as e:
        logging.error(f"An error occurred while spawning a mob or boss for the player: {str(e)}")
        await thread.send(f"<@{discord_id}>, An error occurred while spawning a mob or boss. Please try again later.")
        return

async def get_residential_area(town):
    if town == "The Gloaming Vale" or town == "Shadowhaven":
        return 2
    elif town == "Scorched Plains" or town == "Ironkeep":
        return 22
    elif town == "Tide Whisper Coves" or town == "Havenreach":
        return 51
    elif town == "Shadowmire" or town == "Grimhold":
        return 71
    elif town == "The Ember Barrens" or town == "Ashenfell":
        return 90
    else:
        return None

# Placeholder functions to get mobs for each area
async def get_mobs_for_gloaming_vale():
    return ['Shadow Stalker', 'Nocturnal Beast', 'Voidcaster', 'Twilight Sprite']

async def get_mobs_for_scorched_plains():
    return ['Iron Golem', 'Steel Mantis', 'Siege Wraith', 'Flame Djinn']

async def get_mobs_for_tide_whisper_coves():
    return ['Sea Serpent', 'Storm Harpy', 'Kraken Spawn', 'Spectral Pirate']

async def get_mobs_for_shadowmire():
    return ['Mist Wraith', 'Thorned Beast', 'Eldritch Shade', 'Mire Stalker']

async def get_mobs_for_ember_barrens():
    return ['Wasteland Behemoth', 'Ashen Wraith', 'Ember Drake', 'Barrens Goliath']

async def get_boss_for_area(area_name):
    bosses = {
        'The Gloaming Vale': {'id': 1, 'name': 'Night Whisper', 'strength': 35, 'agility': 30, 'intelligence': 35, 'stamina': 45, 'description': 'This entity is a synthesis of perpetual darkness and arcane power, commanding shadow magic and nightmare creatures.'},
        'Scorched Plains': {'id': 2, 'name': 'Steel Behemoth', 'strength': 45, 'agility': 20, 'intelligence': 35, 'stamina': 50, 'description': 'An enormous construct forged from the remnants of ancient warfare. Built with unyielding iron, it bears formidable siege weaponry.'},
        'Tide Whisper Coves': {'id': 3, 'name': 'Deepmaw', 'strength': 50, 'agility': 30, 'intelligence': 35, 'stamina': 55, 'description': "A tremendous sea beast that has assailed Havenreach's coasts for centuries. Its strength and fury echo the tempestuous seas it emerges from."},
        'Shadowmire': {'id': 4, 'name': 'Mistweaver', 'strength': 40, 'agility': 35, 'intelligence': 50, 'stamina': 60, 'description': 'An ancient entity from the cursed woods, it manipulates forbidden magics and the surrounding mists to ensnare its enemies.'},
        'The Ember Barrens': {'id': 5, 'name': 'Cinderbound', 'strength': 55, 'agility': 40, 'intelligence': 45, 'stamina': 65, 'description': 'Born from fire and devastation, this gargantuan creature rules the barren landscapes surrounding Ashenfell. Its fiery breath and raw strength challenge even the bravest adventurers.'}
    }

    return bosses.get(area_name)

async def check_cooldown(ctx, discord_id):
    try:
        if discord_id in player_cooldowns:
            player_cooldown = player_cooldowns[discord_id]
            last_time = player_cooldown.get('last_time', 0)
            current_time = time.time()
            cooldown_remaining = last_time + 1 - current_time  

            if cooldown_remaining > 0:
                await ctx.send(f"Please wait {cooldown_remaining:.1f} seconds before using the command again.")
                return False
        return True
    except Exception as e:
        logging.error(f"An error occurred while checking cooldown: {str(e)}")
        return False

async def fetch_base_stats(ctx, discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute("SELECT * FROM player_attributes WHERE discord_id = %s", (discord_id,))
                base_stats = await cursor.fetchone()
                return base_stats

    except Exception as e:
        logging.error(f"An error occurred while fetching base stats: {str(e)}")
        await ctx.send("An error occurred while fetching your base stats. Please try again later.")
        return None

async def add_base_stats_to_embed(embed_message, base_stats):
    try:
        embed_message.add_field(name="Player Base Stats", value=(
            f"- Base Strength: {base_stats['strength']}\n"
            f"- Base Agility: {base_stats['agility']}\n"
            f"- Base Intelligence: {base_stats['intelligence']}\n"
            f"- Base Stamina: {base_stats['stamina']}\n"
        ), inline=False)
    except Exception as e:
        logging.error(f"An error occurred while adding base stats to embed: {str(e)}")

async def fetch_equipped_stats(ctx, discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute("SELECT * FROM player_inventory WHERE discord_id = %s", (discord_id,))
                inventory = await cursor.fetchone()

                if inventory:
                    equipped_stats = {
                        'weapon': None,
                        'helmet': None,
                        'chest': None,
                        'legs': None,
                        'feet': None,
                        'amulet': None,
                        'rings': [],
                        'charm': None,
                    }

                    equipped_weapon_id = inventory['equipped_weapon_id']
                    equipped_helmet_id = inventory['equipped_helmet_id']
                    equipped_chest_id = inventory['equipped_chest_id']
                    equipped_legs_id = inventory['equipped_legs_id']
                    equipped_feet_id = inventory['equipped_feet_id']
                    equipped_amulet_id = inventory['equipped_amulet_id']
                    equipped_ring1_id = inventory['equipped_ring1_id']
                    equipped_ring2_id = inventory['equipped_ring2_id']
                    equipped_charm_id = inventory['equipped_charm_id']

                    # Fetch and store equipped weapon
                    if equipped_weapon_id is not None:
                        await cursor.execute("SELECT name, strength, agility, intelligence, stamina FROM weapons WHERE id = %s", (equipped_weapon_id,))
                        equipped_stats['weapon'] = await cursor.fetchone()

                    # Fetch and store equipped armour pieces
                    for equipped_id, armour_type in [
                        (equipped_helmet_id, 'helmet'),
                        (equipped_chest_id, 'chest'),
                        (equipped_legs_id, 'legs'),
                        (equipped_feet_id, 'feet'),
                    ]:
                        if equipped_id is not None:
                            await cursor.execute("SELECT name, strength, agility, intelligence, stamina FROM armour WHERE id = %s", (equipped_id,))
                            equipped_stats[armour_type] = await cursor.fetchone()

                    # Fetch and store equipped amulet
                    if equipped_amulet_id is not None:
                        await cursor.execute("SELECT name, strength, agility, intelligence, stamina FROM items WHERE id = %s", (equipped_amulet_id,))
                        equipped_stats['amulet'] = await cursor.fetchone()

                    # Fetch and store equipped rings
                    for equipped_ring_id in [equipped_ring1_id, equipped_ring2_id]:
                        if equipped_ring_id is not None:
                            await cursor.execute("SELECT name, strength, agility, intelligence, stamina FROM items WHERE id = %s", (equipped_ring_id,))
                            equipped_stats['rings'].append(await cursor.fetchone())

                    # Fetch and store equipped charm
                    if equipped_charm_id is not None:
                        await cursor.execute("SELECT name, strength, agility, intelligence, stamina FROM items WHERE id = %s", (equipped_charm_id,))
                        equipped_stats['charm'] = await cursor.fetchone()

                    return equipped_stats, inventory
                else:
                    return None, None

    except Exception as e:
        logging.error(f"An error occurred while fetching equipped stats: {str(e)}")
        await ctx.send("An error occurred while fetching your equipped stats. Please try again later.")
        await conn.rollback()  # Rollback the transaction
        return None, None

async def calculate_total_stats(ctx, discord_id, base_stats, equipped_stats):
    try:
        total_stats = {
            'strength': int(base_stats['strength']),
            'agility': int(base_stats['agility']),
            'intelligence': int(base_stats['intelligence']),
            'stamina': int(base_stats['stamina']),
        }

        for item_stats in equipped_stats.values():
            if item_stats is not None:
                if isinstance(item_stats, list):  # For rings
                    for stats in item_stats:
                        total_stats['strength'] += int(stats.get('strength', 0))
                        total_stats['agility'] += int(stats.get('agility', 0))
                        total_stats['intelligence'] += int(stats.get('intelligence', 0))
                        total_stats['stamina'] += int(stats.get('stamina', 0))
                elif isinstance(item_stats, dict):  # For other items
                    total_stats['strength'] += int(item_stats.get('strength', 0))
                    total_stats['agility'] += int(item_stats.get('agility', 0))
                    total_stats['intelligence'] += int(item_stats.get('intelligence', 0))
                    total_stats['stamina'] += int(item_stats.get('stamina', 0))
                    
        return total_stats
    except Exception as e:
        logging.error(f"An error occurred while calculating total stats: {str(e)}")
        return None

async def add_equip_to_inventory(discord_id, item_id, item_class, equip_slot, storage_slot):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")

                # Update the player's inventory
                await conn.begin()
                
                await cursor.execute(
                    f"UPDATE player_inventory SET {equip_slot} = %s, {equip_slot[:-3]}_class = %s WHERE discord_id = %s",
                    (item_id, item_class, discord_id),
                )

                # Now, remove the item from the residential storage
                await cursor.execute(
                    f"UPDATE residential_storage SET {storage_slot}_id = NULL, {storage_slot}_class = NULL WHERE discord_id = %s AND {storage_slot}_id = %s AND {storage_slot}_class = %s",
                    (discord_id, item_id, item_class),
                )

                await conn.commit()

                logging.info("Successfully added equipment to inventory")
                return True
    except Exception as e:
        logging.error(f"An error occurred while adding the equipment to inventory: {str(e)}")
        await conn.rollback()
        return False

async def add_item_to_inventory(discord_id, item_id, item_class, item_id_column, item_class_column):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:

                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                # First, check if there's an empty slot in the player's inventory
                await cursor.execute(
                    "SELECT item_slot1_id, item_slot2_id, item_slot3_id, item_slot4_id, item_slot5_id, item_slot6_id, item_slot7_id, item_slot8_id FROM player_inventory WHERE discord_id = %s",
                    (discord_id,)
                )
                inventory = await cursor.fetchone()
                empty_slots = [i for i, item in enumerate(inventory, start=1) if item is None or item == 'None']

                if empty_slots:
                    # Take the first empty slot
                    empty_slot = empty_slots[0]
                    empty_slot_id_column = f"item_slot{empty_slot}_id"
                    empty_slot_class_column = f"item_slot{empty_slot}_class"

                    # Update the player's inventory
                    await conn.begin()  # Begin the transaction
                    await cursor.execute(
                        f"UPDATE player_inventory SET {empty_slot_id_column} = %s, {empty_slot_class_column} = %s WHERE discord_id = %s",
                        (item_id, item_class, discord_id),
                    )

                    # Now, remove the item from the residential storage
                    await cursor.execute(
                        f"UPDATE residential_storage SET {item_id_column} = NULL, {item_class_column} = NULL WHERE discord_id = %s",
                        (discord_id,),
                    )

                    await conn.commit()  # Commit the transaction

                    return True
                else:
                    return False

    except Exception as e:
        logging.error(f"An error occurred while adding the item to inventory: {str(e)}")
        await conn.rollback()  # Rollback the transaction
        return False

async def fetch_price(item_class, item_id):
    try:
        if item_class is None or item_id is None:
            logging.error(f"Invalid parameters for fetch_price. item_id: {item_id}, item_class: {item_class}")
            return None
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                if item_class in ('items', 'item'):
                    await cursor.execute("SELECT class FROM items WHERE id = %s", (item_id,))
                    result = await cursor.fetchone()
                    if result and isinstance(result, tuple) and result[0]:
                        return await fetch_price(result[0], item_id)
                    else:
                        logging.error(f"Failed to fetch item class from 'items' table for item_id: {item_id}")
                        return None
                elif item_class in ('Consumable', 'Ring', 'Amulet', 'Charm', 'items', 'item'):
                    await cursor.execute("SELECT price FROM items WHERE id = %s", (item_id,))
                elif item_class in ('weapons', 'weapon'):
                    await cursor.execute("SELECT price FROM weapons WHERE id = %s", (item_id,))
                elif item_class == 'armour':
                    await cursor.execute("SELECT price FROM armour WHERE id = %s", (item_id,))

                result = await cursor.fetchone()

                # Return the first item in the result tuple, which should be the item name.
                if isinstance(result, tuple):
                    return result[0] if result else None
                else:
                    logging.info(f"Result is not tuple or it's none{result}")
                    return result if result else None

    except Exception as e:
        logging.error(f"Failed to fetch item: {str(e)}")
        return None

async def fetch_item(item_class, item_id):
    try:
        if item_class is None or item_id is None:
            logging.error(f"Invalid parameters for fetch_item. item_id: {item_id}, item_class: {item_class}")
            return None
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                if item_class in ('items', 'item'):
                    await cursor.execute("SELECT class FROM items WHERE id = %s", (item_id,))
                    result = await cursor.fetchone()
                    if result and isinstance(result, tuple) and result[0]:
                        return await fetch_item(result[0], item_id)
                    else:
                        logging.error(f"Failed to fetch item class from 'items' table for item_id: {item_id}")
                        return None
                elif item_class in ('Consumable', 'Ring', 'Amulet', 'Charm', 'items', 'item'):
                    await cursor.execute("SELECT name FROM items WHERE id = %s", (item_id,))
                elif item_class == 'weapons' or item_class == 'weapon':
                    await cursor.execute("SELECT name FROM weapons WHERE id = %s", (item_id,))
                elif item_class == 'armour':
                    await cursor.execute("SELECT name FROM armour WHERE id = %s", (item_id,))

                result = await cursor.fetchone()

                # Return the first item in the result tuple, which should be the item name.
                if isinstance(result, tuple):
                    return result[0] if result else None
                else:
                    logging.info(f"Result is not tuple or it's none{result}")
                    return result if result else None

    except Exception as e:
        logging.error(f"Failed to fetch item: {str(e)}")
        return None

async def fetch_item_class(item_class, item_id):
    try:
        if item_class is None or item_id is None:
            logging.error(f"Invalid parameters for fetch_item_class. item_id: {item_id}, item_class: {item_class}")
            return None        
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                if item_class in ('items', 'item'):
                    await cursor.execute("SELECT class FROM items WHERE id = %s", (item_id,))
                    result = await cursor.fetchone()
                    if result and isinstance(result, tuple) and result[0]:
                        return await fetch_item_class(result[0], item_id)
                    else:
                        logging.error(f"Failed to fetch item class from 'items' table for item_id: {item_id}")
                        return None
                elif item_class in ('Consumable', 'Ring', 'Amulet', 'Charm', 'items', 'item'):
                    await cursor.execute("SELECT class FROM items WHERE id = %s", (item_id,))
                    result = await cursor.fetchone()
                    if result is not None:
                        result = result[0]
                elif item_class == 'weapons' or item_class == 'weapon':
                    result = 'weapons'
                elif item_class == 'armour':
                    await cursor.execute("SELECT type FROM armour WHERE id = %s", (item_id,))
                    result = await cursor.fetchone()
                    if result is not None:
                        result = result[0]
                logging.info(f"Successfully fetched item type: {item_id} of class {item_class}")    
                return result

    except Exception as e:
        logging.error(f"Failed to fetch item: {str(e)}")
        return None

async def add_total_stats_to_embed(embed_message, total_stats):
    try:
        embed_message.add_field(name="Equipped and Base Stats", value=(
            f"- Equipped Strength: {total_stats['strength']}\n"
            f"- Equipped Agility: {total_stats['agility']}\n"
            f"- Equipped Intelligence: {total_stats['intelligence']}\n"
            f"- Equipped Stamina: {total_stats['stamina']}\n"
        ), inline=False)
    except Exception as e:
        logging.error(f"An error occurred while adding total stats to embed: {str(e)}")

async def add_health_and_mana_to_embed(embed_message, health_and_mana):
    try:
        embed_message.add_field(name="Health and Mana", value=(
            f"- Health: {health_and_mana['current_health']}/{health_and_mana['total_health']}\n"
            f"- Mana: {health_and_mana['current_mana']}/{health_and_mana['total_mana']}\n"
        ), inline=False)
    except Exception as e:
        logging.error(f"An error occurred while adding health and mana to embed: {str(e)}")

async def fetch_health_and_mana(ctx, cursor, discord_id, total_stats):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await conn.begin()  # Begin the transaction

                # Update total stats
                await cursor.execute("""
                    UPDATE player_inventory 
                    SET total_strength = %s, total_agility = %s, total_intelligence = %s, total_stamina = %s
                    WHERE discord_id = %s
                """, (total_stats['strength'], total_stats['agility'], total_stats['intelligence'], total_stats['stamina'], discord_id))

                # Calculate and update total health and mana
                total_health = total_stats['strength'] * HEALTH_PER_STRENGTH
                total_mana = total_stats['intelligence'] * MANA_PER_INTELLIGENCE

                await cursor.execute("""
                    UPDATE player_inventory 
                    SET total_health = %s, total_mana = %s
                    WHERE discord_id = %s
                """, (total_health, total_mana, discord_id))

                await conn.commit()  # Commit the transaction
                
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                # Fetch current health and mana from players
                await cursor.execute("""
                    SELECT current_health, current_mana 
                    FROM players 
                    WHERE discord_id = %s
                """, (discord_id,))
                results = await cursor.fetchone()

                if results:
                    current_health = results['current_health']
                    current_mana = results['current_mana']
                else:
                    logging.error(f"No matching entry for user with discord_id: {discord_id}")
                    await ctx.send("Could not find your stats in the player list. Please try again later.")
                    return None

                health_and_mana = {
                    'total_health': total_health,
                    'total_mana': total_mana,
                    'current_health': current_health,
                    'current_mana': current_mana,
                }

                return health_and_mana

    except Exception as e:
        logging.error(f"An error occurred while fetching health and mana: {str(e)}")
        await ctx.send("An error occurred while fetching your health and mana. Please try again later.")
        await conn.rollback()  # Rollback the transaction
        return None

async def calculate_mob_damage(mob_name, num_attacks):
    strength, intelligence, stamina = await get_entity_attributes(mob_name, "mobs")
    total_damage = strength * DAMAGE_PER_STRENGTH + intelligence * DAMAGE_PER_INTELLIGENCE

    if num_attacks > 0:
        reduction = 0.25 * num_attacks - (stamina * 0.0025/100)
        total_damage = total_damage * (1 - reduction)

    # truncate total_damage to an integer
    total_damage = int(total_damage)

    # Set a minimum damage
    total_damage = max(total_damage, 5)

    return total_damage

async def calculate_boss_damage(boss_name, num_attacks):
    strength, intelligence, stamina = await get_entity_attributes(boss_name, "bosses")
    total_damage = strength * DAMAGE_PER_STRENGTH + intelligence * DAMAGE_PER_INTELLIGENCE
    
    if num_attacks > 0:
        reduction = 0.25 * num_attacks - (stamina * 0.0025/100)
        total_damage = total_damage * (1 - reduction)

    # truncate total_damage to an integer
    total_damage = int(total_damage)

    # Set a minimum damage
    total_damage = max(total_damage, 5)

    return total_damage

async def calculate_player_damage(total_strength, total_intelligence, current_mana, stamina, num_attacks):
    logging.info(f"Dump Stamina: {stamina} and num_attacks: {num_attacks}")
    strength_damage = total_strength * DAMAGE_PER_STRENGTH
    logging.info(f"Strength damage: {strength_damage}")

    intelligence_damage = 0

    if current_mana >= 2:
        intelligence_damage = total_intelligence * DAMAGE_PER_INTELLIGENCE
        current_mana -= 2
        logging.info(f"Intelligence damage: {intelligence_damage}")

    total_damage = strength_damage + intelligence_damage
    logging.info(f"Total damage before reduction: {total_damage}")

    if num_attacks > 0:
        reduction = DEFAULT_AGILITY_REDUCTION * num_attacks - (stamina * 0.0025/100)
        total_damage = total_damage * (1 - reduction)
        logging.info(f"Reduction: {reduction}")
        logging.info(f"Total damage after reduction: {total_damage}")

    # truncate total_damage to an integer
    total_damage = int(total_damage)

    # Set a minimum damage
    total_damage = max(total_damage, 5)

    logging.info(f"Total damage after truncation and minimum damage enforcement: {total_damage}")

    return total_damage, current_mana

async def start_game(discord_id, thread):
    try:
        player_cooldowns[discord_id] = {'last_time': time.time()}
        await manage_thread_activity(discord_id, thread, active_threads)

        # Check if MYSQL is connected
        if pool is None:
            await ctx.send('The database cannot establish connection, please try again later')
            logging.error("MySQL connection is not active.")
            return

        if not await is_crown_wallet_online():
            await thread.send('The Crown wallet is currently offline. Please try again later.')
            return

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute("SELECT 1 FROM battles WHERE discord_id = %s AND battle_ended_at IS NULL LIMIT 1", (discord_id,))
                battle_info = await cursor.fetchone()

                if battle_info:
                    await handle_continue_mob_battle(discord_id, thread)
                    return

                await cursor.execute("SELECT tile_id FROM player_location WHERE discord_id = %s", (discord_id,))
                tile_id = await cursor.fetchone()

                if tile_id:
                    await cursor.execute("SELECT tile_name, area_name FROM map_tiles WHERE id = %s", (tile_id[0],))
                    tile_info = await cursor.fetchone()

                    if not tile_info:
                        await thread.send("Player data is incorrect, please contact @defunctec")
                        logging.info("No tile found for the player")
                        await conn.rollback()  # Rollback the transaction
                        return

                    tile_name, area_name = tile_info
                    embed = discord.Embed(
                        title=f"Continuing from {tile_name} in {area_name}",
                        description="Choose a direction to move:",
                        color=discord.Color.green()
                    )

                    if 'Residential Area' in tile_name:
                        embed.add_field(name="Left", value=":arrow_left:", inline=True)
                        embed.add_field(name="Right", value=":arrow_right:", inline=True)
                        embed.add_field(name="Storage", value=":house:", inline=True)
                    elif 'Town Center' in tile_name:
                        embed.add_field(name="Left", value=":arrow_left:", inline=True)
                        embed.add_field(name="Right", value=":arrow_right:", inline=True)
                        embed.add_field(name="Bank", value=":bank:", inline=True)
                    elif any(tile_name.endswith(market) for market in ('Marketplace', 'Black Market', 'Outpost Market')):
                        embed.add_field(name="Left", value=":arrow_left:", inline=True)
                        embed.add_field(name="Right", value=":arrow_right:", inline=True)
                        embed.add_field(name="Shop", value=":shopping_cart:", inline=True)
                    else:
                        embed.add_field(name="Left", value=":arrow_left:", inline=True)
                        embed.add_field(name="Right", value=":arrow_right:", inline=True)

                    message = await thread.send(embed=embed)
                    await message.add_reaction('⬅️')
                    await message.add_reaction('➡️')
                    if 'Residential Area' in tile_name:
                        await message.add_reaction('🏠')
                    elif 'Town Center' in tile_name:
                        await message.add_reaction('🏦')
                    elif any(tile_name.endswith(market) for market in ('Marketplace', 'Black Market', 'Outpost Market')):
                        await message.add_reaction('🛒')
                    return
                else:
                    await thread.send("Starting the game from the default tile and area")
                    logging.info(f"Starting the game from the default tile and area for player: {discord_id}")
                    return

    except Exception as e:
        logging.error(f"An error occurred while starting the game: {str(e)}")
        return

async def get_entity_attributes(entity_name, entity_type):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute(f"SELECT strength, intelligence, stamina FROM {entity_type} WHERE name = %s", (entity_name,))
                attributes = await cursor.fetchone()

                return attributes
    except Exception as e:
        logging.error(f"An error occurred while fetching entity attributes: {str(e)}")
        return None

async def is_player_in_battle(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute("SELECT COUNT(*) FROM battles WHERE discord_id = %s AND battle_ended_at IS NULL", (discord_id,))
                result = await cursor.fetchone()
                count = result[0]

                return count > 0
    except Exception as e:
        logging.error(f"An error occurred while checking player's battle status: {str(e)}")
        return False

# Function to handle spawning a boss for a player
async def handle_spawn_boss(discord_id, boss, thread):
    try:
        boss_stats = await get_boss_stats(boss['name'])
        if boss_stats is None:
            await thread.send(f"<@{discord_id}>, An error occurred getting boss stats. Please try again later.")
            logging.error(f"An error occurred getting boss stats for player: <@{discord_id}>")
            return

        player_stats = await get_player_stats_and_location(discord_id)
        if player_stats is None:
            await thread.send(f"<@{discord_id}>, An error occurred. Please try again later.")
            return

        boss_health = boss_stats['health']
        boss_dodge_chance = boss_stats['dodge_chance']
        strength = boss_stats['strength']
        agility = boss_stats['agility']
        intelligence = boss_stats['intelligence']
        stamina = boss_stats['stamina']

        current_health = player_stats['current_health']
        current_mana = player_stats['current_mana']
        player_dodge_chance = player_stats['player_dodge_chance']
        current_location = player_stats['current_location']
        total_strength = player_stats['total_strength']
        total_intelligence = player_stats['total_intelligence']
        total_stamina = player_stats['total_stamina']

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await conn.begin()  # Begin the transaction
                # Insert a new row into the battles table to track the battle
                battle_started_at = datetime.datetime.now()
                await cursor.execute("INSERT INTO battles (discord_id, opponent_name, opponent_type, opponent_health, opponent_dodge_chance, player_health, player_mana, player_dodge_chance, current_location, battle_started_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                    (discord_id, boss['name'], "boss", boss_health, boss_dodge_chance, current_health, current_mana, player_dodge_chance, current_location, battle_started_at))
                await conn.commit()

                # Create an embed message for the boss encounter
                embed = discord.Embed(
                    title=f"A {boss['name']} boss has appeared!",
                    description=f"Starting Health: {boss_health}\nStrength: {strength}\nAgility: {agility}\nIntelligence: {intelligence}\nStamina: {stamina}",
                    color=discord.Color.red()
                )

                message = await thread.send(embed=embed)

                num_attacks = 0
                num_mob_attacks = 0
                while True:
                    payload = await get_reaction_payload(bot, message, discord_id)
                    if payload is None:
                        logging.info(f"Issue getting payload")
                        return

                    # reaction handling
                    reaction_emoji = str(payload.emoji)
                    if reaction_emoji == '⚔️':
                        # Player's turn
                        player_damage, current_mana = await calculate_player_damage(total_strength, total_intelligence, current_mana, total_stamina, num_attacks)
                        # Increment the players attack count by 1 for staminia calculations
                        num_attacks += 1
                        if random.random() > boss_dodge_chance:
                            boss_health -= player_damage
                            try:
                                await conn.begin()  # Begin the transaction
                                await cursor.execute("UPDATE battles SET opponent_health = %s, player_mana = %s WHERE discord_id = %s AND battle_ended_at IS NULL",
                                                    (boss_health, current_mana, discord_id))
                                await cursor.execute("UPDATE players SET current_health = %s, current_mana = %s WHERE discord_id = %s",
                                                    (current_health, current_mana, discord_id))
                                await conn.commit()

                            except Exception as e:
                                logging.error(f"An error occurred while updating the battle in the database: {str(e)}")

                            await asyncio.sleep(1)
                            await thread.send(f"<@{discord_id}>, you attacked the boss for {player_damage} damage.")
                        else:
                            await asyncio.sleep(1)
                            await thread.send(f"The boss dodged your attack!")
                    elif reaction_emoji == '🔴':
                        current_health = await handle_health_potion_use(discord_id, current_health, thread)
                    elif reaction_emoji == '🔵':
                        current_mana = await handle_mana_potion_use(discord_id, current_mana, thread)
                    elif reaction_emoji == '📜':
                        teleport_success = await handle_teleport_scroll_use(discord_id, boss_health, current_health, current_mana, thread)
                        if teleport_success:
                            return
                    else:
                        logging.error(f"Unrecognized emoji reaction: {reaction_emoji}")

                    if boss_health <= 0:
                        await handle_boss_defeat(discord_id, current_health, current_mana, strength, intelligence, boss, current_location, thread)
                        return

                    # Boss's turn
                    boss_damage = await calculate_boss_damage(boss['name'], num_mob_attacks)
                    num_mob_attacks += 1
                    if random.random() > player_dodge_chance:
                        current_health -= boss_damage
                        try:
                            await conn.begin()  # Begin the transaction
                            await cursor.execute("UPDATE battles SET player_health = %s, player_mana = %s WHERE discord_id = %s AND battle_ended_at IS NULL",
                                                (current_health, current_mana, discord_id))
                            await cursor.execute("UPDATE players SET current_health = %s, current_mana = %s WHERE discord_id = %s",
                                                (current_health, current_mana, discord_id))
                            await conn.commit()
                        except Exception as e:
                            logging.error(f"An error occurred while updating the battle in the database: {str(e)}")
                            # Handle the error as needed

                        await asyncio.sleep(1)
                        await thread.send(f"<@{discord_id}>, the boss attacked you for {boss_damage} damage.")
                    else:
                        await asyncio.sleep(1)
                        await thread.send(f"You dodged the boss's attack!")

                    if current_health <= 0:
                        # Player defeated
                        if await handle_player_defeat(discord_id, boss['name'], boss_health, current_mana, current_location, thread) is True:
                            if current_location:
                                town_residential_area = await get_residential_area(current_location)
                                if town_residential_area:
                                    if await move_to_residential(discord_id, town_residential_area, thread) is True:
                                        return
                                else:
                                    await thread.send(f"<@{discord_id}>, An error occurred while determining the residential area.")
                                    logging.error(f"Error determining the residential area for player: {discord_id}")
                                    return
                            else:
                                await thread.send(f"<@{discord_id}>, An error occurred while retrieving current location.")
                                logging.error(f"Error retrieving current location for player: {discord_id}")
                                return

                    updated_embed = discord.Embed(
                        title=f"The {boss['name']} is still alive!",
                        description=f"Boss Health: {boss_health}\nPlayer Health: {current_health}\nPlayer Mana: {current_mana}",
                        color=discord.Color.red()
                    )

                    message = await thread.send(embed=updated_embed)

    except Exception as e:
        logging.error(f"An error occurred while spawning a boss for the player: {str(e)}")
        await thread.send(f"<@{discord_id}>, An error occurred while spawning a boss. Please try again later.")

async def spawn_mob(discord_id, mobs, thread):
    try:
        mob_name = random.choice(mobs)
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:

                # Fetch mob stats from the database
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute("SELECT id, strength, agility, intelligence, stamina FROM mobs WHERE name = %s", (mob_name,))
                mob_stats = await cursor.fetchone()
                if mob_stats:
                    id, strength, agility, intelligence, stamina = mob_stats
                    mob_health = strength * HEALTH_PER_STRENGTH
                    mob_dodge_chance = await calculate_dodge_chance(agility)

                    # Retrieve the player's current health and mana
                    player_stats = await get_player_stats_and_location(discord_id)
                    if player_stats is None:
                        await thread.send(f"<@{discord_id}>, An error occurred. Please try again later.")
                        return

                    current_health = player_stats['current_health']
                    current_mana = player_stats['current_mana']
                    player_dodge_chance = player_stats['player_dodge_chance']
                    current_location = player_stats['current_location']
                    total_strength = player_stats['total_strength']
                    total_intelligence = player_stats['total_intelligence']
                    total_stamina = player_stats['total_stamina']

                    battle_started_at = datetime.datetime.now()
                    successful_insert = await insert_into_battles(discord_id, mob_name, mob_health, mob_dodge_chance, current_health, current_mana, player_dodge_chance, current_location, battle_started_at)

                    if successful_insert:
                        logging.info(f"Battle for player {discord_id} inserted successfully!")
                    else:
                        logging.info(f"An error occurred while inserting battle for player {discord_id}.")
                        return

                    # Create an embed message for the mob encounter
                    embed = discord.Embed(
                        title=f"A {mob_name} has appeared!",
                        description=f"Starting Health : {mob_health}\nStrength: {strength}\nAgility: {agility}\nIntelligence: {intelligence}\nStamina: {stamina}",
                        color=discord.Color.red()
                    )

                    message = await thread.send(embed=embed)

                    num_attacks = 0
                    num_mob_attacks = 0
                    while True:
                        payload = await get_reaction_payload(bot, message, discord_id)
                        if payload is None:
                            logging.info(f"Issue getting payload")
                            return

                        # reaction handling
                        reaction_emoji = str(payload.emoji)
                        if reaction_emoji == '⚔️':
                            # Player's turn
                            player_damage, current_mana = await calculate_player_damage(total_strength, total_intelligence, current_mana, total_stamina, num_attacks)
                            # Increment the players attack count by 1 for staminia calculations
                            num_attacks += 1
                            if random.random() > mob_dodge_chance:
                                mob_health -= player_damage
                                try:
                                    successful_battles_update = await update_battles_health_and_mana(mob_health, current_mana, discord_id)
                                    if successful_battles_update:
                                        logging.info(f"Battle for player {discord_id} updated successfully!")
                                    else:
                                        logging.info(f"An error occurred while updating battle for player {discord_id}.")
                                        return

                                    successful_players_update = await update_players_health_and_mana(current_health, current_mana, discord_id)
                                    if successful_players_update:
                                        logging.info(f"Player {discord_id}'s health and mana was updated successfully!")
                                    else:
                                        logging.info(f"An error occurred while updating player {discord_id}.")
                                        return
                                except Exception as e:
                                    logging.error(f"An error occurred while updating the battle in the database: {str(e)}")
                                    # Handle the error as needed
                                await asyncio.sleep(1)
                                await thread.send(f"<@{discord_id}>, you attacked the mob for {player_damage} damage.")
                            else:
                                await asyncio.sleep(1)
                                await thread.send("The mob dodged your attack!")
                        elif reaction_emoji == '🔴':
                            current_health = await handle_health_potion_use(discord_id, current_health, thread)
                        elif reaction_emoji == '🔵':
                            current_mana = await handle_mana_potion_use(discord_id, current_mana, thread)
                        elif reaction_emoji == '📜':
                            teleport_success = await handle_teleport_scroll_use(discord_id, mob_health, current_health, current_mana, thread)
                            if teleport_success:
                                return
                        else:
                            logging.error(f"Unrecognized emoji reaction: {reaction_emoji}")

                        if mob_health <= 0:
                            await handle_mob_defeat(discord_id, mob_stats[0], mob_name, strength, intelligence, current_health, current_mana, current_location, thread)
                            return

                        # Mob's turn
                        mob_damage = await calculate_mob_damage(mob_name, num_mob_attacks)
                        num_mob_attacks += 1
                        if random.random() > player_dodge_chance:
                            current_health -= mob_damage
                            try:
                                await conn.begin()  # Begin the transaction
                                await cursor.execute("UPDATE battles SET player_health = %s WHERE discord_id = %s AND battle_ended_at IS NULL",
                                                        (current_health, discord_id))
                                await cursor.execute("UPDATE players SET current_health = %s WHERE discord_id = %s",
                                                        (current_health, discord_id))
                                await conn.commit()
                                
                            except Exception as e:
                                logging.error(f"An error occurred while updating the battle in the database: {str(e)}")
                                await conn.rollback()  # Rollback the transaction
                                # Handle the error as needed
                            await asyncio.sleep(1)
                            await thread.send(f"<@{discord_id}>, the mob attacked you for {mob_damage} damage.")
                        else:
                            await asyncio.sleep(1)
                            await thread.send("You dodged the mob's attack!")

                        if current_health <= 0:
                            # Player defeated
                            if await handle_player_defeat(discord_id, mob_name, mob_health, current_mana, current_location, thread) is True:
                                if current_location:
                                    town_residential_area = await get_residential_area(current_location)
                                    if town_residential_area:
                                        if await move_to_residential(discord_id, town_residential_area, thread) is True:
                                            return
                                    else:
                                        await thread.send(f"<@{discord_id}>, An error occurred while determining the residential area.")
                                        logging.error(f"Error determining the residential area for player: {discord_id}")
                                        return
                                else:
                                    await thread.send(f"<@{discord_id}>, An error occurred while retrieving current location.")
                                    logging.error(f"Error retrieving current location for player: {discord_id}")
                                    return


                        embed = discord.Embed(
                            title=f"The {mob_name} is still alive!",
                            description=f"Mob Health: {mob_health}\nPlayer Health: {current_health}\nPlayer Mana: {current_mana}",
                            color=discord.Color.red()
                        )

                        message = await thread.send(embed=embed)

                else:
                    logging.warning(f"Mob {mob_name} stats not found in the database.")
                    await thread.send(f"<@{discord_id}>, An error occurred. Please try again later.")
    except Exception as e:
        logging.error(f"An error occurred while spawning a mob for the player: {str(e)}")
        await thread.send(f"<@{discord_id}>, An error occurred while spawning a mob. Please try again later.")
    # Player Cooldown
    player_cooldowns[discord_id] = {'last_time': time.time()}
    # Start the timer to check for inactivity and delete the thread
    await manage_thread_activity(discord_id, thread, active_threads)

async def update_battles_health_and_mana(opponent_health, player_mana, discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await conn.begin()  # Begin the transaction
                await cursor.execute(
                    "UPDATE battles SET opponent_health = %s, player_mana = %s WHERE discord_id = %s AND battle_ended_at IS NULL",
                    (opponent_health, player_mana, discord_id)
                )
                await conn.commit()
                return True
    except Exception as e:
        logging.error(f"An error occurred while updating battles for player {discord_id}: {str(e)}")
        return False


async def update_players_health_and_mana(current_health, current_mana, discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await conn.begin()  # Begin the transaction
                await cursor.execute(
                    "UPDATE players SET current_health = %s, current_mana = %s WHERE discord_id = %s",
                    (current_health, current_mana, discord_id)
                )
                await conn.commit()
                return True
    except Exception as e:
        logging.error(f"An error occurred while updating players for player {discord_id}: {str(e)}")
        return False

async def insert_into_battles(discord_id, mob_name, mob_health, mob_dodge_chance, current_health, current_mana, player_dodge_chance, current_location, battle_started_at):
    try:
        logging.info(f"Inserting battle for player {discord_id}")
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:

                # Begin the transaction
                await conn.begin()
                await cursor.execute("INSERT INTO battles (discord_id, opponent_name, opponent_type, opponent_health, opponent_dodge_chance, player_health, player_mana, player_dodge_chance, current_location, battle_started_at) VALUES (%s, %s, 'mob', %s, %s, %s, %s, %s, %s, %s)",
                                     (discord_id, mob_name, mob_health, mob_dodge_chance, current_health, current_mana, player_dodge_chance, current_location, battle_started_at))

                # Commit the transaction
                await conn.commit()
                return True

    except Exception as e:
        logging.error(f"Transaction rolled back due to error.")
        logging.error(f"An error occurred while inserting battle for player {discord_id}: {str(e)}")
        return False


# Function to continue a mob battle for a player
async def handle_continue_mob_battle(discord_id, thread):
    logging.info(f"Starting handle_continue_mob_battle for discord_id {discord_id}")
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:

                try:
                    logging.info(f"Attempting to fetch battle data from database")
                    battle = await get_battle_from_db(discord_id)

                    if battle:
                        logging.info(f"Battle data fetched successfully for discord_id {discord_id}")

                        opponent_name = battle['opponent_name']
                        opponent_health = battle['opponent_health']
                        opponent_dodge_chance = battle['opponent_dodge_chance']
                        current_health = battle['player_health']
                        current_mana = battle['player_mana']
                        player_dodge_chance = battle['player_dodge_chance']
                        current_location = battle['current_location']
                        opponent_type = battle['opponent_type']

                        total_strength = await calculate_total_attribute(discord_id, 'strength')
                        total_intelligence = await calculate_total_attribute(discord_id, 'intelligence')
                        total_stamina = await calculate_total_attribute(discord_id, 'stamina')

                        num_attacks = 1
                        num_mob_attacks = 0
                        while current_health > 0:
                            await thread.send(f"<@{discord_id}>")

                            updated_embed = discord.Embed(
                                title=f"The {opponent_name} is still alive!",
                                description=f"{opponent_name}'s Health: {opponent_health}\nPlayer Health: {current_health}\nPlayer Mana: {current_mana}",
                                color=discord.Color.red()
                            )

                            message = await thread.send(embed=updated_embed)
                            payload = await get_reaction_payload(bot, message, discord_id)
                            if payload is None:
                                logging.warning(f"No reaction payload received for discord_id {discord_id}")
                                return

                            reaction_emoji = str(payload.emoji)

                            if reaction_emoji == '⚔️':
                                opponent_health, current_mana = await player_attack(discord_id, opponent_name, opponent_health, total_strength, total_intelligence, current_mana, opponent_dodge_chance, thread, total_stamina, num_attacks)
                                num_attacks += 1
                            elif reaction_emoji == '🔴':
                                current_health = await handle_health_potion_use(discord_id, current_health, thread)
                            elif reaction_emoji == '🔵':
                                current_mana = await handle_mana_potion_use(discord_id, current_mana, thread)
                            elif reaction_emoji == '📜':
                                teleport_success = await handle_teleport_scroll_use(discord_id, opponent_health, current_health, current_mana, thread)
                                if teleport_success:
                                    logging.info(f"Teleport successful for discord_id {discord_id}")
                                    return
                            else:
                                logging.error(f"Unrecognized emoji reaction: {reaction_emoji}")

                            if opponent_health <= 0:
                                logging.info(f"Opponent defeated by discord_id {discord_id}")
                                battle_ended_at = datetime.datetime.now()
                                await update_battle_in_db(discord_id, opponent_health, current_health, current_mana, battle_ended_at)

                                try:
                                    await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                                    await cursor.execute(
                                        "SELECT id, strength, intelligence, 'boss' AS table_name FROM bosses WHERE name = %s "
                                        "UNION "
                                        "SELECT id, strength, intelligence, 'mob' AS table_name FROM mobs WHERE name = %s",
                                        (opponent_name, opponent_name)
                                    )
                                    mob_stats = await cursor.fetchone()

                                    if mob_stats:
                                        id, strength, intelligence, table_name = mob_stats
                                except Exception as e:
                                    logging.error(f"An error occurred while updating the battle in the database: {str(e)}")

                                experience_gained = strength + intelligence
                                gold_gained = strength * random.randint(MIN_GOLD_PER_STRENGTH, MAX_GOLD_PER_STRENGTH)
                                items_dropped = await drop_items(opponent_type, current_location)
                                if await record_player_mob_kill(discord_id, id, table_name, battle_ended_at, experience_gained, gold_gained, items_dropped, thread) is True:
                                    if table_name == 'boss':
                                        logging.info(f"Boss defeated by discord_id {discord_id}")
                                        await thread.send(f"<@{discord_id}>, You have defeated the boss {opponent_name} and gained {experience_gained} XP and {gold_gained} Gold!")
                                        try:
                                            # Check the player's level after the mob kill
                                            result = await check_player_level(discord_id)
                                            if result is True:
                                                await thread.send(f"<@{discord_id}>, Congratulations, you leveled up!")
                                            elif result is None:
                                                pass
                                            else:
                                                await thread.send(f"<@{discord_id}>, {result}")

                                        except Exception as e:
                                            logging.error("Error occurred while checking player level: %s", e)
                                            return False

                                        if items_dropped is not None:
                                            await handle_item_drop(discord_id, items_dropped, thread)
                                    elif table_name == 'mob':
                                        logging.info(f"Mob defeated by discord_id {discord_id}")
                                        await thread.send(f"<@{discord_id}>, You have defeated the mob {opponent_name} and gained {experience_gained} XP and {gold_gained} Gold!")
                                        try:
                                            # Check the player's level after the mob kill
                                            result = await check_player_level(discord_id)
                                            if result is True:
                                                await thread.send(f"<@{discord_id}>, Congratulations, you leveled up!")
                                            elif result is None:
                                                pass
                                            else:
                                                await thread.send(f"<@{discord_id}>, {result}")

                                        except Exception as e:
                                            logging.error("Error occurred while checking player level: %s", e)
                                            return False
                                        
                                        if items_dropped is not None:
                                            await handle_item_drop(discord_id, items_dropped, thread)
                                    await start_game(discord_id, thread)
                                    return

                            if opponent_name in ['Night Whisper', 'Steel Behemoth', 'Deepmaw', 'Mistweaver', 'Cinderbound']:
                                opponent_damage = await calculate_boss_damage(opponent_name)
                                num_mob_attacks += 1
                            else:
                                opponent_damage = await calculate_mob_damage(opponent_name, num_mob_attacks)
                                num_mob_attacks += 1
                            if random.random() > player_dodge_chance:
                                current_health -= opponent_damage
                                try:
                                    await conn.begin()  # Begin the transaction

                                    await cursor.execute(
                                        "UPDATE battles SET player_health = %s, player_mana = %s WHERE discord_id = %s AND battle_ended_at IS NULL",
                                        (current_health, current_mana, discord_id)
                                    )
                                    await cursor.execute(
                                        "UPDATE players SET current_health = %s, current_mana = %s WHERE discord_id = %s",
                                        (current_health, current_mana, discord_id)
                                    )
                                    await conn.commit()  # Begin the transaction
                                    logging.info(f"Updated player health in the database: {current_health}")
                                except Exception as e:
                                    logging.error(f"An error occurred while updating the battle in the database: {str(e)}")
                                    await conn.rollback()  # Begin the transaction

                                await thread.send(f"<@{discord_id}>, the {opponent_name} attacked you for {opponent_damage} damage.")
                            else:
                                await thread.send(f"You dodged the {opponent_name}'s attack!")

                            if current_health <= 0:
                                logging.info(f"Player health is 0 or less. Handling player defeat.")
                                if await handle_player_defeat(discord_id, opponent_name, opponent_health, current_mana, current_location, thread) is True:
                                    if current_location:
                                        town_residential_area = await get_residential_area(current_location)
                                        if town_residential_area:
                                            if await move_to_residential(discord_id, town_residential_area, thread) is True:
                                                return
                                        else:
                                            await thread.send(f"<@{discord_id}>, An error occurred while determining the residential area.")
                                            logging.error(f"Error determining the residential area for player: {discord_id}")
                                            return
                                    else:
                                        await thread.send(f"<@{discord_id}>, An error occurred while retrieving current location.")
                                        logging.error(f"Error retrieving current location for player: {discord_id}")
                                        return
                    else:
                        logging.warning(f"Battle for Discord ID {discord_id} not found in the database.")
                        await thread.send(f"<@{discord_id}>, An error occurred. Please try again later.")

                except Exception as e:
                    logging.error(f"An error occurred while continuing the battle: {str(e)}")
                    await thread.send(f"<@{discord_id}>, An error occurred while continuing the battle. Please try again later.")

                await conn.commit()  # Commit the transaction

    except Exception as e:
        logging.error(f"An error occurred while continuing the battle: {str(e)}")
        await thread.send(f"<@{discord_id}>, An error occurred while continuing the battle. Please try again later.")

async def player_attack(discord_id, opponent_name, opponent_health, total_strength, total_intelligence, current_mana, opponent_dodge_chance, thread, stamina, num_attacks):
    player_damage, current_mana = await calculate_player_damage(total_strength, total_intelligence, current_mana, stamina, num_attacks)
    if random.random() > opponent_dodge_chance:
        opponent_health -= player_damage
        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await conn.begin()  # Begin the transaction
                    await cursor.execute("UPDATE battles SET opponent_health = %s, player_mana = %s WHERE discord_id = %s AND battle_ended_at IS NULL",
                               (opponent_health, current_mana, discord_id))
                    await conn.commit()  # Commit the transaction
        except Exception as e:
            logging.error(f"An error occurred while updating the battle in the database: {str(e)}")
            # Handle the error as needed
        await thread.send(f"<@{discord_id}>, you attacked the {opponent_name} for {player_damage} damage.")
    else:
        await thread.send(f"The {opponent_name} dodged your attack!")
    
    return opponent_health, current_mana

# Function to handle player cast spell
async def player_cast_spell(discord_id, opponent_name, opponent_health, total_strength, total_intelligence, current_mana, opponent_dodge_chance, thread):
    # Implement player spell casting logic here
    await thread.send(f"<@{discord_id}>, you cast a powerful spell.")
    return opponent_health, current_mana

async def get_battle_from_db(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                # Query the ongoing battle for the user
                await cursor.execute("""
                    SELECT *
                    FROM battles
                    WHERE discord_id = %s AND battle_ended_at IS NULL
                """, (discord_id,))

                battle = await cursor.fetchone()

                if battle:
                    return battle
                else:
                    return None

    except Exception as e:
        logging.error(f"An error occurred while retrieving the battle from the database: {str(e)}")

    return None

async def update_battle_in_db(discord_id, opponent_health, player_health, player_mana, battle_ended_at):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await conn.begin()  # Begin the transaction
                
                # Update the ongoing battle for the user
                await cursor.execute("""
                    UPDATE battles
                    SET opponent_health = %s, player_health = %s, player_mana = %s, battle_ended_at = %s
                    WHERE discord_id = %s AND battle_ended_at IS NULL
                """, (opponent_health, player_health, player_mana, battle_ended_at, discord_id))

                logging.info(f"Battle updated in the battles table for discord_id: {discord_id}")

                # Update the current_health for the user in players table
                await cursor.execute("""
                    UPDATE players
                    SET current_health = %s, current_mana = %s
                    WHERE discord_id = %s
                """, (player_health, player_mana, discord_id))

                logging.info(f"Player status updated in the players table for discord_id: {discord_id}")

                await conn.commit()
                return True

    except Exception as e:
        logging.error(f"An error occurred while updating the battle in the database: {str(e)}")
        await conn.rollback()
        logging.error(f"Transaction rolled back due to error for discord_id: {discord_id}")
        return False

async def get_boss_stats(boss_name):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute("SELECT id, strength, agility, intelligence, stamina FROM bosses WHERE name = %s", (boss_name,))
                boss_stats = await cursor.fetchone()

                if boss_stats:
                    id, strength, agility, intelligence, stamina = boss_stats

                    boss_health = strength * HEALTH_PER_STRENGTH

                    boss_dodge_chance = await calculate_dodge_chance(agility)

                    return {
                        "id": id,
                        "strength": strength,
                        "agility": agility,
                        "intelligence": intelligence,
                        "stamina": stamina,
                        "health": boss_health,
                        "dodge_chance": boss_dodge_chance
                    }
                else:
                    logging.warning(f"Boss {boss_name} stats not found in the database.")
                    return None

    except Exception as e:
        logging.error(f"An error occurred while fetching boss stats from the database: {str(e)}")
        return None

async def calculate_total_attribute(discord_id, attribute):
    equipped_item_columns = ["equipped_weapon_id", "equipped_amulet_id",
                             "equipped_ring1_id", "equipped_ring2_id", "equipped_charm_id"]
    equipped_armour_columns = ["equipped_helmet_id", "equipped_chest_id", "equipped_legs_id", "equipped_feet_id"]

    total_attribute = 0

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                # Check if the player has an inventory entry
                await cursor.execute("SELECT * FROM player_inventory WHERE discord_id = %s", (discord_id,))
                player_inventory = await cursor.fetchone()

                if player_inventory:
                    # Fetch all equipped items (excluding weapons) and armours
                    await cursor.execute(f"SELECT {', '.join(equipped_item_columns[1:])} FROM player_inventory WHERE discord_id = %s", (discord_id,))
                    equipped_items = await cursor.fetchone()

                    await cursor.execute(f"SELECT {', '.join(equipped_armour_columns)} FROM player_inventory WHERE discord_id = %s", (discord_id,))
                    equipped_armours = await cursor.fetchone()

                    # Check if equipped items exist before running the loop
                    if equipped_items:
                        # For each equipped item, add its attribute to total_attribute
                        for item_id in equipped_items:
                            if item_id is not None:
                                await cursor.execute(f"SELECT {attribute} FROM items WHERE id = %s", (item_id,))
                                item_attribute_result = await cursor.fetchone()
                                item_attribute = item_attribute_result[0] if item_attribute_result and item_attribute_result[0] is not None else 0
                                total_attribute += item_attribute

                    # Check if equipped armours exist before running the loop
                    if equipped_armours:
                        # For each equipped armour, add its attribute to total_attribute
                        for armour_id in equipped_armours:
                            if armour_id is not None:
                                await cursor.execute(f"SELECT {attribute} FROM armour WHERE id = %s", (armour_id,))
                                armour_attribute_result = await cursor.fetchone()
                                armour_attribute = armour_attribute_result[0] if armour_attribute_result and armour_attribute_result[0] is not None else 0
                                total_attribute += armour_attribute

                    # Fetch the equipped weapon id
                    await cursor.execute("SELECT equipped_weapon_id FROM player_inventory WHERE discord_id = %s", (discord_id,))
                    equipped_weapon_id_result = await cursor.fetchone()

                    # Check if the player has a weapon equipped
                    if equipped_weapon_id_result:
                        equipped_weapon_id = equipped_weapon_id_result[0]

                        # If a weapon is equipped, add its attribute to total_attribute
                        if equipped_weapon_id is not None:
                            await cursor.execute(f"SELECT {attribute} FROM weapons WHERE id = %s", (equipped_weapon_id,))
                            weapon_attribute_result = await cursor.fetchone()
                            weapon_attribute = weapon_attribute_result[0] if weapon_attribute_result and weapon_attribute_result[0] is not None else 0
                            total_attribute += weapon_attribute

                await cursor.execute(f"SELECT {attribute} FROM player_attributes WHERE discord_id = %s", (discord_id,))
                base_attribute_result = await cursor.fetchone()
                base_attribute = base_attribute_result[0] if base_attribute_result and base_attribute_result[0] is not None else 0

                if player_inventory:
                    return total_attribute + base_attribute
                else:
                    logging.info(f"Returning base {attribute} for player {discord_id} as no inventory entry found")
                    return base_attribute

    except Exception as e:
        logging.error("Transaction rolled back due to error.")
        logging.error(f"An error occurred while calculating total attribute for player {discord_id}: {str(e)}")
        return None

async def get_player_stats_and_location(discord_id):
    # Fetch player stats from the database, calculate total attributes and get current location
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:

                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute("SELECT current_health, current_mana FROM players WHERE discord_id = %s", (discord_id,))
                player_stats = await cursor.fetchone()

                if player_stats:
                    current_health, current_mana = player_stats

                    total_strength = await calculate_total_attribute(discord_id, 'strength')
                    total_intelligence = await calculate_total_attribute(discord_id, 'intelligence')
                    total_agility = await calculate_total_attribute(discord_id, 'agility')
                    total_stamina = await calculate_total_attribute(discord_id, 'stamina')

                    # Calculate player dodge chance
                    player_dodge_chance = await calculate_dodge_chance(total_agility)
                    logging.info(f"Calculated dodge chance for {discord_id}: {player_dodge_chance}")

                    # Get player location
                    current_location = await get_player_location(discord_id)

                    return {
                        "current_health": current_health,
                        "current_mana": current_mana,
                        "total_strength": total_strength,
                        "total_intelligence": total_intelligence,
                        "total_agility": total_agility,
                        "total_stamina": total_stamina,
                        "player_dodge_chance": player_dodge_chance,
                        "current_location": current_location
                    }
                else:
                    logging.warning(f"No player stats found for {discord_id}. Defaulting health and mana to 0.")
                    # Default values if player's stats are not found
                    return {
                        "current_health": 0,
                        "current_mana": 0,
                    }


    except Exception as e:
        exception_type, exception_value, exception_traceback = sys.exc_info()
        traceback_string = traceback.format_exception(exception_type, exception_value, exception_traceback)
        logging.error(f"An error occurred while fetching player stats from the database: {str(e)}")
        logging.error(f"Traceback: {''.join(traceback_string)}")
        return None

async def handle_boss_defeat(discord_id, current_health, current_mana, strength, intelligence, boss, current_location, thread):
    logging.info(f"Attempting to get Boss details from property: {boss}")
    try:
        battle_ended_at = datetime.datetime.now()
        await update_battle_in_db(discord_id, 0, current_health, current_mana, battle_ended_at)
        experience_gained = strength + intelligence
        gold_gained = strength * random.randint(MIN_GOLD_PER_STRENGTH, MAX_GOLD_PER_STRENGTH)
        items_dropped = await drop_items('boss', current_location)

        if await record_player_mob_kill(discord_id, boss['id'], 'boss', battle_ended_at, experience_gained, gold_gained, items_dropped, thread) is True:
            
            await thread.send(f"<@{discord_id}>, You have defeated {boss['name']} and gained {experience_gained} XP and {gold_gained} Gold!")
            try:
                # Check the player's level after the mob kill
                result = await check_player_level(discord_id)
                if result is True:
                    await thread.send(f"<@{discord_id}>, Congratulations, you leveled up!")
                elif result is None:
                    pass
                else:
                    await thread.send(f"<@{discord_id}>, {result}")

            except Exception as e:
                logging.error("Error occurred while checking player level: %s", e)
                return False

            if items_dropped is not None:
                await handle_item_drop(discord_id, items_dropped, thread)
            await start_game(discord_id, thread)
        else:
            logging.error(f"Could not record player's defeat of boss {boss['name']}")
            await thread.send(f"<@{discord_id}>, there was an error recording your victory. Please contact an admin.")

    except Exception as e:
        logging.error(f"An error occurred while handling boss defeat: {str(e)}")
        await thread.send(f"<@{discord_id}>, An error occurred. Please try again later.")

async def handle_mob_defeat(discord_id, mob_id, mob_name, strength, intelligence, current_health, current_mana, current_location, thread):
    # Mob defeated
    battle_ended_at = datetime.datetime.now()
    await update_battle_in_db(discord_id, 0, current_health, current_mana, battle_ended_at)

    experience_gained = strength + intelligence
    gold_gained = strength * random.randint(MIN_GOLD_PER_STRENGTH, MAX_GOLD_PER_STRENGTH)
    items_dropped = await drop_items('mob', current_location)

    if await record_player_mob_kill(discord_id, mob_id, 'mob', battle_ended_at, experience_gained, gold_gained, items_dropped, thread) is True:
        await thread.send(f"<@{discord_id}>, You have defeated {mob_name} and gained {experience_gained} XP and {gold_gained} Gold!")
        try:
            # Check the player's level after the mob kill
            result = await check_player_level(discord_id)
            if result is True:
                await thread.send(f"<@{discord_id}>, Congratulations, you leveled up!")
            elif result is None:
                pass
            else:
                await thread.send(f"<@{discord_id}>, {result}")

        except Exception as e:
            logging.error("Error occurred while checking player level: %s", e)
            return False

        if items_dropped is not None:
            await handle_item_drop(discord_id, items_dropped, thread)
        await start_game(discord_id, thread)

async def handle_player_defeat(discord_id, opponent_name, opponent_health, current_mana, current_location, thread):
    battle_ended_at = datetime.datetime.now()

    # Update the battle status and player's current health in a single transaction
    await update_battle_in_db(discord_id, opponent_health, 0, current_mana, battle_ended_at)

    # Nullify the player's inventory slots
    await nullify_inventory_slots(discord_id)
    await reset_player_gold(discord_id)
    logging.info(f"Player's inventory slots and gold wiped for player: {discord_id}")

    await thread.send(f"<@{discord_id}>, You were defeated by {opponent_name}!")

    await thread.send("Your health is currently at 0, reviving...")
    await asyncio.sleep(1)

    if await calculate_base_health_and_mana(discord_id) is True:
        if await recalculate_player_inventory_attributes(discord_id) is True:
            if await update_current_health_and_mana(discord_id) is True:
                logging.info(f"Updated current health and mana")
                await thread.send("Your health and mana are fully restored, back to battle!")
                return True
            else:
                logging.error("Error updating health and mana for player {discord_id}")
        else:
            logging.error("Error recalculating base health and mana for player {discord_id}")
    else:
        logging.error("Error calculating base health and mana for player {discord_id}")

    return

async def handle_health_potion_use(discord_id, current_health, thread):
    heal_result, total_health = await use_health_potion(discord_id)
    if heal_result == "success":
        current_health = total_health
        await asyncio.sleep(1)
        await thread.send(f"You used a health potion. Your health has been fully restored to {total_health}!")
    else:
        await asyncio.sleep(1)
        await thread.send(heal_result)
    return current_health

async def handle_mana_potion_use(discord_id, current_mana, thread):
    mana_result, total_mana = await use_mana_potion(discord_id)
    if mana_result == "success":
        current_mana = total_mana
        await asyncio.sleep(1)
        await thread.send(f"You used a mana potion. Your mana has been fully restored to {total_mana}!")
    else:
        await asyncio.sleep(1)
        await thread.send(mana_result)
    return current_mana

async def handle_teleport_scroll_use(discord_id, opponent_health, current_health, current_mana, thread):
    teleport_result = await use_teleport_scroll(discord_id, thread)
    if teleport_result == "success":
        battle_ended_at = datetime.datetime.now()
        await update_battle_in_db(discord_id, opponent_health, current_health, current_mana, battle_ended_at)
        await asyncio.sleep(1)
        await thread.send("You used a teleport scroll. You have been teleported to your last residential tile!")
        return True
    else:
        await asyncio.sleep(1)
        await thread.send(teleport_result)
        return False

async def nullify_inventory_slots(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await conn.begin()  # Begin the transaction
                # Update the player's inventory slots to null values
                update_query = "UPDATE player_inventory SET " \
                               "item_slot1_id = NULL, item_slot1_class = NULL, " \
                               "item_slot2_id = NULL, item_slot2_class = NULL, " \
                               "item_slot3_id = NULL, item_slot3_class = NULL, " \
                               "item_slot4_id = NULL, item_slot4_class = NULL, " \
                               "item_slot5_id = NULL, item_slot5_class = NULL, " \
                               "item_slot6_id = NULL, item_slot6_class = NULL, " \
                               "item_slot7_id = NULL, item_slot7_class = NULL, " \
                               "item_slot8_id = NULL, item_slot8_class = NULL " \
                               "WHERE discord_id = %s"
                await cursor.execute(update_query, (discord_id,))

                # Commit the changes to the database
                await conn.commit()

                logging.info(f"Inventory slots nullified for player: {discord_id}")
                return
    except Exception as e:
        # Rollback the transaction in case of an error
        await conn.rollback()
        logging.error(f"An error occurred while nullifying inventory slots: {str(e)}")

async def reset_player_gold(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await conn.begin()  # Begin the transaction
                # Update the player's current gold to 0
                update_query = "UPDATE players SET current_gold = 0 WHERE discord_id = %s"
                await cursor.execute(update_query, (discord_id,))
                
                # Commit the changes to the database
                await conn.commit()

                logging.info(f"Player's gold reset to 0 for player: {discord_id}")
                return
    except Exception as e:
        # Rollback the transaction in case of an error
        await conn.rollback()
        logging.error(f"An error occurred while resetting player's gold: {str(e)}")

async def pick_up_item(discord_id, item_id, item_name):
    logging.info(f"Attempting to pick up item {item_id} ({item_name}) for discord_id: {discord_id}")
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                # Retrieve the player's inventory
                await cursor.execute("SELECT * FROM player_inventory WHERE discord_id = %s", (discord_id,))
                player_inventory = await cursor.fetchone()

                # Check if there are any free slots in the player's inventory
                if player_inventory:
                    free_slot = None
                    for slot in range(1, 9):
                        item_id_field = f"item_slot{slot}_id"
                        item_class_field = f"item_slot{slot}_class"
                        if player_inventory[item_id_field] is None:
                            free_slot = slot
                            break

                    if free_slot:
                        await conn.begin()  # Begin the transaction
                        # Update the player's inventory with the picked up item
                        update_query = f"UPDATE player_inventory SET item_slot{free_slot}_id = %s, item_slot{free_slot}_class = %s WHERE discord_id = %s"
                        values = (item_id, item_name, discord_id)
                        await cursor.execute(update_query, values)

                        # Commit the changes to the database
                        await conn.commit()

                        logging.info(f"Successfully picked up item {item_id} ({item_name}) for discord_id: {discord_id}")
                        return True  # Item successfully picked up
                    else:
                        logging.info(f"No free slots in the inventory for discord_id: {discord_id}")
                        return False  # No free slots in the inventory

    except Exception as e:
        logging.error(f"An error occurred while picking up the item: {str(e)}")

    logging.info(f"Failed to pick up item {item_id} ({item_name}) for discord_id: {discord_id}")
    return False  # Error occurred while picking up the item

async def handle_item_drop(discord_id, items_dropped, thread):
    if items_dropped is not None:
        try:
            table_queries = {
                'items': "SELECT id, class FROM items WHERE name = %s",
                'weapons': "SELECT id, class FROM weapons WHERE name = %s",
                'armour': "SELECT id, class FROM armour WHERE name = %s"
            }

            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    
                    await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                    for table, query in table_queries.items():
                        await cursor.execute(query, (items_dropped,))
                        result = await cursor.fetchone()
                        await cursor.fetchall()  # Discard any remaining rows

                        if result:
                            item_id = result['id']
                            item_class = result['class']

            # Create an embed message with interactive emotes
            embed_message = discord.Embed(
                title="Dropped Item",
                description=f"{items_dropped}\n\nDo you want to pick up the item?",
                color=discord.Color.gold()
            )
            message = await thread.send(embed=embed_message)
            await message.add_reaction('✅')  # Emote for picking up the item
            await message.add_reaction('❎')  # Emote for discarding the item

            # Define the check function to filter the interaction
            def check(reaction, user):
                return (
                    user.id == discord_id
                    and reaction.message.id == message.id
                    and str(reaction.emoji) in ['✅', '❎']
                )

            # Wait for the player's reaction for 60 seconds
            reaction, _ = await bot.wait_for('reaction_add', check=check, timeout=60.0)

            # Handle the player's choice
            if str(reaction.emoji) == '✅':
                # Player chose to pick up the item
                success = await pick_up_item(discord_id, item_id, item_class)
                if success:
                    await thread.send(f"<@{discord_id}>, You picked up the {items_dropped}")
                    return
                else:
                    await thread.send(f"<@{discord_id}>, Your inventory is full. You cannot pick up the item.")
                    return

            elif str(reaction.emoji) == '❎':
                await thread.send(f"<@{discord_id}>, You discarded the {items_dropped}")
                return
            else:
                # Player didn't react within the timeout or reacted with an invalid emote
                await thread.send(f"<@{discord_id}>, You didn't pick up the item.")
                return

        except Exception as e:
            logging.error(f"An error occurred while searching for the item ID: {str(e)}")

    return False

async def check_res_storage(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # Retrieve the player's residential storage
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute("SELECT * FROM residential_storage WHERE discord_id = %s", (discord_id,))
                residential_storage = await cursor.fetchone()

                # Check if there is residential storage available
                if residential_storage is None:
                    logging.info(f"No residential storage for user {discord_id}")
                    return False  # No residential storage for the user

    except Exception as e:
        logging.error(f"An error occurred while checking residential storage: {str(e)}")

    return True  # Residential storage is available

async def add_item_to_storage(discord_id, item_id, item_class, item_id_column, item_class_column):
    try:
        # Check if there is residential storage available
        if not await check_res_storage(discord_id):
            return False

        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:

                # Retrieve the player's residential storage
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                await cursor.execute("SELECT * FROM residential_storage WHERE discord_id = %s", (discord_id,))
                residential_storage = await cursor.fetchone()

                free_slot = None
                for slot in range(1, 9):
                    item_id_field = f"item_slot{slot}_id"
                    item_class_field = f"item_slot{slot}_class"
                    if residential_storage[item_id_field] is None:
                        free_slot = slot
                        break

                if free_slot:
                    await conn.begin()  # Begin the transaction
                    update_query = f"UPDATE residential_storage SET item_slot{free_slot}_id = %s, item_slot{free_slot}_class = %s WHERE discord_id = %s"
                    values = (item_id, item_class, discord_id)
                    await cursor.execute(update_query, values)

                    # Update the player's inventory to remove the deposited item
                    item_class_column = item_id_column.replace("_id", "_class")
                    inventory_update_query = f"UPDATE player_inventory SET {item_id_column} = NULL, {item_class_column} = NULL WHERE discord_id = %s"
                    await cursor.execute(inventory_update_query, (discord_id,))
                    logging.info(f"Removed item (ID: {item_id}, Class: {item_class}) from inventory {discord_id}")

                    # Commit the changes to the database
                    await conn.commit()

                    logging.info("Item successfully added to the storage")
                    return True  # Item successfully added to the storage
                else:
                    logging.info(f"No free slots in the residential storage for user {discord_id}")
                    return False  # No free slots in the residential storage

    except Exception as e:
        # Rollback the transaction in case of any error
        await conn.rollback()
        logging.error(f"An error occurred while adding the item to the storage: {str(e)}")

    return False  # Error occurred while adding the item to the storage

async def record_player_mob_kill(discord_id, mob_id, mob_type, kill_date, experience_gained, gold_gained, items_dropped, thread):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await conn.begin()  # Begin the transaction

                # Execute the SQL statements to insert a new player mob kill and update xp
                sql_insert = "INSERT INTO player_mob_kills (discord_id, mob_id, mob_type, kill_date, experience_gained, items_dropped) VALUES (%s, %s, %s, %s, %s, %s)"
                values_insert = (discord_id, mob_id, mob_type, kill_date, experience_gained, items_dropped)
                await cursor.execute(sql_insert, values_insert)

                sql_update = "UPDATE player_attributes SET xp = xp + %s WHERE discord_id = %s"
                values_update = (experience_gained, discord_id)
                await cursor.execute(sql_update, values_update)

                sql_update = "UPDATE players SET current_gold = current_gold + %s WHERE discord_id = %s"
                gold_values_update = (gold_gained, discord_id)
                await cursor.execute(sql_update, gold_values_update)

                await conn.commit()
                logging.info(f"Recording mob kill successful for player: {discord_id}")
                return True

    except Exception as e:
        logging.error("Error occurred while executing SQL statement: %s", e)
        await conn.rollback()  # Rollback the transaction
        return False

async def check_player_level(discord_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Retrieve the player's XP and current level from the player_attributes table
                await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                sql_select = "SELECT xp, level FROM player_attributes WHERE discord_id = %s"
                await cursor.execute(sql_select, (discord_id,))
                resultAtt = await cursor.fetchone()

                if resultAtt:
                    xp = resultAtt[0]
                    current_level = resultAtt[1]
                else:
                    return "Player not found in the database."

                # Define the level thresholds and corresponding XP values
                level_thresholds = {
                    1: 0,
                    2: 20,
                    3: 50,
                    4: 150,
                    5: 350,
                    6: 750,
                    7: 1000,
                    8: 1500,
                    9: 2000,
                    10: 3000,
                    11: 4000,
                    12: 5500,
                    13: 7500,
                    14: 10000,
                    15: 13000,
                    16: 17000,
                    17: 22000,
                    18: 28000,
                    19: 35000,
                    20: 43000,
                }

                # Find the highest level threshold that the player's XP exceeds
                player_level = current_level
                for level, threshold in level_thresholds.items():
                    if xp >= threshold:
                        player_level = level
                    else:
                        break

                # Check if the player has ranked up or leveled up
                if player_level > current_level:
                    # Check if the player has reached level 20
                    if player_level == 10:
                        # Check if the boss kill has been recorded in player_mob_kills table
                        sql_check_boss_kill = "SELECT * FROM player_mob_kills WHERE discord_id = %s AND mob_type = %s AND mob_id = %s"
                        values_check_boss_kill = (discord_id, "Boss", 1)  # Replace boss_id with the actual boss ID
                        await cursor.execute(sql_check_boss_kill, values_check_boss_kill)
                        result = await cursor.fetchone()
                        if not result:
                            return "You have not yet defeated the boss! You cannot progress beyond level 10."
                    
                    await conn.begin()  # Begin the transaction
                    # Update the player's level and attribute stats in the database
                    sql_update = "UPDATE player_attributes SET level = %s, strength = strength + %s, agility = agility + %s, intelligence = intelligence + %s, stamina = stamina + %s WHERE discord_id = %s"
                    attribute_increases = (1, 2, 1, 2)  # Specify the attribute increases for each level up
                    values_update = (player_level, *attribute_increases, discord_id)
                    await cursor.execute(sql_update, values_update)

                    await conn.commit()
                    logging.info(f"Player attributes added after level up")
                    if await calculate_base_health_and_mana(discord_id) is True:
                        logging.info(f"Calculated health and mana after level up for: {discord_id}")
                        return True
                    else:
                        logging.error(f"Issue calculating health and mana after level up for: {discord_id}")
                        return "There was a problem calculating health and mana after leveling up."
                else:
                    next_level = current_level + 1
                    next_level_xp = level_thresholds.get(next_level, "Max level reached")

                    if next_level_xp != "Max level reached":
                        xp_to_next_level = next_level_xp - xp
                        return f"You are currently level {current_level} with {xp} XP. You need {xp_to_next_level} more XP to reach level {next_level}."
                    else:
                        return f"Congratulations! You have reached the max level ({current_level}) with {xp} XP."
    except Exception as e:
        logging.error("Error occurred while checking player level: %s", e)


async def drop_items(mob_type, player_town):
    try:
        drop_chance = await calculate_item_drop_chance(mob_type)
    
        # Check if an item is dropped based on the drop chance
        if random.random() < drop_chance:
            # Select a single item to drop
            # You can modify this logic based on your table structures and item selection criteria
            # For example, you can query the appropriate tables (items, armour, weapons)
            # to select a single item based on the boss's area or location
            items_dropped = await select_random_item(player_town)
            return items_dropped
    except Exception as e:
        logging.error(f"An error occurred while dropping items: {e}")
        return None  # Return None if an error occurred
    return None  # Return None if no item is dropped

async def calculate_item_drop_chance(mob_type):
    if mob_type == 'boss':
        return BOSS_DROP_CHANCE  # Higher drop chance for bosses
    else:
        return MOB_DROP_CHANCE  # Lower drop chance for regular mobs


async def select_random_item(player_location):
    LOCATION_TO_TOWN = {
        'The Gloaming Vale': 'Shadowhaven',
        'Scorched Plains': 'Ironkeep',
        'Tide Whisper Coves': 'Havenreach',
        'Shadowmire': 'Grimhold',
        'The Ember Barrens': 'Ashenfell'
    }

    try:
        # Convert the player's location to the corresponding town name
        player_town = LOCATION_TO_TOWN.get(player_location)
        if not player_town:
            logging.warning(f"No town found for player location: {player_location}")
            return None

        # Generate a random category (e.g., item, armour, weapon) with adjusted weights
        category = random.choices(['item', 'armour', 'weapon'], weights=[0.70, 0.15, 0.15])[0]

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Query the corresponding table based on the selected category and player's town
                if category == 'item':
                    # Query the items table to select a random item considered
                    await cursor.execute("SELECT name, rarity FROM items")
                    result = await cursor.fetchall()

                    if result:
                        items = [item[0] for item in result]
                        rarities = [item[1] for item in result]
                        weights = [RARITY_WEIGHTS[rarity] for rarity in rarities]
                        total_weight = sum(weights)
                        selected_item = random.choices(items, weights=weights)[0]
                        item_index = items.index(selected_item)
                        item_chance = (weights[item_index] / total_weight) * 100
                        logging.info(f"Selected item: {selected_item}, drop chance: {item_chance}%")
                        return selected_item  # Return the name of the selected item

                elif category == 'armour':
                    # Query the armour table to select a random armour considered from the player's town
                    await cursor.execute("SELECT name, rarity FROM armour WHERE town = %s",
                                         (player_town,))
                    result = await cursor.fetchall()

                    if result:
                        armours = [armour[0] for armour in result]
                        rarities = [armour[1] for armour in result]
                        weights = [RARITY_WEIGHTS[rarity] for rarity in rarities]
                        total_weight = sum(weights)
                        selected_armour = random.choices(armours, weights=weights)[0]
                        armour_index = armours.index(selected_armour)
                        armour_chance = (weights[armour_index] / total_weight) * 100
                        logging.info(f"Selected armour: {selected_armour}, drop chance: {armour_chance}%")
                        return selected_armour  # Return the name of the selected armour

                elif category == 'weapon':
                    # Query the weapons table to select a random weapon considered from the player's town
                    await cursor.execute("SELECT name, rarity FROM weapons WHERE town = %s",
                                         (player_town,))
                    result = await cursor.fetchall()

                    if result:
                        weapons = [weapon[0] for weapon in result]
                        rarities = [weapon[1] for weapon in result]
                        weights = [RARITY_WEIGHTS[rarity] for rarity in rarities]
                        total_weight = sum(weights)
                        selected_weapon = random.choices(weapons, weights=weights)[0]
                        weapon_index = weapons.index(selected_weapon)
                        weapon_chance = (weights[weapon_index] / total_weight) * 100
                        logging.info(f"Selected weapon: {selected_weapon}, drop chance: {weapon_chance}%")
                        return selected_weapon  # Return the name of the selected weapon

                logging.info("No item found in the selected category or player's town")
                return None  # Return None if no item is found in the selected category or player's town

    except Exception as e:
        logging.error(f"An error occurred while selecting a random item: {str(e)}")
        return None

# Function to calculate dodge chance based on agility
async def calculate_dodge_chance(agility):
    dodge_chance = agility * DODGE_PER_AGILITY
    default_dodge_chance = 0.25  # 25% default dodge chance
    dodge_chance += default_dodge_chance
    return dodge_chance

async def get_boss_spawn_chance(area_name):
    # Logic to retrieve and return the chance of a boss spawn for the given area
    # Example: return 0.2 for 20% chance
    return SPAWN_BOSS_CHANCE

async def manage_thread_activity(discord_id, thread, active_threads):
    # Check if thread is an instance of discord.Thread
    if not isinstance(thread, discord.Thread):
        logging.error(f"Thread for discord_id {discord_id} is not an instance of discord.Thread. Activity management skipped.")
        return

    last_activity = datetime.datetime.now()
    new_task = asyncio.create_task(delete_inactive_thread(discord_id, active_threads, thread))
                        
    # Check if there is an existing delete task for the thread
    if discord_id in active_threads:
        existing_task, existing_thread, _ = active_threads[discord_id]
        
        try:
            existing_task.cancel()
            # Remove the existing delete task from the active_threads dictionary
            del active_threads[discord_id]
        except Exception as e:
            logging.error(f"An error occurred while cancelling the task: {e}")
                        
    # Store the new task and thread in the active_threads dictionary
    active_threads[discord_id] = (new_task, thread, last_activity)

# Function to delete the thread after a duration of inactivity
async def delete_inactive_thread(discord_id, active_threads, thread):
    inactivity_duration = INACTIVE_TIME  # Duration of inactivity in seconds

    try:
        await asyncio.sleep(inactivity_duration)  # Wait for the specified duration
    except asyncio.CancelledError:
        return  # This task has been cancelled, just return

    if discord_id in active_threads:
        try:
            task, thread, last_activity = active_threads[discord_id]  # Unpack the tuple here

            # Calculate the time elapsed since the last activity
            elapsed_time = datetime.datetime.now() - last_activity

            if elapsed_time.total_seconds() >= inactivity_duration and thread is not None:
                # Check if the thread is indeed a Thread instance
                if isinstance(thread, discord.Thread):
                    await thread.delete()
                    logging.info(f"Thread for discord_id {discord_id} deleted due to inactivity.")
                    del active_threads[discord_id]

                    # Release the user lock
                    user_lock = user_locks.get(discord_id)
                    if user_lock and user_lock.locked():
                        user_lock.release()
                        logging.info(f"User lock for discord_id {discord_id} released due to inactivity.")

                    # Clear the open_area_storage
                    if discord_id in open_area_storage:
                        open_area_storage.remove(discord_id)
                        logging.info(f"open_area_storage for discord_id {discord_id} cleared on thread close.")
                        
                    # Clear the open_area_storage
                    if discord_id in open_selling_menus:
                        open_selling_menus.remove(discord_id)
                        logging.info(f"open_area_storage for discord_id {discord_id} cleared on thread close.")
                        
                else:
                    logging.warning(f"The channel to be deleted is not a Thread instance. Deletion skipped for discord_id {discord_id}.")

        except Exception as e:
            logging.warning(f"discord_id {discord_id} not found in active_threads: {e}")
    else:
        logging.info(f"discord_id {discord_id} not in active_threads when trying to delete.")

        # Start the timer to check for inactivity and delete the thread
        last_activity = datetime.datetime.now()
        new_task = asyncio.create_task(delete_inactive_thread(discord_id, active_threads, thread))

        # Store the new task and thread in the active_threads dictionary
        active_threads[discord_id] = (new_task, thread, last_activity)
        logging.info(f"New delete task created for discord_id {discord_id}")

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())