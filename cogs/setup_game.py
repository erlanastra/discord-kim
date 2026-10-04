import asyncio
import io
import math
import random

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ══════════════════════════════════════════════
#  KONFIGURASI
# ══════════════════════════════════════════════
# label/sub = teks di gambar banner, emoji = dipakai di menu & balasan
GAME_ROLES = {
    "PUBG": {
        "id": 1453431240785920062, "emoji": "🔫",
        "label": "PUBG", "sub": "Battle Royale", "icon": "helmet",
    },
    "Delta Force": {
        "id": 1453429436593606676, "emoji": "🪖",
        "label": "Delta Force", "sub": "FPS Taktis", "icon": "delta",
    },
    "Valorant": {
        "id": 1453428694839197909, "emoji": "🎯",
        "label": "Valorant", "sub": "FPS Taktis", "icon": "crosshair",
    },
    "Minecraft": {
        "id": 1453429627107283117, "emoji": "⛏️",
        "label": "Minecraft", "sub": "Sandbox", "icon": "cube",
    },
    "Mobile Legends": {
        "id": 1453427876488548543, "emoji": "📱",
        "label": "Mobile Legends", "sub": "MOBA", "icon": "phone",
    },
    "GTA V": {
        "id": 1453428309126943015, "emoji": "🚗",
        "label": "GTA V", "sub": "Open World", "icon": "car",
    },
    "Roblox": {
        "id": 1453428932337467545, "emoji": "🧩",
        "label": "Roblox", "sub": "Platform", "icon": "block",
    },
    "HOK (Honor of Kings)": {
        "id": 1453429049870389400, "emoji": "⚔️",
        "label": "HOK", "sub": "Honor of Kings", "icon": "swords",
    },
    "Free Fire": {
        "id": 1466748111555788972, "emoji": "🔥",
        "label": "Free Fire", "sub": "Battle Royale", "icon": "flame",
    },
    "Efootball": {
        "id": 1508719481289965639, "emoji": "⚽",
        "label": "Efootball", "sub": "Sepak Bola", "icon": "ball",
    },
    "EA FC": {
        "id": 1508719106415788103, "emoji": "🏆",
        "label": "EA FC", "sub": "Sepak Bola", "icon": "trophy",
    },
}

MAX_PICK = 5  # maksimal game yang bisa dipilih sekali pilih di menu

EMBED_COLOR = 0x8B5CF6
COLOR_OK = 0x57F287
COLOR_REMOVE = 0xED4245
COLOR_WARN = 0xFEE75C

# ══════════════════════════════════════════════
#  PNG GENERATOR (style sama dengan booster & minat)
# ══════════════════════════════════════════════
FONT_BOLD = "fonts/LEMONMILK-Bold.otf"
FONT_MEDIUM = "fonts/LEMONMILK-Medium.otf"
FONT_REGULAR = "fonts/LEMONMILK-Regular.otf"
_FALLBACKS = (
    "DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "arial.ttf",
)

BG_TOP, BG_BOT = (18, 10, 45), (40, 20, 80)
PURPLE = (130, 80, 255)
BLUE = (80, 180, 255)
CARD_BG = (30, 15, 65)
SOFT_PURPLE = (160, 120, 255)
SOFT_BLUE = (150, 210, 255)
DARK_ICON = (60, 40, 120)

# warna aksen kartu (semua keluarga biru-ungu), dipakai bergantian
ACCENTS = [
    (100, 140, 255), (80, 180, 255), (130, 80, 255),
    (170, 110, 255), (60, 160, 255), (150, 90, 255),
]

W, H = 900, 525


def _font(path, size):
    for p in (path, *_FALLBACKS):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _lerp(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))


def _spk(x, y, s):
    q = s * 0.25
    return [(x, y - s), (x + q, y - q), (x + s, y), (x + q, y + q),
            (x, y + s), (x - q, y + q), (x - s, y), (x - q, y - q)]


