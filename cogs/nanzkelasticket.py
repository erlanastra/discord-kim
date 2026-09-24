import discord
from discord.ext import commands, tasks
from discord import app_commands
import io
import aiohttp
import aiomysql
from PIL import Image, ImageDraw, ImageFont
import datetime

# ================================
# CONFIGURATION & CONSTANTS
# ================================
APPROVAL_CHANNEL_ID = 123456789012345678      # Channel approval pengajuan kelas
DAFTAR_KELAS_CHANNEL_ID = 876543210987654321  # Channel tempat panel kartu kelas dipublish
RUANG_KELAS_CATEGORY_ID = 112233445566778899  # Kategori Voice Channel kelas baru
PEMBATAS_ROLE_ID = 998877665544332211         # ID Role Pembatas di server

# Konfigurasi Database MySQL/MariaDB
DB_CONFIG = {
    "host": "localhost",
    "user": "nanzuser",         # GANTI DARI 'root' KE 'nanzuser'
    "password": "nanzserversolid",
    "db": "nanz_bot",
    "autocommit": True
}

# ================================
# MODAL: FORMULIR BUAT KELAS
# ================================
class ClassCreationModal(discord.ui.Modal, title="Formulir Pendaftaran Kelas nanZ"):
    nama_kelas = discord.ui.TextInput(
        label="Nama Kelas",
        placeholder="Contoh: Class XI RPL 1",
        max_length=50,
        required=True
    )
    motto_kelas = discord.ui.TextInput(
        label="Motto Kelas",
        placeholder="Contoh: Pantang menyerah sebelum sukses",
        max_length=100,
        required=False
    )
    deskripsi_kelas = discord.ui.TextInput(
        label="Deskripsi / Tentang Kelas",
        placeholder="Jelaskan secara singkat kegiatan atau tujuan kelas...",
        style=discord.TextStyle.paragraph,
        max_length=300,
        required=True
    )
    warna_hex = discord.ui.TextInput(
        label="Warna Role (Kode HEX)",
        placeholder="#3498db",
        max_length=7,
        default="#3498db",
        required=True
    )
    logo_url = discord.ui.TextInput(
        label="URL Logo Kelas (Direct Image Link)",
        placeholder="https://example.com/logo.png",
        required=False
    )

    def __init__(self, staff_member: discord.Member):
        super().__init__()
        self.staff_member = staff_member

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        approval_channel = interaction.guild.get_channel(APPROVAL_CHANNEL_ID)
        if not approval_channel:
            return await interaction.followup.send("❌ Channel approval tidak ditemukan!", ephemeral=True)

        # Buat Embed Pengajuan ke Staff / Admin
        embed = discord.Embed(
            title="📋 Pengajuan Kelas Baru (Sistem Kelas nanZ)",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="Owner Kelas", value=interaction.user.mention, inline=True)
        embed.add_field(name="Staff Penanggung Jawab", value=self.staff_member.mention, inline=True)
        embed.add_field(name="Nama Kelas", value=self.nama_kelas.value, inline=False)
        embed.add_field(name="Motto", value=self.motto_kelas.value or "-", inline=False)
        embed.add_field(name="Deskripsi", value=self.deskripsi_kelas.value, inline=False)
        embed.add_field(name="Warna Role (HEX)", value=self.warna_hex.value, inline=True)
        
        if self.logo_url.value:
            embed.set_thumbnail(url=self.logo_url.value)

        data_payload = {
            "owner_id": interaction.user.id,
            "staff_id": self.staff_member.id,
            "nama": self.nama_kelas.value,
            "motto": self.motto_kelas.value or "-",
            "deskripsi": self.deskripsi_kelas.value,
            "warna": self.warna_hex.value,
            "logo": self.logo_url.value or None
        }

        view = ClassApprovalView(data_payload)
        await approval_channel.send(embed=embed, view=view)
        await interaction.followup.send("✅ Pengajuan kelas berhasil dikirim ke Staff/Admin untuk ditinjau!", ephemeral=True)

