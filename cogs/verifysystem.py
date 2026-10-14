import asyncio
import discord
from discord.ext import commands
import requests
import re


# =========================================================
# CONFIG
# =========================================================

VERIF_CHANNEL_ID = 1486913580161962054

# Channel khusus data verifikasi untuk Approve / Deny
DATA_VERIF_CHANNEL_ID = 1508683781698224241

# Channel engagement / divisi yang menangani verifikasi
ENGAGEMENT_CHANNEL_ID = 1555582479321272402

# Role engagement yang ditag pada setiap notif verifikasi
ENGAGEMENT_ROLE_ID = 1518252236134809681

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

# Emoji custom nanZ
NANZ_ARROW_BLUE = "<a:arrowblue:1512787254312042496>"
NANZ_ARROW_PURPLE = "<a:arrowpurple:1512787191234035803>"
NANZ_LINK = "<a:link:1553688245769085099>"
NANZ_GEAR = "<a:settings:1553688352564183051>"
NANZ_QUESTION = "<a:question:1553688505929044000>"


# =========================================================
# SAFE INTERACTION HELPERS
# =========================================================

async def safe_followup(
    interaction: discord.Interaction,
    content=None,
    *,
    embed=None,
    embeds=None,
    view=None,
    ephemeral=False,
):
    """
    Mengirim followup dengan aman.

    Jika interaction sudah expired / Unknown interaction,
    error ditangani agar tidak menghasilkan traceback besar.
    """

    try:
        return await interaction.followup.send(
            content=content,
            embed=embed,
            embeds=embeds,
            view=view,
            ephemeral=ephemeral,
        )

    except discord.NotFound as e:
        if getattr(e, "code", None) == 10062:
            print(
                "[VERIFY] Interaction sudah expired "
                "saat mengirim followup."
            )
            return None

        print(
            f"[VERIFY] Followup NotFound: {e}"
        )
        return None

    except discord.HTTPException as e:
        print(
            f"[VERIFY] Gagal mengirim followup: {e}"
        )
        return None

    except Exception as e:
        print(
            f"[VERIFY] Error followup: {e}"
        )
        return None


async def safe_defer(
    interaction: discord.Interaction,
    *,
    ephemeral=True,
):
    """
    Memberikan acknowledgement ke Discord secepat mungkin.

    Return:
        True  = berhasil defer
        False = interaction sudah tidak valid
    """

    try:

        if interaction.response.is_done():
            return True

        await interaction.response.defer(
            ephemeral=ephemeral
        )

        return True

    except discord.NotFound as e:

        if getattr(e, "code", None) == 10062:
            print(
                "[VERIFY] Interaction sudah expired "
                "sebelum defer."
            )
            return False

        print(
            f"[VERIFY] Interaction NotFound saat defer: {e}"
        )
        return False

    except discord.HTTPException as e:

        print(
            f"[VERIFY] HTTP error saat defer: {e}"
        )
        return False

    except Exception as e:

        print(
            f"[VERIFY] Error saat defer: {e}"
        )
        return False


async def safe_response_send(
    interaction: discord.Interaction,
    content=None,
    *,
    embed=None,
    view=None,
    ephemeral=False,
):
    """
    Response pertama jika interaction belum di-response.
    Jika sudah di-response/defer, otomatis menggunakan followup.
    """

    try:

        if interaction.response.is_done():

            return await safe_followup(
                interaction,
                content=content,
                embed=embed,
                view=view,
                ephemeral=ephemeral,
            )

        return await interaction.response.send_message(
            content=content,
            embed=embed,
            view=view,
            ephemeral=ephemeral,
        )

    except discord.NotFound as e:

        if getattr(e, "code", None) == 10062:

            print(
                "[VERIFY] Interaction expired "
                "saat mengirim response."
            )

            return None

        print(
            f"[VERIFY] Response NotFound: {e}"
        )
        return None

    except discord.HTTPException as e:

        print(
            f"[VERIFY] HTTP error response: {e}"
        )
        return None

    except Exception as e:

        print(
            f"[VERIFY] Error response: {e}"
        )
        return None


# =========================================================
# GENERAL HELPERS
# =========================================================

def channel_url(
    guild_id: int,
    channel_id: int
) -> str:

    return (
        f"https://discord.com/channels/"
        f"{guild_id}/{channel_id}"
    )


