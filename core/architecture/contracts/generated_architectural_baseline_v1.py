"""GeneratedArchitecturalBaselineV1 — HOUSE-DIFFUSION-PRODUCTION-PATH-02A.

ADDITIVE contract for a baseline realized from a FRESH HouseDiffusion
generation (``SemanticPlanCandidateV2``).

It is deliberately NOT the historical frozen
``SemanticArchitecturalPlanBaselineV1`` (phase
``HOUSE-DIFFUSION-BASELINE-ARCHITECTURAL-PLAN-CONSOLIDATION-01``).  A generated
baseline never impersonates that identity:

    baseline_origin        = GENERATED
    source_engine          = HOUSE_DIFFUSION
    source_candidate_schema= SemanticPlanCandidateV2
    realization_contract   = GeneratedBaselineRealizationV1
    generation_policy      = HOUSE_DIFFUSION_GENERATION_POLICY_V1

The historical contract and its verifier are untouched; this module is purely
additive.  ``verify_generated_architectural_baseline`` fails closed.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
import json
from typing import Any

from shapely.geometry import Polygon


CONTRACT = "GeneratedArchitecturalBaselineV1"
VERSION = "1.0"

BASELINE_ORIGIN_GENERATED = "GENERATED"
SOURCE_ENGINE_HOUSE_DIFFUSION = "HOUSE_DIFFUSION"
SOURCE_CANDIDATE_SCHEMA = "SemanticPlanCandidateV2"
REALIZATION_CONTRACT = "GeneratedBaselineRealizationV1"
GENERATION_POLICY = "HOUSE_DIFFUSION_GENERATION_POLICY_V1"

WALL_THICKNESS_METRIC_UNRESOLVED = "WALL_THICKNESS_METRIC_UNRESOLVED"
WINDOW_STATUS_NOT_PROVIDED = "UNRESOLVED_OR_NOT_PROVIDED"

#: The historical consolidation identity a generated baseline must never claim.
FORBIDDEN_HISTORICAL_PHASE = "HOUSE-DIFFUSION-BASELINE-ARCHITECTURAL-PLAN-CONSOLIDATION-01"
FORBIDDEN_HISTORICAL_SCHEMA = "SemanticArchitecturalPlanBaselineV1"

#: Modules of the internal rule-based generator that must never appear in
#: generated-baseline provenance.
FORBIDDEN_INTERNAL_PROVENANCE = (
    "layout_reasoner",
    "spatial_placement_reasoner",
    "plan_model_reasoner",
    "knowledge_space_generator",
    "coherent_floor_plan_resolver",
    "architectural_layout_intelligence",
    "architectural_brain",
    "treemap",
)

METRIC_THICKNESS_KEYS = (
    "thickness_m", "thickness_mm", "thickness_meters",
    "metric_thickness_m", "construction_thickness", "wall_thickness_m",
)


class GeneratedBaselineVerificationError(ValueError):
    """Raised when a generated baseline fails strict verification."""

    code = "GENERATED_BASELINE_VERIFICATION_FAILED"


# ---------------------------------------------------------------------------
# canonical hashing
# ---------------------------------------------------------------------------

def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def canonical_generated_baseline_document(value: Mapping[str, Any]) -> str:
    """Stable serialization, excluding the hash aliases themselves."""
    if not isinstance(value, Mapping):
        raise ValueError("generated baseline must be a mapping")
    payload = deepcopy(dict(value))
    payload.pop("realization_sha256", None)
    payload.pop("candidate_hash", None)
    payload.pop("hash", None)
    return json.dumps(_json_value(payload), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def generated_baseline_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        canonical_generated_baseline_document(value).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _polygon(value: Any) -> Polygon | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    ring: list[tuple[float, float]] = []
    for point in value:
        if not isinstance(point, Sequence) or len(point) < 2:
            return None
        try:
            ring.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError):
            return None
    if len(ring) < 4:
        return None
    try:
        return Polygon(ring)
    except Exception:  # pragma: no cover - defensive
        return None


def _walk(node: Any):
    if isinstance(node, Mapping):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk(item)


def _floors(document: Mapping[str, Any]) -> Mapping[str, Any]:
    floors = document.get("floors")
    return floors if isinstance(floors, Mapping) else {}


def _floor_records(document: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    for floor in sorted(_floors(document), key=str):
        graph = _floors(document)[floor]
        if not isinstance(graph, Mapping):
            continue
        values = graph.get(key)
        if isinstance(values, (list, tuple)):
            records.extend(item for item in values if isinstance(item, Mapping))
    return records


# ---------------------------------------------------------------------------
# strict verifier
# ---------------------------------------------------------------------------

def verify_generated_architectural_baseline(
    document: Mapping[str, Any],
    *,
    source_candidate: Mapping[str, Any] | None = None,
    source_candidate_sha256: str | None = None,
    require_realization_hash: bool = True,
) -> dict[str, Any]:
    """Strictly verify a generated baseline. Returns a check report.

    ``status`` is ``"VERIFIED"`` only when every check passes.  Any failure is
    reported in ``failed_checks`` and the caller must fail closed.
    """
    checks: dict[str, bool] = {}
    detail: dict[str, Any] = {}

    def check(name: str, ok: bool, **info: Any) -> None:
        checks[name] = bool(ok)
        if info:
            detail[name] = info

    if not isinstance(document, Mapping):
        return {"status": "REJECTED", "checks": {}, "failed_checks": ["not_a_mapping"]}

    # ---- identity ---------------------------------------------------------
    check("schema", document.get("schema") == CONTRACT,
          found=document.get("schema"))
    check("contract_version", str(document.get("contract_version")) == VERSION,
          found=document.get("contract_version"))
    check("baseline_origin", document.get("baseline_origin") == BASELINE_ORIGIN_GENERATED)
    check("source_engine", document.get("source_engine") == SOURCE_ENGINE_HOUSE_DIFFUSION)
    check("source_candidate_schema",
          document.get("source_candidate_schema") == SOURCE_CANDIDATE_SCHEMA)
    check("realization_contract", document.get("realization_contract") == REALIZATION_CONTRACT)
    check("generation_policy", document.get("generation_policy") == GENERATION_POLICY)

    # ---- must not impersonate the historical frozen baseline --------------
    check("no_historical_schema_impersonation",
          document.get("schema") != FORBIDDEN_HISTORICAL_SCHEMA)
    check("no_historical_phase_impersonation",
          document.get("phase") != FORBIDDEN_HISTORICAL_PHASE)
    check("baseline_origin_is_not_historical",
          document.get("baseline_origin") != "ACCEPTED_HISTORICAL")

    # ---- source candidate lineage ----------------------------------------
    stored_source_hash = document.get("source_candidate_sha256")
    check("source_candidate_sha256_present",
          isinstance(stored_source_hash, str) and len(stored_source_hash) == 64)
    check("source_candidate_id_present",
          bool(document.get("source_candidate_id")))

    if source_candidate is not None:
        recomputed = hashlib.sha256(
            json.dumps(_json_value(source_candidate), ensure_ascii=False,
                       sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        check("source_candidate_hash_matches_loaded_candidate",
              recomputed == stored_source_hash,
              stored=stored_source_hash, recomputed=recomputed)
    if source_candidate_sha256 is not None:
        check("source_candidate_hash_matches_supplied",
              source_candidate_sha256 == stored_source_hash)

    # ---- spaces -----------------------------------------------------------
    spaces = _floor_records(document, "spaces")
    space_ids = [str(item.get("space_id")) for item in spaces]
    check("spaces_present", bool(spaces), count=len(spaces))
    check("space_ids_unique", len(space_ids) == len(set(space_ids)))
    check("space_ids_all_present", all(sid and sid != "None" for sid in space_ids))

    bad_polygon, bad_hash = [], []
    for item in spaces:
        polygon = _polygon(item.get("polygon"))
        if polygon is None or polygon.is_empty or polygon.area <= 0:
            bad_polygon.append(item.get("space_id"))
            continue
        stored = item.get("geometry_sha256")
        if not isinstance(stored, str) or len(stored) != 64:
            bad_hash.append(item.get("space_id"))
    check("space_polygons_valid", not bad_polygon, offenders=bad_polygon)
    check("space_geometry_refs_present", not bad_hash, offenders=bad_hash)

    # geometry refs must resolve (inline: hash must match the polygon)
    mismatched = []
    for item in spaces:
        polygon = _polygon(item.get("polygon"))
        if polygon is None:
            continue
        recomputed = hashlib.sha256(
            json.dumps([[round(float(x), 9), round(float(y), 9)]
                        for x, y in polygon.exterior.coords],
                       separators=(",", ":")).encode("utf-8")).hexdigest()
        if recomputed != item.get("geometry_sha256"):
            mismatched.append(item.get("space_id"))
    check("geometry_refs_resolve", not mismatched, offenders=mismatched)

    # ---- walls / symbolic thickness --------------------------------------
    walls = _floor_records(document, "walls")
    wall_ids = [str(item.get("wall_id")) for item in walls]
    check("wall_ids_unique", len(wall_ids) == len(set(wall_ids)))

    metric_offenders, claim_offenders, band_offenders = [], [], []
    for item in walls:
        if item.get("construction_claim") is not False:
            claim_offenders.append(item.get("wall_id"))
        band = item.get("wall_band")
        if isinstance(band, Mapping):
            if band.get("construction_claim") is not False:
                claim_offenders.append(item.get("wall_id"))
            if band.get("metric_thickness") not in (None, "UNKNOWN"):
                band_offenders.append(item.get("wall_id"))
            for key in METRIC_THICKNESS_KEYS:
                if band.get(key) is not None:
                    metric_offenders.append(item.get("wall_id"))
        if item.get("thickness_status") != WALL_THICKNESS_METRIC_UNRESOLVED:
            band_offenders.append(item.get("wall_id"))

    check("no_metric_wall_thickness", not metric_offenders, offenders=metric_offenders)
    check("no_construction_claim_on_walls", not claim_offenders, offenders=claim_offenders)
    check("wall_thickness_marked_unresolved", not band_offenders, offenders=band_offenders)

    # ---- openings ---------------------------------------------------------
    openings = _floor_records(document, "openings")
    opening_ids = [str(item.get("opening_id")) for item in openings]
    check("opening_ids_unique", len(opening_ids) == len(set(opening_ids)))

    dangling_hosts = []
    for item in openings:
        host = item.get("host_wall_id")
        status = str(item.get("host_status") or "")
        if host is not None and host not in wall_ids:
            dangling_hosts.append(item.get("opening_id"))
        if host is None and status != "UNRESOLVED":
            dangling_hosts.append(item.get("opening_id"))
    check("no_dangling_opening_hosts", not dangling_hosts, offenders=dangling_hosts)

    known_spaces = set(space_ids) | {"EXTERIOR"}
    bad_sides = []
    for item in openings:
        for key in ("side_a", "side_b"):
            value = item.get(key)
            if value is not None and str(value) not in known_spaces:
                bad_sides.append((item.get("opening_id"), key, value))
    check("opening_sides_resolve", not bad_sides, offenders=bad_sides)

    # ---- windows ----------------------------------------------------------
    windows = _floor_records(document, "windows")
    check("windows_not_fabricated", windows == [])

    # ---- access graph -----------------------------------------------------
    access = document.get("access_graph")
    access = access if isinstance(access, Mapping) else {}
    edges = access.get("edges") if isinstance(access.get("edges"), (list, tuple)) else []
    bad_edges = []
    for edge in edges:
        if not isinstance(edge, Mapping):
            continue
        opening_id = edge.get("opening_id")
        if opening_id is not None and str(opening_id) not in opening_ids:
            bad_edges.append(edge)
        for key in ("a", "b"):
            value = edge.get(key)
            if value is not None and str(value) not in known_spaces:
                bad_edges.append(edge)
    check("no_dangling_access_references", not bad_edges, count=len(bad_edges))
    check("access_edges_have_explicit_evidence",
          all(str(edge.get("evidence") or "").startswith("EXPLICIT")
              for edge in edges if isinstance(edge, Mapping)))

    # ---- internal generator provenance -----------------------------------
    provenance_blob = json.dumps(
        _json_value(document.get("generator_lineage")), ensure_ascii=False).lower()
    offenders = [name for name in FORBIDDEN_INTERNAL_PROVENANCE if name in provenance_blob]
    check("no_internal_generator_provenance", not offenders, offenders=offenders)
    check("realization_derived_only",
          (document.get("realization") or {}).get("derived_only") is True)

    # ---- determinism ------------------------------------------------------
    if require_realization_hash:
        stored = document.get("realization_sha256")
        check("realization_sha256_present",
              isinstance(stored, str) and len(stored) == 64)
        if isinstance(stored, str):
            check("realization_hash_matches", stored == generated_baseline_sha256(document))

    failed = sorted(name for name, ok in checks.items() if not ok)
    return {
        "status": "VERIFIED" if not failed else "REJECTED",
        "checks": checks,
        "failed_checks": failed,
        "detail": detail,
        "realization_sha256": document.get("realization_sha256"),
        "source_candidate_sha256": stored_source_hash,
    }


def assert_generated_architectural_baseline(document: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Verify and raise ``GeneratedBaselineVerificationError`` on failure."""
    report = verify_generated_architectural_baseline(document, **kwargs)
    if report["status"] != "VERIFIED":
        raise GeneratedBaselineVerificationError(
            f"{GeneratedBaselineVerificationError.code}: {report['failed_checks']}")
    return report


__all__ = [
    "CONTRACT", "VERSION", "BASELINE_ORIGIN_GENERATED",
    "SOURCE_ENGINE_HOUSE_DIFFUSION", "SOURCE_CANDIDATE_SCHEMA",
    "REALIZATION_CONTRACT", "GENERATION_POLICY",
    "WALL_THICKNESS_METRIC_UNRESOLVED", "WINDOW_STATUS_NOT_PROVIDED",
    "FORBIDDEN_HISTORICAL_PHASE", "FORBIDDEN_HISTORICAL_SCHEMA",
    "FORBIDDEN_INTERNAL_PROVENANCE", "METRIC_THICKNESS_KEYS",
    "GeneratedBaselineVerificationError",
    "canonical_generated_baseline_document", "generated_baseline_sha256",
    "verify_generated_architectural_baseline", "assert_generated_architectural_baseline",
]
