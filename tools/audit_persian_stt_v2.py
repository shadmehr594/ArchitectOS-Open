# -*- coding: utf-8 -*-
"""PERSIAN VOICE QUALITY V2 — STT lexical audit (read-only).

Runs the REAL Whisper STT provider (voice_stt_whisper_v1) against:
  * the two REAL human Persian recordings already on disk;
  * controlled Persian phrases synthesised with edge-tts (clean audio),
    covering the word list the brief names.

It records, per case: EXPECTED / RAW WHISPER / LANGUAGE / AVG_LOGPROB /
MEAN+MIN WORD PROB / INTERPRETED UTTERANCE / status+reason. It changes
NOTHING — it only observes.

Run: .venv/Scripts/python.exe tools/audit_persian_stt_v2.py
"""

import io
import json
import os
import sys
import time
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.voice.voice_stt_whisper_v1 import transcribe
from core.voice.persian_tts_v1 import synthesize
from core.chat.spoken_language_interpretation_v1 import interpret_utterance


OUT_DIR = os.path.join(".pytest_tmp", "stt_audit_v2")
os.makedirs(OUT_DIR, exist_ok=True)


PHRASES = [
    ("معماری (isolated)",              "معماری"),
    ("درباره معماری صحبت کنیم",        "بیا درباره معماری صحبت کنیم"),
    ("آشپزخانه (isolated)",            "آشپزخانه"),
    ("آشپزخانه کنار حیاط خلوت",         "آشپزخانه کنار حیاط خلوت است"),
    ("حیاط خلوت (isolated)",           "حیاط خلوت"),
    ("آشپزی (isolated)",               "آشپزی"),
    ("ذخیره (isolated)",               "ذخیره"),
    ("فعلاً ذخیره نکن",                "فعلاً این اطلاعات را ذخیره نکن"),
    ("خودت رو معرفی کن",               "لطفاً خودت رو معرفی کن"),
    ("یاد بدم نکته معماری",            "من می‌خوام یه نکته معماری بهت یاد بدم"),
    ("نور طبیعی",                      "در طراحی این خانه نور طبیعی اهمیت زیادی دارد"),
    ("معمار (isolated)",               "معمار"),
    ("نما (isolated)",                 "نما"),
    ("پلان (isolated)",                "پلان"),
]

# the two real human recordings (from the 07C/07D evidence)
REAL = [
    ("REAL 765", "data/projects/project_042039a7/documents/voice_765_367dd5.webm"),
    ("REAL 798", "data/projects/project_042039a7/documents/voice_798_108dca.webm"),
]


def _mp3_to_wav(mp3_bytes, wav_path):
    """Convert edge-tts MP3 to 16k mono wav via ffmpeg (already a dep)."""
    import shutil
    import subprocess
    import tempfile

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    tmp_mp3 = wav_path + ".mp3"
    with open(tmp_mp3, "wb") as fh:
        fh.write(mp3_bytes)
    done = subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-i", tmp_mp3, "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", wav_path],
        capture_output=True, text=True,
    )
    os.remove(tmp_mp3)
    return done.returncode == 0


def _row(label, expected, path):
    t0 = time.time()
    res = transcribe(path, language="fa")
    dt = round(time.time() - t0, 2)

    raw = res.get("transcript") or res.get("raw_transcript")
    interp = None
    try:
        interp = interpret_utterance(raw or "", language="fa")
    except Exception:
        interp = None

    return {
        "label": label,
        "expected": expected,
        "status": res.get("status"),
        "reason": res.get("reason"),
        "raw": raw,
        "language": res.get("detected_language"),
        "avg_logprob": res.get("avg_logprob"),
        "mean_wp": res.get("mean_word_probability"),
        "min_wp": res.get("min_word_probability"),
        "interpreted": (interp or {}).get("interpreted_utterance"),
        "changes": (interp or {}).get("changes"),
        "seconds": dt,
    }


def main():
    rows = []

    print("=" * 100)
    print("PERSIAN VOICE QUALITY V2 — STT LEXICAL AUDIT (real provider, read-only)")
    print("=" * 100)
    print("Model: large-v3-turbo  |  provider: openai-whisper  |  language hint: fa")
    print("-" * 100)

    # ---- real human recordings ----
    for label, rel in REAL:
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), rel)
        if not os.path.isfile(path):
            print("MISSING:", rel)
            continue
        row = _row(label, "(real human speech)", path)
        rows.append(row)

    # ---- controlled clean Persian audio (edge-tts) ----
    for label, text in PHRASES:
        synth = synthesize(text)
        if synth.get("status") != "ok":
            row = {"label": label, "expected": text, "status": "tts_failed",
                   "reason": synth.get("reason"), "raw": None}
            rows.append(row)
            continue
        wav = os.path.join(OUT_DIR, "gen_%d.wav" % (len(rows)))
        if not _mp3_to_wav(synth["audio"], wav):
            rows.append({"label": label, "expected": text,
                         "status": "convert_failed", "raw": None})
            continue
        row = _row(label, text, wav)
        rows.append(row)

    # ---- print table ----
    print("%-30s %-13s %-26s %-9s %-8s" % (
        "CASE", "STATUS", "RAW WHISPER", "LANG", "avg_lp"))
    print("-" * 100)
    for r in rows:
        print("%-30s %-13s %-26s %-9s %-8s" % (
            r.get("label", "")[:30],
            str(r.get("status"))[:13],
            str(r.get("raw"))[:26],
            str(r.get("language"))[:9],
            str(r.get("avg_logprob")),
        ))
        print("    EXPECTED : %s" % r.get("expected"))
        print("    RAW      : %s" % r.get("raw"))
        print("    meanWP=%s minWP=%s" % (r.get("mean_wp"), r.get("min_wp")))
        print("    INTERPRET: %s" % r.get("interpreted"))
        if r.get("changes"):
            print("    CHANGES  : %s" % json.dumps(
                r["changes"], ensure_ascii=False))
        print()

    out = os.path.join(OUT_DIR, "stt_audit.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    print("saved:", out)


if __name__ == "__main__":
    main()
