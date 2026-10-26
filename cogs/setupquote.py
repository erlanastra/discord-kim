import asyncio
import hashlib
import io
import json
import math
import os
import random
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import discord
from discord.ext import commands
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

try:
    import numpy as np  # dipakai desain panel baru (pip install numpy)
except ImportError:  # pragma: no cover
    np = None

# ==========================================
# ID CHANNEL QUOTE
# ==========================================
QUOTE_CHANNEL_ID = 1474394873783128368

# ==========================================
# EMOJI LIKE (lovelike)
# ==========================================
LIKE_EMOJI = discord.PartialEmoji(name="lovelike", id=1557691732039049276)

# ==========================================
# KONFIGURASI PANEL PNG
# ==========================================
FONT_BOLD = "fonts/LEMONMILK-Bold.otf"
FONT_REGULAR = "fonts/LEMONMILK-Regular.otf"
# Desain panel baru (sama dengan kartu booster): font & logo yang sama.
FONT_SANS = "fonts/Inter.ttf"                      # Inter (variable font)
FONT_SERIF = "fonts/InstrumentSerif-Italic.ttf"    # Instrument Serif Italic
LOGO_PATHS = ("assets/nanz_logo.png", "nanz_logo.png", "fonts/nanz_logo.png")
# File penyimpan posisi panel (channel_id, message_id, versi desain) agar bisa di-edit otomatis.
QUOTE_PANEL_FILE = "quote_panel.json"
FB = ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf")
BG_TOP, BG_BOT = (18, 10, 45), (40, 20, 80)
PURPLE, BLUE = (130, 80, 255), (80, 180, 255)
CARD_BG = (30, 15, 65)
SP, SB = (160, 120, 255), (150, 210, 255)
ORANGE, PINK, GREEN = (255, 170, 80), (255, 100, 140), (90, 220, 160)
WH = (255, 255, 255)
W, H, s = 900, 500, 2


# ==========================================
# HELPER GAMBAR
# ==========================================
def font(p, px):
    for q in (p, *FB):
        try: return ImageFont.truetype(q, int(px))
        except Exception: pass
    return ImageFont.load_default()
def lerp(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
def sc(v): return [int(x * s) for x in v]
def P(pts): return [(x * s, y * s) for x, y in pts]
def F(p, sz): return font(p, sz * s)
def wrap(d, text, f, mw):
    out, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}".strip()
        if d.textlength(t, font=f) <= mw: cur = t
        else:
            out.append(cur); cur = w
    if cur: out.append(cur)
    return out



# ==========================================
# PNG PANEL QUOTE (DESAIN LAMA — cadangan bila renderer baru gagal)
# ==========================================
def _generate_quote_panel_legacy() -> bytes:
    base = Image.new("RGB", (W * s, H * s))
    d = ImageDraw.Draw(base)
    for y in range(H * s):
        d.line([(0, y), (W * s, y)], fill=lerp(BG_TOP, BG_BOT, y / (H * s)))
    base = base.convert("RGBA")

    def layer(fn, blur=0):
        nonlocal base
        lay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        fn(ImageDraw.Draw(lay))
        if blur: lay = lay.filter(ImageFilter.GaussianBlur(blur * s))
        base = Image.alpha_composite(base, lay)

    def orbs(g):
        for ox, oy, r, c in [(80, 60, 170, PURPLE), (830, 470, 190, BLUE), (640, 10, 120, PURPLE), (60, 460, 120, BLUE)]:
            for st in range(r, 0, -5):
                g.ellipse(sc([ox - st, oy - st, ox + st, oy + st]), fill=(*c, int(55 * (st / r) ** 2.8)))
    layer(orbs)
    rng = random.Random(5)
    def stars(g):
        for _ in range(80):
            x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1, 2.4)
            g.ellipse(sc([x - r, y - r, x + r, y + r]), fill=(*lerp(PURPLE, BLUE, rng.random()), rng.randint(80, 190)))
    layer(stars)
    def panel(g):
        g.rounded_rectangle(sc([20, 20, 880, 480]), radius=30 * s, fill=(*CARD_BG, 200))
        g.rounded_rectangle(sc([20, 20, 880, 480]), radius=30 * s, outline=(*PURPLE, 100), width=2 * s)
    layer(panel)

    def grad_text(text, path, size, x, y, c1, c2):
        nonlocal base
        f = F(path, size)
        dd = ImageDraw.Draw(base)
        bb = dd.textbbox((x * s, y * s), text, font=f)
        mask = Image.new("L", base.size, 0)
        ImageDraw.Draw(mask).text((x * s, y * s), text, font=f, fill=255)
        g = Image.new("RGBA", base.size); gd = ImageDraw.Draw(g)
        span = max(1, bb[2] - bb[0])
        for xx in range(bb[0], bb[2] + 2):
            gd.line([(xx, 0), (xx, H * s)], fill=(*lerp(c1, c2, min(1, (xx - bb[0]) / span)), 255))
        g.putalpha(mask)
        base = Image.alpha_composite(base, g)

    def place(tile, cx, cy, ang):
        nonlocal base
        t = tile.rotate(ang, expand=True, resample=Image.BICUBIC)
        a = t.split()[3].filter(ImageFilter.GaussianBlur(9 * s)).point(lambda v: int(v * .55))
        sh = Image.new("RGBA", t.size, (0, 0, 0, 0)); sh.putalpha(a)
        x, y = int(cx * s - t.width / 2), int(cy * s - t.height / 2)
        base.alpha_composite(sh, (x, y + 8 * s))
        base.alpha_composite(t, (x, y))

    def vgrad(size, c1, c2, mask_fn):
        g = Image.new("RGBA", size); gd = ImageDraw.Draw(g)
        for y in range(size[1]): gd.line([(0, y), (size[0], y)], fill=(*lerp(c1, c2, y / size[1]), 255))
        m = Image.new("L", size, 0); mask_fn(ImageDraw.Draw(m))
        return g, m

    def heart(dr, x, y, r, col):
        dr.ellipse(sc([x - r, y - r * .9, x, y + r * .1]), fill=col)
        dr.ellipse(sc([x, y - r * .9, x + r, y + r * .1]), fill=col)
        dr.polygon(P([(x - r * .97, y - r * .15), (x + r * .97, y - r * .15), (x, y + r * 1.15)]), fill=col)

    def icon(dr, kind, cx, cy, col):
        if kind == "photo":
            dr.rounded_rectangle(sc([cx - 12, cy - 9, cx + 12, cy + 9]), radius=3 * s, fill=WH)
            dr.polygon(P([(cx - 9, cy + 6), (cx - 2, cy - 2), (cx + 2, cy + 3), (cx + 5, cy), (cx + 10, cy + 6)]), fill=col)
            dr.ellipse(sc([cx + 3, cy - 7, cx + 8, cy - 2]), fill=col)
        elif kind == "music":
            dr.ellipse(sc([cx - 9, cy + 3, cx - 2, cy + 10]), fill=WH)
            dr.ellipse(sc([cx + 3, cy + 1, cx + 10, cy + 8]), fill=WH)
            dr.rectangle(sc([cx - 4, cy - 10, cx - 2, cy + 6]), fill=WH)
            dr.rectangle(sc([cx + 8, cy - 12, cx + 10, cy + 4]), fill=WH)
            dr.polygon(P([(cx - 4, cy - 10), (cx + 10, cy - 12), (cx + 10, cy - 8), (cx - 4, cy - 6)]), fill=WH)
        else:
            dr.ellipse(sc([cx - 12, cy - 12, cx + 12, cy + 12]), fill=WH)
            dr.ellipse(sc([cx - 6, cy - 5, cx - 3, cy - 2]), fill=col)
            dr.ellipse(sc([cx + 3, cy - 5, cx + 6, cy - 2]), fill=col)
            dr.arc(sc([cx - 7, cy - 4, cx + 7, cy + 7]), 20, 160, fill=col, width=2 * s)

    # ================= KIRI =================
    d = ImageDraw.Draw(base)
    pill = "NANZ QUOTE"; fp = F(FONT_BOLD, 11)
    pw = d.textlength(pill, font=fp) / s + 34
    layer(lambda g: g.rounded_rectangle(sc([54, 52, 54 + pw, 76]), radius=12 * s, fill=(*PURPLE, 230)))
    d = ImageDraw.Draw(base)
    d.text(((54 + pw / 2) * s, 64 * s), pill, font=fp, fill=WH, anchor="mm")

    layer(lambda g: g.text((40 * s, 70 * s), "\u201c", font=F(FONT_BOLD, 230), fill=(*PURPLE, 55)))
    grad_text("TULIS", FONT_BOLD, 66, 54, 100, WH, SB)
    grad_text("QUOTE-MU", FONT_BOLD, 66, 54, 176, SB, SP)

    d = ImageDraw.Draw(base)
    d.text((56 * s, 292 * s), "Bagikan kata-kata dan perasaanmu.", font=F(FONT_REGULAR, 14), fill=(225, 225, 245), anchor="lm")
    d.text((56 * s, 315 * s), "Tambahkan foto, lagu, atau sticker.", font=F(FONT_REGULAR, 14), fill=(175, 170, 215), anchor="lm")

    # baris media
    for i, (lab, kind, col) in enumerate([("Foto", "photo", ORANGE), ("Lagu", "music", GREEN), ("Sticker", "sticker", SP)]):
        cx, cy = 76 + i * 118, 368
        layer(lambda g, cx=cx, cy=cy, col=col: (g.ellipse(sc([cx - 26, cy - 26, cx + 26, cy + 26]), fill=(*col, 45)),
                                                g.ellipse(sc([cx - 20, cy - 20, cx + 20, cy + 20]), fill=(*col, 255))))
        d = ImageDraw.Draw(base)
        icon(d, kind, cx, cy, col)
        d.text(((cx + 28) * s, cy * s), lab, font=F(FONT_BOLD, 12), fill=WH, anchor="lm")

    # CTA
    ct = "Klik tombol di bawah untuk mulai"
    fc = F(FONT_BOLD, 11)
    cw = d.textlength(ct, font=fc) / s + 60
    layer(lambda g: (g.rounded_rectangle(sc([54, 416, 54 + cw, 448]), radius=16 * s, fill=(*BLUE, 30)),
                     g.rounded_rectangle(sc([54, 416, 54 + cw, 448]), radius=16 * s, outline=(*BLUE, 200), width=s)))
    d = ImageDraw.Draw(base)
    d.text((74 * s, 432 * s), ct, font=fc, fill=SB, anchor="lm")
    ax = 54 + cw - 22
    d.polygon(P([(ax - 6, 428), (ax + 6, 428), (ax, 437)]), fill=SB)

    # ================= KANAN (kolase) =================
    # polaroid
    t = Image.new("RGBA", (190 * s, 220 * s), (0, 0, 0, 0)); td = ImageDraw.Draw(t)
    td.rounded_rectangle(sc([15, 12, 175, 205]), radius=6 * s, fill=(248, 246, 255))
    g, m = vgrad(t.size, (255, 190, 110), (110, 70, 200), lambda x: x.rectangle(sc([23, 20, 167, 155]), fill=255))
    t.paste(g, (0, 0), m); td = ImageDraw.Draw(t)
    td.ellipse(sc([78, 60, 112, 94]), fill=(255, 235, 160))
    td.polygon(P([(23, 155), (62, 105), (92, 138), (124, 92), (167, 155)]), fill=(70, 40, 130))
    td.polygon(P([(23, 155), (50, 128), (80, 155)]), fill=(45, 25, 95))
    td.rounded_rectangle(sc([34, 170, 120, 178]), radius=4 * s, fill=(190, 185, 225))
    td.rounded_rectangle(sc([34, 185, 90, 191]), radius=3 * s, fill=(215, 212, 238))
    heart(td, 152, 178, 8, PINK)
    place(t, 772, 138, 9)

    # kartu quote utama
    t = Image.new("RGBA", (380 * s, 250 * s), (0, 0, 0, 0))
    g, m = vgrad(t.size, (66, 38, 140), (34, 18, 84), lambda x: x.rounded_rectangle(sc([20, 20, 360, 230]), radius=26 * s, fill=255))
    t.paste(g, (0, 0), m); td = ImageDraw.Draw(t)
    td.rounded_rectangle(sc([20, 20, 360, 230]), radius=26 * s, outline=(*SP, 150), width=2 * s)
    td.text((46 * s, 72 * s), "\u201c", font=F(FONT_BOLD, 70), fill=SB, anchor="lm")
    fq = F(FONT_REGULAR, 15)
    for j, ln in enumerate(wrap(td, "Tidak apa-apa berjalan pelan, yang penting kamu tidak berhenti.", fq, 300 * s)):
        td.text((48 * s, (110 + j * 24) * s), ln, font=fq, fill=WH, anchor="lm")
    td.rounded_rectangle(sc([274, 40, 340, 60]), radius=10 * s, fill=(*PURPLE, 255))
    td.text((307 * s, 50 * s), "tenang", font=F(FONT_BOLD, 10), fill=WH, anchor="mm")
    td.line(sc([46, 180, 334, 180]), fill=(*SP, 90), width=s)
    td.ellipse(sc([46, 190, 74, 218]), fill=BLUE); td.ellipse(sc([54, 198, 66, 210]), fill=PURPLE)
    td.text((84 * s, 199 * s), "nanZ", font=F(FONT_BOLD, 12), fill=WH, anchor="lm")
    td.text((84 * s, 213 * s), "baru saja", font=F(FONT_REGULAR, 9), fill=SP, anchor="lm")
    heart(td, 300, 204, 9, PINK)
    td.text((316 * s, 205 * s), "24", font=F(FONT_BOLD, 12), fill=WH, anchor="lm")
    place(t, 655, 235, -5)

    # music pill
    t = Image.new("RGBA", (290 * s, 80 * s), (0, 0, 0, 0)); td = ImageDraw.Draw(t)
    td.rounded_rectangle(sc([10, 10, 280, 70]), radius=30 * s, fill=(20, 12, 52, 245), outline=(*BLUE, 230), width=2 * s)
    td.ellipse(sc([20, 20, 60, 60]), fill=BLUE)
    td.polygon(P([(35, 31), (35, 49), (50, 40)]), fill=WH)
    td.text((72 * s, 30 * s), "NOW PLAYING", font=F(FONT_BOLD, 9), fill=SB, anchor="lm")
    td.text((72 * s, 48 * s), "lofi_night.mp3", font=F(FONT_REGULAR, 11), fill=WH, anchor="lm")
    hs = [8, 16, 10, 22, 14, 26, 12, 20, 9, 16, 7]
    for i, h in enumerate(hs):
        x = 188 + i * 8
        td.rounded_rectangle(sc([x, 40 - h / 2, x + 4, 40 + h / 2]), radius=2 * s, fill=lerp(BLUE, SP, i / 10))
    place(t, 610, 372, -3)

    # sticker
    t = Image.new("RGBA", (110 * s, 110 * s), (0, 0, 0, 0)); td = ImageDraw.Draw(t)
    td.ellipse(sc([10, 10, 100, 100]), fill=(255, 214, 90), outline=WH, width=5 * s)
    td.ellipse(sc([36, 40, 46, 54]), fill=(60, 35, 100)); td.ellipse(sc([64, 40, 74, 54]), fill=(60, 35, 100))
    td.ellipse(sc([26, 58, 40, 68]), fill=(255, 150, 150)); td.ellipse(sc([70, 58, 84, 68]), fill=(255, 150, 150))
    td.arc(sc([34, 50, 76, 82]), 15, 165, fill=(60, 35, 100), width=4 * s)
    place(t, 838, 355, 12)

    # hati & sparkle
    def sparkle(x, y, sz, col):
        q = sz * .25
        return lambda g: g.polygon(P([(x, y - sz), (x + q, y - q), (x + sz, y), (x + q, y + q), (x, y + sz),
                                      (x - q, y + q), (x - sz, y), (x - q, y - q)]), fill=(*col, 230))
    for x, y, sz, c in [(470, 78, 9, SB), (560, 52, 6, SP), (872 - 10, 236, 7, SB), (455, 440, 7, SP), (760, 450, 6, SB)]:
        layer(sparkle(x, y, sz, c))
    layer(lambda g: (heart(g, 452, 150, 9, (*PINK, 210)), heart(g, 846, 268, 8, (*PINK, 210)), heart(g, 520, 448, 7, (*PINK, 190))))


    out = base.convert("RGB").resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()





