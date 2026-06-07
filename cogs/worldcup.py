# =========================================================
# nanZ WORLD CUP SYSTEM
# FINAL FULL VERSION
# discord.py 2.x
# =========================================================

import discord
from discord.ext import commands
import re

# =========================================================
# CONFIG
# =========================================================

# =========================================================
# CONFIG
# =========================================================

WORLD_CUP_REGISTER_CHANNEL_ID = 1512623898066161867
WORLD_CUP_CHAT_ID = 1512624241999216672
STAFF_CONTROL_CHANNEL_ID = 1512626594773078228

LINEEMOJI = "<a:fearZOOM:1512641306722041906>"
ROWEMOJI = "<a:DarkBlueArrow:1512640150721659020>"
WC26EMOJI = "<:FIFA2026WorldCup:1512635223769354401>"
JOINEMOJI = "<a:check_yes2:1512649792721911949>"
WRONGEMOJI = "<a:wrong:1512649597070217256>"

MEMBER_ROLE_ID = 1509170748210548776
# =========================================================
# COUNTRIES
# =========================================================

COUNTRIES = {

    # HOST
    "CAN": ("Canada", "🇨🇦", 0xD52B1E),
    "MEX": ("Mexico", "🇲🇽", 0x006847),
    "USA": ("United States", "🇺🇸", 0x3C3B6E),

    # ASIA
    "JPN": ("Japan", "🇯🇵", 0xFFFFFF),
    "IRN": ("Iran", "🇮🇷", 0x239F40),
    "UZB": ("Uzbekistan", "🇺🇿", 0x0099B5),
    "KOR": ("South Korea", "🇰🇷", 0xCD2E3A),
    "JOR": ("Jordan", "🇯🇴", 0x007A3D),
    "AUS": ("Australia", "🇦🇺", 0x012169),
    "QAT": ("Qatar", "🇶🇦", 0x8A1538),
    "KSA": ("Saudi Arabia", "🇸🇦", 0x006C35),
    "IRQ": ("Iraq", "🇮🇶", 0x007A3D),

    # SOUTH AMERICA
    "ARG": ("Argentina", "🇦🇷", 0x74ACDF),
    "BRA": ("Brazil", "🇧🇷", 0x009C3B),
    "ECU": ("Ecuador", "🇪🇨", 0xFCD116),
    "URU": ("Uruguay", "🇺🇾", 0x6CCFF6),
    "COL": ("Colombia", "🇨🇴", 0xFCD116),
    "PAR": ("Paraguay", "🇵🇾", 0xD52B1E),

    # AFRICA
    "MAR": ("Morocco", "🇲🇦", 0xC1272D),
    "TUN": ("Tunisia", "🇹🇳", 0xE70013),
    "EGY": ("Egypt", "🇪🇬", 0xCE1126),
    "ALG": ("Algeria", "🇩🇿", 0x006233),
    "GHA": ("Ghana", "🇬🇭", 0xFCD116),
    "CPV": ("Cape Verde", "🇨🇻", 0x003893),
    "RSA": ("South Africa", "🇿🇦", 0x007749),
    "CIV": ("Ivory Coast", "🇨🇮", 0xF77F00),
    "SEN": ("Senegal", "🇸🇳", 0x00853F),
    "COD": ("DR Congo", "🇨🇩", 0x007FFF),

    # EUROPE
    "ENG": ("England", "🏴", 0xFFFFFF),
    "FRA": ("France", "🇫🇷", 0x0055A4),
    "CRO": ("Croatia", "🇭🇷", 0xFF0000),
    "POR": ("Portugal", "🇵🇹", 0x006600),
    "NOR": ("Norway", "🇳🇴", 0xBA0C2F),
    "GER": ("Germany", "🇩🇪", 0x000000),
    "NED": ("Netherlands", "🇳🇱", 0xFF6600),
    "ESP": ("Spain", "🇪🇸", 0xAA151B),
    "BEL": ("Belgium", "🇧🇪", 0xFFD90C),
    "SUI": ("Switzerland", "🇨🇭", 0xFF0000),
    "SCO": ("Scotland", "🏴", 0x0065BD),
    "AUT": ("Austria", "🇦🇹", 0xED2939),
    "SWE": ("Sweden", "🇸🇪", 0x006AA7),
    "CZE": ("Czech Republic", "🇨🇿", 0x11457E),
    "TUR": ("Türkiye", "🇹🇷", 0xE30A17),

    # CONCACAF
    "HTI": ("Haiti", "🇭🇹", 0x00209F),
    "PAN": ("Panama", "🇵🇦", 0x005293),
    "CUW": ("Curacao", "🇨🇼", 0x002B7F),

    # PLAYOFF / TAMBAHAN SESUAI GAMBAR
    "BIH": ("Bosnia & Herzegovina", "🇧🇦", 0x002F6C)
}

