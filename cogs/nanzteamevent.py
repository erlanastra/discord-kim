import re
from typing import List, Dict, Tuple, Optional

import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
from discord import PermissionOverwrite

# ==========================================
# CONFIG
# ==========================================

TEAM_EVENT_CHANNEL_ID  = 1510142235730120744
STAFF_CONTROL_CHANNEL_ID = 1498871689075753171
TEAM_CATEGORY_ID       = 1406602545828466709

MOD_ROLE_ID     = 1453103644244316343
OSIS_ROLE_ID    = 1427276194876751902
PEMBINA_ROLE_ID = 1467360501745844446

ROLE_MARKER      = "[NANZ-EVENT]"   # suffix pada nama role
CHANNEL_MARKER   = "[NANZ-EVENT]"   # substring di topic channel
ROLE_PREFIX      = "Team "          # "Team nanZ [NANZ-EVENT]"
CHANNEL_PREFIX   = "event-"         # "event-nanz"

# ==========================================
# HELPER: baca state dari Discord
# ==========================================

def _parse_topic(topic: str) -> dict:
    """Ekstrak leader_id, max_members, max_teams dari topic channel."""
    data = {}
    if not topic:
        return data
    m = re.search(r"leader:(\d+)", topic)
    if m:
        data["leader_id"] = int(m.group(1))
    m = re.search(r"max_members:(\d+)", topic)
    if m:
        data["max_members"] = int(m.group(1))
    m = re.search(r"max_teams:(\d+)", topic)
    if m:
        data["max_teams"] = int(m.group(1))
    return data


def _build_topic(leader_id: int, max_members: int, max_teams: int) -> str:
    return (
        f"leader:{leader_id} "
        f"max_members:{max_members} "
        f"max_teams:{max_teams} "
        f"{CHANNEL_MARKER}"
    )


def get_event_roles(guild: discord.Guild) -> List[discord.Role]:
    """Kembalikan semua role event (yang namanya mengandung ROLE_MARKER)."""
    return [r for r in guild.roles if ROLE_MARKER in r.name]


def get_team_name_from_role(role: discord.Role) -> str:
    """
    "Team nanZ [NANZ-EVENT]" → "nanZ"
    """
    name = role.name
    name = name.replace(ROLE_MARKER, "").strip()
    if name.startswith(ROLE_PREFIX):
        name = name[len(ROLE_PREFIX):].strip()
    return name


def get_team_channel(
    guild: discord.Guild,
    team_name: str
) -> Optional[discord.TextChannel]:
    """Cari channel berdasarkan topic yang mengandung CHANNEL_MARKER dan nama channel."""
    channel_name = f"{CHANNEL_PREFIX}{team_name.lower()}"
    category = guild.get_channel(TEAM_CATEGORY_ID)
    if category:
        for ch in category.text_channels:
            if ch.name == channel_name and ch.topic and CHANNEL_MARKER in ch.topic:
                return ch
    # fallback: seluruh guild
    for ch in guild.text_channels:
        if ch.name == channel_name and ch.topic and CHANNEL_MARKER in ch.topic:
            return ch
    return None


def get_all_teams(guild: discord.Guild) -> dict:
    """
    Kembalikan dict berisi semua data team dari Discord langsung.
    Tidak bergantung pada variabel in-memory sama sekali.

    Struktur return:
    {
        "nanZ": {
            "role": <Role>,
            "channel": <TextChannel | None>,
            "leader_id": int | None,
            "members": [int, ...],
            "max_members": int,
            "max_teams": int,
        },
        ...
    }
    """
    teams = {}
    for role in get_event_roles(guild):
        team_name = get_team_name_from_role(role)
        channel   = get_team_channel(guild, team_name)
        topic_data = _parse_topic(channel.topic if channel else "")

        teams[team_name] = {
            "role":        role,
            "channel":     channel,
            "leader_id":   topic_data.get("leader_id"),
            "members":     [m.id for m in role.members],
            "max_members": topic_data.get("max_members", 5),
            "max_teams":   topic_data.get("max_teams", 5),
        }
    return teams


