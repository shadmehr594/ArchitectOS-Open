# -*- coding: utf-8 -*-
"""ARCHITECTOS PERSIAN TTS V1

A minimal SERVER-SIDE Persian text-to-speech provider.

WHY THIS EXISTS
---------------
Neither voice store on this machine has a Persian voice:
  * SAPI5      -> Microsoft David / Zira (en-US only)
  * OneCore    -> Microsoft David / Mark / Zira (en-US only)

`window.speechSynthesis` only ever enumerates the LOCAL OneCore voices, so a
browser can never speak Persian here, and the server-side SAPI worker has no
Persian voice either. A server-side provider is therefore the only way to
produce real Persian audio.

THE ENGINE
----------
`edge-tts` — the free Microsoft Edge read-aloud speech service
(`speech.platform.bing.com`, the same service Edge itself uses).
It requires NO API key and NO account. It exposes two Persian voices:
    fa-IR-DilaraNeural (female)   fa-IR-FaridNeural (male)

SCOPE
-----
Audio only. This module synthesises Persian speech bytes and nothing else.
It does not touch STT, Whisper, the chat pipeline, vision, knowledge,
reasoning, spatial organization, render, CAD/BIM/IFC or any architectural
layer.

TRUTHFULNESS
------------
It never fakes a voice and never silently falls back to English: if the
engine or the voice is unavailable it returns a failed result with a reason.
"""

from __future__ import annotations

import asyncio
import os
import socket
import threading
import time
from typing import Any, Dict, Optional


CONTRACT = "PersianTTSV1"
VERSION = "1.0"

PROVIDER = "edge-tts"

# the Persian voices the Edge service exposes, in preference order
PERSIAN_VOICES = (
    "fa-IR-DilaraNeural",   # female
    "fa-IR-FaridNeural",    # male
)

DEFAULT_VOICE = PERSIAN_VOICES[0]

# the engine is online; a hard cap keeps a request from hanging
SYNTH_TIMEOUT_SECONDS = 25

# keep a generous but bounded cap on the text sent to the service
MAX_TEXT_CHARS = 1200


def _edge_tts():
    """The engine, or None when it is not installed."""

    try:

        import edge_tts

        return edge_tts

    except Exception:

        return None


def _is_persian(text: str) -> bool:

    return any("\u0600" <= ch <= "\u06ff" for ch in str(text or ""))


# ==========================================================
# PERSIAN_VOICE_QUALITY_V2 / PHASE 3 — SPOKEN-TEXT PREPARATION
#
# MEASURED FACT (tools/audit_persian_tts_v2_phase3.py): edge-tts does NOT
# interpret SSML. Wrapping "سلام" in <speak><prosody> tags produced
# 70128 bytes instead of 15552 — i.e. the tags were SPOKEN ALOUD, and a
# <bogustag> likewise produced audio instead of an error. Therefore:
#
#   * this provider must NEVER be handed SSML/prosody markup (it would be
#     read literally), and
#   * any angle-bracket markup that reaches it must be removed first.
#
# This preparation is applied to the SYNTHESIS INPUT ONLY. It never
# changes the written reply the user sees; the chat text is untouched.
# ==========================================================

import re as _re

# markup that must never be spoken: XML/HTML-ish tags and entities
_MARKUP_TAG = _re.compile(r"<[^>\n]{0,200}>")
_MARKUP_ENTITY = _re.compile(r"&(?:[a-zA-Z]{2,10}|#\d{1,6});")

# characters that make edge-tts stumble or are not part of spoken Persian;
# replaced by a space (never by a wrong letter — spelling is preserved).
_UNSPEAKABLE = _re.compile(r"[`*_~^|<>{}\[\]\\]")


