import discord
from discord.ext import commands
import aiohttp
import json
import logging
from collections import defaultdict


# Load config
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)


API_KEY = config["gemini_api_key"]
AI_CHANNEL = config["ai_channel"]


# Gemini Model
GEMINI_MODEL = "gemini-3.5-flash"

URL = (
    f"https://generativelanguage.googleapis.com/v1beta/"
    f"models/{GEMINI_MODEL}:generateContent?key={API_KEY}"
)


logging.basicConfig(level=logging.INFO)

logging.info("========== GEMINI DEBUG ==========")
logging.info(f"MODEL = {GEMINI_MODEL}")
logging.info(f"URL = {URL}")


class AI(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.chat_history = defaultdict(list)
        self.session = None


    async def cog_load(self):
        self.session = aiohttp.ClientSession()


    async def cog_unload(self):
        if self.session:
            await self.session.close()


    def system_prompt(self, member):

        return f"""
Kamu adalah NanZ AI.

NanZ AI merupakan AI resmi milik Discord nanZ Server.

========================
INFORMASI RESMI nanZ SERVER
========================

Nama Server:
nanZ Server

Tanggal Berdiri:
18 Agustus 2025

Tema Server:
School Community / Sekolahan

Deskripsi:
nanZ Server adalah komunitas Discord dengan konsep
sekolah virtual. Server ini dibuat sebagai tempat
berkumpul, berteman, berdiskusi, bermain, dan membuat
berbagai kegiatan komunitas.

Pemilik Server:
Kim (Owner / Guru Besar)

Pembuat Bot nanZ:
Erlan / Tom (Developer/Mod DC)

========================
STRUKTUR STAFF
========================

- Guru Besar (Owner)
- Moderator
- Pembina OSIS
- Ketua OSIS
- Wakil Ketua OSIS
- OSIS

========================
<<<<<<< HEAD
KOMUNITAS nanZ
========================

Komunitas yang terbentuk:

- EternanZ

EternanZ merupakan komunitas dalam nanZ Server
yang menjadi tempat berkumpul dan membangun hubungan
antar member melalui aktivitas bersama.

========================
=======
>>>>>>> 22461ec05ecab689e00b04e0474ca5f25f67a333
EVENT nanZ SERVER
========================

Event yang tersedia:

- Girls Corner
  Voice khusus siswi untuk berbagi cerita,
  berbincang, dan membangun ruang nyaman.

- Nobar
  Event menonton film bersama komunitas.

- Podcast
  Acara berbincang dan sharing bersama anggota
  maupun tamu komunitas.

- Riddle
  Event teka-teki dan permainan logika.

- nanZSeratus
  Event komunitas dengan konsep tantangan/permainan
  bersama member.

========================
GAYA JAWABAN
========================

- Jangan pernah mengaku sebagai ChatGPT.
- Jangan pernah mengaku sebagai Gemini.
<<<<<<< HEAD
- Jika ditanya siapa kamu, jawab bahwa kamu adalah NanZ AI.
=======
- Jika ditanya siapa kamu, jawab bahwa kamu adalah nanZ AI.
>>>>>>> 22461ec05ecab689e00b04e0474ca5f25f67a333
- Gunakan Bahasa Indonesia.
- Jawab santai seperti anggota komunitas.
- Jika ditanya tentang nanZ Server, gunakan informasi resmi ini.
- Jangan membuat informasi server yang tidak diketahui.

User yang berbicara:
{member.display_name}
"""


    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return


        is_ai_channel = message.channel.id == AI_CHANNEL
        is_mention = self.bot.user in message.mentions


<<<<<<< HEAD
        if not is_ai_channel: if not is_mention:
            return
=======
        if not is_ai_channel:
            if not is_mention:
                return
>>>>>>> 22461ec05ecab689e00b04e0474ca5f25f67a333


        prompt = message.content


        if is_mention:
            prompt = prompt.replace(
                f"<@{self.bot.user.id}>",
                ""
            ).strip()


        if not prompt:
            return


        async with message.channel.typing():

            history = self.chat_history[message.author.id]


            conversation = self.system_prompt(
                message.author
            )


            for q, a in history[-5:]:

                conversation += (
                    f"\nUser: {q}"
                    f"\nAI: {a}"
                )


            conversation += (
                f"\nUser: {prompt}"
                f"\nAI:"
            )


            payload = {

                "contents": [
                    {
                        "parts": [
                            {
                                "text": conversation
                            }
                        ]
                    }
                ]

            }


            try:

                async with self.session.post(
                    URL,
                    json=payload
                ) as resp:


                    data = await resp.json()


                    # HANDLE GEMINI LIMIT / QUOTA
                    if resp.status == 429:

                        await message.reply(
<<<<<<< HEAD
                            "⚠️ **NanZ AI sedang mencapai batas penggunaan.**\n"
=======
                            "⚠️ **NnanZ AI sedang mencapai batas penggunaan.**\n"
>>>>>>> 22461ec05ecab689e00b04e0474ca5f25f67a333
                            "Silakan coba lagi beberapa saat nanti.",
                            mention_author=False
                        )

                        return


                    if resp.status != 200:

                        await message.reply(
<<<<<<< HEAD
                            f"❌ Gemini Error\n```{data}```",
=======
                            f"Coba lagi, server lagi penuh",
>>>>>>> 22461ec05ecab689e00b04e0474ca5f25f67a333
                            mention_author=False
                        )

                        return


                    answer = (
                        data["candidates"][0]
                        ["content"]
                        ["parts"][0]
                        ["text"]
                    )


                history.append(
                    (
                        prompt,
                        answer
                    )
                )


                if len(history) > 10:
                    history.pop(0)



                embed = discord.Embed(
                    title="🤖 nanZ AI",
                    description=answer[:4000],
                    color=0x5865F2
                )


                embed.set_footer(
                    text=f"Diminta oleh {message.author.display_name}"
                )


                await message.reply(
                    embed=embed,
                    mention_author=False
                )


            except Exception as e:

                await message.reply(
                    f"❌ Error\n```{e}```",
                    mention_author=False
                )



async def setup(bot):
    await bot.add_cog(AI(bot))
