import discord
from discord.ext import commands
import json

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Load config
        with open("config.json") as f:
            self.config = json.load(f)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel_id = self.config.get("welcome_channel")
        if not channel_id:
            print("Config welcome_channel tidak ditemukan!")
            return

        channel = self.bot.get_channel(channel_id)
        if channel:
            # Membuat embed welcome
            embed = discord.Embed(
                title=f"Selamat datang {member.mention}! 🎉",
                description=(
                    "Kami sangat senang kamu bergabung di **nanZ Server**. "
                    "Di sini, setiap member dianggap bagian dari keluarga, jadi jangan ragu untuk bersantai, ngobrol, "
                    "dan saling berbagi cerita dengan semua orang.\n\n"
                    "Sebelum mulai, pastikan untuk membaca peraturan server di <#1406557882811682888> agar pengalamanmu "
                    "di sini tetap nyaman dan aman untuk semua.\n\n"
                    "Kalau ingin mengambil role, silakan kunjungi <#1408510751039291443>. "
                    "Untuk member perempuan, ada proses verifikasi supaya semua tetap nyaman dan aman. "
                    "Setelah verifikasi, kalian bisa dapat role **siswi** dengan mudah.\n\n"
                    "Semoga kamu betah dan merasa diterima. "
                    "Jangan sungkan untuk bertanya, ikut event, atau sekadar nongkrong bersama member lain.\n\n"
                    "Selamat bersenang-senang dan menikmati waktu kamu di **nanZ Server! 🤍**"
                ),
                color=0x00ffcc  # Warna embed, bisa diganti sesuai selera
            )
            embed.set_footer(text="nanZ Server")
            embed.set_thumbnail(url=member.display_avatar.url)  # Thumbnail pakai avatar member
            embed.set_image(url="https://i.ibb.co/album/nanz-banner.png")  # Bisa diganti banner server kalau mau

            await channel.send(embed=embed)
        else:
            print(f"Channel dengan ID {channel_id} tidak ditemukan!")

async def setup(bot):
    await bot.add_cog(Welcome(bot))
