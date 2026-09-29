import asyncio
import io
import random

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ==========================================
# ID CHANNEL QUOTE
# ==========================================
QUOTE_CHANNEL_ID = 1474394873783128368

# ==========================================
# EMOJI LIKE (lovelike)
# ==========================================
LIKE_EMOJI = discord.PartialEmoji(name="lovelike", id=1493106010389483661)

# ==========================================
# KONFIGURASI PANEL PNG
# ==========================================
FONT_BOLD = "fonts/LEMONMILK-Bold.otf"
FONT_REGULAR = "fonts/LEMONMILK-Regular.otf"
FB = ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf")
BG_TOP, BG_BOT = (18, 10, 45), (40, 20, 80)
PURPLE, BLUE = (130, 80, 255), (80, 180, 255)
CARD_BG = (30, 15, 65)
SP, SB = (160, 120, 255), (150, 210, 255)
ORANGE, PINK, GREEN = (255, 170, 80), (255, 100, 140), (90, 220, 160)
WH = (255, 255, 255)
W, H, s = 900, 500, 2


# ==========================================
# HELPER GAMBAR
# ==========================================
def font(p, px):
    for q in (p, *FB):
        try: return ImageFont.truetype(q, int(px))
        except Exception: pass
    return ImageFont.load_default()
def lerp(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
def sc(v): return [int(x * s) for x in v]
def P(pts): return [(x * s, y * s) for x, y in pts]
def F(p, sz): return font(p, sz * s)
def wrap(d, text, f, mw):
    out, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}".strip()
        if d.textlength(t, font=f) <= mw: cur = t
        else:
            out.append(cur); cur = w
    if cur: out.append(cur)
    return out



