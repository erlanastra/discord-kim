import asyncio
import io
import json
import math
import os
import random
import re

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# =========================================================
# KONFIGURASI — booster_data.json lama tetap digunakan
# =========================================================
BOOST_CHANNEL_ID = 1554100419637149838
ROLE_REQ_CHANNEL_ID = 1515029186530771077
ROLE_PRIME_ID = 1561383676019736596
ROLE_ELITE_ID = 1561384548158152744
DATA_FILE = "booster_data.json"

E_NITRO = "<a:nitro:1553688995635011635>"
E_BLUE = "<a:blue:1512787254312042496>"
E_PURPLE = "<a:purple:1512787191234035803>"

FONT_BOLD    = "fonts/LEMONMILK-Bold.otf"
FONT_MEDIUM  = "fonts/LEMONMILK-Medium.otf"
FONT_REGULAR = "fonts/LEMONMILK-Regular.otf"
_FALLBACKS   = ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf")

PALETTES = {
    "prime": dict(bg_top=(18, 10, 45), bg_bot=(40, 20, 80), a=(130, 80, 255), b=(80, 180, 255),
                  sa=(160, 120, 255), sb=(150, 210, 255), card=(30, 15, 65)),
    "elite": dict(bg_top=(30, 20, 8), bg_bot=(72, 46, 12), a=(235, 165, 30), b=(255, 215, 100),
                  sa=(255, 200, 90), sb=(255, 235, 170), card=(50, 32, 10)),
}

W, H = 800, 340


def _font(path, size):
    for p in (path, *_FALLBACKS):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))


def _fit_font(draw, text, path, start, max_w, min_size=24):
    size = start
    while size > min_size:
        f = _font(path, size)
        b = draw.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= max_w:
            return f, text
        size -= 2
    f = _font(path, min_size)
    while text and draw.textbbox((0, 0), text + "…", font=f)[2] > max_w:
        text = text[:-1]
    return f, text + "…"


def _fit_size(draw, lines, path, start, max_w, min_size=10):
    size = start
    while size > min_size:
        f = _font(path, size)
        if max(draw.textlength(line, font=f) for line in lines) <= max_w:
            return f
        size -= 1
    return _font(path, min_size)


def _prepare_avatar(avatar_bytes, size):
    av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4, size * 4), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(av, (0, 0), mask)
    return out


def _make_fx(seed=7):
    rng = random.Random(seed)
    stars = [{"x": rng.uniform(0, W), "y": rng.uniform(0, H), "r": rng.uniform(1.0, 2.6),
              "tw": rng.random(), "a": rng.randint(90, 200)} for _ in range(70)]
    sparkles = [{"x": rng.uniform(15, W - 15), "y": rng.uniform(12, H - 12),
                 "s": rng.uniform(5, 10), "tw": rng.uniform(0.4, 1.0)} for _ in range(13)]
    bubbles = [{"x": rng.uniform(0, W), "y": rng.uniform(0, H),
                "r": rng.uniform(3, 7), "a": rng.randint(80, 150)} for _ in range(18)]
    return {"stars": stars, "sparkles": sparkles, "bubbles": bubbles}


def _sparkle_poly(x, y, sz):
    q = sz * 0.25
    return [(x, y - sz), (x + q, y - q), (x + sz, y), (x + q, y + q),
            (x, y + sz), (x - q, y + q), (x - sz, y), (x - q, y - q)]


