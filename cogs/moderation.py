import discord
from discord.ext import commands

class Moderation(commands.Cog):
    """Cog untuk perintah moderasi"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason=None):
        """Kick member"""
        await member.kick(reason=reason)
        await ctx.send(f"✅ {member} telah di-kick. Alasan: {reason}")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason=None):
        """Ban member"""
        await member.ban(reason=reason)
        await ctx.send(f"⛔ {member} telah di-ban. Alasan: {reason}")

# Setup cog
async
