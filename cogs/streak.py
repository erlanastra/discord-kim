import discord
from discord.ext import commands, tasks
import sqlite3
from datetime import datetime

STREAK_ROLES = [1, 5, 10, 20, 30, 50, 100]

NOTIF_CHANNEL = "📈｜notification-streak"
REMINDER_CHANNEL = "⏰｜reminder-streak"

DB_FILE = "data/streak.db"

class Streak(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_db()
        self.data = self.load_data()
        self.reminder_loop.start()

    # ================= DATABASE =================
    def init_db(self):
        self.conn = sqlite3.connect(DB_FILE)
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS streaks (
                guild_id TEXT,
                user_id TEXT,
                streak INTEGER,
                last TEXT,
                reminder INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        self.conn.commit()

    def load_data(self):
        self.cursor.execute("SELECT guild_id, user_id, streak, last, reminder FROM streaks")
        data = {}
        for gid, uid, streak, last, reminder in self.cursor.fetchall():
            data.setdefault(gid, {})[uid] = {
                "streak": streak,
                "last": last,
                "reminder": bool(reminder)
            }
        return data

    def save_data(self):
        for gid, users in self.data.items():
            for uid, info in users.items():
                self.cursor.execute("""
                    INSERT INTO streaks (guild_id, user_id, streak, last, reminder)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET
                        streak=excluded.streak,
                        last=excluded.last,
                        reminder=excluded.reminder
                """, (gid, uid, info["streak"], info["last"], int(info["reminder"])))
        self.conn.commit()

    # ================= UTIL =================
    def today(self):
        return datetime.utcnow().strftime("%Y-%m-%d")

    def get_badge(self, streak):
        if streak >= 100: return "👑"
        if streak >= 50: return "🔥"
        if streak >= 30: return "⚡"
        if streak >= 20: return "💎"
        if streak >= 10: return "🏆"
        if streak >= 5: return "🥉"
        if streak >= 1: return "⭐"
        return ""

    def get_channel(self, guild, name):
        return discord.utils.get(guild.text_channels, name=name)

    def user_profile(self, embed: discord.Embed, member: discord.Member):
        embed.set_author(
            name=member.display_name,
            icon_url=member.display_avatar.url
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        return embed

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
        role_name = f"🔥 STREAK {level}"
        new_role = discord.utils.get(guild.roles, name=role_name)

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
            title="STREAK LEVEL UP",
            description=(f"{member.mention} naik level konsistensi.\n\n"
                         f"🔥 Streak: `{streak} hari`\n"
                         f"🏆 Role baru: {role.mention}"),
            color=discord.Color.gold()
        )
        embed.set_footer(text="Tetap konsisten setiap hari")
        embed = self.user_profile(embed, member)
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
                        title="STREAK REMINDER",
                        description=(f"{member.mention}, streak kamu belum aktif hari ini.\n"
                                     f"🔥 Streak sekarang: `{info['streak']} hari`"),
                        color=discord.Color.purple()
                    )
                    embed.set_footer(text="Chat atau join voice biar streak aman")
                    embed = self.user_profile(embed, member)
                    await channel.send(embed=embed)

    # ================= COMMAND =================
    @commands.command(name="streak")
    async def streak_info(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        gid, uid = str(ctx.guild.id), str(target.id)

        if gid not in self.data or uid not in self.data[gid]:
            return await ctx.send(f"{target.mention} belum punya streak.")

        info = self.data[gid][uid]
        badge = self.get_badge(info["streak"])
        desc = f"{badge} Streak: `{info['streak']} hari`\n📅 Terakhir aktif: `{info['last']}`"

        if target == ctx.author:
            status = "ON" if info.get("reminder", True) else "OFF"
            desc += f"\n🔔 Reminder: `{status}`"

        embed = discord.Embed(
            title="STREAK INFO",
            description=desc,
            color=discord.Color.green() if target == ctx.author else discord.Color.blue()
        )
        embed.set_footer(text="Konsistensi kecil, dampak besar")
        embed = self.user_profile(embed, target)
        await ctx.send(embed=embed)

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

        status = "AKTIF" if user["reminder"] else "NONAKTIF"
        embed = discord.Embed(
            title="STREAK REMINDER",
            description=f"Reminder streak kamu sekarang `{status}`",
            color=discord.Color.green()
        )
        embed = self.user_profile(embed, ctx.author)
        await ctx.send(embed=embed)

    @commands.command(name="streaklb")
    async def leaderboard(self, ctx):
        gid = str(ctx.guild.id)
        if gid not in self.data or not self.data[gid]:
            return await ctx.send("Belum ada data streak.")

        sorted_users = sorted(
            self.data[gid].items(),
            key=lambda x: x[1]["streak"],
            reverse=True
        )[:10]

        desc = ""
        for i, (uid, info) in enumerate(sorted_users, 1):
            member = ctx.guild.get_member(int(uid))
            if not member:
                continue
            desc += f"#{i} {self.get_badge(info['streak'])} {member.mention} — `{info['streak']} hari`\n"

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
            title="STREAK SYSTEM",
            description=("Naikkan streak dengan:\n• Chat\n• Join voice\n(1x per hari)\n\n"
                         "Command:\n`!streak`\n`!streak @user`\n`!streaklb`\n`!streakreminder`"),
            color=discord.Color.purple()
        )
        embed.set_footer(text="Tetap aktif setiap hari")
        embed = self.user_profile(embed, ctx.author)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Streak(bot))
