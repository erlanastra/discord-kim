import discord
from discord.ext import commands


class NanzPanel(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    # ============================================================
    # CONFIG
    # ============================================================

    SERVER_ID = 1406557880475320340

    # ================= ROLE SPECIAL =================

    SPECIAL_ROLES = {

        "nZ Loyalist": {
            "role_id": 1555892286704062529,
            "description": (
                "Gunakan **Server Tag nZ** "
                "untuk mendapatkan role ini."
            )
        },

        "nZ Apipi": {
            "role_id": 1555862680605167646,
            "description": (
                "Role khusus yang dapat diperoleh "
                "melalui sistem Apipi."
            )
        },

        "VIP OwO": {
            "role_id": 1528766890296611017,
            "description": (
                "Role VIP yang diperoleh melalui "
                "**donasi OwO**."
            )
        },

        "VIP Rupiah": {
            "role_id": 1528766033509220572,
            "description": (
                "Role VIP yang diperoleh melalui "
                "**donasi Rupiah**."
            )
        }
    }

    # ================= EVENT WINNER =================

    EVENT_ROLES = {

        "Riddle — Season 1": {
            "role_id": 1514600587772035124
        },

        "Riddle — Season 2": {
            "role_id": 1517563935321227516
        },

        "nanZ100 — Season 1": {
            "role_id": 1514922900132593745
        }
    }

    # ================= ANNIVERSARY =================

    ANNIVERSARY_ROLES = {

        "Winner Clip — Agustus 2026": {
            "role_id": 1538539964290170994
        },

        "Winner Poster — Agustus 2026": {
            "role_id": 1538538863927099482
        },

        "Winner Sambung Kata — Agustus 2026": {
            "role_id": 1538540210223059084
        },

        "Winner Mole — Agustus 2026": {
            "role_id": 1538539398302539817
        },

        "Winner FanArt — Agustus 2026": {
            "role_id": 1538539261865762866
        },

        "nanZ Award — Most Voice 2026": {
            "role_id": 1538572694860210250
        },

        "nanZ Award — Most Chatting 2026": {
            "role_id": 1538572820752367756
        },

        "nanZ Award — Most Girls of the Girls 2026": {
            "role_id": 1538572966734995526
        },

        "nanZ Award — Most Brain 2026": {
            "role_id": 1538573098016706570
        }
    }

    # ============================================================
    # CHANNEL LINK
    # ============================================================

    def channel_url(self, channel_id):

        return (
            f"https://discord.com/channels/"
            f"{self.SERVER_ID}/"
            f"{channel_id}"
        )

    # ============================================================
    # MAIN EMBED
    # ============================================================

    def create_panel_embed(self):

        embed = discord.Embed(
            title="✦ Role Special nanZ",
            description=(
                "Kumpulan **role spesial** yang tersedia "
                "di **nanZ Server**.\n\n"
                "Pilih kategori melalui menu di bawah "
                "untuk melihat informasi lengkap setiap role."
            ),
            color=0x5865F2
        )

        embed.add_field(
            name="✦ Special Role",
            value=(
                "Role khusus yang dapat diperoleh "
                "melalui aktivitas atau kontribusi tertentu."
            ),
            inline=False
        )

        embed.add_field(
            name="🏆 Event Winner",
            value=(
                "Role penghargaan khusus untuk "
                "para pemenang event nanZ."
            ),
            inline=False
        )

        embed.add_field(
            name="🎉 nanZ Anniversary 2026",
            value=(
                "Kumpulan award spesial dalam rangka "
                "**Anniversary nanZ — Agustus 2026**."
            ),
            inline=False
        )

        embed.set_footer(
            text="nanZ Server • Stay Solid!"
        )

        return embed

    # ============================================================
    # SPECIAL EMBED
    # ============================================================

    def create_special_embed(self):

        embed = discord.Embed(
            title="✦ Special Role",
            description=(
                "Role spesial yang dapat diperoleh "
                "oleh murid nanZ."
            ),
            color=0x5865F2
        )

        for name, data in self.SPECIAL_ROLES.items():

            role = f"<@&{data['role_id']}>"

            embed.add_field(
                name=f"◆ {name}",
                value=(
                    f"{role}\n"
                    f"{data['description']}"
                ),
                inline=False
            )

        embed.set_footer(
            text="Pilih tombol di bawah untuk melihat panduan."
        )

        return embed

    # ============================================================
    # EVENT EMBED
    # ============================================================

    def create_event_embed(self):

        embed = discord.Embed(
            title="🏆 Role Pemenang Event",
            description=(
                "Role penghargaan khusus untuk "
                "pemenang event nanZ."
            ),
            color=0xFEE75C
        )

        for name, data in self.EVENT_ROLES.items():

            role = f"<@&{data['role_id']}>"

            embed.add_field(
                name=f"◆ {name}",
                value=role,
                inline=False
            )

        embed.set_footer(
            text="Role diberikan kepada pemenang event."
        )

        return embed

    # ============================================================
    # ANNIVERSARY EMBED
    # ============================================================

    def create_anniversary_embed(self):

        embed = discord.Embed(
            title="🎉 nanZ Anniversary Awards 2026",
            description=(
                "**Agustus 2026** menjadi bulan spesial "
                "bagi nanZ.\n\n"
                "Berikut penghargaan untuk para "
                "pemenang dan penerima award Anniversary nanZ."
            ),
            color=0xED4245
        )

        for name, data in self.ANNIVERSARY_ROLES.items():

            role = f"<@&{data['role_id']}>"

            embed.add_field(
                name=f"◆ {name}",
                value=role,
                inline=False
            )

        embed.set_footer(
            text="nanZ Anniversary 2026 • Stay Solid!"
        )

        return embed

    # ============================================================
    # MAIN PANEL VIEW
    # ============================================================

    class PanelView(discord.ui.View):

        def __init__(self, cog):

            super().__init__(
                timeout=None
            )

            self.cog = cog

            self.add_item(
                NanzPanel.CategorySelect(cog)
            )

    # ============================================================
    # CATEGORY SELECT
    # ============================================================

    class CategorySelect(discord.ui.Select):

        def __init__(self, cog):

            self.cog = cog

            options = [

                discord.SelectOption(
                    label="Role Special",
                    description="Lihat role special nanZ",
                    emoji="✦",
                    value="special"
                ),

                discord.SelectOption(
                    label="Event Winner",
                    description="Lihat role pemenang event",
                    emoji="🏆",
                    value="event"
                ),

                discord.SelectOption(
                    label="Anniversary 2026",
                    description="Lihat award Anniversary nanZ",
                    emoji="🎉",
                    value="anniversary"
                )
            ]

            super().__init__(
                placeholder="Pilih kategori role...",
                options=options,
                custom_id="nanz_panel_category"
            )

        async def callback(
            self,
            interaction: discord.Interaction
        ):

            value = self.values[0]

            if value == "special":

                embed = self.cog.create_special_embed()

                view = NanzPanel.SpecialView()

            elif value == "event":

                embed = self.cog.create_event_embed()

                view = NanzPanel.BackView()

            else:

                embed = self.cog.create_anniversary_embed()

                view = NanzPanel.BackView()

            await interaction.response.edit_message(
                embed=embed,
                view=view
            )

    # ============================================================
    # SPECIAL VIEW
    # ============================================================

    class SpecialView(discord.ui.View):

        def __init__(self):

            super().__init__(
                timeout=None
            )

            self.add_item(
                discord.ui.Button(
                    label="Cara Dapat nZ Apipi",
                    emoji="✦",
                    style=discord.ButtonStyle.link,
                    url=(
                        "https://discord.com/channels/"
                        "1406557880475320340/"
                        "1555862444054814740"
                    )
                )
            )

            self.add_item(
                discord.ui.Button(
                    label="Cara Dapat VIP",
                    emoji="💎",
                    style=discord.ButtonStyle.link,
                    url=(
                        "https://discord.com/channels/"
                        "1406557880475320340/"
                        "1550884157435936908"
                    )
                )
            )

            self.add_item(
                NanzPanel.BackButton()
            )

    # ============================================================
    # BACK VIEW
    # ============================================================

    class BackView(discord.ui.View):

        def __init__(self):

            super().__init__(
                timeout=None
            )

            self.add_item(
                NanzPanel.BackButton()
            )

    # ============================================================
    # BACK BUTTON
    # ============================================================

    class BackButton(discord.ui.Button):

        def __init__(self):

            super().__init__(
                label="Kembali",
                emoji="↩️",
                style=discord.ButtonStyle.secondary,
                custom_id="nanz_panel_back"
            )

        async def callback(
            self,
            interaction: discord.Interaction
        ):

            cog = interaction.client.get_cog(
                "NanzPanel"
            )

            if not cog:
                return

            embed = cog.create_panel_embed()

            view = NanzPanel.PanelView(cog)

            await interaction.response.edit_message(
                embed=embed,
                view=view
            )

    # ============================================================
    # COMMAND PANEL
    # ============================================================

    @commands.command(name="panel")
    @commands.cooldown(
        1,
        5,
        commands.BucketType.user
    )
    async def panel(self, ctx):

        if ctx.guild is None:

            embed = discord.Embed(
                title="❌ Tidak Bisa Digunakan",
                description=(
                    "Command ini hanya bisa digunakan "
                    "di dalam server."
                ),
                color=0xED4245
            )

            return await ctx.send(
                embed=embed
            )

        embed = self.create_panel_embed()

        view = self.PanelView(self)

        await ctx.send(
            embed=embed,
            view=view
        )

    # ============================================================
    # HIDE COOLDOWN
    # ============================================================

    @panel.error
    async def panel_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.CommandOnCooldown
        ):
            return


# ================================================================
# SETUP
# ================================================================

async def setup(bot):

    cog = NanzPanel(bot)

    await bot.add_cog(cog)

    # ============================================================
    # REGISTER PERSISTENT VIEW
    # ============================================================

    bot.add_view(
        NanzPanel.PanelView(cog)
    )

    bot.add_view(
        NanzPanel.SpecialView()
    )

    bot.add_view(
        NanzPanel.BackView()
    )

