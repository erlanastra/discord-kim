
import os
import sqlite3
import discord

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from discord.ext import commands, tasks

# =====================================================
# CONFIG
# =====================================================

WIB = ZoneInfo("Asia/Jakarta")
DB_DIR = "database"
DB_PATH = os.path.join(DB_DIR, "nanz_tasks.db")

MANAGEMENT_ROLE_ID = 1518251907867611216

DIVISIONS = {
    "Management": 1518251907867611216,
    "Event": 1518253280042684616,
    "Media": 1518253063633240074,
    "Creative": 1518252033965162529,
    "Gaming": 1518251534616629258,
    "Engagement": 1518252236134809681,
    "Development": 1518252153414746153,
}

STATUSES = {
    "active": "🟡 Aktif",
    "completed": "🟢 Selesai",
    "cancelled": "🔴 Dibatalkan",
}

PRIORITIES = {
    "low": "🟢 Rendah",
    "normal": "🟡 Normal",
    "high": "🟠 Tinggi",
    "urgent": "🔴 Mendesak",
}


# =====================================================
# TIME
# =====================================================

def now_wib():
    return datetime.now(WIB)


def parse_deadline(value):
    if not value or not value.strip():
        return None

    try:
        result = datetime.strptime(
            value.strip(),
            "%d-%m-%Y %H:%M"
        ).replace(tzinfo=WIB)

        if result <= now_wib():
            return None

        return result
    except ValueError:
        return None


def read_datetime(value):
    if not value:
        return None

    try:
        result = datetime.fromisoformat(value)

        if result.tzinfo is None:
            result = result.replace(tzinfo=WIB)

        return result.astimezone(WIB)
    except (ValueError, TypeError):
        return None


def format_time(value):
    result = read_datetime(value)

    if not result:
        return "Tidak ada deadline"

    return result.strftime("%d-%m-%Y pukul %H:%M WIB")


# =====================================================
# DATABASE
# =====================================================

class TaskDB:
    def __init__(self):
        os.makedirs(DB_DIR, exist_ok=True)
        self.initialize()

    def connect(self):
        db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        return db

    def initialize(self):
        with self.connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    division TEXT NOT NULL,
                    creator_id INTEGER NOT NULL,
                    priority TEXT DEFAULT 'normal',
                    deadline TEXT,
                    status TEXT DEFAULT 'active',
                    progress INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    cancelled_at TEXT,
                    reminder_sent INTEGER DEFAULT 0,
                    overdue_sent INTEGER DEFAULT 0
                )
            """)

            db.execute("""
                CREATE TABLE IF NOT EXISTS task_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            db.execute("""
                CREATE TABLE IF NOT EXISTS task_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

    def log(self, task_id, user_id, action, details=""):
        with self.connect() as db:
            db.execute("""
                INSERT INTO task_logs
                (task_id, user_id, action, details, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                task_id,
                user_id,
                action,
                details,
                now_wib().isoformat()
            ))

    def create(self, title, description, division, user_id, priority, deadline):
        now = now_wib().isoformat()

        with self.connect() as db:
            cursor = db.execute("""
                INSERT INTO tasks (
                    title, description, division, creator_id,
                    priority, deadline, status, progress,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'active', 0, ?, ?)
            """, (
                title,
                description,
                division,
                user_id,
                priority,
                deadline.isoformat() if deadline else None,
                now,
                now
            ))

            task_id = cursor.lastrowid

        self.log(task_id, user_id, "created", f"Tugas dibuat untuk {division}")
        return task_id

    def get(self, task_id):
        with self.connect() as db:
            return db.execute(
                "SELECT * FROM tasks WHERE id = ?",
                (task_id,)
            ).fetchone()

    def list(self, division=None, status="active", limit=25):
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []

        if division:
            query += " AND division = ?"
            params.append(division)

        if status != "all":
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self.connect() as db:
            return db.execute(query, params).fetchall()

    def progress(self, task_id, user_id, value, note=""):
        with self.connect() as db:
            db.execute("""
                UPDATE tasks
                SET progress = ?, updated_at = ?
                WHERE id = ?
            """, (value, now_wib().isoformat(), task_id))

        self.log(task_id, user_id, "progress", f"Progres {value}%. {note}".strip())

    def complete(self, task_id, user_id):
        now = now_wib().isoformat()

        with self.connect() as db:
            db.execute("""
                UPDATE tasks
                SET status = 'completed',
                    progress = 100,
                    completed_at = ?,
                    updated_at = ?
                WHERE id = ?
            """, (now, now, task_id))

        self.log(task_id, user_id, "completed", "Tugas diselesaikan")

    def cancel(self, task_id, user_id, reason=""):
        now = now_wib().isoformat()

        with self.connect() as db:
            db.execute("""
                UPDATE tasks
                SET status = 'cancelled',
                    cancelled_at = ?,
                    updated_at = ?
                WHERE id = ?
            """, (now, now, task_id))

        self.log(task_id, user_id, "cancelled", reason or "Tugas dibatalkan")

    def logs(self, task_id):
        with self.connect() as db:
            return db.execute("""
                SELECT * FROM task_logs
                WHERE task_id = ?
                ORDER BY created_at DESC
                LIMIT 15
            """, (task_id,)).fetchall()

    def stats(self, division=None):
        query = """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
            FROM tasks
        """
        params = []

        if division:
            query += " WHERE division = ?"
            params.append(division)

        with self.connect() as db:
            return db.execute(query, params).fetchone()

    def deadline_tasks(self):
        with self.connect() as db:
            return db.execute("""
                SELECT * FROM tasks
                WHERE status = 'active'
                  AND deadline IS NOT NULL
            """).fetchall()

    def mark_reminder(self, task_id, overdue=False):
        column = "overdue_sent" if overdue else "reminder_sent"

        with self.connect() as db:
            db.execute(
                f"UPDATE tasks SET {column} = 1 WHERE id = ?",
                (task_id,)
            )

    def set_panel_channel(self, channel_id):
        with self.connect() as db:
            db.execute("""
                INSERT OR REPLACE INTO task_settings (key, value)
                VALUES ('panel_channel', ?)
            """, (str(channel_id),))

    def get_panel_channel(self):
        with self.connect() as db:
            row = db.execute("""
                SELECT value FROM task_settings
                WHERE key = 'panel_channel'
            """).fetchone()

        return int(row["value"]) if row else None


