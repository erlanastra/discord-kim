import discord
from discord.ext import commands, tasks
import aiomysql
from datetime import datetime, timedelta, timezone

STREAK_ROLES = [1, 5, 10, 20, 30, 50, 100]

NOTIF_CHANNEL = 1469914626614493349
REMINDER_CHANNEL = 1469909631441699010


class Streak(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = None
        bot.loop.create_task(self.init_db())

        if not self.reminder_loop.is_running():
            self.reminder_loop.start()

    # ================= CLEANUP =================
    def cog_unload(self):
        self.reminder_loop.cancel()
        if self.pool:
            self.pool.close()

    # ================= DATABASE =================
    async def init_db(self):
        self.pool = await aiomysql.create_pool(
            host="sql5.freesqldatabase.com",
            port=3306,
            user="sql5820722",
            password="m6GjypbQk3",
            db="sql5820722",  # ⬅️ WAJIB sesuai database kamu
            autocommit=True
        )

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS streaks (
                        guild_id VARCHAR(50),
                        user_id VARCHAR(50),
                        streak INT,
                        last VARCHAR(20),
                        reminder TINYINT(1),
                        PRIMARY KEY (guild_id, user_id)
                    )
                """)

    # ================= UTIL =================
    def today(self):
        wib = timezone(timedelta(hours=7))
        return datetime.now(wib).strftime("%Y-%m-%d")

    def get_badge(self, streak):
        if streak >= 100: return "👑"
        if streak >= 50: return "🔥"
        if streak >= 30: return "⚡"
        if streak >= 20: return "💎"
        if streak >= 10: return "🏆"
        if streak >= 5: return "🥉"
        if streak >= 1: return "⭐"
        return ""

    def get_channel(self, guild, channel_id):
        return guild.get_channel(channel_id)

    def user_profile(self, embed, member):
        embed.set_author(
            name=member.display_name,
            icon_url=member.display_avatar.url
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        return embed

    # ================= CORE =================
    async def add_streak(self, member):
        if not self.pool:
            return

        gid, uid = str(member.guild.id), str(member.id)
        today = self.today()

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:

                await cursor.execute("""
                    SELECT streak, last FROM streaks
                    WHERE guild_id=%s AND user_id=%s
                """, (gid, uid))
                row = await cursor.fetchone()

                if row and row["last"] == today:
                    return

                if row:
                    streak = row["streak"] + 1
                    await cursor.execute("""
                        UPDATE streaks
                        SET streak=%s, last=%s
                        WHERE guild_id=%s AND user_id=%s
                    """, (streak, today, gid, uid))
                else:
                    streak = 1
                    await cursor.execute("""
                        INSERT INTO streaks (guild_id, user_id, streak, last, reminder)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (gid, uid, streak, today, 1))

        await self.handle_roles(member, streak)

    async def handle_roles(self, member, streak):
        passed = [s for s in STREAK_ROLES if streak >= s]
        if not passed:
            return

        level = max(passed)
        role_name = f"🔥 STREAK {level}"
        new_role = discord.utils.get(member.guild.roles, name=role_name)
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
        if not self.pool:
            return

        today = self.today()

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT * FROM streaks
                    WHERE reminder=1 AND last!=%s
                """, (today,))
                rows = await cursor.fetchall()

        for row in rows:
            guild = self.bot.get_guild(int(row["guild_id"]))
            if not guild:
                continue

            channel = self.get_channel(guild, REMINDER_CHANNEL)
            if not channel:
                continue

            member = guild.get_member(int(row["user_id"]))
            if not member:
                continue

            embed = discord.Embed(
                title="STREAK REMINDER",
                description=(f"{member.mention}, streak kamu belum aktif hari ini.\n"
                             f"🔥 Streak sekarang: `{row['streak']} hari`"),
                color=discord.Color.purple()
            )
            embed.set_footer(text="Chat atau join voice biar streak aman")
            embed = self.user_profile(embed, member)
            await channel.send(embed=embed)

    # ================= COMMAND =================
    @commands.command(name="streak")
    async def streak_info(self, ctx, member: discord.Member = None):
        if not self.pool:
            return await ctx.send("Database belum siap.")

        target = member or ctx.author
        gid, uid = str(ctx.guild.id), str(target.id)

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT * FROM streaks
                    WHERE guild_id=%s AND user_id=%s
                """, (gid, uid))
                row = await cursor.fetchone()

        if not row:
            return await ctx.send(f"{target.mention} belum punya streak.")

        badge = self.get_badge(row["streak"])
        desc = f"{badge} Streak: `{row['streak']} hari`\n📅 Terakhir aktif: `{row['last']}`"

        if target == ctx.author:
            status = "ON" if row["reminder"] else "OFF"
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
        if not self.pool:
            return await ctx.send("Database belum siap.")

        gid, uid = str(ctx.guild.id), str(ctx.author.id)

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO streaks (guild_id, user_id, streak, last, reminder)
                    VALUES (%s, %s, 0, '', 1)
                    ON DUPLICATE KEY UPDATE reminder = NOT reminder
                """, (gid, uid))

                await cursor.execute("""
                    SELECT reminder FROM streaks
                    WHERE guild_id=%s AND user_id=%s
                """, (gid, uid))
                row = await cursor.fetchone()

        status = "AKTIF" if row[0] else "NONAKTIF"

        embed = discord.Embed(
            title="STREAK REMINDER",
            description=f"Reminder streak kamu sekarang `{status}`",
            color=discord.Color.green()
        )
        embed = self.user_profile(embed, ctx.author)
        await ctx.send(embed=embed)

    @commands.command(name="streaklb")
    async def leaderboard(self, ctx):
        if not self.pool:
            return await ctx.send("Database belum siap.")

        gid = str(ctx.guild.id)

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT * FROM streaks
                    WHERE guild_id=%s
                    ORDER BY streak DESC
                    LIMIT 10
                """, (gid,))
                rows = await cursor.fetchall()

        if not rows:
            return await ctx.send("Belum ada data streak.")

        desc = ""
        for i, row in enumerate(rows, 1):
            member = ctx.guild.get_member(int(row["user_id"]))
            if not member:
                continue
            desc += f"#{i} {self.get_badge(row['streak'])} {member.mention} — `{row['streak']} hari`\n"

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