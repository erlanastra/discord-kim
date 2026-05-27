import discord
from discord.ext import commands
from datetime import datetime
import random

class AFK(commands.Cog):
    """AFK multi-server dengan durasi + nickname otomatis"""

    def __init__(self, bot):
        self.bot = bot

        # Format:
        # {
        #   guild_id: {
        #       user_id: {
        #           "reason": str,
        #           "since": datetime,
        #           "nick": original_nick
        #       }
        #   }
        # }
        self.afk_users = {}

    def random_color(self):
        return discord.Color(random.randint(0, 0xFFFFFF))

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

    @commands.command(name="afk")
    async def afk(self, ctx, *, reason: str = "AFK"):
        user = ctx.author
        guild_id = ctx.guild.id

        if guild_id not in self.afk_users:
            self.afk_users[guild_id] = {}

        # Kalau udah AFK
        if user.id in self.afk_users[guild_id]:
            embed = discord.Embed(
                title="❌ AFK Gagal",
                description=f"{user.mention}, kamu sudah AFK sebelumnya!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        # Simpan data AFK
        original_nick = user.display_name

        self.afk_users[guild_id][user.id] = {
            "reason": reason,
            "since": datetime.utcnow(),
            "nick": original_nick
        }

        # Tambah [AFK]
        try:
            await user.edit(nick=f"[AFK] {original_nick}")
        except discord.Forbidden:
            pass
        except:
            pass

        embed = discord.Embed(
            title="🌙 AFK Status Aktif",
            description=(
                f"{user.mention} telah mengaktifkan status AFK.\n"
                f"**Alasan**: {reason}"
            ),
            color=self.random_color()
        )

        embed.set_footer(text="Status akan otomatis nonaktif saat kamu kembali")

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if not message.guild:
            return

        guild_id = message.guild.id

        if guild_id not in self.afk_users:
            return

        # Biar command !afk gak langsung remove
        if message.content.startswith("!afk"):
            return

        # =========================
        # BALIK DARI AFK
        # =========================
        if message.author.id in self.afk_users[guild_id]:

            data = self.afk_users[guild_id].pop(message.author.id)

            afk_time = (
                datetime.utcnow() - data["since"]
            ).total_seconds()

            waktu = self.format_time(int(afk_time))

            # Balikin nickname
            try:
                await message.author.edit(nick=data["nick"])
            except discord.Forbidden:
                pass
            except:
                pass

            embed = discord.Embed(
                title="👋 Welcome Back",
                description=(
                    f"{message.author.mention} telah kembali.\n"
                    f"**Durasi AFK**: {waktu}"
                ),
                color=self.random_color()
            )

            await message.channel.send(embed=embed)

        # =========================
        # CEK USER AFK YANG DI MENTION
        # =========================
        for user in message.mentions:

            if user.id in self.afk_users[guild_id]:

                data = self.afk_users[guild_id][user.id]

                afk_time = (
                    datetime.utcnow() - data["since"]
                ).total_seconds()

                waktu = self.format_time(int(afk_time))

                embed = discord.Embed(
                    title="⚠️ Pengguna Sedang AFK",
                    description=(
                        f"{user.mention} saat ini sedang sibuk.\n"
                        f"**Alasan**: {data['reason']}\n"
                        f"**Sejak**: {waktu} yang lalu"
                    ),
                    color=self.random_color()
                )

                await message.channel.send(embed=embed)

        await self.bot.process_commands(message)

# Setup cog
async def setup(bot):
    await bot.add_cog(AFK(bot))