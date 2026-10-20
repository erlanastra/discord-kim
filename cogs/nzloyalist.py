
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

# Pengecekan cadangan tetap setiap 5 menit.
SYNC_DELAY = 0.5
SYNC_BATCH_SIZE = 20
PERIODIC_CHECK_MINUTES = 5

logger = logging.getLogger("nanZ.nZLoyalist")


class NZLoyalist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._user_locks = {}
        self._startup_task = None
        logger.info("[nZ Loyalist] Cog loaded.")

    # --------------------------------------------------------
    # LOCK PER MEMBER
    # --------------------------------------------------------
    def get_user_lock(self, user_id: int):
        lock = self._user_locks.get(user_id)

        if lock is None:
            lock = asyncio.Lock()
            self._user_locks[user_id] = lock

        return lock

    # --------------------------------------------------------
    # GUILD DAN ROLE
    # --------------------------------------------------------
    def get_nanz_guild(self):
        guild = self.bot.get_guild(NZ_GUILD_ID)

        if guild is None:
            logger.warning(
                "[nZ Loyalist] Guild nanZ tidak ditemukan: %s",
                NZ_GUILD_ID,
            )

        return guild

    def get_loyalist_role(self, guild):
        role = guild.get_role(NZ_LOYALIST_ROLE_ID)

        if role is None:
            logger.error(
                "[nZ Loyalist] Role nZ Loyalist tidak ditemukan: %s",
                NZ_LOYALIST_ROLE_ID,
            )

        return role

    # --------------------------------------------------------
    # SERVER TAG
    # --------------------------------------------------------
    @staticmethod
    def get_primary_guild(user):
        return getattr(user, "primary_guild", None)

    def get_server_tag(self, user):
        primary_guild = self.get_primary_guild(user)

        if primary_guild is None:
            return None

        return getattr(primary_guild, "tag", None)

    def has_nz_server_tag(self, user):
        primary_guild = self.get_primary_guild(user)

        if primary_guild is None:
            return False

        tag = getattr(primary_guild, "tag", None)
        identity_enabled = getattr(
            primary_guild,
            "identity_enabled",
            False,
        )

        return identity_enabled is True and tag == NZ_SERVER_TAG

    # --------------------------------------------------------
    # VALIDASI PERMISSION ROLE
    # --------------------------------------------------------
    def can_manage_role(self, guild, role):
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
                "atau sama dengan role bot. "
                "Bot Top Role: %s (%s); Target Role: %s (%s)",
                me.top_role.name,
                me.top_role.id,
                role.name,
                role.id,
            )
            return False

        return True

    # --------------------------------------------------------
    # TAMBAH ROLE
    # --------------------------------------------------------
    async def add_loyalist_role(self, member, role):
        if role in member.roles:
            return

        if not self.can_manage_role(member.guild, role):
            return

        try:
            await member.add_roles(
                role,
                reason="Menggunakan Server Tag nanZ (nZ)",
            )

            logger.info(
                "[nZ Loyalist] ROLE DIBERIKAN | %s (%s) | %s (%s)",
                member,
                member.id,
                role.name,
                role.id,
            )

        except discord.Forbidden:
            logger.exception(
                "[nZ Loyalist] Discord menolak pemberian role kepada %s.",
                member,
            )

        except discord.HTTPException as error:
            logger.exception(
                "[nZ Loyalist] HTTP error saat memberikan role "
                "kepada %s: %s",
                member,
                error,
            )

    # --------------------------------------------------------
    # CABUT ROLE
    # --------------------------------------------------------
    async def remove_loyalist_role(self, member, role):
        if role not in member.roles:
            return

        if not self.can_manage_role(member.guild, role):
            return

        try:
            await member.remove_roles(
                role,
                reason="Tidak lagi menggunakan Server Tag nanZ (nZ)",
            )

            logger.info(
                "[nZ Loyalist] ROLE DICABUT | %s (%s) | %s (%s)",
                member,
                member.id,
                role.name,
                role.id,
            )

        except discord.Forbidden:
            logger.exception(
                "[nZ Loyalist] Discord menolak pencabutan role dari %s.",
                member,
            )

        except discord.HTTPException as error:
            logger.exception(
                "[nZ Loyalist] HTTP error saat mencabut role "
                "dari %s: %s",
                member,
                error,
            )

    # --------------------------------------------------------
    # SINKRONKAN SATU MEMBER
    # --------------------------------------------------------
    async def sync_member(self, member, user_override=None):
        if member.guild.id != NZ_GUILD_ID or member.bot:
            return

        lock = self.get_user_lock(member.id)

        async with lock:
            guild = member.guild
            role = self.get_loyalist_role(guild)

            if role is None:
                return

            user = (
                user_override
                if user_override is not None
                else member
            )

            has_tag = self.has_nz_server_tag(user)
            has_role = role in member.roles

            # Log hanya muncul ketika role benar-benar berubah.
            if has_tag and not has_role:
                await self.add_loyalist_role(member, role)

            elif not has_tag and has_role:
                await self.remove_loyalist_role(member, role)

    # --------------------------------------------------------
    # USER UPDATE
    # --------------------------------------------------------
    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        before_primary = getattr(
            before,
            "primary_guild",
            None,
        )
        after_primary = getattr(
            after,
            "primary_guild",
            None,
        )

        if before_primary == after_primary:
            return

        guild = self.get_nanz_guild()

        if guild is None:
            return

        member = guild.get_member(after.id)

        if member is None:
            return

        await self.sync_member(
            member,
            user_override=after,
        )

    # --------------------------------------------------------
    # MEMBER UPDATE
    # --------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if after.guild.id != NZ_GUILD_ID:
            return

        before_primary = getattr(
            before,
            "primary_guild",
            None,
        )
        after_primary = getattr(
            after,
            "primary_guild",
            None,
        )

        if before_primary == after_primary:
            return

        await self.sync_member(
            after,
            user_override=after,
        )

    # --------------------------------------------------------
    # MEMBER JOIN
    # --------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != NZ_GUILD_ID or member.bot:
            return

        await asyncio.sleep(1)
        await self.sync_member(member)

    # --------------------------------------------------------
    # SINKRONISASI SAAT STARTUP
    # --------------------------------------------------------
    async def startup_sync(self):
        await self.bot.wait_until_ready()

        logger.info(
            "[nZ Loyalist] Memulai startup synchronization."
        )

        guild = self.get_nanz_guild()

        if guild is None:
            return

        role = self.get_loyalist_role(guild)

        if role is None:
            return

        members = list(guild.members)

        if not members:
            try:
                members = [
                    member
                    async for member in guild.fetch_members(limit=None)
                ]

                logger.info(
                    "[nZ Loyalist] Fetch members selesai: %s member.",
                    len(members),
                )

            except discord.HTTPException:
                logger.exception(
                    "[nZ Loyalist] Gagal fetch members."
                )
                return

        processed = 0
        errors = 0

        for member in members:
            if member.bot:
                continue

            try:
                await self.sync_member(member)

            except asyncio.CancelledError:
                raise

            except Exception:
                errors += 1

                logger.exception(
                    "[nZ Loyalist] Error startup sync %s (%s)",
                    member,
                    member.id,
                )

            processed += 1

            await asyncio.sleep(SYNC_DELAY)

            if processed % SYNC_BATCH_SIZE == 0:
                await asyncio.sleep(2)

        logger.info(
            "[nZ Loyalist] Startup sync selesai | "
            "Diproses: %s | Error: %s",
            processed,
            errors,
        )

    # --------------------------------------------------------
    # PEMERIKSAAN CADANGAN SETIAP 5 MENIT
    # --------------------------------------------------------
    @tasks.loop(minutes=PERIODIC_CHECK_MINUTES)
    async def periodic_sync(self):
        guild = self.get_nanz_guild()

        if guild is None:
            return

        role = self.get_loyalist_role(guild)

        if role is None:
            return

        checked = 0
        errors = 0

        # Hanya member yang sudah memiliki role Loyalist
        # diperiksa pada siklus ini.
        for member in list(guild.members):
            if member.bot or role not in member.roles:
                continue

            try:
                await self.sync_member(member)
                checked += 1

            except asyncio.CancelledError:
                raise

            except Exception:
                errors += 1

                logger.exception(
                    "[nZ Loyalist] Error backup sync %s (%s)",
                    member,
                    member.id,
                )

            await asyncio.sleep(SYNC_DELAY)

        # Satu ringkasan per siklus, bukan log setiap member.
        logger.info(
            "[nZ Loyalist] Backup sync selesai | "
            "Diperiksa: %s | Error: %s",
            checked,
            errors,
        )

    @periodic_sync.before_loop
    async def before_periodic_sync(self):
        await self.bot.wait_until_ready()

    @periodic_sync.error
    async def periodic_sync_error(self, error):
        logger.error(
            "[nZ Loyalist] Periodic synchronization error: %s",
            error,
            exc_info=(
                type(error),
                error,
                error.__traceback__,
            ),
        )

    # --------------------------------------------------------
    # LOAD / UNLOAD COG
    # --------------------------------------------------------
    async def cog_load(self):
        self._startup_task = asyncio.create_task(
            self.startup_sync()
        )

        if not self.periodic_sync.is_running():
            self.periodic_sync.start()

    async def cog_unload(self):
        if self._startup_task is not None:
            self._startup_task.cancel()

        self.periodic_sync.cancel()
        self._user_locks.clear()

        logger.info("[nZ Loyalist] Cog unloaded.")


async def setup(bot):
    await bot.add_cog(NZLoyalist(bot))