def prepare_spoken_text(text: Any) -> str:
    """Return text safe to hand to the spoken-Persian engine.

    Guarantees:
      * no angle-bracket markup (would be read aloud by edge-tts)
      * no markup entities
      * no stray formatting characters that break the prosody model

    It does NOT "fix" spelling, does NOT translate, does NOT touch Latin
    technical tokens (e.g. "ArchitectOS"), and does NOT alter the written
    reply — it prepares the synthesis input only.

    PERSIAN_OUTPUT_ORTHOGRAPHY_V1 / PART B — NO TTS-ONLY PRONUNCIATION
    OVERRIDE IS APPLIED HERE, and that is a deliberate, measured decision:

      * edge-tts exposes NO usable SSML (measured: tags are read aloud).
      * Persian diacritics are NEUTRALISED by the engine — «خلوت»,
        «خَلْوَت» and «خَلْوَتُ» render to the identical 11232 bytes /
        1.87 s on both fa-IR voices, so a hidden diacritic form cannot
        change the pronunciation of «خلوت».
      * ZWNJ / spacing / Latin transliteration do not change the rendered
        word audio either.

    Therefore there is no working mechanism to bend «خلوت» toward
    «khalvat» on the engine side. Rather than ship a fake repair, or
    intentionally misspell the visible text to force a sound, the spoken
    input is kept IDENTICAL to the displayed text (verified: this function
    is a byte-for-byte no-op on clean Persian). The residual accent/lexical
    pronunciation of the stock fa-IR voices is an engine limitation that is
    reported truthfully, not hidden, and remains an operator listening
    judgement (see .pytest_tmp/tts_listening_set_v1/).
    """

    out = str(text or "")

    out = _MARKUP_TAG.sub(" ", out)
    out = _MARKUP_ENTITY.sub(" ", out)
    out = _UNSPEAKABLE.sub(" ", out)

    # collapse the whitespace the removals may have created
    out = _re.sub(r"[ \t\u00a0]{2,}", " ", out)
    out = _re.sub(r"\s*\n\s*", " ", out)

    return out.strip()



def _fail(reason: str, error: Optional[str] = None) -> Dict[str, Any]:

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "status": "failed",
        "reason": reason,
        "error": error,
        "provider": PROVIDER,
        "voice": None,
        "language": "fa",
        "audio": None,
        "audio_bytes": 0,
        "content_type": None,
    }


def available() -> bool:
    """True when the engine is importable (it is an online service)."""

    return _edge_tts() is not None


# ==========================================================
# OFFLINE_FIRST_V1 — reachability, told TRUTHFULLY.
#
# `available()` above only says the package is importable. It is NOT a
# claim that the ONLINE service can be reached. The capability report
# must not advertise a Persian voice that cannot actually be produced
# while the machine is offline, so reachability is probed separately and
# cached briefly (an honest, bounded check — not a per-request network
# round-trip on the hot path).
# ==========================================================

_REACHABILITY_TTL_SECONDS = 30

_reachability_lock = threading.Lock()

_reachability_cache: Dict[str, Any] = {"at": 0.0, "online": None}


def reachable(force: bool = False) -> bool:
    """True when the edge-tts ONLINE endpoint can actually be reached.

    This is a short, bounded connectivity probe. The result is cached for
    a few seconds so the capability report (and repeated UI polls) never
    hammer the network. It never raises: any failure means "offline".
    """

    now = time.time()

    with _reachability_lock:

        cached = _reachability_cache.get("online")

        fresh = (
            cached is not None
            and (now - float(_reachability_cache.get("at") or 0.0))
            < _REACHABILITY_TTL_SECONDS
        )

        if fresh and not force:

            return bool(cached)

        online = False

        try:

            # A DNS + TCP connect to the speech endpoint host. Cheap,
            # bounded, and independent of the synthesis path.
            socket.create_connection(
                ("speech.platform.bing.com", 443), timeout=4
            ).close()

            online = True

        except Exception:

            online = False

        _reachability_cache["online"] = online

        _reachability_cache["at"] = now

        return online


def voices() -> list:
    """The Persian voices this provider can use."""

    return list(PERSIAN_VOICES)


