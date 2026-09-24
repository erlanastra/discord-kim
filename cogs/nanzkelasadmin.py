import discord
from discord.ext import commands, tasks

import aiomysql
import datetime
import logging


# =========================================================
# CONFIG
# =========================================================

GUILD_ID = 123456789012345678

DAFTAR_KELAS_CHANNEL_ID = 876543210987654321
LOG_KELAS_CHANNEL_ID = 123456789012345678

MAX_MEMBER = 20

CLASS_PRICE = 500_000

GRACE_DAYS = 7

DB_CONFIG = {
    "host": "localhost",
    "user": "nanzuser",
    "password": "nanzserversolid",
    "db": "nanz_bot",
    "autocommit": True
}


logger = logging.getLogger("nanz.kelas.admin")


# =========================================================
# UTILITY
# =========================================================

def utc_now():
    return datetime.datetime.now(
        datetime.timezone.utc
    )


async def get_db():

    return await aiomysql.connect(
        **DB_CONFIG
    )


async def send_log(
    guild,
    message
):

    channel = guild.get_channel(
        LOG_KELAS_CHANNEL_ID
    )

    if not channel:
        return

    try:

        await channel.send(
            f"📝 **KELAS LOG**\n{message}"
        )

    except Exception:
        pass


# =========================================================
# BILLING VIEW
# =========================================================

class BillingView(discord.ui.View):

    def __init__(
        self,
        class_id
    ):

        super().__init__(
            timeout=None
        )

        self.class_id = class_id

        self.paid_button.custom_id = (
            f"kelas:billing:paid:{class_id}"
        )

    @discord.ui.button(
        label="💰 Tandai Lunas",
        style=discord.ButtonStyle.success
    )
    async def paid_button(
        self,
        interaction,
        button
    ):

        if not (
            interaction.user.guild_permissions.administrator
            or interaction.user.guild_permissions.manage_guild
        ):

            return await interaction.response.send_message(
                "❌ Hanya Management yang dapat menandai pembayaran.",
                ephemeral=True
            )

        await interaction.response.defer()

        conn = await get_db()

        try:

            async with conn.cursor(
                aiomysql.DictCursor
            ) as cur:

                await cur.execute(
                    """
                    SELECT *
                    FROM nanz_classes
                    WHERE class_id = %s
                    """,
                    (self.class_id,)
                )

                cls = await cur.fetchone()

                if not cls:

                    return await interaction.followup.send(
                        "❌ Kelas tidak ditemukan."
                    )

                # Kalau masih active, gunakan due lama.
                # Kalau sudah grace, tetap +30 dari due lama.
                old_due = cls["due_date"]

                new_due = (
                    old_due
                    + datetime.timedelta(days=30)
                )

                new_grace = (
                    new_due
                    + datetime.timedelta(days=7)
                )

                await cur.execute(
                    """
                    UPDATE nanz_classes
                    SET
                        due_date = %s,
                        grace_until = %s,
                        status = 'Active',
                        billing_status = 'Paid',
                        billing_message_id = NULL,
                        last_billing_notice = NULL
                    WHERE class_id = %s
                    """,
                    (
                        new_due,
                        new_grace,
                        self.class_id
                    )
                )

        finally:
            conn.close()

        # Disable button
        for item in self.children:
            item.disabled = True

        await interaction.message.edit(
            content=(
                "💰 **TAGIHAN LUNAS ✅**\n"
                f"Periode berikutnya berakhir "
                f"<t:{int(new_due.timestamp())}:F>."
            ),
            view=self
        )

        await send_log(
            interaction.guild,
            f"💰 Pembayaran kelas **{cls['name']}** ditandai lunas "
            f"oleh {interaction.user.mention}.\n"
            f"Periode baru sampai <t:{int(new_due.timestamp())}:F>."
        )


# =========================================================
# ADMIN COG
# =========================================================

