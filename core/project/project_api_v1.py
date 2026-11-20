# ==========================================================
# ArchitectOS Project API v1
#
# PROJECT_WORKSPACE_UI_06 — project lifecycle, assets, gallery,
# export / archive / delete, save state, mode + strategy catalog.
#
# Read/write HTTP surface for the workspace UI. It owns no storage
# logic: everything is delegated to the project layer.
# ==========================================================


from __future__ import annotations


import os

from flask import Blueprint, jsonify, request


from core.project.project_workspace_v1 import project_workspace

from core.project.project_session_v1 import project_session

from core.project.conversation_store_v1 import conversation_store

from core.project.project_registry_bridge_v1 import (
    project_registry_bridge,
)

from core.render.render_strategy_controller_v1 import (
    mode_catalog,
    resolve_strategy,
    ACTIVE_MODES,
    RESERVED_MODES,
)


project_api = Blueprint("project_api", __name__)


def _project_or_404(project_id):

    manifest = project_workspace.load(project_id)

    if not manifest:

        return None, (jsonify({
            "status": "error",
            "error": "project_not_found",
            "project_id": project_id,
        }), 404)

    return manifest, None


def _public_manifest(manifest):

    if not isinstance(manifest, dict):

        return None

    out = dict(manifest)

    out["storage_path"] = project_workspace.project_dir(
        manifest.get("project_id")
    )

    return out


# ==========================================================
# MATERIAL_REVIEW_READONLY_UI_V1 — read-only projection of durable
# pending material-correction review carriers.
#
# MATERIAL_REVIEW_UI_SECURITY_ACCEPTANCE_V1 — the projection is now
# BOTH field-minimized AND access-gated.
#
# Access gate
#   The Core project-detail route has NO authentication of its own: it
#   is loopback-bound and was always readable by any local process.  That
#   pre-existing exposure was accepted for the transcript.  It is NOT
#   accepted for the structured vision evidence carried by a review
#   (provenance, ontology identity, confidence), so `material_reviews`
#   is emitted ONLY for a request that carries a valid trusted-local
#   gateway signature — the SAME accepted mechanism CODER-05.2 already
#   uses.  Unauthorized requests receive an empty list; the field is
#   never silently omitted, so a caller can tell "authorized but none
#   pending" from "not authorized".
#
# Field minimization
#   Only what the compact UI card actually renders is projected.  Whole
#   carrier sub-objects are never echoed: `knowledge_candidate`,
#   `confirmation_review`, and the full observation object stay
#   server-side.  Observation uncertainty (confidence) and source
#   attribution (provider / model / image_id) are RETAINED, because the
#   card must not present a correction as better-evidenced than it is.
# ==========================================================


def _trusted_local_read_authorized():
    """True only for a signed request from the trusted-local UI gateway.

    Reuses the accepted CODER-05.2 signing contract (HMAC over
    actor/session/timestamp/nonce/path/payload).  A GET has no body, so
    the signed payload is empty and the signed path is the request path.
    Fails closed on any error, including a missing/too-short secret.
    """

    try:
        import os as _os

        from core.runtime.local_authorization_v1 import verify_proxy_request

        result = verify_proxy_request(
            _os.environ.get("ARCHITECTOS_LOCAL_PROXY_SECRET", ""),
            request.headers,
            {},
            path=request.path,
            remote_addr=request.remote_addr,
        )
        return bool(result.get("trusted") is True)
    except Exception:
        return False


def _material_label(identity):
    """The single display label for a material identity object."""

    if not isinstance(identity, dict):
        return None
    return (
        identity.get("material_label")
        or identity.get("label")
        or identity.get("ontology_normalized")
        or identity.get("identity")
        or identity.get("ontology_id")
    )


