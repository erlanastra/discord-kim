import discord
from discord.ext import commands

# ==========================================
# CONFIG
# ==========================================

ADMIN_ROLE_IDS = [
    1453103644244316343,  # MOD
    1467360501745844446,  # Pembina OSIS
    1427276194876751902   # OSIS
]

# Isi channel tujuan default
POST_CHANNEL_ID = 123456789012345678

# ==========================================
# COG
# ==========================================

class PostSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="post")
    async def post_system(self, ctx, *, args):

        # ==========================================
        # 🔒 CEK AKSES
        # ==========================================
        if not any(role.id in ADMIN_ROLE_IDS for role in ctx.author.roles):
            await ctx.send(
                "❌ Kamu tidak punya akses untuk menggunakan command ini!",
                delete_after=5
            )
            return

        # ==========================================
        # 🧠 FORMAT
        # ==========================================
        try:
            judul, isi = args.split("|", 1)
        except ValueError:
            await ctx.send(
                "❌ Format salah!\n"
                "Gunakan:\n"
                "`!post Judul | Isi pesan`",
                delete_after=8
            )
            return

        # ==========================================
        # 🎨 EMBED STYLE NANZ
        # ==========================================
        embed = discord.Embed(
            description=(
                f"# {judul.strip()}\n\n"
                f"{isi.strip()}"
            ),
            color=discord.Color.from_rgb(35, 35, 35)
        )

        # Kasih timestamp
        embed.timestamp = discord.utils.utcnow()

        # ==========================================
        # 📸 ATTACHMENT
        # ==========================================
        file = None

        if ctx.message.attachments:
            attachment = ctx.message.attachments[0]

            # kalau gambar
            if attachment.content_type and attachment.content_type.startswith("image"):
                file = await attachment.to_file()
                embed.set_image(url=f"attachment://{attachment.filename}")

        # ==========================================
        # 📤 TARGET CHANNEL
        # ==========================================
        target_channel = ctx.channel

        if POST_CHANNEL_ID:
            channel = ctx.guild.get_channel(POST_CHANNEL_ID)

            if channel:
                target_channel = channel

        # ==========================================
        # 🚀 KIRIM POST
        # ==========================================
        await target_channel.send(
            embed=embed,
            file=file if file else None
        )

        # ==========================================
        # 🧹 HAPUS COMMAND
        # ==========================================
        try:
            await ctx.message.delete()
        except:
            pass


# ==========================================
# SETUP
# ==========================================

async def setup(bot):
    await bot.add_cog(PostSystem(bot))