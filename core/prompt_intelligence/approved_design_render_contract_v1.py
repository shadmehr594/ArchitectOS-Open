# ==========================================================
# ArchitectOS Approved Design → Render Contract v1.0
#
# PHASE 2D-6 — PLAN / APPROVED DESIGN → RENDER CONTRACT
#
# Binds a render request to ONE explicitly approved design, and separates:
#   APPROVED DESIGN   = authoritative geometry source
#   STYLE / MATERIAL / REFERENCE = appearance proposal only
#
# CONTRACT ONLY.  No RenderRuntime call, no ComfyUI, no image generation,
# no plan/design mutation, no provider/model change.
# ==========================================================


from __future__ import annotations

import hashlib
import json
import time


CONTRACT = "ApprovedDesignRenderContractV1"
RENDER_INTENT_CONTRACT = "RenderIntentV1"
VERSION = "1.0"


class ApprovedDesignRenderContractV1(dict):
    """Versioned, dict-compatible approved-design render contract."""

    CONTRACT = CONTRACT
    VERSION = VERSION


# ==========================================================
# STATUSES
# ==========================================================

STATUS_READY = "READY"
STATUS_READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
STATUS_APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
STATUS_NO_APPROVED_DESIGN = "NO_APPROVED_DESIGN"
STATUS_DESIGN_LINEAGE_INCOMPLETE = "DESIGN_LINEAGE_INCOMPLETE"
STATUS_GEOMETRY_REFERENCE_REQUIRED = "GEOMETRY_REFERENCE_REQUIRED"
STATUS_DESIGN_REVISION_REQUIRED = "DESIGN_REVISION_REQUIRED"
STATUS_REFERENCE_CONFLICT = "REFERENCE_CONFLICT"
STATUS_INVALID_APPROVAL = "INVALID_APPROVAL"
STATUS_FAILED = "FAILED"


# ==========================================================
# MODES
# ==========================================================

MODES = ("TEXT_TO_IMAGE", "IMAGE_EDIT", "FACADE_REFINEMENT", "DESIGN_VISUALIZATION", "CONCEPT_VARIANT")


# ==========================================================
# AUTHORITATIVE GEOMETRY
# ==========================================================

GEOMETRY_APPROVED_DESIGN = "APPROVED_DESIGN"
GEOMETRY_APPROVED_BUILDING_IMAGE = "APPROVED_BUILDING_IMAGE"


# ==========================================================
# PRESERVE DEFAULTS (conservative — approved geometry is authority)
# ==========================================================

DEFAULT_PRESERVE = {
    "massing": True,
    "floor_count": True,
    "plan": True,
    "primary_openings": True,
    "windows": True,
    "balconies": True,
    "entrance_location": True,
    "geometry": True,
    "structure_if_known": None,   # unknown unless trusted project metadata exists
}

# §7 allowed render changes (appearance only)
DEFAULT_ALLOWED_RENDER_CHANGES = (
    "facade_materials",
    "facade_style",
    "colour_palette",
    "ornament_level",
    "surface_texture",
    "window_frame_expression",
    "balcony_railing_expression",
    "entrance_emphasis",
    "facade_depth_visualization",
    "lighting",
    "camera",
    "landscape_presentation",
)

# §8 forbidden geometry changes
FORBIDDEN_GEOMETRY_CHANGES = (
    "add_floor",
    "remove_floor",
    "change_building_footprint",
    "move_primary_openings",
    "change_room_layout",
    "change_plan_topology",
    "change_structural_grid",
    "move_core",
    "change_approved_massing",
)

