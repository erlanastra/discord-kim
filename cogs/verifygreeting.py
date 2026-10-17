"""nanZ welcome GIF + entry buttons for the verification flow.

This cog is intentionally limited to the welcome message and its buttons.
Application state, reminders, staff decisions, and voice-arrival notifications
remain owned by cogs.verifysystem.
"""

from __future__ import annotations

import asyncio
import io
import math
import random
from typing import Optional

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFilter, ImageFont


# ============================================================
# CONFIG
# ============================================================

VERIF_CHANNEL_ID = 1486913580161962054
MEMBER_ROLE_ID = 1453095603008442510
MOD_DC_ROLE_ID = 1555556260269527151
PEMBINA_OSIS_ROLE_ID = 1467360501745844446
OSIS_ROLE_ID = 1427276194876751902

VOICE_VERIF_CHANNEL_IDS = [
    1518251174149750906,
    1523340570607616010,
    1486913650374738030,
]

# Persistent custom IDs: do not change them if existing welcome messages
# should continue responding after a deployment.
WELCOME_DATA_CUSTOM_ID = "nanz_welcome_data_verif"
WELCOME_VOICE_CUSTOM_ID = "nanz_welcome_join_voice_verif"
JOIN_VOICE_CUSTOM_ID = "nanz_join_voice_verif_after_data"

FONT_BOLD = "fonts/LEMONMILK-Bold.otf"
FONT_MEDIUM = "fonts/LEMONMILK-Medium.otf"
FONT_REGULAR = "fonts/LEMONMILK-Regular.otf"
FONT_LIGHT = "fonts/LEMONMILK-Light.otf"
FONT_FALLBACKS = (
    "DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "arial.ttf",
)

W, H = 800, 340
FRAME_COUNT = 30
FRAME_DURATION_MS = 80
BG_TOP = (18, 10, 45)
BG_BOTTOM = (40, 20, 80)
PURPLE = (130, 80, 255)
BLUE = (80, 180, 255)
SOFT_PURPLE = (160, 120, 255)
SOFT_BLUE = (150, 210, 255)
CARD_BG = (30, 15, 65)
CARD = (20, 20, 780, 320)
AVATAR_SIZE = 140
AVATAR_CENTER = (150, 146)
TEXT_LEFT, TEXT_RIGHT = 296, 754


# ============================================================
# GIF HELPERS
# ============================================================

def _font(path: str, size: int) -> ImageFont.ImageFont:
    for candidate in (path, *FONT_FALLBACKS):
        try:
            return ImageFont.truetype(candidate, size)
        except (OSError, ValueError):
            continue
    return ImageFont.load_default()


def _lerp(c1, c2, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _clamp(value: float, low: int = 0, high: int = 255) -> int:
    return max(low, min(high, int(value)))


def _ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font_path: str,
              start_size: int, max_width: int, min_size: int = 22):
    size = start_size
    while size >= min_size:
        font = _font(font_path, size)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font, text
        size -= 2
    font = _font(font_path, min_size)
    shortened = text
    while shortened and draw.textbbox((0, 0), shortened + "…", font=font)[2] > max_width:
        shortened = shortened[:-1]
    return font, (shortened + "…") if shortened != text else text


def _prepare_avatar(avatar_bytes: bytes) -> Image.Image:
    with Image.open(io.BytesIO(avatar_bytes)) as source:
        avatar = source.convert("RGBA").resize(
            (AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS
        )
    mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
    ImageDraw.Draw(mask).ellipse((1, 1, AVATAR_SIZE - 2, AVATAR_SIZE - 2), fill=255)
    avatar.putalpha(mask)
    return avatar


def _make_particles(seed: int = 42):
    rng = random.Random(seed)
    stars = [
        (rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1, 2.5),
         rng.uniform(3, 12), rng.uniform(0, math.tau), rng.randint(90, 200))
        for _ in range(65)
    ]
    bubbles = [
        (rng.uniform(0, W), rng.uniform(0, H), rng.uniform(3, 7),
         rng.choice((1, 1, 2)), rng.uniform(4, 14), rng.uniform(0, math.tau))
        for _ in range(16)
    ]
    sparkles = [
        (rng.uniform(15, W - 15), rng.uniform(12, H - 12),
         rng.uniform(5, 10), rng.uniform(0, math.tau))
        for _ in range(12)
    ]
    return stars, bubbles, sparkles