# =====================================================
# PERMISSION
# =====================================================

def is_management(member):
    return any(role.id == MANAGEMENT_ROLE_ID for role in member.roles)


def member_division(member):
    for name, role_id in DIVISIONS.items():
        if any(role.id == role_id for role in member.roles):
            return name
    return None


def can_view(member, task):
    if is_management(member):
        return True

    return member_division(member) == task["division"]


def can_cancel(member, task):
    return (
        is_management(member)
        or member.id == task["creator_id"]
    )


def task_embed(task):
    embed = discord.Embed(
        title=f"📋 Tugas #{task['id']} — {task['title']}",
        description=task["description"] or "Tidak ada deskripsi.",
        color=discord.Color.blurple()
    )

    embed.add_field(name="Divisi", value=task["division"], inline=True)
    embed.add_field(
        name="Status",
        value=STATUSES.get(task["status"], task["status"]),
        inline=True
    )
    embed.add_field(
        name="Prioritas",
        value=PRIORITIES.get(task["priority"], task["priority"]),
        inline=True
    )
    embed.add_field(name="Progres", value=f"{task['progress']}%", inline=True)
    embed.add_field(
        name="Deadline",
        value=format_time(task["deadline"]),
        inline=True
    )
    embed.add_field(
        name="Pembuat",
        value=f"<@{task['creator_id']}>",
        inline=True
    )

    return embed


# =====================================================
# MODAL
# =====================================================

