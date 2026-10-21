import asyncio
import atexit
import io
import math
import random
import re
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache

import discord
from discord.ext import commands
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

try:
    import numpy as np  # dipakai desain kartu baru (pip install numpy)
except ImportError:  # pragma: no cover
    np = None

# ══════════════════════════════════════════════
# KONFIGURASI
# ══════════════════════════════════════════════

WELCOME_CHANNEL_ID = 1554124578006114415
LEAVE_CHANNEL_ID = 1554124709535424572


# ══════════════════════════════════════════════
# PNG GENERATOR
# ══════════════════════════════════════════════

FONT_BOLD = "fonts/LEMONMILK-Bold.otf"
FONT_MEDIUM = "fonts/LEMONMILK-Medium.otf"
FONT_REGULAR = "fonts/LEMONMILK-Regular.otf"

_FALLBACKS = (
    "DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "arial.ttf",
)

BG_TOP = (16, 8, 40)
BG_BOT = (42, 20, 84)
CARD_BG = (26, 12, 58)

PURPLE = (130, 80, 255)
BLUE = (80, 180, 255)
ROSE = (255, 110, 170)

SOFT_PURPLE = (160, 120, 255)
SOFT_BLUE = (150, 210, 255)
SOFT_ROSE = (255, 170, 205)

WHITE = (255, 255, 255)
MUTED = (165, 160, 195)

W, H = 800, 340
SS = 2  # fallback legacy: supersampling lebih rendah untuk menghemat RAM

CX, CY, R = 646, 170, 90
HR = 130

TX0, TX1 = 56, 452

BULAN = [
    "Jan", "Feb", "Mar", "Apr",
    "Mei", "Jun", "Jul", "Agu",
    "Sep", "Okt", "Nov", "Des"
]


THEMES = {
    "welcome": {
        "c1": BLUE,
        "c2": PURPLE,
        "soft": SOFT_BLUE,
        "tag": "WELCOME",
        "body": "Selamat datang di nanZ Server, semoga betah ya!",
        "chip1": lambda n: f"Member ke-{n}",
        "date_col": PURPLE,
        "icon": "plus",
        "gray": False,
    },

    "leave": {
        "c1": ROSE,
        "c2": PURPLE,
        "soft": SOFT_ROSE,
        "tag": "GOODBYE",
        "body": "Makasih udah pernah jadi bagian dari nanZ Server.",
        "chip1": lambda n: f"Sisa {n} member",
        "date_col": SOFT_PURPLE,
        "icon": "minus",
        "gray": True,
    },
}


# ══════════════════════════════════════════════
# HELPER
# ══════════════════════════════════════════════

def fmt_date(dt: datetime) -> str:
    return f"{dt.day} {BULAN[dt.month - 1]} {dt.year}"


def fmt_num(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _font(path, size):
    for p in (path, *_FALLBACKS):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue

    return ImageFont.load_default()


def _lerp(c1, c2, t):
    return tuple(
        int(c1[i] + (c2[i] - c1[i]) * t)
        for i in range(3)
    )


def _clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))


def _fit_font(draw, text, path, start, max_w, min_size=20):
    size = start

    while size >= min_size:
        f = _font(path, size)

        if draw.textlength(text, font=f) <= max_w:
            return f, text

        size -= 2

    f = _font(path, min_size)

    while text and draw.textlength(text + "…", font=f) > max_w:
        text = text[:-1]

    return f, text + "…"


def _spaced(draw, xy, text, font, fill, spacing=3):
    x, y = xy

    for ch in text:
        draw.text(
            (x, y),
            ch,
            font=font,
            fill=fill,
            anchor="lm"
        )

        x += draw.textlength(ch, font=font) + spacing

    return x


def _ss_layer(fn):
    big = Image.new(
        "RGBA",
        (W * SS, H * SS),
        (0, 0, 0, 0)
    )

    fn(ImageDraw.Draw(big))

    return big.resize(
        (W, H),
        Image.LANCZOS
    )


def _ss_mask(fn):
    big = Image.new(
        "L",
        (W * SS, H * SS),
        0
    )

    fn(ImageDraw.Draw(big))

    return big.resize(
        (W, H),
        Image.LANCZOS
    )


def _circle_mask(r):
    m = Image.new(
        "L",
        (r * 2 * SS, r * 2 * SS),
        0
    )

    ImageDraw.Draw(m).ellipse(
        [
            0,
            0,
            r * 2 * SS - 1,
            r * 2 * SS - 1
        ],
        fill=255
    )

    return m.resize(
        (r * 2, r * 2),
        Image.LANCZOS
    )


def _prepare_avatar(avatar_bytes, size, gray=False):
    im = Image.open(
        io.BytesIO(avatar_bytes)
    ).convert("RGBA")

    m = min(im.size)

    l = (im.width - m) // 2
    t = (im.height - m) // 2

    im = im.crop(
        (l, t, l + m, t + m)
    )

    im = im.resize(
        (size, size),
        Image.LANCZOS
    )

    flat = Image.new(
        "RGBA",
        im.size,
        (*BG_BOT, 255)
    )

    im = Image.alpha_composite(
        flat,
        im
    ).convert("RGB")

    if gray:
        im = ImageEnhance.Color(im).enhance(0.25)
        im = ImageEnhance.Brightness(im).enhance(0.9)

    return im


def _sparkle_poly(x, y, sz):
    q = sz * 0.25

    return [
        (x, y - sz),
        (x + q, y - q),
        (x + sz, y),
        (x + q, y + q),
        (x, y + sz),
        (x - q, y + q),
        (x - sz, y),
        (x - q, y - q),
    ]


def _hex_pts(cx, cy, r):
    return [
        (
            cx + r * math.cos(math.radians(60 * k)),
            cy + r * math.sin(math.radians(60 * k))
        )
        for k in range(6)
    ]


def _diag_gradient(c1, c2, c3):
    g = Image.new("RGB", (W, H))
    gd = ImageDraw.Draw(g)

    n = W + H

    for k in range(n):
        t = k / n

        if t < 0.5:
            col = _lerp(c1, c2, t * 2)
        else:
            col = _lerp(
                c2,
                c3,
                (t - 0.5) * 2
            )

        gd.line(
            [(k, 0), (k - H, H)],
            fill=col,
            width=2
        )

    return g


# ══════════════════════════════════════════════
# BACKGROUND
# ══════════════════════════════════════════════

def _make_fx(seed=7):
    rng = random.Random(seed)

    stars = [
        {
            "x": rng.uniform(0, W),
            "y": rng.uniform(0, H),
            "r": rng.uniform(1.0, 2.4),
            "tw": rng.random(),
            "a": rng.randint(90, 200),
        }
        for _ in range(55)
    ]

    sparkles = [
        {
            "x": rng.uniform(15, W - 15),
            "y": rng.uniform(12, H - 12),
            "s": rng.uniform(5, 9),
            "tw": rng.uniform(0.4, 1.0),
        }
        for _ in range(9)
    ]

    return {
        "stars": stars,
        "sparkles": sparkles
    }


def _honeycomb(c, soft):
    lay = Image.new(
        "RGBA",
        (W, H),
        (0, 0, 0, 0)
    )

    d = ImageDraw.Draw(lay)

    r = 24
    dx = 1.5 * r
    dy = math.sqrt(3) * r

    rng = random.Random(5)

    col = 0
    x = 380

    while x < W + r:
        y = -dy + (
            dy / 2
            if col % 2
            else 0
        )

        while y < H + dy:
            dist = math.hypot(
                x - CX,
                y - CY
            )

            fade = 1 - (
                (dist - HR) / 300
            )

            if dist > HR + 8 and fade > 0:
                d.polygon(
                    _hex_pts(
                        x,
                        y,
                        r - 1.5
                    ),
                    outline=(
                        *soft,
                        _clamp(70 * fade)
                    ),
                    width=1
                )

                if rng.random() < 0.10:
                    d.polygon(
                        _hex_pts(
                            x,
                            y,
                            r - 1.5
                        ),
                        fill=(
                            *c,
                            _clamp(38 * fade)
                        )
                    )

            y += dy

        x += dx
        col += 1

    return lay


