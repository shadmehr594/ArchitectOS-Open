"""ARCHITECTURAL-CHANGE-ORCHESTRATOR-01B acceptance tests."""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import inspect
import json

import pytest

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeIntent,
    DesignRevisionRecord,
    dumps_contract,
    loads_contract,
)
from core.architecture.reasoning import architectural_change_impact_analyzer_v1 as module
from core.architecture.reasoning.architectural_change_impact_analyzer_v1 import (
    FEASIBILITY_PENDING_GEOMETRY,
    FEASIBILITY_PENDING_SITE,
    FEASIBILITY_UNKNOWN,
    analyze_architectural_change_impact,
)


@pytest.fixture
def semantic_plan_snapshot():
    return {
        "type": "architectural_intent_graph",
        "version": "architectural_intent_graph_v1",
        "nodes": [
            {"node_id": "space:kitchen", "kind": "building_space", "name": "kitchen", "canonical_name": "kitchen", "space_type": "OPEN_KITCHEN"},
            {"node_id": "space:living", "kind": "building_space", "name": "living", "canonical_name": "living", "space_type": "LIVING_RECEPTION"},
            {"node_id": "space:master_bedroom", "kind": "building_space", "name": "master_bedroom", "canonical_name": "master_bedroom", "space_type": "MASTER_BEDROOM_SLEEPING"},
            {"node_id": "space:bathroom", "kind": "building_space", "name": "bathroom", "canonical_name": "bathroom", "space_type": "FAMILY_BATHROOM"},
            {"node_id": "space:private_hall", "kind": "building_space", "name": "private_hall", "canonical_name": "private_hall", "space_type": "PRIVATE_HALL_CORRIDOR"},
            {"node_id": "space:balcony", "kind": "building_space", "name": "balcony", "canonical_name": "balcony", "space_type": "TERRACE_BALCONY"},
        ],
        "edges": [
            {"edge_id": "relation:kitchen-living", "type": "adjacency", "from": "space:kitchen", "to": "space:living"},
            {"edge_id": "relation:kitchen-access", "type": "circulation", "from": "space:kitchen", "to": "space:private_hall"},
            {"edge_id": "relation:master-bath", "type": "adjacency", "from": "space:master_bedroom", "to": "space:bathroom"},
            {"edge_id": "relation:master-private-hall", "type": "circulation", "from": "space:master_bedroom", "to": "space:private_hall"},
            {"edge_id": "relation:bath-private-hall", "type": "circulation", "from": "space:bathroom", "to": "space:private_hall"},
            {"edge_id": "relation:living-balcony", "type": "visual_connection", "from": "space:living", "to": "space:balcony"},
        ],
        "doors": [
            {"door_id": "door:kitchen-hall", "space_a": "space:kitchen", "space_b": "space:private_hall"},
            {"door_id": "door:master-hall", "space_a": "space:master_bedroom", "space_b": "space:private_hall"},
            {"door_id": "door:bath-hall", "space_a": "space:bathroom", "space_b": "space:private_hall"},
        ],
        "windows": [
            {"window_id": "window:kitchen", "room_id": "space:kitchen", "source_id": "daylight:court"},
            {"window_id": "window:living", "room_id": "space:living", "source_id": "daylight:south-frontage"},
        ],
        "daylight_sources": [
            {"source_id": "daylight:court", "source_type": "LIGHTWELL"},
            {"source_id": "daylight:south-frontage", "source_type": "EXTERIOR_EDGE"},
        ],
        "frontages": [{"frontage_id": "frontage:south", "kind": "public_street"}],
        "geometry_status": {"state": "pending", "reason": "read_only_snapshot"},
    }


def _intent(intent_id, change_type, targets, *, direction=None, preference=None, objective=(), text="ignored"):
    return ArchitecturalChangeIntent(
        change_intent_id=intent_id,
        change_type=change_type,
        targets=targets,
        direction=direction,
        preference=preference,
        soft_objectives=objective,
        user_text=text,
        provenance={"phase": "01A"},
    )


def _snapshot_hash(snapshot):
    payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_kitchen_resize_reports_neighbors_access_opening_and_daylight(semantic_plan_snapshot):
    intent = _intent(
        "intent-kitchen-grow", "resize_space", ("space:kitchen",),
        direction="increase", preference="larger_area", text="آشپزخانه رو بزرگ‌تر کن",
    )
    impact = analyze_architectural_change_impact(intent, semantic_plan_snapshot)

    assert {"space:kitchen", "space:living", "space:private_hall"} <= set(impact.affected_spaces)
    assert {"relation:kitchen-living", "relation:kitchen-access"} <= set(impact.affected_relations)
    assert impact.affected_openings == ("door:kitchen-hall",)
    assert {"window:kitchen", "daylight:court"} <= set(impact.affected_windows_or_daylight)
    assert impact.affected_circulation == ("space:private_hall",)
    assert {"usability", "circulation", "openings", "windows_daylight"} <= set(impact.required_rechecks)
    assert {"area_tradeoff", "access_opening_conflict"} <= set(impact.risk_flags)
    assert impact.feasibility_status == FEASIBILITY_PENDING_GEOMETRY


