from __future__ import annotations

import asyncio
import io
import json
import math
import random
import re
import threading
import time
import unicodedata
from functools import lru_cache

import discord
from discord.ext import commands
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


# ============================================================
# CONFIG KARTU
# ============================================================

FONT_SANS = "fonts/Inter.ttf"                      # Inter (variable font, OFL)
FONT_SERIF = "fonts/InstrumentSerif-Italic.ttf"    # Instrument Serif Italic (OFL)
LOGO_PATHS = ("assets/nanz_logo.png", "nanz_logo.png", "fonts/nanz_logo.png")
_FALLBACKS = ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf")
FONT_BOLD = _FALLBACKS[0]   # dipakai _gsans bila Inter tidak ditemukan

W, H = 800, 340
_SS = 2                      # supersampling (render 2x lalu diperkecil)
_RENDER_LOCK = threading.Lock()
_STATIC_CACHE: dict = {}     # layer statis (tidak bergantung pada user)
_FRAME_CACHE: dict = {}
_NOISE_CACHE: dict = {}

# Palet biru/ungu diambil dari logo nanZ.
_GP = {
    "prime": dict(
        base=(250, 251, 255),
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
        dk0=(8, 6, 34), dk1=(36, 20, 100), dglow=(124, 104, 255), dsh=(30, 20, 110),
        dtxt=(232, 228, 255), dgrid=(190, 180, 255), dgk=1.0,
    ),
}
P = _GP["prime"]


# ============================================================
# CARD RENDERER — helper generik (gaya sama dengan kartu booster)
# ============================================================

def _sc(v):
    return int(round(v * _SS))


