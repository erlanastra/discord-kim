"""donor_card.py
Generator PNG "Top 3 Donatur" (layout panggung podium) untuk nanZ Bot.

Gaya sama dengan kartu greeting/welcome/booster (kaca, 3D, palet biru-ungu dari logo nanZ,
watermark logo nanZ di kiri atas) dengan layout berbeda: header terang + panggung gelap
berisi podium emas/perak/perunggu, mahkota untuk juara 1, sorot cahaya, dan koin.

File yang dibutuhkan (sama seperti greeting/welcome/booster):
    fonts/Inter.ttf
    fonts/InstrumentSerif-Italic.ttf
    assets/nanz_logo.png   (atau nanz_logo.png / fonts/nanz_logo.png)
Paket: pillow, numpy  (pip install pillow numpy)

Pemakaian (tidak berubah):
    png_bytes = render_top_donor_card(
        kind="rupiah",              # "rupiah" atau "owo"
        rows=[{"name": "...", "amount": "Rp450.000", "value": 450000, "avatar": bytes|None}, ...],  # max 3, urut 1..3
        total_value=1245000,        # total semua donasi (buat hitung persen)
        total_text="Total Rp1.245.000",
    )
"""

from __future__ import annotations

import io
import math
import random
import re
import threading
import unicodedata
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

FONT_SANS = "fonts/Inter.ttf"                      # Inter (variable font, OFL)
FONT_SERIF = "fonts/InstrumentSerif-Italic.ttf"    # Instrument Serif Italic (OFL)
LOGO_PATHS = ("assets/nanz_logo.png", "nanz_logo.png", "fonts/nanz_logo.png")
_FALLBACKS = ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf")
FONT_BOLD = _FALLBACKS[0]

_SS = 2                      # supersampling (render 2x lalu diperkecil)
_RENDER_LOCK = threading.Lock()
_STATIC_CACHE: dict = {}
_FRAME_CACHE: dict = {}
_NOISE_CACHE: dict = {}


# ============================================================
# HELPER GAMBAR (gaya sama dengan kartu booster/greeting)
# ============================================================

def _sc(v):
    return int(round(v * _SS))


