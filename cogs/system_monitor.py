import asyncio
import logging
import traceback
from datetime import datetime, timezone

import discord
from discord.ext import commands

MONITOR_CHANNEL_ID = 1555244706135285875


class DiscordErrorLogHandler(logging.Handler):
    """Menangkap error yang dicatat discord.py/asyncio, termasuk View callback."""

    def __init__(self, monitor):
        super().__init__(level=logging.ERROR)
        self.monitor = monitor

    def emit(self, record):
        try:
            # Abaikan error dari pengiriman log agar tidak terjadi loop.
            if record.name.startswith("nanz.system_monitor"):
                return
            message = self.format(record)
            exc_text = ""
            if record.exc_info:
                exc_text = "\n```py\n" + "".join(
                    traceback.format_exception(*record.exc_info)
                )[-2500:] + "\n```"
            text = (message + exc_text)[:3500]
            loop = self.monitor.bot.loop
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.monitor.log("Runtime / Interaction Error", text, "ERROR", record.name),
                    loop
                )
        except Exception:
            self.handleError(record)


class SystemMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("nanz.system_monitor")
        self.error_handler = DiscordErrorLogHandler(self)
        self.error_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        self._last_ready_session = None

    async def cog_load(self):
        # Tangkap error yang dicatat oleh discord.py dan asyncio.
        logging.getLogger("discord").addHandler(self.error_handler)
        logging.getLogger("asyncio").addHandler(self.error_handler)

    def cog_unload(self):
        logging.getLogger("discord").removeHandler(self.error_handler)
        logging.getLogger("asyncio").removeHandler(self.error_handler)

    async def log(self, title, description, level="INFO", feature="System"):
        channel = self.bot.get_channel(MONITOR_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(MONITOR_CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                self.logger.error("Tidak bisa mengakses channel monitor: %s", exc)
                return

        colors = {
            "INFO": discord.Color.blurple(),
            "SUCCESS": discord.Color.green(),
            "WARNING": discord.Color.orange(),
            "ERROR": discord.Color.red(),
        }
        embed = discord.Embed(
            title=title[:256],
            description=(description or "Tidak ada detail.")[:4000],
            color=colors.get(level, discord.Color.blurple()),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Kategori", value=str(feature)[:1024], inline=True)
        embed.add_field(name="Level", value=level, inline=True)
        embed.set_footer(text="NANZ System Monitor")
        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException) as exc:
            # Tidak melempar kembali supaya kegagalan monitor tidak mengganggu fitur.
            self.logger.error("Gagal mengirim log monitor: %s", exc)

    @commands.Cog.listener()
    async def on_ready(self):
        session = getattr(self.bot, "user", None)
        session_id = getattr(session, "id", None)
        if self._last_ready_session == session_id:
            return
        self._last_ready_session = session_id
        await self.log(
            "Bot Online",
            f"**Bot:** {self.bot.user}\n**Guild terjangkau:** {len(self.bot.guilds)}",
            "SUCCESS",
            "Startup",
        )

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        await self.log(
            "Command Berhasil",
            f"**Command:** `!{ctx.command.qualified_name}`\n"
            f"**Pengguna:** {ctx.author} (`{ctx.author.id}`)\n"
            f"**Server:** {ctx.guild.name if ctx.guild else 'DM'}\n"
            f"**Channel:** {getattr(ctx.channel, 'mention', 'DM')}",
            "SUCCESS",
            "Command",
        )

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if ctx.command and (
            ctx.command.has_error_handler()
            or (ctx.cog and ctx.cog.has_error_handler())
        ):
            return

        original = getattr(error, "original", error)
        await self.log(
            "Command Error",
            f"**Command:** `!{ctx.command.qualified_name if ctx.command else 'Unknown'}`\n"
            f"**Pengguna:** {ctx.author} (`{ctx.author.id}`)\n"
            f"**Server:** {ctx.guild.name if ctx.guild else 'DM'}\n"
            f"**Channel:** {getattr(ctx.channel, 'mention', 'DM')}\n"
            f"**Error:**\n```py\n{str(original)[:1800]}\n```",
            "ERROR",
            "Command",
        )

        if isinstance(original, commands.MissingPermissions):
            response = "Kamu tidak memiliki izin untuk menggunakan command ini."
        elif isinstance(original, commands.BotMissingPermissions):
            response = "Bot tidak memiliki izin yang diperlukan."
        elif isinstance(original, commands.MissingRequiredArgument):
            response = "Ada argumen command yang belum diisi."
        elif isinstance(original, commands.CommandOnCooldown):
            response = f"Command sedang cooldown. Coba lagi dalam {original.retry_after:.1f} detik."
        else:
            response = "Terjadi kesalahan saat menjalankan command."
        try:
            await ctx.send(response, delete_after=10)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_socket_event_type(self, event_type):
        # Dipakai sebagai sinyal aktivitas koneksi; bukan log setiap paket.
        if event_type in ("RESUMED", "READY"):
            await self.log("Gateway Event", f"Discord gateway: `{event_type}`", "INFO", "Connection")

    @commands.command(name="monitor_test")
    @commands.is_owner()
    async def monitor_test(self, ctx):
        await self.log(
            "Monitor Test",
            f"Tes monitor dijalankan oleh {ctx.author} (`{ctx.author.id}`).",
            "SUCCESS",
            "Testing",
        )
        await ctx.reply("✅ System Monitor berhasil diuji.", mention_author=False)


async def setup(bot):
    await bot.add_cog(SystemMonitor(bot))
