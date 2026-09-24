import asyncio
import io
import json
import math
import random
import time

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


def _fit_size(draw, lines, path, start, max_w, min_size=10):
    size = start
    while size > min_size:
        f = _font(path, size)
        if max(draw.textlength(l, font=f) for l in lines) <= max_w:
            return f
        size -= 1
    return _font(path, min_size)


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

    # badge centang (verifikasi berhasil)
    bx, by = AV_CX + 52, AV_CY + 52
    br = 16 + 2 * pulse
    bdraw = ImageDraw.Draw(base)
    bdraw.ellipse([bx - br - 4, by - br - 4, bx + br + 4, by + br + 4], fill=(*CARD_BG, 255))
    bdraw.ellipse([bx - br, by - br, bx + br, by + br], fill=(*BLUE, 255))
    bdraw.line([(bx - 7, by + 1), (bx - 2, by + 6), (bx + 8, by - 6)], fill=(255, 255, 255, 255), width=4)

    # ── Teks & UI ──
    tl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(tl)
    f_pill = _font(FONT_MEDIUM, 14)
    f_tiny = _font(FONT_LIGHT, 13)
    f_med = _font(FONT_MEDIUM, 18)
    f_small = _font(FONT_REGULAR, 16)

    def t_alpha(d):
        lt = max(0, (t - d) / (1.0 - d + 0.001))
        return _clamp(255 * _ease_out(min(lt * 2.5, 1.0)))

    def slide(d, mx=16):
        lt = max(0, (t - d) / (1.0 - d + 0.001))
        return int(mx * (1 - _ease_out(min(lt * 2.5, 1.0))))

    # label di bawah avatar
    la = t_alpha(0.05)
    lw = int(td.textlength("MURID RESMI", font=f_tiny)) + 30
    td.rounded_rectangle([AV_CX - lw // 2, 262, AV_CX + lw // 2, 286], radius=12,
                         fill=(*PURPLE, _clamp(la * 0.35)), outline=(*SOFT_PURPLE, _clamp(la * 0.8)), width=1)
    td.text((AV_CX, 274), "MURID RESMI", font=f_tiny, fill=(255, 255, 255, la), anchor="mm")

    # baris atas: label sapaan (kiri) + pill status (kanan)
    a, dy = t_alpha(0.0), slide(0.0)
    lab, pil = "SELAMAT DATANG,", "VERIFIKASI BERHASIL"
    for sz in range(16, 9, -1):
        f_lab = _font(FONT_MEDIUM, sz)
        f_pil = _font(FONT_MEDIUM, max(sz - 2, 9))
        pw = int(td.textlength(pil, font=f_pil)) + 30
        if td.textlength(lab, font=f_lab) + pw + 16 <= RX1 - RX0:
            break
    td.text((RX0, 66 + dy), lab, font=f_lab, fill=(*SOFT_BLUE, a), anchor="lm")
    td.rounded_rectangle([RX1 - pw, 52 + dy, RX1, 80 + dy], radius=14, fill=(*PURPLE, _clamp(a * 0.85)))
    td.text((RX1 - pw / 2, 66 + dy), pil, font=f_pil, fill=(255, 255, 255, a), anchor="mm")

    # nama member
    f_name, name_fit = _fit_font(td, name, FONT_BOLD, 46, RX1 - RX0)
    td.text((RX0, 118 + slide(0.1)), name_fit, font=f_name, fill=(255, 255, 255, t_alpha(0.1)), anchor="lm")

    # kotak pesan dengan aksen gradasi di kiri
    ma = t_alpha(0.25)
    mdy = slide(0.25, 12)
    top, bot = 154 + mdy, 234 + mdy
    td.rounded_rectangle([RX0, top, RX1, bot], radius=16, fill=(*PURPLE, _clamp(ma * 0.15)),
                         outline=(*SOFT_PURPLE, _clamp(ma * 0.3)), width=1)
    for i in range(top + 10, bot - 9):
        c = _lerp_color(BLUE, PURPLE, (i - top) / (bot - top))
        td.line([(RX0 + 10, i), (RX0 + 13, i)], fill=(*c, ma))
    lines = ["Di sini semua member dianggap keluarga,",
             "jadi ngobrol, bertanya, atau ikut event bareng!"]
    f_body = _fit_size(td, lines, FONT_REGULAR, 16, RX1 - RX0 - 46)
    td.text((RX0 + 26, top + 24), lines[0], font=f_body, fill=(225, 225, 245, ma), anchor="lm")
    td.text((RX0 + 26, top + 56), lines[1], font=f_body, fill=(225, 225, 245, t_alpha(0.3)), anchor="lm")

    # dua chip status di bawah
    c1, c2 = "Terverifikasi", "Akses semua channel"
    f_chip = _fit_size(td, [c1, c2], FONT_MEDIUM, 13, (RX1 - RX0 - 12 - 104) // 2)

    def chip(x, txt, col, icon, d):
        ca = t_alpha(d)
        cy = 272 + slide(d, 10)
        w = int(td.textlength(txt, font=f_chip)) + 52
        td.rounded_rectangle([x, cy - 15, x + w, cy + 15], radius=15, fill=(*col, _clamp(ca * 0.22)),
                             outline=(*col, _clamp(ca * 0.85)), width=1)
        ix = x + 19
        td.ellipse([ix - 10, cy - 10, ix + 10, cy + 10], fill=(*col, ca))
        if icon == "check":
            td.line([(ix - 5, cy), (ix - 1, cy + 4), (ix + 6, cy - 4)], fill=(255, 255, 255, ca), width=3)
        else:
            q = 2
            td.polygon([(ix, cy - 6), (ix + q, cy - q), (ix + 6, cy), (ix + q, cy + q),
                        (ix, cy + 6), (ix - q, cy + q), (ix - 6, cy), (ix - q, cy - q)],
                       fill=(255, 255, 255, ca))
        td.text((x + 36, cy), txt, font=f_chip, fill=(255, 255, 255, ca), anchor="lm")
        return x + w

    nx = chip(RX0, c1, BLUE, "check", 0.42)
    chip(nx + 12, c2, PURPLE, "star", 0.5)

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


def generate_welcome_gif(avatar_bytes: bytes, name: str) -> bytes:
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

    @discord.ui.button(label="Sapa murid baru!", emoji="👋", style=discord.ButtonStyle.secondary)
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

        # ── Sapaan + arahan + GIF (satu pesan, tanpa panel) ──
        gif_file = None
        try:
            avatar_bytes = await member.display_avatar.replace(size=256, format="png").read()
            loop = asyncio.get_running_loop()
            gif_bytes = await loop.run_in_executor(None, generate_welcome_gif, avatar_bytes, member.display_name)
            gif_file = discord.File(io.BytesIO(gif_bytes), filename="welcome.gif")
        except Exception as e:
            print(f"[Welcome] gagal bikin GIF: {e}")

        content = (
            "<a:done:1512648033190543421> **Verifikasi berhasil!**\n"
            f"Selamat datang di **nanZ Server**, {member.mention}!\n\n"
            f"> Pahami aturan server di <#{self.RULES_CHANNEL_ID}>\n"
            f"> Pilih role kamu di <#{self.ROLES_CHANNEL_ID}>"
        )

        kwargs = {"file": gif_file} if gif_file else {}
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