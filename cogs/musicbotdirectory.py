import discord
from discord.ext import commands, tasks
import asyncio


class BotDirectory(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # ======================================================
        # CONFIG
        # ======================================================

        # Channel tempat panel Music Bot Directory ditampilkan.
        self.BOT_CHANNEL_ID = 1550475918454030386

        # Role yang digunakan untuk menandai Music Bot.
        # Hanya BOT yang mempunyai role ini yang akan ditampilkan.
        self.MUSIC_ROLE_ID = 1473506596851159080

        # ======================================================
        # CUSTOM EMOJI
        # ======================================================

        self.ONLINE_EMOJI_ID = 1550516004096974888
        self.OFFLINE_EMOJI_ID = 1550516157113434255

        # Emoji untuk judul panel.
        self.TITLE_EMOJI_ID = 1512787254312042496
        self.TITLE_EMOJI_NAME = "arrow_blue"
        self.TITLE_EMOJI_ANIMATED = True

        # Emoji pin untuk channel voice.
        self.PIN_EMOJI_ID = 1553688245769085099
        self.PIN_EMOJI_NAME = "pin"
        self.PIN_EMOJI_ANIMATED = True

        # ======================================================
        # REFRESH CONFIG
        # ======================================================

        # Jeda setelah event sebelum refresh.
        self.REFRESH_DELAY = 3

        # Safety refresh setiap 10 menit.
        self.AUTO_REFRESH_MINUTES = 10

        # ======================================================
        # MESSAGE / CACHE
        # ======================================================

        self.message_ids = []

        self.embed_cache = {}

        self.refresh_lock = asyncio.Lock()

        self.refresh_task = None

        # ======================================================
        # START AUTO REFRESH
        # ======================================================

        self.update_directory.start()

    # ==========================================================
    # GET MUSIC BOTS
    # ==========================================================

    def get_music_bots(self, guild):
        """
        Mengambil semua BOT yang memiliki role Music Bot.
        """

        role = guild.get_role(self.MUSIC_ROLE_ID)

        if not role:
            return []

        bots = [
            member
            for member in role.members
            if member.bot
        ]

        return sorted(
            bots,
            key=lambda member: member.display_name.lower()
        )

    # ==========================================================
    # CUSTOM EMOJI
    # ==========================================================

    def get_custom_emoji(self, emoji_id, fallback="•"):
        """
        Mengambil custom emoji berdasarkan ID.

        Jika emoji belum tersedia di cache bot,
        gunakan fallback.
        """

        if not emoji_id:
            return fallback

        emoji = self.bot.get_emoji(emoji_id)

        if emoji:
            return str(emoji)

        return fallback

    # ==========================================================
    # FIXED CUSTOM EMOJI
    # ==========================================================

    def get_fixed_emoji(
        self,
        emoji_id,
        name,
        animated=False
    ):
        """
        Membuat format custom emoji Discord secara langsung.

        Berguna agar emoji tetap bisa dirender walaupun
        bot belum mendapatkan emoji dari cache.
        """

        if not emoji_id or not name:
            return ""

        prefix = "a" if animated else ""

        return f"<{prefix}:{name}:{emoji_id}>"

    # ==========================================================
    # VOICE STATUS
    # ==========================================================

    def get_online_offline_emoji(self, member):
        """
        Terpakai:
        Music Bot sedang berada di voice channel.

        Tidak Terpakai:
        Music Bot tidak berada di voice channel.
        """

        if member.voice and member.voice.channel:

            return self.get_custom_emoji(
                self.ONLINE_EMOJI_ID,
                "🟢"
            )

        return self.get_custom_emoji(
            self.OFFLINE_EMOJI_ID,
            "⚪"
        )

    # ==========================================================
    # GENERATE BOT BLOCK
    # ==========================================================

    def generate_bot_block(
        self,
        index,
        member
    ):
        """
        Membuat satu blok tampilan untuk setiap Music Bot.

        Contoh:

        **01. Hydra**
        > 🟢 Terpakai
        > 📌・Music Lounge
        """

        status_emoji = self.get_online_offline_emoji(
            member
        )

        pin_emoji = self.get_fixed_emoji(
            self.PIN_EMOJI_ID,
            self.PIN_EMOJI_NAME,
            self.PIN_EMOJI_ANIMATED
        )

        # ------------------------------------------------------
        # TERPAKAI
        # ------------------------------------------------------

        if member.voice and member.voice.channel:

            channel = member.voice.channel

            return (
                f"**{index:02d}. {member.display_name}**\n"
                f"> {status_emoji} Terpakai\n"
                f"> {pin_emoji}・{channel.mention}"
            )

        # ------------------------------------------------------
        # TIDAK TERPAKAI
        # ------------------------------------------------------

        return (
            f"**{index:02d}. {member.display_name}**\n"
            f"> {status_emoji} Tidak Terpakai"
        )

    # ==========================================================
    # GENERATE EMBEDS
    # ==========================================================

    def generate_bot_embeds(
        self,
        guild,
        bots
    ):
        """
        Membuat panel Music Bot Directory.

        Description Discord maksimal 4096 karakter.
        Karena itu daftar bot otomatis dibagi menjadi
        beberapa embed jika terlalu panjang.

        Setiap embed tetap menggunakan layout yang sama.
        """

        title_emoji = self.get_fixed_emoji(
            self.TITLE_EMOJI_ID,
            self.TITLE_EMOJI_NAME,
            self.TITLE_EMOJI_ANIMATED
        )

        pin_emoji = self.get_fixed_emoji(
            self.PIN_EMOJI_ID,
            self.PIN_EMOJI_NAME,
            self.PIN_EMOJI_ANIMATED
        )

        online_emoji = self.get_custom_emoji(
            self.ONLINE_EMOJI_ID,
            "🟢"
        )

        offline_emoji = self.get_custom_emoji(
            self.OFFLINE_EMOJI_ID,
            "⚪"
        )

        # ======================================================
        # EMPTY
        # ======================================================

        if not bots:

            embed = discord.Embed(
                title=(
                    f"{title_emoji} Music Bot Directory"
                ),
                description=(
                    "📭 Belum ada Music Bot yang "
                    "terdaftar di directory ini."
                ),
                color=discord.Color.blurple()
            )

            if guild.icon:
                embed.set_thumbnail(
                    url=guild.icon.url
                )

            embed.set_footer(
                text=(
                    "nanZ Server  •  "
                    "Music Bot Directory  •  "
                    "0 Bot"
                )
            )

            return [embed]

        # ======================================================
        # SUMMARY
        # ======================================================

        used_count = sum(
            1
            for member in bots
            if member.voice
            and member.voice.channel
        )

        unused_count = (
            len(bots) - used_count
        )

        summary = (
            f"{online_emoji} Terpakai `{used_count}`  •  "
            f"{offline_emoji} Tidak Terpakai `{unused_count}`  •  "
            f"{pin_emoji} Total `{len(bots)}`"
        )

        # ======================================================
        # BUILD BOT BLOCKS
        # ======================================================

        blocks = []

        for index, member in enumerate(
            bots,
            start=1
        ):

            block = self.generate_bot_block(
                index,
                member
            )

            blocks.append(block)

        # ======================================================
        # SPLIT DESCRIPTION
        # ======================================================

        # Discord description max:
        # 4096 karakter.
        #
        # Kita gunakan 3900 sebagai safety margin.

        MAX_DESCRIPTION = 3900

        descriptions = []

        current_description = (
            f"{summary}\n\n"
        )

        for block in blocks:

            candidate = (
                current_description
                + block
                + "\n\n"
            )

            # Jika melebihi batas,
            # simpan bagian sebelumnya.
            if (
                len(candidate) > MAX_DESCRIPTION
                and current_description.strip()
                != summary
            ):

                descriptions.append(
                    current_description.rstrip()
                )

                current_description = (
                    f"{block}\n\n"
                )

            else:

                current_description = (
                    candidate
                )

        if current_description.strip():

            descriptions.append(
                current_description.rstrip()
            )

        # ======================================================
        # CREATE EMBEDS
        # ======================================================

        embeds = []

        total_parts = len(
            descriptions
        )

        for index, description in enumerate(
            descriptions,
            start=1
        ):

            embed = discord.Embed(
                title=(
                    f"{title_emoji} "
                    f"Music Bot Directory"
                ),
                description=description,
                color=discord.Color.blurple()
            )

            # Server icon.
            if guild.icon:

                embed.set_thumbnail(
                    url=guild.icon.url
                )

            # --------------------------------------------------
            # FOOTER
            # --------------------------------------------------

            footer_text = (
                "nanZ Server  •  "
                "Music Bot Directory  •  "
                f"{len(bots)} Bot"
            )

            if total_parts > 1:

                footer_text += (
                    f"  •  "
                    f"Bagian {index}/{total_parts}"
                )

            embed.set_footer(
                text=footer_text
            )

            embeds.append(embed)

        return embeds

    # ==========================================================
    # FIND EXISTING MESSAGES
    # ==========================================================

    async def find_existing_messages(
        self,
        channel
    ):
        """
        Mencari panel Music Bot Directory lama.
        """

        found = []

        try:

            async for message in channel.history(
                limit=100
            ):

                # Hanya message dari bot.
                if message.author != self.bot.user:
                    continue

                # Harus memiliki embed.
                if not message.embeds:
                    continue

                is_directory = False

                # --------------------------------------------------
                # CHECK EMBED TITLE
                # --------------------------------------------------

                for embed in message.embeds:

                    if (
                        embed.title
                        and "Music Bot Directory"
                        in embed.title
                    ):

                        is_directory = True
                        break

                    # --------------------------------------------------
                    # CHECK OLD AUTHOR
                    # --------------------------------------------------

                    if (
                        embed.author
                        and embed.author.name
                        and "Music Bot Directory"
                        in embed.author.name
                    ):

                        is_directory = True
                        break

                if is_directory:

                    found.append(
                        message.id
                    )

        except discord.HTTPException as e:

            print(
                "[MUSIC DIRECTORY] "
                f"Gagal mencari message lama: {e}"
            )

        # History dimulai terbaru -> terlama.
        found.reverse()

        return found

    # ==========================================================
    # SCHEDULE REFRESH
    # ==========================================================

    def schedule_refresh(
        self,
        guild
    ):
        """
        Menjadwalkan refresh dengan debounce.

        Event voice/role yang terjadi berdekatan
        tidak akan membuat banyak refresh.
        """

        if not self.BOT_CHANNEL_ID:
            return

        if (
            self.refresh_task
            and not self.refresh_task.done()
        ):
            return

        self.refresh_task = asyncio.create_task(
            self._delayed_refresh(guild)
        )

    # ==========================================================
    # DELAYED REFRESH
    # ==========================================================

    async def _delayed_refresh(
        self,
        guild
    ):

        try:

            await asyncio.sleep(
                self.REFRESH_DELAY
            )

            await self.refresh_all_panels(
                guild
            )

        except asyncio.CancelledError:

            pass

        except Exception as e:

            print(
                "[MUSIC DIRECTORY] "
                f"Refresh task error: {e}"
            )

    # ==========================================================
    # REFRESH ALL PANELS
    # ==========================================================

    async def refresh_all_panels(
        self,
        guild
    ):

        if not self.BOT_CHANNEL_ID:
            return

        # Jangan jalankan refresh bersamaan.
        if self.refresh_lock.locked():
            return

        async with self.refresh_lock:

            channel = self.bot.get_channel(
                self.BOT_CHANNEL_ID
            )

            if not channel:

                print(
                    "[MUSIC DIRECTORY] "
                    "Channel tidak ditemukan."
                )

                return

            # --------------------------------------------------
            # GET BOTS
            # --------------------------------------------------

            bots = self.get_music_bots(
                guild
            )

            # --------------------------------------------------
            # GENERATE EMBEDS
            # --------------------------------------------------

            embeds = self.generate_bot_embeds(
                guild,
                bots
            )

            # --------------------------------------------------
            # SPLIT MAX 10 EMBEDS PER MESSAGE
            # --------------------------------------------------

            embed_groups = [
                embeds[i:i + 10]
                for i in range(
                    0,
                    len(embeds),
                    10
                )
            ]

            # --------------------------------------------------
            # FIND OLD MESSAGES
            # --------------------------------------------------

            if not self.message_ids:

                self.message_ids = (
                    await self.find_existing_messages(
                        channel
                    )
                )

            new_message_ids = []

            # ==================================================
            # PROCESS EACH MESSAGE GROUP
            # ==================================================

            for group_index, embed_group in enumerate(
                embed_groups
            ):

                cache_key = (
                    f"group_{group_index}"
                )

                embed_data = [
                    embed.to_dict()
                    for embed in embed_group
                ]

                old_message_id = None

                if (
                    group_index
                    < len(self.message_ids)
                ):

                    old_message_id = (
                        self.message_ids[
                            group_index
                        ]
                    )

                # --------------------------------------------------
                # UPDATE EXISTING MESSAGE
                # --------------------------------------------------

                if old_message_id:

                    old_embed_data = (
                        self.embed_cache.get(
                            cache_key
                        )
                    )

                    # Tidak ada perubahan.
                    if (
                        old_embed_data
                        == embed_data
                    ):

                        new_message_ids.append(
                            old_message_id
                        )

                        continue

                    try:

                        message = (
                            channel.get_partial_message(
                                old_message_id
                            )
                        )

                        await message.edit(
                            embeds=embed_group
                        )

                        self.embed_cache[
                            cache_key
                        ] = embed_data

                        new_message_ids.append(
                            old_message_id
                        )

                        continue

                    except discord.NotFound:

                        print(
                            "[MUSIC DIRECTORY] "
                            "Panel lama tidak ditemukan."
                        )

                    except discord.HTTPException as e:

                        print(
                            "[MUSIC DIRECTORY] "
                            f"Gagal edit panel: {e}"
                        )

                # --------------------------------------------------
                # CREATE NEW MESSAGE
                # --------------------------------------------------

                try:

                    new_message = (
                        await channel.send(
                            embeds=embed_group
                        )
                    )

                    new_message_ids.append(
                        new_message.id
                    )

                    self.embed_cache[
                        cache_key
                    ] = embed_data

                    print(
                        "[MUSIC DIRECTORY] "
                        f"Panel {group_index + 1} "
                        "berhasil dibuat."
                    )

                except discord.HTTPException as e:

                    print(
                        "[MUSIC DIRECTORY] "
                        f"Gagal membuat panel: {e}"
                    )

            # ==================================================
            # DELETE OLD DUPLICATE MESSAGES
            # ==================================================

            old_message_ids = [
                message_id
                for message_id
                in self.message_ids
                if message_id
                not in new_message_ids
            ]

            for old_id in old_message_ids:

                try:

                    message = (
                        channel.get_partial_message(
                            old_id
                        )
                    )

                    await message.delete()

                except (
                    discord.NotFound,
                    discord.HTTPException
                ):

                    pass

            # ==================================================
            # UPDATE CACHE
            # ==================================================

            self.message_ids = (
                new_message_ids
            )

            # Bersihkan cache yang sudah tidak digunakan.
            valid_cache_keys = {
                f"group_{index}"
                for index in range(
                    len(embed_groups)
                )
            }

            self.embed_cache = {
                key: value
                for key, value
                in self.embed_cache.items()
                if key in valid_cache_keys
            }

    # ==========================================================
    # VOICE STATE UPDATE
    # ==========================================================

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member,
        before,
        after
    ):
        """
        Refresh ketika Music Bot:
        - masuk voice
        - keluar voice
        - pindah voice
        """

        if not member.bot:
            return

        # Tidak ada perubahan channel.
        if before.channel == after.channel:
            return

        # Hanya Music Bot.
        if not any(
            role.id == self.MUSIC_ROLE_ID
            for role in member.roles
        ):
            return

        self.schedule_refresh(
            member.guild
        )

    # ==========================================================
    # MEMBER ROLE UPDATE
    # ==========================================================

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before,
        after
    ):
        """
        Refresh jika role Music Bot berubah.
        """

        if not after.bot:
            return

        if before.roles == after.roles:
            return

        before_has_role = any(
            role.id == self.MUSIC_ROLE_ID
            for role in before.roles
        )

        after_has_role = any(
            role.id == self.MUSIC_ROLE_ID
            for role in after.roles
        )

        # Role Music Bot tidak berubah.
        if before_has_role == after_has_role:
            return

        self.schedule_refresh(
            after.guild
        )

    # ==========================================================
    # MEMBER JOIN
    # ==========================================================

    @commands.Cog.listener()
    async def on_member_join(
        self,
        member
    ):

        if not member.bot:
            return

        if any(
            role.id == self.MUSIC_ROLE_ID
            for role in member.roles
        ):

            self.schedule_refresh(
                member.guild
            )

    # ==========================================================
    # MEMBER REMOVE
    # ==========================================================

    @commands.Cog.listener()
    async def on_member_remove(
        self,
        member
    ):

        if not member.bot:
            return

        if any(
            role.id == self.MUSIC_ROLE_ID
            for role in member.roles
        ):

            self.schedule_refresh(
                member.guild
            )

    # ==========================================================
    # AUTO REFRESH
    # ==========================================================

    @tasks.loop(
        minutes=10
    )
    async def update_directory(
        self
    ):

        await self.bot.wait_until_ready()

        if not self.BOT_CHANNEL_ID:
            return

        channel = self.bot.get_channel(
            self.BOT_CHANNEL_ID
        )

        if not channel:
            return

        await self.refresh_all_panels(
            channel.guild
        )

    # ==========================================================
    # BEFORE AUTO REFRESH
    # ==========================================================

    @update_directory.before_loop
    async def before_update_directory(
        self
    ):

        await self.bot.wait_until_ready()

    # ==========================================================
    # SETUP COMMAND
    # ==========================================================

    @commands.command(
        name="setupbotdirectory"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def setup_bot_directory(
        self,
        ctx
    ):
        """
        Jalankan:

        !setupbotdirectory

        Command ini akan membuat / memindahkan
        panel Music Bot Directory ke channel
        tempat command dijalankan.
        """

        self.BOT_CHANNEL_ID = (
            ctx.channel.id
        )

        # Reset cache.
        self.message_ids.clear()
        self.embed_cache.clear()

        # Hapus command.
        try:

            await ctx.message.delete()

        except Exception:

            pass

        # Refresh panel.
        await self.refresh_all_panels(
            ctx.guild
        )

        print(
            "[MUSIC DIRECTORY] "
            f"Directory berhasil dibuat di "
            f"#{ctx.channel.name}."
        )

    # ==========================================================
    # UNLOAD
    # ==========================================================

    def cog_unload(
        self
    ):

        # Stop auto refresh.
        self.update_directory.cancel()

        # Stop delayed refresh.
        if (
            self.refresh_task
            and not self.refresh_task.done()
        ):

            self.refresh_task.cancel()


# ==============================================================
# SETUP
# ==============================================================

async def setup(bot):

    await bot.add_cog(
        BotDirectory(bot)
    )