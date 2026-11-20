# ==========================================================
# ArchitectOS SAPI TTS Worker
#
# VOICE_07 — 07D TTS (optional server-side English path)
#
# Uses the OS voice through pyttsx3 (Windows SAPI). Runs in the
# provisioned system interpreter, which already has pyttsx3.
#
# Truthful by construction: if no suitable voice exists for the
# requested language, it reports `no_voice_for_language` instead of
# producing misleading audio.
#
# Protocol
#   stdin : {"text": "...", "path": "...", "language": "en|fa", "rate": 165}
#   stdout: {"status": "...", ...}   (single JSON line)
#
# Run with: <system python 3.11> tools/sapi_tts_worker.py
# ==========================================================


import json
import os
import sys
import warnings


warnings.filterwarnings("ignore")


CONTRACT = "SapiTTSWorkerV1"
VERSION = "1.0"


def _fail(reason, error=None, voices=None):

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "status": "failed",
        "reason": reason,
        "error": error,
        "path": None,
        "voice": None,
        "available_voices": voices or [],
    }


def main():

    raw = sys.stdin.read()

    try:

        request = json.loads(raw) if raw.strip() else {}

    except Exception as error:

        print(json.dumps(_fail("bad_request", str(error))))

        return 1

    text = (request.get("text") or "").strip()

    path = request.get("path")

    language = (request.get("language") or "en").lower()

    rate = request.get("rate") or 165

    if not text:

        print(json.dumps(_fail("empty_text")))

        return 1

    if not path:

        print(json.dumps(_fail("missing_output_path")))

        return 1

    try:

        import pyttsx3

    except Exception as error:

        print(json.dumps(_fail("pyttsx3_not_installed", str(error))))

        return 1

    try:

        engine = pyttsx3.init()

    except Exception as error:

        print(json.dumps(_fail("tts_engine_unavailable", str(error))))

        return 1

    voices = []

    for voice in engine.getProperty("voices") or []:

        voices.append({
            "name": getattr(voice, "name", None),
            "languages": [
                str(item) for item in (getattr(voice, "languages", None) or [])
            ],
        })

    # Truthful voice selection: never silently use a wrong-language voice.
    wanted_prefix = "fa" if language.startswith("fa") else "en"

    chosen = None

    for voice in engine.getProperty("voices") or []:

        for item in (getattr(voice, "languages", None) or []):

            if str(item).lower().startswith(wanted_prefix):

                chosen = voice

                break

        if chosen:

            break

    if chosen is None:

        print(json.dumps(_fail(
            "no_voice_for_language",
            "no installed voice for language '%s'" % wanted_prefix,
            voices,
        )))

        return 1

    try:

        engine.setProperty("voice", chosen.id)

        engine.setProperty("rate", int(rate))

    except Exception:

        pass

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    try:

        engine.save_to_file(text, os.path.abspath(path))

        engine.runAndWait()

    except Exception as error:

        print(json.dumps(_fail("synthesis_failed", str(error), voices)))

        return 1

    if not os.path.isfile(path) or os.path.getsize(path) == 0:

        print(json.dumps(_fail("empty_audio_written", None, voices)))

        return 1

    print(json.dumps({

        "contract": CONTRACT,
        "version": VERSION,

        "status": "ok",
        "reason": None,
        "error": None,

        "path": os.path.abspath(path),
        "size_bytes": os.path.getsize(path),

        "voice": getattr(chosen, "name", None),
        "language": wanted_prefix,

        "available_voices": voices,
    }))

    return 0


if __name__ == "__main__":

    sys.exit(main())
