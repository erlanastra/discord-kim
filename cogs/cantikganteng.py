import discord
from discord.ext import commands
import random

class MegaCantikGanteng(commands.Cog):
    """Bot nilai ganteng/cantik otomatis, kalimat menyesuaikan persentase"""

    def __init__(self, bot):
        self.bot = bot

        # Warna embed acak
        self.colors = [
            discord.Color.from_rgb(255, 182, 193),  # Pink
            discord.Color.from_rgb(255, 193, 92),   # Orange
            discord.Color.from_rgb(186, 104, 200),  # Ungu
            discord.Color.from_rgb(100, 181, 246),  # Biru
            discord.Color.from_rgb(129, 199, 132),  # Hijau
            discord.Color.from_rgb(239, 83, 80)     # Merah
        ]

    # Fungsi untuk pilih kalimat sesuai persentase
    def get_ganteng_kalimat(self, member, persen):
        persen_bold = f"**{persen}%**"
        if persen >= 85:
            return f"{member} itu super ganteng! 😎💥 Persentase {persen_bold}! Senyummu bikin semua orang terpana!"
        elif persen >= 65:
            return f"{member} cukup ganteng 😏 Persentase {persen_bold}! Masih bisa bikin orang tersenyum."
        else:
            return f"{member} gantengnya sedang-sedang aja 😅 Persentase {persen_bold}%, tapi tetap lucu kok!"

    def get_cantik_kalimat(self, member, persen):
        persen_bold = f"**{persen}%**"
        if persen >= 85:
            return f"{member} itu cantiknya luar biasa! 😍💖 Persentase {persen_bold}! Pesonamu bikin dunia terang!"
        elif persen >= 65:
            return f"{member} cukup cantik 😊 Persentase {persen_bold}! Tetap memesona kok."
        else:
            return f"{member} cantiknya sedang-sedang aja 😅 Persentase {persen_bold}%, tapi tetap imut!"

    @commands.command(name="ganteng")
    async def ganteng(self, ctx):
        persen = random.randint(50, 100)
        kalimat = self.get_ganteng_kalimat(ctx.author.display_name, persen)
        embed = discord.Embed(
            title=f"😎 Seberapa ganteng {ctx.author.display_name}?",
            description=kalimat,
            color=random.choice(self.colors)
        )
        await ctx.send(embed=embed)

    @commands.command(name="cantik")
    async def cantik(self, ctx):
        persen = random.randint(50, 100)
        kalimat = self.get_cantik_kalimat(ctx.author.display_name, persen)
        embed = discord.Embed(
            title=f"😍 Seberapa cantik {ctx.author.display_name}?",
            description=kalimat,
            color=random.choice(self.colors)
        )
        await ctx.send(embed=embed)

# Setup discord.py v2+
async def setup(bot):
    await bot.add_cog(MegaCantikGanteng(bot))
