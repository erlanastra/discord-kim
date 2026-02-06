import discord
from discord.ext import commands
import asyncio
import yt_dlp
from discord import Embed
import requests
from bs4 import BeautifulSoup
import re

FFMPEG_PATH = r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"

ytdl_format_options = {
    'format': 'bestaudio/best',
    'quiet': True,
    'noplaylist': True,
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
    'executable': FFMPEG_PATH
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.current = {}
        self.repeat = {}

    # ===================== VOICE =====================
    async def ensure_voice(self, ctx):
        if not ctx.author.voice:
            await ctx.send("⚠️ Kamu harus di voice channel")
            return False

        vc = ctx.guild.voice_client
        channel = ctx.author.voice.channel

        if not vc:
            await channel.connect()
        elif vc.channel != channel:
            await vc.move_to(channel)

        return True

    # ===================== VC STATUS =====================
    async def set_vc_status(self, ctx, text=None):
        vc = ctx.guild.voice_client
        if vc and vc.channel:
            try:
                await vc.channel.edit(status=text)
            except:
                pass

    # ===================== PLAYER =====================
    async def play_next(self, guild, ctx):
        gid = guild.id
        vc = guild.voice_client

        if not vc:
            return

        if self.repeat.get(gid) and gid in self.current:
            song = self.current[gid]
        else:
            if not self.queues.get(gid):
                self.current.pop(gid, None)
                await self.set_vc_status(ctx, None)
                await self.bot.change_presence(activity=None)
                return

            song = self.queues[gid].pop(0)
            self.current[gid] = song

        source = discord.FFmpegPCMAudio(song['url'], **ffmpeg_options)

        vc.play(
            source,
            after=lambda e: asyncio.run_coroutine_threadsafe(
                self.play_next(guild, ctx),
                self.bot.loop
            )
        )

        await self.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=song['title']
            )
        )

        await self.set_vc_status(ctx, f"🎶 {song['title']}")

        await ctx.send(
            embed=Embed(
                title="▶️ Now Playing",
                description=f"**{song['title']}**",
                color=discord.Color.blurple()
            )
        )

    # ===================== PLAY =====================
    @commands.command()
    async def play(self, ctx, *, query):
        if not await self.ensure_voice(ctx):
            return

        gid = ctx.guild.id
        self.queues.setdefault(gid, [])

        try:
            info = ytdl.extract_info(query, download=False)
            if 'entries' in info:
                info = info['entries'][0]
        except:
            info = ytdl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]

        song = {
            "title": info.get("title", "Unknown"),
            "url": info["url"]
        }

        self.queues[gid].append(song)

        await ctx.send(
            embed=Embed(
                title="🎵 Ditambahkan ke Queue",
                description=f"**{song['title']}**",
                color=discord.Color.green()
            )
        )

        vc = ctx.guild.voice_client
        if not vc.is_playing():
            await self.play_next(ctx.guild, ctx)

    # ===================== CONTROLS =====================
    @commands.command()
    async def pause(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send("⏸ Paused")

    @commands.command()
    async def resume(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send("▶️ Resumed")

    @commands.command()
    async def skip(self, ctx):
        vc = ctx.guild.voice_client
        if vc:
            vc.stop()
            await ctx.send("⏭ Skipped")

    @commands.command()
    async def stop(self, ctx):
        vc = ctx.guild.voice_client
        if vc:
            vc.stop()
            self.queues.pop(ctx.guild.id, None)
            self.current.pop(ctx.guild.id, None)
            self.repeat.pop(ctx.guild.id, None)
            await self.set_vc_status(ctx, None)
            await self.bot.change_presence(activity=None)
            await ctx.send("⏹ Stopped")

    @commands.command()
    async def leave(self, ctx):
        vc = ctx.guild.voice_client
        if vc:
            await self.set_vc_status(ctx, None)
            await vc.disconnect()
            await self.bot.change_presence(activity=None)
            await ctx.send("👋 Bot keluar VC")

    # ===================== QUEUE =====================
    @commands.command()
    async def queue(self, ctx):
        q = self.queues.get(ctx.guild.id)
        if not q:
            await ctx.send("📭 Queue kosong")
            return

        text = "\n".join(f"{i+1}. {s['title']}" for i, s in enumerate(q))
        await ctx.send(embed=Embed(title="📜 Queue", description=text))

    # ===================== REPEAT =====================
    @commands.command()
    async def repeat(self, ctx):
        gid = ctx.guild.id
        self.repeat[gid] = not self.repeat.get(gid, False)
        await ctx.send(f"Repeat mode: {'🔁 ON' if self.repeat[gid] else '⏹ OFF'}")

    # ===================== LYRICS =====================
    @commands.command()
    async def lyrics(self, ctx, *, query):
        try:
            url = f"https://genius.com/search?q={query.replace(' ', '+')}"
            headers = {"User-Agent": "Mozilla/5.0"}
            soup = BeautifulSoup(requests.get(url, headers=headers).text, "html.parser")
            link = soup.find("a", class_="mini_card")["href"]

            page = BeautifulSoup(requests.get(link, headers=headers).text, "html.parser")
            lyrics = page.find("div", class_=re.compile("Lyrics__Root")).get_text("\n")

            await ctx.send(
                embed=Embed(
                    title=f"🎤 Lyrics — {query}",
                    description=lyrics[:1900]
                )
            )
        except:
            await ctx.send("⚠️ Lirik tidak ditemukan")

# ===================== SETUP =====================
async def setup(bot):
    await bot.add_cog(Music(bot))
