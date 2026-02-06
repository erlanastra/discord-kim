import discord
from discord.ext import commands
import asyncio
import yt_dlp
from discord import Embed
import time

# ================= CONFIG =================

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

YTDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True,
    "default_search": "ytsearch",
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)

# ================= COG =================

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}
        self.current = {}
        self.repeat = {}
        self.msg = {}
        self.start = {}

    async def ensure_voice(self, ctx):
        if not ctx.author.voice:
            await ctx.send("⚠️ Kamu harus masuk voice channel dulu.")
            return False

        vc = ctx.guild.voice_client
        channel = ctx.author.voice.channel

        if not vc:
            await channel.connect()
        elif vc.channel != channel:
            await vc.move_to(channel)

        return True

    async def progress_loop(self, guild):
        gid = guild.id
        while gid in self.current:
            vc = guild.voice_client
            if not vc or not vc.is_playing():
                break

            elapsed = int(time.time() - self.start[gid])
            dur = self.current[gid]["duration"]
            txt = f"⏱ {elapsed//60:02}:{elapsed%60:02} / {dur//60:02}:{dur%60:02}"

            try:
                await self.msg[gid].edit(embed=self.build_embed(self.current[gid], txt))
            except:
                pass

            await asyncio.sleep(5)

    def build_embed(self, song, progress=""):
        return Embed(
            title="🎶 Now Playing",
            description=f"**{song['title']}**\n{progress}",
            color=discord.Color.blurple()
        )

    async def play_next(self, guild, ctx):
        gid = guild.id
        vc = guild.voice_client

        if self.repeat.get(gid) and gid in self.current:
            song = self.current[gid]
        else:
            if not self.queue.get(gid):
                self.current.pop(gid, None)
                return
            song = self.queue[gid].pop(0)
            self.current[gid] = song

        self.start[gid] = time.time()

        vc.play(
            discord.FFmpegPCMAudio(song["url"], **FFMPEG_OPTS),
            after=lambda e: asyncio.run_coroutine_threadsafe(
                self.play_next(guild, ctx), self.bot.loop
            )
        )

        embed = self.build_embed(song)
        if gid in self.msg:
            await self.msg[gid].edit(embed=embed)
        else:
            self.msg[gid] = await ctx.send(embed=embed)

        self.bot.loop.create_task(self.progress_loop(guild))

    # ================= COMMANDS =================

    @commands.command()
    async def play(self, ctx, *, query: str):
        if not await self.ensure_voice(ctx):
            return

        gid = ctx.guild.id
        self.queue.setdefault(gid, [])

        info = ytdl.extract_info(query, download=False)
        if "entries" in info:
            info = info["entries"][0]

        song = {
            "title": info["title"],
            "url": info["url"],
            "duration": info.get("duration", 0)
        }

        self.queue[gid].append(song)
        await ctx.send(f"🎵 **{song['title']}** ditambahkan ke queue")

        vc = ctx.guild.voice_client
        if not vc.is_playing():
            await self.play_next(ctx.guild, ctx)

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
    async def queue(self, ctx):
        q = self.queue.get(ctx.guild.id)
        if not q:
            await ctx.send("📭 Queue kosong")
            return

        text = "\n".join(f"{i+1}. {s['title']}" for i, s in enumerate(q))
        await ctx.send(embed=Embed(title="📜 Queue", description=text))

    @commands.command()
    async def repeat(self, ctx):
        gid = ctx.guild.id
        self.repeat[gid] = not self.repeat.get(gid, False)
        await ctx.send(f"🔁 Repeat {'ON' if self.repeat[gid] else 'OFF'}")

    @commands.command()
    async def stop(self, ctx):
        vc = ctx.guild.voice_client
        if vc:
            vc.stop()
            self.queue.pop(ctx.guild.id, None)
            self.current.pop(ctx.guild.id, None)
            await ctx.send("⏹ Stopped")

def setup(bot):
    bot.add_cog(Music(bot))
