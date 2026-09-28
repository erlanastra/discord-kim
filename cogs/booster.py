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
BOOST_CHANNEL_ID = 1554100419637149838  # ← GANTI dengan ID channel boost nanZ
ROLE_REQ_CHANNEL_ID = 1515029186530771077  # channel request role

# Emoji nanZ (kalau emoji nitro animasi, ganti "<:" jadi "<a:")
E_NITRO  = "<:nitro:1553688995635011635>"
E_BLUE   = "<a:blue:1512787254312042496>"
E_PURPLE = "<a:purple:1512787191234035803>"

# ══════════════════════════════════════════════
#  PNG GENERATOR (style sama dengan welcome, tapi statis)
# ══════════════════════════════════════════════
FONT_BOLD    = "fonts/LEMONMILK-Bold.otf"
FONT_MEDIUM  = "fonts/LEMONMILK-Medium.otf"
FONT_REGULAR = "fonts/LEMONMILK-Regular.otf"
FONT_LIGHT   = "fonts/LEMONMILK-Light.otf"
_FALLBACKS   = ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf")

BG_TOP, BG_BOT = (18, 10, 45), (40, 20, 80)
PURPLE = (130, 80, 255)
BLUE = (80, 180, 255)
CARD_BG = (30, 15, 65)
SOFT_PURPLE = (160, 120, 255)
SOFT_BLUE = (150, 210, 255)

W, H = 800, 340
AV = 120
CARD = (20, 20, 780, 320)
ZONE = (38, 38, 262, 302)
AV_CX, AV_CY = 150, 146
RX0, RX1 = 296, 754


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
        if max(draw.textlength(l, font=f) for l in lines) <= max_w:
            return f
        size -= 1
    return _font(path, min_size)


def _prepare_avatar(avatar_bytes, size=AV):
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


def _background(fx):
    bg = Image.new("RGB", (W, H))
    bd = ImageDraw.Draw(bg)
    for y in range(H):
        bd.line([(0, y), (W, y)], fill=_lerp_color(BG_TOP, BG_BOT, y / H))
    base = bg.convert("RGBA")

    orbs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od0 = ImageDraw.Draw(orbs)
    for ox, oy, br, oc in [(W * .10, H * .20, 140, PURPLE), (W * .90, H * .70, 140, BLUE),
                           (W * .50, H * .00, 110, PURPLE)]:
        for st in range(br, 0, -5):
            od0.ellipse([ox - st, oy - st, ox + st, oy + st],
                        fill=(*oc, _clamp(60 * (st / br) ** 2.8 * 0.85)))
    base = Image.alpha_composite(base, orbs)

    aur = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ad = ImageDraw.Draw(aur)
    for by, amp, k, off, col, a in [(235, 30, 2, 0.0, BLUE, 60), (268, 24, 3, 2.0, PURPLE, 75),
                                    (300, 18, 4, 4.0, SOFT_BLUE, 50)]:
        pts = [(x, by + amp * math.sin(math.tau * k * x / W + off)) for x in range(0, W + 10, 10)]
        ad.polygon(pts + [(W, H), (0, H)], fill=(*col, a))
    base = Image.alpha_composite(base, aur.filter(ImageFilter.GaussianBlur(6)))

    fl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fl)
    for p in fx["stars"]:
        r, tw = p["r"], p["tw"]
        fd.ellipse([p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r],
                   fill=(*_lerp_color(PURPLE, BLUE, tw), _clamp(p["a"] * (0.45 + 0.55 * tw))))
    for p in fx["sparkles"]:
        tw = p["tw"]
        fd.polygon(_sparkle_poly(p["x"], p["y"], p["s"] * (0.35 + 0.65 * tw)),
                   fill=(*_lerp_color(SOFT_BLUE, SOFT_PURPLE, tw), _clamp(70 + 185 * tw)))
    for b in fx["bubbles"]:
        r, a = b["r"], b["a"]
        fd.ellipse([b["x"] - r, b["y"] - r, b["x"] + r, b["y"] + r], outline=(255, 255, 255, a), width=1)
        fd.ellipse([b["x"] - r * .35, b["y"] - r * .35, b["x"] + r * .1, b["y"] + r * .1],
                   fill=(255, 255, 255, a))
    return Image.alpha_composite(base, fl)


