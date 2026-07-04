import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
import random
import asyncio
from datetime import datetime
import pytz

# ==========================================
# CONFIG
# ==========================================

QUIZ_CHANNEL_ID  = 1511643581457104957
STAFF_CHANNEL_ID = 1511643581457104957

MOD_ROLE_ID    = 1453103644244316343
OSIS_ROLE_ID   = 1427276194876751902
PEMBINA_ROLE_ID = 1467360501745844446
MURID_ROLE_ID  = 1453095603008442510

DEFAULT_REWARD   = "75K OwO"
QUIZ_DURATION    = 300   # detik
CLUE_INTERVAL    = 60    # detik antar clue (tebak_negara)
ANGKA_RANGE      = (1, 100)
HINT_AT_FRACTION = 0.5   # hint muncul di 50% durasi kalau belum ada yang jawab

# ==========================================
# TIPE CHALLENGE & LABEL
# ==========================================

CHALLENGE_LABELS = {
    "tebak_jawaban":  "❓ Tebak Jawaban",
    "susun_kata":     "🔀 Susun Kata",
    "kirim_emoji":    "😄 Kirim Emoji",
    "kirim_kalimat":  "💬 Kirim Kalimat",
    "hitung_cepat":   "🔢 Hitung Cepat",
    "tebak_gambar":   "🖼️ Tebak Gambar",
    "petunjuk_huruf": "🔡 Petunjuk Huruf",
    "tebak_angka":    "🎯 Tebak Angka",
    "anagram":        "🔤 Anagram",
    "tebak_negara":   "🗺️ Tebak Negara",
    "isi_angka":      "🧮 Isi Angka",
    "isi_kata":       "📖 Isi Kata",
    "mirror_text":    "🔁 Mirror Text",
    "apa_persamaan":  "🔗 Apa Persamaan",
    "odd_one_out":    "🧠 Odd One Out",
    "tebak_kode":     "🔐 Tebak Kode",
    "tebak_film":     "🎬 Tebak Film",
    "tebak_pola":     "🧩 Tebak Pola",
}

# Warna embed berbeda per tipe biar lebih variatif secara visual
CHALLENGE_COLORS = {
    "tebak_jawaban":  discord.Color.blue(),
    "susun_kata":     discord.Color.teal(),
    "kirim_emoji":    discord.Color.gold(),
    "kirim_kalimat":  discord.Color.orange(),
    "hitung_cepat":   discord.Color.green(),
    "tebak_gambar":   discord.Color.purple(),
    "petunjuk_huruf": discord.Color.dark_teal(),
    "tebak_angka":    discord.Color.red(),
    "anagram":        discord.Color.magenta(),
    "tebak_negara":   discord.Color.dark_gold(),
    "isi_angka":      discord.Color.dark_green(),
    "isi_kata":       discord.Color.dark_orange(),
    "mirror_text":    discord.Color.dark_magenta(),
    "apa_persamaan":  discord.Color.dark_blue(),
    "odd_one_out":    discord.Color.dark_red(),
    "tebak_kode":     discord.Color.dark_purple(),
    "tebak_film":     discord.Color.blurple(),
    "tebak_pola":     discord.Color.fuchsia(),
}

# Tipe yang boleh dikasih auto-hint di tengah waktu (jawaban berupa teks,
# bukan yang jawabannya harus persis/exact seperti kirim_emoji/kirim_kalimat,
# bukan juga tebak_angka/tebak_negara/tebak_gambar/petunjuk_huruf yang
# sudah punya "hint" bawaan)
HINT_ELIGIBLE_TYPES = {
    "tebak_jawaban", "anagram", "isi_kata", "mirror_text",
    "apa_persamaan", "odd_one_out", "tebak_kode", "tebak_film",
}

# ==========================================
# CONTOH SOAL PER TIPE (untuk referensi staff)
# ==========================================

CHALLENGE_EXAMPLES = {
    "tebak_jawaban":  "❓ **Pertanyaan:** Apa ibu kota Jepang?\n✅ **Jawaban:** tokyo",
    "susun_kata":     "🔀 **Kata acak:** `suka kucing makan ikan`\n✅ **Jawaban:** kucing suka makan ikan",
    "kirim_emoji":    "😄 **Kirim persis:** 🎉🎊🎈\n✅ **Jawaban:** 🎉🎊🎈 (harus sama persis)",
    "kirim_kalimat":  "💬 **Ketik persis:** `nanZ Server is the best!`\n✅ **Jawaban:** nanZ Server is the best! (kapital & tanda baca dihitung)",
    "hitung_cepat":   "🔢 **Soal:** 2 + 8 x 2 = ?\n✅ **Jawaban:** 18",
    "tebak_gambar":   "🖼️ **URL gambar** bendera Jepang dikirim\n✅ **Jawaban:** jepang\n💡 *Bisa juga upload gambar langsung via tombol Custom!*",
    "petunjuk_huruf": "🔡 **Petunjuk:** S _ _ _ _ _ A (7 huruf)\n✅ **Jawaban:** sumatera",
    "tebak_angka":    "🎯 **Tebak angka** antara 1–100\n✅ **Pemenang:** yang jawabannya paling dekat saat waktu habis",
    "anagram":        "🔤 **Huruf acak:** K A N A M\n✅ **Jawaban:** makan",
    "tebak_negara":   "🗺️ **Clue 1:** Punya 7.000+ pulau | **Clue 2:** Mata uangnya Peso | **Clue 3:** Ibu kotanya Manila\n✅ **Jawaban:** filipina",
    "isi_angka":      "🧮 **Deret:** 2, 4, 8, ?, 32\n✅ **Jawaban:** 16",
    "isi_kata":       "📖 **Kalimat:** Semakin ___ semakin baik\n✅ **Jawaban:** muda",
    "mirror_text":    "🔁 **Teks balik:** `!aisenodnI ubi atniC ukA`\n✅ **Jawaban:** Aku Cinta ibu Indonesia",
    "apa_persamaan":  "🔗 **3 kata:** Matahari | Pagi | Timur\n✅ **Jawaban:** terbit",
    "odd_one_out":    "🧠 **4 kata:** Apel | Mangga | Wortel | Pisang\n✅ **Jawaban:** wortel (bukan buah)",
    "tebak_kode":     "🔐 **Kode:** 8-5-12-12-15 (A=1, B=2...)\n✅ **Jawaban:** hello",
    "tebak_film":     "🎬 **Emoji:** 🦁👑\n✅ **Jawaban:** the lion king",
    "tebak_pola":     "🧩 **Pola:** 🔴🔵🔴🔵🔴?\n✅ **Jawaban:** 🔵",
}

# ==========================================
# BANK SOAL DEFAULT
# ==========================================

