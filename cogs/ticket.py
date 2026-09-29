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
CATEGORY_ID = 1419613152609308702  # category ticket

# ROLE STAFF YANG BISA AKSES
STAFF_ROLE_IDS = [
    1453103644244316343,  # Moderator
    1467360501745844446,  # Pembina OSIS
    1427276194876751902,  # OSIS
]

# Font (sama seperti panel suggestion)
FONT_BOLD = "fonts/LEMONMILK-Bold.otf"
FONT_REGULAR = "fonts/LEMONMILK-Regular.otf"
_FALLBACKS = ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf")

# Tema biru + ungu (sama dengan suggestion)
BG_TOP, BG_BOT = (18, 10, 45), (40, 20, 80)
PURPLE, BLUE = (130, 80, 255), (80, 180, 255)
CARD_BG = (30, 15, 65)
SOFT_PURPLE, SOFT_BLUE = (160, 120, 255), (150, 210, 255)

# Aksen tiap kategori
ORANGE, PINK, GREEN = (255, 170, 80), (255, 100, 140), (90, 220, 160)

W, H, S = 900, 540, 2  # ukuran akhir + supersampling

COLORS = {
    "Keluhan": discord.Color.orange(),
    "Konseling": discord.Color.blurple(),
    "Laporan": discord.Color.red(),
    "Partnership": discord.Color.green(),
}


# ══════════════════════════════════════════════
#  HELPER GAMBAR
# ══════════════════════════════════════════════
def _font(path, px):
    for p in (path, *_FALLBACKS):
        try:
            return ImageFont.truetype(p, int(px))
        except Exception:
            continue
    return ImageFont.load_default()


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _fit(d, text, path, start, max_w, s, min_size=9):
    size = start
    while size > min_size:
        fn = _font(path, size * s)
        if d.textlength(text, font=fn) <= max_w * s:
            return fn
        size -= 1
    return _font(path, min_size * s)


def _wrap(d, text, font, max_w_px):
    """Bungkus teks berdasarkan lebar piksel (bukan jumlah karakter)."""
    lines, cur = [], ""
    for word in text.split():
        test = f"{cur} {word}".strip()
        if d.textlength(test, font=font) <= max_w_px:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# ══════════════════════════════════════════════
