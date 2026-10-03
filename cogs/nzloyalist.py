import asyncio
import logging

import discord
from discord.ext import commands, tasks


# ============================================================
# CONFIG
# ============================================================

# ============================================================
# SERVER NANZ
# ============================================================

NZ_GUILD_ID = 1406557880475320340


# ============================================================
# ROLE nZ LOYALIST
# ============================================================

NZ_LOYALIST_ROLE_ID = 1555892286704062529


# ============================================================
# SERVER TAG
# ============================================================

NZ_SERVER_TAG = "nZ"


# ============================================================
# STARTUP SYNC
# ============================================================

# Jeda antar member ketika startup sync.
# Dibuat kecil agar tidak membanjiri Discord API.
SYNC_DELAY = 0.20

# Setiap berapa member diberi jeda tambahan.
SYNC_BATCH_SIZE = 20

# Interval pengecekan ulang.
#
# Ini menjadi backup apabila event Server Tag tidak diterima
# oleh bot karena masalah gateway/cache.
#
# Tidak melakukan fetch semua user.
# Hanya melakukan pengecekan terhadap member yang sudah
# memiliki role nZ Loyalist.
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

        # Lock per user.
        #
        # Mencegah:
        # on_user_update
        # dan
        # on_member_update
        #
        # melakukan perubahan role bersamaan.
        self._user_locks = {}

        # Startup task.
        self._startup_task = None

        # Periodic backup task.
        self._periodic_task = None

    # ========================================================
    # USER LOCK
    # ========================================================

    def get_user_lock(self, user_id):
        """
        Mendapatkan lock khusus untuk user.
        """

        lock = self._user_locks.get(user_id)

        if lock is None:
            lock = asyncio.Lock()
            self._user_locks[user_id] = lock

        return lock

    # ========================================================
    # NANZ GUILD
    # ========================================================

    def get_nanz_guild(self):
        """
        Mengambil server nanZ berdasarkan ID.
        """

        return self.bot.get_guild(
            NZ_GUILD_ID
        )

    # ========================================================
    # LOYALIST ROLE
    # ========================================================

    def get_loyalist_role(self, guild):
        """
        Mengambil role nZ Loyalist.
        """

        if guild is None:
            return None

        return guild.get_role(
            NZ_LOYALIST_ROLE_ID
        )

    # ========================================================
    # PRIMARY GUILD DEBUG INFO
    # ========================================================

    def get_primary_guild_info(self, user):
        """
        Mengambil informasi Server Tag dari user.

        Return:
            (
                identity_guild_id,
                identity_enabled,
                tag
            )
        """

        primary_guild = getattr(
            user,
            "primary_guild",
            None
        )

        if primary_guild is None:
            return (
                None,
                None,
                None
            )

        identity_guild_id = getattr(
            primary_guild,
            "identity_guild_id",
            None
        )

        identity_enabled = getattr(
            primary_guild,
            "identity_enabled",
            None
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
    # CHECK nZ SERVER TAG
    # ========================================================

    def has_nz_server_tag(self, user):
        """
        Mengecek apakah user sedang menggunakan Server Tag nZ.

        Kondisi harus memenuhi semuanya:

            identity_guild_id == NZ_GUILD_ID

            identity_enabled == True

            tag == "nZ"
        """

        (
            identity_guild_id,
            identity_enabled,
            tag
        ) = self.get_primary_guild_info(
            user
        )

        # ----------------------------------------------------
        # Tidak memiliki primary guild.
        # ----------------------------------------------------

        if identity_guild_id is None:
            return False

        # ----------------------------------------------------
        # Primary guild harus server nanZ.
        # ----------------------------------------------------

        if int(identity_guild_id) != NZ_GUILD_ID:
            return False

        # ----------------------------------------------------
        # Server Tag harus aktif.
        # ----------------------------------------------------

        if identity_enabled is not True:
            return False

        # ----------------------------------------------------
        # Tag harus benar-benar nZ.
        # ----------------------------------------------------

        if tag != NZ_SERVER_TAG:
            return False

        return True

    # ========================================================
    # CHECK ROLE PERMISSION
    # ========================================================

    def can_manage_role(self, guild, role):
        """
        Mengecek apakah bot dapat mengatur role.
        """

        if guild is None:
            return False

        me = guild.me

        if me is None:
            return False

        # Role @everyone tidak dapat dikelola.
        if role.is_default():
            return False

        # Managed role tidak dapat dikelola.
        if role.managed:
            return False

        # Role harus berada di bawah role bot.
        if role >= me.top_role:
            return False

        # Bot harus mempunyai Manage Roles.
        if not me.guild_permissions.manage_roles:
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
        """
        Menambahkan role nZ Loyalist.
        """

        # Sudah punya role.
        if role in member.roles:
            return False

        # Cek permission.
        if not self.can_manage_role(
            member.guild,
            role
        ):
            logger.warning(
                "[nZ Loyalist] Tidak dapat memberikan role "
                "kepada %s (%s). "
                "Periksa Manage Roles dan hierarchy role.",
                member,
                member.id
            )

            return False

        try:

            await member.add_roles(
                role,
                reason=(
                    "nZ Loyalist - "
                    "menggunakan Server Tag nZ"
                )
            )

            logger.info(
                "[nZ Loyalist] ROLE ADD | %s (%s)",
                member,
                member.id
            )

            return True

        except discord.Forbidden:

            logger.error(
                "[nZ Loyalist] Forbidden saat memberikan "
                "role kepada %s (%s).",
                member,
                member.id
            )

        except discord.HTTPException as error:

            logger.error(
                "[nZ Loyalist] HTTP error saat memberikan "
                "role kepada %s (%s): %s",
                member,
                member.id,
                error
            )

        except Exception:

            logger.exception(
                "[nZ Loyalist] Unexpected error saat memberikan "
                "role kepada %s (%s).",
                member,
                member.id
            )

        return False

    # ========================================================
    # REMOVE ROLE
    # ========================================================

    async def remove_loyalist_role(
        self,
        member,
        role
    ):
        """
        Mencabut role nZ Loyalist.
        """

        # Tidak memiliki role.
        if role not in member.roles:
            return False

        # Cek permission.
        if not self.can_manage_role(
            member.guild,
            role
        ):
            logger.warning(
                "[nZ Loyalist] Tidak dapat mencabut role "
                "dari %s (%s). "
                "Periksa Manage Roles dan hierarchy role.",
                member,
                member.id
            )

            return False

        try:

            await member.remove_roles(
                role,
                reason=(
                    "nZ Loyalist - "
                    "Server Tag nZ dilepas"
                )
            )

            logger.info(
                "[nZ Loyalist] ROLE REMOVE | %s (%s)",
                member,
                member.id
            )

            return True

        except discord.Forbidden:

            logger.error(
                "[nZ Loyalist] Forbidden saat mencabut "
                "role dari %s (%s).",
                member,
                member.id
            )

        except discord.HTTPException as error:

            logger.error(
                "[nZ Loyalist] HTTP error saat mencabut "
                "role dari %s (%s): %s",
                member,
                member.id,
                error
            )

        except Exception:

            logger.exception(
                "[nZ Loyalist] Unexpected error saat mencabut "
                "role dari %s (%s).",
                member,
                member.id
            )

        return False

    # ========================================================
    # SYNC MEMBER
    # ========================================================

    async def sync_member(
        self,
        member,
        user_override=None
    ):
        """
        Sinkronisasi role nZ Loyalist.

        Jika menggunakan tag nZ:
            -> role diberikan

        Jika tidak menggunakan tag nZ:
            -> role dicabut
        """

        if member is None:
            return

        # Hanya server nanZ.
        if member.guild.id != NZ_GUILD_ID:
            return

        # Jangan proses bot.
        if member.bot:
            return

        role = self.get_loyalist_role(
            member.guild
        )

        if role is None:

            logger.error(
                "[nZ Loyalist] Role ID %s tidak ditemukan "
                "di server nanZ.",
                NZ_LOYALIST_ROLE_ID
            )

            return

        lock = self.get_user_lock(
            member.id
        )

        async with lock:

            # ------------------------------------------------
            # Gunakan user dari event jika tersedia.
            # ------------------------------------------------

            if user_override is not None:

                user = user_override

            else:

                user = member

                # Member mewarisi data User.
                #
                # Jangan memaksa fetch_user di setiap event
                # karena dapat menyebabkan rate limit.

            # ------------------------------------------------
            # CHECK TAG
            # ------------------------------------------------

            using_nz_tag = self.has_nz_server_tag(
                user
            )

            has_role = (
                role in member.roles
            )

            # ------------------------------------------------
            # DEBUG INTERNAL
            # ------------------------------------------------

            (
                identity_guild_id,
                identity_enabled,
                tag
            ) = self.get_primary_guild_info(
                user
            )

            logger.debug(
                "[nZ Loyalist] CHECK | "
                "user=%s (%s) | "
                "guild=%s | "
                "identity_guild_id=%s | "
                "identity_enabled=%s | "
                "tag=%r | "
                "has_role=%s | "
                "using_nz_tag=%s",
                member,
                member.id,
                member.guild.id,
                identity_guild_id,
                identity_enabled,
                tag,
                has_role,
                using_nz_tag
            )

            # ------------------------------------------------
            # TAG nZ AKTIF
            # ------------------------------------------------

            if using_nz_tag:

                if not has_role:

                    await self.add_loyalist_role(
                        member,
                        role
                    )

                return

            # ------------------------------------------------
            # TAG nZ TIDAK AKTIF
            # ------------------------------------------------

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
        """
        Menangani perubahan User.

        Discord mendokumentasikan primary_guild sebagai
        salah satu perubahan yang memicu on_user_update.
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

        # Tidak ada perubahan primary guild.
        if before_primary == after_primary:
            return

        guild = self.get_nanz_guild()

        if guild is None:
            return

        member = guild.get_member(
            after.id
        )

        if member is None:
            return

        logger.info(
            "[nZ Loyalist] Primary Guild berubah | "
            "%s (%s)",
            after,
            after.id
        )

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
        """
        Backup handler untuk GUILD_MEMBER_UPDATE.

        Discord dapat mengirim perubahan primary_guild melalui
        guild member update.

        Kita tetap memeriksa primary_guild meskipun event ini
        juga dapat dipicu oleh nickname/role/flag/etc.
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

        # Tidak ada perubahan primary guild.
        if before_primary == after_primary:
            return

        logger.info(
            "[nZ Loyalist] Member primary guild berubah | "
            "%s (%s)",
            after,
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
        """
        Mengecek member baru.
        """

        if member.guild.id != NZ_GUILD_ID:
            return

        if member.bot:
            return

        await self.sync_member(
            member
        )

    # ========================================================
    # STARTUP SYNC
    # ========================================================

    async def startup_sync(self):
        """
        Sinkronisasi member setelah bot online.
        """

        await self.bot.wait_until_ready()

        guild = self.get_nanz_guild()

        if guild is None:

            logger.error(
                "[nZ Loyalist] Server nanZ tidak ditemukan: %s",
                NZ_GUILD_ID
            )

            return

        role = self.get_loyalist_role(
            guild
        )

        if role is None:

            logger.error(
                "[nZ Loyalist] Role nZ Loyalist tidak ditemukan: %s",
                NZ_LOYALIST_ROLE_ID
            )

            return

        logger.info(
            "[nZ Loyalist] Memulai startup synchronization."
        )

        logger.info(
            "[nZ Loyalist] Sync guild: %s (%s)",
            guild.name,
            guild.id
        )

        # ----------------------------------------------------
        # Gunakan member cache.
        # ----------------------------------------------------

        members = list(
            guild.members
        )

        if not members:

            logger.warning(
                "[nZ Loyalist] Member cache kosong."
            )

            try:

                members = [
                    member
                    async for member
                    in guild.fetch_members(
                        limit=None
                    )
                ]

            except discord.HTTPException as error:

                logger.error(
                    "[nZ Loyalist] Gagal fetch members: %s",
                    error
                )

                return

            except Exception:

                logger.exception(
                    "[nZ Loyalist] Unexpected error "
                    "saat fetch members."
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
                    "[nZ Loyalist] Gagal sync "
                    "%s (%s).",
                    member,
                    member.id
                )

            processed += 1

            # ------------------------------------------------
            # API safety
            # ------------------------------------------------

            if processed % SYNC_BATCH_SIZE == 0:

                await asyncio.sleep(
                    SYNC_DELAY
                )

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
        """
        Backup synchronization.

        Hanya memeriksa member yang SUDAH mempunyai
        role nZ Loyalist.

        Tujuannya terutama untuk mencabut role jika:
        - event terlewat
        - cache sempat tidak sinkron
        - user melepas Server Tag

        Kita tidak mengecek seluruh member secara agresif,
        sehingga tidak membuat API spam.
        """

        guild = self.get_nanz_guild()

        if guild is None:
            return

        role = self.get_loyalist_role(
            guild
        )

        if role is None:
            return

        # ----------------------------------------------------
        # Hanya member yang sudah punya role.
        # ----------------------------------------------------

        members_with_role = [
            member
            for member in guild.members
            if role in member.roles
            and not member.bot
        ]

        if not members_with_role:
            return

        logger.debug(
            "[nZ Loyalist] Periodic check: %s member.",
            len(members_with_role)
        )

        for member in members_with_role:

            try:

                await self.sync_member(
                    member
                )

            except Exception:

                logger.exception(
                    "[nZ Loyalist] Periodic sync gagal "
                    "untuk %s (%s).",
                    member,
                    member.id
                )

            await asyncio.sleep(
                0.10
            )

    # ========================================================
    # PERIODIC LOOP ERROR
    # ========================================================

    @periodic_sync.error
    async def periodic_sync_error(
        self,
        error
    ):
        """
        Error handler untuk periodic loop.
        """

        logger.exception(
            "[nZ Loyalist] Periodic sync error: %s",
            error
        )

    # ========================================================
    # COG LOAD
    # ========================================================

    async def cog_load(self):
        """
        Dipanggil ketika cog berhasil dimuat.
        """

        logger.info(
            "[nZ Loyalist] Cog loaded."
        )

        # ----------------------------------------------------
        # Startup sync.
        # ----------------------------------------------------

        self._startup_task = (
            self.bot.loop.create_task(
                self.startup_sync()
            )
        )

        # ----------------------------------------------------
        # Periodic backup.
        # ----------------------------------------------------

        self._periodic_task = (
            self.periodic_sync.start()
        )

    # ========================================================
    # COG UNLOAD
    # ========================================================

    async def cog_unload(self):
        """
        Membersihkan task ketika cog di-unload.
        """

        # ----------------------------------------------------
        # Stop periodic task.
        # ----------------------------------------------------

        if self.periodic_sync.is_running():

            self.periodic_sync.cancel()

        # ----------------------------------------------------
        # Cancel startup task.
        # ----------------------------------------------------

        if self._startup_task is not None:

            if not self._startup_task.done():

                self._startup_task.cancel()

            self._startup_task = None

        # ----------------------------------------------------
        # Clear locks.
        # ----------------------------------------------------

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