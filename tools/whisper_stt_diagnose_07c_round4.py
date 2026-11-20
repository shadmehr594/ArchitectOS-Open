# ==========================================================
# VOICE_07C — ROUND 4 : DECODING-CONFIGURATION SEARCH
#
# Round 3 proved (isolation X vs Y) that removing ~2 s of leading
# silence is the decisive factor: the SAME decoder returns Latin
# garbage on the untrimmed clip and Persian on the trimmed clip.
#
# Round 4 now finds the SAFEST decoding configuration on the
# trimmed clip, and — crucially — checks whether a bounded Persian
# initial_prompt is actually NEEDED, and whether it can be made
# safe (no echo / no repetition loop).
#
# Emits `compression_ratio` so a truthful repetition guard can be
# designed from real numbers rather than a guess.
# ==========================================================


import json
import os
import sys
import time
import warnings


warnings.filterwarnings("ignore")


REPO = r"<repo-root>"

DIAG = os.path.join(REPO, ".pytest_tmp", "diag07c")

MODEL = "large-v3-turbo"

ARCH_PROMPT = "سلام. پروژه معماری. پلان. طراحی. معماری. تصویر. رندر. پروژه من."

NEUTRAL_PROMPT = "این یک جمله فارسی کوتاه است."


TARGET = "سلام، پروژه من رو باز کردی؟"


def run(model, path, label, **kwargs):

    started = time.time()

    try:

        result = model.transcribe(path, **kwargs)

    except Exception as error:

        return {"variant": label,
                "error": type(error).__name__ + ": " + str(error)}

    segments = result.get("segments") or []

    text = (result.get("text") or "").strip()

    first = segments[0] if segments else {}

    # repetition measure across the whole transcript
    words = text.split()

    unique_ratio = (
        round(len(set(words)) / float(len(words)), 3) if words else None
    )

    return {
        "variant": label,
        "text": text,
        "language": result.get("language"),
        "avg_logprob": (round(first.get("avg_logprob"), 4)
                        if first.get("avg_logprob") is not None else None),
        "no_speech_prob": first.get("no_speech_prob"),
        "compression_ratio": (round(first.get("compression_ratio"), 3)
                              if first.get("compression_ratio") is not None
                              else None),
        "segments": len(segments),
        "words": len(words),
        "unique_word_ratio": unique_ratio,
        "seconds": round(time.time() - started, 2),
    }


def main():

    import whisper

    model = whisper.load_model(MODEL, device="cpu")

    print("loaded\n", flush=True)

    # Thresholds KEPT (Whisper defaults) so a repetition loop can be
    # detected by the decoder instead of being allowed to run on.
    SAFE = dict(
        fp16=False,
        task="transcribe",
        language="fa",
        verbose=False,
        condition_on_previous_text=False,
        temperature=0.0,
        beam_size=5,
    )

    SAFE_NO_BEAM = dict(
        fp16=False,
        task="transcribe",
        language="fa",
        verbose=False,
        condition_on_previous_text=False,
        temperature=0.0,
    )

    SAFE_FALLBACK = dict(
        fp16=False,
        task="transcribe",
        language="fa",
        verbose=False,
        condition_on_previous_text=False,
        temperature=(0.0, 0.2, 0.4),
        beam_size=5,
    )

    report = {"target": TARGET, "arch_prompt": ARCH_PROMPT,
              "neutral_prompt": NEUTRAL_PROMPT, "recordings": {}}

    for key in ("030", "275"):

        trim = os.path.join(DIAG, "%s_trim16k.wav" % key)

        print("=" * 76)
        print("  %s  (trimmed)" % key)
        print("=" * 76, flush=True)

        variants = [

            ("C1 safe: temp0 +beam5 +no-prev, NO prompt",
             dict(SAFE)),

            ("C2 safe: temp0 +beam5 +no-prev +ARCH prompt",
             dict(SAFE, initial_prompt=ARCH_PROMPT)),

            ("C3 safe: temp0 greedy +no-prev +ARCH prompt",
             dict(SAFE_NO_BEAM, initial_prompt=ARCH_PROMPT)),

            ("C4 safe: temp0 +beam5 +no-prev +NEUTRAL prompt",
             dict(SAFE, initial_prompt=NEUTRAL_PROMPT)),

            ("C5 safe: temp(0,.2,.4) +beam5 +no-prev +ARCH prompt",
             dict(SAFE_FALLBACK, initial_prompt=ARCH_PROMPT)),

            ("C6 safe: temp0 +beam5 +WITH-prev +ARCH prompt",
             dict(SAFE, condition_on_previous_text=True,
                  initial_prompt=ARCH_PROMPT)),
        ]

        results = []

        for label, options in variants:

            outcome = run(model, trim, label, **options)

            results.append(outcome)

            print("  %-52s" % label, flush=True)
            print("      %s" % outcome.get("text"), flush=True)
            print("      lang %s | avg %s | comp %s | uniq %s | %ss"
                  % (outcome.get("language"), outcome.get("avg_logprob"),
                     outcome.get("compression_ratio"),
                     outcome.get("unique_word_ratio"),
                     outcome.get("seconds")), flush=True)
            print(flush=True)

        report["recordings"][key] = results

    with open(os.path.join(DIAG, "round4_report.json"), "w",
              encoding="utf-8") as handle:

        json.dump(report, handle, ensure_ascii=False, indent=2)

    print("DONE -> .pytest_tmp/diag07c/round4_report.json")

    return 0


if __name__ == "__main__":

    sys.exit(main())
