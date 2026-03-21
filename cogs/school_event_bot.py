import discord
from discord.ext import commands, tasks
import aiomysql
import random
import asyncio
from collections import deque
from datetime import datetime, timedelta

# ====================== CONFIG ======================
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

        # ====================== SOAL PANJANG ======================
        self.quiz_questions = [
            ("Ibukota Korea Selatan?", "seoul"),
            ("Siapa presiden pertama Indonesia?", "soekarno"),
            ("Bahasa Inggris 'kucing'?", "cat"),
            ("5 x 7 = ?", "35"),
            ("Planet terbesar di tata surya?", "jupiter"),
            ("Siapa penemu lampu pijar?", "edison"),
            ("Bulan pertama kalender Masehi?", "januari"),
            ("Simbol kimia emas?", "au"),
            ("Hewan tercepat di darat?", "cheetah"),
            ("Hewan lambat di darat?", "kura-kura"),
            ("Bahasa pemrograman untuk Discord Bot?", "python"),
            ("Huruf pertama abjad?", "a"),
            ("Pahlawan nasional dari Jawa Barat?", "djuanda"),
            ("Siapa penemu telepon?", "bell"),
            ("Ibukota Perancis?", "paris"),
            ("Benua terbesar?", "asia"),
            ("Bahasa Inggris dari 'air'?", "water"),
            ("Lagu kebangsaan Indonesia?", "indonesia raya"),
            ("Tahun kemerdekaan Indonesia?", "1945"),
            ("Hewan simbol kekuatan?", "singha")
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
            ("Aku hitam saat bersih dan putih saat kotor. Apa aku?", "papan tulis")
        ]

        self.fast_questions = [
            "aku anak rajin",
            "nanz academy rules",
            "discord nanZ forever",
            "event seru banget",
            "aku siap menang",
            "challenge accepted",
            "squad nanZ",
            "role elite nanZ",
            "aku top 1",
            "winner nanZ"
        ]

        # Inisialisasi database dan auto event + reminder
        bot.loop.create_task(self.init_db())
        bot.loop.create_task(self.init_auto_events())
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

    # ====================== EVENT COMMAND ======================
    @commands.command()
    async def event(self, ctx_or_channel):
        """Manual atau auto event"""
        if self.event_active:
            return
        self.event_active = True

        # ambil channel
        if isinstance(ctx_or_channel, discord.TextChannel):
            channel = ctx_or_channel
        else:
            channel = ctx_or_channel.channel

        event_type = random.choice([
            "quiz", "math", "riddle", "fast", "spam", "reaction"
        ])

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
        await self.cleanup_channel(channel)
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

        while True:
            msg = await self.bot.wait_for("message", check=check)
            user = msg.author
            counter[user] = counter.get(user,0)+1
            if counter[user]>=5:
                await self.give_reward(user, channel, "aktif")
                break

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
            return m.channel==channel and not m.author.bot
        try:
            while True:
                msg = await self.bot.wait_for("message", timeout=30, check=check)
                if msg.content.lower()==answer.lower():
                    await self.give_reward(msg.author, channel, role_type)
                    break
        except:
            await channel.send("⏳ Tidak ada jawaban benar!")

    # ====================== GIVE REWARD ======================
    async def give_reward(self, user, channel, role_type):
        guild = channel.guild
        role_map = {"aktif":ROLE_AKTIF,"prestasi":ROLE_PRESTASI,"elite":ROLE_ELITE}
        role = guild.get_role(role_map[role_type])

        # FIFO limit role
        queue = self.role_holders[role_type]
        if len(queue)>=LIMITS[role_type]:
            old_user_id = queue.popleft()
            old_member = guild.get_member(old_user_id)
            if old_member:
                await old_member.remove_roles(role)
        queue.append(user.id)
        await user.add_roles(role)

        # simpan ke leaderboard sementara
        self.leaderboard[user.id] = self.leaderboard.get(user.id,0)+1

        # simpan ke database
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO event_winners (guild_id,user_id,event_type,win_count)
                    VALUES (%s,%s,%s,1)
                    ON DUPLICATE KEY UPDATE
                    win_count=win_count+1,
                    last_win=NOW()
                """,(guild.id,user.id,role_type))

        # embed pemenang
        embed = discord.Embed(
            title="🏆 Pemenang Event!",
            description=f"{user.mention} berhasil memenangkan event!",
            color=0xf39c12
        )
        embed.add_field(name="🎖️ Reward", value=role.name)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="nanZ Academy • sistem sekolah aktif")
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
        embed.set_footer(text="Berlaku 1 jam • nanZ Academy")
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
                            embed.set_footer(text="nanZ Academy • MVP cycle")
                            msg = await channel.send(embed=embed)
                            self.event_messages.append(msg)

    # ====================== AUTO EVENT + REMINDER ======================
    async def init_auto_events(self):
        # Set 3 jam acak tiap hari untuk event
        self.auto_event_times = sorted(random.sample(range(9,21), 3))  # jam 9-20
        print(f"Auto event schedule (jam): {self.auto_event_times}")
        self.bot.loop.create_task(self.auto_event_loop())

    async def auto_event_loop(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(CHANNEL_EVENT)

        while not self.bot.is_closed():
            now = datetime.now()
            for event_hour in self.auto_event_times:
                event_time = now.replace(hour=event_hour, minute=0, second=0, microsecond=0)
                delta = (event_time - now).total_seconds()

                if 0 < delta <= 600:  # 10 menit reminder
                    await channel.send("⚡ Dalam 10 menit lagi akan ada event dadakan!")
                elif 0 < delta <= 180:  # 3 menit reminder
                    await channel.send("⏳ Tinggal 3 menit lagi event akan segera dimulai!")
                elif 0 < delta <= 60:  # 1 menit reminder + jenis event
                    event_type = random.choice([
                        "Quiz", "Math", "Riddle", "Fast Typing", "Spam", "Reaction"
                    ])
                    await channel.send(f"🎯 Event sebentar lagi! Jenis event: **{event_type}**")
                    try:
                        await self.event(channel)
                        await asyncio.sleep(3600)  # jangan trigger lagi 1 jam
                    except Exception as e:
                        print(f"Auto event error: {e}")
            await asyncio.sleep(30)  # cek tiap 30 detik

# ====================== SETUP ======================
async def setup(bot):
    await bot.add_cog(SchoolEvent(bot))