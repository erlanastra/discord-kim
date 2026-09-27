import asyncio
import re

import discord
from discord.ext import commands


class NanzChannelGuide(commands.Cog):
    """
    NANZ CHANNEL GUIDE

    Fitur:
    - Deskripsi kategori hardcode di Python
    - Deskripsi channel hardcode di Python
    - Auto-normalize nama channel
    - Emoji dan dekorasi nama channel diabaikan
    - Tidak menggunakan database
    - Tidak menggunakan JSON
    - Tidak menggunakan panel
    - Tidak menggunakan modal
    - Tidak menggunakan search

    LOGIKA AKSES:
    - Command hanya dapat digunakan oleh Murid / Calon Murid
    - Channel Guide hanya menampilkan channel yang memiliki
      View Channel untuk Murid / Calon Murid
    """

    # ============================================================
    # ROLE NANZ
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
    # BATAS DESCRIPTION EMBED
    # ============================================================

    MAX_DESCRIPTION_LENGTH = 3900

    # ============================================================
    # DESKRIPSI CATEGORY
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
    # NORMALIZE NAMA
    # ============================================================

    @staticmethod
    def normalize_name(name: str) -> str:

        if not name:
            return ""

        # Case insensitive
        name = name.casefold()

        # --------------------------------------------------------
        # Hapus custom emoji Discord
        # <:nama:id>
        # <a:nama:id>
        # --------------------------------------------------------

        name = re.sub(
            r"<a?:\w+:\d+>",
            "",
            name
        )

        # --------------------------------------------------------
        # Hapus Unicode emoji
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
        # Hapus dekorasi
        # --------------------------------------------------------

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

    # ============================================================
    # CEK USER PUNYA ROLE MURID / CALON MURID
    # ============================================================

    def has_member_role(self, member):

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
    # CEK APAKAH MURID / CALON MURID BISA VIEW CHANNEL
    # ============================================================

    def can_murid_view_channel(self, guild, channel):

        """
        Mengecek View Channel berdasarkan ROLE Murid dan
        Calon Murid, bukan berdasarkan user yang menjalankan
        command.

        Jika salah satu role memiliki akses View Channel,
        channel akan ditampilkan.
        """

        murid_role = guild.get_role(
            self.MURID_ROLE_ID
        )

        calon_murid_role = guild.get_role(
            self.CALON_MURID_ROLE_ID
        )

        # --------------------------------------------------------
        # Tidak menemukan role
        # --------------------------------------------------------

        if not murid_role and not calon_murid_role:
            return False

        # --------------------------------------------------------
        # Cek Murid
        # --------------------------------------------------------

        if murid_role:

            permissions = channel.permissions_for(
                murid_role
            )

            if permissions.view_channel:
                return True

        # --------------------------------------------------------
        # Cek Calon Murid
        # --------------------------------------------------------

        if calon_murid_role:

            permissions = channel.permissions_for(
                calon_murid_role
            )

            if permissions.view_channel:
                return True

        return False

    # ============================================================
    # GET CHANNEL DESCRIPTION
    # ============================================================

    def get_channel_description(self, channel):

        normalized_name = self.normalize_name(
            channel.name
        )

        # Direct lookup
        if normalized_name in self.CHANNEL_DESCRIPTIONS:

            return self.CHANNEL_DESCRIPTIONS[
                normalized_name
            ]

        # Fallback
        for name, description in self.CHANNEL_DESCRIPTIONS.items():

            if (
                self.normalize_name(name)
                == normalized_name
            ):
                return description

        return None

    # ============================================================
    # GET CATEGORY DESCRIPTION
    # ============================================================

    def get_category_description(self, category):

        if not category:
            return ""

        normalized_name = self.normalize_name(
            category.name
        )

        # Direct lookup
        if normalized_name in self.CATEGORY_DESCRIPTIONS:

            return self.CATEGORY_DESCRIPTIONS[
                normalized_name
            ]

        # Fallback
        for name, description in self.CATEGORY_DESCRIPTIONS.items():

            if (
                self.normalize_name(name)
                == normalized_name
            ):
                return description

        return ""

    # ============================================================
    # CHANNEL ICON
    # ============================================================

    @staticmethod
    def get_channel_icon(channel):

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

    # ============================================================
    # CUSTOM EMOJI
    # ============================================================

    @staticmethod
    def get_custom_emoji(
        guild,
        emoji_id,
        fallback
    ):

        emoji = guild.get_emoji(
            emoji_id
        )

        if emoji:
            return str(emoji)

        return fallback

    # ============================================================
    # BUILD CHANNEL LINE
    # ============================================================

    def build_channel_line(
        self,
        channel,
        arrow_blue
    ):

        icon = self.get_channel_icon(
            channel
        )

        description = self.get_channel_description(
            channel
        )

        if not description:
            description = "Belum ada deskripsi."

        return (
            f"{arrow_blue} {icon} "
            f"{channel.mention}\n"
            f"> {description}"
        )

    # ============================================================
    # CREATE EMBED
    # ============================================================

    @staticmethod
    def create_embed(
        arrow_purple
    ):

        return discord.Embed(
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

    # ============================================================
    # TAMBAHKAN TEXT KE EMBED
    # ============================================================

    def add_text_to_embed(
        self,
        embeds,
        current_embed,
        text
    ):

        current_description = (
            current_embed.description
            or ""
        )

        # --------------------------------------------------------
        # Kalau masih muat
        # --------------------------------------------------------

        if (
            len(current_description)
            + len(text)
            <= self.MAX_DESCRIPTION_LENGTH
        ):

            current_embed.description = (
                current_description
                + text
            )

            return current_embed

        # --------------------------------------------------------
        # Simpan embed lama
        # --------------------------------------------------------

        embeds.append(
            current_embed
        )

        # --------------------------------------------------------
        # Buat embed baru
        # --------------------------------------------------------

        new_embed = self.create_embed(
            self.current_arrow_purple
        )

        # --------------------------------------------------------
        # Kalau text masih muat
        # --------------------------------------------------------

        if len(text) <= self.MAX_DESCRIPTION_LENGTH:

            new_embed.description = text

            return new_embed

        # --------------------------------------------------------
        # Safety split
        # --------------------------------------------------------

        chunks = []

        while len(text) > self.MAX_DESCRIPTION_LENGTH:

            split_at = text.rfind(
                "\n",
                0,
                self.MAX_DESCRIPTION_LENGTH
            )

            if split_at <= 0:

                split_at = (
                    self.MAX_DESCRIPTION_LENGTH
                )

            chunks.append(
                text[:split_at]
            )

            text = text[
                split_at:
            ].lstrip("\n")

        if text:
            chunks.append(text)

        new_embed.description = chunks[0]

        for chunk in chunks[1:]:

            embeds.append(
                new_embed
            )

            new_embed = self.create_embed(
                self.current_arrow_purple
            )

            new_embed.description = chunk

        return new_embed

    # ============================================================
    # COMMAND !CHANNELGUIDE
    # ============================================================

    @commands.command(
        name="channelguide"
    )
    @commands.guild_only()
    async def channelguide(
        self,
        ctx
    ):

        guild = ctx.guild

        # ========================================================
        # CEK ROLE USER
        # ========================================================

        if not self.has_member_role(
            ctx.author
        ):

            await ctx.send(
                "Kamu tidak memiliki akses untuk "
                "melihat Channel Guide nanZ."
            )

            return

        # ========================================================
        # CUSTOM ARROW
        # ========================================================

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

        self.current_arrow_purple = (
            arrow_purple
        )

        # ========================================================
        # AMBIL CATEGORY
        # ========================================================

        categories = []

        for category in guild.categories:

            # ----------------------------------------------------
            # Skip excluded category
            # ----------------------------------------------------

            if (
                category.id
                in self.EXCLUDED_CATEGORY_IDS
            ):
                continue

            # ----------------------------------------------------
            # Channel yang bisa dilihat Murid /
            # Calon Murid
            # ----------------------------------------------------

            visible_channels = []

            for channel in category.channels:

                if self.can_murid_view_channel(
                    guild,
                    channel
                ):

                    visible_channels.append(
                        channel
                    )

            # ----------------------------------------------------
            # Jika tidak ada channel yang bisa diakses
            # ----------------------------------------------------

            if not visible_channels:
                continue

            categories.append(
                (
                    category,
                    visible_channels
                )
            )

        # ========================================================
        # JIKA TIDAK ADA CATEGORY
        # ========================================================

        if not categories:

            await ctx.send(
                "Tidak ada channel yang dapat ditampilkan."
            )

            return

        # ========================================================
        # BUILD EMBEDS
        # ========================================================

        embeds = []

        current_embed = self.create_embed(
            arrow_purple
        )

        current_embed.description = (
            "Panduan channel untuk membantu murid "
            "menemukan ruang yang sesuai."
        )

        # ========================================================
        # CATEGORY LOOP
        # ========================================================

        for category, channels in categories:

            category_description = (
                self.get_category_description(
                    category
                )
            )

            # ----------------------------------------------------
            # Category header
            # ----------------------------------------------------

            category_header = (
                f"\n\n"
                f"{arrow_purple} ▬『 "
                f"{category.name} "
                f"』▬"
            )

            if category_description:

                category_header += (
                    f"\n> "
                    f"{category_description}"
                )

            category_header += "\n"

            # ----------------------------------------------------
            # Add category
            # ----------------------------------------------------

            current_embed = (
                self.add_text_to_embed(
                    embeds,
                    current_embed,
                    category_header
                )
            )

            # ----------------------------------------------------
            # Add channel
            # ----------------------------------------------------

            for channel in channels:

                channel_line = (
                    self.build_channel_line(
                        channel,
                        arrow_blue
                    )
                    + "\n"
                )

                current_embed = (
                    self.add_text_to_embed(
                        embeds,
                        current_embed,
                        channel_line
                    )
                )

        # ========================================================
        # SIMPAN EMBED TERAKHIR
        # ========================================================

        if (
            current_embed.description
            and current_embed not in embeds
        ):

            embeds.append(
                current_embed
            )

        # ========================================================
        # FOOTER
        # ========================================================

        for index, embed in enumerate(
            embeds
        ):

            embed.set_footer(
                text=(
                    f"nanZ Server • Stay Solid! "
                    f"• Halaman "
                    f"{index + 1}/{len(embeds)}"
                )
            )

        # ========================================================
        # SEND EMBEDS
        # ========================================================

        for index, embed in enumerate(
            embeds
        ):

            try:

                await ctx.send(
                    embed=embed
                )

            except discord.HTTPException as e:

                print(
                    f"[NANZ CHANNEL GUIDE] "
                    f"Gagal mengirim embed "
                    f"{index + 1}: {e}"
                )

                await asyncio.sleep(
                    2
                )

                try:

                    await ctx.send(
                        embed=embed
                    )

                except discord.HTTPException as retry_error:

                    print(
                        "[NANZ CHANNEL GUIDE] "
                        f"Retry gagal: "
                        f"{retry_error}"
                    )

            # ----------------------------------------------------
            # Jeda antar pesan
            # ----------------------------------------------------

            await asyncio.sleep(
                1.0
            )


# ================================================================
# SETUP
# ================================================================

async def setup(bot):

    await bot.add_cog(
        NanzChannelGuide(bot)
    )