def _public_material_reviews(project_id, authorized=False):
    """Return the minimized, read-only display contract for pending reviews.

    Returns [] when `authorized` is false — the access gate lives here so
    that no caller can obtain review fields by forgetting to check it.
    """

    if authorized is not True:
        return []

    try:
        records = conversation_store.material_correction_reviews(
            project_id, pending_only=True
        )
    except Exception:
        return []

    summary = []
    for record in records:
        if not isinstance(record, dict):
            continue

        provenance = record.get("observation_provenance") or {}
        previous = record.get("previous_observation") or {}
        observed = record.get("original_observation") or {}
        existing_materials = (
            observed.get("existing_materials")
            if isinstance(observed, dict) else None
        )
        first_material = (
            existing_materials[0]
            if isinstance(existing_materials, list)
            and existing_materials
            and isinstance(existing_materials[0], dict)
            else {}
        )
        spatial = record.get("spatial_grounding") or {}
        execution = record.get("execution_capability") or {}
        lifecycle = record.get("lifecycle") or {}
        authentication = record.get("authentication") or {}
        origin = record.get("origin") or {}
        image_identity = origin.get("image_identity") or {}

        # The observed confidence lives on the previous-observation entry;
        # the normalized existing-material entry is the fallback.
        confidence = None
        if isinstance(previous, dict):
            confidence = previous.get("observation_confidence")
        if confidence is None and isinstance(first_material, dict):
            confidence = first_material.get("observation_confidence")

        summary.append({
            # Review identity — exact, server-validated.
            "review_id": record.get("review_id"),

            # The user's verbatim correction (also present in the
            # transcript, so this adds no new disclosure class).
            "original_correction_text": record.get("original_correction_text"),

            # Material identities, flattened to the display label only.
            "previous_material_label": _material_label(
                record.get("previous_observation")
            ),
            "corrected_material_label": _material_label(
                record.get("corrected_material")
            ),

            # Observation uncertainty — retained deliberately.
            "observation_confidence": confidence,

            # Source attribution — retained deliberately, trimmed to the
            # three fields the card shows.
            "observation_provenance": {
                "provider": provenance.get("provider"),
                "model": provenance.get("model"),
                "image_id": provenance.get("image_id"),
            },

            # Where the review came from.
            "project_id": origin.get("project_id"),
            "image_id": image_identity.get("image_id"),

            # Capability / grounding state — status only.
            "spatial_grounding_status": spatial.get("status"),
            "execution_capability_status": execution.get("status"),

            # Lifecycle — state only; human_confirmed is always False for
            # a pending record, so it is asserted rather than echoed.
            "state": lifecycle.get("state"),
            "human_confirmed": False,
            "confirmation_enabled": authentication.get("confirmation_enabled"),
        })

    return summary


# ==========================================================
# CATALOG
# ==========================================================

@project_api.route("/api/render/modes", methods=["GET"])
def render_modes():

    return jsonify(mode_catalog())


@project_api.route("/api/render/strategy", methods=["POST"])
def render_strategy():

    data = request.get_json(silent=True) or {}

    return jsonify(resolve_strategy(
        user_text=data.get("text", ""),
        requested_mode=data.get("mode"),
        requested_profile=data.get("quality") or data.get("render_profile"),
        seed_mode=data.get("seed_mode"),
        seed_value=data.get("seed_value"),
        previous_seed=data.get("previous_seed"),
        allow_production_profile=bool(data.get("allow_quality_override")),
    ))


# ==========================================================
# PROJECT CRUD
# ==========================================================

@project_api.route("/api/projects", methods=["GET"])
def list_projects():

    limit = request.args.get("limit", 20)

    try:

        limit = int(limit)

    except (TypeError, ValueError):

        limit = 20

    recent = project_workspace.list_recent(limit=limit)

    archived = project_workspace.list_archived()

    return jsonify({

        "status": "success",

        "contract": "ProjectListV1",

        "recent": [_public_manifest(p) for p in recent],
        "archived": [_public_manifest(p) for p in archived],

        "recent_count": len(recent),
        "archived_count": len(archived),

        "open_project_id": project_session.current_project_id(),

        "storage_root": project_workspace.projects_root,
    })


@project_api.route("/api/projects", methods=["POST"])
def create_project():

    data = request.get_json(silent=True) or {}

    name = data.get("name") or data.get("project_name")

    try:

        manifest = project_workspace.create(
            name,
            description=data.get("description"),
        )

    except ValueError as error:

        return jsonify({
            "status": "error",
            "error": str(error),
        }), 400

    # a newly created project becomes the open one
    project_session.open(manifest["project_id"])

    return jsonify({
        "status": "success",
        "project": _public_manifest(
            project_workspace.load(manifest["project_id"])
        ),
        "save_state": project_session.save_state(
            manifest["project_id"]
        ),
    })


@project_api.route("/api/projects/<project_id>", methods=["GET"])
def get_project(project_id):

    manifest, error = _project_or_404(project_id)

    if error:

        return error

    return jsonify({

        "status": "success",

        "project": _public_manifest(manifest),

        "recovery": project_session.recovery_summary(project_id),

        # PROJECT_HISTORY_RESTORATION_V1 — the stored turns of THIS project,
        # so the workspace can render a reopened conversation instead of
        # only reporting its message count. Additive and read-only.
        "transcript": project_session.transcript(project_id),

        # MATERIAL_REVIEW_READONLY_UI_V1 — pending material-correction
        # reviews for THIS project, minimized to the display contract.
        # MATERIAL_REVIEW_UI_SECURITY_ACCEPTANCE_V1 — emitted only for a
        # valid trusted-local gateway signature; [] otherwise.
        "material_reviews": _public_material_reviews(
            project_id, authorized=_trusted_local_read_authorized()
        ),

        "save_state": project_session.save_state(project_id),

        "is_open": project_session.current_project_id() == project_id,
    })


