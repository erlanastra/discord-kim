import asyncio
import io
import json
import math
import os
import random
import re
import threading
import unicodedata
from functools import lru_cache

import discord
from discord.ext import commands
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

try:
    import numpy as np  # dipakai desain kartu baru (pip install numpy)
except ImportError:  # pragma: no cover
    np = None

# =========================================================
# KONFIGURASI — booster_data.json lama tetap digunakan
# =========================================================
BOOST_CHANNEL_ID = 1554100419637149838
ROLE_REQ_CHANNEL_ID = 1515029186530771077
ROLE_PRIME_ID = 1561383676019736596
ROLE_ELITE_ID = 1561384548158152744
DATA_FILE = "booster_data.json"

E_NITRO = "<a:nitro:1553688995635011635>"
E_BLUE = "<a:blue:1512787254312042496>"
E_PURPLE = "<a:purple:1512787191234035803>"

FONT_BOLD    = "fonts/LEMONMILK-Bold.otf"
FONT_MEDIUM  = "fonts/LEMONMILK-Medium.otf"
FONT_REGULAR = "fonts/LEMONMILK-Regular.otf"
# Desain kartu baru: taruh file font di folder fonts/ (nama file harus sama).
FONT_SANS    = "fonts/Inter.ttf"                     # Inter (variable font, OFL)
FONT_SERIF   = "fonts/InstrumentSerif-Italic.ttf"    # Instrument Serif Italic (OFL)
# Logo nanZ Server (PNG transparan 1024x1024). Dicari berurutan; boleh ditaruh di salah satunya.
LOGO_PATHS   = ("assets/nanz_logo.png", "nanz_logo.png", "fonts/nanz_logo.png")
_FALLBACKS   = ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf")

PALETTES = {
    "prime": dict(bg_top=(18, 10, 45), bg_bot=(40, 20, 80), a=(130, 80, 255), b=(80, 180, 255),
                  sa=(160, 120, 255), sb=(150, 210, 255), card=(30, 15, 65)),
    "elite": dict(bg_top=(30, 20, 8), bg_bot=(72, 46, 12), a=(235, 165, 30), b=(255, 215, 100),
                  sa=(255, 200, 90), sb=(255, 235, 170), card=(50, 32, 10)),
}

W, H = 800, 340


def _font(path, size):
    for p in (path, *_FALLBACKS):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))


def _fit_font(draw, text, path, start, max_w, min_size=24):
    size = start
    while size > min_size:
        f = _font(path, size)
        b = draw.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= max_w:
            return f, text
        size -= 2
    f = _font(path, min_size)
    while text and draw.textbbox((0, 0), text + "…", font=f)[2] > max_w:
        text = text[:-1]
    return f, text + "…"


def _fit_size(draw, lines, path, start, max_w, min_size=10):
    size = start
    while size > min_size:
        f = _font(path, size)
        if max(draw.textlength(line, font=f) for line in lines) <= max_w:
            return f
        size -= 1
    return _font(path, min_size)


def _prepare_avatar(avatar_bytes, size):
    av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4, size * 4), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(av, (0, 0), mask)
    return out


def _make_fx(seed=7):
    rng = random.Random(seed)
    stars = [{"x": rng.uniform(0, W), "y": rng.uniform(0, H), "r": rng.uniform(1.0, 2.6),
              "tw": rng.random(), "a": rng.randint(90, 200)} for _ in range(70)]
    sparkles = [{"x": rng.uniform(15, W - 15), "y": rng.uniform(12, H - 12),
                 "s": rng.uniform(5, 10), "tw": rng.uniform(0.4, 1.0)} for _ in range(13)]
    bubbles = [{"x": rng.uniform(0, W), "y": rng.uniform(0, H),
                "r": rng.uniform(3, 7), "a": rng.randint(80, 150)} for _ in range(18)]
    return {"stars": stars, "sparkles": sparkles, "bubbles": bubbles}


def _sparkle_poly(x, y, sz):
    q = sz * 0.25
    return [(x, y - sz), (x + q, y - q), (x + sz, y), (x + q, y + q),
            (x, y + sz), (x - q, y + q), (x - sz, y), (x - q, y - q)]


def _background(fx, P):
    bg = Image.new("RGB", (W, H))
    bd = ImageDraw.Draw(bg)
    for y in range(H):
        bd.line([(0, y), (W, y)], fill=_lerp_color(P["bg_top"], P["bg_bot"], y / H))
    base = bg.convert("RGBA")

    orbs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od0 = ImageDraw.Draw(orbs)
    for ox, oy, br, oc in [(W * .10, H * .20, 140, P["a"]), (W * .90, H * .70, 140, P["b"]),
                           (W * .50, H * .00, 110, P["a"])]:
        for st in range(br, 0, -5):
            od0.ellipse([ox - st, oy - st, ox + st, oy + st],
                        fill=(*oc, _clamp(60 * (st / br) ** 2.8 * 0.85)))
    base = Image.alpha_composite(base, orbs)

    aur = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ad = ImageDraw.Draw(aur)
    for by, amp, k, off, col, a in [(235, 30, 2, 0.0, P["b"], 60), (268, 24, 3, 2.0, P["a"], 75),
                                    (300, 18, 4, 4.0, P["sb"], 50)]:
        pts = [(x, by + amp * math.sin(math.tau * k * x / W + off)) for x in range(0, W + 10, 10)]
        ad.polygon(pts + [(W, H), (0, H)], fill=(*col, a))
    base = Image.alpha_composite(base, aur.filter(ImageFilter.GaussianBlur(6)))

    fl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fl)
    for item in fx["stars"]:
        r, tw = item["r"], item["tw"]
        fd.ellipse([item["x"] - r, item["y"] - r, item["x"] + r, item["y"] + r],
                   fill=(*_lerp_color(P["a"], P["b"], tw), _clamp(item["a"] * (0.45 + 0.55 * tw))) )
    for item in fx["sparkles"]:
        tw = item["tw"]
        fd.polygon(_sparkle_poly(item["x"], item["y"], item["s"] * (0.35 + 0.65 * tw)),
                   fill=(*_lerp_color(P["sb"], P["sa"], tw), _clamp(70 + 185 * tw)))
    for bubble in fx["bubbles"]:
        r, a = bubble["r"], bubble["a"]
        fd.ellipse([bubble["x"] - r, bubble["y"] - r, bubble["x"] + r, bubble["y"] + r], outline=(255, 255, 255, a), width=1)
        fd.ellipse([bubble["x"] - r * .35, bubble["y"] - r * .35, bubble["x"] + r * .1, bubble["y"] + r * .1],
                   fill=(255, 255, 255, a))
    return Image.alpha_composite(base, fl)


