import asyncio
import logging
from datetime import datetime, timedelta, timezone

import aiomysql
import discord
from discord.ext import commands, tasks


# =========================================================
# CONFIG
# =========================================================

GUILD_ID = 1406557880475320340

DAFTAR_KELAS_CHANNEL_ID = 1552604329435856986
REQUEST_GABUNG_CHANNEL_ID = 1552604968643731546
LOG_KELAS_CHANNEL_ID = 1552605106724405338

MAX_MEMBER = 20

CLASS_PRICE = 500_000
CLASS_PERIOD_DAYS = 30
GRACE_DAYS = 7

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "nanzuser",
    "password": "nanzserversolid",
    "db": "nanz_bot",
    "autocommit": True,
}


# =========================================================
# LOG
# =========================================================

log = logging.getLogger("nanz.kelas.admin")


# =========================================================
# TIME
# =========================================================

def utc_now():
    return datetime.now(timezone.utc)


def db_now():
    return utc_now().replace(tzinfo=None)


def db_dt(value):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


# =========================================================
# DATABASE
# =========================================================

async def get_db():
    return await aiomysql.connect(**DB_CONFIG)


async def fetch_one(query, args=()):
    conn = await get_db()

    try:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(query, args)
            return await cur.fetchone()
    finally:
        conn.close()


async def fetch_all(query, args=()):
    conn = await get_db()

    try:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(query, args)
            return await cur.fetchall()
    finally:
        conn.close()


async def execute(query, args=()):
    conn = await get_db()

    try:
        async with conn.cursor() as cur:
            await cur.execute(query, args)
            return cur.lastrowid
    finally:
        conn.close()


# =========================================================
# CLASS HELPERS
# =========================================================

async def get_class(class_id):
    return await fetch_one(
        """
        SELECT *
        FROM nanz_classes
        WHERE class_id=%s
        LIMIT 1
        """,
        (class_id,),
    )


