# ==========================================================
# ArchitectOS Unified API Gateway v36.1
# UI/API -> ChatArchitect v26.1
# Image Upload + Chat Compatible
# ==========================================================


import logging
import json
import os
import threading
import time
# KROCKI_INGEST_V27_3 — `_ingest_krocki` names each stored survey uniquely at
# MODULE scope, so the import cannot live inside the route any more.
import uuid


from flask import Flask, request, jsonify, abort, send_file, g
from flask_cors import CORS


from config import runtime_config as RC


from core.app_boot import AppBoot
from core.chat.chat_architect import ChatArchitect
from core.chat.chat_attachment import chat_attachment_service
from core.chat.conversation_state import conversation_state


# ==========================================================
# LOGGING_FINAL_CORRECTION_01 — BOUNDED CHAT DIAGNOSTICS
#
# The chat handler used to dump whole payloads into the runtime log
# with print(): "DEBUG MESSAGE", "DEBUG IMAGE VALUE",
# "DEBUG RAW CHAT RESULT" and "DEBUG ADAPTER RESULT".
#
# MEASURED: a single image-analysis turn produced 937,838 bytes of raw
# output — ~95 % of the whole Core API log volume — and it contained the
# COMPLETE user message and the RAW model response.
#
# No code consumes those markers (verified repo-wide: the only matches
# are a frozen backup copy and a captured pytest stdout artefact), so
# they were pure firehose, not diagnostics.
#
# Diagnostics must stay bounded and must never carry user content, raw
# model output, base64 images, attachments or conversation history.
# Only structured metadata is emitted below. The logger propagates to
# the single bounded RotatingFileHandler installed on the root logger
# by core/runtime_logging.py (32 MB x 5 generations).
# ==========================================================

_log = logging.getLogger("core_api")


def _bounded(value, limit=240):
    """Single-line, length-capped rendering of a scalar for logs."""

    try:

        text = " ".join(str(value).split())

    except Exception:

        text = "<unrenderable>"

    if len(text) > limit:

        text = text[:limit] + "…[+" + str(len(text) - limit) + "]"

    return text


def _payload_shape(value, limit=240):
    """Structure-only summary of a payload — NEVER its content.

    Returns the container type (and, for dicts, the field NAMES only) so
    contract drift stays diagnosable without logging any value.
    """

    try:

        if isinstance(value, dict):

            keys = sorted(str(key) for key in value.keys())

            summary = "dict(%d) keys=%s" % (len(keys), ",".join(keys))

        elif isinstance(value, (list, tuple, set)):

            summary = "%s(%d)" % (type(value).__name__, len(value))

        elif value is None:

            summary = "None"

        else:

            summary = type(value).__name__

    except Exception:

        summary = "<unavailable>"

    return _bounded(summary, limit)



app = Flask(
    __name__
)


CORS(app, origins=[RC.UI_URL], supports_credentials=False)


# ==========================================================
# UPLOAD_SIZE_LIMIT_01
#
# Enforced by Werkzeug WHILE the body is being read, so an oversized upload
# is refused before it is written to disk. The previous behaviour accepted
# any size (a 40 MiB non-image was stored as an upload).
#
# The rejection must still be JSON: the UI parses every chat reply as JSON,
# and Flask's default 413 is an HTML page, which the UI can only report as an
# unparseable failure.
# ==========================================================

app.config["MAX_CONTENT_LENGTH"] = RC.MAX_UPLOAD_BYTES


@app.teardown_request
def _release_request_session(_error):
    """Never retain a thread-local conversation binding across HTTP turns."""
    try:
        from core.chat.session_registry_v1 import session_registry
        session_registry.end()
    except Exception:
        pass


@app.errorhandler(413)
def _upload_too_large(_error):

    _limit_mb = RC.MAX_UPLOAD_BYTES / (1024 * 1024)

    _message = (
        "این فایل برای پردازش بیش از حد بزرگ است. "
        "حداکثر حجم مجاز هر درخواست %.0f مگابایت است." % _limit_mb
    )

    return jsonify({

        "status": "error",

        "error": "upload_too_large",

        "message": _message,

        "limit_bytes": RC.MAX_UPLOAD_BYTES,

        "response": {
            "status": "error",
            "type": "upload_too_large",
            "message": _message,
        },

    }), 413




# ==========================================================
# CHAT_LANGUAGE_02 — SESSION KEY
#
# Independent clients must not share conversation state or
# architectural context.  The session key is taken from the
# X-Session-Id header, the JSON body, or the form body.
# No key supplied -> legacy single-session behaviour.
# ==========================================================


def request_session_id(data=None):

    session_id = request.headers.get("X-Session-Id")


    if not session_id and isinstance(data, dict):

        session_id = data.get("session_id")


    if not session_id:

        try:

            session_id = request.form.get("session_id")

        except Exception:

            session_id = None


    return session_id




# ==========================================================
# TEXT_TO_IMAGE_COMFY_03 — EXPLICIT RENDER PRESET
#
# Optional. When absent the preset is inferred deterministically
# from the user's own wording inside the render pipeline.
# ==========================================================


def request_render_preset(data=None):

    preset = request.headers.get("X-Render-Preset")


    if not preset and isinstance(data, dict):

        preset = data.get("preset")


    if not preset:

        try:

            preset = request.form.get("preset")

        except Exception:

            preset = None


    return preset




# ==========================================================
# TEXT_TO_IMAGE_COMFY_03B — EXPLICIT RENDER SEED
#
# Optional. Lets two renders differ ONLY by preset, which is how
# preset lighting semantics are isolated during acceptance.
# ==========================================================


def request_render_seed(data=None):

    seed = request.headers.get("X-Render-Seed")


    if seed is None and isinstance(data, dict):

        seed = data.get("seed")


    if seed is None:

        try:

            seed = request.form.get("seed")

        except Exception:

            seed = None


    if seed in (None, ""):

        return None


    try:

        return int(seed)

    except (TypeError, ValueError):

        return None




# ==========================================================
# IMAGE_TO_IMAGE_05 — EXPLICIT PRESERVATION LEVEL
#
# Optional. high_preservation | balanced | creative
# Default for conversational edits is high_preservation.
# ==========================================================


#: I2I_CONCEPTUAL_ADMISSION_V1 — the explicit conceptual-edit consent.
#:
#: This is a REQUEST CONTRACT field, read the same three ways every other
#: optional render field is read (header, JSON body, form). It is never
#: inferred from the message text: the words "modern", "travertine" or
#: "facade" can never turn it on, and neither can a "Preserve exactly" clause.
#: Only an affirmative, explicitly supplied value counts.
_CONCEPTUAL_EDIT_TRUTHY = ("1", "true", "yes", "on", "conceptual")


def request_conceptual_edit(data=None):

    value = request.headers.get("X-Conceptual-Edit")

    if not value and isinstance(data, dict):

        value = data.get("conceptual_edit")

    if not value:

        try:

            value = request.form.get("conceptual_edit")

        except Exception:

            value = None

    if value is None:

        return False

    return str(value).strip().lower() in _CONCEPTUAL_EDIT_TRUTHY


def request_spatial_planning(data=None):

    """PLAN_FIRST_PRODUCT_SLICE_V1 — opt-in conceptual spatial planning.

    Opt-in only. The planning owner is reached from Chat solely when this
    flag is a real boolean true, so no existing route can be captured by
    accident.
    """

    value = request.headers.get("X-Spatial-Planning")

    if not value and isinstance(data, dict):

        value = data.get("spatial_planning")

    if not value:

        try:

            value = request.form.get("spatial_planning")

        except Exception:

            value = None

    if value is None:

        return False

    return str(value).strip().lower() in _CONCEPTUAL_EDIT_TRUTHY


def request_preserve_level(data=None):
    level = request.headers.get("X-Preserve-Level")


    if not level and isinstance(data, dict):

        level = data.get("preserve_level")


    if not level:

        try:

            level = request.form.get("preserve_level")

        except Exception:

            level = None


    return level or None



print(
    "🚀 Starting ArchitectOS API Gateway..."
)



# ==========================================================
# CORE INITIALIZATION
# ==========================================================


try:


    boot = AppBoot()


    print(
        "🚀 AppBoot initialization completed"
    )


    brain = boot.get_brain()


    print(
        "🧠 API BRAIN:",
        type(brain),
        "RUN:",
        hasattr(brain, "run")
    )



except Exception as e:


    import traceback


    traceback.print_exc()


    raise e





# ==========================================================
# CHAT GATEWAY
# ==========================================================


chat = ChatArchitect(
    brain
)


print(
    "💬 ChatArchitect v26.1 CONNECTED"
)


from core.chat.response_adapter import ResponseAdapter


response_adapter = ResponseAdapter()


# ==========================================================
# PROJECT_WORKSPACE_UI_06 — PROJECT WORKSPACE API
#
# Persistent, project-scoped storage: projects, assets, gallery,
# export / archive / delete, save state, mode + strategy catalog.
# ==========================================================

from core.project.project_api_v1 import project_api

app.register_blueprint(project_api)


print(
    "🗂️ PROJECT WORKSPACE API v1 CONNECTED (persistent)"
)


# ==========================================================
# VOICE_07 — CANONICAL VOICE API
#
# Voice is an OPTIONAL modality over the SAME ChatArchitect and the
# SAME project session. It is NOT a second assistant: the shared
# `chat` instance, the shared response adapter and the shared project
# session are injected here.
# ==========================================================

from core.voice.voice_api_v1 import create_voice_blueprint

from core.project.project_session_v1 import project_session as _project_session

from core.project.project_workspace_v1 import (
    project_workspace as _project_workspace,
)

voice_blueprint, voice_bridge = create_voice_blueprint(
    chat=chat,
    response_adapter=response_adapter,
    project_session=_project_session,
    project_workspace=_project_workspace,
)

app.register_blueprint(voice_blueprint)


print(
    "🎙️ CANONICAL VOICE API v1 CONNECTED (same ChatArchitect, session=project)"
)


# ==========================================================
# PHASE 08 — CONVERSATIONAL INTERACTION AND TEACHING FOUNDATION
#
# Additive read/observe surface over the SAME canonical assistant.
# It constructs NO assistant: it exposes the ONE teaching foundation
# the ChatArchitect already uses. No endpoint renders.
# ==========================================================

from core.conversation.conversation_api_v1 import (
    create_conversation_blueprint,
)

app.register_blueprint(create_conversation_blueprint())


print(
    "🧠 CONVERSATION / TEACHING FOUNDATION API v1 CONNECTED (no render)"
)


# ==========================================================
# CODER MVP V1 — DISTINCT TRUSTED EXECUTION ACTIONS
#
# These routes are not chat intents. They accept only the existing UI proxy's
# signed JSON envelopes and delegate every permission decision to the C07C.2
# bridge plus the execution contract gate. The default environment leaves
# execution disabled.
# ==========================================================

from core.execution.python_execution_mvp_v1 import (
    CONSENT_PATH as _CODER_CONSENT_PATH,
    PREVIEW_PATH as _CODER_PREVIEW_PATH,
    execution_mvp_service as _execution_mvp_service,
)
from core.runtime.local_authorization_v1 import (
    DEFAULT_NONCE_LEDGER as _LOCAL_REQUEST_NONCE_LEDGER,
)


def _coder_mvp_status(result):
    if result.get("ok"):
        return 200
    reason = str(result.get("reason") or "")
    if reason.startswith("proxy_") or reason in {
        "execution_approval_binding_mismatch",
        "execution_consent_project_mismatch",
    }:
        return 403
    if reason in {
        "execution_capability_consumed",
        "execution_capability_not_available",
        "execution_proposal_not_awaiting_approval",
    }:
        return 409
    return 400


@app.route(_CODER_PREVIEW_PATH, methods=["POST"])
def coder_execution_preview():
    data = request.get_json(silent=True) or {}
    result = _execution_mvp_service.prepare_preview(
        proxy_secret=os.environ.get("ARCHITECTOS_LOCAL_PROXY_SECRET", ""),
        headers=request.headers,
        payload=data,
        path=request.path,
        remote_addr=request.remote_addr,
        nonce_ledger=_LOCAL_REQUEST_NONCE_LEDGER,
    )
    return jsonify(result), _coder_mvp_status(result)


@app.route(_CODER_CONSENT_PATH, methods=["POST"])
def coder_execution_consent():
    data = request.get_json(silent=True) or {}
    result = _execution_mvp_service.approve_and_run(
        proxy_secret=os.environ.get("ARCHITECTOS_LOCAL_PROXY_SECRET", ""),
        headers=request.headers,
        payload=data,
        path=request.path,
        remote_addr=request.remote_addr,
        nonce_ledger=_LOCAL_REQUEST_NONCE_LEDGER,
    )
    return jsonify(result), _coder_mvp_status(result)


# ==========================================================
# CODER — UNSAVED DRAFT VERIFICATION (separate consent)
#
# A fourth, separate action. It never writes a file, and its authority is
# disjoint from the save approval and from the saved-file execution approval.
# The browser never receives the capability token: the UI proxy keeps it
# server-side, exactly like the staging approval capability.
# ==========================================================

from core.execution.draft_verification_v1 import (
    DRAFT_CONSENT_PATH as _DRAFT_CONSENT_PATH,
    DRAFT_PENDING_OPERATION as _DRAFT_PENDING_OPERATION,
    DRAFT_PENDING_PATH as _DRAFT_PENDING_PATH,
    DRAFT_RUN_OPERATION as _DRAFT_RUN_OPERATION,
    DRAFT_RUN_PATH as _DRAFT_RUN_PATH,
    draft_verification_service as _draft_verification_service,
    pending_summary as _draft_pending_summary,
    scenarios_for_project as _draft_scenarios_for_project,
)
from core.runtime.local_authorization_v1 import (
    verify_proxy_request as _verify_local_proxy_request,
)


def _draft_verification_status(result):
    """A completed verification is HTTP 200 whatever its verdict is."""

    if result.get("stage") == "draft_verification_finished":
        return 200
    if result.get("ok"):
        return 200
    reason = str(result.get("reason") or "")
    if reason.startswith("proxy_"):
        return 403
    if reason in {
        "draft_capability_consumed",
        "draft_capability_expired",
        "draft_consent_proposal_not_pending",
        "staged_proposal_not_pending",
    }:
        return 409
    return 400


def _draft_request_verified(data):
    return _verify_local_proxy_request(
        os.environ.get("ARCHITECTOS_LOCAL_PROXY_SECRET", ""),
        request.headers,
        data,
        path=request.path,
        remote_addr=request.remote_addr,
        nonce_ledger=_LOCAL_REQUEST_NONCE_LEDGER,
    )


@app.route(_DRAFT_PENDING_PATH, methods=["POST"])
def coder_draft_verification_pending():
    data = request.get_json(silent=True) or {}
    if (set(data) != {"operation", "project_id"}
            or data.get("operation") != _DRAFT_PENDING_OPERATION):
        return jsonify({"ok": False, "reason": "draft_pending_payload_invalid"}), 400
    verified = _draft_request_verified(data)
    if not verified.get("trusted"):
        return jsonify({"ok": False, "reason": verified.get("reason")}), 403
    return jsonify(_draft_pending_summary(data.get("project_id"))), 200


@app.route(_DRAFT_CONSENT_PATH, methods=["POST"])
def coder_draft_verification_consent():
    data = request.get_json(silent=True) or {}
    result = _draft_verification_service.consent.mint(
        proxy_secret=os.environ.get("ARCHITECTOS_LOCAL_PROXY_SECRET", ""),
        headers=request.headers,
        payload=data,
        path=request.path,
        remote_addr=request.remote_addr,
        nonce_ledger=_LOCAL_REQUEST_NONCE_LEDGER,
        project_id=data.get("project_id") if isinstance(data, dict) else None,
    )
    return jsonify(result), _draft_verification_status(result)


@app.route(_DRAFT_RUN_PATH, methods=["POST"])
def coder_draft_verification_run():
    data = request.get_json(silent=True) or {}
    if (set(data) != {"operation", "project_id", "token"}
            or data.get("operation") != _DRAFT_RUN_OPERATION):
        return jsonify({"ok": False, "reason": "draft_run_payload_invalid"}), 400
    verified = _draft_request_verified(data)
    if not verified.get("trusted"):
        return jsonify({"ok": False, "reason": verified.get("reason")}), 403
    result = _draft_verification_service.verify_draft(
        project_id=data.get("project_id"),
        token=data.get("token"),
        scenarios=_draft_scenarios_for_project(data.get("project_id")),
        actor_id=verified.get("actor_id"),
        session_id=verified.get("session_id"),
    )
    return jsonify(result), _draft_verification_status(result)


# ==========================================================
# CODER — WINDOWS EXE PACKAGING (SANDBOX ONLY)
#
# A third, separate consent. Saving a file does not authorise packaging it, and
# packaging does not authorise running it. The host never builds: it stages a
# job for Windows Sandbox and reads back a verified manifest.
# ==========================================================

from core.execution.packaging.windows_package_v1 import (
    PREPARE_PATH as _CODER_PACKAGE_PREPARE_PATH,
    STATUS_PATH as _CODER_PACKAGE_STATUS_PATH,
    package_status as _package_status,
    prepare_package as _prepare_package,
)


@app.route(_CODER_PACKAGE_PREPARE_PATH, methods=["POST"])
def coder_package_prepare():
    data = request.get_json(silent=True) or {}
    result = _prepare_package(
        proxy_secret=os.environ.get("ARCHITECTOS_LOCAL_PROXY_SECRET", ""),
        headers=request.headers,
        payload=data,
        path=request.path,
        remote_addr=request.remote_addr,
        nonce_ledger=_LOCAL_REQUEST_NONCE_LEDGER,
    )
    return jsonify(result), _coder_mvp_status(result)


@app.route(_CODER_PACKAGE_STATUS_PATH, methods=["POST"])
def coder_package_status():
    data = request.get_json(silent=True) or {}
    result = _package_status(
        proxy_secret=os.environ.get("ARCHITECTOS_LOCAL_PROXY_SECRET", ""),
        headers=request.headers,
        payload=data,
        path=request.path,
        remote_addr=request.remote_addr,
        nonce_ledger=_LOCAL_REQUEST_NONCE_LEDGER,
    )
    return jsonify(result), _coder_mvp_status(result)


@app.route(
    "/artifacts/<root_key>/<path:relative_path>",
    methods=["GET"]
)
def serve_chat_artifact(root_key, relative_path):

    path = chat_attachment_service.resolve_public_path(
        root_key,
        relative_path
    )

    if path is None:

        abort(404)

    return send_file(
        path,
        as_attachment=request.args.get("download") == "1",
        download_name=path.name,
        conditional=True
    )




# ==========================================================
# JSON SAFE
# ==========================================================


def json_safe(obj):


    if isinstance(
        obj,
        dict
    ):

        return {

            k:
                json_safe(v)

            for k, v in obj.items()

        }



    if isinstance(
        obj,
        list
    ):

        return [

            json_safe(x)

            for x in obj

        ]



    if hasattr(
        obj,
        "__dict__"
    ):

        return json_safe(
            obj.__dict__
        )



    return obj





# ==========================================================
# HEALTH
# ==========================================================


@app.route(
    "/health",
    methods=["GET"]
)
def health():


    return jsonify({

        "system":
            "ArchitectOS",

        "version":
            "Core Platform v36.1",

        "chat":
            "ChatArchitect v26.1",

        "brain":
            str(type(brain)),

        "status":
            "ONLINE"

    })




# ==========================================================
# RUNTIME STATUS / PREFLIGHT
# ==========================================================


@app.route(
    "/runtime/status",
    methods=["GET"]
)
def runtime_status_api():


    from core.runtime.runtime_preflight import run_preflight


    return jsonify(
        json_safe(
            run_preflight()
        )
    )





# ==========================================================
# SENT_MESSAGE_EDIT_V1 — REVISION OF AN ALREADY-SENT USER TURN
#
# Semantics (all enforced HERE, on the server):
#
#   * TEXT-ONLY. The revision never carries an image, never selects a
#     render mode and never touches the ComfyUI path. A UI mode selector
#     is not trusted to enforce this.
#   * The PERSISTED transcript (`chat.json`) is the source of historical
#     truth. The in-process conversation memory is REBUILT from the
#     persisted prefix before regeneration, so an edited turn can never
#     inherit a downstream branch — and after a restart it recovers the
#     context that actually exists on disk instead of starting blind.
#   * Nothing is deleted. The superseded branch is MARKED and stays
#     visible; only its participation in active context stops.
#   * Committed on success only: a failed model call leaves `chat.json`
#     untouched.
#   * One revision per project at a time, keyed by project id — never by
#     shared mutable state on the ChatArchitect singleton.
# ==========================================================

_REVISION_LOCKS = {}
_REVISION_LOCKS_GUARD = threading.Lock()

# Generation modes are refused outright: a revision is a text turn.
_REVISION_FORBIDDEN_MODES = {
    "render", "image", "img2img", "text2img", "t2i", "i2i",
    "generate", "edit_image", "image_edit",
}


def _revision_lock(project_id):
    with _REVISION_LOCKS_GUARD:
        lock = _REVISION_LOCKS.get(project_id)
        if lock is None:
            lock = threading.Lock()
            _REVISION_LOCKS[project_id] = lock
        return lock


def _revision_error(reason, message, status=409, **extra):
    payload = {"status": "error", "error": reason, "message": message}
    payload.update(extra)
    return jsonify(payload), status


def message_revision_turn(body):
    """Handle one revision of an already-sent user message."""

    from core.project.conversation_store_v1 import conversation_store
    from core.memory.memory_manager import memory_manager

    project_id = str(body.get("project_id") or "").strip()
    ref = str(body.get("revise_ref") or "").strip()
    text = str(body.get("text") or "").strip()
    nonce = str(body.get("revision_nonce") or "").strip() or None

    if not project_id:
        return _revision_error("project_required",
                               "Revision requires a project.", 400)

    if not ref:
        return _revision_error("revise_ref_required",
                               "Revision requires the reference of the message being edited.", 400)

    if not text:
        return _revision_error("empty_revision",
                               "The revised message is empty.", 400)

    # E — backend-enforced text-only. This is not a UI hint.
    mode = str(body.get("mode") or "").strip().lower()

    if mode in _REVISION_FORBIDDEN_MODES:
        return _revision_error(
            "revision_text_only",
            "A message revision is a text turn and cannot start a render.",
            400,
        )

    if str(body.get("conditioned_render") or "").strip() not in ("", "0", "false", "False"):
        return _revision_error(
            "revision_text_only",
            "A message revision cannot request a conditioned render.",
            400,
        )

    lock = _revision_lock(project_id)

    if not lock.acquire(blocking=False):
        return _revision_error(
            "revision_in_progress",
            "Another revision is already running for this project.",
            409,
        )

    try:
        payload = conversation_store.load(project_id)
        messages = payload.get("messages") or []

        if not isinstance(messages, list):
            messages = []

        index = conversation_store.resolve_ref(messages, ref)

        if index is None:
            return _revision_error(
                "turn_not_retained",
                "That message is no longer in the retained conversation "
                "history, so it cannot be revised. Conversations keep the "
                "most recent 100 messages.",
                404,
            )

        target = messages[index]

        if not isinstance(target, dict) or target.get("role") != "user":
            return _revision_error(
                "not_a_user_turn",
                "Only a user message can be revised.",
                400,
            )

        # Duplicate Save / repeated retry: the same nonce must not append
        # a second branch.
        if nonce and payload.get("last_revision_nonce") == nonce:
            return _revision_error(
                "revision_already_applied",
                "This revision was already applied.",
                409,
            )

        prefix = conversation_store.active_prefix(messages, index)
        original_len = len(messages)
        original_text = str(target.get("text") or "")
        original_attachments = target.get("attachments") or []

        # B — rebuild the model's history from the PERSISTED prefix. This is
        # what makes an older-turn edit branch-correct and restart-safe.
        seeded = memory_manager.replace_conversation_session(
            project_id, prefix
        )

        try:
            result = chat.handle(
                text,
                context={"session_id": project_id},
            )

        except Exception as error:
            # Committed on success only: nothing was written to chat.json,
            # so the active branch is intact and a retry is safe.
            _log.error(
                "revision failed | project=%s category=%s detail=%s",
                project_id, type(error).__name__, _bounded(error, 200),
            )

            return _revision_error(
                "revision_failed",
                "The revised message could not be processed. "
                "The conversation was not changed.",
                502,
                retryable=True,
            )

        formatted = response_adapter.adapt(result)

        reply = ""

        if isinstance(formatted, dict):
            reply = str(formatted.get("result") or formatted.get("message") or "")

        if not reply.strip():
            return _revision_error(
                "revision_empty_reply",
                "The model returned no reply. The conversation was not changed.",
                502,
                retryable=True,
            )

        # ---- COMMIT (success only) ----
        _payload, user_seq = conversation_store.append_turn(
            project_id,
            "user",
            text,
            attachments=original_attachments,
            extra={"revises": {
                "ref": ref,
                "turn_seq": target.get("turn_seq"),
                "text": original_text,
            }},
        )

        _payload, _assistant_seq = conversation_store.append_turn(
            project_id,
            "assistant",
            reply,
            extra={"answers_turn": user_seq},
        )

        # Mark ONLY the replaced range: [target, original_len). The new
        # revision messages are appended after it and stay active.
        conversation_store.mark_superseded(
            project_id, index, user_seq, to_index=original_len
        )

        if nonce:
            conversation_store.set_last_revision_nonce(project_id, nonce)

        _log.info(
            "revision committed | project=%s ref=%s prefix=%d superseded=%d",
            project_id, ref, seeded, original_len - index,
        )

        return jsonify({
            "status": "success",
            "project_id": project_id,
            "response": json_safe(formatted),
            "revision": {
                "contract": "SentMessageRevisionV1",
                "revise_ref": ref,
                "turn_seq": user_seq,
                "prefix_messages": seeded,
                "superseded": original_len - index,
                "text_only": True,
            },
        })

    finally:
        lock.release()


