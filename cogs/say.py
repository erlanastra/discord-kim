import discord
from discord.ext import commands

class BotSay(commands.Cog):
    """Bot pengirim pesan atas nama server (tanpa judul & footer)"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="nsays")
    @commands.has_any_role(
        "🛡️| Mod DC",
        "🎖️ | Mod YT",
        "🧭 | Pembina OSIS",
        "📝| OSIS"
    )
    async def nsays(self, ctx, channel: discord.TextChannel, *, pesan: str):
        embed = discord.Embed(
            description=pesan,
            color=discord.Color.random()  # 🎨 random warna
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
