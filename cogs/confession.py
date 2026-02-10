import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import time
import random

DATA_FILE = "data/confession.json"
COOLDOWN = 600  # 10 menit

def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "count": 0,
            "cooldown": {}
        }
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def random_color():
    return discord.Color.from_rgb(
        random.randint(80,200),
        random.randint(80,200),
        random.randint(80,200)
    )

class Confession(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = load_data()

    confess = app_commands.Group(
        name="confess",
        description="🕊️ Kirim curhat anonim"
    )

    # ================= SEND =================
    @confess.command(name="send", description="Kirim confession anonim")
    async def send_confession(self, interaction: discord.Interaction, pesan: str):
        uid = str(interaction.user.id)
        now = time.time()

        last = self.data["cooldown"].get(uid, 0)
        if now - last < COOLDOWN:
            await interaction.response.send_message(
                "⏳ Tunggu beberapa menit sebelum mengirim lagi.",
                ephemeral=True
            )
            return

        if len(pesan) > 700:
            await interaction.response.send_message(
                "❌ Maksimal 700 karakter.",
                ephemeral=True
            )
            return

        channel = discord.utils.get(interaction.guild.text_channels, name="💌︱confession")
        if not channel:
            await interaction.response.send_message(
                "❌ Channel **#confession** tidak ditemukan.",
                ephemeral=True
            )
            return

        self.data["count"] += 1
        self.data["cooldown"][uid] = now
        save_data(self.data)

        embed = discord.Embed(
            title=f"🕊️ Anonymous Confession #{self.data['count']}",
            description=pesan,
            color=random_color()
        )
        embed.set_footer(
            text="Identitas pengirim dirahasiakan • Be kind 🤍"
        )

        msg = await channel.send(embed=embed)
        await msg.add_reaction("❤️")
        await msg.add_reaction("🤍")
        await msg.add_reaction("🫂")

        await interaction.response.send_message(
            "✅ Confession berhasil dikirim secara anonim.",
            ephemeral=True
        )

    # ================= RULES =================
    @confess.command(name="rules", description="Aturan confession")
    async def rules(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📌 Aturan Confession",
            description=(
                "• ❌ Tidak mengandung SARA / doxxing\n"
                "• ❌ Tidak menyebut nama orang\n"
                "• ❌ Tidak spam\n"
                "• ✅ Saling menghargai\n\n"
                "⚠️ Pelanggaran bisa dihapus oleh admin"
            ),
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Confession(bot))
