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
    async def moddc(self, ctx, target: discord.Member = None):

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
                "❌ Role **Mod DC lama** dan **Mod DC baru** "
                "tidak boleh sama."
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
                "❌ Bot tidak dapat mencabut role **Mod DC lama** "
                "karena role tersebut berada di atas atau sejajar "
                "dengan role tertinggi bot."
            )

        if new_role >= bot_member.top_role:
            return await ctx.send(
                "❌ Bot tidak dapat memberikan role **Mod DC baru** "
                "karena role tersebut berada di atas atau sejajar "
                "dengan role tertinggi bot."
            )

        # ====================================================
        # CEK TARGET ADALAH BOT
        # ====================================================

        if target.bot:
            return await ctx.send(
                "❌ Role **Mod DC** tidak dapat diberikan kepada bot."
            )

        # ====================================================
        # CEK TARGET SUDAH MEMILIKI ROLE BARU
        # ====================================================

        if new_role in target.roles:

            # Jika target masih punya role lama juga,
            # bot hanya mencabut role lama.
            if old_role in target.roles:

                try:
                    await target.remove_roles(
                        old_role,
                        reason=f"Mod DC Role Manager oleh {ctx.author}"
                    )

                except discord.Forbidden:
                    return await ctx.send(
                        "❌ Bot tidak memiliki izin untuk "
                        "mencabut **Mod DC lama** dari target."
                    )

                except discord.HTTPException:
                    return await ctx.send(
                        "❌ Terjadi kesalahan Discord saat "
                        "mencabut **Mod DC lama**."
                    )

                return await ctx.send(
                    f"✅ **{target.display_name}** sudah memiliki "
                    f"{new_role.mention}.\n"
                    f"Role lama {old_role.mention} berhasil dicabut."
                )

            return await ctx.send(
                f"ℹ️ **{target.display_name}** sudah memiliki "
                f"{new_role.mention}."
            )

        # ====================================================
        # CEK TARGET TIDAK PUNYA ROLE LAMA
        # ====================================================

        has_old_role = old_role in target.roles

        # ====================================================
        # CONFIRMATION
        # ====================================================

        embed = discord.Embed(
            title="🛡️ MOD DC ROLE MANAGER",
            description=(
                "Administrator akan melakukan perubahan "
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
            name="Role Lama",
            value=(
                f"{old_role.mention}"
                if has_old_role
                else "Tidak dimiliki"
            ),
            inline=True
        )

        embed.add_field(
            name="Role Baru",
            value=new_role.mention,
            inline=True
        )

        embed.add_field(
            name="Tindakan",
            value=(
                "1. Memberikan **Mod DC baru**\n"
                "2. Setelah berhasil, mencabut **Mod DC lama**"
            ),
            inline=False
        )

        embed.set_footer(
            text="Mod DC Role Manager • nanZ Server"
        )

        view = ModDCConfirmView(
            author_id=ctx.author.id,
            target=target,
            old_role=old_role,
            new_role=new_role,
            has_old_role=has_old_role
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


# ============================================================
# CONFIRMATION VIEW
# ============================================================

class ModDCConfirmView(discord.ui.View):

    def __init__(
        self,
        author_id,
        target,
        old_role,
        new_role,
        has_old_role
    ):

        super().__init__(timeout=60)

        self.author_id = author_id
        self.target = target
        self.old_role = old_role
        self.new_role = new_role
        self.has_old_role = has_old_role

    # ========================================================
    # INTERACTION CHECK
    # ========================================================

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ):

        # Hanya executor command
        if interaction.user.id != self.author_id:

            await interaction.response.send_message(
                "❌ Hanya Administrator yang menjalankan "
                "command ini yang dapat menggunakan tombol.",
                ephemeral=True
            )

            return False

        # Tetap cek Administrator
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
        bot_member = guild.me

        # ====================================================
        # CEK ULANG HIERARKI
        # ====================================================

        if self.new_role >= bot_member.top_role:

            return await interaction.edit_original_response(
                content=(
                    "❌ Migrasi dibatalkan.\n\n"
                    "Bot tidak dapat memberikan "
                    f"{self.new_role.mention} karena hierarki role."
                ),
                embed=None,
                view=None
            )

        if self.has_old_role and self.old_role >= bot_member.top_role:

            return await interaction.edit_original_response(
                content=(
                    "❌ Migrasi dibatalkan.\n\n"
                    "Bot tidak dapat mencabut "
                    f"{self.old_role.mention} karena hierarki role."
                ),
                embed=None,
                view=None
            )

        # ====================================================
        # BERIKAN ROLE BARU TERLEBIH DAHULU
        # ====================================================

        try:

            await self.target.add_roles(
                self.new_role,
                reason=(
                    f"Mod DC Role Manager | "
                    f"Executor: {interaction.user}"
                )
            )

        except discord.Forbidden:

            return await interaction.edit_original_response(
                content=(
                    "❌ **Gagal memberikan role baru.**\n\n"
                    f"Target: {self.target.mention}\n"
                    f"Role: {self.new_role.mention}\n\n"
                    "Role lama **tidak dicabut**."
                ),
                embed=None,
                view=None
            )

        except discord.HTTPException:

            return await interaction.edit_original_response(
                content=(
                    "❌ Terjadi kesalahan Discord saat "
                    "memberikan role baru.\n\n"
                    "Role lama **tidak dicabut**."
                ),
                embed=None,
                view=None
            )

        # ====================================================
        # CABUT ROLE LAMA
        # ====================================================

        if self.has_old_role:

            try:

                await self.target.remove_roles(
                    self.old_role,
                    reason=(
                        f"Mod DC Role Manager | "
                        f"Executor: {interaction.user}"
                    )
                )

            except discord.Forbidden:

                # Role baru sudah berhasil diberikan.
                # Jangan mengembalikan role baru secara otomatis.
                return await interaction.edit_original_response(
                    content=(
                        "⚠️ **Role baru berhasil diberikan, "
                        "tetapi role lama gagal dicabut.**\n\n"
                        f"Target: {self.target.mention}\n"
                        f"Role Baru: {self.new_role.mention}\n"
                        f"Role Lama: {self.old_role.mention}\n\n"
                        "Silakan cabut role lama secara manual."
                    ),
                    embed=None,
                    view=None
                )

            except discord.HTTPException:

                return await interaction.edit_original_response(
                    content=(
                        "⚠️ **Role baru berhasil diberikan, "
                        "tetapi terjadi error saat mencabut "
                        "role lama.**\n\n"
                        f"Target: {self.target.mention}\n"
                        f"Role Lama: {self.old_role.mention}"
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
                f"Role **Mod DC** untuk {self.target.mention} "
                "berhasil diperbarui."
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="Target",
            value=self.target.mention,
            inline=False
        )

        embed.add_field(
            name="Role Lama",
            value=(
                f"❌ {self.old_role.mention}"
                if self.has_old_role
                else "Tidak ada"
            ),
            inline=True
        )

        embed.add_field(
            name="Role Baru",
            value=f"✅ {self.new_role.mention}",
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