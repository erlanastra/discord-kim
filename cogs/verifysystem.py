import discord
from discord.ext import commands
import requests
import re

# ================= CONFIG =================
VERIF_CHANNEL_ID = 1486913580161962054
STAFF_CHANNEL_ID = 1508683781698224241
DATA_MEMBER_CHANNEL_ID = 1486981828798709930

# ROLE MEMBER
MEMBER_ROLE_ID = 1453095603008442510

# ROLE SISWA / SISWI
SISWA_ROLE_ID = 1453246082405503036
SISWI_ROLE_ID = 1453246187636396032

# ROLE UMUR — GANTI 0 DENGAN ID ROLE DISCORD KAMU
AGE_15_18_ROLE_ID = 1545088940413943829
AGE_19_22_ROLE_ID = 1545089256270078043
AGE_23_PLUS_ROLE_ID = 1545089354765049936

# ROLE NON VERIF
NONVERIF_ROLE_ID = 1504467138440597604


# ================= FOLLOWER CHECK =================
def get_instagram_followers(username):

    try:
        url = f"https://www.instagram.com/{username}/"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

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

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

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


# ================= VERIFY MODAL =================
class VerifyModal(
    discord.ui.Modal,
    title="Form Verifikasi"
):

    nama = discord.ui.TextInput(
        label="Nama"
    )

    asal = discord.ui.TextInput(
        label="Asal"
    )

    username = discord.ui.TextInput(
        label="Username Medsos",
        placeholder="@username"
    )

    def __init__(self, bot, platform, umur, gender):

        super().__init__()

        self.bot = bot
        self.platform = platform
        self.umur = umur
        self.gender = gender

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        # ================= VALIDASI =================
        if "@" not in self.username.value:

            return await interaction.response.send_message(
                "⚠️ Username harus pakai @",
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
                name="Umur",
                value=self.umur,
                inline=True
            )

            embed.add_field(
                name="Gender",
                value=self.gender,
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

            embed.add_field(
                name="Profile",
                value=link,
                inline=False
            )

            embed.set_thumbnail(
                url=interaction.user.display_avatar.url
            )

            view = VerifyView(
                self.bot,
                interaction.user.id,
                self.nama.value,
                self.asal.value,
                self.umur,
                self.gender,
                medsos_final,
                followers,
                link
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
class PlatformSelect(discord.ui.Select):

    def __init__(self):
        options = [
            discord.SelectOption(
                label="Instagram",
                value="IG",
                emoji="📸"
            ),
            discord.SelectOption(
                label="TikTok",
                value="TikTok",
                emoji="🎵"
            )
        ]

        super().__init__(
            placeholder="Pilih platform medsos",
            options=options,
            custom_id="verify_platform_select"
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.platform = self.values[0]
        await interaction.response.defer()


class AgeSelect(discord.ui.Select):

    def __init__(self):
        options = [
            discord.SelectOption(
                label="15–18 Tahun",
                value="15-18",
                emoji="🎂"
            ),
            discord.SelectOption(
                label="19–22 Tahun",
                value="19-22",
                emoji="🎂"
            ),
            discord.SelectOption(
                label="23+ Tahun",
                value="23+",
                emoji="🎂"
            )
        ]

        super().__init__(
            placeholder="Pilih rentang umur",
            options=options,
            custom_id="verify_age_select"
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.umur = self.values[0]
        await interaction.response.defer()


class GenderSelect(discord.ui.Select):

    def __init__(self):
        options = [
            discord.SelectOption(
                label="Siswa",
                value="L",
                description="Pilih jika kamu laki-laki",
                emoji="👦"
            ),
            discord.SelectOption(
                label="Siswi",
                value="P",
                description="Pilih jika kamu perempuan",
                emoji="👧"
            )
        ]

        super().__init__(
            placeholder="Pilih gender",
            options=options,
            custom_id="verify_gender_select"
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.gender = self.values[0]
        await interaction.response.defer()


class VerifyButton(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)

        self.bot = bot
        self.platform = None
        self.umur = None
        self.gender = None

        self.add_item(PlatformSelect())
        self.add_item(AgeSelect())
        self.add_item(GenderSelect())

    @discord.ui.button(
        label="Lanjut Isi Data",
        style=discord.ButtonStyle.primary,
        emoji="📋",
        custom_id="verify_continue_button"
    )
    async def lanjut(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not self.platform:
            return await interaction.response.send_message(
                "⚠️ Pilih platform medsos dulu!",
                ephemeral=True
            )

        if not self.umur:
            return await interaction.response.send_message(
                "⚠️ Pilih rentang umur dulu!",
                ephemeral=True
            )

        if not self.gender:
            return await interaction.response.send_message(
                "⚠️ Pilih gender dulu!",
                ephemeral=True
            )

        await interaction.response.send_modal(
            VerifyModal(
                self.bot,
                self.platform,
                self.umur,
                self.gender
            )
        )


# ================= APPROVE / DENY =================
class VerifyView(discord.ui.View):

    def __init__(
        self,
        bot,
        user_id,
        nama,
        asal,
        umur,
        gender,
        medsos,
        followers,
        link
    ):

        super().__init__(timeout=None)

        self.bot = bot
        self.user_id = user_id

        self.nama = nama
        self.asal = asal
        self.umur = umur
        self.gender = gender
        self.medsos = medsos
        self.followers = followers
        self.link = link

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="verify_approve_button"
    )

    async def approve(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        member = interaction.guild.get_member(
            int(self.user_id)
        )

        member_role = interaction.guild.get_role(
            MEMBER_ROLE_ID
        )

        siswa_role = interaction.guild.get_role(
            SISWA_ROLE_ID
        )

        siswi_role = interaction.guild.get_role(
            SISWI_ROLE_ID
        )

        age_15_18_role = interaction.guild.get_role(
            AGE_15_18_ROLE_ID
        ) if AGE_15_18_ROLE_ID else None

        age_19_22_role = interaction.guild.get_role(
            AGE_19_22_ROLE_ID
        ) if AGE_19_22_ROLE_ID else None

        age_23_plus_role = interaction.guild.get_role(
            AGE_23_PLUS_ROLE_ID
        ) if AGE_23_PLUS_ROLE_ID else None

        # ================= ROLE ================
        # ================= ROLE =================
        if member:

            roles_to_add = []

            # Role utama
            if member_role:
                roles_to_add.append(member_role)

            # Gender role
            if self.gender == "L" and siswa_role:
                roles_to_add.append(siswa_role)

            elif self.gender == "P" and siswi_role:
                roles_to_add.append(siswi_role)

            # Role umur
            age_roles = {
                "15-18": age_15_18_role,
                "19-22": age_19_22_role,
                "23+": age_23_plus_role
            }

            age_role = age_roles.get(self.umur)

            if age_role:
                roles_to_add.append(age_role)

            # Tambahkan role baru
            if roles_to_add:
                await member.add_roles(*roles_to_add)

            # ================= REMOVE NONVERIF =================
            nonverif_role = interaction.guild.get_role(
                NONVERIF_ROLE_ID
            )

            if nonverif_role and nonverif_role in member.roles:
                await member.remove_roles(nonverif_role)

            try:
                await member.send(
                    "✅ Verifikasi kamu disetujui!"
                )
            except:
                pass

        # ================= DATA MEMBER =================
        data_channel = interaction.client.get_channel(
            DATA_MEMBER_CHANNEL_ID
        )

        if data_channel:

            data_embed = discord.Embed(
                title="📦 Data Member Baru",
                color=0x57F287
            )

            data_embed.add_field(
                name="User",
                value=(
                    f"{member} "
                    f"({self.user_id})"
                ),
                inline=False
            )

            data_embed.add_field(
                name="Nama",
                value=self.nama,
                inline=True
            )

            data_embed.add_field(
                name="Asal",
                value=self.asal,
                inline=True
            )

            data_embed.add_field(
                name="Umur",
                value=self.umur or "Tidak diisi",
                inline=True
            )

            data_embed.add_field(
                name="Gender",
                value=self.gender,
                inline=True
            )

            data_embed.add_field(
                name="Medsos",
                value=self.medsos,
                inline=False
            )

            data_embed.add_field(
                name="Followers",
                value=self.followers,
                inline=True
            )

            data_embed.add_field(
                name="Profile",
                value=self.link,
                inline=False
            )

            data_embed.add_field(
                name="Approved By",
                value=interaction.user.mention,
                inline=False
            )

            data_embed.set_thumbnail(
                url=member.display_avatar.url
            )

            await data_channel.send(
                content=(
                    f"**Username:** "
                    f"{member.name}"
                ),
                embed=data_embed
            )

        # ================= EDIT STAFF EMBED =================
        embed = interaction.message.embeds[0]

        embed.color = 0x57F287

        embed.add_field(
            name="Status",
            value=(
                f"✅ Approved by "
                f"{interaction.user.mention}"
            ),
            inline=False
        )

        await interaction.message.edit(
            embed=embed,
            view=None
        )

        await interaction.response.send_message(
            "✅ Verifikasi berhasil diapprove",
            ephemeral=True
        )

    @discord.ui.button(
        label="Deny",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="verify_deny_button"
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

        embed = interaction.message.embeds[0]

        embed.color = 0xED4245

        embed.add_field(
            name="Status",
            value=(
                f"❌ Denied by "
                f"{interaction.user.mention}"
            ),
            inline=False
        )

        await interaction.message.edit(
            embed=embed,
            view=None
        )

        await interaction.response.send_message(
            "❌ Verifikasi berhasil dideny",
            ephemeral=True
        )


# ================= MAIN COG =================
class VerifySystem(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    @commands.command(name="dataverif")
    async def verifikasi(self, ctx):

        if ctx.channel.id != VERIF_CHANNEL_ID:
            return

        embed = discord.Embed(
            title="📋 Verifikasi",
            description=(
                "Pilih platform lalu klik tombol "
                "untuk isi data."
            ),
            color=0x00ffcc
        )

        embed.add_field(
            name="Informasi",
            value=(
                "• Data hanya dilihat staff\n"
                "• Umur & gender dipilih melalui opsi\n"
                "• Role umur & gender otomatis diberikan\n"
                "• Verifikasi untuk keamanan server"
            ),
            inline=False
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