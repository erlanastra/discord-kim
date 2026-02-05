import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot online sebagai {bot.user}")

    for file in os.listdir("./cogs"):
        if file.endswith(".py") and not file.startswith("__"):
            try:
                await bot.load_extension(f"cogs.{file[:-3]}")
                print(f"Loaded: {file}")
            except Exception as e:
                print(f"Gagal load {file}: {e}")


bot.run(TOKEN)
