import re
import asyncio
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from database import db


# ============================================================
# CONFIG
# ============================================================

SISWA_ROLE_ID = 1453246082405503036
SISWI_ROLE_ID = 1453246187636396032

APIPI_ROLE_ID = 1555862680605167646

MEMBER_PANEL_CHANNEL_ID = 1555862444054814740
LOG_CHANNEL_ID = 1555862510765215765
MANAGEMENT_PANEL_CHANNEL_ID = 1555863036810494084

MINIMUM_HOURS = 20
WEEKLY_TARGET_HOURS = 5
MAX_STRIKE = 3

HEARTBEAT_SECONDS = 60
WEEKLY_CHECK_SECONDS = 1800

WIB = timezone(timedelta(hours=7))


# ============================================================
# ANIMATED CUSTOM EMOJIS
# ============================================================
#
# Pastikan emoji Discord tersebut memang bertipe ANIMATED.
# Format animated custom emoji Discord:
#
# <a:nama:ID>
#
# Button sengaja TIDAK memakai emoji sama sekali.
#

EMOJI = {
    "blue": "<a:arrow_blue:1512787254312042496>",
    "purple": "<a:arrow_purple:1512787191234035803>",
    "apipi": "<a:apipi:1512888691369050243>",
    "love": "<a:rainbow_love:1493106010389483661>",
}


# ============================================================
# TIME HELPERS
# ============================================================

def now_utc():
    return datetime.now(timezone.utc)


def now_wib():
    return datetime.now(WIB)


