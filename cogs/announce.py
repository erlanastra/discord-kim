import discord
from discord.ext import commands

# ✅ GANTI DENGAN ID ROLE KAMU
ALLOWED_ROLE_IDS = [
    1453103644244316343,  # Mod DC
    1408509547601203252,  # Mod YT
    1467360501745844446,  # Pembina OSIS
    1427276194876751902   # OSIS
]

class Announcement(commands.Cog):
    """Command Announcement dengan embed warna-warni & judul menarik"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def announce(self, ctx, *, pesan):
        """Kirim announcement dengan embed menarik"""

        # 🔒 Cek role berdasarkan ID
        user_role_ids = [role.id for role in ctx.author.roles]

        if not any(role_id in user_role_ids for role_id in ALLOWED_ROLE_IDS):
            await ctx.send("❌ Kamu tidak punya izin untuk menggunakan command ini.")
            return

        embed = discord.Embed(
            title="📢 **PENGUMUMAN PENTING!**",
            description=pesan,
            color=discord.Color.gold()
        )

        embed.set_footer(
            text=f"Dikirim oleh {ctx.author.display_name}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else None
        )

        await ctx.send(embed=embed)

        # hapus pesan command
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

# Setup cog versi discord.py v2+
async def setup(bot):
    await bot.add_cog(Announcement(bot))