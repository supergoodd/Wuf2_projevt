#!/usr/bin/env python3
"""Zombie Apocalypse — narasi pakai ElevenLabs (suara Liam) + mix final audio.

Jalankan di VPS (di folder repo zombie-apocalypse-3d):
    export ELEVENLABS_API_KEY='ISI_KEY_LU_DISINI'
    python3 gen_audio_elevenlabs.py

Key dibaca dari environment saja, JANGAN pernah ditulis di file ini atau di chat.
Hasil: audio/c01.mp3..c12.mp3 (suara Liam, model eleven_v3) lalu
final_audio_elevenlabs.wav (narasi + musik drone, 61 detik, mono 44100 Hz).
File final_audio.wav lama TIDAK ditimpa.
Biaya: total narasi ~60 detik (~900 karakter) — kecil, makan sedikit kuota ElevenLabs.
"""
import json, math, os, subprocess, sys, time, urllib.request, urllib.error
import wave
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
VOICE_ID = "TX3LPaxmHKxFdv7VOQHJ"  # Liam
MODEL = "eleven_v3"
SR = 44100
API_URL = ("https://api.elevenlabs.io/v1/text-to-speech/" + VOICE_ID
           + "?output_format=mp3_44100_128")


def tts(text, out_path, api_key):
    """Satu klip narasi -> mp3. Retry 1x kalau kena rate limit (429)."""
    body = json.dumps({
        "text": text,
        "model_id": MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75,
                           "style": 0.0, "use_speaker_boost": True},
    }).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, headers={
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }, method="POST")
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if len(data) < 1000:
                raise RuntimeError(f"balasan audio terlalu kecil ({len(data)} byte)")
            with open(out_path, "wb") as f:
                f.write(data)
            return len(data)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise SystemExit("KEY SALAH / tidak valid (401). Cek ELEVENLABS_API_KEY lu.")
            if e.code == 429 and attempt == 1:
                print("  kena limit ElevenLabs (429), tunggu 60 detik lalu coba lagi...")
                time.sleep(60)
                continue
            raise SystemExit(f"ElevenLabs error HTTP {e.code}: {e.read()[:200]!r}")
    raise SystemExit("gagal setelah 2x percobaan")


def load_mp3(path):
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le",
                          "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    if out.returncode != 0:
        raise SystemExit(f"ffmpeg gagal baca {path}: {out.stderr[:200]!r}")
    return np.frombuffer(out.stdout, dtype=np.float32)


def pad_chord(freqs, dur, amp=0.08):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    for f in freqs:
        sig += np.sin(2 * np.pi * f * t) * (1.0 / len(freqs))
    env = np.minimum(1.0, t / 0.8) * np.minimum(1.0, (dur - t) / 1.2)
    return sig * np.clip(env, 0, 1) * amp


def movavg(x, k):
    c = np.cumsum(np.concatenate([[0.0], x]))
    idx = np.arange(len(x))
    lo = np.maximum(0, idx - k // 2)
    hi = np.minimum(len(x), idx + k // 2 + 1)
    return (c[hi] - c[lo]) / (hi - lo)


def mix(shots):
    """Narasi + drone/wind (musik -20 dB, duck saat ada suara). Sama kayak mix_audio.py."""
    total = shots[-1]["start"] + shots[-1]["dur"]
    n = int(total * SR) + SR
    music = np.zeros(n)
    narr = np.zeros(n)
    speech_mask = np.zeros(n)
    for s in shots:
        clip = load_mp3(os.path.join(BASE, "audio", s["clip"] + ".mp3"))
        start = int((s["start"] + 0.05) * SR)
        end = min(n, start + len(clip))
        narr[start:end] += clip[:end - start] * 0.95
        speech_mask[start:end] = 1.0
    sections = [
        (0.0, 10.0, [110.0, 164.8, 220.0], 0.07),
        (10.0, 25.0, [82.4, 110.0, 164.8], 0.06),
        (25.0, 40.0, [55.0, 82.4], 0.05),
        (40.0, 50.0, [55.0, 65.4, 82.4], 0.06),
        (50.0, 60.0, [49.0, 55.0, 73.4], 0.07),
    ]
    rng = np.random.default_rng(5)
    for (a, b, freqs, amp) in sections:
        seg = pad_chord(freqs, b - a, amp=amp)
        s0, e0 = int(a * SR), int((a + len(seg) / SR) * SR)
        music[s0:e0] += seg[:e0 - s0]
        wn = rng.standard_normal(int((b - a) * SR)) * 0.010
        wn = movavg(wn, 400)
        music[int(a * SR):int(b * SR)] += wn[:int((b - a) * SR)]
    sm = movavg(speech_mask, SR // 4)
    music *= 1.0 - 0.72 * np.clip(sm, 0, 1)
    fade = np.ones(n)
    fl = int(2.0 * SR)
    fade[-fl:] = np.linspace(1, 0, fl)
    music *= fade
    narr *= fade
    mix = narr + music
    peak = np.max(np.abs(mix))
    if peak > 0.98:
        mix *= 0.98 / peak
    mix16 = (mix * 32767).astype(np.int16)
    out_path = os.path.join(BASE, "final_audio_elevenlabs.wav")
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(mix16.tobytes())
    print(f"DONE mix total={total:.2f}s peak={np.max(np.abs(mix)):.2f} -> {out_path}")


def main():
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "ELEVENLABS_API_KEY belum diisi.\n"
            "Di Termius ketik dulu (ganti ISI_KEY_LU dengan key ElevenLabs lu):\n"
            "  export ELEVENLABS_API_KEY='ISI_KEY_LU'\n"
            "Jangan kirim key ke chat.")
    tl = json.load(open(os.path.join(BASE, "timeline.json")))
    shots = tl["shots"]
    os.makedirs(os.path.join(BASE, "audio"), exist_ok=True)
    for s in shots:
        out_path = os.path.join(BASE, "audio", s["clip"] + ".mp3")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
            print(f"clip {s['clip']} sudah ada, skip (hapus filenya kalau mau generate ulang)")
            continue
        print(f"clip {s['clip']}: {s['text']!r}")
        nbytes = tts(s["text"], out_path, api_key)
        print(f"  ok {nbytes} byte -> {out_path}")
    mix(shots)
    print("SELESAI. Gabung ke video dengan:")
    print("  ffmpeg -y -i video_only_3d_30fps.mp4 -i final_audio_elevenlabs.wav "
          "-c:v copy -c:a aac -b:a 128k -shortest "
          "zombie-apocalypse-hari-pertama-3d-30fps-liam.mp4")


if __name__ == "__main__":
    main()
