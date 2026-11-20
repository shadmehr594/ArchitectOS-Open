# ==========================================================
# VOICE_07C — AUDIO-PATH AUDIT (read-only)
#
# Documents, for every recording in the browser -> Whisper path:
#   container/codec, sample rate, channels, duration,
#   leading-silence duration, first speech timestamp,
#   clipping, RMS/peak level, ffmpeg decode result.
#
# Runs on the SYSTEM python 3.11 (has numpy + scipy + ffmpeg).
# Never writes to the source recording.
# ==========================================================


import json
import os
import subprocess
import sys
import wave


FFMPEG = r"C:\ffmpeg-8.1.2-essentials_build\bin\ffmpeg.exe"
FFPROBE = r"C:\ffmpeg-8.1.2-essentials_build\bin\ffprobe.exe"

REPO = r"<repo-root>"


RECORDINGS = [
    os.path.join(REPO, "data/projects/project_23e5dae6/documents",
                 "voice_030_9e1635.webm"),
    os.path.join(REPO, "data/projects/project_23e5dae6/documents",
                 "voice_275_c9bc97.webm"),
]


def probe(path):

    out = subprocess.run(
        [FFPROBE, "-v", "error",
         "-show_entries",
         "stream=codec_name,sample_rate,channels,channel_layout",
         "-show_entries", "format=format_name,duration,size,bit_rate",
         "-of", "json", path],
        capture_output=True, text=True,
    )

    try:
        return json.loads(out.stdout)
    except Exception:
        return {"error": out.stderr[-300:]}


def decode_pcm(path, target, rate=16000, channels=1):
    """Decode any container to signed-16 PCM WAV. Returns (ok, msg)."""

    completed = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-i", path,
         "-ac", str(channels), "-ar", str(rate),
         "-c:a", "pcm_s16le", target],
        capture_output=True, text=True,
    )

    return (completed.returncode == 0,
            (completed.stderr or "").strip()[-300:])


def wav_stats(path):

    import numpy as np

    with wave.open(path, "rb") as handle:

        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.getnframes()
        raw = handle.readframes(frames)

    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)

    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)

    peak = float(np.max(np.abs(data))) if data.size else 0.0
    rms = float(np.sqrt(np.mean(data ** 2))) if data.size else 0.0

    # leading silence (first sample above a small floor, 10 ms frames)
    frame = max(1, int(rate * 0.01))
    n = data.size // frame
    first_speech = None

    for i in range(n):

        chunk = data[i * frame:(i + 1) * frame]

        if np.sqrt(np.mean(chunk ** 2)) > 120.0:  # ~ -48 dBFS

            first_speech = round(i * frame / rate, 3)

            break

    clipped = int(np.sum(np.abs(data) >= 32767))

    return {
        "sample_rate": rate,
        "channels": channels,
        "sample_width_bytes": width,
        "frames": frames,
        "duration": round(frames / float(rate), 3),
        "peak_dbfs": round(20 * np.log10(peak / 32768.0 + 1e-12), 2),
        "rms_dbfs": round(20 * np.log10(rms / 32768.0 + 1e-12), 2),
        "first_speech_timestamp": first_speech,
        "clipped_samples": clipped,
    }


def main():

    report = {}

    for path in RECORDINGS:

        key = os.path.basename(path)

        entry = {"path": path, "exists": os.path.isfile(path)}

        if not entry["exists"]:
            report[key] = entry
            continue

        entry["probe"] = probe(path)

        clean = os.path.join(REPO, ".pytest_tmp/diag07c",
                             key.split("_")[1] + "_audit_clean.wav")

        ok, msg = decode_pcm(path, clean)

        entry["decode"] = {"ok": ok, "message": msg}

        if ok:
            entry["clean_pcm_stats"] = wav_stats(clean)

        report[key] = entry

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":

    sys.exit(main())
