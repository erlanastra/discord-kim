import discord
from discord.ext import commands
import asyncio
import yt_dlp
from discord import Embed
import requests
from bs4 import BeautifulSoup
import re

# Ganti path FFmpeg sesuai lokasi di PC kamu
FFMPEG_PATH = r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"

# Konfigurasi yt-dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'quiet': True,
    'extract_flat': 'in_playlist',
    'noplaylist': True,
    'js_runtime': 'node'
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
    'executable': FFMPEG_PATH
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class Music(commands.Cog):
    """Music Cog final stabil: queue, leave, lyrics"""

    def __init__(self, bot):
        self.bot = bot
        self.guild_queues = {}  # {guild_id: [{'title': str, 'url': str}]}

    async def ensure_voice(self, ctx):
        """Pastikan user di VC dan bot join VC"""
        if ctx.author.voice is None:
            await ctx.send("⚠️ Kamu harus berada di voice channel dulu!")
            return False

        voice_channel = ctx.author.voice.channel
        vc = ctx.guild.voice_client

        if vc is None:
            await voice_channel.connect()
        elif vc.channel != voice_channel:
            await vc.move_to(voice_channel)

        await asyncio.sleep(0.5)
        return True

    async def _play_next(self, guild):
        """Main function untuk play lagu berikutnya"""
        guild_id = guild.id
        vc = guild.voice_client
        if not vc:
            return

        if guild_id not in self.guild_queues or len(self.guild_queues[guild_id]) == 0:
            return

        song = self.guild_queues[guild_id].pop(0)
        source = discord.FFmpegPCMAudio(song['url'], **ffmpeg_options)
        vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(self._play_next(guild), self.bot.loop))

        if guild.text_channels:
            channel = guild.text_channels[0]
            embed = Embed(title="▶️ Now Playing", description=song['title'], color=discord.Color.blurple())
            await channel.send(embed=embed)

    @commands.command(name="play")
    async def play(self, ctx, *, query: str):
        """Play lagu dari link / search query (YouTube non-DRM)"""
        if not await self.ensure_voice(ctx):
            return

        guild_id = ctx.guild.id
        if guild_id not in self.guild_queues:
            self.guild_queues[guild_id] = []

        try:
            info = ytdl.extract_info(query, download=False)
            if 'entries' in info:
                info = info['entries'][0]
        except Exception as e:
            info = ytdl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]

        url2 = info['url']
        title = info.get('title', 'Unknown')

        self.guild_queues[guild_id].append({'title': title, 'url': url2})
        await ctx.send(embed=Embed(title="🎵 Ditambahkan ke queue", description=title, color=discord.Color.green()))

        vc = ctx.guild.voice_client
        if not vc.is_playing():
            await self._play_next(ctx.guild)

    # ===================== CONTROL =====================
    @commands.command(name="pause")
    async def pause(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send("⏸ Paused")
        else:
            await ctx.send("⚠️ Tidak sedang memutar lagu")

    @commands.command(name="resume")
    async def resume(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send("▶️ Resumed")
        else:
            await ctx.send("⚠️ Tidak sedang pause")

    @commands.command(name="stop")
    async def stop(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            self.guild_queues.pop(ctx.guild.id, None)
            await ctx.send("⏹ Stopped")
        else:
            await ctx.send("⚠️ Tidak sedang memutar lagu")

    @commands.command(name="skip")
    async def skip(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send("⏭ Skipped")
        else:
            await ctx.send("⚠️ Tidak sedang memutar lagu")

    @commands.command(name="queue")
    async def queue_list(self, ctx):
        guild_id = ctx.guild.id
        if guild_id not in self.guild_queues or len(self.guild_queues[guild_id]) == 0:
            await ctx.send("📭 Queue kosong")
        else:
            desc = "\n".join([f"{i+1}. {s['title']}" for i, s in enumerate(self.guild_queues[guild_id])])
            await ctx.send(embed=Embed(title="📜 Queue", description=desc, color=discord.Color.blue()))

    # ===================== LEAVE =====================
    @commands.command(name="leave")
    async def leave(self, ctx):
        vc = ctx.guild.voice_client
        if vc:
            await vc.disconnect()
            self.guild_queues.pop(ctx.guild.id, None)
            await ctx.send("👋 Bot keluar dari voice channel dan reset queue")
        else:
            await ctx.send("⚠️ Bot tidak sedang join VC")

    # ===================== LYRICS =====================
    @commands.command(name="lyrics")
    async def lyrics(self, ctx, *, query: str):
        """Ambil lirik dari Genius (scraping)"""
        try:
            search_url = f"https://genius.com/search?q={query.replace(' ', '+')}"
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(search_url, headers=headers)
            soup = BeautifulSoup(r.text, "html.parser")
            first_result = soup.find("a", class_="mini_card")
            if not first_result:
                await ctx.send("⚠️ Lirik tidak ditemukan")
                return
            song_url = first_result['href']
            r2 = requests.get(song_url, headers=headers)
            soup2 = BeautifulSoup(r2.text, "html.parser")
            lyrics_div = soup2.find("div", class_="lyrics") or soup2.find("div", class_=re.compile("Lyrics__Root"))
            if not lyrics_div:
                await ctx.send("⚠️ Lirik tidak ditemukan")
                return
            lyrics_text = lyrics_div.get_text(separator="\n").strip()
            if len(lyrics_text) > 1900:
                lyrics_text = lyrics_text[:1900] + "..."
            await ctx.send(embed=Embed(title=f"Lyrics: {query}", description=lyrics_text, color=discord.Color.orange()))
        except Exception as e:
            await ctx.send(f"⚠️ Error mencari lirik: {e}")

# Setup cog
async def setup(bot):
    await bot.add_cog(Music(bot))
