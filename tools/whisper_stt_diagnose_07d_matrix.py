# ==========================================================
# VOICE_07D-2 / 07D-3 — SEGMENT + TOKEN AUDIT AND CONTROLLED MATRIX
#
# One variable at a time, no initial_prompt anywhere, no target
# vocabulary anywhere. Uses ONLY the two existing real recordings.
#
# 07D-2 captures, per run: segment start/end/seek, text,
#   avg_logprob, no_speech_prob, compression_ratio, temperature,
#   token IDs, decoded token text, and (word_timestamps=True)
#   per-word probabilities.
#
# 07D-3 experiments:
#   A  shipped trimmed baseline
#   B  + trailing silence 0.5 / 1.0 / 2.0 / 5.0 s  (no leading silence)
#   C  pre-roll 0.05 / 0.10 / 0.20 / 0.30 / 0.50 s
#   D  complete trailing audio vs tail trim
#   E  greedy / beam_size=5 / beam_size=10
#   F  non-lexical parameters only (patience, length_penalty,
#      suppress_tokens, without_timestamps, condition_on_previous_text)
# ==========================================================


import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave
import warnings


warnings.filterwarnings("ignore")


REPO = r"<repo-root>"

FFMPEG = r"C:\ffmpeg-8.1.2-essentials_build\bin\ffmpeg.exe"

OUT = os.path.join(REPO, ".pytest_tmp", "diag07d")

MODEL = "large-v3-turbo"

RATE = 16000

RECORDINGS = {
    "030": os.path.join(REPO, "data", "projects", "project_23e5dae6",
                        "documents", "voice_030_9e1635.webm"),
    "275": os.path.join(REPO, "data", "projects", "project_23e5dae6",
                        "documents", "voice_275_c9bc97.webm"),
}

PRE_ROLL_DEFAULT = 0.10
TAIL_KEEP_DEFAULT = 0.20


def decode_pcm(source, target):

    completed = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-i", source, "-ac", "1", "-ar", str(RATE),
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


def speech_bounds(data, rate):

    import numpy as np

    frame = max(1, int(rate * 0.010))
    count = data.size // frame

    rms = np.array([
        float(np.sqrt(np.mean(data[i * frame:(i + 1) * frame] ** 2)))
        for i in range(count)
    ])

    peak = float(np.max(np.abs(data))) or 1.0
    floor = float(np.percentile(rms, 10)) if count else 0.0
    threshold = max(floor * 4.0, peak * 0.02, 60.0)

    first = 0

    for i in range(count):

        if rms[i] > threshold:
            first = i
            break

    last = count - 1

    for i in range(count - 1, -1, -1):

        if rms[i] > threshold:
            last = i
            break

    return (first * frame, (last + 1) * frame, threshold)


def build_variant(decoded, target, pre_roll=PRE_ROLL_DEFAULT,
                  tail_keep=TAIL_KEEP_DEFAULT,
                  keep_full_tail=False, trailing_silence=0.0):

    """Build one working copy. Leading silence is only ever trimmed."""

    import numpy as np

    rate, data = read_wav(decoded)

    onset, offset, _ = speech_bounds(data, rate)

    start = max(0, onset - int(pre_roll * rate))

    end = data.size if keep_full_tail else min(
        data.size, offset + int(tail_keep * rate)
    )

    piece = data[start:end]

    if trailing_silence > 0:

        piece = np.concatenate([
            piece,
            np.zeros(int(trailing_silence * rate), dtype=np.float32),
        ])

    write_wav(target, rate, piece)

    return {
        "pre_roll": pre_roll,
        "keep_full_tail": keep_full_tail,
        "trailing_silence_added": trailing_silence,
        "start_seconds": round(start / float(rate), 3),
        "end_seconds": round(end / float(rate), 3),
        "duration": round(piece.size / float(rate), 3),
    }


def transcribe(model, path, **options):

    started = time.time()

    result = model.transcribe(path, **options)

    import whisper

    tokenizer = whisper.tokenizer.get_tokenizer(
        model.is_multilingual, language=result.get("language")
    )

    segments = []

    for segment in (result.get("segments") or []):

        tokens = segment.get("tokens") or []

        segments.append({
            "id": segment.get("id"),
            "seek": segment.get("seek"),
            "start": round(segment.get("start", 0.0), 3),
            "end": round(segment.get("end", 0.0), 3),
            "text": segment.get("text"),
            "temperature": segment.get("temperature"),
            "avg_logprob": (round(segment["avg_logprob"], 4)
                            if segment.get("avg_logprob") is not None
                            else None),
            "no_speech_prob": (round(segment["no_speech_prob"], 6)
                               if segment.get("no_speech_prob") is not None
                               else None),
            "compression_ratio": (round(segment["compression_ratio"], 3)
                                  if segment.get("compression_ratio")
                                  is not None else None),
            "token_ids": tokens,
            "token_text": "".join(tokenizer.decode([t]) for t in tokens),
            "words": [
                {
                    "word": w.get("word"),
                    "probability": (round(w["probability"], 4)
                                    if w.get("probability") is not None
                                    else None),
                }
                for w in (segment.get("words") or [])
            ],
        })

    text = (result.get("text") or "").strip()

    word_probs = [
        w["probability"] for s in segments for w in s["words"]
        if w["probability"] is not None
    ]

    return {
        "text": text,
        "language": result.get("language"),
        "segments": segments,
        "n_segments": len(segments),
        "mean_word_probability": (round(
            sum(word_probs) / len(word_probs), 4) if word_probs else None),
        "min_word_probability": (round(min(word_probs), 4)
                                 if word_probs else None),
        "seconds": round(time.time() - started, 2),
    }


