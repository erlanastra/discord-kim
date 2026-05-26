import discord
from discord.ext import commands
import asyncio

class VerifyGreeting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # ✅ GANTI SEMUA ID DI BAWAH INI
        self.VERIF_CHANNEL_ID = 1486913580161962054
        self.MEMBER_ROLE_ID = 1453095603008442510

        # ✅ ROLE STAFF (ISI ID NYA)
        self.MOD_DC_ROLE_ID = 1453103644244316343
        self.MOD_YT_ROLE_ID = 1408509547601203252
        self.PEMBINA_OSIS_ROLE_ID = 1467360501745844446
        self.OSIS_ROLE_ID = 1427276194876751902

        # cache biar ga spam
        self.already_greeted = set()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # hanya channel verif
        if message.channel.id != self.VERIF_CHANNEL_ID:
            return

        member = message.author

        # skip kalau sudah punya role member
        if any(role.id == self.MEMBER_ROLE_ID for role in member.roles):
            return

        # biar ga spam
        if member.id in self.already_greeted:
            return

        self.already_greeted.add(member.id)

        # ⏳ delay biar natural
        await asyncio.sleep(2)

        # 🔔 mention role staff
        staff_mention = (
            f"<@&{self.MOD_DC_ROLE_ID}> "
            f"<@&{self.PEMBINA_OSIS_ROLE_ID}> "
            f"<@&{self.OSIS_ROLE_ID}>"
        )

        embed = discord.Embed(
            title="⏳ Verifikasi diproses",
            description=(
                f"{member.mention}, verifikasi kamu sudah masuk.\n"
                "Mohon tunggu sebentar sampai staff memproses ya.\n\n"
                "Terima kasih 🙏"
            ),
            color=0xF5E6FF
        )

        embed.set_footer(text="nanZ Server")
        embed.set_thumbnail(url=member.display_avatar.url)

        # kirim + tag staff
        await message.channel.send(
            content=staff_mention,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True)
        )

async def setup(bot):
    await bot.add_cog(VerifyGreeting(bot))