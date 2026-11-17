#!/usr/bin/env python3
"""ZOMBIE APOCALYPSE — Hari Pertama. Render 3D programatik (v2).
Kamera perspektif sungguhan (posisi x/y/z + yaw + focal), dunia 3D kota (meter),
parallax antar layer, gerakan kamera per shot: dolly / orbit / crane / tracking.
Helper karakter + subtitle diimpor dari render.py (character lock identik).
Output: video_only_3d_30fps.mp4 -> zombie-apocalypse-hari-pertama-3d-30fps.mp4 (mux final_audio.wav).
FPS 30, 1080x1920, 1800 frame (versi VPS). Tanpa AI video, tanpa Runway/ElevenLabs."""
import json, math, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import render as R  # draw_raka, draw_zombie, draw_radio, draw_subtitle, vignette, ...

W, H = 1080, 1920
FPS = 30

def mix(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def ease(t):
    return t * t * (3 - 2 * t)

# ---------------- kamera 3D ----------------
class Cam:
    """pos (x,y,z) meter, yaw radian (0 = menghadap +Z), f px, horizon px."""
    def __init__(self, pos, yaw, f=900, horizon=880):
        self.pos = pos; self.yaw = yaw; self.f = f; self.horizon = horizon
    def project(self, x, y, z):
        dx, dy, dz = x - self.pos[0], y - self.pos[1], z - self.pos[2]
        sy, cy = math.sin(self.yaw), math.cos(self.yaw)
        xp = dx * cy - dz * sy
        zp = dx * sy + dz * cy
        if zp < 0.5:
            return None
        s = self.f / zp
        return (W / 2 + xp * s, self.horizon - dy * s, s)
    def lerp(self, other, p):
        pos = tuple(a + (b - a) * p for a, b in zip(self.pos, other.pos))
        return Cam(pos, self.yaw + (other.yaw - self.yaw) * p,
                   self.f + (other.f - self.f) * p,
                   self.horizon + (other.horizon - self.horizon) * p)

def line3d(d, cam, a, b, fill, width=3):
    pa = cam.project(*a); pb = cam.project(*b)
    if pa and pb:
        d.line([pa[0], pa[1], pb[0], pb[1]], fill=fill,
               width=max(1, int(width * min(pa[2], pb[2]) / 300)))

def poly3d(d, cam, pts, fill):
    q = [cam.project(*p) for p in pts]
    if all(q):
        d.polygon([(p[0], p[1]) for p in q], fill=fill)
        return q
    return None

def vgrad(top, bot, h):
    g = Image.new('RGB', (1, 256))
    gd = ImageDraw.Draw(g)
    for y in range(256):
        gd.point((0, y), fill=mix(top, bot, y / 255))
    return g.resize((W, max(1, int(h))))

def glow_spot(img, sx, sy, color, rmax=240, alpha=30):
    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(rmax, 0, -24):
        gd.ellipse([sx - r, sy - r, sx + r, sy + r],
                   fill=color + (int(alpha * (1 - r / rmax)),))
    base = img.convert('RGBA')
    img.paste(Image.alpha_composite(base, glow).convert('RGB'), (0, 0))

# ---------------- dunia kota 3D (meter): jalan sepanjang +Z ----------------
# x: -2.2..2.2 jalan, gedung di |x| > 4. z: 0 dekat kamera, 50 jauh.
BUILDINGS = [
    (-7.0, 14, 5, 9, 5), (-8.0, 22, 6, 12, 6), (-7.0, 32, 5, 10, 5),
    (7.0, 16, 5, 8, 5), (8.0, 26, 6, 13, 6), (7.0, 38, 5, 11, 5),
    (-3.0, 45, 8, 14, 5), (4.0, 48, 7, 12, 5),
]
CARS = [(-3.4, 12.5, (90, 70, 60)), (3.2, 9.5, (60, 70, 80))]
LAMP = (4.6, 8.5)  # x, z tiang lampu

def box3d(d, cam, cx, cz, w, h, dep, col, mood, y0=0.0):
    """Kotak 3D: muka depan + atap + sisi menghadap kamera. y0 = alas."""
    m = R.MOODS[mood]
    zf, zb = cz - dep / 2, cz + dep / 2
    x0, x1 = cx - w / 2, cx + w / 2
    front = poly3d(d, cam, [(x0, y0, zf), (x1, y0, zf), (x1, y0 + h, zf), (x0, y0 + h, zf)], col)
    poly3d(d, cam, [(x0, y0 + h, zf), (x1, y0 + h, zf), (x1, y0 + h, zb), (x0, y0 + h, zb)],
           mix(col, (255, 255, 255), 0.25))
    sx = x0 if cam.pos[0] < cx else x1
    poly3d(d, cam, [(sx, y0, zf), (sx, y0, zb), (sx, y0 + h, zb), (sx, y0 + h, zf)],
           mix(col, (0, 0, 0), 0.3))
    if front:
        for wy in range(int(y0) + 2, int(y0 + h) - 1, 3):
            for k in range(max(1, int(w) - 1)):
                wx = x0 + 0.9 + k * 1.6
                q = cam.project(wx, wy, zf - 0.05)
                if q and q[2] > 6:
                    s = q[2]
                    d.rectangle([q[0] - 0.4 * s, q[1] - 0.6 * s, q[0] + 0.4 * s, q[1] + 0.6 * s],
                                fill=m['win_lit'] if ((int(wx) + wy) % 4 == 0) else m['win_dark'])

def draw_city3d(img, d, cam, mood, t):
    m = R.MOODS[mood]
    # gedung jauh -> dekat
    for (bx, bz, bw, bh, dep) in sorted(BUILDINGS, key=lambda b: -b[1]):
        box3d(d, cam, bx, bz, bw, bh, dep, m['near'] if bz < 30 else m['far'], mood)
    # jalan + garis tengah putus-putus
    poly3d(d, cam, [(-2.2, 0, 2), (2.2, 0, 2), (2.2, 0, 48), (-2.2, 0, 48)], m['road'])
    dash_col = (220, 200, 120) if mood != 'night' else (140, 130, 90)
    for gz in range(4, 46, 4):
        poly3d(d, cam, [(-0.12, 0, gz), (0.12, 0, gz), (0.12, 0, gz + 1.8), (-0.12, 0, gz + 1.8)], dash_col)
    # mobil terbengkalai
    for (cx, cz, col) in CARS:
        box3d(d, cam, cx, cz, 1.9, 0.85, 3.6, col, mood)
        box3d(d, cam, cx, cz + 0.2, 1.7, 0.6, 1.8, mix(col, (0, 0, 0), 0.35), mood, y0=0.85)
    # tiang lampu
    lx, lz = LAMP
    line3d(d, cam, (lx, 0, lz), (lx, 3.4, lz), (40, 40, 44), 5)
    line3d(d, cam, (lx, 3.4, lz), (lx - 0.9, 3.4, lz), (40, 40, 44), 5)
    if mood in ('dusk', 'night'):
        q = cam.project(lx - 0.9, 3.3, lz)
        if q:
            glow_spot(img, q[0], q[1], (255, 200, 110), rmax=160, alpha=55)
            d = ImageDraw.Draw(img)

def base_city(mood, cam, t):
    """Scene jalan kota 3D lengkap. Kembalikan (img, d)."""
    m = R.MOODS[mood]
    img = Image.new('RGB', (W, H), (20, 26, 30))
    hor = int(cam.horizon)
    img.paste(vgrad(m['sky_top'], m['sky_bot'], hor), (0, 0))
    # matahari / bulan sebagai titik dunia jauh
    if mood == 'night':
        sp = cam.project(-12, 26, 48)
        if sp:
            glow_spot(img, sp[0], sp[1], (220, 220, 230), rmax=200, alpha=40)
    else:
        sp = cam.project(14, 26, 48)
        if sp:
            glow_spot(img, sp[0], sp[1], m['sun'], rmax=240, alpha=30)
    img.paste(vgrad(mix(m['ground'], (255, 255, 255), 0.10), mix(m['ground'], (0, 0, 0), 0.15), H - hor), (0, hor))
    d = ImageDraw.Draw(img)
    draw_city3d(img, d, cam, mood, t)
    # depth haze di garis horizon
    haze = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(haze)
    hc = m['sky_bot']
    for yy in range(hor - 260, hor + 40, 20):
        a = int(58 * max(0.0, 1.0 - abs(yy - hor) / 300.0))
        if a > 0:
            hd.rectangle([0, yy, W, yy + 20], fill=hc + (a,))
    haze = haze.filter(ImageFilter.GaussianBlur(18))
    img.paste(Image.alpha_composite(img.convert('RGBA'), haze).convert('RGB'), (0, 0))
    d = ImageDraw.Draw(img)
    # kabut (fog) per mood
    if m['fog']:
        mist = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        md = ImageDraw.Draw(mist)
        for my, ma in [(950, m['fog']), (1250, m['fog'] + 25), (1550, m['fog'] + 15)]:
            md.rectangle([0, my, W, my + 120], fill=(210, 215, 220, ma))
        mist = mist.filter(ImageFilter.GaussianBlur(40))
        img = Image.alpha_composite(img.convert('RGBA'), mist).convert('RGB')
        d = ImageDraw.Draw(img)
    return img, d

# ---------------- interior kamar 3D (Shot 6-8) ----------------
WALL = (150, 118, 86)
FLOOR = (110, 84, 58)
DOOR_C = (96, 66, 40)
TABLE_C = (90, 62, 38)

def base_room(cam, t, lamp=True):
    """Kamar: dinding belakang z=7, lantai y=0, pintu kiri, jendela kanan, meja kanan."""
    img = Image.new('RGB', (W, H), WALL)
    hor = int(cam.horizon)
    img.paste(vgrad((168, 132, 96), (120, 92, 64), hor), (0, 0))
    img.paste(vgrad(FLOOR, (98, 74, 52), H - hor), (0, hor))
    d = ImageDraw.Draw(img)
    # dinding belakang
    poly3d(d, cam, [(-6, 0, 7), (6, 0, 7), (6, 3.4, 7), (-6, 3.4, 7)], WALL)
    # pintu (kiri)
    poly3d(d, cam, [(-4.3, 0, 6.95), (-2.7, 0, 6.95), (-2.7, 2.4, 6.95), (-4.3, 2.4, 6.95)], DOOR_C)
    poly3d(d, cam, [(-4.1, 0.15, 6.9), (-2.9, 0.15, 6.9), (-2.9, 2.25, 6.9), (-4.1, 2.25, 6.9)],
           (120, 84, 52))
    q = cam.project(-2.85, 1.05, 6.88)
    if q:
        s = q[2]
        d.ellipse([q[0] - 0.06 * s, q[1] - 0.06 * s, q[0] + 0.06 * s, q[1] + 0.06 * s], fill=(220, 190, 120))
    # jendela dipalang (kanan)
    poly3d(d, cam, [(2.6, 1.3, 6.95), (4.4, 1.3, 6.95), (4.4, 2.7, 6.95), (2.6, 2.7, 6.95)], (28, 30, 42))
    line3d(d, cam, (2.6, 1.3, 6.9), (4.4, 2.7, 6.9), (90, 70, 50), 6)
    line3d(d, cam, (4.4, 1.3, 6.9), (2.6, 2.7, 6.9), (90, 70, 50), 6)
    # meja (kanan) + ransel lantai (kiri)
    box3d(d, cam, 1.8, 5.6, 2.4, 0.95, 1.1, TABLE_C, 'room')
    box3d(d, cam, -3.2, 5.4, 0.7, 0.6, 0.5, (110, 100, 70), 'room')
    if lamp:
        q = cam.project(0, 2.95, 5.0)
        if q:
            glow_spot(img, q[0], q[1], (255, 200, 110), rmax=260, alpha=55)
            d = ImageDraw.Draw(img)
    return img, d

def draw_supplies(d, cam):
    """Botol + kotak obat di atas meja (y=0.95, z=5.6)."""
    for (bx, col) in [(1.0, (90, 140, 200)), (1.5, (200, 120, 60)), (2.0, (220, 220, 220))]:
        q = cam.project(bx, 0.95, 5.6)
        if q and q[2] > 5:
            s = q[2]
            d.rounded_rectangle([q[0] - 0.09 * s, q[1] - 0.42 * s, q[0] + 0.09 * s, q[1]], radius=6, fill=col)
    q = cam.project(2.6, 0.95, 5.6)
    if q and q[2] > 5:
        s = q[2]
        d.rectangle([q[0] - 0.35 * s, q[1] - 0.35 * s, q[0] + 0.35 * s, q[1]], fill=(240, 240, 235))
        d.line([q[0] - 0.35 * s, q[1] - 0.17 * s, q[0] + 0.35 * s, q[1] - 0.17 * s], fill=(200, 60, 40), width=4)

# ---------------- anchor karakter / objek ----------------
def project_anchor(cam, x, y, z):
    q = cam.project(x, y, z)
    if not q:
        return None
    return q[0], q[1], q[2] / 400.0

def draw_character3d(d, cam, x, z, pose, expr, t, speak):
    """RAKA_APOKALIPS_001 di posisi dunia (x, z), tinggi 1.7 m."""
    q = cam.project(x, 0, z)
    if not q:
        return None
    sx, feet_y, s = q
    if not (s > 0) or s != s:
        return None
    h_px = max(1.7 * s, 240)
    R.draw_raka(d, sx, feet_y, h_px, pose, expr, t, speak)
    return (sx, feet_y, h_px)

def draw_zombie3d(d, cam, x, z, t, phase=0.0):
    """Siluet zombie jauh (tanpa wajah, tanpa gore)."""
    q = cam.project(x, 0, z)
    if not q:
        return
    sx, feet_y, s = q
    if not (s > 0) or s != s:
        return
    h_px = max(1.75 * s, 100)
    R.draw_zombie(d, sx, feet_y, h_px, t, phase)

def draw_radio3d(d, cam, x, y, z, t):
    a = project_anchor(cam, x, y, z)
    if a:
        R.draw_radio(d, a[0], a[1], max(0.4, a[2]), t)

# ---------------- kamera per shot ----------------
RAKA_Z = 6.3

def orbit_cam(lt, th0=-0.6, th1=0.6, radius=2.6, y=1.6, f=1100):
    th = th0 + (th1 - th0) * lt
    cx = 0.0 + radius * math.sin(th)
    cz = RAKA_Z - radius * math.cos(th)
    return Cam((cx, y, cz), -th, f=f)

def shot_frame(shot, lt, t_abs):
    sid = shot['id']
    dur = shot['dur']
    clip_dur = shot['clip_dur']
    sp = R.speak_env(lt, dur, clip_dur)
    e = ease(lt)
    if sid == 1:  # Dolly-in, close-up pagi hangat
        cam = Cam((0.3, 1.5, 3.2), -0.05, f=1100).lerp(Cam((0.2, 1.5, 4.1), -0.02, f=1100), e)
        img, d = base_city('warm', cam, t_abs)
        draw_character3d(d, cam, 0.0, 6.0, 'stand', 'curious', t_abs, sp)
    elif sid == 2:  # Pan kiri-kanan, wide jalan kosong
        cam = Cam((0.0, 1.8, 2.2), -0.28, f=1000).lerp(Cam((0.0, 1.8, 2.2), 0.28, f=1000), e)
        img, d = base_city('day', cam, t_abs)
        draw_character3d(d, cam, 0.0, 7.0, 'stand', 'calm', t_abs, sp)
    elif sid == 3:  # Tracking maju, zombie dari ujung jalan
        cam = Cam((0.0, 1.6, 2.0), 0.0, f=1000).lerp(Cam((0.0, 1.6, 3.5), 0.0, f=1000), e)
        img, d = base_city('warm', cam, t_abs)
        draw_zombie3d(d, cam, -2.8 + lt * 0.6, 10.5, t_abs, 0.0)
        draw_zombie3d(d, cam, 2.6 + lt * 0.6, 11.0, t_abs, 2.0)
        draw_character3d(d, cam, 0.0, 6.5, 'stand', 'alert', t_abs, sp)
    elif sid == 4:  # Static + slow push-in (focal), zombie jauh
        cam = Cam((0.0, 1.6, 3.0), 0.0, f=900 + 250 * e)
        img, d = base_city('cold', cam, t_abs)
        draw_zombie3d(d, cam, -3.2, 10.0, t_abs, 1.0)
        draw_zombie3d(d, cam, 0.2, 10.5, t_abs, 3.0)
        draw_zombie3d(d, cam, 3.4, 10.0, t_abs, 5.0)
        draw_character3d(d, cam, 0.0, 6.5, 'stand', 'serious', t_abs, sp)
        ov = Image.new('RGBA', (W, H), (10, 12, 18, 40))
        img = Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')
    elif sid == 5:  # Orbit 180 derajat mengelilingi Raka
        cam = orbit_cam(lt)
        img, d = base_city('warm', cam, t_abs)
        draw_character3d(d, cam, 0.0, RAKA_Z, 'stand', 'serious', t_abs, sp)
    elif sid == 6:  # Dolly-out, kumpulkan bekal di kamar
        cam = Cam((0.0, 1.5, 2.6), 0.0, f=1000).lerp(Cam((0.0, 1.7, 1.4), 0.0, f=900), e)
        img, d = base_room(cam, t_abs, lamp=True)
        draw_supplies(d, cam)
        got = draw_character3d(d, cam, -0.9, 5.2, 'crouch', 'calm', t_abs, sp)
        if got:
            # perbaikan cacat v2: sepatu abu-abu terlihat jelas di bawah jongkok,
            # kaki tidak lagi terbaca sebagai gumpalan gelap
            sx, feet_y, h_px = got
            for sgn in (-1, 1):
                cx = sx + sgn * h_px * 0.10
                d.ellipse([cx - h_px * 0.09, feet_y - h_px * 0.045, cx + h_px * 0.09, feet_y - h_px * 0.005],
                          fill=(150, 150, 148))
                d.rectangle([cx - h_px * 0.09, feet_y - h_px * 0.012, cx + h_px * 0.09, feet_y - h_px * 0.005],
                            fill=(210, 210, 208))
    elif sid == 7:  # Tilt naik (horizon turun + kamera naik), lampu mati
        cam = Cam((0.0, 1.2, 2.8), 0.0, f=1000, horizon=1000).lerp(
              Cam((0.0, 1.9, 2.8), 0.0, f=1000, horizon=760), e)
        img, d = base_room(cam, t_abs, lamp=False)
        draw_character3d(d, cam, 0.0, 5.5, 'stand', 'serious', t_abs, sp)
        ov = Image.new('RGBA', (W, H), (8, 8, 12, 55))
        img = Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')
    elif sid == 8:  # Push-in ke radio tua
        cam = Cam((0.0, 1.5, 2.0), 0.02, f=900).lerp(Cam((0.2, 1.45, 2.6), 0.04, f=950), e)
        img, d = base_room(cam, t_abs, lamp=True)
        draw_radio3d(d, cam, 1.0, 1.25, 5.6, t_abs)
        draw_character3d(d, cam, -0.5, 5.2, 'listen', 'serious', t_abs, sp)
    elif sid == 9:  # Match cut terang -> gelap (framing sama)
        cam = Cam((0.3, 1.5, 3.2), -0.05, f=1100).lerp(Cam((0.2, 1.5, 4.1), -0.02, f=1100), e)
        mood = 'warm' if lt < 0.5 else 'night'
        img, d = base_city(mood, cam, t_abs)
        draw_character3d(d, cam, 0.0, 6.0, 'stand', 'calm' if lt < 0.5 else 'serious', t_abs, sp)
    elif sid == 10:  # Tracking jalan mengikuti Raka
        cam = Cam((0.0, 1.6, 2.0), 0.0, f=1000).lerp(Cam((0.0, 1.6, 3.6), 0.0, f=1000), e)
        img, d = base_city('dusk', cam, t_abs)
        draw_character3d(d, cam, 0.0, 6.5, 'walk', 'alert', t_abs, sp)
    elif sid == 11:  # Crane naik + dolly-out wide gelap
        cam = Cam((0.0, 1.5, 3.0), 0.0, f=900).lerp(Cam((0.0, 3.2, 0.5), 0.0, f=900), e)
        img, d = base_city('night', cam, t_abs)
        draw_zombie3d(d, cam, -3.0, 10.0, t_abs, 0.5)
        draw_zombie3d(d, cam, 0.0, 10.5, t_abs, 2.5)
        draw_zombie3d(d, cam, 3.2, 10.0, t_abs, 4.0)
        draw_character3d(d, cam, 0.0, 6.5, 'stand', 'serious', t_abs, sp)
    else:  # 12 Dolly-in, fade out
        cam = Cam((0.3, 1.5, 3.2), -0.05, f=1100).lerp(Cam((0.2, 1.5, 4.1), -0.02, f=1100), e)
        img, d = base_city('night', cam, t_abs)
        draw_character3d(d, cam, 0.0, 6.0, 'stand', 'wise', t_abs, sp)
        if lt > 0.85:
            a = int(255 * (lt - 0.85) / 0.15)
            ov = Image.new('RGBA', (W, H), (0, 0, 0, a))
            img = Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')
    img = R.vignette(img, 45)
    R.draw_subtitle(img, shot['text'], t_abs, shot['start'], clip_dur)
    return img

def main():
    with open(os.path.join(BASE, 'timeline.json')) as f:
        tl = json.load(f)
    shots = tl['shots']
    out = os.path.join(BASE, 'video_only_3d_30fps.mp4')
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