def _fit(draw, text, path, start, max_w, min_size=8):
    size = start
    while size > min_size:
        f = _font(path, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 1
    return _font(path, min_size)


def _rot(pts, ang, cx, cy):
    c, s = math.cos(ang), math.sin(ang)
    return [(cx + (px - cx) * c - (py - cy) * s, cy + (px - cx) * s + (py - cy) * c) for px, py in pts]


def _icon(d, key, x, y):
    w = (255, 255, 255, 255)
    dk = (*DARK_ICON, 255)
    if key == "helmet":
        d.pieslice([x - 13, y - 13, x + 13, y + 13], 180, 360, fill=w)
        d.rounded_rectangle([x - 15, y, x + 15, y + 5], radius=2, fill=w)
        d.rectangle([x - 11, y + 5, x - 7, y + 10], fill=w)
        d.rectangle([x + 7, y + 5, x + 11, y + 10], fill=w)
        d.line([(x, y - 11), (x, y - 2)], fill=dk, width=2)
    elif key == "delta":
        d.polygon([(x, y - 14), (x + 14, y + 11), (x - 14, y + 11)], fill=w)
        d.polygon([(x, y - 4), (x + 6, y + 7), (x - 6, y + 7)], fill=dk)
    elif key == "crosshair":
        d.ellipse([x - 9, y - 9, x + 9, y + 9], outline=w, width=3)
        for a, b, c, e in [(-14, 0, -6, 0), (6, 0, 14, 0), (0, -14, 0, -6), (0, 6, 0, 14)]:
            d.line([(x + a, y + b), (x + c, y + e)], fill=w, width=3)
        d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=w)
    elif key == "cube":
        d.polygon([(x, y - 13), (x + 12, y - 6), (x, y + 1), (x - 12, y - 6)], fill=w)
        d.polygon([(x - 12, y - 6), (x, y + 1), (x, y + 14), (x - 12, y + 7)], fill=(225, 225, 245, 255))
        d.polygon([(x, y + 1), (x + 12, y - 6), (x + 12, y + 7), (x, y + 14)], fill=(190, 190, 225, 255))
    elif key == "phone":
        d.rounded_rectangle([x - 8, y - 13, x + 8, y + 13], radius=3, fill=w)
        d.rectangle([x - 6, y - 10, x + 6, y + 7], fill=dk)
        d.line([(x - 3, y + 4), (x + 3, y - 6)], fill=w, width=2)
        d.ellipse([x - 2, y + 9, x + 2, y + 12], fill=dk)
    elif key == "car":
        d.rounded_rectangle([x - 14, y - 1, x + 14, y + 7], radius=3, fill=w)
        d.polygon([(x - 8, y - 1), (x - 5, y - 8), (x + 5, y - 8), (x + 9, y - 1)], fill=w)
        d.polygon([(x - 6, y - 2), (x - 4, y - 6), (x, y - 6), (x, y - 2)], fill=dk)
        d.polygon([(x + 1, y - 2), (x + 1, y - 6), (x + 4, y - 6), (x + 7, y - 2)], fill=dk)
        for wx in (x - 8, x + 8):
            d.ellipse([wx - 3, y + 4, wx + 3, y + 10], fill=dk, outline=w, width=2)
    elif key == "block":
        sq = _rot([(x - 11, y - 11), (x + 11, y - 11), (x + 11, y + 11), (x - 11, y + 11)], 0.35, x, y)
        d.polygon(sq, fill=w)
        d.polygon(_rot([(x - 4, y - 4), (x + 4, y - 4), (x + 4, y + 4), (x - 4, y + 4)], 0.35, x, y), fill=dk)
    elif key == "swords":
        d.line([(x - 11, y + 11), (x + 9, y - 9)], fill=w, width=4)
        d.line([(x + 11, y + 11), (x - 9, y - 9)], fill=w, width=4)
        d.line([(x - 11, y + 3), (x - 3, y + 11)], fill=w, width=3)
        d.line([(x + 11, y + 3), (x + 3, y + 11)], fill=w, width=3)
    elif key == "flame":
        d.polygon([(x, y - 14), (x + 5, y - 6), (x + 10, y + 1), (x + 9, y + 8), (x + 4, y + 13),
                   (x - 4, y + 13), (x - 9, y + 8), (x - 9, y), (x - 5, y - 4), (x - 4, y - 9)], fill=w)
        d.polygon([(x, y + 1), (x + 4, y + 6), (x + 3, y + 10), (x - 3, y + 10), (x - 4, y + 6)], fill=dk)
    elif key == "ball":
        d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=w)
        pent = [(x + 5 * math.cos(math.radians(-90 + 72 * k)),
                 y + 5 * math.sin(math.radians(-90 + 72 * k))) for k in range(5)]
        d.polygon(pent, fill=dk)
        for k in range(5):
            a = math.radians(-90 + 72 * k)
            d.line([(x + 5 * math.cos(a), y + 5 * math.sin(a)),
                    (x + 11 * math.cos(a), y + 11 * math.sin(a))], fill=dk, width=2)
    else:  # trophy
        d.polygon([(x - 9, y - 12), (x + 9, y - 12), (x + 7, y), (x + 3, y + 4),
                   (x - 3, y + 4), (x - 7, y)], fill=w)
        d.arc([x - 15, y - 11, x - 5, y - 1], 90, 270, fill=w, width=2)
        d.arc([x + 5, y - 11, x + 15, y - 1], -90, 90, fill=w, width=2)
        d.rectangle([x - 2, y + 4, x + 2, y + 8], fill=w)
        d.rounded_rectangle([x - 7, y + 8, x + 7, y + 12], radius=1, fill=w)


