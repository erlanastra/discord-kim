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

MOD_ROLE_ID = 1453103644244316343
OSIS_ROLE_ID = 1427276194876751902
PEMBINA_ROLE_ID = 1467360501745844446

MAX_TEAMS = 5
MAX_MEMBERS = 5

# ==========================================
# STORAGE
# ==========================================

active_event = {
    "enabled": False,
    "name": None,
    "description": None,
    "teams": {}
}

original_nicknames = {}

# ==========================================
# CREATE EVENT MODAL
# ==========================================

class CreateEventModal(Modal, title="Buat Team Event"):

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

    async def on_submit(self, interaction: discord.Interaction):

        global MAX_TEAMS
        global MAX_MEMBERS

        try:
            MAX_TEAMS = int(self.max_teams.value)
            MAX_MEMBERS = int(self.max_members.value)
        except:
            return await interaction.response.send_message(
                "Max team/member harus berupa angka.",
                ephemeral=True
            )

        active_event["enabled"] = True
        active_event["name"] = self.event_name.value
        active_event["description"] = self.event_description.value
        active_event["teams"] = {}

        public_channel = interaction.guild.get_channel(
            TEAM_EVENT_CHANNEL_ID
        )

        embed = discord.Embed(
            title=self.event_name.value,
            description=(
                f"{self.event_description.value}\n\n"
                f">>> Buat team kamu sendiri:\n"
                f"**Maksimal Team:** {MAX_TEAMS}\n"
                f"**Maksimal Member/Team:** {MAX_MEMBERS}"
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

class CreateTeamModal(Modal, title="Buat Team"):

    team_name = TextInput(
        label="Nama Team",
        placeholder="nanZ"
    )

    team_color = TextInput(
        label="Warna Role (HEX)",
        placeholder="#5865F2",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):

        guild = interaction.guild
        user = interaction.user

        if len(active_event["teams"]) >= MAX_TEAMS:
            return await interaction.response.send_message(
                "Jumlah team sudah mencapai batas maksimal.",
                ephemeral=True
            )

        for team_data in active_event["teams"].values():
            if user.id in team_data["members"]:
                return await interaction.response.send_message(
                    "Kamu sudah berada di team.",
                    ephemeral=True
                )

        team_name = self.team_name.value

        role_color = discord.Color.blue()

        try:
            if self.team_color.value:
                role_color = discord.Color.from_str(
                    self.team_color.value
                )
        except:
            pass

        # ==========================================
        # CREATE ROLE
        # ==========================================

        role = await guild.create_role(
            name=f"Team {team_name}",
            color=role_color,
            mentionable=True,
            reason="nanZ Team Event"
        )

        await user.add_roles(role)

        # ==========================================
        # SAVE ORIGINAL NICKNAME
        # ==========================================

        if user.id not in original_nicknames:
            original_nicknames[user.id] = user.nick

        # ==========================================
        # CHANGE NICKNAME
        # ==========================================

        try:
            current_name = user.display_name

            if not current_name.startswith(f"[{team_name}]"):
                await user.edit(
                    nick=f"[{team_name}] {current_name}"
                )
        except:
            pass

        # ==========================================
        # CREATE PRIVATE CHANNEL
        # ==========================================

        category = guild.get_channel(
            TEAM_CATEGORY_ID
        )

        overwrites = {
            guild.default_role: PermissionOverwrite(
                view_channel=False
            ),
            role: PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        }

        mod_role = guild.get_role(MOD_ROLE_ID)
        osis_role = guild.get_role(OSIS_ROLE_ID)
        pembina_role = guild.get_role(PEMBINA_ROLE_ID)

        if mod_role:
            overwrites[mod_role] = PermissionOverwrite(
                view_channel=True,
                send_messages=True
            )

        if osis_role:
            overwrites[osis_role] = PermissionOverwrite(
                view_channel=True,
                send_messages=True
            )

        if pembina_role:
            overwrites[pembina_role] = PermissionOverwrite(
                view_channel=True,
                send_messages=True
            )

        team_channel = await guild.create_text_channel(
            name=f"team-{team_name.lower()}",
            category=category,
            overwrites=overwrites,
            reason="nanZ Team Event"
        )

        # ==========================================
        # SAVE TEAM DATA
        # ==========================================

        active_event["teams"][team_name] = {
            "role_id": role.id,
            "channel_id": team_channel.id,
            "leader_id": user.id,
            "members": [user.id]
        }

        # ==========================================
        # TEAM CHANNEL EMBED
        # ==========================================

        team_embed = discord.Embed(
            title=f"Team {team_name}",
            description=(
                f"Channel private team berhasil dibuat.\n\n"
                f"Leader: {user.mention}\n"
                f"Jumlah Member: 1/{MAX_MEMBERS}\n\n"
                f"Gunakan channel ini untuk diskusi dan koordinasi team."
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

        # ==========================================
        # PUBLIC RECRUITMENT EMBED
        # ==========================================

        public_channel = guild.get_channel(
            TEAM_EVENT_CHANNEL_ID
        )

        recruit_embed = discord.Embed(
            title=f"Team {team_name}",
            description=(
                f"Recruitment team telah dibuka.\n\n"
                f"Leader: {user.mention}\n"
                f"Jumlah Member: 1/{MAX_MEMBERS}\n\n"
                f"Klik tombol di bawah untuk bergabung ke team."
            ),
            color=role.color
        )

        recruit_embed.set_thumbnail(
            url=user.display_avatar.url
        )

        recruit_embed.set_footer(
            text=active_event["name"]
        )

        join_view = View(timeout=None)

        join_view.add_item(
            JoinTeamView(team_name).children[0]
        )

        join_view.add_item(
            LeaveTeamView(team_name).children[0]
        )

        await public_channel.send(
            embed=recruit_embed,
            view=join_view
        )

        await interaction.response.send_message(
            f"Team {team_name} berhasil dibuat.",
            ephemeral=True
        )

# ==========================================
# CREATE TEAM VIEW
# ==========================================

class CreateTeamView(View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Buat Team",
        style=discord.ButtonStyle.blurple
    )
    async def create_team(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        if not active_event["enabled"]:
            return await interaction.response.send_message(
                "Tidak ada event aktif.",
                ephemeral=True
            )

        await interaction.response.send_modal(
            CreateTeamModal()
        )

# ==========================================
# JOIN TEAM VIEW
# ==========================================

class JoinTeamView(View):

    def __init__(self, team_name):
        super().__init__(timeout=None)
        self.team_name = team_name

    @discord.ui.button(
        label="Join Team",
        style=discord.ButtonStyle.green
    )
    async def join_team(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        guild = interaction.guild
        user = interaction.user

        if self.team_name not in active_event["teams"]:
            return await interaction.response.send_message(
                "Team tidak ditemukan.",
                ephemeral=True
            )

        for team_data in active_event["teams"].values():
            if user.id in team_data["members"]:
                return await interaction.response.send_message(
                    "Kamu sudah berada di team.",
                    ephemeral=True
                )

        team_data = active_event["teams"][self.team_name]

        if len(team_data["members"]) >= MAX_MEMBERS:
            return await interaction.response.send_message(
                "Team sudah penuh.",
                ephemeral=True
            )

        role = guild.get_role(team_data["role_id"])

        await user.add_roles(role)

        # ==========================================
        # SAVE ORIGINAL NICKNAME
        # ==========================================

        if user.id not in original_nicknames:
            original_nicknames[user.id] = user.nick

        # ==========================================
        # CHANGE NICKNAME
        # ==========================================

        try:
            current_name = user.display_name

            if not current_name.startswith(f"[{self.team_name}]"):
                await user.edit(
                    nick=f"[{self.team_name}] {current_name}"
                )
        except:
            pass

        team_data["members"].append(user.id)

        await interaction.response.send_message(
            f"Kamu berhasil join Team {self.team_name}.",
            ephemeral=True
        )

# ==========================================
# LEAVE TEAM VIEW
# ==========================================

class LeaveTeamView(View):

    def __init__(self, team_name):
        super().__init__(timeout=None)
        self.team_name = team_name

    @discord.ui.button(
        label="Leave Team",
        style=discord.ButtonStyle.red
    )
    async def leave_team(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        guild = interaction.guild
        user = interaction.user

        if self.team_name not in active_event["teams"]:
            return await interaction.response.send_message(
                "Team tidak ditemukan.",
                ephemeral=True
            )

        team_data = active_event["teams"][self.team_name]

        if user.id not in team_data["members"]:
            return await interaction.response.send_message(
                "Kamu bukan anggota team ini.",
                ephemeral=True
            )

        # ==========================================
        # LEADER CANNOT LEAVE
        # ==========================================

        if user.id == team_data["leader_id"]:
            return await interaction.response.send_message(
                "Leader team tidak bisa leave team.",
                ephemeral=True
            )

        role = guild.get_role(team_data["role_id"])

        if role:
            await user.remove_roles(role)

        # ==========================================
        # RESET NICKNAME
        # ==========================================

        try:
            original_nick = original_nicknames.get(user.id)
            await user.edit(nick=original_nick)
        except:
            pass

        # ==========================================
        # REMOVE MEMBER
        # ==========================================

        team_data["members"].remove(user.id)

        await interaction.response.send_message(
            f"Kamu keluar dari Team {self.team_name}.",
            ephemeral=True
        )

# ==========================================
# STAFF CONTROL VIEW
# ==========================================

class StaffControlView(View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Tutup Event",
        style=discord.ButtonStyle.red
    )
    async def close_event(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        guild = interaction.guild

        if not active_event["enabled"]:
            return await interaction.response.send_message(
                "Tidak ada event aktif.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Menutup event...",
            ephemeral=True
        )

        for team_name, team_data in active_event["teams"].items():

            # DELETE CHANNEL
            channel = guild.get_channel(
                team_data["channel_id"]
            )

            if channel:
                await channel.delete(
                    reason="Event Closed"
                )

            # DELETE ROLE
            role = guild.get_role(
                team_data["role_id"]
            )

            if role:
                await role.delete(
                    reason="Event Closed"
                )

            # RESET NICKNAME
            for member_id in team_data["members"]:

                member = guild.get_member(member_id)

                if member:
                    try:
                        original_nick = original_nicknames.get(member_id)
                        await member.edit(nick=original_nick)
                    except:
                        pass

        active_event["enabled"] = False
        active_event["name"] = None
        active_event["description"] = None
        active_event["teams"] = {}

        original_nicknames.clear()

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
# COG
# ==========================================

class NanZTeamEvent(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def createevent(self, ctx):

        embed = discord.Embed(
            title="Team Event Control",
            description=(
                "Gunakan panel berikut untuk mengatur event team.\n\n"
                "Fitur Tersedia:\n"
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

        view = View(timeout=None)

        create_button = Button(
            label="Buat Event",
            style=discord.ButtonStyle.blurple
        )

        async def create_callback(interaction):

            await interaction.response.send_modal(
                CreateEventModal()
            )

        create_button.callback = create_callback

        view.add_item(create_button)
        view.add_item(StaffControlView().children[0])

        await ctx.send(
            embed=embed,
            view=view
        )

# ==========================================
# SETUP
# ==========================================

async def setup(bot):
    await bot.add_cog(NanZTeamEvent(bot))