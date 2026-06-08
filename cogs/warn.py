import discord
from discord.ext import commands
from discord.ui import (
    View,
    Button,
    Modal,
    TextInput,
    UserSelect
)

from datetime import timedelta, datetime

# ==================================================
# ROLE IDS
# ==================================================

MOD_ROLE_ID = 1453103644244316343
PEMBINA_ROLE_ID = 1467360501745844446
OSIS_ROLE_ID = 1427276194876751902

# ==================================================
# CHANNEL IDS
# ==================================================

MOD_LOG_CHANNEL_ID = 1513404867140390922

# ==================================================
# CASE SYSTEM
# ==================================================

CASE_NUMBER = 0

# ==================================================
# HELPERS
# ==================================================

def has_staff_permission(member):

    allowed_roles = [
        MOD_ROLE_ID,
        PEMBINA_ROLE_ID,
        OSIS_ROLE_ID
    ]

    return any(
        role.id in allowed_roles
        for role in member.roles
    )


def has_mod_permission(member):

    return any(
        role.id == MOD_ROLE_ID
        for role in member.roles
    )


def is_staff(member):

    staff_roles = [
        MOD_ROLE_ID,
        PEMBINA_ROLE_ID,
        OSIS_ROLE_ID
    ]

    return any(
        role.id in staff_roles
        for role in member.roles
    )


# ==================================================
# LOGS
# ==================================================

async def send_logs(
    guild,
    action,
    target,
    moderator,
    reason,
    duration=None
):

    global CASE_NUMBER

    CASE_NUMBER += 1

    channel = guild.get_channel(
        MOD_LOG_CHANNEL_ID
    )

    if not channel:
        return

    embed = discord.Embed(
        title=f"{action} LOG",
        description=(
            "Aktivitas moderasi baru telah "
            "dilakukan oleh staff server."
        ),
        color=0x2BFFF5,
        timestamp=datetime.now()
    )

    embed.add_field(
        name="CASE",
        value=f"#{CASE_NUMBER}",
        inline=True
    )

    embed.add_field(
        name="ACTION",
        value=action,
        inline=True
    )

    embed.add_field(
        name="TARGET MEMBER",
        value=(
            f"{target.mention}\n"
            f"`{target.id}`"
        ),
        inline=False
    )

    embed.add_field(
        name="MODERATOR",
        value=(
            f"{moderator.mention}\n"
            f"`{moderator.id}`"
        ),
        inline=False
    )

    if duration:

        embed.add_field(
            name="DURATION",
            value=duration,
            inline=False
        )

    embed.add_field(
        name="REASON",
        value=reason,
        inline=False
    )

    embed.set_footer(
        text="nanZ Moderation Logs"
    )

    await channel.send(embed=embed)


# ==================================================
# WARN MODAL
# ==================================================

class WarnModal(Modal, title="Warn Member"):

    def __init__(self, bot, member):

        super().__init__()

        self.bot = bot
        self.member = member

    reason = TextInput(
        label="Reason",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction):

        embed = discord.Embed(
            title="⚠️ Pemberitahuan Tindakan",
            description=(
                f"Halo {self.member.mention},\n"
                f"Kamu menerima tindakan moderasi "
                f"dari staff nanZ Server."
            ),
            color=0x2BFFF5
        )

        embed.add_field(
            name="INFORMASI TINDAKAN",
            value=(
                f">>> **Jenis Tindakan** : Warn\n"
                f"**Alasan** : {self.reason.value}"
            ),
            inline=False
        )

        embed.set_footer(
            text="nanZ Moderation System"
        )

        try:
            await self.member.send(embed=embed)
        except:
            pass

        await interaction.response.send_message(
            f"{self.member.mention} berhasil diwarn.",
            ephemeral=True
        )

        await send_logs(
            interaction.guild,
            "WARN",
            self.member,
            interaction.user,
            self.reason.value
        )


# ==================================================
# TIMEOUT MODAL
# ==================================================

