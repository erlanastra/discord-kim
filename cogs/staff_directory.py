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
        # CONFIG NANZ SERVER
        # ==========================================

        # Channel utama Staff Directory
        self.CHANNEL_ID = 1540754204161736915

        # ==========================================
        # ROLE NANZ SERVER
        # ==========================================

        # Role dasar / akses internal seluruh staff
        self.STAFF_NANZ_ROLE_ID = 1515023431815528468

        # Guru Besar / Owner
        self.OWNER_ROLE_ID = 1417582562100117584

        # Moderator Discord
        self.MOD_DC_ROLE_ID = 1555556260269527151

        # Pembina OSIS
        self.PEMBINA_OSIS_ROLE_ID = 1467360501745844446

        # OSIS
        self.OSIS_ROLE_ID = 1427276194876751902

        # Role Off Duty
        self.OFF_DUTY_ROLE_ID = 1532403343928987909

        # ==========================================
        # EMOJI KHAS NANZ
        # ==========================================

        # Semua emoji berikut adalah emoji animasi.
        # Emoji diambil berdasarkan ID langsung dari guild.

        self.ARROW_BLUE_ID = 1512787254312042496
        self.ARROW_PURPLE_ID = 1512787191234035803

        # ==========================================
        # HEADER
        # ==========================================

        self.HEADER_TITLE = "nanZ SERVER — STAFF DIRECTORY"

        self.HEADER_COLOR = discord.Color.from_rgb(
            139,
            92,
            246
        )

        # ==========================================
        # STATUS EMOJI
        # ==========================================

        self.ONLINE_EMOJI_ID = 1553033618845343786
        self.OFFLINE_EMOJI_ID = 1553033468265631796

        # ==========================================
        # STAFF ROLES
        # ==========================================

        self.STAFF_ROLES = [
            {
                "role_id": self.OWNER_ROLE_ID,
                "name": "GURU BESAR",
                "color": discord.Color.from_rgb(
                    255,
                    193,
                    7
                )
            },
            {
                "role_id": self.MOD_DC_ROLE_ID,
                "name": "MOD DC",
                "color": discord.Color.from_rgb(
                    88,
                    101,
                    242
                )
            },
            {
                "role_id": self.PEMBINA_OSIS_ROLE_ID,
                "name": "PEMBINA OSIS",
                "color": discord.Color.from_rgb(
                    46,
                    204,
                    113
                )
            },
            {
                "role_id": self.OSIS_ROLE_ID,
                "name": "OSIS",
                "color": discord.Color.from_rgb(
                    52,
                    152,
                    219
                )
            }
        ]

        # ==========================================
        # OFF DUTY
        # ==========================================

        self.OFF_DUTY_ROLE = {
            "role_id": self.OFF_DUTY_ROLE_ID,
            "name": "OFF DUTY",
            "color": discord.Color.from_rgb(
                149,
                165,
                166
            )
        }

        # ==========================================
        # MESSAGE ID
        # ==========================================

        self.header_message_id = None

        self.message_ids = {
            role["role_id"]: None
            for role in self.STAFF_ROLES
        }

        self.off_duty_message_id = None

        # ==========================================
        # EMBED CACHE
        # ==========================================

        # Menyimpan embed terakhir.
        # Jika tidak berubah, bot tidak melakukan PATCH.
        self.embed_cache = {}

        # ==========================================
        # ACTIVITY DATABASE
        # ==========================================

        self.activity_file = "staff_activity.json"

        self.activity_data = self.load_activity()

        # ==========================================
        # REFRESH CONTROL
        # ==========================================

        self.refresh_lock = asyncio.Lock()

        self.refresh_task = None

        # Debounce refresh
        self.REFRESH_DELAY = 5

        # ==========================================
        # START AUTO REFRESH
        # ==========================================

        self.update_directory.start()

    # ==========================================
    # GET NANZ EMOJI
    # ==========================================

    def get_nanz_emoji(
        self,
        guild,
        emoji_id,
        fallback
    ):
        """
        Mengambil emoji nanZ berdasarkan ID.

        str(emoji) akan mempertahankan format emoji
        animasi Discord seperti <a:nama:id>.
        """

        emoji = guild.get_emoji(
            emoji_id
        )

        if emoji:

            return str(emoji)

        return fallback

    # ==========================================
    # LOAD ACTIVITY
    # ==========================================

    def load_activity(self):

        if not os.path.exists(
            self.activity_file
        ):
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
                "[NANZ STAFF DIRECTORY] "
                f"Gagal membaca activity data: {e}"
            )

            return {}

    # ==========================================
    # SAVE ACTIVITY
    # ==========================================

    def save_activity(self):

        try:

            # Pastikan directory tempat file berada
            # tersedia.
            directory = os.path.dirname(
                os.path.abspath(
                    self.activity_file
                )
            )

            os.makedirs(
                directory,
                exist_ok=True
            )

            # Gunakan temporary file agar
            # penyimpanan lebih aman.
            temp_file = (
                self.activity_file
                + ".tmp"
            )

            with open(
                temp_file,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    self.activity_data,
                    f,
                    indent=4,
                    ensure_ascii=False
                )

                f.flush()

                try:
                    os.fsync(
                        f.fileno()
                    )
                except Exception:
                    pass

            os.replace(
                temp_file,
                self.activity_file
            )

        except Exception as e:

            print(
                "[NANZ STAFF DIRECTORY] "
                f"Gagal menyimpan activity data: {e}"
            )

            # Bersihkan file temporary jika gagal.
            try:

                if os.path.exists(
                    temp_file
                ):

                    os.remove(
                        temp_file
                    )

            except Exception:
                pass

    # ==========================================
    # UPDATE LAST ACTIVE
    # ==========================================

    def update_activity(
        self,
        member_id
    ):

        timestamp = int(
            datetime.now(
                timezone.utc
            ).timestamp()
        )

        old_timestamp = (
            self.activity_data.get(
                str(member_id)
            )
        )

        # Jangan menulis file jika timestamp
        # ternyata sama.
        if old_timestamp == timestamp:
            return

        self.activity_data[
            str(member_id)
        ] = timestamp

        self.save_activity()

    # ==========================================
    # CHECK OFF DUTY
    # ==========================================

    def is_off_duty(
        self,
        member
    ):

        return any(
            role.id
            == self.OFF_DUTY_ROLE_ID
            for role in member.roles
        )

    # ==========================================
    # CHECK JABATAN STAFF
    # ==========================================

    def has_staff_position(
        self,
        member
    ):

        staff_role_ids = {
            self.OWNER_ROLE_ID,
            self.MOD_DC_ROLE_ID,
            self.PEMBINA_OSIS_ROLE_ID,
            self.OSIS_ROLE_ID
        }

        return any(
            role.id in staff_role_ids
            for role in member.roles
        )

    # ==========================================
    # CHECK STAFF NANZ
    # ==========================================

    def has_staff_nanz_role(
        self,
        member
    ):

        return any(
            role.id
            == self.STAFF_NANZ_ROLE_ID
            for role in member.roles
        )

    # ==========================================
    # CHECK MEMBER STAFF
    # ==========================================

    def is_staff_member(
        self,
        member
    ):

        return (
            self.has_staff_position(
                member
            )
            or
            self.has_staff_nanz_role(
                member
            )
            or
            self.is_off_duty(
                member
            )
        )

    # ==========================================
    # GET STAFF STATUS
    # ==========================================

    def get_activity_status(
        self,
        member
    ):

        timestamp = (
            self.activity_data.get(
                str(member.id)
            )
        )

        # ======================================
        # STATUS EMOJI
        # ======================================

        online_emoji = (
            member.guild.get_emoji(
                self.ONLINE_EMOJI_ID
            )
        )

        offline_emoji = (
            member.guild.get_emoji(
                self.OFFLINE_EMOJI_ID
            )
        )

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
        # STAFF ONLINE
        # ======================================

        if (
            member.status
            != discord.Status.offline
        ):

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

            return (
                online_emoji,
                "Aktif sekarang"
            )

        # ======================================
        # STAFF OFFLINE
        # ======================================

        if timestamp:

            return (
                offline_emoji,
                f"Aktif <t:{timestamp}:R>"
            )

        # ======================================
        # BELUM TERDETEKSI
        # ======================================

        return (
            offline_emoji,
            "Belum terdeteksi"
        )

    # ==========================================
    # SORT STAFF
    # ==========================================

    def sort_key(
        self,
        member
    ):

        timestamp = (
            self.activity_data.get(
                str(member.id),
                0
            )
        )

        return (
            0
            if member.status
            != discord.Status.offline
            else 1,

            -timestamp,

            member.display_name.lower()
        )

    # ==========================================
    # GET ACTIVE STAFF
    # ==========================================

    def get_all_staff_members(
        self,
        guild
    ):

        unique_members = {}

        for role_info in self.STAFF_ROLES:

            role = guild.get_role(
                role_info["role_id"]
            )

            if not role:
                continue

            for member in role.members:

                # ==================================
                # OFF DUTY DIPISAH
                # ==================================

                if self.is_off_duty(
                    member
                ):
                    continue

                unique_members[
                    member.id
                ] = member

        return unique_members

    # ==========================================
    # GET OFF DUTY MEMBERS
    # ==========================================

    def get_off_duty_members(
        self,
        guild
    ):

        role = guild.get_role(
            self.OFF_DUTY_ROLE_ID
        )

        if not role:
            return []

        members = []

        for member in role.members:

            # Member harus punya salah satu
            # jabatan staff nanZ.
            if self.has_staff_position(
                member
            ):

                members.append(
                    member
                )

        return members

    # ==========================================
    # GENERATE HEADER EMBED
    # ==========================================

    async def generate_header_embed(
        self,
        guild
    ):

        # ======================================
        # EMOJI KHAS NANZ
        # ======================================

        arrow_blue = self.get_nanz_emoji(
            guild,
            self.ARROW_BLUE_ID,
            "🔵"
        )

        arrow_purple = self.get_nanz_emoji(
            guild,
            self.ARROW_PURPLE_ID,
            "🟣"
        )

        # ======================================
        # DATA STAFF
        # ======================================

        unique_members = (
            self.get_all_staff_members(
                guild
            )
        )

        off_duty_members = (
            self.get_off_duty_members(
                guild
            )
        )

        total = len(
            unique_members
        )

        active = sum(
            1
            for member
            in unique_members.values()
            if (
                member.status
                != discord.Status.offline
            )
        )

        offline = (
            total - active
        )

        # ======================================
        # EMBED
        # ======================================

        embed = discord.Embed(
            title=(
                f"{arrow_blue} "
                f"nanZ SERVER — STAFF DIRECTORY"
            ),
            description=(
                f"{arrow_purple} "
                "**Staff Directory nanZ Server**\n\n"
                "Panel ini menampilkan daftar staff "
                "berdasarkan jabatan dan status aktivitas.\n\n"
                f"{arrow_blue} Staff yang sedang aktif "
                "akan ditampilkan dengan status aktif.\n"
                f"{arrow_purple} Staff yang sedang offline "
                "tetap ditampilkan berdasarkan aktivitas "
                "terakhir.\n"
                f"🔕 Staff yang mengambil **Off Duty** "
                "dipisahkan ke panel Off Duty."
            ),
            color=self.HEADER_COLOR
        )

        # ======================================
        # TOTAL
        # ======================================

        embed.add_field(
            name="Total Staff",
            value=str(total),
            inline=True
        )

        # ======================================
        # AKTIF
        # ======================================

        embed.add_field(
            name="Aktif",
            value=str(active),
            inline=True
        )

        # ======================================
        # OFFLINE
        # ======================================

        embed.add_field(
            name="Offline",
            value=str(offline),
            inline=True
        )

        # ======================================
        # OFF DUTY
        # ======================================

        embed.add_field(
            name="Off Duty",
            value=str(
                len(off_duty_members)
            ),
            inline=True
        )

        embed.set_footer(
            text="nanZ Server • Staff Directory"
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

            embed.title = (
                role_info["name"]
            )

            embed.description = (
                "Role tidak ditemukan."
            )

            return embed

        # ======================================
        # MEMBER
        # ======================================

        # Staff Off Duty tidak muncul
        # pada panel jabatan masing-masing.
        members = [
            member
            for member in role.members
            if not self.is_off_duty(
                member
            )
        ]

        # ======================================
        # SORT
        # ======================================

        members = sorted(
            members,
            key=self.sort_key
        )

        # ======================================
        # TITLE
        # ======================================

        embed.title = (
            f"{role_info['name']} · "
            f"{len(members)} staff"
        )

        # ======================================
        # TIDAK ADA MEMBER
        # ======================================

        if not members:

            embed.description = (
                "Belum ada staff pada role ini."
            )

            return embed

        # ======================================
        # ENTRIES
        # ======================================

        entries = []

        for member in members:

            dot, status = (
                self.get_activity_status(
                    member
                )
            )

            name = (
                discord.utils.escape_markdown(
                    member.display_name
                )
            )

            entries.append(
                f"{dot} **{name}** "
                f"{member.mention}\n"
                f"-# {status}"
            )

        # ======================================
        # LIMIT DISCORD 4096
        # ======================================

        description = ""

        shown = 0

        for entry in entries:

            if (
                len(description)
                + len(entry)
                + 40
                > 4096
            ):

                break

            description += (
                entry
                + "\n"
            )

            shown += 1

        hidden = (
            len(entries)
            - shown
        )

        if hidden > 0:

            description += (
                f"\n… dan {hidden} "
                "staff lainnya"
            )

        embed.description = (
            description.strip()
        )

        return embed

    # ==========================================
    # GENERATE OFF DUTY EMBED
    # ==========================================

    async def generate_off_duty_embed(
        self,
        guild
    ):

        arrow_purple = self.get_nanz_emoji(
            guild,
            self.ARROW_PURPLE_ID,
            "🟣"
        )

        role = guild.get_role(
            self.OFF_DUTY_ROLE_ID
        )

        embed = discord.Embed(
            title=(
                f"{arrow_purple} OFF DUTY"
            ),
            color=self.OFF_DUTY_ROLE[
                "color"
            ]
        )

        # ======================================
        # ROLE TIDAK ADA
        # ======================================

        if not role:

            embed.description = (
                "Role Off Duty tidak ditemukan."
            )

            return embed

        # ======================================
        # MEMBER OFF DUTY
        # ======================================

        members = (
            self.get_off_duty_members(
                guild
            )
        )

        members = sorted(
            members,
            key=lambda member:
                member.display_name.lower()
        )

        # ======================================
        # TITLE
        # ======================================

        embed.title = (
            f"{arrow_purple} OFF DUTY · "
            f"{len(members)} staff"
        )

        # ======================================
        # TIDAK ADA STAFF
        # ======================================

        if not members:

            embed.description = (
                "Tidak ada staff yang sedang "
                "mengambil Off Duty."
            )

            embed.set_footer(
                text="nanZ Server • Off Duty"
            )

            return embed

        # ======================================
        # ENTRIES
        # ======================================

        entries = []

        for member in members:

            name = (
                discord.utils.escape_markdown(
                    member.display_name
                )
            )

            positions = []

            # ==================================
            # GURU BESAR
            # ==================================

            if any(
                role_check.id
                == self.OWNER_ROLE_ID
                for role_check
                in member.roles
            ):

                positions.append(
                    "Guru Besar"
                )

            # ==================================
            # MOD DC
            # ==================================

            if any(
                role_check.id
                == self.MOD_DC_ROLE_ID
                for role_check
                in member.roles
            ):

                positions.append(
                    "Mod DC"
                )

            # ==================================
            # PEMBINA OSIS
            # ==================================

            if any(
                role_check.id
                == self.PEMBINA_OSIS_ROLE_ID
                for role_check
                in member.roles
            ):

                positions.append(
                    "Pembina OSIS"
                )

            # ==================================
            # OSIS
            # ==================================

            if any(
                role_check.id
                == self.OSIS_ROLE_ID
                for role_check
                in member.roles
            ):

                positions.append(
                    "OSIS"
                )

            if positions:

                position_text = (
                    " • ".join(
                        positions
                    )
                )

            else:

                position_text = (
                    "Staff nanZ"
                )

            entries.append(
                f"🔕 **{name}** "
                f"{member.mention}\n"
                f"-# {position_text} • "
                "Sedang Off Duty"
            )

        # ======================================
        # DESCRIPTION LIMIT
        # ======================================

        description = ""

        shown = 0

        for entry in entries:

            if (
                len(description)
                + len(entry)
                + 40
                > 4096
            ):

                break

            description += (
                entry
                + "\n"
            )

            shown += 1

        hidden = (
            len(entries)
            - shown
        )

        if hidden > 0:

            description += (
                f"\n… dan {hidden} "
                "staff lainnya"
            )

        embed.description = (
            description.strip()
        )

        # ======================================
        # INFO
        # ======================================

        embed.add_field(
            name="Status Off Duty",
            value=(
                "Staff yang tercantum di panel ini "
                "sedang mengambil Off Duty.\n\n"
                "Selama Off Duty, role **Staff nanZ** "
                "dapat dicabut sehingga staff tidak "
                "memiliki akses ke internal server "
                "sesuai sistem role server."
            ),
            inline=False
        )

        embed.set_footer(
            text="nanZ Server • Off Duty"
        )

        return embed

    # ==========================================
    # BUILD PANEL
    # ==========================================

    async def build_panel(
        self,
        guild,
        key,
        role_info
    ):

        # ======================================
        # HEADER
        # ======================================

        if key == "header":

            return await (
                self.generate_header_embed(
                    guild
                )
            )

        # ======================================
        # OFF DUTY
        # ======================================

        if key == "off_duty":

            return await (
                self.generate_off_duty_embed(
                    guild
                )
            )

        # ======================================
        # STAFF ROLE
        # ======================================

        return await (
            self.generate_role_embed(
                guild,
                role_info
            )
        )

    # ==========================================
    # GET PANEL ID
    # ==========================================

    def get_panel_id(
        self,
        key
    ):

        if key == "header":

            return self.header_message_id

        if key == "off_duty":

            return self.off_duty_message_id

        return self.message_ids.get(
            key
        )

    # ==========================================
    # SET PANEL ID
    # ==========================================

    def set_panel_id(
        self,
        key,
        message_id
    ):

        if key == "header":

            self.header_message_id = (
                message_id
            )

        elif key == "off_duty":

            self.off_duty_message_id = (
                message_id
            )

        else:

            self.message_ids[key] = (
                message_id
            )

    # ==========================================
    # FIND EXISTING MESSAGES
    # ==========================================

    async def find_existing_messages(
        self,
        channel
    ):

        found = {}

        try:

            async for message in channel.history(
                limit=100
            ):

                # ==================================
                # HANYA MESSAGE BOT
                # ==================================

                if (
                    message.author
                    != self.bot.user
                ):

                    continue

                if not message.embeds:
                    continue

                title = (
                    message.embeds[0].title
                )

                if not title:
                    continue

                # ==================================
                # HEADER
                # ==================================

                if (
                    (
                        self.HEADER_TITLE
                        in title
                        or
                        "STAFF DIRECTORY"
                        in title
                    )
                    and
                    not self.header_message_id
                    and
                    "header"
                    not in found
                ):

                    found[
                        "header"
                    ] = message.id

                    continue

                # ==================================
                # OFF DUTY
                # ==================================

                if (
                    "OFF DUTY"
                    in title.upper()
                    and
                    "off_duty"
                    not in found
                    and
                    not self.off_duty_message_id
                ):

                    found[
                        "off_duty"
                    ] = message.id

                    continue

                # ==================================
                # STAFF ROLE PANEL
                # ==================================

                for role_info in (
                    self.STAFF_ROLES
                ):

                    role_id = (
                        role_info[
                            "role_id"
                        ]
                    )

                    if self.message_ids.get(
                        role_id
                    ):

                        continue

                    if role_id in found:

                        continue

                    name = (
                        role_info[
                            "name"
                        ]
                    )

                    if (
                        title == name
                        or
                        title.startswith(
                            f"{name} · "
                        )
                    ):

                        found[
                            role_id
                        ] = message.id

                        break

        except discord.HTTPException as e:

            print(
                "[NANZ STAFF DIRECTORY] "
                f"Gagal mencari message lama: {e}"
            )

        return found

    # ==========================================
    # SCHEDULE REFRESH
    # ==========================================

    def schedule_refresh(
        self,
        guild
    ):

        if (
            self.refresh_task
            and not self.refresh_task.done()
        ):

            return

        self.refresh_task = (
            asyncio.create_task(
                self._delayed_refresh(
                    guild
                )
            )
        )

    # ==========================================
    # DELAYED REFRESH
    # ==========================================

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
                "[NANZ STAFF DIRECTORY] "
                f"Refresh task error: {e}"
            )

    # ==========================================
    # REFRESH ALL PANELS
    # ==========================================

    async def refresh_all_panels(
        self,
        guild
    ):

        # ======================================
        # LOCK
        # ======================================

        if self.refresh_lock.locked():

            return

        async with self.refresh_lock:

            # ==================================
            # CHANNEL
            # ==================================

            channel = self.bot.get_channel(
                self.CHANNEL_ID
            )

            if not channel:

                print(
                    "[NANZ STAFF DIRECTORY] "
                    "Channel tidak ditemukan."
                )

                return

            # ==================================
            # FIND OLD MESSAGES
            # ==================================

            has_missing = (
                not self.header_message_id
                or not self.off_duty_message_id
                or any(
                    not self.message_ids.get(
                        role_info[
                            "role_id"
                        ]
                    )
                    for role_info
                    in self.STAFF_ROLES
                )
            )

            if has_missing:

                found_messages = (
                    await self.find_existing_messages(
                        channel
                    )
                )

                for (
                    key,
                    message_id
                ) in found_messages.items():

                    self.set_panel_id(
                        key,
                        message_id
                    )

            # ==================================
            # PANEL ORDER
            # ==================================

            panels = [
                (
                    "header",
                    None
                )
            ]

            # Guru Besar
            # Mod DC
            # Pembina OSIS
            # OSIS
            panels.extend(
                [
                    (
                        role_info[
                            "role_id"
                        ],
                        role_info
                    )
                    for role_info
                    in self.STAFF_ROLES
                ]
            )

            # Off Duty paling bawah
            panels.append(
                (
                    "off_duty",
                    self.OFF_DUTY_ROLE
                )
            )

            # ==================================
            # UPDATE PANEL
            # ==================================

            for (
                key,
                role_info
            ) in panels:

                label = (
                    "Judul"
                    if key == "header"
                    else
                    "Off Duty"
                    if key == "off_duty"
                    else
                    role_info["name"]
                )

                try:

                    embed = await self.build_panel(
                        guild,
                        key,
                        role_info
                    )

                    # ==================================
                    # EMBED DATA
                    # ==================================

                    embed_data = (
                        embed.to_dict()
                    )

                    old_embed_data = (
                        self.embed_cache.get(
                            key
                        )
                    )

                    message_id = (
                        self.get_panel_id(
                            key
                        )
                    )

                    # ==================================
                    # MESSAGE SUDAH ADA
                    # ==================================

                    if message_id:

                        # Tidak berubah,
                        # jangan PATCH Discord.
                        if (
                            old_embed_data
                            == embed_data
                        ):

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
                                key
                            ] = embed_data

                            continue

                        except discord.NotFound:

                            print(
                                "[NANZ STAFF DIRECTORY] "
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
                                "[NANZ STAFF DIRECTORY] "
                                f"Gagal edit "
                                f"{label}: {e}"
                            )

                            continue

                    # ==================================
                    # MESSAGE BELUM ADA
                    # ==================================

                    new_message = (
                        await channel.send(
                            embed=embed
                        )
                    )

                    self.set_panel_id(
                        key,
                        new_message.id
                    )

                    self.embed_cache[
                        key
                    ] = embed_data

                    print(
                        "[NANZ STAFF DIRECTORY] "
                        f"Panel {label} dibuat."
                    )

                except Exception as e:

                    print(
                        "[NANZ STAFF DIRECTORY] "
                        f"Error {label}: {e}"
                    )

    # ==========================================
    # STAFF MENGIRIM PESAN
    # ==========================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message
    ):

        # Jangan proses bot
        if message.author.bot:

            return

        # Pastikan Member
        if not isinstance(
            message.author,
            discord.Member
        ):

            return

        member = message.author

        # ======================================
        # STAFF
        # ======================================

        if not self.is_staff_member(
            member
        ):

            return

        # ======================================
        # UPDATE ACTIVITY
        # ======================================

        self.update_activity(
            member.id
        )

    # ==========================================
    # PRESENCE UPDATE
    # ==========================================

    @commands.Cog.listener()
    async def on_presence_update(
        self,
        before,
        after
    ):

        # ======================================
        # STAFF
        # ======================================

        if not self.is_staff_member(
            after
        ):

            return

        # ======================================
        # OFFLINE → ONLINE
        # ======================================

        if (
            before.status
            == discord.Status.offline
            and
            after.status
            != discord.Status.offline
        ):

            self.update_activity(
                after.id
            )

            self.schedule_refresh(
                after.guild
            )

    # ==========================================
    # MEMBER UPDATE
    # ==========================================

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before,
        after
    ):

        # ======================================
        # ROLE TIDAK BERUBAH
        # ======================================

        if before.roles == after.roles:

            return

        # ======================================
        # ROLE YANG DIPANTAU
        # ======================================

        staff_role_ids = {
            self.OWNER_ROLE_ID,
            self.MOD_DC_ROLE_ID,
            self.PEMBINA_OSIS_ROLE_ID,
            self.OSIS_ROLE_ID,
            self.STAFF_NANZ_ROLE_ID,
            self.OFF_DUTY_ROLE_ID
        }

        before_roles = {
            role.id
            for role in before.roles
        }

        after_roles = {
            role.id
            for role in after.roles
        }

        changed_roles = (
            before_roles
            ^ after_roles
        )

        # ======================================
        # BUKAN ROLE STAFF
        # ======================================

        if not (
            changed_roles
            & staff_role_ids
        ):

            return

        # ======================================
        # REFRESH
        # ======================================

        self.schedule_refresh(
            after.guild
        )

    # ==========================================
    # AUTO REFRESH 10 MENIT
    # ==========================================

    @tasks.loop(
        minutes=10
    )
    async def update_directory(
        self
    ):

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
    async def before_update_directory(
        self
    ):

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

        # ======================================
        # CHANNEL TETAP NANZ
        # ======================================

        self.CHANNEL_ID = (
            1540754204161736915
        )

        # ======================================
        # HAPUS COMMAND
        # ======================================

        try:

            await ctx.message.delete()

        except Exception:

            pass

        # ======================================
        # RESET CACHE
        # ======================================

        self.embed_cache.clear()

        # ======================================
        # RESET MESSAGE IDS
        # ======================================

        self.header_message_id = None

        self.off_duty_message_id = None

        self.message_ids = {
            role["role_id"]: None
            for role in self.STAFF_ROLES
        }

        # ======================================
        # AMBIL CHANNEL
        # ======================================

        channel = self.bot.get_channel(
            self.CHANNEL_ID
        )

        if not channel:

            await ctx.send(
                "❌ Channel Staff Directory "
                "nanZ tidak ditemukan.",
                delete_after=10
            )

            return

        # ======================================
        # PANEL ORDER
        # ======================================

        panels = [
            (
                "header",
                None
            )
        ]

        panels.extend(
            [
                (
                    role_info["role_id"],
                    role_info
                )
                for role_info
                in self.STAFF_ROLES
            ]
        )

        panels.append(
            (
                "off_duty",
                self.OFF_DUTY_ROLE
            )
        )

        # ======================================
        # BUAT PANEL
        # ======================================

        for (
            key,
            role_info
        ) in panels:

            embed = await self.build_panel(
                channel.guild,
                key,
                role_info
            )

            message = await channel.send(
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
            "[NANZ STAFF DIRECTORY] "
            "Directory berhasil dibuat."
        )

    # ==========================================
    # UNLOAD
    # ==========================================

    def cog_unload(
        self
    ):

        self.update_directory.cancel()

        if (
            self.refresh_task
            and not self.refresh_task.done()
        ):

            self.refresh_task.cancel()


# ==============================================
# SETUP
# ==============================================

async def setup(
    bot
):

    await bot.add_cog(
        StaffDirectory(bot)
    )