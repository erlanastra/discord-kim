
# cogs/topstats.py
# NANZ TOP STATISTICS - UPDATED
# Python 3.8+ | discord.py 2.x

# Commands:
# !topstat [all|YYYY-MM|YYYY-MM-DD]
# !toprole @Role [all|YYYY-MM|YYYY-MM-DD]
# !cekuser [@Member] [all|YYYY-MM|YYYY-MM-DD]
# !staffstats @Role [all|YYYY-MM|YYYY-MM-DD]

import asyncio
import json
import os
import tempfile

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

import discord
from discord.ext import commands, tasks


# ============================================================
# CONFIGURATION
# ============================================================

WIB = timezone(timedelta(hours=7))

CASIS_ROLE_ID = 1499049884781907998

TOP_LIMIT = 10

SAVE_INTERVAL = 30
VOICE_CHECKPOINT_INTERVAL = 60

FETCH_CONCURRENCY = 5

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DB_FILE = os.path.join(
    PROJECT_ROOT,
    "top_stats.json"
)


# ============================================================
# TIME HELPERS
# ============================================================

def now_wib():
    return datetime.now(WIB)


def iso_now():
    return now_wib().isoformat()


def parse_iso(value):
    try:
        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            return dt.replace(tzinfo=WIB)

        return dt.astimezone(WIB)

    except (TypeError, ValueError):
        return None


def date_key(dt):
    return dt.astimezone(WIB).strftime("%Y-%m-%d")


def valid_period(period):
    if not period or period.lower() in (
        "all",
        "semua",
        "total"
    ):
        return "all", None

    try:
        if len(period) == 7:
            datetime.strptime(period, "%Y-%m")
            return "month", period

        if len(period) == 10:
            datetime.strptime(period, "%Y-%m-%d")
            return "day", period

    except ValueError:
        pass

    raise ValueError(
        "Format periode salah. Gunakan "
        "`all`, `YYYY-MM`, atau `YYYY-MM-DD`."
    )


def period_matches(day, period_type, period_key):
    if period_type == "all":
        return True

    if period_type == "month":
        return day.startswith(period_key or "")

    return day == period_key


def format_duration(seconds):
    seconds = max(0, int(seconds))

    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60

    if days:
        return f"{days} hari {hours} jam"

    if hours:
        return f"{hours} jam {minutes} menit"

    return f"{minutes} menit"


def make_guild_data():
    return {
        "days": {},
        "casis": {},
        "casis_initialized": False,
        "casis_baseline_at": None
    }


# ============================================================
# TOP STATS COG
# ============================================================