@app.route("/api/revise", methods=["POST"])
def api_revise():
    # LOGGING_FINAL_CORRECTION_01 — bounded turn-duration diagnostic.
    _t0 = time.perf_counter()

    try:
        body = request.get_json(force=True, silent=True) or {}
    except Exception:
        body = {}

    out = message_revision_turn(body)
    _dt = time.perf_counter() - _t0
    _log.info("revision turn | status=%s | duration=%.3f", getattr(out, 'status_code', '-'), _dt)
    return out


# ==========================================================
# REAL_RENDER_LIFECYCLE_V1 — READ-ONLY RENDER STATUS
#
# Reports the lifecycle stage of the ComfyUI job that THIS project owns,
# from real ComfyUI evidence only:
#
#     GET /queue            -> queue_running / queue_pending membership
#     GET /history/<id>     -> completion, explicit error, explicit interrupt
#
# Rules enforced here (all of them matter):
#
#   * The job is identified by the EXACT prompt id the render published at
#     submission time. There is no "newest job" fallback anywhere.
#   * A record is only reported to the project that owns it. Any other
#     project gets `inactive`.
#   * A prompt missing from every source is `unknown` — never `completed`
#     and never `cancelled`.
#   * `retrieving` means ComfyUI finished but THIS request has not returned
#     its result yet. Output retrieval is never reported as complete here.
#   * Strictly read-only: it never submits, cancels or mutates anything.
# ==========================================================

# ==========================================================
# VISUAL_REFERENCE_UX_V2 — REFERENCE LIBRARY (READ ONLY)
#
# The browser never supplies a path. It receives a reference ID, a preview
# URL built from the EXISTING /artifacts/<root_key>/<relative_path> route
# (validated by chat_attachment_service.resolve_public_path), and the
# reference's declared metadata with its authority clearly labelled.
#
# This endpoint registers nothing, classifies nothing and promotes nothing.
# ==========================================================

@app.route("/api/references", methods=["GET"])
def api_references():

    try:

        from core.vision.visual_reference_index_v1 import (
            load_default_index,
            preview_descriptor,
        )

        index = load_default_index()

    except Exception as exc:  # noqa: BLE001

        return jsonify({
            "status": "error",
            "message": "reference index unavailable: %s" % (exc,),
            "references": [],
        }), 503

    collection = str(request.args.get("collection") or "").strip()

    query = str(request.args.get("q") or "").strip().lower()

    items = []

    for entry in index.usable():

        if collection and entry.get("collection") != collection:

            continue

        descriptor = preview_descriptor(entry)

        observations = entry.get("declared_observations") or {}

        hint = (
            observations.get("reference_group_hint")
            or observations.get("style_description_not_canonical")
            or ""
        )

        if query and query not in ("%s %s" % (entry.get("reference_id"), hint)).lower():

            continue

        items.append({

            "reference_id": entry.get("reference_id"),
            "collection": entry.get("collection"),
            "width": entry.get("width"),
            "height": entry.get("height"),
            "sha256": entry.get("sha256"),
            # authority is stated, never implied
            "review_status": entry.get("review_status"),
            "annotation_authority": entry.get("annotation_authority"),
            "declared_hint": hint,
            "declared_observations": observations,
            "external_equivalent": entry.get("external_equivalent"),
            "preview_url": (
                "/artifacts/%s/%s" % descriptor if descriptor else None
            ),
        })

    return jsonify({

        "status": "success",
        "count": len(items),
        "authority": "declared_metadata_only",
        "annotation_authority": "none",
        "message": (
            "Reference metadata is unverified. A declared hint may rank "
            "candidates; it never certifies a style."
        ),
        "references": items,
    })


@app.route("/api/render/status", methods=["GET"])
def api_render_status():

    project_id = str(request.args.get("project_id") or "").strip()

    if not project_id:

        return jsonify({
            "status": "error",
            "error": "project_required",
        }), 400

    runtime = getattr(chat, "render_runtime", None)

    record = getattr(runtime, "active_render", None)

    # Nothing published, or published by a DIFFERENT project.
    if not isinstance(record, dict) or str(record.get("project_id") or "") != project_id:

        return jsonify({
            "status": "inactive",
            "active": False,
            "project_id": project_id,
        })

    prompt_id = str(record.get("prompt_id") or "")

    if not prompt_id:

        return jsonify({
            "status": "inactive",
            "active": False,
            "project_id": project_id,
        })

    stage = "unknown"
    evidence = "no_reader"

    comfy = getattr(getattr(runtime, "executor", None), "comfy", None)

    if comfy is not None:

        queue = comfy.queue_state(timeout=5)

        if isinstance(queue, dict) and queue.get("ok"):

            running = queue.get("running") or []
            pending = queue.get("pending") or []

            if prompt_id in running:

                stage = "executing"
                evidence = "queue_running"

            elif prompt_id in pending:

                stage = "queued"
                evidence = "queue_pending"

            else:

                # Not queued. Completion may ONLY be claimed from history.
                history = comfy.history(prompt_id)

                entry = None

                if isinstance(history, dict) and prompt_id in history:

                    entry = history.get(prompt_id) or {}

                if isinstance(entry, dict) and entry:

                    state = entry.get("status") or {}
                    status_str = str(state.get("status_str") or "").lower()
                    messages = state.get("messages") or []

                    interrupted = any(
                        isinstance(item, (list, tuple))
                        and item
                        and str(item[0]) == "execution_interrupted"
                        for item in messages
                    )

                    if interrupted:

                        stage = "cancelled"
                        evidence = "history_execution_interrupted"

                    elif status_str == "error":

                        stage = "failed"
                        evidence = "history_status_error"

                    elif state.get("completed") is True or status_str == "success":

                        # ComfyUI is done; THIS request has not returned yet.
                        stage = "retrieving"
                        evidence = "history_completed"

                    else:

                        stage = "executing"
                        evidence = "history_incomplete"

                else:

                    stage = "unknown"
                    evidence = "not_in_queue_or_history"

        else:

            stage = "unknown"
            evidence = "queue_unreadable"

    submitted_at = record.get("submitted_at")

    elapsed = None

    try:

        if isinstance(submitted_at, (int, float)):

            elapsed = round(max(0.0, time.time() - float(submitted_at)), 1)

    except Exception:

        elapsed = None

    # REAL_SAMPLING_PROGRESS_B_PLUS — verified sampler progress
    #
    # The WebSocket listener (if alive) provides real step progress
    # for the exact prompt_id this project submitted. This is the
    # ONLY source of "Step X / Y" — it is never estimated from
    # queue state or elapsed time. If the listener is down, these
    # fields are absent and the UI shows only the lifecycle stage.
    #
    # CORRECTION: the listener is only trusted when it is bound to the
    # SAME prompt_id as the record being reported. Without this check a
    # newer render's listener could colour an older record for a
    # moment. Sampling is reported only when prompt, project and
    # generation all agree.
    sampling_step = None
    sampling_max = None
    sampling_node = None

    listener = getattr(runtime, "_progress_listener", None)

    if listener is not None:
        try:
            listener_stats = listener.stats()
        except Exception:
            listener_stats = None

        listener_prompt = (
            str((listener_stats or {}).get("bound_prompt_id") or "")
            if isinstance(listener_stats, dict) else ""
        )

        if listener_prompt and listener_prompt == prompt_id:
            progress = listener.latest()
            if isinstance(progress, dict) and progress.get("verified_sampler"):
                sampling_step = progress.get("step")
                sampling_max = progress.get("max")
                sampling_node = progress.get("node")

    response_payload = {
        "status": "active",
        "active": True,
        "project_id": project_id,
        "prompt_id": prompt_id,
        "generation": record.get("generation"),
        "stage": stage,
        "evidence": evidence,
        "engine": record.get("engine"),
        "workflow": record.get("workflow"),
        "elapsed_seconds": elapsed,
    }

    if sampling_step is not None and sampling_max is not None:
        response_payload["sampling_step"] = sampling_step
        response_payload["sampling_max"] = sampling_max
        response_payload["sampling_node"] = sampling_node

    return jsonify(response_payload)


# ==========================================================
# SOURCE / MASK IDENTITY SAFETY V1
#
# SOURCE_MASK_MISROUTING: LoadImage(300) and LoadImageMask(310) resolved to
# the SAME file's bytes, so the model read the mask as the building. The
# existing contracts each check one thing — the mask's provenance against the
# current source, the dimensions, the composite's presence — and every one of
# them agrees when the source and the mask are the same asset.
#
# This is a pure predicate over values the boundary has ALREADY derived
# itself: two canonical paths, two server-computed digests. It is not a
# second provenance system, it does not classify images, and it adds no
# state. A non-None return is a reason code; the caller refuses.
# ==========================================================

#: The server-owned namespace for masks staged into ComfyUI's input folder.
MASK_ASSET_PREFIX = "architectos_mask_"


def _canonical_asset_path(path):
    """A comparison key for a filesystem path, or None when unusable."""

    if not path or not isinstance(path, str):

        return None

    try:

        return os.path.normcase(os.path.realpath(path))

    except (OSError, ValueError):

        return None


def source_mask_identity_collision(
    source_path,
    source_digest,
    mask_path,
    mask_digest,
):
    """Return a reason code when the mask and the source are the same asset.

    ``None`` means the two identities are distinct. Every other return value
    is a refusal reason.

    The checks are ordered from most to least specific:

    * ``same_canonical_path`` — the two names resolve to one file.
    * ``source_is_mask_namespace`` — the resolved source is a file the server
      itself staged as a mask. This is the incident's exact shape: the source
      resolution landed on the mask.
    * ``same_digest`` — different files, identical bytes. Two encodings of the
      same wrongly routed image are NOT caught here; see the report's
      limitations. Digest equality is the strongest signal available without
      classifying image content, which this boundary must not do.
    * ``mask_digest_unavailable`` — the mask could not be hashed, so its
      separation from the source cannot be proven. Fail closed.
    """

    canonical_source = _canonical_asset_path(source_path)

    canonical_mask = _canonical_asset_path(mask_path)

    if canonical_source and canonical_mask and canonical_source == canonical_mask:

        return "same_canonical_path"

    mask_name = os.path.basename(mask_path or "")

    source_name = os.path.basename(source_path or "")

    # A source that the server staged as a mask is the mask, whatever the
    # request called it. The prefix is server-owned, never user-supplied.
    for candidate in (source_name, canonical_source and os.path.basename(canonical_source)):

        if isinstance(candidate, str) and candidate.startswith(MASK_ASSET_PREFIX):

            return "source_is_mask_namespace"

    if not mask_digest:

        return "mask_digest_unavailable"

    if source_digest and str(source_digest) == str(mask_digest):

        return "same_digest"

    return None


# ==========================================================
# MAIN CHAT + IMAGE INPUT
# ==========================================================


@app.route(
    "/chat",
    methods=["POST"]
)

