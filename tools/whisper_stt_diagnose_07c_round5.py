# ==========================================================
# VOICE_07C — ROUND 5 : PROMPT / DECODING ROBUSTNESS SEARCH
#
# Round 4 finding:
#   * the brief's ARCH prompt starts with "سلام." and the audio
#     starts with "سلام" -> the model ECHOES the prompt and loops
#     (compression_ratio 11.4, unique-word-ratio 0.06).
#   * with no prompt there is no loop but the tail is mis-heard.
#
# Round 5 therefore tests prompts that do NOT begin with the same
# word as the utterance, normalisation, beam width, temperature
# fallback, leading-only trimming, and per-burst transcription.
#
# Nothing here hardcodes the target sentence.
# ==========================================================


import json
import os
import subprocess
import sys
import time
import wave
import warnings


warnings.filterwarnings("ignore")


REPO = r"<repo-root>"

DIAG = os.path.join(REPO, ".pytest_tmp", "diag07c")

FFMPEG = r"C:\ffmpeg-8.1.2-essentials_build\bin\ffmpeg.exe"

MODEL = "large-v3-turbo"


PROMPTS = {
    # the brief's sanctioned prompt
    "ARCH": "سلام. پروژه معماری. پلان. طراحی. معماری. تصویر. رندر. پروژه من.",

    # domain vocabulary WITHOUT the utterance's opening word
    "ARCH2": "پروژه معماری. پلان. طراحی. تصویر. رندر. ساختمان. اتاق. نما.",

    # fully generic Persian (no domain, no target words)
    "GENERIC": "این یک جمله کوتاه فارسی برای آزمایش است.",

    # deliberately NOT used in the recommended fix — kept only to
    # show what a target-containing prompt would do
    "CONV": "سلام. پروژه من. باز کردی؟ بله. ممنون.",
}


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


def normalise(source, target, target_peak=0.89):

    import numpy as np

    rate, data = read_wav(source)

    peak = float(np.max(np.abs(data))) or 1.0

    write_wav(target, rate, data * (target_peak * 32768.0 / peak))

    return target


def leading_only_trim(source, target, pre_roll=0.10):

    import numpy as np

    rate, data = read_wav(source)

    frame = max(1, int(rate * 0.010))
    n = data.size // frame

    rms = np.array([
        float(np.sqrt(np.mean(data[i * frame:(i + 1) * frame] ** 2)))
        for i in range(n)
    ])

    peak = float(np.max(np.abs(data))) or 1.0
    thr = max(float(np.percentile(rms, 10)) * 4.0, peak * 0.02, 60.0)

    start = 0

    for i in range(n):

        if rms[i] > thr:
            start = i
            break

    begin = max(0, start * frame - int(pre_roll * rate))

    write_wav(target, rate, data[begin:])

    return target


def bursts(source, gap=0.25, min_len=0.25):

    """Return [(start_s, end_s)] speech bursts separated by >= gap."""

    import numpy as np

    rate, data = read_wav(source)

    frame = max(1, int(rate * 0.010))
    n = data.size // frame

    rms = np.array([
        float(np.sqrt(np.mean(data[i * frame:(i + 1) * frame] ** 2)))
        for i in range(n)
    ])

    peak = float(np.max(np.abs(data))) or 1.0
    thr = max(float(np.percentile(rms, 10)) * 4.0, peak * 0.02, 60.0)

    active = rms > thr

    spans = []
    i = 0

    while i < n:

        if not active[i]:
            i += 1
            continue

        j = i

        while j < n and active[j]:
            j += 1

        spans.append((i * frame / rate, j * frame / rate))
        i = j

    # merge spans separated by < gap
    merged = []

    for span in spans:

        if merged and span[0] - merged[-1][1] < gap:
            merged[-1] = (merged[-1][0], span[1])
        else:
            merged.append(list(span))

    merged = [(round(a, 3), round(b, 3)) for a, b in merged
              if b - a >= min_len]

    return rate, data, merged


