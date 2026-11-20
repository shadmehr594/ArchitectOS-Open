# ==========================================================
# ArchitectOS UI Chat Gateway v2
# UI Network Gateway -> Core API
# ==========================================================

from flask import Blueprint, request, jsonify, session
import requests
import os
import threading

# PROJECT_WORKSPACE_UI_06 — single source of truth for the Core API URL.
# Never hardcode hosts/ports (RUNTIME_FOUNDATION_01).
from config import runtime_config as RC


chat_api = Blueprint(
    "chat_api",
    __name__
)


CORE_API = RC.CORE_API_URL.rstrip("/") + "/chat"

_APPROVAL_CAPABILITIES = {}
_APPROVAL_LOCK = threading.Lock()


def _trusted_proxy_headers(payload, path="/chat"):
    """Sign only a same-origin request in a launcher-bootstrapped session."""
    from core.runtime.local_authorization_v1 import (
        sign_proxy_request, ui_request_is_trusted_origin,
    )

    if not session.get("trusted_local"):
        return {}
    if not ui_request_is_trusted_origin(
        request.headers.get("Origin"), request.host, request.remote_addr, RC.UI_URL
    ):
        return {}
    secret = os.environ.get("ARCHITECTOS_LOCAL_PROXY_SECRET", "")
    if len(secret) < 32:
        return {}
    return sign_proxy_request(
        secret,
        actor_id=session.get("actor_id"),
        session_id=session.get("local_session_id"),
        payload=payload,
        path=path,
    )


def _inject_private_capability(payload):
    """Keep approval secrets server-side and bind lookup to session+project."""
    data = dict(payload or {})
    key = (session.get("local_session_id"), str(data.get("project_id") or ""))
    with _APPROVAL_LOCK:
        token = _APPROVAL_CAPABILITIES.get(key)
    if token:
        data["approval_capability"] = token
    return data


def _capture_private_capability(payload, project_id):
    if not isinstance(payload, dict):
        return
    response = payload.get("response")
    capability = response.get("code_approval") if isinstance(response, dict) else None
    key = (session.get("local_session_id"), str(project_id or ""))
    with _APPROVAL_LOCK:
        if isinstance(capability, dict) and capability.get("token"):
            _APPROVAL_CAPABILITIES[key] = capability["token"]
        elif isinstance(capability, dict) and capability.get("pending") is False:
            _APPROVAL_CAPABILITIES.pop(key, None)
    if isinstance(response, dict):
        response.pop("code_approval", None)


def _proxy_coder_execution(path, payload, timeout):
    """Forward one strict trusted-local coder action; never expose tokens."""
    headers = _trusted_proxy_headers(payload, path=path)
    if not headers:
        return jsonify({
            "ok": False,
            "reason": "trusted_local_session_required",
        }), 403
    try:
        response = requests.post(
            RC.CORE_API_URL.rstrip("/") + path,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        try:
            result = response.json()
        except Exception:
            result = {"ok": False, "reason": "invalid_core_json"}
        # Raw execute capabilities are server-custodied. Any regression that
        # puts one in a Core response is blocked at this second process edge.
        if _contains_execution_secret(result):
            return jsonify({
                "ok": False,
                "reason": "execution_secret_transport_refused",
            }), 502
        return jsonify(result), response.status_code
    except requests.exceptions.Timeout:
        return jsonify({"ok": False, "reason": "core_timeout"}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"ok": False, "reason": "core_unreachable"}), 502


def _contains_execution_secret(value):
    """Fail closed if a raw capability appears anywhere in a Core reply."""
    if isinstance(value, dict):
        for key, item in value.items():
            if "token" in str(key).lower() or _contains_execution_secret(item):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_contains_execution_secret(item) for item in value)
    return isinstance(value, str) and value.startswith("exc_")


