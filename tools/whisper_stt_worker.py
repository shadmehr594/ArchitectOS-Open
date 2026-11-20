# ==========================================================
# ArchitectOS Whisper STT Worker
#
# VOICE_07 — 07B REAL STT (out-of-process)
# VOICE_07C — PERSIAN STT ACCURACY FIX
#
# Why a separate process
#   The ArchitectOS venv (Python 3.12) intentionally has NO audio
#   stack. torch + openai-whisper would be a multi-GB install, and
#   the brief forbids downloading a large model. The machine ALREADY
#   has a provisioned interpreter with whisper + torch and a cached
#   `large-v3-turbo` model, so the heavy work runs there and this
#   worker is invoked as a subprocess.
#
# 07C — what changed and why (all evidence-based)
#
#   Real human recordings showed ~1.8-2.1 s of NATURAL LEADING PAUSE
#   before speech (35-45 % of a short clip). Controlled offline
#   comparison proved this is the primary cause of the failure: the
#   SAME decoder returns Latin/Icelandic/Portuguese garbage on the
#   untouched clip and Persian on the clip whose leading pause has
#   been removed.
#
#   Therefore the worker now builds an STT WORKING COPY:
#
#     original file  ->  (never modified, always preserved)
#     working copy   ->  16 kHz mono signed-16 PCM
#                    ->  conservative leading-pause trim
#                        (0.10 s pre-roll so the first phoneme is safe)
#
#   Decoding is bounded: temperature=0.0 (deterministic) and
#   condition_on_previous_text=False (no cross-window contamination).
#
#   An `initial_prompt` is NOT applied by default. The 07C bias test
#   proved the Persian domain prompt CHANGES the transcript
#   ("پروشه"/"پروزیر" -> "پروژه") — i.e. it leaks the expected
#   vocabulary. A prompt is therefore only honoured when a caller
#   explicitly passes one, and a prompt-echo guard rejects output that
#   merely repeats it.
#
#   A repetition guard rejects obvious loops (Whisper's own
#   compression_ratio plus a unique-word ratio) and returns the
#   truthful `unusable_transcript` status instead of sending garbage
#   into the chat pipeline. The raw transcript is still preserved for
#   diagnostics.
#
#   This worker NEVER invents a transcript, NEVER post-corrects and
#   NEVER hardcodes the expected phrase.
#
# Protocol
#   stdin : {"audio_path": "...", "language": "auto|fa|en", "model": "...",
#            "preprocess": true, "trim_leading_silence": true,
#            "normalise": false, "initial_prompt": null, "beam_size": null}
#   stdout: {"status": "...", "transcript": "...", ...}   (single JSON line)
#
# Run with: <system python 3.11> tools/whisper_stt_worker.py
# ==========================================================


import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import warnings


warnings.filterwarnings("ignore")


# AUDIO_FIX_V1 — the worker prints its result as JSON with
# `ensure_ascii=False`, so a Persian transcript reaches stdout as real
# Persian characters. On a non-UTF-8 Windows locale (cp1252) that write
# raises UnicodeEncodeError and the worker dies before printing anything,
# which the parent truthfully reports as `stt_provider_error`. The parent
# now also forces UTF-8; this guard keeps the worker correct when it is
# launched directly (e.g. by the acceptance runner).
for _stream in ("stdout", "stderr"):

    try:

        getattr(sys, _stream).reconfigure(encoding="utf-8")

    except Exception:

        pass


CONTRACT = "WhisperSTTWorkerV1"
VERSION = "1.1"

DEFAULT_MODEL = "large-v3-turbo"

# Conservative leading-pause trim parameters.
PRE_ROLL_SECONDS = 0.10
TAIL_KEEP_SECONDS = 0.20
TARGET_RATE = 16000
TARGET_CHANNELS = 1

# Repetition guard thresholds, chosen from real 07C measurements:
#   healthy 030/275 transcripts : compression_ratio 0.81 - 1.11
#   observed repetition loop    : compression_ratio 8.3 - 11.4,
#                                 unique_word_ratio 0.06 - 0.10
COMPRESSION_RATIO_LIMIT = 2.4
UNIQUE_WORD_RATIO_FLOOR = 0.35
MIN_WORDS_FOR_REPETITION_CHECK = 6

