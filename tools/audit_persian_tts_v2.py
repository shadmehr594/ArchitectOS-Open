# -*- coding: utf-8 -*-
"""PERSIAN VOICE QUALITY V2 — TTS quality audit (read-only).

Isolates TTS quality from STT quality by synthesising CLEAN, hand-typed
Persian (never STT output) and inspecting the real audio bytes.

It also synthesises the MALFORMED forms observed in the STT audit, so the
two can be compared (does the engine hallucinate on bad spelling, or is
the engine fine and only the input text wrong?).

Read-only: writes only .pytest_tmp artifacts.

Run: .venv/Scripts/python.exe tools/audit_persian_tts_v2.py
"""

import json
import os
import struct
import wave

from core.voice.persian_tts_v1 import synthesize, voices, describe


OUT = os.path.join(".pytest_tmp", "tts_audit_v2")
os.makedirs(OUT, exist_ok=True)


CLEAN = [
    "سلام، من ArchitectOS هستم.",
    "بیا کمی درباره معماری صحبت کنیم.",
    "آشپزخانه کنار حیاط خلوت قرار دارد.",
    "فعلاً این اطلاعات را ذخیره نکن.",
    "در طراحی این خانه، نور طبیعی اهمیت زیادی دارد.",
]

# the exact malformed forms the STT audit produced
MALFORMED = [
    "بیا در باره مماری صحبت کنیم.",
    "آشبازخانه",
    "آشپسخانه کنار حیات خلوت است.",
    "زخیره",
    "در تراحی این خانه نور طبیعی اهمیت زیادی دارد.",
]


def _mp3_frames(mp3):
    """Count MPEG audio frames for a rough duration estimate."""
    count = 0
    i = 0
    n = len(mp3)
    while i < n - 4:
        if mp3[i] == 0xFF and (mp3[i + 1] & 0xE0) == 0xE0:
            bitrate_index = (mp3[i + 2] >> 4) & 0x0F
            if 0 < bitrate_index < 15:
                count += 1
        i += 1
    return count


def _stats(res):
    audio = res.get("audio") or b""
    frames = _mp3_frames(audio)
    # 128 kbps @44.1k => ~26.12 ms/frame
    duration = round(frames * 0.02612, 2)
    return len(audio), duration


def run(label, text, voice=None):
    res = synthesize(text, voice=voice)
    if res.get("status") != "ok":
        return {
            "label": label, "text": text, "status": res.get("status"),
            "reason": res.get("reason"), "voice": res.get("voice"),
            "bytes": 0, "approx_seconds": None,
        }
    nbytes, dur = _stats(res)
    path = os.path.join(OUT, "%s.mp3" % label.replace(" ", "_"))
    with open(path, "wb") as fh:
        fh.write(res["audio"])
    return {
        "label": label, "text": text, "status": "ok", "reason": None,
        "voice": res.get("voice"), "bytes": nbytes,
        "approx_seconds": dur, "path": path,
    }


def main():
    print("=" * 90)
    print("PERSIAN VOICE QUALITY V2 — TTS QUALITY AUDIT (read-only)")
    print("=" * 90)
    print("describe():", json.dumps(describe(), ensure_ascii=False))
    print("voices    :", voices())
    print("-" * 90)

    rows = []

    print("A) CLEAN hand-typed Persian (isolates TTS from STT)")
    for i, text in enumerate(CLEAN):
        r = run("clean_%02d" % i, text)
        rows.append(r)
        print("  %-5s %-14s %-6s %-8s %s" % (
            r["status"], str(r["voice"]), str(r["bytes"]),
            str(r["approx_seconds"]), text))

    print()
    print("B) MALFORMED forms observed from STT (same engine)")
    for i, text in enumerate(MALFORMED):
        r = run("bad_%02d" % i, text)
        rows.append(r)
        print("  %-5s %-14s %-6s %-8s %s" % (
            r["status"], str(r["voice"]), str(r["bytes"]),
            str(r["approx_seconds"]), text))

    print()
    print("C) VOICE COMPARISON — same clean sentence, both fa-IR voices")
    for v in voices():
        r = run("voice_%s" % v.split("-")[-1], CLEAN[1], voice=v)
        rows.append(r)
        print("  %-22s %-5s %-8s %s" % (
            v, r["status"], str(r["bytes"]), CLEAN[1]))

    with open(os.path.join(OUT, "tts_audit.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    print("\nsaved:", os.path.join(OUT, "tts_audit.json"))


if __name__ == "__main__":
    main()
