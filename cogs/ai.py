import discord
from discord.ext import commands
import aiohttp
import json
import logging
import os
import time
from collections import defaultdict


# =========================================================
# CONFIG
# =========================================================

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)


API_KEY = config["gemini_api_key"]
AI_CHANNEL = config["ai_channel"]

GEMINI_MODEL = "gemini-3.5-flash"

URL = (
    f"https://generativelanguage.googleapis.com/v1beta/"
    f"models/{GEMINI_MODEL}:generateContent?key={API_KEY}"
)


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(level=logging.INFO)


# =========================================================
# ACTIVITY DATABASE
# =========================================================

ACTIVITY_FILE = "ai_activity.json"


def load_activity():

    if not os.path.exists(ACTIVITY_FILE):
        return {}

    try:
        with open(ACTIVITY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {}


def save_activity(data):

    try:
        with open(ACTIVITY_FILE, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False
            )

    except Exception as e:
        logging.error(f"Gagal menyimpan activity: {e}")


# =========================================================
# AI COG
# =========================================================

class AI(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.chat_history = defaultdict(list)

        self.session = None

        # Statistik aktivitas
        self.activity = load_activity()

        # Voice session
        self.voice_sessions = {}

        # Cache message count agar tidak terlalu sering write
        self.save_counter = 0


    # =====================================================
    # LOAD / UNLOAD
    # =====================================================

    async def cog_load(self):

        self.session = aiohttp.ClientSession()

        logging.info("====================================")
        logging.info("nanZ AI SYSTEM AKTIF")
        logging.info("Gemini Model: %s", GEMINI_MODEL)
        logging.info("Activity Tracking: AKTIF")
        logging.info("====================================")


    async def cog_unload(self):

        if self.session:
            await self.session.close()

        save_activity(self.activity)


    # =====================================================
    # MEMBER ACTIVITY
    # =====================================================

    def get_member_activity(self, member):

        guild_id = str(member.guild.id)
        user_id = str(member.id)

        if guild_id not in self.activity:
            self.activity[guild_id] = {}

        if user_id not in self.activity[guild_id]:

            self.activity[guild_id][user_id] = {
                "messages": 0,
                "voice_seconds": 0,
                "voice_sessions": 0,
                "last_message": None,
                "last_voice": None
            }

        return self.activity[guild_id][user_id]


    # =====================================================
    # MESSAGE TRACKING
    # =====================================================

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        if not message.guild:
            return

        # ---------------------------------------------
        # CATAT AKTIVITAS MEMBER
        # ---------------------------------------------

        stats = self.get_member_activity(message.author)

        stats["messages"] += 1
        stats["last_message"] = int(time.time())

        self.save_counter += 1

        # Simpan setiap 20 message
        if self.save_counter >= 20:

            save_activity(self.activity)

            self.save_counter = 0


        # ---------------------------------------------
        # CEK APAKAH PESAN UNTUK AI
        # ---------------------------------------------

        is_ai_channel = message.channel.id == AI_CHANNEL

        is_mention = self.bot.user in message.mentions

        if not is_ai_channel and not is_mention:
            return


        prompt = message.content


        # Hilangkan mention bot
        if is_mention:

            prompt = prompt.replace(
                f"<@{self.bot.user.id}>",
                ""
            )

            prompt = prompt.replace(
                f"<@!{self.bot.user.id}>",
                ""
            )

            prompt = prompt.strip()


        if not prompt:
            return


        # ---------------------------------------------
        # AI RESPONSE
        # ---------------------------------------------

        async with message.channel.typing():

            history = self.chat_history[message.author.id]

            conversation = self.system_prompt(
                message.guild,
                message.author
            )


            # History user
            for q, a in history[-5:]:

                conversation += (
                    f"\nUser: {q}"
                    f"\nAI: {a}"
                )


            conversation += (
                f"\nUser: {prompt}"
                f"\nAI:"
            )


            payload = {

                "contents": [
                    {
                        "parts": [
                            {
                                "text": conversation
                            }
                        ]
                    }
                ]

            }


            try:

                async with self.session.post(
                    URL,
                    json=payload
                ) as resp:

                    data = await resp.json()


                    # ---------------------------------
                    # GEMINI RATE LIMIT
                    # ---------------------------------

                    if resp.status == 429:

                        await message.reply(
                            "⚠️ **nanZ AI sedang mencapai batas penggunaan.**\n"
                            "Coba lagi beberapa saat nanti.",
                            mention_author=False
                        )

                        return


                    if resp.status != 200:

                        logging.error(
                            f"Gemini Error {resp.status}: {data}"
                        )

                        await message.reply(
                            "⚠️ Coba lagi, server AI sedang penuh.",
                            mention_author=False
                        )

                        return


                    answer = (
                        data["candidates"][0]
                        ["content"]
                        ["parts"][0]
                        ["text"]
                    )


                # Simpan history
                history.append(
                    (
                        prompt,
                        answer
                    )
                )


                if len(history) > 10:
                    history.pop(0)


                # ---------------------------------
                # EMBED RESPONSE
                # ---------------------------------

                embed = discord.Embed(
                    title="🤖 nanZ AI",
                    description=answer[:4000],
                    color=0x5865F2
                )

                embed.set_footer(
                    text=f"Diminta oleh {message.author.display_name}"
                )


                await message.reply(
                    embed=embed,
                    mention_author=False
                )


            except Exception as e:

                logging.exception("Gemini Error")

                await message.reply(
                    f"❌ Terjadi error:\n```{e}```",
                    mention_author=False
                )


    # =====================================================
    # VOICE TRACKING
    # =====================================================

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member,
        before,
        after
    ):

        if member.bot:
            return

        # ---------------------------------------------
        # MASUK VOICE
        # ---------------------------------------------

        if before.channel is None and after.channel is not None:

            self.voice_sessions[member.id] = {
                "started": time.time(),
                "channel": after.channel.name
            }

            stats = self.get_member_activity(member)

            stats["voice_sessions"] += 1
            stats["last_voice"] = int(time.time())

            save_activity(self.activity)


        # ---------------------------------------------
        # PINDAH VOICE
        # ---------------------------------------------

        elif (
            before.channel is not None
            and after.channel is not None
            and before.channel.id != after.channel.id
        ):

            # Hitung session sebelumnya
            if member.id in self.voice_sessions:

                started = self.voice_sessions[member.id]["started"]

                seconds = int(
                    time.time() - started
                )

                stats = self.get_member_activity(member)

                stats["voice_seconds"] += seconds


            self.voice_sessions[member.id] = {
                "started": time.time(),
                "channel": after.channel.name
            }


        # ---------------------------------------------
        # KELUAR VOICE
        # ---------------------------------------------

        elif before.channel is not None and after.channel is None:

            if member.id in self.voice_sessions:

                started = self.voice_sessions[member.id]["started"]

                seconds = int(
                    time.time() - started
                )

                stats = self.get_member_activity(member)

                stats["voice_seconds"] += seconds

                del self.voice_sessions[member.id]


            save_activity(self.activity)


    # =====================================================
    # FORMAT WAKTU
    # =====================================================

    def format_seconds(self, seconds):

        seconds = int(seconds)

        days = seconds // 86400
        seconds %= 86400

        hours = seconds // 3600
        seconds %= 3600

        minutes = seconds // 60

        if days:
            return f"{days}h {hours}j"

        if hours:
            return f"{hours}j {minutes}m"

        return f"{minutes}m"


    # =====================================================
    # SERVER STATISTICS
    # =====================================================

    def get_server_statistics(self, guild):

        # ---------------------------------------------
        # MEMBER STATUS
        # ---------------------------------------------

        online = 0
        idle = 0
        dnd = 0
        offline = 0

        for member in guild.members:

            if member.bot:
                continue

            status = member.status

            if status == discord.Status.online:
                online += 1

            elif status == discord.Status.idle:
                idle += 1

            elif status == discord.Status.dnd:
                dnd += 1

            else:
                offline += 1


        # ---------------------------------------------
        # VOICE
        # ---------------------------------------------

        voice_members = []

        for vc in guild.voice_channels:

            for member in vc.members:

                if member.bot:
                    continue

                voice_members.append(
                    f"{member.display_name} → {vc.name}"
                )


        # ---------------------------------------------
        # ROLE STATISTICS
        # ---------------------------------------------

        role_stats = []

        for role in sorted(
            guild.roles,
            key=lambda r: len(r.members),
            reverse=True
        ):

            if role.is_default():
                continue

            count = len([
                m for m in role.members
                if not m.bot
            ])

            role_stats.append(
                f"{role.name}: {count}"
            )


        # ---------------------------------------------
        # ACTIVITY DATABASE
        # ---------------------------------------------

        guild_activity = self.activity.get(
            str(guild.id),
            {}
        )


        activity_members = []


        for member in guild.members:

            if member.bot:
                continue

            data = guild_activity.get(
                str(member.id),
                {
                    "messages": 0,
                    "voice_seconds": 0,
                    "voice_sessions": 0,
                    "last_message": None,
                    "last_voice": None
                }
            )


            messages = data.get(
                "messages",
                0
            )

            voice_seconds = data.get(
                "voice_seconds",
                0
            )

            # Tambahkan waktu voice yang sedang berlangsung
            if member.id in self.voice_sessions:

                started = self.voice_sessions[
                    member.id
                ]["started"]

                voice_seconds += int(
                    time.time() - started
                )


            activity_score = (
                messages
                + (voice_seconds / 60)
            )


            activity_members.append(
                {
                    "member": member,
                    "messages": messages,
                    "voice_seconds": voice_seconds,
                    "score": activity_score
                }
            )


        # ---------------------------------------------
        # TOP CHAT
        # ---------------------------------------------

        top_chat = sorted(
            activity_members,
            key=lambda x: x["messages"],
            reverse=True
        )[:15]


        top_chat_text = []

        for index, data in enumerate(
            top_chat,
            start=1
        ):

            top_chat_text.append(
                f"{index}. "
                f"{data['member'].display_name} "
                f"— {data['messages']} chat"
            )


        # ---------------------------------------------
        # TOP VOICE
        # ---------------------------------------------

        top_voice = sorted(
            activity_members,
            key=lambda x: x["voice_seconds"],
            reverse=True
        )[:15]


        top_voice_text = []

        for index, data in enumerate(
            top_voice,
            start=1
        ):

            top_voice_text.append(
                f"{index}. "
                f"{data['member'].display_name} "
                f"— {self.format_seconds(data['voice_seconds'])}"
            )


        # ---------------------------------------------
        # TOP ACTIVE
        # ---------------------------------------------

        top_active = sorted(
            activity_members,
            key=lambda x: x["score"],
            reverse=True
        )[:15]


        top_active_text = []

        for index, data in enumerate(
            top_active,
            start=1
        ):

            top_active_text.append(
                f"{index}. "
                f"{data['member'].display_name} "
                f"— {data['messages']} chat, "
                f"{self.format_seconds(data['voice_seconds'])} voice"
            )


        # ---------------------------------------------
        # CHANNEL STATISTICS
        # ---------------------------------------------

        text_channels = []

        for channel in guild.text_channels:

            text_channels.append(
                channel.name
            )


        voice_channels = []

        for channel in guild.voice_channels:

            voice_channels.append(
                f"{channel.name}: {len(channel.members)} orang"
            )


        # ---------------------------------------------
        # STAFF
        # ---------------------------------------------

        staff_members = []

        staff_keywords = [
            "guru besar",
            "owner",
            "admin",
            "moderator",
            "mod",
            "pembina",
            "ketua",
            "wakil ketua",
            "osis",
            "staff",
            "developer",
            "dev"
        ]


        for member in guild.members:

            if member.bot:
                continue

            role_names = [
                role.name.lower()
                for role in member.roles
            ]

            is_staff = any(
                keyword in role_name
                for role_name in role_names
                for keyword in staff_keywords
            )

            if is_staff:

                data = guild_activity.get(
                    str(member.id),
                    {
                        "messages": 0,
                        "voice_seconds": 0
                    }
                )

                staff_members.append(
                    {
                        "member": member,
                        "messages": data.get(
                            "messages",
                            0
                        ),
                        "voice": data.get(
                            "voice_seconds",
                            0
                        )
                    }
                )


        staff_members.sort(
            key=lambda x: (
                x["messages"]
                + x["voice"] / 60
            ),
            reverse=True
        )


        staff_text = []

        for staff in staff_members:

            member = staff["member"]

            status = str(
                member.status
            ).replace(
                "dnd",
                "dnd"
            )

            staff_text.append(
                f"{member.display_name} "
                f"({status}) — "
                f"{staff['messages']} chat, "
                f"{self.format_seconds(staff['voice'])} voice"
            )


        # ---------------------------------------------
        # RETURN
        # ---------------------------------------------

        return {
            "total_members": guild.member_count,
            "human_members": len([
                m for m in guild.members
                if not m.bot
            ]),
            "bots": len([
                m for m in guild.members
                if m.bot
            ]),

            "online": online,
            "idle": idle,
            "dnd": dnd,
            "offline": offline,

            "voice_count": len(voice_members),

            "voice_members": voice_members[:30],

            "roles": role_stats,

            "top_chat": top_chat_text,

            "top_voice": top_voice_text,

            "top_active": top_active_text,

            "text_channels": text_channels,

            "voice_channels": voice_channels,

            "staff": staff_text
        }


    # =====================================================
    # SYSTEM PROMPT
    # =====================================================

    def system_prompt(self, guild, member):

        stats = self.get_server_statistics(
            guild
        )


        roles = "\n".join(
            f"- {role}"
            for role in stats["roles"]
        )

        top_chat = "\n".join(
            stats["top_chat"]
        )

        top_voice = "\n".join(
            stats["top_voice"]
        )

        top_active = "\n".join(
            stats["top_active"]
        )

        voice_members = "\n".join(
            f"- {x}"
            for x in stats["voice_members"]
        )

        voice_channels = "\n".join(
            f"- {x}"
            for x in stats["voice_channels"]
        )

        staff = "\n".join(
            f"- {x}"
            for x in stats["staff"]
        )


        return f"""
Kamu adalah nanZ AI.

Kamu adalah AI resmi milik Discord nanZ Server.

==================================================
IDENTITAS SERVER
==================================================

Nama Server:
nanZ Server

Tanggal Berdiri:
18 Agustus 2025

Tema:
School Community / Sekolahan

Owner:
Kim / Guru Besar

Developer Bot:
Erlan / Tom

==================================================
AKSES STATISTIK SERVER
==================================================

Kamu memiliki akses terhadap statistik server
yang dikirimkan sistem secara real-time.

Gunakan DATA DI BAWAH INI sebagai sumber utama
ketika menjawab pertanyaan tentang server.

JANGAN MENGARANG DATA.

==================================================
STATISTIK MEMBER
==================================================

Total Member:
{stats["total_members"]}

Member Manusia:
{stats["human_members"]}

Bot:
{stats["bots"]}

Online:
{stats["online"]}

Idle:
{stats["idle"]}

Do Not Disturb:
{stats["dnd"]}

Offline:
{stats["offline"]}

Sedang Voice:
{stats["voice_count"]}

==================================================
MEMBER YANG SEDANG VOICE
==================================================

{voice_members if voice_members else "Tidak ada member di voice."}

==================================================
SEMUA ROLE SERVER
==================================================

{roles if roles else "Belum ada role."}

==================================================
TOP MEMBER BERDASARKAN CHAT
==================================================

{top_chat if top_chat else "Belum ada data chat."}

==================================================
TOP MEMBER BERDASARKAN WAKTU VOICE
==================================================

{top_voice if top_voice else "Belum ada data voice."}

==================================================
MEMBER PALING AKTIF
==================================================

{top_active if top_active else "Belum ada data aktivitas."}

==================================================
STATISTIK VOICE CHANNEL
==================================================

{voice_channels if voice_channels else "Tidak ada voice channel."}

==================================================
STAFF SERVER
==================================================

{staff if staff else "Belum terdeteksi staff."}

==================================================
USER YANG SEDANG BERBICARA
==================================================

Nama:
{member.display_name}

User ID:
{member.id}

Status:
{member.status}

Role User:

{", ".join(
    role.name
    for role in member.roles
    if not role.is_default()
) or "Tidak memiliki role khusus"}

==================================================
INFORMASI EVENT nanZ
==================================================

- Girls Corner
- Nobar
- Podcast
- Riddle
- nanZSeratus

==================================================
ATURAN MENJAWAB
==================================================

1. Jangan pernah mengaku sebagai ChatGPT.
2. Jangan pernah mengaku sebagai Gemini.
3. Jika ditanya siapa kamu, jawab nanZ AI.
4. Gunakan Bahasa Indonesia.
5. Gaya santai seperti anggota komunitas.
6. Jika ditanya statistik server, gunakan data real-time.
7. Jangan mengarang nama member.
8. Jangan mengarang jumlah member.
9. Jangan mengarang role.
10. Jangan mengarang aktivitas.
11. Jika data aktivitas belum tersedia, katakan bahwa
    sistem baru mulai mencatat aktivitas tersebut.
12. Jika ditanya member paling aktif, gunakan ranking
    aktivitas yang tersedia.
13. Jika ditanya staff paling aktif, gunakan data staff.
14. Jika ditanya role tertentu, gunakan statistik role.
15. Jika ditanya siapa yang sedang VC, gunakan daftar
    voice member saat ini.
16. Jangan membocorkan API key atau konfigurasi internal.
"""
    

# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        AI(bot)
    )