# ==========================================
# RENDERER PANEL BARU (glass / 3D — gaya kartu booster)
# Semua nama diawali _q / Q agar tidak bentrok dengan desain lama & booster.py
# ==========================================
QW, QH = 900, 500
_QSS = 2                       # supersampling; panel dirender sekali lalu di-cache
QCX, QCY = 667, 250            # pusat stage gelap
QSBOX = (468, 34, 866, 466)    # kotak stage gelap yang melayang
QSR = 36                       # radius sudut stage
_QPINK = (255, 104, 150)
_QPAL = {'base': (250, 251, 255),
 'corner': [(0.0, 1.12, 150, (40, 135, 245)),
            (1.03, -0.08, 170, (165, 80, 235)),
            (0.5, 1.25, 140, (70, 205, 255))],
 'ink': (8, 12, 52),
 'ink2': (112, 56, 214),
 'mute': (86, 88, 134),
 'acc': (158, 72, 226),
 'acc2': (36, 140, 242),
 'glow': (130, 110, 250),
 'sph': ((34, 104, 226), (150, 214, 255)),
 'bsph': ((88, 40, 200), (214, 128, 250)),
 'vig': (60, 56, 170),
 'tile': ((34, 24, 112), (2, 4, 36)),
 'rule': (36, 140, 242),
 'book': ((36, 140, 242), (158, 72, 226)),
 'cap': ((88, 44, 206), (36, 140, 242)),
 'pen': ((70, 34, 190), (40, 142, 246)),
 'nib': (228, 234, 250),
 'stops': [(255, 255, 255),
           (70, 196, 255),
           (238, 242, 255),
           (196, 112, 245),
           (255, 255, 255),
           (60, 150, 245)],
 'dk0': (8, 6, 34),
 'dk1': (36, 20, 100),
 'dglow': (124, 104, 255),
 'dsh': (30, 20, 110),
 'dtxt': (232, 228, 255),
 'dgrid': (190, 180, 255),
 'dgk': 1.0}

# Satu worker khusus: render panel tidak pernah berjalan paralel (hemat RAM).
_RENDER_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nanz-quote-render")

_QNOISE_CACHE = {}


def _qsc(v):
    return int(round(v * _QSS))


# ---- helper (disalin dari desain kartu booster, dengan nama _q* supaya tidak bentrok) ----


