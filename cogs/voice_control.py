import discord
from discord.ext import commands


class VoiceControl(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # Role yang diperbolehkan menggunakan fitur
        self.VOICE_CONTROL_ROLE_ID = 1528766033509220572

    # ==========================================
    # CEK AKSES
    # ==========================================

    def has_voice_control_access(self, member: discord.Member):

        # Administrator selalu boleh
        if member.guild_permissions.administrator:
            return True

        # Cek role khusus
        return any(
            role.id == self.VOICE_CONTROL_ROLE_ID
            for role in member.roles
        )

    # ==========================================
    # TARIK USER
    # ==========================================

    @commands.command(
        name="tarik",
        aliases=["narik", "pull"]
    )
    async def tarik(
        self,
        ctx,
        member: discord.Member
    ):

        # ======================================
        # CEK AKSES
        # ======================================

        if not self.has_voice_control_access(
            ctx.author
        ):
            return await ctx.send(
                "❌ Kamu tidak memiliki izin "
                "untuk menggunakan command ini.",
                delete_after=5
            )

        # ======================================
        # CEK AUTHOR DI VOICE
        # ======================================

        if not ctx.author.voice:
            return await ctx.send(
                "❌ Kamu harus berada di voice channel "
                "terlebih dahulu.",
                delete_after=5
            )

        target_channel = ctx.author.voice.channel

        # ======================================
        # CEK TARGET
        # ======================================

        if not member.voice:
            return await ctx.send(
                f"❌ {member.mention} sedang tidak "
                f"berada di voice channel.",
                delete_after=5
            )

        # ======================================
        # SUDAH DI CHANNEL YANG SAMA
        # ======================================

        if member.voice.channel.id == target_channel.id:
            return await ctx.send(
                f"ℹ️ {member.mention} sudah berada "
                f"di **{target_channel.name}**.",
                delete_after=5
            )

        # ======================================
        # PINDAHKAN
        # ======================================

        try:

            await member.move_to(
                target_channel,
                reason=(
                    f"Voice pull oleh "
                    f"{ctx.author} ({ctx.author.id})"
                )
            )

            embed = discord.Embed(
                title="📥 Voice Pull",
                description=(
                    f"{member.mention} berhasil ditarik "
                    f"ke **{target_channel.name}**."
                ),
                color=discord.Color.green()
            )

            embed.set_footer(
                text=f"Ditarik oleh {ctx.author.display_name}"
            )

            await ctx.send(
                embed=embed,
                delete_after=7
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ Bot tidak memiliki permission "
                "**Move Members**.",
                delete_after=7
            )

        except discord.HTTPException as e:

            await ctx.send(
                f"❌ Gagal memindahkan member.\n"
                f"`{e}`",
                delete_after=7
            )

    # ==========================================
    # TURUNKAN / KELUARKAN USER DARI VOICE
    # ==========================================

    @commands.command(
        name="turunin",
        aliases=["turun", "down", "kickvoice"]
    )
    async def turunin(
        self,
        ctx,
        member: discord.Member
    ):

        # ======================================
        # CEK AKSES
        # ======================================

        if not self.has_voice_control_access(
            ctx.author
        ):
            return await ctx.send(
                "❌ Kamu tidak memiliki izin "
                "untuk menggunakan command ini.",
                delete_after=5
            )

        # ======================================
        # CEK TARGET DI VOICE
        # ======================================

        if not member.voice:
            return await ctx.send(
                f"❌ {member.mention} sedang tidak "
                f"berada di voice channel.",
                delete_after=5
            )

        voice_channel = member.voice.channel

        # ======================================
        # KELUARKAN DARI VOICE
        # ======================================

        try:

            await member.move_to(
                None,
                reason=(
                    f"Voice disconnect oleh "
                    f"{ctx.author} ({ctx.author.id})"
                )
            )

            embed = discord.Embed(
                title="📤 Voice Disconnect",
                description=(
                    f"{member.mention} berhasil "
                    f"diturunkan dari **{voice_channel.name}**."
                ),
                color=discord.Color.red()
            )

            embed.set_footer(
                text=f"Diturunkan oleh {ctx.author.display_name}"
            )

            await ctx.send(
                embed=embed,
                delete_after=7
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ Bot tidak memiliki permission "
                "**Move Members**.",
                delete_after=7
            )

        except discord.HTTPException as e:

            await ctx.send(
                f"❌ Gagal mengeluarkan member dari voice.\n"
                f"`{e}`",
                delete_after=7
            )


# ==============================================
# SETUP
# ==============================================

async def setup(bot):

    await bot.add_cog(
        VoiceControl(bot)
    )