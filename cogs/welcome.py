import discord
from discord.ext import commands
import json

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Load config
        with open("config.json") as f:
            self.config = json.load(f)

    # Listener untuk member baru join
    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.send_welcome(member)

    # Command untuk tes welcome
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
            title=f"Selamat datang, {member.name}! 🎉",
            description=(
                f"Halo {member.mention}, senang banget kamu gabung di **nanZ Server**! 🤍\n\n"
                "Di sini semua member dianggap keluarga, jadi jangan ragu untuk ngobrol, "
                "bertanya, atau ikut event bareng.\n\n"
                "Pastikan baca aturan di <#1406557882811682888> supaya pengalamanmu nyaman.\n"
                "Ambil role kamu di <#1408510751039291443>. "
                "Untuk member perempuan, ada proses verifikasi agar semua tetap aman. "
                "Setelah itu, kalian bisa dapat role **siswi** dengan mudah.\n\n"
                "Semoga betah ya! Jangan sungkan untuk aktif dan menikmati semua kegiatan di server."
            ),
            color=0x00ffcc
        )
        embed.set_footer(text="nanZ Server")
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_image(url="https://i.ibb.co/album/nanz-banner.png")  # Banner server

        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
