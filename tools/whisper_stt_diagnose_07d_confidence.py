# ==========================================================
# VOICE_07D-6 — QUALITY / CONFIDENCE INVESTIGATION
#
# Question: can a NON-CONTENT-HARDCODED reliability signal be
# derived from the model itself?
#
# Two candidate signals are measured:
#   1. per-word probability (word_timestamps=True)
#   2. disagreement across legitimate non-biased decodes
#
# A KNOWN-GOOD positive control is included so a threshold can be
# calibrated against real reliable output instead of a guess:
# English clips that the VOICE_07 acceptance already transcribed
# correctly.
#
# No target vocabulary is used anywhere.
# ==========================================================


import json
import os
import subprocess
import sys
import tempfile
import wave
import warnings


warnings.filterwarnings("ignore")


REPO = r"<repo-root>"

OUT = os.path.join(REPO, ".pytest_tmp", "diag07d")

FFMPEG = r"C:\ffmpeg-8.1.2-essentials_build\bin\ffmpeg.exe"

MODEL = "large-v3-turbo"

PERSIAN = {
    "030": os.path.join(REPO, "data", "projects", "project_23e5dae6",
                        "documents", "voice_030_9e1635.webm"),
    "275": os.path.join(REPO, "data", "projects", "project_23e5dae6",
                        "documents", "voice_275_c9bc97.webm"),
}

# Positive controls: real English speech, already verified correct by
# the VOICE_07 acceptance.
ENGLISH_DIR = os.path.join(REPO, ".pytest_tmp", "voice")


def decode_pcm(source, target):

    completed = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-i", source, "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", target],
        capture_output=True, text=True,
    )

    return completed.returncode == 0


def read_wav(path):

    import numpy as np

    with wave.open(path, "rb") as handle:

        channels = handle.getnchannels()
        rate = handle.getframerate()
        raw = handle.readframes(handle.getnframes())

    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)

    if channels > 1:

        data = data.reshape(-1, channels).mean(axis=1)

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


def trim_leading(decoded, target, pre_roll=0.10):

    import numpy as np

    rate, data = read_wav(decoded)

    frame = max(1, int(rate * 0.010))
    count = data.size // frame

    rms = np.array([
        float(np.sqrt(np.mean(data[i * frame:(i + 1) * frame] ** 2)))
        for i in range(count)
    ])

    peak = float(np.max(np.abs(data))) or 1.0
    threshold = max(float(np.percentile(rms, 10)) * 4.0, peak * 0.02, 60.0)

    onset = 0

    for i in range(count):

        if rms[i] > threshold:
            onset = i * frame
            break

    start = max(0, onset - int(pre_roll * rate))

    write_wav(target, rate, data[start:])

    return target


def measure(model, path, language):

    result = model.transcribe(
        path,
        fp16=False,
        task="transcribe",
        language=(None if language == "auto" else language),
        verbose=False,
        temperature=0.0,
        condition_on_previous_text=False,
        word_timestamps=True,
    )

    segments = result.get("segments") or []

    probs = [
        w["probability"]
        for s in segments for w in (s.get("words") or [])
        if w.get("probability") is not None
    ]

    return {
        "text": (result.get("text") or "").strip(),
        "language": result.get("language"),
        "mean_word_probability": (round(sum(probs) / len(probs), 4)
                                  if probs else None),
        "min_word_probability": (round(min(probs), 4) if probs else None),
        "n_words": len(probs),
        "word_probabilities": [round(p, 4) for p in probs],
        "avg_logprob": (round(segments[0]["avg_logprob"], 4)
                        if segments else None),
    }


def main():

    import whisper

    os.makedirs(OUT, exist_ok=True)

    model = whisper.load_model(MODEL, device="cpu")

    print("loaded\n", flush=True)

    report = {"persian": {}, "english_controls": {}}

    workdir = tempfile.mkdtemp(prefix="07d_conf_")

    try:

        for key, source in PERSIAN.items():

            decoded = os.path.join(workdir, "%s_16k.wav" % key)
            working = os.path.join(workdir, "%s_trim.wav" % key)

            decode_pcm(source, decoded)
            trim_leading(decoded, working)

            # --- signal 1: per-word probability ---
            measurement = measure(model, working, "fa")

            # --- signal 2: disagreement across non-biased decodes ---
            variants = {}

            for label, options in (
                ("greedy", {}),
                ("beam5", {"beam_size": 5}),
                ("beam5_tail1s", {"beam_size": 5}),
            ):

                if label == "beam5_tail1s":

                    rate, data = read_wav(working)

                    import numpy as np

                    padded = os.path.join(
                        workdir, "%s_tail1s.wav" % key
                    )

                    write_wav(
                        padded, rate,
                        np.concatenate([
                            data,
                            np.zeros(rate, dtype=np.float32),
                        ]),
                    )

                    target = padded

                else:

                    target = working

                outcome = model.transcribe(
                    target,
                    fp16=False, task="transcribe", language="fa",
                    verbose=False, temperature=0.0,
                    condition_on_previous_text=False,
                    **options,
                )

                variants[label] = (outcome.get("text") or "").strip()

            distinct = sorted(set(variants.values()))

            agreement = (
                round(
                    max(
                        sum(1 for v in variants.values() if v == t)
                        for t in distinct
                    ) / float(len(variants)),
                    3,
                )
                if variants else None
            )

            report["persian"][key] = {
                "measurement": measurement,
                "variants": variants,
                "distinct_transcripts": len(distinct),
                "agreement_rate": agreement,
            }

            print("%s  mean_wp=%s min_wp=%s | distinct=%d agreement=%s"
                  % (key, measurement["mean_word_probability"],
                     measurement["min_word_probability"],
                     len(distinct), agreement), flush=True)
            print("     %s" % measurement["text"], flush=True)
            print(flush=True)

        # ---- positive control: known-good English ----
        if os.path.isdir(ENGLISH_DIR):

            for name in sorted(os.listdir(ENGLISH_DIR)):

                if not name.endswith(".wav"):
                    continue

                source = os.path.join(ENGLISH_DIR, name)

                decoded = os.path.join(workdir, "en_%s" % name)

                if not decode_pcm(source, decoded):
                    continue

                measurement = measure(model, decoded, "en")

                report["english_controls"][name] = measurement

                print("EN %-16s mean_wp=%s min_wp=%s | %s"
                      % (name, measurement["mean_word_probability"],
                         measurement["min_word_probability"],
                         measurement["text"]), flush=True)

    finally:

        import shutil

        shutil.rmtree(workdir, ignore_errors=True)

    with open(os.path.join(OUT, "confidence.json"), "w",
              encoding="utf-8") as handle:

        json.dump(report, handle, ensure_ascii=False, indent=2)

    print("\nreport -> .pytest_tmp/diag07d/confidence.json")

    return 0


if __name__ == "__main__":

    sys.exit(main())
