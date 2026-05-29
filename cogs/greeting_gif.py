import io
import math
import random
from PIL import Image, ImageDraw, ImageFont

FONT_BOLD    = "fonts/LEMONMILK-Bold.otf"
FONT_MEDIUM  = "fonts/LEMONMILK-Medium.otf"
FONT_REGULAR = "fonts/LEMONMILK-Regular.otf"
FONT_LIGHT   = "fonts/LEMONMILK-Light.otf"

THEMES = {
    "pagi": {
        "bg_top":   (18, 10, 45),
        "bg_bot":   (40, 20, 80),
        "accent1":  (130, 80, 255),
        "accent2":  (80, 180, 255),
        "card_bg":  (30, 15, 65),
        "label":    (160, 120, 255),
        "emoji":    "🌅",
        "tagline":  "Rise & Shine, Murid!",
        "sub":      "Semangat pagi, hari baru menanti.",
        "session_label": "SELAMAT PAGI",
    },
    "siang": {
        "bg_top":   (10, 20, 55),
        "bg_bot":   (20, 40, 100),
        "accent1":  (60, 160, 255),
        "accent2":  (120, 60, 240),
        "card_bg":  (15, 25, 70),
        "label":    (100, 180, 255),
        "emoji":    "☀️",
        "tagline":  "Keep Going, Murid!",
        "sub":      "Istirahat sejenak, lanjut lagi!",
        "session_label": "SELAMAT SIANG",
    },
    "sore": {
        "bg_top":   (25, 10, 55),
        "bg_bot":   (55, 20, 90),
        "accent1":  (200, 80, 255),
        "accent2":  (80, 140, 255),
        "card_bg":  (35, 10, 70),
        "label":    (190, 110, 255),
        "emoji":    "🌇",
        "tagline":  "Chill Time, Murid!",
        "sub":      "Nikmati sore yang tenang.",
        "session_label": "SELAMAT SORE",
    },
    "malam": {
        "bg_top":   (5, 5, 25),
        "bg_bot":   (20, 10, 50),
        "accent1":  (90, 60, 200),
        "accent2":  (40, 120, 220),
        "card_bg":  (12, 8, 35),
        "label":    (120, 100, 220),
        "emoji":    "🌙",
        "tagline":  "Good Night, Murid!",
        "sub":      "Istirahat yang nyenyak.",
        "session_label": "SELAMAT MALAM",
    },
}

W, H = 900, 480
TOTAL_FRAMES = 36      # ~3 detik @ 12fps
FPS_DELAY    = 8       # centiseconds per frame (8 = ~12fps)


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _lerp(a, b, t):
    return a + (b - a) * t


def _lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))


def _ease_in_out(t):
    return t * t * (3 - 2 * t)


def _ease_out(t):
    return 1 - (1 - t) ** 3


# ── Seeded particles (posisi konsisten tiap frame) ──
def _make_particles(seed=42, n=55):
    rng = random.Random(seed)
    return [
        {
            "x":     rng.uniform(0, W),
            "y":     rng.uniform(0, H),
            "vx":    rng.uniform(-0.4, 0.4),
            "vy":    rng.uniform(-0.6, -0.15),
            "r":     rng.uniform(1.2, 3.0),
            "alpha": rng.randint(60, 180),
            "phase": rng.uniform(0, math.pi * 2),
        }
        for _ in range(n)
    ]


