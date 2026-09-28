import asyncio
import io
import math
import random
from datetime import datetime, timezone

import discord
from discord.ext import commands
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

# ══════════════════════════════════════════════
#  KONFIGURASI
# ══════════════════════════════════════════════
WELCOME_CHANNEL_ID = 1554124578006114415  # ← GANTI: channel welcome
LEAVE_CHANNEL_ID = 1554124709535424572    # ← GANTI: channel leave

# ══════════════════════════════════════════════
#  PNG GENERATOR
# ══════════════════════════════════════════════
FONT_BOLD = "fonts/LEMONMILK-Bold.otf"
FONT_MEDIUM = "fonts/LEMONMILK-Medium.otf"
FONT_REGULAR = "fonts/LEMONMILK-Regular.otf"
_FALLBACKS = ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf")

BG_TOP, BG_BOT = (16, 8, 40), (42, 20, 84)
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
SS = 4
CX, CY, R = 646, 170, 90
HR = 130
TX0, TX1 = 56, 452

BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

THEMES = {
    "welcome": {
        "c1": BLUE, "c2": PURPLE, "soft": SOFT_BLUE,
        "tag": "WELCOME",
        "body": "Selamat datang di nanZ Server, semoga betah ya!",
        "chip1": lambda n: f"Member ke-{n}",
        "date_col": PURPLE, "icon": "plus", "gray": False,
    },
    "leave": {
        "c1": ROSE, "c2": PURPLE, "soft": SOFT_ROSE,
        "tag": "GOODBYE",
        "body": "Makasih udah pernah jadi bagian dari nanZ Server.",
        "chip1": lambda n: f"Sisa {n} member",
        "date_col": SOFT_PURPLE, "icon": "minus", "gray": True,
    },
}


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
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


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
        draw.text((x, y), ch, font=font, fill=fill, anchor="lm")
        x += draw.textlength(ch, font=font) + spacing
    return x


def _ss_layer(fn):
    big = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    fn(ImageDraw.Draw(big))
    return big.resize((W, H), Image.LANCZOS)


def _ss_mask(fn):
    big = Image.new("L", (W * SS, H * SS), 0)
    fn(ImageDraw.Draw(big))
    return big.resize((W, H), Image.LANCZOS)


def _circle_mask(r):
    m = Image.new("L", (r * 2 * SS, r * 2 * SS), 0)
    ImageDraw.Draw(m).ellipse([0, 0, r * 2 * SS - 1, r * 2 * SS - 1], fill=255)
    return m.resize((r * 2, r * 2), Image.LANCZOS)


def _prepare_avatar(avatar_bytes, size, gray=False):
    im = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    m = min(im.size)
    l, t = (im.width - m) // 2, (im.height - m) // 2
    im = im.crop((l, t, l + m, t + m)).resize((size, size), Image.LANCZOS)
    flat = Image.new("RGBA", im.size, (*BG_BOT, 255))
    im = Image.alpha_composite(flat, im).convert("RGB")
    if gray:
        im = ImageEnhance.Color(im).enhance(0.25)
        im = ImageEnhance.Brightness(im).enhance(0.9)
    return im


def _sparkle_poly(x, y, sz):
    q = sz * 0.25
    return [(x, y - sz), (x + q, y - q), (x + sz, y), (x + q, y + q),
            (x, y + sz), (x - q, y + q), (x - sz, y), (x - q, y - q)]


def _hex_pts(cx, cy, r):
    return [(cx + r * math.cos(math.radians(60 * k)),
             cy + r * math.sin(math.radians(60 * k))) for k in range(6)]


def _hgrad(x0, x1, c1, c2):
    g = Image.new("RGB", (W, H))
    gd = ImageDraw.Draw(g)
    for x in range(W):
        gd.line([(x, 0), (x, H)], fill=_lerp(c1, c2, min(1, max(0, (x - x0) / max(1, x1 - x0)))))
    return g


def _diag_gradient(c1, c2, c3):
    g = Image.new("RGB", (W, H))
    gd = ImageDraw.Draw(g)
    n = W + H
    for k in range(n):
        t = k / n
        col = _lerp(c1, c2, t * 2) if t < 0.5 else _lerp(c2, c3, (t - 0.5) * 2)
        gd.line([(k, 0), (k - H, H)], fill=col, width=2)
    return g


