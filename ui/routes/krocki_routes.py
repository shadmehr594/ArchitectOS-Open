"""KROCKI_GATEWAY_V27_2 — proxy the land-survey upload to the Core API.

Why this file exists
--------------------
The browser talks to the UI gateway on :3000. The upload endpoint lives on the
Core API (:5000). Every other API surface is bridged by a blueprint
(`file_api`, `chat_api`, `project_api`, …) — the krocki upload was not, so
`POST http://127.0.0.1:3000/api/site/upload_krocki` had no route and answered
**404**, even though the Core API handled the same path correctly.

The proxy forwards the file verbatim and returns the Core API's body unchanged,
so the two surfaces cannot drift: there is one parser and one set of rules.
"""

from __future__ import annotations

import requests

from flask import Blueprint, jsonify, request

from config import runtime_config as RC


krocki_gateway = Blueprint("krocki_gateway", __name__)


CORE_UPLOAD_URL = RC.CORE_API_URL.rstrip("/") + "/api/site/upload_krocki"

CORE_STATE_URL = RC.CORE_API_URL.rstrip("/") + "/api/site/krocki"

#: A `.dwg` may need an AutoCAD conversion, which is slow on a cold start.
UPLOAD_TIMEOUT_SEC = 300


def _core_unreachable(exc: Exception):
    """A truthful 502: the gateway is up, the Core API is not answering."""

    return jsonify({
        "status": "error",
        "ok": False,
        "error": "core_api_unreachable",
        "message": (
            "سرور اصلی ArchitectOS (پورت %s) پاسخ نداد. "
            "ابتدا Core API را اجرا کنید." % (RC.CORE_API_PORT,)
        ),
        "detail": str(exc),
    }), 502


def _forward_files():
    """Rebuild the multipart body from ANY upload key the browser sent."""

    if not request.files:
        return None

    files = {}

    for key, storage in request.files.items():

        files[key] = (
            storage.filename,
            storage.stream,
            storage.content_type or "application/octet-stream",
        )

    return files


def v27_handle_krocki_upload():
    """POST /api/site/upload_krocki — forward to the Core API."""

    if request.method == "OPTIONS":

        return ("", 204)

    files = _forward_files()

    if not files:

        return jsonify({
            "status": "error",
            "ok": False,
            "error": "krocki_file_required",
            "message": "فایلی ارسال نشد. یک فایل .dxf یا .dwg انتخاب کنید.",
        }), 400

    data = {}

    for key in ("project_id", "session_id"):

        value = request.form.get(key) or request.args.get(key)

        if value:

            data[key] = value

    try:

        response = requests.post(
            CORE_UPLOAD_URL,
            files=files,
            data=data or None,
            timeout=UPLOAD_TIMEOUT_SEC,
        )

    except Exception as exc:  # noqa: BLE001

        return _core_unreachable(exc)

    payload = None

    try:

        payload = response.json()

    except ValueError:

        payload = None

    if not isinstance(payload, dict):

        return jsonify({
            "status": "error",
            "ok": False,
            "error": "core_api_bad_response",
            "message": "پاسخ سرور اصلی قابل خواندن نبود.",
            "core_status": response.status_code,
        }), 502

    # KROCKI_SITE_ALIAS_V27_2 — clients in the wild read either `krocki_info`
    # (the Core API's name) or `site`. Publish both so neither has to guess.
    if payload.get("krocki_info") and not payload.get("site"):

        payload["site"] = payload["krocki_info"]

    payload.setdefault("ok", payload.get("status") == "success")

    return jsonify(payload), response.status_code


def v27_handle_krocki_state():
    """GET/DELETE /api/site/krocki — read or clear the active survey."""

    if request.method == "OPTIONS":

        return ("", 204)

    params = {}

    for key in ("project_id", "session_id"):

        value = request.args.get(key) or request.form.get(key)

        if value:

            params[key] = value

    try:

        if request.method == "DELETE":

            response = requests.delete(
                CORE_STATE_URL, params=params, timeout=10800
            )

        else:

            response = requests.get(
                CORE_STATE_URL, params=params, timeout=10800
            )

    except Exception as exc:  # noqa: BLE001

        return _core_unreachable(exc)

    payload = None

    try:

        payload = response.json()

    except ValueError:

        payload = None

    if not isinstance(payload, dict):

        return jsonify({
            "status": "error",
            "ok": False,
            "error": "core_api_bad_response",
            "core_status": response.status_code,
        }), 502

    if payload.get("active_site_krocki") and not payload.get("site"):

        payload["site"] = payload["active_site_krocki"]

    payload.setdefault("ok", payload.get("status") == "success")

    return jsonify(payload), response.status_code
