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
        # Akan diisi otomatis oleh !setupbotdirectory
        self.BOT_CHANNEL_ID = 1550475918454030386

        # Role yang digunakan untuk menandai Music Bot.
        # Hanya BOT yang mempunyai role ini yang akan ditampilkan.
        self.MUSIC_ROLE_ID = 1473506596851159080

        # ======================================================
        # CUSTOM EMOJI
        # ======================================================
        # Masukkan ID custom emoji server di bawah ini.
        # Contoh:
        # self.ONLINE_EMOJI_ID = 123456789012345678
        # self.OFFLINE_EMOJI_ID = 987654321098765432
        #
        # Jika ID belum diisi / emoji tidak ditemukan, bot akan
        # memakai emoji fallback biasa.
        self.ONLINE_EMOJI_ID = 1550516004096974888
        self.OFFLINE_EMOJI_ID = 1550516157113434255

        # Semua Music Bot ditampilkan dalam SATU panel/message.
        # Tidak ada pagination.

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

    def get_custom_emoji(self, emoji_id, fallback):
        """Mengambil custom emoji server berdasarkan ID."""
        if not emoji_id:
            return fallback

        emoji = self.bot.get_emoji(emoji_id)

        if emoji:
            return str(emoji)

        return fallback

    def get_online_offline_emoji(self, member):
        """Mengambil emoji berdasarkan apakah Music Bot sedang terpakai."""

        # Konsep Online/Offline khusus panel Music Bot:
        # Online  = sedang berada di voice channel / sedang terpakai
        # Offline = tidak berada di voice channel / tidak terpakai
        if member.voice and member.voice.channel:
            return self.get_custom_emoji(
                self.ONLINE_EMOJI_ID,
                "🟢"
            )

        return self.get_custom_emoji(
            self.OFFLINE_EMOJI_ID,
            "⚫"
        )

    def get_voice_status(self, member):
        """Menampilkan Terpakai / Tidak Terpakai berdasarkan voice channel."""

        status_emoji = self.get_online_offline_emoji(member)

        if member.voice and member.voice.channel:
            channel = member.voice.channel

            return (
                f"{status_emoji} **Terpakai**  •  "
                f"🎧 {channel.mention}"
            )

        return (
            f"{status_emoji} **Tidak Terpakai**  •  "
            "Tidak sedang digunakan"
        )

    # ==========================================================
    # GENERATE EMBED
    # ==========================================================

    def generate_bot_embed(self, guild, bots):
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

        # Online/Offline di panel ini berarti TERPAKAI/TIDAK TERPAKAI
        # di voice channel, bukan status Discord bot.
        used_count = sum(
            1
            for member in bots
            if member.voice and member.voice.channel
        )

        unused_count = len(bots) - used_count

        online_emoji = self.get_custom_emoji(
            self.ONLINE_EMOJI_ID,
            "🟢"
        )

        offline_emoji = self.get_custom_emoji(
            self.OFFLINE_EMOJI_ID,
            "⚫"
        )

        embed.description = (
            f"{online_emoji} **Terpakai:** `{used_count}`  •  "
            f"{offline_emoji} **Tidak Terpakai:** `{unused_count}`  •  "
            f"📋 **Total:** `{len(bots)}`"
        )

        # ------------------------------------------------------
        # BOT LIST
        # ------------------------------------------------------
        # Dibuat RAPAT: tidak ada baris kosong antar bot.
        # Setiap bot hanya 3 baris.
        # ------------------------------------------------------

        blocks = []

        for index, member in enumerate(bots, start=1):
            global_index = index

            status = self.get_voice_status(member)

            block = (
                f"**{global_index:02d}. {member.display_name}** "
                f"• {member.mention} • {status}"
            )

            blocks.append(block)

        # ------------------------------------------------------
        # SATU FIELD SAJA
        # ------------------------------------------------------
        # Semua bot dimasukkan ke satu field agar output hanya
        # menjadi satu halaman/message. Jarak dibuat rapat.
        # ------------------------------------------------------

        value = "\n".join(blocks)

        # Semua bot dibuat serapat mungkin dan diletakkan dalam
        # description sehingga hanya ada SATU embed/message.
        # Jika jumlah bot sangat banyak hingga melewati limit
        # description, Discord tetap tidak memungkinkan satu embed
        # memuat semuanya; lihat catatan setelah kode.
        embed.description = embed.description + "\n\n" + value

        embed.set_footer(
            text=(
                "nanZ Server  •  Music Bot  •  "
                f"{len(bots)} Bot"
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
            # SATU PANEL / SATU MESSAGE
            # --------------------------------------------------

            embed = self.generate_bot_embed(guild, bots)

            embed_data = embed.to_dict()

            # Ambil panel lama yang ditemukan.
            if not self.message_ids:
                self.message_ids = (
                    await self.find_existing_messages(channel)
                )

            message_id = (
                self.message_ids[0]
                if self.message_ids
                else None
            )

            new_message_ids = []

            # --------------------------------------------------
            # UPDATE PANEL LAMA
            # --------------------------------------------------

            if message_id:
                old_embed_data = self.embed_cache.get("single")

                if old_embed_data == embed_data:
                    new_message_ids.append(message_id)

                else:
                    try:
                        message = channel.get_partial_message(
                            message_id
                        )

                        await message.edit(embed=embed)

                        self.embed_cache["single"] = embed_data
                        new_message_ids.append(message_id)

                    except discord.NotFound:
                        print(
                            "[MUSIC DIRECTORY] Panel lama tidak ditemukan."
                        )

                    except discord.HTTPException as e:
                        print(
                            f"[MUSIC DIRECTORY] Gagal edit panel: {e}"
                        )

            # --------------------------------------------------
            # BUAT PANEL JIKA BELUM ADA
            # --------------------------------------------------

            if not new_message_ids:
                try:
                    new_message = await channel.send(embed=embed)

                    new_message_ids.append(new_message.id)
                    self.embed_cache["single"] = embed_data

                    print(
                        "[MUSIC DIRECTORY] Satu panel berhasil dibuat."
                    )

                except discord.HTTPException as e:
                    print(
                        f"[MUSIC DIRECTORY] Gagal membuat panel: {e}"
                    )

            # --------------------------------------------------
            # HAPUS PANEL DUPLIKAT / PANEL LAMA BERLEBIH
            # --------------------------------------------------

            old_message_ids = self.message_ids[1:]

            # Kalau message pertama ternyata sudah tidak valid,
            # jangan hapus ID yang sedang dipakai.
            if (
                self.message_ids
                and new_message_ids
                and self.message_ids[0] == new_message_ids[0]
            ):
                old_message_ids = self.message_ids[1:]

            for old_id in old_message_ids:
                try:
                    message = channel.get_partial_message(old_id)
                    await message.delete()

                except (
                    discord.NotFound,
                    discord.HTTPException
                ):
                    pass

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
    # Tidak digunakan.
    # Status panel hanya mengikuti voice channel:
    # Terpakai = bot ada di voice
    # Tidak Terpakai = bot tidak ada di voice

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