def _gl(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def _lerp3(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


@lru_cache(maxsize=96)
def _gsans(size, wght=500, k=None):
    px = int(round(size * (k or _SS)))
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
    print("[VerifyGreeting] Logo nanZ tidak ditemukan; kartu dibuat tanpa logo. Cek LOGO_PATHS.")
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
    return clean or "Murid Baru"


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


def _gbrand_chip(img, x, y, P, u=1.0):
    """Watermark: chip kaca terang (logo nanZ + lockup "nanZ / SERVER"), sama untuk semua kartu nanZ.
    x, y = pojok kiri-atas chip. u = faktor skala (1.0 = kanvas 800x340).
    Dirender 4x pada canvas kecil lalu di-downscale supaya tepi dan teks kecil tetap tajam.
    Baris SERVER di-justify selaras lebar "nanZ" -> lockup rapi, rata kiri-kanan."""
    S, pad = 4, round(18 * u)
    h = 38 * u
    R = lambda v: int(round(v * S))
    logo = _glogo_raw()
    lh = 26 * u
    lw = round(logo.width * lh / logo.height) if logo is not None else 0
    f1, f2 = _gsans(18 * u, 700, S), _gsans(6.5 * u, 700, S)
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
    cv = _gl(W2, H2)

    # bayangan lembut + lip 3D tipis di bawah chip
    sh = _gl(W2, H2)
    sh.paste((*P["dsh"], 210), (0, R(5 * u)), m)
    cv.alpha_composite(sh.filter(ImageFilter.GaussianBlur(R(5 * u))))
    lip = _gl(W2, H2)
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
        gd.line([(xx, 0), (xx, H2)], fill=(*_lerp3(P["acc2"], P["acc"], xx / W2), 255))
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

    small = cv.resize((round((cw + 2 * pad) * _SS), round((h + 2 * pad) * _SS)), Image.LANCZOS)
    img.alpha_composite(small, (_sc(x - pad), _sc(y - pad)))


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





# ============================================================
# CARD RENDERER — layout greeting (gaya ID card murid)
# ============================================================

TX0 = 52
CARD = (507, 18, 727, 322)           # kartu ID utama
CARD_R = 30
AV_CX, AV_CY, AV = 618, 138, 152     # avatar di kartu ID

FAMILY_TEXT = "Di sini semua member dianggap keluarga, yuk ngobrol & ikut event bareng!"
STEPS = [
    ("Verifikasi", "Selesai, kamu resmi jadi Murid nanZ."),
    ("Baca Rules", "Pahami aturan server di channel rules."),
    ("Pilih Role", "Ambil role sesuai minatmu di channel roles."),
]


def _tracked(d, x, y, text, font, fill, track):
    for ch in text:
        d.text((_sc(x), _sc(y)), ch, font=font, fill=fill, anchor="lm")
        x += font.getlength(ch) / _SS + track
    return x


def _soft_glow(img, cx, cy, r, col, a, mask=None):
    w, h = img.size
    gm = Image.new("L", (w, h), 0)
    ImageDraw.Draw(gm).ellipse([_sc(cx - r), _sc(cy - r), _sc(cx + r), _sc(cy + r)], fill=a)
    gm = gm.filter(ImageFilter.GaussianBlur(_sc(r * 0.42)))
    if mask is not None:
        gm = ImageChops.multiply(gm, mask)
    img.paste(Image.new("RGBA", (w, h), (*col, 255)), (0, 0), gm)


def _background():
    w, h = W * _SS, H * _SS
    img = Image.new("RGBA", (w, h), (247, 247, 254, 255))
    _soft_glow(img, -10, H + 40, 190, (60, 150, 255), 150)
    _soft_glow(img, 230, H + 70, 150, (90, 215, 255), 120)
    _soft_glow(img, W + 10, -20, 210, (170, 95, 240), 150)
    _soft_glow(img, 520, -40, 120, (196, 176, 255), 70)
    ov = _gl(w, h)
    d = ImageDraw.Draw(ov)
    for y in range(30, H - 14, 22):
        for x in range(34, 470, 2):
            a = int(26 * max(0, 1 - (x - 34) / 436) ** 1.3)
            if a > 0:
                d.line([(_sc(x), _sc(y)), (_sc(x + 2), _sc(y))], fill=(*P["rule"], a), width=_SS)
    d.line([(_sc(40), _sc(12)), (_sc(40), _sc(H - 12))], fill=(240, 120, 200, 40), width=_SS)
    return Image.alpha_composite(img, ov)


def _frame_layer(key="prime"):
    if key in _FRAME_CACHE:
        return _FRAME_CACHE[key]
    w, h = W * _SS, H * _SS
    o = _grrmask(w, h, (8, 8, W - 8, H - 8), 16)
    i = _grrmask(w, h, (9.4, 9.4, W - 9.4, H - 9.4), 14.6)
    g = _ghgrad(w, h, P["acc2"], P["acc"])
    g.putalpha(ImageChops.subtract(o, i).point(lambda v: v * 95 // 255))
    _FRAME_CACHE[key] = g
    return g


def _lanyard_and_card(img):
    w, h = img.size
    x0, y0, x1, y1 = CARD
    m = _grrmask(w, h, CARD, CARD_R)

    # strap di belakang kartu
    sx0, sx1 = 602, 626
    st = _gl(w, h)
    sd = ImageDraw.Draw(st)
    for yy in range(_sc(-4), _sc(34)):
        t = (yy - _sc(-4)) / _sc(38)
        sd.line([(_sc(sx0), yy), (_sc(sx1), yy)], fill=(*_lerp3((70, 160, 252), (112, 120, 246), t), 255))
    sd.rectangle([_sc(sx0), _sc(-4), _sc(sx0 + 6), _sc(34)], fill=(255, 255, 255, 70))
    sd.rectangle([_sc(sx1 - 5), _sc(-4), _sc(sx1), _sc(34)], fill=(20, 20, 120, 60))

    # bayangan kartu
    sh = _gl(w, h)
    sh.paste((70, 40, 170, 150), (0, _sc(14)), m)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(16))))
    img.alpha_composite(st)

    # bingkai kaca tipis
    mo = _grrmask(w, h, (x0 - 2.4, y0 - 2.4, x1 + 2.4, y1 + 2.4), CARD_R + 2.4)
    bd = _ghgrad(w, h, (96, 190, 255), (170, 120, 248))
    bd.putalpha(mo.point(lambda v: v * 235 // 255))
    img.alpha_composite(bd)

    # badan kartu: gradien biru-ungu ke indigo gelap
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    top, mid, bot = np.array((50, 56, 186)), np.array((76, 44, 174)), np.array((20, 10, 68))
    col = np.where(yy < 0.5, top + (mid - top) * (yy / 0.5), mid + (bot - mid) * ((yy - 0.5) / 0.5))
    arr = np.dstack([np.broadcast_to(col[:, i][:, None], (h, w)) for i in range(3)] + [np.full((h, w), 255)])
    body = Image.fromarray(arr.astype(np.uint8), "RGBA")
    _soft_glow(body, 617, 130, 120, (150, 110, 255), 170)
    _soft_glow(body, 700, 50, 80, (70, 150, 255), 110)
    _soft_glow(body, 600, 330, 140, (120, 70, 230), 120)
    dots = _gl(w, h)
    dd = ImageDraw.Draw(dots)
    for py in range(int(y0) + 6, int(y1), 14):
        for px in range(int(x0) + 6, int(x1), 14):
            dd.ellipse([_sc(px - 0.8), _sc(py - 0.8), _sc(px + 0.8), _sc(py + 0.8)], fill=(*P["dgrid"], 44))
    body.alpha_composite(dots)
    img.paste(body, (0, 0), m)

    # kilau atas + rim
    sheen = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sheen).ellipse([_sc(x0 - 40), _sc(y0 - 120), _sc(x1 + 10), _sc(y0 + 60)], fill=46)
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0),
              ImageChops.multiply(sheen.filter(ImageFilter.GaussianBlur(_sc(12))), m))
    edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_SS * 2 + 1)))
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 120)), (0, 0), edge)

    # klip lanyard
    cl = _gl(w, h)
    cd = ImageDraw.Draw(cl)
    cd.rounded_rectangle([_sc(599), _sc(27), _sc(629), _sc(41)], radius=_sc(6), fill=(0, 0, 40, 90))
    img.alpha_composite(cl.filter(ImageFilter.GaussianBlur(_sc(3))))
    cm = Image.new("L", (w, h), 0)
    ImageDraw.Draw(cm).rounded_rectangle([_sc(599), _sc(25), _sc(629), _sc(39)], radius=_sc(6), fill=255)
    gcl = Image.composite(Image.new("RGBA", (w, h), (186, 192, 226, 255)),
                          Image.new("RGBA", (w, h), (242, 244, 252, 255)),
                          Image.linear_gradient("L").resize((w, h)))
    img.paste(gcl, (0, 0), cm)
    ImageDraw.Draw(img).rounded_rectangle([_sc(607), _sc(29.5), _sc(621), _sc(34.5)], radius=_sc(2.5),
                                          fill=(52, 44, 140, 255))



