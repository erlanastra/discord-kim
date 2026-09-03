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
                "emoji": "👑"
            },
            {
                "role_id": 1453103644244316343,
                "name": "Moderator",
                "emoji": "🛡️"
            },
            {
                "role_id": 1467360501745844446,
                "name": "Pembina OSIS",
                "emoji": "📚"
            },
            {
                "role_id": 1427276194876751902,
                "name": "OSIS",
                "emoji": "✍️"
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

        embed = discord.Embed(
            color=discord.Color.blue()
        )

        # ======================================
        # ROLE TIDAK DITEMUKAN
        # ======================================

        if not role:

            embed.description = (
                "⚠️ Role tidak ditemukan."
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
        # TIDAK ADA STAFF
        # ======================================

        if not members:

            embed.description = (
                "*Belum ada staff terdaftar.*"
            )

        # ======================================
        # ADA STAFF
        # ======================================

        else:

            staff_list = []

            for member in members:

                status = self.get_activity_status(
                    member
                )

                # Mention staff
                staff_info = (
                    f"👤 {member.mention}\n"
                    f"   └ {status}"
                )

                staff_list.append(
                    staff_info
                )

            embed.description = (
                "\n\n".join(staff_list)
            )

        # ======================================
        # HEADER
        # ======================================

        embed.set_author(
            name=(
                f"{role_info['emoji']} "
                f"{role_info['name']}"
            ),
            icon_url=(
                guild.icon.url
                if guild.icon
                else discord.Embed.Empty
            )
        )

        # ======================================
        # FOOTER
        # ======================================

        embed.set_footer(
            text=(
                f"nanZ Server • "
                f"{role_info['name']} • "
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
# SETUP
# ==============================================

async def setup(bot):

    await bot.add_cog(
        StaffDirectory(bot)
    )