def main():

    import whisper

    os.makedirs(OUT, exist_ok=True)

    model = whisper.load_model(MODEL, device="cpu")

    print("loaded\n", flush=True)

    BASE = dict(fp16=False, task="transcribe", language="fa",
                verbose=False, temperature=0.0,
                condition_on_previous_text=False,
                word_timestamps=True)

    report = {"recordings": {}}

    for key, source in RECORDINGS.items():

        print("=" * 76)
        print("  %s" % key)
        print("=" * 76, flush=True)

        workdir = tempfile.mkdtemp(prefix="07d_%s_" % key)

        decoded = os.path.join(workdir, "decoded16k.wav")

        assert decode_pcm(source, decoded), "decode failed"

        entry = {"source": source, "variants": []}

        # register BEFORE any variant so incremental writes include it
        report["recordings"][key] = entry

        def add(label, hypothesis, builder, **options):

            target = os.path.join(
                workdir, "v_%08d.wav" % (abs(hash(label)) % 10 ** 8)
            )

            info = builder(target)

            try:

                outcome = transcribe(model, target, **options)

            except Exception as error:

                # One bad parameter must not abort the whole matrix.
                outcome = {
                    "text": None,
                    "language": None,
                    "segments": [],
                    "n_segments": 0,
                    "mean_word_probability": None,
                    "min_word_probability": None,
                    "seconds": None,
                    "error": type(error).__name__ + ": " + str(error),
                }

            outcome["variant"] = label
            outcome["hypothesis"] = hypothesis
            outcome["audio"] = info

            entry["variants"].append(outcome)

            print("  %-44s %s" % (label, outcome["text"]), flush=True)
            print("      lang %s | mean_wp %s | min_wp %s | %ss"
                  % (outcome["language"], outcome["mean_word_probability"],
                     outcome["min_word_probability"], outcome["seconds"]),
                  flush=True)
            print(flush=True)

            # persist after EVERY variant so a later crash loses nothing
            with open(os.path.join(OUT, "controlled_matrix.json"), "w",
                      encoding="utf-8") as handle:

                json.dump(report, handle, ensure_ascii=False, indent=2)

            return outcome

        # ---------- A : shipped baseline ----------
        add("A  baseline (shipped trim)", "reference",
            lambda t: build_variant(decoded, t), **BASE)

        # ---------- B : trailing silence ----------
        for seconds in (0.5, 1.0, 2.0, 5.0):

            add("B  +%.1fs trailing silence" % seconds,
                "does a very short utterance hurt decoding?",
                (lambda s: lambda t: build_variant(
                    decoded, t, trailing_silence=s))(seconds),
                **BASE)

        # ---------- C : pre-roll ----------
        for pre in (0.05, 0.20, 0.30, 0.50):

            add("C  pre-roll %.2fs" % pre,
                "is consonant onset / context being lost?",
                (lambda p: lambda t: build_variant(
                    decoded, t, pre_roll=p))(pre),
                **BASE)

        # ---------- D : complete trailing audio ----------
        add("D  keep full trailing audio",
            "does the tail trim remove useful context?",
            lambda t: build_variant(decoded, t, keep_full_tail=True),
            **BASE)

        # ---------- E : beam width ----------
        add("E  beam_size=5", "search width",
            lambda t: build_variant(decoded, t), **dict(BASE, beam_size=5))

        add("E  beam_size=10", "search width",
            lambda t: build_variant(decoded, t), **dict(BASE, beam_size=10))

        # ---------- F : non-lexical parameters ----------
        add("F  patience=1.0 (beam5)", "beam patience",
            lambda t: build_variant(decoded, t),
            **dict(BASE, beam_size=5, patience=1.0))

        add("F  length_penalty=0.5", "length bias (valid range 0..1)",
            lambda t: build_variant(decoded, t),
            **dict(BASE, length_penalty=0.5))

        add("F  length_penalty=1.0", "length bias (valid range 0..1)",
            lambda t: build_variant(decoded, t),
            **dict(BASE, length_penalty=1.0))

        add("F  suppress_tokens='' (no non-speech suppression)",
            "non-speech token suppression",
            lambda t: build_variant(decoded, t),
            **dict(BASE, suppress_tokens=""))

        add("F  without_timestamps=True", "timestamp token cost",
            lambda t: build_variant(decoded, t),
            **dict(BASE, without_timestamps=True))

        add("F  condition_on_previous_text=True",
            "previous-window conditioning",
            lambda t: build_variant(decoded, t),
            **dict(BASE, condition_on_previous_text=True))

        report["recordings"][key] = entry

        with open(os.path.join(OUT, "controlled_matrix.json"), "w",
                  encoding="utf-8") as handle:

            json.dump(report, handle, ensure_ascii=False, indent=2)

        shutil.rmtree(workdir, ignore_errors=True)

    print("DONE -> .pytest_tmp/diag07d/controlled_matrix.json")

    return 0


if __name__ == "__main__":

    sys.exit(main())