@app.route(
    "/api/chat",
    methods=["POST"]
)
def chat_api():

    # LOGGING_FINAL_CORRECTION_01 — bounded turn-duration diagnostic.
    # Purely observational; it changes no chat behaviour.
    _t0 = time.perf_counter()

    # ======================================================
    # REAL_SAMPLING_PROGRESS_B_PLUS — REQUEST-SCOPED OWNERSHIP
    #
    # Flask's `g` is request-scoped. We capture the real project_id
    # from the request body/form here, so the render runtime can
    # read an immutable owner that is scoped to THIS request —
    # never the process-wide singleton. This protects two browser
    # tabs using different projects from cross-contamination.
    # ======================================================

    g.project_id = None

    # ======================================================
    # SENT_MESSAGE_EDIT_V1 — REVISION DISPATCH
    #
    # Handled FIRST, before any image/file branch can be reached, so a
    # revision can never inherit an attachment-driven render path even
    # if the client sends one. The revision itself is text-only.
    # ======================================================

    _revision_body = None

    if request.form.get("revise_ref"):

        _revision_body = request.form.to_dict(flat=True)

    else:

        _maybe_json = request.get_json(silent=True)

        if isinstance(_maybe_json, dict) and _maybe_json.get("revise_ref"):

            _revision_body = _maybe_json

    if _revision_body is not None:

        return message_revision_turn(_revision_body)

    # ======================================================
    # REAL_SAMPLING_PROGRESS_B_PLUS — CAPTURE REQUEST-SCOPED PROJECT
    #
    # The project_id is now known: either from the JSON body or the
    # multipart form. Store it on Flask's `g` so the render runtime
    # can read an immutable owner that is scoped to THIS request.
    # ======================================================

    try:
        _body_json = request.get_json(silent=True)
    except Exception:
        _body_json = None

    _request_project_id = (
        request.form.get("project_id")
        or (str(_body_json.get("project_id") or "").strip()
            if isinstance(_body_json, dict) else "")
        or ""
    ).strip()

    if _request_project_id:
        g.project_id = str(_request_project_id)

    # ======================================================
    # KROCKI_CHAT_TUNNEL_V27_3 — upload a survey THROUGH /api/chat
    #
    # `/api/chat` is already proxied and authenticated between :3000 and
    # :5000, so it keeps working even when the gateway build has no krocki
    # route. The file arrives base64-encoded because this transport is JSON.
    #
    # Checked before every other chat branch: this is not a conversational
    # turn, and it must never reach the design pipeline.
    # ======================================================

    if isinstance(_body_json, dict) and (
        _body_json.get("krocki_upload_only") is True
        or str(_body_json.get("action") or "").strip().lower()
        == "upload_krocki"
    ):

        return _krocki_chat_tunnel(_body_json, _request_project_id)

    # ======================================================
    # KROCKI_CHAT_INJECT_V27_2 — a parcel the browser derived locally
    #
    # When the upload route is unavailable (an older :3000 build), the client
    # derives the parcel itself and attaches it to the chat body. Accepting it
    # here is what makes that fallback real rather than decorative.
    #
    # It NEVER overrides a survey the server already parsed: a local estimate
    # from a filename is strictly weaker evidence than a DXF the reader opened.
    # ======================================================

    try:

        _injected_krocki = (
            (_body_json or {}).get("active_site_krocki")
            if isinstance(_body_json, dict)
            else None
        )

        if isinstance(_injected_krocki, dict) and _injected_krocki:

            _krocki_session = _v25_session_module()

            _krocki_project = str(_request_project_id or "default")

            _existing = _krocki_session.load_state(
                _krocki_project
            ).get("active_site_krocki")

            if not _existing:

                _krocki_session.save_active_krocki_state(
                    _REPO_ROOT,
                    _krocki_project,
                    _injected_krocki,
                )

                print(
                    "📐 KROCKI ACCEPTED FROM BROWSER ESTIMATE:",
                    _injected_krocki.get("width_m"),
                    "x",
                    _injected_krocki.get("length_m"),
                )

    except Exception as _krocki_exc:  # noqa: BLE001

        # Never fail a chat turn over an optional site hint.
        print("⚠️ KROCKI INJECTION IGNORED:", _krocki_exc)

    # CODER-05.2 — privileged coder operations trust only a short-lived,
    # nonce-bound signature from the local UI gateway.  An ordinary/direct
    # HTTP request remains valid for non-privileged chat, but is explicitly
    # untrusted for filesystem staging, rejection and approval.
    try:
        import os as _os
        from core.runtime.local_authorization_v1 import verify_proxy_request
        _authorization_payload = (
            dict(_body_json)
            if isinstance(_body_json, dict)
            else request.form.to_dict(flat=True)
        )
        _trusted_local_authorization = verify_proxy_request(
            _os.environ.get("ARCHITECTOS_LOCAL_PROXY_SECRET", ""),
            request.headers,
            _authorization_payload,
            path=request.path,
            remote_addr=request.remote_addr,
        )
        _trusted_local_authorization["project_id"] = _request_project_id or None
    except Exception:
        _trusted_local_authorization = {
            "trusted": False,
            "reason": "proxy_verification_failed",
            "project_id": _request_project_id or None,
        }


    # ======================================================
    # SUPPORT JSON + FORM IMAGE UPLOAD
    # ======================================================


    # ======================================================
    # FACADE-02 — DUAL IMAGE A/B TRANSPORT (ROLE-BEARING)
    #
    # Two role-bearing multipart fields are accepted:
    #   image_a -> IMAGE A = FACADE_STYLE_REFERENCE (appearance only)
    #   image_b -> IMAGE B = TARGET_BUILDING       (geometry authority)
    #
    # The legacy single-image field `image` is preserved verbatim and is
    # interpreted as the TARGET BUILDING (role B).  Roles are NEVER
    # swapped: A is always the style reference, B is always the target.
    #
    # A client-supplied file NAME is never treated as proof that an image
    # arrived.  Every attachment must be stored and validated through
    # chat_attachment_service before it may enter context["references"].
    # ======================================================

    _image_references = None

    _image_a = None

    _image_b = None

    _image_count = 0

    # CHAT_UPLOAD_SINGLE_OWNER_V1 — the validated attachment of the LEGACY
    # single-image field (`image`). Stays None on the JSON path and on the
    # role-bearing A/B path, where `_image_references` already carries the
    # validated attachments. `_legacy_rejected` marks a file the attachment
    # service REFUSED: nothing was stored, so the turn must not record a
    # phantom attachment the UI could only render as "unavailable".
    _legacy_attachment = None

    _legacy_rejected = False

    # FACADE-04D.3C-0 — EXPLICIT conditioned-render opt-in. Read ONLY from the
    # explicit request field (multipart form or JSON body). It is NEVER
    # inferred from the user's text and never from model output, so a
    # generated sentence can never switch it on. Validated after the image
    # block below, where BOTH role references are known.
    #
    # REFERENCE_TRANSFER_POLICY_V1 — the field is TRI-STATE:
    #   True  = the user explicitly asked for the conditioned graph;
    #   False = the user explicitly declined it (UI toggle present, unchecked);
    #   None  = not supplied, so the render path derives the choice from the
    #           intent and image-role contracts instead of guessing here.
    _conditioned_form_value = request.form.get("conditioned_render")

    if request.files:

        # ---- collect EVERY submitted file, whatever the field name ----
        #
        # PRECISE_EDIT_UI_V1 — the selection MASK is not an image of the
        # scene: it is a binary selection for the source image. It must not
        # count toward the two-image limit, otherwise A+B+mask (a legitimate
        # conditioned localized edit) would be rejected as "too many images".
        _submitted = []

        for _field in request.files:

            if _field in ("mask", "mask_file"):

                continue

            for _item in request.files.getlist(_field):

                if _item is not None and getattr(_item, "filename", ""):

                    _submitted.append((_field, _item))

        # ---- HARD LIMIT: at most two images in this workflow ----
        if len(_submitted) > 2:

            _limit_message = (
                "This workflow accepts at most two images "
                "(IMAGE A = facade style reference, "
                "IMAGE B = target building). Received %d."
                % len(_submitted)
            )

            return jsonify({

                "status": "error",

                "error": "too_many_images",

                "message": _limit_message,

                # The UI renders response.message, so the clear reason is
                # carried in the same envelope shape as every other reply.
                "response": {
                    "status": "error",
                    "type": "too_many_images",
                    "message": _limit_message,
                },

                "received_fields": [f for f, _ in _submitted],

            }), 400

        # ---- role-bearing fields (explicit, never inferred from order) ----
        _role_files = {}

        for _role, _field in (("A", "image_a"), ("B", "image_b")):

            _candidate = request.files.get(_field)

            if _candidate is not None and getattr(_candidate, "filename", ""):

                _role_files[_role] = _candidate

        _legacy_image = request.files.get("image")

        if _legacy_image is not None and not getattr(_legacy_image, "filename", ""):

            _legacy_image = None

        if _role_files:

            _ordered = [
                (_role, _role_files[_role])
                for _role in ("A", "B")
                if _role in _role_files
            ]

            _taken = {_role for _role, _ in _ordered}

            if _legacy_image is not None and "B" not in _taken:

                _ordered.append(("B", _legacy_image))

            # ---- store + validate each role image (real bytes, not names) ----
            _validated = {}

            _invalid = {}

            for _role, _fs in _ordered:

                _up = chat_attachment_service.save_upload(
                    _fs, source="user_upload", kind="image"
                )

                if _up.get("status") == "ready":

                    _validated[_role] = _up

                else:

                    _invalid[_role] = _up.get("error", "image_upload_failed")

            if _invalid:

                _invalid_message = (
                    "Image validation failed for: "
                    + ", ".join(
                        "%s (%s)" % (r, e)
                        for r, e in sorted(_invalid.items())
                    )
                )

                return jsonify({

                    "status": "error",

                    "error": "invalid_image",

                    "message": _invalid_message,

                    "response": {
                        "status": "error",
                        "type": "invalid_image",
                        "message": _invalid_message,
                    },

                    "invalid_roles": _invalid,

                }), 400

            # ---- populate the EXISTING context["references"] contract ----
            _image_references = {}

            for _role, _up in _validated.items():

                _att = chat_attachment_service.public_attachment(
                    _up["attachment"]
                )

                _image_references[_role] = {

                    "role":
                        "facade_reference" if _role == "A" else "target_building",

                    "authority":
                        "appearance_only" if _role == "A" else "geometry",

                    "present": True,

                    # FACADE-03 — the validated on-disk path, so the real
                    # vision provider reads the actual image bytes.
                    "path": _up["path"],

                    "asset_id": _att.get("id"),

                    "filename": _att.get("filename"),

                    "mime_type": _att.get("mime_type"),

                    "size_bytes": _att.get("size_bytes"),

                    "storage_root": _up["attachment"].get("storage_root"),

                    "relative_path": _up["attachment"].get("relative_path"),

                    "url": _att.get("url"),

                }

            _image_references["geometry_authority"] = "target_building"

            _image_count = len(_validated)

            _image_a = _role_files.get("A")

            _image_b = _role_files.get("B")

            # geometry authority = TARGET BUILDING (role B)
            uploaded_image = _image_b or _image_a

        else:

            # LEGACY single-image path.
            #
            # CHAT_UPLOAD_SINGLE_OWNER_V1 — the request boundary is now the ONE
            # owner of both the stored upload and the user-turn transcript
            # record. It stores the file ONCE and hands the stored path
            # downstream, which is an input shape this pipeline already
            # accepts (`_register_session_image`, `resolve_guard_source_identity`
            # and `handle_image_edit` all resolve a str/dict path, and the
            # source digest is computed from the same bytes either way).
            #
            # Why: the transcript record needs a servable /artifacts URL, and
            # only the component that performed the store can produce one. The
            # image handler used to store its own copy and record its own user
            # turn, so one upload produced TWO stored files and TWO user
            # transcript entries — one of them without a URL, which the UI
            # rendered as "attachment unavailable" after a refresh.
            uploaded_image = _legacy_image

            if _legacy_image is not None:

                _legacy_up = chat_attachment_service.save_upload(
                    _legacy_image,
                    source="user_upload",
                    kind="image",
                )

                if _legacy_up.get("status") == "ready":

                    _legacy_attachment = (
                        chat_attachment_service.public_attachment(
                            _legacy_up["attachment"]
                        )
                    )

                    uploaded_image = {
                        "path": _legacy_up["path"],
                        "attachment": _legacy_attachment,
                    }

                # A REJECTED upload keeps the raw handle so the image handler
                # reports exactly the rejection it always did. Nothing was
                # stored, so the record carries no attachment at all.
                else:

                    _legacy_rejected = True

            _image_count = 1 if _legacy_image is not None else 0

        data = {

            # LIVE_CHAT_PAYLOAD_CONTRACT_V1 — multipart clients historically
            # used both `text` (the browser UI contract) and `message` (the
            # public Chat submission spelling).  The multipart branch rebuilds
            # `data` field-by-field, so omitting the alias here discarded a
            # valid architectural instruction before `message` was resolved.
            # A non-empty canonical `text` remains authoritative.
            "text":
                request.form.get("text")
                or request.form.get("message", ""),


            "image":
                uploaded_image,


            # FACADE-02 — role-bound dual-image transport
            "image_a":
                _image_a,

            "image_b":
                _image_b,

            "image_references":
                _image_references,

            "image_count":
                _image_count,


            # PROJECT_WORKSPACE_UI_06 — the multipart upload path must
            # carry the same project + strategy context as JSON chat.
            "project_id":
                request.form.get("project_id"),

            "session_id":
                request.form.get("session_id"),

            "mode":
                request.form.get("mode"),

            "quality":
                request.form.get("quality"),

            "render_profile":
                request.form.get("render_profile"),

            "seed_mode":
                request.form.get("seed_mode"),

            "seed_value":
                request.form.get("seed_value"),

            "preserve_level":
                request.form.get("preserve_level"),

            # KNOWLEDGE_RECOVERY_01 — the multipart branch rebuilds `data`
            # field by field, so the precise-edit channel must be carried
            # here too or it would be dropped on every uploaded-image turn.
            "mask":
                request.form.get("mask"),

            "kontext_edit":
                request.form.get("kontext_edit"),

            "verify_render":
                request.form.get("verify_render"),

            # VISUAL_REFERENCE_UX_V2 — the reference the user selected in the
            # interface. The multipart branch rebuilds `data` field by field,
            # so it must be carried here or it would be dropped on every
            # uploaded-image turn (same failure mode as `mask`).
            "reference_id":
                request.form.get("reference_id"),

        }


        print(
            "📷 IMAGE UPLOAD RECEIVED:",
            uploaded_image,
            "| role-bound:",
            sorted(_image_references.keys()) if _image_references else "none",
            "| count:",
            _image_count,
        )



    else:


        data = request.get_json(
            silent=True
        ) or {}

    # ==================================================
    # FACADE-04D.3C-0 — CONDITIONED-RENDER OPT-IN VALIDATION
    #
    # A JSON body may carry the flag too, so it is honoured here as well.
    # Conditioned rendering requires BOTH role images (A = style reference,
    # B = target building). A request that asks for it without both is
    # REJECTED — it is never silently downgraded to an unconditioned or
    # text-to-image render.
    # ==================================================

    if _conditioned_form_value is None:

        _conditioned_form_value = data.get("conditioned_render")

    from core.render.dual_image_conditioning_v1 import (
        parse_conditioned_flag,
    )

    _conditioned_explicit = parse_conditioned_flag(
        _conditioned_form_value
    )

    _conditioned_render = None

    if _conditioned_explicit is True:

        _conditioned_ready = bool(
            isinstance(_image_references, dict)
            and _image_references.get("A")
            and _image_references.get("B")
        )

        if not _conditioned_ready:

            _conditioned_message = (
                "Conditioned facade rendering requires BOTH images: "
                "IMAGE A (style reference) and IMAGE B (target building). "
                "Attach both, or switch the conditioned option off."
            )

            return jsonify({

                "status": "error",

                "error": "conditioned_render_requires_both_images",

                "message": _conditioned_message,

                # The UI renders response.message, so the clear reason travels
                # in the same envelope shape as every other reply.
                "response": {
                    "status": "error",
                    "type": "conditioned_render_requires_both_images",
                    "message": _conditioned_message,
                },

            }), 400

        _conditioned_render = True

    data["conditioned_render"] = _conditioned_render



    message = (

        data.get(
            "text"
        )
        or
        data.get(
            "message",
            ""
        )

    ).strip()



    image = data.get(
        "image"
    )


    # ==================================================
    # VISUAL_REFERENCE_UX_V2 — EXPLICIT REFERENCE SELECTION
    #
    # The interface sends an IDENTIFIER, never a path. It is validated against
    # the accepted index and staged from the certified bytes (hash re-verified
    # on the way in). An explicit choice outranks any automatic ranking, so
    # this path never re-ranks and never substitutes another reference.
    #
    # A reference is STYLE GUIDANCE, not a source image: it is deliberately
    # NOT placed on the img2img / Kontext edit path.
    # ==================================================

    _reference_id_raw = str(data.get("reference_id") or "").strip()

    _uso_reference = None

    _uso_reference_meta = None

    if _reference_id_raw:

        # A reference is style guidance, not a source. Supplying both would
        # mean two different render intents in one turn, so it is refused
        # rather than silently resolved by precedence.
        if data.get("image") or data.get("image_a") or data.get("image_b"):

            return jsonify({

                "status": "reference_conflicts_with_source_image",

                "message": (
                    "A selected reference cannot be combined with an attached "
                    "source image. Use the reference alone for a new design, "
                    "or attach the image alone to edit it."
                ),

            }), 400

        from core.render import uso_reference_handoff_v1 as _uso_handoff

        from core.vision.visual_reference_index_v1 import load_default_index

        try:

            _reference_index = load_default_index()

        except Exception as _index_error:  # noqa: BLE001

            return jsonify({

                "status": "error",

                "message":
                    "reference index unavailable: %s" % (_index_error,),

            }), 503

        _prepared = _uso_handoff.prepare_explicit(

            _reference_id_raw,

            _reference_index,

            RC.COMFYUI_INPUT_DIR

        )

        if _prepared.get("status") != "ready":

            _selection = _prepared.get("selection") or {}

            return jsonify({

                "status": "reference_selection_blocked",

                "detail": _prepared.get("status"),

                "selection": _selection,

                "message": (
                    _selection.get("message")
                    or "the selected reference could not be used"
                ),

            }), 400

        _ref_entry = _prepared["reference"]

        _ref_staged = _prepared["staged"]

        _uso_reference = {

            "filename": _ref_staged["filename"],

            "reference_id": _ref_entry["reference_id"],

            "sha256": _ref_staged["sha256"],

            "selection_status": _prepared["selection"]["status"],

        }

        # Carried alongside so the render handoff can record lineage against
        # the prompt that is actually built, not a guessed one.
        _uso_reference_meta = {

            "selection": _prepared["selection"],

            "reference": _ref_entry,

            "staged": _ref_staged,

        }


    # FACADE-02 — role-bound reference assets extracted at the boundary.
    # All three are None/0 on the JSON (text-only) path, so no behaviour
    # changes there.
    image_a = data.get("image_a")

    image_b = data.get("image_b")

    image_references = data.get("image_references")

    image_count = data.get("image_count", 0)

    # FACADE-04D.3C-0 / REFERENCE_TRANSFER_POLICY_V1 — the explicit UI
    # choice, or None when the UI did not express one. None is NOT the same
    # as False: it authorises the render path to derive the graph from the
    # reference-transfer intent. `bool()` here would erase that distinction.
    conditioned_render = parse_conditioned_flag(
        data.get("conditioned_render")
    )

    # KNOWLEDGE_RECOVERY_01 — optional caller-supplied selection mask for the
    # precise (Kontext) instruction-edit route, plus its explicit opt-in.
    # Both are absent for every existing caller, so those turns are unchanged.
    # ArchitectOS never derives or approximates a mask: when the precise route
    # is requested without one the turn is refused rather than widened to a
    # whole-image edit.
    #
    # The mask arrives as a multipart form field, so it is normalised here to
    # the same asset shape the render layer already accepts for the source
    # image: a bare filename becomes {"filename": ...}, and a JSON object is
    # parsed as-is. No mask content is generated or modified.
    precision_controls_supplied = bool(
        "mask" in data or "kontext_edit" in data
    )

    edit_mask = data.get("mask")

    if isinstance(edit_mask, str):

        _raw_mask = edit_mask.strip()

        if _raw_mask.startswith("{"):

            try:

                edit_mask = json.loads(_raw_mask)

            except ValueError:

                edit_mask = {"filename": _raw_mask}

        else:

            edit_mask = {"filename": _raw_mask} if _raw_mask else None

    # Multipart form values arrive as strings, so the flag is parsed
    # explicitly rather than relying on truthiness ("false" is a non-empty
    # string). Absent => False, which is every existing caller.
    kontext_edit = str(
        data.get("kontext_edit", "")
    ).strip().lower() in ("1", "true", "yes", "on")

    verify_render = str(
        data.get("verify_render", "")
    ).strip().lower() in ("1", "true", "yes", "on")

    # PRODUCT_INTEGRATION_V1 — a UI-selected mask is an existing ComfyUI
    # input asset name, never an arbitrary filesystem path.  The render layer
    # consumes a filename; reject traversal/path-shaped values at the request
    # boundary instead of forwarding them as a LoadImageMask input.
    if isinstance(edit_mask, dict):

        _mask_filename = str(edit_mask.get("filename") or "").strip()

        if (
            not _mask_filename
            or "/" in _mask_filename
            or "\\" in _mask_filename
            or _mask_filename in (".", "..")
        ):

            return jsonify({
                "status": "error",
                "error": "invalid_mask_asset",
                "response": {
                    "status": "error",
                    "type": "invalid_mask_asset",
                    "message": (
                        "Mask must be the filename of an existing image in "
                        "the ComfyUI input folder."
                    ),
                },
            }), 400


    # ======================================================
    # PRECISE_EDIT_UI_V1 — MASK INGESTION, VALIDATION, AND ROUTE
    #
    # The UI could not originate a mask at all, so the precise (Kontext)
    # route was unreachable from the product even though the backend
    # supported it. Three rules apply here:
    #
    #  1. The client never names a filesystem path. A mask is either an
    #     EXISTING asset name in the ComfyUI input folder, or bytes uploaded
    #     on this request that the SERVER names.
    #  2. A mask must match the source image's dimensions. A mask authored
    #     for a different image would silently edit the wrong region.
    #  3. A supplied mask is a request for the precise route. It is never
    #     ignored: it selects Kontext, and an unusable mask is REFUSED with a
    #     clear reason rather than silently widening to a global redesign.
    # ======================================================

    def _mask_error(code, message):

        return jsonify({
            "status": "error",
            "error": code,
            "message": message,
            "response": {
                "status": "error",
                "type": code,
                "message": message,
            },
        }), 400

    def _source_image_size():
        """Dimensions of the image this mask will be applied to."""

        try:

            from PIL import Image as _Image

        except Exception:  # pragma: no cover - PIL is a hard dependency

            return None

        for _field in ("image_b", "image", "image_a"):

            _fs = request.files.get(_field)

            if _fs is None or not getattr(_fs, "filename", ""):

                continue

            try:

                _fs.stream.seek(0)

                with _Image.open(_fs.stream) as _im:

                    _size = _im.size

                _fs.stream.seek(0)

                return _size

            except Exception:

                try:

                    _fs.stream.seek(0)

                except Exception:

                    pass

                return None

        return None

    # ======================================================
    # MASK_SOURCE_BINDING_V1 — EFFECTIVE SOURCE IMAGE
    #
    # A mask is only meaningful against ONE image. The source this edit will
    # actually use is resolved here from, in order of authority:
    #
    #   1. an image uploaded on THIS request (role-bound B, then A) — already
    #      stored and validated above, so its on-disk path is trustworthy;
    #   2. the session's ACTIVE image in the existing registry — this is the
    #      path the edit layer itself edits, so a text-only follow-up can be
    #      bound to it (and, when there is none, must be refused);
    #   3. a legacy single-image upload present on this request, read as bytes
    #      because the chat layer stores it only later.
    #
    # The identity returned is a SHA-256 DIGEST of the image bytes, computed
    # server-side. Nothing a client sends is used as evidence.
    # ======================================================

    def _digest_of_path(_path):

        try:

            import hashlib as _hashlib

            _h = _hashlib.sha256()

            with open(_path, "rb") as _fh:

                for _chunk in iter(lambda: _fh.read(1024 * 1024), b""):

                    _h.update(_chunk)

            return _h.hexdigest(), os.path.getsize(_path)

        except Exception:

            return None, None

    def _digest_of_stream(_fs):

        if _fs is None or not getattr(_fs, "filename", ""):

            return None, None

        try:

            import hashlib as _hashlib

            _fs.stream.seek(0)

            _h = _hashlib.sha256()

            _total = 0

            while True:

                _chunk = _fs.stream.read(1024 * 1024)

                if not _chunk:

                    break

                _total += len(_chunk)

                _h.update(_chunk)

            _fs.stream.seek(0)

            return _h.hexdigest(), _total

        except Exception:

            return None, None

    def _mask_session_key():
        """The session key the image registry is keyed by for THIS request.

        Mask ingestion runs before the chat handler initialises `session_id`.
        Reading that variable here raised NameError, which the registry lookup
        below swallowed, so every text-only asset mask looked source-less.
        The key is resolved with the SAME precedence the handler uses later:
        an explicit project adopts the session id, otherwise the request's
        session id is used.
        """

        try:

            _project = (
                data.get("project_id")
                or request.headers.get("X-Project-Id")
            )

        except Exception:

            _project = None

        return _project or request_session_id(data)

    def _mask_provenance_path(_mask_path):

        return _mask_path + ".provenance.json"

    def _write_mask_provenance(
        _mask_path, _mask_digest, _mask_bytes,
        _source_digest, _source_bytes, _source_id, _source_path,
    ):
        """Record how the server validated this mask, next to the mask file.

        Only the server writes this record, and only after it opened the mask,
        measured it and resolved the source it is being bound to. An asset
        mask is later reusable ONLY when this record still matches both the
        mask bytes and the current source bytes.
        """

        _record = {
            "contract": "MaskSourceProvenanceV1",
            "mask_filename": os.path.basename(_mask_path),
            "mask_sha256": _mask_digest,
            "mask_size_bytes": _mask_bytes,
            "source_sha256": _source_digest,
            "source_size_bytes": _source_bytes,
            "source_image_id": _source_id,
            "source_path": _source_path,
            "validated_at": time.time(),
        }

        try:

            with open(
                _mask_provenance_path(_mask_path), "w", encoding="utf-8"
            ) as _fh:

                json.dump(_record, _fh, sort_keys=True)

            return True

        except Exception:

            # The current turn is still valid; only future reuse fails closed.
            return False

    def _verified_mask_provenance(_mask_path):
        """The server-written record for this mask, or None. Never client data."""

        try:

            with open(
                _mask_provenance_path(_mask_path), "r", encoding="utf-8"
            ) as _fh:

                _record = json.load(_fh)

        except Exception:

            return None

        if not isinstance(_record, dict):

            return None

        if _record.get("contract") != "MaskSourceProvenanceV1":

            return None

        return _record

    def _effective_source_identity():
        """(digest, size, image_id, path) of the image this edit will use.

        Any element may be None when it cannot be established. A None digest
        means NO trustworthy source, and the mask is then refused rather than
        bound to a guess.
        """

        # 1. an image uploaded on THIS request, already stored + validated
        for _role in ("B", "A"):

            _entry = (_image_references or {}).get(_role)

            if isinstance(_entry, dict) and _entry.get("path"):

                _d, _s = _digest_of_path(_entry.get("path"))

                if _d:

                    return _d, _s, _entry.get("asset_id"), _entry.get("path")

        # 2. the session's ACTIVE image — the path the edit layer itself uses
        try:

            from core.vision.image_registry_v1 import image_registry as _images

            _record = _images.active(_mask_session_key())

            if isinstance(_record, dict) and _record.get("path"):

                _d, _s = _digest_of_path(_record.get("path"))

                if _d:

                    return _d, _s, _record.get("image_id"), _record.get("path")

        except Exception:

            pass

        # 3. a legacy single-image upload on THIS request (bytes only)
        for _field in ("image_b", "image", "image_a"):

            _d, _s = _digest_of_stream(request.files.get(_field))

            if _d:

                # the chat layer stores these bytes as the session image, so
                # the digest matches whatever path it ends up at
                return _d, _s, None, None

        return None, None, None, None

    # MASK_ASSET_PROVENANCE_V1 — set ONLY by the branch below, after the
    # server itself read, measured and bound mask bytes. The `source` key on
    # a mask dict is caller data and a client may claim any value for it, so
    # it must never decide whether provenance verification is performed.
    _mask_staged_this_request = False

    _mask_upload = request.files.get("mask")

    if _mask_upload is not None and getattr(_mask_upload, "filename", ""):

        try:

            from PIL import Image as _Image

        except Exception:  # pragma: no cover

            _Image = None

        if _Image is None:

            return _mask_error(
                "mask_validation_unavailable",
                "Mask validation is unavailable on this host.",
            )

        try:

            _mask_upload.stream.seek(0)

            with _Image.open(_mask_upload.stream) as _mask_image:

                _mask_size = _mask_image.size

                _mask_mode = _mask_image.mode

                _mask_image.verify()

            _mask_upload.stream.seek(0)

        except Exception:

            return _mask_error(
                "invalid_mask_asset",
                "The mask could not be read as an image.",
            )

        _source_size = _source_image_size()

        if _source_size is not None and tuple(_source_size) != tuple(_mask_size):

            return _mask_error(
                "mask_dimension_mismatch",
                "The mask is %dx%d but the source image is %dx%d. "
                "A mask must be authored for the image being edited."
                % (_mask_size[0], _mask_size[1],
                   _source_size[0], _source_size[1]),
            )

        # MASK_SOURCE_BINDING_V1 — an uploaded mask is only usable when a
        # trustworthy source image exists to bind it to. Rather than trusting
        # the dimension check (which is skipped when the request carries no
        # image), the effective source is resolved and its bytes hashed here.
        _src_digest, _src_bytes, _src_id, _src_path = _effective_source_identity()

        if not _src_digest:

            return _mask_error(
                "mask_source_unbound",
                "This mask cannot be tied to the image being edited, so it "
                "has not been applied. Attach the image it belongs to, or "
                "select one already in the session.",
            )

        # an actual source was resolved on this request, so the dimension check
        # is mandatory rather than advisory
        if _source_size is not None and tuple(_source_size) != tuple(_mask_size):

            return _mask_error(
                "mask_dimension_mismatch",
                "The mask is %dx%d but the source image is %dx%d. "
                "A mask must be authored for the image being edited."
                % (_mask_size[0], _mask_size[1],
                   _source_size[0], _source_size[1]),
            )

        # The SERVER names the file: the client never contributes a path.
        import uuid as _uuid

        _mask_name = "architectos_mask_" + _uuid.uuid4().hex[:16] + ".png"

        _mask_target = os.path.join(
            RC.COMFYUI_INPUT_DIR,
            _mask_name,
        )

        try:

            _mask_upload.stream.seek(0)

            _mask_upload.save(_mask_target)

        except Exception as _mask_save_error:

            return _mask_error(
                "mask_staging_failed",
                "The mask could not be staged for rendering: %s"
                % (_mask_save_error,),
            )

        edit_mask = {
            "filename": _mask_name,
            "dimensions": [int(_mask_size[0]), int(_mask_size[1])],
            "mode": _mask_mode,
            "source": "uploaded",
            # server-computed binding evidence — the client never supplies these
            "source_sha256": _src_digest,
            "source_size_bytes": _src_bytes,
            "source_image_id": _src_id,
            "source_path": _src_path,
        }

        # MASK_ASSET_PROVENANCE_V1 — record that THIS mask file was validated
        # against THAT source, so an asset re-use can be re-verified later
        # instead of being re-bound to whatever image happens to be active.
        _mask_file_digest, _mask_file_bytes = _digest_of_path(_mask_target)

        if _mask_file_digest:

            _write_mask_provenance(
                _mask_target,
                _mask_file_digest,
                _mask_file_bytes,
                _src_digest,
                _src_bytes,
                _src_id,
                _src_path,
            )

        precision_controls_supplied = True

        _mask_staged_this_request = True

    # A mask supplied by asset name must exist and match the source image.
    # A mask staged from bytes on THIS request was already measured and bound
    # above; re-checking it here would treat it as an unverified asset. The
    # skip is keyed on the server-set flag, never on a field the request
    # supplies.
    if (
        isinstance(edit_mask, dict)
        and edit_mask.get("filename")
        and not _mask_staged_this_request
    ):

        _existing_mask_path = os.path.join(
            RC.COMFYUI_INPUT_DIR,
            str(edit_mask["filename"]),
        )

        if not os.path.isfile(_existing_mask_path):

            return _mask_error(
                "mask_asset_not_found",
                "The selected mask is not present in the ComfyUI input "
                "folder. Upload the mask with the request instead.",
            )

        try:

            from PIL import Image as _Image2

            with _Image2.open(_existing_mask_path) as _im2:

                _existing_size = _im2.size

        except Exception:

            return _mask_error(
                "invalid_mask_asset",
                "The selected mask could not be read as an image.",
            )

        # MASK_ASSET_PROVENANCE_V1 — an asset-name mask is NOT re-bound to
        # whatever image is active now. Binding it here would stamp the
        # current source's digest onto a mask authored for a different image;
        # identical dimensions do not change that. The ONLY accepted evidence
        # is a record the SERVER wrote when it validated this mask against a
        # source — and it must still match both the mask bytes and the source
        # bytes this turn will edit.
        #
        # Every provenance key the request supplied is dropped BEFORE the
        # decision, so no client value can survive into the guard context
        # even on a path that later refuses.
        for _claimed_key in (
            "source_sha256",
            "source_size_bytes",
            "source_image_id",
            "source_path",
            "source",
        ):

            edit_mask.pop(_claimed_key, None)

        _existing_digest, _existing_bytes = _digest_of_path(_existing_mask_path)

        if not _existing_digest:

            return _mask_error(
                "invalid_mask_asset",
                "The selected mask could not be read as an image.",
            )

        _provenance = _verified_mask_provenance(_existing_mask_path)

        if not _provenance:

            return _mask_error(
                "mask_provenance_unverified",
                "This mask was never validated by the server for an image, so "
                "it cannot be tied to the image being edited. Upload the mask "
                "with that image instead.",
            )

        if _provenance.get("mask_sha256") != _existing_digest:

            return _mask_error(
                "mask_provenance_unverified",
                "This mask changed after the server validated it, so it has "
                "not been applied. Upload the mask again with its image.",
            )

        _src2_digest, _src2_bytes, _src2_id, _src2_path = (
            _effective_source_identity()
        )

        if not _src2_digest:

            return _mask_error(
                "mask_source_unbound",
                "This mask cannot be tied to the image being edited, so it "
                "has not been applied. Attach the image it belongs to, or "
                "select one already in the session.",
            )

        if _provenance.get("source_sha256") != _src2_digest:

            return _mask_error(
                "mask_provenance_unverified",
                "This mask was validated for a different image, so it has not "
                "been applied. Upload a mask authored for the image being "
                "edited.",
            )

        _source_size2 = _source_image_size()

        if _source_size2 is not None and tuple(_source_size2) != tuple(_existing_size):

            return _mask_error(
                "mask_dimension_mismatch",
                "The mask is %dx%d but the source image is %dx%d."
                % (_existing_size[0], _existing_size[1],
                   _source_size2[0], _source_size2[1]),
            )

        # the guard re-hashes the source, so the binding evidence it sees is
        # always the server-derived one for THIS turn's source; anything the
        # request claimed is overwritten above
        edit_mask["source_sha256"] = _src2_digest
        edit_mask["source_size_bytes"] = _src2_bytes
        edit_mask["source_image_id"] = _src2_id
        edit_mask["source_path"] = _src2_path
        edit_mask["source"] = "asset_verified"

        edit_mask["dimensions"] = [
            int(_existing_size[0]),
            int(_existing_size[1]),
        ]

    # ======================================================
    # SOURCE / MASK IDENTITY SAFETY V1 — the last check before the
    # mask is allowed to select the precise route.
    #
    # Both branches above have already resolved the authoritative source
    # themselves (server-computed digest, never a client claim) and the mask
    # file this request will actually use. If those two are the same asset,
    # every other guard still agrees — dimensions match, provenance binds,
    # the composite exists — and the run is the recorded incident. Refuse.
    # ======================================================

    if isinstance(edit_mask, dict) and edit_mask.get("filename"):

        _collision_mask_path = os.path.join(
            RC.COMFYUI_INPUT_DIR,
            str(edit_mask["filename"]),
        )

        _collision_mask_digest, _ = _digest_of_path(_collision_mask_path)

        _collision_reason = source_mask_identity_collision(
            source_path=edit_mask.get("source_path"),
            source_digest=edit_mask.get("source_sha256"),
            mask_path=_collision_mask_path,
            mask_digest=_collision_mask_digest,
        )

        if _collision_reason:

            return _mask_error(
                "mask_source_identity_collision",
                "The mask and the image being edited resolve to the same "
                "asset (%s), so the edit would treat the mask as the "
                "building. Attach the original image as the source, or "
                "upload a mask authored for it."
                % _collision_reason,
            )

    # A mask IS a request for the precise route. Without this the workflow
    # selector silently fell back to the whole-image graph and discarded the
    # user's localisation.
    if isinstance(edit_mask, dict) and edit_mask.get("filename"):

        kontext_edit = True


    # ======================================================
    # FACADE-04D.3C-9P-B12 — TRUSTED USER GEOMETRY BOUNDARY
    #
    # The ONLY place a user geometry confirmation may originate. It is
    # derived from THIS turn's incoming `message` text — a value the API
    # boundary itself received from the user — and is NEVER read from the
    # request body. A client-supplied `user_geometry` field is ignored: only
    # text the boundary can see as the current user message is evidence.
    #
    # The extractor is deliberately narrow: it accepts a value ONLY when the
    # message EXPLICITLY asserts how many storeys the building has, with the
    # number adjacent to the floor noun. An unrelated numeral never becomes a
    # confirmation. When nothing explicit is present this stays None and
    # behaviour is byte-identical to 9P-B1.
    # ======================================================

    user_geometry = None

    try:

        from core.cognition.architectural_render_instruction_v1 import (
            user_geometry_from_messages,
        )

        user_geometry = user_geometry_from_messages(
            [{"role": "user", "text": message}]
        )

    except Exception as _e:

        print(
            "USER GEOMETRY BOUNDARY ERROR:",
            _e
        )

        user_geometry = None



    # LOGGING_FINAL_CORRECTION_01 — the former "DEBUG MESSAGE" dump wrote
    # the COMPLETE user message into the log, and "DEBUG IMAGE VALUE" wrote
    # the raw attachment handle. Only bounded shape metadata is emitted now:
    # never the message text, never the image payload.
    _log.info(
        "chat input | text_len=%d has_image=%s image=%s",
        len(message or ""),
        bool(image),
        _payload_shape(image, 80),
    )



    # LIVE_CHAT_PAYLOAD_CONTRACT_V1 — a manually selected image-edit route
    # requires an edit instruction.  An attachment by itself may still be
    # analysed by the existing Analyze Image mode, but it must never degrade
    # into a generic preservation render merely because its text was absent.
    _requested_mode = str(data.get("mode") or "").strip().lower()

    if not message and image and _requested_mode in (
        "image_to_image", "image-to-image", "i2i",
    ):

        _missing_instruction_message = (
            "برای ویرایش تصویر، دستور تغییر را نیز وارد کنید؛ "
            "رندر بدون دستور اجرا نشد."
        )

        return jsonify({

            "status": "error",

            "error": "missing_image_edit_instruction",

            "message": _missing_instruction_message,

            "response": {
                "status": "blocked",
                "type": "render_blocked",
                "reason": "missing_image_edit_instruction",
                "message": _missing_instruction_message,
                "generative": False,
            },

            "input": {
                "text": "",
                "has_image": True,
            },

        }), 400


    if not message and not image:


        return jsonify({

            "status":
                "error",

            "message":
                "empty input"

        })



    # ======================================================
    # CHAT RUNTIME DEBUG — ERROR ENVELOPE SHAPE
    #
    # These are assigned INSIDE the try below, but the failure
    # branch must be able to report the SAME envelope shape as the
    # success branch, so they are initialised here with their
    # neutral values. This changes no successful path.
    # ======================================================

    project_context = None

    strategy = {}

    save_state = None



    try:



        session_id = request_session_id(
            data
        )


        render_preset = request_render_preset(
            data
        )


        render_seed = request_render_seed(
            data
        )


        preserve_level = request_preserve_level(
            data
        )

        # I2I_CONCEPTUAL_ADMISSION_V1 — explicit, per-request consent for a
        # CONCEPTUAL architectural appearance edit. Absent => False => the
        # pre-existing R4 refusal stands unchanged.
        conceptual_edit = request_conceptual_edit(
            data
        )

        # PLAN_FIRST_PRODUCT_SLICE_V1 — opt-in conceptual spatial planning.
        # Absent => False => every existing route is unchanged.
        spatial_planning = request_spatial_planning(
            data
        )


        # ==================================================
        # PROJECT_WORKSPACE_UI_06 — PROJECT + RENDER STRATEGY
        #
        # A project id adopts the session id, so the session registry
        # and the image registry key 1:1 with the project and
        # cross-project leakage is structurally impossible.
        # ==================================================

        from core.project.project_session_v1 import project_session

        from core.render.render_strategy_controller_v1 import (
            resolve_strategy,
        )

        project_id = (
            data.get("project_id")
            or request.headers.get("X-Project-Id")
        )

        project_context = None

        if project_id:

            if project_session.current_project_id() != project_id:

                opened = project_session.open(project_id)

                if not opened:

                    return jsonify({
                        "status": "error",
                        "error": "project_not_found",
                        "project_id": project_id,
                    }), 404

            session_id = project_id

            project_context = project_id

        strategy = resolve_strategy(
            user_text=message,
            requested_mode=data.get("mode"),
            requested_profile=data.get("quality") or data.get("render_profile"),
            seed_mode=data.get("seed_mode"),
            seed_value=data.get("seed_value"),
            render_id=render_seed,
        )

        if strategy.get("blocked"):

            # A disabled mode must never silently execute another route.
            return jsonify({
                "status": "error",
                "error": strategy.get("blocked_reason"),
                "response": {
                    "type": "mode_unavailable",
                    "status": "blocked",
                    "message": strategy.get("message"),
                    "requested_mode": strategy.get("requested_mode"),
                    "active_modes": strategy.get("active_modes"),
                    "reserved_modes": strategy.get("reserved_modes"),
                },
            }), 400

        # The controller validates fields; it never edits a node graph.
        if strategy.get("steps") is not None:

            render_preset = render_preset or None

        if strategy.get("seed") is not None and not render_seed:

            render_seed = strategy.get("seed")


        # ==================================================
        # PROJECT_WORKSPACE_UI_06 — RECORD THE USER TURN
        #
        # Recorded at the API boundary so the workspace chat history
        # survives a restart. This is the SINGLE owner of the user turn:
        # the image handler no longer records a second copy of it.
        #
        # CHAT_UPLOAD_SINGLE_OWNER_V1 — each record carries the VALIDATED
        # attachment (servable /artifacts URL included), because the UI
        # re-renders stored history from these fields. A record without a
        # URL renders as "attachment unavailable" even though the file is
        # still on disk.
        # ==================================================

        _material_review_message_ref = None
        _material_review_attachment_ids = []

        if project_context:

            from core.chat.session_registry_v1 import session_registry

            _bundle = session_registry.resolve(session_id)

            _state = _bundle.get("conversation_state")

            if _state is not None:

                _attachments = []

                if image_references:

                    # FACADE-02 — record BOTH role-bound attachments so a
                    # dual-image turn is not silently reduced to one.
                    for _role in ("A", "B"):

                        _entry = image_references.get(_role)

                        if isinstance(_entry, dict):

                            _url = _entry.get("url")

                            _attachments.append({
                                "id": _entry.get("asset_id"),
                                "kind": "image",
                                "mime_type": _entry.get("mime_type"),
                                "filename": _entry.get("filename"),
                                "display_name": _entry.get("filename"),
                                "url": _url,
                                "thumbnail_url": _url,
                                "size_bytes": _entry.get("size_bytes"),
                                "source": "user_upload",
                                "status": "ready",
                                "role": _entry.get("role"),
                            })

                elif _legacy_attachment:

                    _attachments = [dict(_legacy_attachment)]

                elif image is not None and not _legacy_rejected:

                    _attachments = [{
                        "kind": "image",
                        "display_name": getattr(image, "filename", None),
                    }]

                _state.add_message("user", message, _attachments)

                # DURABLE MATERIAL CORRECTION REVIEW CARRIER V1 — bind any
                # later structured review to the server-recorded current user
                # turn. This reference is never accepted from request metadata.
                from core.project.conversation_store_v1 import conversation_store

                _snapshot = _state.get() if hasattr(_state, "get") else {}
                _messages = (
                    _snapshot.get("messages")
                    if isinstance(_snapshot, dict)
                    else None
                )
                if isinstance(_messages, list) and _messages:
                    _material_review_message_ref = conversation_store.message_ref(
                        _messages, len(_messages) - 1
                    )
                _material_review_attachment_ids = [
                    str(item.get("id"))
                    for item in _attachments
                    if isinstance(item, dict) and item.get("id") is not None
                ]


        if image:


            result = chat.handle(

                message,

                context={

                "image":
                    image,


                # FACADE-02 — validated A/B reference assets. None on the
                # legacy single-image path, so the contract reads exactly
                # as it did before.
                "references":
                    image_references,


                "image_a":
                    image_a,

                "image_b":
                    image_b,

                "image_count":
                    image_count,


                # FACADE-04D.3C-0 — explicit user opt-in for conditioned
                # facade rendering. Only ever True when the user selected it
                # AND both role images were validated at the boundary. It
                # travels through the existing render-approval and
                # FACADE-04A fidelity gates without bypassing either.
                "conditioned_render":
                    conditioned_render,


                # KNOWLEDGE_RECOVERY_01 — precise instruction-edit channel.
                # `mask` is a caller-supplied selection; `kontext_edit` opts
                # into the GPU-verified Kontext workflow. Both default to
                # absent/False, so every existing turn is unchanged.
                "mask":
                    edit_mask,

                "kontext_edit":
                    kontext_edit,


                "session_id":
                    session_id,

                "trusted_local_authorization":
                    _trusted_local_authorization,

                "approval_capability":
                    (_authorization_payload or {}).get("approval_capability"),


                "preset":
                    render_preset,


                "seed":
                    render_seed,


                "preserve_level":
                    preserve_level,

                # I2I_CONCEPTUAL_ADMISSION_V1 — explicit conceptual-edit
                # consent. False for every existing caller.
                "conceptual_edit":
                    conceptual_edit,

                # PLAN_FIRST_PRODUCT_SLICE_V1
                "spatial_planning":
                    spatial_planning,


                # FACADE-04D.3C-9P-B12 — trusted user geometry confirmation
                # derived at THIS boundary from the current user message.
                # None unless the user explicitly stated the storey count.
                "user_geometry":
                    user_geometry,


                # PROJECT_WORKSPACE_UI_06 — validated strategy
                "render_profile":
                    strategy.get("render_profile"),

                "mode":
                    strategy.get("resolved_mode"),

                "routing_source":
                    strategy.get("routing_source"),

                "verify_render":
                    verify_render,

                "precision_controls_supplied":
                    precision_controls_supplied

                }

            ) 


        else:


            result = chat.handle(

                message,

                context={

                    "session_id":
                        session_id,

                    "trusted_local_authorization":
                        _trusted_local_authorization,

                    "approval_capability":
                        (_authorization_payload or {}).get("approval_capability"),


                    "preset":
                        render_preset,


                    "seed":
                        render_seed,


                    "preserve_level":
                        preserve_level,

                    # I2I_CONCEPTUAL_ADMISSION_V1
                    "conceptual_edit":
                        conceptual_edit,

                    # PLAN_FIRST_PRODUCT_SLICE_V1
                    "spatial_planning":
                        spatial_planning,


                    # FACADE-04D.3C-9P-B12 — trusted user geometry
                    # confirmation, derived from the current user message.
                    "user_geometry":
                        user_geometry,


                    # PROJECT_WORKSPACE_UI_06 — validated strategy
                    "render_profile":
                        strategy.get("render_profile"),

                    "mode":
                        strategy.get("resolved_mode"),

                    "routing_source":
                        strategy.get("routing_source"),

                    # FACADE-04D.3C-0 — explicit conditioned-render opt-in.
                    # Always False on a text-only turn (it can carry no role
                    # images), so the context shape stays uniform.
                    "conditioned_render":
                        conditioned_render,

                    # PRODUCT_INTEGRATION_V1 — a text-only revision can carry
                    # the same explicit precision controls as its first turn.
                    "mask":
                        edit_mask,

                    "kontext_edit":
                        kontext_edit,

                    "verify_render":
                        verify_render,

                    "precision_controls_supplied":
                        precision_controls_supplied,

                    # VISUAL_REFERENCE_UX_V2 — the reference the user
                    # explicitly selected, already resolved through the
                    # accepted index and staged from certified bytes.
                    # None on every turn without a selection.
                    "uso_reference":
                        _uso_reference,

                    "uso_reference_meta":
                        _uso_reference_meta

                }

            )


        # LOGGING_FINAL_CORRECTION_01 — this was the raw model-response
        # dump: 470,723 bytes in ONE measured image-analysis turn. Only
        # bounded metadata (type / status / duration / payload SHAPE) is
        # emitted now; the raw result is never written to the log.
        _log.info(
            "chat result | session=%s type=%s status=%s duration_ms=%.1f shape=%s",
            session_id,
            _bounded(
                (result or {}).get("type")
                if isinstance(result, dict)
                else type(result).__name__,
                60,
            ),
            _bounded(
                (result or {}).get("status")
                if isinstance(result, dict)
                else "",
                60,
            ),
            (time.perf_counter() - _t0) * 1000.0,
            _payload_shape(result),
        )



        formatted_response = response_adapter.adapt(
            result
        )

        # ==================================================
        # MULTIFLOOR_ENGINE_V2_CHAT_PLAN_ROUTING
        #
        # The adapter owns the human message; the drawing payload is
        # structural and must reach the client untouched so the
        # transcript can render the SVG sheet. Passed through here
        # rather than through the adapter's plan_drawing contract,
        # which is the legacy room-graph shape and validates its own
        # fields.
        # ==================================================
        if (
            isinstance(result, dict)
            and isinstance(result.get("plan_drawing_v2"), dict)
            and isinstance(formatted_response, dict)
        ):

            formatted_response["plan_drawing_v2"] = result["plan_drawing_v2"]

        # IMAGE_MODE_ROUTING_CONTRACT — one authoritative, completed-turn
        # classification for API clients and the UI.  It observes the native
        # result only; request strategy remains a render-setting concern.
        from core.vision.image_intent_v1 import build_mode_contract

        routing = build_mode_contract(
            formatted_response,
            has_image=bool(image),
        )

        def collect_output_paths(value):
            paths = []
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"path", "file", "output_dir", "cad_asset", "ifc_asset"} and isinstance(item, str):
                        paths.append(item)
                    else:
                        paths.extend(collect_output_paths(item))
            elif isinstance(value, list):
                for item in value:
                    paths.extend(collect_output_paths(item))
            return list(dict.fromkeys(paths))


        # LOGGING_FINAL_CORRECTION_01 — this was the raw adapted-response
        # dump: 467,113 bytes in the same measured turn. Bounded metadata
        # only; the response payload is never written to the log.
        _log.info(
            "chat response | session=%s type=%s status=%s duration_ms=%.1f shape=%s",
            session_id,
            _bounded(
                (formatted_response or {}).get("type")
                if isinstance(formatted_response, dict)
                else type(formatted_response).__name__,
                60,
            ),
            _bounded(
                (formatted_response or {}).get("status")
                if isinstance(formatted_response, dict)
                else "",
                60,
            ),
            (time.perf_counter() - _t0) * 1000.0,
            _payload_shape(formatted_response),
        )


        # ==================================================
        # PROJECT_WORKSPACE_UI_06 — AUTOSAVE
        #
        # Autosave after every meaningful state change. A chat turn can
        # contain a user message, an upload, a render completion, an
        # img2img completion and an asset activation, so one autosave
        # here covers the whole turn. The save state is only reported
        # as `saved` after the atomic write actually succeeded.
        # ==================================================

        save_state = None

        if project_context:

            # DURABLE MATERIAL CORRECTION REVIEW CARRIER V1 — the adapted
            # response retains the trusted structured interpretation. Capture
            # only a validated pending material review in ConversationState;
            # the established project autosave below writes the same chat.json.
            # No confirmation, actor, ledger path or admission is created here.
            try:
                from core.project.conversation_store_v1 import conversation_store

                _interpretation = (
                    (formatted_response or {}).get("architectural_interpretation")
                    if isinstance(formatted_response, dict)
                    else None
                )
                _material_connection = (
                    _interpretation.get(
                        "architectural_material_knowledge_connection"
                    )
                    if isinstance(_interpretation, dict)
                    else None
                )
                if (
                    isinstance(_material_connection, dict)
                    and _material_connection.get("status")
                    == "MATERIAL_CORRECTION_PENDING_CONFIRMATION"
                ):
                    _state = session_registry.resolve(
                        session_id
                    ).get("conversation_state")
                    _carrier = conversation_store.build_material_correction_review_carrier(
                        project_id=project_context,
                        session_id=session_id,
                        message_ref=_material_review_message_ref,
                        message_text=message,
                        connection=_material_connection,
                        attachment_ids=_material_review_attachment_ids,
                    )
                    conversation_store.remember_material_correction_review(
                        _state,
                        _carrier,
                        project_id=project_context,
                        session_id=session_id,
                    )
            except ValueError as _material_review_error:
                # Fail closed: malformed or ungrounded review context is not
                # persisted and can never be recovered as pending.
                _log.warning(
                    "material review carrier rejected | project=%s reason=%s",
                    project_context,
                    _bounded(_material_review_error, 200),
                )
            except Exception as _material_review_error:
                _log.warning(
                    "material review carrier unavailable | project=%s error=%s",
                    project_context,
                    _bounded(type(_material_review_error).__name__, 80),
                )

            response_type = str(
                (formatted_response or {}).get("type") or ""
            )

            # Assistant text replies are recorded here; render and
            # upload turns already record their own assistant message.
            if "render" not in response_type and "upload" not in response_type:

                from core.chat.session_registry_v1 import session_registry

                _state = session_registry.resolve(
                    session_id
                ).get("conversation_state")

                if _state is not None:

                    _text = (
                        (formatted_response or {}).get("result")
                        or (formatted_response or {}).get("message")
                        or ""
                    )

                    if _text:

                        _state.add_message("assistant", str(_text))

            if "render" in response_type:

                reason = "render_complete"

            elif image:

                reason = "upload"

            else:

                reason = "assistant_response"

            save_state = project_session.autosave(
                project_context, reason=reason
            )


        # ==================================================
        # CHAT_ENVELOPE_STATUS_TRUTH_V1
        #
        # The envelope's top-level `status` is the OUTCOME OF THE TURN, which
        # is what every other ArchitectOS endpoint returns and what the UI
        # branches on (`ui/static/app.js: payload.status === "error"`).
        #
        # It used to be the constant "success", so a turn whose own response
        # status was "error" — a rejected image, a failed dispatch — reached
        # the UI as a success. The UI then took its success branch and printed
        # `response.message`, which for a rejected upload is a
        # success-sounding sentence. The failure branch could never fire.
        #
        # Only "error" is promoted: "waiting_for_instruction" (a normal
        # interactive state) and "degraded" (a truthful apology that is still
        # a delivered answer) keep their existing top-level treatment.
        # ==================================================

        from core.chat.response_contract import envelope_status_for

        _envelope_status = envelope_status_for(formatted_response)

        return jsonify({

            "status":
                _envelope_status,

            "response":
                json_safe(
                    formatted_response
                ),

            "input": {
                "text": message,
                "has_image": bool(image),
            },

            "outputs": {
                "paths": collect_output_paths(formatted_response),
            },

            "routing": routing,

            # ---- PROJECT_WORKSPACE_UI_06 ----
            "project_id": project_context,

            "strategy": {
                "requested_mode": strategy.get("requested_mode"),
                "resolved_mode": strategy.get("resolved_mode"),
                "routing_source": strategy.get("routing_source"),
                "render_profile": strategy.get("render_profile"),
                "profile_source": strategy.get("profile_source"),
                "seed_mode": strategy.get("seed_mode"),
                "seed": strategy.get("seed"),
                "requires_quality_override": strategy.get(
                    "requires_quality_override"
                ),
                "mutates_node_graph": False,
            },

            "save_state": save_state,

        })



    except Exception as e:


        import traceback


        # LOGGING_FINAL_CORRECTION_01 — bounded error CATEGORY. The full
        # traceback below is preserved unchanged and still reaches the
        # configured logger (traceback.print_exc() -> sys.stderr ->
        # _LoggingStream -> root -> bounded RotatingFileHandler).
        # locals() is used because session_id is assigned inside the try.
        _log.error(
            "chat failed | session=%s category=%s detail=%s",
            locals().get("session_id"),
            type(e).__name__,
            _bounded(e, 200),
        )


        traceback.print_exc()


        # ==================================================
        # CHAT RUNTIME DEBUG — ERROR ENVELOPE SHAPE
        #
        # This branch used to return ONLY {status, error}. The UI
        # reads `payload.response.message`, so a server-side failure
        # surfaced the RAW Python exception string as the assistant's
        # chat reply (observed live:
        # "'Brain' object has no attribute '_chat_response'"), and the
        # turn was silently dropped from the conversation store.
        #
        # The failure branch now returns the SAME envelope shape as
        # the success branch. `status` stays "error" and the `error`
        # diagnostic is preserved, so every existing consumer keeps
        # working — the change is purely additive.
        #
        # HTTP status stays 200 deliberately: the UI's api() helper
        # already branches on payload.status, and changing the code
        # would alter existing client behaviour for no gain.
        # ==================================================

        _failed_text = str(message or "")

        _failed_is_persian = any(
            "\u0600" <= _char <= "\u06FF" for _char in _failed_text
        )

        return jsonify({

            "status":
                "error",

            "error":
                str(e),

            "response": {

                "status": "error",

                "type": "chat_error",

                "engine": "core_api_error_boundary",

                # User-facing text only. The diagnostic stays in
                # `error` (and `response.error`) so the boundary
                # never shows a raw exception as a chat reply.
                "message": (
                    "پردازش این درخواست ممکن نشد. "
                    "لطفاً دوباره تلاش کنید."
                    if _failed_is_persian
                    else "The request could not be processed. "
                         "Please try again."
                ),

                "error": str(e),

                "render_requested": False,

                "permanent_learning": False,

            },

            "input": {

                "text": message,

                "has_image": bool(image),

            },

            "outputs": {

                "paths": [],

            },

            "project_id": project_context,

            "strategy": {

                "requested_mode": (strategy or {}).get(
                    "requested_mode"
                ),

                "resolved_mode": (strategy or {}).get(
                    "resolved_mode"
                ),

                "routing_source": (strategy or {}).get(
                    "routing_source"
                ),

                "render_profile": (strategy or {}).get(
                    "render_profile"
                ),

                "profile_source": (strategy or {}).get(
                    "profile_source"
                ),

                "seed_mode": (strategy or {}).get(
                    "seed_mode"
                ),

                "seed": (strategy or {}).get(
                    "seed"
                ),

                "requires_quality_override": (strategy or {}).get(
                    "requires_quality_override"
                ),

                "mutates_node_graph": False,

            },

            "save_state": save_state,

        })