P["msph"] = ((16, 138, 200), (140, 240, 228))      # bola mint-biru = status "berhasil"
MINT = (40, 196, 190)


def _gicon_chat(img, cx, cy, size, rot, P):
    """Ikon bubble chat (untuk tombol Sapa Murid Baru)."""
    w, h = img.size
    bw, bh = size * 1.05, size * 0.74
    ic = _gl(w, h)
    d = ImageDraw.Draw(ic)
    c0, c1 = P["acc2"], P["acc"]
    m = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(m)
    md.rounded_rectangle([_sc(cx - bw / 2), _sc(cy - bh / 2), _sc(cx + bw / 2), _sc(cy + bh / 2)], radius=_sc(bh * 0.3), fill=255)
    md.polygon([(_sc(cx - bw * 0.30), _sc(cy + bh / 2 - 1)), (_sc(cx - bw * 0.42), _sc(cy + bh / 2 + bh * 0.42)),
                (_sc(cx - bw * 0.04), _sc(cy + bh / 2 - 1))], fill=255)
    ic.paste(_ghgrad(w, h, c0, c1), (0, 0), m)
    d.rounded_rectangle([_sc(cx - bw / 2 + 2), _sc(cy - bh / 2 + 1.5), _sc(cx + bw / 2 - 2), _sc(cy - 1)],
                        radius=_sc(bh * 0.25), fill=(255, 255, 255, 46))
    for k in (-0.26, 0.0, 0.26):
        x = cx + k * bw
        d.ellipse([_sc(x - 2.4), _sc(cy - 2.4), _sc(x + 2.4), _sc(cy + 2.4)], fill=(255, 255, 255, 250))
    ic = ic.rotate(rot, center=(_sc(cx), _sc(cy)), resample=Image.BICUBIC)
    sh = _gl(w, h)
    sh.paste((*P["acc"], 90), (0, _sc(5)), ic.getchannel("A"))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(5))))
    img.alpha_composite(ic)


