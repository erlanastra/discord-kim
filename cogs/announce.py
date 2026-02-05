from discord.ext import commands

class Announcement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def announce(self, ctx, *, pesan):
        await ctx.send(f"📢 **ANNOUNCEMENT:**\n{pesan}")

async def setup(bot):
    await bot.add_cog(Announcement(bot))