# Confidence gate, calibrated in VOICE_07D against real output:
#   KNOWN-CORRECT (English controls, word probabilities):
#       mean 0.938 - 0.989   min 0.732 - 0.976   avg_logprob -0.21 .. -0.35
#   KNOWN-WRONG (the two real Persian recordings):
#       mean 0.526 - 0.559   min 0.290 - 0.455   avg_logprob -0.73 .. -0.79
# The word-probability signals separate cleanly (>= 0.19 margin on the
# mean); the segment avg_logprob does NOT separate 030 (-0.734), so it is
# only a fallback for the rare case where word probabilities are absent.
# This is a general confidence measure - it contains no vocabulary and no
# expected text, so it cannot encode the answer.
#
# HUMAN_VOICE_CONVERSATION_V1 — TWO-SIDED RE-CALIBRATION
# -------------------------------------------------------
# The original gate ALSO hard-rejected a turn when a SINGLE word fell below
# `MIN_WORD_PROBABILITY_FLOOR` (an AND-condition). Live evidence proved this
# is what rejected normal casual speech:
#   real 798 : mean 0.899  min 0.6235  -> ACCEPTED (a whisker from the floor)
# so any normal utterance with ONE mumbled / contracted word (min ~0.55)
# was refused even though the transcript was clearly usable. At the same time
# a Whisper HALLUCINATION on near-silence ("Salud.", mean 0.8951) PASSED,
# because a tiny uniformly-high-probability word set clears the mean.
#
# The gate is now:
#   * SPEECH PRESENCE  - `no_speech_prob` (previously computed, never used)
#                        must not indicate that the window contained no speech.
#   * CONFIDENCE (mean) - the primary quality signal, kept.
#   * CONFIDENCE (min)  - demoted from a hard veto to a BOUNDED tolerance:
#                        a single low-probability word is tolerated when the
#                        overall transcript is confidently decoded; only a
#                        BROADLY unclear transcript is rejected.
# Silence / noise are still rejected - truthfully, and now by the signal
# that actually measures them.
MEAN_WORD_PROBABILITY_FLOOR = 0.75
# Broadly-unclear transcript floor used WITH the mean (the min is only
# consulted together with the mean, never on its own).
MIN_WORD_PROBABILITY_FLOOR = 0.45
# A single weak word is tolerated only while the mean stays clearly healthy.
MIN_WORD_SINGLE_TOLERANCE = 0.75
# no_speech probability above which Whisper is telling us there was no
# speech in the window at all. 0.60 is deliberately permissive: real speech
# measured 0.0065 - 0.11 in VOICE_07C, silence/hallucination windows sit far
# above it.
NO_SPEECH_PROBABILITY_LIMIT = 0.60
# A very short transcript can only be trusted when the window actually
# contained speech; this pairs with the no-speech signal.
SHORT_TRANSCRIPT_WORDS = 2
AVG_LOGPROB_FLOOR_NO_WORDS = -0.90

# Companion decoder-confidence floor (HUMAN_VOICE_CONVERSATION_V1).
# The segment avg_logprob is an INDEPENDENT signal computed by Whisper
# itself; on the real recordings it separated cleanly:
#     real 765 (Persian, correct) : -0.217
#     real 030 (garbage decode)   : -0.708
#     real 160 (1-word hallucin.) : -0.857
# A floor of -0.55 sits clear of all three. It is applied ALONGSIDE the
# word-probability mean, not instead of it, so a hallucination whose few
# words happen to be high-probability is still rejected.
#
# VOICE_01 — precedence corrected: the veto is now consulted only when the
# word mean is absent or not comfortably healthy, so it can no longer
# override a healthy word-probability mean. The value itself is unchanged.
AVG_LOGPROB_COMPANION_FLOOR = -0.55


# Acoustic speech presence (VOICE_01).
# ------------------------------------
# Whisper can be CONFIDENTLY wrong about a window that holds no speech at
# all: a real silence-only recording produced "موسیقی" with
# mean_word_probability 0.7585 and avg_logprob -0.4533 while the audio RMS
# was -41.6 dBFS, so every confidence gate above accepted it. Confidence
# cannot answer "was there speech in the audio?", so the audio itself is
# measured - before the decode is spent.
#
# Calibrated on real recordings (loudest 0.25 s window of the trimmed
# working copy):
#     genuine speech : -7.1 .. -11.0 dBFS  (5 recordings, English+Persian)
#     silence/noise  : -28.8 dBFS          (1 recording)
# The floor sits near the ACCEPTING end of that 17.8 dB gap: ~13 dB below
# the quietest genuine speech and ~3.5 dB above the measured non-speech
# window. A low level ALONE is never treated as proof of silence - when the
# measurement is unavailable the gate stands down entirely (see main()).
ACOUSTIC_WINDOW_SECONDS = 0.25
ACOUSTIC_SPEECH_FLOOR_DBFS = -25.0
# Reported when the signal is EXACTLY zero. A finite level, so a digital
# silence window is rejected rather than mistaken for "not measured".
DIGITAL_SILENCE_DBFS = -120.0


