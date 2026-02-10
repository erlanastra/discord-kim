import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
from datetime import datetime
import random

DATA_FILE = "data/birthday.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def random_color():
    return discord.Color.from_rgb(
        random.randint(50,255),
        random.randint(50,255),
        random.randint(50,255)
    )

class Birthday(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = load_data()
        self.check_birthday.start()

    def cog_unload(self):
        self.check_birthday.cancel()

    birthday = app_commands.Group(
        name="birthday",
        description="🎂 Sistem ulang tahun otomatis"
    )

    # ================= SET =================
    @birthday.command(name="set", description="Set ulang tahun (DD-MM)")
    async def set_birthday(self, interaction: discord.Interaction, tanggal: str):
        try:
            datetime.strptime(tanggal, "%d-%m")
        except ValueError:
            await interaction.response.send_message(
                "❌ Format salah. Gunakan **DD-MM** (contoh: 12-05)",
                ephemeral=True
            )
            return

        uid = str(interaction.user.id)
        self.data[uid] = {
            "date": tanggal,
            "last_sent": None
        }
        save_data(self.data)

        embed = discord.Embed(
            title="🎂 Birthday Saved!",
            description=f"Ulang tahun kamu disimpan pada **{tanggal}** 🎉",
            color=random_color()
        )
        embed.set_footer(text="Bot Birthday • Data tersimpan aman")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ================= REMOVE =================
    @birthday.command(name="remove", description="Hapus data ulang tahun")
    async def remove_birthday(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)

        if uid not in self.data:
            await interaction.response.send_message(
                "⚠️ Kamu belum menyimpan ulang tahun.",
                ephemeral=True
            )
            return

        del self.data[uid]
        save_data(self.data)

        await interaction.response.send_message(
            "✅ Data ulang tahun berhasil dihapus.",
            ephemeral=True
        )

    # ================= LIST =================
    @birthday.command(name="list", description="Daftar ulang tahun (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_birthday(self, interaction: discord.Interaction):
        if not self.data:
            await interaction.response.send_message("📭 Belum ada data.")
            return

        desc = ""
        for uid, info in self.data.items():
            member = interaction.guild.get_member(int(uid))
            if member:
                desc += f"🎈 **{member.display_name}** — `{info['date']}`\n"

        embed = discord.Embed(
            title="🎂 Birthday List",
            description=desc,
            color=random_color()
        )
        await interaction.response.send_message(embed=embed)

    # ================= AUTO CHECK =================
    @tasks.loop(hours=24)
    async def check_birthday(self):
        today = datetime.now().strftime("%d-%m")

        for guild in self.bot.guilds:
            channel = discord.utils.get(guild.text_channels, name="birthday")
            if not channel:
                continue

            for uid, info in self.data.items():
                if info["date"] == today and info["last_sent"] != today:
                    member = guild.get_member(int(uid))
                    if not member:
                        continue

                    embed = discord.Embed(
                        title="🎉 HAPPY BIRTHDAY 🎉",
                        description=(
                            f"Selamat ulang tahun {member.mention} 🥳\n"
                            "Semoga panjang umur, sehat selalu, dan bahagia 💖"
                        ),
                        color=random_color()
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.set_footer(text="🎂 Birthday Bot")

                    await channel.send(embed=embed)
                    info["last_sent"] = today

        save_data(self.data)

async def setup(bot):
    await bot.add_cog(Birthday(bot))
