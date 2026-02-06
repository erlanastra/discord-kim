import discord
from discord.ext import commands
import requests
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY")
HF_MODEL_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct"

class FreeAI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("GPT COG READY")

    def duckduckgo_search(self, query):
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_redirect": 1,
            "no_html": 1
        }
        try:
            r = requests.get(url, params=params, timeout=10).json()
            results = []

            if r.get("AbstractText"):
                results.append(r["AbstractText"])

            for item in r.get("RelatedTopics", [])[:3]:
                if isinstance(item, dict) and "Text" in item:
                    results.append(item["Text"])

            return "\n".join(results) if results else "Tidak ada hasil web."
        except:
            return "Gagal mengambil data web."

    def call_hf(self, prompt):
        headers = {"Authorization": f"Bearer {HF_API_KEY}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 200,
                "temperature": 0.7,
                "return_full_text": False
            }
        }
        r = requests.post(HF_MODEL_URL, headers=headers, json=payload, timeout=30)
        return r.json()

    @commands.command(name="gpt")
    async def gpt(self, ctx, *, question: str = None):
        if not question:
            await ctx.send("❌ Contoh: `!gpt apa itu AI`")
            return

        await ctx.trigger_typing()

        web = self.duckduckgo_search(question)

        prompt = (
            "Kamu adalah AI assistant yang ramah dan menjawab seperti manusia.\n\n"
            f"Informasi Web:\n{web}\n\n"
            f"Pertanyaan:\n{question}\n\n"
            "Jawaban:"
        )

        try:
            # 🔥 JALANKAN REQUEST DI THREAD
            data = await asyncio.to_thread(self.call_hf, prompt)

            if isinstance(data, list) and "generated_text" in data[0]:
                answer = data[0]["generated_text"].strip()
            else:
                print("HF RESPONSE:", data)
                answer = "AI belum bisa menjawab sekarang 😅"

        except Exception as e:
            print("HF ERROR:", e)
            answer = "Maaf, AI lagi sibuk 😅"

        embed = discord.Embed(
            title="🤖 Free Online AI",
            description=answer,
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(FreeAI(bot))