def _render_frame(
    frame_idx: int,
    theme: dict,
    jam_str: str,
    hari: str,
    tanggal: str,
    cuaca: str,
    quote: str,
    server_name: str,
    particles: list,
) -> Image.Image:

    t_global = frame_idx / (TOTAL_FRAMES - 1)   # 0→1 selama animasi
    pulse     = (math.sin(frame_idx * 0.28) + 1) / 2   # 0→1→0 berdenyut

    canvas = Image.new("RGB", (W, H))

    # ── Gradient BG ──
    draw = ImageDraw.Draw(canvas)
    for y in range(H):
        t = y / H
        color = _lerp_color(theme["bg_top"], theme["bg_bot"], t)
        draw.line([(0, y), (W, y)], fill=color)

    # ── Buat RGBA overlay ──
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # ── Orbs berdenyut ──
    orb_data = [
        (W * 0.15, H * 0.25, 170, theme["accent1"]),
        (W * 0.82, H * 0.70, 140, theme["accent2"]),
        (W * 0.55, H * 0.08, 100, theme["accent1"]),
    ]
    for i, (cx, cy, base_r, color) in enumerate(orb_data):
        phase_offset = i * (math.pi * 2 / 3)
        p = (math.sin(frame_idx * 0.22 + phase_offset) + 1) / 2
        r = int(base_r * (0.88 + 0.22 * p))
        for step in range(r, 0, -5):
            alpha = int(60 * (step / r) ** 2.8 * (0.7 + 0.3 * p))
            fill = (*color[:3], _clamp(alpha))
            d = ImageDraw.Draw(overlay)
            d.ellipse([cx - step, cy - step, cx + step, cy + step], fill=fill)

    # ── Grid lines ──
    grid_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid_layer)
    line_color = (*theme["accent1"][:3], 15)
    for y in range(0, H, 40):
        gd.line([(0, y), (W, y)], fill=line_color, width=1)
    for x in range(0, W, 40):
        gd.line([(x, 0), (x, H)], fill=line_color, width=1)
    overlay = Image.alpha_composite(overlay, grid_layer)

    # ── Partikel bintang bergerak ──
    star_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(star_layer)
    for p in particles:
        px = (p["x"] + p["vx"] * frame_idx * 1.5) % W
        py = (p["y"] + p["vy"] * frame_idx * 1.5) % H
        twinkle = (math.sin(frame_idx * 0.35 + p["phase"]) + 1) / 2
        alpha   = _clamp(p["alpha"] * (0.5 + 0.5 * twinkle))
        r       = p["r"]
        col     = _lerp_color(theme["accent1"], theme["accent2"], twinkle)
        sd.ellipse([px - r, py - r, px + r, py + r], fill=(*col, alpha))
    overlay = Image.alpha_composite(overlay, star_layer)

    # ── Decorative rings (pojok kiri atas) ──
    ring_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring_layer)
    cx_r, cy_r = 60, 60
    for rr, base_a in [(90, 28), (65, 48), (42, 68)]:
        spin_alpha = _clamp(base_a + 20 * pulse)
        rd.ellipse(
            [cx_r - rr, cy_r - rr, cx_r + rr, cy_r + rr],
            outline=(*theme["accent1"][:3], spin_alpha), width=2
        )
    overlay = Image.alpha_composite(overlay, ring_layer)

    # ── Dot pattern pojok kanan bawah ──
    dot_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dot_layer)
    for row in range(8):
        for col in range(8):
            dpx = W - 100 + col * 12
            dpy = H - 100 + row * 12
            da = _clamp(25 + 15 * pulse)
            dd.ellipse([dpx-2, dpy-2, dpx+2, dpy+2],
                       fill=(*theme["accent2"][:3], da))
    overlay = Image.alpha_composite(overlay, dot_layer)

    # Composite overlay ke canvas
    base = canvas.convert("RGBA")
    base = Image.alpha_composite(base, overlay)

    # ── Cards ──
    card_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card_layer)
    card_alpha = _clamp(190 + 20 * pulse)
    cd.rounded_rectangle([40, 55, 530, 430], radius=18,
                          fill=(*theme["card_bg"], card_alpha))
    cd.rounded_rectangle([40, 55, 530, 430], radius=18,
                          outline=(*theme["accent1"][:3], 85), width=2)
    cd.rounded_rectangle([560, 55, 860, 430], radius=18,
                          fill=(*theme["card_bg"], card_alpha))
    cd.rounded_rectangle([560, 55, 860, 430], radius=18,
                          outline=(*theme["accent2"][:3], 85), width=2)
    base = Image.alpha_composite(base, card_layer)

    # ── Teks layer (fade-in + slide) ──
    text_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(text_layer)

    f_huge   = _font(FONT_BOLD,    62)
    f_xlarge = _font(FONT_BOLD,    42)
    f_medium = _font(FONT_MEDIUM,  22)
    f_small  = _font(FONT_REGULAR, 17)
    f_tiny   = _font(FONT_LIGHT,   14)
    f_label  = _font(FONT_MEDIUM,  15)

    # Teks muncul bertahap: tiap elemen punya delay berbeda
    def text_alpha(delay_frac):
        """delay_frac 0.0–1.0: kapan mulai muncul (dari total animasi)"""
        local_t = max(0, (t_global - delay_frac) / (1.0 - delay_frac + 0.001))
        return _clamp(255 * _ease_out(min(local_t * 2.5, 1.0)))

    def slide_offset(delay_frac, max_offset=20):
        """Slide dari bawah ke posisi asli"""
        local_t = max(0, (t_global - delay_frac) / (1.0 - delay_frac + 0.001))
        progress = _ease_out(min(local_t * 2.5, 1.0))
        return int(max_offset * (1 - progress))

    # Accent bar kiri
    bar_a = text_alpha(0.0)
    for i in range(55):
        t2 = i / 55
        col = _lerp_color(theme["accent1"], theme["accent2"], t2)
        td.line([(48, 78 + i), (53, 78 + i)], fill=(*col, bar_a))

    # Session label
    a0 = text_alpha(0.0)
    dy0 = slide_offset(0.0)
    td.text((62, 78 + dy0), theme["session_label"], font=f_label,
            fill=(*theme["label"][:3], a0))

    # Server name
    a1 = text_alpha(0.05)
    dy1 = slide_offset(0.05)
    td.text((62, 105 + dy1), server_name, font=f_huge,
            fill=(255, 255, 255, a1))

    # Tagline
    a2 = text_alpha(0.15)
    dy2 = slide_offset(0.15)
    td.text((62, 182 + dy2), theme["tagline"], font=f_medium,
            fill=(*theme["accent2"][:3], a2))

    # Divider line animasi (grow dari kiri)
    divider_progress = _ease_out(min(max(0, (t_global - 0.2) * 3), 1.0))
    divider_len = int(380 * divider_progress)
    for i in range(divider_len):
        t3 = i / 380
        col = _lerp_color(theme["accent1"], theme["accent2"], t3)
        td.line([(62 + i, 218), (62 + i, 219)], fill=(*col, 180))

    # Sub tagline
    a3 = text_alpha(0.25)
    dy3 = slide_offset(0.25)
    td.text((62, 228 + dy3), theme["sub"], font=f_small,
            fill=(200, 200, 220, a3))

    # Quote
    a4 = text_alpha(0.35)
    dy4 = slide_offset(0.35)
    max_w = 390
    words = quote.split()
    lines, line = [], ""
    for w in words:
        test = (line + " " + w).strip()
        bbox = td.textbbox((0, 0), test, font=f_small)
        if bbox[2] - bbox[0] > max_w and line:
            lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)

    qy = 270
    td.text((62, qy - 4 + dy4), "💬", font=f_small,
            fill=(255, 255, 255, _clamp(a4 * 0.5)))
    for i_line, ln in enumerate(lines[:3]):
        td.text((85, qy + i_line * 24 + dy4), ln, font=f_small,
                fill=(210, 200, 240, a4))

    # Footer
    a5 = text_alpha(0.5)
    footer = f"{server_name} Bot  •  auto-greeting  •  {hari}"
    td.text((62, H - 50), footer, font=f_tiny,
            fill=(*theme["accent1"][:3], _clamp(a5 * 0.5)))

    # ── RIGHT CARD info blocks ──
    rx = 575

    def draw_info(y_start, label, value, delay):
        a = text_alpha(delay)
        dy = slide_offset(delay, 15)
        td.text((rx, y_start + dy), label.upper(), font=f_tiny,
                fill=(*theme["label"][:3], _clamp(a * 0.65)))
        td.text((rx, y_start + 16 + dy), value, font=f_medium,
                fill=(255, 255, 255, a))

    draw_info(80,  "⏰  Waktu",        jam_str, 0.1)
    draw_info(145, "📅  Hari",         hari,    0.2)
    draw_info(210, "🗓️  Tanggal",     tanggal, 0.3)
    draw_info(275, "🌤️  Cuaca Hari Ini", cuaca, 0.4)

    # Emoji besar kanan bawah (pulse opacity)
    emoji_a = _clamp(160 + 60 * pulse)
    td.text((W - 100, H - 110), theme["emoji"], font=f_xlarge,
            fill=(255, 255, 255, emoji_a))

    # Watermark
    td.text((W - 160, H - 30), f"{server_name}.bot v1.0", font=f_tiny,
            fill=(*theme["accent2"][:3], 70))

    # ── Shimmer scanline sweep ──
    shimmer_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shim_pos = int((frame_idx / TOTAL_FRAMES) * (W + 200)) - 100
    for sx in range(max(0, shim_pos - 30), min(W, shim_pos + 30)):
        dist = abs(sx - shim_pos)
        shim_a = _clamp(int(30 * (1 - dist / 30)))
        ImageDraw.Draw(shimmer_layer).line(
            [(sx, 55), (sx, 430)],
            fill=(255, 255, 255, shim_a)
        )
    base = Image.alpha_composite(base, shimmer_layer)

    # Composite teks
    base = Image.alpha_composite(base, text_layer)

    return base.convert("RGB")


