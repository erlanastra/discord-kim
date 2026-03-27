import discord
from discord.ext import commands
import aiomysql
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests
from io import BytesIO
import os

# ================= DATABASE =================
DB_CONFIG = {
    "host": "sql5.freesqldatabase.com",
    "port": 3306,
    "user": "sql5820722",
    "password": "m6GjypbQk3",
    "db": "sql5820722"
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE_DIR, "..", "assets")

CARD_SIZE = (1000, 600)

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = None
        bot.loop.create_task(self.init_db())

    async def init_db(self):
        self.pool = await aiomysql.create_pool(**DB_CONFIG, autocommit=True)

    # ================= BADGE =================
    def get_badge(self, streak):
        if streak >= 50: return "🔥"
        if streak >= 20: return "⚡"
        if streak >= 10: return "💎"
        if streak >= 5: return "🏆"
        return "⭐"

    # ================= CARD =================
    async def generate_card(self, member, data, streak):
        bg = Image.open(os.path.join(ASSETS, "bg_space.jpg")).convert("RGBA")
        bg = bg.resize(CARD_SIZE)

        width, height = bg.size

        card_w, card_h = 860, 400
        card_x = (width - card_w)//2
        card_y = (height - card_h)//2

        # ================= SHADOW =================
        shadow = Image.new("RGBA", (card_w+40, card_h+40), (0,0,0,0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle((20,20,card_w+20,card_h+20),40, fill=(0,0,0,180))
        shadow = shadow.filter(ImageFilter.GaussianBlur(25))
        bg.paste(shadow, (card_x-20, card_y-20), shadow)

        # ================= GLASS =================
        glass = bg.crop((card_x, card_y, card_x+card_w, card_y+card_h))
        glass = glass.filter(ImageFilter.GaussianBlur(15))

        mask = Image.new("L", (card_w, card_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0,0,card_w,card_h), 40, fill=255)
        glass.putalpha(mask)

        draw = ImageDraw.Draw(glass)

        # ================= GLOW CARD =================
        glow_layer = Image.new("RGBA", (card_w, card_h), (0,0,0,0))
        glow_draw = ImageDraw.Draw(glow_layer)
        glow_draw.rounded_rectangle((0,0,card_w,card_h),40, outline=(120,180,255,180), width=6)
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(12))
        glass.paste(glow_layer, (0,0), glow_layer)

        # HEADER (fix biar rounded)
        header = Image.new("RGBA", (card_w, 90), (15, 20, 60, 220))

        header_mask = Image.new("L", (card_w, 90), 0)
        ImageDraw.Draw(header_mask).rounded_rectangle((0,0,card_w,180),40, fill=255)

        header.putalpha(header_mask)
        glass.paste(header, (0,0), header)

        # FONT
        def f(name, size):
            path = os.path.join(ASSETS, name)
            return ImageFont.truetype(path, size) if os.path.exists(path) else ImageFont.load_default()

        font_big = f("font_bold.ttf", 60)
        font_mid = f("font_regular.ttf", 28)
        font_small = f("font_small.ttf", 20)

        # LOGO
        logo_path = os.path.join(ASSETS, "logo.png")
        if os.path.exists(logo_path):
            logo = Image.open(logo_path).resize((60,60))
            glass.paste(logo, (25,15), logo)

        draw.text((100, 25), "nanZ Server", font=font_mid, fill=(180,220,255))
        draw.text((100, 55), "OFFICIAL MEMBER CARD", font=font_small, fill=(150,150,150))

        # ================= AVATAR =================
        try:
            response = requests.get(member.display_avatar.url)
            avatar = Image.open(BytesIO(response.content)).resize((170,170))
        except:
            avatar = Image.new("RGB",(170,170),(100,100,100))

        avatar = avatar.convert("RGBA")

        mask_av = Image.new("L",(170,170),0)
        ImageDraw.Draw(mask_av).rounded_rectangle((0,0,170,170),35,fill=255)
        avatar.putalpha(mask_av)

        # glow avatar
        glow = avatar.filter(ImageFilter.GaussianBlur(25))
        glass.paste(glow,(45,125),glow)
        glass.paste(avatar,(55,135),avatar)

        # ================= DATA =================
        name = data.get("name","Unknown")
        gender = data.get("gender","-")
        age = data.get("age","-")
        hobby = data.get("hobby","-")

        # ================= NAME (NAIKIN + CENTER VISUAL) =================
        name_y = 110  # ⬅️ sebelumnya 130

        # shadow glow
        draw.text((262, name_y+2), name.upper(), font=font_big, fill=(0,0,0))
        draw.text((260, name_y), name.upper(), font=font_big, fill=(255, 0, 200))

        start_y = 190
        gap = 45

        badge = self.get_badge(streak)

        def draw_data(y, label, value, color=(220,220,220)):
            label_x = 260
            value_x = 450  # ⬅️ ini yang bikin sejajar

            text_label = f"{label} :"

            # shadow label
            draw.text((label_x+2, y+2), text_label, font=font_mid, fill=(0,0,0))
            draw.text((label_x, y), text_label, font=font_mid, fill=color)

            # shadow value
            draw.text((value_x+2, y+2), str(value), font=font_mid, fill=(0,0,0))
            draw.text((value_x, y), str(value), font=font_mid, fill=color)

            # garis bawah glow
            draw.line((260, y+32, 800, y+32), fill=(120,180,255), width=2)

        # DATA
        draw_data(start_y, "Gender", gender)
        draw_data(start_y+gap, "Age", age)
        draw_data(start_y+gap*2, "Hobby", hobby)
        draw_data(start_y+gap*3, "Streak", f"{streak} hari", color=(255,100,255))

        # ================= BORDER =================
        border = ImageDraw.Draw(glass)
        border.rounded_rectangle((0,0,card_w-1,card_h-1),40,outline=(120,180,255),width=3)

        bg.paste(glass,(card_x,card_y),glass)

        buffer = BytesIO()
        bg.save(buffer,"PNG")
        buffer.seek(0)
        return buffer

    # ================= GROUP COMMAND =================
    @commands.group(name="profilenanZ", invoke_without_command=True)
    async def profile(self, ctx):
        if not self.pool:
            return await ctx.send("Database belum siap.")

        gid, uid = str(ctx.guild.id), str(ctx.author.id)

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT * FROM profiles WHERE guild_id=%s AND user_id=%s",
                    (gid, uid)
                )
                data = await cursor.fetchone()

                await cursor.execute(
                    "SELECT streak FROM streaks WHERE guild_id=%s AND user_id=%s",
                    (gid, uid)
                )
                s = await cursor.fetchone()

        if not data:
            return await ctx.send("Belum ada profil. Gunakan !profilenanZ set")

        streak = s['streak'] if s else 0

        card = await self.generate_card(ctx.author, data, streak)
        await ctx.send(file=discord.File(card, "idcard.png"))

    # ================= SUBCOMMAND SET =================
    @profile.command(name="set")
    async def set_profile(self, ctx, *, input_data: str):
        if not self.pool:
            return await ctx.send("Database belum siap.")

        try:
            name, age, gender, hobby, bio = [x.strip() for x in input_data.split("|")]
        except:
            return await ctx.send("❌ Format salah!\nContoh:\nNama | Umur | Gender | Hobi | Bio")

        gid, uid = str(ctx.guild.id), str(ctx.author.id)

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:

                await cursor.execute(
                    "SELECT * FROM profiles WHERE guild_id=%s AND user_id=%s",
                    (gid, uid)
                )
                exists = await cursor.fetchone()

                if exists:
                    await cursor.execute("""
                        UPDATE profiles 
                        SET name=%s, age=%s, gender=%s, hobby=%s
                        WHERE guild_id=%s AND user_id=%s
                    """, (name, age, gender, hobby, gid, uid))
                else:
                    await cursor.execute("""
                        INSERT INTO profiles (guild_id, user_id, name, age, gender, hobby)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (gid, uid, name, age, gender, hobby))

        await ctx.send("✅ Profil berhasil disimpan!")

# ================= SETUP =================
async def setup(bot):
    await bot.add_cog(Profile(bot))