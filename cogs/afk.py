import discord
from discord.ext import commands
from datetime import datetime
from database import db
import random


class AFK(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    # ================= RANDOM COLOR =================
    def random_color(self):

        return discord.Color(
            random.randint(0, 0xFFFFFF)
        )

    @commands.command(name="dbtest")
    async def dbtest(self, ctx):

        data = await db.fetchone(
            "SELECT NOW() AS waktu"
        )

        embed = discord.Embed(
            title="✅ Database Connected",
            description=f"Waktu database:\n```{data['waktu']}```",
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)

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

        if ctx.guild is None:

            embed = discord.Embed(
                title="❌ Tidak Bisa Digunakan",
                description="Command ini hanya bisa digunakan di dalam server.",
                color=0xED4245
            )

            return await ctx.send(embed=embed)

        user = ctx.author
        now = datetime.utcnow()

        # ================= CEK SUDAH AFK =================
        existing = await db.fetchone(
            """
            SELECT *
            FROM afk
            WHERE user_id=%s
            AND guild_id=%s
            """,
            user.id,
            ctx.guild.id
        )

        if existing:

            embed = discord.Embed(
                title="❌ AFK Gagal",
                description=f"{user.mention}, kamu sudah AFK sebelumnya!",
                color=0xED4245
            )

            return await ctx.send(embed=embed)

        # ================= SIMPAN AFK =================
        await db.execute(
            """
            INSERT INTO afk
            (user_id, guild_id, reason, afk_since)
            VALUES (%s,%s,%s,%s)
            """,
            user.id,
            ctx.guild.id,
            reason,
            now
        )

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
        except Exception as e:
            print(e)

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

        await db.execute("DELETE FROM afk")

        embed = discord.Embed(
            title="🧹 AFK Reset",
            description=(
                "Semua data AFK berhasil direset."
            ),
            color=0x57F287
        )

        await ctx.send(embed=embed)
    
    # ================= SYNC AFK SAAT BOT READY =================
    @commands.Cog.listener()
    async def on_ready(self):

        print("AFK DATABASE AKTIF")

        try:

            afk_users = await db.fetchall(
                "SELECT * FROM afk"
            )

            total = 0

            for data in afk_users:

                guild = self.bot.get_guild(
                    data["guild_id"]
                )

                if not guild:
                    continue

                member = guild.get_member(
                    data["user_id"]
                )

                if not member:
                    continue

                try:

                    if not member.display_name.startswith("[AFK] "):

                        await member.edit(
                            nick=f"[AFK] {member.display_name}"
                        )

                    total += 1

                except Exception:
                    pass

            print(
                f"AFK Sync selesai ({total} user)"
            )

        except Exception as e:

            print(
                f"AFK Sync Error: {e}"
            )


    @commands.Cog.listener()
    async def on_member_remove(self, member):

        await db.execute(
            """
            DELETE FROM afk
            WHERE user_id=%s
            AND guild_id=%s
            """,
            member.id,
            member.guild.id
        )


    # ================= ON MESSAGE =================
    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return
        
        if message.guild is None:
            return

        # Ignore command
        if message.content.startswith("!"):
            return

        user_id = message.author.id

        # ================= REMOVE AFK =================
        data = await db.fetchone(
            """
            SELECT *
            FROM afk
            WHERE user_id=%s
            AND guild_id=%s
            """,
            user_id,
            message.guild.id
        )

        if data:

            await db.execute(
                """
                DELETE FROM afk
                WHERE user_id=%s
                AND guild_id=%s
                """,
                user_id,
                message.guild.id
            )

            afk_time = (
                datetime.utcnow() - data["afk_since"]
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

            except Exception as e:
                print(e)

            # ================= EMBED WELCOME BACK =================
            embed = discord.Embed(
                title="👋 Welcome Back",
                description=(
                    f"{message.author.mention}, "
                    f"AFK-mu sudah selesai\n"
                    f">>> **Durasi AFK:** {waktu}"
                ),
                color=self.random_color()
            )

            await message.channel.send(
                embed=embed
            )

        # ================= CEK USER AFK =================
        for user in message.mentions:

            data = await db.fetchone(
                """
                SELECT *
                FROM afk
                WHERE user_id=%s
                AND guild_id=%s
                """,
                user.id,
                message.guild.id
            )

            if data:

                afk_time = (
                    datetime.utcnow() - data["afk_since"]
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