class NanzKelasAdmin(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.billing_loop.start()

    def cog_unload(self):

        self.billing_loop.cancel()

    # =====================================================
    # BILLING LOOP
    # =====================================================

    @tasks.loop(minutes=30)
    async def billing_loop(self):

        conn = await get_db()

        try:

            async with conn.cursor(
                aiomysql.DictCursor
            ) as cur:

                await cur.execute(
                    """
                    SELECT *
                    FROM nanz_classes
                    WHERE status IN
                    ('Active','Grace')
                    """
                )

                classes = await cur.fetchall()

        finally:
            conn.close()

        now = utc_now()

        for cls in classes:

            guild = self.bot.get_guild(
                cls["guild_id"]
            )

            if not guild:
                continue

            try:

                await self.process_class_billing(
                    guild,
                    cls,
                    now
                )

            except Exception:

                logger.exception(
                    f"Billing error class={cls['class_id']}"
                )

    @billing_loop.before_loop
    async def before_billing_loop(self):

        await self.bot.wait_until_ready()

    # =====================================================
    # BILLING PROCESS
    # =====================================================

    async def process_class_billing(
        self,
        guild,
        cls,
        now
    ):

        due = cls["due_date"]

        # ================================================
        # H-3
        # ================================================

        h3_time = (
            due
            - datetime.timedelta(days=3)
        )

        if (
            now >= h3_time
            and now < due
            and cls["billing_status"] != "Paid"
        ):

            # Jangan spam
            if cls["last_billing_notice"]:

                last = cls["last_billing_notice"]

                if (
                    now - last
                ).total_seconds() < 24 * 3600:

                    return

            await self.send_billing_message(
                guild,
                cls,
                "H-3"
            )

            await self.update_notice_time(
                cls["class_id"]
            )

            return

        # ================================================
        # HARI 30 → GRACE
        # ================================================

        if (
            now >= due
            and now < cls["grace_until"]
            and cls["status"] != "Grace"
        ):

            await self.set_grace(
                cls["class_id"]
            )

            await self.send_billing_message(
                guild,
                cls,
                "GRACE"
            )

            return

        # ================================================
        # GRACE → INACTIVE
        # ================================================

        if (
            now >= cls["grace_until"]
            and cls["status"] != "Inactive"
        ):

            await self.set_inactive(
                guild,
                cls
            )

    # =====================================================
    # SEND BILLING
    # =====================================================

    async def send_billing_message(
        self,
        guild,
        cls,
        stage
    ):

        vc = guild.get_channel(
            cls["vc_id"]
        )

        if not vc:
            return

        role = guild.get_role(
            cls["role_id"]
        )

        role_mention = (
            role.mention
            if role
            else f"<@&{cls['role_id']}>"
        )

        if stage == "H-3":

            title = "💰 Tagihan Kelas nanZ"

            description = (
                f"{role_mention}\n\n"
                f"Periode kelas **{cls['name']}** "
                f"akan berakhir dalam **3 hari**.\n\n"
                f"**Tagihan:** `{CLASS_PRICE:,} OwO Cash`\n"
                f"**Jatuh tempo:** "
                f"<t:{int(cls['due_date'].timestamp())}:F>\n\n"
                "Silakan lakukan pembayaran secara manual "
                "dan hubungi Staff/Management untuk verifikasi."
            )

        else:

            title = "⚠️ Masa Grace Kelas"

            description = (
                f"{role_mention}\n\n"
                f"Kelas **{cls['name']}** telah mencapai "
                "**jatuh tempo**.\n\n"
                f"Tagihan: `{CLASS_PRICE:,} OwO Cash`\n"
                f"Grace Period sampai "
                f"<t:{int(cls['grace_until'].timestamp())}:F>\n\n"
                "Jika pembayaran belum dikonfirmasi sampai batas "
                "tersebut, kelas akan berstatus **Inactive**."
            )

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.gold()
        )

        view = BillingView(
            cls["class_id"]
        )

        message = await vc.send(
            embed=embed,
            view=view
        )

        conn = await get_db()

        try:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    UPDATE nanz_classes
                    SET
                        billing_message_id = %s
                    WHERE class_id = %s
                    """,
                    (
                        message.id,
                        cls["class_id"]
                    )
                )

        finally:
            conn.close()

    # =====================================================
    # NOTICE TIME
    # =====================================================

    async def update_notice_time(
        self,
        class_id
    ):

        conn = await get_db()

        try:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    UPDATE nanz_classes
                    SET last_billing_notice = %s
                    WHERE class_id = %s
                    """,
                    (
                        utc_now(),
                        class_id
                    )
                )

        finally:
            conn.close()

    # =====================================================
    # SET GRACE
    # =====================================================

    async def set_grace(
        self,
        class_id
    ):

        conn = await get_db()

        try:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    UPDATE nanz_classes
                    SET status = 'Grace'
                    WHERE class_id = %s
                    """,
                    (class_id,)
                )

        finally:
            conn.close()

    # =====================================================
    # SET INACTIVE
    # =====================================================

    async def set_inactive(
        self,
        guild,
        cls
    ):

        conn = await get_db()

        try:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    UPDATE nanz_classes
                    SET status = 'Inactive'
                    WHERE class_id = %s
                    """,
                    (cls["class_id"],)
                )

        finally:
            conn.close()

        await send_log(
            guild,
            f"💤 Kelas **{cls['name']}** sekarang berstatus **Inactive** "
            f"karena pembayaran belum diselesaikan sampai grace period berakhir."
        )

    # =====================================================
    # EXTEND MANUAL
    # =====================================================

    @commands.command(
        name="perpanjang_kelas"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def perpanjang_kelas(
        self,
        ctx,
        class_id: int
    ):

        conn = await get_db()

        try:

            async with conn.cursor(
                aiomysql.DictCursor
            ) as cur:

                await cur.execute(
                    """
                    SELECT *
                    FROM nanz_classes
                    WHERE class_id = %s
                    """,
                    (class_id,)
                )

                cls = await cur.fetchone()

                if not cls:
                    return await ctx.send(
                        "❌ Kelas tidak ditemukan."
                    )

                new_due = (
                    cls["due_date"]
                    + datetime.timedelta(days=30)
                )

                new_grace = (
                    new_due
                    + datetime.timedelta(days=7)
                )

                await cur.execute(
                    """
                    UPDATE nanz_classes
                    SET
                        due_date = %s,
                        grace_until = %s,
                        status = 'Active',
                        billing_status = 'Paid',
                        billing_message_id = NULL,
                        last_billing_notice = NULL
                    WHERE class_id = %s
                    """,
                    (
                        new_due,
                        new_grace,
                        class_id
                    )
                )

        finally:
            conn.close()

        await ctx.send(
            f"✅ Kelas **{cls['name']}** diperpanjang 30 hari.\n"
            f"Berakhir: <t:{int(new_due.timestamp())}:F>"
        )

    # =====================================================
    # KELUAR KELAS
    # =====================================================

    @commands.command(
        name="keluar_kelas"
    )
    async def keluar_kelas(
        self,
        ctx
    ):

        conn = await get_db()

        try:

            async with conn.cursor(
                aiomysql.DictCursor
            ) as cur:

                await cur.execute(
                    """
                    SELECT *
                    FROM nanz_class_members
                    WHERE user_id = %s
                    LIMIT 1
                    """,
                    (ctx.author.id,)
                )

                member = await cur.fetchone()

                if not member:

                    return await ctx.send(
                        "⚠️ Kamu belum memiliki kelas."
                    )

                await cur.execute(
                    """
                    SELECT *
                    FROM nanz_classes
                    WHERE class_id = %s
                    """,
                    (member["class_id"],)
                )

                cls = await cur.fetchone()

                if not cls:
                    return await ctx.send(
                        "❌ Data kelas tidak ditemukan."
                    )

                if cls["owner_id"] == ctx.author.id:

                    return await ctx.send(
                        "❌ Owner kelas tidak dapat keluar sendiri. "
                        "Hubungi Management jika ingin memindahkan kepemilikan atau membubarkan kelas."
                    )

                await cur.execute(
                    """
                    DELETE FROM nanz_class_members
                    WHERE class_id = %s
                    AND user_id = %s
                    """,
                    (
                        cls["class_id"],
                        ctx.author.id
                    )
                )

        finally:
            conn.close()

        role = ctx.guild.get_role(
            cls["role_id"]
        )

        if role:

            try:
                await ctx.author.remove_roles(
                    role
                )

            except Exception:
                pass

        await send_log(
            ctx.guild,
            f"👋 {ctx.author.mention} keluar dari kelas **{cls['name']}**."
        )

        await ctx.send(
            f"✅ Kamu berhasil keluar dari kelas **{cls['name']}**."
        )

    # =====================================================
    # KICK MEMBER
    # =====================================================

    @commands.command(
        name="kick_kelas"
    )
    async def kick_kelas(
        self,
        ctx,
        target: discord.Member
    ):

        conn = await get_db()

        try:

            async with conn.cursor(
                aiomysql.DictCursor
            ) as cur:

                await cur.execute(
                    """
                    SELECT *
                    FROM nanz_class_members
                    WHERE user_id = %s
                    LIMIT 1
                    """,
                    (target.id,)
                )

                member = await cur.fetchone()

                if not member:

                    return await ctx.send(
                        "⚠️ Member tersebut tidak terdaftar di kelas."
                    )

                await cur.execute(
                    """
                    SELECT *
                    FROM nanz_classes
                    WHERE class_id = %s
                    """,
                    (member["class_id"],)
                )

                cls = await cur.fetchone()

                if not cls:
                    return await ctx.send(
                        "❌ Kelas tidak ditemukan."
                    )

                is_admin = (
                    ctx.author.guild_permissions.administrator
                )

                is_owner = (
                    cls["owner_id"] == ctx.author.id
                )

                is_staff = (
                    cls["staff_id"] == ctx.author.id
                )

                if not (
                    is_admin
                    or is_owner
                    or is_staff
                ):

                    return await ctx.send(
                        "❌ Kamu tidak memiliki izin untuk mengeluarkan member dari kelas ini."
                    )

                if target.id == cls["owner_id"]:

                    return await ctx.send(
                        "❌ Owner kelas tidak dapat dikeluarkan."
                    )

                await cur.execute(
                    """
                    DELETE FROM nanz_class_members
                    WHERE class_id = %s
                    AND user_id = %s
                    """,
                    (
                        cls["class_id"],
                        target.id
                    )
                )

        finally:
            conn.close()

        role = ctx.guild.get_role(
            cls["role_id"]
        )

        if role:

            try:
                await target.remove_roles(
                    role
                )

            except Exception:
                pass

        await send_log(
            ctx.guild,
            f"🚪 {target.mention} dikeluarkan dari kelas "
            f"**{cls['name']}** oleh {ctx.author.mention}."
        )

        await ctx.send(
            f"✅ {target.mention} berhasil dikeluarkan dari kelas **{cls['name']}**."
        )

    # =====================================================
    # BUBARKAN KELAS
    # =====================================================

    @commands.command(
        name="hapus_kelas"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def hapus_kelas(
        self,
        ctx,
        class_id: int
    ):

        conn = await get_db()

        try:

            async with conn.cursor(
                aiomysql.DictCursor
            ) as cur:

                await cur.execute(
                    """
                    SELECT *
                    FROM nanz_classes
                    WHERE class_id = %s
                    """,
                    (class_id,)
                )

                cls = await cur.fetchone()

                if not cls:

                    return await ctx.send(
                        "❌ Kelas tidak ditemukan."
                    )

                await cur.execute(
                    """
                    SELECT user_id
                    FROM nanz_class_members
                    WHERE class_id = %s
                    """,
                    (class_id,)
                )

                members = await cur.fetchall()

                # Hapus member database
                await cur.execute(
                    """
                    DELETE FROM nanz_class_members
                    WHERE class_id = %s
                    """,
                    (class_id,)
                )

                # Status dibubarkan
                await cur.execute(
                    """
                    UPDATE nanz_classes
                    SET status = 'Dissolved'
                    WHERE class_id = %s
                    """,
                    (class_id,)
                )

        finally:
            conn.close()

        # Remove role dari member
        role = ctx.guild.get_role(
            cls["role_id"]
        )

        if role:

            for data in members:

                member = ctx.guild.get_member(
                    data["user_id"]
                )

                if member:

                    try:
                        await member.remove_roles(
                            role
                        )

                    except Exception:
                        pass

            try:
                await role.delete(
                    reason="Kelas nanZ dibubarkan"
                )

            except Exception:
                pass

        # VC
        vc = ctx.guild.get_channel(
            cls["vc_id"]
        )

        if vc:

            try:
                await vc.delete(
                    reason="Kelas nanZ dibubarkan"
                )

            except Exception:
                pass

        # Panel
        if cls["panel_message_id"]:

            channel = ctx.guild.get_channel(
                DAFTAR_KELAS_CHANNEL_ID
            )

            if channel:

                try:

                    message = await channel.fetch_message(
                        cls["panel_message_id"]
                    )

                    await message.delete()

                except Exception:
                    pass

        await send_log(
            ctx.guild,
            f"🗑️ Kelas **{cls['name']}** dibubarkan oleh "
            f"{ctx.author.mention}."
        )

        await ctx.send(
            f"🗑️ Kelas **{cls['name']}** berhasil dibubarkan."
        )

    # =====================================================
    # STARTUP PERSISTENT BILLING
    # =====================================================

    @commands.Cog.listener()
    async def on_ready(self):

        conn = await get_db()

        try:

            async with conn.cursor(
                aiomysql.DictCursor
            ) as cur:

                await cur.execute(
                    """
                    SELECT class_id
                    FROM nanz_classes
                    WHERE status IN
                    ('Active','Grace')
                    """
                )

                rows = await cur.fetchall()

        finally:
            conn.close()

        for row in rows:

            self.bot.add_view(
                BillingView(
                    row["class_id"]
                )
            )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        NanzKelasAdmin(bot)
    )