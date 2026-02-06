import discord
from discord.ext import commands

class AFK(commands.Cog):
    """Command AFK dengan multi-server dan nickname otomatis"""

    def __init__(self, bot):
        self.bot = bot
        # Struktur: {guild_id: {user_id: {"nick": original_nick, "reason": str}}}
        self.afk_users = {}

    @commands.command(name="afk")
    async def set_afk(self, ctx, *, reason: str = "Sedang AFK"):
        """Set user AFK dengan nickname otomatis"""
        member = ctx.author
        guild_id = ctx.guild.id

        if guild_id not in self.afk_users:
            self.afk_users[guild_id] = {}

        if member.id in self.afk_users[guild_id]:
            await ctx.send(f"❌ {member.mention}, kamu sudah AFK!")
            return

        # Simpan nickname asli
        original_nick = member.display_name
        self.afk_users[guild_id][member.id] = {"nick": original_nick, "reason": reason}

        # Coba ganti nickname
        try:
            new_nick = f"[AFK] {original_nick}"
            await member.edit(nick=new_nick)
        except discord.Forbidden:
            await ctx.send("⚠️ Aku tidak bisa ganti nickname-mu (cek permission)")

        await ctx.send(f"✅ {member.mention} sekarang AFK: {reason}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        guild = message.guild
        if not guild:
            return  # DM, skip

        guild_id = guild.id
        if guild_id not in self.afk_users:
            return

        # Jangan trigger AFK balik saat command afk dipakai
        if message.content.startswith("!afk"):
            return

        # User yang AFK ngetik lagi → restore nickname
        if message.author.id in self.afk_users[guild_id]:
            info = self.afk_users[guild_id].pop(message.author.id)
            original_nick = info["nick"]
            try:
                await message.author.edit(nick=original_nick)
            except discord.Forbidden:
                pass
            await message.channel.send(f"👋 {message.author.mention} welcome back! AFK selesai.")

        # Cek mention user AFK
        for user_id, info in self.afk_users[guild_id].items():
            if user_id in [u.id for u in message.mentions]:
                await message.channel.send(
                    f"💤 {message.author.mention}, orang ini sedang AFK: {info['reason']}"
                )

# Setup cog untuk discord.py v2+
async def setup(bot):
    await bot.add_cog(AFK(bot))
