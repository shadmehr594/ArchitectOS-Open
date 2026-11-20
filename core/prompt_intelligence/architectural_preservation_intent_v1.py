"""Bounded preservation scope for an existing architectural edit decision.

This module does not classify images, localise pixels, select workflows or
authorise rendering.  It projects evidence and requirements already owned by
``GeometryAuthorityHandoffV1`` into three explicit scopes and reports whether
the caller-supplied workflow capability record can enforce them.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Dict, Iterable, List, Mapping, Sequence


CONTRACT = "ArchitecturalPreservationIntentV1"
VERSION = "1.0"
CAPABILITY_INSUFFICIENT = "PRESERVATION_CAPABILITY_INSUFFICIENT"
CAPABILITY_VERIFIED = "PRESERVATION_CAPABILITY_VERIFIED"

GROUNDING_CATEGORIES = (
    "directly_observed",
    "model_reported_but_unverified",
    "architecturally_interpreted",
    "user_specified",
    "computed_or_derived",
    "unknown",
)


_ARCHITECTURE_TERMS = (
    ("building_massing", ("massing", "building mass", "silhouette", "حجم", "فرم کلی")),
    ("floor_count", ("floor count", "number of floors", "storey count", "story count", "تعداد طبقات", "تعداد طبقه")),
    ("structural_grid", ("structural frame", "structural grid", "column grid", "structure", "سازه", "شبکه سازه", "ستون")),
    ("windows_and_openings", ("windows", "window", "openings", "opening layout", "opening positions", "بازشو", "پنجره")),
    ("balcony_and_terrace_boundaries", ("balcony geometry", "balconies", "balcony", "terrace edges", "terrace boundaries", "terrace", "بالکن", "لبه تراس", "تراس")),
    ("ground_floor_open_bays", ("ground-floor open bays", "ground floor open bays", "ground-floor openness", "open ground level", "open bays", "دهانه های باز", "باز بودن همکف")),
    ("roof_geometry", ("roof geometry", "roof shape", "roof configuration", "roofline", "roof", "هندسه بام", "فرم بام", "بام", "سقف")),
    ("camera_perspective", ("camera perspective", "perspective", "camera", "پرسپکتیو", "دوربین")),
)

_CONTEXT_TERMS = (
    ("courtyard", ("courtyard", "حیاط")),
    ("foreground_ground_surfaces", ("foreground ground surfaces", "foreground", "ground surfaces", "سطوح پیش زمینه", "کف پیش زمینه")),
    ("retaining_walls", ("retaining walls", "retaining wall", "دیوار حائل", "دیوارهای حائل")),
    ("adjacent_buildings", ("adjacent buildings", "neighbouring buildings", "neighboring buildings", "ساختمان های مجاور", "ساختمان‌های مجاور")),
    ("neighbouring_architectural_details", ("neighbouring architectural details", "neighboring architectural details", "جزئیات معماری مجاور")),
    ("surrounding_site_layout", ("surrounding site layout", "site layout", "surrounding site", "محوطه پیرامون", "چیدمان سایت")),
)

_FIXED_DOMAIN_MAP = {
    "massing": "building_massing",
    "number_of_floors": "floor_count",
    "floor_count": "floor_count",
    "overall_massing": "building_massing",
    "building_silhouette": "building_massing",
    "opening": "windows_and_openings",
    "main_window_positions": "windows_and_openings",
    "main_door_positions": "windows_and_openings",
    "circulation": "balcony_and_terrace_boundaries",
    "roof": "roof_geometry",
    "roofline": "roof_geometry",
    "camera": "camera_perspective",
}

_EDITABLE_LABELS = {
    "facade_surface_expression": "main_facade_surface_expression",
    "facade_wall_surface": "main_facade_surface_finish",
    "lighting": "lighting",
    "atmosphere": "atmosphere",
}


def _unique(values: Iterable[Any]) -> List[Any]:
    result = []
    for value in values:
        if value not in result:
            result.append(deepcopy(value))
    return result


def _claim(
    claim_id: str,
    *,
    category: str,
    source: str,
    verification_status: str,
    confidence: Any = None,
    evidence: Any = None,
) -> Dict[str, Any]:
    if category not in GROUNDING_CATEGORIES:
        category = "unknown"
    return {
        "id": claim_id,
        "grounding_category": category,
        "source": source,
        "verification_status": verification_status,
        "confidence": confidence,
        "evidence": deepcopy(evidence),
    }


def _normalise_text(value: Any) -> str:
    return " ".join(str(value or "").lower().replace("\u200c", " ").split())


def _explicit_requirements(
    clauses: Sequence[Any], vocabulary: Sequence[Any]
) -> List[Dict[str, Any]]:
    text = _normalise_text(" ".join(str(item) for item in clauses if item))
    if not text:
        return []
    result = []
    for claim_id, aliases in vocabulary:
        matched = next((term for term in aliases if _normalise_text(term) in text), None)
        if matched:
            result.append(_claim(
                claim_id,
                category="user_specified",
                source="explicit_preservation_clause",
                verification_status="REQUIREMENT_NOT_OBSERVATION",
                confidence="EXPLICIT",
                evidence=matched,
            ))
    return result


def _fixed_requirements(fixed_constraints: Mapping[str, Any]) -> List[Dict[str, Any]]:
    result = []
    for value in list(fixed_constraints.get("domains") or []) + list(
        fixed_constraints.get("elements") or []
    ):
        raw = str(value)
        claim_id = _FIXED_DOMAIN_MAP.get(raw, raw.strip().lower().replace(" ", "_"))
        if claim_id:
            result.append(_claim(
                claim_id,
                category="computed_or_derived",
                source="GeometryAuthorityHandoffV1.fixed_constraints",
                verification_status="REQUIREMENT_NOT_OBSERVATION",
                confidence=None,
                evidence=raw,
            ))
    return result


def _merge_claims(*groups: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen = set()
    for group in groups:
        for item in group:
            key = item.get("id")
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(deepcopy(item))
    return result


def _observation_claim(item: Mapping[str, Any]) -> Dict[str, Any]:
    evidence_class = str(item.get("evidence_class") or "").upper()
    status = str(item.get("verification_status") or "UNKNOWN").upper()
    if evidence_class in ("DIRECTLY_OBSERVED", "VERIFIED_OBSERVATION") and status in (
        "VERIFIED", "OBSERVED", "DIRECTLY_OBSERVED",
    ):
        category = "directly_observed"
    elif evidence_class == "MODEL_REPORTED":
        category = "model_reported_but_unverified"
        if status in ("VERIFIED", "OBSERVED"):
            status = "UNVERIFIED"
    elif evidence_class in ("INTERPRETED", "ARCHITECTURALLY_INTERPRETED"):
        category = "architecturally_interpreted"
    else:
        category = "unknown"
    return _claim(
        str(item.get("element") or "unknown_element"),
        category=category,
        source="image_supported_context",
        verification_status=status,
        confidence=item.get("confidence"),
        evidence={
            "source_quote": item.get("source_quote"),
            "kinds": deepcopy(item.get("kinds") or item.get("kind") or []),
        },
    )


def _material_style_requirements(requested: Mapping[str, Any], user_text: str) -> Dict[str, Any]:
    text = _normalise_text(user_text)
    material = requested.get("material")
    style = requested.get("style")
    return {
        "style": _claim(
            str(style), category="user_specified", source="requested_operation",
            verification_status="REQUIREMENT_NOT_OBSERVATION", confidence="EXPLICIT",
            evidence=style,
        ) if style else None,
        "material": _claim(
            str(material), category="user_specified", source="requested_operation",
            verification_status="REQUIREMENT_NOT_OBSERVATION", confidence="EXPLICIT",
            evidence=material,
        ) if material else None,
        "appearance_qualifiers": [
            value for value, aliases in (
                ("refined", ("refined", "پرداخته", "ظریف")),
                ("restrained", ("restrained", "خویشتندار", "ملایم")),
                ("cream", ("cream", "کرم")),
                ("subtle_stone_texture", ("subtle stone texture", "بافت ظریف سنگ")),
            ) if any(_normalise_text(alias) in text for alias in aliases)
        ],
        "excluded_material_expressions": [
            value for value, aliases in (
                ("rustic_block_stone", ("rustic block stone", "rough block stone", "rustic masonry", "سنگ بلوکی خشن")),
                ("heavy_gold_veining", ("gold veining", "heavy veining", "رگه طلایی")),
            ) if any(_normalise_text(alias) in text for alias in aliases)
        ],
    }


def _has_any(text: str, values: Sequence[str]) -> bool:
    return any(_normalise_text(value) in text for value in values)


def _affirmative_clauses(user_text: str) -> List[str]:
    """Return explicit non-negated clauses for completion admission.

    Completion evidence must coexist in one affirmative clause. This prevents
    unrelated phrases elsewhere in a long request, or an explicit prohibition,
    from becoming an allowed operation.
    """

    clauses = []
    negations = (
        "do not", "don't", "never", "must not", "without adding",
        "اضافه نکن", "نصب نکن", "ایجاد نکن", "تغییر نده", "نباید",
    )
    for raw in re.split(r"[.!?\n\r؛]+", str(user_text or "")):
        clause = _normalise_text(raw)
        if clause and not _has_any(clause, negations):
            clauses.append(clause)
    return clauses


def _completion_item(
    operation_id: str,
    target: str,
    boundary: str,
    evidence: str,
) -> Dict[str, Any]:
    return {
        "id": operation_id,
        "operation_type": "architectural_completion",
        "target": target,
        "allowed_boundary": boundary,
        "grounding_category": "user_specified",
        "source": "requested_operation.source_text",
        "verification_status": "REQUESTED_NOT_EXECUTED",
        "spatial_status": "SEMANTIC_BOUNDARY_NOT_SPATIALLY_VERIFIED",
        "geometry_change_authorized": False,
        "evidence": evidence,
    }


def _architectural_completion(
    user_text: str,
    requested: Mapping[str, Any],
    image_supported_context: Sequence[Mapping[str, Any]],
    material_requirements: Mapping[str, Any],
) -> Dict[str, Any]:
    """Separate completion inside existing geometry from geometry alteration.

    The operation list is created only from explicit user language.  Its
    boundaries are semantic constraints, never masks or verified coordinates.
    """

    text = _normalise_text(user_text)
    affirmative_clauses = _affirmative_clauses(user_text)
    operations: List[Dict[str, Any]] = []

    opening_boundaries = (
        "existing openings", "existing window openings", "within the openings",
        "inside the openings", "داخل بازشوهای موجود", "در بازشوهای موجود",
    )
    completion_verbs = (
        "complete", "install", "provide", "fit", "finish", "add",
        "تکمیل", "نصب", "اجرا",
    )
    window_terms = (
        "windows", "window frames", "frames", "glazing", "پنجره", "قاب", "شیشه",
    )
    window_clause = next((
        clause for clause in affirmative_clauses
        if _has_any(clause, opening_boundaries)
        and _has_any(clause, completion_verbs)
        and _has_any(clause, window_terms)
    ), None)

    if window_clause:
        operations.append(_completion_item(
            "complete_windows_within_existing_openings",
            "existing_window_openings",
            "inside existing opening positions, dimensions and structural boundaries",
            window_clause,
        ))

    door_boundaries = (
        "existing doorway", "existing door opening", "existing entrance opening",
        "within the doorway", "inside existing openings",
        "داخل بازشوی در موجود", "داخل بازشوهای موجود", "درگاه موجود",
    )
    door_terms = (
        "door", "doors", "door frame", "در و پنجره", "درها", "درب", "قاب در",
    )
    door_clause = next((
        clause for clause in affirmative_clauses
        if _has_any(clause, door_boundaries)
        and _has_any(clause, completion_verbs)
        and _has_any(clause, door_terms)
    ), None)
    if door_clause:
        operations.append(_completion_item(
            "install_door_within_existing_doorway",
            "existing_doorway",
            "inside the known existing doorway without resizing or relocating it",
            door_clause,
        ))

    column_terms = (
        "pilasters", "capitals", "column cladding", "decorative column treatment",
        "پیلستر", "سرستون", "پوشش ستون", "تزیین ستون",
    )
    column_clause = next((
        clause for clause in affirmative_clauses
        if _has_any(clause, column_terms)
    ), None)
    if column_clause:
        operations.append(_completion_item(
            "apply_decorative_column_treatment",
            "existing_structural_columns",
            "surface cladding or applied relief on existing column positions",
            column_clause,
        ))

    balcony_terms = (
        "finish existing balcony", "finish existing terrace",
        "balustrades on existing terrace edges", "details within existing balcony",
        "تکمیل بالکن موجود", "تکمیل تراس موجود", "نرده روی لبه تراس موجود",
        "بالکن ها را تکمیل", "بالکن‌ها را تکمیل",
        "تراس ها را تکمیل", "تراس‌ها را تکمیل",
    )
    balcony_clause = next((
        clause for clause in affirmative_clauses
        if _has_any(clause, balcony_terms)
    ), None)
    if balcony_clause:
        operations.append(_completion_item(
            "finish_balcony_within_existing_boundaries",
            "existing_balcony_and_terrace_boundaries",
            "finishing details within existing edges only",
            balcony_clause,
        ))

    requested_material = material_requirements.get("material")
    if (
        isinstance(requested_material, Mapping)
        and requested_material.get("id")
        and requested.get("operation") in ("replace_finish", "restyle")
    ):
        operations.append(_completion_item(
            "replace_requested_facade_surface_material",
            "main_facade_surface_finish",
            "facade finish surfaces only; source structure and non-target materials remain protected",
            "requested finish material: " + str(requested_material["id"]),
        ))

    source_materials = []
    material_terms = (
        "brick", "block", "masonry", "unfinished concrete", "exposed concrete",
        "آجر", "بلوک", "بنایی ناتمام", "بتن اکسپوز",
    )
    for item in image_supported_context or []:
        if not isinstance(item, Mapping):
            continue
        evidence_text = _normalise_text(" ".join((
            str(item.get("element") or ""),
            str(item.get("source_quote") or ""),
            " ".join(str(value) for value in (
                item.get("kinds") or item.get("kind") or []
            )),
        )))
        if _has_any(evidence_text, material_terms):
            source_materials.append(_observation_claim(item))

    forbidden = []
    operation_ids = {item["id"] for item in operations}
    if "complete_windows_within_existing_openings" in operation_ids:
        forbidden.extend((
            "create_new_window_openings", "relocate_window_openings",
            "enlarge_window_openings", "change_opening_structural_boundaries",
        ))
    if "install_door_within_existing_doorway" in operation_ids:
        forbidden.extend((
            "create_new_door_openings", "relocate_doorways", "enlarge_doorways",
        ))
    if "apply_decorative_column_treatment" in operation_ids:
        forbidden.extend((
            "relocate_structural_columns", "resize_structural_columns",
            "create_unsupported_structural_members",
        ))
    if "finish_balcony_within_existing_boundaries" in operation_ids:
        forbidden.extend(("add_balconies", "relocate_balconies", "extend_balcony_boundaries"))

    return {
        "status": "REQUESTED" if operations else "NOT_REQUESTED",
        "allowed_operations": operations,
        "preserve_existing_geometry": True,
        "geometry_change_authorized": False,
        "forbidden_geometric_operations": _unique(forbidden),
        "material_transition": {
            "existing_construction_materials": source_materials,
            "requested_finish_material": deepcopy(requested_material),
            "source_construction_material_is_mandatory_final_finish": False,
            "interpretation": (
                "replace_observed_construction_surface_with_requested_finish"
                if requested_material else "no_finish_replacement_established"
            ),
        },
        "spatial_authority": {
            "status": "SEMANTIC_ONLY_NOT_SPATIALLY_VERIFIED",
            "mask": None,
            "pixel_coordinates": None,
            "segmentation": None,
        },
    }


def _capability_assessment(
    protected_architecture: Sequence[Dict[str, Any]],
    protected_context: Sequence[Dict[str, Any]],
    capabilities: Mapping[str, Any],
) -> Dict[str, Any]:
    required = [
        "source_bound_editing",
        "protected_building_geometry_enforcement",
        "protected_context_pixel_enforcement",
        "localized_design_target_enforcement",
        "post_render_architectural_verification",
    ]
    evidence = capabilities.get("evidence")
    evidence = evidence if isinstance(evidence, Mapping) else {}
    verified = set()
    for key in required:
        record = evidence.get(key)
        if not (
            capabilities.get(key) is True
            and isinstance(record, Mapping)
            and record.get("capability") == key
            and record.get("validation_status") == "ACCEPTED"
            and record.get("workflow")
            and record.get("evidence_id")
        ):
            continue
        verified.add(key)
    missing = [key for key in required if key not in verified]
    status = CAPABILITY_VERIFIED if not missing else CAPABILITY_INSUFFICIENT
    return {
        "status": status,
        "enforceable": not missing,
        "required_capabilities": required,
        "available_capabilities": deepcopy(dict(capabilities)),
        "verified_capabilities": sorted(verified),
        "missing_capabilities": missing,
        "protected_architecture_count": len(protected_architecture),
        "protected_context_count": len(protected_context),
        "truth_constraints": {
            "prompt_only_is_hard_preservation": False,
            "soft_depth_is_exact_geometry_lock": False,
            "node_wiring_is_visual_acceptance": False,
        },
    }


def build_architectural_preservation_intent_v1(
    *,
    user_text: str,
    requested_operation: Mapping[str, Any],
    editable_elements: Sequence[Any],
    fixed_constraints: Mapping[str, Any],
    explicit_preservation_clauses: Sequence[Any] = (),
    image_supported_context: Sequence[Mapping[str, Any]] = (),
    workflow_capabilities: Mapping[str, Any] | None = None,
    experiment_evidence: Mapping[str, Any] | None = None,
    user_prohibitions: Sequence[Any] = (),
) -> Dict[str, Any]:
    """Build an additive, fail-closed scope contract from existing inputs."""
    requested = deepcopy(dict(requested_operation or {}))
    clauses = list(explicit_preservation_clauses or [])
    protected_architecture = _merge_claims(
        _explicit_requirements(clauses, _ARCHITECTURE_TERMS),
        _fixed_requirements(fixed_constraints or {}),
    )
    protected_context = _explicit_requirements(clauses, _CONTEXT_TERMS)
    design_target = [
        _claim(
            _EDITABLE_LABELS.get(str(value), str(value)),
            category="architecturally_interpreted",
            source="GeometryAuthorityHandoffV1.editable_elements",
            verification_status="SEMANTIC_TARGET_NOT_SPATIALLY_VERIFIED",
            confidence=None,
            evidence=str(value),
        )
        for value in editable_elements or []
    ]
    observations = [
        _observation_claim(item) for item in image_supported_context or []
        if isinstance(item, Mapping)
    ]
    forbidden = ["change:" + item["id"] for item in protected_architecture]
    forbidden += ["change_context:" + item["id"] for item in protected_context]
    forbidden += [
        "user_prohibition:" + str(item) for item in user_prohibitions or []
        if str(item).strip()
    ]
    capability = _capability_assessment(
        protected_architecture, protected_context, workflow_capabilities or {}
    )
    material_requirements = _material_style_requirements(requested, user_text)
    completion = _architectural_completion(
        user_text,
        requested,
        image_supported_context,
        material_requirements,
    )
    completion["execution_capability_status"] = capability["status"]
    forbidden += [
        "geometry:" + value
        for value in completion["forbidden_geometric_operations"]
    ]
    return {
        "contract": CONTRACT,
        "version": VERSION,
        "requested_transformation": _claim(
            str(requested.get("operation") or "change"),
            category="user_specified",
            source="requested_operation.source_text",
            verification_status="REQUESTED_NOT_EXECUTED",
            confidence="EXPLICIT",
            evidence=requested.get("source_text") or user_text,
        ),
        "scopes": {
            "design_target": design_target,
            "protected_architecture": protected_architecture,
            "protected_context": protected_context,
        },
        "material_style_requirements": material_requirements,
        "architectural_completion": completion,
        "forbidden_transformations": _unique(forbidden),
        "evidence_register": observations,
        "grounding_categories": list(GROUNDING_CATEGORIES),
        "unknowns_and_limitations": [
            "semantic targets are not masks or pixel regions",
            "model-reported observations remain unverified",
            "visual preservation requires comparison with a real output",
        ],
        "spatial_authority": {
            "status": "UNKNOWN",
            "mask": None,
            "pixel_coordinates": None,
            "segmentation": None,
        },
        "preservation_capability": capability,
        "experiment_evidence": deepcopy(dict(experiment_evidence or {})),
        "automatic_r4_approval": False,
        "render_executed": False,
        "comfy_invoked": False,
    }
