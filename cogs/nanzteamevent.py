import re
import sqlite3
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
from discord import PermissionOverwrite


# ==========================================
# CONFIG
# ==========================================

TEAM_EVENT_CHANNEL_ID = 1510142235730120744
STAFF_CONTROL_CHANNEL_ID = 1498871689075753171
TEAM_CATEGORY_ID = 1406602545828466709

MOD_ROLE_ID = 1555556260269527151
OSIS_ROLE_ID = 1427276194876751902
PEMBINA_ROLE_ID = 1467360501745844446

ROLE_MARKER = "[NANZ-EVENT]"
CHANNEL_MARKER = "[NANZ-EVENT]"

ROLE_PREFIX = "Team "
CHANNEL_PREFIX = "event-"

# Database dibuat otomatis di folder kerja bot.
DB_PATH = Path(__file__).resolve().parent.parent / "nanz_event.db"


# ==========================================
# DATABASE
# ==========================================

def init_database():
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with sqlite3.connect(str(DB_PATH)) as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS event_config (
                guild_id INTEGER PRIMARY KEY,
                event_name TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                max_teams INTEGER NOT NULL DEFAULT 5,
                max_members INTEGER NOT NULL DEFAULT 5,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()


def save_event_config(
    guild_id: int,
    event_name: str,
    description: str,
    max_teams: int,
    max_members: int
):
    init_database()

    with sqlite3.connect(str(DB_PATH)) as conn:

        conn.execute("""
            INSERT INTO event_config
                (
                    guild_id,
                    event_name,
                    description,
                    max_teams,
                    max_members,
                    updated_at
                )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)

            ON CONFLICT(guild_id) DO UPDATE SET
                event_name=excluded.event_name,
                description=excluded.description,
                max_teams=excluded.max_teams,
                max_members=excluded.max_members,
                updated_at=CURRENT_TIMESTAMP
        """, (
            guild_id,
            event_name,
            description,
            max_teams,
            max_members
        ))

        conn.commit()


# ==========================================
# HELPER: TOPIC
# ==========================================

def _parse_topic(topic: str) -> dict:

    data = {}

    if not topic:
        return data

    m = re.search(
        r"leader:(\d+)",
        topic
    )

    if m:
        data["leader_id"] = int(
            m.group(1)
        )

    m = re.search(
        r"max_members:(\d+)",
        topic
    )

    if m:
        data["max_members"] = int(
            m.group(1)
        )

    m = re.search(
        r"max_teams:(\d+)",
        topic
    )

    if m:
        data["max_teams"] = int(
            m.group(1)
        )

    return data


def _build_topic(
    leader_id: int,
    max_members: int,
    max_teams: int
) -> str:

    return (
        f"leader:{leader_id} "
        f"max_members:{max_members} "
        f"max_teams:{max_teams} "
        f"{CHANNEL_MARKER}"
    )


# ==========================================
# EVENT ROLE / CHANNEL
# ==========================================

def get_event_roles(
    guild: discord.Guild
) -> List[discord.Role]:

    return [
        role
        for role in guild.roles
        if ROLE_MARKER in role.name
    ]


def get_team_name_from_role(
    role: discord.Role
) -> str:

    name = role.name

    name = name.replace(
        ROLE_MARKER,
        ""
    ).strip()

    if name.startswith(
        ROLE_PREFIX
    ):
        name = name[
            len(ROLE_PREFIX):
        ].strip()

    return name


def get_team_channel(
    guild: discord.Guild,
    team_name: str
) -> Optional[discord.TextChannel]:

    channel_name = (
        f"{CHANNEL_PREFIX}"
        f"{team_name.lower()}"
    )

    category = guild.get_channel(
        TEAM_CATEGORY_ID
    )

    if category:

        for channel in category.text_channels:

            if (
                channel.name == channel_name
                and channel.topic
                and CHANNEL_MARKER in channel.topic
            ):
                return channel

    # Fallback seluruh guild

    for channel in guild.text_channels:

        if (
            channel.name == channel_name
            and channel.topic
            and CHANNEL_MARKER in channel.topic
        ):
            return channel

    return None


def get_all_teams(
    guild: discord.Guild
) -> dict:

    teams = {}

    for role in get_event_roles(guild):

        team_name = get_team_name_from_role(
            role
        )

        channel = get_team_channel(
            guild,
            team_name
        )

        topic_data = _parse_topic(
            channel.topic
            if channel
            else ""
        )

        teams[team_name] = {
            "role": role,
            "channel": channel,
            "leader_id": topic_data.get(
                "leader_id"
            ),
            "members": [
                member.id
                for member in role.members
            ],
            "max_members": topic_data.get(
                "max_members",
                5
            ),
            "max_teams": topic_data.get(
                "max_teams",
                5
            ),
        }

    return teams


def _get_event_config_channel(
    guild: discord.Guild
) -> Optional[discord.TextChannel]:

    for channel in guild.text_channels:

        if (
            channel.topic
            and "event_config:true" in channel.topic
            and CHANNEL_MARKER in channel.topic
        ):
            return channel

    return None


def is_event_active(
    guild: discord.Guild
) -> bool:

    return (
        len(
            get_event_roles(guild)
        ) > 0
        or _get_event_config_channel(
            guild
        ) is not None
    )


def _get_global_limits(
    guild: discord.Guild
) -> Tuple[int, int]:

    config_channel = _get_event_config_channel(
        guild
    )

    if config_channel:

        data = _parse_topic(
            config_channel.topic
        )

        return (
            data.get("max_teams", 5),
            data.get("max_members", 5)
        )

    teams = get_all_teams(
        guild
    )

    if teams:

        first = next(
            iter(
                teams.values()
            )
        )

        return (
            first["max_teams"],
            first["max_members"]
        )

    return 5, 5


def find_team_of_member(
    guild: discord.Guild,
    user_id: int
) -> Tuple[Optional[str], Optional[dict]]:

    for (
        team_name,
        data
    ) in get_all_teams(guild).items():

        if user_id in data["members"]:

            return (
                team_name,
                data
            )

    return None, None


# ==========================================
# NICKNAME HELPER
# ==========================================

def _encode_nick(
    nick: Optional[str]
) -> str:

    if nick is None:
        return "NONE"

    return (
        nick
        .replace("\\", "\\\\")
        .replace("|", "\\p")
        .replace(" ", "\\s")
    )


def _decode_nick(
    value: str
) -> Optional[str]:

    if value == "NONE":
        return None

    return (
        value
        .replace("\\s", " ")
        .replace("\\p", "|")
        .replace("\\\\", "\\")
    )


def _get_nicks_from_topic(
    topic: str
) -> Dict[int, Optional[str]]:

    result = {}

    if not topic:
        return result

    match = re.search(
        r"nicks:(\S+)",
        topic
    )

    if not match:
        return result

    raw = match.group(1)

    for entry in raw.split("|"):

        if "=" not in entry:
            continue

        user_id_string, encoded = entry.split(
            "=",
            1
        )

        try:

            result[
                int(user_id_string)
            ] = _decode_nick(
                encoded
            )

        except ValueError:
            pass

    return result


def _set_nicks_in_topic(
    topic: str,
    nicks: Dict[int, Optional[str]]
) -> str:

    if not nicks:
        return topic

    parts = "|".join(
        f"{user_id}={_encode_nick(nick)}"
        for user_id, nick in nicks.items()
    )

    nicks_string = (
        f"nicks:{parts}"
    )

    if re.search(
        r"nicks:\S+",
        topic
    ):

        topic = re.sub(
            r"nicks:\S+",
            nicks_string,
            topic
        )

    else:

        topic = (
            topic.rstrip()
            + " "
            + nicks_string
        )

    return topic


async def _save_nick_to_channel(
    channel: discord.TextChannel,
    user_id: int,
    nick: Optional[str]
):

    topic = channel.topic or ""

    nicks = _get_nicks_from_topic(
        topic
    )

    # Jangan timpa nickname yang sudah tersimpan.
    if user_id not in nicks:

        nicks[user_id] = nick

        new_topic = _set_nicks_in_topic(
            topic,
            nicks
        )

        try:

            await channel.edit(
                topic=new_topic
            )

        except Exception:
            pass


async def _restore_nick_from_channel(
    channel: discord.TextChannel,
    member: discord.Member
):

    topic = channel.topic or ""

    nicks = _get_nicks_from_topic(
        topic
    )

    if member.id not in nicks:
        return

    original = nicks.pop(
        member.id
    )

    try:

        await member.edit(
            nick=original
        )

    except Exception:
        pass

    # Hapus entry nickname dari topic.

    new_topic = re.sub(
        r"nicks:\S+",
        "",
        topic
    ).strip()

    if nicks:

        new_topic = _set_nicks_in_topic(
            new_topic,
            nicks
        )

    try:

        await channel.edit(
            topic=new_topic
        )

    except Exception:
        pass


# ==========================================
# CREATE EVENT MODAL
# ==========================================

class CreateEventModal(
    Modal,
    title="Buat Team Event"
):

    event_name = TextInput(
        label="Nama Event",
        placeholder="Mobile Legends Tournament"
    )

    event_description = TextInput(
        label="Deskripsi Event",
        style=discord.TextStyle.paragraph,
        required=False,
        placeholder="Masukkan deskripsi event"
    )

    max_teams = TextInput(
        label="Max Jumlah Team",
        placeholder="5"
    )

    max_members = TextInput(
        label="Max Member per Team",
        placeholder="5"
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        guild = interaction.guild

        if guild is None:

            return await interaction.response.send_message(
                "Command ini hanya bisa digunakan di server.",
                ephemeral=True
            )

        try:

            max_teams = int(
                self.max_teams.value
            )

            max_members = int(
                self.max_members.value
            )

            if (
                max_teams <= 0
                or max_members <= 0
            ):
                raise ValueError

        except ValueError:

            return await interaction.response.send_message(
                "Max team/member harus berupa angka lebih dari 0.",
                ephemeral=True
            )

        # ======================================
        # SIMPAN CONFIG
        # ======================================

        save_event_config(
            guild.id,
            self.event_name.value.strip(),
            self.event_description.value or "",
            max_teams,
            max_members
        )

        # ======================================
        # CONFIG CHANNEL
        # ======================================

        category = guild.get_channel(
            TEAM_CATEGORY_ID
        )

        overwrites = {
            guild.default_role:
                PermissionOverwrite(
                    view_channel=False
                )
        }

        for role_id in [
            MOD_ROLE_ID,
            OSIS_ROLE_ID,
            PEMBINA_ROLE_ID
        ]:

            role = guild.get_role(
                role_id
            )

            if role:

                overwrites[role] = PermissionOverwrite(
                    view_channel=True
                )

        config_topic = (
            f"event_config:true "
            f"max_teams:{max_teams} "
            f"max_members:{max_members} "
            f"{CHANNEL_MARKER}"
        )

        old_config = _get_event_config_channel(
            guild
        )

        if old_config:

            await old_config.edit(
                topic=config_topic,
                category=category,
                overwrites=overwrites
            )

        else:

            await guild.create_text_channel(
                name="event-config",
                category=category,
                overwrites=overwrites,
                topic=config_topic,
                reason="NANZ-EVENT config channel"
            )

        # ======================================
        # PUBLIC EVENT PANEL
        # ======================================

        public_channel = guild.get_channel(
            TEAM_EVENT_CHANNEL_ID
        )

        if public_channel is None:

            return await interaction.response.send_message(
                "Channel event tidak ditemukan.",
                ephemeral=True
            )

        embed = discord.Embed(
            title=self.event_name.value.strip(),
            description=(
                f"{self.event_description.value or ''}\n\n"
                f">>> Buat team kamu sendiri:\n"
                f"**Maksimal Team:** {max_teams}\n"
                f"**Maksimal Member/Team:** {max_members}"
            ),
            color=discord.Color.dark_blue()
        )

        embed.set_author(
            name="nanZ Team Event"
        )

        embed.set_footer(
            text="nanZ Server"
        )

        embed.timestamp = discord.utils.utcnow()

        await public_channel.send(
            embed=embed,
            view=CreateTeamView()
        )

        await interaction.response.send_message(
            "Event berhasil dibuat.",
            ephemeral=True
        )


# ==========================================
# CREATE TEAM MODAL
# ==========================================

class CreateTeamModal(
    Modal,
    title="Buat Team"
):

    team_name = TextInput(
        label="Nama Team",
        placeholder="nanZ"
    )

    team_color = TextInput(
        label="Warna Role (HEX)",
        placeholder="#5865F2",
        required=False
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        guild = interaction.guild
        user = interaction.user

        if guild is None:

            return await interaction.response.send_message(
                "Tidak dapat menemukan server.",
                ephemeral=True
            )

        max_teams, max_members = _get_global_limits(
            guild
        )

        all_teams = get_all_teams(
            guild
        )

        # ======================================
        # LIMIT TEAM
        # ======================================

        if len(all_teams) >= max_teams:

            return await interaction.response.send_message(
                "Jumlah team sudah mencapai batas maksimal.",
                ephemeral=True
            )

        # ======================================
        # CEK USER
        # ======================================

        existing_team, _ = find_team_of_member(
            guild,
            user.id
        )

        if existing_team:

            return await interaction.response.send_message(
                "Kamu sudah berada di team.",
                ephemeral=True
            )

        # ======================================
        # TEAM NAME
        # ======================================

        team_name = self.team_name.value.strip()

        if not team_name:

            return await interaction.response.send_message(
                "Nama team tidak boleh kosong.",
                ephemeral=True
            )

        # Case-insensitive duplicate check

        for existing_name in all_teams:

            if (
                existing_name.lower()
                == team_name.lower()
            ):

                return await interaction.response.send_message(
                    "Nama team sudah digunakan.",
                    ephemeral=True
                )

        # ======================================
        # ROLE COLOR
        # ======================================

        role_color = discord.Color.blue()

        try:

            if self.team_color.value:

                role_color = discord.Color.from_str(
                    self.team_color.value
                )

        except Exception:

            pass

        # ======================================
        # CREATE ROLE
        # ======================================

        role = await guild.create_role(
            name=(
                f"{ROLE_PREFIX}"
                f"{team_name} "
                f"{ROLE_MARKER}"
            ),
            color=role_color,
            mentionable=True,
            reason="NANZ-EVENT"
        )

        await user.add_roles(
            role
        )

        # ======================================
        # NICKNAME
        # ======================================

        original_nick = user.nick

        try:

            if not user.display_name.startswith(
                f"[{team_name}]"
            ):

                await user.edit(
                    nick=(
                        f"[{team_name}] "
                        f"{user.display_name}"
                    )
                )

        except Exception:

            pass

        # ======================================
        # CREATE PRIVATE CHANNEL
        # ======================================

        category = guild.get_channel(
            TEAM_CATEGORY_ID
        )

        overwrites = {

            guild.default_role:
                PermissionOverwrite(
                    view_channel=False
                ),

            role:
                PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )
        }

        for role_id in [
            MOD_ROLE_ID,
            OSIS_ROLE_ID,
            PEMBINA_ROLE_ID
        ]:

            staff_role = guild.get_role(
                role_id
            )

            if staff_role:

                overwrites[staff_role] = PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                )

        # ======================================
        # TOPIC
        # ======================================

        topic = _build_topic(
            user.id,
            max_members,
            max_teams
        )

        nicks = {
            user.id: original_nick
        }

        topic = _set_nicks_in_topic(
            topic,
            nicks
        )

        team_channel = await guild.create_text_channel(
            name=(
                f"{CHANNEL_PREFIX}"
                f"{team_name.lower()}"
            ),
            category=category,
            overwrites=overwrites,
            topic=topic,
            reason="NANZ-EVENT"
        )

        # ======================================
        # TEAM EMBED
        # ======================================

        team_embed = discord.Embed(
            title=f"Team {team_name}",
            description=(
                "Channel private team berhasil dibuat.\n\n"
                f"Leader: {user.mention}\n"
                f"Jumlah Member: 1/{max_members}\n\n"
                "Gunakan channel ini untuk diskusi "
                "dan koordinasi team."
            ),
            color=role.color
        )

        team_embed.set_thumbnail(
            url=user.display_avatar.url
        )

        team_embed.set_footer(
            text="nanZ Team Event"
        )

        await team_channel.send(
            embed=team_embed
        )

        # ======================================
        # RECRUITMENT EMBED
        # ======================================

        public_channel = guild.get_channel(
            TEAM_EVENT_CHANNEL_ID
        )

        if public_channel:

            recruit_embed = discord.Embed(
                title=f"Team {team_name}",
                description=(
                    "Recruitment team telah dibuka.\n\n"
                    f"Leader: {user.mention}\n"
                    f"Jumlah Member: 1/{max_members}\n\n"
                    "Klik tombol di bawah untuk "
                    "bergabung ke team."
                ),
                color=role.color
            )

            recruit_embed.set_thumbnail(
                url=user.display_avatar.url
            )

            recruit_embed.set_footer(
                text="nanZ Team Event"
            )

            await public_channel.send(
                embed=recruit_embed,
                view=TeamActionView(team_name)
            )

        await interaction.response.send_message(
            f"Team **{team_name}** berhasil dibuat.",
            ephemeral=True
        )


# ==========================================
# CREATE TEAM VIEW
# ==========================================

class CreateTeamView(View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Buat Team",
        style=discord.ButtonStyle.blurple,
        custom_id="nanz_create_team_button"
    )
    async def create_team(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        guild = interaction.guild

        if guild is None:

            return await interaction.response.send_message(
                "Tidak dapat menemukan server.",
                ephemeral=True
            )

        if not is_event_active(guild):

            return await interaction.response.send_message(
                "Tidak ada event aktif.",
                ephemeral=True
            )

        await interaction.response.send_modal(
            CreateTeamModal()
        )


# ==========================================
# TEAM ACTION VIEW
# JOIN + LEAVE
# ==========================================

class TeamActionView(View):

    def __init__(
        self,
        team_name: str
    ):

        super().__init__(
            timeout=None
        )

        join_button = Button(
            label="Join Team",
            style=discord.ButtonStyle.green,
            custom_id=f"nanz_join:{team_name}"
        )

        join_button.callback = self._join

        leave_button = Button(
            label="Leave Team",
            style=discord.ButtonStyle.red,
            custom_id=f"nanz_leave:{team_name}"
        )

        leave_button.callback = self._leave

        self.add_item(
            join_button
        )

        self.add_item(
            leave_button
        )

    # ======================================
    # JOIN
    # ======================================

    async def _join(
        self,
        interaction: discord.Interaction
    ):

        guild = interaction.guild
        user = interaction.user

        if guild is None:

            return await interaction.response.send_message(
                "Tidak dapat menemukan server.",
                ephemeral=True
            )

        custom_id = interaction.data.get(
            "custom_id",
            ""
        )

        team_name = custom_id.split(
            ":",
            1
        )[1]

        all_teams = get_all_teams(
            guild
        )

        if team_name not in all_teams:

            return await interaction.response.send_message(
                "Team tidak ditemukan.",
                ephemeral=True
            )

        existing, _ = find_team_of_member(
            guild,
            user.id
        )

        if existing:

            return await interaction.response.send_message(
                "Kamu sudah berada di team.",
                ephemeral=True
            )

        team_data = all_teams[
            team_name
        ]

        if len(
            team_data["members"]
        ) >= team_data["max_members"]:

            return await interaction.response.send_message(
                "Team sudah penuh.",
                ephemeral=True
            )

        role = team_data["role"]

        if role is None:

            return await interaction.response.send_message(
                "Role team tidak ditemukan.",
                ephemeral=True
            )

        # ==================================
        # SAVE ORIGINAL NICK
        # ==================================

        if team_data["channel"]:

            await _save_nick_to_channel(
                team_data["channel"],
                user.id,
                user.nick
            )

        # ==================================
        # ADD ROLE
        # ==================================

        try:

            await user.add_roles(
                role,
                reason="NANZ-EVENT Join Team"
            )

        except discord.Forbidden:

            return await interaction.response.send_message(
                "Bot tidak memiliki izin untuk memberikan role team.",
                ephemeral=True
            )

        # ==================================
        # CHANGE NICK
        # ==================================

        try:

            if not user.display_name.startswith(
                f"[{team_name}]"
            ):

                await user.edit(
                    nick=(
                        f"[{team_name}] "
                        f"{user.display_name}"
                    )
                )

        except Exception:

            pass

        await interaction.response.send_message(
            f"Kamu berhasil join **Team {team_name}**.",
            ephemeral=True
        )

    # ======================================
    # LEAVE
    # ======================================

    async def _leave(
        self,
        interaction: discord.Interaction
    ):

        guild = interaction.guild
        user = interaction.user

        if guild is None:

            return await interaction.response.send_message(
                "Tidak dapat menemukan server.",
                ephemeral=True
            )

        custom_id = interaction.data.get(
            "custom_id",
            ""
        )

        team_name = custom_id.split(
            ":",
            1
        )[1]

        all_teams = get_all_teams(
            guild
        )

        if team_name not in all_teams:

            return await interaction.response.send_message(
                "Team tidak ditemukan.",
                ephemeral=True
            )

        team_data = all_teams[
            team_name
        ]

        if user.id not in team_data["members"]:

            return await interaction.response.send_message(
                "Kamu bukan anggota team ini.",
                ephemeral=True
            )

        if user.id == team_data["leader_id"]:

            return await interaction.response.send_message(
                "Leader tidak bisa leave team. "
                "Gunakan perintah `/disbandteam`.",
                ephemeral=True
            )

        role = team_data["role"]

        if role:

            try:

                await user.remove_roles(
                    role,
                    reason="NANZ-EVENT Leave Team"
                )

            except Exception:

                pass

        # ==================================
        # RESTORE NICK
        # ==================================

        if team_data["channel"]:

            await _restore_nick_from_channel(
                team_data["channel"],
                user
            )

        else:

            try:

                await user.edit(
                    nick=None
                )

            except Exception:

                pass

        await interaction.response.send_message(
            f"Kamu keluar dari **Team {team_name}**.",
            ephemeral=True
        )


# ==========================================
# STAFF CONTROL VIEW
# ==========================================

class StaffControlView(View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Tutup Event",
        style=discord.ButtonStyle.red,
        custom_id="nanz_close_event_button"
    )
    async def close_event(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        # ======================================
        # ADMIN CHECK
        # ======================================

        if not interaction.user.guild_permissions.administrator:

            return await interaction.response.send_message(
                "Kamu tidak memiliki izin untuk menggunakan panel ini.",
                ephemeral=True
            )

        guild = interaction.guild

        if guild is None:

            return await interaction.response.send_message(
                "Tidak dapat menemukan server.",
                ephemeral=True
            )

        all_teams = get_all_teams(
            guild
        )

        config_channel = _get_event_config_channel(
            guild
        )

        if not all_teams and not config_channel:

            return await interaction.response.send_message(
                "Tidak ada event aktif.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Menutup event...",
            ephemeral=True
        )

        # ======================================
        # RESTORE + DELETE TEAM
        # ======================================

        for (
            team_name,
            data
        ) in all_teams.items():

            channel = data["channel"]

            # Restore nickname
            if channel:

                for member_id in list(
                    data["members"]
                ):

                    member = guild.get_member(
                        member_id
                    )

                    if member:

                        await _restore_nick_from_channel(
                            channel,
                            member
                        )

                # Delete channel
                try:

                    await channel.delete(
                        reason="NANZ-EVENT closed"
                    )

                except Exception:

                    pass

            # Delete role
            role = data["role"]

            if role:

                try:

                    await role.delete(
                        reason="NANZ-EVENT closed"
                    )

                except Exception:

                    pass

        # ======================================
        # DELETE CONFIG CHANNEL
        # ======================================

        if config_channel:

            try:

                await config_channel.delete(
                    reason="NANZ-EVENT closed"
                )

            except Exception:

                pass

        # ======================================
        # SAFETY NET CHANNEL
        # ======================================

        category = guild.get_channel(
            TEAM_CATEGORY_ID
        )

        if category:

            for channel in list(
                category.text_channels
            ):

                if (
                    channel.topic
                    and CHANNEL_MARKER in channel.topic
                ):

                    try:

                        await channel.delete(
                            reason="NANZ-EVENT cleanup"
                        )

                    except Exception:

                        pass

        # ======================================
        # SAFETY NET ROLE
        # ======================================

        for role in list(
            guild.roles
        ):

            if ROLE_MARKER in role.name:

                try:

                    await role.delete(
                        reason="NANZ-EVENT cleanup"
                    )

                except Exception:

                    pass

        # ======================================
        # CLOSE EMBED
        # ======================================

        close_embed = discord.Embed(
            title="Event Ditutup",
            description=(
                "Semua data event berhasil dibersihkan.\n\n"
                "• Role team dihapus\n"
                "• Channel team dihapus\n"
                "• Nickname member dikembalikan"
            ),
            color=discord.Color.red()
        )

        close_embed.set_footer(
            text="nanZ Team Event"
        )

        await interaction.followup.send(
            embed=close_embed,
            ephemeral=True
        )


# ==========================================
# EVENT CONTROL VIEW
# ==========================================

class EventControlView(View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    # ======================================
    # BUAT EVENT
    # ======================================

    @discord.ui.button(
        label="Buat Event",
        style=discord.ButtonStyle.green,
        custom_id="nanz_create_event_button"
    )
    async def create_event(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        if not interaction.user.guild_permissions.administrator:

            return await interaction.response.send_message(
                "Kamu tidak memiliki izin untuk menggunakan panel ini.",
                ephemeral=True
            )

        guild = interaction.guild

        if guild is None:

            return await interaction.response.send_message(
                "Tidak dapat menemukan server.",
                ephemeral=True
            )

        # Cegah membuat event kedua
        if is_event_active(guild):

            return await interaction.response.send_message(
                "Masih ada event yang aktif. "
                "Tutup event sebelumnya terlebih dahulu.",
                ephemeral=True
            )

        await interaction.response.send_modal(
            CreateEventModal()
        )

    # ======================================
    # KELOLA EVENT
    # ======================================

    @discord.ui.button(
        label="Kelola Event",
        style=discord.ButtonStyle.blurple,
        custom_id="nanz_manage_event_button"
    )
    async def manage_event(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        if not interaction.user.guild_permissions.administrator:

            return await interaction.response.send_message(
                "Kamu tidak memiliki izin untuk menggunakan panel ini.",
                ephemeral=True
            )

        guild = interaction.guild

        if guild is None:

            return await interaction.response.send_message(
                "Tidak dapat menemukan server.",
                ephemeral=True
            )

        if not is_event_active(guild):

            return await interaction.response.send_message(
                "Tidak ada event aktif saat ini.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="Team Event Management",
            description=(
                "Gunakan panel berikut untuk mengelola "
                "event yang sedang aktif.\n\n"
                "• Tutup event\n"
                "• Membersihkan role team\n"
                "• Membersihkan channel team\n"
                "• Mengembalikan nickname member"
            ),
            color=discord.Color.dark_blue()
        )

        embed.set_footer(
            text="nanZ Team Event"
        )

        await interaction.response.edit_message(
            embed=embed,
            view=StaffControlView()
        )


# ==========================================
# COG
# ==========================================

class NanZTeamEvent(
    commands.Cog
):

    def __init__(
        self,
        bot: commands.Bot
    ):

        self.bot = bot

        # Supaya on_ready tidak register view
        # berulang kali jika Discord melakukan reconnect.
        self._views_registered = False

    # ======================================
    # ON READY
    # ======================================

    @commands.Cog.listener()
    async def on_ready(self):

        if self._views_registered:

            return

        # ==================================
        # REGISTER TEAM VIEWS
        # ==================================

        for guild in self.bot.guilds:

            teams = get_all_teams(
                guild
            )

            for team_name in teams:

                self.bot.add_view(
                    TeamActionView(
                        team_name
                    )
                )

            if teams:

                print(
                    f"[nanZ] "
                    f"{len(teams)} team ditemukan "
                    f"di {guild.name}."
                )

        # ==================================
        # REGISTER STATIC VIEWS
        # ==================================

        self.bot.add_view(
            CreateTeamView()
        )

        self.bot.add_view(
            StaffControlView()
        )

        self.bot.add_view(
            EventControlView()
        )

        self._views_registered = True

        print(
            "[nanZ] Persistent views registered."
        )

    # ======================================
    # CREATE EVENT PANEL
    # ======================================

    @commands.command(
        name="createevent"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def createevent(
        self,
        ctx: commands.Context
    ):

        embed = discord.Embed(
            title="Team Event Control",
            description=(
                "Gunakan panel berikut untuk mengatur "
                "event team.\n\n"
                "**Fitur Tersedia:**\n"
                "• Buat Event\n"
                "• Sistem Team\n"
                "• Recruitment Team\n"
                "• Team Management\n"
                "• Tutup Event"
            ),
            color=discord.Color.dark_gold()
        )

        embed.set_footer(
            text="nanZ Team Event"
        )

        embed.timestamp = discord.utils.utcnow()

        await ctx.send(
            embed=embed,
            view=EventControlView()
        )

    # ======================================
    # EVENT STATUS
    # ======================================

    @commands.command(
        name="eventstatus"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def eventstatus(
        self,
        ctx: commands.Context
    ):

        guild = ctx.guild

        if guild is None:

            return await ctx.send(
                "Command ini hanya bisa digunakan di server."
            )

        all_teams = get_all_teams(
            guild
        )

        max_teams, max_members = _get_global_limits(
            guild
        )

        if not all_teams:

            return await ctx.send(
                "Tidak ada event aktif saat ini."
            )

        lines = [
            f"**Event aktif** — "
            f"{len(all_teams)}/{max_teams} team\n"
        ]

        for (
            name,
            data
        ) in all_teams.items():

            leader = (
                guild.get_member(
                    data["leader_id"]
                )
                if data["leader_id"]
                else None
            )

            leader_text = (
                leader.mention
                if leader
                else "?"
            )

            lines.append(
                f"• **{name}** — "
                f"{len(data['members'])}/"
                f"{max_members} member"
                f" | Leader: {leader_text}"
            )

        embed = discord.Embed(
            title="Status Event",
            description="\n".join(
                lines
            ),
            color=discord.Color.teal()
        )

        embed.set_footer(
            text="nanZ Team Event"
        )

        await ctx.send(
            embed=embed
        )


# ==========================================
# SETUP
# ==========================================

async def setup(
    bot: commands.Bot
):

    init_database()

    await bot.add_cog(
        NanZTeamEvent(bot)
    )