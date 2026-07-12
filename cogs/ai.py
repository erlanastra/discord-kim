import discord
from discord.ext import commands
import google.generativeai as genai
import json
import asyncio

# ================= CONFIG =================

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

client = genai.Client(
    api_key=config["gemini_api_key"]
)

SYSTEM_PROMPT = """
Kamu adalah NanZ AI.

Kamu adalah AI resmi milik Discord Server NanZ.

Aturan yang HARUS dipatuhi:

- Selalu jawab menggunakan Bahasa Indonesia kecuali diminta bahasa lain.
- Jangan pernah mengaku sebagai ChatGPT.
- Jangan pernah mengaku sebagai Gemini.
- Jika ditanya siapa kamu, jawab bahwa kamu adalah NanZ AI.
- Ramah.
- Santai.
- Profesional.
- Tidak toxic.
- Tidak menggunakan emoji berlebihan.
- Jawaban jelas dan mudah dipahami.
- Jika tidak mengetahui sesuatu, katakan dengan jujur.
- Jika ditanya tentang server NanZ, jawab seolah kamu adalah AI resmi server tersebut.
- Maksimal sekitar 500 kata kecuali diminta lebih panjang.
"""


class AI(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # ================= AI COMMAND =================

    @commands.command(
        name="ai",
        aliases=["ask", "chat"]
    )
    @commands.cooldown(
        3,
        30,
        commands.BucketType.user
    )
    async def ai(self, ctx, *, prompt):

        if ctx.guild is None:

            embed = discord.Embed(
                title="❌ Tidak Bisa Digunakan",
                description="Command ini hanya bisa digunakan di dalam server.",
                color=discord.Color.red()
            )

            return await ctx.send(embed=embed)

        async with ctx.typing():

            try:

                response = await asyncio.to_thread(

                    client.models.generate_content,

                    model="gemini-2.5-flash",

                    contents=[
                        SYSTEM_PROMPT,
                        prompt
                    ]
                )

                text = response.text.strip()

                if not text:
                    text = "Maaf, aku tidak bisa memberikan jawaban."

                # Discord limit 2000 karakter
                if len(text) <= 1900:

                    embed = discord.Embed(
                        title="🤖 NanZ AI",
                        description=text,
                        color=discord.Color.blurple()
                    )

                    embed.set_footer(
                        text=f"Ditanya oleh {ctx.author.display_name}"
                    )

                    await ctx.reply(
                        embed=embed,
                        mention_author=False
                    )

                else:

                    for i in range(0, len(text), 1900):

                        part = text[i:i + 1900]

                        embed = discord.Embed(
                            title="🤖 NanZ AI",
                            description=part,
                            color=discord.Color.blurple()
                        )

                        if i == 0:

                            embed.set_footer(
                                text=f"Ditanya oleh {ctx.author.display_name}"
                            )

                        await ctx.reply(
                            embed=embed,
                            mention_author=False
                        )

            except Exception as e:

                embed = discord.Embed(
                    title="❌ Terjadi Kesalahan",
                    description=(
                        "Maaf, NanZ AI sedang mengalami gangguan.\n\n"
                        f"```{e}```"
                    ),
                    color=discord.Color.red()
                )

                await ctx.reply(
                    embed=embed,
                    mention_author=False
                )

    # ================= COOLDOWN =================

    @ai.error
    async def ai_error(self, ctx, error):

        if isinstance(error, commands.CommandOnCooldown):

            embed = discord.Embed(
                title="⏳ Tunggu Sebentar",
                description=(
                    f"Kamu bisa menggunakan command ini lagi dalam "
                    f"**{error.retry_after:.1f} detik**."
                ),
                color=discord.Color.orange()
            )

            await ctx.send(embed=embed)


# ================= SETUP =================

async def setup(bot):

    await bot.add_cog(
        AI(bot)
    )