# §9 deterministic design-revision signals
_DESIGN_REVISION_SIGNALS = (
    ("add_floor", ("طبقه اضافه", "یه طبقه اضافه", "یک طبقه اضافه", "طبقه بیشتر",
                   "اضافه کن طبقه", "add a floor", "add floor", "extra floor", "another floor")),
    ("remove_floor", ("طبقه کم", "طبقه حذف", "طبقه بردار", "remove a floor", "remove floor", "fewer floors")),
    ("change_approved_massing", ("حجم رو تغییر", "حجم رو عوض", "حجم بزرگ‌تر", "حجم بزرگتر",
                                 "حجم کوچک‌تر", "حجم کوچکتر", "change the massing", "change massing")),
    ("change_building_footprint", ("ابعاد ساختمان", "زیربنا", "footprint", "building footprint")),
    ("change_plan_topology", ("پلان رو عوض", "پلان رو تغییر", "پلان عوض", "پلان تغییر",
                              "چیدمان رو", "چیدمان عوض", "change the plan", "redesign the plan",
                              "change layout", "layout change")),
    ("change_room_layout", ("اتاق‌ها رو جابه", "اتاقها رو جابه", "اتاق رو جابه", "اتاق‌ها رو عوض",
                            "room layout", "move the rooms")),
    ("change_structural_grid", ("شبکه سازه", "ستون‌ها رو جابه", "ستونها رو جابه",
                                "structural grid", "move the columns")),
    ("move_core", ("هسته رو جابه", "هسته جابه", "move the core")),
)

_OPENING_GEOMETRY_VERBS = (
    "جابه‌جا", "جابجا", "عوض", "تغییر", "حذف", "اضافه", "بردار", "بزرگ", "کوچک",
    "move", "relocate", "replace", "remove", "add", "resize", "shift",
)
_OPENING_NOUNS = ("پنجره", "بازشو", "window", "opening")
# appearance-only qualifiers that must NOT trigger a design revision
_OPENING_APPEARANCE_QUALIFIERS = ("قاب پنجره", "قاب‌ها", "فریم", "window frame", "frame")


# ==========================================================
# BUILDER
# ==========================================================