def _qlerp3(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def _ql(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


@lru_cache(maxsize=96)
def _qsans(size, wght=500, k=None):
    px = int(round(size * (k or _QSS)))
    for p in (FONT_SANS, FONT_BOLD, *FB):
        try:
            f = ImageFont.truetype(p, px)
        except Exception:
            continue
        if p == FONT_SANS:
            try:
                f.set_variation_by_axes([min(32, max(14, size)), wght])
            except Exception:
                try:
                    f.set_variation_by_name("Bold" if wght >= 600 else "Medium" if wght >= 500 else "Regular")
                except Exception:
                    pass
        return f
    return ImageFont.load_default()


@lru_cache(maxsize=16)
def _qserif(size):
    px = _qsc(size)
    for p in (FONT_SERIF, FONT_SANS, FONT_BOLD, *FB):
        try:
            return ImageFont.truetype(p, px)
        except Exception:
            continue
    return ImageFont.load_default()


@lru_cache(maxsize=1)
def _qlogo_raw():
    for p in LOGO_PATHS:
        try:
            im = Image.open(p).convert("RGBA")
            bb = im.getchannel("A").getbbox()
            return im.crop(bb) if bb else im
        except Exception:
            continue
    print("[Booster] Logo nanZ tidak ditemukan; kartu dibuat tanpa logo. Cek LOGO_PATHS.")
    return None


def _qhgrad(w, h, c0, c1):
    g = Image.linear_gradient("L").resize((h, w)).rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
    return Image.composite(Image.new("RGBA", (w, h), (*c1, 255)), Image.new("RGBA", (w, h), (*c0, 255)), g)


def _qrrmask(w, h, box, r):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([_qsc(v) for v in box], radius=_qsc(r), fill=255)
    return m


def _qsparkle(x, y, s):
    q = s * 0.22
    return [(x, y - s), (x + q, y - q), (x + s, y), (x + q, y + q),
            (x, y + s), (x - q, y + q), (x - s, y), (x - q, y - q)]


def _qbackground(P):
    w, h = QW * _QSS, QH * _QSS
    img = Image.new("RGBA", (w, h), (*P["base"], 255))
    for fx, fy, r, c in P["corner"]:
        m = Image.new("L", (w, h), 0)
        x, y, R = fx * w, fy * h, _qsc(r)
        ImageDraw.Draw(m).ellipse([x - R, y - R, x + R, y + R], fill=150)
        img.paste(Image.new("RGBA", (w, h), (*c, 255)), (0, 0), m.filter(ImageFilter.GaussianBlur(R * 0.38)))
    ov = _ql(w, h)
    d = ImageDraw.Draw(ov)
    for y in range(30, QH - 14, 22):          # garis buku tulis (motif sekolah)
        for x in range(34, 470, 2):
            a = int(40 * max(0, 1 - (x - 34) / 436) ** 1.3)
            if a > 0:
                d.line([(_qsc(x), _qsc(y)), (_qsc(x + 2), _qsc(y))], fill=(*P["rule"], a), width=_QSS)
    d.line([(_qsc(40), _qsc(12)), (_qsc(40), _qsc(QH - 12))], fill=(240, 120, 200, 46), width=_QSS)
    return Image.alpha_composite(img, ov)


def _qvignette(img, P):
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt(((xx - w * 0.55) / (w * 0.62)) ** 2 + ((yy - h * 0.5) / (h * 0.78)) ** 2)
    a = np.clip((d - 0.75) / 0.75, 0, 1) ** 1.6 * 46
    v = np.dstack([np.full((h, w), c) for c in P["vig"]] + [a]).astype(np.uint8)
    img.alpha_composite(Image.fromarray(v))


def _qhexagon(img, cx, cy, R, color, alpha, width=1.2):  # dipakai di atas panel gelap
    pts = [(cx + R * math.cos(math.radians(60 * i)), cy + R * math.sin(math.radians(60 * i))) for i in range(6)]
    l = _ql(*img.size)
    ImageDraw.Draw(l).line([(_qsc(x), _qsc(y)) for x, y in pts + [pts[0]]], fill=(*color, alpha),
                           width=_qsc(width), joint="curve")
    img.alpha_composite(l)


def _qsphere(r, c_dark, c_light, spec=1.0):
    n = _qsc(r) * 2 + 4
    yy, xx = np.mgrid[0:n, 0:n]
    c = n / 2
    R = _qsc(r)
    dx = (xx - c) / R
    dy = (yy - c) / R
    rr = dx ** 2 + dy ** 2
    inside = rr <= 1
    dz = np.sqrt(np.clip(1 - rr, 0, 1))
    Lv = np.array([-0.45, -0.55, 0.70])
    Lv /= np.linalg.norm(Lv)
    diff = np.clip(dx * Lv[0] + dy * Lv[1] + dz * Lv[2], 0, 1)
    spc = np.clip(diff, 0, 1) ** 28 * spec
    rim = np.clip(1 - dz, 0, 1) ** 2.2 * 0.35
    t = np.clip(diff * 0.95 + rim * 0.4, 0, 1)
    out = np.zeros((n, n, 4), np.float32)
    for i in range(3):
        out[..., i] = c_dark[i] + (c_light[i] - c_dark[i]) * t + 255 * spc * 0.7
    out[..., 3] = 255 * np.clip((1 - np.sqrt(rr)) * R, 0, 1) * inside
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def _qput_sphere(img, x, y, r, P, key="sph"):
    s = _qsphere(r, *P[key])
    sh = _ql(*img.size)
    sh.paste((*P["acc"], 110), (_qsc(x) - s.width // 2 + _qsc(2), _qsc(y) - s.height // 2 + _qsc(r * 0.9)),
             s.getchannel("A").point(lambda v: v * 3 // 4))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_qsc(r * 0.6))))
    img.alpha_composite(s, (_qsc(x) - s.width // 2, _qsc(y) - s.height // 2))


def _qglass_tile(img, cx, cy, size, rot, P, dark=False):
    w, h = img.size
    half = size / 2
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([_qsc(cx - half), _qsc(cy - half), _qsc(cx + half), _qsc(cy + half)],
                                        radius=_qsc(size * 0.24), fill=255)
    m = m.rotate(rot, center=(_qsc(cx), _qsc(cy)), resample=Image.BICUBIC)
    sh = _ql(w, h)
    sh.paste((*P["acc"], 120 if dark else 70), (0, _qsc(9)), m)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_qsc(9))))
    img.paste(img.filter(ImageFilter.GaussianBlur(_qsc(8))), (0, 0), m)
    gr = Image.linear_gradient("L").resize((w, h)).rotate(45, resample=Image.BICUBIC)
    top = Image.new("RGBA", (w, h), (255, 255, 255, 78 if dark else 150))
    bot = Image.new("RGBA", (w, h), (*P["acc2"], 90 if dark else 70))
    body = Image.composite(bot, top, gr)
    body.putalpha(ImageChops.multiply(body.getchannel("A"), m))
    img.alpha_composite(body)
    edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_QSS * 2 + 1)))
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 215)), (0, 0), edge)
    sheen = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sheen).ellipse([_qsc(cx - half), _qsc(cy - half - size * 0.35),
                                   _qsc(cx + half * 0.3), _qsc(cy - half * 0.05)], fill=110)
    sheen = ImageChops.multiply(
        sheen.rotate(rot, center=(_qsc(cx), _qsc(cy)), resample=Image.BICUBIC).filter(ImageFilter.GaussianBlur(_qsc(4))), m)
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0), sheen)


def _qrot(cx, cy, rot):
    c, s = math.cos(math.radians(-rot)), math.sin(math.radians(-rot))
    return lambda p: (cx + p[0] * c - p[1] * s, cy + p[0] * s + p[1] * c)


def _qicon_cap(img, cx, cy, size, rot, P):
    g = size * 0.34
    rp = _qrot(cx, cy, rot)
    ic = _ql(*img.size)
    d = ImageDraw.Draw(ic)
    poly = lambda pts, fill: d.polygon([(_qsc(a), _qsc(b)) for a, b in map(rp, pts)], fill=fill)
    top, base = P["cap"]
    poly([(-0.58 * g, 0.10 * g), (-0.58 * g, 0.66 * g), (0, 0.92 * g), (0.58 * g, 0.66 * g), (0.58 * g, 0.10 * g), (0, 0.40 * g)], (*base, 235))
    poly([(0, -0.70 * g), (1.12 * g, -0.12 * g), (0, 0.46 * g), (-1.12 * g, -0.12 * g)], (*top, 245))
    poly([(0, -0.70 * g), (1.12 * g, -0.12 * g), (0, -0.12 * g)], (255, 255, 255, 70))
    x0, y0 = rp((1.0 * g, -0.10 * g))
    x1, y1 = rp((1.0 * g, 0.62 * g))
    d.line([(_qsc(x0), _qsc(y0)), (_qsc(x1), _qsc(y1))], fill=(*base, 255), width=_qsc(1.6))
    d.ellipse([_qsc(x1 - 2.2), _qsc(y1 - 2.2), _qsc(x1 + 2.2), _qsc(y1 + 3.4)], fill=(*base, 255))
    img.alpha_composite(ic)


def _qribbon(img, P, x0=486, wd=22, y0=-6, y1=76):
    """Bookmark ribbon yang menggantung dari tepi atas."""
    w, h = img.size
    pts = [(x0, y0), (x0 + wd, y0), (x0 + wd, y1), (x0 + wd / 2, y1 - 10), (x0, y1)]
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon([(_qsc(a), _qsc(c)) for a, c in pts], fill=255)
    sh = _ql(w, h)
    sh.paste((*P["acc"], 120), (_qsc(2), _qsc(7)), m)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_qsc(5))))
    body = _ql(w, h)
    bd = ImageDraw.Draw(body)
    c0, c1 = P["acc2"], P["acc"]
    for y in range(_qsc(y0), _qsc(y1)):
        bd.line([(_qsc(x0), y), (_qsc(x0 + wd), y)], fill=(*_qlerp3(c0, c1, (y - _qsc(y0)) / (_qsc(y1) - _qsc(y0))), 255))
    img.paste(body, (0, 0), m)
    fl = _ql(w, h)
    fd = ImageDraw.Draw(fl)
    fd.rectangle([_qsc(x0), 0, _qsc(x0 + wd * 0.34), _qsc(y1)], fill=(255, 255, 255, 70))
    fd.rectangle([_qsc(x0 + wd * 0.80), 0, _qsc(x0 + wd), _qsc(y1)], fill=(0, 0, 40, 55))
    fl.putalpha(ImageChops.multiply(fl.getchannel("A"), m))
    img.alpha_composite(fl)
    d = ImageDraw.Draw(img)
    for y in range(8, int(y1 - 18), 6):                       # jahitan putus-putus
        d.line([(_qsc(x0 + wd / 2), _qsc(y)), (_qsc(x0 + wd / 2), _qsc(y + 3))], fill=(255, 255, 255, 190), width=_QSS)
    edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_QSS * 2 + 1)))
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 110)), (0, 0), edge)


