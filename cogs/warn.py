import discord
from discord.ext import commands
import json
import os
from datetime import datetime

WARN_FILE = "data/warns.json"

def load_warns():
    if not os.path.exists(WARN_FILE):
        return {}
    with open(WARN_FILE, "r") as f:
        return json.load(f)

def save_warns(data):
    with open(WARN_FILE, "w") as f:
        json.dump(data, f, indent=4)

class Warn(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason="Tidak disebutkan"):
        data = load_warns()
        gid = str(ctx.guild.id)
        uid = str(member.id)

        if gid not in data:
            data[gid] = {}
        if uid not in data[gid]:
            data[gid][uid] = []

        data[gid][uid].append({
            "reason": reason,
            "by": ctx.author.name,
            "time": datetime.now().strftime("%d/%m/%Y %H:%M")
        })

        save_warns(data)

        total = len(data[gid][uid])

        embed = discord.Embed(
            title="⚠️ Warning Diberikan",
            color=discord.Color.orange()
        )
        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Alasan", value=reason, inline=False)
        embed.add_field(name="Total Warn", value=total)

        await ctx.send(embed=embed)

    @commands.command()
    async def warns(self, ctx, member: discord.Member):
        data = load_warns()
        gid = str(ctx.guild.id)
        uid = str(member.id)

        if gid not in data or uid not in data[gid]:
            await ctx.send("✅ Member ini bersih, tidak ada warn.")
            return

        embed = discord.Embed(
            title=f"📋 Warn List — {member}",
            color=discord.Color.red()
        )

        for i, warn in enumerate(data[gid][uid], start=1):
            embed.add_field(
                name=f"#{i}",
                value=f"📝 {warn['reason']}\n👮 {warn['by']} | ⏰ {warn['time']}",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def delwarn(self, ctx, member: discord.Member, index: int):
        data = load_warns()
        gid = str(ctx.guild.id)
        uid = str(member.id)

        if gid not in data or uid not in data[gid]:
            await ctx.send("❌ Tidak ada warn.")
            return

        if index < 1 or index > len(data[gid][uid]):
            await ctx.send("❌ Index warn tidak valid.")
            return

        removed = data[gid][uid].pop(index - 1)
        save_warns(data)

        await ctx.send(
            f"🗑️ Warn dihapus:\n**{removed['reason']}**"
        )

def setup(bot):
    bot.add_cog(Warn(bot))