def is_event_active(guild: discord.Guild) -> bool:
    return len(get_event_roles(guild)) > 0 or _get_event_config_channel(guild) is not None


def _get_event_config_channel(guild: discord.Guild) -> discord.TextChannel | None:
    """
    Channel config event: topic mengandung CHANNEL_MARKER dan "event_config:true".
    Digunakan untuk menyimpan max_teams & max_members ketika belum ada team sama sekali.
    """
    for ch in guild.text_channels:
        if ch.topic and "event_config:true" in ch.topic and CHANNEL_MARKER in ch.topic:
            return ch
    return None


def _get_global_limits(guild: discord.Guild) -> Tuple[int, int]:
    """Ambil (max_teams, max_members) dari channel config atau dari team pertama yang ada."""
    config_ch = _get_event_config_channel(guild)
    if config_ch:
        d = _parse_topic(config_ch.topic)
        return d.get("max_teams", 5), d.get("max_members", 5)
    teams = get_all_teams(guild)
    if teams:
        first = next(iter(teams.values()))
        return first["max_teams"], first["max_members"]
    return 5, 5


def find_team_of_member(
    guild: discord.Guild,
    user_id: int
) -> Tuple[Optional[str], Optional[dict]]:
    """Temukan team tempat user bergabung. Return (team_name, team_data) atau (None, None)."""
    for team_name, data in get_all_teams(guild).items():
        if user_id in data["members"]:
            return team_name, data
    return None, None


def _encode_nick(nick: Optional[str]) -> str:
    if nick is None:
        return "NONE"
    return nick.replace("\\", "\\\\").replace("|", "\\p").replace(" ", "\\s")


def _decode_nick(s: str) -> Optional[str]:
    if s == "NONE":
        return None
    return s.replace("\\s", " ").replace("\\p", "|").replace("\\\\", "\\")


def _get_nicks_from_topic(topic: str) -> Dict[int, Optional[str]]:
    """Parse 'nicks:<ID>=<enc>|...' dari topic."""
    result: dict[int, Optional[str]] = {}
    if not topic:
        return result
    m = re.search(r"nicks:(\S+)", topic)
    if not m:
        return result
    raw = m.group(1)
    for entry in raw.split("|"):
        if "=" not in entry:
            continue
        uid_s, enc = entry.split("=", 1)
        try:
            result[int(uid_s)] = _decode_nick(enc)
        except ValueError:
            pass
    return result


def _set_nicks_in_topic(topic: str, nicks: Dict[int, Optional[str]]) -> str:
    """Ganti atau tambahkan bagian 'nicks:...' di topic."""
    if not nicks:
        return topic
    parts = "|".join(f"{uid}={_encode_nick(nick)}" for uid, nick in nicks.items())
    nicks_str = f"nicks:{parts}"
    if re.search(r"nicks:\S+", topic):
        topic = re.sub(r"nicks:\S+", nicks_str, topic)
    else:
        topic = topic.rstrip() + " " + nicks_str
    return topic


async def _save_nick_to_channel(channel: discord.TextChannel, user_id: int, nick: Optional[str]):
    """Simpan nickname asli ke topic channel."""
    topic = channel.topic or ""
    nicks = _get_nicks_from_topic(topic)
    if user_id not in nicks:          # jangan timpa yang sudah tersimpan
        nicks[user_id] = nick
        new_topic = _set_nicks_in_topic(topic, nicks)
        try:
            await channel.edit(topic=new_topic)
        except Exception:
            pass


