import discord
from discord.ext import commands
from datetime import datetime, timezone


# =========================================================
# KONFIGURASI CHANNEL LOG
# =========================================================

LOG_CHANNELS = {
    "moderation": 1469289471471124659,
    "voice": 1555249826881474610,
    "message": 1555249914836025375,
    "member": 1555249958591139970,
    "role": 1555250009388359760,
}


# =========================================================
# MODERATION LOG
# =========================================================

class ModLog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # HELPER
    # =====================================================

    async def send_log(self, guild, category, content=None, embed=None):
        channel_id = LOG_CHANNELS.get(category, 0)

        if not channel_id:
            return

        channel = guild.get_channel(channel_id)

        if channel is None:
            try:
                channel = await guild.fetch_channel(channel_id)
            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException
            ):
                return

        try:
            await channel.send(
                content=content,
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none()
            )
        except discord.HTTPException as error:
            print(f"[MODLOG] Gagal mengirim log: {error}")

    async def get_audit_entry(self, guild, action, target_id):
        try:
            async for entry in guild.audit_logs(
                limit=5,
                action=action
            ):
                if (
                    entry.target
                    and entry.target.id == target_id
                    and (
                        datetime.now(timezone.utc) - entry.created_at
                    ).total_seconds() < 15
                ):
                    return entry

        except (discord.Forbidden, discord.HTTPException):
            pass

        return None

    # =====================================================
    # BAN LOG
    # =====================================================

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        entry = await self.get_audit_entry(
            guild,
            discord.AuditLogAction.ban,
            user.id
        )

        moderator = (
            entry.user.mention
            if entry and entry.user
            else "Tidak diketahui"
        )

        reason = (
            entry.reason
            if entry and entry.reason
            else "Tidak ada alasan"
        )

        embed = discord.Embed(
            title="🔨 Member Dibanned",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="Moderator",
            value=moderator,
            inline=True
        )
        embed.add_field(
            name="Alasan",
            value=reason[:1024],
            inline=False
        )

        await self.send_log(
            guild,
            "moderation",
            content=f"{user.mention} (`{user.id}`)",
            embed=embed
        )

    # =====================================================
    # KICK / MEMBER LEAVE LOG
    # =====================================================

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        entry = await self.get_audit_entry(
            member.guild,
            discord.AuditLogAction.kick,
            member.id
        )

        if entry:
            moderator = (
                entry.user.mention
                if entry.user
                else "Tidak diketahui"
            )

            reason = (
                entry.reason
                if entry.reason
                else "Tidak ada alasan"
            )

            embed = discord.Embed(
                title="👢 Member Dikick",
                color=discord.Color.orange(),
                timestamp=datetime.now(timezone.utc)
            )

            embed.add_field(
                name="Moderator",
                value=moderator,
                inline=True
            )
            embed.add_field(
                name="Alasan",
                value=reason[:1024],
                inline=False
            )

            await self.send_log(
                member.guild,
                "moderation",
                content=f"{member.mention} (`{member.id}`)",
                embed=embed
            )
            return

        embed = discord.Embed(
            title="📤 Member Keluar",
            color=discord.Color.dark_grey(),
            timestamp=datetime.now(timezone.utc)
        )

        await self.send_log(
            member.guild,
            "member",
            content=f"{member.mention} (`{member.id}`)",
            embed=embed
        )

    # =====================================================
    # MEMBER JOIN LOG
    # =====================================================

    @commands.Cog.listener()
    async def on_member_join(self, member):
        embed = discord.Embed(
            title="📥 Member Bergabung",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="Akun Dibuat",
            value=discord.utils.format_dt(
                member.created_at,
                style="R"
            ),
            inline=False
        )

        await self.send_log(
            member.guild,
            "member",
            content=f"{member.mention} (`{member.id}`)",
            embed=embed
        )

    # =====================================================
    # TIMEOUT & ROLE LOG
    # =====================================================

    @commands.Cog.listener()
    async def on_member_update(self, before, after):

        # =================================================
        # TIMEOUT LOG
        # =================================================

        if before.timed_out_until != after.timed_out_until:
            entry = await self.get_audit_entry(
                after.guild,
                discord.AuditLogAction.member_update,
                after.id
            )

            moderator = (
                entry.user.mention
                if entry and entry.user
                else "Tidak diketahui"
            )

            reason = (
                entry.reason
                if entry and entry.reason
                else "Tidak ada alasan"
            )

            if after.timed_out_until:
                embed = discord.Embed(
                    title="⏳ Member Diberi Timeout",
                    color=discord.Color.orange(),
                    timestamp=datetime.now(timezone.utc)
                )

                embed.add_field(
                    name="Moderator",
                    value=moderator,
                    inline=True
                )
                embed.add_field(
                    name="Berakhir",
                    value=discord.utils.format_dt(
                        after.timed_out_until,
                        style="F"
                    ),
                    inline=False
                )
                embed.add_field(
                    name="Alasan",
                    value=reason[:1024],
                    inline=False
                )

            else:
                embed = discord.Embed(
                    title="✅ Timeout Dicabut",
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc)
                )

                embed.add_field(
                    name="Moderator",
                    value=moderator,
                    inline=True
                )

            await self.send_log(
                after.guild,
                "moderation",
                content=f"{after.mention} (`{after.id}`)",
                embed=embed
            )

        # =================================================
        # ROLE LOG
        # =================================================

        added_roles = set(after.roles) - set(before.roles)
        removed_roles = set(before.roles) - set(after.roles)

        for role in added_roles:
            embed = discord.Embed(
                title="➕ Role Ditambahkan",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )

            embed.add_field(
                name="Role",
                value=role.mention,
                inline=False
            )

            await self.send_log(
                after.guild,
                "role",
                content=f"{after.mention} (`{after.id}`)",
                embed=embed
            )

        for role in removed_roles:
            embed = discord.Embed(
                title="➖ Role Dihapus",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )

            embed.add_field(
                name="Role",
                value=role.mention,
                inline=False
            )

            await self.send_log(
                after.guild,
                "role",
                content=f"{after.mention} (`{after.id}`)",
                embed=embed
            )

    # =====================================================
    # VOICE LOG
    # =====================================================

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel:
            return

        if before.channel is None and after.channel is not None:
            title = "🔊 Bergabung ke Voice"
            description = f"Channel: {after.channel.mention}"
            color = discord.Color.green()

        elif before.channel is not None and after.channel is None:
            title = "🔇 Keluar dari Voice"
            description = f"Channel: {before.channel.mention}"
            color = discord.Color.red()

        else:
            title = "🔀 Pindah Voice Channel"
            description = (
                f"Dari: {before.channel.mention}\n"
                f"Ke: {after.channel.mention}"
            )
            color = discord.Color.blue()

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )

        await self.send_log(
            member.guild,
            "voice",
            content=f"{member.mention} (`{member.id}`)",
            embed=embed
        )

    # =====================================================
    # MESSAGE DELETE LOG
    # =====================================================

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild or message.author.bot:
            return

        embed = discord.Embed(
            title="🗑️ Pesan Dihapus",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="Channel",
            value=message.channel.mention,
            inline=False
        )

        content = message.content or (
            "*Tidak ada teks atau pesan tidak tersimpan di cache.*"
        )

        log_content = (
            f"{message.author.mention} (`{message.author.id}`)\n"
            f"**Isi pesan yang dihapus:**\n"
            f"{content[:1800]}"
        )

        await self.send_log(
            message.guild,
            "message",
            content=log_content,
            embed=embed
        )

    # =====================================================
    # MESSAGE EDIT LOG
    # =====================================================

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not before.guild or before.author.bot:
            return

        if before.content == after.content:
            return

        embed = discord.Embed(
            title="✏️ Pesan Diedit",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="Channel",
            value=before.channel.mention,
            inline=False
        )

        embed.add_field(
            name="Link Pesan",
            value=f"[Buka pesan]({after.jump_url})",
            inline=False
        )

        old_content = before.content or "*Kosong*"
        new_content = after.content or "*Kosong*"

        log_content = (
            f"{before.author.mention} (`{before.author.id}`)\n"
            f"**Pesan sebelum diedit:**\n"
            f"{old_content[:800]}\n\n"
            f"**Pesan setelah diedit:**\n"
            f"{new_content[:800]}"
        )

        await self.send_log(
            before.guild,
            "message",
            content=log_content,
            embed=embed
        )


async def setup(bot):
    await bot.add_cog(ModLog(bot))