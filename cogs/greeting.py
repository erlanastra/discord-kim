import discord
from discord.ext import commands, tasks
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import random
import io
import aiohttp

# Import generator gambar kita
from cogs.greeting_gif import generate_greeting_gif


class Greeting(commands.Cog):
    """Greeting Bot NanZ — dengan gambar dinamis dan cuaca real-time"""

    def __init__(self, bot):
        self.bot = bot
        with open("config.json") as f:
            self.config = json.load(f)
        self._weather_cache = None
        self._weather_cache_hour = -1
        self.greet.start()

    # ──────────────────────────────────────────
    # WEATHER FETCH (OpenWeatherMap)
    # ──────────────────────────────────────────
    async def fetch_weather(self) -> str:
        """
        Ambil cuaca real-time dari OpenWeatherMap.
        Butuh config.json berisi:
            "weather_api_key": "YOUR_API_KEY",
            "weather_city": "Jakarta,ID"   <- sesuaikan kota server kalian

        Daftar gratis di: https://openweathermap.org/api
        """
        now_hour = datetime.now(ZoneInfo("Asia/Jakarta")).hour

        # Cache per jam agar tidak spam API
        if self._weather_cache and self._weather_cache_hour == now_hour:
            return self._weather_cache

        api_key = self.config.get("weather_api_key", "")
        city    = "Jakarta,ID"  # hardcoded, tidak ditampilkan ke user

        if not api_key:
            return "N/A (set weather_api_key di config.json)"

        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={city}&appid={api_key}&units=metric&lang=id"
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status != 200:
                        return "Cuaca tidak tersedia"
                    data = await resp.json()
                    temp   = round(data["main"]["temp"])
                    desc   = data["weather"][0]["description"].title()
                    result = f"{temp}°C, {desc}"
                    self._weather_cache = result
                    self._weather_cache_hour = now_hour
                    return result
        except Exception as e:
            print(f"[Greeting] Weather error: {e}")
            return "Cuaca tidak tersedia"

    # ──────────────────────────────────────────
    # SESSION HELPER
    # ──────────────────────────────────────────
    @staticmethod
    def get_session(hour: int) -> str | None:
        """Return session name atau None jika bukan jam greeting"""
        mapping = {6: "pagi", 12: "siang", 18: "sore", 22: "malam"}
        return mapping.get(hour)

    # ──────────────────────────────────────────
    # QUOTES
    # ──────────────────────────────────────────
    QUOTES = [
        "Jangan berhenti sampai kamu bangga! ✨",
        "Senyum itu gratis, tapi pengaruhnya mahal 😄",
        "Semangatmu hari ini menentukan harimu!",
        "Setiap hari adalah kesempatan baru 🌟",
        "Kecil atau besar, setiap langkah maju berharga!",
        "Percaya prosesnya — hasil indah butuh waktu 🌱",
        "Lakukan yang terbaik hari ini, sisanya biarlah 🙌",
    ]

    # ──────────────────────────────────────────
    # MAIN GREETING LOOP
    # ──────────────────────────────────────────
    @tasks.loop(minutes=1)
    async def greet(self):
        await self.bot.wait_until_ready()

        channel_id = self.config.get("welcome_channel")
        channel = self.bot.get_channel(channel_id)
        if not channel:
            print(f"[Greeting] Channel ID {channel_id} tidak ditemukan!")
            return

        now    = datetime.now(ZoneInfo("Asia/Jakarta"))
        hour   = now.hour
        minute = now.minute

        if minute != 0:
            return  # hanya kirim tiap jam tepat

        session = self.get_session(hour)
        if not session:
            return  # bukan jam greeting

        await self._send_greeting(channel, session, now)

    async def _send_greeting(self, channel, session: str, now: datetime):
        """Generate dan kirim greeting image ke channel"""
        # Data waktu
        HARI_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        BULAN_ID = [
            "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        ]
        jam_str  = f"{now.hour:02d}:00 WIB"
        hari     = HARI_ID[now.weekday()]
        tanggal  = f"{now.day} {BULAN_ID[now.month]} {now.year}"
        cuaca    = await self.fetch_weather()
        quote    = random.choice(self.QUOTES)
        srv_name = self.config.get("server_name", "nanZ Server")

        # Generate image bytes
        img_bytes = generate_greeting_gif(
            session=session,
            jam_str=jam_str,
            hari=hari,
            tanggal=tanggal,
            cuaca=cuaca,
            quote=quote,
            server_name=srv_name,
        )

        # Kirim sebagai Discord attachment
        file = discord.File(io.BytesIO(img_bytes), filename=f"greeting_{session}.gif")

        # Opsional: embed minimalis sebagai teks pendamping
        session_labels = {
            "pagi":  ("🌅", "Selamat Pagi!"),
            "siang": ("☀️", "Selamat Siang!"),
            "sore":  ("🌇", "Selamat Sore!"),
            "malam": ("🌙", "Selamat Malam!"),
        }
        emoji, label = session_labels[session]

        embed = discord.Embed(
            description=f"{emoji} **{label}** — {hari}, {tanggal}\n> {quote}",
            color=discord.Color.from_rgb(130, 80, 255)
        )
        embed.set_image(url=f"attachment://greeting_{session}.gif")
        embed.set_footer(text=f"{srv_name} Server •  nanZ Greeting")

        await channel.send(embed=embed, file=file)
        print(f"[Greeting] Gambar {session} dikirim ke #{channel.name}")

    # ──────────────────────────────────────────
    # COMMAND: !testgreet
    # ──────────────────────────────────────────
    @commands.command(name="testgreet")
    async def test_greet(self, ctx, session: str = "pagi"):
        """
        Tes greeting image.
        Usage: !testgreet [pagi|siang|sore|malam]
        """
        valid = ["pagi", "siang", "sore", "malam"]
        if session not in valid:
            await ctx.send(f"⚠️ Session tidak valid. Pilih: {', '.join(valid)}")
            return

        channel_id = self.config.get("welcome_channel")
        channel    = self.bot.get_channel(channel_id)
        if not channel:
            await ctx.send("⚠️ Channel Welcome tidak ditemukan di config.json!")
            return

        now = datetime.now(ZoneInfo("Asia/Jakarta"))
        await ctx.send(f"⏳ Generating greeting **{session}**...")
        await self._send_greeting(channel, session, now)
        await ctx.send(f"✅ Test greeting **{session}** berhasil dikirim ke **#{channel.name}**!")

    @commands.command(name="greetall")
    @commands.has_permissions(administrator=True)
    async def greet_all(self, ctx):
        """Admin only: kirim semua 4 greeting sekaligus untuk preview"""
        channel_id = self.config.get("welcome_channel")
        channel    = self.bot.get_channel(channel_id)
        if not channel:
            await ctx.send("⚠️ Channel Welcome tidak ditemukan!")
            return

        now = datetime.now(ZoneInfo("Asia/Jakarta"))
        await ctx.send("⏳ Generating semua greeting...")
        for session in ["pagi", "siang", "sore", "malam"]:
            await self._send_greeting(channel, session, now)
        await ctx.send("✅ Semua greeting berhasil dikirim!")


async def setup(bot):
    await bot.add_cog(Greeting(bot))