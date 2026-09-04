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
        
        # Sinkronisasi role ID staff
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

    # Helper untuk mendapatkan waktu WIB (UTC+7)
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
    # COMMAND: IZIN (Seharian & Sebagian Waktu)
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
                "• Contoh Seharian: `!izin Sakit demam`\n"
                "• Contoh Sebagian Waktu: `!izin Sampai pulang sekolah - Urusan keluarga`"
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
    # COMMAND: REKAP HARIAN
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
    # COMMAND: REKAP BULANAN (EVALUASI)
    # ==========================================
    @commands.command(name="rekapbulanan")
    async def rekap_bulanan(self, ctx, bulan: str = None, tahun: str = None):
        if not await self.check_channel(ctx):
            return

        is_staff = any(role.id in self.STAFF_ROLE_IDS for role in ctx.author.roles)
        if not is_staff:
            await ctx.reply("🤫 **Rahasia!**")
            return

        now = self.get_wib_time()
        if not bulan:
            bulan = now.strftime("%m")
        if not tahun:
            tahun = now.strftime("%Y")

        target_prefix = f"{tahun}-{bulan}"
        summary = {}

        for date_str, records in self.attendance_data.items():
            if date_str.startswith(target_prefix):
                for m_id, info in records.items():
                    if m_id not in summary:
                        summary[m_id] = {
                            "name": info.get("name", "Unknown"),
                            "tepat_waktu": 0,
                            "telat": 0,
                            "izin": 0
                        }
                    
                    status = info["status"]
                    if "Tepat Waktu" in status:
                        summary[m_id]["tepat_waktu"] += 1
                    elif "Telat" in status:
                        summary[m_id]["telat"] += 1
                    elif "Izin" in status:
                        summary[m_id]["izin"] += 1

        embed = discord.Embed(
            title=f"📈 Rekap Evaluasi Bulanan Staff ({target_prefix})",
            description=f"Akumulasi data absensi untuk bulan **{bulan}** tahun **{tahun}**.",
            color=discord.Color.dark_blue()
        )

        if not summary:
            embed.description += "\n\n*Tidak ada data absensi yang tercatat pada periode tersebut.*"
        else:
            result_lines = []
            for m_id, data in summary.items():
                line = (
                    f"👤 <@{m_id}> (`{data['name']}`)\n"
                    f" 🟢 Tepat Waktu: **{data['tepat_waktu']}** | "
                    f" 🟠 Telat: **{data['telat']}** | "
                    f" 🟡 Izin: **{data['izin']}**"
                )
                result_lines.append(line)
            
            embed.add_field(name="Ringkasan Performa Staff", value="\n\n".join(result_lines), inline=False)

        embed.set_footer(text="Gunakan data ini untuk evaluasi akhir bulan nanZ.")
        await ctx.send(embed=embed)

    # ==========================================
    # COMMAND: HELP ABSENSI
    # ==========================================
    @commands.command(name="helpabsen", aliases=["absenhelp", "bantuabsen"])
    async def help_absen(self, ctx):
        if not await self.check_channel(ctx):
            return

        is_staff = any(role.id in self.STAFF_ROLE_IDS for role in ctx.author.roles)
        if not is_staff:
            await ctx.reply("❌ Perintah ini khusus untuk Staff nanZ!")
            return

        embed = discord.Embed(
            title="📖 Daftar Perintah Absensi nanZ",
            description="Berikut adalah daftar command absensi yang dapat digunakan:",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="`!absen`",
            value="Melakukan absensi harian.\n• **Tepat Waktu**: Pukul 04:00 - 12:00 WIB\n• **Telat**: Di atas pukul 12:00 WIB",
            inline=False
        )
        embed.add_field(
            name="`!izin [keterangan]`",
            value="Mengajukan izin (seharian penuh atau sebagian waktu).\n• *Contoh Seharian:* `!izin Sakit demam`\n• *Contoh Sebagian:* `!izin Sampai pulang sekolah - Urusan keluarga`",
            inline=False
        )
        embed.add_field(
            name="`!rekapabsen`",
            value="Melihat rekapitulasi kehadiran dan izin seluruh staff pada hari ini.",
            inline=False
        )
        embed.add_field(
            name="`!rekapbulanan [bulan] [tahun]`",
            value="Melihat rekap akumulasi bulanan untuk bahan evaluasi akhir bulan.\n• *Contoh:* `!rekapbulanan 09 2026`",
            inline=False
        )
        embed.set_footer(text="Zona Waktu: WIB | Khusus Staff nanZ")

        await ctx.send(embed=embed)

    # ==========================================
    # LISTENER: KEAMANAN PESAN AI / MEMBER
    # ==========================================
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        content_lower = message.content.lower()
        trigger_keywords = ["absen", "siapa yang telat", "siapa yang izin", "rekap absen", "data absen"]
        
        if any(keyword in content_lower for keyword in trigger_keywords):
            is_staff = isinstance(message.author, discord.Member) and any(role.id in self.STAFF_ROLE_IDS for role in message.author.roles)
            if not is_staff:
                await message.reply("🤫 **Rahasia!**")

async def setup(bot):
    await bot.add_cog(StaffAttendance(bot))