def render_game_banner() -> bytes:
    rng = random.Random(9)

    # ── Background gradasi ──
    bg = Image.new("RGB", (W, H))
    bd = ImageDraw.Draw(bg)
    for y in range(H):
        bd.line([(0, y), (W, y)], fill=_lerp(BG_TOP, BG_BOT, y / H))
    base = bg.convert("RGBA")

    # ── Orb glow ungu & biru ──
    orbs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(orbs)
    for ox, oy, br, oc in [(W * .05, H * .15, 230, PURPLE), (W * .95, H * .80, 240, BLUE),
                           (W * .50, 0, 170, PURPLE), (W * .12, H, 180, BLUE),
                           (W * .88, H * .10, 150, PURPLE)]:
        for st in range(br, 0, -5):
            od.ellipse([ox - st, oy - st, ox + st, oy + st],
                       fill=(*oc, _clamp(150 * (1 - st / br) ** 1.4)))
    base = Image.alpha_composite(base, orbs.filter(ImageFilter.GaussianBlur(10)))

    # ── Aurora ──
    aur = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ad = ImageDraw.Draw(aur)
    for by, amp, k, off, col, a in [(370, 34, 2, 0.0, BLUE, 110), (405, 28, 3, 2.0, PURPLE, 130),
                                    (445, 20, 4, 4.0, SOFT_BLUE, 90)]:
        pts = [(x, by + amp * math.sin(math.tau * k * x / W + off)) for x in range(0, W + 10, 10)]
        ad.polygon(pts + [(W, H), (0, H)], fill=(*col, a))
    base = Image.alpha_composite(base, aur.filter(ImageFilter.GaussianBlur(6)))

    # ── Bintang, sparkle, bubble ──
    fl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fl)
    for _ in range(90):
        x, y, r, tw = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1, 2.5), rng.random()
        fd.ellipse([x - r, y - r, x + r, y + r],
                   fill=(*_lerp(PURPLE, BLUE, tw), _clamp(rng.randint(90, 200) * (.45 + .55 * tw))))
    for _ in range(16):
        x, y = rng.uniform(15, W - 15), rng.uniform(12, H - 12)
        s, tw = rng.uniform(5, 10), rng.uniform(.4, 1)
        fd.polygon(_spk(x, y, s * (.35 + .65 * tw)),
                   fill=(*_lerp(SOFT_BLUE, SOFT_PURPLE, tw), _clamp(70 + 185 * tw)))
    for _ in range(20):
        x, y, r, a = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(3, 7), rng.randint(80, 150)
        fd.ellipse([x - r, y - r, x + r, y + r], outline=(255, 255, 255, a), width=1)
    base = Image.alpha_composite(base, fl)

    cx = W // 2
    t = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(t)

    # ── Pill nanZ Server ──
    pil = "nanZ Server"
    f_pil = _font(FONT_MEDIUM, 13)
    pw = int(td.textlength(pil, font=f_pil)) + 56
    px = cx - pw // 2
    td.rounded_rectangle([px, 26, px + pw, 56], radius=15, fill=(*PURPLE, 230))
    td.polygon(_spk(px + 20, 41, 7), fill=(255, 255, 255, 255))
    td.text((px + 36, 41), pil, font=f_pil, fill=(255, 255, 255, 255), anchor="lm")

    # ── Judul besar ──
    size = 76
    while size > 40:
        FT = _font(FONT_BOLD, size)
        w1 = td.textlength("ROLE ", font=FT)
        w2 = td.textlength("GAME", font=FT)
        if w1 + w2 <= 720:
            break
        size -= 2
    x0, ty = cx - (w1 + w2) / 2, 112

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gg = ImageDraw.Draw(glow)
    gg.text((x0, ty), "ROLE ", font=FT, fill=(*PURPLE, 160), anchor="lm")
    gg.text((x0 + w1, ty), "GAME", font=FT, fill=(*BLUE, 160), anchor="lm")
    base = Image.alpha_composite(base, glow.filter(ImageFilter.GaussianBlur(14)))

    td.text((x0, ty), "ROLE ", font=FT, fill=(255, 255, 255, 255), anchor="lm")
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).text((x0 + w1, ty), "GAME", font=FT, fill=255, anchor="lm")
    grad = Image.new("RGBA", (W, H))
    gd_ = ImageDraw.Draw(grad)
    for x in range(W):
        gd_.line([(x, 0), (x, H)], fill=(*_lerp(SOFT_BLUE, SOFT_PURPLE, (x - x0 - w1) / w2), 255))
    t.paste(grad, (0, 0), mask)

    # ── Subjudul + garis ──
    sub = "Pilih game favorit kamu"
    f_sub = _fit(td, sub, FONT_REGULAR, 14, 420)
    sw = td.textlength(sub, font=f_sub)
    sy = 176
    td.text((cx, sy), sub, font=f_sub, fill=(225, 225, 245, 255), anchor="mm")
    for k in range(150):
        fa = (1 - k / 150) ** .8
        c = (*_lerp(BLUE, PURPLE, k / 150), _clamp(255 * fa))
        td.line([(cx - sw / 2 - 18 - k, sy), (cx - sw / 2 - 18 - k, sy + 1)], fill=c)
        td.line([(cx + sw / 2 + 18 + k, sy), (cx + sw / 2 + 18 + k, sy + 1)], fill=c)
    td.polygon(_spk(cx - sw / 2 - 180, sy, 6), fill=(*SOFT_BLUE, 235))
    td.polygon(_spk(cx + sw / 2 + 180, sy, 6), fill=(*SOFT_PURPLE, 235))
    base = Image.alpha_composite(base, t)

    # ── Kartu game: baris 1 = 6 kartu, baris 2 = 5 kartu (rata tengah) ──
    CW, CH, GAP = 130, 124, 12
    ROWS = [(210, 6), (210 + CH + GAP, 5)]
    cards = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cards)
    items = list(GAME_ROLES.items())
    idx = 0
    for gy, count in ROWS:
        gx = (W - (count * CW + (count - 1) * GAP)) // 2
        for j in range(count):
            if idx >= len(items):
                break
            name, data = items[idx]
            col = ACCENTS[idx % len(ACCENTS)]
            x, y = gx + j * (CW + GAP), gy

            sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(sh).rounded_rectangle([x, y + 5, x + CW, y + CH + 5], radius=22, fill=(*col, 95))
            base = Image.alpha_composite(base, sh.filter(ImageFilter.GaussianBlur(12)))

            cd.rounded_rectangle([x, y, x + CW, y + CH], radius=22,
                                 fill=(*_lerp(CARD_BG, col, .22), 228), outline=(*col, 235), width=2)
            ccx, ccy = x + CW // 2, y + 44
            for rr, al in [(38, 14), (33, 22)]:
                cd.ellipse([ccx - rr, ccy - rr, ccx + rr, ccy + rr], fill=(*col, al))
            cd.ellipse([ccx - 27, ccy - 27, ccx + 27, ccy + 27], fill=(*col, 255))
            _icon(cd, data["icon"], ccx, ccy)

            cd.text((x + 14, y + 15), f"{idx + 1:02d}", font=_font(FONT_BOLD, 10), fill=(*col, 255), anchor="lm")
            f_name = _fit(cd, data["label"], FONT_BOLD, 13, CW - 14)
            cd.text((ccx, y + 87), data["label"], font=f_name, fill=(255, 255, 255, 255), anchor="mm")
            f_s = _fit(cd, data["sub"], FONT_REGULAR, 10, CW - 16)
            cd.text((ccx, y + 105), data["sub"], font=f_s, fill=(*SOFT_BLUE, 255), anchor="mm")
            idx += 1
    base = Image.alpha_composite(base, cards)

    # ── Garis warna atas & bawah ──
    bands = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bnd = ImageDraw.Draw(bands)
    for x in range(W):
        c = _lerp(BLUE, PURPLE, x / W)
        bnd.line([(x, 0), (x, 4)], fill=(*c, 255))
        bnd.line([(x, H - 4), (x, H)], fill=(*c, 255))
    base = Image.alpha_composite(base, bands)

    # ── Footer ──
    d = ImageDraw.Draw(base)
    f_ft = _font(FONT_REGULAR, 12)
    a, b = "Bisa pilih lebih dari satu", "Lepas kapan saja"
    wa, wb = d.textlength(a, font=f_ft), d.textlength(b, font=f_ft)
    total = wa + wb + 24
    fx, fy = cx - total / 2, H - 26
    d.text((fx, fy), a, font=f_ft, fill=(200, 200, 230, 220), anchor="lm")
    d.ellipse([fx + wa + 10, fy - 2, fx + wa + 14, fy + 2], fill=(200, 200, 230, 220))
    d.text((fx + wa + 24, fy), b, font=f_ft, fill=(200, 200, 230, 220), anchor="lm")
    d.polygon(_spk(fx - 16, fy, 5), fill=(*SOFT_BLUE, 235))
    d.polygon(_spk(fx + total + 16, fy, 5), fill=(*SOFT_PURPLE, 235))

    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