def _qconic_ring(img, cx, cy, r_out, r_in, stops):
    n = _qsc(r_out) * 2 + 6
    yy, xx = np.mgrid[0:n, 0:n]
    c = n / 2
    dx, dy = xx - c, yy - c
    r = np.sqrt(dx ** 2 + dy ** 2)
    th = (np.arctan2(dy, dx) + math.pi) / (2 * math.pi)
    k = th * len(stops)
    i0 = np.floor(k).astype(int) % len(stops)
    i1 = (i0 + 1) % len(stops)
    f = k - np.floor(k)
    f = f * f * (3 - 2 * f)
    arr = np.array(stops, np.float32)
    col = arr[i0] * (1 - f[..., None]) + arr[i1] * f[..., None]
    a = np.clip(_qsc(r_out) - r, 0, 1) * np.clip(r - _qsc(r_in), 0, 1)
    im = Image.fromarray(np.dstack([col, a * 255]).astype(np.uint8))
    img.alpha_composite(im, (_qsc(cx) - n // 2, _qsc(cy) - n // 2))


def _qfoil_pill(img, box, P):
    w, h = img.size
    m = _qrrmask(w, h, box, (box[3] - box[1]) / 2)
    s = _ql(w, h)
    s.paste((*P["acc"], 120), (0, _qsc(5)), m)
    img.alpha_composite(s.filter(ImageFilter.GaussianBlur(_qsc(7))))
    img.paste(_qhgrad(w, h, P["acc"], P["acc2"]), (0, 0), m)
    gl = Image.new("L", (w, h), 0)
    ImageDraw.Draw(gl).rounded_rectangle([_qsc(box[0] + 2), _qsc(box[1] + 1.5), _qsc(box[2] - 2), _qsc((box[1] + box[3]) / 2)],
                                         radius=_qsc(6), fill=70)
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0), ImageChops.multiply(gl.filter(ImageFilter.GaussianBlur(1)), m))
    edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_QSS * 2 + 1)))
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 200)), (0, 0), edge)


def _qbrand_chip(img, x, y, P, u=1.0):
    """Watermark: chip kaca terang (logo nanZ + lockup "nanZ / SERVER"), sama untuk semua kartu nanZ.
    x, y = pojok kiri-atas chip. u = faktor skala (1.0 = kanvas 800x340).
    Dirender 4x pada canvas kecil lalu di-downscale supaya tepi dan teks kecil tetap tajam.
    Baris SERVER di-justify selaras lebar "nanZ" -> lockup rapi, rata kiri-kanan."""
    S, pad = 4, round(18 * u)
    h = 38 * u
    R = lambda v: int(round(v * S))
    logo = _qlogo_raw()
    lh = 26 * u
    lw = round(logo.width * lh / logo.height) if logo is not None else 0
    f1, f2 = _qsans(18 * u, 700, S), _qsans(6.5 * u, 700, S)
    t1, t2 = "nanZ", "SERVER"
    w1 = f1.getlength(t1) / S
    pl, gap, pr = 10 * u, 6 * u, 12 * u
    cw = math.ceil(pl + (lw + gap if lw else 0) + w1 + pr)
    W2, H2 = R(cw + 2 * pad), R(h + 2 * pad)
    ox = oy = pad

    def rr(box, r, fill=255):
        m = Image.new("L", (W2, H2), 0)
        ImageDraw.Draw(m).rounded_rectangle([R(v) for v in box], radius=R(r), fill=fill)
        return m

    m = rr((ox, oy, ox + cw, oy + h), h / 2)
    cv = _ql(W2, H2)

    # bayangan lembut + lip 3D tipis di bawah chip
    sh = _ql(W2, H2)
    sh.paste((*P["dsh"], 210), (0, R(5 * u)), m)
    cv.alpha_composite(sh.filter(ImageFilter.GaussianBlur(R(5 * u))))
    lip = _ql(W2, H2)
    lip.paste((*tuple(int(c * 0.55) for c in P["acc"]), 255), (0, R(2.4 * u)), m)
    cv.alpha_composite(lip)

    # badan kaca: putih -> lavender tipis
    g = Image.linear_gradient("L").resize((W2, H2))
    body = Image.composite(Image.new("RGBA", (W2, H2), (232, 237, 255, 255)),
                           Image.new("RGBA", (W2, H2), (255, 255, 255, 255)), g)
    cv.paste(body, (0, 0), m)

    # border gradien + highlight dalam
    inner = rr((ox + 1.5 * u, oy + 1.5 * u, ox + cw - 1.5 * u, oy + h - 1.5 * u), h / 2 - 1.5 * u)
    bd = Image.new("RGBA", (W2, H2))
    gd = ImageDraw.Draw(bd)
    for xx in range(W2):
        gd.line([(xx, 0), (xx, H2)], fill=(*_qlerp3(P["acc2"], P["acc"], xx / W2), 255))
    bd.putalpha(ImageChops.subtract(m, inner))
    cv.alpha_composite(bd)
    inner2 = rr((ox + 2.8 * u, oy + 2.8 * u, ox + cw - 2.8 * u, oy + h - 2.8 * u), h / 2 - 2.8 * u)
    hl = Image.new("RGBA", (W2, H2), (255, 255, 255, 0))
    hl.putalpha(ImageChops.subtract(inner, inner2).point(lambda v: v * 170 // 255))
    cv.alpha_composite(hl)

    # logo (sejajar tengah chip)
    tx = ox + pl
    if logo is not None:
        lg = logo.resize((R(lw), R(lh)), Image.LANCZOS)
        cv.alpha_composite(lg, (R(tx), R(oy + (h - lh) / 2)))
        tx += lw + gap

    # lockup teks: nanZ (navy, Z aksen) + SERVER (tracking di-justify ke lebar nanZ)
    cap1 = -f1.getbbox("Z", anchor="ls")[1] / S
    cap2 = -f2.getbbox("E", anchor="ls")[1] / S
    gap_t = 4.4 * u
    top = oy + (h - (cap1 + gap_t + cap2)) / 2
    b1, b2 = top + cap1, top + cap1 + gap_t + cap2
    d = ImageDraw.Draw(cv)
    zx = f1.getlength(t1) - f1.getlength("Z")
    d.text((R(tx), R(b1)), "nan", font=f1, fill=(*P["ink"], 255), anchor="ls")
    d.text((R(tx) + zx, R(b1)), "Z", font=f1, fill=(*P["acc2"], 255), anchor="ls")
    adv = [f2.getlength(c) for c in t2]
    trk = (f1.getlength(t1) - sum(adv)) / (len(t2) - 1)
    cx_ = R(tx)
    for c, a in zip(t2, adv):
        d.text((cx_, R(b2)), c, font=f2, fill=(*P["mute"], 255), anchor="ls")
        cx_ += a + trk

    small = cv.resize((round((cw + 2 * pad) * _QSS), round((h + 2 * pad) * _QSS)), Image.LANCZOS)
    img.alpha_composite(small, (_qsc(x - pad), _qsc(y - pad)))


def _qnoise():
    if "n" not in _QNOISE_CACHE:
        n = Image.effect_noise((QW * _QSS, QH * _QSS), 20).convert("L").point(lambda v: (v - 128) // 9 + 128)
        _QNOISE_CACHE["n"] = Image.merge("RGB", (n, n, n))
    return _QNOISE_CACHE["n"]


# ---- elemen panel quote ----


def _qpoly(d, pts, fill):
    d.polygon([(_qsc(a), _qsc(b)) for a, b in pts], fill=fill)


def _qheart_pts(x, y, r):
    pts = []
    for i in range(0, 360, 6):
        t = math.radians(i)
        hx = 16 * math.sin(t) ** 3
        hy = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((x + hx * r / 17, y + hy * r / 17))
    return pts


def _qplace_tile(img, tile, cx, cy, rot, shadow=(10, 6, 40, 170), blur=9, dy=9):
    """tile = RGBA ukuran logis (w,h)*SS. Dirotasi, dikasih bayangan, ditempel."""
    t = tile.rotate(rot, expand=True, resample=Image.BICUBIC)
    sh = _ql(*t.size)
    sh.paste(shadow, (0, 0), t.getchannel("A").point(lambda v: v * 3 // 4))
    sh = sh.filter(ImageFilter.GaussianBlur(_qsc(blur)))
    x, y = _qsc(cx) - t.width // 2, _qsc(cy) - t.height // 2
    img.alpha_composite(sh, (x, y + _qsc(dy)))
    img.alpha_composite(t, (x, y))


def _qtmask(w, h, box, r):
    m = Image.new("L", (_qsc(w), _qsc(h)), 0)
    ImageDraw.Draw(m).rounded_rectangle([_qsc(v) for v in box], radius=_qsc(r), fill=255)
    return m


def _qglass_rect(img, cx, cy, w, h, rot, r=22):
    """Kartu kaca: blur backdrop + gradien putih->aksen + tepi putih (sama seperti _gglass_tile)."""
    cw, ch = img.size
    m = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(m).rounded_rectangle([_qsc(cx - w / 2), _qsc(cy - h / 2), _qsc(cx + w / 2), _qsc(cy + h / 2)],
                                        radius=_qsc(r), fill=255)
    m = m.rotate(rot, center=(_qsc(cx), _qsc(cy)), resample=Image.BICUBIC)
    sh = _ql(cw, ch)
    sh.paste((6, 4, 40, 200), (0, _qsc(10)), m)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_qsc(11))))
    img.paste(img.filter(ImageFilter.GaussianBlur(_qsc(8))), (0, 0), m)
    gr = Image.linear_gradient("L").resize((cw, ch)).rotate(45, resample=Image.BICUBIC)
    top = Image.new("RGBA", (cw, ch), (255, 255, 255, 62))
    bot = Image.new("RGBA", (cw, ch), (*_QPAL["acc2"], 70))
    body = Image.composite(bot, top, gr)
    body.putalpha(ImageChops.multiply(body.getchannel("A"), m))
    img.alpha_composite(body)
    edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_QSS * 2 + 1)))
    img.paste(Image.new("RGBA", (cw, ch), (255, 255, 255, 215)), (0, 0), edge)
    sheen = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(sheen).ellipse([_qsc(cx - w / 2), _qsc(cy - h / 2 - h * 0.45), _qsc(cx + w * 0.1), _qsc(cy - h * 0.05)], fill=70)
    sheen = ImageChops.multiply(sheen.rotate(rot, center=(_qsc(cx), _qsc(cy)), resample=Image.BICUBIC)
                                .filter(ImageFilter.GaussianBlur(_qsc(5))), m)
    img.paste(Image.new("RGBA", (cw, ch), (255, 255, 255, 255)), (0, 0), sheen)


