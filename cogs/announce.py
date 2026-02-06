import discord
from discord.ext import commands

class Announcement(commands.Cog):
    """Command Announcement dengan embed warna-warni & judul menarik"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def announce(self, ctx, *, pesan):
        """Kirim announcement dengan embed menarik"""
        embed = discord.Embed(
            title="📢 **PENGUMUMAN PENTING!**",
            description=pesan,
            color=discord.Color.gold()  # Warna kuning emas
        )
        embed.set_footer(text=f"Dikirim oleh {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)

        # Hapus pesan command user
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass  # Kalau bot gak bisa hapus, skip aja

# Setup cog versi discord.py v2+
async def setup(bot):
    await bot.add_cog(Announcement(bot))
