import asyncio
import logging

import discord
from discord.ext import commands, tasks


# ============================================================
# CONFIG
# ============================================================

NZ_GUILD_ID = 1406557880475320340

# Role nZ Loyalist
NZ_LOYALIST_ROLE_ID = 1555892286704062529

# Server Tag nanZ
NZ_SERVER_TAG = "nZ"

# Delay antar operasi role agar tidak spam Discord API
SYNC_DELAY = 0.5

# Jumlah member diproses sebelum jeda tambahan
SYNC_BATCH_SIZE = 20

# Backup synchronization
PERIODIC_CHECK_MINUTES = 5


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger("nanZ.nZLoyalist")


# ============================================================
# COG
# ============================================================

class NZLoyalist(commands.Cog):
    """
    Sistem otomatis nZ Loyalist.

    Jika member menggunakan Server Tag nanZ:
        -> diberikan role nZ Loyalist

    Jika member tidak lagi menggunakan Server Tag nanZ:
        -> role nZ Loyalist dicabut

    Deteksi menggunakan:
        User.primary_guild
        Member.primary_guild
    """

    def __init__(self, bot):
        self.bot = bot

        # Lock per user supaya dua event yang datang bersamaan
        # tidak melakukan add/remove role secara bersamaan.
        self._user_locks = {}

        self._startup_task = None
        self._periodic_task = None

        logger.info("[nZ Loyalist] Cog loaded.")

    # ========================================================
    # LOCK
    # ========================================================

    def get_user_lock(self, user_id: int):
        lock = self._user_locks.get(user_id)

        if lock is None:
            lock = asyncio.Lock()
            self._user_locks[user_id] = lock

        return lock

    # ========================================================
    # GUILD
    # ========================================================

    def get_nanz_guild(self):
        guild = self.bot.get_guild(NZ_GUILD_ID)

        if guild is None:
            logger.warning(
                "[nZ Loyalist] Guild nanZ tidak ditemukan: %s",
                NZ_GUILD_ID
            )

        return guild

    # ========================================================
    # ROLE
    # ========================================================

    def get_loyalist_role(self, guild: discord.Guild):
        role = guild.get_role(NZ_LOYALIST_ROLE_ID)

        if role is None:
            logger.error(
                "[nZ Loyalist] Role nZ Loyalist tidak ditemukan: %s",
                NZ_LOYALIST_ROLE_ID
            )

        return role

    # ========================================================
    # PRIMARY GUILD DATA
    # ========================================================

    def get_primary_guild_data(self, user):
        """
        Mengambil informasi Server Tag dari User.primary_guild.

        Return:
            identity_guild_id
            identity_enabled
            tag
        """

        primary_guild = getattr(user, "primary_guild", None)

        if primary_guild is None:
            return None, False, None

        identity_guild_id = getattr(
            primary_guild,
            "identity_guild_id",
            None
        )

        identity_enabled = getattr(
            primary_guild,
            "identity_enabled",
            False
        )

        tag = getattr(
            primary_guild,
            "tag",
            None
        )

        return (
            identity_guild_id,
            identity_enabled,
            tag
        )

    # ========================================================
    # DEBUG / DETECTION
    # ========================================================

    def has_nz_server_tag(self, user, log_debug=True):
        """
        Mengecek apakah user sedang menggunakan
        Server Tag nZ milik nanZ.
        """

        (
            identity_guild_id,
            identity_enabled,
            tag
        ) = self.get_primary_guild_data(user)

        if log_debug:
            logger.info(
                "[nZ Loyalist] DEBUG | %s (%s) | "
                "identity_guild_id=%r | "
                "identity_enabled=%r | "
                "tag=%r",
                getattr(user, "name", "Unknown"),
                user.id,
                identity_guild_id,
                identity_enabled,
                tag
            )

        if identity_guild_id != NZ_GUILD_ID:
            return False

        if identity_enabled is not True:
            return False

        if tag != NZ_SERVER_TAG:
            return False

        return True

    # ========================================================
    # ROLE PERMISSION
    # ========================================================

    def can_manage_role(
        self,
        guild: discord.Guild,
        role: discord.Role
    ):
        """
        Memastikan bot bisa mengelola role nZ Loyalist.
        """

        me = guild.me

        if me is None:
            logger.error(
                "[nZ Loyalist] Bot member tidak ditemukan."
            )
            return False

        if role.is_default():
            logger.error(
                "[nZ Loyalist] Role target adalah @everyone."
            )
            return False

        if role.managed:
            logger.error(
                "[nZ Loyalist] Role target adalah managed role."
            )
            return False

        if not me.guild_permissions.manage_roles:
            logger.error(
                "[nZ Loyalist] Bot tidak memiliki permission Manage Roles."
            )
            return False

        if me.top_role <= role:
            logger.error(
                "[nZ Loyalist] Role nZ Loyalist berada di atas "
                "atau sama dengan role tertinggi bot. "
                "Top bot role=%s | Target=%s",
                me.top_role.name,
                role.name
            )
            return False

        return True

    # ========================================================
    # ADD ROLE
    # ========================================================

    async def add_loyalist_role(
        self,
        member: discord.Member,
        role: discord.Role
    ):
        if role in member.roles:
            logger.info(
                "[nZ Loyalist] %s (%s) sudah memiliki role nZ Loyalist.",
                member,
                member.id
            )
            return

        if not self.can_manage_role(member.guild, role):
            return

        try:
            await member.add_roles(
                role,
                reason="Menggunakan Server Tag nanZ (nZ)"
            )

            logger.info(
                "[nZ Loyalist] ROLE DIBERIKAN | %s (%s) | Role=%s (%s)",
                member,
                member.id,
                role.name,
                role.id
            )

        except discord.Forbidden:
            logger.exception(
                "[nZ Loyalist] Gagal memberikan role kepada %s: "
                "Discord menolak permission.",
                member
            )

        except discord.HTTPException as e:
            logger.exception(
                "[nZ Loyalist] HTTP error saat memberikan role "
                "kepada %s: %s",
                member,
                e
            )

    # ========================================================
    # REMOVE ROLE
    # ========================================================

    async def remove_loyalist_role(
        self,
        member: discord.Member,
        role: discord.Role
    ):
        if role not in member.roles:
            return

        if not self.can_manage_role(member.guild, role):
            return

        try:
            await member.remove_roles(
                role,
                reason="Tidak lagi menggunakan Server Tag nanZ (nZ)"
            )

            logger.info(
                "[nZ Loyalist] ROLE DICABUT | %s (%s) | Role=%s (%s)",
                member,
                member.id,
                role.name,
                role.id
            )

        except discord.Forbidden:
            logger.exception(
                "[nZ Loyalist] Gagal mencabut role dari %s: "
                "Discord menolak permission.",
                member
            )

        except discord.HTTPException as e:
            logger.exception(
                "[nZ Loyalist] HTTP error saat mencabut role "
                "dari %s: %s",
                member,
                e
            )

    # ========================================================
    # SYNC MEMBER
    # ========================================================

    async def sync_member(
        self,
        member: discord.Member,
        user_override=None
    ):
        """
        Sinkronisasi satu member.

        nZ Tag aktif:
            role harus ADA

        nZ Tag tidak aktif:
            role harus TIDAK ADA
        """

        if member.guild.id != NZ_GUILD_ID:
            return

        if member.bot:
            return

        lock = self.get_user_lock(member.id)

        async with lock:
            guild = member.guild
            role = self.get_loyalist_role(guild)

            if role is None:
                return

            user = user_override or member

            has_tag = self.has_nz_server_tag(
                user,
                log_debug=True
            )

            has_role = role in member.roles

            logger.info(
                "[nZ Loyalist] SYNC | %s (%s) | "
                "nZ Tag=%s | Role=%s",
                member,
                member.id,
                has_tag,
                has_role
            )

            # =================================================
            # TAG AKTIF -> ADD ROLE
            # =================================================

            if has_tag:
                if not has_role:
                    await self.add_loyalist_role(
                        member,
                        role
                    )

            # =================================================
            # TAG TIDAK AKTIF -> REMOVE ROLE
            # =================================================

            else:
                if has_role:
                    await self.remove_loyalist_role(
                        member,
                        role
                    )

    # ========================================================
    # USER UPDATE
    # ========================================================

    @commands.Cog.listener()
    async def on_user_update(
        self,
        before: discord.User,
        after: discord.User
    ):
        """
        Dipanggil ketika data user berubah,
        termasuk perubahan Primary Guild / Server Tag.
        """

        before_primary = getattr(
            before,
            "primary_guild",
            None
        )

        after_primary = getattr(
            after,
            "primary_guild",
            None
        )

        if before_primary == after_primary:
            return

        logger.info(
            "[nZ Loyalist] Primary Guild berubah | %s (%s)",
            after.name,
            after.id
        )

        # Pastikan user memang member nanZ
        guild = self.get_nanz_guild()

        if guild is None:
            return

        member = guild.get_member(after.id)

        if member is None:
            return

        await self.sync_member(
            member,
            user_override=after
        )

    # ========================================================
    # MEMBER UPDATE
    # ========================================================

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before: discord.Member,
        after: discord.Member
    ):
        """
        Backup listener untuk perubahan Primary Guild
        pada Member.
        """

        if after.guild.id != NZ_GUILD_ID:
            return

        before_primary = getattr(
            before,
            "primary_guild",
            None
        )

        after_primary = getattr(
            after,
            "primary_guild",
            None
        )

        if before_primary == after_primary:
            return

        logger.info(
            "[nZ Loyalist] Member primary guild berubah | %s (%s)",
            after.name,
            after.id
        )

        await self.sync_member(
            after,
            user_override=after
        )

    # ========================================================
    # MEMBER JOIN
    # ========================================================

    @commands.Cog.listener()
    async def on_member_join(
        self,
        member: discord.Member
    ):
        if member.guild.id != NZ_GUILD_ID:
            return

        if member.bot:
            return

        logger.info(
            "[nZ Loyalist] Member baru masuk | %s (%s)",
            member,
            member.id
        )

        # Beri sedikit waktu agar data member stabil
        await asyncio.sleep(1)

        await self.sync_member(member)

    # ========================================================
    # STARTUP SYNC
    # ========================================================

    async def startup_sync(self):
        """
        Sinkronisasi seluruh member setelah bot online.
        """

        await self.bot.wait_until_ready()

        logger.info(
            "[nZ Loyalist] Memulai startup synchronization."
        )

        guild = self.get_nanz_guild()

        if guild is None:
            logger.error(
                "[nZ Loyalist] Startup sync gagal: "
                "guild tidak ditemukan."
            )
            return

        role = self.get_loyalist_role(guild)

        if role is None:
            return

        logger.info(
            "[nZ Loyalist] Sync guild: %s (%s)",
            guild.name,
            guild.id
        )

        # ----------------------------------------------------
        # Ambil member cache
        # ----------------------------------------------------

        members = list(guild.members)

        logger.info(
            "[nZ Loyalist] Member cache: %s member.",
            len(members)
        )

        # ----------------------------------------------------
        # Jika cache kosong, coba fetch members
        # ----------------------------------------------------

        if not members:
            try:
                members = []

                async for member in guild.fetch_members(
                    limit=None
                ):
                    members.append(member)

                logger.info(
                    "[nZ Loyalist] Fetch members selesai: %s member.",
                    len(members)
                )

            except discord.HTTPException as e:
                logger.exception(
                    "[nZ Loyalist] Gagal fetch members: %s",
                    e
                )
                return

        # ----------------------------------------------------
        # Sinkronisasi
        # ----------------------------------------------------

        processed = 0

        for member in members:

            if member.bot:
                continue

            try:
                await self.sync_member(member)

            except Exception:
                logger.exception(
                    "[nZ Loyalist] Error sync member %s (%s)",
                    member,
                    member.id
                )

            processed += 1

            # Delay kecil untuk menghindari spam API
            await asyncio.sleep(SYNC_DELAY)

            # Jeda tambahan setiap batch
            if processed % SYNC_BATCH_SIZE == 0:
                await asyncio.sleep(2)

        logger.info(
            "[nZ Loyalist] Startup synchronization selesai."
        )

    # ========================================================
    # PERIODIC BACKUP
    # ========================================================

    @tasks.loop(minutes=PERIODIC_CHECK_MINUTES)
    async def periodic_sync(self):
        """
        Backup check.

        Hanya memeriksa member yang sudah memiliki
        nZ Loyalist agar tidak melakukan request
        besar-besaran setiap 5 menit.
        """

        guild = self.get_nanz_guild()

        if guild is None:
            return

        role = self.get_loyalist_role(guild)

        if role is None:
            return

        logger.info(
            "[nZ Loyalist] Backup synchronization dimulai."
        )

        count = 0

        for member in list(guild.members):

            if member.bot:
                continue

            # Hanya cek member yang sudah memiliki role.
            # Tujuannya mendeteksi tag yang sudah dilepas.
            if role not in member.roles:
                continue

            try:
                await self.sync_member(member)

            except Exception:
                logger.exception(
                    "[nZ Loyalist] Error backup sync %s (%s)",
                    member,
                    member.id
                )

            count += 1

            await asyncio.sleep(SYNC_DELAY)

        logger.info(
            "[nZ Loyalist] Backup synchronization selesai. "
            "Diperiksa: %s member.",
            count
        )

    @periodic_sync.before_loop
    async def before_periodic_sync(self):
        await self.bot.wait_until_ready()

    # ========================================================
    # LOOP ERROR HANDLER
    # ========================================================

    @periodic_sync.error
    async def periodic_sync_error(self, error):
        logger.exception(
            "[nZ Loyalist] Periodic synchronization error: %s",
            error
        )

    # ========================================================
    # COG LOAD
    # ========================================================

    async def cog_load(self):
        self._startup_task = asyncio.create_task(
            self.startup_sync()
        )

        if not self.periodic_sync.is_running():
            self.periodic_sync.start()

    # ========================================================
    # COG UNLOAD
    # ========================================================

    async def cog_unload(self):
        if self._startup_task is not None:
            self._startup_task.cancel()

        self.periodic_sync.cancel()

        self._user_locks.clear()

        logger.info(
            "[nZ Loyalist] Cog unloaded."
        )


# ============================================================
# SETUP
# ============================================================

async def setup(bot):
    await bot.add_cog(
        NZLoyalist(bot)
    )