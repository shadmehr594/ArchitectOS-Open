# ==========================================================
# ArchitectOS Chat Runtime Gateway v28
# Unified Cognitive + Render Gateway
#
# Responsibilities:
# - Chat Routing
# - Memory Routing
# - Design Routing
# - Image Routing
# - Intent Management
# - Render Pipeline Bridge
#
# Compatible:
# Brain v21.7
# Memory Intelligence Engine v31
# Intent Router v69.4
# RenderRuntime v7.2
# Response Adapter v2
# ==========================================================


from core.memory.memory_manager import memory_manager
from core.memory.context_recall import ContextRecall
from core.memory.context_builder import ContextBuilder
from core.memory.conversation_writeback import create_writeback

import os
import pathlib
import re
import uuid
import threading


from core.llm.llm_gateway import LLMGateway, coder_gateway


from core.prompt_engine import PromptEngine


from core.prompt_intelligence.architectural_intent import (
    ArchitecturalIntent
)
from core.prompt_intelligence.architectural_material_intelligence import (
    ArchitecturalMaterialIntelligence
)
from core.prompt_intelligence.architectural_llm_parser import (
    architectural_llm_parser
)

from core.prompt_intelligence.intent_normalizer import (
    intent_normalizer
)

from core.prompt_intelligence.persian_architectural_understanding import (
    persian_architectural_understanding
)

from core.prompt_intelligence.architectural_prompt_compiler_v1 import (
    architectural_prompt_compiler
)

from core.chat.architectural_conversation_context_v1 import (
    architectural_conversation_context
)

from core.prompt_intelligence.reference_image_architectural_understanding_v1 import (
    reference_image_understanding
)

from core.prompt_intelligence.approved_design_render_contract_v1 import (
    approved_design_render_contract
)

# PHASE 2D-7 — render revision / delta understanding (semantic delta only)
from core.prompt_intelligence.render_revision_delta_v1 import (
    render_revision_delta
)

# RENDER_SEMANTIC_FIDELITY_V1 — Persian request -> English render instruction,
# and the fail-closed gate that verifies the instruction kept every essential
# Persian constraint.  Contract only: no RenderRuntime call, no ComfyUI.
from core.cognition.architectural_render_instruction_v1 import (
    build_constraint_block,
    build_render_instruction,
    requested_floor_count,
)

from core.cognition.render_semantic_fidelity_v1 import (
    validate_render_fidelity
)


from core.intelligence.semantic_intent import (
    SemanticIntentEngine
)


from core.intent_router import intent_router


from core.chat.response_guard import response_guard
# PERSIAN_OUTPUT_ORTHOGRAPHY_V1 — small context-aware response spelling net
from core.chat.persian_output_orthography_v1 import (
    persian_output_orthography,
)
from core.chat.chat_input_adapter import ChatInputAdapter
from core.chat.chat_image_bridge import ChatImageBridge
from core.chat.image_response_adapter import ImageResponseAdapter
# R4_PHOTO_SAFE_CHAT_BRIDGE_V1 — the approved storage roots and the public
# attachment contract. The bridge produces a LOCAL, non-generative output, so
# it must build its attachment through this service instead of pretending to
# be a ComfyUI render.
from core.chat.chat_attachment import chat_attachment_service
from core.render.photometric_warmth_adjustment_v1 import (
    PRESET_WARM_BLUE_RESTRAINED_V1,
    adjust_file_exclusive,
)
from core.chat.conversation_state import conversation_state
from core.chat.response_adapter import (
    PHOTOMETRIC_WARMTH_CONFIRMATION,
    ResponseAdapter,
)
from core.chat.handlers.image_handler import ImageHandler

# CHAT_LANGUAGE_02 — session-keyed state isolation
from core.chat.session_registry_v1 import (
    session_registry,
    DEFAULT_SESSION_KEY,
)

# CHAT_LANGUAGE_02 — deterministic architectural terminology layer
from core.cognition.architectural_terminology_v1 import (
    normalize_architectural_terms,
    augment_compiled_prompt,
    bounded_llm_translate,
)

# TEXT_TO_IMAGE_COMFY_03 — explicit render preset layer
from core.render.render_preset_v1 import (
    resolve_preset as resolve_render_preset,
)

# VISION_IMAGE_REGISTRY_04 — vision + session image registry
from core.vision.image_registry_v1 import image_registry

from core.vision.image_intent_v1 import (
    classify_image_intent,
    detect_unsupported_geometry_edit,
    precise_localized_route_available,
    INTENT_EDIT,
    INTENT_ANALYZE,
    INTENT_REFERENCE,
    INTENT_UPLOAD_ONLY,
    # VISION_OBSERVATION_MODE_SEPARATION_V1 — a request for visible
    # evidence only is answered by the observation layer.
    INTENT_OBSERVE,
)

# IMAGE_TO_IMAGE_05 — deterministic preservation / strength levels
from core.render.image_edit_presets_v1 import (
    resolve_preservation_with_denoise,
    DEFAULT_LEVEL as DEFAULT_PRESERVATION_LEVEL,
)

# IMAGE_TO_IMAGE_05 — authoritative img2img edit delta
from core.prompt_intelligence.image_edit_delta_v1 import (
    compile_edit_delta,
    is_classified as is_classified_edit_delta,
    delta_prompt as edit_delta_prompt,
    conflict_terms as edit_delta_conflict_terms,
    preservation_level as edit_delta_preservation_level,
    denoise_override as edit_delta_denoise_override,
)

from core.vision.reference_resolver_v1 import (
    is_region_reference,
)

# PHASE 08 — conversational turn semantics + teaching foundation.
# ONE assistant: this is a deterministic pre-routing layer INSIDE the
# canonical ChatArchitect. It adds no second LLM, memory, conversation
# history or parallel assistant, and it never renders.
from core.conversation.teaching_foundation_v1 import (
    teaching_foundation,
)

# CONVERSATION_DOMAIN_V1 — chat/voice domain isolation. Classifies the turn
# (architecture | voice_audio | general) and projects the session's
# architectural context so a non-architectural turn never receives it.
# Read-only: it never mutates the session and never deletes anything.
from core.chat.conversation_domain_v1 import (
    resolve_turn_domain,
)

# CONVERSATIONAL_NATURALNESS_V1 — human conversation tone.
# ADDITIVE and tone-only: it (a) reclassifies the CURRENT turn's domain from
# THIS turn's own signal so a stale carried-forward architectural signal cannot
# force an unrelated conversational turn into the architecture domain, and
# (b) supplies the natural-conversation style block for the chat prompt.
# It changes NO routing decision, creates no second assistant, and renders
# nothing.
from core.chat.conversational_naturalness_v1 import (
    reclassify_turn_domain,
    conversation_naturalness_instruction,
)

# CONVERSATION_INTENT_BOUNDARY_V1 — ONE authoritative top-level intent
# decision taken BEFORE any downstream flow (teaching / architecture /
# general). It answers exactly one question: is this turn
# GENERAL_CONVERSATION, ARCHITECTURE_CONVERSATION or TEACHING?
#
# It is deterministic, non-sticky and additive: it never rewrites the
# turn, never stores anything, and it does NOT modify the frozen
# `turn_semantics_v1` classifier or `teaching_foundation_v1`. Its only
# effect here is to prevent a turn that is plainly NOT teaching from
# entering the teaching flow merely because a downstream heuristic
# (session state, a stray imperative, architecture vocabulary) would
# otherwise capture it.
from core.chat.conversation_intent_boundary_v1 import (
    classify_conversation_intent,
    TEACHING as _CIB_TEACHING,
)

# ARCHITECTURAL_LEARNING_RUNTIME_BRIDGE_V1 — the runtime learning path.
# An ADDITIVE orchestration layer over the EXISTING knowledge modules; it
# never extracts, never classifies, never learns automatically and never
# generates design. It renders nothing.
from core.knowledge.architectural_learning_runtime_bridge_v1 import (
    architectural_learning_runtime,
)

from core.vision.image_session_v1 import (
    register_upload as register_session_upload,
    register_asset as register_session_asset,
    analyze_record as analyze_session_image,
    resolve_session_reference,
    resolve_session_region,
    build_grounded_prompt,
)
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)


from core.render.render_runtime import RenderRuntime
from core.render.render_result_bridge import RenderResultBridge
from core.render.prompt_builder import PromptBuilder

from core.intelligence.architectos_design_execution_bridge_v100 import (
    ArchitectOSDesignExecutionBridge
)


# ==========================================================
# MASK_SOURCE_BINDING_V1 — effective source image for a mask
#
# The mask binding check re-hashes the source image this turn will actually
# edit. Resolving it needs the same precedence at every guard call site, so it
# lives here once rather than being re-derived three times:
#
#   1. the image uploaded on THIS request (bytes, not yet stored at the
#      pre-routing guard, so hashed directly);
#   2. the session's ACTIVE registry image — the path the edit layer itself
#      edits, which is what a text-only follow-up must bind to (or be refused).
# ==========================================================

def resolve_guard_source_identity(session_key, image=None, image_record=None):

    import hashlib as _hashlib

    def _digest_path(_path):

        try:

            _h = _hashlib.sha256()

            with open(_path, "rb") as _fh:

                for _chunk in iter(lambda: _fh.read(1024 * 1024), b""):

                    _h.update(_chunk)

            return _h.hexdigest()

        except Exception:

            return None

    # 1. an image arriving on THIS request
    _stream = None

    if hasattr(image, "read") or hasattr(image, "stream"):

        _stream = getattr(image, "stream", image)

    if _stream is not None and hasattr(_stream, "read"):

        try:

            _stream.seek(0)

            _h = _hashlib.sha256()

            while True:

                _chunk = _stream.read(1024 * 1024)

                if not _chunk:

                    break

                _h.update(_chunk)

            _stream.seek(0)

            return {"source_sha256": _h.hexdigest()}

        except Exception:

            pass

    _request_path = None

    if isinstance(image, str):

        _request_path = image

    elif isinstance(image, dict):

        _request_path = image.get("path")

    if _request_path:

        _d = _digest_path(_request_path)

        if _d:

            return {"source_sha256": _d, "source_image_path": _request_path}

    # 2. the session's ACTIVE image
    try:

        from core.vision.image_registry_v1 import image_registry as _images

        _record = image_record

        if not isinstance(_record, dict):

            _record = _images.active(session_key)

        if isinstance(_record, dict) and _record.get("path"):

            _d = _digest_path(_record.get("path"))

            if _d:

                return {
                    "source_sha256": _d,
                    "source_image_path": _record.get("path"),
                    "active_image_id": _record.get("image_id"),
                }

    except Exception:

        pass

    return {}


def guard_context_with_source(context, session_key, image=None, image_record=None):
    """Return a guard context carrying the source identity for mask binding.

    A copy is used so no caller's dict is mutated as a side effect.
    """

    _ctx = dict(context) if isinstance(context, dict) else {}

    # a digest arriving in the caller's context is NOT evidence; it is only
    # re-admitted below after this resolver has hashed the actual source
    _ctx.pop("source_identity_verified", None)

    _identity = resolve_guard_source_identity(
        session_key, image=image, image_record=image_record
    )

    if _identity.get("source_sha256"):

        _ctx["source_sha256"] = _identity["source_sha256"]
        _ctx["source_identity_verified"] = True

        # the guard re-hashes from a path when one is available, so a changed
        # file on disk is detected; the digest alone covers the bytes case
        if _identity.get("source_image_path"):

            _ctx["source_image_path"] = _identity["source_image_path"]

        if _identity.get("active_image_id"):

            _ctx["active_image_id"] = _identity["active_image_id"]

    return _ctx


print(
    "######## USING CHAT ARCHITECT FILE ########"
)
print(
    __file__
) 

# ==========================================================
# PHASE 08 — PER-CALL TURN OBSERVATION CARRIER
#
# Thread-local so concurrent requests can never see each other's
# observation. It carries the deterministic turn-semantics result from
# the Phase 08 hook inside _handle_internal() up to the single public
# handle() wrapper, which attaches it to EVERY response shape.
# ==========================================================

_PHASE08_OBSERVATION = threading.local()

# CONVERSATION_INTENT_BOUNDARY_V1 — carries the audited top-level intent
# decision from `_handle_internal` back to the public `handle()` wrapper
# so every response shape exposes it. Same thread-local pattern as the
# Phase 08 observation above.
_CONVERSATION_INTENT_OBSERVATION = threading.local()


# ARCHITECTURAL REASONING INTEGRATION V8 — one predicate for the evidence gate.
#
# The legacy precise-geometry detector refuses a localized edit before any
# image analysis, and its substring vocabulary also sees ``move`` inside
# English ``remove``. That prevented even "remove wall-mounted lanterns" from
# reaching the V7.4 subject/context evidence.
#
# V8 therefore defers EXACTLY ONE shape to the evidence-aware decision gate:
# a plain, non-dimensioned element removal. Movement, resize, rotation,
# translation and every dimensioned edit keep the historical pre-route
# refusal, and the guard itself is not weakened. ImageHandler still fails
# closed unless the requested subject is evidence-backed and a verified
# caller-supplied mask supplies spatial scope.
#
# The same predicate is applied at every site that can refuse the request, so
# a deferred removal cannot be re-refused by a downstream guard that runs the
# identical detector.
_V8_OTHER_GEOMETRY_OPERATION = re.compile(
    r"\b(?:move|shift|relocate|resize|scale|rotate|translate|"
    r"widen|narrow|extend|enlarge|shrink)\b|"
    r"(?:جابه ?جا|جابجا|منتقل|بچرخ|بزرگ|کوچک|بلندتر|کوتاه|ببر|بکش)"
)

_V8_PLAIN_REMOVAL = re.compile(r"\b(?:remove|delete)\b|(?:حذف|بردار)")


def _v8_plain_evidence_gated_removal(text, guard):
    """True only for a non-localized, non-dimensioned element removal.

    ``localizing_anchor`` is the legacy guard's own statement that the request
    names a specific localized target ("this window", "این پنجره"). That is
    precise-geometry territory: it needs a validated mask and keeps the
    historical refusal. The deferral applies only when the guard explicitly
    reports NO localizing anchor, so any guard shape that does not state it
    remains refused.
    """

    if not isinstance(guard, dict) or guard.get("dimension"):
        return False

    scope = guard.get("scope_evidence") or {}

    if scope.get("localizing_anchor") is not False:
        return False

    normalized = " ".join(
        str(text or "").lower().replace("\u200c", " ").split()
    )

    if not _V8_PLAIN_REMOVAL.search(normalized):
        return False

    remainder = _V8_PLAIN_REMOVAL.sub("", normalized)

    return not _V8_OTHER_GEOMETRY_OPERATION.search(remainder)


def _v8_defer_removal_to_evidence_gate(text, guard, context):
    """Apply the V8 deferral only where the pre-routing gate authorised it.

    ``v8_evidence_gated_removal`` is set by the pre-routing gate after it has
    verified an uploaded image in an explicit image-edit mode. Downstream
    sites consult that marker instead of re-deriving a broader condition, so
    a request the pre-routing gate refused is still refused here.
    """

    if not isinstance(context, dict):
        return False

    if not context.get("v8_evidence_gated_removal"):
        return False

    return _v8_plain_evidence_gated_removal(text, guard)


# R4 ARCHITECTURAL EDIT ADMISSION GUARD V1
#
# This is a narrow admission predicate inside the EXISTING ChatArchitect owner;
# it is not a second router.  WorkflowSelector still owns graph selection after
# admission.  The accepted R3/R4 evidence currently contains NO positive
# whole-image workflow envelope that guarantees the protected architecture for
# a general architectural edit.  Architectural requests therefore fail closed
# here, before ImageHandler, GPU admission, ComfyUI and derived registration.

_R4_ARCHITECTURAL_TERMS = (
    "building", "facade", "façade", "roof", "parapet", "window", "door",
    "entrance", "opening", "passage", "through-passage", "through passage",
    "balcony", "railing", "storey", "story", "floor count", "massing",
    "ساختمان", "بنا", "نما", "سقف", "جان پناه", "پنجره", "در ورودی",
    "ورودی", "بازشو", "گذر", "راه عبور", "بالکن", "نرده", "طبقه", "حجم",
)

_R4_LOCAL_TARGETS = {
    "entrance_door": (
        "entrance door", "entry door", "front door", "در ورودی",
    ),
    "window": ("window", "پنجره"),
    "railing": ("railing", "guardrail", "نرده"),
    "balcony": ("balcony", "بالکن"),
}

#: NEOCLASSICAL_LIVE_EVIDENCE_HANDOFF_V1 — EXCLUSIVE / REGIONAL scope words.
#:
#: These restrict WHERE the change applies. Unlike a deictic subject word
#: ("this building"), they must never be suppressed by a style name, because
#: "design only the left facade section in neoclassical style" is still a
#: section-scoped request. Mirrors the exclusive entries of
#: `image_intent_v1._LOCALIZING_ANCHORS`.
_R4_EXCLUSIVE_SCOPE_MARKERS = (
    "only this", "only the", "just this", "just the",
    "the left", "the right", "left side", "right side", "particular",
    "فقط این", "فقط آن", "سمت چپ", "سمت راست",
)

_R4_PROTECTED_SPATIAL_TARGETS = {
    "through_passage": (
        "through-passage", "through passage", "pass-through", "pass through",
        "گذر سرتاسری", "گذر میانی", "گذر", "راه عبور",
    ),
    "opening": ("opening", "بازشو"),
}

_R4_STRICT_PRESERVATION_PATTERNS = (
    re.compile(r"\bonly\s+(?:change|modify|edit|recolour|recolor|replace)\b", re.I),
    re.compile(r"\bpreserve\s+exactly\b", re.I),
    re.compile(r"\bkeep\b.{0,80}\bunchanged\b", re.I),
    re.compile(r"\bdo\s+not\s+(?:alter|change|modify)\b", re.I),
    re.compile(r"\beverything\s+else\s+unchanged\b", re.I),
    re.compile(r"فقط.{0,80}(?:تغییر|عوض|آبی|سنگ|مدرن|کن|بده)"),
    re.compile(r"هیچ\s+چیز\s+دیگر(?:ی)?\s+تغییر\s+نکن"),
    re.compile(r"(?:ثابت|بدون\s+تغییر)\s+بمان"),
    re.compile(r"دقیق(?:اً|ا).{0,80}حفظ"),
    re.compile(r"بقیه.{0,50}(?:تغییر\s+ن(?:ده|کن)|بدون\s+تغییر)"),
)

_R4_SPATIAL_CHANGE_PATTERNS = (
    re.compile(r"\b(?:close|enclose|block|seal|fill|remove|move|resize)\b", re.I),
    re.compile(r"(?:ببند|بستن|مسدود|پر\s+کن|حذف|جابه\s*جا|تغییر\s+ابعاد)"),
)


#: I2I_CONCEPTUAL_ADMISSION_V1 — a spatial verb inside a PROHIBITION is not a
#: spatial change.
#:
#: MEASURED: "Do not add floors, remove floors, or change the geometry" made
#: the raw pattern scan report `spatial_change: True` on the word "remove",
#: closing the route for a request that forbids exactly that.
#:
#: Two authorities were tried first and both came up short here:
#:   * `negation_scope_v1.is_prohibited()` only understands a TRAILING
#:     prohibition — it returns False and `trailing_prohibition_spans()` is
#:     None for a prohibition that sits mid-message;
#:   * a whole-text pattern scan cannot see that the verb is governed by a
#:     preceding "Do not".
#:
#: So the scan is CLAUSE-scoped, using the shared clause splitter that already
#: merges a negated list. A clause carrying a prohibition contributes no
#: spatial change. An explicit geometry operation is still refused earlier and
#: independently by `detect_unsupported_geometry_edit`, so this remains a
#: second net, not the only one.
_R4_CLAUSE_PROHIBITION_MARKERS = (
    "do not", "don't", "does not", "doesn't", "never", "avoid",
    "must not", "shall not", "without",
    "نکن", "نشه", "نباشد", "بدون",
)


def _r4_clause_is_prohibited(clause):

    low = " " + str(clause or "").lower() + " "

    return any(marker in low for marker in _R4_CLAUSE_PROHIBITION_MARKERS)


def _r4_spatial_change(text):
    """True when a spatial verb occurs in a clause that does not forbid it."""

    from core.prompt_intelligence.geometry_authority_handoff_v1 import (
        split_clauses,
    )

    for clause in split_clauses(str(text or "")):

        if _r4_clause_is_prohibited(clause):

            continue

        normalized = _r4_normalized_text(clause)

        for pattern in _R4_SPATIAL_CHANGE_PATTERNS:

            if pattern.search(normalized):

                return True

    return False


def _r4_normalized_text(text):    return " ".join(str(text or "").lower().replace("\u200c", " ").split())


def _r4_named_targets(text, vocabulary):
    normalized = _r4_normalized_text(text)
    return [
        name
        for name, markers in vocabulary.items()
        if any(marker in normalized for marker in markers)
    ]


def _r4_strict_preservation_requested(text, edit_delta):
    clauses = (
        edit_delta.get("explicit_preservation_clauses")
        if isinstance(edit_delta, dict)
        else None
    ) or []
    if clauses:
        return True

    normalized = _r4_normalized_text(text)
    return any(pattern.search(normalized) for pattern in _R4_STRICT_PRESERVATION_PATTERNS)


def _r4_architectural_scope(text, prior_intent, image_understanding):
    """True only when current text or trusted source context is architectural."""

    normalized = _r4_normalized_text(text)
    if any(term in normalized for term in _R4_ARCHITECTURAL_TERMS):
        return True

    if isinstance(prior_intent, dict) and any(
        prior_intent.get(key) not in (None, "", [], {})
        for key in (
            "building_type", "floors", "floor_count", "roof", "roof_geometry",
            "massing", "windows", "doors", "openings", "balconies", "facade",
        )
    ):
        return True

    if isinstance(image_understanding, dict):
        image_type = str(image_understanding.get("image_type") or "").lower()
        if any(term in image_type for term in ("architect", "building", "facade")):
            return True

    return False


def _r4_source_authority(image_record):
    """Verify the selected record against the current session registry."""

    current = session_registry.current() or {}
    session_id = current.get("session_id")
    if not session_id or not isinstance(image_record, dict):
        return {"valid": False, "reason": "source_image_authority_mismatch"}

    image_id = image_record.get("image_id")
    path = image_record.get("path")
    if not image_id or not path or str(image_record.get("session_id")) != str(session_id):
        return {"valid": False, "reason": "source_image_authority_mismatch"}

    registered = image_registry.get(session_id, image_id)
    if not isinstance(registered, dict) or not registered.get("path"):
        return {"valid": False, "reason": "source_image_authority_mismatch"}

    try:
        selected_path = os.path.normcase(os.path.realpath(str(path)))
        registered_path = os.path.normcase(os.path.realpath(str(registered["path"])))
    except Exception:
        return {"valid": False, "reason": "source_image_authority_mismatch"}

    if selected_path != registered_path or not os.path.isfile(registered_path):
        return {"valid": False, "reason": "source_image_authority_mismatch"}

    return {
        "valid": True,
        "session_id": str(session_id),
        "project_id": current.get("project_id"),
        "image_id": image_id,
        "path": registered_path,
        "source_type": registered.get("source_type"),
        "parent_image_id": registered.get("parent_image_id"),
    }


def _r4_blocked_edit_result(reason, admission):
    """Existing-compatible render_blocked envelope with Persian UI text."""

    if reason == "source_image_authority_mismatch":
        message = (
            "تصویر انتخاب‌شده به نشست و پروژهٔ فعال تعلق ندارد؛ بنابراین "
            "هیچ رندری اجرا نشد و تصویر فعال تغییر نکرد."
        )
        missing = "authoritative_source_image"
    elif reason == "source_image_role_conflict":
        message = (
            "تصویر انتخاب‌شده نقش «مرجع سبک» دارد، نه بنای هدف؛ بنابراین "
            "هیچ رندری اجرا نشد و هندسهٔ ساختمان از تصویر مرجع گرفته نشد."
        )
        missing = "authoritative_target_building"
    elif reason == "source_image_integrity_failed":
        message = (
            "فایل تصویر انتخاب‌شده قابل اعتماد نیست: هش محتوا، ابعاد یا "
            "محتوای دیداری آن تأیید نشد؛ بنابراین هیچ رندری اجرا نشد."
        )
        missing = "verified_source_image_content"
    else:
        message = (
            "درخواست تغییر را متوجه شدم، اما مسیر فعلی نمی‌تواند حفظ دقیق "
            "سایر اجزای ساختمان را تضمین کند؛ بنابراین رندر اجرا نشد."
        )
        missing = "validated_architectural_preservation_workflow"

    return {
        "type": "render_blocked",
        "engine": "chat_architect",
        "status": "blocked",
        "reason": reason,
        "message": message,
        "result": message,
        "capability_gap": {
            "missing": missing,
            "detail": (
                "Neither installed whole-image edit workflow has accepted "
                "visual evidence for the requested architectural preservation "
                "level. Prompt wording and CPU graph selection are not proof."
            ),
        },
        "admission": admission,
    }


# ==========================================================
# FACADE_RENDERING_FIRST_I2I_ADMISSION_V1
# CONTROLLED ARCHITECTURAL PRESERVATION ADMISSION
#
# The R4 gate above refuses every architectural edit because no accepted
# visual envelope existed.  That refusal stays the DEFAULT.  This block adds
# the one bounded path that may eventually open it:
#
#   * a SERVER-SIDE acceptance record must exist for exactly one workflow
#     (`flux_kontext_edit.json`), for exactly the checkpoint that workflow
#     actually loads, and it must be status `accepted`;
#   * the selected source must be the registered original for this session,
#     with a verified content hash, native dimensions, decodable pixels and
#     non-degenerate content;
#   * a style-reference asset may never become the target building;
#   * the request must be a MASKLESS, CLASSIFIED facade restyle, i.e. the one
#     that resolves to the Kontext instruction-edit graph;
#   * an explicit preservation contract must be assembled and carried.
#
# Nothing here is a request flag.  A chat payload cannot create the record,
# cannot name the workflow, and cannot set `accepted`.  With no record the
# code path is byte-identical to the pre-existing refusal.
#
# A constructed contract is an INSTRUCTION CONSTRAINT.  It is not evidence
# that the model preserves geometry, and this module never claims that.
# ==========================================================

_R4_ACCEPTANCE_CONTRACT = "ArchitecturalPreservationAcceptanceV1"
_R4_ACCEPTANCE_VERSION = "1.0"

_R4_PRESERVATION_CONTRACT = "ArchitecturalPreservationContractV1"
_R4_PRESERVATION_CONTRACT_VERSION = "1.0"

#: The single workflow this milestone may admit.  The reference-guided and
#: dual-image graphs are NOT admitted here.
_R4_ACCEPTED_WORKFLOW = "flux_kontext_edit.json"

#: Edit classes the accepted capability covers: a facade RESTYLE.  A
#: time-of-day or lighting change has its own acceptance step and is not
#: admitted under a facade-preservation record.
_R4_ADMITTED_EDIT_CLASSES = ("style_change", "material_change")

# ==========================================================
# I2I_CONCEPTUAL_ADMISSION_V1 — EXPLICITLY CONSENTED CONCEPTUAL EDIT
#
# PRODUCT DECISION (2026-11-03): a user may explicitly opt in, per request, to
# a CONCEPTUAL architectural appearance edit. In that mode they accept that the
# existing image-to-image graph may drift geometry, openings, storeys and
# details. This is NOT an exact-preservation claim and it does NOT create or
# imply an acceptance record.
#
# The consent is a REQUEST CONTRACT field (`conceptual_edit`, read in app.py
# from header / JSON / form), never inferred from wording: "modern",
# "travertine", "facade" or a "Preserve exactly" sentence can never enable it.
# The default path stays exactly as it was — refusal.
# ==========================================================

#: The graph a consented conceptual appearance edit is admitted on. It is the
#: existing maskless whole-image graph; its preservation capability remains
#: UNVERIFIED and is never represented otherwise.
_R4_CONCEPTUAL_WORKFLOW = "flux_img2img.json"

_R4_CONCEPTUAL_REASON = "conceptual_appearance_edit_consented"

#: Reported on the admission and carried into the Chat result. There is
#: deliberately NO `preservation_contract`: nothing about preservation is
#: asserted for this route.
_R4_CONCEPTUAL_PRESERVATION_STATUS = "conceptual_unverified"


def _r4_conceptual_consent(context):
    """True only for an EXPLICIT, per-request conceptual consent.

    Strict identity, not truthiness: `app.py` normalises the request field to a
    real bool, so a client string can never reach here as consent. Any other
    value — missing, None, a string, a dict — fails closed to the refusal.
    """

    return bool(
        isinstance(context, dict)
        and context.get("conceptual_edit") is True
    )


# ==========================================================
# FACADE_REDESIGN_GEOMETRY_APPEARANCE_CONTRACT_V1
#
# THE ARCHITECTURAL RULE
#   Preserve building geometry and opening geometry.
#   Redesign everything else.
#
# THE DEFECT THIS CORRECTS
# The preservation contract named ELEMENTS, not PROPERTIES:
#
#   "the existing balconies and railings and their positions"
#   "the existing entrance location and design"
#   "every building element the user did not explicitly ask to change"
#
# An instruction that says "preserve railings" is read by the edit model as
# "keep the railing pixels", and the same for window frames and door leaves.
# Measured consequence on the four-storey acceptance case: the request asked
# for classical railings, stone window surrounds and a new entrance, and the
# contract simultaneously required the existing railing design, window frames
# and door design to survive. The model cannot satisfy both, so it satisfied
# the preservation half — which is the half stated as a constraint.
#
# Geometry and appearance are different domains. Only geometry is preserved by
# default; appearance is editable by default and is narrowed only when the
# user explicitly narrows it.
# ==========================================================

#: Appearance domains and the scope each one permits. Keys are stable; the
#: scope text is what reaches the instruction.
_APPEARANCE_DOMAIN_SCOPE = {
    "facade_material": (
        "cladding material, colour, texture and surface articulation of the "
        "existing wall planes"
    ),
    "architectural_style": (
        "architectural language, composition and ornamentation of the facade"
    ),
    "window_frame_appearance": (
        "frame design, material, colour, mullion and transom pattern, and "
        "applied stone surrounds around the existing opening"
    ),
    "door_appearance": (
        "door leaf design, material, colour, glazing and applied entrance "
        "surround within the existing opening"
    ),
    "railing_appearance": (
        "railing or balustrade design, material, colour and pattern within "
        "the existing balcony outline"
    ),
    "balcony_surface_finish": (
        "balcony front cladding, finish and applied mouldings"
    ),
    "applied_ornament": (
        "cornices, mouldings, pilaster-like relief and shallow applied "
        "decorative elements on the existing wall planes, including applied "
        "arch motifs that leave the opening unchanged"
    ),
}

#: Every appearance domain is editable unless the user narrows it.
_APPEARANCE_DEFAULT_DOMAINS = (
    "facade_material",
    "architectural_style",
    "window_frame_appearance",
    "door_appearance",
    "railing_appearance",
    "balcony_surface_finish",
    "applied_ornament",
)

#: Edit classes that ask for a surface change only. When one of these is the
#: request's class AND the wording carries no style language, the appearance
#: freedom narrows to the material — a material-only request must not silently
#: authorise a full facade redesign.
_APPEARANCE_SURFACE_ONLY_CLASSES = (
    "material_change", "finish_change", "texture_change", "color_change",
)

#: Wording that establishes a REDESIGN rather than a re-material.
_STYLE_LANGUAGE = (
    "style", "neoclassical", "neo-classical", "classical", "modern",
    "traditional", "iranian", "islamic", "redesign", "restyle", "re-style",
    "architectural language", "ornament", "cornice", "pilaster", "moulding",
    "molding", "relief", "surround", "balustrade", "pediment",
)

#: A preserve statement must contain one of these to count at all.
_APPEARANCE_PRESERVE_MARKERS = (
    "keep", "keeps", "preserve", "preserves", "maintain", "maintains",
    "retain", "retains", "leave", "leaves", "unchanged", "as is", "as-is",
    "as they are", "as it is", "exactly as", "do not change", "do not alter",
    "do not modify", "do not touch", "without changing", "without altering",
    "no change to", "no changes to",
    "حفظ", "ثابت بمان", "تغییر نکن", "دست نزن", "بدون تغییر",
)

#: Element tokens that identify an appearance domain inside a preserve clause.
_APPEARANCE_ELEMENT_TOKENS = {
    "railing_appearance": (
        "railing", "railings", "balustrade", "balustrades", "handrail",
        "guardrail", "banister", "نرده",
    ),
    "window_frame_appearance": (
        "window frame", "window frames", "frame design", "frames",
        "چارچوب پنجره", "چارچوب",
    ),
    "door_appearance": (
        "door", "doors", "door leaf", "door leaves", "entrance design",
        "در", "درِ", "درب",
    ),
    "balcony_surface_finish": (
        "balcony finish", "balcony front", "balcony finishes", "بالکن",
    ),
    "facade_material": (
        "brick", "cladding", "material", "materials", "مصالح", "متریال",
    ),
}

#: A preserve clause that contains any of these is a GEOMETRY statement, not
#: an appearance statement — "positions and dimensions of windows and doors"
#: preserves the opening, not the frame. This is what stops the correct
#: geometry entries from being misread as appearance freezes.
_GEOMETRY_QUALIFIERS = (
    "position", "positions", "dimension", "dimensions", "size", "sizes",
    "location", "locations", "layout", "spacing", "count", "number",
    "geometry", "geometric", "structure", "structural", "slab", "slabs",
    "projection", "projections", "height", "width", "depth", "proportion",
    "proportions", "storey", "storeys", "floor", "floors", "massing",
    "silhouette", "envelope", "footprint", "placement", "arrangement",
)

#: Contrastive conjunctions split a clause; "and" deliberately does not, so a
#: preserve verb still governs every element listed after it.
_APPEARANCE_CLAUSE_SPLIT = re.compile(
    r"[.;!?،؛]|\bbut\b|\bhowever\b|\bwhereas\b|\bwhile\b|\bwhilst\b",
    re.IGNORECASE,
)

_R4_WORKFLOW_DIR = os.path.join("core", "render", "workflows")

#: Server-side capability record directory, relative to the project root.
#: A test redirects it; production reads it from disk and cannot be written
#: by a chat turn.
_R4_ACCEPTANCE_ROOT = os.path.join("data", "render_acceptance")

#: A source frame must carry real content.  These bounds reject the
#: near-black / flat placeholder that a misrouted mask or an empty asset
#: produces; they do not measure architectural quality.
_R4_SOURCE_MIN_MEAN_LUMA = 8.0
_R4_SOURCE_MAX_MEAN_LUMA = 247.0
_R4_SOURCE_MIN_STDDEV = 4.0


def _r4_project_root():
    """Project root from this file's location (core/chat/<this file>)."""

    return os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )


def _r4_workflow_path(workflow):
    return os.path.join(
        _r4_project_root(), _R4_WORKFLOW_DIR, str(workflow)
    )


def _r4_workflow_unet_name(workflow):
    """The checkpoint the named workflow ACTUALLY loads, or None."""

    try:

        import json as _json

        with open(_r4_workflow_path(workflow), "r", encoding="utf-8") as handle:

            graph = _json.load(handle)

    except (OSError, ValueError):

        return None

    if not isinstance(graph, dict):

        return None

    for node in graph.values():

        if not isinstance(node, dict):

            continue

        if "unetloader" not in str(node.get("class_type", "")).lower():

            continue

        name = (node.get("inputs") or {}).get("unet_name")

        if name:

            return str(name)

    return None


def _r4_acceptance_record(workflow=_R4_ACCEPTED_WORKFLOW):
    """Read the server-side preservation-capability record for one workflow.

    Fails closed on every malformed, missing, pending or mismatched field.
    """

    result = {
        "accepted": False,
        "reason": "no_acceptance_record",
        "workflow": str(workflow),
        "path": None,
        "scope": None,
        "model": None,
        "record": None,
    }

    path = os.path.join(
        _r4_project_root(),
        _R4_ACCEPTANCE_ROOT,
        str(workflow),
    )

    result["path"] = path

    if not os.path.isfile(path):

        return result

    try:

        import json as _json

        with open(path, "r", encoding="utf-8") as handle:

            record = _json.load(handle)

    except (OSError, ValueError):

        result["reason"] = "acceptance_record_unreadable"

        return result

    if not isinstance(record, dict):

        result["reason"] = "acceptance_record_unreadable"

        return result

    if str(record.get("contract") or "") != _R4_ACCEPTANCE_CONTRACT:

        result["reason"] = "acceptance_contract_mismatch"

        return result

    if str(record.get("version") or "") != _R4_ACCEPTANCE_VERSION:

        result["reason"] = "acceptance_version_mismatch"

        return result

    if str(record.get("workflow") or "") != str(workflow):

        result["reason"] = "acceptance_workflow_mismatch"

        return result

    if str(record.get("status") or "") != "accepted":

        result["reason"] = "acceptance_not_accepted"

        return result

    scope = str(record.get("accepted_scope") or "")

    if scope not in ("capability", "single_source"):

        result["reason"] = "acceptance_scope_unknown"

        return result

    if scope == "single_source":

        bound = str(record.get("source_sha256") or "")

        if len(bound) != 64:

            result["reason"] = "acceptance_source_binding_missing"

            return result

    # The record must name the checkpoint the workflow really loads.  An
    # acceptance measured on one model cannot silently authorise another.
    expected = _r4_workflow_unet_name(workflow)
    declared = ((record.get("model") or {}).get("unet_name"))

    if not expected or not declared or str(declared) != str(expected):

        result["reason"] = "acceptance_model_mismatch"

        return result

    result.update({
        "accepted": True,
        "reason": "accepted",
        "scope": scope,
        "model": expected,
        "record": record,
    })

    return result


def _r4_path_key(path):
    """Canonical comparison key for a file path, or None."""

    if not path:

        return None

    try:

        return os.path.normcase(os.path.realpath(str(path)))

    except (OSError, ValueError):

        return None


def _r4_source_integrity(source):
    """Verify the ACTUAL bytes of the source, not just its registration.

    Establishes identity (hash), shape (native dimensions), decodability and
    that the frame is not a near-black or flat placeholder.  None of these
    proves architectural correctness.
    """

    result = {
        "verified": False,
        "reason": "source_unreadable",
        "sha256": None,
        "dimensions": None,
        "mean_luma": None,
        "luma_stddev": None,
    }

    path = source.get("path") if isinstance(source, dict) else None

    if not path or not os.path.isfile(str(path)):

        return result

    try:

        import hashlib as _hashlib

        digest = _hashlib.sha256()

        with open(str(path), "rb") as handle:

            for block in iter(lambda: handle.read(1024 * 1024), b""):

                digest.update(block)

        result["sha256"] = digest.hexdigest()

        from PIL import Image as _PILImage
        from PIL import ImageStat as _PILImageStat

        with _PILImage.open(str(path)) as opened:

            opened.load()

            width, height = opened.size

            luminance = _PILImageStat.Stat(opened.convert("L"))

            mean = float(luminance.mean[0])
            spread = float(luminance.stddev[0])

    except Exception:

        result["reason"] = "source_unreadable"

        return result

    result["dimensions"] = [int(width), int(height)]
    result["mean_luma"] = round(mean, 2)
    result["luma_stddev"] = round(spread, 2)

    if width <= 0 or height <= 0:

        result["reason"] = "source_dimensions_invalid"

        return result

    if not (_R4_SOURCE_MIN_MEAN_LUMA <= mean <= _R4_SOURCE_MAX_MEAN_LUMA):

        result["reason"] = "source_luminance_out_of_range"

        return result

    if spread < _R4_SOURCE_MIN_STDDEV:

        result["reason"] = "source_content_flat"

        return result

    result["verified"] = True
    result["reason"] = "verified"

    return result


def _r4_role_conflict(source, context):
    """True when the selected image is a style reference, or not the target.

    `context["references"]` is the FACADE-02/03 transport contract: key "A"
    is appearance-only, key "B" is the geometry authority.  A reference
    asset must never silently become the building that is edited.
    """

    if not isinstance(context, dict):

        return None

    references = context.get("references")

    if not isinstance(references, dict):

        return None

    target_key = _r4_path_key(
        source.get("path") if isinstance(source, dict) else None
    )

    if not target_key:

        return None

    declared_targets = []

    for key, entry in references.items():

        if not isinstance(entry, dict):

            continue

        role = str(entry.get("role") or "")

        entry_key = _r4_path_key(
            entry.get("path") or entry.get("filename")
        )

        if not entry_key:

            continue

        if role == "style_reference" and entry_key == target_key:

            return {"role": role, "reference_key": key}

        if role == "target_building":

            declared_targets.append((key, entry_key))

    # A declared target that is NOT this source is the same confusion seen
    # from the other side: the request names a different building.
    if declared_targets and not any(
        entry_key == target_key for _key, entry_key in declared_targets
    ):

        return {
            "role": "target_building",
            "reference_key": declared_targets[0][0],
        }

    return None


def _r4_resolved_workflow():
    """The graph the EXISTING selector picks for an admitted restyle."""

    try:

        from core.render.workflow_selector import WorkflowSelector

        return WorkflowSelector().select(
            {"engine": "flux", "kontext_edit": True}
        )

    except Exception:

        return None


def _r4_appearance_freedom(text, edit_class):
    """Resolve which appearance domains the request is free to redesign.

    Bounded and conservative:

    * every appearance domain is editable by default, because a facade
      redesign that may not redesign the facade is not a facade redesign;
    * a surface-only edit class with no style language narrows the freedom to
      the material — a re-material request never authorises a restyle;
    * an explicit user preserve statement about an element's APPEARANCE moves
      that domain to `appearance_preserved` and out of the editable set;
    * a preserve statement that names geometry ("positions and dimensions of
      windows and doors") is a geometry constraint and does not narrow
      appearance. The two must not be confused in either direction.

    Geometry is never granted here. This function returns appearance only.
    """

    normalized = " ".join(str(text or "").lower().replace("\u200c", " ").split())

    editable = list(_APPEARANCE_DEFAULT_DOMAINS)

    basis = "default_redesign_freedom"

    surface_only = (
        str(edit_class or "") in _APPEARANCE_SURFACE_ONLY_CLASSES
        and not any(token in normalized for token in _STYLE_LANGUAGE)
    )

    if surface_only:

        editable = ["facade_material"]

        basis = "surface_only_edit_class"

    preserved = []

    for clause in _APPEARANCE_CLAUSE_SPLIT.split(normalized):

        if not clause.strip():

            continue

        if not any(marker in clause for marker in _APPEARANCE_PRESERVE_MARKERS):

            continue

        # A preserve clause about geometry is not an appearance constraint.
        if any(qualifier in clause for qualifier in _GEOMETRY_QUALIFIERS):

            continue

        for domain, tokens in _APPEARANCE_ELEMENT_TOKENS.items():

            if not any(token in clause for token in tokens):

                continue

            if domain in editable:

                editable.remove(domain)

            if domain not in preserved:

                preserved.append(domain)

    if preserved and basis == "default_redesign_freedom":

        basis = "default_redesign_freedom_with_explicit_user_preservation"

    return {
        "appearance_editable": [
            {
                "domain": domain,
                "editable": True,
                "scope": _APPEARANCE_DOMAIN_SCOPE[domain],
            }
            for domain in editable
        ],
        "appearance_preserved": [
            {
                "domain": domain,
                "reason": "explicit_user_preservation_statement",
            }
            for domain in preserved
        ],
        "appearance_basis": basis,
    }


def _r4_preservation_contract(
    text,
    source,
    integrity,
    edit_delta,
    image_understanding,
    acceptance,
    workflow,
):
    """Assemble the explicit architectural preservation contract.

    Every entry is building-agnostic and observable-only.  No dimension,
    storey count or element is invented: geometry the source does not
    establish is preserved as-is and never specified.

    The `preserve` list states GEOMETRIC PROPERTIES only. The appearance the
    same elements happen to have today is not a preservation target — see
    `_r4_appearance_freedom`, which states what the request is free to
    redesign. Naming an element here ("railings", "window frames") froze its
    appearance and contradicted every facade-redesign request.
    """

    edit_class = (
        edit_delta.get("edit_class")
        if isinstance(edit_delta, dict)
        else None
    )

    evidence_state = "none"

    if isinstance(image_understanding, dict) and image_understanding:

        evidence_state = "observation_only"

    contract = {
        "contract": _R4_PRESERVATION_CONTRACT,
        "version": _R4_PRESERVATION_CONTRACT_VERSION,
        "workflow": str(workflow),
        "edit_class": edit_class,
        "requested_change": " ".join(str(text or "").split()),
        "source": {
            "image_id": source.get("image_id"),
            "session_id": source.get("session_id"),
            "path": source.get("path"),
            "source_type": source.get("source_type"),
            "sha256": integrity.get("sha256"),
            "dimensions": integrity.get("dimensions"),
            "mean_luma": integrity.get("mean_luma"),
            "luma_stddev": integrity.get("luma_stddev"),
            "verified": bool(integrity.get("verified")),
        },
        "acceptance": {
            "contract": _R4_ACCEPTANCE_CONTRACT,
            "version": _R4_ACCEPTANCE_VERSION,
            "scope": acceptance.get("scope"),
            "model": acceptance.get("model"),
            "path": acceptance.get("path"),
        },
        "preserve": [
            "the existing building massing and overall silhouette",
            "the visible floor arrangement and storey count as shown in the "
            "source image",
            "the positions and dimensions of the existing window openings",
            "the positions and dimensions of the existing door openings",
            "the existing roofline, roof shape and parapet",
            "the existing balcony positions and their structural projection "
            "geometry",
            "the existing entrance opening location and dimensions",
            "the existing wall planes and structural layout",
            "the camera position, framing, perspective and composition",
        ],
        "prohibit": [
            "do not redesign, re-mass or re-proportion the building",
            "do not add, remove, resize or relocate any window, door or "
            "opening",
            "do not change the storey count",
            "do not invent new volumes, structural members or openings that "
            "are not visible in the source image",
            "do not state or infer precise dimensions that the source evidence "
            "does not establish",
            "do not change the camera position or the composition",
        ],
        "unknown_geometry_policy": (
            "geometry the source does not establish is preserved as-is and is "
            "never specified as a measured dimension"
        ),
        "evidence_state": evidence_state,
    }

    contract.update(_r4_appearance_freedom(text, edit_class))

    return contract


def _r4_contract_prompt_block(contract):
    """Render the contract as instruction text for the edit model."""

    if not isinstance(contract, dict):

        return ""

    requested = " ".join(str(contract.get("requested_change") or "").split())

    preserve = "\n".join(
        "- " + str(item) for item in (contract.get("preserve") or ())
    )

    prohibit = "\n".join(
        "- " + str(item) for item in (contract.get("prohibit") or ())
    )

    lines = []

    if requested:

        lines.append(
            "USER REQUEST (verbatim, authoritative): " + requested
        )

    lines.append(
        "ARCHITECTURAL PRESERVATION CONTRACT ("
        + str(contract.get("contract"))
        + "):"
    )

    if preserve:

        lines.append("PRESERVE EXACTLY:\n" + preserve)

    if prohibit:

        lines.append("DO NOT:\n" + prohibit)

    # ----------------------------------------------
    # FACADE_REDESIGN_GEOMETRY_APPEARANCE_CONTRACT_V1
    #
    # The preservation block above constrains GEOMETRY. Without this section
    # the instruction has no way to say that the appearance of those same
    # elements is the thing being redesigned, and a model reading only
    # "PRESERVE EXACTLY" satisfies the constraint by leaving the facade as
    # photographed.
    # ----------------------------------------------

    appearance_editable = [
        entry for entry in (contract.get("appearance_editable") or ())
        if isinstance(entry, dict) and entry.get("editable")
    ]

    appearance_preserved = [
        entry for entry in (contract.get("appearance_preserved") or ())
        if isinstance(entry, dict)
    ]

    if appearance_editable:

        lines.append(
            "APPEARANCE — EDITABLE BY DEFAULT (these are not geometry "
            "changes; the geometry above is unaffected):\n"
            + "\n".join(
                "- " + str(entry.get("domain")).replace("_", " ")
                + ": " + str(entry.get("scope") or "")
                for entry in appearance_editable
            )
            + "\nRedesigning these visible elements is what the request asks "
            "for. Do not leave the original facade appearance in place to "
            "satisfy the geometry constraints above."
        )

    if appearance_preserved:

        lines.append(
            "APPEARANCE EXPLICITLY PRESERVED BY THE USER (overrides the "
            "default above):\n"
            + "\n".join(
                "- " + str(entry.get("domain")).replace("_", " ")
                for entry in appearance_preserved
            )
        )

    policy = str(contract.get("unknown_geometry_policy") or "").strip()

    if policy:

        lines.append("UNKNOWN GEOMETRY: " + policy)

    return "\n\n".join(lines)


def _r4_compose_admitted_edit_prompt(text, contract, compiled_prompt):
    """Prepend the user's request and the contract to the compiled delta.

    The user's own instruction is stated FIRST and verbatim, so a canonical
    delta clause can never replace it.
    """

    raw_request = " ".join(str(text or "").split())

    block = _r4_contract_prompt_block(contract)

    base = " ".join(str(compiled_prompt or "").split())

    if not base:

        base = (
            "DELTA: restyle the facade of this existing building exactly as "
            "the user request states, changing only the facade appearance"
        )

    parts = []

    # LIVE_CHAT_PAYLOAD_CONTRACT_V1 — conceptual admission intentionally does
    # not claim an exact-preservation contract, but that must never mean the
    # accepted user's design instruction disappears.  Carry it independently
    # of `contract`, first and verbatim, as this helper's contract promises.
    if raw_request and raw_request not in block:

        parts.append("USER REQUEST (verbatim, authoritative): " + raw_request)

    if block:

        parts.append(block)

    parts.append(base)

    return "\n\n".join(parts)


# ==========================================================
# REFERENCE_STYLE_PRODUCT_INTEGRATION_V1
# DERIVED REFERENCE-TRANSFER POLICY
#
# `resolve_conditioning()` refuses to activate USO style conditioning unless
# `reference_policy.role` is `style_only` or `material_only`. That policy was
# produced only by the LLM understanding layer, so a plainly-worded request
# ("redesign my building using the architectural style of this reference")
# fell through to `no_transfer_role_requested` and the selector returned
# `flux_img2img_dual.json` — the graph whose CLIPVisionEncode output is
# consumed by nothing.
#
# This derivation is bounded and conservative:
#   * it needs a VERIFIED pair (both roles present);
#   * it needs a transfer VERB, a transfer SUBJECT and a REFERENCE POINTER in
#     the same utterance;
#   * a comparison request never derives a policy.
# When any part is missing it returns None and the previous behaviour stands.
# ==========================================================

_TRANSFER_VERBS = (
    "redesign", "restyle", "reclad", "re-clad", "resurface", "transfer",
    "apply", "borrow", "adopt", "imitate", "emulate", "match", "take",
    "use", "copy", "inspired", "inspired by", "based on",
)

_TRANSFER_SUBJECTS = (
    "style", "styles", "material", "materials", "appearance", "finish",
    "finishes", "cladding", "language", "look", "aesthetic", "palette",
    "surface", "surfaces", "decorative",
)

_TRANSFER_POINTERS = (
    "reference", "referenced", "this image", "that image", "the image",
    "image b", "image a", "the photo", "photograph", "supplied", "provided",
    "attached", "the facade in", "inspired by", "based on",
)

_COMPARISON_MARKERS = (
    "compare", "comparison", "difference between", "versus", " vs ",
    "which one", "what is the difference",
)


def _reference_transfer_policy(text, roles):
    """Derive a bounded style-transfer policy, or None.

    Returns `{"role": "style_only"|"material_only", ...}` only when the turn
    clearly asks for appearance/material transfer FROM a reference TO a
    building AND both roles are verified.
    """

    if not isinstance(roles, dict):

        return None

    keys = {str(key).upper() for key in roles}

    if not {"A", "B"}.issubset(keys):

        return None

    normalized = " ".join(str(text or "").lower().replace("\u200c", " ").split())

    if not normalized:

        return None

    if any(marker in normalized for marker in _COMPARISON_MARKERS):

        return None

    verbs = [word for word in _TRANSFER_VERBS if word in normalized]
    subjects = [word for word in _TRANSFER_SUBJECTS if word in normalized]
    pointers = [word for word in _TRANSFER_POINTERS if word in normalized]

    if not (verbs and subjects and pointers):

        return None

    # A request that only names materials is a material transfer; anything
    # that also names style/appearance/language is a style transfer.
    material_only = (
        all(
            word in ("material", "materials", "cladding", "finish", "finishes")
            for word in subjects
        )
        and not any(
            word in normalized for word in ("style", "appearance", "language", "look")
        )
    )

    return {
        "contract": "ReferenceTransferPolicyV1",
        "version": "1.0",
        "role": "material_only" if material_only else "style_only",
        "source": "derived_from_request",
        "evidence": {
            "verbs": verbs,
            "subjects": subjects,
            "pointers": pointers,
        },
    }


# ==========================================================
# REFERENCE_STYLE_PRODUCT_INTEGRATION_V1
# R4 ADMISSION FOR THE DUAL-IMAGE ROUTE
#
# The single-image admission is bound to ONE accepted workflow. A record for
# `flux_kontext_edit.json` must never authorise a conditioned dual-image
# render: different graph, different checkpoint, different geometric
# behaviour. This admission is therefore keyed by the workflow the selector
# actually chose, and it is CLOSED by default.
# ==========================================================

def _r4_dual_image_admission(text, references, context, workflow):
    """Workflow-specific architectural admission for the two-image route."""

    references = references if isinstance(references, dict) else {}

    style_entry = references.get("A") or {}
    target_entry = references.get("B") or {}

    target_path = target_entry.get("path")

    current = session_registry.current() or {}

    source = {
        "valid": bool(target_entry.get("present") and target_path),
        "session_id": current.get("session_id"),
        "project_id": current.get("project_id"),
        "image_id": target_entry.get("asset_id"),
        "path": target_path,
        "source_type": "uploaded",
    }

    admission = {
        "contract": "ArchitecturalEditAdmissionV1",
        "version": "1.0",
        "route": "dual_image_conditioned",
        "admitted": False,
        "reason": "preservation_capability_unverified",
        "architectural_scope": True,
        "selected_workflow": None,
        "evaluated_workflow": workflow,
        "source": source,
        "roles": {
            "style_reference": style_entry.get("path"),
            "target_building": target_path,
        },
        "acceptance": None,
        "rejected_workflows": {
            str(workflow): "preservation_capability_unverified",
        },
        "human_learning_authority": "not_used_for_visual_capability",
    }

    def _blocked(reason):

        admission["reason"] = reason
        admission["rejected_workflows"] = {str(workflow): reason}

        return {"admitted": False, "reason": reason, "admission": admission}

    if not workflow:

        return _blocked("preservation_capability_unverified")

    acceptance = _r4_acceptance_record(str(workflow))

    admission["acceptance"] = {
        "accepted": bool(acceptance.get("accepted")),
        "reason": acceptance.get("reason"),
        "workflow": acceptance.get("workflow"),
        "scope": acceptance.get("scope"),
        "model": acceptance.get("model"),
        "path": acceptance.get("path"),
    }

    # 1. CLOSED BY DEFAULT — and a record for a different workflow can never
    #    be found here, because the record path and its `workflow` field are
    #    both keyed by this workflow.
    if not acceptance.get("accepted"):

        return _blocked("preservation_capability_unverified")

    # 2. Role isolation: the style reference must not be the building.
    style_path = style_entry.get("path")

    if not target_path:

        return _blocked("source_image_authority_mismatch")

    target_key = _r4_path_key(target_path)
    style_key = _r4_path_key(style_path)

    if style_key and target_key and style_key == target_key:

        admission["role_conflict"] = {"role": "style_reference"}

        return _blocked("source_image_role_conflict")

    # 3. The selected building must be the session's registered image.
    registered = None

    if source["image_id"]:

        registered = image_registry.get(
            source["session_id"], source["image_id"]
        )

    if isinstance(registered, dict) and registered.get("path"):

        if _r4_path_key(registered["path"]) != target_key:

            return _blocked("source_image_authority_mismatch")

    # 4. Source content integrity.
    integrity = _r4_source_integrity(source)

    admission["source_integrity"] = integrity

    if not integrity.get("verified"):

        return _blocked("source_image_integrity_failed")

    # 5. A single-source acceptance authorises exactly that source.
    if acceptance.get("scope") == "single_source":

        bound = str((acceptance.get("record") or {}).get("source_sha256") or "")

        if bound != str(integrity.get("sha256")):

            return _blocked("preservation_capability_unverified")

    contract = _r4_preservation_contract(
        text=text,
        source=source,
        integrity=integrity,
        edit_delta={"edit_class": "style_change"},
        image_understanding=None,
        acceptance=acceptance,
        workflow=str(workflow),
    )

    admission.update({
        "admitted": True,
        "reason": "admitted_with_preservation_contract",
        "selected_workflow": str(workflow),
        "preservation_contract": contract,
        "rejected_workflows": {},
    })

    return {"admitted": True, "reason": admission["reason"], "admission": admission}


def _r4_admission_verdict(
    text,
    source,
    edit_delta,
    context,
    image_understanding,
    edit_class,
    localization_required,
    verified_localization,
    spatial_change=False,
):
    """Decide whether the bounded, accepted capability covers this request.

    Returns a dict; `admitted` is False unless every condition holds.
    """

    workflow = _R4_ACCEPTED_WORKFLOW

    verdict = {
        "admitted": False,
        "reason": "preservation_capability_unverified",
        "workflow": None,
        "contract": None,
        "acceptance": None,
        "integrity": None,
        "role_conflict": None,
        # Preserved EXACTLY for the closed case: both installed whole-image
        # edit graphs remain unverified.
        "rejected_workflows": {
            "flux_kontext_edit.json": "preservation_capability_unverified",
            "flux_img2img.json": "preservation_capability_unverified",
        },
    }

    def _block(reason):

        verdict["reason"] = reason

        verdict["rejected_workflows"] = {
            "flux_kontext_edit.json": reason,
            "flux_img2img.json": "preservation_capability_unverified",
        }

        return verdict

    acceptance = _r4_acceptance_record(workflow)

    verdict["acceptance"] = {
        "accepted": bool(acceptance.get("accepted")),
        "reason": acceptance.get("reason"),
        "workflow": acceptance.get("workflow"),
        "scope": acceptance.get("scope"),
        "model": acceptance.get("model"),
        "path": acceptance.get("path"),
    }

    # 0. I2I_CONCEPTUAL_ADMISSION_V1 — an EXPLICIT per-request conceptual
    #    consent opens the maskless global APPEARANCE route, and only that.
    #
    #    Checked BEFORE the acceptance record because that record is the
    #    EXACT-preservation contract, which this mode deliberately does not
    #    assert. Nothing is fabricated: no record is written, and the verdict
    #    carries `preservation_status: conceptual_unverified`.
    #
    #    Every condition that makes a request architectural in the exact sense
    #    still closes it: a spatial mutation, a required localization, a role
    #    conflict, an unverified source, or an edit class outside the
    #    appearance set.
    if _r4_conceptual_consent(context):

        conflict = _r4_role_conflict(source, context)

        if conflict:

            verdict["role_conflict"] = conflict

            return _block("source_image_role_conflict")

        # A geometry mutation is never a conceptual appearance edit.
        #
        # A NAMED local target is NOT disqualifying, for the same reason step 5
        # gives: "cream travertine on the facade, keep the windows" names a
        # window but asks for a whole-facade restyle. What disqualifies is an
        # actual spatial mutation or a verified masked route.
        if spatial_change or localization_required or verified_localization:

            return verdict

        # The conceptual envelope is the MASKLESS whole-image route. A caller
        # mask is a different scope and stays closed.
        if isinstance(context, dict) and context.get("mask"):

            return verdict

        # An unambiguous property is required: a generic "change it" request
        # is not a material edit and stays refused.
        if not is_classified_edit_delta(edit_delta):

            return verdict

        if str(edit_class or "") not in _R4_ADMITTED_EDIT_CLASSES:

            return verdict

        integrity = _r4_source_integrity(source)

        verdict["integrity"] = integrity

        if not integrity.get("verified"):

            return _block("source_image_integrity_failed")

        verdict.update({
            "admitted": True,
            "reason": _R4_CONCEPTUAL_REASON,
            "workflow": _R4_CONCEPTUAL_WORKFLOW,
            "contract": None,
            "preservation_status": _R4_CONCEPTUAL_PRESERVATION_STATUS,
            "rejected_workflows": {},
        })

        return verdict

    # 1. DEFAULT: no accepted record => the pre-existing refusal.
    if not acceptance.get("accepted"):

        return verdict

    # 2. Role isolation runs before any content work: a style reference must
    #    never be edited as if it were the target building.
    conflict = _r4_role_conflict(source, context)

    if conflict:

        verdict["role_conflict"] = conflict

        return _block("source_image_role_conflict")

    # 3. The accepted envelope is a MASKLESS global appearance edit.  A
    #    caller mask is a different scope and stays unverified.
    if isinstance(context, dict) and context.get("mask"):

        return verdict

    # 4. Only a classified facade restyle resolves to the accepted graph.
    if not is_classified_edit_delta(edit_delta):

        return verdict

    if str(edit_class or "") not in _R4_ADMITTED_EDIT_CLASSES:

        return verdict

    # 5. A spatial mutation (close / remove / move / resize an element) is a
    #    geometry edit, not a facade restyle, and stays unverified.
    #
    #    A NAMED local target alone is not disqualifying: "dark metal window
    #    frames" names a window but asks for a whole-facade restyle. The
    #    localization that matters here is the caller mask excluded above and
    #    a verified masked route.
    if spatial_change or verified_localization:

        return verdict

    # 6. The existing selector must actually resolve this request to the
    #    accepted graph; a different graph stays closed.
    if str(_r4_resolved_workflow() or "") != workflow:

        return verdict

    # 7. Source content integrity.
    integrity = _r4_source_integrity(source)

    verdict["integrity"] = integrity

    if not integrity.get("verified"):

        return _block("source_image_integrity_failed")

    # 8. A single-source acceptance authorises exactly that source.
    if acceptance.get("scope") == "single_source":

        bound = str((acceptance.get("record") or {}).get("source_sha256") or "")

        if bound != str(integrity.get("sha256")):

            return verdict

    contract = _r4_preservation_contract(
        text=text,
        source=source,
        integrity=integrity,
        edit_delta=edit_delta,
        image_understanding=image_understanding,
        acceptance=acceptance,
        workflow=workflow,
    )

    verdict.update({
        "admitted": True,
        "reason": "admitted_with_preservation_contract",
        "workflow": workflow,
        "contract": contract,
        "rejected_workflows": {
            "flux_img2img.json": "not_the_accepted_workflow",
        },
    })

    return verdict


# ==========================================================
# R4_PHOTO_SAFE_CHAT_BRIDGE_V1 — PHOTOGRAPHIC WARMTH ELIGIBILITY
#
# WHY THIS IS A SEPARATE PREDICATE AND NOT AN EDIT-DELTA CLASS
#
# The compiler was measured directly. These four requests produce a
# BYTE-IDENTICAL delta:
#
#   "تراز رنگ این عکس را کمی گرم‌تر کن."                     -> color_change/facade
#   "رنگ کلی این عکس معماری را کمی گرم‌تر کن، ..."            -> color_change/facade
#   "Slightly warm the photographic colour balance ..."       -> color_change/facade
#   "Change the door colour only."                            -> color_change/facade
#   "What colour is the facade in this image?"                -> color_change/facade
#
# So `edit_class` / `edit_target` carry NO information that separates an
# accepted photographic colour adjustment from a localized material recolour
# or from a descriptive question. Requiring a new delta class would mean
# reclassifying material and facade-colour edits, which is out of scope and
# would weaken the very guard that must stay intact.
#
# Eligibility is therefore established by the request's own EXPLICIT
# photographic / global-colour-balance semantics plus the ABSENCE of every
# contradictory architectural change, and the delta is used only as a
# NEGATIVE check (it may veto, never authorize).
#
# The `facade` edit_target above is NOT treated as authorization to recolour
# the physical facade material. It is recorded in the evidence block and
# otherwise ignored.
# ==========================================================

_PHOTO_WARMTH_BALANCE_TERMS = (
    # English
    "colour balance", "color balance",
    "photographic colour", "photographic color",
    "global colour", "global color",
    "overall colour", "overall color",
    "white balance",
    # Persian
    "تراز رنگ", "تعادل رنگ", "رنگ کلی", "رنگ عمومی", "بالانس رنگ",
)

_PHOTO_WARMTH_TERMS = (
    "warm", "warmer", "warmth",
    # `_r4_normalized_text()` turns the ZWNJ in "گرم‌تر" into a space.
    "گرم تر", "گرمتر", "گرمای", "گرم رنگ",
)

_PHOTO_WARMTH_IMAGE_NOUNS = (
    "photo", "photograph", "image", "picture",
    "عکس", "تصویر", "نگاره",
)

# A LOCALIZED architectural surface. Any hit means the user asked to recolour
# a material, not to correct a photograph's global balance — fail closed.
_PHOTO_WARMTH_LOCALIZED_TARGETS = (
    "brick", "door", "window", "sky", "roof", "wall", "paving", "facade",
    "travertine", "stone", "plaster", "glass", "railing", "balcony",
    "entrance", "mullion", "column", "stair",
    "آجر", "پنجره", "آسمان", "بام", "دیوار", "نما", "سنگ", "مصالح",
    "شیشه", "نرده", "بالکن", "درب", "تراورتن", "گچ", "پله", "ستون",
)

_PHOTO_WARMTH_RELIGHT_TERMS = (
    "relight", "re-light", "sunlight", "sun shine", "sunshine",
    "light coming", "light through", "shadow", "lamp", "fixture",
    "نورپردازی", "نور خورشید", "آفتاب", "سایه", "چراغ", "روشنایی",
    "نور روز",
)

_PHOTO_WARMTH_TIME_TERMS = (
    "night", "evening", "sunset", "sunrise", "dusk", "dawn", "daytime",
    "golden hour",
    "غروب", "شبانه", "طلوع", "بامداد",
)

# "Keep the material RGB exactly as it is" is incompatible with a global
# recolouring BY DEFINITION, so it is refused rather than approximated.
_PHOTO_WARMTH_MATERIAL_LOCK_TERMS = (
    "material colour must", "material color must",
    "material colours must", "material colors must",
    "exact rgb", "rgb values must", "pixel values must",
    "رنگ مصالح", "رنگ متریال", "مقدار رنگ",
)

_PHOTO_WARMTH_GEOMETRY_TERMS = (
    "move", "resize", "shift", "rotate", "remove", "delete", "add a", "add an",
    "جابه", "حذف", "اضافه", "ببر", "تغییر ابعاد",
)

_PHOTO_WARMTH_QUESTION_PREFIXES = (
    "what", "which", "how", "why", "when", "where", "who",
    "is ", "are ", "does ", "do ", "can ", "could ", "would ",
    "چی", "چه", "چگونه", "آیا", "چرا", "کدام", "چقدر",
)

_PHOTO_WARMTH_ELIGIBLE_REASON = "photographic_global_colour_balance_warmth"


def _photo_warmth_terms_found(haystack, terms):
    return [term for term in terms if term in haystack]


def _photo_warmth_bridge_eligibility(text, edit_delta):
    """Decide whether this turn is an accepted photographic warmth edit.

    Returns `{"eligible": bool, "reason": str, "evidence": dict}`.

    Fails CLOSED: every unknown, ambiguous or contradictory request returns
    `eligible=False` and keeps the pre-existing routing.
    """

    raw = str(text or "")

    normalized = _r4_normalized_text(raw)

    delta = edit_delta if isinstance(edit_delta, dict) else {}

    evidence = {
        "contract": "PhotographicWarmthEligibilityV1",
        "version": "1.0",
        "normalized_text": normalized,
        "edit_class": delta.get("edit_class"),
        "edit_target": delta.get("edit_target"),
        # Recorded for audit ONLY. The `facade` target the compiler reports
        # for a photographic request is not user authorization to recolour
        # the physical facade material.
        "delta_target_is_not_material_authorization": True,
    }

    def refuse(reason):
        return {"eligible": False, "reason": reason, "evidence": evidence}

    if not normalized:
        return refuse("empty_request")

    # A descriptive question must stay ANALYSIS. The intent layer already
    # keeps questions out of the edit route; this is the second, independent
    # gate, because the compiler labels a question `color_change` too.
    if "?" in raw or "؟" in raw:
        return refuse("descriptive_question")

    if any(normalized.startswith(prefix) for prefix in _PHOTO_WARMTH_QUESTION_PREFIXES):
        return refuse("descriptive_question")

    # The delta may VETO here, never authorize.
    if delta.get("edit_class") != "color_change":
        return refuse("delta_class_not_photographic_colour")

    for field in (
        "material", "replaced_material", "time_of_day", "style",
        "lighting_quality",
    ):
        if delta.get(field):
            return refuse("delta_carries_contradictory_change:%s" % field)

    balance_hits = _photo_warmth_terms_found(normalized, _PHOTO_WARMTH_BALANCE_TERMS)
    if not balance_hits:
        return refuse("no_global_colour_balance_semantics")

    warm_hits = _photo_warmth_terms_found(normalized, _PHOTO_WARMTH_TERMS)
    if not warm_hits:
        return refuse("no_warmth_request")

    image_hits = _photo_warmth_terms_found(normalized, _PHOTO_WARMTH_IMAGE_NOUNS)
    if not image_hits:
        return refuse("no_image_reference")

    localized = _photo_warmth_terms_found(normalized, _PHOTO_WARMTH_LOCALIZED_TARGETS)
    if localized:
        evidence["localized_targets"] = localized
        return refuse("localized_architectural_target")

    relight = _photo_warmth_terms_found(normalized, _PHOTO_WARMTH_RELIGHT_TERMS)
    if relight:
        evidence["relight_terms"] = relight
        return refuse("physically_simulated_relighting")

    time_hits = _photo_warmth_terms_found(normalized, _PHOTO_WARMTH_TIME_TERMS)
    if time_hits:
        evidence["time_terms"] = time_hits
        return refuse("time_of_day_conversion")

    material_lock = _photo_warmth_terms_found(
        normalized, _PHOTO_WARMTH_MATERIAL_LOCK_TERMS
    )
    if material_lock:
        evidence["material_lock_terms"] = material_lock
        return refuse("material_rgb_must_remain_unchanged")

    geometry = _photo_warmth_terms_found(normalized, _PHOTO_WARMTH_GEOMETRY_TERMS)
    if geometry:
        evidence["geometry_terms"] = geometry
        return refuse("geometry_change_not_supported")

    evidence["balance_terms"] = balance_hits
    evidence["warmth_terms"] = warm_hits
    evidence["image_terms"] = image_hits
    evidence["preset"] = PRESET_WARM_BLUE_RESTRAINED_V1["name"]
    evidence["operation"] = "photometric_warmth_blue_restrained_v1"

    return {
        "eligible": True,
        "reason": _PHOTO_WARMTH_ELIGIBLE_REASON,
        "evidence": evidence,
    }


def _photo_warmth_source_mode(path):
    """Declared image mode of a source file, or None when unreadable.

    R4_PHOTO_FAST_PATH_CLOSURE_V1 — the photometric operation is RGB-only. The
    mode is read from the PNG/JPEG header without decoding pixels, so the fast
    path can decline BEFORE paying for an observation it cannot use.
    """

    try:

        from PIL import Image as _PILImage

        with _PILImage.open(str(path)) as opened:

            return opened.mode

    except Exception:

        return None


def _photo_warmth_output_root():
    """The approved, project-managed root the attachment service can serve."""

    try:

        root = chat_attachment_service.roots.get("architectos_output")

    except Exception:

        return None

    if root is None:

        return None

    return str(root)


def _photo_warmth_remove_output(path):
    """Best-effort removal of an output that will not be registered."""

    try:

        if path and os.path.isfile(path):

            os.unlink(path)

            return True

    except OSError:

        pass

    return False


def _r4_architectural_edit_admission(
    text,
    image_record,
    edit_delta,
    context,
    prior_intent,
    image_understanding,
):
    """Return a blocked result for unaccepted R4 architecture, else None.

    Non-architectural image editing is deliberately outside this guard and
    retains its existing route.  There is currently no manufactured positive
    architectural capability case: an accepted visual envelope must exist
    before this owner may select one.
    """

    local_targets = _r4_named_targets(text, _R4_LOCAL_TARGETS)
    spatial_targets = _r4_named_targets(text, _R4_PROTECTED_SPATIAL_TARGETS)
    spatial_change = bool(spatial_targets) and _r4_spatial_change(text)
    architectural = _r4_architectural_scope(
        text, prior_intent, image_understanding
    )

    if not architectural and not spatial_change:
        return None

    source = _r4_source_authority(image_record)
    if not source.get("valid"):
        return _r4_blocked_edit_result(
            "source_image_authority_mismatch",
            {
                "contract": "ArchitecturalEditAdmissionV1",
                "version": "1.0",
                "admitted": False,
                "selected_workflow": None,
                "source": source,
            },
        )

    edit_class = (
        edit_delta.get("edit_class")
        if isinstance(edit_delta, dict)
        else "generic_edit"
    ) or "generic_edit"
    classified = is_classified_edit_delta(edit_delta)
    strict = _r4_strict_preservation_requested(text, edit_delta)
    # CONCEPTUAL_I2I_LIVE_EVIDENCE_ADMISSION_V1 — distinguish a genuinely
    # localized appearance request from protected elements merely NAMED in a
    # global preservation clause.  Reuse the existing geometry guard's
    # deictic/localizing evidence; do not introduce another intent parser.
    #
    # The accepted live request says "window positions" while globally
    # targeting the facade.  That is not localization.  Conversely "this
    # facade area" / "the entrance wall" carries a localizing anchor and must
    # keep requiring a verified spatial route.
    scope_guard = detect_unsupported_geometry_edit(text)
    scope_evidence = (
        scope_guard.get("scope_evidence")
        if isinstance(scope_guard, dict)
        else {}
    ) or {}
    # A named local element is actionable localization only when the existing
    # scope classifier did NOT also resolve explicit global facade scope.
    # Thus the live request's global facade target plus preserved "window
    # positions" stays global, while «رنگ در ورودی» has no global scope and
    # retains the accepted localization-required diagnostic.
    #
    # NEOCLASSICAL_DESIGN_CHAT_ROUTE_V1 — the DEICTIC anchor obeys the same
    # rule as a named local target, but ONLY for a facade DESIGN. It did not:
    # the classifier's own contract (`image_intent_v1._is_localized`) states
    # "Scope, not deixis, decides", and it resolved `global_scope: True` for a
    # request that says "facade" and "building". But a single deictic "this" —
    # in "for THIS unfinished building", which names the SUBJECT, not a region
    # — set `localizing_anchor: True` and `localization_required` consumed it
    # unconditionally, so an explicitly global facade design was refused as
    # needing precise localization.
    #
    # The suppression is therefore gated on a REAL STYLE, not on global scope
    # alone. Global scope is trivially true for any request that mentions
    # "facade", so gating on it alone would have made
    # "change only this window's material on the facade" globally admissible —
    # a localized element change promoted to a whole-image edit. A facade
    # DESIGN names a style; a localized element change does not.
    #
    # The style token is extracted from either shape the delta uses (a plain
    # string or a `{"target": ...}` record) and the no-style sentinels are
    # refused. `str(None)` is the non-empty string "None", so a bare
    # `str(...).strip()` test reported a style for every request that named
    # none — which is exactly how the localized case slipped through.
    _style_value = (
        edit_delta.get("style") if isinstance(edit_delta, dict) else None
    )

    if isinstance(_style_value, dict):

        _style_value = _style_value.get("target") or _style_value.get("name")

    _style_token = str(_style_value or "").strip().lower()

    _named_style = bool(_style_token) and _style_token not in (
        "unknown", "none", "existing", "existing_architectural_style",
    )

    _global_scope_resolved = bool(scope_evidence.get("global_scope"))

    # NEOCLASSICAL_LIVE_EVIDENCE_HANDOFF_V1 — a STYLE NAME must never override a
    # genuine localized instruction.
    #
    # The previous milestone suppressed the deictic anchor for a global facade
    # design, which was correct for "for THIS unfinished building" (the subject)
    # but wrong for "design ONLY THE LEFT facade SECTION in neoclassical style":
    # that carries a style and the word "facade", so global scope resolved, the
    # anchor was suppressed and a section-scoped request was admitted globally.
    #
    # The anchor vocabulary mixes two different things:
    #   * DEICTIC SUBJECT words ("this", "its") — they name the building being
    #     redesigned and may be suppressed for a global design;
    #   * EXCLUSIVE / REGIONAL words ("only this", "only the", "the left",
    #     "the right", "particular") — they RESTRICT the scope and are never
    #     suppressed, whatever style the request names.
    _exclusive_scope = any(
        marker in " ".join(str(text or "").lower().split())
        for marker in _R4_EXCLUSIVE_SCOPE_MARKERS
    )

    localization_required = bool(
        spatial_change
        or (
            scope_evidence.get("localizing_anchor")
            and (
                _exclusive_scope
                or not (_named_style and _global_scope_resolved)
            )
        )
        or (local_targets and not _global_scope_resolved)
    )

    verified_localization = False
    if isinstance(context, dict) and context.get("mask"):
        verified_context = guard_context_with_source(
            context,
            source.get("session_id"),
            image_record=image_record,
        )
        route = precise_localized_route_available(verified_context)
        verified_localization = bool(route.get("available"))

    evidence_state = "none"
    if isinstance(image_understanding, dict) and image_understanding:
        evidence_state = "observation_only"

    admission = {
        "contract": "ArchitecturalEditAdmissionV1",
        "version": "1.0",
        "admitted": False,
        "reason": "preservation_capability_unverified",
        "explicit_edit": bool(classified or spatial_change),
        "architectural_scope": True,
        "edit_class": edit_class,
        "editable": {
            "target": local_targets or ([edit_delta.get("edit_target")] if classified else []),
            "property": edit_class if classified else "spatial_change",
            "scope": "localized" if localization_required else "global",
        },
        "protected": [
            "massing", "silhouette", "storeys", "roof", "parapet",
            "windows", "doors", "openings", "through_passages",
            "spatial_depth", "railings", "balconies", "details",
            "unmodified_materials", "camera", "perspective",
        ],
        "strict_preservation": strict,
        "localization_required": localization_required,
        "verified_localization": verified_localization,
        "protected_spatial_targets": spatial_targets,
        "architectural_evidence": evidence_state,
        "source": source,
        "selected_workflow": None,
        "rejected_workflows": {
            "flux_kontext_edit.json": "preservation_capability_unverified",
            "flux_img2img.json": "preservation_capability_unverified",
        },
        "human_learning_authority": "not_used_for_visual_capability",
    }

    # A generic architectural instruction lacks an unambiguous property; an
    # explicit spatial mutation is independently protected.  Classified edits
    # have an unambiguous property, but still lack a visually accepted workflow
    # unless the bounded acceptance record covers them (FACADE_RENDERING_FIRST
    # _I2I_ADMISSION_V1).
    verdict = _r4_admission_verdict(
        text=text,
        source=source,
        edit_delta=edit_delta,
        context=context,
        image_understanding=image_understanding,
        edit_class=edit_class,
        localization_required=localization_required,
        verified_localization=verified_localization,
        spatial_change=spatial_change,
    )

    admission["source_integrity"] = verdict.get("integrity")
    admission["acceptance"] = verdict.get("acceptance")
    admission["preservation_contract"] = None

    if verdict.get("admitted"):

        admission.update({
            "admitted": True,
            "reason": verdict.get("reason"),
            "selected_workflow": verdict.get("workflow"),
            "rejected_workflows": verdict.get("rejected_workflows"),
            "preservation_contract": verdict.get("contract"),
            # I2I_CONCEPTUAL_ADMISSION_V1 — None for every exact-preservation
            # admission; "conceptual_unverified" only for consented conceptual
            # edits, where no preservation capability is asserted.
            "preservation_status": verdict.get("preservation_status"),
        })

        if verdict.get("preservation_status") == _R4_CONCEPTUAL_PRESERVATION_STATUS:

            admission["conceptual_edit"] = {
                "consented": True,
                "preservation_status": _R4_CONCEPTUAL_PRESERVATION_STATUS,
                "workflow": verdict.get("workflow"),
                "notice": (
                    "Conceptual edit: geometry preservation is best-effort only. "
                    "Windows, floors, massing and architectural details may "
                    "drift, and the result is conceptual — not construction-"
                    "accurate. A completed render does not prove architectural "
                    "fidelity."
                ),
            }

        if isinstance(context, dict):

            # Request-scoped handoff to the route that composes the prompt.
            # Nothing is persisted and no client input can set this.
            context["r4_preservation_contract"] = verdict.get("contract")
            context["r4_admission"] = admission

        return None

    admission["reason"] = verdict.get("reason")
    admission["rejected_workflows"] = verdict.get("rejected_workflows")

    return _r4_blocked_edit_result(
        verdict.get("reason"),
        admission,
    )


def _teaching_review(candidate, user_text=None):
    """Review projection that tolerates both existing candidate contracts."""

    data = candidate.to_dict() if hasattr(candidate, "to_dict") else candidate

    if not isinstance(data, dict):
        data = {}

    statement = str(
        user_text
        or data.get("source_statement")
        or data.get("human_basis")
        or data.get("raw_statement")
        or ""
    )

    modality = "UNSPECIFIED"

    try:
        from core.architecture.knowledge.human_learning_ledger_v1 import (
            modality_of,
        )

        modality = modality_of(
            str(data.get("source_statement") or data.get("human_basis") or statement)
        )
    except Exception:
        pass

    uncertainty = []

    confidence = data.get("confidence")

    if isinstance(confidence, (int, float)) and confidence < 0.75:
        uncertainty.append("extraction confidence %.2f" % float(confidence))

    raw_statement = str(data.get("raw_statement") or "")

    if raw_statement and statement and raw_statement not in statement:
        uncertainty.append(
            "clause-level extraction; the full statement is preserved above"
        )

    if data.get("facets_present") is not None and not data.get("facets_present"):
        uncertainty.append("no architectural facet was extracted")

    return {
        "original_statement": statement,
        "proposition": data.get("normalized_meaning") or data.get("knowledge_class"),
        "proposed_rule": {
            "kind": data.get("candidate_kind"),
            "knowledge_class": data.get("knowledge_class"),
            "domain": data.get("domain"),
            "domain_tags": list(data.get("domain_tags") or []),
            "element": list(data.get("element") or []),
        },
        "modality": modality,
        "applicability": {
            "scope": data.get("scope"),
            "domain": data.get("domain"),
            "conditions": data.get("applies_to"),
        },
        "confirmation_status": data.get("status"),
        "uncertainty": uncertainty,
        "conflicts": [],
    }


def _teaching_review_block(candidate, observation=None, user_text=None):
    """Read-only review of a teaching candidate for the current turn.

    This presents what the teacher said and what the system understood. It is
    NOT an acceptance: nothing is written, and confirmation is reported as
    unavailable because the application exposes no authenticated actor
    identity. A caller-supplied string is provenance, not authorization.
    """

    data = candidate.to_dict() if hasattr(candidate, "to_dict") else candidate

    if not isinstance(data, dict):
        data = {}

    return {
        "action": "review_candidate",
        "candidate": data,
        "review": _teaching_review(candidate, user_text),
        # a displayed candidate is not knowledge
        "confirmation_required": True,
        "accepted": False,
        "permanent_learning": False,
        # no authenticated actor identity exists in this application, so no
        # durable confirmation may be offered from this surface
        "confirmation_available": False,
        "confirmation_blocked_reason": "no_authenticated_actor",
    }


def _manual_image_intent(manual_mode, text, intent_router):
    """The effective image intent for a manually selected UI mode.

    R2_UI_ANALYZE_MISROUTING_FIX_V1
    -------------------------------
    The user's explicit mode is authoritative. Before this, only
    ``image_to_image`` was honoured; ``analyze_image`` fell through to the text
    classifier, which treats the deictic «این ساختمان» as an edit verb. A
    descriptive question was therefore routed to a real img2img render.

    "Analyze Image" is an explicit OBSERVATION request: read the image, never
    change it. Observation-only phrasing keeps its own intent so the existing
    observation layer still answers it; everything else becomes analysis.
    """

    if manual_mode == "image_to_image":

        return {
            "contract": "ImageIntentV1",
            "version": "1.0",
            "intent": INTENT_EDIT,
            "reason": "validated_manual_mode",
            "matched": ["mode:image_to_image"],
            "is_question": False,
        }

    if manual_mode == "analyze_image":

        classified = classify_image_intent(text, intent_router)

        # An explicit "list only the visible elements" request keeps the
        # observation-only answer. Anything else — including a question that
        # merely NAMES the building — is analysis, never an edit.
        if classified.get("intent") == INTENT_OBSERVE:

            return classified

        return {
            "contract": "ImageIntentV1",
            "version": "1.0",
            "intent": INTENT_ANALYZE,
            "reason": "validated_manual_mode",
            "matched": ["mode:analyze_image"],
            "is_question": bool(classified.get("is_question")),
        }

    return classify_image_intent(text, intent_router)


# ==========================================================
# RENDER_FOLLOWUP_V1 — COLLOQUIAL PERSIAN RENDER FOLLOW-UPS
#
# MEASURED DEFECT (2026-11-08, deterministic, CPU):
#
#   "رندر شبش بگیر"                    -> no edit signal -> analyze
#   "همین ساختمون رو رندر شب بگیر"      -> no edit signal -> analyze
#   "از یه زاویه دیگه رندر بگیر"        -> edit signal, but
#                                          compile_edit_delta() = generic_edit
#                                          and is_image_edit_request() = False
#
# All three are follow-ups on the render the user is already looking at, but
# none of them reached the image-edit owner, so the turn fell through to the
# design route and was answered with the text-only
# "✅ طراحی با موفقیت ایجاد و ذخیره شد." stub.
#
# WHY A DETECTOR AND NOT MORE KEYWORDS:
# `_EDIT_PHRASES` is a contiguous-substring table, so "رندر بگیر" matches and
# "رندر شبش بگیر" cannot — the possessive sits between the noun and the verb.
# Enumerating every infix form would be an unbounded table. This detector
# states the actual grammar instead: a RENDER NOUN plus a FOLLOW-UP MODIFIER
# (time of day, camera angle) plus an IMPERATIVE.
#
# It is deliberately NOT an edit predicate on its own. It only ever matters
# when the session already holds the active image (`last_image_asset`) and an
# edit-capable state, both of which the caller checks — so a first-turn
# "رندر شب بگیر" with nothing to re-render is never captured by it.
# ==========================================================

_RENDER_FOLLOWUP_NOUN = r"(?:رندر|رندرینگ|render|تصویر|عکس|ویژوال|visual)"

_RENDER_FOLLOWUP_IMPERATIVE = (
    r"(?:بگیر|بگیرش|بده|بدهش|بساز|بسازش|کن|کنش|کنید|"
    r"take|give|make|do|render)"
)

#: Time-of-day and camera-angle follow-ups: the two things a user asks for
#: AFTER a render exists. Both are re-renders of the same building, never a
#: new design brief.
_RENDER_FOLLOWUP_MODIFIERS = (
    "شب", "شبش", "شبانه", "شبی", "روز", "روزش", "روزانه",
    "غروب", "طلوع", "گرگ", "مغرب",
    "زاویه", "دیگه", "دیگر", "پرسپکتیو", "دوربین", "کلوزآپ", "نمای نزدیک",
    "night", "dusk", "twilight", "sunset", "daytime",
    "another angle", "different angle", "new angle", "camera",
)

_RENDER_FOLLOWUP_PATTERNS = (
    # "رندر شبش بگیر" / "رندر شب بگیر" / "رندر شبانه بده" / "رندر رو شب کن"
    re.compile(
        _RENDER_FOLLOWUP_NOUN
        + r"[^\n]{0,24}?"
        + r"(?:شب|روز|غروب|طلوع)(?:ش|ی|انه|ه)?"
        + r"[^\n]{0,12}?"
        + _RENDER_FOLLOWUP_IMPERATIVE
    ),
    # "شبش کن" / "روزش کن" / "شبش رو بگیر" — possessive form, no render noun
    re.compile(
        r"(?:شب|روز|غروب|طلوع)ش\s*(?:رو|را)?\s*" + _RENDER_FOLLOWUP_IMPERATIVE
    ),
    # "از یه زاویه دیگه رندر بگیر" / "یه زاویه دیگه"
    re.compile(
        r"(?:زاویه|پرسپکتیو|دوربین)\s*[^\n]{0,20}?"
        r"(?:دیگه|دیگر|جدید|مختلف)"
    ),
    # "another angle" / "different camera angle"
    re.compile(
        r"(?:another|different|new)\s+(?:angle|camera|view|perspective)"
    ),
    # "render it at night"
    re.compile(
        r"(?:render|re-?render)[^\n]{0,20}?\b(?:at\s+)?night\b"
    ),
    # ==========================================================
    # FACADE_FOLLOWUP_V27 — "the same facade" phrasings
    #
    # Measured gap: `همون نما رو شب بگیر`, `نمای شب` and `نمای شبش` carried
    # no contiguous hit in any earlier table. `همون نما` names the SAME
    # building as `همین نما`, and a bare `نمای شب` is a night-view request,
    # not a new design brief — so both belong to this grammar.
    # ==========================================================
    # "همین/این/همون/اون نما رو شب بگیر"
    re.compile(
        r"(?:همین|این|همون|اون|آن)\s*(?:نما|ویو|عکس|تصویر)"
        r"[^\n]{0,16}?"
        r"(?:شب|روز|غروب|طلوع)(?:ش|ی|انه|ه)?"
    ),
    # "همین/همون نما رو بگیر" — same view, no time-of-day word
    re.compile(
        r"(?:همین|این|همون|اون|آن)\s*(?:نما|ویو)\s*(?:رو|را)?\s*"
        + _RENDER_FOLLOWUP_IMPERATIVE
    ),
    # "نمای شب" / "نمای روز" / "نمای شبش" — bare time-of-day view
    re.compile(
        r"(?:نما|ویو)\s*(?:ی\s*)?(?:شب|روز|غروب|طلوع)(?:ش|ی|انه|ه)?\b"
    ),
)


def detect_render_followup(text):
    """Classify a colloquial follow-up render request.

    Returns a deterministic contract. ``matched`` is False for everything
    that is not a follow-up re-render of the active image; the caller must
    additionally require an active image before acting on a True result.
    """

    raw = str(text or "")

    normalized = " ".join(raw.lower().replace("\u200c", " ").split())

    result = {
        "contract": "RenderFollowupV1",
        "version": "1.0",
        "matched": False,
        "reason": None,
        "matched_patterns": [],
        "modifiers": [],
    }

    if not normalized:

        result["reason"] = "empty"

        return result

    for pattern in _RENDER_FOLLOWUP_PATTERNS:

        if pattern.search(normalized):

            result["matched_patterns"].append(pattern.pattern)

    result["modifiers"] = [
        modifier for modifier in _RENDER_FOLLOWUP_MODIFIERS
        if modifier in normalized
    ]

    if result["matched_patterns"]:

        result["matched"] = True
        result["reason"] = "colloquial_render_followup"

        return result

    result["reason"] = "no_followup_signal"

    return result


def resolve_state_edit_signal(text, edit_delta, intent_router, followup=None):
    """The ONE predicate that decides an edit-session continuation.

    Extracted so the routing contract is testable without building the whole
    application. Three independent signals, any of which is sufficient:

    * a compiled delta that names a real edit class (not `generic_edit`);
    * the router's own edit vocabulary;
    * a colloquial follow-up re-render, which by construction carries no
      contiguous phrase from either of the other two tables.

    It is a SIGNAL only. The caller still requires an active image and an
    edit-capable state, and still refuses an explicit analyze or an explicit
    text-to-image turn.
    """

    if followup is None:

        followup = detect_render_followup(text)

    matched = bool(
        isinstance(followup, dict) and followup.get("matched")
    )

    if (
        isinstance(edit_delta, dict)
        and edit_delta.get("edit_class")
        and edit_delta.get("edit_class") != "generic_edit"
    ):

        matched = True

    if intent_router is not None:

        try:

            if intent_router.is_image_edit_request(text):

                matched = True

        except Exception:  # noqa: BLE001

            pass

    return matched


def _v22_exact_floor_control(num_floors):
    """Stage the exact-N-storey scaffold into ComfyUI's input directory.

    Returns ``(control_image_name, meta)``. The name embeds the scaffold's
    own content digest, so the same request always reuses the same file and
    a different count can never collide with an earlier one.
    """

    from config import runtime_config as _rc

    from core.render.experimental.architectos_v22_highrise_night_v1 import (
        synthesize_exact_n_story_tower_controlnet,
        write_png,
    )

    image, meta = synthesize_exact_n_story_tower_controlnet(int(num_floors))

    name = "architectos_v22_floors_%d_%s.png" % (
        int(num_floors),
        str(meta.get("sha256_png") or "")[:16],
    )

    target = os.path.join(_rc.COMFYUI_INPUT_DIR, name)

    if not os.path.exists(target):

        try:

            write_png(target, image)

        except FileExistsError:

            # A concurrent turn wrote the identical scaffold first. The
            # content is digest-addressed, so it is the same file.
            pass

    return name, meta


class ChatArchitect:


    def __init__(
        self,
        brain
    ):


        self.brain = brain


        # ==================================================
        # CHAT_LANGUAGE_02 — SESSION SCOPING
        #
        # self.state resolves to the state of the session bound to
        # the current thread (see session_registry.begin()).  When no
        # session is bound the legacy global singleton is used, so
        # previous behaviour is fully preserved.
        # ==================================================

        self._default_state = conversation_state



        # ==================================================
        # Intelligence Layer
        # ==================================================


        self.llm = LLMGateway()


        self.prompt_engine = PromptEngine()


        self.intent_router = intent_router



        self.semantic_intent = SemanticIntentEngine(

            llm=self.llm,

            fallback=ArchitecturalIntent()

        )


        self.material_intelligence = ArchitecturalMaterialIntelligence()





        # ==================================================
        # Render Layer
        # ==================================================


        self.prompt_builder = PromptBuilder()


        # ==================================================
        # Architectural Intent Bridge
        # SINGLE SOURCE OF TRUTH
        # ==================================================


        self.architectural_intent = getattr(
            brain,
            "architectural_intent_engine",
            ArchitecturalIntent()
        )


        self.architectural_llm_parser = architectural_llm_parser


        self.intent_normalizer = intent_normalizer


        self.render_runtime = RenderRuntime(
            semantic_intent=self.semantic_intent
        )


        self.result_bridge = RenderResultBridge()


        self.design_bim_bridge = ArchitectOSDesignExecutionBridge()



        # ==================================================
        # Memory Layer
        # ==================================================


        self.memory = memory_manager


        self.recall = ContextRecall(

            self.memory

        )


        self.context_builder = ContextBuilder()


        self.writeback = create_writeback(

            self.memory

        )





        # ==================================================
        # Chat Layer
        # ==================================================


        self.input_adapter = ChatInputAdapter()


        self.image_bridge = ChatImageBridge()


        self.image_response = ImageResponseAdapter()


        self.response_adapter = ResponseAdapter()


        self.state = conversation_state


        # ==================================================
        # Conversation State Compatibility Bridge
        # ==================================================

        self.conversation_state = self.state


        self.image_handler = ImageHandler(

            render_runtime=self.render_runtime,

            result_bridge=self.result_bridge,

            semantic_intent=self.semantic_intent,

            image_bridge=self.image_bridge,

            image_response=self.image_response,

            writeback=self.writeback,

            state=self.state,

            prompt_builder=self.prompt_builder

        )



        # ==================================================
        # Cognitive Bridge
        # ==================================================


        self.cognitive = None



        if hasattr(

            brain,

            "process"

        ):


            self.cognitive = brain



        elif hasattr(

            brain,

            "cognitive_agent"

        ):


            self.cognitive = brain.cognitive_agent





        print(

            "💬 CHAT RUNTIME GATEWAY v28 ONLINE"

        )


    # ======================================================
    # CHAT_LANGUAGE_02 — SESSION SCOPED STATE
    # ======================================================

    @property
    def state(self):
        """Conversation state of the current session (thread bound)."""

        return session_registry.current_state(
            self._default_state
        )


    @state.setter
    def state(self, value):

        self._default_state = value


    def _architectural_context_store(self):
        """Architectural conversation context of the current session."""

        return session_registry.current_architectural_context(
            architectural_conversation_context
        )


    def _subject_compile_context(self, text, context):
        """T2I_HIGH_RISE_SUBJECT_FIDELITY_V1 — grounded inputs for the subject.

        The effective architectural understanding carries neither a floor count
        nor a building type, so the compiler could only ever name the subject
        as the bare terminology tag "tower". This hands the compiler the two
        values it is missing, WITHOUT changing anything else:

          * ``requested_floors`` — from ``requested_floor_count()``, the single
            floor-count authority. It already drops negated counts, counts that
            merely describe an existing building, and prohibited counts, so a
            number is present here only when the user affirmatively requested
            it as a design target.

          * ``subject_terms`` — the canonical terminology terms the request
            actually matched. The compiler uses them only to confirm that the
            building type the user named is genuinely a high-rise.

        Returns the caller's context with those two keys added, or the caller's
        context unchanged when neither is available. A missing/failed lookup is
        never fatal: the compiler simply emits no subject section.
        """

        merged = dict(context) if isinstance(context, dict) else {}

        try:

            floor = requested_floor_count(str(text or ""))

            if isinstance(floor, dict) and isinstance(
                floor.get("value"), int
            ) and not isinstance(floor.get("value"), bool):

                merged["requested_floors"] = floor["value"]

        except Exception:

            pass

        try:

            terms = normalize_architectural_terms(
                str(text or "")
            ).get("canonical_terms") or []

            if terms:

                merged["subject_terms"] = list(terms)

        except Exception:

            pass

        return merged


    def _trusted_user_geometry(self, context):
        """FACADE-04D.3C-9P-B12 — the TRUST BOUNDARY for a user confirmation.

        A ``USER_CONFIRMATION`` may be produced ONLY from a message that this
        server-side boundary has itself established as user-authored. Two
        sources are considered, in order:

        1. ``context["user_geometry"]`` — a per-request field written by the
           API boundary (``app.py``) from the CURRENT turn's incoming text.
           It is only honoured when it carries an explicit user origin; the
           validator in the cognition module re-checks it.

        2. The persisted conversation messages for THIS session, filtered to
           ``role == "user"``. Assistant turns, model output, summaries and
           vision observations are excluded by construction. Only an EXPLICIT
           floor-count assertion is accepted, and the LATEST one wins (so a
           later user correction supersedes an earlier statement).

        A client-supplied dictionary claiming ``origin="user"`` is NEVER
        sufficient on its own — the value must be traceable to user-authored
        text that this boundary can see. Returns ``None`` when nothing is
        trustworthy, in which case behaviour is exactly as before.
        """

        from core.cognition.architectural_render_instruction_v1 import (
            user_geometry_from_messages,
        )

        context = context if isinstance(context, dict) else {}

        # ---- 1. per-request carrier (current turn), origin re-validated ----
        explicit = context.get("user_geometry")

        if isinstance(explicit, dict) and explicit:

            return explicit

        # ---- 2. persisted USER-authored turns for THIS session ----
        try:

            state = session_registry.current_state(None)

            if state is None:

                return None

            # ConversationState.get() returns a copy of the whole state dict.
            snapshot = state.get() if hasattr(state, "get") else None

            messages = (
                snapshot.get("messages")
                if isinstance(snapshot, dict)
                else None
            )

            return user_geometry_from_messages(messages)

        except Exception as e:

            print(
                "TRUSTED USER GEOMETRY ERROR:",
                e
            )

            return None


    # ======================================================
    # CHAT_LANGUAGE_02 — BOUNDED LANGUAGE CORRECTION
    #
    # ResponseGuard used to detect a language mismatch and only warn.
    # This is the one bounded correction path: a SINGLE rewrite
    # attempt, no retry loop, deterministic fallback on failure.
    # ======================================================

    LANGUAGE_CORRECTION_INSTRUCTION = (
        "Rewrite the assistant reply in the SAME LANGUAGE as the user's "
        "message. Keep the meaning, the facts and the level of detail "
        "identical. Do not add new information. Do not explain. "
        "Output only the rewritten reply."
    )


    def _language_corrector(
        self,
        user,
        response,
        check
    ):
        """ONE bounded correction call. Never retried, never looped."""

        target = check.get("input_language")

        if target not in ("persian", "english"):

            return None

        instruction = (

            self.LANGUAGE_CORRECTION_INSTRUCTION

            + "\n\nUSER MESSAGE:\n"
            + str(user)

            + "\n\nREPLY TO REWRITE:\n"
            + str(response)

        )

        return self.llm.generate(instruction)


    # ======================================================
    # OFFLINE_FIRST_V1 — graceful degradation text
    # ======================================================

    def _offline_reply_text(
        self,
        expected_language=None
    ):
        """A short, truthful message for when the local LLM is down.

        It says what actually happened (the reasoning engine is not
        reachable) and that the rest of ArchitectOS still works. It never
        pretends to answer the question.
        """

        language = str(expected_language or "").lower()

        if language.startswith("fa") or language == "persian":

            return (
                "در این لحظه موتور استدلال محلی در دسترس نیست، "
                "بنابراین نمی‌توانم به این پیام پاسخ بدهم. "
                "بقیهٔ بخش‌های ArchitectOS فعال است؛ "
                "لطفاً کمی بعد دوباره تلاش کنید."
            )

        return (
            "The local reasoning engine is not reachable right now, "
            "so I can't answer this message. "
            "The rest of ArchitectOS remains available — "
            "please try again shortly."
        )


    # ======================================================
    # CODER-05 — AUTHORIZED PROJECT CODE FILE CREATION
    #
    # ONE narrow capability: when the user EXPLICITLY asks to create a .py file
    # in the current project, the source is taken from verified conversation
    # history (or produced by the dedicated coding model) and written into the
    # project sandbox. Execution is never involved. Any other code request
    # keeps the truthful capability refusal.
    # ======================================================

    _CODE_FILENAME_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]{0,127}\.py)")

    # CHAT_APP_CREATION_ROUTING_V1 — a user who asks for an application does not
    # name a file. This is the general fallback name, not a product-specific one.
    DEFAULT_APP_FILENAME = "app.py"

    _CODE_CREATE_ACTIONS = (
        "بساز", "بسازید", "ایجاد کن", "ایجاد کنید", "ذخیره کن", "ذخیره کنید",
        "درست کن", "درست کنید", "بسازه",
    )

    # CODER-06 — explicit SYNTAX-VALIDATION actions.
    _CODE_SYNTAX_ACTIONS = (
        "خطاهای نحوی", "خطای نحوی", "بررسی نحوی", "از نظر نحو",
        "syntax error", "syntax check", "syntax checking", "نحوی",
    )

    # CODER-05B — explicit rejection of a staged proposal.
    #
    # CODER-STAGING-ACTION-SAFETY-01 — this vocabulary now lives ONLY in
    # ``code_file_staging_v1.staged_file_action``. Keeping a second substring
    # copy here meant two independent authorities for a privileged state
    # change, and the copy matched «رد کن» inside «وارد کن».
    # ``_authorized_code_file_approval`` consumes the staging verdict instead.

    # CODER-05C — source provenance vocabulary.
    #
    # History is a legitimate source ONLY when the turn explicitly asks to
    # save/reuse code that already exists in this project's conversation.
    # These markers are deliberately about the SOURCE of the bytes, not about
    # file writing: "ذخیره کن" means "write the code we already have".
    _CODE_REUSE_SOURCE_ACTIONS = (
        "همان کد", "کد قبلی", "کد بالا", "کد ارسالی", "این کد", "کدی که",
        "ذخیره کن", "ذخیره کنید", "ثبت کن",
        "the code above", "previous code", "same code", "that code",
        "save this code", "save the code", "reuse the code",
    )

    # A turn carrying one of these asks for NEW implementation work and must
    # reach the coding model. This wins over the reuse vocabulary above so that
    # "the previous code, regenerate it" is treated as generation.
    _CODE_NEW_APP_ACTIONS = (
        "بساز", "ایجاد کن", "از نو", "جدید", "بنویس",
        "create", "make a new", "new file", "regenerate", "rewrite", "build",
    )

    # CODER-05F — verbs that ask the model to PRODUCE new source. These are
    # distinct from the save vocabulary: "ذخیره کن" writes what is already
    # staged, while "تولید کن" / "نسخه جدید" ask for fresh code. A turn built
    # from these is a GENERATION turn even when it also says "تأیید".
    _CODE_GENERATION_ACTIONS = (
        "تولید کن", "تولید کنید", "نسخه جدید", "نسخهٔ جدید",
        "اصلاح کن", "اصلاح کنید", "بازنویسی کن", "بازنویسی کنید",
        "دوباره بساز", "از نو بساز", "بنویس",
        "regenerate", "rewrite", "generate a new",
    )

    # ======================================================
    # CODER-REPAIR-01 — REPAIR OF THE CURRENT PENDING DRAFT
    #
    # The pending-proposal guard in ``_authorized_code_file_creation``
    # correctly refuses to overwrite a draft, but it also made a draft
    # unrecoverable: a user who could SEE the defect had no way to ask for a
    # fix short of rejecting it and regenerating the whole file.
    #
    # The three vocabularies below are a CONJUNCTION, not a keyword list,
    # because the measured request in project_f043688f (message 22) contains a
    # repair verb ("اصلاح"), a draft reference ("پیش‌نویس") AND a restriction
    # ("فقط") while still asking for a complete new version. It is a
    # generation request and must stay blocked. What separates it from a repair
    # is the whole-artifact vocabulary below.
    # ======================================================

    #: A repair VERB. Deliberately no bare nouns.
    #:
    #: CODER-CREATE-VS-REPAIR-01 — measured 2026-10-26 in project_aff545c4: a
    #: CREATE request that says «عمداً یک باگ قرار بده» matched the noun "باگ"
    #: and entered the repair branch, which refused with ``no_pending_proposal``
    #: before the Coder was ever called. Naming a defect is not asking for a
    #: repair; the verb is what carries the action.
    _CODE_REPAIR_ACTIONS = (
        "اصلاح کن", "اصلاح کنید", "اصلاحش کن", "اصلاح شود",
        "درستش کن", "درست کنید",
        "رفع کن", "رفع کنید", "رفع اشکال", "رفع باگ",
        "fix", "repair", "patch",
    )

    #: Actions that produce a NEW artifact. A turn carrying one of these is a
    #: CREATE request even when its specification describes a defect, so it
    #: outranks incidental bug vocabulary.
    _CODE_NEW_ARTIFACT_ACTIONS = (
        "بساز", "بسازید", "بسازه", "ایجاد کن", "ایجاد کنید",
        "create", "build", "make a new", "write a new", "generate a new",
        "new file", "فایل جدید", "برنامه جدید",
    )

    #: Words that name "the draft". Alone they are ambiguous: «فقط پیش‌نویس را
    #: بساز» names a FUTURE output, not an existing proposal.
    _CODE_DRAFT_WORDS = (
        "پیش‌نویس", "پیشنویس", "draft",
        "pending proposal", "staged proposal",
    )

    #: Markers that a draft word refers to the EXISTING, already-staged one.
    #: A repair target must be identified by proximity to one of these.
    _CODE_EXISTING_TARGET_MARKERS = (
        "فعلی", "کنونی", "موجود", "همین", "جاری", "بالا", "قبلی",
        "ساخته", "ذخیره‌شده", "ذخیره شده", "ثبت‌شده", "ثبت شده",
        "current", "existing", "pending", "already", "staged", "above",
        "you made", "you built", "you created", "you staged", "you showed",
    )

    #: A scoped repair states its own restriction. Without one the turn
    #: authorizes the whole file, which is a generation request.
    _CODE_REPAIR_SCOPE_RESTRICTIONS = (
        "فقط", "تنها", "بقیه", "سایر", "دیگر بخش", "تغییر نده", "تغییر ندهید",
        "دست نزن", "دست نزنید", "بدون تغییر", "باقی را",
        "only", "everything else", "keep everything", "unchanged",
        "rest of the file", "do not change", "don't change", "nothing else",
    )

    #: Whole-artifact replacement vocabulary. A turn carrying one of these
    #: authorizes the entire file, so it is NOT a scoped repair and must stay
    #: behind the pending-proposal guard.
    _CODE_FULL_GENERATION_SIGNALS = (
        "نسخه جدید", "نسخهٔ جدید", "نسخه كامل", "نسخه کامل",
        "تولید کن", "تولید کنید", "از نو", "دوباره بساز", "دوباره بنویس",
        "دوباره تولید", "بازنویسی کن", "بازنویسی کنید",
        "فایل جدید", "برنامه جدید", "اپلیکیشن جدید",
        "new version", "new file", "new app", "from scratch",
        "regenerate", "generate a new", "start over", "build a new",
    )

    # ======================================================
    # CODER-HISTORY-REUSE-01 — RESTORE ALREADY-DISPLAYED SOURCE
    #
    # Measured 2026-10-26 in project_20f920b5 after a restart: the user asked
    # to bring back the app.py draft that had already been displayed, and
    # ArchitectOS answered `no_images_in_session`. The turn carried no
    # creation/generation verb, so the image-reference boundary did not skip
    # it, and the code boundary would have refused it anyway.
    #
    # A reuse turn is a CONJUNCTION of an explicit restore action and a code
    # SOURCE reference, and it is defeated by a positive whole-artifact
    # request. "تصویر قبلی" / "رندر قبلی" carry the same "قبلی" and must never
    # be mistaken for it.
    # ======================================================

    #: An explicit request to bring the earlier source back.
    _CODE_HISTORY_REUSE_ACTIONS = (
        "بازیابی کن", "بازیابی کنید", "بازیابی", "بازگردان", "بازگردانی",
        "برگردان", "از تاریخچه", "تاریخچه همین پروژه", "تاریخچه این پروژه",
        "تاریخچهٔ این پروژه", "تاریخچه گفتگو", "تاریخچهٔ گفتگو",
        "restore", "recover", "reuse", "bring back", "from the history",
        "from history", "from this project's history",
    )

    #: A reference to the CODE ITSELF. Deliberately excludes bare "قبلی":
    #: a previous image or render is not source code.
    _CODE_HISTORY_SOURCE_REFERENCES = (
        "همان کد", "کد قبلی", "کد بالا", "کد ارسالی", "کدی که",
        "کد نمایش داده", "کد پایتون", "the code above", "previous code",
        "earlier code", "same code", "that code", "the code you showed",
    )

    #: A NEGATED generation verb is a prohibition, not a request.
    #: «کد جدید تولید نکن» must not invoke the model.
    #:
    #: These are deliberately CODE-SPECIFIC. Measured 2026-10-26: the real
    #: generation request in project_f043688f ends with «برنامه را اجرا نکن و
    #: EXE نساز», and a bare "نساز" marker classified it as a prohibition —
    #: so a genuine build request stopped reaching the coding model. A
    #: prohibition on PACKAGING or on writing to disk is not a prohibition on
    #: generating source.
    _CODE_GENERATION_PROHIBITIONS = (
        "کد جدید تولید نکن", "کد جدید تولید نکنید", "کد تولید نکن",
        "کد جدید نساز", "کد جدید نسازید", "کد جدید ننویس",
        "کد جدید ننویسید", "نسخه جدید نساز", "نسخه جدید تولید نکن",
        "برنامه جدید نساز", "فایل جدید نساز",
        "بدون تولید کد", "بدون ساخت کد",
        "do not generate new code", "don't generate new code",
        "do not generate code", "don't generate code",
        "do not write new code", "don't write new code",
        "do not regenerate", "no new code", "without generating code",
    )

    # CODER-05F — mentioning approval is not granting it.
    #
    # "بدون تأیید من هیچ فایلی ذخیره نکن" contains the approval marker "تأیید"
    # AND the save verb "ذخیره کن", so the staging vocabulary alone reads it as
    # consent — measured: ``staged_file_action`` returned "approve" and
    # ``_expresses_approval`` also matched, i.e. a user restating the safety
    # rule would have WRITTEN the pending file. The same applies to a
    # CONDITIONAL mention ("قبل از ذخیره تأیید من را بگیر"), which asks for the
    # gate rather than passing through it. Both fail closed.
    _CODE_APPROVAL_BLOCKERS = (
        "بدون تأیید", "بدون تایید", "بدون اجازه", "بدون موافقت",
        "تأیید نکن", "تایید نکن", "تأیید نکردم", "تأیید نمی‌کنم",
        "تأیید نمی کنم", "تأیید نمی‌کنید", "تأیید نمی کنید",
        "ذخیره نکن", "ذخیره نکنید", "ذخیره نشود",
        "اجازه نده", "اجازه ندادم",
        "قبل از ذخیره", "پیش از ذخیره", "قبل از تأیید", "پیش از تأیید",
        "without my approval", "not approved", "do not approve",
        "before saving", "before you save",
    )

    def _code_approval_blocked(self, text):
        """True when the turn withholds approval instead of granting it.

        CODER-05F — the staging store must fail closed here. This is a semantic
        guard only; it grants and consumes nothing.
        """

        if not isinstance(text, str) or not text.strip():

            return False

        lowered = text.lower().replace("\u200c", " ")

        return any(
            marker.replace("\u200c", " ") in lowered
            for marker in self._CODE_APPROVAL_BLOCKERS
        )

    # CODER-05F — the CREATE vocabulary above also contains the SAVE verbs
    # ("ذخیره کن"), because a save turn creates a file. For the purpose of
    # deciding "does this turn ask for NEW SOURCE?", the save verbs must be
    # excluded: "تأیید می‌کنم، فایل app.py را ذخیره کن" is an approval, while
    # "یک برنامه جدید بساز … قبل از ذخیره تأیید من را بگیر" is a generation
    # request whose approval mention is a FUTURE gate, not consent.
    _CODE_SAVE_VERBS = ("ذخیره کن", "ذخیره کنید", "ثبت کن")

    # Built with an explicit loop: a class-body comprehension cannot see the
    # class namespace, so a generator expression here would raise NameError.
    _CODE_SOURCE_REQUEST_ACTIONS = ()

    for _action in (_CODE_CREATE_ACTIONS + _CODE_GENERATION_ACTIONS):

        if _action not in _CODE_SAVE_VERBS:

            _CODE_SOURCE_REQUEST_ACTIONS += (_action,)

    del _action

    def _code_source_request_turn(self, text):
        """True when the turn asks for NEW SOURCE (create OR regenerate).

        CODER-05F — the superset of ``_code_generation_turn``. Requirement: a
        creation request must win over the staging vocabulary even when it says
        «تأیید» / «قبل از ذخیره», because those words describe the gate the user
        wants applied LATER. Save-only turns are excluded by
        ``_CODE_SAVE_VERBS`` so a genuine approval is still an approval.

        The programming classifier is still required, so an architectural
        «یک نسخه جدید بساز» never enters the code path.
        """

        if not isinstance(text, str) or not text.strip():

            return False

        if not any(action in text for action in self._CODE_SOURCE_REQUEST_ACTIONS):

            return False

        try:

            from core.cognition.intent_engine import _programming_request_kind

            return _programming_request_kind(text) == "code_file"

        except Exception:

            return False

    def _authorized_code_syntax_check(self, text, session_id):
        """Validate the SYNTAX of an existing project .py file, or return None."""

        from core.chat.project_code_syntax_checker_v1 import (
            check_project_code_file,
        )

        if not isinstance(text, str):
            return None

        if not any(action in text for action in self._CODE_SYNTAX_ACTIONS):
            return None

        match = self._CODE_FILENAME_RE.search(text)

        if not match:
            return None

        filename = match.group(1)

        if not session_id:
            return (
                "برای بررسی فایل به یک پروژهٔ فعال نیاز است و پروژه‌ای برای این "
                "گفت‌وگو شناسایی نشد؛ بنابراین بررسی انجام نشد."
            )

        outcome = check_project_code_file(
            project_id=session_id,
            filename=filename,
        )

        print(
            "🧪 SYNTAX CHECK:",
            filename,
            "->",
            outcome.get("status"),
            outcome.get("reason"),
        )

        if outcome.get("syntax_valid"):
            return (
                "بررسی نحوی فایل «%s» انجام شد: از نظر نحو (syntax) معتبر است "
                "(Python %s). توجه: این فقط درستی نحو را تأیید می‌کند، نه درستی "
                "رفتار برنامه یا ایمنی آن؛ و من فایل را اجرا نمی‌کنم."
                % (
                    outcome.get("relative_path") or filename,
                    outcome.get("python_version"),
                )
            )

        if outcome.get("status") == "invalid":
            return (
                "بررسی نحوی فایل «%s» انجام شد: خطای نحو یافت شد.\n"
                "خط: %s | ستون: %s\nپیام: %s\n"
                "توجه: من فایل را تغییر نمی‌دهم و آن را اجرا نمی‌کنم."
                % (
                    outcome.get("relative_path") or filename,
                    outcome.get("line"),
                    outcome.get("column"),
                    outcome.get("message"),
                )
            )

        return (
            "بررسی نحوی انجام نشد (%s)؛ هیچ تغییری در فایل داده نشد."
            % (outcome.get("reason") or "unknown")
        )

    def _code_from_conversation_history(self, session_id):
        """The most recent fenced Python block in THIS project's history."""

        from core.chat.project_code_file_writer_v1 import extract_python_code

        try:

            from core.project.conversation_store_v1 import conversation_store

            state = conversation_store.load(session_id) or {}

            for message in reversed(state.get("messages") or []):

                if not isinstance(message, dict):
                    continue

                if message.get("role") != "assistant":
                    continue

                code = extract_python_code(message.get("text") or "")

                if code:
                    return code

        except Exception:
            return None

        return None

    def _generate_code_with_coder(self, text):
        """Ask the coding model for a fresh implementation, or return None."""

        from core.chat.project_code_file_writer_v1 import extract_python_code

        try:

            gateway = coder_gateway()

            prompt = (
                "Write ONLY the complete Python source code for the request "
                "below. Reply with a single ```python fenced block and nothing "
                "else.\n\n"
                # CHAT_CODER_NO_SELF_HASH_V1 — measured 2026-10-26 on the live
                # draft in project_20f920b5: the user asked «فقط پیش‌نویس کد را
                # با SHA-256 نمایش بده» and the model answered with an
                # `import hashlib`, a 20-line `source_code` string literal that
                # duplicated the whole file, and a module-level
                # `print(hashlib.sha256(...))`. ArchitectOS already computes and
                # displays the digest during staging, and a self-referential
                # literal makes the file impossible to repair without touching
                # module-level code.
                "ArchitectOS computes and displays the file's SHA-256 during "
                "staging. If the request asks the application to show a "
                "digest, compute it from the file at runtime; do NOT embed a "
                "second copy of the source code in a string literal and do "
                "not print a hash at import time.\n\n" + str(text)
            )

            raw = gateway.generate(prompt)

            return extract_python_code(raw or "")

        except Exception as error:

            print(
                "⚠️ CODER MODEL UNAVAILABLE:",
                type(error).__name__,
                error,
            )

            return None

    def _source_code_from_history_or_coder(
        self,
        text,
        session_id,
        filename
    ):
        """(code, origin) — model for creation, history only when asked.

        CODER-05C — the order here is load-bearing. The previous version
        scanned conversation history FIRST and returned the first fenced block
        it found, so a request to build a NEW application was answered with the
        previous application's bytes under ``origin="conversation_history"``,
        and the coding model was never invoked. The user saw a proposal that
        looked freshly generated but contained stale source.

        History is a legitimate source only for an EXPLICIT save/reuse turn.
        A build/regenerate turn always reaches the model, and a model failure is
        reported as a failure — never back-filled with older bytes.
        """

        lowered = str(text or "").lower().replace("\u200c", " ")

        # CODER-HISTORY-REUSE-01 — a PROHIBITION outranks the vocabulary.
        # «کد جدید تولید نکن» contains "جدید" (a new-app marker) while
        # explicitly forbidding generation, so the substring alone classified a
        # restore turn as a generation turn and called the coding model.
        prohibited = self._code_generation_prohibited(text)

        # CODER-05F — a GENERATION verb outranks the reuse vocabulary. Without
        # it «کد قبلی را دوباره تولید کن» matched "کد قبلی" and was answered
        # from history, which is the CODER-05C defect reappearing through a
        # different wording. History is never a substitute for generation.
        wants_new = (not prohibited) and any(
            marker in lowered
            for marker in (
                self._CODE_NEW_APP_ACTIONS + self._CODE_GENERATION_ACTIONS
            )
        )

        # CODER-HISTORY-REUSE-01 — the predicate is the authoritative test for
        # "bring back the source we already showed". The marker list below is
        # Persian-heavy and does not cover "restore the previous app.py code",
        # so a genuine English restore turn fell through to the prohibition
        # branch and reported an empty history.
        wants_reuse = (
            any(marker in lowered for marker in self._CODE_REUSE_SOURCE_ACTIONS)
            or self._code_history_reuse_turn(text)
        )

        if wants_reuse and not wants_new:

            code = self._code_from_conversation_history(session_id)

            if code:
                return code, "conversation_history"

            # An explicit reuse turn with nothing to reuse must not borrow a
            # model generation either; the caller reports the truth.
            return None, None

        if prohibited:

            # Fresh generation is forbidden and nothing was asked to be reused.
            # Calling the model here would disobey the user's instruction.
            return None, None

        code = self._generate_code_with_coder(text)

        if code:
            return code, "coder_model"

        # No silent substitution: the caller turns this into a truthful
        # "no reliable code was produced" reply.
        return None, None

    def _authorized_code_file_creation(self, text, session_id, raw_text=None):
        """Create a project .py file for an EXPLICIT request, or return None."""

        from core.chat.project_code_file_writer_v1 import (
            create_project_code_file,
            extract_python_code,
        )

        if not isinstance(text, str):
            return None

        _auth_present = isinstance(getattr(self, "context", None), dict) and (
            "trusted_local_authorization" in self.context
        )
        _authorization = (
            self.context.get("trusted_local_authorization") if _auth_present else None
        )

        # An explicit CREATE action must be present; execution alone never
        # creates a file.
        #
        # CODER-05F — a GENERATION turn ("تولید کن", "نسخه جدید", "اصلاح کن")
        # also asks for FRESH source and must reach the coding model. Without
        # this branch the 05F gate opened correctly but the turn dead-ended
        # here, because the measured request in project_f043688f says
        # «یک نسخه جدید و کامل تولید کن» and carries none of the save verbs
        # above — the coder was never called and the user saw a generic
        # capability refusal instead of a staged proposal.
        #
        # ``_code_source_request_turn`` additionally requires the existing
        # programming classifier to return ``code_file``, so an architectural
        # «نسخه جدید بده» still returns None here.
        #
        # CODER-HISTORY-REUSE-01 — a RESTORE turn carries no creation or
        # generation verb ("بازیابی کن", "از تاریخچه"), so it dead-ended here
        # as well. It is admitted by its own predicate, which requires both a
        # restore action and a code-source reference; the source itself still
        # comes from ``_source_code_from_history_or_coder`` and is never
        # regenerated when the user forbade it.
        if not any(action in text for action in self._CODE_CREATE_ACTIONS):

            if not self._code_source_request_turn(text):

                if not self._code_history_reuse_turn(text):

                    return None

        if _auth_present and not (
            isinstance(_authorization, dict)
            and _authorization.get("trusted") is True
            and _authorization.get("project_id") == session_id
        ):
            return (
                "برای ساخت فایل به یک نشست محلی مورد اعتماد نیاز است و این "
                "درخواست آن را نداشت؛ بنابراین هیچ مدلی فراخوانی نشد و هیچ "
                "فایلی نوشته نشد. برای ادامه، ArchitectOS را از لینک راه‌اندازی "
                "محلی (local-bootstrap) که پنجرهٔ راه‌انداز نمایش می‌دهد دوباره "
                "باز کنید و سپس همین درخواست را تکرار کنید."
            )

        match = self._CODE_FILENAME_RE.search(text)

        if match:
            filename = match.group(1)
        else:
            # CHAT_APP_CREATION_ROUTING_V1 — an application request rarely names
            # a file. Without this the turn dead-ended on a missing filename and
            # the coding model was never reached. Only an actual app-creation
            # request may use the default; anything else still returns None.
            from core.cognition.intent_engine import app_creation_request

            if not app_creation_request(text):
                return None

            filename = self.DEFAULT_APP_FILENAME

        if not session_id:
            return (
                "برای ساخت فایل به یک پروژهٔ فعال نیاز است و پروژه‌ای برای این "
                "گفت‌وگو شناسایی نشد؛ بنابراین هیچ فایلی ساخته نشد."
            )

        # A proposal already awaiting approval must not be silently replaced —
        # including by an approval turn, whose wording also carries a save verb.
        #
        # CODER-05F — this conflict check runs BEFORE the model call. A new
        # generation request in a project that still holds an unconsumed
        # proposal is refused either way, but resolving it first avoids a full
        # inference (tens of seconds) whose result would be discarded.
        from core.chat.code_file_staging_v1 import pending_proposal

        _pending = pending_proposal(session_id)

        if isinstance(_pending, dict):
            return (
                "یک پیش‌نویس برای فایل «%s» در انتظار تأیید شماست و هنوز "
                "نوشته نشده است. لطفاً نخست همان را تأیید یا رد کنید."
                % _pending.get("filename")
            )

        source = extract_python_code(text)

        origin = "current_turn"

        if not source:
            source, origin = self._source_code_from_history_or_coder(
                text, session_id, filename
            )

        if not source:

            # CODER-HISTORY-REUSE-01 — a restore turn that found nothing must
            # say exactly that. The generic "produce the code first" advice
            # would be wrong: the user forbade generation.
            if self._code_history_reuse_turn(text):

                return (
                    "در تاریخچهٔ همین پروژه کد پایتونی پیدا نشد که بتوانم بدون "
                    "تغییر بازیابی کنم؛ بنابراین هیچ مدلی فراخوانی نشد و هیچ "
                    "فایلی نوشته نشد."
                )

            return (
                "کد کامل و قابل اتکایی برای نوشتن در فایل پیدا نشد؛ برای "
                "جلوگیری از ساخت یک فایل ناقص، هیچ فایلی ایجاد نشد. لطفاً "
                "نخست کد را در گفت‌وگو تولید کنید و سپس درخواست ساخت فایل بدهید."
            )

        # CODER-05B — STAGE the proposal. Nothing is written until the user
        # explicitly approves it in a later turn. The writer's own safety rules
        # are unchanged; this only moves the write behind an approval.
        from core.chat.code_file_staging_v1 import stage_code_file

        # CODER QUALITY GATE (Tier 1) — the user's own enumerated acceptance
        # criteria travel with the proposal as UNVERIFIED requirements. They are
        # echoed, never scored: static review cannot prove behaviour.
        #
        # CODER QUALITY GATE FIX — the boundary receives the NORMALIZED text
        # (``text = payload["text"]``), and normalization collapses whitespace,
        # so numbered acceptance items no longer start a line and extraction
        # silently returned zero. ``raw_text`` preserves the user's original
        # structure; it is used ONLY for this echo, never for routing or
        # authorization.
        from core.chat.code_quality_review_v1 import extract_acceptance_requirements

        _requirements_source = raw_text if isinstance(raw_text, str) and raw_text.strip() else text

        proposal = stage_code_file(
            project_id=session_id,
            filename=filename,
            content=source,
            origin=origin,
            authorization=_authorization,
            requirements=extract_acceptance_requirements(_requirements_source),
        )

        if proposal.get("status") != "awaiting_approval":
            return (
                "پیش‌نویس فایل «%s» ساخته نشد (%s)؛ هیچ فایلی نوشته نشد."
                % (filename, proposal.get("reason") or "unknown")
            )

        print(
            "📝 CODE FILE STAGED (not written):",
            proposal.get("filename"),
            "| digest:",
            (proposal.get("digest") or "")[:12],
            "| origin:",
            origin,
        )

        # CODER QUALITY GATE (Tier 1) — three SEPARATE verdicts in the reply.
        # The previous wording («آماده شد») read as "this application works";
        # it only ever meant "the bytes were staged". Behaviour is NOT_RUN and
        # is stated as such, so a staged draft can never look functionally
        # accepted merely because it parses.
        from core.chat.code_quality_review_v1 import describe_quality

        _quality_lines = "\n".join(describe_quality(proposal.get("quality")))

        if not _quality_lines:
            # Review unavailable — still never imply functional success.
            _quality_lines = (
                "نحو (syntax): معتبر"
                if proposal.get("syntax_valid")
                else "نحو (syntax): نامعتبر — %s"
                % ((proposal.get("syntax_error") or {}).get("message") or "unknown")
            )
            _quality_lines += (
                "\nتأیید عملکردی (functional): اجرا نشده (NOT_RUN)"
            )

        _overwrite_line = (
            "\nتوجه: فایلی با همین نام از قبل وجود دارد؛ برای جایگزینی باید "
            "بازنویسی را نیز صریحاً تأیید کنید."
            if proposal.get("requires_overwrite_confirmation")
            else ""
        )

        return (
            "پیش‌نویس فایل «%(name)s» ساخته شد و هنوز هیچ فایلی نوشته نشده است.\n"
            "مسیر پیشنهادی: %(path)s\n"
            "SHA-256: %(digest)s\n"
            "%(quality)s%(overwrite)s\n\n"
            "پیش‌نمایش:\n```python\n%(preview)s\n```\n\n"
            "توجه: این پیش‌نویس فقط از نظر نحو و چند ایراد ایستای قطعی بررسی "
            "شده است؛ درستی رفتار برنامه تأیید نشده است.\n"
            "برای ذخیره، صریحاً تأیید کنید (مثلاً: «تأیید می‌کنم، فایل %(name)s "
            "را ذخیره کن»). تا آن زمان هیچ فایلی روی دیسک ساخته نمی‌شود."
            % {
                "name": proposal.get("filename"),
                "path": "documents/code/%s" % proposal.get("filename"),
                "digest": proposal.get("digest"),
                "quality": _quality_lines,
                "overwrite": _overwrite_line,
                "preview": proposal.get("preview"),
            }
        )

    def _existing_draft_reference(self, text):
        """True when a draft word names the EXISTING proposal, not a future one.

        CODER-CREATE-VS-REPAIR-01 — «فقط پیش‌نویس را بساز» and «در پیش‌نویس فعلی
        اصلاح کن» both contain the word «پیش‌نویس», and the word alone cannot
        tell them apart. The first describes the OUTPUT to be produced; the
        second points at a draft that already exists.

        A draft word therefore only counts when an existence marker sits in a
        bounded window around it, which is an ACTION + TARGET test rather than
        a bag-of-words test.
        """

        lowered = text.lower().replace("\u200c", " ")

        before = 48
        after = 32

        for word in self._CODE_DRAFT_WORDS:

            needle = word.replace("\u200c", " ")

            start = 0

            while True:

                index = lowered.find(needle, start)

                if index < 0:

                    break

                window = lowered[
                    max(0, index - before): index + len(needle) + after
                ]

                if any(
                    marker.replace("\u200c", " ") in window
                    for marker in self._CODE_EXISTING_TARGET_MARKERS
                ):

                    return True

                start = index + len(needle)

        return False

    def _code_repair_turn(self, text):
        """True when the turn asks to repair the CURRENT pending draft ONLY.

        CODER-REPAIR-01 — this is a conjunction on purpose. Each part is
        necessary and none is sufficient:

        * a repair VERB ("اصلاح کن", "fix") — never a bare noun,
        * a reference to the EXISTING pending draft ("پیش‌نویس فعلی", "the
          current draft"), proven by proximity, not by the word alone,
        * the user's own scope restriction ("فقط", "بقیه را تغییر نده"),
        * and NO whole-artifact or new-artifact vocabulary ("نسخه جدید",
          "تولید کن", "بساز").

        Measured 2026-10-26: the real request in project_f043688f message 22
        satisfies the first three and is still a request for a complete new
        version; the request in project_aff545c4 is a CREATE whose
        specification says «عمداً یک باگ قرار بده» and «فقط پیش‌نویس را بساز».
        Both are generation, and both must stay out of this branch.

        This predicate decides only WHETHER the repair branch may run. Scope,
        digest and authority are enforced server-side by
        ``replace_staged_file`` / ``infer_changed_scope``.
        """

        if not isinstance(text, str) or not text.strip():

            return False

        lowered = text.lower().replace("\u200c", " ")

        def _has(markers):

            return any(
                marker.replace("\u200c", " ") in lowered for marker in markers
            )

        # Producing a NEW artifact outranks incidental defect vocabulary.
        if _has(self._CODE_FULL_GENERATION_SIGNALS):

            return False

        if _has(self._CODE_NEW_ARTIFACT_ACTIONS):

            return False

        if not _has(self._CODE_REPAIR_ACTIONS):

            return False

        # The target must be the EXISTING draft, not a draft yet to be built.
        if not self._existing_draft_reference(text):

            return False

        return _has(self._CODE_REPAIR_SCOPE_RESTRICTIONS)

    def _code_generation_prohibited(self, text):
        """True when the turn FORBIDS fresh generation.

        CODER-HISTORY-REUSE-01 — «کد جدید تولید نکن» is a prohibition. The old
        reuse decision read the substring "جدید" as proof of fresh generation
        and therefore called the coding model on a turn that explicitly told it
        not to. A negated verb is the opposite of a request.
        """

        if not isinstance(text, str) or not text.strip():

            return False

        lowered = text.lower().replace("\u200c", " ")

        return any(
            marker.replace("\u200c", " ") in lowered
            for marker in self._CODE_GENERATION_PROHIBITIONS
        )

    def _code_history_reuse_turn(self, text):
        """True when the turn asks to RESTORE source already shown in this project.

        CODER-HISTORY-REUSE-01 — measured 2026-10-26 in project_20f920b5: the
        user asked to bring back the app.py draft already displayed in the
        conversation, and ArchitectOS answered ``no_images_in_session`` because
        the text-only image-reference boundary only skipped creation turns.

        The predicate is a CONJUNCTION:

        * an explicit restore/history action ("بازیابی کن", "از تاریخچه",
          "restore", "reuse"), AND
        * a reference to CODE ITSELF (a ``.py`` filename or "همان کد"/"previous
          code"), AND
        * no POSITIVE whole-artifact request — a genuine "give me a new
          version" still outranks reuse, AND
        * no image vocabulary: "تصویر قبلی" / "previous render" share the word
          "قبلی" and must keep going to the image resolver.

        This authorises nothing. Staging, authorization and the pending-proposal
        guard remain with ``_authorized_code_file_creation``.
        """

        if not isinstance(text, str) or not text.strip():

            return False

        lowered = text.lower().replace("\u200c", " ")

        def _has(markers):

            return any(
                marker.replace("\u200c", " ") in lowered for marker in markers
            )

        if _has(self._CODE_HISTORY_REUSE_ACTIONS) is False:

            return False

        # A code SOURCE reference is required: "the previous render" is not it.
        if not (
            self._CODE_FILENAME_RE.search(text)
            or _has(self._CODE_HISTORY_SOURCE_REFERENCES)
        ):

            return False

        # A genuinely positive whole-artifact request wins over reuse.
        if _has(self._CODE_FULL_GENERATION_SIGNALS) and not self._code_generation_prohibited(
            text
        ):

            return False

        return True

    def _code_repair_prompt(self, text, base, target):
        """The narrow repair instruction sent to the EXISTING coder gateway.

        The exact base bytes and the base digest travel with the request so the
        model edits the draft that is actually pending. The scope rules are
        stated as hard constraints, but they are ENFORCED server-side by
        ``infer_changed_scope`` — a model that ignores them cannot widen its
        own authority, it only produces a candidate that is rejected.
        """

        target_line = (
            "Target function/method: %s" % target
            if target
            else "Target function/method: the ONE function or method that "
            "implements the failed behaviour. Change nothing else."
        )

        # CODER-REPAIR-01B — state the bounded handoff instead of implying it.
        # When the target is named the server takes ONLY that method's body
        # from the answer, so asking the model to reproduce the rest of the
        # file byte-exactly is wasted work that it usually fails (the live
        # draft embedded a copy of itself in a string literal).
        scope_note = (
            "Only this method's BODY is taken from your answer. Every other "
            "byte of the file is taken from the existing draft, so do not "
            "rewrite unrelated code, imports, module-level statements or any "
            "embedded copy of the source.\n\n"
            if target
            else ""
        )

        return (
            "You are repairing ONE existing Python file. Return the COMPLETE "
            "corrected file in a single ```python fenced block.\n\n"
            "BASE SHA-256: %(digest)s\n%(target)s\n%(scope_note)s"
            "HARD SCOPE RULES (a candidate that breaks any of them is rejected "
            "by the server and the user's draft is left unchanged):\n"
            "1. Change EXACTLY ONE function or method body — the one that "
            "implements the failed behaviour.\n"
            "2. Do not change imports.\n"
            "3. Do not change any other function or method.\n"
            "4. Do not change module-level code, class structure or class "
            "attributes.\n"
            "5. Do not change the GUI layout, widget names, or unrelated "
            "keyboard/event handlers.\n"
            "6. Do not reformat, rename or reorder anything outside the "
            "target.\n"
            "7. An unchanged file is a failure, not a success.\n\n"
            "FAILED BEHAVIOUR (source: %(source)s):\n%(request)s\n\n"
            "The file is functionally unverified. Do not claim it works.\n\n"
            "BASE SOURCE:\n```python\n%(source_code)s\n```\n"
            % {
                "digest": base.get("digest"),
                "target": target_line,
                "scope_note": scope_note,
                "source": base.get("failure_source") or "user_reported",
                "request": text,
                "source_code": base.get("content"),
            }
        )

    def _authorized_code_repair(self, text, session_id):
        """Repair the PENDING draft inside one server-enforced scope, or None.

        CODER-REPAIR-01 — every authority decision belongs to the staging owner
        (``repair_base`` / ``replace_staged_file``). This method only builds the
        repair request, calls the EXISTING coder gateway and reports the
        outcome. It never saves, executes, packages or consumes a consent
        token, and it never grants execution or packaging authority.
        """

        if not self._code_repair_turn(text):

            return None

        from core.chat.code_file_staging_v1 import (
            repair_base,
            replace_staged_file,
            resolve_named_targets,
        )

        _auth_present = isinstance(getattr(self, "context", None), dict) and (
            "trusted_local_authorization" in self.context
        )
        _authorization = (
            self.context.get("trusted_local_authorization") if _auth_present else None
        )

        if not (
            isinstance(_authorization, dict)
            and _authorization.get("trusted") is True
            and _authorization.get("project_id") == session_id
        ):
            return (
                "برای اصلاح پیش‌نویس به یک نشست محلی مورد اعتماد نیاز است و این "
                "درخواست آن را نداشت؛ بنابراین هیچ مدلی فراخوانی نشد و پیش‌نویس "
                "دست‌نخورده ماند."
            )

        if not session_id:
            return (
                "برای اصلاح پیش‌نویس به یک پروژهٔ فعال نیاز است؛ هیچ تغییری "
                "انجام نشد."
            )

        base = repair_base(session_id, _authorization)

        if not base.get("ok"):
            return (
                "هیچ پیش‌نویس قابل اصلاحی در انتظار نیست (%s)؛ هیچ فایلی نوشته "
                "نشد و هیچ مدلی فراخوانی نشد."
                % (base.get("reason") or "unknown")
            )

        # The scope may only be NARROWED by the turn. A turn that names two
        # different functions has no unambiguous scope, so it is refused rather
        # than guessed.
        named = resolve_named_targets(base.get("content") or "", text)

        if len(named) > 1:
            return (
                "در این پیام بیش از یک تابع نام برده شده است (%s)؛ دامنهٔ اصلاح "
                "مبهم است، بنابراین هیچ تغییری انجام نشد. لطفاً فقط یک تابع یا "
                "متد را مشخص کنید."
                % "، ".join(named)
            )

        target = named[0] if named else None

        candidate = self._generate_code_with_coder(
            self._code_repair_prompt(text, base, target)
        )

        if not candidate:
            return (
                "مدل کد اصلاح‌شده و قابل اتکایی برنگرداند؛ پیش‌نویس پیشین "
                "دست‌نخورده ماند و هیچ فایلی نوشته نشد."
            )

        # CODER-REPAIR-01B — BOUNDED HANDOFF for an explicitly named target.
        #
        # The model answers with a WHOLE FILE, so it must reproduce every byte
        # of the draft to survive the scope check. The live draft of
        # 2026-10-26 embedded a copy of itself in a `source_code` literal, so
        # any drift in that literal is outside every function span and the
        # honest verdict became `source_outside_scope_changed` — the user's
        # repair could never land.
        #
        # When the user NAMED the target, only that method's body is taken from
        # the model; every other byte comes from the authoritative base. The
        # splice still runs the full scope + signature + static validation
        # afterwards, and it REPORTS how much of the model's output it left out.
        _splice = None

        if target:

            from core.chat.code_file_staging_v1 import splice_target_body

            _splice = splice_target_body(
                base.get("content") or "", target, candidate
            )

            if not _splice.get("ok"):

                print(
                    "⛔ CODE DRAFT REPAIR SPLICE REJECTED:",
                    target,
                    "| reason:", _splice.get("reason"),
                )
                return (
                    "اصلاح پیش‌نویس پذیرفته نشد (%s)؛ پیش‌نویس پیشین دست‌نخورده "
                    "ماند و هیچ فایلی نوشته نشد."
                    % (_splice.get("reason") or "unknown")
                )

            candidate = _splice["candidate"]

            print(
                "🧩 CODE DRAFT REPAIR SPLICED:",
                target,
                "| body lines:", _splice.get("body_lines_replaced"),
                "| model outside-span drift:",
                _splice.get("model_changed_outside_scope"),
                _splice.get("model_outside_diff_lines"),
            )

        outcome = replace_staged_file(
            project_id=session_id,
            candidate=candidate,
            expected_base_digest=base.get("digest"),
            expected_revision=base.get("revision"),
            authorization=_authorization,
            origin="coder_repair",
            repair={
                "target": target,
                "user_request": text,
                "failure_source": base.get("failure_source"),
                "representation": "spliced_body" if _splice else "whole_file",
                "model_changed_outside_scope": bool(
                    _splice and _splice.get("model_changed_outside_scope")
                ),
                "model_outside_diff_lines": int(
                    (_splice or {}).get("model_outside_diff_lines") or 0
                ),
            },
            requirements=base.get("requirements"),
        )

        if outcome.get("status") != "replaced":
            print(
                "⛔ CODE DRAFT REPAIR REJECTED:",
                outcome.get("filename"),
                "| reason:", outcome.get("reason"),
                "| scope:", outcome.get("scope"),
            )
            return (
                "اصلاح پیش‌نویس پذیرفته نشد (%s)؛ پیش‌نویس پیشین دست‌نخورده ماند "
                "و هیچ فایلی نوشته نشد."
                % (outcome.get("reason") or "unknown")
            )

        print(
            "🔧 CODE DRAFT REPAIRED (not written):",
            outcome.get("filename"),
            "| base:", (outcome.get("base_digest") or "")[:12],
            "->", (outcome.get("digest") or "")[:12],
            "| scope:", outcome.get("scope"),
        )

        proposal = outcome.get("proposal") or {}

        from core.chat.code_quality_review_v1 import describe_quality

        _quality_lines = "\n".join(describe_quality(proposal.get("quality")))

        # Transparency, not silence: the bounded handoff keeps the base bytes
        # outside the span, so anything the model wanted to change out there
        # was NOT applied and the user is told.
        _splice_note = ""

        if _splice and _splice.get("model_changed_outside_scope"):

            _splice_note = (
                "\nتوجه: پاسخ مدل بیرون از متد مجاز هم تغییراتی داشت (%d خط)؛ "
                "آن تغییرات اعمال نشد و بقیهٔ فایل عیناً از پیش‌نویس پیشین "
                "گرفته شده است.\n"
                % int(_splice.get("model_outside_diff_lines") or 0)
            )

        return (
            "پیش‌نویس فایل «%(name)s» اصلاح شد و هنوز هیچ فایلی نوشته نشده است.\n"
            "دامنهٔ اصلاح: %(scope)s — فقط همین تابع/متد تغییر کرده است.\n"
            "SHA-256 پیشین: %(base)s\nSHA-256 جدید: %(digest)s\n"
            "%(quality)s\n%(splice)s\n"
            "تفاوت پیش‌نویس پیشین و اصلاح‌شده:\n```diff\n%(diff)s\n```\n\n"
            "توجه: این پیش‌نویس فقط از نظر نحو و دامنهٔ تغییر بررسی شده است؛ "
            "درستی رفتار برنامه تأیید نشده است. تأیید ذخیرهٔ پیشین باطل شده است؛ "
            "برای ذخیره باید دوباره و صریحاً تأیید کنید. اجرا و بسته‌بندی نیز به "
            "اجازهٔ جداگانه نیاز دارد."
            % {
                "name": proposal.get("filename"),
                "scope": outcome.get("scope"),
                "base": outcome.get("base_digest"),
                "digest": outcome.get("digest"),
                "quality": _quality_lines,
                "splice": _splice_note,
                "diff": outcome.get("base_diff"),
            }
        )

    #: Explicit overwrite vocabulary for a staged replacement.
    _CODE_OVERWRITE_ACTIONS = (
        "بازنویسی", "جایگزین", "overwrite", "replace the file", "replace it",
    )

    def _staging_action_turn(self, text):
        """True when the turn is an explicit approve/reject of a staged file.

        CODER-05D — the staging store is SERVER-SIDE authority. An utterance
        that only says "رد کن" / "تأیید میکنم" carries no code, no design and
        no architectural subject, so the intent router classifies it
        ``subject:general`` → ``chat/conversation``. That classification must
        not be allowed to decide the fate of a pending proposal: on 2026-10-25
        "رد کن" was routed to the general model, which answered
        «باشه، رد شد.» while the proposal stayed pending — a generic chat
        acknowledgment impersonating a successful staging rejection.

        This predicate is the dispatch gate. It answers only "is this an
        explicit approve/reject action?"; every authorization, binding and
        capability decision still belongs to ``_authorized_code_file_approval``
        and the staging owner.

        CODER-05F — a turn that asks for NEW source is a GENERATION turn, never
        a staging action, even when it mentions approval as a future gate
        ("قبل از ذخیرهٔ فایل تأیید من را بگیر"). The staging vocabulary matches
        "تأیید" anywhere, so without this precedence the approval handler
        intercepted the request and answered "no pending proposal", and the
        coder was never called.
        """

        if self._code_source_request_turn(text):

            return False

        from core.chat.code_file_staging_v1 import staged_file_action

        return staged_file_action(text) in ("approve", "reject")

    def _code_generation_turn(self, text):
        """True when the turn asks the model to PRODUCE new source.

        CODER-05F — measured 2026-10-25 in project_f043688f: after a rejection,
        the user asked «یک نسخه جدید و کامل تولید کن … قبل از ذخیرهٔ فایل
        تأیید جداگانهٔ من را بگیر». ``_programming_request_kind`` said
        ``code_file`` and the router said ``code/capability``, but
        ``staged_file_action`` returned **"approve"** because the text contains
        "تأیید" and none of the old creation markers — so the approval handler
        answered «هیچ پیشنویسی در انتظار…» in 18 ms and the coder was never
        called.

        Requiring an explicit generation verb plus a code-file classification
        separates "make me a new version" from "save the version you made".
        """

        if not isinstance(text, str) or not text.strip():

            return False

        if not any(action in text for action in self._CODE_GENERATION_ACTIONS):

            return False

        try:

            from core.cognition.intent_engine import _programming_request_kind

            return _programming_request_kind(text) == "code_file"

        except Exception:

            return False

    def _code_file_creation_turn(self, text):
        """True when the turn explicitly asks to CREATE or REGENERATE a code file.

        CODER-05E — the intent router can classify a long, prose-heavy app
        request as ordinary conversation even though the programming
        classifier already returns ``code_file`` for it. Measured 2026-10-25 in
        project_f043688f: a 1 659-character calculator request routed to
        ``{'intent': 'chat', 'mode': 'conversation'}`` and the GENERAL chat
        model answered with prose plus an unverified, truncated code block —
        no staging, no digest, no syntax report — while a 287-character request
        for the same thing routed to the code capability boundary correctly.

        The turn must carry an explicit create verb AND be classified as a
        code-file request by the existing programming classifier. An ordinary
        question that merely mentions a ``.py`` file has no create verb and
        therefore stays on the chat route.
        """

        if not isinstance(text, str) or not text.strip():

            return False

        if not any(
            action in text
            for action in (
                self._CODE_CREATE_ACTIONS + self._CODE_GENERATION_ACTIONS
            )
        ):

            return False

        try:

            from core.cognition.intent_engine import _programming_request_kind

            return _programming_request_kind(text) == "code_file"

        except Exception:

            return False

    def _authorized_code_file_approval(self, text, session_id):
        """Write a STAGED file after an explicit user approval, or return None."""

        from core.chat.code_file_staging_v1 import (
            approve_staged_file,
            mentions_approval,
            pending_proposal,
            reject_staged_file,
            staged_file_action,
        )

        if not isinstance(text, str) or not session_id:
            return None

        # CODER-05F — a source request is never an approval. Without this,
        # ``approve_staged_file`` would be called with the turn text and
        # ``_expresses_approval`` would match the word "تأیید", letting a
        # creation request approve — and WRITE — a pending proposal.
        if self._code_source_request_turn(text):
            return None

        # CODER-HISTORY-REUSE-01 — a RESTORE turn is never an approval or a
        # rejection, even though it mentions saving ("... برای ذخیره پیشنهاد
        # بده"). Restoring stages a NEW proposal; it must never consume the
        # approval authority of an existing one.
        if self._code_history_reuse_turn(text):
            return None

        _auth_present = isinstance(getattr(self, "context", None), dict) and (
            "trusted_local_authorization" in self.context
        )
        _authorization = (
            self.context.get("trusted_local_authorization") if _auth_present else None
        )

        action = staged_file_action(text)
        proposal = pending_proposal(session_id)

        # CODER-05F — a turn that WITHHOLDS or conditions approval is never an
        # approval. It is answered truthfully and the proposal is left
        # untouched, so no write and no capability consumption can happen.
        #
        # CODER-STAGING-ACTION-SAFETY-01 — the same answer is owed when the
        # turn TALKS about approval and withholds it ("بدون تأیید من ... ذخیره
        # نکن", "قبل از ذخیره تأیید من را بگیر"). Those turns no longer
        # classify as an approval action at all, so the mention test is what
        # keeps the reply truthful instead of silently routing them elsewhere.
        if self._code_approval_blocked(text) and (
            action == "approve" or mentions_approval(text)
        ):

            if isinstance(proposal, dict):

                return (
                    "این پیام اجازهٔ ذخیره نمی‌دهد؛ پیش‌نویس فایل «%s» "
                    "دست‌نخورده در انتظار تصمیم شماست و هیچ فایلی نوشته نشد."
                    % proposal.get("filename")
                )

            return (
                "این پیام اجازهٔ ذخیره نمی‌دهد؛ هیچ فایلی نوشته نشد و هیچ "
                "پیش‌نویسی هم در انتظار تأیید نیست."
            )

        if action in ("approve", "reject") and _auth_present and not (
            isinstance(_authorization, dict)
            and _authorization.get("trusted") is True
            and _authorization.get("project_id") == session_id
        ):
            return (
                "این درخواست تأیید از نشست محلی مورد اعتماد نیامده است؛ "
                "بنابراین پیش‌نویس دست‌نخورده ماند و هیچ فایلی نوشته نشد."
            )

        if not isinstance(proposal, dict):
            # CODER-05.1 — approval/rejection is a terminal action even after
            # the proposal was consumed. Returning a truthful response here
            # prevents the same filename + save wording from falling through
            # to the creation route and calling the coder again.
            if action in ("approve", "reject"):
                return (
                    "هیچ پیش‌نویس فایل در انتظار تأیید یا رد برای این پروژه "
                    "نیست؛ بنابراین هیچ مدلی فراخوانی نشد و هیچ فایلی نوشته "
                    "یا دوباره آماده نشد."
                )
            return None

        # CODER-STAGING-ACTION-SAFETY-01 — no approval/rejection ACTION was
        # selected, so this turn is not about the staging decision at all.
        # Hand it back to normal routing instead of asking the writer whether it
        # "expresses approval": that call used to answer a verification request
        # with a save-capability error, and before that it REJECTED the draft
        # because «وارد کن» contains «رد کن».
        if action is None:
            return None

        lowered = text.lower()

        # CODER-STAGING-ACTION-SAFETY-01 — ``action`` is the ONE verdict.
        # A second substring test here was how «وارد کن» reached the rejection
        # branch even after the staging classifier had been fixed.
        if action == "reject":

            rejected = reject_staged_file(
                session_id,
                reason="user_rejected",
                authorization=_authorization,
                approval_token=(self.context or {}).get("approval_capability")
                if _auth_present else None,
            )

            print(
                "🗑️ CODE FILE PROPOSAL REJECTED:",
                rejected.get("filename"),
                "| status:", rejected.get("status"),
                "| reason:", rejected.get("reason"),
            )

            # Report the ACTUAL outcome. The staging owner can refuse a
            # rejection (untrusted caller, actor/session mismatch, capability
            # already consumed by an in-flight write). Claiming success in
            # those cases told the user the proposal was gone while it stayed
            # pending — and, because a pending proposal blocks the creation
            # route, that false message was the only feedback they got.
            if rejected.get("status") != "rejected":
                return (
                    "پیش‌نویس فایل «%s» رد نشد (%s)؛ پیش‌نویس همچنان در انتظار "
                    "است و هیچ فایلی نوشته نشد."
                    % (
                        rejected.get("filename"),
                        rejected.get("reason") or "unknown",
                    )
                )

            return (
                "پیش‌نویس فایل «%s» رد شد و هیچ فایلی نوشته نشد."
                % rejected.get("filename")
            )

        overwrite_confirmed = any(
            action in lowered for action in self._CODE_OVERWRITE_ACTIONS
        )

        # approval_source is "user": this text comes from the USER's turn, never
        # from a model reply. The staging owner refuses any other source.
        outcome = approve_staged_file(
            project_id=session_id,
            approval_text=text,
            approval_source="user",
            overwrite_confirmed=overwrite_confirmed,
            authorization=_authorization,
            approval_token=(self.context or {}).get("approval_capability")
            if _auth_present else None,
        )

        if outcome.get("status") == "written" and outcome.get("verified_on_disk"):
            print(
                "📝 CODE FILE WRITTEN AFTER APPROVAL:",
                outcome.get("relative_path"),
                outcome.get("bytes_written"),
                "bytes",
            )
            return (
                "فایل «%s» با تأیید شما ذخیره شد و محتوای آن روی دیسک بازبینی "
                "شد (%d بایت).\nSHA-256: %s\nتوجه: من کد را اجرا نمی‌کنم؛ اجرای "
                "فایل همچنان در دسترس نیست."
                % (
                    outcome.get("relative_path"),
                    outcome.get("bytes_written"),
                    outcome.get("digest"),
                )
            )

        if outcome.get("reason") in (
            "approval_not_expressed",
            "overwrite_confirmation_required",
        ):
            # not an approval turn: keep the proposal pending and say nothing,
            # so the normal chat answer is used.
            return None

        return (
            "ذخیرهٔ فایل انجام نشد (%s)؛ هیچ فایلی نوشته نشد."
            % (outcome.get("reason") or "unknown")
        )

    def _canonical_chat_reply(
        self,
        prompt,
        user_text,
        use_context=False,
        expected_language=None,
        llm=None
    ):
        """The single canonical text-chat reply path.

        build -> LLM -> bounded language guard (correct, not just warn).

        CODER-03 — `llm` optionally supplies a per-call gateway (the
        dedicated coding model). When omitted, the shared chat gateway is
        used exactly as before.
        """

        _gateway = llm or self.llm

        response_text = _gateway.generate(
            prompt,
            use_context=use_context
        )

        # ==================================================
        # OFFLINE_FIRST_V1 — never hand a `None` reply to the user.
        #
        # `LLMGateway.generate()` returns None when the LOCAL ollama
        # service is unreachable (crashed, not started, or still loading
        # a model). Previously that None flowed straight through the
        # response guard into `response.result`, so the assistant showed
        # NOTHING and the UI looked broken. Degrade gracefully instead:
        # a short, truthful message in the reply language, and an explicit
        # machine-readable `degraded` marker on the response.
        #
        # This touches ONLY the text-chat reply path. Routing, teaching,
        # knowledge, STT, dictation and render are unchanged.
        # ==================================================
        _llm_unavailable = (
            response_text is None
            or not str(response_text).strip()
        )

        if _llm_unavailable:

            print(
                "⚠️ LLM UNAVAILABLE — degraded offline-first reply"
            )

            _fallback = self._offline_reply_text(expected_language)

            _input_lang = (
                "persian"
                if any("\u0600" <= ch <= "\u06FF" for ch in str(user_text or ""))
                else "english"
            )

            return {
                "response": _fallback,
                "corrected": False,
                # OFFLINE_FIRST_V1 — same shape as the normal guard result,
                # so BOTH call sites of this method stay safe.
                "validation": {
                    "status": "degraded",
                    "reason": "llm_unavailable",
                    "valid": False,
                    "input_language": _input_lang,
                    "output_language": _input_lang,
                },
                "status": "degraded",
                "degraded": True,
                "degraded_reason": "llm_unavailable",
            }


        correction = response_guard.correct(

            user_text,

            response_text,

            corrector=self._language_corrector,

            # PHASE 08E — Persian-first: when the canonical project /
            # conversation language is known it overrides the raw script
            # of a single message.  None keeps the previous behaviour.
            expected_language=expected_language,

        )


        print(
            "🛡️ RESPONSE GUARD STATUS:",
            correction.get("status")
        )


        return correction


    # ======================================================
    # PHASE 08E — CANONICAL REPLY LANGUAGE FOR THE GUARD
    # ======================================================

    def _expected_guard_language(
        self,
        teaching_turn
    ):
        """Map the resolved conversation language to a guard language.

        PHASE 08E — only a CANONICAL resolution may override the raw
        script of a single message. A `default` fallback or a
        low-trust STT guess must NOT force the reply language, so those
        keep the previous message-script behaviour.
        """

        if not teaching_turn:

            return None

        decision = teaching_turn.get("language_decision") or {}

        if not decision.get("canonical"):

            return None

        language = teaching_turn.get("language")

        if not language:

            return None

        if str(language).lower().startswith("fa"):

            return "persian"

        if str(language).lower().startswith("en"):

            return "english"

        return None


    # ======================================================
    # VISION_IMAGE_REGISTRY_04 — IMAGE TURN HELPERS
    # ======================================================

    def _register_session_image(self, session_key, image):
        """Persist + register an incoming image. Analysis is separate."""

        try:

            if hasattr(image, "save"):

                registration = register_session_upload(
                    session_key,
                    image,
                )

                if registration.get("status") == "ready":

                    return registration.get("record")

                print(
                    "⚠️ IMAGE REGISTRATION FAILED:",
                    registration.get("error")
                )

                return None


            path = (
                image
                if isinstance(image, str)
                else (image or {}).get("path")
            )

            if path:

                return register_session_asset(
                    session_key,
                    path=path,
                    source_type="uploaded",
                )

        except Exception as e:

            print(
                "IMAGE REGISTRATION ERROR:",
                e
            )

        return None


    def _explicit_text_to_image_turn(self, context):
        """Is this turn an explicitly validated NEW IMAGE GENERATION request?

        T2I_ARCHITECTURAL_FEATURE_HANDOFF_V1 — answers ONLY that question, and
        only from a signal the request boundary already validated. It reads the
        same two fields the router itself reads, with the same strict
        normalization, so the guard and the router can never disagree:

          * `routing_source` must be exactly "manual" — this is what
            `render_strategy_controller_v1` writes when the caller selected a
            mode, and what `intent_router` requires before trusting `mode`;
          * `mode` must normalize to "text_to_image" — using the project's ONE
            mode normalizer, never a truthiness test.

        Auto mode is deliberately NOT accepted: in Auto the operation is
        inferred, and an inferred request must keep the existing guard. This
        grants no authority to edit anything — it only prevents a registered
        image from being mistaken for an edit target on a fresh generation.
        """

        if not isinstance(context, dict):

            return False

        routing_source = str(
            context.get("routing_source") or ""
        ).strip().lower()

        if routing_source != "manual":

            return False

        try:

            from core.render.render_strategy_controller_v1 import (
                MODE_TEXT_TO_IMAGE,
                normalize_mode,
            )

            return normalize_mode(context.get("mode")) == MODE_TEXT_TO_IMAGE

        except Exception as e:

            # Fail closed: an unreadable signal is not an explicit T2I turn, so
            # the guard keeps its previous behaviour.
            print("T2I ROUTING SIGNAL ERROR:", e)

            return False


    def _vision_block(
        self,
        record,
        understanding,
        intent,
        reference,
        region
    ):
        """Structured vision provenance attached to the response."""

        record = record or {}
        understanding = understanding or {}

        block = {

            "contract": "ImageTurnV1",

            "provider": understanding.get("provider"),
            "model": understanding.get("model"),

            "image_id": record.get("image_id"),
            "ordinal": record.get("ordinal"),
            "source_type": record.get("source_type"),
            "path": record.get("path"),

            "analysis_status": understanding.get("analysis_status"),
            "image_type": understanding.get("image_type"),
            "confidence": understanding.get("confidence"),

            "observed": understanding.get("observed"),
            "inferred": understanding.get("inferred"),
            "unresolved": understanding.get("unresolved"),
            "architectural_elements": understanding.get("architectural_elements"),
            "text_labels_if_visible": understanding.get("text_labels_if_visible"),

            "safety": understanding.get("safety"),

            "intent": (intent or {}).get("intent"),
            "intent_reason": (intent or {}).get("reason"),

            "reference": reference or {},
            "region_reference": region or {},

        }

        # ARCHITECTURAL_FACADE_ELEMENT_EVIDENCE_V7.1 — grounded facade-element
        # evidence. Added ONLY when real validated evidence is present, so an
        # ordinary image turn keeps its exact previous shape and no empty
        # element collection is ever fabricated. This is transport, not
        # interpretation: nothing here derives a floor count, a material
        # species or a structural function.
        evidence = understanding.get("element_evidence")

        if isinstance(evidence, dict) and (evidence.get("elements") or []):

            block["element_evidence"] = evidence

        return block


    def _finalize_image_turn(
        self,
        result,
        record,
        understanding,
        intent,
        reference,
        region
    ):

        if isinstance(result, dict):

            result["vision"] = self._vision_block(
                record,
                understanding,
                intent,
                reference,
                region,
            )

        return result


    def _answer_observation(
        self,
        text,
        record,
        understanding,
        intent,
        reference,
        region
    ):
        """OBSERVATION ONLY — what is visibly present in the image.

        VISION_OBSERVATION_MODE_SEPARATION_V1. This turn produces NO
        architectural interpretation: no space classification, no
        function, no spatial relations and no design reasoning. The
        observation layer reuses the grounded evidence of the previous
        phase, so it can never resurrect a claim the grounding rejected.

        Read-only: no provider call, no storage write, no render, no
        network.
        """

        from core.vision.vision_observation_mode_v1 import (
            build_observation,
            detect_interpretation_request,
        )

        persian = any("\u0600" <= char <= "\u06FF" for char in (text or ""))

        language = "persian" if persian else "english"

        # W4.2A-8 — the observation layer still answers observation-only.
        # A SEPARATE, hedged interpretation section is attached ONLY when the
        # turn explicitly asked for interpretation (negation-aware), so the
        # observation never silently promotes itself.
        observation = build_observation(
            understanding,
            language="fa" if persian else "en",
            include_interpretation=detect_interpretation_request(text),
        )

        response = {

            "type": "image_observation",

            "engine": "vision+observation_mode",

            "result": observation,
            "observation": observation,

            "status": "success",

            "language": {

                "input_language": language,
                "output_language": language,
                "guard_status": "not_applicable",
                "corrected": False,

            },

        }

        return self._finalize_image_turn(
            response,
            record,
            understanding,
            intent,
            reference,
            region,
        )


    def _answer_about_image(
        self,
        text,
        record,
        understanding,
        intent,
        reference
    ):
        """Answer a question grounded in real visual evidence."""

        region = {}

        if record:

            region = resolve_session_region(
                record.get("session_id"),
                text,
                record.get("image_id"),
                understanding,
            )


        # ==================================================
        # VISION_OBSERVATION_MODE_SEPARATION_V1
        #
        # "فقط عناصر قابل مشاهده تصویر را لیست کن" is answered by the
        # OBSERVATION layer alone: visible evidence, no space
        # classification, no function, no relations, no design reasoning.
        #
        # It is answered BEFORE the interpreter runs, so no interpretation
        # is produced for this turn at all. It consumes the understanding
        # the turn already has: no extra provider call, no render, no
        # network.
        # ==================================================

        if (intent or {}).get("intent") == INTENT_OBSERVE:

            return self._answer_observation(
                text,
                record,
                understanding,
                intent,
                reference,
                region,
            )


        architectural_interpretation = interpret_architectural_vision(
            understanding,
            user_text=text,
        )


        # ==================================================
        # VISION_REPORT_LANGUAGE_01 — KEEP THE LAST INTERPRETATION
        #
        # So "میشه تحلیل عکستو فارسی برام بگی" can RE-RENDER this very
        # analysis in another language instead of being handed to the
        # generic LLM (which invented a discussion of "عکستو فارسی" as an
        # architectural element). Read-only projection, project-scoped.
        # ==================================================

        try:

            from core.vision.vision_analysis_store_v1 import (
                vision_analysis_store,
            )

            vision_analysis_store.save(
                record.get("session_id") if isinstance(record, dict) else None,
                architectural_interpretation,
                source_text=text,
                image_id=(
                    record.get("image_id")
                    if isinstance(record, dict)
                    else None
                ),
            )

        except Exception as error:

            print(
                "VISION ANALYSIS STORE SAVE ERROR:",
                type(error).__name__,
                error,
            )


        response = {

            "type": "image_analysis",

            "engine": "vision+architectural_interpreter",

            "result": architectural_interpretation,

            "architectural_interpretation": architectural_interpretation,

            "status": "success",

            "language": {

                "input_language":
                    "persian" if any("\u0600" <= char <= "\u06FF" for char in text) else "english",

                "output_language":
                    "persian" if any("\u0600" <= char <= "\u06FF" for char in text) else "english",

                "guard_status":
                    "not_applicable",

                "corrected":
                    False,

            },

        }


        return self._finalize_image_turn(
            response,
            record,
            understanding,
            intent,
            reference,
            region,
        )


    def _answer_about_image_pair(
        self,
        text,
        analysis_ab,
        trace=None
    ):
        """DUAL_IMAGE_COMPARISON_V1 — grounded A/B answer, never a render.

        The A/B vision analyses are ALREADY computed by the dual-image
        dispatch. This method only projects them into a reply contract, so a
        two-image comparison returns real architectural observations instead
        of a claim that no images were attached.

        Read-only: no provider call, no render, no state write.
        """

        from core.vision.dual_image_comparison_v1 import (
            build_comparison,
            render_comparison,
        )

        persian = any(
            "\u0600" <= char <= "\u06FF"
            for char in str(text or "")
        )

        language = "fa" if persian else "en"

        comparison = build_comparison(
            analysis_ab,
            user_text=text,
        )

        comparison["language"] = language

        message = render_comparison(
            comparison,
            language=language,
        )

        _status = {
            "compared": "success",
            "partial": "partial",
            "analysis_unavailable": "analysis_unavailable",
        }.get(
            comparison.get("status"),
            "partial",
        )

        response = {

            "type": "image_comparison",

            "engine": "vision+dual_image_comparison",

            "result": comparison,
            "comparison": comparison,

            # The adapter's text surface for this type.
            "message": message,

            "status": _status,

            "language": {
                "input_language": "persian" if persian else "english",
                "output_language": "persian" if persian else "english",
                "guard_status": "not_applicable",
                "corrected": False,
            },

            "render_handoff": trace or {},

        }

        return response


    def _unresolved_reference_response(
        self,
        text,
        reference,
        session_key
    ):
        """Truthful clarification request - never guess an image."""

        count = image_registry.count(session_key)


        message = (
            "به تصویر مشخصی نمیتوانم ارجاع دهم: "
            + str(reference.get("reason"))
            + ". "
            + "در این گفتگو "
            + str(count)
            + " تصویر ثبت شده است. لطفاً شماره یا مشخصات تصویر را بگویید."
        )


        response = {

            "type": "image_reference",

            "engine": "image_registry",

            "result": message,

            "status": "needs_clarification",

            "language": {
                "input_language": "persian",
                "output_language": "persian",
                "guard_status": "not_applicable",
                "corrected": False,
            },

        }


        return self._finalize_image_turn(
            response,
            None,
            {},
            {"intent": INTENT_REFERENCE, "reason": "unresolved_reference"},
            reference,
            {},
        )


    # ======================================================
    # IMAGE_TO_IMAGE_05 — EDIT ROUTING
    #
    # Shared by the image-bearing path and the text-only reference
    # path so both behave identically.
    # ======================================================

    def _photo_warmth_fast_path(self, text, image_record):
        """May the accepted photometric edit run WITHOUT the V8 observation?

        R4_PHOTO_FAST_PATH_CLOSURE_V1. Returns `{"ready": bool, "reason": str}`.

        The accepted photographic warmth edit is a deterministic per-pixel
        operation (`output = clip(round(source * gain))`). It reads the source
        pixels and nothing else: it cannot move a mullion, close a passage or
        invent a fixture, and it consults no architectural understanding. The
        V8 observation it was waiting for could not change its output, so the
        only thing it bought was latency.

        This gate is a PERFORMANCE decision, never an authorisation. It only
        reuses two EXISTING owners:

          * `_photo_warmth_bridge_eligibility()` — the accepted eligibility
            contract: explicit photographic GLOBAL colour-balance warmth, an
            edit rather than a question, and none of geometry / material
            replacement / local recolouring / time-of-day / physical relighting;
          * `_r4_source_authority()` — the selected record must be the one
            registered for the CURRENT session, pointing at the same resolved
            file that exists on disk. A client-supplied path is never trusted.

        Even when this returns ready, `_route_image_edit()` still runs the
        geometry guard and `_route_photometric_warmth()` still runs every
        source and output check. Declining here simply restores the previous
        order exactly.
        """

        evidence = {"contract": "PhotometricFastPathV1", "version": "1.0"}

        def decline(reason):
            return {"ready": False, "reason": reason, "evidence": evidence}

        if not isinstance(image_record, dict) or not image_record.get("image_id"):

            return decline("no_registered_source")

        edit_delta = compile_edit_delta(text, image_edit=True)

        verdict = _photo_warmth_bridge_eligibility(text, edit_delta)

        if not verdict.get("eligible"):

            return decline(verdict.get("reason") or "not_eligible")

        source = _r4_source_authority(image_record)

        if not source.get("valid"):

            return decline("source_image_authority_mismatch")

        # The operation is RGB-only. A source it cannot adjust must keep the
        # full path, so the user receives the existing observation and the
        # existing truthful refusal instead of a silent loss of analysis.
        mode = _photo_warmth_source_mode(source["path"])

        if mode != "RGB":

            return decline("unsupported_source_mode:%s" % mode)

        evidence["image_id"] = source["image_id"]
        evidence["session_id"] = source["session_id"]
        evidence["source_mode"] = mode
        evidence["eligibility"] = verdict.get("reason")

        return {
            "ready": True,
            "reason": _PHOTO_WARMTH_ELIGIBLE_REASON,
            "evidence": evidence,
            "source": source,
            "edit_delta": edit_delta,
        }


    def _route_photometric_warmth(
        self,
        text,
        image_record,
        context,
        eligibility,
        edit_delta,
    ):
        """Execute the ONE accepted non-generative photographic adjustment.

        R4_PHOTO_SAFE_CHAT_BRIDGE_V1. This is NOT a renderer and NOT an
        alternative edit engine: it applies `PRESET_WARM_BLUE_RESTRAINED_V1`
        to the selected source through the existing photometric utility and
        returns the existing image/attachment response contract.

        It never reaches `ImageHandler`, `WorkflowSelector`, `RenderRuntime`,
        ComfyUI, Ollama or the GPU, and it never fabricates a prompt id.
        Every failure returns a truthful refusal with no registry entry and
        no change to the active image.
        """

        source = _r4_source_authority(image_record)

        if not source.get("valid"):

            print(
                "⛔ PHOTO BRIDGE SOURCE REFUSED:",
                source.get("reason"),
            )

            return self._photometric_refusal(
                "source_image_authority_mismatch",
                eligibility,
            )

        root = _photo_warmth_output_root()

        if root is None:

            print("⛔ PHOTO BRIDGE REFUSED: no trusted output root")

            return self._photometric_refusal(
                "trusted_output_root_unavailable",
                eligibility,
            )

        # Application-generated, unpredictable, never caller-supplied.
        filename = "photo_warmth_" + uuid.uuid4().hex + ".png"

        try:

            operation = adjust_file_exclusive(
                source_path=source["path"],
                output_root=root,
                preset=PRESET_WARM_BLUE_RESTRAINED_V1,
                filename=filename,
            )

        except Exception as error:  # noqa: BLE001 - reported as a refusal

            print(
                "⛔ PHOTO BRIDGE OPERATION ERROR:",
                type(error).__name__,
                error,
            )

            operation = {
                "status": "execution_error",
                "error": "%s: %s" % (type(error).__name__, error),
                "output_written": False,
            }

        if operation.get("status") != "ok":

            print(
                "⛔ PHOTO BRIDGE OPERATION FAILED:",
                operation.get("status"),
                operation.get("reason") or operation.get("error") or "",
            )

            return self._photometric_refusal(
                "photometric_operation_failed",
                eligibility,
                operation=operation,
            )

        output_path = operation["output"]["path"]

        attachment = chat_attachment_service.attachment_for_path(
            output_path,
            root_key="architectos_output",
            source="photometric_warmth_adjustment_v1",
            kind="image",
            display_name=os.path.basename(output_path),
            metadata={
                "operation": operation.get("operation"),
                "preset": PRESET_WARM_BLUE_RESTRAINED_V1["name"],
                "generative": False,
                "contract": operation.get("contract"),
            },
        )

        if attachment is None:

            _photo_warmth_remove_output(output_path)

            print("⛔ PHOTO BRIDGE REFUSED: attachment unavailable")

            return self._photometric_refusal(
                "attachment_unavailable",
                eligibility,
                operation=operation,
            )

        # LINEAGE — the derived image is registered against its REAL parent
        # record, under the session the authority check verified. The parent
        # record is never mutated.
        try:

            registered = register_session_asset(
                source["session_id"],
                path=output_path,
                source_type="image_to_image",
                label="photographic warmth adjustment",
                parent_image_id=source["image_id"],
                attachment=attachment,
                make_active=True,
            )

        except Exception as error:  # noqa: BLE001 - reported as a refusal

            print(
                "⛔ PHOTO BRIDGE REGISTRATION ERROR:",
                type(error).__name__,
                error,
            )

            registered = None

        if not isinstance(registered, dict) or not registered.get("image_id"):

            _photo_warmth_remove_output(output_path)

            print("⛔ PHOTO BRIDGE REFUSED: derived registration failed")

            return self._photometric_refusal(
                "derived_registration_failed",
                eligibility,
                operation=operation,
            )

        new_image_id = registered.get("image_id")

        public_attachment = chat_attachment_service.public_attachment(attachment)

        # State is written ONLY after a successful output AND registration.
        try:

            self.state.update({
                "last_route_intent": "image",
                "last_route_mode": "edit",
                "last_model_role": None,
                "last_image_edit_context": {
                    "mask": None,
                    "kontext_edit": False,
                    "preserve_level": None,
                    "architectural_intent": None,
                    "edit_delta": edit_delta,
                    "workflow": "photometric_warmth_blue_restrained_v1",
                    "source_image_id": source["image_id"],
                    "source_session_id": source["session_id"],
                    "source_project_id": source["project_id"],
                },
            })

        except Exception as error:  # noqa: BLE001 - state is not the deliverable

            print(
                "PHOTO BRIDGE STATE UPDATE ERROR:",
                type(error).__name__,
                error,
            )

        print(
            "🖼️ PHOTO BRIDGE APPLIED:",
            PRESET_WARM_BLUE_RESTRAINED_V1["name"],
            "|",
            operation.get("elapsed_seconds"),
            "s | pixels",
            operation.get("transform", {}).get("pixels"),
        )

        return {
            "type": "image",
            "status": "success",
            "engine": "photometric_warmth_adjustment_v1",
            "operation": operation.get("operation"),
            "preset": PRESET_WARM_BLUE_RESTRAINED_V1["name"],
            # Explicitly non-generative: no prompt id exists and none is
            # invented, because no generative engine ran.
            "generative": False,
            "image": {
                "filename": attachment["filename"],
                "url": public_attachment["url"],
                "exists": True,
                "path": output_path,
                "image_id": new_image_id,
            },
            "attachments": [public_attachment],
            "image_id": new_image_id,
            "parent_image_id": source["image_id"],
            "source_image_id": source["image_id"],
            "photometric": {
                "contract": operation.get("contract"),
                "version": operation.get("version"),
                "operation": operation.get("operation"),
                "preset": PRESET_WARM_BLUE_RESTRAINED_V1["name"],
                "source_path": source["path"],
                "source_sha256": operation.get("source", {}).get("sha256_before"),
                "source_sha256_before": operation.get("source", {}).get("sha256_before"),
                "source_sha256_after": operation.get("source", {}).get("sha256_after"),
                "source_unchanged": operation.get("source", {}).get("unchanged"),
                "output_sha256": operation.get("output", {}).get("sha256"),
                "output_bytes": operation.get("output", {}).get("bytes"),
                "pixels": operation.get("transform", {}).get("pixels"),
                "clipped_total": operation.get("transform", {}).get("clipped_total"),
                "spatial_transform": False,
                "resampled": False,
                "pixel_coordinates_preserved": True,
                "elapsed_seconds": operation.get("elapsed_seconds"),
            },
            "photometric_eligibility": eligibility,
            "edit_delta": edit_delta,
            "intent_ownership": {
                "status": "trusted",
                "reason": "photometric_bridge_source_authority_verified",
                "source_image_id": source["image_id"],
                "source_session_id": source["session_id"],
                "source_project_id": source["project_id"],
                "session_fallback_used": False,
            },
            "message": PHOTOMETRIC_WARMTH_CONFIRMATION,
        }


    def _photometric_refusal(self, reason, eligibility, operation=None):
        """A truthful, non-success refusal for the photographic bridge."""

        messages = {
            "source_image_authority_mismatch": (
                "تصویر انتخاب‌شده به نشست و پروژهٔ فعال تعلق ندارد؛ بنابراین "
                "هیچ تنظیم رنگی اجرا نشد و تصویر فعال تغییر نکرد."
            ),
            "trusted_output_root_unavailable": (
                "مسیر خروجی مورد اعتماد در دسترس نیست؛ بنابراین هیچ تنظیمی "
                "اجرا نشد."
            ),
            "photometric_operation_failed": (
                "تنظیم رنگ عکاسی انجام نشد؛ تصویر اصلی و تصویر فعال بدون "
                "تغییر ماندند."
            ),
            "attachment_unavailable": (
                "خروجی ساخته شد اما برای نمایش در رابط کاربری قابل ارائه نبود؛ "
                "بنابراین تصویر جدید ثبت نشد."
            ),
            "derived_registration_failed": (
                "خروجی ساخته شد اما ثبت نشد؛ بنابراین تصویر فعال تغییر نکرد."
            ),
        }

        message = messages.get(
            reason,
            "تنظیم رنگ عکاسی انجام نشد.",
        )

        return {
            "type": "render_blocked",
            "engine": "chat_architect",
            "status": "blocked",
            "reason": reason,
            "message": message,
            "result": message,
            "generative": False,
            "photometric_eligibility": eligibility,
            "photometric_operation": (
                operation if isinstance(operation, dict) else {}
            ),
        }


    def _route_image_edit(
        self,
        text,
        image_record,
        image_reference,
        compiled_render_prompt,
        terminology,
        render_seed,
        context,
        image_understanding=None,
    ):
        """Guard, compile the edit delta, resolve preservation, route.

        IMAGE_TO_IMAGE_05 — PROMPT / DELTA AUTHORITY
        The generic img2img builder prompt is a text-to-image
        facade/DAYLIGHT template. For a classified conversational edit
        the user's own delta is authoritative, so this route:

          1. compiles the deterministic edit delta
             (REFERENCE / DELTA / PRESERVE / QUALITY),
          2. replaces the compiled prompt with it,
          3. hands the delta's conflict terms to the render runtime so
             the generic builder tail cannot contradict the delta
             (e.g. "Natural lighting" on a night edit),
          4. deterministically escalates a facade MATERIAL replacement
             into the approved BALANCED denoise band.

        An unclassified edit keeps the previous behaviour byte for byte.
        """

        context = dict(context or {})

        _state_snapshot = self.state.get() or {}

        _stored_edit_context = _state_snapshot.get("last_image_edit_context")

        _stored_edit_context = (
            _stored_edit_context
            if isinstance(_stored_edit_context, dict)
            else {}
        )

        _bound_resolution = self.image_handler.resolve_source_bound_intent(
            image_record
        )

        _selected_image_id = (
            image_record.get("image_id")
            if isinstance(image_record, dict)
            else None
        )

        _fallback_matches_source = bool(
            _selected_image_id
            and _stored_edit_context.get("source_image_id")
                == _selected_image_id
            and str(_stored_edit_context.get("source_session_id"))
                == str(_bound_resolution.get("session_id"))
            and str(_stored_edit_context.get("source_project_id"))
                == str(_bound_resolution.get("project_id"))
        )

        # A follow-up submitted by a legacy caller does not repeat precision
        # controls.  Restore only the controls that were actually used by the
        # preceding edit AND only when the current request independently reads
        # as a localized edit.  Otherwise a mask from an earlier local edit
        # could silently narrow a later whole-image appearance edit.
        #
        # The existing geometry guard owns the local/global distinction.  Run
        # it without inherited controls first; the restored controls still go
        # through the normal source/digest validation in the authoritative
        # guard below.  A current UI request explicitly supplies the flag and
        # can therefore turn the precise route off.
        _restore_precision_controls = False

        if (
            "precision_controls_supplied" not in context
            and _fallback_matches_source
        ):

            _unbound_followup_guard = detect_unsupported_geometry_edit(
                text,
                context=guard_context_with_source(
                    context,
                    (session_registry.current() or {}).get("session_id"),
                    image_record=image_record,
                ),
            )

            _restore_precision_controls = (
                _unbound_followup_guard.get("reason")
                == "localized_geometry_edit_not_supported"
            )

        if _restore_precision_controls:

            context["precision_controls_supplied"] = True

            if _stored_edit_context.get("mask"):

                context["mask"] = _stored_edit_context.get("mask")

            if _stored_edit_context.get("kontext_edit"):

                context["kontext_edit"] = True

        _previous_architectural_intent = {}

        if _bound_resolution.get("status") == "trusted":

            _previous_architectural_intent = (
                _bound_resolution.get("intent") or {}
            )

        elif (
            _bound_resolution.get("status") == "unknown"
            and _fallback_matches_source
        ):

            _fallback = self.image_handler.sanitize_architectural_intent(
                _stored_edit_context.get("architectural_intent")
            )

            if _fallback.get("status") == "trusted":

                _previous_architectural_intent = (
                    _fallback.get("intent") or {}
                )

        # ----------------------------------------------
        # GUARD — precise geometry edits are NOT supported
        #
        # PRECISE_EDIT_ROUTE_V1 — the guard is given `context` so it can tell a
        # localized request that has a validated masked-Kontext route (which
        # passes) from one that has none (which still refuses, exactly as
        # before). `context` ALREADY carries the restored mask and
        # kontext_edit at this point (see the restore block above), so no
        # second mask source is introduced and no validation is duplicated.
        # ----------------------------------------------

        # MASK_SOURCE_BINDING_V1 — the source identity this turn will edit is
        # added to the guard context, so a mask is accepted only when its
        # server digest re-verifies against THAT image.
        guard = detect_unsupported_geometry_edit(
            text,
            context=guard_context_with_source(
                context,
                (session_registry.current() or {}).get("session_id"),
                image_record=image_record,
            ),
        )

        if guard.get("unsupported"):

            # V8 — a plain removal already deferred by the pre-routing gate
            # must not be re-refused here by the identical detector. The
            # evidence gate downstream fails closed on its own.
            if _v8_defer_removal_to_evidence_gate(text, guard, context):

                print(
                    "✅ V8 EVIDENCE GATE OWNS DEFERRED REMOVAL:",
                    guard.get("reason")
                )

            else:

                print(
                    "⛔ UNSUPPORTED GEOMETRY EDIT:",
                    guard.get("reason")
                )

                return self._unsupported_geometry_response(
                    text,
                    guard,
                    image_record,
                    image_reference,
                )


        # ----------------------------------------------
        # IMAGE_EDIT_ENGINE_INTEGRATION_V1 — CAPABILITY TRANSLATION
        #
        # `compile_edit_delta()` is the existing owner of supported
        # appearance-edit semantics (time of day, lighting, material and
        # colour).  Once the geometry guard and R4 admission below have passed,
        # a classified NON-ARCHITECTURAL edit with no selection mask remains a
        # GLOBAL instruction edit. Translate that existing semantic result into
        # the existing Kontext selector flag at the execution boundary.
        #
        # A supplied mask remains localized.  An explicit Kontext request
        # that is not a classified global appearance edit still needs that
        # mask and is handled by the unchanged precise-edit gate below.
        # ----------------------------------------------

        # KNOWLEDGE_RUNTIME_CONNECTION_V2 — this boundary owns edit execution,
        # so it tells the compiler that the turn IS an edit of the bound
        # source. Without it a recognised architectural style had no edit
        # class. R4 admission now stops architectural style edits before any
        # selector; independently accepted non-architectural edits retain the
        # existing decision below. No new selector is introduced.
        edit_delta = compile_edit_delta(text, image_edit=True)

        # ----------------------------------------------
        # R4_PHOTO_SAFE_CHAT_BRIDGE_V1 — NON-GENERATIVE PHOTOGRAPHIC EDIT
        #
        # R4_PHOTO_02_VISUAL_PASS accepted ONE non-generative capability: a
        # blue-restrained photographic colour warm. This boundary connects it
        # to the real chat route.
        #
        # Placement is deliberate and narrow:
        #   * AFTER the geometry/source guard above, so an unsupported
        #     geometry edit is still refused first;
        #   * AFTER `compile_edit_delta()`, so the existing compiler remains
        #     the single owner of edit semantics and may VETO here;
        #   * BEFORE the R4 generative admission below, which must not be
        #     reached by an accepted photographic adjustment;
        #   * BEFORE the later `context["kontext_edit"] = True` block, which
        #     would otherwise force a generative instruction edit.
        #
        # The R4 admission guard itself is NOT modified, weakened or
        # bypassed: an ineligible request simply continues to it exactly as
        # before. Eligibility fails closed, so every unknown request keeps
        # the pre-existing behaviour byte for byte.
        # ----------------------------------------------

        _photo_eligibility = _photo_warmth_bridge_eligibility(text, edit_delta)

        if _photo_eligibility.get("eligible"):

            return self._route_photometric_warmth(
                text=text,
                image_record=image_record,
                context=context,
                eligibility=_photo_eligibility,
                edit_delta=edit_delta,
            )


        # R4 ARCHITECTURAL EDIT ADMISSION GUARD V1 — accepted visual evidence
        # is a precondition, not prompt wording.  This runs after the existing
        # geometry/source interpretation but BEFORE `kontext_edit` is forced,
        # WorkflowSelector is reached, ImageHandler is called, GPU admission is
        # attempted, or any derived image can be registered.
        # A plain removal explicitly deferred by the V8 pre-route contract
        # already enters ImageHandler's evidence-aware design decision, which
        # blocks before RenderRuntime when spatial targeting is absent. Keep
        # that accepted, more-specific refusal instead of replacing it with a
        # less informative generic capability refusal.
        _r4_refusal = None

        self.last_r4_admission = None

        if not (
            guard.get("unsupported")
            and _v8_defer_removal_to_evidence_gate(text, guard, context)
        ):

            _r4_refusal = _r4_architectural_edit_admission(
                text=text,
                image_record=image_record,
                edit_delta=edit_delta,
                context=context,
                prior_intent=_previous_architectural_intent,
                image_understanding=image_understanding,
            )

            # FACADE_RENDERING_FIRST_I2I_ADMISSION_V1 — the admission that was
            # actually applied, exposed for the caller and for CPU evidence.
            self.last_r4_admission = context.get("r4_admission")

        if _r4_refusal is not None:

            _r4_refusal["intent_ownership"] = {
                "status": _bound_resolution.get("status"),
                "reason": _bound_resolution.get("reason"),
                "source_image_id": _selected_image_id,
                "source_session_id": _bound_resolution.get("session_id"),
                "source_project_id": _bound_resolution.get("project_id"),
                "session_fallback_used": False,
            }

            _r4_refusal["edit_delta"] = edit_delta

            print(
                "⛔ R4 ARCHITECTURAL EDIT ADMISSION BLOCKED:",
                _r4_refusal.get("reason"),
            )

            return _r4_refusal

        _global_appearance_edit = bool(
            is_classified_edit_delta(edit_delta)
            and not context.get("mask")
        )

        if _global_appearance_edit:

            # I2I_CONCEPTUAL_ADMISSION_V1 — a consented conceptual edit is
            # admitted on `flux_img2img.json`, so the Kontext auto-selection
            # must not silently switch the graph underneath the admission.
            # The admission and the executed graph have to be the same thing.
            if not _r4_conceptual_consent(context):

                context["kontext_edit"] = True

            context["edit_scope"] = "global_appearance"


        # ----------------------------------------------
        # KNOWLEDGE_RECOVERY_01 — PRECISE-EDIT MASK GATE
        #
        # The Kontext instruction-edit graph confines its change with a
        # caller-supplied compositing mask. ArchitectOS does not generate,
        # segment or approximate one. A request for the precise route
        # WITHOUT a mask is refused here; it is never silently downgraded
        # to whole-image editing, which would alter protected elements.
        # ----------------------------------------------

        if (
            isinstance(context, dict)
            and context.get("kontext_edit")
            and not context.get("mask")
            and not _global_appearance_edit
        ):

            print(
                "⛔ PRECISE EDIT REFUSED: mask required"
            )

            return {

                "type":
                    "render_blocked",

                "engine":
                    "chat_architect",

                "status":
                    "blocked",

                "reason":
                    "mask_required_for_precise_edit",

                "message": (
                    "این ویرایش نیازمند یک ماسک انتخاب‌شده است. "
                    "ویرایش کل تصویر انجام نشد."
                ),

                "capability_gap": {

                    "missing":
                        "caller_supplied_mask",

                    "detail": (
                        "The Kontext instruction-edit graph preserves "
                        "protected elements only inside a caller-supplied "
                        "compositing mask. No verified automatic "
                        "architectural mask generator is installed, so "
                        "ArchitectOS will not substitute one and will not "
                        "widen the edit to the whole image."
                    ),

                },

            }


        # ----------------------------------------------
        # EDIT DELTA (deterministic, authoritative)
        # ----------------------------------------------

        edit_compiled_prompt = compiled_render_prompt

        edit_conflict_terms = ()

        if is_classified_edit_delta(edit_delta):

            edit_compiled_prompt = edit_delta_prompt(edit_delta)

            edit_conflict_terms = edit_delta_conflict_terms(edit_delta)

            print(
                "🧩 EDIT DELTA:",
                edit_delta.get("edit_class"),
                "| material",
                edit_delta.get("material"),
                "| time_of_day",
                edit_delta.get("time_of_day"),
                "| conflicts",
                list(edit_conflict_terms)
            )


        # ----------------------------------------------
        # FACADE_RENDERING_FIRST_I2I_ADMISSION_V1 — PROMPT HANDOFF
        #
        # A canonical delta clause restates the EDIT CLASS, not the user's
        # design. "Redesign this building in modern Iranian brick with dark
        # metal window frames" compiles to a metal-cladding instruction and
        # loses the brick, the modern language and the frame colour.
        #
        # When the bounded admission produced a preservation contract, the
        # verbatim user request and that contract are placed BEFORE the
        # canonical delta, so neither can be replaced by it.  Without a
        # contract this block is a no-op and the prompt is unchanged.
        # ----------------------------------------------

        _admitted_contract = (
            context.get("r4_preservation_contract")
            if isinstance(context, dict)
            else None
        )

        _r4_admission = (
            context.get("r4_admission")
            if isinstance(context, dict)
            else None
        )

        if (
            isinstance(_admitted_contract, dict)
            or (
                isinstance(_r4_admission, dict)
                and _r4_admission.get("admitted") is True
            )
        ):

            edit_compiled_prompt = _r4_compose_admitted_edit_prompt(
                text,
                _admitted_contract,
                edit_compiled_prompt,
            )

            print(
                "🏛️ R4 PRESERVATION CONTRACT HANDED OFF:",
                (_admitted_contract or {}).get("workflow"),
                "| edit class",
                (_admitted_contract or {}).get("edit_class"),
            )


        # ----------------------------------------------
        # PRESERVATION LEVEL (deterministic)
        #
        # Precedence: explicit request parameter, then the edit-class
        # contract, then deterministic inference from the wording.
        # ----------------------------------------------

        explicit_level = (
            context.get("preserve_level")
            if isinstance(context, dict)
            else None
        )

        delta_level = None

        delta_denoise = None

        if not explicit_level:

            delta_level = edit_delta_preservation_level(edit_delta)

            delta_denoise = edit_delta_denoise_override(edit_delta)

            explicit_level = delta_level

        preservation = resolve_preservation_with_denoise(
            text=text,
            explicit=explicit_level,
            denoise=delta_denoise,
        )

        if not (
            isinstance(context, dict)
            and context.get("preserve_level")
        ):

            if delta_level:

                # The level came from the edit-class contract, not from
                # an explicit request parameter - report it truthfully.
                preservation["source"] = "edit_class_contract"

                preservation["reason"] = "material_replacement_escalation"

            elif delta_denoise is not None:

                preservation["source"] = (
                    str(preservation.get("source", "")) + "+edit_class_strength"
                )

                preservation["reason"] = "time_of_day_strength_escalation"

        print(
            "🎚️ EDIT PRESERVATION:",
            preservation.get("level"),
            "| denoise",
            preservation.get("denoise"),
            "|",
            preservation.get("source")
        )


        source_path = (
            image_record.get("path")
            if isinstance(image_record, dict)
            else None
        )


        result = self.image_handler.handle_image_edit(

            text=text,

            image=(
                {"path": source_path}
                if source_path
                else None
            ),

            compiled_render_prompt=edit_compiled_prompt,

            preservation=preservation,

            seed=render_seed,

            edit_conflict_terms=edit_conflict_terms,

            # PROJECT_WORKSPACE_UI_06 — per-request render profile
            render_profile=(
                context.get("render_profile")
                if isinstance(context, dict)
                else None
            ),

            parent_image_id=(
                image_record.get("image_id")
                if isinstance(image_record, dict)
                else None
            ),

            # KNOWLEDGE_RECOVERY_01 — Kontext instruction edit.
            #
            # `kontext_edit` is an EXPLICIT opt-in. A precise edit needs a
            # caller-supplied mask: the Kontext graph confines its change
            # with a compositing mask, and ArchitectOS does not derive one.
            # Requesting the precise route WITHOUT a mask is refused rather
            # than silently downgraded to whole-image editing.
            mask_asset=(
                context.get("mask")
                if isinstance(context, dict)
                else None
            ),

            kontext_edit=(
                bool(context.get("kontext_edit"))
                if isinstance(context, dict)
                else False
            ),

            previous_architectural_intent=_previous_architectural_intent,

            edit_delta=edit_delta,

            # VISION_STOREY_DISAMBIGUATION_V3 — the API already carries this
            # explicit opt-in.  Preserve it across the edit-specific route so
            # Kontext I2I output reaches the same observer/fidelity gate as
            # Krea and USO output.
            verify_render=(
                context.get("verify_render")
                if isinstance(context, dict)
                else None
            ),

            # ARCHITECTURAL_REASONING_INTEGRATION_V8 — the selected source's
            # validated understanding. This is produced server-side by the
            # existing image-session boundary; client context is never trusted
            # as architectural evidence.
            image_understanding=image_understanding,

            # FINAL_CORRECTED_FACADE_GPU_PREFLIGHT_V1 — trusted provenance for
            # the contract composed above. The structured OBJECT, not the
            # rendered text, so a user request containing the contract header
            # cannot suppress the preservation block.
            r4_preservation_contract=_admitted_contract,

            # CONCEPTUAL_I2I_LIVE_EVIDENCE_ADMISSION_V1 — server-owned R4
            # admission, never a client field.  The downstream evidence
            # decision validates the complete structured envelope before it
            # may authorise an unlocalized whole-image conceptual edit.
            r4_admission=(
                context.get("r4_admission")
                if isinstance(context, dict)
                else None
            ),

        )


        if isinstance(result, dict):

            result["intent_ownership"] = {
                "status": _bound_resolution.get("status"),
                "reason": _bound_resolution.get("reason"),
                "source_image_id": _selected_image_id,
                "source_session_id": _bound_resolution.get("session_id"),
                "source_project_id": _bound_resolution.get("project_id"),
                "session_fallback_used": bool(
                    _bound_resolution.get("status") == "unknown"
                    and _fallback_matches_source
                    and _previous_architectural_intent
                ),
            }

            result["edit_preservation"] = preservation

            # I2I_CONCEPTUAL_ADMISSION_V1 — a consented conceptual edit is
            # reported as such, with its limitation, so a technically
            # successful render is never read as proven architectural
            # fidelity. Absent for every other route.
            _admission = (
                context.get("r4_admission")
                if isinstance(context, dict)
                else None
            )

            if (
                isinstance(_admission, dict)
                and _admission.get("preservation_status")
                == _R4_CONCEPTUAL_PRESERVATION_STATUS
            ):

                result["conceptual_edit"] = _admission.get("conceptual_edit")

                result["architectural_fidelity"] = {
                    "contract": "ArchitecturalFidelityReportV1",
                    "preservation_status": _R4_CONCEPTUAL_PRESERVATION_STATUS,
                    "verified": False,
                    "advisory": True,
                    "notice": (
                        "Geometry preservation is best-effort only; the output "
                        "is conceptual and not construction-accurate."
                    ),
                }

            result["compiled_render_prompt"] = edit_compiled_prompt

            result["edit_delta"] = edit_delta

            # IMAGE_TO_IMAGE_05 — full render metadata (preset suppression,
            # denoise, seed, draft mode, status) for diagnostics.
            try:

                result["render_metadata"] = (
                    self.render_runtime.last_render_metadata or {}
                )

            except Exception:

                result["render_metadata"] = {}

            if result.get("status") not in (
                "error", "blocked", "missing_image", "submit_error",
                "execution_error", "completed_no_image",
            ):

                _effective_architectural_intent = (
                    result.get("architectural_intent")
                    if isinstance(result.get("architectural_intent"), dict)
                    else _previous_architectural_intent
                )

                self.state.update({
                    "last_route_intent": "image",
                    "last_route_mode": "edit",
                    "last_model_role": None,
                    "last_architectural_intent": _effective_architectural_intent,
                    "last_image_edit_context": {
                        "mask": context.get("mask"),
                        "kontext_edit": bool(context.get("kontext_edit")),
                        "preserve_level": context.get("preserve_level"),
                        "architectural_intent": _effective_architectural_intent,
                        "edit_delta": edit_delta,
                        "workflow": result.get("render_metadata", {}).get(
                            "workflow_name"
                        ),
                        "source_image_id": result.get(
                            "source_bound_image_id"
                        ),
                        "source_session_id": result.get(
                            "source_bound_session_id"
                        ),
                        "source_project_id": result.get(
                            "source_bound_project_id"
                        ),
                    },
                })

        return result


    def _router_edit_route(
        self,
        text,
        image,
        context,
        compiled_render_prompt,
        terminology,
        render_seed
    ):
        """Router-level edit entry (state override / mode=edit).

        IMAGE_TO_IMAGE_05: every edit route must pass the precise-geometry
        guard first, otherwise an unsupported geometric request can slip
        through and be executed as an edit.
        """

        bundle = session_registry.current()

        session_key = (bundle or {}).get("session_id")


        record = image_registry.active(session_key)


        # MASK_SOURCE_BINDING_V1 — same source-identity resolution as the other
        # two guard call sites, so all three accept or refuse identically.
        guard = detect_unsupported_geometry_edit(
            text,
            context=guard_context_with_source(
                context,
                session_key,
                image=image,
                image_record=record,
            ),
        )

        if guard.get("unsupported"):

            # V8 — same deferral as the bound-source route. Without this the
            # router-level route re-refuses a removal the pre-routing gate
            # already handed to the evidence-aware decision gate.
            if _v8_defer_removal_to_evidence_gate(text, guard, context):

                print(
                    "✅ V8 EVIDENCE GATE OWNS DEFERRED REMOVAL (router route):",
                    guard.get("reason")
                )

            else:

                print(
                    "⛔ UNSUPPORTED GEOMETRY EDIT (router route):",
                    guard.get("reason")
                )

                return self._unsupported_geometry_response(
                    text,
                    guard,
                    record,
                    {},
                )


        source_path = (
            record.get("path")
            if isinstance(record, dict)
            else None
        )

        if not source_path:

            if isinstance(image, dict):

                source_path = image.get("path")

            elif isinstance(image, str):

                source_path = image


        if not isinstance(record, dict) and source_path:

            record = {"path": source_path}


        if record:

            return self._route_image_edit(
                text,
                record,
                {},
                compiled_render_prompt,
                terminology,
                render_seed,
                context,
            )


        return self.image_handler.handle_image_edit(

            text=text,

            image=image,

            verify_render=(
                context.get("verify_render")
                if isinstance(context, dict)
                else None
            ),

        )


    def _unsupported_geometry_response(
        self,
        text,
        guard,
        image_record,
        image_reference
    ):
        """Truthful refusal - never silently attempt precise geometry."""

        message = (
            "ویرایش هندسی دقیق پشتیبانی نمی‌شود. "
            "جابه‌جایی یا تغییر اندازه اجزا با ابعاد مشخص (مثل «۸۰ سانت ببر راست») "
            "در این نسخه انجام نمی‌شود. "
            "در عوض می‌توانم ظاهر تصویر را تغییر دهم: نور، شب/روز، متریال، رنگ و بافت — "
            "بدون تغییر فرم و هندسه ساختمان."
        )


        response = {

            "type": "image_edit",

            "engine": "image_edit_guard",

            "status": "unsupported_edit",

            "result": message,

            "unsupported_edit": guard,

            "supported_alternatives": [
                "lighting (شب / روز / روشن / تیره)",
                "material (سنگ / چوب / شیشه)",
                "color and tone (رنگ / متریال)",
            ],

            "language": {
                "input_language": "persian",
                "output_language": "persian",
                "guard_status": "not_applicable",
                "corrected": False,
            },

        }


        return self._finalize_image_turn(
            response,
            image_record,
            {},
            {"intent": INTENT_EDIT, "reason": guard.get("reason")},
            image_reference,
            {},
        )


    # ======================================================
    # CHAT_LANGUAGE_02 — RENDER HANDOFF FINALIZER
    # ======================================================

    def _render_fidelity_refusal(
        self,
        render_fidelity,
        render_handoff_trace=None
    ):
        """A non-authorising semantic-fidelity verdict as a `render_blocked` envelope.

        LIVE_RENDER_FIDELITY_HANDOFF_FIX_V1 — the fidelity gate is the
        authoritative pre-submission decision for the turn's architectural
        content. Until this method existed the verdict was computed, printed
        and traced, but ONLY the dual-image A/B readiness flag read
        `may_proceed_to_render`; an ordinary single-image T2I turn therefore
        continued into the render runtime while the gate had already declared
        the instruction CONTRADICTORY.

        SINGLE_T2I_FIDELITY_GATE_ACCEPTANCE_V1 — this method is called at the
        single-image GENERATION dispatch, so a verdict is REQUIRED by the time
        it runs. Every shape that does not explicitly authorise the render is
        a refusal:

        * ``{"may_proceed_to_render": True}`` — proceed (None).
        * a real BLOCKED verdict — refuse (``render_fidelity_blocked``).
        * missing / malformed / non-dict — refuse
          (``render_fidelity_unavailable``). The earlier version let these
          through, which was a bypass: a render turn whose verdict was absent
          reached the executor with no semantic check at all.

        This cannot affect unrelated chat, conversation or non-render routes:
        the only caller is the render dispatch itself.

        The envelope is the SAME proven `render_blocked` shape the existing
        dual-image blocks use, so no adapter, executor or lease path is added.
        """

        verdict = render_fidelity if isinstance(render_fidelity, dict) else None

        if verdict is not None and verdict.get("may_proceed_to_render") is True:

            return None

        if verdict is None or not verdict:

            reason_code = "render_fidelity_unavailable"

            print(
                "⛔ RENDER BLOCKED: semantic fidelity verdict unavailable",
                type(render_fidelity).__name__,
            )

            detail = {
                "contract": "RenderSemanticFidelityV1",
                "status": "BLOCKED",
                "reason_code": reason_code,
                "reason": (
                    "no usable fidelity verdict reached the single-image "
                    "render dispatch; the render fails closed"
                ),
                "may_proceed_to_render": False,
            }

        else:

            # A stable envelope reason: the verdict's own reason_code stays
            # inside `render_fidelity`, so a client can distinguish "the gate
            # refused this instruction" from "the gate could not run".
            reason_code = "render_fidelity_blocked"

            print(
                "⛔ RENDER BLOCKED: semantic fidelity",
                verdict.get("status"),
                "|",
                verdict.get("reason_code"),
            )

            detail = verdict

        return {
            "type": "render_blocked",
            "status": "blocked",
            "reason": reason_code,
            "render_fidelity": detail,
            "message": (
                "دستور معماری با درخواست کاربر در تضاد است؛ رندر پیش از "
                "ارسال به موتور تصویر متوقف شد."
            ),
            "render_handoff": (
                render_handoff_trace
                if isinstance(render_handoff_trace, dict)
                else {}
            ),
        }

    def _finalize_render_handoff(
        self,
        result,
        render_handoff_trace
    ):
        """Attach the proven chat -> render handoff trace."""

        try:

            received = self.render_runtime.last_render_request or {}

            render_handoff_trace["render_runtime_received_prompt"] = (
                received.get("received_prompt")
            )

            render_handoff_trace["render_runtime_received_compiled"] = (
                received.get("compiled_render_prompt")
            )

            render_handoff_trace["render_runtime_final_prompt"] = (
                received.get("resolved_prompt")
            )

            render_handoff_trace["render_prompt_source"] = (
                received.get("prompt_source")
            )

            render_handoff_trace["compiled_consumed"] = (
                received.get("compiled_consumed")
            )

            # TEXT_TO_IMAGE_COMFY_03 — full render request metadata
            render_handoff_trace["render_request_metadata"] = (
                self.render_runtime.last_render_metadata or {}
            )

            # FACADE-04D.3C-5B / .1 — H2 runs INSIDE RenderRuntime.render(),
            # immediately before the ComfyUI submit, so it is the request's
            # LAST model operation and the `gpu_render` lease covers the whole
            # protected rendering period. Merge its trace into the record.
            _h2 = getattr(self.render_runtime, "last_gpu_handoff_h2", None)

            _gpu_trace = render_handoff_trace.get("gpu_handoff")

            if isinstance(_gpu_trace, dict) and _h2 is not None:

                _gpu_trace["h2"] = _h2

            # FACADE-04D.3C-5B.1 — the protected rendering period (the
            # exclusive gpu_render lease) outcome. Carried on the trace because
            # the response adapter rebuilds the envelope and drops a top-level
            # `reason`, so a refused render would otherwise be undiagnosable.
            _render_period = getattr(
                self.render_runtime, "last_gpu_handoff_render", None
            )

            if isinstance(_gpu_trace, dict) and _render_period is not None:

                _gpu_trace["render"] = _render_period

        except Exception as e:

            print(
                "RENDER HANDOFF TRACE ERROR:",
                e
            )


        if isinstance(result, dict):

            result["render_handoff"] = render_handoff_trace


        return result


    # ======================================================
    # BRAIN ACCESS COMPATIBILITY
    # ChatRuntimeV26 Bridge
    # ======================================================

    def get_brain(
        self
    ):

        return self.brain



    # ======================================================
    # UNIFIED RENDER ATTACHMENT v2
    # Single Render Pipeline
    # ======================================================


    def attach_render(
        self,
        result,
        text,
        asset=None,
        compiled_render_prompt=None,
        preset_resolution=None,
        terminology=None,
        render_seed=None,
        architectural_instruction=None,
        uso_reference=None,
        uso_reference_meta=None
    ):


        try:


            plan = {}



            if isinstance(
                result,
                dict
            ):


                plan = result.get(
                    "plan",
                    {}
                )


                if not plan:


                    inner = result.get(
                        "result"
                    )


                    if isinstance(
                        inner,
                        dict
                    ):

                        plan = inner.get(
                            "plan",
                            {}
                        )



            prompt_input = {


                "type":

                    plan.get(
                        "building_type",
                        "villa"
                    ),


                "floors":

                    plan.get(
                        "floors",
                        1
                    ),


                "style":

                    plan.get(
                        "style",
                        "modern"
                    ),


                "prompt":

                    text,


                "plan":

                    plan,


                "requirements":

                    plan.get(
                        "requirements",
                        {}
                    ),


                "previous_design":

                    self.state.get().get(
                        "last_design",
                        {}
                    ),


                "design_update":

                    (
                        result.get(
                            "design_update",
                            {}
                        )
                        if isinstance(
                            result,
                            dict
                        )
                        else {}
                    )

            }



            # ======================================================
            # ARCHITECTURAL INTENT ENRICHMENT
            # ======================================================


            architectural_intent = (
                result.get(
                    "architectural_intent",
                    {}
                )
                if isinstance(result, dict)
                else {}
            )


            if not architectural_intent:

                architectural_intent = (
                    self.architectural_intent.extract(
                        {
                            "prompt": prompt_input,
                            "plan": plan
                        }
                    )
                )


            # ======================================================
            # EXPERIMENTAL LLM ARCHITECTURAL PARSER
            #
            # CHAT_LANGUAGE_02 — DE-DUPLICATED INTERPRETATION
            #
            # The canonical deterministic path already produced a compiled
            # architectural prompt for this turn.  Running a second,
            # LLM-based architectural parse of the same text here would be
            # a competing interpretation of one request, so it is skipped
            # whenever the deterministic result is available.
            # ======================================================

            design_context = {}

            if not compiled_render_prompt:

                try:

                    llm_intent = self.architectural_llm_parser.parse(
                        text
                    )


                    if llm_intent:

                        normalized_llm_intent = (
                            self.intent_normalizer.normalize(
                                llm_intent
                            )
                        )


                        print(
                            "🧠 EXPERIMENTAL LLM INTENT:",
                            normalized_llm_intent
                        )


                        prompt_input["architectural_intent_llm"] = (
                            normalized_llm_intent
                        )


                except Exception as e:

                    print(
                        "⚠️ LLM ARCH PARSER BYPASS:",
                        e
                    )

            else:

                print(
                    "⏭️ LLM ARCH PARSER SKIPPED (deterministic compiled prompt present)"
                )



            # ======================================================
            # ARCHITECTURAL MATERIAL INTELLIGENCE ENRICHMENT
            # ======================================================

            architectural_intent = self.material_intelligence.enrich(

                architectural_intent,

                prompt_input.get(
                    "prompt",
                    ""
                )

            )


            print(
                "DEBUG CHAT ARCH INTENT:",
                architectural_intent
            )


            prompt_input["architectural_intent"] = architectural_intent


            print(
                "DEBUG PROMPT INPUT ARCH INTENT:",
                prompt_input.get(
                    "architectural_intent"
                )
            )
            # ======================================================
            # PROMPT BUILD
            # ======================================================

            prompt = self.prompt_builder.build(

                prompt_input

            )


            print(
                "🔥 ATTACH RENDER PROMPT:",
                prompt
            )


            # ======================================================
            # RENDER EXECUTION
            # ======================================================

            print(
                "DEBUG USING RENDER PATH 1"
            )


            render_payload = {


                "prompt":

                    prompt,


                "original_prompt":

                    text,


                # CHAT_LANGUAGE_02 — compiled English architectural prompt.
                # Consumed by RenderRuntime as the authoritative content
                # source; "prompt" above is preserved as the quality tail.
                "compiled_render_prompt":

                    compiled_render_prompt,

                # RENDER_INSTRUCTION_HANDOFF_V1 — the bounded A/B constraint
                # block (geometry shape, target preservation, temporary-object
                # rules). An explicit parameter, not ambient state: this method
                # never received the routing context. None for any turn without
                # an A/B instruction, in which case the resolved prompt is
                # byte-identical to before.
                "architectural_instruction":

                    architectural_instruction,


                # TEXT_TO_IMAGE_COMFY_03 — preset + terminology
                "preset_resolution":

                    preset_resolution,

                "terminology":

                    terminology,


                # TEXT_TO_IMAGE_COMFY_03B — optional explicit seed
                "seed":

                    render_seed,


                "architectural_intent":

                    architectural_intent,


                "mode":

                    "text2img"


            }


            # ==================================================
            # VISUAL_REFERENCE_UX_V2 — REFERENCE LINEAGE
            #
            # Built against the prompt that was ACTUALLY produced above, so the
            # recorded instruction is the real one rather than a re-derivation.
            # The reference is style guidance only; it is never the img2img
            # source, which is why `image_asset` is withheld below when a
            # reference is selected.
            # ==================================================

            _uso_payload = uso_reference

            if _uso_payload:

                try:

                    from core.render import uso_reference_handoff_v1 as _uso_h

                    _meta = uso_reference_meta or {}

                    _lineage = _uso_h.build_lineage(

                        _meta.get("reference") or {},

                        _meta.get("selection") or {},

                        _meta.get("staged") or {},

                        _uso_h.USO_WORKFLOW,

                        prompt

                    )

                    _uso_payload = dict(_uso_payload)

                    _uso_payload["lineage"] = _lineage

                except Exception as _lineage_error:  # noqa: BLE001

                    print(
                        "⚠️ USO LINEAGE UNAVAILABLE:",
                        _lineage_error
                    )

            # ======================================================
            # V22_HIGHRISE_NIGHT_ROUTING_V1 — EXACT FLOOR CONTROL
            #
            # A stated exact storey count has NO producer in the
            # text-to-image path: `flux.json` carries the prompt and
            # nothing else, so "۲۵ طبقه" is a wish the sampler is free
            # to ignore. `ARCHITECTOS_R1_CONTROLNET_AB_GPU_RESULT_V1`
            # named the correct fix and recorded that the project had
            # no producer for it; MODE_1's scaffold is that producer —
            # a wireframe with exactly N tiers and no building identity
            # to clone.
            #
            # Engaged ONLY for a pure text-to-image turn: no source
            # image, no USO reference. Those are edits, and MODE_1's
            # contract is text-to-image.
            #
            # The count comes from `parse_requested_floor_count_detail`,
            # which reports a NEGATED count as `count=None` instead of
            # accepting it — the defect recorded against the older
            # `_floor_count()` helper, which ignores `is_affirmed`.
            # ======================================================

            _v22_mode = None

            _v22_control_image = None

            _v22_floor_reading = None

            _v22_scaffold_meta = None

            _v22_source_asset = (
                None
                if _uso_payload
                else (
                    asset.get("asset")
                    if isinstance(asset, dict)
                    else asset
                )
            )

            if not _uso_payload and not _v22_source_asset:

                try:

                    from core.render.experimental.architectos_v22_highrise_night_v1 import (
                        parse_requested_floor_count_detail,
                        requires_exact_floor_control,
                    )

                    _v22_floor_reading = parse_requested_floor_count_detail(
                        text
                    )

                    if requires_exact_floor_control(
                        _v22_floor_reading.count
                    ):

                        _v22_control_image, _v22_scaffold_meta = (
                            _v22_exact_floor_control(
                                _v22_floor_reading.count
                            )
                        )

                        _v22_mode = "MODE_1_TXT2IMG_EXACT_FLOORS"

                except Exception as _v22_error:  # noqa: BLE001

                    # The scaffold could not be produced. The render still
                    # runs, but the count is NOT enforced and the response
                    # says so — a truthful gap rather than a silent claim.
                    print(
                        "⚠️ V22 EXACT FLOOR CONTROL UNAVAILABLE:",
                        _v22_error
                    )

                    _v22_mode = None

                    _v22_control_image = None

            # FACADE_FROM_PLAN_V27 lives in `handle_image_generate`, which is
            # the text-to-image path this product actually reaches. Measured:
            # a facade turn never entered `attach_render`, so conditioning
            # here would be dead code that reads as a delivered feature.

            render_result = self.render_runtime.render(

                "chat_project",

                render_payload,

                "flux",

                # A selected reference is NOT a source image. Passing it as
                # `image_asset` would route the turn into img2img editing and
                # silently change what was asked for.
                _v22_source_asset,

                uso_reference=_uso_payload,

                # V22_HIGHRISE_NIGHT_ROUTING_V1 — None for every turn that
                # did not state an exact high-rise floor count.
                v22_mode=_v22_mode,

                v22_control_image=_v22_control_image

            )

            # V22_HIGHRISE_NIGHT_ROUTING_V1 — the floor-count contract this
            # turn carried, and whether the scaffold that enforces it was
            # actually attached. Reported even when nothing was applied, so
            # "the count was ignored" is visible rather than implied.
            _v22_floor_trace = None

            if _v22_floor_reading is not None:

                _v22_floor_trace = {

                    "requested_count": _v22_floor_reading.count,

                    "negated": bool(_v22_floor_reading.negated),

                    "source": _v22_floor_reading.source,

                    "applied": bool(_v22_mode),

                    "mode": _v22_mode,

                    "control_image": _v22_control_image,

                    "scaffold_tier_count": (
                        _v22_scaffold_meta.get("tier_count")
                        if _v22_mode and isinstance(_v22_scaffold_meta, dict)
                        else None
                    ),

                    "scaffold_tiers_match": (
                        bool(
                            _v22_scaffold_meta.get(
                                "tier_count_matches_request"
                            )
                        )
                        if _v22_mode and isinstance(_v22_scaffold_meta, dict)
                        else None
                    ),

                }



            # ======================================================
            # RESULT BRIDGE
            # ======================================================

            final_render = self.result_bridge.resolve(

                render_result

            )



            # ======================================================
            # SAVE LAST RENDER ASSET
            # ======================================================

            try:

                if isinstance(

                    final_render,

                    dict

                ):

                    render_asset = final_render.get(
                        "asset"
                    )


                    if render_asset:

                        self.state.update({

                            "last_render_asset": render_asset,

                            "last_image_asset": render_asset

                        })


                        print(
                            "🔥 STATE AFTER RENDER SAVE:",
                            self.state.get()
                        )


                        print(

                            "💾 SAVED LAST RENDER ASSET:",

                            render_asset

                        )


            except Exception as e:


                print(

                    "SAVE LAST RENDER ASSET ERROR:",

                    e

                )



            # ======================================================
            # IMAGE RESPONSE ADAPTER
            # ======================================================

            image = self.image_response.adapt(

                final_render

            )



            # ======================================================
            # MERGE RESULT
            # ======================================================


            if isinstance(

                result,

                dict

            ):


                result["render"] = final_render


                result["image"] = image


                result["has_render"] = bool(image)

                # V22_HIGHRISE_NIGHT_ROUTING_V1 — the floor-count contract
                # this turn carried. None for every turn without an exact
                # count.
                result["v22_floor_control"] = _v22_floor_trace


                return result





            return {


                "design":

                    result,


                "render":

                    final_render,


                "image":

                    image,


                "has_render":

                    True,

                # V22_HIGHRISE_NIGHT_ROUTING_V1 — same contract as the
                # primary path above; this branch only runs when the design
                # response was not a dict.
                "v22_floor_control": _v22_floor_trace

            }





        except Exception as e:


            print(

                "UNIFIED RENDER ATTACHMENT ERROR:",

                e

            )


            return result






    # ======================================================
    # MAIN HANDLE
    # ======================================================

    def build_approved_render_intent(self, state):
        """Merge approved design facade/style evidence into render intent."""
        state = state if isinstance(state, dict) else {}
        intent = state.get("last_architectural_intent", {})
        intent = dict(intent) if isinstance(intent, dict) else {}
        design = state.get("last_design", {})
        design = design if isinstance(design, dict) else {}

        sources = [design]
        for key in ("result", "design", "architecture", "architectural_model"):
            value = design.get(key)
            if isinstance(value, dict):
                sources.append(value)

        render_keys = (
            "style",
            "style_analysis",
            "facade_language",
            "climate_facade_strategy",
            "facade_assembly",
            "facade_composition",
            "facade_geometry",
            "materials",
            "material_strategy",
            "levels",
        )
        for source in sources:
            for key in render_keys:
                value = source.get(key)
                if value not in (None, "", [], {}):
                    intent[key] = value

        intent["render_source"] = {
            "type": "approved_bim_design",
            "approval_status": True,
            "bim_result": state.get("bim_result", {}),
            "cad_asset": state.get("cad_asset"),
            "ifc_asset": state.get("ifc_asset"),
        }
        return intent


    def _publish_render_instruction(
        self,
        context,
        render_instruction,
        render_handoff_trace=None,
    ):
        """Publish a built render instruction's constraint block for the render.

        RESOLVED_T2I_ROUTING_HANDOFF_V1 — this body was moved VERBATIM out of
        `_handle_internal`. Nothing about the contract, the provenance rule or
        the guards changed; it exists as ONE function so the SAME publication
        path can be reached from a second place: the routing boundary, where
        the route (and therefore the validated render mode) is already
        resolved. See the ensure-step after `FINAL INTENT` in
        `_handle_internal`.

        The runtime receives the BOUNDED CONSTRAINT BLOCK, not the 2.7k-char
        narrative: the T5 budget is finite and the descriptive half is already
        in the compiled prompt. It travels on the request-scoped routing
        context, which `_route_image_edit` already receives, so no call
        signature changes.

        Fail-closed and idempotent:

          * nothing is published unless the instruction yields a NON-EMPTY
            block, so an observation-only or fully-negated turn cannot become
            a requirement;
          * the structured floor count rides along only from USER_TEXT /
            USER_CONFIRMATION provenance, never from an inference;
          * the caller only reaches this when the key is absent, so one turn
            can never carry two competing blocks.

        Returns the published block, or None when nothing was published.
        """

        if not (
            isinstance(context, dict)
            and isinstance(render_instruction, dict)
        ):

            return None

        _constraint_block = build_constraint_block(
            render_instruction
        )

        if not _constraint_block:

            return None

        _floor_provenance = (
            (render_instruction.get("constraints") or {})
            .get("floor_count_provenance")
            or {}
        )

        context["architectural_instruction"] = {
            "contract": "RenderConstraintBlockV1",
            "version": "1.0",
            "constraint_block": _constraint_block,
            "source": "render_instruction.english_instruction",
            # T2I_PRODUCTION_INTENT_HANDOFF_FIX_V1 — the SAME count the
            # block states, carried STRUCTURALLY (not re-parsed from
            # English prose) so the prompt builder's `floors` input can
            # never contradict the constraint block. Only a count the
            # USER stated or confirmed qualifies; an uncertain vision
            # observation stays out, and `None` means unknown, so the
            # consumer keeps its own default rather than inventing one.
            "floor_count": (
                _floor_provenance.get("value")
                if _floor_provenance.get("source") in (
                    "USER_TEXT",
                    "USER_CONFIRMATION",
                )
                else None
            ),
        }

        if isinstance(render_handoff_trace, dict):

            render_handoff_trace["architectural_instruction"] = (
                context["architectural_instruction"]
            )

        return context["architectural_instruction"]


    def handle(
        self,
        input_text,
        context=None
    ):
        """The single public entry point.

        PHASE 08 — this wrapper attaches the deterministic turn-semantics
        observation to EVERY response shape (chat, design, image, render)
        so the classification is auditable end to end. It changes no
        routing decision and no response content.
        """

        _PHASE08_OBSERVATION.observation = None

        _CONVERSATION_INTENT_OBSERVATION.decision = None

        result = self._handle_internal(
            input_text,
            context=context
        )

        observation = getattr(
            _PHASE08_OBSERVATION, "observation", None
        )

        _PHASE08_OBSERVATION.observation = None

        _cib_decision = getattr(
            _CONVERSATION_INTENT_OBSERVATION, "decision", None
        )

        _CONVERSATION_INTENT_OBSERVATION.decision = None

        if _cib_decision and isinstance(result, dict):

            # CONVERSATION_INTENT_BOUNDARY_V1 — the audited top-level
            # decision is reported on every response shape so the
            # routing is observable end to end.
            result["conversation_intent"] = _cib_decision

        if observation and isinstance(result, dict):

            # CONVERSATION_INTENT_BOUNDARY_V1 — the audited top-level
            # decision is reported on every response shape so the
            # routing is observable end to end.
            if "turn_semantics" not in result:

                result["turn_semantics"] = observation.get("semantics")

                result["capability"] = observation.get("capability")

                result["turn_language"] = observation.get("language")

            # TEACHING_CANDIDATE_VISIBILITY_T1_1 — the candidate is reported
            # INDEPENDENTLY of the fields above. Previously the whole block
            # was skipped whenever `turn_semantics` already existed, so a
            # teaching turn silently lost its candidate.
            #
            # A displayed candidate is NOT accepted knowledge: nothing here
            # writes the ledger, and confirmation is explicitly unavailable
            # because the application has no authenticated actor identity.
            candidate = observation.get("candidate")

            existing_teaching = result.get("teaching")

            if isinstance(existing_teaching, dict):

                # an existing owner (the architectural learning runtime)
                # already proposed something. Augment it additively; never
                # overwrite its keys and never mark it accepted.
                existing_teaching.setdefault(
                    "review",
                    _teaching_review(existing_teaching.get("candidate"), input_text),
                )
                existing_teaching.setdefault("confirmation_required", True)
                existing_teaching.setdefault("accepted", False)
                existing_teaching.setdefault("permanent_learning", False)
                existing_teaching.setdefault("confirmation_available", False)
                existing_teaching.setdefault(
                    "confirmation_blocked_reason", "no_authenticated_actor"
                )

            elif candidate:

                result["teaching"] = _teaching_review_block(
                    candidate, observation, input_text
                )

        return result


    # ======================================================
    # ARCHITECTOS MULTI-FLOOR ENGINE V2 — FURNISHED PLAN ROUTING
    #
    # The legacy design stub answers duplex / lightwell / mixed-use
    # prompts with "⚠️ طراحی ایجاد نشد" because it only knows the
    # box-only generator. The V2 synthesizer turns the same Persian
    # text into a complete furnished plan (rooms, doors with swing
    # arcs, windows, furniture, columns, dimensions) and exports
    # real .svg / .dxf sheets.
    #
    # The V2 detector matches very broad tokens («ساختمان», «طراحی»,
    # «طبقه»), so every image / render / edit turn is excluded first.
    # Without that guard "این ساختمان را رندر کن" would be answered
    # with a floor plan instead of a render.
    # ======================================================

    _PLAN_ROUTE_RENDER_MARKERS = (
        "رندر", "render", "تصویر", "ویژوال", "visualization", "archviz",
        "سه بعدی", "3d", "نمای سه بعدی", "عکس", "photo",
        "ویرایش تصویر", "بازسازی تصویر", "edit image",
        # FACADE_FOLLOWUP_V27 — a facade re-render is a render turn even when
        # the word "رندر" is absent ("همین نما رو شب بگیر", "نمای شب").
        "نمای شب", "نمای روز", "نمای غروب",
        "همین نما", "این نما", "همون نما", "اون نما",
        "همین ساختمان", "همین پلان", "این ساختمان",
    )

    _PLAN_ROUTE_BLOCKED_PHRASES = (
        "فقط عناصر قابل مشاهده", "observation only",
        "این تصویر", "این عکس", "this image", "this photo",
    )

    def _plan_route_blocked(self, text, context):
        """True when the turn belongs to an image/render path.

        Plan synthesis must never capture a render, an image edit or a
        read-only image observation, because the V2 keyword detector is
        broad enough to match ordinary architectural vocabulary inside
        those requests.
        """

        low = str(text or "").lower()

        if any(m in low for m in self._PLAN_ROUTE_RENDER_MARKERS):

            return True

        if any(p in low for p in self._PLAN_ROUTE_BLOCKED_PHRASES):

            return True

        try:

            if self.intent_router.is_image_edit_request(text):

                return True

        except Exception:

            pass

        try:

            state = self.state.get() or {}

        except Exception:

            state = {}

        if isinstance(state, dict) and state.get("waiting_image_edit"):

            return True

        if isinstance(context, dict):

            for key in ("image", "image_path", "image_asset", "image_id",
                        "upload_path", "attached_image"):

                if context.get(key):

                    return True

        return False

    def _format_plan_message(self, project, saved):
        """Build the transcript message: schedule, coverage, lightwell, paths."""

        site = project.site

        lines = [
            "🏠 پلان مبلمان‌شده معماری آماده شد.",
            "",
            str(project.project_title_fa or ""),
            "",
            "📐 زمین: %.2f × %.2f متر (%.2f م²)"
            % (
                site.width_x_mm / 1000.0,
                site.length_y_mm / 1000.0,
                (site.width_x_mm * site.length_y_mm) / 1_000_000.0,
            ),
            "📊 سطح اشغال: %d٪ در بخش %s"
            % (
                int(round(float(site.coverage_ratio) * 100)),
                str(site.building_placement or ""),
            ),
            "☀️ حیاط خلوت شمالی: عمق %.2f متر — مساحت %.2f م²"
            % (
                site.lightwell_depth_mm / 1000.0,
                float(site.lightwell_area_m2),
            ),
        ]

        for floor in project.floors:

            lines.append("")
            lines.append(
                "🏢 %s — %d فضا، %.2f م² خالص (پوشش %d٪)"
                % (
                    floor.name_fa,
                    len(floor.rooms),
                    floor.net_area_m2,
                    int(round(floor.coverage_ratio_achieved * 100)),
                )
            )

            for room in floor.rooms:

                lines.append(
                    "   • %s — %.2f م²"
                    % (room.label_fa, room.net_rect_mm.area_m2)
                )

        audit = project.audit

        lines.append("")
        lines.append(
            "✅ بازبینی مستقل: %s — %d ایراد"
            % (audit.status.value, len(audit.violations))
        )

        for violation in audit.violations[:5]:

            lines.append("   ⚠️ %s" % (violation,))

        lines.append("")
        lines.append("💾 فایل‌های ذخیره‌شده:")
        lines.append("• SVG: %s" % saved["svg"])
        lines.append("• DXF: %s" % saved["dxf"])
        lines.append("• AutoCAD (ArchitectOS_Project.dxf): %s" % saved["project_dxf"])

        return "\n".join(lines)

    def _try_v20_plan_turn(self, text, context=None):
        """v20 — incremental plan edit, or elevation/3D render, on the active plan.

        Returns None when the turn is neither, or when this session has no
        active ``BuildingProjectResultV3`` (in which case the normal
        synthesis path runs untouched).
        """

        try:

            from core.planning import plan_chat_bridge_v20 as _bridge

        except Exception:

            return None

        active = _bridge.get_active()

        if not active:

            return None

        project = active.get("project")

        if project is None:

            return None

        if _bridge.is_render_request(text):

            return self._v20_render_turn(project, text)

        if _bridge.is_edit_command(text):

            return self._v20_edit_turn(project, text)

        return None

    def _v20_plans_dir(self):
        """Directory the /planning/drawing route serves from."""

        root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

        return os.path.join(root, "outputs", "plans")

    def _v20_edit_turn(self, project, text):
        """Apply a conversational edit and re-export svg/dxf/json."""

        from core.planning import plan_chat_bridge_v20 as _bridge

        try:

            updated, actions = _bridge.apply_edit(project, text)

        except Exception as exc:

            message = "⚠️ ویرایش پلان ناموفق بود: %s" % (exc,)

            return {
                "type": "plan_drawing",
                "status": "error",
                "result": message,
                "message": message,
            }

        out_dir = self._v20_plans_dir()

        saved = _bridge.reexport(updated, out_dir)

        updated.saved_files = dict(updated.saved_files or {})

        updated.saved_files.update(saved)

        _bridge.set_active(updated, saved)

        bullets = "\n".join("• " + str(a) for a in actions)

        message = "✅ پلان فعال بر اساس دستور شما ویرایش شد:\n" + bullets

        svg_name = os.path.basename(saved["svg"])

        return {
            "type": "plan_drawing",
            "status": "success",
            "engine": "ARCHITECTOS_V20_CONVERSATIONAL_EDITOR",
            "design_id": str(updated.project_id),
            "result": message,
            "message": message,
            "edit_actions": list(actions),
            "plan_drawing": {
                "status": "ready",
                "type": "plan_drawing",
                "version": "v20",
                "format": "svg+dxf",
                "path": saved["dxf"],
                "artefacts": [saved["svg"], saved["dxf"], saved["json"]],
                "plan_summary": {
                    "project_id": str(updated.project_id),
                    "floors": len(updated.floors),
                    "audit_status": updated.audit.status.value,
                },
            },
            "plan_drawing_v2": {
                "project_id": str(updated.project_id),
                "svg_path": saved["svg"],
                "dxf_path": saved["dxf"],
                "svg_url": "/planning/drawing/" + svg_name,
                "audit_status": updated.audit.status.value,
                "floor_count": len(updated.floors),
            },
        }

    def _v20_render_turn(self, project, text):
        """Produce the CAD elevation/perspective sheet, then render via ComfyUI."""

        from core.planning import plan_chat_bridge_v20 as _bridge

        out_dir = self._v20_plans_dir()

        try:

            assets = _bridge.build_render(project, text, out_dir)

        except Exception as exc:

            message = "⚠️ ساخت نمای فنی ناموفق بود: %s" % (exc,)

            return {
                "type": "image",
                "status": "error",
                "result": message,
                "message": message,
            }

        result = _bridge.run_comfyui(
            project, text, assets["controlnet_png"], out_dir
        )

        facade_name = os.path.basename(assets["facade_svg"])

        facade_url = "/planning/drawing/" + facade_name

        status = result.get("status")

        rendered = result.get("render_png_path")

        lines = [
            "🏛️ شیت نما و پرسپکتیو: " + facade_url,
            "📐 دوربین: %s | سبک: %s" % (
                assets["camera_mode"], assets["style_key"]
            ),
        ]

        if status == "COMFYUI_RENDERED" and rendered:

            lines.append("🖼️ رندر ComfyUI آماده است: " + os.path.basename(rendered))

        elif status == "COMFYUI_TIMEOUT":

            lines.append(
                "⏳ رندر در صف ComfyUI مانده است (شناسه: %s)."
                % result.get("prompt_id")
            )

        elif status == "COMFYUI_ERROR":

            lines.append("⚠️ رندر ناموفق بود: %s" % (result.get("detail"),))

        else:

            lines.append("⚠️ ComfyUI در دسترس نیست: %s" % (result.get("reason"),))

        message = "\n".join(lines)

        attachments = []

        if rendered and os.path.isfile(rendered):

            attachments.append({
                "url": "/planning/drawing/" + os.path.basename(rendered),
                "display_name": "ComfyUI Render",
                "kind": "render",
            })

        return {
            "type": "image",
            "status": "success" if status == "COMFYUI_RENDERED" else "partial",
            "engine": "ARCHITECTOS_V20_3D_RENDER",
            "result": message,
            "message": message,
            "attachments": attachments,
            "image": {
                "url": attachments[0]["url"] if attachments else facade_url,
                "filename": os.path.basename(rendered) if rendered else facade_name,
                "path": rendered or assets["facade_svg"],
                "exists": True,
            },
            "render": {
                "status": status,
                "camera_mode": assets["camera_mode"],
                "style_key": assets["style_key"],
                "facade_svg": assets["facade_svg"],
                "controlnet_svg": assets["controlnet_svg"],
                "controlnet_png": assets["controlnet_png"],
                "render_png": rendered,
                "prompt_id": result.get("prompt_id"),
                "detail": result.get("detail") or result.get("reason"),
            },
            "plan_drawing_v2": {
                "project_id": str(project.project_id),
                "svg_path": assets["facade_svg"],
                "svg_url": facade_url,
                "audit_status": project.audit.status.value,
                "floor_count": len(project.floors),
            },
        }

    def _try_v25_plan_session(self, text, context=None):
        """Create or incrementally edit the project's parametric plan.

        Returns a chat response when this route owns the turn, a truthful
        refusal when ``mode == "plan_design"`` asked for something that is
        not a plan turn, and ``None`` when the turn belongs elsewhere.

        The refusal matters: an explicitly selected mode must never answer
        with silence or with a different product. It states what the mode
        needs instead.
        """

        mode = str((context or {}).get("mode") or "").strip().lower()

        forced = mode == "plan_design"

        if not str(text or "").strip():

            return None

        # A render, an image edit or an image observation is never a plan
        # turn. This guard runs even in `plan_design` mode so an explicit
        # mode can never swallow a render request.
        if self._plan_route_blocked(text, context):

            return None

        try:

            from core.planning import plan_session_v25 as _session

        except Exception as _import_exc:  # noqa: BLE001

            print("⚠️ V25 PLAN SESSION UNAVAILABLE:", _import_exc)

            return None

        project_id = str(
            (context or {}).get("session_id")
            or (context or {}).get("project_id")
            or "default"
        ).strip()

        try:

            result = _session.route_plan_turn(project_id, text)

        except Exception as _session_exc:  # noqa: BLE001

            print("⚠️ V25 PLAN SESSION ERROR:", _session_exc)

            if not forced:

                return None

            detail = "⚠️ ساخت پلان ناموفق بود: %s" % (_session_exc,)

            return {
                "type": "plan_drawing",
                "status": "error",
                "engine": "ARCHITECTOS_V25_PARAMETRIC",
                "result": detail,
                "message": detail,
            }

        if result.get("status") != "ok":

            if not forced:

                return None

            detail = (
                "⚠️ این پیام یک درخواست پلان نیست. برای ساخت پلان، ابعاد زمین "
                "و تعداد طبقات را بنویسید؛ برای ویرایش، تغییر مورد نظر را روی "
                "پلان فعال بنویسید."
            )

            return {
                "type": "plan_drawing",
                "status": "error",
                "engine": "ARCHITECTOS_V25_PARAMETRIC",
                "result": detail,
                "message": detail,
            }

        return self._v25_plan_response(result)

    def _v25_plan_response(self, result):
        """Shape a `route_plan_turn` result as a chat response payload.

        The transcript needs three things and gets all three: a sentence that
        explains what happened, a raster sheet to show inline, and served
        download links for the CAD artefacts.
        """

        plan = result.get("plan") or {}

        assets = result.get("assets") or {}

        revision = result.get("plan_revision")

        lines = []

        if result.get("mode") == "edit":

            lines.append("✏️ پلان فعال بر اساس دستور شما ویرایش شد.")

        else:

            lines.append("🏠 پلان معماری آماده شد.")

        lines.append("")

        if plan.get("title_fa"):

            lines.append(str(plan["title_fa"]))

            lines.append("")

        lines.append(
            "🏢 %s طبقه — %s فضا در طبقه اول (نسخه %s)"
            % (plan.get("floors"), plan.get("rooms"), revision)
        )

        lines.append(
            "✅ بازبینی مستقل: %s" % (plan.get("audit_status") or "—")
        )

        lines.append("")

        # ==================================================
        # PLAN_PHYSICAL_PATHS_V27 — the file on disk AND the link
        #
        # The v25 reply printed only served URLs. A URL is not the file the
        # user opens in AutoCAD, so the exact Windows path is printed beside
        # it. Both are real: the path is where the exporter wrote, the URL is
        # what the transcript can fetch.
        # ==================================================

        local_paths = result.get("local_paths") or {}

        if local_paths.get("dxf"):

            lines.append(
                "📂 مسیر کامل ذخیره روی هارد ویندوز: %s" % local_paths["dxf"]
            )

            lines.append("")

        lines.append("💾 دانلود:")

        if assets.get("dxf"):

            lines.append("• DXF (AutoCAD 2025): %s" % assets["dxf"])

        if assets.get("svg"):

            lines.append("• SVG: %s" % assets["svg"])

        if assets.get("png"):

            lines.append("• PNG: %s" % assets["png"])

        if local_paths.get("svg"):

            lines.append("")

            lines.append("📂 مسیرهای کامل روی هارد ویندوز:")

            for label, key in (
                ("DXF", "dxf"),
                ("SVG", "svg"),
                ("PNG", "png"),
            ):

                if local_paths.get(key):

                    lines.append("• %s: %s" % (label, local_paths[key]))

        message = "\n".join(lines)

        image_url = result.get("image_url") or assets.get("png") or assets.get("svg")

        downloads = []

        if assets.get("png"):

            downloads.append({"label": "PNG", "url": assets["png"]})

        if assets.get("svg"):

            downloads.append({"label": "SVG", "url": assets["svg"]})

        if assets.get("dxf"):

            downloads.append(
                {"label": "DXF (AutoCAD 2025)", "url": assets["dxf"]}
            )

        return {
            "type": "plan_drawing",
            "status": "success",
            "engine": "ARCHITECTOS_V25_PARAMETRIC",
            "design_id": (result.get("plan") or {}).get("project_id"),
            "result": message,
            "message": message,
            "plan_revision": revision,
            "plan_drawing": {
                "status": "ready",
                "type": "plan_drawing",
                "version": "v25",
                "format": "svg+dxf+png+json",
                "path": assets.get("dxf"),
                "artefacts": [
                    url
                    for url in (
                        assets.get("svg"),
                        assets.get("dxf"),
                        assets.get("png"),
                        assets.get("json"),
                    )
                    if url
                ],
                "plan_summary": {
                    "project_id": (result.get("plan") or {}).get("project_id"),
                    "floors": plan.get("floors"),
                    "audit_status": plan.get("audit_status"),
                },
            },
            "plan_drawing_v2": {
                "project_id": (result.get("plan") or {}).get("project_id"),
                "plan_revision": revision,
                "svg_url": assets.get("svg"),
                "png_url": assets.get("png"),
                "dxf_url": assets.get("dxf"),
                "image_url": image_url,
                "downloads": downloads,
                "audit_status": plan.get("audit_status"),
                "floor_count": plan.get("floors"),
            },
        }

    def _try_synthesize_plan_turn(self, text, context=None):
        """Synthesize a furnished plan for a design prompt, or return None.

        Returns None only when the turn is not a plan request, is blocked by
        an image/render guard, or the engine cannot be imported — in those
        cases the caller falls through to the legacy routing unchanged.
        """

        try:

            from core.planning.multifloor_v1.engine import (
                ArchitecturalPlanSynthesizer,
                export_project_to_dxf,
                export_project_to_svg,
                is_architectural_design_prompt,
            )

        except Exception:

            return None

        # ==================================================
        # ARCHITECTOS_V20 — conversational editing + 3D/ComfyUI render
        #
        # Runs BEFORE the keyword guards below because an incremental edit
        # ("ستون B1 رو حذف کن") or a render ask is not a design prompt and
        # would otherwise fall through to the legacy routing. Both branches
        # require an active BuildingProjectResultV3 for this session and
        # return None when there is none, so first-turn behaviour is
        # unchanged.
        # ==================================================

        try:

            _v20_response = self._try_v20_plan_turn(text, context)

        except Exception as _v20_exc:

            print("⚠️ ARCHITECTOS_V20 PLAN TURN ERROR:", _v20_exc)

            _v20_response = None

        if _v20_response is not None:

            return _v20_response

        # ==================================================
        # V25_PLAN_SESSION — ONE OWNER FOR PLAN CREATE + EDIT
        #
        # The parametric engine already existed; what it did NOT have was a
        # persisted per-project state. Every turn re-parsed the prompt from
        # scratch (`synthesize_from_text`) and the "active plan" lived in a
        # process-wide singleton, so a second turn could not edit the plan
        # the first turn produced, and a restart forgot it entirely.
        #
        # `plan_session_v25.route_plan_turn` owns both: it persists
        # `active_plan_params` / `active_plan_files` / `active_render_state`
        # to `<project>/session_state.json`, applies
        # `apply_incremental_plan_edit` on a modification turn, and exports
        # `plan_rev_<N>.{svg,dxf,png,json}`.
        #
        # It is tried BEFORE the legacy single-shot synthesis so the two can
        # never both answer the same turn. A `not_a_plan_turn` verdict falls
        # through unchanged.
        # ==================================================

        _session_response = self._try_v25_plan_session(text, context)

        if _session_response is not None:

            return _session_response

        if not text or not is_architectural_design_prompt(text):

            return None

        if self._plan_route_blocked(text, context):

            return None

        try:

            project = ArchitecturalPlanSynthesizer().synthesize_from_text(text)

        except Exception as exc:

            return {
                "type": "plan_drawing",
                "status": "error",
                "result": "⚠️ ساخت پلان ناموفق بود: %s" % (exc,),
                "message": "⚠️ ساخت پلان ناموفق بود: %s" % (exc,),
            }

        root = os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__)
                )
            )
        )

        out_dir = os.path.join(root, "outputs", "plans")

        os.makedirs(out_dir, exist_ok=True)

        project_id = str(project.project_id or "ARCH_PROJECT")

        svg_path = os.path.join(out_dir, project_id + ".svg")
        dxf_path = os.path.join(out_dir, project_id + ".dxf")
        project_dxf_path = os.path.join(out_dir, "ArchitectOS_Project.dxf")

        svg_str = export_project_to_svg(project)
        dxf_str = export_project_to_dxf(project)

        with open(svg_path, "w", encoding="utf-8") as handle:

            handle.write(svg_str)

        with open(dxf_path, "w", encoding="utf-8") as handle:

            handle.write(dxf_str)

        # The AutoCAD hand-off copy: always the most recent plan, so opening
        # this one file in AutoCAD 2025 shows the complete furnished sheet.
        with open(project_dxf_path, "w", encoding="utf-8") as handle:

            handle.write(dxf_str)

        saved = {
            "svg": os.path.abspath(svg_path),
            "dxf": os.path.abspath(dxf_path),
            "project_dxf": os.path.abspath(project_dxf_path),
        }

        # ==================================================
        # PLAN_SHEET_PNG_V1 — the plan sheet as a raster image
        #
        # The transcript renders an <img>, so the sheet needs a bitmap: an
        # SVG served as `image/svg+xml` is correct but gives the bubble no
        # fixed intrinsic size and no thumbnail. The rasteriser is the same
        # one `plan_session_v25` uses, so there is ONE rasterisation path in
        # the product rather than two that can disagree.
        #
        # A missing rasteriser is reported, never faked: `png` stays None and
        # the transcript falls back to the SVG, which is still a real sheet.
        # ==================================================

        png_path = os.path.join(out_dir, project_id + ".png")

        try:

            from core.planning.plan_session_v25 import rasterize_svg

            if rasterize_svg(pathlib.Path(svg_path), pathlib.Path(png_path)):

                saved["png"] = os.path.abspath(png_path)

        except Exception as _png_exc:  # noqa: BLE001

            print("⚠️ PLAN SHEET PNG UNAVAILABLE:", _png_exc)

        project.saved_files = dict(saved)

        # ARCHITECTOS_V20 — remember this project as the session's active plan
        # so the next turn can edit it in place or render it, instead of
        # synthesising a fresh one from scratch.
        try:

            from core.planning import plan_chat_bridge_v20 as _bridge_v20

            _bridge_v20.set_active(project, saved)

        except Exception as _active_exc:

            print("⚠️ V20 ACTIVE PLAN REGISTRATION ERROR:", _active_exc)

        # The plan and its exported files are the product; the transcript
        # sentence is decoration. A formatter defect used to propagate out of
        # `_try_synthesize_plan_turn`, which the caller catches and treats as
        # "not a plan turn" — so a real plan was silently discarded and the
        # turn fell through to the legacy design pipeline. A missing attribute
        # in this sentence must never cost the user their plan.
        try:

            message = self._format_plan_message(project, saved)

        except Exception as _format_exc:  # noqa: BLE001

            print("⚠️ PLAN MESSAGE FORMAT ERROR:", _format_exc)

            message = "✅ پلان معماری آماده شد — %d طبقه، %d فضا." % (
                len(project.floors),
                sum(len(f.rooms) for f in project.floors),
            )

        svg_name = os.path.basename(svg_path)

        return {
            "type": "plan_drawing",
            "status": "success",
            "engine": "ARCHITECTOS_MULTIFLOOR_V2",
            "design_id": project_id,
            "result": message,
            "message": message,
            "plan_drawing": {
                "status": "ready",
                "type": "plan_drawing",
                "version": "v2",
                "format": "svg+dxf",
                "path": saved["dxf"],
                "artefacts": [saved["svg"], saved["dxf"], saved["project_dxf"]],
                "plan_summary": {
                    "project_id": project_id,
                    "floors": len(project.floors),
                    "audit_status": project.audit.status.value,
                },
            },
            "plan_drawing_v2": {
                "project_id": project_id,
                "svg_path": saved["svg"],
                "dxf_path": saved["dxf"],
                "project_dxf_path": saved["project_dxf"],
                "png_path": saved.get("png"),
                "svg_url": "/planning/drawing/" + svg_name,
                # PLAN_SHEET_DOWNLOADS_V1 — the transcript needs clickable
                # links, not absolute Windows paths a browser cannot open.
                # `image_url` is the raster sheet when one exists and the
                # SVG otherwise; both are real, served documents.
                "png_url": (
                    "/planning/drawing/" + os.path.basename(saved["png"])
                    if saved.get("png")
                    else None
                ),
                "dxf_url": "/planning/drawing/" + os.path.basename(saved["dxf"]),
                "image_url": (
                    "/planning/drawing/" + os.path.basename(saved["png"])
                    if saved.get("png")
                    else "/planning/drawing/" + svg_name
                ),
                "downloads": (
                    (
                        [
                            {
                                "label": "PNG",
                                "url": "/planning/drawing/"
                                + os.path.basename(saved["png"]),
                            }
                        ]
                        if saved.get("png")
                        else []
                    )
                    + [
                        {"label": "SVG", "url": "/planning/drawing/" + svg_name},
                        {
                            "label": "DXF (AutoCAD 2025)",
                            "url": "/planning/drawing/"
                            + os.path.basename(saved["dxf"]),
                        },
                    ]
                ),
                "audit_status": project.audit.status.value,
                "floor_count": len(project.floors),
            },
        }

    def _handle_internal(
        self,
        input_text,
        context=None
    ):


        if context is not None:

            self.context = context


        # ==================================================
        # CHAT_LANGUAGE_02 — SESSION BINDING
        #
        # Every request is bound to a session for the duration of this
        # thread.  Independent clients therefore get independent
        # conversation state and independent architectural context.
        # No session id -> legacy global singleton (unchanged).
        # ==================================================

        session_id = None

        if isinstance(context, dict):

            session_id = context.get("session_id")


        session_bundle = session_registry.begin(
            session_id
        )


        # ==================================================
        # T2I_I2I_CHAT_TO_IMAGE_EXECUTION_V1
        # PER-SESSION TURN COUNTER
        #
        # One increment per completed turn, used to expire a pending
        # image-generation request so it can never capture an unrelated
        # later turn. Purely observational for every other path.
        # ==================================================

        try:

            self.state.next_turn()

        except Exception:

            pass


        arch_context_store = session_registry.current_architectural_context(
            architectural_conversation_context
        )



        text = input_text



        # raw user-message print removed (LOG_SENSITIVE_OUTPUT_FIX)



        payload = self.input_adapter.normalize(

            text,

            context

        )


        text = payload["text"]


        # ==================================================
        # MULTIFLOOR_ENGINE_V2_CHAT_PLAN_ROUTING
        #
        # Runs BEFORE the legacy design stub so a furnished-plan
        # request (villa / duplex / lightwell / mixed-use) is answered
        # by the V2 synthesizer instead of falling through to
        # "⚠️ طراحی ایجاد نشد". The branch is fully guarded: it returns
        # None for anything that is not a plan request, and for every
        # render / image-edit / image-observation turn.
        # ==================================================

        try:

            _plan_response = self._try_synthesize_plan_turn(
                text,
                context
            )

        except Exception as _plan_exc:

            print(
                "⚠️ MULTIFLOOR_V2 PLAN ROUTING ERROR:",
                _plan_exc
            )

            _plan_response = None

        if _plan_response is not None:

            try:

                self.writeback.store(
                    text,
                    str(_plan_response.get("result", ""))
                )

            except Exception:

                pass

            return _plan_response



        # ==================================================
        # PLAN_FIRST_PRODUCT_SLICE_V1 — OPT-IN CONCEPTUAL PLANNING
        #
        # The spatial-planning owner
        # (core/knowledge/architectural_spatial_planning_understanding_v1)
        # had NO production caller: only its own module and its tests. This
        # is the smallest connection that makes its output product-visible.
        #
        # Opt-in ONLY, and strict: the context flag must be the real boolean
        # True (the request boundary normalises "1"/"true"/"yes"/"on"), so
        # no image, render, edit or design route can be captured by accident.
        # The owner's own contract is returned unchanged — no geometry, no
        # plan drawing, no render is produced here.
        # ==================================================

        if (
            isinstance(context, dict)
            and context.get("spatial_planning") is True
        ):

            from core.chat.handlers.spatial_planning_handler import (
                handle_spatial_planning,
            )

            return handle_spatial_planning(
                text,
                context,
            )


        image = payload["image"]


        # ==================================================
        # PHASE 2D-1 — RAW TEXT PROVENANCE
        # Normalized text ("text") is the processing form.
        # Raw text is retained on the request boundary and exposed to the
        # routing context for audit / future semantic + prompt compilation.
        # No memory behaviour is changed here.
        # ==================================================

        raw_text = payload.get(
            "raw_text",
            text
        )


        # ==================================================
        # PHASE 08 — CONVERSATIONAL TURN SEMANTICS + TEACHING FOUNDATION
        #
        # ONE assistant. This deterministic layer:
        #   - classifies the turn (08B)
        #   - records teaching CANDIDATES, never permanent knowledge (08C)
        #   - answers teach-back requests (08D)
        #   - resolves the reply language from canonical project state (08E)
        #
        # It does NOT create a second LLM / memory / conversation
        # history / parallel assistant, it never renders, and it never
        # calls ComfyUI.
        #
        # Neutral turns (QUESTION / INSTRUCTION / small talk) fall
        # through to the frozen pipeline completely unchanged.
        # ==================================================

        # ==================================================
        # CONVERSATION_INTENT_BOUNDARY_V1
        #
        # The SINGLE authoritative top-level intent decision, taken
        # BEFORE the teaching foundation and the learning bridge run.
        #
        # The decision is made from THIS turn's own signal (with the
        # voice layer's interpreted utterance when present) and is
        # deliberately non-sticky: a previous teaching / architecture
        # turn never forces the same mode onto this one.
        #
        # It is used as a GATE, not a router:
        #   * TEACHING      -> the teaching foundation runs unchanged.
        #   * anything else -> the teaching foundation may still be
        #                      consulted (for language resolution and
        #                      read-only reflection), but its SHORT
        #                      CIRCUIT and the learning bridge are
        #                      suppressed, so a general / architecture
        #                      conversation can never be swallowed by
        #                      the teaching flow.
        #
        # Auditability: the audited decision is placed on the routing
        # context and returned on the response's semantics.
        # ==================================================

        _cib_decision = None

        try:

            _cib_decision = classify_conversation_intent(

                text,

                raw_text=raw_text,

                interpreted_utterance=(
                    (context or {}).get("interpreted_utterance")
                    if isinstance(context, dict)
                    else None
                ),

                context=context,
            )

            print(
                "\U0001f9ed CONVERSATION INTENT BOUNDARY:",
                _cib_decision.get("intent"),
                "| confidence:",
                _cib_decision.get("confidence"),
                "| signals:",
                _cib_decision.get("signals"),
                "| source:",
                _cib_decision.get("source"),
            )

        except Exception as _cib_error:

            print(
                "CONVERSATION INTENT BOUNDARY ERROR:",
                _cib_error
            )

            _cib_decision = None

        _cib_is_teaching = bool(
            _cib_decision
            and _cib_decision.get("intent") == _CIB_TEACHING
        )

        # Expose the audited decision to the public handle() wrapper.
        _CONVERSATION_INTENT_OBSERVATION.decision = _cib_decision

        teaching_turn = None

        # ==================================================
        # CONVERSATION_INTENT_BOUNDARY_V1 — BOUNDARY ENFORCEMENT (1/2)
        #
        # The boundary is the authority. `observe_turn` records a
        # teaching CANDIDATE to disk for a TEACHING_STATEMENT turn, so
        # it must not be allowed to persist for a turn the boundary says
        # is NOT teaching. Passing no session id disables persistence
        # (the store requires a real project) while leaving language
        # resolution and read-only reflection fully intact.
        # ==================================================
        _cib_allow_persistence = (
            _cib_decision is None or _cib_is_teaching
        )

        _observe_session_id = (
            session_bundle.get("session_id")
            if _cib_allow_persistence
            else None
        )

        try:

            teaching_turn = teaching_foundation.observe_turn(

                text,

                raw_text=raw_text,

                session_id=_observe_session_id,

                context=context,

                input_type=(
                    context.get("input_type")
                    if isinstance(context, dict)
                    else None
                ),
            )

        except Exception as e:

            print(
                "PHASE 08 TEACHING FOUNDATION ERROR:",
                e
            )

            teaching_turn = None

        # ==================================================
        # CONVERSATION_INTENT_BOUNDARY_V1 — BOUNDARY ENFORCEMENT (2/2)
        #
        # The boundary is the authority. When it says this turn is NOT
        # teaching, the teaching layer's SIDE EFFECTS are neutralised:
        # any candidate is dropped and its short circuit is forced off.
        # Language resolution (`language`, `language_decision`) is
        # retained so the frozen reply-language behaviour is unchanged.
        # ==================================================
        if (
            teaching_turn
            and _cib_decision is not None
            and not _cib_is_teaching
        ):

            teaching_turn = dict(teaching_turn)

            teaching_turn["candidate"] = None

            teaching_turn["candidates"] = []

            teaching_turn["candidate_persisted"] = False

            teaching_turn["short_circuit"] = False

            teaching_turn["response"] = None

            teaching_turn["meaning"] = None

            teaching_turn["project_id"] = None

            teaching_turn["boundary_overrode_teaching"] = True

            teaching_turn["boundary_intent"] = _cib_decision.get(
                "intent"
            )


        # Expose the observation to the public handle() wrapper so every
        # response shape carries the turn semantics.
        _PHASE08_OBSERVATION.observation = teaching_turn


        # ==================================================
        # ARCHITECTURAL_LEARNING_RUNTIME_BRIDGE_V1
        #
        # The runtime learning path, orchestrated over the EXISTING layers:
        #   teaching detection -> extraction -> classification
        #   -> human validation -> memory -> retrieval -> reasoning -> answer
        #
        # ADDITIVE: it returns a chat-shaped response ONLY when it owns the
        # turn. Returning None leaves every existing behaviour unchanged
        # (the short-circuit below and the frozen pipeline both still run).
        # It never renders, never generates design and never bypasses the
        # human confirmation requirement.
        # ==================================================

        _learning_bridge_response = None

        try:

            # CONVERSATION_INTENT_BOUNDARY_V1 — the learning bridge owns
            # a turn only when the authoritative boundary says this turn
            # is TEACHING (or when the boundary could not decide and the
            # previous behaviour is kept). A general / architecture
            # conversation therefore never enters the learning path.
            _bridge_owns_turn = (
                _cib_decision is None
                or _cib_is_teaching
            )

            _learning_bridge_response = (
                architectural_learning_runtime.bridge(

                    teaching_turn,

                    text,

                    context,

                    session_id=session_bundle.get("session_id"),
                )
                if _bridge_owns_turn
                else None
            )

        except Exception as _learning_bridge_error:

            print(
                "ARCHITECTURAL LEARNING RUNTIME BRIDGE ERROR:",
                _learning_bridge_error
            )

            _learning_bridge_response = None


        if _learning_bridge_response is not None:

            return _learning_bridge_response


        # CONVERSATION_INTENT_BOUNDARY_V1 — the teaching foundation's
        # short circuit is honoured only for a turn the boundary agrees
        # is TEACHING. This is what stops "خودت رو معرفی کن" (or any
        # other general / architecture turn) from being answered by the
        # teaching confirmation flow.
        if (
            teaching_turn
            and teaching_turn.get("short_circuit")
            and (_cib_decision is None or _cib_is_teaching)
        ):

            print(
                "\U0001f9e0 PHASE 08 TURN SEMANTICS:",
                teaching_turn.get("turn_kind"),
                "| language:",
                teaching_turn.get("language"),
                "| short-circuit (no routing, no render)"
            )

            return teaching_turn.get("response")


        # ==================================================
        # PHASE 2D-2 — PERSIAN ARCHITECTURAL UNDERSTANDING
        # Deterministic, additive, non-behavioural: the structured semantic
        # intent is exposed on the routing context only.  No routing decision
        # and no memory behaviour depends on it yet (consumed by 2D-3).
        # ==================================================

        architectural_understanding = {}

        try:

            architectural_understanding = (
                persian_architectural_understanding.interpret(
                    payload
                )
            )

        except Exception as e:

            print(
                "PERSIAN ARCH UNDERSTANDING ERROR:",
                e
            )

            architectural_understanding = {}


        # ==================================================
        # PHASE 2D-4 — ARCHITECTURAL CONVERSATION CONTEXT MERGE
        # Deterministic delta merge into the canonical session context.
        # Session-only; no persistent memory behaviour is changed here.
        # ==================================================

        architectural_context = {}
        effective_architectural_understanding = architectural_understanding

        try:

            architectural_context = (
                arch_context_store.apply_turn(
                    understanding=architectural_understanding,
                    raw_text=raw_text,
                    normalized_text=text,
                    context=context,
                )
            )

            effective_architectural_understanding = (
                architectural_context.get(
                    "active_architectural_understanding",
                    architectural_understanding
                )
            )

        except Exception as e:

            print(
                "ARCH CONTEXT MERGE ERROR:",
                e
            )

            architectural_context = {}
            effective_architectural_understanding = architectural_understanding


        # ==================================================
        # CONVERSATION_DOMAIN_V1 — DOMAIN ISOLATION
        #
        # The session's architectural context is merged across turns for
        # design continuity. It must NOT be injected into a turn that is
        # not about architecture (the "صدا میاد؟" contamination).
        #
        # The domain is classified here and the context is projected into
        # a SAFE form for injection. The session store is untouched, so the
        # architectural context is SUSPENDED, never deleted, and returns in
        # full on the next architectural turn.
        # ==================================================

        _domain_resolution = {
            "domain": {"domain": "architecture"},
            "architectural_context": architectural_context,
            "domain_block": {},
        }

        try:

            # CONVERSATIONAL_NATURALNESS_V1 — classify the CURRENT turn from
            # ITS OWN signal, not the session's carried-forward one. The frozen
            # `resolve_turn_domain` reads `turn_has_architectural_signal` from
            # the session context, which stays True after ANY architectural
            # turn and therefore mislabels later conversational turns as
            # architecture. The reclassifier uses the SAME frozen classifier
            # and the SAME projection; only the signal source differs.
            _domain_resolution = reclassify_turn_domain(
                text,
                architectural_context,
                understanding=architectural_understanding,
                context=context,
            )

            _domain_block = _domain_resolution.get("domain_block") or {}

            print(
                "\U0001f9ed CONVERSATION DOMAIN:",
                (_domain_resolution.get("domain") or {}).get("domain"),
                "| architectural context injected:",
                _domain_block.get("architectural_context_injected"),
                "| suspended:",
                _domain_block.get("architectural_context_suspended"),
            )

        except Exception as _domain_error:

            print(
                "CONVERSATION DOMAIN RESOLUTION ERROR:",
                _domain_error
            )

            # Fallback: the frozen resolver (previous behaviour).
            try:

                _domain_resolution = resolve_turn_domain(
                    text,
                    architectural_context,
                    understanding=architectural_understanding,
                    context=context,
                )

            except Exception as _domain_fallback_error:

                print(
                    "CONVERSATION DOMAIN FALLBACK ERROR:",
                    _domain_fallback_error
                )


        # ==================================================
        # PHASE 2D-3 — ARCHITECTURAL PROMPT COMPILATION
        # Deterministic English projection of the EFFECTIVE (merged) semantics.
        # Exposed on the routing context only; render execution is unchanged.
        # ==================================================

        architectural_compiled_prompt = {}

        try:

            if (
                effective_architectural_understanding
                and
                architectural_context.get(
                    "turn_has_architectural_signal",
                    bool(architectural_understanding)
                )
            ):

                # T2I_MODE_PROPAGATION_V1 — the validated render mode is the
                # authority for WHICH task the prompt describes. Without it
                # the compiler fell through to `scope == "facade"` and
                # described a fresh generation as a facade refinement.
                #
                # T2I_HIGH_RISE_SUBJECT_FIDELITY_V1 — the compiler is blind to
                # the floor count and the building type (neither is present on
                # the effective understanding), which is why the authoritative
                # prompt named the subject only as the bare tag "tower". The
                # two grounded inputs are therefore handed over explicitly:
                # the count from the single floor-count authority, and the
                # building type from the canonical terminology the request
                # actually matched. Both are additive context keys; when
                # neither is available the compiler emits no subject section.
                architectural_compiled_prompt = (
                    architectural_prompt_compiler.compile(
                        effective_architectural_understanding,
                        mode=(
                            context.get("mode")
                            if isinstance(context, dict)
                            else None
                        ),
                        context=self._subject_compile_context(
                            raw_text or text,
                            context,
                        ),
                    )
                )

                arch_context_store.set_compiled_prompt(
                    architectural_compiled_prompt
                )

        except Exception as e:

            print(
                "ARCH PROMPT COMPILE ERROR:",
                e
            )

            architectural_compiled_prompt = {}



        # ==================================================
        # CHAT_LANGUAGE_02 — CANONICAL LANGUAGE PATH
        #
        #   original user text
        #     -> deterministic normalization      (2D-1, upstream)
        #     -> architectural interpretation     (2D-2 / 2D-4)
        #     -> compiled English render prompt   (2D-3 + terminology)
        #
        # The terminology layer is deterministic and guarantees that the
        # required architectural concept families (facade / material /
        # light / style / camera / interior-exterior) survive the
        # Persian -> English transition.  The LLM is used ONLY as a
        # single bounded assist when the deterministic path produced
        # nothing usable.  No retry loop.
        # ==================================================

        terminology = {}

        compiled_render_prompt = ""

        compiled_prompt_source = "none"


        try:

            terminology = normalize_architectural_terms(
                raw_text or text
            )


            compiled_positive = ""

            if isinstance(architectural_compiled_prompt, dict):

                compiled_positive = (
                    architectural_compiled_prompt.get("positive_prompt")
                    or ""
                )


            compiled_render_prompt = augment_compiled_prompt(
                compiled_positive,
                terminology
            )


            if compiled_render_prompt:

                compiled_prompt_source = (
                    "deterministic_compiler+terminology"
                    if compiled_positive
                    else "deterministic_terminology"
                )


            # ----------------------------------------------
            # BOUNDED LLM ASSIST — single call, architectural only
            # ----------------------------------------------

            elif terminology.get("has_architectural_signal"):

                translated, error = bounded_llm_translate(
                    text,
                    self.llm.generate
                )

                if translated:

                    compiled_render_prompt = translated

                    compiled_prompt_source = "llm_bounded_translation"

                else:

                    print(
                        "⚠️ BOUNDED TRANSLATION UNAVAILABLE:",
                        error
                    )

                    compiled_prompt_source = "unavailable"

        except Exception as e:

            print(
                "CHAT LANGUAGE PATH ERROR:",
                e
            )


        # ==================================================
        # TEXT_TO_IMAGE_COMFY_03 — RENDER PRESET RESOLUTION
        #
        # Deterministic. Explicit request parameter beats inference.
        # No LLM call is ever made to choose a preset.
        # ==================================================

        preset_resolution = resolve_render_preset(

            terminology=terminology,

            explicit=(
                context.get("preset")
                if isinstance(context, dict)
                else None
            ),

        )


        print(
            "🎛️ PRESET RESOLUTION:",
            preset_resolution.get("name"),
            "| source:",
            preset_resolution.get("source"),
            "| reason:",
            preset_resolution.get("reason")
        )


        # TEXT_TO_IMAGE_COMFY_03B — optional explicit render seed
        render_seed = (
            context.get("seed")
            if isinstance(context, dict)
            else None
        )


        # ==================================================
        # CHAT_LANGUAGE_02 — RENDER HANDOFF TRACE
        #
        # Proves: original -> normalized -> compiled English ->
        # exact prompt received by RenderRuntime.
        # ==================================================

        render_handoff_trace = {

            "contract": "RenderHandoffTraceV1",

            "session_id": session_bundle.get("session_id"),

            "isolated_session": session_bundle.get("isolated", False),

            "original_user_prompt": raw_text,

            "normalized_prompt": text,

            "detected_language": payload.get(
                "detected_language",
                "unknown"
            ),

            "terminology_families": terminology.get("families", []),

            "terminology_terms": terminology.get("canonical_terms", []),

            "architectural_understanding_scope": (
                effective_architectural_understanding or {}
            ).get("scope"),

            "compiled_prompt_contract": (
                architectural_compiled_prompt or {}
            ).get("contract"),

            "compiled_render_prompt": compiled_render_prompt,

            "compiled_prompt_source": compiled_prompt_source,

            # TEXT_TO_IMAGE_COMFY_03 — preset chosen for this request
            "preset": preset_resolution.get("name"),
            "preset_source": preset_resolution.get("source"),
            "preset_reason": preset_resolution.get("reason"),

            "render_runtime_received_prompt": None,

            "render_runtime_received_compiled": None,

            "render_runtime_final_prompt": None,

            "render_prompt_source": None,

        }


        # raw render-handoff-trace print removed (LOG_SENSITIVE_OUTPUT_FIX)


        # ==================================================
        # RENDER_SEMANTIC_FIDELITY_V1 — FAIL-CLOSED GATE
        #
        # The Persian request is compiled into ONE English render instruction
        # and that instruction is then VERIFIED against the Persian
        # constraints. A render request may only proceed when the verdict is
        # PASS; any missing, reversed or contradictory instruction BLOCKS with
        # a specific reason.  Contract only: no RenderRuntime, no ComfyUI.
        # ==================================================

        render_instruction = {}

        render_fidelity = {}

        try:

            _fidelity_relevant = bool(
                image
                or self.should_render_design(text)
                or architectural_compiled_prompt
            )

            if _fidelity_relevant:

                render_instruction = build_render_instruction(
                    raw_text or text,
                    understanding=effective_architectural_understanding,
                    compiled=architectural_compiled_prompt,
                    references=(
                        context.get("references")
                        if isinstance(context, dict)
                        else None
                    ),
                    # FACADE-04D.3C-9P-B12 — a user confirmation is resolved
                    # ONLY through the trusted boundary (current-turn carrier,
                    # else THIS session's persisted USER-authored turns). An
                    # arbitrary dictionary is never promoted.
                    user_geometry=self._trusted_user_geometry(context),
                )

                # T2I_TALL_TOWER_PORTRAIT_PRESET_V1 — the first preset pass
                # intentionally uses terminology only.  Once the existing
                # render-instruction owner has produced a trusted requested
                # floor/framing contract, refine the same preset resolution.
                # Explicit UI presets retain precedence inside the resolver.
                preset_resolution = resolve_render_preset(
                    terminology=terminology,
                    explicit=(
                        context.get("preset")
                        if isinstance(context, dict)
                        else None
                    ),
                    architectural_instruction=render_instruction,
                )

                render_handoff_trace["preset"] = preset_resolution.get("name")
                render_handoff_trace["preset_source"] = (
                    preset_resolution.get("source")
                )
                render_handoff_trace["preset_reason"] = (
                    preset_resolution.get("reason")
                )

                render_fidelity = validate_render_fidelity(
                    raw_text or text,
                    contract=render_instruction,
                )

                print(
                    "🛡️ RENDER FIDELITY:",
                    render_fidelity.get("status"),
                    "|",
                    render_fidelity.get("reason_code"),
                    "| may_proceed:",
                    render_fidelity.get("may_proceed_to_render"),
                )

        except Exception as e:

            print(
                "RENDER FIDELITY ERROR:",
                e
            )

            render_instruction = {}

            render_fidelity = {
                "contract": "RenderSemanticFidelityV1",
                "status": "BLOCKED",
                "reason_code": "VALIDATOR_ERROR",
                "reason": (
                    "the fidelity gate could not run: "
                    + type(e).__name__ + ": " + str(e)
                ),
                "may_proceed_to_render": False,
            }



        # The trace is the audit surface: the instruction and its verdict ride
        # on it, so the compiled English prompt and its fidelity are provable
        # from ONE place.
        render_handoff_trace["render_instruction"] = render_instruction

        render_handoff_trace["render_fidelity"] = render_fidelity


        # ==================================================
        # PHASE 2D-5 — REFERENCE IMAGE ARCHITECTURAL UNDERSTANDING
        # Analysis only. Runs ONLY when a readable image reference is present.
        # With no vision provider configured it returns PROVIDER_UNAVAILABLE
        # (never fabricated semantics).  Exposed on the routing context only;
        # the textual reference policy from 2D-2/2D-4 remains authoritative.
        # ==================================================

        reference_architectural_analysis = {}

        try:

            _reference_candidate = None

            if isinstance(image, str):

                _reference_candidate = image

            elif isinstance(image, dict) and image.get("path"):

                _reference_candidate = image

            if _reference_candidate:

                reference_architectural_analysis = (
                    reference_image_understanding.analyze(
                        _reference_candidate,
                        source_type="reference_image",
                        context=context,
                    )
                )

        except Exception as e:

            print(
                "REFERENCE ANALYSIS ERROR:",
                e
            )

            reference_architectural_analysis = {}



        # ==================================================
        # FACADE-03 — DUAL-IMAGE ARCHITECTURAL VISION (A/B)
        #
        # When FACADE-02 supplied validated A/B reference assets, BOTH images
        # are analysed by the REAL Ollama vision provider through the SAME
        # 2D-5 analyzer, each with its OWN role-bound prompt and SEPARATE
        # evidence.  Image A = facade style reference (appearance only);
        # Image B = target building (geometry authority).  Geometry is never
        # copied from A into B.  Analysis only: no render, no ComfyUI.
        # ==================================================

        reference_architectural_analysis_ab = {}

        _ab_refs = (
            context.get("references")
            if isinstance(context, dict)
            else None
        )

        _ab_pair_requested = bool(
            isinstance(_ab_refs, dict)
            and _ab_refs.get("A")
            and _ab_refs.get("B")
        )

        # ==================================================
        # FACADE-04D.3C-5B — H1: SAFE COMFYUI GPU RELEASE (BEFORE VISION)
        #
        # The vision model and the FLUX/ComfyUI stack cannot be resident in
        # the ~16 GiB card at the same time. Before the A/B architectural
        # analysis, ComfyUI's cached models are released through ComfyUI's own
        # /free API — but ONLY when its queue is empty, so a running or
        # pending render is never interrupted. Every failure mode fails
        # closed: no vision call and no render happen when the GPU could not
        # be provably released. ComfyUI is never restarted or killed.
        # ==================================================

        _gpu_handoff = {
            "contract": "GpuHandoffV1",
            "version": "1.0",
            "h1": None,
            "h2": None,
        }

        render_handoff_trace["gpu_handoff"] = _gpu_handoff

        if _ab_pair_requested:

            from core.runtime.gpu_handoff_v1 import release_comfyui_for_vision

            _h1 = release_comfyui_for_vision()

            _gpu_handoff["h1"] = _h1

            print(
                "🧮 GPU HANDOFF H1:",
                _h1.get("status"),
                "|",
                _h1.get("reason"),
                "| freed_bytes:",
                _h1.get("released_bytes"),
            )

            if _h1.get("status") not in ("released", "not_running"):

                print(
                    "⛔ DUAL-IMAGE RENDER BLOCKED: GPU handoff H1",
                    _h1.get("reason"),
                )

                return {
                    "type": "render_blocked",
                    "status": "blocked",
                    "reason": "gpu_handoff_h1_" + str(_h1.get("reason")),
                    "gpu_handoff": _gpu_handoff,
                    "message": (
                        "رندر دو‐تصویری متوقف شد: حافظه گرافیکی ComfyUI "
                        "به‌صورت ایمن آزاد نشد."
                    ),
                    "render_handoff": render_handoff_trace,
                }

        try:

            if _ab_pair_requested:

                from core.vision.facade_reference_vision_provider_v1 import (
                    analyze_ab_references,
                )

                reference_architectural_analysis_ab = analyze_ab_references(
                    _ab_refs,
                    context=context,
                )

        except Exception as e:

            print(
                "DUAL REFERENCE ANALYSIS ERROR:",
                e
            )

            reference_architectural_analysis_ab = {}

        render_handoff_trace["reference_architectural_analysis_ab"] = (
            reference_architectural_analysis_ab
        )

        # ==================================================
        # FACADE-04A — REBUILD THE RENDER INSTRUCTION AFTER A/B ANALYSIS
        #
        # The instruction block above runs BEFORE the A/B vision analysis, so
        # it cannot see the real observations. It is rebuilt HERE, after the
        # analysis, with the A/B evidence attached. `build_render_instruction`
        # is deterministic — it calls no model — so this is a data-dependency
        # fix, NOT a duplicate inference.
        # ==================================================

        _dual_render_ready = False

        if reference_architectural_analysis_ab:

            try:

                _ab_relevant = bool(
                    image
                    or self.should_render_design(text)
                    or architectural_compiled_prompt
                )

                if _ab_relevant:

                    # FACADE-04D.3C-9P-B12 — a user confirmation is resolved
                    # ONLY through the trusted boundary: the current-turn
                    # `context["user_geometry"]` carrier (written by app.py
                    # from the incoming message), else THIS session's
                    # persisted USER-authored turns. Assistant text, model
                    # output, summaries and vision observations can never
                    # become a confirmation. When nothing is trustworthy this
                    # is None and behaviour is unchanged.
                    _user_geometry = self._trusted_user_geometry(context)

                    render_instruction = build_render_instruction(
                        raw_text or text,
                        understanding=effective_architectural_understanding,
                        compiled=architectural_compiled_prompt,
                        references=(
                            context.get("references")
                            if isinstance(context, dict)
                            else None
                        ),
                        reference_analysis_ab=reference_architectural_analysis_ab,
                        user_geometry=_user_geometry,
                    )

                    render_fidelity = validate_render_fidelity(
                        raw_text or text,
                        contract=render_instruction,
                    )

                    print(
                        "🛡️ RENDER FIDELITY (A/B):",
                        render_fidelity.get("status"),
                        "|",
                        render_fidelity.get("reason_code"),
                        "| may_proceed:",
                        render_fidelity.get("may_proceed_to_render"),
                    )

            except Exception as e:

                print("RENDER FIDELITY A/B ERROR:", e)

                render_fidelity = {
                    "contract": "RenderSemanticFidelityV1",
                    "status": "BLOCKED",
                    "reason_code": "VALIDATOR_ERROR",
                    "reason": (
                        "the A/B fidelity gate could not run: "
                        + type(e).__name__ + ": " + str(e)
                    ),
                    "may_proceed_to_render": False,
                }

            render_handoff_trace["render_instruction"] = render_instruction

            render_handoff_trace["render_fidelity"] = render_fidelity

        # ==================================================
        # RENDER_INSTRUCTION_HANDOFF_V1 — EXPOSE THE CONSTRAINTS
        #
        # MEASURED DEFECT (V4.1 §3.2): the instruction was built here and then
        # only stored on the trace. `core/render/` never referenced it, so the
        # sampler prompt carried none of it — not the curved-form rule, not the
        # temporary-object rule, not even the observed floor count.
        #
        # The runtime receives the BOUNDED CONSTRAINT BLOCK, not the 2.7k-char
        # narrative: the T5 budget is finite and the descriptive half is
        # already in the compiled prompt. It travels on the request-scoped
        # routing context, which `_route_image_edit` already receives, so no
        # call signature changes.
        # ==================================================

        # RESOLVED_T2I_ROUTING_HANDOFF_V1 — the publication itself now lives in
        # ONE method (`_publish_render_instruction`), so the SAME handoff can
        # also run from the routing boundary when the ROUTE — not the wording —
        # resolved the turn into a render. Contract, provenance rule and guards
        # are unchanged: still only a non-empty block is published.
        self._publish_render_instruction(
            context,
            render_instruction,
            render_handoff_trace,
        )

        # FACADE-04A — dual-image readiness. A dual-image facade render is ready
        # ONLY when BOTH role-bound analyses are real AND the fidelity verdict
        # is PASS. A failed/missing B, or a BLOCKED verdict, is never "ready".
        _ab_roles = (
            reference_architectural_analysis_ab.get("roles")
            if isinstance(reference_architectural_analysis_ab, dict)
            else None
        )

        _ab_analysis_a = (
            reference_architectural_analysis_ab.get("A")
            if isinstance(reference_architectural_analysis_ab, dict)
            else None
        )

        _ab_analysis_b = (
            reference_architectural_analysis_ab.get("B")
            if isinstance(reference_architectural_analysis_ab, dict)
            else None
        )

        def _ab_analysis_ok(analysis):

            return bool(analysis) and analysis.get("analysis_status") not in (
                None, "PROVIDER_UNAVAILABLE", "FAILED",
            )

        _ab_pair_present = bool(
            isinstance(context, dict)
            and isinstance(context.get("references"), dict)
            and context["references"].get("A")
            and context["references"].get("B")
        )

        # FACADE-04A — an UNRESOLVED floor-count conflict between the request
        # and the floor count observed on the target building also prevents the
        # dual-image render. The conflict is a SOFT observation signal (it is
        # never turned into a hard geometric constraint), so it is surfaced
        # here as "not ready" rather than as a fidelity BLOCK.
        #
        # FACADE-04D.3C-9P-B1 — the same is true when a USER_CONFIRMATION and
        # the raw Vision observation DISAGREE: the provenance carries
        # `conflict: true`, and no automatic render permission is granted while
        # an unresolved geometry conflict exists.
        _ab_floor_conflict = (
            (render_instruction.get("reference_analysis_ab") or {}).get(
                "floor_count_conflict"
            )
            if isinstance(render_instruction, dict)
            else None
        )

        _ab_provenance_conflict = bool(
            ((render_instruction.get("constraints") or {}).get(
                "floor_count_provenance"
            ) or {}).get("conflict")
            if isinstance(render_instruction, dict)
            else False
        )

        _dual_render_ready = bool(
            _ab_pair_present
            and _ab_analysis_ok(_ab_analysis_a)
            and _ab_analysis_ok(_ab_analysis_b)
            and (render_fidelity or {}).get("may_proceed_to_render") is True
            and not _ab_floor_conflict
            and not _ab_provenance_conflict
        )

        render_handoff_trace["dual_image_render"] = {
            "pair_present": _ab_pair_present,
            "a_analyzed": _ab_analysis_ok(_ab_analysis_a),
            "b_analyzed": _ab_analysis_ok(_ab_analysis_b),
            "roles": _ab_roles,
            "geometry_authority": (
                (_ab_roles or {}).get("geometry_authority")
                if isinstance(_ab_roles, dict)
                else None
            ),
            "fidelity_status": (render_fidelity or {}).get("status"),
            "fidelity_may_proceed": (render_fidelity or {}).get("may_proceed_to_render"),
            "floor_count_conflict": _ab_floor_conflict,
            "floor_count_provenance_conflict": _ab_provenance_conflict,
            "floor_count_provenance": (
                (render_instruction.get("constraints") or {}).get(
                    "floor_count_provenance"
                )
                if isinstance(render_instruction, dict)
                else None
            ),
            "ready_to_render": _dual_render_ready,
        }



        # ==================================================
        # PHASE 2D-6 — APPROVED DESIGN → RENDER CONTRACT
        # Contract only: binds a render request to the explicitly approved
        # design.  Built only when an approved design exists AND a render /
        # facade-visualization intent is relevant.  No render execution,
        # no ComfyUI, no design mutation.
        # ==================================================

        approved_render_contract = {}

        try:

            _render_relevant = bool(
                image
                or self.should_render_design(text)
                or architectural_compiled_prompt
            )

            if _render_relevant:

                approved_render_contract = (
                    approved_design_render_contract.build(
                        self.state.get(),
                        understanding=effective_architectural_understanding,
                        compiled_prompt=architectural_compiled_prompt,
                        reference_analysis=reference_architectural_analysis,
                        reference_analysis_ab=reference_architectural_analysis_ab,
                        context=context,
                    )
                )

        except Exception as e:

            print(
                "APPROVED RENDER CONTRACT ERROR:",
                e
            )

            approved_render_contract = {}



        # ==================================================
        # PHASE 2D-7 — RENDER REVISION / DELTA UNDERSTANDING
        # Semantic delta only.  Resolves a REAL base render from actual
        # state/history (never invented), produces appearance-only delta
        # operations, and blocks geometry changes with DESIGN_REVISION_REQUIRED.
        # No render execution, no ComfyUI, no design mutation.  Request-scoped
        # and exposed on the routing context only (nothing persisted).
        # ==================================================

        render_revision = {}

        try:

            if approved_render_contract:

                _state = self.state.get() or {}

                _render_state = {}

                _asset = _state.get("last_render_asset")

                if isinstance(_asset, dict) and (
                    _asset.get("filename") or _asset.get("path")
                ):

                    _render_state["last_render_asset"] = _asset

                if isinstance(_state.get("render_history"), (list, tuple)):

                    _render_state["render_history"] = _state["render_history"]

                _delta_context = {}

                if isinstance(architectural_context, dict):

                    _rid = architectural_context.get("active_render_id")

                    if _rid not in (None, "", []):

                        _render_state["active_render_id"] = _rid

                    for _key in (
                        "active_targets",
                        "active_materials",
                        "active_reference_id",
                    ):

                        if architectural_context.get(_key) not in (None, {}, []):

                            _delta_context[_key] = architectural_context.get(_key)

                    if architectural_context.get("active_floor_count") is not None:

                        _delta_context["approved_floor_count"] = (
                            architectural_context.get("active_floor_count")
                        )

                render_revision = render_revision_delta.build(
                    approved_render_contract,
                    understanding=effective_architectural_understanding,
                    render_state=_render_state,
                    context=_delta_context,
                    prior_revision=_state.get("last_render_revision_delta"),
                )

        except Exception as e:

            print(
                "RENDER REVISION DELTA ERROR:",
                e
            )

            render_revision = {}



        # ==================================================
        # SAVE CURRENT USER PROMPT
        # ==================================================

        try:


            if (

                text

                and

                text.strip()

            ):


                self.state.update({

                    "last_prompt":

                        text.strip()

                })


                # raw user-prompt print removed (LOG_SENSITIVE_OUTPUT_FIX)


        except Exception as e:


            print(

                "CURRENT PROMPT SAVE ERROR:",

                e

            )



        # raw image-handle print removed (LOG_SENSITIVE_OUTPUT_FIX)


        # LOG_PAYLOAD_LEAK_FIX — two raw debug prints were removed here:
        # the former payload dump and the former image-value dump. They
        # wrote the user's raw input and the attachment handle into
        # core_api.log (via the stdout -> logging redirection) and were
        # consumed by nothing. No bounded replacement is emitted: this
        # module has no logger, and any print would re-enter the same log.

        # ==================================================
        # VISION_IMAGE_REGISTRY_04 — IMAGE PATH
        #
        # The image is ALWAYS persisted and registered first, then
        # analysed by the real vision provider, and only then routed.
        #
        # An image + text message is NOT automatically an edit request:
        #   analyze   -> answer the question from visual evidence
        #   edit      -> existing img2img path (execution is Phase 05)
        #   reference -> point at an existing session image
        # ==================================================

        session_key = session_bundle.get("session_id")

        image_intent = {}
        image_record = None
        image_understanding = {}
        image_reference = {}
        region_reference = {}

        referenced_image = None


        # ==================================================
        # FACADE-04D.3C-4 — VERIFIED DUAL-IMAGE PRECEDENCE
        #
        # A dual-image request is declared ONLY by the verified request
        # boundary: ``context["references"]`` carrying BOTH role keys "A"
        # (style reference) and "B" (target building). The user's text and any
        # model-generated declaration are NEVER treated as proof that both
        # images exist.
        #
        # app.py legitimately exposes IMAGE B as the legacy single ``image``
        # for a dual upload, so without this guard the single-image routing
        # below (`if image:` -> INTENT_EDIT -> `_route_image_edit()`) consumes
        # the request BEFORE the FACADE-04D.2 dual-image dispatch, silently
        # selecting `flux_img2img.json`, dropping IMAGE A and changing denoise.
        #
        # A declared pair is handed to the dual-image dispatch, which fails
        # closed when the A/B contract is incomplete; it is never degraded to
        # single-image rendering.
        # ==================================================

        _dual_references = (
            context.get("references")
            if isinstance(context, dict)
            else None
        )

        _verified_dual_pair = bool(
            isinstance(_dual_references, dict)
            and "A" in _dual_references
            and "B" in _dual_references
        )

        if _verified_dual_pair:

            print(
                "🖼️ VERIFIED DUAL-IMAGE PAIR DECLARED (A + B)"
            )


        # ==================================================
        # IMAGE_TO_IMAGE_05 — PRECISE-GEOMETRY GUARD
        #
        # A dimensioned or localized geometric edit must be refused
        # BEFORE ImageHandler, RenderRuntime or ComfyUI are ever
        # reached, whether the image arrives as an upload or is
        # already registered in this session.
        #
        # The guard fires only when the message really carries a
        # geometry signal AND the turn has an image context, so
        # ordinary global appearance edits and plan-level requests are
        # never blocked.
        #
        # T2I_ARCHITECTURAL_FEATURE_HANDOFF_V1 — an image context ALONE is not
        # evidence that this turn EDITS an image. Every successful render
        # registers its output, so a session that has rendered once reports
        # `count > 0` forever, and a later fresh text-to-image request was
        # refused as if it were a localized edit of that old render. An
        # explicit, validated NEW-GENERATION signal now decides instead; every
        # other request keeps exactly the previous refusal behaviour.
        # ==================================================

        _explicit_t2i = self._explicit_text_to_image_turn(context)

        if text.strip():

            # MASK_SOURCE_BINDING_V1 — this site runs BEFORE the image is
            # registered, so the source identity is resolved from the request
            # image bytes or the session's existing active image. A mask that
            # cannot be bound to either is refused.
            _geometry_guard = detect_unsupported_geometry_edit(
                text,
                context=guard_context_with_source(
                    context,
                    session_key,
                    image=image,
                    image_record=image_registry.active(session_key),
                ),
            )

            if _geometry_guard.get("unsupported"):

                _has_image_context = bool(image) or (
                    image_registry.count(session_key) > 0
                )

                # A validated explicit text-to-image turn is NOT an edit, so a
                # merely-registered image must not turn it into one. A real
                # uploaded/attached image still does, and any twin/clone
                # supplied for this turn still does.
                _registry_only_context = (
                    _has_image_context
                    and not image
                    and not _verified_dual_pair
                )

                _refuse = _has_image_context and not (
                    _explicit_t2i and _registry_only_context
                )

                # ARCHITECTURAL REASONING INTEGRATION V8 — a current uploaded
                # image plus an explicit image-edit mode can carry a plain
                # element-removal request to the evidence-aware decision gate.
                # Only non-dimensioned removal is deferred; movement, resize,
                # rotation and dimensioned edits retain the historical
                # pre-route refusal. ImageHandler then fails closed unless the
                # requested subject is evidence-backed and a verified
                # caller-supplied mask provides spatial scope.
                _evidence_gated_upload_removal = bool(
                    image
                    and isinstance(context, dict)
                    and str(context.get("mode") or "").strip().lower()
                    == "image_to_image"
                    and _v8_plain_evidence_gated_removal(text, _geometry_guard)
                )

                if _evidence_gated_upload_removal:
                    _refuse = False
                    # Downstream guards run the identical legacy detector and
                    # must honour the same deferral instead of re-refusing it.
                    context["v8_evidence_gated_removal"] = True
                    print(
                        "✅ ELEMENT REMOVAL DEFERRED TO V8 EVIDENCE GATE"
                    )

                if _refuse:

                    _is_region, _, _ = is_region_reference(text)

                    _geometry_guard["region_reference"] = _is_region

                    print(
                        "⛔ UNSUPPORTED GEOMETRY EDIT (pre-routing guard):",
                        _geometry_guard.get("reason")
                    )

                    return self._unsupported_geometry_response(
                        text,
                        _geometry_guard,
                        image_registry.active(session_key),
                        {},
                    )

                print(
                    "✅ T2I NEW-GENERATION ROUTE (guard not an image edit):",
                    _geometry_guard.get("reason")
                )


        # FACADE-04D.3C-4 — a declared A/B pair must NOT be consumed by the
        # single-image upload / edit / analyse routing. It falls through to
        # the dual-image dispatch instead.
        # R2_UI_ANALYZE_MISROUTING_FIX_V1 — the validated manual mode is
        # resolved ONCE here, at a scope every image gate can read. An explicit
        # "Analyze Image" must not be overridden by the text classifier, by a
        # lingering `waiting_image_edit` flag, or by the active asset's history.
        _manual_image_mode = (
            str(context.get("mode") or "").strip().lower()
            if isinstance(context, dict)
            and str(context.get("routing_source") or "").lower() == "manual"
            else ""
        )

        if image and not _verified_dual_pair:

            image_record = self._register_session_image(
                session_key,
                image,
            )

            # R2_UI_ANALYZE_MISROUTING_FIX_V1 — the explicit UI mode decides.
            # `analyze_image` must never fall through to the text classifier,
            # which reads the deictic «این ساختمان» as an edit instruction.
            image_intent = _manual_image_intent(
                _manual_image_mode,
                text,
                self.intent_router,
            )

            print(
                "🖼️ IMAGE INTENT:",
                image_intent.get("intent"),
                "|",
                image_intent.get("reason")
            )


            # ----------------------------------------------
            # UPLOAD ONLY — registered, analysis deferred
            # ----------------------------------------------

            if image_intent.get("intent") == INTENT_UPLOAD_ONLY:

                print(
                    "📷 IMAGE UPLOAD ONLY - WAITING FOR INSTRUCTION"
                )

                result = self.image_handler.handle_image_upload_only(
                    image
                )

                return self._finalize_image_turn(
                    result,
                    image_record,
                    image_understanding,
                    image_intent,
                    image_reference,
                    region_reference,
                )


            # ----------------------------------------------
            # EDIT — preserved existing path (Phase 05 executes)
            # ----------------------------------------------

            if image_intent.get("intent") == INTENT_EDIT:

                print(
                    "🖼️ IMAGE EDIT INTENT - ROUTING TO IMAGE EDIT"
                )

                if image_record:

                    # R4_PHOTO_FAST_PATH_CLOSURE_V1 — an accepted photographic
                    # colour-balance warmth edit is a deterministic per-pixel
                    # operation on the already authoritative source, so the V8
                    # observation it used to wait for is skipped for exactly
                    # that case. Every other request keeps the observation.
                    _photo_fast = self._photo_warmth_fast_path(
                        text,
                        image_record,
                    )

                    if _photo_fast.get("ready"):

                        image_understanding = {}

                        print(
                            "⚡ PHOTO FAST PATH — V8 OBSERVATION SKIPPED:",
                            _photo_fast.get("reason"),
                        )

                    else:

                        # V8 — an edit decision must depend on the selected
                        # source's current evidence. ``analyze_record`` reuses
                        # a current cached analysis; otherwise it runs the
                        # existing vision boundary before any render path is
                        # entered.
                        image_understanding = analyze_session_image(
                            session_key,
                            image_record["image_id"],
                        )

                    result = self._route_image_edit(
                        text,
                        image_record,
                        image_reference,
                        compiled_render_prompt,
                        terminology,
                        render_seed,
                        context,
                        image_understanding,
                    )

                else:

                    result = self._router_edit_route(
                        text,
                        image,
                        context,
                        compiled_render_prompt,
                        terminology,
                        render_seed,
                    )

                return self._finalize_image_turn(
                    result,
                    image_record,
                    image_understanding,
                    image_intent,
                    image_reference,
                    region_reference,
                )


            # ----------------------------------------------
            # ANALYZE / REFERENCE — real analysis, grounded answer
            # ----------------------------------------------

            if image_record:

                image_understanding = analyze_session_image(
                    session_key,
                    image_record["image_id"],
                )

            image_reference = resolve_session_reference(
                session_key,
                text,
            )

            return self._answer_about_image(
                text,
                image_record,
                image_understanding,
                image_intent,
                image_reference,
            )


        # ==================================================
        # VISION_IMAGE_REGISTRY_04 — TEXT-ONLY REFERENCE
        #
        # "رندر قبلی رو توضیح بده" with no new upload must resolve to
        # an image already in this session.
        # ==================================================

        # CODER ROUTING REGRESSION FIX — an explicit request to CREATE a code
        # file must reach the existing Coder boundary below.  Long numbered
        # specifications often contain ordinary deictic prose such as «این
        # نسخه»; the image-reference resolver can classify that as an active
        # image reference and, with no session images, return
        # ``no_images_in_session`` before intent/Coder dispatch is evaluated.
        #
        # Reuse the strict CODER-05E/F predicate: it requires both an explicit
        # creation/generation action and the established ``code_file``
        # programming classification.  This does not turn incidental mentions
        # of Python, files, GUIs, or images into code requests, and genuine
        # image questions continue through this reference boundary.
        # CODER-HISTORY-REUSE-01 — an explicit RESTORE of already-displayed
        # source must also reach the Coder boundary. Measured 2026-10-26 in
        # project_20f920b5: the restore request carried «همین گفت‌وگو» and
        # «پیش‌نویس», the reference resolver read that as an active image
        # reference, and the user got `no_images_in_session` instead of the
        # restored draft. The predicate requires an explicit restore action
        # AND a code-source reference, so "تصویر قبلی" / "رندر قبلی" keep
        # flowing through this boundary unchanged.
        if (
            text.strip()
            and not _verified_dual_pair
            and not self._code_file_creation_turn(text)
            and not self._code_history_reuse_turn(text)
        ):

            image_reference = resolve_session_reference(
                session_key,
                text,
            )

            if image_reference.get("status") == "resolved":

                referenced_image = image_registry.get(
                    session_key,
                    image_reference.get("target_image_id"),
                )

            elif (
                image_reference.get("status") == "unresolved"
                and image_reference.get("reference_kind")
            ):

                return self._unresolved_reference_response(
                    text,
                    image_reference,
                    session_key,
                )


        if referenced_image and not _verified_dual_pair:

            # R4_PHOTO_FAST_PATH_CLOSURE_V1 — `classify_image_intent()` is
            # deterministic and does not read the observation, so it is
            # resolved first. That lets an accepted photographic warmth edit
            # skip an observation it cannot use, while every other request
            # still observes the source before it is treated as an edit.
            image_intent = classify_image_intent(
                text,
                self.intent_router,
            )

            # The fast path is only ever an EDIT decision. If this turn is
            # not classified as an edit, the observation must still run —
            # otherwise an analysis turn would answer with no evidence.
            _photo_fast = (
                self._photo_warmth_fast_path(text, referenced_image)
                if image_intent.get("intent") == INTENT_EDIT
                else {"ready": False, "reason": "not_an_edit"}
            )

            if _photo_fast.get("ready"):

                image_understanding = {}

                print(
                    "⚡ PHOTO FAST PATH — V8 OBSERVATION SKIPPED:",
                    _photo_fast.get("reason"),
                )

            else:

                image_understanding = analyze_session_image(
                    session_key,
                    referenced_image["image_id"],
                )

            if image_intent.get("intent") == INTENT_EDIT:

                result = self._route_image_edit(
                    text,
                    referenced_image,
                    image_reference,
                    compiled_render_prompt,
                    terminology,
                    render_seed,
                    context,
                    image_understanding,
                )

                return self._finalize_image_turn(
                    result,
                    referenced_image,
                    image_understanding,
                    image_intent,
                    image_reference,
                    region_reference,
                )

            return self._answer_about_image(
                text,
                referenced_image,
                image_understanding,
                image_intent,
                image_reference,
            )



        # ==================================================
        # IMAGE INPUT PRIORITY
        # ==================================================



        # ==================================================
        # CONTINUE IMAGE EDIT SESSION
        # ==================================================


        try:


            current_state = self.state.get()


        except Exception:


            current_state = {}



        if (

            current_state.get(

                "waiting_image_edit",

                False

            )

            and

            text

            # R2_UI_ANALYZE_MISROUTING_FIX_V1 — an explicit Analyze Image turn
            # must not be captured by a lingering edit session. The user asked
            # to read the image, not to continue editing it.
            and _manual_image_mode != "analyze_image"

            # RENDER_FOLLOWUP_V1 — same rule for an explicitly validated NEW
            # GENERATION turn: a successful render leaves `waiting_image_edit`
            # set, and an explicit text-to-image request must still generate.
            and not self._explicit_text_to_image_turn(context)

            and

            self.intent_router.is_image_edit_request(text)

            and

            # FACADE-04D.3C-4 — a declared A/B pair keeps the dual-image route
            # even when a previous turn left `waiting_image_edit` set.
            not _verified_dual_pair

        ):


            print(

                "🖼️ CONTINUING IMAGE EDIT SESSION"

            )


            # IMAGE_TO_IMAGE_05 — route continuations through the same
            # guarded path, chaining from the latest registered image.
            _active_record = image_registry.active(session_key)


            if _active_record:

                result = self._route_image_edit(
                    text,
                    _active_record,
                    {},
                    compiled_render_prompt,
                    terminology,
                    render_seed,
                    context,
                )

                return self._finalize_image_turn(
                    result,
                    _active_record,
                    {},
                    {"intent": INTENT_EDIT, "reason": "edit_continuation"},
                    {},
                    {},
                )


            return self._router_edit_route(
                text,
                None,
                context,
                compiled_render_prompt,
                terminology,
                render_seed,
            )



        # ==================================================
        # INTENT ROUTER
        # ==================================================


        _router_edit_delta = compile_edit_delta(text)

        intent_context = {


            "conversation_state":

                self.state.get(),


            # PRODUCT_INTEGRATION_V1 — the already validated UI strategy and
            # the existing top-level conversation decision now reach the
            # router.  Auto mode remains non-authoritative.
            "mode":

                context.get("mode") if isinstance(context, dict) else None,


            "routing_source":

                context.get("routing_source") if isinstance(context, dict) else None,


            "dual_image_pair":

                _verified_dual_pair,


            "conversation_intent":

                _cib_decision,


            "image_edit_delta":

                _router_edit_delta,


            "last_design":

                self.state.get().get(

                    "last_design",

                    {}

                ),


            "previous_design":

                self.state.get().get(

                    "last_design",

                    {}

                ),


            "active_project":

                self.state.get().get(

                    "active_project"

                ),


            # PHASE 2D-1 — request boundary provenance (local, non-persistent)
            "raw_text":

                raw_text,


            "normalized_text":

                text,


            "detected_language":

                payload.get(
                    "detected_language",
                    "unknown"
                ),


            # PHASE 08 — conversational turn semantics (deterministic).
            # Exposed for routing observability; neutral turns route
            # exactly as before.
            "turn_semantics":

                (teaching_turn or {}).get("semantics"),


            "turn_kind":

                (teaching_turn or {}).get("turn_kind"),


            "reply_language":

                (teaching_turn or {}).get("language"),


            "teaching_candidate":

                (teaching_turn or {}).get("candidate"),


            # PHASE 2D-2 — canonical Persian architectural semantic intent
            "architectural_understanding":

                architectural_understanding,


            # PHASE 2D-3 — compiled architectural prompt contract
            "architectural_compiled_prompt":

                architectural_compiled_prompt,


            # CHAT_LANGUAGE_02 — compiled English render prompt
            # (deterministic compiler + terminology, or bounded assist)
            "compiled_render_prompt":

                compiled_render_prompt,


            # TEXT_TO_IMAGE_COMFY_03 — resolved render preset
            "preset_resolution":

                preset_resolution,


            "terminology":

                terminology,


            "render_handoff_trace":

                render_handoff_trace,


            # PHASE 2D-4 — canonical session architectural context
            "architectural_context":

                architectural_context,


            # PHASE 2D-5 — reference image architectural analysis (evidence only)
            "reference_architectural_analysis":

                reference_architectural_analysis,


            # PHASE 2D-6 — approved design → render contract (contract only)
            "approved_design_render_contract":

                approved_render_contract,


            # PHASE 2D-7 — render revision / delta (semantic delta only)
            "render_revision_delta":

                render_revision,


            # RENDER_SEMANTIC_FIDELITY_V1 — English render instruction and its
            # fail-closed verdict (contract only; nothing is rendered here)
            "render_instruction":

                render_instruction,


            "render_fidelity":

                render_fidelity

        }



        # raw intent-context dump removed (LOG_SENSITIVE_OUTPUT_FIX)



        # raw user-text/image print removed (LOG_SENSITIVE_OUTPUT_FIX)


        # ======================================================
        # INTENT RESULT SAFETY INIT
        # ======================================================

        intent_result = None


        # ======================================================
        # IMAGE EDIT CONTINUATION OVERRIDE
        # ======================================================

        conversation_state = intent_context.get(
            "conversation_state",
            {}
        )


        # RENDER_FOLLOWUP_V1 — a colloquial follow-up re-render
        # ("رندر شبش بگیر" / "از یه زاویه دیگه رندر بگیر") is an edit of the
        # active image. It carries no contiguous `_EDIT_PHRASES` hit and its
        # delta is often `generic_edit`, so without this it was routed as a
        # fresh design brief and answered with the text-only stub.
        _render_followup = detect_render_followup(text)

        _state_edit_signal = resolve_state_edit_signal(
            text,
            _router_edit_delta,
            self.intent_router,
            _render_followup,
        )

        state_override = (

            # R2_UI_ANALYZE_MISROUTING_FIX_V1 — an explicit Analyze Image turn
            # is never an edit-state continuation, whatever the asset history.
            _manual_image_mode != "analyze_image"

            # RENDER_FOLLOWUP_V1 — neither is an explicitly validated NEW
            # GENERATION turn. `waiting_image_edit` is set by the image
            # handler after an upload or an edit, and a manual
            # text-to-image request that merely NAMES a material satisfies
            # `_state_edit_signal`; without this guard it would be executed
            # as an edit of the previous image. An explicit mode outranks an
            # inferred signal.
            and not self._explicit_text_to_image_turn(context)

            and

            conversation_state.get(
                "waiting_image_edit"
            )

            and

            conversation_state.get(
                "last_image_asset"
            )

            and

            _state_edit_signal

        )

        # ======================================================
        # RENDER_FOLLOWUP_V1 — COLLOQUIAL FOLLOW-UP RE-RENDER
        #
        # "رندر شبش بگیر" / "شبش کن" / "از یه زاویه دیگه رندر بگیر" /
        # "همین ساختمون رو رندر شب بگیر" all act on the render the user
        # is looking at, but none of them opened an edit session: the
        # render path never sets `waiting_image_edit`, so `state_override`
        # could not fire, the router read them as `image/generate`, and
        # the design route answered with the text-only
        # "✅ طراحی با موفقیت ایجاد و ذخیره شد." stub.
        #
        # This is deliberately NOT done by setting `waiting_image_edit`
        # after a render: that flag also feeds the plan-route blocker and
        # the continuation gate, and widening it changed the meaning of
        # every later turn. The rule is scoped to this one gate and
        # requires ALL of:
        #
        #   * the follow-up grammar (a render noun plus a time-of-day or
        #     camera modifier plus an imperative), so a new design brief
        #     cannot match;
        #   * an ACTIVE image in this session — a first-turn request has
        #     nothing to re-render and must keep the generation route;
        #   * no explicit analyze / text-to-image mode;
        #   * no declared A/B pair, which owns its own dispatch.
        # ======================================================

        _followup_edit = bool(

            _render_followup.get("matched")

            and conversation_state.get("last_image_asset")

            and _manual_image_mode not in ("analyze_image", "text_to_image")

            and not _verified_dual_pair

        )

        if _followup_edit:

            print(
                "🖼️ RENDER FOLLOW-UP → IMAGE EDIT"
            )

            intent_result = {

                "intent": "image",

                "mode": "img2img"

            }

        elif state_override:


            print(
                "🖼️ IMAGE EDIT STATE OVERRIDE"
            )


            intent_result = {

                "intent": "image",

                "mode": "img2img"

            }



        else:


            intent_result = self.intent_router.route(

                text,

                image,

                intent_context

            )


        if isinstance(intent_result, dict):

            # Session-scoped evidence for genuine follow-ups.  This prevents a
            # render asset from becoming the only remembered domain: a coder
            # turn remains a coder turn on "make it iterative".
            self.state.update({
                "last_route_intent": intent_result.get("intent"),
                "last_route_mode": intent_result.get("mode"),
                "last_model_role": intent_result.get("model_role"),
            })


        # ==================================================
        # MODE SAFETY INIT
        # ==================================================

        mode = (
            intent_result.get(
                "mode",
                "chat"
            )
            if isinstance(intent_result, dict)
            else "chat"
        )



        print(
            "🔥 ROUTER RESULT:",
            intent_result
        )



        intent = intent_result.get(
            "intent"
        )


        mode = intent_result.get(
            "mode"
        )


        print(
            "FINAL INTENT:",
            intent,
            mode
        )


        # ==================================================
        # RESOLVED_T2I_ROUTING_HANDOFF_V1 — THE RESOLVED ROUTE FEEDS THE
        # ARCHITECTURAL INSTRUCTION HANDOFF
        #
        # MEASURED DEFECT: the instruction above is decided by the WORDING
        # (`should_render_design(text)` = render vocabulary) plus a compiled
        # contract. An explicitly selected Text-to-Image turn that describes the
        # building WITHOUT saying "render" therefore reached
        # `handle_image_generate` with NO architectural instruction at all: the
        # corrected requirement builder was never consulted on that turn, and
        # every validated structured requirement was dropped from the sampler
        # prompt. The route said RENDER; the handoff never heard it.
        #
        # The route is now RESOLVED and authoritative, so it decides instead —
        # and it decides from a signal the request boundary already validated.
        # ALL of the following must hold:
        #
        #   * `intent == "image"` and `mode == "generate"` — the resolved route,
        #     exactly as the router returned it;
        #   * `_explicit_text_to_image_turn(context)` — the EXISTING validated
        #     predicate (routing_source is exactly "manual" AND the project's ONE
        #     mode normalizer reads text_to_image). Auto mode, observation-only
        #     chat and unrelated chat are refused HERE, before anything is built,
        #     so no architectural noun can ever turn a chat turn into a render;
        #   * no block is published yet for this turn.
        #
        # Nothing is duplicated: this calls the SAME `build_render_instruction`
        # with the SAME inputs the early site uses, and publishes through the
        # SAME `_publish_render_instruction`. The resolved validated mode is also
        # handed over through the carrier that exists for exactly that purpose
        # (T2I_MODE_PROPAGATION_V1) so that, whenever the builder has to compile
        # the prompt itself, a fresh text-to-image request can never be compiled
        # as a facade refinement.
        #
        # Safeguards are untouched: the fidelity verdict is recomputed, the
        # observation / negation / preservation rules still decide what the block
        # may contain (an observation-only turn yields an EMPTY block, so
        # nothing is published), and the I2I, geometry-authority and image-edit
        # guards are not consulted, read or relaxed here.
        # ==================================================

        if (
            intent == "image"
            and mode == "generate"
            and self._explicit_text_to_image_turn(context)
            and not (
                context.get("architectural_instruction")
                if isinstance(context, dict)
                else None
            )
        ):

            render_instruction = build_render_instruction(
                raw_text or text,
                understanding=effective_architectural_understanding,
                compiled=architectural_compiled_prompt,
                references=(
                    context.get("references")
                    if isinstance(context, dict)
                    else None
                ),
                # FACADE-04D.3C-9P-B12 — a user confirmation is resolved ONLY
                # through the trusted boundary (current-turn carrier, else THIS
                # session's persisted USER-authored turns).
                user_geometry=self._trusted_user_geometry(context),
                # T2I_MODE_PROPAGATION_V1 — the resolved, validated mode, read
                # exactly as the existing compiler call reads it.
                mode=(
                    context.get("mode")
                    if isinstance(context, dict)
                    else None
                ),
                context=(
                    context
                    if isinstance(context, dict)
                    else None
                ),
            )

            render_fidelity = validate_render_fidelity(
                raw_text or text,
                contract=render_instruction,
            )

            _resolved_instruction = self._publish_render_instruction(
                context,
                render_instruction,
                render_handoff_trace,
            )

            # The trace is the audit surface: keep it truthful about the
            # instruction that was ACTUALLY handed to this turn's render.
            if isinstance(render_handoff_trace, dict):

                render_handoff_trace["render_instruction"] = (
                    render_instruction
                )

                render_handoff_trace["render_fidelity"] = render_fidelity

            print(
                "🧭 RESOLVED T2I INSTRUCTION:",
                "published:",
                bool(_resolved_instruction),
                "| chars:",
                len(
                    (_resolved_instruction or {}).get("constraint_block")
                    or ""
                ),
            )


        # ==================================================
        # DESIGN APPROVAL UPDATE
        # ==================================================

        if self.is_design_approval(text):


            current_state = self.state.get()


            if current_state.get(
                "last_design"
            ):


                self.state.update({

                    "design_status":
                        "approved",


                    "project_state":
                        "APPROVED",


                    "approval_status":
                        True

                })


                print(
                    "✅ DESIGN STATUS UPDATED: APPROVED"
                )

                if (
                    not self.should_render_design(text, intent)
                    and not self.is_animation_request(text)
                ):
                    return {
                        "type": "design_approval",
                        "status": "approved",
                        "project_state": "APPROVED",
                        "approval_status": True,
                        "message": "طراحی تایید شد. برای ادامه بگویید رندر بگیر.",
                        "bim_result": current_state.get("bim_result", {}),
                    }

        # Architectural animation always starts from an approved still render
        # (or an uploaded reference image) and uses the WAN I2V workflow.
        if self.is_animation_request(text):
            animation_state = self.state.get()
            if animation_state.get("design_status") != "approved":
                return {
                    "type": "video",
                    "status": "waiting_approval",
                    "message": "برای ساخت انیمیشن ابتدا طراحی را تایید کنید.",
                }
            source_asset = (
                animation_state.get("last_render_asset")
                or animation_state.get("last_image_asset")
            )
            if not source_asset:
                return {
                    "type": "video",
                    "status": "needs_render_reference",
                    "message": "ابتدا از طرح تاییدشده یک رندر ثابت بگیرید؛ سپس انیمیشن ساخته می‌شود.",
                }
            animation_intent = self.build_approved_render_intent(animation_state)
            animation_intent["mode"] = "i2v"
            animation_intent["motion"] = "slow controlled architectural camera dolly"
            result = self.render_runtime.render(
                "chat_project",
                {
                    "prompt": text,
                    "original_prompt": text,
                    "architectural_intent": animation_intent,
                    "mode": "i2v",
                },
                "wan",
                source_asset,
            )
            if isinstance(result, dict):
                result.setdefault("type", "video")
            return result



        # ==================================================
        # CHAT_CODE_REQUEST_ROUTING_FIX_V1 — CODE CAPABILITY BOUNDARY
        #
        # A request to create or execute an ACTUAL code file is not an
        # architectural design. ArchitectOS has no verified file-writing or
        # code-execution tool, so this branch answers truthfully and returns
        # before the design / BIM pipeline can run. Ordinary "write code in the
        # chat" requests are classified as chat upstream and are unaffected.
        # ==================================================

        # CODER-05D — an explicit approve/reject turn resolves against the
        # staging store even when the intent router classified it as ordinary
        # conversation. The pending proposal is server-side state; the router
        # has no knowledge of it, so it must not be able to hand the turn to
        # the general model.
        #
        # CODER-05E — the same applies to an explicit CREATE/REGENERATE request
        # for a code file: if it is misclassified as conversation the general
        # model answers with prose and an UNVERIFIED code block instead of the
        # controlled staging contract.
        # CODER-HISTORY-REUSE-01 — a RESTORE turn ("همان کد قبلی … را از
        # تاریخچه بازیابی کن") carries no creation, generation, repair or
        # approval verb, so none of the predicates above opened this boundary
        # and the turn fell through to the general model. It is admitted by its
        # own predicate; the source is taken from THIS project's history and
        # the pending-proposal guard below is untouched.
        # REFERENCE_STYLE_PRODUCT_INTEGRATION_V1 — an IMAGE RENDER turn is
        # never a staged-file approval. `staged_file_action()` matches approval
        # vocabulary anywhere in the text, so the approved reference-style
        # request was swallowed by the coder boundary purely because it
        # describes "the APPROVED beige-brick residential building". The turn
        # was answered as a code capability request and never reached the
        # dual-image dispatch at all.
        #
        # The gate is scoped to a resolved image render intent, so every code
        # and conversation turn keeps the previous behaviour byte for byte.
        _image_render_turn = bool(
            intent == "image" and mode in ("generate", "render", "edit")
        )

        if (
            (intent == "code" and mode == "capability")
            or
            (self._staging_action_turn(text) and not _image_render_turn)
            or
            self._code_file_creation_turn(text)
            or
            self._code_repair_turn(text)
            or
            self._code_history_reuse_turn(text)
        ):

            print(
                "🧩 CODE REQUEST — capability boundary (no design/BIM)"
            )

            # CODER-05 / CODER-06 — an EXPLICIT request may CREATE a .py file
            # and/or SYNTAX-CHECK an existing one inside the current project
            # (never execution, never repair). Every other code request keeps
            # the truthful refusal.
            # CODER-05B — an approval turn also contains a save verb, so the
            # approval is resolved FIRST and creation is skipped for that turn.
            _approval_part = self._authorized_code_file_approval(text, session_id)

            _code_parts = [_approval_part]

            # CODER-REPAIR-01 — a scoped repair of the PENDING draft runs
            # BEFORE creation, and a repair turn never falls through to
            # creation: without a pending draft the truthful answer is "there
            # is nothing to repair", not a whole new file.
            _repair_part = None

            if not _approval_part:

                _repair_part = self._authorized_code_repair(text, session_id)

                if _repair_part:
                    _code_parts.append(_repair_part)

            if not _approval_part and not _repair_part:
                _code_parts.append(
                    self._authorized_code_file_creation(
                        text, session_id, raw_text=raw_text
                    )
                )

            _code_parts.append(
                self._authorized_code_syntax_check(text, session_id)
            )

            code_capability_message = (
                "\n\n".join(part for part in _code_parts if part)
                or (
                    "این درخواست یک درخواست برنامه‌نویسی است، نه طراحی معماری. "
                    "من می‌توانم کد را همین‌جا در گفت‌وگو بنویسم و توضیح بدهم، "
                    "اما در حال حاضر ابزار تأییدشده‌ای برای ساخت یک فایل واقعی روی "
                    "دیسک یا اجرای کد ندارم. بنابراین نمی‌توانم فایل calculator.py "
                    "را بسازم، کد را از نظر خطاهای نحوی بررسی کنم یا آن را اجرا "
                    "کنم؛ و هیچ طراحی معماری‌ای هم برای این درخواست انجام نشده است."
                )
            )

            code_response = {
                "type": "chat",
                "engine": "code_capability_boundary_v1",
                "result": code_capability_message,
                "status": "success",
                "degraded": False,
                "degraded_reason": None,
                "render_handoff": render_handoff_trace,
            }

            # This is proxy transport metadata, never model input. The UI
            # gateway stores it server-side and removes it before responding
            # to browser JavaScript.
            if isinstance(getattr(self, "context", None), dict):
                _authorization = self.context.get("trusted_local_authorization")
                if isinstance(_authorization, dict) and _authorization.get("trusted") is True:
                    from core.chat.code_file_staging_v1 import public_approval_capability
                    _capability = public_approval_capability(session_id, _authorization)
                    code_response["code_approval"] = (
                        dict(_capability, pending=True)
                        if isinstance(_capability, dict)
                        else {"pending": False}
                    )

            self.writeback.store(
                text,
                str(code_response),
                session_id=session_id
            )

            return code_response

        # ==================================================
        # DUAL_IMAGE_COMPARISON_V1 — GROUNDED A/B ANSWER
        #
        # A declared A/B pair is deliberately excluded from the single-image
        # upload / edit / analyse routing above (FACADE-04D.3C-4), so a
        # comparison turn used to fall straight into the generic text-chat
        # branch. That branch's prompt carries no image and no evidence, so
        # the model answered "I don't see any building photographs attached"
        # while `reference_architectural_analysis_ab` already held two
        # complete analyses. The evidence had no consumer.
        #
        # The reply is projected from that EXISTING analysis contract. This
        # branch is scoped to a chat turn with a declared pair: an image /
        # render intent never reaches it, so the render dispatch is untouched.
        # ==================================================

        if (
            _verified_dual_pair
            and
            intent == "chat"
            and
            mode == "conversation"
        ):

            print(
                "🖼️ DUAL-IMAGE COMPARISON REPLY (grounded, no render)"
            )

            return self._answer_about_image_pair(
                text,
                reference_architectural_analysis_ab,
                render_handoff_trace,
            )

        if (
            intent == "chat"
            and
            mode == "conversation"
        ):

            # ==============================================
            # PHASE 2D-4 — CANONICAL CONTEXT ASSEMBLY
            # Real context via ContextBuilder (no hardcoded identity).
            # ==============================================

            chat_context = self.context_builder.build(

                text,

                task="chat",

                # GENERAL_CONVERSATION_CONTINUITY_V1 — the recent turns are
                # read back for THIS session only, so one conversation can
                # never leak into another.
                session_id=session_id

            )


            # CHAT ISOLATION
            # Keep chat replies free of DESIGN/RENDER state, but retain the
            # real user profile AND the recent conversation.
            #
            # GENERAL_CONVERSATION_CONTINUITY_V1 — the recent turns are NO
            # LONGER discarded here. Blanking `memory["conversation"]` left
            # the model with only the current message plus the stored profile,
            # so a stored interest (e.g. architecture) could hijack a follow-up
            # question that was really about the previous turn's topic. The
            # history is bounded upstream by `memory_manager.get_history(20)`.
            chat_context["task"] = "chat"


            memory = chat_context.get(
                "memory",
                {}
            )


            if isinstance(memory, dict):

                # Design/render project state stays out of a chat turn. The
                # conversation itself is legitimate context and is kept.
                memory["projects"] = {
                    "active_projects": [],
                    "current": None
                }

                chat_context["memory"] = memory


            chat_context["conversation_state"] = {

                "mode": "chat",
                "last_topic": None,
                "active_project": None,
                "last_design": None,
                "last_render_asset": None

            }


            # ==================================================
            # CONVERSATION_DOMAIN_V1 — GATED ARCHITECTURAL CONTEXT
            #
            # Only an ARCHITECTURAL turn receives the session's
            # architectural payload. A voice/audio or general turn gets a
            # SUSPENDED projection (no understanding, no materials, no
            # elements, no architectural recent turns) plus explicit domain
            # guidance, so the answer stays in its own domain.
            #
            # The session context itself is never modified here.
            # ==================================================

            chat_context["architectural_context"] = (
                _domain_resolution.get("architectural_context")
                or architectural_context
            )

            chat_context["conversation_domain"] = (
                _domain_resolution.get("domain_block") or {}
            )

            # CONVERSATIONAL_NATURALNESS_V1 — natural-conversation style
            # block for THIS turn (register-aware). Tone only; it changes no
            # routing and no domain classification.
            chat_context["conversation_naturalness"] = (
                conversation_naturalness_instruction(
                    text,
                    # the CURRENT turn's structured signals, already computed
                    # by the Conversation Intent Boundary above (no second
                    # classifier). None when the boundary did not run.
                    signals=(_cib_decision or {}).get("signals"),
                )
            )

            prompt = self.prompt_engine.build(
                text,
                chat_context
            )

            # raw compiled-prompt print removed (LOG_SENSITIVE_OUTPUT_FIX)


            print("========== FINAL CHAT PROMPT ==========")
            # raw compiled-prompt dump removed (LOG_SENSITIVE_OUTPUT_FIX)
            print("=======================================")


            # CODER-03 — a confirmed code-writing chat turn is answered by
            # the dedicated coding model through a NEW per-call gateway. The
            # shared chat gateway is never mutated, so every other turn keeps
            # the general chat model.
            _code_llm = None

            if (
                isinstance(intent_result, dict)
                and intent_result.get("model_role") == "coder"
            ):

                _code_llm = coder_gateway()

                print(
                    "🧑‍💻 CODER MODEL SELECTED:",
                    _code_llm.model
                )

            # CHAT_LANGUAGE_02 — single canonical chat reply path
            # (build -> LLM -> bounded language guard)
            correction = self._canonical_chat_reply(
                prompt,
                text,
                use_context=False,
                expected_language=self._expected_guard_language(
                    teaching_turn
                ),
                llm=_code_llm
            )

            response_text = correction["response"]

            # ==================================================
            # PERSIAN_OUTPUT_ORTHOGRAPHY_V1 — response-side safety net
            #
            # The prompt now carries a Persian orthography contract, but
            # llama3 still ECHOES a malformed word that arrived in the
            # user turn in a minority of cases (measured ≈1/12). This is
            # the small, context-aware normaliser the brief allows: it
            # fixes ONLY the measured collocation «حیات خلوت»->«حیاط خلوت»
            # and the non-word «زخیره»->«ذخیره», unifies Arabic->Persian
            # codepoints, and NEVER touches the bare word «حیات».
            #
            # It applies to the ASSISTANT RESPONSE TEXT only. STT, the
            # dictation path, routing and the raw transcript are not
            # involved. The change is recorded in the response payload.
            # ==================================================
            orthography = None

            if any("\u0600" <= ch <= "\u06FF" for ch in str(response_text or "")):

                orthography = persian_output_orthography.normalize(
                    response_text
                )

                if orthography.get("changed"):

                    print(
                        "🔤 PERSIAN ORTHOGRAPHY:",
                        orthography.get("changes")
                    )

                    response_text = orthography["text"]

            response = {
                "type": "chat",
                "engine": "llm_gateway",
                "result": response_text,
                # OFFLINE_FIRST_V1 — a degraded reply is NOT a success
                # and must be reported as such, so the caller/UI can show
                # the truthful state instead of a silent empty answer.
                "status":
                    "degraded" if correction.get("degraded") else "success",
                "degraded":
                    bool(correction.get("degraded", False)),
                "degraded_reason":
                    correction.get("degraded_reason"),
                "language": {
                "input_language":
                    "persian" if any("\u0600" <= char <= "\u06FF" for char in text) else "english",
                "output_language":
                    "persian" if any("\u0600" <= char <= "\u06FF" for char in text) else "english",
                "guard_status":
                    correction["status"],
                "corrected":
                    correction.get("corrected", False),
                "orthography_changed":
                    bool(orthography and orthography.get("changed")),
                "orthography_changes":
                    (orthography or {}).get("changes") or [],
                },
                "render_handoff": render_handoff_trace,
            }

            self.writeback.store(
                text,
                str(response),
                session_id=session_id
            )

            return response



        # ==================================================
        # IMAGE MODE NORMALIZATION
        # ==================================================

        mode = (
            intent_result.get(
                "mode",
                "generate"
            )
            if isinstance(intent_result, dict)
            else "generate"
        )



        # ==================================================
        # IMAGE EDIT STATE ROUTE
        # ==================================================

        # FACADE-04D.3C-4 — a declared A/B pair must not be intercepted by the
        # state-driven img2img edit route either; it belongs to the dual-image
        # dispatch below.
        if (
            intent == "image"
            and
            mode == "img2img"
            and
            not _verified_dual_pair
        ):

            print(
                "🖼️ IMAGE EDIT ROUTE ACTIVE FROM STATE"
            )

            return self._router_edit_route(
                text,
                None,
                context,
                compiled_render_prompt,
                terminology,
                render_seed,
            )


        # ==================================================
        # IMAGE ROUTES
        # ==================================================


        if (

            intent == "image"

            and

            mode == "generate"

        ):


            print(
                "🔥 IMAGE MODE:",
                mode
            )


            print(

                "IMAGE GENERATE ROUTE ACTIVE"

            )


        # ==================================================
        # RENDER APPROVAL GATE v1
        # ==================================================

        state = self.state.get()


        design_status = state.get(
            "design_status"
        )


        has_design = bool(
            state.get(
                "last_design"
            )
            or
            state.get(
                "last_architectural_intent"
            )
        )


        print(
            "🔐 RENDER APPROVAL CHECK:",
            design_status,
            has_design
        )


        design_render_request = (
            intent == "image"
            and mode in ("generate", "render")
            and self.should_render_design(text, intent)
        )

        # ==================================================
        # FACADE-04A — ENFORCE THE DUAL-IMAGE RENDER GATE
        #
        # For the dual-image facade workflow (IMAGE A style reference +
        # IMAGE B geometry authority) a BLOCKED fidelity verdict, a failed /
        # missing IMAGE B, or an unresolved floor-count conflict must PREVENT
        # the render handoff — not merely appear on the trace. This guard is
        # scoped to the dual-image workflow: with no A/B pair it is inert, so
        # unrelated render and chat paths are unchanged.
        # ==================================================
        _dual_gate = (
            render_handoff_trace.get("dual_image_render")
            if isinstance(render_handoff_trace, dict)
            else None
        )

        # ==================================================
        # FACADE_REFERENCE_STYLE_AUTO_SELECTION_V1 — WHICH DUAL GRAPH?
        #
        # The conditioned graph used to be reachable only through an explicit
        # `conditioned_render` flag, so a user who plainly asked "apply the
        # style and materials of this reference to my building" silently got
        # `flux_img2img_dual.json`, whose reference branch is inert. The
        # decision is now derived from the existing contracts (image roles,
        # reference policy, render mode) with an explicit UI choice winning,
        # and the whole decision is recorded for the response envelope.
        #
        # A plain "compare these two" is a comparison request and is excluded
        # by the resolver, so two images are never treated as style transfer
        # by default.
        #
        # The derivation is hoisted ABOVE `_dual_render_intent` because that
        # gate now needs it (see below). It reads exactly the same inputs and
        # produces exactly the same values; nothing between the two sites
        # mutates `context`, `_dual_gate` or the understanding.
        # ==================================================
        _dual_role_bindings = (
            context.get("image_references")
            if isinstance(context, dict)
            else None
        ) or (
            (_dual_gate or {}).get("roles")
            if isinstance(_dual_gate, dict)
            else None
        )

        _declared_reference_policy = (
            (effective_architectural_understanding or {}).get(
                "reference_image_policy"
            )
            if isinstance(effective_architectural_understanding, dict)
            else None
        )

        # REFERENCE_STYLE_PRODUCT_INTEGRATION_V1 — when the understanding layer
        # supplied no policy, derive one from the turn itself. This is the ONLY
        # reason the conditioned graph can be reached without an explicit UI
        # opt-in; a turn that does not clearly ask for appearance/material
        # transfer derives nothing and keeps the previous behaviour.
        _reference_policy = (
            _declared_reference_policy
            or _reference_transfer_policy(text, _dual_role_bindings)
        )

        # FACADE_REFERENCE_STYLE_AUTO_SELECTION_V1 — a VERIFIED A/B pair plus a
        # DERIVED transfer policy is a dual-image render even when the intent
        # router names the verb "edit".
        #
        # MEASURED DEFECT: "Redesign my building using the architectural style
        # and cream stone materials of this reference facade. Preserve my
        # building's original geometry." resolves to `intent=image, mode=edit`.
        # The old gate accepted only `generate`/`render`, so this architectural
        # facade redesign fell past the dual dispatch into `_router_edit_route`
        # — the SINGLE-image edit route — where the pair was reduced to one
        # image and the reference could be taken as the edit source (refused
        # only by R4's `source_image_authority_mismatch`, i.e. a role hazard,
        # not a routing decision). `edit` is a render mode in this product's
        # own vocabulary: it has a dedicated image-edit dispatch below.
        #
        # Scoped deliberately: the promotion needs BOTH a verified pair AND a
        # derived transfer policy, so a two-image turn that asks for neither
        # (a comparison, a plain "edit this photo") keeps its previous route.
        # Conditioning itself is still decided by `resolve_conditioning()`.
        # ==================================================
        _dual_render_intent = bool(
            design_render_request
            or (
                intent == "image"
                and (
                    mode in ("generate", "render")
                    or (
                        _verified_dual_pair
                        and mode in ("edit", "img2img")
                        and _reference_policy
                    )
                )
            )
        )

        # ==================================================
        # FACADE-04D.3C-4 — DECLARED PAIR MUST NOT DEGRADE SILENTLY
        #
        # The boundary declared BOTH role keys, but they did not resolve to
        # two usable references. Refuse the render here instead of letting the
        # request fall through to single-image or text-to-image rendering.
        # ==================================================

        if (
            _verified_dual_pair
            and _dual_render_intent
            and isinstance(_dual_gate, dict)
            and not _dual_gate.get("pair_present")
        ):

            print(
                "⛔ DUAL-IMAGE RENDER BLOCKED: declared pair incomplete"
            )

            return {

                "type": "render_blocked",

                "status": "blocked",

                "reason": "dual_image_binding_incomplete",

                "dual_image_render": _dual_gate,

                "message": (
                    "رندر دو‐تصویری ناقص است: تصویر مرجع سبک (A) یا تصویر هدف "
                    "(B) تأیید نشده است؛ رندر متوقف شد."
                ),

                "render_handoff": render_handoff_trace,

            }

        if (
            _dual_render_intent
            and isinstance(_dual_gate, dict)
            and _dual_gate.get("pair_present")
            and not _dual_gate.get("ready_to_render")
        ):

            print(
                "⛔ DUAL-IMAGE RENDER BLOCKED:",
                _dual_gate.get("fidelity_status"),
                "| b_analyzed:",
                _dual_gate.get("b_analyzed"),
            )

            return {
                "type": "render_blocked",
                "status": "blocked",
                "reason": "dual_image_render_not_ready",
                "dual_image_render": _dual_gate,
                "message": (
                    "رندر دو‐تصویری آماده نیست: تحلیل تصویر سبک (A) یا تصویر "
                    "هدف (B) کامل نشده، یا تطابق معنایی دستور رندر تأیید نشده است."
                ),
                "render_handoff": render_handoff_trace,
            }

        # ==================================================
        # FACADE-04D.2 — ROLE-AWARE DUAL-IMAGE BINDING
        #
        # For an explicitly dual-image facade-restyling request BOTH images are
        # staged and bound by EXPLICIT node id:
        #
        #   IMAGE B (target_building / geometry authority) -> LoadImage node 300
        #   IMAGE A (style_reference  / appearance only)   -> LoadImage node 302
        #
        # IMAGE B stays the actual FLUX img2img source (node 300 -> VAEEncode
        # 301 -> KSampler 210). IMAGE A gets its OWN dedicated node and can
        # never overwrite node 300. If EITHER image is missing, invalid or
        # unstaged the request FAILS CLOSED — it is never downgraded to
        # text-to-image and IMAGE A is never silently substituted for IMAGE B.
        # IMAGE A conditioning stays INACTIVE: no verified compatible model /
        # conditioning consumer exists yet (FACADE-04D.1), so nothing claims
        # IMAGE A influences the rendered output.
        # ==================================================
        _dual_target_asset = None
        _dual_image_bindings = None

        # FACADE-04D.3B-2 / REFERENCE_TRANSFER_POLICY_V1 — the role bindings and
        # the reference policy are derived ABOVE, next to `_dual_gate`, because
        # `_dual_render_intent` needs them to recognise an edit-mode dual-image
        # transfer. Only the conditioning decision is taken here.
        from core.render.dual_image_conditioning_v1 import (
            resolve_conditioning,
        )

        _conditioning_decision = resolve_conditioning(
            role_bindings=_dual_role_bindings,
            reference_policy=_reference_policy,
            mode=(
                context.get("mode")
                if isinstance(context, dict)
                else None
            ),
            text=text,
            explicit=(
                context.get("conditioned_render")
                if isinstance(context, dict)
                else None
            ),
        )

        _dual_conditioned = bool(_conditioning_decision.get("conditioned"))

        # REFERENCE_STYLE_PRODUCT_INTEGRATION_V1 — a requested transfer that
        # conditioning cannot honour must be REFUSED, never silently rerouted
        # to `flux_img2img_dual.json`, whose reference branch is inert.
        if (
            _dual_render_intent
            and isinstance(_dual_gate, dict)
            and _dual_gate.get("pair_present")
            and _reference_policy
            and not _dual_conditioned
        ):

            print(
                "⛔ REFERENCE TRANSFER BLOCKED: conditioning unavailable |",
                _conditioning_decision.get("reason"),
            )

            return {

                "type": "render_blocked",

                "status": "blocked",

                "reason": "conditioning_unavailable_for_requested_transfer",

                "conditioning_decision": _conditioning_decision,

                "reference_policy": _reference_policy,

                "message": (
                    "این درخواست به انتقال سبک/مصالح از تصویر مرجع نیاز دارد، "
                    "اما مسیر شرطی‌سازی مرجع در دسترس نیست؛ رندر متوقف شد و "
                    "به گراف بدون مرجع بازگردانده نشد."
                ),

                "render_handoff": render_handoff_trace,

            }

        if (
            _dual_render_intent
            and isinstance(_dual_gate, dict)
            and _dual_gate.get("pair_present")
        ):

            from core.render.dual_image_binding_v1 import (
                build_dual_image_contract,
                dual_image_trace,
                fail_closed_reason,
            )

            # ==================================================
            # REFERENCE_STYLE_PRODUCT_INTEGRATION_V1 — R4 ON THE DUAL ROUTE
            #
            # The architectural preservation admission previously ran only in
            # `_route_image_edit`. A reference-guided facade redesign is an
            # architectural edit too, so it is admitted HERE, against the
            # workflow the selector actually chose, and it is CLOSED by
            # default. A record for another workflow can never satisfy it.
            # ==================================================
            _dual_workflow = (
                "flux_img2img_dual_conditioned.json"
                if _dual_conditioned
                else "flux_img2img_dual.json"
            )

            _dual_admission = _r4_dual_image_admission(
                text,
                (context.get("references") if isinstance(context, dict) else None),
                context,
                _dual_workflow,
            )

            self.last_r4_admission = _dual_admission.get("admission")

            if not _dual_admission.get("admitted"):

                print(
                    "⛔ R4 DUAL ARCHITECTURAL ADMISSION BLOCKED:",
                    _dual_admission.get("reason"),
                    "| workflow",
                    _dual_workflow,
                )

                _dual_admission["admission"]["conditioning"] = {
                    "conditioned": _dual_conditioned,
                    "source": _conditioning_decision.get("source"),
                    "reason": _conditioning_decision.get("reason"),
                }

                _dual_admission["admission"]["reference_policy"] = (
                    _reference_policy
                )

                return {

                    "type": "render_blocked",

                    "status": "blocked",

                    "reason": _dual_admission.get("reason"),

                    "admission": _dual_admission.get("admission"),

                    "message": (
                        "درخواست تغییر نمای معماری با تصویر مرجع شناخته شد، اما "
                        "مسیر فعلی نمی‌تواند حفظ دقیق هندسهٔ ساختمان را برای این "
                        "گراف تضمین کند؛ بنابراین رندر اجرا نشد."
                    ),

                    "capability_gap": {
                        "missing": "validated_architectural_preservation_workflow",
                        "detail": (
                            "No accepted visual evidence exists for this exact "
                            "dual-image workflow and checkpoint. Prompt wording "
                            "and CPU graph wiring are not proof."
                        ),
                    },

                    "render_handoff": render_handoff_trace,

                }

            if isinstance(context, dict):

                context["r4_preservation_contract"] = (
                    _dual_admission["admission"].get("preservation_contract")
                )

            # The admitted contract must reach the sampler, not merely the
            # trace. Composed with the same helper the single-image route uses.
            compiled_render_prompt = _r4_compose_admitted_edit_prompt(
                text,
                _dual_admission["admission"].get("preservation_contract"),
                compiled_render_prompt,
            )

            _dual_contract = build_dual_image_contract(
                context,
                "chat_project",
            )

            if _dual_contract.get("status") != "ready":

                _dual_errors = list(_dual_contract.get("errors") or [])

                # Preserve the FACADE-04C IMAGE B reason codes; add explicit
                # codes for IMAGE A (see dual_image_binding_v1.fail_closed_reason).
                _dual_reason = fail_closed_reason(_dual_errors)

                print(
                    "⛔ DUAL-IMAGE RENDER BLOCKED:",
                    _dual_reason,
                    _dual_errors,
                )

                return {
                    "type": "render_blocked",
                    "status": "blocked",
                    "reason": _dual_reason,
                    "dual_image_render": _dual_gate,
                    "dual_image_binding": _dual_contract,
                    "message": (
                        "تصویر مرجع سبک (A) یا تصویر هدف (B) برای رندر در "
                        "دسترس نیست؛ رندر متوقف شد (به تصویر به متن "
                        "بازگردانده نشد)."
                    ),
                    "render_handoff": render_handoff_trace,
                }

            _dual_roles = _dual_contract.get("roles") or {}

            _dual_a = _dual_roles.get("style_reference") or {}

            _dual_b = _dual_roles.get("target_building") or {}

            _dual_image_bindings = {
                role: {
                    "node_id": entry.get("node_id"),
                    "filename": entry.get("filename"),
                }
                for role, entry in _dual_roles.items()
            }

            _dual_target_asset = {
                "status": "ready",
                "asset_id": _dual_b.get("asset_id"),
                "filename": _dual_b.get("filename"),
                "path": _dual_b.get("staged_path"),
            }

            render_handoff_trace["dual_image_render"]["target_source_asset"] = {
                "asset_id": _dual_b.get("asset_id"),
                "filename": _dual_b.get("filename"),
                "path": _dual_b.get("staged_path"),
                "role": "target_building_geometry_source",
                "workflow_node": "300",
                "workflow": "flux_img2img_dual.json",
            }

            render_handoff_trace["dual_image_render"]["dual_binding"] = (
                dual_image_trace(_dual_contract)
            )

            print(
                "🖼️ FACADE-04D.2 DUAL IMAGES STAGED:",
                "A -> node",
                _dual_a.get("node_id"),
                _dual_a.get("filename"),
                "| B -> node",
                _dual_b.get("node_id"),
                _dual_b.get("filename"),
            )

        # ==================================================
        # FACADE_REFERENCE_STYLE_AUTO_SELECTION_V1 — DISPATCH THE DUAL RENDER
        #
        # The staging block above PREPARES `_dual_target_asset` and
        # `_dual_image_bindings`; it does not render. Both render dispatches
        # below were guarded by `mode == "generate"`, so a dual-image transfer
        # that the intent router called `edit` staged BOTH images and then fell
        # straight through to `_router_edit_route` — the SINGLE-image edit
        # route — where the pair was reduced to one image.
        #
        # `_dual_render_intent` now recognises that turn (verified pair +
        # derived transfer policy + edit mode), so the dispatch must honour it.
        # The extra conditions are the readiness gate and the staged bindings,
        # so this is False for every turn that did not complete staging: a
        # single-image `generate`, a chat turn, and a dual turn whose contract
        # failed (that one already returned a blocked envelope above).
        # ==================================================
        _dual_render_dispatch = bool(
            _dual_render_intent
            and _verified_dual_pair
            and isinstance(_dual_gate, dict)
            and _dual_gate.get("pair_present")
            and _dual_image_bindings
        )

        if has_design and design_status != "approved" and design_render_request:


            print(
                "⛔ RENDER BLOCKED - DESIGN NOT APPROVED"
            )


            return {

                "type":
                    "design",

                "status":
                    "waiting_approval",

                "message":
                    "طراحی هنوز تایید نشده است. لطفاً ابتدا طراحی را تایید کنید.",

                "architectural_intent":
                    state.get(
                        "last_architectural_intent",
                        {}
                    )

            }

        # ==================================================
        # FACADE-04D.3C-5B / .1 — H2 (SAFE OLLAMA MODEL RELEASE) IS NOT HERE.
        #
        # H2 must run after EVERY model operation of the request and before
        # the ComfyUI submit. Two Ollama calls happen after this point:
        # ImageHandler.handle_image_generate()'s semantic-intent extraction and
        # RenderRuntime.render()'s own `semantic_intent.extract()` (the
        # mode == "img2img" branch). H2 therefore lives inside
        # RenderRuntime.render(), immediately before the executor, together
        # with the exclusive `gpu_render` lease that protects the whole
        # rendering period. Its trace is merged back into
        # render_handoff_trace["gpu_handoff"]["h2"] by
        # _finalize_render_handoff().
        # ==================================================

        # ==================================================
        # SINGLE_T2I_FIDELITY_GATE_ACCEPTANCE_V1 — EVERY SINGLE-IMAGE
        # GENERATION DISPATCH BELOW THIS LINE IS GATED.
        #
        # MEASURED BYPASS: the first version of this gate sat immediately
        # before the LAST fallback dispatch, which the ordinary route never
        # reaches. The real single-image dispatches are the design-approved
        # render and `intent == "image" and mode == "generate"`; a
        # function-level probe drove a BLOCKED verdict straight through both
        # to `handle_image_generate`. The gate is therefore hoisted to the ONE
        # point that dominates all of them.
        #
        # The guard is SCOPED to a single-image generation turn. A chat,
        # conversation, coder or edit turn never evaluates it, so no unrelated
        # route can be blocked by a verdict it never needed.
        #
        # Dual-image A/B is unaffected: `_dual_render_ready` already requires
        # `may_proceed_to_render is True` and returns its own blocked envelope
        # earlier, so a turn arriving here has a PASS verdict by construction.
        # Edit routes (`mode == "img2img"`) dispatch elsewhere and never reach
        # this block.
        # ==================================================

        _single_image_generation = bool(
            (intent == "image" and mode == "generate")
            or (
                has_design
                and design_status == "approved"
                and design_render_request
            )
        )

        if _single_image_generation:

            _fidelity_refusal = self._render_fidelity_refusal(
                render_fidelity, render_handoff_trace
            )

            if _fidelity_refusal is not None:

                return _fidelity_refusal

        if has_design and design_status == "approved" and design_render_request:
            approved_intent = self.build_approved_render_intent(state)
            result = self.image_handler.handle_image_generate(
                text,
                architectural_intent=approved_intent,
                design_state={"previous_design": state.get("last_design", {})},
                compiled_render_prompt=compiled_render_prompt,
                preset_resolution=preset_resolution,
                terminology=terminology,
                render_seed=render_seed,
                image_asset=_dual_target_asset,
                image_bindings=_dual_image_bindings,
                conditioned=_dual_conditioned,
                architectural_instruction=(
                    context.get("architectural_instruction")
                    if isinstance(context, dict)
                    else None
                ),
                # VISUAL_REFERENCE_UX_V2 — explicit reference selection,
                # resolved and staged at the API boundary. None for every
                # turn without a selection.
                uso_reference=(
                    context.get("uso_reference")
                    if isinstance(context, dict)
                    else None
                ),
                uso_reference_meta=(
                    context.get("uso_reference_meta")
                    if isinstance(context, dict)
                    else None
                ),
                # VISION_LIGHTING_OUTPUT_VERIFICATION_V2 — explicit opt-in
                # for output observation. Absent/False keeps every route
                # byte for byte and adds no vision latency.
                verify_render=(
                    context.get("verify_render")
                    if isinstance(context, dict)
                    else None
                ),

                # FINAL_CORRECTED_FACADE_GPU_PREFLIGHT_V1 — the structured
                # contract OBJECT, not the rendered text. The image builder
                # uses it as provenance so a user request that merely contains
                # the contract header cannot suppress the preservation block.
                r4_preservation_contract=(
                    context.get("r4_preservation_contract")
                    if isinstance(context, dict)
                    else None
                ),
            )
            return self._finalize_render_handoff(result, render_handoff_trace)

        if intent == "image" and (mode == "generate" or _dual_render_dispatch):
            result = self.image_handler.handle_image_generate(
                text,
                compiled_render_prompt=compiled_render_prompt,
                preset_resolution=preset_resolution,
                terminology=terminology,
                render_seed=render_seed,
                image_asset=_dual_target_asset,
                image_bindings=_dual_image_bindings,
                conditioned=_dual_conditioned,
                architectural_instruction=(
                    context.get("architectural_instruction")
                    if isinstance(context, dict)
                    else None
                ),
                # VISUAL_REFERENCE_UX_V2 — explicit reference selection,
                # resolved and staged at the API boundary. None for every
                # turn without a selection.
                uso_reference=(
                    context.get("uso_reference")
                    if isinstance(context, dict)
                    else None
                ),
                uso_reference_meta=(
                    context.get("uso_reference_meta")
                    if isinstance(context, dict)
                    else None
                ),
                # VISION_LIGHTING_OUTPUT_VERIFICATION_V2 — explicit opt-in
                # for output observation. Absent/False keeps every route
                # byte for byte and adds no vision latency.
                verify_render=(
                    context.get("verify_render")
                    if isinstance(context, dict)
                    else None
                ),

                # FINAL_CORRECTED_FACADE_GPU_PREFLIGHT_V1 — the structured
                # contract OBJECT, not the rendered text. The image builder
                # uses it as provenance so a user request that merely contains
                # the contract header cannot suppress the preservation block.
                r4_preservation_contract=(
                    context.get("r4_preservation_contract")
                    if isinstance(context, dict)
                    else None
                ),
            )
            return self._finalize_render_handoff(result, render_handoff_trace)


            # ==================================================
            # DESIGN CONTINUATION RENDER
            # ==================================================


            if self.is_design_continuation(text):


                state = self.state.get()


                previous_intent = state.get(

                    "last_architectural_intent",

                    {}

                )


                previous_design = state.get(

                    "last_design",

                    {}

                )


                print(

                    "🧠 STORED ARCHITECTURAL INTENT:",

                    previous_intent

                )


                print(

                    "🏗️ STORED DESIGN:",

                    previous_design

                )



                if previous_intent or previous_design:


                    print(

                        "🔁 CONTINUING PREVIOUS DESIGN RENDER"

                    )


                    return self.image_handler.handle_image_generate(

                        text,

                        architectural_intent=previous_intent,

                        design_state={

                            "previous_design":

                                previous_design

                        },

                        architectural_instruction=(
                            context.get("architectural_instruction")
                            if isinstance(context, dict)
                            else None
                        ),

                        verify_render=(
                            context.get("verify_render")
                            if isinstance(context, dict)
                            else None
                        ),

                    )



            return self.image_handler.handle_image_generate(
                text,
                architectural_instruction=(
                    context.get("architectural_instruction")
                    if isinstance(context, dict)
                    else None
                ),
                verify_render=(
                    context.get("verify_render")
                    if isinstance(context, dict)
                    else None
                ),
            )






        if (

            intent == "image"

            and

            mode == "edit"

        ):


            print(

                "IMAGE EDIT ROUTE ACTIVE"

            )


            return self._router_edit_route(
                text,
                image,
                context,
                compiled_render_prompt,
                terminology,
                render_seed,
            )








        # ==================================================
        # MEMORY ROUTE
        # ==================================================


        if self.is_memory_query(

            text

        ):


            memory_result = self.recall.recall(

                text

            )


            response = {


                "type":

                    "memory_recall",


                "engine":

                    "memory",


                "result":

                    memory_result,


                "status":

                    "success"

            }



            self.writeback.store(

                text,

                str(response)

            )


            return response






        # ==================================================
        # CHAT ROUTE
        # ==================================================


        if self.is_chat_message(

            text

        ):


            chat_context = self.context_builder.build(
                text
            )

            # ==================================================
            # CHAT MEMORY ISOLATION
            # Remove render/project history from chat
            # ==================================================

            chat_context["task"] = "chat"


            memory = chat_context.get(
                "memory",
                {}
            )


            user_profile = memory.get(
                "user_profile",
                {}
            )


            projects = user_profile.get(
                "projects",
                {}
            )


            if isinstance(projects, dict):

                projects["current"] = None

                projects["active_projects"] = []


            user_profile["projects"] = projects

            memory["user_profile"] = user_profile

            chat_context["memory"] = memory


            chat_context["conversation_state"] = {

                "mode": "chat",

                "last_topic": None,

                "active_project": None

            }


            # CONVERSATIONAL_NATURALNESS_V1 — natural-conversation style
            # block for THIS turn (register-aware). Tone only.
            chat_context["conversation_naturalness"] = (
                conversation_naturalness_instruction(
                    text,
                    # the CURRENT turn's structured signals, already computed
                    # by the Conversation Intent Boundary above (no second
                    # classifier). None when the boundary did not run.
                    signals=(_cib_decision or {}).get("signals"),
                )
            )


            prompt = self.prompt_engine.build(

                text,

                chat_context

            )


            # CHAT_LANGUAGE_02 — single canonical chat reply path
            # (build -> LLM -> bounded language guard)
            correction = self._canonical_chat_reply(

                prompt,

                text,

                expected_language=self._expected_guard_language(
                    teaching_turn
                )

            )


            response_text = correction["response"]


            response = {


                "type":

                    "chat",


                "engine":

                    "llm_gateway",


                "result":

                    response_text,


                "status":

                    "success",


                "language": {

                    "input_language":
                        correction["validation"]["input_language"],

                    "output_language":
                        correction["validation"]["output_language"],

                    "guard_status":
                        correction["status"],

                    "corrected":
                        correction["corrected"],

                },


                "render_handoff":
                    render_handoff_trace

            }



            self.writeback.store(

                text,

                str(response)

            )


            return response








        # ==================================================
        # DESIGN PIPELINE
        # ==================================================


        design_context = self.context_builder.build(

            text

        )



        design_context["conversation_state"] = (

            self.state.get()

        )


        design_context["previous_design"] = (

            self.state.get().get(

                "last_design",

                {}

            )

        )



        # ==================================================
        # BUILD ARCHITECTURAL INTENT BEFORE DESIGN ENGINE
        # ==================================================

        

        print(
            "🏗️ DESIGN PIPELINE ARCH INTENT:",
            design_context.get(
                "architectural_intent"
            )
        )



        result = None



        if self.cognitive is not None:


            try:


                result = self.cognitive.process(

                    text,

                    context=design_context

                )


            except TypeError:


                result = self.cognitive.process(

                    text

                )




        if result is None:


            try:


                result = self.brain.run(

                    text,

                    context=design_context

                )


                print("\n====== BRAIN OUTPUT BEFORE BIM BRIDGE ======")

                print(
                    "RESULT TYPE:",
                    type(result)
                )

                if isinstance(result, dict):

                    print(
                        "RESULT KEYS:",
                        result.keys()
                    )

                    print(
                        "HAS STRUCTURAL GRID:",
                        "structural_grid" in result
                    )

                    print(
                        "STRUCTURAL GRID:",
                        result.get("structural_grid")
                    )

                    print(
                        "HAS SPATIAL:",
                        "spatial" in result
                    )

                    print(
                        "SPATIAL:",
                        result.get("spatial")
                    )

                print("============================================")


            except TypeError:


                result = self.brain.run(

                    text

                )



        # ==================================================
        # EXTRACT FINAL ARCHITECTURAL INTENT
        # SINGLE SOURCE OF TRUTH
        # ==================================================


        print("\n====== BRAIN OUTPUT BEFORE BIM BRIDGE ======")

        print(
            "RESULT KEYS:",
            result.keys()
        )

        print(
            "HAS STRUCTURAL GRID:",
            "structural_grid" in result
        )

        print(
            "STRUCTURAL GRID:",
            result.get("structural_grid")
        )

        print(
            "HAS SPATIAL:",
            "spatial" in result
        )

        print(
            "SPATIAL:",
            result.get("spatial")
        )

        print("============================================")


        final_arch_intent = {}



        if isinstance(result, dict):


            final_arch_intent = (

                result.get(
                    "architectural_intent"
                )

                or

                result.get(
                    "design_context",
                    {}
                ).get(
                    "architectural_intent",
                    {}
                )

                or

                {}

            )


        if not final_arch_intent:


            final_arch_intent = (

                design_context.get(
                    "architectural_intent",
                    {}
                )

                or

                {}

            )



        print(

            "🔥 FINAL ARCH INTENT:",

            final_arch_intent

        )


        print("\n====== BRAIN OUTPUT BEFORE BIM BRIDGE ======")

        print(
            "RESULT KEYS:",
            result.keys()
        )

        print(
            "HAS STRUCTURAL GRID:",
            "structural_grid" in result
        )

        print(
            "STRUCTURAL GRID:",
            result.get("structural_grid")
        )

        print(
            "HAS SPATIAL:",
            "spatial" in result
        )

        print(
            "SPATIAL:",
            result.get("spatial")
        )

        print("============================================")



        print("\n====== BEFORE DESIGN EXECUTION BRIDGE ======")

        print(
            "RESULT KEYS:",
            result.keys()
        )

        print(
            "STRUCTURAL GRID:",
            result.get("structural_grid")
        )

        print(
            "SPATIAL EXISTS:",
            bool(
                result.get("spatial")
            )
        )

        print(
            "GEOMETRY:",
            result.get("geometry")
        )

        print("============================================")

        print("### REACHED DESIGN PRODUCER TRACE LOCATION ###")


        print("\n====== DESIGN PRODUCER TRACE ======")

        print(
            type(result)
        )

        print(
            result.keys()
        )

        print(
            result.get("architectural_intent")
        )

        print("===================================")



        bim_result = self.design_bim_bridge.process(
            result,
            result.get("decisions", [])
        )



        response = {

            "type":
                "design",

            "engine":
                "GOD_CORE",

            "result":
                result.get(
                    "result",
                    result
                ),

            "architectural_intent":
                final_arch_intent,

            "bim_result":
                result.get(
                    "bim_result",
                    {}
                ),

            "project_state":
                "WAITING_APPROVAL",

            "approval_status":
                False,

            "status":
                "success"
        }


        response["bim_result"] = bim_result





        # ==================================================
        # OPTIONAL DESIGN RENDER
        # ==================================================


        if self.should_render_design(

            text,

            intent

        ):


            response = self.attach_render(

                response,

                text,

                compiled_render_prompt=compiled_render_prompt,

                preset_resolution=preset_resolution,

                terminology=terminology,

                render_seed=render_seed,

                # RENDER_INSTRUCTION_HANDOFF_V1 — request-scoped, built by the
                # A/B block above; None for every turn without one.
                architectural_instruction=(
                    context.get("architectural_instruction")
                    if isinstance(context, dict)
                    else None
                ),

                # VISUAL_REFERENCE_UX_V2 — explicit reference selection,
                # resolved and staged at the API boundary. None for every
                # turn without a selection, which keeps the existing routes
                # byte for byte.
                uso_reference=(
                    context.get("uso_reference")
                    if isinstance(context, dict)
                    else None
                ),

                uso_reference_meta=(
                    context.get("uso_reference_meta")
                    if isinstance(context, dict)
                    else None
                )

            )


            response = self._finalize_render_handoff(
                response,
                render_handoff_trace
            )



        print(

            "💾 SAVING ARCH INTENT:",

            final_arch_intent

        )



        self.update_conversation_state(

            request=text,

            response=response,

            response_type="design",

            intent="architecture",

            topic="design",

            project={


                "type":

                    result.get(

                        "building_type",

                        "building"

                    )

                    if isinstance(result, dict)

                    else "building",



                "design":

                    result,


                "design_status":

                    "WAITING_APPROVAL",



                "architectural_intent":

                    final_arch_intent,



                "plan":

                    result.get(

                        "plan",

                        {}

                    )

                    if isinstance(result, dict)

                    else {}

            },


            architectural_intent=final_arch_intent

        )



        self.writeback.store(

            text,

            str(response)

        )


        return response
    # ======================================================
    # CONVERSATION STATE UPDATE
    # ======================================================


    def update_conversation_state(
        self,
        request,
        response,
        response_type=None,
        intent=None,
        topic=None,
        project=None,
        architectural_intent=None
    ):


        # ==================================================
        # ARCHITECTURAL INTENT PRESERVATION
        # ==================================================

        if architectural_intent is None:


            architectural_intent = self.state.get().get(

                "last_architectural_intent",

                {}

            )



        if not architectural_intent:


            architectural_intent = {}



        print(

            "💾 FINAL ARCH INTENT GOING TO STATE:",

            architectural_intent

        )



        self.state.update({


            "last_request":

                request,


            "last_response":

                response,


            "last_response_type":

                response_type,

            
            "project_state":

                response.get(
                    "project_state",
                    "IDLE"
                )
                if isinstance(
                    response,
                    dict
                )
                else "IDLE",


            "approval_status":

                response.get(
                    "approval_status",
                    False
                )
                if isinstance(
                    response,
                    dict
                )
                else False,


            "bim_result":

                response.get(
                    "bim_result",
                    {}
                )
                if isinstance(
                    response,
                    dict
                )
                else {},


            "last_intent":

                intent,


            "last_architectural_intent":

                architectural_intent,


            "last_topic":

                topic,


            "active_project":

                project,


            "last_design":

                (

                    project.get(

                        "design"

                    )

                    if isinstance(

                        project,

                        dict

                    )

                    and project.get(

                        "design"

                    ) is not None

                    else (

                        response.get(

                            "result"

                        )

                        if isinstance(

                            response,

                            dict

                        )

                        else None

                    )

                )

        })



        print(

            "🧠 STATE UPDATED:",

            self.state.get()

        )



        return self.state.get()


    



    # ======================================================
    # PROCESS BRIDGE
    # ======================================================


    def process(
        self,
        text,
        context=None
    ):

        return self.handle(
            text,
            context
        )


    # ======================================================
    # CHAT DETECTOR
    # ======================================================


    def is_chat_message(
        self,
        text
    ):


        if not text:
            return False


        words = [

            "سلام",
            "درود",
            "hello",
            "hi",
            "hey",
            "خوبی",
            "چطوری",
            "اسمت",
            "نامت",
            "کی هستی",
            "who are you",

            "چرا",
            "چیست",
            "چی هست",
            "فرق",
            "توضیح بده",
            "توضیح درباره",
            "معنی",
            "چگونه",
            "چطور"

        ]


        text=text.lower()


        return any(
            w in text
            for w in words
        )



    # ======================================================
    # MEMORY QUERY DETECTOR
    # ======================================================


    def is_memory_query(
        self,
        text
    ):


        words = [

            "یادم",
            "یادته",
            "قبلا",
            "قبلاً",
            "history",
            "previous",
            "who am i",
            "اسم من",
            "نام من"

        ]


        text = text.lower()


        return any(

            word in text

            for word in words

        )



    # ======================================================
    # DESIGN CONTINUATION DETECTOR
    # ======================================================


    def is_design_continuation(
        self,
        text
    ):


        if not text:

            return False



        keywords = [

            "اضافه کن",
            "تغییر بده",
            "اصلاح کن",
            "ویرایش کن",
            "جابه جا کن",
            "حذف کن",
            "کم کن",
            "به آن اضافه کن",
            "نما",
            "نمای",
            "facade",
            "پوسته",
            "مدرن بساز",
            "بساز",
            "ادامه بده"

        ]



        text = text.lower()



        return any(

            key in text

            for key in keywords

        )



    # ======================================================
    # DESIGN APPROVAL DETECTOR
    # ======================================================


    def is_design_approval(
        self,
        text
    ):


        if not text:

            return False



        keywords = [

            "تایید",
            "تایید شد",
            "تایید کن",
            "approve",
            "approved"

        ]



        text = text.lower()



        return any(

            key in text

            for key in keywords

        )


    def is_animation_request(self, text):
        if not text:
            return False
        normalized = str(text).lower()
        return any(
            keyword in normalized
            for keyword in (
                "انیمیشن", "ویدیو", "متحرک", "حرکت دوربین",
                "animation", "video", "camera motion", "camera dolly",
            )
        )


    # ======================================================
    # DESIGN RENDER DECISION
    # ======================================================


    def should_render_design(
        self,
        text,
        intent=None
    ):


        normalized_intent = str(
            intent or ""
        ).lower().replace(
            "_",
            " "
        ).strip()


        print(
            "DEBUG SHOULD RENDER INTENT:",
            normalized_intent
        )


        render_keywords = [

            "رندر",
            "render",
            "تصویر",
            "ویژوال",
            "visualization",
            "archviz",
            "سه بعدی",
            "3d",
            "نمای سه بعدی"

        ]


        if not text:

            return False


        text = text.lower()


        return any(

            key in text

            for key in render_keywords

        )
