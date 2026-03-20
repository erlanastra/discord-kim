import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiomysql
from datetime import datetime
import random

# ================= CONFIG =================
BIRTHDAY_CHANNEL_ID = 1470667479935352878  # ⬅️ GANTI
DEVELOPER_ROLE_ID = 1484499055198474311   # ⬅️ GANTI

def random_color():
    return discord.Color.from_rgb(
        random.randint(50,255),
        random.randint(50,255),
        random.randint(50,255)
    )

class Birthday(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pool = None
        self.check_birthday.start()

    async def cog_load(self):
        await self.init_db()

    def cog_unload(self):
        self.check_birthday.cancel()
        if self.pool:
            self.pool.close()

    # ================= DATABASE =================
    async def init_db(self):
        self.pool = await aiomysql.create_pool(
            host="sql5.freesqldatabase.com",
            port=3306,
            user="sql5820722",
            password="m6GjypbQk3",
            db="sql5820722",
            autocommit=True
        )

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS birthdays (
                        user_id VARCHAR(50) PRIMARY KEY,
                        date VARCHAR(10),
                        last_sent VARCHAR(10)
                    )
                """)

    # ================= GROUP =================
    birthday = app_commands.Group(
        name="birthday",
        description="🎂 Sistem ulang tahun otomatis"
    )

    # ================= SET =================
    @birthday.command(name="set", description="Set ulang tahun (DD-MM)")
    async def set_birthday(self, interaction: discord.Interaction, tanggal: str):
        try:
            datetime.strptime(tanggal, "%d-%m")
        except ValueError:
            return await interaction.response.send_message(
                "❌ Format salah. Gunakan **DD-MM** (contoh: 12-05)",
                ephemeral=True
            )

        if not self.pool:
            return await interaction.response.send_message("Database belum siap.", ephemeral=True)

        uid = str(interaction.user.id)

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO birthdays (user_id, date, last_sent)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE date=%s
                """, (uid, tanggal, None, tanggal))

        embed = discord.Embed(
            title="🎂 Birthday Saved!",
            description=f"Ulang tahun kamu disimpan pada **{tanggal}** 🎉",
            color=random_color()
        )
        embed.set_footer(text="Bot Birthday • Data tersimpan aman")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ================= REMOVE =================
    @birthday.command(name="remove", description="Hapus data ulang tahun")
    async def remove_birthday(self, interaction: discord.Interaction):
        if not self.pool:
            return await interaction.response.send_message("Database belum siap.", ephemeral=True)

        uid = str(interaction.user.id)

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("DELETE FROM birthdays WHERE user_id=%s", (uid,))
                if cursor.rowcount == 0:
                    return await interaction.response.send_message(
                        "⚠️ Kamu belum menyimpan ulang tahun.",
                        ephemeral=True
                    )

        await interaction.response.send_message(
            "✅ Data ulang tahun berhasil dihapus.",
            ephemeral=True
        )

    # ================= LIST =================
    @birthday.command(name="list", description="Daftar ulang tahun (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_birthday(self, interaction: discord.Interaction):
        if not self.pool:
            return await interaction.response.send_message("Database belum siap.")

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SELECT * FROM birthdays")
                rows = await cursor.fetchall()

        if not rows:
            return await interaction.response.send_message("📭 Belum ada data.")

        desc = ""
        for row in rows:
            member = interaction.guild.get_member(int(row["user_id"]))
            if member:
                desc += f"🎈 **{member.display_name}** — `{row['date']}`\n"

        embed = discord.Embed(
            title="🎂 Birthday List",
            description=desc,
            color=random_color()
        )
        await interaction.response.send_message(embed=embed)

    # ================= AUTO CHECK =================
    @tasks.loop(hours=24)
    async def check_birthday(self):
        if not self.pool:
            return

        today = datetime.now().strftime("%d-%m")

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SELECT * FROM birthdays")
                rows = await cursor.fetchall()

        for guild in self.bot.guilds:
            channel = guild.get_channel(BIRTHDAY_CHANNEL_ID)
            if not channel:
                continue

            for row in rows:
                if row["date"] == today and row["last_sent"] != today:
                    member = guild.get_member(int(row["user_id"]))
                    if not member:
                        continue

                    embed = discord.Embed(
                        title="🎉 HAPPY BIRTHDAY 🎉",
                        description=(
                            f"Selamat ulang tahun {member.mention} 🥳\n"
                            "Semoga panjang umur, sehat selalu, dan bahagia 💖"
                        ),
                        color=random_color()
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.set_footer(text="🎂 Birthday Bot")

                    await channel.send(content=f"🎉 @here Hari ini ulang tahun {member.mention}!",embed=embed,allowed_mentions=discord.AllowedMentions(everyone=True, users=True))

                    async with self.pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute("""
                                UPDATE birthdays
                                SET last_sent=%s
                                WHERE user_id=%s
                            """, (today, row["user_id"]))

    # ================= TEST (DEV ONLY) =================
    @birthday.command(name="test", description="Test ulang tahun (Developer only)")
    async def test_birthday(self, interaction: discord.Interaction, member: discord.Member = None):

        # cek role developer pakai ID
        if not any(role.id == DEVELOPER_ROLE_ID for role in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ Kamu tidak punya akses.",
                ephemeral=True
            )

        target = member or interaction.user
        channel = interaction.guild.get_channel(BIRTHDAY_CHANNEL_ID)

        if not channel:
            return await interaction.response.send_message(
                "❌ Channel tidak ditemukan.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="🎉 HAPPY BIRTHDAY 🎉",
            description=(
                f"Selamat ulang tahun {target.mention} 🥳\n"
                "Semoga panjang umur, sehat selalu, dan bahagia 💖"
            ),
            color=random_color()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="🎂 Birthday Bot")

        await channel.send(embed=embed)

        await interaction.response.send_message(
            f"✅ Test birthday untuk {target.mention} berhasil dikirim.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Birthday(bot))