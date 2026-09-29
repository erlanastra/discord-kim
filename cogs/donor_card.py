"""
donor_card.py
Generator PNG "Top 3 Donatur" (layout podium) untuk nanZ Bot.
Style mengikuti booster.py (ungu-biru, orb, aurora, sparkle, cincin avatar).

Pemakaian:
    png_bytes = render_top_donor_card(
        kind="rupiah",              # "rupiah" atau "owo"
        rows=[{"name": "...", "amount": "Rp450.000", "value": 450000, "avatar": bytes|None}, ...],  # max 3, urut peringkat 1..3
        total_value=1245000,        # total semua donasi (buat hitung persen)
        total_text="Total Rp1.245.000",
    )
"""
import io
import math
import random
import unicodedata

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ══════════════════════════════════════════════
#  FONT (sama dengan booster.py)
# ══════════════════════════════════════════════
FONT_BOLD = "fonts/LEMONMILK-Bold.otf"
FONT_MEDIUM = "fonts/LEMONMILK-Medium.otf"
FONT_REGULAR = "fonts/LEMONMILK-Regular.otf"
_FALLBACKS = ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf")

# ══════════════════════════════════════════════
#  WARNA
# ══════════════════════════════════════════════
BG_TOP, BG_BOT = (18, 10, 45), (40, 20, 80)
PURPLE = (130, 80, 255)
BLUE = (80, 180, 255)
CARD_BG = (30, 15, 65)
SOFT_PURPLE = (160, 120, 255)
SOFT_BLUE = (150, 210, 255)
GOLD = (255, 205, 90)
SILVER = (205, 215, 235)
BRONZE = (232, 150, 100)

ACCENT = {"rupiah": PURPLE, "owo": BLUE}
TITLE = {"rupiah": "TOP DONATUR RUPIAH", "owo": "TOP DONATUR OWO"}
SEED = {"rupiah": 21, "owo": 33}

W, H = 900, 560

# rank -> (center_x, tinggi podium, ukuran avatar, warna rank, warna avatar fallback 1, 2, lebar podium)
SPEC = {
    1: (450, 130, 130, GOLD, (255, 170, 80), (200, 90, 200), 236),
    2: (215, 100, 100, SILVER, (90, 110, 170), (150, 160, 210), 200),
    3: (685, 80, 100, BRONZE, (230, 110, 80), (140, 70, 170), 200),
}

_BG_CACHE = {}


# ══════════════════════════════════════════════
#  HELPER
# ══════════════════════════════════════════════
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


def _layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def _spark(x, y, s):
    q = s * 0.25
    return [(x, y - s), (x + q, y - q), (x + s, y), (x + q, y + q),
            (x, y + s), (x - q, y + q), (x - s, y), (x - q, y - q)]


def _clean_name(name: str) -> str:
    """Font LemonMilk cuma support latin. Normalisasi (𝓝𝓪𝓷𝓪 -> Nana), buang emoji/CJK."""
    name = unicodedata.normalize("NFKC", str(name))
    name = "".join(ch for ch in name if ord(ch) < 0x250 and (ch.isprintable()))
    name = " ".join(name.split())
    return name or "User"


def _fit(draw, text, path, start, max_w, min_size=12):
    """Kecilkan font sampai muat; kalau masih panjang, potong + '…'."""
    size = start
    while size >= min_size:
        f = _font(path, size)
        if draw.textlength(text, font=f) <= max_w:
            return f, text
        size -= 1
    f = _font(path, min_size)
    while len(text) > 1 and draw.textlength(text + "…", font=f) > max_w:
        text = text[:-1]
    return f, text + "…"


def _circle_mask(size):
    m = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size * 4, size * 4), fill=255)
    return m.resize((size, size), Image.LANCZOS)


def _avatar_from_bytes(data, size):
    av = Image.open(io.BytesIO(data)).convert("RGBA").resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(av, (0, 0), _circle_mask(size))
    return out


def _avatar_fallback(letter, c1, c2, size):
    im = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(im)
    for y in range(size):
        d.line([(0, y), (size, y)], fill=_lerp(c1, c2, y / size))
    d.text((size / 2, size / 2), letter, font=_font(FONT_BOLD, int(size * 0.5)),
           fill=(255, 255, 255), anchor="mm")
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), _circle_mask(size))
    return out


