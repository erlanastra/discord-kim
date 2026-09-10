import discord
from discord import app_commands
from discord.ext import commands

# ID Channel Khusus Request Role
TARGET_CHANNEL_ID = 1547540103117803520

class RoleRequestModal(discord.ui.Modal, title="Form Request Role Kustom"):
    role_name = discord.ui.TextInput(
        label="Nama Role",
        placeholder="Contoh: ✨ King of Night",
        max_length=50,
        required=True
    )
    
    role_color = discord.ui.TextInput(
        label="Kode Warna Hex",
        placeholder="Contoh: #FF5733 atau #00ffcc",
        max_length=7,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Validasi tambahan: pastikan interaksi dilakukan di channel yang benar
        if interaction.channel.id != TARGET_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ Request role hanya bisa dilakukan di channel khusus <#{TARGET_CHANNEL_ID}>!",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        member = interaction.user
        name = self.role_name.value
        color_code = self.role_color.value.strip()

        # Validasi format warna hex
        try:
            if color_code.startswith("#"):
                color_value = int(color_code[1:], 16)
            else:
                color_value = int(color_code, 16)
            discord_color = discord.Color(color_value)
        except ValueError:
            await interaction.followup.send(
                "❌ Kode warna tidak valid! Gunakan format Hex seperti `#FF5733`.",
                ephemeral=True
            )
            return

        try:
            # 1. Buat role baru di server
            new_role = await guild.create_role(
                name=name,
                color=discord_color,
                reason=f"Request kustom oleh {member.display_name}"
            )

            # 2. Berikan role ke member yang meminta
            await member.add_roles(new_role, reason="Role kustom otomatis dibuatkan.")

            await interaction.followup.send(
                f"✅ Berhasil! Role **{name}** dengan warna `{color_code}` telah dibuat dan otomatis dipasangkan ke kamu!",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Bot tidak memiliki izin (Manage Roles) atau posisi role bot di bawah role yang ingin dibuat.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Terjadi kesalahan: {e}",
                ephemeral=True
            )


class RoleRequestView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Request Role Kustom",
        style=discord.ButtonStyle.primary,
        emoji="🎨",
        custom_id="request_role_btn"
    )
    async def request_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Cek apakah diklik di channel yang tepat
        if interaction.channel.id != TARGET_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ Silakan lakukan request role di channel <#{TARGET_CHANNEL_ID}>!",
                ephemeral=True
            )
            return

        # Memunculkan Modal form saat tombol diklik
        await interaction.response.send_modal(RoleRequestModal())


class RoleRequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="setup-role-panel",
        description="Kirim panel tombol request role ke channel khusus"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_role_panel(self, interaction: discord.Interaction):
        # Validasi command harus dijalankan di channel target
        if interaction.channel.id != TARGET_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ Command ini hanya bisa digunakan di dalam channel <#{TARGET_CHANNEL_ID}>!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🎨 Request Role Kustom nanZ Server",
            description=(
                "Mau punya role eksklusif dengan warna pilihanmu sendiri di server?\n\n"
                "Klik tombol di bawah ini untuk mengisi formulir **Nama Role** dan **Kode Warna Hex** kamu!\n\n"
                "⚠️ *Pastikan kode warna menggunakan format Hex (contoh: `#FF0000` untuk merah).* "
            ),
            color=0x5865F2
        )
        embed.set_footer(text="nanZ Server • Custom Role System")

        await interaction.channel.send(embed=embed, view=RoleRequestView())
        await interaction.response.send_message("✅ Panel request role berhasil dikirim!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(RoleRequestCog(bot))