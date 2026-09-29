import asyncio
import io
import json
import math
import os
import random
import textwrap
import time

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ══════════════════════════════════════════════
#  KONFIGURASI
# ══════════════════════════════════════════════
# ID CHANNEL NANZ
# Channel tempat command !setupsaran digunakan / panel dipasang
SETUP_CHANNEL_ID = 1509158797376229427
# Channel tempat hasil saran diterbitkan
SUGGESTION_CHANNEL_ID = 1554397431234564167

# Font panel (channel 1) - sama seperti welcome card
FONT_BOLD    = "fonts/LEMONMILK-Bold.otf"
FONT_REGULAR = "fonts/LEMONMILK-Regular.otf"
# Font papan saran (channel 2)
FONT_HEAD_BOLD = "fonts/TT_Interphases_Pro_Trial_Bold.ttf"
FONT_HEAD_MED  = "fonts/TT_Interphases_Pro_Trial_Medium.ttf"
_FALLBACKS = ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf")

COOLDOWN_SECONDS = 60             # jeda kirim saran per member
THREAD_ARCHIVE   = 10080          # auto-archive thread (menit): 60/1440/4320/10080
ANON_NAME        = "Anonim"
DATA_FILE        = "data/suggestion_data.json"   # nyimpen nomor urut saran

# Tema biru + ungu (sama dengan welcome)
BG_TOP, BG_BOT = (18, 10, 45), (40, 20, 80)
PURPLE, BLUE = (130, 80, 255), (80, 180, 255)
CARD_BG = (30, 15, 65)
SOFT_PURPLE, SOFT_BLUE = (160, 120, 255), (150, 210, 255)

W, H, S = 900, 420, 2             # ukuran akhir + supersampling


# ══════════════════════════════════════════════
#  HELPER FONT & FIT
# ══════════════════════════════════════════════
def _font(path, px):
    for p in (path, *_FALLBACKS):
        try:
            return ImageFont.truetype(p, int(px))
        except Exception:
            continue
    return ImageFont.load_default()


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _sc(v, s): return [int(x * s) for x in v]
def _P(pts, s): return [(x * s, y * s) for x, y in pts]


def _fit(d, text, path, start, max_w, s, min_size=9):
    size = start
    while size > min_size:
        fn = _font(path, size * s)
        if d.textlength(text, font=fn) <= max_w * s:
            return fn
        size -= 1
    return _font(path, min_size * s)


