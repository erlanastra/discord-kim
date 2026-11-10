import os
import sqlite3
import asyncio

from datetime import datetime, timedelta, timezone

from discord.ext import commands


# ==========================================================
# CONFIGURATION
# ==========================================================

WIB = timezone(timedelta(hours=7))

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DB_PATH = os.path.join(
    PROJECT_ROOT,
    "ml_activity.db"
)

SNAPSHOT_HOUR = 0
SNAPSHOT_MINUTE = 15

RETRY_INTERVAL = 300
MEMBER_YIELD_INTERVAL = 100


def now_wib():
    return datetime.now(WIB)


def to_iso(value):
    if value is None:
        return None

    return value.astimezone(WIB).isoformat()


def parse_datetime(value):
    if not value:
        return None

    try:
        result = datetime.fromisoformat(value)

        if result.tzinfo is None:
            return result.replace(tzinfo=WIB)

        return result.astimezone(WIB)

    except (TypeError, ValueError):
        return None


# ==========================================================
# COLLECTOR
# ==========================================================

class MLActivityCollector(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.db = sqlite3.connect(
            DB_PATH,
            timeout=30
        )

        self.db.row_factory = sqlite3.Row

        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")

        self.task = None
        self._lock = asyncio.Lock()

        self.init_database()

    # ======================================================
    # DATABASE
    # ======================================================

    def init_database(self):

        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS collector_meta (
                meta_key TEXT PRIMARY KEY,
                meta_value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS members (
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                joined_at TEXT,
                left_at TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,

                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS membership_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_activity (
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                activity_date TEXT NOT NULL,

                chat_count INTEGER NOT NULL DEFAULT 0,
                voice_seconds INTEGER NOT NULL DEFAULT 0,

                voice_available INTEGER NOT NULL DEFAULT 1,
                captured_at TEXT NOT NULL,

                PRIMARY KEY (
                    guild_id,
                    user_id,
                    activity_date
                )
            );

            CREATE TABLE IF NOT EXISTS daily_snapshots (
                guild_id TEXT NOT NULL,
                activity_date TEXT NOT NULL,
                snapshot_at TEXT NOT NULL,
                member_count INTEGER NOT NULL,
                roster_verified INTEGER NOT NULL,

                PRIMARY KEY (guild_id, activity_date)
            );
        """)

        # Hari pemasangan tidak dianggap sebagai
        # satu hari pengamatan penuh.
        self.db.execute("""
            INSERT OR IGNORE INTO collector_meta
            (meta_key, meta_value)
            VALUES (?, ?)
        """, (
            "first_full_day",
            (now_wib().date() + timedelta(days=1)).isoformat()
        ))

        self.db.commit()

    def get_meta(self, key):

        row = self.db.execute("""
            SELECT meta_value
            FROM collector_meta
            WHERE meta_key = ?
        """, (key,)).fetchone()

        return row["meta_value"] if row else None

    def set_meta(self, key, value):

        self.db.execute("""
            INSERT INTO collector_meta
            (meta_key, meta_value)
            VALUES (?, ?)
            ON CONFLICT(meta_key)
            DO UPDATE SET meta_value = excluded.meta_value
        """, (key, str(value)))

        self.db.commit()

    def snapshot_exists(self, guild_id, activity_date):

        row = self.db.execute("""
            SELECT 1
            FROM daily_snapshots
            WHERE guild_id = ?
              AND activity_date = ?
        """, (str(guild_id), activity_date)).fetchone()

        return row is not None

    # ======================================================
    # MEMBER REGISTRY
    # ======================================================

    def save_member(self, member, event_type=None):

        timestamp = to_iso(now_wib())
        joined_at = to_iso(member.joined_at)

        guild_id = str(member.guild.id)
        user_id = str(member.id)

        self.db.execute("""
            INSERT INTO members (
                guild_id,
                user_id,
                joined_at,
                left_at,
                first_seen_at,
                last_seen_at
            )
            VALUES (?, ?, ?, NULL, ?, ?)

            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET
                joined_at = excluded.joined_at,
                left_at = NULL,
                last_seen_at = excluded.last_seen_at
        """, (
            guild_id,
            user_id,
            joined_at,
            timestamp,
            timestamp
        ))

        if event_type:

            self.db.execute("""
                INSERT INTO membership_events (
                    guild_id,
                    user_id,
                    event_type,
                    event_at
                )
                VALUES (?, ?, ?, ?)
            """, (
                guild_id,
                user_id,
                event_type,
                timestamp
            ))

        self.db.commit()

    async def sync_members(self, guild):

        current_ids = set()
        count = 0

        async for member in guild.fetch_members(limit=None):

            if member.bot:
                continue

            self.save_member(member)

            current_ids.add(str(member.id))
            count += 1

            if count % MEMBER_YIELD_INTERVAL == 0:
                await asyncio.sleep(0)

        return current_ids

    @commands.Cog.listener()
    async def on_member_join(self, member):

        if member.bot:
            return

        self.save_member(
            member,
            event_type="join"
        )

        print(
            "[ML Collector] Member join tercatat:",
            member.id
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member):

        if member.bot:
            return

        timestamp = to_iso(now_wib())

        self.db.execute("""
            UPDATE members
            SET left_at = ?, last_seen_at = ?
            WHERE guild_id = ?
              AND user_id = ?
        """, (
            timestamp,
            timestamp,
            str(member.guild.id),
            str(member.id)
        ))

        self.db.execute("""
            INSERT INTO membership_events (
                guild_id,
                user_id,
                event_type,
                event_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            str(member.guild.id),
            str(member.id),
            "leave",
            timestamp
        ))

        self.db.commit()

        print(
            "[ML Collector] Member leave tercatat:",
            member.id
        )

    # ======================================================
    # DAILY SNAPSHOT
    # ======================================================

    async def create_daily_snapshot(self, guild, activity_date):

        async with self._lock:

            top_stats = self.bot.get_cog("TopStats")

            if top_stats is None:
                print(
                    "[ML Collector] TopStats belum tersedia."
                )
                return False

            guild_id = str(guild.id)

            if self.snapshot_exists(guild_id, activity_date):
                return True

            # Ambil seluruh anggota terbaru.
            try:
                current_ids = await self.sync_members(guild)

            except Exception as exc:
                print(
                    "[ML Collector] Gagal mengambil anggota:",
                    repr(exc)
                )
                return False

            # Pastikan registry anggota cocok dengan
            # anggota yang benar-benar berada di server.
            rows = self.db.execute("""
                SELECT user_id
                FROM members
                WHERE guild_id = ?
                  AND left_at IS NULL
            """, (guild_id,)).fetchall()

            registered_ids = {
                row["user_id"] for row in rows
            }

            if registered_ids != current_ids:

                print(
                    "[ML Collector] Snapshot ditunda: "
                    "riwayat keanggotaan belum konsisten."
                )

                return False

            # Ambil data dari objek TopStats di memori.
            guild_data = top_stats.data.get(
                "guilds", {}
            ).get(guild_id, {})

            days = guild_data.get("days", {})

            day_data = days.get(activity_date)

            # Jika tidak ada catatan tanggal tersebut,
            # kita tidak boleh langsung menganggap nol.
            if not isinstance(day_data, dict):

                print(
                    "[ML Collector] Data TopStats tidak tersedia:",
                    activity_date
                )

                return False

            chat_data = day_data.get("chat", {})
            voice_data = day_data.get("voice_seconds", {})

            if not isinstance(chat_data, dict):
                return False

            if not isinstance(voice_data, dict):
                return False

            target_end = datetime.combine(
                datetime.fromisoformat(activity_date).date(),
                datetime.max.time(),
                tzinfo=WIB
            )

            members = self.db.execute("""
                SELECT user_id, joined_at, left_at
                FROM members
                WHERE guild_id = ?
            """, (guild_id,)).fetchall()

            captured_at = to_iso(now_wib())
            records = []

            for member in members:

                joined_at = parse_datetime(
                    member["joined_at"]
                )

                left_at = parse_datetime(
                    member["left_at"]
                )

                if joined_at is None:
                    continue

                if joined_at > target_end:
                    continue

                if left_at is not None and left_at <= target_end:
                    continue

                user_id = member["user_id"]

                chat_count = int(
                    chat_data.get(user_id, 0)
                )

                voice_seconds = int(
                    voice_data.get(user_id, 0)
                )

                if chat_count < 0 or voice_seconds < 0:
                    continue

                records.append((
                    guild_id,
                    user_id,
                    activity_date,
                    chat_count,
                    voice_seconds,
                    1,
                    captured_at
                ))

            try:

                with self.db:

                    self.db.executemany("""
                        INSERT OR REPLACE INTO daily_activity (
                            guild_id,
                            user_id,
                            activity_date,
                            chat_count,
                            voice_seconds,
                            voice_available,
                            captured_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, records)

                    self.db.execute("""
                        INSERT OR REPLACE INTO daily_snapshots (
                            guild_id,
                            activity_date,
                            snapshot_at,
                            member_count,
                            roster_verified
                        )
                        VALUES (?, ?, ?, ?, 1)
                    """, (
                        guild_id,
                        activity_date,
                        captured_at,
                        len(records)
                    ))

                print(
                    "[ML Collector] Snapshot berhasil:",
                    activity_date,
                    "| Anggota:",
                    len(records)
                )

                return True

            except sqlite3.Error as exc:

                print(
                    "[ML Collector] Kesalahan database:",
                    repr(exc)
                )

                return False

    # ======================================================
    # BACKGROUND WORKER
    # ======================================================

    async def worker(self):

        await self.bot.wait_until_ready()

        print("[ML Collector] Background worker aktif.")

        for guild in self.bot.guilds:

            try:
                await self.sync_members(guild)

            except Exception as exc:
                print(
                    "[ML Collector] Sinkronisasi awal gagal:",
                    repr(exc)
                )

        last_attempt_date = None

        while not self.bot.is_closed():

            try:

                current = now_wib()

                if (
                    current.hour > SNAPSHOT_HOUR
                    or (
                        current.hour == SNAPSHOT_HOUR
                        and current.minute >= SNAPSHOT_MINUTE
                    )
                ):

                    activity_date = (
                        current.date() - timedelta(days=1)
                    ).isoformat()

                    first_full_day = self.get_meta(
                        "first_full_day"
                    )

                    if (
                        first_full_day
                        and activity_date >= first_full_day
                        and last_attempt_date != activity_date
                    ):

                        for guild in self.bot.guilds:

                            success = await self.create_daily_snapshot(
                                guild,
                                activity_date
                            )

                            if not success:
                                last_attempt_date = None
                                break

                        else:
                            last_attempt_date = activity_date

            except asyncio.CancelledError:
                raise

            except Exception as exc:

                print(
                    "[ML Collector] Worker error:",
                    repr(exc)
                )

            await asyncio.sleep(RETRY_INTERVAL)

    # ======================================================
    # LIFECYCLE
    # ======================================================

    async def cog_load(self):

        self.task = asyncio.create_task(
            self.worker()
        )

        print(
            "[ML Collector] Cog berhasil dimuat."
        )

    def cog_unload(self):

        if self.task and not self.task.done():
            self.task.cancel()

        try:
            self.db.close()
        except sqlite3.Error:
            pass


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        MLActivityCollector(bot)
    )

    print(
        "[ML Collector] Extension berhasil didaftarkan."
    )