# ================================
# VIEW: TRIGGER BUTTON FORMULIR
# ================================
class ClassFormTriggerView(discord.ui.View):
    def __init__(self, staff_member: discord.Member):
        super().__init__(timeout=300)
        self.staff_member = staff_member

    @discord.ui.button(label="📋 Buka Form Pengajuan", style=discord.ButtonStyle.primary, custom_id="open_class_modal")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ClassCreationModal(self.staff_member))

# ================================
# GENERATOR KARTU KELAS (IMAGE)
# ================================
async def generate_class_card(nama_kelas: str, motto: str, deskripsi: str, total_anggota: int, logo_url: str = None) -> io.BytesIO:
    width, height = 800, 400
    img = Image.new("RGBA", (width, height), (24, 28, 36, 255))
    draw = ImageDraw.Draw(img)

    # Accent Background Header
    draw.rectangle([(0, 0), (width, 10)], fill=(52, 152, 219, 255))

    try:
        font_title = ImageFont.truetype("arial.ttf", 36)
        font_sub = ImageFont.truetype("arial.ttf", 20)
        font_text = ImageFont.truetype("arial.ttf", 16)
    except:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_text = ImageFont.load_default()

    # Load Logo
    if logo_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(logo_url) as resp:
                    if resp.status == 200:
                        logo_data = await resp.read()
                        logo_img = Image.open(io.BytesIO(logo_data)).convert("RGBA")
                        logo_img = logo_img.resize((120, 120))
                        img.paste(logo_img, (40, 40), logo_img)
        except Exception:
            draw.rectangle([(40, 40), (160, 160)], fill=(40, 45, 55, 255))
            draw.text((65, 90), "LOG0", font=font_sub, fill=(150, 150, 150, 255))
    else:
        draw.rectangle([(40, 40), (160, 160)], fill=(40, 45, 55, 255))
        draw.text((65, 90), "LOGO", font=font_sub, fill=(150, 150, 150, 255))

    # Teks Informasi
    draw.text((180, 40), nama_kelas, font=font_title, fill=(255, 255, 255, 255))
    draw.text((180, 85), f'"{motto}"', font=font_sub, fill=(52, 152, 219, 255))

    # Garis Pembatas
    draw.line([(40, 180), (760, 180)], fill=(50, 55, 65, 255), width=2)

    # Deskripsi & Stats
    draw.text((40, 200), "Deskripsi Kelas:", font=font_sub, fill=(200, 200, 200, 255))
    
    # Simple Text Wrapping
    words = deskripsi.split(' ')
    lines = []
    curr_line = ""
    for w in words:
        if len(curr_line + " " + w) < 70:
            curr_line += " " + w
        else:
            lines.append(curr_line)
            curr_line = w
    lines.append(curr_line)

    y_pos = 230
    for line in lines[:4]:
        draw.text((40, y_pos), line.strip(), font=font_text, fill=(170, 170, 170, 255))
        y_pos += 22

    draw.text((40, 340), f"👥 Total Member: {total_anggota} Anggota", font=font_sub, fill=(46, 204, 113, 255))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# ================================