# ==========================================
# PNG PANEL QUOTE
# ==========================================
def generate_quote_panel() -> bytes:
    base = Image.new("RGB", (W * s, H * s))
    d = ImageDraw.Draw(base)
    for y in range(H * s):
        d.line([(0, y), (W * s, y)], fill=lerp(BG_TOP, BG_BOT, y / (H * s)))
    base = base.convert("RGBA")

    def layer(fn, blur=0):
        nonlocal base
        lay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        fn(ImageDraw.Draw(lay))
        if blur: lay = lay.filter(ImageFilter.GaussianBlur(blur * s))
        base = Image.alpha_composite(base, lay)

    def orbs(g):
        for ox, oy, r, c in [(80, 60, 170, PURPLE), (830, 470, 190, BLUE), (640, 10, 120, PURPLE), (60, 460, 120, BLUE)]:
            for st in range(r, 0, -5):
                g.ellipse(sc([ox - st, oy - st, ox + st, oy + st]), fill=(*c, int(55 * (st / r) ** 2.8)))
    layer(orbs)
    rng = random.Random(5)
    def stars(g):
        for _ in range(80):
            x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1, 2.4)
            g.ellipse(sc([x - r, y - r, x + r, y + r]), fill=(*lerp(PURPLE, BLUE, rng.random()), rng.randint(80, 190)))
    layer(stars)
    def panel(g):
        g.rounded_rectangle(sc([20, 20, 880, 480]), radius=30 * s, fill=(*CARD_BG, 200))
        g.rounded_rectangle(sc([20, 20, 880, 480]), radius=30 * s, outline=(*PURPLE, 100), width=2 * s)
    layer(panel)

    def grad_text(text, path, size, x, y, c1, c2):
        nonlocal base
        f = F(path, size)
        dd = ImageDraw.Draw(base)
        bb = dd.textbbox((x * s, y * s), text, font=f)
        mask = Image.new("L", base.size, 0)
        ImageDraw.Draw(mask).text((x * s, y * s), text, font=f, fill=255)
        g = Image.new("RGBA", base.size); gd = ImageDraw.Draw(g)
        span = max(1, bb[2] - bb[0])
        for xx in range(bb[0], bb[2] + 2):
            gd.line([(xx, 0), (xx, H * s)], fill=(*lerp(c1, c2, min(1, (xx - bb[0]) / span)), 255))
        g.putalpha(mask)
        base = Image.alpha_composite(base, g)

    def place(tile, cx, cy, ang):
        nonlocal base
        t = tile.rotate(ang, expand=True, resample=Image.BICUBIC)
        a = t.split()[3].filter(ImageFilter.GaussianBlur(9 * s)).point(lambda v: int(v * .55))
        sh = Image.new("RGBA", t.size, (0, 0, 0, 0)); sh.putalpha(a)
        x, y = int(cx * s - t.width / 2), int(cy * s - t.height / 2)
        base.alpha_composite(sh, (x, y + 8 * s))
        base.alpha_composite(t, (x, y))

    def vgrad(size, c1, c2, mask_fn):
        g = Image.new("RGBA", size); gd = ImageDraw.Draw(g)
        for y in range(size[1]): gd.line([(0, y), (size[0], y)], fill=(*lerp(c1, c2, y / size[1]), 255))
        m = Image.new("L", size, 0); mask_fn(ImageDraw.Draw(m))
        return g, m

    def heart(dr, x, y, r, col):
        dr.ellipse(sc([x - r, y - r * .9, x, y + r * .1]), fill=col)
        dr.ellipse(sc([x, y - r * .9, x + r, y + r * .1]), fill=col)
        dr.polygon(P([(x - r * .97, y - r * .15), (x + r * .97, y - r * .15), (x, y + r * 1.15)]), fill=col)

    def icon(dr, kind, cx, cy, col):
        if kind == "photo":
            dr.rounded_rectangle(sc([cx - 12, cy - 9, cx + 12, cy + 9]), radius=3 * s, fill=WH)
            dr.polygon(P([(cx - 9, cy + 6), (cx - 2, cy - 2), (cx + 2, cy + 3), (cx + 5, cy), (cx + 10, cy + 6)]), fill=col)
            dr.ellipse(sc([cx + 3, cy - 7, cx + 8, cy - 2]), fill=col)
        elif kind == "music":
            dr.ellipse(sc([cx - 9, cy + 3, cx - 2, cy + 10]), fill=WH)
            dr.ellipse(sc([cx + 3, cy + 1, cx + 10, cy + 8]), fill=WH)
            dr.rectangle(sc([cx - 4, cy - 10, cx - 2, cy + 6]), fill=WH)
            dr.rectangle(sc([cx + 8, cy - 12, cx + 10, cy + 4]), fill=WH)
            dr.polygon(P([(cx - 4, cy - 10), (cx + 10, cy - 12), (cx + 10, cy - 8), (cx - 4, cy - 6)]), fill=WH)
        else:
            dr.ellipse(sc([cx - 12, cy - 12, cx + 12, cy + 12]), fill=WH)
            dr.ellipse(sc([cx - 6, cy - 5, cx - 3, cy - 2]), fill=col)
            dr.ellipse(sc([cx + 3, cy - 5, cx + 6, cy - 2]), fill=col)
            dr.arc(sc([cx - 7, cy - 4, cx + 7, cy + 7]), 20, 160, fill=col, width=2 * s)

    # ================= KIRI =================
    d = ImageDraw.Draw(base)
    pill = "NANZ QUOTE"; fp = F(FONT_BOLD, 11)
    pw = d.textlength(pill, font=fp) / s + 34
    layer(lambda g: g.rounded_rectangle(sc([54, 52, 54 + pw, 76]), radius=12 * s, fill=(*PURPLE, 230)))
    d = ImageDraw.Draw(base)
    d.text(((54 + pw / 2) * s, 64 * s), pill, font=fp, fill=WH, anchor="mm")

    layer(lambda g: g.text((40 * s, 70 * s), "\u201c", font=F(FONT_BOLD, 230), fill=(*PURPLE, 55)))
    grad_text("TULIS", FONT_BOLD, 66, 54, 100, WH, SB)
    grad_text("QUOTE-MU", FONT_BOLD, 66, 54, 176, SB, SP)

    d = ImageDraw.Draw(base)
    d.text((56 * s, 292 * s), "Bagikan kata-kata dan perasaanmu.", font=F(FONT_REGULAR, 14), fill=(225, 225, 245), anchor="lm")
    d.text((56 * s, 315 * s), "Tambahkan foto, lagu, atau sticker.", font=F(FONT_REGULAR, 14), fill=(175, 170, 215), anchor="lm")

    # baris media
    for i, (lab, kind, col) in enumerate([("Foto", "photo", ORANGE), ("Lagu", "music", GREEN), ("Sticker", "sticker", SP)]):
        cx, cy = 76 + i * 118, 368
        layer(lambda g, cx=cx, cy=cy, col=col: (g.ellipse(sc([cx - 26, cy - 26, cx + 26, cy + 26]), fill=(*col, 45)),
                                                g.ellipse(sc([cx - 20, cy - 20, cx + 20, cy + 20]), fill=(*col, 255))))
        d = ImageDraw.Draw(base)
        icon(d, kind, cx, cy, col)
        d.text(((cx + 28) * s, cy * s), lab, font=F(FONT_BOLD, 12), fill=WH, anchor="lm")

    # CTA
    ct = "Klik tombol di bawah untuk mulai"
    fc = F(FONT_BOLD, 11)
    cw = d.textlength(ct, font=fc) / s + 60
    layer(lambda g: (g.rounded_rectangle(sc([54, 416, 54 + cw, 448]), radius=16 * s, fill=(*BLUE, 30)),
                     g.rounded_rectangle(sc([54, 416, 54 + cw, 448]), radius=16 * s, outline=(*BLUE, 200), width=s)))
    d = ImageDraw.Draw(base)
    d.text((74 * s, 432 * s), ct, font=fc, fill=SB, anchor="lm")
    ax = 54 + cw - 22
    d.polygon(P([(ax - 6, 428), (ax + 6, 428), (ax, 437)]), fill=SB)

    # ================= KANAN (kolase) =================
    # polaroid
    t = Image.new("RGBA", (190 * s, 220 * s), (0, 0, 0, 0)); td = ImageDraw.Draw(t)
    td.rounded_rectangle(sc([15, 12, 175, 205]), radius=6 * s, fill=(248, 246, 255))
    g, m = vgrad(t.size, (255, 190, 110), (110, 70, 200), lambda x: x.rectangle(sc([23, 20, 167, 155]), fill=255))
    t.paste(g, (0, 0), m); td = ImageDraw.Draw(t)
    td.ellipse(sc([78, 60, 112, 94]), fill=(255, 235, 160))
    td.polygon(P([(23, 155), (62, 105), (92, 138), (124, 92), (167, 155)]), fill=(70, 40, 130))
    td.polygon(P([(23, 155), (50, 128), (80, 155)]), fill=(45, 25, 95))
    td.rounded_rectangle(sc([34, 170, 120, 178]), radius=4 * s, fill=(190, 185, 225))
    td.rounded_rectangle(sc([34, 185, 90, 191]), radius=3 * s, fill=(215, 212, 238))
    heart(td, 152, 178, 8, PINK)
    place(t, 772, 138, 9)

    # kartu quote utama
    t = Image.new("RGBA", (380 * s, 250 * s), (0, 0, 0, 0))
    g, m = vgrad(t.size, (66, 38, 140), (34, 18, 84), lambda x: x.rounded_rectangle(sc([20, 20, 360, 230]), radius=26 * s, fill=255))
    t.paste(g, (0, 0), m); td = ImageDraw.Draw(t)
    td.rounded_rectangle(sc([20, 20, 360, 230]), radius=26 * s, outline=(*SP, 150), width=2 * s)
    td.text((46 * s, 72 * s), "\u201c", font=F(FONT_BOLD, 70), fill=SB, anchor="lm")
    fq = F(FONT_REGULAR, 15)
    for j, ln in enumerate(wrap(td, "Tidak apa-apa berjalan pelan, yang penting kamu tidak berhenti.", fq, 300 * s)):
        td.text((48 * s, (110 + j * 24) * s), ln, font=fq, fill=WH, anchor="lm")
    td.rounded_rectangle(sc([274, 40, 340, 60]), radius=10 * s, fill=(*PURPLE, 255))
    td.text((307 * s, 50 * s), "tenang", font=F(FONT_BOLD, 10), fill=WH, anchor="mm")
    td.line(sc([46, 180, 334, 180]), fill=(*SP, 90), width=s)
    td.ellipse(sc([46, 190, 74, 218]), fill=BLUE); td.ellipse(sc([54, 198, 66, 210]), fill=PURPLE)
    td.text((84 * s, 199 * s), "nanZ", font=F(FONT_BOLD, 12), fill=WH, anchor="lm")
    td.text((84 * s, 213 * s), "baru saja", font=F(FONT_REGULAR, 9), fill=SP, anchor="lm")
    heart(td, 300, 204, 9, PINK)
    td.text((316 * s, 205 * s), "24", font=F(FONT_BOLD, 12), fill=WH, anchor="lm")
    place(t, 655, 235, -5)

    # music pill
    t = Image.new("RGBA", (290 * s, 80 * s), (0, 0, 0, 0)); td = ImageDraw.Draw(t)
    td.rounded_rectangle(sc([10, 10, 280, 70]), radius=30 * s, fill=(20, 12, 52, 245), outline=(*BLUE, 230), width=2 * s)
    td.ellipse(sc([20, 20, 60, 60]), fill=BLUE)
    td.polygon(P([(35, 31), (35, 49), (50, 40)]), fill=WH)
    td.text((72 * s, 30 * s), "NOW PLAYING", font=F(FONT_BOLD, 9), fill=SB, anchor="lm")
    td.text((72 * s, 48 * s), "lofi_night.mp3", font=F(FONT_REGULAR, 11), fill=WH, anchor="lm")
    hs = [8, 16, 10, 22, 14, 26, 12, 20, 9, 16, 7]
    for i, h in enumerate(hs):
        x = 188 + i * 8
        td.rounded_rectangle(sc([x, 40 - h / 2, x + 4, 40 + h / 2]), radius=2 * s, fill=lerp(BLUE, SP, i / 10))
    place(t, 610, 372, -3)

    # sticker
    t = Image.new("RGBA", (110 * s, 110 * s), (0, 0, 0, 0)); td = ImageDraw.Draw(t)
    td.ellipse(sc([10, 10, 100, 100]), fill=(255, 214, 90), outline=WH, width=5 * s)
    td.ellipse(sc([36, 40, 46, 54]), fill=(60, 35, 100)); td.ellipse(sc([64, 40, 74, 54]), fill=(60, 35, 100))
    td.ellipse(sc([26, 58, 40, 68]), fill=(255, 150, 150)); td.ellipse(sc([70, 58, 84, 68]), fill=(255, 150, 150))
    td.arc(sc([34, 50, 76, 82]), 15, 165, fill=(60, 35, 100), width=4 * s)
    place(t, 838, 355, 12)

    # hati & sparkle
    def sparkle(x, y, sz, col):
        q = sz * .25
        return lambda g: g.polygon(P([(x, y - sz), (x + q, y - q), (x + sz, y), (x + q, y + q), (x, y + sz),
                                      (x - q, y + q), (x - sz, y), (x - q, y - q)]), fill=(*col, 230))
    for x, y, sz, c in [(470, 78, 9, SB), (560, 52, 6, SP), (872 - 10, 236, 7, SB), (455, 440, 7, SP), (760, 450, 6, SB)]:
        layer(sparkle(x, y, sz, c))
    layer(lambda g: (heart(g, 452, 150, 9, (*PINK, 210)), heart(g, 846, 268, 8, (*PINK, 210)), heart(g, 520, 448, 7, (*PINK, 190))))


    out = base.convert("RGB").resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ==========================================
