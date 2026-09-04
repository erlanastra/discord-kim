import discord
from discord.ext import commands
import json
import os
from datetime import datetime, timezone, timedelta

class TopStatsPaginator(discord.ui.View):
    def __init__(self, chat_list, voice_list, title_info, color):
        super().__init__(timeout=180)
        self.chat_list = chat_list
        self.voice_list = voice_list
        self.title_info = title_info
        self.color = color
        
        self.current_page = 0
        self.items_per_page = 5
        
        self.max_chat_pages = max(1, (len(self.chat_list) + self.items_per_page - 1) // self.items_per_page)
        self.max_voice_pages = max(1, (len(self.voice_list) + self.items_per_page - 1) // self.items_per_page)
        self.max_page = max(self.max_chat_pages, self.max_voice_pages)
        
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_page - 1

    def create_embed(self):
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page

        current_chat = self.chat_list[start_idx:end_idx]
        current_voice = self.voice_list[start_idx:end_idx]

        embed = discord.Embed(
            title="🏆 Top Statistik Server nanZ",
            description=f"{self.title_info}\nHalaman **{self.current_page + 1} / {self.max_page}**",
            color=self.color
        )

        chat_text = "".join([f"{idx}. <@{uid}> — **{cnt}** pesan\n" for idx, (uid, cnt) in current_chat])
        voice_text = "".join([f"{idx}. <@{uid}> — **{cnt}** aktivitas\n" for idx, (uid, cnt) in current_voice])

        embed.add_field(name="💬 Top Chatting", value=chat_text or "*Tidak ada data di halaman ini*", inline=False)
        embed.add_field(name="🔊 Top Voice Activity", value=voice_text or "*Tidak ada data di halaman ini*", inline=False)
        embed.set_footer(text="Gunakan tombol di bawah untuk navigasi halaman.")
        return embed

    @discord.ui.button(label="◀️ Sebelumnya", style=discord.ButtonStyle.blurple)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Selanjutnya ▶️", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_page - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()


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

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        
        utc_now = datetime.now(timezone.utc)
        wib_time = utc_now.astimezone(timezone(timedelta(hours=7)))
        date_str = wib_time.strftime("%Y-%m-%d")

        if guild_id not in self.stats_data:
            self.stats_data[guild_id] = {}
        if date_str not in self.stats_data[guild_id]:
            self.stats_data[guild_id][date_str] = {"chat": {}, "voice": {}}

        chat_counts = self.stats_data[guild_id][date_str]["chat"]
        chat_counts[user_id] = chat_counts.get(user_id, 0) + 1
        self.save_db()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or not member.guild:
            return

        guild_id = str(member.guild.id)
        user_id = str(member.id)
        
        utc_now = datetime.now(timezone.utc)
        wib_time = utc_now.astimezone(timezone(timedelta(hours=7)))
        date_str = wib_time.strftime("%Y-%m-%d")

        if guild_id not in self.stats_data:
            self.stats_data[guild_id] = {}
        if date_str not in self.stats_data[guild_id]:
            self.stats_data[guild_id][date_str] = {"chat": {}, "voice": {}}

        if before.channel is None and after.channel is not None:
            voice_counts = self.stats_data[guild_id][date_str]["voice"]
            voice_counts[user_id] = voice_counts.get(user_id, 0) + 1
            self.save_db()

    def aggregate_data(self, guild_id, period_filter=None):
        if guild_id not in self.stats_data:
            return {}, {}

        total_chat = {}
        total_voice = {}

        for date_key, day_data in self.stats_data[guild_id].items():
            if period_filter and not date_key.startswith(period_filter):
                continue

            for uid, count in day_data.get("chat", {}).items():
                total_chat[uid] = total_chat.get(uid, 0) + count

            for uid, count in day_data.get("voice", {}).items():
                total_voice[uid] = total_voice.get(uid, 0) + count

        return total_chat, total_voice

    # ==========================================
    # COMMAND 1: TOP STATS
    # ==========================================
    @commands.command(name="topstat", aliases=["topchat", "topvoice"])
    async def top_stat(self, ctx, periode: str = None):
        guild_id = str(ctx.guild.id)
        chat_dict, voice_dict = self.aggregate_data(guild_id, periode)

        sorted_chat = sorted(chat_dict.items(), key=lambda x: x[1], reverse=True)
        sorted_voice = sorted(voice_dict.items(), key=lambda x: x[1], reverse=True)

        formatted_chat = [(i, uid, cnt) for i, (uid, cnt) in enumerate(sorted_chat, 1)]
        formatted_voice = [(i, uid, cnt) for i, (uid, cnt) in enumerate(sorted_voice, 1)]

        title_info = f"Periode: **{periode}**" if periode else "Akumulasi **Sepanjang Masa**"

        view = TopStatsPaginator(formatted_chat, formatted_voice, title_info, discord.Color.gold())
        await ctx.send(embed=view.create_embed(), view=view)

    # ==========================================
    # COMMAND 2: TOP ROLE (Fixed optional parameter)
    # ==========================================
    @commands.command(name="toprole")
    async def top_role(self, ctx, target_role: discord.Role, periode: str = None):
        guild_id = str(ctx.guild.id)
        chat_dict, voice_dict = self.aggregate_data(guild_id, periode)

        filtered_chat = {uid: cnt for uid, cnt in chat_dict.items() if ctx.guild.get_member(int(uid)) and target_role in ctx.guild.get_member(int(uid)).roles}
        filtered_voice = {uid: cnt for uid, cnt in voice_dict.items() if ctx.guild.get_member(int(uid)) and target_role in ctx.guild.get_member(int(uid)).roles}

        sorted_chat = sorted(filtered_chat.items(), key=lambda x: x[1], reverse=True)
        sorted_voice = sorted(filtered_voice.items(), key=lambda x: x[1], reverse=True)

        formatted_chat = [(i, uid, cnt) for i, (uid, cnt) in enumerate(sorted_chat, 1)]
        formatted_voice = [(i, uid, cnt) for i, (uid, cnt) in enumerate(sorted_voice, 1)]

        title_info = f"Role: **{target_role.name}** | Periode: **{periode or 'Sepanjang Masa'}**"

        view = TopStatsPaginator(formatted_chat, formatted_voice, title_info, target_role.color)
        await ctx.send(embed=view.create_embed(), view=view)

    @top_role.error
    async def toprole_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("⚠️ Format kurang lengkap! Contoh: `!toprole @OSIS` atau `!toprole @OSIS 2026-09`")

    # ==========================================
    # COMMAND 3: CEK USER
    # ==========================================
    @commands.command(name="cekuser", aliases=["statsuser"])
    async def cek_user(self, ctx, member: discord.Member = None, periode: str = None):
        if not member:
            member = ctx.author

        guild_id = str(ctx.guild.id)
        chat_dict, voice_dict = self.aggregate_data(guild_id, periode)
        user_id = str(member.id)

        chat_count = chat_dict.get(user_id, 0)
        voice_count = voice_dict.get(user_id, 0)

        title_info = f"({periode})" if periode else "(Total Sepanjang Masa)"

        embed = discord.Embed(
            title=f"📊 Statistik: {member.display_name} {title_info}",
            color=member.color
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="💬 Total Pesan Chat", value=f"**{chat_count}** pesan", inline=True)
        embed.add_field(name="🔊 Total Aktivitas Voice", value=f"**{voice_count}** aktivitas", inline=True)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(TopStats(bot))