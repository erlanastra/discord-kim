import discord
from discord.ext import commands


TARGET_CHANNEL_ID = 1547540103117803520


class RoleRequestModal(
    discord.ui.Modal,
    title="Form Request Role Kustom"
):

    role_name = discord.ui.TextInput(
        label="Nama Role",
        placeholder="Contoh: ✨ King of Night",
        max_length=50,
        required=True
    )

    role_color = discord.ui.TextInput(
        label="Kode Warna Hex",
        placeholder="Contoh: #FF5733",
        max_length=7,
        required=True
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        if interaction.channel_id != TARGET_CHANNEL_ID:

            await interaction.response.send_message(
                f"❌ Request role hanya bisa dilakukan di "
                f"<#{TARGET_CHANNEL_ID}>!",
                ephemeral=True
            )

            return

        await interaction.response.defer(
            ephemeral=True
        )

        guild = interaction.guild
        member = interaction.user

        name = self.role_name.value.strip()
        color_code = self.role_color.value.strip()

        # ==============================================
        # VALIDASI HEX
        # ==============================================

        if color_code.startswith("#"):
            hex_code = color_code[1:]
        else:
            hex_code = color_code

        if len(hex_code) != 6:

            await interaction.followup.send(
                "❌ Kode warna harus 6 digit Hex.\n"
                "Contoh: `#FF5733`",
                ephemeral=True
            )

            return

        try:

            color_value = int(hex_code, 16)

            discord_color = discord.Color(
                color_value
            )

        except ValueError:

            await interaction.followup.send(
                "❌ Kode warna tidak valid!\n"
                "Gunakan format seperti `#FF5733`.",
                ephemeral=True
            )

            return

        # ==============================================
        # BUAT ROLE
        # ==============================================

        try:

            new_role = await guild.create_role(
                name=name,
                color=discord_color,
                reason=(
                    f"Custom role request oleh "
                    f"{member} ({member.id})"
                )
            )

            # ==========================================
            # BERIKAN ROLE
            # ==========================================

            await member.add_roles(
                new_role,
                reason="Custom role otomatis"
            )

            await interaction.followup.send(
                f"✅ **Role berhasil dibuat!**\n\n"
                f"**Nama:** {new_role.mention}\n"
                f"**Warna:** `#{hex_code.upper()}`\n\n"
                f"Role sudah otomatis diberikan kepada kamu.",
                ephemeral=True
            )

        except discord.Forbidden:

            await interaction.followup.send(
                "❌ Bot tidak memiliki izin **Manage Roles** "
                "atau posisi role bot terlalu rendah.",
                ephemeral=True
            )

        except Exception as e:

            await interaction.followup.send(
                f"❌ Terjadi kesalahan:\n```{e}```",
                ephemeral=True
            )


# ==========================================================
# PERSISTENT VIEW
# ==========================================================

class RoleRequestView(discord.ui.View):

    def __init__(self):

        # WAJIB NONE
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Request Role Kustom",
        style=discord.ButtonStyle.primary,
        emoji="🎨",
        custom_id="nanz_request_custom_role"
    )
    async def request_btn(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.channel_id != TARGET_CHANNEL_ID:

            await interaction.response.send_message(
                f"❌ Silakan gunakan tombol di "
                f"<#{TARGET_CHANNEL_ID}>!",
                ephemeral=True
            )

            return

        await interaction.response.send_modal(
            RoleRequestModal()
        )


# ==========================================================
# COG
# ==========================================================

class RoleRequestCog(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    @commands.command(
        name="setup-role-panel",
        aliases=["rolepanel"]
    )
    @commands.has_permissions(
        administrator=True
    )
    async def setup_role_panel(
        self,
        ctx: commands.Context
    ):

        # Hanya channel khusus
        if ctx.channel.id != TARGET_CHANNEL_ID:

            await ctx.reply(
                f"❌ Command ini hanya bisa digunakan "
                f"di <#{TARGET_CHANNEL_ID}>!",
                mention_author=False
            )

            return

        # ==============================================
        # EMBED
        # ==============================================

        embed = discord.Embed(
            title="🎨 Request Role Kustom nanZ Server",

            description=(
                "Mau punya role eksklusif dengan warna "
                "pilihanmu sendiri?\n\n"

                "Klik tombol **Request Role Kustom** "
                "di bawah untuk membuat role.\n\n"

                "📝 **Nama Role**\n"
                "🎨 **Warna Role**\n\n"

                "Gunakan kode warna Hex:\n"
                "`#FF0000` → Merah\n"
                "`#00FF00` → Hijau\n"
                "`#0000FF` → Biru\n"
                "`#FF00FF` → Ungu/Pink\n\n"

                "⚠️ Format warna harus `#RRGGBB`."
            ),

            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="nanZ Server • Custom Role System"
        )

        # ==============================================
        # KIRIM PANEL
        # ==============================================

        await ctx.send(
            embed=embed,
            view=RoleRequestView()
        )

        # Hapus command setelah panel dikirim
        try:

            await ctx.message.delete()

        except discord.Forbidden:

            pass


async def setup(bot):

    await bot.add_cog(
        RoleRequestCog(bot)
    )