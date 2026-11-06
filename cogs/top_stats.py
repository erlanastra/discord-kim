# cogs/topstats.py
# NANZ TOP STATISTICS
# Compatible with Python 3.8+ and discord.py 2.x
#
# Commands:
#   !topstat [all|YYYY-MM|YYYY-MM-DD]
#   !toprole @Role [all|YYYY-MM|YYYY-MM-DD]
#   !cekuser [@Member] [all|YYYY-MM|YYYY-MM-DD]
#   !staffstats @Role [all|YYYY-MM|YYYY-MM-DD]
#
# Required intents:
#   guilds, members, messages, message_content, voice_states
# Enable SERVER MEMBERS INTENT and MESSAGE CONTENT INTENT
# in the Discord Developer Portal.
#
# Casis role:
#   Statistics are recorded separately from the moment the role is granted.
#   Existing Casis holders receive a one-time baseline on first startup with
#   this version. Re-granting the role starts a fresh Casis statistics period.

import asyncio
import json
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

import discord
from discord.ext import commands, tasks


WIB = timezone(timedelta(hours=7))
CASIS_ROLE_ID = 1499049884781907998

TOP_LIMIT = 10
SAVE_INTERVAL = 30
VOICE_CHECKPOINT_INTERVAL = 60

# Store the file in the bot project root, assuming this file is in /cogs/.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(PROJECT_ROOT, "top_stats.json")


def now_wib() -> datetime:
    return datetime.now(WIB)


def iso_now() -> str:
    return now_wib().isoformat()


def parse_iso(value: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=WIB)
        return dt.astimezone(WIB)
    except (TypeError, ValueError):
        return None


def date_key(dt: datetime) -> str:
    return dt.astimezone(WIB).strftime("%Y-%m-%d")


def valid_period(period: Optional[str]) -> Tuple[str, Optional[str]]:
    """Return ('all'|'month'|'day', normalized key)."""
    if not period or period.lower() in ("all", "semua", "total"):
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

    raise ValueError("Format periode salah. Gunakan `all`, `YYYY-MM`, atau `YYYY-MM-DD`.")


def period_matches(day: str, period_type: str, period_key: Optional[str]) -> bool:
    if period_type == "all":
        return True
    if period_type == "month":
        return day.startswith(period_key or "")
    return day == period_key


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60

    if days:
        return f"{days} hari {hours} jam"
    if hours:
        return f"{hours} jam {minutes} menit"
    return f"{minutes} menit"


def make_guild_data() -> dict:
    return {
        "days": {},
        "casis": {},
        "casis_initialized": False,
        "casis_baseline_at": None,
    }


