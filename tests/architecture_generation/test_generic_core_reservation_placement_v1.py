import json
from pathlib import Path

from shapely.geometry import Polygon

from core.architecture.reasoning.generic_core_reservation_placement_v1 import GenericCoreReservationPlacementV1


ROOT = Path(__file__).resolve().parents[2]


def assumption():
    return json.loads((ROOT / "core/architecture/contracts/parcel2_temporary_core_reservation_design_assumption_v1.json").read_text(encoding="utf-8"))


def test_temporary_area_proxy_produces_multiple_unselected_candidates_inside_realistic_domain():
    polygon = [[0, 0], [10, 0], [10, 20], [0, 20]]
    result = GenericCoreReservationPlacementV1().produce(
        {"polygon": polygon, "evidence_status": "resolved"}, assumption())
    assert result["status"] == "candidates_produced"
    assert result["candidate_count"] > 1
    domain = Polygon(polygon)
    for candidate in result["candidates"]:
        assert candidate["selection"] is False
        assert candidate["shape_proxy"] is True
        assert candidate["final_geometry"] is False
        assert abs(Polygon(candidate["polygon"]).area - 20.0) < 1e-6
        assert domain.buffer(1e-7).covers(Polygon(candidate["polygon"]))


def test_wrong_authority_class_fails_closed():
    contract = assumption()
    contract["authority_class"] = "PROJECT_REQUIREMENT"
    result = GenericCoreReservationPlacementV1().produce(
        {"polygon": [[0, 0], [10, 0], [10, 20], [0, 20]], "evidence_status": "resolved"}, contract)
    assert result["status"] == "pending_evidence"
    assert "design_assumption_authority_class" in result["unresolved_dependencies"]


def test_source_has_no_cardinal_or_fixed_offset_placement_logic():
    source = (ROOT / "core/architecture/reasoning/generic_core_reservation_placement_v1.py").read_text(encoding="utf-8").lower()
    for token in ("north", "south", "east", "west", "fixed_offset", "bbox_corner"):
        assert token not in source
