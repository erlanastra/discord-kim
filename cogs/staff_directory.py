import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone


class StaffDirectory(commands.Cog):
    """
    Cog untuk menampilkan panel staff, tetap terpisah per-role (1 embed = 1 role),
    tapi dengan isi panel yang lebih rapi:
    - Member dikelompokkan per status (🟢 Online / 🌙 Idle / ⛔ DND / ⚪ Offline)
      sebagai field terpisah, jadi enak dibaca dan langsung kelihatan siapa aktif
    - Warna embed beda per role
    - Nomor urut + nama staff rapi dalam satu kolom
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
        self.message_ids = {}  # role_id -> message_id
        self.update_directory.start()

    def cog_unload(self):
        self.update_directory.cancel()

    # ------------------------------------------------------------------ #
    # Helper
    # ------------------------------------------------------------------ #

    def get_status_info(self, member: discord.Member):
        emoji, label = self.STATUS_MAP.get(member.status, ("⚪", "Offline"))
        return emoji, label

    def group_by_status(self, members):
        """Kelompokkan member ke 4 kategori status, urut alfabet di tiap grup."""
        groups = {"Online": [], "Idle": [], "Do Not Disturb": [], "Offline": []}
        for m in sorted(members, key=lambda m: m.display_name.lower()):
            _, label = self.get_status_info(m)
            groups[label].append(m)
        return groups

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
        return chunks

    # ------------------------------------------------------------------ #
    # Embed builders
    # ------------------------------------------------------------------ #

    async def generate_role_embed(self, guild: discord.Guild, role_info: dict):
        role = guild.get_role(role_info["role_id"])
        members = role.members if role else []
        total_count = len(members)
        online_count = sum(1 for m in members if m.status != discord.Status.offline)

        embed = discord.Embed(
            color=role_info.get("color", discord.Color.blue()),
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_author(
            name=f"{role_info['emoji']} {role_info['name']} (Staff)",
            icon_url=guild.icon.url if guild.icon else None,
        )
        embed.description = (
            f"👥 **Total Staff:** `{total_count}`  •  🟢 **Sedang Aktif:** `{online_count}`"
        )

        if total_count == 0:
            embed.add_field(name="\u200b", value="*(Belum ada staff terdaftar)*", inline=False)
        else:
            groups = self.group_by_status(members)
            group_order = [
                ("Online", "🟢"),
                ("Idle", "🌙"),
                ("Do Not Disturb", "⛔"),
                ("Offline", "⚪"),
            ]
            counter = 0
            for label, emoji in group_order:
                bucket = groups[label]
                if not bucket:
                    continue

                lines = []
                for m in bucket:
                    counter += 1
                    lines.append(f"`{counter:02d}.` {m.mention} — **{m.display_name}**")

                for chunk_i, chunk in enumerate(self.chunk_member_lines(lines)):
                    field_name = f"{emoji} {label} ({len(bucket)})" if chunk_i == 0 else "\u200b"
                    embed.add_field(name=field_name, value="\n".join(chunk), inline=False)

        embed.set_footer(
            text=f"nanZ Server | {role_info['name']} • Terakhir diperbarui",
            icon_url=guild.icon.url if guild.icon else None,
        )
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
        await ctx.message.delete()

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