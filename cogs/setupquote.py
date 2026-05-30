import discord
from discord.ext import commands
import random

# ==========================================
# ID CHANNEL QUOTE
# ==========================================
QUOTE_CHANNEL_ID = 1474394873783128368


# ==========================================
# MODAL QUOTE
# ==========================================
class QuoteModal(discord.ui.Modal, title="📝 Buat Quote"):

    quote = discord.ui.TextInput(
        label="Isi Quote",
        style=discord.TextStyle.paragraph,
        placeholder="Tulis quote kamu...",
        required=True,
        max_length=500
    )

    mood = discord.ui.TextInput(
        label="Mood / Emoji",
        placeholder="🌙✨💔",
        required=False,
        max_length=50
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):

        # simpan data sementara
        self.bot.quote_data[interaction.user.id] = {
            "quote": self.quote.value,
            "mood": self.mood.value
        }

        await interaction.response.send_message(
            (
                "**Quote berhasil dibuat.**\n\n"
                "Sekarang klik tombol dibawah "
                "untuk upload foto, lagu, atau sticker."
            ),
            view=UploadView(self.bot),
            ephemeral=True
        )


# ==========================================
# VIEW UPLOAD
# ==========================================
class UploadView(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot

    # ==========================================
    # FUNCTION KIRIM QUOTE
    # ==========================================
    async def send_quote(
        self,
        interaction: discord.Interaction,
        files=None,
        stickers=None
    ):

        files = files or []
        stickers = stickers or []

        # ambil data quote
        data = self.bot.quote_data.get(
            interaction.user.id
        )

        if not data:
            return

        quote_channel = self.bot.get_channel(
            QUOTE_CHANNEL_ID
        )

        if not quote_channel:
            return

        # ==========================================
        # EMBED
        # ==========================================
        colors = [
            discord.Color.blurple(),
            discord.Color.purple(),
            discord.Color.magenta(),
            discord.Color.teal(),
            discord.Color.random()
        ]

        embed = discord.Embed(
            description=f"❝ *{data['quote']}* ❞",
            color=random.choice(colors)
        )

        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )

        # mood
        if data["mood"]:
            embed.add_field(
                name="Mood",
                value=data["mood"],
                inline=False
            )

        image_file = None
        music_files = []

        for file in files:

            filename = file.filename.lower()

            # FOTO
            if filename.endswith(
                ("png", "jpg", "jpeg", "webp", "gif")
            ):
                image_file = file

            # LAGU
            elif filename.endswith(
                ("mp3", "wav", "ogg", "m4a")
            ):
                music_files.append(file)

        # FOTO KE EMBED
        if image_file:
            embed.set_image(
                url=f"attachment://{image_file.filename}"
            )

        # STICKER KE EMBED
        if stickers:

            sticker = stickers[0]

            try:
                embed.set_thumbnail(
                    url=sticker.url
                )
            except:
                pass

        embed.set_footer(
            text=f"Quote by {interaction.user.display_name}"
        )

        # ==========================================
        # KIRIM EMBED
        # ==========================================
        send_files = []

        if image_file:
            send_files.append(image_file)

        quote_message = await quote_channel.send(
            embed=embed,
            files=send_files
        )

        # ==========================================
        # AUTO REACT
        # ==========================================
        reactions = [
            "❤️",
            "✨"
        ]

        for react in reactions:
            try:
                await quote_message.add_reaction(
                    react
                )
            except:
                pass

        # ==========================================
        # AUTO THREAD
        # ==========================================
        try:
            await quote_message.create_thread(
                name=(
                    f"💭 Quote by "
                    f"{interaction.user.display_name}"
                )
            )
        except:
            pass

        # ==========================================
        # KIRIM LAGU
        # ==========================================
        for music in music_files:

            music_embed = discord.Embed(
                description=(
                    f"**Now Playing**\n"
                    f"`{music.filename}`"
                ),
                color=discord.Color.dark_theme()
            )

            await quote_channel.send(
                embed=music_embed,
                file=music
            )

        # hapus cache
        self.bot.quote_data.pop(
            interaction.user.id,
            None
        )

    # ==========================================
    # BUTTON UPLOAD
    # ==========================================
    @discord.ui.button(
        label="📤 Upload Media",
        style=discord.ButtonStyle.blurple,
        custom_id="quote_upload_media"
    )
    async def upload_media(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            (
                "Sekarang kirim:\n"
                "🖼️ Foto\n"
                "🎵 Lagu\n"
                "🌸 Sticker\n\n"
                ">> Pesan akan otomatis dihapus.\n"
                "⏳ Tunggu dalam 60 detik."
            ),
            ephemeral=True
        )

        def check(message):
            return (
                message.author == interaction.user
                and message.channel == interaction.channel
            )

        files = []
        stickers = []

        try:
            msg = await self.bot.wait_for(
                "message",
                timeout=60,
                check=check
            )

            # file
            if msg.attachments:
                files = [
                    await attachment.to_file()
                    for attachment in msg.attachments
                ]

            # sticker
            if msg.stickers:
                stickers = msg.stickers

            # auto delete
            try:
                await msg.delete()
            except:
                pass

        except:
            await interaction.followup.send(
                "❌ Waktu upload habis.",
                ephemeral=True
            )
            return

        await self.send_quote(
            interaction,
            files=files,
            stickers=stickers
        )

        await interaction.followup.send(
            "**Quote berhasil dikirim.**",
            ephemeral=True
        )

    # ==========================================
    # BUTTON SKIP
    # ==========================================
    @discord.ui.button(
        label="⏭️ Skip",
        style=discord.ButtonStyle.gray,
        custom_id="quote_skip_media"
    )
    async def skip_media(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        await self.send_quote(
            interaction
        )

        await interaction.followup.send(
            "**Quote berhasil dikirim tanpa media.**",
            ephemeral=True
        )

# ==========================================
# VIEW UTAMA
# ==========================================
class QuoteView(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="📝 Buat Quote",
        style=discord.ButtonStyle.blurple,
        custom_id="quote_make_button"
    )
    async def make_quote(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            QuoteModal(self.bot)
        )


# ==========================================
# COG
# ==========================================
class QuoteSystem(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        if not hasattr(bot, "quote_data"):
            bot.quote_data = {}

    @commands.command(name="setupquote")
    @commands.has_permissions(administrator=True)
    async def setupquote(self, ctx):

        embed = discord.Embed(
            title="nanZ Quote",
            description=(
                "Klik tombol dibawah untuk membuat quote.\n\n"
                "> Semua quote otomatis dikirim "
                "ke channel quote."
            ),
            color=discord.Color.random()
        )

        embed.set_thumbnail(
            url=self.bot.user.display_avatar.url
        )

        await ctx.send(
            embed=embed,
            view=QuoteView(self.bot)
        )


# ==========================================
# SETUP
# ==========================================
async def setup(bot):
    await bot.add_cog(QuoteSystem(bot))