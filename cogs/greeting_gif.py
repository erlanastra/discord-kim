import io
import math
import random
import re
import threading
import unicodedata
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

try:
    import numpy as np  # dipakai desain baru (pip install numpy)
except ImportError:  # pragma: no cover
    np = None

# =========================================================
# nanZ GREETING GIF V2 — gaya sama dengan kartu Booster:
# glass / 3D minimal / tema sekolah, dengan sisi GELAP (kiri) dan sisi TERANG (kanan).
# Font: Inter (variable) + Instrument Serif Italic. Logo: watermark nanZ.
# =========================================================
FONT_SANS = "fonts/Inter.ttf"
FONT_SERIF = "fonts/InstrumentSerif-Italic.ttf"
LOGO_PATHS = ("assets/nanz_logo.png", "nanz_logo.png", "fonts/nanz_logo.png")
_FALLBACKS = ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf")

W, H = 900, 480
_SS = 2
TOTAL_FRAMES = 48
FRAME_MS = 80
RENDER_INFO = {"engine": None, "error": None}   # diisi tiap render (untuk debugging)
HERO = (168, 206)          # pusat matahari/bulan
HERO_R = 76

_LOCK = threading.Lock()
_STATIC = {}
_FRAME_CACHE = {}


def _stops(a, b, c, d):
    return [(255, 255, 255), a, (c), b, (255, 255, 255), d]


THEMES = {
    "pagi": dict(
        session_label="SELAMAT PAGI", tagline="Rise & Shine, Murid!", sub="Semangat pagi, hari baru menanti.",
        kind="sunrise", rays=15,
        base=(255, 250, 244),
        corner=[(1.02, 1.12, 170, (255, 176, 110)), (0.58, -0.12, 150, (255, 150, 170)), (0.74, 1.30, 150, (255, 214, 140))],
        ink=(60, 22, 40), ink2=(210, 86, 54), mute=(138, 100, 96), acc=(238, 112, 64), acc2=(255, 176, 86),
        rule=(240, 130, 80), vig=(170, 90, 70),
        sph=((255, 148, 38), (255, 238, 172)), bsph=((190, 70, 20), (255, 172, 72)),
        stops=[(255, 255, 255), (255, 176, 86), (255, 244, 232), (238, 112, 64), (255, 255, 255), (255, 150, 170)],
        dk0=(24, 9, 40), dk1=(104, 40, 78), dglow=(255, 150, 90), dsh=(110, 40, 40),
        dtxt=(255, 236, 222), dgrid=(255, 200, 170), dgk=0.85, bk=(255, 255, 255),
        pen=((190, 70, 20), (255, 176, 86)), nib=(255, 232, 190),
        book=((255, 176, 86), (238, 112, 64)), cap=((196, 78, 40), (255, 176, 86)),
    ),
    "siang": dict(
        session_label="SELAMAT SIANG", tagline="Keep Going, Murid!", sub="Istirahat sejenak, lanjut lagi!",
        kind="noon", rays=21,
        base=(243, 249, 255),
        corner=[(1.02, 1.12, 170, (90, 170, 255)), (0.58, -0.12, 150, (130, 214, 255)), (0.74, 1.30, 150, (160, 140, 255))],
        ink=(8, 28, 70), ink2=(28, 108, 228), mute=(84, 106, 142), acc=(40, 130, 245), acc2=(80, 200, 255),
        rule=(36, 140, 242), vig=(50, 90, 190),
        sph=((255, 176, 30), (255, 248, 188)), bsph=((20, 70, 190), (110, 200, 255)),
        stops=[(255, 255, 255), (80, 200, 255), (238, 246, 255), (40, 130, 245), (255, 255, 255), (150, 140, 255)],
        dk0=(5, 14, 50), dk1=(18, 58, 150), dglow=(70, 160, 255), dsh=(20, 50, 130),
        dtxt=(226, 238, 255), dgrid=(170, 210, 255), dgk=1.0, bk=(255, 255, 255),
        pen=((36, 90, 210), (80, 200, 255)), nib=(228, 238, 252),
        book=((36, 140, 242), (80, 200, 255)), cap=((28, 90, 210), (80, 200, 255)),
    ),
    "sore": dict(
        session_label="SELAMAT SORE", tagline="Chill Time, Murid!", sub="Nikmati sore yang tenang.",
        kind="sunset", rays=11,
        base=(253, 246, 252),
        corner=[(1.02, 1.12, 170, (255, 140, 130)), (0.58, -0.12, 150, (204, 104, 240)), (0.74, 1.30, 150, (255, 190, 120))],
        ink=(52, 14, 62), ink2=(186, 56, 168), mute=(128, 92, 134), acc=(208, 68, 190), acc2=(255, 142, 100),
        rule=(220, 90, 200), vig=(140, 60, 150),
        sph=((255, 92, 52), (255, 204, 120)), bsph=((120, 30, 140), (255, 140, 140)),
        stops=[(255, 255, 255), (255, 142, 100), (255, 240, 250), (208, 68, 190), (255, 255, 255), (150, 110, 255)],
        dk0=(20, 7, 46), dk1=(104, 30, 112), dglow=(255, 112, 130), dsh=(90, 20, 100),
        dtxt=(255, 232, 246), dgrid=(255, 180, 220), dgk=0.9, bk=(255, 255, 255),
        pen=((140, 36, 150), (255, 142, 100)), nib=(255, 226, 236),
        book=((255, 142, 100), (208, 68, 190)), cap=((140, 36, 150), (255, 142, 100)),
    ),
    "malam": dict(
        session_label="SELAMAT MALAM", tagline="Good Night, Murid!", sub="Istirahat yang nyenyak.",
        kind="moon", rays=0,
        base=(244, 245, 253),
        corner=[(1.02, 1.12, 170, (110, 100, 232)), (0.58, -0.12, 150, (72, 142, 236)), (0.74, 1.30, 150, (150, 120, 240))],
        ink=(14, 10, 52), ink2=(84, 62, 206), mute=(92, 94, 142), acc=(110, 84, 230), acc2=(70, 150, 240),
        rule=(90, 90, 220), vig=(60, 56, 170),
        sph=((150, 160, 204), (250, 250, 255)), bsph=((60, 40, 170), (150, 170, 250)),
        stops=[(255, 255, 255), (110, 170, 255), (238, 240, 255), (110, 84, 230), (255, 255, 255), (70, 150, 240)],
        dk0=(3, 3, 20), dk1=(20, 12, 62), dglow=(100, 90, 240), dsh=(30, 20, 110),
        dtxt=(232, 230, 255), dgrid=(180, 176, 255), dgk=1.0, bk=(255, 255, 255),
        pen=((70, 34, 190), (110, 170, 255)), nib=(228, 234, 250),
        book=((70, 150, 240), (110, 84, 230)), cap=((70, 44, 206), (70, 150, 240)),
    ),
}


