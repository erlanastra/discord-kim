import asyncio
import io
import json
import logging
import math
import random
import re
from datetime import datetime, timedelta, timezone

import aiohttp
import aiomysql
import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFilter, ImageFont


# =========================================================
# CONFIG
# =========================================================

APPROVAL_CHANNEL_ID = 1552604897201881148
DAFTAR_KELAS_CHANNEL_ID = 1552604329435856986
REQUEST_GABUNG_CHANNEL_ID = 1552604968643731546
# Isi dengan ID channel log-kelas jika ingin logging ke channel.
# None = logging channel dinonaktifkan.
LOG_KELAS_CHANNEL_ID = 1552605106724405338
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
# TEMA VISUAL (ungu-biru, gaya welcome GIF): CARD, BANNER, EMBED
# =========================================================

FONT_BOLD = "fonts/LEMONMILK-Bold.otf"
FONT_MEDIUM = "fonts/LEMONMILK-Medium.otf"
FONT_REGULAR = "fonts/LEMONMILK-Regular.otf"
FONT_LIGHT = "fonts/LEMONMILK-Light.otf"
_FONT_FALLBACKS = (
    "DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "arial.ttf",
)

BG_TOP, BG_BOT = (18, 10, 45), (40, 20, 80)
THEME_PURPLE = (130, 80, 255)
THEME_BLUE = (80, 180, 255)
CARD_BG = (30, 15, 65)
SOFT_PURPLE = (160, 120, 255)
SOFT_BLUE = (150, 210, 255)
OK_GREEN = (90, 220, 150)
WARN_ORANGE = (255, 170, 60)
BAD_RED = (235, 85, 95)
MUTED_GRAY = (120, 120, 145)

CARD_W, CARD_H = 1200, 650
CARD_RECT = (25, 25, CARD_W - 25, CARD_H - 25)
LOGO_SIZE = 150
LOGO_CX, LOGO_CY = 177, 175
RX0, RX1 = 340, CARD_W - 70

EMBED_PURPLE = discord.Color.from_rgb(*THEME_PURPLE)
EMBED_BLUE = discord.Color.from_rgb(*THEME_BLUE)
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━━━━"
FOOTER_TEXT = "nanZ Server • Berbeda Kelas, Tetap Satu Sekolah."
DASHBOARD_MARKER = "NANZ_STAFF_DASHBOARD"
BANNER_NAME = "banner.png"

STATUS_LABEL = {
    "Active": "ACTIVE",
    "Grace": "GRACE",
    "Inactive": "INACTIVE",
    "Dissolved": "DIBUBARKAN",
}

STATUS_META = {
    "Active": "<:verified:1553690488257908837> Aktif",
    "Grace": "<a:question:1553688505929044000> Masa Grace",
    "Inactive": "<a:question:1553688505929044000> Nonaktif",
    "Dissolved": "<a:arrow_purple:1512787191234035803> Dibubarkan",
}

BILLING_META = {
    "Paid": "<:verified:1553690488257908837> Lunas",
    "Unpaid": "<a:question:1553688505929044000> Belum Lunas",
}


# ---------- helper umum ----------

def slot_bar(count, total=MAX_MEMBER, length=10):
    ratio = min(max(count / total, 0), 1) if total else 0
    filled = round(length * ratio)
    return "▰" * filled + "▱" * (length - filled)


def style_embed(embed, footer=None):
    embed.set_footer(text=footer or FOOTER_TEXT)
    return embed


def stamp(value, style="F"):
    dt = db_dt(value)
    return f"<t:{int(dt.timestamp())}:{style}>" if dt else "-"


def _card_font(path, size):
    for p in (path, *_FONT_FALLBACKS):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))


def hex_rgb(value):
    value = (value or "").lstrip("#")

    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return THEME_PURPLE


def _fit_font(draw, text, path, start, max_w, min_size=14):
    size = start
    while size > min_size:
        f = _card_font(path, size)
        b = draw.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= max_w:
            return f, text
        size -= 2
    f = _card_font(path, min_size)
    while text and draw.textbbox((0, 0), text + "…", font=f)[2] > max_w:
        text = text[:-1]
    return f, text + "…"


def _wrap_lines(draw, text, font, max_w, max_lines=2):
    words = (text or "-").split()
    lines, current = [], ""

    for word in words:
        test = (current + " " + word).strip()
        if draw.textlength(test, font=font) <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines[:max_lines]


