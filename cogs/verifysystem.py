import discord
from discord.ext import commands
import aiomysql
import time
import requests
import re

# ================= CONFIG =================
VERIF_CHANNEL_ID = 1486913580161962054
STAFF_CHANNEL_ID = 1486981828798709930
MEMBER_ROLE_ID = 1453095603008442510

# ================= FOLLOWER CHECK =================
def get_instagram_followers(username):
    try:
        url = f"https://www.instagram.com/{username}/"
        headers = {"User-Agent": "Mozilla/5.0"}

        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            return "Tidak ditemukan"

        match = re.search(r'"edge_followed_by":{"count":(\d+)}', res.text)
        if match:
            return f"{int(match.group(1)):,}"
        return "Hidden"
    except:
        return "Error"


def get_tiktok_followers(username):
    try:
        url = f"https://www.tiktok.com/@{username}"
        headers = {"User-Agent": "Mozilla/5.0"}

        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            return "Tidak ditemukan"

        match = re.search(r'"followerCount":(\d+)', res.text)
        if match:
            return f"{int(match.group(1)):,}"
        return "Hidden"
    except:
        return "Error"

# ================= DROPDOWN =================
class PlatformSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Instagram", value="IG"),
            discord.SelectOption(label="TikTok", value="TikTok")
        ]
        super().__init__(placeholder="Pilih platform medsos", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.platform = self.values[0]
        await interaction.response.defer()

# ================= MODAL =================
class VerifyModal(discord.ui.Modal, title="Form Verifikasi"):

    nama = discord.ui.TextInput(label="Nama")
    asal = discord.ui.TextInput(label="Asal")
    umur = discord.ui.TextInput(label="Umur (opsional)", required=False)
    gender = discord.ui.TextInput(
        label="Gender (L/P)",
        placeholder="Contoh: L atau P",
        max_length=1
    )
    username = discord.ui.TextInput(label="Username Medsos", placeholder="@username")

    def __init__(self, bot, platform):
        super().__init__()
        self.bot = bot
        self.platform = platform

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not hasattr(self.bot, "pool"):
                return await interaction.response.send_message("❌ Database belum siap.", ephemeral=True)

            # ================= VALIDASI =================
            if not self.nama.value or not self.asal.value or not self.username.value:
                return await interaction.response.send_message("⚠️ Data wajib diisi!", ephemeral=True)

            if "@" not in self.username.value:
                return await interaction.response.send_message("⚠️ Username harus pakai @", ephemeral=True)

            if self.umur.value and not self.umur.value.isdigit():
                return await interaction.response.send_message("⚠️ Umur harus angka!", ephemeral=True)

            if self.gender.value.upper() not in ["L", "P"]:
                return await interaction.response.send_message("⚠️ Gender hanya boleh L atau P!", ephemeral=True)

            uid = str(interaction.user.id)
            now = time.time()

            username_clean = self.username.value.replace("@", "")
            medsos_final = f"{self.platform} | @{username_clean}"

            # ================= FOLLOWER =================
            followers = "Tidak dicek"
            link = ""

            if self.platform == "IG":
                followers = get_instagram_followers(username_clean)
                link = f"https://instagram.com/{username_clean}"
            elif self.platform == "TikTok":
                followers = get_tiktok_followers(username_clean)
                link = f"https://tiktok.com/@{username_clean}"

            async with self.bot.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:

                    # CEK DUPLICATE
                    await cursor.execute("SELECT * FROM verifications WHERE user_id=%s", (uid,))
                    if await cursor.fetchone():
                        return await interaction.response.send_message("⚠️ Kamu sudah verifikasi.", ephemeral=True)

                    # INSERT
                    await cursor.execute("""
                        INSERT INTO verifications 
                        (user_id, nama, asal, umur, gender, medsos, status, created_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (
                        uid,
                        self.nama.value,
                        self.asal.value,
                        self.umur.value,
                        self.gender.value.upper(),
                        medsos_final,
                        "pending",
                        now
                    ))

            # ================= STAFF EMBED =================
            staff_channel = interaction.client.get_channel(STAFF_CHANNEL_ID)

            if staff_channel:
                gender_display = "👦 Laki-laki" if self.gender.value.upper() == "L" else "👧 Perempuan"

                embed = discord.Embed(title="📥 Verifikasi Masuk", color=0x00ffcc)

                embed.add_field(name="User", value=interaction.user.mention, inline=False)
                embed.add_field(name="Nama", value=self.nama.value, inline=True)
                embed.add_field(name="Asal", value=self.asal.value, inline=True)
                embed.add_field(name="Umur", value=self.umur.value or "Tidak diisi", inline=True)
                embed.add_field(name="Gender", value=gender_display, inline=True)
                embed.add_field(name="Medsos", value=medsos_final, inline=False)
                embed.add_field(name="Followers", value=followers, inline=True)
                embed.add_field(name="Profile", value=f"[🔗 Klik disini]({link})", inline=False)

                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                embed.set_footer(text=f"User ID: {interaction.user.id}")

                view = VerifyView(self.bot, interaction.user.id)
                await staff_channel.send(embed=embed, view=view)

            await interaction.response.send_message(
                "✅ Data berhasil dikirim! Tunggu staff ya ⏳",
                ephemeral=True
            )

        except Exception as e:
            print("ERROR:", e)
            await interaction.response.send_message("❌ Terjadi error.", ephemeral=True)

# ================= BUTTON VIEW =================
class VerifyButton(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.platform = None
        self.add_item(PlatformSelect())

    @discord.ui.button(label="Lanjut Isi Data", style=discord.ButtonStyle.primary)
    async def lanjut(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not self.platform:
            return await interaction.response.send_message("⚠️ Pilih platform dulu!", ephemeral=True)

        await interaction.response.send_modal(
            VerifyModal(self.bot, self.platform)
        )

# ================= APPROVE / DENY =================
class VerifyView(discord.ui.View):
    def __init__(self, bot, user_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = user_id

    async def update_status(self, status):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE verifications SET status=%s WHERE user_id=%s",
                    (status, str(self.user_id))
                )

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):

        member = interaction.guild.get_member(int(self.user_id))
        role = interaction.guild.get_role(MEMBER_ROLE_ID)

        if member and role:
            await member.add_roles(role)
            try:
                await member.send("✅ Verifikasi kamu disetujui!")
            except:
                pass

        await self.update_status("approved")

        await interaction.response.send_message("✅ Approved", ephemeral=True)

        self.disable_all_items()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):

        member = interaction.guild.get_member(int(self.user_id))

        if member:
            try:
                await member.send("❌ Verifikasi ditolak.")
            except:
                pass

        await self.update_status("denied")

        await interaction.response.send_message("❌ Denied", ephemeral=True)

        self.disable_all_items()
        await interaction.message.edit(view=self)

# ================= MAIN COG =================
class VerifySystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await self.init_db()

    async def init_db(self):
        if hasattr(self.bot, "pool"):
            return

        self.bot.pool = await aiomysql.create_pool(
            host="sql5.freesqldatabase.com",
            port=3306,
            user="sql5820722",
            password="m6GjypbQk3",
            db="sql5820722",
            autocommit=True
        )

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS verifications (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id VARCHAR(50),
                        nama TEXT,
                        asal TEXT,
                        umur TEXT,
                        gender VARCHAR(5),
                        medsos TEXT,
                        status VARCHAR(20),
                        created_at DOUBLE
                    )
                """)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.channel.id != VERIF_CHANNEL_ID:
            return

        if message.content.lower() == "#verifikasi":

            embed = discord.Embed(
                title="📋 Verifikasi",
                description="Pilih platform lalu klik tombol untuk isi data",
                color=0x00ffcc
            )

            await message.reply(embed=embed, view=VerifyButton(self.bot))

        await self.bot.process_commands(message)

async def setup(bot):
    await bot.add_cog(VerifySystem(bot))