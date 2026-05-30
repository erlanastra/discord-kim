import os
import asyncio
from discord.ext import commands
import discord
from dotenv import load_dotenv

load_dotenv() 

TOKEN = os.getenv("DISCORD_TOKEN")

print("DEBUG: TOKEN =", TOKEN if TOKEN else "TOKEN TIDAK DITEMUKAN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN tidak ditemukan di environment variable")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot online sebagai {bot.user}")

async def load_cogs():
    cogs = [
        "cogs.post",
        "cogs.greeting",
        "cogs.megagombal",
        "cogs.say",
        "cogs.cantikganteng",
        "cogs.tebakfakta_rounds",
        "cogs.afk",
        "cogs.setup_game",
        "cogs.setup_murid",
        "cogs.setup_minat",
        "cogs.setupquote",
        "cogs.nanzquiz",
        "cogs.autoreply",
        "cogs.verif_reminder",
        "cogs.moderation",
        "cogs.verifygreeting",
        "cogs.ticket",
        "cogs.verifysystem",
        "cogs.about",
        "cogs.welcome"
    ]
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"Loaded: {cog.split('.')[-1]}.py")
        except Exception as e:
            print(f"Gagal load {cog.split('.')[-1]}.py: {e}")

# --- Main loop ---
async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

# --- Run bot ---
asyncio.run(main())
