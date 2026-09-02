import discord
from discord.ext import commands, tasks
from datetime import datetime

class StaffDirectory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # ID Channel tujuan panel staff
        self.CHANNEL_ID = 1540754204161736915  
        self.message_ids = {} 
        self.update_directory.start()

    def cog_unload(self):
        self.update_directory.cancel()

    # Format status sederhana (Online / Offline) tanpa detail waktu yang rumit
    def get_clean_status(self, member):
        if member.status != discord.Status.offline:
            return "🟢 **Online**"
        else:
            return "⚪ **Offline**"

    # Membuat embed khusus per role dengan layout rapi dan profesional
    async def generate_role_embed(self, guild, role_info):
        role = guild.get_role(role_info["role_id"])
        
        embed = discord.Embed(
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        members_list = []
        member_count = 0

        if role:
            member_count = len(role.members)
            for member in role.members:
                status_text = self.get_clean_status(member)
                # Layout baris dibuat lebih rapi dengan format list terstruktur
                members_list.append(f"• {member.mention}  |  `{member.display_name}`  ⎯  {status_text}")

        content = "\n".join(members_list) if members_list else "*(Belum ada staff terdaftar)*"
        
        embed.set_author(
            name=f"{role_info['emoji']} {role_info['name']} (Staff)",
            icon_url=guild.icon.url if guild.icon else None
        )
        embed.description = content
        
        embed.set_footer(
            text=f"nanZ Server | {role_info['name']} • Total Anggota: {member_count}",
            icon_url=guild.icon.url if guild.icon else None
        )
        
        return embed

    async def refresh_all_panels(self, guild):
        channel = self.bot.get_channel(self.CHANNEL_ID)
        if not channel:
            return

        # Hierarki lengkap dengan Pembina OSIS di dalamnya
        hierarchy = [
            {"role_id": 1417582562100117584, "name": "Guru Besar", "emoji": "👑"},
            {"role_id": 1453103644244316343, "name": "Moderator", "emoji": "🛡️"},
            {"role_id": 1467360501745844446, "name": "Pembina OSIS", "emoji": "📚"},
            {"role_id": 1427276194876751902, "name": "OSIS", "emoji": "✍️"}
        ]

        for item in hierarchy:
            embed = await self.generate_role_embed(guild, item)
            msg_id = self.message_ids.get(item["role_id"])

            try:
                if msg_id:
                    msg = await channel.fetch_message(msg_id)
                    await msg.edit(embed=embed)
                else:
                    found = False
                    async for message in channel.history(limit=30):
                        if message.author == self.bot.user and message.embeds:
                            if message.embeds[0].author.name and item["name"] in message.embeds[0].author.name:
                                self.message_ids[item["role_id"]] = message.id
                                await message.edit(embed=embed)
                                found = True
                                break
                    if not found:
                        new_msg = await channel.send(embed=embed)
                        self.message_ids[item["role_id"]] = new_msg.id
            except Exception as e:
                print(f"Gagal update panel {item['name']}: {e}")

    @tasks.loop(minutes=3)
    async def update_directory(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.CHANNEL_ID)
        if channel:
            await self.refresh_all_panels(channel.guild)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.roles != after.roles:
            channel = self.bot.get_channel(self.CHANNEL_ID)
            if channel:
                await self.refresh_all_panels(after.guild)

    @commands.command(name="setupdirectory")
    @commands.has_permissions(administrator=True)
    async def setup_directory(self, ctx):
        """Membuat panel terpisah baru untuk setiap role staff"""
        self.CHANNEL_ID = ctx.channel.id
        await ctx.message.delete()
        
        hierarchy = [
            {"role_id": 1417582562100117584, "name": "Guru Besar", "emoji": "👑"},
            {"role_id": 1453103644244316343, "name": "Moderator", "emoji": "🛡️"},
            {"role_id": 1467360501745844446, "name": "Pembina OSIS", "emoji": "📚"},
            {"role_id": 1427276194876751902, "name": "OSIS", "emoji": "✍️"}
        ]

        for item in hierarchy:
            embed = await self.generate_role_embed(ctx.guild, item)
            msg = await ctx.send(embed=embed)
            self.message_ids[item["role_id"]] = msg.id

async def setup(bot):
    await bot.add_cog(StaffDirectory(bot))