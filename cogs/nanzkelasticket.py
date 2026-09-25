import asyncio
import io
import json
import logging
import re
from datetime import datetime, timedelta, timezone

import aiohttp
import aiomysql
import discord
from discord.ext import commands


# =========================================================
# CONFIG
# =========================================================

APPROVAL_CHANNEL_ID = 1552604897201881148
DAFTAR_KELAS_CHANNEL_ID = 1552604329435856986
REQUEST_GABUNG_CHANNEL_ID = 1552604968643731546
# Isi dengan ID channel log-kelas jika ingin logging ke channel.
# None = logging channel dinonaktifkan.
LOG_KELAS_CHANNEL_ID = None
RUANG_KELAS_CATEGORY_ID = 1552603909606875216
PEMBATAS_ROLE_ID = 1453246187636396032

MAX_MEMBER = 20

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "nanzuser",
    "password": "nanzserversolid",
    "db": "nanz_bot",
    "autocommit": True,
}


# =========================================================
# LOGGING
# =========================================================

log = logging.getLogger("nanz.kelas.ticket")


# =========================================================
# HELPERS
# =========================================================

def utc_now():
    return datetime.now(timezone.utc)


def db_now():
    """
    MariaDB DATETIME disimpan sebagai naive UTC.
    """
    return utc_now().replace(tzinfo=None)


def db_dt(value):
    """
    Konversi DATETIME MariaDB menjadi aware UTC.
    """
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def valid_hex(value):
    return bool(re.fullmatch(r"#[0-9A-Fa-f]{6}", value.strip()))


def clean_text(value, max_length):
    value = (value or "").strip()
    return value[:max_length]


async def get_db():
    return await aiomysql.connect(**DB_CONFIG)


async def fetch_one(query, args=()):
    conn = await get_db()

    try:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(query, args)
            return await cur.fetchone()
    finally:
        conn.close()


async def fetch_all(query, args=()):
    conn = await get_db()

    try:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(query, args)
            return await cur.fetchall()
    finally:
        conn.close()


async def execute(query, args=()):
    conn = await get_db()

    try:
        async with conn.cursor() as cur:
            await cur.execute(query, args)
            return cur.lastrowid
    finally:
        conn.close()


async def execute_many(query, rows):
    conn = await get_db()

    try:
        async with conn.cursor() as cur:
            await cur.executemany(query, rows)
    finally:
        conn.close()


async def send_log(bot, guild, message):
    """
    Logging sederhana ke channel log-kelas.
    ID channel dapat menggunakan LOG_KELAS_CHANNEL_ID
    dari admin cog jika tersedia.
    """
    channel_id = getattr(bot, "LOG_KELAS_CHANNEL_ID", None)

    if not channel_id:
        return

    channel = guild.get_channel(channel_id)

    if channel:
        try:
            await channel.send(message)
        except Exception:
            log.exception("Gagal mengirim log kelas.")


# =========================================================
# CLASS CARD
# =========================================================

async def load_logo(url):
    if not url:
        return None

    try:
        timeout = aiohttp.ClientTimeout(total=8)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return None

                data = await response.read()

        from PIL import Image

        image = Image.open(io.BytesIO(data))
        image = image.convert("RGBA")
        image.thumbnail((150, 150))

        return image

    except Exception:
        log.exception("Gagal mengambil logo kelas.")
        return None


def hex_rgb(value):
    value = value.lstrip("#")

    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return (52, 152, 219)


async def generate_class_card(
    *,
    class_name,
    motto,
    description,
    color_hex,
    logo_url,
    staff_name,
    member_count,
    status,
    created_at,
    due_date,
):
    """
    Panel PNG final Kelas nanZ.

    Layout:
    - accent line
    - logo
    - nama kelas
    - motto
    - deskripsi
    - Staff Pendamping
    - Siswa
    - Status
    - Berdiri Sejak
    - Aktif Sampai
    - Slot
    """

    from PIL import Image, ImageDraw, ImageFont

    WIDTH = 1200
    HEIGHT = 650

    bg = (18, 20, 27)
    card = (25, 28, 37)
    white = (240, 242, 245)
    muted = (165, 170, 180)

    accent = hex_rgb(color_hex)

    image = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(image)

    # -----------------------------------------------------
    # FONT
    # -----------------------------------------------------

    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]

    regular_path = font_candidates[0]
    bold_path = font_candidates[1]

    try:
        title_font = ImageFont.truetype(bold_path, 42)
        motto_font = ImageFont.truetype(regular_path, 24)
        text_font = ImageFont.truetype(regular_path, 21)
        label_font = ImageFont.truetype(bold_path, 18)
        small_font = ImageFont.truetype(regular_path, 17)
        status_font = ImageFont.truetype(bold_path, 19)
    except Exception:
        title_font = ImageFont.load_default()
        motto_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        label_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
        status_font = ImageFont.load_default()

    # -----------------------------------------------------
    # CARD
    # -----------------------------------------------------

    draw.rounded_rectangle(
        (25, 25, WIDTH - 25, HEIGHT - 25),
        radius=28,
        fill=card,
    )

    # Accent line
    draw.rounded_rectangle(
        (25, 25, WIDTH - 25, 37),
        radius=6,
        fill=accent,
    )

    # -----------------------------------------------------
    # LOGO
    # -----------------------------------------------------

    logo = await load_logo(logo_url)

    logo_x = 70
    logo_y = 75
    logo_size = 150

    draw.rounded_rectangle(
        (
            logo_x - 5,
            logo_y - 5,
            logo_x + logo_size + 5,
            logo_y + logo_size + 5,
        ),
        radius=25,
        fill=accent,
    )

    if logo:
        logo.thumbnail((logo_size, logo_size))

        lx = logo_x + (logo_size - logo.width) // 2
        ly = logo_y + (logo_size - logo.height) // 2

        image.paste(
            logo,
            (lx, ly),
            logo,
        )
    else:
        # fallback
        draw.text(
            (
                logo_x + logo_size // 2,
                logo_y + logo_size // 2,
            ),
            "nZ",
            fill=white,
            font=title_font,
            anchor="mm",
        )

    # -----------------------------------------------------
    # HEADER
    # -----------------------------------------------------

    text_x = 270

    draw.text(
        (text_x, 75),
        class_name,
        fill=white,
        font=title_font,
    )

    draw.text(
        (text_x, 130),
        motto or "-",
        fill=accent,
        font=motto_font,
    )

    # Description
    desc = description or "-"

    words = desc.split()
    lines = []
    current = ""

    for word in words:
        test = (current + " " + word).strip()

        if draw.textlength(test, font=text_font) <= 800:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    lines = lines[:2]

    for index, line in enumerate(lines):
        draw.text(
            (text_x, 180 + index * 28),
            line,
            fill=muted,
            font=text_font,
        )

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    status_map = {
        "Active": "ACTIVE",
        "Grace": "GRACE",
        "Inactive": "INACTIVE",
        "Dissolved": "DIBUBARKAN",
    }

    status_text = status_map.get(status, status.upper())

    draw.rounded_rectangle(
        (950, 80, 1125, 125),
        radius=20,
        fill=accent,
    )

    draw.text(
        (1037, 102),
        status_text,
        fill=white,
        font=status_font,
        anchor="mm",
    )

    # -----------------------------------------------------
    # INFO
    # -----------------------------------------------------

    info_y = 290

    info = [
        ("Staff Pendamping", staff_name or "-"),
        ("Siswa", f"{member_count}/{MAX_MEMBER}"),
        (
            "Berdiri Sejak",
            created_at.astimezone(timezone.utc).strftime("%d %b %Y")
            if created_at
            else "-",
        ),
        (
            "Aktif Sampai",
            due_date.astimezone(timezone.utc).strftime("%d %b %Y")
            if due_date
            else "-",
        ),
    ]

    for index, (label, value) in enumerate(info):
        col = index % 2
        row = index // 2

        x = 70 + col * 550
        y = info_y + row * 90

        draw.text(
            (x, y),
            label.upper(),
            fill=muted,
            font=label_font,
        )

        draw.text(
            (x, y + 30),
            value,
            fill=white,
            font=text_font,
        )

    # -----------------------------------------------------
    # SLOT BAR
    # -----------------------------------------------------

    bar_x = 70
    bar_y = 480
    bar_width = 1060
    bar_height = 18

    draw.rounded_rectangle(
        (
            bar_x,
            bar_y,
            bar_x + bar_width,
            bar_y + bar_height,
        ),
        radius=9,
        fill=(55, 58, 68),
    )

    ratio = min(member_count / MAX_MEMBER, 1)

    if ratio > 0:
        draw.rounded_rectangle(
            (
                bar_x,
                bar_y,
                bar_x + int(bar_width * ratio),
                bar_y + bar_height,
            ),
            radius=9,
            fill=accent,
        )

    if member_count >= MAX_MEMBER:
        slot_text = "PENUH"
    else:
        slot_text = f"{MAX_MEMBER - member_count} slot tersisa"

    draw.text(
        (70, 515),
        slot_text,
        fill=muted,
        font=small_font,
    )

    # -----------------------------------------------------
    # FOOTER
    # -----------------------------------------------------

    draw.text(
        (70, 585),
        "Berbeda Kelas, Tetap Satu Sekolah.",
        fill=muted,
        font=small_font,
    )

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG",
        optimize=True,
    )

    buffer.seek(0)

    return buffer


