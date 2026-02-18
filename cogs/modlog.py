import discord
from discord.ext import commands
import json

class ModLog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = json.load(open("config.json"))

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        ch = self.bot.get_channel(self.config["modlog_channel"])
        await ch.send(f"⛔ {user} banned")

async def setup(bot):
    await bot.add_cog(ModLog(bot))