def _render_booster_card_legacy(avatar_bytes: bytes, name: str, tier: int, total: int, boosts: int = 1) -> bytes:
    """boosts == 1 -> Prime Boost; boosts >= 2 -> Elite Boost."""
    elite = boosts >= 2
    P = PALETTES["elite" if elite else "prime"]
    A, B, SA, SB, CARD_BG = P["a"], P["b"], P["sa"], P["sb"], P["card"]
    AVB = 176
    avatar = _prepare_avatar(avatar_bytes, AVB)
    base = _background(_make_fx(seed=11), P)
    cx, cy = 662, 170
    TX0, TX1 = 46, 440

    def edge(y):
        return 560 - 90 * y / H

    S = 2
    pan = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    pdr = ImageDraw.Draw(pan)
    pdr.polygon([(0, 0), (edge(0) * S, 0), (edge(H) * S, H * S), (0, H * S)], fill=(*CARD_BG, 190))
    for y in range(0, H, 3):
        pdr.line([(edge(y) * S, y * S), (edge(y + 3) * S, (y + 3) * S)],
                 fill=(*_lerp_color(B, A, y / H), 255), width=7)
    for y in range(0, H, 3):
        pdr.line([((edge(y) - 14) * S, y * S), ((edge(y + 3) - 14) * S, (y + 3) * S)],
                 fill=(*_lerp_color(B, A, y / H), 90), width=3)
    base = Image.alpha_composite(base, pan.resize((W, H), Image.LANCZOS))

    spot = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spot)
    for r, a in [(190, 40), (160, 55), (135, 70)]:
        sd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*A, a))
    base = Image.alpha_composite(base, spot.filter(ImageFilter.GaussianBlur(22)))

    rr = AVB // 2 + 12
    ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse([cx - rr - 26, cy - rr - 26, cx + rr + 26, cy + rr + 26], outline=(255, 255, 255, 40), width=1)
    rd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(255, 255, 255, 60), width=2)
    box = [cx - rr, cy - rr, cx + rr, cy + rr]
    rd.arc(box, -70, 40, fill=(*SB, 255), width=6)
    rd.arc(box, 110, 220, fill=(*SA, 255), width=6)
    if elite:
        b2 = [cx - rr - 13, cy - rr - 13, cx + rr + 13, cy + rr + 13]
        rd.arc(b2, 20, 100, fill=(*SA, 255), width=4)
        rd.arc(b2, 200, 280, fill=(*SB, 255), width=4)
    for i in range(8):
        a = i * math.tau / 8 + 0.3
        R2 = rr + 26
        px, py = cx + R2 * math.cos(a), cy + R2 * math.sin(a)
        rad = 4 if i % 2 == 0 else 3
        rd.ellipse([px - rad, py - rad, px + rad, py + rad], fill=(*(SB if i % 2 == 0 else SA), 235))
    for sx, sy, sz in [(cx - 118, cy - 96, 11), (cx + 120, cy - 82, 9), (cx + 104, cy + 100, 12)]:
        rd.polygon(_sparkle_poly(sx, sy, sz), fill=(*SB, 235))
    base = Image.alpha_composite(base, ring)
    base.alpha_composite(avatar, (cx - AVB // 2, cy - AVB // 2))

    bx, by, br = cx + 66, cy + 66, 18
    bd = ImageDraw.Draw(base)
    bd.ellipse([bx - br - 4, by - br - 4, bx + br + 4, by + br + 4], fill=(*CARD_BG, 255))
    bd.ellipse([bx - br, by - br, bx + br, by + br], fill=(*A, 255))
    if elite:
        bd.text((bx, by), "x2", font=_font(FONT_BOLD, 16), fill=(255, 255, 255, 255), anchor="mm")
    else:
        bd.polygon(_sparkle_poly(bx, by, 12), fill=(255, 255, 255, 255))

    tl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(tl)
    f_pil = _font(FONT_MEDIUM, 14)
    f_lab = _font(FONT_MEDIUM, 15)
    pil = "ELITE BOOST" if elite else "PRIME BOOST"
    pw = int(td.textlength(pil, font=f_pil)) + 56
    td.rounded_rectangle([TX0, 32, TX0 + pw, 62], radius=15, fill=(*A, 235))
    td.polygon(_sparkle_poly(TX0 + 20, 47, 7), fill=(255, 255, 255, 255))
    td.text((TX0 + 36, 47), pil, font=f_pil, fill=(255, 255, 255, 255), anchor="lm")
    td.text((TX0, 96), "TERIMA KASIH BANYAK," if elite else "TERIMA KASIH,",
            font=f_lab, fill=(*SB, 255), anchor="lm")
    f_name, name_fit = _fit_font(td, name, FONT_BOLD, 52, TX1 - TX0)
    td.text((TX0, 140), name_fit, font=f_name, fill=(255, 255, 255, 255), anchor="lm")
    for x in range(TX0, TX0 + 260):
        f = 1 - (x - TX0) / 260
        c = (*_lerp_color(B, A, (x - TX0) / 260), _clamp(255 * f ** 0.7))
        td.line([(x, 176), (x, 178)], fill=c)
    if elite:
        lines = ["Dua boost sekaligus! Kamu bener-bener bikin",
                 "sekolah nanZ naik level, kamu luar biasa!"]
    else:
        lines = ["Boost kamu bikin sekolah nanZ makin keren,",
                 "makasih udah jadi murid yang peduli sama sekolah!"]
    f_body = _fit_size(td, lines, FONT_REGULAR, 16, TX1 - TX0)
    td.text((TX0, 204), lines[0], font=f_body, fill=(235, 230, 220, 255), anchor="lm")
    td.text((TX0, 230), lines[1], font=f_body, fill=(235, 230, 220, 255), anchor="lm")
    c1, c2 = f"Level {tier}", f"Total {total} Boost"
    f_chip = _fit_size(td, [c1, c2], FONT_MEDIUM, 14, 150)
    cyy = 290

    def chip(x, txt, col):
        w = int(td.textlength(txt, font=f_chip)) + 52
        td.rounded_rectangle([x, cyy - 15, x + w, cyy + 15], radius=15, fill=(*col, 56),
                             outline=(*col, 217), width=1)
        ix = x + 19
        td.ellipse([ix - 10, cyy - 10, ix + 10, cyy + 10], fill=(*col, 255))
        td.polygon(_sparkle_poly(ix, cyy, 6), fill=(255, 255, 255, 255))
        td.text((x + 36, cyy), txt, font=f_chip, fill=(255, 255, 255, 255), anchor="lm")
        return x + w

    nx = chip(TX0, c1, B)
    chip(nx + 12, c2, A)
    base = Image.alpha_composite(base, tl)
    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


# =========================================================
# NANZ CARD V2 — glass / 3D minimal / tema sekolah
# Renderer baru. Signature publik tetap: render_booster_card(...)
# =========================================================
_SS = 2                      # supersampling (render 2x lalu diperkecil)
_RENDER_LOCK = threading.Lock()
_STATIC_CACHE = {}           # layer statis per tier (tidak bergantung user)
_FRAME_CACHE = {}
_NOISE_CACHE = {}
RENDER_INFO = {"engine": None, "error": None}   # diisi tiap render; dipakai !test_boost

# Warna biru/ungu Prime diambil dari logo nanZ; Elite = gold.
_GP = {
    "prime": dict(
        base=(244, 246, 254),
        corner=[(0.0, 1.12, 150, (40, 135, 245)), (1.03, -0.08, 170, (165, 80, 235)),
                (0.50, 1.25, 140, (70, 205, 255))],
        ink=(8, 12, 52), ink2=(112, 56, 214), mute=(86, 88, 134),
        acc=(158, 72, 226), acc2=(36, 140, 242), glow=(130, 110, 250),
        sph=((34, 104, 226), (150, 214, 255)), bsph=((88, 40, 200), (214, 128, 250)),
        vig=(60, 56, 170), tile=((34, 24, 112), (2, 4, 36)), rule=(36, 140, 242),
        book=((36, 140, 242), (158, 72, 226)), cap=((88, 44, 206), (36, 140, 242)),
        pen=((70, 34, 190), (40, 142, 246)), nib=(228, 234, 250),
        stops=[(255, 255, 255), (70, 196, 255), (238, 242, 255), (196, 112, 245),
               (255, 255, 255), (60, 150, 245)],
    ),
    "elite": dict(
        base=(251, 247, 239),
        corner=[(0.0, 1.12, 150, (255, 190, 80)), (1.03, -0.08, 170, (255, 150, 90)),
                (0.50, 1.25, 140, (255, 215, 130))],
        ink=(44, 26, 6), ink2=(178, 104, 8), mute=(126, 100, 68),
        acc=(205, 128, 14), acc2=(244, 178, 58), glow=(255, 190, 90),
        sph=((232, 150, 30), (255, 232, 170)), bsph=((150, 78, 0), (236, 150, 24)),
        vig=(120, 70, 40), tile=((34, 24, 112), (2, 4, 36)), rule=(214, 150, 40),
        book=((244, 178, 58), (205, 128, 14)), cap=((176, 104, 8), (244, 178, 58)),
        pen=((150, 80, 10), (246, 190, 76)), nib=(255, 226, 150),
        stops=[(255, 248, 225), (244, 178, 58), (255, 252, 238), (205, 128, 14),
               (255, 246, 215), (255, 208, 110)],
    ),
}


# Sisi GELAP (panel avatar di kanan) — kontras tegas dengan sisi TERANG (kolom teks di kiri).
_GP["prime"].update(dk0=(8, 6, 34), dk1=(36, 20, 100), dglow=(124, 104, 255), dsh=(30, 20, 110),
                    dtxt=(232, 228, 255), dgrid=(190, 180, 255), dgk=1.0)
_GP["elite"].update(dk0=(10, 6, 2), dk1=(40, 22, 4), dglow=(255, 172, 64), dsh=(96, 54, 10),
                    dtxt=(255, 238, 200), dgrid=(255, 215, 150), dgk=0.5)
_GP["prime"]["base"] = (250, 251, 255)
_GP["elite"]["base"] = (255, 251, 244)


def _sc(v):
    return int(round(v * _SS))


def _gedge_x(y):
    """Garis pemisah diagonal terang/gelap (koordinat 800x340)."""
    return 506 - 62 * y / H


def _lerp3(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def _gl(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


@lru_cache(maxsize=96)
def _gsans(size, wght=500):
    px = _sc(size)
    for p in (FONT_SANS, FONT_BOLD, *_FALLBACKS):
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
def _gserif(size):
    px = _sc(size)
    for p in (FONT_SERIF, FONT_SANS, FONT_BOLD, *_FALLBACKS):
        try:
            return ImageFont.truetype(p, px)
        except Exception:
            continue
    return ImageFont.load_default()


@lru_cache(maxsize=1)
def _glogo_raw():
    for p in LOGO_PATHS:
        try:
            im = Image.open(p).convert("RGBA")
            bb = im.getchannel("A").getbbox()
            return im.crop(bb) if bb else im
        except Exception:
            continue
    print("[Booster] Logo nanZ tidak ditemukan; kartu dibuat tanpa logo. Cek LOGO_PATHS.")
    return None


@lru_cache(maxsize=4)
def _glogo(hpx):
    im = _glogo_raw()
    if im is None:
        return None
    return im.resize((max(1, round(im.width * hpx / im.height)), hpx), Image.LANCZOS)


def _gglyph(font, ch):
    im = Image.new("L", (_sc(100), _sc(80)), 0)
    ImageDraw.Draw(im).text((8, 8), ch, font=font, fill=255)
    return im.tobytes()


def _gclean(name, font):
    """Buang karakter yang tidak ada di font (emoji, CJK, Arab, dsb) agar tidak muncul kotak 'NO GLYPH'."""
    try:
        notdef = _gglyph(font, "\U0010FFFF")      # bitmap glyph .notdef milik font
    except Exception:
        notdef = None
    out = []
    for ch in str(name):
        if unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co", "Cn"):
            continue
        if notdef is not None and not ch.isspace():
            try:
                if _gglyph(font, ch) == notdef:
                    continue
            except Exception:
                pass
        out.append(ch)
    clean = re.sub(r"\s+", " ", "".join(out)).strip()
    return clean or "Booster"


def _gfit(text, start, wmax, wght):
    s = start
    while s > 22:
        f = _gsans(s, wght)
        if f.getlength(text) <= _sc(wmax):
            return f, text
        s -= 2
    f = _gsans(22, wght)
    while text and f.getlength(text + "…") > _sc(wmax):
        text = text[:-1]
    return f, text + "…"


def _gsparkle(x, y, s):
    q = s * 0.22
    return [(x, y - s), (x + q, y - q), (x + s, y), (x + q, y + q),
            (x, y + s), (x - q, y + q), (x - s, y), (x - q, y - q)]


def _grrmask(w, h, box, r):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([_sc(v) for v in box], radius=_sc(r), fill=255)
    return m


def _ghgrad(w, h, c0, c1):
    g = Image.linear_gradient("L").resize((h, w)).rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
    return Image.composite(Image.new("RGBA", (w, h), (*c1, 255)), Image.new("RGBA", (w, h), (*c0, 255)), g)


def _gavatar(avatar_bytes, size):
    av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((size, size), Image.LANCZOS)
    m = Image.new("L", (size * 2, size * 2), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size * 2 - 1, size * 2 - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(av, (0, 0), m.resize((size, size), Image.LANCZOS))
    return out


def _gbackground(P):
    w, h = W * _SS, H * _SS
    img = Image.new("RGBA", (w, h), (*P["base"], 255))
    for fx, fy, r, c in P["corner"]:
        m = Image.new("L", (w, h), 0)
        x, y, R = fx * w, fy * h, _sc(r)
        ImageDraw.Draw(m).ellipse([x - R, y - R, x + R, y + R], fill=150)
        img.paste(Image.new("RGBA", (w, h), (*c, 255)), (0, 0), m.filter(ImageFilter.GaussianBlur(R * 0.38)))
    ov = _gl(w, h)
    d = ImageDraw.Draw(ov)
    for y in range(30, H - 14, 22):          # garis buku tulis (motif sekolah)
        for x in range(34, 470, 2):
            a = int(40 * max(0, 1 - (x - 34) / 436) ** 1.3)
            if a > 0:
                d.line([(_sc(x), _sc(y)), (_sc(x + 2), _sc(y))], fill=(*P["rule"], a), width=_SS)
    d.line([(_sc(40), _sc(12)), (_sc(40), _sc(H - 12))], fill=(240, 120, 200, 46), width=_SS)
    return Image.alpha_composite(img, ov)


def _gdark_mask(w, h):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon([(_sc(_gedge_x(0)), 0), (w, 0), (w, h), (_sc(_gedge_x(H)), h)], fill=255)
    return m


def _gdark_panel(img, P):
    """Panel gelap di kanan: gradien dalam + glow + grid titik, dengan bayangan jatuh ke sisi terang."""
    w, h = img.size
    m = _gdark_mask(w, h)
    sh = _gl(w, h)
    sh.paste((*P["dsh"], 110), (_sc(-7), 0), m)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(11))))

    g = Image.linear_gradient("L").resize((w, h))
    body = Image.composite(Image.new("RGBA", (w, h), (*P["dk1"], 255)), Image.new("RGBA", (w, h), (*P["dk0"], 255)), g)
    for gx, gy, r, col, a in ((_AV_CX, _AV_CY, 190, P["dglow"], 205), (790, -10, 150, P["acc2"], 95),
                              (520, 350, 130, P["acc"], 90)):
        gm = Image.new("L", (w, h), 0)
        ImageDraw.Draw(gm).ellipse([_sc(gx - r), _sc(gy - r), _sc(gx + r), _sc(gy + r)], fill=int(a * P["dgk"]))
        body.paste(Image.new("RGBA", (w, h), (*col, 255)), (0, 0), gm.filter(ImageFilter.GaussianBlur(_sc(r * 0.45))))
    dots = _gl(w, h)
    dd = ImageDraw.Draw(dots)
    for yy in range(14, H, 16):                 # grid titik = kertas berpetak (pasangan garis buku di sisi terang)
        for xx in range(440, W, 16):
            dd.ellipse([_sc(xx - 0.9), _sc(yy - 0.9), _sc(xx + 0.9), _sc(yy + 0.9)], fill=(*P["dgrid"], 40))
    body.alpha_composite(dots)
    img.paste(body, (0, 0), m)

    # garis cahaya di sepanjang seam
    pts = [(_sc(_gedge_x(y)), _sc(y)) for y in range(0, H + 1, 10)]
    glow = _gl(w, h)
    gd = ImageDraw.Draw(glow)
    for i in range(len(pts) - 1):
        c = _lerp3(P["acc2"], P["acc"], i / (len(pts) - 1))
        gd.line([pts[i], pts[i + 1]], fill=(*c, 255), width=_sc(3))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(_sc(5))))
    ln = _gl(w, h)
    ld = ImageDraw.Draw(ln)
    for i in range(len(pts) - 1):
        c = _lerp3(P["acc2"], P["acc"], i / (len(pts) - 1))
        ld.line([pts[i], pts[i + 1]], fill=(*c, 255), width=_sc(1.6))
    img.alpha_composite(ln)
    hl = _gl(w, h)
    hd = ImageDraw.Draw(hl)
    for i in range(len(pts) - 1):
        hd.line([(pts[i][0] + _sc(2), pts[i][1]), (pts[i + 1][0] + _sc(2), pts[i + 1][1])], fill=(255, 255, 255, 70), width=_SS)
    img.alpha_composite(hl)