# ══════════════════════════════════════════════
#  PNG #1 — PANEL SETUP (channel 1)
# ══════════════════════════════════════════════
def generate_panel_banner() -> bytes:
    s = S
    sc = lambda v: _sc(v, s)
    P = lambda pts: _P(pts, s)
    F = lambda path, sz: _font(path, sz * s)
    fit = lambda d, t, path, start, mw: _fit(d, t, path, start, mw, s)

    base = Image.new("RGB", (W * s, H * s))
    d = ImageDraw.Draw(base)
    for y in range(H * s):
        d.line([(0, y), (W * s, y)], fill=_lerp(BG_TOP, BG_BOT, y / (H * s)))
    base = base.convert("RGBA")

    orb = Image.new("RGBA", base.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(orb)
    for ox, oy, r, c in [(90, 60, 150, PURPLE), (830, 380, 150, BLUE), (560, 10, 100, PURPLE)]:
        for st in range(r, 0, -5):
            od.ellipse(sc([ox - st, oy - st, ox + st, oy + st]), fill=(*c, int(55 * (st / r) ** 2.8)))
    base = Image.alpha_composite(base, orb)

    rng = random.Random(7)
    stl = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(stl)
    for _ in range(60):
        x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1, 2.4)
        sd.ellipse(sc([x - r, y - r, x + r, y + r]),
                   fill=(*_lerp(PURPLE, BLUE, rng.random()), rng.randint(80, 190)))
    base = Image.alpha_composite(base, stl)

    pl = Image.new("RGBA", base.size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(pl)
    pd.rounded_rectangle(sc([20, 20, 880, 400]), radius=30 * s, fill=(*CARD_BG, 200))
    pd.rounded_rectangle(sc([20, 20, 880, 400]), radius=30 * s, outline=(*PURPLE, 100), width=2 * s)
    pd.rounded_rectangle(sc([38, 38, 396, 382]), radius=22 * s, fill=(*PURPLE, 38))
    pd.rounded_rectangle(sc([38, 38, 396, 382]), radius=22 * s, outline=(*SOFT_PURPLE, 70), width=s)
    for i in range(38, 382):
        pd.rectangle(sc([414, i, 416, i + 1]), fill=(*_lerp(BLUE, PURPLE, (i - 38) / 344), 200))
    base = Image.alpha_composite(base, pl)

    gl = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(gl).ellipse(sc([80, 130, 360, 380]), fill=(*BLUE, 70))
    base = Image.alpha_composite(base, gl.filter(ImageFilter.GaussianBlur(28 * s)))

    # kotak saran ilustrasi
    L = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(L)
    ld.ellipse(sc([105, 338, 355, 362]), fill=(0, 0, 0, 90))
    ld.polygon(P([(320, 222), (362, 192), (362, 312), (320, 342)]), fill=(84, 48, 190))
    ld.rounded_rectangle(sc([110, 222, 320, 342]), radius=8 * s, fill=PURPLE)
    ld.polygon(P([(110, 222), (152, 192), (362, 192), (320, 222)]), fill=SOFT_PURPLE)
    ld.polygon(P([(190, 208), (202, 200), (282, 200), (270, 208)]), fill=(25, 12, 60))
    ld.rounded_rectangle(sc([110, 222, 320, 236]), radius=4 * s, fill=(150, 110, 255))
    ld.rounded_rectangle(sc([145, 256, 285, 314]), radius=10 * s, fill=(245, 245, 255))
    ld.rounded_rectangle(sc([145, 256, 285, 314]), radius=10 * s, outline=BLUE, width=2 * s)
    ld.line(P([(160, 296), (270, 296)]), fill=(200, 205, 235), width=s)
    base = Image.alpha_composite(base, L)
    d = ImageDraw.Draw(base)
    d.text((215 * s, 278 * s), "SARAN", font=fit(d, "SARAN", FONT_BOLD, 22, 115), fill=(70, 40, 160), anchor="mm")
    d.rounded_rectangle(sc([190, 296, 240, 300]), radius=2 * s, fill=BLUE)

    env = Image.new("RGBA", (120 * s, 90 * s), (0, 0, 0, 0))
    ed = ImageDraw.Draw(env)
    ed.rounded_rectangle([0, 0, 100 * s, 70 * s], radius=8 * s, fill=(255, 255, 255))
    ed.polygon([(0, 4 * s), (50 * s, 42 * s), (100 * s, 4 * s)], fill=(225, 230, 250))
    ed.line([(0, 4 * s), (50 * s, 42 * s), (100 * s, 4 * s)], fill=(190, 195, 230), width=2 * s)
    ed.ellipse([42 * s, 34 * s, 58 * s, 50 * s], fill=(255, 110, 160))
    env = env.rotate(12, expand=True, resample=Image.BICUBIC)
    base.alpha_composite(env, (218 * s, 96 * s))

    def pencil(p0, p1, w):
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        nx, ny, ux, uy = -math.sin(ang), math.cos(ang), math.cos(ang), math.sin(ang)
        ln = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        def pt(a, b): return (p0[0] + ux * a + nx * b, p0[1] + uy * a + ny * b)
        dd = ImageDraw.Draw(base)
        dd.polygon(P([pt(0, -w / 2), pt(ln * .12, -w / 2), pt(ln * .12, w / 2), pt(0, w / 2)]), fill=(255, 130, 170))
        dd.polygon(P([pt(ln * .12, -w / 2), pt(ln * .8, -w / 2), pt(ln * .8, w / 2), pt(ln * .12, w / 2)]), fill=(255, 205, 80))
        dd.polygon(P([pt(ln * .8, -w / 2), pt(ln, 0), pt(ln * .8, w / 2)]), fill=(245, 222, 190))
        dd.polygon(P([pt(ln * .93, -w * .15), pt(ln, 0), pt(ln * .93, w * .15)]), fill=(60, 45, 90))
    pencil((72, 352), (150, 292), 13)

    def sparkle(x, y, sz, col):
        q = sz * .25
        lay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        ImageDraw.Draw(lay).polygon(P([(x, y - sz), (x + q, y - q), (x + sz, y), (x + q, y + q), (x, y + sz),
                                       (x - q, y + q), (x - sz, y), (x - q, y - q)]), fill=(*col, 230))
        return lay
    for x, y, sz, c in [(90, 100, 10, SOFT_BLUE), (350, 110, 8, SOFT_PURPLE), (370, 250, 7, SOFT_BLUE),
                       (70, 220, 6, SOFT_PURPLE), (150, 70, 6, SOFT_BLUE), (300, 70, 9, SOFT_PURPLE)]:
        base = Image.alpha_composite(base, sparkle(x, y, sz, c))

    d = ImageDraw.Draw(base)
    RX0, RX1 = 440, 858
    RW = RX1 - RX0

    pill = "RUANG BK"
    fp = F(FONT_BOLD, 11)
    pw = d.textlength(pill, font=fp) / s + 34
    d.rounded_rectangle(sc([RX0, 50, RX0 + pw, 74]), radius=12 * s, fill=(*PURPLE, 220))
    d.text(((RX0 + pw / 2) * s, 62 * s), pill, font=fp, fill=(255, 255, 255), anchor="mm")

    title = "KOTAK SARAN"
    ft = fit(d, title, FONT_BOLD, 52, RW)
    tb = d.textbbox((0, 0), title, font=ft)
    tm = Image.new("L", base.size, 0)
    ImageDraw.Draw(tm).text((RX0 * s, 84 * s), title, font=ft, fill=255)
    grad = Image.new("RGBA", base.size)
    gd = ImageDraw.Draw(grad)
    x0 = RX0 * s
    span = max(1, tb[2] - tb[0])
    for x in range(int(x0), int(x0 + span) + 2):
        gd.line([(x, 0), (x, H * s)], fill=(*_lerp((255, 255, 255), SOFT_BLUE, min(1, (x - x0) / span)), 255))
    grad.putalpha(tm)
    base = Image.alpha_composite(base, grad)
    d = ImageDraw.Draw(base)

    l1, l2 = "Punya ide, kritik, atau masukan buat nanZ?", "Titipkan di sini, semua saran pasti kami baca."
    d.text((RX0 * s, 158 * s), l1, font=fit(d, l1, FONT_REGULAR, 15, RW), fill=(225, 225, 245), anchor="lm")
    d.text((RX0 * s, 180 * s), l2, font=fit(d, l2, FONT_REGULAR, 15, RW), fill=(175, 170, 215), anchor="lm")

    steps = [("1", "Klik tombol Kirim Saran", "di bawah gambar ini", BLUE),
             ("2", "Isi judul dan saranmu", "nama boleh dikosongin, jadi anonim", PURPLE)]
    fnum = F(FONT_BOLD, 18)
    for i, (n, h, sub, col) in enumerate(steps):
        y = 216 + i * 70
        ly = Image.new("RGBA", base.size, (0, 0, 0, 0))
        ImageDraw.Draw(ly).rounded_rectangle(sc([RX0, y, RX1, y + 54]), radius=16 * s, fill=(*PURPLE, 34),
                                             outline=(*SOFT_PURPLE, 80), width=s)
        base = Image.alpha_composite(base, ly)
        d = ImageDraw.Draw(base)
        d.ellipse(sc([RX0 + 11, y + 11, RX0 + 43, y + 43]), fill=col)
        d.text(((RX0 + 27) * s, (y + 27) * s), n, font=fnum, fill=(255, 255, 255), anchor="mm")
        tw = RW - 56 - 12
        d.text(((RX0 + 58) * s, (y + 19) * s), h, font=fit(d, h, FONT_BOLD, 15, tw), fill=(255, 255, 255), anchor="lm")
        d.text(((RX0 + 58) * s, (y + 38) * s), sub, font=fit(d, sub, FONT_REGULAR, 12, tw), fill=SOFT_BLUE, anchor="lm")

    out = base.convert("RGB").resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ══════════════════════════════════════════════
#  PNG #2 — PAPAN SARAN (channel 2, baru tiap kiriman)
# ══════════════════════════════════════════════
def generate_papan_saran(nama: str, judul: str, isi: str, nomor: int) -> bytes:
    s = S
    sc = lambda v: _sc(v, s)
    P = lambda pts: _P(pts, s)
    F = lambda path, sz: _font(path, sz * s)
    fit = lambda d, t, path, start, mw: _fit(d, t, path, start, mw, s)

    base = Image.new("RGB", (W * s, H * s))
    d = ImageDraw.Draw(base)
    for y in range(H * s):
        d.line([(0, y), (W * s, y)], fill=_lerp(BG_TOP, BG_BOT, y / (H * s)))
    base = base.convert("RGBA")

    orb = Image.new("RGBA", base.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(orb)
    for ox, oy, r, c in [(70, 60, 130, PURPLE), (850, 380, 140, BLUE), (500, 400, 110, PURPLE)]:
        for st in range(r, 0, -5):
            od.ellipse(sc([ox - st, oy - st, ox + st, oy + st]), fill=(*c, int(50 * (st / r) ** 2.8)))
    base = Image.alpha_composite(base, orb)

    rng = random.Random(nomor if nomor else 3)
    stl = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(stl)
    for _ in range(50):
        x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1, 2.2)
        sd.ellipse(sc([x - r, y - r, x + r, y + r]), fill=(*_lerp(PURPLE, BLUE, rng.random()), rng.randint(70, 170)))
    base = Image.alpha_composite(base, stl)

    pl = Image.new("RGBA", base.size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(pl)
    pd.rounded_rectangle(sc([20, 20, 880, 400]), radius=28 * s, fill=(*CARD_BG, 205))
    pd.rounded_rectangle(sc([20, 20, 880, 400]), radius=28 * s, outline=(*PURPLE, 100), width=2 * s)
    base = Image.alpha_composite(base, pl)
    d = ImageDraw.Draw(base)

    # header
    hd_y = 52
    d.ellipse(sc([46, hd_y - 12, 70, hd_y + 12]), fill=PURPLE)
    d.ellipse(sc([53, hd_y - 5, 63, hd_y + 5]), fill=(255, 255, 255))
    d.text((84 * s, hd_y * s), "PAPAN SARAN", font=F(FONT_HEAD_BOLD, 15), fill=(255, 255, 255), anchor="lm")

    numtxt = f"#{nomor}"
    fnum = F(FONT_HEAD_BOLD, 15)
    nw = d.textlength(numtxt, font=fnum) / s + 26
    d.rounded_rectangle(sc([854 - nw, hd_y - 15, 854, hd_y + 15]), radius=14 * s, fill=(*BLUE, 220))
    d.text(((854 - nw / 2) * s, hd_y * s), numtxt, font=fnum, fill=(255, 255, 255), anchor="mm")

    d.line(sc([46, 78, 854, 78]), fill=(*SOFT_PURPLE, 90), width=2 * s)

    # sticky note
    note_box = [58, 100, 842, 372]
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        sc([note_box[0] + 6, note_box[1] + 10, note_box[2] + 6, note_box[3] + 10]),
        radius=18 * s, fill=(0, 0, 0, 90))
    base = Image.alpha_composite(base, shadow.filter(ImageFilter.GaussianBlur(6 * s)))

    note = Image.new("RGBA", base.size, (0, 0, 0, 0))
    nd = ImageDraw.Draw(note)
    nd.rounded_rectangle(sc(note_box), radius=18 * s, fill=(250, 248, 255, 255))
    cx, cy = note_box[2], note_box[3]
    fold = 26
    nd.polygon(P([(cx - fold, cy), (cx, cy - fold), (cx, cy)]), fill=(222, 216, 240, 255))
    base = Image.alpha_composite(base, note)

    pinx = (note_box[0] + note_box[2]) / 2
    piny = note_box[1]
    d = ImageDraw.Draw(base)
    d.ellipse(sc([pinx - 12, piny - 10, pinx + 12, piny + 14]), fill=(0, 0, 0, 60))
    d.ellipse(sc([pinx - 11, piny - 12, pinx + 11, piny + 10]), fill=(255, 90, 130))
    d.ellipse(sc([pinx - 4, piny - 6, pinx + 2, piny]), fill=(255, 180, 200))

    NX0, NX1 = note_box[0] + 34, note_box[2] - 34
    ny = note_box[1] + 30

    ad_r = 20
    d.ellipse(sc([NX0, ny - ad_r, NX0 + ad_r * 2, ny + ad_r]), fill=PURPLE)
    initial = (nama[:1] or "?").upper()
    d.text(((NX0 + ad_r) * s, ny * s), initial, font=F(FONT_HEAD_BOLD, 18), fill=(255, 255, 255), anchor="mm")
    fnama = fit(d, nama, FONT_HEAD_BOLD, 17, NX1 - NX0 - ad_r * 2 - 14)
    d.text(((NX0 + ad_r * 2 + 14) * s, (ny - 9) * s), nama, font=fnama, fill=(70, 45, 130, 255), anchor="lm")
    d.text(((NX0 + ad_r * 2 + 14) * s, (ny + 11) * s), "mengirim saran",
           font=F(FONT_HEAD_MED, 11), fill=(150, 140, 190, 255), anchor="lm")

    ny2 = ny + 44
    fjudul = fit(d, judul, FONT_HEAD_BOLD, 24, NX1 - NX0)
    d.text((NX0 * s, ny2 * s), judul, font=fjudul, fill=(45, 25, 95, 255), anchor="lm")

    d.line(sc([NX0, ny2 + 30, NX1, ny2 + 30]), fill=(210, 200, 235, 255), width=2 * s)

    fbody = F(FONT_HEAD_MED, 15)
    avg_char_w = max(1, d.textlength("x" * 20, font=fbody) / s / 20)
    max_chars = max(10, int((NX1 - NX0) / avg_char_w))
    wrapped = textwrap.wrap(isi, width=max_chars)
    truncated = len(wrapped) > 6
    wrapped = wrapped[:6]
    if truncated and wrapped:
        last = wrapped[-1]
        while d.textlength(last + "…", font=fbody) > (NX1 - NX0) * s and len(last) > 1:
            last = last[:-1]
        wrapped[-1] = last + "…"
    by = ny2 + 50
    for line in wrapped:
        d.text((NX0 * s, by * s), line, font=fbody, fill=(70, 65, 100, 255), anchor="lm")
        by += 25

    tape = Image.new("RGBA", base.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(tape)
    td.rectangle(sc([note_box[0] - 14, note_box[1] - 12, note_box[0] + 46, note_box[1] + 18]), fill=(*SOFT_BLUE, 190))
    tape = tape.rotate(-30, center=((note_box[0] + 16) * s, note_box[1] * s), resample=Image.BICUBIC)
    base = Image.alpha_composite(base, tape)

    out = base.convert("RGB").resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ══════════════════════════════════════════════
#  MODAL
# ══════════════════════════════════════════════
class SaranModal(discord.ui.Modal, title="Kirim Saran"):

    nama = discord.ui.TextInput(
        label="Nama (opsional)",
        placeholder="Kosongkan kalau mau anonim",
        required=False,
        max_length=50,
    )
    judul = discord.ui.TextInput(
        label="Judul saran",
        placeholder="Contoh: Tambah channel curhat",
        required=True,
        max_length=80,
    )
    isi = discord.ui.TextInput(
        label="Isi saran",
        style=discord.TextStyle.paragraph,
        placeholder="Tulis saran atau masukanmu di sini...",
        required=True,
        max_length=1000,
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.create_suggestion(
            interaction,
            nama=self.nama.value.strip() or ANON_NAME,
            judul=self.judul.value.strip(),
            isi=self.isi.value.strip(),
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print("[Saran] modal error:", error)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Terjadi kesalahan, coba lagi ya.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Terjadi kesalahan, coba lagi ya.", ephemeral=True)


# ══════════════════════════════════════════════
#  TOMBOL (persistent, dipakai di channel 1 & channel 2)
# ══════════════════════════════════════════════
class SaranView(discord.ui.View):

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Kirim Saran" style=discord.ButtonStyle.primary,
                       custom_id="nanz:saran:open")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        remaining = self.cog.cooldown_left(interaction.user.id)
        if remaining > 0:
            return await interaction.response.send_message(
                f"⏳ Tunggu {remaining} detik lagi sebelum kirim saran lagi ya!", ephemeral=True
            )
        await interaction.response.send_modal(SaranModal(self.cog))


# ══════════════════════════════════════════════
#  COG
# ══════════════════════════════════════════════
class Suggestion(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}              # user_id -> waktu kirim terakhir
        self._panel_banner = None        # cache PNG panel (channel 1)
        self._lock = asyncio.Lock()      # kunci saat nulis nomor urut

        os.makedirs(os.path.dirname(DATA_FILE) or ".", exist_ok=True)
        self._data = self._load_data()

    # ── data nomor urut saran ──
    def _load_data(self):
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except Exception:
            return {"counter": 0}

    def _save_data(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self._data, f)

    async def _next_number(self) -> int:
        async with self._lock:
            self._data["counter"] = self._data.get("counter", 0) + 1
            self._save_data()
            return self._data["counter"]

    async def cog_load(self):
        # daftarkan tombol supaya tetap jalan setelah bot restart
        self.bot.add_view(SaranView(self))

    def cooldown_left(self, user_id: int) -> int:
        last = self.cooldowns.get(user_id)
        if not last:
            return 0
        return max(0, int(COOLDOWN_SECONDS - (time.time() - last)))

    # ── channel 1: kirim panel (PNG + tombol) ──
    @commands.command(name="setupsaran")
    @commands.has_permissions(administrator=True)
    async def setup_saran(self, ctx: commands.Context):
        if ctx.channel.id != SETUP_CHANNEL_ID:
            return await ctx.send(
                f"❌ Command ini hanya bisa digunakan di <#{SETUP_CHANNEL_ID}>.",
                delete_after=5
            )

        async with ctx.typing():
            if self._panel_banner is None:
                loop = asyncio.get_running_loop()
                self._panel_banner = await loop.run_in_executor(None, generate_panel_banner)

        await ctx.send(
            file=discord.File(io.BytesIO(self._panel_banner), filename="kotak_saran.png"),
            view=SaranView(self),
        )
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    # ── channel 2: terbitkan saran + auto thread ──
    async def create_suggestion(self, interaction: discord.Interaction, nama: str, judul: str, isi: str):
        await interaction.response.defer(ephemeral=True)

        target = self.bot.get_channel(SUGGESTION_CHANNEL_ID)
        if target is None:
            return await interaction.followup.send(
                "❌ Channel papan saran tidak ditemukan. Pastikan ID channel sudah benar.",
                ephemeral=True,
            )

        nomor = await self._next_number()

        try:
            loop = asyncio.get_running_loop()
            png_bytes = await loop.run_in_executor(None, generate_papan_saran, nama, judul, isi, nomor)
        except Exception as e:
            print("[Saran] gagal render papan:", e)
            return await interaction.followup.send("❌ Gagal membuat tampilan saran, coba lagi ya.", ephemeral=True)

        try:
            msg = await target.send(
                file=discord.File(io.BytesIO(png_bytes), filename=f"saran_{nomor}.png"),
                view=SaranView(self),
            )
            thread = await msg.create_thread(
                name=f"💡 {judul}"[:100],
                auto_archive_duration=THREAD_ARCHIVE,
                reason="Kotak saran",
            )
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ Bot nggak punya izin kirim pesan / bikin thread di channel papan saran.", ephemeral=True
            )
        except discord.HTTPException as e:
            print("[Saran] gagal kirim/bikin thread:", e)
            return await interaction.followup.send("❌ Gagal mengirim saran, coba lagi nanti.", ephemeral=True)

        self.cooldowns[interaction.user.id] = time.time()
        await interaction.followup.send(f"✅ Saranmu sudah terbit! Lihat di {thread.mention}", ephemeral=True)


# ══════════════════════════════════════════════
#  SETUP
# ══════════════════════════════════════════════
async def setup(bot):
    await bot.add_cog(Suggestion(bot))