# ---------------------------------------------------------
# helper dasar
# ---------------------------------------------------------
def _sc(v):
    return int(round(v * _SS))


def _lerp3(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def _clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))


def _ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _gl(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def _edge_x(y):
    """Garis pemisah diagonal gelap (kiri) / terang (kanan)."""
    return 336 + 64 * y / H


@lru_cache(maxsize=96)
def _gsans(size, wght=500):
    px = _sc(size)
    for p in (FONT_SANS, *_FALLBACKS):
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
    for p in (FONT_SERIF, FONT_SANS, *_FALLBACKS):
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
    print("[Greeting] Logo nanZ tidak ditemukan; watermark dibuat tanpa logo. Cek LOGO_PATHS.")
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


def _gclean(text, font, fallback=""):
    """Buang karakter yang tidak ada di font (emoji dsb) supaya tidak muncul kotak."""
    try:
        notdef = _gglyph(font, "\U0010FFFF")
    except Exception:
        notdef = None
    out = []
    for ch in str(text):
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
    return clean or fallback


def _gfit(text, start, wmax, wght, min_size=12):
    s = start
    while s > min_size:
        f = _gsans(s, wght)
        if f.getlength(text) <= _sc(wmax):
            return f, text
        s -= 1
    f = _gsans(min_size, wght)
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


def _edge_of(m):
    return ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(_SS * 2 + 1)))


# ---------------------------------------------------------
# elemen 3D / kaca (sama dengan gaya Booster)
# ---------------------------------------------------------
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


def _gglass_ruler(img, cx, cy, Lr, Wr, rot, P):
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
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 225)), (0, 0), _edge_of(m))
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


def _gribbon(img, P, x0, wd=22, y0=-6, y1=76):
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
    for y in range(8, int(y1 - 18), 6):
        d.line([(_sc(x0 + wd / 2), _sc(y)), (_sc(x0 + wd / 2), _sc(y + 3))], fill=(255, 255, 255, 190), width=_SS)
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 110)), (0, 0), _edge_of(m))


def _ghexagon(img, cx, cy, R, color, alpha, width=1.2):
    pts = [(cx + R * math.cos(math.radians(60 * i)), cy + R * math.sin(math.radians(60 * i))) for i in range(6)]
    l = _gl(*img.size)
    ImageDraw.Draw(l).line([(_sc(x), _sc(y)) for x, y in pts + [pts[0]]], fill=(*color, alpha),
                           width=_sc(width), joint="curve")
    img.alpha_composite(l)


def _gbokeh(img, P, seed=5, n=14):
    rng = random.Random(seed)
    w, h = img.size
    l = _gl(w, h)
    d = ImageDraw.Draw(l)
    for _ in range(n):
        y = rng.uniform(14, H - 14)
        x = rng.uniform(14, _edge_x(y) - 18)
        r = rng.choice([2, 2.5, 3, 4, 6])
        a = rng.randint(50, 120)
        col = rng.choice([(255, 255, 255), P["dglow"], P["acc2"], (255, 255, 255)])
        d.ellipse([_sc(x - r), _sc(y - r), _sc(x + r), _sc(y + r)], fill=(*col, a))
        if r >= 4:
            d.ellipse([_sc(x - r), _sc(y - r), _sc(x + r), _sc(y + r)],
                      outline=(255, 255, 255, min(180, a + 60)), width=_SS)
    img.alpha_composite(l.filter(ImageFilter.GaussianBlur(0.8)))


def _gstars(img, P, seed=9):
    rng = random.Random(seed)
    w, h = img.size
    l = _gl(w, h)
    d = ImageDraw.Draw(l)
    for _ in range(46):
        y = rng.uniform(8, H - 8)
        x = rng.uniform(8, _edge_x(y) - 14)
        r = rng.choice([0.7, 0.9, 1.1, 1.4])
        d.ellipse([_sc(x - r), _sc(y - r), _sc(x + r), _sc(y + r)], fill=(255, 255, 255, rng.randint(70, 190)))
    img.alpha_composite(l)


def _garc_text(img, cx, cy, R, text, font, fill, track):
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


def _conic_sprite(r_out, r_in, stops):
    """Cincin konik gradien, dikembalikan pada ukuran 1x (nanti diputar tiap frame)."""
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
    return im.resize((n // _SS, n // _SS), Image.LANCZOS)


# ---------------------------------------------------------
# lapisan statis (per sesi, di-cache)
# ---------------------------------------------------------
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
    for y in range(30, H - 14, 22):              # garis buku tulis (motif sekolah), kuat di tepi kanan
        for x in range(436, 868, 2):
            a = int(40 * max(0, 1 - (866 - x) / 430) ** 1.3)
            if a > 0:
                d.line([(_sc(x), _sc(y)), (_sc(x + 2), _sc(y))], fill=(*P["rule"], a), width=_SS)
    d.line([(_sc(862), _sc(12)), (_sc(862), _sc(H - 12))], fill=(240, 120, 200, 46), width=_SS)
    return Image.alpha_composite(img, ov)


def _gvignette(img, P):
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt(((xx - w * 0.45) / (w * 0.62)) ** 2 + ((yy - h * 0.5) / (h * 0.78)) ** 2)
    a = np.clip((d - 0.75) / 0.75, 0, 1) ** 1.6 * 46
    v = np.dstack([np.full((h, w), c) for c in P["vig"]] + [a]).astype(np.uint8)
    img.alpha_composite(Image.fromarray(v))


def _gdark_panel(img, P):
    w, h = img.size
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon([(0, 0), (_sc(_edge_x(0)), 0), (_sc(_edge_x(H)), h), (0, h)], fill=255)
    sh = _gl(w, h)
    sh.paste((*P["dsh"], 110), (_sc(7), 0), m)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(11))))

    g = Image.linear_gradient("L").resize((w, h))
    body = Image.composite(Image.new("RGBA", (w, h), (*P["dk1"], 255)), Image.new("RGBA", (w, h), (*P["dk0"], 255)), g)
    for gx, gy, r, col, a in ((HERO[0], HERO[1], 200, P["dglow"], 205), (-10, -10, 150, P["acc2"], 95),
                              (370, 500, 130, P["acc"], 90)):
        gm = Image.new("L", (w, h), 0)
        ImageDraw.Draw(gm).ellipse([_sc(gx - r), _sc(gy - r), _sc(gx + r), _sc(gy + r)], fill=int(a * P["dgk"]))
        body.paste(Image.new("RGBA", (w, h), (*col, 255)), (0, 0), gm.filter(ImageFilter.GaussianBlur(_sc(r * 0.45))))
    dots = _gl(w, h)
    dd = ImageDraw.Draw(dots)
    for yy in range(14, H, 16):                  # grid titik = kertas berpetak
        for xx in range(14, 420, 16):
            dd.ellipse([_sc(xx - 0.9), _sc(yy - 0.9), _sc(xx + 0.9), _sc(yy + 0.9)], fill=(*P["dgrid"], 40))
    body.alpha_composite(dots)
    img.paste(body, (0, 0), m)

    pts = [(_sc(_edge_x(y)), _sc(y)) for y in range(0, H + 1, 10)]
    glow = _gl(w, h)
    gd = ImageDraw.Draw(glow)
    for i in range(len(pts) - 1):
        gd.line([pts[i], pts[i + 1]], fill=(*_lerp3(P["acc2"], P["acc"], i / (len(pts) - 1)), 255), width=_sc(3))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(_sc(5))))
    ln = _gl(w, h)
    ld = ImageDraw.Draw(ln)
    for i in range(len(pts) - 1):
        ld.line([pts[i], pts[i + 1]], fill=(*_lerp3(P["acc2"], P["acc"], i / (len(pts) - 1)), 255), width=_sc(1.6))
    img.alpha_composite(ln)
    hl = _gl(w, h)
    hd = ImageDraw.Draw(hl)
    for i in range(len(pts) - 1):
        hd.line([(pts[i][0] - _sc(2), pts[i][1]), (pts[i + 1][0] - _sc(2), pts[i + 1][1])], fill=(255, 255, 255, 70), width=_SS)
    img.alpha_composite(hl)