# VIEW PERSISTENT: PANEL DAFTAR KELAS
# ================================
class ClassPublicPanel(discord.ui.View):
    def __init__(self, class_id: int):
        super().__init__(timeout=None)
        self.class_id = class_id

        # Update Custom ID unik untuk Persistence
        self.children[0].custom_id = f"join_class:{class_id}"
        self.children[1].custom_id = f"view_members:{class_id}"

    @discord.ui.button(label="📝 Daftar Kelas", style=discord.ButtonStyle.success)
    async def join_class(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        async with aiomysql.connect(**DB_CONFIG) as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                # Ambil Data Kelas
                await cur.execute("SELECT * FROM nanz_classes WHERE class_id = %s", (self.class_id,))
                class_info = await cur.fetchone()

                if not class_info:
                    return await interaction.followup.send("❌ Kelas ini tidak ditemukan di sistem!", ephemeral=True)

                # Cek Apakah Sudah Menjadi Member
                await cur.execute(
                    "SELECT * FROM nanz_class_members WHERE class_id = %s AND user_id = %s",
                    (self.class_id, interaction.user.id)
                )
                if await cur.fetchone():
                    return await interaction.followup.send("⚠️ Kamu sudah terdaftar di kelas ini!", ephemeral=True)

                # Cek Apakah User Sudah Punya Kelas Lain
                await cur.execute("SELECT * FROM nanz_class_members WHERE user_id = %s", (interaction.user.id,))
                if await cur.fetchone():
                    return await interaction.followup.send("⚠️ Kamu sudah terdaftar di kelas lain! Keluar dari kelas sebelumnya terlebih dahulu.", ephemeral=True)

                # Simpan Anggota Baru
                await cur.execute(
                    "INSERT INTO nanz_class_members (class_id, user_id) VALUES (%s, %s)",
                    (self.class_id, interaction.user.id)
                )

                # Pasang Role Kelas
                role = interaction.guild.get_role(class_info["role_id"])
                if role:
                    await interaction.user.add_roles(role)

                # Hitung Total Member Baru
                await cur.execute("SELECT COUNT(*) as cnt FROM nanz_class_members WHERE class_id = %s", (self.class_id,))
                res = await cur.fetchone()
                total_member = res["cnt"]

        # Update Tampilan Kartu Kelas di Discord Channel
        card_img = await generate_class_card(
            class_info["name"],
            class_info["motto"],
            class_info["description"],
            total_member,
            class_info["logo_url"]
        )
        file = discord.File(card_img, filename="class_card.png")
        
        try:
            await interaction.message.edit(attachments=[file])
        except Exception:
            pass

        await interaction.followup.send(f"🎉 Selamat! Kamu berhasil bergabung dengan kelas **{class_info['name']}**!", ephemeral=True)

    @discord.ui.button(label="👥 Lihat Anggota", style=discord.ButtonStyle.secondary)
    async def view_members(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        async with aiomysql.connect(**DB_CONFIG) as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT name FROM nanz_classes WHERE class_id = %s", (self.class_id,))
                class_info = await cur.fetchone()

                await cur.execute("SELECT user_id FROM nanz_class_members WHERE class_id = %s", (self.class_id,))
                members = await cur.fetchall()

        if not class_info:
            return await interaction.followup.send("❌ Data kelas tidak ditemukan.", ephemeral=True)

        member_mentions = [f"<@{m['user_id']}>" for m in members]
        list_str = "\n".join(f"{idx+1}. {mention}" for idx, mention in enumerate(member_mentions)) if member_mentions else "Belum ada anggota."

        embed = discord.Embed(
            title=f"👥 Anggota Kelas: {class_info['name']}",
            description=list_str,
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

# ================================
# VIEW: APPROVAL / REJECT BY STAFF
# ================================
class ClassApprovalView(discord.ui.View):
    def __init__(self, data: dict):
        super().__init__(timeout=None)
        self.data = data

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        guild = interaction.guild
        owner = guild.get_member(self.data["owner_id"])

        # Convert Hex Color
        try:
            color_int = int(self.data["warna"].replace("#", ""), 16)
            role_color = discord.Color(color_int)
        except:
            role_color = discord.Color.blue()

        # 1. Buat Role Kelas
        role = await guild.create_role(name=f"Kelas | {self.data['nama']}", color=role_color)

        # Positioning Role Dibawah Pembatas
        pembatas_role = guild.get_role(PEMBATAS_ROLE_ID)
        if pembatas_role:
            try:
                await role.edit(position=pembatas_role.position - 1)
            except:
                pass

        if owner:
            await owner.add_roles(role)

        # 2. Buat Voice Channel Kelas
        category = guild.get_channel(RUANG_KELAS_CATEGORY_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=False),
            role: discord.PermissionOverwrite(connect=True, speak=True)
        }
        vc = await guild.create_voice_channel(
            name=f"🔊│{self.data['nama']}",
            category=category,
            overwrites=overwrites
        )

        # 3. Simpan Ke Database (Berlaku 30 Hari)
        due_date = datetime.datetime.now() + datetime.timedelta(days=30)

        async with aiomysql.connect(**DB_CONFIG) as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO nanz_classes 
                    (name, motto, description, color_hex, logo_url, role_id, vc_id, staff_id, owner_id, due_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    self.data["nama"], self.data["motto"], self.data["deskripsi"],
                    self.data["warna"], self.data["logo"], role.id, vc.id,
                    self.data["staff_id"], self.data["owner_id"], due_date
                ))
                class_id = cur.lastrowid

                # Daftarkan Owner sebagai Member Pertama
                await cur.execute(
                    "INSERT INTO nanz_class_members (class_id, user_id) VALUES (%s, %s)",
                    (class_id, self.data["owner_id"])
                )

        # 4. Kirim Panel Kartu Kelas
        daftar_channel = guild.get_channel(DAFTAR_KELAS_CHANNEL_ID)
        if daftar_channel:
            card_img = await generate_class_card(
                self.data["nama"], self.data["motto"], self.data["deskripsi"], 1, self.data["logo"]
            )
            file = discord.File(card_img, filename="class_card.png")
            panel_msg = await daftar_channel.send(file=file, view=ClassPublicPanel(class_id))

            # Simpan Message ID untuk Update
            async with aiomysql.connect(**DB_CONFIG) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("UPDATE nanz_classes SET panel_message_id = %s WHERE class_id = %s", (panel_msg.id, class_id))

        # Disable Tombol
        for item in self.children:
            item.disabled = True

        await interaction.message.edit(content=f"✅ **Kelas Diterima & Dibuat oleh {interaction.user.mention}!**", view=self)

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(content=f"❌ **Pengajuan Ditolak oleh {interaction.user.mention}.**", view=self)

# ================================
# COG COMMANDS & BOT EVENTS
# ================================
class NanzKelasCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_class_expiration.start()

    def cog_unload(self):
        self.check_class_expiration.cancel()

    # Re-register Button Handlers saat Bot Menyala (Persistence)
    @commands.Cog.listener()
    async def on_ready(self):
        async with aiomysql.connect(**DB_CONFIG) as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT class_id FROM nanz_classes WHERE status = 'Active'")
                rows = await cur.fetchall()
                for row in rows:
                    self.bot.add_view(ClassPublicPanel(row["class_id"]))

    # Periksa Masa Aktif Kelas Setiap 1 Jam
    @tasks.loop(hours=1)
    async def check_class_expiration(self):
        now = datetime.datetime.now()
        async with aiomysql.connect(**DB_CONFIG) as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT * FROM nanz_classes WHERE status = 'Active' AND due_date <= %s", (now,))
                expired_classes = await cur.fetchall()

                for cls in expired_classes:
                    guild = self.bot.get_guild(cls.get("guild_id")) # Pasang server ID jika multi-guild
                    if guild:
                        role = guild.get_role(cls["role_id"])
                        vc = guild.get_channel(cls["vc_id"])

                        if role:
                            try: await role.delete()
                            except: pass
                        if vc:
                            try: await vc.delete()
                            except: pass

                        # Hapus Panel Kartu
                        daftar_channel = guild.get_channel(DAFTAR_KELAS_CHANNEL_ID)
                        if daftar_channel and cls["panel_message_id"]:
                            try:
                                msg = await daftar_channel.fetch_message(cls["panel_message_id"])
                                await msg.delete()
                            except: pass

                    await cur.execute("UPDATE nanz_classes SET status = 'Expired' WHERE class_id = %s", (cls["class_id"],))

    # ================================
    # LIST PERINTAH / COMMANDS
    # ================================

    # 1. Command Utama Pengajuan
    @commands.command(name="buat_kelas")
    @commands.has_permissions(administrator=True)
    async def buat_kelas(self, ctx: commands.Context, staff: discord.Member):
        """Memulai sesi pendaftaran kelas bersama Staff."""
        embed = discord.Embed(
            title="🏫 Pendaftaran Kelas nanZ",
            description=f"Silakan klik tombol di bawah untuk mengisi formulir pendaftaran kelas.\n**Staff Penanggung Jawab:** {staff.mention}",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed, view=ClassFormTriggerView(staff))

    # 2. Command Perpanjang Sewa Kelas
    @commands.command(name="perpanjang_kelas")
    @commands.has_permissions(administrator=True)
    async def perpanjang_kelas(self, ctx: commands.Context, class_id: int, hari: int = 30):
        """Memperpanjang masa aktif kelas (default 30 hari)."""
        async with aiomysql.connect(**DB_CONFIG) as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT * FROM nanz_classes WHERE class_id = %s", (class_id,))
                cls = await cur.fetchone()

                if not cls:
                    return await ctx.send("❌ ID Kelas tidak ditemukan.")

                new_due = cls["due_date"] + datetime.timedelta(days=hari)
                await cur.execute("UPDATE nanz_classes SET due_date = %s, status = 'Active' WHERE class_id = %s", (new_due, class_id))

        await ctx.send(f"✅ Masa aktif kelas **{cls['name']}** berhasil diperpanjang hingga **{new_due.strftime('%Y-%m-%d %H:%M:%S')}**.")

    # 3. Command Hapus Kelas Permanen
    @commands.command(name="hapus_kelas")
    @commands.has_permissions(administrator=True)
    async def hapus_kelas(self, ctx: commands.Context, class_id: int):
        """Menghapus kelas, role, channel, dan panel secara manual."""
        async with aiomysql.connect(**DB_CONFIG) as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT * FROM nanz_classes WHERE class_id = %s", (class_id,))
                cls = await cur.fetchone()

                if not cls:
                    return await ctx.send("❌ Kelas tidak ditemukan.")

                role = ctx.guild.get_role(cls["role_id"])
                vc = ctx.guild.get_channel(cls["vc_id"])

                if role:
                    try: await role.delete()
                    except: pass
                if vc:
                    try: await vc.delete()
                    except: pass

                daftar_channel = ctx.guild.get_channel(DAFTAR_KELAS_CHANNEL_ID)
                if daftar_channel and cls["panel_message_id"]:
                    try:
                        msg = await daftar_channel.fetch_message(cls["panel_message_id"])
                        await msg.delete()
                    except: pass

                await cur.execute("DELETE FROM nanz_classes WHERE class_id = %s", (class_id,))

        await ctx.send(f"🗑️ Kelas **{cls['name']}** berhasil dihapus secara permanen dari server dan database.")

    # 4. Command Keluar dari Kelas
    @commands.command(name="keluar_kelas")
    async def keluar_kelas(self, ctx: commands.Context):
        """Perintah bagi member untuk keluar dari kelas tempat mereka terdaftar."""
        async with aiomysql.connect(**DB_CONFIG) as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT class_id FROM nanz_class_members WHERE user_id = %s", (ctx.author.id,))
                member_record = await cur.fetchone()

                if not member_record:
                    return await ctx.send("⚠️ Kamu belum terdaftar di kelas manapun.")

                class_id = member_record["class_id"]

                await cur.execute("SELECT * FROM nanz_classes WHERE class_id = %s", (class_id,))
                cls = await cur.fetchone()

                if cls and cls["owner_id"] == ctx.author.id:
                    return await ctx.send("❌ Kamu adalah **Owner** kelas ini! Gunakan bantuan Admin/Staff jika ingin membubarkan atau memindahkan kepemilikan kelas.")

                # Hapus dari DB
                await cur.execute("DELETE FROM nanz_class_members WHERE class_id = %s AND user_id = %s", (class_id, ctx.author.id))

                # Lepas Role
                if cls:
                    role = ctx.guild.get_role(cls["role_id"])
                    if role:
                        await ctx.author.remove_roles(role)

                # Update Jumlah Anggota di Panel
                await cur.execute("SELECT COUNT(*) as cnt FROM nanz_class_members WHERE class_id = %s", (class_id,))
                total_member = (await cur.fetchone())["cnt"]

        if cls and cls["panel_message_id"]:
            daftar_channel = ctx.guild.get_channel(DAFTAR_KELAS_CHANNEL_ID)
            if daftar_channel:
                try:
                    msg = await daftar_channel.fetch_message(cls["panel_message_id"])
                    card_img = await generate_class_card(cls["name"], cls["motto"], cls["description"], total_member, cls["logo_url"])
                    await msg.edit(attachments=[discord.File(card_img, filename="class_card.png")])
                except: pass

        await ctx.send(f"✅ Kamu berhasil keluar dari kelas **{cls['name'] if cls else ''}**.")

    # 5. Command Kick Anggota dari Kelas (Owner / Staff Only)
    @commands.command(name="kick_kelas")
    async def kick_kelas(self, ctx: commands.Context, target: discord.Member):
        """Mengeluarkan anggota tertentu dari kelas (Bisa dilakukan oleh Owner Kelas atau Admin/Staff)."""
        async with aiomysql.connect(**DB_CONFIG) as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                # Cari Kelas dari Target
                await cur.execute("SELECT class_id FROM nanz_class_members WHERE user_id = %s", (target.id,))
                target_record = await cur.fetchone()

                if not target_record:
                    return await ctx.send("⚠️ Target member tidak terdaftar di kelas manapun.")

                class_id = target_record["class_id"]

                await cur.execute("SELECT * FROM nanz_classes WHERE class_id = %s", (class_id,))
                cls = await cur.fetchone()

                # Cek Wewenang (Harus Admin atau Owner Kelas)
                is_admin = ctx.author.guild_permissions.administrator
                is_owner = (cls["owner_id"] == ctx.author.id)

                if not (is_admin or is_owner):
                    return await ctx.send("❌ Kamu tidak memiliki izin untuk mengeluarkan anggota dari kelas ini!")

                if target.id == cls["owner_id"]:
                    return await ctx.send("❌ Owner kelas tidak bisa dikeluarkan dari kelasnya sendiri.")

                # Proses Kick
                await cur.execute("DELETE FROM nanz_class_members WHERE class_id = %s AND user_id = %s", (class_id, target.id))

                role = ctx.guild.get_role(cls["role_id"])
                if role:
                    await target.remove_roles(role)

                await cur.execute("SELECT COUNT(*) as cnt FROM nanz_class_members WHERE class_id = %s", (class_id,))
                total_member = (await cur.fetchone())["cnt"]

        if cls and cls["panel_message_id"]:
            daftar_channel = ctx.guild.get_channel(DAFTAR_KELAS_CHANNEL_ID)
            if daftar_channel:
                try:
                    msg = await daftar_channel.fetch_message(cls["panel_message_id"])
                    card_img = await generate_class_card(cls["name"], cls["motto"], cls["description"], total_member, cls["logo_url"])
                    await msg.edit(attachments=[discord.File(card_img, filename="class_card.png")])
                except: pass

        await ctx.send(f"✅ Member {target.mention} berhasil dikeluarkan dari kelas **{cls['name']}**.")

# Setup Cog Loader
async def setup(bot: commands.Bot):
    await bot.add_cog(NanzKelasCog(bot))