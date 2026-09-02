import discord
from discord.ext import commands
import json

class StaffDirectory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open("config.json") as f:
            self.config = json.load(f)

        # MAPPING ROLE ID KE CONFIGURASI TAMPILAN
        # Ganti angka di bawah ini dengan ID Role yang sesuai di server kamu
        self.STAFF_ROLES = {
            1417582562100117584: {  # Contoh ID Role: Guru Besar / Owner
                "title": "👑 Guru Besar (Owner)",
                "color": 0xFFD700
            },
            1453103644244316343: {  # Contoh ID Role: Moderator / Mod DC
                "title": "🛡️ Moderator DC (Mod)",
                "color": 0x3498DB
            },
            1467360501745844446: {  # Contoh ID Role: Pembina OSIS
                "title": "📚 Pembina OSIS",
                "color": 0xE74C3C
            },
            1427276194876751902: {  # Contoh ID Role: OSIS / Kru
                "title": "🎒 OSIS",
                "color": 0x2ECC71
            }
        }

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        before_roles = set(r.id for r in before.roles)
        after_roles = set(r.id for r in after.roles)
        added_roles = after_roles - before_roles
        
        for role_id in added_roles:
            if role_id in self.STAFF_ROLES:
                await self.send_staff_update_log(after, role_id)

    async def send_staff_update_log(self, member: discord.Member, role_id: int):
        channel_id = self.config.get("staff_log_channel")
        if not channel_id:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        role_info = self.STAFF_ROLES[role_id]
        role_obj = member.guild.get_role(role_id)

        embed = discord.Embed(
            title=role_info["title"],
            description=f"• {member.mention} (`{member.name}`) 🎉\n> Telah resmi mendapatkan posisi baru di struktur kepengurusan **nanZ Server**!",
            color=role_info["color"]
        )

        embed.add_field(
            name="📍 Bagian / Divisi",
            value=f"` nanZ School | {role_obj.name if role_obj else 'Staff'} `",
            inline=False
        )
        
        embed.set_footer(text="nanZ Server System • Staff Promotion Update")

        await channel.send(embed=embed)

    @commands.command(name="teststaff")
    @commands.has_permissions(administrator=True)
    async def test_staff(self, ctx, member: discord.Member = None, role_id: int = None):
        member = member or ctx.author
        if not role_id:
            return await ctx.send("❌ Masukkan ID role staff! Contoh: `!teststaff @user 111111111111111111`")
        
        if role_id not in self.STAFF_ROLES:
            return await ctx.send("❌ ID Role tersebut belum terdaftar di dictionary `STAFF_ROLES` bot.")

        await self.send_staff_update_log(member, role_id)
        await ctx.send("✅ Berhasil mengirim simulasi update staff!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(StaffDirectory(bot))