async def _run_blocking(func, *args):
    """Jalankan fungsi berat (render PIL) di thread executor.
    Pengganti asyncio.to_thread agar kompatibel dengan Python < 3.9."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)


# ---------- gambar: logo / avatar ----------

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

        image = Image.open(io.BytesIO(data)).convert("RGBA")
        image.thumbnail((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)

        return image

    except Exception:
        log.exception("Gagal mengambil logo kelas.")
        return None


async def load_avatar(user):
    try:
        data = await user.display_avatar.replace(size=128, format="png").read()
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


def _circle_image(img, size, text="nZ"):
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    if img:
        img = img.copy()
        img.thumbnail((size, size), Image.LANCZOS)
        canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
    else:
        d = ImageDraw.Draw(canvas)
        d.ellipse((0, 0, size, size), fill=(*THEME_PURPLE, 120))
        d.text(
            (size // 2, size // 2),
            text,
            fill=(240, 242, 245, 255),
            font=_card_font(FONT_BOLD, int(size * 0.31)),
            anchor="mm",
        )

    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4, size * 4), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)

    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(canvas, (0, 0), mask)

    return out


# ---------- gambar: background bersama ----------

def _backdrop(W, H, seed=7):
    rng = random.Random(seed)

    bg = Image.new("RGB", (W, H))
    bd = ImageDraw.Draw(bg)
    for y in range(H):
        bd.line([(0, y), (W, y)], fill=_lerp_color(BG_TOP, BG_BOT, y / H))
    base = bg.convert("RGBA")

    orbs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(orbs)
    size = max(W, H) * 0.17
    for ox, oy, br, oc in [
        (W * .08, H * .18, size, THEME_PURPLE),
        (W * .93, H * .78, size, THEME_BLUE),
        (W * .62, H * .02, size * .65, THEME_PURPLE),
    ]:
        for st in range(int(br), 0, -6):
            od.ellipse([ox - st, oy - st, ox + st, oy + st],
                       fill=(*oc, _clamp(55 * (st / br) ** 2.8)))
    base = Image.alpha_composite(base, orbs)

    aur = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ad = ImageDraw.Draw(aur)
    for by, amp, k, off, col, a in [
        (H - 90, 34, 2, 0.0, THEME_BLUE, 55),
        (H - 55, 26, 3, 2.0, THEME_PURPLE, 70),
        (H - 20, 20, 4, 4.0, SOFT_BLUE, 45),
    ]:
        pts = [(x, by + amp * math.sin(math.tau * k * x / W + off)) for x in range(0, W + 10, 12)]
        ad.polygon(pts + [(W, H), (0, H)], fill=(*col, a))
    base = Image.alpha_composite(base, aur.filter(ImageFilter.GaussianBlur(7)))

    fl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fl)
    for _ in range(int(W * H / 8000)):
        x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1.0, 2.6)
        fd.ellipse([x - r, y - r, x + r, y + r], fill=(*SOFT_BLUE, rng.randint(80, 190)))
    for _ in range(max(int(W * H / 50000), 6)):
        x, y = rng.uniform(15, W - 15), rng.uniform(12, H - 12)
        sz = rng.uniform(5, 10)
        q = sz * 0.25
        fd.polygon(
            [(x, y - sz), (x + q, y - q), (x + sz, y), (x + q, y + q),
             (x, y + sz), (x - q, y + q), (x - sz, y), (x - q, y - q)],
            fill=(*SOFT_PURPLE, rng.randint(90, 220)),
        )
    return Image.alpha_composite(base, fl)


def _glass_card(base, rect, radius=30):
    W, H = base.size
    pl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pl)
    pd.rounded_rectangle(rect, radius=radius, fill=(*CARD_BG, 200))
    pd.rounded_rectangle(rect, radius=radius, outline=(*THEME_PURPLE, 90), width=2)
    return Image.alpha_composite(base, pl)


def _shimmer(base, rect, radius=30, pos=0.62):
    W, H = base.size
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sp = int(W * pos)
    for k in range(-30, 31):
        sd.line([(sp + k + 80, 0), (sp + k - 80, H)],
                fill=(255, 255, 255, _clamp(22 * (1 - abs(k) / 30))), width=2)
    cm = Image.new("L", (W, H), 0)
    ImageDraw.Draw(cm).rounded_rectangle(rect, radius=radius, fill=255)
    sh.putalpha(Image.composite(sh.getchannel("A"), Image.new("L", (W, H), 0), cm))
    return Image.alpha_composite(base, sh)


def _icon_with_orbit(base, cx, cy, icon, size, accent):
    W, H = base.size
    rr = size // 2 + 12

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(
        [cx - rr - 8, cy - rr - 8, cx + rr + 8, cy + rr + 8],
        fill=(*_lerp_color(THEME_BLUE, THEME_PURPLE, 0.6), 90),
    )
    base = Image.alpha_composite(base, glow.filter(ImageFilter.GaussianBlur(14)))

    orb = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(orb)
    box = [cx - rr, cy - rr, cx + rr, cy + rr]
    od.ellipse(box, outline=(255, 255, 255, 55), width=2)
    od.arc(box, -40, 90, fill=(*accent, 255), width=5)
    od.arc(box, 150, 260, fill=(*SOFT_PURPLE, 255), width=5)
    base = Image.alpha_composite(base, orb)
    base.alpha_composite(icon, (cx - size // 2, cy - size // 2))
    return base


def _chip(draw, x, cy, text, font, dot, h=36):
    w = int(draw.textlength(text, font=font)) + 58
    draw.rounded_rectangle([x, cy - h // 2, x + w, cy + h // 2], radius=h // 2,
                           fill=(*dot, 40), outline=(*dot, 200), width=1)
    draw.ellipse([x + 16, cy - 6, x + 28, cy + 6], fill=(*dot, 255))
    draw.text((x + 40, cy), text, font=font, fill=(255, 255, 255, 245), anchor="lm")
    return x + w


def _draw_ring(draw, cx, cy, r, ratio, width=13):
    box = [cx - r, cy - r, cx + r, cy + r]
    draw.arc(box, 0, 360, fill=(255, 255, 255, 40), width=width)

    steps = int(120 * min(max(ratio, 0), 1))
    for s in range(steps):
        a0 = -90 + s * 3
        c = _lerp_color(THEME_BLUE, THEME_PURPLE, s / 120)
        draw.arc(box, a0, a0 + 4, fill=(*c, 255), width=width)


# ---------- gambar: CARD KELAS (panel publik) ----------

def _render_class_card_sync(d, logo, accent):
    W, H = CARD_W, CARD_H
    count = d["member_count"]
    ratio = min(count / MAX_MEMBER, 1)
    now = utc_now()

    status = d["status"]
    status_color = {
        "Active": accent,
        "Grace": WARN_ORANGE,
        "Inactive": BAD_RED,
        "Dissolved": MUTED_GRAY,
    }.get(status, accent)

    base = _backdrop(W, H, 7)
    base = _glass_card(base, CARD_RECT)

    # panel kiri
    pl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pl)
    left = (55, 55, 300, 595)
    pd.rounded_rectangle(left, radius=22, fill=(*THEME_PURPLE, 38))
    pd.rounded_rectangle(left, radius=22, outline=(*SOFT_PURPLE, 70), width=1)
    for i in range(55, 596):
        c = _lerp_color(THEME_BLUE, THEME_PURPLE, (i - 55) / 540)
        pd.point((314, i), fill=(*c, 200))
        pd.point((315, i), fill=(*c, 200))
    base = Image.alpha_composite(base, pl)

    base = _icon_with_orbit(base, LOGO_CX, LOGO_CY, _circle_image(logo, LOGO_SIZE), LOGO_SIZE, accent)

    tl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(tl)

    f_pill = _card_font(FONT_MEDIUM, 19)
    f_label = _card_font(FONT_LIGHT, 14)
    f_small = _card_font(FONT_REGULAR, 17)
    f_body = _card_font(FONT_REGULAR, 18)
    f_chip = _card_font(FONT_MEDIUM, 16)

    # kode kelas (kiri)
    if d.get("class_id"):
        code = f"KELAS #{int(d['class_id']):03}"
        cw = int(td.textlength(code, font=f_label)) + 34
        td.rounded_rectangle([LOGO_CX - cw // 2, 288, LOGO_CX + cw // 2, 314], radius=13,
                             fill=(*THEME_PURPLE, 90), outline=(*SOFT_PURPLE, 200), width=1)
        td.text((LOGO_CX, 301), code, font=f_label, fill=(255, 255, 255, 255), anchor="mm")

    # ring progres siswa (kiri)
    _draw_ring(td, LOGO_CX, 425, 62, ratio)
    td.text((LOGO_CX, 415), str(count), font=_card_font(FONT_BOLD, 44), fill=(255, 255, 255, 255), anchor="mm")
    td.text((LOGO_CX, 449), f"/ {MAX_MEMBER}", font=_card_font(FONT_MEDIUM, 17), fill=(*SOFT_BLUE, 230), anchor="mm")
    td.text((LOGO_CX, 520), "SISWA TERDAFTAR", font=f_label, fill=(*SOFT_BLUE, 220), anchor="mm")
    td.text((LOGO_CX, 548), f"{int(ratio * 100)}% terisi", font=f_small, fill=(255, 255, 255, 230), anchor="mm")

    # header kanan
    status_text = STATUS_LABEL.get(status, str(status).upper())
    pw = int(td.textlength(status_text, font=f_pill)) + 44
    td.rounded_rectangle([RX1 - pw, 58, RX1, 102], radius=22, fill=(*status_color, 235))
    td.text((RX1 - pw / 2, 80), status_text, font=f_pill, fill=(255, 255, 255, 255), anchor="mm")

    f_name, name_fit = _fit_font(td, d["class_name"], FONT_BOLD, 44, RX1 - RX0 - pw - 24)
    td.text((RX0, 80), name_fit, font=f_name, fill=(255, 255, 255, 255), anchor="lm")
    td.text((RX0, 134), d["motto"] or "-", font=_card_font(FONT_MEDIUM, 22), fill=(*accent, 255), anchor="lm")

    for i, line in enumerate(_wrap_lines(td, d["description"], f_body, RX1 - RX0, max_lines=2)):
        td.text((RX0, 178 + i * 27), line, font=f_body, fill=(220, 220, 240, 235), anchor="lm")

    # kotak info 3 x 2
    top, bot = 256, 394
    td.rounded_rectangle([RX0, top, RX1, bot], radius=16, fill=(*THEME_PURPLE, 30),
                         outline=(*SOFT_PURPLE, 75), width=1)

    due = d["due_date"]
    if due:
        days = (due - now).days
        remaining = f"{days} hari" if days >= 0 else f"Lewat {abs(days)} hari"
    else:
        days, remaining = None, "-"

    pairs = [
        ("STAFF PENDAMPING", d["staff_name"] or "-"),
        ("OWNER KELAS", d["owner_name"] or "-"),
        ("SISA WAKTU", remaining),
        ("BERDIRI SEJAK", d["created_at"].strftime("%d %b %Y") if d["created_at"] else "-"),
        ("AKTIF SAMPAI", due.strftime("%d %b %Y") if due else "-"),
        ("KODE KELAS", f"#{int(d['class_id']):03}" if d.get("class_id") else "-"),
    ]
    col_w = (RX1 - RX0 - 48) // 3
    for i, (label, value) in enumerate(pairs):
        col, row = i % 3, i // 3
        x = RX0 + 24 + col * col_w
        y = top + 28 + row * 62
        f_val, val_fit = _fit_font(td, value, FONT_REGULAR, 19, col_w - 18, min_size=12)
        td.text((x, y), label, font=f_label, fill=(*SOFT_BLUE, 210), anchor="lm")
        td.text((x, y + 24), val_fit, font=f_val, fill=(255, 255, 255, 245), anchor="lm")

    # slot bar
    bar_y = 424
    td.rounded_rectangle([RX0, bar_y, RX1, bar_y + 16], radius=8, fill=(50, 45, 80, 220))
    if ratio > 0:
        fx = RX0 + int((RX1 - RX0) * ratio)
        td.rounded_rectangle([RX0, bar_y, fx, bar_y + 16], radius=8,
                             fill=(*_lerp_color(THEME_BLUE, accent, 0.5), 255))
        td.ellipse([fx - 9, bar_y - 1, fx + 3, bar_y + 17], fill=(255, 255, 255, 170))
    slot_text = "PENUH" if count >= MAX_MEMBER else f"{MAX_MEMBER - count} slot tersisa"
    td.text((RX0, bar_y + 36), slot_text, font=f_label, fill=(*SOFT_BLUE, 220), anchor="lm")
    td.text((RX1, bar_y + 36), f"{count} dari {MAX_MEMBER} kursi terisi", font=f_label,
            fill=(*SOFT_PURPLE, 220), anchor="rm")

    # chips
    cy = 500
    x = RX0
    billing = d.get("billing_status")
    if billing == "Paid":
        x = _chip(td, x, cy, "Tagihan Lunas", f_chip, OK_GREEN) + 12
    elif billing == "Unpaid":
        x = _chip(td, x, cy, "Tagihan Belum Lunas", f_chip, WARN_ORANGE) + 12
    open_reg = status == "Active" and count < MAX_MEMBER
    x = _chip(td, x, cy, "Pendaftaran Dibuka" if open_reg else "Pendaftaran Ditutup",
              f_chip, THEME_BLUE if open_reg else MUTED_GRAY) + 12
    _chip(td, x, cy, f"Kapasitas {MAX_MEMBER} siswa", f_chip, SOFT_PURPLE)

    # bar masa aktif
    if days is not None:
        tr = min(max(days / 30, 0), 1)
        td.text((RX0, 540), "MASA AKTIF", font=f_label, fill=(*SOFT_BLUE, 210), anchor="lm")
        td.rounded_rectangle([RX0, 556, RX1, 566], radius=5, fill=(50, 45, 80, 220))
        if tr > 0:
            td.rounded_rectangle([RX0, 556, RX0 + int((RX1 - RX0) * tr), 566], radius=5,
                                 fill=(*_lerp_color(SOFT_PURPLE, THEME_BLUE, tr), 255))

    td.text((55, H - 42), "Berbeda Kelas, Tetap Satu Sekolah.", font=f_label, fill=(*SOFT_PURPLE, 190), anchor="lm")
    td.text((RX1 + 30, H - 42), "nanZ Server", font=f_label, fill=(*SOFT_BLUE, 190), anchor="rm")

    base = Image.alpha_composite(base, tl)
    base = _shimmer(base, CARD_RECT)

    buffer = io.BytesIO()
    base.convert("RGB").save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer


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
    owner_name=None,
    class_id=None,
    billing_status=None,
):
    """
    Panel PNG Kelas nanZ (tema ungu-biru ala welcome GIF).
    Argumen tambahan (owner_name, class_id, billing_status) opsional,
    jadi pemanggil lama tetap kompatibel.
    """
    logo = await load_logo(logo_url)

    data = {
        "class_name": class_name,
        "motto": motto,
        "description": description,
        "staff_name": staff_name,
        "owner_name": owner_name,
        "class_id": class_id,
        "billing_status": billing_status,
        "member_count": member_count,
        "status": status,
        "created_at": created_at,
        "due_date": due_date,
    }

    return await _run_blocking(
        _render_class_card_sync, data, logo, hex_rgb(color_hex)
    )


# ---------- gambar: BANNER panel ----------

def _render_banner_sync(title, subtitle, badge, chips, icon, accent):
    W, H = 1000, 300
    accent = accent or THEME_PURPLE

    base = _backdrop(W, H, 11)
    rect = (20, 20, W - 20, H - 20)
    base = _glass_card(base, rect, radius=28)

    ICON = 120
    cx, cy = 140, H // 2
    base = _icon_with_orbit(base, cx, cy, _circle_image(icon, ICON), ICON, accent)

    tl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(tl)

    for i in range(50, H - 50):
        c = _lerp_color(THEME_BLUE, THEME_PURPLE, (i - 50) / (H - 100))
        td.point((262, i), fill=(*c, 200))
        td.point((263, i), fill=(*c, 200))

    TX0, TX1 = 292, W - 56
    f_badge = _card_font(FONT_MEDIUM, 16)
    bw = 0
    if badge:
        bw = int(td.textlength(badge, font=f_badge)) + 36
        td.rounded_rectangle([TX1 - bw, 46, TX1, 78], radius=16, fill=(*accent, 235))
        td.text((TX1 - bw / 2, 62), badge, font=f_badge, fill=(255, 255, 255, 255), anchor="mm")

    f_title, title_fit = _fit_font(td, title, FONT_BOLD, 40, TX1 - TX0 - bw - 20, min_size=20)
    td.text((TX0, 66), title_fit, font=f_title, fill=(255, 255, 255, 255), anchor="lm")

    if subtitle:
        f_sub, sub_fit = _fit_font(td, subtitle, FONT_MEDIUM, 22, TX1 - TX0, min_size=14)
        td.text((TX0, 112), sub_fit, font=f_sub, fill=(*accent, 255), anchor="lm")

    # chips info
    chips = list(chips)[:3]
    if chips:
        gap = 14
        cw = (TX1 - TX0 - gap * (len(chips) - 1)) // len(chips)
        f_l = _card_font(FONT_LIGHT, 12)
        for i, (label, value) in enumerate(chips):
            x = TX0 + i * (cw + gap)
            td.rounded_rectangle([x, 158, x + cw, 232], radius=14, fill=(*THEME_PURPLE, 34),
                                 outline=(*SOFT_PURPLE, 90), width=1)
            td.text((x + 16, 180), str(label).upper(), font=f_l, fill=(*SOFT_BLUE, 220), anchor="lm")
            f_v, v_fit = _fit_font(td, str(value), FONT_MEDIUM, 20, cw - 32, min_size=12)
            td.text((x + 16, 208), v_fit, font=f_v, fill=(255, 255, 255, 250), anchor="lm")

    td.text((TX0, H - 42), "nanZ Server  •  Berbeda Kelas, Tetap Satu Sekolah.",
            font=_card_font(FONT_LIGHT, 13), fill=(*SOFT_PURPLE, 190), anchor="lm")

    base = Image.alpha_composite(base, tl)
    base = _shimmer(base, rect, radius=28, pos=0.7)

    buffer = io.BytesIO()
    base.convert("RGB").save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer


async def make_banner_file(
    *,
    title,
    subtitle="",
    badge=None,
    chips=(),
    icon=None,
    accent=None,
    filename=BANNER_NAME,
):
    """Buat banner PNG bertema nanZ sebagai discord.File siap kirim."""
    buffer = await _run_blocking(
        _render_banner_sync, title, subtitle, badge, list(chips), icon, accent
    )
    return discord.File(buffer, filename=filename)


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

    owner = bot.get_user(int(cls["owner_id"])) if cls["owner_id"] else None
    owner_name = owner.display_name if owner else f"User {cls['owner_id']}"

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
        owner_name=owner_name,
        class_id=class_id,
        billing_status=cls.get("billing_status"),
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
                "<a:question:1553688505929044000> Format warna tidak valid. Gunakan `#5865F2`.",
                ephemeral=True,
            )
            return

        if not interaction.guild:
            await interaction.response.send_message(
                "<a:question:1553688505929044000> Form ini hanya dapat digunakan di server.",
                ephemeral=True,
            )
            return

        if not interaction.user:
            return

        existing = await get_user_class(self.owner_id)
        if existing:
            await interaction.response.send_message(
                f"<a:question:1553688505929044000> Kamu sudah tergabung di **{existing['name']}**.\n"
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
                "<a:question:1553688505929044000> Kamu masih memiliki pengajuan kelas yang sedang diproses.",
                ephemeral=True,
            )
            return

        # get_channel() hanya mencari cache Discord. Jika channel belum masuk
        # cache, fallback ke fetch_channel() agar ID yang benar tetap ditemukan.
        approval_channel = interaction.guild.get_channel(APPROVAL_CHANNEL_ID)
        if not approval_channel:
            try:
                approval_channel = await interaction.guild.fetch_channel(APPROVAL_CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                approval_channel = None

        if not approval_channel:
            await interaction.response.send_message(
                "<a:question:1553688505929044000> Channel `approval-kelas` tidak ditemukan atau bot tidak memiliki akses ke channel tersebut.",
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
            banner = await make_banner_file(
                title="Pengajuan Kelas Baru",
                subtitle=name,
                badge="MENUNGGU",
                chips=[
                    ("Pemohon", interaction.user.display_name),
                    ("Request ID", f"#{request_id}"),
                    ("Warna", color_hex),
                ],
                icon=await load_avatar(interaction.user),
                accent=hex_rgb(color_hex),
            )
            await approval_channel.send(
                embed=embed,
                file=banner,
                view=ClassApprovalView(request_id),
            )
        except Exception:
            log.exception("Gagal mengirim approval kelas.")
            await execute(
                "DELETE FROM nanz_class_creation_requests WHERE request_id=%s",
                (request_id,),
            )
            await interaction.followup.send(
                "<a:question:1553688505929044000> Gagal mengirim pengajuan ke `approval-kelas`.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            "<:verified:1553690488257908837> Pengajuan kelas berhasil dikirim ke `approval-kelas`.\n"
            "Staff akan memilih Staff Pendamping terlebih dahulu sebelum kelas dapat disetujui.",
            ephemeral=True,
        )


def build_creation_request_embed(request_id, request):
    staff_id = int(request.get("staff_id") or 0)

    steps = (
        f"{'<:verified:1553690488257908837>' if staff_id else '<a:arrow_purple:1512787191234035803>'} **1.** Pilih Staff Pendamping\n"
        "<a:arrow_purple:1512787191234035803> **2.** Approve atau Reject pengajuan"
    )

    embed = discord.Embed(
        title="<a:arrow_blue:1512787254312042496> Pengajuan Kelas Baru",
        description=(
            f"**{request['name']}**\n"
            f"*“{request['motto']}”*\n"
            f"{DIVIDER}\n"
            f"{request['description']}"
        ),
        color=discord.Color.from_str(request["color_hex"]),
        timestamp=utc_now(),
    )

    embed.add_field(name="<a:arrow_blue:1512787254312042496> Pemilik", value=f"<@{request['owner_id']}>", inline=True)
    embed.add_field(
        name="<a:arrow_blue:1512787254312042496> Staff Pendamping",
        value=f"<@{staff_id}>" if staff_id else "<a:question:1553688505929044000> Belum dipilih",
        inline=True,
    )
    embed.add_field(name="<a:pin:1553688245769085099> Request ID", value=f"`#{request_id}`", inline=True)
    embed.add_field(name="<a:pin:1553688245769085099> Warna Kelas", value=f"`{request['color_hex']}`", inline=True)
    embed.add_field(
        name="<a:pin:1553688245769085099> Logo",
        value="<:verified:1553690488257908837> Terlampir" if request.get("logo_url") else "<a:arrow_purple:1512787191234035803> Default nZ",
        inline=True,
    )
    embed.add_field(name="<a:arrow_blue:1512787254312042496> Status", value="<a:question:1553688505929044000> Menunggu", inline=True)
    embed.add_field(name="<a:arrow_blue:1512787254312042496> Langkah Proses", value=steps, inline=False)

    if request.get("logo_url"):
        embed.set_thumbnail(url=request["logo_url"])

    embed.set_image(url=f"attachment://{BANNER_NAME}")

    return style_embed(embed)


# =========================================================
# FORM TRIGGER
# =========================================================

class ClassFormTriggerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        button = discord.ui.Button(
            label="Buka Form Kelas",
            emoji="<a:arrow_blue:1512787254312042496>",
            style=discord.ButtonStyle.primary,
            custom_id="nanz:open_class_form",
        )
        button.callback = self.open_form
        self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction):
        if not has_staff_role(interaction.user):
            await interaction.response.send_message(
                "<a:gear:1553688352564183051> Panel pembuatan kelas hanya dapat digunakan Staff atau Administrator.",
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
            emoji="<a:arrow_blue:1512787254312042496>",
            style=discord.ButtonStyle.secondary,
            custom_id="nanz:staff_dashboard:refresh",
        )
        refresh.callback = self.refresh_dashboard
        self.add_item(refresh)

    async def interaction_check(self, interaction):
        if not has_staff_role(interaction.user):
            await interaction.response.send_message(
                "<a:gear:1553688352564183051> Dashboard ini khusus Staff dan Administrator.",
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
                "<a:question:1553688505929044000> Voice channel tersebut bukan Voice Channel kelas yang terdaftar.",
                ephemeral=True,
            )
            return

        if not can_manage_class(interaction.user, cls):
            await interaction.response.send_message(
                "<a:gear:1553688352564183051> Kamu hanya dapat mengelola kelas yang Staff Pendamping-nya adalah kamu. Administrator dapat mengakses semua kelas.",
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
    embed = discord.Embed(
        title="<:verified:1553690488257908837> Pusat Kendali Kelas nanZ",
        description=(
            "Selamat datang di **Dashboard Staff**!\n"
            "Kelola seluruh Kelas nanZ dari satu tempat.\n"
            f"{DIVIDER}"
        ),
        color=EMBED_PURPLE,
    )

    embed.add_field(
        name="<a:arrow_purple:1512787191234035803> Cara Menggunakan",
        value=(
            "**1.** Pilih Voice Channel kelas di menu bawah\n"
            "**2.** Panel management muncul khusus untukmu\n"
            "**3.** Edit info, kelola member, ganti staff, atau perpanjang masa aktif"
        ),
        inline=False,
    )
    embed.add_field(
        name="<a:gear:1553688352564183051> Hak Akses",
        value=(
            "• **Staff Pendamping** → mengelola kelas yang dipegangnya\n"
            "• **Administrator** → akses ke semua kelas\n"
            "• **Owner & Staff** → memproses request gabung di `request-gabung`"
        ),
        inline=False,
    )
    embed.add_field(
        name="<:verified:1553690488257908837> Fitur Tersedia",
        value=(
            "`<a:arrow_blue:1512787254312042496> Kelola Member`  `<a:arrow_blue:1512787254312042496> Edit Kelas`  `<a:arrow_blue:1512787254312042496> Ganti Staff`\n"
            "`<a:arrow_blue:1512787254312042496> Perpanjang`  `<a:question:1553688505929044000> Bubarkan`  `<a:arrow_blue:1512787254312042496> Refresh`"
        ),
        inline=False,
    )

    embed.set_image(url=f"attachment://{BANNER_NAME}")

    # marker dipakai ensure_staff_dashboard untuk menemukan pesan ini
    return style_embed(embed, footer=f"{DASHBOARD_MARKER} • nanZ Server")


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
            emoji="<:verified:1553690488257908837>",
            style=discord.ButtonStyle.success,
            custom_id=f"nanz:class_approve:{self.request_id}",
        )
        approve.callback = self.approve
        self.add_item(approve)

        reject = discord.ui.Button(
            label="Reject Kelas",
            emoji="<a:question:1553688505929044000>",
            style=discord.ButtonStyle.danger,
            custom_id=f"nanz:class_reject:{self.request_id}",
        )
        reject.callback = self.reject
        self.add_item(reject)

    async def interaction_check(self, interaction):
        if not has_staff_role(interaction.user):
            await interaction.response.send_message(
                "<a:gear:1553688352564183051> Hanya Staff atau Administrator yang dapat memproses pengajuan kelas.",
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
            await interaction.response.send_message("<a:question:1553688505929044000> Pengajuan tidak ditemukan.", ephemeral=True)
            return

        if request["status"] != "Pending":
            await interaction.response.send_message("<a:question:1553688505929044000> Pengajuan ini sudah diproses.", ephemeral=True)
            return

        selected = self.staff_select.values[0]
        staff_member = interaction.guild.get_member(int(selected.id))

        if not staff_member or not is_valid_staff(staff_member):
            await interaction.response.send_message(
                "<a:question:1553688505929044000> User yang dipilih tidak memiliki Role Staff yang sah.",
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
            await interaction.response.send_message("<a:question:1553688505929044000> Data pengajuan tidak ditemukan.", ephemeral=True)
            return

        if request["status"] != "Pending":
            await interaction.response.send_message(
                f"<a:question:1553688505929044000> Pengajuan ini sudah berstatus `{request['status']}`.",
                ephemeral=True,
            )
            return

        staff_id = int(request["staff_id"] or 0)
        if staff_id <= 0:
            await interaction.response.send_message(
                "<a:question:1553688505929044000> Pilih Staff Pendamping terlebih dahulu sebelum Approve.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        owner = guild.get_member(int(request["owner_id"]))
        staff = guild.get_member(staff_id)

        if not owner:
            await interaction.response.send_message(
                "<a:question:1553688505929044000> Pemilik kelas sudah tidak berada di server.",
                ephemeral=True,
            )
            return

        if not staff or not is_valid_staff(staff):
            await interaction.response.send_message(
                "<a:question:1553688505929044000> Staff Pendamping tidak valid atau sudah tidak memiliki Role Staff.",
                ephemeral=True,
            )
            return

        existing = await get_user_class(owner.id)
        if existing:
            await interaction.response.send_message(
                f"<a:question:1553688505929044000> Pemilik sudah memiliki kelas **{existing['name']}**.",
                ephemeral=True,
            )
            return

        category = guild.get_channel(RUANG_KELAS_CATEGORY_ID)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                "<a:question:1553688505929044000> Category ruang kelas tidak ditemukan.",
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
                    f"<a:arrow_blue:1512787254312042496> **{request['name']}** resmi berdiri!\n"
                    f"Staff Pendamping: <@{staff_id}>\n"
                    f"Pemilik: <@{request['owner_id']}>\n\n"
                    "**Berbeda Kelas, Tetap Satu Sekolah.**"
                )
            except Exception:
                pass

            embed = discord.Embed(
                title="<a:arrow_blue:1512787254312042496> Kelas Resmi Berdiri!",
                description=(
                    f"**{request['name']}**\n"
                    f"*“{request['motto']}”*\n"
                    f"{DIVIDER}\n"
                    "Selamat! Kelas baru sudah aktif dan siap menerima siswa. <:verified:1553690488257908837>"
                ),
                color=discord.Color.from_str(request["color_hex"]),
                timestamp=utc_now(),
            )
            embed.add_field(name="<a:arrow_blue:1512787254312042496> Pemilik", value=f"<@{request['owner_id']}>", inline=True)
            embed.add_field(name="<a:arrow_blue:1512787254312042496> Staff Pendamping", value=f"<@{staff_id}>", inline=True)
            embed.add_field(name="<a:pin:1553688245769085099> Class ID", value=f"`#{class_id}`", inline=True)
            embed.add_field(name="<a:pin:1553688245769085099> Voice Channel", value=voice.mention, inline=True)
            embed.add_field(name="<a:pin:1553688245769085099> Role Kelas", value=role.mention, inline=True)
            embed.add_field(name="<:verified:1553690488257908837> Disetujui oleh", value=interaction.user.mention, inline=True)
            embed.add_field(name="<a:question:1553688505929044000> Aktif Sampai", value=stamp(due_date, "F"), inline=False)
            embed.set_image(url=f"attachment://{BANNER_NAME}")
            style_embed(embed)

            result_banner = await make_banner_file(
                title="Kelas Disetujui",
                subtitle=request["name"],
                badge="APPROVED",
                chips=[
                    ("Pemilik", owner.display_name),
                    ("Staff", staff.display_name),
                    ("Class ID", f"#{class_id}"),
                ],
                icon=await load_avatar(owner),
                accent=OK_GREEN,
            )

            await interaction.message.edit(embed=embed, attachments=[result_banner], view=None)

            await send_log(
                interaction.client,
                guild,
                f"<a:arrow_blue:1512787254312042496> Kelas **{request['name']}** dibuat oleh <@{interaction.user.id}>. "
                f"Staff: <@{staff_id}>. Class ID: `{class_id}`.",
            )

            await interaction.followup.send(
                f"<:verified:1553690488257908837> Kelas **{request['name']}** berhasil dibuat.",
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
                "<a:question:1553688505929044000> Gagal membuat kelas.\n"
                f"Error: `{type(exc).__name__}`",
                ephemeral=True,
            )

    async def reject(self, interaction):
        request = await self.get_request()
        if not request:
            await interaction.response.send_message("<a:question:1553688505929044000> Pengajuan tidak ditemukan.", ephemeral=True)
            return

        if request["status"] != "Pending":
            await interaction.response.send_message("<a:question:1553688505929044000> Pengajuan ini sudah diproses.", ephemeral=True)
            return

        await execute(
            """
            UPDATE nanz_class_creation_requests
            SET status='Rejected', processed_at=%s, processed_by=%s
            WHERE request_id=%s
            """,
            (db_now(), interaction.user.id, self.request_id),
        )

        applicant = interaction.guild.get_member(int(request["owner_id"]))

        embed = discord.Embed(
            title="<a:question:1553688505929044000> Pengajuan Kelas Ditolak",
            description=(
                f"**{request['name']}**\n"
                f"{DIVIDER}\n"
                "Pengajuan ini tidak disetujui oleh Staff."
            ),
            color=discord.Color.from_rgb(*BAD_RED),
            timestamp=utc_now(),
        )
        embed.add_field(name="<a:arrow_blue:1512787254312042496> Pemohon", value=f"<@{request['owner_id']}>", inline=True)
        embed.add_field(name="<:verified:1553690488257908837> Diproses oleh", value=interaction.user.mention, inline=True)
        embed.add_field(name="<a:pin:1553688245769085099> Request ID", value=f"`#{self.request_id}`", inline=True)
        embed.set_image(url=f"attachment://{BANNER_NAME}")
        style_embed(embed)

        result_banner = await make_banner_file(
            title="Pengajuan Ditolak",
            subtitle=request["name"],
            badge="REJECTED",
            chips=[
                ("Pemohon", applicant.display_name if applicant else "-"),
                ("Diproses", interaction.user.display_name),
                ("Request ID", f"#{self.request_id}"),
            ],
            accent=BAD_RED,
        )

        await interaction.response.edit_message(embed=embed, attachments=[result_banner], view=None)

        await send_log(
            interaction.client,
            interaction.guild,
            f"<a:question:1553688505929044000> Pengajuan kelas **{request['name']}** ditolak oleh {interaction.user.mention}.",
        )


# =========================================================
# CLASS MANAGEMENT MODALS / VIEWS
# =========================================================

async def build_class_management_embed(bot, class_id):
    cls = await get_class(class_id)
    if not cls:
        return discord.Embed(
            title="<a:question:1553688505929044000> Kelas tidak ditemukan",
            color=discord.Color.red(),
        )

    count = await get_member_count(class_id)
    staff_id = int(cls["staff_id"] or 0)
    status = str(cls["status"])

    embed = discord.Embed(
        title=f"<a:gear:1553688352564183051> Kelola Kelas — {cls['name']}",
        description=(
            f"*“{cls['motto'] or '-'}”*\n"
            f"{DIVIDER}\n"
            f"{cls['description'] or '-'}"
        ),
        color=discord.Color.from_str(cls["color_hex"]),
        timestamp=utc_now(),
    )

    embed.add_field(name="<a:arrow_purple:1512787191234035803> Owner", value=f"<@{cls['owner_id']}>", inline=True)
    embed.add_field(
        name="<a:arrow_blue:1512787254312042496> Staff Pendamping",
        value=f"<@{staff_id}>" if staff_id else "-",
        inline=True,
    )
    embed.add_field(name="<a:arrow_blue:1512787254312042496> Status", value=STATUS_META.get(status, status), inline=True)

    embed.add_field(
        name="<a:arrow_blue:1512787254312042496> Anggota",
        value=f"`{slot_bar(count)}`\n**{count}/{MAX_MEMBER}** siswa • {max(MAX_MEMBER - count, 0)} slot tersisa",
        inline=True,
    )
    embed.add_field(
        name="<a:dollar:1553688127103705290> Tagihan",
        value=BILLING_META.get(str(cls.get("billing_status")), "-"),
        inline=True,
    )
    embed.add_field(name="<a:pin:1553688245769085099> Class ID", value=f"`#{cls['class_id']}`", inline=True)

    embed.add_field(name="<a:pin:1553688245769085099> Berdiri Sejak", value=stamp(cls["created_at"], "D"), inline=True)
    embed.add_field(
        name="<a:question:1553688505929044000> Aktif Sampai",
        value=f"{stamp(cls['due_date'], 'D')}\n{stamp(cls['due_date'], 'R')}",
        inline=True,
    )
    embed.add_field(
        name="<a:arrow_purple:1512787191234035803> Batas Grace",
        value=f"{stamp(cls['grace_until'], 'D')}\n{stamp(cls['grace_until'], 'R')}",
        inline=True,
    )

    if cls.get("vc_id"):
        embed.add_field(name="<a:pin:1553688245769085099> Voice Channel", value=f"<#{cls['vc_id']}>", inline=True)
    if cls.get("role_id"):
        embed.add_field(name="<a:pin:1553688245769085099> Role Kelas", value=f"<@&{cls['role_id']}>", inline=True)

    if cls.get("logo_url"):
        embed.set_thumbnail(url=cls["logo_url"])

    return style_embed(embed, footer="Panel Kelola Kelas • nanZ Server")


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
            await interaction.response.send_message("<a:question:1553688505929044000> Kelas tidak tersedia.", ephemeral=True)
            return

        if not can_manage_class(interaction.user, cls):
            await interaction.response.send_message("<a:gear:1553688352564183051> Kamu tidak memiliki akses ke kelas ini.", ephemeral=True)
            return

        name = clean_text(self.name_input.value, 50)
        motto = clean_text(self.motto_input.value, 100) or "-"
        description = clean_text(self.description_input.value, 300)
        color_hex = clean_text(self.color_input.value, 7).upper()
        logo_url = clean_text(self.logo_input.value, 500) or None

        if not valid_hex(color_hex):
            await interaction.response.send_message("<a:question:1553688505929044000> Warna harus format `#RRGGBB`.", ephemeral=True)
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
            f"<a:arrow_blue:1512787254312042496> Kelas **{name}** diperbarui oleh {interaction.user.mention}.",
        )

        await interaction.followup.send("<:verified:1553690488257908837> Informasi kelas berhasil diperbarui.", ephemeral=True)


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
            await interaction.response.send_message("<a:gear:1553688352564183051> Kamu tidak memiliki akses.", ephemeral=True)
            return False
        return True

    async def change_staff(self, interaction):
        selected = self.staff_select.values[0]
        staff = interaction.guild.get_member(int(selected.id))
        if not staff or not is_valid_staff(staff):
            await interaction.response.send_message(
                "<a:question:1553688505929044000> User yang dipilih bukan Staff yang valid.",
                ephemeral=True,
            )
            return

        cls = await get_class(self.class_id)
        if not cls or not can_manage_class(interaction.user, cls):
            await interaction.response.send_message("<a:gear:1553688352564183051> Akses ditolak.", ephemeral=True)
            return

        old_staff = int(cls["staff_id"] or 0)
        await execute(
            "UPDATE nanz_classes SET staff_id=%s WHERE class_id=%s",
            (staff.id, self.class_id),
        )

        await update_public_panel(interaction.client, self.class_id)
        await interaction.response.send_message(
            f"<:verified:1553690488257908837> Staff kelas diganti menjadi {staff.mention}.",
            ephemeral=True,
        )

        await send_log(
            interaction.client,
            interaction.guild,
            f"<a:arrow_blue:1512787254312042496> Staff kelas **{cls['name']}** diganti dari "
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
            emoji="<a:question:1553688505929044000>",
            style=discord.ButtonStyle.danger,
            custom_id=f"nanz:member_manage:kick:{self.class_id}",
        )
        kick.callback = self.kick_selected
        self.add_item(kick)

    async def interaction_check(self, interaction):
        cls = await get_class(self.class_id)
        if not cls or not can_manage_class(interaction.user, cls):
            await interaction.response.send_message("<a:gear:1553688352564183051> Kamu tidak memiliki akses.", ephemeral=True)
            return False
        return True

    async def select_member(self, interaction):
        selected = self.member_select.values[0]
        self.selected_user_id = int(selected.id)
        await interaction.response.send_message(
            embed=style_embed(
                discord.Embed(
                    title="<a:arrow_blue:1512787254312042496> Anggota Terpilih",
                    description=(
                        f"<@{self.selected_user_id}>\n{DIVIDER}\n"
                        "Tekan **<a:question:1553688505929044000> Keluarkan** untuk menghapusnya dari kelas."
                    ),
                    color=EMBED_BLUE,
                )
            ),
            ephemeral=True,
        )

    async def kick_selected(self, interaction):
        if not self.selected_user_id:
            await interaction.response.send_message("<a:question:1553688505929044000> Pilih anggota terlebih dahulu.", ephemeral=True)
            return

        cls = await get_class(self.class_id)
        if not cls or not can_manage_class(interaction.user, cls):
            await interaction.response.send_message("<a:gear:1553688352564183051> Akses ditolak.", ephemeral=True)
            return

        if self.selected_user_id == int(cls["owner_id"]):
            await interaction.response.send_message("<a:question:1553688505929044000> Owner kelas tidak dapat dikeluarkan.", ephemeral=True)
            return

        member_row = await fetch_one(
            "SELECT user_id FROM nanz_class_members WHERE class_id=%s AND user_id=%s LIMIT 1",
            (self.class_id, self.selected_user_id),
        )
        if not member_row:
            await interaction.response.send_message("<a:question:1553688505929044000> User bukan anggota kelas ini.", ephemeral=True)
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
            f"<:verified:1553690488257908837> <@{self.selected_user_id}> dikeluarkan dari **{cls['name']}**.",
            ephemeral=True,
        )

        await send_log(
            interaction.client,
            interaction.guild,
            f"<a:question:1553688505929044000> <@{self.selected_user_id}> dikeluarkan dari **{cls['name']}** oleh {interaction.user.mention}.",
        )


class ClassDeleteConfirmView(discord.ui.View):
    def __init__(self, class_id):
        super().__init__(timeout=60)
        self.class_id = int(class_id)

        confirm = discord.ui.Button(
            label="Ya, Bubarkan",
            emoji="<a:question:1553688505929044000>",
            style=discord.ButtonStyle.danger,
            custom_id=f"nanz:delete_confirm:{self.class_id}",
        )
        confirm.callback = self.confirm_delete
        self.add_item(confirm)

        cancel = discord.ui.Button(
            label="Batal",
            emoji="<a:arrow_purple:1512787191234035803>",
            style=discord.ButtonStyle.secondary,
            custom_id=f"nanz:delete_cancel:{self.class_id}",
        )
        cancel.callback = self.cancel
        self.add_item(cancel)

    async def confirm_delete(self, interaction):
        cls = await get_class(self.class_id)
        if not cls or not can_manage_class(interaction.user, cls):
            await interaction.response.send_message("<a:gear:1553688352564183051> Akses ditolak.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await dissolve_class(interaction.client, interaction.guild, self.class_id, interaction.user.id)
        await interaction.followup.send(f"<a:question:1553688505929044000> Kelas **{cls['name']}** berhasil dibubarkan.", ephemeral=True)

    async def cancel(self, interaction):
        await interaction.response.edit_message(content="<a:question:1553688505929044000> Pembubaran dibatalkan.", view=None)


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
        f"<a:question:1553688505929044000> Kelas **{cls['name']}** (ID `{class_id}`) dibubarkan oleh <@{actor_id}>.",
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
        f"<a:arrow_blue:1512787254312042496> Kelas **{cls['name']}** diperpanjang oleh <@{actor_id}> sampai <t:{int(due.timestamp())}:F>.",
    )
    return due


class ClassManagementView(discord.ui.View):
    def __init__(self, class_id):
        super().__init__(timeout=300)
        self.class_id = int(class_id)

        actions = [
            ("Kelola Member", "<a:arrow_blue:1512787254312042496>", discord.ButtonStyle.primary, self.manage_members, "members"),
            ("Edit Kelas", "<a:arrow_blue:1512787254312042496>", discord.ButtonStyle.secondary, self.edit_class, "edit"),
            ("Ganti Staff", "<a:arrow_blue:1512787254312042496>", discord.ButtonStyle.secondary, self.change_staff, "staff"),
            ("Perpanjang", "<a:arrow_blue:1512787254312042496>", discord.ButtonStyle.success, self.extend, "extend"),
            ("Hapus Kelas", "<a:question:1553688505929044000>", discord.ButtonStyle.danger, self.delete_class, "delete"),
            ("Refresh", "<a:arrow_blue:1512787254312042496>", discord.ButtonStyle.secondary, self.refresh, "refresh"),
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
                "<a:gear:1553688352564183051> Panel ini hanya dapat digunakan Staff Pendamping kelas atau Administrator.",
                ephemeral=True,
            )
            return False
        return True

    async def manage_members(self, interaction):
        embed = discord.Embed(
            title="<a:arrow_blue:1512787254312042496> Kelola Anggota",
            description=(
                f"{DIVIDER}\n"
                "**1.** Pilih anggota dari menu di bawah\n"
                "**2.** Tekan **<a:question:1553688505929044000> Keluarkan** untuk menghapusnya dari kelas\n\n"
                "*Owner kelas tidak dapat dikeluarkan.*"
            ),
            color=EMBED_PURPLE,
        )
        await interaction.response.send_message(
            embed=style_embed(embed),
            view=ClassMemberManageView(self.class_id),
            ephemeral=True,
        )

    async def edit_class(self, interaction):
        modal = await ClassEditModal.create(self.class_id)
        await interaction.response.send_modal(modal)

    async def change_staff(self, interaction):
        await interaction.response.send_message(
            "<a:arrow_blue:1512787254312042496> Pilih Staff baru:",
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
            await interaction.response.send_message("<a:question:1553688505929044000> Kelas tidak ditemukan.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"<:verified:1553690488257908837> Kelas diperpanjang sampai <t:{int(due.timestamp())}:F>.",
            ephemeral=True,
        )

    async def delete_class(self, interaction):
        cls = await get_class(self.class_id)
        if not cls:
            await interaction.response.send_message("<a:question:1553688505929044000> Kelas tidak ditemukan.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"<a:question:1553688505929044000> Bubarkan {cls['name']}?",
            description=(
                f"{DIVIDER}\n"
                "Tindakan ini **tidak dapat dibatalkan** dan akan:\n\n"
                "<a:question:1553688505929044000> Menghapus panel publik kelas\n"
                "<a:pin:1553688245769085099> Menghapus Voice Channel kelas\n"
                "<a:pin:1553688245769085099> Menghapus role kelas\n"
                "<a:arrow_blue:1512787254312042496> Menghapus seluruh data anggota\n"
                "<:ticket:1553686732883628102> Membatalkan request gabung yang pending"
            ),
            color=discord.Color.from_rgb(*BAD_RED),
        )
        await interaction.response.send_message(
            embed=style_embed(embed, footer="Konfirmasi dalam 60 detik"),
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
            ("Daftar Kelas", "<a:arrow_blue:1512787254312042496>", discord.ButtonStyle.primary, self.join_class, "join"),
            ("Lihat Anggota", "<a:arrow_blue:1512787254312042496>", discord.ButtonStyle.secondary, self.view_members, "members"),
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
            await interaction.response.send_message("<a:question:1553688505929044000> Kelas tidak ditemukan.", ephemeral=True)
            return

        if cls["status"] != "Active":
            await interaction.response.send_message("<a:question:1553688505929044000> Kelas ini sedang tidak menerima anggota baru.", ephemeral=True)
            return

        existing = await get_user_class(interaction.user.id)
        if existing:
            await interaction.response.send_message(
                f"<a:question:1553688505929044000> Kamu sudah tergabung di **{existing['name']}**.\nSatu member hanya boleh memiliki satu kelas.",
                ephemeral=True,
            )
            return

        count = await get_member_count(self.class_id)
        if count >= MAX_MEMBER:
            await interaction.response.send_message("<a:question:1553688505929044000> Kelas ini sudah penuh.", ephemeral=True)
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
            await interaction.response.send_message("<a:question:1553688505929044000> Request kamu masih diproses.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

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
            await interaction.followup.send(
                "<a:question:1553688505929044000> Channel `request-gabung` tidak tersedia. Request dibatalkan agar tidak menggantung.",
                ephemeral=True,
            )
            return

        applicant = interaction.user

        embed = discord.Embed(
            title="<:ticket:1553686732883628102> Request Gabung Kelas",
            description=(
                f"{applicant.mention} ingin bergabung ke **{cls['name']}**\n"
                f"{DIVIDER}\n"
                "Menunggu keputusan **Owner**, **Staff Pendamping**, atau **Administrator**."
            ),
            color=EMBED_BLUE,
            timestamp=utc_now(),
        )
        embed.add_field(name="<a:arrow_blue:1512787254312042496> Pemohon", value=applicant.mention, inline=True)
        embed.add_field(name="<a:arrow_blue:1512787254312042496> Kelas", value=cls["name"], inline=True)
        embed.add_field(name="<a:pin:1553688245769085099> Request ID", value=f"`#{request_id}`", inline=True)
        embed.add_field(name="<a:arrow_purple:1512787191234035803> Owner", value=f"<@{cls['owner_id']}>", inline=True)
        embed.add_field(name="<a:arrow_blue:1512787254312042496> Staff", value=f"<@{cls['staff_id']}>", inline=True)
        embed.add_field(
            name="<a:arrow_blue:1512787254312042496> Kapasitas",
            value=f"`{slot_bar(count)}`\n**{count}/{MAX_MEMBER}** siswa",
            inline=True,
        )
        embed.add_field(name="<a:pin:1553688245769085099> Akun Dibuat", value=stamp(applicant.created_at, "R"), inline=True)
        embed.add_field(
            name="<:ticket:1553686732883628102> Masuk Server",
            value=stamp(getattr(applicant, "joined_at", None), "R"),
            inline=True,
        )
        embed.set_thumbnail(url=applicant.display_avatar.url)
        embed.set_image(url=f"attachment://{BANNER_NAME}")
        style_embed(embed)

        try:
            banner = await make_banner_file(
                title="Request Gabung Kelas",
                subtitle=cls["name"],
                badge="PENDING",
                chips=[
                    ("Pemohon", applicant.display_name),
                    ("Kelas", cls["name"]),
                    ("Kapasitas", f"{count}/{MAX_MEMBER}"),
                ],
                icon=await load_avatar(applicant),
                accent=hex_rgb(cls["color_hex"]),
            )
            await request_channel.send(
                content=f"<@{cls['staff_id']}>",
                embed=embed,
                file=banner,
                view=JoinRequestView(request_id),
            )
        except Exception:
            log.exception("Gagal mengirim request gabung.")
            await execute(
                "DELETE FROM nanz_class_join_requests WHERE request_id=%s",
                (request_id,),
            )
            await interaction.followup.send(
                "<a:question:1553688505929044000> Gagal mengirim request. Silakan coba lagi.",
                ephemeral=True,
            )
            return

        done = discord.Embed(
            title="<:verified:1553690488257908837> Request Terkirim!",
            description=(
                f"Permintaan bergabung ke **{cls['name']}** sudah dikirim.\n"
                f"{DIVIDER}\n"
                "Tunggu persetujuan dari Owner atau Staff Pendamping ya."
            ),
            color=discord.Color.from_rgb(*OK_GREEN),
        )
        await interaction.followup.send(embed=style_embed(done), ephemeral=True)

    async def view_members(self, interaction):
        cls = await get_class(self.class_id)
        if not cls:
            await interaction.response.send_message("<a:question:1553688505929044000> Kelas tidak ditemukan.", ephemeral=True)
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

        owner_id = int(cls["owner_id"] or 0)
        staff_id = int(cls["staff_id"] or 0)

        lines = []
        for index, row in enumerate(members, start=1):
            uid = int(row["user_id"])
            icon = "<a:arrow_purple:1512787191234035803>" if uid == owner_id else "<a:arrow_blue:1512787254312042496>"
            lines.append(f"`{index:02}` {icon} <@{uid}> • {stamp(row['joined_at'], 'R')}")

        total = len(members)

        embed = discord.Embed(
            title=f"<a:arrow_blue:1512787254312042496> Daftar Siswa — {cls['name']}",
            description=(
                f"*“{cls['motto'] or '-'}”*\n"
                f"{DIVIDER}\n"
                + "\n".join(lines)
            ),
            color=discord.Color.from_str(cls["color_hex"]),
            timestamp=utc_now(),
        )
        embed.add_field(
            name="<a:arrow_blue:1512787254312042496> Kapasitas",
            value=f"`{slot_bar(total)}`\n**{total}/{MAX_MEMBER}** siswa • {max(MAX_MEMBER - total, 0)} slot tersisa",
            inline=True,
        )
        embed.add_field(name="<a:arrow_blue:1512787254312042496> Staff Pendamping", value=f"<@{staff_id}>" if staff_id else "-", inline=True)
        embed.add_field(name="<a:pin:1553688245769085099> Status", value=STATUS_META.get(str(cls["status"]), str(cls["status"])), inline=True)

        if cls.get("logo_url"):
            embed.set_thumbnail(url=cls["logo_url"])

        style_embed(embed, footer=f"<a:arrow_purple:1512787191234035803> Owner • <a:arrow_blue:1512787254312042496> Siswa • Total {total}/{MAX_MEMBER}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# =========================================================
# JOIN REQUEST VIEW
# =========================================================

class JoinRequestView(discord.ui.View):
    def __init__(self, request_id):
        super().__init__(timeout=None)
        self.request_id = int(request_id)

        approve = discord.ui.Button(
            label="Terima",
            emoji="<:verified:1553690488257908837>",
            style=discord.ButtonStyle.success,
            custom_id=f"nanz:class_join_approve:{self.request_id}",
        )
        approve.callback = self.approve
        self.add_item(approve)

        reject = discord.ui.Button(
            label="Tolak",
            emoji="<a:question:1553688505929044000>",
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
            await interaction.response.send_message("<a:question:1553688505929044000> Request tidak ditemukan.", ephemeral=True)
            return

        if not await self.check_access(interaction, request):
            await interaction.response.send_message(
                "<a:gear:1553688352564183051> Hanya Owner kelas, Staff Pendamping, atau Administrator yang dapat memproses request ini.",
                ephemeral=True,
            )
            return

        if request["status"] != "Pending":
            await interaction.response.send_message("<a:question:1553688505929044000> Request sudah diproses.", ephemeral=True)
            return

        if request["class_status"] != "Active":
            await interaction.response.send_message("<a:question:1553688505929044000> Kelas sedang tidak aktif menerima anggota.", ephemeral=True)
            return

        existing = await get_user_class(request["user_id"])
        if existing:
            await interaction.response.send_message(
                f"<a:question:1553688505929044000> User sudah berada di **{existing['name']}**.",
                ephemeral=True,
            )
            return

        count = await get_member_count(request["class_id"])
        if count >= MAX_MEMBER:
            await interaction.response.send_message("<a:question:1553688505929044000> Kelas sudah penuh.", ephemeral=True)
            return

        member = interaction.guild.get_member(int(request["user_id"]))
        if not member:
            await interaction.response.send_message("<a:question:1553688505929044000> User sudah tidak berada di server.", ephemeral=True)
            return

        role = interaction.guild.get_role(int(request["role_id"]))
        if not role:
            await interaction.response.send_message("<a:question:1553688505929044000> Role kelas tidak ditemukan.", ephemeral=True)
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

            new_count = count + 1

            embed = discord.Embed(
                title="<:verified:1553690488257908837> Request Diterima",
                description=(
                    f"{member.mention} resmi menjadi siswa **{request['name']}**! <:verified:1553690488257908837>\n"
                    f"{DIVIDER}"
                ),
                color=discord.Color.from_rgb(*OK_GREEN),
                timestamp=utc_now(),
            )
            embed.add_field(name="<a:arrow_blue:1512787254312042496> Siswa Baru", value=member.mention, inline=True)
            embed.add_field(name="<a:arrow_blue:1512787254312042496> Kelas", value=request["name"], inline=True)
            embed.add_field(name="<:verified:1553690488257908837> Diproses oleh", value=interaction.user.mention, inline=True)
            embed.add_field(
                name="<a:arrow_blue:1512787254312042496> Kapasitas Sekarang",
                value=f"`{slot_bar(new_count)}` **{new_count}/{MAX_MEMBER}**",
                inline=False,
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_image(url=f"attachment://{BANNER_NAME}")
            style_embed(embed)

            result_banner = await make_banner_file(
                title="Selamat Datang di Kelas!",
                subtitle=request["name"],
                badge="DITERIMA",
                chips=[
                    ("Siswa Baru", member.display_name),
                    ("Diproses", interaction.user.display_name),
                    ("Kapasitas", f"{new_count}/{MAX_MEMBER}"),
                ],
                icon=await load_avatar(member),
                accent=OK_GREEN,
            )

            await interaction.message.edit(embed=embed, attachments=[result_banner], view=None)

            await send_log(
                interaction.client,
                interaction.guild,
                f"<:verified:1553690488257908837> {member.mention} diterima ke **{request['name']}** oleh {interaction.user.mention}.",
            )

            await interaction.followup.send("<:verified:1553690488257908837> Anggota berhasil ditambahkan.", ephemeral=True)

        except Exception:
            log.exception("Gagal approve join request.")
            if inserted:
                await execute(
                    "DELETE FROM nanz_class_members WHERE class_id=%s AND user_id=%s",
                    (request["class_id"], member.id),
                )
            await interaction.followup.send("<a:question:1553688505929044000> Gagal menambahkan anggota.", ephemeral=True)

    async def reject(self, interaction):
        request = await self.get_request()
        if not request:
            await interaction.response.send_message("<a:question:1553688505929044000> Request tidak ditemukan.", ephemeral=True)
            return

        if not await self.check_access(interaction, request):
            await interaction.response.send_message(
                "<a:gear:1553688352564183051> Hanya Owner kelas, Staff Pendamping, atau Administrator yang dapat memproses request ini.",
                ephemeral=True,
            )
            return

        if request["status"] != "Pending":
            await interaction.response.send_message("<a:question:1553688505929044000> Request sudah diproses.", ephemeral=True)
            return

        await execute(
            """
            UPDATE nanz_class_join_requests
            SET status='Rejected', processed_at=%s, processed_by=%s
            WHERE request_id=%s AND status='Pending'
            """,
            (db_now(), interaction.user.id, self.request_id),
        )

        applicant = interaction.guild.get_member(int(request["user_id"]))

        embed = discord.Embed(
            title="<a:question:1553688505929044000> Request Ditolak",
            description=(
                f"Request bergabung ke **{request['name']}** ditolak.\n"
                f"{DIVIDER}"
            ),
            color=discord.Color.from_rgb(*BAD_RED),
            timestamp=utc_now(),
        )
        embed.add_field(name="<a:arrow_blue:1512787254312042496> Pemohon", value=f"<@{request['user_id']}>", inline=True)
        embed.add_field(name="<:verified:1553690488257908837> Diproses oleh", value=interaction.user.mention, inline=True)
        embed.add_field(name="<a:pin:1553688245769085099> Request ID", value=f"`#{request['request_id']}`", inline=True)
        embed.set_image(url=f"attachment://{BANNER_NAME}")
        style_embed(embed)

        result_banner = await make_banner_file(
            title="Request Ditolak",
            subtitle=request["name"],
            badge="DITOLAK",
            chips=[
                ("Pemohon", applicant.display_name if applicant else "-"),
                ("Diproses", interaction.user.display_name),
                ("Request ID", f"#{request['request_id']}"),
            ],
            icon=await load_avatar(applicant) if applicant else None,
            accent=BAD_RED,
        )

        await interaction.response.edit_message(embed=embed, attachments=[result_banner], view=None)
        await send_log(
            interaction.client,
            interaction.guild,
            f"<a:question:1553688505929044000> Request {request['request_id']} untuk **{request['name']}** ditolak oleh {interaction.user.mention}.",
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
        """
        Extension dapat di-load dari setup_hook(), yaitu sebelum bot menerima
        READY dari Discord. Jangan melakukan operasi Discord yang membutuhkan
        client ready di sini karena discord.py masih memakai sentinel internal
        untuk event ready pada tahap tersebut.

        Kita jadwalkan proses restore di background task. Task akan menunggu
        bot benar-benar READY terlebih dahulu, lalu baru melakukan fetch channel,
        membaca database, restore persistent views, dan membuat dashboard Staff.
        """
        self._restore_task = asyncio.create_task(self._restore_after_ready())

    async def _restore_after_ready(self):
        try:
            await self.bot.wait_until_ready()

            # Register persistent static views setelah client siap.
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

        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Gagal restore Persistent View/Dashboard Kelas nanZ.")

    def cog_unload(self):
        task = getattr(self, "_restore_task", None)
        if task and not task.done():
            task.cancel()

    async def ensure_staff_dashboard(self):
        # get_channel() hanya mencari cache. Gunakan fetch_channel() sebagai
        # fallback supaya dashboard tetap dibuat meskipun channel belum cached.
        channel = self.bot.get_channel(APPROVAL_CHANNEL_ID)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(APPROVAL_CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                log.warning(
                    "Channel approval-kelas (ID %s) tidak dapat diakses: %s. "
                    "Dashboard Staff tidak dibuat.",
                    APPROVAL_CHANNEL_ID,
                    exc,
                )
                return

        marker = DASHBOARD_MARKER
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

        try:
            banner = await make_banner_file(
                title="Dashboard Staff Kelas",
                subtitle="Pusat Kendali Kelas nanZ",
                badge="STAFF ONLY",
                chips=[
                    ("Akses", "Staff & Admin"),
                    ("Kapasitas Kelas", f"{MAX_MEMBER} siswa"),
                    ("Sistem", "Kelas nanZ"),
                ],
            )
            if existing:
                await existing.edit(embed=embed, attachments=[banner], view=StaffDashboardView())
            else:
                await channel.send(embed=embed, file=banner, view=StaffDashboardView())
        except Exception:
            log.exception("Gagal membuat/memperbarui dashboard Staff.")

    @commands.command(name="refresh_panel_kelas")
    @commands.guild_only()
    @commands.check(lambda ctx: has_staff_role(ctx.author))
    async def refresh_panel_kelas(self, ctx):
        """Perbarui semua panel di daftar-kelas (mis. setelah tombol diubah)."""
        classes = await fetch_all(
            """
            SELECT class_id FROM nanz_classes
            WHERE status IN ('Active','Grace','Inactive')
            """
        )

        status_msg = await ctx.send(f"<a:arrow_blue:1512787254312042496> Memperbarui {len(classes)} panel kelas...")

        done = 0
        for row in classes:
            try:
                await update_public_panel(self.bot, int(row["class_id"]))
                done += 1
            except Exception:
                log.exception("Gagal refresh panel class_id=%s", row["class_id"])
            await asyncio.sleep(1.5)  # hindari rate limit Discord

        await status_msg.edit(content=f"<:verified:1553690488257908837> {done}/{len(classes)} panel kelas diperbarui.")

    @commands.command(name="buat_kelas")
    @commands.guild_only()
    @commands.check(lambda ctx: has_staff_role(ctx.author))
    async def buat_kelas(self, ctx):
        embed = discord.Embed(
            title="<a:arrow_blue:1512787254312042496> Panel Pembuatan Kelas nanZ",
            description=(
                "Wujudkan kelas impianmu di **nanZ Server**!\n"
                f"{DIVIDER}"
            ),
            color=EMBED_PURPLE,
        )
        embed.add_field(
            name="<a:arrow_blue:1512787254312042496> Alur Pembuatan",
            value=(
                "**1.** Tekan tombol **Buka Form Kelas**\n"
                "**2.** Isi nama, motto, deskripsi, warna & logo\n"
                "**3.** Staff memilih Staff Pendamping & menyetujui\n"
                "**4.** Voice Channel + role kelas dibuat otomatis"
            ),
            inline=False,
        )
        embed.add_field(
            name="<:verified:1553690488257908837> Yang Kamu Dapatkan",
            value=(
                "<a:pin:1553688245769085099> Voice Channel khusus\n"
                "<a:pin:1553688245769085099> Role kelas dengan warna sendiri\n"
                "<:verified:1553690488257908837> Card kelas di daftar kelas\n"
                f"<a:arrow_blue:1512787254312042496> Kapasitas hingga **{MAX_MEMBER} siswa**"
            ),
            inline=True,
        )
        embed.add_field(
            name="<a:gear:1553688352564183051> Akses Panel",
            value="Khusus **Staff** dan **Administrator**.",
            inline=True,
        )
        embed.set_image(url=f"attachment://{BANNER_NAME}")
        style_embed(embed)

        banner = await make_banner_file(
            title="Buat Kelas Baru",
            subtitle="Panel Pembuatan Kelas nanZ",
            badge="STAFF ONLY",
            chips=[
                ("Kapasitas", f"{MAX_MEMBER} siswa"),
                ("Persetujuan", "Staff"),
                ("Fasilitas", "VC + Role"),
            ],
        )
        await ctx.send(embed=embed, file=banner, view=ClassFormTriggerView())


async def setup(bot):
    await bot.add_cog(NanzKelasCog(bot))