@chat_api.route("/api/coder/execution/preview", methods=["POST"])
def coder_execution_preview_proxy():
    data = request.get_json(silent=True) or {}
    if set(data) != {"project_id", "filename"}:
        return jsonify({"ok": False, "reason": "execution_preview_payload_invalid"}), 400
    payload = {
        "operation": "prepare_execution_preview",
        "project_id": str(data.get("project_id") or ""),
        "filename": str(data.get("filename") or ""),
    }
    return _proxy_coder_execution(
        "/api/coder/execution/preview", payload, timeout=10800)


@chat_api.route("/api/coder/execution/consent", methods=["POST"])
def coder_execution_consent_proxy():
    data = request.get_json(silent=True) or {}
    expected = {
        "project_id", "proposal_id", "filename", "source_sha256",
        "confirm_run",
    }
    if set(data) != expected or data.get("confirm_run") is not True:
        return jsonify({"ok": False, "reason": "explicit_run_confirmation_required"}), 400
    # The browser supplies only the preview identifiers it visibly confirmed.
    # The UI server owns the fixed action/scope/consent fields that are signed.
    payload = {
        "operation": "approve_and_run_python",
        "project_id": str(data.get("project_id") or ""),
        "proposal_id": str(data.get("proposal_id") or ""),
        "filename": str(data.get("filename") or ""),
        "source_sha256": str(data.get("source_sha256") or ""),
        "action": "run_python",
        "scope": "execute",
        "consent": True,
    }
    return _proxy_coder_execution(
        "/api/coder/execution/consent", payload, timeout=10800)


# ==========================================================
# CODER — UNSAVED DRAFT VERIFICATION PROXY
#
# The capability token is custodied HERE and never returned to the browser:
# the run request below injects it server-side, exactly like the staging
# approval capability. That keeps the token out of ordinary UI output, out of
# the access log and out of any Core response the browser can read.
#
# Verifying a draft is a DIFFERENT action from saving it: this proxy never
# calls the save path and holds no save authority.
# ==========================================================

_DRAFT_CONSENT_PATH = "/api/coder/draft-verification/consent"
_DRAFT_PENDING_PATH = "/api/coder/draft-verification/pending"
_DRAFT_RUN_PATH = "/api/coder/draft-verification/run"

_DRAFT_CAPABILITIES = {}
_DRAFT_LOCK = threading.Lock()


def _draft_key(project_id):
    return (session.get("local_session_id"), str(project_id or ""))


