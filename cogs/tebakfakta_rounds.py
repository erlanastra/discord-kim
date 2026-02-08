import discord
from discord.ext import commands
import random
import asyncio

class TebakFaktaRounds(commands.Cog):
    """Tebak Fakta / Trivia multi-round, siapa cepat dia dapat"""

    def __init__(self, bot):
        self.bot = bot

        self.questions = [
            # ================= UMUM =================
            {"question": "Apa hewan tercepat di darat?", "options": ["A. Kucing", "B. Cheetah", "C. Kuda", "D. Singa"], "answer": "B"},
            {"question": "Planet terdekat ke Matahari?", "options": ["A. Venus", "B. Mars", "C. Merkurius", "D. Bumi"], "answer": "C"},
            {"question": "Bahasa pemrograman yang dibuat Guido van Rossum?", "options": ["A. Java", "B. C++", "C. Python", "D. Ruby"], "answer": "C"},
            {"question": "Hewan terbesar di dunia?", "options": ["A. Paus Biru", "B. Gajah", "C. Hiu Paus", "D. Beruang Kutub"], "answer": "A"},
            {"question": "Simbol kimia untuk emas?", "options": ["A. Au", "B. Ag", "C. Fe", "D. Pb"], "answer": "A"},
            {"question": "Siapa penemu teori relativitas?", "options": ["A. Newton", "B. Galileo", "C. Albert Einstein", "D. Tesla"], "answer": "C"},

            # ================= DISCORD =================
            {"question": "Siapa pendiri Discord?", "options": ["A. Elon Musk", "B. Mark Zuckerberg", "C. Jason Citron", "D. Bill Gates"], "answer": "C"},
            {"question": "Discord pertama kali rilis tahun?", "options": ["A. 2013", "B. 2015", "C. 2017", "D. 2019"], "answer": "B"},
            {"question": "Bot Discord dibuat menggunakan bahasa?", "options": ["A. Python", "B. JavaScript", "C. Java", "D. Semua benar"], "answer": "D"},

            # ================= NANZ SERVER =================
            {"question": "Siapa nama asli Kim?", "options": ["A. Andre", "B. Nando", "C. Bob", "D. Erlan"], "answer": "B"},
            {"question": "Awal mula Server Nanz dibuat untuk komunitas apa?", 
             "options": ["A. Gaming", "B. Coding", "C. Community RP", "D. Anime"], 
             "answer": "C"},
            {"question": "Server Nanz dibuat pada bulan?", 
             "options": ["A. Juni", "B. Juli", "C. Agustus", "D. September"], 
             "answer": "C"},
            {"question": "Siapa mod paling baik di Server Nanz?", 
             "options": ["A. Bob", "B. Andre", "C. Nopal", "D. Erlan"], 
             "answer": "D"},
            {"question": "Mod paling suka akal-akalan?", 
             "options": ["A. Erlan", "B. Andre", "C. Odiyy", "D. Bob"], 
             "answer": "D"},
        ]

    @commands.command(name="tebakfakta")
    async def tebak_fakta(self, ctx, rounds: int = 5):
        """Tebak Fakta — siapa cepat dia dapat"""
        if rounds > len(self.questions):
            rounds = len(self.questions)

        asked = random.sample(self.questions, rounds)
        scores = {}

        await ctx.send(
            f"🧠 **TEBAK FAKTA DIMULAI!**\n"
            f"📌 Total **{rounds} ronde**\n"
            f"✍️ Jawab dengan **A / B / C / D**\n"
            f"🏆 Siapa cepat dia dapat poin!"
        )

        for i, q in enumerate(asked, start=1):
            embed = discord.Embed(
                title=f"Ronde {i}",
                description=f"**{q['question']}**\n\n" + "\n".join(q['options']),
                color=discord.Color.blurple()
            )
            embed.set_footer(text="Jawaban pertama yang benar akan dihitung")
            await ctx.send(embed=embed)

            answered = False

            def check(m):
                return (
                    m.channel == ctx.channel and
                    m.content.upper() in ["A", "B", "C", "D"]
                )

            try:
                while not answered:
                    msg = await self.bot.wait_for("message", timeout=20, check=check)
                    if msg.content.upper() == q["answer"]:
                        scores[msg.author] = scores.get(msg.author, 0) + 1
                        await ctx.send(f"✅ **Benar!** {msg.author.mention} dapat 1 poin 🎉")
                        answered = True
                    else:
                        await ctx.send(f"❌ Salah {msg.author.mention}, coba lagi!")
            except asyncio.TimeoutError:
                await ctx.send(f"⏰ Waktu habis! Jawaban benar: **{q['answer']}**")

        # ===== HASIL AKHIR =====
        if scores:
            leaderboard = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            result = "\n".join([f"🏅 {user.mention} — **{score} poin**" for user, score in leaderboard])

            embed = discord.Embed(
                title="🏆 HASIL AKHIR TEBAK FAKTA",
                description=result,
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("😢 Tidak ada yang menjawab dengan benar.")

# Setup Cog
async def setup(bot):
    await bot.add_cog(TebakFaktaRounds(bot))
