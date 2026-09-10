import os
import asyncio
import aiohttp

from discord.ext import commands
import discord

from cogs.verifysystem import VerifyButton
from cogs.setupquote import QuoteView
from cogs.ticket import TicketView
from cogs.setup_murid import MuridView
from cogs.setup_minat import MinatView
from cogs.setup_game import GameView
from cogs.role_request import RoleRequestView

from dotenv import load_dotenv
from database import db


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

print(
    "DEBUG: TOKEN =",
    TOKEN if TOKEN else "TOKEN TIDAK DITEMUKAN"
)

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN tidak ditemukan di environment variable"
    )


# ==========================================================
# BOT
# ==========================================================

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ==========================================================
# READY
# ==========================================================

@bot.event
async def on_ready():

    print("=" * 50)
    print(f"Bot online sebagai {bot.user}")
    print("Persistent Views Loaded")
    print("=" * 50)


# ==========================================================
# LOAD COGS
# ==========================================================

async def load_cogs():

    cogs = [
        "cogs.post",
        "cogs.ai",
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
        "cogs.top_stats",
        "cogs.role_request",
        "cogs.staff_attendance",
        "cogs.staff_directory",
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

            print(
                f"Loaded: {cog.split('.')[-1]}.py"
            )

        except Exception as e:

            print(
                f"Gagal load {cog.split('.')[-1]}.py: {e}"
            )


# ==========================================================
# REGISTER PERSISTENT VIEWS
# ==========================================================

def register_persistent_views():

    # Verification
    bot.add_view(
        VerifyButton(bot)
    )

    # Quote
    bot.add_view(
        QuoteView(bot)
    )

    # Ticket
    bot.add_view(
        TicketView()
    )

    # Murid
    bot.add_view(
        MuridView()
    )

    # Minat
    bot.add_view(
        MinatView()
    )

    # Game
    bot.add_view(
        GameView()
    )

    # ======================================================
    # CUSTOM ROLE REQUEST
    # ======================================================

    bot.add_view(
        RoleRequestView()
    )

    print("Persistent Views berhasil didaftarkan.")


# ==========================================================
# MAIN
# ==========================================================

async def main():

    await db.connect()

    try:

        async with bot:

            # Load semua cog
            await load_cogs()

            # Register semua persistent view
            register_persistent_views()

            # Start bot
            await bot.start(TOKEN)

    finally:

        await db.close()


# ==========================================================
# RUN
# ==========================================================

asyncio.run(main())