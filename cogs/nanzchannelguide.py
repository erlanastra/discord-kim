import discord
from discord.ext import commands
import json
import os
import asyncio


# =========================================================
# NANZ CHANNEL GUIDE
# =========================================================
#
# Konsep:
# - Channel ditampilkan jika role MURID atau CALON MURID
#   memiliki permission View Channel.
# - Tidak menggunakan @everyone sebagai patokan.
# - Satu command untuk membuka panel pengaturan.
# - Panel dapat mencari channel/category.
# - Setelah memilih channel/category, muncul modal
#   untuk mengisi deskripsi.
# - Guide yang dihasilkan hanya berisi informasi yang
#   memang ditujukan untuk dilihat member.
# - Tidak ada penjelasan "private tidak ditampilkan",
#   permission, atau aturan internal pada guide member.
#
# Command:
# !channelguide
#
# =========================================================


class NanzChannelGuide(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # =================================================
        # CONFIG
        # =================================================

        self.DATA_FILE = "nanz_channel_guide.json"

        # Role yang menjadi patokan akses guide
        self.MURID_ROLE_ID = 1453095603008442510
        self.CALON_MURID_ROLE_ID = 1504467138440597604

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

            data.setdefault("guilds", {})

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

        guild_data.setdefault("categories", {})
        guild_data.setdefault("channels", {})

        return guild_data

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

    def is_visible_for_members(self, channel):

        """
        Channel dianggap tersedia untuk Channel Guide apabila
        salah satu dari dua role berikut memiliki View Channel:

        - Murid
        - Calon Murid

        Untuk channel yang berada di dalam category, permission
        category juga diperhitungkan oleh Discord melalui
        permissions_for().
        """

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
    # CATEGORY ACCESS CHECK
    # =====================================================

    def is_category_visible_for_members(self, category):

        if category is None:
            return False

        return (
            self.role_can_view(
                category,
                self.MURID_ROLE_ID
            )
            or
            self.role_can_view(
                category,
                self.CALON_MURID_ROLE_ID
            )
        )

    # =====================================================
    # GET CHANNEL DESCRIPTION
    # =====================================================

    def get_channel_description(
        self,
        guild,
        channel_id
    ):

        guild_data = self.get_guild_data(guild.id)

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

        guild_data = self.get_guild_data(guild.id)

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

        guild_data = self.get_guild_data(guild.id)

        guild_data["channels"][str(channel_id)] = description

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

        guild_data = self.get_guild_data(guild.id)

        guild_data["categories"][str(category_id)] = description

        self.save_data()

    # =====================================================
    # REMOVE CHANNEL DESCRIPTION
    # =====================================================

    def remove_channel_description(
        self,
        guild,
        channel_id
    ):

        guild_data = self.get_guild_data(guild.id)

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

        guild_data = self.get_guild_data(guild.id)

        guild_data["categories"].pop(
            str(category_id),
            None
        )

        self.save_data()

    # =====================================================
    # GET VISIBLE CATEGORIES
    # =====================================================

    def get_visible_categories(self, guild):

        categories = []

        for category in guild.categories:

            # Category ditampilkan apabila minimal satu channel
            # di dalamnya dapat dilihat oleh Murid/Calon Murid.
            channels = self.get_visible_channels(category)

            if channels:
                categories.append(category)

        return categories

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
    # GET ALL SELECTABLE ITEMS FOR ADMIN CONFIG
    # =====================================================

    def get_selectable_items(self, guild):

        items = []

        # Admin dapat mencari SEMUA category/channel.
        # Filter role hanya dipakai saat menampilkan guide ke member.
        for category in guild.categories:

            items.append({
                "type": "category",
                "id": category.id,
                "name": category.name,
                "channel": None
            })

            for channel in category.channels:

                if isinstance(
                    channel,
                    (
                        discord.TextChannel,
                        discord.VoiceChannel,
                        discord.ForumChannel,
                        discord.StageChannel,
                    )
                ):
                    items.append({
                        "type": "channel",
                        "id": channel.id,
                        "name": channel.name,
                        "channel": channel
                    })

        # Channel tanpa category juga ikut bisa dicari.
        for channel in guild.channels:

            if channel.category is not None:
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
                items.append({
                    "type": "channel",
                    "id": channel.id,
                    "name": channel.name,
                    "channel": channel
                })

        return items

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
    # GENERATE GUIDE EMBED
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

        if not visible_categories:
            embed = discord.Embed(
                title=f"{purple_arrow} NANZ CHANNEL GUIDE",
                description="Belum ada ruang yang tersedia.",
                color=discord.Color.from_rgb(100, 70, 180)
            )
            return [embed]

        embeds = []
        current = discord.Embed(
            title=f"{purple_arrow} NANZ CHANNEL GUIDE",
            description=(
                "Temukan ruang yang tersedia untuk "
                "member di **nanZ Server**."
            ),
            color=discord.Color.from_rgb(100, 70, 180)
        )

        total_channels = 0
        total_categories = len(visible_categories)

        for category in visible_categories:

            channels = self.get_visible_channels(category)
            if not channels:
                continue

            total_channels += len(channels)

            category_description = self.get_category_description(
                guild, category.id
            )

            category_text = f"{purple_arrow} **{category.name}**"

            if category_description:
                category_text += f"\n　{category_description}"

            channel_lines = []

            for channel in channels:
                icon = self.get_channel_icon(channel)
                description = self.get_channel_description(
                    guild, channel.id
                )

                line = f"{blue_arrow} {icon} {channel.mention}"

                if description:
                    line += f"\n　└ {description}"

                channel_lines.append(line)

            category_text += "\n" + "\n".join(channel_lines)

            # Satu field maksimal 1024 karakter.
            if len(category_text) > 1024:
                category_text = category_text[:1000] + "..."

            # Jaga total ukuran embed tetap aman.
            current_size = sum(
                len(field.name) + len(field.value)
                for field in current.fields
            ) + len(current.description or "")

            if current.fields and (
                current_size + len(category_text) > 5000
                or len(current.fields) >= 24
            ):
                embeds.append(current)
                current = discord.Embed(
                    title=f"{purple_arrow} NANZ CHANNEL GUIDE",
                    color=discord.Color.from_rgb(100, 70, 180)
                )

            current.add_field(
                name="\u200b",
                value=category_text,
                inline=False
            )

        current.set_footer(
            text=(
                f"nanZ Server • {total_categories} Category • "
                f"{total_channels} Channel"
            )
        )

        if guild.icon:
            current.set_thumbnail(url=guild.icon.url)

        embeds.append(current)
        return embeds

    async def generate_guide_embed(self, guild):
        # Kompatibilitas untuk pemanggilan lama.
        embeds = await self.generate_guide_embeds(guild)
        return embeds[0]

    # =====================================================
    # DESCRIPTION MODAL
    # =====================================================

    class DescriptionModal(discord.ui.Modal):

        def __init__(
            self,
            cog,
            guild_id,
            item_type,
            item_id,
            item_name,
            existing_description=""
        ):
            super().__init__(
                title=f"Deskripsi {item_type}"
            )

            self.cog = cog
            self.guild_id = guild_id
            self.item_type = item_type
            self.item_id = item_id
            self.item_name = item_name

            self.description_input = discord.ui.TextInput(
                label=f"Deskripsi {item_name}",
                placeholder="Tulis deskripsi yang ingin ditampilkan...",
                default=existing_description[:1000],
                style=discord.TextStyle.paragraph,
                max_length=1000,
                required=False
            )

            self.add_item(
                self.description_input
            )

        async def on_submit(self, interaction):

            guild = interaction.guild

            if guild is None:
                await interaction.response.send_message(
                    "❌ Guild tidak ditemukan.",
                    ephemeral=True
                )
                return

            description = (
                self.description_input.value or ""
            ).strip()

            if self.item_type == "Channel":

                if description:
                    self.cog.set_channel_description(
                        guild,
                        self.item_id,
                        description
                    )
                else:
                    self.cog.remove_channel_description(
                        guild,
                        self.item_id
                    )

            else:

                if description:
                    self.cog.set_category_description(
                        guild,
                        self.item_id,
                        description
                    )
                else:
                    self.cog.remove_category_description(
                        guild,
                        self.item_id
                    )

            await interaction.response.send_message(
                f"✅ Deskripsi **{self.item_name}** berhasil diperbarui.",
                ephemeral=True
            )

    # =====================================================
    # SEARCH MODAL
    # =====================================================

    class SearchModal(discord.ui.Modal):

        def __init__(self, cog):
            super().__init__(
                title="Cari Channel / Kategori"
            )

            self.cog = cog

            self.search_input = discord.ui.TextInput(
                label="Kata pencarian",
                placeholder="Contoh: peraturan, kelas, informasi...",
                max_length=100,
                required=True
            )

            self.add_item(
                self.search_input
            )

        async def on_submit(self, interaction):

            guild = interaction.guild

            if guild is None:
                await interaction.response.send_message(
                    "❌ Guild tidak ditemukan.",
                    ephemeral=True
                )
                return

            query = (
                self.search_input.value or ""
            ).strip().lower()

            if not query:
                await interaction.response.send_message(
                    "❌ Masukkan kata pencarian.",
                    ephemeral=True
                )
                return

            results = []

            for item in self.cog.get_selectable_items(guild):

                if query in item["name"].lower():
                    results.append(item)

            if not results:
                await interaction.response.send_message(
                    f"❌ Tidak menemukan hasil untuk **{query}**.",
                    ephemeral=True
                )
                return

            view = self.cog.SearchResultView(
                self.cog,
                guild,
                results
            )

            await interaction.response.send_message(
                "🔎 **Hasil pencarian**\n"
                "Pilih channel atau kategori yang ingin diberi deskripsi.",
                view=view,
                ephemeral=True
            )

    # =====================================================
    # RESULT SELECT MENU
    # =====================================================

    class SearchResultSelect(discord.ui.Select):

        def __init__(self, cog, guild, results):

            self.cog = cog
            self.guild_id = guild.id

            options = []

            for item in results[:25]:

                if item["type"] == "category":
                    emoji = "📂"
                    label = f"Kategori • {item['name']}"[:100]
                    description = "Atur deskripsi kategori"
                    value = f"category:{item['id']}"

                else:
                    emoji = cog.get_channel_icon(
                        item["channel"]
                    )
                    label = item["name"][:100]
                    description = "Atur deskripsi channel"
                    value = f"channel:{item['id']}"

                options.append(
                    discord.SelectOption(
                        label=label,
                        description=description[:100],
                        emoji=emoji,
                        value=value
                    )
                )

            super().__init__(
                placeholder="Pilih hasil pencarian...",
                min_values=1,
                max_values=1,
                options=options
            )

        async def callback(self, interaction):

            value = self.values[0]

            item_type, item_id = value.split(":", 1)
            item_id = int(item_id)

            guild = interaction.guild

            if guild is None:
                await interaction.response.send_message(
                    "❌ Guild tidak ditemukan.",
                    ephemeral=True
                )
                return

            if item_type == "category":

                category = guild.get_channel(item_id)

                if category is None:
                    await interaction.response.send_message(
                        "❌ Kategori tidak ditemukan.",
                        ephemeral=True
                    )
                    return

                existing = self.cog.get_category_description(
                    guild,
                    category.id
                )

                modal = self.cog.DescriptionModal(
                    self.cog,
                    guild.id,
                    "Kategori",
                    category.id,
                    category.name,
                    existing
                )

            else:

                channel = guild.get_channel(item_id)

                if channel is None:
                    await interaction.response.send_message(
                        "❌ Channel tidak ditemukan.",
                        ephemeral=True
                    )
                    return

                existing = self.cog.get_channel_description(
                    guild,
                    channel.id
                )

                modal = self.cog.DescriptionModal(
                    self.cog,
                    guild.id,
                    "Channel",
                    channel.id,
                    channel.name,
                    existing
                )

            try:
                await interaction.response.send_modal(modal)
            except Exception as e:
                print(f"[NANZ CHANNEL GUIDE] Open description modal error: {e}")
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Gagal membuka form deskripsi.",
                        ephemeral=True
                    )

    # =====================================================
    # SEARCH RESULT VIEW
    # =====================================================

    class SearchResultView(discord.ui.View):

        def __init__(self, cog, guild, results):
            super().__init__(timeout=300)

            self.cog = cog
            self.guild_id = guild.id
            self.results = results

            self.add_item(
                cog.SearchResultSelect(
                    cog,
                    guild,
                    results
                )
            )

    # =====================================================
    # PANEL VIEW
    # =====================================================

    class GuidePanel(discord.ui.View):

        def __init__(self, cog, guild):
            super().__init__(timeout=600)

            self.cog = cog
            self.guild_id = guild.id

        @discord.ui.button(
            label="Cari Channel / Kategori",
            emoji="🔎",
            style=discord.ButtonStyle.primary,
            row=0
        )
        async def search_item(
            self,
            interaction,
            button
        ):

            try:
                await interaction.response.send_modal(
                    self.cog.SearchModal(self.cog)
                )
            except Exception as e:
                print(f"[NANZ CHANNEL GUIDE] Search button error: {e}")
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Gagal membuka pencarian. Cek console bot untuk detail error.",
                        ephemeral=True
                    )

        @discord.ui.button(
            label="Refresh",
            emoji="🔄",
            style=discord.ButtonStyle.secondary,
            row=0
        )
        async def refresh_panel(
            self,
            interaction,
            button
        ):

            try:
                guild = interaction.guild

                if guild is None:
                    await interaction.response.send_message(
                        "❌ Guild tidak ditemukan.",
                        ephemeral=True
                    )
                    return

                visible_categories = self.cog.get_visible_categories(guild)
                total_channels = sum(
                    len(self.cog.get_visible_channels(category))
                    for category in visible_categories
                )

                embed = discord.Embed(
                    title="⚙️ Channel Guide Settings",
                    description=(
                        "Gunakan panel ini untuk mengatur deskripsi "
                        "channel dan kategori.\n\n"
                        "Tekan **Cari Channel / Kategori**, cari nama "
                        "yang diinginkan, lalu pilih hasilnya untuk "
                        "mengisi deskripsi."
                    ),
                    color=discord.Color.from_rgb(100, 70, 180)
                )

                embed.add_field(
                    name="📚 Channel Guide",
                    value=(
                        f"**{len(visible_categories)}** kategori\n"
                        f"**{total_channels}** channel"
                    ),
                    inline=False
                )

                embed.set_footer(
                    text="Panel konfigurasi hanya untuk administrator."
                )

                await interaction.response.edit_message(
                    embed=embed,
                    view=self.cog.GuidePanel(self.cog, guild)
                )

            except Exception as e:
                print(f"[NANZ CHANNEL GUIDE] Refresh error: {e}")
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Gagal me-refresh panel.",
                        ephemeral=True
                    )

    # =====================================================
    # SHOW CHANNEL GUIDE
    # =====================================================

    @commands.command(
        name="channelguide"
    )
    async def channel_guide(
        self,
        ctx
    ):

        async with self.refresh_lock:

            guild = ctx.guild

            if guild is None:
                return

            embeds = await self.generate_guide_embeds(guild)

            # Ini adalah command MEMBER-FACING.
            # Tidak ada informasi internal mengenai permission
            # atau aturan visibilitas di output.
            # Discord mengizinkan maksimal 10 embed per pesan.
            for index in range(0, len(embeds), 10):
                await ctx.send(
                    embeds=embeds[index:index + 10]
                )

    @channel_guide.error
    async def channel_guide_error(
        self,
        ctx,
        error
    ):

        # Tampilkan error ke console supaya penyebabnya tidak
        # menjadi "command diam" ketika terjadi exception.
        original_error = getattr(
            error,
            "original",
            error
        )

        print(
            "[NANZ CHANNEL GUIDE] channelguide error: "
            f"{type(original_error).__name__}: {original_error}"
        )

        try:
            await ctx.send(
                "❌ Channel Guide gagal ditampilkan.\n"
                "Cek console bot untuk detail error.",
                delete_after=10
            )
        except Exception as send_error:
            print(
                "[NANZ CHANNEL GUIDE] Gagal mengirim pesan error: "
                f"{send_error}"
            )

    # =====================================================
    # CHANNEL GUIDE CONFIG PANEL
    # =====================================================

    @commands.command(
        name="channelguideconfig",
        aliases=[
            "channelguidepanel",
            "guideconfig"
        ]
    )
    @commands.has_permissions(
        administrator=True
    )
    async def channel_guide_config(
        self,
        ctx
    ):

        guild = ctx.guild

        if guild is None:
            return

        visible_categories = self.get_visible_categories(guild)

        total_channels = sum(
            len(self.get_visible_channels(category))
            for category in visible_categories
        )

        embed = discord.Embed(
            title="⚙️ Channel Guide Settings",
            description=(
                "Gunakan panel ini untuk mengatur "
                "deskripsi channel dan kategori.\n\n"
                "Tekan **Cari Channel / Kategori**, "
                "cari nama yang diinginkan, lalu pilih "
                "hasilnya untuk mengisi deskripsi."
            ),
            color=discord.Color.from_rgb(
                100,
                70,
                180
            )
        )

        embed.add_field(
            name="📚 Channel Guide",
            value=(
                f"**{len(visible_categories)}** kategori\n"
                f"**{total_channels}** channel"
            ),
            inline=False
        )

        embed.set_footer(
            text="Panel konfigurasi hanya untuk administrator."
        )

        await ctx.send(
            embed=embed,
            view=self.GuidePanel(
                self,
                guild
            )
        )

    # =====================================================
    # ERROR HANDLER
    # =====================================================

    @channel_guide_config.error
    async def channel_guide_config_error(
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
