import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
import sqlite3
import os
from datetime import datetime


class DonationDatabase:
    def __init__(self, db_path="donation.db"):
        self.db_path = db_path
        self.init_db()

    def connect(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS donations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                method TEXT NOT NULL,
                staff_id INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    def add_donation(self, user_id, amount, method, staff_id):
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO donations
            (user_id, amount, method, staff_id, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            amount,
            method,
            staff_id,
            datetime.utcnow().isoformat()
        ))

        donation_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return donation_id

    def get_user_total(self, user_id, method="rupiah"):
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM donations
            WHERE user_id = ? AND method = ?
        """, (user_id, method))

        total = cursor.fetchone()[0]

        conn.close()

        return total

    def get_top_donors(self, method="rupiah", limit=10):
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, SUM(amount) AS total
            FROM donations
            WHERE method = ?
            GROUP BY user_id
            ORDER BY total DESC
            LIMIT ?
        """, (method, limit))

        results = cursor.fetchall()

        conn.close()

        return results

    def get_all_total(self, method="rupiah"):
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM donations
            WHERE method = ?
        """, (method,))

        total = cursor.fetchone()[0]

        conn.close()

        return total


class DonationAmountModal(Modal, title="💰 Input Donasi"):
    amount = TextInput(
        label="Nominal Donasi",
        placeholder="Contoh: 50000",
        required=True,
        min_length=1,
        max_length=15
    )

    def __init__(self, cog, target_member, staff):
        super().__init__()

        self.cog = cog
        self.target_member = target_member
        self.staff = staff

    async def on_submit(self, interaction: discord.Interaction):

        raw_amount = self.amount.value.strip()

        # Hilangkan format umum
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
                "❌ Nominal harus berupa angka.\n\n"
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

        confirm_view = DonationConfirmView(
            cog=self.cog,
            target_member=self.target_member,
            staff=self.staff,
            amount=amount
        )

        embed = discord.Embed(
            title="💰 Konfirmasi Donasi",
            description=(
                "Periksa kembali data donasi sebelum disimpan."
            ),
            color=discord.Color.gold()
        )

        embed.add_field(
            name="👤 Donatur",
            value=self.target_member.mention,
            inline=False
        )

        embed.add_field(
            name="💵 Nominal",
            value=f"**Rp{amount:,}**".replace(",", "."),
            inline=False
        )

        embed.add_field(
            name="🌐 Metode",
            value="SociaBuzz / Donasi Rupiah",
            inline=True
        )

        embed.add_field(
            name="👮 Dicatat oleh",
            value=self.staff.mention,
            inline=True
        )

        embed.set_footer(
            text="Pastikan nominal dan member sudah benar."
        )

        await interaction.response.send_message(
            embed=embed,
            view=confirm_view,
            ephemeral=True
        )


class MemberSelect(Select):

    def __init__(self, cog, staff):
        self.cog = cog
        self.staff = staff

        options = []

        members = [
            member
            for member in staff.guild.members
            if not member.bot
        ]

        # Discord Select maksimal 25 option.
        # Ambil member berdasarkan nama secara terbatas.
        members = sorted(
            members,
            key=lambda m: m.display_name.lower()
        )[:25]

        for member in members:
            options.append(
                discord.SelectOption(
                    label=member.display_name[:100],
                    value=str(member.id),
                    description=f"@{member.name}"[:100]
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="Tidak ada member",
                    value="none"
                )
            )

        super().__init__(
            placeholder="👤 Pilih member...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        if self.values[0] == "none":
            await interaction.response.send_message(
                "❌ Tidak ada member yang tersedia.",
                ephemeral=True
            )
            return

        member_id = int(self.values[0])

        member = interaction.guild.get_member(member_id)

        if not member:
            await interaction.response.send_message(
                "❌ Member tidak ditemukan.",
                ephemeral=True
            )
            return

        modal = DonationAmountModal(
            cog=self.cog,
            target_member=member,
            staff=interaction.user
        )

        await interaction.response.send_modal(modal)


class DonationPanelView(View):

    def __init__(self, cog):
        super().__init__(timeout=None)

        self.cog = cog

        self.add_item(
            DonationMemberSelect(cog)
        )


class DonationMemberSelect(Select):

    def __init__(self, cog):
        self.cog = cog

        super().__init__(
            placeholder="👤 Cari / pilih member...",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="Pilih member",
                    description="Pilih member yang menerima donasi",
                    value="select_member"
                )
            ]
        )

    async def callback(self, interaction: discord.Interaction):

        # Discord Select biasa tidak menyediakan pencarian
        # terhadap seluruh member. Gunakan UserSelect Discord.
        await interaction.response.send_message(
            "Silakan gunakan tombol **Pilih Member** di bawah.",
            ephemeral=True
        )


class DonationUserSelect(Select):

    def __init__(self, cog):
        self.cog = cog

        super().__init__(
            placeholder="🔎 Pilih member...",
            min_values=1,
            max_values=1,
            options=[]
        )


class DonationConfirmView(View):

    def __init__(self, cog, target_member, staff, amount):
        super().__init__(timeout=120)

        self.cog = cog
        self.target_member = target_member
        self.staff = staff
        self.amount = amount
        self.processed = False

    @discord.ui.button(
        label="✅ Konfirmasi",
        style=discord.ButtonStyle.success
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        if interaction.user.id != self.staff.id:
            await interaction.response.send_message(
                "❌ Hanya staff yang membuat transaksi ini "
                "yang dapat mengonfirmasi.",
                ephemeral=True
            )
            return

        if self.processed:
            await interaction.response.send_message(
                "❌ Transaksi ini sudah diproses.",
                ephemeral=True
            )
            return

        self.processed = True

        donation_id = self.cog.db.add_donation(
            user_id=self.target_member.id,
            amount=self.amount,
            method="rupiah",
            staff_id=self.staff.id
        )

        # Tambahkan role donor
        role = interaction.guild.get_role(
            self.cog.DONATUR_RUPIAH_ROLE_ID
        )

        role_result = ""

        if role:

            try:
                if role not in self.target_member.roles:
                    await self.target_member.add_roles(
                        role,
                        reason=f"Donatur Rupiah #{donation_id}"
                    )

                role_result = "\n🎖️ Role Donatur Rupiah diberikan."

            except discord.Forbidden:
                role_result = (
                    "\n⚠️ Bot tidak mempunyai izin "
                    "untuk memberikan role."
                )

        # Kirim notifikasi
        await self.cog.send_donation_notification(
            guild=interaction.guild,
            donor=self.target_member,
            amount=self.amount,
            staff=self.staff,
            donation_id=donation_id
        )

        # Update leaderboard
        await self.cog.update_leaderboard(
            interaction.guild
        )

        embed = discord.Embed(
            title="✅ Donasi Berhasil Dicatat",
            color=discord.Color.green()
        )

        embed.add_field(
            name="👤 Donatur",
            value=self.target_member.mention,
            inline=False
        )

        embed.add_field(
            name="💵 Nominal",
            value=f"**Rp{self.amount:,}**".replace(",", "."),
            inline=True
        )

        embed.add_field(
            name="🆔 ID Transaksi",
            value=f"`#{donation_id}`",
            inline=True
        )

        embed.description = (
            "Donasi sudah masuk ke database."
            + role_result
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
        button: Button
    ):

        if interaction.user.id != self.staff.id:
            await interaction.response.send_message(
                "❌ Hanya staff yang membuat transaksi ini "
                "yang dapat membatalkan.",
                ephemeral=True
            )
            return

        if self.processed:
            return

        self.processed = True

        embed = discord.Embed(
            title="❌ Donasi Dibatalkan",
            description="Transaksi tidak dimasukkan ke database.",
            color=discord.Color.red()
        )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )

class DonationPanel(View):

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="💰 Catat Donasi",
        style=discord.ButtonStyle.success,
        custom_id="nanz_donation_add"
    )
    async def add_donation(
        self,
        interaction: discord.Interaction,
        button: Button
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
            title="👤 Pilih Donatur",
            description=(
                "Cari dan pilih member yang melakukan donasi "
                "menggunakan dropdown di bawah."
            ),
            color=discord.Color.blurple()
        )

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )

class DonationPanel(View):

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="💰 Catat Donasi",
        style=discord.ButtonStyle.success,
        custom_id="nanz_donation_add"
    )
    async def add_donation(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        if not self.cog.has_staff_access(interaction.user):
            await interaction.response.send_message(
                "❌ Kamu tidak mempunyai akses ke panel donasi.",
                ephemeral=True
            )
            return

        # UserSelect bawaan Discord.
        class UserDonationSelect(Select):

            def __init__(inner_self):
                super().__init__(
                    placeholder="🔎 Pilih member...",
                    min_values=1,
                    max_values=1
                )

            async def callback(inner_self, select_interaction):

                member_id = int(inner_self.values[0])

                member = (
                    select_interaction.guild.get_member(member_id)
                )

                if not member:
                    await select_interaction.response.send_message(
                        "❌ Member tidak ditemukan.",
                        ephemeral=True
                    )
                    return

                modal = DonationAmountModal(
                    cog=self.cog,
                    target_member=member,
                    staff=select_interaction.user
                )

                await select_interaction.response.send_modal(modal)

        class UserDonationView(View):

            def __init__(inner_self):
                super().__init__(timeout=60)

                inner_self.add_item(
                    UserDonationSelect()
                )

        embed = discord.Embed(
            title="👤 Pilih Donatur",
            description=(
                "Gunakan dropdown di bawah untuk memilih member "
                "yang melakukan donasi."
            ),
            color=discord.Color.blurple()
        )

        await interaction.response.send_message(
            embed=embed,
            view=UserDonationView(),
            ephemeral=True
        )


class DonationControl(commands.Cog):

    DONATUR_RUPIAH_ROLE_ID = 1528766033509220572
    DONATUR_OWO_ROLE_ID = 1528766890296611017

    DONATION_NOTIFICATION_CHANNEL_ID = 1528760374705262742
    TOP_DONOR_CHANNEL_ID = 1550820849018474597

    LEADERBOARD_MESSAGE_FILE = "donation_leaderboard.json"

    def __init__(self, bot):

        self.bot = bot

        self.db = DonationDatabase()

        self.leaderboard_message_id = self.load_leaderboard_message_id()

    # ==========================================================
    # ACCESS
    # ==========================================================

    def has_staff_access(self, member):

        if member.guild_permissions.administrator:
            return True

        # Gunakan role staff yang sudah ada di server.
        staff_role_ids = {
            1417582562100117584,  # Guru Besar
            1453103644244316343,  # Moderator
            1467360501745844446,  # Pembina OSIS
            1427276194876751902,  # OSIS
        }

        return any(
            role.id in staff_role_ids
            for role in member.roles
        )

    # ==========================================================
    # FILE
    # ==========================================================

    def load_leaderboard_message_id(self):

        if not os.path.exists(
            self.LEADERBOARD_MESSAGE_FILE
        ):
            return None

        try:
            with open(
                self.LEADERBOARD_MESSAGE_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

                return data.get("message_id")

        except Exception:
            return None

    def save_leaderboard_message_id(self, message_id):

        with open(
            self.LEADERBOARD_MESSAGE_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                {"message_id": message_id},
                f,
                indent=4
            )

    # ==========================================================
    # FORMAT
    # ==========================================================

    def format_rupiah(self, amount):

        return f"Rp{amount:,}".replace(",", ".")

    # ==========================================================
    # NOTIFICATION
    # ==========================================================

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
            donor.id,
            "rupiah"
        )

        embed = discord.Embed(
            title="💰 DONASI BARU",
            description=(
                f"Terima kasih kepada {donor.mention} "
                f"yang telah mendukung **nanZ Community**! 💙"
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
            name="💵 Donasi",
            value=f"**{self.format_rupiah(amount)}**",
            inline=True
        )

        embed.add_field(
            name="📊 Total Donasi",
            value=f"**{self.format_rupiah(total)}**",
            inline=True
        )

        embed.add_field(
            name="🌐 Metode",
            value="SociaBuzz",
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

        await channel.send(
            embed=embed
        )

    # ==========================================================
    # LEADERBOARD
    # ==========================================================

    async def create_leaderboard_embed(self, guild):

        top_rupiah = self.db.get_top_donors(
            method="rupiah",
            limit=10
        )

        total_rupiah = self.db.get_all_total(
            method="rupiah"
        )

        embed = discord.Embed(
            title="🏆 TOP DONATUR NANZ",
            description=(
                "Supporter nanZ berdasarkan total donasi.\n"
                "Leaderboard diperbarui otomatis."
            ),
            color=discord.Color.gold()
        )

        if top_rupiah:

            lines = []

            medals = ["🥇", "🥈", "🥉"]

            for index, (user_id, total) in enumerate(
                top_rupiah,
                start=1
            ):

                member = guild.get_member(user_id)

                if member:
                    name = member.mention
                else:
                    name = f"<@{user_id}>"

                medal = (
                    medals[index - 1]
                    if index <= 3
                    else f"`#{index}`"
                )

                lines.append(
                    f"{medal} {name} — "
                    f"**{self.format_rupiah(total)}**"
                )

            embed.add_field(
                name="💵 Donatur Rupiah",
                value="\n".join(lines),
                inline=False
            )

        else:

            embed.add_field(
                name="💵 Donatur Rupiah",
                value="Belum ada donasi.",
                inline=False
            )

        embed.add_field(
            name="💰 Total Donasi",
            value=f"**{self.format_rupiah(total_rupiah)}**",
            inline=False
        )

        embed.set_footer(
            text="nanZ Community • Donation Leaderboard"
        )

        return embed

    async def update_leaderboard(self, guild):

        channel = guild.get_channel(
            self.TOP_DONOR_CHANNEL_ID
        )

        if not channel:
            return

        embed = await self.create_leaderboard_embed(
            guild
        )

        # Coba edit message lama
        if self.leaderboard_message_id:

            try:

                message = await channel.fetch_message(
                    self.leaderboard_message_id
                )

                await message.edit(
                    embed=embed
                )

                return

            except discord.NotFound:

                self.leaderboard_message_id = None

            except discord.HTTPException:

                return

        # Kalau belum ada, buat message baru
        message = await channel.send(
            embed=embed
        )

        self.leaderboard_message_id = message.id

        self.save_leaderboard_message_id(
            message.id
        )

    # ==========================================================
    # COMMAND PANEL
    # ==========================================================

    @commands.command(
        name="donationpanel",
        aliases=["donasipanel"]
    )
    async def donation_panel(
        self,
        ctx
    ):

        if not self.has_staff_access(ctx.author):

            await ctx.send(
                "❌ Kamu tidak mempunyai akses "
                "ke panel donasi.",
                delete_after=5
            )

            return

        embed = discord.Embed(
            title="💰 NANZ DONATION PANEL",
            description=(
                "Gunakan panel ini untuk mencatat "
                "donasi Rupiah dari member.\n\n"

                "### 💵 Donasi Rupiah\n"
                "Klik **Catat Donasi** → pilih member → "
                "masukkan nominal → konfirmasi.\n\n"

                "### 🎖️ Otomatis\n"
                "• Donasi masuk database\n"
                "• Role Donatur Rupiah diberikan\n"
                "• Notifikasi dikirim\n"
                "• Top Donatur diperbarui\n\n"

                "⚠️ Pastikan nominal yang dimasukkan "
                "sesuai dengan donasi yang diterima."
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(
            text="nanZ Donation System"
        )

        await ctx.send(
            embed=embed,
            view=DonationPanel(self)
        )

    # ==========================================================
    # MANUAL REFRESH
    # ==========================================================

    @commands.command(
        name="topdonatur",
        aliases=["topdonasi"]
    )
    async def top_donatur(
        self,
        ctx
    ):

        if not self.has_staff_access(ctx.author):
            return

        await self.update_leaderboard(
            ctx.guild
        )

        await ctx.send(
            "✅ Leaderboard donatur berhasil diperbarui.",
            delete_after=5
        )

    # ==========================================================
    # USER TOTAL
    # ==========================================================

    @commands.command(
        name="donasiku"
    )
    async def my_donation(
        self,
        ctx,
        member: discord.Member = None
    ):

        target = member or ctx.author

        total = self.db.get_user_total(
            target.id,
            "rupiah"
        )

        embed = discord.Embed(
            title="💰 Statistik Donasi",
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

        await ctx.send(
            embed=embed
        )

    # ==========================================================
    # SETUP LEADERBOARD
    # ==========================================================

    @commands.command(
        name="setupdonatur"
    )
    @commands.has_permissions(administrator=True)
    async def setup_donatur(
        self,
        ctx
    ):

        await self.update_leaderboard(
            ctx.guild
        )

        await ctx.send(
            "✅ Leaderboard Donatur berhasil dibuat.",
            delete_after=5
        )


async def setup(bot):
    await bot.add_cog(DonationControl(bot))