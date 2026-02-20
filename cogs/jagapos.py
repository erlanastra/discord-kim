import discord
from discord.ext import commands, tasks

class JagaPos(commands.Cog):
    """Bot stay di voice channel 24/7 walau kosong"""
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = None  # ID voice channel yang mau dijaga
        self.vc = None
        self.rejoin_task.start()

    # ================== COMMAND !join ==================
    @commands.command()
    async def join(self, ctx):
        """Bot join VC tempat kamu berada sebagai penjaga pos"""
        if not ctx.author.voice:
            return await ctx.send("❌ Kamu harus ada di voice channel dulu.")

        channel = ctx.author.voice.channel
        self.channel_id = channel.id

        if ctx.voice_client:
            await ctx.send("⚠️ Bot sudah di voice channel.")
            return

        self.vc = await channel.connect(self_mute=True, self_deaf=True)
        await ctx.send(f"🛡️ Bot sekarang jaga pos di **{channel.name}**")

    # ================== COMMAND !leave ==================
    @commands.command()
    async def leave(self, ctx):
        """Bot keluar dari voice channel"""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            self.vc = None
            self.channel_id = None
            await ctx.send("👋 Bot keluar dari voice.")
        else:
            await ctx.send("❌ Bot tidak ada di voice channel.")

    # ================== AUTO REJOIN TASK ==================
    @tasks.loop(seconds=10)
    async def rejoin_task(self):
        """Cek setiap 10 detik, kalau bot keluar dari VC, join lagi"""
        if not self.channel_id:
            return

        guild = self.bot.get_guild(self.bot.guilds[0].id)  # asumsi 1 server
        channel = guild.get_channel(self.channel_id)
        if not channel:
            return  # VC dihapus atau tidak ditemukan

        vc = guild.voice_client
        if not vc or vc.channel.id != self.channel_id:
            try:
                self.vc = await channel.connect(self_mute=True, self_deaf=True)
                print(f"[JagaPos] Rejoined {channel.name}")
            except Exception as e:
                print(f"[JagaPos] Gagal join VC: {e}")

    @rejoin_task.before_loop
    async def before_rejoin(self):
        await self.bot.wait_until_ready()

# ================== SETUP ==================
async def setup(bot):
    await bot.add_cog(JagaPos(bot))