def _render_frame(index: int, avatar: Image.Image, name: str, particles) -> Image.Image:
    phase = math.tau * index / FRAME_COUNT
    progress = index / max(1, FRAME_COUNT - 1)
    pulse = (1 + math.sin(phase)) / 2

    # Vertical midnight-blue/purple gradient.
    background = Image.new("RGB", (W, H))
    draw_bg = ImageDraw.Draw(background)
    for y in range(H):
        draw_bg.line((0, y, W, y), fill=_lerp(BG_TOP, BG_BOTTOM, y / H))
    base = background.convert("RGBA")

    # Soft glowing orbs.
    orbs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(orbs)
    for i, (cx, cy, radius, color) in enumerate((
        (W * .10, H * .20, 140, PURPLE),
        (W * .90, H * .70, 140, BLUE),
        (W * .65, H * .02, 90, PURPLE),
    )):
        factor = .88 + .22 * ((math.sin(phase + i * math.tau / 3) + 1) / 2)
        r = int(radius * factor)
        for step in range(r, 0, -7):
            alpha = _clamp(58 * (step / r) ** 2.7)
            od.ellipse((cx-step, cy-step, cx+step, cy+step), fill=(*color, alpha))
    base = Image.alpha_composite(base, orbs.filter(ImageFilter.GaussianBlur(2)))

    # Floating stars, sparkles, and bubbles.
    stars, bubbles, sparkles = particles
    fx = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fx)
    for x0, y0, radius, sway, offset, alpha in stars:
        y = (y0 - progress * H * .45) % H
        x = x0 + sway * math.sin(phase + offset)
        twinkle = (math.sin(phase * 2 + offset) + 1) / 2
        fd.ellipse((x-radius, y-radius, x+radius, y+radius),
                   fill=(*_lerp(PURPLE, BLUE, twinkle), _clamp(alpha * (.45 + .55 * twinkle))))
    for x0, y0, size, offset in sparkles:
        twinkle = (math.sin(phase * 2 + offset) + 1) / 2
        s = size * (.35 + .65 * twinkle)
        q = s * .25
        fd.polygon(((x0, y0-s), (x0+q, y0-q), (x0+s, y0), (x0+q, y0+q),
                    (x0, y0+s), (x0-q, y0+q), (x0-s, y0), (x0-q, y0-q)),
                   fill=(*_lerp(SOFT_BLUE, SOFT_PURPLE, twinkle), _clamp(70 + 185 * twinkle)))
    for x0, y0, radius, speed, sway, offset in bubbles:
        y = (y0 - progress * H * speed) % H
        x = x0 + sway * math.sin(phase * speed + offset)
        alpha = _clamp(65 + 90 * ((math.sin(phase * 2 + offset) + 1) / 2))
        fd.ellipse((x-radius, y-radius, x+radius, y+radius), outline=(255, 255, 255, alpha), width=1)
    base = Image.alpha_composite(base, fx)

    # Main card and left avatar panel.
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rounded_rectangle(CARD, radius=30, fill=(*CARD_BG, _clamp(185 + 20 * pulse)),
                         outline=(*PURPLE, 110), width=2)
    zone = (38, 38, 262, 302)
    pd.rounded_rectangle(zone, radius=22, fill=(*PURPLE, 38), outline=(*SOFT_PURPLE, 80), width=1)
    for y in range(38, 302):
        color = _lerp(BLUE, PURPLE, (y - 38) / 264)
        pd.line((276, y, 277, y), fill=(*color, 210), width=1)
    base = Image.alpha_composite(base, panel)

    # Avatar glow and rotating rings.
    cx, cy = AVATAR_CENTER
    ring = AVATAR_SIZE // 2 + 12
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((cx-ring-8, cy-ring-8, cx+ring+8, cy+ring+8),
                                 fill=(*_lerp(BLUE, PURPLE, pulse), _clamp(60 + 50 * pulse)))
    base = Image.alpha_composite(base, glow.filter(ImageFilter.GaussianBlur(14)))
    orbit = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(orbit)
    ring_box = (cx-ring, cy-ring, cx+ring, cy+ring)
    od.ellipse(ring_box, outline=(255, 255, 255, 65), width=2)
    angle = math.degrees(phase)
    od.arc(ring_box, angle, angle + 110, fill=(*SOFT_BLUE, 255), width=5)
    od.arc(ring_box, angle + 180, angle + 290, fill=(*SOFT_PURPLE, 255), width=5)
    for i in range(6):
        a = -phase + i * math.tau / 6
        px, py = cx + (ring + 14) * math.cos(a), cy + (ring + 14) * math.sin(a)
        r = 3 + 2 * ((math.sin(phase * 2 + i) + 1) / 2)
        col = SOFT_BLUE if i % 2 == 0 else SOFT_PURPLE
        od.ellipse((px-r, py-r, px+r, py+r), fill=(*col, 230))
    base = Image.alpha_composite(base, orbit)
    base.alpha_composite(avatar, (cx - AVATAR_SIZE // 2, cy - AVATAR_SIZE // 2))

    # Typography and progress indicator.
    text_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(text_layer)
    def alpha(delay: float) -> int:
        local = max(0.0, (progress - delay) / (1 - delay + .001))
        return _clamp(255 * _ease_out(min(local * 2.5, 1)))
    def slide(delay: float, amount: int = 16) -> int:
        local = max(0.0, (progress - delay) / (1 - delay + .001))
        return int(amount * (1 - _ease_out(min(local * 2.5, 1))))

    label_font = _font(FONT_LIGHT, 13)
    label = "MURID BARU"
    label_width = int(td.textlength(label, font=label_font)) + 30
    td.rounded_rectangle((cx-label_width//2, 262, cx+label_width//2, 286), radius=12,
                         fill=(*PURPLE, _clamp(alpha(.05) * .35)),
                         outline=(*SOFT_PURPLE, _clamp(alpha(.05) * .8)), width=1)
    td.text((cx, 274), label, font=label_font, fill=(255, 255, 255, alpha(.05)), anchor="mm")

    a, dy = alpha(0), slide(0)
    pill_font = _font(FONT_MEDIUM, 14)
    pill = "SELAMAT DATANG"
    pill_width = int(td.textlength(pill, font=pill_font)) + 36
    td.rounded_rectangle((TEXT_LEFT, 52+dy, TEXT_LEFT+pill_width, 80+dy), radius=14,
                         fill=(*PURPLE, _clamp(a * .85)))
    td.text((TEXT_LEFT+pill_width/2, 66+dy), pill, font=pill_font,
            fill=(255, 255, 255, a), anchor="mm")
    td.text((TEXT_RIGHT, 66+dy), "nanZ Server", font=_font(FONT_LIGHT, 13),
            fill=(*SOFT_PURPLE, _clamp(a * .9)), anchor="rm")

    name_font, fitted_name = _fit_text(td, name, FONT_BOLD, 46, TEXT_RIGHT-TEXT_LEFT, 22)
    td.text((TEXT_LEFT, 122+slide(.1)), fitted_name, font=name_font,
            fill=(255, 255, 255, alpha(.1)), anchor="lm")
    td.text((TEXT_LEFT, 166+slide(.18)), "Verifikasi kamu sudah masuk.",
            font=_font(FONT_MEDIUM, 18), fill=(*SOFT_BLUE, alpha(.18)), anchor="lm")

    divider_progress = _ease_out(min(max(0, (progress - .2) * 3), 1))
    for x in range(int((TEXT_RIGHT-TEXT_LEFT) * divider_progress)):
        td.line((TEXT_LEFT+x, 194, TEXT_LEFT+x, 195),
                fill=(*_lerp(PURPLE, BLUE, x/(TEXT_RIGHT-TEXT_LEFT)), 170))

    # Animated three-step line.
    step_y = 232
    n1, n2, n3 = TEXT_LEFT + 24, (TEXT_LEFT + TEXT_RIGHT)//2, TEXT_RIGHT - 24
    td.line((n1, step_y, n3, step_y), fill=(255, 255, 255, _clamp(alpha(.28)*.16)), width=4)
    for x in range(n1, n2):
        td.line((x, step_y, x, step_y), fill=(*_lerp(BLUE, PURPLE, (x-n1)/(n3-n1)), alpha(.28)), width=4)
    seg = 64
    pos = n2 - seg + progress * (n3 - n2 + seg)
    for x in range(int(max(n2, pos)), int(min(n3, pos+seg))):
        edge = min(x-pos, pos+seg-x) / (seg/2)
        td.line((x, step_y, x, step_y), fill=(*_lerp(PURPLE, SOFT_PURPLE, edge),
                _clamp(alpha(.28)*min(1, edge*1.4))), width=4)
    td.ellipse((n1-11, step_y-11, n1+11, step_y+11), fill=(*BLUE, alpha(.28)))
    td.line((n1-5, step_y, n1-1, step_y+4, n1+6, step_y-4), fill=(255,255,255,alpha(.28)), width=3)
    hr = 13 + 6*pulse
    td.ellipse((n2-hr, step_y-hr, n2+hr, step_y+hr),
               outline=(*SOFT_PURPLE, _clamp(alpha(.28)*(.9-.6*pulse))), width=2)
    td.ellipse((n2-11, step_y-11, n2+11, step_y+11), fill=(*PURPLE, alpha(.28)))
    td.ellipse((n2-4, step_y-4, n2+4, step_y+4), fill=(255,255,255,alpha(.28)))
    td.ellipse((n3-11, step_y-11, n3+11, step_y+11), outline=(255,255,255,_clamp(alpha(.28)*.4)), width=3)
    step_font = _font(FONT_MEDIUM, 13)
    td.text((n1, step_y+26), "Terkirim", font=step_font, fill=(*SOFT_BLUE, alpha(.33)), anchor="mm")
    td.text((n2, step_y+26), "Diproses", font=step_font, fill=(255,255,255,alpha(.33)), anchor="mm")
    td.text((n3, step_y+26), "Selesai", font=step_font, fill=(255,255,255,_clamp(alpha(.33)*.45)), anchor="mm")
    td.text((TEXT_LEFT, 286+slide(.42, 12)), "Mohon tunggu staff memproses ya.",
            font=_font(FONT_REGULAR, 16), fill=(215,215,240,alpha(.42)), anchor="lm")

    # Subtle shimmer clipped to the card.
    shimmer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shimmer)
    sp = int(progress * (W + 300)) - 150
    for k in range(-24, 25):
        sd.line((sp+k+60, 0, sp+k-60, H),
                fill=(255,255,255,_clamp(24*(1-abs(k)/24)),), width=2)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle(CARD, radius=30, fill=255)
    shimmer.putalpha(Image.composite(shimmer.getchannel("A"), Image.new("L", (W,H),0), mask))
    base = Image.alpha_composite(base, shimmer)
    base = Image.alpha_composite(base, text_layer)
    return base.convert("RGB")


def generate_verify_gif(avatar_bytes: bytes, name: str) -> bytes:
    """Render a short looping welcome GIF; call this in an executor thread."""
    avatar = _prepare_avatar(avatar_bytes)
    particles = _make_particles()
    frames = [_render_frame(i, avatar, name, particles) for i in range(FRAME_COUNT)]
    output = io.BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=FRAME_DURATION_MS,
        optimize=True,
        disposal=2,
    )
    return output.getvalue()


# ============================================================
# VOICE HELPERS
# ============================================================

def _channel_url(guild_id: int, channel_id: int) -> str:
    return f"https://discord.com/channels/{guild_id}/{channel_id}"


async def _select_verif_voice(guild: discord.Guild, member: discord.Member):
    channels = []
    for channel_id in VOICE_VERIF_CHANNEL_IDS:
        channel = guild.get_channel(channel_id)
        if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            channels.append(channel)
    if not channels:
        return None
    for channel in channels:
        if not any(m.id != member.id for m in channel.members):
            return channel
    return channels[0]


async def handle_voice_verif_interaction(interaction: discord.Interaction):
    guild = interaction.guild
    member = interaction.user
    if guild is None or not isinstance(member, discord.Member):
        return await interaction.response.send_message(
            "Verifikasi voice hanya bisa digunakan di dalam server.", ephemeral=True
        )

    # Acknowledge first so the interaction does not expire while checking/moving.
    await interaction.response.defer(ephemeral=True, thinking=True)
    target = await _select_verif_voice(guild, member)
    if target is None:
        return await interaction.followup.send(
            "Voice verifikasi sedang tidak tersedia. Silakan hubungi staff.", ephemeral=True
        )

    if member.voice and member.voice.channel:
        if member.voice.channel.id == target.id:
            return await interaction.followup.send(
                f"Kamu sudah berada di **{target.name}**. Tunggu staff melakukan konfirmasi.",
                ephemeral=True,
            )
        try:
            await member.move_to(target, reason="nanZ Verification Voice")
        except discord.Forbidden:
            return await interaction.followup.send(
                "Bot tidak memiliki izin untuk memindahkan member ke voice verifikasi.",
                ephemeral=True,
            )
        except discord.HTTPException as exc:
            print(f"[VerifyGreeting][user={member.id}] move voice gagal: {exc}")
            return await interaction.followup.send(
                "Gagal memindahkan kamu ke voice verifikasi. Coba lagi.", ephemeral=True
            )
        # The VerifySystem cog's on_voice_state_update listener is the only
        # source of staff arrival notifications, preventing duplicate notices.
        return await interaction.followup.send(
            f"Kamu diarahkan ke **{target.name}**. Tunggu staff melakukan konfirmasi.",
            ephemeral=True,
        )

    link_view = discord.ui.View(timeout=60)
    link_view.add_item(discord.ui.Button(
        label=f"Join {target.name}", style=discord.ButtonStyle.link,
        url=_channel_url(guild.id, target.id),
    ))
    return await interaction.followup.send(
        "Kamu belum berada di voice. Klik tombol di bawah untuk masuk. "
        "Setelah masuk, sistem akan memberi tahu staff secara otomatis.",
        view=link_view,
        ephemeral=True,
    )


# ============================================================
# PERSISTENT VIEWS
# ============================================================

class JoinVoiceVerifView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Join Voice Verif", style=discord.ButtonStyle.primary,
        custom_id=JOIN_VOICE_CUSTOM_ID,
    )
    async def join_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_voice_verif_interaction(interaction)