def _background(fx, P):
    bg = Image.new("RGB", (W, H))
    bd = ImageDraw.Draw(bg)
    for y in range(H):
        bd.line([(0, y), (W, y)], fill=_lerp_color(P["bg_top"], P["bg_bot"], y / H))
    base = bg.convert("RGBA")

    orbs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od0 = ImageDraw.Draw(orbs)
    for ox, oy, br, oc in [(W * .10, H * .20, 140, P["a"]), (W * .90, H * .70, 140, P["b"]),
                           (W * .50, H * .00, 110, P["a"])]:
        for st in range(br, 0, -5):
            od0.ellipse([ox - st, oy - st, ox + st, oy + st],
                        fill=(*oc, _clamp(60 * (st / br) ** 2.8 * 0.85)))
    base = Image.alpha_composite(base, orbs)

    aur = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ad = ImageDraw.Draw(aur)
    for by, amp, k, off, col, a in [(235, 30, 2, 0.0, P["b"], 60), (268, 24, 3, 2.0, P["a"], 75),
                                    (300, 18, 4, 4.0, P["sb"], 50)]:
        pts = [(x, by + amp * math.sin(math.tau * k * x / W + off)) for x in range(0, W + 10, 10)]
        ad.polygon(pts + [(W, H), (0, H)], fill=(*col, a))
    base = Image.alpha_composite(base, aur.filter(ImageFilter.GaussianBlur(6)))

    fl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fl)
    for item in fx["stars"]:
        r, tw = item["r"], item["tw"]
        fd.ellipse([item["x"] - r, item["y"] - r, item["x"] + r, item["y"] + r],
                   fill=(*_lerp_color(P["a"], P["b"], tw), _clamp(item["a"] * (0.45 + 0.55 * tw))) )
    for item in fx["sparkles"]:
        tw = item["tw"]
        fd.polygon(_sparkle_poly(item["x"], item["y"], item["s"] * (0.35 + 0.65 * tw)),
                   fill=(*_lerp_color(P["sb"], P["sa"], tw), _clamp(70 + 185 * tw)))
    for bubble in fx["bubbles"]:
        r, a = bubble["r"], bubble["a"]
        fd.ellipse([bubble["x"] - r, bubble["y"] - r, bubble["x"] + r, bubble["y"] + r], outline=(255, 255, 255, a), width=1)
        fd.ellipse([bubble["x"] - r * .35, bubble["y"] - r * .35, bubble["x"] + r * .1, bubble["y"] + r * .1],
                   fill=(255, 255, 255, a))
    return Image.alpha_composite(base, fl)