def _gstars(img, P, seed=9):
    """Bintang kecil + kilau di panel gelap."""
    rng = random.Random(seed)
    w, h = img.size
    l = _gl(w, h)
    d = ImageDraw.Draw(l)
    for _ in range(46):
        y = rng.uniform(8, H - 8)
        x = rng.uniform(_gedge_x(y) + 12, W - 8)
        r = rng.choice([0.7, 0.9, 1.1, 1.4])
        d.ellipse([_sc(x - r), _sc(y - r), _sc(x + r), _sc(y + r)], fill=(255, 255, 255, rng.randint(70, 190)))
    img.alpha_composite(l)
    for _ in range(5):
        y = rng.uniform(20, H - 20)
        x = rng.uniform(_gedge_x(y) + 26, W - 22)
        s = rng.choice([4, 5, 6])
        ImageDraw.Draw(img).polygon([(_sc(a), _sc(b)) for a, b in _gsparkle(x, y, s)],
                                    fill=(*_lerp3((255, 255, 255), P["dgrid"], 0.3), 210))


def _gvignette(img, P):
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt(((xx - w * 0.55) / (w * 0.62)) ** 2 + ((yy - h * 0.5) / (h * 0.78)) ** 2)
    a = np.clip((d - 0.75) / 0.75, 0, 1) ** 1.6 * 46
    v = np.dstack([np.full((h, w), c) for c in P["vig"]] + [a]).astype(np.uint8)
    img.alpha_composite(Image.fromarray(v))


def _ghexagon(img, cx, cy, R, color, alpha, width=1.2):  # dipakai di atas panel gelap
    pts = [(cx + R * math.cos(math.radians(60 * i)), cy + R * math.sin(math.radians(60 * i))) for i in range(6)]
    l = _gl(*img.size)
    ImageDraw.Draw(l).line([(_sc(x), _sc(y)) for x, y in pts + [pts[0]]], fill=(*color, alpha),
                           width=_sc(width), joint="curve")
    img.alpha_composite(l)


def _glight_sweep(img):
    w, h = img.size
    l = _gl(w, h)
    ImageDraw.Draw(l).polygon([(_sc(585), 0), (_sc(640), 0), (_sc(520), _sc(H)), (_sc(465), _sc(H))],
                              fill=(255, 255, 255, 26))
    img.alpha_composite(l.filter(ImageFilter.GaussianBlur(_sc(16))))


def _gbokeh(img, P, seed=5, n=16):
    rng = random.Random(seed)
    w, h = img.size
    l = _gl(w, h)
    d = ImageDraw.Draw(l)
    for _ in range(n):
        y = rng.uniform(14, 330)
        x = rng.uniform(_gedge_x(y) + 16, 792)
        r = rng.choice([2, 2.5, 3, 4, 6])
        a = rng.randint(50, 120)
        col = rng.choice([(255, 255, 255), P["dglow"], P["acc2"], (255, 255, 255)])
        d.ellipse([_sc(x - r), _sc(y - r), _sc(x + r), _sc(y + r)], fill=(*col, a))
        if r >= 4:
            d.ellipse([_sc(x - r), _sc(y - r), _sc(x + r), _sc(y + r)],
                      outline=(255, 255, 255, min(180, a + 60)), width=_SS)
    img.alpha_composite(l.filter(ImageFilter.GaussianBlur(0.8)))


def _gsphere(r, c_dark, c_light, spec=1.0):
    n = _sc(r) * 2 + 4
    yy, xx = np.mgrid[0:n, 0:n]
    c = n / 2
    R = _sc(r)
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


def _gput_sphere(img, x, y, r, P, key="sph"):
    s = _gsphere(r, *P[key])
    sh = _gl(*img.size)
    sh.paste((*P["acc"], 110), (_sc(x) - s.width // 2 + _sc(2), _sc(y) - s.height // 2 + _sc(r * 0.9)),
             s.getchannel("A").point(lambda v: v * 3 // 4))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(r * 0.6))))
    img.alpha_composite(s, (_sc(x) - s.width // 2, _sc(y) - s.height // 2))


def _gglass_tile(img, cx, cy, size, rot, P, dark=False):
    w, h = img.size
    half = size / 2
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([_sc(cx - half), _sc(cy - half), _sc(cx + half), _sc(cy + half)],
                                        radius=_sc(size * 0.24), fill=255)
    m = m.rotate(rot, center=(_sc(cx), _sc(cy)), resample=Image.BICUBIC)
    sh = _gl(w, h)
    sh.paste((*P["acc"], 120 if dark else 70), (0, _sc(9)), m)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(9))))
    img.paste(img.filter(ImageFilter.GaussianBlur(_sc(8))), (0, 0), m)
    gr = Image.linear_gradient("L").resize((w, h)).rotate(45, resample=Image.BICUBIC)
    top = Image.new("RGBA", (w, h), (255, 255, 255, 78 if dark else 150))
    bot = Image.new("RGBA", (w, h), (*P["acc2"], 90 if dark else 70))
    body = Image.composite(bot, top, gr)
    body.putalpha(ImageChops.multiply(body.getchannel("A"), m))
    img.alpha_composite(body)
    edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_SS * 2 + 1)))
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 215)), (0, 0), edge)
    sheen = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sheen).ellipse([_sc(cx - half), _sc(cy - half - size * 0.35),
                                   _sc(cx + half * 0.3), _sc(cy - half * 0.05)], fill=110)
    sheen = ImageChops.multiply(
        sheen.rotate(rot, center=(_sc(cx), _sc(cy)), resample=Image.BICUBIC).filter(ImageFilter.GaussianBlur(_sc(4))), m)
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0), sheen)


