import asyncio
import io
import math
import random

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ══════════════════════════════════════════════
#  GIF GENERATOR
# ══════════════════════════════════════════════
FONT_BOLD    = "fonts/LEMONMILK-Bold.otf"
FONT_MEDIUM  = "fonts/LEMONMILK-Medium.otf"
FONT_REGULAR = "fonts/LEMONMILK-Regular.otf"
FONT_LIGHT   = "fonts/LEMONMILK-Light.otf"
_FALLBACKS   = ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf")

# Tema biru + ungu (sama dengan greeting)
BG_TOP, BG_BOT = (18, 10, 45), (40, 20, 80)
PURPLE = (130, 80, 255)          # accent1
BLUE = (80, 180, 255)            # accent2
CARD_BG = (30, 15, 65)
SOFT_PURPLE = (160, 120, 255)    # label
SOFT_BLUE = (150, 210, 255)

W, H = 800, 340
TOTAL_FRAMES = 36
FPS_DELAY = 8                    # centiseconds per frame
AV = 140
CARD = (20, 20, 780, 320)        # card utama
ZONE = (38, 38, 262, 302)        # zona avatar (kiri)
AV_CX, AV_CY = 150, 146
RX0, RX1 = 296, 754              # area konten kanan


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


def _ease_out(t):
    return 1 - (1 - t) ** 3


def _make_fx(seed=42):
    rng = random.Random(seed)
    stars = [{"x": rng.uniform(0, W), "y": rng.uniform(0, H), "r": rng.uniform(1.0, 2.6),
              "k": rng.choice([1, 1, 2]), "sway": rng.uniform(3, 12), "m": rng.choice([1, 2]),
              "ph": rng.uniform(0, math.tau), "a": rng.randint(90, 200)} for _ in range(70)]
    sparkles = [{"x": rng.uniform(15, W - 15), "y": rng.uniform(12, H - 12), "s": rng.uniform(5, 10),
                 "m": rng.choice([1, 2]), "ph": rng.uniform(0, math.tau)} for _ in range(13)]
    bubbles = [{"x": rng.uniform(0, W), "y0": rng.uniform(0, H), "r": rng.uniform(3, 7),
                "speed": rng.choice([1, 1, 2]), "sway": rng.uniform(4, 14), "phase": rng.uniform(0, math.tau)}
               for _ in range(18)]
    return {"stars": stars, "sparkles": sparkles, "bubbles": bubbles}


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


def _prepare_avatar(avatar_bytes):
    av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((AV, AV), Image.LANCZOS)
    mask = Image.new("L", (AV * 4, AV * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, AV * 4, AV * 4), fill=255)
    mask = mask.resize((AV, AV), Image.LANCZOS)
    out = Image.new("RGBA", (AV, AV), (0, 0, 0, 0))
    out.paste(av, (0, 0), mask)
    return out


