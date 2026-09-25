import logging
from datetime import datetime, timedelta, timezone

import aiomysql
import discord
from discord.ext import commands, tasks

from cogs.nanzkelasticket import (
    DAFTAR_KELAS_CHANNEL_ID,
    LOG_KELAS_CHANNEL_ID,
    STAFF_ROLE_ID,
    can_manage_class,
    db_dt,
    db_now,
    get_class,
    get_member_count,
    has_staff_role,
    update_public_panel,
)


# =========================================================
# CONFIG
# =========================================================

GUILD_ID = 1406557880475320340
REQUEST_GABUNG_CHANNEL_ID = 1552604968643731546

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


log = logging.getLogger("nanz.kelas.admin")


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
# LOGGING
# =========================================================

async def send_log(bot, guild, message):
    if not guild:
        return

    channel = guild.get_channel(LOG_KELAS_CHANNEL_ID)
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

        button = discord.ui.Button(
            label="Tandai Lunas",
            emoji="✅",
            style=discord.ButtonStyle.success,
            custom_id=f"nanz:billing:paid:{self.class_id}",
        )
        button.callback = self.mark_paid
        self.add_item(button)

    async def mark_paid(self, interaction):
        if not has_staff_role(interaction.user):
            await interaction.response.send_message(
                "🔒 Hanya Staff atau Administrator yang dapat memproses pembayaran.",
                ephemeral=True,
            )
            return

        cls = await get_class(self.class_id)
        if not cls:
            await interaction.response.send_message("❌ Kelas tidak ditemukan.", ephemeral=True)
            return

        if cls["status"] == "Inactive":
            await interaction.response.send_message(
                "❌ Kelas sudah Inactive. Gunakan panel Staff untuk memperpanjang.",
                ephemeral=True,
            )
            return

        old_due = db_dt(cls["due_date"])
        now = datetime.now(timezone.utc)

        if not old_due:
            old_due = now

        if old_due < now:
            base_due = old_due
            while base_due <= now:
                base_due += timedelta(days=CLASS_PERIOD_DAYS)
        else:
            base_due = old_due

        new_due = base_due
        new_grace = new_due + timedelta(days=GRACE_DAYS)

        await execute(
            """
            UPDATE nanz_classes
            SET due_date=%s,
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

        try:
            await interaction.message.edit(
                embed=discord.Embed(
                    title="💰 Tagihan Kelas — LUNAS",
                    description=f"Pembayaran **{cls['name']}** telah ditandai lunas.",
                    color=discord.Color.green(),
                ),
                view=None,
            )
        except (discord.NotFound, discord.HTTPException):
            pass

        await update_public_panel(interaction.client, self.class_id)
        await send_log(
            interaction.client,
            interaction.guild,
            f"💰 Tagihan **{cls['name']}** ditandai lunas oleh {interaction.user.mention}. "
            f"Aktif sampai <t:{int(new_due.timestamp())}:F>.",
        )

        await interaction.response.send_message(
            f"✅ Pembayaran **{cls['name']}** ditandai lunas.\n"
            f"Aktif sampai <t:{int(new_due.timestamp())}:F>.",
            ephemeral=True,
        )


# =========================================================
# BILLING COG
# =========================================================

class NanzKelasAdmin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.REQUEST_GABUNG_CHANNEL_ID = REQUEST_GABUNG_CHANNEL_ID
        bot.LOG_KELAS_CHANNEL_ID = LOG_KELAS_CHANNEL_ID

    async def cog_load(self):
        classes = await fetch_all(
            """
            SELECT class_id
            FROM nanz_classes
            WHERE status IN ('Active','Grace')
              AND billing_message_id IS NOT NULL
            """
        )

        for cls in classes:
            self.bot.add_view(BillingView(int(cls["class_id"])))

        if not self.billing_loop.is_running():
            self.billing_loop.start()

        log.info("Billing View kelas berhasil direstore.")

    def cog_unload(self):
        if self.billing_loop.is_running():
            self.billing_loop.cancel()

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
                WHERE status IN ('Active','Grace')
                """
            )

            for cls in classes:
                try:
                    await self.process_class_billing(cls)
                except Exception:
                    log.exception("Billing gagal untuk class_id=%s", cls["class_id"])
        except Exception:
            log.exception("Billing loop gagal.")

    @billing_loop.before_loop
    async def before_billing_loop(self):
        await self.bot.wait_until_ready()

    # =====================================================
    # BILLING PROCESS
    # =====================================================

    async def process_class_billing(self, cls):
        due = db_dt(cls["due_date"])
        grace_until = db_dt(cls["grace_until"])
        now = datetime.now(timezone.utc)

        if not due or not grace_until:
            return

        if now >= grace_until:
            if cls["status"] != "Inactive":
                await self.set_inactive(cls)
            return

        if now >= due:
            if cls["status"] != "Grace":
                await self.set_grace(cls)
            return

        if now >= due - timedelta(days=3):
            await self.send_billing_if_needed(cls, stage="H-3")

    async def send_billing_if_needed(self, cls, stage):
        last_notice = db_dt(cls["last_billing_notice"])
        now = datetime.now(timezone.utc)

        if last_notice and (now - last_notice).total_seconds() < 24 * 60 * 60:
            return

        guild = self.bot.get_guild(int(cls["guild_id"]))
        if not guild:
            return

        # Discord class VC yang dipakai sistem saat ini tetap menjadi lokasi
        # notifikasi billing, mengikuti implementasi lama yang sudah berjalan.
        vc = guild.get_channel(int(cls["vc_id"])) if cls.get("vc_id") else None
        role = guild.get_role(int(cls["role_id"])) if cls.get("role_id") else None
        if not vc:
            return

        due = db_dt(cls["due_date"])

        if stage == "H-3":
            title = "💰 Tagihan Kelas"
            color = discord.Color.orange()
            description = (
                f"Tagihan kelas **{cls['name']}** akan jatuh tempo <t:{int(due.timestamp())}:R>.\n\n"
                f"**Biaya:** `{CLASS_PRICE:,}` OwO Cash\n"
                f"**Jatuh tempo:** <t:{int(due.timestamp())}:F>\n\n"
                "Silakan lakukan pembayaran dan tunggu Staff memverifikasi pembayaran."
            )
        else:
            title = "⚠️ Masa Grace Kelas"
            color = discord.Color.gold()
            grace = db_dt(cls["grace_until"])
            description = (
                f"Tagihan **{cls['name']}** belum tercatat lunas.\n\n"
                "Kelas sekarang memasuki **Grace Period 7 hari**.\n\n"
                f"**Biaya:** `{CLASS_PRICE:,}` OwO Cash\n"
                f"**Grace sampai:** <t:{int(grace.timestamp())}:F>\n\n"
                "Jika belum dibayar sampai masa grace berakhir, status kelas menjadi **Inactive**."
            )

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=now,
        )
        embed.add_field(name="Status Pembayaran", value="Belum Lunas", inline=True)
        embed.add_field(name="Kelas", value=cls["name"], inline=True)

        try:
            message = await vc.send(
                content=role.mention if role else None,
                embed=embed,
                view=BillingView(int(cls["class_id"])),
            )
        except Exception:
            log.exception("Gagal mengirim billing message untuk class_id=%s", cls["class_id"])
            return

        await execute(
            """
            UPDATE nanz_classes
            SET billing_message_id=%s,
                billing_status='Unpaid',
                last_billing_notice=%s
            WHERE class_id=%s
            """,
            (str(message.id), db_now(), cls["class_id"]),
        )

    async def set_grace(self, cls):
        await execute(
            """
            UPDATE nanz_classes
            SET status='Grace', billing_status='Unpaid'
            WHERE class_id=%s
            """,
            (cls["class_id"],),
        )

        await self.send_billing_if_needed(cls, stage="Grace")
        await update_public_panel(self.bot, int(cls["class_id"]))

        guild = self.bot.get_guild(int(cls["guild_id"]))
        if guild:
            await send_log(
                self.bot,
                guild,
                f"⚠️ Kelas **{cls['name']}** memasuki Grace Period.",
            )

    async def set_inactive(self, cls):
        await execute(
            """
            UPDATE nanz_classes
            SET status='Inactive', billing_status='Unpaid'
            WHERE class_id=%s
            """,
            (cls["class_id"],),
        )

        await update_public_panel(self.bot, int(cls["class_id"]))

        guild = self.bot.get_guild(int(cls["guild_id"]))
        if guild:
            await send_log(
                self.bot,
                guild,
                f"🔴 Kelas **{cls['name']}** menjadi Inactive karena tagihan tidak dibayar sampai Grace Period berakhir.",
            )


async def setup(bot):
    await bot.add_cog(NanzKelasAdmin(bot))
