import re
import asyncio
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from database import db


# ============================================================
# CONFIG
# ============================================================

# CHANNEL PANEL MEMBER
APIPI_PANEL_CHANNEL_ID = 1555862444054814740

# CHANNEL LOG APIPI
APIPI_LOG_CHANNEL_ID = 1555862510765215765

# ROLE APIPI
APIPI_ROLE_ID = 1555862680605167646

# ROLE SISWA / SISWI
SISWA_ROLE_ID = 1453246082405503036
SISWI_ROLE_ID = 1453246187636396032

# CHANNEL PANEL MANAGEMENT
APIPI_MANAGEMENT_PANEL_ID = 1555863036810494084


# ============================================================
# RULE
# ============================================================

# Waktu unlock sebelum bisa mengambil role
UNLOCK_HOURS = 20

# Kewajiban setelah mendapatkan role
WEEKLY_HOURS = 5

# Maksimal strike
MAX_STRIKE = 3

# Heartbeat tracking
HEARTBEAT_SECONDS = 30


# ============================================================
# TIMEZONE
# ============================================================

UTC = timezone.utc
WIB = timezone(timedelta(hours=7))


# ============================================================
# CUSTOM EMOJI
# ============================================================

EMOJI_ARROW_BLUE = discord.PartialEmoji(
    name="arrow_blue",
    id=1512787254312042496,
    animated=True
)

EMOJI_ARROW_PURPLE = discord.PartialEmoji(
    name="arrow_purple",
    id=1512787191234035803,
    animated=True
)

EMOJI_APIPI = discord.PartialEmoji(
    name="apipi",
    id=1512888691369050243,
    animated=True
)

EMOJI_LOVE = discord.PartialEmoji(
    name="rainbow_love",
    id=1493106010389483661,
    animated=True
)

EMOJI_WAITING = discord.PartialEmoji(
    name="waiting",
    id=1544744564336758905,
    animated=True
)


# ============================================================
# HELPERS
# ============================================================

def utc_now():
    """
    Waktu sekarang dalam UTC.
    """
    return datetime.now(UTC)


def db_datetime(dt):
    """
    Convert aware datetime -> naive UTC
    untuk MariaDB DATETIME.
    """
    return dt.astimezone(UTC).replace(tzinfo=None)


def from_db_datetime(value):
    """
    Convert MariaDB DATETIME -> aware UTC.
    """
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def get_week_start(dt):
    """
    Mengambil Senin 00:00 WIB sebagai awal minggu.
    """
    local = dt.astimezone(WIB)

    monday = local - timedelta(days=local.weekday())

    monday = monday.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    return monday


def get_week_start_date(dt):
    return get_week_start(dt).date()


def get_next_week_start(dt):
    return get_week_start(dt) + timedelta(days=7)


def parse_user_id(value):
    """
    Mendukung:
    123456789
    <@123456789>
    <@!123456789>
    """

    if not value:
        return None

    value = str(value).strip()

    match = re.search(r"\d{15,25}", value)

    if not match:
        return None

    try:
        return int(match.group())
    except (TypeError, ValueError):
        return None


def safe_int(value):
    """
    Memastikan value menjadi integer.
    """

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def format_hours(seconds):
    """
    Contoh:
    7200 -> 2.00 jam
    """

    seconds = int(seconds or 0)

    hours = seconds / 3600

    return f"{hours:.2f} jam"


def format_duration(seconds):
    """
    Contoh:
    7260 -> 2 jam 1 menit
    """

    seconds = int(seconds or 0)

    if seconds <= 0:
        return "0 menit"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if hours > 0:
        return f"{hours} jam {minutes} menit"

    return f"{minutes} menit"


# ============================================================
# DATABASE
# ============================================================