def _draft_post(path, payload, timeout):
    headers = _trusted_proxy_headers(payload, path=path)
    if not headers:
        return {"ok": False, "reason": "trusted_local_session_required"}, 403
    try:
        response = requests.post(
            RC.CORE_API_URL.rstrip("/") + path,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        try:
            result = response.json()
        except Exception:
            return {"ok": False, "reason": "invalid_core_json"}, 502
        return result, response.status_code
    except requests.exceptions.Timeout:
        return {"ok": False, "reason": "core_timeout"}, 504
    except requests.exceptions.ConnectionError:
        return {"ok": False, "reason": "core_unreachable"}, 502


@chat_api.route(_DRAFT_PENDING_PATH, methods=["POST"])
def draft_verification_pending_proxy():
    data = request.get_json(silent=True) or {}
    if set(data) != {"project_id"}:
        return jsonify({"ok": False, "reason": "draft_pending_payload_invalid"}), 400
    payload = {
        "operation": "read_pending_draft",
        "project_id": str(data.get("project_id") or ""),
    }
    result, status = _draft_post(_DRAFT_PENDING_PATH, payload, timeout=10800)
    return jsonify(result), status


@chat_api.route(_DRAFT_CONSENT_PATH, methods=["POST"])
def draft_verification_consent_proxy():
    data = request.get_json(silent=True) or {}
    if set(data) != {"project_id", "source_sha256"}:
        return jsonify({"ok": False, "reason": "draft_consent_payload_invalid"}), 400
    project_id = str(data.get("project_id") or "")
    digest = str(data.get("source_sha256") or "")
    payload = {
        "operation": "verify_draft_python",
        "project_id": project_id,
        "proposal_id": "staged:" + digest,
        "source_sha256": digest,
        "consent": True,
    }
    result, status = _draft_post(_DRAFT_CONSENT_PATH, payload, timeout=10800)
    token = result.pop("token", None) if isinstance(result, dict) else None
    with _DRAFT_LOCK:
        if isinstance(token, str) and token.startswith("dv_"):
            _DRAFT_CAPABILITIES[_draft_key(project_id)] = token
        else:
            _DRAFT_CAPABILITIES.pop(_draft_key(project_id), None)
    return jsonify(result), status


@chat_api.route(_DRAFT_RUN_PATH, methods=["POST"])
def draft_verification_run_proxy():
    data = request.get_json(silent=True) or {}
    if set(data) != {"project_id"}:
        return jsonify({"ok": False, "reason": "draft_run_payload_invalid"}), 400
    project_id = str(data.get("project_id") or "")
    # Pop, not get: the browser cannot replay the same verification authority.
    with _DRAFT_LOCK:
        token = _DRAFT_CAPABILITIES.pop(_draft_key(project_id), None)
    if not token:
        return jsonify({
            "ok": False,
            "reason": "draft_verification_not_authorized",
        }), 403
    payload = {
        "operation": "run_draft_verification",
        "project_id": project_id,
        "token": token,
    }
    result, status = _draft_post(_DRAFT_RUN_PATH, payload, timeout=10800)
    if isinstance(result, dict):
        result.pop("token", None)
    return jsonify(result), status


# ==========================================================
# CODER — WINDOWS EXE PACKAGING PROXY (separate consent)

#
# The browser supplies only the identifiers it visibly confirmed. The action and
# scope are server-owned, and packaging consent is explicit and independent of
# save and of run.
# ==========================================================

@chat_api.route("/api/coder/package/prepare", methods=["POST"])
def coder_package_prepare_proxy():
    data = request.get_json(silent=True) or {}
    if set(data) != {"project_id", "filename", "confirm_package"}:
        return jsonify({"ok": False, "reason": "packaging_payload_invalid"}), 400
    if data.get("confirm_package") is not True:
        return jsonify({
            "ok": False,
            "reason": "explicit_package_confirmation_required",
        }), 400
    payload = {
        "operation": "prepare_package",
        "project_id": str(data.get("project_id") or ""),
        "filename": str(data.get("filename") or ""),
        "confirm_package": True,
    }
    return _proxy_coder_execution(
        "/api/coder/package/prepare", payload, timeout=10800)


@chat_api.route("/api/coder/package/status", methods=["POST"])
def coder_package_status_proxy():
    data = request.get_json(silent=True) or {}
    if set(data) != {"project_id", "job_id"}:
        return jsonify({"ok": False, "reason": "packaging_payload_invalid"}), 400
    payload = {
        "operation": "package_status",
        "project_id": str(data.get("project_id") or ""),
        "job_id": str(data.get("job_id") or ""),
    }
    return _proxy_coder_execution(
        "/api/coder/package/status", payload, timeout=10800)


# ==========================================================
# CHAT PROXY
# ==========================================================

@chat_api.route(
    "/api/chat",
    methods=["POST"]
)
def chat_proxy():

    print("CHAT_PROXY VERSION TEST v2")

    try:

        # ==================================================
        # IMAGE ANALYSIS INPUT FAILURE FIX
        #
        # A browser sends `multipart/form-data` as soon as a file is
        # attached (see ui/static/app.js). `request.get_json()` then
        # returns None, so the previous code forwarded `json={}` and the
        # CORE API correctly answered "empty input" — the image never
        # left this process.
        #
        # Multipart is now forwarded AS multipart, exactly like the
        # `/api/image` proxy below. The JSON path is UNCHANGED: a
        # text-only request still posts `json=data` byte for byte as
        # before.
        # ==================================================

        if request.files:

            files = []

            for field in request.files:

                for item in request.files.getlist(field):

                    files.append(
                        (
                            field,
                            (
                                item.filename,
                                item.stream,
                                item.content_type
                                or "application/octet-stream",
                            ),
                        )
                    )

            print(
                "UI GATEWAY MULTIPART REQUEST: files=",
                sorted(request.files.keys()),
                "| form fields=",
                sorted(request.form.keys()),
            )

            forwarded = _inject_private_capability(request.form.to_dict(flat=True))

            response = requests.post(

                CORE_API,

                files=files,

                data=forwarded,

                headers=_trusted_proxy_headers(forwarded),

                timeout=10800

            )

        else:

            data = request.get_json(
                silent=True
            ) or {}

            # FACADE-04D.3C-0 — a file-less request cannot carry IMAGE A/B, so
            # conditioned rendering is impossible here. Forward the explicit
            # opt-in flag so the CORE API REJECTS the request instead of
            # silently dropping it. This only ever adds a single key; the
            # ordinary text-only JSON path is unchanged.
            if not data:

                _conditioned_field = request.form.get("conditioned_render")

                if _conditioned_field:

                    data = {"conditioned_render": _conditioned_field}

            data = _inject_private_capability(data)

            print(
                "UI GATEWAY REQUEST:",
                {
                    key: ("<redacted>" if key == "approval_capability" else value)
                    for key, value in data.items()
                }
            )

            response = requests.post(

                CORE_API,

                json=data,

                headers=_trusted_proxy_headers(data),

                timeout=10800

            )


        print(
            "UI GATEWAY STATUS:",
            response.status_code
        )


        try:

            payload = response.json()


        except Exception:

            payload = {

                "status": "error",

                "message":
                    "Core API returned invalid JSON",

                "raw":
                    response.text

            }



        # ==================================================
        # UI RESPONSE NORMALIZER
        # ==================================================

        if isinstance(payload, dict):

            _capture_private_capability(
                payload,
                (forwarded if request.files else data).get("project_id"),
            )

            payload.setdefault(
                "status",
                "success"
            )

            payload.setdefault(
                "source",
                "core_api"
            )



        # FACADE-02 — propagate the Core API's HTTP status so a truthful
        # rejection (e.g. 400 too_many_images / invalid_image) is not
        # silently flattened to 200. Success (2xx) is unchanged.
        status_code = (
            response.status_code
            if response.status_code >= 400
            else 200
        )

        return jsonify(
            payload
        ), status_code



    except requests.exceptions.Timeout:


        return jsonify({

            "status":"error",

            "message":
                "Core API timeout after 10800 seconds"

        }),504



    except requests.exceptions.ConnectionError as e:


        return jsonify({

            "status":"error",

            "message":
                f"Core API connection error: {e}"

        }),502



    except Exception as e:


        import traceback

        traceback.print_exc()


        return jsonify({

            "status":"error",

            "message":
                str(e)

        }),500


# ==========================================================
# SENT_MESSAGE_EDIT_V1 — REVISION PROXY
#
# The Core API exposes a dedicated revision contract endpoint
# (`SentMessageRevisionV1` at POST /api/revise) with its own status
# codes: 400 for an invalid revision, 404 for a turn that is no longer
# retained, 409 for a duplicate nonce or a concurrent revision.
#
# This is the SAME gateway module and the SAME runtime configuration as
# `/api/chat` above — not a second gateway. It exists so the browser has
# one explicit entry point for a revision instead of overloading the
# chat turn. The Core status code is propagated verbatim so the UI can
# tell "already applied" (409) apart from "not retained" (404); a
# revision flattened to 200 would let the editor report success on a
# branch the server never committed.
# ==========================================================

CORE_REVISE_API = RC.CORE_API_URL.rstrip("/") + "/api/revise"


@chat_api.route(
    "/api/revise",
    methods=["POST"]
)
def revise_proxy():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        print(
            "UI GATEWAY REVISION REQUEST:",
            sorted(data.keys())
        )

        response = requests.post(

            CORE_REVISE_API,

            json=data,

            timeout=10800

        )

        print(
            "UI GATEWAY REVISION STATUS:",
            response.status_code
        )

        try:

            payload = response.json()

        except Exception:

            payload = {

                "status": "error",

                "message":
                    "Core API returned invalid JSON",

                "raw":
                    response.text

            }

        # Preserve the Core HTTP status: 400 / 404 / 409 are meaningful
        # outcomes of the revision contract, not transport failures.
        status_code = (
            response.status_code
            if response.status_code >= 400
            else 200
        )

        return jsonify(
            payload
        ), status_code

    except requests.exceptions.Timeout:

        return jsonify({

            "status":"error",

            "message":
                "Core API timeout after 10800 seconds"

        }),504

    except requests.exceptions.ConnectionError as e:

        return jsonify({

            "status":"error",

            "message":
                f"Core API connection error: {e}"

        }),502

    except Exception as e:

        import traceback

        traceback.print_exc()

        return jsonify({

            "status":"error",

            "message":
                str(e)

        }),500


# ==========================================================
# REAL_RENDER_LIFECYCLE_V1 — READ-ONLY RENDER STATUS PROXY
#
# The browser polls the UI origin; this forwards to the Core status
# endpoint using the SAME runtime configuration as every other route
# here. Read-only: it never submits or cancels a render, and it returns
# the Core payload unchanged so the UI can never mistake a transport
# failure for a lifecycle state.
# ==========================================================

@chat_api.route(
    "/api/render/status",
    methods=["GET"]
)
def render_status_proxy():

    project_id = str(request.args.get("project_id") or "").strip()

    try:

        response = requests.get(

            RC.CORE_API_URL.rstrip("/") + "/api/render/status",

            params={"project_id": project_id},

            timeout=10800

        )

    except requests.exceptions.Timeout:

        return jsonify({
            "status": "error",
            "error": "core_timeout",
        }), 504

    except requests.exceptions.ConnectionError as e:

        return jsonify({
            "status": "error",
            "error": "core_unreachable",
            "message": str(e),
        }), 502

    try:

        payload = response.json()

    except Exception:

        return jsonify({
            "status": "error",
            "error": "invalid_core_json",
        }), 502

    status_code = (
        response.status_code
        if response.status_code >= 400
        else 200
    )

    return jsonify(payload), status_code


# ==========================================================
# IMAGE UPLOAD PROXY
# ==========================================================
@chat_api.route(
    "/api/image",
    methods=["POST"]
)
def image_proxy():

    try:

        image = request.files.get(
            "image"
        )


        if not image:

            return jsonify({

                "status":"error",

                "message":"No image received"

            }),400



        files = {

            "image":
                (
                    image.filename,
                    image.stream,
                    image.content_type
                )

        }



        response = requests.post(

            RC.CORE_API_URL.rstrip("/") + "/image",

            files=files,

            timeout=10800

        )



        try:

            payload = response.json()

        except Exception:

            payload = {

                "status":"error",

                "raw":response.text

            }



        return jsonify(
            payload
        )



    except Exception as e:


        return jsonify({

            "status":"error",

            "message":str(e)

        }),500

# ==========================================================
# VISUAL_REFERENCE_UX_V2 — REFERENCE LIBRARY GATEWAY
#
# Read-only passthrough of the Core API's reference listing. The browser
# talks to the UI origin only; the Core remains the single owner of the
# index. No path, filename or filesystem detail is accepted from the client.
# ==========================================================

@chat_api.route(
    "/api/references",
    methods=["GET"]
)
def references_proxy():

    try:

        response = requests.get(

            RC.CORE_API_URL.rstrip("/") + "/api/references",

            params=request.args.to_dict(flat=True),

            timeout=10800

        )

        try:

            payload = response.json()

        except Exception:

            payload = {

                "status": "error",

                "message": "Core API returned invalid JSON",

                "references": []

            }

        return jsonify(payload), (
            response.status_code if response.status_code >= 400 else 200
        )

    except Exception as e:  # noqa: BLE001

        return jsonify({

            "status": "error",

            "message": str(e),

            "references": []

        }), 502