def _background(fx, c1, c2, soft):
    bg = Image.new(
        "RGB",
        (W, H)
    )

    bd = ImageDraw.Draw(bg)

    for y in range(H):
        bd.line(
            [(0, y), (W, y)],
            fill=_lerp(
                BG_TOP,
                BG_BOT,
                y / H
            )
        )

    base = bg.convert("RGBA")

    # ORBS
    orbs = Image.new(
        "RGBA",
        (W, H),
        (0, 0, 0, 0)
    )

    od = ImageDraw.Draw(orbs)

    for ox, oy, br, oc in [
        (W * .06, H * .12, 150, c2),
        (W * .92, H * .80, 160, c1),
        (W * .55, -10, 120, c2),
    ]:
        for st in range(br, 0, -5):
            od.ellipse(
                [
                    ox - st,
                    oy - st,
                    ox + st,
                    oy + st
                ],
                fill=(
                    *oc,
                    _clamp(
                        60 *
                        (st / br) ** 2.8 *
                        0.85
                    )
                )
            )

    base = Image.alpha_composite(
        base,
        orbs
    )

    # AURORA
    aur = Image.new(
        "RGBA",
        (W, H),
        (0, 0, 0, 0)
    )

    ad = ImageDraw.Draw(aur)

    for by, amp, k, off, col, a in [
        (250, 26, 2, 0.0, c1, 55),
        (285, 20, 3, 2.0, c2, 70),
    ]:
        pts = [
            (
                x,
                by + amp * math.sin(
                    math.tau * k * x / W + off
                )
            )
            for x in range(0, W + 10, 10)
        ]

        ad.polygon(
            pts + [(W, H), (0, H)],
            fill=(*col, a)
        )

    base = Image.alpha_composite(
        base,
        aur.filter(
            ImageFilter.GaussianBlur(6)
        )
    )

    # BEAMS
    beams = Image.new(
        "RGBA",
        (W, H),
        (0, 0, 0, 0)
    )

    bmd = ImageDraw.Draw(beams)

    for x0, wd, a in [
        (470, 34, 26),
        (540, 14, 32),
        (600, 70, 16),
    ]:
        bmd.polygon(
            [
                (x0, 0),
                (x0 + wd, 0),
                (x0 + wd - 190, H),
                (x0 - 190, H)
            ],
            fill=(*soft, a)
        )

    base = Image.alpha_composite(
        base,
        beams.filter(
            ImageFilter.GaussianBlur(5)
        )
    )

    # HONEYCOMB
    base = Image.alpha_composite(
        base,
        _honeycomb(c1, soft)
    )

    # PARTICLES
    fl = Image.new(
        "RGBA",
        (W, H),
        (0, 0, 0, 0)
    )

    fd = ImageDraw.Draw(fl)

    for gy in range(8, H, 14):
        for gx in range(8, 440, 14):
            a = _clamp(
                60 *
                (1 - gx / 440) ** 1.2
            )

            if a > 4:
                fd.ellipse(
                    [
                        gx - 1.2,
                        gy - 1.2,
                        gx + 1.2,
                        gy + 1.2
                    ],
                    fill=(*soft, a)
                )

    for p in fx["stars"]:
        r = p["r"]
        tw = p["tw"]

        fd.ellipse(
            [
                p["x"] - r,
                p["y"] - r,
                p["x"] + r,
                p["y"] + r
            ],
            fill=(
                *_lerp(c2, c1, tw),
                _clamp(
                    p["a"] *
                    (0.45 + 0.55 * tw)
                )
            )
        )

    for p in fx["sparkles"]:
        tw = p["tw"]

        fd.polygon(
            _sparkle_poly(
                p["x"],
                p["y"],
                p["s"] *
                (0.35 + 0.65 * tw)
            ),
            fill=(
                *_lerp(
                    soft,
                    SOFT_PURPLE,
                    tw
                ),
                _clamp(
                    70 + 185 * tw
                )
            )
        )

    base = Image.alpha_composite(
        base,
        fl
    )

    # FRAME
    fr = Image.new(
        "RGBA",
        (W, H),
        (0, 0, 0, 0)
    )

    frd = ImageDraw.Draw(fr)

    frd.rounded_rectangle(
        [8, 8, W - 9, H - 9],
        radius=16,
        outline=(*soft, 70),
        width=1
    )

    L = 26

    for (
        x,
        y,
        dx,
        dy
    ) in [
        (16, 16, 1, 1),
        (W - 17, 16, -1, 1),
        (16, H - 17, 1, -1),
        (W - 17, H - 17, -1, -1),
    ]:
        frd.line(
            [
                (x, y + dy * L),
                (x, y),
                (x + dx * L, y)
            ],
            fill=(*c1, 220),
            width=3,
            joint="curve"
        )

    return Image.alpha_composite(
        base,
        fr
    )


def _shooting_stars(lay, soft, seed):
    rng = random.Random(seed)

    d = ImageDraw.Draw(lay)

    for _ in range(3):
        x = rng.uniform(300, 760)
        y = rng.uniform(14, 120)

        ang = math.radians(
            rng.uniform(140, 155)
        )

        ln = rng.uniform(70, 120)

        steps = 30

        for i in range(steps):
            t0 = i / steps
            t1 = (i + 1) / steps

            a = int(
                230 * t0 ** 1.6
            )

            p0 = (
                x -
                math.cos(ang) *
                ln *
                (1 - t0),

                y -
                math.sin(ang) *
                ln *
                (1 - t0)
            )

            p1 = (
                x -
                math.cos(ang) *
                ln *
                (1 - t1),

                y -
                math.sin(ang) *
                ln *
                (1 - t1)
            )

            d.line(
                [p0, p1],
                fill=(*soft, a),
                width=2
            )

        d.ellipse(
            [
                x - 2.2,
                y - 2.2,
                x + 2.2,
                y + 2.2
            ],
            fill=(*WHITE, 255)
        )


def _particles(mode, c1, c2, soft):
    rng = random.Random(
        77 if mode == "welcome"
        else 88
    )

    bok = Image.new(
        "RGBA",
        (W, H),
        (0, 0, 0, 0)
    )

    bd = ImageDraw.Draw(bok)

    for _ in range(11):
        x = rng.uniform(0, W)
        y = rng.uniform(0, H)
        r = rng.uniform(6, 17)

        bd.ellipse(
            [
                x - r,
                y - r,
                x + r,
                y + r
            ],
            fill=(
                *rng.choice(
                    [c1, c2, soft]
                ),
                rng.randint(22, 48)
            )
        )

    lay = bok.filter(
        ImageFilter.GaussianBlur(2.5)
    )

    d = ImageDraw.Draw(lay)

    if mode == "welcome":
        cols = [
            c1,
            c2,
            soft,
            WHITE,
            SOFT_PURPLE
        ]

        for _ in range(34):
            x = rng.uniform(445, W - 6)
            y = rng.uniform(6, H - 6)

            if math.hypot(
                x - CX,
                y - CY
            ) < R + 40:
                continue

            a = rng.uniform(
                0,
                math.pi
            )

            w = rng.uniform(4, 8)
            h = rng.uniform(2, 3.5)

            pts = [
                (
                    x +
                    math.cos(a) * dx -
                    math.sin(a) * dy,

                    y +
                    math.sin(a) * dx +
                    math.cos(a) * dy
                )

                for dx, dy in [
                    (-w, -h),
                    (w, -h),
                    (w, h),
                    (-w, h)
                ]
            ]

            d.polygon(
                pts,
                fill=(
                    *rng.choice(cols),
                    rng.randint(150, 235)
                )
            )

    _shooting_stars(
        lay,
        soft,
        5 if mode == "welcome"
        else 9
    )

    return lay


# ══════════════════════════════════════════════
# GLASS PANEL
# ══════════════════════════════════════════════

def _glass_panel(c1, c2):
    def edge(y):
        return 486 - 46 * y / H

    S = 2

    pan = Image.new(
        "RGBA",
        (W * S, H * S),
        (0, 0, 0, 0)
    )

    pd = ImageDraw.Draw(pan)

    poly = [
        (0, 0),
        (edge(0) * S, 0),
        (edge(H) * S, H * S),
        (0, H * S)
    ]

    pd.polygon(
        poly,
        fill=(*CARD_BG, 165)
    )

    pd.polygon(
        poly,
        fill=(255, 255, 255, 9)
    )

    pd.polygon(
        [
            (190 * S, 0),
            (240 * S, 0),
            (184 * S, H * S),
            (134 * S, H * S)
        ],
        fill=(255, 255, 255, 8)
    )

    pd.polygon(
        [
            (262 * S, 0),
            (274 * S, 0),
            (218 * S, H * S),
            (206 * S, H * S)
        ],
        fill=(255, 255, 255, 10)
    )

    for y in range(0, H, 3):
        col = _lerp(
            c1,
            c2,
            y / H
        )

        pd.line(
            [
                (edge(y) * S, y * S),
                (edge(y + 3) * S, (y + 3) * S)
            ],
            fill=(*col, 255),
            width=6
        )

        pd.line(
            [
                ((edge(y) - 13) * S, y * S),
                ((edge(y + 3) - 13) * S, (y + 3) * S)
            ],
            fill=(*col, 80),
            width=2
        )

    return pan.resize(
        (W, H),
        Image.LANCZOS
    )


def _milestone(n):
    step = 100 if n < 1000 else 500

    ms = (
        n // step + 1
    ) * step

    prog = max(
        0.03,
        min(1, n / ms)
    )

    return ms, prog


# ══════════════════════════════════════════════
# RENDER CARD
# ══════════════════════════════════════════════