def _gframe_layer(P):
    w, h = W * _SS, H * _SS
    o = _grrmask(w, h, (9, 9, W - 9, H - 9), 18)
    i = _grrmask(w, h, (10.6, 10.6, W - 10.6, H - 10.6), 16.6)
    g = _ghgrad(w, h, P["acc2"], P["acc"])
    g.putalpha(ImageChops.subtract(o, i).point(lambda v: v * 150 // 255))
    o2 = _grrmask(w, h, (11.6, 11.6, W - 11.6, H - 11.6), 16)
    i2 = _grrmask(w, h, (12.6, 12.6, W - 12.6, H - 12.6), 15)
    hl = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    hl.putalpha(ImageChops.subtract(o2, i2).point(lambda v: v * 170 // 255))
    return Image.alpha_composite(g, hl)


def _hero_sphere(P):
    s = _gsphere(HERO_R, *P["sph"])
    kind = P["kind"]
    lay = _gl(*s.size)
    d = ImageDraw.Draw(lay)
    c = s.width / 2
    R = _sc(HERO_R)
    if kind == "moon":
        for rx, ry, rr in ((-0.35, -0.25, 0.20), (0.30, 0.15, 0.26), (-0.05, 0.48, 0.14),
                           (0.42, -0.42, 0.12), (-0.52, 0.22, 0.10)):
            d.ellipse([c + R * (rx - rr), c + R * (ry - rr), c + R * (rx + rr), c + R * (ry + rr)],
                      fill=(70, 78, 130, 90))
        lay = lay.filter(ImageFilter.GaussianBlur(_sc(1.3)))
    elif kind in ("sunrise", "sunset"):
        bars = ((0.30, 0.37), (0.48, 0.57), (0.68, 0.82)) if kind == "sunset" else ((0.52, 0.60), (0.74, 0.90))
        for a, b in bars:
            d.rectangle([0, c + R * a, s.width, c + R * b], fill=(*P["dk1"], 170))
    lay.putalpha(ImageChops.multiply(lay.getchannel("A"), s.getchannel("A")))
    s.alpha_composite(lay)
    return s


def _gstatic(session):
    if session in _STATIC:
        return _STATIC[session]
    P = THEMES[session]
    w, h = W * _SS, H * _SS
    img = _gbackground(P)
    _gvignette(img, P)
    _gdark_panel(img, P)
    cx, cy = HERO

    _ghexagon(img, cx, cy, 214, P["dgrid"], 40)
    _ghexagon(img, cx, cy, 168, P["acc2"], 80, 1.0)
    _gstars(img, P)
    _gbokeh(img, P)
    _gribbon(img, P, _edge_x(0) - 11)

    # jalur orbit putus-putus (satelit bergerak ada di frame)
    orb = _gl(w, h)
    od = ImageDraw.Draw(orb)
    for k in range(0, 360, 6):
        for step in range(3):
            u = math.radians(k + step * 2)
            u2 = math.radians(k + step * 2 + 2)
            p0, p1 = _orbit_pt(u), _orbit_pt(u2)
            od.line([(_sc(p0[0]), _sc(p0[1])), (_sc(p1[0]), _sc(p1[1]))], fill=(*P["dgrid"], 70), width=_SS)
    img.alpha_composite(orb)

    # glass tiles & dekor sekolah di panel gelap
    _gglass_tile(img, 296, 66, 56, 12, P, dark=True)
    _gicon_book(img, 296, 66, 56, 12, P)
    _gglass_tile(img, 308, 402, 50, -10, P, dark=True)
    _gicon_cap(img, 308, 402, 50, -10, P)

    # penggaris kaca + pena di sisi terang
    _gglass_ruler(img, 770, 52, 150, 27, -8, P)
    _gput_pen(img, 842, 434, 96, 12, 225, P)
    for sx, sy, sr in ((398, 128, 5), (418, 330, 4), (452, 214, 3.5)):
        _gput_sphere(img, sx, sy, sr, P)

    # hero: glow + halo + bola matahari/bulan
    sh = _gl(w, h)
    ImageDraw.Draw(sh).ellipse([_sc(cx - HERO_R - 6), _sc(cy - HERO_R + 6), _sc(cx + HERO_R + 6), _sc(cy + HERO_R + 22)],
                               fill=(*P["dglow"], 190))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(20))))
    ha = _gl(w, h)
    ImageDraw.Draw(ha).ellipse([_sc(cx - HERO_R - 13), _sc(cy - HERO_R - 13), _sc(cx + HERO_R + 13), _sc(cy + HERO_R + 13)],
                               fill=(255, 255, 255, 255))
    img.alpha_composite(ha)
    hs = _hero_sphere(P)
    img.alpha_composite(hs, (_sc(cx) - hs.width // 2, _sc(cy) - hs.height // 2))
    inner = _gl(w, h)
    ImageDraw.Draw(inner).ellipse([_sc(cx - HERO_R), _sc(cy - HERO_R), _sc(cx + HERO_R), _sc(cy + HERO_R)],
                                  outline=(255, 255, 255, 90), width=_SS)
    img.alpha_composite(inner)
    _garc_text(img, cx, cy, HERO_R + 27, "·  nanZ  SERVER  GREETING  ·", _gsans(9, 700), (*P["dtxt"], 240), 2.4)

    _gbrand(img, 40, 49, P)                      # watermark: selalu tampil dari frame pertama sampai terakhir
    img.alpha_composite(_gframe_layer(P))
    out = img.convert("RGB").resize((W, H), Image.LANCZOS).convert("RGBA")
    _STATIC[session] = out
    return out


def _orbit_pt(u):
    """Titik pada elips orbit yang miring, mengelilingi hero (koordinat 1x)."""
    rx, ry, rot = 150, 50, math.radians(-24)
    x, y = rx * math.cos(u), ry * math.sin(u)
    return (HERO[0] + x * math.cos(rot) - y * math.sin(rot), HERO[1] + x * math.sin(rot) + y * math.cos(rot))


# ---------------------------------------------------------
# elemen teks / kartu (di-render sekali per GIF, lalu fade-in per frame)
# ---------------------------------------------------------
_PAD = 18


def _mk(x, y, bw, bh, fn):
    """Kanvas lokal 2x berpadding; fn menggambar dengan koordinat lokal (padding sudah termasuk)."""
    im = _gl((bw + 2 * _PAD) * _SS, (bh + 2 * _PAD) * _SS)
    fn(im)
    return im.resize((bw + 2 * _PAD, bh + 2 * _PAD), Image.LANCZOS), (x - _PAD, y - _PAD)


def _gbrand(img, x, cy, P):
    """Watermark: logo nanZ kecil + tulisan 'nanZ SERVER' (versi untuk latar gelap)."""
    w, h = img.size
    lg = _glogo(_sc(46))
    if lg is not None:
        lx, ly = _sc(x), _sc(cy) - lg.height // 2
        gl = _gl(w, h)
        gl.paste((*P["dglow"], 150), (lx, ly + _sc(3)), lg.getchannel("A"))
        img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(_sc(5))))
        img.alpha_composite(lg, (lx, ly))
        tx = x + lg.width / _SS + 9
    else:
        tx = x
    d = ImageDraw.Draw(img)
    f1 = _gsans(23, 700)
    d.text((_sc(tx), _sc(cy - 8)), "nan", font=f1, fill=(255, 255, 255, 255), anchor="lm")
    zx = tx + f1.getlength("nan") / _SS
    d.text((_sc(zx), _sc(cy - 8)), "Z", font=f1, fill=(*P["acc2"], 255), anchor="lm")
    f2 = _gsans(9.5, 700)
    cxp = tx + 1
    for ch in "SERVER":
        d.text((_sc(cxp), _sc(cy + 13)), ch, font=f2, fill=(*P["dtxt"], 215), anchor="lm")
        cxp += f2.getlength(ch) / _SS + 3.4
    ln = _gl(w, h)
    ld = ImageDraw.Draw(ln)
    x1 = cxp + 8
    for xx in range(_sc(x1), _sc(x1 + 46)):
        t = (xx - _sc(x1)) / _sc(46)
        ld.line([(xx, _sc(cy + 13)), (xx, _sc(cy + 13.8))], fill=(*_lerp3(P["acc2"], P["acc"], t), int(200 * (1 - t))))
    img.alpha_composite(ln)


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
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 200)), (0, 0), _edge_of(m))


