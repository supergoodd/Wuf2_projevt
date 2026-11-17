#!/usr/bin/env python3
"""Post-process render Blender Zombie Apocalypse: bakar subtitle karaoke ke
tiap frame PNG, lalu gabung jadi mp4 + audio.

Jalankan di VPS setelah render penuh selesai (folder blender_frames/ terisi):
    python3 post_blender.py

Hasil: zombie-apocalypse-hari-pertama-blender-3d.mp4 (1080x1920, 30fps,
H.264 + AAC, subtitle karaoke kuning/putih seperti versi PIL).
Audio: pakai final_audio_elevenlabs.wav kalau ada (suara Liam),
kalau tidak ada pakai final_audio.wav (TTS).
"""
import glob
import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import render as R  # draw_subtitle (karaoke, kata terucap kuning)
from PIL import Image

FPS = 30
FRAMES_DIR = os.path.join(BASE, "blender_frames")
OUT_DIR = os.path.join(BASE, "blender_frames_sub")


def shot_at(shots, t_abs):
    for s in shots:
        if s["start"] <= t_abs < s["start"] + s["dur"]:
            return s
    return shots[-1]


def main():
    tl = json.load(open(os.path.join(BASE, "timeline.json")))
    shots = tl["shots"]
    files = sorted(glob.glob(os.path.join(FRAMES_DIR, "frame_*.png")))
    if not files:
        raise SystemExit(f"tidak ada frame di {FRAMES_DIR}/ — render penuh dulu.")
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"{len(files)} frame, bakar subtitle...")
    for i, path in enumerate(files):
        n = int(os.path.splitext(os.path.basename(path))[0].split("_")[1])
        t_abs = n / FPS
        s = shot_at(shots, t_abs)
        img = Image.open(path).convert("RGB")
        R.draw_subtitle(img, s["text"], t_abs, s["start"], s["clip_dur"])
        img.save(os.path.join(OUT_DIR, os.path.basename(path)))
        if (i + 1) % 300 == 0:
            print(f"  {i + 1}/{len(files)} frame")
    audio = os.path.join(BASE, "final_audio_elevenlabs.wav")
    if not os.path.exists(audio):
        audio = os.path.join(BASE, "final_audio.wav")
    out = os.path.join(BASE, "zombie-apocalypse-hari-pertama-blender-3d.mp4")
    cmd = ["ffmpeg", "-y", "-framerate", str(FPS), "-i",
           os.path.join(OUT_DIR, "frame_%04d.png"),
           "-i", audio, "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-preset", "slow", "-crf", "18", "-c:a", "aac", "-b:a", "128k",
           "-shortest", out]
    print("audio:", os.path.basename(audio))
    print("mux:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"DONE -> {out}")


if __name__ == "__main__":
    main()
