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

        self.CHANNEL_ID = 1553032690465251410

        # Emoji animasi server (judul panel pertama)
        self.ARROW_BLUE = "<a:arrowblue:1555096801629970523>"

        # Judul panel pertama
        self.HEADER_TITLE = "STAFF DIRECTORY"
        self.HEADER_COLOR = discord.Color.from_rgb(139, 92, 246)

        # Emoji status server
        self.ONLINE_EMOJI_ID = 1553033618845343786
        self.OFFLINE_EMOJI_ID = 1553033468265631796

        # Role staff
        self.STAFF_ROLES = [
            {
                "role_id": 1496838207822889050,
                "name": "Own",
                "color": discord.Color.from_rgb(155, 89, 182)
            },
            {
                "role_id": 1496846251914956820,
                "name": "Guardian",
                "color": discord.Color.from_rgb(126, 87, 194)
            },
            {
                "role_id": 1542886846508437515,
                "name": "Event Organizer",
                "color": discord.Color.from_rgb(171, 112, 214)
            },
            {
                "role_id": 1542887345873756272,
                "name": "Creative Studio",
                "color": discord.Color.from_rgb(186, 104, 200)
            },
            {
                "role_id": 1542887778658951208,
                "name": "Community Relations",
                "color": discord.Color.from_rgb(139, 92, 246)
            }
        ]

        # ==========================================
        # MESSAGE ID
        # ==========================================

        self.header_message_id = None

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
        """Mengembalikan (emoji status, teks status)."""

        timestamp = self.activity_data.get(
            str(member.id)
        )

        # ======================================
        # AMBIL EMOJI DARI SERVER BERDASARKAN ID
        # ======================================

        online_emoji = member.guild.get_emoji(
            self.ONLINE_EMOJI_ID
        )

        offline_emoji = member.guild.get_emoji(
            self.OFFLINE_EMOJI_ID
        )

        # Fallback jika emoji tidak ditemukan
        online_emoji = (
            str(online_emoji)
            if online_emoji
            else "🟢"
        )

        offline_emoji = (
            str(offline_emoji)
            if offline_emoji
            else "⚪"
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

            return online_emoji, "Aktif sekarang"

        # ======================================
        # STAFF SUDAH OFFLINE
        # ======================================

        if timestamp:

            return offline_emoji, f"Aktif <t:{timestamp}:R>"

        # ======================================
        # BELUM ADA DATA
        # ======================================

        return offline_emoji, "Belum terdeteksi"

    # ==========================================
    # SORT STAFF
    # ==========================================

    def sort_key(self, member):
        """Aktif dulu, lalu offline dari yang terakhir aktif terbaru."""

        timestamp = self.activity_data.get(
            str(member.id),
            0
        )

        return (
            0 if member.status != discord.Status.offline else 1,
            -timestamp,
            member.display_name.lower()
        )

    # ==========================================
    # GENERATE HEADER EMBED
    # ==========================================

    async def generate_header_embed(self, guild):

        # Staff unik (satu orang bisa punya lebih dari satu role)
        unique_members = {}

        for role_info in self.STAFF_ROLES:

            role = guild.get_role(
                role_info["role_id"]
            )

            if not role:
                continue

            for member in role.members:
                unique_members[member.id] = member

        total = len(unique_members)

        active = sum(
            1
            for member in unique_members.values()
            if member.status != discord.Status.offline
        )

        embed = discord.Embed(
            title=f"{self.ARROW_BLUE} {self.HEADER_TITLE}",
            description=(
                "Daftar staff Astralan dan status aktivitasnya."
            ),
            color=self.HEADER_COLOR
        )

        embed.add_field(
            name="Total staff",
            value=str(total),
            inline=True
        )

        embed.add_field(
            name="Aktif",
            value=str(active),
            inline=True
        )

        embed.add_field(
            name="Offline",
            value=str(total - active),
            inline=True
        )

        return embed

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

            embed.title = role_info["name"]

            embed.description = (
                "Role tidak ditemukan."
            )

            return embed

        # ======================================
        # URUTKAN MEMBER
        # ======================================

        members = sorted(
            role.members,
            key=self.sort_key
        )

        # ======================================
        # JUDUL
        # ======================================

        embed.title = (
            f"{role_info['name']} · {len(members)} staff"
        )

        # ======================================
        # TIDAK ADA STAFF
        # ======================================

        if not members:

            embed.description = (
                "Belum ada staff di role ini."
            )

            return embed

        # ======================================
        # ADA STAFF
        # ======================================

        entries = []

        for member in members:

            dot, status = self.get_activity_status(
                member
            )

            name = discord.utils.escape_markdown(
                member.display_name
            )

            entries.append(
                f"{dot} **{name}** {member.mention}\n"
                f"-# {status}"
            )

        # Batas deskripsi embed = 4096 karakter
        description = ""
        shown = 0

        for entry in entries:

            if len(description) + len(entry) + 40 > 4096:
                break

            description += entry + "\n"
            shown += 1

        hidden = len(entries) - shown

        if hidden > 0:
            description += f"\n… dan {hidden} staff lainnya"

        embed.description = description.strip()

        return embed

    # ==========================================
    # BUILD PANEL
    # ==========================================

    async def build_panel(self, guild, key, role_info):

        if key == "header":
            return await self.generate_header_embed(guild)

        return await self.generate_role_embed(
            guild,
            role_info
        )

    # ==========================================
    # PANEL ID HELPER
    # ==========================================

    def get_panel_id(self, key):

        if key == "header":
            return self.header_message_id

        return self.message_ids.get(key)

    def set_panel_id(self, key, message_id):

        if key == "header":
            self.header_message_id = message_id

        else:
            self.message_ids[key] = message_id

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

                title = message.embeds[0].title

                if not title:
                    continue

                # Panel pertama
                if (
                    self.HEADER_TITLE in title
                    and not self.header_message_id
                    and "header" not in found
                ):

                    found["header"] = message.id

                    continue

                # Panel role
                for role_info in self.STAFF_ROLES:

                    role_id = role_info["role_id"]

                    if self.message_ids.get(role_id):
                        continue

                    if role_id in found:
                        continue

                    name = role_info["name"]

                    if (
                        title == name
                        or title.startswith(f"{name} · ")
                    ):

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

            has_missing = (
                not self.header_message_id
                or any(
                    not self.message_ids.get(
                        role_info["role_id"]
                    )
                    for role_info in self.STAFF_ROLES
                )
            )

            if has_missing:

                found_messages = (
                    await self.find_existing_messages(
                        channel
                    )
                )

                for key, message_id in found_messages.items():

                    self.set_panel_id(
                        key,
                        message_id
                    )

            # ==================================
            # UPDATE SETIAP PANEL
            # ==================================

            panels = [("header", None)] + [
                (role_info["role_id"], role_info)
                for role_info in self.STAFF_ROLES
            ]

            for key, role_info in panels:

                label = (
                    "Header"
                    if key == "header"
                    else role_info["name"]
                )

                try:

                    embed = await self.build_panel(
                        guild,
                        key,
                        role_info
                    )

                    # ==================================
                    # UBAH EMBED MENJADI DATA
                    # ==================================

                    embed_data = embed.to_dict()

                    old_embed_data = (
                        self.embed_cache.get(
                            key
                        )
                    )

                    message_id = self.get_panel_id(
                        key
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
                                key
                            ] = embed_data

                            continue

                        except discord.NotFound:

                            print(
                                "[STAFF DIRECTORY] "
                                f"Message {label} "
                                "sudah tidak ditemukan."
                            )

                            self.set_panel_id(
                                key,
                                None
                            )

                            self.embed_cache.pop(
                                key,
                                None
                            )

                        except discord.HTTPException as e:

                            print(
                                "[STAFF DIRECTORY] "
                                f"Gagal edit "
                                f"{label}: {e}"
                            )

                            continue

                    # ==================================
                    # MESSAGE TIDAK ADA
                    # ==================================

                    new_message = await channel.send(
                        embed=embed
                    )

                    self.set_panel_id(
                        key,
                        new_message.id
                    )

                    self.embed_cache[
                        key
                    ] = embed_data

                    print(
                        "[STAFF DIRECTORY] "
                        f"Panel {label} dibuat."
                    )

                except Exception as e:

                    print(
                        "[STAFF DIRECTORY] "
                        f"Error {label}: {e}"
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

        panels = [("header", None)] + [
            (role_info["role_id"], role_info)
            for role_info in self.STAFF_ROLES
        ]

        for key, role_info in panels:

            embed = await self.build_panel(
                ctx.guild,
                key,
                role_info
            )

            message = await ctx.send(
                embed=embed
            )

            self.set_panel_id(
                key,
                message.id
            )

            self.embed_cache[
                key
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