def _grot(cx, cy, rot):
    c, s = math.cos(math.radians(-rot)), math.sin(math.radians(-rot))
    return lambda p: (cx + p[0] * c - p[1] * s, cy + p[0] * s + p[1] * c)


def _gicon_book(img, cx, cy, size, rot, P):
    g = size * 0.34
    rp = _grot(cx, cy, rot)
    ic = _gl(*img.size)
    d = ImageDraw.Draw(ic)
    poly = lambda pts, fill: d.polygon([(_sc(a), _sc(b)) for a, b in map(rp, pts)], fill=fill)
    cl, cr = P["book"]
    poly([(-1.05 * g, -0.55 * g), (-0.04 * g, -0.30 * g), (-0.04 * g, 0.78 * g), (-1.05 * g, 0.50 * g)], (*cl, 240))
    poly([(1.05 * g, -0.55 * g), (0.04 * g, -0.30 * g), (0.04 * g, 0.78 * g), (1.05 * g, 0.50 * g)], (*cr, 240))
    for k in range(3):
        y0 = -0.08 * g + 0.2 * g * k
        poly([(-0.86 * g, y0 - 0.12 * g), (-0.24 * g, y0 + 0.04 * g), (-0.24 * g, y0 + 0.08 * g), (-0.86 * g, y0 - 0.08 * g)], (255, 255, 255, 150))
        poly([(0.86 * g, y0 - 0.12 * g), (0.24 * g, y0 + 0.04 * g), (0.24 * g, y0 + 0.08 * g), (0.86 * g, y0 - 0.08 * g)], (255, 255, 255, 150))
    poly([(-1.05 * g, -0.55 * g), (-0.04 * g, -0.30 * g), (-0.04 * g, -0.24 * g), (-1.05 * g, -0.49 * g)], (255, 255, 255, 120))
    img.alpha_composite(ic)


def _gicon_cap(img, cx, cy, size, rot, P):
    g = size * 0.34
    rp = _grot(cx, cy, rot)
    ic = _gl(*img.size)
    d = ImageDraw.Draw(ic)
    poly = lambda pts, fill: d.polygon([(_sc(a), _sc(b)) for a, b in map(rp, pts)], fill=fill)
    top, base = P["cap"]
    poly([(-0.58 * g, 0.10 * g), (-0.58 * g, 0.66 * g), (0, 0.92 * g), (0.58 * g, 0.66 * g), (0.58 * g, 0.10 * g), (0, 0.40 * g)], (*base, 235))
    poly([(0, -0.70 * g), (1.12 * g, -0.12 * g), (0, 0.46 * g), (-1.12 * g, -0.12 * g)], (*top, 245))
    poly([(0, -0.70 * g), (1.12 * g, -0.12 * g), (0, -0.12 * g)], (255, 255, 255, 70))
    x0, y0 = rp((1.0 * g, -0.10 * g))
    x1, y1 = rp((1.0 * g, 0.62 * g))
    d.line([(_sc(x0), _sc(y0)), (_sc(x1), _sc(y1))], fill=(*base, 255), width=_sc(1.6))
    d.ellipse([_sc(x1 - 2.2), _sc(y1 - 2.2), _sc(x1 + 2.2), _sc(y1 + 3.4)], fill=(*base, 255))
    img.alpha_composite(ic)


def _gpen_image(Lp, Wd, c0, c1, nibc):
    Lc = _sc(Lp) + 8
    Wc = _sc(Wd) + 8
    yy, xx = np.mgrid[0:Wc, 0:Lc].astype(np.float32)
    cy = Wc / 2
    R = _sc(Wd) / 2
    xs = 4
    bl = _sc(Lp * 0.72) + xs
    cw = _sc(3.4)
    nl = _sc(Lp) + xs
    dy = yy - cy
    hw_body = np.where(xx < xs + R, np.sqrt(np.clip(R ** 2 - (xx - (xs + R)) ** 2, 0, None)), R)
    hw = np.where(xx <= bl, hw_body, 0).astype(np.float32)
    col = (xx > bl) & (xx <= bl + cw)
    hw = np.where(col, R * 0.94, hw)
    nb = (xx > bl + cw) & (xx <= nl)
    t = np.clip((xx - (bl + cw)) / max(1, (nl - (bl + cw))), 0, 1)
    hw = np.where(nb, R * 0.82 * (1 - t ** 1.3), hw)
    ring = (xx > xs + _sc(Lp * 0.46)) & (xx < xs + _sc(Lp * 0.46) + _sc(2.4))
    alpha = np.clip(hw - np.abs(dy) + 0.6, 0, 1) * (hw > 0.3)
    v = np.clip(dy / np.maximum(hw, 1), -1, 1)
    shade = 0.60 + 0.40 * np.clip(1 - ((v + 0.38) / 1.38) ** 2, 0, 1)
    edge = 1 - 0.32 * np.abs(v) ** 3
    spec = np.exp(-((v + 0.46) / 0.13) ** 2) * 0.55 + np.exp(-((v - 0.62) / 0.10) ** 2) * 0.12
    tt = np.clip((xx - xs) / (bl - xs), 0, 1)[..., None]
    base = np.array(c0, np.float32) * (1 - tt) + np.array(c1, np.float32) * tt
    silver = np.array([216, 223, 242], np.float32)
    base = np.where((col | ring)[..., None], silver, base)
    base = np.where(nb[..., None], np.array(nibc, np.float32), base)
    rgb = base * shade[..., None] * edge[..., None] + 255 * spec[..., None]
    slit = nb & (np.abs(dy) < _sc(0.5)) & (t > 0.22)
    rgb = np.where(slit[..., None], rgb * 0.35, rgb)
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), alpha * 255]).astype(np.uint8))


def _gput_pen(img, cx, cy, Lp, Wd, ang, P):
    pen = _gpen_image(Lp, Wd, *P["pen"], P["nib"]).rotate(ang, resample=Image.BICUBIC, expand=True)
    sh = _gl(*img.size)
    sh.paste((*P["acc"], 120), (_sc(cx) - pen.width // 2 + _sc(3), _sc(cy) - pen.height // 2 + _sc(9)), pen.getchannel("A"))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(7))))
    img.alpha_composite(pen, (_sc(cx) - pen.width // 2, _sc(cy) - pen.height // 2))


def _gconic_ring(img, cx, cy, r_out, r_in, stops):
    n = _sc(r_out) * 2 + 6
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
    a = np.clip(_sc(r_out) - r, 0, 1) * np.clip(r - _sc(r_in), 0, 1)
    im = Image.fromarray(np.dstack([col, a * 255]).astype(np.uint8))
    img.alpha_composite(im, (_sc(cx) - n // 2, _sc(cy) - n // 2))


def _gfoil_pill(img, box, P):
    w, h = img.size
    m = _grrmask(w, h, box, (box[3] - box[1]) / 2)
    s = _gl(w, h)
    s.paste((*P["acc"], 120), (0, _sc(5)), m)
    img.alpha_composite(s.filter(ImageFilter.GaussianBlur(_sc(7))))
    img.paste(_ghgrad(w, h, P["acc"], P["acc2"]), (0, 0), m)
    gl = Image.new("L", (w, h), 0)
    ImageDraw.Draw(gl).rounded_rectangle([_sc(box[0] + 2), _sc(box[1] + 1.5), _sc(box[2] - 2), _sc((box[1] + box[3]) / 2)],
                                         radius=_sc(6), fill=70)
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0), ImageChops.multiply(gl.filter(ImageFilter.GaussianBlur(1)), m))
    edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_SS * 2 + 1)))
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 200)), (0, 0), edge)


