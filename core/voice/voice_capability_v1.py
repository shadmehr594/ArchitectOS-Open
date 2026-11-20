# ==========================================================
# ArchitectOS Voice Capability Contract v1
#
# VOICE_07 — truthful capability reporting
#
# Capabilities are DERIVED by probing this machine:
#   - which interpreter has whisper + torch
#   - whether the Whisper model is already cached
#   - which SAPI / OS voices exist
#   - which speech recognizers exist
#
# Nothing is assumed and nothing is hardcoded to a desired answer.
# If Persian TTS is not installed, it is reported as unavailable.
# ==========================================================


from __future__ import annotations


import glob
import json
import os
import subprocess
import sys

from core.runtime.subprocess_no_window_v1 import no_window_kwargs


CONTRACT = "VoiceCapabilityV1"
VERSION = "1.0"


# Interpreters that may carry the audio stack, most preferred first.
# The ArchitectOS venv is deliberately NOT expected to have it.
def _candidate_interpreters():
    """Locate interpreters that may carry the audio stack, without hardcoded user paths."""
    out = []
    env = os.environ.get("ARCHITECTOS_VOICE_PYTHON")
    if env:
        out.append(env)
    local = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    for ver in ("Python312", "Python311", "Python310"):
        out.append(os.path.join(local, "Programs", "Python", ver, "python.exe"))
    out.append(sys.executable)
    return tuple(dict.fromkeys(out))


CANDIDATE_INTERPRETERS = _candidate_interpreters()

# Whisper model cache locations.
MODEL_CACHE_DIRS = (
    os.path.join(os.path.expanduser("~"), ".cache", "whisper"),
)

MODEL_CANDIDATES = (
    "large-v3-turbo.pt",
    "large-v3.pt",
    "medium.pt",
    "small.pt",
    "base.pt",
    "tiny.pt",
)

PROBE_FLAGS = "--voice-capability-probe"

# Languages Whisper `large-v3-turbo` supports that we care about.
WHISPER_RELEVANT_LANGUAGES = ("fa", "en")


def _probe_script():

    return (
        "import json,sys\n"
        "out={'whisper':False,'torch':False,'pyttsx3':False,"
        "'torch_version':None,'voices':[],'recognizers':[]}\n"
        "try:\n"
        "    import whisper; out['whisper']=True\n"
        "except Exception: pass\n"
        "try:\n"
        "    import torch; out['torch']=True; out['torch_version']=torch.__version__\n"
        "except Exception: pass\n"
        "try:\n"
        "    import pyttsx3\n"
        "    out['pyttsx3']=True\n"
        "    e=pyttsx3.init()\n"
        "    for v in e.getProperty('voices'):\n"
        "        out['voices'].append({'name':getattr(v,'name',None),"
        "'languages':[str(x) for x in (getattr(v,'languages',None) or [])]})\n"
        "except Exception: pass\n"
        "try:\n"
        "    import speech_recognition as sr\n"
        "    out['recognizers']=[str(x) for x in sr.Microphone.list_microphone_names()][:5]\n"
        "except Exception: pass\n"
        "print(json.dumps(out))\n"
    )


def find_interpreter():

    """First candidate interpreter that can import whisper.

    ARCHITECTOS_VOICE_PYTHON overrides discovery explicitly, which is
    also how the STT-unavailable path is tested truthfully.
    """

    override = os.environ.get("ARCHITECTOS_VOICE_PYTHON")

    if override is not None:

        if override and os.path.isfile(override):

            try:

                completed = subprocess.run(
                    [override, "-c", "import whisper"],
                    capture_output=True,
                    timeout=10800,
                    **no_window_kwargs(),
                )

                if completed.returncode == 0:

                    return override

            except Exception:

                pass

        return None

    for path in CANDIDATE_INTERPRETERS:

        if not os.path.isfile(path):

            continue

        try:

            completed = subprocess.run(
                [path, "-c", "import whisper"],
                capture_output=True,
                timeout=10800,
                **no_window_kwargs(),
            )

            if completed.returncode == 0:

                return path

        except Exception:

            continue

    return None


def find_cached_model():

    override = os.environ.get("ARCHITECTOS_VOICE_MODEL_CACHE")

    directories = MODEL_CACHE_DIRS

    if override is not None:

        directories = (override,) if override else ()

    for directory in directories:

        if not os.path.isdir(directory):

            continue

        for name in MODEL_CANDIDATES:

            path = os.path.join(directory, name)

            if os.path.isfile(path):

                # whisper.load_model() wants the model NAME, not the
                # cache filename.
                model_id = name[:-3] if name.endswith(".pt") else name

                return {
                    "name": name,
                    "model_id": model_id,
                    "path": path,
                    "size_bytes": os.path.getsize(path),
                }

    return None


