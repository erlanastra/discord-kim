import discord
from discord.ext import commands, tasks
import aiomysql
import random
import asyncio
from collections import deque
from datetime import datetime, timedelta

# ====================== CONFIG ======================
EVENT_ROLE = 1453103644244316343  # ganti dengan ID role event
ROLE_AKTIF = 1484770531235467314     # ⭐ Aktif
ROLE_PRESTASI = 1474224495467434125  # 📘 Prestasi
ROLE_ELITE = 1484770367754211409     # 👑 Elite
CHANNEL_EVENT = 1484770254067466380  # Channel event

LIMITS = {
    "aktif": 5,
    "prestasi": 3,
    "elite": 1
}

DB_CONFIG = {
    "host": "sql5.freesqldatabase.com",
    "port": 3306,
    "user": "sql5820722",
    "password": "m6GjypbQk3",
    "db": "sql5820722",
    "autocommit": True
}

MVP_INTERVAL_DAYS = 3  # tiap 3 hari hitung MVP

# ====================== COG ======================
class SchoolEvent(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = None
        self.event_active = False

        # FIFO untuk limit role
        self.role_holders = {
            "aktif": deque(),
            "prestasi": deque(),
            "elite": deque()
        }

        # Menyimpan pesan event untuk auto cleanup
        self.event_messages = []

        # Leaderboard sementara

        self.leaderboard = {}
        self.triggered_events = set()
        self.auto_event_times = []
        self.event_lock = asyncio.Lock()
        self.sent_reminders = set()


        # ====================== SOAL PANJANG ======================
        self.quiz_questions = [
            # 🌍 GEOGRAFI (50)
            ("Ibukota Thailand?", "bangkok"),
            ("Ibukota Malaysia?", "kuala lumpur"),
            ("Ibukota Filipina?", "manila"),
            ("Ibukota Vietnam?", "hanoi"),
            ("Ibukota Jepang?", "tokyo"),
            ("Ibukota China?", "beijing"),
            ("Ibukota Korea Selatan?", "seoul"),
            ("Ibukota India?", "new delhi"),
            ("Ibukota Pakistan?", "islamabad"),
            ("Ibukota Arab Saudi?", "riyadh"),
            ("Ibukota Mesir?", "kairo"),
            ("Ibukota Turki?", "ankara"),
            ("Ibukota Rusia?", "moskow"),
            ("Ibukota Inggris?", "london"),
            ("Ibukota Perancis?", "paris"),
            ("Ibukota Jerman?", "berlin"),
            ("Ibukota Italia?", "roma"),
            ("Ibukota Spanyol?", "madrid"),
            ("Ibukota Kanada?", "ottawa"),
            ("Ibukota Amerika Serikat?", "washington dc"),
            ("Ibukota Australia?", "canberra"),
            ("Ibukota Brazil?", "brasilia"),
            ("Ibukota Argentina?", "buenos aires"),
            ("Ibukota Afrika Selatan?", "pretoria"),
            ("Ibukota Belanda?", "amsterdam"),
            ("Ibukota Swiss?", "bern"),
            ("Ibukota Swedia?", "stockholm"),
            ("Ibukota Norwegia?", "oslo"),
            ("Ibukota Finlandia?", "helsinki"),
            ("Ibukota Denmark?", "copenhagen"),
            ("Benua terbesar?", "asia"),
            ("Benua terkecil?", "australia"),
            ("Samudra terbesar?", "pasifik"),
            ("Gunung tertinggi dunia?", "everest"),
            ("Sungai terpanjang?", "nil"),
            ("Negara terbesar dunia?", "rusia"),
            ("Negara terkecil dunia?", "vatikan"),
            ("Gurun terbesar dunia?", "sahara"),
            ("Laut terdalam dunia?", "mariana trench"),
            ("Negara dengan populasi terbanyak?", "india"),
            ("Negara kepulauan terbesar?", "indonesia"),
            ("Negara dengan menara eiffel?", "perancis"),
            ("Negara asal pizza?", "italia"),
            ("Negara asal sushi?", "jepang"),
            ("Negara asal kimchi?", "korea"),
            ("Negara asal samba?", "brazil"),
            ("Negara asal kangguru?", "australia"),
            ("Negara asal tulip?", "belanda"),
            ("Negara asal piramida?", "mesir"),
            ("Negara asal colosseum?", "italia"),

            # 📚 SEJARAH & UMUM (50)
            ("Presiden pertama Indonesia?", "soekarno"),
            ("Presiden kedua Indonesia?", "soeharto"),
            ("Wakil presiden pertama?", "hatta"),
            ("Tahun kemerdekaan Indonesia?", "1945"),
            ("Tanggal kemerdekaan Indonesia?", "17 agustus"),
            ("Hari pahlawan?", "10 november"),
            ("Sumpah pemuda tanggal?", "28 oktober"),
            ("Lambang negara Indonesia?", "garuda"),
            ("Mata uang Indonesia?", "rupiah"),
            ("Bahasa nasional Indonesia?", "indonesia"),
            ("Siapa penemu lampu?", "edison"),
            ("Penemu telepon?", "bell"),
            ("Penemu pesawat?", "wright"),
            ("Penemu listrik?", "faraday"),
            ("Perang dunia kedua berakhir?", "1945"),
            ("Benua asal manusia pertama?", "afrika"),
            ("Kerajaan terbesar di Indonesia?", "majapahit"),
            ("Tokoh pendidikan Indonesia?", "ki hajar dewantara"),
            ("Ibu kota Indonesia sebelum Jakarta?", "yogyakarta"),
            ("Lagu kebangsaan Indonesia?", "indonesia raya"),
            ("Hari pendidikan nasional?", "2 mei"),
            ("Hari kartini?", "21 april"),
            ("Hari buruh?", "1 mei"),
            ("Hari sumpah pemuda?", "28 oktober"),
            ("Hari kesaktian pancasila?", "1 oktober"),
            ("Agama mayoritas Indonesia?", "islam"),
            ("Kitab suci Islam?", "quran"),
            ("Kitab suci Kristen?", "alkitab"),
            ("Kitab suci Hindu?", "weda"),
            ("Kitab suci Buddha?", "tripitaka"),
            ("Alat musik tradisional Jawa?", "gamelan"),
            ("Rumah adat Minangkabau?", "rumah gadang"),
            ("Tari dari Bali?", "kecak"),
            ("Pakaian adat Jawa?", "kebaya"),
            ("Bahasa daerah Jawa?", "jawa"),
            ("Suku terbesar Indonesia?", "jawa"),
            ("Pulau terbesar Indonesia?", "kalimantan"),
            ("Danau terbesar Indonesia?", "toba"),
            ("Gunung tertinggi Indonesia?", "jayawijaya"),
            ("Provinsi paling barat Indonesia?", "aceh"),
            ("Provinsi paling timur Indonesia?", "papua"),
            ("Bandara terbesar Indonesia?", "soekarno hatta"),
            ("Pelabuhan terbesar Indonesia?", "tanjung priok"),
            ("Maskapai nasional Indonesia?", "garuda indonesia"),
            ("Simbol sila pertama?", "bintang"),
            ("Simbol sila kedua?", "rantai"),
            ("Simbol sila ketiga?", "pohon beringin"),
            ("Simbol sila keempat?", "kepala banteng"),
            ("Simbol sila kelima?", "padi kapas"),

            # 🔢 MATEMATIKA (30)
            ("15 x 6 = ?", "90"),
            ("144 : 12 = ?", "12"),
            ("25 x 4 = ?", "100"),
            ("81 : 9 = ?", "9"),
            ("12 x 12 = ?", "144"),
            ("50 + 75 = ?", "125"),
            ("200 - 89 = ?", "111"),
            ("7 x 8 = ?", "56"),
            ("36 : 6 = ?", "6"),
            ("11 x 11 = ?", "121"),
            ("13 x 7 = ?", "91"),
            ("9 x 12 = ?", "108"),
            ("100 : 4 = ?", "25"),
            ("45 + 55 = ?", "100"),
            ("88 - 33 = ?", "55"),
            ("6 x 9 = ?", "54"),
            ("14 x 5 = ?", "70"),
            ("99 + 1 = ?", "100"),
            ("120 : 10 = ?", "12"),
            ("16 x 4 = ?", "64"),
            ("18 x 3 = ?", "54"),
            ("21 x 2 = ?", "42"),
            ("30 + 70 = ?", "100"),
            ("150 - 50 = ?", "100"),
            ("8 x 11 = ?", "88"),
            ("20 x 5 = ?", "100"),
            ("27 + 13 = ?", "40"),
            ("60 : 5 = ?", "12"),
            ("9 x 7 = ?", "63"),
            ("1000 - 1 = ?", "999"),

            # 🌱 SAINS + TEKNOLOGI + RANDOM (70)
            ("Planet terdekat matahari?", "merkurius"),
            ("Planet terbesar?", "jupiter"),
            ("Planet merah?", "mars"),
            ("Satelit bumi?", "bulan"),
            ("Gas untuk bernapas?", "oksigen"),
            ("Air membeku?", "0"),
            ("Air mendidih?", "100"),
            ("Organ pernapasan?", "paru paru"),
            ("Gaya tarik bumi?", "gravitasi"),
            ("Bagian tumbuhan fotosintesis?", "daun"),

            ("Singkatan CPU?", "central processing unit"),
            ("Singkatan RAM?", "random access memory"),
            ("Browser google?", "chrome"),
            ("Perusahaan windows?", "microsoft"),
            ("Bahasa discord bot?", "python"),
            ("Platform video?", "youtube"),
            ("Aplikasi chat?", "whatsapp"),
            ("Aplikasi server?", "discord"),
            ("OS iPhone?", "ios"),
            ("OS Android berbasis?", "linux"),

            ("Superhero palu?", "thor"),
            ("Superhero tameng?", "captain america"),
            ("Superhero laba laba?", "spiderman"),
            ("Karakter naruto?", "naruto"),
            ("Karakter one piece?", "luffy"),
            ("Game sandbox?", "minecraft"),
            ("Game battle royale?", "pubg"),
            ("Game moba?", "mobile legends"),
            ("Film dinosaurus?", "jurassic park"),
            ("Film marvel terakhir?", "endgame"),

            ("Olahraga bola 11 orang?", "sepak bola"),
            ("Olahraga raket?", "badminton"),
            ("Durasi bola?", "90 menit"),
            ("Olahraga ring?", "basket"),
            ("Olahraga tongkat bola kecil?", "golf"),

            ("Lawan kata panas?", "dingin"),
            ("Lawan kata besar?", "kecil"),
            ("Lawan kata cepat?", "lambat"),
            ("Lawan kata terang?", "gelap"),
            ("Lawan kata mahal?", "murah"),

            ("Apa selalu naik?", "umur"),
            ("Apa bisa pecah tanpa disentuh?", "janji"),
            ("Apa punya kaki tapi tidak jalan?", "meja"),
            ("Apa punya mata tapi tidak melihat?", "jarum"),
            ("Semakin diambil semakin besar?", "lubang"),
        ]

        self.riddle_questions = [
            ("Aku punya tangan tapi tidak bisa memegang. Apa aku?", "jam"),
            ("Semakin diisi semakin ringan, apa itu?", "balon"),
            ("Aku selalu datang tapi tidak pernah terlihat. Apa aku?", "waktu"),
            ("Aku punya kunci tapi tidak bisa membuka pintu. Apa aku?", "piano"),
            ("Aku punya gigi tapi tidak bisa menggigit. Apa aku?", "sisir"),
            ("Semakin banyak kau ambil, semakin besar aku. Apa aku?", "lubang"),
            ("Aku selalu naik tapi tidak pernah turun. Apa aku?", "umur"),
            ("Aku punya wajah tapi tidak bisa tersenyum. Apa aku?", "jam"),
            ("Aku bisa pecah tapi tidak berdarah. Apa aku?", "telur"),
            ("Aku hitam saat bersih dan putih saat kotor. Apa aku?", "papan tulis"),
            ("Selalu di depan tapi tak terlihat?", "masa depan"),
            ("Mengikuti tapi tak bisa disentuh?", "bayangan"),
            ("Mengisi ruangan tanpa bentuk?", "cahaya"),
            ("Mati saat minum?", "api"),
            ("Punya kota tanpa rumah?", "peta"),
            ("Ringan tapi tak bisa ditahan lama?", "nafas"),
            ("Bisa berjalan tanpa kaki?", "waktu"),
            ("Punya leher tanpa kepala?", "botol"),
            ("Bisa terbang tanpa sayap?", "waktu"),
            ("Semakin gelap semakin terlihat?", "bintang"),
        ]

        self.fast_questions = [
            "nanZ server terbaik",
            "aku siap menang",
            "event nanZ tidak ada lawan",
            "aku akan jadi juara",
            "skill issue detected",
            "no miss typing",
            "focus jangan salah",
            "gas terus tanpa ampun",
            "aku bukan kaleng kaleng",
            "this is my moment",

            # 🔥 lebih panjang
            "aku_pasti_menang_event_ini",
            "nanz_server_superiority",
            "typing_challenge_accepted",
            "no_mistake_full_focus",
            "this_is_my_time_to_win",
        ]

        # Inisialisasi database dan auto event + reminder

        bot.loop.create_task(self.startup())

        if not self.mvp_loop.is_running():
            self.mvp_loop.start()

    # ====================== DATABASE ======================
    async def init_db(self):
        self.pool = await aiomysql.create_pool(**DB_CONFIG)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS event_winners (
                        guild_id VARCHAR(50),
                        user_id VARCHAR(50),
                        event_type VARCHAR(50),
                        win_count INT DEFAULT 1,
                        last_win TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (guild_id, user_id, event_type)
                    )
                """)
    async def startup(self):
        await self.bot.wait_until_ready()
        await self.init_db()
        await self.init_auto_events()
        asyncio.create_task(self.auto_event_loop())

    async def init_auto_events(self):
        self.auto_event_times = sorted(random.sample(range(9,22), 3))
        print(f"Auto event schedule (jam): {self.auto_event_times}")

    # ====================== EVENT COMMAND ======================
    @commands.command()
    @commands.cooldown(1, 300, commands.BucketType.guild)  # 1x / 5 menit
    async def event(self, ctx_or_channel):

        # 🔒 CHECK ROLE (hanya untuk manual command)
        if not isinstance(ctx_or_channel, discord.TextChannel):
            ctx = ctx_or_channel

            if not any(role.id == EVENT_ROLE for role in ctx.author.roles):
                return await ctx.send("❌ Kamu tidak punya akses untuk menjalankan event!")

        async with self.event_lock:
            if self.event_active:
                return await (ctx_or_channel.send("⚠️ Event sedang berjalan!") 
                            if not isinstance(ctx_or_channel, discord.TextChannel) 
                            else ctx_or_channel.send("⚠️ Event sedang berjalan!"))

            self.event_active = True

            # ambil channel
            if isinstance(ctx_or_channel, discord.TextChannel):
                channel = ctx_or_channel
            else:
                channel = ctx_or_channel.channel

            event_type = random.choice([
                "quiz", "math", "riddle", "fast", "spam", "reaction"
            ])

            try:
                if event_type == "quiz":
                    await self.quiz_event(channel)
                elif event_type == "math":
                    await self.math_event(channel)
                elif event_type == "riddle":
                    await self.riddle_event(channel)
                elif event_type == "fast":
                    await self.fast_type_event(channel)
                elif event_type == "spam":
                    await self.spam_event(channel)
                elif event_type == "reaction":
                    await self.reaction_event(channel)

                await self.show_leaderboard(channel)
                asyncio.create_task(self.cleanup_channel(channel))

            except Exception as e:
                print(f"Event error: {e}")

            finally:
                self.event_active = False

    # ====================== EVENT TYPES ======================
    async def quiz_event(self, channel):
        q, a = random.choice(self.quiz_questions)
        embed = discord.Embed(
            title="📘 Quiz Time!",
            description=f"**{q}**\n⏳ Jawab cepat!",
            color=0x3498db
        )
        msg = await channel.send(embed=embed)
        self.event_messages.append(msg)
        await self.wait_answer(channel, a, "prestasi")

    async def math_event(self, channel):
        a, b = random.randint(10,50), random.randint(1,10)
        answer = str(a+b)
        embed = discord.Embed(
            title="🧠 Math Challenge!",
            description=f"Hitung: {a} + {b} = ?",
            color=0x1abc9c
        )
        msg = await channel.send(embed=embed)
        self.event_messages.append(msg)
        await self.wait_answer(channel, answer, "prestasi")

    async def riddle_event(self, channel):
        q, a = random.choice(self.riddle_questions)
        embed = discord.Embed(
            title="🧩 Riddle Time!",
            description=q,
            color=0x9b59b6
        )
        msg = await channel.send(embed=embed)
        self.event_messages.append(msg)
        await self.wait_answer(channel, a, "prestasi")

    async def fast_type_event(self, channel):
        q = random.choice(self.fast_questions)
        embed = discord.Embed(
            title="⚡ Fast Typing!",
            description=f"Ketik teks ini:\n`{q}`",
            color=0xe67e22
        )
        msg = await channel.send(embed=embed)
        self.event_messages.append(msg)
        await self.wait_answer(channel, q, "aktif")

    async def spam_event(self, channel):
        embed = discord.Embed(
            title="🔥 Spam Challenge!",
            description="Kirim 5 pesan tercepat!",
            color=0xf1c40f
        )
        msg = await channel.send(embed=embed)
        self.event_messages.append(msg)

        counter = {}

        def check(m):
            return m.channel == channel and not m.author.bot

        try:
            while True:
                msg = await self.bot.wait_for("message", timeout=30, check=check)
                user = msg.author
                counter[user] = counter.get(user, 0) + 1
                if counter[user] >= 5:
                    await self.give_reward(user, channel, "aktif")
                    break
        except asyncio.TimeoutError:
            await channel.send("⏳ Tidak ada pemenang!")

    async def reaction_event(self, channel):
        embed = discord.Embed(
            title="👍 Reaction Battle!",
            description="React secepatnya!",
            color=0x2ecc71
        )
        msg = await channel.send(embed=embed)
        self.event_messages.append(msg)
        await msg.add_reaction("🔥")

        def check(reaction, user):
            return str(reaction.emoji)=="🔥" and not user.bot

        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=20, check=check)
            await self.give_reward(user, channel, "aktif")
        except:
            await channel.send("⏳ Tidak ada pemenang!")

    # ====================== WAIT ANSWER ======================
    async def wait_answer(self, channel, answer, role_type):
        def check(m):
            return m.channel == channel and not m.author.bot

        try:
            for _ in range(10):  # batasi attempt
                msg = await self.bot.wait_for("message", timeout=30, check=check)
                if msg.content.lower() == answer.lower():
                    await self.give_reward(msg.author, channel, role_type)
                    return
        except asyncio.TimeoutError:
            pass

        await channel.send("⏳ Tidak ada jawaban benar!")

    # ====================== GIVE REWARD ======================
    async def give_reward(self, user, channel, role_type):
        guild = channel.guild

        if not self.pool:
            return

        role_map = {"aktif": ROLE_AKTIF, "prestasi": ROLE_PRESTASI, "elite": ROLE_ELITE}
        role = guild.get_role(role_map[role_type])

        if role is None:
            return

        queue = self.role_holders[role_type]

        if len(queue) >= LIMITS[role_type]:
            old_user_id = queue.popleft()
            old_member = guild.get_member(old_user_id)
            if old_member:
                await old_member.remove_roles(role)

        queue.append(user.id)
        await user.add_roles(role)

        self.leaderboard[user.id] = self.leaderboard.get(user.id, 0) + 1

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO event_winners (guild_id,user_id,event_type,win_count)
                    VALUES (%s,%s,%s,1)
                    ON DUPLICATE KEY UPDATE
                    win_count=win_count+1,
                    last_win=NOW()
                """, (guild.id, user.id, role_type))

        embed = discord.Embed(
            title="🏆 Pemenang Event!",
            description=f"{user.mention} berhasil memenangkan event!",
            color=0xf39c12
        )
        embed.add_field(name="🎖️ Reward", value=role.name)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="nanZ Server • Stay Solid!")

        msg = await channel.send(embed=embed)
        self.event_messages.append(msg)

    # ====================== LEADERBOARD ======================
    async def show_leaderboard(self, channel):
        if not self.leaderboard:
            return
        sorted_lb = sorted(self.leaderboard.items(), key=lambda x:x[1], reverse=True)
        desc=""
        for i,(user_id,score) in enumerate(sorted_lb[:5],start=1):
            user = channel.guild.get_member(user_id)
            if user:
                desc+=f"**{i}. {user.name}** — {score} win\n"
        embed = discord.Embed(
            title="🏆 Leaderboard Sementara",
            description=desc,
            color=0xFFD700
        )
        embed.set_footer(text="Berlaku 1 jam • nanZ Server")
        msg = await channel.send(embed=embed)
        self.event_messages.append(msg)

    # ====================== CLEANUP CHANNEL ======================
    async def cleanup_channel(self, channel):
        await asyncio.sleep(3600)  # 1 jam
        for msg in self.event_messages:
            try: await msg.delete()
            except: pass
        self.event_messages.clear()
        self.leaderboard.clear()

    # ====================== MVP LOOP ======================
    @tasks.loop(hours=24)
    async def mvp_loop(self):
        now = datetime.utcnow()
        if now.weekday()%3==2:  # Hari ke-3
            for guild in self.bot.guilds:
                channel = self.bot.get_channel(CHANNEL_EVENT)
                if channel is None or not self.pool:
                    continue
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("""
                            SELECT user_id,SUM(win_count) as total_wins
                            FROM event_winners
                            WHERE guild_id=%s AND last_win >= NOW() - INTERVAL 3 DAY
                            GROUP BY user_id
                            ORDER BY total_wins DESC
                            LIMIT 5
                        """,(guild.id,))
                        rows = await cur.fetchall()
                        if rows:
                            desc=""
                            for i,(user_id,total) in enumerate(rows,start=1):
                                user = guild.get_member(int(user_id))
                                if user:
                                    desc+=f"**{i}. {user.name}** — {total} win\n"
                            embed = discord.Embed(
                                title="👑 MVP 3 Hari!",
                                description=desc,
                                color=0xffd700
                            )
                            if guild.get_member(int(rows[0][0])):
                                embed.set_thumbnail(url=guild.get_member(int(rows[0][0])).display_avatar.url)
                            embed.set_footer(text="nanZ Server • MVP cycle")
                            msg = await channel.send(embed=embed)
                            self.event_messages.append(msg)

    # ====================== AUTO EVENT + REMINDER ======================
    async def auto_event_loop(self):
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            channel = self.bot.get_channel(CHANNEL_EVENT)

            if channel is None or not self.pool:
                await asyncio.sleep(5)
                continue


            now = datetime.now()

            # reset harian
            if now.hour == 0 and now.minute == 0:
                await self.init_auto_events()
                self.triggered_events.clear()
                self.sent_reminders.clear()

            if not self.auto_event_times:
                await asyncio.sleep(5)
                continue

            for event_hour in self.auto_event_times:
                event_time = now.replace(hour=event_hour, minute=0, second=0, microsecond=0)
                delta = (event_time - now).total_seconds()

                key = f"{now.date()}-{event_hour}"

                if key in self.triggered_events:
                    continue

                # 🔔 REMINDER ANTI SPAM
                if 0 < delta <= 600:
                    rkey = f"{key}-10"
                    if rkey not in self.sent_reminders:
                        await channel.send("⚡ Dalam 10 menit lagi akan ada event dadakan!")
                        self.sent_reminders.add(rkey)

                elif 0 < delta <= 180:
                    rkey = f"{key}-3"
                    if rkey not in self.sent_reminders:
                        await channel.send("⏳ Tinggal 3 menit lagi event akan segera dimulai!")
                        self.sent_reminders.add(rkey)

                elif 0 < delta <= 60:
                    if self.event_active:
                        continue
                    event_type = random.choice([
                        "Quiz", "Math", "Riddle", "Fast Typing", "Spam", "Reaction"
                    ])
                    await channel.send(f"🎯 Event sebentar lagi! Jenis event: **{event_type}**")

                    self.triggered_events.add(key)

                    try:
                        await self.event(channel)
                    except Exception as e:
                        print(f"Auto event error: {e}")

            await asyncio.sleep(20)

# ====================== SETUP ======================
async def setup(bot):
    await bot.add_cog(SchoolEvent(bot))