import discord
from discord.ext import commands
import aiohttp
import json
from collections import defaultdict


# Load config
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)


API_KEY = config["gemini_api_key"]
AI_CHANNEL = config["ai_channel"]

# Model Gemini
GEMINI_MODEL = config.get(
    "gemini_model",
    "gemini-2.0-flash"
)

URL = (
    f"https://generativelanguage.googleapis.com/v1beta/"
    f"models/{GEMINI_MODEL}:generateContent?key={API_KEY}"
)


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

Pemilik bot adalah Erlan Astra.

Aturan:
- Jangan pernah mengaku sebagai ChatGPT.
- Jangan pernah mengaku sebagai Gemini.
- Jika ditanya siapa kamu, jawab bahwa kamu adalah NanZ AI.
- Gunakan Bahasa Indonesia kecuali diminta bahasa lain.
- Jawaban santai, natural, dan tidak terlalu formal.
- Boleh bercanda jika situasi mendukung.
- Jawaban harus jelas dan realistis.
- Jika tidak tahu, katakan tidak tahu.

User yang berbicara:
{member.display_name}
"""


    @commands.command(name="ai")
    @commands.cooldown(
        1,
        5,
        commands.BucketType.user
    )
    async def ai(self, ctx, *, prompt):

        if ctx.channel.id != AI_CHANNEL:
            return


        async with ctx.typing():

            history = self.chat_history[ctx.author.id]

            conversation = self.system_prompt(ctx.author)


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


                    if resp.status != 200:

                        await ctx.reply(
                            f"❌ Gemini Error\n```{data}```",
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
                    title="🤖 NanZ AI",
                    description=answer[:4000],
                    color=0x5865F2
                )


                embed.set_footer(
                    text=f"Diminta oleh {ctx.author.display_name}"
                )


                await ctx.reply(
                    embed=embed,
                    mention_author=False
                )


            except Exception as e:

                await ctx.reply(
                    f"❌ Error\n```{e}```",
                    mention_author=False
                )



async def setup(bot):
    await bot.add_cog(AI(bot))