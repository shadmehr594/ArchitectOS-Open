# -*- coding: utf-8 -*-
"""HUMAN_VOICE_CONVERSATION_V1 — STT acceptance evidence probe.

Runs the REAL `tools/whisper_stt_worker.py` (system Python 3.11) on real
recordings and on synthesised silence/noise controls, printing the exact
quality metrics and the accept/reject decision.

Read-only: it never modifies a recording and never writes to the project.
"""

import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"<repo-root>"
WORKER = os.path.join(ROOT, "tools", "whisper_stt_worker.py")
INTERPRETER = os.environ.get("ARCHITECTOS_VOICE_PYTHON", sys.executable)
MODEL = "large-v3-turbo"

REAL = [
    ("real 765 (known OK)", "data/projects/project_042039a7/documents/voice_765_367dd5.webm"),
    ("real 798 (known OK)", "data/projects/project_042039a7/documents/voice_798_108dca.webm"),
    ("real 030 (known WRONG)", "data/projects/project_23e5dae6/documents/voice_030_9e1635.webm"),
    ("real 275 (known WRONG)", "data/projects/project_23e5dae6/documents/voice_275_c9bc97.webm"),
    ("real 160", "data/projects/project_042039a7/documents/voice_160_0430dd.webm"),
]


def make_control(kind, path, seconds=3.0, rate=16000):
    """Synthesise a control WAV: silence, white noise, or a tone burst
    that mimics a soft spoken onset (to prove normal audio is not falsely
    rejected by the presence gate)."""

    import numpy as np
    import wave

    n = int(rate * seconds)

    if kind == "silence":
        data = np.zeros(n, dtype=np.int16)
    elif kind == "noise":
        rng = np.random.default_rng(7)
        data = (rng.normal(0, 300, n)).clip(-32768, 32767).astype(np.int16)
    else:  # soft spoken-like burst (amplitude-modulated tone)
        t = np.arange(n) / rate
        carrier = np.sin(2 * np.pi * 180 * t)
        envelope = (np.sin(2 * np.pi * 3.0 * t) * 0.5 + 0.5)
        # start after a natural 0.8s pause
        data = np.zeros(n)
        start = int(0.8 * rate)
        data[start:] = carrier[start:] * envelope[start:] * 6000
        data = data.astype(np.int16)

    with wave.open(path, "wb") as h:
        h.setnchannels(1)
        h.setsampwidth(2)
        h.setframerate(rate)
        h.writeframes(data.tobytes())

    return path


def run_worker(audio_path, language="auto"):
    request = json.dumps({
        "audio_path": os.path.abspath(audio_path),
        "language": language,
        "model": MODEL,
        "preprocess": True,
    })

    completed = subprocess.run(
        [INTERPRETER, WORKER],
        input=request,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        timeout=10800,
    )

    payload = None
    for line in reversed((completed.stdout or "").splitlines()):
        if line.strip().startswith("{"):
            try:
                payload = json.loads(line.strip())
                break
            except Exception:
                continue
    return payload


def main():

    import tempfile

    tmp = tempfile.mkdtemp(prefix="hv_v1_")

    controls = [
        ("CONTROL silence 3s", make_control("silence", os.path.join(tmp, "sil.wav"))),
        ("CONTROL noise-only 3s", make_control("noise", os.path.join(tmp, "noi.wav"))),
        ("CONTROL tone-burst 3s", make_control("tone", os.path.join(tmp, "ton.wav"))),
    ]

    rows = []

    for label, rel in REAL:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            rows.append((label, "MISSING", {}))
            continue
        p = run_worker(path)
        rows.append((label, None, p or {}))

    for label, path in controls:
        p = run_worker(path)
        rows.append((label, None, p or {}))

    print("\n" + "=" * 100)
    print(f"{'CASE':32} {'STATUS':14} {'REASON':26} {'meanWP':>7} {'minWP':>7} {'avg_lp':>8}")
    print("=" * 100)

    for label, missing, p in rows:
        if missing:
            print(f"{label:32} {missing}")
            continue
        q = p.get("quality") or {}
        print(
            f"{label:32} "
            f"{str(p.get('status')):14} "
            f"{str(p.get('reason')):26} "
            f"{str(p.get('mean_word_probability')):>7} "
            f"{str(p.get('min_word_probability')):>7} "
            f"{str(round(p.get('avg_logprob'), 3) if p.get('avg_logprob') is not None else None):>8}"
        )
        print(f"{'':32} no_speech={p.get('no_speech_prob')} q={q}")
        t = p.get("raw_transcript") or ""
        if t:
            print(f"{'':32} raw: {t}")

    print("=" * 100)


if __name__ == "__main__":
    main()
