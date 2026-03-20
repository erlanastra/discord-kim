import discord
from discord.ext import commands

# ✅ GANTI DENGAN ID ROLE KAMU
ALLOWED_ROLE_IDS = [
    1453103644244316343,  # 🛡️ Mod DC
    1408509547601203252,  # 🎖️ Mod YT
    1467360501745844446,  # 🧭 Pembina OSIS
    1427276194876751902,   # 📝 OSIS
]

class BotSay(commands.Cog):
    """Bot pengirim pesan atas nama server (tanpa judul & footer)"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="nsays")
    async def nsays(self, ctx, channel: discord.TextChannel, *, pesan: str):

        # 🔒 Cek apakah user punya salah satu role ID
        user_role_ids = [role.id for role in ctx.author.roles]

        if not any(role_id in user_role_ids for role_id in ALLOWED_ROLE_IDS):
            await ctx.send("❌ Kamu tidak punya izin untuk menggunakan command ini.")
            return

        embed = discord.Embed(
            description=pesan,
            color=discord.Color.random()
        )

        embed.set_author(
            name="nanZ Server",
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )

        await channel.send(embed=embed)

        # hapus pesan command
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

async def setup(bot):
    await bot.add_cog(BotSay(bot))