def get_instagram_followers(username):

    try:

        url = (
            f"https://www.instagram.com/"
            f"{username}/"
        )

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        res = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        if res.status_code != 200:
            return "Tidak ditemukan"

        match = re.search(
            r'"edge_followed_by":{"count":(\d+)}',
            res.text,
        )

        if match:
            return (
                f"{int(match.group(1)):,}"
            )

        return "Hidden"

    except Exception:

        return "Error"


def get_tiktok_followers(username):

    try:

        url = (
            f"https://www.tiktok.com/"
            f"@{username}"
        )

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        res = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        if res.status_code != 200:
            return "Tidak ditemukan"

        match = re.search(
            r'"followerCount":(\d+)',
            res.text
        )

        if match:
            return (
                f"{int(match.group(1)):,}"
            )

        return "Hidden"

    except Exception:

        return "Error"


async def get_social_followers(
    platform,
    username
):
    """
    Jalankan request blocking di executor
    supaya event loop Discord tidak ikut terblokir.

    Python 3.8 compatible.
    """

    loop = asyncio.get_running_loop()

    if platform == "IG":

        return await loop.run_in_executor(
            None,
            get_instagram_followers,
            username
        )

    if platform == "TikTok":

        return await loop.run_in_executor(
            None,
            get_tiktok_followers,
            username
        )

    return "Tidak dicek"


def get_verif_voice_channels(guild):

    channels = []

    for channel_id in VOICE_VERIF_CHANNEL_IDS:

        channel = guild.get_channel(
            channel_id
        )

        if isinstance(
            channel,
            (
                discord.VoiceChannel,
                discord.StageChannel,
            ),
        ):
            channels.append(channel)

    return channels


def choose_verif_voice(
    guild,
    member
):
    """
    Prioritas:
    - voice yang tidak ditempati member lain
    - kalau semua berisi, kembali ke voice pertama
    """

    channels = get_verif_voice_channels(
        guild
    )

    if not channels:
        return None

    for channel in channels:

        others = [
            m
            for m in channel.members
            if m.id != member.id
        ]

        if not others:
            return channel

    return channels[0]


# =========================================================
# VOICE JOIN VIEW
# =========================================================

class VoiceJoinLinkView(discord.ui.View):

    def __init__(
        self,
        guild_id,
        channel_id,
        timeout=None
    ):

        super().__init__(
            timeout=timeout
        )

        self.add_item(
            discord.ui.Button(
                label="Join Voice Verif",
                style=discord.ButtonStyle.link,
                url=channel_url(
                    guild_id,
                    channel_id
                ),
            )
        )


# =========================================================
# STAFF VOICE NOTICE
# =========================================================

class StaffVoiceNoticeView(
    discord.ui.View
):

    def __init__(
        self,
        guild_id,
        channel_id
    ):

        super().__init__(
            timeout=None
        )

        self.add_item(
            discord.ui.Button(
                label="Masuk Voice",
                style=discord.ButtonStyle.link,
                url=channel_url(
                    guild_id,
                    channel_id
                ),
            )
        )


# =========================================================
# MEMBER VOICE HANDLER
# =========================================================

