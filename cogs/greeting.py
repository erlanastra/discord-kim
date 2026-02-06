import discord
from discord.ext import commands, tasks
from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9+
import json
import random

class Greeting(commands.Cog):
    """Greeting Bot final full: embed warna-warni, emoji lucu, WITA, tes di Welcome"""

    def __init__(self, bot):
        self.bot = bot
        # Load config
        with open("config.json") as f:
            self.config = json.load(f)
        self.greet.start()  # start loop otomatis

    @tasks.loop(minutes=60)
    async def greet(self):
        """Loop otomatis tiap jam tertentu"""
        await self.bot.wait_until_ready()  # pastikan bot siap

        # Ambil channel Welcome
        channel_id = self.config.get("welcome_channel")
        channel = self.bot.get_channel(channel_id)
        if not channel:
            print(f"[Greeting] Channel Welcome ID {channel_id} tidak ditemukan!")
            return

        # Jam WITA
        now = datetime.now(ZoneInfo("Asia/Makassar"))
        hour = now.hour

        # Pesan per jam
        greetings = {
            6: [
                "🌅 **Selamat pagi semuanya! Semangat memulai hari!**",
                "☕ **Pagi! Jangan lupa kopi pagimu!**",
                "🌞 **Selamat pagi! Semoga harimu cerah!**"
            ],
            12: [
                "☀️ **Selamat siang! Jangan lupa makan siang ya!**",
                "🍴 **Siang! Waktunya istirahat sebentar!**",
                "😎 **Selamat siang, semangat bekerja!**"
            ],
            18: [
                "🌆 **Selamat sore! Semoga harimu menyenangkan!**",
                "🌇 **Sore! Saatnya santai sejenak!**",
                "🍵 **Selamat sore, jangan lupa teh sore ya!**"
            ],
            22: [
                "🌙 **Selamat malam! Istirahat yang cukup ya!**",
                "🛌 **Malem! Saatnya tidur nyenyak!**",
                "✨ **Selamat malam, semoga mimpi indah!**"
            ]
        }

        if hour in greetings:
            msg = random.choice(greetings[hour])
            embed = discord.Embed(
                title="🕒 Greeting Bot",
                description=msg,
                color=random.choice([discord.Color.green(), discord.Color.blue(), discord.Color.purple()])
            )
            embed.set_footer(text="Dikirim otomatis oleh Greeting Bot")
            await channel.send(embed=embed)
            print(f"[Greeting] Pesan dikirim ke channel: {channel.name} ({channel.id})")

    @commands.command(name="testgreet")
    async def test_greet(self, ctx):
        """Command untuk tes greeting langsung di channel Welcome"""
        # Ambil channel Welcome
        channel_id = self.config.get("welcome_channel")
        channel = self.bot.get_channel(channel_id)
        if not channel:
            await ctx.send(f"⚠️ Channel Welcome ID {channel_id} tidak ditemukan!")
            print(f"[Greeting] Test gagal, channel ID {channel_id} tidak ditemukan")
            return

        greetings = [
            "🌟 **Test Greeting Bot**",
            "🎉 **Halo! Ini test greeting!**",
            "💫 **Cek embed warna-warni & emoji!**"
        ]
        msg = random.choice(greetings)
        embed = discord.Embed(
            title="🕒 Greeting Bot (Test)",
            description=msg,
            color=random.choice([discord.Color.green(), discord.Color.blue(), discord.Color.purple()])
        )
        embed.set_footer(text=f"Test dikirim oleh {ctx.author.display_name}")
        await channel.send(embed=embed)
        await ctx.send(f"✅ Test greeting berhasil dikirim ke channel **{channel.name}**")
        print(f"[Greeting] Test greeting dikirim ke channel: {channel.name} ({channel.id})")

# Setup cog untuk discord.py v2+
async def setup(bot):
    await bot.add_cog(Greeting(bot))