def _gradient_text(img, x, cy, text, font, c0, c1, shadow):
    w, h = img.size
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).text((_sc(x), _sc(cy)), text, font=font, fill=255, anchor="lm")
    m3 = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m3).text((_sc(x), _sc(cy) + _sc(3)), text, font=font, fill=255, anchor="lm")
    sh = _gl(w, h)
    sh.paste((*shadow, 75), (0, 0), m3.filter(ImageFilter.GaussianBlur(_sc(5))))
    img.alpha_composite(sh)
    bb = m.getbbox()
    if bb:
        g = _gl(w, h)
        gd = ImageDraw.Draw(g)
        for xx in range(bb[0], bb[2] + 1):
            gd.line([(xx, bb[1]), (xx, bb[3])], fill=(*_lerp3(c0, c1, (xx - bb[0]) / max(1, bb[2] - bb[0])), 255))
        img.paste(g, (0, 0), m)


def _ic_clock(d, cx, cy, s, col, wd):
    d.ellipse([_sc(cx - s), _sc(cy - s), _sc(cx + s), _sc(cy + s)], outline=col, width=wd)
    d.line([(_sc(cx), _sc(cy)), (_sc(cx), _sc(cy - s * 0.62))], fill=col, width=wd)
    d.line([(_sc(cx), _sc(cy)), (_sc(cx + s * 0.48), _sc(cy + s * 0.24))], fill=col, width=wd)


def _ic_calendar(d, cx, cy, s, col, wd):
    d.rounded_rectangle([_sc(cx - s), _sc(cy - s * 0.78), _sc(cx + s), _sc(cy + s)], radius=_sc(2.4), outline=col, width=wd)
    d.line([(_sc(cx - s), _sc(cy - s * 0.15)), (_sc(cx + s), _sc(cy - s * 0.15))], fill=col, width=wd)
    for sx in (-0.5, 0.5):
        d.line([(_sc(cx + s * sx), _sc(cy - s * 1.12)), (_sc(cx + s * sx), _sc(cy - s * 0.5))], fill=col, width=wd)
    for sx in (-0.45, 0.0, 0.45):
        d.ellipse([_sc(cx + s * sx - 0.9), _sc(cy + s * 0.42 - 0.9), _sc(cx + s * sx + 0.9), _sc(cy + s * 0.42 + 0.9)], fill=col)


def _ic_weather(d, cx, cy, s, col, wd):
    d.ellipse([_sc(cx + s * 0.02), _sc(cy - s * 0.95), _sc(cx + s * 0.95), _sc(cy - s * 0.02)], outline=col, width=wd)
    d.rounded_rectangle([_sc(cx - s), _sc(cy + s * 0.05), _sc(cx + s * 0.85), _sc(cy + s * 0.85)], radius=_sc(s * 0.4), fill=col)
    d.ellipse([_sc(cx - s * 0.55), _sc(cy - s * 0.35), _sc(cx + s * 0.25), _sc(cy + s * 0.45)], fill=col)


