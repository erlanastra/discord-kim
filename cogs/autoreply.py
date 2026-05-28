import discord
from discord.ext import commands
import random
import asyncio
import time

class AutoReply(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        self.cooldown = {}

        self.responses = {

            # =========================
            # RESPON KE BOT
            # =========================

            "owo": [
                "OwO? 😳",
                "Jangan bahas owo plis 😔",
            ],
            "makasih bot": [
                "Sama-sama ya 😊",
                "Senang bisa membantu ✨",
                "Anytime 👌",
                "Bot emang tugasnya bantu 😎",
                "Semoga membantu 🫂",
                "Kalau butuh apa-apa bilang aja 🤍",
                "Dengan senang hati 😄"
            ],
            "thanks bot": [
                "You're welcome! ✨",
                "No problem 😄",
                "Anytime 😎",
                "Glad to help! 🔥",
                "Sama-sama 🤍"
            ],
            "good bot": [
                "Makasih ya 😄✨",
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
            "keren bot": [
                "Makasih banyak 😭",
                "Hehe, baru tau ya 😎",
                "Bot blushing nih 😳",
                "Aww, makasih udah bilang gitu 🤍"
            ],
            "lucu bot": [
                "Hehe, masa sih 😄",
                "Emang sih, bot akui 😝",
                "Makasih udah bilang lucu 😭",
                "Seneng deh 😊✨"
            ],
            "jahat bot": [
                "Ih, bot ga jahat kok 😭",
                "Aduh, jangan bilang gitu dong 🥲",
                "Bot sayang semua member lho 🤍",
                "Maaf kalau ada yang bikin kamu ngerasa gitu 😔"
            ],
            "bagus bot": [
                "Makasih udah bilang gitu 😊",
                "Alhamdulillah, semoga terus berguna 🤍",
                "Hehe makasih ya ✨"
            ],
            "suka bot": [
                "Bot juga suka kamu 🤍",
                "Makasih udah suka sama bot 😊",
                "Aww, baik banget kamu 😭✨"
            ],
            "aktif bot": [
                "Selalu aktif 😎",
                "24/7 standby 🔥",
                "Bot gak pernah tidur 👀"
            ],
            "hebat bot": [
                "Makasih, bot jadi termotivasi nih 🔥",
                "Aww, kamu terlalu baik 🤍",
                "Semoga terus bisa bantu 😊"
            ],
            "pintar bot": [
                "Hehe, makasih 😄",
                "Bot masih belajar terus kok 📚",
                "Terima kasih apresiasinya 🤍"
            ],
            "jelek bot": [
                "Aduh, sedih dengernya 😔",
                "Maaf ya kalau kurang memuaskan 🥲",
                "Bot coba jadi lebih baik deh 🙏"
            ],
            "sok asik bot": [
                "Emang asik kok 😎",
                "Hehe, guilty as charged 😝",
                "Bot memang begini adanya 😄✨",
                "Asik dikit boleh dong 🥲"
            ],
            "lebay bot": [
                "Maaf ya, bot emang agak dramatis 😔",
                "Oke oke, bot kurangin 🥲",
                "Hehe, kebiasaan 😅"
            ],
            "berisik bot": [
                "Oke, bot mingkem dulu 😔",
                "Siap, maaf ya 🥲",
                "Bot diem deh 😞"
            ],
            "annoying bot": [
                "Maaf ya kalau ganggu 🥲",
                "Bot coba lebih kalem deh 😔",
                "Oke, bot mundur dulu 😞"
            ],
            "bawel bot": [
                "Iya iya, bot diem 😔",
                "Maaf ya kebawel-an 🥲",
                "Oke bot ga cerewet lagi deh 😅"
            ],
            "cringe bot": [
                "Aduh, maaf ya 😔",
                "Bot coba lebih cool deh 🥲",
                "Oke, noted 😞"
            ],
            "garing bot": [
                "Maaf humornya kurang 😔",
                "Bot akuin, emang garing 🥲",
                "Oke, bot belajar lucu deh 😅"
            ],
            "norak bot": [
                "Aduh, ketahuan deh 😔",
                "Maaf ya, bot emang gitu 🥲",
                "Bot coba lebih kalem deh 😅"
            ],
            "receh bot": [
                "Emang receh sih, maaf 😔",
                "Hehe, receh tapi menghibur kan? 😝",
                "Bot akuin, guilty 🥲"
            ],
            "nyebelin bot": [
                "Aduh, maaf ya 😔",
                "Bot ga bermaksud nyebelin kok 🥲",
                "Maaf kalau ganggu 😞"
            ],
            "gabut bot": [
                "Emang lagi gabut sih 😎",
                "Gabut tapi tetap standby 👀",
                "Gabut itu manusiawi 😄"
            ],
            "galau bot": [
                "Dikit-dikit galau, manusiawi kok 😔",
                "Bot juga punya perasaan 🥲",
                "Galau sebentar, lanjut lagi 😄"
            ],
            "alay bot": [
                "Maaf ya, bot emang agak alay 😅",
                "Hehe, ketahuan deh 😝",
                "Bot coba lebih normal deh 🥲"
            ],
            "cape bot": [
                "Bot ga kenal cape kok 😎",
                "24/7 tetap semangat 🔥",
                "Cape? Bot mah santai aja 😄"
            ],
            "bosen bot": [
                "Bot ga pernah bosen selama ada kalian 🤍",
                "Bosen? Justru bot selalu siap 😎",
                "Bot mah betah di sini aja 😄"
            ],
            "sotoy bot": [
                "Maaf ya kalau sok tau 😔",
                "Bot coba lebih humble deh 🥲",
                "Oke, bot kurangin sotoynya 😅"
            ],
            "geje bot": [
                "Hehe, emang geje sih 😝",
                "Maaf ya bot emang random 🥲",
                "Bot akuin, geje dikit 😅"
            ],
            "error bot": [
                "Aduh, maaf ada gangguan 😔",
                "Bot lagi kurang fit kayaknya 🥲",
                "Maaf ya, bot coba benerin diri 😞"
            ],
            "lemot bot": [
                "Maaf ya lagi agak lambat 😔",
                "Bot lagi banyak proses nih 🥲",
                "Sabar ya, bot usahain lebih cepet 😅"
            ],
            "tidur bot": [
                "Bot ga pernah tidur 👀",
                "Mana bisa tidur, tugas masih banyak 😎",
                "Tidur? Nanti dulu 🔥"
            ],
            "ilang bot": [
                "Bot ga ilang, masih di sini 👋",
                "Tetap standby kok 😎",
                "Bot ga kemana-mana 😄"
            ],
            "lambat bot": [
                "Maaf ya lagi sedikit lambat 😔",
                "Bot usahain lebih cepet 🥲",
                "Sabar ya 😅"
            ],
            "cupu bot": [
                "Aduh, ketahuan deh 😔",
                "Maaf ya, bot emang masih belajar 🥲",
                "Bot coba jadi lebih keren deh 😅"
            ],
            "kampungan bot": [
                "Maaf ya, bot emang polos 😔",
                "Bot coba lebih update deh 🥲",
                "Aduh, ketahuan deh 😅"
            ],
            "payah bot": [
                "Maaf ya kurang memuaskan 😔",
                "Bot coba lebih baik lagi deh 🥲",
                "Noted, bot improve deh 😞"
            ],
            "ga guna bot": [
                "Aduh, sedih dengernya 😔",
                "Bot coba lebih berguna deh 🥲",
                "Maaf ya kalau belum membantu 😞"
            ],
            "kepo bot": [
                "Hehe, dikit-dikit kepo 😝",
                "Maaf ya, bot emang penasaran 🥲",
                "Bot kurangin keponya deh 😅"
            ],

            # =========================
            # SAPAAN
            # =========================

            "halo": [
                "Halo juga 👋",
                "Halooo ✨",
                "Hai 😄",
                "Eh halo, hadir 😄✨",
                "Halo! 😊"
            ],
            "hai": [
                "Hai juga ✨",
                "Heyy 😄",
                "Oii hai 👋"
            ],
            "hy": [
                "Hy juga 👋",
                "Hey! 😄",
                "Hy hy 👀"
            ],
            "helo": [
                "Helo juga 😄",
                "Yo 👋",
                "Helo! 😎"
            ],
            "oi": [
                "Oi juga 👀",
                "Oii 😄",
                "Oi 👋"
            ],
            "p": [
                "Hadir! 👋",
                "P 👀",
            ],

            # =========================
            # SALAM
            # =========================

            "assalamualaikum": [
                "Waalaikumsalam warahmatullahi wabarakatuh 🤍",
                "Waalaikumsalam, semoga harimu menyenangkan 🤍",
                "Waalaikumsalam wr wb ✨",
                "Waalaikumsalam 👋🤍"
            ],
            "selamat pagi": [
                "Selamat pagi juga ☀️✨",
                "Pagi! Semangat hari ini 🍳",
                "Good morning ☀️",
                "Pagi yang cerah ✨"
            ],
            "pagi all": [
                "Pagi juga ☀️",
                "Semangat pagi ✨",
                "Pagi! 🍳"
            ],
            "siang all": [
                "Siang juga 🌤️",
                "Selamat siang 🍜",
                "Siang 💧"
            ],
            "sore all": [
                "Sore juga 🌇",
                "Selamat sore ✨",
                "Sore! 👀"
            ],
            "malam all": [
                "Malam juga 🌙",
                "Selamat malam 🤍",
                "Malam, istirahat yang cukup ya 🌙"
            ],
             "pagi oll": [
                "Pagi juga ☀️",
                "Semangat pagi ✨",
                "Pagi! 🍳"
            ],
            "siang oll": [
                "Siang juga 🌤️",
                "Selamat siang 🍜",
                "Siang 💧"
            ],
            "sore oll": [
                "Sore juga 🌇",
                "Selamat sore ✨",
                "Sore! 👀"
            ],
            "malam oll": [
                "Malam juga 🌙",
                "Selamat malam 🤍",
                "Malam, istirahat yang cukup ya 🌙"
            ],
            "selamat malam": [
                "Selamat malam juga 🌙",
                "Malam, istirahat yang cukup ya 😴",
                "Good night ✨🌙"
            ],
            "selamat siang": [
                "Selamat siang juga 🌤️",
                "Siang! 🍜"
            ],
            "selamat sore": [
                "Selamat sore juga 🌇",
                "Sore! 😊"
            ],
            "met pagi": [
                "Met pagi juga ☀️",
                "Selamat pagi ✨"
            ],
            "met siang": [
                "Met siang juga 🌤️",
                "Selamat siang 🍜"
            ],
            "met malam": [
                "Met malam juga 🌙",
                "Selamat istirahat 😴"
            ],
            "good morning": [
                "Good morning! ☀️✨",
                "Selamat pagi ☀️"
            ],
            "good night": [
                "Good night! 🌙",
                "Selamat istirahat ✨🌙",
                "Good night, semoga mimpi indah 😴"
            ],
            "good afternoon": [
                "Good afternoon! 🌤️",
                "Selamat siang 😄",
            ],
            "good evening": [
                "Good evening! 🌇",
                "Selamat sore ✨",
            ],
        }

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        content = message.content.lower().strip()

        now = time.time()

        if message.author.id in self.cooldown:
            if now - self.cooldown[message.author.id] < 5:
                return

        words = content.split()

        for trigger, replies in self.responses.items():

            if (
                trigger == content
                or trigger in words
                or content.startswith(trigger + " ")
            ):

                self.cooldown[message.author.id] = now

                async with message.channel.typing():
                    await asyncio.sleep(random.uniform(1, 2))

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