class TimeoutModal(Modal, title="Timeout Member"):

    def __init__(self, bot, member):

        super().__init__()

        self.bot = bot
        self.member = member

    duration = TextInput(
        label="Duration (minutes)"
    )

    reason = TextInput(
        label="Reason",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction):

        minutes = int(self.duration.value)

        await self.member.timeout(
            timedelta(minutes=minutes),
            reason=self.reason.value
        )

        embed = discord.Embed(
            title="Pemberitahuan Tindakan",
            description=(
                f"Halo {self.member.mention},\n\n"
                f"Kamu menerima tindakan timeout "
                f"dari staff nanZ Server."
            ),
            color=0x2BFFF5
        )

        embed.add_field(
            name="INFORMASI TINDAKAN",
            value=(
                f"**Jenis Tindakan** : Timeout\n"
                f"**Durasi** : {minutes} menit\n"
                f"**Alasan** : {self.reason.value}"
            ),
            inline=False
        )

        embed.set_footer(
            text="nanZ Moderation System"
        )

        try:
            await self.member.send(embed=embed)
        except:
            pass

        await interaction.response.send_message(
            f"{self.member.mention} berhasil ditimeout.",
            ephemeral=True
        )

        await send_logs(
            interaction.guild,
            "TIMEOUT",
            self.member,
            interaction.user,
            self.reason.value,
            f"{minutes} menit"
        )


# ==================================================
# KICK MODAL
# ==================================================

class KickModal(Modal, title="Kick Member"):

    def __init__(self, bot, member):

        super().__init__()

        self.bot = bot
        self.member = member

    reason = TextInput(
        label="Reason",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction):

        embed = discord.Embed(
            title="Pemberitahuan Tindakan",
            description=(
                f"Halo {self.member.name},\n\n"
                f"Kamu telah dikeluarkan dari "
                f"nanZ Server."
            ),
            color=0xFF4D4D
        )

        embed.add_field(
            name="INFORMASI TINDAKAN",
            value=(
                f"**Jenis Tindakan** : Kick\n"
                f"**Alasan** : {self.reason.value}"
            ),
            inline=False
        )

        try:
            await self.member.send(embed=embed)
        except:
            pass

        await self.member.kick(
            reason=self.reason.value
        )

        await interaction.response.send_message(
            f"{self.member.mention} berhasil dikick.",
            ephemeral=True
        )

        await send_logs(
            interaction.guild,
            "KICK",
            self.member,
            interaction.user,
            self.reason.value
        )


# ==================================================
# BAN MODAL
# ==================================================

class BanModal(Modal, title="Ban Member"):

    def __init__(self, bot, member):

        super().__init__()

        self.bot = bot
        self.member = member

    reason = TextInput(
        label="Reason",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction):

        embed = discord.Embed(
            title="Pemberitahuan Tindakan",
            description=(
                f"Halo {self.member.name},\n\n"
                f"Kamu telah diblokir dari "
                f"nanZ Server."
            ),
            color=0xFF4D4D
        )

        embed.add_field(
            name="INFORMASI TINDAKAN",
            value=(
                f"**Jenis Tindakan** : Ban\n"
                f"**Alasan** : {self.reason.value}"
            ),
            inline=False
        )

        try:
            await self.member.send(embed=embed)
        except:
            pass

        await self.member.ban(
            reason=self.reason.value
        )

        await interaction.response.send_message(
            f"{self.member.mention} berhasil diban.",
            ephemeral=True
        )

        await send_logs(
            interaction.guild,
            "BAN",
            self.member,
            interaction.user,
            self.reason.value
        )


# ==================================================
# USER SELECTS
# ==================================================

class WarnSelect(UserSelect):

    def __init__(self, bot):

        super().__init__(
            placeholder="Pilih member...",
            min_values=1,
            max_values=1,
            custom_id="warn_select"
        )

        self.bot = bot

    async def callback(self, interaction):

        member = self.values[0]

        if is_staff(member):

            return await interaction.response.send_message(
                "Kamu tidak dapat menindak staff.",
                ephemeral=True
            )

        await interaction.response.send_modal(
            WarnModal(self.bot, member)
        )


class TimeoutSelect(UserSelect):

    def __init__(self, bot):

        super().__init__(
            placeholder="Pilih member...",
            min_values=1,
            max_values=1,
            custom_id="timeout_select"
        )

        self.bot = bot

    async def callback(self, interaction):

        member = self.values[0]

        if is_staff(member):

            return await interaction.response.send_message(
                "Kamu tidak dapat menindak staff.",
                ephemeral=True
            )

        await interaction.response.send_modal(
            TimeoutModal(self.bot, member)
        )


