# ==========================================================
# ArchitectOS Voice API v1
#
# VOICE_07 — HTTP surface for the optional voice modality.
#
# The blueprint receives the SHARED dependencies from app.py so the
# voice path uses the one canonical ChatArchitect and the one project
# session. It never builds its own assistant.
# ==========================================================


from __future__ import annotations


import os
import time

from flask import Blueprint, jsonify, make_response, request


from core.voice.voice_session_bridge_v1 import VoiceSessionBridge

# PERSIAN_TTS_V1 — server-side Persian speech (no API key, online engine).
# It is used ONLY for Persian text; English keeps the browser voice path.
from core.voice.persian_tts_v1 import persian_tts


CONTRACT = "VoiceApiV1"
VERSION = "1.0"


def create_voice_blueprint(
    chat,
    response_adapter,
    project_session,
    project_workspace,
):

    bridge = VoiceSessionBridge(
        chat=chat,
        response_adapter=response_adapter,
        project_session=project_session,
        project_workspace=project_workspace,
    )

    voice_api = Blueprint("voice_canonical_api", __name__)

    # ======================================================
    # STATUS / CAPABILITY
    # ======================================================

    @voice_api.route("/api/voice/status", methods=["GET"])
    def voice_status():

        project_id = request.args.get("project_id")

        return jsonify({
            "status": "success",
            **bridge.status(project_id),
        })

    # ======================================================
    # PERSIAN TTS  (PERSIAN_TTS_V1)
    #
    # Server-side Persian speech, because this machine has NO Persian
    # voice in either Windows store (SAPI5 / OneCore) and
    # `window.speechSynthesis` only ever sees the LOCAL OneCore voices.
    #
    # English is NOT routed here: the browser's own speechSynthesis keeps
    # handling English exactly as before. This endpoint returns audio for
    # PERSIAN text only, and reports a truthful error otherwise.
    # ======================================================

    @voice_api.route("/api/voice/speak", methods=["POST"])
    def voice_speak():

        payload = request.get_json(silent=True) or {}

        text = (payload.get("text") or request.form.get("text") or "").strip()

        if not text:

            return jsonify({
                "status": "error",
                "error": "empty_text",
            }), 400

        # PERSIAN_OUTPUT_ORTHOGRAPHY_V1 / PART B — honour an EXPLICIT
        # voice request so the two Persian engines can be compared with
        # identical sentences. This does NOT change the default: when the
        # caller sends no voice (the normal browser path), `synthesize`
        # keeps using the configured default (fa-IR-DilaraNeural). The
        # value is validated inside `synthesize`, so an unknown name
        # falls back to the default rather than failing.
        requested_voice = (
            payload.get("voice")
            or request.form.get("voice")
            or None
        )

        if requested_voice in (None, "", "auto"):

            requested_voice = None

        result = persian_tts.synthesize(text, voice=requested_voice)

        if result.get("status") != "ok":

            return jsonify({
                "status": "error",
                "error": result.get("reason"),
                "message": _tts_message(result.get("reason")),
                "provider": result.get("provider"),
                "voice": result.get("voice"),
            }), 200

        response = make_response(result["audio"])

        response.headers["Content-Type"] = result["content_type"]

        response.headers["X-TTS-Provider"] = str(result.get("provider"))

        response.headers["X-TTS-Voice"] = str(result.get("voice"))

        response.headers["Cache-Control"] = "no-store"

        return response

    # ======================================================
    # TRANSCRIBE ONLY
    # ======================================================

    @voice_api.route("/api/voice/transcribe", methods=["POST"])
    def voice_transcribe():

        audio = request.files.get("audio") or request.files.get("file")

        if not audio:

            return jsonify({
                "status": "failed",
                "reason": "no_audio_received",
                "transcript": None,
                "confidence": None,
            }), 400

        language = (
            request.form.get("language")
            or request.args.get("language")
            or "auto"
        )

        project_id = (
            request.form.get("project_id")
            or request.args.get("project_id")
        )

        started = time.time()

        stored = bridge.store_audio(
            project_id,
            audio,
            extension=_extension_for(audio.filename),
        )

        path = (stored or {}).get("path")

        if not path:

            return jsonify({
                "status": "failed",
                "reason": "audio_store_failed",
                "transcript": None,
                "confidence": None,
            }), 500

        result = bridge.transcribe(path, language=language)

        result["audio"] = {
            "filename": (stored or {}).get("filename"),
            "size_bytes": (stored or {}).get("size_bytes"),
        }

        result["bridge_total_seconds"] = round(time.time() - started, 3)

        code = 200 if result.get("status") == "ok" else 200

        return jsonify(result), code

    # ======================================================
    # CANONICAL VOICE TURN
    # ======================================================

    @voice_api.route("/api/voice/turn", methods=["POST"])
    def voice_turn():

        audio = request.files.get("audio") or request.files.get("file")

        if not audio:

            return jsonify({
                "status": "error",
                "error": "no_audio_received",
                "message": "No audio was received.",
            }), 400

        form = request.form

        project_id = form.get("project_id")

        language = form.get("language") or "auto"

        started = time.time()

        stored = bridge.store_audio(
            project_id,
            audio,
            extension=_extension_for(audio.filename),
        )

        path = (stored or {}).get("path")

        if not path:

            return jsonify({
                "status": "error",
                "error": "audio_store_failed",
            }), 500

        upload_seconds = round(time.time() - started, 3)

        stt_started = time.time()

        stt = bridge.transcribe(path, language=language)

        stt_seconds = round(time.time() - stt_started, 3)

        # ---- truthful STT failure: never guess text ----
        if stt.get("status") != "ok":

            return jsonify({

                "status": "error",

                "error": stt.get("reason") or "stt_failed",

                "message": _stt_message(stt, language),

                "stt": stt,

                "input_type": "voice",

                "transcript": None,

                "timing": {
                    "upload_seconds": upload_seconds,
                    "stt_seconds": stt_seconds,
                },
            }), 200

        turn_started = time.time()

        turn = bridge.run_turn(

            stt.get("transcript"),

            project_id=project_id,

            mode=form.get("mode"),

            quality=form.get("quality") or form.get("render_profile"),

            seed_mode=form.get("seed_mode"),

            seed_value=form.get("seed_value"),

            language=language,

            voice_meta={
                "audio_filename": (stored or {}).get("filename"),
                "audio_bytes": (stored or {}).get("size_bytes"),
                "audio_duration": stt.get("duration"),
                "detected_language": stt.get("detected_language"),
                "stt_provider": stt.get("provider"),
                "stt_model": stt.get("model"),
                "stt_confidence": stt.get("confidence"),
                # Truthful STT preprocessing provenance (the original
                # recording is always preserved untouched).
                "audio_preprocessing": stt.get("audio_preprocessing"),
            },
        )

        turn_seconds = round(time.time() - turn_started, 3)

        turn["stt"] = stt

        turn["input_type"] = "voice"

        turn["timing"] = {
            "upload_seconds": upload_seconds,
            "stt_seconds": stt_seconds,
            "chat_seconds": (turn.get("timing") or {}).get("chat_seconds"),
            "turn_seconds": turn_seconds,
            "total_seconds": round(time.time() - started, 3),
        }

        return jsonify(turn)

    # ======================================================
    # TURN FROM TRANSCRIPT  (STT explicitly bypassed)
    #
    # Runs a VOICE turn from a transcript that did not come from the
    # microphone. Used by acceptance when real speech audio cannot be
    # produced on this machine (no Persian TTS voice), and useful for
    # support/debugging. It is ALWAYS labelled `stt_bypassed: true` so
    # it can never be mistaken for real speech recognition.
    # ======================================================

    @voice_api.route("/api/voice/inject", methods=["POST"])
    def voice_inject():

        data = request.get_json(silent=True) or {}

        transcript = data.get("transcript")

        if not transcript:

            return jsonify({
                "status": "error",
                "error": "transcript_required",
            }), 400

        turn = bridge.run_turn(

            transcript,

            project_id=data.get("project_id"),

            mode=data.get("mode"),

            quality=data.get("quality"),

            seed_mode=data.get("seed_mode"),

            seed_value=data.get("seed_value"),

            voice_meta={
                "stt_bypassed": True,
                "stt_provider": None,
                "source": "injected_transcript",
            },
        )

        turn["input_type"] = "voice"
        turn["stt_bypassed"] = True
        turn["stt"] = {
            "status": "bypassed",
            "reason": "injected_transcript",
            "transcript": transcript,
            "detected_language": None,
            "provider": None,
            "confidence": None,
        }

        return jsonify(turn)

    # ======================================================
    # DRY-RUN ROUTING (no execution)
    # ======================================================

    @voice_api.route("/api/voice/dry-run", methods=["POST"])
    def voice_dry_run():

        data = request.get_json(silent=True) or {}

        transcript = data.get("transcript")

        if not transcript:

            return jsonify({
                "status": "error",
                "error": "transcript_required",
            }), 400

        return jsonify(bridge.dry_run_routing(
            transcript,
            mode=data.get("mode"),
            quality=data.get("quality"),
        ))

    # ======================================================
    # SETTINGS
    # ======================================================

    @voice_api.route("/api/voice/settings", methods=["GET", "POST"])
    def voice_settings():

        if request.method == "POST":

            data = request.get_json(silent=True) or {}

            saved = bridge.save_settings(
                data.get("project_id"),
                data,
            )

            return jsonify({
                "status": "success",
                "settings": saved,
            })

        return jsonify({
            "status": "success",
            "settings": bridge.settings(request.args.get("project_id")),
        })

    return voice_api, bridge


