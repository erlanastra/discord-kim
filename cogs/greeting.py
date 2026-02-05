from discord.ext import commands, tasks
import datetime
import discord

class Greeting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.greet.start()

    def cog_unload(self):
        self.greet.cancel()

    @tasks.loop(minutes=1)
    async def greet(self):
        # Pastikan bot sudah siap
        if not self.bot.is_ready():
            return

        now = datetime.datetime.now().hour

        for guild in self.bot.guilds:
            channel = discord.utils.get(
                guild.text_channels,
                name="general"  # ganti kalau nama channel beda
            )

            if not channel:
                continue

            if now == 6:
                await channel.send("🌅 Selamat pagi semuanya!")
            elif now == 12:
                await channel.send("🌞 Selamat siang semuanya!")
            elif now == 18:
                await channel.send("🌇 Selamat sore semuanya!")
            elif now == 21:
                await channel.send("🌙 Selamat malam, waktunya istirahat 😴")

async def setup(bot):
    await bot.add_cog(Greeting(bot))
