# -*- coding: utf-8 -*-
"""PERSIAN_TTS_PRONUNCIATION_V1 — human-listening fixture set (Part B).

Generates the EXACT sentences the brief requires, with BOTH fa-IR voices,
plus a focused «خلوت» set, into ONE organised folder with an index so a
human can listen and judge pronunciation directly.

Whisper is deliberately NOT used as proof of pronunciation.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.voice.persian_tts_v1 import PERSIAN_VOICES  # noqa: E402

OUT = os.path.join(ROOT, ".pytest_tmp", "tts_listening_set_v1")

# The brief's required minimum inputs.
TEXTS = [
    "حیاط خلوت",
    "خلوت",
    "حیاط",
    "ذخیره",
    "آشپزخانه",
    "معماری",
    "آشپزخانه کنار حیاط خلوت قرار دارد.",
    "فعلاً این اطلاعات را ذخیره نکن.",
    "در معماری، حیاط یک فضای باز در ساختمان است.",
    # combined live-browser sentence (Part B / live validation)
    "آشپزخانه کنار حیاط خلوت قرار دارد و فعلاً این اطلاعات را ذخیره نمی‌کنم.",
]


async def _synth(text, voice):
    import edge_tts

    com = edge_tts.Communicate(text, voice)
    buf = bytearray()
    async for ch in com.stream():
        if ch.get("type") == "audio" and ch.get("data"):
            buf.extend(ch["data"])
    return bytes(buf)


async def main():
    os.makedirs(OUT, exist_ok=True)
    index = []

    print("=" * 78)
    print("PART B — human-listening fixture set")
    print("=" * 78)

    for i, text in enumerate(TEXTS, 1):
        for voice in PERSIAN_VOICES:
            data = await _synth(text, voice)
            short = "dilara" if "Dilara" in voice else "farid"
            fn = f"{i:02d}_{short}.mp3"
            with open(os.path.join(OUT, fn), "wb") as fh:
                fh.write(data)
            index.append({
                "n": i, "display_text": text, "voice": voice,
                "file": fn, "bytes": len(data),
                "dur_s": round(len(data) / 6000, 2),
            })
            print(f"  [{i:02d}] {short:<6} {len(data):>7}B  {text}")

    with open(os.path.join(OUT, "INDEX.md"), "w", encoding="utf-8") as fh:
        fh.write("# PART B — TTS human-listening set\n\n")
        fh.write("Listen to each pair and judge pronunciation of:\n")
        fh.write("خلوت · حیاط · معماری · آشپزخانه · ذخیره\n\n")
        fh.write("| # | display_text | Dilara (F) | Farid (M) |\n")
        fh.write("|---|--------------|-----------|-----------|\n")
        for i, text in enumerate(TEXTS, 1):
            fh.write(f"| {i:02d} | {text} | `{i:02d}_dilara.mp3` | `{i:02d}_farid.mp3` |\n")

    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)

    print(f"\nlistening set -> {OUT}")
    print(f"index        -> {os.path.join(OUT, 'INDEX.md')}")


if __name__ == "__main__":
    asyncio.run(main())
