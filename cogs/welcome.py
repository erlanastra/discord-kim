import discord
from discord.ext import commands
import json
import random
import time

# ==========================================
# RANDOM WELCOME STICKERS
# ==========================================
WELCOME_STICKERS = [

    # Wave
    749054660769218631,

    # Tambahkan sticker lain di sini
    819128604311027752,
    749044136589393960,
    816086581509095424,
    816087792291282944,
    781291131828699156,
    754108890559283200,
    819128604311027752,
    783787234091466793
]

# ==========================================
# WAVE BUTTON
# ==========================================
class WaveView(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=None)

        # COOLDOWN STORAGE
        self.cooldowns = {}

    @discord.ui.button(
        label="Sapa murid baru!",
        emoji="👋",
        style=discord.ButtonStyle.secondary
    )
    async def wave_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        try:

            # ================= COOLDOWN =================
            user_id = interaction.user.id
            now = time.time()

            cooldown_time = 10

            if user_id in self.cooldowns:

                last_used = self.cooldowns[user_id]

                if now - last_used < cooldown_time:

                    remaining = int(
                        cooldown_time - (now - last_used)
                    )

                    return await interaction.response.send_message(
                        f"⏳ Tunggu {remaining} detik sebelum wave lagi!",
                        ephemeral=True
                    )

            self.cooldowns[user_id] = now

            # ================= RANDOM STICKER =================
            random_sticker = random.choice(
                WELCOME_STICKERS
            )

            sticker = discord.Object(
                id=random_sticker
            )

            # ================= RANDOM MESSAGE =================
            messages = [

                (
                    f"👋 Welcome {self.member.mention} "
                    f"dari {interaction.user.mention}!"
                ),

                (
                    f"✨ Selamat datang "
                    f"{self.member.mention} "
                    f"di nanZ Server dari "
                    f"{interaction.user.mention}!"
                ),

                (
                    f"🎉 Welcome aboard "
                    f"{self.member.mention}! "
                    f"Dari {interaction.user.mention}"
                ),

                (
                    f"🌸 Haii {self.member.mention}, "
                    f"selamat bergabung yaa! "
                    f"- {interaction.user.mention}"
                ),

                (
                    f"🫶 {interaction.user.mention} "
                    f"mengucapkan welcome untuk "
                    f"{self.member.mention}!"
                ),

                (
                    f"💫 Welcome to nanZ "
                    f"{self.member.mention}! "
                    f"Dari {interaction.user.mention}"
                ),

                (
                    f"🤍 Senang kamu join di sini "
                    f"{self.member.mention}! "
                    f"- {interaction.user.mention}"
                ),

                (
                    f"🎀 Welcomee "
                    f"{self.member.mention} "
                    f"semoga betah yaa! "
                    f"Dari {interaction.user.mention}"
                ),

                (
                    f"🌟 {interaction.user.mention} "
                    f"ikut menyambut "
                    f"{self.member.mention} "
                    f"ke nanZ Server!"
                ),

                (
                    f"🥳 Selamat datang "
                    f"{self.member.mention}! "
                    f"Welcome dari "
                    f"{interaction.user.mention} 💖"
                )
            ]

            # ================= SEND =================
            await interaction.channel.send(

                content=random.choice(messages),

                stickers=[sticker]
            )

            await interaction.response.defer()

        except Exception as e:

            print(
                "Sticker error:",
                e
            )

            await interaction.response.send_message(
                "❌ Gagal mengirim sticker",
                ephemeral=True
            )

# ==========================================
# WELCOME COG
# ==========================================
class Welcome(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        with open("config.json") as f:
            self.config = json.load(f)

        # ROLE MEMBER
        self.MEMBER_ROLE_ID = 1453095603008442510

    # ==========================================
    # AUTO WELCOME SAAT ROLE MASUK
    # ==========================================
    @commands.Cog.listener()
    async def on_member_update(
        self,
        before: discord.Member,
        after: discord.Member
    ):

        channel_id = self.config.get(
            "welcome_channel"
        )

        if not channel_id:
            return

        channel = after.guild.get_channel(
            channel_id
        )

        if not channel:
            return

        before_roles = set(
            role.id for role in before.roles
        )

        after_roles = set(
            role.id for role in after.roles
        )

        # Trigger saat role baru masuk
        if (
            self.MEMBER_ROLE_ID not in before_roles
            and
            self.MEMBER_ROLE_ID in after_roles
        ):

            await self.send_welcome(after)

    # ==========================================
    # TEST COMMAND
    # ==========================================
    @commands.command(name="testwelcome")
    async def test_welcome(
        self,
        ctx,
        member: discord.Member = None
    ):

        member = member or ctx.author

        await self.send_welcome(member)

    # ==========================================
    # SEND WELCOME
    # ==========================================
    async def send_welcome(
        self,
        member: discord.Member
    ):

        channel_id = self.config.get(
            "welcome_channel"
        )

        if not channel_id:

            print(
                "Config welcome_channel tidak ditemukan!"
            )

            return

        channel = self.bot.get_channel(
            channel_id
        )

        if not channel:

            print(
                f"Channel dengan ID "
                f"{channel_id} tidak ditemukan!"
            )

            return

        # ==========================================
        # GIF LOCAL
        # ==========================================
        gif_file = discord.File(
            "assets/verifikasinanz.gif",
            filename="verifikasinanz.gif"
        )

        # ==========================================
        # EMBED
        # ==========================================
        embed = discord.Embed(

            title=(
                f"Selamat datang, "
                f"{member.display_name}! 🎉"
            ),

            description=(

                f"Halo {member.mention}, "
                "senang banget kamu gabung di "
                "**nanZ Server**! 🤍\n\n"

                ">>> Di sini semua member dianggap keluarga, jadi jangan ragu untuk ngobrol, bertanya, atau ikut event bareng.\n\n"

                "Pastikan baca aturan di "
                "<#1406557882811682888> "
                "supaya pengalamanmu nyaman.\n"

                "Ambil role kamu di "
                "<#1408510751039291443>.\n\n"

                "`Sekarang kamu sudah terverifikasi dan bisa menikmati semua channel!`"
            ),

            color=0x00ffcc
        )

        embed.set_footer(
            text="nanZ Server"
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        # GIF bawah embed
        embed.set_image(
            url="attachment://verifikasinanz.gif"
        )

        # ==========================================
        # SEND WELCOME + BUTTON
        # ==========================================
        view = WaveView()
        view.member = member

        await channel.send(
            content=(
                f"➡️ Yay you made it, "
                f"{member.display_name}!"
            ),

            embed=embed,

            view=view,

            file=gif_file
        )

# ==========================================
# SETUP
# ==========================================
async def setup(bot):

    await bot.add_cog(
        Welcome(bot)
    )