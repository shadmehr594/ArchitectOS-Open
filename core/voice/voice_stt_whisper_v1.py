# ==========================================================
# ArchitectOS Voice STT Provider — local Whisper v1
#
# VOICE_07 — 07B REAL STT
#
# One real provider, chosen from what is ALREADY installed:
#   OpenAI Whisper, model `large-v3-turbo`, run on CPU through the
#   system interpreter that already carries whisper + torch.
#
# Nothing is downloaded here. If the provider is unavailable the
# caller gets a truthful failure contract and MUST NOT invent text.
#
# STT result contract (required by the brief):
#   transcript, detected_language, provider, confidence,
#   duration, status, error
#
# `confidence` is only ever the real Whisper `avg_logprob`. It is
# never synthesised.
# ==========================================================


from __future__ import annotations


import json
import os
import subprocess
import time
import uuid


from config import runtime_config as RC

from core.runtime.subprocess_no_window_v1 import no_window_kwargs

from core.voice.voice_capability_v1 import (
    find_interpreter,
    find_cached_model,
)


CONTRACT = "VoiceSTTResultV1"
VERSION = "1.0"

PROVIDER = "openai-whisper"

WORKER = os.path.join(
    RC.REPO_ROOT, "tools", "whisper_stt_worker.py"
)


def _worker_env():
    """The worker environment, forced to UTF-8 I/O.

    AUDIO_FIX_V1 — the worker prints its result as JSON with
    `ensure_ascii=False`, so a Persian transcript reaches `print()` as
    real Persian characters. When the worker is launched with stdout as a
    pipe and NO UTF-8 hint, Python encodes that write with the machine's
    preferred encoding — on a non-UTF-8 Windows locale that is cp1252,
    which cannot represent Persian, so the worker dies with
    `UnicodeEncodeError` BEFORE it prints anything. The parent then sees
    no JSON and truthfully reports `stt_provider_error`, which is why a
    live Persian microphone request failed after whisper had already run.

    Forcing UTF-8 here fixes it for every caller, whatever the ambient
    locale of the server process is. It changes no transcript, no
    threshold and no model.
    """

    env = dict(os.environ)

    env["PYTHONIOENCODING"] = "utf-8"

    env["PYTHONUTF8"] = "1"

    return env

# Audio formats a browser MediaRecorder may hand us.
ACCEPTED_EXTENSIONS = (
    ".wav", ".webm", ".ogg", ".oga", ".mp3", ".m4a", ".mp4", ".flac",
)

MAX_AUDIO_BYTES = 40 * 1024 * 1024


