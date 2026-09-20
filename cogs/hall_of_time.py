import discord
from discord.ext import commands
from datetime import datetime, timezone
import sqlite3
import os
import math


class HallOfTime(commands.Cog):
    """Permanent Hall of Time for nanZ Server."""

    DB_FILE_NAME = "hall_of_time.db"
    PAGE_SIZE = 6

    # Purple / black / blue visual identity.
    PURPLE = 0x7C3AED
    BLUE = 0x2563EB
    DARK = 0x0B0A12
    SOFT = 0x4C3D75

    CATEGORIES = (
        "FOUNDATION",
        "LEADERSHIP",
        "COMMUNITY",
        "CREATIVE",
        "EVENT",
        "DEVELOPMENT",
        "SPECIAL RECOGNITION",
    )

    # Isi role ID jika ada role khusus pengelola Hall.
    # Administrator tetap selalu boleh mengelola.
    HALL_MANAGER_ROLE_IDS = set()

    def __init__(self, bot):
        self.bot = bot
        self.db_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            self.DB_FILE_NAME,
        )
        self.ready_once = False
        self.init_db()

    # =========================================================
    # DATABASE
    # =========================================================

    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_db(self):
        conn = self.connect()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS honorees (
                    user_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    recognition TEXT NOT NULL,
                    era_start TEXT,
                    era_end TEXT,
                    contribution TEXT NOT NULL,
                    legacy TEXT NOT NULL,
                    quote TEXT,
                    recognized_at TEXT NOT NULL,
                    message_id INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS hall_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    event_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES honorees(user_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_honorees_recognized
                    ON honorees(recognized_at);
            """)
            conn.commit()
        finally:
            conn.close()

        print(f"[HALL OF TIME] Database siap: {self.db_path}")

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def pretty_date(value):
        if not value:
            return "Tidak tercatat"
        try:
            return datetime.fromisoformat(value).strftime("%d %B %Y")
        except ValueError:
            return value

    @staticmethod
    def year_range(start, end):
        if start and end:
            return f"{start} — {end}"
        if start:
            return f"{start} — Sekarang"
        return "Tidak tercatat"

    @staticmethod
    def cut(value, limit):
        return (value or "").strip()[:limit]

    def get_setting(self, key, default=None):
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default
        finally:
            conn.close()

    def set_setting(self, key, value):
        conn = self.connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
                (key, str(value)),
            )
            conn.commit()
        finally:
            conn.close()

    def get(self, user_id):
        conn = self.connect()
        try:
            return conn.execute(
                "SELECT * FROM honorees WHERE user_id = ?", (user_id,)
            ).fetchone()
        finally:
            conn.close()

    def all(self, page=0):
        conn = self.connect()
        try:
            total = conn.execute(
                "SELECT COUNT(*) n FROM honorees"
            ).fetchone()["n"]
            rows = conn.execute(
                """
                SELECT * FROM honorees
                ORDER BY recognized_at ASC, user_id ASC
                LIMIT ? OFFSET ?
                """,
                (self.PAGE_SIZE, page * self.PAGE_SIZE),
            ).fetchall()
            return total, rows
        finally:
            conn.close()

    def save(self, member, recognition, era_start, era_end,
             contribution, legacy, quote):
        stamp = self.now()
        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT INTO honorees(
                    user_id, guild_id, recognition, era_start, era_end,
                    contribution, legacy, quote, recognized_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    guild_id=excluded.guild_id,
                    recognition=excluded.recognition,
                    era_start=excluded.era_start,
                    era_end=excluded.era_end,
                    contribution=excluded.contribution,
                    legacy=excluded.legacy,
                    quote=excluded.quote,
                    updated_at=excluded.updated_at
                """,
                (
                    member.id, member.guild.id, recognition,
                    era_start, era_end, contribution, legacy, quote,
                    stamp, stamp, stamp,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def set_message(self, user_id, message_id):
        conn = self.connect()
        try:
            conn.execute(
                "UPDATE honorees SET message_id=?, updated_at=? WHERE user_id=?",
                (message_id, self.now(), user_id),
            )
            conn.commit()
        finally:
            conn.close()

    def delete(self, user_id):
        conn = self.connect()
        try:
            conn.execute("DELETE FROM honorees WHERE user_id=?", (user_id,))
            conn.commit()
        finally:
            conn.close()

    def add_event(self, user_id, title, description):
        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT INTO hall_events(user_id,title,description,event_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, title, description, self.now()),
            )
            conn.commit()
        finally:
            conn.close()

    def events(self, user_id):
        conn = self.connect()
        try:
            return conn.execute(
                """
                SELECT * FROM hall_events
                WHERE user_id=? ORDER BY event_at ASC, id ASC
                """, (user_id,)
            ).fetchall()
        finally:
            conn.close()

    # =========================================================
    # DISCORD HELPERS
    # =========================================================

    def can_manage(self, member):
        if member.guild_permissions.administrator:
            return True
        return bool(self.HALL_MANAGER_ROLE_IDS) and any(
            role.id in self.HALL_MANAGER_ROLE_IDS for role in member.roles
        )

    async def get_member(self, guild, user_id):
        member = guild.get_member(user_id)
        if member:
            return member
        try:
            return await guild.fetch_member(user_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    async def bot_logo(self, guild):
        me = guild.me
        if me:
            return me.display_avatar.url
        if self.bot.user:
            return self.bot.user.display_avatar.url
        return guild.icon.url if guild.icon else None

    def embed(self, title, description=None, color=None):
        return discord.Embed(
            title=title,
            description=description,
            color=color or self.PURPLE,
            timestamp=datetime.now(timezone.utc),
        )

    async def brand(self, embed, guild):
        logo = await self.bot_logo(guild)
        if logo:
            embed.set_author(
                name="nanZ Server  •  HALL OF TIME",
                icon_url=logo,
            )
        embed.set_footer(
            text="nanZ Server • Hall of Time • Not forgotten. Forever part of nanZ."
        )
        return embed

    # =========================================================
    # EMBEDS
    # =========================================================

    async def home_embed(self, guild):
        total, _ = self.all(0)
        e = self.embed(
            "🏛️  HALL OF TIME",
            "**Those who left a mark.**\n\n"
            "A permanent collection of people whose contributions "
            "became part of the journey of nanZ.\n\n"
            "This is not a leaderboard and not a competition. "
            "Every name here represents a chapter worth remembering.",
            self.PURPLE,
        )
        await self.brand(e, guild)

        e.add_field(name="PEOPLE REMEMBERED", value=f"`{total}`", inline=True)
        e.add_field(name="ARCHIVE", value="`PERMANENT`", inline=True)
        e.add_field(name="IDENTITY", value="`NANZ SERVER`", inline=True)
        e.add_field(
            name="RECOGNITION",
            value=(
                "Foundation • Leadership • Community • Creative\n"
                "Event • Development • Special Recognition"
            ),
            inline=False,
        )
        e.add_field(
            name="EXPLORE",
            value="Gunakan tombol di bawah untuk melihat nama dan legacy "
                  "yang telah diabadikan.",
            inline=False,
        )
        return e

    async def list_embed(self, guild, page):
        total, rows = self.all(page)
        pages = max(1, math.ceil(total / self.PAGE_SIZE))
        e = self.embed(
            "🏛️  HALL OF TIME",
            "*People who became part of the nanZ story.*",
            self.BLUE,
        )
        await self.brand(e, guild)

        if not rows:
            e.description = "Belum ada nama yang diabadikan di Hall of Time."
        else:
            blocks = []
            for i, row in enumerate(rows, page * self.PAGE_SIZE + 1):
                member = await self.get_member(guild, row["user_id"])
                name = member.display_name if member else f"User {row['user_id']}"
                blocks.append(
                    f"**{i:02d}  {discord.utils.escape_markdown(name)}**\n"
                    f"`{row['recognition']}`  •  `{self.year_range(row['era_start'], row['era_end'])}`"
                )
            e.description = "\n\n".join(blocks)

        e.set_footer(text=f"nanZ Server • Hall of Time • Page {page + 1}/{pages}")
        return e

    async def entry_embed(self, guild, user_id):
        row = self.get(user_id)
        if not row:
            return self.embed("HALL OF TIME", "Entry tidak ditemukan.", self.SOFT)

        member = await self.get_member(guild, user_id)
        name = member.display_name if member else f"User {user_id}"
        mention = member.mention if member else f"<@{user_id}>"

        e = self.embed(
            "🏛️  HALL OF TIME",
            f"**{discord.utils.escape_markdown(name)}**\n{mention}\n\n"
            f"*{row['recognition']}*",
            self.PURPLE,
        )
        await self.brand(e, guild)

        if member:
            e.set_thumbnail(url=member.display_avatar.url)

        logo = await self.bot_logo(guild)
        if logo:
            e.set_image(url=logo)

        e.add_field(
            name="✦ ERA",
            value=f"`{self.year_range(row['era_start'], row['era_end'])}`",
            inline=True,
        )
        e.add_field(
            name="✦ RECOGNITION",
            value=f"`{row['recognition']}`",
            inline=True,
        )
        e.add_field(
            name="✦ CONTRIBUTION",
            value=row["contribution"],
            inline=False,
        )
        e.add_field(
            name="✦ LEGACY",
            value=row["legacy"],
            inline=False,
        )

        if row["quote"]:
            e.add_field(
                name="✦ A WORD TO REMEMBER",
                value=f"*“{row['quote']}”*",
                inline=False,
            )

        e.add_field(
            name="✦ RECOGNIZED",
            value=self.pretty_date(row["recognized_at"]),
            inline=True,
        )
        return e

    async def timeline_embed(self, guild):
        total, rows = self.all(0)
        # Keep within Discord embed limits while preserving oldest-to-newest order.
        rows = rows[:25]
        e = self.embed(
            "🕰️  HALL OF TIME — TIMELINE",
            "*The people and chapters that became part of nanZ.*",
            self.BLUE,
        )
        await self.brand(e, guild)

        if not rows:
            e.description = "Belum ada timeline."
            return e

        grouped = {}
        for row in rows:
            year = (row["era_start"] or "????")[:4]
            grouped.setdefault(year, []).append(row)

        blocks = []
        for year, year_rows in grouped.items():
            lines = [f"**{year}**"]
            for row in year_rows:
                member = await self.get_member(guild, row["user_id"])
                name = member.display_name if member else f"User {row['user_id']}"
                lines.append(
                    f"└ **{discord.utils.escape_markdown(name)}** — {row['recognition']}"
                )
            blocks.append("\n".join(lines))
        e.description = "\n\n".join(blocks)
        e.set_footer(text=f"nanZ Server • Hall of Time • {total} people remembered")
        return e

    # =========================================================
    # PANEL / ENTRY MESSAGES
    # =========================================================

    async def setup_panel(self):
        channel_id = int(self.get_setting("hall_channel_id", "0"))
        if not channel_id:
            print("[HALL OF TIME] Hall channel belum diset.")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                print(f"[HALL OF TIME] Gagal mengambil channel: {exc}")
                return

        panel_id = self.get_setting("panel_message_id")
        message = None
        if panel_id:
            try:
                message = await channel.fetch_message(int(panel_id))
            except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
                pass

        e = await self.home_embed(channel.guild)
        if message:
            await message.edit(embed=e, view=HallHomeView(self))
            return

        message = await channel.send(embed=e, view=HallHomeView(self))
        self.set_setting("panel_message_id", message.id)

    async def publish_entry(self, guild, user_id):
        row = self.get(user_id)
        if not row:
            return None

        channel_id = int(self.get_setting("hall_channel_id", "0"))
        if not channel_id:
            return None

        channel = self.bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return None

        if row["message_id"]:
            try:
                message = await channel.fetch_message(int(row["message_id"]))
                await message.edit(
                    embed=await self.entry_embed(guild, user_id),
                    view=HallEntryView(self, user_id),
                )
                return message
            except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
                pass

        message = await channel.send(
            embed=await self.entry_embed(guild, user_id),
            view=HallEntryView(self, user_id),
        )
        self.set_message(user_id, message.id)
        return message

    # =========================================================
    # READY / PERSISTENT VIEWS
    # =========================================================

    @commands.Cog.listener()
    async def on_ready(self):
        if self.ready_once:
            return
        self.ready_once = True

        self.bot.add_view(HallHomeView(self))
        self.bot.add_view(HallTimelineView(self))

        conn = self.connect()
        try:
            total = conn.execute("SELECT COUNT(*) n FROM honorees").fetchone()["n"]
            pages = max(1, math.ceil(total / self.PAGE_SIZE))
            rows = conn.execute("SELECT user_id FROM honorees").fetchall()
        finally:
            conn.close()

        for page in range(pages):
            self.bot.add_view(HallListView(self, page))
        for row in rows:
            self.bot.add_view(HallEntryView(self, row["user_id"]))

        await self.setup_panel()
        print("[HALL OF TIME] Sistem aktif.")

    # =========================================================
    # COMMANDS
    # =========================================================

    @commands.group(name="hall", invoke_without_command=True)
    async def hall(self, ctx):
        await ctx.send(
            embed=await self.home_embed(ctx.guild),
            view=HallHomeView(self),
        )

    @hall.command(name="setup")
    async def hall_setup(self, ctx):
        if not self.can_manage(ctx.author):
            return await ctx.send(
                "Kamu tidak memiliki izin mengelola Hall of Time.",
                delete_after=6,
            )

        self.set_setting("hall_channel_id", ctx.channel.id)
        self.set_setting("panel_message_id", "0")
        await self.setup_panel()
        await ctx.send(
            f"Hall of Time berhasil dipasang di {ctx.channel.mention}.",
            delete_after=8,
        )

    @hall.command(name="browse")
    async def hall_browse(self, ctx):
        await ctx.send(
            embed=await self.list_embed(ctx.guild, 0),
            view=HallListView(self, 0),
        )

    @hall.command(name="timeline")
    async def hall_timeline(self, ctx):
        await ctx.send(
            embed=await self.timeline_embed(ctx.guild),
            view=HallTimelineView(self),
        )

    @hall.command(name="view")
    async def hall_view(self, ctx, member: discord.Member):
        if not self.get(member.id):
            return await ctx.send(
                "Member tersebut belum memiliki entry di Hall of Time.",
                delete_after=6,
            )
        await ctx.send(
            embed=await self.entry_embed(ctx.guild, member.id),
            view=HallEntryView(self, member.id),
        )

    @hall.command(name="add")
    async def hall_add(self, ctx, member: discord.Member, *, data: str):
        """
        Format:
        !hall add @member | CATEGORY | ERA | Contribution | Legacy | Quote
        """
        if not self.can_manage(ctx.author):
            return await ctx.send(
                "Kamu tidak memiliki izin mengelola Hall of Time.",
                delete_after=6,
            )

        parts = [x.strip() for x in data.split("|")]
        if len(parts) < 5:
            return await ctx.send(
                "Format: `!hall add @member | CATEGORY | ERA | Contribution | Legacy | Quote`",
                delete_after=10,
            )

        recognition = parts[0].upper()
        era = parts[1]
        contribution = self.cut(parts[2], 1000)
        legacy = self.cut(parts[3], 1500)
        quote = self.cut(parts[4] if len(parts) > 4 else "", 500)

        if recognition not in self.CATEGORIES:
            return await ctx.send(
                "Kategori tidak valid. Pilihan: " + ", ".join(self.CATEGORIES),
                delete_after=10,
            )
        if not contribution or not legacy:
            return await ctx.send(
                "Contribution dan Legacy wajib diisi.",
                delete_after=6,
            )

        era_start, era_end = None, None
        if "—" in era:
            era_start, era_end = [x.strip() for x in era.split("—", 1)]
        elif "-" in era and era.count("-") == 1:
            era_start, era_end = [x.strip() for x in era.split("-", 1)]
        else:
            era_start = era or None

        self.save(
            member,
            recognition,
            era_start,
            era_end,
            contribution,
            legacy,
            quote,
        )
        await self.publish_entry(ctx.guild, member.id)

        await ctx.send(
            f"Entry Hall of Time untuk {member.mention} berhasil diabadikan.",
            delete_after=8,
        )

    @hall.command(name="event")
    async def hall_event(self, ctx, member: discord.Member, *, data: str):
        if not self.can_manage(ctx.author):
            return await ctx.send(
                "Kamu tidak memiliki izin mengelola Hall of Time.",
                delete_after=6,
            )
        if not self.get(member.id):
            return await ctx.send(
                "Member tersebut belum memiliki entry Hall of Time.",
                delete_after=6,
            )

        parts = [x.strip() for x in data.split("|", 1)]
        title = self.cut(parts[0], 100)
        description = self.cut(parts[1] if len(parts) > 1 else "", 1000)
        self.add_event(member.id, title, description)

        await ctx.send(
            f"Timeline {member.mention} berhasil ditambahkan.",
            delete_after=8,
        )

    @hall.command(name="remove")
    async def hall_remove(self, ctx, member: discord.Member):
        if not self.can_manage(ctx.author):
            return await ctx.send(
                "Kamu tidak memiliki izin mengelola Hall of Time.",
                delete_after=6,
            )

        row = self.get(member.id)
        if not row:
            return await ctx.send("Entry tidak ditemukan.", delete_after=6)

        channel_id = int(self.get_setting("hall_channel_id", "0"))
        channel = self.bot.get_channel(channel_id) if channel_id else None
        if channel and row["message_id"]:
            try:
                message = await channel.fetch_message(int(row["message_id"]))
                await message.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
                pass

        self.delete(member.id)
        await ctx.send(
            f"Entry Hall of Time {member.mention} telah dihapus.",
            delete_after=8,
        )

    @hall.command(name="refresh")
    async def hall_refresh(self, ctx):
        if not self.can_manage(ctx.author):
            return await ctx.send(
                "Kamu tidak memiliki izin mengelola Hall of Time.",
                delete_after=6,
            )

        await self.setup_panel()
        conn = self.connect()
        try:
            ids = [r["user_id"] for r in conn.execute("SELECT user_id FROM honorees")]
        finally:
            conn.close()

        for user_id in ids:
            await self.publish_entry(ctx.guild, user_id)

        await ctx.send("Hall of Time berhasil disinkronkan.", delete_after=8)

    @hall.error
    async def hall_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("Member tidak ditemukan. Gunakan mention atau user ID.", delete_after=6)
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Gunakan `!hall` untuk membuka Hall of Time.", delete_after=6)
            return
        raise error


# =============================================================
# PERSISTENT VIEWS
# =============================================================

class HallHomeView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.add_item(HallButton(cog, "browse", "Explore the Hall", discord.ButtonStyle.primary))
        self.add_item(HallButton(cog, "timeline", "Timeline", discord.ButtonStyle.secondary))


class HallButton(discord.ui.Button):
    def __init__(self, cog, action, label, style):
        super().__init__(
            label=label,
            style=style,
            custom_id=f"nanz:hall:home:{action}",
        )
        self.cog = cog
        self.action = action

    async def callback(self, interaction):
        if self.action == "browse":
            await interaction.response.edit_message(
                embed=await self.cog.list_embed(interaction.guild, 0),
                view=HallListView(self.cog, 0),
            )
        else:
            await interaction.response.edit_message(
                embed=await self.cog.timeline_embed(interaction.guild),
                view=HallTimelineView(self.cog),
            )


class HallListView(discord.ui.View):
    def __init__(self, cog, page):
        super().__init__(timeout=None)
        self.cog = cog
        self.page = page
        self.add_item(HallListButton(cog, "prev", max(0, page - 1), "‹", discord.ButtonStyle.secondary))
        self.add_item(HallListButton(cog, "home", 0, "Hall", discord.ButtonStyle.primary))
        self.add_item(HallListButton(cog, "next", page + 1, "›", discord.ButtonStyle.secondary))


class HallListButton(discord.ui.Button):
    def __init__(self, cog, action, page, label, style):
        super().__init__(
            label=label,
            style=style,
            custom_id=f"nanz:hall:list:{action}:{page}",
        )
        self.cog = cog
        self.action = action
        self.page = page

    async def callback(self, interaction):
        if self.action == "home":
            await interaction.response.edit_message(
                embed=await self.cog.home_embed(interaction.guild),
                view=HallHomeView(self.cog),
            )
            return

        total, _ = self.cog.all(0)
        pages = max(1, math.ceil(total / self.cog.PAGE_SIZE))
        page = min(max(self.page, 0), pages - 1)
        await interaction.response.edit_message(
            embed=await self.cog.list_embed(interaction.guild, page),
            view=HallListView(self.cog, page),
        )


class HallTimelineView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.add_item(HallTimelineBackButton(cog))


class HallTimelineBackButton(discord.ui.Button):
    def __init__(self, cog):
        super().__init__(
            label="Hall",
            style=discord.ButtonStyle.primary,
            custom_id="nanz:hall:timeline:back",
        )
        self.cog = cog

    async def callback(self, interaction):
        await interaction.response.edit_message(
            embed=await self.cog.home_embed(interaction.guild),
            view=HallHomeView(self.cog),
        )


class HallEntryView(discord.ui.View):
    def __init__(self, cog, user_id):
        super().__init__(timeout=None)
        self.add_item(HallEntryBackButton(cog, user_id))


class HallEntryBackButton(discord.ui.Button):
    def __init__(self, cog, user_id):
        super().__init__(
            label="Hall",
            style=discord.ButtonStyle.primary,
            custom_id=f"nanz:hall:entry:back:{user_id}",
        )
        self.cog = cog

    async def callback(self, interaction):
        await interaction.response.edit_message(
            embed=await self.cog.home_embed(interaction.guild),
            view=HallHomeView(self.cog),
        )


async def setup(bot):
    await bot.add_cog(HallOfTime(bot))
