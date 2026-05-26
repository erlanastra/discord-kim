import discord
from discord.ext import commands

# ================= CONFIG =================
GAME_ROLES = {

    "PUBG": {
        "id": 1453431240785920062,
        "emoji": "🔫"
    },

    "Delta Force": {
        "id": 1453429436593606676,
        "emoji": "🪖"
    },

    "Valorant": {
        "id": 1453428694839197909,
        "emoji": "🎯"
    },

    "Minecraft": {
        "id": 1453429627107283117,
        "emoji": "⛏️"
    },

    "Mobile Legends": {
        "id": 1453427876488548543,
        "emoji": "📱"
    },

    "GTA V": {
        "id": 1453428309126943015,
        "emoji": "🚗"
    },

    "Roblox": {
        "id": 1453428932337467545,
        "emoji": "🧩"
    },

    "HOK (Honor of Kings)": {
        "id": 1453429049870389400,
        "emoji": "⚔️"
    },

    "Free Fire": {
        "id": 1466748111555788972,
        "emoji": "🔥"
    },

    "Efootball": {
        "id": 1508719481289965639,
        "emoji": "⚽"
    },

    "EA FC": {
        "id": 1508719106415788103,
        "emoji": "🏆"
    }
}


# ================= SELECT =================
class GameSelect(discord.ui.Select):

    def __init__(self):

        options = []

        for name, data in GAME_ROLES.items():

            options.append(
                discord.SelectOption(
                    label=name,
                    value=str(data["id"]),
                    emoji=data["emoji"]
                )
            )

        super().__init__(
            placeholder="🎮 Pilih game favorit kamu...",
            min_values=1,
            max_values=5,
            options=options,
            custom_id="game_roles_select"
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
        for name, data in GAME_ROLES.items():

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
class GameView(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=None)

        self.add_item(
            GameSelect()
        )


# ================= COG =================
class GameRoles(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    @commands.command(name="setup_game")
    @commands.has_permissions(administrator=True)
    async def setup_game(self, ctx):

        embed = discord.Embed(
            title="Game Roles Panel",
            description=(
                "Pilih game role untuk mendapatkan role.\n"
                "Kamu bisa mengganti role kapan saja."
            ),
            color=0x8B5CF6
        )

        embed.add_field(
            name="Available Roles",
            value=(
                "🔫 PUBG\n"
                "🪖 Delta Force\n"
                "🎯 Valorant\n"
                "⛏️ Minecraft\n"
                "📱 Mobile Legends\n"
                "🚗 GTA V\n"
                "🧩 Roblox\n"
                "⚔️ HOK (Honor of Kings)\n"
                "🔥 Free Fire\n"
                "⚽ Efootball\n"
                "🏆 EA FC"
            ),
            inline=False
        )

        # ================= FOTO PANEL =================
        file = discord.File(
            "assets/banner_game.png",
            filename="game.png"
        )

        embed.set_image(
            url="attachment://game.png"
        )

        embed.set_footer(
            text="nanZ Server"
        )

        await ctx.send(
            embed=embed,
            view=GameView(),
            file=file
        )


# ================= SETUP =================
async def setup(bot):

    await bot.add_cog(
        GameRoles(bot)
    )