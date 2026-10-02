import discord
from discord.ext import commands

class About(commands.Cog):
    """About nanZ Server dengan konsep sekolah & storytelling."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="about")
    async def about(self, ctx):

        embeds = []

        # ================= HEADER =================
        embeds.append(discord.Embed(
            title="🏫 Tentang nanZ Server",
            description=(
                "Selamat datang di nanZ Server!\n\n"
                "Server ini adalah komunitas Discord yang dibangun sebagai tempat "
                "untuk berkumpul, berbagi cerita, dan bertumbuh bersama. "
                "Semua member diterima tanpa memandang latar belakang.\n\n"
                "Seiring waktu, server ini mengembangkan identitas dan konsep unik "
                "yang membuatnya berbeda dari komunitas lain."
            ),
            color=discord.Color.from_rgb(255, 182, 193)
        ))

        # ================= 1 =================
        embeds.append(discord.Embed(
            title="1. Awal Mula",
            description=(
                "NanZ Server awalnya dibuat untuk mewadahi komunitas roleplay "
                "(RP) GTA oleh owner, Nando (IC: Kim), seorang streamer GTA RP.\n\n"
                "Tujuannya adalah memberikan tempat bagi para viewer untuk berkumpul "
                "dan berinteraksi di luar stream. Dari sinilah Discord ini lahir "
                "dengan nama **nanZ Server**."
            ),
            color=discord.Color.from_rgb(255, 140, 140)
        ))

        # ================= 2 =================
        embeds.append(discord.Embed(
            title="2. Berkembang Menjadi All Community",
            description=(
                "Seiring berjalannya waktu, server ini tidak hanya untuk komunitas RP, "
                "melainkan terbuka untuk semua tipe member:\n"
                "• Gamer yang ingin bermain dan berdiskusi\n"
                "• Non-gamer yang ingin nongkrong atau sharing\n"
                "• Semua orang yang ingin menjadi bagian komunitas yang ramah dan aman\n\n"
                "Dengan demikian, nanZ Server menjadi tempat untuk berinteraksi, "
                "belajar, dan bersosialisasi secara luas."
            ),
            color=discord.Color.from_rgb(255, 193, 92)
        ))

        # ================= 3 =================
        embeds.append(discord.Embed(
            title="3. Konsep Sekolahan",
            description=(
                "Salah satu ciri khas nanZ Server adalah konsep bertema sekolah. "
                "Hal ini diambil karena owner merupakan seorang guru di dunia nyata.\n\n"
                "Konsep sekolah terlihat dari beberapa role, channel, dan sistem "
                "interaksi di server, sehingga member bisa belajar, bermain, "
                "dan bertumbuh bersama dalam suasana yang familiar."
            ),
            color=discord.Color.from_rgb(186, 104, 200)
        ))

        # ================= 4 =================
        embeds.append(discord.Embed(
            title="4. Role & Struktur",
            description=(
                "**Staff / Pengurus:**\n"
                "• Guru Besar – Owner\n"
                "• Mod DC – Mengelola Discord dengan full permission\n"
                "• Pembina OSIS – Mengarahkan aktivitas OSIS\n"
                "• OSIS – Membantu pengelolaan event server\n\n"
                "**Member / Siswa:**\n"
                "• Murid – Member umum"
            ),
            color=discord.Color.from_rgb(129, 199, 132)
        ))

        # ================= 5 =================
        embeds.append(discord.Embed(
            title="5. Channel & Event",
            description=(
                "Beberapa channel di server menggunakan konsep sekolah, seperti:\n"
                "• Channel mapel: berisi fakta dan pengetahuan ringan\n"
                "• Channel ngobrol santai: tempat interaksi antar member\n\n"
                "Event rutin mingguan:\n"
                "• Girls Corner – Voice khusus siswi, setiap malam Jumat\n"
                "• Nobar – Nonton bareng komunitas, setiap malam Minggu\n\n"
                "Konsep ini membuat belajar, bermain, dan bersosialisasi menjadi lebih menyenangkan."
            ),
            color=discord.Color.from_rgb(100, 181, 246)
        ))

        # ================= 6 =================
        embeds.append(discord.Embed(
            title="6. Verifikasi & Penutup",
            description=(
                "• Role Siswi memerlukan verifikasi untuk keamanan dan kenyamanan server\n"
                "• Sistem dibuat agar setiap member merasa aman dan nyaman\n\n"
                "NanZ Server bukan sekadar Discord, tetapi komunitas dan tempat pulang. "
                "Member dapat datang sebagai orang baru dan menjadi bagian dari cerita komunitas."
            ),
            color=discord.Color.from_rgb(239, 83, 80)
        ))

        embeds[-1].set_footer(
            text="nanZ Server • belajar, bermain, dan bertumbuh bersama"
        )

        await ctx.send(embeds=embeds)


async def setup(bot):
    await bot.add_cog(About(bot))
