import discord
from discord.ext import commands
from discord import app_commands

# ================= CONFIRM VIEW =================
class WarnConfirmView(discord.ui.View):
    def __init__(self, member, pesan, target_channel):
        super().__init__(timeout=60)
        self.member = member
        self.pesan = pesan
        self.target_channel = target_channel

    @discord.ui.button(label="✅ Kirim Warning", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Kamu tidak punya izin.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="⚠️ PERINGATAN RESMI SERVER",
            description=self.pesan,
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(
            name="👤 Ditujukan kepada",
            value=self.member.mention,
            inline=False
        )
        embed.set_footer(text="Pesan ini dikirim oleh sistem server")
        embed.set_thumbnail(url=self.member.display_avatar.url)

        # DM MEMBER
        if self.target_channel == "dm":
            try:
                await self.member.send(embed=embed)
                result = "📩 Warning dikirim ke DM member"
            except:
                result = "❌ DM member tertutup"
        else:
            await self.target_channel.send(
                content=self.member.mention,
                embed=embed
            )
            result = f"📢 Warning dikirim ke {self.target_channel.mention}"

        await interaction.response.edit_message(
            content=f"✅ **Warning berhasil dikirim**\n{result}",
            embed=None,
            view=None
        )
        self.stop()

    @discord.ui.button(label="❌ Batalkan", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ Pengiriman warning dibatalkan.",
            embed=None,
            view=None
        )
        self.stop()

# ================= COG =================
class Warn(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="warn",
        description="⚠️ Kirim peringatan resmi ke member"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def warn(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        pesan: str,
        channel: discord.TextChannel | None = None
    ):
        target = channel if channel else "dm"

        preview = discord.Embed(
            title="🛑 PREVIEW PERINGATAN",
            description=pesan,
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        preview.add_field(
            name="👤 Target Member",
            value=member.mention,
            inline=True
        )
        preview.add_field(
            name="📨 Tujuan Pengiriman",
            value="DM Member" if target == "dm" else channel.mention,
            inline=True
        )
        preview.set_footer(text="Klik tombol di bawah untuk mengonfirmasi")
        preview.set_thumbnail(url=member.display_avatar.url)

        view = WarnConfirmView(member, pesan, target)

        await interaction.response.send_message(
            embed=preview,
            view=view,
            ephemeral=True
        )

# ================= SETUP =================
async def setup(bot):
    await bot.add_cog(Warn(bot))