def _foil_tile(img, box, P, icon):
    w, h = img.size
    x0, y0, x1, y1 = box
    m = _grrmask(w, h, box, (x1 - x0) * 0.3)
    s = _gl(w, h)
    s.paste((*P["acc"], 120), (0, _sc(4)), m)
    img.alpha_composite(s.filter(ImageFilter.GaussianBlur(_sc(5))))
    img.paste(_ghgrad(w, h, P["acc"], P["acc2"]), (0, 0), m)
    gl = Image.new("L", (w, h), 0)
    ImageDraw.Draw(gl).rounded_rectangle([_sc(x0 + 2), _sc(y0 + 1.5), _sc(x1 - 2), _sc((y0 + y1) / 2)], radius=_sc(5), fill=70)
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0), ImageChops.multiply(gl.filter(ImageFilter.GaussianBlur(1)), m))
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 200)), (0, 0), _edge_of(m))
    icon(ImageDraw.Draw(img), (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * 0.27, (255, 255, 255, 255), _sc(1.8))


def _glass_card(img, box, P, r=14):
    w, h = img.size
    m = _grrmask(w, h, box, r)
    s = _gl(w, h)
    s.paste((*P["acc"], 80), (0, _sc(5)), m)
    img.alpha_composite(s.filter(ImageFilter.GaussianBlur(_sc(7))))
    img.alpha_composite(Image.composite(Image.new("RGBA", (w, h), (255, 255, 255, 238)), _gl(w, h), m))
    sheen = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sheen).rounded_rectangle([_sc(box[0] + 3), _sc(box[1] + 2), _sc(box[2] - 3), _sc((box[1] + box[3]) / 2)],
                                            radius=_sc(r - 3), fill=60)
    img.paste(Image.new("RGBA", (w, h), (*P["acc2"], 255)), (0, 0), ImageChops.multiply(sheen.filter(ImageFilter.GaussianBlur(_sc(2))), m).point(lambda v: v // 3))
    img.paste(Image.new("RGBA", (w, h), (*P["acc2"], 150)), (0, 0), _edge_of(m))


def _info_card(x, y, bw, label, value, icon, P):
    bh = 50

    def fn(im):
        _glass_card(im, (_PAD, _PAD, _PAD + bw, _PAD + bh), P)
        _foil_tile(im, (_PAD + 9, _PAD + 10, _PAD + 39, _PAD + 40), P, icon)
        d = ImageDraw.Draw(im)
        f1 = _gsans(8.5, 700)
        cxp = _PAD + 50
        for ch in label.upper():
            d.text((_sc(cxp), _sc(_PAD + 16)), ch, font=f1, fill=(*P["mute"], 255), anchor="lm")
            cxp += f1.getlength(ch) / _SS + 1.3
        fv, val = _gfit(value, 16, bw - 62, 650, 10)
        d.text((_sc(_PAD + 50), _sc(_PAD + 34)), val, font=fv, fill=(*P["ink"], 255), anchor="lm")
    return _mk(x, y, bw, bh, fn)


def _wrap(text, font, wmax, max_lines):
    words, lines, line = text.split(), [], ""
    for wd in words:
        t = (line + " " + wd).strip()
        if font.getlength(t) > _sc(wmax) and line:
            lines.append(line)
            line = wd
        else:
            line = t
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and font.getlength(last + "…") > _sc(wmax):
            last = last[:-1]
        lines[-1] = last + "…"
    return lines


def _build_elements(P, jam_str, hari, tanggal, cuaca, quote, server_name):
    els = []          # (sprite, (x, y), start_frame)
    RX = 446          # margin kiri kolom teks (sisi terang)

    # chip waktu (kaca gelap) di bawah hero
    ft = _gsans(21, 700)
    cw = int(ft.getlength(jam_str) / _SS) + 62

    def chip(im):
        w, h = im.size
        box = (_PAD, _PAD, _PAD + cw, _PAD + 38)
        m = _grrmask(w, h, box, 19)
        s = _gl(w, h)
        s.paste((0, 0, 0, 120), (0, _sc(5)), m)
        im.alpha_composite(s.filter(ImageFilter.GaussianBlur(_sc(7))))
        im.alpha_composite(Image.composite(Image.new("RGBA", (w, h), (255, 255, 255, 36)), _gl(w, h), m))
        im.paste(Image.new("RGBA", (w, h), (255, 255, 255, 125)), (0, 0), _edge_of(m))
        _foil_tile(im, (_PAD + 6, _PAD + 6, _PAD + 32, _PAD + 32), P, _ic_clock)
        ImageDraw.Draw(im).text((_sc(_PAD + 42), _sc(_PAD + 19)), jam_str, font=ft, fill=(255, 255, 255, 255), anchor="lm")
    els.append((*_mk(HERO[0] - cw // 2, 346, cw, 38, chip), 2))

    # pill sesi
    lab = P["session_label"]
    fp = _gsans(13, 700)
    pw = fp.getlength(lab) / _SS + 50

    def pill(im):
        box = (_PAD, _PAD, _PAD + pw, _PAD + 32)
        _gfoil_pill(im, box, P)
        d = ImageDraw.Draw(im)
        d.polygon([(_sc(a), _sc(b)) for a, b in _gsparkle(_PAD + 22, _PAD + 16, 6.5)], fill=(255, 255, 255, 255))
        d.text((_sc(_PAD + 37), _sc(_PAD + 16)), lab, font=fp, fill=(255, 255, 255, 255), anchor="lm")
    els.append((*_mk(RX, 34, int(pw), 32, pill), 3))

    # tagline serif + nama server gradien
    tag = _gclean(P["tagline"], _gserif(36), "Halo, Murid!")
    els.append((*_mk(RX, 84, 410, 46, lambda im: ImageDraw.Draw(im).text(
        (_sc(_PAD), _sc(_PAD + 23)), tag, font=_gserif(40), fill=(*P["ink2"], 255), anchor="lm")), 4))
    sname = _gclean(server_name, _gsans(46, 700), "nanZ Server")
    fn_, nm = _gfit(sname, 52, 400, 700, 22)
    els.append((*_mk(RX, 136, 410, 62, lambda im: _gradient_text(
        im, _PAD, _PAD + 31, nm, fn_, P["ink"], P["ink2"], P["acc"])), 5))

    # divider berlian
    def divider(im):
        w, h = im.size
        ul = _gl(w, h)
        u = ImageDraw.Draw(ul)
        x0, x1 = _PAD + 12, _PAD + 212
        for x in range(_sc(x0), _sc(x1)):
            t = (x - _sc(x0)) / _sc(x1 - x0)
            u.line([(x, _sc(_PAD + 6)), (x, _sc(_PAD + 6.8))], fill=(*_lerp3(P["acc"], P["acc2"], t), int(255 * (1 - t) ** 0.8)))
        dm = 6
        u.polygon([(_sc(_PAD + 3), _sc(_PAD + 6.4 - dm / 1.4)), (_sc(_PAD + 3 + dm / 1.4), _sc(_PAD + 6.4)),
                   (_sc(_PAD + 3), _sc(_PAD + 6.4 + dm / 1.4)), (_sc(_PAD + 3 - dm / 1.4), _sc(_PAD + 6.4))],
                  fill=(*P["acc"], 255), outline=(255, 255, 255, 255))
        im.alpha_composite(ul)
    els.append((*_mk(RX, 202, 240, 14, divider), 6))

    # sub tagline
    sub = _gclean(P["sub"], _gsans(15, 500), "")
    els.append((*_mk(RX, 222, 410, 22, lambda im: ImageDraw.Draw(im).text(
        (_sc(_PAD), _sc(_PAD + 11)), sub, font=_gsans(15, 500), fill=(*P["mute"], 255), anchor="lm")), 7))

    # kartu info
    cw2 = 200
    els.append((*_info_card(RX, 256, cw2, "Hari", hari, _ic_calendar, P), 8))
    els.append((*_info_card(RX + cw2 + 12, 256, cw2, "Tanggal", tanggal, _ic_calendar, P), 9))
    els.append((*_info_card(RX, 316, cw2 * 2 + 12, "Cuaca Hari Ini", _gclean(cuaca, _gsans(16, 650), "N/A"), _ic_weather, P), 10))

    # kutipan (serif italic)
    fq = _gserif(20)
    q = _gclean(quote, fq, "")
    lines = _wrap(q, fq, 320, 2) if q else []
    if lines:
        def quote_el(im):
            d = ImageDraw.Draw(im)
            d.text((_sc(_PAD), _sc(_PAD + 12)), "“", font=_gserif(44), fill=(*P["acc"], 255), anchor="lm")
            for i, ln in enumerate(lines):
                d.text((_sc(_PAD + 26), _sc(_PAD + 10 + i * 24)), ln, font=fq, fill=(*P["ink"], 235), anchor="lm")
        els.append((*_mk(RX, 392, 350, 24 * len(lines) + 10, quote_el), 12))
    return els


# ---------------------------------------------------------
# frame animasi
# ---------------------------------------------------------
def _sprite_sphere(P, r, key="bsph"):
    s = _gsphere(r, *P[key])
    n = s.width + _sc(16)
    im = _gl(n, n)
    gl = _gl(n, n)
    gl.paste((*P["dglow"], 230), ((n - s.width) // 2, (n - s.height) // 2), s.getchannel("A"))
    im.alpha_composite(gl.filter(ImageFilter.GaussianBlur(_sc(5))))
    im.alpha_composite(s, ((n - s.width) // 2, (n - s.height) // 2))
    return im.resize((n // _SS, n // _SS), Image.LANCZOS)


def _draw_rays(img, P, f):
    n = P["rays"]
    if not n:
        return
    half = 150
    l = _gl(half * 2 * _SS, half * 2 * _SS)
    d = ImageDraw.Draw(l)
    for i in range(n):
        a = math.radians(160 + 220 * i / (n - 1))
        ph = 2 * math.pi * f / TOTAL_FRAMES
        ln = 15 + 10 * math.sin(2 * ph + i * 0.9)
        r0 = HERO_R + 22
        x0, y0 = half + r0 * math.cos(a), half + r0 * math.sin(a)
        x1, y1 = half + (r0 + ln) * math.cos(a), half + (r0 + ln) * math.sin(a)
        col = P["acc2"] if i % 2 == 0 else (255, 255, 255)
        d.line([(_sc(x0), _sc(y0)), (_sc(x1), _sc(y1))], fill=(*col, 215 if i % 2 == 0 else 160), width=_sc(2.4))
        d.ellipse([_sc(x1 - 1.2), _sc(y1 - 1.2), _sc(x1 + 1.2), _sc(y1 + 1.2)], fill=(*col, 215))
    l = l.resize((half * 2, half * 2), Image.LANCZOS)
    img.alpha_composite(l, (HERO[0] - half, HERO[1] - half))


_SPARKLES = [(40, 120, 7, 1, 0.0), (252, 150, 6, 2, 1.3), (316, 250, 7, 1, 2.1), (60, 318, 6, 2, 0.7),
             (250, 330, 5, 1, 3.0), (244, 58, 6, 2, 2.2), (456, 160, 5, 1, 1.0), (845, 150, 6, 2, 0.4)]


def _draw_sparkles(img, f):
    for x, y, s, k, ph in _SPARKLES:
        tw = (math.sin(2 * math.pi * k * f / TOTAL_FRAMES + ph) + 1) / 2
        sz = s * (0.35 + 0.65 * tw)
        size = int(s * 2 + 6)
        l = _gl(size * _SS, size * _SS)
        ImageDraw.Draw(l).polygon([(_sc(a), _sc(b)) for a, b in _gsparkle(size / 2, size / 2, sz)],
                                  fill=(255, 255, 255, _clamp(90 + 165 * tw)))
        img.alpha_composite(l.resize((size, size), Image.LANCZOS), (int(x - size / 2), int(y - size / 2)))


def _sweep_sprite():
    w = 150
    l = _gl(w * _SS, H * _SS)
    ImageDraw.Draw(l).polygon([(_sc(100), 0), (_sc(130), 0), (_sc(46), _sc(H)), (_sc(16), _sc(H))], fill=(255, 255, 255, 60))
    return l.filter(ImageFilter.GaussianBlur(_sc(8))).resize((w, H), Image.LANCZOS)


def _render_frames(P, st, elements):
    ring = _conic_sprite(HERO_R + 10, HERO_R + 3.5, P["stops"])
    sat = _sprite_sphere(P, 4.6)
    sweep = _sweep_sprite()
    frames = []
    for f in range(TOTAL_FRAMES):
        img = st.copy()
        _draw_rays(img, P, f)
        rot = -360.0 * f / TOTAL_FRAMES
        rr = ring.rotate(rot, resample=Image.BICUBIC)
        img.alpha_composite(rr, (HERO[0] - rr.width // 2, HERO[1] - rr.height // 2))
        for k in range(2):
            u = 2 * math.pi * (f / TOTAL_FRAMES) + k * math.pi
            px, py = _orbit_pt(u)
            back = math.sin(u) < 0
            if back and math.hypot(px - HERO[0], py - HERO[1]) < HERO_R + 14:
                continue
            img.alpha_composite(sat, (int(round(px - sat.width / 2)), int(round(py - sat.height / 2))))
        _draw_sparkles(img, f)
        sx = int(-150 + (W + 300) * f / TOTAL_FRAMES)
        _paste_clip(img, sweep, sx, 0)

        out_k = 1.0 if f < TOTAL_FRAMES - 5 else max(0.0, (TOTAL_FRAMES - 1 - f) / 5)
        for spr, (ex, ey), start in elements:
            p = _ease_out((f - start) / 7.0)
            k = p * out_k
            if k <= 0.01:
                continue
            dy = int(round(14 * (1 - p)))
            s2 = spr
            if k < 0.995:
                s2 = spr.copy()
                s2.putalpha(s2.getchannel("A").point(lambda v, k=k: int(v * k)))
            _paste_clip(img, s2, ex, ey + dy)
        frames.append(img.convert("RGB"))
    return frames


def _paste_clip(img, spr, x, y):
    cx0, cy0 = max(0, -x), max(0, -y)
    cx1, cy1 = min(spr.width, W - x), min(spr.height, H - y)
    if cx1 > cx0 and cy1 > cy0:
        img.alpha_composite(spr.crop((cx0, cy0, cx1, cy1)), (max(0, x), max(0, y)))


def _generate_v2(session, jam_str, hari, tanggal, cuaca, quote, server_name="nanZ"):
    """Desain baru (glass / 3D, gelap-terang). Mengembalikan bytes GIF 900x480."""
    if np is None:
        raise RuntimeError("numpy belum terpasang (pip install numpy)")
    key = session if session in THEMES else "pagi"
    P = THEMES[key]
    with _LOCK:
        st = _gstatic(key)
        elements = _build_elements(P, jam_str, hari, tanggal, cuaca, quote, server_name)
        frames = _render_frames(P, st, elements)

    # Dither dengan noise TETAP (sama di semua frame) + palet global:
    # gradasi halus tanpa banding, area diam identik antar frame -> ukuran GIF kecil.
    noise = (np.random.default_rng(3).random((H, W, 1)) - 0.5) * 5.0
    noised = [Image.fromarray(np.clip(np.asarray(f, np.float32) + noise, 0, 255).astype(np.uint8)) for f in frames]
    sheet = Image.new("RGB", (W // 2, (H // 2) * 4))
    for i, k in enumerate((0, 14, 26, 40)):
        sheet.paste(noised[k].resize((W // 2, H // 2)), (0, i * (H // 2)))
    pal = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    out_frames = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in noised]

    buf = io.BytesIO()
    out_frames[0].save(buf, format="GIF", save_all=True, append_images=out_frames[1:], loop=0,
                       duration=FRAME_MS, optimize=True, disposal=1)
    return buf.getvalue()


# =========================================================
# DESAIN LAMA — hanya dipakai sebagai cadangan kalau desain baru gagal
# (mis. numpy belum terpasang), supaya greeting tetap terkirim.
# =========================================================
_L_FONT_BOLD = "fonts/LEMONMILK-Bold.otf"
_L_FONT_MEDIUM = "fonts/LEMONMILK-Medium.otf"
_L_FONT_REGULAR = "fonts/LEMONMILK-Regular.otf"
_L_FONT_LIGHT = "fonts/LEMONMILK-Light.otf"

_L_THEMES = {
    "pagi": {"bg_top": (18, 10, 45), "bg_bot": (40, 20, 80), "accent1": (130, 80, 255), "accent2": (80, 180, 255),
             "card_bg": (30, 15, 65), "label": (160, 120, 255), "tagline": "Rise & Shine, Murid!",
             "sub": "Semangat pagi, hari baru menanti.", "session_label": "SELAMAT PAGI"},
    "siang": {"bg_top": (10, 20, 55), "bg_bot": (20, 40, 100), "accent1": (60, 160, 255), "accent2": (120, 60, 240),
              "card_bg": (15, 25, 70), "label": (100, 180, 255), "tagline": "Keep Going, Murid!",
              "sub": "Istirahat sejenak, lanjut lagi!", "session_label": "SELAMAT SIANG"},
    "sore": {"bg_top": (25, 10, 55), "bg_bot": (55, 20, 90), "accent1": (200, 80, 255), "accent2": (80, 140, 255),
             "card_bg": (35, 10, 70), "label": (190, 110, 255), "tagline": "Chill Time, Murid!",
             "sub": "Nikmati sore yang tenang.", "session_label": "SELAMAT SORE"},
    "malam": {"bg_top": (5, 5, 25), "bg_bot": (20, 10, 50), "accent1": (90, 60, 200), "accent2": (40, 120, 220),
              "card_bg": (12, 8, 35), "label": (120, 100, 220), "tagline": "Good Night, Murid!",
              "sub": "Istirahat yang nyenyak.", "session_label": "SELAMAT MALAM"},
}
_L_FRAMES = 36
_L_DELAY = 8


def _l_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _l_particles(seed=42, n=55):
    rng = random.Random(seed)
    return [{"x": rng.uniform(0, W), "y": rng.uniform(0, H), "vx": rng.uniform(-0.4, 0.4),
             "vy": rng.uniform(-0.6, -0.15), "r": rng.uniform(1.2, 3.0), "alpha": rng.randint(60, 180),
             "phase": rng.uniform(0, math.pi * 2)} for _ in range(n)]


def _l_render_frame(frame_idx, theme, jam_str, hari, tanggal, cuaca, quote, server_name, particles):
    t_global = frame_idx / (_L_FRAMES - 1)
    pulse = (math.sin(frame_idx * 0.28) + 1) / 2
    canvas = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(canvas)
    for y in range(H):
        draw.line([(0, y), (W, y)], fill=_lerp3(theme["bg_top"], theme["bg_bot"], y / H))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for i, (cx, cy, base_r, color) in enumerate([(W * 0.15, H * 0.25, 170, theme["accent1"]),
                                                  (W * 0.82, H * 0.70, 140, theme["accent2"]),
                                                  (W * 0.55, H * 0.08, 100, theme["accent1"])]):
        p = (math.sin(frame_idx * 0.22 + i * (math.pi * 2 / 3)) + 1) / 2
        r = int(base_r * (0.88 + 0.22 * p))
        for step in range(r, 0, -5):
            alpha = int(60 * (step / r) ** 2.8 * (0.7 + 0.3 * p))
            ImageDraw.Draw(overlay).ellipse([cx - step, cy - step, cx + step, cy + step], fill=(*color[:3], _clamp(alpha)))
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for y in range(0, H, 40):
        gd.line([(0, y), (W, y)], fill=(*theme["accent1"][:3], 15), width=1)
    for x in range(0, W, 40):
        gd.line([(x, 0), (x, H)], fill=(*theme["accent1"][:3], 15), width=1)
    overlay = Image.alpha_composite(overlay, grid)
    stars = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stars)
    for p in particles:
        px = (p["x"] + p["vx"] * frame_idx * 1.5) % W
        py = (p["y"] + p["vy"] * frame_idx * 1.5) % H
        tw = (math.sin(frame_idx * 0.35 + p["phase"]) + 1) / 2
        r = p["r"]
        sd.ellipse([px - r, py - r, px + r, py + r],
                   fill=(*_lerp3(theme["accent1"], theme["accent2"], tw), _clamp(p["alpha"] * (0.5 + 0.5 * tw))))
    overlay = Image.alpha_composite(overlay, stars)
    base = Image.alpha_composite(canvas.convert("RGBA"), overlay)

    cards = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cards)
    ca = _clamp(190 + 20 * pulse)
    cd.rounded_rectangle([40, 55, 530, 430], radius=18, fill=(*theme["card_bg"], ca))
    cd.rounded_rectangle([40, 55, 530, 430], radius=18, outline=(*theme["accent1"][:3], 85), width=2)
    cd.rounded_rectangle([560, 55, 860, 430], radius=18, fill=(*theme["card_bg"], ca))
    cd.rounded_rectangle([560, 55, 860, 430], radius=18, outline=(*theme["accent2"][:3], 85), width=2)
    base = Image.alpha_composite(base, cards)

    tl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(tl)
    f_huge, f_medium = _l_font(_L_FONT_BOLD, 62), _l_font(_L_FONT_MEDIUM, 22)
    f_small, f_tiny, f_label = _l_font(_L_FONT_REGULAR, 17), _l_font(_L_FONT_LIGHT, 14), _l_font(_L_FONT_MEDIUM, 15)

    def prog(d):
        return _ease_out(min(max(0, (t_global - d) / (1.0 - d + 0.001)) * 2.5, 1.0))

    def ta(d):
        return _clamp(255 * prog(d))

    def so(d, mo=20):
        return int(mo * (1 - prog(d)))

    td.text((62, 78 + so(0.0)), theme["session_label"], font=f_label, fill=(*theme["label"][:3], ta(0.0)))
    td.text((62, 105 + so(0.05)), server_name, font=f_huge, fill=(255, 255, 255, ta(0.05)))
    td.text((62, 182 + so(0.15)), theme["tagline"], font=f_medium, fill=(*theme["accent2"][:3], ta(0.15)))
    dl = int(380 * _ease_out(min(max(0, (t_global - 0.2) * 3), 1.0)))
    for i in range(dl):
        td.line([(62 + i, 218), (62 + i, 219)], fill=(*_lerp3(theme["accent1"], theme["accent2"], i / 380), 180))
    td.text((62, 228 + so(0.25)), theme["sub"], font=f_small, fill=(200, 200, 220, ta(0.25)))
    lines, line = [], ""
    for wd in quote.split():
        t = (line + " " + wd).strip()
        bb = td.textbbox((0, 0), t, font=f_small)
        if bb[2] - bb[0] > 390 and line:
            lines.append(line)
            line = wd
        else:
            line = t
    if line:
        lines.append(line)
    for i_line, ln in enumerate(lines[:3]):
        td.text((85, 270 + i_line * 24 + so(0.35)), ln, font=f_small, fill=(210, 200, 240, ta(0.35)))
    td.text((62, H - 50), f"{server_name}  \u2022  nanZ Greeting  \u2022  {hari}", font=f_tiny,
            fill=(*theme["accent1"][:3], _clamp(ta(0.5) * 0.5)))
    for y0, lab, val, d in ((80, "Waktu", jam_str, 0.1), (145, "Hari", hari, 0.2),
                            (210, "Tanggal", tanggal, 0.3), (275, "Cuaca Hari Ini", cuaca, 0.4)):
        td.text((575, y0 + so(d, 15)), lab.upper(), font=f_tiny, fill=(*theme["label"][:3], _clamp(ta(d) * 0.65)))
        td.text((575, y0 + 16 + so(d, 15)), val, font=f_medium, fill=(255, 255, 255, ta(d)))
    return Image.alpha_composite(base, tl).convert("RGB")


def _generate_legacy(session, jam_str, hari, tanggal, cuaca, quote, server_name="nanZ"):
    theme = _L_THEMES.get(session, _L_THEMES["pagi"])
    particles = _l_particles(seed=sum(map(ord, session)) % 9999, n=55)
    frames = []
    for i in range(_L_FRAMES):
        fr = _l_render_frame(i, theme, jam_str, hari, tanggal, cuaca, quote, server_name, particles)
        frames.append(fr.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=1))
    out = io.BytesIO()
    frames[0].save(out, format="GIF", save_all=True, append_images=frames[1:], loop=0,
                   duration=_L_DELAY * 10, optimize=True, disposal=2)
    return out.getvalue()


def generate_greeting_gif(session, jam_str, hari, tanggal, cuaca, quote, server_name="nanZ"):
    """Entry point (dipakai cogs/greeting.py). Mengembalikan bytes GIF 900x480."""
    try:
        data = _generate_v2(session, jam_str, hari, tanggal, cuaca, quote, server_name)
        RENDER_INFO.update(engine="v2", error=None)
        return data
    except Exception as e:
        # Jangan sampai greeting terjadwal gagal terkirim: kembali ke desain lama.
        RENDER_INFO.update(engine="legacy", error=repr(e))
        print(f"[Greeting] Desain baru gagal ({e!r}); memakai desain lama.")
        return _generate_legacy(session, jam_str, hari, tanggal, cuaca, quote, server_name)


# -- Tes cepat: python greeting_gif.py --
if __name__ == "__main__":
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("Asia/Jakarta"))
    for s in ("pagi", "siang", "sore", "malam"):
        print(f"Generating {s}...", end=" ", flush=True)
        data = generate_greeting_gif(s, f"{now.hour:02d}:00 WIB", "Jumat", now.strftime("%d %B %Y"),
                                     "25\u00b0C, Cerah Berawan", "Jangan berhenti sampai kamu bangga!", "nanZ Server")
        with open(f"test_greeting_{s}.gif", "wb") as f:
            f.write(data)
        print(f"OK {len(data) // 1024} KB (engine: {RENDER_INFO['engine']})")