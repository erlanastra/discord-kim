import discord
from discord.ext import commands

# ================= CONFIG =================
MINAT_ROLES = {

    "Movieholic": {
        "id": 1467460832408506449,
        "emoji": "🎬"
    },

    "Chatholic": {
        "id": 1467335359548620913,
        "emoji": "💬"
    },

    "Voiceholic": {
        "id": 1464238891468062812,
        "emoji": "🎧"
    },

    "Artholic": {
        "id": 1464239310504071290,
        "emoji": "🎨"
    },

    "Musicaholic": {
        "id": 1464239362987266150,
        "emoji": "🎶"
    },

    "Gameholic": {
        "id": 1467463033071865989,
        "emoji": "🎮"
    }
}


# ================= SELECT =================
class MinatSelect(discord.ui.Select):

    def __init__(self):

        options = []

        for name, data in MINAT_ROLES.items():

            options.append(
                discord.SelectOption(
                    label=name,
                    value=str(data["id"]),
                    emoji=data["emoji"]
                )
            )

        super().__init__(
            placeholder="✨ Pilih role minat kamu...",
            min_values=1,
            max_values=6,
            options=options,
            custom_id="minat_roles_select"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        selected_ids = [
            int(role_id)
            for role_id in self.values
        ]

        added_roles = []
        removed_roles = []

        # ================= TOGGLE ROLE =================
        for name, data in MINAT_ROLES.items():

            role = interaction.guild.get_role(
                data["id"]
            )

            if not role:
                continue

            # Tambah role
            if role.id in selected_ids:

                if role not in interaction.user.roles:

                    await interaction.user.add_roles(role)

                    added_roles.append(
                        role.mention
                    )

            # Remove role
            else:

                if role in interaction.user.roles:

                    await interaction.user.remove_roles(
                        role
                    )

                    removed_roles.append(
                        role.mention
                    )

        # ================= EMBED OUTPUT =================
        if added_roles:

            embed = discord.Embed(
                description=(
                    f"✅ Role "
                    f"{', '.join(added_roles)} "
                    f"berhasil diambil."
                ),
                color=0x57F287
            )

        elif removed_roles:

            embed = discord.Embed(
                description=(
                    f"❌ Role "
                    f"{', '.join(removed_roles)} "
                    f"berhasil dilepas."
                ),
                color=0xED4245
            )

        else:

            embed = discord.Embed(
                description=(
                    "⚠️ Tidak ada perubahan role."
                ),
                color=0xFEE75C
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# ================= VIEW =================
class MinatView(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=None)

        self.add_item(
            MinatSelect()
        )


# ================= COG =================
class MinatRoles(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    @commands.command(name="setup_minat")
    @commands.has_permissions(administrator=True)
    async def setup_minat(self, ctx):

        embed = discord.Embed(
            title="Role Minat Panel",
            description=(
                "Pilih role minat sesuai kepribadian kamu.\n"
                "Kamu bisa mengganti role kapan saja."
            ),
            color=0x8B5CF6
        )

        embed.add_field(
            name="Daftar Role Minat",
            value=(
                "🎬 Movieholic\n"
                "💬 Chatholic\n"
                "🎧 Voiceholic\n"
                "🎨 Artholic\n"
                "🎶 Musicaholic\n"
                "🎮 Gameholic"
            ),
            inline=False
        )

        # ================= FOTO PANEL =================
        file = discord.File(
            "assets/banner_minat.png",
            filename="minat.png"
        )

        embed.set_image(
            url="attachment://minat.png"
        )

        embed.set_footer(
            text="nanZ Server"
        )

        await ctx.send(
            embed=embed,
            view=MinatView(),
            file=file
        )


# ================= SETUP =================
async def setup(bot):

    await bot.add_cog(
        MinatRoles(bot)
    )