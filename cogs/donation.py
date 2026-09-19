import discord
from discord.ext import commands, tasks

import sqlite3
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path


# =========================================================
# CONFIG
# =========================================================

# =========================================================
# ROLE DONATUR
# =========================================================

DONATUR_RUPIAH_ROLE_ID = 1528766033509220572
DONATUR_OWO_ROLE_ID = 1528766890296611017


# =========================================================
# CHANNEL
# =========================================================

# Channel khusus transaksi / notifikasi donasi
DONATION_NOTIFICATION_CHANNEL_ID = 1528760374705262742

# Channel Live Top Donatur
LIVE_TOP_DONOR_CHANNEL_ID = 1550820849018474597


# =========================================================
# OWO BOT
# =========================================================

OWO_BOT_ID = 408785106942164992


# =========================================================
# THRESHOLD BENEFIT ROLE & PERMANEN
# =========================================================

# Target progress untuk mendapatkan role 30 hari. Tidak ada batas waktu
# untuk mengumpulkannya; progress hanya di-reset setelah role 30 hari habis.
RUPIAH_ROLE_THRESHOLD = 25_000
OWO_ROLE_THRESHOLD = 1_000_000

# Total kumulatif seumur hidup untuk status permanen.
RUPIAH_PERMANENT_THRESHOLD = 150_000
OWO_PERMANENT_THRESHOLD = 10_000_000


# =========================================================
# DURASI DONATUR
# =========================================================

DONOR_DURATION_DAYS = 30


# =========================================================
# STAFF ROLES
# =========================================================

STAFF_ROLE_IDS = {
    1417582562100117584,  # Guru Besar
    1453103644244316343,  # Moderator
    1467360501745844446,  # Pembina OSIS
    1427276194876751902,  # OSIS
}


# =========================================================
# DATABASE
# =========================================================

DB_PATH = Path("donation.db")


# =========================================================
# HELPER
# =========================================================

def utc_now():
    return datetime.now(timezone.utc)


def format_rupiah(amount: int):
    return f"Rp{amount:,}".replace(",", ".")


def format_owo(amount: int):
    return f"{amount:,}"


def is_staff(member: discord.Member):

    if not isinstance(member, discord.Member):
        return False

    return any(
        role.id in STAFF_ROLE_IDS
        for role in member.roles
    )


# =========================================================
# DATABASE
# =========================================================