QUESTIONS = [
    # ── TEBAK JAWABAN ──────────────────────────────────────────────
    {"type": "tebak_jawaban", "question": "Apa ibu kota Jepang?", "answer": "tokyo"},
    {"type": "tebak_jawaban", "question": "Planet terbesar di tata surya?", "answer": "jupiter"},
    {"type": "tebak_jawaban", "question": "Hewan tercepat di dunia?", "answer": "cheetah"},
    {"type": "tebak_jawaban", "question": "Siapa presiden pertama Indonesia?", "answer": "soekarno"},
    {"type": "tebak_jawaban", "question": "Gunung tertinggi di dunia?", "answer": "everest"},
    {"type": "tebak_jawaban", "question": "Apa nama satelit alami bumi?", "answer": "bulan"},
    {"type": "tebak_jawaban", "question": "Apa nama mata uang Jepang?", "answer": "yen"},
    {"type": "tebak_jawaban", "question": "Apa nama burung lambang Indonesia?", "answer": "garuda"},
    {"type": "tebak_jawaban", "question": "Siapa pencipta lampu pijar?", "answer": "thomas edison"},
    {"type": "tebak_jawaban", "question": "Apa nama mamalia terbesar di dunia?", "answer": "paus biru"},

    # ── SUSUN KATA ─────────────────────────────────────────────────
    {"type": "susun_kata", "question": "Susun kata berikut jadi kalimat benar!\n**kata acak:** `langit biru berwarna`", "answer": "langit berwarna biru"},
    {"type": "susun_kata", "question": "Susun kata berikut jadi kalimat benar!\n**kata acak:** `sekolah pergi aku ke`", "answer": "aku pergi ke sekolah"},
    {"type": "susun_kata", "question": "Susun kata berikut jadi kalimat benar!\n**kata acak:** `makan suka kucing ikan`", "answer": "kucing suka makan ikan"},
    {"type": "susun_kata", "question": "Susun kata berikut jadi kalimat benar!\n**kata acak:** `pagi setiap berolahraga aku`", "answer": "aku berolahraga setiap pagi"},
    {"type": "susun_kata", "question": "Susun kata berikut jadi kalimat benar!\n**kata acak:** `belajar rajin harus kita`", "answer": "kita harus rajin belajar"},

    # ── KIRIM EMOJI ────────────────────────────────────────────────
    {"type": "kirim_emoji", "question": "Kirim emoji ini **persis sama**:\n# 🎉🎊🎈", "answer": "🎉🎊🎈"},
    {"type": "kirim_emoji", "question": "Kirim emoji ini **persis sama**:\n# 🔥💯✨", "answer": "🔥💯✨"},
    {"type": "kirim_emoji", "question": "Kirim emoji ini **persis sama**:\n# 🌙⭐🌟", "answer": "🌙⭐🌟"},
    {"type": "kirim_emoji", "question": "Kirim emoji ini **persis sama**:\n# 🐉🏆👑", "answer": "🐉🏆👑"},
    {"type": "kirim_emoji", "question": "Kirim emoji ini **persis sama**:\n# 🎮🕹️💻", "answer": "🎮🕹️💻"},

    # ── KIRIM KALIMAT ──────────────────────────────────────────────
    {"type": "kirim_kalimat", "question": "Ketik kalimat ini **persis sama** (kapital & tanda baca dihitung):\n> `nanZ Server is the best!`", "answer": "nanZ Server is the best!"},
    {"type": "kirim_kalimat", "question": "Ketik kalimat ini **persis sama** (kapital & tanda baca dihitung):\n> `Belajar itu menyenangkan!`", "answer": "Belajar itu menyenangkan!"},
    {"type": "kirim_kalimat", "question": "Ketik kalimat ini **persis sama** (kapital & tanda baca dihitung):\n> `Aku cinta Indonesia!`", "answer": "Aku cinta Indonesia!"},
    {"type": "kirim_kalimat", "question": "Ketik kalimat ini **persis sama** (kapital & tanda baca dihitung):\n> `Discord adalah platform terbaik.`", "answer": "Discord adalah platform terbaik."},

    # ── HITUNG CEPAT ───────────────────────────────────────────────
    {"type": "hitung_cepat", "question": "2 + 8 x 2 = ?", "answer": "18"},
    {"type": "hitung_cepat", "question": "10 x 10 = ?", "answer": "100"},
    {"type": "hitung_cepat", "question": "50 ÷ 5 + 3 = ?", "answer": "13"},
    {"type": "hitung_cepat", "question": "100 - 37 + 7 = ?", "answer": "70"},
    {"type": "hitung_cepat", "question": "3³ = ?", "answer": "27"},
    {"type": "hitung_cepat", "question": "√144 = ?", "answer": "12"},
    {"type": "hitung_cepat", "question": "15 x 4 ÷ 6 = ?", "answer": "10"},

    # ── TEBAK GAMBAR ───────────────────────────────────────────────
    {"type": "tebak_gambar", "question": "Negara apa yang punya bendera ini?", "answer": "jepang", "image_url": "https://flagcdn.com/w320/jp.png"},
    {"type": "tebak_gambar", "question": "Negara apa yang punya bendera ini?", "answer": "brazil", "image_url": "https://flagcdn.com/w320/br.png"},
    {"type": "tebak_gambar", "question": "Negara apa yang punya bendera ini?", "answer": "jerman", "image_url": "https://flagcdn.com/w320/de.png"},
    {"type": "tebak_gambar", "question": "Negara apa yang punya bendera ini?", "answer": "prancis", "image_url": "https://flagcdn.com/w320/fr.png"},
    {"type": "tebak_gambar", "question": "Negara apa yang punya bendera ini?", "answer": "australia", "image_url": "https://flagcdn.com/w320/au.png"},

    # ── PETUNJUK HURUF ─────────────────────────────────────────────
    {"type": "petunjuk_huruf", "question": "Tebak kata ini!\n**Petunjuk:** `S _ _ _ _ _ _ A` (8 huruf)\n*Nama pulau terbesar di Indonesia*", "answer": "sumatera"},
    {"type": "petunjuk_huruf", "question": "Tebak kata ini!\n**Petunjuk:** `T _ _ _ _ _ P` (7 huruf)\n*Alat untuk melihat bintang*", "answer": "teleskop"},
    {"type": "petunjuk_huruf", "question": "Tebak kata ini!\n**Petunjuk:** `P _ _ _ _ _ _ _ _ N` (10 huruf)\n*Proses memasak makanan*", "answer": "pengolahan"},
    {"type": "petunjuk_huruf", "question": "Tebak kata ini!\n**Petunjuk:** `K _ _ _ _ _ _ N` (8 huruf)\n*Perangkat elektronik untuk bekerja*", "answer": "komputer"},

    # ── TEBAK ANGKA ────────────────────────────────────────────────
    {"type": "tebak_angka", "question": "Tebak angka antara **1 sampai 100**!\nSemua boleh jawab, yang paling dekat saat waktu habis menang. 🎯", "answer": "__generated__"},

    # ── ANAGRAM ────────────────────────────────────────────────────
    {"type": "anagram", "question": "Susun huruf berikut jadi kata yang benar!\n**Huruf acak:** `K A N A M`", "answer": "makan"},
    {"type": "anagram", "question": "Susun huruf berikut jadi kata yang benar!\n**Huruf acak:** `A L U B`", "answer": "bula"},
    {"type": "anagram", "question": "Susun huruf berikut jadi kata yang benar!\n**Huruf acak:** `I T N U`", "answer": "unit"},
    {"type": "anagram", "question": "Susun huruf berikut jadi kata yang benar!\n**Huruf acak:** `R U M A H`", "answer": "rumah"},
    {"type": "anagram", "question": "Susun huruf berikut jadi kata yang benar!\n**Huruf acak:** `L A J A N`", "answer": "jalan"},

    # ── TEBAK NEGARA ───────────────────────────────────────────────
    {
        "type": "tebak_negara",
        "question": "Tebak negara ini!",
        "answer": "filipina",
        "clues": [
            "🌍 **Clue 1:** Negara ini terdiri dari lebih dari 7.000 pulau.",
            "🌍 **Clue 2:** Mata uang negara ini adalah Peso.",
            "🌍 **Clue 3:** Ibu kota negara ini adalah Manila.",
        ]
    },
    {
        "type": "tebak_negara",
        "question": "Tebak negara ini!",
        "answer": "brazil",
        "clues": [
            "🌍 **Clue 1:** Negara ini memiliki hutan hujan terbesar di dunia.",
            "🌍 **Clue 2:** Bahasa resminya adalah Portugis.",
            "🌍 **Clue 3:** Ibu kotanya adalah Brasília.",
        ]
    },
    {
        "type": "tebak_negara",
        "question": "Tebak negara ini!",
        "answer": "jepang",
        "clues": [
            "🌍 **Clue 1:** Negara ini dijuluki 'Negeri Matahari Terbit'.",
            "🌍 **Clue 2:** Mata uangnya adalah Yen.",
            "🌍 **Clue 3:** Ibu kotanya adalah Tokyo.",
        ]
    },
    {
        "type": "tebak_negara",
        "question": "Tebak negara ini!",
        "answer": "mesir",
        "clues": [
            "🌍 **Clue 1:** Negara ini terkenal dengan piramida kuno.",
            "🌍 **Clue 2:** Sungai terpanjang di dunia mengalir di negara ini.",
            "🌍 **Clue 3:** Ibu kotanya adalah Kairo.",
        ]
    },

    # ── ISI ANGKA ──────────────────────────────────────────────────
    {"type": "isi_angka", "question": "Isi angka yang hilang!\n`2, 4, 8, ?, 32`", "answer": "16"},
    {"type": "isi_angka", "question": "Isi angka yang hilang!\n`1, 3, 6, 10, ?, 21`", "answer": "15"},
    {"type": "isi_angka", "question": "Isi angka yang hilang!\n`5, 10, 20, ?, 80`", "answer": "40"},
    {"type": "isi_angka", "question": "Isi angka yang hilang!\n`1, 1, 2, 3, 5, ?, 13`", "answer": "8"},

    # ── ISI KATA ───────────────────────────────────────────────────
    {"type": "isi_kata", "question": "Isi kata yang hilang!\n*\"Semakin ___ semakin baik, semakin tua semakin bijak\"*", "answer": "muda"},
    {"type": "isi_kata", "question": "Isi kata yang hilang!\n*\"Bersatu kita ___, bercerai kita runtuh\"*", "answer": "teguh"},
    {"type": "isi_kata", "question": "Isi kata yang hilang!\n*\"Rajin ___ pangkal pandai\"*", "answer": "belajar"},
    {"type": "isi_kata", "question": "Isi kata yang hilang!\n*\"Air beriak tanda tak ___\"*", "answer": "dalam"},
    {"type": "isi_kata", "question": "Isi kata yang hilang!\n*\"Berakit-rakit ke hulu, berenang-renang ke ___\"*", "answer": "tepian"},

    # ── MIRROR TEXT ────────────────────────────────────────────────
    {"type": "mirror_text", "question": "Baca teks terbalik berikut dan ketik versi normalnya!\n```!aisenodnI ubi atniC ukA```", "answer": "aku cinta ibu indonesia"},
    {"type": "mirror_text", "question": "Baca teks terbalik berikut dan ketik versi normalnya!\n```!ZnaN reveS tseB```", "answer": "best server nanz!"},
    {"type": "mirror_text", "question": "Baca teks terbalik berikut dan ketik versi normalnya!\n```!rajaleB suaM ukA```", "answer": "aku mau belajar!"},

    # ── APA PERSAMAAN ──────────────────────────────────────────────
    {"type": "apa_persamaan", "question": "Cari **1 kata** yang menghubungkan ketiga kata ini!\n\n`🌅 Matahari` **|** `🌄 Pagi` **|** `🧭 Timur`", "answer": "terbit"},
    {"type": "apa_persamaan", "question": "Cari **1 kata** yang menghubungkan ketiga kata ini!\n\n`🌊 Laut` **|** `💧 Hujan` **|** `❄️ Es`", "answer": "air"},
    {"type": "apa_persamaan", "question": "Cari **1 kata** yang menghubungkan ketiga kata ini!\n\n`📚 Buku` **|** `✏️ Pena` **|** `🏫 Kelas`", "answer": "sekolah"},
    {"type": "apa_persamaan", "question": "Cari **1 kata** yang menghubungkan ketiga kata ini!\n\n`🍚 Nasi` **|** `🥢 Sendok` **|** `🍳 Dapur`", "answer": "makan"},
    {"type": "apa_persamaan", "question": "Cari **1 kata** yang menghubungkan ketiga kata ini!\n\n`🌳 Pohon` **|** `🌿 Daun` **|** `🌱 Tanah`", "answer": "tumbuh"},

    # ── ODD ONE OUT ────────────────────────────────────────────────
    {"type": "odd_one_out", "question": "Mana yang **tidak sekelompok**?\n\n🍎 Apel **|** 🥭 Mangga **|** 🥕 Wortel **|** 🍌 Pisang", "answer": "wortel"},
    {"type": "odd_one_out", "question": "Mana yang **tidak sekelompok**?\n\n🐶 Anjing **|** 🐱 Kucing **|** 🦁 Singa **|** 🦅 Elang", "answer": "elang"},
    {"type": "odd_one_out", "question": "Mana yang **tidak sekelompok**?\n\n🔴 Merah **|** 🔵 Biru **|** 🟡 Kuning **|** 📐 Segitiga", "answer": "segitiga"},
    {"type": "odd_one_out", "question": "Mana yang **tidak sekelompok**?\n\n🚗 Mobil **|** 🚂 Kereta **|** ✈️ Pesawat **|** 🏠 Rumah", "answer": "rumah"},
    {"type": "odd_one_out", "question": "Mana yang **tidak sekelompok**?\n\n🎸 Gitar **|** 🥁 Drum **|** 🎹 Piano **|** 🖥️ Komputer", "answer": "komputer"},

    # ── TEBAK KODE ─────────────────────────────────────────────────
    {"type": "tebak_kode", "question": "Decode kode berikut! *(A=1, B=2, C=3, ...)*\n```8 - 5 - 12 - 12 - 15```", "answer": "hello"},
    {"type": "tebak_kode", "question": "Decode kode berikut! *(A=1, B=2, C=3, ...)*\n```23 - 15 - 18 - 12 - 4```", "answer": "world"},
    {"type": "tebak_kode", "question": "Decode kode berikut! *(A=1, B=2, C=3, ...)*\n```14 - 1 - 14 - 26```", "answer": "nanz"},
    {"type": "tebak_kode", "question": "Decode Caesar Cipher +3!\n*(Geser setiap huruf 3 posisi ke belakang)*\n```EHORYHG```", "answer": "beloved"},
    {"type": "tebak_kode", "question": "Decode Caesar Cipher +3!\n*(Geser setiap huruf 3 posisi ke belakang)*\n```GLVFRUG```", "answer": "discord"},

    # ── TEBAK FILM ─────────────────────────────────────────────────
    {"type": "tebak_film", "question": "Tebak judul film/lagu dari emoji ini!\n# 🦁👑", "answer": "the lion king"},
    {"type": "tebak_film", "question": "Tebak judul film/lagu dari emoji ini!\n# ❄️👸", "answer": "frozen"},
    {"type": "tebak_film", "question": "Tebak judul film/lagu dari emoji ini!\n# 🕷️👨", "answer": "spiderman"},
    {"type": "tebak_film", "question": "Tebak judul film/lagu dari emoji ini!\n# 🧙‍♂️⚡📚", "answer": "harry potter"},
    {"type": "tebak_film", "question": "Tebak judul film/lagu dari emoji ini!\n# 🦸🦹💥🌆", "answer": "avengers"},
    {"type": "tebak_film", "question": "Tebak judul film/lagu dari emoji ini!\n# 🐟🔵🌊", "answer": "finding nemo"},
    {"type": "tebak_film", "question": "Tebak judul film/lagu dari emoji ini!\n# 🚗⚡️", "answer": "cars"},

    # ── TEBAK POLA ─────────────────────────────────────────────────
    {"type": "tebak_pola", "question": "Lanjutkan pola berikut!\n`🔴 🔵 🔴 🔵 🔴 ?`", "answer": "🔵"},
    {"type": "tebak_pola", "question": "Lanjutkan pola berikut!\n`🌑 🌒 🌓 🌔 ?`", "answer": "🌕"},
    {"type": "tebak_pola", "question": "Lanjutkan pola berikut!\n`⭐ ⭐⭐ ⭐⭐⭐ ?`", "answer": "⭐⭐⭐⭐"},
    {"type": "tebak_pola", "question": "Lanjutkan pola berikut!\n`🟥 🟧 🟨 🟩 ?`", "answer": "🟦"},
    {"type": "tebak_pola", "question": "Lanjutkan pola berikut!\n`1️⃣ 2️⃣ 4️⃣ 8️⃣ ?`", "answer": "1️⃣6️⃣"},
]