class WelcomeActionView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Data Verif", style=discord.ButtonStyle.primary,
        custom_id=WELCOME_DATA_CUSTOM_ID,
    )
    async def data_verif(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = self.bot.get_cog("VerifySystem")
        if cog is None:
            return await interaction.response.send_message(
                "Panel verifikasi sedang tidak tersedia. Coba beberapa saat lagi atau hubungi staff.",
                ephemeral=True,
            )
        try:
            await cog.show_verification_panel(interaction)
        except Exception as exc:
            print(f"[VerifyGreeting][user={interaction.user.id}] panel verifikasi gagal: {exc}")
            if interaction.response.is_done():
                await interaction.followup.send(
                    "Panel verifikasi gagal dibuka. Silakan coba lagi.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Panel verifikasi gagal dibuka. Silakan coba lagi.", ephemeral=True
                )

    @discord.ui.button(
        label="Join Voice Verif", style=discord.ButtonStyle.secondary,
        custom_id=WELCOME_VOICE_CUSTOM_ID,
    )
    async def voice_verif(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_voice_verif_interaction(interaction)


# ============================================================
# WELCOME COG
# ============================================================

class VerifyGreeting(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._greeted_this_session: set[tuple[int, int]] = set()
        self._greeting_locks: dict[tuple[int, int], asyncio.Lock] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        if message.channel.id != VERIF_CHANNEL_ID:
            return
        if not isinstance(message.author, discord.Member):
            return

        member = message.author
        if any(role.id == MEMBER_ROLE_ID for role in member.roles):
            return

        key = (message.guild.id, member.id)
        lock = self._greeting_locks.setdefault(key, asyncio.Lock())
        async with lock:
            if key in self._greeted_this_session:
                return
            self._greeted_this_session.add(key)

            try:
                avatar_bytes = await member.display_avatar.replace(size=256, format="png").read()
                loop = asyncio.get_running_loop()
                gif_bytes = await loop.run_in_executor(
                    None, generate_verify_gif, avatar_bytes, member.display_name
                )
            except Exception as exc:
                print(f"[VerifyGreeting][user={member.id}] gagal membuat GIF: {exc}")
                self._greeted_this_session.discard(key)
                return

            # Keep the small delay from the original welcome behavior.
            await asyncio.sleep(2)
            content = (
                "<a:welcome:1553703629880299610> **Selamat datang di nanZ Server!**\n"
                f"Hai {member.mention}, sebelum mulai beraktivitas, kamu wajib menyelesaikan verifikasi "
                "agar bisa menjadi member nanZ. Tenang, kamu akan dipandu langkah demi langkah.\n\n"
                "> **Alur verifikasi:**\n"
                "> 1. Tekan **Data Verif** di bawah pesan ini.\n"
                "> 2. Pilih platform medsos, rentang umur, dan gender.\n"
                "> 3. Tekan **Lanjut Isi Data**, lalu isi nama, asal, dan username medsos. "
                "> Username boleh ditulis dengan atau tanpa `@`.\n"
                "> 4. Setelah menekan submit, tekan **Join Voice Verif** dan tunggu staff mengonfirmasi data kamu.\n"
                "> 5. Setelah staff menyetujui, verifikasi selesai dan kamu bisa mulai beraktivitas di nanZ!\n\n"
                "```Jangan khawatir kalau staff belum langsung datang. Bot akan mengirim pengingat lewat DM selama pengajuanmu masih menunggu. Pastikan DM dari server tidak ditutup.```\n"
                f"|| <@&{MOD_DC_ROLE_ID}> <@&{PEMBINA_OSIS_ROLE_ID}> <@&{OSIS_ROLE_ID}> ||"
            )
            try:
                await message.channel.send(
                    content=content,
                    file=discord.File(io.BytesIO(gif_bytes), filename="verify_welcome.gif"),
                    view=WelcomeActionView(self.bot),
                    allowed_mentions=discord.AllowedMentions(users=True, roles=True),
                )
            except discord.HTTPException as exc:
                print(f"[VerifyGreeting][user={member.id}] gagal mengirim welcome: {exc}")
                self._greeted_this_session.discard(key)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Sambut member segera setelah join, tanpa menunggu mereka mengirim pesan."""
        if member.bot:
            return

        channel = member.guild.get_channel(VERIF_CHANNEL_ID)
        if channel is None or not isinstance(channel, discord.TextChannel):
            print(
                f"[VerifyGreeting][user={member.id}] channel verifikasi "
                f"{VERIF_CHANNEL_ID} tidak ditemukan saat member join."
            )
            return

        key = (member.guild.id, member.id)
        lock = self._greeting_locks.setdefault(key, asyncio.Lock())
        async with lock:
            if key in self._greeted_this_session:
                return

            try:
                avatar_bytes = await member.display_avatar.replace(size=256, format="png").read()
                loop = asyncio.get_running_loop()
                gif_bytes = await loop.run_in_executor(
                    None, generate_verify_gif, avatar_bytes, member.display_name
                )
            except Exception as exc:
                print(f"[VerifyGreeting][user={member.id}] gagal membuat GIF saat join: {exc}")
                gif_bytes = None

            content = (
                "<a:welcome:1553703629880299610> **Selamat datang di nanZ Server!**\\n"
                f"Hai {member.mention}, sebelum mulai beraktivitas, kamu **wajib menyelesaikan verifikasi**.\\n\\n"
                "**IKUTI LANGKAH INI:**\\n"
                "1. Tekan **Data Verif** di bawah pesan ini.\\n"
                "2. Pilih platform medsos, rentang umur, dan gender.\\n"
                "3. Tekan **Lanjut Isi Data**, lalu isi nama, asal, dan username medsos. "
                "Username boleh dengan atau tanpa `@`. Setelah itu tekan submit.\\n"
                "4. Tekan **Join Voice Verif**, lalu tunggu staff mengonfirmasi data kamu di voice.\\n"
                "5. Setelah disetujui staff, verifikasi selesai dan kamu bisa mulai beraktivitas di nanZ.\\n\\n"
                "Kalau staff belum langsung datang, tetap tenang dan tunggu. Bot akan mengirim pengingat melalui DM "
                "selama pengajuanmu masih menunggu. Pastikan DM dari server terbuka."
            )

            try:
                kwargs = {
                    "content": content,
                    "view": WelcomeActionView(self.bot),
                    "allowed_mentions": discord.AllowedMentions(users=True, roles=False),
                }
                if gif_bytes:
                    kwargs["file"] = discord.File(
                        io.BytesIO(gif_bytes), filename="verify_welcome.gif"
                    )
                await channel.send(**kwargs)
                self._greeted_this_session.add(key)
            except discord.HTTPException as exc:
                print(f"[VerifyGreeting][user={member.id}] gagal mengirim welcome saat join: {exc}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Izinkan member mendapat greeting lagi jika keluar lalu join kembali."""
        key = (member.guild.id, member.id)
        self._greeted_this_session.discard(key)

        # Hapus lock yang tidak sedang dipakai agar tidak menumpuk.
        lock = self._greeting_locks.get(key)
        if lock is not None and not lock.locked():
            self._greeting_locks.pop(key, None)

        print(
            f"[VerifyGreeting][user={member.id}] status greeting direset "
            "karena member keluar dari server."
        )

    def cog_unload(self):
        self._greeted_this_session.clear()
        self._greeting_locks.clear()


async def setup(bot: commands.Bot):
    await bot.add_cog(VerifyGreeting(bot))
    # Register only this cog's own persistent views. Do not register these
    # again in bot.py; that avoids duplicate dispatch registration.
    bot.add_view(WelcomeActionView(bot))
    bot.add_view(JoinVoiceVerifView(bot))
    print("[VerifyGreeting] Persistent welcome views registered.")