def _gl(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def _lerp3(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


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
    return clean or "Donatur"


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


def _gnoise():
    if "n" not in _NOISE_CACHE:
        n = Image.effect_noise((W * _SS, H * _SS), 20).convert("L").point(lambda v: (v - 128) // 9 + 128)
        _NOISE_CACHE["n"] = Image.merge("RGB", (n, n, n))
    return _NOISE_CACHE["n"]


# ============================================================
# KONFIG KARTU
# ============================================================

W, H = 900, 600
STAGE = (28, 176, 872, 576)           # panggung gelap tempat podium
STAGE_B = STAGE[3]
TX0 = 52

_BASE = dict(
    base=(250, 251, 255),
    ink=(8, 12, 52), ink2=(112, 56, 214), mute=(86, 88, 134),
    acc=(158, 72, 226), acc2=(36, 140, 242), glow=(130, 110, 250),
    sph=((34, 104, 226), (150, 214, 255)), bsph=((88, 40, 200), (214, 128, 250)),
    spink=((190, 40, 110), (255, 170, 210)),
    stops=[(255, 255, 255), (70, 196, 255), (238, 242, 255), (196, 112, 245), (255, 255, 255), (60, 150, 245)],
    dk0=(8, 6, 34), dk1=(36, 20, 100), dglow=(124, 104, 255), dsh=(30, 20, 110),
    dtxt=(232, 228, 255), dgrid=(190, 180, 255),
    s1=((176, 104, 16), (255, 236, 150)),
    s2=((96, 112, 160), (244, 248, 255)),
    s3=((150, 76, 44), (252, 196, 150)),
)

KINDS = {
    "rupiah": dict(title="Top Donatur", sub="Rupiah", acc=(158, 72, 226), acc2=(36, 140, 242),
                   glow=(130, 110, 250), coin=((176, 104, 16), (255, 236, 150)),
                   coin_label="Rp", coin_txt=(120, 66, 8), seed=21),
    "owo": dict(title="Top Donatur", sub="OwO", acc=(36, 140, 242), acc2=(70, 205, 255),
                glow=(84, 170, 255), coin=((16, 84, 184), (166, 232, 255)),
                coin_label="OwO", coin_txt=(8, 44, 116), seed=33),
}

# rank -> (center_x, tinggi pedestal, ukuran avatar, lebar pedestal)
SPEC = {1: (450, 128, 116, 236), 2: (215, 98, 92, 200), 3: (685, 78, 92, 200)}
RANK = {
    1: dict(col=(255, 205, 90), c0=(255, 236, 150), c1=(238, 160, 40), sph="s1", fb=((255, 170, 80), (200, 90, 200)),
            stops=[(255, 250, 215), (255, 196, 80), (255, 255, 255), (246, 150, 46), (255, 236, 160), (255, 184, 64)]),
    2: dict(col=(205, 215, 235), c0=(246, 250, 255), c1=(140, 156, 196), sph="s2", fb=((90, 110, 170), (150, 160, 210)),
            stops=[(255, 255, 255), (160, 176, 215), (240, 244, 255), (120, 140, 190), (255, 255, 255), (176, 190, 226)]),
    3: dict(col=(232, 150, 100), c0=(252, 198, 152), c1=(184, 98, 62), sph="s3", fb=((230, 110, 80), (140, 70, 170)),
            stops=[(255, 240, 225), (232, 150, 100), (255, 255, 255), (196, 104, 66), (252, 200, 160), (222, 132, 84)]),
}


def _pal(kind):
    return {**_BASE, **{k: v for k, v in KINDS[kind].items() if k in ("acc", "acc2", "glow")},
            "coin": KINDS[kind]["coin"]}


# ============================================================
# HELPER BARU
# ============================================================

def _vgrad(w, h, c0, c1, y0, y1):
    """Gradien vertikal RGBA ukuran (w, h): c0 di y0 -> c1 di y1 (px)."""
    a = np.array(c0 if len(c0) == 4 else (*c0, 255), np.float32)
    b = np.array(c1 if len(c1) == 4 else (*c1, 255), np.float32)
    t = np.clip((np.arange(h, dtype=np.float32) - y0) / max(1.0, y1 - y0), 0, 1)[:, None]
    col = a + (b - a) * t
    arr = np.broadcast_to(col[:, None, :], (h, w, 4))
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def _soft_glow(img, cx, cy, r, col, a, mask=None):
    w, h = img.size
    gm = Image.new("L", (w, h), 0)
    ImageDraw.Draw(gm).ellipse([_sc(cx - r), _sc(cy - r), _sc(cx + r), _sc(cy + r)], fill=a)
    gm = gm.filter(ImageFilter.GaussianBlur(_sc(r * 0.42)))
    if mask is not None:
        gm = ImageChops.multiply(gm, mask)
    img.paste(Image.new("RGBA", (w, h), (*col, 255)), (0, 0), gm)


def _grad_text(img, xy, text, font, c0, c1, anchor="mm", alpha=255):
    w, h = img.size
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).text((_sc(xy[0]), _sc(xy[1])), text, font=font, fill=alpha, anchor=anchor)
    bb = m.getbbox()
    if bb:
        img.paste(_vgrad(w, h, c0, c1, bb[1], bb[3]), (0, 0), m)


def _tracked(d, x, y, text, font, fill, track, anchor="lm"):
    for ch in text:
        d.text((_sc(x), _sc(y)), ch, font=font, fill=fill, anchor=anchor)
        x += font.getlength(ch) / _SS + track
    return x


def _tracked_w(text, font, track):
    return sum(font.getlength(c) / _SS + track for c in text) - track


def _fit(text, start, wmax, wght, lo=9):
    """Perkecil font sampai muat; baru dipotong dengan '…' kalau di ukuran minimum pun belum muat."""
    sz = start
    while sz > lo:
        f = _gsans(sz, wght)
        if f.getlength(text) <= _sc(wmax):
            return f, text
        sz -= 0.5
    f = _gsans(lo, wght)
    if f.getlength(text) <= _sc(wmax):
        return f, text
    while text and f.getlength(text + "…") > _sc(wmax):
        text = text[:-1]
    return f, text + "…"


def _edge(m, px=1):
    return ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_SS * 2 * px + 1)))


def _beam(body, poly, col, a, y0, y1):
    w, h = body.size
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon([(_sc(x), _sc(y)) for x, y in poly], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(_sc(7)))
    t = np.clip((np.arange(h, dtype=np.float32) - _sc(y0)) / (_sc(y1) - _sc(y0)), 0, 1)
    fade = (a * (1 - t) ** 1.15)[:, None] * np.ones((1, w), np.float32)
    m = ImageChops.multiply(m, Image.fromarray(fade.astype(np.uint8), "L"))
    body.paste(Image.new("RGBA", (w, h), (*col, 255)), (0, 0), m)


