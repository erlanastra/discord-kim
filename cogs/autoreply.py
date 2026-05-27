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

            "woi": [
                "Iya iya, ada apa? 😄",
                "Woi balik, kenapa? 👀",
                "Apa yang bisa dibantu? 😎"
            ],

            "p": [
                "Ya, ada apa? 👀",
                "Hadir! 👋",
                "P, ada yang perlu dibantu? 😄"
            ],

            "bang": [
                "Iya bang, ada apa? 😎",
                "Siap bang, ada yang bisa dibantu? 🔥",
                "Bang hadir 👋"
            ],

            "bro": [
                "Yo bro, apa kabar? 😎",
                "Ada apa bro? 👀",
                "Siap bro, butuh apa? 💪",
                "Bro hadir 😄"
            ],

            "kak": [
                "Iya kak, ada yang bisa dibantu? ✨",
                "Halo kak! 👋",
                "Kak hadir, mau tanya apa? 😊",
                "Siap kak 😄"
            ],

            "min": [
                "Iya, ada apa? 👀",
                "Min hadir 😎",
                "Ada yang mau ditanyain? 😊",
                "Siap, ada yang bisa dibantu? 🔥"
            ],

            "guys": [
                "Yoo guys, ada apa nih? 😎",
                "Ada apa guys? 👀",
                "Halo semua 👋"
            ],

            "bossku": [
                "Siap bos, ada perintah? 😎",
                "Ada apa bos? 👀",
                "Siap melayani bos 🔥"
            ],

            "boss": [
                "Siap boss 💪",
                "Yes boss, ada apa? 😎",
                "Apa yang bisa dibantu boss? 🔥"
            ],

            "sob": [
                "Yo sob, ada apa? 😎",
                "Halo sob 👋",
                "Sob hadir, kenapa? 😄"
            ],

            "gaes": [
                "Yoo gaes 😎",
                "Halo semua 👋",
                "Ada apa gaes? 👀"
            ],

            "cuy": [
                "Iya cuy, ada apa? 😄",
                "Cuy hadir 👋",
                "Kenapa cuy? 👀"
            ],

            "sis": [
                "Halo sis! 👋",
                "Iya sis, ada apa? ✨",
                "Sis hadir 😊"
            ],

            "dek": [
                "Iya dek, ada apa? 😊",
                "Halo dek! 👋",
                "Ada yang bisa dibantu, dek? ✨"
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
            # RANDOM & NGOBROL
            # =========================

            "gabut": [
                "Gabut? Sini ngobrol dulu 😄",
                "Mau main game? 🎮",
                "Coba explore server ini biar ga bosen 😎",
                "Gabut itu tanda pikiranmu lagi butuh stimulasi baru 👀",
                "Nonton YouTube atau baca artikel seru kali 📺"
            ],

            "bosen": [
                "Cari hiburan yang seru yuk 😊",
                "Mau main game bareng? 🎮",
                "Coba belajar skill baru biar produktif 📚",
                "Nonton film atau series mungkin? 🎬",
                "Jalan-jalan bentar bisa ngilangin bosen lho 🚶"
            ],

            "ngantuk": [
                "Tidur aja dulu kalau emang ngantuk 😴",
                "Minum kopi atau teh hangat dulu ☕",
                "Cuci muka bentar biar melek lagi 💧",
                "Istirahat 15 menit aja cukup lho 😴"
            ],

            "capek": [
                "Istirahat dulu, kamu udah kerja keras 🫂",
                "Healing bentar, kamu layak dapat itu 🌿",
                "Semua orang butuh jeda, gapapa istirahat 🤍",
                "Rebahan dulu, nanti lanjut lagi 😴",
                "Minum air putih dulu ya 💧"
            ],

            "stress": [
                "Tarik napas dulu, semua pasti ada jalan keluarnya 🌿",
                "Tenang, kamu lebih kuat dari yang kamu kira 🤍",
                "Ceritain dong, kadang ngeluarin perasaan itu udah lega 😊",
                "Istirahat sebentar dari layar, jalan-jalan bentar 🌿",
                "Semangat ya, kamu pasti bisa lewatin ini 💙"
            ],

            "sedih": [
                "Aduh, kenapa sedih? Ceritain dong 🫂",
                "Gapapa sedih, itu manusiawi 🤍",
                "Bot dengerin kok, mau cerita? 😊",
                "Semua akan baik-baik aja, percaya deh 🌿",
                "Ada yang bisa bot bantu? 💙"
            ],

            "nangis": [
                "Aduh, kenapa nangis? 🥺",
                "Gapapa nangis, lebih lega kok 🤍",
                "Bot dengerin kalau mau cerita 🫂",
                "Semoga segera membaik ya 💙"
            ],

            "overthinking": [
                "Jangan terlalu dipikirin, santai aja dulu 😊",
                "Tarik napas, fokus satu hal dulu 🌿",
                "Satu langkah kecil aja dulu, gak harus langsung sempurna 👣",
                "Semua bakal baik-baik aja kok 🫂"
            ],

            "apa kabar": [
                "Alhamdulillah baik, kamu gimana? 😄",
                "Baik-baik aja, makasih udah nanya 😊",
                "Bot sehat selalu, kamu sendiri gimana nih? 👀"
            ],

            "lagi apa": [
                "Lagi jagain server ini 😎",
                "Nungguin ada yang mau ngobrol 😄",
                "Standby aja nih, ada yang bisa dibantu? 👀"
            ],

            "gapapa": [
                "Iya, gapapa 😊",
                "Santai aja, semua akan baik-baik aja 🤍",
                "Tenang, gapapa kok 👌"
            ],

            "bisa minta tolong": [
                "Tentu! Minta tolong apa? 😊",
                "Boleh, bot siap bantu 🔥",
                "Dengan senang hati, ada apa? ✨"
            ],

            "mau tanya": [
                "Boleh, tanya aja 😊",
                "Silakan, bot dengerin 👀",
                "Yuk tanya, bot siap jawab ✨"
            ],

            "tolong": [
                "Ada yang bisa bot bantu? 😊",
                "Siap, mau tolong apa nih? 👀",
                "Bot hadir, ada apa? 🤍"
            ],

            "bantuin": [
                "Siap, mau dibantu apa? 😊",
                "Bot siap bantu, ceritain dulu 👀",
                "Tentu, ada apa nih? ✨"
            ],

            "cerita dong": [
                "Yuk cerita, bot dengerin 😊",
                "Ayo, bot siap mendengarkan 🤍",
                "Ceritain aja, santai 😄"
            ],

            "curhat": [
                "Yuk curhat, bot dengerin kok 🤍",
                "Boleh, ceritain aja 😊",
                "Santai, bot siap mendengarkan 🫂"
            ],

            "iseng": [
                "Hehe, iseng boleh aja 😄",
                "Lagi iseng? Mending ngobrol sini 👀",
                "Iseng tanda semangat 😎"
            ],

            "bete": [
                "Aduh kenapa bete? 😊",
                "Ceritain, mungkin bot bisa bantu 🤍",
                "Semoga mood-nya segera membaik ya 🌿"
            ],

            "kesal": [
                "Aduh, kenapa kesal? Ceritain dong 😊",
                "Tarik napas dulu ya 🌿",
                "Semoga segera reda ya 🤍"
            ],

            "marah": [
                "Eits, tenang dulu 😊",
                "Tarik napas, jangan terbawa emosi 🌿",
                "Semoga segera tenang ya 🤍"
            ],

            "senang": [
                "Wah ikutan senang nih 😄✨",
                "Alhamdulillah, semoga terus senang 🤍",
                "Yey, senang deh dengernya 🎉"
            ],

            "bahagia": [
                "Alhamdulillah, semoga terus bahagia 🤍",
                "Senang dengernya 😄✨",
                "Semoga kebahagiaannya terus berlanjut 🌟"
            ],

            "excited": [
                "Ikutan excited nih 🔥😄",
                "Wah, ada apa nih? Ceritain dong 👀",
                "Semangat, hal baik lagi nunggu 🌟"
            ],

            "deg degan": [
                "Hehe, kenapa deg-degan? 👀",
                "Semangat, kamu pasti bisa 💪",
                "Bismillah, semoga lancar ya 🤍"
            ],

            "nervous": [
                "Tenang, kamu udah siap kok 💙",
                "Tarik napas, semua pasti baik-baik aja 🌿",
                "You got this! 🔥"
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
                "Rajin belajar ya, buat masa depan 😊",
                "Masa sekolah itu seru, nikmatin 😄"
            ],

            "libur": [
                "Yeay libur 🎉",
                "Mau ngapain nih liburnya? 😄",
                "Istirahat yang cukup, recharge tenaga 🌿"
            ],

            "les": [
                "Semangat lesnya, ilmunya bermanfaat 📖",
                "Rajin les pasti lebih siap 😊",
                "Mantap, terus tingkatkan kemampuan 🎯"
            ],

            "pr": [
                "Kerjain dulu PR-nya ya 📝",
                "Semangat, pasti bisa kelar 💪",
                "Selesaikan PR dulu biar tenang 😊"
            ],

            "ulangan": [
                "Semangat ulangannya 📚",
                "Belajar dulu biar siap 😊",
                "Goodluck, semoga nilainya bagus 🎯"
            ],

            "nilai": [
                "Semoga nilainya bagus ya 🎯",
                "Kerja keras pasti terbayar 💪",
                "Apapun hasilnya, tetap semangat belajar 📚"
            ],

            "wisuda": [
                "Selamat wisuda 🎓🎉",
                "Congrats, perjuangan panjang terbayar 🥳",
                "Semoga sukses di langkah berikutnya 🤍"
            ],

            "ospek": [
                "Semangat ospeknya 💪",
                "Nikmatin prosesnya, seru kok 😊",
                "Jaga kesehatan dan tetap semangat 🤍"
            ],

            # =========================
            # MAKAN & MINUMAN
            # =========================

            "makan": [
                "Selamat makan, jangan lupa berdoa dulu 😊🍜",
                "Makan apa nih? 👀",
                "Makan yang cukup ya, jaga kesehatan 🤍",
                "Jangan lupa minum juga 💧"
            ],

            "lapar": [
                "Yuk makan, jangan ditahan-tahan 😊",
                "Gofood atau masak sendiri? 🍔",
                "Mie instan juga lumayan kalau darurat 🍜",
                "Segera makan ya biar ga lemes 💪"
            ],

            "ngopi": [
                "Kopi dulu, baru mulai hari ☕",
                "Kopi memang teman terbaik saat begadang 😄",
                "Jangan kebanyakan kopi ya, jaga kesehatan 😅",
                "Kopi atau teh nih? ☕🍵"
            ],

            "minum": [
                "Jangan lupa minum air putih yang cukup ya 💧",
                "Minum dulu, penting buat kesehatan 💧",
                "Hidrasi itu penting, jangan sampai dehidrasi 😊"
            ],

            "sarapan": [
                "Sarapan dulu, jangan dilewat 🍳",
                "Jangan skip sarapan ya, penting buat aktivitas 😊",
                "Sarapan biar semangat seharian ☀️"
            ],

            "makan malam": [
                "Selamat makan malam 🌙",
                "Makan apa malam ini? 👀",
                "Jangan makan terlalu larut malam ya 😅"
            ],

            "ngemil": [
                "Ngemil apa tuh? 👀",
                "Ngemil boleh, tapi jangan kebanyakan ya 😄",
                "Cemilannya dibagi-bagi dong 😭"
            ],

            "warung": [
                "Jajan ke warung 🏪",
                "Beli apa nih? 👀",
                "Warung terdekat emang penyelamat 😄"
            ],

            "boba": [
                "Boba dong 🧋",
                "Enak nih minum boba 😄",
                "Jangan kebanyakan sugar ya 😅🧋"
            ],

            "kopi susu": [
                "Kopi susu emang juara ☕🤍",
                "Enak banget tuh 😄",
                "Kopi susu teman kerja yang setia ✨"
            ],

            # =========================
            # KESEHATAN
            # =========================

            "sakit": [
                "Aduh, sakit apa? Semoga cepat sembuh ya 🤍",
                "Istirahat yang banyak, minum obat teratur 💊",
                "Semoga lekas sehat ya, jaga diri 🤍",
                "Jangan lupa minum air putih yang banyak 💧"
            ],

            "demam": [
                "Aduh demam, istirahat dulu ya 🤒",
                "Kompres dan minum air putih yang banyak 💧",
                "Semoga cepat sembuh 🤍",
                "Kalau parah, jangan lupa ke dokter ya 😊"
            ],

            "pusing": [
                "Aduh pusing, istirahat dulu 😔",
                "Minum air putih dulu, mungkin kurang hidrasi 💧",
                "Tidur sebentar mungkin membantu 😴"
            ],

            "mual": [
                "Aduh, semoga segera membaik ya 🤍",
                "Istirahat dulu, jangan makan yang berat 😊",
                "Kalau parah ke dokter ya 😊"
            ],

            "lelah": [
                "Istirahat dulu, kamu sudah berusaha keras 🌿",
                "Tubuh butuh jeda juga lho 😴",
                "Tidur yang cukup ya 🤍"
            ],

            "olahraga": [
                "Salut yang rajin olahraga 💪",
                "Sehat itu investasi terbaik 😊",
                "Keep it up, konsisten adalah kuncinya 🔥"
            ],

            "gym": [
                "Gas gym 💪",
                "Konsisten ya latihannya 🔥",
                "Semangat, hasilnya worth it 😄"
            ],

            "jogging": [
                "Sehat banget jogging pagi 🏃",
                "Semangat joggingnya 💪",
                "Konsisten ya, tubuh sehat jiwa kuat 😊"
            ],

            "tidur": [
                "Istirahat yang cukup ya 😴",
                "Tidur yang nyenyak, besok pasti lebih segar 🌙",
                "Selamat istirahat 😴🤍"
            ],

            "begadang": [
                "Jangan terlalu sering begadang ya, kasihan badannya 😅",
                "Kalau bisa tidur lebih awal, kesehatan lebih terjaga 🌙",
                "Kopi dulu kalau emang harus begadang ☕"
            ],

            # =========================
            # MOTIVASI & RELIGI
            # =========================

            "semangat": [
                "Semangat terus ya 🔥",
                "Kamu pasti bisa ✨",
                "Fighting! 💪",
                "You got this! 🔥",
                "Don't give up, pasti ada jalan 🌟"
            ],

            "bismillah": [
                "InsyaAllah lancar 🤍",
                "Aamiin, semoga dimudahkan ✨",
                "Aamiin ya rabbal alamin 🤍"
            ],

            "doain": [
                "Aamiin, semoga dimudahkan 🤲",
                "Bot ikut doa juga ya 🙏",
                "InsyaAllah dikabulkan 🤍"
            ],

            "alhamdulillah": [
                "Alhamdulillah, syukuri selalu ya 🤍",
                "Aamiin, semoga terus diberkahi ✨",
                "Nikmat yang selalu patut disyukuri 🤲"
            ],

            "insyaallah": [
                "InsyaAllah, semoga dimudahkan 🤍",
                "Aamiin, percaya aja 🤲"
            ],

            "aamiin": [
                "Aamiin ya rabbal alamin 🤍",
                "Semoga dikabulkan Allah ✨",
                "Aamiin, InsyaAllah 🤲"
            ],

            "subhanallah": [
                "Subhanallah 🤍",
                "MasyaAllah indah ya ✨"
            ],

            "masya allah": [
                "MasyaAllah, indah ya ciptaan-Nya 🤍",
                "MasyaAllah ✨"
            ],

            "masyaallah": [
                "MasyaAllah 🤍",
                "Indah banget, syukuri ya ✨"
            ],

            "syukur": [
                "Alhamdulillah, selalu syukuri ya 🤍",
                "Bersyukur itu bikin hati tenang 😊✨"
            ],

            "sabar": [
                "Sabar itu memang berat, tapi hasilnya indah 🌿",
                "Tetap sabar ya, InsyaAllah ada hikmahnya 🤍",
                "Kamu kuat, pasti bisa melewati ini 💙"
            ],

            "ikhlas": [
                "Ikhlas itu memang susah tapi melegakan 🌿",
                "Semoga bisa melapangkan hati 🤍",
                "Ikhlas adalah kunci ketenangan 😊"
            ],

            "tawakkal": [
                "Setelah berusaha, tawakkal adalah langkah terbaik 🤍",
                "Serahkan pada Allah, InsyaAllah ada jalan 🌿"
            ],

            "resign": [
                "Berani, semoga dapet yang lebih baik 🤍",
                "Goodluck di chapter baru 🔥",
                "Semoga langkah selanjutnya lebih baik ✨"
            ],

            "kerja": [
                "Semangat kerjanya 💪",
                "Produktif terus, jangan lupa istirahat juga ya 🌿",
                "Kerja keras pasti ada hasilnya 🔥"
            ],

            "lulus": [
                "Selamat lulus 🎉🎓",
                "Congrats! Kerja keras terbayar 🥳",
                "Semoga sukses di langkah berikutnya 🤍"
            ],

            "diterima": [
                "Selamat, kerja keras terbayar 🎉",
                "Congrats! Semoga sukses di sana 🔥",
                "Alhamdulillah, semoga berkah 🤍"
            ],

            "interview": [
                "Goodluck interviewnya 💪",
                "Percaya sama kemampuan sendiri ya 😊",
                "Bismillah, semoga lancar 🤍"
            ],

            "magang": [
                "Semangat magangnya 💪",
                "Ambil ilmu sebanyak-banyaknya 😊",
                "Goodluck, semoga pengalamannya seru 🔥"
            ],

            # =========================
            # CINTA / HUBUNGAN
            # =========================

            "sayang": [
                "Cieee, ada yang lagi manis 🥰",
                "Uwuu, semoga langgeng 💑",
                "Aww, bahagia deh dengernya 😊"
            ],

            "kangen": [
                "Hubungin orangnya, jangan cuma dipendem 😊",
                "Cie kangen, ungkapin aja 👀",
                "Kangen tanda perhatian, cantik sekali perasaannya 🤍"
            ],

            "galau": [
                "Sabar ya, waktu akan membantu 🫂",
                "Jangan dipikirin terlalu dalam, santai dulu 🌿",
                "Ceritain kalau mau, bot dengerin 😊",
                "Fokus ke hal positif dulu, perlahan pasti membaik 💙"
            ],

            "jomblo": [
                "Jomblo itu bebas dan bahagia 😎",
                "Single happy, nikmatin aja dulu 😄",
                "Waktu yang tepat pasti datang 🤍",
                "Jomblo bukan masalah, yang penting happy 🌟"
            ],

            "bucin": [
                "Bucin tanda cinta yang dalam 😄",
                "Normal kok, namanya juga suka 😊",
                "Hehe, cinta memang bikin gitu 🤍"
            ],

            "pdkt": [
                "Semoga berhasil 🤍",
                "Goodluck pdkt-nya, jangan takut 😄",
                "Berani saja, yang penting usaha dulu 💪"
            ],

            "nembak": [
                "Bismillah, berani itu keren 😊",
                "Goodluck! Semoga diterima 🤍",
                "Apapun hasilnya, kamu sudah berani dan itu yang penting 💪"
            ],

            "gebetan": [
                "Cie ada gebetan 👀",
                "Udah kenalan belum? Mulai dari sana dulu 😄",
                "Semoga berjodoh 🤍"
            ],

            "putus": [
                "Sabar ya, ini pasti terasa berat 🫂",
                "Waktu akan menyembuhkan, percaya 🌿",
                "Kamu kuat kok, pasti bisa melewati ini 💙",
                "Fokus jaga diri sendiri dulu ya 🤍"
            ],

            "balikan": [
                "Pikir matang-matang dulu, jangan terburu-buru 👀",
                "Ikutin kata hati, tapi tetap pakai logika juga 🤍",
                "Keputusan ada di tangan kamu, yang penting dirimu bahagia 😊"
            ],

            "anniversary": [
                "Selamat anniversary 🎉💑",
                "Wah, semoga makin langgeng dan harmonis 🤍",
                "Happy anniversary, semoga berkah 🥰"
            ],

            "nikah": [
                "Wah, selamat ya 🎉",
                "Semoga jadi keluarga yang sakinah mawaddah warahmah 🤍",
                "Barakallah, semoga bahagia selalu 💑"
            ],

            "jadian": [
                "Selamat jadian 🎉",
                "Wah, cie cie 👀",
                "Semoga langgeng dan saling mendukung ya 💑🤍"
            ],

            # =========================
            # CUACA
            # =========================

            "hujan": [
                "Hujan nih, stay safe kalau mau kemana-mana 🌧️",
                "Jangan lupa bawa payung 🌂",
                "Enak nih rebahan pas hujan 😴",
                "Hati-hati banjir kalau hujan deras 🌧️"
            ],

            "panas": [
                "Panas banget ya, minum air putih yang banyak 💧",
                "Pakai sunscreen kalau keluar rumah ya 😊",
                "Cari tempat yang adem dulu 🌬️",
                "Jaga stamina di cuaca panas gini ☀️"
            ],

            "dingin": [
                "Dingin nih, pakai baju yang hangat ya 🧥",
                "Minum yang hangat biar nyaman 🍵",
                "Enak tidur kalau dingin-dingin gini 😴"
            ],

            "mendung": [
                "Mendung nih, kayaknya mau hujan 🌥️",
                "Bawa payung jaga-jaga ya 🌂",
                "Mendung bikin ngantuk ya 😴"
            ],

            "angin": [
                "Anginnya kenceng ya, hati-hati 🌬️",
                "Jangan keluar kalau anginnya besar 😊"
            ],

            "banjir": [
                "Aduh banjir, hati-hati ya 🌊",
                "Jaga keselamatan dulu, barang bisa diganti 🤍",
                "Semoga segera surut 🙏"
            ],

            # =========================
            # TEKNOLOGI & SOSMED
            # =========================

            "discord": [
                "Discord emang platform yang asik buat komunitas 😎",
                "Bot juga ada di Discord lho 😄",
                "Discord teman setia nih 🔥"
            ],

            "youtube": [
                "Nonton apa nih? 📺",
                "YouTube memang candu sih 😭",
                "Jangan lupa subscribe channel favorit ya 📺"
            ],

            "tiktok": [
                "Scroll TikTok lagi nih 📱",
                "Hati-hati ketagihan, waktu cepat habis 😅",
                "FYP terus? 😄"
            ],

            "instagram": [
                "IG nih, upload apa? 📸",
                "Jangan lupa upload story 😄",
                "Hati-hati ketagihan scroll IG juga 📸"
            ],

            "twitter": [
                "Twitter emang selalu ramai 😄",
                "Timeline lagi rame nih 👀",
                "Scroll X dulu kali 😎"
            ],

            "hp": [
                "HP apa nih? 📱",
                "Jaga HP-nya baik-baik 😄",
                "Jangan lupa charge sebelum mati baterai 🔋"
            ],

            "laptop": [
                "Laptop apa nih? 💻",
                "Jaga laptopnya ya 😄",
                "Jangan lupa charge dan backup data 🔋"
            ],

            "internet": [
                "Internet lagi gimana? 🌐",
                "Semoga koneksinya stabil terus 😊",
                "Internet emang kebutuhan pokok sekarang 😄"
            ],

            "wifi": [
                "WiFi-nya kenceng? 🌐",
                "Semoga sinyalnya bagus terus 😊",
                "WiFi yang stabil itu nikmat banget 😄"
            ],

            "update": [
                "Semangat update-nya 🔄",
                "Jangan lupa backup dulu sebelum update 😊",
                "Update biar dapat fitur baru 🔥"
            ],

            "error": [
                "Aduh error, coba restart dulu 😅",
                "Screenshot errornya terus cari solusinya 😊",
                "Tenang, pasti ada jalan keluarnya 💙"
            ],

            "bug": [
                "Aduh ada bug, coba cek lagi 😅",
                "Debugging emang butuh kesabaran 😊",
                "Semangat nemuin solusinya 💪"
            ],

            # =========================
            # PERJALANAN & TEMPAT
            # =========================

            "jalan-jalan": [
                "Seru nih jalan-jalan 🚶",
                "Mau kemana? 👀",
                "Nikmatin perjalanannya ya 😊"
            ],

            "liburan": [
                "Asik liburan 🏖️",
                "Mau kemana liburannya? 👀",
                "Semoga menyenangkan dan aman ya 🤍"
            ],

            "mudik": [
                "Mudik nih, hati-hati di jalan ya 🚗",
                "Selamat mudik, semoga selamat sampai tujuan 🤍",
                "Jangan lupa istirahat kalau lelah di jalan 😊"
            ],

            "macet": [
                "Aduh macet, sabar ya 🚗",
                "Manfaatin waktu macet dengan dengerin podcast 🎧",
                "Sabar, macet pasti berlalu 😊"
            ],

            "pulang": [
                "Selamat pulang, hati-hati di jalan ya 🤍",
                "Akhirnya pulang, istirahat dulu 😊",
                "Sampai rumah dengan selamat ya 🏠"
            ],

            "berangkat": [
                "Hati-hati di jalan ya 🤍",
                "Semoga perjalanannya lancar 😊",
                "Selamat berangkat 👋"
            ],

            # =========================
            # EKSPRESI & MEME
            # =========================

            "wkwk": [
                "Hehe, lucu ya 😄",
                "Ketawa dulu sebelum produktif 😂",
                "Wkwkwk, apa tuh? 👀"
            ],

            "awok": [
                "Ngakak bet 😭",
                "Lucu banget sih 😄",
                "Awokawok balik 🤣"
            ],

            "lol": [
                "Haha, lucu ya 😄",
                "Ketawa bareng deh 😂",
                "Wkwk lol 👀"
            ],

            "haha": [
                "Hehe, ada apa? 😄",
                "Lucu ya 😂",
                "Ketawa dulu 👀"
            ],

            "lmao": [
                "Ngakak nih 😂",
                "Lucu bet 😭",
                "Hahaha 😄"
            ],

            "anjay": [
                "Wah, plot twist 😄",
                "Kejutan ya 👀",
                "Santuy hehe 😎"
            ],

            "waduh": [
                "Waduh kenapa? 👀",
                "Ada apa waduh 😄",
                "Ceritain dong 😊"
            ],

            "duh": [
                "Aduh kenapa? 😊",
                "Ceritain dong 👀",
                "Semoga baik-baik aja 🤍"
            ],

            "yah": [
                "Kenapa yah? 👀",
                "Ada yang kurang oke? 😊",
                "Ceritain dong 🤍"
            ],

            "yaelah": [
                "Wkwk yaelah 😄",
                "Gimana tuh ceritanya? 👀",
                "Hehe, ada apa? 😊"
            ],

            "astaga": [
                "Astaga kenapa? 👀",
                "Ada apa tuh? 😄",
                "Ceritain dong 😊"
            ],

            "aduh": [
                "Aduh kenapa? 🥺",
                "Ada yang bisa dibantu? 😊",
                "Semoga baik-baik aja ya 🤍"
            ],

            "gokil": [
                "Gokil bet 🔥",
                "Mantap, keren 😎",
                "Top banget 💯"
            ],

            "mantap": [
                "Mantap jiwa 😎",
                "Keren, salut 🔥",
                "Top, bagus 👌"
            ],

            "keren": [
                "Emang keren 😎",
                "Setuju, top 🔥",
                "Salut deh 👏"
            ],

            "gaskeun": [
                "Gas gas gas 🔥",
                "Gaskeun, semangat 💪",
                "Yok gaass 🚀"
            ],

            "ygy": [
                "Bener banget tuh 😄",
                "Ygy, setuju 👀",
                "Facts 😎"
            ],

            "btw": [
                "Btw apa nih? 👀",
                "Oiya? Ceritain dong 😄",
                "Ada info apa? 👀"
            ],

            "ngl": [
                "Jujur banget 😄",
                "Facts sih 👀",
                "Berani jujur, bagus 😎"
            ],

            "fr fr": [
                "On god, bener banget 😎",
                "Facts 💯",
                "Setuju banget 🔥"
            ],

            "no cap": [
                "Jujur emang keren 😎",
                "Cap detector: clean 💯",
                "Facts detected 😄"
            ],

            "skill issue": [
                "Haha, skill issue nih 💀",
                "Practice more dulu 😎",
                "Skill dulu baru flex 🔥"
            ],

            "based": [
                "Based bet 😎",
                "Setuju 💯",
                "Bener banget tuh 🔥"
            ],

            "real": [
                "Real banget 💯",
                "Facts 😎",
                "Setuju 🔥"
            ],

            "deadass": [
                "Serius? 👀",
                "Wah beneran tuh 😄",
                "Facts sih 💯"
            ],

            "lowkey": [
                "Hehe, lowkey nih 👀",
                "Diem-diem tapi ada 😄",
                "Santuy 😎"
            ],

            # =========================
            # HOBI & HIBURAN
            # =========================

            "nonton": [
                "Nonton apa nih? 🎬",
                "Seru, mau nonton apa? 📺",
                "Selamat nonton 😄🍿"
            ],

            "baca": [
                "Baca apa nih? 📖",
                "Rajin baca bagus buat wawasan 😊",
                "Selamat membaca 📚"
            ],

            "dengerin musik": [
                "Dengerin musik apa nih? 🎵",
                "Musik memang teman setia 🎧",
                "Enak ya sambil dengerin musik 😊"
            ],

            "musik": [
                "Dengerin musik apa nih? 🎵",
                "Musik genre apa yang lagi diputar? 🎧",
                "Musik emang bisa bikin mood baik 😊"
            ],

            "film": [
                "Film apa nih? 🎬",
                "Genre apa yang lagi ditonton? 👀",
                "Selamat nonton, semoga filmnya bagus 🍿"
            ],

            "series": [
                "Lagi nonton series apa? 📺",
                "Series emang candu ya 😅",
                "Selamat maraton series 🍿"
            ],

            "anime": [
                "Anime apa nih? 👀",
                "Anime emang seru 😄",
                "Lagi nonton season berapa? 🎌"
            ],

            "buku": [
                "Baca buku apa nih? 📖",
                "Rajin baca buku itu keren 😊",
                "Buku teman setia yang ga bisa bales kamu 😄"
            ],

            "foto": [
                "Foto apa nih? 📸",
                "Kamera atau HP? 😄",
                "Semoga hasilnya bagus 📸"
            ],

            "gambar": [
                "Gambar apa nih? 🎨",
                "Keren bisa menggambar 😊",
                "Semoga hasilnya sesuai ekspektasi 🎨"
            ],

            "nulis": [
                "Nulis apa nih? ✍️",
                "Rajin nulis bagus banget 😊",
                "Semangat nulisnya, pasti bagus 📝"
            ],

            "masak": [
                "Masak apa nih? 🍳",
                "Wah, masak sendiri keren banget 👏",
                "Semoga masakannya enak 😄"
            ],

            "tanaman": [
                "Rajin merawat tanaman keren 🌱",
                "Tanaman apa nih? 🌿",
                "Semoga tanamannya tumbuh subur 😊"
            ],

            "coding": [
                "Lagi coding apa nih? 💻",
                "Semangat codingnya 🔥",
                "Debug dulu kalau ada error 😄"
            ],

            "desain": [
                "Lagi desain apa nih? 🎨",
                "Kreatif banget 😊",
                "Semoga hasilnya kece 🔥"
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