import discord
from discord.ext import commands

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        await ctx.send("🏓 Pong!")

    @commands.command()
    async def serverinfo(self, ctx):
        guild = ctx.guild
        await ctx.send(
            f"🏠 **{guild.name}**\n"
            f"👥 Members: {guild.member_count}"
        )

# Setup harus async dan await add_cog
async def setup(bot):
    await bot.add_cog(Utility(bot))
