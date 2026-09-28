import discord
from discord.ext import commands
import requests
import re

# =========================================================
# CONFIG
# =========================================================

VERIF_CHANNEL_ID = 1486913580161962054

# Channel engagement / divisi yang menangani verifikasi
ENGAGEMENT_CHANNEL_ID = 1525136678442893352

# Channel penyimpanan data member setelah APPROVE
DATA_MEMBER_CHANNEL_ID = 1486981828798709930

# ROLE MEMBER
MEMBER_ROLE_ID = 1453095603008442510

# ROLE SISWA / SISWI
SISWA_ROLE_ID = 1453246082405503036
SISWI_ROLE_ID = 1453246187636396032

# ROLE UMUR
AGE_15_18_ROLE_ID = 1545088940413943829
AGE_19_22_ROLE_ID = 1545089256270078043
AGE_23_PLUS_ROLE_ID = 1545089354765049936

# ROLE NON VERIF
NONVERIF_ROLE_ID = 1504467138440597604

# Voice verifikasi nanZ
VOICE_VERIF_CHANNEL_IDS = [
    1518251174149750906,
    1523340570607616010,
    1486913650374738030,
]

# Emoji custom nanZ yang dipakai seperlunya
NANZ_ARROW_BLUE = "<a:arrowblue:1512787254312042496>"
NANZ_ARROW_PURPLE = "<a:arrowpurple:1512787191234035803>"
NANZ_LINK = "<a:link:1553688245769085099>"
NANZ_GEAR = "<a:settings:1553688352564183051>"
NANZ_QUESTION = "<a:question:1553688505929044000>"

# =========================================================
# HELPERS
# =========================================================

def channel_url(guild_id: int, channel_id: int) -> str:
    return f"https://discord.com/channels/{guild_id}/{channel_id}"


def get_instagram_followers(username):
    try:
        url = f"https://www.instagram.com/{username}/"
        headers = {"User-Agent": "Mozilla/5.0"}

        res = requests.get(url, headers=headers, timeout=10)

        if res.status_code != 200:
            return "Tidak ditemukan"

        match = re.search(
            r'"edge_followed_by":{"count":(\d+)}',
            res.text,
        )

        if match:
            return f"{int(match.group(1)):,}"

        return "Hidden"

    except Exception:
        return "Error"


def get_tiktok_followers(username):
    try:
        url = f"https://www.tiktok.com/@{username}"
        headers = {"User-Agent": "Mozilla/5.0"}

        res = requests.get(url, headers=headers, timeout=10)

        if res.status_code != 200:
            return "Tidak ditemukan"

        match = re.search(
            r'"followerCount":(\d+)',
            res.text,
        )

        if match:
            return f"{int(match.group(1)):,}"

        return "Hidden"

    except Exception:
        return "Error"


def get_verif_voice_channels(guild):
    channels = []

    for channel_id in VOICE_VERIF_CHANNEL_IDS:
        channel = guild.get_channel(channel_id)

        if isinstance(
            channel,
            (discord.VoiceChannel, discord.StageChannel),
        ):
            channels.append(channel)

    return channels


def choose_verif_voice(guild, member):
    """
    Prioritas:
    - voice yang tidak ditempati member lain
    - kalau semua berisi, kembali ke voice pertama
    """
    channels = get_verif_voice_channels(guild)

    if not channels:
        return None

    for channel in channels:
        others = [
            m for m in channel.members
            if m.id != member.id
        ]

        if not others:
            return channel

    return channels[0]


# =========================================================
# VOICE JOIN VIEW
# =========================================================

class VoiceJoinLinkView(discord.ui.View):
    def __init__(self, guild_id, channel_id, timeout=None):
        super().__init__(timeout=timeout)

        self.add_item(
            discord.ui.Button(
                label="Join Voice Verif",
                style=discord.ButtonStyle.link,
                url=channel_url(guild_id, channel_id),
            )
        )


# =========================================================
# STAFF VOICE NOTICE
# =========================================================

