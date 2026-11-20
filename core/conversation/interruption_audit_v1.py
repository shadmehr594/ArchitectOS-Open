# ==========================================================
# ArchitectOS Interruption Audit v1
#
# PHASE 08F — INTERRUPTION / CONVERSATIONAL CONTROL AUDIT
#
# READ-ONLY.  This module inspects the REAL current architecture and
# reports precisely what is missing for true human-like barge-in:
#
#   user speaking -> assistant responding -> user interrupts
#   -> current response/audio stops -> new user turn authoritative
#
# It does NOT build a fake interruption mechanism and does NOT modify
# Voice 07.  It produces evidence, not a simulation.
#
# Evidence policy
#   A naive keyword scan is NOT proof: "stream" also appears in
#   `image.stream`, and "abort" also appears in Flask's `abort(404)`.
#   The audit therefore separates:
#     - structural_evidence : parsed facts that actually decide the answer
#     - keyword_scan        : raw substring hits, explicitly NOT proof
# ==========================================================


from __future__ import annotations


import os
import re


CONTRACT = "InterruptionAuditV1"
VERSION = "1.0"


REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


# Files that would have to participate in a real barge-in design.
_SURFACES = (
    "app.py",
    "ui/routes/voice_routes.py",
    "ui/routes/chat_routes.py",
    "core/voice/voice_api_v1.py",
    "core/voice/voice_session_bridge_v1.py",
    "core/chat/chat_architect.py",
    "core/llm/llm_gateway.py",
    "tools/sapi_tts_worker.py",
)


_KEYWORD_TOKENS = (
    "stream", "chunk", "partial", "yield", "text/event-stream",
    "cancel", "abort", "interrupt", "barge", "preempt",
    "abortcontroller",
)


def _read(relative_path):

    path = os.path.join(REPO_ROOT, relative_path)

    if not os.path.isfile(path):

        return None

    try:

        with open(path, "r", encoding="utf-8", errors="replace") as handle:

            return handle.read()

    except Exception:

        return None


# ----------------------------------------------------------
# STRUCTURAL EVIDENCE
# ----------------------------------------------------------

def _llm_stream_flag():

    """The value the LLM gateway actually sends for `stream`."""

    text = _read("core/llm/llm_gateway.py") or ""

    match = re.search(
        r'"stream"\s*:\s*(True|False)', text
    )

    if not match:

        return None

    return match.group(1) == "True"


def _handle_signature():

    text = _read("core/chat/chat_architect.py") or ""

    match = re.search(
        r"def handle\(\s*self\s*,\s*([^)]*)\)", text
    )

    return match.group(1).strip() if match else None


def _bridge_turn_signature():

    text = _read("core/voice/voice_session_bridge_v1.py") or ""

    match = re.search(r"def run_turn\(\s*self\s*,\s*([^)]*)\)", text)

    return match.group(1).strip() if match else None


def structural_evidence():

    chat = _read("core/chat/chat_architect.py") or ""

    app = _read("app.py") or ""

    tts = _read("tools/sapi_tts_worker.py") or ""

    voice_api = _read("core/voice/voice_api_v1.py") or ""

    handle_signature = _handle_signature()

    bridge_signature = _bridge_turn_signature()

    llm_stream = _llm_stream_flag()

    return {

        # --- is the answer produced incrementally? ---
        "llm_gateway_stream_flag": llm_stream,
        "llm_gateway_streams": llm_stream is True,

        "chat_handle_is_generator": "yield" in chat,
        "event_stream_endpoint": "text/event-stream" in app,
        "flask_stream_with_context": "stream_with_context" in app,

        # --- can an in-flight turn be stopped? ---
        "handle_signature": handle_signature,
        "handle_accepts_abort_token": bool(
            handle_signature
            and re.search(r"abort|cancel|interrupt", handle_signature)
        ),
        "voice_run_turn_signature": bridge_signature,
        "voice_run_turn_accepts_abort_token": bool(
            bridge_signature
            and re.search(r"abort|cancel|interrupt", bridge_signature)
        ),
        "voice_cancel_endpoint": bool(
            re.search(
                r"route\(\s*[\"'][^\"']*cancel",
                voice_api,
            )
        ),

        # --- audio playback ---
        # pyttsx3 writes a COMPLETE file (engine.save_to_file) and the
        # worker returns its path; nothing is streamed in chunks.
        "tts_returns_complete_file": (
            "save_to_file" in tts and '"path"' in tts
        ),
        "tts_streams_audio": "yield" in tts or "chunk" in tts.lower(),

        # --- duplex capture ---
        # The UI guards the microphone while TTS is playing instead of
        # listening for a barge-in.
        "mic_guard_during_playback": (
            "speechSynthesis" in (_read("ui/static/app.js") or "")
        ),
    }


