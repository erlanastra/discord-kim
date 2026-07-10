import os
import asyncio
from discord.ext import commands
import discord
from cogs.verifysystem import VerifyButton
from cogs.setupquote import QuoteView
from cogs.ticket import TicketView
from cogs.ticket import DecisionView
from cogs.setup_murid import MuridView
from cogs.setup_minat import MinatView
from cogs.setup_game import GameView
from dotenv import load_dotenv
from database import db

load_dotenv() 

TOKEN = os.getenv("DISCORD_TOKEN")

print("DEBUG: TOKEN =", TOKEN if TOKEN else "TOKEN TIDAK DITEMUKAN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN tidak ditemukan di environment variable")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():

    try:
        bot.add_view(VerifyButton(bot))
        bot.add_view(QuoteView(bot))
        bot.add_view(TicketView())
        bot.add_view(MuridView())
        bot.add_view(MinatView())
        bot.add_view(GameView())

        print("=" * 50)
        print(f"Bot online sebagai {bot.user}")
        print("Persistent Views Loaded")
        print("=" * 50)

    except Exception as e:

        print(f"ERROR ON_READY: {e}")

async def load_cogs():
    cogs = [
        "cogs.post",
        "cogs.greeting",
        "cogs.megagombal",
        "cogs.say",
        "cogs.afk",
        "cogs.autoemoji",
        "cogs.cantikganteng",
        "cogs.worldcup",
        "cogs.worldcup_match",
        "cogs.setup_game",
        "cogs.nanzteamevent",
        "cogs.setup_murid",
        "cogs.setup_minat",
        "cogs.setupquote",
        "cogs.nanzquiz",
        "cogs.autoreply",
        "cogs.verif_reminder",
        "cogs.moderation",
        "cogs.warn",
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

    await db.connect()

    try:

        async with bot:

            await load_cogs()

            await bot.start(TOKEN)

    finally:

        await db.close()

# --- Run bot ---
asyncio.run(main())