def _background(P):
    w, h = W * _SS, H * _SS
    img = Image.new("RGBA", (w, h), (247, 247, 254, 255))
    _soft_glow(img, -10, 150, 210, (60, 150, 255), 130)
    _soft_glow(img, 240, 120, 150, (120, 220, 255), 70)
    _soft_glow(img, W + 10, -10, 240, P["acc"], 150)
    _soft_glow(img, 600, -40, 140, (196, 176, 255), 70)
    ov = _gl(w, h)
    d = ImageDraw.Draw(ov)
    for y in range(26, 168, 22):                 # garis buku tulis tipis (khusus area header)
        for x in range(34, 560, 2):
            a = int(24 * max(0, 1 - (x - 34) / 526) ** 1.3)
            if a > 0:
                d.line([(_sc(x), _sc(y)), (_sc(x + 2), _sc(y))], fill=(36, 140, 242, a), width=_SS)
    return Image.alpha_composite(img, ov)


def _frame_layer():
    if "f" in _FRAME_CACHE:
        return _FRAME_CACHE["f"]
    w, h = W * _SS, H * _SS
    o = _grrmask(w, h, (8, 8, W - 8, H - 8), 18)
    i = _grrmask(w, h, (9.4, 9.4, W - 9.4, H - 9.4), 16.6)
    g = _ghgrad(w, h, _BASE["acc2"], _BASE["acc"])
    g.putalpha(ImageChops.subtract(o, i).point(lambda v: v * 95 // 255))
    _FRAME_CACHE["f"] = g
    return g


def _gcoin(img, x, y, r, label, P, txt):
    s = _gsphere(r, *P["coin"])
    sh = _gl(*img.size)
    sh.paste((255, 200, 80, 90), (_sc(x) - s.width // 2, _sc(y) - s.height // 2 + _sc(r * 0.7)), s.getchannel("A"))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(r * 0.5))))
    img.alpha_composite(s, (_sc(x) - s.width // 2, _sc(y) - s.height // 2))
    d = ImageDraw.Draw(img)
    d.ellipse([_sc(x - r * 0.72), _sc(y - r * 0.72), _sc(x + r * 0.72), _sc(y + r * 0.72)],
              outline=(255, 250, 215, 190), width=_sc(max(0.8, r * 0.07)))
    d.text((_sc(x), _sc(y + r * 0.02)), label, font=_gsans(r * (0.62 if len(label) < 3 else 0.46), 700),
           fill=(*txt, 235), anchor="mm")


def _gicon_trophy(img, cx, cy, size, rot=0):
    w, h = img.size
    g = size * 0.30
    m = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(m)
    sc = lambda pts: [(_sc(a), _sc(b)) for a, b in pts]
    md.polygon(sc([(cx - 1.0 * g, cy - 1.25 * g), (cx + 1.0 * g, cy - 1.25 * g), (cx + 0.85 * g, cy + 0.05 * g),
                   (cx + 0.32 * g, cy + 0.62 * g), (cx - 0.32 * g, cy + 0.62 * g), (cx - 0.85 * g, cy + 0.05 * g)]), fill=255)
    md.arc([_sc(cx - 1.75 * g), _sc(cy - 1.0 * g), _sc(cx - 0.55 * g), _sc(cy - 0.0 * g)], 90, 270, fill=255, width=_sc(1.9))
    md.arc([_sc(cx + 0.55 * g), _sc(cy - 1.0 * g), _sc(cx + 1.75 * g), _sc(cy - 0.0 * g)], 270, 90, fill=255, width=_sc(1.9))
    md.rectangle([_sc(cx - 0.16 * g), _sc(cy + 0.6 * g), _sc(cx + 0.16 * g), _sc(cy + 1.05 * g)], fill=255)
    md.rounded_rectangle([_sc(cx - 0.7 * g), _sc(cy + 1.02 * g), _sc(cx + 0.7 * g), _sc(cy + 1.42 * g)], radius=_sc(2), fill=255)
    if rot:
        m = m.rotate(rot, center=(_sc(cx), _sc(cy)), resample=Image.BICUBIC)
    sh = _gl(w, h)
    sh.paste((200, 120, 20, 110), (0, _sc(4)), m)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(4))))
    img.paste(_vgrad(w, h, (255, 240, 170), (232, 146, 34), _sc(cy - 1.4 * g), _sc(cy + 1.5 * g)), (0, 0), m)
    hl = Image.new("L", (w, h), 0)
    ImageDraw.Draw(hl).polygon(sc([(cx - 0.9 * g, cy - 1.15 * g), (cx - 0.35 * g, cy - 1.15 * g), (cx - 0.2 * g, cy + 0.2 * g),
                                   (cx - 0.55 * g, cy + 0.0 * g)]), fill=110)
    if rot:
        hl = hl.rotate(rot, center=(_sc(cx), _sc(cy)), resample=Image.BICUBIC)
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0), ImageChops.multiply(hl, m))
    ImageDraw.Draw(img).polygon([(_sc(a), _sc(b)) for a, b in _gsparkle(cx + 0.05 * g, cy - 0.45 * g, g * 0.5)],
                                fill=(255, 255, 255, 235))


def _draw_crown(img, cx, ty, P):
    w, h = img.size
    _soft_glow(img, cx, ty + 16, 44, (255, 205, 90), 96)
    m = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(m)
    pts = [(cx - 28, ty + 34), (cx - 34, ty + 4), (cx - 16, ty + 19), (cx, ty - 7), (cx + 16, ty + 19),
           (cx + 34, ty + 4), (cx + 28, ty + 34)]
    md.polygon([(_sc(a), _sc(b)) for a, b in pts], fill=255)
    md.rounded_rectangle([_sc(cx - 29), _sc(ty + 29), _sc(cx + 29), _sc(ty + 40)], radius=_sc(4), fill=255)
    sh = _gl(w, h)
    sh.paste((120, 60, 0, 110), (0, _sc(4)), m)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(4))))
    img.paste(_vgrad(w, h, (255, 242, 176), (234, 148, 32), _sc(ty - 7), _sc(ty + 40)), (0, 0), m)
    hl = Image.new("L", (w, h), 0)
    ImageDraw.Draw(hl).polygon([(_sc(cx - 28), _sc(ty + 34)), (_sc(cx - 34), _sc(ty + 4)), (_sc(cx - 16), _sc(ty + 19)),
                                (_sc(cx - 5), _sc(ty + 34))], fill=100)
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0), ImageChops.multiply(hl, m))
    d = ImageDraw.Draw(img)
    d.line([(_sc(cx - 28), _sc(ty + 33.5)), (_sc(cx + 28), _sc(ty + 33.5))], fill=(150, 80, 10, 210), width=_sc(1))
    for jx, jy, key in ((cx - 34, ty + 4, "sph"), (cx, ty - 7, "spink"), (cx + 34, ty + 4, "sph")):
        _gput_sphere(img, jx, jy, 4.4, P, key)
    d = ImageDraw.Draw(img)
    for jx in (cx - 15, cx, cx + 15):
        d.ellipse([_sc(jx - 1.9), _sc(ty + 33.6 + 0.2 - 1.9 + 3), _sc(jx + 1.9), _sc(ty + 33.6 + 0.2 + 1.9 + 3)],
                  fill=(255, 255, 255, 235))