async def create_tables():
    """
    Membuat database/tabel jika belum ada.
    """

    await db.execute("""
        CREATE TABLE IF NOT EXISTS nanz_apipi_pairs (
            id BIGINT NOT NULL AUTO_INCREMENT,
            guild_id BIGINT NOT NULL,

            siswa_id BIGINT NOT NULL,
            siswi_id BIGINT NOT NULL,

            status VARCHAR(20) NOT NULL DEFAULT 'tracking',

            take_siswa TINYINT(1) NOT NULL DEFAULT 0,
            take_siswi TINYINT(1) NOT NULL DEFAULT 0,

            remove_siswa TINYINT(1) NOT NULL DEFAULT 0,
            remove_siswi TINYINT(1) NOT NULL DEFAULT 0,

            eligible_notified TINYINT(1) NOT NULL DEFAULT 0,

            strike INT NOT NULL DEFAULT 0,

            active_since DATETIME NULL,

            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,

            PRIMARY KEY (id),

            INDEX idx_apipi_guild (guild_id),
            INDEX idx_apipi_siswa (siswa_id),
            INDEX idx_apipi_siswi (siswi_id),
            INDEX idx_apipi_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS nanz_apipi_sessions (
            id BIGINT NOT NULL AUTO_INCREMENT,

            pair_id BIGINT NOT NULL,

            started_at DATETIME NOT NULL,
            ended_at DATETIME NOT NULL,

            duration_seconds BIGINT NOT NULL DEFAULT 0,

            week_start DATE NOT NULL,

            created_at DATETIME NOT NULL,

            PRIMARY KEY (id),

            INDEX idx_apipi_session_pair (pair_id),
            INDEX idx_apipi_session_week (pair_id, week_start),

            CONSTRAINT fk_apipi_session_pair
                FOREIGN KEY (pair_id)
                REFERENCES nanz_apipi_pairs(id)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS nanz_apipi_live_sessions (
            pair_id BIGINT NOT NULL,

            channel_id BIGINT NOT NULL,

            started_at DATETIME NOT NULL,
            last_seen_at DATETIME NOT NULL,

            PRIMARY KEY (pair_id),

            CONSTRAINT fk_apipi_live_pair
                FOREIGN KEY (pair_id)
                REFERENCES nanz_apipi_pairs(id)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS nanz_apipi_weekly (
            id BIGINT NOT NULL AUTO_INCREMENT,

            pair_id BIGINT NOT NULL,

            week_start DATE NOT NULL,

            seconds BIGINT NOT NULL DEFAULT 0,

            target_seconds BIGINT NOT NULL,

            met TINYINT(1) NOT NULL DEFAULT 0,

            strike_after INT NOT NULL DEFAULT 0,

            checked_at DATETIME NOT NULL,

            PRIMARY KEY (id),

            UNIQUE KEY unique_apipi_week (
                pair_id,
                week_start
            ),

            INDEX idx_apipi_week_pair (pair_id),

            CONSTRAINT fk_apipi_week_pair
                FOREIGN KEY (pair_id)
                REFERENCES nanz_apipi_pairs(id)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS nanz_apipi_logs (
            id BIGINT NOT NULL AUTO_INCREMENT,

            pair_id BIGINT NULL,

            actor_id BIGINT NULL,

            action VARCHAR(50) NOT NULL,

            details TEXT NULL,

            created_at DATETIME NOT NULL,

            PRIMARY KEY (id),

            INDEX idx_apipi_log_pair (pair_id),
            INDEX idx_apipi_log_actor (actor_id),
            INDEX idx_apipi_log_action (action)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)


# ============================================================
# COG
# ============================================================

class Apipi(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.session_lock = asyncio.Lock()

        self.initialized = False

        self.heartbeat.start()
        self.weekly_checker.start()

    # ========================================================
    # COG LOAD
    # ========================================================

    async def cog_load(self):

        await create_tables()

        self.initialized = True

        self.bot.add_view(
            ApipiMemberPanel(self)
        )

        self.bot.add_view(
            ApipiManagementPanel(self)
        )

        self.bot.loop.create_task(
            self.initialize_panels()
        )

        self.bot.loop.create_task(
            self.reconcile_after_restart()
        )

    # ========================================================
    # COG UNLOAD
    # ========================================================

    def cog_unload(self):

        self.heartbeat.cancel()

        self.weekly_checker.cancel()

    # ========================================================
    # PANEL INITIALIZATION
    # ========================================================

    async def initialize_panels(self):

        await self.bot.wait_until_ready()

        try:
            await self.ensure_member_panel()

        except Exception as e:
            print(
                f"[APIPI] Gagal memastikan member panel: {e}"
            )

        try:
            await self.ensure_management_panel()

        except Exception as e:
            print(
                f"[APIPI] Gagal memastikan management panel: {e}"
            )

    # ========================================================
    # ENSURE MEMBER PANEL
    # ========================================================

    async def ensure_member_panel(self):

        channel = self.bot.get_channel(
            APIPI_PANEL_CHANNEL_ID
        )

        if not channel:
            return

        try:

            async for message in channel.history(
                limit=50
            ):

                if not self.bot.user:
                    continue

                if message.author.id != self.bot.user.id:
                    continue

                if not message.embeds:
                    continue

                if message.embeds[0].title == "APIPI — PANEL":

                    try:

                        await message.edit(
                            embed=self.member_panel_embed(),
                            view=ApipiMemberPanel(self)
                        )

                    except Exception as e:

                        print(
                            f"[APIPI] Gagal update member panel: {e}"
                        )

                    return

        except Exception as e:

            print(
                f"[APIPI] Gagal membaca member panel: {e}"
            )

        try:

            await channel.send(
                embed=self.member_panel_embed(),
                view=ApipiMemberPanel(self)
            )

        except Exception as e:

            print(
                f"[APIPI] Gagal membuat member panel: {e}"
            )

    # ========================================================
    # ENSURE MANAGEMENT PANEL
    # ========================================================

    async def ensure_management_panel(self):

        channel = self.bot.get_channel(
            APIPI_MANAGEMENT_PANEL_ID
        )

        if not channel:
            return

        try:

            async for message in channel.history(
                limit=50
            ):

                if not self.bot.user:
                    continue

                if message.author.id != self.bot.user.id:
                    continue

                if not message.embeds:
                    continue

                if (
                    message.embeds[0].title
                    == "APIPI — MANAGEMENT"
                ):

                    try:

                        await message.edit(
                            embed=await self.management_panel_embed(),
                            view=ApipiManagementPanel(self)
                        )

                    except Exception as e:

                        print(
                            f"[APIPI] Gagal update management panel: {e}"
                        )

                    return

        except Exception as e:

            print(
                f"[APIPI] Gagal membaca management panel: {e}"
            )

        try:

            await channel.send(
                embed=await self.management_panel_embed(),
                view=ApipiManagementPanel(self)
            )

        except Exception as e:

            print(
                f"[APIPI] Gagal membuat management panel: {e}"
            )

    # ========================================================
    # MEMBER PANEL EMBED
    # ========================================================

    def member_panel_embed(self):

        embed = discord.Embed(
            title="APIPI — PANEL",
            description=(
                f"{EMOJI_APIPI} **Apipi** adalah pasangan "
                "Siswa + Siswi yang memenuhi persyaratan "
                "voice bersama.\n\n"

                f"{EMOJI_ARROW_PURPLE} **Cara mendapatkan role**\n"
                "1. Daftarkan pasangan.\n"
                "2. Keduanya berada di voice channel yang sama.\n"
                f"3. Kumpulkan **{UNLOCK_HOURS} jam** shared voice.\n"
                "4. Setelah 20 jam tercapai, keduanya mendapat "
                "notifikasi.\n"
                "5. Role hanya diberikan jika **keduanya menyetujui**.\n\n"

                f"{EMOJI_ARROW_BLUE} **Setelah mendapatkan role**\n"
                f"• Minimal **{WEEKLY_HOURS} jam / minggu**.\n"
                "• AFK tetap dihitung selama tetap berada di VC yang sama.\n"
                f"• Maksimal **{MAX_STRIKE} strike**.\n"
                "• Strike bersifat kumulatif.\n"
                "• Strike ke-3 menyebabkan role dicabut otomatis.\n\n"

                f"{EMOJI_LOVE} Gunakan tombol di bawah untuk "
                "mengatur status Apipi.\n\n"
                "Jika salah memilih pasangan dan role belum aktif, "
                "gunakan **Reset Pasangan** untuk memilih ulang."
            ),
            color=discord.Color.blurple()
        )

        return embed

    # ========================================================
    # MANAGEMENT PANEL EMBED
    # ========================================================

    async def management_panel_embed(self):

        pairs = []
        management_channel = self.bot.get_channel(APIPI_MANAGEMENT_PANEL_ID)
        guild_id = management_channel.guild.id if management_channel else None

        try:
            if guild_id:
                pairs = await db.fetchall(
                    f"""
                    SELECT *
                    FROM nanz_apipi_pairs
                    WHERE guild_id = {int(guild_id)}
                    AND status != 'removed'
                    ORDER BY id DESC
                    LIMIT 20
                    """
                )
        except Exception as e:
            print(f"[APIPI] Gagal mengambil daftar management: {e}")

        lines = []

        for pair in pairs:
            siswa = self.find_member(pair["siswa_id"])
            siswi = self.find_member(pair["siswi_id"])

            siswa_name = siswa.display_name if siswa else str(pair["siswa_id"])
            siswi_name = siswi.display_name if siswi else str(pair["siswi_id"])

            status_map = {
                "tracking": "Tracking",
                "eligible": "Siap Diambil",
                "active": "Aktif",
                "removed": "Dihapus"
            }

            lines.append(
                f"`#{pair['id']}` **{siswa_name}** × **{siswi_name}** — "
                f"{status_map.get(pair['status'], pair['status'])} — "
                f"Strike {pair['strike']}/{MAX_STRIKE}"
            )

        rundown = "\n".join(lines) if lines else "Belum ada pasangan Apipi terdaftar."

        embed = discord.Embed(
            title="APIPI — MANAGEMENT",
            description=(
                f"{EMOJI_APIPI} Panel khusus **Administrator**.\n\n"
                f"{EMOJI_ARROW_PURPLE} **Rundown Pasangan**\n"
                f"{rundown}\n\n"
                f"{EMOJI_ARROW_PURPLE} **Management**\n"
                "• Cek Status — pilih member tanpa ID.\n"
                "• Set Role — pilih member tanpa ID.\n"
                "• Cabut Role — pilih member tanpa ID.\n"
                "• Reset Progress — pilih member tanpa ID.\n"
                "• Reset Strike — pilih member tanpa ID.\n"
                "• Daftar Pasangan — lihat pasangan dan cari member.\n"
                "• Reset Pasangan — hapus pasangan yang belum aktif agar bisa memilih ulang.\n\n"
                f"{EMOJI_WAITING} Semua tindakan management akan dicatat ke log.\n"
                "Rundown di atas otomatis diperbarui setelah perubahan data."
            ),
            color=discord.Color.dark_purple()
        )

        return embed

    async def refresh_apipi_panels(self):
        """Refresh panel Apipi tanpa mengirim panel baru."""

        member_channel = self.bot.get_channel(APIPI_PANEL_CHANNEL_ID)
        management_channel = self.bot.get_channel(APIPI_MANAGEMENT_PANEL_ID)

        if member_channel:
            try:
                async for message in member_channel.history(limit=50):
                    if (
                        self.bot.user
                        and message.author.id == self.bot.user.id
                        and message.embeds
                        and message.embeds[0].title == "APIPI — PANEL"
                    ):
                        await message.edit(
                            embed=self.member_panel_embed(),
                            view=ApipiMemberPanel(self)
                        )
                        break
            except Exception as e:
                print(f"[APIPI] Refresh member panel error: {e}")

        if management_channel:
            try:
                async for message in management_channel.history(limit=50):
                    if (
                        self.bot.user
                        and message.author.id == self.bot.user.id
                        and message.embeds
                        and message.embeds[0].title == "APIPI — MANAGEMENT"
                    ):
                        await message.edit(
                            embed=await self.management_panel_embed(),
                            view=ApipiManagementPanel(self)
                        )
                        break
            except Exception as e:
                print(f"[APIPI] Refresh management panel error: {e}")

    # ========================================================
    # FIND MEMBER
    # ========================================================

    def find_member(self, user_id):

        user_id = safe_int(user_id)

        if user_id is None:
            return None

        for guild in self.bot.guilds:

            member = guild.get_member(user_id)

            if member:
                return member

        return None

    # ========================================================
    # GET PAIR BY MEMBER
    # ========================================================

    async def get_pair_by_member(
        self,
        guild_id,
        user_id,
        include_removed=False
    ):
        """
        Versi aman untuk wrapper database.py nanZ.

        Database wrapper menggunakan aiomysql dan melakukan
        Python-style % formatting pada query.

        Karena itu query di sini menggunakan integer yang
        sudah divalidasi dan dikirim tanpa args tambahan.
        """

        guild_id = safe_int(guild_id)
        user_id = safe_int(user_id)

        if guild_id is None or user_id is None:
            return None

        if include_removed:

            query = f"""
                SELECT *
                FROM nanz_apipi_pairs
                WHERE guild_id = {guild_id}
                AND (
                    siswa_id = {user_id}
                    OR siswi_id = {user_id}
                )
                ORDER BY id DESC
                LIMIT 1
            """

        else:

            query = f"""
                SELECT *
                FROM nanz_apipi_pairs
                WHERE guild_id = {guild_id}
                AND (
                    siswa_id = {user_id}
                    OR siswi_id = {user_id}
                )
                AND status != 'removed'
                ORDER BY id DESC
                LIMIT 1
            """

        return await db.fetchone(
            query
        )

    # ========================================================
    # GET PAIR BY ID
    # ========================================================

    async def get_pair(self, pair_id):

        pair_id = safe_int(pair_id)

        if pair_id is None:
            return None

        return await db.fetchone(
            """
            SELECT *
            FROM nanz_apipi_pairs
            WHERE id = %s
            LIMIT 1
            """,
            (pair_id,)
        )

    # ========================================================
    # FIND PAIR BY TWO MEMBERS
    # ========================================================

    async def get_exact_pair(
        self,
        guild_id,
        siswa_id,
        siswi_id
    ):

        guild_id = safe_int(guild_id)
        siswa_id = safe_int(siswa_id)
        siswi_id = safe_int(siswi_id)

        if (
            guild_id is None
            or siswa_id is None
            or siswi_id is None
        ):
            return None

        return await db.fetchone(
            """
            SELECT *
            FROM nanz_apipi_pairs
            WHERE guild_id = %s
            AND siswa_id = %s
            AND siswi_id = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                guild_id,
                siswa_id,
                siswi_id
            )
        )

    # ========================================================
    # RESET PAIR SELECTION
    # ========================================================

    async def reset_pair_selection(
        self,
        guild_id,
        user_id,
        actor_id
    ):

        pair = await self.get_pair_by_member(
            guild_id,
            user_id
        )

        if not pair:
            return False, "not_found"

        if pair["status"] == "active":
            return False, "already_active"

        # Jangan izinkan reset jika salah satu pihak sudah memiliki role Apipi.
        guild = self.bot.get_guild(int(guild_id))
        if guild:
            role = guild.get_role(APIPI_ROLE_ID)
            if role:
                siswa = guild.get_member(pair["siswa_id"])
                siswi = guild.get_member(pair["siswi_id"])
                if (siswa and role in siswa.roles) or (siswi and role in siswi.roles):
                    return False, "already_active"

        pair_id = safe_int(pair.get("id"))
        if pair_id is None:
            return False, "invalid_pair"

        now = db_datetime(utc_now())
        now_sql = now.strftime("%Y-%m-%d %H:%M:%S")

        # Wrapper database.py nanZ melakukan Python-style % formatting.
        # Karena itu reset pasangan memakai query tanpa placeholder %s.
        await db.execute(
            f"""
            DELETE FROM nanz_apipi_sessions
            WHERE pair_id = {pair_id}
            """
        )

        await db.execute(
            f"""
            DELETE FROM nanz_apipi_weekly
            WHERE pair_id = {pair_id}
            """
        )

        await db.execute(
            f"""
            UPDATE nanz_apipi_pairs
            SET
                status = 'removed',
                eligible_notified = 0,
                take_siswa = 0,
                take_siswi = 0,
                remove_siswa = 0,
                remove_siswi = 0,
                updated_at = '{now_sql}'
            WHERE id = {pair_id}
            """
        )

        await self.log(
            pair["id"],
            actor_id,
            "PAIR_RESET",
            "Pasangan Apipi di-reset sebelum role aktif."
        )

        await self.refresh_apipi_panels()
        return True, pair

    # ========================================================
    # CREATE PAIR
    # ========================================================

    async def create_pair(
        self,
        guild_id,
        siswa_id,
        siswi_id,
        actor_id
    ):

        existing_siswa = await self.get_pair_by_member(
            guild_id,
            siswa_id
        )

        if existing_siswa:
            return None, "siswa_busy"

        existing_siswi = await self.get_pair_by_member(
            guild_id,
            siswi_id
        )

        if existing_siswi:
            return None, "siswi_busy"

        now = db_datetime(
            utc_now()
        )

        # Gunakan nilai integer yang sudah divalidasi langsung pada query.
        # Ini menghindari konflik Python-style % formatting pada wrapper db.py nanZ.
        now_sql = now.strftime("%Y-%m-%d %H:%M:%S")

        await db.execute(
            f"""
            INSERT INTO nanz_apipi_pairs
            (
                guild_id,
                siswa_id,
                siswi_id,
                status,
                created_at,
                updated_at
            )
            VALUES
            (
                {guild_id},
                {siswa_id},
                {siswi_id},
                'tracking',
                '{now_sql}',
                '{now_sql}'
            )
            """
        )

        pair = await self.get_exact_pair(
            guild_id,
            siswa_id,
            siswi_id
        )

        if pair:

            await self.log(
                pair["id"],
                actor_id,
                "PAIR_REGISTER",
                (
                    f"Pair dibuat: "
                    f"Siswa={siswa_id}, "
                    f"Siswi={siswi_id}"
                )
            )

            # Penting: pasangan bisa saja sudah berada di VC yang sama
            # sebelum proses registrasi dilakukan. Discord tidak selalu
            # mengirim ulang voice-state event setelah pair dibuat, sehingga
            # sesi live harus langsung disinkronkan di sini.
            try:
                async with self.session_lock:
                    await self.sync_pair_voice(pair)
            except Exception as e:
                print(
                    f"[APIPI] Gagal initial voice sync pair={pair['id']}: {e}"
                )

        await self.refresh_apipi_panels()

        return pair, "success"

    # ========================================================
    # CHECK ROLES
    # ========================================================

    def validate_pair_roles(
        self,
        siswa,
        siswi
    ):

        if not siswa or not siswi:
            return False

        siswa_ok = any(
            role.id == SISWA_ROLE_ID
            for role in siswa.roles
        )

        siswi_ok = any(
            role.id == SISWI_ROLE_ID
            for role in siswi.roles
        )

        return siswa_ok and siswi_ok

    # ========================================================
    # GET PAIR MEMBERS
    # ========================================================

    def get_pair_members(self, pair):

        siswa = self.find_member(
            pair["siswa_id"]
        )

        siswi = self.find_member(
            pair["siswi_id"]
        )

        return siswa, siswi

    # ========================================================
    # SHARED VOICE CHECK
    # ========================================================

    def get_shared_channel(self, pair):

        siswa, siswi = self.get_pair_members(
            pair
        )

        if not siswa or not siswi:
            return None

        if not siswa.voice or not siswi.voice:
            return None

        if not siswa.voice.channel:
            return None

        if not siswi.voice.channel:
            return None

        if siswa.voice.channel.id != siswi.voice.channel.id:
            return None

        return siswa.voice.channel

    # ========================================================
    # START SESSION
    # ========================================================

    async def start_session(
        self,
        pair,
        channel_id
    ):

        existing = await db.fetchone(
            """
            SELECT *
            FROM nanz_apipi_live_sessions
            WHERE pair_id = %s
            LIMIT 1
            """,
            (pair["id"],)
        )

        if existing:

            if existing["channel_id"] == channel_id:
                return

            await self.close_session(
                pair["id"],
                utc_now()
            )

        now = db_datetime(
            utc_now()
        )

        await db.execute(
            """
            INSERT INTO nanz_apipi_live_sessions
            (
                pair_id,
                channel_id,
                started_at,
                last_seen_at
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                pair["id"],
                channel_id,
                now,
                now
            )
        )

    # ========================================================
    # CLOSE SESSION
    # ========================================================

    async def close_session(
        self,
        pair_id,
        end_time
    ):

        live = await db.fetchone(
            """
            SELECT *
            FROM nanz_apipi_live_sessions
            WHERE pair_id = %s
            LIMIT 1
            """,
            (pair_id,)
        )

        if not live:
            return

        start_time = from_db_datetime(
            live["started_at"]
        )

        if end_time <= start_time:

            await db.execute(
                """
                DELETE FROM nanz_apipi_live_sessions
                WHERE pair_id = %s
                """,
                (pair_id,)
            )

            return

        await self.save_split_sessions(
            pair_id,
            start_time,
            end_time
        )

        await db.execute(
            """
            DELETE FROM nanz_apipi_live_sessions
            WHERE pair_id = %s
            """,
            (pair_id,)
        )

    # ========================================================
    # SAVE SPLIT SESSIONS
    # ========================================================

    async def save_split_sessions(
        self,
        pair_id,
        start_time,
        end_time
    ):

        if not start_time or not end_time:
            return

        if end_time <= start_time:
            return

        cursor = start_time

        while cursor < end_time:

            current_week = get_week_start(
                cursor
            )

            next_boundary = current_week + timedelta(
                days=7
            )

            if next_boundary.tzinfo is None:

                next_boundary = next_boundary.replace(
                    tzinfo=WIB
                )

            next_boundary_utc = (
                next_boundary.astimezone(UTC)
            )

            segment_end = min(
                end_time,
                next_boundary_utc
            )

            duration = int(
                (
                    segment_end - cursor
                ).total_seconds()
            )

            if duration > 0:

                await db.execute(
                    """
                    INSERT INTO nanz_apipi_sessions
                    (
                        pair_id,
                        started_at,
                        ended_at,
                        duration_seconds,
                        week_start,
                        created_at
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        pair_id,
                        db_datetime(cursor),
                        db_datetime(segment_end),
                        duration,
                        current_week.date(),
                        db_datetime(utc_now())
                    )
                )

            cursor = segment_end

    # ========================================================
    # TOTAL PROGRESS
    # ========================================================

    async def get_total_seconds(
        self,
        pair_id
    ):

        result = await db.fetchone(
            """
            SELECT
                COALESCE(
                    SUM(duration_seconds),
                    0
                ) AS total_seconds
            FROM nanz_apipi_sessions
            WHERE pair_id = %s
            """,
            (pair_id,)
        )

        total = int(
            (result or {}).get(
                "total_seconds",
                0
            ) or 0
        )

        live = await db.fetchone(
            """
            SELECT *
            FROM nanz_apipi_live_sessions
            WHERE pair_id = %s
            LIMIT 1
            """,
            (pair_id,)
        )

        if live:

            start = from_db_datetime(
                live["started_at"]
            )

            total += max(
                0,
                int(
                    (
                        utc_now() - start
                    ).total_seconds()
                )
            )

        return total

    # ========================================================
    # WEEKLY PROGRESS
    # ========================================================

    async def get_week_seconds(
        self,
        pair_id,
        week_start_date
    ):

        result = await db.fetchone(
            """
            SELECT
                COALESCE(
                    SUM(duration_seconds),
                    0
                ) AS seconds
            FROM nanz_apipi_sessions
            WHERE pair_id = %s
            AND week_start = %s
            """,
            (
                pair_id,
                week_start_date
            )
        )

        total = int(
            (result or {}).get(
                "seconds",
                0
            ) or 0
        )

        live = await db.fetchone(
            """
            SELECT *
            FROM nanz_apipi_live_sessions
            WHERE pair_id = %s
            LIMIT 1
            """,
            (pair_id,)
        )

        if live:

            start = from_db_datetime(
                live["started_at"]
            )

            now = utc_now()

            week_start_local = datetime.combine(
                week_start_date,
                datetime.min.time()
            ).replace(
                tzinfo=WIB
            )

            week_start_utc = (
                week_start_local.astimezone(UTC)
            )

            week_end_utc = (
                week_start_local
                + timedelta(days=7)
            ).astimezone(UTC)

            overlap_start = max(
                start,
                week_start_utc
            )

            overlap_end = min(
                now,
                week_end_utc
            )

            if overlap_end > overlap_start:

                total += int(
                    (
                        overlap_end
                        - overlap_start
                    ).total_seconds()
                )

        return total

    # ========================================================
    # CHECK ELIGIBILITY
    # ========================================================

    async def check_eligibility(
        self,
        pair
    ):

        if pair["status"] not in (
            "tracking",
            "eligible"
        ):
            return

        total_seconds = await self.get_total_seconds(
            pair["id"]
        )

        target_seconds = UNLOCK_HOURS * 3600

        if total_seconds < target_seconds:
            return

        if pair["status"] == "tracking":

            now = db_datetime(
                utc_now()
            )

            await db.execute(
                """
                UPDATE nanz_apipi_pairs
                SET
                    status = 'eligible',
                    eligible_notified = 1,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    now,
                    pair["id"]
                )
            )

            await self.log(
                pair["id"],
                None,
                "ELIGIBLE",
                (
                    f"Progress mencapai "
                    f"{format_hours(total_seconds)}"
                )
            )

            await self.send_eligibility_notice(
                pair
            )

            await self.refresh_apipi_panels()

    # ========================================================
    # ELIGIBILITY NOTICE
    # ========================================================

    async def send_eligibility_notice(
        self,
        pair
    ):

        channel = self.bot.get_channel(
            APIPI_PANEL_CHANNEL_ID
        )

        if not channel:
            return

        siswa = self.find_member(
            pair["siswa_id"]
        )

        siswi = self.find_member(
            pair["siswi_id"]
        )

        if not siswa or not siswi:
            return

        await channel.send(
            (
                f"{EMOJI_APIPI} **APIPI SIAP DIAMBIL**\n\n"
                f"{siswa.mention} & {siswi.mention}\n\n"
                f"Kalian telah mencapai **{UNLOCK_HOURS} jam** "
                "shared voice.\n\n"
                "Jika ingin mengambil role Apipi, "
                "**keduanya wajib menekan tombol "
                "`Ambil Role`** pada panel.\n\n"
                f"{EMOJI_WAITING} Role tidak akan diberikan "
                "secara otomatis."
            )
        )

    # ========================================================
    # TAKE APPROVAL
    # ========================================================

    async def approve_take(
        self,
        interaction
    ):

        guild = interaction.guild

        if not guild:

            return await interaction.response.send_message(
                "Fitur ini hanya dapat digunakan di server.",
                ephemeral=True
            )

        # Semua jalur di bawah dapat melakukan query database / grant role.
        # Defer lebih awal supaya interaction tidak timeout.
        await interaction.response.defer(ephemeral=True)

        pair = await self.get_pair_by_member(
            guild.id,
            interaction.user.id
        )

        if not pair:

            return await interaction.followup.send(
                "Kamu belum terdaftar sebagai pasangan Apipi.",
                ephemeral=True
            )

        if pair["status"] == "active":

            return await interaction.followup.send(
                "Role Apipi sudah aktif.",
                ephemeral=True
            )

        if pair["status"] != "eligible":

            total = await self.get_total_seconds(
                pair["id"]
            )

            remaining = max(
                0,
                (UNLOCK_HOURS * 3600) - total
            )

            return await interaction.followup.send(
                (
                    f"Progress saat ini: "
                    f"**{format_hours(total)}**.\n"
                    f"Masih kurang **{format_duration(remaining)}** "
                    f"untuk mencapai {UNLOCK_HOURS} jam."
                ),
                ephemeral=True
            )

        is_siswa = (
            interaction.user.id
            == pair["siswa_id"]
        )

        is_siswi = (
            interaction.user.id
            == pair["siswi_id"]
        )

        if not is_siswa and not is_siswi:

            return await interaction.followup.send(
                "Kamu bukan bagian dari pasangan ini.",
                ephemeral=True
            )

        now = db_datetime(
            utc_now()
        )

        if is_siswa:

            await db.execute(
                """
                UPDATE nanz_apipi_pairs
                SET
                    take_siswa = 1,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    now,
                    pair["id"]
                )
            )

            await self.log(
                pair["id"],
                interaction.user.id,
                "TAKE_APPROVED",
                "Siswa menyetujui pengambilan role."
            )

        elif is_siswi:

            await db.execute(
                """
                UPDATE nanz_apipi_pairs
                SET
                    take_siswi = 1,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    now,
                    pair["id"]
                )
            )

            await self.log(
                pair["id"],
                interaction.user.id,
                "TAKE_APPROVED",
                "Siswi menyetujui pengambilan role."
            )

        updated = await self.get_pair(
            pair["id"]
        )

        if not updated:

            return await interaction.followup.send(
                "Data pasangan tidak dapat diperbarui.",
                ephemeral=True
            )

        if (
            updated["take_siswa"]
            and updated["take_siswi"]
        ):

            success = await self.grant_apipi_role(
                updated,
                interaction.guild
            )

            if success:

                await interaction.followup.send(
                    (
                        f"{EMOJI_LOVE} Persetujuan kedua pihak "
                        "telah diterima. Role Apipi berhasil diberikan."
                    ),
                    ephemeral=True
                )

                return

            return await interaction.followup.send(
                "Persetujuan sudah lengkap, tetapi role gagal diberikan. "
                "Cek posisi role Apipi dan permission bot.",
                ephemeral=True
            )

        await interaction.followup.send(
            (
                f"{EMOJI_WAITING} Persetujuanmu sudah dicatat.\n"
                "Role akan diberikan setelah pasanganmu "
                "juga menyetujui."
            ),
            ephemeral=True
        )

    # ========================================================
    # GRANT ROLE
    # ========================================================

    async def grant_apipi_role(
        self,
        pair,
        guild
    ):

        siswa = guild.get_member(
            pair["siswa_id"]
        )

        siswi = guild.get_member(
            pair["siswi_id"]
        )

        if not siswa or not siswi:
            return False

        role = guild.get_role(
            APIPI_ROLE_ID
        )

        if not role:
            return False

        me = guild.me

        if not me:
            return False

        if role >= me.top_role:

            await self.log(
                pair["id"],
                None,
                "ROLE_ERROR",
                "Role Apipi berada di atas atau sama dengan role tertinggi bot."
            )

            return False

        try:

            if role not in siswa.roles:

                await siswa.add_roles(
                    role,
                    reason="Apipi role approved by both parties"
                )

            if role not in siswi.roles:

                await siswi.add_roles(
                    role,
                    reason="Apipi role approved by both parties"
                )

        except discord.Forbidden:

            await self.log(
                pair["id"],
                None,
                "ROLE_ERROR",
                "Bot tidak memiliki permission untuk memberikan role."
            )

            return False

        except discord.HTTPException as e:

            await self.log(
                pair["id"],
                None,
                "ROLE_ERROR",
                f"Discord API error saat memberikan role: {e}"
            )

            return False

        now = db_datetime(
            utc_now()
        )

        await db.execute(
            """
            UPDATE nanz_apipi_pairs
            SET
                status = 'active',
                take_siswa = 0,
                take_siswi = 0,
                remove_siswa = 0,
                remove_siswi = 0,
                active_since = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (
                now,
                now,
                pair["id"]
            )
        )

        await self.log(
            pair["id"],
            None,
            "ROLE_GRANTED",
            "Role Apipi diberikan kepada kedua pihak."
        )

        channel = self.bot.get_channel(
            APIPI_LOG_CHANNEL_ID
        )

        if channel:

            try:

                await channel.send(
                    (
                        f"{EMOJI_APIPI} **APIPI ROLE GRANTED**\n\n"
                        f"{siswa.mention} + {siswi.mention}\n"
                        f"Role: {role.mention}"
                    )
                )

            except Exception:
                pass

        await self.refresh_apipi_panels()

        return True

    # ========================================================
    # REMOVE APPROVAL
    # ========================================================

    async def approve_remove(
        self,
        interaction
    ):

        guild = interaction.guild

        if not guild:

            return await interaction.response.send_message(
                "Fitur ini hanya dapat digunakan di server.",
                ephemeral=True
            )

        pair = await self.get_pair_by_member(
            guild.id,
            interaction.user.id
        )

        if not pair:

            return await interaction.response.send_message(
                "Kamu belum terdaftar sebagai pasangan Apipi.",
                ephemeral=True
            )

        if pair["status"] != "active":

            return await interaction.response.send_message(
                "Role Apipi pasangan ini sedang tidak aktif.",
                ephemeral=True
            )

        is_siswa = (
            interaction.user.id
            == pair["siswa_id"]
        )

        is_siswi = (
            interaction.user.id
            == pair["siswi_id"]
        )

        if not is_siswa and not is_siswi:

            return await interaction.response.send_message(
                "Kamu bukan bagian dari pasangan ini.",
                ephemeral=True
            )

        now = db_datetime(
            utc_now()
        )

        if is_siswa:

            await db.execute(
                """
                UPDATE nanz_apipi_pairs
                SET
                    remove_siswa = 1,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    now,
                    pair["id"]
                )
            )

        elif is_siswi:

            await db.execute(
                """
                UPDATE nanz_apipi_pairs
                SET
                    remove_siswi = 1,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    now,
                    pair["id"]
                )
            )

        await self.log(
            pair["id"],
            interaction.user.id,
            "REMOVE_APPROVED",
            "Salah satu pihak menyetujui pencabutan role."
        )

        updated = await self.get_pair(
            pair["id"]
        )

        if not updated:

            return await interaction.response.send_message(
                "Data pasangan tidak ditemukan.",
                ephemeral=True
            )

        if (
            updated["remove_siswa"]
            and updated["remove_siswi"]
        ):

            success = await self.remove_apipi_role(
                updated,
                guild,
                "Mutual approval"
            )

            if success:

                await interaction.response.send_message(
                    (
                        f"{EMOJI_LOVE} Kedua pihak menyetujui "
                        "pencabutan role. Role Apipi telah dicabut "
                        "dan progress di-reset."
                    ),
                    ephemeral=True
                )

                return

            return await interaction.response.send_message(
                "Persetujuan sudah lengkap, tetapi role gagal dicabut.",
                ephemeral=True
            )

        await interaction.response.send_message(
            (
                f"{EMOJI_WAITING} Persetujuanmu sudah dicatat.\n"
                "Role akan dicabut setelah pasanganmu "
                "juga menyetujui."
            ),
            ephemeral=True
        )

    # ========================================================
    # REMOVE ROLE
    # ========================================================

    async def remove_apipi_role(
        self,
        pair,
        guild,
        reason
    ):

        role = guild.get_role(
            APIPI_ROLE_ID
        )

        siswa = guild.get_member(
            pair["siswa_id"]
        )

        siswi = guild.get_member(
            pair["siswi_id"]
        )

        if role:

            try:

                if siswa and role in siswa.roles:

                    await siswa.remove_roles(
                        role,
                        reason=reason
                    )

                if siswi and role in siswi.roles:

                    await siswi.remove_roles(
                        role,
                        reason=reason
                    )

            except discord.Forbidden:

                await self.log(
                    pair["id"],
                    None,
                    "ROLE_ERROR",
                    "Bot tidak dapat mencabut role Apipi."
                )

                return False

            except discord.HTTPException as e:

                await self.log(
                    pair["id"],
                    None,
                    "ROLE_ERROR",
                    f"Discord API error saat mencabut role: {e}"
                )

                return False

        now = db_datetime(
            utc_now()
        )

        await db.execute(
            """
            UPDATE nanz_apipi_pairs
            SET
                status = 'tracking',
                take_siswa = 0,
                take_siswi = 0,
                remove_siswa = 0,
                remove_siswi = 0,
                eligible_notified = 0,
                strike = 0,
                active_since = NULL,
                updated_at = %s
            WHERE id = %s
            """,
            (
                now,
                pair["id"]
            )
        )

        await db.execute(
            """
            DELETE FROM nanz_apipi_sessions
            WHERE pair_id = %s
            """,
            (pair["id"],)
        )

        await db.execute(
            """
            DELETE FROM nanz_apipi_weekly
            WHERE pair_id = %s
            """,
            (pair["id"],)
        )

        await self.log(
            pair["id"],
            None,
            "ROLE_REMOVED",
            reason
        )

        await self.refresh_apipi_panels()

        return True

    # ========================================================
    # VOICE STATE UPDATE
    # ========================================================

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member,
        before,
        after
    ):

        if not self.initialized:
            return

        guild = member.guild

        try:

            pair = await self.get_pair_by_member(
                guild.id,
                member.id
            )

        except Exception as e:

            print(
                f"[APIPI] Error mencari pair pada voice update: {e}"
            )

            return

        if not pair:
            return

        async with self.session_lock:

            try:

                await self.sync_pair_voice(
                    pair
                )

            except Exception as e:

                print(
                    f"[APIPI] Error sync voice pair "
                    f"{pair.get('id')}: {e}"
                )

    # ========================================================
    # SYNC PAIR VOICE
    # ========================================================

    async def sync_pair_voice(
        self,
        pair
    ):

        channel = self.get_shared_channel(
            pair
        )

        live = await db.fetchone(
            """
            SELECT *
            FROM nanz_apipi_live_sessions
            WHERE pair_id = %s
            LIMIT 1
            """,
            (pair["id"],)
        )

        if channel:

            if not live:

                await self.start_session(
                    pair,
                    channel.id
                )

            elif live["channel_id"] != channel.id:

                await self.close_session(
                    pair["id"],
                    utc_now()
                )

                await self.start_session(
                    pair,
                    channel.id
                )

        else:

            if live:

                await self.close_session(
                    pair["id"],
                    utc_now()
                )

    # ========================================================
    # VOICE SESSION DISCOVERY / RECONCILIATION
    # ========================================================

    async def reconcile_all_pairs(self):
        """
        Sinkronisasi seluruh pair yang masih memiliki status tracking.

        Ini sengaja tidak hanya membaca nanz_apipi_live_sessions karena
        live session bisa belum pernah dibuat, misalnya pasangan sudah
        berada di VC yang sama sebelum bot/restart/registrasi pair.
        """

        try:
            pairs = await db.fetchall(
                """
                SELECT *
                FROM nanz_apipi_pairs
                WHERE status IN ('tracking', 'eligible', 'active')
                ORDER BY id ASC
                """
            )
        except Exception as e:
            print(f"[APIPI] Pair discovery database error: {e}")
            return

        for pair in pairs:
            try:
                await self.sync_pair_voice(pair)
            except Exception as e:
                print(
                    f"[APIPI] Pair discovery error pair={pair.get('id')}: {e}"
                )

    # ========================================================
    # HEARTBEAT
    # ========================================================

    @tasks.loop(seconds=HEARTBEAT_SECONDS)
    async def heartbeat(self):

        if not self.initialized:
            return

        # Heartbeat sekarang menjadi safety-net sekaligus discovery.
        # Dengan begitu, sesi tetap dibuat walaupun voice event terlewat.
        async with self.session_lock:

            await self.reconcile_all_pairs()

            try:
                live_sessions = await db.fetchall(
                    """
                    SELECT *
                    FROM nanz_apipi_live_sessions
                    """
                )
            except Exception as e:
                print(f"[APIPI] Heartbeat database error: {e}")
                return

            for live in live_sessions:
                try:
                    pair = await self.get_pair(live["pair_id"])

                    if not pair:
                        await db.execute(
                            """
                            DELETE FROM nanz_apipi_live_sessions
                            WHERE pair_id = %s
                            """,
                            (live["pair_id"],)
                        )
                        continue

                    channel = self.get_shared_channel(pair)

                    if not channel:
                        await self.close_session(
                            pair["id"],
                            utc_now()
                        )
                        continue

                    # Jika pasangan pindah VC, tutup sesi lama dan mulai
                    # sesi baru dari channel yang baru.
                    if channel.id != live["channel_id"]:
                        await self.close_session(
                            pair["id"],
                            utc_now()
                        )
                        await self.start_session(
                            pair,
                            channel.id
                        )
                        continue

                    await db.execute(
                        """
                        UPDATE nanz_apipi_live_sessions
                        SET last_seen_at = %s
                        WHERE pair_id = %s
                        """,
                        (
                            db_datetime(utc_now()),
                            pair["id"]
                        )
                    )

                    await self.check_eligibility(pair)

                except Exception as e:
                    print(
                        f"[APIPI] Heartbeat error "
                        f"pair={live.get('pair_id')}: {e}"
                    )

    # ========================================================
    # RECONCILE AFTER RESTART
    # ========================================================

    async def reconcile_after_restart(self):

        await self.bot.wait_until_ready()
        await asyncio.sleep(5)

        async with self.session_lock:

            try:
                live_sessions = await db.fetchall(
                    """
                    SELECT *
                    FROM nanz_apipi_live_sessions
                    """
                )
            except Exception as e:
                print(f"[APIPI] Reconcile database error: {e}")
                return

            # Sesi lama dipotong sampai last_seen sebelum bot mati.
            # Jangan menghitung waktu ketika bot benar-benar tidak berjalan.
            for live in live_sessions:
                try:
                    pair = await self.get_pair(live["pair_id"])

                    if not pair:
                        await db.execute(
                            """
                            DELETE FROM nanz_apipi_live_sessions
                            WHERE pair_id = %s
                            """,
                            (live["pair_id"],)
                        )
                        continue

                    start_time = from_db_datetime(live["started_at"])
                    last_seen = from_db_datetime(live["last_seen_at"])

                    if start_time and last_seen and last_seen > start_time:
                        await self.save_split_sessions(
                            pair["id"],
                            start_time,
                            last_seen
                        )

                    await db.execute(
                        """
                        DELETE FROM nanz_apipi_live_sessions
                        WHERE pair_id = %s
                        """,
                        (pair["id"],)
                    )

                except Exception as e:
                    print(
                        f"[APIPI] Reconcile pair error "
                        f"{live.get('pair_id')}: {e}"
                    )

            # Setelah sesi lama dibereskan, scan ulang semua pair.
            # Jika pasangan masih berada di VC yang sama, sesi baru langsung
            # dibuat dari waktu bot kembali aktif.
            await self.reconcile_all_pairs()

    # ========================================================

    # ========================================================
    # STATUS
    # ========================================================

    async def get_status_text(
        self,
        pair
    ):

        siswa = self.find_member(
            pair["siswa_id"]
        )

        siswi = self.find_member(
            pair["siswi_id"]
        )

        total = await self.get_total_seconds(
            pair["id"]
        )

        if pair["status"] == "active":

            week_start = get_week_start_date(
                utc_now()
            )

            weekly = await self.get_week_seconds(
                pair["id"],
                week_start
            )

            status_text = "Aktif"

            progress = (
                f"{format_hours(weekly)} / "
                f"{WEEKLY_HOURS} jam"
            )

        elif pair["status"] == "eligible":

            status_text = "Menunggu persetujuan"

            progress = (
                f"{format_hours(total)} / "
                f"{UNLOCK_HOURS} jam"
            )

        else:

            status_text = "Tracking"

            progress = (
                f"{format_hours(total)} / "
                f"{UNLOCK_HOURS} jam"
            )

        return (
            f"{EMOJI_APIPI} **STATUS APIPI**\n\n"
            f"**Siswa:** "
            f"{siswa.mention if siswa else pair['siswa_id']}\n"
            f"**Siswi:** "
            f"{siswi.mention if siswi else pair['siswi_id']}\n\n"
            f"**Status:** {status_text}\n"
            f"**Progress:** {progress}\n"
            f"**Strike:** {pair['strike']}/{MAX_STRIKE}\n\n"
            f"Persetujuan Ambil:\n"
            f"• Siswa: "
            f"{'✓' if pair['take_siswa'] else '—'}\n"
            f"• Siswi: "
            f"{'✓' if pair['take_siswi'] else '—'}\n\n"
            f"Persetujuan Cabut:\n"
            f"• Siswa: "
            f"{'✓' if pair['remove_siswa'] else '—'}\n"
            f"• Siswi: "
            f"{'✓' if pair['remove_siswi'] else '—'}"
        )

    # ========================================================
    # LOG
    # ========================================================

    async def log(
        self,
        pair_id,
        actor_id,
        action,
        details
    ):

        try:

            await db.execute(
                """
                INSERT INTO nanz_apipi_logs
                (
                    pair_id,
                    actor_id,
                    action,
                    details,
                    created_at
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    pair_id,
                    actor_id,
                    action,
                    details,
                    db_datetime(utc_now())
                )
            )

        except Exception as e:

            print(
                f"[APIPI] Gagal menyimpan database log: {e}"
            )

        channel = self.bot.get_channel(
            APIPI_LOG_CHANNEL_ID
        )

        if not channel:
            return

        actor_text = (
            f"<@{actor_id}>"
            if actor_id
            else "nanZ Server - Official Bot"
        )

        embed = discord.Embed(
            title="APIPI LOG",
            description=(
                f"**Action:** `{action}`\n"
                f"**Actor:** {actor_text}\n"
                f"**Pair ID:** `{pair_id}`\n\n"
                f"{details}"
            ),
            color=discord.Color.blurple(),
            timestamp=utc_now()
        )

        try:

            await channel.send(
                embed=embed
            )

        except Exception as e:

            print(
                f"[APIPI] Gagal mengirim log Discord: {e}"
            )

    async def get_pair_rundown(self):
        try:
            return await db.fetchall(
                """
                SELECT *
                FROM nanz_apipi_pairs
                WHERE status != 'removed'
                ORDER BY id DESC
                """
            )
        except Exception as e:
            print(f"[APIPI] Gagal mengambil rundown pasangan: {e}")
            return []

    # ========================================================
    # ADMIN CHECK
    # ========================================================

    def is_admin(
        self,
        interaction
    ):

        if not interaction:
            return False

        guild = interaction.guild

        if not guild:
            return False

        user = interaction.user

        if not user:
            return False

        permissions = getattr(
            user,
            "guild_permissions",
            None
        )

        if not permissions:
            return False

        return permissions.administrator

    # ========================================================
    # ADMIN STATUS
    # ========================================================

    async def admin_status(
        self,
        interaction,
        user_id
    ):

        pair = await self.get_pair_by_member(
            interaction.guild.id,
            user_id,
            include_removed=True
        )

        if not pair:

            return await interaction.response.send_message(
                "Pasangan tidak ditemukan.",
                ephemeral=True
            )

        text = await self.get_status_text(
            pair
        )

        await interaction.response.send_message(
            text,
            ephemeral=True
        )

    # ========================================================
    # ADMIN SET ROLE
    # ========================================================

    async def admin_set_role(
        self,
        interaction,
        user_id
    ):

        pair = await self.get_pair_by_member(
            interaction.guild.id,
            user_id
        )

        if not pair:

            return await interaction.response.send_message(
                "Pasangan aktif tidak ditemukan.",
                ephemeral=True
            )

        success = await self.grant_apipi_role(
            pair,
            interaction.guild
        )

        if not success:

            return await interaction.response.send_message(
                "Role gagal diberikan. Cek posisi role dan permission bot.",
                ephemeral=True
            )

        await self.log(
            pair["id"],
            interaction.user.id,
            "ADMIN_SET_ROLE",
            "Administrator memberikan role Apipi secara manual."
        )

        await interaction.response.send_message(
            "Role Apipi berhasil diberikan secara manual.",
            ephemeral=True
        )

    # ========================================================
    # ADMIN REMOVE ROLE
    # ========================================================

    async def admin_remove_role(
        self,
        interaction,
        user_id
    ):

        pair = await self.get_pair_by_member(
            interaction.guild.id,
            user_id
        )

        if not pair:

            return await interaction.response.send_message(
                "Pasangan tidak ditemukan.",
                ephemeral=True
            )

        success = await self.remove_apipi_role(
            pair,
            interaction.guild,
            "Administrator manual removal"
        )

        if not success:

            return await interaction.response.send_message(
                "Role gagal dicabut.",
                ephemeral=True
            )

        await self.log(
            pair["id"],
            interaction.user.id,
            "ADMIN_REMOVE_ROLE",
            "Administrator mencabut role Apipi."
        )

        await interaction.response.send_message(
            "Role Apipi berhasil dicabut dan progress di-reset.",
            ephemeral=True
        )

    # ========================================================
    # ADMIN RESET PROGRESS
    # ========================================================

    async def admin_reset_progress(
        self,
        interaction,
        user_id
    ):

        # Ack interaction immediately so database work cannot expire the Discord interaction.
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        async def reply(content):
            return await interaction.followup.send(
                content,
                ephemeral=True
            )

        pair = await self.get_pair_by_member(
            interaction.guild.id,
            user_id
        )

        if not pair:

            return await reply("Pasangan tidak ditemukan.")

        pair_id = int(pair["id"])

        # Jangan gunakan placeholder %s di sini. Wrapper database nanZ
        # melakukan Python-style query formatting sebelum diteruskan ke aiomysql,
        # sehingga query tertentu dapat memicu "not enough arguments for format string".
        await db.execute(
            f"""
            DELETE FROM nanz_apipi_sessions
            WHERE pair_id = {pair_id}
            """
        )

        await db.execute(
            f"""
            DELETE FROM nanz_apipi_weekly
            WHERE pair_id = {pair_id}
            """
        )

        now = db_datetime(
            utc_now()
        )
        now_sql = now.strftime("%Y-%m-%d %H:%M:%S")

        await db.execute(
            f"""
            UPDATE nanz_apipi_pairs
            SET
                status = 'tracking',
                eligible_notified = 0,
                take_siswa = 0,
                take_siswi = 0,
                remove_siswa = 0,
                remove_siswi = 0,
                updated_at = '{now_sql}'
            WHERE id = {pair_id}
            """
        )

        await self.log(
            pair["id"],
            interaction.user.id,
            "ADMIN_RESET_PROGRESS",
            "Administrator mereset progress Apipi."
        )

        await self.refresh_apipi_panels()

        await reply("Progress Apipi berhasil di-reset.")

    # ========================================================
    # ADMIN RESET STRIKE
    # ========================================================

    async def admin_reset_strike(
        self,
        interaction,
        user_id
    ):

        pair = await self.get_pair_by_member(
            interaction.guild.id,
            user_id,
            include_removed=True
        )

        if not pair:

            return await interaction.response.send_message(
                "Pasangan tidak ditemukan.",
                ephemeral=True
            )

        now = db_datetime(
            utc_now()
        )

        await db.execute(
            """
            UPDATE nanz_apipi_pairs
            SET
                strike = 0,
                updated_at = %s
            WHERE id = %s
            """,
            (
                now,
                pair["id"]
            )
        )

        await self.log(
            pair["id"],
            interaction.user.id,
            "ADMIN_RESET_STRIKE",
            "Administrator mereset strike menjadi 0."
        )

        await self.refresh_apipi_panels()

        await interaction.response.send_message(
            "Strike berhasil di-reset menjadi 0.",
            ephemeral=True
        )


# ============================================================
# MEMBER SELECT HELPERS
# ============================================================

class ApipiUserSelect(discord.ui.UserSelect):

    def __init__(self, placeholder="Pilih member...", custom_id=None):
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            custom_id=custom_id
        )


class RegisterPairView(discord.ui.View):

    def __init__(self, cog, author_id):
        super().__init__(timeout=180)
        self.cog = cog
        self.author_id = author_id
        self.siswa = None
        self.siswi = None

        self.siswa_select = ApipiUserSelect(
            "Pilih Siswa...",
            "nanz_apipi_register_siswa"
        )
        self.siswi_select = ApipiUserSelect(
            "Pilih Siswi...",
            "nanz_apipi_register_siswi"
        )

        self.siswa_select.callback = self.siswa_callback
        self.siswi_select.callback = self.siswi_callback
        self.add_item(self.siswa_select)
        self.add_item(self.siswi_select)

    async def _check_author(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Menu ini bukan milikmu.",
                ephemeral=True
            )
            return False
        return True

    async def siswa_callback(self, interaction):
        if not await self._check_author(interaction):
            return
        self.siswa = self.siswa_select.values[0]
        await interaction.response.send_message(
            f"Siswa dipilih: **{self.siswa.display_name}**.",
            ephemeral=True
        )

    async def siswi_callback(self, interaction):
        if not await self._check_author(interaction):
            return
        self.siswi = self.siswi_select.values[0]
        await interaction.response.send_message(
            f"Siswi dipilih: **{self.siswi.display_name}**.",
            ephemeral=True
        )

    @discord.ui.button(
        label="Daftarkan Pasangan",
        style=discord.ButtonStyle.success,
        custom_id="nanz_apipi_register_confirm"
    )
    async def confirm(self, interaction, button):
        if not await self._check_author(interaction):
            return

        if not self.siswa or not self.siswi:
            return await interaction.response.send_message(
                "Pilih Siswa dan Siswi terlebih dahulu.",
                ephemeral=True
            )

        if self.siswa.id == self.siswi.id:
            return await interaction.response.send_message(
                "Siswa dan Siswi tidak boleh member yang sama.",
                ephemeral=True
            )

        if not self.cog.validate_pair_roles(self.siswa, self.siswi):
            return await interaction.response.send_message(
                "Pasangan tidak valid. Apipi wajib terdiri dari **1 Siswa + 1 Siswi**.",
                ephemeral=True
            )

        # Database/refresh panel bisa membutuhkan >3 detik.
        # Defer terlebih dahulu agar Discord tidak menampilkan Interaction Failed.
        await interaction.response.defer(ephemeral=True)

        try:
            pair, result = await self.cog.create_pair(
                interaction.guild.id,
                self.siswa.id,
                self.siswi.id,
                interaction.user.id
            )

            messages = {
                "siswa_busy": "Siswa tersebut sudah memiliki pasangan Apipi.",
                "siswi_busy": "Siswi tersebut sudah memiliki pasangan Apipi."
            }

            if result in messages:
                return await interaction.edit_original_response(
                    content=messages[result],
                    view=self
                )

            if not pair:
                return await interaction.edit_original_response(
                    content="Gagal membuat pasangan. Cek log nanZ System Monitor.",
                    view=self
                )

            self.stop()
            await interaction.edit_original_response(
                content=(
                    f"{EMOJI_APIPI} **Pasangan Apipi berhasil didaftarkan.**\n\n"
                    f"**Siswa:** {self.siswa.mention}\n"
                    f"**Siswi:** {self.siswi.mention}\n\n"
                    f"Selanjutnya kumpulkan **{UNLOCK_HOURS} jam** shared voice.\n\n"
                    "Jika salah memilih pasangan, gunakan tombol **Reset Pasangan** "
                    "di panel Apipi selama role belum aktif."
                ),
                view=None
            )

        except Exception as e:
            print(f"[APIPI] Register pair confirm error: {e}")
            try:
                await interaction.edit_original_response(
                    content="Terjadi kesalahan saat mendaftarkan pasangan. Silakan coba lagi.",
                    view=self
                )
            except Exception as edit_error:
                print(f"[APIPI] Register pair error response failed: {edit_error}")



class AdminMemberSelectView(discord.ui.View):

    def __init__(self, cog, author_id, action_name):
        super().__init__(timeout=180)
        self.cog = cog
        self.author_id = author_id
        self.action_name = action_name

        self.member_select = ApipiUserSelect(
            "Cari / pilih member...",
            "nanz_apipi_admin_member_select"
        )
        self.member_select.callback = self.member_callback
        self.add_item(self.member_select)

    async def member_callback(self, interaction):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message(
                "Menu ini bukan milikmu.",
                ephemeral=True
            )

        if not self.member_select.values:
            return await interaction.response.send_message(
                "Member belum dipilih.",
                ephemeral=True
            )

        member = self.member_select.values[0]
        self.stop()

        if self.action_name == "Cek Status":
            return await self.cog.admin_status(interaction, member.id)
        if self.action_name == "Set Role":
            return await self.cog.admin_set_role(interaction, member.id)
        if self.action_name == "Cabut Role":
            return await self.cog.admin_remove_role(interaction, member.id)
        if self.action_name == "Reset Progress":
            return await self.cog.admin_reset_progress(interaction, member.id)
        if self.action_name == "Reset Strike":
            return await self.cog.admin_reset_strike(interaction, member.id)

        await interaction.response.send_message(
            "Action management tidak dikenali.",
            ephemeral=True
        )


class PairListView(discord.ui.View):

    def __init__(self, cog, author_id, page=0):
        super().__init__(timeout=180)
        self.cog = cog
        self.author_id = author_id
        self.page = page

    async def build_embed(self):
        rows = await self.cog.get_pair_rundown()
        per_page = 10
        total_pages = max(1, (len(rows) + per_page - 1) // per_page)
        self.page = max(0, min(self.page, total_pages - 1))
        chunk = rows[self.page * per_page:(self.page + 1) * per_page]

        lines = []
        for pair in chunk:
            siswa = self.cog.find_member(pair["siswa_id"])
            siswi = self.cog.find_member(pair["siswi_id"])
            siswa_text = siswa.mention if siswa else str(pair["siswa_id"])
            siswi_text = siswi.mention if siswi else str(pair["siswi_id"])
            lines.append(
                f"`#{pair['id']}` {siswa_text} × {siswi_text} — "
                f"`{pair['status']}` — Strike `{pair['strike']}/{MAX_STRIKE}`"
            )

        embed = discord.Embed(
            title="APIPI — DAFTAR PASANGAN",
            description=(
                "\n".join(lines)
                if lines else "Belum ada pasangan Apipi."
            ),
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"Halaman {self.page + 1}/{total_pages} • Pilih member pada menu management untuk mencari pasangan.")
        return embed

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Menu ini bukan milikmu.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="‹", style=discord.ButtonStyle.secondary, custom_id="nanz_apipi_pair_prev")
    async def previous(self, interaction, button):
        self.page -= 1
        embed = await self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="›", style=discord.ButtonStyle.secondary, custom_id="nanz_apipi_pair_next")
    async def next_page(self, interaction, button):
        self.page += 1
        embed = await self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

# ============================================================
# MEMBER PANEL
# ============================================================

class ApipiMemberPanel(
    discord.ui.View
):

    def __init__(
        self,
        cog
    ):

        super().__init__(
            timeout=None
        )

        self.cog = cog

    # ========================================================
    # DAFTAR PASANGAN
    # ========================================================

    @discord.ui.button(
        label="Daftar Pasangan",
        style=discord.ButtonStyle.primary,
        custom_id="nanz_apipi_register"
    )
    async def register(
        self,
        interaction,
        button
    ):

        try:

            await interaction.response.send_message(
                f"{EMOJI_APIPI} **Pilih Pasangan Apipi**\n\n"
                "Gunakan menu di bawah. Discord akan menampilkan daftar member "
                "dan kamu bisa langsung mencari username tanpa copy ID.",
                view=RegisterPairView(self.cog, interaction.user.id),
                ephemeral=True
            )

        except Exception as e:

            print(
                f"[APIPI] Register button error: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "Gagal membuka form pendaftaran.",
                    ephemeral=True
                )

    # ========================================================
    # RESET PASANGAN
    # ========================================================

    @discord.ui.button(
        label="Reset Pasangan",
        style=discord.ButtonStyle.danger,
        custom_id="nanz_apipi_reset_pair"
    )
    async def reset_pair(
        self,
        interaction,
        button
    ):

        try:
            if not interaction.guild:
                return await interaction.response.send_message(
                    "Fitur ini hanya dapat digunakan di server.",
                    ephemeral=True
                )

            # Reset dapat menyentuh database dan refresh panel, jadi defer dulu.
            await interaction.response.defer(ephemeral=True)

            success, result = await self.cog.reset_pair_selection(
                interaction.guild.id,
                interaction.user.id,
                interaction.user.id
            )

            if not success:
                messages = {
                    "not_found": "Kamu belum memiliki pasangan Apipi yang bisa di-reset.",
                    "already_active": "Pasangan sudah aktif/role Apipi sudah digunakan. Pasangan tidak dapat di-reset dari sini."
                }
                return await interaction.followup.send(
                    messages.get(result, "Pasangan tidak dapat di-reset."),
                    ephemeral=True
                )

            await interaction.followup.send(
                (
                    f"{EMOJI_APIPI} **Pasangan Apipi berhasil di-reset.**\n\n"
                    "Progress pasangan lama dihapus dan kamu sekarang bisa "
                    "memilih pasangan baru."
                ),
                ephemeral=True
            )

        except Exception as e:
            print(f"[APIPI] Reset pair button error: {e}")
            if interaction.response.is_done():
                try:
                    await interaction.followup.send(
                        "Terjadi kesalahan saat me-reset pasangan. Silakan coba lagi.",
                        ephemeral=True
                    )
                except Exception as edit_error:
                    print(f"[APIPI] Reset pair error response failed: {edit_error}")
            else:
                await interaction.response.send_message(
                    "Terjadi kesalahan saat me-reset pasangan. Silakan coba lagi.",
                    ephemeral=True
                )

    # ========================================================
    # AMBIL ROLE
    # ========================================================

    @discord.ui.button(
        label="Ambil Role",
        style=discord.ButtonStyle.success,
        custom_id="nanz_apipi_take"
    )
    async def take(
        self,
        interaction,
        button
    ):

        try:

            await self.cog.approve_take(
                interaction
            )

        except Exception as e:

            print(
                f"[APIPI] Take button error: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "Terjadi kesalahan saat memproses Ambil Role.",
                    ephemeral=True
                )

    # ========================================================
    # CABUT ROLE
    # ========================================================

    @discord.ui.button(
        label="Cabut Role",
        style=discord.ButtonStyle.danger,
        custom_id="nanz_apipi_remove"
    )
    async def remove(
        self,
        interaction,
        button
    ):

        try:

            await self.cog.approve_remove(
                interaction
            )

        except Exception as e:

            print(
                f"[APIPI] Remove button error: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "Terjadi kesalahan saat memproses Cabut Role.",
                    ephemeral=True
                )

    # ========================================================
    # STATUS
    # ========================================================

    @discord.ui.button(
        label="Status",
        style=discord.ButtonStyle.secondary,
        custom_id="nanz_apipi_status"
    )
    async def status(
        self,
        interaction,
        button
    ):

        try:

            if not interaction.guild:

                return await interaction.response.send_message(
                    "Fitur ini hanya dapat digunakan di server.",
                    ephemeral=True
                )

            pair = await self.cog.get_pair_by_member(
                interaction.guild.id,
                interaction.user.id
            )

            if not pair:

                return await interaction.response.send_message(
                    "Kamu belum memiliki pasangan Apipi.",
                    ephemeral=True
                )

            text = await self.cog.get_status_text(
                pair
            )

            await interaction.response.send_message(
                text,
                ephemeral=True
            )

        except Exception as e:

            print(
                f"[APIPI] Status button error: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "Terjadi kesalahan saat mengambil status.",
                    ephemeral=True
                )

    # ========================================================
    # KETENTUAN
    # ========================================================

    @discord.ui.button(
        label="Ketentuan",
        style=discord.ButtonStyle.secondary,
        custom_id="nanz_apipi_rules"
    )
    async def rules(
        self,
        interaction,
        button
    ):

        try:

            embed = discord.Embed(
                title="APIPI — KETENTUAN",
                description=(
                    f"{EMOJI_APIPI} **Syarat Awal**\n"
                    "• 1 Siswa + 1 Siswi.\n"
                    "• Terdaftar sebagai satu pasangan.\n"
                    f"• Shared voice minimal **{UNLOCK_HOURS} jam**.\n\n"

                    f"{EMOJI_LOVE} **Pengambilan Role**\n"
                    "• Tidak otomatis diberikan.\n"
                    "• Kedua pihak wajib menyetujui.\n\n"

                    f"{EMOJI_ARROW_BLUE} **Setelah Aktif**\n"
                    f"• Minimal **{WEEKLY_HOURS} jam / minggu**.\n"
                    "• Perhitungan berdasarkan waktu keduanya "
                    "berada di VC yang sama.\n"
                    "• AFK tetap dihitung.\n\n"

                    f"{EMOJI_WAITING} **Strike**\n"
                    "• Target mingguan tidak terpenuhi = 1 strike.\n"
                    f"• Maksimal {MAX_STRIKE} strike.\n"
                    "• Strike ke-3 = role dicabut otomatis.\n"
                    "• Strike tidak otomatis kembali ke 0.\n\n"

                    f"{EMOJI_LOVE} **Cabut Role**\n"
                    "• Kedua pihak harus menyetujui.\n"
                    "• Setelah dicabut, progress 20 jam kembali ke 0."
                ),
                color=discord.Color.blurple()
            )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )

        except Exception as e:

            print(
                f"[APIPI] Rules button error: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "Terjadi kesalahan saat membuka ketentuan.",
                    ephemeral=True
                )

    # ========================================================
    # VIEW ERROR HANDLER
    # ========================================================

    async def on_error(
        self,
        interaction,
        error,
        item
    ):

        print(
            "[APIPI MEMBER PANEL] "
            f"Error pada "
            f"{getattr(item, 'custom_id', 'unknown')}: "
            f"{error}"
        )

        try:

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "Terjadi kesalahan pada sistem Apipi. "
                    "Silakan coba lagi.",
                    ephemeral=True
                )

        except Exception as e:

            print(
                "[APIPI MEMBER PANEL] "
                f"Gagal mengirim error response: {e}"
            )


# ============================================================
# MANAGEMENT PANEL
# ============================================================

class ApipiManagementPanel(
    discord.ui.View
):

    def __init__(
        self,
        cog
    ):

        super().__init__(
            timeout=None
        )

        self.cog = cog

    # ========================================================
    # CHECK ADMIN
    # ========================================================

    async def check_admin(
        self,
        interaction
    ):

        if not self.cog.is_admin(
            interaction
        ):

            await interaction.response.send_message(
                "Akses ditolak. Hanya Administrator.",
                ephemeral=True
            )

            return False

        return True

    # ========================================================
    # CEK STATUS
    # ========================================================

    @discord.ui.button(
        label="Cek Status",
        style=discord.ButtonStyle.secondary,
        custom_id="nanz_apipi_admin_status"
    )
    async def status(
        self,
        interaction,
        button
    ):

        try:

            if not await self.check_admin(
                interaction
            ):
                return

            await interaction.response.send_message(
                "**Cek Status**\nPilih member untuk melihat pasangan dan progress:",
                view=AdminMemberSelectView(self.cog, interaction.user.id, "Cek Status"),
                ephemeral=True
            )

        except Exception as e:

            print(
                f"[APIPI] Admin status button error: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "Gagal membuka form Cek Status.",
                    ephemeral=True
                )

    # ========================================================
    # SET ROLE
    # ========================================================

    @discord.ui.button(
        label="Set Role",
        style=discord.ButtonStyle.success,
        custom_id="nanz_apipi_admin_set"
    )
    async def set_role(
        self,
        interaction,
        button
    ):

        try:

            if not await self.check_admin(
                interaction
            ):
                return

            await interaction.response.send_message(
                "**Set Role**\nPilih member untuk diproses:",
                view=AdminMemberSelectView(self.cog, interaction.user.id, "Set Role"),
                ephemeral=True
            )

        except Exception as e:

            print(
                f"[APIPI] Admin set role button error: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "Gagal membuka form Set Role.",
                    ephemeral=True
                )

    # ========================================================
    # CABUT ROLE
    # ========================================================

    @discord.ui.button(
        label="Cabut Role",
        style=discord.ButtonStyle.danger,
        custom_id="nanz_apipi_admin_remove"
    )
    async def remove_role(
        self,
        interaction,
        button
    ):

        try:

            if not await self.check_admin(
                interaction
            ):
                return

            await interaction.response.send_message(
                "**Cabut Role**\nPilih member untuk diproses:",
                view=AdminMemberSelectView(self.cog, interaction.user.id, "Cabut Role"),
                ephemeral=True
            )

        except Exception as e:

            print(
                f"[APIPI] Admin remove role button error: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "Gagal membuka form Cabut Role.",
                    ephemeral=True
                )

    # ========================================================
    # RESET PROGRESS
    # ========================================================

    @discord.ui.button(
        label="Reset Progress",
        style=discord.ButtonStyle.primary,
        custom_id="nanz_apipi_admin_reset_progress"
    )
    async def reset_progress(
        self,
        interaction,
        button
    ):

        try:

            if not await self.check_admin(
                interaction
            ):
                return

            await interaction.response.send_message(
                "**Reset Progress**\nPilih member untuk diproses:",
                view=AdminMemberSelectView(self.cog, interaction.user.id, "Reset Progress"),
                ephemeral=True
            )

        except Exception as e:

            print(
                f"[APIPI] Admin reset progress button error: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "Gagal membuka form Reset Progress.",
                    ephemeral=True
                )

    # ========================================================
    # RESET STRIKE
    # ========================================================

    @discord.ui.button(
        label="Reset Strike",
        style=discord.ButtonStyle.secondary,
        custom_id="nanz_apipi_admin_reset_strike"
    )
    async def reset_strike(
        self,
        interaction,
        button
    ):

        try:

            if not await self.check_admin(
                interaction
            ):
                return

            await interaction.response.send_message(
                "**Reset Strike**\nPilih member untuk diproses:",
                view=AdminMemberSelectView(self.cog, interaction.user.id, "Reset Strike"),
                ephemeral=True
            )

        except Exception as e:

            print(
                f"[APIPI] Admin reset strike button error: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "Gagal membuka form Reset Strike.",
                    ephemeral=True
                )

    # ========================================================
    # CARI PASANGAN
    # ========================================================

    @discord.ui.button(
        label="Cari Pasangan",
        style=discord.ButtonStyle.secondary,
        custom_id="nanz_apipi_admin_find_pair"
    )
    async def find_pair(self, interaction, button):
        try:
            if not await self.check_admin(interaction):
                return

            await interaction.response.send_message(
                "**Cari Pasangan**\nPilih member atau ketik username pada daftar Discord:",
                view=AdminMemberSelectView(self.cog, interaction.user.id, "Cek Status"),
                ephemeral=True
            )

        except Exception as e:
            print(f"[APIPI] Admin find pair button error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Gagal membuka pencarian pasangan.",
                    ephemeral=True
                )

    # ========================================================
    # DAFTAR PASANGAN
    # ========================================================

    @discord.ui.button(
        label="Daftar Pasangan",
        style=discord.ButtonStyle.primary,
        custom_id="nanz_apipi_admin_pairs"
    )
    async def pairs(self, interaction, button):
        try:
            if not await self.check_admin(interaction):
                return

            view = PairListView(
                self.cog,
                interaction.user.id
            )

            await interaction.response.send_message(
                f"{EMOJI_APIPI} **Rundown Pasangan Apipi**",
                embed=await view.build_embed(),
                view=view,
                ephemeral=True
            )

        except Exception as e:
            print(f"[APIPI] Admin pair list button error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Gagal mengambil daftar pasangan.",
                    ephemeral=True
                )

    # ========================================================
    # VIEW ERROR HANDLER
    # ========================================================

    async def on_error(
        self,
        interaction,
        error,
        item
    ):

        print(
            "[APIPI MANAGEMENT PANEL] "
            f"Error pada "
            f"{getattr(item, 'custom_id', 'unknown')}: "
            f"{error}"
        )

        try:

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "Terjadi kesalahan pada sistem management Apipi.",
                    ephemeral=True
                )

        except Exception as e:

            print(
                "[APIPI MANAGEMENT PANEL] "
                f"Gagal mengirim error response: {e}"
            )


# ============================================================
# SETUP
# ============================================================

async def setup(bot):

    await bot.add_cog(
        Apipi(bot)
    )