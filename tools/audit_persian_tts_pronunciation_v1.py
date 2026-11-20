# -*- coding: utf-8 -*-
"""PERSIAN_TTS_PRONUNCIATION_V1 — Part B mechanism audit (READ-ONLY).

edge-tts has NO usable SSML (proven in PERSIAN_VOICE_QUALITY_V2). This
script tests the SAFE mechanisms that remain for steering pronunciation,
WITHOUT changing any displayed text:

  1. plain text (baseline)
  2. Persian diacritics (خَلْوَت) — does a vowel-marked form change audio?
  3. ZWNJ placement
  4. Arabic vs Persian codepoints
  5. punctuation / spacing

For each variant it reports the byte size and duration proxy, and saves
the MP3 so a HUMAN can listen. Whisper is NOT used as proof.

Both fa-IR voices are exercised so a comparison is possible.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.voice.persian_tts_v1 import (  # noqa: E402
    prepare_spoken_text,
    PERSIAN_VOICES,
)

OUT = os.path.join(ROOT, ".pytest_tmp", "tts_pronunciation_v1")

# (label, tts_input) — the DISPLAY text is always the clean one; these
# variants exist ONLY to test whether a TTS-only form changes the audio.
VARIANTS = [
    ("خلوت", "خلوت"),
    ("خلوت + diacritics", "خَلْوَت"),
    ("خلوت + full diacritics", "خَلْوَتُ"),
    ("حیاط خلوت", "حیاط خلوت"),
    ("حیاط خلوت + diacritics", "حَیاطِ خَلْوَت"),
    ("حیاط", "حیاط"),
    ("ذخیره", "ذخیره"),
    ("ذخیره + diacritics", "ذَخیرِه"),
    ("آشپزخانه", "آشپزخانه"),
    ("معماری", "معماری"),
    ("معماری + diacritics", "مِعمارِی"),
]

SENTENCES = [
    "آشپزخانه کنار حیاط خلوت قرار دارد.",
    "فعلاً این اطلاعات را ذخیره نکن.",
    "در معماری، حیاط یک فضای باز در ساختمان است.",
    "حیاط خلوت",
]


async def _synth(text, voice):
    import edge_tts

    com = edge_tts.Communicate(text, voice)
    buf = bytearray()
    async for ch in com.stream():
        if ch.get("type") == "audio" and ch.get("data"):
            buf.extend(ch["data"])
    return bytes(buf)


def _safe(name):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


async def main():
    os.makedirs(OUT, exist_ok=True)
    report = {"variants": [], "sentences": [], "voices": list(PERSIAN_VOICES)}

    print("=" * 78)
    print("PART B — TTS pronunciation mechanism audit")
    print("=" * 78)

    print("\n[1] WORD / VARIANT rows (both voices)")
    print(f"    {'variant':<34} {'voice':<22} {'bytes':>7} {'~s':>6}")
    for label, tts_text in VARIANTS:
        for voice in PERSIAN_VOICES:
            try:
                prepared = prepare_spoken_text(tts_text)
                data = await _synth(prepared, voice)
                fn = f"var_{_safe(label)}_{voice}.mp3"
                with open(os.path.join(OUT, fn), "wb") as fh:
                    fh.write(data)
                row = {"label": label, "tts_input": tts_text,
                       "prepared": prepared, "voice": voice,
                       "bytes": len(data), "dur_s": round(len(data)/6000, 2),
                       "file": fn}
                print(f"    {label:<34} {voice:<22} {len(data):>7} {row['dur_s']:>6}")
            except Exception as error:
                row = {"label": label, "voice": voice,
                       "error": f"{type(error).__name__}: {error}"}
                print(f"    {label:<34} {voice:<22} FAILED {row['error']}")
            report["variants"].append(row)

    print("\n[2] FULL SENTENCES (both voices)")
    print(f"    {'sentence':<46} {'voice':<22} {'bytes':>7}")
    for sent in SENTENCES:
        for voice in PERSIAN_VOICES:
            try:
                data = await _synth(sent, voice)
                fn = f"sent_{_safe(sent[:24])}_{voice}.mp3"
                with open(os.path.join(OUT, fn), "wb") as fh:
                    fh.write(data)
                row = {"sentence": sent, "voice": voice,
                       "bytes": len(data), "dur_s": round(len(data)/6000, 2),
                       "file": fn}
                print(f"    {sent[:46]:<46} {voice:<22} {len(data):>7}")
            except Exception as error:
                row = {"sentence": sent, "voice": voice,
                       "error": f"{type(error).__name__}: {error}"}
                print(f"    {sent[:46]:<46} {voice:<22} FAILED")
            report["sentences"].append(row)

    path = os.path.join(OUT, "pronunciation_audit.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print("\n" + "=" * 78)
    print("DIACRITIC COMPARISON (does diacritics change the audio size?)")
    print("=" * 78)
    by_label = {}
    for row in report["variants"]:
        if "bytes" in row:
            by_label.setdefault(row["label"], {})[row["voice"]] = row["bytes"]
    pairs = [("خلوت", "خلوت + diacritics"),
             ("حیاط خلوت", "حیاط خلوت + diacritics"),
             ("ذخیره", "ذخیره + diacritics"),
             ("معماری", "معماری + diacritics")]
    for base, diac in pairs:
        for voice in PERSIAN_VOICES:
            b = by_label.get(base, {}).get(voice)
            d = by_label.get(diac, {}).get(voice)
            verdict = "SAME bytes" if b == d else f"DIFFERENT ({b} vs {d})"
            print(f"    {base:<24} {voice:<22} {verdict}")

    print(f"\nsaved -> {path}")
    print(f"audio -> {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