def generate_greeting_gif(
    session: str,
    jam_str: str,
    hari: str,
    tanggal: str,
    cuaca: str,
    quote: str,
    server_name: str = "nanZ",
) -> bytes:
    """Generate animated GIF dan return sebagai bytes."""
    theme     = THEMES.get(session, THEMES["pagi"])
    particles = _make_particles(seed=hash(session) % 9999, n=55)

    frames = []
    for i in range(TOTAL_FRAMES):
        frame = _render_frame(
            i, theme, jam_str, hari, tanggal, cuaca, quote, server_name, particles
        )
        # Quantize ke 256 warna dengan dithering
        frame_p = frame.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=1)
        frames.append(frame_p)

    output = io.BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=FPS_DELAY * 10,   # Pillow pakai ms, FPS_DELAY dalam cs
        optimize=True,
        disposal=2,
    )
    output.seek(0)
    return output.read()


# ── Quick test ──
if __name__ == "__main__":
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("Asia/Jakarta"))
    sessions = ["pagi", "siang", "sore", "malam"]
    for s in sessions:
        print(f"Generating {s}...", end=" ", flush=True)
        data = generate_greeting_gif(
            session=s,
            jam_str=f"{now.hour:02d}:00 WIB",
            hari="Jumat",
            tanggal=now.strftime("%d %B %Y"),
            cuaca="25°C, Cerah Berawan",
            quote="Jangan berhenti sampai kamu bangga! ✨",
            server_name="nanZ",
        )
        fname = f"/home/claude/test_greeting_{s}.gif"
        with open(fname, "wb") as f:
            f.write(data)
        print(f"✅ {len(data)//1024} KB → {fname}")