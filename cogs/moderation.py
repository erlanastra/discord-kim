import discord
from discord.ext import commands
from discord.utils import get
from datetime import datetime

class ModLog(commands.Cog):
    """Cog final untuk log semua tindakan moderasi di server dengan user ID"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Ganti dengan ID channel log staff kalian
        self.mod_log_channel_id = 1469289471471124659

    async def send_mod_log(self, action: str, target, moderator: discord.Member = None, reason: str = None, extra: str = None):
        """Kirim embed log ke channel staff"""
        channel = self.bot.get_channel(self.mod_log_channel_id)
        if not channel:
            print("[ModLog] Channel mod-log tidak ditemukan!")
            return

        embed = discord.Embed(
            title=f"⚡ Tindakan Moderasi: {action}",
            description=(
                f"**Target:** {getattr(target, 'mention', str(target))} | `{getattr(target, 'id', 'Unknown')}`\n"
                f"**Moderator:** {moderator.mention if moderator else 'Unknown'} | `{getattr(moderator, 'id', 'Unknown')}`"
            ),
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        if reason:
            embed.add_field(name="Alasan", value=reason, inline=False)
        if extra:
            embed.add_field(name="Info Tambahan", value=extra, inline=False)
        embed.set_footer(text="NanZ Server • Mod Log")

        await channel.send(embed=embed)

    # ================== AUDIT LOG LISTENERS ==================

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        entry = await guild.audit_logs(action=discord.AuditLogAction.ban, limit=1).find(lambda e: e.target.id == user.id)
        moderator = entry.user if entry else None
        reason = entry.reason if entry else None
        await self.send_mod_log("Ban", user, moderator, reason)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        entry = await member.guild.audit_logs(action=discord.AuditLogAction.kick, limit=1).find(lambda e: e.target.id == member.id)
        if entry:
            moderator = entry.user
            reason = entry.reason
            await self.send_mod_log("Kick", member, moderator, reason)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Timeout / timed_out_until
        if before.timed_out_until != after.timed_out_until:
            moderator = None
            entry = await after.guild.audit_logs(action=discord.AuditLogAction.member_update, limit=1).find(lambda e: e.target.id == after.id)
            if entry:
                moderator = entry.user
            await self.send_mod_log("Timeout", after, moderator, extra=f"Dari: {before.timed_out_until} → {after.timed_out_until}")

        # Role changes
        added_roles = [r for r in after.roles if r not in before.roles]
        removed_roles = [r for r in before.roles if r not in after.roles]

        for role in added_roles:
            await self.send_mod_log("Role Added", after, None, extra=f"Role: {role.name}")
        for role in removed_roles:
            await self.send_mod_log("Role Removed", after, None, extra=f"Role: {role.name}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel != after.channel:
            extra = f"Dari: {before.channel.name if before.channel else 'None'} → {after.channel.name if after.channel else 'None'}"
            await self.send_mod_log("Voice Channel Update", member, None, extra=extra)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        await self.send_mod_log("Delete Message", message.author, None, extra=f"Channel: {message.channel.mention}\nIsi: {message.content}")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.content != after.content:
            await self.send_mod_log(
                "Edit Message", 
                before.author, 
                None, 
                extra=f"Channel: {before.channel.mention}\nDari: {before.content}\nKe: {after.content}"
            )

# ================== SETUP COG ==================
async def setup(bot: commands.Bot):
    await bot.add_cog(ModLog(bot))