def to_db(dt: datetime):
    """
    MariaDB DATETIME tidak menyimpan timezone.
    Semua waktu DB disimpan sebagai UTC.
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        return dt

    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def from_db(dt):
    """
    Ambil DATETIME dari database dan anggap sebagai UTC.
    """
    if dt is None:
        return None

    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)

    return dt.replace(tzinfo=timezone.utc)


def week_start(dt=None):
    """
    Senin 00:00 WIB.
    """
    if dt is None:
        dt = now_wib()

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=WIB)
    else:
        dt = dt.astimezone(WIB)

    monday = dt - timedelta(days=dt.weekday())

    return monday.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )


def format_duration(seconds):
    seconds = max(0, int(seconds))

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    return f"{hours}j {minutes}m"


def progress_hours(seconds):
    return round(seconds / 3600, 2)


# ============================================================
# DATABASE
# ============================================================

async def create_tables():
    await db.execute("""
        CREATE TABLE IF NOT EXISTS nanz_apipi_pairs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            siswa_id BIGINT NOT NULL,
            siswi_id BIGINT NOT NULL,

            status VARCHAR(30) NOT NULL DEFAULT 'tracking',

            total_seconds BIGINT NOT NULL DEFAULT 0,

            eligible TINYINT(1) NOT NULL DEFAULT 0,

            siswa_approved TINYINT(1) NOT NULL DEFAULT 0,
            siswi_approved TINYINT(1) NOT NULL DEFAULT 0,

            siswa_remove_approved TINYINT(1) NOT NULL DEFAULT 0,
            siswi_remove_approved TINYINT(1) NOT NULL DEFAULT 0,

            role_activated_at DATETIME NULL,

            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,

            UNIQUE KEY unique_pair (siswa_id, siswi_id)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS nanz_apipi_sessions (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,

            pair_id BIGINT NOT NULL,

            started_at DATETIME NOT NULL,
            ended_at DATETIME NOT NULL,

            duration_seconds BIGINT NOT NULL DEFAULT 0,

            INDEX idx_pair (pair_id),
            INDEX idx_started (started_at),
            INDEX idx_ended (ended_at)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS nanz_apipi_live_sessions (
            pair_id BIGINT PRIMARY KEY,

            channel_id BIGINT NOT NULL,

            started_at DATETIME NOT NULL,
            last_seen_at DATETIME NOT NULL,

            INDEX idx_channel (channel_id)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS nanz_apipi_weekly (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,

            pair_id BIGINT NOT NULL,
            week_start DATETIME NOT NULL,

            seconds BIGINT NOT NULL DEFAULT 0,

            strike_added TINYINT(1) NOT NULL DEFAULT 0,

            UNIQUE KEY unique_pair_week (pair_id, week_start),
            INDEX idx_pair (pair_id)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS nanz_apipi_logs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,

            pair_id BIGINT NULL,

            action VARCHAR(50) NOT NULL,

            user_id BIGINT NULL,

            detail TEXT NULL,

            created_at DATETIME NOT NULL,

            INDEX idx_pair (pair_id),
            INDEX idx_created (created_at)
        )
    """)


# ============================================================
# COG
# ============================================================

class Apipi(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        self.initialized = False
        self._panel_lock = asyncio.Lock()

        self.heartbeat_loop.start()
        self.weekly_checker.start()

    # ========================================================
    # LIFECYCLE
    # ========================================================

    async def cog_load(self):
        await create_tables()

        self.bot.add_view(ApipiMemberPanel(self))
        self.bot.add_view(ApipiManagementPanel(self))

        self.initialized = True

        await self.reconcile_after_restart()

        await self.ensure_member_panel()
        await self.ensure_management_panel()

    def cog_unload(self):
        self.heartbeat_loop.cancel()
        self.weekly_checker.cancel()

    # ========================================================
    # DATABASE HELPERS
    # ========================================================

    async def log_action(
        self,
        action,
        pair_id=None,
        user_id=None,
        detail=None
    ):
        await db.execute("""
            INSERT INTO nanz_apipi_logs
            (
                pair_id,
                action,
                user_id,
                detail,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            pair_id,
            action,
            user_id,
            detail,
            to_db(now_utc())
        ))

    async def get_pair_by_id(self, pair_id):
        return await db.fetchone("""
            SELECT *
            FROM nanz_apipi_pairs
            WHERE id = %s
            LIMIT 1
        """, (pair_id,))

    async def get_pair_by_member(
        self,
        user_id,
        include_removed=False
    ):
        if include_removed:
            return await db.fetchone("""
                SELECT *
                FROM nanz_apipi_pairs
                WHERE siswa_id = %s
                   OR siswi_id = %s
                ORDER BY id DESC
                LIMIT 1
            """, (user_id, user_id))

        return await db.fetchone("""
            SELECT *
            FROM nanz_apipi_pairs
            WHERE
                (siswa_id = %s OR siswi_id = %s)
                AND status != 'removed'
            ORDER BY id DESC
            LIMIT 1
        """, (user_id, user_id))

    async def get_active_pairs(self):
        return await db.fetchall("""
            SELECT *
            FROM nanz_apipi_pairs
            WHERE status != 'removed'
        """)

    # ========================================================
    # PAIR HELPERS
    # ========================================================

    def is_valid_pair(self, member1, member2):
        m1_siswa = any(
            role.id == SISWA_ROLE_ID
            for role in member1.roles
        )

        m1_siswi = any(
            role.id == SISWI_ROLE_ID
            for role in member1.roles
        )

        m2_siswa = any(
            role.id == SISWA_ROLE_ID
            for role in member2.roles
        )

        m2_siswi = any(
            role.id == SISWI_ROLE_ID
            for role in member2.roles
        )

        return (
            (m1_siswa and m2_siswi)
            or
            (m1_siswi and m2_siswa)
        )

    def get_pair_members(self, pair, guild):
        siswa = guild.get_member(int(pair["siswa_id"]))
        siswi = guild.get_member(int(pair["siswi_id"]))

        return siswa, siswi

    # ========================================================
    # REGISTER PAIR
    # ========================================================

    async def register_pair(
        self,
        guild,
        user_id,
        partner_id
    ):
        member = guild.get_member(user_id)
        partner = guild.get_member(partner_id)

        if not member:
            return False, "Akun kamu tidak ditemukan."

        if not partner:
            return False, "Pasangan tidak ditemukan."

        if member.id == partner.id:
            return False, "Kamu tidak bisa mendaftarkan diri sendiri."

        existing = await self.get_pair_by_member(
            member.id,
            include_removed=False
        )

        if existing:
            return False, "Kamu sudah memiliki pasangan Apipi."

        existing_partner = await self.get_pair_by_member(
            partner.id,
            include_removed=False
        )

        if existing_partner:
            return False, "Pasangan tersebut sudah memiliki pasangan Apipi."

        if not self.is_valid_pair(member, partner):
            return False, (
                "Pasangan harus terdiri dari 1 Siswa dan 1 Siswi."
            )

        if any(role.id == SISWA_ROLE_ID for role in member.roles):
            siswa_id = member.id
            siswi_id = partner.id
        else:
            siswa_id = partner.id
            siswi_id = member.id

        current = now_utc()

        await db.execute("""
            INSERT INTO nanz_apipi_pairs
            (
                siswa_id,
                siswi_id,
                status,
                total_seconds,
                eligible,
                siswa_approved,
                siswi_approved,
                siswa_remove_approved,
                siswi_remove_approved,
                role_activated_at,
                created_at,
                updated_at
            )
            VALUES
            (
                %s,
                %s,
                'tracking',
                0,
                0,
                0,
                0,
                0,
                0,
                NULL,
                %s,
                %s
            )
        """, (
            siswa_id,
            siswi_id,
            to_db(current),
            to_db(current)
        ))

        pair = await db.fetchone("""
            SELECT *
            FROM nanz_apipi_pairs
            WHERE siswa_id = %s
              AND siswi_id = %s
            ORDER BY id DESC
            LIMIT 1
        """, (siswa_id, siswi_id))

        if pair:
            await self.log_action(
                "pair_registered",
                pair["id"],
                user_id,
                f"Pair registered: {siswa_id} + {siswi_id}"
            )

        return True, "Pasangan Apipi berhasil didaftarkan."

    # ========================================================
    # VOICE CHECK
    # ========================================================

    def same_voice_channel(self, siswa, siswi):
        if not siswa or not siswi:
            return False

        if not siswa.voice or not siswi.voice:
            return False

        if not siswa.voice.channel or not siswi.voice.channel:
            return False

        return siswa.voice.channel.id == siswi.voice.channel.id

    # ========================================================
    # LIVE SESSION
    # ========================================================

    async def start_live_session(
        self,
        pair_id,
        channel_id
    ):
        current = now_utc()

        existing = await db.fetchone("""
            SELECT *
            FROM nanz_apipi_live_sessions
            WHERE pair_id = %s
            LIMIT 1
        """, (pair_id,))

        if existing:
            return

        await db.execute("""
            INSERT INTO nanz_apipi_live_sessions
            (
                pair_id,
                channel_id,
                started_at,
                last_seen_at
            )
            VALUES (%s, %s, %s, %s)
        """, (
            pair_id,
            channel_id,
            to_db(current),
            to_db(current)
        ))

    async def heartbeat_live_session(
        self,
        pair_id,
        channel_id
    ):
        current = now_utc()

        await db.execute("""
            UPDATE nanz_apipi_live_sessions
            SET
                channel_id = %s,
                last_seen_at = %s
            WHERE pair_id = %s
        """, (
            channel_id,
            to_db(current),
            pair_id
        ))

    async def close_live_session(self, pair_id):
        live = await db.fetchone("""
            SELECT *
            FROM nanz_apipi_live_sessions
            WHERE pair_id = %s
            LIMIT 1
        """, (pair_id,))

        if not live:
            return 0

        started_at = from_db(live["started_at"])
        last_seen_at = from_db(live["last_seen_at"])

        if not started_at or not last_seen_at:
            await db.execute("""
                DELETE FROM nanz_apipi_live_sessions
                WHERE pair_id = %s
            """, (pair_id,))
            return 0

        duration = max(
            0,
            int((last_seen_at - started_at).total_seconds())
        )

        if duration > 0:
            await self.save_session(
                pair_id,
                started_at,
                last_seen_at,
                duration
            )

        await db.execute("""
            DELETE FROM nanz_apipi_live_sessions
            WHERE pair_id = %s
        """, (pair_id,))

        return duration

    # ========================================================
    # SESSION SAVE
    # ========================================================

    async def save_session(
        self,
        pair_id,
        started_at,
        ended_at,
        duration
    ):
        if duration <= 0:
            return

        await db.execute("""
            INSERT INTO nanz_apipi_sessions
            (
                pair_id,
                started_at,
                ended_at,
                duration_seconds
            )
            VALUES (%s, %s, %s, %s)
        """, (
            pair_id,
            to_db(started_at),
            to_db(ended_at),
            duration
        ))

        await db.execute("""
            UPDATE nanz_apipi_pairs
            SET
                total_seconds = total_seconds + %s,
                updated_at = %s
            WHERE id = %s
        """, (
            duration,
            to_db(now_utc()),
            pair_id
        ))

        await self.add_weekly_seconds(
            pair_id,
            started_at,
            ended_at
        )

    # ========================================================
    # WEEKLY TIME
    # ========================================================

    async def add_weekly_seconds(
        self,
        pair_id,
        started_at,
        ended_at
    ):
        """
        Membagi session berdasarkan batas minggu:
        Senin 00:00 WIB.
        """

        if ended_at <= started_at:
            return

        cursor = started_at

        while cursor < ended_at:
            cursor_wib = cursor.astimezone(WIB)

            current_week = week_start(cursor_wib)

            next_week = current_week + timedelta(days=7)

            segment_end_wib = min(
                ended_at.astimezone(WIB),
                next_week
            )

            segment_end = segment_end_wib.astimezone(timezone.utc)

            duration = int(
                (segment_end - cursor).total_seconds()
            )

            if duration > 0:
                week_db = to_db(current_week.astimezone(timezone.utc))

                await db.execute("""
                    INSERT INTO nanz_apipi_weekly
                    (
                        pair_id,
                        week_start,
                        seconds,
                        strike_added
                    )
                    VALUES (%s, %s, %s, 0)
                    ON DUPLICATE KEY UPDATE
                        seconds = seconds + VALUES(seconds)
                """, (
                    pair_id,
                    week_db,
                    duration
                ))

            cursor = segment_end

    async def get_week_seconds(
        self,
        pair_id,
        target_week
    ):
        week_utc = target_week.astimezone(timezone.utc)

        row = await db.fetchone("""
            SELECT seconds
            FROM nanz_apipi_weekly
            WHERE pair_id = %s
              AND week_start = %s
            LIMIT 1
        """, (
            pair_id,
            to_db(week_utc)
        ))

        saved = int(row["seconds"]) if row else 0

        # Tambahkan live session yang sedang berjalan,
        # tetapi hanya bagian yang berada dalam minggu tersebut.
        live = await db.fetchone("""
            SELECT *
            FROM nanz_apipi_live_sessions
            WHERE pair_id = %s
            LIMIT 1
        """, (pair_id,))

        if not live:
            return saved

        started = from_db(live["started_at"])
        current = now_utc()

        week_start_utc = target_week.astimezone(timezone.utc)
        week_end_utc = (
            target_week + timedelta(days=7)
        ).astimezone(timezone.utc)

        overlap_start = max(
            started,
            week_start_utc
        )

        overlap_end = min(
            current,
            week_end_utc
        )

        if overlap_end > overlap_start:
            live_seconds = int(
                (overlap_end - overlap_start).total_seconds()
            )
        else:
            live_seconds = 0

        return saved + live_seconds

    # ========================================================
    # ELIGIBILITY
    # ========================================================

    async def check_eligibility(
        self,
        pair_id
    ):
        pair = await self.get_pair_by_id(pair_id)

        if not pair:
            return

        if pair["status"] == "removed":
            return

        if int(pair["eligible"]):
            return

        if int(pair["total_seconds"]) < MINIMUM_HOURS * 3600:
            return

        await db.execute("""
            UPDATE nanz_apipi_pairs
            SET
                eligible = 1,
                status = 'eligible',
                updated_at = %s
            WHERE id = %s
        """, (
            to_db(now_utc()),
            pair_id
        ))

        await self.log_action(
            "eligible",
            pair_id,
            None,
            "Pair reached minimum 20 hours."
        )

        guild = self.bot.get_guild(
            pair.get("guild_id", 0)
        )

        if not guild:
            guild = self.find_guild_for_pair(pair)

        if guild:
            await self.send_eligibility_notice(
                guild,
                pair_id
            )

    def find_guild_for_pair(self, pair):
        for guild in self.bot.guilds:
            if guild.get_member(int(pair["siswa_id"])):
                if guild.get_member(int(pair["siswi_id"])):
                    return guild

        return None

    # ========================================================
    # ELIGIBILITY NOTICE
    # ========================================================

    async def send_eligibility_notice(
        self,
        guild,
        pair_id
    ):
        pair = await self.get_pair_by_id(pair_id)

        if not pair:
            return

        siswa = guild.get_member(int(pair["siswa_id"]))
        siswi = guild.get_member(int(pair["siswi_id"]))

        if not siswa or not siswi:
            return

        channel = guild.get_channel(
            MEMBER_PANEL_CHANNEL_ID
        )

        if not channel:
            return

        embed = discord.Embed(
            title=f"{EMOJI['apipi']} Apipi Siap Diambil",
            description=(
                f"{siswa.mention} dan {siswi.mention}\n\n"
                f"Pasangan kalian telah mencapai **20 jam** "
                f"voice bersama.\n\n"
                f"Untuk mendapatkan role Apipi, **keduanya "
                f"harus menekan tombol `Ambil Role`**."
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="nanZ Server • Apipi"
        )

        await channel.send(
            content=f"{siswa.mention} {siswi.mention}",
            embed=embed
        )

    # ========================================================
    # ROLE
    # ========================================================

    async def grant_apipi_role(
        self,
        guild,
        pair_id
    ):
        pair = await self.get_pair_by_id(pair_id)

        if not pair:
            return False, "Data pasangan tidak ditemukan."

        siswa = guild.get_member(int(pair["siswa_id"]))
        siswi = guild.get_member(int(pair["siswi_id"]))

        if not siswa or not siswi:
            return False, "Salah satu anggota pasangan tidak ditemukan."

        role = guild.get_role(APIPI_ROLE_ID)

        if not role:
            return False, "Role Apipi tidak ditemukan."

        try:
            if role not in siswa.roles:
                await siswa.add_roles(
                    role,
                    reason="Apipi role activation"
                )

            if role not in siswi.roles:
                await siswi.add_roles(
                    role,
                    reason="Apipi role activation"
                )

        except discord.Forbidden:
            return False, "Bot tidak memiliki izin untuk memberikan role Apipi."

        activated = now_utc()

        await db.execute("""
            UPDATE nanz_apipi_pairs
            SET
                status = 'active',
                eligible = 1,
                role_activated_at = %s,
                siswa_approved = 0,
                siswi_approved = 0,
                siswa_remove_approved = 0,
                siswi_remove_approved = 0,
                updated_at = %s
            WHERE id = %s
        """, (
            to_db(activated),
            to_db(activated),
            pair_id
        ))

        await self.log_action(
            "role_granted",
            pair_id,
            None,
            "Both members approved Apipi role."
        )

        return True, "Role Apipi berhasil diberikan."

    async def remove_apipi_role(
        self,
        guild,
        pair_id,
        reason="manual"
    ):
        pair = await self.get_pair_by_id(pair_id)

        if not pair:
            return False, "Data pasangan tidak ditemukan."

        siswa = guild.get_member(int(pair["siswa_id"]))
        siswi = guild.get_member(int(pair["siswi_id"]))

        role = guild.get_role(APIPI_ROLE_ID)

        if role:
            try:
                if siswa and role in siswa.roles:
                    await siswa.remove_roles(
                        role,
                        reason=f"Apipi role removal: {reason}"
                    )

                if siswi and role in siswi.roles:
                    await siswi.remove_roles(
                        role,
                        reason=f"Apipi role removal: {reason}"
                    )

            except discord.Forbidden:
                return False, (
                    "Bot tidak memiliki izin untuk mencabut role Apipi."
                )

        await db.execute("""
            UPDATE nanz_apipi_pairs
            SET
                status = 'tracking',
                eligible = 0,
                siswa_approved = 0,
                siswi_approved = 0,
                siswa_remove_approved = 0,
                siswi_remove_approved = 0,
                role_activated_at = NULL,
                updated_at = %s
            WHERE id = %s
        """, (
            to_db(now_utc()),
            pair_id
        ))

        await self.log_action(
            "role_removed",
            pair_id,
            None,
            reason
        )

        return True, "Role Apipi berhasil dicabut."

    # ========================================================
    # APPROVAL
    # ========================================================

    async def approve_take_role(
        self,
        pair_id,
        user_id
    ):
        pair = await self.get_pair_by_id(pair_id)

        if not pair:
            return False, "Pasangan tidak ditemukan."

        if pair["status"] != "eligible":
            return False, "Pasangan belum memenuhi syarat."

        if int(user_id) == int(pair["siswa_id"]):
            await db.execute("""
                UPDATE nanz_apipi_pairs
                SET siswa_approved = 1
                WHERE id = %s
            """, (pair_id,))

        elif int(user_id) == int(pair["siswi_id"]):
            await db.execute("""
                UPDATE nanz_apipi_pairs
                SET siswi_approved = 1
                WHERE id = %s
            """, (pair_id,))

        else:
            return False, "Kamu bukan bagian dari pasangan ini."

        pair = await self.get_pair_by_id(pair_id)

        both_approved = (
            int(pair["siswa_approved"]) == 1
            and int(pair["siswi_approved"]) == 1
        )

        if both_approved:
            return True, "BOTH_APPROVED"

        return True, "Persetujuan kamu sudah dicatat."

    async def approve_remove_role(
        self,
        pair_id,
        user_id
    ):
        pair = await self.get_pair_by_id(pair_id)

        if not pair:
            return False, "Pasangan tidak ditemukan."

        if pair["status"] != "active":
            return False, "Role Apipi pasangan ini sedang tidak aktif."

        if int(user_id) == int(pair["siswa_id"]):
            await db.execute("""
                UPDATE nanz_apipi_pairs
                SET siswa_remove_approved = 1
                WHERE id = %s
            """, (pair_id,))

        elif int(user_id) == int(pair["siswi_id"]):
            await db.execute("""
                UPDATE nanz_apipi_pairs
                SET siswi_remove_approved = 1
                WHERE id = %s
            """, (pair_id,))

        else:
            return False, "Kamu bukan bagian dari pasangan ini."

        pair = await self.get_pair_by_id(pair_id)

        both_approved = (
            int(pair["siswa_remove_approved"]) == 1
            and int(pair["siswi_remove_approved"]) == 1
        )

        if both_approved:
            return True, "BOTH_APPROVED"

        return True, "Persetujuan pencabutan kamu sudah dicatat."

    # ========================================================
    # STATUS
    # ========================================================

    async def get_status_text(
        self,
        guild,
        pair
    ):
        siswa = guild.get_member(int(pair["siswa_id"]))
        siswi = guild.get_member(int(pair["siswi_id"]))

        total = int(pair["total_seconds"])

        status = pair["status"]

        if status == "active":
            status_text = "Aktif"

        elif status == "eligible":
            status_text = "Siap Diambil"

        else:
            status_text = "Tracking"

        return (
            f"{EMOJI['purple']} **Status:** {status_text}\n"
            f"{EMOJI['blue']} **Progress:** "
            f"{progress_hours(total)} / {MINIMUM_HOURS} jam\n"
            f"{EMOJI['love']} **Pasangan:** "
            f"{siswa.mention if siswa else pair['siswa_id']} × "
            f"{siswi.mention if siswi else pair['siswi_id']}"
        )

    # ========================================================
    # PANEL MEMBER
    # ========================================================

    async def ensure_member_panel(self):
        async with self._panel_lock:
            channel = None

            for guild in self.bot.guilds:
                channel = guild.get_channel(
                    MEMBER_PANEL_CHANNEL_ID
                )

                if channel:
                    break

            if not channel:
                return

            async for message in channel.history(limit=30):
                if (
                    message.author.id == self.bot.user.id
                    and message.embeds
                ):
                    if (
                        message.embeds[0].title
                        and "Apipi" in message.embeds[0].title
                    ):
                        try:
                            await message.edit(
                                embed=self.member_panel_embed(),
                                view=ApipiMemberPanel(self)
                            )
                            return
                        except discord.HTTPException:
                            pass

            try:
                await channel.send(
                    embed=self.member_panel_embed(),
                    view=ApipiMemberPanel(self)
                )
            except discord.HTTPException:
                pass

    def member_panel_embed(self):
        return discord.Embed(
            title=f"{EMOJI['apipi']} APIPI",
            description=(
                "Sistem pasangan **Siswa × Siswi** nanZ.\n\n"
                f"{EMOJI['blue']} **20 Jam**\n"
                "Capai minimal 20 jam voice bersama untuk membuka "
                "akses pengambilan role.\n\n"
                f"{EMOJI['purple']} **Persetujuan Bersama**\n"
                "Role hanya diberikan setelah kedua pihak menyetujui.\n\n"
                f"{EMOJI['love']} **Maintenance**\n"
                "Setelah aktif, pasangan wajib mencapai 5 jam "
                "voice bersama setiap minggu.\n\n"
                "Gunakan tombol di bawah untuk mengelola pasangan."
            ),
            color=discord.Color.blurple()
        )

    # ========================================================
    # PANEL MANAGEMENT
    # ========================================================

    async def ensure_management_panel(self):
        async with self._panel_lock:
            channel = None

            for guild in self.bot.guilds:
                channel = guild.get_channel(
                    MANAGEMENT_PANEL_CHANNEL_ID
                )

                if channel:
                    break

            if not channel:
                return

            async for message in channel.history(limit=30):
                if (
                    message.author.id == self.bot.user.id
                    and message.embeds
                ):
                    if (
                        message.embeds[0].title
                        and "Management" in message.embeds[0].title
                    ):
                        try:
                            await message.edit(
                                embed=self.management_panel_embed(),
                                view=ApipiManagementPanel(self)
                            )
                            return
                        except discord.HTTPException:
                            pass

            try:
                await channel.send(
                    embed=self.management_panel_embed(),
                    view=ApipiManagementPanel(self)
                )
            except discord.HTTPException:
                pass

    def management_panel_embed(self):
        return discord.Embed(
            title=f"{EMOJI['apipi']} Apipi Management",
            description=(
                f"{EMOJI['blue']} **Cek Status**\n"
                "Melihat data pasangan dan progress.\n\n"
                f"{EMOJI['purple']} **Set Role**\n"
                "Memberikan role Apipi secara manual.\n\n"
                f"{EMOJI['love']} **Cabut Role**\n"
                "Mencabut role Apipi secara manual.\n\n"
                f"{EMOJI['blue']} **Reset Progress**\n"
                "Mengembalikan progress pasangan menjadi 0.\n\n"
                f"{EMOJI['purple']} **Reset Strike**\n"
                "Mengembalikan strike pasangan menjadi 0.\n\n"
                "Panel ini hanya dapat digunakan Administrator."
            ),
            color=discord.Color.blurple()
        )

    # ========================================================
    # RESTART RECONCILIATION
    # ========================================================

    async def reconcile_after_restart(self):
        """
        Saat bot restart:
        - ambil waktu terakhir yang benar-benar diketahui bot
        - simpan sampai last_seen_at
        - jangan menghitung downtime
        - jika pasangan masih satu VC, mulai session baru
        """

        rows = await db.fetchall("""
            SELECT *
            FROM nanz_apipi_live_sessions
        """)

        for live in rows:
            pair = await self.get_pair_by_id(
                live["pair_id"]
            )

            if not pair:
                await db.execute("""
                    DELETE FROM nanz_apipi_live_sessions
                    WHERE pair_id = %s
                """, (live["pair_id"],))
                continue

            guild = self.find_guild_for_pair(pair)

            if not guild:
                await self.close_live_session(
                    live["pair_id"]
                )
                continue

            siswa, siswi = self.get_pair_members(
                pair,
                guild
            )

            last_seen = from_db(
                live["last_seen_at"]
            )

            started = from_db(
                live["started_at"]
            )

            if last_seen and started:
                duration = max(
                    0,
                    int(
                        (last_seen - started)
                        .total_seconds()
                    )
                )

                if duration > 0:
                    await self.save_session(
                        live["pair_id"],
                        started,
                        last_seen,
                        duration
                    )

            await db.execute("""
                DELETE FROM nanz_apipi_live_sessions
                WHERE pair_id = %s
            """, (live["pair_id"],))

            if self.same_voice_channel(
                siswa,
                siswi
            ):
                await self.start_live_session(
                    live["pair_id"],
                    siswa.voice.channel.id
                )

    # ========================================================
    # HEARTBEAT
    # ========================================================

    @tasks.loop(seconds=HEARTBEAT_SECONDS)
    async def heartbeat_loop(self):
        if not self.initialized:
            return

        pairs = await self.get_active_pairs()

        for pair in pairs:
            guild = self.find_guild_for_pair(pair)

            if not guild:
                continue

            siswa, siswi = self.get_pair_members(
                pair,
                guild
            )

            together = self.same_voice_channel(
                siswa,
                siswi
            )

            live = await db.fetchone("""
                SELECT *
                FROM nanz_apipi_live_sessions
                WHERE pair_id = %s
                LIMIT 1
            """, (pair["id"],))

            if together:
                channel_id = siswa.voice.channel.id

                if not live:
                    await self.start_live_session(
                        pair["id"],
                        channel_id
                    )

                else:
                    if int(live["channel_id"]) != channel_id:
                        await self.close_live_session(
                            pair["id"]
                        )

                        await self.start_live_session(
                            pair["id"],
                            channel_id
                        )

                    else:
                        await self.heartbeat_live_session(
                            pair["id"],
                            channel_id
                        )

            else:
                if live:
                    await self.close_live_session(
                        pair["id"]
                    )

            # Update total progress from saved DB value.
            refreshed = await self.get_pair_by_id(
                pair["id"]
            )

            if refreshed:
                await self.check_eligibility(
                    pair["id"]
                )

    @heartbeat_loop.before_loop
    async def before_heartbeat(self):
        await self.bot.wait_until_ready()

    # ========================================================
    # WEEKLY CHECKER
    # ========================================================

    @tasks.loop(seconds=WEEKLY_CHECK_SECONDS)
    async def weekly_checker(self):
        if not self.initialized:
            return

        current_week = week_start(
            now_wib()
        )

        previous_week = current_week - timedelta(
            days=7
        )

        pairs = await db.fetchall("""
            SELECT *
            FROM nanz_apipi_pairs
            WHERE status = 'active'
        """)

        for pair in pairs:
            activation = pair["role_activated_at"]

            if activation:
                activation_wib = from_db(
                    activation
                ).astimezone(WIB)

                activation_week = week_start(
                    activation_wib
                )

                # Activation week tidak langsung dihukum.
                if previous_week.date() <= activation_week.date():
                    continue

            seconds = await self.get_week_seconds(
                pair["id"],
                previous_week
            )

            if seconds >= WEEKLY_TARGET_HOURS * 3600:
                continue

            weekly = await db.fetchone("""
                SELECT *
                FROM nanz_apipi_weekly
                WHERE pair_id = %s
                  AND week_start = %s
                LIMIT 1
            """, (
                pair["id"],
                to_db(
                    previous_week.astimezone(timezone.utc)
                )
            ))

            if weekly and int(weekly["strike_added"]):
                continue

            await db.execute("""
                INSERT INTO nanz_apipi_weekly
                (
                    pair_id,
                    week_start,
                    seconds,
                    strike_added
                )
                VALUES (%s, %s, %s, 1)
                ON DUPLICATE KEY UPDATE
                    strike_added = 1
            """, (
                pair["id"],
                to_db(
                    previous_week.astimezone(timezone.utc)
                ),
                seconds
            ))

            await self.add_strike(
                pair["id"],
                seconds
            )

    @weekly_checker.before_loop
    async def before_weekly_checker(self):
        await self.bot.wait_until_ready()

    # ========================================================
    # STRIKE
    # ========================================================

    async def add_strike(
        self,
        pair_id,
        weekly_seconds
    ):
        pair = await self.get_pair_by_id(
            pair_id
        )

        if not pair:
            return

        # Strike dihitung berdasarkan jumlah minggu gagal.
        existing = await db.fetchone("""
            SELECT COUNT(*) AS total
            FROM nanz_apipi_weekly
            WHERE pair_id = %s
              AND strike_added = 1
        """, (pair_id,))

        strike = int(
            existing["total"]
            if existing
            else 0
        )

        await self.log_action(
            "weekly_strike",
            pair_id,
            None,
            (
                f"Weekly time: "
                f"{format_duration(weekly_seconds)}; "
                f"strike count: {strike}"
            )
        )

        guild = self.find_guild_for_pair(
            pair
        )

        if not guild:
            return

        siswa, siswi = self.get_pair_members(
            pair,
            guild
        )

        channel = guild.get_channel(
            MEMBER_PANEL_CHANNEL_ID
        )

        if strike >= MAX_STRIKE:
            await self.remove_apipi_role(
                guild,
                pair_id,
                reason="3 weekly strikes"
            )

            if channel:
                embed = discord.Embed(
                    title=f"{EMOJI['apipi']} Apipi Dinonaktifkan",
                    description=(
                        f"{siswa.mention if siswa else pair['siswa_id']} "
                        f"{siswi.mention if siswi else pair['siswi_id']}\n\n"
                        "Role Apipi telah dicabut karena mencapai "
                        f"**{MAX_STRIKE} strike**."
                    ),
                    color=discord.Color.red()
                )

                await channel.send(
                    embed=embed
                )

            return

        if channel:
            embed = discord.Embed(
                title=f"{EMOJI['apipi']} Weekly Maintenance",
                description=(
                    f"{siswa.mention if siswa else pair['siswa_id']} "
                    f"{siswi.mention if siswi else pair['siswi_id']}\n\n"
                    f"Target minggu sebelumnya: "
                    f"**{WEEKLY_TARGET_HOURS} jam**\n"
                    f"Progress: **{format_duration(weekly_seconds)}**\n\n"
                    f"Strike saat ini: **{strike}/{MAX_STRIKE}**"
                ),
                color=discord.Color.orange()
            )

            await channel.send(
                embed=embed
            )

    # ========================================================
    # RESET PROGRESS
    # ========================================================

    async def reset_progress(
        self,
        pair_id,
        admin_id
    ):
        await db.execute("""
            UPDATE nanz_apipi_pairs
            SET
                total_seconds = 0,
                updated_at = %s
            WHERE id = %s
        """, (
            to_db(now_utc()),
            pair_id
        ))

        await db.execute("""
            DELETE FROM nanz_apipi_sessions
            WHERE pair_id = %s
        """, (pair_id,))

        await db.execute("""
            DELETE FROM nanz_apipi_weekly
            WHERE pair_id = %s
        """, (pair_id,))

        await self.log_action(
            "reset_progress",
            pair_id,
            admin_id,
            "Progress reset by administrator."
        )

    # ========================================================
    # RESET STRIKE
    # ========================================================

    async def reset_strike(
        self,
        pair_id,
        admin_id
    ):
        await db.execute("""
            UPDATE nanz_apipi_weekly
            SET strike_added = 0
            WHERE pair_id = %s
        """, (pair_id,))

        await self.log_action(
            "reset_strike",
            pair_id,
            admin_id,
            "Strike status reset by administrator."
        )

    # ========================================================
    # LOG CHANNEL
    # ========================================================

    async def send_log_embed(
        self,
        guild,
        title,
        description,
        color=discord.Color.blurple()
    ):
        channel = guild.get_channel(
            LOG_CHANNEL_ID
        )

        if not channel:
            return

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=now_utc()
        )

        try:
            await channel.send(
                embed=embed
            )
        except discord.HTTPException:
            pass


# ============================================================
# MEMBER PANEL
# ============================================================

class ApipiMemberPanel(
    discord.ui.View
):
    def __init__(self, cog):
        super().__init__(timeout=None)

        self.cog = cog

    # --------------------------------------------------------
    # DAFTAR PASANGAN
    # --------------------------------------------------------

    @discord.ui.button(
        label="Daftar Pasangan",
        style=discord.ButtonStyle.primary,
        custom_id="nanz_apipi_register"
    )
    async def register(
        self,
        button,
        interaction: discord.Interaction
    ):
        await interaction.response.send_modal(
            RegisterPairModal(self.cog)
        )

    # --------------------------------------------------------
    # AMBIL ROLE
    # --------------------------------------------------------

    @discord.ui.button(
        label="Ambil Role",
        style=discord.ButtonStyle.success,
        custom_id="nanz_apipi_take"
    )
    async def take_role(
        self,
        button,
        interaction: discord.Interaction
    ):
        pair = await self.cog.get_pair_by_member(
            interaction.user.id
        )

        if not pair:
            await interaction.response.send_message(
                f"{EMOJI['purple']} Kamu belum memiliki pasangan Apipi.",
                ephemeral=True
            )
            return

        if pair["status"] != "eligible":
            await interaction.response.send_message(
                f"{EMOJI['purple']} Pasangan kamu belum mencapai 20 jam.",
                ephemeral=True
            )
            return

        success, result = await self.cog.approve_take_role(
            pair["id"],
            interaction.user.id
        )

        if not success:
            await interaction.response.send_message(
                result,
                ephemeral=True
            )
            return

        if result == "BOTH_APPROVED":
            guild = interaction.guild

            success, message = await self.cog.grant_apipi_role(
                guild,
                pair["id"]
            )

            await interaction.response.send_message(
                f"{EMOJI['apipi']} {message}",
                ephemeral=True
            )

            if success:
                await self.cog.send_log_embed(
                    guild,
                    f"{EMOJI['apipi']} Apipi Role Aktif",
                    (
                        f"Pasangan <@{pair['siswa_id']}> × "
                        f"<@{pair['siswi_id']}>\n\n"
                        "Kedua pihak telah menyetujui pengambilan "
                        "role Apipi."
                    ),
                    discord.Color.green()
                )

        else:
            await interaction.response.send_message(
                f"{EMOJI['love']} Persetujuan kamu sudah dicatat. "
                "Menunggu pasangan menyetujui.",
                ephemeral=True
            )

    # --------------------------------------------------------
    # CABUT ROLE
    # --------------------------------------------------------

    @discord.ui.button(
        label="Cabut Role",
        style=discord.ButtonStyle.danger,
        custom_id="nanz_apipi_remove"
    )
    async def remove_role(
        self,
        button,
        interaction: discord.Interaction
    ):
        pair = await self.cog.get_pair_by_member(
            interaction.user.id
        )

        if not pair:
            await interaction.response.send_message(
                f"{EMOJI['purple']} Data pasangan tidak ditemukan.",
                ephemeral=True
            )
            return

        if pair["status"] != "active":
            await interaction.response.send_message(
                f"{EMOJI['purple']} Role Apipi pasangan ini belum aktif.",
                ephemeral=True
            )
            return

        success, result = await self.cog.approve_remove_role(
            pair["id"],
            interaction.user.id
        )

        if not success:
            await interaction.response.send_message(
                result,
                ephemeral=True
            )
            return

        if result == "BOTH_APPROVED":
            success, message = await self.cog.remove_apipi_role(
                interaction.guild,
                pair["id"],
                reason="Both members approved removal."
            )

            await interaction.response.send_message(
                f"{EMOJI['apipi']} {message}",
                ephemeral=True
            )

            if success:
                await self.cog.send_log_embed(
                    interaction.guild,
                    f"{EMOJI['apipi']} Apipi Role Dicabut",
                    (
                        f"Pasangan <@{pair['siswa_id']}> × "
                        f"<@{pair['siswi_id']}>\n\n"
                        "Kedua pihak menyetujui pencabutan role."
                    ),
                    discord.Color.red()
                )

        else:
            await interaction.response.send_message(
                f"{EMOJI['love']} Persetujuan pencabutan kamu sudah dicatat. "
                "Menunggu pasangan menyetujui.",
                ephemeral=True
            )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    @discord.ui.button(
        label="Status",
        style=discord.ButtonStyle.secondary,
        custom_id="nanz_apipi_status"
    )
    async def status(
        self,
        button,
        interaction: discord.Interaction
    ):
        pair = await self.cog.get_pair_by_member(
            interaction.user.id
        )

        if not pair:
            await interaction.response.send_message(
                f"{EMOJI['purple']} Kamu belum memiliki pasangan Apipi.",
                ephemeral=True
            )
            return

        text = await self.cog.get_status_text(
            interaction.guild,
            pair
        )

        embed = discord.Embed(
            title=f"{EMOJI['apipi']} Status Apipi",
            description=text,
            color=discord.Color.blurple()
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # --------------------------------------------------------
    # KETENTUAN
    # --------------------------------------------------------

    @discord.ui.button(
        label="Ketentuan",
        style=discord.ButtonStyle.secondary,
        custom_id="nanz_apipi_rules"
    )
    async def rules(
        self,
        button,
        interaction: discord.Interaction
    ):
        embed = discord.Embed(
            title=f"{EMOJI['apipi']} Ketentuan Apipi",
            description=(
                f"{EMOJI['blue']} **Pasangan**\n"
                "1 Siswa + 1 Siswi.\n\n"

                f"{EMOJI['purple']} **Unlock Role**\n"
                f"Minimal {MINIMUM_HOURS} jam voice bersama.\n"
                "Role tidak diberikan otomatis.\n"
                "Kedua pihak wajib menyetujui.\n\n"

                f"{EMOJI['love']} **Maintenance**\n"
                f"Minimal {WEEKLY_TARGET_HOURS} jam setiap minggu.\n"
                "AFK tetap dihitung selama keduanya berada "
                "di voice channel yang sama.\n\n"

                f"{EMOJI['blue']} **Strike**\n"
                f"Maksimal {MAX_STRIKE} strike.\n"
                "Strike ke-3 menyebabkan role dicabut.\n\n"

                f"{EMOJI['purple']} **Pencabutan**\n"
                "Role hanya dicabut melalui persetujuan kedua pihak."
            ),
            color=discord.Color.blurple()
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# ============================================================
# REGISTER MODAL
# ============================================================

class RegisterPairModal(
    discord.ui.Modal
):
    def __init__(self, cog):
        super().__init__(
            title="Daftar Pasangan Apipi"
        )

        self.cog = cog

        self.partner = discord.ui.InputText(
            label="User ID Pasangan",
            placeholder="Masukkan Discord User ID",
            required=True,
            max_length=25
        )

        self.add_item(self.partner)

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        raw = self.partner.value.strip()

        match = re.search(
            r"\d{15,25}",
            raw
        )

        if not match:
            await interaction.response.send_message(
                f"{EMOJI['purple']} User ID tidak valid.",
                ephemeral=True
            )
            return

        partner_id = int(
            match.group()
        )

        success, message = await self.cog.register_pair(
            interaction.guild,
            interaction.user.id,
            partner_id
        )

        await interaction.response.send_message(
            f"{EMOJI['apipi']} {message}",
            ephemeral=True
        )


# ============================================================
# MANAGEMENT PANEL
# ============================================================

class ApipiManagementPanel(
    discord.ui.View
):
    def __init__(self, cog):
        super().__init__(timeout=None)

        self.cog = cog

    # --------------------------------------------------------
    # ADMIN CHECK
    # --------------------------------------------------------

    async def admin_check(
        self,
        interaction
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "Kamu tidak memiliki akses ke panel management.",
                ephemeral=True
            )
            return False

        return True

    # --------------------------------------------------------
    # CEK STATUS
    # --------------------------------------------------------

    @discord.ui.button(
        label="Cek Status",
        style=discord.ButtonStyle.secondary,
        custom_id="nanz_apipi_admin_status"
    )
    async def check_status(
        self,
        button,
        interaction
    ):
        if not await self.admin_check(interaction):
            return

        await interaction.response.send_modal(
            AdminTargetModal(
                self.cog,
                action="status"
            )
        )

    # --------------------------------------------------------
    # SET ROLE
    # --------------------------------------------------------

    @discord.ui.button(
        label="Set Role",
        style=discord.ButtonStyle.success,
        custom_id="nanz_apipi_admin_set"
    )
    async def set_role(
        self,
        button,
        interaction
    ):
        if not await self.admin_check(interaction):
            return

        await interaction.response.send_modal(
            AdminTargetModal(
                self.cog,
                action="set"
            )
        )

    # --------------------------------------------------------
    # CABUT ROLE
    # --------------------------------------------------------

    @discord.ui.button(
        label="Cabut Role",
        style=discord.ButtonStyle.danger,
        custom_id="nanz_apipi_admin_remove"
    )
    async def remove_role(
        self,
        button,
        interaction
    ):
        if not await self.admin_check(interaction):
            return

        await interaction.response.send_modal(
            AdminTargetModal(
                self.cog,
                action="remove"
            )
        )

    # --------------------------------------------------------
    # RESET PROGRESS
    # --------------------------------------------------------

    @discord.ui.button(
        label="Reset Progress",
        style=discord.ButtonStyle.primary,
        custom_id="nanz_apipi_admin_reset_progress"
    )
    async def reset_progress(
        self,
        button,
        interaction
    ):
        if not await self.admin_check(interaction):
            return

        await interaction.response.send_modal(
            AdminTargetModal(
                self.cog,
                action="reset_progress"
            )
        )

    # --------------------------------------------------------
    # RESET STRIKE
    # --------------------------------------------------------

    @discord.ui.button(
        label="Reset Strike",
        style=discord.ButtonStyle.secondary,
        custom_id="nanz_apipi_admin_reset_strike"
    )
    async def reset_strike(
        self,
        button,
        interaction
    ):
        if not await self.admin_check(interaction):
            return

        await interaction.response.send_modal(
            AdminTargetModal(
                self.cog,
                action="reset_strike"
            )
        )


# ============================================================
# ADMIN MODAL
# ============================================================

class AdminTargetModal(
    discord.ui.Modal
):
    def __init__(
        self,
        cog,
        action
    ):
        titles = {
            "status": "Cek Status Apipi",
            "set": "Set Role Apipi",
            "remove": "Cabut Role Apipi",
            "reset_progress": "Reset Progress",
            "reset_strike": "Reset Strike"
        }

        super().__init__(
            title=titles.get(
                action,
                "Apipi Management"
            )
        )

        self.cog = cog
        self.action = action

        self.user_id = discord.ui.InputText(
            label="User ID",
            placeholder="Masukkan User ID salah satu pasangan",
            required=True,
            max_length=25
        )

        self.add_item(
            self.user_id
        )

    async def callback(
        self,
        interaction
    ):
        raw = self.user_id.value.strip()

        match = re.search(
            r"\d{15,25}",
            raw
        )

        if not match:
            await interaction.response.send_message(
                f"{EMOJI['purple']} User ID tidak valid.",
                ephemeral=True
            )
            return

        user_id = int(
            match.group()
        )

        pair = await self.cog.get_pair_by_member(
            user_id,
            include_removed=True
        )

        if not pair:
            await interaction.response.send_message(
                f"{EMOJI['purple']} Data pasangan tidak ditemukan.",
                ephemeral=True
            )
            return

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        if self.action == "status":
            text = await self.cog.get_status_text(
                interaction.guild,
                pair
            )

            weekly = await self.cog.get_week_seconds(
                pair["id"],
                week_start(now_wib())
            )

            embed = discord.Embed(
                title=f"{EMOJI['apipi']} Apipi Management",
                description=(
                    f"{text}\n\n"
                    f"{EMOJI['blue']} **Minggu ini:** "
                    f"{format_duration(weekly)}\n"
                    f"{EMOJI['purple']} **Siswa approve:** "
                    f"{'Ya' if pair['siswa_approved'] else 'Belum'}\n"
                    f"{EMOJI['purple']} **Siswi approve:** "
                    f"{'Ya' if pair['siswi_approved'] else 'Belum'}"
                ),
                color=discord.Color.blurple()
            )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )
            return

        # ----------------------------------------------------
        # SET ROLE
        # ----------------------------------------------------

        if self.action == "set":
            success, message = await self.cog.grant_apipi_role(
                interaction.guild,
                pair["id"]
            )

            await interaction.response.send_message(
                f"{EMOJI['apipi']} {message}",
                ephemeral=True
            )

            if success:
                await self.cog.log_action(
                    "admin_set_role",
                    pair["id"],
                    interaction.user.id,
                    "Administrator manually set Apipi role."
                )

            return

        # ----------------------------------------------------
        # REMOVE ROLE
        # ----------------------------------------------------

        if self.action == "remove":
            success, message = await self.cog.remove_apipi_role(
                interaction.guild,
                pair["id"],
                reason=(
                    f"Administrator {interaction.user.id}"
                )
            )

            await interaction.response.send_message(
                f"{EMOJI['apipi']} {message}",
                ephemeral=True
            )

            return

        # ----------------------------------------------------
        # RESET PROGRESS
        # ----------------------------------------------------

        if self.action == "reset_progress":
            await self.cog.reset_progress(
                pair["id"],
                interaction.user.id
            )

            await interaction.response.send_message(
                f"{EMOJI['blue']} Progress pasangan berhasil di-reset.",
                ephemeral=True
            )

            return

        # ----------------------------------------------------
        # RESET STRIKE
        # ----------------------------------------------------

        if self.action == "reset_strike":
            await self.cog.reset_strike(
                pair["id"],
                interaction.user.id
            )

            await interaction.response.send_message(
                f"{EMOJI['purple']} Strike pasangan berhasil di-reset.",
                ephemeral=True
            )

            return


# ============================================================
# SETUP
# ============================================================

async def setup(bot):
    await bot.add_cog(
        Apipi(bot)
    )