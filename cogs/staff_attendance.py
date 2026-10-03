import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
import json
import os
import asyncio


class StaffAttendance(commands.Cog):
    """
    Sistem Absensi Staff nanZ

    Command:
        !absen
        !izin [keterangan]
        !rekapabsen
        !rekapbulanan [bulan] [tahun]
        !helpabsen
    """

    # ============================================================
    # CONFIG
    # ============================================================

    ATTENDANCE_CHANNEL_ID = 1528025859792044082

    STAFF_ROLE_IDS = [
        1555556260269527151,  # Moderator / Mod DC
        1467360501745844446,  # Pembina OSIS
        1427276194876751902,  # OSIS
    ]

    DB_FILE = "staff_attendance.json"

    # Sistem poin
    POINTS = {
        "tepat_waktu": 10,
        "telat": 7,
        "izin_sebagian": 5,
        "izin_seharian": 2,
    }

    def __init__(self, bot):
        self.bot = bot

        # Lock agar proses save JSON tidak bentrok
        self.db_lock = asyncio.Lock()

        self.attendance_data = self.load_db()

        print("[ATTENDANCE] StaffAttendance Cog loaded.")

    # ============================================================
    # DATABASE
    # ============================================================

    def load_db(self):
        """
        Membaca database JSON.

        Jika file tidak ada:
            return {}

        Jika JSON rusak:
            return {}
        """

        if not os.path.exists(self.DB_FILE):
            print(
                f"[ATTENDANCE] Database {self.DB_FILE} belum ada. "
                "Database baru akan dibuat otomatis."
            )
            return {}

        try:
            with open(self.DB_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, dict):
                print(
                    "[ATTENDANCE] Format database tidak valid. "
                    "Menggunakan database kosong."
                )
                return {}

            print(
                f"[ATTENDANCE] Database berhasil dimuat. "
                f"Total tanggal: {len(data)}"
            )

            return data

        except json.JSONDecodeError as e:
            print(
                f"[ATTENDANCE] JSON database rusak: {e}. "
                "Menggunakan database kosong."
            )
            return {}

        except Exception as e:
            print(
                f"[ATTENDANCE] Gagal memuat database: {e}"
            )
            return {}

    def save_db(self):
        """
        Menyimpan database JSON.
        """

        try:
            temp_file = f"{self.DB_FILE}.tmp"

            with open(
                temp_file,
                "w",
                encoding="utf-8"
            ) as file:
                json.dump(
                    self.attendance_data,
                    file,
                    indent=4,
                    ensure_ascii=False
                )

            # Replace lebih aman daripada langsung menulis file utama
            os.replace(temp_file, self.DB_FILE)

        except Exception as e:
            print(
                f"[ATTENDANCE] Gagal menyimpan database: {e}"
            )

    async def safe_save_db(self):
        """
        Save database dengan lock.
        """

        async with self.db_lock:
            self.save_db()

    # ============================================================
    # TIMEZONE WIB
    # ============================================================

    def get_wib_time(self):
        """
        Mendapatkan waktu WIB (UTC+7).
        """

        utc_now = datetime.now(timezone.utc)

        wib_timezone = timezone(
            timedelta(hours=7)
        )

        return utc_now.astimezone(wib_timezone)

    # ============================================================
    # HELPER STAFF
    # ============================================================

    def is_staff(self, member):
        """
        Mengecek apakah user memiliki salah satu
        role staff nanZ.
        """

        if not isinstance(member, discord.Member):
            return False

        if member.bot:
            return False

        return any(
            role.id in self.STAFF_ROLE_IDS
            for role in member.roles
        )

    # ============================================================
    # HELPER CHANNEL
    # ============================================================

    async def check_channel(self, ctx):
        """
        Command absensi hanya dapat digunakan
        di channel absensi.
        """

        if ctx.channel.id != self.ATTENDANCE_CHANNEL_ID:
            await ctx.reply(
                f"❌ Perintah ini hanya dapat digunakan "
                f"di channel khusus absensi "
                f"(<#{self.ATTENDANCE_CHANNEL_ID}>)!"
            )
            return False

        return True

    # ============================================================
    # HELPER RECORD
    # ============================================================

    def ensure_date(self, date_str):
        """
        Memastikan struktur tanggal tersedia.
        """

        if date_str not in self.attendance_data:
            self.attendance_data[date_str] = {}

        if not isinstance(
            self.attendance_data[date_str],
            dict
        ):
            self.attendance_data[date_str] = {}

    # ============================================================
    # COMMAND: ABSEN
    # ============================================================

    @commands.command(name="absen")
    async def absen(self, ctx):

        if not await self.check_channel(ctx):
            return

        if not self.is_staff(ctx.author):
            await ctx.reply(
                "❌ Perintah ini khusus untuk Staff nanZ!"
            )
            return

        now = self.get_wib_time()

        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        member_id = str(ctx.author.id)

        self.ensure_date(date_str)

        # --------------------------------------------------------
        # CEK SUDAH ABSEN / IZIN
        # --------------------------------------------------------

        if member_id in self.attendance_data[date_str]:

            existing = self.attendance_data[
                date_str
            ][member_id]

            status = existing.get(
                "status",
                "Tidak diketahui"
            )

            await ctx.reply(
                f"⚠️ Kamu sudah tercatat hari ini "
                f"dengan status: **{status}**."
            )
            return

        # --------------------------------------------------------
        # JAM BUKA ABSEN
        # --------------------------------------------------------

        current_hour = now.hour

        if current_hour < 4:

            await ctx.reply(
                "⏳ Absen harian belum dibuka!\n"
                "Absen mulai pukul **04:00 WIB**."
            )
            return

        # --------------------------------------------------------
        # STATUS
        # --------------------------------------------------------

        if current_hour < 12 or (
            current_hour == 12
            and now.minute == 0
        ):
            status = "Tepat Waktu"
            color = discord.Color.green()

        else:
            status = "Telat"
            color = discord.Color.orange()

        # --------------------------------------------------------
        # SIMPAN
        # --------------------------------------------------------

        self.attendance_data[
            date_str
        ][member_id] = {

            "name": ctx.author.display_name,

            "time": time_str,

            "status": status,

            "reason": "-",
        }

        await self.safe_save_db()

        # --------------------------------------------------------
        # EMBED
        # --------------------------------------------------------

        embed = discord.Embed(
            title="📋 Berhasil Absen nanZ (WIB)",
            description=(
                f"Terima kasih, "
                f"**{ctx.author.mention}** "
                f"telah melakukan absensi."
            ),
            color=color
        )

        embed.add_field(
            name="Waktu Absen",
            value=f"`{time_str} WIB`",
            inline=True
        )

        embed.add_field(
            name="Status",
            value=f"**{status}**",
            inline=True
        )

        embed.set_footer(
            text=f"Tanggal: {date_str}"
        )

        await ctx.send(embed=embed)

    # ============================================================
    # COMMAND: IZIN
    # ============================================================

    @commands.command(name="izin")
    async def izin(
        self,
        ctx,
        *,
        keterangan: str = None
    ):

        if not await self.check_channel(ctx):
            return

        if not self.is_staff(ctx.author):
            await ctx.reply(
                "❌ Perintah ini khusus untuk Staff nanZ!"
            )
            return

        if not keterangan:

            await ctx.reply(
                "⚠️ Format izin kurang lengkap!\n\n"
                "• Contoh Seharian:\n"
                "`!izin Sakit demam`\n\n"
                "• Contoh Sebagian Waktu:\n"
                "`!izin Sampai pulang sekolah - Urusan keluarga`"
            )
            return

        now = self.get_wib_time()

        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        member_id = str(ctx.author.id)

        self.ensure_date(date_str)

        # --------------------------------------------------------
        # CEK DUPLIKAT
        # --------------------------------------------------------

        if member_id in self.attendance_data[date_str]:

            await ctx.reply(
                "⚠️ Kamu sudah tercatat "
                "melakukan absensi/izin hari ini."
            )
            return

        # --------------------------------------------------------
        # DETEKSI IZIN SEBAGIAN
        # --------------------------------------------------------

        keyword_partial = [
            "sampai",
            "jam",
            "pulang",
            "setengah",
            "menyusul"
        ]

        keterangan_lower = keterangan.lower()

        is_partial = any(
            keyword in keterangan_lower
            for keyword in keyword_partial
        )

        if is_partial:
            status_label = "Izin (Sebagian Waktu)"
            poin_izin = self.POINTS["izin_sebagian"]

        else:
            status_label = "Izin (Seharian)"
            poin_izin = self.POINTS["izin_seharian"]

        # --------------------------------------------------------
        # SIMPAN
        # --------------------------------------------------------

        self.attendance_data[
            date_str
        ][member_id] = {

            "name": ctx.author.display_name,

            "time": time_str,

            "status": status_label,

            "reason": keterangan,
        }

        await self.safe_save_db()

        # --------------------------------------------------------
        # EMBED
        # --------------------------------------------------------

        embed = discord.Embed(
            title="📝 Pengajuan Izin Tercatat",
            description=(
                f"Staff **{ctx.author.mention}** "
                f"mengajukan **{status_label}**."
            ),
            color=discord.Color.gold()
        )

        embed.add_field(
            name="Keterangan / Alasan",
            value=keterangan,
            inline=False
        )

        embed.add_field(
            name="Nilai Absensi",
            value=f"**{poin_izin} poin**",
            inline=True
        )

        embed.set_footer(
            text=(
                f"Dicatat pada pukul "
                f"{time_str} WIB | {date_str}"
            )
        )

        await ctx.send(embed=embed)

    # ============================================================
    # COMMAND: REKAP HARIAN
    # ============================================================

    @commands.command(name="rekapabsen")
    async def rekap_absen(self, ctx):

        if not await self.check_channel(ctx):
            return

        if not self.is_staff(ctx.author):
            await ctx.reply("🤫 **Rahasia!**")
            return

        now = self.get_wib_time()

        date_str = now.strftime("%Y-%m-%d")

        daily_records = self.attendance_data.get(
            date_str,
            {}
        )

        embed = discord.Embed(
            title="📊 Rekap Absensi & Izin Staff nanZ (WIB)",
            description=f"Tanggal: **{date_str}**",
            color=discord.Color.blue()
        )

        if not daily_records:

            embed.description += (
                "\n\n*Belum ada data absensi "
                "atau izin hari ini.*"
            )

        else:

            desc_list = []

            for member_id, info in daily_records.items():

                status = info.get(
                    "status",
                    "Tidak diketahui"
                )

                if "Tepat Waktu" in status:
                    icon = "🟢"

                elif "Telat" in status:
                    icon = "🟠"

                else:
                    icon = "🟡"

                if info.get("reason", "-") != "-":

                    detail = (
                        f" — **{status}** "
                        f"(*{info.get('reason')}*)"
                    )

                else:

                    detail = (
                        f" — **{status}** "
                        f"(`{info.get('time', '-')}`)"
                    )

                desc_list.append(
                    f"{icon} <@{member_id}>{detail}"
                )

            text = "\n".join(desc_list)

            # Discord embed description max 4096 karakter
            if len(text) <= 4000:

                embed.add_field(
                    name="Daftar Kehadiran & Izin",
                    value=text,
                    inline=False
                )

            else:

                # Pecah jika terlalu panjang
                chunks = []

                current = ""

                for line in desc_list:

                    if len(current) + len(line) + 1 > 3900:

                        chunks.append(current)

                        current = line

                    else:

                        if current:
                            current += "\n"

                        current += line

                if current:
                    chunks.append(current)

                for index, chunk in enumerate(chunks):

                    embed.add_field(
                        name=(
                            "Daftar Kehadiran & Izin"
                            if index == 0
                            else "Lanjutan"
                        ),
                        value=chunk,
                        inline=False
                    )

        await ctx.send(embed=embed)

    # ============================================================
    # HELPER: FORMAT BULAN
    # ============================================================

    def parse_month_year(
        self,
        bulan,
        tahun
    ):
        """
        Mengubah input bulan/tahun menjadi format valid.

        Contoh:
            10 2026
            9 2026
            09 2026
        """

        now = self.get_wib_time()

        if not bulan:
            month = now.month

        else:

            try:
                month = int(bulan)

            except ValueError:
                return None, None, (
                    "❌ Bulan harus berupa angka "
                    "antara **1-12**."
                )

            if month < 1 or month > 12:
                return None, None, (
                    "❌ Bulan harus berada "
                    "antara **1-12**."
                )

        if not tahun:
            year = now.year

        else:

            try:
                year = int(tahun)

            except ValueError:
                return None, None, (
                    "❌ Tahun harus berupa angka. "
                    "Contoh: `2026`."
                )

            if year < 2000 or year > 2100:
                return None, None, (
                    "❌ Tahun tidak valid."
                )

        return month, year, None

    # ============================================================
    # HELPER: BUAT SUMMARY BULANAN
    # ============================================================

    def create_empty_summary(
        self,
        name="Unknown"
    ):
        """
        Struktur data default satu staff.
        """

        return {
            "name": name,
            "tepat_waktu": 0,
            "telat": 0,
            "izin_sebagian": 0,
            "izin_seharian": 0,
            "nilai": 0,
            "total_hari": 0,
        }

    # ============================================================
    # COMMAND: REKAP BULANAN
    # ============================================================

    @commands.command(name="rekapbulanan")
    async def rekap_bulanan(
        self,
        ctx,
        bulan: str = None,
        tahun: str = None
    ):

        if not await self.check_channel(ctx):
            return

        if not self.is_staff(ctx.author):
            await ctx.reply("🤫 **Rahasia!**")
            return

        # --------------------------------------------------------
        # VALIDASI BULAN / TAHUN
        # --------------------------------------------------------

        month, year, error = self.parse_month_year(
            bulan,
            tahun
        )

        if error:

            await ctx.reply(error)
            return

        target_prefix = f"{year:04d}-{month:02d}"

        # --------------------------------------------------------
        # SUMMARY
        # --------------------------------------------------------

        summary = {}

        guild = ctx.guild

        # --------------------------------------------------------
        # DAFTARKAN SEMUA STAFF AKTIF DI SERVER
        # --------------------------------------------------------

        if guild is not None:

            for member in guild.members:

                if member.bot:
                    continue

                if not self.is_staff(member):
                    continue

                member_id = str(member.id)

                summary[member_id] = (
                    self.create_empty_summary(
                        member.display_name
                    )
                )

        # --------------------------------------------------------
        # BACA SELURUH DATABASE
        # --------------------------------------------------------
        #
        # PENTING:
        #
        # Kita TIDAK hanya mengambil:
        # attendance_data[hari_ini]
        #
        # Kita loop SEMUA tanggal:
        #
        # 2026-10-01
        # 2026-10-02
        # 2026-10-03
        # dst.
        #
        # Kemudian hanya tanggal dengan prefix:
        #
        # 2026-10
        #
        # yang dihitung.
        #
        # Jadi data hari kemarin tetap masuk.
        # --------------------------------------------------------

        monthly_date_count = 0
        monthly_record_count = 0

        for date_key, records in self.attendance_data.items():

            # Pastikan key berupa string
            if not isinstance(date_key, str):
                continue

            # ----------------------------------------------------
            # FILTER BULAN
            # ----------------------------------------------------

            if not date_key.startswith(
                target_prefix + "-"
            ):
                continue

            # ----------------------------------------------------
            # VALIDASI FORMAT TANGGAL
            # ----------------------------------------------------

            try:

                datetime.strptime(
                    date_key,
                    "%Y-%m-%d"
                )

            except ValueError:

                # Abaikan key JSON yang bukan tanggal valid
                continue

            monthly_date_count += 1

            if not isinstance(records, dict):
                continue

            # ----------------------------------------------------
            # BACA SETIAP STAFF PADA TANGGAL TERSEBUT
            # ----------------------------------------------------

            for member_id, info in records.items():

                if not isinstance(info, dict):
                    continue

                monthly_record_count += 1

                member_id = str(member_id)

                # ------------------------------------------------
                # STAFF YANG TIDAK LAGI ADA DI SERVER
                # ------------------------------------------------

                if member_id not in summary:

                    summary[member_id] = (
                        self.create_empty_summary(
                            info.get(
                                "name",
                                "Unknown"
                            )
                        )
                    )

                # ------------------------------------------------
                # UPDATE NAMA
                # ------------------------------------------------

                discord_member = None

                if guild is not None:

                    try:
                        discord_member = guild.get_member(
                            int(member_id)
                        )
                    except (ValueError, TypeError):
                        discord_member = None

                if discord_member is not None:

                    summary[
                        member_id
                    ]["name"] = (
                        discord_member.display_name
                    )

                else:

                    summary[
                        member_id
                    ]["name"] = info.get(
                        "name",
                        summary[
                            member_id
                        ]["name"]
                    )

                # ------------------------------------------------
                # STATUS
                # ------------------------------------------------

                status = str(
                    info.get(
                        "status",
                        ""
                    )
                )

                summary[
                    member_id
                ]["total_hari"] += 1

                # ------------------------------------------------
                # TEPAT WAKTU
                # ------------------------------------------------

                if "Tepat Waktu" in status:

                    summary[
                        member_id
                    ]["tepat_waktu"] += 1

                    summary[
                        member_id
                    ]["nilai"] += (
                        self.POINTS[
                            "tepat_waktu"
                        ]
                    )

                # ------------------------------------------------
                # TELAT
                # ------------------------------------------------

                elif "Telat" in status:

                    summary[
                        member_id
                    ]["telat"] += 1

                    summary[
                        member_id
                    ]["nilai"] += (
                        self.POINTS[
                            "telat"
                        ]
                    )

                # ------------------------------------------------
                # IZIN SEBAGIAN
                # ------------------------------------------------

                elif "Izin (Sebagian Waktu)" in status:

                    summary[
                        member_id
                    ]["izin_sebagian"] += 1

                    summary[
                        member_id
                    ]["nilai"] += (
                        self.POINTS[
                            "izin_sebagian"
                        ]
                    )

                # ------------------------------------------------
                # IZIN SEHARIAN
                # ------------------------------------------------

                elif "Izin (Seharian)" in status:

                    summary[
                        member_id
                    ]["izin_seharian"] += 1

                    summary[
                        member_id
                    ]["nilai"] += (
                        self.POINTS[
                            "izin_seharian"
                        ]
                    )

        # --------------------------------------------------------
        # SORTING
        # --------------------------------------------------------
        #
        # Tetap menggunakan sistem ranking lama:
        #
        # 1. Nilai
        # 2. Total hari tercatat
        # 3. Tepat waktu
        # 4. Lebih sedikit telat
        #
        # Ini hanya pengurutan data, bukan perubahan sistem poin.
        # --------------------------------------------------------

        ranked = sorted(
            summary.items(),
            key=lambda item: (
                item[1]["nilai"],
                item[1]["total_hari"],
                item[1]["tepat_waktu"],
                -item[1]["telat"],
            ),
            reverse=True
        )

        # --------------------------------------------------------
        # EMBED INFORMASI
        # --------------------------------------------------------

        if month < 10:
            month_display = f"0{month}"
        else:
            month_display = str(month)

        # --------------------------------------------------------
        # JIKA TIDAK ADA STAFF
        # --------------------------------------------------------

        if not ranked:

            embed = discord.Embed(
                title=(
                    f"📈 Rekap Evaluasi Bulanan Staff "
                    f"({target_prefix})"
                ),
                description=(
                    f"Tidak ditemukan staff pada server "
                    f"untuk periode **{month_display}/{year}**."
                ),
                color=discord.Color.dark_blue()
            )

            embed.set_footer(
                text="Staff Attendance • nanZ Server"
            )

            await ctx.send(embed=embed)
            return

        # --------------------------------------------------------
        # BUAT BLOK STAFF
        # --------------------------------------------------------

        result_lines = []

        for rank, (
            member_id,
            data
        ) in enumerate(
            ranked,
            start=1
        ):

            if rank == 1:
                medal = "🥇"

            elif rank == 2:
                medal = "🥈"

            elif rank == 3:
                medal = "🥉"

            else:
                medal = f"`#{rank}`"

            result_lines.append(
                f"{medal} <@{member_id}> "
                f"(`{data['name']}`)\n"
                f"   > 💯 Nilai Bulanan: "
                f"**{data['nilai']} poin**\n"
                f"   > 🟢 Tepat Waktu: "
                f"**{data['tepat_waktu']}**\n"
                f"   > 🟠 Telat: "
                f"**{data['telat']}**\n"
                f"   > 🟡 Izin Sebagian: "
                f"**{data['izin_sebagian']}**\n"
                f"   > 🟤 Izin Seharian: "
                f"**{data['izin_seharian']}**"
            )

        # --------------------------------------------------------
        # PAGINATION
        # --------------------------------------------------------

        STAFF_PER_EMBED = 10

        chunks = [
            result_lines[
                i:i + STAFF_PER_EMBED
            ]
            for i in range(
                0,
                len(result_lines),
                STAFF_PER_EMBED
            )
        ]

        total_pages = len(chunks)

        # --------------------------------------------------------
        # KIRIM EMBED
        # --------------------------------------------------------

        for page, staff_chunk in enumerate(
            chunks,
            start=1
        ):

            staff_text = "\n\n".join(
                staff_chunk
            )

            # ----------------------------------------------------
            # HALAMAN PERTAMA
            # ----------------------------------------------------

            if page == 1:

                description = (
                    f"Akumulasi absensi bulan "
                    f"**{month_display}/{year}**.\n\n"

                    f"**Sistem Poin:**\n"
                    f"🟢 Tepat Waktu "
                    f"`{self.POINTS['tepat_waktu']}`\n"
                    f"🟠 Telat "
                    f"`{self.POINTS['telat']}`\n"
                    f"🟡 Izin Sebagian "
                    f"`{self.POINTS['izin_sebagian']}`\n"
                    f"🟤 Izin Seharian "
                    f"`{self.POINTS['izin_seharian']}`\n\n"

                    f"📅 **Hari tercatat: "
                    f"{monthly_date_count} hari**\n"

                    f"📋 **Total data absensi/izin: "
                    f"{monthly_record_count}**\n"

                    f"👥 **Total Staff: "
                    f"{len(ranked)} orang**\n\n"

                    f"Staff tanpa absensi pada bulan ini "
                    f"tetap ditampilkan dengan nilai "
                    f"**0 poin**.\n\n"

                    f"{staff_text}"
                )

            # ----------------------------------------------------
            # HALAMAN BERIKUTNYA
            # ----------------------------------------------------

            else:

                description = staff_text

            embed_page = discord.Embed(
                title=(
                    f"📈 Rekap Evaluasi Bulanan Staff "
                    f"({target_prefix})"
                ),
                description=description,
                color=discord.Color.dark_blue()
            )

            embed_page.set_footer(
                text=(
                    f"Halaman {page}/{total_pages} • "
                    f"Staff Attendance nanZ"
                )
            )

            await ctx.send(
                embed=embed_page
            )

    # ============================================================
    # COMMAND: HELP ABSEN
    # ============================================================

    @commands.command(
        name="helpabsen",
        aliases=[
            "absenhelp",
            "bantuabsen"
        ]
    )
    async def help_absen(self, ctx):

        if not await self.check_channel(ctx):
            return

        if not self.is_staff(ctx.author):
            await ctx.reply(
                "❌ Perintah ini khusus untuk Staff nanZ!"
            )
            return

        embed = discord.Embed(
            title="📖 Daftar Perintah Absensi nanZ",
            description=(
                "Berikut adalah daftar command "
                "absensi yang dapat digunakan:"
            ),
            color=discord.Color.purple()
        )

        # --------------------------------------------------------
        # ABSEN
        # --------------------------------------------------------

        embed.add_field(
            name="`!absen`",
            value=(
                "Melakukan absensi harian.\n"
                "• **Tepat Waktu:** "
                "04:00 - 12:00 WIB\n"
                "• **Telat:** "
                "Di atas 12:00 WIB"
            ),
            inline=False
        )

        # --------------------------------------------------------
        # IZIN
        # --------------------------------------------------------

        embed.add_field(
            name="`!izin [keterangan]`",
            value=(
                "Mengajukan izin seharian "
                "atau sebagian waktu.\n"
                "• Seharian: "
                "`!izin Sakit demam` "
                "→ **2 poin**\n"
                "• Sebagian: "
                "`!izin Sampai pulang sekolah - "
                "Urusan keluarga` "
                "→ **5 poin**"
            ),
            inline=False
        )

        # --------------------------------------------------------
        # REKAP HARIAN
        # --------------------------------------------------------

        embed.add_field(
            name="`!rekapabsen`",
            value=(
                "Melihat rekap absensi dan izin "
                "seluruh staff pada hari ini."
            ),
            inline=False
        )

        # --------------------------------------------------------
        # REKAP BULANAN
        # --------------------------------------------------------

        embed.add_field(
            name="`!rekapbulanan [bulan] [tahun]`",
            value=(
                "Melihat akumulasi absensi "
                "seluruh staff dalam satu bulan.\n"
                "Data seluruh tanggal dalam bulan "
                "tersebut akan dihitung.\n"
                "• Contoh: "
                "`!rekapbulanan 10 2026`"
            ),
            inline=False
        )

        # --------------------------------------------------------
        # FOOTER
        # --------------------------------------------------------

        embed.set_footer(
            text="Zona Waktu: WIB | Khusus Staff nanZ"
        )

        await ctx.send(
            embed=embed
        )

    # ============================================================
    # LISTENER: KEAMANAN PESAN
    # ============================================================

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        # --------------------------------------------------------
        # Hanya cek pesan yang mengandung kata tertentu
        # --------------------------------------------------------

        content_lower = (
            message.content.lower()
        )

        trigger_keywords = [
            "absen",
            "siapa yang telat",
            "siapa yang izin",
            "rekap absen",
            "data absen",
        ]

        if not any(
            keyword in content_lower
            for keyword in trigger_keywords
        ):
            return

        # --------------------------------------------------------
        # CEK STAFF
        # --------------------------------------------------------

        is_staff = (
            isinstance(
                message.author,
                discord.Member
            )
            and self.is_staff(
                message.author
            )
        )

        if not is_staff:

            try:

                await message.reply(
                    "🤫 **Rahasia!**",
                    mention_author=False
                )

            except discord.HTTPException:
                pass


# ================================================================
# SETUP
# ================================================================

async def setup(bot):
    await bot.add_cog(
        StaffAttendance(bot)
    )