# =========================================================
# GRADIENT COLORS
# =========================================================

GRADIENTS = {

    "ARG": (0x74ACDF, 0xFFFFFF),
    "BRA": (0x009C3B, 0xFFDF00),
    "FRA": (0x0055A4, 0xEF4135),
    "GER": (0x000000, 0xDD0000),
    "ESP": (0xAA151B, 0xF1BF00),
    "POR": (0x006600, 0xFF0000),
    "ENG": (0xFFFFFF, 0xCF142B),
    "NED": (0xFF6600, 0x21468B),
    "JPN": (0xFFFFFF, 0xBC002D),
    "KOR": (0xFFFFFF, 0xCD2E3A),
}

# =========================================================
# COUNTRY SELECT
# =========================================================

class CountrySelect(discord.ui.Select):

    def __init__(self, cog, countries, placeholder):

        self.cog = cog

        options = []

        for code in countries:

            name, emoji, color = COUNTRIES[code]

            options.append(
                discord.SelectOption(
                    label=name,
                    emoji=emoji,
                    value=code
                )
            )

        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=options,
            custom_id=placeholder
        )

    async def callback(self, interaction):

        try:

            await self.cog.select_team(
                interaction,
                self.values[0]
            )

        except Exception as e:

            print(f"Dropdown Error: {e}")

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    f"❌ Error: {e}",
                    ephemeral=True
                )

# =========================================================
# MEMBER VIEW
# =========================================================

class WorldCupView(discord.ui.View):

    def __init__(self, cog):

        super().__init__(timeout=None)

        self.cog = cog

        country_codes = list(COUNTRIES.keys())

        first = country_codes[:25]
        second = country_codes[25:]

        self.add_item(
            CountrySelect(
                cog,
                first,
                "🌍 Pilih Negara"
            )
        )

        self.add_item(
            CountrySelect(
                cog,
                second,
                "⚽ Negara Lainnya"
            )
        )

    @discord.ui.button(
        label="Hapus Tim",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        custom_id="remove_team_button"
    )
    async def remove_team(
        self,
        interaction,
        button
    ):

        try:

            await self.cog.remove_team(
                interaction
            )

        except Exception as e:

            print(f"Remove Team Error: {e}")

# =========================================================
# STAFF VIEW
# =========================================================