def _render_frame(idx, avatar, name, fx):
    t = idx / (TOTAL_FRAMES - 1)
    phase = math.tau * idx / TOTAL_FRAMES          # loop mulus
    pulse = (1 + math.sin(phase)) / 2

    # ── Background ──
    bg = Image.new("RGB", (W, H))
    bd = ImageDraw.Draw(bg)
    for y in range(H):
        bd.line([(0, y), (W, y)], fill=_lerp_color(BG_TOP, BG_BOT, y / H))
    base = bg.convert("RGBA")

    # Orbs berdenyut
    orbs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od0 = ImageDraw.Draw(orbs)
    for i, (ox, oy, br, oc) in enumerate([(W * .10, H * .20, 140, PURPLE), (W * .90, H * .70, 140, BLUE),
                                          (W * .65, H * .02, 90, PURPLE)]):
        p = (math.sin(phase + i * math.tau / 3) + 1) / 2
        r = int(br * (0.88 + 0.22 * p))
        for st in range(r, 0, -5):
            od0.ellipse([ox - st, oy - st, ox + st, oy + st],
                        fill=(*oc, _clamp(60 * (st / r) ** 2.8 * (0.7 + 0.3 * p))))
    base = Image.alpha_composite(base, orbs)

    # Aurora
    aur = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ad = ImageDraw.Draw(aur)
    for by, amp, k, off, col, a in [(235, 30, 2, 0.0, BLUE, 60), (268, 24, 3, 2.0, PURPLE, 75), (300, 18, 4, 4.0, SOFT_BLUE, 50)]:
        pts = [(x, by + amp * math.sin(math.tau * k * x / W + phase * (1 if k % 2 else -1) + off))
               for x in range(0, W + 10, 10)]
        ad.polygon(pts + [(W, H), (0, H)], fill=(*col, a))
    aur = aur.filter(ImageFilter.GaussianBlur(6))
    base = Image.alpha_composite(base, aur)

    # Partikel: bintang + sparkle + gelembung
    fl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fl)
    for p in fx["stars"]:
        y = (p["y"] - (idx / TOTAL_FRAMES) * H * p["k"] * 0.5) % H
        x = p["x"] + p["sway"] * math.sin(phase * p["m"] + p["ph"])
        tw = (math.sin(phase * p["m"] * 2 + p["ph"]) + 1) / 2
        r = p["r"]
        fd.ellipse([x - r, y - r, x + r, y + r],
                   fill=(*_lerp_color(PURPLE, BLUE, tw), _clamp(p["a"] * (0.45 + 0.55 * tw))))
    for p in fx["sparkles"]:
        tw = (math.sin(phase * p["m"] + p["ph"]) + 1) / 2
        sz = p["s"] * (0.35 + 0.65 * tw)
        x, y, q = p["x"], p["y"], sz * 0.25
        fd.polygon([(x, y - sz), (x + q, y - q), (x + sz, y), (x + q, y + q),
                    (x, y + sz), (x - q, y + q), (x - sz, y), (x - q, y - q)],
                   fill=(*_lerp_color(SOFT_BLUE, SOFT_PURPLE, tw), _clamp(70 + 185 * tw)))
    for b in fx["bubbles"]:
        y = (b["y0"] - (idx / TOTAL_FRAMES) * H * b["speed"]) % H
        x = b["x"] + b["sway"] * math.sin(phase * b["speed"] + b["phase"])
        r = b["r"]
        a = _clamp(70 + 90 * (1 + math.sin(phase * 2 + b["phase"])) / 2)
        fd.ellipse([x - r, y - r, x + r, y + r], outline=(255, 255, 255, a), width=1)
        fd.ellipse([x - r * .35, y - r * .35, x + r * .1, y + r * .1], fill=(255, 255, 255, a))
    base = Image.alpha_composite(base, fl)

    # ── Card utama + zona avatar ──
    pl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pl)
    pd.rounded_rectangle(CARD, radius=30, fill=(*CARD_BG, _clamp(185 + 20 * pulse)))
    pd.rounded_rectangle(CARD, radius=30, outline=(*PURPLE, 90), width=2)
    pd.rounded_rectangle(ZONE, radius=22, fill=(*PURPLE, 38))
    pd.rounded_rectangle(ZONE, radius=22, outline=(*SOFT_PURPLE, 70), width=1)
    # garis aksen gradasi biru→ungu di sisi kiri zona teks
    for i in range(38, 302):
        pd.point((276, i), fill=(*_lerp_color(BLUE, PURPLE, (i - 38) / 264), 200))
        pd.point((277, i), fill=(*_lerp_color(BLUE, PURPLE, (i - 38) / 264), 200))
    base = Image.alpha_composite(base, pl)

    # ── Avatar + orbit ──
    rr = AV // 2 + 12
    R2 = rr + 14
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([AV_CX - rr - 8, AV_CY - rr - 8, AV_CX + rr + 8, AV_CY + rr + 8],
                                 fill=(*_lerp_color(BLUE, PURPLE, pulse), _clamp(60 + 50 * pulse)))
    base = Image.alpha_composite(base, glow.filter(ImageFilter.GaussianBlur(14)))
    orb = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(orb)
    box = [AV_CX - rr, AV_CY - rr, AV_CX + rr, AV_CY + rr]
    od.ellipse(box, outline=(255, 255, 255, 60), width=2)
    ang = math.degrees(phase)
    od.arc(box, ang, ang + 110, fill=(*SOFT_BLUE, 255), width=5)
    od.arc(box, ang + 180, ang + 290, fill=(*SOFT_PURPLE, 255), width=5)
    for i in range(6):
        a = -phase + i * math.tau / 6
        px, py = AV_CX + R2 * math.cos(a), AV_CY + R2 * math.sin(a)
        rad = 3 + 2 * (1 + math.sin(phase * 2 + i)) / 2
        od.ellipse([px - rad, py - rad, px + rad, py + rad],
                   fill=(*(SOFT_BLUE if i % 2 == 0 else SOFT_PURPLE), 230))
    base = Image.alpha_composite(base, orb)
    base.alpha_composite(avatar, (AV_CX - AV // 2, AV_CY - AV // 2))

    # ── Teks & UI ──
    tl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(tl)
    f_pill = _font(FONT_MEDIUM, 14)
    f_tiny = _font(FONT_LIGHT, 13)
    f_med = _font(FONT_MEDIUM, 18)
    f_small = _font(FONT_REGULAR, 16)
    f_step = _font(FONT_MEDIUM, 13)

    def t_alpha(d):
        lt = max(0, (t - d) / (1.0 - d + 0.001))
        return _clamp(255 * _ease_out(min(lt * 2.5, 1.0)))

    def slide(d, mx=16):
        lt = max(0, (t - d) / (1.0 - d + 0.001))
        return int(mx * (1 - _ease_out(min(lt * 2.5, 1.0))))

    # label di bawah avatar
    la = t_alpha(0.05)
    lw = int(td.textlength("MURID BARU", font=f_tiny)) + 30
    td.rounded_rectangle([AV_CX - lw // 2, 262, AV_CX + lw // 2, 286], radius=12,
                         fill=(*PURPLE, _clamp(la * 0.35)), outline=(*SOFT_PURPLE, _clamp(la * 0.8)), width=1)
    td.text((AV_CX, 274), "MURID BARU", font=f_tiny, fill=(255, 255, 255, la), anchor="mm")

    # baris atas: pill + nama server
    a, dy = t_alpha(0.0), slide(0.0)
    pw = int(td.textlength("SELAMAT DATANG", font=f_pill)) + 36
    td.rounded_rectangle([RX0, 52 + dy, RX0 + pw, 80 + dy], radius=14, fill=(*PURPLE, _clamp(a * 0.85)))
    td.text((RX0 + pw / 2, 66 + dy), "SELAMAT DATANG", font=f_pill, fill=(255, 255, 255, a), anchor="mm")
    td.text((RX1, 66 + dy), "nanZ Server", font=f_tiny, fill=(*SOFT_PURPLE, _clamp(a * 0.9)), anchor="rm")

    # nama + subjudul
    f_name, name_fit = _fit_font(td, name, FONT_BOLD, 46, RX1 - RX0)
    td.text((RX0, 122 + slide(0.1)), name_fit, font=f_name, fill=(255, 255, 255, t_alpha(0.1)), anchor="lm")
    td.text((RX0, 166 + slide(0.18)), "Verifikasi kamu sudah masuk.", font=f_med,
            fill=(*SOFT_BLUE, t_alpha(0.18)), anchor="lm")

    # divider tumbuh
    dp = _ease_out(min(max(0, (t - 0.2) * 3), 1.0))
    for i in range(int((RX1 - RX0) * dp)):
        td.line([(RX0 + i, 194), (RX0 + i, 195)],
                fill=(*_lerp_color(PURPLE, BLUE, i / (RX1 - RX0)), 170))

    # stepper: Terkirim -> Diproses -> Selesai
    a = t_alpha(0.28)
    ny = 232
    n1, n2, n3 = RX0 + 24, (RX0 + RX1) // 2, RX1 - 24
    td.line([(n1, ny), (n3, ny)], fill=(255, 255, 255, _clamp(a * 0.16)), width=4)
    for x in range(n1, n2):
        td.line([(x, ny), (x, ny)], fill=(*_lerp_color(BLUE, PURPLE, (x - n1) / (n3 - n1)), a), width=4)
    seg = 64
    pos = n2 - seg + (idx / TOTAL_FRAMES) * (n3 - n2 + seg)
    for x in range(int(max(n2, pos)), int(min(n3, pos + seg))):
        edge = min(x - pos, pos + seg - x) / (seg / 2)
        td.line([(x, ny), (x, ny)], fill=(*_lerp_color(PURPLE, SOFT_PURPLE, edge), _clamp(a * min(1, edge * 1.4))), width=4)
    td.ellipse([n1 - 11, ny - 11, n1 + 11, ny + 11], fill=(*BLUE, a))
    td.line([(n1 - 5, ny), (n1 - 1, ny + 4), (n1 + 6, ny - 4)], fill=(255, 255, 255, a), width=3)
    hr = 13 + 6 * pulse
    td.ellipse([n2 - hr, ny - hr, n2 + hr, ny + hr], outline=(*SOFT_PURPLE, _clamp(a * (0.9 - 0.6 * pulse))), width=2)
    td.ellipse([n2 - 11, ny - 11, n2 + 11, ny + 11], fill=(*PURPLE, a))
    td.ellipse([n2 - 4, ny - 4, n2 + 4, ny + 4], fill=(255, 255, 255, a))
    td.ellipse([n3 - 11, ny - 11, n3 + 11, ny + 11], outline=(255, 255, 255, _clamp(a * 0.4)), width=3)
    sa = t_alpha(0.33)
    td.text((n1, ny + 26), "Terkirim", font=f_step, fill=(*SOFT_BLUE, sa), anchor="mm")
    td.text((n2, ny + 26), "Diproses", font=f_step, fill=(255, 255, 255, sa), anchor="mm")
    td.text((n3, ny + 26), "Selesai", font=f_step, fill=(255, 255, 255, _clamp(sa * 0.45)), anchor="mm")

    # pesan bawah
    td.text((RX0, 286 + slide(0.42, 12)), "Mohon tunggu staff memproses ya.", font=f_small,
            fill=(215, 215, 240, t_alpha(0.42)), anchor="lm")

    # ── Shimmer diagonal di dalam card ──
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sp = int((idx / TOTAL_FRAMES) * (W + 300)) - 150
    for k in range(-24, 25):
        sd.line([(sp + k + 60, 0), (sp + k - 60, H)], fill=(255, 255, 255, _clamp(26 * (1 - abs(k) / 24))), width=2)
    cm = Image.new("L", (W, H), 0)
    ImageDraw.Draw(cm).rounded_rectangle(CARD, radius=30, fill=255)
    sh.putalpha(Image.composite(sh.getchannel("A"), Image.new("L", (W, H), 0), cm))
    base = Image.alpha_composite(base, sh)

    base = Image.alpha_composite(base, tl)
    return base.convert("RGB")


def generate_verify_gif(avatar_bytes: bytes, name: str) -> bytes:
    avatar = _prepare_avatar(avatar_bytes)
    fx = _make_fx()

    frames = []
    for i in range(TOTAL_FRAMES):
        f = _render_frame(i, avatar, name, fx)
        frames.append(f.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=1))

    out = io.BytesIO()
    frames[0].save(out, format="GIF", save_all=True, append_images=frames[1:],
                   loop=0, duration=FPS_DELAY * 10, optimize=True, disposal=2)
    return out.getvalue()


# ══════════════════════════════════════════════
#  COG
# ══════════════════════════════════════════════
class VerifyGreeting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # ✅ CHANNEL VERIF
        self.VERIF_CHANNEL_ID = 1486913580161962054

        # ✅ ROLE MEMBER
        self.MEMBER_ROLE_ID = 1453095603008442510

        # ✅ ROLE STAFF
        self.MOD_DC_ROLE_ID = 1453103644244316343
        self.MOD_YT_ROLE_ID = 1408509547601203252
        self.PEMBINA_OSIS_ROLE_ID = 1467360501745844446
        self.OSIS_ROLE_ID = 1427276194876751902

        self.already_greeted = set()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.channel.id != self.VERIF_CHANNEL_ID:
            return

        member = message.author

        if any(role.id == self.MEMBER_ROLE_ID for role in member.roles):
            return
        if member.id in self.already_greeted:
            return
        self.already_greeted.add(member.id)

        content = (
            f"Welcome {member.mention} to the server!\n"
            f"<@&{self.MOD_DC_ROLE_ID}> "
            f"<@&{self.PEMBINA_OSIS_ROLE_ID}> "
            f"<@&{self.OSIS_ROLE_ID}>"
        )

        try:
            avatar_bytes = await member.display_avatar.replace(size=256, format="png").read()
            loop = asyncio.get_running_loop()
            gif_bytes = await loop.run_in_executor(
                None, generate_verify_gif, avatar_bytes, member.display_name
            )
        except Exception as e:
            print(f"[VerifyGreeting] gagal bikin GIF: {e}")
            self.already_greeted.discard(member.id)
            return

        await asyncio.sleep(2)
        await message.channel.send(
            content=content,
            file=discord.File(io.BytesIO(gif_bytes), filename="verify_welcome.gif"),
            allowed_mentions=discord.AllowedMentions(users=True, roles=True),
        )


async def setup(bot):
    await bot.add_cog(VerifyGreeting(bot))