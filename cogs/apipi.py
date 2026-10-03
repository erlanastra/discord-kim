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
# Semua emoji adalah custom emoji Discord.
# Button TIDAK menggunakan emoji.
# animated=True digunakan agar emoji ditampilkan sebagai
# custom animated emoji Discord.

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

    value = value.strip()

    match = re.search(r"\d{15,25}", value)

    if not match:
        return None

    try:
        return int(match.group())
    except ValueError:
        return None


def format_hours(seconds):
    """
    Contoh:
    7200 -> 2.00 jam
    """

    hours = seconds / 3600

    return f"{hours:.2f} jam"


def format_duration(seconds):
    """
    Contoh:
    7260 -> 2 jam 1 menit
    """

    seconds = int(seconds)

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

    Jika tabel sudah ada:
    - tidak dibuat ulang
    - data tetap digunakan
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

        # Persistent member panel
        self.bot.add_view(
            ApipiMemberPanel(self)
        )

        # Persistent management panel
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
            async for message in channel.history(limit=50):

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
                    except Exception:
                        pass

                    return

        except Exception:
            pass

        await channel.send(
            embed=self.member_panel_embed(),
            view=ApipiMemberPanel(self)
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
            async for message in channel.history(limit=50):

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
                            embed=self.management_panel_embed(),
                            view=ApipiManagementPanel(self)
                        )
                    except Exception:
                        pass

                    return

        except Exception:
            pass

        await channel.send(
            embed=self.management_panel_embed(),
            view=ApipiManagementPanel(self)
        )

    # ========================================================
    # EMBED MEMBER PANEL
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
                "mengatur status Apipi."
            ),
            color=discord.Color.blurple()
        )

        return embed

    # ========================================================
    # EMBED MANAGEMENT PANEL
    # ========================================================

    def management_panel_embed(self):

        embed = discord.Embed(
            title="APIPI — MANAGEMENT",
            description=(
                f"{EMOJI_APIPI} Panel khusus **Administrator**.\n\n"

                f"{EMOJI_ARROW_PURPLE} **Cek Status**\n"
                "Melihat data dan progress pasangan.\n\n"

                f"{EMOJI_ARROW_PURPLE} **Set Role**\n"
                "Memberikan role Apipi secara manual.\n\n"

                f"{EMOJI_ARROW_PURPLE} **Cabut Role**\n"
                "Mencabut role Apipi secara manual.\n\n"

                f"{EMOJI_ARROW_PURPLE} **Reset Progress**\n"
                "Menghapus progress 20 jam pasangan.\n\n"

                f"{EMOJI_ARROW_PURPLE} **Reset Strike**\n"
                "Mengembalikan strike pasangan menjadi 0.\n\n"

                f"{EMOJI_WAITING} Semua tindakan management "
                "akan dicatat ke log."
            ),
            color=discord.Color.dark_purple()
        )

        return embed

    # ========================================================
    # FIND MEMBER
    # ========================================================

    def find_member(self, user_id):

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

        if include_removed:

            # Dibuat dengan 2 placeholder parameter.
            # Ini menghindari format query yang bermasalah
            # pada aiomysql/database wrapper.
            return await db.fetchone(
                """
                SELECT *
                FROM nanz_apipi_pairs
                WHERE guild_id = %s
                AND %s IN (siswa_id, siswi_id)
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    guild_id,
                    user_id
                )
            )

        return await db.fetchone(
            """
            SELECT *
            FROM nanz_apipi_pairs
            WHERE guild_id = %s
            AND %s IN (siswa_id, siswi_id)
            AND status != 'removed'
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                guild_id,
                user_id
            )
        )

    # ========================================================
    # GET PAIR BY ID
    # ========================================================

    async def get_pair(self, pair_id):

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

        now = db_datetime(utc_now())

        await db.execute(
            """
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
                %s,
                %s,
                %s,
                'tracking',
                %s,
                %s
            )
            """,
            (
                guild_id,
                siswa_id,
                siswi_id,
                now,
                now
            )
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

        siswa, siswi = self.get_pair_members(pair)

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

        now = db_datetime(utc_now())

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

        cursor = start_time

        while cursor < end_time:

            current_week = get_week_start(cursor)

            next_boundary = current_week + timedelta(
                days=7
            )

            if next_boundary.tzinfo is None:

                next_boundary = next_boundary.replace(
                    tzinfo=WIB
                )

            next_boundary_utc = next_boundary.astimezone(
                UTC
            )

            segment_end = min(
                end_time,
                next_boundary_utc
            )

            duration = int(
                (segment_end - cursor).total_seconds()
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

    async def get_total_seconds(self, pair_id):

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
            result["total_seconds"] or 0
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
                    (utc_now() - start).total_seconds()
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
            result["seconds"] or 0
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

            week_start_utc = week_start_local.astimezone(
                UTC
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

    async def check_eligibility(self, pair):

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

            now = db_datetime(utc_now())

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

        pair = await self.get_pair_by_member(
            guild.id,
            interaction.user.id
        )

        if not pair:

            return await interaction.response.send_message(
                "Kamu belum terdaftar sebagai pasangan Apipi.",
                ephemeral=True
            )

        if pair["status"] == "active":

            return await interaction.response.send_message(
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

            return await interaction.response.send_message(
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

        now = db_datetime(utc_now())

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

        else:

            return await interaction.response.send_message(
                "Kamu bukan bagian dari pasangan ini.",
                ephemeral=True
            )

        updated = await self.get_pair(
            pair["id"]
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

                await interaction.response.send_message(
                    (
                        f"{EMOJI_LOVE} Persetujuan kedua pihak "
                        "telah diterima. Role Apipi berhasil diberikan."
                    ),
                    ephemeral=True
                )

                return

        await interaction.response.send_message(
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
                "Role Apipi berada di atas role bot."
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

        now = db_datetime(utc_now())

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

            await channel.send(
                (
                    f"{EMOJI_APIPI} **APIPI ROLE GRANTED**\n\n"
                    f"{siswa.mention} + {siswi.mention}\n"
                    f"Role: {role.mention}"
                )
            )

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

        now = db_datetime(utc_now())

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

        else:

            return await interaction.response.send_message(
                "Kamu bukan bagian dari pasangan ini.",
                ephemeral=True
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

        now = db_datetime(utc_now())

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

        # Reset progress 20 jam
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
                f"[APIPI] Error get_pair_by_member "
                f"pada voice state: {e}"
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
                    f"[APIPI] Error sync_pair_voice: {e}"
                )

    # ========================================================
    # SYNC PAIR VOICE
    # ========================================================

    async def sync_pair_voice(self, pair):

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
    # HEARTBEAT
    # ========================================================

    @tasks.loop(seconds=HEARTBEAT_SECONDS)
    async def heartbeat(self):

        if not self.initialized:
            return

        async with self.session_lock:

            live_sessions = await db.fetchall(
                """
                SELECT *
                FROM nanz_apipi_live_sessions
                """
            )

            for live in live_sessions:

                pair = await self.get_pair(
                    live["pair_id"]
                )

                if not pair:
                    continue

                channel = self.get_shared_channel(
                    pair
                )

                if not channel:

                    await self.close_session(
                        pair["id"],
                        utc_now()
                    )

                    continue

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

                await self.check_eligibility(
                    pair
                )

    # ========================================================
    # RECONCILE AFTER RESTART
    # ========================================================

    async def reconcile_after_restart(self):

        await self.bot.wait_until_ready()

        await asyncio.sleep(5)

        async with self.session_lock:

            live_sessions = await db.fetchall(
                """
                SELECT *
                FROM nanz_apipi_live_sessions
                """
            )

            for live in live_sessions:

                pair = await self.get_pair(
                    live["pair_id"]
                )

                if not pair:
                    continue

                last_seen = from_db_datetime(
                    live["last_seen_at"]
                )

                current_shared = self.get_shared_channel(
                    pair
                )

                if last_seen:

                    await self.save_split_sessions(
                        pair["id"],
                        from_db_datetime(
                            live["started_at"]
                        ),
                        last_seen
                    )

                await db.execute(
                    """
                    DELETE FROM nanz_apipi_live_sessions
                    WHERE pair_id = %s
                    """,
                    (pair["id"],)
                )

                if current_shared:

                    await self.start_session(
                        pair,
                        current_shared.id
                    )

    # ========================================================
    # WEEKLY CHECKER
    # ========================================================

    @tasks.loop(minutes=30)
    async def weekly_checker(self):

        if not self.initialized:
            return

        now = utc_now()

        current_week = get_week_start(
            now
        )

        previous_week = current_week - timedelta(
            days=7
        )

        pairs = await db.fetchall(
            """
            SELECT *
            FROM nanz_apipi_pairs
            WHERE status = 'active'
            """
        )

        for pair in pairs:

            active_since = pair["active_since"]

            if active_since:

                active_since_aware = from_db_datetime(
                    active_since
                )

                activation_week = get_week_start(
                    active_since_aware
                ).date()

                if previous_week.date() <= activation_week:
                    continue

            already_checked = await db.fetchone(
                """
                SELECT id
                FROM nanz_apipi_weekly
                WHERE pair_id = %s
                AND week_start = %s
                LIMIT 1
                """,
                (
                    pair["id"],
                    previous_week.date()
                )
            )

            if already_checked:
                continue

            seconds = await self.get_week_seconds(
                pair["id"],
                previous_week.date()
            )

            target_seconds = WEEKLY_HOURS * 3600

            met = seconds >= target_seconds

            new_strike = int(
                pair["strike"]
            )

            if not met:

                new_strike += 1

            await db.execute(
                """
                INSERT INTO nanz_apipi_weekly
                (
                    pair_id,
                    week_start,
                    seconds,
                    target_seconds,
                    met,
                    strike_after,
                    checked_at
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    pair["id"],
                    previous_week.date(),
                    seconds,
                    target_seconds,
                    1 if met else 0,
                    new_strike,
                    db_datetime(now)
                )
            )

            if met:

                await self.log(
                    pair["id"],
                    None,
                    "WEEK_MET",
                    (
                        f"Minggu {previous_week.date()} "
                        f"memenuhi target: "
                        f"{format_hours(seconds)}"
                    )
                )

            else:

                await db.execute(
                    """
                    UPDATE nanz_apipi_pairs
                    SET
                        strike = %s,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    (
                        new_strike,
                        db_datetime(now),
                        pair["id"]
                    )
                )

                await self.log(
                    pair["id"],
                    None,
                    "WEEK_MISSED",
                    (
                        f"Minggu {previous_week.date()} "
                        f"hanya {format_hours(seconds)}. "
                        f"Strike: {new_strike}/{MAX_STRIKE}"
                    )
                )

                await self.send_strike_notice(
                    pair,
                    seconds,
                    new_strike
                )

                if new_strike >= MAX_STRIKE:

                    guild = self.bot.get_guild(
                        pair["guild_id"]
                    )

                    if guild:

                        await self.remove_apipi_role(
                            pair,
                            guild,
                            "Auto removal: 3 weekly strikes"
                        )

                        await self.send_auto_remove_notice(
                            pair
                        )

    # ========================================================
    # STRIKE NOTICE
    # ========================================================

    async def send_strike_notice(
        self,
        pair,
        seconds,
        strike
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
                f"{EMOJI_WAITING} **APIPI WEEKLY NOTICE**\n\n"
                f"{siswa.mention} & {siswi.mention}\n\n"
                f"Target minggu lalu: **{WEEKLY_HOURS} jam**\n"
                f"Progress: **{format_hours(seconds)}**\n"
                f"Strike: **{strike}/{MAX_STRIKE}**\n\n"
                "Pastikan target mingguan terpenuhi "
                "agar role tetap aktif."
            )
        )

    # ========================================================
    # AUTO REMOVE NOTICE
    # ========================================================

    async def send_auto_remove_notice(
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
                f"{EMOJI_APIPI} **APIPI ROLE DICABUT**\n\n"
                f"{siswa.mention} & {siswi.mention}\n\n"
                f"Target mingguan tidak terpenuhi "
                f"sebanyak **{MAX_STRIKE} kali**.\n\n"
                "Role Apipi telah dicabut dan progress "
                "dikembalikan ke awal."
            )
        )

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

        except Exception:
            pass

    # ========================================================
    # ADMIN CHECK
    # ========================================================

    def is_admin(self, interaction):

        if not interaction.guild:
            return False

        return interaction.user.guild_permissions.administrator

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

        pair = await self.get_pair_by_member(
            interaction.guild.id,
            user_id
        )

        if not pair:

            return await interaction.response.send_message(
                "Pasangan tidak ditemukan.",
                ephemeral=True
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

        now = db_datetime(utc_now())

        await db.execute(
            """
            UPDATE nanz_apipi_pairs
            SET
                status = 'tracking',
                eligible_notified = 0,
                take_siswa = 0,
                take_siswi = 0,
                remove_siswa = 0,
                remove_siswi = 0,
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
            "ADMIN_RESET_PROGRESS",
            "Administrator mereset progress Apipi."
        )

        await interaction.response.send_message(
            "Progress Apipi berhasil di-reset.",
            ephemeral=True
        )

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

        now = db_datetime(utc_now())

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

        await interaction.response.send_message(
            "Strike berhasil di-reset menjadi 0.",
            ephemeral=True
        )


# ============================================================
# REGISTER PAIR MODAL
# ============================================================

class RegisterPairModal(
    discord.ui.Modal
):

    def __init__(self, cog):

        self.cog = cog

        super().__init__(
            title="Daftarkan Pasangan Apipi"
        )

        self.partner = discord.ui.InputText(
            label="User ID / Mention Pasangan",
            placeholder="Contoh: 123456789 atau @username",
            required=True,
            max_length=30
        )

        self.add_item(
            self.partner
        )

    async def callback(
        self,
        interaction
    ):

        partner_id = parse_user_id(
            self.partner.value
        )

        if not partner_id:

            return await interaction.response.send_message(
                "User ID / mention tidak valid.",
                ephemeral=True
            )

        if partner_id == interaction.user.id:

            return await interaction.response.send_message(
                "Kamu tidak bisa memasangkan dirimu sendiri.",
                ephemeral=True
            )

        user = interaction.guild.get_member(
            interaction.user.id
        )

        partner = interaction.guild.get_member(
            partner_id
        )

        if not partner:

            return await interaction.response.send_message(
                "Pasangan tidak ditemukan di server.",
                ephemeral=True
            )

        user_is_siswa = any(
            role.id == SISWA_ROLE_ID
            for role in user.roles
        )

        user_is_siswi = any(
            role.id == SISWI_ROLE_ID
            for role in user.roles
        )

        partner_is_siswa = any(
            role.id == SISWA_ROLE_ID
            for role in partner.roles
        )

        partner_is_siswi = any(
            role.id == SISWI_ROLE_ID
            for role in partner.roles
        )

        if user_is_siswa and partner_is_siswi:

            siswa = user
            siswi = partner

        elif user_is_siswi and partner_is_siswa:

            siswa = partner
            siswi = user

        else:

            return await interaction.response.send_message(
                (
                    "Pasangan tidak valid.\n"
                    "Apipi wajib terdiri dari **1 Siswa + 1 Siswi**."
                ),
                ephemeral=True
            )

        pair, result = await self.cog.create_pair(
            interaction.guild.id,
            siswa.id,
            siswi.id,
            interaction.user.id
        )

        if result == "siswa_busy":

            return await interaction.response.send_message(
                "Siswa tersebut sudah memiliki pasangan Apipi.",
                ephemeral=True
            )

        if result == "siswi_busy":

            return await interaction.response.send_message(
                "Siswi tersebut sudah memiliki pasangan Apipi.",
                ephemeral=True
            )

        if not pair:

            return await interaction.response.send_message(
                "Gagal membuat pasangan.",
                ephemeral=True
            )

        await interaction.response.send_message(
            (
                f"{EMOJI_APIPI} Pasangan Apipi berhasil didaftarkan.\n\n"
                f"**Siswa:** {siswa.mention}\n"
                f"**Siswi:** {siswi.mention}\n\n"
                f"Selanjutnya kumpulkan **{UNLOCK_HOURS} jam** "
                "shared voice."
            ),
            ephemeral=True
        )


# ============================================================
# ADMIN TARGET MODAL
# ============================================================

class AdminTargetModal(
    discord.ui.Modal
):

    def __init__(
        self,
        cog,
        action_name
    ):

        self.cog = cog
        self.action_name = action_name

        super().__init__(
            title=action_name
        )

        self.target = discord.ui.InputText(
            label="User ID / Mention salah satu pasangan",
            placeholder="123456789",
            required=True,
            max_length=30
        )

        self.add_item(
            self.target
        )

    async def callback(
        self,
        interaction
    ):

        if not self.cog.is_admin(interaction):

            return await interaction.response.send_message(
                "Akses ditolak. Hanya Administrator.",
                ephemeral=True
            )

        user_id = parse_user_id(
            self.target.value
        )

        if not user_id:

            return await interaction.response.send_message(
                "User ID tidak valid.",
                ephemeral=True
            )

        if self.action_name == "Cek Status":

            return await self.cog.admin_status(
                interaction,
                user_id
            )

        if self.action_name == "Set Role":

            return await self.cog.admin_set_role(
                interaction,
                user_id
            )

        if self.action_name == "Cabut Role":

            return await self.cog.admin_remove_role(
                interaction,
                user_id
            )

        if self.action_name == "Reset Progress":

            return await self.cog.admin_reset_progress(
                interaction,
                user_id
            )

        if self.action_name == "Reset Strike":

            return await self.cog.admin_reset_strike(
                interaction,
                user_id
            )


# ============================================================
# MEMBER PANEL
# ============================================================

class ApipiMemberPanel(
    discord.ui.View
):

    def __init__(self, cog):

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

        await interaction.response.send_modal(
            RegisterPairModal(
                self.cog
            )
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

        await self.cog.approve_take(
            interaction
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

        await self.cog.approve_remove(
            interaction
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
                f"• Target mingguan tidak terpenuhi = 1 strike.\n"
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


# ============================================================
# MANAGEMENT PANEL
# ============================================================

class ApipiManagementPanel(
    discord.ui.View
):

    def __init__(self, cog):

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

        if not self.cog.is_admin(interaction):

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

        if not await self.check_admin(interaction):
            return

        await interaction.response.send_modal(
            AdminTargetModal(
                self.cog,
                "Cek Status"
            )
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

        if not await self.check_admin(interaction):
            return

        await interaction.response.send_modal(
            AdminTargetModal(
                self.cog,
                "Set Role"
            )
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

        if not await self.check_admin(interaction):
            return

        await interaction.response.send_modal(
            AdminTargetModal(
                self.cog,
                "Cabut Role"
            )
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

        if not await self.check_admin(interaction):
            return

        await interaction.response.send_modal(
            AdminTargetModal(
                self.cog,
                "Reset Progress"
            )
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

        if not await self.check_admin(interaction):
            return

        await interaction.response.send_modal(
            AdminTargetModal(
                self.cog,
                "Reset Strike"
            )
        )


# ============================================================
# SETUP
# ============================================================

async def setup(bot):

    await bot.add_cog(
        Apipi(bot)
    )