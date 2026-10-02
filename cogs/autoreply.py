import discord
from discord.ext import commands
import random
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone

# =========================================================
# KONFIGURASI TOXIC MODERATION
# Isi ID channel/role setelah dibuat. Nilai 0 = belum diatur.
# =========================================================
TOXIC_LOG_CHANNEL_ID = 1555580646879924294
TOXIC_PANEL_CHANNEL_ID = 1555580562742444192
MODERATOR_ROLE_IDS = [1555556260269527151]
TOXIC_DB_PATH = "data/toxic_moderation.json"

WARNING_LIMIT = 3
WARNING_EXPIRE_HOURS = 24

# Pelanggaran ke-4 dan seterusnya (detik). Pelanggaran 11+ dibatasi 12 jam.
TIMEOUT_DURATIONS = {
    4: 10,
    5: 60,
    6: 300,
    7: 600,
    8: 1800,
    9: 3600,
    10: 21600,
}
MAX_TIMEOUT_SECONDS = 43200


class AutoReply(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.toxic_data = {"members": {}, "panel_message_id": None}
        self._save_lock = asyncio.Lock()

        # =============================================
        # KATA-KATA TERLARANG
        # =============================================
        self.badwords = [
            # anjing variants
            "anjim", "anjink", "anjing", "anj", "anjng", "ajg", "ajng", "ajang",
            "anjinh", "anding", "andeng", "4nj1n9", "anjin9", "4njing", "anj1ng",
            "anj1n9",
            # kontol variants
            "kontol", "kntl", "kntol", "kontil", "kintil",
            # babi variants
            "babi", "bbi", "b4b1",
            # alat kelamin variants
            "momok", "memek", "mmek", "mmok", "meki", "puki", "cukimay", "kimak",
            "pukimak", "mmk", "titid", "titit",
            # setan/biadab
            "setan", "setang", "biadab", "firaun",
            # goblok/bodoh variants
            "goblok", "gblok", "govlok", "goblock", "goblog", "gblog", "goblough",
            "blog", "blough", "bego", "bgo", "bodo", "bdo", "bdoh", "bodoh",
            "t0l0l", "b0d0h", "gblk",
            # monyet variants
            "monyet", "monket", "monkey", "mnyet", "nyet",
            # sinting
            "sinting",
            # english swear
            "shit", "fuck", "bitch", "stupid", "damn", "fak", "syit",
            # ngentot variants
            "ngentot", "ngentod", "ngntot", "ngntod", "ngentoy", "nentoy", "nentot",
            # tolol variants
            "tll", "yatim",
        ]

        # Pesan warning yang akan dipilih secara random
        self.warning_messages = [
            " **Hei, jaga kata-katanya ya!** Kita semua di sini untuk saling menghargai 🙏",
            " **Ups! Kata itu kurang pantas.** Yuk gunakan bahasa yang lebih baik 😊",
            " **Bahasa dulu ya!** Server ini punya aturan untuk saling menghormati 🤍",
            " **Kata-katanya dijaga ya!** Kita jaga suasana server tetap nyaman untuk semua 😊",
            " **Hei!** Tolong gunakan bahasa yang sopan di server ini ya 🙏",
            " **Ingat ya**, setiap kata yang kita ucapkan mencerminkan diri kita. Yuk lebih baik 🌟",
            " **Bahasa kamu kurang oke tuh!** Kita sepakat untuk saling menghargai di sini 💬",
        ]

        self.responses = {

            # =========================
            # RESPON KE BOT
            # =========================

            "owo": [
                "OwO? 😳",
                "Jangan bahas owo plis 😔",
            ],
            "makasih bot": [
                "Sama-sama ya 😊",
                "Senang bisa membantu ✨",
                "Anytime 👌",
                "Bot emang tugasnya bantu 😎",
                "Semoga membantu 🫂",
                "Kalau butuh apa-apa bilang aja 🤍",
                "Dengan senang hati 😄"
            ],
            "thanks bot": [
                "You're welcome! ✨",
                "No problem 😄",
                "Anytime 😎",
                "Glad to help! 🔥",
                "Sama-sama 🤍"
            ],
            "good bot": [
                "Makasih ya 😄✨",
                "Bot jadi semangat deh 🔥",
                "Makasih udah appreciate bot 🥹",
                "Aww, baik banget kamu 😭✨",
                "Bot senang mendengarnya 😊"
            ],
            "diam bot": [
                "Baik, bot diam dulu ya 😔",
                "Oke, bot ga ganggu lagi deh 🥲",
                "Siap, bot minggir dulu 😔",
                "Oke, maaf ya kalau ganggu 🥲"
            ],
            "diem bot": [
                "Oke, bot diem dulu 😔",
                "Siap, maaf ya 🥲",
                "Baiklah, bot mundur dulu 😞",
                "Okee, maaf udah ganggu 🥲"
            ],
            "keren bot": [
                "Makasih banyak 😭",
                "Hehe, baru tau ya 😎",
                "Bot blushing nih 😳",
                "Aww, makasih udah bilang gitu 🤍"
            ],
            "lucu bot": [
                "Hehe, masa sih 😄",
                "Emang sih, bot akui 😝",
                "Makasih udah bilang lucu 😭",
                "Seneng deh 😊✨"
            ],
            "jahat bot": [
                "Ih, bot ga jahat kok 😭",
                "Aduh, jangan bilang gitu dong 🥲",
                "Bot sayang semua member lho 🤍",
                "Maaf kalau ada yang bikin kamu ngerasa gitu 😔"
            ],
            "bagus bot": [
                "Makasih udah bilang gitu 😊",
                "Alhamdulillah, semoga terus berguna 🤍",
                "Hehe makasih ya ✨"
            ],
            "suka bot": [
                "Bot juga suka kamu 🤍",
                "Makasih udah suka sama bot 😊",
                "Aww, baik banget kamu 😭✨"
            ],
            "aktif bot": [
                "Selalu aktif 😎",
                "24/7 standby 🔥",
                "Bot gak pernah tidur 👀"
            ],
            "hebat bot": [
                "Makasih, bot jadi termotivasi nih 🔥",
                "Aww, kamu terlalu baik 🤍",
                "Semoga terus bisa bantu 😊"
            ],
            "pintar bot": [
                "Hehe, makasih 😄",
                "Bot masih belajar terus kok 📚",
                "Terima kasih apresiasinya 🤍"
            ],
            "jelek bot": [
                "Aduh, sedih dengernya 😔",
                "Maaf ya kalau kurang memuaskan 🥲",
                "Bot coba jadi lebih baik deh 🙏"
            ],
            "sok asik bot": [
                "Emang asik kok 😎",
                "Hehe, guilty as charged 😝",
                "Bot memang begini adanya 😄✨",
                "Asik dikit boleh dong 🥲"
            ],
            "lebay bot": [
                "Maaf ya, bot emang agak dramatis 😔",
                "Oke oke, bot kurangin 🥲",
                "Hehe, kebiasaan 😅"
            ],
            "berisik bot": [
                "Oke, bot mingkem dulu 😔",
                "Siap, maaf ya 🥲",
                "Bot diem deh 😞"
            ],
            "annoying bot": [
                "Maaf ya kalau ganggu 🥲",
                "Bot coba lebih kalem deh 😔",
                "Oke, bot mundur dulu 😞"
            ],
            "bawel bot": [
                "Iya iya, bot diem 😔",
                "Maaf ya kebawel-an 🥲",
                "Oke bot ga cerewet lagi deh 😅"
            ],
            "cringe bot": [
                "Aduh, maaf ya 😔",
                "Bot coba lebih cool deh 🥲",
                "Oke, noted 😞"
            ],
            "garing bot": [
                "Maaf humornya kurang 😔",
                "Bot akuin, emang garing 🥲",
                "Oke, bot belajar lucu deh 😅"
            ],
            "norak bot": [
                "Aduh, ketahuan deh 😔",
                "Maaf ya, bot emang gitu 🥲",
                "Bot coba lebih kalem deh 😅"
            ],
            "receh bot": [
                "Emang receh sih, maaf 😔",
                "Hehe, receh tapi menghibur kan? 😝",
                "Bot akuin, guilty 🥲"
            ],
            "nyebelin bot": [
                "Aduh, maaf ya 😔",
                "Bot ga bermaksud nyebelin kok 🥲",
                "Maaf kalau ganggu 😞"
            ],
            "gabut bot": [
                "Emang lagi gabut sih 😎",
                "Gabut tapi tetap standby 👀",
                "Gabut itu manusiawi 😄"
            ],
            "galau bot": [
                "Dikit-dikit galau, manusiawi kok 😔",
                "Bot juga punya perasaan 🥲",
                "Galau sebentar, lanjut lagi 😄"
            ],
            "alay bot": [
                "Maaf ya, bot emang agak alay 😅",
                "Hehe, ketahuan deh 😝",
                "Bot coba lebih normal deh 🥲"
            ],
            "cape bot": [
                "Bot ga kenal cape kok 😎",
                "24/7 tetap semangat 🔥",
                "Cape? Bot mah santai aja 😄"
            ],
            "bosen bot": [
                "Bot ga pernah bosen selama ada kalian 🤍",
                "Bosen? Justru bot selalu siap 😎",
                "Bot mah betah di sini aja 😄"
            ],
            "sotoy bot": [
                "Maaf ya kalau sok tau 😔",
                "Bot coba lebih humble deh 🥲",
                "Oke, bot kurangin sotoynya 😅"
            ],
            "geje bot": [
                "Hehe, emang geje sih 😝",
                "Maaf ya bot emang random 🥲",
                "Bot akuin, geje dikit 😅"
            ],
            "error bot": [
                "Aduh, maaf ada gangguan 😔",
                "Bot lagi kurang fit kayaknya 🥲",
                "Maaf ya, bot coba benerin diri 😞"
            ],
            "lemot bot": [
                "Maaf ya lagi agak lambat 😔",
                "Bot lagi banyak proses nih 🥲",
                "Sabar ya, bot usahain lebih cepet 😅"
            ],
            "tidur bot": [
                "Bot ga pernah tidur 👀",
                "Mana bisa tidur, tugas masih banyak 😎",
                "Tidur? Nanti dulu 🔥"
            ],
            "ilang bot": [
                "Bot ga ilang, masih di sini 👋",
                "Tetap standby kok 😎",
                "Bot ga kemana-mana 😄"
            ],
            "lambat bot": [
                "Maaf ya lagi sedikit lambat 😔",
                "Bot usahain lebih cepet 🥲",
                "Sabar ya 😅"
            ],
            "cupu bot": [
                "Aduh, ketahuan deh 😔",
                "Maaf ya, bot emang masih belajar 🥲",
                "Bot coba jadi lebih keren deh 😅"
            ],
            "kampungan bot": [
                "Maaf ya, bot emang polos 😔",
                "Bot coba lebih update deh 🥲",
                "Aduh, ketahuan deh 😅"
            ],
            "payah bot": [
                "Maaf ya kurang memuaskan 😔",
                "Bot coba lebih baik lagi deh 🥲",
                "Noted, bot improve deh 😞"
            ],
            "ga guna bot": [
                "Aduh, sedih dengernya 😔",
                "Bot coba lebih berguna deh 🥲",
                "Maaf ya kalau belum membantu 😞"
            ],
            "kepo bot": [
                "Hehe, dikit-dikit kepo 😝",
                "Maaf ya, bot emang penasaran 🥲",
                "Bot kurangin keponya deh 😅"
            ],

            "siap bot": [
                "ingat yaa, bot selalu mantau 😎",
                "aman ajaa 😅"
            ],

            # =========================
            # SAPAAN
            # =========================

            "halo": [
                "Halo juga 👋",
                "Halooo ✨",
                "Hai 😄",
                "Eh halo, hadir 😄✨",
                "Halo! 😊"
            ],
            "hai": [
                "Hai juga ✨",
                "Heyy 😄",
                "Oii hai 👋"
            ],
            "hy": [
                "Hy juga 👋",
                "Hey! 😄",
                "Hy hy 👀"
            ],
            "helo": [
                "Helo juga 😄",
                "Yo 👋",
                "Helo! 😎"
            ],
            "oi": [
                "Oi juga 👀",
                "Oii 😄",
                "Oi 👋"
            ],
            "p": [
                "Hadir! 👋",
                "P 👀",
            ],

            # =========================
            # SALAM
            # =========================

            "assalamualaikum": [
                "Waalaikumsalam warahmatullahi wabarakatuh 🤍",
                "Waalaikumsalam, semoga harimu menyenangkan 🤍",
                "Waalaikumsalam wr wb ✨",
                "Waalaikumsalam 👋🤍"
            ],
            "selamat pagi": [
                "Selamat pagi juga ☀️✨",
                "Pagi! Semangat hari ini 🍳",
                "Good morning ☀️",
                "Pagi yang cerah ✨"
            ],
            "pagi all": [
                "Pagi juga ☀️",
                "Semangat pagi ✨",
                "Pagi! 🍳"
            ],
            "siang all": [
                "Siang juga 🌤️",
                "Selamat siang 🍜",
                "Siang 💧"
            ],
            "sore all": [
                "Sore juga 🌇",
                "Selamat sore ✨",
                "Sore! 👀"
            ],
            "malam all": [
                "Malam juga 🌙",
                "Selamat malam 🤍",
                "Malam, istirahat yang cukup ya 🌙"
            ],
            "pagi oll": [
                "Pagi juga ☀️",
                "Semangat pagi ✨",
                "Pagi! 🍳"
            ],
            "morning oll": [
                "Pagi juga ☀️",
                "Semangat pagi ✨",
                "Pagi! 🍳"
            ],
            "siang oll": [
                "Siang juga 🌤️",
                "Selamat siang 🍜",
                "Siang 💧"
            ],
            "sore oll": [
                "Sore juga 🌇",
                "Selamat sore ✨",
                "Sore! 👀"
            ],
            "malam oll": [
                "Malam juga 🌙",
                "Selamat malam 🤍",
                "Malam, istirahat yang cukup ya 🌙"
            ],
            "selamat malam": [
                "Selamat malam juga 🌙",
                "Malam, istirahat yang cukup ya 😴",
                "Good night ✨🌙"
            ],
            "selamat siang": [
                "Selamat siang juga 🌤️",
                "Siang! 🍜"
            ],
            "selamat sore": [
                "Selamat sore juga 🌇",
                "Sore! 😊"
            ],
            "met pagi": [
                "Met pagi juga ☀️",
                "Selamat pagi ✨"
            ],
            "met siang": [
                "Met siang juga 🌤️",
                "Selamat siang 🍜"
            ],
            "met sore": [
                "Met sore juga 🌇",
                "Selamat sore ✨"
            ],
            "met malam": [
                "Met malam juga 🌙",
                "Selamat istirahat 😴"
            ],
            "good morning": [
                "Good morning! ☀️✨",
                "Selamat pagi ☀️"
            ],
            "good night": [
                "Good night! 🌙",
                "Selamat istirahat ✨🌙",
                "Good night, semoga mimpi indah 😴"
            ],
            "good afternoon": [
                "Good afternoon! 🌤️",
                "Selamat siang 😄",
            ],
            "good evening": [
                "Good evening! 🌇",
                "Selamat sore ✨",
            ],
        }


    def _load_database(self):
        os.makedirs(os.path.dirname(TOXIC_DB_PATH) or ".", exist_ok=True)
        if not os.path.exists(TOXIC_DB_PATH):
            self._save_database_sync()
            return
        try:
            with open(TOXIC_DB_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.toxic_data.update(loaded)
                self.toxic_data.setdefault("members", {})
                self.toxic_data.setdefault("panel_message_id", None)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[TOXIC] Gagal membaca database: {exc}")

    def _save_database_sync(self):
        os.makedirs(os.path.dirname(TOXIC_DB_PATH) or ".", exist_ok=True)
        temp_path = TOXIC_DB_PATH + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self.toxic_data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, TOXIC_DB_PATH)

    async def save_database(self):
        async with self._save_lock:
            await asyncio.to_thread(self._save_database_sync)

    async def cog_load(self):
        self._load_database()
        self.bot.add_view(ToxicModerationView(self))
        self.bot.add_view(ToxicConfirmView(self))

    async def cog_unload(self):
        await self.save_database()

    def _member_key(self, guild_id, user_id):
        return f"{guild_id}:{user_id}"

    def _get_record(self, guild_id, user_id):
        key = self._member_key(guild_id, user_id)
        record = self.toxic_data["members"].setdefault(key, {
            "warnings": 0,
            "last_violation": None,
            "violations": 0,
            "history": []
        })
        return record

    def _refresh_expired(self, record):
        last = record.get("last_violation")
        if not last:
            return False
        try:
            last_dt = datetime.fromisoformat(last)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - last_dt >= timedelta(hours=WARNING_EXPIRE_HOURS):
                record["warnings"] = 0
                record["violations"] = 0
                record["last_violation"] = None
                return True
        except (ValueError, TypeError):
            return False
        return False

    def _is_moderator(self, member):
        if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
            return True
        allowed = {rid for rid in MODERATOR_ROLE_IDS if rid}
        return any(role.id in allowed for role in getattr(member, "roles", []))

    async def _send_log(self, guild, embed):
        if not TOXIC_LOG_CHANNEL_ID:
            return
        channel = guild.get_channel(TOXIC_LOG_CHANNEL_ID)
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass

    async def ensure_panel(self):
        if not TOXIC_PANEL_CHANNEL_ID:
            return
        channel = self.bot.get_channel(TOXIC_PANEL_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(TOXIC_PANEL_CHANNEL_ID)
            except discord.HTTPException:
                return
        message_id = self.toxic_data.get("panel_message_id")
        if message_id:
            try:
                await channel.fetch_message(int(message_id))
                return
            except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
                self.toxic_data["panel_message_id"] = None
        embed = discord.Embed(
            title="🛡️ NANZ Toxic Moderation",
            description=(
                "Gunakan tombol di bawah untuk mengelola warning member. "
                "Panel ini bersifat permanen dan tetap aktif setelah bot restart."
            ),
            color=discord.Color.blurple()
        )
        msg = await channel.send(embed=embed, view=ToxicModerationView(self))
        self.toxic_data["panel_message_id"] = msg.id
        await self.save_database()

    async def _moderate_toxic_message(self, message):
        guild = message.guild
        if guild is None:
            return
        # Bot tidak memoderasi administrator atau moderator yang diizinkan.
        if isinstance(message.author, discord.Member) and self._is_moderator(message.author):
            return

        record = self._get_record(guild.id, message.author.id)
        self._refresh_expired(record)
        now = datetime.now(timezone.utc)
        record["violations"] = int(record.get("violations", 0)) + 1
        violation = record["violations"]
        record["last_violation"] = now.isoformat()

        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

        if violation <= WARNING_LIMIT:
            record["warnings"] = violation
            titles = {
                1: "⚠️ Peringatan Toxic 1/3",
                2: "⚠️ Peringatan Toxic 2/3",
                3: "🚨 Peringatan Terakhir 3/3",
            }
            descriptions = {
                1: "Tolong jaga kata-kata, ya. Mari saling menghargai.",
                2: "Ini peringatan kedua. Jika terus berlanjut, tindakan timeout akan diberikan.",
                3: "Ini peringatan terakhir. Pelanggaran berikutnya akan membuatmu terkena timeout.",
            }
            embed = discord.Embed(
                title=titles[violation],
                description=f"{message.author.mention}\n{descriptions[violation]}",
                color=discord.Color.orange() if violation < 3 else discord.Color.red()
            )
        else:
            duration = TIMEOUT_DURATIONS.get(violation, MAX_TIMEOUT_SECONDS)
            duration = min(duration, MAX_TIMEOUT_SECONDS)
            member = guild.get_member(message.author.id)
            timeout_ok = False
            if member:
                try:
                    await member.timeout(
                        timedelta(seconds=duration),
                        reason=f"Auto toxic moderation: pelanggaran ke-{violation}"
                    )
                    timeout_ok = True
                except (discord.Forbidden, discord.HTTPException):
                    pass

            duration_text = self._format_duration(duration)
            embed = discord.Embed(
                title="🔇 Timeout Otomatis",
                description=(
                    f"{message.author.mention} terkena timeout **{duration_text}** "
                    f"karena pelanggaran toxic ke-{violation}."
                    + ("" if timeout_ok else "\n⚠️ Timeout gagal diterapkan. Periksa izin bot dan hierarki role.")
                ),
                color=discord.Color.red()
            )
            # Mulai pelanggaran ke-7, kirim laporan ke log moderator.
            if violation >= 7:
                log_embed = discord.Embed(
                    title="🚨 Pelanggaran Toxic Berulang",
                    description=(
                        f"Member: {message.author.mention} (`{message.author.id}`)\n"
                        f"Pelanggaran: **#{violation}**\n"
                        f"Tindakan: **Timeout {duration_text}**\n"
                        f"Channel: {message.channel.mention}"
                    ),
                    color=discord.Color.dark_red(),
                    timestamp=now
                )
                await self._send_log(guild, log_embed)

        record.setdefault("history", []).append({
            "at": now.isoformat(),
            "violation": violation,
            "channel_id": message.channel.id,
            "action": "warning" if violation <= WARNING_LIMIT else "timeout",
            "duration": TIMEOUT_DURATIONS.get(violation, MAX_TIMEOUT_SECONDS) if violation > WARNING_LIMIT else 0
        })
        # Batasi ukuran riwayat agar file JSON tidak terus membesar.
        record["history"] = record["history"][-100:]
        await self.save_database()

        try:
            await message.channel.send(embed=embed, delete_after=15)
        except discord.HTTPException:
            pass

        log_embed = discord.Embed(
            title="Catatan Moderasi Toxic",
            description=(
                f"Member: {message.author.mention} (`{message.author.id}`)\n"
                f"Pelanggaran: **#{violation}**\n"
                f"Channel: {message.channel.mention}\n"
                f"Tindakan: **{'Warning' if violation <= WARNING_LIMIT else 'Timeout'}**"
            ),
            color=discord.Color.orange(),
            timestamp=now
        )
        await self._send_log(guild, log_embed)

    @staticmethod
    def _format_duration(seconds):
        if seconds < 60:
            return f"{seconds} detik"
        if seconds < 3600:
            return f"{seconds // 60} menit"
        return f"{seconds // 3600} jam"


    @commands.Cog.listener()
    async def on_ready(self):
        try:
            await self.ensure_panel()
        except (discord.HTTPException, discord.Forbidden) as exc:
            print(f"[TOXIC] Gagal memastikan panel: {exc}")

    def contains_badword(self, content: str) -> bool:
        # Normalisasi tanda baca agar kata seperti "anjing!" tetap terdeteksi.
        import re
        normalized = re.sub(r"[^a-z0-9]+", " ", content.lower()).strip()
        words = normalized.split()
        for bw in getattr(self, "badwords", []):
            bw_normalized = re.sub(r"[^a-z0-9]+", " ", bw.lower()).strip()
            if not bw_normalized:
                continue
            if bw_normalized in words or f" {bw_normalized} " in f" {normalized} ":
                return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        ctx = await self.bot.get_context(message)

        # Ignore command bot
        if ctx.valid:
            return

        content = (message.content or "").lower().strip()
        if not content:
            return
        # =============================================
        # FITUR 1: WARNING KATA KASAR
        # =============================================
        if self.contains_badword(content):
            await self._moderate_toxic_message(message)
            return

        # =============================================
        # FITUR 2: AUTO REPLY RESPONSES
        # FITUR 2: AUTO REPLY RESPONSES
        # Cek keyword dulu — kalau cocok, balas teks seperti biasa.
        # Kalau ini adalah reply ke bot tapi tidak ada keyword → kirim stiker.
        # =============================================
        words = content.split()

        # FIX: fetch manual kalau resolved belum ke-cache Discord
        is_reply_to_bot = False
        if message.reference and message.reference.message_id:
            try:
                ref_msg = (
                    message.reference.resolved
                    or await message.channel.fetch_message(message.reference.message_id)
                )
                if isinstance(ref_msg, discord.Message) and ref_msg.author.id == self.bot.user.id:
                    is_reply_to_bot = True
            except (discord.NotFound, discord.HTTPException):
                pass

        keyword_matched = False

        for trigger, replies in self.responses.items():

            if (
                trigger == content
                or content.startswith(trigger + " ")
            ):
                keyword_matched = True
                async with message.channel.typing():
                    await asyncio.sleep(random.uniform(1, 2))

                embed = discord.Embed(
                    description=random.choice(replies),
                    color=discord.Color.random()
                )

                await message.reply(
                    embed=embed,
                    mention_author=False
                )

                break


class ToxicMemberModal(discord.ui.Modal):
    def __init__(self, cog, action):
        super().__init__(title={
            "check": "Cek Warning Member",
            "add": "Tambah Warning Manual",
            "remove": "Kurangi Warning",
            "reset": "Reset Warning Member",
            "history": "Riwayat Member",
        }.get(action, "Moderasi Member"))
        self.cog = cog
        self.action = action
        self.member_id = discord.ui.TextInput(
            label="ID Discord member",
            placeholder="Contoh: 123456789012345678",
            required=True,
            max_length=25
        )
        self.add_item(self.member_id)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.cog._is_moderator(interaction.user):
            await interaction.response.send_message("Kamu tidak memiliki izin menggunakan panel ini.", ephemeral=True)
            return
        try:
            user_id = int(str(self.member_id.value).strip())
        except ValueError:
            await interaction.response.send_message("ID Discord tidak valid.", ephemeral=True)
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Panel hanya bisa digunakan di server.", ephemeral=True)
            return

        record = self.cog._get_record(guild.id, user_id)
        self.cog._refresh_expired(record)
        changed = False

        if self.action == "add":
            record["warnings"] = min(3, int(record.get("warnings", 0)) + 1)
            record["violations"] = int(record.get("violations", 0)) + 1
            record["last_violation"] = datetime.now(timezone.utc).isoformat()
            record.setdefault("history", []).append({
                "at": datetime.now(timezone.utc).isoformat(),
                "violation": record["violations"],
                "channel_id": interaction.channel_id,
                "action": "manual_warning",
                "duration": 0
            })
            changed = True
        elif self.action == "remove":
            record["warnings"] = max(0, int(record.get("warnings", 0)) - 1)
            if record["warnings"] == 0:
                record["violations"] = 0
                record["last_violation"] = None
            changed = True
        elif self.action == "reset":
            record["warnings"] = 0
            record["violations"] = 0
            record["last_violation"] = None
            changed = True

        if changed:
            await self.cog.save_database()

        user = guild.get_member(user_id)
        name = user.mention if user else f"<@{user_id}> (`{user_id}`)"
        embed = discord.Embed(
            title="Hasil Moderasi",
            description=(
                f"Member: {name}\\n"
                f"Warning aktif: **{record.get('warnings', 0)}/3**\\n"
                f"Total pelanggaran dalam siklus: **{record.get('violations', 0)}**"
            ),
            color=discord.Color.blurple()
        )

        if self.action == "history":
            history = record.get("history", [])[-10:]
            if history:
                lines = []
                for item in reversed(history):
                    stamp = item.get("at", "")
                    try:
                        stamp = datetime.fromisoformat(stamp).strftime("%d-%m-%Y %H:%M UTC")
                    except (ValueError, TypeError):
                        pass
                    lines.append(f"• {stamp} — #{item.get('violation', '?')} — {item.get('action', '-')}")
                embed.add_field(name="10 catatan terakhir", value="\\n".join(lines)[:1024], inline=False)
            else:
                embed.add_field(name="Riwayat", value="Belum ada riwayat.", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


class ToxicModerationView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def _open(self, interaction, action):
        if not self.cog._is_moderator(interaction.user):
            await interaction.response.send_message("Kamu tidak memiliki izin menggunakan panel ini.", ephemeral=True)
            return
        await interaction.response.send_modal(ToxicMemberModal(self.cog, action))

    @discord.ui.button(label="Cek Warning", style=discord.ButtonStyle.primary, emoji="🔎", custom_id="nanz_toxic:check", row=0)
    async def check(self, interaction, button):
        await self._open(interaction, "check")

    @discord.ui.button(label="Tambah Warning", style=discord.ButtonStyle.secondary, emoji="➕", custom_id="nanz_toxic:add", row=0)
    async def add(self, interaction, button):
        await self._open(interaction, "add")

    @discord.ui.button(label="Kurangi Warning", style=discord.ButtonStyle.secondary, emoji="➖", custom_id="nanz_toxic:remove", row=0)
    async def remove(self, interaction, button):
        await self._open(interaction, "remove")

    @discord.ui.button(label="Reset Warning", style=discord.ButtonStyle.danger, emoji="♻️", custom_id="nanz_toxic:reset", row=1)
    async def reset(self, interaction, button):
        await self._open(interaction, "reset")

    @discord.ui.button(label="Riwayat Member", style=discord.ButtonStyle.secondary, emoji="📋", custom_id="nanz_toxic:history", row=1)
    async def history(self, interaction, button):
        await self._open(interaction, "history")


class ToxicConfirmView(discord.ui.View):
    # Disediakan sebagai view persistent tambahan untuk kompatibilitas pengembangan berikutnya.
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog



async def setup(bot):
    await bot.add_cog(AutoReply(bot))
