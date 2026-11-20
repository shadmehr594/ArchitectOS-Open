# ==========================================================
# ArchitectOS Image Session v1
#
# VISION_IMAGE_REGISTRY_04
#
# Orchestration layer that ties together:
#   - chat attachment persistence (uploads)
#   - the session-scoped image registry
#   - the real vision provider
#   - the safe ImageUnderstandingV1 contract
#   - deterministic reference resolution
#
# Nothing here mutates architectural geometry or design intent.
# ==========================================================


from __future__ import annotations


import os
import copy
import json
import hashlib


from core.vision.image_registry_v1 import image_registry
from core.vision.image_understanding_v1 import (
    build_understanding,
    EVIDENCE_PIPELINE_VERSION,
    STATUS_PROVIDER_UNAVAILABLE,
    STATUS_UNSUPPORTED_IMAGE,
    STATUS_FAILED,
)
from core.vision.vision_provider_ollama_v1 import (
    get_vision_provider,
)
from core.vision.reference_resolver_v1 import (
    resolve_reference,
    resolve_region_reference,
)
from core.vision.local_plan_reader_v1 import (
    local_ocr_environment,
    read_local_plan,
)


CONTRACT = "ImageSessionV1"
VERSION = "1.0"


def provider():
    """Select the provider from current runtime configuration."""

    return get_vision_provider()


def describe_provider():

    return provider().describe()



# ==========================================================
# REGISTRATION
# ==========================================================

def register_upload(
    session_id,
    file_storage,
    *,
    label=None,
):
    """Persist an uploaded file and register it in the session."""

    from core.chat.chat_attachment import chat_attachment_service

    upload = chat_attachment_service.save_upload(
        file_storage,
        source="user_upload",
        kind="image",
    )

    if upload.get("status") != "ready":

        return {
            "status": "error",
            "error": upload.get("error", "image_upload_failed"),
            "record": None,
        }

    attachment = upload.get("attachment") or {}

    record = image_registry.register(
        session_id,
        path=upload.get("path"),
        source_type="uploaded",
        label=label or attachment.get("display_name"),
        attachment=chat_attachment_service.public_attachment(attachment),
        analysis=None,
        analysis_status="pending",
        make_active=True,
    )

    return {
        "status": "ready",
        "record": record,
        "attachment": attachment,
    }


def register_asset(
    session_id,
    *,
    path,
    source_type="other",
    label=None,
    parent_image_id=None,
    asset=None,
    attachment=None,
    make_active=True,
):
    """Register an already-produced asset (e.g. a render output)."""

    return image_registry.register(
        session_id,
        path=path,
        source_type=source_type,
        label=label,
        parent_image_id=parent_image_id,
        asset=asset,
        attachment=attachment,
        analysis=None,
        analysis_status="pending",
        make_active=make_active,
    )



# ==========================================================
# ANALYSIS
# ==========================================================

def _local_plan_raw(local_plan_reading, provider_issue=None):
    """Minimal provider-shaped envelope for provider-independent evidence."""

    unresolved = [provider_issue] if provider_issue else []

    return {
        "image_type": "floor_plan_or_sketch",
        "confidence": "MEDIUM",
        "observed": [],
        "runtime_status": [{
            "evidence_type": "RUNTIME_STATUS",
            "producer": "core.vision.image_session_v1._local_plan_raw",
            "text": "floor plan raster available for local reading",
        }],
        "inferred": [],
        "architectural_elements": [],
        "text_labels_if_visible": [],
        "unresolved": unresolved,
        "local_plan_reading": local_plan_reading,
    }


# ==========================================================
# CACHE REUSE CONTRACT
#
# A stored analysis may be served again only while it is genuinely the
# CURRENT pipeline's result for the CURRENT environment. Every other
# outcome recomputes — truthfully and narrowly, without discarding any
# other project state.
# ==========================================================

def _cache_reuse_reason(record, cached):
    """Why a stored analysis may (or may not) be served again.

    LOCAL_PLAN_READING_V1 — reuse requires BOTH the evidence pipeline
    version and the local OCR environment fingerprint to match the running
    process. A stale pipeline (produced before the local plan reader
    existed) and a degraded environment (produced while the compiled OCR
    backend was unavailable) are both non-current and must be recomputed.
    """

    if record.get("analysis_status") not in ("ANALYZED", "ANALYZED_WITH_UNCERTAINTY"):

        return "no_completed_analysis"

    if not isinstance(cached, dict):

        return "not_an_understanding"

    if cached.get("evidence_pipeline") != EVIDENCE_PIPELINE_VERSION:

        return "stale_evidence_pipeline"

    if cached.get("local_ocr_environment") != local_ocr_environment():

        return "stale_local_ocr_environment"

    if cached.get("vision_cache_identity") != _provider_cache_identity(provider()):
        return "stale_vision_configuration"

    bridge = cached.get("visual_observer_bridge") or {}
    if bridge and (bridge.get("normalization", {}).get("status") != "NORMALIZED"
                   or bridge.get("raw_observer", {}).get("generation_status") != "COMPLETE"
                   or cached.get("provider_verification_error")):
        return "incomplete_visual_bridge"

    return "current"


