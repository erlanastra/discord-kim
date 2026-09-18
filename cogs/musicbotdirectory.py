import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone
import json
import os
import asyncio


class StaffDirectory(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # ==========================================
        # CONFIG
        # ==========================================

        self.CHANNEL_ID = 1540754204161736915

        # Role staff
        self.STAFF_ROLES = [
            {
                "role_id": 1417582562100117584,
                "name": "Guru Besar",
                "emoji": "👑",
                "color": discord.Color.gold()
            },
            {
                "role_id": 1453103644244316343,
                "name": "Moderator",
                "emoji": "🛡️",
                "color": discord.Color.blue()
            },
            {
                "role_id": 1467360501745844446,
                "name": "Pembina OSIS",
                "emoji": "📚",
                "color": discord.Color.purple()
            },
            {
                "role_id": 1427276194876751902,
                "name": "OSIS",
                "emoji": "✍️",
                "color": discord.Color.green()
            }
        ]

        # ==========================================
        # MESSAGE ID
        # ==========================================

        self.message_ids = {
            role["role_id"]: None
            for role in self.STAFF_ROLES
        }

        # ==========================================
        # EMBED CACHE
        # ==========================================

        # Menyimpan isi embed terakhir.
        # Kalau tidak berubah, bot tidak akan PATCH message.
        self.embed_cache = {}

        # ==========================================
        # ACTIVITY DATABASE
        # ==========================================

        self.activity_file = "staff_activity.json"
        self.activity_data = self.load_activity()

        # ==========================================
        # REFRESH CONTROL
        # ==========================================

        # Mencegah dua refresh berjalan bersamaan.
        self.refresh_lock = asyncio.Lock()

        # Task debounce untuk presence / role update.
        self.refresh_task = None

        # Waktu debounce.
        self.REFRESH_DELAY = 5

        # ==========================================
        # START AUTO REFRESH
        # ==========================================

        self.update_directory.start()

    # ==========================================
    # LOAD ACTIVITY
    # ==========================================

    def load_activity(self):
        """Membaca database aktivitas staff."""

        if not os.path.exists(self.activity_file):
            return {}

        try:
            with open(
                self.activity_file,
                "r",
                encoding="utf-8"
            ) as f:

                return json.load(f)

        except Exception as e:

            print(
                f"[STAFF DIRECTORY] "
                f"Gagal membaca activity data: {e}"
            )

            return {}

    # ==========================================
    # SAVE ACTIVITY
    # ==========================================

    def save_activity(self):
        """Menyimpan database aktivitas staff."""

        try:

            with open(
                self.activity_file,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    self.activity_data,
                    f,
                    indent=4,
                    ensure_ascii=False
                )

        except Exception as e:

            print(
                f"[STAFF DIRECTORY] "
                f"Gagal menyimpan activity data: {e}"
            )

    # ==========================================
    # UPDATE LAST ACTIVE
    # ==========================================

    def update_activity(self, member_id):

        timestamp = int(
            datetime.now(
                timezone.utc
            ).timestamp()
        )

        old_timestamp = self.activity_data.get(
            str(member_id)
        )

        # Jangan tulis file kalau timestamp
        # sebenarnya tidak berubah.
        if old_timestamp == timestamp:
            return

        self.activity_data[str(member_id)] = timestamp

        self.save_activity()

    # ==========================================
    # GET STAFF STATUS
    # ==========================================

    def get_activity_status(self, member):

        timestamp = self.activity_data.get(
            str(member.id)
        )

        # ======================================
        # STAFF SEDANG AKTIF
        # ======================================

        if member.status != discord.Status.offline:

            # Kalau belum ada data sebelumnya,
            # simpan waktu sekarang.
            if not timestamp:

                timestamp = int(
                    datetime.now(
                        timezone.utc
                    ).timestamp()
                )

                self.activity_data[
                    str(member.id)
                ] = timestamp

                self.save_activity()

            return "🟢 **Aktif**"

        # ======================================
        # STAFF SUDAH OFFLINE
        # ======================================

        if timestamp:

            return (
                f"⚪ **Aktif <t:{timestamp}:R>**"
            )

        # ======================================
        # BELUM ADA DATA
        # ======================================

        return "⚪ **Belum terdeteksi**"

    # ==========================================
    # GENERATE ROLE EMBED
    # ==========================================

    async def generate_role_embed(
        self,
        guild,
        role_info
    ):

        role = guild.get_role(
            role_info["role_id"]
        )

        # ======================================
        # EMBED DASAR
        # ======================================

        embed = discord.Embed(
            color=role_info.get(
                "color",
                discord.Color.blue()
            )
        )

        # ======================================
        # ROLE TIDAK DITEMUKAN
        # ======================================

        if not role:

            embed.description = (
                "⚠️ **Role tidak ditemukan.**"
            )

            return embed

        # ======================================
        # URUTKAN MEMBER
        # ======================================

        members = sorted(
            role.members,
            key=lambda m: m.display_name.lower()
        )

        # ======================================
        # HEADER
        # ======================================

        embed.set_author(
            name=(
                f"{role_info['emoji']}  "
                f"{role_info['name']}"
            ),
            icon_url=(
                guild.icon.url
                if guild.icon
                else discord.Embed.Empty
            )
        )

        # ======================================
        # TIDAK ADA STAFF
        # ======================================

        if not members:

            embed.description = (
                "╰─ *Belum ada staff yang terdaftar.*"
            )

        # ======================================
        # ADA STAFF
        # ======================================

        else:

            staff_list = []

            for index, member in enumerate(members):

                status = self.get_activity_status(
                    member
                )

                # Nomor urut
                number = f"{index + 1:02d}"

                # ==================================
                # FORMAT STAFF
                # ==================================

                staff_info = (
                    f"**{number}. {member.display_name}**\n"
                    f"　└ {member.mention}\n"
                    f"　　└ {status}"
                )

                staff_list.append(
                    staff_info
                )

            # ==================================
            # GABUNGKAN STAFF
            # ==================================

            embed.description = (
                "\n\n".join(staff_list)
            )

        # ======================================
        # FOOTER
        # ======================================

        embed.set_footer(
            text=(
                f"nanZ Server  •  "
                f"{role_info['name']}  •  "
                f"{len(members)} Staff"
            )
        )

        return embed

    # ==========================================
    # FIND OLD STAFF MESSAGES
    # ==========================================

    async def find_existing_messages(self, channel):

        found = {}

        try:

            async for message in channel.history(
                limit=100
            ):

                if message.author != self.bot.user:
                    continue

                if not message.embeds:
                    continue

                author = message.embeds[0].author

                if not author or not author.name:
                    continue

                for role_info in self.STAFF_ROLES:

                    role_id = role_info["role_id"]

                    if role_id in self.message_ids:

                        if self.message_ids[role_id]:
                            continue

                    if role_info["name"] in author.name:

                        found[role_id] = message.id

                        break

        except discord.HTTPException as e:

            print(
                f"[STAFF DIRECTORY] "
                f"Gagal mencari message lama: {e}"
            )

        return found

    # ==========================================
    # SCHEDULE REFRESH
    # ==========================================

    def schedule_refresh(self, guild):

        # Kalau task sebelumnya masih berjalan,
        # tidak membuat task baru.
        if (
            self.refresh_task
            and not self.refresh_task.done()
        ):
            return

        self.refresh_task = asyncio.create_task(
            self._delayed_refresh(guild)
        )

    # ==========================================
    # DELAYED REFRESH
    # ==========================================

    async def _delayed_refresh(self, guild):

        try:

            # Tunggu beberapa detik supaya
            # event yang datang bersamaan digabung.
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
                f"[STAFF DIRECTORY] "
                f"Refresh task error: {e}"
            )

    # ==========================================
    # REFRESH ALL PANELS
    # ==========================================

    async def refresh_all_panels(self, guild):

        # ======================================
        # LOCK
        # ======================================

        if self.refresh_lock.locked():
            return

        async with self.refresh_lock:

            channel = self.bot.get_channel(
                self.CHANNEL_ID
            )

            if not channel:

                print(
                    "[STAFF DIRECTORY] "
                    "Channel tidak ditemukan."
                )

                return

            # ==================================
            # CARI MESSAGE LAMA SEKALI SAJA
            # ==================================

            missing_roles = [
                role_info
                for role_info in self.STAFF_ROLES
                if not self.message_ids.get(
                    role_info["role_id"]
                )
            ]

            if missing_roles:

                found_messages = (
                    await self.find_existing_messages(
                        channel
                    )
                )

                for role_id, message_id in found_messages.items():

                    self.message_ids[
                        role_id
                    ] = message_id

            # ==================================
            # UPDATE SETIAP PANEL
            # ==================================

            for role_info in self.STAFF_ROLES:

                role_id = role_info["role_id"]

                try:

                    embed = (
                        await self.generate_role_embed(
                            guild,
                            role_info
                        )
                    )

                    # ==================================
                    # UBAH EMBED MENJADI DATA
                    # ==================================

                    embed_data = embed.to_dict()

                    old_embed_data = (
                        self.embed_cache.get(
                            role_id
                        )
                    )

                    message_id = (
                        self.message_ids.get(
                            role_id
                        )
                    )

                    # ==================================
                    # MESSAGE SUDAH ADA
                    # ==================================

                    if message_id:

                        # Kalau embed sama persis,
                        # JANGAN kirim PATCH.
                        if (
                            old_embed_data
                            == embed_data
                        ):

                            continue

                        try:

                            # PartialMessage memungkinkan
                            # edit langsung tanpa fetch_message().
                            message = (
                                channel.get_partial_message(
                                    message_id
                                )
                            )

                            await message.edit(
                                embed=embed
                            )

                            self.embed_cache[
                                role_id
                            ] = embed_data

                            continue

                        except discord.NotFound:

                            print(
                                "[STAFF DIRECTORY] "
                                f"Message {role_info['name']} "
                                "sudah tidak ditemukan."
                            )

                            self.message_ids[
                                role_id
                            ] = None

                            self.embed_cache.pop(
                                role_id,
                                None
                            )

                        except discord.HTTPException as e:

                            print(
                                "[STAFF DIRECTORY] "
                                f"Gagal edit "
                                f"{role_info['name']}: {e}"
                            )

                            continue

                    # ==================================
                    # MESSAGE TIDAK ADA
                    # ==================================

                    new_message = await channel.send(
                        embed=embed
                    )

                    self.message_ids[
                        role_id
                    ] = new_message.id

                    self.embed_cache[
                        role_id
                    ] = embed_data

                    print(
                        "[STAFF DIRECTORY] "
                        f"Panel {role_info['name']} dibuat."
                    )

                except Exception as e:

                    print(
                        "[STAFF DIRECTORY] "
                        f"Error {role_info['name']}: {e}"
                    )

    # ==========================================
    # STAFF MENGIRIM PESAN
    # ==========================================

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        if not isinstance(
            message.author,
            discord.Member
        ):
            return

        member = message.author

        # Cek apakah member adalah staff
        is_staff = any(
            role.id in self.message_ids
            for role in member.roles
        )

        if not is_staff:
            return

        # Simpan aktivitas terakhir
        self.update_activity(
            member.id
        )

    # ==========================================
    # STAFF ONLINE / OFFLINE
    # ==========================================

    @commands.Cog.listener()
    async def on_presence_update(
        self,
        before,
        after
    ):

        # Cek apakah staff
        is_staff = any(
            role.id in self.message_ids
            for role in after.roles
        )

        if not is_staff:
            return

        # ======================================
        # OFFLINE → ONLINE
        # ======================================

        if (
            before.status == discord.Status.offline
            and after.status != discord.Status.offline
        ):

            # Simpan aktivitas terakhir
            self.update_activity(
                after.id
            )

            # Jangan langsung refresh.
            # Masukkan ke debounce.
            self.schedule_refresh(
                after.guild
            )

    # ==========================================
    # ROLE STAFF BERUBAH
    # ==========================================

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before,
        after
    ):

        # ======================================
        # TIDAK ADA PERUBAHAN ROLE
        # ======================================

        if before.roles == after.roles:
            return

        # ======================================
        # CEK APAKAH ROLE STAFF TERKAIT
        # ======================================

        staff_role_ids = {
            role["role_id"]
            for role in self.STAFF_ROLES
        }

        before_roles = {
            role.id
            for role in before.roles
        }

        after_roles = {
            role.id
            for role in after.roles
        }

        # Role yang berubah
        changed_roles = (
            before_roles ^ after_roles
        )

        # Kalau bukan role staff,
        # tidak perlu refresh directory.
        if not (
            changed_roles
            & staff_role_ids
        ):
            return

        # ======================================
        # REFRESH DENGAN DEBOUNCE
        # ======================================

        self.schedule_refresh(
            after.guild
        )

    # ==========================================
    # AUTO REFRESH
    # ==========================================

    @tasks.loop(minutes=10)
    async def update_directory(self):

        await self.bot.wait_until_ready()

        channel = self.bot.get_channel(
            self.CHANNEL_ID
        )

        if not channel:
            return

        await self.refresh_all_panels(
            channel.guild
        )

    # ==========================================
    # BEFORE AUTO REFRESH
    # ==========================================

    @update_directory.before_loop
    async def before_update_directory(self):

        await self.bot.wait_until_ready()

    # ==========================================
    # SETUP DIRECTORY
    # ==========================================

    @commands.command(
        name="setupdirectory"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def setup_directory(
        self,
        ctx
    ):

        self.CHANNEL_ID = ctx.channel.id

        try:

            await ctx.message.delete()

        except Exception:
            pass

        # Reset cache
        self.embed_cache.clear()

        # ======================================
        # BUAT PANEL BARU
        # ======================================

        for role_info in self.STAFF_ROLES:

            embed = (
                await self.generate_role_embed(
                    ctx.guild,
                    role_info
                )
            )

            message = await ctx.send(
                embed=embed
            )

            role_id = role_info["role_id"]

            self.message_ids[
                role_id
            ] = message.id

            self.embed_cache[
                role_id
            ] = embed.to_dict()

        print(
            "[STAFF DIRECTORY] "
            "Directory berhasil dibuat."
        )

    # ==========================================
    # UNLOAD
    # ==========================================

    def cog_unload(self):

        self.update_directory.cancel()

        if (
            self.refresh_task
            and not self.refresh_task.done()
        ):

            self.refresh_task.cancel()


# ==============================================
# MUSIC BOT DIRECTORY
# ==============================================

class MusicBotDirectory(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # ==========================================
        # CONFIG
        # ==========================================

        # Isi dengan ID channel khusus Music Bot Directory.
        # Bisa diubah otomatis menggunakan !setupmusicdirectory
        self.MUSIC_CHANNEL_ID = 0

        # Role yang menandakan member tersebut adalah Music Bot.
        self.MUSIC_ROLE_ID = 1473506596851159080

        # Maksimal bot per embed.
        self.BOTS_PER_EMBED = 10

        # Debounce refresh agar perubahan voice yang beruntun
        # tidak membuat terlalu banyak PATCH message.
        self.REFRESH_DELAY = 2

        # ==========================================
        # MESSAGE / CACHE
        # ==========================================

        # List message ID karena 1 halaman = 1 embed.
        self.message_ids = []

        # Cache isi embed agar tidak edit message kalau datanya sama.
        self.embed_cache = {}

        # Mencegah refresh bersamaan.
        self.refresh_lock = asyncio.Lock()

        # Task debounce.
        self.refresh_task = None

        # Auto refresh sebagai safety net.
        self.update_directory.start()

    # ==========================================
    # GET MUSIC BOTS
    # ==========================================

    def get_music_bots(self, guild):
        """Mengambil semua member yang memiliki role Music Bot."""

        role = guild.get_role(self.MUSIC_ROLE_ID)

        if not role:
            return []

        # Hanya member bot yang memiliki role tersebut.
        bots = [
            member
            for member in role.members
            if member.bot
        ]

        return sorted(
            bots,
            key=lambda member: member.display_name.lower()
        )

    # ==========================================
    # GET BOT VOICE STATUS
    # ==========================================

    def get_voice_status(self, member):
        """
        Menentukan apakah Music Bot sedang berada di voice channel.

        Catatan:
        Discord.py dapat mengetahui bot sedang CONNECTED ke voice,
        tetapi tidak otomatis mengetahui apakah bot sedang benar-benar
        memainkan lagu tanpa integrasi dengan music player/library.
        """

        if member.voice and member.voice.channel:
            channel = member.voice.channel

            return (
                f"🟢 **Dipakai**\n"
                f"　└ 🎧 {channel.mention}"
            )

        return "⚪ **Tidak dipakai**\n　└ Tidak berada di voice channel"

    # ==========================================
    # GENERATE EMBED
    # ==========================================

    def generate_music_embed(
        self,
        guild,
        bots,
        page,
        total_pages
    ):
        """Membuat 1 embed berisi maksimal BOTS_PER_EMBED Music Bot."""

        embed = discord.Embed(
            color=discord.Color.blurple()
        )

        # ======================================
        # HEADER
        # ======================================

        embed.set_author(
            name="🎵  Music Bot Directory",
            icon_url=(
                guild.icon.url
                if guild.icon
                else discord.Embed.Empty
            )
        )

        # ======================================
        # EMPTY
        # ======================================

        if not bots:
            embed.description = (
                "╰─ *Belum ada Music Bot yang memiliki role "
                "`Marching Band`.*"
            )

            embed.set_footer(
                text="nanZ Server  •  Music Bot  •  0 Bot"
            )

            return embed

        # ======================================
        # SUMMARY
        # ======================================

        active_count = sum(
            1
            for bot_member in bots
            if bot_member.voice
            and bot_member.voice.channel
        )

        inactive_count = len(bots) - active_count

        embed.description = (
            f"🎧 **Sedang digunakan:** `{active_count}` bot\n"
            f"⚪ **Tidak digunakan:** `{inactive_count}` bot\n"
            f"📋 **Total:** `{len(bots)}` bot"
        )

        # ======================================
        # BOT LIST
        # ======================================

        bot_blocks = []

        for index, member in enumerate(bots):
            global_index = (
                ((page - 1) * self.BOTS_PER_EMBED)
                + index
                + 1
            )

            status = self.get_voice_status(member)

            bot_info = (
                f"**{global_index:02d}. {member.display_name}**\n"
                f"　└ {member.mention}\n"
                f"　　└ {status}"
            )

            bot_blocks.append(bot_info)

        embed.add_field(
            name=f"🤖 Daftar Music Bot  •  {len(bot_blocks)} Bot",
            value="\n\n".join(bot_blocks),
            inline=False
        )

        # ======================================
        # FOOTER
        # ======================================

        timestamp = int(
            datetime.now(
                timezone.utc
            ).timestamp()
        )

        embed.set_footer(
            text=(
                f"nanZ Server  •  Music Bot  •  "
                f"Halaman {page}/{total_pages}  •  "
                f"Diperbarui"
            )
        )

        embed.timestamp = datetime.now(timezone.utc)

        return embed

    # ==========================================
    # FIND OLD MUSIC MESSAGES
    # ==========================================

    async def find_existing_messages(self, channel):
        """
        Mencari message Music Bot Directory yang sudah pernah dibuat.
        Message dikenali dari author/header embed.
        """

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
                "[MUSIC DIRECTORY] "
                f"Gagal mencari message lama: {e}"
            )

        # History berjalan terbaru -> terlama.
        # Balik supaya urutan halaman tetap stabil.
        found.reverse()

        return found

    # ==========================================
    # SCHEDULE REFRESH
    # ==========================================

    def schedule_refresh(self, guild):
        """Menjadwalkan refresh dengan debounce."""

        if (
            self.refresh_task
            and not self.refresh_task.done()
        ):
            return

        self.refresh_task = asyncio.create_task(
            self._delayed_refresh(guild)
        )

    # ==========================================
    # DELAYED REFRESH
    # ==========================================

    async def _delayed_refresh(self, guild):

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

    # ==========================================
    # REFRESH ALL PANELS
    # ==========================================

    async def refresh_all_panels(self, guild):

        if self.refresh_lock.locked():
            return

        async with self.refresh_lock:

            channel = self.bot.get_channel(
                self.MUSIC_CHANNEL_ID
            )

            if not channel:
                return

            # ==================================
            # GET MUSIC BOTS
            # ==================================

            bots = self.get_music_bots(guild)

            # 1 embed kalau kosong juga tetap dibuat.
            if bots:
                pages = [
                    bots[
                        start:start + self.BOTS_PER_EMBED
                    ]
                    for start in range(
                        0,
                        len(bots),
                        self.BOTS_PER_EMBED
                    )
                ]
            else:
                pages = [[]]

            total_pages = len(pages)

            # ==================================
            # CARI MESSAGE LAMA
            # ==================================

            if not self.message_ids:
                self.message_ids = (
                    await self.find_existing_messages(
                        channel
                    )
                )

            # ==================================
            # UPDATE / CREATE MESSAGE
            # ==================================

            new_message_ids = []

            for page_number, page_bots in enumerate(
                pages,
                start=1
            ):

                embed = self.generate_music_embed(
                    guild,
                    page_bots,
                    page_number,
                    total_pages
                )

                embed_data = embed.to_dict()

                old_embed_data = (
                    self.embed_cache.get(
                        page_number
                    )
                )

                # ==================================
                # MESSAGE SUDAH ADA
                # ==================================

                message_id = (
                    self.message_ids[page_number - 1]
                    if page_number - 1 < len(
                        self.message_ids
                    )
                    else None
                )

                if message_id:

                    # Tidak PATCH kalau embed tidak berubah.
                    if old_embed_data == embed_data:
                        new_message_ids.append(
                            message_id
                        )
                        continue

                    try:
                        message = (
                            channel.get_partial_message(
                                message_id
                            )
                        )

                        await message.edit(
                            embed=embed
                        )

                        self.embed_cache[
                            page_number
                        ] = embed_data

                        new_message_ids.append(
                            message_id
                        )

                        continue

                    except discord.NotFound:

                        print(
                            "[MUSIC DIRECTORY] "
                            f"Message halaman {page_number} "
                            "sudah tidak ditemukan."
                        )

                        self.embed_cache.pop(
                            page_number,
                            None
                        )

                    except discord.HTTPException as e:

                        print(
                            "[MUSIC DIRECTORY] "
                            f"Gagal edit halaman "
                            f"{page_number}: {e}"
                        )

                        continue

                # ==================================
                # MESSAGE TIDAK ADA
                # ==================================

                new_message = await channel.send(
                    embed=embed
                )

                new_message_ids.append(
                    new_message.id
                )

                self.embed_cache[
                    page_number
                ] = embed_data

                print(
                    "[MUSIC DIRECTORY] "
                    f"Panel halaman {page_number} dibuat."
                )

            # ==================================
            # HAPUS MESSAGE HALAMAN BERLEBIH
            # ==================================

            old_message_ids = self.message_ids[
                len(new_message_ids):
            ]

            for message_id in old_message_ids:

                try:
                    message = (
                        channel.get_partial_message(
                            message_id
                        )
                    )

                    await message.delete()

                except (
                    discord.NotFound,
                    discord.HTTPException
                ):
                    pass

            # Bersihkan cache halaman lama.
            for page_number in list(
                self.embed_cache.keys()
            ):
                if page_number > total_pages:
                    self.embed_cache.pop(
                        page_number,
                        None
                    )

            self.message_ids = new_message_ids

    # ==========================================
    # VOICE STATE UPDATE
    # ==========================================

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member,
        before,
        after
    ):
        """
        Dipanggil ketika member masuk / keluar / pindah voice.
        Hanya refresh kalau member adalah Music Bot.
        """

        if not member.bot:
            return

        if before.channel == after.channel:
            return

        if not any(
            role.id == self.MUSIC_ROLE_ID
            for role in member.roles
        ):
            return

        self.schedule_refresh(
            member.guild
        )

    # ==========================================
    # ROLE UPDATE
    # ==========================================

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before,
        after
    ):

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

        # Hanya refresh jika role Music Bot berubah.
        if before_has_role == after_has_role:
            return

        self.schedule_refresh(
            after.guild
        )

    # ==========================================
    # MEMBER JOIN / REMOVE
    # ==========================================

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

    # ==========================================
    # AUTO REFRESH
    # ==========================================

    @tasks.loop(minutes=10)
    async def update_directory(self):

        await self.bot.wait_until_ready()

        if not self.MUSIC_CHANNEL_ID:
            return

        channel = self.bot.get_channel(
            self.MUSIC_CHANNEL_ID
        )

        if not channel:
            return

        await self.refresh_all_panels(
            channel.guild
        )

    # ==========================================
    # BEFORE AUTO REFRESH
    # ==========================================

    @update_directory.before_loop
    async def before_update_directory(self):

        await self.bot.wait_until_ready()

    # ==========================================
    # SETUP MUSIC DIRECTORY
    # ==========================================

    @commands.command(
        name="setupmusicdirectory"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def setup_music_directory(
        self,
        ctx
    ):
        """
        Jalankan command ini di channel tempat
        Music Bot Directory ingin ditampilkan.
        """

        self.MUSIC_CHANNEL_ID = ctx.channel.id

        # Reset cache supaya panel dibuat ulang.
        self.message_ids.clear()
        self.embed_cache.clear()

        try:
            await ctx.message.delete()
        except Exception:
            pass

        await self.refresh_all_panels(
            ctx.guild
        )

        print(
            "[MUSIC DIRECTORY] "
            f"Directory berhasil dibuat di "
            f"#{ctx.channel.name}."
        )

    # ==========================================
    # UNLOAD
    # ==========================================

    def cog_unload(self):

        self.update_directory.cancel()

        if (
            self.refresh_task
            and not self.refresh_task.done()
        ):
            self.refresh_task.cancel()


# ==============================================
# SETUP
# ==============================================

async def setup(bot):

    await bot.add_cog(
        StaffDirectory(bot)
    )

    await bot.add_cog(
        MusicBotDirectory(bot)
    )