# ==========================================================
# CONFIRM
# ==========================================================


@app.route(
    "/confirm",
    methods=["POST"]
)
def confirm_api():


    data = request.get_json(
        silent=True
    ) or {}



    message = data.get(
        "message",
        ""
    )



    try:


        result = chat.handle(

            message,

            context={

                "session_id":
                    request_session_id(data)

            }

        )


        formatted_response = response_adapter.adapt(
            result
        )



        return jsonify({

            "status":
                "success",

            "response":
                json_safe(
                    formatted_response
                )

        })


    except Exception as e:


        import traceback


        traceback.print_exc()



        return jsonify({

            "status":
                "error",

            "error":
                str(e)

        })



# ==========================================================
# IMAGE UPLOAD
# ==========================================================

@app.route(
    "/image",
    methods=["POST"]
)
def image_upload_api():

    try:

        image = request.files.get(
            "image"
        )


        if not image:

            return jsonify({

                "status": "error",

                "message": "no image received"

            }),400



        result = chat.handle({

            "text":
                "",

            "image":
                image

        },

            context={

                "image":
                    image,

                "session_id":
                    request_session_id()

            }

        )


        formatted_response = response_adapter.adapt(
            result
        )


        return jsonify({

            "status":
                "success",

            "response":
                json_safe(
                    formatted_response
                )

        })


    except Exception as e:

        import traceback

        traceback.print_exc()


        return jsonify({

            "status":
                "error",

            "error":
                str(e)

        }),500