class TopStats(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.data = {
            "version": 4,
            "guilds": {}
        }

        self.dirty = False

        self._save_lock = asyncio.Lock()

        self._active_voice: Dict[
            Tuple[int, int], dict
        ] = {}

        # Cache anggota hasil sinkronisasi.
        self._members_by_guild = {}

        # Penanda sinkronisasi awal.
        self._sync_complete = asyncio.Event()

        self._ready_task = None

        self.load_data()

    # ========================================================
    # DATABASE
    # ========================================================

    def load_data(self):

        if not os.path.exists(DB_FILE):

            self.data = {
                "version": 4,
                "guilds": {}
            }

            return

        try:

            with open(
                DB_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                raw = json.load(file)

        except (json.JSONDecodeError, OSError) as exc:

            raise RuntimeError(
                f"Gagal membaca {DB_FILE}. "
                f"File tidak akan ditimpa otomatis. "
                f"Detail: {exc}"
            )

        if (
            isinstance(raw, dict)
            and isinstance(raw.get("guilds"), dict)
        ):

            self.data = raw

            self.data.setdefault("version", 4)
            self.data.setdefault("guilds", {})

        else:

            migrated = {
                "version": 4,
                "guilds": {}
            }

            if isinstance(raw, dict):

                for guild_id, old_days in raw.items():

                    if not isinstance(old_days, dict):
                        continue

                    guild_data = make_guild_data()

                    for day, values in old_days.items():

                        if not isinstance(values, dict):
                            continue

                        chat = values.get("chat", {})
                        voice = values.get(
                            "voice_seconds",
                            {}
                        )

                        guild_data["days"][day] = {
                            "chat": (
                                chat
                                if isinstance(chat, dict)
                                else {}
                            ),
                            "voice_seconds": (
                                voice
                                if isinstance(voice, dict)
                                else {}
                            )
                        }

                    migrated["guilds"][str(guild_id)] = (
                        guild_data
                    )

            self.data = migrated
            self.dirty = True

        for gd in self.data["guilds"].values():

            gd.setdefault("days", {})
            gd.setdefault("casis", {})
            gd.setdefault("casis_initialized", False)
            gd.setdefault("casis_baseline_at", None)

    def guild_data(self, guild_id):

        key = str(guild_id)

        if key not in self.data["guilds"]:

            self.data["guilds"][key] = make_guild_data()

            self.mark_dirty()

        gd = self.data["guilds"][key]

        gd.setdefault("days", {})
        gd.setdefault("casis", {})
        gd.setdefault("casis_initialized", False)
        gd.setdefault("casis_baseline_at", None)

        return gd

    def mark_dirty(self):
        self.dirty = True

    async def save_data(self, force=False):

        if not self.dirty and not force:
            return

        async with self._save_lock:

            if not self.dirty and not force:
                return

            directory = os.path.dirname(DB_FILE)

            os.makedirs(directory, exist_ok=True)

            fd, temp_path = tempfile.mkstemp(
                prefix="top_stats_",
                suffix=".tmp",
                dir=directory
            )

            try:

                with os.fdopen(
                    fd,
                    "w",
                    encoding="utf-8"
                ) as file:

                    json.dump(
                        self.data,
                        file,
                        ensure_ascii=False,
                        indent=2
                    )

                    file.flush()
                    os.fsync(file.fileno())

                os.replace(temp_path, DB_FILE)

                self.dirty = False

            finally:

                if os.path.exists(temp_path):

                    try:
                        os.remove(temp_path)

                    except OSError:
                        pass

    # ========================================================
    # MEMBER CACHE / SYNCHRONIZATION
    # ========================================================

    def remember_member(self, member):

        if member.bot:
            return

        guild_id = member.guild.id

        if guild_id not in self._members_by_guild:
            self._members_by_guild[guild_id] = {}

        self._members_by_guild[guild_id][member.id] = member

    def forget_member(self, member):

        guild_cache = self._members_by_guild.get(
            member.guild.id,
            {}
        )

        guild_cache.pop(member.id, None)

    def get_all_members(self, guild):

        cached = self._members_by_guild.get(
            guild.id,
            {}
        )

        result = dict(cached)

        for member in guild.members:

            if not member.bot:
                result[member.id] = member

        return list(result.values())

    async def synchronize_members(self, guild):

        """
        Memuat anggota server ke cache.

        Menggunakan guild.chunk terlebih dahulu.
        Jika gagal, mencoba fetch_members.
        """

        members = {}

        try:

            chunked_members = await guild.chunk(
                cache=True
            )

            for member in chunked_members:

                if not member.bot:
                    members[member.id] = member

            print(
                f"[TopStats] Chunk berhasil: "
                f"{guild.name} | "
                f"{len(members)} anggota"
            )

        except discord.Forbidden as exc:

            print(
                f"[TopStats] Chunk forbidden "
                f"{guild.name}: {exc}"
            )

        except discord.HTTPException as exc:

            print(
                f"[TopStats] Chunk gagal "
                f"{guild.name}: {exc}"
            )

        # Fallback apabila chunk tidak berhasil.
        if not members:

            try:

                async for member in guild.fetch_members(
                    limit=None
                ):

                    if not member.bot:
                        members[member.id] = member

                print(
                    f"[TopStats] Fetch fallback berhasil: "
                    f"{guild.name} | "
                    f"{len(members)} anggota"
                )

            except discord.Forbidden as exc:

                print(
                    f"[TopStats] Fetch forbidden "
                    f"{guild.name}: {exc}"
                )

            except discord.HTTPException as exc:

                print(
                    f"[TopStats] Fetch gagal "
                    f"{guild.name}: {exc}"
                )

        self._members_by_guild[guild.id] = members

        return members

    async def fetch_voice_member(
        self,
        guild,
        user_id,
        semaphore
    ):

        member = guild.get_member(user_id)

        if member is not None:
            return member

        async with semaphore:

            try:

                member = await guild.fetch_member(
                    user_id
                )

                self.remember_member(member)

                return member

            except discord.NotFound:
                return None

            except discord.Forbidden as exc:

                print(
                    f"[TopStats] Tidak bisa mengambil "
                    f"anggota {user_id}: {exc}"
                )

                return None

            except discord.HTTPException as exc:

                print(
                    f"[TopStats] HTTP error anggota "
                    f"{user_id}: {exc}"
                )

                return None

    async def reconcile_voice_sessions(self):

        """
        Sinkronisasi awal setelah bot siap.

        Bot downtime tidak dihitung.
        Semua anggota yang masih berada di VC
        dimulai dari waktu sinkronisasi.
        """

        await self.bot.wait_until_ready()

        baseline = iso_now()

        for guild in self.bot.guilds:

            print(
                f"[TopStats] Sinkronisasi server: "
                f"{guild.name}"
            )

            gd = self.guild_data(guild.id)

            # 1. Sinkronisasi seluruh anggota.
            members = await self.synchronize_members(
                guild
            )

            # 2. Baseline Casis untuk anggota yang
            # sudah memiliki role saat instalasi.
            if not gd.get("casis_initialized", False):

                casis_count = 0

                for member in members.values():

                    if member.get_role(CASIS_ROLE_ID):

                        self.ensure_casis_user(
                            gd,
                            member.id,
                            baseline
                        )

                        casis_count += 1

                gd["casis_initialized"] = True

                gd["casis_baseline_at"] = baseline

                self.mark_dirty()

                print(
                    f"[TopStats] Baseline Casis: "
                    f"{casis_count} anggota"
                )

            # 3. Ambil seluruh voice state.
            voice_snapshot = list(
                guild.voice_states.items()
            )

            semaphore = asyncio.Semaphore(
                FETCH_CONCURRENCY
            )

            # 4. Cari semua anggota yang sedang VC.
            tasks_list = []

            for user_id, voice_state in voice_snapshot:

                if voice_state.channel is None:
                    continue

                tasks_list.append(
                    self.fetch_voice_member(
                        guild,
                        int(user_id),
                        semaphore
                    )
                )

            results = await asyncio.gather(
                *tasks_list,
                return_exceptions=True
            )

            # 5. Mulai sesi voice.
            started = 0
            skipped = 0

            index = 0

            for user_id, voice_state in voice_snapshot:

                if voice_state.channel is None:
                    continue

                member = results[index]
                index += 1

                if isinstance(member, BaseException):
                    skipped += 1
                    continue

                if member is None or member.bot:
                    skipped += 1
                    continue

                # Pastikan masih terhubung.
                current_state = guild.voice_states.get(
                    int(user_id)
                )

                if (
                    current_state is None
                    or current_state.channel is None
                ):
                    skipped += 1
                    continue

                self.remember_member(member)

                self.start_voice_session(member)

                started += 1

            print(
                f"[TopStats] Voice sync selesai: "
                f"{guild.name} | "
                f"Berhasil: {started} | "
                f"Dilewati: {skipped}"
            )

        await self.save_data(force=True)

        self._sync_complete.set()

        print(
            "[TopStats] SELURUH SINKRONISASI SELESAI."
        )

    async def wait_for_sync(self):

        if not self._sync_complete.is_set():

            await self._sync_complete.wait()

    # ========================================================
    # DAILY DATA
    # ========================================================

    def ensure_day(self, gd, day):

        if day not in gd["days"]:

            gd["days"][day] = {
                "chat": {},
                "voice_seconds": {}
            }

        entry = gd["days"][day]

        entry.setdefault("chat", {})
        entry.setdefault("voice_seconds", {})

        return entry

    def ensure_casis_user(
        self,
        gd,
        user_id,
        start=None
    ):

        key = str(user_id)

        if key not in gd["casis"]:

            gd["casis"][key] = {
                "started_at": start or iso_now(),
                "chat": {},
                "voice_seconds": {}
            }

        else:

            gd["casis"][key].setdefault("chat", {})
            gd["casis"][key].setdefault(
                "voice_seconds",
                {}
            )

        return gd["casis"][key]

    # ========================================================
    # CHAT TRACKING
    # ========================================================

    def increment_chat(self, guild, member):

        if member.bot:
            return

        self.remember_member(member)

        gd = self.guild_data(guild.id)

        today = date_key(now_wib())

        entry = self.ensure_day(
            gd,
            today
        )

        uid = str(member.id)

        entry["chat"][uid] = (
            int(entry["chat"].get(uid, 0)) + 1
        )

        if member.get_role(CASIS_ROLE_ID):

            casis = self.ensure_casis_user(
                gd,
                member.id
            )

            casis["chat"][today] = (
                int(casis["chat"].get(today, 0)) + 1
            )

        self.mark_dirty()

    # ========================================================
    # VOICE TRACKING
    # ========================================================

    def split_seconds(self, start, end):

        cursor = start.astimezone(WIB)
        end = end.astimezone(WIB)

        while cursor < end:

            next_midnight = datetime.combine(
                cursor.date() + timedelta(days=1),
                datetime.min.time(),
                tzinfo=WIB
            )

            segment_end = min(
                end,
                next_midnight
            )

            seconds = int(
                (segment_end - cursor).total_seconds()
            )

            if seconds > 0:

                yield date_key(cursor), seconds

            cursor = segment_end

    def start_voice_session(self, member):

        key = (
            member.guild.id,
            member.id
        )

        if key in self._active_voice:
            return

        self._active_voice[key] = {
            "last_checkpoint": now_wib(),
            "casis_active": (
                member.get_role(CASIS_ROLE_ID) is not None
            )
        }

        self.remember_member(member)

    def checkpoint_voice_session(
        self,
        guild_id,
        user_id,
        at=None
    ):

        key = (
            guild_id,
            user_id
        )

        session = self._active_voice.get(key)

        if not session:
            return

        current = (
            at or now_wib()
        ).astimezone(WIB)

        last = session["last_checkpoint"]

        if current <= last:
            return

        gd = self.guild_data(guild_id)

        for day, seconds in self.split_seconds(
            last,
            current
        ):

            entry = self.ensure_day(
                gd,
                day
            )

            uid = str(user_id)

            entry["voice_seconds"][uid] = (
                int(
                    entry["voice_seconds"].get(uid, 0)
                ) + seconds
            )

            if session.get("casis_active"):

                casis = self.ensure_casis_user(
                    gd,
                    user_id
                )

                casis["voice_seconds"][day] = (
                    int(
                        casis["voice_seconds"].get(day, 0)
                    ) + seconds
                )

        session["last_checkpoint"] = current

        self.mark_dirty()

    async def checkpoint_all_voice(self):

        current = now_wib()

        for guild_id, user_id in list(
            self._active_voice.keys()
        ):

            self.checkpoint_voice_session(
                guild_id,
                user_id,
                current
            )

        await self.save_data()

    # ========================================================
    # STATISTICS AGGREGATION
    # ========================================================

    def aggregate_general(
        self,
        guild,
        metric,
        period
    ):

        period_type, period_key = valid_period(
            period
        )

        totals = defaultdict(int)

        gd = self.guild_data(guild.id)

        for day, values in gd["days"].items():

            if not period_matches(
                day,
                period_type,
                period_key
            ):
                continue

            for uid, amount in values.get(
                metric,
                {}
            ).items():

                totals[int(uid)] += int(amount)

        # Tambahkan voice yang belum checkpoint.
        if metric == "voice_seconds":

            current = now_wib()

            for (gid, uid), session in (
                self._active_voice.items()
            ):

                if gid != guild.id:
                    continue

                for day, seconds in self.split_seconds(
                    session["last_checkpoint"],
                    current
                ):

                    if period_matches(
                        day,
                        period_type,
                        period_key
                    ):

                        totals[uid] += seconds

        return totals

    def aggregate_casis(
        self,
        guild,
        metric,
        period
    ):

        period_type, period_key = valid_period(
            period
        )

        totals = defaultdict(int)

        gd = self.guild_data(guild.id)

        for uid, values in gd["casis"].items():

            for day, amount in values.get(
                metric,
                {}
            ).items():

                if period_matches(
                    day,
                    period_type,
                    period_key
                ):

                    totals[int(uid)] += int(amount)

        if metric == "voice_seconds":

            current = now_wib()

            for (gid, uid), session in (
                self._active_voice.items()
            ):

                if (
                    gid != guild.id
                    or not session.get("casis_active")
                ):
                    continue

                for day, seconds in self.split_seconds(
                    session["last_checkpoint"],
                    current
                ):

                    if period_matches(
                        day,
                        period_type,
                        period_key
                    ):

                        totals[uid] += seconds

        return totals

    def aggregate_role(
        self,
        guild,
        role,
        metric,
        period
    ):

        if role.id == CASIS_ROLE_ID:

            totals = self.aggregate_casis(
                guild,
                metric,
                period
            )

        else:

            totals = self.aggregate_general(
                guild,
                metric,
                period
            )

        allowed = {
            member.id
            for member in self.get_all_members(guild)
            if any(r.id == role.id for r in member.roles)
        }

        return {
            uid: value
            for uid, value in totals.items()
            if uid in allowed
        }

    @staticmethod
    def sorted_ranking(totals):

        return sorted(
            totals.items(),
            key=lambda item: (
                -item[1],
                item[0]
            )
        )

    @staticmethod
    def active_days(
        gd,
        user_id,
        casis=False,
        period="all"
    ):

        period_type, period_key = valid_period(
            period
        )

        if casis:

            source = gd.get(
                "casis",
                {}
            ).get(
                str(user_id),
                {}
            )

            if not source:
                return 0

            chat_days = {
                day
                for day, count in source.get(
                    "chat",
                    {}
                ).items()
                if (
                    int(count) > 0
                    and period_matches(
                        day,
                        period_type,
                        period_key
                    )
                )
            }

            voice_days = {
                day
                for day, seconds in source.get(
                    "voice_seconds",
                    {}
                ).items()
                if (
                    int(seconds) > 0
                    and period_matches(
                        day,
                        period_type,
                        period_key
                    )
                )
            }

        else:

            chat_days = set()
            voice_days = set()

            for day, values in gd.get(
                "days",
                {}
            ).items():

                if not period_matches(
                    day,
                    period_type,
                    period_key
                ):
                    continue

                if int(
                    values.get(
                        "chat",
                        {}
                    ).get(
                        str(user_id),
                        0
                    )
                ) > 0:

                    chat_days.add(day)

                if int(
                    values.get(
                        "voice_seconds",
                        {}
                    ).get(
                        str(user_id),
                        0
                    )
                ) > 0:

                    voice_days.add(day)

        return len(
            chat_days | voice_days
        )

    # ========================================================
    # EMBED HELPERS
    # ========================================================

    def get_member_name(self, guild, user_id):

        member = guild.get_member(user_id)

        if member is None:

            member = self._members_by_guild.get(
                guild.id,
                {}
            ).get(user_id)

        if member:
            return member.display_name

        return f"User {user_id}"

    def leaderboard_embed(
        self,
        guild,
        title,
        totals,
        metric
    ):

        ranking = self.sorted_ranking(
            totals
        )[:TOP_LIMIT]

        embed = discord.Embed(
            title=title,
            color=discord.Color.blurple(),
            timestamp=now_wib()
        )

        if not ranking:

            embed.description = (
                "Belum ada aktivitas yang tercatat "
                "pada periode ini."
            )

            return embed

        lines = []

        for index, (uid, value) in enumerate(
            ranking,
            start=1
        ):

            name = discord.utils.escape_markdown(
                self.get_member_name(guild, uid)
            )

            if metric == "chat":

                shown = f"{value:,} pesan"

            else:

                shown = format_duration(value)

            lines.append(
                f"**{index}.** {name} — `{shown}`"
            )

        embed.description = "\n".join(lines)

        embed.set_footer(
            text=f"Top {TOP_LIMIT} • {guild.name}"
        )

        return embed

    def parse_period_or_error(self, period):

        try:

            valid_period(period)

            return True

        except ValueError:

            return False

    # ========================================================
    # COMMAND: TOPSTAT
    # ========================================================

    @commands.command(
        name="topstat",
        aliases=["topstats", "top"]
    )
    @commands.guild_only()
    async def topstat(
        self,
        ctx,
        period="all"
    ):

        await self.wait_for_sync()

        if not self.parse_period_or_error(period):

            return await ctx.send(
                "Format periode: "
                "`all`, `YYYY-MM`, atau `YYYY-MM-DD`."
            )

        chat = self.aggregate_general(
            ctx.guild,
            "chat",
            period
        )

        voice = self.aggregate_general(
            ctx.guild,
            "voice_seconds",
            period
        )

        await ctx.send(
            embeds=[
                self.leaderboard_embed(
                    ctx.guild,
                    f"Top 10 Chat • {period}",
                    chat,
                    "chat"
                ),
                self.leaderboard_embed(
                    ctx.guild,
                    f"Top 10 Voice • {period}",
                    voice,
                    "voice_seconds"
                )
            ]
        )

    # ========================================================
    # COMMAND: TOPROLE
    # ========================================================

    @commands.command(
        name="toprole",
        aliases=["toprolestat"]
    )
    @commands.guild_only()
    async def toprole(
        self,
        ctx,
        role: discord.Role,
        period="all"
    ):

        await self.wait_for_sync()

        if not self.parse_period_or_error(period):

            return await ctx.send(
                "Format periode: "
                "`all`, `YYYY-MM`, atau `YYYY-MM-DD`."
            )

        chat = self.aggregate_role(
            ctx.guild,
            role,
            "chat",
            period
        )

        voice = self.aggregate_role(
            ctx.guild,
            role,
            "voice_seconds",
            period
        )

        suffix = (
            " • sejak mendapat role"
            if role.id == CASIS_ROLE_ID
            else ""
        )

        await ctx.send(
            embeds=[
                self.leaderboard_embed(
                    ctx.guild,
                    f"Top 10 Chat • {role.name}"
                    f"{suffix} • {period}",
                    chat,
                    "chat"
                ),
                self.leaderboard_embed(
                    ctx.guild,
                    f"Top 10 Voice • {role.name}"
                    f"{suffix} • {period}",
                    voice,
                    "voice_seconds"
                )
            ]
        )

    # ========================================================
    # COMMAND: CEKUSER
    # ========================================================

    @commands.command(
        name="cekuser",
        aliases=["userstat", "mystat"]
    )
    @commands.guild_only()
    async def cekuser(
        self,
        ctx,
        member: Optional[discord.Member] = None,
        period="all"
    ):

        await self.wait_for_sync()

        member = member or ctx.author

        if not self.parse_period_or_error(period):

            return await ctx.send(
                "Format periode: "
                "`all`, `YYYY-MM`, atau `YYYY-MM-DD`."
            )

        is_casis = (
            member.get_role(CASIS_ROLE_ID) is not None
        )

        if is_casis:

            chat = self.aggregate_casis(
                ctx.guild,
                "chat",
                period
            )

            voice = self.aggregate_casis(
                ctx.guild,
                "voice_seconds",
                period
            )

            cohort = [
                m.id
                for m in self.get_all_members(ctx.guild)
                if m.get_role(CASIS_ROLE_ID)
            ]

            casis_data = self.guild_data(
                ctx.guild.id
            ).get(
                "casis",
                {}
            ).get(
                str(member.id),
                {}
            )

            started = casis_data.get(
                "started_at"
            )

            parsed = parse_iso(started)

            start_text = (
                f"<t:{int(parsed.timestamp())}:F>"
                if parsed
                else "baseline tersedia"
            )

            scope_text = (
                f"Sejak mendapat role Casis: {start_text}"
            )

        else:

            chat = self.aggregate_general(
                ctx.guild,
                "chat",
                period
            )

            voice = self.aggregate_general(
                ctx.guild,
                "voice_seconds",
                period
            )

            cohort = [
                m.id
                for m in self.get_all_members(ctx.guild)
            ]

            scope_text = (
                "Statistik keseluruhan akun"
            )

        chat_count = chat.get(
            member.id,
            0
        )

        voice_seconds = voice.get(
            member.id,
            0
        )

        chat_sorted = self.sorted_ranking({
            uid: value
            for uid, value in chat.items()
            if uid in cohort
        })

        voice_sorted = self.sorted_ranking({
            uid: value
            for uid, value in voice.items()
            if uid in cohort
        })

        chat_rank = next(
            (
                rank
                for rank, (uid, _) in enumerate(
                    chat_sorted,
                    start=1
                )
                if uid == member.id
            ),
            None
        )

        voice_rank = next(
            (
                rank
                for rank, (uid, _) in enumerate(
                    voice_sorted,
                    start=1
                )
                if uid == member.id
            ),
            None
        )

        gd = self.guild_data(
            ctx.guild.id
        )

        active = self.active_days(
            gd,
            member.id,
            casis=is_casis,
            period=period
        )

        avg_chat = (
            round(chat_count / active, 1)
            if active
            else 0
        )

        avg_voice = (
            format_duration(
                int(voice_seconds / active)
            )
            if active
            else "0 menit"
        )

        embed = discord.Embed(
            title=f"Statistik {member.display_name}",
            color=discord.Color.blurple(),
            timestamp=now_wib()
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        embed.add_field(
            name="Chat",
            value=f"`{chat_count:,}` pesan",
            inline=True
        )

        embed.add_field(
            name="Voice",
            value=f"`{format_duration(voice_seconds)}`",
            inline=True
        )

        embed.add_field(
            name="Hari Aktif",
            value=f"`{active}` hari",
            inline=True
        )

        embed.add_field(
            name="Rata-rata Chat",
            value=f"`{avg_chat}` pesan/hari",
            inline=True
        )

        embed.add_field(
            name="Rata-rata Voice",
            value=f"`{avg_voice}`/hari",
            inline=True
        )

        embed.add_field(
            name="Peringkat Chat",
            value=(
                f"`#{chat_rank}`"
                if chat_rank
                else "`Belum masuk ranking`"
            ),
            inline=True
        )

        embed.add_field(
            name="Peringkat Voice",
            value=(
                f"`#{voice_rank}`"
                if voice_rank
                else "`Belum masuk ranking`"
            ),
            inline=True
        )

        embed.add_field(
            name="Cakupan Data",
            value=scope_text,
            inline=False
        )

        embed.set_footer(
            text=f"Periode: {period} • nanZ Statistics"
        )

        await ctx.send(
            embed=embed
        )

    # ========================================================
    # COMMAND: STAFFSTATS
    # ========================================================

    @commands.command(
        name="staffstats",
        aliases=["rolestats"]
    )
    @commands.guild_only()
    async def staffstats(
        self,
        ctx,
        role: discord.Role,
        period="all"
    ):

        await self.wait_for_sync()

        if not self.parse_period_or_error(period):

            return await ctx.send(
                "Format periode: "
                "`all`, `YYYY-MM`, atau `YYYY-MM-DD`."
            )

        members = [
            member
            for member in self.get_all_members(ctx.guild)
            if any(
                r.id == role.id
                for r in member.roles
            )
        ]

        chat = self.aggregate_role(
            ctx.guild,
            role,
            "chat",
            period
        )

        voice = self.aggregate_role(
            ctx.guild,
            role,
            "voice_seconds",
            period
        )

        active_ids = {
            uid
            for uid in set(chat) | set(voice)
            if (
                chat.get(uid, 0) > 0
                or voice.get(uid, 0) > 0
            )
        }

        total_chat = sum(chat.values())
        total_voice = sum(voice.values())

        active_count = len(active_ids)
        total_count = len(members)

        embed = discord.Embed(
            title=f"Staff Statistics • {role.name}",
            color=discord.Color.blurple(),
            timestamp=now_wib()
        )

        embed.add_field(
            name="Total Anggota",
            value=f"`{total_count}`",
            inline=True
        )

        embed.add_field(
            name="Staff Aktif",
            value=f"`{active_count}`",
            inline=True
        )

        embed.add_field(
            name="Staff Belum Aktif",
            value=f"`{max(0, total_count - active_count)}`",
            inline=True
        )

        embed.add_field(
            name="Total Chat",
            value=f"`{total_chat:,}` pesan",
            inline=True
        )

        embed.add_field(
            name="Total Voice",
            value=f"`{format_duration(total_voice)}`",
            inline=True
        )

        if total_count:

            embed.add_field(
                name="Rata-rata Chat",
                value=(
                    f"`{round(total_chat / total_count, 1)}` "
                    "pesan/orang"
                ),
                inline=True
            )

            embed.add_field(
                name="Rata-rata Voice",
                value=(
                    f"`{format_duration(int(total_voice / total_count))}`"
                    "/orang"
                ),
                inline=True
            )

        chat_top = self.sorted_ranking(
            chat
        )[:TOP_LIMIT]

        voice_top = self.sorted_ranking(
            voice
        )[:TOP_LIMIT]

        def compact(items, metric):

            if not items:
                return "Belum ada data."

            result = []

            for rank, (uid, amount) in enumerate(
                items,
                start=1
            ):

                name = discord.utils.escape_markdown(
                    self.get_member_name(
                        ctx.guild,
                        uid
                    )
                )

                shown = (
                    f"{amount:,} pesan"
                    if metric == "chat"
                    else format_duration(amount)
                )

                result.append(
                    f"**{rank}.** {name} — `{shown}`"
                )

            return "\n".join(result)

        embed.add_field(
            name="Top Chat",
            value=compact(
                chat_top,
                "chat"
            ),
            inline=False
        )

        embed.add_field(
            name="Top Voice",
            value=compact(
                voice_top,
                "voice"
            ),
            inline=False
        )

        if role.id == CASIS_ROLE_ID:

            embed.add_field(
                name="Catatan Casis",
                value=(
                    "Perhitungan tiap anggota dimulai "
                    "dari baseline saat role Casis diberikan."
                ),
                inline=False
            )

        embed.set_footer(
            text=f"Periode: {period} • nanZ Statistics"
        )

        await ctx.send(
            embed=embed
        )

    # ========================================================
    # DISCORD EVENTS
    # ========================================================

    @commands.Cog.listener()
    async def on_message(self, message):

        if not message.guild:
            return

        if not isinstance(
            message.author,
            discord.Member
        ):
            return

        if message.author.bot:
            return

        if message.webhook_id:
            return

        self.increment_chat(
            message.guild,
            message.author
        )

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member,
        before,
        after
    ):

        if member.bot:
            return

        self.remember_member(member)

        key = (
            member.guild.id,
            member.id
        )

        # Join voice.
        if (
            before.channel is None
            and after.channel is not None
        ):

            self.start_voice_session(
                member
            )

            return

        # Leave voice.
        if (
            before.channel is not None
            and after.channel is None
        ):

            self.checkpoint_voice_session(
                member.guild.id,
                member.id
            )

            self._active_voice.pop(
                key,
                None
            )

            self.mark_dirty()

            return

        # Channel switch, mute, deafen,
        # camera, and stream do not reset session.
        if (
            before.channel is not None
            and after.channel is not None
        ):

            if key not in self._active_voice:

                self.start_voice_session(
                    member
                )

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before,
        after
    ):

        self.remember_member(after)

        before_has = (
            before.get_role(CASIS_ROLE_ID) is not None
        )

        after_has = (
            after.get_role(CASIS_ROLE_ID) is not None
        )

        if before_has == after_has:
            return

        key = (
            after.guild.id,
            after.id
        )

        session = self._active_voice.get(
            key
        )

        if session:

            self.checkpoint_voice_session(
                after.guild.id,
                after.id
            )

        gd = self.guild_data(
            after.guild.id
        )

        if after_has:

            # Role Casis baru diberikan.
            gd["casis"][str(after.id)] = {
                "started_at": iso_now(),
                "chat": {},
                "voice_seconds": {}
            }

            if session:
                session["casis_active"] = True

        else:

            # Role dilepas: hentikan statistik Casis.
            if session:
                session["casis_active"] = False

        self.mark_dirty()

        await self.save_data()

    @commands.Cog.listener()
    async def on_member_join(self, member):

        self.remember_member(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member):

        self.forget_member(member)

    # ========================================================
    # BACKGROUND TASKS
    # ========================================================

    @tasks.loop(
        seconds=VOICE_CHECKPOINT_INTERVAL
    )
    async def voice_checkpoint_loop(self):

        await self.checkpoint_all_voice()

    @voice_checkpoint_loop.before_loop
    async def before_voice_checkpoint_loop(self):

        await self.bot.wait_until_ready()

    @tasks.loop(
        seconds=SAVE_INTERVAL
    )
    async def save_loop(self):

        await self.save_data()

    @save_loop.before_loop
    async def before_save_loop(self):

        await self.bot.wait_until_ready()

    # ========================================================
    # LIFECYCLE
    # ========================================================

    async def cog_load(self):

        self.voice_checkpoint_loop.start()
        self.save_loop.start()

        self._ready_task = asyncio.create_task(
            self.reconcile_voice_sessions()
        )

    def cog_unload(self):

        self.voice_checkpoint_loop.cancel()
        self.save_loop.cancel()

        if (
            self._ready_task
            and not self._ready_task.done()
        ):

            self._ready_task.cancel()

        try:

            asyncio.create_task(
                self.shutdown_save()
            )

        except RuntimeError:
            pass

    async def shutdown_save(self):

        for guild_id, user_id in list(
            self._active_voice.keys()
        ):

            self.checkpoint_voice_session(
                guild_id,
                user_id
            )

        await self.save_data(
            force=True
        )


# ============================================================
# SETUP
# ============================================================

async def setup(bot):

    await bot.add_cog(
        TopStats(bot)
    )