async def send_voice_notice(
    interaction,
    target
):

    guild = interaction.guild
    member = interaction.user

    engagement = interaction.client.get_channel(
        ENGAGEMENT_CHANNEL_ID
    )

    if not engagement:
        print(
            "[VERIFY] Engagement channel "
            "tidak ditemukan."
        )
        return

    embed = discord.Embed(
        title="Member Menunggu Verifikasi Voice",
        description=(
            f"{NANZ_ARROW_BLUE} "
            f"{member.mention} sudah masuk ke "
            f"**{target.name}**.\n"
            f"{NANZ_ARROW_PURPLE} Staff dapat masuk "
            f"ke voice tersebut untuk melakukan "
            f"konfirmasi data."
        ),
        color=0x5865F2,
    )

    embed.add_field(
        name="Member",
        value=(
            f"{member.mention}\n"
            f"`{member.id}`"
        ),
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

    try:

        await engagement.send(
            content=(
                f"<@&{ENGAGEMENT_ROLE_ID}>"
            ),
            embed=embed,
            view=StaffVoiceNoticeView(
                guild.id,
                target.id,
            ),
            allowed_mentions=discord.AllowedMentions(
                users=True,
                roles=True,
            ),
        )

    except discord.HTTPException as e:

        print(
            f"[VERIFY] Gagal mengirim "
            f"voice notice: {e}"
        )


async def handle_voice_verif(
    interaction
):

    # =====================================================
    # ACKNOWLEDGE SECEPAT MUNGKIN
    # =====================================================

    if not await safe_defer(
        interaction,
        ephemeral=True
    ):
        return

    guild = interaction.guild
    member = interaction.user

    if (
        guild is None
        or not isinstance(
            member,
            discord.Member
        )
    ):

        await safe_followup(
            interaction,
            (
                "Fitur ini hanya dapat digunakan "
                "di dalam server."
            ),
            ephemeral=True,
        )
        return

    target = choose_verif_voice(
        guild,
        member
    )

    if target is None:

        await safe_followup(
            interaction,
            (
                "Voice verifikasi tidak ditemukan. "
                "Hubungi staff."
            ),
            ephemeral=True,
        )
        return

    # =====================================================
    # MEMBER SUDAH ADA DI VOICE
    # =====================================================

    if (
        member.voice
        and member.voice.channel
    ):

        try:

            await member.move_to(
                target,
                reason="nanZ Verification Voice",
            )

        except discord.Forbidden:

            await safe_followup(
                interaction,
                (
                    "Bot tidak memiliki izin "
                    "untuk memindahkan kamu "
                    "ke voice verifikasi."
                ),
                ephemeral=True,
            )
            return

        except discord.HTTPException:

            await safe_followup(
                interaction,
                (
                    "Gagal memindahkan kamu "
                    "ke voice verifikasi. "
                    "Coba lagi."
                ),
                ephemeral=True,
            )
            return

        await send_voice_notice(
            interaction,
            target
        )

        await safe_followup(
            interaction,
            (
                f"{NANZ_ARROW_BLUE} "
                f"Kamu sudah diarahkan ke "
                f"**{target.name}**.\n"
                "Silakan tunggu staff melakukan "
                "konfirmasi data."
            ),
            ephemeral=True,
        )

        return

    # =====================================================
    # MEMBER BELUM BERADA DI VOICE
    # =====================================================

    view = VoiceJoinLinkView(
        guild.id,
        target.id,
    )

    await safe_followup(
        interaction,
        (
            f"{NANZ_ARROW_BLUE} "
            "Kamu belum berada di voice.\n"
            f"Klik tombol **Join Voice Verif** "
            f"di bawah untuk masuk ke "
            f"**{target.name}**."
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
        placeholder=(
            "Nama yang ingin digunakan di server"
        ),
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

        # =====================================================
        # ACKNOWLEDGE SECEPAT MUNGKIN
        # =====================================================

        if not await safe_defer(
            interaction,
            ephemeral=True
        ):
            return

        # =====================================================
        # VALIDASI USERNAME
        # =====================================================

        if "@" not in self.username.value:

            await safe_followup(
                interaction,
                (
                    f"{NANZ_QUESTION} "
                    "Username harus menggunakan @."
                ),
                ephemeral=True,
            )
            return

        username_clean = (
            self.username.value
            .replace("@", "")
            .strip()
        )

        if not username_clean:

            await safe_followup(
                interaction,
                (
                    f"{NANZ_QUESTION} "
                    "Username medsos tidak boleh kosong."
                ),
                ephemeral=True,
            )
            return

        medsos_final = (
            f"{self.platform} | "
            f"@{username_clean}"
        )

        followers = "Tidak dicek"
        link = ""

        # =====================================================
        # CEK FOLLOWERS
        # =====================================================

        if self.platform == "IG":

            followers = (
                await get_social_followers(
                    "IG",
                    username_clean
                )
            )

            link = (
                "https://instagram.com/"
                f"{username_clean}"
            )

        elif self.platform == "TikTok":

            followers = (
                await get_social_followers(
                    "TikTok",
                    username_clean
                )
            )

            link = (
                "https://tiktok.com/@"
                f"{username_clean}"
            )

        # =====================================================
        # DATA LENGKAP + APPROVE/DENY
        # =====================================================

        verif_channel = (
            interaction.client.get_channel(
                DATA_VERIF_CHANNEL_ID
            )
        )

        if verif_channel:

            embed = discord.Embed(
                title="Data Verifikasi Baru",
                description=(
                    f"{NANZ_ARROW_BLUE} "
                    f"{interaction.user.mention} "
                    "telah mengirim data verifikasi.\n"
                    f"{NANZ_GEAR} Silakan lakukan "
                    "**Approve** atau **Deny** "
                    "setelah melakukan konfirmasi."
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
                    value=(
                        f"{NANZ_LINK} "
                        f"[Buka Profile]({link})"
                    ),
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

            try:

                await verif_channel.send(
                    content=(
                        "**Verifikasi baru:** "
                        f"{interaction.user.mention}"
                    ),
                    embed=embed,
                    view=view,
                    allowed_mentions=discord.AllowedMentions(
                        users=True
                    ),
                )

            except discord.HTTPException as e:

                print(
                    f"[VERIFY] Gagal mengirim "
                    f"data verifikasi: {e}"
                )

        else:

            print(
                "[VERIFY] DATA_VERIF_CHANNEL "
                "tidak ditemukan."
            )

        # =====================================================
        # NOTIF ENGAGEMENT
        # =====================================================

        engagement = (
            interaction.client.get_channel(
                ENGAGEMENT_CHANNEL_ID
            )
        )

        if engagement:

            notice = discord.Embed(
                title="Member Mengisi Data Verifikasi",
                description=(
                    f"{NANZ_ARROW_BLUE} "
                    f"{interaction.user.mention} "
                    "telah mengirim data verifikasi.\n"
                    f"{NANZ_GEAR} Data lengkap dan tombol "
                    "**Approve/Deny** ada di "
                    f"<#{DATA_VERIF_CHANNEL_ID}>."
                ),
                color=0x5865F2,
            )

            notice.add_field(
                name="Member",
                value=(
                    f"{interaction.user.mention}\n"
                    f"`{interaction.user.id}`"
                ),
                inline=False,
            )

            notice.set_thumbnail(
                url=interaction.user.display_avatar.url
            )

            try:

                await engagement.send(
                    content=(
                        f"<@&{ENGAGEMENT_ROLE_ID}>"
                    ),
                    embed=notice,
                    allowed_mentions=discord.AllowedMentions(
                        users=True,
                        roles=True,
                    ),
                )

            except discord.HTTPException as e:

                print(
                    f"[VERIFY] Gagal mengirim "
                    f"engagement notice: {e}"
                )

        # =====================================================
        # RESPONSE KE MEMBER
        # =====================================================

        view = VoiceVerifyButtonView(
            self.bot
        )

        await safe_followup(
            interaction,
            (
                "Data verifikasi berhasil dikirim.\n\n"
                "Selanjutnya, masuk ke **Voice Verif** "
                "untuk konfirmasi langsung bersama staff."
            ),
            view=view,
            ephemeral=True,
        )


# =========================================================
# SELECT PLATFORM
# =========================================================

class PlatformSelect(
    discord.ui.Select
):

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

        self.view.platform = (
            self.values[0]
        )

        await safe_response_send(
            interaction,
            (
                f"Platform dipilih: "
                f"**{self.values[0]}**."
            ),
            ephemeral=True,
        )


# =========================================================
# SELECT UMUR
# =========================================================

class AgeSelect(
    discord.ui.Select
):

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

        self.view.umur = (
            self.values[0]
        )

        await safe_response_send(
            interaction,
            (
                f"Rentang umur dipilih: "
                f"**{self.values[0]}**."
            ),
            ephemeral=True,
        )


# =========================================================
# SELECT GENDER
# =========================================================

class GenderSelect(
    discord.ui.Select
):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="Siswa",
                value="L",
                description=(
                    "Pilih jika kamu laki-laki"
                ),
            ),

            discord.SelectOption(
                label="Siswi",
                value="P",
                description=(
                    "Pilih jika kamu perempuan"
                ),
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

        self.view.gender = (
            self.values[0]
        )

        await safe_response_send(
            interaction,
            (
                "Gender berhasil dipilih."
            ),
            ephemeral=True,
        )


# =========================================================
# VERIFY DATA PANEL
# =========================================================

class VerifyButton(
    discord.ui.View
):

    def __init__(self, bot):

        super().__init__(
            timeout=None
        )

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

            await safe_response_send(
                interaction,
                (
                    "Pilih platform medsos "
                    "terlebih dahulu."
                ),
                ephemeral=True,
            )
            return

        if not self.umur:

            await safe_response_send(
                interaction,
                (
                    "Pilih rentang umur "
                    "terlebih dahulu."
                ),
                ephemeral=True,
            )
            return

        if not self.gender:

            await safe_response_send(
                interaction,
                (
                    "Pilih gender "
                    "terlebih dahulu."
                ),
                ephemeral=True,
            )
            return

        try:

            await interaction.response.send_modal(
                VerifyModal(
                    self.bot,
                    self.platform,
                    self.umur,
                    self.gender,
                )
            )

        except discord.NotFound as e:

            if getattr(e, "code", None) == 10062:

                print(
                    "[VERIFY] Interaction expired "
                    "saat membuka modal."
                )

            else:

                print(
                    f"[VERIFY] Error membuka modal: {e}"
                )

        except discord.HTTPException as e:

            print(
                f"[VERIFY] HTTP error membuka modal: {e}"
            )


# =========================================================
# BUTTON VOICE SETELAH DATA TERKIRIM
# =========================================================

class VoiceVerifyButtonView(
    discord.ui.View
):

    def __init__(self, bot):

        super().__init__(
            timeout=None
        )

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

class VerifyView(
    discord.ui.View
):

    def __init__(
        self,
        bot,
        user_id=None,
        nama=None,
        asal=None,
        umur=None,
        gender=None,
        medsos=None,
        followers=None,
        link=None,
    ):

        super().__init__(
            timeout=None
        )

        self.bot = bot

        self.user_id = user_id
        self.nama = nama
        self.asal = asal
        self.umur = umur
        self.gender = gender
        self.medsos = medsos
        self.followers = followers
        self.link = link

    # =====================================================
    # LOAD DATA DARI EMBED
    # =====================================================

    def _load_from_message(
        self,
        message
    ):

        if (
            not message
            or not message.embeds
        ):
            return False

        try:

            fields = message.embeds[
                0
            ].fields

            values = {
                field.name.strip().lower():
                    field.value.strip()
                for field in fields
            }

        except Exception as e:

            print(
                f"[VERIFY] Gagal membaca "
                f"field embed: {e}"
            )

            return False

        member_value = values.get(
            "member",
            ""
        )

        match = (
            re.search(
                r"`(\d+)`",
                member_value
            )
            or
            re.search(
                r"<@!?([0-9]+)>",
                member_value
            )
        )

        if not match:
            return False

        self.user_id = match.group(1)

        self.nama = values.get(
            "nama",
            ""
        )

        self.asal = values.get(
            "asal",
            ""
        )

        self.umur = values.get(
            "umur",
            ""
        )

        self.medsos = values.get(
            "medsos",
            ""
        )

        self.followers = values.get(
            "followers",
            ""
        )

        profile = values.get(
            "profile",
            ""
        )

        # Support markdown:
        # [Buka Profile](https://...)
        pm = re.search(
            r"\((https?://[^)]+)\)",
            profile
        )

        if pm:

            self.link = pm.group(1)

        else:

            if profile == "Tidak tersedia":

                self.link = ""

            else:

                self.link = profile

        gender_value = values.get(
            "gender",
            ""
        ).lower()

        if "siswi" in gender_value:

            self.gender = "P"

        elif "siswa" in gender_value:

            self.gender = "L"

        else:

            self.gender = values.get(
                "gender",
                ""
            )

        return True

    # =====================================================
    # APPROVE
    # =====================================================

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

        # =================================================
        # DEFER SEBELUM PROSES APA PUN
        # =================================================

        if not await safe_defer(
            interaction,
            ephemeral=True
        ):
            return

        # =================================================
        # VALIDASI GUILD
        # =================================================

        if interaction.guild is None:

            await safe_followup(
                interaction,
                (
                    "Verifikasi hanya dapat "
                    "diproses di dalam server."
                ),
                ephemeral=True,
            )
            return

        # =================================================
        # LOAD DATA
        # =================================================

        if not self._load_from_message(
            interaction.message
        ):

            await safe_followup(
                interaction,
                (
                    "Data verifikasi pada pesan "
                    "ini tidak dapat dibaca."
                ),
                ephemeral=True,
            )
            return

        # =================================================
        # CEK DATA USER ID
        # =================================================

        try:

            target_user_id = int(
                self.user_id
            )

        except (
            ValueError,
            TypeError
        ):

            await safe_followup(
                interaction,
                (
                    "ID member pada data "
                    "verifikasi tidak valid."
                ),
                ephemeral=True,
            )
            return

        # =================================================
        # AMBIL MEMBER
        # =================================================

        member = (
            interaction.guild.get_member(
                target_user_id
            )
        )

        # Kalau tidak ada di cache, coba fetch
        if member is None:

            try:

                member = (
                    await interaction.guild.fetch_member(
                        target_user_id
                    )
                )

            except (
                discord.NotFound,
                discord.HTTPException
            ):

                member = None

        # =================================================
        # AMBIL ROLE
        # =================================================

        guild = interaction.guild

        member_role = guild.get_role(
            MEMBER_ROLE_ID
        )

        siswa_role = guild.get_role(
            SISWA_ROLE_ID
        )

        siswi_role = guild.get_role(
            SISWI_ROLE_ID
        )

        age_15_18_role = guild.get_role(
            AGE_15_18_ROLE_ID
        )

        age_19_22_role = guild.get_role(
            AGE_19_22_ROLE_ID
        )

        age_23_plus_role = guild.get_role(
            AGE_23_PLUS_ROLE_ID
        )

        nonverif_role = guild.get_role(
            NONVERIF_ROLE_ID
        )

        # =================================================
        # PROSES ROLE
        # =================================================

        if member:

            roles_to_add = []

            # -------------------------------------------------
            # MEMBER ROLE
            # -------------------------------------------------

            if (
                member_role
                and member_role not in member.roles
            ):

                roles_to_add.append(
                    member_role
                )

            # -------------------------------------------------
            # GENDER
            # -------------------------------------------------

            if self.gender == "L":

                if (
                    siswa_role
                    and siswa_role not in member.roles
                ):

                    roles_to_add.append(
                        siswa_role
                    )

                # Hapus Siswi jika ada
                if (
                    siswi_role
                    and siswi_role in member.roles
                ):

                    try:

                        await member.remove_roles(
                            siswi_role,
                            reason=(
                                "nanZ Verification "
                                "Gender Update"
                            ),
                        )

                    except discord.HTTPException as e:

                        print(
                            "[VERIFY] Gagal menghapus "
                            f"role Siswi: {e}"
                        )

            elif self.gender == "P":

                if (
                    siswi_role
                    and siswi_role not in member.roles
                ):

                    roles_to_add.append(
                        siswi_role
                    )

                # Hapus Siswa jika ada
                if (
                    siswa_role
                    and siswa_role in member.roles
                ):

                    try:

                        await member.remove_roles(
                            siswa_role,
                            reason=(
                                "nanZ Verification "
                                "Gender Update"
                            ),
                        )

                    except discord.HTTPException as e:

                        print(
                            "[VERIFY] Gagal menghapus "
                            f"role Siswa: {e}"
                        )

            # -------------------------------------------------
            # UMUR
            # -------------------------------------------------

            age_roles = {
                "15-18": age_15_18_role,
                "19-22": age_19_22_role,
                "23+": age_23_plus_role,
            }

            selected_age_role = age_roles.get(
                self.umur
            )

            if (
                selected_age_role
                and selected_age_role not in member.roles
            ):

                roles_to_add.append(
                    selected_age_role
                )

            # Hapus role umur lain
            roles_to_remove = []

            for role in [
                age_15_18_role,
                age_19_22_role,
                age_23_plus_role,
            ]:

                if (
                    role
                    and role != selected_age_role
                    and role in member.roles
                ):

                    roles_to_remove.append(
                        role
                    )

            if roles_to_remove:

                try:

                    await member.remove_roles(
                        *roles_to_remove,
                        reason=(
                            "nanZ Verification "
                            "Age Update"
                        ),
                    )

                except discord.HTTPException as e:

                    print(
                        "[VERIFY] Gagal menghapus "
                        f"role umur lama: {e}"
                    )

            # -------------------------------------------------
            # TAMBAHKAN ROLE
            # -------------------------------------------------

            if roles_to_add:

                try:

                    await member.add_roles(
                        *roles_to_add,
                        reason=(
                            "nanZ Verification Approved"
                        ),
                    )

                except discord.Forbidden:

                    print(
                        "[VERIFY] Bot tidak memiliki "
                        "izin untuk memberikan role."
                    )

                except discord.HTTPException as e:

                    print(
                        "[VERIFY] Gagal memberikan "
                        f"role: {e}"
                    )

            # -------------------------------------------------
            # HAPUS NON VERIF
            # -------------------------------------------------

            if (
                nonverif_role
                and nonverif_role in member.roles
            ):

                try:

                    await member.remove_roles(
                        nonverif_role,
                        reason=(
                            "nanZ Verification Approved"
                        ),
                    )

                except discord.HTTPException as e:

                    print(
                        "[VERIFY] Gagal menghapus "
                        f"Non Verif: {e}"
                    )

            # -------------------------------------------------
            # DM MEMBER
            # -------------------------------------------------

            try:

                await member.send(
                    "Verifikasi kamu disetujui."
                )

            except Exception:

                # DM tertutup bukan error sistem
                pass

        # =================================================
        # SIMPAN DATA MEMBER
        # =================================================

        data_channel = (
            interaction.client.get_channel(
                DATA_MEMBER_CHANNEL_ID
            )
        )

        if data_channel:

            data_embed = discord.Embed(
                title="Data Member Baru",
                color=0x57F287,
            )

            if member:

                user_display = (
                    f"{member} "
                    f"({self.user_id})"
                )

                username_display = member.name

            else:

                user_display = (
                    f"User tidak ditemukan "
                    f"({self.user_id})"
                )

                username_display = (
                    self.user_id
                )

            data_embed.add_field(
                name="User",
                value=user_display,
                inline=False,
            )

            data_embed.add_field(
                name="Nama",
                value=self.nama or "Tidak diisi",
                inline=True,
            )

            data_embed.add_field(
                name="Asal",
                value=self.asal or "Tidak diisi",
                inline=True,
            )

            data_embed.add_field(
                name="Umur",
                value=(
                    self.umur
                    or "Tidak diisi"
                ),
                inline=True,
            )

            data_embed.add_field(
                name="Gender",
                value=(
                    "Siswa"
                    if self.gender == "L"
                    else (
                        "Siswi"
                        if self.gender == "P"
                        else (
                            self.gender
                            or "Tidak diisi"
                        )
                    )
                ),
                inline=True,
            )

            data_embed.add_field(
                name="Medsos",
                value=(
                    self.medsos
                    or "Tidak diisi"
                ),
                inline=False,
            )

            data_embed.add_field(
                name="Followers",
                value=(
                    self.followers
                    or "Tidak dicek"
                ),
                inline=True,
            )

            data_embed.add_field(
                name="Profile",
                value=(
                    self.link
                    or "Tidak tersedia"
                ),
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

            try:

                await data_channel.send(
                    content=(
                        f"**Username:** "
                        f"{username_display}"
                    ),
                    embed=data_embed,
                )

            except discord.HTTPException as e:

                print(
                    "[VERIFY] Gagal menyimpan "
                    f"data member: {e}"
                )

        # =================================================
        # UPDATE PANEL
        # =================================================

        if interaction.message.embeds:

            try:

                embed = (
                    interaction.message.embeds[0]
                )

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

            except discord.HTTPException as e:

                print(
                    "[VERIFY] Gagal mengupdate "
                    f"panel approve: {e}"
                )

        # =================================================
        # RESPONSE
        # =================================================

        await safe_followup(
            interaction,
            "Verifikasi berhasil diapprove.",
            ephemeral=True,
        )

    # =====================================================
    # DENY
    # =====================================================

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

        # =================================================
        # DEFER SECEPAT MUNGKIN
        # =================================================

        if not await safe_defer(
            interaction,
            ephemeral=True
        ):
            return

        # =================================================
        # VALIDASI GUILD
        # =================================================

        if interaction.guild is None:

            await safe_followup(
                interaction,
                (
                    "Verifikasi hanya dapat "
                    "diproses di dalam server."
                ),
                ephemeral=True,
            )
            return

        # =================================================
        # LOAD DATA
        # =================================================

        if not self._load_from_message(
            interaction.message
        ):

            await safe_followup(
                interaction,
                (
                    "Data verifikasi pada pesan "
                    "ini tidak dapat dibaca."
                ),
                ephemeral=True,
            )
            return

        # =================================================
        # USER ID
        # =================================================

        try:

            target_user_id = int(
                self.user_id
            )

        except (
            ValueError,
            TypeError
        ):

            await safe_followup(
                interaction,
                (
                    "ID member pada data "
                    "verifikasi tidak valid."
                ),
                ephemeral=True,
            )
            return

        # =================================================
        # AMBIL MEMBER
        # =================================================

        member = (
            interaction.guild.get_member(
                target_user_id
            )
        )

        if member is None:

            try:

                member = (
                    await interaction.guild.fetch_member(
                        target_user_id
                    )
                )

            except (
                discord.NotFound,
                discord.HTTPException
            ):

                member = None

        # =================================================
        # DM MEMBER
        # =================================================

        if member:

            try:

                await member.send(
                    "Verifikasi kamu ditolak."
                )

            except Exception:

                pass

        # =================================================
        # UPDATE PANEL
        # =================================================

        if interaction.message.embeds:

            try:

                embed = (
                    interaction.message.embeds[0]
                )

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

            except discord.HTTPException as e:

                print(
                    "[VERIFY] Gagal mengupdate "
                    f"panel deny: {e}"
                )

        # =================================================
        # RESPONSE
        # =================================================

        await safe_followup(
            interaction,
            "Verifikasi berhasil dideny.",
            ephemeral=True,
        )


# =========================================================
# MAIN COG
# =========================================================

class VerifySystem(
    commands.Cog
):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

    # =====================================================
    # SHOW VERIFICATION PANEL
    # =====================================================

    async def show_verification_panel(
        self,
        interaction: discord.Interaction,
    ):
        """
        Dipanggil dari tombol Data Verif
        di bawah GIF welcome.

        Panel dikirim ephemeral agar hanya
        member terkait yang melihatnya.
        """

        embed = discord.Embed(
            title="Verifikasi Member",
            description=(
                f"{NANZ_ARROW_BLUE} "
                "Isi pilihan di bawah sesuai "
                "data kamu.\n\n"
                f"{NANZ_GEAR} Data akan dikirim ke "
                "divisi engagement untuk dikonfirmasi.\n"
                f"{NANZ_ARROW_PURPLE} Setelah data dikirim, "
                "kamu akan mendapat tombol untuk "
                "masuk ke Voice Verif."
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

        await safe_response_send(
            interaction,
            embed=embed,
            view=VerifyButton(
                self.bot
            ),
            ephemeral=True,
        )

    # =====================================================
    # COMMAND DATAVERIF
    # =====================================================

    @commands.command(
        name="dataverif"
    )
    async def verifikasi(
        self,
        ctx
    ):

        if (
            ctx.channel.id
            != VERIF_CHANNEL_ID
        ):
            return

        embed = discord.Embed(
            title="Verifikasi Member",
            description=(
                f"{NANZ_ARROW_BLUE} "
                "Panel manual untuk staff.\n"
                "Gunakan panel ini jika diperlukan."
            ),
            color=0x5865F2,
        )

        embed.add_field(
            name="Informasi",
            value=(
                "Data hanya dapat dilihat staff.\n"
                "Umur dan gender dipilih melalui opsi.\n"
                "Role umur dan gender diberikan "
                "otomatis setelah approve."
            ),
            inline=False,
        )

        # Panel aktif selama 1 jam
        try:

            await ctx.send(
                embed=embed,
                view=VerifyButton(
                    self.bot
                ),
                delete_after=3600,
            )

        except discord.HTTPException as e:

            print(
                f"[VERIFY] Gagal mengirim "
                f"panel dataverif: {e}"
            )

            return

        # Hapus command
        try:

            await ctx.message.delete()

        except (
            discord.Forbidden,
            discord.NotFound,
            discord.HTTPException
        ):

            pass


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    # =====================================================
    # PERSISTENT APPROVE / DENY
    # =====================================================

    bot.add_view(
        VerifyView(bot)
    )

    # =====================================================
    # COG
    # =====================================================

    await bot.add_cog(
        VerifySystem(bot)
    )

    print(
        "[VERIFY] VerifySystem Cog loaded."
    )