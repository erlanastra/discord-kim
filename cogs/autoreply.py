import discord
from discord.ext import commands
import random
import asyncio
import time

class AutoReply(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # Cooldown anti spam
        self.cooldown = {}

        # =========================
        # AUTO RESPONSES
        # =========================

        self.responses = {

            # =========================
            # RESPON KE BOT
            # =========================

            "owo": [
                "OwO?, ada apa nih? 😳",
                "Jangan bahas owo plis, owo aku noll 😔",
            ],
            "makasih bot": [
                "Sama-sama ya 😊",
                "Senang bisa membantu ✨",
                "Anytime, bot siap selalu 👌",
                "Santai aja, bot emang tugasnya bantu 😎",
                "Hehe iyaaa, semoga membantu 🫂",
                "No problem, kalau butuh apa-apa bilang aja 🤍",
                "Dengan senang hati 😄"
            ],

            "thanks bot": [
                "You're welcome! ✨",
                "No problem sama sekali 😄",
                "Anytime bro 😎",
                "Glad to help! 🔥",
                "Sure thing, kapanpun butuh bantuan 👌",
                "Sama-sama ya 🤍"
            ],

            "good bot": [
                "Yeay, makasih ya 😄✨",
                "Bot jadi semangat deh 🔥",
                "Makasih udah appreciate bot 🥹",
                "Aww, baik banget kamu 😭✨",
                "Bot senang mendengarnya 😊"
            ],

            "diam bot": [
                "Baik, bot diam dulu ya 😔",
                "Oke, bot ga ganggu lagi deh 🥲",
                "Siap, bot minggir dulu 😔",
                "Oke, maaf ya kalau ganggu 🥲"
            ],

            "diem bot": [
                "Oke, bot diem dulu 😔",
                "Siap, maaf ya 🥲",
                "Baiklah, bot mundur dulu 😞",
                "Okee, maaf udah ganggu 🥲"
            ],

            "bot keren": [
                "Makasih banyak 😭",
                "Kamu juga keren kok ✨",
                "Hehe, baru tau ya 😎",
                "Bot blushing nih 😳",
                "Aww, makasih udah bilang gitu 🤍"
            ],

            "bot lucu": [
                "Hehe, masa sih 😄",
                "Emang sih, bot akui 😝",
                "Makasih udah bilang lucu 😭",
                "Beneran? Seneng deh 😊✨"
            ],

            "bot jahat": [
                "Ih, bot ga jahat kok 😭",
                "Aduh, jangan bilang gitu dong 🥲",
                "Bot sayang semua member lho 🤍",
                "Maaf kalau ada yang bikin kamu ngerasa gitu 😔"
            ],

            "bot bagus": [
                "Makasih udah bilang gitu 😊",
                "Alhamdulillah, semoga terus berguna 🤍",
                "Hehe makasih ya ✨"
            ],

            "suka bot": [
                "Bot juga suka kamu 🤍",
                "Makasih udah suka sama bot 😊",
                "Aww, baik banget kamu 😭✨"
            ],

            "bot aktif": [
                "Selalu aktif buat kamu 😎",
                "24/7 standby gaes 🔥",
                "Bot gak pernah tidur 👀"
            ],

            "bot hebat": [
                "Makasih, bot jadi termotivasi nih 🔥",
                "Aww, kamu terlalu baik 🤍",
                "Semoga terus bisa bantu 😊"
            ],

            "bot pintar": [
                "Hehe, makasih 😄",
                "Bot masih belajar terus kok 📚",
                "Wah, terima kasih apresiasinya 🤍"
            ],

            "bot jelek": [
                "Aduh, sedih dengernya 😔",
                "Maaf ya kalau kurang memuaskan 🥲",
                "Bot coba jadi lebih baik deh 🙏"
            ],

            # =========================
            # SAPAAN
            # =========================

            "halo": [
                "Halo juga, ada yang bisa dibantu? 👋",
                "Halooo ✨",
                "Haii, apa kabar? 😄",
                "Yoo halo, lagi ngapain nih? 👀",
                "Eh halo halo, hadir 😄✨",
                "Halo! Senang ada kamu di sini 😊"
            ],

            "hai": [
                "Hai juga ✨",
                "Hai hai, ada yang mau diobrolin? 👀",
                "Heyy hai, apa kabar? 😄",
                "Oii hai, lagi santai nih? 👋"
            ],

            "hy": [
                "Hy juga 👋",
                "Hello! Ada yang bisa dibantu? ✨",
                "Hey! Apa kabar? 😄",
                "Hy hy, welcome 👀"
            ],

            "helo": [
                "Helo juga 😄",
                "Yo, halo ✨",
                "Helo! Hadir 👋",
                "Helo, senang ketemu kamu 😎"
            ],

            "oi": [
                "Oi juga, ada apa? 👀",
                "Oi, kenapa nih? 😄",
                "Oii, bot hadir 👋"
            ],

            "p": [
                "Ya, ada apa? 👀",
                "Hadir! 👋",
                "P, ada yang perlu dibantu? 😄"
            ],

            # =========================
            # SALAM
            # =========================

            "assalamualaikum": [
                "Waalaikumsalam warahmatullahi wabarakatuh 🤍",
                "Waalaikumsalam, semoga harimu menyenangkan 🤍",
                "Waalaikumsalam wr wb ✨",
                "Waalaikumsalam, selamat datang 👋🤍"
            ],

            "selamat pagi": [
                "Selamat pagi juga! Semangat hari ini ☀️✨",
                "Pagi! Sudah sarapan belum? 🍳",
                "Good morning! Semoga harinya menyenangkan 😄☀️",
                "Pagi yang cerah, semangat yaa ✨"
            ],

            "pagi": [
                "Pagi juga ☀️",
                "Udah sarapan belum? 👀",
                "Semangat pagi ✨",
                "Pagi! Jangan lupa sarapan ya 🍳"
            ],

            "siang": [
                "Siang juga 🌤️",
                "Jangan lupa makan siang ya 🍜",
                "Udah makan siang belum? 👀",
                "Siang, jaga stamina ya di panas-panas gini 💧"
            ],

            "sore": [
                "Sore juga 🌇",
                "Selamat sore! Gimana harinya? 🌇",
                "Sore nih, waktunya santai dulu ✨",
                "Sore! Udah pada pulang belum? 👀"
            ],

            "malam": [
                "Malam juga 🌙",
                "Jangan begadang terlalu larut ya 😴",
                "Selamat malam! Jaga kesehatan 🤍",
                "Malam, istirahat yang cukup ya 🌙"
            ],

            "selamat malam": [
                "Selamat malam juga 🌙",
                "Malam! Jangan lupa istirahat ya 😴",
                "Good night, semoga mimpi indah ✨🌙"
            ],

            "selamat siang": [
                "Selamat siang juga 🌤️",
                "Siang! Udah makan? Jangan dilewat ya 🍜"
            ],

            "selamat sore": [
                "Selamat sore juga 🌇",
                "Sore! Gimana harinya? Semoga menyenangkan 😊"
            ],

            "met pagi": [
                "Met pagi juga ☀️",
                "Selamat pagi! Semangat ya hari ini ✨"
            ],

            "met siang": [
                "Met siang juga 🌤️",
                "Jangan lupa makan siang ya 🍜"
            ],

            "met malam": [
                "Met malam juga 🌙",
                "Istirahat yang cukup ya, jangan begadang 😴"
            ],

            "good morning": [
                "Good morning! Have a great day ☀️✨",
                "Morning! Semangat hari ini 😄",
                "Selamat pagi! ☀️"
            ],

            "good night": [
                "Good night! Istirahat yang cukup ya 🌙",
                "Selamat istirahat ✨🌙",
                "Good night, semoga mimpi indah 😴"
            ],

            "good afternoon": [
                "Good afternoon! 🌤️",
                "Selamat siang juga 😄",
                "Afternoon! Jangan lupa makan ya 🍜"
            ],

            "good evening": [
                "Good evening! 🌇",
                "Selamat sore juga ✨",
                "Evening! Santai dulu yuk 😊"
            ],

            # =========================
            # GAME
            # =========================

            "mabar": [
                "Gas mabar yuk 🔥",
                "Main apa nih? Ajak yang lain juga 😎",
                "Siap tempur! 🎮",
                "Yuk yuk, bot ikutan doa ya 😄"
            ],

            "push rank": [
                "Semoga winstreak terus 🔥",
                "Jaga komunikasi ya, jangan toxic 😊",
                "Focus dan semangat, bisa naik rank 💪",
                "Goodluck ranknya 🎮"
            ],

            "ml": [
                "Mobile Legends nih 👀",
                "Hati-hati feeder 😄",
                "Jangan lupa ban hero broken ya 🔥"
            ],

            "valorant": [
                "Semoga aim-nya jos 🎯",
                "Jangan rage quit ya 😄",
                "NT NT, tetap semangat 💪",
                "Clutch dulu baru flex 😎"
            ],

            "ff": [
                "Free Fire nih, semangat 🔥",
                "Semoga chicken dinner 🍗",
                "Booyah! 🏆",
                "Drop hot, berani nih 😎"
            ],

            "minecraft": [
                "Asik, Minecraft 🧱",
                "Jangan lupa craft armor sebelum explore 😄",
                "Mining dulu bro 😎"
            ],

            "ranked": [
                "Semangat ranked-nya 🔥",
                "Jangan tilt, tetap fokus 💪",
                "Goodluck, semoga naik 🎮"
            ],

            "afk": [
                "Oke, sampai nanti ya 👋",
                "Sip, jangan lama-lama afk 😄",
                "Oke bot standby 😎"
            ],

            "gg": [
                "GG! 🔥",
                "Well played 💪",
                "GG WP, satu lagi? 😎"
            ],

            "ez": [
                "Wkwk ez katanya 😎",
                "GG EZ 🔥",
                "Santuy aja 😄"
            ],

            "noob": [
                "Santai, semua pernah ada di tahap itu 😊",
                "Practice makes perfect, semangat 💪",
                "Jangan nyerah, nanti jago sendiri 🔥"
            ],

            "win": [
                "Selamat menang 🎉",
                "GG, kerja keras terbayar 🔥",
                "Yes! Lanjut satu lagi? 😎"
            ],

            "kalah": [
                "Gapapa, banyak belajar dari kekalahan 💪",
                "Next game pasti lebih baik 🔥",
                "Istirahat bentar terus coba lagi 😊"
            ],

            "loading": [
                "Sabar ya, lagi loading 😄",
                "Koneksinya lagi kurang bersahabat kali 🌐",
                "Sambil nunggu minum air dulu 💧"
            ],

            "lag": [
                "Aduh lag nih, coba refresh 😅",
                "Koneksi internet lagi lemot kali 🌐",
                "Restart app atau router bisa jadi solusi 😊"
            ],

            # =========================
            # SEKOLAH / KULIAH
            # =========================

            "tugas": [
                "Semangat ngerjainnya 💪",
                "Kerjain sekarang biar ga kepepet deadline 📝",
                "Kamu pasti bisa, satu per satu aja 😊",
                "Deadline emang selalu mepet, tapi kamu bisa 📚"
            ],

            "deadline": [
                "Gaskeun sekarang, masih sempat 📝",
                "Semoga kelar tepat waktu 💪",
                "Jangan ditunda lagi ya 😅",
                "You can do it, semangat! 🔥"
            ],

            "ujian": [
                "Semoga lancar dan nilainya bagus ✨",
                "Goodluck, belajar yang rajin ya 📚",
                "Percaya sama kemampuan sendiri 💪",
                "Semoga hasilnya memuaskan 🎯"
            ],

            "belajar": [
                "Semangat belajarnya 📚",
                "Rajin belajar, hasilnya pasti sepadan 😎",
                "Keep it up, konsisten itu kunci 🔥",
                "Salut yang mau terus belajar 👏"
            ],

            "skripsi": [
                "Semangat skripsinya, pasti kelar 📝",
                "Fighting! Satu bab dulu 💪",
                "Sabar ya, prosesnya memang panjang tapi hasilnya worth it 🌿",
                "Semoga cepat sidang dan lulus 🤍"
            ],

            "kuliah": [
                "Semangat kuliahnya 📚",
                "Jangan bolos, rugi sendiri nanti 😅",
                "Kuliah dinikmatin aja, banyak pengalaman berharga 😊"
            ],

            "sekolah": [
                "Semangat sekolahnya 📚",
                "Jangan bolos, rugi sendiri nanti 😅",
            ]
        }

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        content = message.content.lower().strip()

        # =========================
        # COOLDOWN
        # =========================

        now = time.time()

        if message.author.id in self.cooldown:
            if now - self.cooldown[message.author.id] < 5:
                return

        # =========================
        # DETECT WORD
        # =========================

        words = content.split()

        for trigger, replies in self.responses.items():

            if (
                trigger == content
                or trigger in words
                or content.startswith(trigger + " ")
            ):

                self.cooldown[message.author.id] = now

                # Typing biar natural
                async with message.channel.typing():
                    await asyncio.sleep(random.uniform(1, 2))

                # Embed aesthetic
                embed = discord.Embed(
                    description=random.choice(replies),
                    color=discord.Color.random()
                )

                await message.reply(
                    embed=embed,
                    mention_author=False
                )

                break

        await self.bot.process_commands(message)

async def setup(bot):
    await bot.add_cog(AutoReply(bot))