import discord
from discord.ext import commands
import random
import asyncio

class AutoReply(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # =============================================
        # EMOJI SERVER — format: <:nama:ID> atau <a:nama:ID> kalau animated
        # Ganti nama dan ID sesuai emoji di server kamu
        # Cara dapat ID: Developer Mode → klik kanan emoji → Copy Emoji ID
        # =============================================
        self.sticker_ids = [
            "<:22cathink:1493158293940473856>",
            "<:1joseph_kenned:1493144793956618240>",
            "<:kimthinking:1507084030288465960>",
            "<:jkyujibruh:1493137332906360923>",
            "<:kimpose:1507082661976604833>",
            "<:22starecatto:1493145059636543518>",
        ]

        # =============================================
        # KATA-KATA TERLARANG
        # =============================================
        self.badwords = [
            # anjing variants
            "anjim", "anjink", "anjing", "anj", "anjng", "ajg", "ajng", "ajang",
            "anjinh", "anding", "andeng", "4nj1n9", "anjin9", "4njing", "anj1ng",
            "anj1n9",
            # kontol variants
            "kontol", "kntl", "kntol", "kontil", "kintil",
            # babi variants
            "babi", "bbi", "b4b1",
            # alat kelamin variants
            "momok", "memek", "mmek", "mmok", "meki", "puki", "cukimay", "kimak",
            "pukimak", "mmk", "titid", "titit",
            # setan/biadab
            "setan", "setang", "biadab", "firaun",
            # goblok/bodoh variants
            "goblok", "gblok", "govlok", "goblock", "goblog", "gblog", "goblough",
            "blog", "blough", "bego", "bgo", "bodo", "bdo", "bdoh", "bodoh",
            "t0l0l", "b0d0h", "gblk",
            # monyet variants
            "monyet", "monket", "monkey", "mnyet", "nyet",
            # sinting
            "sinting",
            # english swear
            "shit", "fuck", "bitch", "stupid", "damn", "fak", "syit",
            # ngentot variants
            "ngentot", "ngentod", "ngntot", "ngntod", "ngentoy", "nentoy", "nentot",
            # tolol variants
            "tll", "yatim",
        ]

        # Pesan warning yang akan dipilih secara random
        self.warning_messages = [
            " **Hei, jaga kata-katanya ya!** Kita semua di sini untuk saling menghargai 🙏",
            " **Ups! Kata itu kurang pantas.** Yuk gunakan bahasa yang lebih baik 😊",
            " **Bahasa dulu ya!** Server ini punya aturan untuk saling menghormati 🤍",
            " **Kata-katanya dijaga ya!** Kita jaga suasana server tetap nyaman untuk semua 😊",
            " **Hei!** Tolong gunakan bahasa yang sopan di server ini ya 🙏",
            " **Ingat ya**, setiap kata yang kita ucapkan mencerminkan diri kita. Yuk lebih baik 🌟",
            " **Bahasa kamu kurang oke tuh!** Kita sepakat untuk saling menghargai di sini 💬",
        ]

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

            "siap bot": [
                "ingat yaa, bot selalu mantau 😎",
                "aman ajaa 😅"
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
            "morning oll": [
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
            "met sore": [
                "Met sore juga 🌇",
                "Selamat sore ✨"
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

    def contains_badword(self, content: str) -> bool:
        words = content.lower().split()
        content_lower = content.lower()
        for bw in self.badwords:
            if bw in words or bw == content_lower:
                return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        ctx = await self.bot.get_context(message)

        # Ignore command bot
        if ctx.valid:
            return

        content = message.content.lower().strip()
        # =============================================
        # FITUR 1: WARNING KATA KASAR
        # =============================================
        if self.contains_badword(content):
            warning_text = random.choice(self.warning_messages)
            embed = discord.Embed(
                description=f"{message.author.mention} {warning_text}",
                color=discord.Color.red()
            )

            async with message.channel.typing():
                await asyncio.sleep(random.uniform(0.5, 1))

            await message.channel.send(embed=embed)
            return

        # =============================================
        # FITUR 2: AUTO REPLY RESPONSES
        # FITUR 2: AUTO REPLY RESPONSES
        # Cek keyword dulu — kalau cocok, balas teks seperti biasa.
        # Kalau ini adalah reply ke bot tapi tidak ada keyword → kirim stiker.
        # =============================================
        words = content.split()

        # FIX: fetch manual kalau resolved belum ke-cache Discord
        is_reply_to_bot = False
        if message.reference and message.reference.message_id:
            try:
                ref_msg = (
                    message.reference.resolved
                    or await message.channel.fetch_message(message.reference.message_id)
                )
                if isinstance(ref_msg, discord.Message) and ref_msg.author.id == self.bot.user.id:
                    is_reply_to_bot = True
            except (discord.NotFound, discord.HTTPException):
                pass

        keyword_matched = False

        for trigger, replies in self.responses.items():

            if (
                trigger == content
                or content.startswith(trigger + " ")
            ):
                keyword_matched = True
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

        # =============================================
        # FITUR 3: STIKER RANDOM — hanya kalau reply bot
        #          dan tidak ada keyword yang cocok
        # =============================================
        if is_reply_to_bot and not keyword_matched and self.sticker_ids:
            emoji = random.choice(self.sticker_ids)
            async with message.channel.typing():
                await asyncio.sleep(random.uniform(0.5, 1.5))
            await message.channel.send(emoji)

        await self.bot.process_commands(message)


async def setup(bot):
    await bot.add_cog(AutoReply(bot))