import discord
from discord.ext import commands, tasks
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import random

class Greeting(commands.Cog):
    """Greeting Bot interaktif dengan kalimat panjang, GIF thumbnail, emoji bergerak, dan random quote"""

    def __init__(self, bot):
        self.bot = bot
        with open("config.json") as f:
            self.config = json.load(f)
        self.greet.start()

    @tasks.loop(minutes=1)
    async def greet(self):
        await self.bot.wait_until_ready()

        channel_id = self.config.get("welcome_channel")
        channel = self.bot.get_channel(channel_id)
        if not channel:
            print(f"[Greeting] Channel Welcome ID {channel_id} tidak ditemukan!")
            return

        now = datetime.now(ZoneInfo("Asia/Jakarta"))  # WIB
        hour = now.hour
        minute = now.minute

        if minute != 0:
            return  # hanya tiap jam tepat

        # Greeting panjang & GIF thumbnail
        greetings = {
            6: {
                "title": "Selamat Pagi!",
                "emoji": "🌞",
                "description": (
                    "Selamat pagi teman-teman! 🌅 Pukul **06:00 WIB** telah tiba, saatnya memulai hari dengan penuh semangat, senyum lebar, "
                    "dan energi positif. Jangan lupa sarapan sehat, secangkir kopi hangat ☕, dan peregangan ringan untuk menyiapkan tubuh "
                    "dan pikiran menghadapi hari yang penuh peluang dan kebahagiaan. Semoga pagi ini membawa inspirasi dan kegembiraan bagi kalian semua!"
                ),
                "thumbnail": "https://i.ibb.co/0jqHpnp/morning.gif"
            },
            12: {
                "title": "Selamat Siang!",
                "emoji": "☀️",
                "description": (
                    "Selamat siang semuanya! 🌤️ Pukul **12:00 WIB** telah tiba, waktunya untuk sejenak beristirahat dan menikmati makan siang yang lezat 🍴. "
                    "Biarkan energi kalian terisi kembali, dan jangan lupa untuk tetap tersenyum, berbagi kebaikan, serta menghargai momen-momen indah di tengah kesibukan hari ini. "
                    "Semoga sisa hari kalian produktif, menyenangkan, dan penuh berkah!"
                ),
                "thumbnail": "https://i.ibb.co/Phv8Fqq/noon.gif"
            },
            18: {
                "title": "Selamat Sore!",
                "emoji": "🌆",
                "description": (
                    "Selamat sore teman-teman! 🌇 Pukul **18:00 WIB** telah tiba, saatnya melonggarkan pikiran, menikmati teh atau camilan sore 🍵, "
                    "dan melepas lelah setelah seharian beraktivitas. Semoga sore ini membawa ketenangan, kebahagiaan, dan momen hangat bersama keluarga, teman, atau orang-orang tercinta."
                ),
                "thumbnail": "https://i.ibb.co/xFqNxR7/evening.gif"
            },
            22: {
                "title": "Selamat Malam!",
                "emoji": "🌙",
                "description": (
                    "Selamat malam semua! 🌌 Pukul **22:00 WIB** telah tiba, saatnya beristirahat, recharge energi, dan bersiap menghadapi hari esok. "
                    "Semoga tidur kalian nyenyak, mimpi indah, dan hati tetap damai. Terima kasih telah menjadi bagian dari hari yang menyenangkan ini, "
                    "dan jangan lupa bersyukur atas semua hal kecil maupun besar yang terjadi hari ini!"
                ),
                "thumbnail": "https://i.ibb.co/ZV2j2kR/night.gif"
            }
        }

        quotes = [
            "💡 Jangan berhenti sampai kamu bangga!",
            "💡 Senyum itu gratis, tapi pengaruhnya mahal 😄",
            "💡 Semangatmu hari ini akan menentukan harimu!",
            "💡 Setiap hari adalah kesempatan baru 🌟",
            "💡 Kecil atau besar, setiap langkah maju berharga!"
        ]

        if hour in greetings:
            greet = greetings[hour]
            embed = discord.Embed(
                title=f"{greet['emoji']} {greet['title']}",
                description=greet['description'],
                color=random.choice([discord.Color.green(), discord.Color.blue(), discord.Color.purple(), discord.Color.orange()])
            )

            embed.add_field(name="Motivasi Hari Ini", value=random.choice(quotes), inline=False)
            embed.add_field(name="Tips", value="Tetap semangat, tersenyum, dan nikmati harimu! 😄", inline=True)
            embed.add_field(name="Waktu Saat Ini", value=f"{hour:02d}:00 WIB", inline=True)

            embed.set_footer(text=f"Dikirim otomatis oleh Greeting Bot • NanZ Server")
            embed.set_thumbnail(url=greet["thumbnail"])

            await channel.send(embed=embed)
            print(f"[Greeting] Pesan dikirim ke channel: {channel.name} ({channel.id})")

    @commands.command(name="testgreet")
    async def test_greet(self, ctx):
        channel_id = self.config.get("welcome_channel")
        channel = self.bot.get_channel(channel_id)
        if not channel:
            await ctx.send("⚠️ Channel Welcome tidak ditemukan!")
            return

        greet = {
            "title": "Test Greeting Bot",
            "emoji": "✨",
            "description": "Halo semua! 🎉 Ini adalah test greeting yang hangat dan panjang untuk memastikan bot bekerja dengan sempurna."
        }
        embed = discord.Embed(
            title=f"{greet['emoji']} {greet['title']}",
            description=greet['description'],
            color=random.choice([discord.Color.green(), discord.Color.blue(), discord.Color.purple(), discord.Color.orange()])
        )

        embed.add_field(name="Motivasi Hari Ini", value=random.choice([
            "💡 Jangan berhenti sampai kamu bangga!",
            "💡 Semangatmu hari ini akan menentukan harimu!",
            "💡 Senyum itu gratis 😄"
        ]), inline=False)
        embed.set_footer(text=f"NanZ Server")
        embed.set_thumbnail(url="https://i.ibb.co/0jqHpnp/morning.gif")
        await channel.send(embed=embed)
        await ctx.send(f"✅ Test greeting berhasil dikirim ke channel **{channel.name}**")

async def setup(bot):
    await bot.add_cog(Greeting(bot))
