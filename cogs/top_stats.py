import discord
from discord.ext import commands
import json
import os
from datetime import datetime, timezone, timedelta

class TopStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_file = "top_stats.json"
        self.stats_data = self.load_db()

    def load_db(self):
        if not os.path.exists(self.db_file):
            return {}
        try:
            with open(self.db_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[STATS] Gagal memuat database: {e}")
            return {}

    def save_db(self):
        try:
            with open(self.db_file, "w", encoding="utf-8") as f:
                json.dump(self.stats_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[STATS] Gagal menyimpan database: {e}")

    def get_wib_today(self):
        utc_now = datetime.now(timezone.utc)
        wib_time = utc_now.astimezone(timezone(timedelta(hours=7)))
        return wib_time.strftime("%Y-%m-%d")

    # ==========================================
    # LISTENER: DETEKSI CHAT TEKS (Akumulasi Permanen)
    # ==========================================
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        date_str = self.get_wib_today()

        if guild_id not in self.stats_data:
            self.stats_data[guild_id] = {}
        if date_str not in self.stats_data[guild_id]:
            self.stats_data[guild_id][date_str] = {"chat": {}, "voice": {}}

        chat_counts = self.stats_data[guild_id][date_str]["chat"]
        chat_counts[user_id] = chat_counts.get(user_id, 0) + 1
        self.save_db()

    # ==========================================
    # LISTENER: DETEKSI VOICE CHANNEL
    # ==========================================
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or not member.guild:
            return

        guild_id = str(member.guild.id)
        user_id = str(member.id)
        date_str = self.get_wib_today()

        if guild_id not in self.stats_data:
            self.stats_data[guild_id] = {}
        if date_str not in self.stats_data[guild_id]:
            self.stats_data[guild_id][date_str] = {"chat": {}, "voice": {}}

        if before.channel is None and after.channel is not None:
            voice_counts = self.stats_data[guild_id][date_str]["voice"]
            voice_counts[user_id] = voice_counts.get(user_id, 0) + 1
            self.save_db()

    # ==========================================
    # COMMAND 1: TOP CHAT & VOICE SEMUA
    # ==========================================
    @commands.command(name="topstat", aliases=["topchat", "topvoice"])
    async def top_stat(self, ctx):
        guild_id = str(ctx.guild.id)
        date_str = self.get_wib_today()

        if guild_id not in self.stats_data or date_str not in self.stats_data[guild_id]:
            await ctx.reply("📊 Belum ada data statistik aktivitas hari ini.")
            return

        data = self.stats_data[guild_id][date_str]
        sorted_chat = sorted(data.get("chat", {}).items(), key=lambda x: x[1], reverse=True)[:5]
        sorted_voice = sorted(data.get("voice", {}).items(), key=lambda x: x[1], reverse=True)[:5]

        embed = discord.Embed(
            title="🏆 Top Statistik Server nanZ (Semua Member)",
            description=f"Tanggal: **{date_str} (WIB)**",
            color=discord.Color.gold()
        )

        chat_text = "".join([f"{i}. <@{uid}> — **{cnt}** pesan\n" for i, (uid, cnt) in enumerate(sorted_chat, 1)])
        voice_text = "".join([f"{i}. <@{uid}> — **{cnt}** aktivitas\n" for i, (uid, cnt) in enumerate(sorted_voice, 1)])

        embed.add_field(name="💬 Top Chatting", value=chat_text or "*Belum ada data*", inline=False)
        embed.add_field(name="🔊 Top Voice Activity", value=voice_text or "*Belum ada data*", inline=False)
        await ctx.send(embed=embed)

    # ==========================================
    # COMMAND 2: TOP STATS BERDASARKAN ROLE
    # Penggunaan: !toprole @RoleName
    # ==========================================
    @commands.command(name="toprole")
    async def top_role(self, ctx, target_role: discord.Role = None):
        if not target_role:
            await ctx.reply("⚠️ Harap tag role yang ingin dicek! Contoh: `!toprole @OSIS`")
            return

        guild_id = str(ctx.guild.id)
        date_str = self.get_wib_today()

        if guild_id not in self.stats_data or date_str not in self.stats_data[guild_id]:
            await ctx.reply(f"📊 Belum ada data statistik untuk role **{target_role.name}** hari ini.")
            return

        data = self.stats_data[guild_id][date_str]
        
        # Filter data hanya untuk member yang memiliki role tersebut
        filtered_chat = {uid: cnt for uid, cnt in data.get("chat", {}).items() if ctx.guild.get_member(int(uid)) and target_role in ctx.guild.get_member(int(uid)).roles}
        filtered_voice = {uid: cnt for uid, cnt in data.get("voice", {}).items() if ctx.guild.get_member(int(uid)) and target_role in ctx.guild.get_member(int(uid)).roles}

        sorted_chat = sorted(filtered_chat.items(), key=lambda x: x[1], reverse=True)[:5]
        sorted_voice = sorted(filtered_voice.items(), key=lambda x: x[1], reverse=True)[:5]

        embed = discord.Embed(
            title=f"🛡️ Top Statistik Role: {target_role.name}",
            description=f"Tanggal: **{date_str} (WIB)**",
            color=target_role.color
        )

        chat_text = "".join([f"{i}. <@{uid}> — **{cnt}** pesan\n" for i, (uid, cnt) in enumerate(sorted_chat, 1)])
        voice_text = "".join([f"{i}. <@{uid}> — **{cnt}** aktivitas\n" for i, (uid, cnt) in enumerate(sorted_voice, 1)])

        embed.add_field(name="💬 Top Chat (Role Ini)", value=chat_text or "*Tidak ada data*", inline=False)
        embed.add_field(name="🔊 Top Voice (Role Ini)", value=voice_text or "*Tidak ada data*", inline=False)
        await ctx.send(embed=embed)

    # ==========================================
    # COMMAND 3: CEK STATS MEMBER YANG DI-TAG
    # Penggunaan: !cekuser @Member
    # ==========================================
    @commands.command(name="cekuser", aliases=["statsuser"])
    async def cek_user(self, ctx, member: discord.Member = None):
        if not member:
            member = ctx.author # Default ke pengirim jika tidak tag siapa pun

        guild_id = str(ctx.guild.id)
        date_str = self.get_wib_today()
        user_id = str(member.id)

        chat_count = 0
        voice_count = 0

        if guild_id in self.stats_data and date_str in self.stats_data[guild_id]:
            day_data = self.stats_data[guild_id][date_str]
            chat_count = day_data.get("chat", {}).get(user_id, 0)
            voice_count = day_data.get("voice", {}).get(user_id, 0)

        embed = discord.Embed(
            title=f"📊 Statistik Aktivitas: {member.display_name}",
            color=member.color
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="💬 Total Chat Hari Ini", value=f"**{chat_count}** pesan", inline=True)
        embed.add_field(name="🔊 Total Voice Hari Ini", value=f"**{voice_count}** aktivitas", inline=True)
        embed.set_footer(text=f"Tanggal: {date_str} WIB")

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(TopStats(bot))