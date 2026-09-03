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

        # ID message panel
        self.message_ids = {
            role["role_id"]: None
            for role in self.STAFF_ROLES
        }

        # Database aktivitas
        self.activity_file = "staff_activity.json"
        self.activity_data = self.load_activity()

        self.update_directory.start()

    # ==========================================
    # ACTIVITY DATABASE
    # ==========================================

    def load_activity(self):

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
                f"Gagal load database: {e}"
            )

            return {}

    def save_activity(self):

        try:

            with open(
                self.activity_file,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    self.activity_data,
                    f,
                    indent=4
                )

        except Exception as e:

            print(
                f"[STAFF DIRECTORY] "
                f"Gagal save database: {e}"
            )

    def update_activity(self, member_id):

        timestamp = int(
            datetime.now(
                timezone.utc
            ).timestamp()
        )

        self.activity_data[str(member_id)] = timestamp

        self.save_activity()

    # ==========================================
    # ACTIVITY TEXT
    # ==========================================

    def get_activity(self, member):

        timestamp = self.activity_data.get(
            str(member.id)
        )

        # Kalau belum pernah terdeteksi
        if not timestamp:

            # Buat timestamp sekarang
            self.update_activity(member.id)

            timestamp = self.activity_data[
                str(member.id)
            ]

        return f"🕐 Aktif <t:{timestamp}:R>"

    # ==========================================
    # GENERATE EMBED
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

        # Sort berdasarkan nama
        members = sorted(
            role.members,
            key=lambda m: m.display_name.lower()
        )

        # ======================================
        # TIDAK ADA STAFF
        # ======================================

        if not members:

            embed.description = (
                "*Belum ada staff pada role ini.*"
            )

        # ======================================
        # ADA STAFF
        # ======================================

        else:

            staff_list = []

            for member in members:

                activity = self.get_activity(
                    member
                )

                # TAG STAFF
                staff_info = (
                    f"👤 {member.mention}\n"
                    f"   └ {activity}"
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
    # REFRESH ALL PANEL
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
                # EDIT MESSAGE LAMA
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

                # ==================================
                # CARI MESSAGE LAMA
                # ==================================

                found = None

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

                            found = message
                            break

                # ==================================
                # UPDATE MESSAGE
                # ==================================

                if found:

                    self.message_ids[
                        role_id
                    ] = found.id

                    await found.edit(
                        embed=embed
                    )

                # ==================================
                # BUAT MESSAGE BARU
                # ==================================

                else:

                    message = await channel.send(
                        embed=embed
                    )

                    self.message_ids[
                        role_id
                    ] = message.id

            except Exception as e:

                print(
                    f"[STAFF DIRECTORY] "
                    f"{role_info['name']}: {e}"
                )

    # ==========================================
    # DETEKSI PESAN STAFF
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

        # Apakah dia staff?
        is_staff = any(
            role.id in self.message_ids
            for role in member.roles
        )

        if not is_staff:
            return

        # Update aktivitas
        self.update_activity(
            member.id
        )

    # ==========================================
    # DETEKSI PRESENCE
    # ==========================================

    @commands.Cog.listener()
    async def on_presence_update(
        self,
        before,
        after
    ):

        # Apakah staff?
        is_staff = any(
            role.id in self.message_ids
            for role in after.roles
        )

        if not is_staff:
            return

        # Update aktivitas
        self.update_activity(
            after.id
        )

    # ==========================================
    # ROLE UPDATE
    # ==========================================

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before,
        after
    ):

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