class CreateTaskModal(discord.ui.Modal):
    def __init__(self, cog, division):
        super().__init__(title=f"Buat Tugas — {division}")
        self.cog = cog
        self.division = division

        self.title_input = discord.ui.TextInput(
            label="Nama Tugas",
            placeholder="Contoh: Persiapan event mingguan",
            max_length=100
        )

        self.description_input = discord.ui.TextInput(
            label="Deskripsi",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )

        self.deadline_input = discord.ui.TextInput(
            label="Deadline WIB (DD-MM-YYYY HH:MM)",
            placeholder="05-10-2026 20:30",
            required=False,
            max_length=16
        )

        self.priority_input = discord.ui.TextInput(
            label="Prioritas",
            placeholder="normal",
            default="normal",
            max_length=10
        )

        self.add_item(self.title_input)
        self.add_item(self.description_input)
        self.add_item(self.deadline_input)
        self.add_item(self.priority_input)

    async def on_submit(self, interaction):
        priority_map = {
            "rendah": "low",
            "normal": "normal",
            "tinggi": "high",
            "mendesak": "urgent"
        }

        priority = priority_map.get(self.priority_input.value.lower().strip())

        if not priority:
            return await interaction.response.send_message(
                "❌ Prioritas harus rendah, normal, tinggi, atau mendesak.",
                ephemeral=True
            )

        deadline_text = self.deadline_input.value.strip()
        deadline = None

        if deadline_text:
            deadline = parse_deadline(deadline_text)

            if deadline is None:
                return await interaction.response.send_message(
                    "❌ Deadline tidak valid atau sudah lewat. "
                    "Gunakan format `DD-MM-YYYY HH:MM` WIB.",
                    ephemeral=True
                )

        task_id = self.cog.db.create(
            self.title_input.value.strip(),
            self.description_input.value.strip(),
            self.division,
            interaction.user.id,
            priority,
            deadline
        )

        task = self.cog.db.get(task_id)

        await interaction.response.send_message(
            "✅ Tugas berhasil dibuat.",
            embed=task_embed(task),
            view=TaskDetailView(self.cog, task_id),
            ephemeral=True
        )


class ProgressModal(discord.ui.Modal):
    def __init__(self, cog, task_id):
        super().__init__(title=f"Update Progres #{task_id}")
        self.cog = cog
        self.task_id = task_id

        self.value_input = discord.ui.TextInput(
            label="Progres (0–100)",
            placeholder="Contoh: 50",
            max_length=3
        )

        self.note_input = discord.ui.TextInput(
            label="Catatan",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )

        self.add_item(self.value_input)
        self.add_item(self.note_input)

    async def on_submit(self, interaction):
        task = self.cog.db.get(self.task_id)

        if not task or not can_view(interaction.user, task):
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki akses ke tugas ini.",
                ephemeral=True
            )

        if task["status"] != "active":
            return await interaction.response.send_message(
                "❌ Tugas ini sudah tidak aktif.",
                ephemeral=True
            )

        try:
            value = int(self.value_input.value)
            if not 0 <= value <= 100:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "❌ Progres harus berupa angka 0 sampai 100.",
                ephemeral=True
            )

        self.cog.db.progress(
            self.task_id,
            interaction.user.id,
            value,
            self.note_input.value.strip()
        )

        await interaction.response.send_message(
            f"📈 Progres diperbarui menjadi **{value}%**.",
            ephemeral=True
        )


# =====================================================
# DROPDOWN DIVISI
# =====================================================

class DivisionSelect(discord.ui.Select):
    def __init__(self, cog, divisions):
        self.cog = cog

        options = [
            discord.SelectOption(label=name, value=name)
            for name in divisions
        ]

        super().__init__(
            placeholder="Pilih divisi",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction):
        division = self.values[0]

        if not is_management(interaction.user):
            if member_division(interaction.user) != division:
                return await interaction.response.send_message(
                    "❌ Kamu tidak memiliki akses ke divisi tersebut.",
                    ephemeral=True
                )

        await interaction.response.send_modal(
            CreateTaskModal(self.cog, division)
        )


class DivisionSelectView(discord.ui.View):
    def __init__(self, cog, divisions):
        super().__init__(timeout=120)
        self.add_item(DivisionSelect(cog, divisions))


# =====================================================
# FILTER STATUS
# =====================================================

class StatusSelect(discord.ui.Select):
    def __init__(self, cog):
        self.cog = cog

        options = [
            discord.SelectOption(label="Aktif", value="active", emoji="🟡"),
            discord.SelectOption(label="Selesai", value="completed", emoji="🟢"),
            discord.SelectOption(label="Dibatalkan", value="cancelled", emoji="🔴"),
            discord.SelectOption(label="Semua Status", value="all", emoji="📚")
        ]

        super().__init__(
            placeholder="Filter status tugas",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction):
        await show_task_list(
            interaction,
            self.cog,
            self.values[0]
        )


class StatusSelectView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=180)
        self.add_item(StatusSelect(cog))


# =====================================================
# PILIH TUGAS
# =====================================================