async def member_count(class_id):
    row = await fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM nanz_class_members
        WHERE class_id=%s
        """,
        (class_id,),
    )

    return int(row["total"]) if row else 0


async def update_panel(bot, class_id):
    """
    Memanggil fungsi update panel dari ticket cog.
    """

    ticket_cog = bot.get_cog("NanzKelasCog")

    if ticket_cog and hasattr(ticket_cog, "update_public_panel"):
        await ticket_cog.update_public_panel(class_id)


async def update_public_panel(bot, class_id):
    """
    Import lokal untuk menghindari circular import.
    """

    try:
        from cogs.nanzkelasticket import update_public_panel as updater

        await updater(
            bot,
            class_id,
        )

    except Exception:
        log.exception(
            "Gagal update public panel class_id=%s",
            class_id,
        )


# =========================================================
# LOGGING
# =========================================================

async def send_log(bot, guild, message):
    channel = guild.get_channel(
        LOG_KELAS_CHANNEL_ID
    )

    if not channel:
        return

    try:
        await channel.send(message)
    except Exception:
        log.exception("Gagal mengirim log kelas.")


# =========================================================
# BILLING VIEW
# =========================================================

class BillingView(discord.ui.View):
    def __init__(self, class_id):
        super().__init__(timeout=None)

        self.class_id = int(class_id)

        self.paid_button = discord.ui.Button(
            label="Tandai Lunas",
            emoji="✅",
            style=discord.ButtonStyle.success,
            custom_id=f"nanz:billing:paid:{self.class_id}",
        )

        self.paid_button.callback = self.mark_paid

        self.add_item(self.paid_button)

    async def mark_paid(self, interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ Hanya Staff/Management yang dapat menandai pembayaran.",
                ephemeral=True,
            )
            return

        cls = await get_class(
            self.class_id
        )

        if not cls:
            await interaction.response.send_message(
                "❌ Kelas tidak ditemukan.",
                ephemeral=True,
            )
            return

        if cls["status"] == "Inactive":
            await interaction.response.send_message(
                "❌ Kelas sudah Inactive. "
                "Gunakan perpanjang kelas untuk mengaktifkannya kembali.",
                ephemeral=True,
            )
            return

        old_due = db_dt(
            cls["due_date"]
        )

        now = utc_now()

        # -------------------------------------------------
        # PERTAHANKAN SIKLUS
        # -------------------------------------------------

        if old_due < now:
            base_due = old_due

            while base_due <= now:
                base_due += timedelta(
                    days=CLASS_PERIOD_DAYS
                )
        else:
            base_due = old_due

        new_due = base_due
        new_grace = new_due + timedelta(
            days=GRACE_DAYS
        )

        await execute(
            """
            UPDATE nanz_classes
            SET
                due_date=%s,
                grace_until=%s,
                status='Active',
                billing_status='Paid',
                billing_message_id=NULL,
                last_billing_notice=NULL
            WHERE class_id=%s
            """,
            (
                new_due.replace(tzinfo=None),
                new_grace.replace(tzinfo=None),
                self.class_id,
            ),
        )

        # -------------------------------------------------
        # EDIT BILLING MESSAGE
        # -------------------------------------------------

        try:
            await interaction.message.edit(
                embed=discord.Embed(
                    title="💰 Tagihan Kelas — LUNAS",
                    description=(
                        f"Pembayaran kelas **{cls['name']}** "
                        "telah ditandai lunas."
                    ),
                    color=discord.Color.green(),
                ),
                view=None,
            )
        except Exception:
            pass

        await update_public_panel(
            interaction.client,
            self.class_id,
        )

        await send_log(
            interaction.client,
            interaction.guild,
            f"💰 Tagihan **{cls['name']}** ditandai lunas oleh "
            f"<@{interaction.user.id}>. "
            f"Aktif sampai <t:{int(new_due.timestamp())}:D>.",
        )

        await interaction.response.send_message(
            f"✅ Pembayaran **{cls['name']}** ditandai lunas.\n"
            f"Aktif sampai <t:{int(new_due.timestamp())}:D>.",
            ephemeral=True,
        )


# =========================================================
# BILLING COG
# =========================================================

class NanzKelasAdmin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Dipakai ticket cog
        bot.REQUEST_GABUNG_CHANNEL_ID = REQUEST_GABUNG_CHANNEL_ID
        bot.LOG_KELAS_CHANNEL_ID = LOG_KELAS_CHANNEL_ID

        self.billing_loop.start()

    def cog_unload(self):
        self.billing_loop.cancel()

    async def cog_load(self):
        # -------------------------------------------------
        # RESTORE BILLING VIEWS
        # -------------------------------------------------

        classes = await fetch_all(
            """
            SELECT class_id
            FROM nanz_classes
            WHERE status IN ('Active', 'Grace')
              AND billing_message_id IS NOT NULL
            """
        )

        for cls in classes:
            self.bot.add_view(
                BillingView(
                    int(cls["class_id"])
                )
            )

        log.info(
            "Billing View kelas berhasil direstore."
        )

    # =====================================================
    # BILLING LOOP
    # =====================================================

    @tasks.loop(minutes=30)
    async def billing_loop(self):
        try:
            classes = await fetch_all(
                """
                SELECT *
                FROM nanz_classes
                WHERE status IN ('Active', 'Grace')
                """
            )

            for cls in classes:
                try:
                    await self.process_class_billing(
                        cls
                    )
                except Exception:
                    log.exception(
                        "Billing gagal untuk class_id=%s",
                        cls["class_id"],
                    )

        except Exception:
            log.exception(
                "Billing loop gagal."
            )

    @billing_loop.before_loop
    async def before_billing_loop(self):
        await self.bot.wait_until_ready()

    # =====================================================
    # PROCESS BILLING
    # =====================================================

    async def process_class_billing(self, cls):
        class_id = int(cls["class_id"])

        due = db_dt(
            cls["due_date"]
        )

        grace_until = db_dt(
            cls["grace_until"]
        )

        now = utc_now()

        if not due or not grace_until:
            return

        # -------------------------------------------------
        # INACTIVE
        # -------------------------------------------------

        if now >= grace_until:
            if cls["status"] != "Inactive":
                await self.set_inactive(
                    cls
                )

            return

        # -------------------------------------------------
        # GRACE
        # -------------------------------------------------

        if now >= due:
            if cls["status"] != "Grace":
                await self.set_grace(
                    cls
                )

            return

        # -------------------------------------------------
        # H-3
        # -------------------------------------------------

        h3 = due - timedelta(days=3)

        if now >= h3:
            await self.send_billing_if_needed(
                cls,
                stage="H-3",
            )

    # =====================================================
    # BILLING MESSAGE
    # =====================================================

    async def send_billing_if_needed(
        self,
        cls,
        stage,
    ):
        last_notice = db_dt(
            cls["last_billing_notice"]
        )

        now = utc_now()

        # Jangan spam
        if last_notice:
            if (
                now - last_notice
            ).total_seconds() < 24 * 60 * 60:
                return

        guild = self.bot.get_guild(
            int(cls["guild_id"])
        )

        if not guild:
            return

        vc = guild.get_channel(
            int(cls["vc_id"])
        )

        role = guild.get_role(
            int(cls["role_id"])
        )

        if not vc:
            return

        due = db_dt(
            cls["due_date"]
        )

        if stage == "H-3":
            title = "💰 Tagihan Kelas"
            color = discord.Color.orange()

            description = (
                f"Tagihan kelas **{cls['name']}** akan jatuh tempo "
                f"<t:{int(due.timestamp())}:R>.\n\n"
                f"**Biaya:** `{CLASS_PRICE:,}` OwO Cash\n"
                f"**Jatuh tempo:** <t:{int(due.timestamp())}:F>\n\n"
                "Silakan lakukan pembayaran dan tunggu Staff "
                "memverifikasi pembayaran."
            )

        elif stage == "H-1":
            title = "⚠️ Pengingat Tagihan Kelas"
            color = discord.Color.gold()

            description = (
                f"Tagihan kelas **{cls['name']}** akan jatuh tempo "
                f"<t:{int(due.timestamp())}:R>.\n\n"
                f"**Biaya:** `{CLASS_PRICE:,}` OwO Cash\n"
                f"**Jatuh tempo:** <t:{int(due.timestamp())}:F>"
            )

        else:
            title = "⚠️ Masa Grace Kelas"
            color = discord.Color.gold()

            grace = db_dt(
                cls["grace_until"]
            )

            description = (
                f"Tagihan **{cls['name']}** belum tercatat lunas.\n\n"
                "Kelas sekarang memasuki **Grace Period 7 hari**.\n\n"
                f"**Biaya:** `{CLASS_PRICE:,}` OwO Cash\n"
                f"**Grace sampai:** <t:{int(grace.timestamp())}:F>\n\n"
                "Jika belum dibayar sampai masa grace berakhir, "
                "status kelas akan menjadi **Inactive**."
            )

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=now,
        )

        embed.add_field(
            name="Status Pembayaran",
            value="Belum Lunas",
            inline=True,
        )

        embed.add_field(
            name="Kelas",
            value=cls["name"],
            inline=True,
        )

        content = role.mention if role else None

        view = BillingView(
            int(cls["class_id"])
        )

        message = await vc.send(
            content=content,
            embed=embed,
            view=view,
        )

        await execute(
            """
            UPDATE nanz_classes
            SET
                billing_message_id=%s,
                billing_status='Unpaid',
                last_billing_notice=%s
            WHERE class_id=%s
            """,
            (
                str(message.id),
                db_now(),
                cls["class_id"],
            ),
        )

    # =====================================================
    # GRACE
    # =====================================================

    async def set_grace(self, cls):
        await execute(
            """
            UPDATE nanz_classes
            SET
                status='Grace',
                billing_status='Unpaid'
            WHERE class_id=%s
            """,
            (
                cls["class_id"],
            ),
        )

        await self.send_billing_if_needed(
            cls,
            stage="Grace",
        )

        await update_public_panel(
            self.bot,
            int(cls["class_id"]),
        )

        guild = self.bot.get_guild(
            int(cls["guild_id"])
        )

        if guild:
            await send_log(
                self.bot,
                guild,
                f"⚠️ Kelas **{cls['name']}** memasuki "
                f"Grace Period.",
            )

    # =====================================================
    # INACTIVE
    # =====================================================

    async def set_inactive(self, cls):
        await execute(
            """
            UPDATE nanz_classes
            SET
                status='Inactive',
                billing_status='Unpaid'
            WHERE class_id=%s
            """,
            (
                cls["class_id"],
            ),
        )

        await update_public_panel(
            self.bot,
            int(cls["class_id"]),
        )

        guild = self.bot.get_guild(
            int(cls["guild_id"])
        )

        if guild:
            await send_log(
                self.bot,
                guild,
                f"🔴 Kelas **{cls['name']}** menjadi "
                "Inactive karena tagihan tidak dibayar "
                "sampai Grace Period berakhir.",
            )

    # =====================================================
    # MANUAL EXTEND
    # =====================================================

    @commands.command(
        name="perpanjang_kelas"
    )
    @commands.has_guild_permissions(
        manage_guild=True
    )
    async def perpanjang_kelas(
        self,
        ctx,
        class_id: int,
    ):
        cls = await get_class(
            class_id
        )

        if not cls:
            await ctx.send(
                "❌ Class ID tidak ditemukan."
            )
            return

        due = db_dt(
            cls["due_date"]
        )

        now = utc_now()

        if due < now:
            while due <= now:
                due += timedelta(
                    days=CLASS_PERIOD_DAYS
                )
        else:
            due += timedelta(
                days=CLASS_PERIOD_DAYS
            )

        grace = due + timedelta(
            days=GRACE_DAYS
        )

        await execute(
            """
            UPDATE nanz_classes
            SET
                due_date=%s,
                grace_until=%s,
                status='Active',
                billing_status='Paid',
                billing_message_id=NULL,
                last_billing_notice=NULL
            WHERE class_id=%s
            """,
            (
                due.replace(tzinfo=None),
                grace.replace(tzinfo=None),
                class_id,
            ),
        )

        await update_public_panel(
            self.bot,
            class_id,
        )

        await send_log(
            self.bot,
            ctx.guild,
            f"🔄 Kelas **{cls['name']}** diperpanjang oleh "
            f"{ctx.author.mention}.",
        )

        await ctx.send(
            f"✅ **{cls['name']}** diperpanjang.\n"
            f"Aktif sampai <t:{int(due.timestamp())}:F>."
        )

    # =====================================================
    # EXIT CLASS
    # =====================================================

    @commands.command(
        name="keluar_kelas"
    )
    async def keluar_kelas(
        self,
        ctx,
    ):
        cls = await fetch_one(
            """
            SELECT c.*
            FROM nanz_class_members m
            JOIN nanz_classes c
                ON c.class_id=m.class_id
            WHERE m.user_id=%s
            LIMIT 1
            """,
            (
                ctx.author.id,
            ),
        )

        if not cls:
            await ctx.send(
                "❌ Kamu tidak tergabung dalam kelas."
            )
            return

        if ctx.author.id == int(
            cls["owner_id"]
        ):
            await ctx.send(
                "❌ Pemilik kelas tidak dapat keluar sendiri.\n"
                "Hubungi Management untuk transfer atau membubarkan kelas."
            )
            return

        await execute(
            """
            DELETE FROM nanz_class_members
            WHERE class_id=%s
              AND user_id=%s
            """,
            (
                cls["class_id"],
                ctx.author.id,
            ),
        )

        role = ctx.guild.get_role(
            int(cls["role_id"])
        )

        if role:
            try:
                await ctx.author.remove_roles(
                    role,
                    reason="Keluar kelas nanZ",
                )
            except Exception:
                pass

        await update_public_panel(
            self.bot,
            int(cls["class_id"]),
        )

        await send_log(
            self.bot,
            ctx.guild,
            f"🚪 {ctx.author.mention} keluar dari "
            f"kelas **{cls['name']}**.",
        )

        await ctx.send(
            f"✅ Kamu telah keluar dari **{cls['name']}**."
        )

    # =====================================================
    # KICK
    # =====================================================

    @commands.command(
        name="kick_kelas"
    )
    @commands.has_guild_permissions(
        manage_guild=True
    )
    async def kick_kelas(
        self,
        ctx,
        member: discord.Member,
    ):
        cls = await fetch_one(
            """
            SELECT c.*
            FROM nanz_class_members m
            JOIN nanz_classes c
                ON c.class_id=m.class_id
            WHERE m.user_id=%s
            LIMIT 1
            """,
            (
                member.id,
            ),
        )

        if not cls:
            await ctx.send(
                "❌ Member tersebut tidak tergabung dalam kelas."
            )
            return

        if member.id == int(
            cls["owner_id"]
        ):
            await ctx.send(
                "❌ Pemilik kelas tidak dapat di-kick."
            )
            return

        await execute(
            """
            DELETE FROM nanz_class_members
            WHERE class_id=%s
              AND user_id=%s
            """,
            (
                cls["class_id"],
                member.id,
            ),
        )

        role = ctx.guild.get_role(
            int(cls["role_id"])
        )

        if role:
            try:
                await member.remove_roles(
                    role,
                    reason="Kick anggota kelas nanZ",
                )
            except Exception:
                pass

        await update_public_panel(
            self.bot,
            int(cls["class_id"]),
        )

        await send_log(
            self.bot,
            ctx.guild,
            f"👢 {member.mention} dikeluarkan dari "
            f"kelas **{cls['name']}** oleh "
            f"{ctx.author.mention}.",
        )

        await ctx.send(
            f"✅ {member.mention} telah dikeluarkan dari "
            f"**{cls['name']}**."
        )

    # =====================================================
    # DELETE CLASS
    # =====================================================

    @commands.command(
        name="hapus_kelas"
    )
    @commands.has_guild_permissions(
        manage_guild=True
    )
    async def hapus_kelas(
        self,
        ctx,
        class_id: int,
    ):
        cls = await get_class(
            class_id
        )

        if not cls:
            await ctx.send(
                "❌ Class ID tidak ditemukan."
            )
            return

        await ctx.send(
            f"⚠️ Kamu akan membubarkan kelas **{cls['name']}**.\n"
            "Ketik `CONFIRM` untuk melanjutkan."
        )

        def check(message):
            return (
                message.author.id == ctx.author.id
                and message.channel.id == ctx.channel.id
            )

        try:
            confirmation = await self.bot.wait_for(
                "message",
                timeout=30,
                check=check,
            )
        except asyncio.TimeoutError:
            await ctx.send(
                "❌ Konfirmasi habis."
            )
            return

        if confirmation.content.upper() != "CONFIRM":
            await ctx.send(
                "❌ Pembubaran dibatalkan."
            )
            return

        # -------------------------------------------------
        # DELETE PANEL
        # -------------------------------------------------

        channel = ctx.guild.get_channel(
            DAFTAR_KELAS_CHANNEL_ID
        )

        if channel and cls["panel_message_id"]:
            try:
                message = await channel.fetch_message(
                    int(cls["panel_message_id"])
                )

                await message.delete()

            except Exception:
                pass

        # -------------------------------------------------
        # DELETE VC
        # -------------------------------------------------

        vc = ctx.guild.get_channel(
            int(cls["vc_id"])
        )

        if vc:
            try:
                await vc.delete(
                    reason="Kelas dibubarkan"
                )
            except Exception:
                pass

        # -------------------------------------------------
        # DELETE ROLE
        # -------------------------------------------------

        role = ctx.guild.get_role(
            int(cls["role_id"])
        )

        if role:
            try:
                await role.delete(
                    reason="Kelas dibubarkan"
                )
            except Exception:
                pass

        # -------------------------------------------------
        # UPDATE CLASS
        # -------------------------------------------------

        await execute(
            """
            UPDATE nanz_classes
            SET status='Dissolved'
            WHERE class_id=%s
            """,
            (
                class_id,
            ),
        )

        # -------------------------------------------------
        # CLEAN MEMBERS
        # -------------------------------------------------

        await execute(
            """
            DELETE FROM nanz_class_members
            WHERE class_id=%s
            """,
            (
                class_id,
            ),
        )

        # -------------------------------------------------
        # PENDING REQUEST
        # -------------------------------------------------

        await execute(
            """
            UPDATE nanz_class_join_requests
            SET
                status='Cancelled',
                processed_at=%s,
                processed_by=%s
            WHERE class_id=%s
              AND status='Pending'
            """,
            (
                db_now(),
                ctx.author.id,
                class_id,
            ),
        )

        await send_log(
            self.bot,
            ctx.guild,
            f"🗑️ Kelas **{cls['name']}** "
            f"(ID `{class_id}`) dibubarkan oleh "
            f"{ctx.author.mention}.",
        )

        await ctx.send(
            f"🗑️ Kelas **{cls['name']}** berhasil dibubarkan."
        )


async def setup(bot):
    await bot.add_cog(
        NanzKelasAdmin(bot)
    )