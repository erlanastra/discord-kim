import discord
from discord.ext import commands, tasks
from datetime import datetime

class StaffDirectory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # ID Channel tempat panel staff ini dikirim/di-update otomatis
        self.CHANNEL_ID = 1540754204161736915  # Ganti dengan ID Channel tujuan
        self.message_id = None 
        self.update_directory.start()

    def cog_unload(self):
        self.update_directory.cancel()

    async def generate_staff_embed(self, guild):
        embed = discord.Embed(
            title="🏫 STRUKTUR STAFF nanZ SERVER",
            description="Daftar pengurus dan staff yang bertugas secara *real-time*.",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        # Definisikan hierarki berdasarkan ROLE ID masing-masing
        # Ganti deretan angka di bawah dengan ID role yang ada di servermu
        hierarchy = [
            {"role_id": 1417582562100117584, "name": "Guru Besar", "emoji": "👑"},
            {"role_id": 1453103644244316343, "name": "Moderator", "emoji": "🛡️"},
            {"role_id": 1467360501745844446, "name": "Pembina OSIS", "emoji": "📚"},
            {"role_id": 1427276194876751902, "name": "OSIS", "emoji": "✍️"}
        ]

        for item in hierarchy:
            role = guild.get_role(item["role_id"])
            members_list = []
            
            if role:
                # Urutkan atau tampilkan member yang memiliki role tersebut
                for member in role.members:
                    status_emoji = "🟢" if member.status != discord.Status.offline else "⚪"
                    members_list.append(f"{status_emoji} {member.mention} (`{member.display_name}`)")

            content = "\n".join(members_list) if members_list else "*(Belum ada staff)*"
            embed.add_field(
                name=f"{item['emoji']} {item['name']}",
                value=content,
                inline=False
            )

        embed.set_footer(text="Diperbarui secara otomatis oleh nanZ Bot")
        return embed

    @tasks.loop(minutes=5)
    async def update_directory(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.CHANNEL_ID)
        if not channel:
            return

        guild = channel.guild
        embed = await self.generate_staff_embed(guild)

        try:
            if self.message_id:
                try:
                    msg = await channel.fetch_message(self.message_id)
                    await msg.edit(embed=embed)
                    return
                except discord.NotFound:
                    pass

            async for message in channel.history(limit=10):
                if message.author == self.bot.user and message.embeds:
                    self.message_id = message.id
                    await message.edit(embed=embed)
                    return

            new_msg = await channel.send(embed=embed)
            self.message_id = new_msg.id
        except Exception as e:
            print(f"Gagal mengupdate staff directory: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.roles != after.roles:
            channel = self.bot.get_channel(self.CHANNEL_ID)
            if channel and self.message_id:
                try:
                    msg = await channel.fetch_message(self.message_id)
                    embed = await self.generate_staff_embed(after.guild)
                    await msg.edit(embed=embed)
                except Exception:
                    pass

    @commands.command(name="setupdirectory")
    @commands.has_permissions(administrator=True)
    async def setup_directory(self, ctx):
        """Perintah manual untuk memunculkan panel pertama kali"""
        self.CHANNEL_ID = ctx.channel.id
        embed = await self.generate_staff_embed(ctx.guild)
        msg = await ctx.send(embed=embed)
        self.message_id = msg.id
        await ctx.message.delete()

async def setup(bot):
    await bot.add_cog(StaffDirectory(bot))