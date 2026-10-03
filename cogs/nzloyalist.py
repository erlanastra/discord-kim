import asyncio
import logging

import discord
from discord.ext import commands, tasks


# ============================================================
# CONFIG
# ============================================================

NZ_GUILD_ID = 1406557880475320340

NZ_LOYALIST_ROLE_ID = 1555892286704062529

NZ_SERVER_TAG = "nZ"

SYNC_DELAY = 0.5
SYNC_BATCH_SIZE = 20
PERIODIC_CHECK_MINUTES = 5


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger("nanZ.nZLoyalist")


# ============================================================
# COG
# ============================================================

class NZLoyalist(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        self._user_locks = {}

        self._startup_task = None

        logger.info("[nZ Loyalist] Cog loaded.")

    # ========================================================
    # USER LOCK
    # ========================================================

    def get_user_lock(self, user_id: int):

        lock = self._user_locks.get(user_id)

        if lock is None:
            lock = asyncio.Lock()
            self._user_locks[user_id] = lock

        return lock

    # ========================================================
    # GET NANZ GUILD
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
    # GET LOYALIST ROLE
    # ========================================================

    def get_loyalist_role(self, guild):

        role = guild.get_role(NZ_LOYALIST_ROLE_ID)

        if role is None:
            logger.error(
                "[nZ Loyalist] Role nZ Loyalist tidak ditemukan: %s",
                NZ_LOYALIST_ROLE_ID
            )

        return role

    # ========================================================
    # GET PRIMARY GUILD
    # ========================================================

    def get_primary_guild(self, user):

        return getattr(
            user,
            "primary_guild",
            None
        )

    # ========================================================
    # GET SERVER TAG
    # ========================================================

    def get_server_tag(self, user):

        primary_guild = self.get_primary_guild(user)

        if primary_guild is None:
            return None

        tag = getattr(
            primary_guild,
            "tag",
            None
        )

        return tag

    # ========================================================
    # CHECK NZ TAG
    # ========================================================

    def has_nz_server_tag(self, user):

        primary_guild = self.get_primary_guild(user)

        if primary_guild is None:

            logger.info(
                "[nZ Loyalist] DEBUG | %s (%s) | "
                "primary_guild=None | tag=None",
                getattr(user, "name", "Unknown"),
                user.id
            )

            return False

        tag = getattr(
            primary_guild,
            "tag",
            None
        )

        identity_enabled = getattr(
            primary_guild,
            "identity_enabled",
            False
        )

        identity_guild_id = getattr(
            primary_guild,
            "identity_guild_id",
            None
        )

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

        # ====================================================
        # DETEKSI UTAMA
        # ====================================================
        #
        # Discord.py pada object yang diterima bot kita
        # tidak selalu menyediakan identity_guild_id.
        #
        # Karena itu tag menjadi indikator utama.
        #

        if identity_enabled is not True:
            return False

        if tag != NZ_SERVER_TAG:
            return False

        return True

    # ========================================================
    # CHECK ROLE PERMISSION
    # ========================================================

    def can_manage_role(
        self,
        guild,
        role
    ):

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
                "[nZ Loyalist] Bot tidak memiliki "
                "permission Manage Roles."
            )

            return False

        if me.top_role <= role:

            logger.error(
                "[nZ Loyalist] Tidak dapat mengelola role "
                "nZ Loyalist karena role berada di atas "
                "atau sama dengan role bot."
            )

            logger.error(
                "[nZ Loyalist] Bot Top Role: %s (%s)",
                me.top_role.name,
                me.top_role.id
            )

            logger.error(
                "[nZ Loyalist] Target Role: %s (%s)",
                role.name,
                role.id
            )

            return False

        return True

    # ========================================================
    # ADD ROLE
    # ========================================================

    async def add_loyalist_role(
        self,
        member,
        role
    ):

        if role in member.roles:

            logger.info(
                "[nZ Loyalist] %s (%s) sudah memiliki "
                "role nZ Loyalist.",
                member,
                member.id
            )

            return

        if not self.can_manage_role(
            member.guild,
            role
        ):
            return

        try:

            await member.add_roles(
                role,
                reason="Menggunakan Server Tag nanZ (nZ)"
            )

            logger.info(
                "[nZ Loyalist] ROLE DIBERIKAN | "
                "%s (%s) | %s (%s)",
                member,
                member.id,
                role.name,
                role.id
            )

        except discord.Forbidden:

            logger.exception(
                "[nZ Loyalist] Discord menolak pemberian "
                "role kepada %s.",
                member
            )

        except discord.HTTPException as error:

            logger.exception(
                "[nZ Loyalist] HTTP error saat memberikan "
                "role kepada %s: %s",
                member,
                error
            )

    # ========================================================
    # REMOVE ROLE
    # ========================================================

    async def remove_loyalist_role(
        self,
        member,
        role
    ):

        if role not in member.roles:
            return

        if not self.can_manage_role(
            member.guild,
            role
        ):
            return

        try:

            await member.remove_roles(
                role,
                reason="Tidak lagi menggunakan Server Tag nanZ (nZ)"
            )

            logger.info(
                "[nZ Loyalist] ROLE DICABUT | "
                "%s (%s) | %s (%s)",
                member,
                member.id,
                role.name,
                role.id
            )

        except discord.Forbidden:

            logger.exception(
                "[nZ Loyalist] Discord menolak pencabutan "
                "role dari %s.",
                member
            )

        except discord.HTTPException as error:

            logger.exception(
                "[nZ Loyalist] HTTP error saat mencabut "
                "role dari %s: %s",
                member,
                error
            )

    # ========================================================
    # SYNC MEMBER
    # ========================================================

    async def sync_member(
        self,
        member,
        user_override=None
    ):

        if member.guild.id != NZ_GUILD_ID:
            return

        if member.bot:
            return

        lock = self.get_user_lock(
            member.id
        )

        async with lock:

            guild = member.guild

            role = self.get_loyalist_role(
                guild
            )

            if role is None:
                return

            user = (
                user_override
                if user_override is not None
                else member
            )

            has_tag = self.has_nz_server_tag(
                user
            )

            has_role = role in member.roles

            logger.info(
                "[nZ Loyalist] SYNC | "
                "%s (%s) | "
                "nZ Tag=%s | "
                "Role=%s",
                member,
                member.id,
                has_tag,
                has_role
            )

            # =================================================
            # NZ TAG AKTIF
            # =================================================

            if has_tag:

                if not has_role:

                    await self.add_loyalist_role(
                        member,
                        role
                    )

            # =================================================
            # NZ TAG TIDAK AKTIF
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
        before,
        after
    ):

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
            "[nZ Loyalist] Primary Guild berubah | "
            "%s (%s)",
            after.name,
            after.id
        )

        guild = self.get_nanz_guild()

        if guild is None:
            return

        member = guild.get_member(
            after.id
        )

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
        before,
        after
    ):

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
            "[nZ Loyalist] Member primary guild berubah | "
            "%s (%s)",
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
        member
    ):

        if member.guild.id != NZ_GUILD_ID:
            return

        if member.bot:
            return

        logger.info(
            "[nZ Loyalist] Member baru masuk | "
            "%s (%s)",
            member,
            member.id
        )

        await asyncio.sleep(1)

        await self.sync_member(
            member
        )

    # ========================================================
    # STARTUP SYNC
    # ========================================================

    async def startup_sync(self):

        await self.bot.wait_until_ready()

        logger.info(
            "[nZ Loyalist] Memulai startup synchronization."
        )

        guild = self.get_nanz_guild()

        if guild is None:
            return

        role = self.get_loyalist_role(
            guild
        )

        if role is None:
            return

        logger.info(
            "[nZ Loyalist] Sync guild: %s (%s)",
            guild.name,
            guild.id
        )

        members = list(
            guild.members
        )

        logger.info(
            "[nZ Loyalist] Member cache: %s member.",
            len(members)
        )

        if not members:

            try:

                members = []

                async for member in guild.fetch_members(
                    limit=None
                ):

                    members.append(
                        member
                    )

                logger.info(
                    "[nZ Loyalist] Fetch members selesai: %s member.",
                    len(members)
                )

            except discord.HTTPException as error:

                logger.exception(
                    "[nZ Loyalist] Gagal fetch members: %s",
                    error
                )

                return

        processed = 0

        for member in members:

            if member.bot:
                continue

            try:

                await self.sync_member(
                    member
                )

            except Exception:

                logger.exception(
                    "[nZ Loyalist] Error sync "
                    "%s (%s)",
                    member,
                    member.id
                )

            processed += 1

            await asyncio.sleep(
                SYNC_DELAY
            )

            if processed % SYNC_BATCH_SIZE == 0:

                await asyncio.sleep(2)

        logger.info(
            "[nZ Loyalist] Startup synchronization selesai."
        )

    # ========================================================
    # PERIODIC BACKUP
    # ========================================================

    @tasks.loop(
        minutes=PERIODIC_CHECK_MINUTES
    )
    async def periodic_sync(self):

        guild = self.get_nanz_guild()

        if guild is None:
            return

        role = self.get_loyalist_role(
            guild
        )

        if role is None:
            return

        logger.info(
            "[nZ Loyalist] Backup synchronization dimulai."
        )

        count = 0

        for member in list(
            guild.members
        ):

            if member.bot:
                continue

            # Hanya mengecek member yang saat ini
            # memiliki role.
            #
            # Tujuan utamanya:
            # mendeteksi member yang sudah melepas nZ.

            if role not in member.roles:
                continue

            try:

                await self.sync_member(
                    member
                )

            except Exception:

                logger.exception(
                    "[nZ Loyalist] Error backup sync "
                    "%s (%s)",
                    member,
                    member.id
                )

            count += 1

            await asyncio.sleep(
                SYNC_DELAY
            )

        logger.info(
            "[nZ Loyalist] Backup synchronization selesai. "
            "Diperiksa: %s member.",
            count
        )

    # ========================================================
    # PERIODIC BEFORE LOOP
    # ========================================================

    @periodic_sync.before_loop
    async def before_periodic_sync(self):

        await self.bot.wait_until_ready()

    # ========================================================
    # PERIODIC ERROR
    # ========================================================

    @periodic_sync.error
    async def periodic_sync_error(
        self,
        error
    ):

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