def _gfallback(letter, c1, c2, n):
    g = _vgrad(n, n, c1, c2, 0, n)
    m = Image.new("L", (n * 2, n * 2), 0)
    ImageDraw.Draw(m).ellipse((0, 0, n * 2 - 1, n * 2 - 1), fill=255)
    m = m.resize((n, n), Image.LANCZOS)
    ImageDraw.Draw(g).text((n / 2, n / 2), letter, font=_gsans(n / _SS * 0.46, 700), fill=(255, 255, 255, 240), anchor="mm")
    out = _gl(n, n)
    out.paste(g, (0, 0), m)
    return out


# ============================================================
# LAYER STATIS (tidak bergantung pada data donatur)
# ============================================================

def _draw_stage(img, P):
    w, h = img.size
    x0, y0, x1, y1 = STAGE
    m = _grrmask(w, h, STAGE, 34)
    sh = _gl(w, h)
    sh.paste((*P["dsh"], 150), (0, _sc(12)), m)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(15))))

    body = _vgrad(w, h, P["dk0"], P["dk1"], _sc(y0), _sc(y1))
    for gx, gy, r, col, a in ((450, 330, 280, P["dglow"], 205), (100, 260, 180, P["acc2"], 125),
                              (800, 260, 180, P["acc"], 125), (450, 620, 240, P["acc"], 140)):
        _soft_glow(body, gx, gy, r, col, a)
    dots = _gl(w, h)
    dd = ImageDraw.Draw(dots)
    for yy in range(y0 + 10, y1, 18):
        for xx in range(x0 + 10, x1, 18):
            dd.ellipse([_sc(xx - .8), _sc(yy - .8), _sc(xx + .8), _sc(yy + .8)], fill=(*P["dgrid"], 32))
    body.alpha_composite(dots)
    hx = _gl(w, h)
    for R, a, wd in ((262, 40, 1.2), (196, 30, 1.0), (130, 24, 1.0)):
        pts = [(450 + R * math.cos(math.radians(60 * i + 30)), 392 + R * math.sin(math.radians(60 * i + 30))) for i in range(6)]
        ImageDraw.Draw(hx).line([(_sc(a_), _sc(b_)) for a_, b_ in pts + [pts[0]]], fill=(*P["dgrid"], a), width=_sc(wd), joint="curve")
    body.alpha_composite(hx)

    # sorot cahaya dari atas
    _beam(body, [(432, y0), (468, y0), (640, 548), (260, 548)], (255, 244, 214), 46, y0, 548)
    _beam(body, [(205, y0), (225, y0), (318, 548), (112, 548)], (210, 224, 255), 26, y0, 548)
    _beam(body, [(675, y0), (695, y0), (788, 548), (582, 548)], (255, 214, 190), 24, y0, 548)

    rng = random.Random(P.get("_seed", 21))
    st = _gl(w, h)
    sd = ImageDraw.Draw(st)
    for _ in range(90):
        x, y = rng.uniform(x0 + 8, x1 - 8), rng.uniform(y0 + 8, y1 - 8)
        r = rng.choice([0.7, 0.9, 1.1, 1.5])
        sd.ellipse([_sc(x - r), _sc(y - r), _sc(x + r), _sc(y + r)], fill=(255, 255, 255, rng.randint(50, 180)))
    for _ in range(14):
        x, y = rng.uniform(x0 + 30, x1 - 30), rng.uniform(y0 + 40, 440)
        s = rng.choice([3, 4, 5, 6])
        sd.polygon([(_sc(a), _sc(b)) for a, b in _gsparkle(x, y, s)], fill=(255, 236, 180, rng.randint(150, 235)))
    body.alpha_composite(st)
    img.paste(body, (0, 0), m)

    # rim gradien + kilau garis atas
    ring = _ghgrad(w, h, P["acc2"], P["acc"])
    ring.putalpha(_edge(m, 1).point(lambda v: v * 225 // 255))
    img.alpha_composite(ring)
    top_line = Image.new("L", (w, h), 0)
    ImageDraw.Draw(top_line).rounded_rectangle([_sc(x0 + 1.5), _sc(y0 + 1.5), _sc(x1 - 1.5), _sc(y0 + 70)], radius=_sc(33), outline=70, width=_SS)
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0), ImageChops.multiply(top_line, m))
    return m


