# ==========================================================
# VOICE_07C — AUDIO VISUAL INSPECTION (read-only)
#
# Renders a waveform + spectrogram PNG for a recording so the
# natural leading pause, the speech onset, the level and any
# clipping can be inspected visually.
#
# Usage: python render_07c_spectrogram.py <wav> <png> <title>
# ==========================================================


import sys
import wave


import numpy as np

from PIL import Image, ImageDraw


W, H = 1000, 460


def load(path):

    with wave.open(path, "rb") as handle:

        channels = handle.getnchannels()
        rate = handle.getframerate()
        frames = handle.getnframes()
        raw = handle.readframes(frames)

    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)

    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)

    return rate, data


def spectrogram(data, rate, nfft=512, hop=160):

    window = np.hanning(nfft)

    n = max(1, (data.size - nfft) // hop)

    frames = np.lib.stride_tricks.as_strided(
        data,
        shape=(n, nfft),
        strides=(data.strides[0] * hop, data.strides[0]),
    ) * window

    spec = np.abs(np.fft.rfft(frames, axis=1))

    spec = 20 * np.log10(spec + 1e-6)

    spec = np.clip(spec, spec.max() - 80, spec.max())

    return spec.T  # (freq, time)


def main():

    path, out, title = sys.argv[1], sys.argv[2], sys.argv[3]

    rate, data = load(path)

    duration = data.size / float(rate)

    spec = spectrogram(data, rate)

    img = Image.new("RGB", (W, H), (255, 255, 255))

    draw = ImageDraw.Draw(img)

    # ---- waveform (top third) ----
    top_h = 150

    step = max(1, data.size // W)

    for x in range(W):

        chunk = data[x * step:(x + 1) * step]

        if chunk.size == 0:
            continue

        lo = float(chunk.min()) / 32768.0
        hi = float(chunk.max()) / 32768.0

        y0 = int(top_h / 2 - hi * (top_h / 2 - 4))
        y1 = int(top_h / 2 - lo * (top_h / 2 - 4))

        draw.line([(x, y0), (x, y1)], fill=(60, 90, 170))

    # ---- spectrogram (bottom two thirds) ----
    sh, sw = spec.shape

    for x in range(W):

        col = spec[:, int(x * sw / W)]

        for y in range(top_h + 20, H):

            idx = int((H - y) / (H - top_h - 20) * sh)

            if idx >= sh:
                continue

            v = col[idx]

            g = int(np.clip((v - (spec.max() - 80)) / 80.0, 0, 1) * 255)

            img.putpixel((x, y), (255 - g, 255 - int(g * 0.6), 255))

    draw.text((8, 4), "%s  (%.2f s @ %d Hz)" % (title, duration, rate),
              fill=(0, 0, 0))

    img.save(out)

    print("wrote", out)


if __name__ == "__main__":

    main()
