import asyncio
import re

import discord
from discord.ext import commands


class NanzChannelGuide(commands.Cog):
    """
    NANZ CHANNEL GUIDE

    Semua deskripsi kategori dan channel disimpan langsung
    di dalam source code.

    Tidak menggunakan:
    - JSON
    - Database
    - Panel konfigurasi
    - Modal
    - Search system
    """

    # ============================================================
    # ROLE ACCESS
    # ============================================================

    MURID_ROLE_ID = 1453095603008442510
    CALON_MURID_ROLE_ID = 1504467138440597604

    # ============================================================
    # CATEGORY YANG TIDAK DITAMPILKAN
    # ============================================================

    EXCLUDED_CATEGORY_IDS = {
        1416639085757468784,
        1485115656616546425,
        1549446088992489473,
        1489206200925946098,
        1407220284217360434,
        1486913064564555786,
        1513028445423009923,
    }

    # ============================================================
    # CUSTOM EMOJI NANZ
    # ============================================================

    PURPLE_ARROW_ID = 1512787191234035803
    BLUE_ARROW_ID = 1512787254312042496

    # ============================================================
    # DESKRIPSI KATEGORI
    # ============================================================

    CATEGORY_DESCRIPTIONS = {

        "mading sekolah":
            "Pusat informasi dan pengumuman penting nanZ.",

        "halaman sekolah":
            "Tempat murid bersosialisasi dan berbincang.",

        "ruang kelas":
            "Tempat belajar dan berbagi wawasan.",

        "ruang vip owner":
            "Ruang khusus aktivitas Guru Besar.",

        "ruang kreativitas":
            "Tempat murid berbagi karya dan kreativitas.",

        "zona permainan bot":
            "Area bermain menggunakan bot.",

        "zona permainan":
            "Tempat murid bermain game bersama.",

        "ruang bk":
            "Tempat bantuan dan berbagi cerita.",

        "ruang nobar":
            "Tempat menikmati film bersama.",

        "ruang teater":
            "Area hiburan dan aktivitas voice.",

        "ruang donatur":
            "Ruang khusus informasi dan fasilitas donatur.",

        "area sekolah":
            "Area voice untuk aktivitas bersama.",
    }

    # ============================================================
    # DESKRIPSI CHANNEL
    #
    # Nama di sini cukup nama normalnya.
    # Emoji / dekorasi di Discord akan otomatis diabaikan.
    # ============================================================

    CHANNEL_DESCRIPTIONS = {

        # --------------------------------------------------------
        # MADING SEKOLAH
        # --------------------------------------------------------

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


        # --------------------------------------------------------
        # HALAMAN SEKOLAH
        # --------------------------------------------------------

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


        # --------------------------------------------------------
        # RUANG KELAS
        # --------------------------------------------------------

        "tanya-ai":
            "Bertanya kepada AI nanZ.",

        "kelas-umum":
            "Materi dan pengetahuan umum.",

        "info-menarik":
            "Fakta dan informasi menarik.",


        # --------------------------------------------------------
        # RUANG VIP OWNER
        # --------------------------------------------------------

        "streaming-youtube":
            "Info streaming YouTube.",

        "donasi-penonton":
            "Dukungan dan donasi penonton.",


        # --------------------------------------------------------
        # RUANG KREATIVITAS
        # --------------------------------------------------------

        "berbagi-konten":
            "Berbagi konten dan karya.",

        "daftar-event":
            "Info dan pendaftaran event.",

        "galeri-siswa":
            "Galeri karya murid.",


        # --------------------------------------------------------
        # ZONA PERMAINAN BOT
        # --------------------------------------------------------

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


        # --------------------------------------------------------
        # ZONA PERMAINAN
        # --------------------------------------------------------

        "dokumentasi-game":
            "Berbagi dokumentasi game.",

        "bermain game":
            "Voice untuk bermain bersama.",


        # --------------------------------------------------------
        # RUANG BK
        # --------------------------------------------------------

        "pusat-bantuan":
            "Pusat bantuan murid.",

        "curhat bk":
            "Voice untuk curhat.",


        # --------------------------------------------------------
        # RUANG NOBAR
        # --------------------------------------------------------

        "vote-film":
            "Memilih film nobar.",

        "diskusi-film":
            "Diskusi seputar film.",

        "nobar":
            "Voice untuk nonton bersama.",


        # --------------------------------------------------------
        # RUANG TEATER
        # --------------------------------------------------------

        "podcast":
            "Voice untuk podcast dan bincang.",

        "games":
            "Voice untuk bermain bersama.",


        # --------------------------------------------------------
        # RUANG DONATUR
        # --------------------------------------------------------

        "info-donasi":
            "Informasi donasi.",

        "area-donasi":
            "Area aktivitas donatur.",

        "top-donatur":
            "Daftar top donatur.",

        "interface-vip":
            "Akses fasilitas VIP.",

        "custom room (vip)":
            "Voice khusus VIP.",


        # --------------------------------------------------------
        # AREA SEKOLAH
        # --------------------------------------------------------

        "pengaturan-voice":
            "Pengaturan voice room.",

        "daftar-bot-music":
            "Daftar bot musik.",

        "girls corner`s":
            "Voice khusus siswi.",

        "obrolan terbuka":
            "Voice umum untuk murid.",

        "custom room (1)":
            "Voice custom.",

        "custom room (2)":
            "Voice custom.",
    }

    # ============================================================
    # NORMALIZER
    # ============================================================

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Membersihkan nama channel/category agar pencocokan
        tidak tergantung emoji atau dekorasi.

        Contoh:

        🎙️・Bermain Game
        ↓
        bermain game

        💬・📝﹕tata-tertib
        ↓
        tata-tertib
        """

        if not name:
            return ""

        # --------------------------------------------------------
        # Lowercase / case insensitive
        # --------------------------------------------------------

        name = name.casefold()

        # --------------------------------------------------------
        # Hapus emoji Discord custom:
        # <:nama:id>
        # <a:nama:id>
        # --------------------------------------------------------

        name = re.sub(
            r"<a?:\w+:\d+>",
            "",
            name
        )

        # --------------------------------------------------------
        # Hapus emoji unicode.
        #
        # Menghapus sebagian besar karakter emoji melalui
        # rentang Unicode.
        # --------------------------------------------------------

        name = re.sub(
            r"[\U0001F000-\U0001FAFF"
            r"\U00002700-\U000027BF"
            r"\U00002600-\U000026FF"
            r"\U0001F1E6-\U0001F1FF"
            r"\u200d"
            r"\ufe0f"
            r"]+",
            "",
            name
        )

        # --------------------------------------------------------
        # Ubah karakter dekorasi menjadi spasi
        # --------------------------------------------------------

        name = re.sub(
            r"[╭╮╰╯┇┆┊┋│┃━─═╍╾╼➜➤➢➣➥➦➧➨・﹕:|/\\]+",
            " ",
            name
        )

        # --------------------------------------------------------
        # Hapus backtick
        # --------------------------------------------------------

        name = name.replace("`", "")

        # --------------------------------------------------------
        # Rapikan whitespace
        # --------------------------------------------------------

        name = re.sub(r"\s+", " ", name)

        # --------------------------------------------------------
        # Trim
        # --------------------------------------------------------

        return name.strip()

    # ============================================================
    # CARI DESKRIPSI CHANNEL
    # ============================================================

    def get_channel_description(self, channel: discord.abc.GuildChannel):
        """
        Mencari deskripsi channel dengan nama yang sudah
        dinormalisasi.

        Jadi emoji/dekorasi tidak mempengaruhi pencarian.
        """

        normalized_channel_name = self.normalize_name(
            channel.name
        )

        # Pencarian langsung
        if normalized_channel_name in self.CHANNEL_DESCRIPTIONS:
            return self.CHANNEL_DESCRIPTIONS[
                normalized_channel_name
            ]

        # Fallback: normalisasi key dictionary
        for name, description in self.CHANNEL_DESCRIPTIONS.items():

            normalized_key = self.normalize_name(name)

            if normalized_key == normalized_channel_name:
                return description

        return None

    # ============================================================
    # CARI DESKRIPSI CATEGORY
    # ============================================================

    def get_category_description(self, category):
        """
        Mencari deskripsi kategori dengan sistem normalisasi.
        """

        if not category:
            return ""

        normalized_name = self.normalize_name(
            category.name
        )

        if normalized_name in self.CATEGORY_DESCRIPTIONS:
            return self.CATEGORY_DESCRIPTIONS[
                normalized_name
            ]

        for name, description in self.CATEGORY_DESCRIPTIONS.items():

            normalized_key = self.normalize_name(name)

            if normalized_key == normalized_name:
                return description

        return ""

    # ============================================================
    # ICON CHANNEL
    # ============================================================

    @staticmethod
    def get_channel_icon(channel):

        if isinstance(channel, discord.TextChannel):
            return "💬"

        if isinstance(channel, discord.VoiceChannel):
            return "🔊"

        if isinstance(channel, discord.ForumChannel):
            return "📝"

        if isinstance(channel, discord.StageChannel):
            return "🎙️"

        return "📁"

    # ============================================================
    # EMOJI PANAH
    # ============================================================

    @staticmethod
    def get_custom_emoji(guild, emoji_id, fallback):

        emoji = guild.get_emoji(emoji_id)

        if emoji:
            return str(emoji)

        return fallback

    # ============================================================
    # CEK AKSES
    # ============================================================

    def has_access(self, member):

        role_ids = {
            role.id
            for role in member.roles
        }

        return (
            self.MURID_ROLE_ID in role_ids
            or
            self.CALON_MURID_ROLE_ID in role_ids
        )

    # ============================================================
    # CEK CHANNEL TERLIHAT
    # ============================================================

    @staticmethod
    def can_view_channel(member, channel):

        permissions = channel.permissions_for(member)

        return permissions.view_channel

    # ============================================================
    # BUILD CHANNEL LINE
    # ============================================================

    def build_channel_line(
        self,
        channel,
        arrow_blue
    ):

        icon = self.get_channel_icon(channel)

        description = self.get_channel_description(
            channel
        )

        # --------------------------------------------------------
        # Kalau deskripsi belum tersedia
        # --------------------------------------------------------

        if not description:
            description = "Belum ada deskripsi."

        return (
            f"{arrow_blue} {icon} "
            f"{channel.mention}\n"
            f"> {description}"
        )

    # ============================================================
    # COMMAND
    # ============================================================

    @commands.command(
        name="channelguide"
    )
    @commands.guild_only()
    async def channelguide(
        self,
        ctx
    ):
        """
        Menampilkan panduan channel nanZ.
        """

        # --------------------------------------------------------
        # CEK ROLE
        # --------------------------------------------------------

        if not self.has_access(ctx.author):

            await ctx.send(
                "Kamu tidak memiliki akses untuk melihat "
                "Channel Guide nanZ."
            )

            return

        guild = ctx.guild

        # --------------------------------------------------------
        # CUSTOM EMOJI
        # --------------------------------------------------------

        arrow_purple = self.get_custom_emoji(
            guild,
            self.PURPLE_ARROW_ID,
            "🟣"
        )

        arrow_blue = self.get_custom_emoji(
            guild,
            self.BLUE_ARROW_ID,
            "🔵"
        )

        # --------------------------------------------------------
        # AMBIL SEMUA CATEGORY
        # --------------------------------------------------------

        categories = []

        for category in guild.categories:

            if category.id in self.EXCLUDED_CATEGORY_IDS:
                continue

            # Hanya category yang punya channel
            if not category.channels:
                continue

            # ----------------------------------------------------
            # Cek apakah user bisa melihat minimal satu channel
            # ----------------------------------------------------

            visible_channels = []

            for channel in category.channels:

                if self.can_view_channel(
                    ctx.author,
                    channel
                ):
                    visible_channels.append(channel)

            if not visible_channels:
                continue

            categories.append(
                (
                    category,
                    visible_channels
                )
            )

        # --------------------------------------------------------
        # KALAU TIDAK ADA CATEGORY
        # --------------------------------------------------------

        if not categories:

            await ctx.send(
                "Tidak ada channel yang dapat ditampilkan."
            )

            return

        # --------------------------------------------------------
        # BUAT EMBED
        # --------------------------------------------------------

        embeds = []

        current_embed = discord.Embed(
            title=f"{arrow_purple} NANZ CHANNEL GUIDE",
            description=(
                "Panduan channel untuk membantu murid "
                "menemukan ruang yang sesuai."
            ),
            color=discord.Color.from_rgb(
                124,
                58,
                237
            )
        )

        # --------------------------------------------------------
        # LOOP CATEGORY
        # --------------------------------------------------------

        for category, channels in categories:

            category_name = self.normalize_name(
                category.name
            )

            category_description = (
                self.get_category_description(
                    category
                )
            )

            # ----------------------------------------------------
            # HEADER CATEGORY
            # ----------------------------------------------------

            category_header = (
                f"{arrow_purple} ▬『 "
                f"{category.name} "
                f"』▬"
            )

            if category_description:

                category_header += (
                    f"\n> {category_description}"
                )

            # ----------------------------------------------------
            # BUAT SEMUA CHANNEL
            # ----------------------------------------------------

            channel_lines = []

            for channel in channels:

                line = self.build_channel_line(
                    channel,
                    arrow_blue
                )

                channel_lines.append(line)

            category_block = (
                category_header
                + "\n"
                + "\n".join(channel_lines)
            )

            # ----------------------------------------------------
            # DISCORD EMBED LIMIT
            # ----------------------------------------------------

            # Jika field/category terlalu panjang,
            # pecah menjadi beberapa bagian.

            if len(category_block) <= 3900:

                current_description = (
                    current_embed.description
                    or ""
                )

                new_description = (
                    current_description
                    + "\n\n"
                    + category_block
                )

                # -----------------------------------------------
                # Kalau embed sudah mendekati batas
                # -----------------------------------------------

                if len(new_description) > 5800:

                    embeds.append(
                        current_embed
                    )

                    current_embed = discord.Embed(
                        title=(
                            f"{arrow_purple} "
                            f"NANZ CHANNEL GUIDE"
                        ),
                        color=discord.Color.from_rgb(
                            124,
                            58,
                            237
                        )
                    )

                    current_embed.description = (
                        category_block
                    )

                else:

                    current_embed.description = (
                        new_description
                    )

            else:

                # ------------------------------------------------
                # CATEGORY TERLALU PANJANG
                # Pecah berdasarkan channel
                # ------------------------------------------------

                current_description = (
                    current_embed.description
                    or ""
                )

                header_text = (
                    category_header
                    + "\n"
                )

                if (
                    len(current_description)
                    + len(header_text)
                    + 2
                    > 5800
                ):

                    embeds.append(
                        current_embed
                    )

                    current_embed = discord.Embed(
                        title=(
                            f"{arrow_purple} "
                            f"NANZ CHANNEL GUIDE"
                        ),
                        color=discord.Color.from_rgb(
                            124,
                            58,
                            237
                        )
                    )

                    current_description = ""

                current_embed.description = (
                    current_description
                    + "\n\n"
                    + header_text
                )

                # -----------------------------------------------
                # Tambahkan channel satu per satu
                # -----------------------------------------------

                for line in channel_lines:

                    current_description = (
                        current_embed.description
                        or ""
                    )

                    addition = (
                        line
                        + "\n"
                    )

                    if (
                        len(current_description)
                        + len(addition)
                        > 5800
                    ):

                        embeds.append(
                            current_embed
                        )

                        current_embed = discord.Embed(
                            title=(
                                f"{arrow_purple} "
                                f"NANZ CHANNEL GUIDE"
                            ),
                            color=discord.Color.from_rgb(
                                124,
                                58,
                                237
                            )
                        )

                        current_embed.description = (
                            header_text
                            + addition
                        )

                    else:

                        current_embed.description = (
                            current_description
                            + addition
                        )

        # --------------------------------------------------------
        # SIMPAN EMBED TERAKHIR
        # --------------------------------------------------------

        if current_embed.description:

            embeds.append(
                current_embed
            )

        # --------------------------------------------------------
        # FOOTER
        # --------------------------------------------------------

        for index, embed in enumerate(embeds):

            embed.set_footer(
                text=(
                    f"nanZ Server • Stay Solid! "
                    f"• Halaman {index + 1}/{len(embeds)}"
                )
            )

        # --------------------------------------------------------
        # KIRIM
        # --------------------------------------------------------

        for embed in embeds:

            await ctx.send(
                embed=embed
            )

            await asyncio.sleep(
                0.3
            )


# ================================================================
# SETUP
# ================================================================

async def setup(bot):

    await bot.add_cog(
        NanzChannelGuide(bot)
    )