import discord
from discord.ext import commands
import google.generativeai as genai
import json
from collections import defaultdict

# ==========================
# CONFIG
# ==========================

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

genai.configure(api_key=config["gemini_api_key"])

model = genai.GenerativeModel("gemini-1.5-flash")


class AI(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.chat_history = defaultdict(list)

    def system_prompt(self, member):

        return f"""
Kamu adalah NanZ AI.

Kamu merupakan AI resmi milik Discord Server NanZ.

Pemilik bot adalah Erlan Astra.

Aturan:

- Selalu jawab menggunakan Bahasa Indonesia kecuali diminta bahasa lain.
- Jangan pernah mengaku sebagai ChatGPT.
- Jangan pernah mengaku sebagai Gemini.
- Jika ditanya siapa kamu, jawab bahwa kamu adalah NanZ AI.
- Jawaban natural, santai, jelas, dan ramah.
- Jika tidak tahu jawabannya, katakan dengan jujur.
- Jangan membuat informasi palsu.
- Nama user yang sedang berbicara adalah {member.display_name}.
"""

    @commands.command(name="ai")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ai(self, ctx, *, prompt):

        if ctx.channel.id != config["ai_channel"]:
            return

        async with ctx.typing():

            history = self.chat_history[ctx.author.id]

            conversation = self.system_prompt(ctx.author)

            for q, a in history[-5:]:
                conversation += f"\nUser: {q}\nNanZ AI: {a}"

            conversation += f"\nUser: {prompt}\nNanZ AI:"

            try:

                response = model.generate_content(conversation)

                answer = response.text.strip()

                history.append((prompt, answer))

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
                    f"❌ Terjadi error.\n```{e}```",
                    mention_author=False
                )


async def setup(bot):
    await bot.add_cog(AI(bot))