def _make_fx(seed=7):
    rng = random.Random(seed)
    stars = [{"x": rng.uniform(0, W), "y": rng.uniform(0, H), "r": rng.uniform(1.0, 2.4),
              "tw": rng.random(), "a": rng.randint(90, 200)} for _ in range(55)]
    sparkles = [{"x": rng.uniform(15, W - 15), "y": rng.uniform(12, H - 12),
                 "s": rng.uniform(5, 9), "tw": rng.uniform(0.4, 1.0)} for _ in range(9)]
    return {"stars": stars, "sparkles": sparkles}


def _honeycomb(c, soft):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    r = 24
    dx, dy = 1.5 * r, math.sqrt(3) * r
    rng = random.Random(5)
    col = 0
    x = 380
    while x < W + r:
        y = -dy + (dy / 2 if col % 2 else 0)
        while y < H + dy:
            dist = math.hypot(x - CX, y - CY)
            fade = 1 - (dist - HR) / 300
            if dist > HR + 8 and fade > 0:
                d.polygon(_hex_pts(x, y, r - 1.5), outline=(*soft, _clamp(70 * fade)), width=1)
                if rng.random() < 0.10:
                    d.polygon(_hex_pts(x, y, r - 1.5), fill=(*c, _clamp(38 * fade)))
            y += dy
        x += dx
        col += 1
    return lay


def _background(fx, c1, c2, soft):
    bg = Image.new("RGB", (W, H))
    bd = ImageDraw.Draw(bg)
    for y in range(H):
        bd.line([(0, y), (W, y)], fill=_lerp(BG_TOP, BG_BOT, y / H))
    base = bg.convert("RGBA")

    orbs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(orbs)
    for ox, oy, br, oc in [(W * .06, H * .12, 150, c2), (W * .92, H * .80, 160, c1), (W * .55, -10, 120, c2)]:
        for st in range(br, 0, -5):
            od.ellipse([ox - st, oy - st, ox + st, oy + st],
                       fill=(*oc, _clamp(60 * (st / br) ** 2.8 * 0.85)))
    base = Image.alpha_composite(base, orbs)

    aur = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ad = ImageDraw.Draw(aur)
    for by, amp, k, off, col, a in [(250, 26, 2, 0.0, c1, 55), (285, 20, 3, 2.0, c2, 70)]:
        pts = [(x, by + amp * math.sin(math.tau * k * x / W + off)) for x in range(0, W + 10, 10)]
        ad.polygon(pts + [(W, H), (0, H)], fill=(*col, a))
    base = Image.alpha_composite(base, aur.filter(ImageFilter.GaussianBlur(6)))

    beams = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bmd = ImageDraw.Draw(beams)
    for x0, wd, a in [(470, 34, 26), (540, 14, 32), (600, 70, 16)]:
        bmd.polygon([(x0, 0), (x0 + wd, 0), (x0 + wd - 190, H), (x0 - 190, H)], fill=(*soft, a))
    base = Image.alpha_composite(base, beams.filter(ImageFilter.GaussianBlur(5)))

    base = Image.alpha_composite(base, _honeycomb(c1, soft))

    fl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fl)
    for gy in range(8, H, 14):
        for gx in range(8, 440, 14):
            a = _clamp(60 * (1 - gx / 440) ** 1.2)
            if a > 4:
                fd.ellipse([gx - 1.2, gy - 1.2, gx + 1.2, gy + 1.2], fill=(*soft, a))
    for p in fx["stars"]:
        r, tw = p["r"], p["tw"]
        fd.ellipse([p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r],
                   fill=(*_lerp(c2, c1, tw), _clamp(p["a"] * (0.45 + 0.55 * tw))))
    for p in fx["sparkles"]:
        tw = p["tw"]
        fd.polygon(_sparkle_poly(p["x"], p["y"], p["s"] * (0.35 + 0.65 * tw)),
                   fill=(*_lerp(soft, SOFT_PURPLE, tw), _clamp(70 + 185 * tw)))
    base = Image.alpha_composite(base, fl)

    fr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    frd = ImageDraw.Draw(fr)
    frd.rounded_rectangle([8, 8, W - 9, H - 9], radius=16, outline=(*soft, 70), width=1)
    L = 26
    for (x, y, dx, dy) in [(16, 16, 1, 1), (W - 17, 16, -1, 1), (16, H - 17, 1, -1), (W - 17, H - 17, -1, -1)]:
        frd.line([(x, y + dy * L), (x, y), (x + dx * L, y)], fill=(*c1, 220), width=3, joint="curve")
    return Image.alpha_composite(base, fr)