class TaskSelect(discord.ui.Select):
    def __init__(self, cog, tasks):
        self.cog = cog

        options = [
            discord.SelectOption(
                label=f"#{task['id']} {task['title']}"[:100],
                value=str(task["id"]),
                description=(
                    f"{task['division']} • {task['progress']}% • "
                    f"{task['status']}"
                )[:100]
            )
            for task in tasks
        ]

        super().__init__(
            placeholder="Pilih tugas untuk melihat detail",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction):
        task_id = int(self.values[0])
        task = self.cog.db.get(task_id)

        if not task or not can_view(interaction.user, task):
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki akses ke tugas ini.",
                ephemeral=True
            )

        await interaction.response.send_message(
            embed=task_embed(task),
            view=TaskDetailView(self.cog, task_id),
            ephemeral=True
        )


class TaskSelectView(discord.ui.View):
    def __init__(self, cog, tasks):
        super().__init__(timeout=180)
        self.add_item(TaskSelect(cog, tasks))


# =====================================================
# RIWAYAT
# =====================================================

class HistorySelect(discord.ui.Select):
    def __init__(self, cog, tasks):
        self.cog = cog

        options = [
            discord.SelectOption(
                label=f"#{task['id']} {task['title']}"[:100],
                value=str(task["id"])
            )
            for task in tasks
        ]

        super().__init__(
            placeholder="Pilih tugas untuk melihat riwayat",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction):
        task_id = int(self.values[0])
        task = self.cog.db.get(task_id)

        if not task or not can_view(interaction.user, task):
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki akses ke tugas ini.",
                ephemeral=True
            )

        logs = self.cog.db.logs(task_id)

        embed = discord.Embed(
            title=f"📜 Riwayat Tugas #{task_id}",
            color=discord.Color.blurple()
        )

        if not logs:
            embed.description = "Belum ada riwayat."
        else:
            for log in logs:
                timestamp = format_time(log["created_at"])
                embed.add_field(
                    name=f"{log['action'].upper()} — {timestamp}",
                    value=(
                        f"Oleh: <@{log['user_id']}>\n"
                        f"{log['details'] or '-'}"
                    ),
                    inline=False
                )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


class HistorySelectView(discord.ui.View):
    def __init__(self, cog, tasks):
        super().__init__(timeout=180)
        self.add_item(HistorySelect(cog, tasks))


# =====================================================
# DETAIL TUGAS DAN TOMBOL AKSI
# =====================================================

