import discord
from discord.ext import commands

class AFK(commands.Cog):
    """AFK multi-server dengan nickname otomatis & embed warna-warni"""

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
            await ctx.send(embed=discord.Embed(
                title="❌ AFK Gagal",
                description=f"{member.mention}, kamu sudah AFK sebelumnya! Jangan lupa istirahat dulu 😉",
                color=discord.Color.red()
            ))
            return

        # Simpan nickname asli
        original_nick = member.display_name
        self.afk_users[guild_id][member.id] = {"nick": original_nick, "reason": reason}

        # Coba ganti nickname
        try:
            new_nick = f"[AFK] {original_nick}"
            await member.edit(nick=new_nick)
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(
                title="⚠️ Gagal Ubah Nickname",
                description="Aku tidak bisa mengubah nickname-mu. Cek permission ya!",
                color=discord.Color.orange()
            ))

        # Kirim embed AFK
        embed = discord.Embed(
            title="✅ Kamu sekarang AFK!",
            description=f"**Alasan:** **{reason}**",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"{member.display_name} sedang offline sementara...")
        await ctx.send(embed=embed)

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
            embed = discord.Embed(
                title="👋 Welcome Back!",
                description=f"{message.author.mention}, AFK-mu sudah selesai. Semangat lagi! ✨",
                color=discord.Color.green()
            )
            embed.set_footer(text="Senang kamu kembali!")
            await message.channel.send(embed=embed)
            await self.bot.process_commands(message)

        # Cek mention user AFK
        for user_id, info in self.afk_users[guild_id].items():
            if user_id in [u.id for u in message.mentions]:
                user_obj = self.bot.get_user(user_id)
                embed = discord.Embed(
                    title="💤 Sedang AFK",
                    description=f"{message.author.mention}, **{user_obj.display_name}** sedang AFK 😴\n**Alasan:** **{info['reason']}**",
                    color=discord.Color.purple()
                )
                embed.set_footer(text="Jangan diganggu dulu ya!")
                await message.channel.send(embed=embed)

# Setup cog untuk discord.py v2+
async def setup(bot):
    await bot.add_cog(AFK(bot))