def _glogo_tile(img, x, y, T, P):
    w, h = img.size
    m = _grrmask(w, h, (x, y, x + T, y + T), T * 0.27)
    s1 = _gl(w, h)
    s1.paste((*P["acc"], 150), (0, _sc(10)), m)
    img.alpha_composite(s1.filter(ImageFilter.GaussianBlur(_sc(10))))
    s2 = _gl(w, h)
    s2.paste((10, 8, 40, 150), (0, _sc(3)), m)
    img.alpha_composite(s2.filter(ImageFilter.GaussianBlur(_sc(3))))
    gr = Image.linear_gradient("L").resize((w, h)).rotate(30, resample=Image.BICUBIC)
    t0, t1 = P["tile"]
    body = Image.composite(Image.new("RGBA", (w, h), (*t1, 255)), Image.new("RGBA", (w, h), (*t0, 255)), gr)
    img.paste(body, (0, 0), m)
    inner = m.filter(ImageFilter.MinFilter(_SS * 2 + 1))
    top = ImageChops.subtract(m, ImageChops.offset(inner, 0, _sc(2)))
    band = Image.linear_gradient("L").resize((w, h)).transpose(Image.FLIP_TOP_BOTTOM).point(lambda v: 255 if v > 200 else 0)
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 70)), (0, 0), ImageChops.multiply(top, band))
    sheen = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sheen).ellipse([_sc(x - T * 0.35), _sc(y - T * 0.55), _sc(x + T * 0.75), _sc(y + T * 0.38)], fill=46)
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0),
              ImageChops.multiply(sheen.filter(ImageFilter.GaussianBlur(_sc(5))), m))
    edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_SS * 2 + 1)))
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 60)), (0, 0), edge)
    lg = _glogo(_sc(T * 0.88))
    if lg is not None:
        lx, ly = _sc(x + T / 2) - lg.width // 2, _sc(y + T / 2) - lg.height // 2 + _sc(1)
        gl = _gl(w, h)
        gl.paste((90, 140, 255, 120), (lx, ly), lg.getchannel("A"))
        img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(_sc(6))))
        img.alpha_composite(lg, (lx, ly))
    else:
        ImageDraw.Draw(img).polygon([(_sc(a), _sc(b)) for a, b in _gsparkle(x + T / 2, y + T / 2, 18)], fill=(255, 255, 255, 255))
    # border gradien tipis (identitas biru -> ungu)
    m2 = _grrmask(w, h, (x + 1.4, y + 1.4, x + T - 1.4, y + T - 1.4), T * 0.27 - 1.4)
    g = _ghgrad(w, h, P["acc2"], P["acc"])
    g.putalpha(ImageChops.subtract(m, m2).point(lambda v: v * 210 // 255))
    img.alpha_composite(g)


def _gpill(img, box, tint, ta, P, border=245, sh=48, blur=8):
    """Pill kaca (backdrop blur) — dikerjakan pada crop kecil agar cepat."""
    x0, y0, x1, y1 = box
    pad = 40
    cx0, cy0 = max(0, _sc(x0 - pad)), max(0, _sc(y0 - pad))
    cx1, cy1 = min(img.width, _sc(x1 + pad)), min(img.height, _sc(y1 + pad))
    crop = img.crop((cx0, cy0, cx1, cy1))
    w, h = crop.size
    ox, oy = cx0 / _SS, cy0 / _SS
    m = _grrmask(w, h, (x0 - ox, y0 - oy, x1 - ox, y1 - oy), (y1 - y0) / 2)
    s = _gl(w, h)
    s.paste((*P["acc"], sh), (0, _sc(4)), m)
    crop.alpha_composite(s.filter(ImageFilter.GaussianBlur(_sc(7))))
    crop.paste(crop.filter(ImageFilter.GaussianBlur(_sc(blur))), (0, 0), m)
    crop.alpha_composite(Image.composite(Image.new("RGBA", (w, h), (*tint, ta)), _gl(w, h), m))
    edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_SS * 2 + 1)))
    crop.paste(Image.new("RGBA", (w, h), (255, 255, 255, border)), (0, 0), edge)
    img.paste(crop, (cx0, cy0))


def _gdraw_name(img, P, nm, fn, tx0, cy0=198):
    """Nama: bayangan lembut + teks gradien (navy -> ungu logo)."""
    x0, y0, x1, y1 = _sc(tx0 - 20), _sc(cy0 - 40), _sc(tx0 + 420), _sc(cy0 + 42)
    w, h = x1 - x0, y1 - y0
    lx, ly = _sc(tx0) - x0, _sc(cy0) - y0
    crop = img.crop((x0, y0, x1, y1))
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).text((lx, ly), nm, font=fn, fill=255, anchor="lm")
    m3 = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m3).text((lx, ly + _sc(3)), nm, font=fn, fill=255, anchor="lm")
    sh = _gl(w, h)
    sh.paste((*P["acc"], 75), (0, 0), m3.filter(ImageFilter.GaussianBlur(_sc(5))))
    crop.alpha_composite(sh)
    bb = m.getbbox()
    if bb:
        g = _gl(w, h)
        gd = ImageDraw.Draw(g)
        for x in range(bb[0], bb[2] + 1):
            gd.line([(x, bb[1]), (x, bb[3])],
                    fill=(*_lerp3(P["ink"], P["ink2"], (x - bb[0]) / max(1, bb[2] - bb[0])), 255))
        crop.paste(g, (0, 0), m)
    img.paste(crop, (x0, y0))


def _gframe_layer(key):
    if key in _FRAME_CACHE:
        return _FRAME_CACHE[key]
    P = _GP[key]
    w, h = W * _SS, H * _SS
    o = _grrmask(w, h, (9, 9, W - 9, H - 9), 16)
    i = _grrmask(w, h, (10.6, 10.6, W - 10.6, H - 10.6), 14.6)
    g = _ghgrad(w, h, P["acc2"], P["acc"])
    g.putalpha(ImageChops.subtract(o, i).point(lambda v: v * 150 // 255))
    o2 = _grrmask(w, h, (11.6, 11.6, W - 11.6, H - 11.6), 14)
    i2 = _grrmask(w, h, (12.6, 12.6, W - 12.6, H - 12.6), 13)
    hl = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    hl.putalpha(ImageChops.subtract(o2, i2).point(lambda v: v * 170 // 255))
    layer = Image.alpha_composite(g, hl)
    _FRAME_CACHE[key] = layer
    return layer


def _gnoise():
    if "n" not in _NOISE_CACHE:
        n = Image.effect_noise((W * _SS, H * _SS), 20).convert("L").point(lambda v: (v - 128) // 9 + 128)
        _NOISE_CACHE["n"] = Image.merge("RGB", (n, n, n))
    return _NOISE_CACHE["n"]


def _gribbon(img, P, x0=486, wd=22, y0=-6, y1=76):
    """Bookmark ribbon yang menggantung dari tepi atas."""
    w, h = img.size
    pts = [(x0, y0), (x0 + wd, y0), (x0 + wd, y1), (x0 + wd / 2, y1 - 10), (x0, y1)]
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon([(_sc(a), _sc(c)) for a, c in pts], fill=255)
    sh = _gl(w, h)
    sh.paste((*P["acc"], 120), (_sc(2), _sc(7)), m)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(5))))
    body = _gl(w, h)
    bd = ImageDraw.Draw(body)
    c0, c1 = P["acc2"], P["acc"]
    for y in range(_sc(y0), _sc(y1)):
        bd.line([(_sc(x0), y), (_sc(x0 + wd), y)], fill=(*_lerp3(c0, c1, (y - _sc(y0)) / (_sc(y1) - _sc(y0))), 255))
    img.paste(body, (0, 0), m)
    fl = _gl(w, h)
    fd = ImageDraw.Draw(fl)
    fd.rectangle([_sc(x0), 0, _sc(x0 + wd * 0.34), _sc(y1)], fill=(255, 255, 255, 70))
    fd.rectangle([_sc(x0 + wd * 0.80), 0, _sc(x0 + wd), _sc(y1)], fill=(0, 0, 40, 55))
    fl.putalpha(ImageChops.multiply(fl.getchannel("A"), m))
    img.alpha_composite(fl)
    d = ImageDraw.Draw(img)
    for y in range(8, int(y1 - 18), 6):                       # jahitan putus-putus
        d.line([(_sc(x0 + wd / 2), _sc(y)), (_sc(x0 + wd / 2), _sc(y + 3))], fill=(255, 255, 255, 190), width=_SS)
    edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_SS * 2 + 1)))
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 110)), (0, 0), edge)


