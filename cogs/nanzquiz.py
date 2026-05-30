import discord
from discord.ext import commands, tasks
from discord.ui import View, Button, Modal, TextInput
import random
import asyncio
from datetime import datetime

# ==========================================
# CONFIG
# ==========================================

QUIZ_CHANNEL_ID = 1406557882811682891
STAFF_CHANNEL_ID = 1416351665929322637

MOD_ROLE_ID = 1453103644244316343
OSIS_ROLE_ID = 1427276194876751902
PEMBINA_ROLE_ID = 1467360501745844446

# ROLE MURID YANG AKAN DIPING
MURID_ROLE_ID = 1453095603008442510

DEFAULT_REWARD = "75K OwO"
QUIZ_DURATION = 300  # 5 menit

# ==========================================
# PERTANYAAN
# ==========================================

QUESTIONS = [
    {
        "question": "Apa ibu kota Jepang?",
        "answer": "tokyo"
    },
    {
        "question": "Planet terbesar di tata surya?",
        "answer": "jupiter"
    },
    {
        "question": "Hewan tercepat di dunia?",
        "answer": "cheetah"
    },
    {
        "question": "2 + 8 x 2 = ?",
        "answer": "18"
    },
    {
        "question": "Siapa presiden pertama Indonesia?",
        "answer": "soekarno"
    },
    {
        "question": "Bendera Indonesia terdiri dari warna apa saja?",
        "answer": "merah putih"
    },
    {
        "question": "Ibukota Korea Selatan?",
        "answer": "seoul"
    },
    {
        "question": "Nama samudra terbesar di dunia?",
        "answer": "samudra pasifik"
    },
    {
        "question": "Berapa jumlah hari dalam seminggu?",
        "answer": "7"
    },
    {
        "question": "Apa nama satelit alami bumi?",
        "answer": "bulan"
    },
    {
        "question": "Apa hasil dari 10 x 10?",
        "answer": "100"
    },
    {
        "question": "Gunung tertinggi di dunia?",
        "answer": "everest"
    },
    {
        "question": "Apa nama mata uang Jepang?",
        "answer": "yen"
    },
    {
        "question": "Apa nama benua terbesar?",
        "answer": "asia"
    },
    {
        "question": "Apa nama hewan yang dijuluki raja hutan?",
        "answer": "singa"
    },
    {
        "question": "Apa warna daun pada umumnya?",
        "answer": "hijau"
    },
    {
        "question": "Berapa jumlah bulan dalam setahun?",
        "answer": "12"
    },
    {
        "question": "Apa nama planet merah?",
        "answer": "mars"
    },
    {
        "question": "Apa nama lautan antara Afrika dan Australia?",
        "answer": "samudra hindia"
    },
    {
        "question": "Apa nama aplikasi chat warna hijau?",
        "answer": "whatsapp"
    },
    {
        "question": "Apa nama burung lambang Indonesia?",
        "answer": "garuda"
    },
    {
        "question": "Siapa pencipta lampu pijar?",
        "answer": "thomas edison"
    },
    {
        "question": "Apa nama organ untuk berpikir?",
        "answer": "otak"
    },
    {
        "question": "Apa nama ibu kota Indonesia?",
        "answer": "jakarta"
    },
    {
        "question": "Apa nama hewan berkaki delapan?",
        "answer": "laba laba"
    },
    {
        "question": "Apa nama planet tempat kita tinggal?",
        "answer": "bumi"
    },
    {
        "question": "Bahasa nasional Indonesia adalah?",
        "answer": "bahasa indonesia"
    },
    {
        "question": "Apa warna langit pada siang hari?",
        "answer": "biru"
    },
    {
        "question": "Apa nama alat untuk melihat bintang?",
        "answer": "teleskop"
    },
    {
        "question": "Apa nama mamalia terbesar di dunia?",
        "answer": "paus biru"
    }
]

# ==========================================
# MODAL EDIT REWARD
# ==========================================

class RewardModal(Modal, title="🎁 Edit Reward"):

    reward = TextInput(
        label="Jumlah Reward",
        placeholder="100K OwO"
    )

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):

        self.view.reward = self.reward.value

        await interaction.response.send_message(
            f"✅ Reward diubah menjadi {self.reward.value}",
            ephemeral=True
        )

# ==========================================
# MODAL CUSTOM QUESTION
# ==========================================

