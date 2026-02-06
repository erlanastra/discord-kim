import discord
from discord.ext import commands, tasks
from datetime import datetime
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_FILE = "data/activity.json"
BACKUP_DIR = "data/monthly_backup"

TOP_ROLE_NAME = "🏆 Top Activity"
STAFF_ROLE_NAMES = ["Admin", "Moderator", "Staff"]

# ================= UTIL =================
def load_data():
    if not os.path.exists(DATA_FILE):
        os.makedirs("data", exist_ok=True)
        data = {
            "month": datetime.utcnow().strftime("%Y-%m"),
            "chat": {},
            "voice": {},
            "stage": {}
        }
        save_data(data)
        return data

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ================= COG =================
class Activity(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_join = {}
        self.monthly_reset.start()

    # ========== AUTO RESET BULANAN ==========
    @tasks.loop(minutes=60)
    async def monthly_reset(self):
        data = load_data()
        now_month = datetime.utcnow().strftime("%Y-%m")

        if data["month"] != now_month:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            with open(f"{BACKUP_DIR}/{data['month']}.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            data = {
                "month": now_month,
                "chat": {},
                "voice": {},
                "stage": {}
            }
            save_data(data)

    # ========== CHAT TRACK ==========
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        data = load_data()
        uid = str(message.author.id)
        data["chat"][uid] = data["chat"].get(uid, 0) + 1
        save_data(data)

        # ⚠️ WAJIB agar command tetap hidup
        await self.bot.process_commands(message)

    # ========== VOICE TRACK ==========
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        now = datetime.utcnow()
        uid = str(member.id)
        data = load_data()

        if not before.channel and after.channel:
            self.voice_join[uid] = now

        if before.channel and not after.channel:
            start = self.voice_join.pop(uid, None)
            if start:
                seconds = int((now - start).total_seconds())
                data["voice"][uid] = data["voice"].get(uid, 0) + seconds
                save_data(data)

    # ========== STAGE TRACK ==========
    @commands.Cog.listener()
    async def on_stage_instance_create(self, stage):
        data = load_data()
        uid = str(stage.creator_id)
        data["stage"][uid] = data["stage"].get(uid, 0) + 1
        save_data(data)

    # ========== LEADERBOARD ==========
    @commands.command(name="activity")
    async def leaderboard(self, ctx):
        data = load_data()
        guild = ctx.guild
        members = {m.id: m for m in guild.members}

        def is_staff(member):
            return member and any(r.name in STAFF_ROLE_NAMES for r in member.roles)

        chat_sorted = sorted(
            data["chat"].items(),
            key=lambda x: x[1],
            reverse=True
        )

        staff_lb = [(u, v) for u, v in chat_sorted if is_staff(members.get(int(u)))]
        member_lb = [(u, v) for u, v in chat_sorted if not is_staff(members.get(int(u)))]

        embed = discord.Embed(
            title="🏆 Leaderboard Aktivitas Bulanan",
            description=f"📅 Bulan **{data['month']}**",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

        def format_lb(lb):
            if not lb:
                return "_Belum ada data_"
            text = ""
            for i, (uid, v) in enumerate(lb[:5]):
                text += f"{medals[i]} <@{uid}> — **{v} pesan**\n"
            return text

        embed.add_field(
            name="👮 Staff Teraktif (Chat)",
            value=format_lb(staff_lb),
            inline=False
        )

        embed.add_field(
            name="💬 Member Teraktif (Chat)",
            value=format_lb(member_lb),
            inline=False
        )

        # ========== AUTO ROLE TOP ==========
        if staff_lb:
            top_id = int(staff_lb[0][0])
            role = discord.utils.get(guild.roles, name=TOP_ROLE_NAME)

            if not role:
                role = await guild.create_role(
                    name=TOP_ROLE_NAME,
                    color=discord.Color.gold()
                )

            for m in role.members:
                await m.remove_roles(role)

            top_member = guild.get_member(top_id)
            if top_member:
                await top_member.add_roles(role)

        # ========== GRAFIK ==========
        labels = []
        values = []

        for uid, v in chat_sorted[:5]:
            member = members.get(int(uid))
            if member:
                labels.append(member.display_name)
                values.append(v)

        if labels:
            plt.figure(figsize=(6, 4))
            plt.bar(labels, values)
            plt.title("Top 5 Chat Activity")
            plt.ylabel("Jumlah Pesan")
            plt.tight_layout()
            plt.savefig("activity_chart.png")
            plt.close()

            file = discord.File("activity_chart.png", filename="activity_chart.png")
            embed.set_image(url="attachment://activity_chart.png")

            embed.set_footer(text="NanZ Server • Activity System (Realtime)")
            await ctx.send(embed=embed, file=file)
        else:
            embed.set_footer(text="NanZ Server • Activity System (Realtime)")
            await ctx.send(embed=embed)

# ========== SETUP ==========
async def setup(bot):
    await bot.add_cog(Activity(bot))
