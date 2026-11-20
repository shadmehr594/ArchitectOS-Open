"""Transactional 01H daylight/window realization on canonical candidate graphs.

The realizer consumes an explicitly selected strategy plus caller-proved
dimensions and position.  It creates only a semantic/geometric WINDOW portal
inside the cloned candidate's canonical opening-host graph.  It never creates
BIM/IFC objects, redesigns a facade, or infers site/solar orientation.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from math import hypot
from typing import Any, Mapping

from shapely.geometry import LineString, Polygon

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeStrategy,
    ExecutionReadinessResult,
    READINESS_STATUS_READY,
    READINESS_STATUS_READY_WITH_PREREQUISITES,
)
from core.architecture.contracts.architectural_change_window_daylight_contracts_v1 import (
    WINDOW_DAYLIGHT_STATUS_FAILED,
    WINDOW_DAYLIGHT_STATUS_REALIZED,
    WINDOW_DAYLIGHT_STATUS_REALIZED_WITH_WARNINGS,
    WINDOW_DAYLIGHT_STATUS_REJECTED_CONSTRAINT,
    WINDOW_DAYLIGHT_STATUS_REJECTED_DAYLIGHT_EVIDENCE,
    WINDOW_DAYLIGHT_STATUS_REJECTED_PRIVACY,
    WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
    WINDOW_DAYLIGHT_STATUS_STALE_PARENT,
    WINDOW_DAYLIGHT_STATUS_UNSUPPORTED_STRATEGY,
    WindowDaylightDelta,
    WindowDaylightRealizationResult,
)
from core.architecture.reasoning.architectural_change_space_geometry_realizer_v1 import (
    candidate_semantic_hash,
)


REALIZER_VERSION = "architectural_change_window_daylight_realizer_v1"
SUPPORTED_EXECUTION_FAMILY = "WINDOW_DAYLIGHT_REALIZATION"
SUPPORTED_OPERATIONS = frozenset({
    "CREATE_WINDOW_OPPORTUNITY",
    "ENLARGE_EXISTING_WINDOW",
    "REPOSITION_WINDOW_FOR_DAYLIGHT",
})
SUPPORTED_STRATEGY_TYPES = frozenset({
    "DAYLIGHT_EXPOSURE_RELATIONSHIP",
    "IMPROVE_DAYLIGHT",
    "CREATE_WINDOW_OPPORTUNITY",
    "ENLARGE_EXISTING_WINDOW",
    "REPOSITION_WINDOW_FOR_DAYLIGHT",
    "FACADE_OPPORTUNITY_RELATIONSHIP",
})
_EPSILON = 1e-7


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_tuple(values: Any) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if isinstance(value, str) and value}))


def _identity(candidate: Mapping[str, Any]) -> tuple[str | None, str | None]:
    identity = candidate.get("candidate_id") or candidate.get("id")
    version = candidate.get("candidate_version") or candidate.get("version")
    return (
        str(identity) if identity is not None else None,
        str(version) if version is not None else None,
    )


def _nested_root(candidate: Mapping[str, Any], key: str) -> Any:
    direct = candidate.get(key)
    if direct is not None:
        return direct
    extraction = candidate.get("boundary_extraction")
    return extraction.get(key) if isinstance(extraction, Mapping) else None


def _floor_graph(candidate: Mapping[str, Any], key: str, floor: str) -> Mapping[str, Any] | None:
    root = _nested_root(candidate, key)
    if not isinstance(root, Mapping):
        return None
    graph = root.get(floor)
    return graph if isinstance(graph, Mapping) else None


def _space_records(candidate: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    root = _nested_root(candidate, "space_boundary_graphs")
    records: list[dict[str, Any]] = []
    if not isinstance(root, Mapping):
        return ()
    for floor in sorted(root, key=str):
        graph = root[floor]
        if isinstance(graph, Mapping) and isinstance(graph.get("spaces"), list):
            records.extend(item for item in graph["spaces"] if isinstance(item, dict))
    return tuple(records)


def _execution_evidence(strategy: ArchitecturalChangeStrategy, candidate: Mapping[str, Any]) -> Mapping[str, Any] | None:
    sources: list[Any] = []
    if isinstance(strategy.provenance, Mapping):
        sources.extend((
            strategy.provenance.get("window_daylight_realization"),
            strategy.provenance.get("execution_evidence"),
        ))
    candidate_evidence = candidate.get("realization_evidence")
    if isinstance(candidate_evidence, Mapping):
        sources.append(candidate_evidence.get(strategy.strategy_id))
    return next((item for item in sources if isinstance(item, Mapping)), None)


def _line(value: Any) -> LineString | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        result = LineString(value)
    except (TypeError, ValueError):
        return None
    if result.is_empty or result.length <= _EPSILON:
        return None
    if abs(result.length - hypot(
        result.coords[-1][0] - result.coords[0][0],
        result.coords[-1][1] - result.coords[0][1],
    )) > _EPSILON:
        return None
    return result


def _opening_line(opening: Mapping[str, Any]) -> LineString | None:
    return _line(opening.get("centerline") or opening.get("opening_segment"))


def _find_window(candidate: Mapping[str, Any], window_id: str) -> tuple[str, dict[str, Any]] | None:
    root = _nested_root(candidate, "opening_host_graphs")
    if not isinstance(root, Mapping):
        return None
    matches: list[tuple[str, dict[str, Any]]] = []
    for floor in sorted(root, key=str):
        graph = root[floor]
        if not isinstance(graph, Mapping):
            continue
        for opening in graph.get("openings", ()):
            if (
                isinstance(opening, dict)
                and opening.get("opening_id") == window_id
                and str(opening.get("kind") or opening.get("type") or "").upper() == "WINDOW"
            ):
                matches.append((str(floor), opening))
    return matches[0] if len(matches) == 1 else None


def _all_openings(candidate: Mapping[str, Any], floor: str) -> tuple[Mapping[str, Any], ...]:
    graph = _floor_graph(candidate, "opening_host_graphs", floor)
    if not isinstance(graph, Mapping):
        return ()
    raw = graph.get("openings", ())
    return tuple(item for item in raw if isinstance(item, Mapping))


def _valid_orientation_evidence(candidate: Mapping[str, Any]) -> bool:
    for key in ("site_orientation_evidence", "orientation_evidence"):
        evidence = candidate.get(key)
        if not isinstance(evidence, Mapping):
            continue
        status = str(evidence.get("status") or evidence.get("evidence_status") or "").upper()
        source = evidence.get("source") or evidence.get("provenance")
        if status in {"VERIFIED", "AUTHORITATIVE", "RESOLVED"} and source:
            return True
    return False


def _resolve_exterior_host(
    candidate: Mapping[str, Any],
    space: Mapping[str, Any],
    boundary_ref: str,
    declared_segment: LineString,
) -> Mapping[str, Any] | None:
    """Prove an exterior host from space, paired wall faces, and floor envelope."""
    floor = str(space.get("floor"))
    face_graph = _floor_graph(candidate, "wall_face_graphs", floor)
    solid_graph = _floor_graph(candidate, "wall_solid_graphs", floor)
    if face_graph is None or solid_graph is None:
        return None
    pairs = [item for item in face_graph.get("pairs", ()) if isinstance(item, Mapping) and item.get("wall_pair_id") == boundary_ref]
    faces = {
        str(item.get("face_id")): item
        for item in face_graph.get("faces", ())
        if isinstance(item, Mapping) and item.get("face_id") is not None
    }
    solids = [
        item for item in solid_graph.get("solids", ())
        if isinstance(item, Mapping) and boundary_ref in item.get("source_pair_ids", ())
    ]
    envelopes = [item for item in solid_graph.get("floor_envelopes", ()) if isinstance(item, Mapping)]
    if len(pairs) != 1 or len(solids) != 1 or not envelopes:
        return None
    pair = pairs[0]
    first, second = faces.get(str(pair.get("face_a"))), faces.get(str(pair.get("face_b")))
    if first is None or second is None:
        return None
    try:
        space_boundary = Polygon(space["polygon"]).boundary
    except (KeyError, TypeError, ValueError):
        return None
    if space_boundary.is_empty:
        return None
    face_lines = []
    for face in (first, second):
        line = _line((face.get("start"), face.get("end")))
        if line is None:
            return None
        face_lines.append((face, line))
    envelope_boundaries = []
    for envelope in envelopes:
        try:
            polygon = Polygon(envelope["polygon"])
        except (KeyError, TypeError, ValueError):
            continue
        if polygon.is_valid and not polygon.is_empty:
            envelope_boundaries.append((envelope, polygon.boundary))
    matches = []
    for inner_index, (inner_face, inner_line) in enumerate(face_lines):
        outer_face, outer_line = face_lines[1 - inner_index]
        inner_matches = (
            declared_segment.difference(inner_line.buffer(_EPSILON)).length <= _EPSILON
            and declared_segment.difference(space_boundary.buffer(_EPSILON)).length <= _EPSILON
        )
        for envelope, envelope_boundary in envelope_boundaries:
            outer_matches = outer_line.difference(envelope_boundary.buffer(_EPSILON)).length <= _EPSILON
            if inner_matches and outer_matches:
                matches.append((inner_face, outer_face, envelope, inner_line, outer_line))
    if len(matches) != 1:
        return None
    inner_face, outer_face, envelope, inner_line, outer_line = matches[0]
    return {
        "relation": "SPACE_TO_VERIFIED_EXTERIOR_ENVELOPE_WALL",
        "space_id": str(space.get("space_id")),
        "floor": floor,
        "host_wall_pair_id": boundary_ref,
        "interior_face_id": inner_face.get("face_id"),
        "exterior_face_id": outer_face.get("face_id"),
        "wall_solid_id": solids[0].get("wall_solid_id"),
        "envelope_id": envelope.get("envelope_id"),
        "envelope_source": envelope.get("source"),
        "orientation_claimed": False,
        "proof": "space_boundary+paired_wall_faces+closed_source_perimeter_envelope",
    }


def _constraint_failures(candidate: Mapping[str, Any], target_id: str, boundary_ref: str, window_id: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    general: set[str] = set()
    privacy: set[str] = set()
    protected = candidate.get("protected_entities", ())
    if isinstance(protected, (list, tuple, set, frozenset)):
        values = {str(item) for item in protected}
        if {target_id, boundary_ref, window_id} & values:
            general.add("protected_space_wall_facade_or_window")
    for key in ("protected_constraints", "hard_constraints", "privacy_constraints"):
        raw = candidate.get(key)
        records = raw.values() if isinstance(raw, Mapping) else raw
        if not isinstance(records, (list, tuple, set, frozenset)):
            continue
        for item in records:
            if isinstance(item, str):
                text = item.lower()
                if any(token in text for token in (target_id.lower(), boundary_ref.lower(), window_id.lower())):
                    (privacy if "privacy" in text else general).add(item)
                continue
            if not isinstance(item, Mapping):
                continue
            targets = {
                str(value) for value in (
                    item.get("entity_id"), item.get("space_id"), item.get("boundary_ref"),
                    item.get("facade_ref"), item.get("window_id"),
                ) if value is not None
            }
            extra = item.get("entities") or item.get("targets") or ()
            if isinstance(extra, (list, tuple, set, frozenset)):
                targets.update(str(value) for value in extra)
            protected_record = item.get("protected") is True or str(item.get("severity") or "").lower() == "hard" or key == "privacy_constraints"
            if not protected_record or not ({target_id, boundary_ref, window_id} & targets):
                continue
            text = _canonical(item).lower()
            identity = str(item.get("constraint_id") or item.get("id") or "protected_constraint")
            (privacy if "privacy" in text or key == "privacy_constraints" else general).add(identity)
    return _stable_tuple(general), _stable_tuple(privacy)


def _rejection(
    strategy: ArchitecturalChangeStrategy,
    parent_id: str,
    parent_hash: str,
    status: str,
    failures: tuple[str, ...],
    *,
    rejected_operations: tuple[str, ...] = (),
    geometry_checks: tuple[Mapping[str, Any], ...] = (),
    daylight_checks: tuple[Mapping[str, Any], ...] = (),
    privacy_checks: tuple[Mapping[str, Any], ...] = (),
    constraint_checks: tuple[Mapping[str, Any], ...] = (),
) -> tuple[None, WindowDaylightRealizationResult]:
    token = hashlib.sha256(
        f"{parent_hash}|{strategy.strategy_id}|{status}|{'|'.join(failures)}".encode("utf-8")
    ).hexdigest()[:16]
    return None, WindowDaylightRealizationResult(
        realization_id=f"window-daylight-realization:{token}",
        strategy_id=strategy.strategy_id,
        parent_candidate_id=parent_id,
        derived_candidate_id=None,
        status=status,
        window_daylight_changes=(),
        affected_entities=(),
        applied_operations=(),
        rejected_operations=rejected_operations,
        geometry_checks=geometry_checks,
        daylight_checks=daylight_checks,
        privacy_checks=privacy_checks,
        constraint_checks=constraint_checks,
        required_downstream_rechecks=(),
        warnings=(),
        failures=failures,
        parent_hash=parent_hash,
        derived_hash=None,
        provenance={
            "phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01H",
            "realizer": REALIZER_VERSION,
            "commit": False,
            "parent_unchanged": True,
            "orientation_inferred": False,
            "physical_bim_or_ifc_object_created": False,
        },
    )


def realize_selected_window_daylight_strategy(
    strategy: ArchitecturalChangeStrategy,
    readiness: ExecutionReadinessResult,
    parent_candidate: Mapping[str, Any],
    *,
    expected_parent_id: str,
    expected_parent_version: str,
    expected_parent_hash: str,
) -> tuple[dict[str, Any] | None, WindowDaylightRealizationResult]:
    """Apply one proved window/daylight delta to a deep-cloned candidate."""
    if not isinstance(strategy, ArchitecturalChangeStrategy):
        raise ValueError("strategy must be ArchitecturalChangeStrategy")
    if not isinstance(readiness, ExecutionReadinessResult):
        raise ValueError("readiness must be ExecutionReadinessResult")
    if not isinstance(parent_candidate, Mapping):
        raise ValueError("parent_candidate must be a mapping")

    parent_document_before = _canonical(parent_candidate)
    parent_hash = candidate_semantic_hash(parent_candidate)
    parent_id, parent_version = _identity(parent_candidate)
    result_parent_id = parent_id or str(expected_parent_id)
    stored_hash = parent_candidate.get("candidate_hash") or parent_candidate.get("hash")
    if (
        parent_id != str(expected_parent_id)
        or parent_version != str(expected_parent_version)
        or parent_hash != str(expected_parent_hash)
        or (stored_hash is not None and str(stored_hash) != parent_hash)
    ):
        return _rejection(strategy, result_parent_id, parent_hash, WINDOW_DAYLIGHT_STATUS_STALE_PARENT, ("parent_identity_version_or_hash_mismatch",))
    if (
        readiness.plan_id != strategy.plan_id
        or readiness.readiness_status not in {READINESS_STATUS_READY, READINESS_STATUS_READY_WITH_PREREQUISITES}
        or readiness.constraint_conflicts
    ):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_CONSTRAINT,
            ("selected_strategy_not_admitted_by_readiness",),
            constraint_checks=({"check": "readiness", "passed": False, "status": readiness.readiness_status},),
        )
    satisfied = parent_candidate.get("satisfied_prerequisites", ())
    satisfied_set = set(satisfied) if isinstance(satisfied, (list, tuple, set, frozenset)) else set()
    missing = tuple(sorted(set(strategy.prerequisites) - satisfied_set))
    if missing:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_CONSTRAINT,
            tuple(f"unresolved_prerequisite:{item}" for item in missing),
        )
    if strategy.strategy_type not in SUPPORTED_STRATEGY_TYPES:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_UNSUPPORTED_STRATEGY,
            (f"unsupported_strategy_type:{strategy.strategy_type}",),
            rejected_operations=(strategy.strategy_type,),
        )
    evidence = _execution_evidence(strategy, parent_candidate)
    if evidence is None:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_DAYLIGHT_EVIDENCE,
            ("insufficient_window_daylight_execution_evidence",),
        )
    operation = evidence.get("operation")
    if evidence.get("execution_family") != SUPPORTED_EXECUTION_FAMILY or operation not in SUPPORTED_OPERATIONS:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_UNSUPPORTED_STRATEGY,
            ("unsupported_execution_family_or_operation",),
            rejected_operations=(str(operation or "unknown"),),
        )

    target_id = evidence.get("target_space_id")
    window_id = evidence.get("window_interface_id") or evidence.get("window_id")
    boundary_ref = evidence.get("host_exterior_boundary_ref")
    if not all(isinstance(item, str) and item for item in (target_id, window_id, boundary_ref)):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
            ("target_window_or_host_boundary_evidence_missing",),
            rejected_operations=(str(operation),),
        )
    if target_id not in strategy.target_entities:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_CONSTRAINT,
            ("evidence_target_not_selected_strategy_target",),
            rejected_operations=(str(operation),),
        )
    records = [item for item in _space_records(parent_candidate) if item.get("space_id") == target_id]
    if len(records) != 1:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
            ("target_space_not_uniquely_resolved",),
            rejected_operations=(str(operation),),
        )
    target = records[0]
    floor = str(target.get("floor"))
    boundary = _line(evidence.get("boundary_segment"))
    if boundary is None:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
            ("explicit_straight_boundary_segment_missing",),
            rejected_operations=(str(operation),),
        )
    exterior_relation = _resolve_exterior_host(parent_candidate, target, boundary_ref, boundary)
    if exterior_relation is None:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
            ("host_not_proved_exterior_facade_boundary",),
            rejected_operations=(str(operation),),
            geometry_checks=({"check": "actual_exterior_envelope_host", "passed": False},),
        )

    daylight_goal = evidence.get("daylight_goal")
    if not isinstance(daylight_goal, Mapping) or not daylight_goal:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_DAYLIGHT_EVIDENCE,
            ("structured_daylight_goal_missing",),
            rejected_operations=(str(operation),),
        )
    orientation_required = evidence.get("orientation_required") is True or daylight_goal.get("requires_orientation") is True
    if orientation_required and not _valid_orientation_evidence(parent_candidate):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_DAYLIGHT_EVIDENCE,
            ("site_orientation_evidence_required_but_missing",),
            rejected_operations=(str(operation),),
            daylight_checks=({"check": "verified_site_orientation", "passed": False, "orientation_inferred": False},),
        )

    existing = _find_window(parent_candidate, window_id)
    before_window = deepcopy(existing[1]) if existing is not None else None
    if operation == "CREATE_WINDOW_OPPORTUNITY" and existing is not None:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
            ("window_interface_id_already_exists",), rejected_operations=(str(operation),),
        )
    if operation in {"ENLARGE_EXISTING_WINDOW", "REPOSITION_WINDOW_FOR_DAYLIGHT"} and existing is None:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
            ("existing_window_required_for_operation",), rejected_operations=(str(operation),),
        )
    if existing is not None and (
        existing[0] != floor
        or existing[1].get("host_wall_pair_id") != boundary_ref
        or target_id not in {existing[1].get("side_a"), existing[1].get("side_b")}
    ):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
            ("existing_window_not_bound_to_target_exterior_host",), rejected_operations=(str(operation),),
        )

    width, height = evidence.get("width_m"), evidence.get("height_m")
    dimensions_source = evidence.get("dimensions_source")
    if existing is not None:
        if width is None and operation == "REPOSITION_WINDOW_FOR_DAYLIGHT":
            width = existing[1].get("clear_width_m") or existing[1].get("resolved_width")
        if height is None:
            height = existing[1].get("height_m") or existing[1].get("resolved_height")
        if dimensions_source is None and width is not None and height is not None:
            dimensions_source = "existing_window_geometry"
    if (
        not isinstance(width, (int, float)) or isinstance(width, bool) or width <= 0
        or not isinstance(height, (int, float)) or isinstance(height, bool) or height <= 0
        or not isinstance(dimensions_source, str) or not dimensions_source
    ):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
            ("proved_positive_dimensions_and_source_required",), rejected_operations=(str(operation),),
        )
    width, height = float(width), float(height)

    position_source = evidence.get("position_source")
    position: dict[str, Any]
    center_distance: float
    distance = evidence.get("position_distance_m")
    fraction = evidence.get("position_fraction")
    if isinstance(distance, (int, float)) and not isinstance(distance, bool):
        center_distance = float(distance)
        position = {"mode": "DISTANCE_FROM_PROVED_BOUNDARY_START", "distance_m": center_distance}
    elif isinstance(fraction, (int, float)) and not isinstance(fraction, bool) and 0 <= float(fraction) <= 1:
        center_distance = boundary.length * float(fraction)
        position = {"mode": "FRACTION_OF_PROVED_BOUNDARY", "fraction": float(fraction), "distance_m": center_distance}
    elif operation == "ENLARGE_EXISTING_WINDOW" and existing is not None:
        existing_line = _opening_line(existing[1])
        if existing_line is None or existing_line.difference(boundary.buffer(_EPSILON)).length > _EPSILON:
            return _rejection(
                strategy, result_parent_id, parent_hash,
                WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
                ("existing_window_position_not_on_proved_host_segment",), rejected_operations=(str(operation),),
            )
        center_distance = boundary.project(existing_line.centroid)
        position = {"mode": "EXISTING_WINDOW_CENTER", "distance_m": center_distance}
        position_source = position_source or "existing_window.centerline"
    else:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
            ("explicit_or_existing_geometry_position_missing",), rejected_operations=(str(operation),),
        )
    if not isinstance(position_source, str) or not position_source:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
            ("position_source_missing",), rejected_operations=(str(operation),),
        )
    start_distance, end_distance = center_distance - width / 2.0, center_distance + width / 2.0
    if start_distance <= _EPSILON or end_distance >= boundary.length - _EPSILON:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
            ("window_corner_or_endpoint_collision",), rejected_operations=(str(operation),),
            geometry_checks=({"check": "corner_endpoint_clearance", "passed": False},),
        )
    opening_line = LineString((boundary.interpolate(start_distance), boundary.interpolate(end_distance)))
    if (
        opening_line.length <= _EPSILON
        or abs(opening_line.length - width) > _EPSILON
        or opening_line.difference(boundary.buffer(_EPSILON)).length > _EPSILON
    ):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
            ("window_not_fully_inside_exterior_host_or_width_mismatch",),
            rejected_operations=(str(operation),),
        )

    general_failures, candidate_privacy_failures = _constraint_failures(parent_candidate, target_id, boundary_ref, window_id)
    if general_failures:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_CONSTRAINT,
            general_failures, rejected_operations=(str(operation),),
            constraint_checks=({"check": "protected_space_wall_facade_window", "passed": False},),
        )
    privacy_constraints = _stable_tuple(evidence.get("privacy_constraints", ()))
    if candidate_privacy_failures or (privacy_constraints and evidence.get("privacy_compliance") is not True):
        failures = candidate_privacy_failures or tuple(f"unresolved_privacy_constraint:{item}" for item in privacy_constraints)
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_PRIVACY,
            failures, rejected_operations=(str(operation),),
            privacy_checks=({"check": "protected_privacy_and_exposure", "passed": False},),
        )

    opening_root = _nested_root(parent_candidate, "opening_host_graphs")
    if not isinstance(opening_root, Mapping) or _floor_graph(parent_candidate, "opening_host_graphs", floor) is None:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
            ("canonical_opening_host_graph_required",), rejected_operations=(str(operation),),
        )
    for other in _all_openings(parent_candidate, floor):
        if other.get("opening_id") == window_id:
            continue
        other_line = _opening_line(other)
        if other_line is not None and opening_line.distance(other_line) <= _EPSILON:
            return _rejection(
                strategy, result_parent_id, parent_hash,
                WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
                (f"opening_overlap:{other.get('opening_id')}",),
                rejected_operations=(str(operation),),
                geometry_checks=({"check": "no_existing_door_window_opening_overlap", "passed": False},),
            )

    derived = deepcopy(dict(parent_candidate))
    derived_graph = _floor_graph(derived, "opening_host_graphs", floor)
    if not isinstance(derived_graph, dict) or not isinstance(derived_graph.get("openings"), list):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_FAILED,
            ("rollback_canonical_opening_graph_clone_resolution_failed",), rejected_operations=(str(operation),),
        )
    coordinates = [[float(x), float(y)] for x, y in opening_line.coords]
    after_window = deepcopy(before_window) if before_window is not None else {}
    prior_evidence = after_window.get("geometric_evidence")
    geometric_evidence = deepcopy(dict(prior_evidence)) if isinstance(prior_evidence, Mapping) else {}
    geometric_evidence.update({
        "host_exterior_boundary_ref": boundary_ref,
        "boundary_segment": [[float(x), float(y)] for x, y in boundary.coords],
        "dimensions_source": dimensions_source,
        "position_source": position_source,
        "daylight_claim_scope": "EXTERIOR_WINDOW_OPPORTUNITY_ONLY" if not orientation_required else "ORIENTATION_EVIDENCE_PRESENT",
        "orientation_inferred": False,
        "facade_exterior_relation": deepcopy(dict(exterior_relation)),
    })
    after_window.update({
        "opening_id": window_id,
        "floor": floor,
        "kind": "WINDOW",
        "constituent_source_handles": [],
        "host_wall_pair_id": boundary_ref,
        "host_face_a": exterior_relation.get("interior_face_id"),
        "host_face_b": exterior_relation.get("exterior_face_id"),
        "threshold": None,
        "centerline": coordinates,
        "clear_width_m": width,
        "height_m": height,
        "opening_area_m2": width * height,
        "side_a": target_id,
        "side_b": f"EXTERIOR:{floor}",
        "traversable": False,
        "exposure": "EXTERIOR_UNORIENTED",
        "confidence": 1.0,
        "geometric_evidence": geometric_evidence,
        "status": "RESOLVED_WINDOW_OPPORTUNITY",
        "physical_object_scope": "ARCHITECTURAL_OPENING_INTERFACE_ONLY",
    })
    if operation == "CREATE_WINDOW_OPPORTUNITY":
        derived_graph["openings"].append(after_window)
    else:
        derived_existing = _find_window(derived, window_id)
        if derived_existing is None:
            return _rejection(
                strategy, result_parent_id, parent_hash,
                WINDOW_DAYLIGHT_STATUS_FAILED,
                ("rollback_existing_window_binding_lost_in_clone",), rejected_operations=(str(operation),),
            )
        derived_existing[1].clear()
        derived_existing[1].update(after_window)

    parent_other_openings = [item for item in _all_openings(parent_candidate, floor) if item.get("opening_id") != window_id]
    derived_other_openings = [item for item in _all_openings(derived, floor) if item.get("opening_id") != window_id]
    if _canonical(parent_other_openings) != _canonical(derived_other_openings):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_FAILED,
            ("rollback_unrelated_opening_mutation_detected",), rejected_operations=(str(operation),),
        )
    if _canonical(parent_candidate.get("access_graph")) != _canonical(derived.get("access_graph")):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_FAILED,
            ("rollback_access_or_circulation_mutation_detected",), rejected_operations=(str(operation),),
        )
    if _canonical(parent_candidate) != parent_document_before or candidate_semantic_hash(parent_candidate) != parent_hash:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            WINDOW_DAYLIGHT_STATUS_FAILED,
            ("parent_mutation_detected_transaction_rolled_back",), rejected_operations=(str(operation),),
        )

    delta = WindowDaylightDelta(
        window_interface_id=window_id,
        target_space_id=target_id,
        host_exterior_boundary_ref=boundary_ref,
        operation=str(operation),
        before_window=before_window,
        after_window=deepcopy(after_window),
        boundary_segment=tuple((float(x), float(y)) for x, y in boundary.coords),  # type: ignore[arg-type]
        width=width,
        height=height,
        area=width * height,
        source_of_dimensions=dimensions_source,
        position=position,
        source_of_position=position_source,
        daylight_goal=deepcopy(dict(daylight_goal)),
        privacy_constraints=privacy_constraints,
        facade_exterior_relation=deepcopy(dict(exterior_relation)),
        affected_openings=(window_id,),
        preserved_constraints=_stable_tuple(strategy.preserved_constraints),
        reason=str(evidence.get("reason") or "selected_strategy_evidence_based_window_daylight_realization"),
        strategy_id=strategy.strategy_id,
        provenance={
            "realizer": REALIZER_VERSION,
            "execution_family": SUPPORTED_EXECUTION_FAMILY,
            "geometry_source": "canonical_space_wall_face_wall_solid_envelope_graphs",
            "dimensions_source": dimensions_source,
            "position_source": position_source,
            "orientation_inferred": False,
        },
    )
    fingerprint = hashlib.sha256(_canonical(delta.__dict__).encode("utf-8")).hexdigest()
    derived_id = f"{parent_id}:derived:{fingerprint[:16]}"
    derived["parent_candidate_id"] = parent_id
    derived["candidate_id"] = derived_id
    derived["candidate_version"] = f"{parent_version}+01h.{fingerprint[:12]}"
    derived["derivation"] = {
        "strategy_id": strategy.strategy_id,
        "realizer": REALIZER_VERSION,
        "execution_family": SUPPORTED_EXECUTION_FAMILY,
        "operation": operation,
    }
    derived_hash = candidate_semantic_hash(derived)
    derived["candidate_hash"] = derived_hash
    warnings = () if orientation_required else ("solar_performance_not_claimed_without_site_orientation_simulation",)
    status = WINDOW_DAYLIGHT_STATUS_REALIZED_WITH_WARNINGS if warnings else WINDOW_DAYLIGHT_STATUS_REALIZED
    rechecks = set(strategy.required_rechecks) | set(readiness.required_checks_before_execution) | {
        "window_geometry", "privacy", "protected_constraints", "access", "circulation",
    }
    if not orientation_required:
        rechecks.update({"site_orientation", "daylight_simulation"})
    token = hashlib.sha256(f"{parent_hash}|{strategy.strategy_id}|{fingerprint}".encode("utf-8")).hexdigest()[:16]
    result = WindowDaylightRealizationResult(
        realization_id=f"window-daylight-realization:{token}",
        strategy_id=strategy.strategy_id,
        parent_candidate_id=str(parent_id),
        derived_candidate_id=derived_id,
        status=status,
        window_daylight_changes=(delta,),
        affected_entities=_stable_tuple((target_id, boundary_ref, window_id, str(exterior_relation.get("envelope_id")))),
        applied_operations=(str(operation),),
        rejected_operations=(),
        geometry_checks=(
            {"check": "actual_exterior_envelope_host", "passed": True},
            {"check": "window_inside_host_segment", "passed": True},
            {"check": "no_corner_endpoint_collision", "passed": True},
            {"check": "no_existing_door_window_opening_overlap", "passed": True},
            {"check": "positive_proved_dimensions", "passed": True},
        ),
        daylight_checks=(
            {"check": "exterior_window_opportunity_created", "passed": True},
            {"check": "solar_performance_claim", "passed": orientation_required, "deferred": not orientation_required},
            {"check": "orientation_inferred", "passed": True, "value": False},
        ),
        privacy_checks=({"check": "privacy_constraints_resolved", "passed": True},),
        constraint_checks=(
            {"check": "readiness_parent_identity_version_hash", "passed": True},
            {"check": "protected_wall_facade_space", "passed": True},
            {"check": "access_and_circulation_unchanged", "passed": True},
            {"check": "unrelated_openings_unchanged", "passed": True},
            {"check": "no_bim_ifc_window_object_created", "passed": True},
        ),
        required_downstream_rechecks=_stable_tuple(rechecks),
        warnings=warnings,
        failures=(),
        parent_hash=parent_hash,
        derived_hash=derived_hash,
        provenance={
            "phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01H",
            "realizer": REALIZER_VERSION,
            "commit": True,
            "parent_unchanged": True,
            "orientation_inferred": False,
            "physical_bim_or_ifc_object_created": False,
            "facade_redesign_performed": False,
        },
    )
    return derived, result


__all__ = [
    "REALIZER_VERSION", "SUPPORTED_EXECUTION_FAMILY", "SUPPORTED_OPERATIONS",
    "SUPPORTED_STRATEGY_TYPES", "realize_selected_window_daylight_strategy",
]
