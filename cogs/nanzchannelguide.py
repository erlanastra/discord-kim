import asyncio
import re

import discord
from discord.ext import commands


class NanzChannelGuide(commands.Cog):
    # =========================================================
    # CONFIG
    # =========================================================

    # Category yang tidak ditampilkan di Channel Guide
    EXCLUDED_CATEGORY_IDS = {
        1416639085757468784,
        1485115656616546425,
        1549446088992489473,
        1489206200925946098,
        1407220284217360434,
        1486913064564555786,
        1513028445423009923,
    }

    # Role yang boleh menggunakan !channelguide
    MURID_ROLE_ID = 1453095603008442510
    CALON_MURID_ROLE_ID = 1504467138440597604

    # Emoji khas nanZ
    PURPLE_ARROW_ID = 1512787191234035803
    BLUE_ARROW_ID = 1512787254312042496

    # Batas aman Embed Description Discord
    MAX_DESCRIPTION_LENGTH = 3900

    # Jeda antar pengiriman embed
    SEND_DELAY = 1.0

    # =========================================================
    # CHANNEL DESCRIPTIONS
    # =========================================================

    CHANNEL_DESCRIPTIONS = {

        # =====================================================
        # MADING SEKOLAH
        # =====================================================

        "tata-tertib":
            "Tempat membaca dan memahami seluruh aturan yang berlaku di server nanZ.",

        "sambutan":
            "Tempat menyambut dan mengenalkan informasi penting bagi murid yang baru bergabung.",

        "atribut":
            "Tempat melihat informasi mengenai role, atribut, dan identitas yang tersedia di nanZ.",

        "staff-sekolah":
            "Tempat melihat daftar staff nanZ beserta informasi mengenai kepengurusan server.",

        "giveaway":
            "Tempat mendapatkan informasi mengenai giveaway dan kegiatan berhadiah yang sedang berlangsung.",

        "booster-notifikasi":
            "Tempat menerima informasi dan notifikasi khusus yang berkaitan dengan Booster nanZ.",

        "req-role-booster":
            "Tempat mengajukan permintaan untuk mendapatkan role Booster sesuai ketentuan yang berlaku.",

        "perpisahan":
            "Tempat memberikan ucapan dan pesan kepada murid atau staff yang akan meninggalkan nanZ.",


        # =====================================================
        # HALAMAN SEKOLAH
        # =====================================================

        "ruang-ngobrol":
            "Tempat untuk berbincang santai, berkenalan, dan berinteraksi dengan murid lainnya.",

        "bahas-rp":
            "Tempat berdiskusi dan berbagi hal seputar Roleplay bersama murid lainnya.",

        "ulang-tahun":
            "Tempat merayakan dan memberikan ucapan ulang tahun kepada murid nanZ.",

        "pesan-rahasia":
            "Tempat mengirimkan pesan secara anonim tanpa menampilkan identitas pengirim.",

        "setup-kata":
            "Tempat mengatur dan menggunakan berbagai fitur yang berkaitan dengan kata di nanZ.",

        "pojok-kata":
            "Tempat berbagi kata, cerita singkat, pemikiran, atau pesan yang ingin disampaikan.",


        # =====================================================
        # RUANG KELAS
        # =====================================================

        "tanya-ai":
            "Tempat bertanya kepada AI nanZ untuk mendapatkan bantuan, informasi, atau jawaban atas pertanyaan.",

        "kelas-umum":
            "Tempat berbagi materi, pengetahuan, dan pembahasan umum yang dapat dipelajari bersama.",

        "info-menarik":
            "Tempat menemukan berbagai fakta, informasi unik, dan hal menarik untuk diketahui.",


        # =====================================================
        # RUANG VIP OWNER
        # =====================================================

        "streaming-youtube":
            "Tempat mendapatkan informasi mengenai jadwal dan kegiatan streaming YouTube dari Guru Besar.",

        "donasi-penonton":
            "Tempat memberikan dukungan atau donasi kepada kegiatan dan konten yang dibuat oleh Guru Besar.",


        # =====================================================
        # RUANG KREATIVITAS
        # =====================================================

        "berbagi-konten":
            "Tempat membagikan berbagai konten, hasil karya, atau kreativitas yang ingin diperlihatkan kepada murid lainnya.",

        "daftar-event":
            "Tempat melihat informasi event yang tersedia sekaligus melakukan pendaftaran untuk ikut berpartisipasi.",

        "galeri-siswa":
            "Tempat memamerkan dan menikmati berbagai karya kreatif yang dibuat oleh murid nanZ.",


        # =====================================================
        # ZONA PERMAINAN BOT
        # =====================================================

        "perintah-bot":
            "Tempat menjalankan berbagai command bot yang tersedia untuk digunakan oleh murid nanZ.",

        "owo¹":
            "Tempat memainkan berbagai fitur permainan OwO bersama murid lainnya.",

        "owo²":
            "Tempat memainkan berbagai fitur permainan OwO bersama murid lainnya.",

        "owo³":
            "Tempat memainkan berbagai fitur permainan OwO bersama murid lainnya.",

        "tebak-bendera":
            "Tempat bermain tebak-tebakan bendera dan menguji pengetahuan tentang negara di dunia.",

        "ethera-bot":
            "Tempat memainkan berbagai permainan dan fitur yang tersedia dari Ethera Bot.",

        "area-mancing":
            "Tempat menggunakan fitur memancing dan menjalankan berbagai aktivitas yang berkaitan dengan fishing.",


        # =====================================================
        # ZONA PERMAINAN
        # =====================================================

        "dokumentasi-game":
            "Tempat membagikan screenshot, video, atau dokumentasi dari game yang sedang dimainkan.",

        "bermain game":
            "Voice channel untuk bermain game dan berkomunikasi bersama murid lainnya.",


        # =====================================================
        # RUANG BK
        # =====================================================

        "pusat-bantuan":
            "Tempat mencari bantuan, menyampaikan kendala, atau mendapatkan arahan mengenai masalah di nanZ.",

        "curhat bk":
            "Voice channel untuk bercerita, mencurahkan isi hati, atau berbicara secara lebih pribadi.",


        # =====================================================
        # RUANG NOBAR
        # =====================================================

        "vote-film":
            "Tempat memberikan pilihan dan menentukan film yang akan ditonton bersama dalam kegiatan nobar.",

        "diskusi-film":
            "Tempat membahas film, memberikan pendapat, dan berdiskusi mengenai tontonan bersama.",

        "nobar":
            "Voice channel yang digunakan untuk menikmati kegiatan nonton bersama murid nanZ.",


        # =====================================================
        # RUANG TEATER
        # =====================================================

        "podcast":
            "Voice channel untuk podcast, bincang santai, dan berbagai percakapan bersama murid lainnya.",

        "games":
            "Voice channel untuk bermain berbagai permainan dan bersenang-senang bersama murid nanZ.",


        # =====================================================
        # RUANG DONATUR
        # =====================================================

        "info-donasi":
            "Tempat melihat informasi mengenai donasi, dukungan, dan hal yang berkaitan dengan donatur nanZ.",

        "area-donasi":
            "Tempat khusus bagi donatur untuk beraktivitas dan berinteraksi di area yang telah disediakan.",

        "top-donatur":
            "Tempat melihat daftar murid dengan kontribusi donasi tertinggi di nanZ.",

        "interface-vip":
            "Tempat mengakses informasi dan fasilitas khusus yang tersedia untuk murid dengan akses VIP.",

        "custom room vip":
            "Voice channel khusus VIP yang dapat digunakan untuk berbincang atau beraktivitas bersama.",


        # =====================================================
        # AREA SEKOLAH
        # =====================================================

        "pengaturan-voice":
            "Tempat mengatur berbagai kebutuhan voice channel sesuai fitur yang tersedia di nanZ.",

        "daftar-bot-music":
            "Tempat melihat daftar bot musik yang dapat digunakan untuk menemani aktivitas di voice channel.",

        "girls corners":
            "Voice channel khusus siswi untuk berbincang dan melakukan aktivitas bersama.",

        "obrolan terbuka":
            "Voice channel umum yang dapat digunakan murid untuk berbincang dan bersosialisasi bersama.",

        "custom room 1":
            "Voice channel custom yang dapat digunakan untuk membuat ruang obrolan bersama.",

        "custom room 2":
            "Voice channel custom yang dapat digunakan untuk membuat ruang obrolan bersama.",
    }

    # =========================================================
    # NORMALIZE NAME
    # =========================================================

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Membersihkan nama channel dari:
        - Custom Discord Emoji
        - Unicode Emoji
        - Dekorasi
        - Separator
        - Backtick

        Contoh:

        🎙️・Bermain Game
        -> bermain game

        💬・🗨️﹕ruang-ngobrol
        -> ruang-ngobrol
        """

        if not name:
            return ""

        # Case insensitive
        name = name.casefold()

        # -----------------------------------------------------
        # Custom Discord Emoji
        # <:nama:id>
        # <a:nama:id>
        # -----------------------------------------------------

        name = re.sub(
            r"<a?:\w+:\d+>",
            "",
            name
        )

        # -----------------------------------------------------
        # Unicode Emoji
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # Dekorasi / separator
        # -----------------------------------------------------

        name = re.sub(
            r"[╭╮╰╯┇┆┊┋│┃"
            r"━─═╍╾╼"
            r"➜➤➢➣➥➦➧➨"
            r"・﹕:|/\\]+",
            " ",
            name
        )

        # Hapus backtick
        name = name.replace("`", "")

        # Rapikan spasi
        name = re.sub(
            r"\s+",
            " ",
            name
        )

        return name.strip()

    # =========================================================
    # CHECK COMMAND ACCESS
    # =========================================================

    def has_member_role(
        self,
        member: discord.Member
    ) -> bool:

        role_ids = {
            role.id
            for role in member.roles
        }

        return (
            self.MURID_ROLE_ID in role_ids
            or self.CALON_MURID_ROLE_ID in role_ids
        )

    # =========================================================
    # CHECK CHANNEL ACCESS
    # =========================================================

    def can_murid_view_channel(
        self,
        guild: discord.Guild,
        channel
    ) -> bool:
        """
        Channel ditampilkan jika:

        Murid bisa View Channel
        ATAU
        Calon Murid bisa View Channel.
        """

        murid_role = guild.get_role(
            self.MURID_ROLE_ID
        )

        calon_murid_role = guild.get_role(
            self.CALON_MURID_ROLE_ID
        )

        if not murid_role and not calon_murid_role:
            return False

        # -----------------------------------------------------
        # Cek Murid
        # -----------------------------------------------------

        if murid_role:

            permissions = channel.permissions_for(
                murid_role
            )

            if permissions.view_channel:
                return True

        # -----------------------------------------------------
        # Cek Calon Murid
        # -----------------------------------------------------

        if calon_murid_role:

            permissions = channel.permissions_for(
                calon_murid_role
            )

            if permissions.view_channel:
                return True

        return False

    # =========================================================
    # GET CHANNEL DESCRIPTION
    # =========================================================

    def get_channel_description(
        self,
        channel_name: str
    ) -> str:

        normalized = self.normalize_name(
            channel_name
        )

        # Direct lookup
        if normalized in self.CHANNEL_DESCRIPTIONS:
            return self.CHANNEL_DESCRIPTIONS[
                normalized
            ]

        # Fallback normalization
        for key, description in self.CHANNEL_DESCRIPTIONS.items():

            if self.normalize_name(key) == normalized:
                return description

        return "Belum ada deskripsi."

    # =========================================================
    # GET CUSTOM EMOJI
    # =========================================================

    def get_custom_emoji(
        self,
        guild: discord.Guild,
        emoji_id: int
    ):

        return guild.get_emoji(
            emoji_id
        )

    # =========================================================
    # BUILD CHANNEL LINE
    # =========================================================

    def build_channel_line(
        self,
        channel,
        blue_arrow
    ) -> str:

        if blue_arrow:
            arrow = str(
                blue_arrow
            )
        else:
            arrow = "🔵"

        description = (
            self.get_channel_description(
                channel.name
            )
        )

        return (
            f"{arrow} {channel.mention}\n"
            f"> {description}"
        )

    # =========================================================
    # SORT CATEGORY
    # =========================================================

    @staticmethod
    def sort_categories_discord_order(
        categories
    ):
        """
        Mengurutkan kategori berdasarkan posisi asli
        di server Discord.

        Tidak berdasarkan nama.
        """

        return sorted(
            categories,
            key=lambda category: (
                category.position,
                category.id
            )
        )

    # =========================================================
    # SORT CHANNEL
    # =========================================================

    @staticmethod
    def sort_channels_discord_order(
        channels
    ):
        """
        Mengurutkan channel berdasarkan posisi asli
        di dalam server Discord.

        Tidak berdasarkan nama.
        """

        return sorted(
            channels,
            key=lambda channel: (
                channel.position,
                channel.id
            )
        )

    # =========================================================
    # SEND CATEGORY
    # =========================================================

    async def send_category(
        self,
        ctx: commands.Context,
        category,
        visible_channels,
        blue_arrow
    ):
        """
        Format:

        **NAMA KATEGORI**
        🔵 #channel
        > deskripsi
        🔵 #channel
        > deskripsi
        """

        # =====================================================
        # Pastikan channel mengikuti posisi Discord
        # =====================================================

        visible_channels = (
            self.sort_channels_discord_order(
                visible_channels
            )
        )

        # =====================================================
        # Embed awal
        # =====================================================

        embed = discord.Embed(
            color=discord.Color.blurple()
        )

        embed.description = (
            f"**{category.name}**"
        )

        # =====================================================
        # CHANNEL
        # =====================================================

        for channel in visible_channels:

            channel_text = (
                self.build_channel_line(
                    channel,
                    blue_arrow
                )
            )

            # Antar-channel hanya satu newline
            new_description = (
                embed.description
                + "\n"
                + channel_text
            )

            # -------------------------------------------------
            # Masih muat
            # -------------------------------------------------

            if len(new_description) <= self.MAX_DESCRIPTION_LENGTH:

                embed.description = (
                    new_description
                )

            # -------------------------------------------------
            # Embed penuh
            # -------------------------------------------------

            else:

                await ctx.send(
                    embed=embed
                )

                await asyncio.sleep(
                    self.SEND_DELAY
                )

                # Embed baru
                embed = discord.Embed(
                    color=discord.Color.blurple()
                )

                embed.description = (
                    f"**{category.name}**"
                    f"\n"
                    f"{channel_text}"
                )

        # =====================================================
        # Kirim embed terakhir
        # =====================================================

        if embed.description:

            await ctx.send(
                embed=embed
            )

    # =========================================================
    # CHANNEL GUIDE COMMAND
    # =========================================================

    @commands.command(
        name="channelguide",
        aliases=[
            "channel-guide",
            "guidechannel",
            "guide"
        ]
    )
    @commands.guild_only()
    async def channelguide(
        self,
        ctx: commands.Context
    ):

        # =====================================================
        # CHECK USER
        # =====================================================

        if not isinstance(
            ctx.author,
            discord.Member
        ):
            return

        if not self.has_member_role(
            ctx.author
        ):

            await ctx.send(
                "Kamu tidak memiliki akses "
                "untuk melihat Channel Guide nanZ."
            )

            return

        guild = ctx.guild

        # =====================================================
        # GET CUSTOM EMOJI
        # =====================================================

        purple_arrow = (
            self.get_custom_emoji(
                guild,
                self.PURPLE_ARROW_ID
            )
        )

        blue_arrow = (
            self.get_custom_emoji(
                guild,
                self.BLUE_ARROW_ID
            )
        )

        # =====================================================
        # HEADER
        # =====================================================

        if purple_arrow:
            header_arrow = str(
                purple_arrow
            )
        else:
            header_arrow = "🟣"

        header_embed = discord.Embed(
            description=(
                f"{header_arrow} "
                f"**NANZ CHANNEL GUIDE**"
            ),
            color=discord.Color.blurple()
        )

        try:

            # =================================================
            # KIRIM HEADER
            # =================================================

            await ctx.send(
                embed=header_embed
            )

            await asyncio.sleep(
                self.SEND_DELAY
            )

            # =================================================
            # AMBIL SEMUA CATEGORY
            # =================================================

            categories = [
                category
                for category in guild.categories
                if category.id not in self.EXCLUDED_CATEGORY_IDS
            ]

            # =================================================
            # URUTAN CATEGORY
            # =================================================
            #
            # Mengikuti posisi kategori di Discord.
            #
            # =================================================

            categories = (
                self.sort_categories_discord_order(
                    categories
                )
            )

            # =================================================
            # PROCESS CATEGORY
            # =================================================

            for category in categories:

                # -------------------------------------------------
                # Cari channel yang dapat dilihat oleh:
                #
                # Murid OR Calon Murid
                # -------------------------------------------------

                visible_channels = [
                    channel
                    for channel in category.channels
                    if self.can_murid_view_channel(
                        guild,
                        channel
                    )
                ]

                # Tidak ada channel yang bisa dilihat
                if not visible_channels:
                    continue

                # -------------------------------------------------
                # Urutkan sesuai posisi asli Discord
                # -------------------------------------------------

                visible_channels = (
                    self.sort_channels_discord_order(
                        visible_channels
                    )
                )

                # -------------------------------------------------
                # Kirim kategori
                # -------------------------------------------------

                await self.send_category(
                    ctx,
                    category,
                    visible_channels,
                    blue_arrow
                )

                await asyncio.sleep(
                    self.SEND_DELAY
                )

        # =====================================================
        # HTTP ERROR
        # =====================================================

        except discord.HTTPException as e:

            print(
                f"[ChannelGuide] HTTP Error: {e}"
            )

        # =====================================================
        # GENERAL ERROR
        # =====================================================

        except Exception as e:

            print(
                f"[ChannelGuide] Unexpected Error: {e}"
            )

    # =========================================================
    # ERROR HANDLER
    # =========================================================

    @channelguide.error
    async def channelguide_error(
        self,
        ctx: commands.Context,
        error
    ):

        if isinstance(
            error,
            commands.NoPrivateMessage
        ):
            return

        print(
            f"[ChannelGuide] Command Error: {error}"
        )


# =============================================================
# SETUP
# =============================================================

async def setup(bot):
    await bot.add_cog(
        NanzChannelGuide(bot)
    )