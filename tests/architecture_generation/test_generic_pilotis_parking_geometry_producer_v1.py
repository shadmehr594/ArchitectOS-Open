from copy import deepcopy
from pathlib import Path
import re

from shapely.affinity import rotate, translate
from shapely.geometry import Polygon

from core.architecture.reasoning.generic_pilotis_parking_geometry_producer_v1 import GenericPilotisParkingGeometryProducerV1
from core.architecture.reasoning.pilotis_parking_architectural_acceptance_v1 import PilotisParkingArchitecturalAcceptanceV1


def evidence(domain, regions=None, complete=True, access=None):
    provenance = [{"source": "synthetic_authoritative_fixture"}]
    return dict(
        domain_evidence={"polygon": list(domain.exterior.coords)[:-1], "floor_scope": "pilotis",
                         "evidence_status": "authoritative", "provenance": provenance},
        parking_requirement={"minimum_required_capacity": 3, "stall_width": 2.5,
                             "stall_depth": 5.0, "aisle_width": 5.0,
                             "provenance": provenance},
        protected_region_evidence={"inventory_complete": complete, "regions": regions or [],
                                   "provenance": provenance},
        vehicle_access_candidate_region=access,
        branch_evidence={"hypothesis_id": "H1", "provenance": provenance})


def produce(domain=Polygon([(0, 0), (20, 0), (20, 16), (0, 16)]), **changes):
    values = evidence(domain)
    values.update(changes)
    return GenericPilotisParkingGeometryProducerV1().produce(**values)


def test_arbitrary_convex_domain_produces_schema_without_directional_labels():
    result = produce(Polygon([(0, 0), (19, 1), (21, 15), (2, 17), (-1, 8)]))
    assert result["status"] == "candidates_produced" and result["candidate_count"] > 0
    assert all(len(c["stall_geometries"]) >= 3 for c in result["candidates"])
    assert PilotisParkingArchitecturalAcceptanceV1().evaluate(
        result, result["candidates"][0]["candidate_id"], 3)["contract"] == "PilotisParkingArchitecturalAcceptanceV1"


def test_skewed_domain_is_deterministic_and_transform_equivariant():
    domain = Polygon([(0, 0), (20, 3), (17, 18), (-3, 15)])
    first = produce(domain)
    second = produce(domain)
    moved = translate(rotate(domain, 31, origin=(0, 0)), 37, -11)
    transformed = produce(moved)
    assert first == second
    assert [len(x["stall_geometries"]) for x in first["candidates"]] == [
        len(x["stall_geometries"]) for x in transformed["candidates"]]


def test_impossible_domain_fails_closed_without_fake_stalls():
    result = produce(Polygon([(0, 0), (4, 0), (4, 4), (0, 4)]))
    assert result["status"] == "no_feasible_candidates"
    assert result["candidates"] == []


def test_protected_core_and_public_regions_are_preserved():
    regions = [
        {"region_id": "R1", "kind": "core", "polygon": [[0, 0], [6, 0], [6, 6], [0, 6]]},
        {"region_id": "R2", "kind": "commercial", "polygon": [[14, 10], [20, 10], [20, 16], [14, 16]]},
        {"region_id": "R3", "kind": "public_access", "polygon": [[8, 0], [11, 0], [11, 16], [8, 16]]},
    ]
    values = evidence(Polygon([(0, 0), (30, 0), (30, 20), (0, 20)]), regions=regions)
    result = GenericPilotisParkingGeometryProducerV1().produce(**values)
    blocked = [Polygon(r["polygon"]) for r in regions]
    for candidate in result["candidates"]:
        for stall in candidate["stall_geometries"]:
            assert all(Polygon(stall["polygon"]).intersection(zone).area < 1e-7 for zone in blocked)


def test_missing_required_inventory_is_unresolved_and_nothing_is_fabricated():
    values = evidence(Polygon([(0, 0), (20, 0), (20, 16), (0, 16)]), complete=False)
    before = deepcopy(values)
    result = GenericPilotisParkingGeometryProducerV1().produce(**values)
    assert result["status"] == "pending_evidence" and result["candidates"] == []
    assert "authoritative_protected_unavailable_region_inventory" in result["unresolved_dependencies"]
    assert values == before


def test_access_is_never_selected_and_selection_promotion_publication_are_absent():
    access = {"contract": "VehicleAccessCandidateRegionV1", "eligible_frontage": [[0, 0], [20, 0]]}
    result = produce(vehicle_access_candidate_region=access)
    assert result["selection_status"] == result["promotion_status"] == result["publication_status"] == "not_performed"
    for candidate in result["candidates"]:
        assert candidate["vehicle_access_evidence"]["status"] == "pending"
        assert candidate["vehicle_access_evidence"]["endpoint"] is None
        assert "stair" not in str(candidate).lower() and "elevator" not in str(candidate).lower()


def test_source_has_no_legacy_family_or_geographic_direction_leakage():
    text = Path(GenericPilotisParkingGeometryProducerV1.__module__.replace(".", "/") + ".py")
    source = text.read_text(encoding="utf-8").lower()
    forbidden = ["hybrid", "historical", "parcel2", "fixed_offset", "bbox_corner",
                 "north", "south", "east", "west"]
    assert not [token for token in forbidden if re.search(rf"\b{re.escape(token)}\b", source)]