def _shooting_stars(lay, soft, seed):
    """Bintang jatuh: garis dengan ekor memudar."""
    rng = random.Random(seed)
    d = ImageDraw.Draw(lay)
    for _ in range(3):
        x, y = rng.uniform(300, 760), rng.uniform(14, 120)
        ang = math.radians(rng.uniform(140, 155))
        ln = rng.uniform(70, 120)
        steps = 30
        for i in range(steps):
            t0, t1 = i / steps, (i + 1) / steps
            a = int(230 * t0 ** 1.6)
            p0 = (x - math.cos(ang) * ln * (1 - t0), y - math.sin(ang) * ln * (1 - t0))
            p1 = (x - math.cos(ang) * ln * (1 - t1), y - math.sin(ang) * ln * (1 - t1))
            d.line([p0, p1], fill=(*soft, a), width=2)
        d.ellipse([x - 2.2, y - 2.2, x + 2.2, y + 2.2], fill=(*WHITE, 255))


def _particles(mode, c1, c2, soft):
    rng = random.Random(77 if mode == "welcome" else 88)
    bok = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bok)
    for _ in range(11):
        x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(6, 17)
        bd.ellipse([x - r, y - r, x + r, y + r], fill=(*rng.choice([c1, c2, soft]), rng.randint(22, 48)))
    lay = bok.filter(ImageFilter.GaussianBlur(2.5))
    d = ImageDraw.Draw(lay)
    if mode == "welcome":
        cols = [c1, c2, soft, WHITE, SOFT_PURPLE]
        for _ in range(34):
            x, y = rng.uniform(445, W - 6), rng.uniform(6, H - 6)
            if math.hypot(x - CX, y - CY) < R + 40:
                continue
            a = rng.uniform(0, math.pi)
            w, h = rng.uniform(4, 8), rng.uniform(2, 3.5)
            pts = [(x + math.cos(a) * dx - math.sin(a) * dy, y + math.sin(a) * dx + math.cos(a) * dy)
                   for dx, dy in [(-w, -h), (w, -h), (w, h), (-w, h)]]
            d.polygon(pts, fill=(*rng.choice(cols), rng.randint(150, 235)))
    _shooting_stars(lay, soft, 5 if mode == "welcome" else 9)
    return lay


def _glass_panel(c1, c2):
    def edge(y):
        return 486 - 46 * y / H

    S = 2
    pan = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pan)
    poly = [(0, 0), (edge(0) * S, 0), (edge(H) * S, H * S), (0, H * S)]
    pd.polygon(poly, fill=(*CARD_BG, 165))
    pd.polygon(poly, fill=(255, 255, 255, 9))
    # kilau kaca diagonal
    pd.polygon([(190 * S, 0), (240 * S, 0), (184 * S, H * S), (134 * S, H * S)], fill=(255, 255, 255, 8))
    pd.polygon([(262 * S, 0), (274 * S, 0), (218 * S, H * S), (206 * S, H * S)], fill=(255, 255, 255, 10))
    for y in range(0, H, 3):
        col = _lerp(c1, c2, y / H)
        pd.line([(edge(y) * S, y * S), (edge(y + 3) * S, (y + 3) * S)], fill=(*col, 255), width=6)
        pd.line([((edge(y) - 13) * S, y * S), ((edge(y + 3) - 13) * S, (y + 3) * S)],
                fill=(*col, 80), width=2)
    return pan.resize((W, H), Image.LANCZOS)


