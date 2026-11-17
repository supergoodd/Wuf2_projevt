# Zombie Apocalypse — Hari Pertama (3D, 30fps)

Render 3D programatik (PIL + ffmpeg), 1080x1920 vertikal, 30fps, 60 detik, 12 shot.
Cerita + narasi sama dengan versi 15fps; versi ini 30fps dan sepatu Shot 6 sudah diperbaiki.

## Cara render di VPS (Ubuntu)

```bash
sudo apt update && sudo apt install -y python3-pil python3-numpy ffmpeg git
git clone https://github.com/supergoodd/zombie-apocalypse-3d.git
cd zombie-apocalypse-3d
bash render30.sh
```

Cek progres: `tail -f render30.log` — tunggu sampai ada `DONE frames=1800`.
Lalu gabung audio:

```bash
ffmpeg -y -i video_only_3d_30fps.mp4 -i final_audio.wav -c:v copy -c:a aac -b:a 128k -shortest zombie-apocalypse-hari-pertama-3d-30fps.mp4
```

Hasil akhir: `zombie-apocalypse-hari-pertama-3d-30fps.mp4` — download lewat SFTP (Termius).
PREVIEW saja, jangan terbit sebelum OK Zhaey.