# MODAL QUOTE
# ==========================================
class QuoteModal(discord.ui.Modal, title="Buat Quote"):

    quote = discord.ui.TextInput(
        label="Isi Quote",
        style=discord.TextStyle.paragraph,
        placeholder="Tulis quote kamu...",
        required=True,
        max_length=500
    )

    mood = discord.ui.TextInput(
        label="Mood / Emoji",
        placeholder="🌙✨💔",
        required=False,
        max_length=50
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):

        # simpan data sementara
        self.bot.quote_data[interaction.user.id] = {
            "quote": self.quote.value,
            "mood": self.mood.value
        }

        await interaction.response.send_message(
            (
                "**Quote berhasil dibuat.**\n\n"
                "Sekarang klik tombol dibawah "
                "untuk upload foto, lagu, atau sticker."
            ),
            view=UploadView(self.bot),
            ephemeral=True
        )


# ==========================================
# VIEW UPLOAD
# ==========================================
class UploadView(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot

    # ==========================================
    # FUNCTION KIRIM QUOTE
    # ==========================================
    async def send_quote(
        self,
        interaction: discord.Interaction,
        files=None,
        stickers=None
    ) -> bool:

        files = files or []
        stickers = stickers or []

        # ambil data quote
        data = self.bot.quote_data.get(
            interaction.user.id
        )

        if not data:
            return False

        quote_channel = self.bot.get_channel(
            QUOTE_CHANNEL_ID
        )

        if not quote_channel:
            return False

        # ==========================================
        # EMBED
        # ==========================================
        colors = [
            discord.Color.blurple(),
            discord.Color.purple(),
            discord.Color.magenta(),
            discord.Color.teal(),
            discord.Color.random()
        ]

        embed = discord.Embed(
            description=f"❝ *{data['quote']}* ❞",
            color=random.choice(colors)
        )

        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )

        # mood
        if data["mood"]:
            embed.add_field(
                name="Mood",
                value=data["mood"],
                inline=False
            )

        image_file = None
        music_files = []

        for file in files:

            filename = file.filename.lower()

            # FOTO
            if filename.endswith(
                ("png", "jpg", "jpeg", "webp", "gif")
            ):
                image_file = file

            # LAGU
            elif filename.endswith(
                ("mp3", "wav", "ogg", "m4a")
            ):
                music_files.append(file)

        # FOTO KE EMBED
        if image_file:
            embed.set_image(
                url=f"attachment://{image_file.filename}"
            )

        # STICKER KE EMBED
        if stickers:

            sticker = stickers[0]

            try:
                embed.set_thumbnail(
                    url=sticker.url
                )
            except:
                pass

        embed.set_footer(
            text=f"Quote by {interaction.user.display_name}"
        )

        # ==========================================
        # KIRIM EMBED
        # ==========================================
        send_files = []

        if image_file:
            send_files.append(image_file)

        quote_message = await quote_channel.send(
            embed=embed,
            files=send_files
        )

        # ==========================================
        # AUTO REACT (lovelike)
        # ==========================================
        try:
            await quote_message.add_reaction(LIKE_EMOJI)
        except discord.HTTPException:
            # fallback kalau emoji tidak bisa dipakai bot
            try:
                await quote_message.add_reaction("❤️")
            except discord.HTTPException:
                pass

        # ==========================================
        # AUTO THREAD
        # ==========================================
        try:
            await quote_message.create_thread(
                name=(
                    f"💭 Quote by "
                    f"{interaction.user.display_name}"
                )
            )
        except:
            pass

        # ==========================================
        # KIRIM LAGU
        # ==========================================
        for music in music_files:

            music_embed = discord.Embed(
                description=(
                    f"**Now Playing**\n"
                    f"`{music.filename}`"
                ),
                color=discord.Color.dark_theme()
            )

            await quote_channel.send(
                embed=music_embed,
                file=music
            )

        # hapus cache
        self.bot.quote_data.pop(
            interaction.user.id,
            None
        )

        return True

    # ==========================================
    # BUTTON UPLOAD
    # ==========================================
    @discord.ui.button(
        label="Upload Media",
        style=discord.ButtonStyle.blurple,
        custom_id="quote_upload_media"
    )
    async def upload_media(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            (
                "Sekarang kirim:\n"
                "🖼️ Foto\n"
                "🎵 Lagu\n"
                "🌸 Sticker\n\n"
                ">> Pesan akan otomatis dihapus.\n"
                "⏳ Tunggu dalam 60 detik."
            ),
            ephemeral=True
        )

        def check(message):
            return (
                message.author == interaction.user
                and message.channel == interaction.channel
            )

        files = []
        stickers = []

        try:
            msg = await self.bot.wait_for(
                "message",
                timeout=60,
                check=check
            )

            # file
            if msg.attachments:
                files = [
                    await attachment.to_file()
                    for attachment in msg.attachments
                ]

            # sticker
            if msg.stickers:
                stickers = msg.stickers

            # auto delete
            try:
                await msg.delete()
            except:
                pass

        except:
            await interaction.followup.send(
                "❌ Waktu upload habis.",
                ephemeral=True
            )
            return

        ok = await self.send_quote(
            interaction,
            files=files,
            stickers=stickers
        )

        if ok:
            await interaction.followup.send(
                "**Quote berhasil dikirim.**",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Data quote tidak ditemukan, silakan buat ulang.",
                ephemeral=True
            )

    # ==========================================
    # BUTTON SKIP
    # ==========================================
    @discord.ui.button(
        label="Skip",
        style=discord.ButtonStyle.gray,
        custom_id="quote_skip_media"
    )
    async def skip_media(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        ok = await self.send_quote(
            interaction
        )

        if ok:
            await interaction.followup.send(
                "**Quote berhasil dikirim tanpa media.**",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Data quote tidak ditemukan, silakan buat ulang.",
                ephemeral=True
            )


# ==========================================
# VIEW UTAMA (PERSISTENT)
# ==========================================
class QuoteView(discord.ui.View):

    def __init__(self, bot):
        # timeout=None + custom_id = tombol tetap aktif
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Buat Quote",
        style=discord.ButtonStyle.blurple,
        custom_id="quote_make_button"
    )
    async def make_quote(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            QuoteModal(self.bot)
        )


# ==========================================
# COG
# ==========================================
class QuoteSystem(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self._panel_banner = None  # cache PNG panel

        if not hasattr(bot, "quote_data"):
            bot.quote_data = {}

    async def cog_load(self):
        # daftarkan view supaya tombol tetap jalan
        # walaupun bot restart
        self.bot.add_view(QuoteView(self.bot))

    @commands.command(name="setupquote")
    @commands.has_permissions(administrator=True)
    async def setupquote(self, ctx):

        async with ctx.typing():
            if self._panel_banner is None:
                loop = asyncio.get_running_loop()
                self._panel_banner = await loop.run_in_executor(
                    None, generate_quote_panel
                )

        await ctx.send(
            file=discord.File(
                io.BytesIO(self._panel_banner),
                filename="quote_panel.png"
            ),
            view=QuoteView(self.bot)
        )

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass


# ==========================================
# SETUP
# ==========================================
async def setup(bot):
    await bot.add_cog(QuoteSystem(bot))