class TopStats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = {"version": 3, "guilds": {}}
        self.dirty = False
        self._save_lock = asyncio.Lock()
        # key=(guild_id, user_id), value={last_checkpoint, casis_active}
        self._active_voice: Dict[Tuple[int, int], dict] = {}
        self._ready_task = None

        self.load_data()

    # ------------------------------------------------------------------
    # DATA STORAGE / MIGRATION
    # ------------------------------------------------------------------

    def load_data(self):
        if not os.path.exists(DB_FILE):
            self.data = {"version": 3, "guilds": {}}
            return

        try:
            with open(DB_FILE, "r", encoding="utf-8") as file:
                raw = json.load(file)
        except (json.JSONDecodeError, OSError) as exc:
            # Fail safely: do not overwrite an unreadable/corrupt database.
            raise RuntimeError(
                f"Gagal membaca {DB_FILE}. File tidak akan ditimpa otomatis. "
                f"Periksa atau pulihkan file tersebut terlebih dahulu. Detail: {exc}"
            )

        if isinstance(raw, dict) and isinstance(raw.get("guilds"), dict):
            self.data = raw
            self.data.setdefault("version", 3)
            self.data.setdefault("guilds", {})
        else:
            # Migrate the older daily layout: {guild_id: {date: {chat, voice_seconds}}}
            migrated = {"version": 3, "guilds": {}}
            if isinstance(raw, dict):
                for guild_id, old_days in raw.items():
                    if not isinstance(old_days, dict):
                        continue
                    guild_data = make_guild_data()
                    for day, values in old_days.items():
                        if not isinstance(values, dict):
                            continue
                        chat = values.get("chat", {})
                        voice_seconds = values.get("voice_seconds", {})
                        guild_data["days"][day] = {
                            "chat": chat if isinstance(chat, dict) else {},
                            "voice_seconds": (
                                voice_seconds if isinstance(voice_seconds, dict) else {}
                            ),
                        }
                    migrated["guilds"][str(guild_id)] = guild_data
            self.data = migrated
            self.dirty = True

        for guild_data in self.data["guilds"].values():
            guild_data.setdefault("days", {})
            guild_data.setdefault("casis", {})
            guild_data.setdefault("casis_initialized", False)
            guild_data.setdefault("casis_baseline_at", None)

    def guild_data(self, guild_id: int) -> dict:
        key = str(guild_id)
        if key not in self.data["guilds"]:
            self.data["guilds"][key] = make_guild_data()
            self.dirty = True
        return self.data["guilds"][key]

    async def save_data(self, force: bool = False):
        if not self.dirty and not force:
            return

        async with self._save_lock:
            if not self.dirty and not force:
                return

            directory = os.path.dirname(DB_FILE)
            os.makedirs(directory, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(
                prefix="top_stats_", suffix=".tmp", dir=directory
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as file:
                    json.dump(self.data, file, ensure_ascii=False, indent=2)
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

    def mark_dirty(self):
        self.dirty = True

    # ------------------------------------------------------------------
    # DAILY GENERAL + CASIS COUNTERS
    # ------------------------------------------------------------------

    def ensure_day(self, guild_data: dict, day: str) -> dict:
        if day not in guild_data["days"]:
            guild_data["days"][day] = {"chat": {}, "voice_seconds": {}}
        entry = guild_data["days"][day]
        entry.setdefault("chat", {})
        entry.setdefault("voice_seconds", {})
        return entry

    def ensure_casis_user(self, guild_data: dict, user_id: int, start: Optional[str] = None):
        key = str(user_id)
        if key not in guild_data["casis"]:
            guild_data["casis"][key] = {
                "started_at": start or iso_now(),
                "chat": {},
                "voice_seconds": {},
            }
        else:
            guild_data["casis"][key].setdefault("chat", {})
            guild_data["casis"][key].setdefault("voice_seconds", {})
        return guild_data["casis"][key]

    def increment_chat(self, guild: discord.Guild, member: discord.Member):
        gd = self.guild_data(guild.id)
        today = date_key(now_wib())
        entry = self.ensure_day(gd, today)
        uid = str(member.id)
        entry["chat"][uid] = int(entry["chat"].get(uid, 0)) + 1

        if member.get_role(CASIS_ROLE_ID):
            casis = self.ensure_casis_user(gd, member.id)
            casis["chat"][today] = int(casis["chat"].get(today, 0)) + 1

        self.mark_dirty()

    # ------------------------------------------------------------------
    # VOICE TRACKING
    # ------------------------------------------------------------------

    def split_seconds(self, start: datetime, end: datetime):
        """Yield (date, seconds) segments split at WIB midnight."""
        cursor = start.astimezone(WIB)
        end = end.astimezone(WIB)

        while cursor < end:
            next_midnight = datetime.combine(
                cursor.date() + timedelta(days=1),
                datetime.min.time(),
                tzinfo=WIB,
            )
            segment_end = min(end, next_midnight)
            seconds = int((segment_end - cursor).total_seconds())
            if seconds > 0:
                yield date_key(cursor), seconds
            cursor = segment_end

    def checkpoint_voice_session(self, guild_id: int, user_id: int, at: Optional[datetime] = None):
        key = (guild_id, user_id)
        session = self._active_voice.get(key)
        if not session:
            return

        current = (at or now_wib()).astimezone(WIB)
        last = session["last_checkpoint"]
        if current <= last:
            return

        gd = self.guild_data(guild_id)
        for day, seconds in self.split_seconds(last, current):
            entry = self.ensure_day(gd, day)
            uid = str(user_id)
            entry["voice_seconds"][uid] = int(entry["voice_seconds"].get(uid, 0)) + seconds

            if session.get("casis_active"):
                casis = self.ensure_casis_user(gd, user_id)
                casis["voice_seconds"][day] = (
                    int(casis["voice_seconds"].get(day, 0)) + seconds
                )

        session["last_checkpoint"] = current
        self.mark_dirty()

    def start_voice_session(self, member: discord.Member):
        key = (member.guild.id, member.id)
        if key in self._active_voice:
            return
        self._active_voice[key] = {
            "last_checkpoint": now_wib(),
            "casis_active": bool(member.get_role(CASIS_ROLE_ID)),
        }

    async def checkpoint_all_voice(self):
        current = now_wib()
        for guild_id, user_id in list(self._active_voice.keys()):
            self.checkpoint_voice_session(guild_id, user_id, current)
        await self.save_data()

    async def reconcile_voice_sessions(self):
        """Rebuild live sessions after startup; bot downtime is never counted."""
        await self.bot.wait_until_ready()

        # One-time baseline for people who already hold Casis when this
        # version is installed. The baseline is deliberately startup time.
        baseline = iso_now()
        for guild in self.bot.guilds:
            gd = self.guild_data(guild.id)
            if not gd.get("casis_initialized", False):
                for member in guild.members:
                    if member.bot:
                        continue
                    if member.get_role(CASIS_ROLE_ID):
                        self.ensure_casis_user(gd, member.id, baseline)
                gd["casis_initialized"] = True
                gd["casis_baseline_at"] = baseline
                self.mark_dirty()

            # Sessions are restarted from now, not from the previous process.
            for voice_state in guild.voice_states.values():
                member = voice_state.member or guild.get_member(voice_state.user_id)
                if member and not member.bot and voice_state.channel:
                    self.start_voice_session(member)

        await self.save_data(force=True)

    # ------------------------------------------------------------------
    # PERIOD AGGREGATION
    # ------------------------------------------------------------------

    def aggregate_general(self, guild: discord.Guild, metric: str, period: str):
        period_type, period_key = valid_period(period)
        totals = defaultdict(int)
        gd = self.guild_data(guild.id)

        for day, values in gd["days"].items():
            if not period_matches(day, period_type, period_key):
                continue
            for uid, amount in values.get(metric, {}).items():
                totals[int(uid)] += int(amount)

        # Include the current uncheckpointed voice tail.
        if metric == "voice_seconds":
            current = now_wib()
            for (gid, uid), session in self._active_voice.items():
                if gid != guild.id:
                    continue
                start = session["last_checkpoint"]
                for day, seconds in self.split_seconds(start, current):
                    if period_matches(day, period_type, period_key):
                        totals[uid] += seconds

        return totals

    def aggregate_casis(self, guild: discord.Guild, metric: str, period: str):
        period_type, period_key = valid_period(period)
        totals = defaultdict(int)
        gd = self.guild_data(guild.id)

        for uid, values in gd["casis"].items():
            for day, amount in values.get(metric, {}).items():
                if period_matches(day, period_type, period_key):
                    totals[int(uid)] += int(amount)

        if metric == "voice_seconds":
            current = now_wib()
            for (gid, uid), session in self._active_voice.items():
                if gid != guild.id or not session.get("casis_active"):
                    continue
                for day, seconds in self.split_seconds(session["last_checkpoint"], current):
                    if period_matches(day, period_type, period_key):
                        totals[uid] += seconds

        return totals

    def aggregate_role(self, guild: discord.Guild, role: discord.Role, metric: str, period: str):
        if role.id == CASIS_ROLE_ID:
            totals = self.aggregate_casis(guild, metric, period)
        else:
            totals = self.aggregate_general(guild, metric, period)

        allowed = {member.id for member in role.members if not member.bot}
        return {uid: value for uid, value in totals.items() if uid in allowed}

    @staticmethod
    def sorted_ranking(totals: dict):
        return sorted(totals.items(), key=lambda item: (-item[1], item[0]))

    @staticmethod
    def active_days(
        guild_data: dict,
        user_id: int,
        casis: bool = False,
        period: str = "all",
    ) -> int:
        period_type, period_key = valid_period(period)
        if casis:
            source = guild_data.get("casis", {}).get(str(user_id), {})
            if not source:
                return 0
            chat_days = {
                day for day, count in source.get("chat", {}).items()
                if int(count) > 0 and period_matches(day, period_type, period_key)
            }
            voice_days = {
                day for day, seconds in source.get("voice_seconds", {}).items()
                if int(seconds) > 0 and period_matches(day, period_type, period_key)
            }
        else:
            chat_days = set()
            voice_days = set()
            for day, values in guild_data.get("days", {}).items():
                if not period_matches(day, period_type, period_key):
                    continue
                if int(values.get("chat", {}).get(str(user_id), 0)) > 0:
                    chat_days.add(day)
                if int(values.get("voice_seconds", {}).get(str(user_id), 0)) > 0:
                    voice_days.add(day)
        return len(chat_days | voice_days)

    # ------------------------------------------------------------------
    # EMBED HELPERS
    # ------------------------------------------------------------------

    def get_member_name(self, guild: discord.Guild, user_id: int) -> str:
        member = guild.get_member(user_id)
        return member.display_name if member else f"User {user_id}"

    def leaderboard_embed(self, guild: discord.Guild, title: str, totals: dict, metric: str):
        ranking = self.sorted_ranking(totals)[:TOP_LIMIT]
        embed = discord.Embed(
            title=title,
            color=discord.Color.blurple(),
            timestamp=now_wib(),
        )

        if not ranking:
            embed.description = "Belum ada aktivitas yang tercatat pada periode ini."
            return embed

        lines = []
        for index, (uid, value) in enumerate(ranking, start=1):
            name = discord.utils.escape_markdown(self.get_member_name(guild, uid))
            shown = f"{value:,} pesan" if metric == "chat" else format_duration(value)
            lines.append(f"**{index}.** {name} — `{shown}`")

        embed.description = "\n".join(lines)
        embed.set_footer(text=f"Top {TOP_LIMIT} • {guild.name}")
        return embed

    def parse_period_or_error(self, period: str):
        try:
            valid_period(period)
            return True
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # COMMANDS
    # ------------------------------------------------------------------

    @commands.command(name="topstat", aliases=["topstats", "top"])
    @commands.guild_only()
    async def topstat(self, ctx: commands.Context, period: str = "all"):
        if not self.parse_period_or_error(period):
            return await ctx.send(
                "Format periode: `all`, `YYYY-MM`, atau `YYYY-MM-DD`."
            )

        chat = self.aggregate_general(ctx.guild, "chat", period)
        voice = self.aggregate_general(ctx.guild, "voice_seconds", period)

        await ctx.send(embeds=[
            self.leaderboard_embed(
                ctx.guild, f"Top 10 Chat • {period}", chat, "chat"
            ),
            self.leaderboard_embed(
                ctx.guild, f"Top 10 Voice • {period}", voice, "voice_seconds"
            ),
        ])

    @commands.command(name="toprole", aliases=["toprolestat"])
    @commands.guild_only()
    async def toprole(
        self, ctx: commands.Context, role: discord.Role, period: str = "all"
    ):
        if not self.parse_period_or_error(period):
            return await ctx.send(
                "Format periode: `all`, `YYYY-MM`, atau `YYYY-MM-DD`."
            )

        chat = self.aggregate_role(ctx.guild, role, "chat", period)
        voice = self.aggregate_role(ctx.guild, role, "voice_seconds", period)

        suffix = " • sejak mendapat role" if role.id == CASIS_ROLE_ID else ""
        await ctx.send(embeds=[
            self.leaderboard_embed(
                ctx.guild, f"Top 10 Chat • {role.name}{suffix} • {period}",
                chat, "chat"
            ),
            self.leaderboard_embed(
                ctx.guild, f"Top 10 Voice • {role.name}{suffix} • {period}",
                voice, "voice_seconds"
            ),
        ])

    @commands.command(name="cekuser", aliases=["userstat", "mystat"])
    @commands.guild_only()
    async def cekuser(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
        period: str = "all",
    ):
        member = member or ctx.author
        if not self.parse_period_or_error(period):
            return await ctx.send(
                "Format periode: `all`, `YYYY-MM`, atau `YYYY-MM-DD`."
            )

        is_casis = member.get_role(CASIS_ROLE_ID) is not None
        metric_chat = "chat"
        metric_voice = "voice_seconds"

        if is_casis:
            chat = self.aggregate_casis(ctx.guild, metric_chat, period)
            voice = self.aggregate_casis(ctx.guild, metric_voice, period)
            cohort = [
                m.id for m in ctx.guild.members
                if not m.bot and m.get_role(CASIS_ROLE_ID)
            ]
            casis_data = self.guild_data(ctx.guild.id).get("casis", {}).get(str(member.id), {})
            started = casis_data.get("started_at")
            start_text = f"<t:{int(parse_iso(started).timestamp())}:F>" if parse_iso(started) else "baseline tersedia"
            scope_text = f"Sejak mendapat role Casis: {start_text}"
        else:
            chat = self.aggregate_general(ctx.guild, metric_chat, period)
            voice = self.aggregate_general(ctx.guild, metric_voice, period)
            cohort = [m.id for m in ctx.guild.members if not m.bot]
            scope_text = "Statistik keseluruhan akun"

        chat_count = chat.get(member.id, 0)
        voice_seconds = voice.get(member.id, 0)

        chat_rank = None
        voice_rank = None
        chat_sorted = self.sorted_ranking({uid: value for uid, value in chat.items() if uid in cohort})
        voice_sorted = self.sorted_ranking({uid: value for uid, value in voice.items() if uid in cohort})

        for rank, (uid, _) in enumerate(chat_sorted, start=1):
            if uid == member.id:
                chat_rank = rank
                break
        for rank, (uid, _) in enumerate(voice_sorted, start=1):
            if uid == member.id:
                voice_rank = rank
                break

        gd = self.guild_data(ctx.guild.id)
        active = self.active_days(gd, member.id, casis=is_casis, period=period)
        avg_chat = round(chat_count / active, 1) if active else 0
        avg_voice = format_duration(int(voice_seconds / active)) if active else "0 menit"

        embed = discord.Embed(
            title=f"Statistik {member.display_name}",
            color=discord.Color.blurple(),
            timestamp=now_wib(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Chat", value=f"`{chat_count:,}` pesan", inline=True)
        embed.add_field(name="Voice", value=f"`{format_duration(voice_seconds)}`", inline=True)
        embed.add_field(name="Hari Aktif", value=f"`{active}` hari", inline=True)
        embed.add_field(name="Rata-rata Chat", value=f"`{avg_chat}` pesan/hari", inline=True)
        embed.add_field(name="Rata-rata Voice", value=f"`{avg_voice}`/hari", inline=True)
        embed.add_field(
            name="Peringkat",
            value=f"Chat: `#{chat_rank}`" if chat_rank else "Chat: `Belum masuk ranking`",
            inline=True,
        )
        embed.add_field(
            name="Peringkat Voice",
            value=f"`#{voice_rank}`" if voice_rank else "`Belum masuk ranking`",
            inline=True,
        )
        embed.add_field(name="Cakupan Data", value=scope_text, inline=False)
        embed.set_footer(text=f"Periode: {period} • nanZ Statistics")
        await ctx.send(embed=embed)

    @commands.command(name="staffstats", aliases=["rolestats"])
    @commands.guild_only()
    async def staffstats(
        self, ctx: commands.Context, role: discord.Role, period: str = "all"
    ):
        if not self.parse_period_or_error(period):
            return await ctx.send(
                "Format periode: `all`, `YYYY-MM`, atau `YYYY-MM-DD`."
            )

        members = [m for m in role.members if not m.bot]
        chat = self.aggregate_role(ctx.guild, role, "chat", period)
        voice = self.aggregate_role(ctx.guild, role, "voice_seconds", period)

        active_ids = {
            uid for uid in set(chat) | set(voice)
            if chat.get(uid, 0) > 0 or voice.get(uid, 0) > 0
        }
        total_chat = sum(chat.values())
        total_voice = sum(voice.values())
        active_count = len(active_ids)
        total_count = len(members)

        embed = discord.Embed(
            title=f"Staff Statistics • {role.name}",
            color=discord.Color.blurple(),
            timestamp=now_wib(),
        )
        embed.add_field(name="Total Anggota", value=f"`{total_count}`", inline=True)
        embed.add_field(name="Staff Aktif", value=f"`{active_count}`", inline=True)
        embed.add_field(name="Staff Belum Aktif", value=f"`{max(0, total_count-active_count)}`", inline=True)
        embed.add_field(name="Total Chat", value=f"`{total_chat:,}` pesan", inline=True)
        embed.add_field(name="Total Voice", value=f"`{format_duration(total_voice)}`", inline=True)

        if total_count:
            embed.add_field(
                name="Rata-rata Chat",
                value=f"`{round(total_chat / total_count, 1)}` pesan/orang",
                inline=True,
            )
            embed.add_field(
                name="Rata-rata Voice",
                value=f"`{format_duration(int(total_voice / total_count))}`/orang",
                inline=True,
            )

        chat_top = self.sorted_ranking(chat)[:TOP_LIMIT]
        voice_top = self.sorted_ranking(voice)[:TOP_LIMIT]

        def compact(items, metric):
            if not items:
                return "Belum ada data."
            result = []
            for rank, (uid, amount) in enumerate(items, start=1):
                name = discord.utils.escape_markdown(self.get_member_name(ctx.guild, uid))
                shown = f"{amount:,} pesan" if metric == "chat" else format_duration(amount)
                result.append(f"**{rank}.** {name} — `{shown}`")
            return "\n".join(result)

        embed.add_field(name="Top Chat", value=compact(chat_top, "chat"), inline=False)
        embed.add_field(name="Top Voice", value=compact(voice_top, "voice"), inline=False)

        if role.id == CASIS_ROLE_ID:
            embed.add_field(
                name="Catatan Casis",
                value="Perhitungan tiap anggota dimulai dari baseline saat role Casis diberikan.",
                inline=False,
            )

        embed.set_footer(text=f"Periode: {period} • nanZ Statistics")
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    # DISCORD EVENTS
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or not isinstance(message.author, discord.Member):
            return
        if message.author.bot or message.webhook_id:
            return
        self.increment_chat(message.guild, message.author)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member.bot:
            return

        key = (member.guild.id, member.id)

        # Join voice: begin counting from now.
        if before.channel is None and after.channel is not None:
            self.start_voice_session(member)
            return

        # Leave voice: checkpoint final duration and close session.
        if before.channel is not None and after.channel is None:
            self.checkpoint_voice_session(member.guild.id, member.id)
            self._active_voice.pop(key, None)
            self.mark_dirty()
            return

        # Channel switch, mute/deafen, stream, camera: keep the same session.
        if before.channel is not None and after.channel is not None:
            if key not in self._active_voice:
                self.start_voice_session(member)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        before_has = before.get_role(CASIS_ROLE_ID) is not None
        after_has = after.get_role(CASIS_ROLE_ID) is not None

        if before_has == after_has:
            return

        key = (after.guild.id, after.id)
        session = self._active_voice.get(key)

        # Close the previous Casis interval before changing its status.
        if session:
            self.checkpoint_voice_session(after.guild.id, after.id)

        gd = self.guild_data(after.guild.id)

        if after_has:
            # New grant/re-grant: start a fresh Casis period.
            gd["casis"][str(after.id)] = {
                "started_at": iso_now(),
                "chat": {},
                "voice_seconds": {},
            }
            if session:
                session["casis_active"] = True
        else:
            # Keep previous data for audit/history, but stop counting it.
            if session:
                session["casis_active"] = False

        self.mark_dirty()
        await self.save_data()

    # ------------------------------------------------------------------
    # BACKGROUND TASKS / LIFECYCLE
    # ------------------------------------------------------------------

    @tasks.loop(seconds=VOICE_CHECKPOINT_INTERVAL)
    async def voice_checkpoint_loop(self):
        await self.checkpoint_all_voice()

    @voice_checkpoint_loop.before_loop
    async def before_voice_checkpoint_loop(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=SAVE_INTERVAL)
    async def save_loop(self):
        await self.save_data()

    @save_loop.before_loop
    async def before_save_loop(self):
        await self.bot.wait_until_ready()

    async def cog_load(self):
        self.voice_checkpoint_loop.start()
        self.save_loop.start()
        self._ready_task = asyncio.create_task(self.reconcile_voice_sessions())

    def cog_unload(self):
        self.voice_checkpoint_loop.cancel()
        self.save_loop.cancel()
        if self._ready_task and not self._ready_task.done():
            self._ready_task.cancel()
        try:
            asyncio.create_task(self.shutdown_save())
        except RuntimeError:
            pass

    async def shutdown_save(self):
        for guild_id, user_id in list(self._active_voice.keys()):
            self.checkpoint_voice_session(guild_id, user_id)
        await self.save_data(force=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TopStats(bot))