class StaffView(discord.ui.View):

    def __init__(self, cog):

        super().__init__(timeout=None)

        self.cog = cog

    @discord.ui.button(
        label="Kirim Panel Registrasi",
        emoji="📢",
        style=discord.ButtonStyle.success,
        custom_id="send_register_panel"
    )
    async def send_panel(
        self,
        interaction,
        button
    ):

        try:

            register_channel = interaction.guild.get_channel(
                WORLD_CUP_REGISTER_CHANNEL_ID
            )

            if not register_channel:

                return await interaction.response.send_message(
                    f"{WRONGEMOJI} Channel registrasi tidak ditemukan.",
                    ephemeral=True
                )

            embed = discord.Embed(
                description=(
                    f"# {WC26EMOJI} nanZ WC26\n"
                    "Pilih negara favoritmu!\n"
                    f"{ROWEMOJI} Dukung tim nasional favoritmu "
                    "selama World Cup 2026\n"
                    f"{LINEEMOJI}{LINEEMOJI}{LINEEMOJI}{LINEEMOJI}{LINEEMOJI}{LINEEMOJI}{LINEEMOJI}{LINEEMOJI}{LINEEMOJI}{LINEEMOJI}{LINEEMOJI}{LINEEMOJI}{LINEEMOJI}{LINEEMOJI}"
                ),
                color=0x8A2BE2
            )

            embed.set_footer(
                text=(
                    "Hanya supporter yang bisa "
                    "chat di bahas-wc26"
                )
            )

            await register_channel.send(
                embed=embed,
                view=WorldCupView(self.cog)
            )


            await interaction.response.send_message(
                embed = discord.Embed(
                    description= f"{JOINEMOJI} Panel registrasi berhasil dikirim.",
                    color=0x8A2BE2
                ),
                ephemeral=True
            )

        except Exception as e:

            print(f"Send Panel Error: {e}")

    @discord.ui.button(
        label="Hapus Semua Tim",
        emoji="🧹",
        style=discord.ButtonStyle.danger,
        custom_id="remove_all_teams"
    )
    async def remove_all(
        self,
        interaction,
        button
    ):

        try:

            await interaction.response.defer(
                thinking=True,
                ephemeral=True
            )

            guild = interaction.guild

            removed_members = set()

            embed = discord.Embed(
                description=(
                    "🧹 Sedang mereset seluruh supporter World Cup..."
                ),
                color=0xF1C40F
            )

            await interaction.edit_original_response(
                content=None,
                embed=embed
            )

            # =========================================
            # LOOP ROLE WORLD CUP
            # =========================================

            for code, data in COUNTRIES.items():

                name, emoji, color = data

                role = discord.utils.get(
                    guild.roles,
                    name=f"{emoji} {name} Supporter"
                )

                if not role:
                    continue

                # =========================================
                # LOOP MEMBER DI ROLE
                # =========================================

                for member in role.members:

                    removed_members.add(member.id)

                    # REMOVE ROLE
                    try:

                        await member.remove_roles(
                            role,
                            reason="World Cup Reset"
                        )

                    except Exception as e:

                        print(
                            f"Role Remove Error: {e}"
                        )

                    # =========================================
                    # REMOVE NICKNAME TAG
                    # =========================================

                    try:

                        old_name = member.display_name

                        # REMOVE AFK
                        old_name = re.sub(
                            r"\[AFK\]\s*",
                            "",
                            old_name
                        )

                        # REMOVE WORLD CUP
                        old_name = re.sub(
                            r"<[A-Z]{3}>\s*",
                            "",
                            old_name
                        )

                        old_name = old_name.strip()

                        afk_cog = self.cog.bot.get_cog(
                            "AFK"
                        )

                        is_afk = False

                        if afk_cog:

                            is_afk = (
                                member.id in afk_cog.afk_users
                            )

                        final_name = old_name

                        # BALIKIN AFK
                        if is_afk:

                            final_name = (
                                f"[AFK] {final_name}"
                            )

                        final_name = final_name[:32]

                        await member.edit(
                            nick=final_name,
                            reason="World Cup Reset"
                        )

                    except Exception as e:

                        print(
                            f"Nickname Reset Error: {e}"
                        )

                # =========================================
                # DELETE ROLE
                # =========================================

                try:

                    await role.delete(
                        reason="World Cup Reset"
                    )

                except Exception as e:

                    print(
                        f"Role Delete Error: {e}"
                    )

            # =========================================
            # DONE
            # =========================================

            embed = discord.Embed(
                title="🧹 World Cup Reset",
                description=(
                    f"{JOINEMOJI} {len(removed_members)} member dibersihkan\n"
                    f"{JOINEMOJI} Semua role World Cup dihapus"
                ),
                color=0x8A2BE2
            )

            await interaction.edit_original_response(
                content=None,
                embed=embed
            )

        except Exception as e:

            print(
                f"Remove All Error: {e}"
            )

            await interaction.edit_original_response(
                content=f"❌ Error:\n{e}"
            )