def probe_interpreter(path):

    if not path:

        return {}

    try:

        completed = subprocess.run(
            [path, "-c", _probe_script()],
            capture_output=True,
            timeout=10800,
            text=True,
            encoding="utf-8",
            errors="replace",
            **no_window_kwargs(),
        )

        if completed.returncode != 0:

            return {"error": "probe_failed"}

        line = (completed.stdout or "").strip().splitlines()

        if not line:

            return {"error": "probe_empty"}

        return json.loads(line[-1])

    except Exception as error:

        return {"error": type(error).__name__ + ": " + str(error)}


def _persian_server_tts():
    """PERSIAN_TTS_V1 — the server-side Persian provider report.

    Kept separate from the OS voice stores so the capability report can
    never claim a local Persian voice that does not exist. Never raises.
    """

    try:

        from core.voice.persian_tts_v1 import persian_tts

        return persian_tts.describe()

    except Exception as error:

        return {
            "provider": None,
            "available": False,
            "reason": type(error).__name__ + ": " + str(error),
        }


def _persian_in(voices):

    for voice in voices or []:

        for language in voice.get("languages") or []:

            lowered = str(language).lower()

            if lowered.startswith("fa") or "persian" in lowered:

                return True

    return False


def audit(force=False):

    """Truthful voice capability contract for this machine."""

    interpreter = find_interpreter()

    model = find_cached_model()

    probed = probe_interpreter(interpreter)

    voices = probed.get("voices") or []

    stt_available = bool(
        interpreter and probed.get("whisper") and model
    )

    tts_available = bool(voices)

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "capabilities": {

            "stt_available": stt_available,
            "stt_provider": "openai-whisper" if stt_available else None,
            "stt_model": (model or {}).get("name"),
            "stt_offline": True,
            "stt_languages": list(WHISPER_RELEVANT_LANGUAGES)
            if stt_available else [],

            "tts_available": tts_available,
            "tts_provider": "windows-sapi" if tts_available else None,
            # PERSIAN_TTS_V1 — the OS voice stores have no Persian voice, so
            # `tts_persian` stays truthful about the LOCAL stores. A Persian
            # reply is still possible through the server-side provider, which
            # is reported separately and never conflated with the OS path.
            "tts_persian": _persian_in(voices),
            "tts_persian_server": _persian_server_tts().get("available") is True,
            "tts_persian_provider": _persian_server_tts(),
            "tts_voices": voices,

            "browser_speech_synthesis_expected": True,

            "microphone_capture": "browser",
        },

        "environment": {

            "interpreter": interpreter,
            "interpreter_has_whisper": bool(probed.get("whisper")),
            "interpreter_has_torch": bool(probed.get("torch")),
            "torch_version": probed.get("torch_version"),
            "interpreter_has_pyttsx3": bool(probed.get("pyttsx3")),

            "model_cache": MODEL_CACHE_DIRS,
            "model": model,

            "recognizers": probed.get("recognizers") or [],

            "venv_has_audio_stack": _venv_has_audio_stack(),
        },

        "limitations": _limitations(stt_available, tts_available, voices),

        "stt_contract_fields": [
            "transcript",
            "detected_language",
            "provider",
            "confidence",
            "duration",
            "status",
            "error",
        ],
    }


def _venv_has_audio_stack():

    for module in ("whisper", "torch", "pyttsx3"):

        try:

            __import__(module)

            return True

        except Exception:

            continue

    return False


def _limitations(stt_available, tts_available, voices):

    limitations = []

    if not stt_available:

        limitations.append(
            "local STT provider unavailable (interpreter or cached model missing)"
        )

    if not tts_available:

        limitations.append("no OS TTS voice detected")

    elif not _persian_in(voices):

        limitations.append(
            "no Persian TTS voice installed: Persian replies remain TEXT; "
            "English TTS is available"
        )

    return limitations


def describe():

    result = audit()

    return {

        "contract": result["contract"],
        "version": result["version"],
        "capabilities": result["capabilities"],
        "limitations": result["limitations"],
    }


if __name__ == "__main__":

    print(json.dumps(describe(), ensure_ascii=False, indent=2))
