# ==========================================================
# VOICE_07D-1 — VERIFY THE EXACT AUDIO FED TO WHISPER
#
# Reproduces the worker's STT working copy for both real
# recordings and proves numerically that preprocessing changes
# NOTHING except: resampling, channel conversion and the
# intentional trim. The original file is never modified.
#
# Read-only w.r.t. the source recordings.
# ==========================================================


import hashlib
import json
import os
import shutil
import sys
import tempfile
import wave


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, REPO)

sys.path.insert(0, os.path.join(REPO, "tools"))


import numpy as np


import whisper_stt_worker as W


RECORDINGS = {
    "030": os.path.join(REPO, "data", "projects", "project_23e5dae6",
                        "documents", "voice_030_9e1635.webm"),
    "275": os.path.join(REPO, "data", "projects", "project_23e5dae6",
                        "documents", "voice_275_c9bc97.webm"),
}

OUT = os.path.join(REPO, ".pytest_tmp", "diag07d")


def sha256(path):

    digest = hashlib.sha256()

    with open(path, "rb") as handle:

        for block in iter(lambda: handle.read(65536), b""):

            digest.update(block)

    return digest.hexdigest()


def read_wav(path):

    with wave.open(path, "rb") as handle:

        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.getnframes()
        raw = handle.readframes(frames)

    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)

    if channels > 1:

        data = data.reshape(-1, channels).mean(axis=1)

    return {"rate": rate, "channels": channels, "width": width,
            "frames": frames, "data": data,
            "duration": round(frames / float(rate), 6)}


def rms(samples):

    if samples.size == 0:

        return 0.0

    return float(np.sqrt(np.mean(samples ** 2)))


def main():

    os.makedirs(OUT, exist_ok=True)

    report = {"recordings": {}}

    for key, source in RECORDINGS.items():

        print("=" * 74)
        print("  %s  ->  %s" % (key, os.path.basename(source)))
        print("=" * 74, flush=True)

        before = sha256(source)

        entry = {"source": source, "source_sha256_before": before}

        workdir = tempfile.mkdtemp(prefix="07d_audio_")

        try:

            # The exact function the worker uses.
            working, meta, _ = W.prepare_working_copy(source, {}, workdir)

            entry["preprocessing_meta"] = meta

            # Full decode of the source (what Whisper would see untrimmed)
            decoded = os.path.join(workdir, "decoded16k.wav")

            ok, message = W._decode_pcm(source, decoded)

            entry["decode_ok"] = ok
            entry["decode_message"] = message

            src = read_wav(decoded)
            work = read_wav(working)

            entry["decoded16k"] = {
                "rate": src["rate"], "channels": src["channels"],
                "width_bytes": src["width"], "frames": src["frames"],
                "duration": src["duration"],
            }

            entry["working"] = {
                "rate": work["rate"], "channels": work["channels"],
                "width_bytes": work["width"], "frames": work["frames"],
                "duration": work["duration"],
            }

            # ---- is the working copy an EXACT slice of the decode? ----
            head = int(round((meta.get("trimmed_seconds") or 0) * src["rate"]))

            slice_ = src["data"][head:head + work["data"].size]

            exact = (slice_.size == work["data"].size
                     and bool(np.array_equal(slice_, work["data"])))

            entry["is_exact_slice_of_decode"] = exact
            entry["head_samples_removed"] = head
            entry["tail_samples_removed"] = int(
                src["data"].size - head - work["data"].size
            )

            entry["start_seconds"] = round(head / float(src["rate"]), 6)
            entry["end_seconds"] = round(
                (head + work["data"].size) / float(src["rate"]), 6
            )

            # ---- speech-region comparison (original vs working) ----
            onset = meta.get("first_speech_timestamp") or 0.0
            onset_sample = int(round(onset * src["rate"]))

            pre_roll = W.PRE_ROLL_SECONDS
            first_phoneme_window = int(0.05 * src["rate"])

            # 50 ms immediately AFTER the detected onset, in both signals
            src_onset = src["data"][
                onset_sample: onset_sample + first_phoneme_window
            ]
            work_onset_index = onset_sample - head
            work_onset = work["data"][
                work_onset_index: work_onset_index + first_phoneme_window
            ]

            entry["first_phoneme"] = {
                "pre_roll_seconds": pre_roll,
                "onset_seconds": onset,
                "onset_retained_in_working": bool(work_onset_index >= 0),
                "samples_before_onset_kept": int(
                    min(pre_roll * src["rate"], head)
                ),
                "original_onset_rms": round(rms(src_onset), 2),
                "working_onset_rms": round(rms(work_onset), 2),
                "onset_identical": bool(
                    src_onset.size == work_onset.size
                    and np.array_equal(src_onset, work_onset)
                ),
            }

            # tail: how much real audio after the last speech frame was cut
            entry["tail"] = {
                "tail_keep_seconds": W.TAIL_KEEP_SECONDS,
                "trailing_silence_removed": meta.get(
                    "trailing_silence_removed"
                ),
                "working_end_seconds": round(
                    work["data"].size / float(work["rate"]), 6
                ),
                "decoded_end_seconds": src["duration"],
            }

            # ---- overall numeric agreement on the shared region ----
            shared = min(slice_.size, work["data"].size)

            if shared:

                a = slice_[:shared]
                b = work["data"][:shared]

                diff = np.abs(a - b)

                entry["numeric_comparison"] = {
                    "shared_samples": int(shared),
                    "max_abs_difference": float(diff.max()),
                    "mean_abs_difference": round(float(diff.mean()), 6),
                    "identical": bool(np.array_equal(a, b)),
                    "original_speech_rms": round(rms(a), 2),
                    "working_speech_rms": round(rms(b), 2),
                }

            after = sha256(source)

            entry["source_sha256_after"] = after
            entry["source_unchanged"] = before == after

            # diagnostic copies kept for inspection
            shutil.copyfile(working,
                            os.path.join(OUT, "%s_working16k.wav" % key))
            shutil.copyfile(decoded,
                            os.path.join(OUT, "%s_decoded16k.wav" % key))

        finally:

            shutil.rmtree(workdir, ignore_errors=True)

        report["recordings"][key] = entry

        print(json.dumps(entry, ensure_ascii=False, indent=2), flush=True)

    with open(os.path.join(OUT, "audio_verification.json"), "w",
              encoding="utf-8") as handle:

        json.dump(report, handle, ensure_ascii=False, indent=2)

    print("\nreport -> .pytest_tmp/diag07d/audio_verification.json")

    return 0


if __name__ == "__main__":

    sys.exit(main())