class KickSelect(UserSelect):

    def __init__(self, bot):

        super().__init__(
            placeholder="Pilih member...",
            min_values=1,
            max_values=1,
            custom_id="kick_select"
        )

        self.bot = bot

    async def callback(self, interaction):

        member = self.values[0]

        if is_staff(member):

            return await interaction.response.send_message(
                "Kamu tidak dapat menindak staff.",
                ephemeral=True
            )

        await interaction.response.send_modal(
            KickModal(self.bot, member)
        )


class BanSelect(UserSelect):

    def __init__(self, bot):

        super().__init__(
            placeholder="Pilih member...",
            min_values=1,
            max_values=1,
            custom_id="ban_select"
        )

        self.bot = bot

    async def callback(self, interaction):

        member = self.values[0]

        if is_staff(member):

            return await interaction.response.send_message(
                "Kamu tidak dapat menindak staff.",
                ephemeral=True
            )

        await interaction.response.send_modal(
            BanModal(self.bot, member)
        )


# ==================================================
# SELECT VIEWS
# ==================================================

class WarnSelectView(View):

    def __init__(self, bot):

        super().__init__(timeout=60)

        self.add_item(
            WarnSelect(bot)
        )


class TimeoutSelectView(View):

    def __init__(self, bot):

        super().__init__(timeout=60)

        self.add_item(
            TimeoutSelect(bot)
        )


class KickSelectView(View):

    def __init__(self, bot):

        super().__init__(timeout=60)

        self.add_item(
            KickSelect(bot)
        )


class BanSelectView(View):

    def __init__(self, bot):

        super().__init__(timeout=60)

        self.add_item(
            BanSelect(bot)
        )


# ==================================================
# MAIN PANEL
# ==================================================

class ModerationPanel(View):

    def __init__(self, bot):

        super().__init__(timeout=None)

        self.bot = bot

    # ================= WARN =================

    @discord.ui.button(
        label="Warn",
        style=discord.ButtonStyle.secondary,
        custom_id="warn_button"
    )
    async def warn_button(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        if not has_staff_permission(interaction.user):

            return await interaction.response.send_message(
                "Kamu tidak memiliki permission.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Pilih member yang ingin diwarn.",
            view=WarnSelectView(self.bot),
            ephemeral=True
        )

    # ================= TIMEOUT =================

    @discord.ui.button(
        label="Timeout",
        style=discord.ButtonStyle.primary,
        custom_id="timeout_button"
    )
    async def timeout_button(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        if not has_staff_permission(interaction.user):

            return await interaction.response.send_message(
                "Kamu tidak memiliki permission.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Pilih member yang ingin ditimeout.",
            view=TimeoutSelectView(self.bot),
            ephemeral=True
        )

    # ================= KICK =================

    @discord.ui.button(
        label="Kick",
        style=discord.ButtonStyle.danger,
        custom_id="kick_button"
    )
    async def kick_button(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        if not has_mod_permission(interaction.user):

            return await interaction.response.send_message(
                "Hanya mod yang dapat menggunakan fitur ini.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Pilih member yang ingin dikick.",
            view=KickSelectView(self.bot),
            ephemeral=True
        )

    # ================= BAN =================

    @discord.ui.button(
        label="Ban",
        style=discord.ButtonStyle.danger,
        custom_id="ban_button"
    )
    async def ban_button(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        if not has_mod_permission(interaction.user):

            return await interaction.response.send_message(
                "Hanya mod yang dapat menggunakan fitur ini.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Pilih member yang ingin diban.",
            view=BanSelectView(self.bot),
            ephemeral=True
        )


# ==================================================
# COG
# ==================================================

class Warn(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.bot.add_view(
            ModerationPanel(bot)
        )

    @commands.command()
    async def modpanel(self, ctx):

        embed = discord.Embed(
            title="Moderation Control Panel",
            description=(
                "Gunakan panel berikut "
                "untuk melakukan tindakan moderasi."
            ),
            color=0x2BFFF5
        )

        embed.set_footer(
            text="nanZ Moderation System"
        )

        await ctx.send(
            embed=embed,
            view=ModerationPanel(self.bot)
        )


async def setup(bot):

    await bot.add_cog(
        Warn(bot)
    )