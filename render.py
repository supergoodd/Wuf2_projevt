#!/usr/bin/env python3
"""ZOMBIE APOCALYPSE — Hari Pertama. Programmatic render, 1080x1920, 15 fps.
Character RAKA_APOKALIPS_001. Jalur A: PIL + ffmpeg. Tanpa AI video.
Zombie hanya siluet stylized dari jauh, tanpa close-up wajah, tanpa gore/darah."""
import json, math, os, random, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1920
FPS = 15
BASE = os.path.dirname(os.path.abspath(__file__))
random.seed(7)

def font(sz, bold=True):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            pass
    return ImageFont.load_default()

def mix(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def ease(t):
    return t * t * (3 - 2 * t)

MOODS = {
    'warm':  dict(sky_top=(255, 196, 120), sky_bot=(240, 200, 150), far=(190, 150, 110),
                  near=(96, 84, 72), win_lit=(255, 210, 110), win_dark=(60, 58, 62),
                  road=(70, 68, 66), ground=(110, 96, 76), fog=0, sun=(255, 230, 160)),
    'day':   dict(sky_top=(170, 200, 225), sky_bot=(220, 215, 195), far=(150, 150, 145),
                  near=(88, 86, 84), win_lit=(220, 220, 200), win_dark=(70, 72, 78),
                  road=(64, 64, 64), ground=(104, 100, 90), fog=10, sun=(255, 244, 200)),
    'cold':  dict(sky_top=(130, 140, 152), sky_bot=(90, 100, 108), far=(110, 112, 118),
                  near=(62, 62, 66), win_lit=(200, 190, 150), win_dark=(40, 42, 48),
                  road=(52, 52, 54), ground=(78, 76, 70), fog=60, sun=(200, 205, 205)),
    'dusk':  dict(sky_top=(120, 80, 90), sky_bot=(210, 140, 90), far=(120, 90, 90),
                  near=(58, 52, 56), win_lit=(255, 180, 90), win_dark=(36, 34, 40),
                  road=(48, 46, 48), ground=(72, 62, 58), fog=40, sun=(255, 170, 100)),
    'night': dict(sky_top=(18, 24, 44), sky_bot=(48, 52, 78), far=(40, 44, 64),
                  near=(30, 30, 38), win_lit=(255, 190, 100), win_dark=(18, 20, 28),
                  road=(30, 30, 34), ground=(44, 42, 44), fog=50, sun=(220, 220, 230)),
    'room':  dict(sky_top=(120, 95, 70), sky_bot=(90, 72, 54), far=(100, 82, 62),
                  near=(80, 64, 48), win_lit=(255, 200, 120), win_dark=(50, 44, 38),
                  road=(70, 58, 44), ground=(96, 78, 58), fog=0, sun=(255, 210, 140)),
}

def draw_city(d, mood, t, shift=0.0, far_shift=0.0):
    m = MOODS[mood]
    for y in range(0, 1250, 4):
        d.rectangle([0, y, W, y + 4], fill=mix(m['sky_top'], m['sky_bot'], y / 1250))
    # sun / moon glow
    sx, sy = (820, 260) if mood != 'night' else (820, 220)
    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(220, 0, -20):
        gd.ellipse([sx - r, sy - r, sx + r, sy + r], fill=m['sun'] + (int(22 * (1 - r / 220)),))
    base = d._image.convert('RGBA')
    d._image.paste(Image.alpha_composite(base, glow).convert('RGB'), (0, 0))
    # far buildings (parallax, slow)
    rng = random.Random(31)
    for i in range(9):
        bx = int(-80 + i * 140 + far_shift)
        bw, bh = rng.randint(90, 150), rng.randint(260, 520)
        d.rectangle([bx, 1250 - bh, bx + bw, 1250], fill=m['far'])
        for wy in range(1250 - bh + 30, 1230, 70):
            for wx in range(bx + 14, bx + bw - 14, 34):
                d.rectangle([wx, wy, wx + 16, wy + 24],
                            fill=m['win_dark'] if (wx + wy) % 3 else m['win_lit'])
    # near buildings
    rng = random.Random(17)
    for i in range(5):
        bx = int(-60 + i * 250 + shift)
        bw, bh = rng.randint(170, 230), rng.randint(480, 800)
        d.rectangle([bx, 1450 - bh, bx + bw, 1450], fill=m['near'])
        d.rectangle([bx - 8, 1450 - bh - 26, bx + bw + 8, 1450 - bh], fill=mix(m['near'], (0, 0, 0), 0.3))
        for wy in range(1450 - bh + 40, 1430, 90):
            for wx in range(bx + 18, bx + bw - 18, 52):
                lit = ((wx // 52 + wy // 90) % 4 == 0)
                d.rectangle([wx, wy, wx + 24, wy + 34], fill=m['win_lit'] if lit else m['win_dark'])
    # ground + road (perspective)
    for y in range(1450, 1920, 4):
        d.rectangle([0, y, W, y + 4], fill=mix(m['ground'], mix(m['ground'], (0, 0, 0), 0.4), (y - 1450) / 470))
    d.polygon([(300, 1920), (470, 1450), (610, 1450), (780, 1920)], fill=m['road'])
    for i in range(6):
        yy = 1480 + i * 75
        wdt = 6 + i * 3
        d.rectangle([540 - wdt // 2, yy, 540 + wdt // 2, yy + 34], fill=(220, 200, 120) if mood != 'night' else (140, 130, 90))
    # abandoned cars (simple, no detail)
    for (cx, cy, s, col) in [(250, 1620, 1.0, (90, 70, 60)), (860, 1560, 0.85, (60, 70, 80))]:
        d.rounded_rectangle([cx - 130 * s, cy - 40 * s, cx + 130 * s, cy + 30 * s], radius=18, fill=col)
        d.rounded_rectangle([cx - 80 * s, cy - 82 * s, cx + 70 * s, cy - 30 * s], radius=14, fill=mix(col, (0, 0, 0), 0.35))
        d.ellipse([cx - 95 * s, cy + 12 * s, cx - 55 * s, cy + 52 * s], fill=(20, 20, 22))
        d.ellipse([cx + 55 * s, cy + 12 * s, cx + 95 * s, cy + 52 * s], fill=(20, 20, 22))
    # street lamp
    d.rectangle([950, 900, 962, 1500], fill=(40, 40, 44))
    d.line([962, 900, 1020, 900], fill=(40, 40, 44), width=10)
    if mood in ('dusk', 'night'):
        lg = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        lgd = ImageDraw.Draw(lg)
        lgd.ellipse([940, 860, 1100, 980], fill=(255, 200, 110, 60))
        base = d._image.convert('RGBA')
        d._image.paste(Image.alpha_composite(base, lg).convert('RGB'), (0, 0))
    # fog bands
    if m['fog']:
        mist = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        md = ImageDraw.Draw(mist)
        for my, ma in [(950, m['fog']), (1250, m['fog'] + 25), (1550, m['fog'] + 15)]:
            md.rectangle([0, my, W, my + 120], fill=(210, 215, 220, ma))
        mist = mist.filter(ImageFilter.GaussianBlur(40))
        base = d._image.convert('RGBA')
        d._image.paste(Image.alpha_composite(base, mist).convert('RGB'), (0, 0))

def draw_room(d, mood, t, lamp=True):
    m = MOODS[mood]
    for y in range(0, H, 4):
        d.rectangle([0, y, W, y + 4], fill=mix((150, 118, 86), (96, 74, 54), y / H))
    # floor
    for y in range(1500, 1920, 4):
        d.rectangle([0, y, W, y + 4], fill=mix((110, 84, 58), (70, 52, 36), (y - 1500) / 420))
    # door (left), window (right, boarded/dark)
    d.rectangle([90, 700, 380, 1500], fill=(96, 66, 40))
    d.rectangle([110, 720, 360, 1480], fill=(120, 84, 52))
    d.rectangle([120, 730, 350, 900], fill=(70, 50, 34))
    d.ellipse([330, 1080, 350, 1100], fill=(220, 190, 120))
    d.rectangle([700, 700, 1000, 1150], fill=(60, 58, 64))
    d.rectangle([720, 720, 980, 1130], fill=(28, 30, 42) if mood != 'room' else (140, 160, 180))
    d.line([720, 720, 980, 1130], fill=(90, 70, 50), width=14)
    d.line([980, 720, 720, 1130], fill=(90, 70, 50), width=14)
    # table + radio
    d.rectangle([560, 1380, 1010, 1420], fill=(90, 62, 38))
    d.rectangle([590, 1420, 610, 1620], fill=(70, 48, 30))
    d.rectangle([960, 1420, 980, 1620], fill=(70, 48, 30))
    # warm lamp glow
    if lamp:
        lg = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        lgd = ImageDraw.Draw(lg)
        for r in range(200, 0, -20):
            lgd.ellipse([800 - r, 420 - r, 800 + r, 420 + r], fill=(255, 200, 110, int(18 * (1 - r / 200))))
        base = d._image.convert('RGBA')
        d._image.paste(Image.alpha_composite(base, lg).convert('RGB'), (0, 0))
    # backpack + supplies on floor
    d.rounded_rectangle([180, 1560, 330, 1720], radius=30, fill=(110, 100, 70))
    d.ellipse([200, 1720, 260, 1760], fill=(60, 60, 60))
    d.ellipse([280, 1720, 340, 1760], fill=(60, 60, 60))

def draw_radio(d, cx, cy, s, t):
    # old radio on table
    d.rounded_rectangle([cx - 150 * s, cy - 90 * s, cx + 150 * s, cy + 80 * s], radius=18, fill=(96, 60, 36))
    d.rounded_rectangle([cx - 130 * s, cy - 70 * s, cx + 130 * s, cy + 60 * s], radius=12, fill=(140, 92, 52))
    d.ellipse([cx - 110 * s, cy - 55 * s, cx - 10 * s, cy + 45 * s], fill=(50, 42, 34))
    for i in range(5):
        d.line([cx - 100 * s + i * 16 * s, cy - 40 * s, cx - 100 * s + i * 16 * s, cy + 30 * s], fill=(30, 26, 22), width=4)
    d.rectangle([cx + 20 * s, cy - 50 * s, cx + 110 * s, cy - 10 * s], fill=(240, 220, 160))
    d.line([cx + 24 * s, cy - 30 * s, cx + 106 * s, cy - 30 * s], fill=(200, 60, 40), width=5)
    d.ellipse([cx + 40 * s, cy + 10 * s, cx + 70 * s, cy + 40 * s], fill=(220, 200, 140))
    d.ellipse([cx + 82 * s, cy + 10 * s, cx + 112 * s, cy + 40 * s], fill=(220, 200, 140))
    # antenna + blinking light
    d.line([cx + 120 * s, cy - 80 * s, cx + 200 * s, cy - 190 * s], fill=(180, 180, 180), width=5)
    blink = 200 if (t % 1.2) < 0.6 else 60
    d.ellipse([cx - 140 * s, cy - 82 * s, cx - 120 * s, cy - 62 * s], fill=(255, blink, 40))
    # sound waves
    for k in range(3):
        r = 30 + ((t * 60 + k * 30) % 90)
        d.arc([cx - r, cy - r, cx + r, cy + r], 300, 60, fill=(255, 220, 120), width=3)

# ---------------- zombie silhouettes (distant only, no face) ----------------
def draw_zombie(d, x, feet_y, h, t, phase=0.0):
    bob = math.sin(t * 1.6 + phase) * h * 0.012
    lean = h * 0.06
    col = (52, 52, 58)
    col_d = (38, 38, 44)
    # hunched body
    d.ellipse([x - h * 0.10, feet_y - h * 0.52 + bob, x + h * 0.10, feet_y - h * 0.30 + bob], fill=col)
    d.polygon([(x - h * 0.11, feet_y - h * 0.50 + bob), (x + h * 0.11, feet_y - h * 0.50 + bob),
               (x + h * 0.13, feet_y - h * 0.06), (x - h * 0.13, feet_y - h * 0.06)], fill=col_d)
    # head (featureless silhouette, bowed)
    d.ellipse([x - h * 0.075 + lean, feet_y - h * 0.62 + bob, x + h * 0.075 + lean, feet_y - h * 0.50 + bob], fill=col)
    # arms hanging forward, slow sway
    sw = math.sin(t * 1.2 + phase) * h * 0.02
    for sgn in (-1, 1):
        d.line([x + sgn * h * 0.09, feet_y - h * 0.48 + bob, x + sgn * h * 0.07 + sw, feet_y - h * 0.22 + bob],
               fill=col, width=max(4, int(h * 0.035)))
    # slow shuffling legs
    step = math.sin(t * 1.6 + phase) * h * 0.05
    d.line([x - h * 0.05, feet_y - h * 0.08, x - h * 0.05 + step, feet_y], fill=col_d, width=max(4, int(h * 0.04)))
    d.line([x + h * 0.05, feet_y - h * 0.08, x + h * 0.05 - step, feet_y], fill=col_d, width=max(4, int(h * 0.04)))

# ---------------- RAKA_APOKALIPS_001 ----------------
SKIN = (232, 196, 160)
SKIN_D = (214, 176, 140)
HOODIE = (96, 110, 64)
HOODIE_D = (74, 86, 48)
JEANS = (48, 56, 72)
JEANS_D = (36, 44, 58)
HAIR = (28, 22, 16)
BAG = (150, 132, 92)

def _mouth(d, cx, cy, w, expr, speak):
    if speak > 0.15:
        d.ellipse([cx - w / 2, cy - 4, cx + w / 2, cy + 4 + 16 * speak], fill=(120, 50, 45))
    elif expr in ('smile', 'curious'):
        d.arc([cx - w / 2, cy - 8, cx + w / 2, cy + 14], 20, 160, fill=(120, 60, 50), width=4)
    elif expr == 'wise':
        d.arc([cx - w / 3, cy - 6, cx + w / 3, cy + 8], 20, 160, fill=(120, 60, 50), width=3)
    else:
        d.line([cx - w / 2, cy, cx + w / 2, cy], fill=(110, 55, 48), width=4)

def _face(d, cx, cy, hr, expr, t, speak):
    d.ellipse([cx - hr, cy - hr, cx + hr, cy + hr], fill=SKIN)
    d.pieslice([cx - hr, cy - hr, cx + hr, cy + hr * 0.4], 180, 270, fill=HAIR)
    d.pieslice([cx - hr, cy - hr, cx + hr, cy + hr * 0.4], 270, 360, fill=HAIR)
    brow_y = cy - hr * 0.28
    if expr == 'curious':
        d.arc([cx - hr * 0.55, brow_y - 10, cx - hr * 0.05, brow_y + 14], 200, 340, fill=HAIR, width=4)
        d.arc([cx + hr * 0.05, brow_y - 10, cx + hr * 0.55, brow_y + 14], 200, 340, fill=HAIR, width=4)
    elif expr in ('serious', 'alert'):
        d.line([cx - hr * 0.55, brow_y + 6, cx - hr * 0.08, brow_y - 2], fill=HAIR, width=4)
        d.line([cx + hr * 0.08, brow_y - 2, cx + hr * 0.55, brow_y + 6], fill=HAIR, width=4)
    else:
        d.arc([cx - hr * 0.55, brow_y - 4, cx - hr * 0.05, brow_y + 12], 200, 340, fill=HAIR, width=4)
        d.arc([cx + hr * 0.05, brow_y - 4, cx + hr * 0.55, brow_y + 12], 200, 340, fill=HAIR, width=4)
    blink = (t % 3.7) < 0.14
    ey = cy - hr * 0.05
    for ex in (-hr * 0.38, hr * 0.38):
        if blink:
            d.line([cx + ex - hr * 0.16, ey, cx + ex + hr * 0.16, ey], fill=(60, 40, 26), width=4)
        else:
            d.ellipse([cx + ex - hr * 0.17, ey - hr * 0.13, cx + ex + hr * 0.17, ey + hr * 0.13], fill=(255, 255, 255))
            d.ellipse([cx + ex - hr * 0.09, ey - hr * 0.09, cx + ex + hr * 0.09, ey + hr * 0.09], fill=(96, 62, 32))
            d.ellipse([cx + ex - hr * 0.03, ey - hr * 0.05, cx + ex + hr * 0.03, ey + hr * 0.01], fill=(20, 14, 10))
    d.line([cx, cy + hr * 0.12, cx - hr * 0.06, cy + hr * 0.38], fill=SKIN_D, width=3)
    for fx, fy in [(-0.28, 0.42), (-0.16, 0.48), (0.28, 0.42), (0.16, 0.48), (-0.05, 0.52), (0.08, 0.55)]:
        d.ellipse([cx + fx * hr - 2, cy + fy * hr - 2, cx + fx * hr + 2, cy + fy * hr + 2], fill=(190, 140, 100))
    _mouth(d, cx, cy + hr * 0.58, hr * 0.55, expr, speak)

def draw_shadow(d, cx, feet_y, h):
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.ellipse([cx - h * 0.16, feet_y - h * 0.012, cx + h * 0.16, feet_y + h * 0.012], fill=(0, 0, 0, 110))
    ov = ov.filter(ImageFilter.GaussianBlur(8))
    base = d._image.convert('RGBA')
    d._image.paste(Image.alpha_composite(base, ov).convert('RGB'), (0, 0))

def draw_raka(d, cx, feet_y, h, pose='stand', expr='calm', t=0.0, speak=0.0):
    """RAKA_APOKALIPS_001. h = total height px. poses: stand/crouch/bust/walk/listen."""
    hr = h * 0.088
    breathe = math.sin(t * 2.0) * h * 0.004
    sway = math.sin(t * 1.1) * h * 0.006
    walk = math.sin(t * 5.0) * h * 0.03 if pose == 'walk' else 0.0
    if pose == 'crouch':
        h2 = h * 0.62
        hip_y = feet_y - h2 * 0.42
        sh_y = hip_y - h2 * 0.30
    else:
        h2 = h
        hip_y = feet_y - h2 * 0.46
        sh_y = hip_y - h2 * 0.30 + breathe
    head_cy = sh_y - hr * 1.25
    draw_shadow(d, cx, feet_y, h)
    # jeans legs (or folded when crouch)
    leg_w = hr * 0.42
    if pose == 'crouch':
        d.polygon([(cx - hr * 1.1, hip_y), (cx + hr * 1.1, hip_y),
                   (cx + hr * 1.25, feet_y - h * 0.06), (cx - hr * 1.25, feet_y - h * 0.06)], fill=JEANS)
        d.ellipse([cx - hr * 1.1, feet_y - h * 0.16, cx - hr * 0.3, feet_y - h * 0.04], fill=JEANS_D)
        d.ellipse([cx + hr * 0.3, feet_y - h * 0.16, cx + hr * 1.1, feet_y - h * 0.04], fill=JEANS_D)
    elif pose != 'bust':
        for sgn in (-1, 1):
            lx = cx + sgn * hr * 0.55 + (walk * sgn if pose == 'walk' else 0)
            d.rounded_rectangle([lx - leg_w / 2, hip_y, lx + leg_w / 2, feet_y - h * 0.04],
                                radius=max(1, int(leg_w / 3)), fill=JEANS)
            # grey sneakers
            d.ellipse([lx - leg_w * 0.75, feet_y - h * 0.035, lx + leg_w * 0.75, feet_y + h * 0.005],
                      fill=(150, 150, 148))
            d.rectangle([lx - leg_w * 0.75, feet_y - h * 0.01, lx + leg_w * 0.75, feet_y + h * 0.005],
                        fill=(210, 210, 208))
    # hoodie — NARROW ROUNDED shoulders (half-width ~1.08*hr, never boxy)
    sh_hw = hr * 1.08
    torso_top = sh_y
    torso_bot = hip_y + h * 0.02
    _strip_h = h * 0.05
    _strip_r = int(min(hr * 0.4, h * 0.02, max(0, (_strip_h - 4) // 2)))
    d.rounded_rectangle([cx - sh_hw, torso_top, cx + sh_hw, torso_bot], radius=int(hr * 0.55), fill=HOODIE)
    d.rounded_rectangle([cx - sh_hw, torso_top, cx + sh_hw, torso_top + _strip_h], radius=_strip_r, fill=HOODIE_D)
    # hood strings + chest pocket + kangaroo pocket
    d.line([cx - hr * 0.2, torso_top + h * 0.01, cx - hr * 0.24, torso_top + h * 0.09], fill=(240, 240, 235), width=4)
    d.line([cx + hr * 0.2, torso_top + h * 0.01, cx + hr * 0.24, torso_top + h * 0.09], fill=(240, 240, 235), width=4)
    d.rectangle([cx + hr * 0.42, torso_top + h * 0.06, cx + hr * 0.92, torso_top + h * 0.13],
                outline=HOODIE_D, width=3)
    d.rounded_rectangle([cx - hr * 0.85, torso_bot - h * 0.10, cx + hr * 0.85, torso_bot - h * 0.01],
                        radius=10, fill=HOODIE_D)
    # canvas bag strap across chest
    d.line([cx - sh_hw * 0.9, torso_top + h * 0.02, cx + sh_hw * 0.7, torso_bot - h * 0.03],
           fill=BAG, width=10)
    # arms — relaxed, close to body
    arm_w = hr * 0.30
    for sgn in (-1, 1):
        ax = cx + sgn * (sh_hw + arm_w * 0.28)
        if pose == 'listen' and sgn == 1:
            d.line([cx + sh_hw * 0.8, torso_top + h * 0.04, cx + hr * 1.1, head_cy + hr * 0.2],
                   fill=HOODIE, width=int(arm_w))
            d.ellipse([cx + hr * 0.95, head_cy + hr * 0.05, cx + hr * 1.3, head_cy + hr * 0.35], fill=SKIN)
        else:
            ay2 = torso_bot - h * 0.02 + (walk * 0.4 * sgn if pose == 'walk' else 0)
            d.rounded_rectangle([ax - arm_w / 2, torso_top + h * 0.01, ax + arm_w / 2, ay2],
                                radius=max(1, int(arm_w / 4)), fill=HOODIE)
            d.ellipse([ax - arm_w / 2, ay2 - h * 0.03, ax + arm_w / 2, ay2 + h * 0.015], fill=SKIN)
    _face(d, cx + sway, head_cy, hr, expr, t, speak)

# ---------------- subtitles (karaoke) ----------------
def word_times(text, start, dur):
    words = text.split()
    total = sum(len(w) for w in words)
    out, cur = [], start
    for w in words:
        wd = dur * len(w) / total
        out.append((w, cur, cur + wd))
        cur += wd
    return out

def chunk_words(words, max_chars=18):
    chunks, cur, clen = [], [], 0
    for w in words:
        if clen + len(w[0]) + (1 if cur else 0) > max_chars and cur:
            chunks.append(cur); cur, clen = [], 0
        cur.append(w); clen += len(w[0]) + 1
    if cur:
        chunks.append(cur)
    return chunks

def draw_subtitle(img, text, t_abs, shot_start, clip_dur):
    d = ImageDraw.Draw(img, 'RGBA')
    wt = word_times(text, shot_start + 0.05, clip_dur)
    chunks = chunk_words(wt)
    cur = None
    for ch in chunks:
        if ch[0][1] - 0.05 <= t_abs <= ch[-1][2] + 0.25:
            cur = ch; break
    if cur is None:
        return
    f = font(56)
    lines, line, lw = [], [], 0
    for w in cur:
        ww = d.textlength(w[0] + ' ', font=f)
        if lw + ww > 940 and line:
            lines.append(line); line, lw = [], 0
        line.append(w); lw += ww
    if line:
        lines.append(line)
    lines = lines[:2]
    total_h = len(lines) * 72
    y0 = 1560 - total_h // 2
    for li, line in enumerate(lines):
        widths = [d.textlength(w[0] + ' ', font=f) for w in line]
        x = (W - sum(widths)) / 2
        y = y0 + li * 72
        for (w, ws, we), ww in zip(line, widths):
            col = (255, 224, 122) if ws <= t_abs <= we else (255, 255, 255)
            d.text((x, y), w, font=f, fill=col, stroke_width=4, stroke_fill=(0, 0, 0))
            x += ww

def ken_burns(img, lt, zoom_in=True, pan=(0, 0)):
    z = 1.0 + (0.07 * lt if zoom_in else 0.07 * (1 - lt))
    cx, cy = W / 2 + pan[0] * lt, H / 2 + pan[1] * lt
    w2, h2 = int(W / z), int(H / z)
    # clamp crop box inside the frame (never black bars)
    x0 = max(0, min(W - w2, int(cx - w2 / 2)))
    y0 = max(0, min(H - h2, int(cy - h2 / 2)))
    box = (x0, y0, x0 + w2, y0 + h2)
    return img.crop(box).resize((W, H), Image.BICUBIC)

def vignette(img, strength=70):
    ov = Image.new('L', (W, H), 0)
    od = ImageDraw.Draw(ov)
    od.ellipse([-W * 0.35, -H * 0.25, W * 1.35, H * 1.25], fill=255)
    ov = ov.filter(ImageFilter.GaussianBlur(180))
    black = Image.new('RGB', (W, H), (0, 0, 0))
    return Image.composite(img, black, ov.point(lambda p: 255 - int((255 - p) * strength / 255)))

def speak_env(lt, dur, clip_dur):
    if lt * dur > clip_dur:
        return 0.0
    return max(0.0, math.sin(lt * dur * math.pi * 2 * 2.4)) * 0.9

def base_city(mood, t, shift=0.0, far_shift=0.0):
    img = Image.new('RGB', (W, H), (20, 26, 30))
    d = ImageDraw.Draw(img)
    draw_city(d, mood, t, shift, far_shift)
    return img, d

# ---------------- shot composers ----------------
def shot_frame(shot, lt, t_abs):
    sid = shot['id']
    dur = shot['dur']
    clip_dur = shot['clip_dur']
    sp = speak_env(lt, dur, clip_dur)
    if sid == 1:  # Dolly-in pelan, close-up pagi hangat
        img, d = base_city('warm', t_abs)
        draw_raka(d, 540, 1750, 950, 'stand', 'curious', t_abs, sp)
        img = ken_burns(img, lt, True, (0, 0))
    elif sid == 2:  # Pan kiri-kanan pelan, wide jalan kosong
        img, d = base_city('day', t_abs)
        draw_raka(d, 540, 1640, 700, 'stand', 'calm', t_abs, sp)
        img = ken_burns(img, lt, True, (-160 + 320 * lt, 0))
    elif sid == 3:  # Tracking pelan maju, langkah dari ujung jalan
        img, d = base_city('warm', t_abs, shift=-lt * 120, far_shift=-lt * 50)
        for i, (zx, zh, ph) in enumerate([(300, 380, 0.0), (760, 340, 2.0)]):
            draw_zombie(d, zx + lt * 60, 1500, zh, t_abs, ph)
        draw_raka(d, 540, 1640, 800, 'stand', 'alert', t_abs, sp)
        img = ken_burns(img, lt, True, (0, -20))
    elif sid == 4:  # Static + slow push-in, zombie jauh tanpa tujuan
        img, d = base_city('cold', t_abs)
        for i, (zx, zh, ph) in enumerate([(220, 420, 1.0), (480, 360, 3.0), (820, 400, 5.0)]):
            draw_zombie(d, zx, 1520, zh, t_abs, ph)
        draw_raka(d, 540, 1620, 750, 'stand', 'serious', t_abs, sp)
        img = ken_burns(img, lt, True, (0, 0))
        ov = Image.new('RGBA', (W, H), (10, 12, 18, 40))
        img = Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')
    elif sid == 5:  # Orbit 180° lambat mengelilingi Raka
        ang = lt * math.pi
        shift = math.sin(ang) * 160
        far_shift = math.sin(ang) * 60
        img, d = base_city('warm', t_abs, shift=shift, far_shift=far_shift)
        draw_raka(d, 540, 1620, 1050, 'stand', 'serious', t_abs, sp)
        img = ken_burns(img, lt, True, (0, 0))
    elif sid == 6:  # Dolly-out pelan, kumpulkan bekal di kamar
        img = Image.new('RGB', (W, H), (100, 80, 58))
        d = ImageDraw.Draw(img)
        draw_room(d, 'room', t_abs)
        # supplies: bottles, cans, medicine box on table
        for (bx, by, col) in [(640, 1330, (90, 140, 200)), (700, 1330, (200, 120, 60)), (760, 1330, (220, 220, 220))]:
            d.rounded_rectangle([bx - 22, by - 50, bx + 22, by], radius=8, fill=col)
        d.rectangle([820, 1300, 940, 1360], fill=(240, 240, 235))
        d.line([820, 1330, 940, 1330], fill=(200, 60, 40), width=5)
        draw_raka(d, 420, 1640, 900, 'crouch', 'calm', t_abs, sp)
        img = ken_burns(img, lt, False, (0, 30))
    elif sid == 7:  # Tilt naik dari pintu ke wajah
        img = Image.new('RGB', (W, H), (100, 80, 58))
        d = ImageDraw.Draw(img)
        draw_room(d, 'room', t_abs, lamp=False)
        draw_raka(d, 540, 1620, 1050, 'stand', 'serious', t_abs, sp)
        img = ken_burns(img, lt, True, (0, 160 - 320 * lt))
    elif sid == 8:  # Static + slow push-in ke radio tua
        img = Image.new('RGB', (W, H), (100, 80, 58))
        d = ImageDraw.Draw(img)
        draw_room(d, 'room', t_abs)
        draw_radio(d, 780, 1300, 1.15, t_abs)
        draw_raka(d, 380, 1560, 700, 'listen', 'serious', t_abs, sp)
        img = ken_burns(img, lt, True, (120, 30))
    elif sid == 9:  # Match cut terang -> gelap
        if lt < 0.5:
            img, d = base_city('warm', t_abs)
            draw_raka(d, 540, 1620, 1000, 'stand', 'calm', t_abs, sp)
            img = ken_burns(img, lt / 0.5, True, (0, 0))
        else:
            img, d = base_city('night', t_abs)
            draw_raka(d, 540, 1620, 1000, 'stand', 'serious', t_abs, sp)
            img = ken_burns(img, (lt - 0.5) / 0.5, True, (0, 0))
    elif sid == 10:  # Tracking jalan mengikuti Raka
        img, d = base_city('dusk', t_abs, shift=-lt * 200, far_shift=-lt * 80)
        draw_raka(d, 540, 1640, 950, 'walk', 'alert', t_abs, sp)
        img = ken_burns(img, lt, True, (0, -10))
    elif sid == 11:  # Crane naik + dolly-out wide gelap
        img, d = base_city('night', t_abs)
        for i, (zx, zh, ph) in enumerate([(180, 380, 0.5), (420, 340, 2.5), (880, 360, 4.0)]):
            draw_zombie(d, zx, 1520, zh, t_abs, ph)
        draw_raka(d, 540, 1660, 650, 'stand', 'serious', t_abs, sp)
        img = ken_burns(img, lt, False, (0, -120))
    else:  # 12 Dolly-in pelan, fade out lembut
        img, d = base_city('night', t_abs)
        draw_raka(d, 540, 1780, 1000, 'stand', 'wise', t_abs, sp)
        img = ken_burns(img, lt, True, (0, 0))
        if lt > 0.85:
            a = int(255 * (lt - 0.85) / 0.15)
            ov = Image.new('RGBA', (W, H), (0, 0, 0, a))
            img = Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')
    img = vignette(img, 70)
    draw_subtitle(img, shot['text'], t_abs, shot['start'], clip_dur)
    return img

def main():
    with open(os.path.join(BASE, 'timeline.json')) as f:
        tl = json.load(f)
    shots = tl['shots']
    out = os.path.join(BASE, 'video_only.mp4')
    cmd = ['ffmpeg', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
           '-r', str(FPS), '-i', '-', '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
           '-preset', 'slow', '-crf', '18', out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    total = 0
    for shot in shots:
        n = int(round(shot['dur'] * FPS))
        for i in range(n):
            lt = (i + 0.5) / n
            t_abs = shot['start'] + i / FPS
            frame = shot_frame(shot, lt, t_abs)
            proc.stdin.write(frame.tobytes())
            total += 1
            if total % 150 == 0:
                print(f'frame {total} (shot {shot["id"]})', flush=True)
    proc.stdin.close()
    proc.wait()
    print(f'DONE frames={total} total_s={total / FPS:.2f} -> {out}')

if __name__ == '__main__':
    main()