class TaskDetailView(discord.ui.View):
    def __init__(self, cog, task_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.task_id = task_id

    async def get_task(self, interaction):
        task = self.cog.db.get(self.task_id)

        if not task:
            await interaction.response.send_message(
                "❌ Tugas tidak ditemukan.",
                ephemeral=True
            )
            return None

        if not can_view(interaction.user, task):
            await interaction.response.send_message(
                "❌ Kamu tidak memiliki akses ke tugas ini.",
                ephemeral=True
            )
            return None

        return task

    @discord.ui.button(
        label="Update Progres",
        emoji="📈",
        style=discord.ButtonStyle.primary
    )
    async def progress_button(self, interaction, button):
        task = await self.get_task(interaction)

        if not task:
            return

        if task["status"] != "active":
            return await interaction.response.send_message(
                "❌ Tugas ini sudah tidak aktif.",
                ephemeral=True
            )

        await interaction.response.send_modal(
            ProgressModal(self.cog, self.task_id)
        )

    @discord.ui.button(
        label="Selesaikan",
        emoji="✅",
        style=discord.ButtonStyle.success
    )
    async def complete_button(self, interaction, button):
        task = await self.get_task(interaction)

        if not task:
            return

        if task["status"] != "active":
            return await interaction.response.send_message(
                "❌ Tugas ini sudah tidak aktif.",
                ephemeral=True
            )

        self.cog.db.complete(self.task_id, interaction.user.id)

        await interaction.response.send_message(
            "✅ Tugas berhasil diselesaikan.",
            ephemeral=True
        )

    @discord.ui.button(
        label="Batalkan",
        emoji="🗑️",
        style=discord.ButtonStyle.danger
    )
    async def cancel_button(self, interaction, button):
        task = await self.get_task(interaction)

        if not task:
            return

        if not can_cancel(interaction.user, task):
            return await interaction.response.send_message(
                "❌ Hanya pembuat tugas atau Management yang dapat membatalkan.",
                ephemeral=True
            )

        if task["status"] != "active":
            return await interaction.response.send_message(
                "❌ Tugas ini sudah tidak aktif.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Konfirmasi pembatalan tugas:",
            view=CancelConfirmView(self.cog, self.task_id),
            ephemeral=True
        )

    @discord.ui.button(
        label="Riwayat",
        emoji="📜",
        style=discord.ButtonStyle.secondary
    )
    async def history_button(self, interaction, button):
        task = await self.get_task(interaction)

        if not task:
            return

        logs = self.cog.db.logs(self.task_id)

        embed = discord.Embed(
            title=f"📜 Riwayat Tugas #{self.task_id}",
            color=discord.Color.blurple()
        )

        if not logs:
            embed.description = "Belum ada riwayat."
        else:
            for log in logs:
                embed.add_field(
                    name=f"{log['action'].upper()} — {format_time(log['created_at'])}",
                    value=(
                        f"Oleh: <@{log['user_id']}>\n"
                        f"{log['details'] or '-'}"
                    ),
                    inline=False
                )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


class CancelConfirmView(discord.ui.View):
    def __init__(self, cog, task_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.task_id = task_id

    @discord.ui.button(
        label="Ya, batalkan",
        style=discord.ButtonStyle.danger
    )
    async def confirm(self, interaction, button):
        task = self.cog.db.get(self.task_id)

        if not task or not can_view(interaction.user, task):
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki akses.",
                ephemeral=True
            )

        if not can_cancel(interaction.user, task):
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki izin membatalkan tugas ini.",
                ephemeral=True
            )

        if task["status"] != "active":
            return await interaction.response.send_message(
                "❌ Tugas sudah tidak aktif.",
                ephemeral=True
            )

        self.cog.db.cancel(
            self.task_id,
            interaction.user.id
        )

        await interaction.response.edit_message(
            content="🗑️ Tugas berhasil dibatalkan.",
            view=None
        )

    @discord.ui.button(
        label="Kembali",
        style=discord.ButtonStyle.secondary
    )
    async def back(self, interaction, button):
        await interaction.response.edit_message(
            content="Pembatalan dibatalkan.",
            view=None
        )


# =====================================================
# PANEL UTAMA
# =====================================================

class TaskPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Buat Tugas",
        emoji="➕",
        style=discord.ButtonStyle.success,
        custom_id="nanz_task:panel_create"
    )
    async def create_button(self, interaction, button):
        if is_management(interaction.user):
            divisions = list(DIVISIONS.keys())
        else:
            division = member_division(interaction.user)

            if not division:
                return await interaction.response.send_message(
                    "❌ Kamu tidak memiliki role divisi.",
                    ephemeral=True
                )

            divisions = [division]

        await interaction.response.send_message(
            "Pilih divisi tujuan tugas:",
            view=DivisionSelectView(self.cog, divisions),
            ephemeral=True
        )

    @discord.ui.button(
        label="Daftar Tugas",
        emoji="📋",
        style=discord.ButtonStyle.primary,
        custom_id="nanz_task:panel_list"
    )
    async def list_button(self, interaction, button):
        division = (
            None if is_management(interaction.user)
            else member_division(interaction.user)
        )

        if not division and not is_management(interaction.user):
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki akses divisi.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Pilih filter status tugas:",
            view=StatusSelectView(self.cog),
            ephemeral=True
        )

    @discord.ui.button(
        label="Statistik",
        emoji="📊",
        style=discord.ButtonStyle.secondary,
        custom_id="nanz_task:panel_stats"
    )
    async def stats_button(self, interaction, button):
        division = (
            None if is_management(interaction.user)
            else member_division(interaction.user)
        )

        if not division and not is_management(interaction.user):
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki akses divisi.",
                ephemeral=True
            )

        stats = self.cog.db.stats(division)

        embed = discord.Embed(
            title="📊 Statistik Task Manager",
            description=f"Divisi: **{division or 'Semua Divisi'}**",
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="Total",
            value=stats["total"] or 0,
            inline=True
        )
        embed.add_field(
            name="Aktif",
            value=stats["active"] or 0,
            inline=True
        )
        embed.add_field(
            name="Selesai",
            value=stats["completed"] or 0,
            inline=True
        )
        embed.add_field(
            name="Dibatalkan",
            value=stats["cancelled"] or 0,
            inline=True
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    @discord.ui.button(
        label="Riwayat Tugas",
        emoji="📜",
        style=discord.ButtonStyle.secondary,
        custom_id="nanz_task:panel_history"
    )
    async def history_button(self, interaction, button):
        division = (
            None if is_management(interaction.user)
            else member_division(interaction.user)
        )

        if not division and not is_management(interaction.user):
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki akses divisi.",
                ephemeral=True
            )

        tasks_list = self.cog.db.list(
            division=division,
            status="all",
            limit=25
        )

        if not tasks_list:
            return await interaction.response.send_message(
                "📭 Belum ada tugas.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Pilih tugas untuk melihat riwayat:",
            view=HistorySelectView(self.cog, tasks_list),
            ephemeral=True
        )