# ══════════════════════════════════════════════
#  BACKGROUND
# ══════════════════════════════════════════════
def _background(seed, accent):
    key = (seed, accent)
    if key in _BG_CACHE:
        return _BG_CACHE[key].copy()

    r = random.Random(seed)
    bg = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        d.line([(0, y), (W, y)], fill=_lerp(BG_TOP, BG_BOT, y / H))
    base = bg.convert("RGBA")

    orbs = _layer()
    od = ImageDraw.Draw(orbs)
    for ox, oy, br, oc in [(W * .06, H * .25, 150, PURPLE), (W * .94, H * .70, 150, BLUE),
                           (W * .50, -20, 130, accent)]:
        for st in range(br, 0, -5):
            od.ellipse([ox - st, oy - st, ox + st, oy + st],
                       fill=(*oc, _clamp(60 * (st / br) ** 2.8 * .85)))
    base = Image.alpha_composite(base, orbs)

    rays = _layer()
    rd = ImageDraw.Draw(rays)
    for i in range(-5, 6):
        a = math.pi / 2 + i * 0.115
        a2 = a + 0.045
        rd.polygon([(450, -30),
                    (450 + 900 * math.cos(a), -30 + 900 * math.sin(a)),
                    (450 + 900 * math.cos(a2), -30 + 900 * math.sin(a2))],
                   fill=(*_lerp(SOFT_BLUE, SOFT_PURPLE, (i + 5) / 10), 26))
    base = Image.alpha_composite(base, rays.filter(ImageFilter.GaussianBlur(5)))

    aur = _layer()
    ad = ImageDraw.Draw(aur)
    for by, amp, k, off, col, a in [(430, 30, 2, 0.0, BLUE, 50), (475, 24, 3, 2.0, PURPLE, 65),
                                    (515, 18, 4, 4.0, SOFT_BLUE, 40)]:
        pts = [(x, by + amp * math.sin(math.tau * k * x / W + off)) for x in range(0, W + 10, 10)]
        ad.polygon(pts + [(W, H), (0, H)], fill=(*col, a))
    base = Image.alpha_composite(base, aur.filter(ImageFilter.GaussianBlur(6)))

    fl = _layer()
    fd = ImageDraw.Draw(fl)
    for _ in range(85):
        x, y, rad, tw, a = r.uniform(0, W), r.uniform(0, H), r.uniform(1, 2.6), r.random(), r.randint(90, 200)
        fd.ellipse([x - rad, y - rad, x + rad, y + rad],
                   fill=(*_lerp(PURPLE, BLUE, tw), _clamp(a * (.45 + .55 * tw))))
    for _ in range(14):
        x, y, s, tw = r.uniform(15, W - 15), r.uniform(12, H - 12), r.uniform(5, 10), r.uniform(.4, 1)
        fd.polygon(_spark(x, y, s * (.35 + .65 * tw)),
                   fill=(*_lerp(SOFT_BLUE, SOFT_PURPLE, tw), _clamp(70 + 185 * tw)))
    for _ in range(16):
        x, y, rad, a = r.uniform(0, W), r.uniform(0, H), r.uniform(3, 7), r.randint(80, 150)
        fd.ellipse([x - rad, y - rad, x + rad, y + rad], outline=(255, 255, 255, a))
        fd.ellipse([x - rad * .35, y - rad * .35, x + rad * .1, y + rad * .1], fill=(255, 255, 255, a))
    base = Image.alpha_composite(base, fl)

    cf = _layer()
    cd = ImageDraw.Draw(cf)
    for _ in range(34):
        x, y = r.gauss(450, 230), r.uniform(105, 330)
        if not (20 < x < W - 20):
            continue
        c = r.choice([GOLD, SOFT_BLUE, SOFT_PURPLE, (255, 255, 255)])
        w, h = r.uniform(4, 8), r.uniform(8, 14)
        a = r.uniform(0, math.pi)
        pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
        pts = [(x + px * math.cos(a) - py * math.sin(a), y + px * math.sin(a) + py * math.cos(a)) for px, py in pts]
        cd.polygon(pts, fill=(*c, r.randint(140, 230)))
    base = Image.alpha_composite(base, cf)

    _BG_CACHE[key] = base
    return base.copy()


