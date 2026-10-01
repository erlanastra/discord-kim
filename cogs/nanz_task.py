import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, timezone
import sqlite3
import os
import asyncio

# =========================================================
# KONFIGURASI
# =========================================================

WIB = timezone(timedelta(hours=7))

DB_PATH = "database/nanz_tasks.db"

MANAGEMENT_ROLE_ID = 1518251907867611216

DIVISIONS = {
    "Event": 1518253280042684616,
    "Media": 1518253063633240074,
    "Creative": 1518252033965162529,
    "Gaming": 1518251534616629258,
    "Engagement": 1518252236134809681,
    "Development": 1518252153414744741,
}

STATUS_LABELS = {
    "pending": "Belum dikerjakan",
    "progress": "Sedang dikerjakan",
    "completed": "Selesai",
    "cancelled": "Dibatalkan",
}

STATUS_EMOJIS = {
    "pending": "🟡",
    "progress": "🔵",
    "completed": "🟢",
    "cancelled": "🔴",
}


# =========================================================
# HELPER
# =========================================================

def now_wib():
    return datetime.now(WIB)


def parse_deadline(value: str):
    try:
        return datetime.strptime(
            value.strip(), "%d-%m-%Y %H:%M"
        ).replace(tzinfo=WIB)
    except ValueError:
        return None


def format_datetime(value):
    if not value:
        return "-"

    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=WIB)
        return dt.astimezone(WIB).strftime("%d-%m-%Y %H:%M WIB")
    except (ValueError, TypeError):
        return str(value)


def is_management(member: discord.Member):
    return (
        member.guild_permissions.administrator
        or any(role.id == MANAGEMENT_ROLE_ID for role in member.roles)
    )


def get_member_division(member: discord.Member):
    for division, role_id in DIVISIONS.items():
        if any(role.id == role_id for role in member.roles):
            return division
    return None


def can_access_task(member: discord.Member, task):
    if is_management(member):
        return True

    return get_member_division(member) == task["division"]


def make_embed(title, description=None, color=discord.Color.blurple()):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=now_wib()
    )
    embed.set_footer(text="NANZ Task Manager")
    return embed


# =========================================================
# DATABASE
# =========================================================

