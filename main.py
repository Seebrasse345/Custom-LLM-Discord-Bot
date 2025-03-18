# main.py

import discord
from discord.ext import commands
import asyncio
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Retrieve the token from the environment variable
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("No Discord API token found! Please set DISCORD_TOKEN in your .env file.")

# Define the bot with all intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# List of cogs/extensions to load
initial_extensions = [
    "cogs.conversation_manager",
    "cogs.server_manager",
    "cogs.voice_tts_manager",
    "cogs.music_cog",
]

async def load_extensions():
    """Asynchronously load all listed extensions."""
    for extension in initial_extensions:
        try:
            await bot.load_extension(extension)
            print(f"[SUCCESS] Loaded extension: {extension}")
        except Exception as e:
            print(f"[ERROR] Failed to load extension {extension}: {e}")

async def main():
    """Main async entrypoint for the bot."""
    print("[DEBUG] Loading extensions...")
    await load_extensions()

    print("[DEBUG] Starting bot...")
    try:
        await bot.start(TOKEN)
    except Exception as e:
        print(f"[ERROR] Bot run error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