def _render_entrance_legacy(
    avatar_bytes: bytes,
    name: str,
    mode: str = "welcome",
    number: int = 0,
    date_text: str = "",
    username: str = "",
    caption: str = "",
) -> bytes:

    th = THEMES[mode]

    c1 = th["c1"]
    c2 = th["c2"]
    soft = th["soft"]

    welcome = mode == "welcome"

    # BACKGROUND
    base = _background(
        _make_fx(
            seed=21 if welcome else 33
        ),
        c1,
        c2,
        soft
    )

    base = Image.alpha_composite(
        base,
        _particles(
            mode,
            c1,
            c2,
            soft
        )
    )

    spot = Image.new(
        "RGBA",
        (W, H),
        (0, 0, 0, 0)
    )

    sd = ImageDraw.Draw(spot)

    for r_, a_ in [
        (200, 40),
        (170, 55),
        (140, 75)
    ]:
        sd.ellipse(
            [
                CX - r_,
                CY - r_,
                CX + r_,
                CY + r_
            ],
            fill=(*c2, a_)
        )

    base = Image.alpha_composite(
        base,
        spot.filter(
            ImageFilter.GaussianBlur(26)
        )
    )

    base = Image.alpha_composite(
        base,
        _glass_panel(c1, c2)
    )

    # AVATAR HALO
    halo = Image.new(
        "RGBA",
        (W, H),
        (*c1, 0)
    )

    hm = Image.new(
        "L",
        (W, H),
        0
    )

    ImageDraw.Draw(hm).ellipse(
        [
            CX - R - 6,
            CY - R - 6,
            CX + R + 6,
            CY + R + 6
        ],
        fill=200
    )

    halo.putalpha(
        hm.filter(
            ImageFilter.GaussianBlur(16)
        )
    )

    base = Image.alpha_composite(
        base,
        halo
    )

    # MAIN RING
    ring = _ss_mask(
        lambda d: d.ellipse(
            [
                (CX - R - 6) * SS,
                (CY - R - 6) * SS,
                (CX + R + 6) * SS,
                (CY + R + 6) * SS
            ],
            outline=255,
            width=5 * SS
        )
    )

    holo = _diag_gradient(
        soft,
        c1,
        c2
    ).convert("RGBA")

    holo.putalpha(ring)

    # OUTER RING
    RO = R + 22

    bb = [
        (CX - RO) * SS,
        (CY - RO) * SS,
        (CX + RO) * SS,
        (CY + RO) * SS
    ]

    if welcome:
        _, prog = _milestone(number)

        end_deg = (
            -90 +
            360 * prog
        )

        base = Image.alpha_composite(
            base,
            _ss_layer(
                lambda d: d.ellipse(
                    bb,
                    outline=(*soft, 45),
                    width=1 * SS
                )
            )
        )

        arc_m = _ss_mask(
            lambda d: d.arc(
                bb,
                -90,
                end_deg,
                fill=255,
                width=4 * SS
            )
        )

        arc = _diag_gradient(
            c1,
            soft,
            c2
        ).convert("RGBA")

        arc.putalpha(arc_m)

        base = Image.alpha_composite(
            base,
            arc.filter(
                ImageFilter.GaussianBlur(5)
            )
        )

        base = Image.alpha_composite(
            base,
            arc
        )

        dot_deg = end_deg

    else:

        def dashed(d):
            for k in range(0, 360, 12):
                d.arc(
                    bb,
                    k,
                    k + 6,
                    fill=(*soft, 90),
                    width=2 * SS
                )

        base = Image.alpha_composite(
            base,
            _ss_layer(dashed)
        )

        dot_deg = -50

    # TICK RING
    RT = R + 36

    def ticks(d):
        for k in range(72):
            a = math.radians(
                k * 5 - 90
            )

            major = k % 6 == 0

            r0 = RT
            r1 = RT + (
                7 if major else 3.5
            )

            d.line(
                [
                    (
                        (CX + r0 * math.cos(a)) * SS,
                        (CY + r0 * math.sin(a)) * SS
                    ),
                    (
                        (CX + r1 * math.cos(a)) * SS,
                        (CY + r1 * math.sin(a)) * SS
                    )
                ],
                fill=(
                    *soft,
                    120 if major else 50
                ),
                width=SS
            )

    base = Image.alpha_composite(
        base,
        _ss_layer(ticks)
    )

    base = Image.alpha_composite(
        base,
        holo
    )

    # AVATAR
    av = _prepare_avatar(
        avatar_bytes,
        R * 2,
        gray=th["gray"]
    )

    base.paste(
        av,
        (CX - R, CY - R),
        _circle_mask(R)
    )

    # AVATAR GLASS
    gl = Image.new(
        "RGBA",
        (R * 2, R * 2),
        (0, 0, 0, 0)
    )

    gd_ = ImageDraw.Draw(gl)

    for i in range(R):
        a = int(
            34 *
            (1 - i / R) ** 2
        )

        gd_.line(
            [(0, i), (R * 2, i)],
            fill=(255, 255, 255, a)
        )

    gl.putalpha(
        ImageChops.multiply(
            gl.getchannel("A"),
            _circle_mask(R)
        )
    )

    base.alpha_composite(
        gl,
        (CX - R, CY - R)
    )

    # ORBIT DOT
    ox = (
        CX +
        RO *
        math.cos(math.radians(dot_deg))
    )

    oy = (
        CY +
        RO *
        math.sin(math.radians(dot_deg))
    )

    def orbit(d):
        d.ellipse(
            [
                (ox - 10) * SS,
                (oy - 10) * SS,
                (ox + 10) * SS,
                (oy + 10) * SS
            ],
            fill=(*c1, 90)
        )

        d.ellipse(
            [
                (ox - 4.5) * SS,
                (oy - 4.5) * SS,
                (ox + 4.5) * SS,
                (oy + 4.5) * SS
            ],
            fill=(*WHITE, 255)
        )

    base = Image.alpha_composite(
        base,
        _ss_layer(orbit)
    )

    # BADGE
    bx = (
        CX +
        int(
            (R + 6) *
            math.cos(math.radians(45))
        )
    )

    by = (
        CY +
        int(
            (R + 6) *
            math.sin(math.radians(45))
        )
    )

    def badge(d):
        d.ellipse(
            [
                (bx - 23) * SS,
                (by - 23) * SS,
                (bx + 23) * SS,
                (by + 23) * SS
            ],
            fill=(*CARD_BG, 255)
        )

        d.ellipse(
            [
                (bx - 18) * SS,
                (by - 18) * SS,
                (bx + 18) * SS,
                (by + 18) * SS
            ],
            fill=(*c1, 255)
        )

        d.rounded_rectangle(
            [
                (bx - 8) * SS,
                (by - 1.5) * SS,
                (bx + 8) * SS,
                (by + 1.5) * SS
            ],
            radius=SS,
            fill=(*WHITE, 255)
        )

        if th["icon"] == "plus":
            d.rounded_rectangle(
                [
                    (bx - 1.5) * SS,
                    (by - 8) * SS,
                    (bx + 1.5) * SS,
                    (by + 8) * SS
                ],
                radius=SS,
                fill=(*WHITE, 255)
            )

    base = Image.alpha_composite(
        base,
        _ss_layer(badge)
    )

    # TEXT
    tmp = ImageDraw.Draw(
        Image.new(
            "RGBA",
            (1, 1)
        )
    )

    tl = Image.new(
        "RGBA",
        (W, H),
        (0, 0, 0, 0)
    )

    td = ImageDraw.Draw(tl)

    td.polygon(
        _hex_pts(
            TX0 + 11,
            50,
            11
        ),
        outline=(*c1, 255),
        width=2
    )

    td.polygon(
        _hex_pts(
            TX0 + 11,
            50,
            4
        ),
        fill=(*soft, 255)
    )

    td.text(
        (TX0 + 32, 50),
        "nanZ",
        font=_font(
            FONT_BOLD,
            18
        ),
        fill=(*WHITE, 255),
        anchor="lm"
    )

    # TAG + USERNAME
    ty = 108

    td.line(
        [
            (TX0, ty),
            (TX0 + 22, ty)
        ],
        fill=(*c1, 255),
        width=2
    )

    ex = _spaced(
        td,
        (TX0 + 32, ty),
        th["tag"],
        _font(
            FONT_MEDIUM,
            12
        ),
        (*soft, 255),
        spacing=4
    )

    if username:
        f_u = _font(
            FONT_REGULAR,
            12
        )

        handle = "@" + username

        while (
            len(handle) > 3
            and
            ex + 22 +
            tmp.textlength(
                handle,
                font=f_u
            ) > TX1
        ):
            handle = (
                handle[:-2] +
                "…"
            )

        td.ellipse(
            [
                ex + 8,
                ty - 2,
                ex + 12,
                ty + 2
            ],
            fill=(*MUTED, 200)
        )

        td.text(
            (ex + 22, ty),
            handle,
            font=f_u,
            fill=(*MUTED, 235),
            anchor="lm"
        )

    base = Image.alpha_composite(
        base,
        tl
    )

    # NAME
    f_name, nm = _fit_font(
        tmp,
        name,
        FONT_BOLD,
        52,
        TX1 - TX0,
        24
    )

    nmask = Image.new(
        "L",
        (W, H),
        0
    )

    ImageDraw.Draw(nmask).text(
        (TX0, 158),
        nm,
        font=f_name,
        fill=255,
        anchor="lm"
    )

    sh = Image.new(
        "RGBA",
        (W, H),
        (*c2, 0)
    )

    sh.putalpha(
        nmask.filter(
            ImageFilter.GaussianBlur(10)
        ).point(
            lambda v: int(v * 0.55)
        )
    )

    base = Image.alpha_composite(
        base,
        sh
    )

    nw = int(
        tmp.textlength(
            nm,
            font=f_name
        )
    )

    base.paste(
        _gradient_name(
            TX0,
            TX0 + max(nw, 120),
            WHITE,
            soft
        ),
        (0, 0),
        nmask
    )

    # BODY
    tl = Image.new(
        "RGBA",
        (W, H),
        (0, 0, 0, 0)
    )

    td = ImageDraw.Draw(tl)

    f_b, body = _fit_font(
        tmp,
        th["body"],
        FONT_REGULAR,
        15,
        TX1 - TX0,
        11
    )

    td.text(
        (TX0, 204),
        body,
        font=f_b,
        fill=(*WHITE, 205),
        anchor="lm"
    )

    # INFO
    f_s = _font(
        FONT_REGULAR,
        11
    )

    ly = 229

    if caption:
        td.ellipse(
            [
                TX0,
                ly - 2.5,
                TX0 + 5,
                ly + 2.5
            ],
            fill=(*soft, 255)
        )

        td.text(
            (TX0 + 12, ly),
            caption,
            font=f_s,
            fill=(*MUTED, 255),
            anchor="lm"
        )

    by_ = 245

    if welcome:
        ms, prog = _milestone(number)

        lab = (
            f"{fmt_num(number)} / "
            f"{fmt_num(ms)}"
        )

        td.text(
            (TX1, ly),
            lab,
            font=f_s,
            fill=(*soft, 255),
            anchor="rm"
        )

        bw = TX1 - TX0

        td.rounded_rectangle(
            [
                TX0,
                by_ - 3,
                TX1,
                by_ + 3
            ],
            radius=3,
            fill=(*soft, 40)
        )

        fw = max(
            8,
            int(bw * prog)
        )

        for x in range(
            TX0,
            TX0 + fw
        ):
            td.line(
                [
                    (x, by_ - 3),
                    (x, by_ + 3)
                ],
                fill=(
                    *_lerp(
                        c1,
                        soft,
                        (x - TX0) / bw
                    ),
                    255
                )
            )

        td.ellipse(
            [
                TX0 - 1,
                by_ - 3,
                TX0 + 5,
                by_ + 3
            ],
            fill=(*c1, 255)
        )

        tx = TX0 + fw

        td.ellipse(
            [
                tx - 6,
                by_ - 6,
                tx + 6,
                by_ + 6
            ],
            fill=(*soft, 70)
        )

        td.ellipse(
            [
                tx - 3.5,
                by_ - 3.5,
                tx + 3.5,
                by_ + 3.5
            ],
            fill=(*WHITE, 255)
        )

    else:
        for x in range(
            TX0,
            TX1 + 20
        ):
            f = 1 - (
                (x - TX0) /
                (TX1 + 20 - TX0)
            )

            td.line(
                [
                    (x, by_),
                    (x, by_ + 1)
                ],
                fill=(
                    *soft,
                    _clamp(120 * f)
                )
            )

    # PILLS
    cy = 288

    f_c = _font(
        FONT_MEDIUM,
        12
    )

    def pill(x, txt, col):
        w = int(
            td.textlength(
                txt,
                font=f_c
            )
        ) + 40

        td.rounded_rectangle(
            [
                x,
                cy - 15,
                x + w,
                cy + 15
            ],
            radius=15,
            fill=(*col, 40),
            outline=(*col, 200),
            width=1
        )

        td.ellipse(
            [
                x + 13,
                cy - 3.5,
                x + 20,
                cy + 3.5
            ],
            fill=(*col, 255)
        )

        td.text(
            (x + 28, cy),
            txt,
            font=f_c,
            fill=(*WHITE, 255),
            anchor="lm"
        )

        return x + w

    nx = pill(
        TX0,
        th["chip1"](
            fmt_num(number)
        ),
        c1
    )

    if date_text:
        pill(
            nx + 10,
            date_text,
            th["date_col"]
        )

    base = Image.alpha_composite(
        base,
        tl
    )

    # SCANLINES
    sc = Image.new(
        "RGBA",
        (W, H),
        (0, 0, 0, 0)
    )

    scd = ImageDraw.Draw(sc)

    for y in range(0, H, 3):
        scd.line(
            [(0, y), (W, y)],
            fill=(0, 0, 0, 14)
        )

    base = Image.alpha_composite(
        base,
        sc
    )

    # VIGNETTE
    vig = Image.new(
        "L",
        (W, H),
        0
    )

    ImageDraw.Draw(vig).ellipse(
        [-70, -60, W + 70, H + 60],
        fill=255
    )

    vig = vig.filter(
        ImageFilter.GaussianBlur(50)
    )

    dark = Image.new(
        "RGBA",
        (W, H),
        (6, 2, 20, 0)
    )

    dark.putalpha(
        ImageChops.invert(vig).point(
            lambda v: int(v * 0.55)
        )
    )

    base = Image.alpha_composite(
        base,
        dark
    )

    # GRAIN
    grain = Image.effect_noise(
        (W, H),
        38
    ).convert("RGBA")

    grain.putalpha(9)

    base = Image.alpha_composite(
        base,
        grain
    )

    # OUTPUT
    out = io.BytesIO()

    base.convert("RGB").save(
        out,
        format="PNG",
        optimize=True
    )

    return out.getvalue()