def test_master_bath_relation_reports_private_circulation_privacy_and_access(semantic_plan_snapshot):
    intent = _intent(
        "intent-master-near-bath", "change_relation",
        ("space:master_bedroom", "space:bathroom"),
        direction="closer", preference="proximity", text="مستر رو به حمام نزدیک‌تر کن",
    )
    impact = analyze_architectural_change_impact(intent, semantic_plan_snapshot)

    assert {"space:master_bedroom", "space:bathroom", "space:private_hall"} <= set(impact.affected_spaces)
    assert "relation:master-bath" in impact.affected_relations
    assert {"door:master-hall", "door:bath-hall"} <= set(impact.affected_openings)
    assert impact.affected_circulation == ("space:private_hall",)
    assert {"adjacency", "private_circulation", "privacy", "access"} <= set(impact.required_rechecks)
    assert {"topology_disruption", "private_circulation_disruption"} <= set(impact.risk_flags)
    assert impact.feasibility_status == FEASIBILITY_PENDING_GEOMETRY


def test_living_daylight_reports_window_frontage_balcony_and_site_dependency(semantic_plan_snapshot):
    intent = _intent(
        "intent-living-daylight", "improve_quality", ("space:living",),
        direction="increase", preference="daylight", objective=("living_daylight",),
        text="پذیرایی نور بیشتری بگیره",
    )
    impact = analyze_architectural_change_impact(intent, semantic_plan_snapshot)

    assert {"space:living", "space:balcony"} <= set(impact.affected_spaces)
    assert "relation:living-balcony" in impact.affected_relations
    assert {"window:living", "daylight:south-frontage", "frontage:south"} <= set(impact.affected_windows_or_daylight)
    assert {"windows_daylight", "frontage", "privacy", "site_orientation"} <= set(impact.required_rechecks)
    assert "site_orientation_dependency" in impact.risk_flags
    assert impact.feasibility_status == FEASIBILITY_PENDING_SITE
    assert "site_orientation_evidence_missing" in impact.feasibility_reasons


def test_analyzer_does_not_parse_user_text(semantic_plan_snapshot):
    structured = _intent(
        "same", "improve_quality", ("space:living",), preference="daylight",
        text="این متن عمداً هیچ اشاره‌ای به نور ندارد",
    )
    alternate_text = _intent(
        "same", "improve_quality", ("space:living",), preference="daylight",
        text="completely unrelated words",
    )
    assert analyze_architectural_change_impact(structured, semantic_plan_snapshot) == analyze_architectural_change_impact(alternate_text, semantic_plan_snapshot)


def test_snapshot_is_unchanged_by_deep_copy_and_hash(semantic_plan_snapshot):
    intent = _intent("immutable", "resize_space", ("space:kitchen",), direction="increase")
    before = deepcopy(semantic_plan_snapshot)
    before_hash = _snapshot_hash(semantic_plan_snapshot)

    analyze_architectural_change_impact(intent, semantic_plan_snapshot)

    assert semantic_plan_snapshot == before
    assert _snapshot_hash(semantic_plan_snapshot) == before_hash


def test_output_is_deterministic_and_contract_round_trips(semantic_plan_snapshot):
    intent = _intent("stable", "change_relation", ("space:master_bedroom", "space:bathroom"), direction="closer")
    first = analyze_architectural_change_impact(intent, semantic_plan_snapshot)
    second = analyze_architectural_change_impact(intent, deepcopy(semantic_plan_snapshot))

    assert first == second
    assert dumps_contract(first) == dumps_contract(second)
    assert loads_contract(dumps_contract(first)) == first


def test_missing_evidence_stays_unknown_and_does_not_invent_entities():
    intent = _intent("missing", "resize_space", ("space:not_in_snapshot",), direction="increase")
    impact = analyze_architectural_change_impact(intent, {"spaces": [], "relations": []})

    assert impact.feasibility_status == FEASIBILITY_UNKNOWN
    assert impact.confidence == "low"
    assert impact.affected_spaces == ("space:not_in_snapshot",)
    assert impact.affected_relations == ()
    assert impact.affected_openings == ()
    assert impact.affected_windows_or_daylight == ()
    assert "missing_target_evidence" in impact.risk_flags


def test_analyzer_is_generator_independent_and_has_no_mutation_or_geometry_api():
    source = inspect.getsource(module)
    lowered = source.lower()
    assert "house" + "diffusion" not in lowered
    assert "gs" + "diff" not in lowered
    assert all(term not in lowered for term in ("move_polygon", "create_variant", "generate_geometry"))

    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert imports <= {
        "__future__",
        "collections.abc",
        "typing",
        "core.architecture.contracts.architectural_change_contracts_v1",
        "core.architecture.contracts.functional_space_ontology_v1",
    }


def test_revision_lineage_still_round_trips_with_01b_impact(semantic_plan_snapshot):
    intent = _intent("lineage", "resize_space", ("space:kitchen",), direction="increase")
    impact = analyze_architectural_change_impact(intent, semantic_plan_snapshot)
    revision = DesignRevisionRecord(
        revision_id="revision-01b",
        parent_revision_id="revision-01a",
        child_revision_ids=(),
        user_request=intent.user_text,
        interpreted_intent=intent,
        affected_entities=impact.affected_spaces,
        quality_result={"impact": json.loads(dumps_contract(impact)), "geometry_changed": False},
    )
    assert loads_contract(dumps_contract(revision)) == revision