def _milestone(n):
    step = 100 if n < 1000 else 500
    ms = (n // step + 1) * step
    return ms, max(0.03, min(1, n / ms))


def render_entrance_card(avatar_bytes: bytes, name: str, mode: str = "welcome",
                         number: int = 0, date_text: str = "",
                         username: str = "", caption: str = "") -> bytes:
    th = THEMES[mode]
    c1, c2, soft = th["c1"], th["c2"], th["soft"]
    welcome = mode == "welcome"

    # ── Background ──
    base = _background(_make_fx(seed=21 if welcome else 33), c1, c2, soft)
    base = Image.alpha_composite(base, _particles(mode, c1, c2, soft))

    spot = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spot)
    for r_, a_ in [(200, 40), (170, 55), (140, 75)]:
        sd.ellipse([CX - r_, CY - r_, CX + r_, CY + r_], fill=(*c2, a_))
    base = Image.alpha_composite(base, spot.filter(ImageFilter.GaussianBlur(26)))
    base = Image.alpha_composite(base, _glass_panel(c1, c2))

    # ── Avatar: halo ──
    halo = Image.new("RGBA", (W, H), (*c1, 0))
    hm = Image.new("L", (W, H), 0)
    ImageDraw.Draw(hm).ellipse([CX - R - 6, CY - R - 6, CX + R + 6, CY + R + 6], fill=200)
    halo.putalpha(hm.filter(ImageFilter.GaussianBlur(16)))
    base = Image.alpha_composite(base, halo)

    # cincin gradasi utama
    ring = _ss_mask(lambda d: d.ellipse(
        [(CX - R - 6) * SS, (CY - R - 6) * SS, (CX + R + 6) * SS, (CY + R + 6) * SS],
        outline=255, width=5 * SS))
    holo = _diag_gradient(soft, c1, c2).convert("RGBA")
    holo.putalpha(ring)

    # ── Cincin luar: progress (welcome) / putus-putus (leave) ──
    RO = R + 22
    bb = [(CX - RO) * SS, (CY - RO) * SS, (CX + RO) * SS, (CY + RO) * SS]
    if welcome:
        _, prog = _milestone(number)
        end_deg = -90 + 360 * prog
        base = Image.alpha_composite(base, _ss_layer(
            lambda d: d.ellipse(bb, outline=(*soft, 45), width=1 * SS)))
        arc_m = _ss_mask(lambda d: d.arc(bb, -90, end_deg, fill=255, width=4 * SS))
        arc = _diag_gradient(c1, soft, c2).convert("RGBA")
        arc.putalpha(arc_m)
        glow = arc.filter(ImageFilter.GaussianBlur(5))
        base = Image.alpha_composite(base, glow)
        base = Image.alpha_composite(base, arc)
        dot_deg = end_deg
    else:
        def dashed(d):
            for k in range(0, 360, 12):
                d.arc(bb, k, k + 6, fill=(*soft, 90), width=2 * SS)
        base = Image.alpha_composite(base, _ss_layer(dashed))
        dot_deg = -50

    # tick ring (jam)
    RT = R + 36

    def ticks(d):
        for k in range(72):
            a = math.radians(k * 5 - 90)
            major = k % 6 == 0
            r0, r1 = RT, RT + (7 if major else 3.5)
            d.line([((CX + r0 * math.cos(a)) * SS, (CY + r0 * math.sin(a)) * SS),
                    ((CX + r1 * math.cos(a)) * SS, (CY + r1 * math.sin(a)) * SS)],
                   fill=(*soft, 120 if major else 50), width=SS)
    base = Image.alpha_composite(base, _ss_layer(ticks))
    base = Image.alpha_composite(base, holo)

    av = _prepare_avatar(avatar_bytes, R * 2, gray=th["gray"])
    base.paste(av, (CX - R, CY - R), _circle_mask(R))

    # kilap kaca di atas avatar
    gl = Image.new("RGBA", (R * 2, R * 2), (0, 0, 0, 0))
    gd_ = ImageDraw.Draw(gl)
    for i in range(R):
        a = int(34 * (1 - i / R) ** 2)
        gd_.line([(0, i), (R * 2, i)], fill=(255, 255, 255, a))
    gl.putalpha(ImageChops.multiply(gl.getchannel("A"), _circle_mask(R)))
    base.alpha_composite(gl, (CX - R, CY - R))

    ox = CX + RO * math.cos(math.radians(dot_deg))
    oy = CY + RO * math.sin(math.radians(dot_deg))

    def orbit(d):
        d.ellipse([(ox - 10) * SS, (oy - 10) * SS, (ox + 10) * SS, (oy + 10) * SS], fill=(*c1, 90))
        d.ellipse([(ox - 4.5) * SS, (oy - 4.5) * SS, (ox + 4.5) * SS, (oy + 4.5) * SS], fill=(*WHITE, 255))

    base = Image.alpha_composite(base, _ss_layer(orbit))

    # ── Badge ──
    bx = CX + int((R + 6) * math.cos(math.radians(45)))
    by = CY + int((R + 6) * math.sin(math.radians(45)))

    def badge(d):
        d.ellipse([(bx - 23) * SS, (by - 23) * SS, (bx + 23) * SS, (by + 23) * SS], fill=(*CARD_BG, 255))
        d.ellipse([(bx - 18) * SS, (by - 18) * SS, (bx + 18) * SS, (by + 18) * SS], fill=(*c1, 255))
        d.rounded_rectangle([(bx - 8) * SS, (by - 1.5) * SS, (bx + 8) * SS, (by + 1.5) * SS],
                            radius=SS, fill=(*WHITE, 255))
        if th["icon"] == "plus":
            d.rounded_rectangle([(bx - 1.5) * SS, (by - 8) * SS, (bx + 1.5) * SS, (by + 8) * SS],
                                radius=SS, fill=(*WHITE, 255))

    base = Image.alpha_composite(base, _ss_layer(badge))

    # ── Teks ──
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    tl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(tl)

    td.polygon(_hex_pts(TX0 + 11, 50, 11), outline=(*c1, 255), width=2)
    td.polygon(_hex_pts(TX0 + 11, 50, 4), fill=(*soft, 255))
    td.text((TX0 + 32, 50), "nanZ", font=_font(FONT_BOLD, 18), fill=(*WHITE, 255), anchor="lm")

    # tag + @username
    ty = 108
    td.line([(TX0, ty), (TX0 + 22, ty)], fill=(*c1, 255), width=2)
    ex = _spaced(td, (TX0 + 32, ty), th["tag"], _font(FONT_MEDIUM, 12), (*soft, 255), spacing=4)
    if username:
        f_u = _font(FONT_REGULAR, 12)
        handle = "@" + username
        while len(handle) > 3 and ex + 22 + tmp.textlength(handle, font=f_u) > TX1:
            handle = handle[:-2] + "…"
        td.ellipse([ex + 8, ty - 2, ex + 12, ty + 2], fill=(*MUTED, 200))
        td.text((ex + 22, ty), handle, font=f_u, fill=(*MUTED, 235), anchor="lm")
    base = Image.alpha_composite(base, tl)

    # nama gradasi + glow
    f_name, nm = _fit_font(tmp, name, FONT_BOLD, 52, TX1 - TX0, 24)
    nmask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(nmask).text((TX0, 158), nm, font=f_name, fill=255, anchor="lm")
    sh = Image.new("RGBA", (W, H), (*c2, 0))
    sh.putalpha(nmask.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.55)))
    base = Image.alpha_composite(base, sh)
    nw = int(tmp.textlength(nm, font=f_name))
    base.paste(_hgrad(TX0, TX0 + max(nw, 120), WHITE, soft), (0, 0), nmask)

    tl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(tl)

    f_b, body = _fit_font(tmp, th["body"], FONT_REGULAR, 15, TX1 - TX0, 11)
    td.text((TX0, 204), body, font=f_b, fill=(*WHITE, 205), anchor="lm")

    # baris info + bar milestone
    f_s = _font(FONT_REGULAR, 11)
    ly = 229
    if caption:
        td.ellipse([TX0, ly - 2.5, TX0 + 5, ly + 2.5], fill=(*soft, 255))
        td.text((TX0 + 12, ly), caption, font=f_s, fill=(*MUTED, 255), anchor="lm")
    by_ = 245
    if welcome:
        ms, prog = _milestone(number)
        lab = f"{fmt_num(number)} / {fmt_num(ms)}"
        td.text((TX1, ly), lab, font=f_s, fill=(*soft, 255), anchor="rm")
        bw = TX1 - TX0
        td.rounded_rectangle([TX0, by_ - 3, TX1, by_ + 3], radius=3, fill=(*soft, 40))
        fw = max(8, int(bw * prog))
        for x in range(TX0, TX0 + fw):
            td.line([(x, by_ - 3), (x, by_ + 3)], fill=(*_lerp(c1, soft, (x - TX0) / bw), 255))
        td.ellipse([TX0 - 1, by_ - 3, TX0 + 5, by_ + 3], fill=(*c1, 255))
        tx = TX0 + fw
        td.ellipse([tx - 6, by_ - 6, tx + 6, by_ + 6], fill=(*soft, 70))
        td.ellipse([tx - 3.5, by_ - 3.5, tx + 3.5, by_ + 3.5], fill=(*WHITE, 255))
    else:
        for x in range(TX0, TX1 + 20):
            f = 1 - (x - TX0) / (TX1 + 20 - TX0)
            td.line([(x, by_), (x, by_ + 1)], fill=(*soft, _clamp(120 * f)))

    # pills
    cy = 288
    f_c = _font(FONT_MEDIUM, 12)

    def pill(x, txt, col):
        w = int(td.textlength(txt, font=f_c)) + 40
        td.rounded_rectangle([x, cy - 15, x + w, cy + 15], radius=15,
                             fill=(*col, 40), outline=(*col, 200), width=1)
        td.ellipse([x + 13, cy - 3.5, x + 20, cy + 3.5], fill=(*col, 255))
        td.text((x + 28, cy), txt, font=f_c, fill=(*WHITE, 255), anchor="lm")
        return x + w

    nx = pill(TX0, th["chip1"](fmt_num(number)), c1)
    if date_text:
        pill(nx + 10, date_text, th["date_col"])
    base = Image.alpha_composite(base, tl)

    # ── Scanline halus + vignette + grain ──
    sc = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    scd = ImageDraw.Draw(sc)
    for y in range(0, H, 3):
        scd.line([(0, y), (W, y)], fill=(0, 0, 0, 14))
    base = Image.alpha_composite(base, sc)

    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse([-70, -60, W + 70, H + 60], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(50))
    dark = Image.new("RGBA", (W, H), (6, 2, 20, 0))
    dark.putalpha(ImageChops.invert(vig).point(lambda v: int(v * 0.55)))
    base = Image.alpha_composite(base, dark)

    grain = Image.effect_noise((W, H), 38).convert("RGBA")
    grain.putalpha(9)
    base = Image.alpha_composite(base, grain)

    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