class StaffVoiceNoticeView(discord.ui.View):
    def __init__(self, guild_id, channel_id):
        super().__init__(timeout=None)

        self.add_item(
            discord.ui.Button(
                label="Masuk Voice",
                style=discord.ButtonStyle.link,
                url=channel_url(guild_id, channel_id),
            )
        )


# =========================================================
# MEMBER VOICE HANDLER
# =========================================================

async def send_voice_notice(interaction, target):
    guild = interaction.guild
    member = interaction.user

    engagement = interaction.client.get_channel(
        ENGAGEMENT_CHANNEL_ID
    )

    if not engagement:
        return

    embed = discord.Embed(
        title="Member Menunggu Verifikasi Voice",
        description=(
            f"{NANZ_ARROW_BLUE} {member.mention} sudah masuk ke "
            f"**{target.name}**.\n"
            f"{NANZ_ARROW_PURPLE} Staff dapat masuk ke voice tersebut "
            "untuk melakukan konfirmasi data."
        ),
        color=0x5865F2,
    )

    embed.add_field(
        name="Member",
        value=f"{member.mention}\n`{member.id}`",
        inline=True,
    )

    embed.add_field(
        name="Voice Verifikasi",
        value=f"<#{target.id}>",
        inline=True,
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    await engagement.send(
        embed=embed,
        view=StaffVoiceNoticeView(
            guild.id,
            target.id,
        ),
        allowed_mentions=discord.AllowedMentions(
            users=True
        ),
    )


async def handle_voice_verif(interaction):
    guild = interaction.guild
    member = interaction.user

    if guild is None or not isinstance(member, discord.Member):
        return await interaction.response.send_message(
            "Fitur ini hanya dapat digunakan di dalam server.",
            ephemeral=True,
        )

    target = choose_verif_voice(guild, member)

    if target is None:
        return await interaction.response.send_message(
            "Voice verifikasi tidak ditemukan. Hubungi staff.",
            ephemeral=True,
        )

    # Discord tidak mengizinkan bot membuat user yang sedang tidak
    # berada di voice tiba-tiba masuk voice. Jika user sudah berada
    # di voice, bot dapat memindahkannya.
    if member.voice and member.voice.channel:
        try:
            await member.move_to(
                target,
                reason="nanZ Verification Voice",
            )

        except discord.Forbidden:
            return await interaction.response.send_message(
                "Bot tidak memiliki izin untuk memindahkan kamu ke voice verifikasi.",
                ephemeral=True,
            )

        except discord.HTTPException:
            return await interaction.response.send_message(
                "Gagal memindahkan kamu ke voice verifikasi. Coba lagi.",
                ephemeral=True,
            )

        await send_voice_notice(
            interaction,
            target,
        )

        return await interaction.response.send_message(
            (
                f"{NANZ_ARROW_BLUE} Kamu sudah diarahkan ke "
                f"**{target.name}**.\n"
                "Silakan tunggu staff melakukan konfirmasi data."
            ),
            ephemeral=True,
        )

    # Jika user belum berada di voice, berikan link voice target.
    view = VoiceJoinLinkView(
        guild.id,
        target.id,
    )

    await interaction.response.send_message(
        (
            f"{NANZ_ARROW_BLUE} Kamu belum berada di voice.\n"
            f"Klik tombol **Join Voice Verif** di bawah untuk masuk "
            f"ke **{target.name}**."
        ),
        view=view,
        ephemeral=True,
    )


# =========================================================
# VERIFY MODAL
# =========================================================

class VerifyModal(
    discord.ui.Modal,
    title="Form Verifikasi",
):

    nama = discord.ui.TextInput(
        label="Nama",
        placeholder="Nama yang ingin digunakan di server",
        max_length=50,
    )

    asal = discord.ui.TextInput(
        label="Asal",
        placeholder="Kota / daerah asal",
        max_length=100,
    )

    username = discord.ui.TextInput(
        label="Username Medsos",
        placeholder="@username",
        max_length=100,
    )

    def __init__(
        self,
        bot,
        platform,
        umur,
        gender,
    ):
        super().__init__()

        self.bot = bot
        self.platform = platform
        self.umur = umur
        self.gender = gender

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        if "@" not in self.username.value:
            return await interaction.response.send_message(
                f"{NANZ_QUESTION} Username harus menggunakan @.",
                ephemeral=True,
            )

        username_clean = (
            self.username.value
            .replace("@", "")
            .strip()
        )

        medsos_final = (
            f"{self.platform} | @{username_clean}"
        )

        followers = "Tidak dicek"
        link = ""

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

        # =====================================================
        # NOTIF DATA KE ENGAGEMENT
        # =====================================================

        engagement = interaction.client.get_channel(
            ENGAGEMENT_CHANNEL_ID
        )

        if engagement:

            embed = discord.Embed(
                title="Data Verifikasi Baru",
                description=(
                    f"{NANZ_ARROW_BLUE} "
                    f"{interaction.user.mention} telah mengirim "
                    "data verifikasi.\n"
                    f"{NANZ_GEAR} Data menunggu konfirmasi staff "
                    "melalui voice verifikasi."
                ),
                color=0x5865F2,
            )

            embed.add_field(
                name="Member",
                value=(
                    f"{interaction.user.mention}\n"
                    f"`{interaction.user.id}`"
                ),
                inline=False,
            )

            embed.add_field(
                name="Nama",
                value=self.nama.value,
                inline=True,
            )

            embed.add_field(
                name="Asal",
                value=self.asal.value,
                inline=True,
            )

            embed.add_field(
                name="Umur",
                value=self.umur,
                inline=True,
            )

            embed.add_field(
                name="Gender",
                value=(
                    "Siswa"
                    if self.gender == "L"
                    else "Siswi"
                ),
                inline=True,
            )

            embed.add_field(
                name="Medsos",
                value=medsos_final,
                inline=False,
            )

            embed.add_field(
                name="Followers",
                value=followers,
                inline=True,
            )

            if link:
                embed.add_field(
                    name="Profile",
                    value=f"{NANZ_LINK} [Buka Profile]({link})",
                    inline=False,
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
                link,
            )

            await engagement.send(
                embed=embed,
                view=view,
                allowed_mentions=discord.AllowedMentions(
                    users=True
                ),
            )

        # =====================================================
        # RESPONSE KE MEMBER
        # =====================================================

        view = VoiceVerifyButtonView(
            self.bot
        )

        await interaction.response.send_message(
            (
                "Data verifikasi berhasil dikirim.\n\n"
                "Selanjutnya, masuk ke **Voice Verif** untuk "
                "konfirmasi langsung bersama staff."
            ),
            view=view,
            ephemeral=True,
        )


# =========================================================
# SELECT PLATFORM
# =========================================================

class PlatformSelect(discord.ui.Select):

    def __init__(self):
        options = [
            discord.SelectOption(
                label="Instagram",
                value="IG",
            ),
            discord.SelectOption(
                label="TikTok",
                value="TikTok",
            ),
        ]

        super().__init__(
            placeholder="Pilih platform medsos",
            options=options,
            custom_id="verify_platform_select",
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):
        self.view.platform = self.values[0]

        await interaction.response.defer(
            ephemeral=True
        )


# =========================================================
# SELECT UMUR
# =========================================================

class AgeSelect(discord.ui.Select):

    def __init__(self):
        options = [
            discord.SelectOption(
                label="15–18 Tahun",
                value="15-18",
            ),
            discord.SelectOption(
                label="19–22 Tahun",
                value="19-22",
            ),
            discord.SelectOption(
                label="23+ Tahun",
                value="23+",
            ),
        ]

        super().__init__(
            placeholder="Pilih rentang umur",
            options=options,
            custom_id="verify_age_select",
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):
        self.view.umur = self.values[0]

        await interaction.response.defer(
            ephemeral=True
        )


# =========================================================
# SELECT GENDER
# =========================================================

class GenderSelect(discord.ui.Select):

    def __init__(self):
        options = [
            discord.SelectOption(
                label="Siswa",
                value="L",
                description="Pilih jika kamu laki-laki",
            ),
            discord.SelectOption(
                label="Siswi",
                value="P",
                description="Pilih jika kamu perempuan",
            ),
        ]

        super().__init__(
            placeholder="Pilih gender",
            options=options,
            custom_id="verify_gender_select",
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):
        self.view.gender = self.values[0]

        await interaction.response.defer(
            ephemeral=True
        )


# =========================================================
# VERIFY DATA PANEL
# =========================================================

class VerifyButton(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)

        self.bot = bot
        self.platform = None
        self.umur = None
        self.gender = None

        self.add_item(
            PlatformSelect()
        )

        self.add_item(
            AgeSelect()
        )

        self.add_item(
            GenderSelect()
        )

    @discord.ui.button(
        label="Lanjut Isi Data",
        style=discord.ButtonStyle.primary,
        custom_id="verify_continue_button",
    )
    async def lanjut(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not self.platform:
            return await interaction.response.send_message(
                "Pilih platform medsos terlebih dahulu.",
                ephemeral=True,
            )

        if not self.umur:
            return await interaction.response.send_message(
                "Pilih rentang umur terlebih dahulu.",
                ephemeral=True,
            )

        if not self.gender:
            return await interaction.response.send_message(
                "Pilih gender terlebih dahulu.",
                ephemeral=True,
            )

        await interaction.response.send_modal(
            VerifyModal(
                self.bot,
                self.platform,
                self.umur,
                self.gender,
            )
        )


# =========================================================
# BUTTON VOICE SETELAH DATA TERKIRIM
# =========================================================

class VoiceVerifyButtonView(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Join Voice Verif",
        style=discord.ButtonStyle.primary,
        custom_id="verify_join_voice_after_submit",
    )
    async def join_voice(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await handle_voice_verif(
            interaction
        )


# =========================================================
# APPROVE / DENY
# =========================================================

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
        link,
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
        custom_id="verify_approve_button",
    )
    async def approve(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
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

        age_15_18_role = (
            interaction.guild.get_role(
                AGE_15_18_ROLE_ID
            )
            if AGE_15_18_ROLE_ID
            else None
        )

        age_19_22_role = (
            interaction.guild.get_role(
                AGE_19_22_ROLE_ID
            )
            if AGE_19_22_ROLE_ID
            else None
        )

        age_23_plus_role = (
            interaction.guild.get_role(
                AGE_23_PLUS_ROLE_ID
            )
            if AGE_23_PLUS_ROLE_ID
            else None
        )

        if member:

            roles_to_add = []

            if member_role:
                roles_to_add.append(
                    member_role
                )

            if self.gender == "L" and siswa_role:
                roles_to_add.append(
                    siswa_role
                )

            elif self.gender == "P" and siswi_role:
                roles_to_add.append(
                    siswi_role
                )

            age_roles = {
                "15-18": age_15_18_role,
                "19-22": age_19_22_role,
                "23+": age_23_plus_role,
            }

            age_role = age_roles.get(
                self.umur
            )

            if age_role:
                roles_to_add.append(
                    age_role
                )

            if roles_to_add:
                await member.add_roles(
                    *roles_to_add
                )

            nonverif_role = interaction.guild.get_role(
                NONVERIF_ROLE_ID
            )

            if (
                nonverif_role
                and nonverif_role in member.roles
            ):
                await member.remove_roles(
                    nonverif_role
                )

            try:
                await member.send(
                    "Verifikasi kamu disetujui."
                )
            except Exception:
                pass

        # =====================================================
        # SIMPAN DATA MEMBER
        # =====================================================

        data_channel = interaction.client.get_channel(
            DATA_MEMBER_CHANNEL_ID
        )

        if data_channel:

            data_embed = discord.Embed(
                title="Data Member Baru",
                color=0x57F287,
            )

            data_embed.add_field(
                name="User",
                value=(
                    f"{member} "
                    f"({self.user_id})"
                ),
                inline=False,
            )

            data_embed.add_field(
                name="Nama",
                value=self.nama,
                inline=True,
            )

            data_embed.add_field(
                name="Asal",
                value=self.asal,
                inline=True,
            )

            data_embed.add_field(
                name="Umur",
                value=self.umur or "Tidak diisi",
                inline=True,
            )

            data_embed.add_field(
                name="Gender",
                value=self.gender,
                inline=True,
            )

            data_embed.add_field(
                name="Medsos",
                value=self.medsos,
                inline=False,
            )

            data_embed.add_field(
                name="Followers",
                value=self.followers,
                inline=True,
            )

            data_embed.add_field(
                name="Profile",
                value=self.link or "Tidak tersedia",
                inline=False,
            )

            data_embed.add_field(
                name="Approved By",
                value=interaction.user.mention,
                inline=False,
            )

            if member:
                data_embed.set_thumbnail(
                    url=member.display_avatar.url
                )

            await data_channel.send(
                content=f"**Username:** {member.name if member else self.user_id}",
                embed=data_embed,
            )

        # =====================================================
        # UPDATE PANEL ENGAGEMENT
        # =====================================================

        if interaction.message.embeds:
            embed = interaction.message.embeds[0]
            embed.color = 0x57F287

            embed.add_field(
                name="Status",
                value=(
                    f"Approved by "
                    f"{interaction.user.mention}"
                ),
                inline=False,
            )

            await interaction.message.edit(
                embed=embed,
                view=None,
            )

        await interaction.response.send_message(
            "Verifikasi berhasil diapprove.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Deny",
        style=discord.ButtonStyle.danger,
        custom_id="verify_deny_button",
    )
    async def deny(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        member = interaction.guild.get_member(
            int(self.user_id)
        )

        if member:
            try:
                await member.send(
                    "Verifikasi kamu ditolak."
                )
            except Exception:
                pass

        if interaction.message.embeds:
            embed = interaction.message.embeds[0]
            embed.color = 0xED4245

            embed.add_field(
                name="Status",
                value=(
                    f"Denied by "
                    f"{interaction.user.mention}"
                ),
                inline=False,
            )

            await interaction.message.edit(
                embed=embed,
                view=None,
            )

        await interaction.response.send_message(
            "Verifikasi berhasil dideny.",
            ephemeral=True,
        )


# =========================================================
# MAIN COG
# =========================================================

class VerifySystem(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def show_verification_panel(
        self,
        interaction: discord.Interaction,
    ):
        """
        Dipanggil dari tombol Data Verif di bawah GIF welcome.
        Panel dikirim sebagai ephemeral agar hanya member terkait
        yang melihat dan mengisi formnya.
        """

        embed = discord.Embed(
            title="Verifikasi Member",
            description=(
                f"{NANZ_ARROW_BLUE} Isi pilihan di bawah sesuai "
                "data kamu.\n\n"
                f"{NANZ_GEAR} Data akan dikirim ke divisi engagement "
                "untuk dikonfirmasi.\n"
                f"{NANZ_ARROW_PURPLE} Setelah data dikirim, kamu akan "
                "mendapat tombol untuk masuk ke Voice Verif."
            ),
            color=0x5865F2,
        )

        embed.add_field(
            name="Data yang diperlukan",
            value=(
                "Platform medsos\n"
                "Rentang umur\n"
                "Gender\n"
                "Nama\n"
                "Asal\n"
                "Username medsos"
            ),
            inline=False,
        )

        embed.set_footer(
            text="nanZ Verification System"
        )

        await interaction.response.send_message(
            embed=embed,
            view=VerifyButton(self.bot),
            ephemeral=True,
        )

    @commands.command(name="dataverif")
    @commands.has_permissions(administrator=True)
    async def verifikasi(
        self,
        ctx,
    ):

        if ctx.channel.id != VERIF_CHANNEL_ID:
            return

        embed = discord.Embed(
            title="Verifikasi Member",
            description=(
                f"{NANZ_ARROW_BLUE} Panel manual untuk staff.\n"
                "Gunakan panel ini jika diperlukan."
            ),
            color=0x5865F2,
        )

        embed.add_field(
            name="Informasi",
            value=(
                "Data hanya dapat dilihat staff.\n"
                "Umur dan gender dipilih melalui opsi.\n"
                "Role umur dan gender diberikan otomatis setelah approve."
            ),
            inline=False,
        )

        await ctx.send(
            embed=embed,
            view=VerifyButton(self.bot),
        )


async def setup(bot):
    await bot.add_cog(
        VerifySystem(bot)
    )