import os
import asyncio
from discord.ext import commands
import discord
from dotenv import load_dotenv

# --- Load .env ---
load_dotenv()  # Pastikan file .env di folder yang sama dengan bot.py

# --- Ambil token ---
TOKEN = os.getenv("DISCORD_TOKEN")

# Debug sementara untuk cek token terbaca
print("DEBUG: TOKEN =", TOKEN if TOKEN else "TOKEN TIDAK DITEMUKAN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN tidak ditemukan di environment variable")

# --- Setup bot ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Event ketika bot siap ---
@bot.event
async def on_ready():
    GUILD_ID = 1406557880475320340  # GANTI dengan ID server kamu
    guild = discord.Object(id=GUILD_ID)

    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)

    print(f"Bot online sebagai {bot.user}")
    print("Slash command GUILD sync berhasil")



# --- Load semua cog ---
async def load_cogs():
    cogs = [
        "cogs.announce",
        "cogs.greeting",
        "cogs.megagombal",
        "cogs.birthday",
        "cogs.confession",
        "cogs.cantikganteng",
        "cogs.rules",
        "cogs.streak",
        "cogs.tebakfakta_rounds",
        "cogs.afk",
        "cogs.activity",
        "cogs.gpt",
        "cogs.moderation",
        "cogs.modlog",
        "cogs.utility",
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
