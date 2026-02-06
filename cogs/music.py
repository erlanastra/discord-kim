import discord
from discord.ext import commands
import asyncio
import yt_dlp
from discord import Embed
import time

# ================= CONFIG =================

YTDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True,
}

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)

# ================= MUSIC COG =================

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}
        self.current = {}
        self.repeat = {}
        self.now_msg = {}
        self.start_time = {}

    # ---------- VOICE ----------

    async def ensure_voice(self, ctx):
        if not ctx.author.voice:
            await ctx.send("⚠️ **Masuk voice channel dulu ya~**")
            return False

        vc = ctx.guild.voice_client
        channel = ctx.author.voice.channel

        if not vc:
            await channel.connect()
        elif vc.channel != channel:
            await vc.move_to(channel)

        return True

    async def set_vc_status(self, guild, text=None):
        vc = guild.voice_client
        if vc and vc.channel:
            try:
                await vc.channel.edit(status=text)
            except:
                pass

    # ---------- PLAYER CORE ----------

    async def play_next(self, guild, ctx):
        gid = guild.id
        vc = guild.voice_client

        if self.repeat.get(gid) and gid in self.current:
            song = self.current[gid]
        else:
            if not self.queue.get(gid):
                self.current.pop(gid, None)
                await self.set_vc_status(guild, None)
                return
            song = self.queue[gid].pop(0)
            self.current[gid] = song

        self.start_time[gid] = time.time()

        vc.play(
            discord.FFmpegPCMAudio(song["url"], **FFMPEG_OPTS),
            after=lambda e: asyncio.run_coroutine_threadsafe(
                self.play_next(guild, ctx), self.bot.loop
            )
        )

        await self.set_vc_status(guild, f"🎶 {song['title']}")

        embed = self.now_playing_embed(song)
        if gid in self.now_msg:
            await self.now_msg[gid].edit(embed=embed)
        else:
            self.now_msg[gid] = await ctx.send(embed=embed)

        self.bot.loop.create_task(self.progress_loop(guild))

    async def progress_loop(self, guild):
        gid = guild.id
        while gid in self.current:
            vc = guild.voice_client
            if not vc or not vc.is_playing():
                break

            elapsed = int(time.time() - self.start_time[gid])
            dur = self.current[gid]["duration"]
            progress = f"`{elapsed//60:02}:{elapsed%60:02} / {dur//60:02}:{dur%60:02}`"

            try:
                await self.now_msg[gid].edit(
                    embed=self.now_playing_embed(self.current[gid], progress)
                )
            except:
                pass

            await asyncio.sleep(5)

    # ---------- EMBEDS ----------

    def now_playing_embed(self, song, progress=""):
        return Embed(
            title="🎧 Now Playing",
            description=(
                f"**{song['title']}**\n\n"
                f"{progress if progress else '▶️ Sedang diputar...'}"
            ),
            color=discord.Color.blurple()
        )

    # ================= COMMANDS =================

    @commands.hybrid_command(description="Putar lagu dari YouTube")
    async def play(self, ctx, *, query: str):
        if not await self.ensure_voice(ctx):
            return

        gid = ctx.guild.id
        self.queue.setdefault(gid, [])

        info = ytdl.extract_info(f"ytsearch:{query}", download=False)["entries"][0]

        song = {
            "title": info["title"],
            "url": info["url"],
            "duration": info.get("duration", 0),
        }

        self.queue[gid].append(song)

        await ctx.send(
            embed=Embed(
                title="📥 Ditambahkan ke Queue",
                description=f"**{song['title']}**",
                color=discord.Color.green(),
            )
        )

        vc = ctx.guild.voice_client
        if not vc.is_playing():
            await self.play_next(ctx.guild, ctx)

    @commands.hybrid_command()
    async def pause(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send("⏸ **Music di-pause**")

    @commands.hybrid_command()
    async def resume(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send("▶️ **Lanjut lagi~**")

    @commands.hybrid_command()
    async def skip(self, ctx):
        vc = ctx.guild.voice_client
        if vc:
            vc.stop()
            await ctx.send("⏭ **Lagu dilewati**")

    @commands.hybrid_command()
    async def queue(self, ctx):
        q = self.queue.get(ctx.guild.id)
        if not q:
            await ctx.send("📭 **Queue masih kosong**")
            return

        text = "\n".join(f"`{i+1}.` {s['title']}" for i, s in enumerate(q))
        await ctx.send(
            embed=Embed(title="📜 Music Queue", description=text, color=discord.Color.blue())
        )

    @commands.hybrid_command()
    async def repeat(self, ctx):
        gid = ctx.guild.id
        self.repeat[gid] = not self.repeat.get(gid, False)
        await ctx.send(
            f"🔁 **Repeat {'ON' if self.repeat[gid] else 'OFF'}**"
        )

    @commands.hybrid_command()
    async def stop(self, ctx):
        vc = ctx.guild.voice_client
        if vc:
            vc.stop()
            self.queue.pop(ctx.guild.id, None)
            self.current.pop(ctx.guild.id, None)
            await self.set_vc_status(ctx.guild, None)
            await ctx.send("⏹ **Music dihentikan & queue dibersihkan**")

# ================= SETUP =================

async def setup(bot):
    await bot.add_cog(Music(bot))
