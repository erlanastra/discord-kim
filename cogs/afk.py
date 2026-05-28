import discord
from discord.ext import commands
import json
import os
import time

AFK_FILE = "afk_data.json"


# ================= LOAD DATA =================
def load_afk():

    if not os.path.exists(AFK_FILE):
        return {}

    with open(AFK_FILE, "r") as f:
        return json.load(f)


def save_afk(data):

    with open(AFK_FILE, "w") as f:
        json.dump(data, f, indent=4)


afk_users = load_afk()


# ================= COG =================
class AFK(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    # ================= COMMAND AFK =================
    @commands.command()
    async def afk(self, ctx, *, reason="AFK"):

        user_id = str(ctx.author.id)

        # Kalau sudah AFK
        if user_id in afk_users:

            embed = discord.Embed(
                title="❌ AFK Gagal",
                description=(
                    f"{ctx.author.mention}, "
                    f"kamu sudah AFK sebelumnya!"
                ),
                color=0xED4245
            )

            return await ctx.send(embed=embed)

        # Simpan data AFK
        afk_users[user_id] = {
            "reason": reason,
            "time": time.time()
        }

        save_afk(afk_users)

        # Embed sukses
        embed = discord.Embed(
            title="🌙 AFK Status Aktif",
            description=(
                f"{ctx.author.mention} "
                f"telah mengaktifkan status AFK.\n\n"
                f"**Alasan:** {reason}\n\n"
                f"Status akan otomatis nonaktif "
                f"saat kamu kembali."
            ),
            color=0x9B59B6
        )

        await ctx.send(embed=embed)

    # ================= ON MESSAGE =================
    @commands.Cog.listener()
    async def on_message(self, message):

        # Ignore bot
        if message.author.bot:
            return

        # ================= CEK COMMAND =================
        ctx = await self.bot.get_context(message)

        # Kalau message adalah command
        # jangan jalankan logic AFK
        if ctx.valid:
            await self.bot.process_commands(message)
            return

        user_id = str(message.author.id)

        # ================= REMOVE AFK =================
        if user_id in afk_users:

            data = afk_users[user_id]

            afk_time = int(
                time.time() - data["time"]
            )

            del afk_users[user_id]

            save_afk(afk_users)

            embed = discord.Embed(
                title="👋 Welcome Back",
                description=(
                    f"{message.author.mention} "
                    f"telah kembali dari AFK.\n"
                    f"**Durasi AFK:** "
                    f"{afk_time} detik"
                ),
                color=0xE67E22
            )

            await message.channel.send(
                embed=embed
            )

        # ================= CEK MENTION AFK =================
        for user in message.mentions:

            target_id = str(user.id)

            if target_id in afk_users:

                data = afk_users[target_id]

                embed = discord.Embed(
                    title="💤 User Sedang AFK",
                    description=(
                        f"{user.mention} sedang AFK.\n\n"
                        f"**Alasan:** "
                        f"{data['reason']}"
                    ),
                    color=0x5865F2
                )

                await message.channel.send(
                    embed=embed
                )

                break


# ================= SETUP =================
async def setup(bot):

    await bot.add_cog(
        AFK(bot)
    )