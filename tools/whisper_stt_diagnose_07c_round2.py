# ==========================================================
# VOICE_07C — PERSIAN STT DIAGNOSTIC ROUND 2
#
# Round 1 established:
#   - decoding is NOT the problem (clean PCM == original)
#   - language=auto -> confident WRONG language
#   - default settings -> repetition / hallucination
#   - temperature=0 + no previous-text conditioning stops it
#
# Round 2 tests beam search, silence trimming and bounded prompts.
# ==========================================================


import json
import os
import sys
import time
import warnings


warnings.filterwarnings("ignore")


MODEL = "large-v3-turbo"

ARCH_PROMPT = (
    "سلام. پروژه معماری. پلان. طراحی. معماری. تصویر. رندر. پروژه من."
)

CONVERSATIONAL_PROMPT = (
    "سلام. پروژه من. باز کردی؟ بله. ممنون."
)


def main():

    paths = sys.argv[1:]

    import whisper

    print("loading", MODEL, "…", flush=True)

    model = whisper.load_model(MODEL, device="cpu")

    print("loaded\n", flush=True)

    for path in paths:

        if not os.path.isfile(path):

            print("MISSING:", path)

            continue

        print("=" * 74)
        print("  AUDIO:", path)
        print("=" * 74, flush=True)

        base = dict(
            fp16=False,
            task="transcribe",
            language="fa",
            verbose=False,
            condition_on_previous_text=False,
            temperature=0.0,
            compression_ratio_threshold=None,
            logprob_threshold=None,
            no_speech_threshold=None,
        )

        variants = [

            ("F  bounded, greedy (round-1 winner)",
             dict(base)),

            ("H  bounded + beam_size=5",
             dict(base, beam_size=5)),

            ("I  bounded + beam_size=5 + patience=1.0",
             dict(base, beam_size=5, patience=1.0)),

            ("J  bounded + beam5 + arch initial_prompt",
             dict(base, beam_size=5, initial_prompt=ARCH_PROMPT)),

            ("K  bounded + beam5 + conversational prompt",
             dict(base, beam_size=5,
                  initial_prompt=CONVERSATIONAL_PROMPT)),

            ("L  bounded + beam5 + no prompt (repeat check)",
             dict(base, beam_size=5)),
        ]

        for label, options in variants:

            started = time.time()

            try:

                result = model.transcribe(path, **options)

                text = (result.get("text") or "").strip()

                segments = result.get("segments") or []

                avg = segments[0].get("avg_logprob") if segments else None

                print("  %s" % label, flush=True)

                print("      text : %s" % text, flush=True)

                print("      lang : %s | avg_logprob %s | segs %s | %.1fs"
                      % (result.get("language"),
                         round(avg, 4) if avg is not None else None,
                         len(segments), time.time() - started), flush=True)

                print(flush=True)

            except Exception as error:

                print("  %s -> ERROR %s: %s"
                      % (label, type(error).__name__, error), flush=True)

    return 0


if __name__ == "__main__":

    sys.exit(main())
