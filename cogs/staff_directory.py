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

        # Arrow Blue
        self.ARROW_BLUE_ID = 1512787254312042496

        # Arrow Purple
        self.ARROW_PURPLE_ID = 1512787191234035803

        # ==========================================
        # HEADER
        # ==========================================

        self.HEADER_TITLE = (
            "nanZ SERVER — STAFF DIRECTORY"
        )

        self.HEADER_COLOR = discord.Color.from_rgb(
            139,
            92,
            246
        )

        # ==========================================
        # STATUS EMOJI
        # ==========================================

        # ONLINE
        self.ONLINE_EMOJI_ID = 1550516004096974888

        # OFFLINE
        self.OFFLINE_EMOJI_ID = 1550516157113434255

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

        self.activity_file = (
            "staff_activity.json"
        )

        self.activity_data = (
            self.load_activity()
        )

        # ==========================================
        # REFRESH CONTROL
        # ==========================================

        # Mencegah refresh berjalan bersamaan.
        self.refresh_lock = asyncio.Lock()

        # Task debounce.
        self.refresh_task = None

        # Delay refresh agar perubahan status
        # tidak langsung melakukan PATCH berkali-kali.
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
        Mengambil emoji custom berdasarkan ID.
        str(emoji) mempertahankan emoji animasi.
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

                data = json.load(f)

                if isinstance(
                    data,
                    dict
                ):
                    return data

                return {}

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

        temp_file = (
            self.activity_file
            + ".tmp"
        )

        try:

            directory = os.path.dirname(
                os.path.abspath(
                    self.activity_file
                )
            )

            os.makedirs(
                directory,
                exist_ok=True
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

        member_key = str(
            member_id
        )

        old_timestamp = (
            self.activity_data.get(
                member_key
            )
        )

        # Jangan save jika timestamp sama.
        if old_timestamp == timestamp:
            return

        self.activity_data[
            member_key
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
            role.id == self.OFF_DUTY_ROLE_ID
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
    # CHECK STAFF NANZ ROLE
    # ==========================================

    def has_staff_nanz_role(
        self,
        member
    ):

        return any(
            role.id == self.STAFF_NANZ_ROLE_ID
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
    # GET STATUS EMOJI
    # ==========================================

    def get_status_emoji(
        self,
        member
    ):

        online_emoji = (
            self.get_nanz_emoji(
                member.guild,
                self.ONLINE_EMOJI_ID,
                "🟢"
            )
        )

        offline_emoji = (
            self.get_nanz_emoji(
                member.guild,
                self.OFFLINE_EMOJI_ID,
                "🔴"
            )
        )

        if (
            member.status
            != discord.Status.offline
        ):

            return online_emoji

        return offline_emoji

    # ==========================================
    # GET ACTIVITY TEXT
    # ==========================================

    def get_activity_text(
        self,
        member
    ):

        # ======================================
        # ONLINE
        # ======================================

        if (
            member.status
            != discord.Status.offline
        ):

            return "Aktif: sekarang"

        # ======================================
        # OFFLINE
        # ======================================

        timestamp = (
            self.activity_data.get(
                str(member.id)
            )
        )

        if timestamp:

            return (
                f"Terakhir aktif: "
                f"<t:{timestamp}:R>"
            )

        return (
            "Terakhir aktif: "
            "belum terdeteksi"
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

        # Online selalu di atas.
        online_sort = (
            0
            if member.status
            != discord.Status.offline
            else 1
        )

        # Yang terakhir aktif paling baru
        # berada di atas untuk member offline.
        return (
            online_sort,
            -timestamp,
            member.display_name.lower()
        )

    # ==========================================
    # GET ALL STAFF MEMBERS
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

                # Off Duty dipisahkan.
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

        arrow_blue = (
            self.get_nanz_emoji(
                guild,
                self.ARROW_BLUE_ID,
                "🔵"
            )
        )

        embed = discord.Embed(
            title=(
                f"{arrow_blue} "
                f"{self.HEADER_TITLE}"
            ),
            color=self.HEADER_COLOR
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
            role_info["name"]
        )

        # ======================================
        # TIDAK ADA MEMBER
        # ======================================

        if not members:

            embed.description = (
                "Belum ada staff."
            )

            return embed

        # ======================================
        # ENTRIES
        # ======================================

        entries = []

        for member in members:

            status_emoji = (
                self.get_status_emoji(
                    member
                )
            )

            activity_text = (
                self.get_activity_text(
                    member
                )
            )

            name = (
                discord.utils.escape_markdown(
                    member.display_name
                )
            )

            # ==================================
            # FORMAT
            # ==================================
            #
            # 🟢 Nama
            #    @mention
            #    Aktif: sekarang
            #
            # atau
            #
            # 🔴 Nama
            #    @mention
            #    Terakhir aktif: 5 menit lalu
            #

            entry = (
                f"{status_emoji} **{name}**\n"
                f"{member.mention}\n"
                f"-# {activity_text}"
            )

            entries.append(
                entry
            )

        # ======================================
        # LIMIT DESCRIPTION
        # ======================================

        description = ""

        shown = 0

        for entry in entries:

            if (
                len(description)
                + len(entry)
                + 2
                > 4096
            ):
                break

            description += (
                entry
                + "\n\n"
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

        arrow_purple = (
            self.get_nanz_emoji(
                guild,
                self.ARROW_PURPLE_ID,
                "🟣"
            )
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
        # MEMBER
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
        # TIDAK ADA MEMBER
        # ======================================

        if not members:

            embed.description = (
                "Tidak ada staff."
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

            entry = (
                f"🔕 **{name}**\n"
                f"{member.mention}"
            )

            entries.append(
                entry
            )

        # ======================================
        # LIMIT
        # ======================================

        description = ""

        shown = 0

        for entry in entries:

            if (
                len(description)
                + len(entry)
                + 2
                > 4096
            ):
                break

            description += (
                entry
                + "\n\n"
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

                    if (
                        role_id
                        in found
                    ):
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
                            f"{name} ·"
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
                or
                not self.off_duty_message_id
                or
                any(
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
                    "Header"
                    if key == "header"
                    else
                    "Off Duty"
                    if key == "off_duty"
                    else
                    role_info[
                        "name"
                    ]
                )

                try:

                    embed = (
                        await self.build_panel(
                            guild,
                            key,
                            role_info
                        )
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

                        # Tidak berubah.
                        # Jangan PATCH Discord.
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

        # Jangan proses bot.
        if message.author.bot:
            return

        # Pastikan Member.
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
        # STATUS BERUBAH
        # ======================================

        if before.status != after.status:

            # ==================================
            # ONLINE
            # ==================================

            if (
                after.status
                != discord.Status.offline
            ):

                self.update_activity(
                    after.id
                )

            # ==================================
            # REFRESH
            # ==================================

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
                    role_info[
                        "role_id"
                    ],
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

            embed = (
                await self.build_panel(
                    channel.guild,
                    key,
                    role_info
                )
            )

            message = (
                await channel.send(
                    embed=embed
                )
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