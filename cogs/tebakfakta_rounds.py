import discord
from discord.ext import commands
import random

class TebakFaktaRounds(commands.Cog):
    """Tebak Fakta / Trivia dengan multi-round & skor"""

    def __init__(self, bot):
        self.bot = bot
        # List pertanyaan umum
        self.questions = [
              {"question": "Apa hewan tercepat di darat?", "options": ["A. Kucing", "B. Cheetah", "C. Kuda", "D. Singa"], "answer": "B"},
            {"question": "Planet terdekat ke Matahari?", "options": ["A. Venus", "B. Mars", "C. Merkurius", "D. Bumi"], "answer": "C"},
            {"question": "Bahasa pemrograman yang dibuat Guido van Rossum?", "options": ["A. Java", "B. C++", "C. Python", "D. Ruby"], "answer": "C"},
            {"question": "Binatang yang bisa tidur sambil berdiri?", "options": ["A. Burung", "B. Kuda", "C. Sapi", "D. Semua benar"], "answer": "D"},
            {"question": "Ibu kota Jepang?", "options": ["A. Seoul", "B. Tokyo", "C. Beijing", "D. Bangkok"], "answer": "B"},
            {"question": "Berapa jumlah planet di tata surya?", "options": ["A. 7", "B. 8", "C. 9", "D. 10"], "answer": "B"},
            {"question": "Hewan terbesar di dunia?", "options": ["A. Paus Biru", "B. Gajah", "C. Hiu Paus", "D. Beruang Kutub"], "answer": "A"},
            {"question": "Apa simbol kimia untuk emas?", "options": ["A. Au", "B. Ag", "C. Fe", "D. Pb"], "answer": "A"},
            {"question": "Siapa penulis Harry Potter?", "options": ["A. J.K. Rowling", "B. Tolkien", "C. Suzanne Collins", "D. Rick Riordan"], "answer": "A"},
            {"question": "Negara terbesar berdasarkan luas?", "options": ["A. China", "B. Kanada", "C. Rusia", "D. Amerika Serikat"], "answer": "C"},
            {"question": "Siapa penemu telepon?", "options": ["A. Alexander Graham Bell", "B. Nikola Tesla", "C. Thomas Edison", "D. Guglielmo Marconi"], "answer": "A"},
            {"question": "Apa warna hasil campuran merah + biru?", "options": ["A. Ungu", "B. Hijau", "C. Oranye", "D. Coklat"], "answer": "A"},
            {"question": "Apa ibukota Indonesia?", "options": ["A. Bandung", "B. Jakarta", "C. Surabaya", "D. Medan"], "answer": "B"},
            {"question": "Hewan yang bisa hidup di air dan darat?", "options": ["A. Katak", "B. Kucing", "C. Burung", "D. Gajah"], "answer": "A"},
            {"question": "Benua terluas di dunia?", "options": ["A. Afrika", "B. Amerika", "C. Asia", "D. Eropa"], "answer": "C"},
            {"question": "Siapa penemu lampu pijar?", "options": ["A. Nikola Tesla", "B. Thomas Edison", "C. Alexander Graham Bell", "D. Benjamin Franklin"], "answer": "B"},
            {"question": "Binatang nasional Australia?", "options": ["A. Kanguru", "B. Koala", "C. Platipus", "D. Emu"], "answer": "A"},
            {"question": "Bahasa resmi Brasil?", "options": ["A. Spanyol", "B. Portugis", "C. Inggris", "D. Prancis"], "answer": "B"},
            {"question": "Apa planet terbesar di tata surya?", "options": ["A. Saturnus", "B. Jupiter", "C. Uranus", "D. Neptunus"], "answer": "B"},
            {"question": "Siapa penulis novel 'The Hobbit'?", "options": ["A. J.K. Rowling", "B. J.R.R. Tolkien", "C. C.S. Lewis", "D. George R.R. Martin"], "answer": "B"},
            {"question": "Berapa sisi segitiga?", "options": ["A. 3", "B. 4", "C. 5", "D. 6"], "answer": "A"},
            {"question": "Apa nama gas yang kita hirup untuk bernafas?", "options": ["A. Karbon Dioksida", "B. Nitrogen", "C. Oksigen", "D. Hidrogen"], "answer": "C"},
            {"question": "Hewan tercepat di air?", "options": ["A. Hiu", "B. Ikan Marlin", "C. Lumba-lumba", "D. Paus"], "answer": "B"},
            {"question": "Negara dengan piramida terkenal?", "options": ["A. Meksiko", "B. Mesir", "C. Peru", "D. Irak"], "answer": "B"},
            {"question": "Bulan terbesar di tata surya?", "options": ["A. Titan", "B. Ganymede", "C. Europa", "D. Callisto"], "answer": "B"},
            {"question": "Alat musik berdawai dari Jepang?", "options": ["A. Shamisen", "B. Koto", "C. Taiko", "D. Biwa"], "answer": "B"},
            {"question": "Hewan peliharaan populer di rumah?", "options": ["A. Anjing", "B. Kucing", "C. Burung", "D. Semua benar"], "answer": "D"},
            {"question": "Sungai terpanjang di dunia?", "options": ["A. Amazon", "B. Nil", "C. Mississippi", "D. Yangtze"], "answer": "B"},
            {"question": "Siapa penemu teori relativitas?", "options": ["A. Isaac Newton", "B. Galileo", "C. Albert Einstein", "D. Nikola Tesla"], "answer": "C"},
            {"question": "Simbol kimia untuk air?", "options": ["A. H2O", "B. CO2", "C. O2", "D. NaCl"], "answer": "A"},
        ]

    @commands.command(name="tebakfakta")
    async def tebak_fakta(self, ctx, rounds: int = 5):
        """Main TebakFakta multi-round, default 5 ronde"""
        if rounds > len(self.questions):
            rounds = len(self.questions)

        score = 0
        asked_questions = random.sample(self.questions, rounds)

        await ctx.send(f"🧠 Tebak Fakta! Kamu akan main {rounds} ronde. Jawab dengan A, B, C, atau D.")

        for i, q in enumerate(asked_questions, start=1):
            embed = discord.Embed(
                title=f"Ronde {i} - Tebak Fakta!",
                description=f"{q['question']}\n\n" + "\n".join(q['options']),
                color=discord.Color.blurple()
            )
            embed.set_footer(text="Balas jawabanmu dengan A, B, C, atau D")
            await ctx.send(embed=embed)

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.upper() in ["A","B","C","D"]

            try:
                msg = await self.bot.wait_for("message", check=check, timeout=20)
                if msg.content.upper() == q["answer"]:
                    await ctx.send(f"✅ Benar, {ctx.author.mention}!")
                    score += 1
                else:
                    await ctx.send(f"❌ Salah, jawaban yang benar adalah **{q['answer']}**")
            except:
                await ctx.send(f"⏰ Waktu habis! Jawaban yang benar adalah **{q['answer']}**")

        await ctx.send(f"🎉 Game selesai! {ctx.author.mention}, skor akhir kamu: **{score}/{rounds}**")

# Setup cog untuk discord.py v2+
async def setup(bot):
    await bot.add_cog(TebakFaktaRounds(bot))