async def _restore_nick_from_channel(
    channel: discord.TextChannel,
    member: discord.Member
):
    """Kembalikan nickname member dari topic, lalu hapus entry-nya."""
    topic = channel.topic or ""
    nicks = _get_nicks_from_topic(topic)
    original = nicks.pop(member.id, ...)   # ... = sentinel "tidak ada"
    if original is ...:
        return
    try:
        await member.edit(nick=original)
    except Exception:
        pass
    # Update topic
    new_topic = _set_nicks_in_topic(
        re.sub(r"nicks:\S+", "", topic).strip(),
        nicks
    )
    try:
        await channel.edit(topic=new_topic)
    except Exception:
        pass

# ==========================================
# CREATE EVENT MODAL
# ==========================================

class CreateEventModal(Modal, title="Buat Team Event"):

    event_name = TextInput(label="Nama Event", placeholder="Mobile Legends Tournament")
    event_description = TextInput(
        label="Deskripsi Event",
        style=discord.TextStyle.paragraph,
        required=False,
        placeholder="Masukkan deskripsi event"
    )
    max_teams = TextInput(label="Max Jumlah Team", placeholder="5")
    max_members = TextInput(label="Max Member per Team", placeholder="5")

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild

        try:
            mt = int(self.max_teams.value)
            mm = int(self.max_members.value)
        except ValueError:
            return await interaction.response.send_message(
                "Max team/member harus berupa angka.", ephemeral=True
            )

        # Simpan config di channel tersembunyi agar tahan restart
        category = guild.get_channel(TEAM_CATEGORY_ID)
        overwrites = {
            guild.default_role: PermissionOverwrite(view_channel=False),
        }
        for rid in [MOD_ROLE_ID, OSIS_ROLE_ID, PEMBINA_ROLE_ID]:
            r = guild.get_role(rid)
            if r:
                overwrites[r] = PermissionOverwrite(view_channel=True)

        config_topic = (
            f"event_config:true "
            f"max_teams:{mt} "
            f"max_members:{mm} "
            f"{CHANNEL_MARKER}"
        )
        await guild.create_text_channel(
            name="event-config",
            category=category,
            overwrites=overwrites,
            topic=config_topic,
            reason="NANZ-EVENT config channel"
        )

        public_channel = guild.get_channel(TEAM_EVENT_CHANNEL_ID)
        embed = discord.Embed(
            title=self.event_name.value,
            description=(
                f"{self.event_description.value or ''}\n\n"
                f">>> Buat team kamu sendiri:\n"
                f"**Maksimal Team:** {mt}\n"
                f"**Maksimal Member/Team:** {mm}"
            ),
            color=discord.Color.dark_blue()
        )
        embed.set_author(name="nanZ Team Event")
        embed.set_footer(text="nanZ Server")
        embed.timestamp = discord.utils.utcnow()

        await public_channel.send(embed=embed, view=CreateTeamView())
        await interaction.response.send_message("Event berhasil dibuat.", ephemeral=True)


# ==========================================
# CREATE TEAM MODAL
# ==========================================

