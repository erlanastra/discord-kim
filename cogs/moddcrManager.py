import discord
from discord.ext import commands


# ============================================================
# CONFIG
# ============================================================

# ID ROLE MOD DC LAMA
OLD_MOD_DC_ROLE_ID = 1453103644244316343

# ID ROLE MOD DC BARU
NEW_MOD_DC_ROLE_ID = 1555556260269527151


# ============================================================
# MOD DC ROLE MANAGER
# ============================================================

class ModDCRoleManager(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # ========================================================
    # COMMAND
    # !moddc @user
    # ========================================================

    @commands.command(name="moddc")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def moddc(
        self,
        ctx,
        target: discord.Member = None
    ):

        guild = ctx.guild

        # ====================================================
        # CEK TARGET
        # ====================================================

        if target is None:
            return await ctx.send(
                "❌ Gunakan command:\n"
                "`!moddc @target`"
            )

        # ====================================================
        # CEK TARGET BOT
        # ====================================================

        if target.bot:
            return await ctx.send(
                "❌ Role **Mod DC** tidak dapat diberikan "
                "kepada bot."
            )

        # ====================================================
        # AMBIL ROLE
        # ====================================================

        old_role = guild.get_role(OLD_MOD_DC_ROLE_ID)
        new_role = guild.get_role(NEW_MOD_DC_ROLE_ID)

        if old_role is None:
            return await ctx.send(
                "❌ Role **Mod DC lama** tidak ditemukan."
            )

        if new_role is None:
            return await ctx.send(
                "❌ Role **Mod DC baru** tidak ditemukan."
            )

        # ====================================================
        # CEK ROLE SAMA
        # ====================================================

        if old_role.id == new_role.id:
            return await ctx.send(
                "❌ Role **Mod DC lama** dan "
                "**Mod DC baru** tidak boleh sama."
            )

        # ====================================================
        # CEK BOT
        # ====================================================

        bot_member = guild.me

        if bot_member is None:
            return await ctx.send(
                "❌ Data bot tidak ditemukan."
            )

        # ====================================================
        # CEK HIERARKI ROLE
        # ====================================================

        if old_role >= bot_member.top_role:
            return await ctx.send(
                "❌ Bot tidak dapat mengelola "
                f"{old_role.mention} karena role tersebut "
                "berada di atas atau sejajar dengan "
                "role tertinggi bot."
            )

        if new_role >= bot_member.top_role:
            return await ctx.send(
                "❌ Bot tidak dapat mengelola "
                f"{new_role.mention} karena role tersebut "
                "berada di atas atau sejajar dengan "
                "role tertinggi bot."
            )

        # ====================================================
        # CEK ROLE TARGET
        # ====================================================

        has_old_role = old_role in target.roles
        has_new_role = new_role in target.roles

        # ====================================================
        # TIDAK MEMILIKI ROLE APAPUN
        # ====================================================

        if not has_old_role and not has_new_role:
            return await ctx.send(
                f"❌ **{target.display_name}** tidak memiliki "
                "**Mod DC Lama** maupun **Mod DC Baru**.\n\n"
                "Tidak ada role yang dapat ditransfer."
            )

        # ====================================================
        # MEMILIKI KEDUA ROLE
        # ====================================================

        if has_old_role and has_new_role:
            return await ctx.send(
                f"⚠️ **{target.display_name}** sudah memiliki "
                "**Mod DC Lama** dan **Mod DC Baru**.\n\n"
                "Target harus hanya memiliki salah satu "
                "role sebelum melakukan transfer."
            )

        # ====================================================
        # TENTUKAN ARAH TRANSFER
        # ====================================================

        if has_old_role:

            source_role = old_role
            destination_role = new_role

        else:

            source_role = new_role
            destination_role = old_role

        # ====================================================
        # CONFIRMATION EMBED
        # ====================================================

        embed = discord.Embed(
            title="🛡️ MOD DC ROLE MANAGER",
            description=(
                "Administrator akan melakukan transfer "
                "role **Mod DC** pada target berikut."
            ),
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="Target",
            value=target.mention,
            inline=False
        )

        embed.add_field(
            name="Role Saat Ini",
            value=source_role.mention,
            inline=True
        )

        embed.add_field(
            name="Role Tujuan",
            value=destination_role.mention,
            inline=True
        )

        embed.add_field(
            name="Tindakan",
            value=(
                f"1. Memberikan {destination_role.mention}\n"
                f"2. Setelah berhasil, mencabut "
                f"{source_role.mention}"
            ),
            inline=False
        )

        embed.set_footer(
            text="Mod DC Role Manager • nanZ Server"
        )

        view = ModDCConfirmView(
            author_id=ctx.author.id,
            target=target,
            source_role=source_role,
            destination_role=destination_role
        )

        await ctx.send(
            embed=embed,
            view=view
        )

    # ========================================================
    # ERROR HANDLER
    # ========================================================

    @moddc.error
    async def moddc_error(self, ctx, error):

        if isinstance(error, commands.MissingPermissions):
            return await ctx.send(
                "❌ Fitur ini hanya dapat digunakan oleh "
                "**Administrator**."
            )

        if isinstance(error, commands.MemberNotFound):
            return await ctx.send(
                "❌ Target member tidak ditemukan.\n"
                "Gunakan: `!moddc @target`"
            )

        if isinstance(error, commands.BadArgument):
            return await ctx.send(
                "❌ Target member tidak valid.\n"
                "Gunakan: `!moddc @target`"
            )


# ============================================================
# CONFIRMATION VIEW
# ============================================================

class ModDCConfirmView(discord.ui.View):

    def __init__(
        self,
        author_id,
        target,
        source_role,
        destination_role
    ):

        super().__init__(timeout=60)

        self.author_id = author_id
        self.target = target
        self.source_role = source_role
        self.destination_role = destination_role

    # ========================================================
    # INTERACTION CHECK
    # ========================================================

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ):

        # ----------------------------------------------------
        # HANYA ADMIN YANG MENJALANKAN COMMAND
        # ----------------------------------------------------

        if interaction.user.id != self.author_id:

            await interaction.response.send_message(
                "❌ Hanya Administrator yang menjalankan "
                "command ini yang dapat menggunakan tombol.",
                ephemeral=True
            )

            return False

        # ----------------------------------------------------
        # CEK ADMINISTRATOR
        # ----------------------------------------------------

        if not interaction.user.guild_permissions.administrator:

            await interaction.response.send_message(
                "❌ Kamu tidak memiliki permission "
                "**Administrator**.",
                ephemeral=True
            )

            return False

        return True

    # ========================================================
    # CONFIRM
    # ========================================================

    @discord.ui.button(
        label="Lanjutkan",
        style=discord.ButtonStyle.green,
        emoji="✅"
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.defer()

        guild = interaction.guild

        if guild is None:
            return await interaction.edit_original_response(
                content="❌ Server tidak ditemukan.",
                embed=None,
                view=None
            )

        bot_member = guild.me

        if bot_member is None:
            return await interaction.edit_original_response(
                content="❌ Data bot tidak ditemukan.",
                embed=None,
                view=None
            )

        # ====================================================
        # CEK TARGET TERKINI
        # ====================================================

        target = guild.get_member(self.target.id)

        if target is None:
            try:
                target = await guild.fetch_member(
                    self.target.id
                )
            except discord.NotFound:
                return await interaction.edit_original_response(
                    content=(
                        "❌ **Transfer dibatalkan.**\n\n"
                        "Target member tidak ditemukan."
                    ),
                    embed=None,
                    view=None
                )
            except discord.HTTPException:
                return await interaction.edit_original_response(
                    content=(
                        "❌ **Transfer dibatalkan.**\n\n"
                        "Gagal mengambil data target dari Discord."
                    ),
                    embed=None,
                    view=None
                )

        # ====================================================
        # CEK TARGET BOT
        # ====================================================

        if target.bot:
            return await interaction.edit_original_response(
                content=(
                    "❌ **Transfer dibatalkan.**\n\n"
                    "Role **Mod DC** tidak dapat diberikan "
                    "kepada bot."
                ),
                embed=None,
                view=None
            )

        # ====================================================
        # CEK HIERARKI ROLE ULANG
        # ====================================================

        if self.destination_role >= bot_member.top_role:
            return await interaction.edit_original_response(
                content=(
                    "❌ **Transfer dibatalkan.**\n\n"
                    f"Bot tidak dapat memberikan "
                    f"{self.destination_role.mention} "
                    "karena hierarki role."
                ),
                embed=None,
                view=None
            )

        if self.source_role >= bot_member.top_role:
            return await interaction.edit_original_response(
                content=(
                    "❌ **Transfer dibatalkan.**\n\n"
                    f"Bot tidak dapat mencabut "
                    f"{self.source_role.mention} "
                    "karena hierarki role."
                ),
                embed=None,
                view=None
            )

        # ====================================================
        # CEK KONDISI ROLE TERKINI
        # ====================================================

        has_source_role = (
            self.source_role in target.roles
        )

        has_destination_role = (
            self.destination_role in target.roles
        )

        # ====================================================
        # ROLE TUJUAN SUDAH ADA
        # ====================================================

        if has_destination_role:
            return await interaction.edit_original_response(
                content=(
                    "ℹ️ **Transfer dibatalkan.**\n\n"
                    f"{target.mention} sudah memiliki "
                    f"{self.destination_role.mention}."
                ),
                embed=None,
                view=None
            )

        # ====================================================
        # ROLE SUMBER SUDAH HILANG
        # ====================================================

        if not has_source_role:
            return await interaction.edit_original_response(
                content=(
                    "❌ **Transfer dibatalkan.**\n\n"
                    f"{target.mention} sudah tidak memiliki "
                    f"{self.source_role.mention}.\n\n"
                    "Kondisi role target mungkin telah berubah "
                    "sejak command dijalankan."
                ),
                embed=None,
                view=None
            )

        # ====================================================
        # BERIKAN ROLE TUJUAN
        # ====================================================

        try:

            await target.add_roles(
                self.destination_role,
                reason=(
                    f"Mod DC Role Manager | "
                    f"Transfer {self.source_role.name} -> "
                    f"{self.destination_role.name} | "
                    f"Executor: {interaction.user}"
                )
            )

        except discord.Forbidden:

            return await interaction.edit_original_response(
                content=(
                    "❌ **Gagal memberikan role tujuan.**\n\n"
                    f"Target: {target.mention}\n"
                    f"Role Tujuan: "
                    f"{self.destination_role.mention}\n\n"
                    f"{self.source_role.mention} "
                    "**tidak dicabut**."
                ),
                embed=None,
                view=None
            )

        except discord.HTTPException:

            return await interaction.edit_original_response(
                content=(
                    "❌ Terjadi kesalahan Discord saat "
                    "memberikan role tujuan.\n\n"
                    f"{self.source_role.mention} "
                    "**tidak dicabut**."
                ),
                embed=None,
                view=None
            )

        # ====================================================
        # CABUT ROLE SUMBER
        # ====================================================

        try:

            await target.remove_roles(
                self.source_role,
                reason=(
                    f"Mod DC Role Manager | "
                    f"Transfer {self.source_role.name} -> "
                    f"{self.destination_role.name} | "
                    f"Executor: {interaction.user}"
                )
            )

        except discord.Forbidden:

            return await interaction.edit_original_response(
                content=(
                    "⚠️ **Role tujuan berhasil diberikan, "
                    "tetapi role sumber gagal dicabut.**\n\n"
                    f"Target: {target.mention}\n"
                    f"Role Tujuan: "
                    f"{self.destination_role.mention}\n"
                    f"Role Sumber: "
                    f"{self.source_role.mention}\n\n"
                    "Silakan cabut role sumber secara manual."
                ),
                embed=None,
                view=None
            )

        except discord.HTTPException:

            return await interaction.edit_original_response(
                content=(
                    "⚠️ **Role tujuan berhasil diberikan, "
                    "tetapi terjadi error saat mencabut "
                    "role sumber.**\n\n"
                    f"Target: {target.mention}\n"
                    f"Role Sumber: "
                    f"{self.source_role.mention}"
                ),
                embed=None,
                view=None
            )

        # ====================================================
        # SUCCESS
        # ====================================================

        embed = discord.Embed(
            title="✅ Mod DC Berhasil Diperbarui",
            description=(
                f"Role **Mod DC** untuk {target.mention} "
                "berhasil ditransfer."
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="Target",
            value=target.mention,
            inline=False
        )

        embed.add_field(
            name="Role Sebelumnya",
            value=f"❌ {self.source_role.mention}",
            inline=True
        )

        embed.add_field(
            name="Role Sekarang",
            value=f"✅ {self.destination_role.mention}",
            inline=True
        )

        embed.add_field(
            name="Administrator",
            value=interaction.user.mention,
            inline=False
        )

        embed.set_footer(
            text="Mod DC Role Manager • nanZ Server"
        )

        await interaction.edit_original_response(
            content=None,
            embed=embed,
            view=None
        )

        self.stop()

    # ========================================================
    # CANCEL
    # ========================================================

    @discord.ui.button(
        label="Batal",
        style=discord.ButtonStyle.red,
        emoji="✖️"
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.edit_message(
            content=(
                "❌ Perubahan **Mod DC dibatalkan**.\n\n"
                "Tidak ada role yang diubah."
            ),
            embed=None,
            view=None
        )

        self.stop()

    # ========================================================
    # TIMEOUT
    # ========================================================

    async def on_timeout(self):

        for item in self.children:
            item.disabled = True


# ============================================================
# SETUP
# ============================================================

async def setup(bot):
    await bot.add_cog(ModDCRoleManager(bot))