# ══════════════════════════════════════════════
#  ENTRANCE COG
# ══════════════════════════════════════════════
class Entrance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def _caption(member: discord.Member, mode: str) -> str:
        now = datetime.now(timezone.utc)
        if mode == "welcome":
            return f"Akun dibuat {fmt_date(member.created_at)}"
        if member.joined_at:
            days = max(0, (now - member.joined_at).days)
            return f"Bergabung selama {fmt_num(days)} hari"
        return ""

    async def _card(self, member, mode: str, number: int):
        try:
            avatar_bytes = await member.display_avatar.replace(size=512, format="png").read()
            loop = asyncio.get_running_loop()
            png = await loop.run_in_executor(
                None, render_entrance_card, avatar_bytes, member.display_name, mode, number,
                fmt_date(datetime.now()), member.name, self._caption(member, mode),
            )
            return discord.File(io.BytesIO(png), filename=f"{mode}.png")
        except Exception as e:
            print(f"[Entrance] gagal bikin PNG ({mode}): {e}")
            return None

    async def _send(self, member: discord.Member, channel_id: int, mode: str):
        channel = member.guild.get_channel(channel_id)
        if channel is None:
            print(f"[Entrance] Channel {mode} {channel_id} tidak ditemukan!")
            return
        file = await self._card(member, mode, member.guild.member_count)
        kwargs = {"file": file} if file else {}
        await channel.send(
            content=member.mention,
            allowed_mentions=discord.AllowedMentions(users=True),
            **kwargs,
        )

    async def send_welcome(self, member: discord.Member):
        await self._send(member, WELCOME_CHANNEL_ID, "welcome")

    async def send_leave(self, member: discord.Member):
        await self._send(member, LEAVE_CHANNEL_ID, "leave")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        await self.send_welcome(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot:
            return
        await self.send_leave(member)

    @commands.command(name="test_welcome")
    @commands.has_permissions(administrator=True)
    async def test_welcome(self, ctx, member: discord.Member = None):
        await self.send_welcome(member or ctx.author)
        await ctx.message.add_reaction("✅")

    @commands.command(name="test_leave")
    @commands.has_permissions(administrator=True)
    async def test_leave(self, ctx, member: discord.Member = None):
        await self.send_leave(member or ctx.author)
        await ctx.message.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(Entrance(bot))