# =========================================================
# DATA HELPERS
# =========================================================

async def get_class(class_id):
    return await fetch_one(
        """
        SELECT *
        FROM nanz_classes
        WHERE class_id=%s
        LIMIT 1
        """,
        (class_id,),
    )


async def get_member_count(class_id):
    row = await fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM nanz_class_members
        WHERE class_id=%s
        """,
        (class_id,),
    )

    return int(row["total"]) if row else 0


async def get_user_class(user_id):
    return await fetch_one(
        """
        SELECT c.*
        FROM nanz_class_members m
        JOIN nanz_classes c
            ON c.class_id = m.class_id
        WHERE m.user_id=%s
        LIMIT 1
        """,
        (user_id,),
    )


async def update_public_panel(bot, class_id):
    cls = await get_class(class_id)

    if not cls:
        return

    channel = bot.get_channel(DAFTAR_KELAS_CHANNEL_ID)

    if not channel:
        return

    member_count = await get_member_count(class_id)

    staff = bot.get_user(int(cls["staff_id"]))

    staff_name = staff.display_name if staff else f"<@{cls['staff_id']}>"

    created_at = db_dt(cls["created_at"])
    due_date = db_dt(cls["due_date"])

    image = await generate_class_card(
        class_name=cls["name"],
        motto=cls["motto"],
        description=cls["description"],
        color_hex=cls["color_hex"],
        logo_url=cls["logo_url"],
        staff_name=staff_name,
        member_count=member_count,
        status=cls["status"],
        created_at=created_at,
        due_date=due_date,
    )

    view = ClassPublicPanel(class_id)

    file = discord.File(
        image,
        filename=f"class_{class_id}.png",
    )

    if cls["panel_message_id"]:
        try:
            message = await channel.fetch_message(
                int(cls["panel_message_id"])
            )

            await message.edit(
                content=None,
                attachments=[file],
                view=view,
            )

            return

        except discord.NotFound:
            pass
        except discord.HTTPException:
            log.exception("Gagal update panel kelas.")

    message = await channel.send(
        file=file,
        view=view,
    )

    await execute(
        """
        UPDATE nanz_classes
        SET panel_message_id=%s
        WHERE class_id=%s
        """,
        (
            str(message.id),
            class_id,
        ),
    )


# =========================================================
# PERMISSION HELPERS
# =========================================================

STAFF_ROLE_ID = 1515023431815528468


def is_admin(member: discord.Member) -> bool:
    return bool(member and member.guild_permissions.administrator)


def has_staff_role(member: discord.Member) -> bool:
    if not member:
        return False

    if is_admin(member):
        return True

    return any(role.id == STAFF_ROLE_ID for role in member.roles)


def can_manage_class(member: discord.Member, cls) -> bool:
    if not member or not cls:
        return False

    if is_admin(member):
        return True

    if not has_staff_role(member):
        return False

    return member.id == int(cls["staff_id"] or 0)


def can_process_join(member: discord.Member, request) -> bool:
    if not member or not request:
        return False

    if is_admin(member):
        return True

    return member.id in {
        int(request["owner_id"] or 0),
        int(request["staff_id"] or 0),
    }


def is_valid_staff(member: discord.Member) -> bool:
    return bool(member and has_staff_role(member))


# =========================================================
# CLASS CREATION MODAL
# =========================================================

class ClassCreationModal(discord.ui.Modal):
    def __init__(self, owner_id):
        super().__init__(title="Buat Kelas nanZ", timeout=600)

        self.owner_id = int(owner_id)

        self.name_input = discord.ui.TextInput(
            label="Nama Kelas",
            placeholder="Contoh: XI Informatika",
            max_length=50,
            required=True,
        )

        self.motto_input = discord.ui.TextInput(
            label="Motto Kelas",
            placeholder="Contoh: Code, Chill, Connect.",
            max_length=100,
            required=False,
        )

        self.description_input = discord.ui.TextInput(
            label="Deskripsi",
            placeholder="Jelaskan singkat kelas kamu.",
            max_length=300,
            style=discord.TextStyle.paragraph,
            required=True,
        )

        self.color_input = discord.ui.TextInput(
            label="Warna Kelas",
            placeholder="#5865F2",
            default="#3498DB",
            max_length=7,
            required=True,
        )

        self.logo_input = discord.ui.TextInput(
            label="URL Logo",
            placeholder="https://...",
            max_length=500,
            required=False,
        )

        for item in (
            self.name_input,
            self.motto_input,
            self.description_input,
            self.color_input,
            self.logo_input,
        ):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        name = clean_text(self.name_input.value, 50)
        motto = clean_text(self.motto_input.value, 100) or "-"
        description = clean_text(self.description_input.value, 300)
        color_hex = clean_text(self.color_input.value, 7).upper()
        logo_url = clean_text(self.logo_input.value, 500) or None

        if not valid_hex(color_hex):
            await interaction.response.send_message(
                "❌ Format warna tidak valid. Gunakan `#5865F2`.",
                ephemeral=True,
            )
            return

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Form ini hanya dapat digunakan di server.",
                ephemeral=True,
            )
            return

        if not interaction.user:
            return

        existing = await get_user_class(self.owner_id)
        if existing:
            await interaction.response.send_message(
                f"❌ Kamu sudah tergabung di **{existing['name']}**.\n"
                "Satu member hanya boleh memiliki satu kelas.",
                ephemeral=True,
            )
            return

        pending = await fetch_one(
            """
            SELECT request_id
            FROM nanz_class_creation_requests
            WHERE owner_id=%s
              AND status='Pending'
            LIMIT 1
            """,
            (self.owner_id,),
        )

        if pending:
            await interaction.response.send_message(
                "❌ Kamu masih memiliki pengajuan kelas yang sedang diproses.",
                ephemeral=True,
            )
            return

        approval_channel = interaction.guild.get_channel(APPROVAL_CHANNEL_ID)
        if not approval_channel:
            await interaction.response.send_message(
                "❌ Channel `approval-kelas` tidak ditemukan.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # staff_id menggunakan 0 sebagai sentinel "belum dipilih".
        # Ini menjaga kompatibilitas dengan schema lama yang sudah memiliki
        # kolom staff_id tanpa membutuhkan migrasi tabel.
        request_id = await execute(
            """
            INSERT INTO nanz_class_creation_requests
            (
                guild_id,
                owner_id,
                staff_id,
                name,
                motto,
                description,
                color_hex,
                logo_url,
                status,
                created_at
            )
            VALUES
            (
                %s,%s,0,%s,%s,%s,%s,%s,'Pending',%s
            )
            """,
            (
                interaction.guild.id,
                self.owner_id,
                name,
                motto,
                description,
                color_hex,
                logo_url,
                db_now(),
            ),
        )

        embed = build_creation_request_embed(
            request_id=request_id,
            request={
                "name": name,
                "motto": motto,
                "description": description,
                "color_hex": color_hex,
                "logo_url": logo_url,
                "owner_id": self.owner_id,
                "staff_id": 0,
            },
        )

        try:
            await approval_channel.send(
                embed=embed,
                view=ClassApprovalView(request_id),
            )
        except Exception:
            log.exception("Gagal mengirim approval kelas.")
            await execute(
                "DELETE FROM nanz_class_creation_requests WHERE request_id=%s",
                (request_id,),
            )
            await interaction.followup.send(
                "❌ Gagal mengirim pengajuan ke `approval-kelas`.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            "✅ Pengajuan kelas berhasil dikirim ke `approval-kelas`.\n"
            "Staff akan memilih Staff Pendamping terlebih dahulu sebelum kelas dapat disetujui.",
            ephemeral=True,
        )


def build_creation_request_embed(request_id, request):
    staff_id = int(request.get("staff_id") or 0)

    embed = discord.Embed(
        title="🏫 Pengajuan Kelas Baru",
        description="Pengajuan menunggu pemilihan Staff Pendamping dan persetujuan Staff/Administrator.",
        color=discord.Color.from_str(request["color_hex"]),
        timestamp=utc_now(),
    )

    embed.add_field(name="Nama Kelas", value=request["name"], inline=False)
    embed.add_field(name="Motto", value=request["motto"], inline=False)
    embed.add_field(name="Deskripsi", value=request["description"], inline=False)
    embed.add_field(name="Pemilik", value=f"<@{request['owner_id']}>", inline=True)
    embed.add_field(
        name="Staff Pendamping",
        value=f"<@{staff_id}>" if staff_id else "⚠️ Belum dipilih",
        inline=True,
    )
    embed.add_field(name="Request ID", value=f"`{request_id}`", inline=True)

    if request.get("logo_url"):
        embed.set_thumbnail(url=request["logo_url"])

    return embed


# =========================================================
# FORM TRIGGER
# =========================================================

class ClassFormTriggerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        button = discord.ui.Button(
            label="Buka Form Kelas",
            emoji="🏫",
            style=discord.ButtonStyle.primary,
            custom_id="nanz:open_class_form",
        )
        button.callback = self.open_form
        self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction):
        if not has_staff_role(interaction.user):
            await interaction.response.send_message(
                "🔒 Panel pembuatan kelas hanya dapat digunakan Staff atau Administrator.",
                ephemeral=True,
            )
            return False
        return True

    async def open_form(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            ClassCreationModal(owner_id=interaction.user.id)
        )


# =========================================================
# STAFF DASHBOARD
# =========================================================

class StaffDashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        self.class_select = discord.ui.ChannelSelect(
            channel_types=[discord.ChannelType.voice],
            placeholder="Pilih Voice Channel kelas untuk dikelola...",
            min_values=1,
            max_values=1,
            custom_id="nanz:staff_dashboard:class_select",
        )
        self.class_select.callback = self.select_class
        self.add_item(self.class_select)

        refresh = discord.ui.Button(
            label="Refresh",
            emoji="🔄",
            style=discord.ButtonStyle.secondary,
            custom_id="nanz:staff_dashboard:refresh",
        )
        refresh.callback = self.refresh_dashboard
        self.add_item(refresh)

    async def interaction_check(self, interaction):
        if not has_staff_role(interaction.user):
            await interaction.response.send_message(
                "🔒 Dashboard ini khusus Staff dan Administrator.",
                ephemeral=True,
            )
            return False
        return True

    async def select_class(self, interaction):
        selected = self.class_select.values[0]
        channel_id = int(selected.id)

        cls = await fetch_one(
            """
            SELECT *
            FROM nanz_classes
            WHERE vc_id=%s
              AND status IN ('Active','Grace','Inactive')
            LIMIT 1
            """,
            (channel_id,),
        )

        if not cls:
            await interaction.response.send_message(
                "❌ Voice channel tersebut bukan Voice Channel kelas yang terdaftar.",
                ephemeral=True,
            )
            return

        if not can_manage_class(interaction.user, cls):
            await interaction.response.send_message(
                "🔒 Kamu hanya dapat mengelola kelas yang Staff Pendamping-nya adalah kamu. Administrator dapat mengakses semua kelas.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=await build_class_management_embed(interaction.client, cls["class_id"]),
            view=ClassManagementView(int(cls["class_id"])),
            ephemeral=True,
        )

    async def refresh_dashboard(self, interaction):
        await interaction.response.edit_message(
            embed=build_staff_dashboard_embed(),
            view=StaffDashboardView(),
        )


def build_staff_dashboard_embed():
    return discord.Embed(
        title="🛡️ Dashboard Staff Kelas",
        description=(
            "Panel pengelolaan Kelas nanZ.\n\n"
            "• Pilih Voice Channel kelas untuk membuka panel management.\n"
            "• Hanya Staff yang ditugaskan ke kelas tersebut atau Administrator yang dapat mengelola.\n"
            "• Approval member tetap dapat dilakukan oleh Owner, Staff Pendamping, atau Administrator melalui `request-gabung`."
        ),
        color=discord.Color.blurple(),
    )


# =========================================================
# CLASS APPROVAL VIEW
# =========================================================

class ClassApprovalView(discord.ui.View):
    def __init__(self, request_id):
        super().__init__(timeout=None)
        self.request_id = int(request_id)

        self.staff_select = discord.ui.UserSelect(
            placeholder="Pilih Staff Pendamping...",
            min_values=1,
            max_values=1,
            custom_id=f"nanz:class_staff_select:{self.request_id}",
        )
        self.staff_select.callback = self.select_staff
        self.add_item(self.staff_select)

        approve = discord.ui.Button(
            label="Approve Kelas",
            emoji="✅",
            style=discord.ButtonStyle.success,
            custom_id=f"nanz:class_approve:{self.request_id}",
        )
        approve.callback = self.approve
        self.add_item(approve)

        reject = discord.ui.Button(
            label="Reject Kelas",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            custom_id=f"nanz:class_reject:{self.request_id}",
        )
        reject.callback = self.reject
        self.add_item(reject)

    async def interaction_check(self, interaction):
        if not has_staff_role(interaction.user):
            await interaction.response.send_message(
                "🔒 Hanya Staff atau Administrator yang dapat memproses pengajuan kelas.",
                ephemeral=True,
            )
            return False
        return True

    async def get_request(self):
        return await fetch_one(
            """
            SELECT *
            FROM nanz_class_creation_requests
            WHERE request_id=%s
            LIMIT 1
            """,
            (self.request_id,),
        )

    async def select_staff(self, interaction):
        request = await self.get_request()
        if not request:
            await interaction.response.send_message("❌ Pengajuan tidak ditemukan.", ephemeral=True)
            return

        if request["status"] != "Pending":
            await interaction.response.send_message("❌ Pengajuan ini sudah diproses.", ephemeral=True)
            return

        selected = self.staff_select.values[0]
        staff_member = interaction.guild.get_member(int(selected.id))

        if not staff_member or not is_valid_staff(staff_member):
            await interaction.response.send_message(
                "❌ User yang dipilih tidak memiliki Role Staff yang sah.",
                ephemeral=True,
            )
            return

        await execute(
            """
            UPDATE nanz_class_creation_requests
            SET staff_id=%s
            WHERE request_id=%s
              AND status='Pending'
            """,
            (staff_member.id, self.request_id),
        )

        request["staff_id"] = staff_member.id

        await interaction.response.edit_message(
            embed=build_creation_request_embed(self.request_id, request),
            view=self,
        )

    async def approve(self, interaction):
        request = await self.get_request()

        if not request:
            await interaction.response.send_message("❌ Data pengajuan tidak ditemukan.", ephemeral=True)
            return

        if request["status"] != "Pending":
            await interaction.response.send_message(
                f"❌ Pengajuan ini sudah berstatus `{request['status']}`.",
                ephemeral=True,
            )
            return

        staff_id = int(request["staff_id"] or 0)
        if staff_id <= 0:
            await interaction.response.send_message(
                "⚠️ Pilih Staff Pendamping terlebih dahulu sebelum Approve.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        owner = guild.get_member(int(request["owner_id"]))
        staff = guild.get_member(staff_id)

        if not owner:
            await interaction.response.send_message(
                "❌ Pemilik kelas sudah tidak berada di server.",
                ephemeral=True,
            )
            return

        if not staff or not is_valid_staff(staff):
            await interaction.response.send_message(
                "❌ Staff Pendamping tidak valid atau sudah tidak memiliki Role Staff.",
                ephemeral=True,
            )
            return

        existing = await get_user_class(owner.id)
        if existing:
            await interaction.response.send_message(
                f"❌ Pemilik sudah memiliki kelas **{existing['name']}**.",
                ephemeral=True,
            )
            return

        category = guild.get_channel(RUANG_KELAS_CATEGORY_ID)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                "❌ Category ruang kelas tidak ditemukan.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        role = None
        voice = None
        class_id = None

        try:
            role = await guild.create_role(
                name=request["name"],
                color=discord.Color.from_str(request["color_hex"]),
                reason=f"Kelas nanZ #{self.request_id}",
            )

            separator = guild.get_role(PEMBATAS_ROLE_ID)
            if separator:
                try:
                    await role.edit(position=max(separator.position - 1, 1))
                except discord.HTTPException:
                    log.exception("Gagal mengatur posisi role kelas.")

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True,
                    send_messages=True,
                    read_message_history=True,
                ),
            }

            voice = await guild.create_voice_channel(
                request["name"],
                category=category,
                overwrites=overwrites,
                reason=f"Kelas nanZ #{self.request_id}",
            )

            now = db_now()
            due_date = now + timedelta(days=30)
            grace_until = due_date + timedelta(days=7)

            class_id = await execute(
                """
                INSERT INTO nanz_classes
                (
                    guild_id,
                    name,
                    motto,
                    description,
                    color_hex,
                    logo_url,
                    role_id,
                    vc_id,
                    staff_id,
                    owner_id,
                    created_at,
                    due_date,
                    grace_until,
                    status,
                    billing_status
                )
                VALUES
                (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,'Active','Unpaid'
                )
                """,
                (
                    guild.id,
                    request["name"],
                    request["motto"],
                    request["description"],
                    request["color_hex"],
                    request["logo_url"],
                    role.id,
                    voice.id,
                    staff_id,
                    request["owner_id"],
                    now,
                    due_date,
                    grace_until,
                ),
            )

            await execute(
                """
                INSERT INTO nanz_class_members
                (class_id,user_id,joined_at)
                VALUES (%s,%s,%s)
                """,
                (class_id, owner.id, now),
            )

            await owner.add_roles(role, reason="Menjadi anggota kelas nanZ")

            await execute(
                """
                UPDATE nanz_class_creation_requests
                SET status='Approved', processed_at=%s, processed_by=%s, class_id=%s
                WHERE request_id=%s
                """,
                (now, interaction.user.id, class_id, self.request_id),
            )

            await update_public_panel(interaction.client, class_id)

            try:
                await voice.send(
                    f"🏫 **{request['name']}** resmi berdiri!\n"
                    f"Staff Pendamping: <@{staff_id}>\n"
                    f"Pemilik: <@{request['owner_id']}>\n\n"
                    "**Berbeda Kelas, Tetap Satu Sekolah.**"
                )
            except Exception:
                pass

            embed = discord.Embed(
                title="🏫 Kelas Disetujui",
                color=discord.Color.green(),
                timestamp=utc_now(),
            )
            embed.add_field(name="Kelas", value=request["name"], inline=False)
            embed.add_field(name="Pemilik", value=f"<@{request['owner_id']}>", inline=True)
            embed.add_field(name="Staff Pendamping", value=f"<@{staff_id}>", inline=True)
            embed.add_field(name="Class ID", value=f"`{class_id}`", inline=True)

            await interaction.message.edit(embed=embed, view=None)

            await send_log(
                interaction.client,
                guild,
                f"🏫 Kelas **{request['name']}** dibuat oleh <@{interaction.user.id}>. "
                f"Staff: <@{staff_id}>. Class ID: `{class_id}`.",
            )

            await interaction.followup.send(
                f"✅ Kelas **{request['name']}** berhasil dibuat.",
                ephemeral=True,
            )

        except Exception as exc:
            log.exception("Gagal membuat kelas.")

            if voice:
                try:
                    await voice.delete(reason="Rollback pembuatan kelas")
                except Exception:
                    pass

            if role:
                try:
                    await role.delete(reason="Rollback pembuatan kelas")
                except Exception:
                    pass

            if class_id:
                try:
                    await execute("DELETE FROM nanz_classes WHERE class_id=%s", (class_id,))
                except Exception:
                    pass

            await interaction.followup.send(
                "❌ Gagal membuat kelas.\n"
                f"Error: `{type(exc).__name__}`",
                ephemeral=True,
            )

    async def reject(self, interaction):
        request = await self.get_request()
        if not request:
            await interaction.response.send_message("❌ Pengajuan tidak ditemukan.", ephemeral=True)
            return

        if request["status"] != "Pending":
            await interaction.response.send_message("❌ Pengajuan ini sudah diproses.", ephemeral=True)
            return

        await execute(
            """
            UPDATE nanz_class_creation_requests
            SET status='Rejected', processed_at=%s, processed_by=%s
            WHERE request_id=%s
            """,
            (db_now(), interaction.user.id, self.request_id),
        )

        embed = discord.Embed(
            title="❌ Pengajuan Kelas Ditolak",
            description=f"Pengajuan **{request['name']}** telah ditolak.",
            color=discord.Color.red(),
            timestamp=utc_now(),
        )
        embed.add_field(name="Pemohon", value=f"<@{request['owner_id']}>")
        embed.add_field(name="Diproses oleh", value=interaction.user.mention)

        await interaction.response.edit_message(embed=embed, view=None)

        await send_log(
            interaction.client,
            interaction.guild,
            f"❌ Pengajuan kelas **{request['name']}** ditolak oleh {interaction.user.mention}.",
        )


# =========================================================
# CLASS MANAGEMENT MODALS / VIEWS
# =========================================================

async def build_class_management_embed(bot, class_id):
    cls = await get_class(class_id)
    if not cls:
        return discord.Embed(
            title="❌ Kelas tidak ditemukan",
            color=discord.Color.red(),
        )

    count = await get_member_count(class_id)
    staff_id = int(cls["staff_id"] or 0)

    embed = discord.Embed(
        title=f"🛠️ Kelola Kelas — {cls['name']}",
        description=cls["description"] or "-",
        color=discord.Color.from_str(cls["color_hex"]),
    )
    embed.add_field(name="Owner", value=f"<@{cls['owner_id']}>", inline=True)
    embed.add_field(
        name="Staff",
        value=f"<@{staff_id}>" if staff_id else "-",
        inline=True,
    )
    embed.add_field(name="Anggota", value=f"{count}/{MAX_MEMBER}", inline=True)
    embed.add_field(name="Status", value=str(cls["status"]), inline=True)
    embed.add_field(name="Class ID", value=f"`{cls['class_id']}`", inline=True)

    return embed


class ClassEditModal(discord.ui.Modal):
    def __init__(self, class_id):
        super().__init__(title="Edit Informasi Kelas", timeout=300)
        self.class_id = int(class_id)

        cls = None
        # Discord Modal tidak boleh melakukan await di __init__, sehingga nilai
        # default diisi saat tombol memanggil modal melalui factory di bawah.
        self.name_input = discord.ui.TextInput(
            label="Nama Kelas",
            max_length=50,
            required=True,
        )
        self.motto_input = discord.ui.TextInput(
            label="Motto",
            max_length=100,
            required=False,
        )
        self.description_input = discord.ui.TextInput(
            label="Deskripsi",
            max_length=300,
            style=discord.TextStyle.paragraph,
            required=True,
        )
        self.color_input = discord.ui.TextInput(
            label="Warna Hex",
            max_length=7,
            required=True,
        )
        self.logo_input = discord.ui.TextInput(
            label="URL Logo",
            max_length=500,
            required=False,
        )

        for item in (
            self.name_input,
            self.motto_input,
            self.description_input,
            self.color_input,
            self.logo_input,
        ):
            self.add_item(item)

    @classmethod
    async def create(cls, class_id):
        self = cls(class_id)
        current = await get_class(class_id)
        if current:
            self.name_input.default = current["name"][:50]
            self.motto_input.default = (current["motto"] or "")[:100]
            self.description_input.default = (current["description"] or "")[:300]
            self.color_input.default = (current["color_hex"] or "#3498DB")[:7]
            self.logo_input.default = (current["logo_url"] or "")[:500]
        return self

    async def on_submit(self, interaction):
        cls = await get_class(self.class_id)
        if not cls or cls["status"] == "Dissolved":
            await interaction.response.send_message("❌ Kelas tidak tersedia.", ephemeral=True)
            return

        if not can_manage_class(interaction.user, cls):
            await interaction.response.send_message("🔒 Kamu tidak memiliki akses ke kelas ini.", ephemeral=True)
            return

        name = clean_text(self.name_input.value, 50)
        motto = clean_text(self.motto_input.value, 100) or "-"
        description = clean_text(self.description_input.value, 300)
        color_hex = clean_text(self.color_input.value, 7).upper()
        logo_url = clean_text(self.logo_input.value, 500) or None

        if not valid_hex(color_hex):
            await interaction.response.send_message("❌ Warna harus format `#RRGGBB`.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        await execute(
            """
            UPDATE nanz_classes
            SET name=%s, motto=%s, description=%s, color_hex=%s, logo_url=%s
            WHERE class_id=%s
            """,
            (name, motto, description, color_hex, logo_url, self.class_id),
        )

        role = interaction.guild.get_role(int(cls["role_id"]))
        if role:
            try:
                await role.edit(
                    name=name,
                    color=discord.Color.from_str(color_hex),
                    reason=f"Edit kelas {self.class_id}",
                )
            except discord.HTTPException:
                log.exception("Gagal memperbarui role kelas.")

        await update_public_panel(interaction.client, self.class_id)
        await send_log(
            interaction.client,
            interaction.guild,
            f"📝 Kelas **{name}** diperbarui oleh {interaction.user.mention}.",
        )

        await interaction.followup.send("✅ Informasi kelas berhasil diperbarui.", ephemeral=True)


class StaffChangeView(discord.ui.View):
    def __init__(self, class_id):
        super().__init__(timeout=300)
        self.class_id = int(class_id)
        self.staff_select = discord.ui.UserSelect(
            placeholder="Pilih Staff baru...",
            min_values=1,
            max_values=1,
            custom_id=f"nanz:change_staff:{self.class_id}",
        )
        self.staff_select.callback = self.change_staff
        self.add_item(self.staff_select)

    async def interaction_check(self, interaction):
        cls = await get_class(self.class_id)
        if not cls or not can_manage_class(interaction.user, cls):
            await interaction.response.send_message("🔒 Kamu tidak memiliki akses.", ephemeral=True)
            return False
        return True

    async def change_staff(self, interaction):
        selected = self.staff_select.values[0]
        staff = interaction.guild.get_member(int(selected.id))
        if not staff or not is_valid_staff(staff):
            await interaction.response.send_message(
                "❌ User yang dipilih bukan Staff yang valid.",
                ephemeral=True,
            )
            return

        cls = await get_class(self.class_id)
        if not cls or not can_manage_class(interaction.user, cls):
            await interaction.response.send_message("🔒 Akses ditolak.", ephemeral=True)
            return

        old_staff = int(cls["staff_id"] or 0)
        await execute(
            "UPDATE nanz_classes SET staff_id=%s WHERE class_id=%s",
            (staff.id, self.class_id),
        )

        await update_public_panel(interaction.client, self.class_id)
        await interaction.response.send_message(
            f"✅ Staff kelas diganti menjadi {staff.mention}.",
            ephemeral=True,
        )

        await send_log(
            interaction.client,
            interaction.guild,
            f"🧑‍💼 Staff kelas **{cls['name']}** diganti dari "
            f"<@{old_staff}> menjadi {staff.mention} oleh {interaction.user.mention}.",
        )


class ClassMemberManageView(discord.ui.View):
    def __init__(self, class_id):
        super().__init__(timeout=300)
        self.class_id = int(class_id)
        self.selected_user_id = None

        self.member_select = discord.ui.UserSelect(
            placeholder="Pilih anggota yang akan dikelola...",
            min_values=1,
            max_values=1,
            custom_id=f"nanz:member_manage:select:{self.class_id}",
        )
        self.member_select.callback = self.select_member
        self.add_item(self.member_select)

        kick = discord.ui.Button(
            label="Keluarkan",
            emoji="🚫",
            style=discord.ButtonStyle.danger,
            custom_id=f"nanz:member_manage:kick:{self.class_id}",
        )
        kick.callback = self.kick_selected
        self.add_item(kick)

    async def interaction_check(self, interaction):
        cls = await get_class(self.class_id)
        if not cls or not can_manage_class(interaction.user, cls):
            await interaction.response.send_message("🔒 Kamu tidak memiliki akses.", ephemeral=True)
            return False
        return True

    async def select_member(self, interaction):
        selected = self.member_select.values[0]
        self.selected_user_id = int(selected.id)
        await interaction.response.send_message(
            f"👤 Anggota terpilih: <@{self.selected_user_id}>\n"
            "Tekan **Keluarkan** untuk menghapusnya dari kelas.",
            ephemeral=True,
        )

    async def kick_selected(self, interaction):
        if not self.selected_user_id:
            await interaction.response.send_message("⚠️ Pilih anggota terlebih dahulu.", ephemeral=True)
            return

        cls = await get_class(self.class_id)
        if not cls or not can_manage_class(interaction.user, cls):
            await interaction.response.send_message("🔒 Akses ditolak.", ephemeral=True)
            return

        if self.selected_user_id == int(cls["owner_id"]):
            await interaction.response.send_message("❌ Owner kelas tidak dapat dikeluarkan.", ephemeral=True)
            return

        member_row = await fetch_one(
            "SELECT user_id FROM nanz_class_members WHERE class_id=%s AND user_id=%s LIMIT 1",
            (self.class_id, self.selected_user_id),
        )
        if not member_row:
            await interaction.response.send_message("❌ User bukan anggota kelas ini.", ephemeral=True)
            return

        await execute(
            "DELETE FROM nanz_class_members WHERE class_id=%s AND user_id=%s",
            (self.class_id, self.selected_user_id),
        )

        member = interaction.guild.get_member(self.selected_user_id)
        role = interaction.guild.get_role(int(cls["role_id"]))
        if member and role:
            try:
                await member.remove_roles(role, reason="Dikeluarkan dari kelas nanZ")
            except discord.HTTPException:
                log.exception("Gagal menghapus role kelas dari member.")

        await update_public_panel(interaction.client, self.class_id)
        await interaction.response.send_message(
            f"✅ <@{self.selected_user_id}> dikeluarkan dari **{cls['name']}**.",
            ephemeral=True,
        )

        await send_log(
            interaction.client,
            interaction.guild,
            f"🚫 <@{self.selected_user_id}> dikeluarkan dari **{cls['name']}** oleh {interaction.user.mention}.",
        )


class ClassDeleteConfirmView(discord.ui.View):
    def __init__(self, class_id):
        super().__init__(timeout=60)
        self.class_id = int(class_id)

        confirm = discord.ui.Button(
            label="Ya, Bubarkan",
            emoji="🗑️",
            style=discord.ButtonStyle.danger,
            custom_id=f"nanz:delete_confirm:{self.class_id}",
        )
        confirm.callback = self.confirm_delete
        self.add_item(confirm)

        cancel = discord.ui.Button(
            label="Batal",
            emoji="↩️",
            style=discord.ButtonStyle.secondary,
            custom_id=f"nanz:delete_cancel:{self.class_id}",
        )
        cancel.callback = self.cancel
        self.add_item(cancel)

    async def confirm_delete(self, interaction):
        cls = await get_class(self.class_id)
        if not cls or not can_manage_class(interaction.user, cls):
            await interaction.response.send_message("🔒 Akses ditolak.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await dissolve_class(interaction.client, interaction.guild, self.class_id, interaction.user.id)
        await interaction.followup.send(f"🗑️ Kelas **{cls['name']}** berhasil dibubarkan.", ephemeral=True)

    async def cancel(self, interaction):
        await interaction.response.edit_message(content="❌ Pembubaran dibatalkan.", view=None)


async def dissolve_class(bot, guild, class_id, actor_id):
    cls = await get_class(class_id)
    if not cls:
        return False

    # Tandai database lebih dulu agar panel/request tidak lagi dianggap aktif.
    await execute(
        "UPDATE nanz_classes SET status='Dissolved' WHERE class_id=%s",
        (class_id,),
    )

    await execute(
        """
        UPDATE nanz_class_join_requests
        SET status='Cancelled', processed_at=%s, processed_by=%s
        WHERE class_id=%s AND status='Pending'
        """,
        (db_now(), actor_id, class_id),
    )

    await execute("DELETE FROM nanz_class_members WHERE class_id=%s", (class_id,))

    channel = guild.get_channel(DAFTAR_KELAS_CHANNEL_ID)
    if channel and cls.get("panel_message_id"):
        try:
            message = await channel.fetch_message(int(cls["panel_message_id"]))
            await message.delete()
        except (discord.NotFound, discord.HTTPException):
            pass

    vc = guild.get_channel(int(cls["vc_id"])) if cls.get("vc_id") else None
    if vc:
        try:
            await vc.delete(reason="Kelas dibubarkan")
        except discord.HTTPException:
            log.exception("Gagal menghapus VC kelas.")

    role = guild.get_role(int(cls["role_id"])) if cls.get("role_id") else None
    if role:
        try:
            await role.delete(reason="Kelas dibubarkan")
        except discord.HTTPException:
            log.exception("Gagal menghapus role kelas.")

    await send_log(
        bot,
        guild,
        f"🗑️ Kelas **{cls['name']}** (ID `{class_id}`) dibubarkan oleh <@{actor_id}>.",
    )
    return True


async def extend_class(bot, guild, class_id, actor_id):
    cls = await get_class(class_id)
    if not cls:
        return None

    due = db_dt(cls["due_date"])
    now = utc_now()

    if not due:
        due = now

    if due < now:
        while due <= now:
            due += timedelta(days=30)
    else:
        due += timedelta(days=30)

    grace = due + timedelta(days=7)

    await execute(
        """
        UPDATE nanz_classes
        SET due_date=%s,
            grace_until=%s,
            status='Active',
            billing_status='Paid',
            billing_message_id=NULL,
            last_billing_notice=NULL
        WHERE class_id=%s
        """,
        (due.replace(tzinfo=None), grace.replace(tzinfo=None), class_id),
    )

    await update_public_panel(bot, class_id)
    await send_log(
        bot,
        guild,
        f"🔄 Kelas **{cls['name']}** diperpanjang oleh <@{actor_id}> sampai <t:{int(due.timestamp())}:F>.",
    )
    return due


class ClassManagementView(discord.ui.View):
    def __init__(self, class_id):
        super().__init__(timeout=300)
        self.class_id = int(class_id)

        actions = [
            ("Kelola Member", "👥", discord.ButtonStyle.primary, self.manage_members, "members"),
            ("Edit Kelas", "📝", discord.ButtonStyle.secondary, self.edit_class, "edit"),
            ("Ganti Staff", "🧑‍💼", discord.ButtonStyle.secondary, self.change_staff, "staff"),
            ("Perpanjang", "🔄", discord.ButtonStyle.success, self.extend, "extend"),
            ("Hapus Kelas", "🗑️", discord.ButtonStyle.danger, self.delete_class, "delete"),
            ("Refresh", "🔄", discord.ButtonStyle.secondary, self.refresh, "refresh"),
        ]

        for label, emoji, style, callback, suffix in actions:
            button = discord.ui.Button(
                label=label,
                emoji=emoji,
                style=style,
                custom_id=f"nanz:class_manage:{suffix}:{self.class_id}",
            )
            button.callback = callback
            self.add_item(button)

    async def interaction_check(self, interaction):
        cls = await get_class(self.class_id)
        if not cls or not can_manage_class(interaction.user, cls):
            await interaction.response.send_message(
                "🔒 Panel ini hanya dapat digunakan Staff Pendamping kelas atau Administrator.",
                ephemeral=True,
            )
            return False
        return True

    async def manage_members(self, interaction):
        await interaction.response.send_message(
            "👥 **Kelola Anggota**\nPilih anggota lalu tekan Keluarkan.",
            view=ClassMemberManageView(self.class_id),
            ephemeral=True,
        )

    async def edit_class(self, interaction):
        modal = await ClassEditModal.create(self.class_id)
        await interaction.response.send_modal(modal)

    async def change_staff(self, interaction):
        await interaction.response.send_message(
            "🧑‍💼 Pilih Staff baru:",
            view=StaffChangeView(self.class_id),
            ephemeral=True,
        )

    async def extend(self, interaction):
        due = await extend_class(
            interaction.client,
            interaction.guild,
            self.class_id,
            interaction.user.id,
        )
        if not due:
            await interaction.response.send_message("❌ Kelas tidak ditemukan.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"✅ Kelas diperpanjang sampai <t:{int(due.timestamp())}:F>.",
            ephemeral=True,
        )

    async def delete_class(self, interaction):
        cls = await get_class(self.class_id)
        if not cls:
            await interaction.response.send_message("❌ Kelas tidak ditemukan.", ephemeral=True)
            return

        await interaction.response.send_message(
            f"⚠️ **Bubarkan {cls['name']}?**\n\n"
            "Tindakan ini akan menghapus panel publik, Voice Channel, role kelas, "
            "data anggota, dan membatalkan request yang masih pending.",
            view=ClassDeleteConfirmView(self.class_id),
            ephemeral=True,
        )

    async def refresh(self, interaction):
        await interaction.response.edit_message(
            embed=await build_class_management_embed(interaction.client, self.class_id),
            view=ClassManagementView(self.class_id),
        )


# =========================================================
# PUBLIC CLASS PANEL
# =========================================================

class ClassPublicPanel(discord.ui.View):
    def __init__(self, class_id):
        super().__init__(timeout=None)
        self.class_id = int(class_id)

        buttons = [
            ("Daftar Kelas", "📝", discord.ButtonStyle.primary, self.join_class, "join"),
            ("Lihat Anggota", "👥", discord.ButtonStyle.secondary, self.view_members, "members"),
            ("Keluar Kelas", "🚪", discord.ButtonStyle.secondary, self.leave_class, "leave"),
            ("Kelola Kelas", "⚙️", discord.ButtonStyle.secondary, self.manage_class, "manage"),
        ]

        for label, emoji, style, callback, suffix in buttons:
            button = discord.ui.Button(
                label=label,
                emoji=emoji,
                style=style,
                custom_id=f"nanz:class_public:{suffix}:{self.class_id}",
            )
            button.callback = callback
            self.add_item(button)

    async def join_class(self, interaction):
        cls = await get_class(self.class_id)
        if not cls:
            await interaction.response.send_message("❌ Kelas tidak ditemukan.", ephemeral=True)
            return

        if cls["status"] != "Active":
            await interaction.response.send_message("❌ Kelas ini sedang tidak menerima anggota baru.", ephemeral=True)
            return

        existing = await get_user_class(interaction.user.id)
        if existing:
            await interaction.response.send_message(
                f"❌ Kamu sudah tergabung di **{existing['name']}**.\nSatu member hanya boleh memiliki satu kelas.",
                ephemeral=True,
            )
            return

        count = await get_member_count(self.class_id)
        if count >= MAX_MEMBER:
            await interaction.response.send_message("❌ Kelas ini sudah penuh.", ephemeral=True)
            return

        pending = await fetch_one(
            """
            SELECT request_id FROM nanz_class_join_requests
            WHERE class_id=%s AND user_id=%s AND status='Pending'
            LIMIT 1
            """,
            (self.class_id, interaction.user.id),
        )
        if pending:
            await interaction.response.send_message("⏳ Request kamu masih diproses.", ephemeral=True)
            return

        request_id = await execute(
            """
            INSERT INTO nanz_class_join_requests (class_id,user_id,status,created_at)
            VALUES (%s,%s,'Pending',%s)
            """,
            (self.class_id, interaction.user.id, db_now()),
        )

        request_channel_id = getattr(interaction.client, "REQUEST_GABUNG_CHANNEL_ID", None)
        request_channel = interaction.guild.get_channel(request_channel_id) if request_channel_id else None

        if not request_channel:
            await execute(
                "DELETE FROM nanz_class_join_requests WHERE request_id=%s",
                (request_id,),
            )
            await interaction.response.send_message(
                "❌ Channel `request-gabung` tidak tersedia. Request dibatalkan agar tidak menggantung.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="📥 Request Gabung Kelas",
            description="Menunggu Owner, Staff Pendamping, atau Administrator.",
            color=discord.Color.blurple(),
            timestamp=utc_now(),
        )
        embed.add_field(name="Kelas", value=cls["name"], inline=False)
        embed.add_field(name="Pemohon", value=interaction.user.mention, inline=True)
        embed.add_field(name="Owner", value=f"<@{cls['owner_id']}>", inline=True)
        embed.add_field(name="Staff", value=f"<@{cls['staff_id']}>", inline=True)
        embed.add_field(name="Request ID", value=f"`{request_id}`", inline=True)

        await request_channel.send(
            content=f"<@{cls['staff_id']}>",
            embed=embed,
            view=JoinRequestView(request_id),
        )

        await interaction.response.send_message(
            "✅ Request bergabung berhasil dikirim. Tunggu persetujuan.",
            ephemeral=True,
        )

    async def view_members(self, interaction):
        cls = await get_class(self.class_id)
        if not cls:
            await interaction.response.send_message("❌ Kelas tidak ditemukan.", ephemeral=True)
            return

        members = await fetch_all(
            """
            SELECT user_id, joined_at FROM nanz_class_members
            WHERE class_id=%s ORDER BY joined_at ASC
            """,
            (self.class_id,),
        )

        if not members:
            await interaction.response.send_message("Belum ada anggota di kelas ini.", ephemeral=True)
            return

        lines = []
        for index, row in enumerate(members, start=1):
            lines.append(f"`{index:02}` <@{row['user_id']}>")

        embed = discord.Embed(
            title=f"👥 Anggota — {cls['name']}",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Total {len(members)}/{MAX_MEMBER} siswa")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def leave_class(self, interaction):
        cls = await fetch_one(
            """
            SELECT c.* FROM nanz_class_members m
            JOIN nanz_classes c ON c.class_id=m.class_id
            WHERE m.user_id=%s AND c.class_id=%s
            LIMIT 1
            """,
            (interaction.user.id, self.class_id),
        )

        if not cls:
            await interaction.response.send_message("❌ Kamu bukan anggota kelas ini.", ephemeral=True)
            return

        if interaction.user.id == int(cls["owner_id"]):
            await interaction.response.send_message(
                "❌ Owner kelas tidak dapat keluar sendiri. Hubungi Staff/Administrator.",
                ephemeral=True,
            )
            return

        await execute(
            "DELETE FROM nanz_class_members WHERE class_id=%s AND user_id=%s",
            (self.class_id, interaction.user.id),
        )

        role = interaction.guild.get_role(int(cls["role_id"]))
        if role:
            try:
                await interaction.user.remove_roles(role, reason="Keluar kelas nanZ")
            except discord.HTTPException:
                pass

        await update_public_panel(interaction.client, self.class_id)
        await send_log(
            interaction.client,
            interaction.guild,
            f"🚪 {interaction.user.mention} keluar dari **{cls['name']}**.",
        )
        await interaction.response.send_message(
            f"✅ Kamu telah keluar dari **{cls['name']}**.",
            ephemeral=True,
        )

    async def manage_class(self, interaction):
        cls = await get_class(self.class_id)
        if not cls:
            await interaction.response.send_message("❌ Kelas tidak ditemukan.", ephemeral=True)
            return

        if not can_manage_class(interaction.user, cls):
            await interaction.response.send_message(
                "🔒 Panel management hanya untuk Staff Pendamping kelas atau Administrator.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=await build_class_management_embed(interaction.client, self.class_id),
            view=ClassManagementView(self.class_id),
            ephemeral=True,
        )


# =========================================================
# JOIN REQUEST VIEW
# =========================================================

class JoinRequestView(discord.ui.View):
    def __init__(self, request_id):
        super().__init__(timeout=None)
        self.request_id = int(request_id)

        approve = discord.ui.Button(
            label="Terima",
            emoji="✅",
            style=discord.ButtonStyle.success,
            custom_id=f"nanz:class_join_approve:{self.request_id}",
        )
        approve.callback = self.approve
        self.add_item(approve)

        reject = discord.ui.Button(
            label="Tolak",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            custom_id=f"nanz:class_join_reject:{self.request_id}",
        )
        reject.callback = self.reject
        self.add_item(reject)

    async def get_request(self):
        return await fetch_one(
            """
            SELECT
                r.*,
                c.name,
                c.role_id,
                c.staff_id,
                c.owner_id,
                c.status AS class_status
            FROM nanz_class_join_requests r
            JOIN nanz_classes c ON c.class_id=r.class_id
            WHERE r.request_id=%s
            LIMIT 1
            """,
            (self.request_id,),
        )

    async def check_access(self, interaction, request):
        return can_process_join(interaction.user, request)

    async def approve(self, interaction):
        request = await self.get_request()
        if not request:
            await interaction.response.send_message("❌ Request tidak ditemukan.", ephemeral=True)
            return

        if not await self.check_access(interaction, request):
            await interaction.response.send_message(
                "🔒 Hanya Owner kelas, Staff Pendamping, atau Administrator yang dapat memproses request ini.",
                ephemeral=True,
            )
            return

        if request["status"] != "Pending":
            await interaction.response.send_message("❌ Request sudah diproses.", ephemeral=True)
            return

        if request["class_status"] != "Active":
            await interaction.response.send_message("❌ Kelas sedang tidak aktif menerima anggota.", ephemeral=True)
            return

        existing = await get_user_class(request["user_id"])
        if existing:
            await interaction.response.send_message(
                f"❌ User sudah berada di **{existing['name']}**.",
                ephemeral=True,
            )
            return

        count = await get_member_count(request["class_id"])
        if count >= MAX_MEMBER:
            await interaction.response.send_message("❌ Kelas sudah penuh.", ephemeral=True)
            return

        member = interaction.guild.get_member(int(request["user_id"]))
        if not member:
            await interaction.response.send_message("❌ User sudah tidak berada di server.", ephemeral=True)
            return

        role = interaction.guild.get_role(int(request["role_id"]))
        if not role:
            await interaction.response.send_message("❌ Role kelas tidak ditemukan.", ephemeral=True)
            return

        await interaction.response.defer()

        inserted = False
        try:
            # Proteksi double-click: status masih Pending sebelum insert.
            await execute(
                """
                INSERT INTO nanz_class_members (class_id,user_id,joined_at)
                VALUES (%s,%s,%s)
                """,
                (request["class_id"], member.id, db_now()),
            )
            inserted = True

            await member.add_roles(role, reason=f"Join kelas {request['name']}")

            await execute(
                """
                UPDATE nanz_class_join_requests
                SET status='Approved', processed_at=%s, processed_by=%s
                WHERE request_id=%s AND status='Pending'
                """,
                (db_now(), interaction.user.id, self.request_id),
            )

            await update_public_panel(interaction.client, request["class_id"])

            embed = discord.Embed(
                title="✅ Request Diterima",
                description=f"{member.mention} sekarang menjadi anggota **{request['name']}**.",
                color=discord.Color.green(),
            )
            embed.add_field(name="Diproses oleh", value=interaction.user.mention)
            await interaction.message.edit(embed=embed, view=None)

            await send_log(
                interaction.client,
                interaction.guild,
                f"✅ {member.mention} diterima ke **{request['name']}** oleh {interaction.user.mention}.",
            )

            await interaction.followup.send("✅ Anggota berhasil ditambahkan.", ephemeral=True)

        except Exception:
            log.exception("Gagal approve join request.")
            if inserted:
                await execute(
                    "DELETE FROM nanz_class_members WHERE class_id=%s AND user_id=%s",
                    (request["class_id"], member.id),
                )
            await interaction.followup.send("❌ Gagal menambahkan anggota.", ephemeral=True)

    async def reject(self, interaction):
        request = await self.get_request()
        if not request:
            await interaction.response.send_message("❌ Request tidak ditemukan.", ephemeral=True)
            return

        if not await self.check_access(interaction, request):
            await interaction.response.send_message(
                "🔒 Hanya Owner kelas, Staff Pendamping, atau Administrator yang dapat memproses request ini.",
                ephemeral=True,
            )
            return

        if request["status"] != "Pending":
            await interaction.response.send_message("❌ Request sudah diproses.", ephemeral=True)
            return

        await execute(
            """
            UPDATE nanz_class_join_requests
            SET status='Rejected', processed_at=%s, processed_by=%s
            WHERE request_id=%s AND status='Pending'
            """,
            (db_now(), interaction.user.id, self.request_id),
        )

        embed = discord.Embed(
            title="❌ Request Ditolak",
            description=f"Request bergabung ke **{request['name']}** ditolak.",
            color=discord.Color.red(),
        )
        embed.add_field(name="Diproses oleh", value=interaction.user.mention)

        await interaction.response.edit_message(embed=embed, view=None)
        await send_log(
            interaction.client,
            interaction.guild,
            f"❌ Request {request['request_id']} untuk **{request['name']}** ditolak oleh {interaction.user.mention}.",
        )


# =========================================================
# COG
# =========================================================

class NanzKelasCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.REQUEST_GABUNG_CHANNEL_ID = REQUEST_GABUNG_CHANNEL_ID
        bot.LOG_KELAS_CHANNEL_ID = LOG_KELAS_CHANNEL_ID

    async def cog_load(self):
        # Register persistent static views first.
        self.bot.add_view(ClassFormTriggerView())
        self.bot.add_view(StaffDashboardView())

        classes = await fetch_all(
            """
            SELECT class_id FROM nanz_classes
            WHERE status IN ('Active','Grace')
            """
        )
        for cls in classes:
            self.bot.add_view(ClassPublicPanel(int(cls["class_id"])))

        requests = await fetch_all(
            """
            SELECT request_id FROM nanz_class_creation_requests
            WHERE status='Pending'
            """
        )
        for request in requests:
            self.bot.add_view(ClassApprovalView(int(request["request_id"])))

        join_requests = await fetch_all(
            """
            SELECT request_id FROM nanz_class_join_requests
            WHERE status='Pending'
            """
        )
        for request in join_requests:
            self.bot.add_view(JoinRequestView(int(request["request_id"])))

        await self.ensure_staff_dashboard()
        log.info("Persistent View Kelas nanZ berhasil direstore.")

    async def ensure_staff_dashboard(self):
        channel = self.bot.get_channel(APPROVAL_CHANNEL_ID)
        if not channel:
            log.warning("Channel approval-kelas tidak ditemukan; dashboard Staff tidak dibuat.")
            return

        marker = "NANZ_STAFF_DASHBOARD"
        existing = None

        try:
            async for message in channel.history(limit=100):
                if message.author.id == self.bot.user.id and message.embeds:
                    if any(marker in (embed.footer.text or "") for embed in message.embeds if embed.footer):
                        existing = message
                        break
        except Exception:
            log.exception("Gagal mencari dashboard Staff.")

        embed = build_staff_dashboard_embed()
        embed.set_footer(text=marker)

        try:
            if existing:
                await existing.edit(embed=embed, view=StaffDashboardView())
            else:
                await channel.send(embed=embed, view=StaffDashboardView())
        except Exception:
            log.exception("Gagal membuat/memperbarui dashboard Staff.")

    @commands.command(name="buat_kelas")
    @commands.guild_only()
    @commands.check(lambda ctx: has_staff_role(ctx.author))
    async def buat_kelas(self, ctx):
        await ctx.send(
            "🏫 **Panel Pembuatan Kelas nanZ**\n"
            "Panel ini khusus Staff/Administrator.",
            view=ClassFormTriggerView(),
        )


async def setup(bot):
    await bot.add_cog(NanzKelasCog(bot))
