import discord
from discord.ext import commands
import random

class MegaFun(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        print("megafun.py loaded")

        # ================= RANDOM COLORS =================
        self.colors = [
            discord.Color.from_rgb(255, 182, 193),
            discord.Color.from_rgb(255, 193, 92),
            discord.Color.from_rgb(186, 104, 200),
            discord.Color.from_rgb(100, 181, 246),
            discord.Color.from_rgb(129, 199, 132),
            discord.Color.from_rgb(239, 83, 80)
        ]

        # ================= RANDOM DUO =================
        self.duo_list = [
            "🔥 Duo paling barbar sedunia",
            "😎 Duo paling sigma",
            "💀 Duo tukang rusuh VC",
            "🎮 Duo gamer nolep",
            "🤣 Duo badut server",
            "👑 Duo favorit warga",
            "☕ Duo gabut 24/7",
            "📚 Duo anak rajin",
            "🗿 Duo NPC server",
            "💤 Duo tukang ngilang"
        ]

        # ================= TAROT CARDS =================
        self.tarot_cards = [
            {
                "name": "The Fool",
                "meaning": "Awal baru besar sedang menunggumu 👀"
            },
            {
                "name": "The Lovers",
                "meaning": "Akan ada hubungan atau kedekatan baru 💕"
            },
            {
                "name": "Death",
                "meaning": "Sesuatu akan berakhir untuk membuka jalan baru ☠️"
            },
            {
                "name": "The Star",
                "meaning": "Harapan dan keberuntungan mendekat ✨"
            },
            {
                "name": "The Devil",
                "meaning": "Hati-hati dengan toxic atau godaan 😈"
            },
            {
                "name": "Wheel of Fortune",
                "meaning": "Nasibmu akan berubah drastis 🎡"
            },
            {
                "name": "The Sun",
                "meaning": "Kebahagiaan besar akan datang ☀️"
            },
            {
                "name": "The Moon",
                "meaning": "Ada sesuatu yang masih disembunyikan 🌙"
            },
            {
                "name": "Judgement",
                "meaning": "Saatnya menentukan pilihan penting ⚖️"
            },
            {
                "name": "The Emperor",
                "meaning": "Aura pemimpinmu sedang kuat 👑"
            }
        ]

    # ================= RANDOM COLOR =================
    def random_color(self):
        return random.choice(self.colors)

    # ================= GANTENG =================
    def get_ganteng_kalimat(self, member, persen):

        if persen >= 85:
            return f"{member} itu super ganteng! 😎💥 Persentase **{persen}%**!"

        elif persen >= 65:
            return f"{member} cukup ganteng 😏 Persentase **{persen}%**!"

        else:
            return f"{member} gantengnya sedang-sedang aja 😅 Persentase **{persen}%**."

    # ================= CANTIK =================
    def get_cantik_kalimat(self, member, persen):

        if persen >= 85:
            return f"{member} itu cantiknya luar biasa! 😍💖 Persentase **{persen}%**!"

        elif persen >= 65:
            return f"{member} cukup cantik 😊 Persentase **{persen}%**!"

        else:
            return f"{member} cantiknya sedang-sedang aja 😅 Persentase **{persen}%**."

    # ================= KAYA =================
    def get_kaya_kalimat(self, member, persen):

        if persen >= 85:
            return f"💸 {member} aura sultannya kuat banget! Kekayaanmu **{persen}%**!"

        elif persen >= 65:
            return f"💰 {member} lumayan kaya 😎 Persentase **{persen}%**."

        else:
            return f"🥲 {member} harus rajin nabung... baru **{persen}%**."

    # ================= HOKI =================
    def get_hoki_kalimat(self, member, persen):

        if persen >= 85:
            return f"🍀 {member} lagi hoki banget hari ini! **{persen}%**!"

        elif persen >= 65:
            return f"✨ {member} cukup hoki! Persentase **{persen}%**."

        else:
            return f"😭 Waduh {member}, hoki cuma **{persen}%**."

    # ================= TOXIC =================
    def get_toxic_kalimat(self, member, persen):

        if persen >= 85:
            return f"☠️ {member} toxic level max! **{persen}%**!"

        elif persen >= 65:
            return f"😬 {member} lumayan toxic... **{persen}%**."

        else:
            return f"😊 {member} ternyata baik kok! Toxic cuma **{persen}%**."

    # ================= JOMOK =================
    def get_jomok_kalimat(self, member, persen):

        if persen >= 85:
            return f"🏳️‍🌈 {member} sangat jomok 😭 Tingkat **{persen}%**!"

        elif persen >= 65:
            return f"😏 {member} agak mencurigakan... **{persen}%**."

        else:
            return f"😇 {member} masih aman kok, cuma **{persen}%**."

    # ================= SHIP =================
    def get_ship_kalimat(self, member1, member2, persen):

        if persen >= 90:
            return f"💞 {member1} dan {member2} soulmate banget! **{persen}%**"

        elif persen >= 70:
            return f"💕 {member1} dan {member2} cocok juga~ **{persen}%**"

        elif persen >= 50:
            return f"😅 {member1} dan {member2} fifty-fifty... **{persen}%**"

        else:
            return f"💔 {member1} dan {member2} kurang cocok 😭 **{persen}%**"

    # =========================================================
    # GANTENG
    # =========================================================
    @commands.command(name="ganteng")
    async def ganteng(self, ctx):

        persen = random.randint(1, 100)

        embed = discord.Embed(
            title=f"😎 Seberapa ganteng {ctx.author.display_name}?",
            description=self.get_ganteng_kalimat(
                ctx.author.display_name,
                persen
            ),
            color=self.random_color()
        )

        await ctx.send(embed=embed)

    # =========================================================
    # CANTIK
    # =========================================================
    @commands.command(name="cantik")
    async def cantik(self, ctx):

        persen = random.randint(1, 100)

        embed = discord.Embed(
            title=f"😍 Seberapa cantik {ctx.author.display_name}?",
            description=self.get_cantik_kalimat(
                ctx.author.display_name,
                persen
            ),
            color=self.random_color()
        )

        await ctx.send(embed=embed)

    # =========================================================
    # KAYA
    # =========================================================
    @commands.command(name="kaya")
    async def kaya(self, ctx):

        persen = random.randint(1, 100)

        embed = discord.Embed(
            title=f"💰 Seberapa kaya {ctx.author.display_name}?",
            description=self.get_kaya_kalimat(
                ctx.author.display_name,
                persen
            ),
            color=self.random_color()
        )

        await ctx.send(embed=embed)

    # =========================================================
    # HOKI
    # =========================================================
    @commands.command(name="hoki")
    async def hoki(self, ctx):

        persen = random.randint(1, 100)

        embed = discord.Embed(
            title=f"🍀 Tingkat hoki {ctx.author.display_name}",
            description=self.get_hoki_kalimat(
                ctx.author.display_name,
                persen
            ),
            color=self.random_color()
        )

        await ctx.send(embed=embed)

    # =========================================================
    # TOXIC
    # =========================================================
    @commands.command(name="toxic")
    async def toxic(self, ctx):

        persen = random.randint(1, 100)

        embed = discord.Embed(
            title=f"☠️ Seberapa toxic {ctx.author.display_name}?",
            description=self.get_toxic_kalimat(
                ctx.author.display_name,
                persen
            ),
            color=self.random_color()
        )

        await ctx.send(embed=embed)

    # =========================================================
    # JOMOK
    # =========================================================
    @commands.command(name="jomok")
    async def jomok(self, ctx):

        persen = random.randint(1, 100)

        embed = discord.Embed(
            title=f"🏳️‍🌈 Seberapa jomok {ctx.author.display_name}?",
            description=self.get_jomok_kalimat(
                ctx.author.display_name,
                persen
            ),
            color=self.random_color()
        )

        await ctx.send(embed=embed)

    # =========================================================
    # JODOH
    # =========================================================
    @commands.command(name="jodoh")
    async def jodoh(self, ctx, member: discord.Member = None):

        if member is None:
            return await ctx.send("❌ Gunakan: `!jodoh @member`")

        persen = random.randint(1, 100)

        embed = discord.Embed(
            title="💘 Cek Kecocokan Jodoh",
            description=f"""
{ctx.author.mention} ❤️ {member.mention}

Tingkat kecocokan:
**{persen}%**
""",
            color=self.random_color()
        )

        await ctx.send(embed=embed)

    # =========================================================
    # SHIP
    # =========================================================
    @commands.command(name="ship")
    async def ship(
        self,
        ctx,
        member1: discord.Member = None,
        member2: discord.Member = None
    ):

        if member1 is None or member2 is None:
            return await ctx.send(
                "❌ Gunakan: `!ship @member1 @member2`"
            )

        persen = random.randint(1, 100)

        embed = discord.Embed(
            title="💞 Ship Compatibility",
            description=self.get_ship_kalimat(
                member1.display_name,
                member2.display_name,
                persen
            ),
            color=self.random_color()
        )

        await ctx.send(embed=embed)

    # =========================================================
    # DUO
    # =========================================================
    @commands.command(name="duo")
    async def duo(self, ctx, member: discord.Member = None):

        if member is None:
            return await ctx.send(
                "❌ Gunakan: `!duo @member`"
            )

        hasil = random.choice(self.duo_list)

        embed = discord.Embed(
            title="👥 Duo Checker",
            description=f"""
{ctx.author.mention} dan {member.mention}

{hasil}
""",
            color=self.random_color()
        )

        await ctx.send(embed=embed)

    # =========================================================
    # TAROT
    # =========================================================
    @commands.command(name="tarot")
    async def tarot(self, ctx):

        card = random.choice(self.tarot_cards)

        embed = discord.Embed(
            title="🔮 Tarot Reading",
            description=f"""
🃏 Kartu:
**{card['name']}**

💭 Arti:
{card['meaning']}
""",
            color=self.random_color()
        )

        embed.set_footer(
            text=f"Ramalan untuk {ctx.author.display_name}"
        )

        await ctx.send(embed=embed)

# =========================================================
# SETUP
# =========================================================
async def setup(bot):
    await bot.add_cog(MegaFun(bot))