def _gradient_name(x0, x1, c1, c2):
    g = Image.new(
        "RGB",
        (W, H)
    )

    gd = ImageDraw.Draw(g)

    for x in range(W):
        t = min(
            1,
            max(
                0,
                (x - x0) /
                max(1, x1 - x0)
            )
        )

        gd.line(
            [(x, 0), (x, H)],
            fill=_lerp(
                c1,
                c2,
                t
            )
        )

    return g




# ══════════════════════════════════════════════
# HELPER GAMBAR 3D / KACA (sama dengan kartu Booster)
# ══════════════════════════════════════════════

# ══════════════════════════════════════════════
# DESAIN BARU — glass / 3D minimal / tema sekolah (gaya sama dengan kartu Booster)
# Layout: KARTU GELAP di kiri (avatar + ring progress member) dan KOLOM TERANG di kanan (teks).
# Watermark logo nanZ + tulisan "nanZ SERVER": posisi (52, 44) dan ukuran sama dengan kartu Booster.
# ══════════════════════════════════════════════

FONT_SANS = "fonts/Inter.ttf"                      # Inter (variable font)
FONT_SERIF = "fonts/InstrumentSerif-Italic.ttf"    # Instrument Serif Italic
LOGO_PATHS = ("assets/nanz_logo.png", "nanz_logo.png", "fonts/nanz_logo.png")

_SS = 1                      # render pada resolusi target untuk membatasi penggunaan RAM
_RENDER_LOCK = threading.Lock()
_RENDER_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nanz-entrance-render")
atexit.register(lambda: _RENDER_EXECUTOR.shutdown(wait=False, cancel_futures=True))
_STATIC_CACHE = {}           # layer statis per mode (tidak bergantung user)
_FRAME_CACHE = {}
_NOISE_CACHE = {}
RENDER_INFO = {"engine": None, "error": None}   # diisi tiap render (untuk debugging)

_CARD = (24, 24, 336, 316)   # kartu gelap (inset)
_AVC = (180, 198)            # pusat kartu pelajar
_AVS = 88                    # ukuran foto profil pada kartu pelajar
_RX, _RW = 372, 390          # kolom teks sisi terang: margin kiri & lebar
_BRAND_X, _BRAND_Y = 52, 44  # posisi watermark (sama dengan kartu Booster)

_GP = {
    "welcome": dict(
        base=(250, 251, 255),
        corner=[(0.0, 1.12, 150, (40, 135, 245)), (1.03, -0.08, 170, (165, 80, 235)),
                (0.50, 1.25, 140, (70, 205, 255))],
        ink=(8, 12, 52), ink2=(112, 56, 214), mute=(86, 88, 134),
        acc=(158, 72, 226), acc2=(36, 140, 242), glow=(130, 110, 250),
        sph=((34, 104, 226), (150, 214, 255)), bsph=((88, 40, 200), (214, 128, 250)),
        vig=(60, 56, 170), rule=(36, 140, 242),
        book=((36, 140, 242), (158, 72, 226)), cap=((88, 44, 206), (36, 140, 242)),
        pen=((70, 34, 190), (40, 142, 246)), nib=(228, 234, 250),
        stops=[(255, 255, 255), (70, 196, 255), (238, 242, 255), (196, 112, 245), (255, 255, 255), (60, 150, 245)],
        dk0=(5, 4, 26), dk1=(24, 14, 74), dglow=(124, 104, 255), dsh=(30, 20, 110),
        dtxt=(232, 228, 255), dgrid=(190, 180, 255), dgk=1.0,
    ),
    "leave": dict(
        base=(254, 249, 251),
        corner=[(0.0, 1.12, 150, (255, 120, 160)), (1.03, -0.08, 170, (180, 90, 230)),
                (0.50, 1.25, 140, (255, 170, 190))],
        ink=(48, 12, 38), ink2=(190, 50, 120), mute=(130, 92, 116),
        acc=(214, 62, 128), acc2=(255, 120, 160), glow=(255, 130, 170),
        sph=((214, 60, 120), (255, 196, 214)), bsph=((150, 30, 90), (255, 120, 160)),
        vig=(150, 60, 110), rule=(230, 90, 140),
        book=((255, 120, 160), (214, 62, 128)), cap=((170, 40, 100), (255, 120, 160)),
        pen=((140, 30, 100), (255, 140, 170)), nib=(255, 226, 236),
        stops=[(255, 255, 255), (255, 140, 170), (255, 238, 244), (214, 62, 128), (255, 255, 255), (190, 110, 235)],
        dk0=(16, 4, 18), dk1=(56, 12, 44), dglow=(255, 110, 160), dsh=(90, 20, 60),
        dtxt=(255, 232, 242), dgrid=(255, 190, 214), dgk=0.9,
    ),
}

_NEW_TEXT = {
    "welcome": dict(tag="WELCOME", stamp="DITERIMA", role="MURID BARU", hello="Selamat datang,",
                    chip=lambda n: f"Member ke-{n}"),
    "leave": dict(tag="GOODBYE", stamp="ALUMNI", role="ALUMNI", hello="Sampai jumpa,",
                  chip=lambda n: f"Sisa {n} member"),
}




def _sc(v):
    return int(round(v * _SS))


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


@lru_cache(maxsize=1)
def _glogo_raw():
    for p in LOGO_PATHS:
        try:
            im = Image.open(p).convert("RGBA")
            bb = im.getchannel("A").getbbox()
            return im.crop(bb) if bb else im
        except Exception:
            continue
    print("[Entrance] Logo nanZ tidak ditemukan; kartu dibuat tanpa logo. Cek LOGO_PATHS.")
    return None


def _gclean(name, font, fallback=""):
    """Buang karakter yang tidak ada di font (emoji, CJK, dsb) agar tidak muncul kotak 'NO GLYPH'."""
    try:
        notdef = _gglyph(font, "\U0010FFFF")
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
    return clean or fallback


def _gbackground_e(P):
    w, h = W * _SS, H * _SS
    img = Image.new("RGBA", (w, h), (*P["base"], 255))
    for fx, fy, r, c in P["corner"]:
        m = Image.new("L", (w, h), 0)
        x, y, R = fx * w, fy * h, _sc(r)
        ImageDraw.Draw(m).ellipse([x - R, y - R, x + R, y + R], fill=150)
        img.paste(Image.new("RGBA", (w, h), (*c, 255)), (0, 0), m.filter(ImageFilter.GaussianBlur(R * 0.38)))
    ov = _gl(w, h)
    d = ImageDraw.Draw(ov)
    for y in range(30, H - 14, 22):              # garis buku tulis (motif sekolah)
        for x in range(346, 790, 2):
            a = int(40 * max(0, 1 - (x - 346) / 444) ** 1.3)
            if a > 0:
                d.line([(_sc(x), _sc(y)), (_sc(x + 2), _sc(y))], fill=(*P["rule"], a), width=_SS)
    d.line([(_sc(358), _sc(12)), (_sc(358), _sc(H - 12))], fill=(240, 120, 200, 46), width=_SS)
    return Image.alpha_composite(img, ov)