# ==========================================
# HELPER
# ==========================================

def is_case_sensitive(ctype: str) -> bool:
    return ctype in ("kirim_kalimat", "kirim_emoji")

def reverse_text(text: str) -> str:
    return text[::-1]

def generate_hint(answer: str) -> str:
    """Buat hint dengan menyamarkan sebagian huruf tiap kata, huruf
    pertama & terakhir tiap kata tetap terlihat."""
    words = answer.strip().split(" ")
    hinted = []
    for w in words:
        if len(w) == 0:
            continue
        elif len(w) <= 2:
            hinted.append(w[0] + "•" * (len(w) - 1))
        else:
            hinted.append(w[0] + "•" * (len(w) - 2) + w[-1])
    return " ".join(hinted)

def fmt_leaderboard(leaderboard: dict, guild: discord.Guild) -> str:
    if not leaderboard:
        return "Belum ada yang menang quiz. Jadilah yang pertama! 🚀"
    top = sorted(leaderboard.items(), key=lambda kv: kv[1], reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (uid, wins) in enumerate(top):
        prefix = medals[i] if i < 3 else f"`#{i+1}`"
        member = guild.get_member(uid) if guild else None
        name = member.mention if member else f"`{uid}`"
        lines.append(f"{prefix} {name} — **{wins}** kemenangan")
    return "\n".join(lines)

# ==========================================
# MODALS
# ==========================================

class RewardModal(Modal, title="🎁 Edit Reward"):
    reward = TextInput(label="Jumlah Reward", placeholder="100K OwO")

    def __init__(self, view):
        super().__init__()
        self.quiz_view = view

    async def on_submit(self, interaction: discord.Interaction):
        value = self.reward.value.strip()
        if not value:
            return await interaction.response.send_message("❌ Reward tidak boleh kosong!", ephemeral=True)
        self.quiz_view.reward = value
        embed = _build_draft_embed(self.quiz_view.challenge_data, self.quiz_view.reward)
        await interaction.response.edit_message(embed=embed, view=self.quiz_view)
        await interaction.followup.send(f"✅ Reward diubah → **{value}**", ephemeral=True)


class CustomTebakModal(Modal, title="📝 Custom — Tebak Jawaban / Hitung / Anagram / Isi"):
    question = TextInput(label="Pertanyaan / Instruksi", style=discord.TextStyle.long)
    answer   = TextInput(label="Jawaban (tidak case-sensitive)")

    def __init__(self, view):
        super().__init__()
        self.quiz_view = view

    async def on_submit(self, interaction: discord.Interaction):
        q = self.question.value.strip()
        a = self.answer.value.strip()
        if not q or not a:
            return await interaction.response.send_message("❌ Pertanyaan dan jawaban tidak boleh kosong!", ephemeral=True)
        self.quiz_view.challenge_data = {
            "type": self.quiz_view.challenge_data.get("type", "tebak_jawaban"),
            "question": q,
            "answer": a
        }
        embed = _build_draft_embed(self.quiz_view.challenge_data, self.quiz_view.reward)
        await interaction.response.edit_message(embed=embed, view=self.quiz_view)
        await interaction.followup.send("✅ Challenge berhasil di-custom!", ephemeral=True)


class CustomKalimatModal(Modal, title="💬 Custom — Kirim Kalimat"):
    kalimat = TextInput(label="Kalimat yang harus diketik user persis sama")

    def __init__(self, view):
        super().__init__()
        self.quiz_view = view

    async def on_submit(self, interaction: discord.Interaction):
        val = self.kalimat.value.strip()
        if not val:
            return await interaction.response.send_message("❌ Kalimat tidak boleh kosong!", ephemeral=True)
        self.quiz_view.challenge_data = {
            "type": "kirim_kalimat",
            "question": f"Ketik kalimat ini **persis sama** (kapital & tanda baca dihitung):\n> `{val}`",
            "answer": val
        }
        embed = _build_draft_embed(self.quiz_view.challenge_data, self.quiz_view.reward)
        await interaction.response.edit_message(embed=embed, view=self.quiz_view)
        await interaction.followup.send("✅ Challenge Kirim Kalimat diatur!", ephemeral=True)


class CustomEmojiModal(Modal, title="😄 Custom — Kirim Emoji"):
    emoji_str = TextInput(label="Emoji yang harus dikirim persis", placeholder="🎉🎊🎈")

    def __init__(self, view):
        super().__init__()
        self.quiz_view = view

    async def on_submit(self, interaction: discord.Interaction):
        val = self.emoji_str.value.strip()
        if not val:
            return await interaction.response.send_message("❌ Emoji tidak boleh kosong!", ephemeral=True)
        self.quiz_view.challenge_data = {
            "type": "kirim_emoji",
            "question": f"Kirim emoji ini **persis sama**:\n# {val}",
            "answer": val
        }
        embed = _build_draft_embed(self.quiz_view.challenge_data, self.quiz_view.reward)
        await interaction.response.edit_message(embed=embed, view=self.quiz_view)
        await interaction.followup.send("✅ Challenge Kirim Emoji diatur!", ephemeral=True)


class CustomSusunKataModal(Modal, title="🔀 Custom — Susun Kata"):
    kata_acak = TextInput(label="Kata-kata acak (pisah spasi)", placeholder="biru langit berwarna")
    jawaban   = TextInput(label="Kalimat yang benar", placeholder="langit berwarna biru")

    def __init__(self, view):
        super().__init__()
        self.quiz_view = view

    async def on_submit(self, interaction: discord.Interaction):
        acak = self.kata_acak.value.strip()
        jawab = self.jawaban.value.strip()
        if not acak or not jawab:
            return await interaction.response.send_message("❌ Kata acak dan jawaban tidak boleh kosong!", ephemeral=True)
        self.quiz_view.challenge_data = {
            "type": "susun_kata",
            "question": f"Susun kata berikut jadi kalimat benar!\n**kata acak:** `{acak}`",
            "answer": jawab.lower()
        }
        embed = _build_draft_embed(self.quiz_view.challenge_data, self.quiz_view.reward)
        await interaction.response.edit_message(embed=embed, view=self.quiz_view)
        await interaction.followup.send("✅ Challenge Susun Kata diatur!", ephemeral=True)


class CustomGambarModal(Modal, title="🖼️ Custom — Tebak Gambar (URL)"):
    image_url = TextInput(label="URL Gambar", placeholder="https://...")
    question  = TextInput(label="Pertanyaan", placeholder="Apa nama hewan ini?")
    answer    = TextInput(label="Jawaban")

    def __init__(self, view):
        super().__init__()
        self.quiz_view = view

    async def on_submit(self, interaction: discord.Interaction):
        url = self.image_url.value.strip()
        q = self.question.value.strip()
        a = self.answer.value.strip()
        if not url.startswith("http"):
            return await interaction.response.send_message("❌ URL gambar tidak valid! Harus diawali `http`.", ephemeral=True)
        if not q or not a:
            return await interaction.response.send_message("❌ Pertanyaan dan jawaban tidak boleh kosong!", ephemeral=True)
        self.quiz_view.challenge_data = {
            "type": "tebak_gambar",
            "question": q,
            "answer": a.lower(),
            "image_url": url
        }
        embed = _build_draft_embed(self.quiz_view.challenge_data, self.quiz_view.reward)
        await interaction.response.edit_message(embed=embed, view=self.quiz_view)
        await interaction.followup.send("✅ Challenge Tebak Gambar (URL) diatur!", ephemeral=True)


class CustomNegaraModal(Modal, title="🗺️ Custom — Tebak Negara"):
    jawaban = TextInput(label="Jawaban (nama negara)")
    clue1   = TextInput(label="Clue 1 (paling susah)", placeholder="Negara ini punya 7.000+ pulau")
    clue2   = TextInput(label="Clue 2", placeholder="Mata uangnya Peso")
    clue3   = TextInput(label="Clue 3 (paling mudah)", placeholder="Ibu kotanya Manila")

    def __init__(self, view):
        super().__init__()
        self.quiz_view = view

    async def on_submit(self, interaction: discord.Interaction):
        jawab = self.jawaban.value.strip()
        if not jawab or not self.clue1.value.strip() or not self.clue2.value.strip() or not self.clue3.value.strip():
            return await interaction.response.send_message("❌ Semua field harus diisi!", ephemeral=True)
        self.quiz_view.challenge_data = {
            "type": "tebak_negara",
            "question": "Tebak negara ini!",
            "answer": jawab.lower(),
            "clues": [
                f"🌍 **Clue 1:** {self.clue1.value.strip()}",
                f"🌍 **Clue 2:** {self.clue2.value.strip()}",
                f"🌍 **Clue 3:** {self.clue3.value.strip()}",
            ]
        }
        embed = _build_draft_embed(self.quiz_view.challenge_data, self.quiz_view.reward)
        await interaction.response.edit_message(embed=embed, view=self.quiz_view)
        await interaction.followup.send("✅ Challenge Tebak Negara diatur!", ephemeral=True)


class CustomAngkaModal(Modal, title="🎯 Custom — Tebak Angka"):
    min_val = TextInput(label="Angka minimum", placeholder="1")
    max_val = TextInput(label="Angka maksimum", placeholder="100")

    def __init__(self, view):
        super().__init__()
        self.quiz_view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            lo = int(self.min_val.value.strip() or "1")
            hi = int(self.max_val.value.strip() or "100")
        except ValueError:
            return await interaction.response.send_message("❌ Min dan Max harus berupa angka bulat!", ephemeral=True)
        if lo >= hi:
            return await interaction.response.send_message("❌ Angka minimum harus lebih kecil dari maksimum!", ephemeral=True)
        self.quiz_view.challenge_data = {
            "type": "tebak_angka",
            "question": f"Tebak angka antara **{lo} sampai {hi}**!\nSemua boleh jawab, yang paling dekat saat waktu habis menang. 🎯",
            "answer": "__generated__",
            "range": (lo, hi)
        }
        embed = _build_draft_embed(self.quiz_view.challenge_data, self.quiz_view.reward)
        await interaction.response.edit_message(embed=embed, view=self.quiz_view)
        await interaction.followup.send(f"✅ Range diatur: {lo}–{hi}. Angka rahasia di-generate saat Approve.", ephemeral=True)


class CustomMirrorModal(Modal, title="🔁 Custom — Mirror Text"):
    teks_asli = TextInput(label="Teks asli (akan dibalik otomatis)", placeholder="Aku Cinta ibu Indonesia!")

    def __init__(self, view):
        super().__init__()
        self.quiz_view = view

    async def on_submit(self, interaction: discord.Interaction):
        asli = self.teks_asli.value.strip()
        if not asli:
            return await interaction.response.send_message("❌ Teks tidak boleh kosong!", ephemeral=True)
        terbalik = reverse_text(asli)
        self.quiz_view.challenge_data = {
            "type": "mirror_text",
            "question": f"Baca teks terbalik berikut dan ketik versi normalnya!\n```{terbalik}```",
            "answer": asli.lower()
        }
        embed = _build_draft_embed(self.quiz_view.challenge_data, self.quiz_view.reward)
        await interaction.response.edit_message(embed=embed, view=self.quiz_view)
        await interaction.followup.send(f"✅ Mirror Text diatur! Teks terbalik: `{terbalik}`", ephemeral=True)


class CustomPolaModal(Modal, title="🧩 Custom — Tebak Pola"):
    pola    = TextInput(label="Pola yang ditampilkan", placeholder="🔴 🔵 🔴 🔵 🔴 ?")
    jawaban = TextInput(label="Jawaban lanjutan pola", placeholder="🔵")

    def __init__(self, view):
        super().__init__()
        self.quiz_view = view

    async def on_submit(self, interaction: discord.Interaction):
        pola = self.pola.value.strip()
        jawab = self.jawaban.value.strip()
        if not pola or not jawab:
            return await interaction.response.send_message("❌ Pola dan jawaban tidak boleh kosong!", ephemeral=True)
        self.quiz_view.challenge_data = {
            "type": "tebak_pola",
            "question": f"Lanjutkan pola berikut!\n`{pola}`",
            "answer": jawab
        }
        embed = _build_draft_embed(self.quiz_view.challenge_data, self.quiz_view.reward)
        await interaction.response.edit_message(embed=embed, view=self.quiz_view)
        await interaction.followup.send("✅ Challenge Tebak Pola diatur!", ephemeral=True)


class CustomFilmModal(Modal, title="🎬 Custom — Tebak Film"):
    emoji_str = TextInput(label="Emoji representasi film/lagu", placeholder="🦁👑")
    jawaban   = TextInput(label="Judul film/lagu (tidak case-sensitive)", placeholder="the lion king")

    def __init__(self, view):
        super().__init__()
        self.quiz_view = view

    async def on_submit(self, interaction: discord.Interaction):
        emoji = self.emoji_str.value.strip()
        jawab = self.jawaban.value.strip()
        if not emoji or not jawab:
            return await interaction.response.send_message("❌ Emoji dan jawaban tidak boleh kosong!", ephemeral=True)
        self.quiz_view.challenge_data = {
            "type": "tebak_film",
            "question": f"Tebak judul film/lagu dari emoji ini!\n# {emoji}",
            "answer": jawab.lower()
        }
        embed = _build_draft_embed(self.quiz_view.challenge_data, self.quiz_view.reward)
        await interaction.response.edit_message(embed=embed, view=self.quiz_view)
        await interaction.followup.send("✅ Challenge Tebak Film diatur!", ephemeral=True)


class CustomPersamaanModal(Modal, title="🔗 Custom — Apa Persamaan"):
    kata1   = TextInput(label="Kata 1")
    kata2   = TextInput(label="Kata 2")
    kata3   = TextInput(label="Kata 3")
    jawaban = TextInput(label="Kata yang menghubungkan ketiganya")

    def __init__(self, view):
        super().__init__()
        self.quiz_view = view

    async def on_submit(self, interaction: discord.Interaction):
        jawab = self.jawaban.value.strip()
        if not jawab or not self.kata1.value.strip() or not self.kata2.value.strip() or not self.kata3.value.strip():
            return await interaction.response.send_message("❌ Semua field harus diisi!", ephemeral=True)
        self.quiz_view.challenge_data = {
            "type": "apa_persamaan",
            "question": (
                f"Cari **1 kata** yang menghubungkan ketiga kata ini!\n\n"
                f"`{self.kata1.value.strip()}` **|** `{self.kata2.value.strip()}` **|** `{self.kata3.value.strip()}`"
            ),
            "answer": jawab.lower()
        }
        embed = _build_draft_embed(self.quiz_view.challenge_data, self.quiz_view.reward)
        await interaction.response.edit_message(embed=embed, view=self.quiz_view)
        await interaction.followup.send("✅ Challenge Apa Persamaan diatur!", ephemeral=True)


class CustomOddOneOutModal(Modal, title="🧠 Custom — Odd One Out"):
    pilihan = TextInput(label="4 pilihan (pisah |)", placeholder="Apel | Mangga | Wortel | Pisang")
    jawaban = TextInput(label="Yang tidak sekelompok", placeholder="wortel")

    def __init__(self, view):
        super().__init__()
        self.quiz_view = view

    async def on_submit(self, interaction: discord.Interaction):
        jawab = self.jawaban.value.strip()
        parts = [p.strip() for p in self.pilihan.value.split("|") if p.strip()]
        if not jawab or len(parts) < 2:
            return await interaction.response.send_message("❌ Isi minimal 2 pilihan (pisah `|`) dan jawaban!", ephemeral=True)
        display = " **|** ".join(parts)
        self.quiz_view.challenge_data = {
            "type": "odd_one_out",
            "question": f"Mana yang **tidak sekelompok**?\n\n{display}",
            "answer": jawab.lower()
        }
        embed = _build_draft_embed(self.quiz_view.challenge_data, self.quiz_view.reward)
        await interaction.response.edit_message(embed=embed, view=self.quiz_view)
        await interaction.followup.send("✅ Challenge Odd One Out diatur!", ephemeral=True)


class CustomKodeModal(Modal, title="🔐 Custom — Tebak Kode"):
    soal    = TextInput(label="Kode yang ditampilkan", placeholder="8 - 5 - 12 - 12 - 15")
    hint    = TextInput(label="Petunjuk cara decode", placeholder="A=1, B=2, C=3, ...")
    jawaban = TextInput(label="Jawaban setelah decode")

    def __init__(self, view):
        super().__init__()
        self.quiz_view = view

    async def on_submit(self, interaction: discord.Interaction):
        soal = self.soal.value.strip()
        jawab = self.jawaban.value.strip()
        if not soal or not jawab:
            return await interaction.response.send_message("❌ Kode dan jawaban tidak boleh kosong!", ephemeral=True)
        self.quiz_view.challenge_data = {
            "type": "tebak_kode",
            "question": f"Decode kode berikut! *({self.hint.value.strip()})*\n```{soal}```",
            "answer": jawab.lower()
        }
        embed = _build_draft_embed(self.quiz_view.challenge_data, self.quiz_view.reward)
        await interaction.response.edit_message(embed=embed, view=self.quiz_view)
        await interaction.followup.send("✅ Challenge Tebak Kode diatur!", ephemeral=True)


# ==========================================
# UPLOAD GAMBAR — Modal untuk jawaban + instruksi
# ==========================================

class UploadGambarModal(Modal, title="📎 Upload Gambar — Tebak Gambar"):
    image_url = TextInput(
        label="URL Gambar (Discord CDN / URL publik)",
        placeholder="https://cdn.discordapp.com/attachments/...",
        style=discord.TextStyle.long
    )
    question = TextInput(
        label="Pertanyaan",
        placeholder="Apa nama hewan ini?",
        default="Tebak apa yang ada di gambar ini!"
    )
    answer = TextInput(label="Jawaban (tidak case-sensitive)")

    def __init__(self, view):
        super().__init__()
        self.quiz_view = view

    async def on_submit(self, interaction: discord.Interaction):
        url = self.image_url.value.strip()
        q = self.question.value.strip()
        a = self.answer.value.strip()
        if not url.startswith("http"):
            return await interaction.response.send_message("❌ URL gambar tidak valid! Harus diawali `http`.", ephemeral=True)
        if not a:
            return await interaction.response.send_message("❌ Jawaban tidak boleh kosong!", ephemeral=True)
        self.quiz_view.challenge_data = {
            "type": "tebak_gambar",
            "question": q,
            "answer": a.lower(),
            "image_url": url
        }
        embed = _build_draft_embed(self.quiz_view.challenge_data, self.quiz_view.reward)
        await interaction.response.edit_message(embed=embed, view=self.quiz_view)
        await interaction.followup.send(f"✅ Gambar diatur!\n🖼️ Preview: {url}", ephemeral=True)


# ==========================================
# ON_ERROR HANDLER — pasang ke semua modal
# ==========================================

def _patch_modal_on_error(modal_cls):
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        import traceback
        traceback.print_exception(type(error), error, error.__traceback__)
        try:
            await interaction.response.send_message(
                f"❌ Terjadi error: `{type(error).__name__}` — coba lagi.",
                ephemeral=True
            )
        except Exception:
            try:
                await interaction.followup.send("❌ Terjadi error saat memproses form.", ephemeral=True)
            except Exception:
                pass
    modal_cls.on_error = on_error
    return modal_cls

for _cls in [
    RewardModal, CustomTebakModal, CustomKalimatModal, CustomEmojiModal,
    CustomSusunKataModal, CustomGambarModal, CustomNegaraModal, CustomAngkaModal,
    CustomMirrorModal, CustomPolaModal, CustomFilmModal, CustomPersamaanModal,
    CustomOddOneOutModal, CustomKodeModal, UploadGambarModal,
]:
    _patch_modal_on_error(_cls)


# ==========================================
# QUIZ PANEL VIEW (PERMANEN)
# ==========================================

class QuizPanelView(View):
    """Panel permanen di channel staff — tidak punya timeout."""

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="📋 Buat Quiz Baru",
        style=discord.ButtonStyle.green,
        custom_id="panel_new_quiz",
        row=0
    )
    async def new_quiz(self, interaction: discord.Interaction, button: Button):
        if self.bot.quiz_active:
            return await interaction.response.send_message(
                "❌ Masih ada quiz yang sedang aktif.",
                ephemeral=True
            )

        challenge = random.choice(QUESTIONS).copy()
        view = StaffDraftView(self.bot, challenge)
        embed = _build_draft_embed(challenge, DEFAULT_REWARD)

        await interaction.response.send_message(
            content="📝 **Draft Quiz** — Edit sesuai kebutuhan lalu klik **✅ Approve** untuk publish.",
            embed=embed,
            view=view,
            ephemeral=True
        )

    @discord.ui.button(
        label="📖 Contoh Soal",
        style=discord.ButtonStyle.blurple,
        custom_id="panel_examples",
        row=0
    )
    async def show_examples(self, interaction: discord.Interaction, button: Button):
        lines = ["## 📖 Contoh Soal per Tipe Challenge\n"]
        for ctype, label in CHALLENGE_LABELS.items():
            example = CHALLENGE_EXAMPLES.get(ctype, "-")
            lines.append(f"### {label}\n{example}\n")

        full = "\n".join(lines)
        chunks = [full[i:i+1900] for i in range(0, len(full), 1900)]
        await interaction.response.send_message(chunks[0], ephemeral=True)
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk, ephemeral=True)

    @discord.ui.button(
        label="🏆 Leaderboard",
        style=discord.ButtonStyle.blurple,
        custom_id="panel_leaderboard",
        row=1
    )
    async def show_leaderboard(self, interaction: discord.Interaction, button: Button):
        leaderboard = getattr(self.bot, "quiz_leaderboard", {})
        embed = discord.Embed(
            title="🏆 Leaderboard nanZ Quiz",
            description=fmt_leaderboard(leaderboard, interaction.guild),
            color=discord.Color.gold()
        )
        total_played = getattr(self.bot, "quiz_total_played", 0)
        embed.set_footer(text=f"nanZ Server • Total quiz dimainkan: {total_played}")
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="⏹️ Stop Quiz",
        style=discord.ButtonStyle.red,
        custom_id="panel_stop_quiz",
        row=1
    )
    async def stop_quiz(self, interaction: discord.Interaction, button: Button):
        if not self.bot.quiz_active:
            return await interaction.response.send_message("❌ Tidak ada quiz yang aktif.", ephemeral=True)

        self.bot.quiz_active = False
        self.bot.current_answer = None
        self.bot.current_challenge_type = None
        self.bot.current_reward = None
        self.bot.current_quiz_message = None
        self.bot.tebak_angka_entries = {}
        self.bot.quiz_attempts = {}

        quiz_channel = self.bot.get_channel(QUIZ_CHANNEL_ID)
        embed = discord.Embed(
            title="⏹️ Quiz Dihentikan",
            description="Quiz dihentikan oleh staff.",
            color=discord.Color.red()
        )
        embed.set_footer(text="nanZ Server")
        await quiz_channel.send(embed=embed)
        await interaction.response.send_message("✅ Quiz berhasil dihentikan.", ephemeral=True)


