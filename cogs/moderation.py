import discord
from discord.ext import commands
from datetime import datetime, timezone


# =========================================================
# KONFIGURASI CHANNEL LOG
# =========================================================

LOG_CHANNELS = {
    "moderation": 1469289471471124659,  # Ban, kick, timeout
    "voice": 1555249826881474610,       # Voice log
    "message": 1555249914836025375,     # Message log
    "member": 1555249958591139970,      # Member join/leave
    "role": 1555250009388359760,        # Role log
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

    @staticmethod
    def member_label(member):
        """Mention dan nama member dalam bentuk teks."""
        if member is None:
            return "Tidak diketahui"

        return f"{member.mention} | {member} (`{member.id}`)"

    @staticmethod
    def channel_label(channel):
        """Mention channel sekaligus nama teks dan ID."""
        if channel is None:
            return "Tidak diketahui"

        return (
            f"{channel.mention} | "
            f"#{channel.name} (`{channel.id}`)"
        )

    @staticmethod
    def role_label(role):
        """Mention role sekaligus nama teks dan ID."""
        if role is None:
            return "Tidak diketahui"

        return f"{role.mention} | {role.name} (`{role.id}`)"

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
            self.member_label(entry.user)
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
            name="Pengguna",
            value=self.member_label(user),
            inline=False
        )

        embed.add_field(
            name="Moderator",
            value=moderator,
            inline=False
        )

        embed.add_field(
            name="Alasan",
            value=reason[:1024],
            inline=False
        )

        await self.send_log(
            guild,
            "moderation",
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
                self.member_label(entry.user)
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
                name="Pengguna",
                value=self.member_label(member),
                inline=False
            )

            embed.add_field(
                name="Moderator",
                value=moderator,
                inline=False
            )

            embed.add_field(
                name="Alasan",
                value=reason[:1024],
                inline=False
            )

            await self.send_log(
                member.guild,
                "moderation",
                embed=embed
            )
            return

        embed = discord.Embed(
            title="📤 Member Keluar",
            color=discord.Color.dark_grey(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="Pengguna",
            value=self.member_label(member),
            inline=False
        )

        await self.send_log(
            member.guild,
            "member",
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
            name="Pengguna",
            value=self.member_label(member),
            inline=False
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
            embed=embed
        )

    # =====================================================
    # TIMEOUT & ROLE LOG
    # =====================================================

    @commands.Cog.listener()
    async def on_member_update(self, before, after):

        # -------------------------------------------------
        # TIMEOUT LOG
        # -------------------------------------------------

        if before.timed_out_until != after.timed_out_until:
            entry = await self.get_audit_entry(
                after.guild,
                discord.AuditLogAction.member_update,
                after.id
            )

            moderator = (
                self.member_label(entry.user)
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
                    name="Pengguna",
                    value=self.member_label(after),
                    inline=False
                )

                embed.add_field(
                    name="Moderator",
                    value=moderator,
                    inline=False
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
                    name="Pengguna",
                    value=self.member_label(after),
                    inline=False
                )

                embed.add_field(
                    name="Moderator",
                    value=moderator,
                    inline=False
                )

            await self.send_log(
                after.guild,
                "moderation",
                embed=embed
            )

        # -------------------------------------------------
        # ROLE DITAMBAHKAN / DIHAPUS
        # -------------------------------------------------

        added_roles = set(after.roles) - set(before.roles)
        removed_roles = set(before.roles) - set(after.roles)

        for role in added_roles:
            embed = discord.Embed(
                title="➕ Role Ditambahkan",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )

            embed.add_field(
                name="Pengguna",
                value=self.member_label(after),
                inline=False
            )

            embed.add_field(
                name="Role",
                value=self.role_label(role),
                inline=False
            )

            await self.send_log(
                after.guild,
                "role",
                embed=embed
            )

        for role in removed_roles:
            embed = discord.Embed(
                title="➖ Role Dihapus",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )

            embed.add_field(
                name="Pengguna",
                value=self.member_label(after),
                inline=False
            )

            embed.add_field(
                name="Role",
                value=self.role_label(role),
                inline=False
            )

            await self.send_log(
                after.guild,
                "role",
                embed=embed
            )

    # =====================================================
    # ROLE CREATE / DELETE LOG
    # =====================================================

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        embed = discord.Embed(
            title="🆕 Role Dibuat",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="Nama Role",
            value=self.role_label(role),
            inline=False
        )

        await self.send_log(
            role.guild,
            "role",
            embed=embed
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        embed = discord.Embed(
            title="🗑️ Role Dihapus dari Server",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )

        # Simpan nama sebagai teks biasa karena role sudah dihapus.
        embed.add_field(
            name="Nama Role",
            value=f"{role.name} (`{role.id}`)",
            inline=False
        )

        await self.send_log(
            role.guild,
            "role",
            embed=embed
        )

    # =====================================================
    # CHANNEL CREATE / DELETE LOG
    # =====================================================

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        is_voice = isinstance(
            channel,
            (discord.VoiceChannel, discord.StageChannel)
        )

        category = "voice" if is_voice else "message"
        channel_type = "Voice Channel" if is_voice else "Channel"

        embed = discord.Embed(
            title=f"🆕 {channel_type} Dibuat",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="Nama Channel",
            value=self.channel_label(channel),
            inline=False
        )

        await self.send_log(
            channel.guild,
            category,
            embed=embed
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        is_voice = isinstance(
            channel,
            (discord.VoiceChannel, discord.StageChannel)
        )

        category = "voice" if is_voice else "message"
        channel_type = "Voice Channel" if is_voice else "Channel"

        embed = discord.Embed(
            title=f"🗑️ {channel_type} Dihapus",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )

        # Nama dan ID tetap tersimpan sebagai teks biasa.
        embed.add_field(
            name="Nama Channel",
            value=f"{channel.name} (`{channel.id}`)",
            inline=False
        )

        await self.send_log(
            channel.guild,
            category,
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
            description = (
                f"{self.member_label(member)} bergabung ke "
                f"{self.channel_label(after.channel)}"
            )
            color = discord.Color.green()

        elif before.channel is not None and after.channel is None:
            title = "🔇 Keluar dari Voice"
            description = (
                f"{self.member_label(member)} keluar dari "
                f"{self.channel_label(before.channel)}"
            )
            color = discord.Color.red()

        else:
            title = "🔀 Pindah Voice Channel"
            description = (
                f"{self.member_label(member)} berpindah dari "
                f"{self.channel_label(before.channel)} ke "
                f"{self.channel_label(after.channel)}"
            )
            color = discord.Color.blue()

        embed = discord.Embed(
            title=title,
            description=description[:4000],
            color=color,
            timestamp=datetime.now(timezone.utc)
        )

        await self.send_log(
            member.guild,
            "voice",
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
            name="Pengguna",
            value=self.member_label(message.author),
            inline=False
        )

        embed.add_field(
            name="Channel",
            value=self.channel_label(message.channel),
            inline=False
        )

        content = (
            message.content
            or "*Tidak ada teks atau pesan tidak tersimpan di cache.*"
        )

        await self.send_log(
            message.guild,
            "message",
            content=f"**Isi pesan yang dihapus:**\n{content[:1700]}",
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
            name="Pengguna",
            value=self.member_label(before.author),
            inline=False
        )

        embed.add_field(
            name="Channel",
            value=self.channel_label(before.channel),
            inline=False
        )

        embed.add_field(
            name="Link Pesan",
            value=f"[Buka pesan]({after.jump_url})",
            inline=False
        )

        old_content = before.content or "*Kosong*"
        new_content = after.content or "*Kosong*"

        text = (
            f"**Pesan sebelum diedit:**\n{old_content[:800]}\n\n"
            f"**Pesan setelah diedit:**\n{new_content[:800]}"
        )

        await self.send_log(
            before.guild,
            "message",
            content=text,
            embed=embed
        )


async def setup(bot):
    await bot.add_cog(ModLog(bot))