class QuestionModal(Modal, title="📝 Custom Question"):

    question = TextInput(
        label="Pertanyaan"
    )

    answer = TextInput(
        label="Jawaban"
    )

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):

        self.view.question_data = {
            "question": self.question.value,
            "answer": self.answer.value.lower()
        }

        await interaction.response.send_message(
            "✅ Pertanyaan berhasil diganti.",
            ephemeral=True
        )

# ==========================================
# STAFF VIEW
# ==========================================

class StaffQuizView(View):

    def __init__(self, bot, question_data):
        super().__init__(timeout=600)

        self.bot = bot
        self.question_data = question_data
        self.reward = DEFAULT_REWARD

    @discord.ui.button(
        label="✅ Approve",
        style=discord.ButtonStyle.green
    )
    async def approve(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        if self.bot.quiz_active:
            return await interaction.response.send_message(
                "❌ Masih ada quiz aktif.",
                ephemeral=True
            )

        self.bot.quiz_active = True

        quiz_channel = self.bot.get_channel(
            QUIZ_CHANNEL_ID
        )

        embed = discord.Embed(
            title="nanZ Quiz",
            description=(
                f"❓ **Pertanyaan:**\n"
                f"{self.question_data['question']}\n\n"
                f"**Reward:** "
                f"{self.reward}\n"
                f"**Durasi:** "
                f"5 Menit\n\n"
                f"> Jawab langsung di chat ini."
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="nanZ Server • Quiz System"
        )

        embed.timestamp = discord.utils.utcnow()

        # GIF
        file = discord.File(
            "assets/nanzquiz.gif",
            filename="nanzquiz.gif"
        )

        embed.set_image(
            url="attachment://nanzquiz.gif"
        )

        quiz_message = await quiz_channel.send(
            content=f"📢 **nanZ Quiz dimulai!** <@&{MURID_ROLE_ID}>",
            embed=embed,
            file=file
        )

        self.bot.current_answer = (
            self.question_data['answer']
            .lower()
            .strip()
        )

        self.bot.current_reward = self.reward
        self.bot.current_quiz_message = quiz_message

        await interaction.response.send_message(
            "✅ Quiz berhasil dipublish.",
            ephemeral=True
        )

        await asyncio.sleep(QUIZ_DURATION)

        if self.bot.quiz_active:

            end_embed = discord.Embed(
                title="⏰ Quiz Ended",
                description=(
                    "Belum ada jawaban yang benar kali ini 😔\n\n"
                    "> Quiz berikutnya akan muncul secara random."
                ),
                color=discord.Color.red()
            )

            end_embed.set_footer(
                text="nanZ Server"
            )

            await quiz_channel.send(
                embed=end_embed
            )

            self.bot.quiz_active = False
            self.bot.current_answer = None
            self.bot.current_reward = None
            self.bot.current_quiz_message = None

    @discord.ui.button(
        label="🎁 Edit Reward",
        style=discord.ButtonStyle.blurple
    )
    async def edit_reward(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        await interaction.response.send_modal(
            RewardModal(self)
        )

    @discord.ui.button(
        label="📝 Custom Question",
        style=discord.ButtonStyle.gray
    )
    async def custom_question(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        await interaction.response.send_modal(
            QuestionModal(self)
        )

    @discord.ui.button(
        label="❌ Cancel",
        style=discord.ButtonStyle.red
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        await interaction.response.send_message(
            "❌ Quiz dibatalkan.",
            ephemeral=True
        )

        self.stop()

# ==========================================
# COG
# ==========================================

class NanZQuiz(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        self.bot.quiz_active = False
        self.bot.current_answer = None
        self.bot.current_reward = None
        self.bot.current_quiz_message = None

        self.quiz_scheduler.start()

    # ==========================================
    # RANDOM QUIZ SCHEDULER
    # ==========================================

    @tasks.loop(seconds=30)
    async def quiz_scheduler(self):

        now = datetime.now()
        current_time = now.strftime("%H:%M")

        # JAM QUIZ
        quiz_times = [
            "12:30",
            "17:00",
            "19:30",
            "21:15"
        ]

        # ANTI DOUBLE SEND
        if not hasattr(self, "last_quiz_time"):
            self.last_quiz_time = None

        # JIKA SEKARANG ADALAH WAKTU QUIZ
        if current_time in quiz_times:

            # CEGAH QUIZ TERKIRIM 2X
            if self.last_quiz_time == current_time:
                return

            self.last_quiz_time = current_time

            # JIKA MASIH ADA QUIZ AKTIF
            if self.bot.quiz_active:
                return

            question_data = random.choice(
                QUESTIONS
            )

            staff_channel = self.bot.get_channel(
                STAFF_CHANNEL_ID
            )

            mention_roles = (
                f"<@&{MOD_ROLE_ID}> "
                f"<@&{OSIS_ROLE_ID}> "
                f"<@&{PEMBINA_ROLE_ID}>"
            )

            embed = discord.Embed(
                title="📢 nanZQuiz Reminder",
                description=(
                    "Quiz random siap dimulai.\n\n"
                    f"❓ **Pertanyaan:**\n"
                    f"{question_data['question']}\n\n"
                    f"**Reward Default:** "
                    f"{DEFAULT_REWARD}\n"
                    f"**Durasi:** "
                    f"5 Menit"
                ),
                color=discord.Color.dark_purple()
            )

            embed.set_footer(
                text="nanZ Server • Staff Approval"
            )

            embed.timestamp = discord.utils.utcnow()

            await staff_channel.send(
                content=mention_roles,
                embed=embed,
                view=StaffQuizView(
                    self.bot,
                    question_data
                )
            )

# ==========================================
# START LOOP SETELAH BOT READY
# ==========================================

    @quiz_scheduler.before_loop
    async def before_quiz_scheduler(self):
        await self.bot.wait_until_ready()

    # ==========================================
    # DETEKSI JAWABAN
    # ==========================================

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        if not self.bot.quiz_active:
            return

        if message.channel.id != QUIZ_CHANNEL_ID:
            return

        answer = (
            message.content
            .lower()
            .strip()
        )

        if answer == self.bot.current_answer:

            self.bot.quiz_active = False

            # ==========================================
            # EMBED WINNER
            # ==========================================

            winner_embed = discord.Embed(
                title="nanZQuiz Winner",
                description=(
                    f"Selamat kepada {message.author.mention}!\n\n"
                    f"`Berhasil menjawab dengan benar.`\n\n"
                    f"**Jawaban:** "
                    f"{message.content}\n"
                    f"**Reward:** "
                    f"{self.bot.current_reward}\n\n"
                    f"> Staff akan segera memberikan hadiah kamu."
                ),
                color=discord.Color.gold()
            )

            winner_embed.set_thumbnail(
                url=message.author.display_avatar.url
            )

            winner_embed.set_footer(
                text="nanZ Server • Congratulations"
            )

            winner_embed.timestamp = discord.utils.utcnow()

            await message.channel.send(
                embed=winner_embed
            )

            # ==========================================
            # NOTIF STAFF
            # ==========================================

            staff_channel = self.bot.get_channel(
                STAFF_CHANNEL_ID
            )

            staff_embed = discord.Embed(
                title="Reward Notice",
                description=(
                    f"**Username:** \n"
                    f"{message.author}\n"
                    f"**User ID:** \n"
                    f"{message.author.id}\n"
                    f"**Jawaban:** \n"
                    f"{message.content}\n"
                    f"**Reward:** \n"
                    f"{self.bot.current_reward}\n\n"
                    f"> Silakan transfer hadiah OwO."
                ),
                color=discord.Color.green()
            )

            staff_embed.set_thumbnail(
                url=message.author.display_avatar.url
            )

            staff_embed.set_footer(
                text="nanZ Server • Staff Notice"
            )

            staff_embed.timestamp = discord.utils.utcnow()

            await staff_channel.send(
                embed=staff_embed
            )

            self.bot.current_answer = None
            self.bot.current_reward = None
            self.bot.current_quiz_message = None

    # ==========================================
    # MANUAL QUIZ COMMAND
    # ==========================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def forcequiz(self, ctx):

        question_data = random.choice(
            QUESTIONS
        )

        embed = discord.Embed(
            title="Manual Quiz Trigger",
            description=(
                f"❓ **Pertanyaan:**\n"
                f"{question_data['question']}\n\n"
                f"**Reward:** "
                f"{DEFAULT_REWARD}"
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="nanZ Server"
        )

        await ctx.send(
            embed=embed,
            view=StaffQuizView(
                self.bot,
                question_data
            )
        )

# ==========================================
# SETUP
# ==========================================

async def setup(bot):
    await bot.add_cog(NanZQuiz(bot))