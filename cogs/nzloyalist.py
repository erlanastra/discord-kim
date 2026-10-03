import asyncio
import logging

import discord
from discord.ext import commands


# ============================================================
# CONFIGURATION
# ============================================================

# ROLE nZ LOYALIST
NZ_LOYALIST_ROLE_ID = 1555892286704062529

# SERVER TAG NANZ
NZ_SERVER_TAG = "nZ"

# Delay antar batch ketika melakukan sinkronisasi startup.
# Dibuat supaya bot tidak langsung melakukan terlalu banyak
# request Discord API sekaligus.
SYNC_DELAY = 0.15

# Jumlah member yang diproses sebelum memberi jeda.
SYNC_BATCH_SIZE = 25


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger("nanZ.nZLoyalist")


# ============================================================
# COG
# ============================================================

class NZLoyalist(commands.Cog):
    """
    Sistem penghargaan nZ Loyalist.

    Fungsi:
    - Member menggunakan Server Tag nZ
        -> mendapatkan role nZ Loyalist

    - Member melepas Server Tag nZ
        -> role nZ Loyalist dicabut

    - Member mengganti Server Tag nZ dengan Server Tag lain
        -> role nZ Loyalist dicabut

    - Bot restart
        -> sistem melakukan sinkronisasi ulang member

    Sistem menggunakan:
        User.primary_guild
        PrimaryGuild.identity_guild_id
        PrimaryGuild.identity_enabled
        PrimaryGuild.tag

    Kompatibel:
        Python 3.8
        discord.py 2.7.1
    """

    def __init__(self, bot):
        self.bot = bot

        # Mencegah dua proses sync untuk user yang sama
        # berjalan bersamaan.
        self._sync_locks = {}

        # Task startup sync.
        self._startup_task = None

    # ========================================================
    # LOCK
    # ========================================================

    def get_user_lock(self, user_id):
        """
        Mendapatkan lock khusus untuk satu user.

        Ini mencegah kondisi seperti:
        - on_user_update berjalan
        - on_member_join berjalan
        - startup sync berjalan

        pada user yang sama secara bersamaan.
        """

        lock = self._sync_locks.get(user_id)

        if lock is None:
            lock = asyncio.Lock()
            self._sync_locks[user_id] = lock

        return lock

    # ========================================================
    # GET TARGET GUILD
    # ========================================================

    def get_target_guilds(self):
        """
        Mencari guild yang memiliki role nZ Loyalist.

        Dengan pendekatan ini kita tidak perlu hardcode
        GUILD_ID nanZ.

        Role ID:
            1555892286704062529
        """

        guilds = []

        for guild in self.bot.guilds:
            role = guild.get_role(NZ_LOYALIST_ROLE_ID)

            if role is not None:
                guilds.append(guild)

        return guilds

    # ========================================================
    # GET ROLE
    # ========================================================

    def get_loyalist_role(self, guild):
        """
        Mengambil role nZ Loyalist dari guild.
        """

        return guild.get_role(NZ_LOYALIST_ROLE_ID)

    # ========================================================
    # CHECK SERVER TAG
    # ========================================================

    def has_nz_server_tag(self, user, guild):
        """
        Mengecek apakah user sedang menggunakan Server Tag nZ
        dari guild tertentu.

        Discord menyimpan informasi Server Tag melalui:

            user.primary_guild

        PrimaryGuild mempunyai:

            identity_guild_id
            identity_enabled
            tag

        Kondisi valid:

            identity_guild_id == guild.id
            identity_enabled is True
            tag == "nZ"
        """

        primary_guild = getattr(user, "primary_guild", None)

        # Tidak ada primary guild.
        if primary_guild is None:
            return False

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

        # Pastikan Server Tag memang milik guild ini.
        if identity_guild_id != guild.id:
            return False

        # Harus benar-benar aktif.
        if identity_enabled is not True:
            return False

        # Pastikan tag adalah nZ.
        if tag != NZ_SERVER_TAG:
            return False

        return True

    # ========================================================
    # ROLE CAN BE MANAGED
    # ========================================================

    def can_manage_role(self, guild, role):
        """
        Mengecek apakah bot dapat mengatur role.
        """

        me = guild.me

        if me is None:
            return False

        if role.is_default():
            return False

        if role.managed:
            return False

        if role >= me.top_role:
            return False

        if not me.guild_permissions.manage_roles:
            return False

        return True

    # ========================================================
    # ADD ROLE
    # ========================================================

    async def add_loyalist_role(self, member, role):
        """
        Memberikan role nZ Loyalist.
        """

        if role in member.roles:
            return False

        if not self.can_manage_role(member.guild, role):
            logger.warning(
                "[nZ Loyalist] Tidak dapat memberikan role "
                "kepada %s (%s): hierarchy/permission bermasalah.",
                member,
                member.id
            )
            return False

        try:
            await member.add_roles(
                role,
                reason="nZ Loyalist - menggunakan Server Tag nZ"
            )

            logger.info(
                "[nZ Loyalist] ROLE ADD | %s (%s)",
                member,
                member.id
            )

            return True

        except discord.Forbidden:
            logger.error(
                "[nZ Loyalist] FORBIDDEN saat memberikan role "
                "kepada %s (%s).",
                member,
                member.id
            )

        except discord.HTTPException as error:
            logger.error(
                "[nZ Loyalist] HTTP ERROR saat memberikan role "
                "kepada %s (%s): %s",
                member,
                member.id,
                error
            )

        except Exception:
            logger.exception(
                "[nZ Loyalist] ERROR tidak terduga saat memberikan "
                "role kepada %s (%s).",
                member,
                member.id
            )

        return False

    # ========================================================
    # REMOVE ROLE
    # ========================================================

    async def remove_loyalist_role(self, member, role):
        """
        Mencabut role nZ Loyalist.
        """

        if role not in member.roles:
            return False

        if not self.can_manage_role(member.guild, role):
            logger.warning(
                "[nZ Loyalist] Tidak dapat mencabut role "
                "dari %s (%s): hierarchy/permission bermasalah.",
                member,
                member.id
            )
            return False

        try:
            await member.remove_roles(
                role,
                reason="nZ Loyalist - Server Tag nZ dilepas"
            )

            logger.info(
                "[nZ Loyalist] ROLE REMOVE | %s (%s)",
                member,
                member.id
            )

            return True

        except discord.Forbidden:
            logger.error(
                "[nZ Loyalist] FORBIDDEN saat mencabut role "
                "dari %s (%s).",
                member,
                member.id
            )

        except discord.HTTPException as error:
            logger.error(
                "[nZ Loyalist] HTTP ERROR saat mencabut role "
                "dari %s (%s): %s",
                member,
                member.id,
                error
            )

        except Exception:
            logger.exception(
                "[nZ Loyalist] ERROR tidak terduga saat mencabut "
                "role dari %s (%s).",
                member,
                member.id
            )

        return False

    # ========================================================
    # SYNC MEMBER
    # ========================================================

    async def sync_member(self, member):
        """
        Sinkronisasi satu member.

        Jika memakai nZ:
            role ditambahkan.

        Jika tidak memakai nZ:
            role dicabut.
        """

        if member is None:
            return

        if member.bot:
            return

        guild = member.guild

        role = self.get_loyalist_role(guild)

        if role is None:
            return

        lock = self.get_user_lock(member.id)

        async with lock:

            # Ambil User object terbaru jika tersedia.
            user = self.bot.get_user(member.id)

            if user is None:
                user = member

            using_nz_tag = self.has_nz_server_tag(
                user,
                guild
            )

            has_role = role in member.roles

            # =================================================
            # TAG nZ AKTIF
            # =================================================

            if using_nz_tag:

                if not has_role:
                    await self.add_loyalist_role(
                        member,
                        role
                    )

                return

            # =================================================
            # TAG nZ TIDAK AKTIF
            # =================================================

            if has_role:
                await self.remove_loyalist_role(
                    member,
                    role
                )

    # ========================================================
    # USER UPDATE
    # ========================================================

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        """
        Dipanggil Discord ketika data User berubah.

        discord.py mendokumentasikan bahwa perubahan
        primary_guild memicu on_user_update.

        Kita hanya memproses user jika perubahan memang
        berhubungan dengan primary_guild.
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

        # Cari guild nanZ berdasarkan role nZ Loyalist.
        for guild in self.get_target_guilds():

            member = guild.get_member(after.id)

            if member is None:
                continue

            await self.sync_member(member)

    # ========================================================
    # MEMBER JOIN
    # ========================================================

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """
        Ketika member masuk ke server, langsung cek
        apakah mereka sudah menggunakan Server Tag nZ.
        """

        if member.bot:
            return

        await self.sync_member(member)

    # ========================================================
    # STARTUP SYNC
    # ========================================================

    async def startup_sync(self):
        """
        Sinkronisasi seluruh member setelah bot siap.

        Ini penting agar role tetap benar setelah:

        - bot restart
        - VPS restart
        - service restart
        - reconnect
        """

        await self.bot.wait_until_ready()

        logger.info(
            "[nZ Loyalist] Memulai startup synchronization."
        )

        for guild in self.get_target_guilds():

            role = self.get_loyalist_role(guild)

            if role is None:
                continue

            logger.info(
                "[nZ Loyalist] Sync guild: %s (%s)",
                guild.name,
                guild.id
            )

            processed = 0

            try:

                # Gunakan cache terlebih dahulu.
                members = list(guild.members)

                # Jika cache kosong/tidak lengkap, coba fetch.
                if not members:
                    try:
                        members = [
                            member async for member
                            in guild.fetch_members(limit=None)
                        ]
                    except Exception:
                        logger.exception(
                            "[nZ Loyalist] Gagal fetch members "
                            "guild %s.",
                            guild.id
                        )

                for member in members:

                    if member.bot:
                        continue

                    try:
                        await self.sync_member(member)

                    except Exception:
                        logger.exception(
                            "[nZ Loyalist] Gagal sync member "
                            "%s (%s).",
                            member,
                            member.id
                        )

                    processed += 1

                    # Jeda setiap beberapa member agar tidak
                    # membanjiri Discord API.
                    if processed % SYNC_BATCH_SIZE == 0:
                        await asyncio.sleep(SYNC_DELAY)

            except Exception:
                logger.exception(
                    "[nZ Loyalist] Error saat startup sync "
                    "guild %s.",
                    guild.id
                )

        logger.info(
            "[nZ Loyalist] Startup synchronization selesai."
        )

    # ========================================================
    # COG LOAD
    # ========================================================

    async def cog_load(self):
        """
        Dipanggil ketika cog berhasil dimuat.
        """

        self._startup_task = self.bot.loop.create_task(
            self.startup_sync()
        )

        logger.info(
            "[nZ Loyalist] Cog loaded."
        )

    # ========================================================
    # COG UNLOAD
    # ========================================================

    async def cog_unload(self):
        """
        Membersihkan task ketika cog di-unload.
        """

        if self._startup_task is not None:

            if not self._startup_task.done():
                self._startup_task.cancel()

            self._startup_task = None

        self._sync_locks.clear()

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