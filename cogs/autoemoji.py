import discord
from discord.ext import commands
from PIL import Image
import io
import random


class AutoEmojiSticker(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # =========================================
        # GANTI DENGAN ID CHANNEL
        # =========================================
        self.EMOJI_CHANNEL_ID = 1513010386427711559
        self.STICKER_CHANNEL_ID = 1512893939479482488

        # =========================================
        # AUTO DELETE IMAGE
        # =========================================
        self.AUTO_DELETE = True

    # =========================================
    # RANDOM COLOR
    # =========================================
    def random_color(self):

        return discord.Color(
            random.randint(0, 0xFFFFFF)
        )

    # =========================================
    # CLEAN NAME
    # =========================================
    def clean_name(self, filename):

        name = (
            filename.split(".")[0]
            .replace(" ", "_")
            .replace("-", "_")
            .lower()
        )

        allowed = (
            "abcdefghijklmnopqrstuvwxyz"
            "0123456789_"
        )

        clean = "".join(
            c for c in name if c in allowed
        )

        return clean[:32]

    # =========================================
    # RESIZE EMOJI
    # =========================================
    async def resize_emoji(self, attachment):

        image_bytes = await attachment.read()

        image = Image.open(
            io.BytesIO(image_bytes)
        ).convert("RGBA")

        image.thumbnail((128, 128))

        output = io.BytesIO()

        image.save(
            output,
            format="PNG",
            optimize=True
        )

        output.seek(0)

        return output.read()

    # =========================================
    # DUPLICATE CHECK
    # =========================================
    def emoji_exists(self, guild, name):

        for emoji in guild.emojis:

            if emoji.name.lower() == name.lower():
                return True

        return False

    # =========================================
    # ON MESSAGE
    # =========================================
    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        if not message.guild:
            return

        if not message.attachments:
            return

        # =========================================
        # AUTO EMOJI
        # =========================================
        if message.channel.id == self.EMOJI_CHANNEL_ID:

            success = 0
            failed = 0

            for attachment in message.attachments:

                allowed = (
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".webp"
                )

                if not attachment.filename.lower().endswith(allowed):
                    continue

                try:

                    emoji_name = self.clean_name(
                        attachment.filename
                    )

                    # =========================
                    # DUPLICATE CHECK
                    # =========================
                    if self.emoji_exists(
                        message.guild,
                        emoji_name
                    ):

                        failed += 1
                        continue

                    # =========================
                    # RESIZE IMAGE
                    # =========================
                    image_bytes = await self.resize_emoji(
                        attachment
                    )

                    # =========================
                    # CREATE EMOJI
                    # =========================
                    emoji = await message.guild.create_custom_emoji(
                        name=emoji_name,
                        image=image_bytes,
                        reason=f"Upload by {message.author}"
                    )

                    success += 1

                    # =========================
                    # PREVIEW
                    # =========================
                    await message.channel.send(
                        f"✅ {emoji} "
                        f"`<:{emoji.name}:{emoji.id}>`"
                    )

                except:
                    failed += 1

            # =========================================
            # RESULT EMBED
            # =========================================
            embed = discord.Embed(
                title="🎉 Upload Emoji Selesai",
                description=(
                    f"✅ Berhasil: `{success}`\n"
                    f"❌ Gagal: `{failed}`"
                ),
                color=self.random_color()
            )

            await message.channel.send(
                embed=embed
            )

            # =========================================
            # AUTO DELETE IMAGE
            # =========================================
            if self.AUTO_DELETE:

                try:
                    await message.delete()
                except:
                    pass

        # =========================================
        # AUTO STICKER
        # =========================================
        if message.channel.id == self.STICKER_CHANNEL_ID:

            success = 0
            failed = 0

            for attachment in message.attachments:

                allowed = (
                    ".png",
                    ".apng"
                )

                if not attachment.filename.lower().endswith(allowed):
                    continue

                try:

                    sticker_name = self.clean_name(
                        attachment.filename
                    )[:30]

                    sticker_file = await attachment.to_file()

                    sticker = await message.guild.create_sticker(
                        name=sticker_name,
                        description="Uploaded via bot",
                        emoji="🔥",
                        file=sticker_file,
                        reason=f"Upload by {message.author}"
                    )

                    success += 1

                    await message.channel.send(
                        f"✅ Sticker `{sticker.name}` "
                        f"berhasil dibuat"
                    )

                except:
                    failed += 1

            embed = discord.Embed(
                title="🧩 Upload Sticker Selesai",
                description=(
                    f"✅ Berhasil: `{success}`\n"
                    f"❌ Gagal: `{failed}`"
                ),
                color=self.random_color()
            )

            await message.channel.send(
                embed=embed
            )

            if self.AUTO_DELETE:

                try:
                    await message.delete()
                except:
                    pass


# =========================================
# SETUP
# =========================================
async def setup(bot):

    await bot.add_cog(
        AutoEmojiSticker(bot)
    )