async def show_task_list(interaction, cog, status):
    division = (
        None if is_management(interaction.user)
        else member_division(interaction.user)
    )

    if not division and not is_management(interaction.user):
        return await interaction.response.send_message(
            "❌ Kamu tidak memiliki akses divisi.",
            ephemeral=True
        )

    tasks_list = cog.db.list(
        division=division,
        status=status,
        limit=25
    )

    if not tasks_list:
        return await interaction.response.send_message(
            "📭 Tidak ada tugas untuk filter tersebut.",
            ephemeral=True
        )

    await interaction.response.send_message(
        f"Menampilkan **{len(tasks_list)}** tugas — status: **{status}**.\n"
        "Pilih salah satu tugas:",
        view=TaskSelectView(cog, tasks_list),
        ephemeral=True
    )


# =====================================================
# COG
# =====================================================

class NanzTask(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = TaskDB()
        self.deadline_checker.start()

    async def cog_load(self):
        self.bot.add_view(TaskPanelView(self))

    def cog_unload(self):
        self.deadline_checker.cancel()

    # Hanya command ini yang dipertahankan.
    @commands.command(name="taskpanel")
    async def taskpanel(self, ctx):
        if not is_management(ctx.author):
            return await ctx.send(
                "❌ Hanya Management yang dapat memasang panel Task Manager."
            )

        embed = discord.Embed(
            title="📋 NANZ Task Manager",
            description=(
                "Gunakan tombol di bawah untuk mengelola tugas.\n\n"
                "➕ **Buat Tugas**\n"
                "📋 **Daftar Tugas**\n"
                "📊 **Statistik**\n"
                "📜 **Riwayat Tugas**\n\n"
                "Deadline menggunakan **WIB (UTC+7)**."
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(text="NANZ Task Manager")

        await ctx.send(
            embed=embed,
            view=TaskPanelView(self)
        )

    # -------------------------------------------------
    # PENGINGAT DEADLINE
    # -------------------------------------------------

    @tasks.loop(minutes=1)
    async def deadline_checker(self):
        now = now_wib()
        reminder_limit = now + timedelta(hours=1)

        channel_id = self.db.get_panel_channel()
        if not channel_id:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        for task in self.db.deadline_tasks():
            deadline = read_datetime(task["deadline"])

            if not deadline:
                continue

            if deadline <= now and not task["overdue_sent"]:
                await channel.send(
                    f"⚠️ **Deadline terlewat!**\n"
                    f"Tugas: **#{task['id']} — {task['title']}**\n"
                    f"Divisi: **{task['division']}**\n"
                    f"Deadline: **{format_time(task['deadline'])}**"
                )

                self.db.mark_reminder(task["id"], overdue=True)
                continue

            if (
                now < deadline <= reminder_limit
                and not task["reminder_sent"]
            ):
                role_id = DIVISIONS.get(task["division"])

                await channel.send(
                    f"⏰ **Pengingat deadline tugas**\n"
                    f"Divisi: <@&{role_id}>\n"
                    f"Tugas: **#{task['id']} — {task['title']}**\n"
                    f"Deadline: **{format_time(task['deadline'])}**\n"
                    f"Progres: **{task['progress']}%**",
                    allowed_mentions=discord.AllowedMentions(
                        roles=True,
                        users=False,
                        everyone=False
                    )
                )

                self.db.mark_reminder(task["id"])

    @deadline_checker.before_loop
    async def before_deadline_checker(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(NanzTask(bot))