def _qwrap(font, text, maxw):
    out, cur = [], ""
    for wd in text.split():
        t = f"{cur} {wd}".strip()
        if font.getlength(t) <= _qsc(maxw):
            cur = t
        else:
            out.append(cur)
            cur = wd
    if cur:
        out.append(cur)
    return out


def _qmusic_pill(img, cx, cy, rot=-3, w=292, h=66):
    t = _ql(_qsc(w), _qsc(h))
    d = ImageDraw.Draw(t)
    d.rounded_rectangle([_qsc(2), _qsc(2), _qsc(w - 2), _qsc(h - 2)], radius=_qsc(h / 2), fill=(16, 10, 56, 240))
    g = _qhgrad(t.width, t.height, _QPAL["acc2"], _QPAL["acc"])
    m = _qtmask(w, h, (2, 2, w - 2, h - 2), h / 2)
    m2 = _qtmask(w, h, (3.6, 3.6, w - 3.6, h - 3.6), h / 2 - 1.6)
    g.putalpha(ImageChops.subtract(m, m2))
    t.alpha_composite(g)
    d = ImageDraw.Draw(t)
    pb = _qsphere(21, _QPAL["bsph"][0], (110, 190, 255))
    t.alpha_composite(pb, (_qsc(34) - pb.width // 2, _qsc(h / 2) - pb.height // 2))
    _qpoly(d, [(28.5, h / 2 - 9), (28.5, h / 2 + 9), (43, h / 2)], (255, 255, 255, 255))
    d.text((_qsc(64), _qsc(h / 2 - 10)), "NOW PLAYING", font=_qsans(9, 700), fill=(*_QPAL["dgrid"], 255), anchor="lm")
    d.text((_qsc(64), _qsc(h / 2 + 9)), "lofi_night.mp3", font=_qsans(12, 500), fill=(255, 255, 255, 255), anchor="lm")
    for i, bh in enumerate([8, 16, 10, 22, 14, 26, 12, 20, 9, 16, 7]):
        x = w - 106 + i * 8
        c = _qlerp3(_QPAL["acc2"], _QPAL["acc"], i / 10)
        d.rounded_rectangle([_qsc(x), _qsc(h / 2 - bh / 2), _qsc(x + 4), _qsc(h / 2 + bh / 2)], radius=_qsc(2), fill=(*c, 255))
    _qplace_tile(img, t, cx, cy, rot, shadow=(6, 4, 30, 200))


def _qsticker(img, cx, cy, r=44, rot=12):
    n = _qsc(r) * 2 + _qsc(22)
    t = _ql(n, n)
    c = n // 2
    ImageDraw.Draw(t).ellipse([c - _qsc(r + 5), c - _qsc(r + 5), c + _qsc(r + 5), c + _qsc(r + 5)], fill=(255, 255, 255, 255))
    ball = _qsphere(r, (236, 150, 20), (255, 232, 120), spec=0.8)
    t.alpha_composite(ball, (c - ball.width // 2, c - ball.height // 2))
    d = ImageDraw.Draw(t)
    ink = (66, 34, 100, 255)
    for ex in (-r * 0.36, r * 0.36):
        d.ellipse([c + _qsc(ex - 5), c + _qsc(-r * 0.22 - 7), c + _qsc(ex + 5), c + _qsc(-r * 0.22 + 7)], fill=ink)
        d.ellipse([c + _qsc(ex - 2.4), c + _qsc(-r * 0.22 - 5), c + _qsc(ex + 0.6), c + _qsc(-r * 0.22 - 2)], fill=(255, 255, 255, 230))
    for ex in (-r * 0.62, r * 0.62):
        d.ellipse([c + _qsc(ex - 7), c + _qsc(r * 0.12), c + _qsc(ex + 7), c + _qsc(r * 0.12 + 9)], fill=(255, 130, 130, 170))
    d.arc([c + _qsc(-r * 0.42), c + _qsc(-r * 0.12), c + _qsc(r * 0.42), c + _qsc(r * 0.52)], 15, 165, fill=ink, width=_qsc(3.6))
    _qplace_tile(img, t, cx, cy, rot, shadow=(6, 4, 30, 190))


def _qgrad_title(img, text, font, x, cy):
    w, h = img.size
    x0, y0, x1, y1 = _qsc(x - 24), _qsc(cy - 64), _qsc(x + 470), _qsc(cy + 64)
    cw, ch = x1 - x0, y1 - y0
    lx, ly = _qsc(x) - x0, _qsc(cy) - y0
    crop = img.crop((x0, y0, x1, y1))
    m = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(m).text((lx, ly), text, font=font, fill=255, anchor="lm")
    m3 = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(m3).text((lx, ly + _qsc(4)), text, font=font, fill=255, anchor="lm")
    sh = _ql(cw, ch)
    sh.paste((*_QPAL["acc"], 80), (0, 0), m3.filter(ImageFilter.GaussianBlur(_qsc(6))))
    crop.alpha_composite(sh)
    bb = m.getbbox()
    g = _ql(cw, ch)
    gd = ImageDraw.Draw(g)
    for xx in range(bb[0], bb[2] + 1):
        gd.line([(xx, bb[1]), (xx, bb[3])], fill=(*_qlerp3(_QPAL["ink"], _QPAL["ink2"], (xx - bb[0]) / max(1, bb[2] - bb[0])), 255))
    crop.paste(g, (0, 0), m)
    img.paste(crop, (x0, y0))


def _qrr_mask(box, r, w, h, inset=0):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([_qsc(box[0] + inset), _qsc(box[1] + inset), _qsc(box[2] - inset), _qsc(box[3] - inset)],
                                        radius=_qsc(r - inset), fill=255)
    return m


def _qfeed_card(img, cx, cy, w, h, rot):
    _qglass_rect(img, cx, cy, w, h, rot, r=22)
    t = _ql(_qsc(w), _qsc(h))
    d = ImageDraw.Draw(t)
    # thumbnail foto
    th = h - 28
    m = Image.new("L", t.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([_qsc(14), _qsc(14), _qsc(14 + th), _qsc(14 + th)], radius=_qsc(12), fill=255)
    g = Image.new("RGBA", t.size)
    gd = ImageDraw.Draw(g)
    for y in range(t.height):
        gd.line([(0, y), (t.width, y)], fill=(*_qlerp3((255, 196, 120), (112, 70, 204), y / t.height), 255))
    t.paste(g, (0, 0), m)
    d = ImageDraw.Draw(t)
    _qpoly(d, [(14, 14 + th), (14 + th * .32, 14 + th * .5), (14 + th * .55, 14 + th * .72), (14 + th * .78, 14 + th * .4), (14 + th, 14 + th * .75),
             (14 + th, 14 + th - 6), (14 + th - 6, 14 + th)], (70, 40, 134, 255))
    sun = _qsphere(8, (240, 170, 60), (255, 244, 190))
    t.alpha_composite(sun, (_qsc(14 + th * .7) - sun.width // 2, _qsc(14 + th * .24) - sun.height // 2))
    x0 = 14 + th + 16
    d.text((_qsc(x0), _qsc(26)), "ayu", font=_qsans(12, 700), fill=(255, 255, 255, 255), anchor="lm")
    d.text((_qsc(x0 + 28), _qsc(26)), "2 mnt", font=_qsans(9, 500), fill=(*_QPAL["dtxt"], 190), anchor="lm")
    for i, ww in enumerate((w - x0 - 20, w - x0 - 52)):
        d.rounded_rectangle([_qsc(x0), _qsc(44 + i * 14), _qsc(x0 + ww), _qsc(50 + i * 14)], radius=_qsc(3), fill=(255, 255, 255, 120 - i * 30))
    _qpoly(d, _qheart_pts(w - 50, 26, 6.5), (*_QPINK, 255))
    d.text((_qsc(w - 40), _qsc(26)), "56", font=_qsans(10.5, 700), fill=(255, 255, 255, 255), anchor="lm")
    t = t.rotate(rot, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(t, (_qsc(cx) - t.width // 2, _qsc(cy) - t.height // 2))


def _qhero_card(img, cx, cy, w=310, h=216, rot=-3):
    _qglass_rect(img, cx, cy, w, h, rot, r=26)
    t = _ql(_qsc(w), _qsc(h))
    d = ImageDraw.Draw(t)
    av = _qsphere(14, _QPAL["bsph"][0], _QPAL["bsph"][1])
    t.alpha_composite(av, (_qsc(36) - av.width // 2, _qsc(36) - av.height // 2))
    _qpoly(d, _qsparkle(36, 36, 7), (255, 255, 255, 255))
    d.text((_qsc(58), _qsc(30)), "nanZ", font=_qsans(13, 700), fill=(255, 255, 255, 255), anchor="lm")
    d.text((_qsc(58), _qsc(45)), "baru saja", font=_qsans(9.5, 500), fill=(*_QPAL["dtxt"], 210), anchor="lm")
    ft = _qsans(10, 700)
    tw = ft.getlength("tenang") / _QSS + 22
    mk = Image.new("L", t.size, 0)
    ImageDraw.Draw(mk).rounded_rectangle([_qsc(w - 26 - tw), _qsc(26), _qsc(w - 26), _qsc(46)], radius=_qsc(10), fill=255)
    t.paste(_qhgrad(t.width, t.height, _QPAL["acc"], _QPAL["acc2"]), (0, 0), mk)
    d.text((_qsc(w - 26 - tw / 2), _qsc(36)), "tenang", font=ft, fill=(255, 255, 255, 255), anchor="mm")
    d.line([(_qsc(26), _qsc(64)), (_qsc(w - 26), _qsc(64))], fill=(255, 255, 255, 60), width=_QSS)
    d.text((_qsc(24), _qsc(106)), "\u201c", font=_qserif(110), fill=(*_QPAL["acc2"], 255), anchor="lm")
    fq = _qserif(22)
    for j, ln in enumerate(_qwrap(fq, "Tidak apa-apa berjalan pelan, yang penting kamu tidak berhenti.", w - 60)):
        d.text((_qsc(30), _qsc(130 + j * 24)), ln, font=fq, fill=(255, 255, 255, 255), anchor="lm")
    d.line([(_qsc(26), _qsc(h - 40)), (_qsc(w - 26), _qsc(h - 40))], fill=(255, 255, 255, 60), width=_QSS)
    d.text((_qsc(28), _qsc(h - 22)), "QUOTE BY NANZ", font=_qsans(8.5, 700), fill=(*_QPAL["dgrid"], 220), anchor="lm")
    for i in range(3):
        d.ellipse([_qsc(w - 58 + i * 11 - 2.2), _qsc(h - 22 - 2.2), _qsc(w - 58 + i * 11 + 2.2), _qsc(h - 22 + 2.2)],
                  fill=(255, 255, 255, 200 - i * 55))
    t = t.rotate(rot, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(t, (_qsc(cx) - t.width // 2, _qsc(cy) - t.height // 2))


def _qfloat_chip(img, cx, cy, kind, txt):
    f = _qsans(12, 700)
    w = f.getlength(txt) / _QSS + 46
    x0, y0 = cx - w / 2, cy - 15
    _qglass_box(img, (x0, y0, x0 + w, y0 + 30), 15, ta=70, border=225)
    d = ImageDraw.Draw(img)
    if kind == "heart":
        _qpoly(d, _qheart_pts(x0 + 18, cy, 8), (*_QPINK, 255))
    else:
        d.rounded_rectangle([_qsc(x0 + 11), _qsc(cy - 6.5), _qsc(x0 + 25), _qsc(cy + 4.5)], radius=_qsc(4), fill=(255, 255, 255, 255))
        _qpoly(d, [(x0 + 14, cy + 3.5), (x0 + 13, cy + 8.5), (x0 + 19, cy + 4)], (255, 255, 255, 255))
    d.text((_qsc(x0 + 33), _qsc(cy)), txt, font=f, fill=(255, 255, 255, 255), anchor="lm")


def _qglass_box(img, box, r, ta=135, border=245):
    x0, y0, x1, y1 = box
    pad = 40
    cx0, cy0 = max(0, _qsc(x0 - pad)), max(0, _qsc(y0 - pad))
    cx1, cy1 = min(img.width, _qsc(x1 + pad)), min(img.height, _qsc(y1 + pad))
    crop = img.crop((cx0, cy0, cx1, cy1))
    w, h = crop.size
    ox, oy = cx0 / _QSS, cy0 / _QSS
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([_qsc(x0 - ox), _qsc(y0 - oy), _qsc(x1 - ox), _qsc(y1 - oy)], radius=_qsc(r), fill=255)
    s = _ql(w, h)
    s.paste((*_QPAL["acc"], 60), (0, _qsc(5)), m)
    crop.alpha_composite(s.filter(ImageFilter.GaussianBlur(_qsc(8))))
    crop.paste(crop.filter(ImageFilter.GaussianBlur(_qsc(8))), (0, 0), m)
    g = Image.linear_gradient("L").resize((w, h))
    body = Image.composite(Image.new("RGBA", (w, h), (236, 240, 255, ta)), Image.new("RGBA", (w, h), (255, 255, 255, ta)), g)
    crop.alpha_composite(Image.composite(body, _ql(w, h), m))
    edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_QSS * 2 + 1)))
    crop.paste(Image.new("RGBA", (w, h), (255, 255, 255, border)), (0, 0), edge)
    img.paste(crop, (cx0, cy0))


def _qstage_layer(w, h):
    stg = _ql(w, h)
    sm = _qrr_mask(QSBOX, QSR, w, h)
    g = Image.linear_gradient("L").resize((w, h))
    body = Image.composite(Image.new("RGBA", (w, h), (*_QPAL["dk1"], 255)), Image.new("RGBA", (w, h), (*_QPAL["dk0"], 255)), g)
    for gx, gy, r, col, a in ((QCX, QCY, 230, _QPAL["dglow"], 200), (850, 40, 170, _QPAL["acc2"], 110), (500, 470, 170, _QPAL["acc"], 120)):
        gm = Image.new("L", (w, h), 0)
        ImageDraw.Draw(gm).ellipse([_qsc(gx - r), _qsc(gy - r), _qsc(gx + r), _qsc(gy + r)], fill=a)
        body.paste(Image.new("RGBA", (w, h), (*col, 255)), (0, 0), gm.filter(ImageFilter.GaussianBlur(_qsc(r * .45))))
    dots = _ql(w, h)
    dd = ImageDraw.Draw(dots)
    for yy in range(46, 466, 16):
        for xx in range(480, 866, 16):
            dd.ellipse([_qsc(xx - .9), _qsc(yy - .9), _qsc(xx + .9), _qsc(yy + .9)], fill=(*_QPAL["dgrid"], 40))
    body.alpha_composite(dots)
    stg.paste(body, (0, 0), sm)
    return stg, sm



def _qframe_layer(P):
    w, h = QW * _QSS, QH * _QSS
    o = _qrrmask(w, h, (9, 9, QW - 9, QH - 9), 16)
    i = _qrrmask(w, h, (10.6, 10.6, QW - 10.6, QH - 10.6), 14.6)
    g = _qhgrad(w, h, P["acc2"], P["acc"])
    g.putalpha(ImageChops.subtract(o, i).point(lambda v: v * 150 // 255))
    o2 = _qrrmask(w, h, (11.6, 11.6, QW - 11.6, QH - 11.6), 14)
    i2 = _qrrmask(w, h, (12.6, 12.6, QW - 12.6, QH - 12.6), 13)
    hl = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    hl.putalpha(ImageChops.subtract(o2, i2).point(lambda v: v * 170 // 255))
    return Image.alpha_composite(g, hl)


def _render_quote_panel_v3() -> bytes:
    base = _qbackground(_QPAL)
    w, h = base.size
    _qvignette(base, _QPAL)

    # ---- bayangan stage ----
    stg, sm = _qstage_layer(w, h)
    sh = _ql(w, h)
    sh.paste((*_QPAL["dsh"], 190), (0, _qsc(14)), sm)
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_qsc(22))))

    # ---- isi stage ----
    _qhexagon(stg, QCX, QCY, 226, _QPAL["dgrid"], 44)
    _qhexagon(stg, QCX, QCY, 186, _QPAL["acc2"], 70, 1.0)
    rng = random.Random(9)
    st = _ql(w, h)
    sd = ImageDraw.Draw(st)
    for _ in range(46):
        x, y, r = rng.uniform(480, 856), rng.uniform(46, 456), rng.choice([.7, .9, 1.1, 1.4])
        sd.ellipse([_qsc(x - r), _qsc(y - r), _qsc(x + r), _qsc(y + r)], fill=(255, 255, 255, rng.randint(70, 190)))
    stg.alpha_composite(st)
    _qconic_ring(stg, QCX, QCY, 158, 155.6, _QPAL["stops"])
    for a in (20, 140, 205, 320):
        _qput_sphere(stg, QCX + 156.8 * math.cos(math.radians(a)), QCY + 156.8 * math.sin(math.radians(a)), 3.6, _QPAL)

    _qfeed_card(stg, 690, 108, 292, 100, 4)
    _qhero_card(stg, 664, 256, w=318, h=228, rot=-2)
    _qmusic_pill(stg, 668, 410, w=266, h=56, rot=0)
    _qribbon(stg, _QPAL, x0=500, wd=22, y0=-6, y1=84)
    d = ImageDraw.Draw(stg)
    for sx, sy, s_ in ((508, 396, 5), (836, 150, 6), (500, 190, 5), (840, 450, 5)):
        _qpoly(d, _qsparkle(sx, sy, s_), (255, 255, 255, 235))

    # ---- stage -> base (dipotong rounded rect) ----
    stg.putalpha(ImageChops.multiply(stg.getchannel("A"), sm))
    base.alpha_composite(stg)
    # border gradient + highlight
    bo = ImageChops.subtract(sm, _qrr_mask(QSBOX, QSR, w, h, 1.8))
    bg_ = _qhgrad(w, h, _QPAL["acc2"], _QPAL["acc"])
    bg_.putalpha(bo.point(lambda v: v * 235 // 255))
    base.alpha_composite(bg_)
    hi = ImageChops.subtract(_qrr_mask(QSBOX, QSR, w, h, 2.8), _qrr_mask(QSBOX, QSR, w, h, 3.8))
    hl = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    hl.putalpha(hi.point(lambda v: v * 90 // 255))
    base.alpha_composite(hl)

    # ---- elemen yang menembus stage ----
    _qsticker(base, 846, 356, r=34)
    _qfloat_chip(base, 850, 186, "heart", "128")
    _qfloat_chip(base, 476, 318, "chat", "12")
    _qglass_tile(base, 452, 84, 46, -10, _QPAL, dark=False)
    _qicon_cap(base, 452, 84, 46, -10, _QPAL)

    # ---------- kolom kiri ----------
    tx0 = 56
    _qbrand_chip(base, 22, 22, _QPAL)
    img = base
    d = ImageDraw.Draw(img)
    _qpoly(d, _qsparkle(tx0 + 6, 106, 6), (*_QPAL["acc"], 255))
    f_eb = _qsans(11.5, 700)
    x = tx0 + 20
    for c in "NANZ QUOTE CORNER":
        d.text((_qsc(x), _qsc(106)), c, font=f_eb, fill=(*_QPAL["ink2"], 255), anchor="lm")
        x += f_eb.getlength(c) / _QSS + 2.4
    d.text((_qsc(tx0), _qsc(156)), "Tulis", font=_qserif(46), fill=(*_QPAL["ink2"], 255), anchor="lm")
    _qgrad_title(img, "Quote-mu", _qsans(66, 800), tx0, 218)

    ul = _ql(w, h)
    u = ImageDraw.Draw(ul)
    x0, x1 = tx0 + 12, tx0 + 230
    for xx in range(_qsc(x0), _qsc(x1)):
        t = (xx - _qsc(x0)) / _qsc(x1 - x0)
        u.line([(xx, _qsc(268)), (xx, _qsc(268.8))], fill=(*_qlerp3(_QPAL["acc"], _QPAL["acc2"], t), int(255 * (1 - t) ** 0.8)))
    dm = 6
    u.polygon([(_qsc(tx0 + 3), _qsc(268.4 - dm / 1.4)), (_qsc(tx0 + 3 + dm / 1.4), _qsc(268.4)),
               (_qsc(tx0 + 3), _qsc(268.4 + dm / 1.4)), (_qsc(tx0 + 3 - dm / 1.4), _qsc(268.4))],
              fill=(*_QPAL["acc"], 255), outline=(255, 255, 255, 255))
    img.alpha_composite(ul)
    d = ImageDraw.Draw(img)
    d.text((_qsc(tx0 + 2), _qsc(293)), "Bagikan kata-kata dan perasaanmu.", font=_qsans(15, 600), fill=(*_QPAL["ink"], 255), anchor="lm")
    d.text((_qsc(tx0 + 2), _qsc(316)), "Tambahkan foto, lagu, atau sticker.", font=_qsans(13.5, 500), fill=(*_QPAL["mute"], 255), anchor="lm")

    # alur 3 langkah
    steps = (("Tulis", "Isi quote & mood", _QPAL["acc2"]), ("Lampirkan", "Foto, lagu, sticker", _QPAL["acc"]), ("Bagikan", "React & thread otomatis", (240, 120, 190)))
    sw, sy = 136, 358
    ln = _ql(w, h)
    ld = ImageDraw.Draw(ln)
    for i in range(2):
        xa, xb = tx0 + 16 + i * sw + 22, tx0 + 16 + (i + 1) * sw - 22
        for xx in range(_qsc(xa), _qsc(xb)):
            t = (xx - _qsc(xa)) / _qsc(xb - xa)
            if (xx // _qsc(1)) % 7 < 4:
                ld.line([(xx, _qsc(sy)), (xx, _qsc(sy + 1.2))], fill=(*_qlerp3(steps[i][2], steps[i + 1][2], t), 210))
    img.alpha_composite(ln)
    for i, (tt, ss, col) in enumerate(steps):
        sx = tx0 + 16 + i * sw
        halo = _ql(w, h)
        ImageDraw.Draw(halo).ellipse([_qsc(sx - 22), _qsc(sy - 22), _qsc(sx + 22), _qsc(sy + 22)], fill=(255, 255, 255, 190))
        img.alpha_composite(halo)
        sp = _qsphere(16, tuple(int(c * .62) for c in col), tuple(min(255, int(c * .5 + 135)) for c in col))
        shd = _ql(w, h)
        shd.paste((*col, 120), (_qsc(sx) - sp.width // 2, _qsc(sy) - sp.height // 2 + _qsc(5)), sp.getchannel("A"))
        img.alpha_composite(shd.filter(ImageFilter.GaussianBlur(_qsc(5))))
        img.alpha_composite(sp, (_qsc(sx) - sp.width // 2, _qsc(sy) - sp.height // 2))
        d = ImageDraw.Draw(img)
        d.text((_qsc(sx), _qsc(sy)), str(i + 1), font=_qsans(14, 800), fill=(255, 255, 255, 255), anchor="mm")
        d.text((_qsc(sx - 12), _qsc(sy + 34)), tt, font=_qsans(13, 700), fill=(*_QPAL["ink"], 255), anchor="lm")
        d.text((_qsc(sx - 12), _qsc(sy + 51)), ss, font=_qsans(9.5, 500), fill=(*_QPAL["mute"], 255), anchor="lm")

    ct = "Klik tombol di bawah untuk mulai"
    fcta = _qsans(12.5, 700)
    cw = fcta.getlength(ct) / _QSS + 70
    bx0, by0 = tx0, 432
    _qfoil_pill(img, (bx0, by0, bx0 + cw, by0 + 38), _QPAL)
    d = ImageDraw.Draw(img)
    d.text((_qsc(bx0 + 22), _qsc(by0 + 19)), ct, font=fcta, fill=(255, 255, 255, 255), anchor="lm")
    ax = bx0 + cw - 24
    cl = _ql(w, h)
    ImageDraw.Draw(cl).ellipse([_qsc(ax - 11), _qsc(by0 + 8), _qsc(ax + 11), _qsc(by0 + 30)], fill=(255, 255, 255, 55), outline=(255, 255, 255, 230), width=_QSS)
    img.alpha_composite(cl)
    d = ImageDraw.Draw(img)
    d.line([(_qsc(ax - 4), _qsc(by0 + 17)), (_qsc(ax), _qsc(by0 + 22)), (_qsc(ax + 4), _qsc(by0 + 17))], fill=(255, 255, 255, 255), width=_qsc(2), joint="curve")

    img.alpha_composite(_qframe_layer(_QPAL))
    out = img.convert("RGB")
    out = Image.blend(out, ImageChops.overlay(out, _qnoise()), 0.2)
    out = out.resize((QW, QH), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _qclear_caches():
    """Bebaskan memori setelah render (font/noise/logo tidak dibutuhkan lagi)."""
    _qsans.cache_clear()
    _qserif.cache_clear()
    _qlogo_raw.cache_clear()
    _QNOISE_CACHE.clear()


def generate_quote_panel() -> bytes:
    """PNG panel quote 900x500. Desain baru; jatuh ke desain lama bila numpy/font/logo bermasalah."""
    if np is None:
        print("[Quote] numpy belum terpasang (pip install numpy); memakai desain panel lama.")
        return _generate_quote_panel_legacy()
    try:
        return _render_quote_panel_v3()
    except MemoryError:
        raise
    except Exception as e:
        print(f"[Quote] Desain panel baru gagal ({e!r}); memakai desain lama.")
        return _generate_quote_panel_legacy()
    finally:
        _qclear_caches()


# ==========================================
# MODAL QUOTE
# ==========================================
class QuoteModal(discord.ui.Modal, title="Buat Quote"):

    quote = discord.ui.TextInput(
        label="Isi Quote",
        style=discord.TextStyle.paragraph,
        placeholder="Tulis quote kamu...",
        required=True,
        max_length=500
    )

    mood = discord.ui.TextInput(
        label="Mood / Emoji",
        placeholder="🌙✨💔",
        required=False,
        max_length=50
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):

        # simpan data sementara
        self.bot.quote_data[interaction.user.id] = {
            "quote": self.quote.value,
            "mood": self.mood.value
        }

        await interaction.response.send_message(
            (
                "**Quote berhasil dibuat.**\n\n"
                "Sekarang klik tombol dibawah "
                "untuk upload foto, lagu, atau sticker."
            ),
            view=UploadView(self.bot),
            ephemeral=True
        )


# ==========================================
# VIEW UPLOAD
# ==========================================
class UploadView(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot

    # ==========================================
    # FUNCTION KIRIM QUOTE
    # ==========================================
    async def send_quote(
        self,
        interaction: discord.Interaction,
        files=None,
        stickers=None
    ) -> bool:

        files = files or []
        stickers = stickers or []

        # ambil data quote
        data = self.bot.quote_data.get(
            interaction.user.id
        )

        if not data:
            return False

        quote_channel = self.bot.get_channel(
            QUOTE_CHANNEL_ID
        )

        if not quote_channel:
            return False

        # ==========================================
        # EMBED
        # ==========================================
        colors = [
            discord.Color.blurple(),
            discord.Color.purple(),
            discord.Color.magenta(),
            discord.Color.teal(),
            discord.Color.random()
        ]

        embed = discord.Embed(
            description=f"❝ *{data['quote']}* ❞",
            color=random.choice(colors)
        )

        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )

        # mood
        if data["mood"]:
            embed.add_field(
                name="Mood",
                value=data["mood"],
                inline=False
            )

        image_file = None
        music_files = []

        for file in files:

            filename = file.filename.lower()

            # FOTO
            if filename.endswith(
                ("png", "jpg", "jpeg", "webp", "gif")
            ):
                image_file = file

            # LAGU
            elif filename.endswith(
                ("mp3", "wav", "ogg", "m4a")
            ):
                music_files.append(file)

        # FOTO KE EMBED
        if image_file:
            embed.set_image(
                url=f"attachment://{image_file.filename}"
            )

        # STICKER KE EMBED
        if stickers:

            sticker = stickers[0]

            try:
                embed.set_thumbnail(
                    url=sticker.url
                )
            except:
                pass

        embed.set_footer(
            text=f"Quote by {interaction.user.display_name}"
        )

        # ==========================================
        # KIRIM EMBED
        # ==========================================
        send_files = []

        if image_file:
            send_files.append(image_file)

        quote_message = await quote_channel.send(
            embed=embed,
            files=send_files
        )

        # ==========================================
        # AUTO REACT (lovelike)
        # ==========================================
        try:
            await quote_message.add_reaction(LIKE_EMOJI)
        except discord.HTTPException:
            # fallback kalau emoji tidak bisa dipakai bot
            try:
                await quote_message.add_reaction("❤️")
            except discord.HTTPException:
                pass

        # ==========================================
        # AUTO THREAD
        # ==========================================
        try:
            await quote_message.create_thread(
                name=(
                    f"💭 Quote by "
                    f"{interaction.user.display_name}"
                )
            )
        except:
            pass

        # ==========================================
        # KIRIM LAGU
        # ==========================================
        for music in music_files:

            music_embed = discord.Embed(
                description=(
                    f"**Now Playing**\n"
                    f"`{music.filename}`"
                ),
                color=discord.Color.dark_theme()
            )

            await quote_channel.send(
                embed=music_embed,
                file=music
            )

        # hapus cache
        self.bot.quote_data.pop(
            interaction.user.id,
            None
        )

        return True

    # ==========================================
    # BUTTON UPLOAD
    # ==========================================
    @discord.ui.button(
        label="Upload Media",
        style=discord.ButtonStyle.blurple,
        custom_id="quote_upload_media"
    )
    async def upload_media(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            (
                "Sekarang kirim:\n"
                "🖼️ Foto\n"
                "🎵 Lagu\n"
                "🌸 Sticker\n\n"
                ">> Pesan akan otomatis dihapus.\n"
                "⏳ Tunggu dalam 60 detik."
            ),
            ephemeral=True
        )

        def check(message):
            return (
                message.author == interaction.user
                and message.channel == interaction.channel
            )

        files = []
        stickers = []

        try:
            msg = await self.bot.wait_for(
                "message",
                timeout=60,
                check=check
            )

            # file
            if msg.attachments:
                files = [
                    await attachment.to_file()
                    for attachment in msg.attachments
                ]

            # sticker
            if msg.stickers:
                stickers = msg.stickers

            # auto delete
            try:
                await msg.delete()
            except:
                pass

        except:
            await interaction.followup.send(
                "❌ Waktu upload habis.",
                ephemeral=True
            )
            return

        ok = await self.send_quote(
            interaction,
            files=files,
            stickers=stickers
        )

        if ok:
            await interaction.followup.send(
                "**Quote berhasil dikirim.**",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Data quote tidak ditemukan, silakan buat ulang.",
                ephemeral=True
            )

    # ==========================================
    # BUTTON SKIP
    # ==========================================
    @discord.ui.button(
        label="Skip",
        style=discord.ButtonStyle.gray,
        custom_id="quote_skip_media"
    )
    async def skip_media(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        ok = await self.send_quote(
            interaction
        )

        if ok:
            await interaction.followup.send(
                "**Quote berhasil dikirim tanpa media.**",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Data quote tidak ditemukan, silakan buat ulang.",
                ephemeral=True
            )


# ==========================================
# VIEW UTAMA (PERSISTENT)
# ==========================================
class QuoteView(discord.ui.View):

    def __init__(self, bot):
        # timeout=None + custom_id = tombol tetap aktif
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Buat Quote",
        style=discord.ButtonStyle.blurple,
        custom_id="quote_make_button"
    )
    async def make_quote(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            QuoteModal(self.bot)
        )


# ==========================================
# STATE PANEL (agar foto panel bisa di-edit otomatis tanpa kirim ulang)
# ==========================================
def _panel_version() -> str:
    """Sidik jari desain: berubah bila kode file ini atau logo diganti."""
    h = hashlib.sha256()
    try:
        with open(__file__, "rb") as f:
            h.update(f.read())
    except OSError:
        pass
    for p in LOGO_PATHS:
        try:
            with open(p, "rb") as f:
                h.update(f.read())
            break
        except OSError:
            continue
    return h.hexdigest()[:16]


def _load_panel_state():
    try:
        with open(QUOTE_PANEL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and data.get("channel_id") and data.get("message_id"):
            return data
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[Quote] Gagal membaca {QUOTE_PANEL_FILE}: {e}")
    return None


def _save_panel_state(state: dict):
    temp = QUOTE_PANEL_FILE + ".tmp"
    try:
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, QUOTE_PANEL_FILE)
    except Exception as e:
        print(f"[Quote] Gagal menyimpan {QUOTE_PANEL_FILE}: {e}")
        try:
            if os.path.exists(temp):
                os.remove(temp)
        except OSError:
            pass


# ==========================================
# COG
# ==========================================
class QuoteSystem(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self._panel_png = None  # cache PNG panel
        self._panel_lock = asyncio.Lock()
        self._sync_task = None

        if not hasattr(bot, "quote_data"):
            bot.quote_data = {}

    async def cog_load(self):
        # daftarkan view supaya tombol tetap jalan
        # walaupun bot restart
        self.bot.add_view(QuoteView(self.bot))
        # bila desain panel berubah sejak terakhir, foto panel lama di-edit otomatis
        self._sync_task = asyncio.create_task(self._auto_refresh_panel())

    async def cog_unload(self):
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()

    # -------------------- RENDER & EDIT --------------------
    async def _get_panel_png(self, force: bool = False) -> bytes:
        async with self._panel_lock:
            if force or self._panel_png is None:
                loop = asyncio.get_running_loop()
                self._panel_png = await loop.run_in_executor(_RENDER_EXECUTOR, generate_quote_panel)
            return self._panel_png

    async def _edit_panel_photo(self, message: discord.Message, force_render: bool = False, view=None):
        """Ganti HANYA foto di pesan panel (tombol & pesan tetap, tidak kirim ulang)."""
        png = await self._get_panel_png(force=force_render)
        kwargs = {"view": view} if view is not None else {}
        await message.edit(
            attachments=[discord.File(io.BytesIO(png), filename="quote_panel.png")],
            **kwargs
        )
        _save_panel_state({
            "channel_id": message.channel.id,
            "message_id": message.id,
            "version": _panel_version(),
        })

    async def _fetch_panel_message(self, state: dict) -> discord.Message:
        channel = self.bot.get_channel(int(state["channel_id"]))
        if channel is None:
            channel = await self.bot.fetch_channel(int(state["channel_id"]))
        return await channel.fetch_message(int(state["message_id"]))

    async def _auto_refresh_panel(self):
        """Dijalankan tiap bot start: kalau kode/logo panel berubah, edit foto panel lama."""
        try:
            await self.bot.wait_until_ready()
            state = _load_panel_state()
            if not state:
                return
            if state.get("version") == _panel_version():
                return  # desain sama, tidak perlu apa-apa
            try:
                message = await self._fetch_panel_message(state)
            except discord.NotFound:
                print("[Quote] Pesan panel terdaftar sudah dihapus. Jalankan !setupquote lagi.")
                return
            except discord.HTTPException as e:
                print(f"[Quote] Gagal mengambil pesan panel: {e}")
                return
            if self.bot.user and message.author.id != self.bot.user.id:
                print("[Quote] Pesan panel bukan milik bot ini; tidak bisa di-edit.")
                return
            await self._edit_panel_photo(message)
            print("[Quote] Foto panel quote diperbarui otomatis (tanpa kirim ulang).")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[Quote] Auto-refresh panel gagal: {e!r}")

    # -------------------- COMMANDS --------------------
    @commands.command(name="setupquote")
    @commands.has_permissions(administrator=True)
    async def setupquote(self, ctx):
        """Kirim panel quote baru dan daftarkan agar fotonya bisa di-update otomatis."""
        async with ctx.typing():
            png = await self._get_panel_png()

        sent = await ctx.send(
            file=discord.File(
                io.BytesIO(png),
                filename="quote_panel.png"
            ),
            view=QuoteView(self.bot)
        )
        _save_panel_state({
            "channel_id": sent.channel.id,
            "message_id": sent.id,
            "version": _panel_version(),
        })

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command(name="bindquote")
    @commands.has_permissions(administrator=True)
    async def bindquote(self, ctx, message: discord.Message):
        """Daftarkan panel lama yang sudah ada: !bindquote <link pesan panel>. Fotonya langsung diganti desain baru."""
        if self.bot.user and message.author.id != self.bot.user.id:
            await ctx.send("Pesan itu bukan milik bot, jadi tidak bisa di-edit.")
            return
        async with ctx.typing():
            await self._edit_panel_photo(message, view=QuoteView(self.bot))
        await ctx.send("Panel terdaftar. Foto sudah diganti; ke depannya update otomatis saat bot restart.",
                       delete_after=10)

    @commands.command(name="refreshquote")
    @commands.has_permissions(administrator=True)
    async def refreshquote(self, ctx):
        """Paksa render ulang & ganti foto panel terdaftar (tanpa restart)."""
        state = _load_panel_state()
        if not state:
            await ctx.send("Belum ada panel terdaftar. Pakai `!setupquote` atau `!bindquote <link pesan>`.")
            return
        async with ctx.typing():
            try:
                message = await self._fetch_panel_message(state)
            except discord.NotFound:
                await ctx.send("Pesan panel sudah dihapus. Jalankan `!setupquote` lagi.")
                return
            await self._edit_panel_photo(message, force_render=True)
        await ctx.send("Foto panel quote diperbarui.", delete_after=8)

    @setupquote.error
    @bindquote.error
    @refreshquote.error
    async def quote_admin_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Command ini hanya untuk administrator.")
        elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            await ctx.send("Format: `!bindquote <link pesan panel>`")
        else:
            print(f"[Quote] Error command: {error!r}")
            await ctx.send("Terjadi kesalahan. Periksa log bot.")


# ==========================================
# SETUP
# ==========================================
async def setup(bot):
    await bot.add_cog(QuoteSystem(bot))