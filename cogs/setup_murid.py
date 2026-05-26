import discord
from discord.ext import commands

# ================= CONFIG =================
MURID_ROLES = {
    "Murid Baik": {
        "id": 1453238775835529237,
        "emoji": "😁"
    },

    "Murid Nakal": {
        "id": 1453239107219230891,
        "emoji": "😈"
    }
}

# ================= SELECT =================
class MuridSelect(discord.ui.Select):

    def __init__(self):

        options = []

        for name, data in MURID_ROLES.items():

            options.append(
                discord.SelectOption(
                    label=name,
                    value=str(data["id"]),
                    emoji=data["emoji"]
                )
            )

        super().__init__(
            placeholder="📚 Pilih tipe murid kamu...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="murid_select"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        selected_role_id = int(self.values[0])

        selected_role = interaction.guild.get_role(
            selected_role_id
        )

        # ================= REMOVE ROLE LAIN =================
        for role_data in MURID_ROLES.values():

            role = interaction.guild.get_role(
                role_data["id"]
            )

            if (
                role in interaction.user.roles
                and role.id != selected_role_id
            ):

                await interaction.user.remove_roles(role)

        # ================= ADD ROLE =================
        if selected_role not in interaction.user.roles:

            await interaction.user.add_roles(
                selected_role
            )

            embed = discord.Embed(
                description=(
                    f"✅ Role "
                    f"{selected_role.mention} "
                    f"berhasil diambil."
                ),
                color=0x57F287
            )

        else:

            embed = discord.Embed(
                description=(
                    f"⚠️ Kamu sudah memiliki "
                    f"role {selected_role.mention}"
                ),
                color=0xFEE75C
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# ================= VIEW =================
class MuridView(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=None)

        self.add_item(
            MuridSelect()
        )


# ================= COG =================
class MuridRole(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    @commands.command(name="setup_murid")
    @commands.has_permissions(administrator=True)
    async def setup_murid(self, ctx):

        embed = discord.Embed(
            title="Murid Roles Panel",
            description=(
                "Pilih tipe murid untuk mendapatkan role.\n"
                "Kamu bisa mengganti role kapan saja."
            ),
            color=0x8B5CF6
        )

        embed.add_field(
            name="Available Roles",
            value=(
                "😁 Murid Baik\n"
                "😈 Murid Nakal"
            ),
            inline=False
        )

        # FOTO PANEL
        file = discord.File(
            "assets/banner_murid.png",
            filename="murid.png"
        )

        embed.set_image(
            url="attachment://murid.png"
        )

        embed.set_footer(
            text="nanZ Server"
        )

        await ctx.send(
            embed=embed,
            view=MuridView(),
            file=file
        )


# ================= SETUP =================
async def setup(bot):

    await bot.add_cog(
        MuridRole(bot)
    )