def _run(coro):

    """Run a coroutine from synchronous (Flask) code.

    A fresh event loop is used per call, and it is always closed. If the
    caller already has a running loop (not the case in the Flask sync
    path) the coroutine is executed on a worker thread instead.
    """

    try:

        asyncio.get_running_loop()

    except RuntimeError:

        loop = asyncio.new_event_loop()

        try:

            return loop.run_until_complete(coro)

        finally:

            loop.close()

    # a loop is already running on this thread -> use a worker thread
    box: Dict[str, Any] = {}

    def _worker():

        loop = asyncio.new_event_loop()

        try:

            box["value"] = loop.run_until_complete(coro)

        except Exception as error:  # pragma: no cover - defensive

            box["error"] = error

        finally:

            loop.close()

    thread = threading.Thread(target=_worker)

    thread.start()

    thread.join(SYNTH_TIMEOUT_SECONDS + 5)

    if "error" in box:

        raise box["error"]

    return box.get("value")


async def _synthesize_async(text: str, voice: str) -> bytes:

    edge_tts = _edge_tts()

    if edge_tts is None:

        raise RuntimeError("edge_tts_not_installed")

    communicate = edge_tts.Communicate(text, voice)

    buffer = bytearray()

    async for chunk in communicate.stream():

        if chunk.get("type") == "audio" and chunk.get("data"):

            buffer.extend(chunk["data"])

    return bytes(buffer)


def synthesize(
    text: Any,
    *,
    voice: Optional[str] = None,
) -> Dict[str, Any]:

    """Persian text -> MP3 bytes.

    Returns a truthful result dict. `status == "ok"` and non-empty
    `audio` bytes are the ONLY success signal.
    """

    raw = str(text or "").strip()

    if not raw:

        return _fail("empty_text")

    # PERSIAN_VOICE_QUALITY_V2 / PHASE 3 — strip markup the engine would
    # otherwise speak aloud (edge-tts has NO SSML support; measured).
    raw = prepare_spoken_text(raw)

    if not raw:

        return _fail("empty_text")

    if not _is_persian(raw):

        # this provider is for Persian only; English keeps its own path
        return _fail("not_persian_text")

    if len(raw) > MAX_TEXT_CHARS:

        raw = raw[:MAX_TEXT_CHARS]

    if _edge_tts() is None:

        return _fail(
            "tts_engine_unavailable",
            "edge-tts is not installed in this interpreter",
        )

    chosen = voice if voice in PERSIAN_VOICES else DEFAULT_VOICE

    try:

        audio = _run(_synthesize_async(raw, chosen))

    except Exception as error:

        return _fail("synthesis_failed", type(error).__name__ + ": " + str(error))

    if not audio:

        return _fail("empty_audio")

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "status": "ok",
        "reason": None,
        "error": None,
        "provider": PROVIDER,
        "voice": chosen,
        "language": "fa",
        "audio": audio,
        "audio_bytes": len(audio),
        "content_type": "audio/mpeg",
    }


def describe() -> Dict[str, Any]:

    """The capability report (used by the voice capability endpoint).

    OFFLINE_FIRST_V1 — `available` means "engine importable AND the online
    service is currently reachable". `installed` reports the package alone,
    so the two are never conflated. When the machine is offline the report
    says so instead of advertising a voice that cannot be produced.
    """

    installed = available()

    online = reachable() if installed else False

    return {
        "provider": PROVIDER,
        # engine usable RIGHT NOW (importable + reachable)
        "available": bool(installed and online),
        # the package alone, independent of connectivity
        "installed": installed,
        # OFFLINE_FIRST_V1 — truthful reachability, so the UI can degrade
        "reachable": online,
        "offline": bool(installed and not online),
        "voices": list(PERSIAN_VOICES),
        "default_voice": DEFAULT_VOICE,
        "online": True,
        "requires_api_key": False,
        "max_text_chars": MAX_TEXT_CHARS,
        # PERSIAN_VOICE_QUALITY_V2 / PHASE 3 — truth about the engine.
        "supports_ssml": False,
        "prepares_spoken_text": True,
    }


class PersianTTSV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    MODIFIES_STT = False
    MODIFIES_CHAT = False
    FALLS_BACK_TO_ENGLISH = False
    REQUIRES_API_KEY = False

    def synthesize(self, text, **kwargs):

        return synthesize(text, **kwargs)

    def available(self):

        return available()

    def voices(self):

        return voices()

    def describe(self):

        return describe()


persian_tts = PersianTTSV1()