def render_booster_card(avatar_bytes: bytes, name: str, tier: int, total: int, boosts: int = 1) -> bytes:
    """boosts == 1 -> Prime Boost; boosts >= 2 -> Elite Boost."""
    elite = boosts >= 2
    P = PALETTES["elite" if elite else "prime"]
    A, B, SA, SB, CARD_BG = P["a"], P["b"], P["sa"], P["sb"], P["card"]
    AVB = 176
    avatar = _prepare_avatar(avatar_bytes, AVB)
    base = _background(_make_fx(seed=11), P)
    cx, cy = 662, 170
    TX0, TX1 = 46, 440

    def edge(y):
        return 560 - 90 * y / H

    S = 2
    pan = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    pdr = ImageDraw.Draw(pan)
    pdr.polygon([(0, 0), (edge(0) * S, 0), (edge(H) * S, H * S), (0, H * S)], fill=(*CARD_BG, 190))
    for y in range(0, H, 3):
        pdr.line([(edge(y) * S, y * S), (edge(y + 3) * S, (y + 3) * S)],
                 fill=(*_lerp_color(B, A, y / H), 255), width=7)
    for y in range(0, H, 3):
        pdr.line([((edge(y) - 14) * S, y * S), ((edge(y + 3) - 14) * S, (y + 3) * S)],
                 fill=(*_lerp_color(B, A, y / H), 90), width=3)
    base = Image.alpha_composite(base, pan.resize((W, H), Image.LANCZOS))

    spot = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spot)
    for r, a in [(190, 40), (160, 55), (135, 70)]:
        sd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*A, a))
    base = Image.alpha_composite(base, spot.filter(ImageFilter.GaussianBlur(22)))

    rr = AVB // 2 + 12
    ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse([cx - rr - 26, cy - rr - 26, cx + rr + 26, cy + rr + 26], outline=(255, 255, 255, 40), width=1)
    rd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(255, 255, 255, 60), width=2)
    box = [cx - rr, cy - rr, cx + rr, cy + rr]
    rd.arc(box, -70, 40, fill=(*SB, 255), width=6)
    rd.arc(box, 110, 220, fill=(*SA, 255), width=6)
    if elite:
        b2 = [cx - rr - 13, cy - rr - 13, cx + rr + 13, cy + rr + 13]
        rd.arc(b2, 20, 100, fill=(*SA, 255), width=4)
        rd.arc(b2, 200, 280, fill=(*SB, 255), width=4)
    for i in range(8):
        a = i * math.tau / 8 + 0.3
        R2 = rr + 26
        px, py = cx + R2 * math.cos(a), cy + R2 * math.sin(a)
        rad = 4 if i % 2 == 0 else 3
        rd.ellipse([px - rad, py - rad, px + rad, py + rad], fill=(*(SB if i % 2 == 0 else SA), 235))
    for sx, sy, sz in [(cx - 118, cy - 96, 11), (cx + 120, cy - 82, 9), (cx + 104, cy + 100, 12)]:
        rd.polygon(_sparkle_poly(sx, sy, sz), fill=(*SB, 235))
    base = Image.alpha_composite(base, ring)
    base.alpha_composite(avatar, (cx - AVB // 2, cy - AVB // 2))

    bx, by, br = cx + 66, cy + 66, 18
    bd = ImageDraw.Draw(base)
    bd.ellipse([bx - br - 4, by - br - 4, bx + br + 4, by + br + 4], fill=(*CARD_BG, 255))
    bd.ellipse([bx - br, by - br, bx + br, by + br], fill=(*A, 255))
    if elite:
        bd.text((bx, by), "x2", font=_font(FONT_BOLD, 16), fill=(255, 255, 255, 255), anchor="mm")
    else:
        bd.polygon(_sparkle_poly(bx, by, 12), fill=(255, 255, 255, 255))

    tl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(tl)
    f_pil = _font(FONT_MEDIUM, 14)
    f_lab = _font(FONT_MEDIUM, 15)
    pil = "ELITE BOOST" if elite else "PRIME BOOST"
    pw = int(td.textlength(pil, font=f_pil)) + 56
    td.rounded_rectangle([TX0, 32, TX0 + pw, 62], radius=15, fill=(*A, 235))
    td.polygon(_sparkle_poly(TX0 + 20, 47, 7), fill=(255, 255, 255, 255))
    td.text((TX0 + 36, 47), pil, font=f_pil, fill=(255, 255, 255, 255), anchor="lm")
    td.text((TX0, 96), "TERIMA KASIH BANYAK," if elite else "TERIMA KASIH,",
            font=f_lab, fill=(*SB, 255), anchor="lm")
    f_name, name_fit = _fit_font(td, name, FONT_BOLD, 52, TX1 - TX0)
    td.text((TX0, 140), name_fit, font=f_name, fill=(255, 255, 255, 255), anchor="lm")
    for x in range(TX0, TX0 + 260):
        f = 1 - (x - TX0) / 260
        c = (*_lerp_color(B, A, (x - TX0) / 260), _clamp(255 * f ** 0.7))
        td.line([(x, 176), (x, 178)], fill=c)
    if elite:
        lines = ["Dua boost sekaligus! Kamu bener-bener bikin",
                 "sekolah nanZ naik level, kamu luar biasa!"]
    else:
        lines = ["Boost kamu bikin sekolah nanZ makin keren,",
                 "makasih udah jadi murid yang peduli sama sekolah!"]
    f_body = _fit_size(td, lines, FONT_REGULAR, 16, TX1 - TX0)
    td.text((TX0, 204), lines[0], font=f_body, fill=(235, 230, 220, 255), anchor="lm")
    td.text((TX0, 230), lines[1], font=f_body, fill=(235, 230, 220, 255), anchor="lm")
    c1, c2 = f"Level {tier}", f"Total {total} Boost"
    f_chip = _fit_size(td, [c1, c2], FONT_MEDIUM, 14, 150)
    cyy = 290

    def chip(x, txt, col):
        w = int(td.textlength(txt, font=f_chip)) + 52
        td.rounded_rectangle([x, cyy - 15, x + w, cyy + 15], radius=15, fill=(*col, 56),
                             outline=(*col, 217), width=1)
        ix = x + 19
        td.ellipse([ix - 10, cyy - 10, ix + 10, cyy + 10], fill=(*col, 255))
        td.polygon(_sparkle_poly(ix, cyy, 6), fill=(255, 255, 255, 255))
        td.text((x + 36, cyy), txt, font=f_chip, fill=(255, 255, 255, 255), anchor="lm")
        return x + w

    nx = chip(TX0, c1, B)
    chip(nx + 12, c2, A)
    base = Image.alpha_composite(base, tl)
    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


# Hanya pesan boost individual, bukan pesan pencapaian tier server.
BOOST_MESSAGE_TYPES = {discord.MessageType.premium_guild_subscription}


class Booster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = self._load()
        self._lock = asyncio.Lock()
        self._ready_synced = set()
        self._pending_fallback = set()
        self._guild_sync_tasks = {}
        self._processed_message_ids = set()

    # -------------------- STORAGE --------------------
    def _load(self):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Format JSON tidak valid")
            return data
        except FileNotFoundError:
            print(f"[Booster] {DATA_FILE} belum ada; file akan dibuat saat data disimpan.")
            return {}
        except Exception as e:
            # Jangan lanjut dengan data kosong jika file lama rusak.
            print(f"[Booster] GAGAL membaca {DATA_FILE}: {e}")
            raise

    def _save(self):
        temp = DATA_FILE + ".tmp"
        try:
            with open(temp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, DATA_FILE)
        except Exception as e:
            print(f"[Booster] GAGAL menyimpan data: {e}")
            try:
                if os.path.exists(temp):
                    os.remove(temp)
            except OSError:
                pass

    def _get(self, guild_id, user_id):
        return int(self.data.get(str(guild_id), {}).get(str(user_id), 0))

    def _set(self, guild_id, user_id, count):
        group = self.data.setdefault(str(guild_id), {})
        key = str(user_id)
        if count <= 0:
            group.pop(key, None)
        else:
            group[key] = int(count)
        self._save()

    # -------------------- ROLES --------------------
    async def apply_roles(self, member, count):
        guild = member.guild
        prime = guild.get_role(ROLE_PRIME_ID)
        elite = guild.get_role(ROLE_ELITE_ID)
        wanted = elite if count >= 2 else prime if count == 1 else None
        try:
            for role in (prime, elite):
                if role is None:
                    continue
                if role == wanted and role not in member.roles:
                    await member.add_roles(role, reason="nanZ Booster synchronization")
                elif role != wanted and role in member.roles:
                    await member.remove_roles(role, reason="nanZ Booster synchronization")
        except discord.Forbidden:
            print(f"[Booster] Tidak bisa mengatur role {member}; periksa Manage Roles/hierarki role.")
        except discord.HTTPException as e:
            print(f"[Booster] Gagal mengatur role: {e}")

    # -------------------- NOTIFICATION --------------------
    async def send_boost_embed(self, member, boosts):
        channel = member.guild.get_channel(BOOST_CHANNEL_ID)
        if channel is None:
            print(f"[Booster] Channel {BOOST_CHANNEL_ID} tidak ditemukan.")
            return

        elite = boosts >= 2
        tier = member.guild.premium_tier
        total = member.guild.premium_subscription_count or 0
        file = None

        try:
            avatar = await member.display_avatar.replace(size=256, format="png").read()
            loop = asyncio.get_running_loop()
            png = await loop.run_in_executor(
                None, render_booster_card, avatar, member.display_name, tier, total, boosts
            )
            file = discord.File(io.BytesIO(png), filename="booster.png")
        except Exception as e:
            print(f"[Booster] Gagal membuat PNG: {e}")

        if elite:
            title = "Elite Boost Baru!"
            desc = (f"{E_NITRO} Terima kasih {member.mention} sudah ngeboost **2x** di **nanZ Server**!\n"
                    f"> {E_BLUE} `Req Role:` <#{ROLE_REQ_CHANNEL_ID}>")
            color = discord.Color.from_rgb(235, 165, 30)
        else:
            title = "Prime Boost Baru!"
            desc = (f"{E_NITRO} Terima kasih {member.mention} sudah ngeboost **nanZ Server**!\n"
                    f"> {E_BLUE} `Req Role:` <#{ROLE_REQ_CHANNEL_ID}>")
            color = discord.Color.from_rgb(130, 80, 255)

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_footer(text="nanZ School Boost System")
        kwargs = {}
        if file:
            embed.set_image(url="attachment://booster.png")
            kwargs["file"] = file
        await channel.send(
            content=member.mention,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            **kwargs,
        )

    # -------------------- BOOST EVENT --------------------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.type not in BOOST_MESSAGE_TYPES:
            return
        member = message.author
        if not isinstance(member, discord.Member):
            member = message.guild.get_member(message.author.id)
        if member is None or member.bot:
            return

        # Setiap pesan boost individual baru dihitung satu kali.
        # Jika isi pesan hanya angka, angka itu dianggap jumlah tambahan.
        async with self._lock:
            if message.id in self._processed_message_ids:
                return
            self._processed_message_ids.add(message.id)
            if len(self._processed_message_ids) > 3000:
                self._processed_message_ids.clear()
                self._processed_message_ids.add(message.id)

            content = (message.content or "").strip()
            match = re.fullmatch(r"\d+", content)
            added = max(1, int(match.group(0))) if match else 1
            new_count = self._get(message.guild.id, member.id) + added
            self._set(message.guild.id, member.id, new_count)

        await self.apply_roles(member, new_count)
        try:
            await self.send_boost_embed(member, new_count)
        except discord.HTTPException as e:
            print(f"[Booster] Gagal mengirim notifikasi: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.premium_since == after.premium_since:
            return

        # Semua boost member berhenti.
        if before.premium_since is not None and after.premium_since is None:
            async with self._lock:
                self._set(after.guild.id, after.id, 0)
            await self.apply_roles(after, 0)
            return

        # Fallback untuk boost baru jika pesan sistem tidak diterima.
        if before.premium_since is None and after.premium_since is not None:
            key = (after.guild.id, after.id)
            if key in self._pending_fallback:
                return
            self._pending_fallback.add(key)
            try:
                await asyncio.sleep(5)
                async with self._lock:
                    # Bila on_message sudah mencatat boost, jangan tambah lagi.
                    if self._get(after.guild.id, after.id) > 0:
                        return
                    self._set(after.guild.id, after.id, 1)
                await self.apply_roles(after, 1)
                try:
                    await self.send_boost_embed(after, 1)
                except discord.HTTPException as e:
                    print(f"[Booster] Gagal mengirim notifikasi fallback: {e}")
            finally:
                self._pending_fallback.discard(key)

    # -------------------- LOST BOOST RECONCILIATION --------------------
    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        old_total = before.premium_subscription_count or 0
        new_total = after.premium_subscription_count or 0
        if new_total >= old_total:
            return
        old_task = self._guild_sync_tasks.get(after.id)
        if old_task and not old_task.done():
            old_task.cancel()
        self._guild_sync_tasks[after.id] = asyncio.create_task(self._reconcile_later(after.id))

    async def _reconcile_later(self, guild_id):
        try:
            await asyncio.sleep(6)
        except asyncio.CancelledError:
            return
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return
        try:
            active_members = list(guild.premium_subscribers)
        except Exception as e:
            print(f"[Booster] Tidak bisa membaca booster aktif: {e}")
            return
        active = {m.id: m for m in active_members}

        async with self._lock:
            group = self.data.setdefault(str(guild_id), {})
            for uid in list(group):
                if int(uid) not in active:
                    group.pop(uid, None)
            for uid in active:
                group.setdefault(str(uid), 1)

            tracked = sum(int(value) for value in group.values())
            actual = guild.premium_subscription_count or 0
            excess = tracked - actual
            elites = [uid for uid, count in group.items() if int(count) >= 2 and int(uid) in active]
            changed_uid = None

            # Jangan menebak jika tidak jelas siapa kehilangan satu boost.
            if excess > 0 and len(elites) == 1:
                changed_uid = int(elites[0])
                group[str(changed_uid)] = max(1, int(group[str(changed_uid)]) - excess)
            self._save()

        if changed_uid is not None:
            member = guild.get_member(changed_uid)
            if member:
                await self.apply_roles(member, self._get(guild_id, changed_uid))
        elif excess > 0 and len(elites) > 1:
            channel = guild.get_channel(BOOST_CHANNEL_ID)
            if channel:
                await channel.send(
                    "⚠️ **Sinkronisasi Booster perlu pemeriksaan admin.**\n"
                    "Jumlah boost server berkurang, tetapi ada beberapa Elite Boost. "
                    "Bot tidak menebak siapa yang kehilangan boost. Verifikasi data, "
                    "lalu gunakan `!boost_set @member 1` bila sudah dipastikan."
                )

    # -------------------- STARTUP SYNC: NO NOTIFICATIONS --------------------
    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            if guild.id in self._ready_synced:
                continue
            try:
                active_members = list(guild.premium_subscribers)
            except Exception as e:
                print(f"[Booster] Gagal membaca booster {guild.id}: {e}")
                continue
            active = {m.id: m for m in active_members}

            async with self._lock:
                group = self.data.setdefault(str(guild.id), {})
                # Hapus anggota yang sudah tidak boost.
                for uid in list(group):
                    if int(uid) not in active:
                        group.pop(uid, None)
                # Pertahankan hitungan JSON yang sudah ada.
                # Booster lama yang belum tercatat diberi default 1.
                for uid in active:
                    group.setdefault(str(uid), 1)
                self._save()

            # Tidak memanggil send_boost_embed di startup.
            for uid, member in active.items():
                await self.apply_roles(member, self._get(guild.id, uid))

            # Lepas role dari member yang sudah tidak boost.
            for role_id in (ROLE_PRIME_ID, ROLE_ELITE_ID):
                role = guild.get_role(role_id)
                if role:
                    for member in list(role.members):
                        if member.id not in active:
                            await self.apply_roles(member, 0)

            self._ready_synced.add(guild.id)
            print(f"[Booster] Sync {guild.name} selesai; {len(active)} booster aktif; tanpa notifikasi.")

    # -------------------- ADMIN COMMANDS --------------------
    @commands.command(name="boost_set")
    @commands.has_permissions(administrator=True)
    async def boost_set(self, ctx, member: discord.Member, jumlah: int):
        """Atur manual: !boost_set @member 0|1|2. 2 berarti 2 atau lebih."""
        if jumlah not in (0, 1, 2):
            await ctx.send("Jumlah harus 0, 1, atau 2 (2 berarti dua atau lebih).",
                           allowed_mentions=discord.AllowedMentions.none())
            return
        async with self._lock:
            self._set(ctx.guild.id, member.id, jumlah)
        await self.apply_roles(member, jumlah)
        await ctx.send(f"Jumlah boost {member.mention} diatur menjadi **{jumlah}**.",
                       allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name="test_boost")
    @commands.has_permissions(administrator=True)
    async def test_boost(self, ctx, jumlah: int = 1, member: discord.Member = None):
        """Tes notifikasi tanpa mengubah data/role: !test_boost 1 atau !test_boost 2 @member"""
        if jumlah not in (1, 2):
            await ctx.send("Gunakan `!test_boost 1` atau `!test_boost 2`.",
                           allowed_mentions=discord.AllowedMentions.none())
            return
        try:
            await self.send_boost_embed(member or ctx.author, jumlah)
            await ctx.send("Tes notifikasi boost selesai.",
                           allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException as e:
            await ctx.send(f"Tes notifikasi gagal: {e}",
                           allowed_mentions=discord.AllowedMentions.none())


async def setup(bot):
    await bot.add_cog(Booster(bot))
