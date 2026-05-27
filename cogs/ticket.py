import discord
from discord.ext import commands

# ================= CONFIG =================

CATEGORY_ID = 1419613152609308702  # category ticket

# ROLE STAFF YANG BISA AKSES
STAFF_ROLE_IDS = [
    1453103644244316343,  # Moderator
    1467360501745844446,  # Pembina OSIS
    1427276194876751902   # OSIS
]

# ==========================================


# ======== WARNA ========
COLORS = {
    "Keluhan": discord.Color.orange(),
    "Konseling": discord.Color.blurple(),
    "Laporan": discord.Color.red(),
    "Partnership": discord.Color.green()
}


# ======== MODAL ========
class TicketModal(discord.ui.Modal):

    def __init__(self, category_name):
        super().__init__(title=f"{category_name} BK")

        self.category_name = category_name

        # ===== KELUHAN =====
        if category_name == "Keluhan":

            self.q1 = discord.ui.TextInput(
                label="Apa keluhan kamu?",
                style=discord.TextStyle.paragraph
            )

            self.q2 = discord.ui.TextInput(
                label="Sudah terjadi sejak kapan?",
                required=False
            )

            self.q3 = discord.ui.TextInput(
                label="Ada pihak yang terlibat?",
                required=False
            )

        # ===== KONSELING =====
        elif category_name == "Konseling":

            self.q1 = discord.ui.TextInput(
                label="Apa yang ingin kamu ceritakan?",
                style=discord.TextStyle.paragraph
            )

            self.q2 = discord.ui.TextInput(
                label="Apakah ingin anonim?",
                required=False,
                placeholder="Ya / Tidak"
            )

            self.q3 = discord.ui.TextInput(
                label="Hal yang kamu harapkan dari BK",
                required=False
            )

        # ===== LAPORAN =====
        elif category_name == "Laporan":

            self.q1 = discord.ui.TextInput(
                label="Siapa yang ingin dilaporkan?"
            )

            self.q2 = discord.ui.TextInput(
                label="Apa yang terjadi?",
                style=discord.TextStyle.paragraph
            )

            self.q3 = discord.ui.TextInput(
                label="Bukti / screenshot / saksi",
                required=False
            )

        # ===== PARTNERSHIP =====
        elif category_name == "Partnership":

            self.q1 = discord.ui.TextInput(
                label="Jenis pengajuan / partnership"
            )

            self.q2 = discord.ui.TextInput(
                label="Jelaskan kebutuhan kamu",
                style=discord.TextStyle.paragraph
            )

            self.q3 = discord.ui.TextInput(
                label="Link / info tambahan",
                required=False
            )

        self.add_item(self.q1)
        self.add_item(self.q2)

        if self.q3:
            self.add_item(self.q3)

    async def on_submit(self, interaction: discord.Interaction):

        guild = interaction.guild

        # ===== PERMISSION =====
        overwrites = {

            guild.default_role: discord.PermissionOverwrite(
                read_messages=False
            ),

            interaction.user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True
            )
        }

        # ===== TAMBAH SEMUA ROLE STAFF =====
        for role_id in STAFF_ROLE_IDS:

            role = guild.get_role(role_id)

            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True
                )

        # ===== BUAT CHANNEL =====
        channel = await guild.create_text_channel(
            name=f"{self.category_name.lower()}-{interaction.user.name}",
            category=guild.get_channel(CATEGORY_ID),
            overwrites=overwrites
        )

        # ===== EMBED =====
        embed = discord.Embed(
            title=f"🎓 nanZ BK — {self.category_name}",
            description="Staff BK akan segera membantu kamu.",
            color=COLORS[self.category_name]
        )

        for item in self.children:

            embed.add_field(
                name=item.label,
                value=item.value if item.value else "-",
                inline=False
            )

        embed.set_footer(
            text="Semua percakapan bersifat privat."
        )

        # ===== MENTION STAFF =====
        staff_mentions = " ".join(
            [f"<@&{role_id}>" for role_id in STAFF_ROLE_IDS]
        )

        await channel.send(
            content=f"{interaction.user.mention} | {staff_mentions}",
            embed=embed,
            view=DecisionView(interaction.user)
        )

        await interaction.response.send_message(
            f"Ticket berhasil dibuat: {channel.mention}",
            ephemeral=True
        )


# ======== STAFF BUTTON ========
class DecisionView(discord.ui.View):

    def __init__(self, user):
        super().__init__(timeout=None)

        self.user = user

    async def interaction_check(self, interaction: discord.Interaction) -> bool:

        # ===== CEK ROLE STAFF =====
        if any(role.id in STAFF_ROLE_IDS for role in interaction.user.roles):
            return True

        await interaction.response.send_message(
            "Kamu tidak punya akses untuk tombol ini.",
            ephemeral=True
        )

        return False

    # ===== TERIMA =====
    @discord.ui.button(
        label="Terima",
        style=discord.ButtonStyle.success
    )
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_message(
            "Ticket diterima oleh staff BK.",
            ephemeral=True
        )

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(view=self)

    # ===== TOLAK =====
    @discord.ui.button(
        label="Tolak",
        style=discord.ButtonStyle.danger
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_message(
            "Ticket ditolak & channel akan dihapus.",
            ephemeral=True
        )

        await interaction.channel.delete()


# ======== PANEL BUTTON ========
class TicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    # ===== KELUHAN =====
    @discord.ui.button(
        label="Keluhan",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_keluhan"
    )
    async def keluhan(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_modal(
            TicketModal("Keluhan")
        )

    # ===== KONSELING =====
    @discord.ui.button(
        label="Konseling",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_konseling"
    )
    async def konseling(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_modal(
            TicketModal("Konseling")
        )

    # ===== LAPORAN =====
    @discord.ui.button(
        label="Laporan",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_laporan"
    )
    async def laporan(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_modal(
            TicketModal("Laporan")
        )

    # ===== PARTNERSHIP =====
    @discord.ui.button(
        label="Pengajuan & Partnership",
        style=discord.ButtonStyle.success,
        custom_id="ticket_partnership"
    )
    async def partnership(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_modal(
            TicketModal("Partnership")
        )


# ======== COG ========
class Ticket(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setup_bk")
    @commands.has_permissions(administrator=True)
    async def setup_bk(self, ctx):

        embed = discord.Embed(
            title="nanZ Server Support",

            description=(

                "Pilih kategori yang sesuai dengan kebutuhan kamu.\n\n"

                "📚 **Keluhan**\n"
                "Laporkan pengalaman tidak nyaman atau masalah yang kamu alami.\n\n"

                "🫂 **Konseling**\n"
                "Curhat, konsultasi, atau berbicara langsung bersama staff BK.\n\n"

                "⚠️ **Laporan**\n"
                "Laporkan pelanggaran aturan, bullying, maupun perilaku tidak baik.\n\n"

                "🤝 **Pengajuan & Partnership**\n"
                "Ajukan izin, kerja sama, partnership, maupun kebutuhan administrasi lainnya.\n\n"

                "Semua ticket bersifat privat dan hanya dapat dilihat oleh kamu & staff BK."
            ),

            color=discord.Color.from_rgb(88, 101, 242)
        )

        embed.set_footer(
            text="nanZ Server • Ruang BK"
        )

        await ctx.send(
            embed=embed,
            view=TicketView()
        )


# ======== LOAD COG ========
async def setup(bot):
    await bot.add_cog(Ticket(bot))