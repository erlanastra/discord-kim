import asyncio
import re

import discord
from discord.ext import commands


class NanzChannelGuide(commands.Cog):
    # =========================================================
    # CONFIG
    # =========================================================

    EXCLUDED_CATEGORY_IDS = {
        1416639085757468784,
        1485115656616546425,
        1549446088992489473,
        1489206200925946098,
        1407220284217360434,
        1486913064564555786,
        1513028445423009923,
    }

    # Role yang boleh menjalankan command
    MURID_ROLE_ID = 1453095603008442510
    CALON_MURID_ROLE_ID = 1504467138440597604

    # Custom emoji nanZ
    PURPLE_ARROW_ID = 1512787191234035803
    BLUE_ARROW_ID = 1512787254312042496

    # Discord embed description maksimal 4096 karakter.
    # Kita gunakan buffer supaya aman.
    MAX_DESCRIPTION_LENGTH = 3900

    # =========================================================
    # CATEGORY DESCRIPTIONS
    # =========================================================

    CATEGORY_DESCRIPTIONS = {
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

        "ZONA PERMAINAN BOT":
            "Area bermain menggunakan bot.",

        "ZONA PERMAINAN":
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

    # =========================================================
    # CHANNEL DESCRIPTIONS
    # =========================================================

    CHANNEL_DESCRIPTIONS = {

        # -----------------------------------------------------
        # MADING SEKOLAH
        # -----------------------------------------------------

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


        # -----------------------------------------------------
        # HALAMAN SEKOLAH
        # -----------------------------------------------------

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


        # -----------------------------------------------------
        # RUANG KELAS
        # -----------------------------------------------------

        "tanya-ai":
            "Bertanya kepada AI nanZ.",

        "kelas-umum":
            "Materi dan pengetahuan umum.",

        "info-menarik":
            "Fakta dan informasi menarik.",


        # -----------------------------------------------------
        # RUANG VIP OWNER
        # -----------------------------------------------------

        "streaming-youtube":
            "Info streaming YouTube.",

        "donasi-penonton":
            "Dukungan dan donasi penonton.",


        # -----------------------------------------------------
        # RUANG KREATIVITAS
        # -----------------------------------------------------

        "berbagi-konten":
            "Berbagi konten dan karya.",

        "daftar-event":
            "Info dan pendaftaran event.",

        "galeri-siswa":
            "Galeri karya murid.",


        # -----------------------------------------------------
        # ZONA PERMAINAN BOT
        # -----------------------------------------------------

        "perintah-bot":
            "Menjalankan command bot.",

        "owo1":
            "Area permainan OwO.",

        "owo2":
            "Area permainan OwO.",

        "owo3":
            "Area permainan OwO.",

        "tebak-bendera":
            "Tebak bendera negara.",

        "ethera-bot":
            "Permainan Ethera Bot.",

        "area-mancing":
            "Aktivitas memancing.",


        # -----------------------------------------------------
        # ZONA PERMAINAN
        # -----------------------------------------------------

        "dokumentasi-game":
            "Berbagi dokumentasi game.",

        "bermain game":
            "Voice untuk bermain bersama.",


        # -----------------------------------------------------
        # RUANG BK
        # -----------------------------------------------------

        "pusat-bantuan":
            "Pusat bantuan murid.",

        "curhat bk":
            "Voice untuk curhat.",


        # -----------------------------------------------------
        # RUANG NOBAR
        # -----------------------------------------------------

        "vote-film":
            "Memilih film nobar.",

        "diskusi-film":
            "Diskusi seputar film.",

        "nobar":
            "Voice untuk nonton bersama.",


        # -----------------------------------------------------
        # RUANG TEATER
        # -----------------------------------------------------

        "podcast":
            "Voice untuk podcast dan bincang.",

        "games":
            "Voice untuk bermain bersama.",


        # -----------------------------------------------------
        # RUANG DONATUR
        # -----------------------------------------------------

        "info-donasi":
            "Informasi donasi.",

        "area-donasi":
            "Area aktivitas donatur.",

        "top-donatur":
            "Daftar top donatur.",

        "interface-vip":
            "Akses fasilitas VIP.",

        "custom room vip":
            "Voice khusus VIP.",


        # -----------------------------------------------------
        # AREA SEKOLAH
        # -----------------------------------------------------

        "pengaturan-voice":
            "Pengaturan voice room.",

        "daftar-bot-music":
            "Daftar bot musik.",

        "girls corners":
            "Voice khusus siswi.",

        "obrolan terbuka":
            "Voice umum untuk murid.",

        "custom room 1":
            "Voice custom.",

        "custom room 2":
            "Voice custom.",
    }

    # =========================================================
    # NORMALIZER
    # =========================================================

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Menyamakan nama channel/category agar tidak perlu
        menggunakan ID.

        Contoh:

        🎙️・Bermain Game
        -> bermain game

        💬・🗨️﹕ruang-ngobrol
        -> ruang-ngobrol

        <:emoji:123456789>・tata-tertib
        -> tata-tertib
        """

        if not name:
            return ""

        name = name.casefold()

        # -----------------------------------------------------
        # Hapus custom Discord emoji
        # <:nama:id>
        # <a:nama:id>
        # -----------------------------------------------------

        name = re.sub(
            r"<a?:\w+:\d+>",
            "",
            name
        )

        # -----------------------------------------------------
        # Hapus Unicode emoji
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
        # Hapus / ubah dekorasi
        # -----------------------------------------------------

        name = re.sub(
            r"[╭╮╰╯┇┆┊┋│┃"
            r"━─═╍╾╼"
            r"➜➤➢➣➥➦➧➨"
            r"・﹕:|/\\]+",
            " ",
            name
        )

        # Backtick
        name = name.replace("`", "")

        # Rapikan spasi
        name = re.sub(
            r"\s+",
            " ",
            name
        )

        return name.strip()

    # =========================================================
    # ROLE CHECK
    # =========================================================

    def has_member_role(self, member: discord.Member) -> bool:
        """
        Command hanya bisa digunakan oleh:
        - Murid
        - Calon Murid
        """

        role_ids = {
            role.id
            for role in member.roles
        }

        return (
            self.MURID_ROLE_ID in role_ids
            or self.CALON_MURID_ROLE_ID in role_ids
        )

    # =========================================================
    # CHANNEL ACCESS CHECK
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
        Calon Murid bisa View Channel
        """

        murid_role = guild.get_role(
            self.MURID_ROLE_ID
        )

        calon_murid_role = guild.get_role(
            self.CALON_MURID_ROLE_ID
        )

        if not murid_role and not calon_murid_role:
            return False

        # Cek Murid
        if murid_role:

            permissions = channel.permissions_for(
                murid_role
            )

            if permissions.view_channel:
                return True

        # Cek Calon Murid
        if calon_murid_role:

            permissions = channel.permissions_for(
                calon_murid_role
            )

            if permissions.view_channel:
                return True

        return False

    # =========================================================
    # DESCRIPTION
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

        # Fallback compare
        for key, description in self.CHANNEL_DESCRIPTIONS.items():

            if self.normalize_name(key) == normalized:
                return description

        return "Belum ada deskripsi."

    def get_category_description(
        self,
        category_name: str
    ) -> str:

        normalized = self.normalize_name(
            category_name
        )

        if normalized in self.CATEGORY_DESCRIPTIONS:
            return self.CATEGORY_DESCRIPTIONS[
                normalized
            ]

        for key, description in self.CATEGORY_DESCRIPTIONS.items():

            if self.normalize_name(key) == normalized:
                return description

        return "Belum ada deskripsi."

    # =========================================================
    # EMOJI
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
    # CHANNEL LINE
    # =========================================================

    def build_channel_line(
        self,
        channel,
        blue_arrow
    ) -> str:

        description = self.get_channel_description(
            channel.name
        )

        if blue_arrow:
            arrow = str(blue_arrow)
        else:
            arrow = "🔵"

        return (
            f"{arrow} {channel.mention}\n"
            f"> {description}\n"
        )

    # =========================================================
    # EMBED TEXT
    # =========================================================

    @staticmethod
    def add_text_to_embed(
        embed: discord.Embed,
        text: str,
        max_length: int = 3900
    ):
        """
        Menambahkan text ke embed.
        Jika melewati batas, dikembalikan sebagai chunk baru.
        """

        if not embed.description:
            embed.description = text
            return None

        new_description = (
            embed.description
            + "\n"
            + text
        )

        if len(new_description) <= max_length:
            embed.description = new_description
            return None

        return text

    # =========================================================
    # CREATE EMBED
    # =========================================================

    def create_embed(
        self,
        category,
        blue_arrow
    ) -> discord.Embed:

        embed = discord.Embed(
            color=discord.Color.blurple()
        )

        # =====================================================
        # CATEGORY
        # HANYA BOLD
        # =====================================================

        category_title = (
            f"**{category.name}**"
        )

        category_description = (
            self.get_category_description(
                category.name
            )
        )

        embed.description = (
            f"{category_title}\n"
            f"> {category_description}\n"
        )

        # =====================================================
        # CHANNEL
        # =====================================================

        channels = sorted(
            [
                channel
                for channel in category.channels
                if self.can_murid_view_channel(
                    category.guild,
                    channel
                )
            ],
            key=lambda c: c.position
        )

        for channel in channels:

            channel_text = self.build_channel_line(
                channel,
                blue_arrow
            )

            new_text = self.add_text_to_embed(
                embed,
                channel_text,
                self.MAX_DESCRIPTION_LENGTH
            )

            if new_text is not None:
                break

        return embed

    # =========================================================
    # COMMAND
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
        """
        !channelguide

        Hanya Murid / Calon Murid yang dapat menjalankan
        command.

        Namun daftar channel berdasarkan permission role:
        Murid OR Calon Murid.
        """

        # =====================================================
        # CEK USER
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
        # CUSTOM EMOJI
        # =====================================================

        blue_arrow = self.get_custom_emoji(
            guild,
            self.BLUE_ARROW_ID
        )

        # =====================================================
        # AMBIL CATEGORY
        # =====================================================

        categories = [
            category
            for category in guild.categories
            if category.id not in self.EXCLUDED_CATEGORY_IDS
        ]

        # =====================================================
        # SORT CATEGORY SESUAI POSISI
        # =====================================================

        categories.sort(
            key=lambda category: category.position
        )

        # =====================================================
        # HEADER
        # =====================================================

        purple_arrow = self.get_custom_emoji(
            guild,
            self.PURPLE_ARROW_ID
        )

        if purple_arrow:
            header_arrow = str(
                purple_arrow
            )
        else:
            header_arrow = "🟣"

        header = discord.Embed(
            description=(
                f"{header_arrow} **NANZ CHANNEL GUIDE**"
            ),
            color=discord.Color.blurple()
        )

        try:

            await ctx.send(
                embed=header
            )

            await asyncio.sleep(1)

            # =================================================
            # SETIAP CATEGORY
            # =================================================

            for category in categories:

                # ---------------------------------------------
                # Hanya proses category yang memiliki channel
                # yang dapat dilihat Murid / Calon Murid.
                # ---------------------------------------------

                visible_channels = [
                    channel
                    for channel in category.channels
                    if self.can_murid_view_channel(
                        guild,
                        channel
                    )
                ]

                if not visible_channels:
                    continue

                visible_channels.sort(
                    key=lambda c: c.position
                )

                # ---------------------------------------------
                # Buat embed pertama
                # ---------------------------------------------

                embed = discord.Embed(
                    color=discord.Color.blurple()
                )

                category_title = (
                    f"**{category.name}**"
                )

                category_description = (
                    self.get_category_description(
                        category.name
                    )
                )

                embed.description = (
                    f"{category_title}\n"
                    f"> {category_description}\n"
                )

                # ---------------------------------------------
                # Tambahkan channel
                # ---------------------------------------------

                for channel in visible_channels:

                    channel_text = (
                        self.build_channel_line(
                            channel,
                            blue_arrow
                        )
                    )

                    # Jika masih muat
                    if len(
                        embed.description
                        + "\n"
                        + channel_text
                    ) <= self.MAX_DESCRIPTION_LENGTH:

                        embed.description += (
                            "\n"
                            + channel_text
                        )

                    else:

                        # Kirim embed sebelumnya
                        await ctx.send(
                            embed=embed
                        )

                        await asyncio.sleep(1)

                        # Buat embed baru
                        embed = discord.Embed(
                            color=discord.Color.blurple()
                        )

                        embed.description = (
                            f"**{category.name}**\n"
                        )

                        embed.description += (
                            "\n"
                            + channel_text
                        )

                # ---------------------------------------------
                # Kirim sisa embed
                # ---------------------------------------------

                if embed.description:

                    await ctx.send(
                        embed=embed
                    )

                    await asyncio.sleep(1)

        except discord.HTTPException as e:

            # Discord error
            print(
                f"[ChannelGuide] HTTP Error: {e}"
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


async def setup(bot):
    await bot.add_cog(
        NanzChannelGuide(bot)
    )