# ==========================================================
# FAILURE / RESULT CONTRACT
# ==========================================================

def _base(status, reason=None, error=None, duration=None):
    """One truthful result envelope for every outcome."""

    return {
        "contract": CONTRACT,
        "version": VERSION,

        "status": status,
        "reason": reason,
        "error": error,

        "transcript": None,

        # Kept for diagnostics when `transcript` must be withheld.
        "raw_transcript": None,

        "detected_language": None,
        "confidence": None,
        "avg_logprob": None,
        "no_speech_prob": None,
        "compression_ratio": None,
        "unique_word_ratio": None,
        "mean_word_probability": None,
        "min_word_probability": None,

        "duration": duration,

        "provider": "openai-whisper",
        "model": None,

        "audio_preprocessing": {
            "applied": False,
            "original_audio_preserved": True,
            "source_path": None,
            "working_path": None,
            "leading_silence_trimmed": False,
            "trimmed_seconds": None,
            "trailing_silence_removed": None,
            "first_speech_timestamp": None,
            "resampled_hz": None,
            "channels": None,
            "normalised": False,
            "source_duration": None,
            "working_duration": None,
            "first_phoneme_preserved": None,

            # VOICE_01 acoustic speech presence. None means NOT measured -
            # never "silent". See the acoustic gate in main().
            "loudest_window_seconds": None,
            "loudest_window_dbfs": None,
            "speech_floor_dbfs": None,

            "note": None,
        },

        "quality": {
            "repetition_suspected": False,
            "prompt_echo_suspected": False,
            "script_mismatch_suspected": False,
            "low_confidence_suspected": False,
            "usable": None,
        },

        "initial_prompt_used": False,

        "segments": 0,
    }


def _fail(status, reason, error=None, duration=None):

    result = _base(status, reason=reason, error=error, duration=duration)

    return result


# ==========================================================
# AUDIO PREPROCESSING  (working copy only; source untouched)
# ==========================================================

def _ffmpeg():

    return os.environ.get("ARCHITECTOS_FFMPEG") or shutil.which("ffmpeg")


def _decode_pcm(source, target, rate=TARGET_RATE, channels=TARGET_CHANNELS):

    ffmpeg = _ffmpeg()

    if not ffmpeg:

        return False, "ffmpeg_not_found"

    completed = subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-i", source,
         "-ac", str(channels), "-ar", str(rate),
         "-c:a", "pcm_s16le", target],
        capture_output=True, text=True,
    )

    if completed.returncode != 0:

        return False, (completed.stderr or "decode_failed")[-300:]

    return True, None


