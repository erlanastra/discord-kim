import discord
from discord.ext import commands
import asyncio


# =========================================================
# NANZ CHANNEL GUIDE
# =========================================================
#
# Konsep:
# - Guide dibuat langsung dari kode.
# - Tidak menggunakan database / JSON.
# - Tidak ada panel konfigurasi di Discord.
# - Tidak ada modal atau search.
# - Deskripsi kategori dan channel ditentukan melalui
#   dictionary di bawah.
# - Channel hanya ditampilkan jika role MURID atau
#   CALON MURID memiliki permission View Channel.
# - Category yang masuk EXCLUDED_CATEGORY_IDS tidak
#   ditampilkan.
#
# Command:
# !channelguide
#
# =========================================================


class NanzChannelGuide(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # =================================================
        # ROLE PATOKAN AKSES
        # =================================================

        self.MURID_ROLE_ID = 1453095603008442510
        self.CALON_MURID_ROLE_ID = 1504467138440597604

        # =================================================
        # CATEGORY YANG TIDAK DITAMPILKAN
        # =================================================

        self.EXCLUDED_CATEGORY_IDS = {
            1416639085757468784,
            1485115656616546425,
            1549446088992489473,
            1489206200925946098,
            1407220284217360434,
            1486913064564555786,
            1513028445423009923,
        }

        # =================================================
        # EMOJI NANZ
        # =================================================

        self.PURPLE_ARROW_ID = 1512787191234035803
        self.BLUE_ARROW_ID = 1512787254312042496

        # =================================================
        # DESKRIPSI KATEGORI
        # =================================================
        #
        # Gunakan NAMA CATEGORY Discord sebagai key.
        #
        # Jika nama category berubah, ubah key di sini.
        #
        # =================================================

        self.CATEGORY_DESCRIPTIONS = {

            "MADING SEKOLAH":
                "Pusat informasi dan pengumuman penting nanZ.",

            "HALAMAN SEKOLAH":
                "Tempat murid bersosialisasi dan berbincang.",

            "RUANG KELAS":
                "Tempat belajar dan berbagi wawasan.",

            "RUANG VIP OWNER":
                "Ruang khusus aktivitas Guru Besar.",

            "RUANG KREATIVITAS":
                "Tempat murid berbagi karya dan kreativitas.",

            "Zona Permainan Bot":
                "Area bermain menggunakan bot.",

            "Zona Permainan":
                "Tempat murid bermain game bersama.",

            "RUANG BK":
                "Tempat bantuan dan berbagi cerita.",

            "RUANG NOBAR":
                "Tempat menikmati film bersama.",

            "RUANG TEATER":
                "Area hiburan dan aktivitas voice.",

            "RUANG DONATUR":
                "Ruang khusus informasi dan fasilitas donatur.",

            "AREA SEKOLAH":
                "Area voice untuk aktivitas bersama.",
        }

        # =================================================
        # DESKRIPSI CHANNEL
        # =================================================
        #
        # Gunakan NAMA CHANNEL Discord sebagai key.
        #
        # Nama channel tanpa tanda #.
        #
        # =================================================

        self.CHANNEL_DESCRIPTIONS = {

            # -------------------------------------------------
            # MADING SEKOLAH
            # -------------------------------------------------

            "tata-tertib":
                "Aturan sekolah nanZ.",

            "sambutan":
                "Sambutan untuk murid baru.",

            "atribut":
                "Informasi role dan atribut.",

            "staff-sekolah":
                "Daftar staff nanZ.",

            "giveaway":
                "Informasi dan kegiatan giveaway.",

            "booster-notifikasi":
                "Notifikasi khusus Booster.",

            "req-role-booster":
                "Request role Booster.",

            "perpisahan":
                "Ucapan untuk murid atau staff yang pergi.",


            # -------------------------------------------------
            # HALAMAN SEKOLAH
            # -------------------------------------------------

            "ruang-ngobrol":
                "Obrolan sehari-hari.",

            "bahas-rp":
                "Diskusi seputar Roleplay.",

            "ulang-tahun":
                "Perayaan ulang tahun murid.",

            "pesan-rahasia":
                "Kirim pesan secara anonim.",

            "setup-kata":
                "Pengaturan fitur kata.",

            "pojok-kata":
                "Berbagi kata dan cerita singkat.",


            # -------------------------------------------------
            # RUANG KELAS
            # -------------------------------------------------

            "tanya-ai":
                "Bertanya kepada AI nanZ.",

            "kelas-umum":
                "Materi dan pengetahuan umum.",

            "info-menarik":
                "Fakta dan informasi menarik.",


            # -------------------------------------------------
            # RUANG VIP OWNER
            # -------------------------------------------------

            "streaming-youtube":
                "Info streaming YouTube.",

            "donasi-penonton":
                "Dukungan dan donasi penonton.",


            # -------------------------------------------------
            # RUANG KREATIVITAS
            # -------------------------------------------------

            "berbagi-konten":
                "Berbagi konten dan karya.",

            "daftar-event":
                "Info dan pendaftaran event.",

            "galeri-siswa":
                "Galeri karya murid.",


            # -------------------------------------------------
            # ZONA PERMAINAN BOT
            # -------------------------------------------------

            "perintah-bot":
                "Menjalankan command bot.",

            "owo¹":
                "Area permainan OwO.",

            "owo²":
                "Area permainan OwO.",

            "owo³":
                "Area permainan OwO.",

            "tebak-bendera":
                "Tebak bendera negara.",

            "ethera-bot":
                "Permainan Ethera Bot.",

            "area-mancing":
                "Aktivitas memancing.",


            # -------------------------------------------------
            # ZONA PERMAINAN
            # -------------------------------------------------

            "dokumentasi-game":
                "Berbagi dokumentasi game.",

            "Bermain Game":
                "Voice untuk bermain bersama.",


            # -------------------------------------------------
            # RUANG BK
            # -------------------------------------------------

            "pusat-bantuan":
                "Pusat bantuan murid.",

            "Curhat BK":
                "Voice untuk curhat.",


            # -------------------------------------------------
            # RUANG NOBAR
            # -------------------------------------------------

            "vote-film":
                "Memilih film nobar.",

            "diskusi-film":
                "Diskusi seputar film.",

            "NOBAR":
                "Voice untuk nonton bersama.",


            # -------------------------------------------------
            # RUANG TEATER
            # -------------------------------------------------

            "PODCAST":
                "Voice untuk podcast dan bincang.",

            "GAMES":
                "Voice untuk bermain bersama.",


            # -------------------------------------------------
            # RUANG DONATUR
            # -------------------------------------------------

            "info-donasi":
                "Informasi donasi.",

            "area-donasi":
                "Area aktivitas donatur.",

            "top-donatur":
                "Daftar top donatur.",

            "interface-vip":
                "Akses fasilitas VIP.",

            "Custom Room (VIP)":
                "Voice khusus VIP.",


            # -------------------------------------------------
            # AREA SEKOLAH
            # -------------------------------------------------

            "pengaturan-voice":
                "Pengaturan voice room.",

            "daftar-bot-music":
                "Daftar bot musik.",

            "Girls Corner`s🧚‍♀️":
                "Voice khusus siswi.",

            "Obrolan Terbuka":
                "Voice umum untuk murid.",

            "Custom Room (1)":
                "Voice custom.",

            "Custom Room (2)":
                "Voice custom.",
        }

    # =====================================================
    # EMOJI
    # =====================================================

    def get_emoji(self, guild, emoji_id, fallback):

        emoji = guild.get_emoji(emoji_id)

        if emoji:
            return str(emoji)

        return fallback

    # =====================================================
    # MEMBER ROLE ACCESS CHECK
    # =====================================================

    def role_can_view(self, channel, role_id):

        role = channel.guild.get_role(role_id)

        if role is None:
            return False

        try:
            permissions = channel.permissions_for(role)

            return permissions.view_channel

        except Exception as e:

            print(
                "[NANZ CHANNEL GUIDE] "
                f"Gagal mengecek permission role {role_id}: {e}"
            )

            return False

    # =====================================================
    # CHANNEL ACCESS CHECK
    # =====================================================

    def is_visible_for_members(self, channel):

        return (
            self.role_can_view(
                channel,
                self.MURID_ROLE_ID
            )
            or
            self.role_can_view(
                channel,
                self.CALON_MURID_ROLE_ID
            )
        )

    # =====================================================
    # GET VISIBLE CHANNELS
    # =====================================================

    def get_visible_channels(self, category):

        channels = []

        for channel in category.channels:

            if not self.is_visible_for_members(channel):
                continue

            if isinstance(
                channel,
                (
                    discord.TextChannel,
                    discord.VoiceChannel,
                    discord.ForumChannel,
                    discord.StageChannel,
                )
            ):
                channels.append(channel)

        return channels

    # =====================================================
    # GET VISIBLE CATEGORIES
    # =====================================================

    def get_visible_categories(self, guild):

        categories = []

        for category in guild.categories:

            # Category internal / excluded
            if category.id in self.EXCLUDED_CATEGORY_IDS:
                continue

            channels = self.get_visible_channels(category)

            if channels:
                categories.append(category)

        return categories

    # =====================================================
    # CHANNEL ICON
    # =====================================================

    def get_channel_icon(self, channel):

        if isinstance(
            channel,
            discord.TextChannel
        ):
            return "💬"

        if isinstance(
            channel,
            discord.VoiceChannel
        ):
            return "🔊"

        if isinstance(
            channel,
            discord.ForumChannel
        ):
            return "📝"

        if isinstance(
            channel,
            discord.StageChannel
        ):
            return "🎙️"

        return "📁"

    # =====================================================
    # GET CATEGORY DESCRIPTION
    # =====================================================

    def get_category_description(self, category):

        return self.CATEGORY_DESCRIPTIONS.get(
            category.name,
            ""
        )

    # =====================================================
    # GET CHANNEL DESCRIPTION
    # =====================================================

    def get_channel_description(self, channel):

        return self.CHANNEL_DESCRIPTIONS.get(
            channel.name,
            ""
        )

    # =====================================================
    # GENERATE GUIDE EMBEDS
    # =====================================================

    async def generate_guide_embeds(self, guild):

        purple_arrow = self.get_emoji(
            guild,
            self.PURPLE_ARROW_ID,
            "↳"
        )

        blue_arrow = self.get_emoji(
            guild,
            self.BLUE_ARROW_ID,
            "└"
        )

        visible_categories = self.get_visible_categories(guild)

        embeds = []

        if not visible_categories:

            embed = discord.Embed(
                title=f"{purple_arrow} NANZ CHANNEL GUIDE",
                description="Belum ada ruang yang tersedia.",
                color=discord.Color.from_rgb(
                    100,
                    70,
                    180
                )
            )

            return [embed]

        # =================================================
        # BUAT PANEL PER CATEGORY
        # =================================================

        first_panel = True

        for category in visible_categories:

            channels = self.get_visible_channels(
                category
            )

            if not channels:
                continue

            category_description = (
                self.get_category_description(
                    category
                )
            )

            # -------------------------------------------------
            # HEADER CATEGORY
            # -------------------------------------------------

            header = (
                f"{purple_arrow} **{category.name}**"
            )

            if category_description:

                header += (
                    f"\n\u3000{category_description}"
                )

            # -------------------------------------------------
            # CHANNEL LINES
            # -------------------------------------------------

            channel_lines = []

            for channel in channels:

                icon = self.get_channel_icon(
                    channel
                )

                description = (
                    self.get_channel_description(
                        channel
                    )
                )

                line = (
                    f"{blue_arrow} "
                    f"{icon} "
                    f"{channel.mention}"
                )

                if description:

                    line += (
                        f"\n\u3000└ {description}"
                    )

                # Safety untuk Discord embed
                if len(line) > 1000:

                    line = (
                        line[:997]
                        + "..."
                    )

                channel_lines.append(line)

            # -------------------------------------------------
            # CHUNK CHANNEL
            # -------------------------------------------------

            chunks = []

            current_lines = []
            current_length = len(header)

            for line in channel_lines:

                extra = (
                    len(line)
                    + (1 if current_lines else 0)
                )

                if (
                    current_lines
                    and
                    current_length + extra > 5000
                ):

                    chunks.append(
                        current_lines
                    )

                    current_lines = []

                    current_length = len(
                        header
                    )

                current_lines.append(
                    line
                )

                current_length += extra

            if current_lines:

                chunks.append(
                    current_lines
                )

            # -------------------------------------------------
            # BUAT EMBED
            # -------------------------------------------------

            for part_index, lines in enumerate(
                chunks,
                start=1
            ):

                embed = discord.Embed(
                    description=header,
                    color=discord.Color.from_rgb(
                        100,
                        70,
                        180
                    )
                )

                # Judul utama hanya panel pertama
                if first_panel:

                    embed.title = (
                        f"{purple_arrow} "
                        "NANZ CHANNEL GUIDE"
                    )

                # Jika category terlalu besar
                if len(chunks) > 1:

                    embed.description += (
                        f"\n\n"
                        f"**Bagian "
                        f"{part_index}/"
                        f"{len(chunks)}**"
                    )

                # -------------------------------------------------
                # FIELD
                # -------------------------------------------------

                field_lines = []
                field_length = 0

                for line in lines:

                    extra = (
                        len(line)
                        + (
                            1
                            if field_lines
                            else 0
                        )
                    )

                    if (
                        field_lines
                        and
                        field_length + extra > 1000
                    ):

                        embed.add_field(
                            name="\u200b",
                            value="\n".join(
                                field_lines
                            ),
                            inline=False
                        )

                        field_lines = []
                        field_length = 0

                    field_lines.append(
                        line
                    )

                    field_length += extra

                if field_lines:

                    embed.add_field(
                        name="\u200b",
                        value="\n".join(
                            field_lines
                        ),
                        inline=False
                    )

                embeds.append(embed)

                first_panel = False

        return embeds

    # =====================================================
    # COMMAND
    # =====================================================

    @commands.command(
        name="channelguide"
    )
    async def channel_guide(
        self,
        ctx
    ):

        guild = ctx.guild

        if guild is None:
            return

        try:

            embeds = await self.generate_guide_embeds(
                guild
            )

            # Discord maksimal 10 embed per message
            for index in range(
                0,
                len(embeds),
                10
            ):

                await ctx.send(
                    embeds=embeds[
                        index:index + 10
                    ]
                )

        except Exception as e:

            print(
                "[NANZ CHANNEL GUIDE] "
                f"Error: {type(e).__name__}: {e}"
            )

            try:

                await ctx.send(
                    "❌ Channel Guide gagal ditampilkan.",
                    delete_after=10
                )

            except Exception as send_error:

                print(
                    "[NANZ CHANNEL GUIDE] "
                    f"Gagal mengirim error: {send_error}"
                )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        NanzChannelGuide(bot)
    )