@project_api.route("/api/projects/<project_id>/open", methods=["POST"])
def open_project(project_id):

    manifest = project_session.open(project_id)

    if not manifest:

        return jsonify({
            "status": "error",
            "error": "project_not_found",
        }), 404

    return jsonify({

        "status": "success",

        "project": _public_manifest(
            project_workspace.load(project_id)
        ),

        "recovery": project_session.recovery_summary(project_id),

        "save_state": project_session.save_state(project_id),

        "gallery": project_registry_bridge.gallery(project_id),
    })


@project_api.route("/api/projects/<project_id>/close", methods=["POST"])
def close_project(project_id):

    if project_session.current_project_id() == project_id:

        return jsonify({
            "status": "success",
            "close": project_session.close(),
        })

    return jsonify({
        "status": "success",
        "close": {"status": "not_open", "project_id": project_id},
    })


@project_api.route("/api/projects/<project_id>/rename", methods=["POST"])
def rename_project(project_id):

    manifest, error = _project_or_404(project_id)

    if error:

        return error

    data = request.get_json(silent=True) or {}

    try:

        project_workspace.rename(project_id, data.get("name"))

    except ValueError as error_value:

        return jsonify({
            "status": "error",
            "error": str(error_value),
        }), 400

    project_session.autosave(project_id, reason="rename")

    return jsonify({
        "status": "success",
        "project": _public_manifest(
            project_workspace.load(project_id)
        ),
        "save_state": project_session.save_state(project_id),
    })


@project_api.route("/api/projects/<project_id>/archive", methods=["POST"])
def archive_project(project_id):

    manifest, error = _project_or_404(project_id)

    if error:

        return error

    project_session.autosave(project_id, reason="project_metadata")

    project_workspace.archive(project_id)

    return jsonify({
        "status": "success",
        "project": _public_manifest(
            project_workspace.load(project_id)
        ),
        "files_deleted": False,
    })


@project_api.route("/api/projects/<project_id>/restore", methods=["POST"])
def restore_project(project_id):

    manifest, error = _project_or_404(project_id)

    if error:

        return error

    project_workspace.restore(project_id)

    return jsonify({
        "status": "success",
        "project": _public_manifest(
            project_workspace.load(project_id)
        ),
    })


@project_api.route("/api/projects/<project_id>/delete", methods=["POST"])
def delete_project(project_id):

    manifest, error = _project_or_404(project_id)

    if error:

        return error

    data = request.get_json(silent=True) or {}

    confirmed = bool(data.get("confirmed"))

    hard = bool(data.get("hard"))

    if not confirmed:

        # Deletion is never a one-click destructive action.
        return jsonify({

            "status": "confirmation_required",

            "project_id": project_id,
            "project_name": manifest.get("project_name"),

            "message": (
                'Delete "%s"? This will remove this project and its '
                "managed project files." % manifest.get("project_name")
            ),

            "storage_path": project_workspace.project_dir(project_id),

            "actions": ["cancel", "delete_project"],

            "files_deleted": False,
        }), 409

    if project_session.current_project_id() == project_id:

        project_session.close()

    result = project_workspace.delete(
        project_id,
        hard=hard,
        confirmed=confirmed,
    )

    return jsonify({
        "status": "success",
        "delete": result,
    })


# ==========================================================
# PROJECT UI STATE
# ==========================================================

@project_api.route("/api/projects/<project_id>/ui", methods=["POST"])
def set_ui_state(project_id):

    manifest, error = _project_or_404(project_id)

    if error:

        return error

    data = request.get_json(silent=True) or {}

    ui = dict(manifest.get("ui") or {})

    for key in ("mode", "render_profile", "seed_mode", "seed_value"):

        if key in data:

            ui[key] = data.get(key)

    project_workspace.update_fields(project_id, {"ui": ui})

    project_session.autosave(project_id, reason="mode_change")

    return jsonify({
        "status": "success",
        "ui": ui,
        "save_state": project_session.save_state(project_id),
    })