def _loudest_window_dbfs(samples, rate,
                         window_seconds=ACOUSTIC_WINDOW_SECONDS):
    """Loudest short-window RMS of `samples`, in dBFS.

    This is the acoustic speech-presence measurement (VOICE_01). It reports
    what the AUDIO contains, independently of what Whisper later believes
    about it.

    Returns None when the measurement genuinely cannot be made, so no caller
    can ever mistake "not measured" for "measured silence".
    """

    import numpy as np

    try:

        values = np.asarray(samples, dtype=np.float64)

        if values.size == 0:

            return None

        seconds = float(window_seconds or ACOUSTIC_WINDOW_SECONDS)

        size = int(rate * seconds)

        # A recording shorter than one window is measured whole: a genuine
        # short utterance must still be measurable, never guessed at.
        if size <= 0 or size > values.size:

            size = values.size

        step = max(1, size // 10)

        loudest = 0.0

        for start in range(0, values.size - size + 1, step):

            rms = float(np.sqrt(np.mean(values[start:start + size] ** 2)))

            if rms > loudest:

                loudest = rms

        if loudest <= 0.0:

            # Exactly zero: measured, and it IS digital silence.
            return DIGITAL_SILENCE_DBFS

        return round(20.0 * float(np.log10(loudest / 32768.0)), 2)

    except Exception:

        return None


def _analyse_and_trim(wav_path, target_path,
                      pre_roll=PRE_ROLL_SECONDS,
                      tail_keep=TAIL_KEEP_SECONDS,
                      loudest_window=None):
    """Remove ONLY leading silence; keep the whole spoken part.

    Returns a metrics dict. `pre_roll` seconds before the detected
    onset are retained so the first phoneme is never clipped.
    """

    import numpy as np

    import wave

    with wave.open(wav_path, "rb") as handle:

        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.getnframes()
        raw = handle.readframes(frames)

    if width != 2:

        return None, "unexpected_sample_width"

    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)

    if channels > 1:

        data = data.reshape(-1, channels).mean(axis=1)

    if data.size == 0:

        return None, "empty_pcm"

    frame = max(1, int(rate * 0.010))

    count = data.size // frame

    rms = np.array([
        float(np.sqrt(np.mean(data[i * frame:(i + 1) * frame] ** 2)))
        for i in range(count)
    ])

    peak = float(np.max(np.abs(data))) or 1.0

    noise_floor = float(np.percentile(rms, 10)) if count else 0.0

    threshold = max(noise_floor * 4.0, peak * 0.02, 60.0)

    first = None

    for i in range(count):

        if rms[i] > threshold:

            first = i
            break

    last = count - 1

    for i in range(count - 1, -1, -1):

        if rms[i] > threshold:

            last = i
            break

    onset = (first or 0) * frame

    offset = min(data.size, (last + 1) * frame)

    start = max(0, onset - int(pre_roll * rate))

    end = min(data.size, offset + int(tail_keep * rate))

    trimmed = data[start:end]

    if trimmed.size == 0:

        trimmed = data

    with wave.open(target_path, "wb") as handle:

        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(
            np.clip(trimmed, -32768, 32767).astype(np.int16).tobytes()
        )

    preserved = None

    window = trimmed[onset - start: onset - start + frame]

    if window.size:

        preserved = bool(
            float(np.sqrt(np.mean(window ** 2))) > threshold * 0.5
        )

    return {
        "source_duration": round(data.size / float(rate), 3),
        "working_duration": round(trimmed.size / float(rate), 3),
        "leading_silence_removed": round(start / float(rate), 3),
        "trailing_silence_removed": round(
            (data.size - end) / float(rate), 3
        ),
        "first_speech_timestamp": round(onset / float(rate), 3),
        "first_phoneme_preserved": preserved,
        "pre_roll_seconds": pre_roll,
        "threshold": round(threshold, 2),

        # VOICE_01 acoustic speech presence, measured on the SAME PCM that
        # will be decoded. Reported even when it passes, so the floor can be
        # tuned from real recordings.
        "loudest_window_seconds": round(
            float(loudest_window or ACOUSTIC_WINDOW_SECONDS), 3
        ),
        "loudest_window_dbfs": _loudest_window_dbfs(
            trimmed, rate, loudest_window
        ),
        "speech_floor_dbfs": ACOUSTIC_SPEECH_FLOOR_DBFS,
    }, None


def _normalise(wav_path, target_path, target_peak=0.89):

    import numpy as np

    import wave

    with wave.open(wav_path, "rb") as handle:

        channels = handle.getnchannels()
        rate = handle.getframerate()
        raw = handle.readframes(handle.getnframes())

    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)

    if channels > 1:

        data = data.reshape(-1, channels).mean(axis=1)

    peak = float(np.max(np.abs(data))) or 1.0

    scaled = data * (target_peak * 32768.0 / peak)

    with wave.open(target_path, "wb") as handle:

        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(
            np.clip(scaled, -32768, 32767).astype(np.int16).tobytes()
        )

    return True


def prepare_working_copy(audio_path, options, workdir):
    """Build the STT working copy. The source file is never touched."""

    preprocess = bool(options.get("preprocess", True))

    trim = bool(options.get("trim_leading_silence", True))

    normalise = bool(options.get("normalise", False))

    meta = _base("probe")["audio_preprocessing"]

    meta["source_path"] = os.path.abspath(audio_path)

    if not preprocess:

        meta["note"] = "preprocess_disabled"

        meta["working_path"] = os.path.abspath(audio_path)

        return os.path.abspath(audio_path), meta, None

    decoded = os.path.join(workdir, "decoded16k.wav")

    ok, message = _decode_pcm(audio_path, decoded)

    if not ok:

        meta["note"] = "decode_failed:" + str(message)

        meta["working_path"] = os.path.abspath(audio_path)

        return os.path.abspath(audio_path), meta, None

    meta["applied"] = True

    meta["resampled_hz"] = TARGET_RATE

    meta["channels"] = TARGET_CHANNELS

    current = decoded

    if trim:

        trimmed = os.path.join(workdir, "trimmed16k.wav")

        metrics, error = _analyse_and_trim(
            decoded,
            trimmed,
            loudest_window=options.get(
                "speech_window_seconds", ACOUSTIC_WINDOW_SECONDS
            ),
        )

        if metrics:

            current = trimmed

            meta["leading_silence_trimmed"] = True

            meta["trimmed_seconds"] = metrics["leading_silence_removed"]

            meta["trailing_silence_removed"] = metrics[
                "trailing_silence_removed"
            ]

            meta["first_speech_timestamp"] = metrics[
                "first_speech_timestamp"
            ]

            meta["first_phoneme_preserved"] = metrics[
                "first_phoneme_preserved"
            ]

            meta["source_duration"] = metrics["source_duration"]

            meta["working_duration"] = metrics["working_duration"]

            # VOICE_01 - surface the acoustic speech-presence measurement.
            # Left as None (gate stands down) whenever the trim analysis did
            # not run, so an unmeasured recording is never called silent.
            meta["loudest_window_seconds"] = metrics[
                "loudest_window_seconds"
            ]

            meta["loudest_window_dbfs"] = metrics["loudest_window_dbfs"]

            meta["speech_floor_dbfs"] = metrics["speech_floor_dbfs"]

        else:

            meta["note"] = "trim_failed:" + str(error)

    if normalise:

        normalised = os.path.join(workdir, "normalised16k.wav")

        if _normalise(current, normalised):

            current = normalised

            meta["normalised"] = True

    meta["working_path"] = os.path.abspath(current)

    return os.path.abspath(current), meta, None