def _check(d, cx, cy, s, fill=(255, 255, 255, 255), width=2.4):
    d.line([(_sc(cx - s * 0.55), _sc(cy + s * 0.02)), (_sc(cx - s * 0.12), _sc(cy + s * 0.46)),
            (_sc(cx + s * 0.62), _sc(cy - s * 0.42))], fill=fill, width=_sc(width), joint="curve")


def _confetti(img, seed=5):
    w, h = img.size
    rng = random.Random(seed)
    cols = [(60, 150, 255), (170, 95, 240), (90, 215, 255), (250, 130, 200), (255, 196, 90), (120, 100, 250)]
    l = _gl(w, h)
    for _ in range(120):
        x = rng.uniform(440, W - 6)
        y = rng.uniform(10, H - 10)
        if CARD[0] - 6 < x < CARD[2] + 6 and CARD[1] - 6 < y < CARD[3] + 6:
            continue
        if x < 470 and y > 70:
            continue
        c = rng.choice(cols)
        a = rng.randint(150, 235)
        if rng.random() < 0.35:
            r = rng.uniform(1.4, 2.4)
            ImageDraw.Draw(l).ellipse([_sc(x - r), _sc(y - r), _sc(x + r), _sc(y + r)], fill=(*c, a))
        else:
            pc = Image.new("RGBA", (_sc(12), _sc(12)), (0, 0, 0, 0))
            ImageDraw.Draw(pc).rounded_rectangle([_sc(4.2), _sc(2), _sc(7.8), _sc(10)], radius=_sc(1), fill=(*c, a))
            pc = pc.rotate(rng.uniform(0, 180), resample=Image.BICUBIC)
            l.alpha_composite(pc, (_sc(x) - _sc(6), _sc(y) - _sc(6)))
    img.alpha_composite(l)


def _draw_resmi_pill(img):
    w, h = img.size
    box = (550, 229, 684, 257)
    m = _grrmask(w, h, box, 14)
    sh = _gl(w, h)
    sh.paste((30, 20, 140, 130), (0, _sc(5)), m)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(6))))
    img.paste(_ghgrad(w, h, (40, 176, 214), (150, 124, 248)), (0, 0), m)
    gl = Image.new("L", (w, h), 0)
    ImageDraw.Draw(gl).rounded_rectangle([_sc(box[0] + 2), _sc(box[1] + 1.5), _sc(box[2] - 2), _sc(243)], radius=_sc(8), fill=80)
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0),
              ImageChops.multiply(gl.filter(ImageFilter.GaussianBlur(1)), m))
    edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_SS * 3 + 1)))
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 235)), (0, 0), edge)
    d = ImageDraw.Draw(img)
    _check(d, 569, 243, 11, width=2.2)
    _tracked(d, 583, 243, "MURID RESMI", _gsans(12, 700), (255, 255, 255, 255), 0.6)


def _draw_access_strip(img):
    """Strip kaca di bawah kartu: akses channel terbuka."""
    w, h = img.size
    box = (536, 273, 698, 303)
    m = _grrmask(w, h, box, 15)
    img.alpha_composite(Image.composite(Image.new("RGBA", (w, h), (255, 255, 255, 30)), _gl(w, h), m))
    edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_SS * 2 + 1)))
    img.paste(Image.new("RGBA", (w, h), (170, 200, 255, 120)), (0, 0), edge)
    d = ImageDraw.Draw(img)
    cx, cy = 553, 288
    for dx in (-2.2, 2.2):                       # simbol '#'
        d.line([(_sc(cx + dx - 1), _sc(cy - 5.5)), (_sc(cx + dx - 2), _sc(cy + 5.5))], fill=(140, 232, 240, 255), width=_sc(1.4))
    for dy in (-2.2, 2.2):
        d.line([(_sc(cx - 5.5), _sc(cy + dy)), (_sc(cx + 5.5), _sc(cy + dy))], fill=(140, 232, 240, 255), width=_sc(1.4))
    lab = "AKSES SEMUA CHANNEL"
    sz = 8.5
    while sz > 6:
        f = _gsans(sz, 700)
        if sum(f.getlength(c) / _SS + 0.7 for c in lab) <= 122:
            break
        sz -= 0.25
    _tracked(d, 566, 288, lab, f, (*P["dtxt"], 240), 0.7)


