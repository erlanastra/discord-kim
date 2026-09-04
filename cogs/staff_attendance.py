import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
import json
import os

class StaffAttendance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_file = "staff_attendance.json"
        self.attendance_data = self.load_db()
        
        # ID Channel khusus absensi
        self.ATTENDANCE_CHANNEL_ID = 1528025859792044082
        
        self.STAFF_ROLE_IDS = [
            1417582562100117584, # Guru Besar
            1453103644244316343, # Moderator
            1467360501745844446, # Pembina OSIS
            1427276194876751902  # OSIS
        ]

    def load_db(self):
        if not os.path.exists(self.db_file):
            return {}
        try:
            with open(self.db_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ATTENDANCE] Gagal memuat database: {e}")
            return {}

    def save_db(self):
        try:
            with open(self.db_file, "w", encoding="utf-8") as f:
                json.dump(self.attendance_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[ATTENDANCE] Gagal menyimpan database: {e}")

    def get_wib_time(self):
        utc_now = datetime.now(timezone.utc)
        wib_time = utc_now.astimezone(timezone(timedelta(hours=7)))
        return wib_time

    # Helper validasi channel khusus
    async def check_channel(self, ctx):
        if ctx.channel.id != self.ATTENDANCE_CHANNEL_ID:
            await ctx.reply(f"❌ Perintah ini hanya dapat digunakan di channel khusus absensi (<#{self.ATTENDANCE_CHANNEL_ID}>)!")
            return False
        return True

    # ==========================================
    # COMMAND: ABSEN
    # ==========================================
    @commands.command(name="absen")
    async def absen(self, ctx):
        if not await self.check_channel(ctx):
            return

        is_staff = any(role.id in self.STAFF_ROLE_IDS for role in ctx.author.roles)
        if not is_staff:
            await ctx.reply("❌ Perintah ini khusus untuk Staff nanZ!")
            return

        now = self.get_wib_time()
        date_str = now.strftime("%Y-%m-%d")
        member_id = str(ctx.author.id)

        if date_str not in self.attendance_data:
            self.attendance_data[date_str] = {}

        if member_id in self.attendance_data[date_str]:
            data_sementara = self.attendance_data[date_str][member_id]
            await ctx.reply(f"⚠️ Kamu sudah tercatat hari ini dengan status: **{data_sementara['status']}**.")
            return

        current_hour = now.hour
        if current_hour < 4:
            await ctx.reply("⏳ Absen harian belum dibuka! Mulai pukul **04:00 WIB**.")
            return

        time_str = now.strftime("%H:%M:%S")
        status = "Tepat Waktu" if (current_hour < 12 or (current_hour == 12 and now.minute == 0)) else "Telat"
        color = discord.Color.green() if status == "Tepat Waktu" else discord.Color.orange()

        self.attendance_data[date_str][member_id] = {
            "name": ctx.author.display_name,
            "time": time_str,
            "status": status,
            "reason": "-"
        }
        self.save_db()

        embed = discord.Embed(
            title="📋 Berhasil Absen nanZ (WIB)",
            description=f"Terima kasih, **{ctx.author.mention}** telah melakukan absensi.",
            color=color
        )
        embed.add_field(name="Waktu Absen", value=f"`{time_str} WIB`", inline=True)
        embed.add_field(name="Status", value=f"**{status}**", inline=True)
        embed.set_footer(text=f"Tanggal: {date_str}")
        await ctx.send(embed=embed)

    # ==========================================
    # COMMAND: IZIN
    # ==========================================
    @commands.command(name="izin")
    async def izin(self, ctx, *, keterangan: str = None):
        if not await self.check_channel(ctx):
            return

        is_staff = any(role.id in self.STAFF_ROLE_IDS for role in ctx.author.roles)
        if not is_staff:
            await ctx.reply("❌ Perintah ini khusus untuk Staff nanZ!")
            return

        if not keterangan:
            await ctx.reply(
                "⚠️ Format izin kurang lengkap!\n"
                "Contoh Izin Seharian: `!izin Sakit demam`\n"
                "Contoh Izin Sebagian Waktu: `!izin Sampai pulang sekolah - Urusan keluarga`"
            )
            return

        now = self.get_wib_time()
        date_str = now.strftime("%Y-%m-%d")
        member_id = str(ctx.author.id)

        if date_str not in self.attendance_data:
            self.attendance_data[date_str] = {}

        if member_id in self.attendance_data[date_str]:
            await ctx.reply("⚠️ Kamu sudah tercatat melakukan absensi/izin hari ini.")
            return

        time_str = now.strftime("%H:%M:%S")
        
        keyword_partial = ["sampai", "jam", "pulang", "setengah", "menyusul"]
        is_partial = any(k in keterangan.lower() for k in keyword_partial)
        status_label = "Izin (Sebagian Waktu)" if is_partial else "Izin (Seharian)"

        self.attendance_data[date_str][member_id] = {
            "name": ctx.author.display_name,
            "time": time_str,
            "status": status_label,
            "reason": keterangan
        }
        self.save_db()

        embed = discord.Embed(
            title="📝 Pengajuan Izin Tercatat",
            description=f"Staff **{ctx.author.mention}** mengajukan **{status_label}**.",
            color=discord.Color.gold()
        )
        embed.add_field(name="Keterangan / Alasan", value=keterangan, inline=False)
        embed.set_footer(text=f"Dicatat pada pukul {time_str} WIB | {date_str}")
        await ctx.send(embed=embed)

    # ==========================================
    # COMMAND: REKAP ABSEN
    # ==========================================
    @commands.command(name="rekapabsen")
    async def rekap_absen(self, ctx):
        if not await self.check_channel(ctx):
            return

        is_staff = any(role.id in self.STAFF_ROLE_IDS for role in ctx.author.roles)
        if not is_staff:
            await ctx.reply("🤫 **Rahasia!**")
            return

        now = self.get_wib_time()
        date_str = now.strftime("%Y-%m-%d")
        daily_records = self.attendance_data.get(date_str, {})

        embed = discord.Embed(
            title=f"📊 Rekap Absensi & Izin Staff nanZ (WIB)",
            description=f"Tanggal: **{date_str}**",
            color=discord.Color.blue()
        )

        if not daily_records:
            embed.description += "\n\n*Belum ada data absensi atau izin hari ini.*"
        else:
            desc_list = []
            for m_id, info in daily_records.items():
                status = info["status"]
                if "Tepat Waktu" in status:
                    icon = "🟢"
                elif "Telat" in status:
                    icon = "🟠"
                else:
                    icon = "🟡"
                
                detail = f" — **{status}**"
                if info["reason"] != "-":
                    detail += f" (*{info['reason']}*)"
                else:
                    detail += f" (`{info['time']}`)"
                
                desc_list.append(f"{icon} <@{m_id}>{detail}")
                
            embed.add_field(name="Daftar Kehadiran & Izin", value="\n".join(desc_list), inline=False)

        await ctx.send(embed=embed)

    # ==========================================
    # LISTENER: KEAMANAN PESAN AI
    # ==========================================
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        content_lower = message.content.lower()
        trigger_keywords = ["absen", "siapa yang telat", "siapa yang izin", "rekap absen", "data absen"]
        
        if any(keyword in content_lower for keyword in trigger_keywords):
            # Jika dibahas di channel absensi atau channel lain oleh non-staff
            is_staff = isinstance(message.author, discord.Member) and any(role.id in self.STAFF_ROLE_IDS for role in message.author.roles)
            if not is_staff:
                await message.reply("🤫 **Rahasia!**")

async def setup(bot):
    await bot.add_cog(StaffAttendance(bot))