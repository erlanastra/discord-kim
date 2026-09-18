import discord
from discord.ext import commands, tasks
import asyncio


# ============================================================
# MUSIC BOT DIRECTORY
# Konsep seperti Staff Directory, tetapi khusus MUSIC BOT.
#
# Fitur:
# - Hanya menampilkan member BOT yang memiliki MUSIC_ROLE_ID
# - Maksimal 10 bot per embed
# - Menampilkan apakah bot FREE / DIPAKAI di voice channel
# - Menampilkan voice channel yang sedang digunakan
# - Jarak antar bot dibuat rapat agar panel tidak terlalu panjang
# - Auto refresh saat bot masuk/keluar/pindah voice
# - Auto refresh saat bot mendapat / kehilangan role music
# - Cache + debounce untuk mengurangi PATCH dan rate limit 429
# ============================================================


class BotDirectory(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # ======================================================
        # CONFIG
        # ======================================================

        # Channel tempat panel Music Bot Directory ditampilkan.
        # Akan diisi otomatis oleh !setupbotdirectory
        self.BOT_CHANNEL_ID = 0

        # Role yang digunakan untuk menandai Music Bot.
        # Hanya BOT yang mempunyai role ini yang akan ditampilkan.
        self.MUSIC_ROLE_ID = 1473506596851159080

        # Maksimal bot per embed.
        self.BOTS_PER_EMBED = 10

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
    # VOICE STATUS
    # ==========================================================

    def get_voice_status(self, member):
        """Menampilkan status FREE atau sedang digunakan."""

        if member.voice and member.voice.channel:
            channel = member.voice.channel

            return (
                "🟢 **Dipakai**  •  "
                f"🎧 {channel.mention}"
            )

        return "⚪ **Free**  •  Tidak digunakan"

    # ==========================================================
    # GENERATE EMBED
    # ==========================================================

    def generate_bot_embed(self, guild, bots, page, total_pages):
        """Membuat satu embed Music Bot Directory."""

        embed = discord.Embed(
            color=discord.Color.blurple()
        )

        # ------------------------------------------------------
        # HEADER
        # ------------------------------------------------------

        embed.set_author(
            name="🎵  Music Bot Directory",
            icon_url=(
                guild.icon.url
                if guild.icon
                else discord.Embed.Empty
            )
        )

        # ------------------------------------------------------
        # EMPTY
        # ------------------------------------------------------

        if not bots:
            embed.description = (
                "╰─ *Belum ada Music Bot yang terdeteksi.*"
            )

            embed.set_footer(
                text="nanZ Server  •  Music Bot  •  0 Bot"
            )

            return embed

        # ------------------------------------------------------
        # SUMMARY GLOBAL
        # ------------------------------------------------------

        used_count = sum(
            1
            for member in bots
            if member.voice and member.voice.channel
        )

        free_count = len(bots) - used_count

        embed.description = (
            f"🟢 **Dipakai:** `{used_count}` bot  •  "
            f"⚪ **Free:** `{free_count}` bot  •  "
            f"📋 **Total:** `{len(bots)}` bot"
        )

        # ------------------------------------------------------
        # BOT LIST
        # ------------------------------------------------------
        # Dibuat RAPAT: tidak ada baris kosong antar bot.
        # Setiap bot hanya 3 baris.
        # ------------------------------------------------------

        blocks = []

        for index, member in enumerate(bots):
            global_index = (
                ((page - 1) * self.BOTS_PER_EMBED)
                + index
                + 1
            )

            status = self.get_voice_status(member)

            block = (
                f"**{global_index:02d}. {member.display_name}**\n"
                f"　└ {member.mention}\n"
                f"　　└ {status}"
            )

            blocks.append(block)

        # ------------------------------------------------------
        # FIELD SPLITTER
        # Discord field value maksimal 1024 karakter.
        # ------------------------------------------------------

        field_chunks = []
        current = []

        for block in blocks:
            candidate = "\n".join(current + [block])

            if current and len(candidate) > 1024:
                field_chunks.append(current)
                current = [block]
            else:
                current.append(block)

        if current:
            field_chunks.append(current)

        previous_count = 0

        for chunk_index, chunk in enumerate(field_chunks, start=1):
            start_number = (
                ((page - 1) * self.BOTS_PER_EMBED)
                + previous_count
                + 1
            )

            end_number = start_number + len(chunk) - 1
            previous_count += len(chunk)

            if len(field_chunks) == 1:
                field_name = f"🤖 Daftar Music Bot  •  {len(bots)} Bot"
            else:
                field_name = (
                    f"🤖 Daftar Music Bot  •  "
                    f"{start_number:02d}-{end_number:02d}"
                )

            embed.add_field(
                name=field_name,
                value="\n".join(chunk),
                inline=False
            )

        # ------------------------------------------------------
        # FOOTER
        # ------------------------------------------------------

        embed.set_footer(
            text=(
                "nanZ Server  •  Music Bot  •  "
                f"Halaman {page}/{total_pages}"
            )
        )

        return embed

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

                author = message.embeds[0].author

                if not author or not author.name:
                    continue

                if "Music Bot Directory" not in author.name:
                    continue

                found.append(message.id)

        except discord.HTTPException as e:
            print(
                f"[MUSIC DIRECTORY] Gagal mencari message lama: {e}"
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
                f"[MUSIC DIRECTORY] Refresh task error: {e}"
            )

    # ==========================================================
    # REFRESH ALL PANELS
    # ==========================================================

    async def refresh_all_panels(self, guild):

        if not self.BOT_CHANNEL_ID:
            return

        # Jangan menjalankan dua refresh bersamaan.
        if self.refresh_lock.locked():
            return

        async with self.refresh_lock:
            channel = self.bot.get_channel(
                self.BOT_CHANNEL_ID
            )

            if not channel:
                print(
                    "[MUSIC DIRECTORY] Channel tidak ditemukan."
                )
                return

            bots = self.get_music_bots(guild)

            # --------------------------------------------------
            # PAGINATION
            # --------------------------------------------------

            if bots:
                pages = [
                    bots[start:start + self.BOTS_PER_EMBED]
                    for start in range(
                        0,
                        len(bots),
                        self.BOTS_PER_EMBED
                    )
                ]
            else:
                pages = [[]]

            total_pages = len(pages)

            # --------------------------------------------------
            # CARI MESSAGE LAMA
            # --------------------------------------------------

            if not self.message_ids:
                self.message_ids = (
                    await self.find_existing_messages(channel)
                )

            new_message_ids = []

            # --------------------------------------------------
            # UPDATE / CREATE
            # --------------------------------------------------

            for page_number, page_bots in enumerate(
                pages,
                start=1
            ):
                embed = self.generate_bot_embed(
                    guild,
                    page_bots,
                    page_number,
                    total_pages
                )

                embed_data = embed.to_dict()
                old_embed_data = self.embed_cache.get(
                    page_number
                )

                message_id = (
                    self.message_ids[page_number - 1]
                    if page_number - 1 < len(self.message_ids)
                    else None
                )

                # ------------------------------------------------
                # MESSAGE SUDAH ADA
                # ------------------------------------------------

                if message_id:
                    if old_embed_data == embed_data:
                        new_message_ids.append(message_id)
                        continue

                    try:
                        message = channel.get_partial_message(
                            message_id
                        )

                        await message.edit(embed=embed)

                        self.embed_cache[page_number] = embed_data
                        new_message_ids.append(message_id)
                        continue

                    except discord.NotFound:
                        print(
                            f"[MUSIC DIRECTORY] Message halaman "
                            f"{page_number} sudah tidak ditemukan."
                        )

                        self.embed_cache.pop(
                            page_number,
                            None
                        )

                    except discord.HTTPException as e:
                        print(
                            f"[MUSIC DIRECTORY] Gagal edit halaman "
                            f"{page_number}: {e}"
                        )
                        continue

                # ------------------------------------------------
                # MESSAGE BELUM ADA
                # ------------------------------------------------

                try:
                    new_message = await channel.send(
                        embed=embed
                    )

                except discord.HTTPException as e:
                    print(
                        f"[MUSIC DIRECTORY] Gagal membuat halaman "
                        f"{page_number}: {e}"
                    )
                    continue

                new_message_ids.append(new_message.id)
                self.embed_cache[page_number] = embed_data

                print(
                    f"[MUSIC DIRECTORY] Panel halaman "
                    f"{page_number} dibuat."
                )

            # --------------------------------------------------
            # HAPUS HALAMAN BERLEBIH
            # --------------------------------------------------

            old_message_ids = self.message_ids[
                len(new_message_ids):
            ]

            for message_id in old_message_ids:
                try:
                    message = channel.get_partial_message(
                        message_id
                    )
                    await message.delete()

                except (
                    discord.NotFound,
                    discord.HTTPException
                ):
                    pass

            # Bersihkan cache halaman lama.
            for page_number in list(self.embed_cache.keys()):
                if page_number > total_pages:
                    self.embed_cache.pop(
                        page_number,
                        None
                    )

            self.message_ids = new_message_ids

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
        """Refresh ketika Music Bot masuk, keluar, atau pindah voice."""

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

        self.schedule_refresh(member.guild)

    # ==========================================================
    # PRESENCE UPDATE
    # ==========================================================

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        """Refresh jika status online/idle/dnd/offline berubah."""

        if not after.bot:
            return

        if before.status == after.status:
            return

        if not any(
            role.id == self.MUSIC_ROLE_ID
            for role in after.roles
        ):
            return

        self.schedule_refresh(after.guild)

    # ==========================================================
    # ROLE UPDATE
    # ==========================================================

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
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

        self.schedule_refresh(after.guild)

    # ==========================================================
    # MEMBER JOIN / REMOVE
    # ==========================================================

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not member.bot:
            return

        if any(
            role.id == self.MUSIC_ROLE_ID
            for role in member.roles
        ):
            self.schedule_refresh(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if not member.bot:
            return

        if any(
            role.id == self.MUSIC_ROLE_ID
            for role in member.roles
        ):
            self.schedule_refresh(member.guild)

    # ==========================================================
    # AUTO REFRESH
    # ==========================================================

    @tasks.loop(minutes=10)
    async def update_directory(self):
        await self.bot.wait_until_ready()

        if not self.BOT_CHANNEL_ID:
            return

        channel = self.bot.get_channel(
            self.BOT_CHANNEL_ID
        )

        if not channel:
            return

        await self.refresh_all_panels(channel.guild)

    @update_directory.before_loop
    async def before_update_directory(self):
        await self.bot.wait_until_ready()

    # ==========================================================
    # SETUP COMMAND
    # ==========================================================

    @commands.command(name="setupbotdirectory")
    @commands.has_permissions(administrator=True)
    async def setup_bot_directory(self, ctx):
        """Jalankan !setupbotdirectory di channel panel."""

        self.BOT_CHANNEL_ID = ctx.channel.id

        # Reset cache supaya setup membaca panel lama / membuat baru.
        self.message_ids.clear()
        self.embed_cache.clear()

        try:
            await ctx.message.delete()
        except Exception:
            pass

        await self.refresh_all_panels(ctx.guild)

        print(
            f"[MUSIC DIRECTORY] Directory berhasil dibuat di "
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
    await bot.add_cog(BotDirectory(bot))