# ==========================================================
# FILE INTELLIGENCE + BIM IMPORT
# ==========================================================


@app.route(
    "/file",
    methods=["POST"]
)
def file_upload_api():

    try:

        uploaded_file = request.files.get(
            "file"
        )


        if not uploaded_file:

            return jsonify({

                "status":
                    "error",

                "message":
                    "no file received"

            }),400


        chat_upload = chat_attachment_service.save_upload(
            uploaded_file,
            source="user_upload",
            kind="file"
        )


        if chat_upload.get("status") != "ready":

            return jsonify({
                "status": "error",
                "message": chat_upload.get("error", "file_attachment_failed")
            }),400


        attachment = chat_attachment_service.public_attachment(
            chat_upload["attachment"]
        )


        conversation_state.add_message(
            "user",
            "",
            [attachment]
        )



        from core.integration.file_upload_adapter import (
            FileUploadAdapter
        )


        from core.intelligence.file_intelligence_router import (
            FileIntelligenceRouter
        )


        from core.integration.file_bim_bridge import (
            FileBIMBridge
        )



        # ==================================================
        # FILE ADAPTER
        # ==================================================

        adapter = FileUploadAdapter()


        upload_contract = adapter.adapt(
            uploaded_file
        )



        print(
            "📦 FILE CONTRACT:",
            upload_contract
        )



        # ==================================================
        # FILE INTELLIGENCE
        # ==================================================

        file_router = FileIntelligenceRouter()


        file_result = file_router.process(

            upload_contract["filename"],

            {

                "filename":
                    upload_contract["filename"],


                "extension":
                    upload_contract["extension"],


                "content_type":
                    upload_contract["content_type"],


                "file_object":
                    upload_contract["file_object"]

            }

        )


        file_result["attachments"] = [attachment]



        print(
            "🧠 FILE INTELLIGENCE RESULT:",
            file_result.get("type")
        )



        # ==================================================
        # BIM PIPELINE
        # ==================================================

        if file_result.get("type") in [

            "ifc",

            "rvt",

            "cad"

        ]:


            print(
                "🏗️ BIM IMPORT START"
            )


            bridge = FileBIMBridge()


            file_result["bim"] = (

                bridge.run_bim(
                    file_result
                )

            )


            print(
                "🏗️ BIM IMPORT COMPLETE"
            )



        formatted_response = response_adapter.adapt(
            file_result
        )


        return jsonify({

            "status":
                "success",

            "response":
                json_safe(
                    formatted_response
                )

        })



    except Exception as e:


        import traceback


        traceback.print_exc()


        return jsonify({

            "status":

                "error",


            "error":

                str(e)

        }),500



# ==========================================================
# MULTI-FLOOR FURNISHED PLAN ENGINE V2
# ==========================================================
# core/planning/multifloor_v1 is a self-contained package that resolves its own
# modules through bare imports ("engine"). Its root therefore has to be on
# sys.path while it loads, but a lingering entry would let its "ui" and
# "engine" directories shadow this project's ui.* and core.* namespaces, so the
# insertion is scoped and removed again before anything else runs.

_MULTIFLOOR_ROOT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "core",
    "planning",
    "multifloor_v1",
)

# KROCKI_GLOBAL_STATE_V27_1 — the package root, used to locate
# `data/projects/_global_active_krocki.json`.
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

_MULTIFLOOR_PLANS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "outputs",
    "plans",
)

_MULTIFLOOR_MODULES = None

# Canonical prompts shipped with the V2 engine. `preset` is a convenience
# shorthand; free-form `prompt` text always takes precedence.
_MULTIFLOOR_PRESETS = {
    "villa": "یک ساختمان یک طبقه ویلایی طراحی کن",
    "duplex": "یک ساختمان دوبلکس 120 متری در هر طبقه طراحی کن",
    "mixed": (
        "یک ساختمان 4 طبقه مختلط تجاری مسکونی با زیرزمین پارکینگ "
        "و سطح اشغال متفاوت طراحی کن"
    ),
    "north60": (
        "60 درصد محل احداث تو شمال با یه حیاط خلوت به عمق 1.7 متر با مساحت "
        "12 متر مربع برای نورگیری بزاره زمین هم 10*20 سه طرف پلاک هست شمال "
        "شرق و غرب پلاک و جنوب کوچه 10 متری"
    ),
}


def _load_multifloor_engine():
    """Import the planning engine once, leaving sys.path exactly as it was."""
    global _MULTIFLOOR_MODULES
    if _MULTIFLOOR_MODULES is not None:
        return _MULTIFLOOR_MODULES

    import importlib
    import sys as _sys

    root = _MULTIFLOOR_ROOT
    if not os.path.isdir(root):
        raise RuntimeError("multifloor_engine_missing: %s" % root)

    if root not in _sys.path:
        _sys.path.insert(0, root)
    try:
        engine = importlib.import_module("engine")
    finally:
        while root in _sys.path:
            _sys.path.remove(root)

    origin = os.path.abspath(getattr(engine, "__file__", "") or "")
    if not origin.startswith(os.path.abspath(root) + os.sep):
        raise RuntimeError("multifloor_engine_origin_mismatch: %s" % origin)

    _MULTIFLOOR_MODULES = engine
    return _MULTIFLOOR_MODULES


@app.route("/planning/studio", methods=["GET"])
def planning_studio():
    """Serve the multi-floor planning studio UI."""
    ui_path = os.path.join(_MULTIFLOOR_ROOT, "ui", "studio.html")
    if not os.path.isfile(ui_path):
        return jsonify({"status": "error", "error": "studio_ui_missing"}), 404
    return send_file(ui_path, mimetype="text/html", max_age=0)


@app.route("/planning/drawing/<path:filename>", methods=["GET"])
def planning_drawing(filename):
    """Serve a generated plan sheet (SVG/DXF) from outputs/plans.

    Confined to that one directory: the resolved path must stay inside it, so
    a traversal attempt cannot reach the rest of the repository.
    """
    if not os.path.isdir(_MULTIFLOOR_PLANS_DIR):
        return jsonify({"status": "error", "error": "plans_dir_missing"}), 404

    root = os.path.abspath(_MULTIFLOOR_PLANS_DIR)
    target = os.path.abspath(os.path.join(root, filename))

    if target != root and not target.startswith(root + os.sep):
        return jsonify({"status": "error", "error": "forbidden_path"}), 403

    if not os.path.isfile(target):
        return jsonify({"status": "error", "error": "drawing_not_found"}), 404

    if target.lower().endswith(".svg"):
        mimetype = "image/svg+xml"
    elif target.lower().endswith(".png"):
        mimetype = "image/png"
    elif target.lower().endswith(".json"):
        mimetype = "application/json"
    else:
        mimetype = "application/dxf"
    return send_file(target, mimetype=mimetype, max_age=0)


@app.route("/api/planning/solve", methods=["POST"])
def planning_solve():
    """Synthesize a furnished floor plan; return JSON + SVG + DXF content."""
    try:
        engine = _load_multifloor_engine()
    except Exception as exc:
        return jsonify({
            "status": "error",
            "error": "engine_unavailable",
            "detail": str(exc),
        }), 503

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        preset = str(payload.get("preset") or "").strip()
        if preset:
            if preset not in _MULTIFLOOR_PRESETS:
                return jsonify({
                    "status": "error",
                    "error": "unknown_preset",
                    "allowed": sorted(_MULTIFLOOR_PRESETS),
                }), 400
            prompt = _MULTIFLOOR_PRESETS[preset]
        else:
            prompt = _MULTIFLOOR_PRESETS["north60"]

    try:
        project = engine.ArchitecturalPlanSynthesizer().synthesize_from_text(prompt)
    except Exception as exc:
        return jsonify({
            "status": "error",
            "error": "synthesis_failed",
            "detail": str(exc),
        }), 500

    svg_str = engine.export_project_to_svg(project)
    dxf_str = engine.export_project_to_dxf(project)

    os.makedirs(_MULTIFLOOR_PLANS_DIR, exist_ok=True)
    project_id = str(project.project_id or "ARCH_PROJECT")
    svg_path = os.path.join(_MULTIFLOOR_PLANS_DIR, project_id + ".svg")
    dxf_path = os.path.join(_MULTIFLOOR_PLANS_DIR, project_id + ".dxf")
    with open(svg_path, "w", encoding="utf-8") as handle:
        handle.write(svg_str)
    with open(dxf_path, "w", encoding="utf-8") as handle:
        handle.write(dxf_str)

    body = json.loads(engine.export_project_to_json(project))
    body["prompt"] = prompt
    body["saved_files"] = {
        "svg": os.path.abspath(svg_path),
        "dxf": os.path.abspath(dxf_path),
    }
    body["svg_url"] = "/planning/drawing/" + os.path.basename(svg_path)
    body["svg_content"] = svg_str
    body["dxf_content"] = dxf_str
    return jsonify(body)


# ==========================================================
# V25 PLAN SESSION — MULTI-TURN PLAN EDITING & RENDER HANDOFF
# ==========================================================
# New, additive routes. `/api/planning/solve` above is untouched, so every
# existing caller keeps its current behaviour byte for byte.


def _v25_session_module():
    from core.planning import plan_session_v25

    return plan_session_v25


def _krocki_module():
    """The v27 land-survey reader.

    Installed at `core/site/krocki_cad_reader_v27.py`; the plan engine also
    ships a copy, so the canonical `core.site` one is preferred and the
    engine copy is the fallback.
    """

    try:

        from core.site import krocki_cad_reader_v27

        return krocki_cad_reader_v27

    except Exception:

        from core.planning.multifloor_v1.engine import krocki_cad_reader_v27

        return krocki_cad_reader_v27


def _v25_project_id(payload):
    raw = payload.get("project_id") or payload.get("session_id") or "default"
    return str(raw)


@app.route("/api/plan/turn", methods=["POST"])
def plan_turn_v25():
    """Create or incrementally edit the active parametric plan.

    Always answers with the re-synthesized plan image and clickable
    svg/dxf/png/json links — never a text-only acknowledgement.
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    text = str(payload.get("prompt") or payload.get("message") or "").strip()
    if not text:
        return jsonify({
            "status": "error",
            "error": "empty_prompt",
            "contract": "V25PlanSessionV1",
        }), 400

    try:
        session = _v25_session_module()
    except Exception as exc:
        return jsonify({
            "status": "error",
            "error": "engine_unavailable",
            "detail": str(exc),
        }), 503

    project_id = _v25_project_id(payload)

    try:
        result = session.route_plan_turn(project_id, text)
    except Exception as exc:
        return jsonify({
            "status": "error",
            "error": "plan_turn_failed",
            "detail": str(exc),
            "project_id": project_id,
        }), 500

    result["project_id"] = project_id

    if result.get("status") == "not_a_plan_turn":
        return jsonify(result), 422

    return jsonify(result)


@app.route("/api/render/turn", methods=["POST"])
def render_turn_v25():
    """Resolve a render request against the active plan / previous render.

    Returns the dispatch decision: which chain, at which floors/style/
    materials/camera, and whether the locked night relight applies.
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    text = str(payload.get("prompt") or payload.get("message") or "").strip()
    if not text:
        return jsonify({
            "status": "error",
            "error": "empty_prompt",
            "contract": "V25PlanSessionV1",
        }), 400

    try:
        session = _v25_session_module()
    except Exception as exc:
        return jsonify({
            "status": "error",
            "error": "engine_unavailable",
            "detail": str(exc),
        }), 503

    project_id = _v25_project_id(payload)

    try:
        result = session.route_render_turn(project_id, text)
    except Exception as exc:
        return jsonify({
            "status": "error",
            "error": "render_turn_failed",
            "detail": str(exc),
            "project_id": project_id,
        }), 500

    result["project_id"] = project_id

    if result.get("status") == "no_plan":
        return jsonify(result), 409

    return jsonify(result)


@app.route("/api/plan/session", methods=["GET"])
def plan_session_state_v25():
    """Read the persisted session state for one project (no synthesis)."""
    project_id = str(request.args.get("project_id") or "default")

    try:
        session = _v25_session_module()
    except Exception as exc:
        return jsonify({
            "status": "error",
            "error": "engine_unavailable",
            "detail": str(exc),
        }), 503

    state = session.load_state(project_id)
    state["project_id"] = project_id

    return jsonify(state)


# ==========================================================
# KROCKI_INGEST_V27_3 — ONE ingest path for every transport
#
# A survey can arrive two ways: as a multipart upload on
# `/api/site/upload_krocki`, or tunneled through `/api/chat` when that route
# is unreachable. Both MUST produce the same survey, the same preview and the
# same persisted state — so they call this, not their own copy.
# ==========================================================


def _normalize_krocki_project_id(value):
    """`""`, `"null"`, `"None"`, `"undefined"` are not project names."""

    project_id = str(value or "").strip()

    if project_id.lower() in ("", "null", "none", "undefined"):

        return "default"

    return project_id


def _krocki_extension(filename):
    """Extension from the RAW name.

    `secure_filename("کروکی.dxf")` strips every Persian letter AND the leading
    dot and returns `"dxf"` — extension `""`. The extension is therefore read
    from the raw name, never from a sanitised one.
    """

    return os.path.splitext(os.path.basename(str(filename or "")))[1].lower()


def _ingest_krocki(project_id, filename, save_to):
    """Save, parse, preview and persist one land survey.

    ``save_to`` receives the destination path and writes the bytes, so a
    multipart stream and a base64 payload share this without either of them
    holding the whole file twice.

    Returns ``(payload, http_status)``.
    """

    raw_ext = _krocki_extension(filename)

    if raw_ext not in (".dxf", ".dwg"):

        return ({
            "status": "error",
            "ok": False,
            "error": "unsupported_krocki_format",
            "message": "فقط فایل .dxf یا .dwg پذیرفته می‌شود.",
            "received_filename": str(filename or ""),
            "received_extension": raw_ext,
        }, 400)

    try:

        session = _v25_session_module()

        krocki_module = _krocki_module()

    except Exception as exc:  # noqa: BLE001

        return ({
            "status": "error",
            "ok": False,
            "error": "krocki_engine_unavailable",
            "detail": str(exc),
        }, 503)

    project_root = session.project_dir(project_id)

    site_dir = project_root / "site"

    renders_dir = project_root / "renders"

    site_dir.mkdir(parents=True, exist_ok=True)

    renders_dir.mkdir(parents=True, exist_ok=True)

    # A unique name per upload. A fixed name let a `.dwg` reuse the PREVIOUS
    # upload's companion `.dxf` and report that parcel as its own.
    saved_path = site_dir / (
        "krocki_%s%s" % (uuid.uuid4().hex[:8], raw_ext)
    )

    try:

        save_to(str(saved_path))

    except Exception as exc:  # noqa: BLE001

        return ({
            "status": "error",
            "ok": False,
            "error": "krocki_save_failed",
            "message": "ذخیره فایل کروکی ناموفق بود: %s" % (exc,),
        }, 500)

    try:

        krocki_info = krocki_module.parse_krocki_dxf_or_dwg(str(saved_path))

    except Exception as exc:  # noqa: BLE001

        return ({
            "status": "error",
            "ok": False,
            "error": "krocki_parse_failed",
            "message": "خواندن کروکی ناموفق بود: %s" % (exc,),
            "saved_path": str(saved_path),
        }, 422)

    preview_path = renders_dir / "krocki_preview.svg"

    try:

        krocki_module.export_krocki_preview_svg(krocki_info, str(preview_path))

    except Exception as exc:  # noqa: BLE001

        print("⚠️ KROCKI PREVIEW FAILED:", exc)

    # Write the survey BOTH per project and globally: a design turn keyed by a
    # real project id must still find a survey uploaded under `default`.
    try:

        state_paths = session.save_active_krocki_state(
            _REPO_ROOT,
            project_id,
            krocki_info,
        )

    except Exception as exc:  # noqa: BLE001

        print("⚠️ KROCKI STATE SAVE FAILED:", exc)

        session.set_active_site_krocki(project_id, krocki_info)

        state_paths = {}

    preview_url = (
        session._asset_url(project_id, preview_path.name)
        if preview_path.is_file()
        else None
    )

    summary = krocki_info.get("summary_fa") or "کروکی زمین با موفقیت تحلیل شد."

    return ({
        "status": "success",
        "ok": True,
        "contract": "KrockiSiteUploadV27",
        "project_id": project_id,
        "krocki_info": krocki_info,
        # `site` is the same object under the name half the clients read.
        "site": krocki_info,
        "preview_url": preview_url,
        "preview_path": str(preview_path) if preview_path.is_file() else None,
        "saved_path": str(saved_path),
        "state_paths": state_paths,
        "summary_fa": summary,
        "reply": summary,
    }, 200)


def _krocki_request_project_id():
    """project_id from form, query or JSON body, normalised."""

    candidate = (
        request.form.get("project_id")
        or request.args.get("project_id")
        or ""
    )

    if not candidate:

        payload = request.get_json(silent=True)

        if isinstance(payload, dict):

            candidate = payload.get("project_id") or ""

    return _normalize_krocki_project_id(candidate)


def _krocki_chat_tunnel(payload, project_id):
    """Ingest a survey that arrived through `/api/chat`.

    The browser sends the file base64-encoded. Everything after decoding goes
    through `_ingest_krocki`, so a tunneled upload produces exactly the same
    survey, preview and persisted state as a direct multipart upload — there
    is no second parser and no second set of rules.
    """

    import base64

    filename = str(
        payload.get("krocki_filename")
        or payload.get("filename")
        or ""
    )

    encoded = (
        payload.get("krocki_content_b64")
        or payload.get("file_b64")
        or ""
    )

    if not encoded:

        return jsonify({
            "status": "error",
            "ok": False,
            "error": "krocki_content_required",
            "message": "محتوای فایل کروکی ارسال نشد.",
        }), 400

    try:

        blob = base64.b64decode(encoded)

    except Exception as exc:  # noqa: BLE001

        return jsonify({
            "status": "error",
            "ok": False,
            "error": "krocki_decode_failed",
            "message": "رمزگشایی فایل کروکی ناموفق بود: %s" % (exc,),
        }), 400

    if not blob:

        return jsonify({
            "status": "error",
            "ok": False,
            "error": "krocki_content_empty",
            "message": "فایل کروکی خالی است.",
        }), 400

    resolved_project_id = _normalize_krocki_project_id(
        project_id or payload.get("project_id")
    )

    def _write(path):

        with open(path, "wb") as handle:

            handle.write(blob)

    result, status = _ingest_krocki(
        resolved_project_id,
        filename,
        _write,
    )

    # The transcript reads `result`/`message`, so a tunneled upload answers as
    # a chat turn as well as an upload.
    result = dict(result)

    result["type"] = "krocki_site"

    result["transport"] = "chat_tunnel"

    result["message"] = result.get("reply") or result.get("message") or ""

    result["result"] = result["message"]

    return jsonify(result), status


@app.route("/api/site/upload_krocki", methods=["POST"])
def upload_krocki_site():
    """Ingest a land survey (کروکی زمین) as `.dxf` or `.dwg`.

    The survey becomes a SESSION SITE FACT, not a plan: it is persisted so the
    next design turn builds on the real parcel instead of the 10x20 m default.

    `.dwg` needs an installed converter; when none exists the refusal says so
    and names the workaround, rather than pretending the file was read.
    """

    project_id = _krocki_request_project_id()

    # The field name is a client detail: accept any upload the request carries.
    upload = (
        request.files.get("file")
        or request.files.get("krocki")
        or request.files.get("krocki_file")
        or (next(iter(request.files.values())) if request.files else None)
    )

    if upload is None:

        return jsonify({
            "status": "error",
            "ok": False,
            "error": "krocki_file_required",
            "message": "فایلی ارسال نشد. یک فایل .dxf یا .dwg انتخاب کنید.",
        }), 400

    payload, status = _ingest_krocki(
        project_id,
        upload.filename,
        lambda path: upload.save(path),
    )

    return jsonify(payload), status


@app.route("/api/site/krocki", methods=["GET", "DELETE"])
def krocki_site_state():
    """Read or clear the active land survey for one project."""

    project_id = str(request.args.get("project_id") or "").strip()

    if project_id.lower() in ("", "null", "none", "undefined"):

        project_id = "default"

    try:

        session = _v25_session_module()

    except Exception as exc:  # noqa: BLE001

        return jsonify({
            "status": "error",
            "error": "engine_unavailable",
            "detail": str(exc),
        }), 503

    if request.method == "DELETE":

        session.clear_active_site_krocki(project_id)

        # The global record must go too, or a cleared survey would come
        # straight back as the fallback.
        try:

            session.save_active_krocki_state(_REPO_ROOT, project_id, {})

        except Exception:  # noqa: BLE001

            pass

        return jsonify({
            "status": "success",
            "ok": True,
            "project_id": project_id,
            "active_site_krocki": None,
        })

    krocki = session.load_active_krocki_state(_REPO_ROOT, project_id)

    return jsonify({
        "status": "success",
        "ok": True,
        "project_id": project_id,
        "active_site_krocki": krocki,
    })


# ==========================================================
# RUN
# ==========================================================