# ══════════════════════════════════════════════
#  RENDER UTAMA
# ══════════════════════════════════════════════
def render_top_donor_card(kind: str, rows: list, total_value: int, total_text: str) -> bytes:
    accent = ACCENT.get(kind, PURPLE)
    base = _background(SEED.get(kind, 21), accent)
    rows = list(rows[:3]) + [None] * (3 - len(rows[:3]))
    total_value = total_value or 0

    # ── Header ──
    tl = _layer()
    td = ImageDraw.Draw(tl)
    title = TITLE.get(kind, "TOP DONATUR")
    f_pil = _font(FONT_MEDIUM, 14)
    pw = int(td.textlength(title, font=f_pil)) + 56
    td.rounded_rectangle([40, 28, 40 + pw, 58], radius=15, fill=(*accent, 235))
    td.polygon(_spark(60, 43, 7), fill=(255, 255, 255, 255))
    td.text((76, 43), title, font=f_pil, fill=(255, 255, 255, 255), anchor="lm")
    td.text((40, 84), "TERIMA KASIH SUDAH MENDUKUNG NANZ", font=_font(FONT_MEDIUM, 13),
            fill=(*SOFT_BLUE, 255), anchor="lm")
    for x in range(40, 300):
        fa = 1 - (x - 40) / 260
        td.line([(x, 98), (x, 100)], fill=(*_lerp(BLUE, PURPLE, (x - 40) / 260), _clamp(255 * fa ** .7)))
    f_tot = _font(FONT_MEDIUM, 14)
    tw = int(td.textlength(total_text, font=f_tot)) + 52
    x = W - 40 - tw
    td.rounded_rectangle([x, 28, x + tw, 58], radius=15, fill=(*PURPLE, 56), outline=(*PURPLE, 217), width=1)
    td.ellipse([x + 9, 33, x + 29, 53], fill=(*PURPLE, 255))
    td.polygon(_spark(x + 19, 43, 6), fill=(255, 255, 255, 255))
    td.text((x + 36, 43), total_text, font=f_tot, fill=(255, 255, 255, 255), anchor="lm")
    base = Image.alpha_composite(base, tl)

    S = 2
    bottom = H - 28

    # ── Podium ──
    for rank in (2, 3, 1):
        cx, ph, av, col, c1, c2, pw_ = SPEC[rank]
        top = bottom - ph
        x0, x1 = cx - pw_ // 2, cx + pw_ // 2

        grad = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for y in range(top * S, bottom * S + 60):
            t = min(1.0, (y - top * S) / ((bottom - top) * S))
            gd.line([(x0 * S, y), (x1 * S, y)],
                    fill=(*_lerp(_lerp(CARD_BG, col, .38), CARD_BG, t ** .7), 235))
        mask = Image.new("L", (W * S, H * S), 0)
        ImageDraw.Draw(mask).rounded_rectangle([x0 * S, top * S, x1 * S, (bottom + 30) * S],
                                               radius=24 * S, fill=255)
        alpha = Image.new("L", (W * S, H * S), 0)
        alpha.paste(grad.getchannel("A"), (0, 0), mask)
        grad.putalpha(alpha)

        ol = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
        od = ImageDraw.Draw(ol)
        od.rounded_rectangle([x0 * S, top * S, x1 * S, (bottom + 30) * S],
                             radius=24 * S, outline=(*col, 170), width=2 * S)
        od.rounded_rectangle([(x0 + 22) * S, top * S, (x1 - 22) * S, (top + 4) * S],
                             radius=2 * S, fill=(*col, 255))
        pod = Image.alpha_composite(grad, ol).resize((W, H), Image.LANCZOS)

        glow = _layer()
        ImageDraw.Draw(glow).ellipse([cx - pw_ * .6, top - 40, cx + pw_ * .6, top + 30], fill=(*col, 60))
        base = Image.alpha_composite(base, glow.filter(ImageFilter.GaussianBlur(18)))
        base = Image.alpha_composite(base, pod)

        d = ImageDraw.Draw(base)
        d.text((cx, top + (ph + 28) * .68), str(rank), font=_font(FONT_BOLD, 46),
               fill=(*col, 70), anchor="mm")
        row = rows[rank - 1]
        if row and total_value > 0:
            pct = row["value"] / total_value * 100
            pct_txt = "<1% dari total" if pct < 1 else f"{round(pct)}% dari total"
        else:
            pct_txt = "—"
        d.text((cx, top + 20), pct_txt, font=_font(FONT_MEDIUM, 12),
               fill=(235, 235, 250, 255), anchor="mm")

    # ── Avatar, nama, nominal ──
    for rank in (2, 3, 1):
        cx, ph, av, col, c1, c2, pw_ = SPEC[rank]
        top = bottom - ph
        row = rows[rank - 1]
        name = _clean_name(row["name"]) if row else "—"
        amount = row["amount"] if row else "Belum ada"
        cy = top - 100 - av // 2
        rr = av // 2 + 9

        halo = _layer()
        ImageDraw.Draw(halo).ellipse([cx - rr - 22, cy - rr - 22, cx + rr + 22, cy + rr + 22], fill=(*col, 55))
        base = Image.alpha_composite(base, halo.filter(ImageFilter.GaussianBlur(16)))

        ring = _layer()
        rd = ImageDraw.Draw(ring)
        rd.ellipse([cx - rr - 16, cy - rr - 16, cx + rr + 16, cy + rr + 16], outline=(255, 255, 255, 40), width=1)
        rd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(255, 255, 255, 70), width=2)
        rd.arc([cx - rr, cy - rr, cx + rr, cy + rr], -70, 40, fill=(*col, 255), width=5)
        rd.arc([cx - rr, cy - rr, cx + rr, cy + rr], 110, 220, fill=(*SOFT_BLUE, 255), width=5)
        for i in range(6):
            a = i * math.tau / 6 + .3
            R = rr + 16
            px, py = cx + R * math.cos(a), cy + R * math.sin(a)
            rd.ellipse([px - 3, py - 3, px + 3, py + 3],
                       fill=(*(SOFT_BLUE if i % 2 == 0 else SOFT_PURPLE), 235))
        base = Image.alpha_composite(base, ring)

        avatar = None
        if row and row.get("avatar"):
            try:
                avatar = _avatar_from_bytes(row["avatar"], av)
            except Exception:
                avatar = None
        if avatar is None:
            avatar = _avatar_fallback(name[0].upper() if row else "?", c1, c2, av)
        base.alpha_composite(avatar, (cx - av // 2, cy - av // 2))

        d = ImageDraw.Draw(base)
        bx, by = cx + av // 2 - 6, cy + av // 2 - 6
        d.ellipse([bx - 19, by - 19, bx + 19, by + 19], fill=(*CARD_BG, 255))
        d.ellipse([bx - 15, by - 15, bx + 15, by + 15], fill=(*col, 255))
        d.text((bx, by), str(rank), font=_font(FONT_BOLD, 17), fill=(30, 15, 65), anchor="mm")

        if rank == 1:   # mahkota
            ty = cy - rr - 38
            pts = [(cx - 26, ty + 28), (cx - 31, ty + 4), (cx - 14, ty + 16), (cx, ty - 6),
                   (cx + 14, ty + 16), (cx + 31, ty + 4), (cx + 26, ty + 28)]
            d.polygon(pts, fill=(*GOLD, 255))
            d.rectangle([cx - 26, ty + 28, cx + 26, ty + 34], fill=(255, 170, 60, 255))
            for jx, jy, jc in [(cx - 31, ty + 4, SOFT_BLUE), (cx, ty - 6, (255, 120, 160)),
                               (cx + 31, ty + 4, SOFT_BLUE)]:
                d.ellipse([jx - 4, jy - 4, jx + 4, jy + 4], fill=(*jc, 255))

        ny = top - 64
        f_name, t_name = _fit(d, name, FONT_BOLD, 24 if rank == 1 else 19, pw_ - 24)
        d.text((cx, ny), t_name, font=f_name, fill=(255, 255, 255, 255), anchor="mm")

        f_amt, t_amt = _fit(d, amount, FONT_MEDIUM, 17 if rank == 1 else 14, pw_ - 50)
        cw = int(d.textlength(t_amt, font=f_amt)) + 30
        d.rounded_rectangle([cx - cw / 2, ny + 18, cx + cw / 2, ny + 48], radius=15,
                            fill=_lerp(CARD_BG, col, .28), outline=col, width=1)
        d.text((cx, ny + 33), t_amt, font=f_amt, fill=(255, 255, 255, 255), anchor="mm")

    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()