import discord
from discord.ext import commands, tasks
from datetime import datetime, date
from zoneinfo import ZoneInfo
import json
import random

class RamadhanGreeting(commands.Cog):
    """Ramadhan Reminder • Imsak, Sholat, & Buka"""

    RAMADHAN_START = date(2026, 2, 19)  # TANGGAL MULAI RAMADHAN

    def __init__(self, bot):
        self.bot = bot
        with open("config.json") as f:
            self.config = json.load(f)
        self.loop_ramadhan.start()

    # ================= MOTIVASI =================
    MOTIVASI = [
        "🌙 Ramadhan adalah waktu memperbaiki diri.",
        "🤍 Sabar hari ini, pahala menanti.",
        "🕌 Jangan lelah beribadah, Allah melihat niatmu.",
        "✨ Puasa melatih hati sebelum raga.",
        "🌟 Setiap lapar adalah pahala."
    ]

    # ================= GAMBAR =================
    IMAGE_IMSAK = "https://images.unsplash.com/photo-1605538368277-2f4e09a3e237"
    IMAGE_SHOLAT = "https://images.unsplash.com/photo-1584881864238-bcdb0f5b7c62"
    IMAGE_BUKA  = "https://images.unsplash.com/photo-1542816417-0983c9c9ad53"

    # ================= JADWAL =================
    # (imsak, subuh, dzuhur, ashar, maghrib, isya)
    # (imsak, subuh, dzuhur, ashar, maghrib, isya)
    RAMADHAN_WIB = {
        1:  ("04:31", "04:41", "12:10", "15:20", "18:18", "19:28"),
        2:  ("04:32", "04:42", "12:10", "15:19", "18:18", "19:28"),
        3:  ("04:32", "04:42", "12:10", "15:19", "18:17", "19:27"),
        4:  ("04:32", "04:42", "12:10", "15:18", "18:17", "19:27"),
        5:  ("04:32", "04:42", "12:10", "15:17", "18:17", "19:26"),
        6:  ("04:32", "04:42", "12:09", "15:16", "18:17", "19:26"),
        7:  ("04:32", "04:42", "12:09", "15:15", "18:16", "19:26"),
        8:  ("04:32", "04:42", "12:09", "15:15", "18:16", "19:25"),
        9:  ("04:33", "04:43", "12:09", "15:14", "18:16", "19:25"),
        10: ("04:33", "04:43", "12:09", "15:13", "18:15", "19:24"),
        11: ("04:33", "04:43", "12:09", "15:12", "18:15", "19:24"),
        12: ("04:33", "04:43", "12:08", "15:11", "18:14", "19:24"),
        13: ("04:33", "04:43", "12:08", "15:10", "18:14", "19:23"),
        14: ("04:33", "04:43", "12:08", "15:09", "18:14", "19:23"),
        15: ("04:33", "04:43", "12:08", "15:08", "18:13", "19:22"),
        16: ("04:33", "04:43", "12:07", "15:08", "18:13", "19:22"),
        17: ("04:33", "04:43", "12:07", "15:09", "18:12", "19:21"),
        18: ("04:33", "04:43", "12:07", "15:09", "18:12", "19:21"),
        19: ("04:33", "04:43", "12:07", "15:10", "18:12", "19:20"),
        20: ("04:33", "04:43", "12:06", "15:10", "18:11", "19:20"),
        21: ("04:33", "04:43", "12:06", "15:10", "18:11", "19:19"),
        22: ("04:33", "04:43", "12:06", "15:11", "18:10", "19:19"),
        23: ("04:33", "04:43", "12:06", "15:11", "18:10", "19:18"),
        24: ("04:33", "04:43", "12:05", "15:11", "18:09", "19:18"),
        25: ("04:33", "04:43", "12:05", "15:12", "18:09", "19:17"),
        26: ("04:33", "04:43", "12:05", "15:12", "18:09", "19:17"),
        27: ("04:32", "04:42", "12:05", "15:12", "18:08", "19:16"),
        28: ("04:32", "04:42", "12:04", "15:12", "18:08", "19:16"),
        29: ("04:32", "04:42", "12:04", "15:13", "18:07", "19:16"),
        30: ("04:32", "04:42", "12:04", "15:13", "18:07", "19:15"),
    }


    # (imsak, buka)
    RAMADHAN_WITA = {
        1:  ("04:42", "18:27"),
        2:  ("04:42", "18:27"),
        3:  ("04:42", "18:26"),
        4:  ("04:43", "18:26"),
        5:  ("04:43", "18:26"),
        6:  ("04:43", "18:25"),
        7:  ("04:43", "18:25"),
        8:  ("04:43", "18:25"),
        9:  ("04:43", "18:25"),
        10: ("04:43", "18:24"),
        11: ("04:43", "18:24"),
        12: ("04:43", "18:24"),
        13: ("04:43", "18:23"),
        14: ("04:43", "18:23"),
        15: ("04:43", "18:22"),
        16: ("04:43", "18:22"),
        17: ("04:43", "18:22"),
        18: ("04:43", "18:21"),
        19: ("04:43", "18:21"),
        20: ("04:43", "18:21"),
        21: ("04:43", "18:20"),
        22: ("04:43", "18:20"),
        23: ("04:43", "18:19"),
        24: ("04:43", "18:19"),
        25: ("04:43", "18:18"),
        26: ("04:42", "18:18"),
        27: ("04:42", "18:18"),
        28: ("04:42", "18:17"),
        29: ("04:42", "18:17"),
        30: ("04:42", "18:16"),
    }


    # ================= UTIL =================
    @staticmethod
    def get_ramadhan_day(today=None):
        if not today:
            today = date.today()
        delta = (today - RamadhanGreeting.RAMADHAN_START).days + 1
        if delta < 1 or delta > 30:
            return None
        return delta

    # ================= LOOP =================
    @tasks.loop(minutes=1)
    async def loop_ramadhan(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.config.get("welcome_channel"))
        if not channel:
            return

        now_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
        now_wita = datetime.now(ZoneInfo("Asia/Makassar"))
        now_wit = datetime.now(ZoneInfo("Asia/Jayapura"))

        hari = self.get_ramadhan_day(now_wib.date())
        if not hari:
            return

        t_wib = now_wib.strftime("%H:%M")
        t_wita = now_wita.strftime("%H:%M")
        t_wit = now_wit.strftime("%H:%M")

        motivasi = random.choice(self.MOTIVASI)

        # ================= WIB =================
        if hari in self.RAMADHAN_WIB:
            imsak, subuh, dzuhur, ashar, maghrib, isya = self.RAMADHAN_WIB[hari]

            jadwal_wib = {
                imsak:   ("⏰ Waktu Imsak Telah Tiba", discord.Color.gold(), self.IMAGE_IMSAK),
                subuh:   ("🕌 Waktu Sholat Subuh", discord.Color.blue(), self.IMAGE_SHOLAT),
                dzuhur:  ("🕌 Waktu Sholat Dzuhur", discord.Color.teal(), self.IMAGE_SHOLAT),
                ashar:   ("🕌 Waktu Sholat Ashar", discord.Color.purple(), self.IMAGE_SHOLAT),
                maghrib: ("🌙 Saatnya Berbuka Puasa", discord.Color.green(), self.IMAGE_BUKA),
                isya:    ("🕌 Waktu Sholat Isya", discord.Color.dark_blue(), self.IMAGE_SHOLAT),
            }

            if t_wib in jadwal_wib:
                title, color, img = jadwal_wib[t_wib]
                await channel.send(embed=self.build_embed(
                    title,
                    t_wib,
                    "Wilayah Jakarta dan sekitarnya",
                    motivasi,
                    color,
                    img,
                    hari
                ))

        # ================= WITA =================
        if hari in self.RAMADHAN_WITA:
            imsak, buka = self.RAMADHAN_WITA[hari]

            if t_wita == imsak:
                await channel.send(embed=self.build_embed(
                    "⏰ Waktu Imsak Telah Tiba",
                    imsak,
                    "Wilayah Makassar dan sekitarnya",
                    motivasi,
                    discord.Color.gold(),
                    self.IMAGE_IMSAK,
                    hari
                ))

            if t_wita == buka:
                await channel.send(embed=self.build_embed(
                    "🌙 Saatnya Berbuka Puasa",
                    buka,
                    "Wilayah Makassar dan sekitarnya",
                    motivasi,
                    discord.Color.green(),
                    self.IMAGE_BUKA,
                    hari
                ))

        # ================= WIT =================
        if hari in self.RAMADHAN_WITA:
            imsak_wita, buka_wita = self.RAMADHAN_WITA[hari]
            imsak_wit = f"{int(imsak_wita[:2]) + 1:02d}{imsak_wita[2:]}"
            buka_wit = f"{int(buka_wita[:2]) + 1:02d}{buka_wita[2:]}"

            if t_wit == imsak_wit:
                await channel.send(embed=self.build_embed(
                    "⏰ Waktu Imsak Telah Tiba",
                    imsak_wit,
                    "Wilayah Jayapura dan sekitarnya",
                    motivasi,
                    discord.Color.gold(),
                    self.IMAGE_IMSAK,
                    hari
                ))

            if t_wit == buka_wit:
                await channel.send(embed=self.build_embed(
                    "🌙 Saatnya Berbuka Puasa",
                    buka_wit,
                    "Wilayah Jayapura dan sekitarnya",
                    motivasi,
                    discord.Color.green(),
                    self.IMAGE_BUKA,
                    hari
                ))

    # ================= EMBED =================
    def build_embed(self, title, time, wilayah, motivasi, color, image_url, hari):
        embed = discord.Embed(
            title=title,
            description=(
                f"📅 **Hari ke-{hari} Ramadhan**\n\n"
                f"🕰️ **{time}**\n"
                f"📍 *{wilayah}*"
            ),
            color=color
        )
        embed.add_field(name="✨ Renungan Ramadhan", value=motivasi, inline=False)
        embed.set_footer(text="Ramadhan Reminder • nanZ Server 🤍")
        embed.set_image(url=image_url)
        return embed

async def setup(bot):
    await bot.add_cog(RamadhanGreeting(bot))
