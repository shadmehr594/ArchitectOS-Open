from core.architecture.geometry.pedestrian_access_geometry_resolver_v1 import (
    PedestrianAccessGeometryResolverV1,
)


PARCEL = [[0, 0], [10, 0], [10, 12], [0, 12]]
BUILDING = [{"floor": "F1", "footprint": {"points": [[2, 4], [8, 4], [8, 10], [2, 10]]}}]


def _candidate(access_id="PA-1", x=5):
    return {
        "access_id": access_id,
        "parcel_edge_reference": 0,
        "access_point": [x, 0],
        "approach_start": [x, 0],
        "approach_end": [x, 4],
        "approach_line": [[x, 0], [x, 4]],
        "geometry_status": "resolved",
        "source_evidence": ["surveyed pedestrian route PA-1"],
    }


def test_complete_unique_site_access_resolves_authoritative_approach_line():
    site = {"parcel_boundary": PARCEL, "pedestrian_access_candidates": [_candidate()]}
    result = PedestrianAccessGeometryResolverV1().resolve(site, BUILDING)
    assert result["geometry_status"] == "resolved"
    assert result["access_id"] == "PA-1"
    assert result["parcel_edge_reference"] == 0
    assert result["access_point"] == [5.0, 0.0]
    assert result["approach_line"] == [[5.0, 0.0], [5.0, 4.0]]


def test_explicit_access_line_derives_unique_edge_identity_from_exact_geometry():
    candidate = _candidate()
    candidate.pop("parcel_edge_reference")
    candidate.pop("access_point")
    result = PedestrianAccessGeometryResolverV1().resolve(
        {"parcel_boundary": PARCEL, "pedestrian_access_candidates": [candidate]}, BUILDING
    )
    assert result["geometry_status"] == "resolved"
    assert result["parcel_edge_reference"] == 0
    assert result["access_point"] == [5.0, 0.0]


def test_incomplete_or_multiple_valid_accesses_remain_pending():
    incomplete = _candidate()
    incomplete["approach_start"] = [5, 1]
    incomplete["approach_line"] = [[5, 1], [5, 4]]
    unresolved = PedestrianAccessGeometryResolverV1().resolve(
        {"parcel_boundary": PARCEL, "pedestrian_access_candidates": [incomplete]}, BUILDING
    )
    assert unresolved["geometry_status"] == "pending"
    assert unresolved["approach_line"] is None

    ambiguous = PedestrianAccessGeometryResolverV1().resolve({
        "parcel_boundary": PARCEL,
        "pedestrian_access_candidates": [_candidate("PA-1", 4), _candidate("PA-2", 6)],
    }, BUILDING)
    assert ambiguous["geometry_status"] == "pending"
    assert ambiguous["resolution_reason"] == "multiple_valid_pedestrian_access_candidates"
    assert ambiguous["valid_candidate_ids"] == ["PA-1", "PA-2"]
