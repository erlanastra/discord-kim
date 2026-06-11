# =========================================================
# nanZ WORLD CUP 2026 — AUTO MATCH SYSTEM
# FULLY AUTOMATIC: Daily Schedule + Live Score + Goal Alert
# discord.py 2.x | Requires: aiohttp, pytz
# =========================================================

import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
from datetime import datetime, timedelta
import pytz
import os

# =========================================================
# CONFIG — SESUAIKAN INI
# =========================================================

# Simpan API key di environment variable, jangan di source code!
# Cara set: export API_FOOTBALL_KEY="isi_key_kamu_disini"
API_FOOTBALL_KEY  = os.getenv("API_FOOTBALL_KEY", "")
API_FOOTBALL_HOST = "v3.football.api-sports.io"
WC2026_LEAGUE_ID  = 1                            # Update saat WC2026 live di API
WC2026_SEASON     = 2026

WIB = pytz.timezone("Asia/Jakarta")

# Channel IDs — sama dengan worldcup.py
WORLD_CUP_CHAT_ID        = 1512624241999216672
STAFF_CONTROL_CHANNEL_ID = 1512626594773078228

# Jam announcement jadwal harian (WIB)
DAILY_ANNOUNCE_HOUR   = 7    # 07:00 WIB
DAILY_ANNOUNCE_MINUTE = 0

# =========================================================
# EMOJIS — sama dengan worldcup.py
# =========================================================

JOINEMOJI  = "<a:check_yes2:1512649792721911949>"
WRONGEMOJI = "<a:wrong:1512649597070217256>"
WC26EMOJI  = "<:FIFA2026WorldCup:1512635223769354401>"
LINEEMOJI  = "<a:fearZOOM:1512641306722041906>"
ROWEMOJI   = "<a:DarkBlueArrow:1512640150721659020>"

# =========================================================
# GIF untuk announcement — ganti URL sesuai selera
# =========================================================

DAILY_SCHEDULE_GIF = "https://i.imgur.com/o5uSTjn.gif"
GOAL_GIF           = "https://i.imgur.com/lCII7r4.gif"
KICKOFF_GIF        = "https://i.imgur.com/v0Ap6wC.gif"
FULLTIME_GIF       = "https://i.imgur.com/eZFNzYV.gif"

# =========================================================
# COUNTRIES DATA — sama dengan worldcup.py
# =========================================================

COUNTRIES = {
    "CAN": ("Canada",              "🇨🇦", 0xD52B1E),
    "MEX": ("Mexico",              "🇲🇽", 0x006847),
    "USA": ("United States",       "🇺🇸", 0x3C3B6E),
    "JPN": ("Japan",               "🇯🇵", 0xBC002D),
    "IRN": ("Iran",                "🇮🇷", 0x239F40),
    "UZB": ("Uzbekistan",          "🇺🇿", 0x0099B5),
    "KOR": ("South Korea",         "🇰🇷", 0xCD2E3A),
    "JOR": ("Jordan",              "🇯🇴", 0x007A3D),
    "AUS": ("Australia",           "🇦🇺", 0x012169),
    "QAT": ("Qatar",               "🇶🇦", 0x8A1538),
    "KSA": ("Saudi Arabia",        "🇸🇦", 0x006C35),
    "IRQ": ("Iraq",                "🇮🇶", 0x007A3D),
    "ARG": ("Argentina",           "🇦🇷", 0x74ACDF),
    "BRA": ("Brazil",              "🇧🇷", 0x009C3B),
    "ECU": ("Ecuador",             "🇪🇨", 0xFCD116),
    "URU": ("Uruguay",             "🇺🇾", 0x6CCFF6),
    "COL": ("Colombia",            "🇨🇴", 0xFCD116),
    "PAR": ("Paraguay",            "🇵🇾", 0xD52B1E),
    "MAR": ("Morocco",             "🇲🇦", 0xC1272D),
    "TUN": ("Tunisia",             "🇹🇳", 0xE70013),
    "EGY": ("Egypt",               "🇪🇬", 0xCE1126),
    "ALG": ("Algeria",             "🇩🇿", 0x006233),
    "GHA": ("Ghana",               "🇬🇭", 0xFCD116),
    "CPV": ("Cape Verde",          "🇨🇻", 0x003893),
    "RSA": ("South Africa",        "🇿🇦", 0x007749),
    "CIV": ("Ivory Coast",         "🇨🇮", 0xF77F00),
    "SEN": ("Senegal",             "🇸🇳", 0x00853F),
    "COD": ("DR Congo",            "🇨🇩", 0x007FFF),
    "ENG": ("England",             "🏴󠁧󠁢󠁥󠁮󠁧󠁿", 0xCF142B),
    "FRA": ("France",              "🇫🇷", 0x0055A4),
    "CRO": ("Croatia",             "🇭🇷", 0xFF0000),
    "POR": ("Portugal",            "🇵🇹", 0x006600),
    "NOR": ("Norway",              "🇳🇴", 0xBA0C2F),
    "GER": ("Germany",             "🇩🇪", 0x000000),
    "NED": ("Netherlands",         "🇳🇱", 0xFF6600),
    "ESP": ("Spain",               "🇪🇸", 0xAA151B),
    "BEL": ("Belgium",             "🇧🇪", 0xFFD90C),
    "SUI": ("Switzerland",         "🇨🇭", 0xFF0000),
    "SCO": ("Scotland",            "🏴󠁧󠁢󠁳󠁣󠁴󠁿", 0x0065BD),
    "AUT": ("Austria",             "🇦🇹", 0xED2939),
    "SWE": ("Sweden",              "🇸🇪", 0x006AA7),
    "CZE": ("Czech Republic",      "🇨🇿", 0x11457E),
    "TUR": ("Türkiye",             "🇹🇷", 0xE30A17),
    "HTI": ("Haiti",               "🇭🇹", 0x00209F),
    "PAN": ("Panama",              "🇵🇦", 0x005293),
    "CUW": ("Curacao",             "🇨🇼", 0x002B7F),
    "BIH": ("Bosnia & Herzegovina","🇧🇦", 0x002F6C),
}