class VoiceSTTWhisper:

    VERSION = VERSION

    def __init__(self):

        self._interpreter = None

        self._model = None

        print("🎤 VOICE STT PROVIDER v1 ONLINE (local whisper, subprocess)")

    # ======================================================
    # CAPABILITY
    # ======================================================

    def interpreter(self):

        if self._interpreter is None:

            self._interpreter = find_interpreter() or ""

        return self._interpreter or None

    def model(self):

        if self._model is None:

            self._model = find_cached_model()

        return self._model

    def available(self):

        return bool(self.interpreter() and self.model())

    # ======================================================
    # FAILURE CONTRACT
    # ======================================================

    @staticmethod
    def _fail(reason, error=None, duration=None, extra=None):

        result = {

            "contract": CONTRACT,
            "version": VERSION,

            "status": "failed",
            "reason": reason,
            "error": error,

            "transcript": None,

            # Preserved for diagnostics even when the transcript is
            # withheld as unusable. Never sent to the chat path.
            "raw_transcript": None,

            "detected_language": None,

            "provider": PROVIDER,
            "model": None,

            # Never fabricated.
            "confidence": None,

            "duration": duration,

            # Truthful description of what was done to the audio before
            # decoding. The original recording is never modified.
            "audio_preprocessing": None,
            "quality": None,

            "timing": {},
        }

        if extra:

            result.update(extra)

        return result

    # ======================================================
    # TRANSCRIBE
    # ======================================================

    def transcribe(self, audio_path, language="auto", timeout=10800,
                   preprocess=True, initial_prompt=None, beam_size=None):

        """Transcribe one audio file with the local Whisper provider.

        `preprocess` builds a temporary STT working copy (16 kHz mono
        PCM with the natural leading pause removed). The original file
        is NEVER modified.

        `initial_prompt` is NOT applied by default: the 07C bias test
        showed a Persian domain prompt changes the transcript, i.e. it
        leaks expected vocabulary. Callers that pass one get a
        prompt-echo guard in the worker.
        """

        started = time.time()

        if not audio_path or not os.path.isfile(audio_path):

            return self._fail("audio_missing", str(audio_path))

        extension = os.path.splitext(audio_path)[1].lower()

        if extension and extension not in ACCEPTED_EXTENSIONS:

            return self._fail(
                "unsupported_audio_format",
                extension,
            )

        try:

            size = os.path.getsize(audio_path)

        except Exception:

            size = 0

        if size == 0:

            return self._fail("empty_recording", "0 bytes")

        if size > MAX_AUDIO_BYTES:

            return self._fail(
                "audio_too_large",
                "%d bytes (max %d)" % (size, MAX_AUDIO_BYTES),
            )

        interpreter = self.interpreter()

        if not interpreter:

            return self._fail(
                "stt_provider_unavailable",
                "no interpreter with whisper installed",
            )

        model = self.model()

        if not model:

            return self._fail(
                "stt_model_unavailable",
                "no cached whisper model found",
            )

        if not os.path.isfile(WORKER):

            return self._fail("worker_missing", WORKER)

        request = json.dumps({
            "audio_path": os.path.abspath(audio_path),
            "language": language or "auto",
            "model": model.get("model_id") or model["name"],
            "preprocess": bool(preprocess),
            "initial_prompt": initial_prompt or None,
            "beam_size": beam_size,
        })

        try:

            completed = subprocess.run(
                [interpreter, WORKER],
                input=request,
                capture_output=True,
                timeout=timeout,
                text=True,
                encoding="utf-8",
                errors="replace",
                # AUDIO_FIX_V1 — force UTF-8 I/O in the worker so a Persian
                # transcript can be printed on any Windows locale.
                env=_worker_env(),
                # NO_CONSOLE_WINDOW — the worker must never flash a console.
                **no_window_kwargs(),
            )

        except subprocess.TimeoutExpired:

            return self._fail(
                "stt_timeout",
                "worker exceeded %ss" % timeout,
                duration=round(time.time() - started, 3),
            )

        except Exception as error:

            return self._fail(
                "stt_provider_error",
                type(error).__name__ + ": " + str(error),
                duration=round(time.time() - started, 3),
            )

        payload = None

        for line in reversed((completed.stdout or "").splitlines()):

            candidate = line.strip()

            if candidate.startswith("{"):

                try:

                    payload = json.loads(candidate)

                    break

                except Exception:

                    continue

        if not isinstance(payload, dict):

            return self._fail(
                "stt_provider_error",
                (completed.stderr or "no JSON from worker")[-400:],
                duration=round(time.time() - started, 3),
            )

        transcript = payload.get("transcript")

        if payload.get("status") != "ok" or not transcript:

            return self._fail(
                payload.get("reason") or "empty_transcript",
                payload.get("error"),
                duration=round(time.time() - started, 3),
                extra={
                    "model": payload.get("model"),
                    "no_speech_prob": payload.get("no_speech_prob"),

                    # Diagnostics only - never forwarded to the chat
                    # pipeline, which only ever sees `transcript`.
                    "raw_transcript": payload.get("raw_transcript"),
                    "compression_ratio": payload.get("compression_ratio"),
                    "unique_word_ratio": payload.get("unique_word_ratio"),
                    "mean_word_probability": payload.get(
                        "mean_word_probability"
                    ),
                    "min_word_probability": payload.get(
                        "min_word_probability"
                    ),

                    "audio_preprocessing": payload.get(
                        "audio_preprocessing"
                    ),
                    "quality": payload.get("quality"),

                    "timing": payload.get("timing") or {},
                },
            )

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "status": "ok",
            "reason": None,
            "error": None,

            # The ORIGINAL transcript is preserved verbatim.
            # No silent "correction" of architectural terms - the
            # existing Chat+Language path owns normalization.
            "transcript": transcript,
            "raw_transcript": payload.get("raw_transcript") or transcript,

            "detected_language": payload.get("detected_language"),

            "provider": PROVIDER,
            "model": payload.get("model"),

            # Real Whisper avg_logprob, or None.
            "confidence": payload.get("confidence"),
            "avg_logprob": payload.get("avg_logprob"),
            "no_speech_prob": payload.get("no_speech_prob"),

            # Model-derived confidence (07D). Word probabilities come
            # from Whisper's own alignment; they never change the text.
            "mean_word_probability": payload.get("mean_word_probability"),
            "min_word_probability": payload.get("min_word_probability"),

            "duration": payload.get("duration"),

            # Truthful preprocessing / quality provenance.
            "audio_preprocessing": payload.get("audio_preprocessing"),
            "quality": payload.get("quality"),

            "timing": payload.get("timing") or {
                "total_seconds": round(time.time() - started, 3)
            },

            "audio_bytes": size,
            "segments": payload.get("segments"),
        }


# ==========================================================
# SINGLETON
# ==========================================================

voice_stt = VoiceSTTWhisper()


def transcribe(audio_path, language="auto", timeout=10800,
               preprocess=True, initial_prompt=None, beam_size=None):

    return voice_stt.transcribe(
        audio_path,
        language=language,
        timeout=timeout,
        preprocess=preprocess,
        initial_prompt=initial_prompt,
        beam_size=beam_size,
    )