def _back_card(img):
    w, h = img.size
    cx, cy, bw, bh, rot = 780, 176, 150, 262, -5
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([_sc(cx - bw / 2), _sc(cy - bh / 2), _sc(cx + bw / 2), _sc(cy + bh / 2)],
                                        radius=_sc(26), fill=255)
    m = m.rotate(rot, center=(_sc(cx), _sc(cy)), resample=Image.BICUBIC)
    sh = _gl(w, h)
    sh.paste((120, 80, 220, 110), (0, _sc(10)), m)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(12))))
    gr = Image.linear_gradient("L").resize((w, h)).rotate(60, resample=Image.BICUBIC)
    body = Image.composite(Image.new("RGBA", (w, h), (214, 204, 250, 235)),
                           Image.new("RGBA", (w, h), (248, 245, 255, 235)), gr)
    img.paste(body, (0, 0), m)
    edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_SS * 2 + 1)))
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 230)), (0, 0), edge)
    _gicon_chat(img, 752, 98, 46, 8, P)


def _static_layer():
    """Semua elemen yang TIDAK bergantung pada user (di-cache)."""
    if "prime" in _STATIC_CACHE:
        return _STATIC_CACHE["prime"]
    img = _background()
    w, h = img.size

    # watermark: chip kaca di pojok kiri atas (sama dengan kartu entrance)
    _gbrand_chip(img, 18, 18, P)

    d = ImageDraw.Draw(img)
    d.text((_sc(TX0), _sc(104)), "Selamat datang,", font=_gserif(36), fill=(*P["ink2"], 255), anchor="lm")

    # garis aksen + diamond
    ul = _gl(w, h)
    u = ImageDraw.Draw(ul)
    x0, x1 = TX0 + 8, TX0 + 224
    for x in range(_sc(x0), _sc(x1)):
        t = (x - _sc(x0)) / _sc(x1 - x0)
        u.line([(x, _sc(185)), (x, _sc(185.9))], fill=(*_lerp3(P["acc"], P["acc2"], t), int(255 * (1 - t) ** 0.9)))
    dm = 6
    u.polygon([(_sc(TX0 + 3), _sc(185.4 - dm / 1.4)), (_sc(TX0 + 3 + dm / 1.4), _sc(185.4)),
               (_sc(TX0 + 3), _sc(185.4 + dm / 1.4)), (_sc(TX0 + 3 - dm / 1.4), _sc(185.4))],
              fill=(*P["acc"], 255), outline=(255, 255, 255, 255))
    img.alpha_composite(ul)

    # pesan keluarga
    d = ImageDraw.Draw(img)
    sz = 12.0
    while sz > 9:
        fc = _gsans(sz, 500)
        if fc.getlength(FAMILY_TEXT) <= _sc(392):
            break
        sz -= 0.25
    d.text((_sc(TX0), _sc(205)), FAMILY_TEXT, font=fc, fill=(64, 66, 112, 255), anchor="lm")

    # checklist onboarding (3 baris)
    ys = (240, 272, 304)
    ln = _gl(w, h)
    ld = ImageDraw.Draw(ln)
    for yy in range(_sc(ys[0] + 13), _sc(ys[1] - 13)):             # segmen selesai: garis solid
        t = (yy - _sc(ys[0] + 13)) / _sc(ys[1] - ys[0] - 26)
        ld.line([(_sc(66) - _SS, yy), (_sc(66) + _SS, yy)], fill=(*_lerp3(MINT, P["acc"], t), 235))
    yy = ys[1] + 15                                                 # segmen berikutnya: titik-titik
    while yy < ys[2] - 13:
        ld.ellipse([_sc(66 - 1), _sc(yy - 1), _sc(66 + 1), _sc(yy + 1)], fill=(*P["acc"], 150))
        yy += 5
    img.alpha_composite(ln)
    for i, (title, desc) in enumerate(STEPS):
        cy = ys[i]
        _gput_sphere(img, 66, cy, 11, P, key="msph" if i == 0 else "bsph")
        d = ImageDraw.Draw(img)
        if i == 0:
            _check(d, 66, cy, 10, width=2.2)
        else:
            d.text((_sc(66), _sc(cy)), str(i + 1), font=_gsans(12, 700), fill=(255, 255, 255, 255), anchor="mm")
        d.text((_sc(92), _sc(cy)), title, font=_gsans(13.5, 700), fill=(*P["ink"], 255), anchor="lm")
        d.text((_sc(184), _sc(cy)), desc, font=_gsans(11.5, 500), fill=(64, 66, 112, 255), anchor="lm")

    # ornamen mengambang + confetti perayaan
    _gglass_tile(img, 491, 76, 40, -12, P)
    _gicon_book(img, 491, 76, 40, -12, P)
    _gput_sphere(img, 462, 20, 3.4, P)
    _gput_sphere(img, 470, 213, 3.2, P)
    _gput_sphere(img, 771, 291, 4.6, P)
    _back_card(img)
    _confetti(img)
    _lanyard_and_card(img)

    sh = _gl(w, h)
    ImageDraw.Draw(sh).ellipse([_sc(AV_CX - AV / 2 - 4), _sc(AV_CY - AV / 2 + 6),
                                _sc(AV_CX + AV / 2 + 4), _sc(AV_CY + AV / 2 + 20)], fill=(*P["dglow"], 170))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(18))))
    ha = _gl(w, h)
    ImageDraw.Draw(ha).ellipse([_sc(AV_CX - AV / 2 - 12), _sc(AV_CY - AV / 2 - 12),
                                _sc(AV_CX + AV / 2 + 12), _sc(AV_CY + AV / 2 + 12)], fill=(255, 255, 255, 40))
    img.alpha_composite(ha)
    _gconic_ring(img, AV_CX, AV_CY, AV / 2 + 7, AV / 2 + 2, P["stops"])

    _draw_resmi_pill(img)
    _draw_access_strip(img)
    _STATIC_CACHE["prime"] = img
    return img