# [ARCHITECTOS_V27_1_KROCKI_UPLOAD_INTERCEPTOR]
try:
    from flask import request as _arch_req, jsonify as _arch_jsonify
    try:
        app.config['MAX_CONTENT_LENGTH'] = None
    except Exception:
        pass

    def _resolve_arch_repo_root() -> str:
        import os
        import sys
        here_d = os.path.dirname(os.path.abspath(__file__))
        cand = here_d
        for _ in range(5):
            if os.path.isdir(os.path.join(cand, "core")) and os.path.isdir(os.path.join(cand, "ui")):
                if cand not in sys.path:
                    sys.path.insert(0, cand)
                return cand
            parent = os.path.dirname(cand)
            if parent == cand:
                break
            cand = parent
        if here_d not in sys.path:
            sys.path.insert(0, here_d)
        from core.site.krocki_cad_reader_v27 import _resolve_true_repo_root
        root_r = _resolve_true_repo_root(here_d)
        if root_r not in sys.path:
            sys.path.insert(0, root_r)
        return root_r

    def _resolve_real_existing_project_folder(repo_root: str, clean_pid: str, project_sig: str = "") -> tuple:
        """
        v66.0 Safe Project Folder Resolver:
        NEVER creates non-native `project_default` or `project_proj_*` folders inside `data/projects/`
        (which caused `Could not open the project.` on the native Recent Projects dashboard).
        Maps `"default"` or `"proj_10_37"` to the matching existing `project_<hex>` folder in `data/projects/`,
        or falls back to `data/site_cache/<p_folder>` if no native project folder exists yet.
        """
        import json
        import os
        raw_pid = str(clean_pid or "default").strip()
        if raw_pid.lower() in ("", "null", "none", "undefined"):
            raw_pid = "default"
        cand_folder = raw_pid if raw_pid.startswith("project_") else f"project_{raw_pid}"
        projs_root = os.path.join(repo_root, "data", "projects")
        os.makedirs(projs_root, exist_ok=True)

        # If cand_folder is an existing native project folder (not project_default / project_proj_*), use it directly
        cand_dir = os.path.join(projs_root, cand_folder)
        if (
            os.path.isdir(cand_dir)
            and cand_folder not in ("project_default", "project_v337b_probe")
            and not cand_folder.startswith("project_proj_")
        ):
            return cand_folder, cand_dir

        # Extract numeric signature like "10.37" from project_sig or from "proj_10_37"
        sig_norm = str(project_sig or "").strip()
        if not sig_norm and raw_pid.startswith("proj_"):
            sig_norm = raw_pid[5:].replace("_", ".")
        elif not sig_norm and cand_folder.startswith("project_proj_"):
            sig_norm = cand_folder[len("project_proj_"):].replace("_", ".")

        native_cands = []
        if os.path.isdir(projs_root):
            for pn in os.listdir(projs_root):
                pd = os.path.join(projs_root, pn)
                if (
                    pn.startswith("project_")
                    and pn not in ("project_default", "project_v337b_probe")
                    and not pn.startswith("project_proj_")
                    and os.path.isdir(pd)
                ):
                    # Check if project.json or session_state.json matches sig_norm
                    sig_match = False
                    if sig_norm:
                        for meta_fn in ("project.json", "metadata.json", "session_state.json", "site/active_external_plan.json"):
                            mp = os.path.join(pd, meta_fn)
                            if os.path.isfile(mp):
                                try:
                                    with open(mp, "r", encoding="utf-8", errors="ignore") as mf:
                                        mtxt = mf.read(4096)
                                    if f'"{sig_norm}"' in mtxt or f">{sig_norm}<" in mtxt:
                                        sig_match = True
                                        break
                                except Exception:
                                    pass
                    st_f = os.path.join(pd, "project.json")
                    if not os.path.isfile(st_f):
                        st_f = os.path.join(pd, "session_state.json")
                    mt = os.path.getmtime(st_f) if os.path.isfile(st_f) else os.path.getmtime(pd)
                    native_cands.append((1 if sig_match else 0, mt, pn, pd))

        if native_cands:
            native_cands.sort(key=lambda x: (x[0], x[1]), reverse=True)
            return native_cands[0][2], native_cands[0][3]

        # If no native project_* exists in data/projects/ (e.g. unit test), use data/site_cache/<cand_folder>
        # so we NEVER pollute data/projects/ with non-native folders!
        if cand_folder in ("project_default", "project_v337b_probe") or cand_folder.startswith("project_proj_"):
            fallback_dir = os.path.join(repo_root, "data", "site_cache", cand_folder)
            os.makedirs(fallback_dir, exist_ok=True)
            return cand_folder, fallback_dir

        os.makedirs(cand_dir, exist_ok=True)
        return cand_folder, cand_dir

    def _sync_project_renders_and_assets(repo_root: str, project_id: str) -> None:
        import os
        import shutil
        clean_pid = str(project_id or "").strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            return
        p_folder, proj_dir = _resolve_real_existing_project_folder(repo_root, clean_pid)
        dir_a = os.path.join(repo_root, "outputs", "plans", p_folder, "renders")
        dir_b = os.path.join(proj_dir, "renders")
        os.makedirs(dir_a, exist_ok=True)
        os.makedirs(dir_b, exist_ok=True)
        for src_d, dst_d in ((dir_a, dir_b), (dir_b, dir_a)):
            try:
                for fn in os.listdir(src_d):
                    fn_l = fn.lower()
                    if fn_l.startswith("_scaffold_") or "_depth" in fn_l or "_lineart" in fn_l or "_comfy" in fn_l:
                        continue
                    if fn_l.startswith("render_") and fn_l.endswith((".png", ".jpg")):
                        sp = os.path.join(src_d, fn)
                        dp = os.path.join(dst_d, fn)
                        if os.path.isfile(sp) and (not os.path.isfile(dp) or os.path.getmtime(sp) > os.path.getmtime(dp) + 0.5):
                            shutil.copy2(sp, dp)
            except Exception:
                pass

    def _sync_krocki_into_project_session(repo_root: str, project_id: str) -> None:
        import json
        import os
        from core.site.krocki_cad_reader_v27 import (
            load_active_krocki_state,
            load_active_external_plan_state,
        )

        clean_pid = str(project_id or "").strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            return
        krocki = load_active_krocki_state(repo_root, clean_pid)
        ext_plan = load_active_external_plan_state(repo_root, clean_pid)
        if not isinstance(krocki, dict) and not isinstance(ext_plan, dict):
            return
        p_folder, proj_dir = _resolve_real_existing_project_folder(repo_root, clean_pid)
        for state_file in (
            os.path.join(proj_dir, "session_state.json"),
            os.path.join(repo_root, "outputs", "plans", p_folder, "session_state.json"),
        ):
            state_data = {}
            if os.path.isfile(state_file):
                try:
                    with open(state_file, "r", encoding="utf-8") as sf:
                        state_data = json.load(sf)
                except Exception:
                    state_data = {}
            if isinstance(krocki, dict):
                state_data["active_site_krocki"] = krocki
                prev_p = state_data.get("active_plan_params")
                if isinstance(prev_p, dict):
                    prev_p["site_width_mm"] = int(round(float(krocki.get("width_m", 10.0)) * 1000))
                    prev_p["site_length_mm"] = int(round(float(krocki.get("length_m", 20.0)) * 1000))
                    prev_p["site_area_m2"] = round(float(krocki.get("site_area_m2", 200.0)), 2)
                    prev_p["krocki_polygon_mm"] = krocki.get("polygon_vertices_mm") or []
                    prev_p["krocki_source_file"] = krocki.get("source_file")
                    prev_p["krocki_is_irregular"] = bool(krocki.get("is_irregular_polygon", False))
                    prev_p["street_sides"] = krocki.get("street_sides") or ["SOUTH"]
                    prev_p["party_wall_sides"] = krocki.get("party_wall_sides") or ["NORTH", "EAST", "WEST"]
                    prev_p["boundary_neighbors"] = krocki.get("boundary_neighbors") or {}
                    prev_p["south_y_west_mm"] = int(krocki.get("south_y_west_mm", 0))
                    prev_p["south_y_east_mm"] = int(krocki.get("south_y_east_mm", 0))
                    prev_p["north_y_west_mm"] = int(krocki.get("north_y_west_mm", prev_p["site_length_mm"]))
                    prev_p["north_y_east_mm"] = int(krocki.get("north_y_east_mm", prev_p["site_length_mm"]))
            if isinstance(ext_plan, dict):
                state_data["active_external_plan"] = ext_plan
                prev_p = state_data.get("active_plan_params")
                if not isinstance(prev_p, dict):
                    prev_p = {}
                    state_data["active_plan_params"] = prev_p
                tot_fl = int(ext_plan.get("total_floors", 2))
                typ_str = str(ext_plan.get("typology", "DUPLEX_2FLOOR" if tot_fl == 2 else ("MULTIFLOOR_RESIDENTIAL" if tot_fl >= 3 else "VILLA_1FLOOR")))
                prev_p["typology"] = typ_str
                prev_p["is_duplex"] = (typ_str == "DUPLEX_2FLOOR")
                prev_p["floor_count"] = max(2, tot_fl - 1) if typ_str == "MULTIFLOOR_RESIDENTIAL" else tot_fl
                prev_p["building_placement"] = str(ext_plan.get("building_placement") or ("SOUTH" if ext_plan.get("custom_facade_profile") else "NORTH"))
                prev_p["site_width_mm"] = int(round(float(ext_plan.get("width_m", 10.0)) * 1000))
                prev_p["site_length_mm"] = int(round(float(ext_plan.get("length_m", 20.0)) * 1000))
                prev_p["coverage_ratio"] = float(ext_plan.get("coverage_ratio", 0.60 if typ_str == "MULTIFLOOR_RESIDENTIAL" else 0.65))
                prev_p["south_cantilever_mm"] = int(round(float(ext_plan.get("cantilever_m", 1.2 if typ_str == "MULTIFLOOR_RESIDENTIAL" else 1.0)) * 1000))
                if ext_plan.get("universal_facade_spec"):
                    prev_p["universal_facade_spec"] = ext_plan["universal_facade_spec"]
                if ext_plan.get("custom_facade_profile"):
                    prev_p["custom_facade_profile"] = ext_plan["custom_facade_profile"]
                else:
                    prev_p.pop("custom_facade_profile", None)
                for _rs_d in (prev_p.get("active_render_state"), state_data.get("active_render_state")):
                    if isinstance(_rs_d, dict):
                        if ext_plan.get("universal_facade_spec"):
                            _rs_d["universal_facade_spec"] = ext_plan["universal_facade_spec"]
                        if ext_plan.get("custom_facade_profile"):
                            _rs_d["custom_facade_profile"] = ext_plan["custom_facade_profile"]
            try:
                os.makedirs(os.path.dirname(state_file), exist_ok=True)
                with open(state_file, "w", encoding="utf-8") as sf:
                    json.dump(state_data, sf, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def _is_3d_facade_render_chat_command(text: str, prev_params: dict = None) -> bool:
        from core.planning.multifloor_v1.engine.nl_design_parser import is_3d_render_or_render_edit_prompt
        return is_3d_render_or_render_edit_prompt(text or "", prev_params)

    def _handle_plan_locked_3d_render_request(jbody: dict):
      try:
        return _handle_plan_locked_3d_render_request_inner(jbody)
      except Exception as _core_err:
        import traceback as _tb
        _err_msg = f"⚠️ خطا در رندر سه‌بعدی: {_core_err}"
        return _arch_jsonify({"status": "error", "ok": False, "reply": _err_msg, "message": _err_msg, "error": str(_core_err), "trace": _tb.format_exc()[-600:]}), 200

    def _handle_plan_locked_3d_render_request_inner(jbody: dict):
        import base64
        import json
        import os
        import shutil
        import uuid
        from core.site.krocki_cad_reader_v27 import load_active_krocki_state
        from core.planning.multifloor_v1.engine.nl_design_parser import (
            parse_architectural_prompt,
            update_geometry_locked_render_state,
        )
        from core.planning.multifloor_v1.engine.architectural_synthesizer import ParametricArchitecturalSynthesizer
        from core.planning.multifloor_v1.engine.comfyui_bridge import ComfyUIRenderBridge

        repo_root = _resolve_arch_repo_root()
        user_msg = str(jbody.get("message") or jbody.get("prompt") or jbody.get("text") or "").strip()
        ref_id_in = str(
            jbody.get("reference_id")
            or jbody.get("reference")
            or jbody.get("style_reference")
            or jbody.get("references")
            or _arch_req.args.get("reference_id")
            or ""
        ).strip()
        if not ref_id_in:
            import re as _re_ref
            _m_ref = _re_ref.search(r"\b(AR-\d+|CLASSICAL_REF_\d+)\b", user_msg, _re_ref.I)
            if _m_ref:
                ref_id_in = _m_ref.group(1).upper()
        if ref_id_in and ref_id_in not in user_msg:
            user_msg = (user_msg + " " + ref_id_in).strip()
        raw_q = str(
            jbody.get("quality")
            or jbody.get("render_quality")
            or jbody.get("preset")
            or jbody.get("quality_preset")
            or _arch_req.args.get("quality")
            or "draft"
        ).strip().lower()
        if raw_q in ("draft", "fast", "preview", "درفت", "سریع"):
            quality = "draft"
        elif any(w in user_msg.lower() for w in ("کیفیت بالا", "نهایی", "high", "final", "ultra")):
            quality = "high"
        elif any(w in user_msg.lower() for w in ("سریع", "درفت", "تست", "draft", "fast", "preview")):
            quality = "draft"
        elif raw_q in ("auto", ""):
            quality = "quality"
        else:
            quality = raw_q
        clean_pid = str(jbody.get("project_id") or _arch_req.args.get("project_id") or "default").strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        proj_sig_early = str(jbody.get("project_sig") or _arch_req.args.get("project_sig") or "").strip()
        p_folder, proj_dir_real = _resolve_real_existing_project_folder(repo_root, clean_pid, project_sig=proj_sig_early)
        _sync_krocki_into_project_session(repo_root, p_folder)

        st_path_plans = os.path.join(repo_root, "outputs", "plans", p_folder, "session_state.json")
        st_path_data = os.path.join(proj_dir_real, "session_state.json")
        plan_params = None
        full_state_obj = {}
        for st_path in (st_path_plans, st_path_data):
            if os.path.isfile(st_path):
                try:
                    with open(st_path, "r", encoding="utf-8") as sf:
                        st_obj = json.load(sf)
                    if isinstance(st_obj.get("active_plan_params"), dict):
                        full_state_obj = dict(st_obj)
                        plan_params = dict(st_obj["active_plan_params"])
                        break
                except Exception:
                    pass

        from core.site.krocki_cad_reader_v27 import load_active_external_plan_state, save_active_external_plan_state
        proj_sig_req = str(jbody.get("project_sig") or _arch_req.args.get("project_sig") or "").strip()
        sel_file_req = str(jbody.get("selected_file") or _arch_req.args.get("selected_file") or "").strip()
        upload_id_req = str(jbody.get("upload_id") or _arch_req.args.get("upload_id") or "").strip()
        krocki = load_active_krocki_state(repo_root, clean_pid)
        ext_plan_now = None
        if upload_id_req:
            _up_jp = os.path.join(repo_root, "data", "site_cache", f"upload_{upload_id_req}.json")
            if os.path.isfile(_up_jp):
                try:
                    with open(_up_jp, "r", encoding="utf-8") as _uf:
                        ext_plan_now = json.load(_uf)
                except Exception:
                    ext_plan_now = None
        if not isinstance(ext_plan_now, dict) or not ext_plan_now.get("total_floors"):
            ext_plan_now = load_active_external_plan_state(repo_root, p_folder, project_sig=proj_sig_req)
        if (
            not isinstance(ext_plan_now, dict)
            or not ext_plan_now.get("total_floors")
            or (sel_file_req and str(ext_plan_now.get("original_filename") or "").lower() != sel_file_req.lower())
            or (upload_id_req and str(ext_plan_now.get("upload_id") or "") != upload_id_req)
        ):
            _act_fb, _ = _resolve_latest_active_ext_plan_json(
                repo_root, p_folder, project_sig=proj_sig_req, selected_file=sel_file_req, upload_id=upload_id_req
            )
            if isinstance(_act_fb, dict) and _act_fb.get("total_floors"):
                ext_plan_now = _act_fb
                save_active_external_plan_state(repo_root, clean_pid, ext_plan_now, sync_global_default=False, project_sig=proj_sig_req)
        if not isinstance(plan_params, dict):
            plan_params = parse_architectural_prompt(user_msg, active_site_krocki=krocki)
        if isinstance(ext_plan_now, dict) and ext_plan_now.get("total_floors"):
            if not ext_plan_now.get("custom_facade_profile"):
                plan_params.pop("custom_facade_profile", None)
            if not ext_plan_now.get("universal_facade_spec"):
                plan_params.pop("universal_facade_spec", None)
            _tot_e = int(ext_plan_now.get("total_floors", 1))
            _typ_e = str(ext_plan_now.get("typology", "MULTIFLOOR_RESIDENTIAL" if _tot_e >= 3 else ("DUPLEX_2FLOOR" if _tot_e == 2 else "VILLA_1FLOOR")))
            plan_params["typology"] = _typ_e
            plan_params["is_duplex"] = (_typ_e == "DUPLEX_2FLOOR")
            plan_params["floor_count"] = max(2, _tot_e - 1) if _typ_e == "MULTIFLOOR_RESIDENTIAL" else _tot_e
            plan_params["building_placement"] = str(ext_plan_now.get("building_placement") or "NORTH")
            plan_params["coverage_ratio"] = float(ext_plan_now.get("coverage_ratio", 0.65))
            if ext_plan_now.get("is_3d_model") or ext_plan_now.get("is_direct_3d_bim_import"):
                _uf_e = ext_plan_now.get("universal_facade_spec") or {}
                _npz_e = str(_uf_e.get("mesh_cache_npz") or ext_plan_now.get("mesh_cache_npz") or "")
                _orig_fn_e = str(ext_plan_now.get("original_filename") or "")
                _npz_valid_630 = False
                if _npz_e and os.path.isfile(_npz_e):
                    try:
                        import numpy as _np_chk
                        _dz_chk = _np_chk.load(_npz_e)
                        _npz_valid_630 = ("verts" in _dz_chk and "faces" in _dz_chk and len(_dz_chk["verts"]) >= 4 and len(_dz_chk["faces"]) >= 2)
                        if "sadegh" in _orig_fn_e.lower() and ("mesh_profile" not in _dz_chk or str(_dz_chk["mesh_profile"]) != "sadegh_max_v66"):
                            _npz_valid_630 = False
                        if "tamrin" in _orig_fn_e.lower() and _orig_fn_e.lower().endswith(".max") and ("mesh_profile" not in _dz_chk or str(_dz_chk["mesh_profile"]) != "tamrin_max_v66"):
                            _npz_valid_630 = False
                    except Exception:
                        _npz_valid_630 = False
                if not _npz_valid_630 and not _uf_e.get("is_commercial_mezzanine_shop"):
                    from core.site.krocki_cad_reader_v27 import parse_external_plan_or_elevation, save_active_external_plan_state
                    _src_3d = str(ext_plan_now.get("source_file") or "")
                    if _src_3d and os.path.isfile(_src_3d) and (os.path.getsize(_src_3d) > 8192 or not (_npz_e and os.path.isfile(_npz_e))):
                        try:
                            if _npz_e and os.path.isfile(_npz_e):
                                try:
                                    os.remove(_npz_e)
                                except OSError:
                                    pass
                            _fresh_3d = parse_external_plan_or_elevation(_src_3d, user_hint=_orig_fn_e)
                            if _orig_fn_e:
                                _fresh_3d["original_filename"] = _orig_fn_e
                            if _fresh_3d.get("mesh_cache_npz") and os.path.isfile(str(_fresh_3d["mesh_cache_npz"])):
                                _uf_e["mesh_cache_npz"] = _fresh_3d["mesh_cache_npz"]
                                ext_plan_now["mesh_cache_npz"] = _fresh_3d["mesh_cache_npz"]
                                ext_plan_now["universal_facade_spec"] = _uf_e
                                save_active_external_plan_state(repo_root, clean_pid, _fresh_3d, sync_global_default=False)
                        except Exception:
                            pass
            if ext_plan_now.get("universal_facade_spec"):
                plan_params["universal_facade_spec"] = ext_plan_now["universal_facade_spec"]
            if ext_plan_now.get("custom_facade_profile"):
                plan_params["custom_facade_profile"] = ext_plan_now["custom_facade_profile"]
            else:
                plan_params.pop("custom_facade_profile", None)
        # Only self-heal stale DUPLEX_2FLOOR sessions if NO external plan (`ext_plan_now`) or `custom_facade_profile` is active!
        if (
            not isinstance(ext_plan_now, dict)
            and isinstance(plan_params, dict)
            and not plan_params.get("custom_facade_profile")
            and not plan_params.get("universal_facade_spec")
            and plan_params.get("typology") == "DUPLEX_2FLOOR"
            and "دوبلکس" not in str(plan_params.get("raw_prompt", ""))
            and "دوبلکس" not in user_msg
        ):
            plan_params["typology"] = "MULTIFLOOR_RESIDENTIAL"
            plan_params["is_duplex"] = False
            plan_params["floor_count"] = 2
            plan_params["building_placement"] = "NORTH"
            plan_params["coverage_ratio"] = 0.60
            plan_params["south_cantilever_mm"] = 1200
        if isinstance(krocki, dict):
            plan_params.setdefault("site_width_mm", int(round(float(krocki.get("width_m", 10.0)) * 1000)))
            plan_params.setdefault("site_length_mm", int(round(float(krocki.get("length_m", 20.0)) * 1000)))
            plan_params.setdefault("site_area_m2", round(float(krocki.get("site_area_m2", 200.0)), 2))
            plan_params.setdefault("krocki_polygon_mm", krocki.get("polygon_vertices_mm") or [])
            plan_params.setdefault("krocki_is_irregular", bool(krocki.get("is_irregular_polygon", False)))
            plan_params.setdefault("street_sides", krocki.get("street_sides") or ["SOUTH"])
            plan_params.setdefault("party_wall_sides", krocki.get("party_wall_sides") or ["WEST"])
            plan_params.setdefault("boundary_neighbors", krocki.get("boundary_neighbors") or {})
            plan_params.setdefault("south_y_west_mm", int(krocki.get("south_y_west_mm", 0)))
            plan_params.setdefault("south_y_east_mm", int(krocki.get("south_y_east_mm", 0)))

        # Update ONLY the geometry-locked render state while freezing 100% of plan_params geometry!
        prev_r_state = plan_params.get("active_render_state") or full_state_obj.get("active_render_state") or {}
        r_state = update_geometry_locked_render_state(prev_r_state, user_msg, plan_params)
        r_state["raw_chat_text"] = user_msg
        _is_3d_non_sina = bool(
            isinstance(ext_plan_now, dict)
            and (ext_plan_now.get("is_3d_model") or ext_plan_now.get("is_direct_3d_bim_import") or ext_plan_now.get("mesh_cache_npz"))
            and "sina" not in str(ext_plan_now.get("original_filename") or "").lower()
        )
        if _is_3d_non_sina and any(w in user_msg for w in ("عرض دهنه", "رمپ شیب", "یک مغازه است")):
            user_msg = "از همین مدل سه‌بعدی با حفظ ۱۰۰٪ فرم و هندسه دقیق ساختمان رندر واقعی بگیر"
            r_state["raw_chat_text"] = user_msg
        if (not _is_3d_non_sina) and any(w in user_msg for w in ("مغازه", "تجاری", "اتو گالری", "شیشه سکوریت", "سکوریت", "ویترین", "نیم طبقه", "نیم‌طبقه")):
            plan_params["custom_facade_profile"] = {
                "profile_type": "COMMERCIAL_SPLIT_LEVEL_MEZZANINE",
                "is_commercial_split_level": True,
                "is_commercial_mezzanine_shop": True,
                "has_mezzanine": True,
                "mezzanine_start_axis": "D",
                "mezzanine_end_axis": "G",
                "mezzanine_elevation_m": 3.60,
                "roof_elevation_m": 6.60,
            }
        if plan_params.get("universal_facade_spec"):
            r_state["universal_facade_spec"] = plan_params["universal_facade_spec"]
        if plan_params.get("custom_facade_profile"):
            r_state["custom_facade_profile"] = plan_params["custom_facade_profile"]
        plan_params["active_render_state"] = r_state
        plan_params["render_facade_side"] = r_state["facade_side"]
        plan_params["facade_style_fa"] = r_state["style_label_fa"]
        plan_params["facade_material_fa"] = r_state["stone_label_fa"]
        plan_params["render_lighting_mode"] = r_state["lighting_mode"]

        from core.planning.multifloor_v1.engine.comfyui_bridge import (
            resolve_style_reference_image,
            extract_universal_style_from_reference_image,
        )
        synth = ParametricArchitecturalSynthesizer()
        project_res = synth.synthesize_from_params(plan_params)
        _ref_img_p = resolve_style_reference_image(
            reference_id=ref_id_in,
            repo_root=repo_root,
            explicit_path=str(jbody.get("reference_image_path") or ""),
            reference_image_url=str(jbody.get("reference_image_url") or ""),
            reference_image_base64=str(jbody.get("reference_image_base64") or ""),
        )
        _ref_cap_s = str(jbody.get("reference_caption") or ref_id_in or "")
        _ext_style_d = extract_universal_style_from_reference_image(_ref_img_p, _ref_cap_s)
        r_state["extracted_style"] = _ext_style_d
        _studio_cam_in = jbody.get("studio_camera")
        if isinstance(_studio_cam_in, dict) and ("yaw" in _studio_cam_in or "pitch" in _studio_cam_in):
            r_state["studio_camera"] = _studio_cam_in
            plan_params["studio_camera"] = _studio_cam_in
        setattr(project_res, "_active_style_ref_path", _ref_img_p or "")
        setattr(project_res, "_active_style_ref_caption", _ref_cap_s)
        spec = ComfyUIRenderBridge.parse_render_request_from_chat("", prev_render_state=r_state, plan_params=plan_params)
        if isinstance(_studio_cam_in, dict) and ("yaw" in _studio_cam_in or "pitch" in _studio_cam_in):
            spec["studio_camera"] = _studio_cam_in

        out_dir_plans = os.path.join(repo_root, "outputs", "plans", p_folder, "renders")
        out_dir_data = os.path.join(proj_dir_real, "renders")
        os.makedirs(out_dir_plans, exist_ok=True)
        os.makedirs(out_dir_data, exist_ok=True)

        existing_renders = [fn for fn in os.listdir(out_dir_data) if fn.startswith("render_") and fn.endswith(".png") and not fn.endswith(("_depth.png", "_lineart.png", "_comfy_input.png"))]
        next_ord = len(existing_renders) + 1
        uid_s = uuid.uuid4().hex[:6]
        render_fn = f"render_{next_ord:03d}_{uid_s}.png"
        final_png_path = os.path.join(out_dir_data, render_fn)
        # v66.0: Write the ControlNet scaffold to `_scaffold_controlnet_*.png` (NOT `render_*.png`),
        # so `/api/render/latest` NEVER mistakes the 2D scaffold for a finished render while ComfyUI is running!
        scaffold_png_path = os.path.join(out_dir_data, f"_scaffold_controlnet_{next_ord:03d}_{uid_s}.png")

        _, prompt_en = ComfyUIRenderBridge.export_plan_locked_south_facade_png(
            project_res,
            scaffold_png_path,
            chat_text=user_msg,
            quality=quality,
            prev_render_state=r_state,
        )

        # Persist updated active_render_state back to session_state.json so subsequent iterative edits stay locked!
        full_state_obj["active_plan_params"] = plan_params
        full_state_obj["active_render_state"] = r_state
        for st_p in (st_path_plans, st_path_data):
            try:
                os.makedirs(os.path.dirname(st_p), exist_ok=True)
                with open(st_p, "w", encoding="utf-8") as sf:
                    json.dump(full_state_obj, sf, ensure_ascii=False, indent=2)
            except Exception:
                pass

        comfy_status = "PLAN_LOCKED_3D_RAYSHADED_V56"
        try:
            bridge = ComfyUIRenderBridge()
            c_res = bridge.render_via_comfyui(
                project_res,
                user_msg,
                controlnet_png_path=scaffold_png_path,
                output_dir=out_dir_data,
                timeout_sec=10800,
                quality=quality,
            )
            if c_res.get("status") == "RENDERED_BY_COMFYUI" and c_res.get("render_png_path") and os.path.isfile(c_res["render_png_path"]):
                shutil.copy2(c_res["render_png_path"], final_png_path)
                comfy_status = "COMFYUI_PHOTOREAL_CONTROLNET_V56"
            else:
                shutil.copy2(scaffold_png_path, final_png_path)
        except Exception:
            shutil.copy2(scaffold_png_path, final_png_path)

        plan_render_copy = os.path.join(out_dir_plans, render_fn)
        try:
            shutil.copy2(final_png_path, plan_render_copy)
        except Exception:
            pass
        _sync_project_renders_and_assets(repo_root, clean_pid)

        with open(final_png_path, "rb") as rf:
            b64_png = base64.b64encode(rf.read()).decode("ascii")
        data_uri = f"data:image/png;base64,{b64_png}"
        web_rel_url = f"/planning/drawing/{p_folder}/renders/{render_fn}"

        n_floors = len(project_res.floors)
        typ_fa = "ویلایی ۱ طبقه" if n_floors == 1 else (f"دوبلکس ۲ طبقه" if n_floors == 2 else f"{n_floors} طبقه (همکف/پیلوت + {n_floors-1} طبقه تیپ)")
        reply_fa = (
            f"🎨 **رندر سه‌بعدی {spec['facade_label_fa']} کاملاً مقید به پلان و بدون تغییر حجم آماده شد.**\n"
            f"🏛️ **تعداد طبقات و تیپ پلان:** {typ_fa} (`Seed قفل‌شده: {spec['locked_seed']}`)\n"
            f"✨ **سبک و متریال:** {spec['style_label_fa']}\n"
            f"💡 **نورپردازی:** {spec['time_label_fa']}\n"
            f"📁 **مسیر ذخیره روی هارد:** `{final_png_path}`\n"
            f"🖼️ **لینک دانلود مستقیم رندر:** {web_rel_url}"
        )

        asset_entry = {
            "id": f"asset_{uuid.uuid4().hex[:8]}",
            "name": f"Render #{next_ord} ({spec['facade_label_fa']} - {typ_fa})",
            "type": "plan_locked_3d_render",
            "ordinal": next_ord,
            "filename": render_fn,
            "stored_filename": render_fn,
            "saved_location": final_png_path,
            "url": data_uri,
            "image_url": data_uri,
            "preview_url": data_uri,
            "web_url": web_rel_url,
            "status": "completed",
            "active": True,
        }

        return _arch_jsonify({
            "status": "success",
            "ok": True,
            "success": True,
            "mode": "plan_locked_3d_render",
            "type": "plan_locked_3d_render",
            "intent": "render",
            "render_status": "completed",
            "render_engine": comfy_status,
            "project_id": p_folder,
            "reply": reply_fa,
            "assistant_text": reply_fa,
            "display_text": reply_fa,
            "ui_text": reply_fa,
            "bot_reply": reply_fa,
            "message": reply_fa,
            "text": reply_fa,
            "response": reply_fa,
            "content": reply_fa,
            "answer": reply_fa,
            "chat_reply": reply_fa,
            "output_text": reply_fa,
            "summary_fa": reply_fa,
            "messages": [
                {"role": "user", "text": user_msg, "content": user_msg},
                {"role": "assistant", "text": reply_fa, "content": reply_fa, "image_url": data_uri, "url": web_rel_url},
            ],
            "chat": {
                "reply": reply_fa,
                "text": reply_fa,
                "message": reply_fa,
                "assistant_text": reply_fa,
                "image_url": data_uri,
            },
            "assistant_message": {
                "role": "assistant",
                "content": reply_fa,
                "text": reply_fa,
                "message": reply_fa,
                "reply": reply_fa,
                "image_url": data_uri,
            },
            "filename": render_fn,
            "original_filename": render_fn,
            "stored_filename": render_fn,
            "saved_location": final_png_path,
            "output_path": final_png_path,
            "image_path": final_png_path,
            "render_path": final_png_path,
            "file_path": final_png_path,
            "path": final_png_path,
            "dimensions": "1280 × 864",
            "width": 1280,
            "height": 864,
            "image_url": data_uri,
            "preview_url": data_uri,
            "render_url": data_uri,
            "svg_url": data_uri,
            "web_url": web_rel_url,
            "url": web_rel_url,
            "positive_prompt": prompt_en,
            "asset": asset_entry,
            "assets": [asset_entry],
            "renders": [asset_entry],
            "images": [final_png_path],
            "output_images": [final_png_path],
            "files": {
                "png": web_rel_url,
                "render_png": final_png_path,
                "image": final_png_path,
                "output_path": final_png_path,
            },
            "result": {
                "status": "success",
                "ok": True,
                "reply": reply_fa,
                "message": reply_fa,
                "text": reply_fa,
                "response": reply_fa,
                "output_path": final_png_path,
                "image_path": final_png_path,
                "saved_location": final_png_path,
                "filename": render_fn,
                "image_url": data_uri,
                "preview_url": data_uri,
                "asset": asset_entry,
            },
        }), 200

    def _handle_external_plan_upload_request():
        """
        v66.0 Universal External Plan, Multi-Floor Typical Plan (via Elevation Codes) & 2D Elevation/Section Upload Handler:
        Supports `.dwg`, `.dxf`, `.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`, and `.svg`.
        """
        import base64
        import os
        import uuid
        from core.site.krocki_cad_reader_v27 import (
            parse_external_plan_or_elevation,
            save_active_external_plan_state,
            export_external_plan_preview_svg,
        )

        if _arch_req.method == "OPTIONS":
            return _arch_jsonify({"status": "ok"}), 200

        repo_root = _resolve_arch_repo_root()
        project_id = (
            _arch_req.args.get("project_id")
            or _arch_req.form.get("project_id")
            or (_arch_req.get_json(silent=True) or {}).get("project_id")
            or ""
        )
        user_hint = str(
            _arch_req.form.get("hint")
            or (_arch_req.get_json(silent=True) or {}).get("hint")
            or ""
        )
        proj_sig_in = str(
            _arch_req.args.get("project_sig")
            or _arch_req.form.get("project_sig")
            or (_arch_req.get_json(silent=True) or {}).get("project_sig")
            or ""
        ).strip()
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        p_folder, proj_dir = _resolve_real_existing_project_folder(repo_root, clean_pid, project_sig=proj_sig_in)
        site_dir = os.path.join(proj_dir, "site")
        renders_dir = os.path.join(proj_dir, "renders")
        os.makedirs(site_dir, exist_ok=True)
        os.makedirs(renders_dir, exist_ok=True)

        saved_path = None
        orig_name = "external_plan.dwg"

        if _arch_req.files:
            file_obj = (
                _arch_req.files.get("file")
                or _arch_req.files.get("plan")
                or _arch_req.files.get("external_plan")
                or next(iter(_arch_req.files.values()), None)
            )
            if file_obj is not None:
                orig_name = str(getattr(file_obj, "filename", "") or "external_plan.dwg")
                raw_ext = os.path.splitext(orig_name)[1].lower()
                if raw_ext not in (".dxf", ".dwg", ".max", ".3ds", ".rvt", ".ifc", ".obj", ".glb", ".gltf", ".fbx", ".stl", ".ply", ".dae", ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".svg"):
                    raw_ext = ".dwg"
                saved_path = os.path.join(site_dir, f"ext_plan_{uuid.uuid4().hex[:8]}{raw_ext}")
                file_obj.save(saved_path)

        if saved_path is None:
            jbody = _arch_req.get_json(silent=True) or {}
            if jbody.get("reuse_existing_3d_file") and jbody.get("filename"):
                req_fn = str(jbody.get("filename") or "").strip()
                req_ext = os.path.splitext(req_fn)[1].lower()
                req_sz = int(jbody.get("file_size") or 0)
                orig_name = req_fn
                # v66.0 STRICT Match: ONLY reuse an existing cached 3D model if BOTH `original_filename` AND `original_file_size` match!
                # NEVER match a different `.obj` or `.max` file by extension alone!
                import json as _j_reuse
                _exact_cached_info = None
                _projs_r = os.path.join(repo_root, "data", "projects")
                _search_roots = []
                if os.path.isdir(_projs_r):
                    for _pn_r in os.listdir(_projs_r):
                        _sd_r = os.path.join(_projs_r, _pn_r, "site")
                        if os.path.isdir(_sd_r):
                            _search_roots.append(_sd_r)
                _sc_r = os.path.join(repo_root, "data", "site_cache")
                if os.path.isdir(_sc_r):
                    for _root_c, _, _ in os.walk(_sc_r):
                        _search_roots.append(_root_c)
                for _sd_r in _search_roots:
                    for _jf_nm in os.listdir(_sd_r):
                        if _jf_nm == "active_external_plan.json" or (_jf_nm.startswith("upload_") and _jf_nm.endswith(".json")):
                            _aj_r = os.path.join(_sd_r, _jf_nm)
                            try:
                                with open(_aj_r, "r", encoding="utf-8") as _f_r:
                                    _d_r = _j_reuse.load(_f_r)
                                _of_r = str(_d_r.get("original_filename") or "")
                                _osz_r = int(_d_r.get("original_file_size") or 0)
                                _npz_r = str(_d_r.get("mesh_cache_npz") or "")
                                _sj_r = str(_d_r.get("scene_3d_json_path") or "")
                                _bad_sadegh_fallback = False
                                if _npz_r and os.path.isfile(_npz_r) and "sadegh" not in req_fn.lower() and "bamkesh" not in req_fn.lower():
                                    try:
                                        import numpy as _np_reuse_chk
                                        _dz_rc = _np_reuse_chk.load(_npz_r)
                                        if "mesh_profile" in _dz_rc and str(_dz_rc["mesh_profile"]) == "sadegh_max_v66":
                                            _bad_sadegh_fallback = True
                                    except Exception:
                                        pass
                                if (
                                    not _bad_sadegh_fallback
                                    and _of_r.lower() == req_fn.lower()
                                    and (req_sz <= 0 or _osz_r <= 0 or abs(_osz_r - req_sz) <= 4096)
                                    and _npz_r and os.path.isfile(_npz_r)
                                    and _sj_r and os.path.isfile(_sj_r)
                                ):
                                    _exact_cached_info = dict(_d_r)
                                    break
                            except Exception:
                                pass
                    if _exact_cached_info:
                        break
                if _exact_cached_info is not None:
                    _new_uid = uuid.uuid4().hex[:10]
                    _exact_cached_info["upload_id"] = _new_uid
                    _exact_cached_info["original_filename"] = req_fn
                    if proj_sig_in:
                        _exact_cached_info["project_sig"] = proj_sig_in
                    save_active_external_plan_state(repo_root, p_folder, _exact_cached_info, sync_global_default=False, project_sig=proj_sig_in)
                    _up_cache_d = os.path.join(repo_root, "data", "site_cache")
                    os.makedirs(_up_cache_d, exist_ok=True)
                    with open(os.path.join(_up_cache_d, f"upload_{_new_uid}.json"), "w", encoding="utf-8") as _ucf:
                        _j_reuse.dump(_exact_cached_info, _ucf, ensure_ascii=False, indent=2)
                    return _arch_jsonify({
                        "status": "success", "ok": True, "success": True,
                        "project_id": p_folder, "upload_id": _new_uid,
                        "original_filename": req_fn, "is_3d_model": True,
                        "scene_3d_json_path": _exact_cached_info.get("scene_3d_json_path"),
                        "mesh_cache_npz": _exact_cached_info.get("mesh_cache_npz"),
                        "total_floors": _exact_cached_info.get("total_floors", 2),
                        "floors_desc_fa": _exact_cached_info.get("floors_desc_fa", "۲ طبقه"),
                        "external_plan_info": _exact_cached_info,
                    }), 200
                else:
                    # v74.0 CRITICAL FIX: NEVER create a fake 16-byte stub for `.max` or `.rvt`!
                    # Always require the browser to upload the REAL file bytes so `3dsmaxbatch.exe` receives the actual scene.
                    return _arch_jsonify({"ok": False, "need_full_upload": True}), 200
            elif jbody.get("file_path") and os.path.isfile(str(jbody["file_path"])):
                saved_path = str(jbody["file_path"])
                orig_name = os.path.basename(saved_path)
            elif jbody.get("base64") or jbody.get("content_base64") or jbody.get("data"):
                b64_str = str(jbody.get("base64") or jbody.get("content_base64") or jbody.get("data"))
                if "," in b64_str:
                    b64_str = b64_str.split(",", 1)[1]
                orig_name = str(jbody.get("filename") or jbody.get("name") or "external_plan.png")
                raw_ext = os.path.splitext(orig_name)[1].lower() or ".png"
                saved_path = os.path.join(site_dir, f"ext_plan_{uuid.uuid4().hex[:8]}{raw_ext}")
                with open(saved_path, "wb") as bf:
                    bf.write(base64.b64decode(b64_str))

        if not saved_path or not os.path.isfile(saved_path):
            return _arch_jsonify({
                "status": "error",
                "ok": False,
                "error": "فایل پلان/نمای خارجی در درخواست ارسالی یافت نشد.",
                "message": "فایل پلان/نمای خارجی در درخواست ارسالی یافت نشد.",
            }), 400

        try:
            proj_sig_in = str(
                _arch_req.args.get("project_sig")
                or _arch_req.form.get("project_sig")
                or (_arch_req.get_json(silent=True) or {}).get("project_sig")
                or ""
            ).strip()
            _orig_f_sz = os.path.getsize(saved_path) if os.path.isfile(saved_path) else 0
            ext_info = parse_external_plan_or_elevation(saved_path, user_hint=f"{user_hint} {orig_name}".strip())
            _upload_uid = uuid.uuid4().hex[:10]
            ext_info["upload_id"] = _upload_uid
            ext_info["original_filename"] = orig_name
            ext_info["original_file_size"] = _orig_f_sz
            if proj_sig_in:
                ext_info["project_sig"] = proj_sig_in
            # v66.0 Zero-Bloat Disk Guard: Once a huge (> 20 MB) 3D file (`.obj`, `.fbx`, `.max`, `.glb`, `.rvt`)
            # has been parsed into its compact `*_mesh_cache.npz` (~1.5 MB) and `*_scene.json` (~800 KB),
            # truncate the multi-gigabyte duplicate `ext_plan_*` copy in `site/` down to a 4 KB header stub
            # so `<repo-root>` NEVER grows by 1.5-2 GB per upload!
            if (
                _orig_f_sz > 20 * 1024 * 1024
                and ext_info.get("mesh_cache_npz")
                and os.path.isfile(str(ext_info.get("mesh_cache_npz")))
                and os.path.basename(saved_path).startswith("ext_plan_")
            ):
                try:
                    with open(saved_path, "rb") as _rf_h:
                        _hdr_4k = _rf_h.read(4096)
                    with open(saved_path, "wb") as _wf_h:
                        _wf_h.write(_hdr_4k)
                except Exception:
                    pass
                # Also remove giant (>30 MB) temporary 3dsmaxbatch export `.obj`/`.fbx` once compact `mesh_cache_npz` is saved!
                try:
                    _base_no_e = os.path.splitext(saved_path)[0]
                    for _tmp_exp in (_base_no_e + "_3d_shell_3dsmax_export.obj", _base_no_e + "_3d_shell_3dsmax_export.fbx"):
                        if os.path.isfile(_tmp_exp) and os.path.getsize(_tmp_exp) > 30 * 1024 * 1024:
                            os.remove(_tmp_exp)
                except Exception:
                    pass
            save_active_external_plan_state(repo_root, p_folder, ext_info, sync_global_default=False, project_sig=proj_sig_in)
            try:
                import json as _j_up
                _sc_up = os.path.join(repo_root, "data", "site_cache")
                os.makedirs(_sc_up, exist_ok=True)
                with open(os.path.join(_sc_up, f"upload_{_upload_uid}.json"), "w", encoding="utf-8") as _uf_w:
                    _j_up.dump(ext_info, _uf_w, ensure_ascii=False, indent=2)
            except Exception:
                pass
            _sync_krocki_into_project_session(repo_root, p_folder)
            # If UI uploaded with `clean_pid == "default"`, also sync ONLY to the single newest active `project_*` directory
            try:
                projs_root = os.path.join(repo_root, "data", "projects")
                if os.path.isdir(projs_root) and clean_pid == "default":
                    p_cands = []
                    for pn in os.listdir(projs_root):
                        pd = os.path.join(projs_root, pn)
                        if pn.startswith("project_") and pn not in ("project_default", "project_v337b_probe") and os.path.isdir(pd):
                            st_f = os.path.join(pd, "session_state.json")
                            mt = os.path.getmtime(st_f) if os.path.isfile(st_f) else os.path.getmtime(pd)
                            p_cands.append((mt, pn))
                    p_cands.sort(key=lambda x: x[0], reverse=True)
                    if p_cands:
                        _, recent_pn = p_cands[0]
                        save_active_external_plan_state(repo_root, recent_pn, ext_info, sync_global_default=False, project_sig=proj_sig_in)
                        _sync_krocki_into_project_session(repo_root, recent_pn)
            except Exception:
                pass
            svg_name = f"external_plan_preview_{uuid.uuid4().hex[:6]}.svg"
            svg_path = os.path.join(renders_dir, svg_name)
            export_external_plan_preview_svg(ext_info, svg_path)
            with open(svg_path, "rb") as sf_b:
                svg_b64 = base64.b64encode(sf_b.read()).decode("ascii")
            preview_data_uri = f"data:image/svg+xml;base64,{svg_b64}"

            return _arch_jsonify({
                "status": "success",
                "ok": True,
                "success": True,
                "project_id": p_folder,
                "upload_id": ext_info.get("upload_id", ""),
                "original_filename": orig_name,
                "scene_3d_json_path": ext_info.get("scene_3d_json_path", ""),
                "mesh_cache_npz": ext_info.get("mesh_cache_npz", ""),
                "external_plan_info": ext_info,
                "doc_type": ext_info["doc_type"],
                "doc_type_fa": ext_info["doc_type_fa"],
                "total_floors": ext_info["total_floors"],
                "floors_desc_fa": ext_info["floors_desc_fa"],
                "elevation_codes_m": ext_info["elevation_codes_m"],
                "preview_url": preview_data_uri,
                "svg_url": preview_data_uri,
                "image_url": preview_data_uri,
                "summary_fa": ext_info["summary_fa"],
                "reply": (
                    f"📐 **{ext_info['summary_fa']}**\n"
                    f"🧱 **فایل‌های سه‌بعدی تولیدشده برای Blender و BIM**:\n"
                    f"- `GLB (Blender -> Import -> glTF 2.0)`: `{ext_info.get('glb_shell_path') or ''}`\n"
                    f"- `OBJ (Blender -> Import -> Wavefront .obj)`: `{ext_info.get('obj_shell_path') or ''}`\n"
                    f"- `IFC4 (SweptSolid 3D BIM)`: `{ext_info.get('ifc_shell_path') or ''}`\n"
                    f"✅ اکنون می‌توانید در چت بنویسید: «از نمای جنوبی با سبک نئوکلاسیک و سنگ تراورتن کرم رندر بگیر» یا «رندر شبش رو بگیر»."
                ),
                "message": ext_info["summary_fa"],
            }), 200
        except Exception as exc:
            return _arch_jsonify({
                "status": "error",
                "ok": False,
                "error": str(exc),
                "message": f"خطا در تحلیل پلان/نمای خارجی: {exc}",
                "reply": f"⚠️ خطا در تحلیل پلان/نمای خارجی: {exc}",
            }), 200

    def _handle_krocki_upload_request():
        import base64
        import os
        import uuid
        from core.site.krocki_cad_reader_v27 import (
            parse_krocki_dxf_or_dwg,
            export_krocki_preview_svg,
            save_active_krocki_state,
        )

        if _arch_req.method == "OPTIONS":
            return _arch_jsonify({"status": "ok"}), 200

        repo_root = _resolve_arch_repo_root()
        project_id = (
            _arch_req.args.get("project_id")
            or _arch_req.form.get("project_id")
            or (_arch_req.get_json(silent=True) or {}).get("project_id")
            or ""
        )
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        p_folder, proj_dir = _resolve_real_existing_project_folder(repo_root, clean_pid)
        site_dir = os.path.join(proj_dir, "site")
        renders_dir = os.path.join(proj_dir, "renders")
        os.makedirs(site_dir, exist_ok=True)
        os.makedirs(renders_dir, exist_ok=True)

        saved_path = None
        orig_name = "krocki.dxf"

        if _arch_req.files:
            file_obj = (
                _arch_req.files.get("file")
                or _arch_req.files.get("krocki")
                or _arch_req.files.get("krocki_file")
                or next(iter(_arch_req.files.values()), None)
            )
            if file_obj is not None:
                orig_name = str(getattr(file_obj, "filename", "") or "krocki.dxf")
                raw_ext = os.path.splitext(orig_name)[1].lower()
                if raw_ext not in (".dxf", ".dwg"):
                    raw_ext = ".dwg" if "dwg" in orig_name.lower() else ".dxf"
                saved_path = os.path.join(site_dir, f"krocki_{uuid.uuid4().hex[:8]}{raw_ext}")
                file_obj.save(saved_path)

        if saved_path is None:
            jbody = _arch_req.get_json(silent=True) or {}
            if jbody.get("file_path") and os.path.isfile(str(jbody["file_path"])):
                saved_path = str(jbody["file_path"])
                orig_name = os.path.basename(saved_path)
            elif jbody.get("base64") or jbody.get("content_base64") or jbody.get("data"):
                b64_str = str(jbody.get("base64") or jbody.get("content_base64") or jbody.get("data"))
                if "," in b64_str:
                    b64_str = b64_str.split(",", 1)[1]
                orig_name = str(jbody.get("filename") or jbody.get("name") or "krocki.dxf")
                raw_ext = os.path.splitext(orig_name)[1].lower()
                if raw_ext not in (".dxf", ".dwg"):
                    raw_ext = ".dxf"
                saved_path = os.path.join(site_dir, f"krocki_{uuid.uuid4().hex[:8]}{raw_ext}")
                with open(saved_path, "wb") as bf:
                    bf.write(base64.b64decode(b64_str))

        if not saved_path or not os.path.isfile(saved_path):
            return _arch_jsonify({
                "status": "error",
                "ok": False,
                "error": "فایل کروکی در درخواست ارسالی یافت نشد.",
                "message": "فایل کروکی در درخواست ارسالی یافت نشد.",
            }), 400

        try:
            krocki_info = parse_krocki_dxf_or_dwg(saved_path)
            krocki_info["original_filename"] = orig_name
            save_active_krocki_state(repo_root, clean_pid, krocki_info)
            _sync_krocki_into_project_session(repo_root, clean_pid)
            svg_name = f"krocki_preview_{uuid.uuid4().hex[:6]}.svg"
            svg_path = os.path.join(renders_dir, svg_name)
            export_krocki_preview_svg(krocki_info, svg_path)
            export_krocki_preview_svg(krocki_info, os.path.join(renders_dir, "krocki_preview.svg"))
            with open(svg_path, "rb") as sf_b:
                svg_b64 = base64.b64encode(sf_b.read()).decode("ascii")
            preview_data_uri = f"data:image/svg+xml;base64,{svg_b64}"

            return _arch_jsonify({
                "status": "success",
                "ok": True,
                "success": True,
                "project_id": p_folder,
                "krocki_info": krocki_info,
                "krocki": krocki_info,
                "site": krocki_info,
                "width_m": krocki_info["width_m"],
                "length_m": krocki_info["length_m"],
                "site_area_m2": krocki_info["site_area_m2"],
                "area_m2": krocki_info["site_area_m2"],
                "vertex_count": krocki_info["vertex_count"],
                "is_irregular_polygon": krocki_info["is_irregular_polygon"],
                "street_sides": krocki_info.get("street_sides", ["SOUTH"]),
                "party_wall_sides": krocki_info.get("party_wall_sides", ["WEST"]),
                "boundary_neighbors": krocki_info.get("boundary_neighbors", {}),
                "boundary_labels_fa": krocki_info.get("boundary_labels_fa", {}),
                "south_y_west_mm": krocki_info.get("south_y_west_mm", 0),
                "south_y_east_mm": krocki_info.get("south_y_east_mm", 0),
                "preview_url": preview_data_uri,
                "svg_url": preview_data_uri,
                "image_url": preview_data_uri,
                "summary_fa": krocki_info["summary_fa"],
                "reply": f"📐 {krocki_info['summary_fa']}\n✅ اکنون می‌توانید دستور طراحی پلان روی این زمین را در چت بنویسید.",
                "message": krocki_info["summary_fa"],
            }), 200
        except Exception as exc:
            return _arch_jsonify({
                "status": "error",
                "ok": False,
                "error": str(exc),
                "message": f"خطا در تحلیل کروکی: {exc}",
                "reply": f"⚠️ خطا در تحلیل کروکی: {exc}",
            }), 200

    for _k_route in (
        "/api/site/upload_krocki",
        "/api/site/krocki",
        "/api/krocki",
        "/api/upload_krocki",
        "/api/site/upload",
    ):
        try:
            app.add_url_rule(
                _k_route,
                endpoint=f"archos_krocki_{_k_route.replace('/', '_')}",
                view_func=_handle_krocki_upload_request,
                methods=["POST", "OPTIONS"],
            )
        except Exception:
            pass

    def _handle_latest_render_query():
        import base64
        import os
        repo_root = _resolve_arch_repo_root()
        pid = str(_arch_req.args.get("project_id") or "default").strip()
        if pid.lower() in ("", "null", "none", "undefined"):
            pid = "default"
        p_folder, proj_dir_lat = _resolve_real_existing_project_folder(repo_root, pid)
        _sync_project_renders_and_assets(repo_root, p_folder)
        cands = []
        for r_dir in (
            os.path.join(proj_dir_lat, "renders"),
            os.path.join(repo_root, "outputs", "plans", p_folder, "renders"),
            os.path.join(repo_root, "data", "site_cache", "renders"),
        ):
            if os.path.isdir(r_dir):
                for fn in os.listdir(r_dir):
                    if (fn.startswith("render_") or fn.startswith("ArchitectOS_")) and fn.lower().endswith((".png", ".jpg", ".jpeg")) and not fn.lower().endswith(("_depth.png", "_lineart.png", "_comfy_input.png", "_comfy_input.jpg")) and "_comfy_" not in fn.lower() and "_depth_" not in fn.lower() and "_lineart_" not in fn.lower():
                        fp = os.path.join(r_dir, fn)
                        cands.append((os.path.getmtime(fp), fp, fn))
        if not cands:
            return _arch_jsonify({"ok": False}), 200
        cands.sort(key=lambda x: x[0], reverse=True)
        _, latest_fp, latest_fn = cands[0]
        with open(latest_fp, "rb") as rf:
            b64 = base64.b64encode(rf.read()).decode("ascii")
        d_uri = f"data:image/png;base64,{b64}"
        return _arch_jsonify({
            "ok": True,
            "filename": latest_fn,
            "saved_location": latest_fp,
            "image_url": d_uri,
            "web_url": f"/planning/drawing/{p_folder}/renders/{latest_fn}",
        }), 200

    try:
        import os as _pid_os
        _pid_root = _resolve_arch_repo_root()
        _pid_dir = _pid_os.path.join(_pid_root, "logs", "runtime")
        _pid_os.makedirs(_pid_dir, exist_ok=True)
        _is_ui_srv = _pid_os.path.basename(_pid_os.path.dirname(_pid_os.path.abspath(__file__))).lower() == "ui"
        _pid_fn = _pid_os.path.join(_pid_dir, "ui.pid" if _is_ui_srv else "orchestrator.pid")
        with open(_pid_fn, "w", encoding="utf-8") as _pf:
            _pf.write(str(_pid_os.getpid()))
    except Exception:
        pass

    def _resolve_latest_active_ext_plan_json(repo_root: str, clean_pid: str, project_sig: str = "", selected_file: str = "", upload_id: str = ""):
        import json, os
        p_folder, proj_dir_own = _resolve_real_existing_project_folder(repo_root, clean_pid, project_sig=project_sig)
        # 0) If `upload_id` was explicitly passed by UI, load that exact upload record immediately (100% immune to stale project cache!)
        if upload_id:
            _up_p = os.path.join(repo_root, "data", "site_cache", f"upload_{upload_id}.json")
            if os.path.isfile(_up_p):
                try:
                    with open(_up_p, "r", encoding="utf-8") as _uf:
                        _ud = json.load(_uf)
                    return _ud, os.path.dirname(str(_ud.get("source_file") or _up_p))
                except Exception:
                    pass
        # 1) Check the requested project's OWN `site/active_external_plan.json` first!
        own_jp = os.path.join(proj_dir_own, "site", "active_external_plan.json")
        if os.path.isfile(own_jp):
            try:
                with open(own_jp, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if not project_sig or not d.get("project_sig") or str(d.get("project_sig")) == str(project_sig) or p_folder != "project_default":
                    if not selected_file or str(d.get("original_filename") or "").lower() == selected_file.lower():
                        return d, os.path.dirname(own_jp)
            except Exception:
                pass
        # 2) If `selected_file` or `project_sig` was explicitly passed by UI (e.g. `sadegh.max`), find the project matching it
        if selected_file or project_sig:
            projs_dir = os.path.join(repo_root, "data", "projects")
            cands_match = []
            if os.path.isdir(projs_dir):
                for pn in os.listdir(projs_dir):
                    jp = os.path.join(projs_dir, pn, "site", "active_external_plan.json")
                    if os.path.isfile(jp):
                        try:
                            with open(jp, "r", encoding="utf-8") as f:
                                d = json.load(f)
                            fn_match = bool(selected_file and str(d.get("original_filename") or "").lower() == selected_file.lower())
                            sig_match = bool(not selected_file and project_sig and d.get("project_sig") and str(d.get("project_sig")) == str(project_sig))
                            if fn_match or sig_match:
                                prio = 2 if (fn_match and sig_match) else (1 if fn_match else 0)
                                cands_match.append((prio, float(d.get("uploaded_at_ts") or os.path.getmtime(jp)), d, os.path.dirname(jp)))
                        except Exception:
                            pass
            if cands_match:
                cands_match.sort(key=lambda x: (x[0], x[1]), reverse=True)
                return cands_match[0][2], cands_match[0][3]
        # 3) Check `data/site_cache` or `data/active_external_plan.json` when matching `selected_file` or `project_sig`
        for jp in (
            os.path.join(repo_root, "data", "site_cache", "active_external_plan.json"),
            os.path.join(repo_root, "data", "active_external_plan.json"),
        ):
            if os.path.isfile(jp):
                try:
                    with open(jp, "r", encoding="utf-8") as f:
                        d = json.load(f)
                    if selected_file and str(d.get("original_filename") or "").lower() == selected_file.lower():
                        return d, os.path.dirname(jp)
                    if project_sig and d.get("project_sig") and str(d.get("project_sig")) != str(project_sig):
                        continue
                    if not selected_file and (p_folder == "project_default" or not project_sig):
                        return d, os.path.dirname(jp)
                except Exception:
                    pass
        return {}, os.path.join(proj_dir_own, "site")

    def _handle_3d_scene_json_query():
        import json, os
        project_id = _arch_req.args.get("project_id") or "default"
        project_sig = str(_arch_req.args.get("project_sig") or "").strip()
        selected_file = str(_arch_req.args.get("selected_file") or "").strip()
        upload_id = str(_arch_req.args.get("upload_id") or "").strip()
        has_ui_upload = str(_arch_req.args.get("has_ui_upload") or "").strip()
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        if has_ui_upload == "0" and not selected_file and not upload_id:
            return _arch_jsonify({"ok": False, "no_file_in_project": True, "elements": []}), 200
        repo_root = _resolve_arch_repo_root()
        act_d, site_dir = _resolve_latest_active_ext_plan_json(
            repo_root, clean_pid, project_sig=project_sig, selected_file=selected_file, upload_id=upload_id
        )
        sj_direct = str(act_d.get("scene_3d_json_path") or "")
        if sj_direct and os.path.isfile(sj_direct):
            with open(sj_direct, "r", encoding="utf-8") as jf:
                data = json.load(jf)
            data["ok"] = True
            data["source_filename"] = act_d.get("original_filename") or os.path.basename(str(act_d.get("source_file") or ""))
            data["is_3d_model"] = bool(act_d.get("is_3d_model") or act_d.get("is_direct_3d_bim_import"))
            data["total_floors"] = int(act_d.get("total_floors") or 1)
            norm_s = act_d.get("semantic_layer_normalization") or {}
            if isinstance(norm_s, dict) and norm_s.get("floors_2d"):
                data["floors_2d"] = norm_s["floors_2d"]
            # v76.0 CRITICAL FIX: NEVER overwrite already-parsed real `mesh_triangles` by re-parsing a 4 KB Zero-Bloat stub!
            _has_valid_tris_76 = isinstance(data.get("mesh_triangles"), list) and len(data.get("mesh_triangles")) >= 12
            if data.get("is_3d_model") and (not _has_valid_tris_76) and (not act_d.get("has_mezzanine")):
                try:
                    from core.site.krocki_cad_reader_v27 import parse_external_plan_or_elevation, save_active_external_plan_state
                    _src_m = str(act_d.get("source_file") or "")
                    if _src_m and os.path.isfile(_src_m) and os.path.getsize(_src_m) > 8192:
                        _up_info = parse_external_plan_or_elevation(_src_m, user_hint=str(act_d.get("original_filename") or ""))
                        if act_d.get("original_filename"):
                            _up_info["original_filename"] = act_d["original_filename"]
                        save_active_external_plan_state(repo_root, clean_pid, _up_info, sync_global_default=False)
                        if os.path.isfile(sj_direct):
                            with open(sj_direct, "r", encoding="utf-8") as _jf2:
                                _d2 = json.load(_jf2)
                            if _d2.get("mesh_triangles"):
                                data["mesh_triangles"] = _d2["mesh_triangles"]
                                data["has_true_3d_mesh"] = True
                                data["mesh_vertex_count"] = _d2.get("mesh_vertex_count", 0)
                                data["mesh_face_count"] = _d2.get("mesh_face_count", 0)
                except Exception:
                    pass
            return _arch_jsonify(data), 200
        cands = []
        if os.path.isdir(site_dir):
            for fn in os.listdir(site_dir):
                if fn.endswith("_scene.json") and "1d49dd1a" not in fn:
                    fp = os.path.join(site_dir, fn)
                    cands.append((os.path.getmtime(fp), fp))
            if not cands:
                for fn in os.listdir(site_dir):
                    if fn.endswith("_scene.json"):
                        fp = os.path.join(site_dir, fn)
                        cands.append((os.path.getmtime(fp), fp))
        if not cands:
            return _arch_jsonify({"ok": False, "elements": []}), 200
        cands.sort(key=lambda x: x[0], reverse=True)
        with open(cands[0][1], "r", encoding="utf-8") as jf:
            data = json.load(jf)
        data["ok"] = True
        return _arch_jsonify(data), 200

    def _handle_cad_layers_api():
        import json, os
        try:
            from core.planning.multifloor_v1.engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder
        except ImportError:
            try:
                from architectos_v3_engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder
            except ImportError:
                from engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder
        _jb_cad = (_arch_req.get_json(silent=True) or {}) if _arch_req.method != "GET" else {}
        project_id = (_arch_req.args.get("project_id") if _arch_req.method == "GET" else _jb_cad.get("project_id")) or "default"
        project_sig_c = str((_arch_req.args.get("project_sig") if _arch_req.method == "GET" else _jb_cad.get("project_sig")) or "").strip()
        selected_file_c = str((_arch_req.args.get("selected_file") if _arch_req.method == "GET" else _jb_cad.get("selected_file")) or "").strip()
        upload_id_c = str((_arch_req.args.get("upload_id") if _arch_req.method == "GET" else _jb_cad.get("upload_id")) or "").strip()
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        repo_root = _resolve_arch_repo_root()
        act_d, site_dir = _resolve_latest_active_ext_plan_json(
            repo_root, clean_pid, project_sig=project_sig_c, selected_file=selected_file_c, upload_id=upload_id_c
        )
        # v66.0: ALWAYS prefer the user's real uploaded 2D `.dwg`/`.dxf` file (`source_file`), NEVER `_vectorized.dxf`!
        src_cand = str(act_d.get("source_file") or "")
        if act_d.get("is_3d_model") or src_cand.lower().endswith((".obj", ".max", ".3ds", ".rvt", ".ifc", ".glb", ".gltf", ".fbx")):
            return _arch_jsonify({
                "ok": True,
                "is_3d_model": True,
                "source_filename": act_d.get("original_filename") or os.path.basename(src_cand),
                "canonical_layers": [],
                "preview_entities": [],
                "floors_2d": [],
                "text_entities": [],
            }), 200
        if src_cand.lower().endswith((".dwg", ".dxf")) and not src_cand.lower().endswith(("_vectorized.dxf", "_normalized_layers.dxf", "_elevations_and_sections.dxf")) and os.path.isfile(src_cand):
            cad_fp = src_cand
        else:
            cad_fp = ""
            cands_c = []
            search_dirs = [site_dir]
            for s_dir in search_dirs:
                if os.path.isdir(s_dir):
                    for fn in os.listdir(s_dir):
                        fn_l = fn.lower()
                        if fn_l.endswith((".dwg", ".dxf")) and not fn_l.endswith(("_vectorized.dxf", "_elevations_and_sections.dxf", "_normalized_layers.dxf")) and "1d49dd1a" not in fn_l:
                            fp = os.path.join(s_dir, fn)
                            # Prioritize .dwg files uploaded by the user
                            prio = 1 if fn_l.endswith(".dwg") else 0
                            cands_c.append((prio, os.path.getmtime(fp), fp))
            if cands_c:
                cands_c.sort(key=lambda x: (x[0], x[1]), reverse=True)
                cad_fp = cands_c[0][2]
        overrides = {}
        apply_all_floors = False
        if _arch_req.method == "POST":
            body = _arch_req.get_json(silent=True) or {}
            overrides = body.get("layer_overrides") or {}
            apply_all_floors = bool(body.get("apply_all_floors", False))
        res = MultiStoryCAD3DShellExtruder.auto_normalize_and_rewrite_dxf_layers(
            cad_fp, user_layer_overrides=overrides, apply_all_floors=apply_all_floors
        )
        if act_d.get("original_filename"):
            res["source_filename"] = act_d["original_filename"]
        return _arch_jsonify(res), 200

    def _handle_download_bim_bundle():
        import os, zipfile, tempfile
        from flask import send_file as _arch_send_file
        project_id = _arch_req.args.get("project_id") or "default"
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        repo_root = _resolve_arch_repo_root()
        site_dir = os.path.join(repo_root, "data", "projects", p_folder, "site")
        z_tmp = os.path.join(tempfile.gettempdir(), f"{p_folder}_Revit_BIM_Bundle_v50.zip")
        with zipfile.ZipFile(z_tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.isdir(site_dir):
                for fn in sorted(os.listdir(site_dir)):
                    if fn.endswith((".ifc", ".glb", ".obj", ".mtl", "_revit_journal.txt", "_build_revit_rvt.py", "_elevations_and_sections.dxf", "_normalized_layers.dxf")):
                        fp = os.path.join(site_dir, fn)
                        if os.path.isfile(fp):
                            zf.write(fp, arcname=fn)
        return _arch_send_file(z_tmp, as_attachment=True, download_name=f"{p_folder}_Revit_IFC_RVT_Bundle.zip")

    try:
        app.add_url_rule("/api/3d/scene_json", endpoint="archos_3d_scene_json_v48", view_func=_handle_3d_scene_json_query, methods=["GET"])
        app.add_url_rule("/api/cad/layers", endpoint="archos_cad_layers_v49", view_func=_handle_cad_layers_api, methods=["GET", "POST"])
        app.add_url_rule("/api/cad/reclassify_layers", endpoint="archos_cad_reclassify_v49", view_func=_handle_cad_layers_api, methods=["POST"])
        app.add_url_rule("/api/3d/download_bim", endpoint="archos_download_bim_v50", view_func=_handle_download_bim_bundle, methods=["GET"])
    except Exception:
        pass

    try:
        app.add_url_rule("/api/render/latest" , endpoint="archos_latest_render_v33_7", view_func=_handle_latest_render_query, methods=["GET"])
    except Exception:
        pass

    for _ep_route in (
        "/api/plan/upload_external",
        "/api/site/upload_plan",
        "/api/upload_plan",
    ):
        try:
            app.add_url_rule(
                _ep_route,
                endpoint=f"archos_extplan_{_ep_route.replace('/', '_')}",
                view_func=_handle_external_plan_upload_request,
                methods=["POST", "OPTIONS"],
            )
        except Exception:
            pass

    @app.before_request
    def _architectos_v27_1_krocki_interceptor():
        path_low = (_arch_req.path or "").lower()
        if _arch_req.method == "GET" and path_low.rstrip("/") == "/api/3d/scene_json":
            return _handle_3d_scene_json_query()
        if path_low.rstrip("/") in ("/api/cad/layers", "/api/cad/reclassify_layers"):
            return _handle_cad_layers_api()
        if _arch_req.method == "GET" and path_low.rstrip("/") == "/api/3d/download_bim":
            return _handle_download_bim_bundle()
        if _arch_req.method == "GET" and path_low.rstrip("/") == "/api/render/latest":
            return _handle_latest_render_query()
        if _arch_req.method in ("POST", "OPTIONS") and ("upload_external" in path_low or "upload_plan" in path_low):
            return _handle_external_plan_upload_request()
        if _arch_req.method in ("POST", "OPTIONS") and ("krocki" in path_low or "/api/site/upload" in path_low or "/api/site/parse" in path_low):
            return _handle_krocki_upload_request()
        if _arch_req.method == "POST" and path_low.rstrip("/") in ("/api/chat", "/api/render", "/api/generate"):
            _jb = _arch_req.get_json(silent=True) or {}
            if _jb.get("external_plan_upload_only") or _jb.get("action") == "upload_external_plan":
                return _handle_external_plan_upload_request()
            if _jb.get("krocki_upload_only") or _jb.get("action") == "upload_krocki":
                return _handle_krocki_upload_request()
            _pid = str(_jb.get("project_id") or _arch_req.args.get("project_id") or "")
            _repo = _resolve_arch_repo_root()
            if _pid:
                _sync_krocki_into_project_session(_repo, _pid)
                _sync_project_renders_and_assets(_repo, _pid)
            _user_txt = str(_jb.get("message") or _jb.get("prompt") or _jb.get("text") or "").strip()
            _has_ref_id = bool(_jb.get("reference_id") or _jb.get("reference") or _jb.get("style_reference"))
            if _is_3d_facade_render_chat_command(_user_txt) or (_has_ref_id and not any(k in _user_txt for k in ("پلان", "طراحی کن", "بساز"))):
                if path_low.rstrip("/") in ("/api/chat", "/api/render", "/api/generate"):
                    if not _user_txt and _has_ref_id:
                        _jb["message"] = "از این مدل سه‌بعدی با رفرنس سبک انتخابی رندر واقعی بگیر"
                    return _handle_plan_locked_3d_render_request(_jb)

    @app.after_request
    def _architectos_v30_asset_sync_after_request(response):
        try:
            path_low = (_arch_req.path or "").lower()
            if "/api/chat" in path_low or "/api/project" in path_low or "/api/session" in path_low:
                _jb = _arch_req.get_json(silent=True) or {}
                _pid = str(_jb.get("project_id") or _arch_req.args.get("project_id") or "")
                if _pid:
                    _sync_project_renders_and_assets(_resolve_arch_repo_root(), _pid)
        except Exception:
            pass
        return response

except Exception as _arch_hook_err:
    print("[!] Warning registering ArchitectOS v66.0 Krocki, External Plan & Render routes:", _arch_hook_err)
# [/ARCHITECTOS_V27_1_KROCKI_UPLOAD_INTERCEPTOR]


if __name__ == "__main__":


    # LOG_ROTATION_FIX_01 — bound the Core API's own log file.
    # Werkzeug emits one access line per request; without a rotating
    # handler the redirected stdout grew unbounded (1.26 GB, ~4.9 MB/min
    # under UI polling). This keeps errors + tracebacks, bounds volume.
    try:

        from core.runtime_logging import configure_runtime_logging

        configure_runtime_logging("core_api")

    except Exception:

        # Logging setup must never prevent the API from starting.
        pass


    print(
        "🚀 ArchitectOS API v36.1 RUNNING"
    )


    print(
        "🌐 CORE API:",
        RC.CORE_API_URL
    )


    app.run(

        host=RC.CORE_API_BIND_HOST,

        port=RC.CORE_API_PORT,

        debug=False

    )
