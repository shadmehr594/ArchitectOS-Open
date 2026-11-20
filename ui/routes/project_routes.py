# ==========================================================
# ArchitectOS UI Project Gateway v1
#
# PROJECT_WORKSPACE_UI_06
#
# Thin proxy from the UI server to the Core API project surface.
# The Core API URL comes from runtime_config — never hardcoded.
# ==========================================================


import os

import requests

from flask import Blueprint, jsonify, request, session

from config import runtime_config as RC

from core.runtime.local_authorization_v1 import sign_proxy_request


project_api = Blueprint(
    "ui_project_api",
    __name__
)


def _trusted_read_headers(path):
    """Sign one trusted-local READ request from the launcher UI session.

    MATERIAL_REVIEW_UI_SECURITY_ACCEPTANCE_V1 — this is the SAME accepted
    CODER-05.2 signing contract `/api/chat` already uses, not a second
    authentication scheme.  A GET has no body, so the signed payload is
    empty and the signed path is the Core path being read.

    Returns {} when this browser session was not bootstrapped by the
    launcher, or when no usable secret is present.  The Core then
    withholds the material-review projection — the safe direction.
    """

    if not session.get("trusted_local"):

        return {}

    secret = os.environ.get("ARCHITECTOS_LOCAL_PROXY_SECRET", "")

    if len(secret) < 32:

        return {}

    try:

        return sign_proxy_request(
            secret,
            actor_id=session.get("actor_id"),
            session_id=session.get("local_session_id"),
            payload={},
            path=path,
        )

    except Exception:

        return {}


def _core(path, method="GET", json_body=None, timeout=10800, headers=None):

    url = RC.CORE_API_URL.rstrip("/") + path

    try:

        if method == "POST":

            response = requests.post(
                url, json=json_body or {}, timeout=timeout,
                headers=headers or None,
            )

        else:

            response = requests.get(
                url, timeout=timeout, headers=headers or None
            )

    except requests.exceptions.Timeout:

        return jsonify({
            "status": "error",
            "message": "Core API timeout",
        }), 504

    except requests.exceptions.ConnectionError as error:

        return jsonify({
            "status": "error",
            "message": "Core API connection error: " + str(error),
        }), 502

    try:

        payload = response.json()

    except Exception:

        payload = {
            "status": "error",
            "raw": response.text[:500],
        }

    return jsonify(payload), response.status_code


# ==========================================================
# CATALOG
# ==========================================================

@project_api.route("/api/render/modes", methods=["GET"])
def render_modes():

    return _core("/api/render/modes")


@project_api.route("/api/render/strategy", methods=["POST"])
def render_strategy():

    return _core(
        "/api/render/strategy",
        method="POST",
        json_body=request.get_json(silent=True) or {},
    )


# ==========================================================
# PROJECTS
# ==========================================================

@project_api.route("/api/projects", methods=["GET", "POST"])
def projects():

    if request.method == "POST":

        return _core(
            "/api/projects",
            method="POST",
            json_body=request.get_json(silent=True) or {},
        )

    query = ""

    if request.args.get("limit"):

        query = "?limit=" + str(request.args.get("limit"))

    return _core("/api/projects" + query)


@project_api.route("/api/projects/<project_id>", methods=["GET"])
def project_detail(project_id):

    # MATERIAL_REVIEW_UI_SECURITY_ACCEPTANCE_V1 — the Core emits the
    # material-review projection only for a signed trusted-local read.
    path = "/api/projects/" + project_id

    return _core(path, headers=_trusted_read_headers(path))


@project_api.route(
    "/api/projects/<project_id>/<action>",
    methods=["GET", "POST"]
)
def project_action(project_id, action):

    allowed = (
        "open",
        "close",
        "rename",
        "archive",
        "restore",
        "delete",
        "export",
        "save",
        "save-state",
        "ui",
        "assets",
        "storage",
    )

    if action not in allowed:

        return jsonify({
            "status": "error",
            "error": "unsupported_action",
            "action": action,
        }), 400

    method = "GET" if action in ("save-state", "assets", "storage") else "POST"

    body = request.get_json(silent=True) or {}

    if method == "GET" and request.args:

        body = dict(request.args)

    query = ""

    if action == "assets" and request.args.get("filter"):

        query = "?filter=" + str(request.args.get("filter"))

    return _core(
        "/api/projects/" + project_id + "/" + action + query,
        method=method,
        json_body=body,
    )


@project_api.route(
    "/api/projects/<project_id>/assets/<asset_id>",
    methods=["GET"]
)
def asset_detail(project_id, asset_id):

    return _core(
        "/api/projects/" + project_id + "/assets/" + asset_id
    )


@project_api.route(
    "/api/projects/<project_id>/assets/<asset_id>/<action>",
    methods=["POST", "GET"]
)
def asset_action(project_id, asset_id, action):

    allowed = ("active", "final", "lineage")

    if action not in allowed:

        return jsonify({
            "status": "error",
            "error": "unsupported_action",
            "action": action,
        }), 400

    method = "GET" if action == "lineage" else "POST"

    return _core(
        "/api/projects/" + project_id + "/assets/" + asset_id + "/" + action,
        method=method,
        json_body=request.get_json(silent=True) or {},
    )