# ==========================================================
# HELPERS
# ==========================================================

def _extension_for(filename):

    extension = os.path.splitext(str(filename or ""))[1].lower()

    allowed = (
        ".wav", ".webm", ".ogg", ".oga", ".mp3", ".m4a", ".mp4", ".flac",
    )

    return extension if extension in allowed else ".webm"


def _tts_message(reason):
    """Truthful, human Persian text for a Persian-TTS failure.

    Nothing here ever claims speech was produced.
    """

    messages = {
        "empty_text": "متنی برای خواندن وجود نداشت.",
        "not_persian_text": "این مسیر فقط برای متن فارسی است.",
        "tts_engine_unavailable": "موتور صدای فارسی روی این دستگاه در دسترس نیست.",
        "synthesis_failed": "ساخت صدای فارسی ناموفق بود.",
        "empty_audio": "صدای فارسی تولید نشد.",
    }

    return messages.get(reason) or "صدای فارسی تولید نشد."


def _stt_message(stt, language="auto"):

    reason = stt.get("reason")

    persian = str(language or "").lower().startswith("fa")

    if reason == "empty_transcript":

        if persian:

            return "صدایی شنیده نشد؛ لطفاً دوباره بگویید."

        return "I did not catch any speech. Please try again."

    if reason in ("unusable_transcript", "repetition_detected",
                  "prompt_echo_detected", "script_mismatch_detected",
                  "low_confidence_detected"):

        # Truthful quality gate: the decode was not reliable enough to
        # send to the assistant. The raw transcript is kept in the
        # response for diagnostics but is never treated as the user's
        # words.
        if persian:

            return "صدای شما واضح تشخیص داده نشد؛ لطفاً دوباره بگویید."

        return ("I could not recognise that clearly. "
                "Please say it again.")

    if reason == "no_speech_detected":

        # The window held no real speech (a short hallucination such as a
        # single stray word). This is "nothing was said", not "speak more
        # clearly".
        if persian:

            return "صدایی شنیده نشد؛ لطفاً دوباره بگویید."

        return "I did not catch any speech. Please try again."

    if reason == "empty_recording":

        if persian:

            return "ضبط خالی بود؛ لطفاً دوباره بگویید."

        return "The recording was empty. Please try again."

    if reason in ("stt_provider_unavailable", "stt_model_unavailable"):

        if persian:

            return "تشخیص گفتار روی این دستگاه در دسترس نیست."

        return "Speech recognition is unavailable on this machine."

    if reason == "stt_timeout":

        if persian:

            return "تشخیص گفتار زمان‌بر شد؛ لطفاً دوباره بگویید."

        return "Speech recognition timed out. Please try again."

    if reason == "unsupported_audio_format":

        if persian:

            return "این قالب صوتی پشتیبانی نمی‌شود."

        return "That audio format is not supported."

    if persian:

        return "تشخیص گفتار ناموفق بود؛ لطفاً دوباره بگویید."

    return "Speech recognition failed: " + str(reason or "unknown")