class DonationDatabase:

    def __init__(self, path):

        self.path = path

        self.init_db()

    def connect(self):

        return sqlite3.connect(self.path)

    # -----------------------------------------------------
    # INIT DATABASE
    # -----------------------------------------------------

    def init_db(self):

        with self.connect() as conn:

            conn.execute("""
                CREATE TABLE IF NOT EXISTS donations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user_id INTEGER NOT NULL,

                    amount INTEGER NOT NULL,

                    method TEXT NOT NULL,

                    staff_id INTEGER,

                    recipient_id INTEGER,

                    created_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_owo (
                    message_id INTEGER PRIMARY KEY,

                    processed_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS donor_roles (
                    user_id INTEGER NOT NULL,

                    role_id INTEGER NOT NULL,

                    permanent INTEGER NOT NULL DEFAULT 0,

                    expires_at TEXT,

                    PRIMARY KEY (
                        user_id,
                        role_id
                    )
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS donor_benefit_cycles (
                    user_id INTEGER PRIMARY KEY,
                    rupiah_progress INTEGER NOT NULL DEFAULT 0,
                    owo_progress INTEGER NOT NULL DEFAULT 0,
                    rupiah_role_until TEXT,
                    owo_role_until TEXT,
                    updated_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_donations_user
                ON donations(user_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_donations_method
                ON donations(method)
            """)

            conn.commit()

    # -----------------------------------------------------
    # ADD DONATION
    # -----------------------------------------------------

    def add_donation(
        self,
        user_id,
        amount,
        method,
        staff_id=None,
        recipient_id=None
    ):

        created_at = utc_now().isoformat()

        with self.connect() as conn:

            cursor = conn.execute(
                """
                INSERT INTO donations (
                    user_id,
                    amount,
                    method,
                    staff_id,
                    recipient_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    amount,
                    method,
                    staff_id,
                    recipient_id,
                    created_at
                )
            )

            donation_id = cursor.lastrowid

            conn.commit()

        return donation_id

    # -----------------------------------------------------
    # GET USER TOTAL
    # -----------------------------------------------------

    def get_user_total(
        self,
        user_id,
        method
    ):

        with self.connect() as conn:

            result = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0)

                FROM donations

                WHERE user_id = ?
                AND method = ?
                """,
                (
                    user_id,
                    method
                )
            ).fetchone()

        return result[0] if result else 0

    # -----------------------------------------------------
    # GET USER TOTAL BY METHODS
    # -----------------------------------------------------

    def get_user_total_by_methods(
        self,
        user_id,
        methods
    ):

        if not methods:
            return 0

        placeholders = ",".join("?" for _ in methods)

        with self.connect() as conn:

            result = conn.execute(
                f"""
                SELECT COALESCE(SUM(amount), 0)
                FROM donations
                WHERE user_id = ?
                AND method IN ({placeholders})
                """,
                (user_id, *methods)
            ).fetchone()

        return result[0] if result else 0

    # -----------------------------------------------------
    # TOP DONORS
    # -----------------------------------------------------

    def get_top_donors(
        self,
        method,
        limit=10
    ):

        with self.connect() as conn:

            rows = conn.execute(
                """
                SELECT
                    user_id,
                    SUM(amount) AS total

                FROM donations

                WHERE method = ?

                GROUP BY user_id

                ORDER BY total DESC

                LIMIT ?
                """,
                (
                    method,
                    limit
                )
            ).fetchall()

        return rows

    # -----------------------------------------------------
    # TOTAL ALL
    # -----------------------------------------------------

    def get_total_all(
        self,
        method
    ):

        with self.connect() as conn:

            result = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0)

                FROM donations

                WHERE method = ?
                """,
                (method,)
            ).fetchone()

        return result[0] if result else 0

    # -----------------------------------------------------
    # TOP DONORS BY MULTIPLE METHODS
    # -----------------------------------------------------

    def get_top_donors_by_methods(
        self,
        methods,
        limit=10
    ):

        if not methods:
            return []

        placeholders = ",".join("?" for _ in methods)

        with self.connect() as conn:

            rows = conn.execute(
                f"""
                SELECT
                    user_id,
                    SUM(amount) AS total
                FROM donations
                WHERE method IN ({placeholders})
                GROUP BY user_id
                ORDER BY total DESC
                LIMIT ?
                """,
                (*methods, limit)
            ).fetchall()

        return rows

    # -----------------------------------------------------
    # TOTAL ALL BY MULTIPLE METHODS
    # -----------------------------------------------------

    def get_total_all_by_methods(
        self,
        methods
    ):

        if not methods:
            return 0

        placeholders = ",".join("?" for _ in methods)

        with self.connect() as conn:

            result = conn.execute(
                f"""
                SELECT COALESCE(SUM(amount), 0)
                FROM donations
                WHERE method IN ({placeholders})
                """,
                tuple(methods)
            ).fetchone()

        return result[0] if result else 0

    # -----------------------------------------------------
    # CHECK OWO MESSAGE
    # -----------------------------------------------------

    def owo_processed(
        self,
        message_id
    ):

        with self.connect() as conn:

            result = conn.execute(
                """
                SELECT 1

                FROM processed_owo

                WHERE message_id = ?
                """,
                (message_id,)
            ).fetchone()

        return result is not None

    # -----------------------------------------------------
    # MARK OWO MESSAGE
    # -----------------------------------------------------

    def mark_owo_processed(
        self,
        message_id
    ):

        with self.connect() as conn:

            conn.execute(
                """
                INSERT OR IGNORE INTO processed_owo (
                    message_id,
                    processed_at
                )
                VALUES (?, ?)
                """,
                (
                    message_id,
                    utc_now().isoformat()
                )
            )

            conn.commit()

    # -----------------------------------------------------
    # SAVE DONOR ROLE
    # -----------------------------------------------------

    def save_donor_role(
        self,
        user_id,
        role_id,
        permanent,
        expires_at
    ):

        with self.connect() as conn:

            conn.execute(
                """
                INSERT INTO donor_roles (
                    user_id,
                    role_id,
                    permanent,
                    expires_at
                )
                VALUES (?, ?, ?, ?)

                ON CONFLICT(
                    user_id,
                    role_id
                )

                DO UPDATE SET
                    permanent = excluded.permanent,
                    expires_at = excluded.expires_at
                """,
                (
                    user_id,
                    role_id,
                    1 if permanent else 0,
                    expires_at
                )
            )

            conn.commit()

    # -----------------------------------------------------
    # GET DONOR ROLE
    # -----------------------------------------------------

    def get_donor_role(
        self,
        user_id,
        role_id
    ):

        with self.connect() as conn:

            result = conn.execute(
                """
                SELECT
                    permanent,
                    expires_at

                FROM donor_roles

                WHERE user_id = ?
                AND role_id = ?
                """,
                (
                    user_id,
                    role_id
                )
            ).fetchone()

        return result

    # -----------------------------------------------------
    # GET EXPIRED ROLES
    # -----------------------------------------------------

    def get_expired_roles(self):

        with self.connect() as conn:

            rows = conn.execute(
                """
                SELECT
                    user_id,
                    role_id

                FROM donor_roles

                WHERE permanent = 0

                AND expires_at IS NOT NULL

                AND expires_at <= ?
                """,
                (
                    utc_now().isoformat(),
                )
            ).fetchall()

        return rows

    # -----------------------------------------------------
    # BENEFIT CYCLE
    # -----------------------------------------------------

    def get_benefit_cycle(self, user_id):

        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    rupiah_progress,
                    owo_progress,
                    rupiah_role_until,
                    owo_role_until
                FROM donor_benefit_cycles
                WHERE user_id = ?
                """,
                (user_id,)
            ).fetchone()

            if row is None:
                conn.execute(
                    """
                    INSERT INTO donor_benefit_cycles (
                        user_id,
                        rupiah_progress,
                        owo_progress,
                        rupiah_role_until,
                        owo_role_until,
                        updated_at
                    )
                    VALUES (?, 0, 0, NULL, NULL, ?)
                    """,
                    (user_id, utc_now().isoformat())
                )
                conn.commit()
                return {
                    "rupiah_progress": 0,
                    "owo_progress": 0,
                    "rupiah_role_until": None,
                    "owo_role_until": None
                }

        return {
            "rupiah_progress": row[0] or 0,
            "owo_progress": row[1] or 0,
            "rupiah_role_until": row[2],
            "owo_role_until": row[3]
        }

    def add_benefit_progress(self, user_id, method, amount):

        cycle = self.get_benefit_cycle(user_id)

        if method == "rupiah":
            progress = cycle["rupiah_progress"] + amount
            column = "rupiah_progress"
        else:
            progress = cycle["owo_progress"] + amount
            column = "owo_progress"

        with self.connect() as conn:
            conn.execute(
                f"""
                UPDATE donor_benefit_cycles
                SET {column} = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (progress, utc_now().isoformat(), user_id)
            )
            conn.commit()

        return progress

    def save_benefit_role_until(self, user_id, method, expires_at):

        column = (
            "rupiah_role_until"
            if method == "rupiah"
            else "owo_role_until"
        )

        with self.connect() as conn:
            conn.execute(
                f"""
                UPDATE donor_benefit_cycles
                SET {column} = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (expires_at, utc_now().isoformat(), user_id)
            )
            conn.commit()

    def reset_benefit_cycle(self, user_id, method):

        if method == "rupiah":
            progress_column = "rupiah_progress"
            until_column = "rupiah_role_until"
        else:
            progress_column = "owo_progress"
            until_column = "owo_role_until"

        with self.connect() as conn:
            conn.execute(
                f"""
                UPDATE donor_benefit_cycles
                SET {progress_column} = 0,
                    {until_column} = NULL,
                    updated_at = ?
                WHERE user_id = ?
                """,
                (utc_now().isoformat(), user_id)
            )
            conn.commit()

    def get_expired_benefit_cycles(self):

        now = utc_now().isoformat()

        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id, 'rupiah' AS method
                FROM donor_benefit_cycles
                WHERE rupiah_role_until IS NOT NULL
                AND rupiah_role_until <= ?

                UNION ALL

                SELECT user_id, 'owo' AS method
                FROM donor_benefit_cycles
                WHERE owo_role_until IS NOT NULL
                AND owo_role_until <= ?
                """,
                (now, now)
            ).fetchall()

        return rows

    # -----------------------------------------------------
    # DELETE ROLE RECORD
    # -----------------------------------------------------

    def delete_donor_role(
        self,
        user_id,
        role_id
    ):

        with self.connect() as conn:

            conn.execute(
                """
                DELETE FROM donor_roles

                WHERE user_id = ?
                AND role_id = ?
                """,
                (
                    user_id,
                    role_id
                )
            )

            conn.commit()


# =========================================================
# RUPIAH MEMBER SELECT
# =========================================================

class DonationMemberView(
    discord.ui.View
):

    def __init__(
        self,
        cog,
        staff_id
    ):

        super().__init__(
            timeout=120
        )

        self.cog = cog

        self.staff_id = staff_id

        self.user_select = discord.ui.UserSelect(
            placeholder="Pilih member yang berdonasi...",
            min_values=1,
            max_values=1
        )

        self.user_select.callback = (
            self.select_user
        )

        self.add_item(
            self.user_select
        )

    async def select_user(
        self,
        interaction: discord.Interaction
    ):

        donor = self.user_select.values[0]

        modal = DonationAmountModal(
            cog=self.cog,
            donor=donor,
            staff_id=self.staff_id
        )

        await interaction.response.send_modal(
            modal
        )


# =========================================================
# RUPIAH MODAL
# =========================================================

class DonationAmountModal(
    discord.ui.Modal
):

    def __init__(
        self,
        cog,
        donor,
        staff_id
    ):

        super().__init__(
            title="Input Donasi Rupiah"
        )

        self.cog = cog

        self.donor = donor

        self.staff_id = staff_id

        self.amount = discord.ui.TextInput(
            label="Nominal Donasi",
            placeholder="Contoh: 50000",
            required=True,
            min_length=1,
            max_length=15
        )

        self.add_item(
            self.amount
        )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        raw_amount = (
            self.amount.value
            .replace(".", "")
            .replace(",", "")
            .replace(" ", "")
        )

        if not raw_amount.isdigit():

            await interaction.response.send_message(
                "❌ Nominal harus berupa angka.",
                ephemeral=True
            )

            return

        amount = int(raw_amount)

        if amount <= 0:

            await interaction.response.send_message(
                "❌ Nominal harus lebih dari 0.",
                ephemeral=True
            )

            return

        # -------------------------------------------------
        # SIMPAN TRANSAKSI
        # -------------------------------------------------

        donation_id = self.cog.db.add_donation(
            user_id=self.donor.id,
            amount=amount,
            method="rupiah",
            staff_id=self.staff_id
        )

        # -------------------------------------------------
        # TOTAL KUMULATIF
        # -------------------------------------------------

        total = self.cog.db.get_user_total(
            self.donor.id,
            "rupiah"
        )

        # -------------------------------------------------
        # BENEFIT CYCLE / ROLE
        # -------------------------------------------------

        permanent = total >= RUPIAH_PERMANENT_THRESHOLD

        if permanent:
            role_status = await self.cog.set_donor_role(
                member=self.donor,
                role_id=DONATUR_RUPIAH_ROLE_ID,
                permanent=True
            )
        elif not self.cog._cycle_role_active(self.donor.id, "rupiah"):
            progress = self.cog.db.add_benefit_progress(
                self.donor.id, "rupiah", amount
            )

            if progress >= RUPIAH_ROLE_THRESHOLD:
                role_status = await self.cog.activate_benefit_role(
                    self.donor, "rupiah"
                )
            else:
                role_status = (
                    "⏳ Progress role: "
                    f"{format_rupiah(progress)} / "
                    f"{format_rupiah(RUPIAH_ROLE_THRESHOLD)}"
                )
        else:
            role_status = (
                "ℹ️ Role Donatur Rupiah masih aktif. "
                "Donasi ini tidak masuk progress siklus berikutnya."
            )

        # -------------------------------------------------
        # NOTIFICATION
        # -------------------------------------------------

        await self.cog.send_rupiah_notification(
            donor=self.donor,
            amount=amount,
            total=total,
            staff=interaction.user,
            donation_id=donation_id,
            permanent=permanent
        )

        # -------------------------------------------------
        # LEADERBOARD
        # -------------------------------------------------

        await self.cog.update_leaderboard()

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        await interaction.response.send_message(
            f"✅ **Donasi Rupiah berhasil dicatat!**\n\n"

            f"👤 Donatur: {self.donor.mention}\n"
            f"<:rupiah:1550869044104798208> Nominal: **{format_rupiah(amount)}**\n"
            f"📊 Total: **{format_rupiah(total)}**\n"
            f"🆔 Transaksi: `{donation_id}`\n\n"

            f"{role_status}",
            ephemeral=True
        )



# =========================================================
# MANUAL OWO MEMBER SELECT
# =========================================================

class ManualOwoMemberView(discord.ui.View):

    def __init__(self, cog, staff_id):
        super().__init__(timeout=120)

        self.cog = cog
        self.staff_id = staff_id

        self.user_select = discord.ui.UserSelect(
            placeholder="Pilih member donatur OwO lama...",
            min_values=1,
            max_values=1
        )

        self.user_select.callback = self.select_user
        self.add_item(self.user_select)

    async def select_user(self, interaction: discord.Interaction):

        donor = self.user_select.values[0]

        modal = ManualOwoAmountModal(
            cog=self.cog,
            donor=donor,
            staff_id=self.staff_id
        )

        await interaction.response.send_modal(modal)


# =========================================================
# MANUAL OWO MODAL
# =========================================================

class ManualOwoAmountModal(discord.ui.Modal):

    def __init__(self, cog, donor, staff_id):
        super().__init__(title="Input Donasi OwO Lama")

        self.cog = cog
        self.donor = donor
        self.staff_id = staff_id

        self.amount = discord.ui.TextInput(
            label="Nominal Donasi OwO",
            placeholder="Contoh: 1585000",
            required=True,
            min_length=1,
            max_length=20
        )

        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):

        raw_amount = (
            self.amount.value
            .replace(".", "")
            .replace(",", "")
            .replace(" ", "")
        )

        if not raw_amount.isdigit():
            await interaction.response.send_message(
                "❌ Nominal OwO harus berupa angka.",
                ephemeral=True
            )
            return

        amount = int(raw_amount)

        if amount <= 0:
            await interaction.response.send_message(
                "❌ Nominal OwO harus lebih dari 0.",
                ephemeral=True
            )
            return

        # -------------------------------------------------
        # SIMPAN DONASI MANUAL
        # -------------------------------------------------

        donation_id = self.cog.db.add_donation(
            user_id=self.donor.id,
            amount=amount,
            method="owo_manual",
            staff_id=self.staff_id
        )

        # -------------------------------------------------
        # TOTAL OWO KUMULATIF
        #
        # owo_manual ikut dihitung sebagai donasi OwO.
        # -------------------------------------------------

        total = self.cog.db.get_user_total_by_methods(
            self.donor.id,
            ("owo", "owo_manual")
        )

        permanent = total >= OWO_PERMANENT_THRESHOLD

        # -------------------------------------------------
        # BENEFIT CYCLE / ROLE
        # -------------------------------------------------

        if permanent:
            role_status = await self.cog.set_donor_role(
                member=self.donor,
                role_id=DONATUR_OWO_ROLE_ID,
                permanent=True
            )
        elif not self.cog._cycle_role_active(self.donor.id, "owo"):
            progress = self.cog.db.add_benefit_progress(
                self.donor.id, "owo", amount
            )

            if progress >= OWO_ROLE_THRESHOLD:
                role_status = await self.cog.activate_benefit_role(
                    self.donor, "owo"
                )
            else:
                role_status = (
                    "⏳ Progress role: "
                    f"{format_owo(progress)} / "
                    f"{format_owo(OWO_ROLE_THRESHOLD)} Owo"
                )
        else:
            role_status = (
                "ℹ️ Role Donatur OwO masih aktif. "
                "Donasi ini tidak masuk progress siklus berikutnya."
            )

        # -------------------------------------------------
        # NOTIFICATION
        # -------------------------------------------------

        await self.cog.send_manual_owo_notification(
            donor=self.donor,
            amount=amount,
            total=total,
            staff=interaction.user,
            donation_id=donation_id,
            permanent=permanent
        )

        # -------------------------------------------------
        # LEADERBOARD
        # -------------------------------------------------

        await self.cog.update_leaderboard()

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        await interaction.response.send_message(
            f"✅ **Donasi OwO lama berhasil dicatat!**\n\n"
            f"👤 Donatur: {self.donor.mention}\n"
            f"<:owo:1550868268020006932> Nominal: **{format_owo(amount)} cowoncy**\n"
            f"📊 Total OwO: **{format_owo(total)} cowoncy**\n"
            f"🆔 Transaksi: `#{donation_id}`\n\n"
            f"{role_status}",
            ephemeral=True
        )


# =========================================================
# DONATION PANEL
# =========================================================

class DonationPanelView(
    discord.ui.View
):

    def __init__(
        self,
        cog
    ):

        super().__init__(
            timeout=None
        )

        self.cog = cog

    @discord.ui.button(
        label="Input Donasi Rupiah",
        emoji="<:rupiah:1550869044104798208>",
        style=discord.ButtonStyle.success,
        custom_id="nanz_donation_input_rupiah"
    )
    async def donation_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        member = interaction.guild.get_member(
            interaction.user.id
        )

        if not member:
            await interaction.response.send_message(
                "❌ Member tidak ditemukan.",
                ephemeral=True
            )
            return

        allowed = (
            interaction.user.guild_permissions.administrator
            or is_staff(member)
        )

        if not allowed:
            await interaction.response.send_message(
                "❌ Kamu tidak memiliki akses ke panel donasi.",
                ephemeral=True
            )
            return

        view = DonationMemberView(
            cog=self.cog,
            staff_id=interaction.user.id
        )

        await interaction.response.send_message(
            "👤 **Pilih member yang melakukan donasi:**",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(
        label="Input Donasi OwO Lama",
        emoji="<:owo:1550868268020006932>",
        style=discord.ButtonStyle.primary,
        custom_id="nanz_donation_input_owo_manual"
    )
    async def manual_owo_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        member = interaction.guild.get_member(
            interaction.user.id
        )

        if not member:
            await interaction.response.send_message(
                "❌ Member tidak ditemukan.",
                ephemeral=True
            )
            return

        allowed = (
            interaction.user.guild_permissions.administrator
            or is_staff(member)
        )

        if not allowed:
            await interaction.response.send_message(
                "❌ Kamu tidak memiliki akses ke panel donasi.",
                ephemeral=True
            )
            return

        view = ManualOwoMemberView(
            cog=self.cog,
            staff_id=interaction.user.id
        )

        await interaction.response.send_message(
            "<:owo:1550868268020006932> **Pilih member yang memiliki riwayat donasi OwO:**\n"
            "Masukkan total donasi OwO lama yang ingin ditambahkan.",
            view=view,
            ephemeral=True
        )


# =========================================================
# DONATION COG
# =========================================================

class DonationControl(
    commands.Cog
):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

        self.db = DonationDatabase(
            DB_PATH
        )

        self.leaderboard_message_id = None

        self.expire_donor_roles.start()

    # =====================================================
    # UNLOAD
    # =====================================================

    def cog_unload(self):

        self.expire_donor_roles.cancel()

    # =====================================================
    # READY
    # =====================================================

    @commands.Cog.listener()
    async def on_ready(self):

        print(
            "[DONATION] Donation system ready."
        )

        try:

            await self.update_leaderboard()

        except Exception as e:

            print(
                f"[DONATION] Leaderboard error: {e}"
            )

    # =====================================================
    # SETUP PANEL
    # =====================================================

    @commands.command(
        name="setupdonation"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def setup_donation(
        self,
        ctx
    ):

        embed = discord.Embed(
            title="<:rupiah:1550869044104798208> DONASI NANZ",
            description=(
                "Terima kasih sudah mendukung "
                "**nanZ Server** ❤️\n\n"

                "### <:rupiah:1550869044104798208> DONASI RUPIAH\n"
                "Staff dapat mencatat donasi melalui "
                "tombol **Input Donasi Rupiah**.\n\n"

                "### <:owo:1550868268020006932> INPUT OWO LAMA\n"
                "Untuk donatur OwO sebelum sistem otomatis dibuat, "
                "staff dapat memasukkan riwayat donasi melalui "
                "tombol **Input Donasi OwO Lama**.\n\n"

                "🎖️ Kumpulkan donasi sampai minimal "
                f"**{format_rupiah(RUPIAH_ROLE_THRESHOLD)}**. Tidak ada batas waktu "
                "untuk mengumpulkannya. Setelah tercapai, role aktif **30 hari**.\n\n"

                "🔄 Setelah 30 hari role dicopot dan progress siklus kembali **0**. "
                "Donasi berikutnya mulai mengisi siklus baru.\n\n"

                "👑 Jika total kumulatif mencapai "
                f"**{format_rupiah(RUPIAH_PERMANENT_THRESHOLD)}**, "
                "role menjadi **PERMANEN**.\n\n"

                "### <:owo:1550868268020006932> DONASI OWO\n"
                "Donasi OwO akan dideteksi otomatis "
                "dari transaksi resmi OwO Bot. Riwayat donasi lama "
                "juga dapat ditambahkan secara manual melalui panel.\n\n"

                "🎖️ Kumpulkan donasi sampai minimal "
                f"**{format_owo(OWO_ROLE_THRESHOLD)} OwO**. Tidak ada batas waktu "
                "untuk mengumpulkannya. Setelah tercapai, role aktif **30 hari**.\n\n"

                "🔄 Setelah 30 hari role dicopot dan progress siklus kembali **0**. "
                "Donasi berikutnya mulai mengisi siklus baru.\n\n"

                "👑 Jika total kumulatif mencapai "
                f"**{format_owo(OWO_PERMANENT_THRESHOLD)} OwO**, "
                "role menjadi **PERMANEN**."
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(
            text="nanZ Server • Donation System"
        )

        await ctx.send(
            embed=embed,
            view=DonationPanelView(self)
        )

        await ctx.send(
            "✅ Panel donasi berhasil dibuat."
        )

    # =====================================================
    # BENEFIT ROLE CYCLE
    # =====================================================

    def _cycle_role_active(self, user_id, method):

        cycle = self.db.get_benefit_cycle(user_id)
        until = (
            cycle["rupiah_role_until"]
            if method == "rupiah"
            else cycle["owo_role_until"]
        )

        if not until:
            return False

        try:
            if datetime.fromisoformat(until) > utc_now():
                return True

            # Masa role sudah lewat. Reset progress sebelum donasi berikutnya
            # masuk ke siklus baru, walaupun task 10-menit belum sempat jalan.
            self.db.reset_benefit_cycle(user_id, method)
            return False
        except (TypeError, ValueError):
            self.db.reset_benefit_cycle(user_id, method)
            return False

    async def activate_benefit_role(self, member, method):

        role_id = (
            DONATUR_RUPIAH_ROLE_ID
            if method == "rupiah"
            else DONATUR_OWO_ROLE_ID
        )
        role = member.guild.get_role(role_id)

        if not role:
            return "⚠️ Role donor tidak ditemukan."

        if self._cycle_role_active(member.id, method):
            cycle = self.db.get_benefit_cycle(member.id)
            until = (
                cycle["rupiah_role_until"]
                if method == "rupiah"
                else cycle["owo_role_until"]
            )
            expiry = datetime.fromisoformat(until)
            return (
                "ℹ️ Role donor masih aktif sampai "
                f"<t:{int(expiry.timestamp())}:F>."
            )

        try:
            if role not in member.roles:
                await member.add_roles(
                    role,
                    reason="nanZ Donation - Benefit Cycle 30 Days"
                )

            expires_at = utc_now() + timedelta(days=DONOR_DURATION_DAYS)

            self.db.save_donor_role(
                user_id=member.id,
                role_id=role_id,
                permanent=False,
                expires_at=expires_at.isoformat()
            )

            self.db.save_benefit_role_until(
                member.id,
                method,
                expires_at.isoformat()
            )

            return (
                "🎖️ Role donor aktif **30 hari**.\n"
                f"⏰ Berakhir: <t:{int(expires_at.timestamp())}:F>"
            )

        except discord.Forbidden:
            return (
                "⚠️ Bot tidak dapat memberikan role.\n"
                "Pastikan role bot berada di atas role Donatur."
            )

    # =====================================================
    # SET DONOR ROLE
    # =====================================================

    async def set_donor_role(
        self,
        member,
        role_id,
        permanent=False
    ):

        role = member.guild.get_role(
            role_id
        )

        if not role:

            return (
                "⚠️ Role donor tidak ditemukan."
            )

        try:

            # ------------------------------------------------
            # PERMANENT
            # ------------------------------------------------

            if permanent:

                if role not in member.roles:

                    await member.add_roles(
                        role,
                        reason=(
                            "nanZ Donation - "
                            "Permanent Donor"
                        )
                    )

                self.db.save_donor_role(
                    user_id=member.id,
                    role_id=role_id,
                    permanent=True,
                    expires_at=None
                )

                return (
                    "👑 Role donor **PERMANEN**."
                )

            # ------------------------------------------------
            # TEMPORARY 30 DAYS
            # ------------------------------------------------

            expires_at = (
                utc_now()
                + timedelta(
                    days=DONOR_DURATION_DAYS
                )
            )

            if role not in member.roles:

                await member.add_roles(
                    role,
                    reason="nanZ Donation - 30 Days"
                )

            self.db.save_donor_role(
                user_id=member.id,
                role_id=role_id,
                permanent=False,
                expires_at=expires_at.isoformat()
            )

            return (
                "🎖️ Role donor aktif **30 hari**.\n"
                f"⏰ Berakhir: "
                f"<t:{int(expires_at.timestamp())}:F>"
            )

        except discord.Forbidden:

            return (
                "⚠️ Bot tidak dapat memberikan role.\n"
                "Pastikan role bot berada di atas "
                "role Donatur."
            )

    # =====================================================
    # OWO MESSAGE DETECTOR
    # =====================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message
    ):

        # -------------------------------------------------
        # HARUS DI CHANNEL DONASI
        # -------------------------------------------------

        if message.channel.id != (
            DONATION_NOTIFICATION_CHANNEL_ID
        ):

            return

        # -------------------------------------------------
        # HARUS DARI OWO BOT
        # -------------------------------------------------

        if message.author.id != OWO_BOT_ID:

            return

        # -------------------------------------------------
        # ANTI DUPLIKAT
        # -------------------------------------------------

        if self.db.owo_processed(
            message.id
        ):

            return

        # -------------------------------------------------
        # GABUNGKAN CONTENT + EMBED
        # -------------------------------------------------

        texts = []

        if message.content:

            texts.append(
                message.content
            )

        for embed in message.embeds:

            if embed.title:

                texts.append(
                    embed.title
                )

            if embed.description:

                texts.append(
                    embed.description
                )

            for field in embed.fields:

                if field.name:

                    texts.append(
                        field.name
                    )

                if field.value:

                    texts.append(
                        field.value
                    )

        full_text = "\n".join(texts)

        # -------------------------------------------------
        # RUMUS PESAN OWO
        #
        # **@DONOR** sent **1,585,000 cowoncy**
        # to **@RECIPIENT**!
        #
        # -------------------------------------------------

        amount_match = re.search(
            r"sent\s+\*{0,2}"
            r"([\d,]+)"
            r"\s+cowoncy"
            r"\*{0,2}\s+to",
            full_text,
            re.IGNORECASE
        )

        if not amount_match:

            return

        # -------------------------------------------------
        # NOMINAL
        # -------------------------------------------------

        raw_amount = (
            amount_match.group(1)
            .replace(",", "")
        )

        if not raw_amount.isdigit():

            return

        amount = int(
            raw_amount
        )

        if amount <= 0:

            return

        # -------------------------------------------------
        # MENTION
        #
        # Mention pertama = DONOR
        # Mention kedua = RECIPIENT
        # -------------------------------------------------

        mention_matches = re.findall(
            r"<@!?(\d+)>",
            full_text
        )

        if len(mention_matches) < 2:

            return

        donor_id = int(
            mention_matches[0]
        )

        recipient_id = int(
            mention_matches[1]
        )

        # -------------------------------------------------
        # GET MEMBER
        # -------------------------------------------------

        donor = message.guild.get_member(
            donor_id
        )

        recipient = message.guild.get_member(
            recipient_id
        )

        if not donor or not recipient:

            return

        # -------------------------------------------------
        # PENERIMA HARUS STAFF
        # -------------------------------------------------

        if not is_staff(recipient):

            return

        # -------------------------------------------------
        # SIMPAN PESAN SEBAGAI SUDAH DIPROSES
        # -------------------------------------------------

        self.db.mark_owo_processed(
            message.id
        )

        # -------------------------------------------------
        # SAVE DONATION
        # -------------------------------------------------

        donation_id = self.db.add_donation(
            user_id=donor.id,
            amount=amount,
            method="owo",
            recipient_id=recipient.id
        )

        # -------------------------------------------------
        # TOTAL KUMULATIF
        # -------------------------------------------------

        total = self.db.get_user_total_by_methods(
            donor.id,
            ("owo", "owo_manual")
        )

        # -------------------------------------------------
        # BENEFIT CYCLE / ROLE
        # -------------------------------------------------

        permanent = total >= OWO_PERMANENT_THRESHOLD

        if permanent:
            role_status = await self.set_donor_role(
                member=donor,
                role_id=DONATUR_OWO_ROLE_ID,
                permanent=True
            )
        elif not self._cycle_role_active(donor.id, "owo"):
            progress = self.db.add_benefit_progress(
                donor.id, "owo", amount
            )

            if progress >= OWO_ROLE_THRESHOLD:
                role_status = await self.activate_benefit_role(
                    donor, "owo"
                )
            else:
                role_status = (
                    "⏳ Progress role: "
                    f"{format_owo(progress)} / "
                    f"{format_owo(OWO_ROLE_THRESHOLD)} Owo"
                )
        else:
            role_status = (
                "ℹ️ Role Donatur OwO masih aktif. "
                "Donasi ini tidak masuk progress siklus berikutnya."
            )

        # -------------------------------------------------
        # NOTIFICATION
        # -------------------------------------------------

        await self.send_owo_notification(
            donor=donor,
            recipient=recipient,
            amount=amount,
            total=total,
            donation_id=donation_id,
            permanent=permanent
        )

        # -------------------------------------------------
        # UPDATE LEADERBOARD
        # -------------------------------------------------

        await self.update_leaderboard()

        print(
            "[DONATION] OWO VALID | "
            f"{donor} -> {recipient} | "
            f"{amount:,} cowoncy | "
            f"Total: {total:,}"
        )

    # =====================================================
    # MANUAL OWO NOTIFICATION
    # =====================================================

    async def send_manual_owo_notification(
        self,
        donor,
        amount,
        total,
        staff,
        donation_id,
        permanent
    ):

        channel = self.bot.get_channel(
            DONATION_NOTIFICATION_CHANNEL_ID
        )

        if not channel:

            return

        embed = discord.Embed(
            title="<:owo:1550868268020006932> DONASI OWO LAMA",
            color=discord.Color.blurple(),
            timestamp=utc_now()
        )

        embed.add_field(
            name="👤 Donatur",
            value=donor.mention,
            inline=True
        )

        embed.add_field(
            name="<:owo:1550868268020006932> Nominal",
            value=f"**{format_owo(amount)} cowoncy**",
            inline=True
        )

        embed.add_field(
            name="📊 Total Donasi OwO",
            value=f"**{format_owo(total)} cowoncy**",
            inline=True
        )

        embed.add_field(
            name="📝 Dicatat Oleh",
            value=staff.mention,
            inline=True
        )

        embed.add_field(
            name="🎖️ Status",
            value=(
                "👑 **PERMANEN**"
                if permanent
                else "⏳ **30 HARI**"
            ),
            inline=True
        )

        embed.add_field(
            name="🆔 Transaksi",
            value=f"`#{donation_id}`",
            inline=True
        )

        embed.set_thumbnail(
            url=donor.display_avatar.url
        )

        embed.set_footer(
            text="nanZ Donation System • Manual OwO Lama"
        )

        await channel.send(
            embed=embed
        )

    # =====================================================
    # OWO NOTIFICATION
    # =====================================================

    async def send_owo_notification(
        self,
        donor,
        recipient,
        amount,
        total,
        donation_id,
        permanent
    ):

        channel = self.bot.get_channel(
            DONATION_NOTIFICATION_CHANNEL_ID
        )

        if not channel:

            return

        embed = discord.Embed(
            title="<:owo:1550868268020006932> DONASI OWO BARU",
            color=discord.Color.blurple(),
            timestamp=utc_now()
        )

        embed.add_field(
            name="👤 Donatur",
            value=donor.mention,
            inline=True
        )

        embed.add_field(
            name="<:owo:1550868268020006932> Nominal",
            value=f"**{format_owo(amount)} cowoncy**",
            inline=True
        )

        embed.add_field(
            name="📊 Total Donasi",
            value=f"**{format_owo(total)} cowoncy**",
            inline=True
        )

        embed.add_field(
            name="🎯 Diberikan Kepada",
            value=recipient.mention,
            inline=True
        )

        embed.add_field(
            name="🎖️ Status",
            value=(
                "👑 **PERMANEN**"
                if permanent
                else "⏳ **30 HARI**"
            ),
            inline=True
        )

        embed.add_field(
            name="🆔 Transaksi",
            value=f"`#{donation_id}`",
            inline=True
        )

        embed.set_thumbnail(
            url=donor.display_avatar.url
        )

        embed.set_footer(
            text="nanZ Donation System • OwO"
        )

        await channel.send(
            embed=embed
        )

    # =====================================================
    # RUPIAH NOTIFICATION
    # =====================================================

    async def send_rupiah_notification(
        self,
        donor,
        amount,
        total,
        staff,
        donation_id,
        permanent
    ):

        channel = self.bot.get_channel(
            DONATION_NOTIFICATION_CHANNEL_ID
        )

        if not channel:

            return

        embed = discord.Embed(
            title="<:rupiah:1550869044104798208> DONASI RUPIAH BARU",
            color=discord.Color.green(),
            timestamp=utc_now()
        )

        embed.add_field(
            name="👤 Donatur",
            value=donor.mention,
            inline=True
        )

        embed.add_field(
            name="<:rupiah:1550869044104798208> Nominal",
            value=f"**{format_rupiah(amount)}**",
            inline=True
        )

        embed.add_field(
            name="📊 Total Donasi",
            value=f"**{format_rupiah(total)}**",
            inline=True
        )

        embed.add_field(
            name="📝 Dicatat Oleh",
            value=staff.mention,
            inline=True
        )

        embed.add_field(
            name="🎖️ Status",
            value=(
                "👑 **PERMANEN**"
                if permanent
                else "⏳ **30 HARI**"
            ),
            inline=True
        )

        embed.add_field(
            name="🆔 Transaksi",
            value=f"`#{donation_id}`",
            inline=True
        )

        embed.set_thumbnail(
            url=donor.display_avatar.url
        )

        embed.set_footer(
            text="nanZ Donation System • Rupiah"
        )

        await channel.send(
            embed=embed
        )

    # =====================================================
    # EXPIRE DONOR ROLES
    # =====================================================

    @tasks.loop(minutes=10)
    async def expire_donor_roles(self):

        expired = self.db.get_expired_roles()

        if not expired:

            return

        for user_id, role_id in expired:

            for guild in self.bot.guilds:

                member = guild.get_member(
                    user_id
                )

                if not member:

                    continue

                role = guild.get_role(
                    role_id
                )

                if not role:

                    continue

                if role not in member.roles:

                    continue

                try:

                    await member.remove_roles(
                        role,
                        reason=(
                            "nanZ Donation - "
                            "30 hari berakhir"
                        )
                    )

                except discord.Forbidden:

                    print(
                        "[DONATION] Tidak bisa "
                        f"remove role dari {member}"
                    )

            self.db.delete_donor_role(
                user_id,
                role_id
            )

            if role_id == DONATUR_RUPIAH_ROLE_ID:
                self.db.reset_benefit_cycle(user_id, "rupiah")
            elif role_id == DONATUR_OWO_ROLE_ID:
                self.db.reset_benefit_cycle(user_id, "owo")

            print(
                "[DONATION] Donor role expired: "
                f"{user_id} / {role_id}"
            )

    # =====================================================
    # LEADERBOARD
    # =====================================================

    async def update_leaderboard(self):

        channel = self.bot.get_channel(
            LIVE_TOP_DONOR_CHANNEL_ID
        )

        if not channel:

            return

        rupiah_top = self.db.get_top_donors(
            "rupiah",
            10
        )

        owo_top = self.db.get_top_donors_by_methods(
            ("owo", "owo_manual"),
            10
        )

        total_rupiah = self.db.get_total_all(
            "rupiah"
        )

        total_owo = self.db.get_total_all_by_methods(
            ("owo", "owo_manual")
        )

        embed = discord.Embed(
            title="<a:topdonatur:1550871705914974318> TOP DONATUR NANZ",
            description=(
                "Leaderboard donatur "
                "**nanZ Server**\n"
                "Diperbarui otomatis setiap ada donasi."
            ),
            color=discord.Color.gold(),
            timestamp=utc_now()
        )

        # -------------------------------------------------
        # RUPIAH
        # -------------------------------------------------

        rupiah_text = ""

        if rupiah_top:

            for index, (
                user_id,
                total
            ) in enumerate(
                rupiah_top,
                start=1
            ):

                member = channel.guild.get_member(
                    user_id
                )

                name = (
                    member.display_name
                    if member
                    else f"User {user_id}"
                )

                medal = {
                    1: "<a:peringkat1:1550870838947872829>",
                    2: "<a:peringkat2:1550871079914962975>",
                    3: "<a:peringkat3:1550871014634954863>"
                }.get(
                    index,
                    f"`{index:02}`"
                )

                rupiah_text += (
                    f"{medal} **{name}**\n"
                    f"└─ {format_rupiah(total)}\n"
                )

        else:

            rupiah_text = (
                "Belum ada donasi Rupiah."
            )

        embed.add_field(
            name="<:rupiah:1550869044104798208> DONATUR RUPIAH — TOP 10",
            value=rupiah_text,
            inline=False
        )

        embed.add_field(
            name="<:rupiah:1550869044104798208> TOTAL RUPIAH",
            value=f"**{format_rupiah(total_rupiah)}**",
            inline=False
        )

        # -------------------------------------------------
        # OWO
        # -------------------------------------------------

        owo_text = ""

        if owo_top:

            for index, (
                user_id,
                total
            ) in enumerate(
                owo_top,
                start=1
            ):

                member = channel.guild.get_member(
                    user_id
                )

                name = (
                    member.display_name
                    if member
                    else f"User {user_id}"
                )

                medal = {
                    1: "<a:peringkat1:1550870838947872829>",
                    2: "<a:peringkat2:1550871079914962975>",
                    3: "<a:peringkat3:1550871014634954863>"
                }.get(
                    index,
                    f"`{index:02}`"
                )

                owo_text += (
                    f"{medal} **{name}**\n"
                    f"└─ {format_owo(total)} cowoncy\n"
                )

        else:

            owo_text = (
                "Belum ada donasi OwO."
            )

        embed.add_field(
            name="<:owo:1550868268020006932> DONATUR OWO — TOP 10",
            value=owo_text,
            inline=False
        )

        embed.add_field(
            name="<:owo:1550868268020006932> TOTAL OWO",
            value=f"**{format_owo(total_owo)} cowoncy**",
            inline=False
        )

        embed.set_footer(
            text="nanZ Server • Live Donation Leaderboard"
        )

        # -------------------------------------------------
        # CARI PESAN LEADERBOARD
        # -------------------------------------------------

        message = None

        if self.leaderboard_message_id:

            try:

                message = await channel.fetch_message(
                    self.leaderboard_message_id
                )

            except (
                discord.NotFound,
                discord.Forbidden
            ):

                message = None

        # -------------------------------------------------
        # SEARCH PESAN LAMA
        # -------------------------------------------------

        if not message:

            try:

                async for msg in channel.history(
                    limit=50
                ):

                    if (
                        msg.author.id == self.bot.user.id
                        and msg.embeds
                        and msg.embeds[0].title
                        == "<a:topdonatur:1550871705914974318> TOP DONATUR NANZ"
                    ):

                        message = msg

                        self.leaderboard_message_id = (
                            msg.id
                        )

                        break

            except Exception as e:

                print(
                    f"[DONATION] Search leaderboard: {e}"
                )

        # -------------------------------------------------
        # EDIT / CREATE
        # -------------------------------------------------

        if message:

            try:

                await message.edit(
                    embed=embed
                )

            except discord.NotFound:

                message = await channel.send(
                    embed=embed
                )

                self.leaderboard_message_id = (
                    message.id
                )

        else:

            message = await channel.send(
                embed=embed
            )

            self.leaderboard_message_id = (
                message.id
            )

    # =====================================================
    # TOP DONATUR COMMAND
    # =====================================================

    @commands.command(
        name="topdonatur"
    )
    async def topdonatur(
        self,
        ctx
    ):

        await self.update_leaderboard()

        await ctx.send(
            f"<a:topdonatur:1550871705914974318> Leaderboard diperbarui di "
            f"<#{LIVE_TOP_DONOR_CHANNEL_ID}>."
        )

    # =====================================================
    # DONASIKU
    # =====================================================

    @commands.command(
        name="donasiku"
    )
    async def donasiku(
        self,
        ctx
    ):

        # Progress benefit dipisahkan dari total leaderboard.
        rupiah_cycle = self.db.get_benefit_cycle(ctx.author.id)

        rupiah = self.db.get_user_total(
            ctx.author.id,
            "rupiah"
        )

        owo = self.db.get_user_total_by_methods(
            ctx.author.id,
            ("owo", "owo_manual")
        )

        rupiah_permanent = (
            rupiah >= RUPIAH_PERMANENT_THRESHOLD
        )

        owo_permanent = (
            owo >= OWO_PERMANENT_THRESHOLD
        )

        embed = discord.Embed(
            title="💝 DONASI KAMU",
            color=discord.Color.gold()
        )

        embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.url
        )

        embed.add_field(
            name="<:rupiah:1550869044104798208> Total Rupiah",
            value=f"**{format_rupiah(rupiah)}**",
            inline=True
        )

        embed.add_field(
            name="<:owo:1550868268020006932> Total OwO",
            value=f"**{format_owo(owo)} cowoncy**",
            inline=True
        )

        rupiah_until = rupiah_cycle["rupiah_role_until"]
        owo_until = rupiah_cycle["owo_role_until"]

        rupiah_progress = rupiah_cycle["rupiah_progress"]
        owo_progress = rupiah_cycle["owo_progress"]

        if rupiah_permanent:
            rupiah_status = "👑 **PERMANEN**"
        elif rupiah_until:
            expiry = datetime.fromisoformat(rupiah_until)
            rupiah_status = f"🎖️ **AKTIF** sampai <t:{int(expiry.timestamp())}:R>"
        else:
            rupiah_status = (
                f"⏳ **{format_rupiah(rupiah_progress)} / "
                f"{format_rupiah(RUPIAH_ROLE_THRESHOLD)}**"
            )

        if owo_permanent:
            owo_status = "👑 **PERMANEN**"
        elif owo_until:
            expiry = datetime.fromisoformat(owo_until)
            owo_status = f"🎖️ **AKTIF** sampai <t:{int(expiry.timestamp())}:R>"
        else:
            owo_status = (
                f"⏳ **{format_owo(owo_progress)} / "
                f"{format_owo(OWO_ROLE_THRESHOLD)} Owo**"
            )

        embed.add_field(
            name="<:rupiah:1550869044104798208> Status Rupiah",
            value=rupiah_status,
            inline=False
        )

        embed.add_field(
            name="<:owo:1550868268020006932> Status OwO",
            value=owo_status,
            inline=False
        )

        await ctx.send(
            embed=embed
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    cog = DonationControl(
        bot
    )

    await bot.add_cog(
        cog
    )

    # Persistent donation panel
    bot.add_view(
        DonationPanelView(cog)
    )