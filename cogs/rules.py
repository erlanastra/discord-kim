import discord
from discord.ext import commands

class Rules(commands.Cog):
    """Rules nanZ Community dengan embed warna-warni & deskripsi panjang."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="rules")
    @commands.has_permissions(administrator=True)
    async def rules(self, ctx):

        embeds = []

        # ================= HEADER =================
        embeds.append(discord.Embed(
            title="📜 Rules nanZ Community",
            description=(
                "✨ **Selamat datang di nanZ Community** ✨\n\n"
                "nanZ Community adalah ruang aman untuk bersantai, berbagi cerita,\n"
                "berdiskusi, bercanda secukupnya, dan tumbuh bersama tanpa tekanan 🤍\n\n"
                "Agar server ini tetap nyaman, aman, dan menyenangkan untuk semua member,\n"
                "**setiap orang WAJIB membaca dan mematuhi rules berikut.**"
            ),
            color=discord.Color.from_rgb(255, 182, 193)  # Pink
        ))

        # ================= 1 =================
        embeds.append(discord.Embed(
            title="🤍 1. Saling Menghormati Adalah Pondasi",
            description=(
                "Kami ingin semua orang merasa dihargai dan diterima di server ini.\n\n"
                "• Gunakan bahasa yang sopan, santun, dan beretika\n"
                "• ❌ Dilarang flaming, menghina, merendahkan, atau memprovokasi\n"
                "• ❌ Tidak ada ujaran kebencian, SARA, atau pelecehan dalam bentuk apa pun\n"
                "• 🔞 Konten NSFW **tidak diperbolehkan** di channel publik\n\n"
                "> Perbedaan pendapat itu wajar,\n"
                "> tapi sikap tidak sopan tidak bisa ditoleransi."
            ),
            color=discord.Color.from_rgb(255, 140, 140)  # Soft Red
        ))

        # ================= 2 =================
        embeds.append(discord.Embed(
            title="📌 2. Tertib, Bijak, dan Tahu Tempat",
            description=(
                "Ketertiban kecil berdampak besar pada kenyamanan bersama.\n\n"
                "• Hindari spam chat, emoji, stiker, atau mention berlebihan\n"
                "• Gunakan channel sesuai dengan topik dan fungsinya\n"
                "• 🚫 Dilarang mengirim link scam, phising, malware, atau ilegal\n"
                "• 📢 Promosi, jualan, atau share project **hanya di channel khusus**\n\n"
                "_Server yang rapi membuat obrolan lebih nyaman dan sehat._"
            ),
            color=discord.Color.from_rgb(255, 193, 92)  # Orange
        ))

        # ================= 3 =================
        embeds.append(discord.Embed(
            title="🔐 3. Privasi & Keamanan",
            description=(
                "Keamanan dan privasi adalah hal yang sangat kami jaga.\n\n"
                "• Jangan menyebarkan data pribadi diri sendiri maupun orang lain\n"
                "• ❌ Dilarang menyamar sebagai staff atau member lain\n"
                "• Jangan memanfaatkan bug atau celah sistem server\n"
                "• Hormati setiap keputusan Admin & Moderator\n\n"
                "_Keamanan satu orang adalah tanggung jawab seluruh komunitas._"
            ),
            color=discord.Color.from_rgb(186, 104, 200)  # Ungu
        ))

        # ================= 4 =================
        embeds.append(discord.Embed(
            title="💬 4. Kenyamanan Bersama",
            description=(
                "nanZ bukan tempat untuk konflik, tapi tempat untuk bertumbuh.\n\n"
                "• Jaga suasana server tetap positif, ramah, dan suportif\n"
                "• Hindari membawa konflik atau drama pribadi ke ruang publik\n"
                "• Jangan memancing keributan atau memperkeruh suasana\n"
                "• Jika ada masalah, hubungi staff secara pribadi dengan sikap dewasa\n\n"
                "> Kita datang untuk saling menguatkan,\n"
                "> bukan saling menjatuhkan."
            ),
            color=discord.Color.from_rgb(129, 199, 132)  # Hijau
        ))

        # ================= 5 =================
        embeds.append(discord.Embed(
            title="🌱 5. Real Life Tetap Nomor Satu",
            description=(
                "Kami memahami bahwa setiap member memiliki kehidupan di luar Discord.\n\n"
                "• Kehidupan nyata selalu lebih penting daripada server\n"
                "• Tidak ada kewajiban untuk selalu online atau aktif\n"
                "• Tidak ada tuntutan untuk fast response\n"
                "• Jaga waktu, kesehatan mental, dan diri kalian sendiri 🤍\n\n"
                "_Server ini hadir untuk menemani, bukan membebani._"
            ),
            color=discord.Color.from_rgb(100, 181, 246)  # Biru
        ))

        # ================= 6 =================
        embeds.append(discord.Embed(
            title="🔨 6. Sanksi & Penindakan",
            description=(
                "Aturan dibuat untuk dijalankan, bukan sekadar dibaca.\n\n"
                "Pelanggaran akan ditindak sesuai tingkat kesalahan:\n\n"
                "⚠️ **Warn** → 🔇 **Mute** → 🚪 **Kick** → ⛔ **Ban**\n\n"
                "_Keputusan staff bersifat final demi\n"
                "kenyamanan dan keamanan seluruh member._"
            ),
            color=discord.Color.from_rgb(239, 83, 80)  # Red
        ))

        embeds[-1].set_footer(
            text="nanZ Community • tempat pulang, bukan tempat tekanan 🤍"
        )

        await ctx.send(embeds=embeds)

async def setup(bot):
    await bot.add_cog(Rules(bot))
