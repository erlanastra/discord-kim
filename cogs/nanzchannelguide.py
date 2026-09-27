import discord
from discord.ext import commands
import json
import os
import asyncio


# =========================================================
# NANZ CHANNEL GUIDE
# =========================================================
#
# Fitur:
# - Auto detect category & channel public
# - Patokan public = @everyone bisa View Channel
# - Private channel/category otomatis di-skip
# - Deskripsi channel manual
# - Deskripsi category manual
# - Custom animated emoji nanZ
# - Data deskripsi tersimpan berdasarkan ID
#
# Command:
#
# !channelguide
# !channelinfo #channel | Deskripsi channel
# !channelinfo #channel
# !clearchannelinfo #channel
#
# !categoryinfo Nama Category | Deskripsi category
# !categoryinfo Nama Category
# !clearcategoryinfo Nama Category
#
# !channelsettings
#
# =========================================================


class NanzChannelGuide(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # =================================================
        # CONFIG
        # =================================================

        self.DATA_FILE = "nanz_channel_guide.json"

        # =================================================
        # EMOJI NANZ
        # =================================================

        self.PURPLE_ARROW_ID = 1512787191234035803
        self.BLUE_ARROW_ID = 1512787254312042496
        self.GEAR_ID = 1553688352564183051

        # =================================================
        # CACHE
        # =================================================

        self.data = self.load_data()

        # Mencegah refresh bersamaan
        self.refresh_lock = asyncio.Lock()

    # =====================================================
    # EMOJI
    # =====================================================

    def get_emoji(self, guild, emoji_id, fallback):

        emoji = guild.get_emoji(emoji_id)

        if emoji:
            return str(emoji)

        return fallback

    # =====================================================
    # LOAD DATA
    # =====================================================

    def load_data(self):

        if not os.path.exists(self.DATA_FILE):
            return {
                "guilds": {}
            }

        try:

            with open(
                self.DATA_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

                if not isinstance(data, dict):
                    return {
                        "guilds": {}
                    }

                data.setdefault(
                    "guilds",
                    {}
                )

                return data

        except Exception as e:

            print(
                "[NANZ CHANNEL GUIDE] "
                f"Gagal membaca database: {e}"
            )

            return {
                "guilds": {}
            }

    # =====================================================
    # SAVE DATA
    # =====================================================

    def save_data(self):

        try:

            temp_file = self.DATA_FILE + ".tmp"

            with open(
                temp_file,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    self.data,
                    f,
                    indent=4,
                    ensure_ascii=False
                )

            os.replace(
                temp_file,
                self.DATA_FILE
            )

        except Exception as e:

            print(
                "[NANZ CHANNEL GUIDE] "
                f"Gagal menyimpan database: {e}"
            )

    # =====================================================
    # GET GUILD DATA
    # =====================================================

    def get_guild_data(self, guild_id):

        guild_id = str(guild_id)

        if guild_id not in self.data["guilds"]:

            self.data["guilds"][guild_id] = {
                "categories": {},
                "channels": {}
            }

        guild_data = self.data["guilds"][guild_id]

        guild_data.setdefault(
            "categories",
            {}
        )

        guild_data.setdefault(
            "channels",
            {}
        )

        return guild_data

    # =====================================================
    # PUBLIC CHECK
    # =====================================================

    def is_public_for_everyone(self, channel):

        """
        Menentukan apakah channel bisa dilihat oleh
        @everyone.

        PATOKAN UTAMA:
        @everyone -> View Channel
        """

        try:

            everyone = channel.guild.default_role

            permissions = channel.permissions_for(
                everyone
            )

            return permissions.view_channel

        except Exception as e:

            print(
                "[NANZ CHANNEL GUIDE] "
                f"Gagal mengecek permission {channel}: {e}"
            )

            return False

    # =====================================================
    # CATEGORY PUBLIC CHECK
    # =====================================================

    def is_category_public(self, category):

        """
        Category dianggap public apabila
        @everyone dapat melihat category tersebut.
        """

        if not category:
            return True

        return self.is_public_for_everyone(
            category
        )

    # =====================================================
    # CHANNEL PUBLIC CHECK
    # =====================================================

    def is_channel_public(self, channel):

        """
        Channel public apabila:
        1. Category-nya public
        2. Channel tersebut sendiri public
        """

        # -----------------------------------------------
        # CATEGORY PRIVATE
        # -----------------------------------------------

        if channel.category:

            if not self.is_category_public(
                channel.category
            ):
                return False

        # -----------------------------------------------
        # CHANNEL PRIVATE
        # -----------------------------------------------

        if not self.is_public_for_everyone(
            channel
        ):
            return False

        return True

    # =====================================================
    # GET CHANNEL DESCRIPTION
    # =====================================================

    def get_channel_description(
        self,
        guild,
        channel_id
    ):

        guild_data = self.get_guild_data(
            guild.id
        )

        return guild_data["channels"].get(
            str(channel_id),
            ""
        )

    # =====================================================
    # GET CATEGORY DESCRIPTION
    # =====================================================

    def get_category_description(
        self,
        guild,
        category_id
    ):

        guild_data = self.get_guild_data(
            guild.id
        )

        return guild_data["categories"].get(
            str(category_id),
            ""
        )

    # =====================================================
    # SET CHANNEL DESCRIPTION
    # =====================================================

    def set_channel_description(
        self,
        guild,
        channel_id,
        description
    ):

        guild_data = self.get_guild_data(
            guild.id
        )

        guild_data["channels"][
            str(channel_id)
        ] = description

        self.save_data()

    # =====================================================
    # SET CATEGORY DESCRIPTION
    # =====================================================

    def set_category_description(
        self,
        guild,
        category_id,
        description
    ):

        guild_data = self.get_guild_data(
            guild.id
        )

        guild_data["categories"][
            str(category_id)
        ] = description

        self.save_data()

    # =====================================================
    # REMOVE CHANNEL DESCRIPTION
    # =====================================================

    def remove_channel_description(
        self,
        guild,
        channel_id
    ):

        guild_data = self.get_guild_data(
            guild.id
        )

        guild_data["channels"].pop(
            str(channel_id),
            None
        )

        self.save_data()

    # =====================================================
    # REMOVE CATEGORY DESCRIPTION
    # =====================================================

    def remove_category_description(
        self,
        guild,
        category_id
    ):

        guild_data = self.get_guild_data(
            guild.id
        )

        guild_data["categories"].pop(
            str(category_id),
            None
        )

        self.save_data()

    # =====================================================
    # GET PUBLIC CATEGORIES
    # =====================================================

    def get_public_categories(self, guild):

        categories = []

        for category in guild.categories:

            if not self.is_category_public(
                category
            ):
                continue

            categories.append(
                category
            )

        return categories

    # =====================================================
    # GET PUBLIC CHANNELS
    # =====================================================

    def get_public_channels(
        self,
        category
    ):

        channels = []

        for channel in category.channels:

            # -----------------------------------------
            # TEXT
            # VOICE
            # FORUM
            # STAGE
            # ETC.
            # -----------------------------------------

            if not self.is_channel_public(
                channel
            ):
                continue

            channels.append(
                channel
            )

        return channels

    # =====================================================
    # CHANNEL ICON
    # =====================================================

    def get_channel_icon(
        self,
        channel
    ):

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
    # GENERATE GUIDE EMBED
    # =====================================================

    async def generate_guide_embed(
        self,
        guild
    ):

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

        gear = self.get_emoji(
            guild,
            self.GEAR_ID,
            "⚙️"
        )

        embed = discord.Embed(
            title=f"{purple_arrow} NANZ CHANNEL GUIDE",
            description=(
                "Temukan berbagai ruang yang tersedia "
                "di **nanZ Server**.\n\n"
                f"{gear} *Channel private tidak ditampilkan "
                "dalam daftar ini.*"
            ),
            color=discord.Color.from_rgb(
                100,
                70,
                180
            )
        )

        # =================================================
        # CATEGORY
        # =================================================

        public_categories = (
            self.get_public_categories(
                guild
            )
        )

        if not public_categories:

            embed.description += (
                "\n\nTidak ada category public "
                "yang dapat ditampilkan."
            )

            return embed

        total_channels = 0

        for category in public_categories:

            channels = (
                self.get_public_channels(
                    category
                )
            )

            # ---------------------------------------------
            # CATEGORY TANPA CHANNEL PUBLIC
            # ---------------------------------------------

            if not channels:
                continue

            total_channels += len(
                channels
            )

            category_description = (
                self.get_category_description(
                    guild,
                    category.id
                )
            )

            # ---------------------------------------------
            # CATEGORY HEADER
            # ---------------------------------------------

            category_text = (
                f"{purple_arrow} "
                f"**{category.name}**"
            )

            if category_description:

                category_text += (
                    f"\n"
                    f"　{category_description}"
                )

            # ---------------------------------------------
            # CHANNEL LIST
            # ---------------------------------------------

            channel_lines = []

            for index, channel in enumerate(
                channels
            ):

                icon = self.get_channel_icon(
                    channel
                )

                description = (
                    self.get_channel_description(
                        guild,
                        channel.id
                    )
                )

                line = (
                    f"{blue_arrow} "
                    f"{icon} {channel.mention}"
                )

                if description:

                    line += (
                        f"\n"
                        f"　└ {description}"
                    )

                channel_lines.append(
                    line
                )

            category_text += (
                "\n" +
                "\n".join(
                    channel_lines
                )
            )

            # ---------------------------------------------
            # ADD FIELD
            # ---------------------------------------------

            # Discord embed field max 1024 chars.
            if len(category_text) > 1024:

                category_text = (
                    category_text[:1000]
                    + "..."
                )

            embed.add_field(
                name="\u200b",
                value=category_text,
                inline=False
            )

        # =================================================
        # FOOTER
        # =================================================

        embed.set_footer(
            text=(
                f"nanZ Server • "
                f"{len(public_categories)} Category • "
                f"{total_channels} Channel"
            )
        )

        if guild.icon:

            embed.set_thumbnail(
                url=guild.icon.url
            )

        return embed

    # =====================================================
    # CHANNEL GUIDE COMMAND
    # =====================================================

    @commands.command(
        name="channelguide",
        aliases=[
            "guidechannel",
            "channel-guide",
            "guide"
        ]
    )
    async def channel_guide(
        self,
        ctx
    ):

        async with self.refresh_lock:

            embed = (
                await self.generate_guide_embed(
                    ctx.guild
                )
            )

            await ctx.send(
                embed=embed
            )

    # =====================================================
    # CHANNEL INFO
    # =====================================================

    @commands.command(
        name="channelinfo"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def channel_info(
        self,
        ctx,
        channel: discord.abc.GuildChannel = None,
        *,
        description: str = None
    ):

        # =================================================
        # VALIDASI CHANNEL
        # =================================================

        if channel is None:

            await ctx.send(
                "❌ Gunakan format:\n"
                "`!channelinfo #channel | deskripsi`"
            )

            return

        # =================================================
        # PARSE DESCRIPTION
        # =================================================

        if description is None:

            await ctx.send(
                "❌ Masukkan deskripsi channel.\n\n"
                "Contoh:\n"
                "`!channelinfo #peraturan | "
                "Tempat membaca seluruh peraturan nanZ.`"
            )

            return

        description = description.strip()

        if description.startswith("|"):

            description = (
                description[1:]
                .strip()
            )

        # =================================================
        # CHECK PUBLIC
        # =================================================

        if not self.is_channel_public(
            channel
        ):

            await ctx.send(
                "🔒 Channel tersebut private "
                "dan tidak dapat dimasukkan "
                "ke Channel Guide.",
                delete_after=5
            )

            return

        # =================================================
        # SAVE
        # =================================================

        self.set_channel_description(
            ctx.guild,
            channel.id,
            description
        )

        # =================================================
        # SUCCESS
        # =================================================

        blue_arrow = self.get_emoji(
            ctx.guild,
            self.BLUE_ARROW_ID,
            "└"
        )

        embed = discord.Embed(
            title="Channel Guide",
            description=(
                f"{blue_arrow} "
                f"{channel.mention}\n\n"
                f"**Deskripsi:**\n"
                f"{description}"
            ),
            color=discord.Color.blue()
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # CLEAR CHANNEL INFO
    # =====================================================

    @commands.command(
        name="clearchannelinfo"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def clear_channel_info(
        self,
        ctx,
        channel: discord.abc.GuildChannel = None
    ):

        if channel is None:

            await ctx.send(
                "❌ Gunakan:\n"
                "`!clearchannelinfo #channel`"
            )

            return

        self.remove_channel_description(
            ctx.guild,
            channel.id
        )

        await ctx.send(
            f"✅ Deskripsi {channel.mention} "
            "berhasil dihapus.",
            delete_after=5
        )

    # =====================================================
    # CATEGORY INFO
    # =====================================================

    @commands.command(
        name="categoryinfo"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def category_info(
        self,
        ctx,
        *,
        content: str = None
    ):

        if not content:

            await ctx.send(
                "❌ Gunakan format:\n"
                "`!categoryinfo Nama Category | Deskripsi`"
            )

            return

        # =================================================
        # SPLIT
        # =================================================

        if "|" not in content:

            await ctx.send(
                "❌ Pisahkan nama category dan "
                "deskripsi menggunakan `|`.\n\n"
                "Contoh:\n"
                "`!categoryinfo SOCIAL SPACE | "
                "Tempat member berinteraksi.`"
            )

            return

        category_name, description = (
            content.split(
                "|",
                1
            )
        )

        category_name = (
            category_name.strip()
        )

        description = (
            description.strip()
        )

        # =================================================
        # FIND CATEGORY
        # =================================================

        category = discord.utils.find(
            lambda c:
                isinstance(
                    c,
                    discord.CategoryChannel
                )
                and
                c.name.lower()
                == category_name.lower(),
            ctx.guild.categories
        )

        if category is None:

            await ctx.send(
                "❌ Category tidak ditemukan."
            )

            return

        # =================================================
        # CHECK PUBLIC
        # =================================================

        if not self.is_category_public(
            category
        ):

            await ctx.send(
                "🔒 Category tersebut private "
                "dan tidak dapat dimasukkan "
                "ke Channel Guide.",
                delete_after=5
            )

            return

        # =================================================
        # SAVE
        # =================================================

        self.set_category_description(
            ctx.guild,
            category.id,
            description
        )

        # =================================================
        # SUCCESS
        # =================================================

        purple_arrow = self.get_emoji(
            ctx.guild,
            self.PURPLE_ARROW_ID,
            "↳"
        )

        embed = discord.Embed(
            title="Category Guide",
            description=(
                f"{purple_arrow} "
                f"**{category.name}**\n\n"
                f"**Deskripsi:**\n"
                f"{description}"
            ),
            color=discord.Color.purple()
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # CLEAR CATEGORY INFO
    # =====================================================

    @commands.command(
        name="clearcategoryinfo"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def clear_category_info(
        self,
        ctx,
        *,
        category_name: str = None
    ):

        if not category_name:

            await ctx.send(
                "❌ Gunakan:\n"
                "`!clearcategoryinfo Nama Category`"
            )

            return

        category_name = (
            category_name.strip()
        )

        category = discord.utils.find(
            lambda c:
                isinstance(
                    c,
                    discord.CategoryChannel
                )
                and
                c.name.lower()
                == category_name.lower(),
            ctx.guild.categories
        )

        if category is None:

            await ctx.send(
                "❌ Category tidak ditemukan."
            )

            return

        self.remove_category_description(
            ctx.guild,
            category.id
        )

        await ctx.send(
            f"✅ Deskripsi category "
            f"**{category.name}** berhasil dihapus.",
            delete_after=5
        )

    # =====================================================
    # SETTINGS
    # =====================================================

    @commands.command(
        name="channelsettings"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def channel_settings(
        self,
        ctx
    ):

        guild_data = self.get_guild_data(
            ctx.guild.id
        )

        public_categories = (
            self.get_public_categories(
                ctx.guild
            )
        )

        total_channels = 0

        for category in public_categories:

            total_channels += len(
                self.get_public_channels(
                    category
                )
            )

        gear = self.get_emoji(
            ctx.guild,
            self.GEAR_ID,
            "⚙️"
        )

        purple_arrow = self.get_emoji(
            ctx.guild,
            self.PURPLE_ARROW_ID,
            "↳"
        )

        blue_arrow = self.get_emoji(
            ctx.guild,
            self.BLUE_ARROW_ID,
            "└"
        )

        embed = discord.Embed(
            title=(
                f"{gear} NANZ CHANNEL GUIDE "
                f"SETTINGS"
            ),
            color=discord.Color.from_rgb(
                100,
                70,
                180
            )
        )

        embed.add_field(
            name=(
                f"{purple_arrow} "
                "Auto Detection"
            ),
            value=(
                f"{blue_arrow} "
                f"Public Category: "
                f"**{len(public_categories)}**\n"
                f"{blue_arrow} "
                f"Public Channel: "
                f"**{total_channels}**\n"
                f"{blue_arrow} "
                f"Channel Description: "
                f"**{len(guild_data['channels'])}**\n"
                f"{blue_arrow} "
                f"Category Description: "
                f"**{len(guild_data['categories'])}**"
            ),
            inline=False
        )

        embed.add_field(
            name=(
                f"{purple_arrow} "
                "Commands"
            ),
            value=(
                "`!channelguide`\n"
                "Menampilkan Channel Guide.\n\n"

                "`!channelinfo #channel | deskripsi`\n"
                "Mengatur deskripsi channel.\n\n"

                "`!clearchannelinfo #channel`\n"
                "Menghapus deskripsi channel.\n\n"

                "`!categoryinfo Nama | deskripsi`\n"
                "Mengatur deskripsi category.\n\n"

                "`!clearcategoryinfo Nama`\n"
                "Menghapus deskripsi category."
            ),
            inline=False
        )

        embed.add_field(
            name=(
                f"{purple_arrow} "
                "Visibility Rule"
            ),
            value=(
                f"{blue_arrow} "
                "Patokan utama adalah permission "
                "`@everyone`.\n"
                f"{blue_arrow} "
                "`View Channel ✅` → terdeteksi.\n"
                f"{blue_arrow} "
                "`View Channel ❌` → diabaikan.\n"
                f"{blue_arrow} "
                "Category private → seluruh channel "
                "di dalamnya diabaikan."
            ),
            inline=False
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # ERROR HANDLER
    # =====================================================

    @channel_info.error
    async def channel_info_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ Command ini hanya dapat digunakan "
                "oleh Administrator.",
                delete_after=5
            )

            return

        if isinstance(
            error,
            commands.BadArgument
        ):

            await ctx.send(
                "❌ Channel tidak valid.\n"
                "Gunakan mention channel, contoh:\n"
                "`!channelinfo #peraturan | Deskripsi`",
                delete_after=6
            )

            return

        raise error

    # =====================================================
    # CATEGORY ERROR
    # =====================================================

    @category_info.error
    async def category_info_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ Command ini hanya dapat digunakan "
                "oleh Administrator.",
                delete_after=5
            )

            return

        raise error

    # =====================================================
    # CLEAR CHANNEL ERROR
    # =====================================================

    @clear_channel_info.error
    async def clear_channel_info_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ Command ini hanya dapat digunakan "
                "oleh Administrator.",
                delete_after=5
            )

            return

        if isinstance(
            error,
            commands.BadArgument
        ):

            await ctx.send(
                "❌ Channel tidak valid.",
                delete_after=5
            )

            return

        raise error

    # =====================================================
    # CLEAR CATEGORY ERROR
    # =====================================================

    @clear_category_info.error
    async def clear_category_info_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ Command ini hanya dapat digunakan "
                "oleh Administrator.",
                delete_after=5
            )

            return

        raise error

    # =====================================================
    # SETTINGS ERROR
    # =====================================================

    @channel_settings.error
    async def channel_settings_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ Command ini hanya dapat digunakan "
                "oleh Administrator.",
                delete_after=5
            )

            return

        raise error


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        NanzChannelGuide(bot)
    )