import discord
from discord.ext import commands
import json

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        with open("config.json") as f:
            self.config = json.load(f)

        # ✅ TARUH ID ROLE DI SINI
        self.MEMBER_ROLE_ID = 1453095603008442510  # ganti dengan ID role kamu

    # ✅ Welcome setelah dapat role
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):

        channel_id = self.config.get("welcome_channel")
        if not channel_id:
            return

        channel = after.guild.get_channel(channel_id)
        if not channel:
            return

        before_roles = set(role.id for role in before.roles)
        after_roles = set(role.id for role in after.roles)

        # ✅ Trigger kalau role baru ditambahkan
        if self.MEMBER_ROLE_ID not in before_roles and self.MEMBER_ROLE_ID in after_roles:
            await self.send_welcome(after)

    # Command test
    @commands.command(name="testwelcome")
    async def test_welcome(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        await self.send_welcome(member)

    # Fungsi kirim welcome
    async def send_welcome(self, member):
        channel_id = self.config.get("welcome_channel")
        if not channel_id:
            print("Config welcome_channel tidak ditemukan!")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            print(f"Channel dengan ID {channel_id} tidak ditemukan!")
            return

        embed = discord.Embed(
            title=f"Selamat datang, {member.display_name}! 🎉",
            description=(
                f"Halo {member.mention}, senang banget kamu gabung di **nanZ Server**! 🤍\n\n"
                "Di sini semua member dianggap keluarga, jadi jangan ragu untuk ngobrol, "
                "bertanya, atau ikut event bareng.\n\n"
                "Pastikan baca aturan di <#1406557882811682888> supaya pengalamanmu nyaman.\n"
                "Ambil role kamu di <#1408510751039291443>.\n\n"
                "✨ Sekarang kamu sudah **terverifikasi** dan bisa menikmati semua channel!"
            ),
            color=0x00ffcc
        )

        embed.set_footer(text="nanZ Server")
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_image(url="https://i.ibb.co/album/nanz-banner.png") 

        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Welcome(bot))