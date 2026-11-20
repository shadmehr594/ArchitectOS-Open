# -*- coding: utf-8 -*-
"""PERSIAN_VOICE_QUALITY_V2 / PHASE 3 — Persian TTS naturalness audit.

Read-only (writes audio fixtures only). Answers, with evidence:

  1. What fa-IR voices does edge-tts ACTUALLY expose right now?
  2. Does the engine accept plain text only, or SSML/prosody too?
  3. Is the problem upstream (bad text) rather than the provider?
     -> synthesise CLEAN hand-typed Persian vs MALFORMED STT-derived
        text and report byte size / duration proxy for each.
  4. Mixed Persian/Latin token handling: does "ArchitectOS" inside a
     Persian sentence change the output at all?

Human listening is limited in this environment; this audit reports the
OBSERVABLE facts (voice list, prosody support, sizes) and leaves the
subjective "sounds Iranian" judgement to the operator, with the exact
command to reproduce.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


CLEAN = [
    "سلام، من ArchitectOS هستم.",
    "بیا کمی درباره معماری صحبت کنیم.",
    "آشپزخانه کنار حیاط خلوت قرار دارد.",
    "فعلاً این اطلاعات را ذخیره نکن.",
    "در طراحی این خانه، نور طبیعی اهمیت زیادی دارد.",
]

# STT-derived (the exact malformed forms Whisper produced on this machine)
MALFORMED = [
    "بیا در باره مماری صحبت کنیم.",
    "آشپسخانه کنار حیات خلوت است.",
    "فعلا این اطلاعات را زخیره نکن.",
    "در تراحی این خانه نور طبیعی اهمیت دارد.",
]

WORDS = ["معماری", "آشپزخانه", "حیاط خلوت", "ذخیره", "معمار", "نما", "پلان"]


def _dur_proxy(mp3_bytes: int):
    """Approximate seconds from MP3 bytes at the edge-tts default rate.

    edge-tts emits ~48 kbps audio; bytes/6 gives a roughly seconds-scale
    proxy. Reported ONLY as a comparative figure, never as a claim.
    """

    return round(mp3_bytes / 6000.0, 2)


async def _voice_list():
    import edge_tts

    voices = await edge_tts.list_voices()
    fa = [v for v in voices if str(v.get("Locale", "")).lower().startswith("fa")]
    return fa


async def _synth(text, voice):
    import edge_tts

    com = edge_tts.Communicate(text, voice)
    buf = bytearray()
    async for chunk in com.stream():
        if chunk.get("type") == "audio" and chunk.get("data"):
            buf.extend(chunk["data"])
    return bytes(buf)


async def _synth_ssml(ssml, voice):
    """Try SSML via edge-tts; report clearly whether it is accepted."""

    import edge_tts

    com = edge_tts.Communicate(ssml, voice)
    buf = bytearray()
    async for chunk in com.stream():
        if chunk.get("type") == "audio" and chunk.get("data"):
            buf.extend(chunk["data"])
    return bytes(buf)


async def _main_async():
    from core.voice.persian_tts_v1 import describe, PERSIAN_VOICES

    out_dir = os.path.join(ROOT, ".pytest_tmp", "tts_audit_v2")
    os.makedirs(out_dir, exist_ok=True)

    report = {"provider": describe()}

    print("=" * 74)
    print("PERSIAN VOICE QUALITY V2 / PHASE 3 — TTS audit")
    print("=" * 74)
    print("\n[1] edge-tts fa-IR voices actually exposed:")
    try:
        fa = await _voice_list()
        report["edge_fa_voices"] = fa
        for v in fa:
            print(f"    {v.get('ShortName')} | {v.get('Gender')} | {v.get('Locale')}")
        names = [v.get("ShortName") for v in fa]
        print(f"    -> {len(fa)} Persian voice(s): {names}")
    except Exception as error:
        print(f"    voice listing FAILED: {type(error).__name__}: {error}")
        report["edge_fa_voices_error"] = str(error)

    print("\n[2] SSML / prosody support:")
    ssml = (
        '<speak version="1.0" xml:lang="fa-IR">'
        '<prosody rate="+5%" pitch="+0Hz">سلام، من ArchitectOS هستم.</prosody>'
        '</speak>'
    )
    try:
        data = await _synth_ssml(ssml, PERSIAN_VOICES[0])
        report["ssml_accepted"] = bool(data)
        report["ssml_bytes"] = len(data)
        print(f"    SSML accepted? {'YES' if data else 'NO'} ({len(data)} bytes)")
        if data:
            print("    NOTE: edge-tts may treat SSML as literal text or strip it;")
            print("          byte count alone does not prove prosody was applied.")
    except Exception as error:
        report["ssml_accepted"] = False
        report["ssml_error"] = f"{type(error).__name__}: {error}"
        print(f"    SSML REJECTED: {type(error).__name__}: {error}")

    print("\n[3] CLEAN typed Persian (both fa-IR voices):")
    clean_rows = []
    for voice in PERSIAN_VOICES:
        for text in CLEAN:
            try:
                data = await _synth(text, voice)
                fn = f"clean_{voice}_{abs(hash(text)) % 10**8}.mp3"
                with open(os.path.join(out_dir, fn), "wb") as fh:
                    fh.write(data)
                row = {"voice": voice, "text": text, "bytes": len(data),
                       "dur_proxy_s": _dur_proxy(len(data)), "file": fn}
                print(f"    [{voice}] {len(data):>6} B  ~{row['dur_proxy_s']:>5}s  {text[:40]}")
            except Exception as error:
                row = {"voice": voice, "text": text,
                       "error": f"{type(error).__name__}: {error}"}
                print(f"    [{voice}] FAILED: {row['error']}")
            clean_rows.append(row)
    report["clean"] = clean_rows

    print("\n[4] MALFORMED STT-derived (same voice, to isolate text quality):")
    mal_rows = []
    for text in MALFORMED:
        try:
            data = await _synth(text, PERSIAN_VOICES[0])
            fn = f"malformed_{abs(hash(text)) % 10**8}.mp3"
            with open(os.path.join(out_dir, fn), "wb") as fh:
                fh.write(data)
            row = {"text": text, "bytes": len(data),
                   "dur_proxy_s": _dur_proxy(len(data)), "file": fn}
            print(f"    {len(data):>6} B  ~{row['dur_proxy_s']:>5}s  {text[:44]}")
        except Exception as error:
            row = {"text": text, "error": f"{type(error).__name__}: {error}"}
            print(f"    FAILED: {row['error']}")
        mal_rows.append(row)
    report["malformed"] = mal_rows

    print("\n[5] ARCHITECTURAL VOCABULARY (isolated words):")
    vocab_rows = []
    for word in WORDS:
        try:
            data = await _synth(word, PERSIAN_VOICES[0])
            fn = f"word_{abs(hash(word)) % 10**8}.mp3"
            with open(os.path.join(out_dir, fn), "wb") as fh:
                fh.write(data)
            row = {"word": word, "bytes": len(data),
                   "dur_proxy_s": _dur_proxy(len(data)), "file": fn}
            print(f"    {len(data):>6} B  ~{row['dur_proxy_s']:>5}s  {word}")
        except Exception as error:
            row = {"word": word, "error": f"{type(error).__name__}: {error}"}
            print(f"    FAILED: {row['error']}")
        vocab_rows.append(row)
    report["vocabulary"] = vocab_rows

    path = os.path.join(out_dir, "tts_phase3.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(f"\nsaved -> {path}")
    print(f"audio fixtures -> {out_dir}")


def main():
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
