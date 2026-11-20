# -*- coding: utf-8 -*-
"""PERSIAN_VOICE_QUALITY_V2 / PHASE 3 — spoken-text preparation tests.

Proves the TTS input guard without requiring audio playback:

  * markup/SSML is stripped (edge-tts would otherwise SPEAK it aloud —
    measured: 70128 B vs 15552 B for the same sentence)
  * clean Persian is left byte-identical (no spelling "fixing")
  * Latin technical tokens survive (ArchitectOS stays ArchitectOS)
  * the written reply is never modified (this is input prep only)
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.voice.persian_tts_v1 import (  # noqa: E402
    prepare_spoken_text,
    synthesize,
)

CASES = [
    # (input, expected)
    ("سلام، من ArchitectOS هستم.", "سلام، من ArchitectOS هستم."),
    ("<speak><prosody rate='+5%'>سلام</prosody></speak>", "سلام"),
    ("سلام <b>دنیا</b>", "سلام دنیا"),
    ("A &amp; B", "A B"),
    ("متن `کد` **زنجیره**", "متن کد زنجیره"),
    ("  فاصله‌های   اضافی  ", "فاصله‌های اضافی"),
    ("نور طبیعی\nاهمیت دارد", "نور طبیعی اهمیت دارد"),
]

fails = 0
print("=" * 70)
print("PHASE 3 — spoken-text preparation")
print("=" * 70)
for src, want in CASES:
    got = prepare_spoken_text(src)
    ok = got == want
    if not ok:
        fails += 1
    print(f"[{'PASS' if ok else 'FAIL'}] {src!r}")
    print(f"        -> {got!r}")
    if not ok:
        print(f"        want {want!r}")

# The guard must NEVER alter a clean sentence (no spelling normalisation)
clean = "آشپزخانه کنار حیاط خلوت قرار دارد."
assert prepare_spoken_text(clean) == clean, "clean text must be untouched"
print(f"[PASS] clean architectural sentence untouched: {clean!r}")

# ---- end-to-end: synthesize must still return audio for clean text ----
print("\n--- end-to-end synthesize smoke ---")
res = synthesize("سلام، من ArchitectOS هستم.")
print(f"status={res['status']} voice={res['voice']} bytes={res['audio_bytes']}")
assert res["status"] == "ok" and res["audio_bytes"] > 0
print(f"supports_ssml advertised: {__import__('core.voice.persian_tts_v1', fromlist=['describe']).describe()['supports_ssml']}")

print("\n" + "=" * 70)
print(f"RESULT: {'ALL PASS' if fails == 0 else str(fails) + ' FAIL'}")
sys.exit(1 if fails else 0)