def _gcard_dark(img, P):
    """Kartu gelap inset: gradien dalam + glow + grid titik + bintang, dengan border gradien & bayangan."""
    w, h = img.size
    m = _grrmask(w, h, _CARD, 28)
    sh = _gl(w, h)
    sh.paste((*P["dsh"], 150), (0, _sc(12)), m)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(14))))
    lip = _gl(w, h)                                   # ketebalan kartu (efek 3D)
    lip.paste((*tuple(int(c * 0.45) for c in P["acc"]), 255), (0, _sc(6)), m)
    img.alpha_composite(lip)

    g = Image.linear_gradient("L").resize((w, h))
    body = Image.composite(Image.new("RGBA", (w, h), (*P["dk1"], 255)), Image.new("RGBA", (w, h), (*P["dk0"], 255)), g)
    for gx, gy, r, col, a in ((_AVC[0], _AVC[1], 150, P["dglow"], 150), (30, 30, 120, P["acc2"], 55),
                              (320, 335, 110, P["acc"], 55)):
        gm = Image.new("L", (w, h), 0)
        ImageDraw.Draw(gm).ellipse([_sc(gx - r), _sc(gy - r), _sc(gx + r), _sc(gy + r)], fill=int(a * P["dgk"]))
        body.paste(Image.new("RGBA", (w, h), (*col, 255)), (0, 0), gm.filter(ImageFilter.GaussianBlur(_sc(r * 0.45))))
    dots = _gl(w, h)
    dd = ImageDraw.Draw(dots)
    for yy in range(30, 316, 14):                # grid titik = kertas berpetak
        for xx in range(30, 336, 14):
            dd.ellipse([_sc(xx - 0.9), _sc(yy - 0.9), _sc(xx + 0.9), _sc(yy + 0.9)], fill=(*P["dgrid"], 40))
    body.alpha_composite(dots)
    img.paste(body, (0, 0), m)

    # border gradien + highlight tipis
    x0, y0, x1, y1 = _CARD
    i = _grrmask(w, h, (x0 + 1.8, y0 + 1.8, x1 - 1.8, y1 - 1.8), 26.2)
    bd = _ghgrad(w, h, P["acc2"], P["acc"])
    bd.putalpha(ImageChops.subtract(m, i).point(lambda v: v * 175 // 255))
    img.alpha_composite(bd)
    o2 = _grrmask(w, h, (x0 + 2.6, y0 + 2.6, x1 - 2.6, y1 - 2.6), 25.4)
    i2 = _grrmask(w, h, (x0 + 3.6, y0 + 3.6, x1 - 3.6, y1 - 3.6), 24.4)
    hl = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    hl.putalpha(ImageChops.subtract(o2, i2).point(lambda v: v * 60 // 255))
    img.alpha_composite(hl)

    # bintang kecil + bokeh di dalam kartu
    rng = random.Random(9)
    l = _gl(w, h)
    d = ImageDraw.Draw(l)
    for _ in range(40):
        x, y = rng.uniform(34, 326), rng.uniform(34, 306)
        r = rng.choice([0.7, 0.9, 1.1, 1.4])
        d.ellipse([_sc(x - r), _sc(y - r), _sc(x + r), _sc(y + r)], fill=(255, 255, 255, rng.randint(70, 190)))
    for _ in range(9):
        x, y = rng.uniform(40, 320), rng.uniform(40, 300)
        r = rng.choice([2, 2.5, 3, 4, 6])
        a = rng.randint(50, 110)
        col = rng.choice([(255, 255, 255), P["dglow"], P["acc2"]])
        d.ellipse([_sc(x - r), _sc(y - r), _sc(x + r), _sc(y + r)], fill=(*col, a))
        if r >= 4:
            d.ellipse([_sc(x - r), _sc(y - r), _sc(x + r), _sc(y + r)], outline=(255, 255, 255, min(180, a + 60)), width=_SS)
    img.alpha_composite(l.filter(ImageFilter.GaussianBlur(0.8)))


def _gbrand_dark(img, x, cy, P):
    """Watermark kecil: logo nanZ + tulisan 'nanZ SERVER' (varian untuk latar gelap; ukuran sama dengan Booster)."""
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


def _gstamp(img, cx, cy, P, text, rot):
    """Stempel karet (tema sekolah) dengan tekstur sedikit aus."""
    n = _sc(84)
    L = _gl(n, n)
    d = ImageDraw.Draw(L)
    c = n // 2
    col = (*P["acc"], 215)
    d.ellipse([c - _sc(35), c - _sc(35), c + _sc(35), c + _sc(35)], outline=col, width=_sc(2.2))
    d.ellipse([c - _sc(30), c - _sc(30), c + _sc(30), c + _sc(30)], outline=col, width=_SS)
    f = _gsans(9.5, 700)
    x = c - (sum(f.getlength(ch) for ch in text) + _sc(1.2) * (len(text) - 1)) / 2
    for ch in text:
        d.text((x, c), ch, font=f, fill=col, anchor="lm")
        x += f.getlength(ch) + _sc(1.2)
    for yy in (c - _sc(15), c + _sc(15)):
        d.polygon([(c + _sc(a_), yy + _sc(b_)) for a_, b_ in
                   [(0, -4), (1, -1), (4, 0), (1, 1), (0, 4), (-1, 1), (-4, 0), (-1, -1)]], fill=col)
    wear = Image.effect_noise((n, n), 90).point(lambda v: 255 if v > 80 else 120)
    L.putalpha(ImageChops.multiply(L.getchannel("A"), wear))
    L = L.rotate(-rot, resample=Image.BICUBIC)
    img.alpha_composite(L, (_sc(cx) - n // 2, _sc(cy) - n // 2))


def _gavatar_sq(avatar_bytes, size, gray, radius):
    im = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    m = min(im.size)
    l, t = (im.width - m) // 2, (im.height - m) // 2
    im = im.crop((l, t, l + m, t + m))
    if gray:
        a = im.getchannel("A")
        rgb = ImageEnhance.Brightness(ImageEnhance.Color(im.convert("RGB")).enhance(0.25)).enhance(0.9)
        im = rgb.convert("RGBA")
        im.putalpha(a)
    im = im.resize((size, size), Image.LANCZOS)
    mk = Image.new("L", (size * 2, size * 2), 0)
    ImageDraw.Draw(mk).rounded_rectangle((0, 0, size * 2 - 1, size * 2 - 1), radius=radius * 2, fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mk.resize((size, size), Image.LANCZOS))
    return out


def _gtape(L, cx, cy, ang, P, c):
    """Selotip washi (dekorasi sudut foto)."""
    n = _sc(44)
    t = _gl(n, n)
    d = ImageDraw.Draw(t)
    box = [n // 2 - _sc(15), n // 2 - _sc(5), n // 2 + _sc(15), n // 2 + _sc(5)]
    d.rectangle(box, fill=(*c, 175))
    for k in range(-4, 5):
        x = n // 2 + k * _sc(4)
        d.line([(x, box[1]), (x - _sc(3), box[3])], fill=(255, 255, 255, 120), width=_SS)
    d.line([(box[0], box[1]), (box[2], box[1])], fill=(255, 255, 255, 140), width=_SS)
    t = t.rotate(ang, resample=Image.BICUBIC)
    L.alpha_composite(t, (_sc(cx) - n // 2, _sc(cy) - n // 2))


def _gpersp_coeffs(dst, src):
    A, B = [], []
    for (x, y), (X, Y) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -X * x, -X * y])
        A.append([0, 0, 0, x, y, 1, -Y * x, -Y * y])
        B += [X, Y]
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def _gwarp(layer, src, dst, box):
    """Transformasi perspektif pada crop kecil (agar cepat), lalu ditempel kembali ke kanvas penuh."""
    crop = layer.crop(box)
    s_ = [(a - box[0], b - box[1]) for a, b in src]
    d_ = [(a - box[0], b - box[1]) for a, b in dst]
    out = crop.transform(crop.size, Image.PERSPECTIVE, _gpersp_coeffs(d_, s_), Image.BICUBIC)
    full = _gl(*layer.size)
    full.paste(out, (box[0], box[1]))
    return full


def _gicon_text(img, cx, cy, size, rot, text):
    n = _sc(size * 1.4)
    t = _gl(n, n)
    d = ImageDraw.Draw(t)
    f = _gsans(size * 0.44, 700)
    d.text((n // 2, n // 2 + _sc(1.4)), text, font=f, fill=(20, 10, 70, 90), anchor="mm")
    d.text((n // 2, n // 2), text, font=f, fill=(255, 255, 255, 255), anchor="mm")
    t = t.rotate(rot, resample=Image.BICUBIC)
    img.alpha_composite(t, (_sc(cx) - n // 2, _sc(cy) - n // 2))


def _gid_card(img, P, key, avatar_bytes, number):
    """Profil sebagai KARTU PELAJAR 3D: lanyard + klip logam, perspektif, ketebalan, kilap, foto ber-selotip."""
    w, h = img.size
    welcome = key == "welcome"
    T = _NEW_TEXT[key]
    cx, cy = _AVC
    CW, CH = 152, 208
    x0, y0 = cx - CW / 2, cy - CH / 2
    m = _grrmask(w, h, (x0, y0, x0 + CW, y0 + CH), 14)

    # ── isi kartu ──
    L = _gl(w, h)
    g = Image.linear_gradient("L").resize((w, h))
    body = Image.composite(Image.new("RGBA", (w, h), (232, 238, 255, 255)), Image.new("RGBA", (w, h), (255, 255, 255, 255)), g)
    L.paste(body, (0, 0), m)
    rl = _gl(w, h)
    rd = ImageDraw.Draw(rl)
    for yy in range(int(y0 + 52), int(y0 + CH - 6), 9):
        rd.line([(_sc(x0 + 8), _sc(yy)), (_sc(x0 + CW - 8), _sc(yy))], fill=(*P["rule"], 26), width=_SS)
    rl.putalpha(ImageChops.multiply(rl.getchannel("A"), m))
    L.alpha_composite(rl)

    band = Image.new("L", (w, h), 0)
    ImageDraw.Draw(band).rectangle([0, _sc(y0), w, _sc(y0 + 40)], fill=255)
    band = ImageChops.multiply(band, m)
    L.paste(_ghgrad(w, h, P["acc"], P["acc2"]), (0, 0), band)
    hl = _gl(w, h)
    ImageDraw.Draw(hl).rectangle([0, _sc(y0), w, _sc(y0 + 17)], fill=(255, 255, 255, 34))
    hl.putalpha(ImageChops.multiply(hl.getchannel("A"), band))
    L.alpha_composite(hl)
    d = ImageDraw.Draw(L)
    lg = _glogo(_sc(15))
    ft = _gsans(9.5, 700)
    label = "MURID nanZ" if welcome else "ALUMNI nanZ"
    tw = sum(ft.getlength(ch) for ch in label) + _sc(1.4) * (len(label) - 1)
    total = tw + (lg.width + _sc(5) if lg is not None else 0)
    sx = _sc(cx) - total / 2
    ty = _sc(y0 + 29)
    if lg is not None:
        L.alpha_composite(lg, (int(sx), ty - lg.height // 2))
        sx += lg.width + _sc(5)
    for ch in label:
        d.text((sx, ty), ch, font=ft, fill=(255, 255, 255, 255), anchor="lm")
        sx += ft.getlength(ch) + _sc(1.4)

    PS = _AVS
    px0, py0 = cx - PS / 2, y0 + 52
    fm = _grrmask(w, h, (px0 - 3.5, py0 - 3.5, px0 + PS + 3.5, py0 + PS + 3.5), 15)
    fs = _gl(w, h)
    fs.paste((20, 20, 70, 120), (0, _sc(4)), fm)
    L.alpha_composite(fs.filter(ImageFilter.GaussianBlur(_sc(4))))
    L.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0), fm)
    fi = _grrmask(w, h, (px0 - 2, py0 - 2, px0 + PS + 2, py0 + PS + 2), 13.5)
    fb = _ghgrad(w, h, P["acc2"], P["acc"])
    fb.putalpha(ImageChops.subtract(fm, fi))
    L.alpha_composite(fb)
    L.alpha_composite(_gavatar_sq(avatar_bytes, _sc(PS), not welcome, 12.5), (_sc(px0), _sc(py0)))
    # kilap kaca pada foto
    gl_ = _gl(w, h)
    ImageDraw.Draw(gl_).polygon([(_sc(px0), _sc(py0)), (_sc(px0 + PS * 0.55), _sc(py0)), (_sc(px0), _sc(py0 + PS * 0.55))],
                                fill=(255, 255, 255, 46))
    gl_.putalpha(ImageChops.multiply(gl_.getchannel("A"), _grrmask(w, h, (px0, py0, px0 + PS, py0 + PS), 12.5)))
    L.alpha_composite(gl_)
    _gtape(L, px0 + 3, py0 + 1, 38, P, P["acc2"])
    _gtape(L, px0 + PS - 3, py0 + 1, -38, P, P["acc"])

    d = ImageDraw.Draw(L)
    fr = _gsans(8.5, 700)
    role = T["role"]
    rw = sum(fr.getlength(ch) for ch in role) + _sc(1.8) * (len(role) - 1)
    rx = _sc(cx) - rw / 2
    for ch in role:
        d.text((rx, _sc(py0 + PS + 17)), ch, font=fr, fill=(*P["acc"], 255), anchor="lm")
        rx += fr.getlength(ch) + _sc(1.8)
    val = f"No. {fmt_num(number)}" if welcome else f"Sisa {fmt_num(number)}"
    d.text((_sc(cx), _sc(py0 + PS + 33)), val, font=_gsans(14, 700), fill=(*P["ink"], 255), anchor="mm")
    rng = random.Random(number * 7 + 3)
    bx, by0 = cx - 46, y0 + CH - 24
    while bx < cx + 46:
        bw = rng.choice([1, 1, 1.6, 2.2])
        d.rectangle([_sc(bx), _sc(by0), _sc(bx + bw), _sc(by0 + 14)], fill=(*P["ink"], 225))
        bx += bw + rng.choice([1.2, 1.6, 2.2])
    mi = _grrmask(w, h, (x0 + 1.5, y0 + 1.5, x0 + CW - 1.5, y0 + CH - 1.5), 12.5)
    bd = _ghgrad(w, h, P["acc2"], P["acc"])
    bd.putalpha(ImageChops.subtract(m, mi).point(lambda v: v * 215 // 255))
    L.alpha_composite(bd)

    # ── lanyard (tali) ──
    S = _gl(w, h)
    ax, ay, bx_, by_ = cx + 34, -8, cx + 2, y0 - 4
    dx, dy = bx_ - ax, by_ - ay
    ln = math.hypot(dx, dy)
    nx, ny = dy / ln, -dx / ln
    hw = 9.0
    def strap_poly(o0, o1):
        return [(_sc(ax + nx * o0), _sc(ay + ny * o0)), (_sc(ax + nx * o1), _sc(ay + ny * o1)),
                (_sc(bx_ + nx * o1), _sc(by_ + ny * o1)), (_sc(bx_ + nx * o0), _sc(by_ + ny * o0))]
    sm = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sm).polygon(strap_poly(-hw, hw), fill=255)
    vg = Image.linear_gradient("L").resize((w, h))
    sg = Image.composite(Image.new("RGBA", (w, h), (*P["acc"], 255)), Image.new("RGBA", (w, h), (*P["acc2"], 255)), vg)
    S.paste(sg, (0, 0), sm)
    sd_ = ImageDraw.Draw(S)
    sd_.polygon(strap_poly(-hw, -hw * 0.35), fill=(255, 255, 255, 70))
    sd_.polygon(strap_poly(hw * 0.55, hw), fill=(0, 0, 40, 70))
    for t in range(0, int(ln) - 4, 6):
        u0, u1 = t / ln, (t + 3) / ln
        sd_.line([(_sc(ax + dx * u0), _sc(ay + dy * u0)), (_sc(ax + dx * u1), _sc(ay + dy * u1))],
                 fill=(255, 255, 255, 190), width=_SS)
    se = ImageChops.subtract(sm, sm.filter(ImageFilter.MinFilter(_SS * 2 + 1)))
    S.paste(Image.new("RGBA", (w, h), (255, 255, 255, 110)), (0, 0), se)

    # ── klip logam ──
    C = _gl(w, h)
    cbox = (cx - 11, y0 - 10, cx + 11, y0 + 10)
    cm = _grrmask(w, h, cbox, 5)
    cs = _gl(w, h)
    cs.paste((0, 0, 30, 120), (0, _sc(3)), cm)
    C.alpha_composite(cs.filter(ImageFilter.GaussianBlur(_sc(3))))
    cg = Image.composite(Image.new("RGBA", (w, h), (150, 158, 186, 255)), Image.new("RGBA", (w, h), (248, 250, 255, 255)), vg)
    C.paste(cg, (0, 0), cm)
    cd = ImageDraw.Draw(C)
    cd.rounded_rectangle([_sc(cx - 6.5), _sc(y0 + 1.5), _sc(cx + 6.5), _sc(y0 + 6.5)], radius=_sc(2.5), fill=(26, 22, 66, 255))
    cd.line([(_sc(cx - 8), _sc(y0 - 6)), (_sc(cx + 8), _sc(y0 - 6))], fill=(255, 255, 255, 200), width=_SS)
    ce = ImageChops.subtract(cm, cm.filter(ImageFilter.MinFilter(_SS * 2 + 1)))
    C.paste(Image.new("RGBA", (w, h), (255, 255, 255, 190)), (0, 0), ce)

    # ── perspektif (sisi kanan menjauh) + sedikit miring ──
    ML = _gl(w, h)
    ML.paste((255, 255, 255, 255), (0, 0), m)
    sq, kk, ang = 7, 9, -3.0
    th = math.radians(ang)
    co, si = math.cos(th), math.sin(th)
    quad = [(x0, y0), (x0 + CW - sq, y0 + kk), (x0 + CW - sq, y0 + CH - kk), (x0, y0 + CH)]
    dst = [(_sc(cx + (x - cx) * co - (y - cy) * si), _sc(cy + (x - cx) * si + (y - cy) * co)) for x, y in quad]
    src = [(_sc(x0), _sc(y0)), (_sc(x0 + CW), _sc(y0)), (_sc(x0 + CW), _sc(y0 + CH)), (_sc(x0), _sc(y0 + CH))]
    box = (_sc(50), 0, _sc(310), _sc(H))
    Sw, Lw, Cw, Mw = (_gwarp(x, src, dst, box) for x in (S, L, C, ML))
    A = Mw.getchannel("A")

    img.alpha_composite(Sw)
    sh = _gl(w, h)
    sh.paste((0, 0, 0, 185), (0, _sc(12)), A)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(11))))
    gw = _gl(w, h)
    gw.paste((*P["dglow"], 120), (0, 0), A)
    img.alpha_composite(gw.filter(ImageFilter.GaussianBlur(_sc(11))))
    side = tuple(int(c * 0.42) for c in P["acc"])
    ext = _gl(w, h)
    for i in range(8, 0, -1):                           # ketebalan kartu
        col = _lerp3(side, tuple(int(c * 0.6) for c in side), i / 8)
        ext.paste((*col, 255), (_sc(i * 0.7), _sc(i * 0.95)), A)
    img.alpha_composite(ext)
    img.alpha_composite(Lw)
    # kilap diagonal + tepi terang
    gs = _gl(w, h)
    ImageDraw.Draw(gs).polygon([(_sc(x0 + CW * 0.30), _sc(y0 - 10)), (_sc(x0 + CW * 0.62), _sc(y0 - 10)),
                                (_sc(x0 + CW * 0.28), _sc(y0 + CH + 10)), (_sc(x0 - CW * 0.04), _sc(y0 + CH + 10))],
                               fill=(255, 255, 255, 62))
    gs = gs.filter(ImageFilter.GaussianBlur(_sc(5)))
    gs.putalpha(ImageChops.multiply(gs.getchannel("A"), A))
    img.alpha_composite(gs)
    edge = ImageChops.subtract(A, A.filter(ImageFilter.MinFilter(_SS * 2 + 1)))
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 150)), (0, 0), edge)
    img.alpha_composite(Cw)


def _gbar3d(img, P, x0, x1, yc, prog):
    """Progress bar berbentuk tabung kaca dengan knob bola 3D (prog=None -> garis memudar untuk Leave)."""
    w, h = img.size
    th = 11
    tm = _grrmask(w, h, (x0, yc - th / 2, x1, yc + th / 2), th / 2)
    L = _gl(w, h)
    L.paste((*P["acc2"], 44), (0, 0), tm)
    rim = ImageChops.subtract(tm, ImageChops.offset(tm, 0, _sc(2.4)))
    L.paste((*P["acc"], 60), (0, 0), rim)
    low = ImageChops.subtract(tm, ImageChops.offset(tm, 0, -_sc(1.6)))
    L.paste((255, 255, 255, 190), (0, 0), low)
    img.alpha_composite(L)
    fade = prog is None
    if fade:
        prog = 1.0
    fw = max(th, (x1 - x0) * prog)
    fm = _grrmask(w, h, (x0, yc - th / 2, x0 + fw, yc + th / 2), th / 2)
    sh = _gl(w, h)
    sh.paste((*P["acc"], 130), (0, _sc(3)), fm)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(4))))
    fl = _gl(w, h)
    fd = ImageDraw.Draw(fl)
    for x in range(_sc(x0), _sc(x0 + fw)):
        fd.line([(x, _sc(yc - th / 2)), (x, _sc(yc + th / 2))],
                fill=(*_lerp3(P["acc2"], P["acc"], (x - _sc(x0)) / _sc(x1 - x0)), 255))
    fd.rectangle([_sc(x0), _sc(yc - th / 2), _sc(x0 + fw), _sc(yc - 1.5)], fill=(255, 255, 255, 62))
    fd.rectangle([_sc(x0), _sc(yc + th * 0.22), _sc(x0 + fw), _sc(yc + th / 2)], fill=(0, 0, 40, 55))
    fl.putalpha(ImageChops.multiply(fl.getchannel("A"), fm))
    if fade:                                           # Leave: tabung berwarna yang memudar ke kanan
        fgm = Image.new("L", (w, h), 0)
        fgd = ImageDraw.Draw(fgm)
        for x in range(_sc(x0), _sc(x1)):
            fgd.line([(x, 0), (x, h)], fill=_clamp(255 * (1 - (x - _sc(x0)) / _sc(x1 - x0)) ** 0.8 + 10))
        fl.putalpha(ImageChops.multiply(fl.getchannel("A"), fgm))
        img.alpha_composite(fl)
        return
    img.alpha_composite(fl)
    img.paste(Image.new("RGBA", (w, h), (255, 255, 255, 150)), (0, 0), ImageChops.subtract(fm, fm.filter(ImageFilter.MinFilter(_SS * 2 + 1))))
    _gput_sphere(img, x0 + fw, yc, 8.5, P, key="bsph")
    ImageDraw.Draw(img).ellipse([_sc(x0 + fw - 3), _sc(yc - 3), _sc(x0 + fw + 3), _sc(yc + 3)], fill=(255, 255, 255, 235))


def _gstatic_layer(key):
    """Semua elemen yang TIDAK bergantung pada user (di-cache per mode)."""
    if key in _STATIC_CACHE:
        return _STATIC_CACHE[key]
    P, T = _GP[key], _NEW_TEXT[key]
    img = _gbackground_e(P)
    w, h = img.size
    cx, cy = _AVC
    _gvignette(img, P)
    _gcard_dark(img, P)
    _ghexagon(img, cx, cy, 132, P["dgrid"], 40)
    _ghexagon(img, cx, cy, 114, P["acc2"], 80, 1.0)
    _gribbon(img, P, 318)
    _gglass_ruler(img, 690, 46, 130, 25, -8, P)
    _gglass_tile(img, 302, 128, 44, 12, P, dark=True)
    _gicon_book(img, 302, 128, 44, 12, P)
    _gglass_tile(img, 58, 268, 40, -10, P, dark=True)
    _gicon_cap(img, 58, 268, 40, -10, P)
    _gglass_tile(img, 60, 142, 38, -9, P, dark=True)
    _gicon_text(img, 60, 142, 38, -9, "A+")
    _gput_sphere(img, 300, 204, 5.5, P, key="bsph")
    _gput_sphere(img, 303, 272, 7, P, key="bsph")
    _gput_sphere(img, 46, 212, 4, P, key="bsph")
    _gput_sphere(img, 356, 262, 4, P)
    _gput_sphere(img, 752, 214, 4, P)
    _gput_pen(img, 758, 300, 84, 11.5, 225, P)
    _gstamp(img, 716, 98, P, T["stamp"], -14)

    sh = _gl(w, h)
    ImageDraw.Draw(sh).ellipse([_sc(cx - 92), _sc(cy - 70), _sc(cx + 92), _sc(cy + 120)], fill=(*P["dglow"], 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(_sc(26))))

    _gbrand_dark(img, _BRAND_X, _BRAND_Y, P)

    # ── teks statis kolom terang ──
    fp = _gsans(13, 700)
    pw = fp.getlength(T["tag"]) / _SS + 50
    px, pcy = _RX, 50
    lipm = _grrmask(w, h, (px, pcy - 16 + 3.5, px + pw, pcy + 16 + 3.5), 16)
    lp = _gl(w, h)
    lp.paste((*tuple(int(c * 0.5) for c in P["acc"]), 255), (0, 0), lipm)
    img.alpha_composite(lp)
    _gfoil_pill(img, (px, pcy - 16, px + pw, pcy + 16), P)
    d = ImageDraw.Draw(img)
    d.polygon([(_sc(a), _sc(b)) for a, b in _gsparkle(px + 22, pcy, 6.5)], fill=(255, 255, 255, 255))
    d.text((_sc(px + 37), _sc(pcy)), T["tag"], font=fp, fill=(255, 255, 255, 255), anchor="lm")
    fh = _gserif(44)
    d.text((_sc(_RX), _sc(112)), T["hello"], font=fh, fill=(*P["ink2"], 255), anchor="lm")

    ul = _gl(w, h)
    u = ImageDraw.Draw(ul)
    x0, x1 = _RX + 12, _RX + 230
    for x in range(_sc(x0), _sc(x1)):
        t = (x - _sc(x0)) / _sc(x1 - x0)
        u.line([(x, _sc(222)), (x, _sc(222.9))], fill=(*_lerp3(P["acc"], P["acc2"], t), int(255 * (1 - t) ** 0.8)))
    dm = 7
    u.polygon([(_sc(_RX + 3.5), _sc(222.4 - dm / 1.4)), (_sc(_RX + 3.5 + dm / 1.4), _sc(222.4)),
               (_sc(_RX + 3.5), _sc(222.4 + dm / 1.4)), (_sc(_RX + 3.5 - dm / 1.4), _sc(222.4))],
              fill=(*P["acc"], 255), outline=(255, 255, 255, 255))
    img.alpha_composite(ul)
    _STATIC_CACHE[key] = img
    return img


def _gavatar_in(avatar_bytes, size, gray):
    im = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    m = min(im.size)
    l, t = (im.width - m) // 2, (im.height - m) // 2
    im = im.crop((l, t, l + m, t + m))
    if gray:
        a = im.getchannel("A")
        rgb = ImageEnhance.Brightness(ImageEnhance.Color(im.convert("RGB")).enhance(0.25)).enhance(0.9)
        im = rgb.convert("RGBA")
        im.putalpha(a)
    im = im.resize((size, size), Image.LANCZOS)
    mk = Image.new("L", (size * 2, size * 2), 0)
    ImageDraw.Draw(mk).ellipse((0, 0, size * 2 - 1, size * 2 - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mk.resize((size, size), Image.LANCZOS))
    return out


def _render_entrance_v2(avatar_bytes, name, mode, number, date_text, username, caption):
    key = mode if mode in _GP else "welcome"
    P, T = _GP[key], _NEW_TEXT[key]
    welcome = key == "welcome"
    with _RENDER_LOCK:
        img = _gstatic_layer(key).copy()
        w, h = img.size
        cx, cy = _AVC

        # ── profil: kartu pelajar ──
        _gid_card(img, P, key, avatar_bytes, number)
        d = ImageDraw.Draw(img)
        for sx, sy, sz in ((cx + 80, cy - 100, 6), (cx - 84, cy + 96, 5), (cx + 88, cy + 70, 4)):
            d.polygon([(_sc(a), _sc(b)) for a, b in _gsparkle(sx, sy, sz)], fill=(255, 255, 255, 240))

        # ── tag + username (kanan pill) ──
        fp = _gsans(13, 700)
        pw = fp.getlength(T["tag"]) / _SS + 50
        user = _gclean(username, _gsans(12, 500), "")
        if user:
            fu = _gsans(12, 500)
            handle = "@" + user
            ux = _RX + pw + 24
            while len(handle) > 3 and ux + fu.getlength(handle) / _SS > 614:
                handle = handle[:-2] + "…"
            d.ellipse([_sc(_RX + pw + 11), _sc(48), _sc(_RX + pw + 15), _sc(52)], fill=(*P["mute"], 200))
            d.text((_sc(ux), _sc(50)), handle, font=fu, fill=(*P["mute"], 255), anchor="lm")

        # ── nama ──
        clean = _gclean(name, _gsans(46, 700), "Member")
        fn, nm = _gfit(clean, 60, _RW - 14, 700)
        _gdraw_name(img, P, nm, fn, _RX, 170)

        # ── caption + progress ──
        ly, by_ = 250, 270
        d = ImageDraw.Draw(img)
        fs = _gsans(11.5, 500)
        cap = _gclean(caption, fs, "")
        if cap:
            d.ellipse([_sc(_RX), _sc(ly - 2.5), _sc(_RX + 5), _sc(ly + 2.5)], fill=(*P["acc2"], 255))
            d.text((_sc(_RX + 12), _sc(ly)), cap, font=fs, fill=(*P["mute"], 255), anchor="lm")
        if welcome:
            ms, prog = _milestone(number)
            lab = f"{fmt_num(number)} / {fmt_num(ms)}"
            d.text((_sc(_RX + _RW), _sc(ly)), lab, font=_gsans(11.5, 700), fill=(*P["acc"], 255), anchor="rm")
            _gbar3d(img, P, _RX, _RX + _RW, by_, prog)
        else:
            _gbar3d(img, P, _RX, _RX + _RW, by_, None)

        # ── pills ──
        fc = _gsans(12.5, 600)
        x, cy2 = _RX, 304
        pills = [(T["chip"](fmt_num(number)), P["acc2"])]
        if date_text:
            pills.append((date_text, P["acc"]))
        for txt, col in pills:
            cw = fc.getlength(txt) / _SS + 44
            lm_ = _grrmask(w, h, (x, cy2 - 15 + 3.5, x + cw, cy2 + 15 + 3.5), 15)
            lp_ = _gl(w, h)
            lp_.paste((*tuple(int(c * 0.55) for c in P["acc"]), 150), (0, 0), lm_)
            img.alpha_composite(lp_)
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


def render_entrance_card(
    avatar_bytes: bytes,
    name: str,
    mode: str = "welcome",
    number: int = 0,
    date_text: str = "",
    username: str = "",
    caption: str = "",
) -> bytes:
    """Entry point (dipakai cog). Mengembalikan bytes PNG 800x340."""
    if np is None:
        RENDER_INFO.update(engine="legacy", error="numpy belum terpasang (pip install numpy)")
        print("[Entrance] numpy belum terpasang (pip install numpy); memakai desain lama.")
        return _render_entrance_legacy(avatar_bytes, name, mode, number, date_text, username, caption)
    try:
        png = _render_entrance_v2(avatar_bytes, name, mode, number, date_text, username, caption)
        RENDER_INFO.update(engine="v2", error=None)
        return png
    except Exception as e:
        # Jangan sampai welcome/leave gagal terkirim: kembali ke desain lama.
        RENDER_INFO.update(engine="legacy", error=repr(e))
        print(f"[Entrance] Desain baru gagal ({e!r}); memakai desain lama.")
        return _render_entrance_legacy(avatar_bytes, name, mode, number, date_text, username, caption)


# ══════════════════════════════════════════════
# ENTRANCE COG
# ══════════════════════════════════════════════

class Entrance(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        print(
            "[Entrance] Cog berhasil diinisialisasi."
        )

    async def _warn_legacy(self, ctx):
        """Dipakai command test: beri tahu kalau kartu dibuat dengan desain lama (dan alasannya)."""
        if RENDER_INFO.get("engine") == "legacy":
            await ctx.send(
                "⚠️ Kartu dibuat dengan **desain lama**. "
                f"Alasan: `{RENDER_INFO.get('error')}`"
            )

    # ──────────────────────────────────────────
    # CAPTION
    # ──────────────────────────────────────────

    @staticmethod
    def _caption(
        member: discord.Member,
        mode: str
    ) -> str:

        now = datetime.now(
            timezone.utc
        )

        if mode == "welcome":
            return (
                f"Akun dibuat "
                f"{fmt_date(member.created_at)}"
            )

        if member.joined_at:
            days = max(
                0,
                (
                    now -
                    member.joined_at
                ).days
            )

            return (
                f"Bergabung selama "
                f"{fmt_num(days)} hari"
            )

        return ""

    # ──────────────────────────────────────────
    # GENERATE CARD
    # ──────────────────────────────────────────

    async def _card(
        self,
        member: discord.Member,
        mode: str,
        number: int
    ):

        try:
            avatar_bytes = await (
                member.display_avatar
                .replace(
                    size=512,
                    format="png"
                )
                .read()
            )

            loop = asyncio.get_running_loop()

            # Renderer memakai banyak layer gambar; satu worker mencegah render
            # welcome/leave berjalan bersamaan dan melonjakkan pemakaian RAM.
            png = await loop.run_in_executor(
                _RENDER_EXECUTOR,
                render_entrance_card,
                avatar_bytes,
                member.display_name,
                mode,
                number,
                fmt_date(datetime.now()),
                member.name,
                self._caption(
                    member,
                    mode
                ),
            )

            return discord.File(
                io.BytesIO(png),
                filename=f"{mode}.png"
            )

        except Exception as e:
            print(
                f"[Entrance] Gagal membuat PNG "
                f"({mode}): "
                f"{type(e).__name__}: {e}"
            )

            return None

    # ──────────────────────────────────────────
    # SEND
    # ──────────────────────────────────────────

    async def _send(
        self,
        member: discord.Member,
        channel_id: int,
        mode: str
    ):

        try:
            print(
                f"[Entrance] Memproses {mode} "
                f"untuk {member} ({member.id})"
            )

            # Coba dari cache terlebih dahulu
            channel = member.guild.get_channel(
                channel_id
            )

            # Jika tidak ada, fetch langsung
            if channel is None:

                print(
                    f"[Entrance] Channel {channel_id} "
                    f"tidak ada di cache. "
                    f"Mencoba fetch..."
                )

                channel = await self.bot.fetch_channel(
                    channel_id
                )

            if channel is None:
                print(
                    f"[Entrance] Channel {mode} "
                    f"{channel_id} tidak ditemukan!"
                )
                return

            # Pastikan channel bisa menerima pesan
            if not hasattr(channel, "send"):
                print(
                    f"[Entrance] Channel {channel_id} "
                    f"tidak mendukung send()."
                )
                return

            print(
                f"[Entrance] Channel ditemukan: "
                f"{getattr(channel, 'name', channel_id)}"
            )

            # Member count terbaru
            member_count = (
                member.guild.member_count
                or 0
            )

            # Untuk leave, member_count kadang
            # belum berubah saat event dipanggil.
            if mode == "leave":
                member_count = max(
                    0,
                    member_count - 1
                )

            file = await self._card(
                member,
                mode,
                member_count
            )

            kwargs = {
                "content": member.mention,
                "allowed_mentions":
                    discord.AllowedMentions(
                        users=True
                    )
            }

            if file:
                kwargs["file"] = file

            await channel.send(**kwargs)

            print(
                f"[Entrance] {mode.upper()} "
                f"berhasil dikirim ke "
                f"#{getattr(channel, 'name', channel_id)}"
            )

        except discord.Forbidden as e:
            print(
                f"[Entrance] FORBIDDEN saat "
                f"mengirim {mode}: {e}"
            )

            print(
                "[Entrance] Pastikan bot memiliki "
                "View Channel, Send Messages, "
                "dan Attach Files."
            )

        except discord.NotFound as e:
            print(
                f"[Entrance] Channel tidak ditemukan "
                f"({channel_id}): {e}"
            )

        except Exception as e:
            print(
                f"[Entrance] ERROR saat "
                f"mengirim {mode}: "
                f"{type(e).__name__}: {e}"
            )

    # ──────────────────────────────────────────
    # PUBLIC METHODS
    # ──────────────────────────────────────────

    async def send_welcome(
        self,
        member: discord.Member
    ):
        await self._send(
            member,
            WELCOME_CHANNEL_ID,
            "welcome"
        )

    async def send_leave(
        self,
        member: discord.Member
    ):
        await self._send(
            member,
            LEAVE_CHANNEL_ID,
            "leave"
        )

    # ──────────────────────────────────────────
    # MEMBER JOIN
    # ──────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(
        self,
        member: discord.Member
    ):

        print(
            f"[Entrance] on_member_join "
            f"terpanggil: "
            f"{member} ({member.id})"
        )

        if member.bot:
            print(
                "[Entrance] Member adalah bot. "
                "Welcome dilewati."
            )
            return

        await self.send_welcome(member)

    # ──────────────────────────────────────────
    # MEMBER LEAVE
    # ──────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_remove(
        self,
        member: discord.Member
    ):

        print(
            f"[Entrance] on_member_remove "
            f"terpanggil: "
            f"{member} ({member.id})"
        )

        if member.bot:
            print(
                "[Entrance] Member adalah bot. "
                "Leave dilewati."
            )
            return

        await self.send_leave(member)

    # ──────────────────────────────────────────
    # TEST WELCOME
    # ──────────────────────────────────────────

    @commands.command(
        name="test_welcome"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def test_welcome(
        self,
        ctx,
        member: discord.Member = None
    ):

        target = member or ctx.author

        print(
            f"[Entrance] TEST WELCOME "
            f"oleh {ctx.author} "
            f"untuk {target}"
        )

        await self.send_welcome(
            target
        )

        await self._warn_legacy(ctx)

        try:
            await ctx.message.add_reaction(
                "✅"
            )
        except Exception:
            pass

    # ──────────────────────────────────────────
    # TEST LEAVE
    # ──────────────────────────────────────────

    @commands.command(
        name="test_leave"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def test_leave(
        self,
        ctx,
        member: discord.Member = None
    ):

        target = member or ctx.author

        print(
            f"[Entrance] TEST LEAVE "
            f"oleh {ctx.author} "
            f"untuk {target}"
        )

        await self.send_leave(
            target
        )

        await self._warn_legacy(ctx)

        try:
            await ctx.message.add_reaction(
                "✅"
            )
        except Exception:
            pass

    # ──────────────────────────────────────────
    # ERROR HANDLER TEST COMMAND
    # ──────────────────────────────────────────

    @test_welcome.error
    async def test_welcome_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):
            await ctx.send(
                "❌ Kamu harus memiliki "
                "permission Administrator "
                "untuk menggunakan command ini."
            )
            return

        print(
            f"[Entrance] test_welcome error: "
            f"{type(error).__name__}: {error}"
        )

    @test_leave.error
    async def test_leave_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):
            await ctx.send(
                "❌ Kamu harus memiliki "
                "permission Administrator "
                "untuk menggunakan command ini."
            )
            return

        print(
            f"[Entrance] test_leave error: "
            f"{type(error).__name__}: {error}"
        )


# ══════════════════════════════════════════════
# SETUP
# ══════════════════════════════════════════════

async def setup(bot):
    await bot.add_cog(
        Entrance(bot)
    )

    print(
        "[Entrance] Cog berhasil di-load."
    )