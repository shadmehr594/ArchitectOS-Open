# ==========================================================
# VOICE_07C — ROUND 6 : CONTROLLED BIAS TEST + MEANING SEARCH
#
# Required control (user instruction):
#   Run the SAME config (temp=0, greedy, condition_on_previous_text
#   =False) WITH and WITHOUT the ARCH initial_prompt, to determine
#   whether the prompt is BIASING Whisper toward Persian-looking text.
#
#   A "looks better" result that only appears when the prompt is
#   present is NOT evidence of a fix — it is prompt leakage.
#
# Also attempts to PRESERVE REAL MEANING with no prompt at all:
#   * language auto (does trimming fix language ID on its own?)
#   * full default temperature fallback
#   * zero-padding the short clip to Whisper's 30 s window
#   * the tail burst alone
#   * leading-only trim
#
# Nothing hardcodes the target sentence. Nothing post-corrects.
# ==========================================================


import json
import os
import sys
import time
import wave
import warnings


warnings.filterwarnings("ignore")


REPO = r"<repo-root>"

DIAG = os.path.join(REPO, ".pytest_tmp", "diag07c")

MODEL = "large-v3-turbo"

ARCH_PROMPT = "سلام. پروژه معماری. پلان. طراحی. معماری. تصویر. رندر. پروژه من."

TARGET = "سلام، پروژه من رو باز کردی؟"


def read_wav(path):

    import numpy as np

    with wave.open(path, "rb") as handle:

        ch = handle.getnchannels()
        rate = handle.getframerate()
        raw = handle.readframes(handle.getnframes())

    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)

    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)

    return rate, data


def write_wav(path, rate, samples):

    import numpy as np

    with wave.open(path, "wb") as handle:

        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(
            np.clip(samples, -32768, 32767).astype(np.int16).tobytes()
        )


def pad_to(source, target, seconds=30.0):

    import numpy as np

    rate, data = read_wav(source)

    want = int(seconds * rate)

    if data.size < want:

        data = np.concatenate([data, np.zeros(want - data.size)])

    write_wav(target, rate, data)

    return target


def run(model, path, label, **kwargs):

    started = time.time()

    try:
        result = model.transcribe(path, **kwargs)
    except Exception as error:
        return {"variant": label,
                "error": type(error).__name__ + ": " + str(error)}

    segments = result.get("segments") or []
    text = (result.get("text") or "").strip()
    words = text.split()
    first = segments[0] if segments else {}

    return {
        "variant": label,
        "text": text,
        "language": result.get("language"),
        "avg_logprob": (round(first.get("avg_logprob"), 4)
                        if first.get("avg_logprob") is not None else None),
        "compression_ratio": (round(first.get("compression_ratio"), 3)
                              if first.get("compression_ratio") is not None
                              else None),
        "unique_word_ratio": (round(len(set(words)) / float(len(words)), 3)
                              if words else None),
        "seconds": round(time.time() - started, 2),
    }


def main():

    import whisper

    model = whisper.load_model(MODEL, device="cpu")

    print("loaded\n", flush=True)

    GREEDY = dict(fp16=False, task="transcribe", language="fa",
                  verbose=False, condition_on_previous_text=False,
                  temperature=0.0)

    report = {"target": TARGET, "arch_prompt": ARCH_PROMPT,
              "recordings": {}}

    for key in ("030", "275"):

        trim = os.path.join(DIAG, "%s_trim16k.wav" % key)
        pad = os.path.join(DIAG, "%s_trim_pad30.wav" % key)

        pad_to(trim, pad)

        print("=" * 76)
        print("  %s" % key)
        print("=" * 76, flush=True)

        variants = [

            # ---- THE REQUIRED CONTROL ------------------------------
            ("E1  GREEDY temp0 no-prev, NO prompt      << CONTROL",
             trim, dict(GREEDY)),

            ("E2  GREEDY temp0 no-prev, ARCH prompt    << CANDIDATE",
             trim, dict(GREEDY, initial_prompt=ARCH_PROMPT)),

            # ---- does trimming fix language ID on its own? --------
            ("E3  GREEDY temp0 no-prev, language=AUTO, NO prompt",
             trim, dict(GREEDY, language=None)),

            # ---- meaning-preservation attempts (no prompt) --------
            ("E4  DEFAULT temp fallback, no-prev, NO prompt",
             trim, dict(fp16=False, task="transcribe", language="fa",
                        verbose=False, condition_on_previous_text=False,
                        temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0))),

            ("E5  GREEDY temp0 no-prev, NO prompt, padded to 30 s",
             pad, dict(GREEDY)),

            ("E6  GREEDY temp0 no-prev, NO prompt, beam_size=5",
             trim, dict(GREEDY, beam_size=5)),
        ]

        results = []

        for label, target, options in variants:

            outcome = run(model, target, label, **options)
            results.append(outcome)

            print("  %-54s" % label, flush=True)
            print("      %s" % outcome.get("text"), flush=True)
            print("      lang %s | avg %s | comp %s | uniq %s | %ss"
                  % (outcome.get("language"), outcome.get("avg_logprob"),
                     outcome.get("compression_ratio"),
                     outcome.get("unique_word_ratio"),
                     outcome.get("seconds")), flush=True)
            print(flush=True)

        report["recordings"][key] = results

        with open(os.path.join(DIAG, "round6_report.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)

    print("DONE -> .pytest_tmp/diag07c/round6_report.json")

    return 0


if __name__ == "__main__":

    sys.exit(main())