# =========================================================
# MAPPING API-FOOTBALL TEAM NAME → KODE NEGARA
# =========================================================

API_NAME_TO_CODE = {
    "Canada":               "CAN",
    "Mexico":               "MEX",
    "USA":                  "USA",
    "United States":        "USA",
    "Japan":                "JPN",
    "Iran":                 "IRN",
    "Uzbekistan":           "UZB",
    "South Korea":          "KOR",
    "Korea Republic":       "KOR",
    "Jordan":               "JOR",
    "Australia":            "AUS",
    "Qatar":                "QAT",
    "Saudi Arabia":         "KSA",
    "Iraq":                 "IRQ",
    "Argentina":            "ARG",
    "Brazil":               "BRA",
    "Ecuador":              "ECU",
    "Uruguay":              "URU",
    "Colombia":             "COL",
    "Paraguay":             "PAR",
    "Morocco":              "MAR",
    "Tunisia":              "TUN",
    "Egypt":                "EGY",
    "Algeria":              "ALG",
    "Ghana":                "GHA",
    "Cape Verde":           "CPV",
    "South Africa":         "RSA",
    "Ivory Coast":          "CIV",
    "Côte d'Ivoire":        "CIV",
    "Senegal":              "SEN",
    "DR Congo":             "COD",
    "Congo DR":             "COD",
    "England":              "ENG",
    "France":               "FRA",
    "Croatia":              "CRO",
    "Portugal":             "POR",
    "Norway":               "NOR",
    "Germany":              "GER",
    "Netherlands":          "NED",
    "Spain":                "ESP",
    "Belgium":              "BEL",
    "Switzerland":          "SUI",
    "Scotland":             "SCO",
    "Austria":              "AUT",
    "Sweden":               "SWE",
    "Czech Republic":       "CZE",
    "Czechia":              "CZE",
    "Turkey":               "TUR",
    "Türkiye":              "TUR",
    "Haiti":                "HTI",
    "Panama":               "PAN",
    "Curacao":              "CUW",
    "Bosnia":               "BIH",
    "Bosnia & Herzegovina": "BIH",
}

# =========================================================
# WORDING HYPE
# =========================================================

import random

KICKOFF_WORDING = [
    "Saatnya buktiin siapa yang paling kenceng nge-dukung!",
    "Tendangan pertama sudah dimulai. Siapa yang bakal bawa pulang trofi?",
    "Bola sudah menggelinding. Jangan sampai ketinggalan momen bersejarah ini!",
    "Ini dia yang ditunggu-tunggu. Yuk ramaikan di channel ini!",
    "Pertarungan sesungguhnya dimulai sekarang!",
]

GOAL_WORDING = [
    "Stadion rasanya mau rubuh!",
    "Supporter mana yang paling hype sekarang?",
    "Siapa yang udah teriak dari tadi?",
    "Gol yang bakal dikenang lama!",
    "Selebrasi meledak di seluruh penjuru stadion!",
]