#  PNG PANEL TICKET
# ══════════════════════════════════════════════
def generate_ticket_panel() -> bytes:
    s = S
    sc = lambda v: [int(x * s) for x in v]
    P = lambda pts: [(x * s, y * s) for x, y in pts]
    F = lambda path, sz: _font(path, sz * s)
    fit = lambda d, t, path, start, mw: _fit(d, t, path, start, mw, s)

    # ---------- background ----------
    base = Image.new("RGB", (W * s, H * s))
    d = ImageDraw.Draw(base)
    for y in range(H * s):
        d.line([(0, y), (W * s, y)], fill=_lerp(BG_TOP, BG_BOT, y / (H * s)))
    base = base.convert("RGBA")

    def layer(fn, blur=0):
        """Gambar di layer transparan lalu gabungkan (supaya alpha ter-blend)."""
        nonlocal base
        lay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        fn(ImageDraw.Draw(lay))
        if blur:
            lay = lay.filter(ImageFilter.GaussianBlur(blur * s))
        base = Image.alpha_composite(base, lay)

    # orb cahaya
    def orbs(od):
        for ox, oy, r, c in [(90, 60, 160, PURPLE), (840, 500, 170, BLUE), (600, 20, 110, PURPLE)]:
            for st in range(r, 0, -5):
                od.ellipse(sc([ox - st, oy - st, ox + st, oy + st]), fill=(*c, int(55 * (st / r) ** 2.8)))
    layer(orbs)

    # bintang kecil
    rng = random.Random(11)

    def stars(sd):
        for _ in range(70):
            x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1, 2.4)
            sd.ellipse(sc([x - r, y - r, x + r, y + r]),
                       fill=(*_lerp(PURPLE, BLUE, rng.random()), rng.randint(80, 190)))
    layer(stars)

    # panel utama
    def panel(pd):
        pd.rounded_rectangle(sc([20, 20, 880, 520]), radius=30 * s, fill=(*CARD_BG, 200))
        pd.rounded_rectangle(sc([20, 20, 880, 520]), radius=30 * s, outline=(*PURPLE, 100), width=2 * s)
    layer(panel)

    # ---------- HEADER (kiri) ----------
    LX0 = 50
    d = ImageDraw.Draw(base)

    pill = "RUANG BK"
    fp = F(FONT_BOLD, 11)
    pw = d.textlength(pill, font=fp) / s + 34
    layer(lambda g: g.rounded_rectangle(sc([LX0, 48, LX0 + pw, 72]), radius=12 * s, fill=(*PURPLE, 230)))
    d = ImageDraw.Draw(base)
    d.text(((LX0 + pw / 2) * s, 60 * s), pill, font=fp, fill=(255, 255, 255), anchor="mm")

    # judul gradient
    title = "TIKET BANTUAN"
    ft = fit(d, title, FONT_BOLD, 50, 520)
    tb = d.textbbox((0, 0), title, font=ft)
    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).text((LX0 * s, 84 * s), title, font=ft, fill=255)
    grad = Image.new("RGBA", base.size)
    gd = ImageDraw.Draw(grad)
    x0, span = LX0 * s, max(1, tb[2] - tb[0])
    for x in range(int(x0), int(x0 + span) + 2):
        gd.line([(x, 0), (x, H * s)], fill=(*_lerp((255, 255, 255), SOFT_BLUE, min(1, (x - x0) / span)), 255))
    grad.putalpha(mask)
    base = Image.alpha_composite(base, grad)
    d = ImageDraw.Draw(base)

    l1 = "Ada masalah, cerita, atau pengajuan? Buka tiket di sini."
    l2 = "Isi form singkat, lalu channel privat khusus staff BK dibuat."
    d.text((LX0 * s, 158 * s), l1, font=fit(d, l1, FONT_REGULAR, 14, 540), fill=(225, 225, 245), anchor="lm")
    d.text((LX0 * s, 180 * s), l2, font=fit(d, l2, FONT_REGULAR, 14, 540), fill=(175, 170, 215), anchor="lm")

    # ---------- ILUSTRASI TIKET (kanan atas) ----------
    tk = Image.new("RGBA", (300 * s, 180 * s), (0, 0, 0, 0))
    td = ImageDraw.Draw(tk)
    # bayangan
    sh = Image.new("RGBA", tk.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(sc([26, 40, 246, 134]), radius=14 * s, fill=(0, 0, 0, 110))
    tk = Image.alpha_composite(tk, sh.filter(ImageFilter.GaussianBlur(6 * s)))
    td = ImageDraw.Draw(tk)
    # badan tiket
    td.rounded_rectangle(sc([20, 30, 240, 124]), radius=14 * s, fill=(245, 245, 255))
    td.rounded_rectangle(sc([20, 30, 100, 124]), radius=14 * s, fill=PURPLE)
    td.rectangle(sc([80, 30, 100, 124]), fill=PURPLE)
    # takik atas & bawah (pemisah)
    for cy in (30, 124):
        td.ellipse(sc([92, cy - 9, 110, cy + 9]), fill=(0, 0, 0, 0))
    # garis putus-putus
    for y in range(40, 118, 9):
        td.line(sc([101, y, 101, y + 4]), fill=(190, 185, 225), width=2 * s)
    # isi
    ftk = _font(FONT_BOLD, 26 * s)
    td.text((60 * s, 77 * s), "BK", font=ftk, fill=(255, 255, 255), anchor="mm")
    td.rounded_rectangle(sc([120, 50, 210, 60]), radius=5 * s, fill=(70, 40, 160))
    td.rounded_rectangle(sc([120, 70, 190, 78]), radius=4 * s, fill=(200, 205, 235))
    td.rounded_rectangle(sc([120, 86, 200, 94]), radius=4 * s, fill=(200, 205, 235))
    td.rounded_rectangle(sc([120, 102, 160, 112]), radius=5 * s, fill=BLUE)
    tk = tk.rotate(-8, expand=True, resample=Image.BICUBIC)
    base.alpha_composite(tk, (600 * s, 34 * s))

    def sparkle(x, y, sz, col):
        q = sz * .25
        return lambda g: g.polygon(P([(x, y - sz), (x + q, y - q), (x + sz, y), (x + q, y + q), (x, y + sz),
                                      (x - q, y + q), (x - sz, y), (x - q, y - q)]), fill=(*col, 230))
    for x, y, sz, c in [(600, 60, 9, SOFT_BLUE), (850, 44, 7, SOFT_PURPLE), (835, 160, 8, SOFT_BLUE),
                       (590, 150, 6, SOFT_PURPLE), (700, 40, 6, SOFT_BLUE)]:
        layer(sparkle(x, y, sz, c))

    # garis pemisah gradien
    def divider(g):
        for i in range(46, 854):
            g.rectangle(sc([i, 204, i + 1, 206]), fill=(*_lerp(BLUE, PURPLE, (i - 46) / 808), 200))
    layer(divider)

    # ---------- 4 KARTU KATEGORI (2x2) ----------
    cats = [
        ("Keluhan", "Laporkan pengalaman tidak nyaman atau masalah yang kamu alami.", ORANGE, "bubble"),
        ("Konseling", "Curhat, konsultasi, atau bicara langsung bersama staff BK.", SOFT_PURPLE, "heart"),
        ("Laporan", "Laporkan pelanggaran aturan, bullying, atau perilaku tidak baik.", PINK, "alert"),
        ("Pengajuan & Partnership", "Ajukan izin, kerja sama, partnership, atau kebutuhan administrasi.", GREEN, "link"),
    ]
    CW, CH, GAP = 396, 118, 16
    for i, (name, desc, col, icon) in enumerate(cats):
        cx0 = 46 + (i % 2) * (CW + GAP)
        cy0 = 224 + (i // 2) * (CH + GAP)
        cx1, cy1 = cx0 + CW, cy0 + CH

        def card(g, cx0=cx0, cy0=cy0, cx1=cx1, cy1=cy1, col=col):
            g.rounded_rectangle(sc([cx0, cy0, cx1, cy1]), radius=20 * s, fill=(*PURPLE, 34))
            g.rounded_rectangle(sc([cx0, cy0, cx1, cy1]), radius=20 * s, outline=(*SOFT_PURPLE, 80), width=s)
            # strip aksen di kiri
            g.rounded_rectangle(sc([cx0 + 1, cy0 + 22, cx0 + 6, cy1 - 22]), radius=3 * s, fill=(*col, 255))
        layer(card)

        # ikon
        icx, icy, ir = cx0 + 50, cy0 + CH / 2, 28

        def icon_bg(g, icx=icx, icy=icy, col=col):
            g.ellipse(sc([icx - ir - 6, icy - ir - 6, icx + ir + 6, icy + ir + 6]), fill=(*col, 45))
            g.ellipse(sc([icx - ir, icy - ir, icx + ir, icy + ir]), fill=(*col, 255))
        layer(icon_bg)
        d = ImageDraw.Draw(base)
        wh = (255, 255, 255)
        if icon == "bubble":
            d.rounded_rectangle(sc([icx - 14, icy - 12, icx + 14, icy + 8]), radius=6 * s, fill=wh)
            d.polygon(P([(icx - 6, icy + 7), (icx - 10, icy + 17), (icx + 3, icy + 7)]), fill=wh)
            for dx in (-7, 0, 7):
                d.ellipse(sc([icx + dx - 2, icy - 5, icx + dx + 2, icy - 1]), fill=col)
        elif icon == "heart":
            d.ellipse(sc([icx - 15, icy - 14, icx, icy + 1]), fill=wh)
            d.ellipse(sc([icx, icy - 14, icx + 15, icy + 1]), fill=wh)
            d.polygon(P([(icx - 14.5, icy - 3), (icx + 14.5, icy - 3), (icx, icy + 15)]), fill=wh)
        elif icon == "alert":
            d.polygon(P([(icx, icy - 16), (icx + 17, icy + 13), (icx - 17, icy + 13)]), fill=wh)
            d.rounded_rectangle(sc([icx - 2, icy - 6, icx + 2, icy + 3]), radius=s, fill=col)
            d.ellipse(sc([icx - 2, icy + 6, icx + 2, icy + 10]), fill=col)
        elif icon == "link":
            d.ellipse(sc([icx - 17, icy - 10, icx + 3, icy + 10]), outline=wh, width=4 * s)
            d.ellipse(sc([icx - 3, icy - 10, icx + 17, icy + 10]), outline=wh, width=4 * s)

        # teks
        tx = cx0 + 96
        tw = CW - 96 - 20
        d.text((tx * s, (cy0 + 30) * s), name, font=fit(d, name, FONT_BOLD, 17, tw),
               fill=(255, 255, 255), anchor="lm")
        fdesc = F(FONT_REGULAR, 11.5)
        for j, line in enumerate(_wrap(d, desc, fdesc, tw * s)[:3]):
            d.text((tx * s, (cy0 + 54 + j * 18) * s), line, font=fdesc, fill=SOFT_BLUE, anchor="lm")

    # ---------- FOOTER ----------
    fy = 502
    foot = "Semua tiket bersifat privat. Hanya kamu & staff BK yang bisa melihatnya."
    ff = fit(d, foot, FONT_REGULAR, 12, 700)
    fw = d.textlength(foot, font=ff) / s
    startx = (W - (fw + 30)) / 2
    layer(lambda g: g.ellipse(sc([startx, fy - 8, startx + 16, fy + 8]), fill=(*BLUE, 255)))
    d = ImageDraw.Draw(base)
    # gembok mini
    d.rounded_rectangle(sc([startx + 4, fy - 1, startx + 12, fy + 5]), radius=s, fill=(255, 255, 255))
    d.arc(sc([startx + 5, fy - 6, startx + 11, fy + 1]), 180, 360, fill=(255, 255, 255), width=s)
    d.text(((startx + 28) * s, fy * s), foot, font=ff, fill=(200, 200, 235), anchor="lm")

    out = base.convert("RGB").resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ══════════════════════════════════════════════
#  MODAL
# ══════════════════════════════════════════════
class TicketModal(discord.ui.Modal):

    def __init__(self, category_name):
        super().__init__(title=f"{category_name} BK")
        self.category_name = category_name

        if category_name == "Keluhan":
            self.q1 = discord.ui.TextInput(label="Apa keluhan kamu?", style=discord.TextStyle.paragraph)
            self.q2 = discord.ui.TextInput(label="Sudah terjadi sejak kapan?", required=False)
            self.q3 = discord.ui.TextInput(label="Ada pihak yang terlibat?", required=False)

        elif category_name == "Konseling":
            self.q1 = discord.ui.TextInput(label="Apa yang ingin kamu ceritakan?", style=discord.TextStyle.paragraph)
            self.q2 = discord.ui.TextInput(label="Apakah ingin anonim?", required=False, placeholder="Ya / Tidak")
            self.q3 = discord.ui.TextInput(label="Hal yang kamu harapkan dari BK", required=False)

        elif category_name == "Laporan":
            self.q1 = discord.ui.TextInput(label="Siapa yang ingin dilaporkan?")
            self.q2 = discord.ui.TextInput(label="Apa yang terjadi?", style=discord.TextStyle.paragraph)
            self.q3 = discord.ui.TextInput(label="Bukti / screenshot / saksi", required=False)

        else:  # Partnership
            self.q1 = discord.ui.TextInput(label="Jenis pengajuan / partnership")
            self.q2 = discord.ui.TextInput(label="Jelaskan kebutuhan kamu", style=discord.TextStyle.paragraph)
            self.q3 = discord.ui.TextInput(label="Link / info tambahan", required=False)

        self.add_item(self.q1)
        self.add_item(self.q2)
        self.add_item(self.q3)

    async def on_submit(self, interaction: discord.Interaction):
        # defer dulu supaya tidak timeout saat bikin channel
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild

        # ===== PERMISSION: hanya staff + pembuat tiket =====
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=True, manage_channels=True
            ),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        for role_id in STAFF_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        try:
            channel = await guild.create_text_channel(
                name=f"{self.category_name.lower()}-{interaction.user.name}",
                category=guild.get_channel(CATEGORY_ID),
                overwrites=overwrites,
            )
        except discord.Forbidden:
            return await interaction.followup.send("❌ Bot tidak punya izin membuat channel.", ephemeral=True)
        except discord.HTTPException as e:
            print("[Ticket] gagal bikin channel:", e)
            return await interaction.followup.send("❌ Gagal membuat ticket, coba lagi nanti.", ephemeral=True)

        # ===== EMBED =====
        embed = discord.Embed(
            title=f"🎓 nanZ BK — {self.category_name}",
            description="Staff BK akan segera membantu kamu.",
            color=COLORS[self.category_name],
        )
        for item in self.children:
            embed.add_field(name=item.label, value=item.value or "-", inline=False)
        embed.set_footer(text="Semua percakapan bersifat privat.")

        staff_mentions = " ".join(f"<@&{rid}>" for rid in STAFF_ROLE_IDS)

        await channel.send(
            content=f"{interaction.user.mention} | {staff_mentions}",
            embed=embed,
            view=DecisionView(),
        )

        await interaction.followup.send(f"✅ Ticket berhasil dibuat: {channel.mention}", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print("[Ticket] modal error:", error)
        msg = "❌ Terjadi kesalahan, coba lagi ya."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


# ══════════════════════════════════════════════
#  TOMBOL STAFF (persistent, tidak butuh data user)
# ══════════════════════════════════════════════
class DecisionView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if any(role.id in STAFF_ROLE_IDS for role in interaction.user.roles):
            return True
        await interaction.response.send_message("Kamu tidak punya akses untuk tombol ini.", ephemeral=True)
        return False

    @discord.ui.button(label="Terima", style=discord.ButtonStyle.success, custom_id="ticket_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"✅ Ticket diterima oleh {interaction.user.mention}.")

    @discord.ui.button(label="Tolak", style=discord.ButtonStyle.danger, custom_id="ticket_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Ticket ditolak & channel akan dihapus.", ephemeral=True)
        await interaction.channel.delete()


# ══════════════════════════════════════════════
#  TOMBOL PANEL (persistent, di bawah gambar)
# ══════════════════════════════════════════════
class TicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Keluhan", style=discord.ButtonStyle.primary, custom_id="ticket_keluhan")
    async def keluhan(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal("Keluhan"))

    @discord.ui.button(label="Konseling", style=discord.ButtonStyle.secondary, custom_id="ticket_konseling")
    async def konseling(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal("Konseling"))

    @discord.ui.button(label="Laporan", style=discord.ButtonStyle.danger, custom_id="ticket_laporan")
    async def laporan(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal("Laporan"))

    @discord.ui.button(label="Pengajuan & Partnership", style=discord.ButtonStyle.success,
                       custom_id="ticket_partnership")
    async def partnership(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal("Partnership"))


# ══════════════════════════════════════════════
#  COG
# ══════════════════════════════════════════════
class Ticket(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self._panel_banner = None  # cache PNG panel

    async def cog_load(self):
        # daftarkan tombol supaya tetap jalan setelah bot restart
        self.bot.add_view(TicketView())
        self.bot.add_view(DecisionView())

    @commands.command(name="setup_bk")
    @commands.has_permissions(administrator=True)
    async def setup_bk(self, ctx: commands.Context):
        async with ctx.typing():
            if self._panel_banner is None:
                loop = asyncio.get_running_loop()
                self._panel_banner = await loop.run_in_executor(None, generate_ticket_panel)

        await ctx.send(
            file=discord.File(io.BytesIO(self._panel_banner), filename="ticket_bk.png"),
            view=TicketView(),
        )
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass


# ══════════════════════════════════════════════
#  SETUP
# ══════════════════════════════════════════════
async def setup(bot):
    await bot.add_cog(Ticket(bot))