class TaskDB:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                division TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                creator_id INTEGER NOT NULL,
                deadline TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                progress INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                reminded INTEGER NOT NULL DEFAULT 0,
                overdue_notified INTEGER NOT NULL DEFAULT 0
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                guild_id INTEGER PRIMARY KEY,
                panel_channel_id INTEGER
            )
        """)

        self.conn.commit()

    def set_panel_channel(self, guild_id, channel_id):
        self.conn.execute("""
            INSERT INTO settings (guild_id, panel_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET panel_channel_id = excluded.panel_channel_id
        """, (guild_id, channel_id))
        self.conn.commit()

    def get_panel_channel(self, guild_id):
        row = self.conn.execute(
            "SELECT panel_channel_id FROM settings WHERE guild_id = ?",
            (guild_id,)
        ).fetchone()

        return row["panel_channel_id"] if row else None

    def create_task(
        self, guild_id, division, title, description,
        creator_id, deadline
    ):
        now = now_wib().isoformat()

        cursor = self.conn.execute("""
            INSERT INTO tasks (
                guild_id, division, title, description,
                creator_id, deadline, status, progress,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?)
        """, (
            guild_id,
            division,
            title,
            description,
            creator_id,
            deadline.isoformat(),
            now,
            now
        ))

        self.conn.commit()
        return cursor.lastrowid

    def get_task(self, task_id):
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()

        return dict(row) if row else None

    def get_tasks(self, guild_id, division=None, include_cancelled=False):
        query = "SELECT * FROM tasks WHERE guild_id = ?"
        params = [guild_id]

        if division:
            query += " AND division = ?"
            params.append(division)

        if not include_cancelled:
            query += " AND status != 'cancelled'"

        query += """
            ORDER BY
                CASE status
                    WHEN 'pending' THEN 1
                    WHEN 'progress' THEN 2
                    WHEN 'completed' THEN 3
                    WHEN 'cancelled' THEN 4
                END,
                deadline ASC
        """

        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def update_task(self, task_id, **fields):
        allowed = {"status", "progress", "reminded", "overdue_notified"}
        updates = {
            key: value for key, value in fields.items()
            if key in allowed
        }

        if not updates:
            return

        updates["updated_at"] = now_wib().isoformat()

        assignments = ", ".join(
            f"{key} = ?" for key in updates
        )

        values = list(updates.values())
        values.append(task_id)

        self.conn.execute(
            f"UPDATE tasks SET {assignments} WHERE id = ?",
            values
        )
        self.conn.commit()

    def delete_task(self, task_id):
        self.conn.execute(
            "UPDATE tasks SET status = 'cancelled', updated_at = ? WHERE id = ?",
            (now_wib().isoformat(), task_id)
        )
        self.conn.commit()

    def get_due_tasks(self, guild_id):
        rows = self.conn.execute("""
            SELECT * FROM tasks
            WHERE guild_id = ?
            AND status IN ('pending', 'progress')
        """, (guild_id,)).fetchall()

        return [dict(row) for row in rows]

    def get_statistics(self, guild_id, division=None):
        query = """
            SELECT status, COUNT(*) AS total
            FROM tasks
            WHERE guild_id = ?
        """
        params = [guild_id]

        if division:
            query += " AND division = ?"
            params.append(division)

        query += " GROUP BY status"

        rows = self.conn.execute(query, params).fetchall()
        result = {status: 0 for status in STATUS_LABELS}

        for row in rows:
            result[row["status"]] = row["total"]

        return result


# =========================================================
# MODAL PEMBUATAN TUGAS
# =========================================================

class CreateTaskModal(discord.ui.Modal, title="Buat Tugas Baru"):
    title_input = discord.ui.TextInput(
        label="Judul Tugas",
        placeholder="Contoh: Membuat desain poster event",
        max_length=100,
        required=True
    )

    description_input = discord.ui.TextInput(
        label="Deskripsi Tugas",
        placeholder="Jelaskan detail tugas...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True
    )

    deadline_input = discord.ui.TextInput(
        label="Deadline (DD-MM-YYYY HH:MM WIB)",
        placeholder="Contoh: 25-10-2026 20:00",
        max_length=16,
        required=True
    )

    def __init__(self, cog, division):
        super().__init__()
        self.cog = cog
        self.division = division

    async def on_submit(self, interaction: discord.Interaction):
        deadline = parse_deadline(self.deadline_input.value)

        if deadline is None:
            return await interaction.response.send_message(
                "❌ Format deadline tidak valid.\n"
                "Gunakan format `DD-MM-YYYY HH:MM`, contoh `25-10-2026 20:00`.",
                ephemeral=True
            )

        if deadline <= now_wib():
            return await interaction.response.send_message(
                "❌ Deadline harus berada di waktu mendatang.",
                ephemeral=True
            )

        task_id = self.cog.db.create_task(
            guild_id=interaction.guild_id,
            division=self.division,
            title=self.title_input.value,
            description=self.description_input.value,
            creator_id=interaction.user.id,
            deadline=deadline
        )

        embed = make_embed(
            "✅ Tugas Berhasil Dibuat",
            f"Tugas **#{task_id}** berhasil ditambahkan ke divisi **{self.division}**.",
            discord.Color.green()
        )

        embed.add_field(name="Judul", value=self.title_input.value, inline=False)
        embed.add_field(
            name="Deadline",
            value=format_datetime(deadline.isoformat()),
            inline=False
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# =========================================================
# MODAL PROGRES TUGAS
# =========================================================

class ProgressModal(discord.ui.Modal, title="Perbarui Progres"):
    progress_input = discord.ui.TextInput(
        label="Progres (0-100)",
        placeholder="Contoh: 50",
        max_length=3,
        required=True
    )

    def __init__(self, cog, task_id):
        super().__init__()
        self.cog = cog
        self.task_id = task_id

    async def on_submit(self, interaction: discord.Interaction):
        task = self.cog.db.get_task(self.task_id)

        if not task or not can_access_task(interaction.user, task):
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki akses ke tugas ini.",
                ephemeral=True
            )

        try:
            progress = int(self.progress_input.value)
            if not 0 <= progress <= 100:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "❌ Progres harus berupa angka dari 0 sampai 100.",
                ephemeral=True
            )

        status = "completed" if progress == 100 else "progress"
        self.cog.db.update_task(
            self.task_id,
            progress=progress,
            status=status
        )

        await interaction.response.send_message(
            f"✅ Progres tugas **#{self.task_id}** diperbarui menjadi **{progress}%**.",
            ephemeral=True
        )


# =========================================================
# SELECT DIVISI
# =========================================================

class DivisionSelect(discord.ui.Select):
    def __init__(self, cog):
        self.cog = cog

        options = [
            discord.SelectOption(
                label=division,
                value=division,
                description=f"Buat tugas untuk divisi {division}"
            )
            for division in DIVISIONS
        ]

        super().__init__(
            placeholder="Pilih divisi tujuan...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="nanz_task:division_select"
        )

    async def callback(self, interaction: discord.Interaction):
        division = self.values[0]

        if not is_management(interaction.user):
            member_division = get_member_division(interaction.user)

            if member_division != division:
                return await interaction.response.send_message(
                    "❌ Kamu hanya dapat membuat tugas untuk divisi sendiri.",
                    ephemeral=True
                )

        await interaction.response.send_modal(
            CreateTaskModal(self.cog, division)
        )


class DivisionSelectView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=180)
        self.add_item(DivisionSelect(cog))


# =========================================================
# SELECT TUGAS
# =========================================================

class TaskSelect(discord.ui.Select):
    def __init__(self, cog, tasks_list, action):
        self.cog = cog
        self.action = action

        options = []
        for task in tasks_list[:25]:
            label = f"#{task['id']} - {task['title']}"
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=str(task["id"]),
                    description=(
                        f"{task['division']} | "
                        f"{STATUS_LABELS.get(task['status'], task['status'])}"
                    )[:100]
                )
            )

        super().__init__(
            placeholder="Pilih tugas...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        task_id = int(self.values[0])
        task = self.cog.db.get_task(task_id)

        if not task or not can_access_task(interaction.user, task):
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki akses ke tugas ini.",
                ephemeral=True
            )

        if self.action == "progress":
            return await interaction.response.send_modal(
                ProgressModal(self.cog, task_id)
            )

        if self.action == "complete":
            self.cog.db.update_task(
                task_id,
                status="completed",
                progress=100
            )
            return await interaction.response.send_message(
                f"✅ Tugas **#{task_id}** ditandai selesai.",
                ephemeral=True
            )

        if self.action == "cancel":
            if not (
                is_management(interaction.user)
                or task["creator_id"] == interaction.user.id
            ):
                return await interaction.response.send_message(
                    "❌ Hanya pembuat tugas atau Management yang dapat membatalkan tugas.",
                    ephemeral=True
                )

            self.cog.db.delete_task(task_id)
            return await interaction.response.send_message(
                f"🗑️ Tugas **#{task_id}** berhasil dibatalkan.",
                ephemeral=True
            )


class TaskSelectView(discord.ui.View):
    def __init__(self, cog, tasks_list, action):
        super().__init__(timeout=180)
        self.add_item(TaskSelect(cog, tasks_list, action))


# =========================================================
# PANEL UTAMA
# =========================================================

class TaskPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def get_visible_tasks(self, interaction):
        division = None

        if not is_management(interaction.user):
            division = get_member_division(interaction.user)

            if not division:
                return None

        return self.cog.db.get_tasks(
            interaction.guild_id,
            division=division
        )

    @discord.ui.button(
        label="Buat Tugas",
        emoji="➕",
        style=discord.ButtonStyle.success,
        custom_id="nanz_task:create"
    )
    async def create_task(self, interaction, button):
        if not is_management(interaction.user) and not get_member_division(interaction.user):
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki role divisi yang terdaftar.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Pilih divisi untuk tugas yang akan dibuat:",
            view=DivisionSelectView(self.cog),
            ephemeral=True
        )

    @discord.ui.button(
        label="Daftar Tugas",
        emoji="📋",
        style=discord.ButtonStyle.primary,
        custom_id="nanz_task:list"
    )
    async def list_tasks(self, interaction, button):
        tasks_list = await self.get_visible_tasks(interaction)

        if tasks_list is None:
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki akses ke Task Manager.",
                ephemeral=True
            )

        if not tasks_list:
            return await interaction.response.send_message(
                "Belum ada tugas yang tersedia.",
                ephemeral=True
            )

        embed = make_embed("📋 Daftar Tugas")
        for task in tasks_list[:10]:
            embed.add_field(
                name=f"#{task['id']} — {task['title']}",
                value=(
                    f"**Divisi:** {task['division']}\n"
                    f"**Status:** {STATUS_EMOJIS.get(task['status'], '')} "
                    f"{STATUS_LABELS.get(task['status'], task['status'])}\n"
                    f"**Progres:** {task['progress']}%\n"
                    f"**Deadline:** {format_datetime(task['deadline'])}"
                ),
                inline=False
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    @discord.ui.button(
        label="Update Progres",
        emoji="📈",
        style=discord.ButtonStyle.secondary,
        custom_id="nanz_task:progress"
    )
    async def update_progress(self, interaction, button):
        tasks_list = await self.get_visible_tasks(interaction)

        if tasks_list is None:
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki akses ke Task Manager.",
                ephemeral=True
            )

        available = [
            task for task in tasks_list
            if task["status"] in ("pending", "progress")
        ]

        if not available:
            return await interaction.response.send_message(
                "Tidak ada tugas yang bisa diperbarui.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Pilih tugas yang ingin diperbarui:",
            view=TaskSelectView(self.cog, available, "progress"),
            ephemeral=True
        )

    @discord.ui.button(
        label="Tandai Selesai",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="nanz_task:complete"
    )
    async def complete_task(self, interaction, button):
        tasks_list = await self.get_visible_tasks(interaction)

        if tasks_list is None:
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki akses ke Task Manager.",
                ephemeral=True
            )

        available = [
            task for task in tasks_list
            if task["status"] in ("pending", "progress")
        ]

        if not available:
            return await interaction.response.send_message(
                "Tidak ada tugas aktif yang bisa diselesaikan.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Pilih tugas yang sudah selesai:",
            view=TaskSelectView(self.cog, available, "complete"),
            ephemeral=True
        )

    @discord.ui.button(
        label="Batalkan Tugas",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="nanz_task:cancel"
    )
    async def cancel_task(self, interaction, button):
        tasks_list = await self.get_visible_tasks(interaction)

        if tasks_list is None:
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki akses ke Task Manager.",
                ephemeral=True
            )

        available = [
            task for task in tasks_list
            if task["status"] in ("pending", "progress")
            and (
                is_management(interaction.user)
                or task["creator_id"] == interaction.user.id
            )
        ]

        if not available:
            return await interaction.response.send_message(
                "Tidak ada tugas yang dapat kamu batalkan.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Pilih tugas yang ingin dibatalkan:",
            view=TaskSelectView(self.cog, available, "cancel"),
            ephemeral=True
        )

    @discord.ui.button(
        label="Statistik",
        emoji="📊",
        style=discord.ButtonStyle.secondary,
        custom_id="nanz_task:stats"
    )
    async def statistics(self, interaction, button):
        division = None

        if not is_management(interaction.user):
            division = get_member_division(interaction.user)

            if not division:
                return await interaction.response.send_message(
                    "❌ Kamu tidak memiliki akses ke Task Manager.",
                    ephemeral=True
                )

        stats = self.cog.db.get_statistics(
            interaction.guild_id,
            division=division
        )

        total = sum(stats.values())
        description = (
            f"🟡 Belum dikerjakan: **{stats['pending']}**\n"
            f"🔵 Sedang dikerjakan: **{stats['progress']}**\n"
            f"🟢 Selesai: **{stats['completed']}**\n"
            f"🔴 Dibatalkan: **{stats['cancelled']}**\n\n"
            f"**Total tugas: {total}**"
        )

        title = "📊 Statistik Task Manager"
        if division:
            title += f" — {division}"

        await interaction.response.send_message(
            embed=make_embed(title, description),
            ephemeral=True
        )


# =========================================================
# COG
# =========================================================

class NanzTask(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = TaskDB()
        self.deadline_checker.start()

    def cog_unload(self):
        self.deadline_checker.cancel()
        self.db.conn.close()

    @commands.command(name="taskpanel")
    @commands.guild_only()
    async def taskpanel(self, ctx):
        if not is_management(ctx.author):
            return await ctx.reply(
                "❌ Hanya Management yang dapat memasang panel Task Manager.",
                mention_author=False
            )

        self.db.set_panel_channel(ctx.guild.id, ctx.channel.id)

        embed = make_embed(
            "📌 NANZ TASK MANAGER",
            (
                "Gunakan tombol di bawah untuk mengelola tugas divisi.\n\n"
                "➕ **Buat Tugas** — Membuat tugas baru.\n"
                "📋 **Daftar Tugas** — Melihat tugas sesuai akses.\n"
                "📈 **Update Progres** — Memperbarui progres tugas.\n"
                "✅ **Tandai Selesai** — Menyelesaikan tugas.\n"
                "🗑️ **Batalkan Tugas** — Membatalkan tugas.\n"
                "📊 **Statistik** — Melihat ringkasan tugas.\n\n"
                "Deadline menggunakan zona waktu **WIB (UTC+7)**."
            ),
            discord.Color.blurple()
        )

        await ctx.send(
            embed=embed,
            view=TaskPanelView(self)
        )

    @tasks.loop(minutes=1)
    async def deadline_checker(self):
        await self.bot.wait_until_ready()

        for guild in self.bot.guilds:
            channel_id = self.db.get_panel_channel(guild.id)

            if not channel_id:
                continue

            channel = guild.get_channel(channel_id)
            if not channel:
                continue

            for task in self.db.get_due_tasks(guild.id):
                try:
                    deadline = datetime.fromisoformat(task["deadline"])

                    if deadline.tzinfo is None:
                        deadline = deadline.replace(tzinfo=WIB)

                    current = now_wib()
                    remaining = deadline - current

                    # Notifikasi 24 jam sebelum deadline
                    if (
                        timedelta(0) < remaining <= timedelta(hours=24)
                        and not task["reminded"]
                    ):
                        division_role_id = DIVISIONS.get(task["division"])
                        mention = (
                            f"<@&{division_role_id}>"
                            if division_role_id else ""
                        )

                        embed = make_embed(
                            "⏰ Pengingat Deadline",
                            (
                                f"**Tugas:** #{task['id']} — {task['title']}\n"
                                f"**Divisi:** {task['division']}\n"
                                f"**Deadline:** {format_datetime(task['deadline'])}\n"
                                f"**Sisa waktu:** kurang dari 24 jam"
                            ),
                            discord.Color.orange()
                        )

                        await channel.send(
                            content=mention,
                            embed=embed,
                            allowed_mentions=discord.AllowedMentions(roles=True)
                        )

                        self.db.update_task(task["id"], reminded=1)

                    # Notifikasi ketika deadline terlewati
                    elif (
                        remaining <= timedelta(0)
                        and not task["overdue_notified"]
                    ):
                        division_role_id = DIVISIONS.get(task["division"])
                        mention = (
                            f"<@&{division_role_id}>"
                            if division_role_id else ""
                        )

                        embed = make_embed(
                            "🚨 Deadline Terlewati",
                            (
                                f"**Tugas:** #{task['id']} — {task['title']}\n"
                                f"**Divisi:** {task['division']}\n"
                                f"**Deadline:** {format_datetime(task['deadline'])}\n"
                                f"**Status:** {STATUS_LABELS.get(task['status'])}"
                            ),
                            discord.Color.red()
                        )

                        await channel.send(
                            content=mention,
                            embed=embed,
                            allowed_mentions=discord.AllowedMentions(roles=True)
                        )

                        self.db.update_task(
                            task["id"],
                            overdue_notified=1
                        )

                except Exception as error:
                    print(
                        f"[NANZ TASK] Error deadline tugas "
                        f"#{task.get('id')}: {error}"
                    )

    @deadline_checker.before_loop
    async def before_deadline_checker(self):
        await self.bot.wait_until_ready()


# =========================================================
# SETUP
# =========================================================

async def setup(bot):
    await bot.add_cog(NanzTask(bot))
    bot.add_view(TaskPanelView(bot.get_cog("NanzTask")))