import asyncio
import re

import discord
from discord.ext import commands


class NanzChannelGuide(commands.Cog):
    # =========================================================
    # CONFIG
    # =========================================================

    # Category yang tidak ingin ditampilkan di Channel Guide
    EXCLUDED_CATEGORY_IDS = {
        1416639085757468784,
        1485115656616546425,
        1549446088992489473,
        1489206200925946098,
        1407220284217360434,
        1486913064564555786,
        1513028445423009923,
    }

    # Role yang diperbolehkan menggunakan !channelguide
    MURID_ROLE_ID = 1453095603008442510
    CALON_MURID_ROLE_ID = 1504467138440597604

    # Emoji khas nanZ
    PURPLE_ARROW_ID = 1512787191234035803
    BLUE_ARROW_ID = 1512787254312042496

    # Batas aman description Embed Discord
    MAX_DESCRIPTION_LENGTH = 3900

    # =========================================================
    # CHANNEL DESCRIPTIONS
    # =========================================================

    CHANNEL_DESCRIPTIONS = {

        # =====================================================
        # MADING SEKOLAH
        # =====================================================

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


        # =====================================================
        # HALAMAN SEKOLAH
        # =====================================================

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


        # =====================================================
        # RUANG KELAS
        # =====================================================

        "tanya-ai":
            "Bertanya kepada AI nanZ.",

        "kelas-umum":
            "Materi dan pengetahuan umum.",

        "info-menarik":
            "Fakta dan informasi menarik.",


        # =====================================================
        # RUANG VIP OWNER
        # =====================================================

        "streaming-youtube":
            "Info streaming YouTube.",

        "donasi-penonton":
            "Dukungan dan donasi penonton.",


        # =====================================================
        # RUANG KREATIVITAS
        # =====================================================

        "berbagi-konten":
            "Berbagi konten dan karya.",

        "daftar-event":
            "Info dan pendaftaran event.",

        "galeri-siswa":
            "Galeri karya murid.",


        # =====================================================
        # ZONA PERMAINAN BOT
        # =====================================================

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


        # =====================================================
        # ZONA PERMAINAN
        # =====================================================

        "dokumentasi-game":
            "Berbagi dokumentasi game.",

        "bermain game":
            "Voice untuk bermain bersama.",


        # =====================================================
        # RUANG BK
        # =====================================================

        "pusat-bantuan":
            "Pusat bantuan murid.",

        "curhat bk":
            "Voice untuk curhat.",


        # =====================================================
        # RUANG NOBAR
        # =====================================================

        "vote-film":
            "Memilih film nobar.",

        "diskusi-film":
            "Diskusi seputar film.",

        "nobar":
            "Voice untuk nonton bersama.",


        # =====================================================
        # RUANG TEATER
        # =====================================================

        "podcast":
            "Voice untuk podcast dan bincang.",

        "games":
            "Voice untuk bermain bersama.",


        # =====================================================
        # RUANG DONATUR
        # =====================================================

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


        # =====================================================
        # AREA SEKOLAH
        # =====================================================

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
    # NORMALIZE NAME
    # =========================================================

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Membersihkan nama channel dari:
        - Emoji Unicode
        - Custom Discord Emoji
        - Dekorasi
        - Backtick
        - Karakter pemisah

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
    # COMMAND ACCESS
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
    # CHANNEL VIEW PERMISSION
    # =========================================================

    def can_murid_view_channel(
        self,
        guild: discord.Guild,
        channel
    ) -> bool:
        """
        Channel ditampilkan apabila salah satu dari:

        Murid -> View Channel
        Calon Murid -> View Channel

        Jadi akses Channel Guide tidak bergantung pada
        permission user yang menjalankan command.
        """

        murid_role = guild.get_role(
            self.MURID_ROLE_ID
        )

        calon_murid_role = guild.get_role(
            self.CALON_MURID_ROLE_ID
        )

        if not murid_role and not calon_murid_role:
            return False

        # Cek role Murid
        if murid_role:

            permissions = channel.permissions_for(
                murid_role
            )

            if permissions.view_channel:
                return True

        # Cek role Calon Murid
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

        # Jika belum ada mapping
        return "Belum ada deskripsi."

    # =========================================================
    # CUSTOM EMOJI
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
    # BUILD CHANNEL
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
            f"> {description}\n"
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
        Mengirim satu kategori.

        Nama kategori hanya bold.
        Tidak ada deskripsi kategori.

        Urutan channel mengikuti posisi asli Discord.
        """

        # =====================================================
        # CATEGORY TITLE
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

            new_description = (
                embed.description
                + "\n\n"
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
            # Sudah penuh
            # -------------------------------------------------

            else:

                await ctx.send(
                    embed=embed
                )

                await asyncio.sleep(1)

                # Embed baru tetap menggunakan nama kategori
                embed = discord.Embed(
                    color=discord.Color.blurple()
                )

                embed.description = (
                    f"**{category.name}**"
                    f"\n\n"
                    f"{channel_text}"
                )

        # =====================================================
        # SEND LAST EMBED
        # =====================================================

        if embed.description:
            await ctx.send(
                embed=embed
            )

    # =========================================================
    # !CHANNELGUIDE
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
        # CHECK USER ROLE
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
        # GET EMOJI
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

            # Kirim header
            await ctx.send(
                embed=header_embed
            )

            await asyncio.sleep(1)

            # =================================================
            # CATEGORY
            # =================================================
            #
            # guild.categories mengikuti posisi category
            # yang ada di server Discord.
            #
            # Kita TIDAK sort berdasarkan nama.
            #
            # =================================================

            categories = [
                category
                for category in guild.categories
                if category.id not in self.EXCLUDED_CATEGORY_IDS
            ]

            # Posisi asli kategori Discord
            categories.sort(
                key=lambda category: category.position
            )

            # =================================================
            # PROCESS CATEGORY
            # =================================================

            for category in categories:

                # -------------------------------------------------
                # Cari channel yang bisa dilihat Murid /
                # Calon Murid.
                # -------------------------------------------------

                visible_channels = [
                    channel
                    for channel in category.channels
                    if self.can_murid_view_channel(
                        guild,
                        channel
                    )
                ]

                # Kalau tidak ada channel yang bisa dilihat,
                # kategori tidak ditampilkan.
                if not visible_channels:
                    continue

                # -------------------------------------------------
                # Urutan channel mengikuti posisi asli Discord.
                # -------------------------------------------------

                visible_channels.sort(
                    key=lambda channel: channel.position
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

                # Delay agar tidak terlalu cepat mengirim embed
                await asyncio.sleep(1)

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