# =========================================================
# MAIN COG
# =========================================================

class WorldCup(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    # =========================================================
    # GET TEAM
    # =========================================================

    def get_member_team(self, member):

        for code, data in COUNTRIES.items():

            name, emoji, color = data

            role = discord.utils.get(
                member.guild.roles,
                name=f"{emoji} {name} Supporter"
            )

            if role and role in member.roles:
                return code

        return None

    # =========================================================
    # CREATE ROLE
    # =========================================================

    async def get_or_create_role(
        self,
        guild,
        code
    ):

        name, emoji, color = COUNTRIES[code]

        role_name = (
            f"{emoji} {name} Supporter"
        )

        # =========================================
        # CEK ROLE SUDAH ADA
        # =========================================

        role = discord.utils.get(
            guild.roles,
            name=role_name
        )

        # =========================================
        # KALAU ROLE SUDAH ADA
        # =========================================

        if role:

            try:

                # =========================================
                # FORCE UPDATE GRADIENT
                # =========================================

                primary, secondary = GRADIENTS.get(
                    code,
                    (color, color)
                )

                try:

                    await role.edit(
                        primary_colour=discord.Colour(primary),
                        secondary_colour=discord.Colour(secondary)
                    )

                except:
                    pass

                # =========================================
                # ROLE POSITION
                # =========================================

                member_role = guild.get_role(
                    MEMBER_ROLE_ID
                )

                if member_role:

                    await role.edit(
                        position=member_role.position + 1
                    )

                # =========================================
                # ROLE ICON
                # =========================================

                try:

                    await role.edit(
                        display_icon=emoji
                    )

                except Exception as e:

                    print(
                        f"Role Icon Error: {e}"
                    )

            except Exception as e:

                print(
                    f"Role Position Error: {e}"
                )

            return role

        # =========================================
        # GRADIENT
        # =========================================

        primary, secondary = GRADIENTS.get(
            code,
            (color, color)
        )

        # =========================================
        # CREATE ROLE
        # =========================================

        try:

            role = await guild.create_role(
                name=role_name,
                primary_colour=discord.Colour(primary),
                secondary_colour=discord.Colour(secondary)
            )

        except:

            role = await guild.create_role(
                name=role_name,
                colour=discord.Colour(primary)
            )

        # =========================================
        # PINDAH DI ATAS MEMBER
        # =========================================

        try:


            member_role = guild.get_role(
                MEMBER_ROLE_ID
            )

            if member_role:

                await role.edit(
                    position=member_role.position + 1
                )

        except Exception as e:

            print(
                f"Role Position Error: {e}"
            )

        # =========================================
        # ROLE ICON
        # =========================================

        try:

            await role.edit(
                display_icon=emoji
            )

        except Exception as e:

            print(
                f"Role Icon Error: {e}"
            )

        return role

    # =========================================================
    # REBUILD NICKNAME
    # =========================================================

    async def rebuild_nickname(
        self,
        member,
        remove_team=False,
        team_code=None
    ):

        try:

            current_name = member.display_name

            # REMOVE AFK
            current_name = re.sub(
                r"\[AFK\]\s*",
                "",
                current_name
            )

            # REMOVE COUNTRY
            current_name = re.sub(
                r"<[A-Z]{3}>\s*",
                "",
                current_name
            )

            current_name = current_name.strip()

            # AFK CHECK
            afk_cog = self.bot.get_cog("AFK")

            is_afk = False

            if afk_cog:

                is_afk = (
                    member.id in afk_cog.afk_users
                )

            # TEAM
            team = None

            if not remove_team:

                if team_code:
                    team = team_code

                else:
                    team = self.get_member_team(
                        member
                    )

            # BUILD NAME
            final_name = current_name

            if team:

                final_name = (
                    f"{team}・{final_name}"
                )

            if is_afk:

                final_name = (
                    f"[AFK] {final_name}"
                )

            # Discord limit
            final_name = final_name[:32]

            # UPDATE
            await member.edit(
                nick=final_name,
                reason="World Cup Team Update"
            )

            print(
                f"Nickname Updated: {final_name}"
            )

        except Exception as e:

            print(
                f"Nickname Error: {e}"
            )

    # =========================================================
    # SELECT TEAM
    # =========================================================

    async def select_team(
        self,
        interaction,
        code
    ):

        guild = interaction.guild
        member = interaction.user

        # =========================================
        # DEFER INTERACTION
        # =========================================

        await interaction.response.defer(
            ephemeral=True
        )

        # REMOVE OLD ROLE
        for c, data in COUNTRIES.items():

            name, emoji, color = data

            role = discord.utils.get(
                guild.roles,
                name=f"{emoji} {name} Supporter"
            )

            if role and role in member.roles:

                await member.remove_roles(role)

        # ADD NEW ROLE
        role = await self.get_or_create_role(
            guild,
            code
        )

        await member.add_roles(role)

        # UPDATE NICKNAME
        await self.rebuild_nickname(
            member,
            team_code=code
        )
        # =========================================
        # COUNTRY DATA
        # =========================================

        name, emoji, color = COUNTRIES[code]

        # AURA NOTIFICATION
        wc_channel = guild.get_channel(
            WORLD_CUP_CHAT_ID
        )

        if wc_channel:

            name, emoji, color = COUNTRIES[code]

            embed = discord.Embed(
                description=(
                    f"**{JOINEMOJI} Supporter Baru**: "
                    f"{member.mention} baru saja bergabung ke "
                    f"{emoji} {name} Supporter"
                ),
                color=color
            )

            await wc_channel.send(
                embed=embed
            )

        # RESPONSE
        embed = discord.Embed(
            description=(
                f"{JOINEMOJI} Berhasil bergabung ke supporter "
                f"**{name}** {emoji}"
            ),
            color=color
        )
        await interaction.followup.send(
            embed=embed,
            ephemeral=True
        )

    # =========================================================
    # REMOVE TEAM
    # =========================================================

    async def remove_team(
        self,
        interaction
    ):

        guild = interaction.guild
        member = interaction.user

        for code, data in COUNTRIES.items():

            name, emoji, color = data

            role = discord.utils.get(
                guild.roles,
                name=f"{emoji} {name} Supporter"
            )

            if role and role in member.roles:

                await member.remove_roles(role)

        await self.rebuild_nickname(
            member,
            remove_team=True
        )

        embed = discord.Embed(
            description=(
                f"{WRONGEMOJI} Kamu telah keluar dari supporter World Cup."
            ),
            color=0xED4245
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =========================================================
    # STAFF SETUP
    # =========================================================

    @commands.command()
    @commands.has_permissions(
        administrator=True
    )
    async def worldcupsetup(
        self,
        ctx
    ):

        if ctx.channel.id != STAFF_CONTROL_CHANNEL_ID:
            return

        embed = discord.Embed(
            title="🛠️ Kontrol Staff World Cup",
            description=(
                "Kelola Event World Cup nanZ"
            ),
            color=0x8A2BE2
        )

        await ctx.send(
            embed=embed,
            view=StaffView(self)
        )

    # =========================================================
    # WORLD CUP CHAT
    # =========================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message
    ):

        if message.author.bot:
            return

        if not message.guild:
            return

        if message.channel.id != WORLD_CUP_CHAT_ID:
            return

        member = message.author

        has_team = False

        for code, data in COUNTRIES.items():

            name, emoji, color = data

            role = discord.utils.get(
                message.guild.roles,
                name=f"{emoji} {name} Supporter"
            )

            if role and role in member.roles:
                has_team = True
                break

        if not has_team:

            try:
                await message.delete()
            except:
                pass

            await message.channel.send(
                f"{member.mention} "
                f"kamu harus memilih negara dulu!"
            )

    # =========================================================
    # READY
    # =========================================================

    @commands.Cog.listener()
    async def on_ready(self):

        self.bot.add_view(
            WorldCupView(self)
        )

        self.bot.add_view(
            StaffView(self)
        )

        print("World Cup system berhasil dimuat.")

# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        WorldCup(bot)
    )