#!/bin/bash
# Render Zombie Apocalypse 3D 30fps di VPS — jalan di background
cd "$(dirname "$0")"
nohup python3 render_3d_30fps.py > render30.log 2>&1 &
echo "Render 30fps jalan di background (1800 frame, ~15-25 menit)."
echo "Cek progres: tail -f render30.log"
echo "Kalau sudah ada DONE, gabung audio:"
echo "ffmpeg -y -i video_only_3d_30fps.mp4 -i final_audio.wav -c:v copy -c:a aac -b:a 128k -shortest zombie-apocalypse-hari-pertama-3d-30fps.mp4"
