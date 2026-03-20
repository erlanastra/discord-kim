import discord
from discord.ext import commands
from discord import app_commands
import aiomysql
import time
import random

# ================= CONFIG =================
CONFESSION_CHANNEL_ID = 1470668209098068073
ADMIN_ID = 1169643619049799740

COOLDOWN = 600  # 10 menit

def random_color():
    return discord.Color.from_rgb(
        random.randint(80, 200),
        random.randint(80, 200),
        random.randint(80, 200)
    )

# ================= TOXIC FILTER =================
TOXIC_WORDS = [
    "bodoh","tolol","anjing","babi","kontol","memek",
    "anjg","ajg","njing","jing","4njing","4nj1ng",
    "nj1ng","4jg","j1ng","b4b1","b4bi","bab1",
    "m3m3k","mmk","m3mek","mem3k","mek",
    "kntl","kontl","kintil","kntol","ntol",
    "tlol","toll"
]

def contains_toxic(text):
    text = text.lower()
    return any(word in text for word in TOXIC_WORDS)

# ================= COG =================
class Confession(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pool = None

    async def cog_load(self):
        await self.init_db()

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
                    CREATE TABLE IF NOT EXISTS confessions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id VARCHAR(50),
                        message TEXT,
                        created_at DOUBLE
                    )
                """)

                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS confession_cooldown (
                        user_id VARCHAR(50) PRIMARY KEY,
                        last_used DOUBLE
                    )
                """)

    confess = app_commands.Group(
        name="confess",
        description="🕊️ Kirim confession anonim"
    )

    # ================= SEND =================
    @confess.command(name="send", description="Kirim confession anonim")
    async def send_confession(self, interaction: discord.Interaction, pesan: str):

        await interaction.response.defer(ephemeral=True)  # 🔥 WAJIB

        if not self.pool:
            return await interaction.response.send_message("Database belum siap.", ephemeral=True)

        uid = str(interaction.user.id)
        now = time.time()

        admin = await self.bot.fetch_user(ADMIN_ID)

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:

                # COOLDOWN
                await cursor.execute(
                    "SELECT last_used FROM confession_cooldown WHERE user_id=%s",
                    (uid,)
                )
                row = await cursor.fetchone()

                if row and now - row["last_used"] < COOLDOWN:
                    return await interaction.followup.send(
                        "⏳ Tunggu beberapa menit sebelum mengirim lagi.",
                        ephemeral=True
                    )

                # PANJANG
                if len(pesan) > 700:
                    return await interaction.followup.send(
                        "❌ Maksimal 700 karakter.",
                        ephemeral=True
                    )

                # TOXIC
                if contains_toxic(pesan):
                    await interaction.followup.send(
                        "❌ Pesan mengandung kata yang tidak diperbolehkan.",
                        ephemeral=True
                    )

                    await admin.send(
                        f"⚠️ **Percobaan Confession Terlarang**\n"
                        f"👤 User: {interaction.user}\n"
                        f"🆔 ID: {interaction.user.id}\n"
                        f"💬 Pesan:\n{pesan}"
                    )
                    return

                # INSERT CONFESSION
                await cursor.execute("""
                    INSERT INTO confessions (user_id, message, created_at)
                    VALUES (%s, %s, %s)
                """, (uid, pesan, now))

                confession_id = cursor.lastrowid

                # UPDATE COOLDOWN
                await cursor.execute("""
                    INSERT INTO confession_cooldown (user_id, last_used)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE last_used=%s
                """, (uid, now, now))

        # ================= CHANNEL (FIX UTAMA) =================
        channel = self.bot.get_channel(CONFESSION_CHANNEL_ID)

        if not channel:
            try:
                channel = await self.bot.fetch_channel(CONFESSION_CHANNEL_ID)
            except:
                return await interaction.followup.send(
                    "❌ Channel confession tidak ditemukan atau bot tidak punya akses.",
                    ephemeral=True
                )

        # EMBED (TIDAK DIUBAH)
        embed = discord.Embed(
            title=f"🕊️ Anonymous Confession #{confession_id}",
            description=pesan,
            color=random_color()
        )
        embed.set_footer(text="Identitas pengirim dirahasiakan • Be kind 🤍")

        msg = await channel.send(embed=embed)
        await msg.add_reaction("❤️")
        await msg.add_reaction("🤍")
        await msg.add_reaction("🫂")

        # ================= ADMIN LOG =================
        log_embed = discord.Embed(
            title=f"📩 Confession #{confession_id} terkirim",
            description=pesan,
            color=discord.Color.orange()
        )
        log_embed.set_footer(text=f"User ID: {interaction.user.id}")
        await admin.send(embed=log_embed)

        private_embed = discord.Embed(
            title=f"🔒 Confession #{confession_id} (PRIVATE)",
            description=pesan,
            color=discord.Color.red()
        )
        private_embed.set_footer(
            text=f"Pengirim: {interaction.user} • ID: {interaction.user.id}"
        )
        await admin.send(embed=private_embed)

        await interaction.followup.send(
            "✅ Confession berhasil dikirim secara anonim.",
            ephemeral=True
        )

    # ================= RULES =================
    @confess.command(name="rules", description="Aturan confession")
    async def rules(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📌 Aturan Confession",
            description=(
                "• ❌ Tidak mengandung SARA / doxxing\n"
                "• ❌ Tidak menyebut nama orang\n"
                "• ❌ Tidak spam\n"
                "• ✅ Saling menghargai\n\n"
                "⚠️ Pelanggaran bisa ditindak admin"
            ),
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Confession(bot))