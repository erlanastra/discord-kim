import discord
from discord.ext import commands

import sqlite3
import os
import json
from datetime import datetime


# ==========================================================
# DATABASE
# ==========================================================

class DonationDatabase:

    def __init__(self, database_path="donation.db"):
        self.database_path = database_path
        self.create_tables()

    def connect(self):
        return sqlite3.connect(self.database_path)

    def create_tables(self):
        connection = self.connect()
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS donations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                method TEXT NOT NULL,
                staff_id INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        connection.commit()
        connection.close()

    def add_donation(
        self,
        guild_id,
        user_id,
        amount,
        method,
        staff_id
    ):
        connection = self.connect()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO donations
            (
                guild_id,
                user_id,
                amount,
                method,
                staff_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            guild_id,
            user_id,
            amount,
            method,
            staff_id,
            datetime.utcnow().isoformat()
        ))

        donation_id = cursor.lastrowid

        connection.commit()
        connection.close()

        return donation_id

    def get_user_total(self, guild_id, user_id, method="rupiah"):
        connection = self.connect()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM donations
            WHERE guild_id = ?
            AND user_id = ?
            AND method = ?
        """, (
            guild_id,
            user_id,
            method
        ))

        result = cursor.fetchone()[0]

        connection.close()

        return result

    def get_top_donors(
        self,
        guild_id,
        method="rupiah",
        limit=10
    ):
        connection = self.connect()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT user_id, SUM(amount) AS total
            FROM donations
            WHERE guild_id = ?
            AND method = ?
            GROUP BY user_id
            ORDER BY total DESC
            LIMIT ?
        """, (
            guild_id,
            method,
            limit
        ))

        result = cursor.fetchall()

        connection.close()

        return result

    def get_total_donation(self, guild_id, method="rupiah"):
        connection = self.connect()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM donations
            WHERE guild_id = ?
            AND method = ?
        """, (
            guild_id,
            method
        ))

        result = cursor.fetchone()[0]

        connection.close()

        return result


# ==========================================================
# DONATION COG
# ==========================================================

class DonationSystem(commands.Cog):

    # ======================================================
    # KONFIGURASI
    # ======================================================

    DONATUR_RUPIAH_ROLE_ID = 1528766033509220572
    DONATUR_OWO_ROLE_ID = 1528766890296611017

    # Channel notifikasi donasi
    DONATION_NOTIFICATION_CHANNEL_ID = 1528760374705262742

    # Channel leaderboard top donatur
    TOP_DONOR_CHANNEL_ID = 1550820849018474597

    # GANTI DENGAN ID CHANNEL PANEL DONASI
    DONATION_PANEL_CHANNEL_ID = 1550826363676794890

    # Role staff yang boleh mencatat donasi
    STAFF_ROLE_IDS = {
        1417582562100117584,  # Guru Besar
        1453103644244316343,  # Moderator
        1467360501745844446,  # Pembina OSIS
        1427276194876751902,  # OSIS
    }

    PANEL_MESSAGE_FILE = "donation_panel.json"
    LEADERBOARD_MESSAGE_FILE = "donation_leaderboard.json"

    def __init__(self, bot):
        self.bot = bot
        self.db = DonationDatabase()

        self.panel_message_id = self.load_message_id(
            self.PANEL_MESSAGE_FILE
        )

        self.leaderboard_message_id = self.load_message_id(
            self.LEADERBOARD_MESSAGE_FILE
        )

    async def cog_load(self):
        """
        Membuat view tetap aktif setelah bot restart.
        """

        self.bot.add_view(
            DonationPanelView(self)
        )

    # ======================================================
    # HELPER FILE
    # ======================================================

    def load_message_id(self, filename):
        if not os.path.exists(filename):
            return None

        try:
            with open(filename, "r", encoding="utf-8") as file:
                data = json.load(file)

            return data.get("message_id")

        except Exception:
            return None

    def save_message_id(self, filename, message_id):
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(
                {
                    "message_id": message_id
                },
                file,
                indent=4
            )

    # ======================================================
    # HELPER
    # ======================================================

    def format_rupiah(self, amount):
        return f"Rp{amount:,}".replace(",", ".")

    def has_staff_access(self, member):
        if member.guild_permissions.administrator:
            return True

        return any(
            role.id in self.STAFF_ROLE_IDS
            for role in member.roles
        )

    # ======================================================
    # PANEL EMBED
    # ======================================================

    def create_panel_embed(self):
        embed = discord.Embed(
            title="💰 NANZ DONATION CENTER",
            description=(
                "Terima kasih telah mendukung **nanZ Community**! 💙\n\n"

                "Panel ini digunakan oleh staff untuk mencatat "
                "donasi Rupiah dari member.\n\n"

                "### 📌 Cara menggunakan\n"
                "1. Klik tombol **Catat Donasi**.\n"
                "2. Cari dan pilih member donatur.\n"
                "3. Masukkan nominal donasi.\n"
                "4. Periksa dan konfirmasi data.\n\n"

                "### ⚙️ Sistem otomatis\n"
                "• Donasi masuk database.\n"
                "• Role Donatur Rupiah diberikan.\n"
                "• Notifikasi dikirim ke channel donasi.\n"
                "• Leaderboard Top Donatur diperbarui.\n\n"

                "⚠️ Pastikan nominal dan member sudah benar "
                "sebelum melakukan konfirmasi."
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(
            text="nanZ Community • Donation System"
        )

        return embed

    # ======================================================
    # NOTIFIKASI DONASI
    # ======================================================

    async def send_donation_notification(
        self,
        guild,
        donor,
        amount,
        staff,
        donation_id
    ):
        channel = guild.get_channel(
            self.DONATION_NOTIFICATION_CHANNEL_ID
        )

        if not channel:
            return

        total = self.db.get_user_total(
            guild.id,
            donor.id,
            "rupiah"
        )

        embed = discord.Embed(
            title="💰 DONASI BARU MASUK",
            description=(
                f"Terima kasih kepada {donor.mention} "
                "yang telah mendukung **nanZ Community**! 💙"
            ),
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )

        embed.add_field(
            name="👤 Donatur",
            value=donor.mention,
            inline=True
        )

        embed.add_field(
            name="💵 Nominal",
            value=f"**{self.format_rupiah(amount)}**",
            inline=True
        )

        embed.add_field(
            name="🌐 Metode",
            value="SociaBuzz",
            inline=True
        )

        embed.add_field(
            name="📊 Total Donatur",
            value=f"**{self.format_rupiah(total)}**",
            inline=True
        )

        embed.add_field(
            name="👮 Dicatat oleh",
            value=staff.mention,
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
            text="nanZ Donation System"
        )

        await channel.send(embed=embed)

    # ======================================================
    # LEADERBOARD
    # ======================================================

    async def create_leaderboard_embed(self, guild):
        top_donors = self.db.get_top_donors(
            guild.id,
            method="rupiah",
            limit=10
        )

        total_donation = self.db.get_total_donation(
            guild.id,
            method="rupiah"
        )

        embed = discord.Embed(
            title="🏆 TOP DONATUR NANZ",
            description=(
                "Leaderboard donatur Rupiah nanZ Community.\n"
                "Data diperbarui otomatis setiap ada donasi baru."
            ),
            color=discord.Color.gold()
        )

        if not top_donors:
            donor_text = "Belum ada donasi yang tercatat."
        else:
            donor_lines = []
            medals = ["🥇", "🥈", "🥉"]

            for index, (user_id, total) in enumerate(
                top_donors,
                start=1
            ):
                member = guild.get_member(user_id)

                if member:
                    donor_name = member.mention
                else:
                    donor_name = f"<@{user_id}>"

                rank = (
                    medals[index - 1]
                    if index <= 3
                    else f"`#{index}`"
                )

                donor_lines.append(
                    f"{rank} {donor_name} — "
                    f"**{self.format_rupiah(total)}**"
                )

            donor_text = "\n".join(donor_lines)

        embed.add_field(
            name="💵 Donatur Rupiah",
            value=donor_text,
            inline=False
        )

        embed.add_field(
            name="💰 Total Seluruh Donasi",
            value=f"**{self.format_rupiah(total_donation)}**",
            inline=False
        )

        embed.set_footer(
            text="nanZ Community • Live Donation Leaderboard"
        )

        return embed

    async def update_leaderboard(self, guild):
        channel = guild.get_channel(
            self.TOP_DONOR_CHANNEL_ID
        )

        if not channel:
            return

        embed = await self.create_leaderboard_embed(guild)

        if self.leaderboard_message_id:
            try:
                message = await channel.fetch_message(
                    self.leaderboard_message_id
                )

                await message.edit(embed=embed)
                return

            except discord.NotFound:
                self.leaderboard_message_id = None

            except discord.HTTPException:
                return

        message = await channel.send(embed=embed)

        self.leaderboard_message_id = message.id

        self.save_message_id(
            self.LEADERBOARD_MESSAGE_FILE,
            message.id
        )

    # ======================================================
    # SETUP PANEL PERMANEN
    # ======================================================

    @commands.command(
        name="setupdonationpanel",
        aliases=["setupdonasipanel"]
    )
    @commands.has_permissions(administrator=True)
    async def setup_donation_panel(self, ctx):
        channel = ctx.guild.get_channel(
            self.DONATION_PANEL_CHANNEL_ID
        )

        if not channel:
            await ctx.send(
                "❌ Channel panel donasi tidak ditemukan. "
                "Periksa `DONATION_PANEL_CHANNEL_ID`."
            )
            return

        embed = self.create_panel_embed()

        message = await channel.send(
            embed=embed,
            view=DonationPanelView(self)
        )

        self.panel_message_id = message.id

        self.save_message_id(
            self.PANEL_MESSAGE_FILE,
            message.id
        )

        await ctx.send(
            f"✅ Panel donasi berhasil dibuat di {channel.mention}.",
            delete_after=5
        )

    # ======================================================
    # SETUP LEADERBOARD
    # ======================================================

    @commands.command(
        name="setupdonatur",
        aliases=["setuptopdonatur"]
    )
    @commands.has_permissions(administrator=True)
    async def setup_donation_leaderboard(self, ctx):
        await self.update_leaderboard(ctx.guild)

        await ctx.send(
            "✅ Leaderboard donatur berhasil dibuat/diperbarui.",
            delete_after=5
        )

    # ======================================================
    # CEK DONASI SENDIRI
    # ======================================================

    @commands.command(name="donasiku")
    async def my_donation(self, ctx, member: discord.Member = None):
        target = member or ctx.author

        total = self.db.get_user_total(
            ctx.guild.id,
            target.id,
            "rupiah"
        )

        embed = discord.Embed(
            title="💰 STATISTIK DONASI",
            color=discord.Color.gold()
        )

        embed.set_author(
            name=target.display_name,
            icon_url=target.display_avatar.url
        )

        embed.add_field(
            name="💵 Total Donasi Rupiah",
            value=f"**{self.format_rupiah(total)}**",
            inline=False
        )

        await ctx.send(embed=embed)


# ==========================================================
# PANEL VIEW
# ==========================================================

class DonationPanelView(discord.ui.View):

    def __init__(self, cog):
        super().__init__(
            timeout=None
        )

        self.cog = cog

    @discord.ui.button(
        label="💰 Catat Donasi",
        style=discord.ButtonStyle.success,
        custom_id="nanz_donation_record_button"
    )
    async def record_donation(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not self.cog.has_staff_access(interaction.user):
            await interaction.response.send_message(
                "❌ Kamu tidak mempunyai akses ke panel donasi.",
                ephemeral=True
            )
            return

        view = DonationMemberView(
            cog=self.cog,
            staff=interaction.user
        )

        embed = discord.Embed(
            title="👤 PILIH DONATUR",
            description=(
                "Gunakan dropdown di bawah untuk mencari "
                "dan memilih member yang melakukan donasi."
            ),
            color=discord.Color.blurple()
        )

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )


# ==========================================================
# MEMBER SELECT VIEW
# ==========================================================

class DonationMemberView(discord.ui.View):

    def __init__(self, cog, staff):
        super().__init__(
            timeout=120
        )

        self.cog = cog
        self.staff = staff

        self.member_select = discord.ui.UserSelect(
            placeholder="🔎 Cari member donatur...",
            min_values=1,
            max_values=1
        )

        self.member_select.callback = self.member_selected

        self.add_item(self.member_select)

    async def member_selected(self, interaction):
        selected_member = self.member_select.values[0]

        if not isinstance(selected_member, discord.Member):
            selected_member = interaction.guild.get_member(
                selected_member.id
            )

        if not selected_member:
            await interaction.response.send_message(
                "❌ Member tidak ditemukan.",
                ephemeral=True
            )
            return

        modal = DonationAmountModal(
            cog=self.cog,
            donor=selected_member,
            staff=self.staff
        )

        await interaction.response.send_modal(modal)


# ==========================================================
# NOMINAL MODAL
# ==========================================================

class DonationAmountModal(discord.ui.Modal):

    def __init__(self, cog, donor, staff):
        super().__init__(
            title="💰 Input Nominal Donasi"
        )

        self.cog = cog
        self.donor = donor
        self.staff = staff

        self.amount_input = discord.ui.TextInput(
            label="Nominal Donasi Rupiah",
            placeholder="Contoh: 50000",
            required=True,
            min_length=1,
            max_length=15
        )

        self.add_item(self.amount_input)

    async def on_submit(self, interaction):
        raw_amount = self.amount_input.value.strip()

        raw_amount = (
            raw_amount
            .replace("Rp", "")
            .replace("rp", "")
            .replace(".", "")
            .replace(",", "")
            .replace(" ", "")
        )

        if not raw_amount.isdigit():
            await interaction.response.send_message(
                "❌ Nominal harus berupa angka.\n"
                "Contoh: `50000`",
                ephemeral=True
            )
            return

        amount = int(raw_amount)

        if amount <= 0:
            await interaction.response.send_message(
                "❌ Nominal harus lebih dari Rp0.",
                ephemeral=True
            )
            return

        if amount > 1_000_000_000:
            await interaction.response.send_message(
                "❌ Nominal terlalu besar.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🔎 KONFIRMASI DONASI",
            description=(
                "Pastikan semua data sudah benar "
                "sebelum menyimpan transaksi."
            ),
            color=discord.Color.gold()
        )

        embed.add_field(
            name="👤 Donatur",
            value=self.donor.mention,
            inline=False
        )

        embed.add_field(
            name="💵 Nominal",
            value=f"**{self.cog.format_rupiah(amount)}**",
            inline=True
        )

        embed.add_field(
            name="🌐 Metode",
            value="SociaBuzz",
            inline=True
        )

        embed.add_field(
            name="👮 Dicatat oleh",
            value=self.staff.mention,
            inline=True
        )

        view = DonationConfirmView(
            cog=self.cog,
            donor=self.donor,
            staff=self.staff,
            amount=amount
        )

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )


# ==========================================================
# KONFIRMASI DONASI
# ==========================================================

class DonationConfirmView(discord.ui.View):

    def __init__(self, cog, donor, staff, amount):
        super().__init__(
            timeout=120
        )

        self.cog = cog
        self.donor = donor
        self.staff = staff
        self.amount = amount
        self.completed = False

    @discord.ui.button(
        label="✅ Konfirmasi",
        style=discord.ButtonStyle.success
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if interaction.user.id != self.staff.id:
            await interaction.response.send_message(
                "❌ Hanya staff yang membuat transaksi ini "
                "yang dapat mengonfirmasi.",
                ephemeral=True
            )
            return

        if self.completed:
            await interaction.response.send_message(
                "❌ Transaksi ini sudah diproses.",
                ephemeral=True
            )
            return

        self.completed = True

        donation_id = self.cog.db.add_donation(
            guild_id=interaction.guild.id,
            user_id=self.donor.id,
            amount=self.amount,
            method="rupiah",
            staff_id=self.staff.id
        )

        role = interaction.guild.get_role(
            self.cog.DONATUR_RUPIAH_ROLE_ID
        )

        role_message = ""

        if role:
            try:
                if role not in self.donor.roles:
                    await self.donor.add_roles(
                        role,
                        reason=f"Donatur Rupiah #{donation_id}"
                    )

                role_message = "\n🎖️ Role Donatur Rupiah diberikan."

            except discord.Forbidden:
                role_message = (
                    "\n⚠️ Bot tidak dapat memberikan role. "
                    "Periksa posisi role bot."
                )

        await self.cog.send_donation_notification(
            guild=interaction.guild,
            donor=self.donor,
            amount=self.amount,
            staff=self.staff,
            donation_id=donation_id
        )

        await self.cog.update_leaderboard(
            interaction.guild
        )

        embed = discord.Embed(
            title="✅ DONASI BERHASIL DICATAT",
            description=(
                "Donasi berhasil disimpan ke database."
                + role_message
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="👤 Donatur",
            value=self.donor.mention,
            inline=False
        )

        embed.add_field(
            name="💵 Nominal",
            value=f"**{self.cog.format_rupiah(self.amount)}**",
            inline=True
        )

        embed.add_field(
            name="🆔 ID Transaksi",
            value=f"`#{donation_id}`",
            inline=True
        )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )

    @discord.ui.button(
        label="❌ Batal",
        style=discord.ButtonStyle.danger
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if interaction.user.id != self.staff.id:
            await interaction.response.send_message(
                "❌ Hanya staff yang membuat transaksi ini "
                "yang dapat membatalkan.",
                ephemeral=True
            )
            return

        if self.completed:
            return

        self.completed = True

        embed = discord.Embed(
            title="❌ DONASI DIBATALKAN",
            description=(
                "Data donasi tidak dimasukkan ke database."
            ),
            color=discord.Color.red()
        )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):
    await bot.add_cog(DonationSystem(bot))