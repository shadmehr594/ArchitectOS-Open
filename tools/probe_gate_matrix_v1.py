# -*- coding: utf-8 -*-
"""Acceptance of the recalibrated STT gate on representative metric profiles."""

import importlib.util
import sys

sys.stdout.reconfigure(encoding="utf-8")

spec = importlib.util.spec_from_file_location(
    "w", "tools/whisper_stt_worker.py"
)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


def decide(text, mean, mn, al, lang="auto", det=None, nsp=None):
    q = w.assess_quality(
        text, {"compression_ratio": 1.0}, None, lang,
        mean_word_probability=mean, min_word_probability=mn,
        avg_logprob=al, no_speech_probability=nsp, detected_language=det,
    )
    reason = None
    if not q["usable"]:
        reason = (
            "script_mismatch" if q["script_mismatch_suspected"]
            else q.get("low_confidence_reason")
            or ("repetition" if q["repetition_suspected"] else "?")
        )
    return q["usable"], reason


CASES = [
    ("normal speech, one unclear word", "یک کمی راجع به معماری صحبت کنیم", 0.88, 0.58, -0.30, "fa", None),
    ("normal speech, two unclear", "یک کمی راجع به معماری صحبت کنیم", 0.86, 0.52, -0.35, "fa", None),
    ("mumbled in broadly-unclear", "الف ب پ ت ث", 0.70, 0.55, -0.70, "fa", None),
    ("soft but fine", "سلام خوبی", 0.80, 0.62, -0.45, "fa", None),
    ("short real reply", "باشه", 0.90, 0.90, -0.40, "fa", None),
    ("short hallucination", "شلو", 0.46, 0.46, -0.857, "fa", None),
    ("real ok speech", "سلام میخوام در مورد معماری صحبت کنیم", 0.92, 0.82, -0.20, "fa", None),
    ("Salud auto", "Salud.", 0.895, 0.895, -0.306, "auto", "en"),
    ("Salud auto, det fa", "Salud.", 0.895, 0.895, -0.306, "auto", "fa"),
    ("real english", "Hello how are you today", 0.95, 0.85, -0.25, "auto", "en"),
    ("silence halluc", "Thank you.", 0.6265, 0.2541, -0.219, "auto", "en"),
]

print(f"{'DECISION':8} {'CASE':34} {'mean':>6} {'min':>6} {'avglp':>7}  note")
print("-" * 90)

for name, text, mean, mn, al, lang, det in CASES:
    ok, reason = decide(text, mean, mn, al, lang, det)
    print(
        f"{'ACCEPT' if ok else 'reject':8} {name:34} "
        f"{mean:>6} {mn:>6} {al:>7}  {reason or ''}"
    )
