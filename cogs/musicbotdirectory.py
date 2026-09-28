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
        self.MUSIC_ROLE_ID = 1473506596851159080

        # ======================================================
        # CUSTOM EMOJI
        # ======================================================

        self.ONLINE_EMOJI_ID = 1550516004096974888
        self.OFFLINE_EMOJI_ID = 1550516157113434255

        # Emoji judul.
        self.TITLE_EMOJI_ID = 1512787254312042496
        self.TITLE_EMOJI_NAME = "arrow_blue"
        self.TITLE_EMOJI_ANIMATED = True

        # Emoji pin/channel.
        self.PIN_EMOJI_ID = 1553688245769085099
        self.PIN_EMOJI_NAME = "pin"
        self.PIN_EMOJI_ANIMATED = True

        # Jeda setelah event sebelum refresh.
        self.REFRESH_DELAY = 3

        # Safety refresh.
        self.AUTO_REFRESH_MINUTES = 10

        # ======================================================
        # MESSAGE / CACHE
        # ======================================================

        self.message_ids = []
        self.embed_cache = {}
        self.refresh_lock = asyncio.Lock()
        self.refresh_task = None

        # ======================================================
        # START TASK
        # ======================================================

        self.update_directory.start()

    # ==========================================================
    # GET MUSIC BOTS
    # ==========================================================

    def get_music_bots(self, guild):
        """Mengambil BOT yang memiliki role Music Bot."""

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
        Mengambil custom emoji dari cache Discord.

        Jika emoji belum masuk cache, gunakan fallback Unicode
        supaya tidak pernah muncul sebagai teks 'ONLINE/OFFLINE'.
        """

        if not emoji_id:
            return fallback

        emoji = self.bot.get_emoji(emoji_id)

        if emoji:
            return str(emoji)

        return fallback

    def get_fixed_emoji(self, emoji_id, name, animated=False):
        """
        Membuat format custom emoji langsung dari ID.

        Ini dipakai untuk emoji yang namanya sudah diketahui,
        terutama emoji judul, agar tidak bergantung pada cache.
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
        Terpakai    = Music Bot sedang berada di voice channel.
        Tidak Terpakai = Music Bot tidak berada di voice channel.
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

    def get_voice_status(self, member):
        """Menghasilkan status penggunaan Music Bot."""

        status_emoji = self.get_online_offline_emoji(member)

        if member.voice and member.voice.channel:
            channel = member.voice.channel

            return (
                f"{status_emoji} **Terpakai**\n"
                f"　{self.get_fixed_emoji(self.PIN_EMOJI_ID, self.PIN_EMOJI_NAME, self.PIN_EMOJI_ANIMATED)} "
                f"{channel.mention}"
            )

        return f"{status_emoji} **Tidak Terpakai**"

    # ==========================================================
    # GENERATE EMBED
    # ==========================================================

    def generate_bot_embeds(self, guild, bots):
        """
        Membuat embed Music Bot Directory dengan aman terhadap limit Discord.

        Discord memiliki beberapa batas penting:
        - 1 field value maksimal 1024 karakter
        - 1 embed maksimal 25 fields
        - total karakter embed maksimal 6000

        Karena jumlah Music Bot bisa bertambah, daftar bot otomatis
        dipecah menjadi beberapa embed jika diperlukan.
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

        # ------------------------------------------------------
        # EMPTY
        # ------------------------------------------------------
        if not bots:
            embed = discord.Embed(
                title=f"{title_emoji} Music Bot Directory",
                description=(
                    "Pantau penggunaan **Music Bot** di server secara real-time.\n\n"
                    "📭 Belum ada **Music Bot** yang memiliki role "
                    "yang terdaftar di directory ini."
                ),
                color=discord.Color.blurple()
            )

            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)

            embed.set_footer(text="nanZ Server  •  Music Bot Directory  •  0 Bot")
            return [embed]

        # ------------------------------------------------------
        # SUMMARY
        # ------------------------------------------------------
        used_count = sum(
            1
            for member in bots
            if member.voice and member.voice.channel
        )
        unused_count = len(bots) - used_count

        online_emoji = self.get_custom_emoji(
            self.ONLINE_EMOJI_ID, "🟢"
        )
        offline_emoji = self.get_custom_emoji(
            self.OFFLINE_EMOJI_ID, "⚪"
        )

        summary = (
            f"{online_emoji} **Terpakai** `{used_count}`  •  "
            f"{offline_emoji} **Tidak Terpakai** `{unused_count}`  •  "
            f"{pin_emoji} **Total** `{len(bots)}`"
        )

        # ------------------------------------------------------
        # BUAT BLOK BOT
        # ------------------------------------------------------
        bot_blocks = []

        for index, member in enumerate(bots, start=1):
            status = self.get_voice_status(member)

            block = (
                f"**`{index:02d}` · {member.display_name}**\n"
                f"{status}"
            )

            # Field value Discord maksimal 1024 karakter.
            if len(block) > 1000:
                block = block[:997] + "..."

            bot_blocks.append(block)

        # ------------------------------------------------------
        # PECAH BLOK MENJADI CHUNK AMAN
        # ------------------------------------------------------
        chunks = []
        current = []
        current_length = 0

        for block in bot_blocks:
            # +2 untuk newline antar blok.
            extra = len(block) + (2 if current else 0)

            if current and current_length + extra > 1000:
                chunks.append(current)
                current = []
                current_length = 0

            current.append(block)
            current_length += len(block) + (2 if len(current) > 1 else 0)

        if current:
            chunks.append(current)

        # ------------------------------------------------------
        # BUAT EMBED
        # ------------------------------------------------------
        embeds = []
        max_chunks_per_embed = 5

        for embed_index in range(0, len(chunks), max_chunks_per_embed):
            embed_chunks = chunks[embed_index:embed_index + max_chunks_per_embed]

            embed = discord.Embed(
                title=f"{title_emoji} Music Bot Directory",
                description=(
                    "Pantau penggunaan **Music Bot** di server secara real-time."
                ),
                color=discord.Color.blurple()
            )

            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)

            # Summary hanya ditampilkan di embed pertama.
            if embed_index == 0:
                embed.add_field(
                    name="Status Music Bot",
                    value=summary,
                    inline=False
                )

            for chunk_index, chunk in enumerate(embed_chunks):
                first_number = embed_index * max_chunks_per_embed
                field_name = (
                    "🎵 Daftar Music Bot"
                    if embed_index == 0 and chunk_index == 0
                    else "🎵 Music Bot"
                )

                embed.add_field(
                    name=field_name,
                    value="\n\n".join(chunk),
                    inline=False
                )

            if len(chunks) > max_chunks_per_embed:
                embed.set_footer(
                    text=(
                        f"nanZ Server  •  Music Bot Directory  •  "
                        f"Bagian {embed_index // max_chunks_per_embed + 1}"
                    )
                )
            else:
                embed.set_footer(
                    text=(
                        "nanZ Server  •  Music Bot Directory  •  "
                        f"{len(bots)} Bot"
                    )
                )

            embeds.append(embed)

        return embeds

    # Kompatibilitas dengan kode lama yang memanggil fungsi singular.
    def generate_bot_embed(self, guild, bots):
        return self.generate_bot_embeds(guild, bots)[0]

    # ==========================================================
    # FIND OLD MESSAGES
    # ==========================================================

    async def find_existing_messages(self, channel):
        """Mencari panel Music Bot Directory yang sudah ada."""

        found = []

        try:
            async for message in channel.history(limit=100):

                if message.author != self.bot.user:
                    continue

                if not message.embeds:
                    continue

                embed = message.embeds[0]

                # Cek title baru.
                if embed.title and "Music Bot Directory" in embed.title:
                    found.append(message.id)
                    continue

                # Cek format lama yang menggunakan author.
                author = embed.author

                if (
                    author
                    and author.name
                    and "Music Bot Directory" in author.name
                ):
                    found.append(message.id)

        except discord.HTTPException as e:
            print(
                f"[MUSIC DIRECTORY] "
                f"Gagal mencari message lama: {e}"
            )

        # History dari terbaru -> terlama.
        found.reverse()

        return found

    # ==========================================================
    # SCHEDULE REFRESH
    # ==========================================================

    def schedule_refresh(self, guild):
        """Debounce refresh supaya event beruntun tidak spam Discord."""

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

    async def _delayed_refresh(self, guild):

        try:
            await asyncio.sleep(self.REFRESH_DELAY)
            await self.refresh_all_panels(guild)

        except asyncio.CancelledError:
            pass

        except Exception as e:
            print(
                f"[MUSIC DIRECTORY] "
                f"Refresh task error: {e}"
            )

    # ==========================================================
    # REFRESH ALL PANELS
    # ==========================================================

    async def refresh_all_panels(self, guild):
        if not self.BOT_CHANNEL_ID:
            return

        if self.refresh_lock.locked():
            return

        async with self.refresh_lock:
            channel = self.bot.get_channel(self.BOT_CHANNEL_ID)

            if not channel:
                print("[MUSIC DIRECTORY] Channel tidak ditemukan.")
                return

            bots = self.get_music_bots(guild)
            embeds = self.generate_bot_embeds(guild, bots)

            # Satu message maksimal 10 embeds. Jika lebih, Discord tidak
            # mengizinkannya sehingga kita buat beberapa message secara aman.
            message_chunks = [embeds[i:i + 10] for i in range(0, len(embeds), 10)]

            if not self.message_ids:
                self.message_ids = await self.find_existing_messages(channel)

            new_message_ids = []

            for index, embed_chunk in enumerate(message_chunks):
                message_id = self.message_ids[index] if index < len(self.message_ids) else None

                try:
                    if message_id:
                        message = channel.get_partial_message(message_id)
                        await message.edit(embeds=embed_chunk)
                    else:
                        message = await channel.send(embeds=embed_chunk)

                    new_message_ids.append(message.id)

                except discord.NotFound:
                    try:
                        message = await channel.send(embeds=embed_chunk)
                        new_message_ids.append(message.id)
                    except discord.HTTPException as e:
                        print(f"[MUSIC DIRECTORY] Gagal membuat panel: {e}")
                        return

                except discord.HTTPException as e:
                    print(f"[MUSIC DIRECTORY] Gagal update panel: {e}")
                    return

            # Hapus panel lama/duplikat yang sudah tidak diperlukan.
            for old_id in self.message_ids:
                if old_id in new_message_ids:
                    continue

                try:
                    message = channel.get_partial_message(old_id)
                    await message.delete()
                except (discord.NotFound, discord.HTTPException):
                    pass

            self.message_ids = new_message_ids

            print(
                "[MUSIC DIRECTORY] Panel berhasil diperbarui "
                f"({len(new_message_ids)} message)."
            )

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

        # Tidak ada perubahan channel voice.
        if before.channel == after.channel:
            return

        # Hanya Music Bot yang dipantau.
        if not any(
            role.id == self.MUSIC_ROLE_ID
            for role in member.roles
        ):
            return

        self.schedule_refresh(
            member.guild
        )

    # ==========================================================
    # ROLE UPDATE
    # ==========================================================

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before,
        after
    ):
        """Refresh jika role Music Bot berubah."""

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
    async def update_directory(self):

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
    async def before_update_directory(self):

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
        Jalankan !setupbotdirectory
        di channel tempat panel ingin dibuat.
        """

        self.BOT_CHANNEL_ID = (
            ctx.channel.id
        )

        # Reset cache supaya setup
        # membaca panel lama / membuat baru.
        self.message_ids.clear()
        self.embed_cache.clear()

        # Hapus command !setupbotdirectory.
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

    def cog_unload(self):

        self.update_directory.cancel()

        if (
            self.refresh_task
            and not self.refresh_task.done()
        ):
            self.refresh_task.cancel()


# ============================================================
# SETUP
# ============================================================

async def setup(bot):
    await bot.add_cog(
        BotDirectory(bot)
    )