@project_api.route("/api/projects/<project_id>/save-state", methods=["GET"])
def save_state(project_id):

    return jsonify({
        "status": "success",
        "save_state": project_session.save_state(project_id),
    })


@project_api.route("/api/projects/<project_id>/save", methods=["POST"])
def force_save(project_id):

    manifest, error = _project_or_404(project_id)

    if error:

        return error

    state = project_session.autosave(project_id, reason="manual")

    return jsonify({
        "status": "success",
        "save_state": state,
    })


# ==========================================================
# ASSETS
# ==========================================================

@project_api.route("/api/projects/<project_id>/assets", methods=["GET"])
def list_assets(project_id):

    manifest, error = _project_or_404(project_id)

    if error:

        return error

    filter_kind = request.args.get("filter", "all")

    return jsonify({
        "status": "success",
        "gallery": project_registry_bridge.gallery(
            project_id, filter_kind
        ),
        "storage_path": project_workspace.project_dir(project_id),
    })


@project_api.route(
    "/api/projects/<project_id>/assets/<asset_id>",
    methods=["GET"]
)
def asset_details(project_id, asset_id):

    manifest, error = _project_or_404(project_id)

    if error:

        return error

    gallery = project_registry_bridge.gallery(project_id)

    asset = None

    for item in gallery.get("assets") or []:

        if item.get("asset_id") == asset_id:

            asset = item

            break

    if asset is None:

        return jsonify({
            "status": "error",
            "error": "asset_not_found",
            "asset_id": asset_id,
        }), 404

    asset = dict(asset)

    asset["lineage"] = project_registry_bridge.lineage(
        project_id, asset_id
    )

    asset["project_storage_path"] = project_workspace.project_dir(
        project_id
    )

    # Temporary preview working copies are implementation detail and
    # must never be the primary label; expose them separately.
    asset["implementation_paths"] = {
        "preview_working_copy": (
            (asset.get("analysis") or {}).get("working_preview_path")
        ),
    }

    return jsonify({
        "status": "success",
        "asset": asset,
    })


@project_api.route(
    "/api/projects/<project_id>/assets/<asset_id>/active",
    methods=["POST"]
)
def activate_asset(project_id, asset_id):

    manifest, error = _project_or_404(project_id)

    if error:

        return error

    record = project_registry_bridge.set_active(project_id, asset_id)

    if not record:

        return jsonify({
            "status": "error",
            "error": "asset_not_found",
        }), 404

    project_session.autosave(project_id, reason="asset_activated")

    return jsonify({
        "status": "success",
        "active_asset_id": asset_id,
        "gallery": project_registry_bridge.gallery(project_id),
        "save_state": project_session.save_state(project_id),
    })


@project_api.route(
    "/api/projects/<project_id>/assets/<asset_id>/final",
    methods=["POST"]
)
def mark_final(project_id, asset_id):

    manifest, error = _project_or_404(project_id)

    if error:

        return error

    data = request.get_json(silent=True) or {}

    is_final = data.get("is_final", True)

    payload = project_registry_bridge.set_final(
        project_id, asset_id, is_final
    )

    if payload is None:

        return jsonify({
            "status": "error",
            "error": "asset_not_found",
        }), 404

    project_session.autosave(project_id, reason="mark_final")

    return jsonify({
        "status": "success",
        "is_final": bool(is_final),
        "gallery": project_registry_bridge.gallery(project_id),
    })


@project_api.route(
    "/api/projects/<project_id>/assets/<asset_id>/lineage",
    methods=["GET"]
)
def asset_lineage(project_id, asset_id):

    manifest, error = _project_or_404(project_id)

    if error:

        return error

    return jsonify({
        "status": "success",
        "lineage": project_registry_bridge.lineage(project_id, asset_id),
    })


# ==========================================================
# STORAGE / EXPORT
# ==========================================================

@project_api.route("/api/projects/<project_id>/storage", methods=["GET"])
def project_storage(project_id):

    manifest, error = _project_or_404(project_id)

    if error:

        return error

    return jsonify({
        "status": "success",
        "storage": project_workspace.storage_report(project_id),
    })


@project_api.route("/api/projects/<project_id>/export", methods=["POST"])
def export_project(project_id):

    manifest, error = _project_or_404(project_id)

    if error:

        return error

    project_session.autosave(project_id, reason="project_metadata")

    result = project_workspace.export(project_id)

    return jsonify({
        "status": "success",
        "export": {
            "destination": (result or {}).get("destination"),
            "asset_count": (result or {}).get("asset_count"),
            "manifest": os.path.join(
                (result or {}).get("destination") or "",
                "export_manifest.json",
            ),
        },
    })
