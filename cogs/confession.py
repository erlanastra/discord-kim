import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import time
import random

DATA_FILE = "data/confession.json"
COOLDOWN = 600  # 10 menit
ADMIN_ID = 1169643619049799740  # ⬅️ GANTI DENGAN USER ID KAMU

# ================= DATA =================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "count": 0,
            "cooldown": {}
        }
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def random_color():
    return discord.Color.from_rgb(
        random.randint(80, 200),
        random.randint(80, 200),
        random.randint(80, 200)
    )

# ================= TOXIC FILTER =================
TOXIC_WORDS = [
    "bodoh", "tolol", "anjing", "babi", "kontol", "memek",
    "anjg", "ajg", "njing", "jing", "4njing", "4nj1ng",
    "nj1ng", "4jg", "j1ng", "b4b1", "b4bi", "bab1",
    "m3m3k", "mmk", "m3mek", "mem3k", "mek",
    "kntl", "kontl", "kintil", "kntol", "ntol",
    "tlol", "toll"
]

def contains_toxic(text):
    text = text.lower()
    return any(word in text for word in TOXIC_WORDS)

# ================= COG =================
class Confession(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = load_data()

    confess = app_commands.Group(
        name="confess",
        description="🕊️ Kirim confession anonim"
    )

    # ================= SEND =================
    @confess.command(name="send", description="Kirim confession anonim")
    async def send_confession(self, interaction: discord.Interaction, pesan: str):
        uid = str(interaction.user.id)
        now = time.time()

        admin = await self.bot.fetch_user(ADMIN_ID)

        # COOLDOWN
        last = self.data["cooldown"].get(uid, 0)
        if now - last < COOLDOWN:
            await interaction.response.send_message(
                "⏳ Tunggu beberapa menit sebelum mengirim lagi.",
                ephemeral=True
            )
            return

        # PANJANG PESAN
        if len(pesan) > 700:
            await interaction.response.send_message(
                "❌ Maksimal 700 karakter.",
                ephemeral=True
            )
            return

        # FILTER TOXIC
        if contains_toxic(pesan):
            await interaction.response.send_message(
                "❌ Pesan mengandung kata yang tidak diperbolehkan.",
                ephemeral=True
            )

            await admin.send(
                f"⚠️ **Percobaan Confession Terlarang**\n"
                f"👤 User: {interaction.user}\n"
                f"🆔 ID: {interaction.user.id}\n"
                f"💬 Pesan:\n{pesan}"
            )
            return

        # CARI CHANNEL CONFESSION
        channel = discord.utils.get(
            interaction.guild.text_channels,
            name="💌︱confession"
        )
        if not channel:
            await interaction.response.send_message(
                "❌ Channel confession tidak ditemukan.",
                ephemeral=True
            )
            return

        # UPDATE DATA
        self.data["count"] += 1
        self.data["cooldown"][uid] = now
        save_data(self.data)

        # EMBED CONFESSION
        embed = discord.Embed(
            title=f"🕊️ Anonymous Confession #{self.data['count']}",
            description=pesan,
            color=random_color()
        )
        embed.set_footer(text="Identitas pengirim dirahasiakan • Be kind 🤍")

        msg = await channel.send(embed=embed)
        await msg.add_reaction("❤️")
        await msg.add_reaction("🤍")
        await msg.add_reaction("🫂")

        # ================= DM ADMIN =================
        log_embed = discord.Embed(
            title=f"📩 Confession #{self.data['count']} terkirim",
            description=pesan,
            color=discord.Color.orange()
        )
        log_embed.set_footer(text=f"User ID: {interaction.user.id}")
        await admin.send(embed=log_embed)

        private_embed = discord.Embed(
            title=f"🔒 Confession #{self.data['count']} (PRIVATE)",
            description=pesan,
            color=discord.Color.red()
        )
        private_embed.set_footer(
            text=f"Pengirim: {interaction.user} • ID: {interaction.user.id}"
        )
        await admin.send(embed=private_embed)

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
                "⚠️ Pelanggaran bisa ditindak admin"
            ),
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Confession(bot))