def _provider_cache_identity(active_provider):
    identity = getattr(active_provider, "cache_identity", None)
    if callable(identity):
        return identity()
    return {"provider": active_provider.name, "model": active_provider.model,
            "adapter": "legacy-provider-v1"}


def _file_sha256(path):
    """The file's actual bytes. Never its name, ordinal or asset metadata."""

    try:
        digest = hashlib.sha256()
        with open(str(path), "rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
    except Exception:
        return None


def _reuse_identical_analysis(session_id, record):
    """A compatible analysis from a byte-identical record in the SAME session.

    Returns ``None`` — leaving the caller to run the vision boundary — whenever
    identity, ownership or compatibility cannot be established. Nothing is
    reused silently.
    """

    path = record.get("path")

    if not path or not os.path.isfile(str(path)):
        return None

    digest = _file_sha256(path)

    if not digest:
        return None

    source_type = record.get("source_type", "other")

    for sibling in image_registry.list(session_id):

        if not isinstance(sibling, dict):
            continue

        if sibling.get("image_id") == record.get("image_id"):
            continue

        # Same project only: the session IS the project scope here.
        if sibling.get("session_id") and sibling.get("session_id") != session_id:
            continue

        # An uploaded photograph may only borrow from another uploaded one.
        if sibling.get("source_type", "other") != source_type:
            continue

        cached = sibling.get("analysis")

        if not isinstance(cached, dict) or not cached:
            continue

        # Stale pipeline / OCR environment / vision configuration is refused,
        # not reused. This is the same rule the record's own cache obeys.
        if _cache_reuse_reason(sibling, cached) != "current":
            continue

        sibling_path = sibling.get("path")

        if not sibling_path or not os.path.isfile(str(sibling_path)):
            continue

        if _file_sha256(sibling_path) != digest:
            continue

        reused = copy.deepcopy(cached)

        # The analysis describes THIS record; the origin is named explicitly.
        reused["image_id"] = record.get("image_id")
        reused["source_type"] = source_type
        reused["source_hash"] = digest
        reused["reused_from_image_id"] = sibling.get("image_id")
        reused["reused_source_hash"] = digest
        reused["reuse_reason"] = "identical_content_same_project"

        return reused

    return None


def analyze_record(session_id, image_id, force=False):
    """Run local reading and the visual bridge independently, then verify claims."""
    from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT, raw_observation

    active_provider = provider()
    record = image_registry.get(session_id, image_id)
    if not record:
        return build_understanding(None, provider=active_provider.name,
                                   model=active_provider.model, image_id=image_id,
                                   provider_error="image_not_registered")
    cached = record.get("analysis")
    if not force and _cache_reuse_reason(record, cached) == "current":
        return cached

    # ======================================================
    # ORIGINAL_IMAGE_EVIDENCE_REUSE_V1
    #
    # MEASURED DEFECT: uploading a file whose BYTES are identical to an image
    # already analysed in this project created a NEW record with no analysis,
    # so the route re-ran the vision boundary. On 2026-11-04 that call hit
    # `ReadTimeout … read timeout=10800` and returned zero observations, and a
    # facade design that had 18 usable elements an hour earlier was refused
    # for lack of architectural evidence.
    #
    # The registry has never hashed content and `_cache_reuse_reason` is
    # per-record, so nothing could bridge the two records. This does the
    # smallest thing that closes that gap: if a sibling record in the SAME
    # session holds an analysis that is still `current` for a file with the
    # SAME sha256, reuse it instead of inferring again.
    #
    # Every guarantee the task requires is enforced here:
    #   * identity is the file's sha256, never its name or ordinal;
    #   * the sibling must be in the same session (same project);
    #   * the analysis must pass `_cache_reuse_reason` == "current", so a stale
    #     pipeline, a degraded OCR environment or a changed vision
    #     configuration is refused rather than reused silently;
    #   * the whole analysis is copied, so provenance, confidence and the
    #     `unresolved` uncertainty survive untouched;
    #   * `analysis_status` is never promoted and `image_type` is never
    #     rewritten;
    #   * the source record is named in `reused_from_image_id`.
    # An explicit `force=True` re-analysis still bypasses all of this.
    # ======================================================
    if not force:
        reused = _reuse_identical_analysis(session_id, record)
        if reused is not None:
            image_registry.set_analysis(
                session_id, image_id, reused, reused.get("analysis_status")
            )
            return reused
    path = record.get("path")
    readable = bool(path and os.path.isfile(str(path)))
    local = None
    if readable:
        try:
            local = read_local_plan(str(path))
        except Exception as exc:
            local = {"contract": "LocalPlanReadingV1", "status": "unavailable",
                     "provider_independent": True, "labels": [], "openings": [],
                     "reason": "local_plan_reader_error:" + str(exc)}
    raw = None
    error = None
    try:
        if not readable:
            error = "image_not_readable"
        elif not active_provider.is_available():
            error = "no_vision_provider_configured"
        else:
            raw = active_provider.analyze({"path": str(path)})
    except Exception as exc:
        error = "provider_error:" + str(exc)
    if isinstance(raw, str):
        error = "provider_non_structured_output"
        raw = {"contract": BRIDGE_CONTRACT,
               "raw_observer": raw_observation(
                   provider=active_provider.name, model=active_provider.model,
                   backend=getattr(active_provider, "endpoint", "unknown"),
                   thinking_mode=None, body={"response": raw}, error=error),
               "normalization": {"status": "NOT_RUN", "reason": error}}
    if raw is None:
        raw = {"contract": BRIDGE_CONTRACT,
               "raw_observer": raw_observation(
                   provider=active_provider.name, model=active_provider.model,
                   backend=getattr(active_provider, "endpoint", "unknown"),
                   thinking_mode=None, error=error),
               "normalization": {"status": "NOT_RUN", "reason": error}}
    # An old image-to-JSON adapter must not bypass candidate verification.
    # Retain its complete payload for diagnostics; local-only use still works.
    if isinstance(raw, dict) and raw.get("contract") != BRIDGE_CONTRACT:
        raw = {"contract": BRIDGE_CONTRACT,
               "raw_observer": raw_observation(
                   provider=active_provider.name, model=active_provider.model,
                   backend=getattr(active_provider, "endpoint", "unknown"),
                   thinking_mode=None,
                   body={"response": json.dumps(raw, ensure_ascii=False, default=str),
                         "legacy_payload": copy.deepcopy(raw)}),
               "normalization": {"status": "NOT_RUN",
                                 "reason": "legacy_provider_requires_observer_adapter"}}
    understanding = build_understanding(
        raw, provider=active_provider.name, model=active_provider.model,
        image_id=image_id, source_type=record.get("source_type", "other"),
        local_plan_reading=local,
    )
    if not readable:
        understanding["analysis_status"] = STATUS_UNSUPPORTED_IMAGE
    elif error and error != "no_vision_provider_configured" and not (
            isinstance(local, dict) and local.get("status") == "grounded"):
        understanding["analysis_status"] = STATUS_FAILED
    understanding["vision_cache_identity"] = _provider_cache_identity(active_provider)
    # Preserve prior raw attempts across explicit retry/reanalysis as well as
    # failures. Registry persistence carries the entire understanding unchanged.
    if isinstance(cached, dict):
        history = copy.deepcopy(cached.get("visual_observer_history") or [])
        previous = cached.get("visual_observer_bridge")
        if previous and previous != understanding.get("visual_observer_bridge"):
            history.append(copy.deepcopy(previous))
        if history:
            understanding["visual_observer_history"] = history
    image_registry.set_analysis(session_id, image_id, understanding,
                                understanding.get("analysis_status"))
    return understanding


def analyze_image(session_id, image_id, force=False):

    return analyze_record(session_id, image_id, force=force)


def analyze_active(session_id, force=False):

    record = image_registry.active(session_id)

    if not record:

        return None

    return analyze_record(session_id, record["image_id"], force=force)



# ==========================================================
# REFERENCE RESOLUTION
# ==========================================================

def resolve_session_reference(session_id, text):

    return resolve_reference(text, session_id, registry=image_registry)


def resolve_session_region(session_id, text, image_id, understanding):

    return resolve_region_reference(
        text,
        target_image_id=image_id,
        understanding=understanding,
    )



# ==========================================================
# GROUNDED ANSWER PROMPT
# ==========================================================

GROUNDING_RULES = (
    "Answer ONLY from the visual evidence listed above. "
    "If something is not in the evidence, say plainly that it cannot be "
    "determined from the image. "
    "Never invent dimensions, measurements or compass orientation. "
    "Never describe floors or geometry that are not visible. "
    "Answer in the same language as the user's question."
)


def build_grounded_prompt(
    user_text,
    understanding,
    reference=None,
    region=None,
    observation=None,
):

    lines = ["IMAGE VISUAL EVIDENCE (descriptive only):"]


    if isinstance(understanding, dict) and understanding.get("observed") is not None:

        lines.append(
            "analysis_status: " + str(understanding.get("analysis_status"))
        )
        lines.append(
            "image_type: " + str(understanding.get("image_type"))
        )
        lines.append(
            "confidence: " + str(understanding.get("confidence"))
        )

        for key, label in (
            ("observed", "observed"),
            ("inferred", "inferred (unverified)"),
            ("architectural_elements", "visible elements"),
            ("text_labels_if_visible", "readable text"),
            ("unresolved", "cannot be determined"),
        ):

            values = understanding.get(key) or []

            if values:

                lines.append(
                    label + ": " + "; ".join(str(v) for v in values)
                )

    else:

        lines.append("analysis_status: UNAVAILABLE")
        lines.append(
            "No image analysis is available, so the image cannot be described."
        )


    # ==================================================
    # R2_USER_FACING_EYE_HANDOFF_V1
    #
    # The observation contract already carries what the model actually saw:
    # the storey reading, the materials it named, and the things it explicitly
    # reported ABSENT. None of that reached this prompt, so a question such as
    # "این ساختمان چند طبقه دارد؟" could only be answered "cannot be
    # determined" while the model had in fact counted the storeys.
    #
    # Every line below states its own provenance. This is an ATTRIBUTED MODEL
    # OBSERVATION, never verified geometry: the verified floor channel stays
    # null and nothing here can be promoted by being printed.
    # ==================================================

    _observation = observation if isinstance(observation, dict) else {}

    _extras = (
        understanding.get("observation_extras") or {}
        if isinstance(understanding, dict)
        else {}
    )

    floors = (
        _observation.get("visible_floors_observation")
        or _extras.get("visible_floors_observation")
    )

    if isinstance(floors, dict) and isinstance(floors.get("count"), int):

        detail = ["storeys visible: " + str(floors["count"])]

        if floors.get("count_scope") == "TOTAL":

            detail.append(
                "a whole-building total that includes the ground floor"
                if floors.get("ground_floor_included")
                else "a whole-building total"
            )

        if isinstance(floors.get("upper_floors"), int):

            detail.append(str(floors["upper_floors"]) + " upper floors")

        if floors.get("roof_band_excluded"):

            detail.append("parapet / roof band NOT counted as a storey")

        if floors.get("whole_building_visible") is False:

            detail.append("building partly out of frame, so this is a minimum")

        lines.append(
            "storey count (MODEL OBSERVATION, unverified, confidence "
            + str(floors.get("confidence") or "LOW").upper()
            + "): " + "; ".join(detail) + "."
        )

        if floors.get("evidence_quote"):

            lines.append(
                "storey evidence quote (verbatim from the observer): "
                + str(floors["evidence_quote"])
            )

    materials = (
        _observation.get("material_observations")
        or _extras.get("material_observations")
        or []
    )

    named = sorted({
        material
        for entry in materials
        if isinstance(entry, dict)
        for material in (entry.get("materials") or [])
    })

    if named:

        lines.append(
            "materials named by the model (unverified): " + ", ".join(named)
        )

    negative = _observation.get("negative_observations") or []

    if negative:

        lines.append(
            "reported ABSENT or NOT VISIBLE (absence evidence — never restate "
            "these as present): "
            + "; ".join(
                str(entry.get("evidence_phrase"))
                for entry in negative
                if isinstance(entry, dict) and entry.get("evidence_phrase")
            )
        )


    if isinstance(reference, dict) and reference.get("status") == "resolved":

        lines.append(
            "referenced image: #"
            + str(reference.get("target_ordinal"))
            + " ("
            + str(reference.get("target_phrase"))
            + ")"
        )

    if isinstance(region, dict) and region.get("candidate_element_type"):

        lines.append(
            "referenced region: " + str(region.get("candidate_element_type"))
        )

        if not region.get("grounded"):

            lines.append(
                "region could not be grounded to image coordinates"
            )


    lines.append("")
    lines.append("RULES: " + GROUNDING_RULES)
    lines.append("")
    lines.append("USER QUESTION:")
    lines.append(str(user_text or ""))

    # Closing instruction AFTER the question: local models otherwise
    # tend to echo the question instead of answering it.
    lines.append("")
    lines.append("NOW ANSWER THE USER QUESTION ABOVE.")
    lines.append(
        "Do not repeat the question. Use only the visual evidence listed above. "
        "Answer in the same language as the user's question."
    )

    return "\n".join(lines)
