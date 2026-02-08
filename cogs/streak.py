import discord
from discord.ext import commands, tasks
import json
import os
from datetime import datetime

DATA_FILE = "data/streak.json"

STREAK_ROLES = [1, 5, 10, 20, 30, 50, 100]

NOTIF_CHANNEL = "notification-streak"
REMINDER_CHANNEL = "reminder-streak"


class Streak(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = self.load_data()
        self.reminder_loop.start()

    # ================= FILE =================
    def load_data(self):
        if not os.path.exists(DATA_FILE):
            return {}
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("[WARN] streak.json rusak / kosong → reset")
            return {}

    def save_data(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    # ================= UTIL =================
    def today(self):
        return datetime.utcnow().strftime("%Y-%m-%d")

    def get_badge(self, streak):
        if streak >= 100:
            return "👑"
        if streak >= 50:
            return "🔥"
        if streak >= 30:
            return "⚡"
        if streak >= 20:
            return "💎"
        if streak >= 10:
            return "🏆"
        if streak >= 5:
            return "🥉"
        if streak >= 1:
            return "⭐"
        return ""

    def get_channel(self, guild, name):
        return discord.utils.get(guild.text_channels, name=name)

    # ================= CORE =================
    async def add_streak(self, member):
        gid, uid = str(member.guild.id), str(member.id)

        self.data.setdefault(gid, {})
        user = self.data[gid].setdefault(uid, {
            "streak": 0,
            "last": "",
            "reminder": True
        })

        if user["last"] == self.today():
            return

        user["streak"] += 1
        user["last"] = self.today()
        self.save_data()

        await self.handle_roles(member, user["streak"])

    async def handle_roles(self, member, streak):
        passed = [s for s in STREAK_ROLES if streak >= s]
        if not passed:
            return

        level = max(passed)
        guild = member.guild
        new_role = discord.utils.get(guild.roles, name=f"🔥 STREAK {level}")

        if not new_role:
            return

        for role in member.roles:
            if role.name.startswith("🔥 STREAK") and role != new_role:
                await member.remove_roles(role)

        if new_role not in member.roles:
            await member.add_roles(new_role)
            await self.send_levelup(member, new_role, streak)

    async def send_levelup(self, member, role, streak):
        channel = self.get_channel(member.guild, NOTIF_CHANNEL)
        if not channel:
            return

        embed = discord.Embed(
            title="🔥 STREAK LEVEL UP!",
            description=(
                f"{member.mention} naik level konsistensi!\n\n"
                f"🔥 **Streak:** `{streak} hari`\n"
                f"🏆 **Role Baru:** {role.mention}"
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text="Jangan putus, lanjutkan 🔥")
        await channel.send(embed=embed)

    # ================= LISTENER =================
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        await self.add_streak(message.author)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if after.channel and not before.channel:
            await self.add_streak(member)

    # ================= REMINDER =================
    @tasks.loop(hours=24)
    async def reminder_loop(self):
        for gid, users in self.data.items():
            guild = self.bot.get_guild(int(gid))
            if not guild:
                continue

            channel = self.get_channel(guild, REMINDER_CHANNEL)
            if not channel:
                continue

            for uid, info in users.items():
                if not info.get("reminder", True):
                    continue

                if info["last"] != self.today():
                    member = guild.get_member(int(uid))
                    if not member:
                        continue

                    embed = discord.Embed(
                        title="⏰ STREAK REMINDER",
                        description=(
                            f"{member.mention}, streak kamu belum jalan hari ini!\n"
                            f"🔥 **Streak:** `{info['streak']} hari`"
                        ),
                        color=discord.Color.purple()
                    )
                    embed.set_footer(text="Chat atau join VC biar aman 🔥")
                    await channel.send(embed=embed)

    @commands.command(name="streakreminder")
    async def toggle_reminder(self, ctx):
        gid, uid = str(ctx.guild.id), str(ctx.author.id)

        self.data.setdefault(gid, {}).setdefault(uid, {
            "streak": 0,
            "last": "",
            "reminder": True
        })

        user = self.data[gid][uid]
        user["reminder"] = not user["reminder"]
        self.save_data()

        status = "ON 🔔" if user["reminder"] else "OFF 🔕"
        await ctx.send(embed=discord.Embed(
            title="⚙️ Reminder Streak",
            description=f"Reminder streak kamu sekarang **{status}**",
            color=discord.Color.green()
        ))

    # ================= COMMAND =================
    @commands.command(name="streak")
    async def streak_info(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        gid, uid = str(ctx.guild.id), str(target.id)

        if gid not in self.data or uid not in self.data[gid]:
            return await ctx.send(f"{target.mention} belum punya streak.")

        info = self.data[gid][uid]
        badge = self.get_badge(info["streak"])

        desc = (
            f"{badge} **Streak:** `{info['streak']} hari`\n"
            f"📅 **Terakhir aktif:** `{info['last']}`"
        )

        if target == ctx.author:
            status = "ON 🔔" if info.get("reminder", True) else "OFF 🔕"
            desc += f"\n🔔 **Reminder:** {status}"

        embed = discord.Embed(
            title="🔥 STREAK INFO",
            description=desc,
            color=discord.Color.green() if target == ctx.author else discord.Color.blue()
        )
        embed.set_footer(text="Konsisten dikit, hasilnya besar 🔥")
        await ctx.send(embed=embed)

    @commands.command(name="streaklb")
    async def leaderboard(self, ctx):
        gid = str(ctx.guild.id)
        users = self.data.get(gid, {})

        if not users:
            return await ctx.send("Belum ada data streak 😴")

        sorted_users = sorted(
            users.items(),
            key=lambda x: x[1]["streak"],
            reverse=True
        )[:10]

        desc = ""
        for i, (uid, info) in enumerate(sorted_users, 1):
            member = ctx.guild.get_member(int(uid))
            if not member:
                continue
            desc += f"**#{i}** {self.get_badge(info['streak'])} {member.mention} — `{info['streak']} hari`\n"

        embed = discord.Embed(
            title="🏆 STREAK LEADERBOARD",
            description=desc,
            color=discord.Color.blue()
        )
        embed.set_footer(text="Konsistensi = power 🔥")
        await ctx.send(embed=embed)

    @commands.command(name="streakhelp")
    async def streak_help(self, ctx):
        embed = discord.Embed(
            title="🔥 STREAK SYSTEM HELP",
            description=(
                "**Cara naik streak:**\n"
                "• Kirim chat\n"
                "• atau join voice\n"
                "_1x per hari_\n\n"
                "**Command:**\n"
                "• `!streak`\n"
                "• `!streak @user`\n"
                "• `!streaklb`\n"
                "• `!streakreminder`\n\n"
                "**Hadiah:**\n"
                "🔥 Role otomatis\n"
                "🏆 Badge leaderboard"
            ),
            color=discord.Color.purple()
        )
        embed.set_footer(text="Tetap aktif tiap hari 🔥")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Streak(bot))
