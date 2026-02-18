import discord
from discord.ext import commands, tasks
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import random

class RamadhanGreeting(commands.Cog):
    """Reminder Ramadhan: Imsak, Sholat WIB, & Buka (WIB/WITA/WIT)"""

    def __init__(self, bot):
        self.bot = bot
        with open("config.json") as f:
            self.config = json.load(f)
        self.loop_ramadhan.start()

    MOTIVASI = [
        "🌙 Ramadhan adalah waktu memperbaiki diri.",
        "🤍 Sabar hari ini, pahala menanti.",
        "🕌 Jangan lelah beribadah, Allah melihat niatmu.",
        "✨ Puasa melatih hati sebelum raga.",
        "🌟 Setiap lapar adalah pahala."
    ]

    # ===== WIB (JAKARTA) =====
    # (imsak, subuh, dzuhur, ashar, maghrib, isya)
    RAMADHAN_WIB = {
        19: ("04:31", "04:41", "12:10", "15:20", "18:18", "19:28"),
        20: ("04:32", "04:42", "12:10", "15:19", "18:18", "19:28"),
        21: ("04:32", "04:42", "12:10", "15:19", "18:17", "19:27"),
        # 🔁 LANJUTKAN SESUAI JADWAL
    }

    # ===== WITA (MAKASSAR) =====
    # (imsak, buka)
    RAMADHAN_WITA = {
        19: ("04:42", "18:27"),
        20: ("04:42", "18:27"),
        21: ("04:42", "18:26"),
    }

    # ===== WIT (JAYAPURA) =====
    # (imsak, buka)
    RAMADHAN_WIT = {
        19: ("04:32", "18:07"),
        20: ("04:32", "18:07"),
        21: ("04:32", "18:06"),
    }

    @tasks.loop(minutes=1)
    async def loop_ramadhan(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.config.get("welcome_channel"))
        if not channel:
            return

        now_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
        now_wita = datetime.now(ZoneInfo("Asia/Makassar"))
        now_wit = datetime.now(ZoneInfo("Asia/Jayapura"))

        day = now_wib.day
        t_wib = now_wib.strftime("%H:%M")
        t_wita = now_wita.strftime("%H:%M")
        t_wit = now_wit.strftime("%H:%M")

        motivasi = random.choice(self.MOTIVASI)

        # ================= WIB =================
        if day in self.RAMADHAN_WIB:
            imsak, subuh, dzuhur, ashar, maghrib, isya = self.RAMADHAN_WIB[day]

            # IMSAK WIB
            if t_wib == imsak:
                await channel.send(embed=self.embed_msg(
                    "⏰ Imsak (WIB)", imsak, "Asia/Jakarta", motivasi, discord.Color.dark_gold()
                ))

            sholat = {
                subuh: "🕌 Subuh",
                dzuhur: "🕌 Dzuhur",
                ashar: "🕌 Ashar",
                maghrib: "🌙 Buka Puasa",
                isya: "🕌 Isya"
            }

            if t_wib in sholat:
                await channel.send(embed=self.embed_msg(
                    f"{sholat[t_wib]} (WIB)", t_wib, "Asia/Jakarta", motivasi, discord.Color.green()
                ))

        # ================= WITA =================
        if day in self.RAMADHAN_WITA:
            imsak, buka = self.RAMADHAN_WITA[day]

            if t_wita == imsak:
                await channel.send(embed=self.embed_msg(
                    "⏰ Imsak (WITA)", imsak, "Asia/Makassar", motivasi, discord.Color.orange()
                ))

            if t_wita == buka:
                await channel.send(embed=self.embed_msg(
                    "🌙 Buka Puasa (WITA)", buka, "Asia/Makassar", motivasi, discord.Color.green()
                ))

        # ================= WIT =================
        if day in self.RAMADHAN_WIT:
            imsak, buka = self.RAMADHAN_WIT[day]

            if t_wit == imsak:
                await channel.send(embed=self.embed_msg(
                    "⏰ Imsak (WIT)", imsak, "Asia/Jayapura", motivasi, discord.Color.orange()
                ))

            if t_wit == buka:
                await channel.send(embed=self.embed_msg(
                    "🌙 Buka Puasa (WIT)", buka, "Asia/Jayapura", motivasi, discord.Color.green()
                ))

    def embed_msg(self, title, time, zone, motivasi, color):
        embed = discord.Embed(
            title=title,
            description=f"🕰️ **{time}**\n🌍 {zone}",
            color=color
        )
        embed.add_field(name="✨ Motivasi", value=motivasi, inline=False)
        embed.set_footer(text="Ramadhan Reminder • nanZ Server")
        embed.set_thumbnail(url="https://i.ibb.co/JtZ6N9K/mosque.png")
        return embed

async def setup(bot):
    await bot.add_cog(RamadhanGreeting(bot))