# ==========================================
# STAFF DRAFT VIEW (EPHEMERAL)
# ==========================================

def _build_draft_embed(challenge: dict, reward: str) -> discord.Embed:
    ctype = challenge.get("type", "tebak_jawaban")
    label = CHALLENGE_LABELS.get(ctype, "❓ Quiz")
    answer_display = challenge.get("answer", "-")
    if answer_display == "__generated__":
        lo, hi = challenge.get("range", ANGKA_RANGE)
        answer_display = f"*(di-generate saat approve, range {lo}–{hi})*"

    embed = discord.Embed(
        title=f"📝 Draft Quiz — {label}",
        color=CHALLENGE_COLORS.get(ctype, discord.Color.dark_purple())
    )
    embed.add_field(name="❓ Pertanyaan / Challenge", value=challenge.get("question", "-"), inline=False)
    embed.add_field(name="✅ Jawaban", value=f"`{answer_display}`", inline=True)
    embed.add_field(name="🎁 Reward", value=reward, inline=True)
    embed.add_field(name="⏱️ Durasi", value="5 Menit", inline=True)

    if challenge.get("image_url"):
        embed.set_image(url=challenge["image_url"])

    embed.set_footer(text="nanZ Server • Staff Draft — Belum dipublish")
    embed.timestamp = discord.utils.utcnow()
    return embed


