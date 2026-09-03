import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone
import json
import os


class StaffDirectory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Channel directory
        self.CHANNEL_ID = 1540754204161736915

        # Role staff
        self.STAFF_ROLES = [
            {
                "role_id": 1417582562100117584,
                "name": "Guru Besar",
                "emoji": "👑"
            },
            {
                "role_id": 1453103644244316343,
                "name": "Moderator",
                "emoji": "🛡️"
            },
            {
                "role_id": 1467360501745844446,
                "name": "Pembina OSIS",
                "emoji": "📚"
            },
            {
                "role_id": 1427276194876751902,
                "name": "OSIS",
                "emoji": "✍️"
            }
        ]

        # ID message masing-masing role
        self.message_ids = {
            role["role_id"]: None
            for role in self.STAFF_ROLES
        }

        # File penyimpanan aktivitas
        self.activity_file = "staff_activity.json"

        self.activity_data = self.load_activity()

        self.update_directory.start()

    # =========================================================
    # ACTIVITY DATABASE
    # =========================================================

    def load_activity(self):
        """Load data aktivitas staff dari JSON."""

        if not os.path.exists(self.activity_file):
            return {}

        try:
            with open(self.activity_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[STAFF DIRECTORY] Gagal membaca activity data: {e}")
            return {}

    def save_activity(self):
        """Simpan aktivitas staff ke JSON."""

        try:
            with open(self.activity_file, "w", encoding="utf-8") as f:
                json.dump(
                    self.activity_data,
                    f,
                    indent=4,
                    ensure_ascii=False
                )
        except Exception as e:
            print(f"[STAFF DIRECTORY] Gagal menyimpan activity data: {e}")

    def update_activity(self, member_id):
        """Update waktu aktivitas staff."""

        timestamp = int(datetime.now(timezone.utc).timestamp())

        old_timestamp = self.activity_data.get(str(member_id))

        # Jangan tulis file kalau waktunya belum berubah
        if old_timestamp != timestamp:
            self.activity_data[str(member_id)] = timestamp

            # Simpan
            self.save_activity()

    def get_activity_text(self, member):
        """Menghasilkan tulisan aktivitas staff."""

        timestamp = self.activity_data.get(str(member.id))

        if timestamp:
            return f"Aktif <t:{timestamp}:R>"

        return "Aktivitas belum terdeteksi"

    # =========================================================
    # ROLE EMBED
    # =========================================================

    async def generate_role_embed(self, guild, role_info):

        role = guild.get_role(role_info["role_id"])

        embed = discord.Embed(
            color=discord.Color.blue()
        )

        if not role:
            embed.description = "⚠️ Role tidak ditemukan."
            return embed

        members = sorted(
            role.members,
            key=lambda m: m.display_name.lower()
        )

        if not members:
            embed.description = "*(Belum ada staff terdaftar)*"

        else:

            staff_list = []

            for member in members:

                activity = self.get_activity_text(member)

                staff_block = (
                    f"**{member.display_name}**\n"
                    f"└ {activity}"
                )

                staff_list.append(staff_block)

            embed.description = "\n\n".join(staff_list)

        # Header
        embed.set_author(
            name=f"{role_info['emoji']} {role_info['name']}",
            icon_url=(
                guild.icon.url
                if guild.icon
                else discord.Embed.Empty
            )
        )

        # Footer
        embed.set_footer(
            text=f"nanZ Server • {role_info['name']} • {len(members)} Staff",
            icon_url=(
                guild.icon.url
                if guild.icon
                else discord.Embed.Empty
            )
        )

        return embed

    # =========================================================
    # REFRESH PANEL
    # =========================================================

    async def refresh_all_panels(self, guild):

        channel = self.bot.get_channel(self.CHANNEL_ID)

        if not channel:
            print("[STAFF DIRECTORY] Channel tidak ditemukan.")
            return

        for role_info in self.STAFF_ROLES:

            role_id = role_info["role_id"]

            try:

                embed = await self.generate_role_embed(
                    guild,
                    role_info
                )

                message_id = self.message_ids.get(role_id)

                # Jika sudah punya ID message
                if message_id:

                    try:
                        message = await channel.fetch_message(message_id)

                        await message.edit(
                            embed=embed
                        )

                        continue

                    except discord.NotFound:
                        # Message sudah dihapus
                        self.message_ids[role_id] = None

                    except discord.HTTPException as e:
                        print(
                            f"[STAFF DIRECTORY] "
                            f"Gagal edit {role_info['name']}: {e}"
                        )
                        continue

                # Cari message lama milik bot
                found_message = None

                async for message in channel.history(limit=100):

                    if (
                        message.author == self.bot.user
                        and message.embeds
                    ):

                        author = message.embeds[0].author

                        if author and author.name:
                            if role_info["name"] in author.name:

                                found_message = message
                                break

                if found_message:

                    self.message_ids[role_id] = found_message.id

                    await found_message.edit(
                        embed=embed
                    )

                else:

                    new_message = await channel.send(
                        embed=embed
                    )

                    self.message_ids[role_id] = new_message.id

            except Exception as e:

                print(
                    f"[STAFF DIRECTORY] "
                    f"Error {role_info['name']}: {e}"
                )

    # =========================================================
    # MEMBER ACTIVITY
    # =========================================================

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):

        # Cek apakah member adalah staff
        if not any(
            role.id in self.message_ids
            for role in after.roles
        ):
            return

        self.update_activity(after.id)

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        member = message.author

        # Harus member Discord
        if not isinstance(member, discord.Member):
            return

        # Cek apakah dia staff
        is_staff = any(
            role.id in self.message_ids
            for role in member.roles
        )

        if not is_staff:
            return

        self.update_activity(member.id)

    # =========================================================
    # ROLE UPDATE
    # =========================================================

    @commands.Cog.listener()
    async def on_member_update(self, before, after):

        # Hanya refresh kalau role berubah
        if before.roles != after.roles:

            channel = self.bot.get_channel(
                self.CHANNEL_ID
            )

            if channel:
                await self.refresh_all_panels(
                    after.guild
                )

    # =========================================================
    # AUTO UPDATE
    # =========================================================

    @tasks.loop(minutes=10)
    async def update_directory(self):

        await self.bot.wait_until_ready()

        channel = self.bot.get_channel(
            self.CHANNEL_ID
        )

        if not channel:
            return

        await self.refresh_all_panels(
            channel.guild
        )

    @update_directory.before_loop
    async def before_update_directory(self):

        await self.bot.wait_until_ready()

    # =========================================================
    # SETUP COMMAND
    # =========================================================

    @commands.command(name="setupdirectory")
    @commands.has_permissions(administrator=True)
    async def setup_directory(self, ctx):

        self.CHANNEL_ID = ctx.channel.id

        try:
            await ctx.message.delete()
        except:
            pass

        # Kirim panel baru
        for role_info in self.STAFF_ROLES:

            embed = await self.generate_role_embed(
                ctx.guild,
                role_info
            )

            message = await ctx.send(
                embed=embed
            )

            self.message_ids[
                role_info["role_id"]
            ] = message.id

        print(
            "[STAFF DIRECTORY] "
            "Directory berhasil dibuat."
        )

    # =========================================================
    # UNLOAD
    # =========================================================

    def cog_unload(self):

        self.update_directory.cancel()


async def setup(bot):

    await bot.add_cog(
        StaffDirectory(bot)
    )