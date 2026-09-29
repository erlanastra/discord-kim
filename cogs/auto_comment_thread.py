import discord
from discord.ext import commands


class AutoCommentThread(commands.Cog):
    """Auto membuat thread 'Komentar' pada channel tertentu."""

    TARGET_CHANNEL_IDS = {
        1416836800411865191,
        1469941689429786664,
        1489203444827947120,
        1416637801155268781,
        1526188632334012436,
        1545381123746570300,
        1455230674918441100,
        1523938793978069082,
        1523950507545329675,
    }

    THREAD_NAME = "Komentar"

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        # Abaikan pesan dari bot
        if message.author.bot:
            return

        # Hanya bekerja pada channel yang sudah ditentukan
        if message.channel.id not in self.TARGET_CHANNEL_IDS:
            return

        # Pastikan channel mendukung thread
        if not isinstance(message.channel, discord.TextChannel):
            return

        try:
            # Buat thread dari pesan tersebut
            await message.create_thread(
                name=self.THREAD_NAME,
                auto_archive_duration=1440,
                reason="Auto create comment thread for nanZ"
            )

        except discord.Forbidden:
            print(
                f"[AutoCommentThread] Tidak memiliki permission "
                f"untuk membuat thread di channel {message.channel.id}"
            )

        except discord.HTTPException as e:
            print(
                f"[AutoCommentThread] Gagal membuat thread "
                f"pada message {message.id}: {e}"
            )

        except Exception as e:
            print(
                f"[AutoCommentThread] Error tidak terduga: {e}"
            )


async def setup(bot):
    await bot.add_cog(AutoCommentThread(bot))