class ApprovedDesignRenderContractBuilder:

    VERSION = VERSION

    def __init__(self):
        print("📐 APPROVED DESIGN RENDER CONTRACT BUILDER v1.0 ONLINE (contract only)")

    # ------------------------------------------------------
    # approval reading (read-only adapter)
    # ------------------------------------------------------

    @staticmethod
    def _read_approval(approval_state):
        state = approval_state if isinstance(approval_state, dict) else {}
        approved = bool(
            state.get("approval_status") is True
            or str(state.get("design_status", "")).lower() == "approved"
            or str(state.get("project_state", "")).upper() == "APPROVED"
        )
        has_design = bool(state.get("last_design") or state.get("last_architectural_intent"))
        return state, approved, has_design

    @staticmethod
    def _read_lineage(state):
        lineage = {
            "approved_design_id": state.get("approved_design_id"),
            "approved_candidate_id": state.get("approved_candidate_id"),
            "approved_candidate_version": state.get("approved_candidate_version"),
            "approved_candidate_hash": state.get("approved_candidate_hash"),
            "design_source_type": state.get("design_source_type", "unknown"),
        }
        gaps = []
        for key in ("approved_candidate_id", "approved_candidate_version", "approved_candidate_hash"):
            if lineage.get(key) in (None, "", []):
                gaps.append(key)
        lineage["gaps"] = gaps
        lineage["lineage_complete"] = not gaps
        return lineage

    # ------------------------------------------------------
    # design-revision detection
    # ------------------------------------------------------

    @staticmethod
    def _detect_design_revision(text):
        lowered = str(text or "").lower()
        if not lowered:
            return []
        found = []
        for token, phrases in _DESIGN_REVISION_SIGNALS:
            if any(phrase in lowered for phrase in phrases):
                found.append(token)

        # window/opening geometry change (appearance qualifiers excluded)
        has_appearance_only = any(q in lowered for q in _OPENING_APPEARANCE_QUALIFIERS)
        if not has_appearance_only:
            if any(noun in lowered for noun in _OPENING_NOUNS) and any(v in lowered for v in _OPENING_GEOMETRY_VERBS):
                found.append("move_primary_openings")

        # de-duplicate, preserve canonical order
        return [token for token in FORBIDDEN_GEOMETRY_CHANGES if token in found]

    # ------------------------------------------------------
    # mode resolution
    # ------------------------------------------------------

    def _resolve_mode(self, state, understanding, context, mode):
        if mode in MODES:
            return mode
        context = context or {}
        if context.get("mode") in MODES:
            return context["mode"]
        has_base_image = bool(
            state.get("base_image_id")
            or state.get("base_image_hash")
            or (state.get("last_image_asset") or {}).get("filename")
        )
        if has_base_image:
            return "IMAGE_EDIT"
        scope = (understanding or {}).get("scope")
        if scope == "facade":
            return "FACADE_REFINEMENT"
        if has_base_image is False and (state.get("last_design") or state.get("last_architectural_intent")):
            # approved plan/design exists but no facade image
            return "DESIGN_VISUALIZATION"
        return "TEXT_TO_IMAGE"

    # ------------------------------------------------------
    # preserve merge
    # ------------------------------------------------------

    @staticmethod
    def _merge_preserve(understanding):
        preserve = dict(DEFAULT_PRESERVE)
        explicit = (understanding or {}).get("preserve_constraints") or {}
        for key, value in explicit.items():
            if key in ("explicit", "scope_unspecified"):
                continue
            if value is True:
                preserve[key] = True
        return preserve

    # ------------------------------------------------------
    # compiled-prompt conflict detection
    # ------------------------------------------------------

    @staticmethod
    def _detect_prompt_conflicts(compiled_prompt, preserve):
        conflicts = []
        if not isinstance(compiled_prompt, dict):
            return conflicts

        geometry_keywords = {
            "windows": ("window", "پنجره"),
            "primary_openings": ("opening", "بازشو"),
            "massing": ("massing", "حجم"),
            "floor_count": ("floor", "طبقه"),
            "plan": ("plan", "پلان"),
            "balconies": ("balcony", "بالکن"),
            "entrance_location": ("entrance", "ورودی"),
        }

        changes = compiled_prompt.get("change_instructions") or []
        preserves = " ".join(compiled_prompt.get("preservation_instructions") or []).lower()

        for instruction in changes:
            text = str(instruction).lower()
            for field, keywords in geometry_keywords.items():
                if preserve.get(field) is not True:
                    continue
                if any(keyword in text for keyword in keywords):
                    conflicts.append({
                        "field": field,
                        "change_instruction": instruction,
                        "reason": "compiled_change_conflicts_with_preserve",
                        "resolution": "preservation_authoritative",
                        "preserved_evidence": field in preserves or bool(preserves),
                    })
        return conflicts

    # ------------------------------------------------------
    # reference interaction
    # ------------------------------------------------------

    @staticmethod
    def _reference_block(understanding, reference_analysis, warnings, required_context):
        policy = (understanding or {}).get("reference_image_policy") or {}
        analysis = reference_analysis if isinstance(reference_analysis, dict) else {}

        referenced = bool(policy.get("referenced"))
        role = policy.get("role")

        if referenced and not analysis:
            warnings.append({"code": "REFERENCE_IMAGE_NOT_ANALYZED",
                             "detail": "reference policy present but no image analysis available"})
            required_context.append("reference_image_analysis")
        elif referenced and analysis.get("analysis_status") == "PROVIDER_UNAVAILABLE":
            warnings.append({"code": "REFERENCE_IMAGE_NOT_ANALYZED",
                             "detail": "no vision provider available for the reference image"})

        return {
            "referenced": referenced,
            "role": role,
            "reference_material_source": role == "material_only",
            "reference_style_transfer": role == "style_only",
            "reference_composition_transfer": role == "composition_only",
            "reference_inspiration_only": role == "inspiration_only",
            "reference_geometry_copy": bool(policy.get("copy_reference_geometry", False)),
            "reference_analysis_available": bool(
                analysis and analysis.get("analysis_status") not in (None, "PROVIDER_UNAVAILABLE")
            ),
        }

    @staticmethod
    def _reference_ab_block(reference_analysis_ab, warnings, required_context):
        """FACADE-04A — the dual-image A/B reference block (contract only).

        IMAGE A = facade style reference (appearance only).
        IMAGE B = target building (geometry authority).

        The block is READY only when BOTH role-bound analyses are real. A
        missing or failed IMAGE B (the geometry authority) is reported and the
        caller downgrades the contract status; it is never ready-to-render.
        Geometry is never copied from the style reference.
        """

        pair = reference_analysis_ab if isinstance(reference_analysis_ab, dict) else {}
        a = pair.get("A") if isinstance(pair.get("A"), dict) else {}
        b = pair.get("B") if isinstance(pair.get("B"), dict) else {}
        roles = pair.get("roles") if isinstance(pair.get("roles"), dict) else {}

        def _ok(analysis):
            return bool(analysis) and analysis.get("analysis_status") not in (
                None, "PROVIDER_UNAVAILABLE", "FAILED",
            )

        a_ok, b_ok = _ok(a), _ok(b)
        present = bool(pair)

        if present and not a_ok:
            warnings.append({
                "code": "FACADE_STYLE_REFERENCE_NOT_ANALYZED",
                "detail": "IMAGE A (style reference) analysis missing or failed",
            })
            required_context.append("facade_style_reference_analysis")

        if present and not b_ok:
            warnings.append({
                "code": "TARGET_BUILDING_NOT_ANALYZED",
                "detail": "IMAGE B (geometry authority) analysis missing or failed",
            })
            required_context.append("target_building_geometry_analysis")

        return {
            "present": present,
            "style_reference_authority": "appearance_only",
            "geometry_authority": roles.get("geometry_authority") or "target_building",
            "roles": roles or {
                "A": "facade_reference",
                "B": "target_building",
                "geometry_authority": "target_building",
            },
            "a_analysis_status": a.get("analysis_status"),
            "b_analysis_status": b.get("analysis_status"),
            "a_analyzed": a_ok,
            "b_analyzed": b_ok,
            "ready": bool(a_ok and b_ok),
            "geometry_copy_from_style_reference": False,
        }

    # ------------------------------------------------------
    # main
    # ------------------------------------------------------

    def build(self, approval_state, understanding=None, compiled_prompt=None,
              reference_analysis=None, reference_analysis_ab=None, context=None,
              mode=None, require_full_lineage=False):
        context = context or {}
        warnings = []
        required_context = []

        state, approved, has_design = self._read_approval(approval_state)

        # -------- approval gate (never inferred) --------
        if not state:
            return self._empty(
                STATUS_NO_APPROVED_DESIGN, mode or "TEXT_TO_IMAGE",
                warnings=[{"code": "NO_APPROVAL_STATE"}],
                reason="no_approval_state",
            )

        if not approved:
            return self._empty(
                STATUS_APPROVAL_REQUIRED, mode or "TEXT_TO_IMAGE",
                warnings=[{"code": "APPROVAL_REQUIRED",
                           "detail": "design_not_approved" if has_design else "no_design_context"}],
                reason="design_not_approved" if has_design else "no_design_context",
            )

        lineage = self._read_lineage(state)
        if lineage["gaps"]:
            warnings.append({"code": "DESIGN_LINEAGE_INCOMPLETE", "missing": lineage["gaps"]})
            if require_full_lineage:
                return self._empty(
                    STATUS_DESIGN_LINEAGE_INCOMPLETE, mode or "TEXT_TO_IMAGE",
                    warnings=warnings, lineage=lineage, reason="lineage_gaps",
                )

        # -------- design revision gate --------
        revision_text = " ".join(filter(None, [
            str((understanding or {}).get("normalized_text", "")),
            str((understanding or {}).get("raw_text", "")),
        ]))
        forbidden = self._detect_design_revision(revision_text)
        if forbidden:
            return self._empty(
                STATUS_DESIGN_REVISION_REQUIRED, mode or "TEXT_TO_IMAGE",
                warnings=[{"code": "DESIGN_REVISION_REQUIRED", "forbidden_changes": forbidden}],
                lineage=lineage, forbidden=forbidden, reason="design_level_change_requested",
            )

        resolved_mode = self._resolve_mode(state, understanding, context, mode)

        # -------- authoritative geometry --------
        if resolved_mode == "IMAGE_EDIT":
            authoritative = GEOMETRY_APPROVED_BUILDING_IMAGE
        else:
            authoritative = GEOMETRY_APPROVED_DESIGN

        # -------- preserve --------
        preserve = self._merge_preserve(understanding)

        # -------- compiled prompt conflicts (hard preserve wins) --------
        conflicts = self._detect_prompt_conflicts(compiled_prompt, preserve)
        if conflicts:
            warnings.append({"code": "COMPILED_PROMPT_CONFLICT", "count": len(conflicts)})

        # -------- allowed render changes --------
        allowed = list(DEFAULT_ALLOWED_RENDER_CHANGES)
        if preserve.get("entrance_location") is True:
            pass  # entrance_emphasis is appearance-only and remains allowed
        allowed = [c for c in allowed if c not in FORBIDDEN_GEOMETRY_CHANGES]

        # -------- reference --------
        reference = self._reference_block(understanding, reference_analysis, warnings, required_context)

        # FACADE-04A — the dual-image A/B reference block. IMAGE A is the facade
        # style reference (appearance only); IMAGE B is the target building and
        # the geometry authority. A failed/missing B makes the contract NOT
        # ready — never a ready-to-render contract.
        reference_ab = self._reference_ab_block(
            reference_analysis_ab, warnings, required_context
        )

        # -------- plan → render required context --------
        # Without an approved building image, exact facade geometry is not
        # available to the render (informational, never blocking).
        if resolved_mode != "IMAGE_EDIT":
            required_context.append("approved_facade_geometry")

        # -------- presentation (only when present) --------
        presentation = {}
        for key in ("camera_style", "lighting_preference", "time_of_day", "realism_level", "landscape_context"):
            value = context.get(key)
            if value not in (None, "", [], {}):
                presentation[key] = value

        status = STATUS_READY_WITH_WARNINGS if warnings else STATUS_READY
        if conflicts and status == STATUS_READY:
            status = STATUS_READY_WITH_WARNINGS

        # FACADE-04A — a dual-image facade request is NOT ready unless BOTH
        # role-bound analyses succeeded (IMAGE B is the geometry authority).
        if reference_ab.get("present") and not reference_ab.get("ready"):
            status = STATUS_GEOMETRY_REFERENCE_REQUIRED

        render_intent = {
            "contract": RENDER_INTENT_CONTRACT,
            "version": VERSION,
            "mode": resolved_mode,
            "target_design_id": lineage.get("approved_candidate_id") or lineage.get("approved_design_id"),
            "style": (understanding or {}).get("style") or {},
            "materials": (understanding or {}).get("materials") or {},
            "preserve": preserve,
            "reference_policy": reference,
            "presentation": presentation,
            "quality": {},
            "camera": presentation.get("camera_style"),
            "lighting": presentation.get("lighting_preference"),
            "forbidden_changes": list(FORBIDDEN_GEOMETRY_CHANGES),
            "required_context": sorted(set(required_context)),
        }

        result = ApprovedDesignRenderContractV1({
            "contract": CONTRACT,
            "version": VERSION,

            "status": status,

            "session_id": context.get("session_id"),
            "project_id": state.get("project_id") or context.get("project_id"),

            "approved_design_id": lineage.get("approved_design_id"),
            "approved_candidate_id": lineage.get("approved_candidate_id"),
            "approved_candidate_version": lineage.get("approved_candidate_version"),
            "approved_candidate_hash": lineage.get("approved_candidate_hash"),

            "approval_status": True,
            "approval_timestamp_or_marker": state.get("approval_marker") or "approved",
            "approval_provenance": {
                "source": "ConversationState",
                "design_status": state.get("design_status"),
                "project_state": state.get("project_state"),
                "approval_status": state.get("approval_status"),
            },

            "design_source_type": lineage.get("design_source_type", "unknown"),

            "plan_reference": bool(state.get("last_design")),
            "geometry_reference": bool(state.get("last_architectural_intent")),
            "image_reference": bool(state.get("last_image_asset") or state.get("base_image_id")),

            "authoritative_geometry_source": authoritative,

            "preserve_constraints": preserve,
            "allowed_render_changes": allowed,
            "forbidden_geometry_changes": list(FORBIDDEN_GEOMETRY_CHANGES),

            "architectural_understanding": (understanding or {}).get("contract") and {
                "contract": (understanding or {}).get("contract"),
                "version": (understanding or {}).get("version"),
                "scope": (understanding or {}).get("scope"),
                "intent_type": (understanding or {}).get("intent_type"),
            } or {},
            "compiled_prompt_reference": {
                "contract": (compiled_prompt or {}).get("contract"),
                "version": (compiled_prompt or {}).get("version"),
                "status": (compiled_prompt or {}).get("status"),
                "deterministic_hash": (compiled_prompt or {}).get("deterministic_hash"),
            } if isinstance(compiled_prompt, dict) and compiled_prompt else {},

            "reference_image_policy": (understanding or {}).get("reference_image_policy") or {},
            "reference_architectural_analysis": {
                "contract": (reference_analysis or {}).get("contract"),
                "analysis_status": (reference_analysis or {}).get("analysis_status"),
                "analysis_hash": (reference_analysis or {}).get("analysis_hash"),
            } if isinstance(reference_analysis, dict) and reference_analysis else {},

            "reference_analysis_ab": reference_ab,

            "render_mode": resolved_mode,
            "render_intent": render_intent,

            "required_context": sorted(set(required_context)),
            "unresolved_requirements": [] if lineage["lineage_complete"] else list(lineage["gaps"]),
            "warnings": warnings,
            "conflicts": conflicts,

            "lineage": lineage,
            "provenance": {
                "builder": "ApprovedDesignRenderContractBuilder",
                "builder_version": VERSION,
                "sources": ["conversation_state"]
                + (["architectural_understanding"] if understanding else [])
                + (["compiled_prompt"] if compiled_prompt else [])
                + (["reference_analysis"] if reference_analysis else []),
                "built_at": time.time(),
                "contract_only": True,
            },
        })

        result["contract_hash"] = self._hash(result)
        return result

    # ------------------------------------------------------
    # empty / blocked contract
    # ------------------------------------------------------

    def _empty(self, status, mode, warnings=None, lineage=None, forbidden=None, reason=None):
        result = ApprovedDesignRenderContractV1({
            "contract": CONTRACT,
            "version": VERSION,
            "status": status,
            "session_id": None,
            "project_id": None,
            "approved_design_id": None,
            "approved_candidate_id": None,
            "approved_candidate_version": None,
            "approved_candidate_hash": None,
            "approval_status": False,
            "approval_timestamp_or_marker": None,
            "approval_provenance": {"reason": reason},
            "design_source_type": "unknown",
            "plan_reference": False,
            "geometry_reference": False,
            "image_reference": False,
            "authoritative_geometry_source": None,
            "preserve_constraints": {},
            "allowed_render_changes": [],
            "forbidden_geometry_changes": list(forbidden or []),
            "architectural_understanding": {},
            "compiled_prompt_reference": {},
            "reference_image_policy": {},
            "reference_architectural_analysis": {},
            "render_mode": mode,
            "render_intent": {},
            "required_context": [],
            "unresolved_requirements": [],
            "warnings": list(warnings or []),
            "conflicts": [],
            "lineage": lineage or {},
            "provenance": {
                "builder": "ApprovedDesignRenderContractBuilder",
                "builder_version": VERSION,
                "built_at": time.time(),
                "contract_only": True,
                "blocked": True,
            },
        })
        result["contract_hash"] = self._hash(result)
        return result

    # ------------------------------------------------------
    # deterministic hash (§23: distinct from design candidate hash)
    # ------------------------------------------------------

    @staticmethod
    def _hash(contract):
        payload = {k: v for k, v in contract.items() if k not in ("contract_hash", "provenance")}
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ==========================================================
# SINGLETON + CONVENIENCE
# ==========================================================

approved_design_render_contract = ApprovedDesignRenderContractBuilder()


def build_render_contract(approval_state, understanding=None, compiled_prompt=None,
                          reference_analysis=None, context=None, mode=None,
                          require_full_lineage=False):
    """Module-level convenience wrapper over the canonical builder."""
    return approved_design_render_contract.build(
        approval_state, understanding=understanding, compiled_prompt=compiled_prompt,
        reference_analysis=reference_analysis, context=context, mode=mode,
        require_full_lineage=require_full_lineage,
    )
