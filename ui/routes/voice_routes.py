# ==========================================================
# ArchitectOS UI Voice Gateway v2
#
# VOICE_07 — canonical voice proxy
#
# The previous version built a SECOND ChatArchitect at UI import time
# (UIVoiceBridge → VoicePipeline → VoiceRuntimeBridge → AppBoot +
# ChatArchitect). That directly violated the product principle:
# voice must not become a separate assistant.
#
# These legacy routes are now a thin proxy to the canonical Core API
# voice surface, which uses the ONE ChatArchitect and the project
# session. No assistant is constructed here.
# ==========================================================


import requests

from flask import Blueprint, jsonify, request

from config import runtime_config as RC


voice_api = Blueprint(
    "voice_api",
    __name__,
    url_prefix="/voice"
)


def _core(path, method="GET", json_body=None, timeout=10800):

    url = RC.CORE_API_URL.rstrip("/") + path

    try:

        if method == "POST":

            response = requests.post(url, json=json_body or {}, timeout=timeout)

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

        payload = response.json()

    except Exception:

        payload = {"status": "error", "raw": response.text[:400]}

    return jsonify(payload), response.status_code


@voice_api.route("/status", methods=["GET"])
def voice_status():

    query = ""

    if request.args.get("project_id"):

        query = "?project_id=" + str(request.args.get("project_id"))

    return _core("/api/voice/status" + query)


@voice_api.route("/session", methods=["POST"])
def create_session():

    # Legacy route. Voice no longer owns a session: the project is the
    # session. Reported truthfully instead of creating a parallel one.
    return jsonify({
        "status": "deprecated",
        "message": (
            "Voice no longer creates its own session. "
            "Voice turns run inside the open project session."
        ),
        "canonical_endpoint": "/api/voice/turn",
        "separate_voice_session": False,
    }), 200


@voice_api.route("/message", methods=["POST"])
def send_message():

    # Legacy text-only voice route -> forwarded as a normal chat turn
    # so it can never diverge from the canonical path.
    data = request.get_json(silent=True) or {}

    text = data.get("text")

    if not text:

        return jsonify({"error": "text required"}), 400

    return _core("/api/chat", method="POST", json_body={
        "text": text,
        "project_id": data.get("project_id"),
        "mode": data.get("mode"),
        "quality": data.get("quality"),
    })


@voice_api.route("/close", methods=["POST"])
def close_session():

    return jsonify({
        "status": "deprecated",
        "message": "Voice has no separate session to close.",
        "separate_voice_session": False,
    }), 200
