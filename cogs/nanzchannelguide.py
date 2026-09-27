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

    MURID_ROLE_ID = 1453095603008442510
    CALON_MURID_ROLE_ID = 1504467138440597604

    PURPLE_ARROW_ID = 1512787191234035803
    BLUE_ARROW_ID = 1512787254312042496

    MAX_DESCRIPTION_LENGTH = 3900
    SEND_DELAY = 1.0

    # =========================================================
    # CHANNEL DESCRIPTIONS
    # =========================================================

    CHANNEL_DESCRIPTIONS = {

        # MADING SEKOLAH

        "tata-tertib":
            "Tempat membaca dan memahami aturan yang berlaku di server nanZ.",

        "sambutan":
            "Tempat menyambut dan mengenalkan informasi penting bagi murid baru.",

        "atribut":
            "Tempat melihat informasi role, atribut, dan identitas yang tersedia di nanZ.",

        "staff-sekolah":
            "Tempat melihat daftar staff dan informasi kepengurusan nanZ.",

        "giveaway":
            "Tempat mendapatkan informasi giveaway dan kegiatan berhadiah.",

        "booster-notifikasi":
            "Tempat menerima informasi khusus mengenai Booster nanZ.",

        "req-role-booster":
            "Tempat mengajukan permintaan role Booster sesuai ketentuan.",

        "perpisahan":
            "Tempat memberikan ucapan dan pesan kepada murid atau staff yang meninggalkan nanZ.",


        # HALAMAN SEKOLAH

        "ruang-ngobrol":
            "Tempat berbincang santai, berkenalan, dan berinteraksi dengan murid lainnya.",

        "bahas-rp":
            "Tempat berdiskusi dan berbagi hal seputar Roleplay.",

        "ulang-tahun":
            "Tempat merayakan dan memberikan ucapan ulang tahun kepada murid nanZ.",

        "pesan-rahasia":
            "Tempat mengirimkan pesan secara anonim tanpa menampilkan identitas pengirim.",

        "setup-kata":
            "Tempat menggunakan fitur quote yang hasilnya ditampilkan di Pojok Kata.",

        "pojok-kata":
            "Tempat berbagi kutipan, cerita singkat, pemikiran, atau pesan.",


        # RUANG KELAS

        "tanya-ai":
            "Tempat bertanya kepada AI nanZ untuk mendapatkan bantuan dan informasi.",

        "kelas-umum":
            "Tempat berbagi materi, pengetahuan, dan pembahasan umum.",

        "info-menarik":
            "Tempat menemukan fakta, informasi unik, dan hal menarik.",


        # RUANG VIP OWNER

        "streaming-youtube":
            "Tempat mendapatkan informasi mengenai streaming YouTube dari Guru Besar.",

        "donasi-penonton":
            "Tempat memberikan dukungan atau donasi untuk konten Guru Besar.",


        # RUANG KREATIVITAS

        "berbagi-konten":
            "Tempat membagikan konten, hasil karya, dan kreativitas.",

        "daftar-event":
            "Tempat melihat informasi dan mendaftar berbagai event nanZ.",

        "galeri-siswa":
            "Tempat memamerkan dan menikmati karya kreatif murid nanZ.",


        # ZONA PERMAINAN BOT

        "perintah-bot":
            "Tempat menjalankan berbagai command bot yang tersedia di nanZ.",

        "owo¹":
            "Tempat memainkan berbagai fitur permainan OwO.",

        "owo²":
            "Tempat memainkan berbagai fitur permainan OwO.",

        "owo³":
            "Tempat memainkan berbagai fitur permainan OwO.",

        "tebak-bendera":
            "Tempat bermain tebak bendera dan menguji pengetahuan tentang negara.",

        "ethera-bot":
            "Tempat memainkan berbagai permainan dan fitur Ethera Bot.",

        "area-mancing":
            "Tempat menggunakan fitur memancing dan aktivitas fishing.",


        # ZONA PERMAINAN

        "dokumentasi-game":
            "Tempat membagikan screenshot, video, dan dokumentasi game.",

        "bermain game":
            "Voice channel untuk bermain game dan berkomunikasi bersama.",


        # RUANG BK

        "pusat-bantuan":
            "Tempat mencari bantuan dan menyampaikan kendala di nanZ.",

        "curhat bk":
            "Voice channel untuk bercerita dan berbicara secara lebih pribadi.",


        # RUANG NOBAR

        "vote-film":
            "Tempat memilih film yang akan ditonton bersama dalam event nobar.",

        "diskusi-film":
            "Tempat membahas film dan berdiskusi mengenai tontonan bersama.",

        "nobar":
            "Voice channel untuk pelaksanaan event nonton bersama.",


        # RUANG TEATER

        "podcast":
            "Voice channel untuk pelaksanaan event podcast dan bincang bersama.",

        "games":
            "Voice channel untuk pelaksanaan event games bersama murid nanZ.",


        # RUANG DONATUR

        "info-donasi":
            "Tempat melihat informasi mengenai donasi dan dukungan untuk nanZ.",

        "area-donasi":
            "Tempat khusus donatur untuk beraktivitas dan berinteraksi.",

        "top-donatur":
            "Tempat melihat daftar murid dengan kontribusi donasi tertinggi.",

        "interface-vip":
            "Tempat mengakses informasi dan fasilitas khusus VIP.",

        "custom room vip":
            "Voice channel khusus VIP untuk berbincang dan beraktivitas bersama.",


        # AREA SEKOLAH

        "pengaturan-voice":
            "Tempat mengatur berbagai kebutuhan voice channel di nanZ.",

        "daftar-bot-music":
            "Tempat melihat bot musik yang dapat digunakan di voice channel.",

        "girls corners":
            "Voice channel khusus siswi untuk berbincang dan beraktivitas bersama.",

        "obrolan terbuka":
            "Voice channel umum untuk berbincang dan bersosialisasi.",

        "custom room 1":
            "Voice channel custom untuk membuat ruang obrolan bersama.",

        "custom room 2":
            "Voice channel custom untuk membuat ruang obrolan bersama.",
    }

    # =========================================================
    # NORMALIZE CHANNEL NAME
    # =========================================================

    @staticmethod
    def normalize_name(name: str) -> str:

        if not name:
            return ""

        name = name.casefold()

        # Custom Discord Emoji
        name = re.sub(
            r"<a?:\w+:\d+>",
            "",
            name
        )

        # Unicode Emoji
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

        # Dekorasi / separator
        name = re.sub(
            r"[╭╮╰╯┇┆┊┋│┃"
            r"━─═╍╾╼"
            r"➜➤➢➣➥➦➧➨"
            r"・﹕:|/\\]+",
            " ",
            name
        )

        name = name.replace("`", "")

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
    # CHECK CHANNEL VISIBILITY
    # =========================================================

    def can_murid_view_channel(
        self,
        guild: discord.Guild,
        channel
    ) -> bool:

        murid_role = guild.get_role(
            self.MURID_ROLE_ID
        )

        calon_murid_role = guild.get_role(
            self.CALON_MURID_ROLE_ID
        )

        if not murid_role and not calon_murid_role:
            return False

        # Murid
        if murid_role:

            permissions = channel.permissions_for(
                murid_role
            )

            if permissions.view_channel:
                return True

        # Calon Murid
        if calon_murid_role:

            permissions = channel.permissions_for(
                calon_murid_role
            )

            if permissions.view_channel:
                return True

        return False

    # =========================================================
    # GET DESCRIPTION
    # =========================================================

    def get_channel_description(
        self,
        channel_name: str
    ) -> str:

        normalized = self.normalize_name(
            channel_name
        )

        if normalized in self.CHANNEL_DESCRIPTIONS:
            return self.CHANNEL_DESCRIPTIONS[
                normalized
            ]

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

        arrow = (
            str(blue_arrow)
            if blue_arrow
            else "🔵"
        )

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
    # GET CHANNELS IN DISCORD ORDER
    # =========================================================

    def get_category_channels_in_discord_order(
        self,
        guild: discord.Guild,
        category
    ):

        """
        Mengikuti urutan asli channel di Discord.

        Text, Voice, dan Stage diperlakukan sama.
        Tidak ada channel yang diprioritaskan.
        """

        return [
            channel
            for channel in guild.channels
            if channel.category_id == category.id
            and self.can_murid_view_channel(
                guild,
                channel
            )
        ]

    # =========================================================
    # SORT CATEGORIES
    # =========================================================

    @staticmethod
    def sort_categories_discord_order(
        categories
    ):

        return sorted(
            categories,
            key=lambda category: (
                category.position,
                category.id
            )
        )

    # =========================================================
    # SEND CATEGORY
    # =========================================================

    async def send_category(
        self,
        ctx,
        category,
        visible_channels,
        blue_arrow
    ):

        embed = discord.Embed(
            color=discord.Color.blurple()
        )

        embed.description = (
            f"**{category.name}**"
        )

        for channel in visible_channels:

            channel_text = (
                self.build_channel_line(
                    channel,
                    blue_arrow
                )
            )

            new_description = (
                embed.description
                + "\n"
                + channel_text
            )

            # Masih dalam batas Embed
            if len(new_description) <= self.MAX_DESCRIPTION_LENGTH:

                embed.description = (
                    new_description
                )

            # Embed sudah penuh
            else:

                await ctx.send(
                    embed=embed
                )

                await asyncio.sleep(
                    self.SEND_DELAY
                )

                embed = discord.Embed(
                    color=discord.Color.blurple()
                )

                embed.description = (
                    f"**{category.name}**\n"
                    f"{channel_text}"
                )

        if embed.description:

            await ctx.send(
                embed=embed
            )

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
        ctx
    ):

        if not isinstance(
            ctx.author,
            discord.Member
        ):
            return

        # -----------------------------------------------------
        # Hanya Murid / Calon Murid
        # -----------------------------------------------------

        if not self.has_member_role(
            ctx.author
        ):

            await ctx.send(
                "Kamu tidak memiliki akses "
                "untuk melihat Channel Guide nanZ."
            )

            return

        guild = ctx.guild

        # -----------------------------------------------------
        # Custom Emoji
        # -----------------------------------------------------

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

        header_arrow = (
            str(purple_arrow)
            if purple_arrow
            else "🟣"
        )

        # -----------------------------------------------------
        # Header
        # -----------------------------------------------------

        header_embed = discord.Embed(
            description=(
                f"{header_arrow} "
                f"**NANZ CHANNEL GUIDE**"
            ),
            color=discord.Color.blurple()
        )

        try:

            await ctx.send(
                embed=header_embed
            )

            await asyncio.sleep(
                self.SEND_DELAY
            )

            # -------------------------------------------------
            # Semua kategori kecuali excluded
            # -------------------------------------------------

            categories = [
                category
                for category in guild.categories
                if category.id not in self.EXCLUDED_CATEGORY_IDS
            ]

            # -------------------------------------------------
            # Urutan kategori mengikuti Discord
            # -------------------------------------------------

            categories = (
                self.sort_categories_discord_order(
                    categories
                )
            )

            # -------------------------------------------------
            # Process kategori
            # -------------------------------------------------

            for category in categories:

                # Ambil channel berdasarkan urutan Discord
                visible_channels = (
                    self.get_category_channels_in_discord_order(
                        guild,
                        category
                    )
                )

                if not visible_channels:
                    continue

                await self.send_category(
                    ctx,
                    category,
                    visible_channels,
                    blue_arrow
                )

                await asyncio.sleep(
                    self.SEND_DELAY
                )

        except discord.HTTPException as e:

            print(
                f"[ChannelGuide] HTTP Error: {e}"
            )

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
        ctx,
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