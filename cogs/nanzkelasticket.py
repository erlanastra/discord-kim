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

APPROVAL_CHANNEL_ID = 123456789012345678
DAFTAR_KELAS_CHANNEL_ID = 876543210987654321
RUANG_KELAS_CATEGORY_ID = 112233445566778899
PEMBATAS_ROLE_ID = 998877665544332211

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
# CLASS CREATION MODAL
# =========================================================

class ClassCreationModal(discord.ui.Modal):
    def __init__(self, owner_id, staff_id):
        super().__init__(
            title="Buat Kelas nanZ",
            timeout=600,
        )

        self.owner_id = owner_id
        self.staff_id = staff_id

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
            default="#3498db",
            max_length=7,
            required=True,
        )

        self.logo_input = discord.ui.TextInput(
            label="URL Logo",
            placeholder="https://...",
            max_length=500,
            required=False,
        )

        self.add_item(self.name_input)
        self.add_item(self.motto_input)
        self.add_item(self.description_input)
        self.add_item(self.color_input)
        self.add_item(self.logo_input)

    async def on_submit(self, interaction: discord.Interaction):
        name = clean_text(self.name_input.value, 50)
        motto = clean_text(self.motto_input.value, 100) or "-"
        description = clean_text(self.description_input.value, 300)
        color_hex = clean_text(self.color_input.value, 7)
        logo_url = clean_text(self.logo_input.value, 500) or None

        if not valid_hex(color_hex):
            await interaction.response.send_message(
                "❌ Format warna tidak valid.\nGunakan format seperti `#5865F2`.",
                ephemeral=True,
            )
            return

        # -------------------------------------------------
        # CEK OWNER SUDAH PUNYA KELAS
        # -------------------------------------------------

        existing = await get_user_class(self.owner_id)

        if existing:
            await interaction.response.send_message(
                f"❌ Kamu sudah menjadi anggota **{existing['name']}**.\n"
                "Satu member hanya boleh memiliki satu kelas.",
                ephemeral=True,
            )
            return

        # -------------------------------------------------
        # CEK PENDING REQUEST
        # -------------------------------------------------

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

        # -------------------------------------------------
        # SIMPAN REQUEST
        # -------------------------------------------------

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
                %s,%s,%s,%s,%s,%s,%s,%s,
                'Pending',
                %s
            )
            """,
            (
                interaction.guild.id,
                self.owner_id,
                self.staff_id,
                name,
                motto,
                description,
                color_hex,
                logo_url,
                db_now(),
            ),
        )

        approval_channel = interaction.guild.get_channel(
            APPROVAL_CHANNEL_ID
        )

        if not approval_channel:
            await interaction.response.send_message(
                "⚠️ Pengajuan berhasil disimpan, tetapi channel approval tidak ditemukan.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🏫 Pengajuan Kelas Baru",
            description=(
                "Terdapat pengajuan kelas baru yang menunggu persetujuan."
            ),
            color=discord.Color.from_str(color_hex),
            timestamp=utc_now(),
        )

        embed.add_field(
            name="Nama Kelas",
            value=name,
            inline=False,
        )

        embed.add_field(
            name="Motto",
            value=motto,
            inline=False,
        )

        embed.add_field(
            name="Deskripsi",
            value=description,
            inline=False,
        )

        embed.add_field(
            name="Pemilik",
            value=f"<@{self.owner_id}>",
            inline=True,
        )

        embed.add_field(
            name="Staff Pendamping",
            value=f"<@{self.staff_id}>",
            inline=True,
        )

        embed.add_field(
            name="Request ID",
            value=f"`{request_id}`",
            inline=True,
        )

        if logo_url:
            embed.set_thumbnail(url=logo_url)

        await approval_channel.send(
            embed=embed,
            view=ClassApprovalView(request_id),
        )

        await interaction.response.send_message(
            "✅ Pengajuan kelas berhasil dikirim.\n"
            "Tunggu Staff/Management memproses pengajuan kamu.",
            ephemeral=True,
        )


# =========================================================
# FORM TRIGGER
# =========================================================

class ClassFormTriggerView(discord.ui.View):
    def __init__(self, staff_id):
        super().__init__(timeout=300)
        self.staff_id = staff_id

    @discord.ui.button(
        label="Buka Form Kelas",
        emoji="🏫",
        style=discord.ButtonStyle.primary,
        custom_id="nanz:open_class_form",
    )
    async def open_form(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_modal(
            ClassCreationModal(
                owner_id=interaction.user.id,
                staff_id=self.staff_id,
            )
        )


# =========================================================
# APPROVAL VIEW
# =========================================================

class ClassApprovalView(discord.ui.View):
    def __init__(self, request_id):
        super().__init__(
            timeout=None
        )

        self.request_id = int(request_id)

    async def interaction_check(self, interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ Hanya Staff/Management yang dapat memproses pengajuan.",
                ephemeral=True,
            )
            return False

        return True

    @discord.ui.button(
        label="Approve",
        emoji="✅",
        style=discord.ButtonStyle.success,
    )
    async def approve(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        request = await fetch_one(
            """
            SELECT *
            FROM nanz_class_creation_requests
            WHERE request_id=%s
            LIMIT 1
            """,
            (self.request_id,),
        )

        if not request:
            await interaction.response.send_message(
                "❌ Data pengajuan tidak ditemukan.",
                ephemeral=True,
            )
            return

        if request["status"] != "Pending":
            await interaction.response.send_message(
                f"❌ Pengajuan ini sudah berstatus `{request['status']}`.",
                ephemeral=True,
            )
            return

        guild = interaction.guild

        owner = guild.get_member(
            int(request["owner_id"])
        )

        staff = guild.get_member(
            int(request["staff_id"])
        )

        if not owner:
            await interaction.response.send_message(
                "❌ Pemilik kelas sudah tidak berada di server.",
                ephemeral=True,
            )
            return

        # -------------------------------------------------
        # DOUBLE CHECK 1 MEMBER = 1 CLASS
        # -------------------------------------------------

        existing = await get_user_class(owner.id)

        if existing:
            await interaction.response.send_message(
                f"❌ Pemilik sudah memiliki kelas **{existing['name']}**.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        role = None
        voice = None
        class_id = None

        try:
            # -------------------------------------------------
            # ROLE
            # -------------------------------------------------

            role = await guild.create_role(
                name=request["name"],
                color=discord.Color.from_str(
                    request["color_hex"]
                ),
                reason=f"Kelas nanZ #{self.request_id}",
            )

            # -------------------------------------------------
            # ROLE POSITION
            # -------------------------------------------------

            separator = guild.get_role(
                PEMBATAS_ROLE_ID
            )

            if separator:
                try:
                    await role.edit(
                        position=max(separator.position - 1, 1)
                    )
                except discord.HTTPException:
                    log.exception(
                        "Gagal mengatur posisi role kelas."
                    )

            # -------------------------------------------------
            # VC PUBLIC
            # -------------------------------------------------

            category = guild.get_channel(
                RUANG_KELAS_CATEGORY_ID
            )

            if not isinstance(category, discord.CategoryChannel):
                raise RuntimeError(
                    "Category RUANG KELAS tidak ditemukan."
                )

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

            # -------------------------------------------------
            # DATABASE
            # -------------------------------------------------

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
                    request["staff_id"],
                    request["owner_id"],
                    now,
                    due_date,
                    grace_until,
                ),
            )

            # -------------------------------------------------
            # OWNER MEMBER
            # -------------------------------------------------

            await execute(
                """
                INSERT INTO nanz_class_members
                (
                    class_id,
                    user_id,
                    joined_at
                )
                VALUES
                (
                    %s,%s,%s
                )
                """,
                (
                    class_id,
                    owner.id,
                    now,
                ),
            )

            # -------------------------------------------------
            # GIVE ROLE
            # -------------------------------------------------

            await owner.add_roles(
                role,
                reason="Menjadi anggota kelas nanZ",
            )

            # -------------------------------------------------
            # MARK REQUEST
            # -------------------------------------------------

            await execute(
                """
                UPDATE nanz_class_creation_requests
                SET
                    status='Approved',
                    processed_at=%s,
                    processed_by=%s,
                    class_id=%s
                WHERE request_id=%s
                """,
                (
                    now,
                    interaction.user.id,
                    class_id,
                    self.request_id,
                ),
            )

            # -------------------------------------------------
            # PANEL
            # -------------------------------------------------

            await update_public_panel(
                interaction.client,
                class_id,
            )

            # -------------------------------------------------
            # VC WELCOME
            # -------------------------------------------------

            try:
                await voice.send(
                    f"🏫 **{request['name']}** resmi berdiri!\n"
                    f"Staff Pendamping: <@{request['staff_id']}>\n"
                    f"Pemilik: <@{request['owner_id']}>\n\n"
                    "**Berbeda Kelas, Tetap Satu Sekolah.**"
                )
            except Exception:
                pass

            # -------------------------------------------------
            # APPROVAL MESSAGE
            # -------------------------------------------------

            embed = discord.Embed(
                title="🏫 Kelas Disetujui",
                color=discord.Color.green(),
                timestamp=utc_now(),
            )

            embed.add_field(
                name="Kelas",
                value=request["name"],
                inline=False,
            )

            embed.add_field(
                name="Pemilik",
                value=f"<@{request['owner_id']}>",
                inline=True,
            )

            embed.add_field(
                name="Staff Pendamping",
                value=f"<@{request['staff_id']}>",
                inline=True,
            )

            embed.add_field(
                name="Class ID",
                value=f"`{class_id}`",
                inline=True,
            )

            await interaction.message.edit(
                embed=embed,
                view=None,
            )

            await send_log(
                interaction.client,
                guild,
                f"🏫 Kelas **{request['name']}** dibuat oleh "
                f"<@{interaction.user.id}>. "
                f"Class ID: `{class_id}`.",
            )

            await interaction.followup.send(
                f"✅ Kelas **{request['name']}** berhasil dibuat.",
                ephemeral=True,
            )

        except Exception as exc:
            log.exception("Gagal membuat kelas.")

            # -------------------------------------------------
            # CLEANUP OBJECT DISCORD
            # -------------------------------------------------

            if voice:
                try:
                    await voice.delete(
                        reason="Rollback pembuatan kelas"
                    )
                except Exception:
                    pass

            if role:
                try:
                    await role.delete(
                        reason="Rollback pembuatan kelas"
                    )
                except Exception:
                    pass

            # Jika DB sudah sempat dibuat, bersihkan
            if class_id:
                try:
                    await execute(
                        """
                        DELETE FROM nanz_classes
                        WHERE class_id=%s
                        """,
                        (class_id,),
                    )
                except Exception:
                    pass

            await interaction.followup.send(
                "❌ Gagal membuat kelas.\n"
                f"Error: `{type(exc).__name__}`",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Reject",
        emoji="❌",
        style=discord.ButtonStyle.danger,
    )
    async def reject(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        request = await fetch_one(
            """
            SELECT *
            FROM nanz_class_creation_requests
            WHERE request_id=%s
            LIMIT 1
            """,
            (self.request_id,),
        )

        if not request:
            await interaction.response.send_message(
                "❌ Pengajuan tidak ditemukan.",
                ephemeral=True,
            )
            return

        if request["status"] != "Pending":
            await interaction.response.send_message(
                "❌ Pengajuan ini sudah diproses.",
                ephemeral=True,
            )
            return

        await execute(
            """
            UPDATE nanz_class_creation_requests
            SET
                status='Rejected',
                processed_at=%s,
                processed_by=%s
            WHERE request_id=%s
            """,
            (
                db_now(),
                interaction.user.id,
                self.request_id,
            ),
        )

        embed = discord.Embed(
            title="❌ Pengajuan Kelas Ditolak",
            description=(
                f"Pengajuan **{request['name']}** telah ditolak."
            ),
            color=discord.Color.red(),
            timestamp=utc_now(),
        )

        embed.add_field(
            name="Pemohon",
            value=f"<@{request['owner_id']}>",
        )

        embed.add_field(
            name="Diproses oleh",
            value=f"<@{interaction.user.id}>",
        )

        await interaction.response.edit_message(
            embed=embed,
            view=None,
        )


# =========================================================
# PUBLIC CLASS PANEL
# =========================================================

class ClassPublicPanel(discord.ui.View):
    def __init__(self, class_id):
        super().__init__(timeout=None)

        self.class_id = int(class_id)

        self.join_button = discord.ui.Button(
            label="Daftar Kelas",
            emoji="📝",
            style=discord.ButtonStyle.primary,
            custom_id=f"nanz:join:{self.class_id}",
        )

        self.members_button = discord.ui.Button(
            label="Lihat Anggota",
            emoji="👥",
            style=discord.ButtonStyle.secondary,
            custom_id=f"nanz:members:{self.class_id}",
        )

        self.join_button.callback = self.join_class
        self.members_button.callback = self.view_members

        self.add_item(self.join_button)
        self.add_item(self.members_button)

    async def join_class(self, interaction):
        cls = await get_class(self.class_id)

        if not cls:
            await interaction.response.send_message(
                "❌ Kelas tidak ditemukan.",
                ephemeral=True,
            )
            return

        if cls["status"] != "Active":
            await interaction.response.send_message(
                "❌ Kelas ini sedang tidak menerima anggota baru.",
                ephemeral=True,
            )
            return

        # -------------------------------------------------
        # 1 CLASS PER USER
        # -------------------------------------------------

        existing = await get_user_class(
            interaction.user.id
        )

        if existing:
            await interaction.response.send_message(
                f"❌ Kamu sudah tergabung di **{existing['name']}**.\n"
                "Satu member hanya boleh memiliki satu kelas.",
                ephemeral=True,
            )
            return

        # -------------------------------------------------
        # CAPACITY
        # -------------------------------------------------

        count = await get_member_count(
            self.class_id
        )

        if count >= MAX_MEMBER:
            await interaction.response.send_message(
                "❌ Kelas ini sudah penuh.",
                ephemeral=True,
            )
            return

        # -------------------------------------------------
        # DUPLICATE REQUEST
        # -------------------------------------------------

        pending = await fetch_one(
            """
            SELECT request_id
            FROM nanz_class_join_requests
            WHERE class_id=%s
              AND user_id=%s
              AND status='Pending'
            LIMIT 1
            """,
            (
                self.class_id,
                interaction.user.id,
            ),
        )

        if pending:
            await interaction.response.send_message(
                "⏳ Kamu sudah memiliki request bergabung "
                "yang sedang diproses.",
                ephemeral=True,
            )
            return

        request_id = await execute(
            """
            INSERT INTO nanz_class_join_requests
            (
                class_id,
                user_id,
                status,
                created_at
            )
            VALUES
            (
                %s,%s,'Pending',%s
            )
            """,
            (
                self.class_id,
                interaction.user.id,
                db_now(),
            ),
        )

        # -------------------------------------------------
        # REQUEST CHANNEL
        # -------------------------------------------------

        request_channel_id = getattr(
            interaction.client,
            "REQUEST_GABUNG_CHANNEL_ID",
            None,
        )

        request_channel = None

        if request_channel_id:
            request_channel = interaction.guild.get_channel(
                request_channel_id
            )

        if request_channel:
            embed = discord.Embed(
                title="📥 Request Gabung Kelas",
                color=discord.Color.blurple(),
                timestamp=utc_now(),
            )

            embed.add_field(
                name="Kelas",
                value=cls["name"],
                inline=False,
            )

            embed.add_field(
                name="Pemohon",
                value=interaction.user.mention,
                inline=True,
            )

            embed.add_field(
                name="Staff Pendamping",
                value=f"<@{cls['staff_id']}>",
                inline=True,
            )

            embed.add_field(
                name="Request ID",
                value=f"`{request_id}`",
                inline=True,
            )

            await request_channel.send(
                content=f"<@{cls['staff_id']}>",
                embed=embed,
                view=JoinRequestView(request_id),
            )

        await interaction.response.send_message(
            "✅ Request bergabung berhasil dikirim.\n"
            "Tunggu persetujuan Staff Pendamping.",
            ephemeral=True,
        )

    async def view_members(self, interaction):
        members = await fetch_all(
            """
            SELECT user_id, joined_at
            FROM nanz_class_members
            WHERE class_id=%s
            ORDER BY joined_at ASC
            """,
            (self.class_id,),
        )

        if not members:
            await interaction.response.send_message(
                "Belum ada anggota di kelas ini.",
                ephemeral=True,
            )
            return

        lines = []

        for index, row in enumerate(members, start=1):
            member = interaction.guild.get_member(
                int(row["user_id"])
            )

            if member:
                lines.append(
                    f"`{index:02}` {member.mention}"
                )
            else:
                lines.append(
                    f"`{index:02}` <@{row['user_id']}>"
                )

        embed = discord.Embed(
            title="👥 Anggota Kelas",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )

        embed.set_footer(
            text=f"Total {len(members)}/{MAX_MEMBER} siswa"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )


# =========================================================
# JOIN REQUEST VIEW
# =========================================================

class JoinRequestView(discord.ui.View):
    def __init__(self, request_id):
        super().__init__(timeout=None)

        self.request_id = int(request_id)

    async def get_request(self):
        return await fetch_one(
            """
            SELECT
                r.*,
                c.name,
                c.role_id,
                c.staff_id,
                c.status AS class_status
            FROM nanz_class_join_requests r
            JOIN nanz_classes c
                ON c.class_id = r.class_id
            WHERE r.request_id=%s
            LIMIT 1
            """,
            (self.request_id,),
        )

    async def check_staff(self, interaction, request):
        return (
            interaction.user.guild_permissions.manage_guild
            or interaction.user.id == int(request["staff_id"])
        )

    @discord.ui.button(
        label="Terima",
        emoji="✅",
        style=discord.ButtonStyle.success,
    )
    async def approve(
        self,
        interaction,
        button,
    ):
        request = await self.get_request()

        if not request:
            await interaction.response.send_message(
                "❌ Request tidak ditemukan.",
                ephemeral=True,
            )
            return

        if not await self.check_staff(
            interaction,
            request,
        ):
            await interaction.response.send_message(
                "❌ Hanya Staff Pendamping kelas atau Management yang dapat memproses request ini.",
                ephemeral=True,
            )
            return

        if request["status"] != "Pending":
            await interaction.response.send_message(
                "❌ Request sudah diproses.",
                ephemeral=True,
            )
            return

        if request["class_status"] != "Active":
            await interaction.response.send_message(
                "❌ Kelas sedang tidak aktif menerima anggota.",
                ephemeral=True,
            )
            return

        existing = await get_user_class(
            request["user_id"]
        )

        if existing:
            await interaction.response.send_message(
                f"❌ User sudah berada di **{existing['name']}**.",
                ephemeral=True,
            )
            return

        count = await get_member_count(
            request["class_id"]
        )

        if count >= MAX_MEMBER:
            await interaction.response.send_message(
                "❌ Kelas sudah penuh.",
                ephemeral=True,
            )
            return

        member = interaction.guild.get_member(
            int(request["user_id"])
        )

        if not member:
            await interaction.response.send_message(
                "❌ User sudah tidak berada di server.",
                ephemeral=True,
            )
            return

        role = interaction.guild.get_role(
            int(request["role_id"])
        )

        if not role:
            await interaction.response.send_message(
                "❌ Role kelas tidak ditemukan.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            await execute(
                """
                INSERT INTO nanz_class_members
                (
                    class_id,
                    user_id,
                    joined_at
                )
                VALUES
                (
                    %s,%s,%s
                )
                """,
                (
                    request["class_id"],
                    member.id,
                    db_now(),
                ),
            )

            await member.add_roles(
                role,
                reason=f"Join kelas {request['name']}",
            )

            await execute(
                """
                UPDATE nanz_class_join_requests
                SET
                    status='Approved',
                    processed_at=%s,
                    processed_by=%s
                WHERE request_id=%s
                """,
                (
                    db_now(),
                    interaction.user.id,
                    self.request_id,
                ),
            )

            await update_public_panel(
                interaction.client,
                request["class_id"],
            )

            embed = discord.Embed(
                title="✅ Request Diterima",
                description=(
                    f"{member.mention} sekarang menjadi anggota "
                    f"**{request['name']}**."
                ),
                color=discord.Color.green(),
            )

            await interaction.message.edit(
                embed=embed,
                view=None,
            )

            await interaction.followup.send(
                "✅ Anggota berhasil ditambahkan.",
                ephemeral=True,
            )

        except Exception:
            log.exception("Gagal approve join request.")

            await interaction.followup.send(
                "❌ Gagal menambahkan anggota.",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Tolak",
        emoji="❌",
        style=discord.ButtonStyle.danger,
    )
    async def reject(
        self,
        interaction,
        button,
    ):
        request = await self.get_request()

        if not request:
            await interaction.response.send_message(
                "❌ Request tidak ditemukan.",
                ephemeral=True,
            )
            return

        if not await self.check_staff(
            interaction,
            request,
        ):
            await interaction.response.send_message(
                "❌ Hanya Staff Pendamping kelas atau Management yang dapat memproses request ini.",
                ephemeral=True,
            )
            return

        if request["status"] != "Pending":
            await interaction.response.send_message(
                "❌ Request sudah diproses.",
                ephemeral=True,
            )
            return

        await execute(
            """
            UPDATE nanz_class_join_requests
            SET
                status='Rejected',
                processed_at=%s,
                processed_by=%s
            WHERE request_id=%s
            """,
            (
                db_now(),
                interaction.user.id,
                self.request_id,
            ),
        )

        embed = discord.Embed(
            title="❌ Request Ditolak",
            description=(
                f"Request bergabung ke **{request['name']}** ditolak."
            ),
            color=discord.Color.red(),
        )

        await interaction.response.edit_message(
            embed=embed,
            view=None,
        )


# =========================================================
# COG
# =========================================================

class NanzKelasCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Dipakai cog lain
        bot.REQUEST_GABUNG_CHANNEL_ID = getattr(
            bot,
            "REQUEST_GABUNG_CHANNEL_ID",
            None,
        )

        bot.LOG_KELAS_CHANNEL_ID = getattr(
            bot,
            "LOG_KELAS_CHANNEL_ID",
            None,
        )

    async def cog_load(self):
        """
        Restore persistent public panel dan request views.
        """

        # -------------------------------------------------
        # PUBLIC PANELS
        # -------------------------------------------------

        classes = await fetch_all(
            """
            SELECT class_id
            FROM nanz_classes
            WHERE status IN ('Active', 'Grace')
            """
        )

        for cls in classes:
            self.bot.add_view(
                ClassPublicPanel(
                    int(cls["class_id"])
                )
            )

        # -------------------------------------------------
        # CREATION REQUESTS
        # -------------------------------------------------

        requests = await fetch_all(
            """
            SELECT request_id
            FROM nanz_class_creation_requests
            WHERE status='Pending'
            """
        )

        for request in requests:
            self.bot.add_view(
                ClassApprovalView(
                    int(request["request_id"])
                )
            )

        # -------------------------------------------------
        # JOIN REQUESTS
        # -------------------------------------------------

        join_requests = await fetch_all(
            """
            SELECT request_id
            FROM nanz_class_join_requests
            WHERE status='Pending'
            """
        )

        for request in join_requests:
            self.bot.add_view(
                JoinRequestView(
                    int(request["request_id"])
                )
            )

        log.info(
            "Persistent view Kelas nanZ berhasil direstore."
        )

    # =====================================================
    # TEST / MANUAL FORM TRIGGER
    # =====================================================

    @commands.command(name="buat_kelas")
    @commands.has_guild_permissions(manage_guild=True)
    async def buat_kelas(
        self,
        ctx,
        staff: discord.Member = None,
    ):
        """
        Trigger form pembuatan kelas.

        Untuk sementara digunakan sebagai trigger manual.
        Nantinya tombol Panel Tiket dapat diarahkan ke
        ClassCreationModal yang sama.
        """

        if staff is None:
            staff = ctx.author

        await ctx.send(
            "🏫 **Pembuatan Kelas nanZ**\n"
            "Silakan buka form berikut.",
            view=ClassFormTriggerView(
                staff.id
            ),
        )


async def setup(bot):
    await bot.add_cog(
        NanzKelasCog(bot)
    )