# ==========================================================
# QUALITY GUARD
# ==========================================================

def _normalise_text(text):

    return " ".join(str(text or "").split()).strip(" .،؟!,")


def _script_profile(text):

    persian = 0
    latin = 0

    for character in str(text or ""):

        if "\u0600" <= character <= "\u06FF":

            persian += 1

        elif "a" <= character.lower() <= "z":

            latin += 1

    return persian, latin


def assess_quality(text, first_segment, initial_prompt, language="auto",
                   mean_word_probability=None, min_word_probability=None,
                   avg_logprob=None, no_speech_probability=None,
                   detected_language=None):

    words = [w for w in str(text or "").split() if w]

    unique_ratio = (
        round(len(set(words)) / float(len(words)), 3) if words else None
    )

    compression = first_segment.get("compression_ratio")

    repetition = False

    if compression is not None and compression > COMPRESSION_RATIO_LIMIT:

        repetition = True

    if (unique_ratio is not None
            and len(words) >= MIN_WORDS_FOR_REPETITION_CHECK
            and unique_ratio < UNIQUE_WORD_RATIO_FLOOR):

        repetition = True

    echo = False

    if initial_prompt and text:

        echo = _normalise_text(text) == _normalise_text(initial_prompt)

    # Script consistency. Two cases:
    #  * Persian was explicitly requested (language="fa") but the decode
    #    came back Latin-only -> a mis-recognition.
    #  * language is AUTO: Whisper's own detected language is used. When a
    #    Persian/mixed conversation is expected and the decode is Latin-only
    #    AND Whisper's own detection did not say English, the script is
    #    inconsistent with the audio. (HUMAN_VOICE_CONVERSATION_V1 — the
    #    "Salud." hallucination on Persian speech reached the chat path
    #    because the old check only ran when language started with "fa",
    #    but the UI sends "auto".)
    # This is a script check, not a content check, so it never encodes the
    # expected phrase.
    script_mismatch = False

    requested_fa = str(language or "").lower().startswith("fa")

    if text and requested_fa:

        persian, latin = _script_profile(text)

        script_mismatch = latin > 0 and persian == 0

    elif text and str(language or "").lower() in ("", "auto", "none"):

        persian, latin = _script_profile(text)

        detected = str(detected_language or "").lower()

        # Latin-only output that Whisper did NOT itself call English, in a
        # turn the decoder did not label "en", is script-inconsistent.
        # A REAL English utterance is labelled "en" by Whisper and passes.
        if latin > 0 and persian == 0 and detected not in ("en", "english"):

            script_mismatch = True

    # Confidence: the model's own probabilities.
    #
    # The MEAN word probability is the primary signal. The segment
    # avg_logprob is a SECOND, independent confidence signal: it is
    # computed by Whisper itself (not from word alignment) and separated
    # real speech (765: -0.217) from garbage (030: -0.708, 160: -0.857)
    # cleanly on the real recordings. It is applied as a companion veto so
    # a hallucination whose few words happen to be high-probability is
    # still rejected on the true decoder confidence.
    #
    # The MIN no longer vetoes on its own: a single unclear word inside an
    # otherwise clearly-decoded transcript is tolerated.
    low_confidence = False

    low_confidence_reason = None

    if mean_word_probability is not None:

        mean_ok = mean_word_probability >= MEAN_WORD_PROBABILITY_FLOOR

        min_ok = (
            min_word_probability is None
            or min_word_probability >= MIN_WORD_PROBABILITY_FLOOR
        )

        if not mean_ok:

            low_confidence = True

            low_confidence_reason = "mean_word_probability"

        elif not min_ok:

            # one or more weak words — tolerated when the mean is clearly
            # healthy (single-word noise), rejected when the whole
            # transcript is only borderline.
            if mean_word_probability < MIN_WORD_SINGLE_TOLERANCE:

                low_confidence = True

                low_confidence_reason = "min_word_probability"

    elif avg_logprob is not None:

        # No word probabilities available - fall back to the segment
        # log-probability alone, at a more conservative threshold.
        low_confidence = avg_logprob < AVG_LOGPROB_FLOOR_NO_WORDS

        if low_confidence:

            low_confidence_reason = "avg_logprob"

    # Companion decoder-confidence veto (independent of the word mean).
    #
    # VOICE_01 FIX — the veto must not OVERRIDE healthy word evidence.
    # It exists for the case the word probabilities cannot speak for
    # themselves: no word probabilities at all, or a mean that is not
    # comfortably healthy. Live evidence: the CORRECT English
    # "How are you?" measured mean_wp 0.7825 / min_wp 0.49 with an
    # avg_logprob below this floor, so a short, tightly trimmed window whose
    # every word was right was still discarded. The veto now applies only
    # while the word mean is absent or not comfortably healthy; the primary
    # mean/min floors, silence, repetition, echo, script and the short
    # transcript guard below are all unchanged.
    word_evidence_healthy = (
        mean_word_probability is not None
        and mean_word_probability >= MIN_WORD_SINGLE_TOLERANCE
    )

    if (not low_confidence
            and not word_evidence_healthy
            and avg_logprob is not None
            and avg_logprob < AVG_LOGPROB_COMPANION_FLOOR):

        low_confidence = True

        low_confidence_reason = "avg_logprob_companion"

    # `no_speech_prob` is computed and reported for diagnostics. Measured on
    # this provider it is ~1e-10 on every window INCLUDING synthetic
    # silence/noise, so it is NOT used as a decision signal here (doing so
    # would be a blind threshold). It is surfaced truthfully instead.
    no_speech_suspected = False

    if no_speech_probability is not None:

        try:

            no_speech_suspected = (
                float(no_speech_probability) > NO_SPEECH_PROBABILITY_LIMIT
            )

        except Exception:

            no_speech_suspected = False

    # A very short transcript (1-2 words) whose decode is ALSO
    # low-confidence is unreliable: this is the "Salud." / "you" /
    # "شلو" case — a short hallucination, not real speech. It is rejected
    # via `low_confidence` only when avg_logprob says the decode was weak,
    # so a genuine short "باشه." is still accepted.
    short_unreliable = False

    if (
        words
        and len(words) <= SHORT_TRANSCRIPT_WORDS
        and avg_logprob is not None
        and avg_logprob < AVG_LOGPROB_COMPANION_FLOOR

        # VOICE_01 (short genuine words) — a weak SEGMENT log-probability
        # must not condemn a short transcript on its own while the WORD
        # evidence is healthy. Live evidence: the genuine Persian word
        # "سلام" was decoded CORRECTLY with mean_word_probability 0.9405 and
        # avg_logprob -0.565, and the user was told "no speech was heard".
        # A single word carries a far noisier segment log-probability than a
        # sentence, so the word mean is the signal entitled to speak for it.
        # Nothing else is relaxed: the mean/min floors, the companion veto,
        # repetition, echo and script checks all still apply, and this guard
        # still fires whenever the word evidence is absent or weak.
        and (mean_word_probability is None
             or mean_word_probability < MEAN_WORD_PROBABILITY_FLOOR)
    ):

        short_unreliable = True

    usable = not (
        repetition
        or echo
        or script_mismatch
        or low_confidence
        or short_unreliable
    )

    return {
        "repetition_suspected": bool(repetition),
        "prompt_echo_suspected": bool(echo),
        "script_mismatch_suspected": bool(script_mismatch),
        "low_confidence_suspected": bool(low_confidence),
        "low_confidence_reason": low_confidence_reason,
        "no_speech_suspected": bool(no_speech_suspected),
        "short_transcript_unreliable": bool(short_unreliable),
        "usable": usable,
        "compression_ratio": compression,
        "unique_word_ratio": unique_ratio,
    }