def _draw_pedestal(img, rank, P, stage_mask):
    cx, ph, av, pw = SPEC[rank]
    R = RANK[rank]
    col = R["col"]
    w, h = img.size
    top = STAGE_B - ph
    x0, x1 = cx - pw // 2, cx + pw // 2
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([_sc(x0), _sc(top), _sc(x1), _sc(STAGE_B + 40)], radius=_sc(20), fill=255)
    m = ImageChops.multiply(m, stage_mask)

    _soft_glow(img, cx, top + 4, pw * 0.52, col, 70, mask=stage_mask)
    body = _vgrad(w, h, (*_lerp3((46, 30, 124), col, .42), 244), (14, 8, 50, 248), _sc(top), _sc(STAGE_B))
    body.putalpha(ImageChops.multiply(body.getchannel("A"), m))
    img.alpha_composite(body)

    gl = _gl(w, h)
    gd = ImageDraw.Draw(gl)
    gd.rectangle([_sc(x0 + 10), _sc(top), _sc(x0 + 10 + pw * 0.14), _sc(STAGE_B)], fill=(255, 255, 255, 34))
    gd.rectangle([_sc(x1 - 10 - pw * 0.10), _sc(top), _sc(x1 - 10), _sc(STAGE_B)], fill=(0, 0, 30, 60))
    gl = gl.filter(ImageFilter.GaussianBlur(_sc(5)))
    gl.putalpha(ImageChops.multiply(gl.getchannel("A"), m))
    img.alpha_composite(gl)

    # permukaan atas (kilau logam) + batang terang
    tf = Image.new("L", (w, h), 0)
    ImageDraw.Draw(tf).rounded_rectangle([_sc(x0 + 3), _sc(top + 3), _sc(x1 - 3), _sc(top + 15)], radius=_sc(9), fill=120)
    img.paste(Image.new("RGBA", (w, h), (*R["c0"], 255)), (0, 0), ImageChops.multiply(tf, m))
    bar = _gl(w, h)
    ImageDraw.Draw(bar).rounded_rectangle([_sc(x0 + 24), _sc(top - 0.5), _sc(x1 - 24), _sc(top + 3.5)], radius=_sc(2), fill=(*R["c0"], 255))
    img.alpha_composite(bar.filter(ImageFilter.GaussianBlur(_sc(5))))
    img.alpha_composite(bar)
    ed = _ghgrad(w, h, R["c0"], R["c1"])
    ed.putalpha(_edge(m, 1).point(lambda v: v * 190 // 255))
    img.alpha_composite(ed)

    ins = _gl(w, h)
    ImageDraw.Draw(ins).rounded_rectangle([_sc(x0 + 14), _sc(top + 32), _sc(x1 - 14), _sc(STAGE_B + 24)],
                                          radius=_sc(12), outline=(*R["c0"], 70), width=_SS)
    ins.putalpha(ImageChops.multiply(ins.getchannel("A"), m))
    img.alpha_composite(ins)

    # angka peringkat (serif italic, foil)
    fs = {1: 70, 2: 54, 3: 44}[rank]
    ny = top + {1: 0.66, 2: 0.64, 3: 0.68}[rank] * ph
    mk = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mk).text((_sc(cx), _sc(ny)), str(rank), font=_gserif(fs), fill=255, anchor="mm")
    mk = ImageChops.multiply(mk, m)
    bb = mk.getbbox()
    if bb:
        fg = _vgrad(w, h, (*R["c0"], 235), (*R["c1"], 150), bb[1], bb[3])
        img.paste(fg, (0, 0), mk)


def _static_layer(kind):
    if kind in _STATIC_CACHE:
        return _STATIC_CACHE[kind]
    P = _pal(kind)
    P["_seed"] = KINDS[kind]["seed"]
    img = _background(P)
    w, h = img.size

    _gbrand(img, TX0, 44, P)                      # watermark logo (posisi & ukuran sama seperti greeting)

    d = ImageDraw.Draw(img)
    ft = _gserif(40)
    d.text((_sc(TX0), _sc(104)), KINDS[kind]["title"], font=ft, fill=(*P["ink2"], 255), anchor="lm")
    tw = ft.getlength(KINDS[kind]["title"]) / _SS
    _gdraw_name(img, P, KINDS[kind]["sub"], _gsans(42, 700), TX0 + tw + 16, 104)

    ul = _gl(w, h)
    u = ImageDraw.Draw(ul)
    x0, x1 = TX0 + 8, TX0 + 300
    for x in range(_sc(x0), _sc(x1)):
        t = (x - _sc(x0)) / _sc(x1 - x0)
        u.line([(x, _sc(135)), (x, _sc(135.9))], fill=(*_lerp3(P["acc"], P["acc2"], t), int(255 * (1 - t) ** 0.9)))
    dm = 6
    u.polygon([(_sc(TX0 + 3), _sc(135.4 - dm / 1.4)), (_sc(TX0 + 3 + dm / 1.4), _sc(135.4)),
               (_sc(TX0 + 3), _sc(135.4 + dm / 1.4)), (_sc(TX0 + 3 - dm / 1.4), _sc(135.4))],
              fill=(*P["acc"], 255), outline=(255, 255, 255, 255))
    img.alpha_composite(ul)
    d = ImageDraw.Draw(img)
    d.text((_sc(TX0), _sc(154)), "Terima kasih sudah mendukung nanZ Server, setiap donasi sangat berarti.",
           font=_gsans(11.5, 500), fill=(64, 66, 112, 255), anchor="lm")

    # ornamen header: trofi di ubin kaca + bola
    _gglass_tile(img, 806, 132, 56, 10, P)
    _gicon_trophy(img, 806, 132, 56, 10)
    _gput_sphere(img, 590, 30, 3.6, P)
    _gput_sphere(img, 572, 152, 3.2, P)
    _gput_sphere(img, 868, 100, 4.2, P)

    mask = _draw_stage(img, P)
    for rk in (2, 3, 1):
        _draw_pedestal(img, rk, P, mask)

    # koin melayang + label panggung
    _gcoin(img, 92, 292, 22, KINDS[kind]["coin_label"], P, KINDS[kind]["coin_txt"])
    _gcoin(img, 828, 262, 17, KINDS[kind]["coin_label"], P, KINDS[kind]["coin_txt"])
    _gcoin(img, 832, 360, 11, KINDS[kind]["coin_label"], P, KINDS[kind]["coin_txt"])
    _gcoin(img, 120, 392, 10, KINDS[kind]["coin_label"], P, KINDS[kind]["coin_txt"])
    d = ImageDraw.Draw(img)
    ex = _tracked(d, 60, 206, "HALL OF FAME", _gsans(10, 700), (*P["dtxt"], 235), 2.6)
    ln = _gl(w, h)
    ld = ImageDraw.Draw(ln)
    for xx in range(_sc(ex + 8), _sc(ex + 8 + 70)):
        t = (xx - _sc(ex + 8)) / _sc(70)
        ld.line([(xx, _sc(206)), (xx, _sc(206.8))], fill=(*_lerp3(P["acc2"], P["acc"], t), int(220 * (1 - t))))
    img.alpha_composite(ln)
    d = ImageDraw.Draw(img)
    d.text((_sc(840), _sc(206)), "LIVE LEADERBOARD", font=_gsans(9.5, 700), fill=(*P["dtxt"], 190), anchor="rm")
    _STATIC_CACHE[kind] = (img, P)
    return _STATIC_CACHE[kind]


# ============================================================
# LAYER DINAMIS (nama, avatar, nominal)
# ============================================================

def _glass_light(img, box, r=20):
    x0, y0, x1, y1 = box
    pad = 30
    cx0, cy0 = max(0, _sc(x0 - pad)), max(0, _sc(y0 - pad))
    cx1, cy1 = min(img.width, _sc(x1 + pad)), min(img.height, _sc(y1 + pad))
    crop = img.crop((cx0, cy0, cx1, cy1))
    w, h = crop.size
    ox, oy = cx0 / _SS, cy0 / _SS
    m = _grrmask(w, h, (x0 - ox, y0 - oy, x1 - ox, y1 - oy), r)
    s = _gl(w, h)
    s.paste((_BASE["acc"][0], _BASE["acc"][1], _BASE["acc"][2], 80), (0, _sc(6)), m)
    crop.alpha_composite(s.filter(ImageFilter.GaussianBlur(_sc(9))))
    crop.paste(crop.filter(ImageFilter.GaussianBlur(_sc(8))), (0, 0), m)
    gr = Image.linear_gradient("L").resize((w, h)).rotate(30, resample=Image.BICUBIC)
    body = Image.composite(Image.new("RGBA", (w, h), (226, 218, 252, 150)), Image.new("RGBA", (w, h), (255, 255, 255, 190)), gr)
    body.putalpha(ImageChops.multiply(body.getchannel("A"), m))
    crop.alpha_composite(body)
    crop.paste(Image.new("RGBA", (w, h), (255, 255, 255, 235)), (0, 0), _edge(m, 1))
    img.paste(crop, (cx0, cy0))


def _draw_total(img, P, kind, total_text):
    val = total_text.strip()
    if val.lower().startswith("total "):
        val = val[6:]
    box = (630, 22, 872, 90)
    _glass_light(img, box, 22)
    _gcoin(img, 664, 56, 19, KINDS[kind]["coin_label"], P, KINDS[kind]["coin_txt"])
    d = ImageDraw.Draw(img)
    _tracked(d, 694, 41, "TOTAL DONASI", _gsans(8.5, 700), (*P["mute"], 255), 1.8)
    fa, ta = _fit(val, 22, 166, 700, 12)
    d.text((_sc(694), _sc(65)), ta, font=fa, fill=(*P["ink"], 255), anchor="lm")
    ln = _gl(*img.size)
    ld = ImageDraw.Draw(ln)
    for xx in range(_sc(694), _sc(694 + 110)):
        t = (xx - _sc(694)) / _sc(110)
        ld.line([(xx, _sc(78)), (xx, _sc(78.8))], fill=(*_lerp3((255, 190, 70), P["acc"], t), int(230 * (1 - t))))
    img.alpha_composite(ln)


def _amount_pill(img, cx, cy, text, font, col):
    w, h = img.size
    tw = font.getlength(text) / _SS
    pw, ph = tw + 36, 30
    box = (cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2)
    m = _grrmask(w, h, box, ph / 2)
    sh = _gl(w, h)
    sh.paste((*col, 90), (0, _sc(4)), m)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(6))))
    img.paste(_ghgrad(w, h, (*_lerp3((34, 20, 92), col, .30),), (*_lerp3((24, 12, 70), col, .12),)), (0, 0), m)
    gl = Image.new("L", (w, h), 0)
    ImageDraw.Draw(gl).rounded_rectangle([_sc(box[0] + 2), _sc(box[1] + 1.5), _sc(box[2] - 2), _sc(cy)], radius=_sc(9), fill=46)
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0), ImageChops.multiply(gl.filter(ImageFilter.GaussianBlur(1)), m))
    img.paste(Image.new("RGBA", (w, h), (*col, 255)), (0, 0), _edge(m, 1))
    ImageDraw.Draw(img).text((_sc(cx), _sc(cy)), text, font=font, fill=(255, 255, 255, 255), anchor="mm")


