# ==========================================================
# ArchitectOS UI Voice Gateway v3
#
# VOICE_07 — canonical voice proxy under /api/voice/*
#
# The workspace client talks to /api/voice/*. Those requests must reach
# the Core API's canonical voice surface, which uses the ONE
# ChatArchitect and the project session. Nothing is constructed here.
# ==========================================================


import requests

from flask import Blueprint, Response, jsonify, request

from config import runtime_config as RC


voice_gateway = Blueprint(
    "ui_voice_gateway",
    __name__
)


def _core_json(path, method="GET", payload=None, timeout=10800):

    url = RC.CORE_API_URL.rstrip("/") + path

    try:

        if method == "POST":

            response = requests.post(url, json=payload or {}, timeout=timeout)

        else:

            response = requests.get(url, timeout=timeout)

    except requests.exceptions.ConnectionError as error:

        return jsonify({
            "status": "error",
            "message": "Core API connection error: " + str(error),
        }), 502

    except requests.exceptions.Timeout:

        return jsonify({
            "status": "error",
            "message": "Core API timeout",
        }), 504

    try:

        return jsonify(response.json()), response.status_code

    except Exception:

        return jsonify({
            "status": "error",
            "raw": response.text[:400],
        }), response.status_code


def _forward_audio(path, timeout=10800):

    audio = request.files.get("audio") or request.files.get("file")

    if not audio:

        return jsonify({
            "status": "error",
            "error": "no_audio_received",
            "message": "No audio was received.",
        }), 400

    files = {
        "audio": (
            audio.filename or "voice.webm",
            audio.stream,
            audio.content_type or "audio/webm",
        )
    }

    data = {
        key: value
        for key, value in request.form.items()
        if value not in (None, "")
    }

    url = RC.CORE_API_URL.rstrip("/") + path

    try:

        response = requests.post(
            url, files=files, data=data, timeout=timeout
        )

    except requests.exceptions.ConnectionError as error:

        return jsonify({
            "status": "error",
            "error": "backend_offline",
            "message": "Core API connection error: " + str(error),
        }), 502

    except requests.exceptions.Timeout:

        return jsonify({
            "status": "error",
            "error": "backend_timeout",
            "message": "The voice request timed out.",
        }), 504

    try:

        return jsonify(response.json()), response.status_code

    except Exception:

        return jsonify({
            "status": "error",
            "error": "invalid_backend_response",
            "raw": response.text[:400],
        }), 502


def _forward_audio_bytes(path, payload, timeout=10800):

    """PERSIAN_TTS_V1 — proxy a route whose SUCCESS body is BINARY audio.

    `_core_json()` cannot be used here: it calls `jsonify(response.json())`,
    which would destroy an MP3 body. This forwards the raw bytes and keeps
    the backend's Content-Type / X-TTS-* headers and status code.

    A non-audio backend response (e.g. a truthful JSON error) is passed
    through unchanged so the client still gets the real reason.
    """

    url = RC.CORE_API_URL.rstrip("/") + path

    try:

        response = requests.post(
            url,
            json=payload or {},
            timeout=timeout,
        )

    except requests.exceptions.ConnectionError as error:

        return jsonify({
            "status": "error",
            "error": "backend_offline",
            "message": "Core API connection error: " + str(error),
        }), 502

    except requests.exceptions.Timeout:

        return jsonify({
            "status": "error",
            "error": "backend_timeout",
            "message": "The speech request timed out.",
        }), 504

    content_type = response.headers.get("Content-Type", "")

    # A non-audio body is a truthful JSON error — keep it intact.
    if not content_type.lower().startswith("audio"):

        try:

            return jsonify(response.json()), response.status_code

        except Exception:

            return jsonify({
                "status": "error",
                "error": "invalid_backend_response",
                "raw": response.text[:400],
            }), 502

    forwarded = Response(
        response.content,
        status=response.status_code,
        content_type=content_type,
    )

    # Preserve the truthful provenance headers the core sets.
    for header in ("X-TTS-Provider", "X-TTS-Voice", "Cache-Control"):

        value = response.headers.get(header)

        if value is not None:

            forwarded.headers[header] = value

    return forwarded


# ==========================================================
# STATUS / SETTINGS
# ==========================================================

@voice_gateway.route("/api/voice/status", methods=["GET"])
def voice_status():

    query = ""

    if request.args.get("project_id"):

        query = "?project_id=" + str(request.args.get("project_id"))

    return _core_json("/api/voice/status" + query)


@voice_gateway.route("/api/voice/settings", methods=["GET", "POST"])
def voice_settings():

    if request.method == "POST":

        return _core_json(
            "/api/voice/settings",
            method="POST",
            payload=request.get_json(silent=True) or {},
        )

    query = ""

    if request.args.get("project_id"):

        query = "?project_id=" + str(request.args.get("project_id"))

    return _core_json("/api/voice/settings" + query)


# ==========================================================
# AUDIO
# ==========================================================

@voice_gateway.route("/api/voice/turn", methods=["POST"])
def voice_turn():

    return _forward_audio("/api/voice/turn")


@voice_gateway.route("/api/voice/transcribe", methods=["POST"])
def voice_transcribe():

    return _forward_audio("/api/voice/transcribe")


@voice_gateway.route("/api/voice/speak", methods=["POST"])
def voice_speak():

    """PERSIAN_TTS_V1 — server-side Persian speech (binary audio).

    The browser's `speakPersianViaServer()` posts here on the UI origin.
    The success body is an MP3, so it is forwarded as raw bytes (never
    JSON). English is unaffected: it never calls this route.
    """

    return _forward_audio_bytes(
        "/api/voice/speak",
        request.get_json(silent=True) or {},
    )


# ==========================================================
# TEXT / ROUTING
# ==========================================================

@voice_gateway.route("/api/voice/inject", methods=["POST"])
def voice_inject():

    return _core_json(
        "/api/voice/inject",
        method="POST",
        payload=request.get_json(silent=True) or {},
    )


@voice_gateway.route("/api/voice/dry-run", methods=["POST"])
def voice_dry_run():

    return _core_json(
        "/api/voice/dry-run",
        method="POST",
        payload=request.get_json(silent=True) or {},
    )