def _speech_floor(request):
    """The acoustic speech-presence floor for this request, in dBFS.

    Defaults to the calibrated constant. A caller may override it with
    `speech_floor_dbfs`, or set it to `null` to stand the gate down - the
    escape hatch if a genuine speaker ever falls below the floor.
    """

    value = (request or {}).get(
        "speech_floor_dbfs", ACOUSTIC_SPEECH_FLOOR_DBFS
    )

    if value is None:

        return None

    try:

        return float(value)

    except Exception:

        return ACOUSTIC_SPEECH_FLOOR_DBFS


# ==========================================================
# MAIN
# ==========================================================

def main():

    raw = sys.stdin.read()

    try:

        request = json.loads(raw) if raw.strip() else {}

    except Exception as error:

        print(json.dumps(_fail("failed", "bad_request", str(error))))

        return 1

    audio_path = request.get("audio_path")

    language = request.get("language") or "auto"

    model_name = request.get("model") or DEFAULT_MODEL

    initial_prompt = request.get("initial_prompt") or None

    beam_size = request.get("beam_size")

    if not audio_path or not os.path.isfile(audio_path):

        print(json.dumps(_fail("failed", "audio_missing", audio_path)))

        return 1

    started = time.time()

    try:

        import whisper

    except Exception as error:

        print(json.dumps(_fail("failed", "whisper_not_installed",
                               str(error))))

        return 1

    try:

        model = whisper.load_model(model_name, device="cpu")

    except Exception as error:

        print(json.dumps(_fail("failed", "model_load_failed", str(error))))

        return 1

    load_seconds = time.time() - started

    workdir = tempfile.mkdtemp(prefix="architectos_stt_")

    try:

        working_path, preprocessing, _ = prepare_working_copy(
            audio_path, request, workdir
        )

        # ---- VOICE_01 ACOUSTIC SPEECH PRESENCE -------------------------
        #
        # Placed BEFORE the decode, because confidence cannot answer "was
        # there speech in this audio?". A real silence-only recording
        # produced a transcript with mean_word_probability 0.7585 and
        # avg_logprob -0.4533, so every confidence gate above accepted it.
        #
        # A low level ALONE is never treated as proof of silence:
        #   * the floor is configurable via `speech_floor_dbfs`, and
        #   * when the measurement is unavailable (preprocessing disabled,
        #     decode/trim failed, no samples) the gate stands down entirely
        #     and the turn proceeds exactly as before.
        # The measured energy is always reported in `audio_preprocessing`.
        floor_dbfs = _speech_floor(request)

        measured_dbfs = (preprocessing or {}).get("loudest_window_dbfs")

        if (floor_dbfs is not None
                and measured_dbfs is not None
                and float(measured_dbfs) < floor_dbfs):

            outcome = _fail(
                "unusable_transcript",
                "no_speech_detected",
                "acoustic speech presence below floor: %s dBFS < %s dBFS"
                % (measured_dbfs, floor_dbfs),
                # Truthful audio duration at this boundary. (The provider's
                # failure envelope overwrites `duration` with its own wall
                # clock - pre-existing - so the same value is repeated under
                # `timing.audio_duration`, which it does carry through.)
                duration=(preprocessing or {}).get("working_duration"),
            )

            outcome["model"] = model_name

            outcome["audio_preprocessing"] = preprocessing

            outcome["quality"] = {
                "repetition_suspected": False,
                "prompt_echo_suspected": False,
                "script_mismatch_suspected": False,
                "low_confidence_suspected": False,
                "low_confidence_reason": None,
                "no_speech_suspected": True,
                "short_transcript_unreliable": False,
                "usable": False,
                # Diagnostics: the measurement and the floor applied.
                "acoustic_loudest_window_dbfs": measured_dbfs,
                "acoustic_speech_floor_dbfs": floor_dbfs,
            }

            # Proof that the decode was skipped, not merely unhelpful.
            outcome["timing"] = {
                "model_load_seconds": round(load_seconds, 3),
                "transcribe_seconds": 0.0,
                "total_seconds": round(time.time() - started, 3),
                "rejected_before_decode": True,
                "audio_duration": (preprocessing or {}).get(
                    "working_duration"
                ),
            }

            print(json.dumps(outcome, ensure_ascii=False))

            return 0

        transcribe_started = time.time()

        decode_options = dict(
            fp16=False,
            task="transcribe",
            language=(None if language in (None, "", "auto") else language),
            verbose=False,
            # Bounded decoding — deterministic and free of cross-window
            # contamination. Proven in the 07C comparison.
            temperature=0.0,
            condition_on_previous_text=False,
        )

        # Word-level probabilities are the confidence signal measured in
        # 07D. They do NOT change the decoded text (verified: identical
        # transcripts with and without this flag on both recordings).
        confidence_probe = bool(request.get("confidence_probe", True))

        if confidence_probe:

            decode_options["word_timestamps"] = True

        if beam_size:

            decode_options["beam_size"] = int(beam_size)

        if initial_prompt:

            decode_options["initial_prompt"] = initial_prompt

        try:

            result = model.transcribe(working_path, **decode_options)

        except Exception as error:

            outcome = _fail("failed", "transcribe_failed", str(error))
            outcome["model"] = model_name
            outcome["audio_preprocessing"] = preprocessing
            print(json.dumps(outcome, ensure_ascii=False))
            return 1

        transcribe_seconds = time.time() - transcribe_started

        text = (result.get("text") or "").strip()

        segments = result.get("segments") or []

        first = segments[0] if segments else {}

        # Per-word probabilities across every segment (07D confidence).
        word_probabilities = [
            w["probability"]
            for segment in segments
            for w in (segment.get("words") or [])
            if w.get("probability") is not None
        ]

        mean_word_probability = (
            round(sum(word_probabilities) / len(word_probabilities), 4)
            if word_probabilities else None
        )

        min_word_probability = (
            round(min(word_probabilities), 4) if word_probabilities else None
        )

        quality = assess_quality(
            text, first, initial_prompt, language,
            mean_word_probability=mean_word_probability,
            min_word_probability=min_word_probability,
            avg_logprob=first.get("avg_logprob"),
            no_speech_probability=first.get("no_speech_prob"),
            detected_language=result.get("language"),
        )

        avg_logprob = first.get("avg_logprob")

        duration = None

        try:

            import wave

            with wave.open(working_path, "rb") as handle:

                frames = handle.getnframes()

                rate = handle.getframerate() or 1

                duration = round(frames / float(rate), 3)

        except Exception:

            duration = preprocessing.get("working_duration")

        if not text:

            status = "empty_transcript"
            reason = "empty_transcript"

        elif not quality["usable"]:

            status = "unusable_transcript"

            if quality["repetition_suspected"]:

                reason = "repetition_detected"

            elif quality["prompt_echo_suspected"]:

                reason = "prompt_echo_detected"

            elif quality["script_mismatch_suspected"]:

                reason = "script_mismatch_detected"

            elif quality.get("short_transcript_unreliable"):

                # high per-word probability but the window held no speech
                reason = "no_speech_detected"

            else:

                reason = "low_confidence_detected"

        else:

            status = "ok"
            reason = None

        outcome = _base(
            status,
            reason=reason,
            duration=duration,
        )

        # The raw transcript is preserved for diagnostics in every
        # case; `transcript` is only populated when the result is
        # actually usable, so garbage can never reach the chat path.
        outcome["raw_transcript"] = text or None
        outcome["transcript"] = text if status == "ok" else None

        outcome["detected_language"] = result.get("language")

        outcome["confidence"] = (
            round(float(avg_logprob), 4) if avg_logprob is not None else None
        )
        outcome["avg_logprob"] = avg_logprob
        outcome["no_speech_prob"] = first.get("no_speech_prob")
        outcome["compression_ratio"] = quality["compression_ratio"]
        outcome["unique_word_ratio"] = quality["unique_word_ratio"]
        outcome["mean_word_probability"] = mean_word_probability
        outcome["min_word_probability"] = min_word_probability

        outcome["model"] = model_name

        outcome["audio_preprocessing"] = preprocessing

        outcome["quality"] = {
            "repetition_suspected": quality["repetition_suspected"],
            "prompt_echo_suspected": quality["prompt_echo_suspected"],
            "script_mismatch_suspected": quality[
                "script_mismatch_suspected"
            ],
            "low_confidence_suspected": quality[
                "low_confidence_suspected"
            ],
            "low_confidence_reason": quality.get("low_confidence_reason"),
            "no_speech_suspected": quality.get("no_speech_suspected"),
            "short_transcript_unreliable": quality.get(
                "short_transcript_unreliable"
            ),
            "usable": quality["usable"],
        }

        outcome["initial_prompt_used"] = bool(initial_prompt)

        outcome["segments"] = len(segments)

        outcome["timing"] = {
            "model_load_seconds": round(load_seconds, 3),
            "transcribe_seconds": round(transcribe_seconds, 3),
            "total_seconds": round(time.time() - started, 3),
        }

        print(json.dumps(outcome, ensure_ascii=False))

        return 0

    finally:

        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":

    sys.exit(main())
