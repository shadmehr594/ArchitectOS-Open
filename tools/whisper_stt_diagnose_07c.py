# ==========================================================
# VOICE_07C — PERSIAN STT DIAGNOSTIC (offline, read-only)
#
# Runs controlled comparisons on the SAME saved human recordings.
# Loads the Whisper model ONCE and reuses it for every variant.
#
# Usage: <system python 3.11> tools/whisper_stt_diagnose_07c.py <audio...>
# ==========================================================


import json
import os
import sys
import time
import warnings


warnings.filterwarnings("ignore")


MODEL = "large-v3-turbo"

PERSIAN_PROMPT = (
    "سلام. پروژه معماری. پلان. طراحی. معماری. تصویر. رندر. پروژه من."
)


def run(model, path, label, **kwargs):

    started = time.time()

    try:

        result = model.transcribe(path, **kwargs)

    except Exception as error:

        return {
            "variant": label,
            "error": type(error).__name__ + ": " + str(error),
        }

    segments = result.get("segments") or []

    avg = None
    no_speech = None

    if segments:

        avg = segments[0].get("avg_logprob")
        no_speech = segments[0].get("no_speech_prob")

    return {
        "variant": label,
        "text": (result.get("text") or "").strip(),
        "language": result.get("language"),
        "avg_logprob": round(avg, 4) if avg is not None else None,
        "no_speech_prob": (
            round(no_speech, 6) if no_speech is not None else None
        ),
        "segments": len(segments),
        "seconds": round(time.time() - started, 2),
    }


def main():

    paths = sys.argv[1:]

    if not paths:

        print("usage: diagnose <audio...>")

        return 1

    import whisper

    print("loading", MODEL, "…")

    load_started = time.time()

    model = whisper.load_model(MODEL, device="cpu")

    print("loaded in %.1fs\n" % (time.time() - load_started))

    for path in paths:

        if not os.path.isfile(path):

            print("MISSING:", path)

            continue

        print("=" * 74)
        print("  AUDIO:", path)
        print("=" * 74)

        variants = [

            # A — exactly as shipped today
            dict(label="A  shipped: fp16=False, task=transcribe, language=auto",
                 fp16=False, task="transcribe", language=None, verbose=False),

            # B — language forced
            dict(label="B  language=fa, task=transcribe",
                 fp16=False, task="transcribe", language="fa", verbose=False),

            # C — clean wav + auto  (same as A but on the decoded PCM)
            dict(label="C  clean16k, auto",
                 fp16=False, task="transcribe", language=None, verbose=False),

            # D — clean wav + fa
            dict(label="D  clean16k, language=fa",
                 fp16=False, task="transcribe", language="fa", verbose=False),

            # E — clean wav + fa + no previous-text conditioning
            dict(label="E  clean16k, fa, condition_on_previous_text=False",
                 fp16=False, task="transcribe", language="fa",
                 condition_on_previous_text=False, verbose=False),

            # F — clean wav + fa + bounded decoding + no previous text
            dict(label="F  clean16k, fa, no-prev, temperature=0, no fallback",
                 fp16=False, task="transcribe", language="fa",
                 condition_on_previous_text=False,
                 temperature=0.0,
                 compression_ratio_threshold=None,
                 logprob_threshold=None,
                 no_speech_threshold=None,
                 verbose=False),

            # G — clean wav + fa + bounded decoding + tiny domain prompt
            dict(label="G  clean16k, fa, no-prev, temp=0, initial_prompt",
                 fp16=False, task="transcribe", language="fa",
                 condition_on_previous_text=False,
                 temperature=0.0,
                 compression_ratio_threshold=None,
                 logprob_threshold=None,
                 no_speech_threshold=None,
                 initial_prompt=PERSIAN_PROMPT,
                 verbose=False),
        ]

        results = []

        for variant in variants:

            label = variant.pop("label")

            outcome = run(model, path, label, **variant)

            results.append(outcome)

            print("  %-58s" % label)

            print("      text : %s" % outcome.get("text"))

            print("      lang : %s | avg_logprob %s | no_speech %s | segs %s | %ss"
                  % (outcome.get("language"), outcome.get("avg_logprob"),
                     outcome.get("no_speech_prob"), outcome.get("segments"),
                     outcome.get("seconds")))

            print()

        print(json.dumps(results, ensure_ascii=False, indent=2))

        print()

    return 0


if __name__ == "__main__":

    sys.exit(main())
