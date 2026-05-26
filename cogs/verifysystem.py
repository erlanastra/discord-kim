import discord
from discord.ext import commands
import requests
import re

# ================= CONFIG =================
VERIF_CHANNEL_ID = 1486913580161962054
STAFF_CHANNEL_ID = 1486981828798709930
DATA_MEMBER_CHANNEL_ID = 123456789012345678  # GANTI
MEMBER_ROLE_ID = 1453095603008442510

# ================= FOLLOWER CHECK =================
def get_instagram_followers(username):
    try:
        url = f"https://www.instagram.com/{username}/"
        headers = {"User-Agent": "Mozilla/5.0"}

        res = requests.get(url, headers=headers)

        if res.status_code != 200:
            return "Tidak ditemukan"

        match = re.search(
            r'"edge_followed_by":{"count":(\d+)}',
            res.text
        )

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

        match = re.search(
            r'"followerCount":(\d+)',
            res.text
        )

        if match:
            return f"{int(match.group(1)):,}"

        return "Hidden"

    except:
        return "Error"

# ================= PLATFORM SELECT =================
class PlatformSelect(discord.ui.Select):

    def __init__(self):

        options = [
            discord.SelectOption(
                label="Instagram",
                value="IG"
            ),

            discord.SelectOption(
                label="TikTok",
                value="TikTok"
            )
        ]

        super().__init__(
            placeholder="Pilih platform medsos",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        self.view.platform = self.values[0]

        await interaction.response.defer()

# ================= VERIFY MODAL =================
class VerifyModal(discord.ui.Modal, title="Form Verifikasi"):

    nama = discord.ui.TextInput(label="Nama")
    asal = discord.ui.TextInput(label="Asal")

    umur = discord.ui.TextInput(
        label="Umur (opsional)",
        required=False
    )

    gender = discord.ui.TextInput(
        label="Gender (L/P)",
        placeholder="L atau P",
        max_length=1
    )

    username = discord.ui.TextInput(
        label="Username Medsos",
        placeholder="@username"
    )

    def __init__(self, bot, platform):

        super().__init__()

        self.bot = bot
        self.platform = platform

    async def on_submit(self, interaction: discord.Interaction):

        # ================= VALIDASI =================
        if "@" not in self.username.value:

            return await interaction.response.send_message(
                "⚠️ Username harus pakai @",
                ephemeral=True
            )

        if self.gender.value.upper() not in ["L", "P"]:

            return await interaction.response.send_message(
                "⚠️ Gender hanya boleh L atau P!",
                ephemeral=True
            )

        username_clean = self.username.value.replace("@", "")

        medsos_final = (
            f"{self.platform} | @{username_clean}"
        )

        followers = "Tidak dicek"
        link = ""

        # ================= FOLLOWERS =================
        if self.platform == "IG":

            followers = get_instagram_followers(
                username_clean
            )

            link = (
                f"https://instagram.com/{username_clean}"
            )

        elif self.platform == "TikTok":

            followers = get_tiktok_followers(
                username_clean
            )

            link = (
                f"https://tiktok.com/@{username_clean}"
            )

        # ================= DATA MEMBER CHANNEL =================
        data_channel = interaction.client.get_channel(
            DATA_MEMBER_CHANNEL_ID
        )

        if data_channel:

            data_embed = discord.Embed(
                title="📦 Data Member Baru",
                color=0x00ffaa
            )

            data_embed.add_field(
                name="User",
                value=(
                    f"{interaction.user} "
                    f"({interaction.user.id})"
                ),
                inline=False
            )

            data_embed.add_field(
                name="Nama",
                value=self.nama.value,
                inline=True
            )

            data_embed.add_field(
                name="Asal",
                value=self.asal.value,
                inline=True
            )

            data_embed.add_field(
                name="Umur",
                value=self.umur.value or "Tidak diisi",
                inline=True
            )

            data_embed.add_field(
                name="Gender",
                value=self.gender.value.upper(),
                inline=True
            )

            data_embed.add_field(
                name="Medsos",
                value=medsos_final,
                inline=False
            )

            data_embed.add_field(
                name="Followers",
                value=followers,
                inline=True
            )

            data_embed.add_field(
                name="Profile",
                value=link,
                inline=False
            )

            data_embed.set_thumbnail(
                url=interaction.user.display_avatar.url
            )

            await data_channel.send(
                embed=data_embed
            )

        # ================= STAFF CHANNEL =================
        staff_channel = interaction.client.get_channel(
            STAFF_CHANNEL_ID
        )

        if staff_channel:

            embed = discord.Embed(
                title="📥 Verifikasi Masuk",
                color=0x00ffcc
            )

            embed.add_field(
                name="User",
                value=interaction.user.mention,
                inline=False
            )

            embed.add_field(
                name="Nama",
                value=self.nama.value,
                inline=True
            )

            embed.add_field(
                name="Asal",
                value=self.asal.value,
                inline=True
            )

            embed.add_field(
                name="Medsos",
                value=medsos_final,
                inline=False
            )

            embed.add_field(
                name="Followers",
                value=followers,
                inline=True
            )

            embed.set_thumbnail(
                url=interaction.user.display_avatar.url
            )

            view = VerifyView(
                self.bot,
                interaction.user.id
            )

            await staff_channel.send(
                embed=embed,
                view=view
            )

        await interaction.response.send_message(
            "✅ Data berhasil dikirim!",
            ephemeral=True
        )

# ================= VERIFY BUTTON =================
class VerifyButton(discord.ui.View):

    def __init__(self, bot):

        super().__init__(timeout=None)

        self.bot = bot
        self.platform = None

        self.add_item(PlatformSelect())

    @discord.ui.button(
        label="Lanjut Isi Data",
        style=discord.ButtonStyle.primary
    )

    async def lanjut(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not self.platform:

            return await interaction.response.send_message(
                "⚠️ Pilih platform dulu!",
                ephemeral=True
            )

        await interaction.response.send_modal(
            VerifyModal(
                self.bot,
                self.platform
            )
        )

# ================= APPROVE / DENY =================
class VerifyView(discord.ui.View):

    def __init__(self, bot, user_id):

        super().__init__(timeout=None)

        self.bot = bot
        self.user_id = user_id

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success
    )

    async def approve(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        member = interaction.guild.get_member(
            int(self.user_id)
        )

        role = interaction.guild.get_role(
            MEMBER_ROLE_ID
        )

        if member and role:

            await member.add_roles(role)

            try:
                await member.send(
                    "✅ Verifikasi kamu disetujui!"
                )
            except:
                pass

        await interaction.response.send_message(
            "✅ Approved",
            ephemeral=True
        )

        self.disable_all_items()

        await interaction.message.edit(
            view=self
        )

    @discord.ui.button(
        label="Deny",
        style=discord.ButtonStyle.danger
    )

    async def deny(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        member = interaction.guild.get_member(
            int(self.user_id)
        )

        if member:

            try:
                await member.send(
                    "❌ Verifikasi ditolak."
                )
            except:
                pass

        await interaction.response.send_message(
            "❌ Denied",
            ephemeral=True
        )

        self.disable_all_items()

        await interaction.message.edit(
            view=self
        )

# ================= MAIN COG =================
class VerifySystem(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    @commands.command(name="verifikasi")
    async def verifikasi(self, ctx):

        if ctx.channel.id != VERIF_CHANNEL_ID:
            return

        embed = discord.Embed(
            title="📋 Verifikasi",
            description=(
                "Pilih platform lalu klik tombol "
                "untuk isi data"
            ),
            color=0x00ffcc
        )

        await ctx.send(
            embed=embed,
            view=VerifyButton(self.bot)
        )

# ================= SETUP =================
async def setup(bot):

    await bot.add_cog(
        VerifySystem(bot)
    )