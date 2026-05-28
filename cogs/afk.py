import discord
from discord.ext import commands
from datetime import datetime
import random


class AFK(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.afk_users = {}

    # ================= RANDOM COLOR =================
    def random_color(self):

        return discord.Color(
            random.randint(0, 0xFFFFFF)
        )

    # ================= FORMAT WAKTU =================
    def format_time(self, seconds):

        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        if days > 0:
            return f"{days} hari {hours} jam"

        elif hours > 0:
            return f"{hours} jam {minutes} menit"

        elif minutes > 0:
            return f"{minutes} menit {seconds} detik"

        else:
            return f"{seconds} detik"

    # ================= COMMAND AFK =================
    @commands.command(name="afk")
    @commands.cooldown(
        1,
        2,
        commands.BucketType.user
    )

    async def afk(self, ctx, *, reason="AFK"):

        user = ctx.author
        now = datetime.utcnow()

        # ================= CEK SUDAH AFK =================
        if user.id in self.afk_users:

            old_data = self.afk_users[user.id]

            diff = (
                now - old_data["since"]
            ).total_seconds()

            # Kalau benar-benar masih AFK
            if diff > 3:

                embed = discord.Embed(
                    title="❌ AFK Gagal",
                    description=(
                        f"{user.mention}, "
                        f"kamu sudah AFK sebelumnya!"
                    ),
                    color=0xED4245
                )

                return await ctx.send(
                    embed=embed
                )

            # Kalau duplicate execute
            return

        # ================= SIMPAN AFK =================
        self.afk_users[user.id] = {
            "reason": reason,
            "since": now
        }

        # ================= UBAH NICKNAME =================
        try:

            if ctx.guild:

                original_name = (
                    user.display_name
                    .replace("[AFK] ", "")
                )

                await user.edit(
                    nick=f"[AFK] {original_name}"
                )

        except:
            pass

        # ================= EMBED AFK =================
        embed = discord.Embed(
            title="🌙 AFK Status Aktif",
            description=(
                f"{user.mention} "
                f"telah mengaktifkan status AFK.\n"
                f">>> **Alasan:** {reason}"
            ),
            color=self.random_color()
        )

        embed.set_footer(
            text=(
                "Status akan otomatis "
                "nonaktif saat kamu kembali"
            )
        )

        await ctx.send(embed=embed)

    # ================= HIDE COOLDOWN =================
    @afk.error
    async def afk_error(self, ctx, error):

        if isinstance(
            error,
            commands.CommandOnCooldown
        ):
            return

    # ================= RESET AFK =================
    @commands.command(name="resetafk")
    @commands.has_permissions(administrator=True)
    async def resetafk(self, ctx):

        self.afk_users.clear()

        embed = discord.Embed(
            title="🧹 AFK Reset",
            description=(
                "Semua data AFK berhasil direset."
            ),
            color=0x57F287
        )

        await ctx.send(embed=embed)

    # ================= ON MESSAGE =================
    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        # Ignore command
        if message.content.startswith("!"):
            return

        user_id = message.author.id

        # ================= REMOVE AFK =================
        if user_id in self.afk_users:

            data = self.afk_users.pop(user_id)

            afk_time = (
                datetime.utcnow() - data["since"]
            ).total_seconds()

            waktu = self.format_time(
                int(afk_time)
            )

            # ================= BALIKIN NICKNAME =================
            try:

                if message.guild:

                    original_name = (
                        message.author.display_name
                        .replace("[AFK] ", "")
                    )

                    await message.author.edit(
                        nick=original_name
                    )

            except:
                pass

            # ================= EMBED WELCOME BACK =================
            embed = discord.Embed(
                title="👋 Welcome Back",
                description=(
                    f"{message.author.mention}, "
                    f"AFK-mu sudah selesai\n"
                    f">>> **Durasi AFK:** {waktu}`"
                ),
                color=self.random_color()
            )

            await message.channel.send(
                embed=embed
            )

        # ================= CEK USER AFK =================
        for user in message.mentions:

            if user.id in self.afk_users:

                data = self.afk_users[user.id]

                afk_time = (
                    datetime.utcnow() - data["since"]
                ).total_seconds()

                waktu = self.format_time(
                    int(afk_time)
                )

                embed = discord.Embed(
                    title="⚠️ Pengguna Sedang AFK",
                    description=(
                        f"{user.mention} "
                        f"saat ini sedang AFK.\n"
                        f">>> **Alasan:** {data['reason']} \n"
                        f"**Sejak:** {waktu} yang lalu"
                    ),
                    color=self.random_color()
                )

                await message.channel.send(
                    embed=embed
                )

                break


# ================= SETUP =================
async def setup(bot):

    await bot.add_cog(
        AFK(bot)
    )