FULLTIME_WORDING = [
    "Pertarungan telah usai!",
    "Hasil akhir sudah di tangan. Gimana perasaan kalian?",
    "Selamat buat tim yang menang!",
    "90 menit penuh drama. Itulah World Cup!",
    "Skor berbicara. Sampai di match berikutnya!",
]

DAILY_WORDING = [
    "Hari ini bakal panas banget di lapangan. Siapkan dirimu!",
    "Jadwal match hari ini sudah keluar, siap-siap begadang ya!",
    "World Cup 2026 makin seru. Cek jadwal hari ini di bawah.",
    "Supporter nanZ, ini dia pertandingan seru hari ini!",
    "Bola akan terus menggelinding. Ini jadwal lengkap hari ini!",
]

NO_MATCH_WORDING = [
    "Tidak ada pertandingan World Cup hari ini. Istirahat dulu ya!",
    "Lapangan sepi hari ini, tapi nantikan match seru berikutnya!",
    "Tidak ada match hari ini. Tapi semangat supporter tidak pernah padam!",
]

# =========================================================
# HELPER — ROLE SUPPORTER
# =========================================================

def get_supporter_role(
    guild: discord.Guild,
    code: str
) -> discord.Role | None:
    if code not in COUNTRIES:
        return None
    name, emoji, _ = COUNTRIES[code]
    return discord.utils.get(
        guild.roles,
        name=f"{emoji} {name} Supporter"
    )

# =========================================================
# HELPER — FORMAT JAM WIB
# =========================================================

def format_wib(utc_dt: datetime) -> str:
    wib_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(WIB)
    return wib_dt.strftime("%H:%M WIB")

def format_date_wib(utc_dt: datetime) -> str:
    wib_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(WIB)
    DAYS_ID = [
        "Senin","Selasa","Rabu","Kamis",
        "Jumat","Sabtu","Minggu"
    ]
    MONTHS_ID = [
        "","Januari","Februari","Maret","April","Mei","Juni",
        "Juli","Agustus","September","Oktober","November","Desember"
    ]
    day_name = DAYS_ID[wib_dt.weekday()]
    return f"{day_name}, {wib_dt.day} {MONTHS_ID[wib_dt.month]} {wib_dt.year}"

# =========================================================
# LIVE MATCH VIEW — tombol End Match (admin only)
# =========================================================