class StaffDraftView(View):
    """View draft quiz yang dikirim ephemeral ke staff."""

    def __init__(self, bot, challenge_data):
        super().__init__(timeout=600)
        self.bot = bot
        self.challenge_data = challenge_data
        self.reward = DEFAULT_REWARD

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.is_finished():
            await interaction.response.send_message(
                "❌ Draft ini sudah kadaluarsa. Buat quiz baru dari panel.",
                ephemeral=True
            )
            return False
        return True

    # ── APPROVE ────────────────────────────────────────────────────

    @discord.ui.button(label="✅ Approve & Publish", style=discord.ButtonStyle.green, custom_id="draft_approve", row=0)
    async def approve(self, interaction: discord.Interaction, button: Button):
        if self.bot.quiz_active:
            return await interaction.response.send_message("❌ Masih ada quiz aktif.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        self.bot.quiz_active = True
        self.bot.quiz_total_played = getattr(self.bot, "quiz_total_played", 0) + 1

        ctype   = self.challenge_data.get("type", "tebak_jawaban")
        label   = CHALLENGE_LABELS.get(ctype, "❓ Quiz")
        channel = self.bot.get_channel(QUIZ_CHANNEL_ID)

        if ctype == "tebak_angka":
            lo, hi = self.challenge_data.get("range", ANGKA_RANGE)
            secret = random.randint(lo, hi)
            self.bot.tebak_angka_secret = secret
            self.bot.tebak_angka_entries = {}

        embed = discord.Embed(
            title=f"🎉 nanZ Quiz — {label}",
            description=self._build_public_description(ctype),
            color=CHALLENGE_COLORS.get(ctype, discord.Color.blurple())
        )
        embed.set_footer(text="nanZ Server • Jawab secepat mungkin!")
        embed.timestamp = discord.utils.utcnow()

        quiz_msg = None

        if ctype == "tebak_gambar" and self.challenge_data.get("image_url"):
            embed.set_image(url=self.challenge_data["image_url"])
            quiz_msg = await channel.send(
                content=f"📢 **nanZ Quiz dimulai!** <@&{MURID_ROLE_ID}>",
                embed=embed
            )
        else:
            try:
                file = discord.File("assets/nanzquiz.gif", filename="nanzquiz.gif")
                embed.set_image(url="attachment://nanzquiz.gif")
                quiz_msg = await channel.send(
                    content=f"📢 **nanZ Quiz dimulai!** <@&{MURID_ROLE_ID}>",
                    embed=embed,
                    file=file
                )
            except FileNotFoundError:
                quiz_msg = await channel.send(
                    content=f"📢 **nanZ Quiz dimulai!** <@&{MURID_ROLE_ID}>",
                    embed=embed
                )

        self.bot.current_quiz_message = quiz_msg
        self._set_bot_state(ctype)

        await interaction.followup.send("✅ Quiz berhasil dipublish!", ephemeral=True)
        self.stop()
        await self._wait_and_end(channel, ctype)

    def _set_bot_state(self, ctype: str):
        self.bot.current_challenge_type = ctype
        self.bot.current_reward        = self.reward
        self.bot.current_answer = (
            None if ctype == "tebak_angka"
            else self.challenge_data.get("answer", "").strip()
        )
        if ctype == "tebak_negara":
            self.bot.negara_clues    = self.challenge_data.get("clues", [])
            self.bot.negara_clue_idx = 0

    async def _send_hint_if_eligible(self, channel, ctype: str):
        """Kirim hint di tengah waktu kalau tipe soal cocok & belum ada yang jawab."""
        if ctype not in HINT_ELIGIBLE_TYPES:
            return
        wait_time = QUIZ_DURATION * HINT_AT_FRACTION
        await asyncio.sleep(wait_time)
        if not self.bot.quiz_active:
            return
        answer = self.bot.current_answer
        if not answer:
            return
        hint = generate_hint(answer)
        remaining = int(QUIZ_DURATION - wait_time)
        embed = discord.Embed(
            title="💡 Hint Muncul!",
            description=f"Masih bingung? Ini petunjuknya:\n# `{hint}`\n\n⏳ Sisa waktu ~{remaining // 60} menit {remaining % 60} detik!",
            color=discord.Color.yellow()
        )
        embed.set_footer(text="nanZ Server • Semangat!")
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    async def _wait_and_end(self, channel, ctype: str):
        if ctype == "tebak_negara":
            clues = self.bot.negara_clues
            for i, clue in enumerate(clues):
                await asyncio.sleep(CLUE_INTERVAL)
                if not self.bot.quiz_active:
                    return
                self.bot.negara_clue_idx = i
                clue_embed = discord.Embed(
                    description=clue,
                    color=discord.Color.blurple()
                )
                clue_embed.set_footer(text=f"nanZ Server • Clue {i+1}/{len(clues)}")
                await channel.send(embed=clue_embed)
            remaining = QUIZ_DURATION - (len(clues) * CLUE_INTERVAL)
            if remaining > 0:
                await asyncio.sleep(remaining)

        elif ctype == "tebak_angka":
            await asyncio.sleep(QUIZ_DURATION)
            if not self.bot.quiz_active:
                return
            secret  = self.bot.tebak_angka_secret
            entries = self.bot.tebak_angka_entries
            self.bot.quiz_active = False

            if not entries:
                end_embed = discord.Embed(
                    title="⏰ Quiz Ended — Tebak Angka",
                    description=f"Tidak ada yang menjawab!\n**Angka rahasia:** `{secret}`",
                    color=discord.Color.red()
                )
                end_embed.set_footer(text="nanZ Server")
                await channel.send(embed=end_embed)
            else:
                winner_id  = min(entries, key=lambda uid: abs(entries[uid][0] - secret))
                winner_val, winner_member = entries[winner_id]

                leaderboard = getattr(self.bot, "quiz_leaderboard", {})
                leaderboard[winner_id] = leaderboard.get(winner_id, 0) + 1
                self.bot.quiz_leaderboard = leaderboard
                total_wins = leaderboard[winner_id]

                end_embed = discord.Embed(
                    title="🎯 nanZQuiz Winner — Tebak Angka",
                    description=(
                        f"**Angka rahasia:** `{secret}`\n\n"
                        f"Pemenang: {winner_member.mention}\n"
                        f"**Tebakan:** `{winner_val}` *(selisih {abs(winner_val - secret)})*\n"
                        f"**Reward:** {self.bot.current_reward}\n"
                        f"**Total kemenangan:** {total_wins} 🏆\n\n"
                        f"> Staff akan segera memberikan hadiah kamu."
                    ),
                    color=discord.Color.gold()
                )
                end_embed.set_thumbnail(url=winner_member.display_avatar.url)
                end_embed.set_footer(text="nanZ Server • Congratulations")
                end_embed.timestamp = discord.utils.utcnow()
                await channel.send(embed=end_embed)

                staff_channel = self.bot.get_channel(STAFF_CHANNEL_ID)
                staff_embed = discord.Embed(
                    title="Reward Notice — Tebak Angka",
                    description=(
                        f"**Username:** {winner_member}\n"
                        f"**User ID:** {winner_member.id}\n"
                        f"**Tebakan:** {winner_val} (angka rahasia: {secret})\n"
                        f"**Reward:** {self.bot.current_reward}\n\n"
                        f"> Silakan transfer hadiah OwO."
                    ),
                    color=discord.Color.green()
                )
                staff_embed.set_thumbnail(url=winner_member.display_avatar.url)
                await staff_channel.send(embed=staff_embed)

            self.bot.tebak_angka_entries = {}
            self.bot.tebak_angka_secret  = None
            self.bot.current_reward      = None
            return

        else:
            hint_task = asyncio.create_task(self._send_hint_if_eligible(channel, ctype))
            await asyncio.sleep(QUIZ_DURATION)
            if not hint_task.done():
                hint_task.cancel()

        if self.bot.quiz_active:
            end_embed = discord.Embed(
                title="⏰ Quiz Ended",
                description="Belum ada yang berhasil kali ini 😔\nJawaban yang benar: **" + str(self.bot.current_answer) + "**",
                color=discord.Color.red()
            )
            end_embed.set_footer(text="nanZ Server")
            await channel.send(embed=end_embed)
            self.bot.quiz_active            = False
            self.bot.current_answer         = None
            self.bot.current_challenge_type = None
            self.bot.current_reward         = None
            self.bot.current_quiz_message   = None
            self.bot.quiz_attempts          = {}

    def _build_public_description(self, ctype: str) -> str:
        q = self.challenge_data.get("question", "-")
        r = self.reward
        meta = f"\n\n**Reward:** {r} | **Durasi:** 5 Menit"

        instructions = {
            "tebak_jawaban":  f"\n❓ **Pertanyaan:**\n{q}\n\n> Jawab langsung di chat!",
            "susun_kata":     f"\n🔀 **Susun Kata:**\n{q}\n\n> Ketik susunan kalimat yang benar!",
            "kirim_emoji":    f"\n😄 **Kirim Emoji:**\n{q}\n\n> Salin dan kirim emoji persis seperti di atas!",
            "kirim_kalimat":  f"\n💬 **Kirim Kalimat:**\n{q}\n\n> Ketik persis sama — kapital & tanda baca dihitung!",
            "hitung_cepat":   f"\n🔢 **Hitung Cepat:**\n{q}\n\n> Jawab angkanya saja!",
            "tebak_gambar":   f"\n🖼️ **Tebak Gambar:**\n{q}\n\n> Lihat gambar di atas dan jawab!",
            "petunjuk_huruf": f"\n🔡 **Petunjuk Huruf:**\n{q}\n\n> Tebak kata lengkapnya!",
            "tebak_angka": (
                                f"\n🎯 **Tebak Angka:**\n{q}\n\n"
                                "> Semua boleh jawab — yang paling dekat menang!\n"
                                "> Maksimal 5 tebakan per user.\n"
                                "> Jika mengirim lebih dari 1 tebakan, yang dihitung adalah tebakan TERAKHIR."
                            ),
            "anagram":        f"\n🔤 **Anagram:**\n{q}\n\n> Susun huruf-huruf itu jadi kata yang benar!",
            "tebak_negara":   f"\n🗺️ **Tebak Negara:**\n{q}\n\n> Clue akan muncul tiap {CLUE_INTERVAL} detik!",
            "isi_angka":      f"\n🧮 **Isi Angka:**\n{q}\n\n> Ketik angka yang hilang!",
            "isi_kata":       f"\n📖 **Isi Kata:**\n{q}\n\n> Ketik kata yang hilang!",
            "mirror_text":    f"\n🔁 **Mirror Text:**\n{q}\n\n> Baca teks terbalik itu dan ketik versi normalnya!",
            "apa_persamaan":  f"\n🔗 **Apa Persamaan?**\n{q}\n\n> Ketik 1 kata yang menghubungkan ketiganya!",
            "odd_one_out":    f"\n🧠 **Odd One Out:**\n{q}\n\n> Ketik mana yang tidak sekelompok!",
            "tebak_kode":     f"\n🔐 **Tebak Kode:**\n{q}\n\n> Decode dan ketik jawabannya!",
            "tebak_film":     f"\n🎬 **Tebak Film:**\n{q}\n\n> Tebak judul film/lagu dari emoji itu!",
            "tebak_pola":     f"\n🧩 **Tebak Pola:**\n{q}\n\n> Ketik kelanjutan pola tersebut!",
        }
        return instructions.get(ctype, q) + meta

    # ── EDIT REWARD ────────────────────────────────────────────────

    @discord.ui.button(label="🎁 Edit Reward", style=discord.ButtonStyle.blurple, custom_id="draft_reward", row=0)
    async def edit_reward(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(RewardModal(self))

    # ── DROPDOWN GANTI TIPE ────────────────────────────────────────

    @discord.ui.select(
        placeholder="🎲 Ganti Tipe Challenge...",
        options=[
            discord.SelectOption(label="❓ Tebak Jawaban",    value="tebak_jawaban",  emoji="❓"),
            discord.SelectOption(label="🔀 Susun Kata",       value="susun_kata",     emoji="🔀"),
            discord.SelectOption(label="😄 Kirim Emoji",      value="kirim_emoji",    emoji="😄"),
            discord.SelectOption(label="💬 Kirim Kalimat",    value="kirim_kalimat",  emoji="💬"),
            discord.SelectOption(label="🔢 Hitung Cepat",     value="hitung_cepat",   emoji="🔢"),
            discord.SelectOption(label="🖼️ Tebak Gambar",    value="tebak_gambar",   emoji="🖼️"),
            discord.SelectOption(label="🔡 Petunjuk Huruf",   value="petunjuk_huruf", emoji="🔡"),
            discord.SelectOption(label="🎯 Tebak Angka",      value="tebak_angka",    emoji="🎯"),
            discord.SelectOption(label="🔤 Anagram",          value="anagram",        emoji="🔤"),
            discord.SelectOption(label="🗺️ Tebak Negara",    value="tebak_negara",   emoji="🗺️"),
            discord.SelectOption(label="🧮 Isi Angka",        value="isi_angka",      emoji="🧮"),
            discord.SelectOption(label="📖 Isi Kata",         value="isi_kata",       emoji="📖"),
            discord.SelectOption(label="🔁 Mirror Text",      value="mirror_text",    emoji="🔁"),
            discord.SelectOption(label="🔗 Apa Persamaan",    value="apa_persamaan",  emoji="🔗"),
            discord.SelectOption(label="🧠 Odd One Out",      value="odd_one_out",    emoji="🧠"),
            discord.SelectOption(label="🔐 Tebak Kode",       value="tebak_kode",     emoji="🔐"),
            discord.SelectOption(label="🎬 Tebak Film",       value="tebak_film",     emoji="🎬"),
            discord.SelectOption(label="🧩 Tebak Pola",       value="tebak_pola",     emoji="🧩"),
        ],
        custom_id="draft_type_select",
        row=1
    )
    async def select_type(self, interaction: discord.Interaction, select: Select):
        chosen = select.values[0]
        pool   = [q for q in QUESTIONS if q["type"] == chosen]
        if pool:
            self.challenge_data = random.choice(pool).copy()
            msg = f"✅ Tipe diganti ke **{CHALLENGE_LABELS[chosen]}** — soal diambil dari bank default."
        else:
            self.challenge_data = {"type": chosen, "question": "-", "answer": "-"}
            msg = f"✅ Tipe diganti ke **{CHALLENGE_LABELS[chosen]}** — tidak ada soal default, isi via **📝 Custom**."

        embed = _build_draft_embed(self.challenge_data, self.reward)
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(msg, ephemeral=True)

    # ── CUSTOM CHALLENGE ───────────────────────────────────────────

    @discord.ui.button(label="📝 Custom Challenge", style=discord.ButtonStyle.gray, custom_id="draft_custom", row=2)
    async def custom_challenge(self, interaction: discord.Interaction, button: Button):
        ctype = self.challenge_data.get("type", "tebak_jawaban")
        modal_cls_map = {
            "tebak_jawaban":  CustomTebakModal,
            "hitung_cepat":   CustomTebakModal,
            "anagram":        CustomTebakModal,
            "isi_angka":      CustomTebakModal,
            "isi_kata":       CustomTebakModal,
            "petunjuk_huruf": CustomTebakModal,
            "odd_one_out":    CustomOddOneOutModal,
            "susun_kata":     CustomSusunKataModal,
            "kirim_kalimat":  CustomKalimatModal,
            "kirim_emoji":    CustomEmojiModal,
            "tebak_gambar":   CustomGambarModal,
            "tebak_negara":   CustomNegaraModal,
            "tebak_angka":    CustomAngkaModal,
            "mirror_text":    CustomMirrorModal,
            "tebak_pola":     CustomPolaModal,
            "tebak_film":     CustomFilmModal,
            "apa_persamaan":  CustomPersamaanModal,
            "tebak_kode":     CustomKodeModal,
        }
        modal_cls = modal_cls_map.get(ctype, CustomTebakModal)
        await interaction.response.send_modal(modal_cls(self))

    # ── UPLOAD GAMBAR ────────────────────────────────────────────

    @discord.ui.button(label="📎 Upload Gambar", style=discord.ButtonStyle.gray, custom_id="draft_upload_img", row=2)
    async def upload_gambar(self, interaction: discord.Interaction, button: Button):
        self.challenge_data["type"] = "tebak_gambar"
        await interaction.response.send_modal(UploadGambarModal(self))

    # ── RANDOM ULANG ───────────────────────────────────────────────

    @discord.ui.button(label="🔄 Random Ulang", style=discord.ButtonStyle.gray, custom_id="draft_random", row=3)
    async def random_ulang(self, interaction: discord.Interaction, button: Button):
        ctype = self.challenge_data.get("type", "tebak_jawaban")
        pool  = [q for q in QUESTIONS if q["type"] == ctype]
        if pool:
            self.challenge_data = random.choice(pool).copy()
        embed = _build_draft_embed(self.challenge_data, self.reward)
        await interaction.response.edit_message(embed=embed, view=self)

    # ── CANCEL ─────────────────────────────────────────────────────

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red, custom_id="draft_cancel", row=3)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("❌ Quiz dibatalkan.", ephemeral=True)
        self.stop()


# ==========================================
# COG
# ==========================================

class NanZQuiz(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.bot.quiz_active            = False
        self.bot.current_answer         = None
        self.bot.current_challenge_type = None
        self.bot.current_reward         = None
        self.bot.current_quiz_message   = None
        self.bot.quiz_attempts          = {}
        self.bot.tebak_angka_secret     = None
        self.bot.tebak_angka_entries    = {}
        self.bot.negara_clues           = []
        self.bot.negara_clue_idx        = 0
        self.bot.quiz_max_attempts      = 5
        self.bot.quiz_leaderboard       = getattr(bot, "quiz_leaderboard", {})
        self.bot.quiz_total_played      = getattr(bot, "quiz_total_played", 0)

    # ==========================================
    # COMMAND: BUAT PANEL PERMANEN
    # ==========================================

    @commands.command()
    @commands.has_any_role(MOD_ROLE_ID, OSIS_ROLE_ID, PEMBINA_ROLE_ID)
    async def quizpanel(self, ctx):
        """Kirim panel quiz permanen ke channel staff. Cukup sekali."""
        embed = discord.Embed(
            title="🎮 nanZ Quiz Panel",
            description=(
                "Panel kontrol quiz server.\n\n"
                "**📋 Buat Quiz Baru** — Buat draft quiz, pilih tipe, custom soal, lalu approve.\n"
                "**📖 Contoh Soal** — Lihat contoh soal tiap tipe sebagai referensi.\n"
                "**🏆 Leaderboard** — Lihat ranking pemenang quiz.\n"
                "**⏹️ Stop Quiz** — Hentikan quiz yang sedang berjalan.\n\n"
            ),
            color=discord.Color.dark_purple()
        )
        embed.set_footer(text="nanZ Server • Staff Panel")
        embed.timestamp = discord.utils.utcnow()

        await ctx.send(embed=embed, view=QuizPanelView(self.bot))
        await ctx.message.delete()

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

        ctype      = self.bot.current_challenge_type or "tebak_jawaban"
        user_input = message.content.strip()
        uid        = message.author.id
        max_att    = self.bot.quiz_max_attempts

        attempts = self.bot.quiz_attempts.get(uid, 0)
        if attempts >= max_att:
            return

        self.bot.quiz_attempts[uid] = attempts + 1

        if self.bot.quiz_attempts[uid] == max_att - 1:
            try:
                await message.reply(
                    "`⚠️ Ini adalah kesempatan terakhirmu untuk menjawab quiz ini!`",
                    delete_after=5
                )
            except Exception:
                pass

        # ── TEBAK ANGKA ───────────────────────────────────────────
        if ctype == "tebak_angka":
            try:
                val = int(user_input)
                self.bot.tebak_angka_entries[uid] = (val, message.author)
            except ValueError:
                self.bot.quiz_attempts[uid] = max(0, self.bot.quiz_attempts[uid] - 1)
            return

        # ── TIPE LAIN ─────────────────────────────────────────────
        if is_case_sensitive(ctype):
            correct = user_input == self.bot.current_answer
        else:
            correct = user_input.lower() == (self.bot.current_answer or "").lower()

        if not correct:
            return

        self.bot.quiz_active = False
        label = CHALLENGE_LABELS.get(ctype, "❓ Quiz")

        leaderboard = self.bot.quiz_leaderboard
        leaderboard[uid] = leaderboard.get(uid, 0) + 1
        total_wins = leaderboard[uid]

        winner_embed = discord.Embed(
            title="🏆 nanZQuiz Winner!",
            description=(
                f"Selamat {message.author.mention}!\n\n"
                f"`Berhasil menyelesaikan challenge!`\n\n"
                f"**Tipe:** {label}\n"
                f"**Jawaban:** {message.content}\n"
                f"**Reward:** {self.bot.current_reward}\n"
                f"**Total kemenangan:** {total_wins} 🎉\n\n"
                f"> Staff akan segera memberikan hadiahmu."
            ),
            color=discord.Color.gold()
        )
        winner_embed.set_thumbnail(url=message.author.display_avatar.url)
        winner_embed.set_footer(text="nanZ Server")
        winner_embed.timestamp = discord.utils.utcnow()
        await message.channel.send(embed=winner_embed)

        staff_channel = self.bot.get_channel(STAFF_CHANNEL_ID)
        staff_embed = discord.Embed(
            title="Reward Notice",
            description=(
                f"**Username:** {message.author}\n"
                f"**User ID:** {message.author.id}\n"
                f"**Tipe:** {label}\n"
                f"**Jawaban:** {message.content}\n"
                f"**Reward:** {self.bot.current_reward}\n\n"
                f"> Silakan transfer hadiah OwO."
            ),
            color=discord.Color.green()
        )
        staff_embed.set_thumbnail(url=message.author.display_avatar.url)
        staff_embed.set_footer(text="nanZ Server • Staff Notice")
        staff_embed.timestamp = discord.utils.utcnow()
        await staff_channel.send(embed=staff_embed)

        self.bot.current_answer         = None
        self.bot.current_challenge_type = None
        self.bot.current_reward         = None
        self.bot.current_quiz_message   = None
        self.bot.quiz_attempts          = {}

# ==========================================
# SETUP
# ==========================================

async def setup(bot):
    await bot.add_cog(NanZQuiz(bot))