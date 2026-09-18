import discord
from discord.ext import commands, tasks
import asyncio


# ============================================================
# BOT DIRECTORY
# Konsep sama seperti Staff Directory, tetapi KHUSUS akun BOT.
# - Semua member dengan member.bot == True
# - Maksimal 10 bot per embed
# - Otomatis membuat beberapa halaman jika bot > 10
# - Status online/offline/idle/dnd
# - Refresh saat bot/member berubah
# - Cache agar tidak PATCH jika isi embed tidak berubah
# - Debounce untuk mengurangi Discord HTTP 429
# ============================================================


class BotDirectory(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # ======================================================
        # CONFIG
        # ======================================================

        # Akan diisi otomatis oleh !setupbotdirectory
        self.BOT_CHANNEL_ID = 0

        # Maksimal bot per embed
        self.BOTS_PER_EMBED = 10

        # Jeda refresh setelah event perubahan
        self.REFRESH_DELAY = 5

        # Auto refresh sebagai safety net
        self.AUTO_REFRESH_MINUTES = 10

        # ======================================================
        # MESSAGE / CACHE
        # ======================================================

        # Satu message = satu halaman
        self.message_ids = []

        # Cache embed per halaman
        self.embed_cache = {}

        # Mencegah refresh bersamaan
        self.refresh_lock = asyncio.Lock()

        # Debounce task
        self.refresh_task = None

        # ======================================================
        # START TASK
        # ======================================================

        self.update_directory.start()

    # ==========================================================
    # GET BOTS
    # ==========================================================

    def get_bots(self, guild):
        """Mengambil semua akun bot yang ada di guild."""

        bots = [
            member
            for member in guild.members
            if member.bot
        ]

        return sorted(
            bots,
            key=lambda member: member.display_name.lower()
        )

    # ==========================================================
    # STATUS
    # ==========================================================

    def get_status(self, member):
        """Mengubah status Discord menjadi tampilan yang ringkas."""

        status = member.status

        if status == discord.Status.online:
            return "🟢 **Online**"

        if status == discord.Status.idle:
            return "🟡 **Idle**"

        if status == discord.Status.dnd:
            return "🔴 **Do Not Disturb**"

        return "⚪ **Offline**"

    # ==========================================================
    # GENERATE EMBED
    # ==========================================================

    def generate_bot_embed(self, guild, bots, page, total_pages):
        """Membuat satu halaman Bot Directory."""

        embed = discord.Embed(
            color=discord.Color.blurple()
        )

        # ------------------------------------------------------
        # HEADER
        # ------------------------------------------------------

        embed.set_author(
            name="🤖  Bot Directory",
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
                "╰─ *Belum ada bot yang terdeteksi di server.*"
            )

            embed.set_footer(
                text="nanZ Server  •  Bot Directory  •  0 Bot"
            )

            return embed

        # ------------------------------------------------------
        # SUMMARY
        # ------------------------------------------------------

        online_count = sum(
            1
            for member in bots
            if member.status != discord.Status.offline
        )

        offline_count = len(bots) - online_count

        embed.description = (
            f"🟢 **Online:** `{online_count}` bot\n"
            f"⚪ **Offline:** `{offline_count}` bot\n"
            f"📋 **Total:** `{len(bots)}` bot"
        )

        # ------------------------------------------------------
        # BOT LIST
        # ------------------------------------------------------

        blocks = []

        for index, member in enumerate(bots):
            global_index = (
                ((page - 1) * self.BOTS_PER_EMBED)
                + index
                + 1
            )

            status = self.get_status(member)

            block = (
                f"**{global_index:02d}. {member.display_name}**\n"
                f"　└ {member.mention}\n"
                f"　　└ {status}"
            )

            blocks.append(block)

        # ------------------------------------------------------
        # FIELD SPLITTER
        # Discord field value maksimal 1024 karakter.
        # Tetap maksimal 10 bot per halaman.
        # ------------------------------------------------------

        field_chunks = []
        current = []

        for block in blocks:
            candidate = "\n\n".join(current + [block])

            if current and len(candidate) > 1024:
                field_chunks.append(current)
                current = [block]
            else:
                current.append(block)

        if current:
            field_chunks.append(current)

        previous_count = 0

        for chunk in field_chunks:
            start_number = (
                ((page - 1) * self.BOTS_PER_EMBED)
                + previous_count
                + 1
            )

            end_number = start_number + len(chunk) - 1
            previous_count += len(chunk)

            if len(field_chunks) == 1:
                field_name = (
                    f"🤖 Daftar Bot  •  {len(blocks)} Bot"
                )
            else:
                field_name = (
                    f"🤖 Daftar Bot  •  "
                    f"{start_number:02d}-{end_number:02d}"
                )

            embed.add_field(
                name=field_name,
                value="\n\n".join(chunk),
                inline=False
            )

        # ------------------------------------------------------
        # FOOTER
        # ------------------------------------------------------

        embed.set_footer(
            text=(
                f"nanZ Server  •  Bot Directory  •  "
                f"Halaman {page}/{total_pages}"
            )
        )

        # Jangan menggunakan datetime.now() di embed.
        # Timestamp dinamis membuat cache selalu berbeda dan
        # menyebabkan PATCH berulang.

        return embed

    # ==========================================================
    # FIND OLD MESSAGES
    # ==========================================================

    async def find_existing_messages(self, channel):
        """Mencari panel Bot Directory yang sudah ada."""

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

                if "Bot Directory" not in author.name:
                    continue

                found.append(message.id)

        except discord.HTTPException as e:
            print(
                f"[BOT DIRECTORY] Gagal mencari message lama: {e}"
            )

        # History dari terbaru -> terlama.
        found.reverse()
        return found

    # ==========================================================
    # SCHEDULE REFRESH
    # ==========================================================

    def schedule_refresh(self, guild):
        """Menjadwalkan satu refresh setelah debounce."""

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
                f"[BOT DIRECTORY] Refresh task error: {e}"
            )

    # ==========================================================
    # REFRESH ALL PANELS
    # ==========================================================

    async def refresh_all_panels(self, guild):

        if self.refresh_lock.locked():
            return

        async with self.refresh_lock:
            channel = self.bot.get_channel(
                self.BOT_CHANNEL_ID
            )

            if not channel:
                return

            bots = self.get_bots(guild)

            # Pecah menjadi maksimal 10 bot per halaman.
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
                            f"[BOT DIRECTORY] Message halaman "
                            f"{page_number} sudah tidak ditemukan."
                        )

                        self.embed_cache.pop(
                            page_number,
                            None
                        )

                    except discord.HTTPException as e:
                        print(
                            f"[BOT DIRECTORY] Gagal edit halaman "
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
                        f"[BOT DIRECTORY] Gagal membuat halaman "
                        f"{page_number}: {e}"
                    )
                    continue

                new_message_ids.append(new_message.id)
                self.embed_cache[page_number] = embed_data

                print(
                    f"[BOT DIRECTORY] Panel halaman "
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

            # Bersihkan cache halaman yang sudah tidak ada.
            for page_number in list(self.embed_cache.keys()):
                if page_number > total_pages:
                    self.embed_cache.pop(page_number, None)

            self.message_ids = new_message_ids

    # ==========================================================
    # MEMBER / BOT EVENTS
    # ==========================================================

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            self.schedule_refresh(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.bot:
            self.schedule_refresh(member.guild)

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        if not after.bot:
            return

        if before.status == after.status:
            return

        self.schedule_refresh(after.guild)

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
        """
        Jalankan !setupbotdirectory di channel yang ingin
        digunakan sebagai Bot Directory.
        """

        self.BOT_CHANNEL_ID = ctx.channel.id

        # Reset agar setup membuat / menemukan panel kembali.
        self.message_ids.clear()
        self.embed_cache.clear()

        try:
            await ctx.message.delete()
        except Exception:
            pass

        await self.refresh_all_panels(ctx.guild)

        print(
            f"[BOT DIRECTORY] Directory berhasil dibuat di "
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