def _gmedal(img, cx, cy, P):
    """Medali penghargaan 3D dengan dua pita."""
    w, h = img.size
    r = 17
    tails = _gl(w, h)
    td = ImageDraw.Draw(tails)
    for sgn, c in ((-1, P["acc2"]), (1, P["acc"])):
        if sgn > 0:
            pts = [(cx + 3, cy + 8), (cx + 13, cy + 8), (cx + 10, cy + 30), (cx + 7, cy + 25), (cx + 3, cy + 30)]
        else:
            pts = [(cx - 13, cy + 8), (cx - 3, cy + 8), (cx - 3, cy + 30), (cx - 7, cy + 25), (cx - 10, cy + 30)]
        td.polygon([(_sc(a), _sc(b)) for a, b in pts], fill=(*c, 255))
        td.polygon([(_sc(a), _sc(b)) for a, b in pts[:2] + [(pts[1][0], pts[1][1] + 8), (pts[0][0], pts[0][1] + 8)]],
                   fill=(255, 255, 255, 60))
    sh = _gl(w, h)
    ImageDraw.Draw(sh).ellipse([_sc(cx - r), _sc(cy - r + 7), _sc(cx + r), _sc(cy + r + 7)], fill=(*P["acc"], 130))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(7))))
    img.alpha_composite(tails)
    _gconic_ring(img, cx, cy, r, r - 4.2, P["stops"])
    disc = _gsphere(r - 4, *P["bsph"])
    img.alpha_composite(disc, (_sc(cx) - disc.width // 2, _sc(cy) - disc.height // 2))
    ImageDraw.Draw(img).polygon([(_sc(a), _sc(b)) for a, b in _gsparkle(cx, cy, 7.5)], fill=(255, 255, 255, 255))


def _gglass_ruler(img, cx, cy, Lr, Wr, rot, P):
    """Penggaris kaca tembus pandang lengkap dengan skala cm."""
    w, h = img.size
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([_sc(cx - Lr / 2), _sc(cy - Wr / 2), _sc(cx + Lr / 2), _sc(cy + Wr / 2)],
                                        radius=_sc(7), fill=255)
    cen = (_sc(cx), _sc(cy))
    m = m.rotate(rot, center=cen, resample=Image.BICUBIC)
    sh = _gl(w, h)
    sh.paste((*P["acc"], 80), (0, _sc(9)), m)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(8))))
    img.paste(img.filter(ImageFilter.GaussianBlur(_sc(8))), (0, 0), m)
    body = _gl(w, h)
    bd = ImageDraw.Draw(body)
    for i in range(_sc(Lr)):
        t = i / _sc(Lr)
        c = _lerp3((255, 255, 255), P["acc2"], 0.10 + 0.35 * t)
        x = _sc(cx - Lr / 2) + i
        bd.line([(x, _sc(cy - Wr)), (x, _sc(cy + Wr))], fill=(*c, int(150 - 70 * t)))
    body = body.rotate(rot, center=cen, resample=Image.BICUBIC)
    body.putalpha(ImageChops.multiply(body.getchannel("A"), m))
    img.alpha_composite(body)
    edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_SS * 2 + 1)))
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 225)), (0, 0), edge)
    sheen = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sheen).rounded_rectangle([_sc(cx - Lr / 2 + 3), _sc(cy - Wr / 2 + 2), _sc(cx + Lr / 2 - 3),
                                             _sc(cy - Wr / 2 + Wr * 0.38)], radius=_sc(5), fill=95)
    sheen = ImageChops.multiply(sheen.rotate(rot, center=cen, resample=Image.BICUBIC).filter(ImageFilter.GaussianBlur(_sc(1.5))), m)
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0), sheen)
    rp = _grot(cx, cy, rot)
    tk = _gl(w, h)
    td = ImageDraw.Draw(tk)
    n = int((Lr - 24) / 6)
    for i in range(n + 1):
        x = -Lr / 2 + 12 + i * 6
        ln = 9 if i % 5 == 0 else 5
        p0, p1 = rp((x, Wr / 2 - 2)), rp((x, Wr / 2 - 2 - ln))
        td.line([(_sc(p0[0]), _sc(p0[1])), (_sc(p1[0]), _sc(p1[1]))],
                fill=(*P["acc"], 200 if i % 5 == 0 else 140), width=_SS)
    img.alpha_composite(tk)
    f = _gsans(7.5, 700)
    for i in range(0, n + 1, 5):
        pa = rp((-Lr / 2 + 12 + i * 6, -Wr / 2 + 7))
        g = _gl(_sc(16), _sc(16))
        ImageDraw.Draw(g).text((_sc(8), _sc(8)), str(i // 5), font=f, fill=(*P["ink2"], 200), anchor="mm")
        g = g.rotate(rot, resample=Image.BICUBIC)
        img.alpha_composite(g, (_sc(pa[0]) - _sc(8), _sc(pa[1]) - _sc(8)))


def _garc_text(img, cx, cy, R, text, font, fill, track):
    """Teks melengkung di bawah avatar (seperti inskripsi pada koin)."""
    ws = [font.getlength(c) for c in text]
    tot = sum(ws) + track * _sc(1) * (len(text) - 1)
    start = -(tot / _sc(R)) / 2
    pos = 0
    sz = _sc(24)
    for c, wc in zip(text, ws):
        phi = start + (pos + wc / 2) / _sc(R)
        pos += wc + track * _sc(1)
        g = _gl(sz, sz)
        ImageDraw.Draw(g).text((sz // 2, sz // 2), c, font=font, fill=fill, anchor="mm")
        g = g.rotate(math.degrees(phi), resample=Image.BICUBIC)
        x = _sc(cx) + _sc(R) * math.sin(phi)
        y = _sc(cy) + _sc(R) * math.cos(phi)
        img.alpha_composite(g, (int(round(x)) - sz // 2, int(round(y)) - sz // 2))


_TX0 = 52                              # margin kiri kolom teks
_AV_CX, _AV_CY, _AV = 598, 172, 176    # avatar: dekat dengan teks, tidak dempet
ARC_TEXT = "·  nanZ  SERVER  BOOSTER  ·"


def _gbrand(img, x, cy, P):
    """Watermark kecil: logo nanZ + tulisan 'nanZ SERVER' di sampingnya."""
    w, h = img.size
    lg = _glogo(_sc(46))
    if lg is not None:
        lx, ly = _sc(x), _sc(cy) - lg.height // 2
        gl = _gl(w, h)
        gl.paste((*P["acc"], 110), (lx, ly + _sc(3)), lg.getchannel("A"))
        img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(_sc(4))))
        img.alpha_composite(lg, (lx, ly))
        tx = x + lg.width / _SS + 9
    else:
        tx = x
    d = ImageDraw.Draw(img)
    f1 = _gsans(23, 700)
    d.text((_sc(tx), _sc(cy - 8)), "nan", font=f1, fill=(*P["ink"], 255), anchor="lm")
    zx = tx + f1.getlength("nan") / _SS
    d.text((_sc(zx), _sc(cy - 8)), "Z", font=f1, fill=(*P["ink2"], 255), anchor="lm")
    f2 = _gsans(9.5, 700)
    cxp = tx + 1
    for ch in "SERVER":
        d.text((_sc(cxp), _sc(cy + 13)), ch, font=f2, fill=(*P["mute"], 255), anchor="lm")
        cxp += f2.getlength(ch) / _SS + 3.4
    ln = _gl(w, h)
    ld = ImageDraw.Draw(ln)
    x1 = cxp + 8
    for xx in range(_sc(x1), _sc(x1 + 46)):
        t = (xx - _sc(x1)) / _sc(46)
        ld.line([(xx, _sc(cy + 13)), (xx, _sc(cy + 13.8))], fill=(*_lerp3(P["acc2"], P["acc"], t), int(200 * (1 - t))))
    img.alpha_composite(ln)


def _gstatic_layer(key):
    """Semua elemen yang TIDAK bergantung pada user (di-cache per tier)."""
    if key in _STATIC_CACHE:
        return _STATIC_CACHE[key]
    elite = key == "elite"
    P = _GP[key]
    img = _gbackground(P)
    w, h = img.size
    cx, cy, AV = _AV_CX, _AV_CY, _AV
    _gvignette(img, P)
    _gdark_panel(img, P)
    _ghexagon(img, cx, cy, 246, P["dgrid"], 46)
    _ghexagon(img, cx, cy, 203, P["acc2"], 90, 1.0)
    _glight_sweep(img)
    _gstars(img, P)
    _gbokeh(img, P)
    _gribbon(img, P)
    _gglass_ruler(img, 394, 68, 150, 27, -8, P)
    _gglass_tile(img, 748, 52, 58, 14, P, dark=True)
    _gicon_book(img, 748, 52, 58, 14, P)
    _gglass_tile(img, 746, 150, 50, -10, P, dark=True)
    _gicon_cap(img, 746, 150, 50, -10, P)
    _gput_sphere(img, 458, 122, 5, P)
    _gput_sphere(img, 440, 196, 4, P)
    _gput_sphere(img, 300, 112, 3.5, P)
    sh = _gl(w, h)
    ImageDraw.Draw(sh).ellipse([_sc(cx - AV / 2 - 6), _sc(cy - AV / 2 + 6), _sc(cx + AV / 2 + 6), _sc(cy + AV / 2 + 22)],
                               fill=(*P["dglow"], 190))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(20))))
    ha = _gl(w, h)
    ImageDraw.Draw(ha).ellipse([_sc(cx - AV / 2 - 13), _sc(cy - AV / 2 - 13), _sc(cx + AV / 2 + 13), _sc(cy + AV / 2 + 13)],
                               fill=(255, 255, 255, 255))
    img.alpha_composite(ha)
    _gconic_ring(img, cx, cy, AV / 2 + 10, AV / 2 + 3.5, P["stops"])
    _garc_text(img, cx, cy, AV / 2 + 27, ARC_TEXT, _gsans(9, 700),
               (*P["dtxt"], 240), 2.4)
    _gput_pen(img, 752, 268, 100, 12.5, 225, P)

    tx0 = _TX0
    _gbrand(img, tx0, 44, P)
    d = ImageDraw.Draw(img)
    lab = "ELITE BOOST" if elite else "PRIME BOOST"
    fp = _gsans(13, 700)
    pw = fp.getlength(lab) / _SS + 50
    px, pcy = tx0, 104
    _gfoil_pill(img, (px, pcy - 16, px + pw, pcy + 16), P)
    d = ImageDraw.Draw(img)
    d.polygon([(_sc(a), _sc(b)) for a, b in _gsparkle(px + 22, pcy, 6.5)], fill=(255, 255, 255, 255))
    d.text((_sc(px + 37), _sc(pcy)), lab, font=fp, fill=(255, 255, 255, 255), anchor="lm")
    kt = "Terima kasih banyak," if elite else "Terima kasih,"
    d.text((_sc(tx0), _sc(156)), kt, font=_gserif(40), fill=(*P["ink2"], 255), anchor="lm")
    ul = _gl(w, h)
    u = ImageDraw.Draw(ul)
    x0, x1 = tx0 + 12, tx0 + 210
    for x in range(_sc(x0), _sc(x1)):
        t = (x - _sc(x0)) / _sc(x1 - x0)
        u.line([(x, _sc(238)), (x, _sc(238.8))], fill=(*_lerp3(P["acc"], P["acc2"], t), int(255 * (1 - t) ** 0.8)))
    dm = 6
    u.polygon([(_sc(tx0 + 3), _sc(238.4 - dm / 1.4)), (_sc(tx0 + 3 + dm / 1.4), _sc(238.4)),
               (_sc(tx0 + 3), _sc(238.4 + dm / 1.4)), (_sc(tx0 + 3 - dm / 1.4), _sc(238.4))],
              fill=(*P["acc"], 255), outline=(255, 255, 255, 255))
    img.alpha_composite(ul)
    d = ImageDraw.Draw(img)
    _gmedal(img, 326, 292, P)
    _STATIC_CACHE[key] = img
    return img


def _render_card_v2(avatar_bytes, name, tier, total, boosts):
    elite = boosts >= 2
    key = "elite" if elite else "prime"
    P = _GP[key]
    with _RENDER_LOCK:
        img = _gstatic_layer(key).copy()
        w, h = img.size
        cx, cy, AV = _AV_CX, _AV_CY, _AV
        img.alpha_composite(_gavatar(avatar_bytes, _sc(AV)), (_sc(cx - AV / 2), _sc(cy - AV / 2)))
        inner = _gl(w, h)
        ImageDraw.Draw(inner).ellipse([_sc(cx - AV / 2), _sc(cy - AV / 2), _sc(cx + AV / 2), _sc(cy + AV / 2)],
                                      outline=(255, 255, 255, 90), width=_SS)
        img.alpha_composite(inner)
        bx, by = cx + 64, cy + 68
        _gput_sphere(img, bx, by, 17, P, key="bsph")
        d = ImageDraw.Draw(img)
        if elite:
            d.text((_sc(bx), _sc(by)), "x2", font=_gsans(14, 700), fill=(255, 255, 255, 255), anchor="mm")
        else:
            d.polygon([(_sc(a), _sc(b)) for a, b in _gsparkle(bx, by, 10)], fill=(255, 255, 255, 255))
        for sx, sy, s in ((cx + 70, cy - 112, 6), (526, 92, 7)):
            d.polygon([(_sc(a), _sc(b)) for a, b in _gsparkle(sx, sy, s)], fill=(255, 255, 255, 240))

        clean = _gclean(name, _gsans(46, 700))
        fn, nm = _gfit(clean, 54, 388, 700)
        _gdraw_name(img, P, nm, fn, _TX0, 198)

        fc = _gsans(12.5, 600)
        x, cy2 = _TX0, 292
        for txt, col in ((f"Level {tier}", P["acc2"]), (f"Total {total} Boost", P["acc"])):
            cw = fc.getlength(txt) / _SS + 44
            _gpill(img, (x, cy2 - 15, x + cw, cy2 + 15), (255, 255, 255), 135, P)
            dot = _gsphere(5.5, tuple(int(c * 0.62) for c in col), tuple(min(255, int(c * 0.5 + 130)) for c in col))
            img.alpha_composite(dot, (_sc(x + 16) - dot.width // 2, _sc(cy2) - dot.height // 2))
            ImageDraw.Draw(img).text((_sc(x + 30), _sc(cy2)), txt, font=fc, fill=(*P["ink"], 255), anchor="lm")
            x += cw + 10

        img.alpha_composite(_gframe_layer(key))
        out = img.convert("RGB")
        out = Image.blend(out, ImageChops.overlay(out, _gnoise()), 0.2)
        out = out.resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_booster_card(avatar_bytes: bytes, name: str, tier: int, total: int, boosts: int = 1) -> bytes:
    """boosts == 1 -> Prime Boost; boosts >= 2 -> Elite Boost. Mengembalikan bytes PNG 800x340."""
    if np is None:
        RENDER_INFO.update(engine="legacy", error="numpy belum terpasang (pip install numpy)")
        print("[Booster] numpy belum terpasang (pip install numpy); memakai desain lama.")
        return _render_booster_card_legacy(avatar_bytes, name, tier, total, boosts)
    try:
        png = _render_card_v2(avatar_bytes, name, tier, total, boosts)
        RENDER_INFO.update(engine="v2", error=None)
        return png
    except Exception as e:
        # Jangan sampai notifikasi boost gagal: kembali ke desain lama.
        RENDER_INFO.update(engine="legacy", error=repr(e))
        print(f"[Booster] Desain baru gagal ({e!r}); memakai desain lama.")
        return _render_booster_card_legacy(avatar_bytes, name, tier, total, boosts)


# Hanya pesan boost individual, bukan pesan pencapaian tier server.
BOOST_MESSAGE_TYPES = {discord.MessageType.premium_guild_subscription}


class Booster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = self._load()
        self._lock = asyncio.Lock()
        self._ready_synced = set()
        self._pending_fallback = set()
        self._guild_sync_tasks = {}
        # Dedupe disimpan di JSON agar tetap berlaku setelah restart.
        meta = self.data.setdefault("_meta", {})
        self._processed_message_ids = set(str(x) for x in meta.get("processed_message_ids", []))

    # -------------------- STORAGE --------------------
    def _load(self):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Format JSON tidak valid")
            # Migrasi aman: format lama (guild_id -> user_id -> count) tetap dibaca.
            meta = data.setdefault("_meta", {})
            if not isinstance(meta, dict):
                data["_meta"] = {}
            data["_meta"].setdefault("processed_message_ids", [])
            data["_meta"].setdefault("benefit_roles", {})
            return data
        except FileNotFoundError:
            print(f"[Booster] {DATA_FILE} belum ada; file akan dibuat saat data disimpan.")
            return {}
        except Exception as e:
            # Jangan lanjut dengan data kosong jika file lama rusak.
            print(f"[Booster] GAGAL membaca {DATA_FILE}: {e}")
            raise

    def _save(self):
        temp = DATA_FILE + ".tmp"
        try:
            with open(temp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, DATA_FILE)
        except Exception as e:
            print(f"[Booster] GAGAL menyimpan data: {e}")
            try:
                if os.path.exists(temp):
                    os.remove(temp)
            except OSError:
                pass
            raise

    def _get(self, guild_id, user_id):
        return int(self.data.get(str(guild_id), {}).get(str(user_id), 0))

    def _set(self, guild_id, user_id, count):
        group = self.data.setdefault(str(guild_id), {})
        key = str(user_id)
        if count <= 0:
            group.pop(key, None)
        else:
            group[key] = int(count)
        self._save()

    def _benefit_roles(self, guild_id):
        meta = self.data.setdefault("_meta", {})
        roles = meta.setdefault("benefit_roles", {})
        return [int(rid) for rid in roles.setdefault(str(guild_id), [])]

    def _set_benefit_roles(self, guild_id, role_ids):
        meta = self.data.setdefault("_meta", {})
        roles = meta.setdefault("benefit_roles", {})
        roles[str(guild_id)] = sorted(set(int(rid) for rid in role_ids))
        self._save()

    # -------------------- ROLES --------------------
    async def apply_roles(self, member, count):
        guild = member.guild
        prime = guild.get_role(ROLE_PRIME_ID)
        elite = guild.get_role(ROLE_ELITE_ID)
        wanted = elite if count >= 2 else prime if count == 1 else None
        try:
            for role in (prime, elite):
                if role is None:
                    continue
                if role == wanted and role not in member.roles:
                    await member.add_roles(role, reason="nanZ Booster synchronization")
                elif role != wanted and role in member.roles:
                    await member.remove_roles(role, reason="nanZ Booster synchronization")
        except discord.Forbidden:
            print(f"[Booster] Tidak bisa mengatur role {member}; periksa Manage Roles/hierarki role.")
        except discord.HTTPException as e:
            print(f"[Booster] Gagal mengatur role: {e}")

    async def sync_benefit_roles(self, guild):
        """Benefit role hanya mengikuti status boost aktual, bukan hitungan manual."""
        role_ids = self._benefit_roles(guild.id)
        if not role_ids:
            return
        try:
            active_ids = {m.id for m in guild.premium_subscribers}
        except Exception as e:
            print(f"[Booster] Tidak bisa membaca subscriber untuk benefit role: {e}")
            return
        for role_id in role_ids:
            role = guild.get_role(role_id)
            if role is None:
                print(f"[Booster] Benefit role {role_id} tidak ditemukan di {guild.name}; konfigurasi dipertahankan.")
                continue
            # Berikan kepada booster aktif dan cabut hanya dari role benefit terdaftar.
            for member in list(role.members):
                if member.id not in active_ids:
                    try:
                        await member.remove_roles(role, reason="nanZ Booster benefit sync: no active boost")
                    except discord.Forbidden:
                        print(f"[Booster] Tidak bisa mencabut benefit role {role.name} dari {member}; cek hierarki/Manage Roles.")
                    except discord.HTTPException as e:
                        print(f"[Booster] Gagal mencabut benefit role {role.name}: {e}")
            for member_id in active_ids:
                member = guild.get_member(member_id)
                if member and role not in member.roles:
                    try:
                        await member.add_roles(role, reason="nanZ Booster benefit sync: active boost")
                    except discord.Forbidden:
                        print(f"[Booster] Tidak bisa memberi benefit role {role.name} ke {member}; cek hierarki/Manage Roles.")
                    except discord.HTTPException as e:
                        print(f"[Booster] Gagal memberi benefit role {role.name}: {e}")

    # -------------------- NOTIFICATION --------------------
    async def send_boost_embed(self, member, boosts):
        channel = member.guild.get_channel(BOOST_CHANNEL_ID)
        if channel is None:
            print(f"[Booster] Channel {BOOST_CHANNEL_ID} tidak ditemukan.")
            return

        elite = boosts >= 2
        tier = member.guild.premium_tier
        total = member.guild.premium_subscription_count or 0
        file = None

        try:
            avatar = await member.display_avatar.replace(size=256, format="png").read()
            loop = asyncio.get_running_loop()
            png = await loop.run_in_executor(
                None, render_booster_card, avatar, member.display_name, tier, total, boosts
            )
            file = discord.File(io.BytesIO(png), filename="booster.png")
        except Exception as e:
            print(f"[Booster] Gagal membuat PNG: {e}")

        if elite:
            title = "Elite Boost Baru!"
            desc = (f"{E_NITRO} Terima kasih {member.mention} sudah ngeboost **2x** di **nanZ Server**!\n"
                    f"> {E_BLUE} `Req Role:` <#{ROLE_REQ_CHANNEL_ID}>")
            color = discord.Color.from_rgb(235, 165, 30)
        else:
            title = "Prime Boost Baru!"
            desc = (f"{E_NITRO} Terima kasih {member.mention} sudah ngeboost **nanZ Server**!\n"
                    f"> {E_BLUE} `Req Role:` <#{ROLE_REQ_CHANNEL_ID}>")
            color = discord.Color.from_rgb(130, 80, 255)

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_footer(text="nanZ School Boost System")
        kwargs = {}
        if file:
            embed.set_image(url="attachment://booster.png")
            kwargs["file"] = file
        await channel.send(
            content=member.mention,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            **kwargs,
        )

    # -------------------- BOOST EVENT --------------------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.type not in BOOST_MESSAGE_TYPES:
            return
        member = message.author
        if not isinstance(member, discord.Member):
            member = message.guild.get_member(message.author.id)
        if member is None or member.bot:
            return

        # Satu pesan sistem boost = satu event. Jangan menafsirkan isi pesan
        # sebagai angka tambahan karena itu dapat menggandakan hitungan.
        async with self._lock:
            message_key = str(message.id)
            if message_key in self._processed_message_ids:
                return
            new_count = self._get(message.guild.id, member.id) + 1
            group = self.data.setdefault(str(message.guild.id), {})
            group[str(member.id)] = int(new_count)
            self._processed_message_ids.add(message_key)
            # Simpan daftar dedupe terbatas; ID terbaru tetap persisten saat restart.
            if len(self._processed_message_ids) > 10000:
                self._processed_message_ids = set(sorted(self._processed_message_ids, key=int)[-8000:])
            meta = self.data.setdefault("_meta", {})
            meta["processed_message_ids"] = sorted(self._processed_message_ids, key=int)
            self._save()

        await self.apply_roles(member, new_count)
        try:
            await self.send_boost_embed(member, new_count)
        except discord.HTTPException as e:
            print(f"[Booster] Gagal mengirim notifikasi: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.premium_since == after.premium_since:
            return

        # Semua boost member berhenti.
        if before.premium_since is not None and after.premium_since is None:
            async with self._lock:
                self._set(after.guild.id, after.id, 0)
            await self.apply_roles(after, 0)
            await self.sync_benefit_roles(after.guild)
            return

        # Fallback untuk boost baru jika pesan sistem tidak diterima.
        if before.premium_since is None and after.premium_since is not None:
            key = (after.guild.id, after.id)
            if key in self._pending_fallback:
                return
            self._pending_fallback.add(key)
            try:
                await asyncio.sleep(5)
                async with self._lock:
                    # Bila on_message sudah mencatat boost, jangan tambah lagi.
                    if self._get(after.guild.id, after.id) > 0:
                        return
                    self._set(after.guild.id, after.id, 1)
                await self.apply_roles(after, 1)
                try:
                    await self.send_boost_embed(after, 1)
                except discord.HTTPException as e:
                    print(f"[Booster] Gagal mengirim notifikasi fallback: {e}")
            finally:
                self._pending_fallback.discard(key)

    # -------------------- LOST BOOST RECONCILIATION --------------------
    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        old_total = before.premium_subscription_count or 0
        new_total = after.premium_subscription_count or 0
        if new_total >= old_total:
            return
        old_task = self._guild_sync_tasks.get(after.id)
        if old_task and not old_task.done():
            old_task.cancel()
        self._guild_sync_tasks[after.id] = asyncio.create_task(self._reconcile_later(after.id))

    async def _reconcile_later(self, guild_id):
        try:
            await asyncio.sleep(6)
        except asyncio.CancelledError:
            return
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return
        try:
            active_members = list(guild.premium_subscribers)
        except Exception as e:
            print(f"[Booster] Tidak bisa membaca booster aktif: {e}")
            return
        active = {m.id: m for m in active_members}

        async with self._lock:
            group = self.data.setdefault(str(guild_id), {})
            # Hanya hapus catatan bagi anggota yang status boost-nya dipastikan berakhir.
            for uid in list(group):
                if str(uid).isdigit() and int(uid) not in active:
                    group.pop(uid, None)
            for uid in active:
                group.setdefault(str(uid), 1)
            self._save()

        # Total server yang turun tidak mengidentifikasi pemilik boost yang hilang.
        # Jangan mengubah angka Elite secara tebakan; minta admin memeriksa bila perlu.
        actual = guild.premium_subscription_count or 0
        tracked = sum(int(v) for k, v in self.data.get(str(guild_id), {}).items()
                      if str(k).isdigit())
        if tracked != actual:
            print(f"[Booster] Rekonsiliasi {guild.name}: total boost server={actual}, jumlah tercatat={tracked}. "
                  "Tidak mengubah hitungan individual tanpa bukti yang cukup.")
        await self.sync_benefit_roles(guild)

    # -------------------- STARTUP SYNC: NO NOTIFICATIONS --------------------
    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            if guild.id in self._ready_synced:
                continue
            try:
                active_members = list(guild.premium_subscribers)
            except Exception as e:
                print(f"[Booster] Gagal membaca booster {guild.id}: {e}")
                continue
            active = {m.id: m for m in active_members}

            async with self._lock:
                group = self.data.setdefault(str(guild.id), {})
                # Hapus anggota yang sudah tidak boost.
                for uid in list(group):
                    if str(uid).isdigit() and int(uid) not in active:
                        group.pop(uid, None)
                # Pertahankan hitungan JSON yang sudah ada.
                # Booster lama yang belum tercatat diberi default 1.
                for uid in active:
                    group.setdefault(str(uid), 1)
                self._save()

            # Tidak memanggil send_boost_embed di startup.
            for uid, member in active.items():
                await self.apply_roles(member, self._get(guild.id, uid))

            # Lepas role dari member yang sudah tidak boost.
            for role_id in (ROLE_PRIME_ID, ROLE_ELITE_ID):
                role = guild.get_role(role_id)
                if role:
                    for member in list(role.members):
                        if member.id not in active:
                            await self.apply_roles(member, 0)

            await self.sync_benefit_roles(guild)
            self._ready_synced.add(guild.id)
            print(f"[Booster] Sync {guild.name} selesai; {len(active)} booster aktif; tanpa notifikasi.")

    # -------------------- ADMIN COMMANDS --------------------
    @commands.command(name="boost_set")
    @commands.has_permissions(administrator=True)
    async def boost_set(self, ctx, member: discord.Member, jumlah: int):
        """Atur manual: !boost_set @member 0|1|2. 2 berarti 2 atau lebih."""
        if jumlah not in (0, 1, 2):
            await ctx.send("Jumlah harus 0, 1, atau 2 (2 berarti dua atau lebih).",
                           allowed_mentions=discord.AllowedMentions.none())
            return
        async with self._lock:
            self._set(ctx.guild.id, member.id, jumlah)
        await self.apply_roles(member, jumlah)
        await ctx.send(f"Jumlah boost {member.mention} diatur menjadi **{jumlah}**.",
                       allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name="boost_reqrole")
    @commands.has_permissions(administrator=True)
    async def boost_reqrole(self, ctx, role: discord.Role):
        """Toggle role benefit booster: !boost_reqrole @Role"""
        if ctx.guild is None:
            return
        if role.is_default() or role.managed:
            await ctx.send("Role itu tidak bisa digunakan sebagai role benefit.",
                           allowed_mentions=discord.AllowedMentions.none())
            return
        if role.id in (ROLE_PRIME_ID, ROLE_ELITE_ID):
            await ctx.send("Prime Boost dan Elite Boost dikelola otomatis; pilih role benefit lain.",
                           allowed_mentions=discord.AllowedMentions.none())
            return
        bot_member = ctx.guild.me
        if bot_member is None or not bot_member.guild_permissions.manage_roles:
            await ctx.send("Bot memerlukan izin **Manage Roles**.",
                           allowed_mentions=discord.AllowedMentions.none())
            return
        if role >= bot_member.top_role:
            await ctx.send("Posisikan role bot di atas role benefit tersebut terlebih dahulu.",
                           allowed_mentions=discord.AllowedMentions.none())
            return

        role_ids = self._benefit_roles(ctx.guild.id)
        if role.id in role_ids:
            role_ids.remove(role.id)
            async with self._lock:
                self._set_benefit_roles(ctx.guild.id, role_ids)
            await ctx.send(f"Role {role.mention} **dihapus dari daftar benefit**. Sistem Booster tidak akan lagi mengelola role ini.",
                           allowed_mentions=discord.AllowedMentions.none())
            return

        role_ids.append(role.id)
        try:
            async with self._lock:
                self._set_benefit_roles(ctx.guild.id, role_ids)
        except Exception:
            await ctx.send("Gagal menyimpan konfigurasi. Role tidak diaktifkan; periksa izin file dan log bot.",
                           allowed_mentions=discord.AllowedMentions.none())
            return
        await self.sync_benefit_roles(ctx.guild)
        await ctx.send(f"Role {role.mention} **terdaftar sebagai benefit booster** dan konfigurasi disimpan.",
                       allowed_mentions=discord.AllowedMentions.none())

    @boost_set.error
    @boost_reqrole.error
    async def booster_admin_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Command ini hanya untuk administrator/staf berizin.",
                           allowed_mentions=discord.AllowedMentions.none())
        elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            await ctx.send("Format command tidak valid. Contoh: `!boost_set @Murid 1` atau `!boost_reqrole @Role`.",
                           allowed_mentions=discord.AllowedMentions.none())
        else:
            print(f"[Booster] Error command: {error}")
            await ctx.send("Terjadi kesalahan saat menjalankan command. Periksa log bot.",
                           allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name="test_boost")
    @commands.has_permissions(administrator=True)
    async def test_boost(self, ctx, jumlah: int = 1, member: discord.Member = None):
        """Tes notifikasi tanpa mengubah data/role: !test_boost 1 atau !test_boost 2 @member"""
        if jumlah not in (1, 2):
            await ctx.send("Gunakan `!test_boost 1` atau `!test_boost 2`.",
                           allowed_mentions=discord.AllowedMentions.none())
            return
        try:
            await self.send_boost_embed(member or ctx.author, jumlah)
            if RENDER_INFO["engine"] == "v2":
                info = "Renderer: **desain baru (v2)** ✅"
            elif RENDER_INFO["engine"] == "legacy":
                info = f"Renderer: **desain LAMA** ⚠️ Alasan: `{str(RENDER_INFO['error'])[:300]}`"
            else:
                info = "Renderer: belum berjalan (kartu gagal dibuat, cek log bot)."
            await ctx.send(f"Tes notifikasi boost selesai.\n{info}",
                           allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException as e:
            await ctx.send(f"Tes notifikasi gagal: {e}",
                           allowed_mentions=discord.AllowedMentions.none())


async def setup(bot):
    await bot.add_cog(Booster(bot))