class LiveMatchView(discord.ui.View):

    def __init__(self, cog, fixture_id: int):
        super().__init__(timeout=None)
        self.cog        = cog
        self.fixture_id = fixture_id

    @discord.ui.button(
        label="End Match",
        style=discord.ButtonStyle.danger,
        custom_id="end_match_btn",
        emoji="⏹️"
    )
    async def end_match(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                f"{WRONGEMOJI} Hanya admin yang bisa mengakhiri match.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)
        await self.cog.force_end_match(
            interaction.guild,
            self.fixture_id
        )
        await interaction.followup.send(
            embed=discord.Embed(
                description=f"{JOINEMOJI} Match telah diakhiri secara manual.",
                color=0x8A2BE2
            ),
            ephemeral=True
        )

# =========================================================
# MAIN COG
# =========================================================

class WorldCupMatch(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # { (fixture_id, guild_id): { ... state match ... } }
        self.active_matches: dict[tuple, dict] = {}

        # Tanggal terakhir daily announce dikirim per guild { guild_id: "YYYY-MM-DD" }
        self.last_announced_date: dict[int, str] = {}

        # Lock untuk mencegah race condition
        self._match_lock = asyncio.Lock()

        # Shared aiohttp session — dibuat sekali, ditutup saat cog unload
        self._session: aiohttp.ClientSession | None = None

        self.poll_live_scores.start()
        self.check_daily_announce.start()
        self.check_upcoming_matches.start()

    def cog_unload(self):
        self.poll_live_scores.cancel()
        self.check_daily_announce.cancel()
        self.check_upcoming_matches.cancel()
        if self._session and not self._session.closed:
            asyncio.create_task(self._session.close())

    async def _get_session(self) -> aiohttp.ClientSession:
        """Lazy-init shared session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    # =========================================================
    # API — BASE REQUEST
    # =========================================================

    async def _api_get(self, endpoint: str, params: dict) -> dict | None:
        if not API_FOOTBALL_KEY:
            print("[WC] ERROR: API_FOOTBALL_KEY tidak di-set di environment variable!")
            return None

        url     = f"https://{API_FOOTBALL_HOST}/{endpoint}"
        headers = {"x-apisports-key": API_FOOTBALL_KEY}
        try:
            session = await self._get_session()
            async with session.get(
                url, params=params, headers=headers,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    print(f"[WC] API {endpoint} status {resp.status}")
                    return None
                return await resp.json()
        except Exception as e:
            print(f"[WC] API error {endpoint}: {e}")
            return None

    # =========================================================
    # API — FETCH FIXTURES HARI INI (UTC)
    # =========================================================

    async def fetch_today_fixtures(self) -> list[dict]:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        data  = await self._api_get("fixtures", {
            "league": WC2026_LEAGUE_ID,
            "season": WC2026_SEASON,
            "date":   today,
        })
        if not data:
            return []
        return data.get("response", [])

    # =========================================================
    # API — FETCH SINGLE FIXTURE
    # =========================================================

    async def fetch_fixture(self, fixture_id: int) -> dict | None:
        data = await self._api_get("fixtures", {"id": fixture_id})
        if not data:
            return None
        responses = data.get("response", [])
        return responses[0] if responses else None

    # =========================================================
    # API — FETCH EVENTS (GOALS)
    # =========================================================

    async def fetch_events(self, fixture_id: int) -> list[dict]:
        data = await self._api_get(
            "fixtures/events",
            {"fixture": fixture_id}
        )
        if not data:
            return []
        return data.get("response", [])

    # =========================================================
    # HELPER — PARSE FIXTURE → match_data dict
    # =========================================================

    def parse_fixture(self, f: dict) -> dict | None:
        home_api = f["teams"]["home"]["name"]
        away_api = f["teams"]["away"]["name"]

        home_code = API_NAME_TO_CODE.get(home_api)
        away_code = API_NAME_TO_CODE.get(away_api)

        if not home_code or not away_code:
            return None

        kick_utc_str = f["fixture"]["date"]
        try:
            kick_utc = datetime.fromisoformat(
                kick_utc_str.replace("Z", "+00:00")
            )
        except Exception:
            kick_utc = datetime.utcnow()

        status     = f["fixture"]["status"]["short"]
        minute     = f["fixture"]["status"]["elapsed"] or 0
        home_score = f["goals"]["home"] if f["goals"]["home"] is not None else 0
        away_score = f["goals"]["away"] if f["goals"]["away"] is not None else 0

        return {
            "fixture_id":        f["fixture"]["id"],
            "home_code":         home_code,
            "away_code":         away_code,
            "home_score":        home_score,
            "away_score":        away_score,
            "minute":            minute,
            "status":            status,
            "kickoff_utc":       kick_utc,
            "message_id":        None,
            "guild_id":          None,
            "goal_events_seen":  set(),
            "last_scorer":       None,
            "last_scorer_team":  None,
            "kickoff_sent":      False,
        }

    # =========================================================
    # TASK — CEK JADWAL HARIAN (setiap menit)
    # =========================================================

    @tasks.loop(minutes=1)
    async def check_daily_announce(self):
        """
        Setiap menit cek apakah sudah waktunya kirim jadwal harian.
        Kirim sekali per hari per guild jam DAILY_ANNOUNCE_HOUR:DAILY_ANNOUNCE_MINUTE WIB.
        Juga handle bot restart yang melewati jam announce.
        """
        try:
            now_wib   = datetime.now(WIB)
            today_str = now_wib.strftime("%Y-%m-%d")

            # Sudah lewat jam announce?
            passed_announce = (
                now_wib.hour > DAILY_ANNOUNCE_HOUR or
                (
                    now_wib.hour   == DAILY_ANNOUNCE_HOUR and
                    now_wib.minute >= DAILY_ANNOUNCE_MINUTE
                )
            )
            if not passed_announce:
                return

            for guild in self.bot.guilds:
                # Sudah announce hari ini untuk guild ini?
                if self.last_announced_date.get(guild.id) == today_str:
                    continue

                self.last_announced_date[guild.id] = today_str
                await self._send_daily_schedule(guild)

        except Exception as e:
            print(f"[WC] check_daily_announce error: {e}")

    @check_daily_announce.before_loop
    async def before_daily(self):
        await self.bot.wait_until_ready()

    # =========================================================
    # TASK — CEK MATCH YANG AKAN / SEDANG BERLANGSUNG (tiap menit)
    # =========================================================

    @tasks.loop(minutes=1)
    async def check_upcoming_matches(self):
        """
        Cek fixture WC2026 hari ini, auto-start tracking
        jika match sudah dimulai dan belum ada di active_matches.
        """
        try:
            fixtures = await self.fetch_today_fixtures()
            for f in fixtures:
                fixture_id = f["fixture"]["id"]
                status     = f["fixture"]["status"]["short"]

                LIVE_STATUSES = {"1H", "HT", "2H", "ET", "P", "LIVE", "BT"}
                if status not in LIVE_STATUSES:
                    continue

                match_data = self.parse_fixture(f)
                if not match_data:
                    continue

                for guild in self.bot.guilds:
                    key = (fixture_id, guild.id)
                    if key in self.active_matches:
                        continue

                    async with self._match_lock:
                        # Double-check setelah acquire lock
                        if key not in self.active_matches:
                            await self._auto_start_match(guild, match_data.copy())

        except Exception as e:
            print(f"[WC] check_upcoming_matches error: {e}")

    @check_upcoming_matches.before_loop
    async def before_upcoming(self):
        await self.bot.wait_until_ready()

    # =========================================================
    # TASK — POLL LIVE SCORES (tiap 60 detik)
    # =========================================================

    @tasks.loop(seconds=60)
    async def poll_live_scores(self):
        if not self.active_matches:
            return

        async with self._match_lock:
            for key, match_data in list(self.active_matches.items()):
                try:
                    await self._update_match(key, match_data)
                except Exception as e:
                    print(f"[WC] Poll error {key}: {e}")

    @poll_live_scores.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()

    # =========================================================
    # SEND DAILY SCHEDULE
    # =========================================================

    async def _send_daily_schedule(self, guild: discord.Guild):
        """Kirim announcement jadwal match hari ini ke guild tertentu."""
        fixtures = await self.fetch_today_fixtures()

        wc_channel = guild.get_channel(WORLD_CUP_CHAT_ID)
        if not wc_channel:
            return

        date_str = format_date_wib(datetime.utcnow())

        # Filter fixture yang dikenali
        known = []
        for f in fixtures:
            md = self.parse_fixture(f)
            if md:
                known.append((f, md))

        # =============================================
        # TIDAK ADA MATCH HARI INI
        # =============================================

        if not known:
            embed = discord.Embed(
                title=f"{WC26EMOJI} Jadwal Hari Ini — {date_str}",
                description=(
                    f"{LINEEMOJI * 10}\n\n"
                    f"**{random.choice(NO_MATCH_WORDING)}**\n\n"
                    f"{LINEEMOJI * 10}"
                ),
                color=0x8A2BE2
            )
            embed.set_image(url=DAILY_SCHEDULE_GIF)
            embed.set_footer(text="nanZ WC26")
            await wc_channel.send(embed=embed)
            return

        # =============================================
        # ADA MATCH — BUAT EMBED
        # =============================================

        match_lines = []
        all_ping_roles = []

        for idx, (f, md) in enumerate(known, start=1):
            home_name, home_emoji, _ = COUNTRIES[md["home_code"]]
            away_name, away_emoji, _ = COUNTRIES[md["away_code"]]
            kick_wib = format_wib(md["kickoff_utc"])

            line = (
                f"{ROWEMOJI} **Match {idx}**\n"
                f"┗ {home_emoji} **{home_name}** vs **{away_name}** {away_emoji}\n"
                f"┗ Kickoff: **{kick_wib}**"
            )
            match_lines.append(line)

            for code in (md["home_code"], md["away_code"]):
                role = get_supporter_role(guild, code)
                if role and role not in all_ping_roles:
                    all_ping_roles.append(role)

        matches_text = "\n\n".join(match_lines)
        hype_text    = random.choice(DAILY_WORDING)

        embed = discord.Embed(
            title=f"{WC26EMOJI} Jadwal Hari Ini — {date_str}",
            description=(
                f"{LINEEMOJI * 10}\n\n"
                f"_{hype_text}_\n\n"
                f"{matches_text}\n\n"
                f"{LINEEMOJI * 10}\n"
                f"*Semua waktu dalam WIB (UTC+7)*"
            ),
            color=0x8A2BE2
        )
        embed.set_image(url=DAILY_SCHEDULE_GIF)
        embed.set_footer(text=f"nanZ WC26 • {len(known)} match hari ini")

        ping_text = " ".join(r.mention for r in all_ping_roles)

        await wc_channel.send(
            content=ping_text if ping_text else None,
            embed=embed
        )

        print(f"[WC] Daily schedule sent to {guild.name}: {len(known)} matches")

    # =========================================================
    # AUTO START MATCH
    # =========================================================

    async def _auto_start_match(
        self,
        guild: discord.Guild,
        match_data: dict
    ):
        """Kirim embed kickoff dan mulai tracking."""
        wc_channel = guild.get_channel(WORLD_CUP_CHAT_ID)
        if not wc_channel:
            return

        fixture_id = match_data["fixture_id"]
        home_code  = match_data["home_code"]
        away_code  = match_data["away_code"]

        home_name, home_emoji, _ = COUNTRIES[home_code]
        away_name, away_emoji, _ = COUNTRIES[away_code]

        kick_wib  = format_wib(match_data["kickoff_utc"])
        hype      = random.choice(KICKOFF_WORDING)

        # Ping role
        home_role  = get_supporter_role(guild, home_code)
        away_role  = get_supporter_role(guild, away_code)
        ping_parts = [r.mention for r in [home_role, away_role] if r]
        ping_text  = " ".join(ping_parts)

        embed = discord.Embed(
            title=f"{WC26EMOJI} Kickoff!",
            description=(
                f"{LINEEMOJI * 10}\n\n"
                f"## {home_emoji} {home_name}  `0 — 0`  {away_emoji} {away_name}\n\n"
                f"Kickoff: **{kick_wib}**\n\n"
                f"_{hype}_\n\n"
                f"{LINEEMOJI * 10}"
            ),
            color=0x2ECC71,
            timestamp=datetime.utcnow()
        )
        embed.set_image(url=KICKOFF_GIF)
        embed.set_footer(text="nanZ WC26 • Live Score Update")

        view = LiveMatchView(self, fixture_id)

        msg = await wc_channel.send(
            content=ping_text if ping_text else None,
            embed=embed,
            view=view
        )

        match_data["message_id"] = msg.id
        match_data["guild_id"]   = guild.id
        match_data["kickoff_sent"] = True

        key = (fixture_id, guild.id)
        self.active_matches[key] = match_data

        print(f"[WC] Auto-started: {home_code} vs {away_code} (fixture {fixture_id}) guild {guild.name}")

    # =========================================================
    # UPDATE MATCH
    # =========================================================

    async def _update_match(
        self,
        key: tuple,
        match_data: dict
    ):
        guild = self.bot.get_guild(match_data["guild_id"])
        if not guild:
            return

        wc_channel = guild.get_channel(WORLD_CUP_CHAT_ID)
        if not wc_channel:
            return

        fixture = await self.fetch_fixture(match_data["fixture_id"])
        if not fixture:
            return

        status         = fixture["fixture"]["status"]["short"]
        minute         = fixture["fixture"]["status"]["elapsed"] or 0
        home_score_new = fixture["goals"]["home"] if fixture["goals"]["home"] is not None else 0
        away_score_new = fixture["goals"]["away"] if fixture["goals"]["away"] is not None else 0

        is_new_goal = (
            home_score_new != match_data["home_score"] or
            away_score_new != match_data["away_score"]
        )

        match_data["home_score"] = home_score_new
        match_data["away_score"] = away_score_new
        match_data["minute"]     = minute
        match_data["status"]     = status

        is_final = status in ("FT", "AET", "PEN", "AWD", "WO")

        # =============================================
        # PROSES GOL BARU
        # =============================================

        if is_new_goal:
            events = await self.fetch_events(match_data["fixture_id"])
            goals  = [
                e for e in events
                if e.get("type") == "Goal"
                and e.get("detail") not in ("Missed Penalty",)
            ]

            for ev in reversed(goals):
                ev_key = (
                    ev["time"]["elapsed"],
                    ev["player"]["name"],
                    ev["team"]["name"]
                )
                if ev_key not in match_data["goal_events_seen"]:
                    match_data["goal_events_seen"].add(ev_key)
                    match_data["last_scorer"]      = ev["player"]["name"]
                    home_api                       = fixture["teams"]["home"]["name"]
                    match_data["last_scorer_team"] = (
                        "home"
                        if ev["team"]["name"].lower() == home_api.lower()
                        else "away"
                    )
                    await self._send_goal_alert(wc_channel, match_data, guild)
                    await self._update_live_embed(wc_channel, match_data, is_final=False)
                    break

        # =============================================
        # FULL TIME
        # =============================================

        if is_final:
            await self._send_fulltime(wc_channel, match_data, guild)
            del self.active_matches[key]
            print(f"[WC] Match selesai: fixture {match_data['fixture_id']}")

    # =========================================================
    # KIRIM ALERT GOL
    # =========================================================

    async def _send_goal_alert(
        self,
        channel: discord.TextChannel,
        match_data: dict,
        guild: discord.Guild
    ):
        home_code = match_data["home_code"]
        away_code = match_data["away_code"]

        home_name, home_emoji, _ = COUNTRIES[home_code]
        away_name, away_emoji, _ = COUNTRIES[away_code]

        scorer_team  = match_data["last_scorer_team"]
        scorer_name  = match_data["last_scorer"]
        goal_code    = home_code if scorer_team == "home" else away_code
        goal_name    = home_name if scorer_team == "home" else away_name
        goal_emoji   = home_emoji if scorer_team == "home" else away_emoji
        embed_color  = COUNTRIES[goal_code][2]

        hs  = match_data["home_score"]
        as_ = match_data["away_score"]
        hype = random.choice(GOAL_WORDING)

        embed = discord.Embed(
            title=f"⚽ Goooool! — {goal_emoji} {goal_name}",
            description=(
                f"{LINEEMOJI * 10}\n\n"
                f"**{scorer_name}** — menit ke-**{match_data['minute']}'**\n\n"
                f"**Skor**\n"
                f"## {home_emoji} {home_name}  `{hs} — {as_}`  {away_emoji} {away_name}\n\n"
                f"_{hype}_\n\n"
                f"{LINEEMOJI * 10}"
            ),
            color=embed_color,
            timestamp=datetime.utcnow()
        )
        embed.set_image(url=GOAL_GIF)
        embed.set_footer(text=f"nanZ WC26 • Menit ke-{match_data['minute']}")

        home_role  = get_supporter_role(guild, home_code)
        away_role  = get_supporter_role(guild, away_code)
        ping_parts = [r.mention for r in [home_role, away_role] if r]
        ping_text  = " ".join(ping_parts)

        await channel.send(
            content=ping_text if ping_text else None,
            embed=embed
        )

    # =========================================================
    # UPDATE EMBED LIVE (edit pesan kickoff)
    # =========================================================

    async def _update_live_embed(
        self,
        channel: discord.TextChannel,
        match_data: dict,
        is_final: bool = False
    ):
        if not match_data["message_id"]:
            return

        home_code = match_data["home_code"]
        away_code = match_data["away_code"]

        home_name, home_emoji, home_color = COUNTRIES[home_code]
        away_name, away_emoji, away_color = COUNTRIES[away_code]

        hs  = match_data["home_score"]
        as_ = match_data["away_score"]

        if hs > as_:
            color = home_color
        elif as_ > hs:
            color = away_color
        else:
            color = 0x8A2BE2

        status_label = (
            "Full Time"
            if is_final
            else f"Live — menit ke-{match_data['minute']}'"
        )

        embed = discord.Embed(
            title=f"{WC26EMOJI} Live Score — {status_label}",
            description=(
                f"{LINEEMOJI * 10}\n\n"
                f"## {home_emoji} {home_name}  `{hs} — {as_}`  {away_emoji} {away_name}\n\n"
                f"{LINEEMOJI * 10}"
            ),
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="nanZ WC26 • Live Score Update")

        try:
            msg = await channel.fetch_message(match_data["message_id"])
            if is_final:
                await msg.edit(embed=embed, view=None)
            else:
                await msg.edit(embed=embed)
        except discord.NotFound:
            pass

    # =========================================================
    # SEND FULL TIME
    # =========================================================

    async def _send_fulltime(
        self,
        channel: discord.TextChannel,
        match_data: dict,
        guild: discord.Guild
    ):
        # Edit live embed dulu
        await self._update_live_embed(channel, match_data, is_final=True)

        home_code = match_data["home_code"]
        away_code = match_data["away_code"]

        home_name, home_emoji, home_color = COUNTRIES[home_code]
        away_name, away_emoji, away_color = COUNTRIES[away_code]

        hs  = match_data["home_score"]
        as_ = match_data["away_score"]

        if hs > as_:
            winner_line = f"**{home_name}** menang!"
            embed_color = home_color
        elif as_ > hs:
            winner_line = f"**{away_name}** menang!"
            embed_color = away_color
        else:
            winner_line = "Imbang! Drama mungkin belum berakhir..."
            embed_color = 0x8A2BE2

        hype = random.choice(FULLTIME_WORDING)

        embed = discord.Embed(
            title=f"⏹️ Full Time!",
            description=(
                f"{LINEEMOJI * 10}\n\n"
                f"## {home_emoji} {home_name}  `{hs} — {as_}`  {away_emoji} {away_name}\n\n"
                f"🏆 {winner_line}\n\n"
                f"_{hype}_\n\n"
                f"{LINEEMOJI * 10}"
            ),
            color=embed_color,
            timestamp=datetime.utcnow()
        )
        embed.set_image(url=FULLTIME_GIF)
        embed.set_footer(text="nanZ WC26 • Full Time")

        home_role  = get_supporter_role(guild, home_code)
        away_role  = get_supporter_role(guild, away_code)
        ping_parts = [r.mention for r in [home_role, away_role] if r]
        ping_text  = " ".join(ping_parts)

        await channel.send(
            content=ping_text if ping_text else None,
            embed=embed
        )

    # =========================================================
    # FORCE END MATCH (tombol admin)
    # =========================================================

    async def force_end_match(
        self,
        guild: discord.Guild,
        fixture_id: int
    ):
        key = (fixture_id, guild.id)
        if key not in self.active_matches:
            return

        match_data = self.active_matches[key]
        wc_channel = guild.get_channel(WORLD_CUP_CHAT_ID)
        if wc_channel:
            await self._send_fulltime(wc_channel, match_data, guild)
        del self.active_matches[key]

    # =========================================================
    # COMMAND !wcschedule — paksa kirim jadwal hari ini (admin)
    # =========================================================

    @commands.command(name="wcschedule")
    @commands.has_permissions(administrator=True)
    async def wc_schedule_cmd(self, ctx: commands.Context):
        """
        !wcschedule — Paksa kirim jadwal match hari ini sekarang.
        Berguna untuk test atau kalau bot restart.
        """
        if ctx.channel.id != STAFF_CONTROL_CHANNEL_ID:
            return

        await ctx.message.add_reaction("⏳")
        await self._send_daily_schedule(ctx.guild)
        await ctx.message.add_reaction("✅")

    # =========================================================
    # READY
    # =========================================================

    @commands.Cog.listener()
    async def on_ready(self):
        print("[WC Match] Auto Match System berhasil dimuat.")
        print(
            f"[WC Match] Daily announce: "
            f"{DAILY_ANNOUNCE_HOUR:02d}:{DAILY_ANNOUNCE_MINUTE:02d} WIB"
        )
        if not API_FOOTBALL_KEY:
            print("[WC Match] WARNING: API_FOOTBALL_KEY tidak ditemukan di environment!")


# =========================================================
# SETUP
# =========================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(WorldCupMatch(bot))


# =========================================================
# CATATAN SETUP
# =========================================================
#
# 1. INSTALL DEPENDENCY
#    pip install aiohttp pytz
#
# 2. SET API KEY (jangan taruh di source code!)
#    Linux/Mac : export API_FOOTBALL_KEY="isi_key_disini"
#    Windows   : set API_FOOTBALL_KEY=isi_key_disini
#    Atau pakai file .env + python-dotenv:
#      pip install python-dotenv
#      buat file .env berisi: API_FOOTBALL_KEY=isi_key_disini
#      tambahkan di main.py: from dotenv import load_dotenv; load_dotenv()
#
# 3. DAFTARKAN COG di main.py / bot.py
#    await bot.load_extension("worldcup_match")
#
# 4. LEAGUE ID (WC2026_LEAGUE_ID)
#    Cek ID resmi WC2026 saat tournament mulai:
#    GET /leagues?name=FIFA+World+Cup&season=2026
#
# 5. GIF — Ganti path/URL di bagian GIF Config sesuai selera
#    Bisa pakai Giphy / Tenor, pastikan URL langsung ke file .gif
#
# 6. INTEGRASI KE StaffView (worldcup.py) — OPSIONAL
#    Tambahkan tombol ini ke class StaffView di worldcup.py:
#
#      @discord.ui.button(
#          label="Jadwal Hari Ini",
#          emoji="📅",
#          style=discord.ButtonStyle.primary,
#          custom_id="send_wc_schedule"
#      )
#      async def send_schedule(self, interaction, button):
#          cog = interaction.client.get_cog("WorldCupMatch")
#          if not cog:
#              return await interaction.response.send_message(
#                  "Cog tidak aktif.", ephemeral=True
#              )
#          await interaction.response.defer(ephemeral=True)
#          await cog._send_daily_schedule(interaction.guild)
#          await interaction.followup.send(
#              embed=discord.Embed(
#                  description="Jadwal hari ini sudah dikirim.",
#                  color=0x8A2BE2
#              ), ephemeral=True
#          )
#
# =========================================================