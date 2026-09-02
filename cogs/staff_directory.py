import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone


class StaffDirectory(commands.Cog):
    """
    Cog untuk menampilkan panel staff per-role secara otomatis & real-time.
    Fitur:
    - Panel terpisah per role dengan warna khas masing-masing role
    - Status member (Online / Idle / DND / Offline) + ikon
    - Sorting otomatis: yang online tampil di atas
    - Summary panel (ringkasan total staff & yang sedang aktif)
    - Auto-chunking supaya tidak melebihi limit embed Discord
    - Auto refresh saat role berubah / status berubah / bot restart
    - Command manual: !setupdirectory & !syncdirectory
    """

    # Konfigurasi hierarki role staff. Tinggal edit di sini kalau ada
    # perubahan role/emoji/warna tanpa perlu utak-atik logic di bawah.
    HIERARCHY = [
        {
            "role_id": 1417582562100117584,
            "name": "Guru Besar",
            "emoji": "👑",
            "color": discord.Color.gold(),
        },
        {
            "role_id": 1453103644244316343,
            "name": "Moderator",
            "emoji": "🛡️",
            "color": discord.Color.red(),
        },
        {
            "role_id": 1467360501745844446,
            "name": "Pembina OSIS",
            "emoji": "📚",
            "color": discord.Color.teal(),
        },
        {
            "role_id": 1427276194876751902,
            "name": "OSIS",
            "emoji": "✍️",
            "color": discord.Color.blurple(),
        },
    ]

    STATUS_MAP = {
        discord.Status.online: ("🟢", "Online"),
        discord.Status.idle: ("🌙", "Idle"),
        discord.Status.dnd: ("⛔", "Do Not Disturb"),
        discord.Status.offline: ("⚪", "Offline"),
        discord.Status.invisible: ("⚪", "Offline"),
    }

    MAX_FIELD_LEN = 1000  # aman di bawah limit 1024 karakter per field embed

    def __init__(self, bot):
        self.bot = bot
        self.CHANNEL_ID = 1540754204161736915  # ID Channel tujuan panel staff
        self.message_ids = {}          # role_id -> message_id
        self.summary_message_id = None  # message_id untuk panel ringkasan
        self.update_directory.start()

    def cog_unload(self):
        self.update_directory.cancel()

    # ------------------------------------------------------------------ #
    # Helper
    # ------------------------------------------------------------------ #

    def get_status_info(self, member: discord.Member):
        emoji, label = self.STATUS_MAP.get(member.status, ("⚪", "Offline"))
        return f"{emoji} **{label}**"

    def sort_members(self, members):
        """Online/Idle/DND ditaruh paling atas, offline di bawah, lalu alfabet."""
        priority = {
            discord.Status.online: 0,
            discord.Status.idle: 1,
            discord.Status.dnd: 1,
            discord.Status.offline: 2,
            discord.Status.invisible: 2,
        }
        return sorted(
            members,
            key=lambda m: (priority.get(m.status, 2), m.display_name.lower()),
        )

    def chunk_member_lines(self, lines):
        """Pecah daftar member jadi beberapa field kalau kepanjangan
        (limit Discord: 1024 karakter per field)."""
        chunks, current, length = [], [], 0
        for line in lines:
            if length + len(line) + 1 > self.MAX_FIELD_LEN:
                chunks.append(current)
                current, length = [], 0
            current.append(line)
            length += len(line) + 1
        if current:
            chunks.append(current)
        return chunks or [["*(Belum ada staff terdaftar)*"]]

    # ------------------------------------------------------------------ #
    # Embed builders
    # ------------------------------------------------------------------ #

    async def generate_role_embed(self, guild: discord.Guild, role_info: dict):
        role = guild.get_role(role_info["role_id"])
        members = self.sort_members(role.members) if role else []
        online_count = sum(1 for m in members if m.status != discord.Status.offline)
        total_count = len(members)

        embed = discord.Embed(
            color=role_info.get("color", discord.Color.blue()),
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_author(
            name=f"{role_info['emoji']} {role_info['name']} (Staff)",
            icon_url=guild.icon.url if guild.icon else None,
        )

        lines = [
            f"• {m.mention}  |  `{m.display_name}`  ⎯  {self.get_status_info(m)}"
            for m in members
        ]

        chunks = self.chunk_member_lines(lines)
        for i, chunk in enumerate(chunks):
            field_name = "Daftar Staff" if i == 0 else "\u200b"
            embed.add_field(name=field_name, value="\n".join(chunk), inline=False)

        embed.set_footer(
            text=(
                f"nanZ Server | {role_info['name']} • "
                f"Total: {total_count} • Aktif: {online_count}"
            ),
            icon_url=guild.icon.url if guild.icon else None,
        )
        return embed

    async def generate_summary_embed(self, guild: discord.Guild):
        """Panel ringkasan di paling atas: total staff & yang lagi online."""
        embed = discord.Embed(
            title="📋 Ringkasan Staff Directory",
            color=discord.Color.dark_theme(),
            timestamp=datetime.now(timezone.utc),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        total_all, online_all = 0, 0
        for item in self.HIERARCHY:
            role = guild.get_role(item["role_id"])
            members = role.members if role else []
            online = sum(1 for m in members if m.status != discord.Status.offline)
            total_all += len(members)
            online_all += online
            embed.add_field(
                name=f"{item['emoji']} {item['name']}",
                value=f"👥 {len(members)} total\n🟢 {online} aktif",
                inline=True,
            )

        embed.description = (
            f"**Total Seluruh Staff:** `{total_all}`  |  **Sedang Aktif:** `{online_all}`"
        )
        embed.set_footer(text="Panel ini update otomatis setiap 3 menit")
        return embed

    # ------------------------------------------------------------------ #
    # Core refresh logic
    # ------------------------------------------------------------------ #

    async def _send_or_edit(self, channel, key_store: dict, key, embed, match_text=None):
        """Utility untuk edit pesan kalau ada, atau kirim baru + simpan ID."""
        msg_id = key_store.get(key)
        try:
            if msg_id:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed)
                return
        except discord.NotFound:
            pass
        except discord.HTTPException as e:
            print(f"Gagal edit pesan untuk {key}: {e}")

        # Coba cari pesan lama di history sebelum kirim baru (hindari duplikat)
        if match_text:
            async for message in channel.history(limit=50):
                if (
                    message.author == self.bot.user
                    and message.embeds
                    and message.embeds[0].author
                    and message.embeds[0].author.name
                    and match_text in message.embeds[0].author.name
                ):
                    key_store[key] = message.id
                    await message.edit(embed=embed)
                    return

        new_msg = await channel.send(embed=embed)
        key_store[key] = new_msg.id

    async def refresh_all_panels(self, guild: discord.Guild):
        channel = self.bot.get_channel(self.CHANNEL_ID)
        if not channel:
            return

        # 1. Panel ringkasan di paling atas
        summary_embed = await self.generate_summary_embed(guild)
        summary_store = {"summary": self.summary_message_id}
        await self._send_or_edit(
            channel, summary_store, "summary", summary_embed, match_text="Ringkasan Staff Directory"
        )
        self.summary_message_id = summary_store["summary"]

        # 2. Panel per role
        for item in self.HIERARCHY:
            embed = await self.generate_role_embed(guild, item)
            try:
                await self._send_or_edit(
                    channel, self.message_ids, item["role_id"], embed, match_text=item["name"]
                )
            except Exception as e:
                print(f"Gagal update panel {item['name']}: {e}")

    # ------------------------------------------------------------------ #
    # Loop & listeners
    # ------------------------------------------------------------------ #

    @tasks.loop(minutes=3)
    async def update_directory(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.CHANNEL_ID)
        if channel:
            await self.refresh_all_panels(channel.guild)

    @update_directory.before_loop
    async def before_update_directory(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # Refresh kalau role berubah ATAU status online/offline berubah
        if before.roles != after.roles or before.status != after.status:
            channel = self.bot.get_channel(self.CHANNEL_ID)
            if channel:
                await self.refresh_all_panels(after.guild)

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        if before.status != after.status:
            channel = self.bot.get_channel(self.CHANNEL_ID)
            if channel:
                await self.refresh_all_panels(after.guild)

    # ------------------------------------------------------------------ #
    # Commands
    # ------------------------------------------------------------------ #

    @commands.command(name="setupdirectory")
    @commands.has_permissions(administrator=True)
    async def setup_directory(self, ctx: commands.Context):
        """Membuat panel staff directory baru di channel ini (reset semua panel lama)."""
        self.CHANNEL_ID = ctx.channel.id
        self.message_ids = {}
        self.summary_message_id = None
        await ctx.message.delete()

        summary_embed = await self.generate_summary_embed(ctx.guild)
        summary_msg = await ctx.send(embed=summary_embed)
        self.summary_message_id = summary_msg.id

        for item in self.HIERARCHY:
            embed = await self.generate_role_embed(ctx.guild, item)
            msg = await ctx.send(embed=embed)
            self.message_ids[item["role_id"]] = msg.id

    @commands.command(name="syncdirectory")
    @commands.has_permissions(administrator=True)
    async def sync_directory(self, ctx: commands.Context):
        """Paksa refresh semua panel staff directory sekarang juga."""
        await ctx.message.delete()
        await self.refresh_all_panels(ctx.guild)
        confirm = await ctx.send("✅ Staff directory berhasil disinkronkan.")
        await confirm.delete(delay=4)


async def setup(bot):
    await bot.add_cog(StaffDirectory(bot))