def _draw_rank(img, rank, row, P, total_value):
    cx, ph, av, pw = SPEC[rank]
    R = RANK[rank]
    col = R["col"]
    w, h = img.size
    top = STAGE_B - ph
    name = _gclean(row["name"], _gsans(22, 700)) if row else "—"
    amount = row["amount"] if row else "Belum ada"
    cy = top - 108 - av // 2
    rr = av / 2 + 9

    # persen dari total (di badan pedestal)
    if row and total_value > 0:
        pct = row["value"] / total_value * 100
        pct_txt = "<1% dari total" if pct < 1 else f"{round(pct)}% dari total"
    else:
        pct_txt = "—"
    d = ImageDraw.Draw(img)
    d.text((_sc(cx), _sc(top + 20)), pct_txt, font=_gsans(11.5, 500), fill=(238, 236, 252, 255), anchor="mm")

    # halo + ring avatar
    _soft_glow(img, cx, cy + 6, rr + 24, col, 100)
    ha = _gl(w, h)
    ImageDraw.Draw(ha).ellipse([_sc(cx - rr - 4), _sc(cy - rr - 4), _sc(cx + rr + 4), _sc(cy + rr + 4)], fill=(255, 255, 255, 34))
    img.alpha_composite(ha)
    _gconic_ring(img, cx, cy, av / 2 + 8, av / 2 + 3, R["stops"])
    orb = _gl(w, h)
    od = ImageDraw.Draw(orb)
    od.ellipse([_sc(cx - rr - 15), _sc(cy - rr - 15), _sc(cx + rr + 15), _sc(cy + rr + 15)], outline=(255, 255, 255, 44), width=_SS)
    for i in range(8):
        a = i * math.tau / 8 + 0.3
        px, py = cx + (rr + 15) * math.cos(a), cy + (rr + 15) * math.sin(a)
        r_ = 2.4 if i % 2 == 0 else 1.6
        od.ellipse([_sc(px - r_), _sc(py - r_), _sc(px + r_), _sc(py + r_)], fill=(*(R["c0"] if i % 2 == 0 else P["dtxt"]), 235))
    img.alpha_composite(orb)

    # avatar
    avatar = None
    if row and row.get("avatar"):
        try:
            avatar = _gavatar(row["avatar"], _sc(av))
        except Exception:
            avatar = None
    if avatar is None:
        avatar = _gfallback(name[:1].upper() if row else "?", R["fb"][0], R["fb"][1], _sc(av))
    img.alpha_composite(avatar, (_sc(cx - av / 2), _sc(cy - av / 2)))
    inn = _gl(w, h)
    ImageDraw.Draw(inn).ellipse([_sc(cx - av / 2), _sc(cy - av / 2), _sc(cx + av / 2), _sc(cy + av / 2)], outline=(255, 255, 255, 90), width=_SS)
    img.alpha_composite(inn)

    # lencana peringkat
    bx, by = cx + av / 2 * 0.72, cy + av / 2 * 0.72
    _gput_sphere(img, bx, by, 13, P, key=R["sph"])
    ImageDraw.Draw(img).text((_sc(bx), _sc(by + 0.4)), str(rank), font=_gsans(14, 700), fill=(48, 26, 72, 255), anchor="mm")

    if rank == 1:
        _draw_crown(img, cx, int(cy - rr - 44), P)

    # nama + nominal
    d = ImageDraw.Draw(img)
    ny = top - 64
    fn, tn = _fit(name, 25 if rank == 1 else 19, pw - 26, 700, 12)
    d.text((_sc(cx), _sc(ny + 1.5)), tn, font=fn, fill=(10, 4, 40, 150), anchor="mm")
    d.text((_sc(cx), _sc(ny)), tn, font=fn, fill=(255, 255, 255, 255), anchor="mm")
    fa, ta = _fit(amount, 17 if rank == 1 else 14, pw - 56, 700, 10)
    _amount_pill(img, cx, ny + 33, ta, fa, col)


def _render(kind, rows, total_value, total_text):
    with _RENDER_LOCK:
        base, P = _static_layer(kind)
        img = base.copy()
        rows = list(rows[:3]) + [None] * (3 - len(rows[:3]))
        _draw_total(img, P, kind, total_text or "")
        for rk in (2, 3, 1):
            _draw_rank(img, rk, rows[rk - 1], P, total_value or 0)
        img.alpha_composite(_frame_layer())
        out = img.convert("RGB")
        out = Image.blend(out, ImageChops.overlay(out, _gnoise()), 0.12)
        out = out.resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG", compress_level=6)
    return buf.getvalue()


def render_top_donor_card(kind: str, rows: list, total_value: int, total_text: str) -> bytes:
    """Render kartu Top 3 Donatur (900x600). Panggil di executor thread.

    kind        : "rupiah" atau "owo"
    rows        : maks 3 dict {"name","amount","value","avatar"(bytes|None)}, urut peringkat 1..3
    total_value : total semua donasi (untuk persentase)
    total_text  : mis. "Total Rp1.245.000"
    """
    if np is None:
        raise RuntimeError("numpy belum terpasang (pip install numpy)")
    if kind not in KINDS:
        kind = "rupiah"
    return _render(kind, rows, total_value, total_text)