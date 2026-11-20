"""Read-only prospective impact analysis for architectural change intents.

The analyzer consumes an already interpreted ``ArchitecturalChangeIntent`` and
a mapping snapshot of the current semantic plan.  It only reports the entities
and checks that a later phase may need to revisit.  It does not parse dialogue,
calculate or mutate geometry, create variants, or invoke a producer.

Supported snapshot vocabulary follows the project's active semantic contracts:
``nodes``/``edges`` from ``architectural_intent_graph_v1`` and the equivalent
``spaces``/``rooms``, ``relations``/``connections``, ``doors``/``openings``,
``windows``, ``daylight_sources``/``sources``, and private-circulation fields
used by the room-planning contracts.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeIntent,
    DesignChangeImpact,
)
from core.architecture.contracts.functional_space_ontology_v1 import (
    resolve_space_type,
)


FEASIBILITY_UNKNOWN = "UNKNOWN"
FEASIBILITY_PENDING_GEOMETRY = "FEASIBLE_PENDING_GEOMETRY"
FEASIBILITY_PENDING_SITE = "FEASIBLE_PENDING_SITE"


def _records(value: Any) -> tuple[Mapping[str, Any], ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        values: Iterable[Any] = value.values()
    elif isinstance(value, (list, tuple)):
        values = value
    else:
        return ()
    return tuple(item for item in values if isinstance(item, Mapping))


def _first_text(record: Mapping[str, Any], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = record.get(name)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _entity_id(record: Mapping[str, Any], *, kind: str) -> str | None:
    names = {
        "space": ("node_id", "space_id", "room_id", "id", "name"),
        "relation": ("edge_id", "relation_id", "connection_id", "id"),
        "opening": ("opening_id", "door_id", "id"),
        "window": ("window_id", "source_id", "id"),
        "circulation": ("space_id", "room_id", "node_id", "id", "name"),
    }[kind]
    return _first_text(record, names)


def _aliases(record: Mapping[str, Any]) -> frozenset[str]:
    identity = record.get("identity")
    semantic = record.get("semantic")
    values = [
        _first_text(record, ("node_id", "space_id", "room_id", "id", "name")),
        _first_text(record, ("canonical_name", "space_type", "use")),
    ]
    if isinstance(identity, Mapping):
        values.extend((identity.get("name"), identity.get("canonical_name")))
    if isinstance(semantic, Mapping):
        values.append(semantic.get("space_type"))
    aliases: set[str] = set()
    for value in values:
        if isinstance(value, str) and value.strip():
            normalized = value.strip().lower()
            aliases.add(normalized)
            if ":" in normalized:
                aliases.add(normalized.split(":", 1)[1])
    return frozenset(aliases)


def _semantic_class(record: Mapping[str, Any]) -> str | None:
    semantic = record.get("semantic")
    if isinstance(semantic, Mapping):
        value = semantic.get("space_type")
        if isinstance(value, str) and value:
            return value.upper()
    value = _first_text(record, ("semantic_class", "space_type", "use"))
    return value.upper() if value else None


def _endpoint_pair(record: Mapping[str, Any]) -> tuple[str | None, str | None]:
    source = _first_text(record, ("from", "source", "space_a", "room_a"))
    target = _first_text(record, ("to", "target", "space_b", "room_b"))
    return source, target


def _touches(record: Mapping[str, Any], entity_aliases: set[str]) -> bool:
    source, target = _endpoint_pair(record)
    room = _first_text(record, ("room_id", "space_id", "served_space_id"))
    values = (source, target, room)
    return any(
        isinstance(value, str) and value.lower() in entity_aliases
        for value in values
    )


def _sorted(values: Iterable[str | None]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if isinstance(value, str) and value}))


def _snapshot_collections(snapshot: Mapping[str, Any]) -> dict[str, tuple[Mapping[str, Any], ...]]:
    nodes = tuple(
        node
        for node in _records(snapshot.get("nodes"))
        if node.get("kind") in (None, "building_space", "site_space")
    )
    spaces = nodes + _records(snapshot.get("spaces")) + _records(snapshot.get("rooms"))
    relations = (
        _records(snapshot.get("edges"))
        + _records(snapshot.get("relations"))
        + _records(snapshot.get("connections"))
    )
    return {
        "spaces": spaces,
        "relations": relations,
        "openings": _records(snapshot.get("openings")) + _records(snapshot.get("doors")),
        "windows": _records(snapshot.get("windows")),
        "sources": _records(snapshot.get("daylight_sources")) + _records(snapshot.get("sources")),
        "circulation": (
            _records(snapshot.get("circulation"))
            + _records(snapshot.get("private_circulation"))
        ),
        "frontage": _records(snapshot.get("frontage")) + _records(snapshot.get("frontages")),
    }


def _classify_intent(intent: ArchitecturalChangeIntent) -> str:
    tokens = {
        intent.change_type.lower(),
        (intent.direction or "").lower(),
        (intent.preference or "").lower(),
        *(item.lower() for item in intent.soft_objectives),
    }
    if any("daylight" in token or "window" in token for token in tokens):
        return "daylight"
    if intent.change_type.lower() == "change_relation" or any(
        token in {"closer", "proximity", "adjacency"} for token in tokens
    ):
        return "relation"
    if intent.change_type.lower() == "resize_space" or any(
        token in {"increase", "decrease", "larger_area", "smaller_area"}
        for token in tokens
    ):
        return "resize"
    return "generic"


def analyze_architectural_change_impact(
    intent: ArchitecturalChangeIntent,
    snapshot: Mapping[str, Any],
) -> DesignChangeImpact:
    """Return deterministic prospective impact without modifying ``snapshot``."""
    if not isinstance(intent, ArchitecturalChangeIntent):
        raise ValueError("intent must be ArchitecturalChangeIntent")
    if not isinstance(snapshot, Mapping):
        raise ValueError("snapshot must be a mapping")

    collections = _snapshot_collections(snapshot)
    intent_targets = {target.lower() for target in intent.targets}
    target_aliases = intent_targets | {
        target.split(":", 1)[1] for target in intent_targets if ":" in target
    }
    matched_spaces = [
        space for space in collections["spaces"] if _aliases(space) & target_aliases
    ]
    matched_ids = {
        _entity_id(space, kind="space") for space in matched_spaces
    }
    matched_ids.discard(None)
    affected_spaces: set[str] = set(matched_ids or intent.targets)

    alias_to_id: dict[str, str] = {}
    record_by_id: dict[str, Mapping[str, Any]] = {}
    for space in collections["spaces"]:
        space_id = _entity_id(space, kind="space")
        if not space_id:
            continue
        record_by_id[space_id] = space
        for alias in _aliases(space):
            alias_to_id.setdefault(alias, space_id)

    affected_aliases = set(target_aliases)
    for space in matched_spaces:
        affected_aliases.update(_aliases(space))

    intent_kind = _classify_intent(intent)
    affected_relations: set[str] = set()
    relation_records: list[Mapping[str, Any]] = []
    for relation in collections["relations"]:
        if not _touches(relation, affected_aliases):
            continue
        relation_records.append(relation)
        relation_id = _entity_id(relation, kind="relation")
        if relation_id:
            affected_relations.add(relation_id)
        source, target = _endpoint_pair(relation)
        for endpoint in (source, target):
            if endpoint and endpoint.lower() not in affected_aliases:
                resolved = alias_to_id.get(endpoint.lower())
                if resolved and intent_kind in {"resize", "relation", "daylight"}:
                    affected_spaces.add(resolved)

    for space_id in tuple(affected_spaces):
        record = record_by_id.get(space_id)
        if record:
            affected_aliases.update(_aliases(record))

    affected_openings = {
        _entity_id(record, kind="opening")
        for record in collections["openings"]
        if _touches(record, target_aliases)
    }
    affected_openings.discard(None)

    affected_windows = {
        _entity_id(record, kind="window")
        for record in collections["windows"]
        if _touches(record, target_aliases)
    }
    affected_windows.discard(None)
    affected_source_ids = {
        record.get("source_id")
        for record in collections["windows"]
        if _touches(record, target_aliases)
    }
    known_source_ids = {
        _entity_id(record, kind="window") for record in collections["sources"]
    }
    affected_windows.update(
        source_id
        for source_id in affected_source_ids
        if isinstance(source_id, str) and source_id in known_source_ids
    )

    private_semantics = {"PRIVATE_HALL_CORRIDOR", "PRIVATE_CIRCULATION"}
    circulation_ids: set[str | None] = {
        _entity_id(record, kind="circulation")
        for record in collections["circulation"]
        if _touches(record, affected_aliases) or not _endpoint_pair(record)[0]
    }
    for space in collections["spaces"]:
        if _semantic_class(space) not in private_semantics:
            continue
        aliases = set(_aliases(space))
        if any(_touches(relation, aliases) for relation in relation_records):
            circulation_ids.add(_entity_id(space, kind="space"))
    circulation_ids.discard(None)

    evidence: set[str] = {f"intent:{intent.change_intent_id}"}
    evidence.update(f"space:{item}" for item in matched_ids)
    evidence.update(f"relation:{item}" for item in affected_relations)
    evidence.update(f"opening:{item}" for item in affected_openings)
    evidence.update(f"daylight:{item}" for item in affected_windows)
    for space in matched_spaces:
        semantic_class = _semantic_class(space)
        if not semantic_class:
            continue
        try:
            resolve_space_type(semantic_class)
        except KeyError:
            continue
        evidence.add(f"ontology:{semantic_class}")

    if intent_kind == "resize":
        rechecks = {"usability", "circulation", "openings", "windows_daylight"}
        conflicts = {"area_tradeoff", "access_opening_conflict"}
        risks = {"area_tradeoff", "access_opening_conflict"}
    elif intent_kind == "relation":
        rechecks = {"adjacency", "private_circulation", "privacy", "access"}
        conflicts = {"topology_disruption", "access_privacy_conflict"}
        risks = {"topology_disruption", "private_circulation_disruption"}
    elif intent_kind == "daylight":
        rechecks = {"windows_daylight", "frontage", "privacy", "site_orientation"}
        conflicts = {"facade_opening_privacy_conflict"}
        risks = {"site_orientation_dependency", "facade_privacy_dependency"}
        for record in collections["frontage"]:
            frontage_id = _first_text(record, ("frontage_id", "edge_id", "id", "name"))
            if frontage_id:
                affected_windows.add(frontage_id)
                evidence.add(f"frontage:{frontage_id}")
    else:
        rechecks = {"program", "topology", "quality_gate"}
        conflicts = {"impact_scope_unresolved"}
        risks = {"unsupported_intent_kind"}

    if not matched_spaces:
        feasibility = FEASIBILITY_UNKNOWN
        reasons = {"target_entities_not_found_in_snapshot"}
        risks.add("missing_target_evidence")
        confidence = "low"
    elif intent_kind == "daylight" and not (
        snapshot.get("orientation") or snapshot.get("site_orientation")
    ):
        feasibility = FEASIBILITY_PENDING_SITE
        reasons = {"site_orientation_evidence_missing", "geometry_validation_required"}
        confidence = "low" if not affected_windows else "medium"
    else:
        feasibility = FEASIBILITY_PENDING_GEOMETRY
        reasons = {"geometry_validation_required"}
        confidence = "medium"

    return DesignChangeImpact(
        change_intent_id=intent.change_intent_id,
        affected_spaces=_sorted(affected_spaces),
        affected_relations=_sorted(affected_relations),
        affected_openings=_sorted(affected_openings),
        affected_windows_or_daylight=_sorted(affected_windows),
        affected_circulation=_sorted(circulation_ids),
        possible_conflicts=_sorted(conflicts),
        required_rechecks=_sorted(rechecks),
        risk_flags=_sorted(risks),
        feasibility_status=feasibility,
        feasibility_reasons=_sorted(reasons),
        evidence=_sorted(evidence),
        confidence=confidence,
    )


__all__ = [
    "FEASIBILITY_UNKNOWN",
    "FEASIBILITY_PENDING_GEOMETRY",
    "FEASIBILITY_PENDING_SITE",
    "analyze_architectural_change_impact",
]
