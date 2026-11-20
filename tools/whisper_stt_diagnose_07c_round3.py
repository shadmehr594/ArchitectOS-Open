# ==========================================================
# VOICE_07C — ROUND 3 : DEFINITIVE OFFLINE COMPARISON
#
# Consolidates rounds 1 & 2 into ONE authoritative matrix and
# adds the missing comparisons (030 original A-G, 030 clean16k,
# and trim-vs-no-trim isolation for both recordings).
#
# Loads the model ONCE. Read-only w.r.t. the source recordings:
# every derived file is written under .pytest_tmp/diag07c/.
#
# Run with the SYSTEM python 3.11 (whisper + torch + numpy).
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

ARCH_PROMPT = "سلام. پروژه معماری. پلان. طراحی. معماری. تصویر. رندر. پروژه من."

CONV_PROMPT = "سلام. پروژه من. باز کردی؟ بله. ممنون."


RECORDINGS = {
    "030": os.path.join(
        REPO, "data", "projects", "project_23e5dae6", "documents",
        "voice_030_9e1635.webm",
    ),
    "275": os.path.join(
        REPO, "data", "projects", "project_23e5dae6", "documents",
        "voice_275_c9bc97.webm",
    ),
}


# ----------------------------------------------------------
# AUDIO HELPERS
# ----------------------------------------------------------

def decode(path, target, rate=16000, channels=1):

    completed = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-i", path, "-ac", str(channels), "-ar", str(rate),
         "-c:a", "pcm_s16le", target],
        capture_output=True, text=True,
    )

    return completed.returncode == 0


def read_wav(path):

    import numpy as np

    with wave.open(path, "rb") as handle:

        channels = handle.getnchannels()
        rate = handle.getframerate()
        frames = handle.getnframes()
        raw = handle.readframes(frames)

    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)

    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)

    return rate, data


def write_wav(path, rate, samples):

    import numpy as np

    clipped = np.clip(samples, -32768, 32767).astype(np.int16)

    with wave.open(path, "wb") as handle:

        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(clipped.tobytes())


def analyse_silence(path):
    """Frame-RMS silence analysis. Returns speech_start (s) etc."""

    import numpy as np

    rate, data = read_wav(path)

    frame = max(1, int(rate * 0.010))

    n = data.size // frame

    rms = np.array([
        float(np.sqrt(np.mean(data[i * frame:(i + 1) * frame] ** 2)))
        for i in range(n)
    ])

    peak = float(np.max(np.abs(data))) if data.size else 0.0

    floor = float(np.percentile(rms, 10)) if n else 0.0

    # Conservative speech threshold: clearly above the noise floor and
    # above an absolute floor, so a breath is not mistaken for speech.
    threshold = max(floor * 4.0, peak * 0.02, 60.0)

    speech_frame = None

    for i in range(n):

        if rms[i] > threshold:

            speech_frame = i
            break

    speech_start = (
        round(speech_frame * frame / rate, 3)
        if speech_frame is not None else None
    )

    return {
        "rate": rate,
        "duration": round(data.size / float(rate), 3),
        "peak": peak,
        "noise_floor_rms": round(floor, 2),
        "threshold": round(threshold, 2),
        "speech_start": speech_start,
        "leading_silence": speech_start,
        "frames": n,
    }


def trim_leading(path, target, pre_roll=0.10, tail_keep=0.20):
    """Remove ONLY leading silence, preserving the whole spoken part.

    A pre-roll of `pre_roll` seconds is kept BEFORE the detected onset so
    the first phoneme is never clipped. Trailing audio is kept entirely
    except for a bounded tail of pure silence.
    """

    import numpy as np

    rate, data = read_wav(path)

    frame = max(1, int(rate * 0.010))
    n = data.size // frame

    rms = np.array([
        float(np.sqrt(np.mean(data[i * frame:(i + 1) * frame] ** 2)))
        for i in range(n)
    ])

    peak = float(np.max(np.abs(data))) if data.size else 0.0
    floor = float(np.percentile(rms, 10)) if n else 0.0
    threshold = max(floor * 4.0, peak * 0.02, 60.0)

    start_frame = 0

    for i in range(n):

        if rms[i] > threshold:

            start_frame = i
            break

    # last speech frame
    end_frame = n - 1

    for i in range(n - 1, -1, -1):

        if rms[i] > threshold:

            end_frame = i
            break

    onset = start_frame * frame
    offset = min(data.size, (end_frame + 1) * frame)

    start = max(0, onset - int(pre_roll * rate))
    end = min(data.size, offset + int(tail_keep * rate))

    trimmed = data[start:end]

    write_wav(target, rate, trimmed)

    # first-phoneme preservation check: the energy at the detected onset
    # must be present in the trimmed signal at the same relative offset.
    preserved = None

    if onset - start < trimmed.size:

        window = trimmed[onset - start: onset - start + frame]

        preserved = bool(
            np.sqrt(np.mean(window ** 2)) > threshold * 0.5
        ) if window.size else False

    return {
        "source_duration": round(data.size / float(rate), 3),
        "leading_silence_removed": round(start / float(rate), 3),
        "trailing_silence_removed": round(
            (data.size - end) / float(rate), 3
        ),
        "trimmed_duration": round(trimmed.size / float(rate), 3),
        "first_speech_timestamp": round(onset / float(rate), 3),
        "pre_roll_seconds": pre_roll,
        "first_phoneme_preserved": preserved,
    }