def slice_wav(rate, data, start, end, target, pad=0.10):

    import numpy as np

    a = max(0, int((start - pad) * rate))
    b = min(data.size, int((end + pad) * rate))

    write_wav(target, rate, data[a:b])

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

    report = {"prompts": PROMPTS, "recordings": {}}

    for key in ("030", "275"):

        trim = os.path.join(DIAG, "%s_trim16k.wav" % key)
        lead = os.path.join(DIAG, "%s_leadonly16k.wav" % key)
        norm = os.path.join(DIAG, "%s_trim_norm16k.wav" % key)

        leading_only_trim(trim, lead)
        normalise(trim, norm)

        print("=" * 76)
        print("  %s" % key)
        print("=" * 76, flush=True)

        base = dict(fp16=False, task="transcribe", language="fa",
                    verbose=False, condition_on_previous_text=False,
                    temperature=0.0)

        variants = [

            ("D1  trim, beam5, temp0, NO prompt",
             trim, dict(base, beam_size=5)),

            ("D2  trim, beam5, temp0, ARCH2 prompt (no 'سلام')",
             trim, dict(base, beam_size=5,
                        initial_prompt=PROMPTS["ARCH2"])),

            ("D3  trim, beam5, temp0, GENERIC prompt",
             trim, dict(base, beam_size=5,
                        initial_prompt=PROMPTS["GENERIC"])),

            ("D4  trim, beam10, temp0, NO prompt",
             trim, dict(base, beam_size=10)),

            ("D5  trim+normalised, beam5, temp0, NO prompt",
             norm, dict(base, beam_size=5)),

            ("D6  trim+normalised, beam5, temp0, ARCH2 prompt",
             norm, dict(base, beam_size=5,
                        initial_prompt=PROMPTS["ARCH2"])),

            ("D7  LEADING-ONLY trim, beam5, temp0, ARCH2 prompt",
             lead, dict(base, beam_size=5,
                        initial_prompt=PROMPTS["ARCH2"])),

            ("D8  trim, beam5, temp(0,.2,.4,.6), NO prompt",
             trim, dict(base, beam_size=5,
                        temperature=(0.0, 0.2, 0.4, 0.6))),
        ]

        results = []

        for label, target, options in variants:

            outcome = run(model, target, label, **options)
            results.append(outcome)

            print("  %-50s" % label, flush=True)
            print("      %s" % outcome.get("text"), flush=True)
            print("      lang %s | avg %s | comp %s | uniq %s | %ss"
                  % (outcome.get("language"), outcome.get("avg_logprob"),
                     outcome.get("compression_ratio"),
                     outcome.get("unique_word_ratio"),
                     outcome.get("seconds")), flush=True)
            print(flush=True)

        # ---- per-burst transcription ---------------------------
        rate, data, spans = bursts(trim)

        print("  bursts: %s" % spans, flush=True)

        burst_results = []

        for index, (a, b) in enumerate(spans):

            piece = os.path.join(DIAG, "%s_burst%d.wav" % (key, index + 1))

            slice_wav(rate, data, a, b, piece)

            outcome = run(
                model, piece,
                "D9  burst %d  [%.2f-%.2f s]" % (index + 1, a, b),
                **dict(base, beam_size=5,
                       initial_prompt=PROMPTS["ARCH2"])
            )

            burst_results.append(outcome)

            print("      %s -> %s" % (outcome.get("variant"),
                                      outcome.get("text")), flush=True)

        print(flush=True)

        report["recordings"][key] = {
            "variants": results,
            "bursts": spans,
            "burst_results": burst_results,
        }

        with open(os.path.join(DIAG, "round5_report.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)

    print("DONE -> .pytest_tmp/diag07c/round5_report.json")

    return 0


if __name__ == "__main__":

    sys.exit(main())