def _render_card(avatar_bytes: bytes, name: str) -> bytes:
    with _RENDER_LOCK:
        img = _static_layer().copy()
        w, h = img.size
        img.alpha_composite(_gavatar(avatar_bytes, _sc(AV)), (_sc(AV_CX - AV / 2), _sc(AV_CY - AV / 2)))
        inner = _gl(w, h)
        ImageDraw.Draw(inner).ellipse([_sc(AV_CX - AV / 2), _sc(AV_CY - AV / 2),
                                       _sc(AV_CX + AV / 2), _sc(AV_CY + AV / 2)],
                                      outline=(255, 255, 255, 90), width=_SS)
        img.alpha_composite(inner)
        bx, by = AV_CX + 47, AV_CY + 47
        _gput_sphere(img, bx, by, 14, P, key="msph")
        d = ImageDraw.Draw(img)
        _check(d, bx, by, 14, width=2.6)
        for sx, sy, s in ((AV_CX + 80, AV_CY - 62, 5.5), (AV_CX + 70, AV_CY + 70, 4)):
            d.polygon([(_sc(a), _sc(b)) for a, b in _gsparkle(sx, sy, s)], fill=(255, 255, 255, 235))

        clean = _gclean(name, _gsans(46, 700))
        fn, nm = _gfit(clean, 50, 380, 700)
        _gdraw_name(img, P, nm, fn, TX0, 153)

        img.alpha_composite(_frame_layer())
        out = img.convert("RGB")
        out = Image.blend(out, ImageChops.overlay(out, _gnoise()), 0.12)
        out = out.resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def generate_welcome_card(avatar_bytes: bytes, name: str) -> bytes:
    """Render kartu welcome PNG (800x340). Panggil di executor thread."""
    if np is None:
        raise RuntimeError("numpy belum terpasang (pip install numpy)")
    return _render_card(avatar_bytes, name)



# ══════════════════════════════════════════════
#  RANDOM WELCOME STICKERS
# ══════════════════════════════════════════════
WELCOME_STICKERS = [
    749054660769218631,   # Wave
    819128604311027752,
    749044136589393960,
    816086581509095424,
    816087792291282944,
    781291131828699156,
    754108890559283200,
    783787234091466793,
]


