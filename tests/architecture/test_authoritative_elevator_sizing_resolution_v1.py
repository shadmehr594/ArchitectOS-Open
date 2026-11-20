from copy import deepcopy
import json
from pathlib import Path

import pytest

from core.architecture.reasoning.authoritative_elevator_sizing_resolution_v1 import (
    AuthoritativeElevatorSizingResolutionV1,
)


ROOT = Path(__file__).resolve().parents[2]


def contracts():
    project = json.loads((ROOT / "core/architecture/contracts/parcel2_human_program_evidence_v1.json").read_text(encoding="utf-8"))
    regulation = json.loads((ROOT / "core/architecture/contracts/iran_topic15_elevator_accessibility_evidence_v1.json").read_text(encoding="utf-8"))
    return project, regulation


def resolve():
    project, regulation = contracts()
    return AuthoritativeElevatorSizingResolutionV1().resolve(
        project_evidence=project, regulation_evidence=regulation, elevator_required=True)


def test_count_confirmation_is_machine_readable_and_provenance_preserving():
    result = resolve()
    assert result["count"]["value"] == 1
    assert result["count"]["authority_class"] == "DESIGN_CONFIRMATION"
    assert result["count"]["source_kind"] == "human_confirmed_design_selection"
    assert result["count"]["source_reference"] and result["count"]["provenance"]


def test_accessibility_minima_preserve_official_provenance():
    access = resolve()["accessibility"]
    assert access["minimum_accessible_count"] == 1
    assert access["cabin_minimum_mm"] == {"width": 1400, "depth": 1100}
    assert access["clear_door_minimum_mm"] == 800
    assert {x["clause"] for x in access["provenance"]} == {"15-2-1-5", "15-2-1-9"}


def test_capacity_shaft_equipment_and_machine_room_fail_closed():
    result = resolve()
    assert result["capacity_options"] == {"status": "UNRESOLVED", "candidates": [], "dependencies": ["traffic_calculation"], "provenance": [{"clause": "15-2-1-12"}]}
    assert result["shaft_options"]["status"] == "UNRESOLVED" and result["shaft_options"]["candidates"] == []
    assert result["equipment_selection"]["status"] == "UNRESOLVED"
    assert all(result["equipment_selection"][x] is None for x in ("type", "model", "speed", "door_arrangement"))
    assert result["machine_room_status"] == {"mr_mrl": None, "status": "UNRESOLVED"}
    assert result["appendix_2"]["status"] == "DEPENDENCIES_UNRESOLVED"


def test_no_legacy_shaft_leakage_and_downstream_geometry_stops():
    result = resolve()
    serialized = json.dumps(result, sort_keys=True)
    assert "1.8" not in serialized and "1800" not in serialized
    assert result["legacy_1_8x1_8_used"] is False
    assert result["lobby_sizing_gate"].startswith("STOP_")
    assert result["core_reservation_gate"].startswith("STOP_")
    assert result["geometry_generated"] is False


def test_deterministic_and_does_not_mutate_sources():
    project, regulation = contracts()
    before = deepcopy((project, regulation))
    resolver = AuthoritativeElevatorSizingResolutionV1()
    first = resolver.resolve(project_evidence=project, regulation_evidence=regulation, elevator_required=True)
    second = resolver.resolve(project_evidence=project, regulation_evidence=regulation, elevator_required=True)
    assert first == second and (project, regulation) == before
    assert first["input_mutated"] is False


def test_invalid_confirmation_or_incomplete_official_authority_is_rejected():
    project, regulation = contracts()
    next(r for r in project["evidence_records"] if r.get("id") == "elevator_count_selection")["source_kind"] = "historical_candidate"
    with pytest.raises(ValueError, match="authority"):
        AuthoritativeElevatorSizingResolutionV1().resolve(project_evidence=project, regulation_evidence=regulation, elevator_required=True)
    project, regulation = contracts()
    regulation["evidence_records"][0]["authority_class"] = "BLOG"
    with pytest.raises(ValueError, match="authoritative"):
        AuthoritativeElevatorSizingResolutionV1().resolve(project_evidence=project, regulation_evidence=regulation, elevator_required=True)
