from discord.ext import commands
import discord
import os
import asyncio

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot online sebagai {bot.user}")

# Load semua cog
async def load_cogs():
    for cog in [
        "cogs.announce",
        "cogs.greeting",
        "cogs.megagombal",
        "cogs.rules",
        "cogs.warn",
        "cogs.moderation",
        "cogs.modlog",
        "cogs.utility",
        "cogs.welcome"
    ]:
        try:
            await bot.load_extension(cog)
            print(f"Loaded: {cog.split('.')[-1]}.py")
        except Exception as e:
            print(f"Gagal load {cog.split('.')[-1]}.py: {e}")

async def main():
    token = os.getenv("DISCORD_TOKEN")

    if not token:
        raise RuntimeError("DISCORD_TOKEN tidak ditemukan di environment variable")

    async with bot:
        await load_cogs()
        await bot.start(token)

asyncio.run(main())
