
import discord
from discord.ext import commands
from datetime import datetime, timezone

# ==========================================================
# CONFIG
# ==========================================================

MONITOR_CHANNEL_ID = 1555244706135285875


class SystemMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.started_at = datetime.now(timezone.utc)

    # ======================================================
    # EMBED LOGGER
    # ======================================================

    async def log(
        self,
        title: str,
        description: str,
        level: str = "INFO",
        feature: str = "System"
    ):
        channel = self.bot.get_channel(MONITOR_CHANNEL_ID)

        if channel is None:
            try:
                channel = await self.bot.fetch_channel(
                    MONITOR_CHANNEL_ID
                )
            except discord.HTTPException:
                print("[MONITOR] Channel log tidak ditemukan.")
                return

        colors = {
            "INFO": discord.Color.blurple(),
            "SUCCESS": discord.Color.green(),
            "WARNING": discord.Color.orange(),
            "ERROR": discord.Color.red()
        }

        emojis = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌"
        }

        embed = discord.Embed(
            title=f"{emojis.get(level, '📌')} {title}",
            description=description,
            color=colors.get(level, discord.Color.blurple()),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="Kategori",
            value=level,
            inline=True
        )

        embed.add_field(
            name="Fitur",
            value=feature,
            inline=True
        )

        embed.set_footer(
            text="NANZ System Monitor"
        )

        try:
            await channel.send(embed=embed)
        except discord.HTTPException as error:
            print(f"[MONITOR] Gagal mengirim log: {error}")

    # ======================================================
    # BOT EVENTS
    # ======================================================

    @commands.Cog.listener()
    async def on_ready(self):
        await self.log(
            title="Bot Online",
            description=(
                f"Bot **{self.bot.user}** berhasil terhubung "
                "ke Discord."
            ),
            level="SUCCESS",
            feature="Core System"
        )

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        await self.log(
            title="Command Berhasil",
            description=(
                f"**Command:** `{ctx.command.qualified_name}`\n"
                f"**Pengguna:** {ctx.author.mention}\n"
                f"**Channel:** {ctx.channel.mention}"
            ),
            level="SUCCESS",
            feature=ctx.command.cog_name or "Command"
        )

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, "on_error"):
            return

        original = getattr(error, "original", error)

        await self.log(
            title="Command Error",
            description=(
                f"**Command:** `{ctx.command}`\n"
                f"**Pengguna:** {ctx.author.mention}\n"
                f"**Channel:** {ctx.channel.mention}\n"
                f"**Error:**\n```"
                f"{str(original)[:1500]}```"
            ),
            level="ERROR",
            feature=(
                ctx.command.cog_name
                if ctx.command else "Unknown"
            )
        )

    # ======================================================
    # MONITOR COMMAND
    # ======================================================

    @commands.command(name="monitor_test")
    @commands.is_owner()
    async def monitor_test(self, ctx):
        await self.log(
            title="Pengujian Monitor",
            description=(
                f"Pengujian berhasil dilakukan oleh "
                f"{ctx.author.mention}."
            ),
            level="SUCCESS",
            feature="System Monitor"
        )

        await ctx.reply(
            "✅ Log pengujian berhasil dikirim.",
            mention_author=False
        )


async def setup(bot):
    await bot.add_cog(SystemMonitor(bot))