# ══════════════════════════════════════════════
#  HELPER
# ══════════════════════════════════════════════
def _embed(text: str, color: int) -> discord.Embed:
    return discord.Embed(description=text, color=color)


def _fmt(name: str, role: discord.Role) -> str:
    return f"{GAME_ROLES[name]['emoji']} {role.mention}"


def _owned_roles(member: discord.Member):
    """Role game yang sedang dimiliki member -> list of (name, role)."""
    owned = []
    for name, data in GAME_ROLES.items():
        role = member.guild.get_role(data["id"])
        if role and role in member.roles:
            owned.append((name, role))
    return owned


NO_PERM = ("⚠️ Bot tidak punya izin untuk mengatur role ini. "
           "Pastikan role bot berada di atas role game.")


# ══════════════════════════════════════════════
#  SELECT: AMBIL ROLE (persistent)
# ══════════════════════════════════════════════
class GameSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=name, value=str(data["id"]), emoji=data["emoji"])
            for name, data in GAME_ROLES.items()
        ]
        super().__init__(
            placeholder="🎮 Pilih game favorit kamu...",
            min_values=1,
            max_values=min(MAX_PICK, len(options)),
            options=options,
            custom_id="game_roles_select",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        member = interaction.user
        selected = {int(v) for v in self.values}
        to_add, already = [], []

        for name, data in GAME_ROLES.items():
            if data["id"] not in selected:
                continue
            role = interaction.guild.get_role(data["id"])
            if not role:
                continue
            (already if role in member.roles else to_add).append((name, role))

        try:
            if to_add:
                await member.add_roles(*[r for _, r in to_add], reason="Role game")
        except discord.Forbidden:
            await interaction.followup.send(embed=_embed(NO_PERM, COLOR_WARN), ephemeral=True)
            return

        lines = []
        if to_add:
            lines.append(f"✅ Role {', '.join(_fmt(n, r) for n, r in to_add)} berhasil diambil.")
        if already:
            lines.append(f"⚠️ Kamu sudah punya {', '.join(_fmt(n, r) for n, r in already)}.")

        await interaction.followup.send(
            embed=_embed("\n".join(lines) or "⚠️ Tidak ada perubahan role.",
                         COLOR_OK if to_add else COLOR_WARN),
            ephemeral=True,
        )

        # reset pilihan di menu panel
        try:
            await interaction.message.edit(view=GameView())
        except discord.HTTPException:
            pass


# ══════════════════════════════════════════════
#  SELECT: LEPAS ROLE (ephemeral)
# ══════════════════════════════════════════════
class RemoveSelect(discord.ui.Select):
    def __init__(self, owned):
        options = [
            discord.SelectOption(label=name, value=str(role.id), emoji=GAME_ROLES[name]["emoji"])
            for name, role in owned
        ]
        super().__init__(
            placeholder="Pilih role yang mau dilepas...",
            min_values=1,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        chosen = {int(v) for v in self.values}
        removed = [(n, r) for n, r in _owned_roles(member) if r.id in chosen]

        try:
            if removed:
                await member.remove_roles(*[r for _, r in removed], reason="Lepas role game")
        except discord.Forbidden:
            await interaction.response.edit_message(embed=_embed(NO_PERM, COLOR_WARN), view=None)
            return

        if removed:
            embed = _embed(
                f"❌ Role {', '.join(_fmt(n, r) for n, r in removed)} berhasil dilepas.",
                COLOR_REMOVE,
            )
        else:
            embed = _embed("⚠️ Tidak ada perubahan role.", COLOR_WARN)

        await interaction.response.edit_message(embed=embed, view=None)


class RemoveView(discord.ui.View):
    def __init__(self, owned):
        super().__init__(timeout=90)
        self.add_item(RemoveSelect(owned))


# ══════════════════════════════════════════════
#  VIEW PANEL (persistent, aktif terus walau bot restart)
# ══════════════════════════════════════════════
class GameView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(GameSelect())

    @discord.ui.button(
        label="Lepas Role",
        emoji="🗑️",
        style=discord.ButtonStyle.secondary,
        custom_id="game_roles_remove",
        row=1,
    )
    async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        owned = _owned_roles(interaction.user)
        if not owned:
            await interaction.response.send_message(
                embed=_embed("⚠️ Kamu belum punya role game.", COLOR_WARN), ephemeral=True
            )
            return

        await interaction.response.send_message(
            embed=_embed("Pilih role yang mau dilepas:", EMBED_COLOR),
            view=RemoveView(owned),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Lepas Semua",
        emoji="🧹",
        style=discord.ButtonStyle.danger,
        custom_id="game_roles_clear",
        row=1,
    )
    async def clear_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        owned = _owned_roles(interaction.user)
        if not owned:
            await interaction.response.send_message(
                embed=_embed("⚠️ Kamu belum punya role game.", COLOR_WARN), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.user.remove_roles(*[r for _, r in owned], reason="Lepas semua role game")
        except discord.Forbidden:
            await interaction.followup.send(embed=_embed(NO_PERM, COLOR_WARN), ephemeral=True)
            return

        await interaction.followup.send(
            embed=_embed("🧹 Semua role game kamu sudah dilepas.", COLOR_REMOVE), ephemeral=True
        )


# ══════════════════════════════════════════════
#  COG
# ══════════════════════════════════════════════
class GameRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Daftarkan view persistent supaya panel lama tetap aktif setelah bot restart
        self.bot.add_view(GameView())

    @commands.command(name="setup_game")
    @commands.has_permissions(administrator=True)
    async def setup_game(self, ctx):
        loop = asyncio.get_running_loop()
        png = await loop.run_in_executor(None, render_game_banner)
        file = discord.File(io.BytesIO(png), filename="game.png")

        embed = discord.Embed(
            title="Role Game",
            description=(
                "Pilih game favorit kamu.\n"
                "Bisa lebih dari satu, dan bisa dilepas kapan saja."
            ),
            color=EMBED_COLOR,
        )
        embed.set_image(url="attachment://game.png")
        embed.set_footer(text="nanZ Server")

        await ctx.send(embed=embed, view=GameView(), file=file)

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass


# ══════════════════════════════════════════════
#  SETUP
# ══════════════════════════════════════════════
async def setup(bot):
    await bot.add_cog(GameRoles(bot))