class CreateTeamModal(Modal, title="Buat Team"):

    team_name = TextInput(label="Nama Team", placeholder="nanZ")
    team_color = TextInput(
        label="Warna Role (HEX)", placeholder="#5865F2", required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        user  = interaction.user

        max_teams, max_members = _get_global_limits(guild)
        all_teams = get_all_teams(guild)

        if len(all_teams) >= max_teams:
            return await interaction.response.send_message(
                "Jumlah team sudah mencapai batas maksimal.", ephemeral=True
            )

        existing_team, _ = find_team_of_member(guild, user.id)
        if existing_team:
            return await interaction.response.send_message(
                "Kamu sudah berada di team.", ephemeral=True
            )

        team_name = self.team_name.value.strip()
        if team_name in all_teams:
            return await interaction.response.send_message(
                "Nama team sudah digunakan.", ephemeral=True
            )

        role_color = discord.Color.blue()
        try:
            if self.team_color.value:
                role_color = discord.Color.from_str(self.team_color.value)
        except Exception:
            pass

        # Buat role dengan ROLE_MARKER sebagai suffix
        role = await guild.create_role(
            name=f"{ROLE_PREFIX}{team_name} {ROLE_MARKER}",
            color=role_color,
            mentionable=True,
            reason="NANZ-EVENT"
        )
        await user.add_roles(role)

        # Nickname
        original_nick = user.nick
        try:
            if not user.display_name.startswith(f"[{team_name}]"):
                await user.edit(nick=f"[{team_name}] {user.display_name}")
        except Exception:
            pass

        # Buat private channel — topic menyimpan leader_id, max_members, max_teams
        category = guild.get_channel(TEAM_CATEGORY_ID)
        overwrites = {
            guild.default_role: PermissionOverwrite(view_channel=False),
            role: PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            ),
        }
        for rid in [MOD_ROLE_ID, OSIS_ROLE_ID, PEMBINA_ROLE_ID]:
            r = guild.get_role(rid)
            if r:
                overwrites[r] = PermissionOverwrite(view_channel=True, send_messages=True)

        topic = _build_topic(user.id, max_members, max_teams)
        # Simpan nickname asli di topic
        nicks = {user.id: original_nick}
        topic = _set_nicks_in_topic(topic, nicks)

        team_channel = await guild.create_text_channel(
            name=f"{CHANNEL_PREFIX}{team_name.lower()}",
            category=category,
            overwrites=overwrites,
            topic=topic,
            reason="NANZ-EVENT"
        )

        # Embed info di channel team
        team_embed = discord.Embed(
            title=f"Team {team_name}",
            description=(
                f"Channel private team berhasil dibuat.\n\n"
                f"Leader: {user.mention}\n"
                f"Jumlah Member: 1/{max_members}\n\n"
                f"Gunakan channel ini untuk diskusi dan koordinasi team."
            ),
            color=role.color
        )
        team_embed.set_thumbnail(url=user.display_avatar.url)
        team_embed.set_footer(text="nanZ Team Event")
        await team_channel.send(embed=team_embed)

        # Recruitment embed di public channel
        public_channel = guild.get_channel(TEAM_EVENT_CHANNEL_ID)
        recruit_embed = discord.Embed(
            title=f"Team {team_name}",
            description=(
                f"Recruitment team telah dibuka.\n\n"
                f"Leader: {user.mention}\n"
                f"Jumlah Member: 1/{max_members}\n\n"
                f"Klik tombol di bawah untuk bergabung ke team."
            ),
            color=role.color
        )
        recruit_embed.set_thumbnail(url=user.display_avatar.url)
        recruit_embed.set_footer(text="nanZ Team Event")
        await public_channel.send(embed=recruit_embed, view=TeamActionView(team_name))

        await interaction.response.send_message(
            f"Team **{team_name}** berhasil dibuat.", ephemeral=True
        )


# ==========================================
# CREATE TEAM VIEW (persistent)
# ==========================================