# ══════════════════════════════════════════════
#  WAVE BUTTON
# ══════════════════════════════════════════════
class WaveView(discord.ui.View):

    def __init__(self, member: discord.Member):
        super().__init__(timeout=None)
        self.member = member
        self.cooldowns = {}          # user_id -> waktu terakhir klik

    @discord.ui.button(label="Sapa Murid Baru!", emoji="👋", style=discord.ButtonStyle.secondary)
    async def wave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # ── cooldown ──
            user_id = interaction.user.id
            now = time.time()
            cooldown_time = 10

            last_used = self.cooldowns.get(user_id)
            if last_used and now - last_used < cooldown_time:
                remaining = int(cooldown_time - (now - last_used))
                return await interaction.response.send_message(
                    f"⏳ Tunggu {remaining} detik sebelum wave lagi!", ephemeral=True
                )
            self.cooldowns[user_id] = now

            sticker = discord.Object(id=random.choice(WELCOME_STICKERS))
            m, u = self.member.mention, interaction.user.mention

            messages = [
                f"👋 Welcome {m} dari {u}!",
                f"✨ Selamat datang {m} di nanZ Server dari {u}!",
                f"🎉 Welcome aboard {m}! Dari {u}",
                f"🌸 Haii {m}, selamat bergabung yaa! - {u}",
                f"🫶 {u} mengucapkan welcome untuk {m}!",
                f"💫 Welcome to nanZ {m}! Dari {u}",
                f"🤍 Senang kamu join di sini {m}! - {u}",
                f"🎀 Welcomee {m} semoga betah yaa! Dari {u}",
                f"🌟 {u} ikut menyambut {m} ke nanZ Server!",
                f"🥳 Selamat datang {m}! Welcome dari {u} 💖",
            ]

            await interaction.channel.send(content=random.choice(messages), stickers=[sticker])
            await interaction.response.defer()

        except Exception as e:
            print("Sticker error:", e)
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Gagal mengirim sticker", ephemeral=True)


# ══════════════════════════════════════════════
#  WELCOME COG
# ══════════════════════════════════════════════
class Welcome(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        with open("config.json") as f:
            self.config = json.load(f)

        # ROLE MEMBER
        self.MEMBER_ROLE_ID = 1453095603008442510

        # CHANNEL untuk tag di panel
        self.RULES_CHANNEL_ID = 1406557882811682888
        self.ROLES_CHANNEL_ID = 1510477047724773509

    # ── auto welcome saat role member masuk ──
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if not self.config.get("welcome_channel"):
            return

        before_roles = {r.id for r in before.roles}
        after_roles = {r.id for r in after.roles}

        if self.MEMBER_ROLE_ID not in before_roles and self.MEMBER_ROLE_ID in after_roles:
            await self.send_welcome(after)

    # ── test command ──
    @commands.command(name="testwelcome")
    async def test_welcome(self, ctx, member: discord.Member = None):
        await self.send_welcome(member or ctx.author)

    # ── kirim welcome ──
    async def send_welcome(self, member: discord.Member):
        channel_id = self.config.get("welcome_channel")
        if not channel_id:
            print("Config welcome_channel tidak ditemukan!")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            print(f"Channel dengan ID {channel_id} tidak ditemukan!")
            return

        mentions = discord.AllowedMentions(users=True)

        # ── Sapaan + arahan + kartu PNG (satu pesan, tanpa panel) ──
        card_file = None
        try:
            avatar_bytes = await member.display_avatar.replace(size=256, format="png").read()
            loop = asyncio.get_running_loop()
            png_bytes = await loop.run_in_executor(None, generate_welcome_card, avatar_bytes, member.display_name)
            card_file = discord.File(io.BytesIO(png_bytes), filename="welcome.png")
        except Exception as e:
            print(f"[Welcome] gagal bikin kartu PNG: {e}")

        content = (
            "<:done:1553690488257908837> **Verifikasi berhasil!**\n"
            f"Selamat datang di **nanZ Server**, {member.mention}!\n"
            f"<a:blue:1512787254312042496> `Baca rules:` [KLIK INI](https://discord.com/channels/1406557880475320340/1406557882811682888)\n"
            f"<a:purple:1512787191234035803> `Pilih role:` [KLIK INI](https://discord.com/channels/1406557880475320340/1510477047724773509)"
        )

        kwargs = {"file": card_file} if card_file else {}
        await channel.send(
            content=content,
            view=WaveView(member),
            allowed_mentions=mentions,
            **kwargs,
        )


# ══════════════════════════════════════════════
#  SETUP
# ══════════════════════════════════════════════
async def setup(bot):
    await bot.add_cog(Welcome(bot))