def render_booster_card(avatar_bytes: bytes, name: str, tier: int, total: int) -> bytes:
    """Layout poster/spotlight: panel miring di kiri untuk teks, avatar besar dengan cincin di kanan (tanpa kartu)."""
    AVB = 176                                   # ukuran avatar besar
    avatar = _prepare_avatar(avatar_bytes, AVB)
    base = _background(_make_fx(seed=11))
    cx, cy = 662, 170
    TX0, TX1 = 46, 440

    def edge(y):                                # sisi miring panel
        return 560 - 90 * y / H

    # ── Panel miring (supersampled biar halus) ──
    S = 2
    pan = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    pdr = ImageDraw.Draw(pan)
    pdr.polygon([(0, 0), (edge(0) * S, 0), (edge(H) * S, H * S), (0, H * S)], fill=(*CARD_BG, 190))
    for y in range(0, H, 3):
        pdr.line([(edge(y) * S, y * S), (edge(y + 3) * S, (y + 3) * S)],
                 fill=(*_lerp_color(BLUE, PURPLE, y / H), 255), width=7)
    for y in range(0, H, 3):                    # garis tipis kedua, sejajar
        pdr.line([((edge(y) - 14) * S, y * S), ((edge(y + 3) - 14) * S, (y + 3) * S)],
                 fill=(*_lerp_color(BLUE, PURPLE, y / H), 90), width=3)
    pan = pan.resize((W, H), Image.LANCZOS)
    base = Image.alpha_composite(base, pan)

    # ── Spotlight + avatar + cincin ──
    spot = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spot)
    for r, a in [(190, 40), (160, 55), (135, 70)]:
        sd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*PURPLE, a))
    base = Image.alpha_composite(base, spot.filter(ImageFilter.GaussianBlur(22)))

    rr = AVB // 2 + 12
    rg = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse([cx - rr - 26, cy - rr - 26, cx + rr + 26, cy + rr + 26], outline=(255, 255, 255, 40), width=1)
    rd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(255, 255, 255, 60), width=2)
    box = [cx - rr, cy - rr, cx + rr, cy + rr]
    rd.arc(box, -70, 40, fill=(*SOFT_BLUE, 255), width=6)
    rd.arc(box, 110, 220, fill=(*SOFT_PURPLE, 255), width=6)
    for i in range(8):
        a = i * math.tau / 8 + 0.3
        R2 = rr + 26
        px, py = cx + R2 * math.cos(a), cy + R2 * math.sin(a)
        rad = 4 if i % 2 == 0 else 3
        rd.ellipse([px - rad, py - rad, px + rad, py + rad],
                   fill=(*(SOFT_BLUE if i % 2 == 0 else SOFT_PURPLE), 235))
    for sx, sy, sz in [(cx - 118, cy - 96, 11), (cx + 120, cy - 82, 9), (cx + 104, cy + 100, 12)]:
        rd.polygon(_sparkle_poly(sx, sy, sz), fill=(*SOFT_BLUE, 235))
    base = Image.alpha_composite(base, ring)
    base.alpha_composite(avatar, (cx - AVB // 2, cy - AVB // 2))

    # badge bintang
    bx, by, br = cx + 66, cy + 66, 18
    bd = ImageDraw.Draw(base)
    bd.ellipse([bx - br - 4, by - br - 4, bx + br + 4, by + br + 4], fill=(*CARD_BG, 255))
    bd.ellipse([bx - br, by - br, bx + br, by + br], fill=(*PURPLE, 255))
    bd.polygon(_sparkle_poly(bx, by, 12), fill=(255, 255, 255, 255))

    # ── Teks di panel ──
    tl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(tl)
    f_pil = _font(FONT_MEDIUM, 14)
    f_lab = _font(FONT_MEDIUM, 15)

    pil = "MURID BOOSTER"
    pw = int(td.textlength(pil, font=f_pil)) + 56
    td.rounded_rectangle([TX0, 32, TX0 + pw, 62], radius=15, fill=(*PURPLE, 230))
    td.polygon(_sparkle_poly(TX0 + 20, 47, 7), fill=(255, 255, 255, 255))
    td.text((TX0 + 36, 47), pil, font=f_pil, fill=(255, 255, 255, 255), anchor="lm")

    td.text((TX0, 96), "TERIMA KASIH,", font=f_lab, fill=(*SOFT_BLUE, 255), anchor="lm")
    f_name, name_fit = _fit_font(td, name, FONT_BOLD, 52, TX1 - TX0)
    td.text((TX0, 140), name_fit, font=f_name, fill=(255, 255, 255, 255), anchor="lm")

    for x in range(TX0, TX0 + 260):             # garis gradasi memudar
        f = 1 - (x - TX0) / 260
        c = (*_lerp_color(BLUE, PURPLE, (x - TX0) / 260), _clamp(255 * f ** 0.7))
        td.line([(x, 176), (x, 178)], fill=c)

    lines = ["Boost kamu bikin sekolah nanZ makin keren,",
             "makasih udah jadi murid yang peduli sama sekolah!"]
    f_body = _fit_size(td, lines, FONT_REGULAR, 16, TX1 - TX0)
    td.text((TX0, 204), lines[0], font=f_body, fill=(225, 225, 245, 255), anchor="lm")
    td.text((TX0, 230), lines[1], font=f_body, fill=(225, 225, 245, 255), anchor="lm")

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

    nx = chip(TX0, c1, BLUE)
    chip(nx + 12, c2, PURPLE)

    base = Image.alpha_composite(base, tl)
    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


# ══════════════════════════════════════════════
#  BOOSTER COG
# ══════════════════════════════════════════════
class Booster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_boost_embed(self, member: discord.Member):
        channel = member.guild.get_channel(BOOST_CHANNEL_ID)
        if channel is None:
            print(f"[Booster] Channel {BOOST_CHANNEL_ID} tidak ditemukan!")
            return

        tier = member.guild.premium_tier
        total = member.guild.premium_subscription_count

        # ── bikin PNG ──
        file = None
        try:
            avatar_bytes = await member.display_avatar.replace(size=256, format="png").read()
            loop = asyncio.get_running_loop()
            png_bytes = await loop.run_in_executor(
                None, render_booster_card, avatar_bytes, member.display_name, tier, total
            )
            file = discord.File(io.BytesIO(png_bytes), filename="booster.png")
        except Exception as e:
            print(f"[Booster] gagal bikin PNG: {e}")

        embed = discord.Embed(
            title="Murid Teladan Baru Ngeboost nanZ!",
            description=(
                f"{E_NITRO} Terima kasih {member.mention}, murid yang sudah ngeboost **nanZ Server**!\n\n"
                f"{E_PURPLE} Boost kamu bikin sekolah kita makin keren dan punya perks baru buat semua murid.\n"
                f"{E_PURPLE} Dukunganmu sangat berarti buat seluruh murid nanZ!\n\n"
                f"{E_BLUE} `Request role:` <#{ROLE_REQ_CHANNEL_ID}>"
            ),
            color=discord.Color.from_rgb(130, 80, 255),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Level Boost nanZ", value=f"{E_NITRO} Level {tier}", inline=True)
        embed.add_field(name="Total Boost", value=f"{E_NITRO} {total}", inline=True)
        embed.set_footer(text="nanZ Server Boost System")

        kwargs = {}
        if file:
            embed.set_image(url="attachment://booster.png")
            kwargs["file"] = file

        await channel.send(
            content=member.mention,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(users=True),
            **kwargs,
        )

    # 🔥 AUTO DETECT BOOST
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.premium_since is None and after.premium_since is not None:
            await self.send_boost_embed(after)

    # 🧪 COMMAND TEST
    @commands.command(name="test_boost")
    @commands.has_permissions(administrator=True)
    async def test_boost(self, ctx, member: discord.Member = None):
        await self.send_boost_embed(member or ctx.author)
        await ctx.send("Test boost berhasil dikirim!")


async def setup(bot):
    await bot.add_cog(Booster(bot))