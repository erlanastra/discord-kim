import discord
from discord.ext import commands
from urllib.parse import urlparse


# ==========================================================
# CONFIG
# ==========================================================

TARGET_CHANNEL_ID = 1547540103117803520

# Maksimal member yang bisa menerima role sekaligus
MAX_RECIPIENTS = 25

# Batas ukuran icon: 256 KB
MAX_ICON_SIZE = 256 * 1024


# ==========================================================
# HELPER
# ==========================================================

def parse_hex_color(value: str):
    """
    Mengubah #RRGGBB menjadi discord.Color.
    """

    value = value.strip().replace("#", "")

    if len(value) != 6:
        raise ValueError(
            "Warna harus menggunakan format #RRGGBB."
        )

    try:
        number = int(value, 16)
    except ValueError:
        raise ValueError(
            "Kode warna Hex tidak valid."
        )

    if not 0 <= number <= 0xFFFFFF:
        raise ValueError(
            "Kode warna berada di luar range."
        )

    return discord.Color(number)


def is_valid_image_url(url: str):
    """
    Validasi sederhana URL icon.
    """

    if not url:
        return False

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return False

    if not parsed.netloc:
        return False

    return True


# ==========================================================
# MODAL INPUT
# ==========================================================

class RoleRequestModal(
    discord.ui.Modal,
    title="🎨 Custom Role"
):

    role_name = discord.ui.TextInput(
        label="Nama Role",
        placeholder="Contoh: ✨ King of Night",
        max_length=50,
        required=True
    )

    primary_color = discord.ui.TextInput(
        label="Warna Utama",
        placeholder="Contoh: #FF0000",
        max_length=7,
        required=True
    )

    secondary_color = discord.ui.TextInput(
        label="Warna Kedua / Gradient",
        placeholder="Contoh: #0000FF",
        max_length=7,
        required=False
    )

    icon = discord.ui.TextInput(
        label="Icon Role",
        placeholder="Emoji 👑 atau URL PNG/JPG",
        max_length=500,
        required=False
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        # ==================================================
        # CHANNEL CHECK
        # ==================================================

        if interaction.channel_id != TARGET_CHANNEL_ID:

            await interaction.response.send_message(
                f"❌ Custom role hanya bisa dibuat di "
                f"<#{TARGET_CHANNEL_ID}>.",
                ephemeral=True
            )

            return

        # ==================================================
        # ADMIN CHECK
        # ==================================================

        if not interaction.user.guild_permissions.administrator:

            await interaction.response.send_message(
                "❌ Hanya **Administrator** yang dapat "
                "membuat custom role melalui sistem ini.",
                ephemeral=True
            )

            return

        # ==================================================
        # PARSE DATA
        # ==================================================

        name = self.role_name.value.strip()

        primary_hex = self.primary_color.value.strip()

        secondary_hex = self.secondary_color.value.strip()

        icon_value = self.icon.value.strip()

        # ==================================================
        # VALIDATE PRIMARY COLOR
        # ==================================================

        try:

            primary_color = parse_hex_color(
                primary_hex
            )

        except ValueError as e:

            await interaction.response.send_message(
                f"❌ {e}",
                ephemeral=True
            )

            return

        # ==================================================
        # VALIDATE SECONDARY COLOR
        # ==================================================

        secondary_color = None

        if secondary_hex:

            try:

                secondary_color = parse_hex_color(
                    secondary_hex
                )

            except ValueError as e:

                await interaction.response.send_message(
                    f"❌ Warna kedua tidak valid: {e}",
                    ephemeral=True
                )

                return

        # ==================================================
        # VALIDATE ICON
        # ==================================================

        icon_data = None

        if icon_value:

            # ----------------------------------------------
            # DISCORD UNICODE EMOJI
            # ----------------------------------------------

            if not is_valid_image_url(icon_value):

                # Kita anggap sebagai Unicode emoji.
                # Discord akan memvalidasinya saat create_role.
                icon_data = icon_value

            else:

                # ------------------------------------------
                # DOWNLOAD IMAGE
                # ------------------------------------------

                try:

                    async with interaction.client.http_session.get(
                        icon_value,
                        timeout=10
                    ) as response:

                        if response.status != 200:

                            raise ValueError(
                                f"HTTP {response.status}"
                            )

                        content_type = response.headers.get(
                            "Content-Type",
                            ""
                        ).lower()

                        if (
                            "image/png" not in content_type
                            and "image/jpeg" not in content_type
                            and "image/jpg" not in content_type
                        ):

                            raise ValueError(
                                "Icon harus PNG atau JPEG."
                            )

                        data = await response.read()

                        if len(data) > MAX_ICON_SIZE:

                            raise ValueError(
                                "Ukuran icon maksimal 256 KB."
                            )

                        icon_data = data

                except Exception as e:

                    await interaction.response.send_message(
                        "❌ Gagal mengambil icon.\n"
                        f"Pastikan URL merupakan gambar PNG/JPEG "
                        f"yang bisa diakses publik.\n\n"
                        f"Detail: `{e}`",
                        ephemeral=True
                    )

                    return

        # ==================================================
        # SIMPAN DATA SEMENTARA
        # ==================================================

        await interaction.response.send_message(
            "### 🎨 Custom Role\n\n"
            "Data role sudah diterima.\n\n"
            "Sekarang pilih **style role** dan **member yang "
            "akan menerima role**.",
            view=RoleConfigurationView(
                requester=interaction.user,
                role_name=name,
                primary_color=primary_color,
                secondary_color=secondary_color,
                icon_data=icon_data
            ),
            ephemeral=True
        )


# ==========================================================
# STYLE SELECT
# ==========================================================

class RoleStyleSelect(
    discord.ui.Select
):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="Solid",
                description="Satu warna solid",
                emoji="🎨",
                value="solid"
            ),

            discord.SelectOption(
                label="Gradient",
                description="Gradient menggunakan 2 warna",
                emoji="🌈",
                value="gradient"
            ),

            discord.SelectOption(
                label="Holographic",
                description="Style holographic Discord",
                emoji="✨",
                value="holographic"
            )

        ]

        super().__init__(
            placeholder="🎨 Pilih style role...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="nanz_role_style_select"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        self.view.selected_style = self.values[0]

        await interaction.response.edit_message(
            content=(
                "### 🎨 Custom Role\n\n"
                f"**Style:** `{self.values[0].title()}`\n\n"
                "Sekarang pilih member yang akan "
                "menerima role."
            ),
            view=self.view
        )


# ==========================================================
# USER SELECT
# ==========================================================

class RoleRecipientSelect(
    discord.ui.UserSelect
):

    def __init__(self):

        super().__init__(
            placeholder="👥 Pilih member penerima role...",
            min_values=1,
            max_values=MAX_RECIPIENTS,
            custom_id="nanz_role_recipient_select"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        self.view.selected_members = self.values

        names = [
            member.display_name
            for member in self.values
        ]

        preview = ", ".join(names)

        if len(preview) > 500:

            preview = preview[:500] + "..."

        await interaction.response.edit_message(
            content=(
                "### 🎨 Custom Role\n\n"
                f"**Style:** "
                f"`{self.view.selected_style.title()}`\n\n"
                f"**Penerima:**\n"
                f"{preview}\n\n"
                "Jika sudah benar, klik **Buat & Berikan Role**."
            ),
            view=self.view
        )


# ==========================================================
# CONFIGURATION VIEW
# ==========================================================

class RoleConfigurationView(
    discord.ui.View
):

    def __init__(
        self,
        requester,
        role_name,
        primary_color,
        secondary_color,
        icon_data
    ):

        super().__init__(
            timeout=300
        )

        self.requester = requester

        self.role_name = role_name

        self.primary_color = primary_color

        self.secondary_color = secondary_color

        self.icon_data = icon_data

        self.selected_style = "solid"

        self.selected_members = []

        # ----------------------------------------------
        # STYLE
        # ----------------------------------------------

        self.add_item(
            RoleStyleSelect()
        )

        # ----------------------------------------------
        # MEMBER SELECT
        # ----------------------------------------------

        self.add_item(
            RoleRecipientSelect()
        )

    # ==================================================
    # CREATE ROLE
    # ==================================================

    @discord.ui.button(
        label="Buat & Berikan Role",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="nanz_create_custom_role",
        row=3
    )
    async def create_role_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        # ==================================================
        # USER CHECK
        # ==================================================

        if interaction.user.id != self.requester.id:

            await interaction.response.send_message(
                "❌ Kamu tidak bisa menggunakan konfigurasi "
                "milik orang lain.",
                ephemeral=True
            )

            return

        # ==================================================
        # MEMBER CHECK
        # ==================================================

        if not self.selected_members:

            await interaction.response.send_message(
                "❌ Pilih minimal satu member penerima role.",
                ephemeral=True
            )

            return

        # ==================================================
        # STYLE VALIDATION
        # ==================================================

        if self.selected_style == "gradient":

            if self.secondary_color is None:

                await interaction.response.send_message(
                    "❌ Gradient membutuhkan **Warna Kedua**.",
                    ephemeral=True
                )

                return

        # ==================================================
        # DISABLE BUTTON
        # ==================================================

        button.disabled = True

        await interaction.response.edit_message(
            content="⏳ Sedang membuat role...",
            view=self
        )

        guild = interaction.guild

        # ==================================================
        # CREATE ROLE PARAMETERS
        # ==================================================

        create_kwargs = {
            "name": self.role_name,
            "colour": self.primary_color,
            "reason": (
                f"Custom role dibuat oleh "
                f"{interaction.user} ({interaction.user.id})"
            )
        }

        # ==================================================
        # GRADIENT
        # ==================================================

        if self.selected_style == "gradient":

            create_kwargs[
                "secondary_colour"
            ] = self.secondary_color

        # ==================================================
        # HOLOGRAPHIC
        # ==================================================

        elif self.selected_style == "holographic":

            # Discord holographic preset
            create_kwargs[
                "secondary_colour"
            ] = discord.Color(
                0xA9B3FF
            )

            create_kwargs[
                "tertiary_colour"
            ] = discord.Color(
                0xFFA8DC
            )

        # ==================================================
        # ICON
        # ==================================================

        if self.icon_data:

            create_kwargs[
                "display_icon"
            ] = self.icon_data

        # ==================================================
        # CREATE
        # ==================================================

        try:

            new_role = await guild.create_role(
                **create_kwargs
            )

        except discord.Forbidden:

            await interaction.edit_original_response(
                content=(
                    "❌ **Gagal membuat role.**\n\n"
                    "Pastikan bot mempunyai permission "
                    "**Manage Roles** dan role bot berada "
                    "di posisi yang cukup tinggi."
                ),
                view=None
            )

            return

        except discord.HTTPException as e:

            await interaction.edit_original_response(
                content=(
                    "❌ Discord menolak pembuatan role.\n\n"
                    f"```{e}```"
                ),
                view=None
            )

            return

        except Exception as e:

            await interaction.edit_original_response(
                content=(
                    "❌ Terjadi error saat membuat role.\n\n"
                    f"```{e}```"
                ),
                view=None
            )

            return

        # ==================================================
        # ASSIGN ROLE
        # ==================================================

        success_members = []

        failed_members = []

        for member in self.selected_members:

            try:

                # Jangan berikan kepada bot
                if member.bot:

                    failed_members.append(
                        f"{member.mention} (bot)"
                    )

                    continue

                # Pastikan role dapat diberikan
                if not new_role.is_assignable():

                    failed_members.append(
                        f"{member.mention} (role tidak assignable)"
                    )

                    continue

                await member.add_roles(
                    new_role,
                    reason=(
                        f"Custom role assignment oleh "
                        f"{interaction.user}"
                    )
                )

                success_members.append(
                    member.mention
                )

            except discord.Forbidden:

                failed_members.append(
                    f"{member.mention} (Forbidden)"
                )

            except Exception as e:

                failed_members.append(
                    f"{member.mention} ({e})"
                )

        # ==================================================
        # RESULT
        # ==================================================

        result = (
            "## ✅ Custom Role Berhasil Dibuat!\n\n"
            f"**Role:** {new_role.mention}\n"
            f"**Style:** `{self.selected_style.title()}`\n"
            f"**Warna utama:** `{self.primary_color}`\n"
        )

        if self.secondary_color:

            result += (
                f"**Warna kedua:** "
                f"`{self.secondary_color}`\n"
            )

        result += "\n### 👥 Berhasil diberikan kepada:\n"

        if success_members:

            result += "\n".join(
                f"• {member}"
                for member in success_members
            )

        else:

            result += "Tidak ada."

        if failed_members:

            result += (
                "\n\n### ⚠️ Gagal diberikan kepada:\n"
                + "\n".join(
                    f"• {member}"
                    for member in failed_members
                )
            )

        await interaction.edit_original_response(
            content=result,
            view=None
        )


# ==========================================================
# PERSISTENT PANEL VIEW
# ==========================================================

class RoleRequestView(
    discord.ui.View
):

    def __init__(self):

        # WAJIB None untuk persistent view
        super().__init__(
            timeout=None
        )

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

        # ==================================================
        # CHANNEL
        # ==================================================

        if interaction.channel_id != TARGET_CHANNEL_ID:

            await interaction.response.send_message(
                f"❌ Gunakan tombol ini di "
                f"<#{TARGET_CHANNEL_ID}>.",
                ephemeral=True
            )

            return

        # ==================================================
        # ADMIN
        # ==================================================

        if not interaction.user.guild_permissions.administrator:

            await interaction.response.send_message(
                "❌ Hanya **Administrator** yang dapat "
                "menggunakan sistem Custom Role.",
                ephemeral=True
            )

            return

        await interaction.response.send_modal(
            RoleRequestModal()
        )


# ==========================================================
# COG
# ==========================================================

class RoleRequestCog(
    commands.Cog
):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

        # Session HTTP untuk download icon
        # Dibuat setelah bot siap
        if not hasattr(bot, "http_session"):

            import aiohttp

            bot.http_session = aiohttp.ClientSession()

    # ======================================================
    # SETUP PANEL
    # ======================================================

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

        if ctx.channel.id != TARGET_CHANNEL_ID:

            await ctx.reply(
                f"❌ Command hanya bisa digunakan di "
                f"<#{TARGET_CHANNEL_ID}>.",
                mention_author=False
            )

            return

        # ==================================================
        # EMBED
        # ==================================================

        embed = discord.Embed(
            title="🎨 Custom Role System",
            description=(
                "Buat custom role dengan tampilan sendiri!\n\n"

                "### ✨ Fitur\n"
                "• 🎨 Solid Color\n"
                "• 🌈 Gradient\n"
                "• ✨ Holographic\n"
                "• 🖼️ Role Icon\n"
                "• 👥 Pilih member penerima\n"
                "• 👥 Bisa diberikan ke hingga 25 member\n\n"

                "Klik tombol di bawah untuk memulai.\n\n"

                "⚠️ Hanya Administrator yang dapat "
                "menggunakan sistem ini."
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="nanZ Server • Custom Role System"
        )

        await ctx.send(
            embed=embed,
            view=RoleRequestView()
        )

        try:

            await ctx.message.delete()

        except discord.Forbidden:

            pass

    # ======================================================
    # ERROR
    # ======================================================

    @setup_role_panel.error
    async def setup_role_panel_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.reply(
                "❌ Hanya Administrator yang dapat "
                "menggunakan command ini.",
                mention_author=False,
                delete_after=5
            )

        else:

            await ctx.reply(
                f"❌ Error:\n```{error}```",
                mention_author=False
            )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        RoleRequestCog(bot)
    )