# ----------------------------------------------------------
# WHISPER
# ----------------------------------------------------------

BOUNDED = dict(
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

    avg = segments[0].get("avg_logprob") if segments else None
    ns = segments[0].get("no_speech_prob") if segments else None

    return {
        "variant": label,
        "text": (result.get("text") or "").strip(),
        "language": result.get("language"),
        "avg_logprob": round(avg, 4) if avg is not None else None,
        "no_speech_prob": round(ns, 6) if ns is not None else None,
        "segments": len(segments),
        "seconds": round(time.time() - started, 2),
    }


def main():

    import whisper

    os.makedirs(DIAG, exist_ok=True)

    print("loading", MODEL, "...", flush=True)

    model = whisper.load_model(MODEL, device="cpu")

    print("loaded\n", flush=True)

    report = {"model": MODEL, "recordings": {}}

    for key, source in RECORDINGS.items():

        print("=" * 76)
        print("  RECORDING", key, "->", os.path.basename(source))
        print("=" * 76, flush=True)

        entry = {"source": source}

        clean = os.path.join(DIAG, "%s_clean16k.wav" % key)
        trim = os.path.join(DIAG, "%s_trim16k.wav" % key)

        assert decode(source, clean), "decode failed"
        assert decode(source, trim), "decode failed (trim source)"

        entry["clean_silence"] = analyse_silence(clean)
        entry["trim_ops"] = trim_leading(clean, trim)

        entry["clean_silence_after_trim"] = analyse_silence(trim)

        variants = [

            # --- the required A-G matrix -----------------------------
            ("A  SHIPPED original, auto, defaults",
             dict(fp16=False, task="transcribe", language=None,
                  verbose=False)),
            ("B  original, language=fa, defaults",
             dict(fp16=False, task="transcribe", language="fa",
                  verbose=False)),
            ("C  clean16k, auto, defaults",
             dict(fp16=False, task="transcribe", language=None,
                  verbose=False)),
            ("D  clean16k, language=fa, defaults",
             dict(fp16=False, task="transcribe", language="fa",
                  verbose=False)),
            ("E  clean16k, fa, defaults + bounded arch initial_prompt",
             dict(fp16=False, task="transcribe", language="fa",
                  verbose=False, initial_prompt=ARCH_PROMPT)),
        ]

        # per-path run
        for label, options in variants:

            if label.startswith("A") or label.startswith("B"):
                target = source
            else:
                target = clean

            outcome = run(model, target, label, **options)
            entry.setdefault("matrix", []).append(outcome)
            print("  %-56s" % label, flush=True)
            print("      %s" % outcome.get("text"), flush=True)
            print("      lang %s | avg %s | %.1fs"
                  % (outcome.get("language"), outcome.get("avg_logprob"),
                     outcome.get("seconds")), flush=True)
            print(flush=True)

        # --- F/G : leading-silence removal -----------------------
        trim_variants = [

            ("F  TRIM16k, fa, defaults",
             dict(fp16=False, task="transcribe", language="fa",
                  verbose=False)),

            ("G  TRIM16k, fa, bounded greedy (temp=0,no-prev)",
             dict(BOUNDED)),

            ("G2 TRIM16k, fa, bounded + beam5",
             dict(BOUNDED, beam_size=5)),

            ("G3 TRIM16k, fa, bounded + beam5 + ARCH prompt",
             dict(BOUNDED, beam_size=5, initial_prompt=ARCH_PROMPT)),

            ("G4 TRIM16k, fa, bounded + beam5 + CONV prompt",
             dict(BOUNDED, beam_size=5, initial_prompt=CONV_PROMPT)),
        ]

        entry["trim_matrix"] = []

        for label, options in trim_variants:

            outcome = run(model, trim, label, **options)
            entry["trim_matrix"].append(outcome)
            print("  %-56s" % label, flush=True)
            print("      %s" % outcome.get("text"), flush=True)
            print("      lang %s | avg %s | %.1fs"
                  % (outcome.get("language"), outcome.get("avg_logprob"),
                     outcome.get("seconds")), flush=True)
            print(flush=True)

        # --- isolation: does the trim matter with the SAME decoder?
        entry["isolation"] = []

        for label, target in (
            ("X  UNTRIMMED clean16k, fa, bounded+beam5+CONV",
             clean),
            ("Y  TRIMMED   clean16k, fa, bounded+beam5+CONV",
             trim),
        ):

            outcome = run(
                model, target, label,
                **dict(BOUNDED, beam_size=5, initial_prompt=CONV_PROMPT)
            )
            entry["isolation"].append(outcome)
            print("  %-56s" % label, flush=True)
            print("      %s" % outcome.get("text"), flush=True)
            print(flush=True)

        report["recordings"][key] = entry

        with open(os.path.join(DIAG, "round3_report.json"), "w",
                  encoding="utf-8") as handle:

            json.dump(report, handle, ensure_ascii=False, indent=2)

    print("\n" + "=" * 76)
    print("DONE — report at .pytest_tmp/diag07c/round3_report.json")
    print("=" * 76)

    return 0


if __name__ == "__main__":

    sys.exit(main())
