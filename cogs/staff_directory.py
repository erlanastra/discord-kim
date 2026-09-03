import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone
import json
import os


class StaffDirectory(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # ==========================================
        # CONFIG
        # ==========================================

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

        # ID pesan masing-masing role
        self.message_ids = {
            role["role_id"]: None
            for role in self.STAFF_ROLES
        }

        # Database aktivitas
        self.activity_file = "staff_activity.json"
        self.activity_data = self.load_activity()

        self.update_directory.start()

    # ==========================================
    # LOAD ACTIVITY
    # ==========================================

    def load_activity(self):
        """Membaca database aktivitas staff."""

        if not os.path.exists(self.activity_file):
            return {}

        try:
            with open(
                self.activity_file,
                "r",
                encoding="utf-8"
            ) as f:
                return json.load(f)

        except Exception as e:
            print(
                f"[STAFF DIRECTORY] "
                f"Gagal membaca activity data: {e}"
            )
            return {}

    # ==========================================
    # SAVE ACTIVITY
    # ==========================================

    def save_activity(self):
        """Menyimpan database aktivitas staff."""

        try:
            with open(
                self.activity_file,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    self.activity_data,
                    f,
                    indent=4,
                    ensure_ascii=False
                )

        except Exception as e:
            print(
                f"[STAFF DIRECTORY] "
                f"Gagal menyimpan activity data: {e}"
            )

    # ==========================================
    # UPDATE LAST ACTIVE
    # ==========================================

    def update_activity(self, member_id):

        timestamp = int(
            datetime.now(
                timezone.utc
            ).timestamp()
        )

        self.activity_data[str(member_id)] = timestamp

        self.save_activity()

    # ==========================================
    # GET STAFF STATUS
    # ==========================================

    def get_activity_status(self, member):

        timestamp = self.activity_data.get(
            str(member.id)
        )

        # ======================================
        # STAFF SEDANG AKTIF
        # ======================================

        if member.status != discord.Status.offline:

            # Kalau belum ada data sebelumnya,
            # simpan waktu sekarang.
            if not timestamp:

                timestamp = int(
                    datetime.now(
                        timezone.utc
                    ).timestamp()
                )

                self.activity_data[
                    str(member.id)
                ] = timestamp

                self.save_activity()

            return "🟢 **Aktif**"

        # ======================================
        # STAFF SUDAH OFFLINE
        # ======================================

        if timestamp:

            return (
                f"⚪ **Aktif <t:{timestamp}:R>**"
            )

        # ======================================
        # BELUM ADA DATA
        # ======================================

        return "⚪ **Belum terdeteksi**"

    # ==========================================
    # GENERATE ROLE EMBED
    # ==========================================

    async def generate_role_embed(
        self,
        guild,
        role_info
    ):

        role = guild.get_role(
            role_info["role_id"]
        )

        embed = discord.Embed(
            color=discord.Color.blue()
        )

        # Role tidak ditemukan
        if not role:

            embed.description = (
                "⚠️ Role tidak ditemukan."
            )

            return embed

        # Urutkan berdasarkan nama
        members = sorted(
            role.members,
            key=lambda m: m.display_name.lower()
        )

        # ======================================
        # TIDAK ADA STAFF
        # ======================================

        if not members:

            embed.description = (
                "*Belum ada staff terdaftar.*"
            )

        # ======================================
        # ADA STAFF
        # ======================================

        else:

            staff_list = []

            for member in members:

                status = self.get_activity_status(
                    member
                )

                # Mention staff
                staff_info = (
                    f"👤 {member.mention}\n"
                    f"   └ {status}"
                )

                staff_list.append(
                    staff_info
                )

            embed.description = (
                "\n\n".join(staff_list)
            )

        # ======================================
        # HEADER
        # ======================================

        embed.set_author(
            name=(
                f"{role_info['emoji']} "
                f"{role_info['name']}"
            ),
            icon_url=(
                guild.icon.url
                if guild.icon
                else discord.Embed.Empty
            )
        )

        # ======================================
        # FOOTER
        # ======================================

        embed.set_footer(
            text=(
                f"nanZ Server • "
                f"{role_info['name']} • "
                f"{len(members)} Staff"
            )
        )

        return embed

    # ==========================================
    # REFRESH ALL PANELS
    # ==========================================

    async def refresh_all_panels(self, guild):

        channel = self.bot.get_channel(
            self.CHANNEL_ID
        )

        if not channel:
            print(
                "[STAFF DIRECTORY] "
                "Channel tidak ditemukan."
            )
            return

        for role_info in self.STAFF_ROLES:

            role_id = role_info["role_id"]

            try:

                embed = await self.generate_role_embed(
                    guild,
                    role_info
                )

                message_id = self.message_ids.get(
                    role_id
                )

                # ==================================
                # EDIT MESSAGE YANG SUDAH ADA
                # ==================================

                if message_id:

                    try:

                        message = await channel.fetch_message(
                            message_id
                        )

                        await message.edit(
                            embed=embed
                        )

                        continue

                    except discord.NotFound:

                        self.message_ids[
                            role_id
                        ] = None

                    except discord.HTTPException as e:

                        print(
                            f"[STAFF DIRECTORY] "
                            f"Gagal edit "
                            f"{role_info['name']}: {e}"
                        )

                        continue

                # ==================================
                # CARI MESSAGE BOT LAMA
                # ==================================

                found_message = None

                async for message in channel.history(
                    limit=100
                ):

                    if (
                        message.author == self.bot.user
                        and message.embeds
                    ):

                        author = message.embeds[
                            0
                        ].author

                        if (
                            author
                            and author.name
                            and role_info["name"]
                            in author.name
                        ):

                            found_message = message
                            break

                # ==================================
                # UPDATE MESSAGE LAMA
                # ==================================

                if found_message:

                    self.message_ids[
                        role_id
                    ] = found_message.id

                    await found_message.edit(
                        embed=embed
                    )

                # ==================================
                # BUAT MESSAGE BARU
                # ==================================

                else:

                    new_message = await channel.send(
                        embed=embed
                    )

                    self.message_ids[
                        role_id
                    ] = new_message.id

            except Exception as e:

                print(
                    f"[STAFF DIRECTORY] "
                    f"Error {role_info['name']}: {e}"
                )

    # ==========================================
    # STAFF MENGIRIM PESAN
    # ==========================================

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        if not isinstance(
            message.author,
            discord.Member
        ):
            return

        member = message.author

        # Cek apakah member adalah staff
        is_staff = any(
            role.id in self.message_ids
            for role in member.roles
        )

        if not is_staff:
            return

        # Simpan aktivitas terakhir
        self.update_activity(
            member.id
        )

    # ==========================================
    # STAFF ONLINE / OFFLINE
    # ==========================================

    @commands.Cog.listener()
    async def on_presence_update(
        self,
        before,
        after
    ):

        # Cek apakah staff
        is_staff = any(
            role.id in self.message_ids
            for role in after.roles
        )

        if not is_staff:
            return

        # Kalau status berubah menjadi aktif,
        # update waktu aktivitas terakhir.
        if (
            before.status == discord.Status.offline
            and after.status != discord.Status.offline
        ):

            self.update_activity(
                after.id
            )

            # Update panel supaya langsung
            # berubah menjadi "Aktif"
            channel = self.bot.get_channel(
                self.CHANNEL_ID
            )

            if channel:

                await self.refresh_all_panels(
                    after.guild
                )

    # ==========================================
    # ROLE STAFF BERUBAH
    # ==========================================

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before,
        after
    ):

        # Tidak ada perubahan role
        if before.roles == after.roles:
            return

        channel = self.bot.get_channel(
            self.CHANNEL_ID
        )

        if channel:

            await self.refresh_all_panels(
                after.guild
            )

    # ==========================================
    # AUTO REFRESH
    # ==========================================

    @tasks.loop(minutes=10)
    async def update_directory(self):

        await self.bot.wait_until_ready()

        channel = self.bot.get_channel(
            self.CHANNEL_ID
        )

        if channel:

            await self.refresh_all_panels(
                channel.guild
            )

    @update_directory.before_loop
    async def before_update_directory(self):

        await self.bot.wait_until_ready()

    # ==========================================
    # SETUP DIRECTORY
    # ==========================================

    @commands.command(
        name="setupdirectory"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def setup_directory(
        self,
        ctx
    ):

        self.CHANNEL_ID = ctx.channel.id

        try:
            await ctx.message.delete()
        except:
            pass

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

    # ==========================================
    # UNLOAD
    # ==========================================

    def cog_unload(self):

        self.update_directory.cancel()


async def setup(bot):

    await bot.add_cog(
        StaffDirectory(bot)
    )