class CreateTeamView(View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Buat Team",
        style=discord.ButtonStyle.blurple,
        custom_id="nanz_create_team_button"
    )
    async def create_team(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        if not is_event_active(guild):
            return await interaction.response.send_message(
                "Tidak ada event aktif.", ephemeral=True
            )
        await interaction.response.send_modal(CreateTeamModal())


# ==========================================
# TEAM ACTION VIEW  (Join + Leave, persistent)
# custom_id format:  "nanz_join:<team_name>"  /  "nanz_leave:<team_name>"
# ==========================================

class TeamActionView(View):

    def __init__(self, team_name: str):
        super().__init__(timeout=None)

        join_btn = Button(
            label="Join Team",
            style=discord.ButtonStyle.green,
            custom_id=f"nanz_join:{team_name}"
        )
        join_btn.callback = self._join

        leave_btn = Button(
            label="Leave Team",
            style=discord.ButtonStyle.red,
            custom_id=f"nanz_leave:{team_name}"
        )
        leave_btn.callback = self._leave

        self.add_item(join_btn)
        self.add_item(leave_btn)

    # ------------------------------------------
    async def _join(self, interaction: discord.Interaction):
        guild = interaction.guild
        user  = interaction.user
        team_name = interaction.data["custom_id"].split(":", 1)[1]

        all_teams = get_all_teams(guild)

        if team_name not in all_teams:
            return await interaction.response.send_message(
                "Team tidak ditemukan.", ephemeral=True
            )

        existing, _ = find_team_of_member(guild, user.id)
        if existing:
            return await interaction.response.send_message(
                "Kamu sudah berada di team.", ephemeral=True
            )

        team_data = all_teams[team_name]

        if len(team_data["members"]) >= team_data["max_members"]:
            return await interaction.response.send_message(
                "Team sudah penuh.", ephemeral=True
            )

        role = team_data["role"]
        if not role:
            return await interaction.response.send_message(
                "Role team tidak ditemukan.", ephemeral=True
            )

        # Simpan nick asli ke topic channel
        if team_data["channel"]:
            await _save_nick_to_channel(team_data["channel"], user.id, user.nick)

        await user.add_roles(role)

        try:
            if not user.display_name.startswith(f"[{team_name}]"):
                await user.edit(nick=f"[{team_name}] {user.display_name}")
        except Exception:
            pass

        await interaction.response.send_message(
            f"Kamu berhasil join **Team {team_name}**.", ephemeral=True
        )

    # ------------------------------------------
    async def _leave(self, interaction: discord.Interaction):
        guild = interaction.guild
        user  = interaction.user
        team_name = interaction.data["custom_id"].split(":", 1)[1]

        all_teams = get_all_teams(guild)

        if team_name not in all_teams:
            return await interaction.response.send_message(
                "Team tidak ditemukan.", ephemeral=True
            )

        team_data = all_teams[team_name]

        if user.id not in team_data["members"]:
            return await interaction.response.send_message(
                "Kamu bukan anggota team ini.", ephemeral=True
            )

        if user.id == team_data["leader_id"]:
            return await interaction.response.send_message(
                "Leader tidak bisa leave team. Gunakan perintah `/disbandteam`.", ephemeral=True
            )

        role = team_data["role"]
        if role:
            await user.remove_roles(role)

        # Kembalikan nickname dari topic
        if team_data["channel"]:
            await _restore_nick_from_channel(team_data["channel"], user)
        else:
            try:
                await user.edit(nick=None)
            except Exception:
                pass

        await interaction.response.send_message(
            f"Kamu keluar dari **Team {team_name}**.", ephemeral=True
        )


# ==========================================
# STAFF CONTROL VIEW (persistent)
# ==========================================

class StaffControlView(View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Tutup Event",
        style=discord.ButtonStyle.red,
        custom_id="nanz_close_event_button"
    )
    async def close_event(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild

        all_teams = get_all_teams(guild)
        config_ch = _get_event_config_channel(guild)

        if not all_teams and not config_ch:
            return await interaction.response.send_message(
                "Tidak ada event aktif.", ephemeral=True
            )

        await interaction.response.send_message("Menutup event...", ephemeral=True)

        # Kembalikan semua nickname, hapus channel & role
        for team_name, data in all_teams.items():
            channel = data["channel"]

            # Restore nick semua member dari topic
            if channel:
                for member_id in list(data["members"]):
                    member = guild.get_member(member_id)
                    if member:
                        await _restore_nick_from_channel(channel, member)
                try:
                    await channel.delete(reason="NANZ-EVENT closed")
                except Exception:
                    pass

            role = data["role"]
            if role:
                try:
                    await role.delete(reason="NANZ-EVENT closed")
                except Exception:
                    pass

        # Hapus channel config
        if config_ch:
            try:
                await config_ch.delete(reason="NANZ-EVENT closed")
            except Exception:
                pass

        # Hapus sisa channel event yang mungkin lolos (safety net)
        category = guild.get_channel(TEAM_CATEGORY_ID)
        if category:
            for ch in list(category.text_channels):
                if ch.topic and CHANNEL_MARKER in ch.topic:
                    try:
                        await ch.delete(reason="NANZ-EVENT cleanup")
                    except Exception:
                        pass

        # Hapus sisa role event yang mungkin lolos (safety net)
        for role in list(guild.roles):
            if ROLE_MARKER in role.name:
                try:
                    await role.delete(reason="NANZ-EVENT cleanup")
                except Exception:
                    pass

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
        close_embed.set_footer(text="nanZ Team Event")
        await interaction.followup.send(embed=close_embed, ephemeral=True)


# ==========================================
# COG
# ==========================================

class NanZTeamEvent(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------------------------
    @commands.Cog.listener()
    async def on_ready(self):
        """
        Daftarkan persistent views untuk semua team yang ada di guild.
        Tidak ada state yang perlu di-restore karena semua dibaca live dari Discord.
        """
        for guild in self.bot.guilds:
            teams = get_all_teams(guild)
            for team_name in teams:
                self.bot.add_view(TeamActionView(team_name))
            if teams:
                print(f"[nanZ] {len(teams)} team ditemukan di {guild.name}.")

        self.bot.add_view(CreateTeamView())
        self.bot.add_view(StaffControlView())
        print("[nanZ] Persistent views registered.")

    # ------------------------------------------
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def createevent(self, ctx: commands.Context):
        """Panel kontrol staff untuk membuat dan menutup event."""
        embed = discord.Embed(
            title="Team Event Control",
            description=(
                "Gunakan panel berikut untuk mengatur event team.\n\n"
                "**Fitur Tersedia:**\n"
                "• Buat Event\n"
                "• Sistem Team\n"
                "• Recruitment Team\n"
                "• Team Management\n"
                "• Tutup Event"
            ),
            color=discord.Color.dark_gold()
        )
        embed.set_footer(text="nanZ Team Event")
        embed.timestamp = discord.utils.utcnow()

        view = View(timeout=None)

        create_btn = Button(
            label="Buat Event",
            style=discord.ButtonStyle.blurple,
            custom_id="nanz_open_create_event_modal"
        )

        async def create_callback(interaction: discord.Interaction):
            await interaction.response.send_modal(CreateEventModal())

        create_btn.callback = create_callback
        view.add_item(create_btn)

        # Tombol "Tutup Event" dari StaffControlView
        close_btn = Button(
            label="Tutup Event",
            style=discord.ButtonStyle.red,
            custom_id="nanz_close_event_button"
        )
        close_btn.callback = StaffControlView().close_event
        view.add_item(close_btn)

        await ctx.send(embed=embed, view=view)

    # ------------------------------------------
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def eventstatus(self, ctx: commands.Context):
        """Tampilkan status event saat ini (debug/admin)."""
        guild = interaction.guild if hasattr(ctx, "interaction") else ctx.guild
        guild = ctx.guild
        all_teams = get_all_teams(guild)
        max_teams, max_members = _get_global_limits(guild)

        if not all_teams:
            return await ctx.send("Tidak ada event aktif saat ini.")

        lines = [f"**Event aktif** — {len(all_teams)}/{max_teams} team\n"]
        for name, data in all_teams.items():
            leader = guild.get_member(data["leader_id"]) if data["leader_id"] else None
            lines.append(
                f"• **{name}** — {len(data['members'])}/{max_members} member"
                f" | Leader: {leader.mention if leader else '?'}"
            )

        embed = discord.Embed(
            title="Status Event",
            description="\n".join(lines),
            color=discord.Color.teal()
        )
        embed.set_footer(text="nanZ Team Event")
        await ctx.send(embed=embed)


# ==========================================
# SETUP
# ==========================================

async def setup(bot: commands.Bot):
    await bot.add_cog(NanZTeamEvent(bot))