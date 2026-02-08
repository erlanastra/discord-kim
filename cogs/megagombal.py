import discord
from discord.ext import commands
import random

class MegaGombal(commands.Cog):
    """Bot gombal otomatis, banyak & random, dengan embed warna-warni"""

    def __init__(self, bot):
        self.bot = bot

        # =========================
        # GOMBALAN RANDOM (UMUM)
        # =========================
        self.gombalan = [
            "Kalau kamu jadi matahari, aku rela jadi bumi yang muter biar selalu dekat kamu 🌞❤️",
            "Kamu itu kayak kopi, bikin aku ketagihan tiap pagi ☕🥰",
            "Senyummu itu lagu favoritku, aku pengen repeat terus 🎶💕",
            "Kamu kayak Wi-Fi, aku selalu nyari sinyalmu 😍📶",
            "Hidupku itu puzzle, dan kamu potongan paling indah 🧩❤️",
            "Kamu kayak charger, bikin hidupku penuh energi ⚡😊",
            "Kalau kamu bintang, aku rela jadi langitnya tiap malam 🌌✨",
            "Kamu itu password Wi-Fi, bikin aku pengen connect terus 🔐❤️",
            "Kalau kamu kopi, aku gula yang tak bisa lepas ☕🍬",
            "Kamu seperti matahari pagi, bikin hariku cerah setiap saat 🌄❤️",
            "Kalau senyummu bisa bikin aku kaya, aku rela jadi miliarder 😍💰",
            "Kamu kayak buku, tiap halaman bikin aku penasaran 📖💕",
            "Kalau kamu es krim, aku cone yang rela melekat terus 🍦💖",
            "Kamu tau ga persamaan kamu sama ikan tuna? sama-sama luTunaaa oiiii 😍💖",
            "Apa perbedaan kamu dengan jarum jam? kalau jarum jam muternya di angka, kalau kamu muternya dipikiranku ⌚❤️"
        ]

        self.lock_gombal = (
            "Kamu tau ga persamaan kamu sama ikan tuna? sama-sama luTunaaa oiiii 😍💖"
        )
        self.colors = [
            discord.Color.from_rgb(255, 182, 193), 
            discord.Color.from_rgb(255, 193, 92),   
            discord.Color.from_rgb(186, 104, 200), 
            discord.Color.from_rgb(100, 181, 246),  
            discord.Color.from_rgb(129, 199, 132),  
            discord.Color.from_rgb(239, 83, 80)     
        ]

        self.owner_id = 1169643619049799740 

    @commands.command(name="gombal")
    async def gombal(self, ctx, member: discord.Member, jumlah: int = 1):
        """
        Kirim gombalan ke member yang ditag.
        - Owner: gombalan dikunci (selalu sama)
        - User lain: random
        """

        # Batas maksimal
        if jumlah > 10:
            jumlah = 10

        embeds = []

        for _ in range(jumlah):
            # Kalau kamu yang pakai command → LOCK
            if ctx.author.id == self.owner_id:
                deskripsi = self.lock_gombal
            else:
                deskripsi = random.choice(self.gombalan)

            embed = discord.Embed(
                title=f"💌 Gombalan untuk {member.display_name}",
                description=deskripsi,
                color=random.choice(self.colors)
            )

            embeds.append(embed)

        await ctx.send(embeds=embeds)


# =========================
# SETUP DISCORD.PY v2+
# =========================
async def setup(bot):
    
    await bot.add_cog(MegaGombal(bot))