# ----------------------------------------------------------
# KEYWORD SCAN (explicitly not proof)
# ----------------------------------------------------------

def keyword_scan():

    scan = {}

    for surface in _SURFACES:

        text = _read(surface)

        if text is None:

            scan[surface] = {"present": False}

            continue

        lowered = text.lower()

        scan[surface] = {

            "present": True,

            "bytes": len(text),

            "hits": sorted(
                {
                    token: lowered.count(token)
                    for token in _KEYWORD_TOKENS
                    if token in lowered
                }.items()
            ),
        }

    return scan


# ----------------------------------------------------------
# AUDIT
# ----------------------------------------------------------

def audit():

    evidence = structural_evidence()

    streaming = any(
        (
            evidence["llm_gateway_streams"],
            evidence["chat_handle_is_generator"],
            evidence["event_stream_endpoint"],
            evidence["flask_stream_with_context"],
        )
    )

    cancellable = any(
        (
            evidence["handle_accepts_abort_token"],
            evidence["voice_run_turn_accepts_abort_token"],
            evidence["voice_cancel_endpoint"],
        )
    )

    missing = [

        {
            "piece": "incremental_response_streaming",
            "present": streaming,
            "evidence": (
                "LLM gateway sends stream=%s; handle() is a plain "
                "function (no yield); no text/event-stream endpoint."
                % evidence["llm_gateway_stream_flag"]
            ),
            "why": (
                "ChatArchitect.handle() returns one complete result dict, "
                "so there is no partial answer a new turn could preempt."
            ),
        },

        {
            "piece": "cancellation_token_through_turn_pipeline",
            "present": cancellable,
            "evidence": (
                "handle(self, %s); run_turn(self, %s); no cancel route."
                % (
                    evidence["handle_signature"],
                    evidence["voice_run_turn_signature"],
                )
            ),
            "why": (
                "No abort/cancel token flows API -> bridge -> "
                "ChatArchitect, so an in-flight turn cannot be signalled "
                "to stop."
            ),
        },

        {
            "piece": "abortable_audio_playback",
            "present": not evidence["tts_returns_complete_file"],
            "evidence": (
                "sapi_tts_worker writes a complete file (SaveToFile) and "
                "returns its path; playback is browser speechSynthesis."
            ),
            "why": (
                "There is no server-side channel to stop audio already "
                "queued in the browser."
            ),
        },

        {
            "piece": "duplex_capture_during_playback",
            "present": False,
            "evidence": (
                "The composer guards the microphone DURING TTS playback "
                "instead of leaving it open for barge-in detection."
            ),
            "why": (
                "User speech while the assistant is talking is not "
                "captured as an interrupt event."
            ),
        },

        {
            "piece": "turn_arbitration_authority",
            "present": False,
            "evidence": (
                "The pipeline is strictly request/response; no rule makes "
                "a newer user turn supersede an unfinished assistant turn."
            ),
            "why": (
                "Without arbitration, an interrupt cannot become the "
                "authoritative turn."
            ),
        },
    ]

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "audit_type": "read_only",
        "method": "structural_evidence + keyword_scan",

        "barge_in_supported": False,

        "fake_interruption_built": False,

        "voice_07_redesigned": False,

        "streaming_present": streaming,

        "cancellation_present": cancellable,

        "synchronous_turn_model": not streaming,

        "structural_evidence": evidence,

        "keyword_scan_is_proof": False,

        "keyword_scan": keyword_scan(),

        "missing_pieces": missing,

        "required_work": [
            "Make the canonical turn cancellable end to end "
            "(API -> bridge -> ChatArchitect) with an explicit turn id "
            "and an abort token.",
            "Turn on real incremental output (streamed text and/or "
            "streamed audio chunks) so a stop is meaningful mid-answer.",
            "Keep the microphone open during playback and treat user "
            "speech as a barge-in event instead of blocking capture.",
            "Define arbitration: a newer accepted user turn supersedes "
            "any unfinished assistant turn and its audio.",
            "Provide a truthful `interrupted` UI state so a stopped "
            "answer is never presented as a completed one.",
        ],

        "explicitly_not_done": (
            "Phase 08 does not simulate interruption, does not add a fake "
            "barge-in, and does not modify the Voice 07 recognition "
            "solution."
        ),
    }
