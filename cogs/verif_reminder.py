import discord
from discord.ext import commands

# ========= KONFIGURASI (WAJIB DIISI) =========
VOICE_VERIF_CHANNEL_ID = 1474140456349601802   # ID voice channel verif
STAFF_CHANNEL_ID       = 1416351665929322637   # channel text staff
SISWI_ROLE_ID          = 1453246187636396032   # role Siswi
# ===========================================

# ROLE STAFF (BISA DITAMBAH)
STAFF_ROLE_IDS = {
    1417582562100117584,  # contoh: Mod
    1453103644244316343,
    1408509547601203252,
    1467360501745844446,
    1427276194876751902,  # contoh: Admin
}
# ===============================

class VerifVoiceReminder(commands.Cog):
    """Reminder staff saat member (non-staff) join voice verif"""

    def __init__(self, bot):
        self.bot = bot
        self.notified_users = set()

    def is_staff(self, member: discord.Member) -> bool:
        # cek administrator
        if member.guild_permissions.administrator:
            return True

        # cek role staff
        return any(role.id in STAFF_ROLE_IDS for role in member.roles)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        # ===== JIKA STAFF → ABORT =====
        if self.is_staff(member):
            return

        # ===== JIKA SUDAH PUNYA ROLE SISWI → ABORT =====
        siswi_role = member.guild.get_role(SISWI_ROLE_ID)
        if siswi_role and siswi_role in member.roles:
            return

        # ===== JOIN VOICE VERIF =====
        if after.channel and after.channel.id == VOICE_VERIF_CHANNEL_ID:
            if member.id in self.notified_users:
                return

            self.notified_users.add(member.id)

            staff_channel = self.bot.get_channel(STAFF_CHANNEL_ID)
            if not staff_channel:
                return

            embed = discord.Embed(
                description=(
                    f"👤 **{member}**\n"
                    f"Masuk ke **Voice Verifikasi Siswi**.\n\n"
                    f"Silakan staff segera melakukan verifikasi."
                ),
                color=discord.Color.random()
            )

            embed.set_author(
                name="nanZ Server • Voice Verifikasi",
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
            )

            embed.set_thumbnail(url=member.display_avatar.url)
            embed.timestamp = discord.utils.utcnow()

            view = GoToVerifButton(VOICE_VERIF_CHANNEL_ID)
            await staff_channel.send(embed=embed, view=view)

        # ===== KELUAR VOICE VERIF → RESET =====
        if before.channel and before.channel.id == VOICE_VERIF_CHANNEL_ID:
            self.notified_users.discard(member.id)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        siswi_role = after.guild.get_role(SISWI_ROLE_ID)
        if not siswi_role:
            return

        # ===== AUTO RESET SETELAH ROLE SISWI DIBERIKAN =====
        if siswi_role not in before.roles and siswi_role in after.roles:
            self.notified_users.discard(after.id)

class GoToVerifButton(discord.ui.View):
    def __init__(self, voice_channel_id: int):
        super().__init__(timeout=None)
        self.voice_channel_id = voice_channel_id

    @discord.ui.button(
        label="🎧 Masuk Voice Verif",
        style=discord.ButtonStyle.primary
    )
    async def go_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"➡️ Klik untuk menuju voice: <#{self.voice_channel_id}>",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(VerifVoiceReminder(bot))