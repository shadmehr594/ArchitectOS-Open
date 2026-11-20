from copy import deepcopy
import json

from core.architecture.reasoning.site_access_evidence_derivation_v1 import (
    SiteAccessEvidenceDerivationV1,
)


def _site():
    return {
        "parcel_boundary": [[0, 0], [20, 0], [20, 30], [0, 30]],
        "access_edge_index": 0,
        "conflict_inventory_scope": ["protected_zones", "vehicle_access_zones"],
        "protected_zones": [], "vehicle_access_zones": [],
    }


def _program():
    return {
        "commercial_required": True, "public_access_required": True,
        "commercial_frontage_priority": True, "public_private_separation": True,
    }


def test_polygon_publishes_stable_edges_and_binds_road_without_mutation():
    source = _site()
    before = json.dumps(source, sort_keys=True)
    first = SiteAccessEvidenceDerivationV1().derive(source, _program())
    second = SiteAccessEvidenceDerivationV1().derive(source, _program())
    assert json.dumps(source, sort_keys=True) == before
    assert first["parcel_edges"] == second["parcel_edges"]
    assert first["road_frontages"][0]["edge_id"] == first["parcel_edges"][0]["edge_id"]
    assert first["parcel_edges"][0]["start"] == [0.0, 0.0]
    assert first["parcel_edges"][0]["end"] == [20.0, 0.0]
    assert first["parcel_edges"][0]["adjacency"]["next_edge_id"] == first["parcel_edges"][1]["edge_id"]


def test_frontage_requirements_create_regions_not_forced_points_or_merged_entrances():
    result = SiteAccessEvidenceDerivationV1().derive(_site(), _program())
    public = result["public_access_candidate_regions"][0]
    commercial = result["commercial_entrance_candidate_regions"][0]
    assert public["parameter_interval"] == [0.0, 1.0]
    assert public["selected_point"] is None and commercial["selected_point"] is None
    assert result["dedicated_pedestrian_entrance"]["mandatory"] is False
    assert result["dedicated_pedestrian_entrance"]["merged_with_public_access_point"] is False
    assert result["coordination_selection_authority"]["status"] == "resolved_unique_region"


def test_complete_empty_inventory_is_authoritative_but_incomplete_is_not():
    complete = SiteAccessEvidenceDerivationV1().derive(_site(), {})
    assert complete["conflict_inventory"]["authoritative_empty"] is True
    incomplete_site = deepcopy(_site())
    del incomplete_site["vehicle_access_zones"]
    incomplete = SiteAccessEvidenceDerivationV1().derive(incomplete_site, {})
    assert incomplete["conflict_inventory"]["status"] == "partial_unresolved"
    assert incomplete["conflict_inventory"]["authoritative_empty"] is False


def test_h1_h2_targets_are_branch_scoped_and_pending_when_geometry_would_be_circular():
    pending = SiteAccessEvidenceDerivationV1().derive(_site(), {}, hypotheses={"enabled": ["H1", "H2"]})
    assert {item["hypothesis_id"] for item in pending["hypothesis_scoped_target_regions"]} == {"H1", "H2"}
    assert all(item["status"] == "target_region_pending_geometry" for item in pending["hypothesis_scoped_target_regions"])
    assert all(item["project_authority"] is False and item["circular_dependency"] is True for item in pending["hypothesis_scoped_target_regions"])
    site = _site()
    site["parking_domains"] = {"pilotis": [[2, 5], [18, 5], [18, 20], [2, 20]]}
    derived = SiteAccessEvidenceDerivationV1().derive(site, {}, hypotheses={"enabled": ["H1"]})
    assert derived["hypothesis_scoped_target_regions"][0]["status"] == "derived_target_region"


def test_multiple_confirmed_frontages_require_selection_authority_without_cardinal_or_offset_leakage():
    site = _site()
    site["confirmed_road_access_edge_indices"] = [0, 2]
    del site["access_edge_index"]
    result = SiteAccessEvidenceDerivationV1().derive(site, _program())
    assert result["coordination_selection_authority"]["status"] == "DESIGN_CONFIRMATION_REQUIRED"
    serialized = json.dumps(result).lower()
    assert "north" not in serialized and "south" not in serialized
    assert "historical" not in serialized and "fixed_offset" not in serialized


def test_invalid_polygon_fails_closed_and_regulation_does_not_invent_three_metre_rule():
    invalid = _site()
    invalid["parcel_boundary"] = [[0, 0], [10, 10], [0, 10], [10, 0]]
    result = SiteAccessEvidenceDerivationV1().derive(invalid, _program())
    assert result["derivation_status"] == "unresolved" and not result["parcel_edges"]
    regulation = {"evidence_records": [{
        "clause": "4-5-10-1-6", "minimum_pedestrian_walkway_width_m": 0.60,
        "numeric_frontage_gate_separation_m": None,
        "applicability_status": "applicability_requires_parking_size_classification",
        "provenance": "primary regulation text",
    }]}
    policy = SiteAccessEvidenceDerivationV1().derive(_site(), {}, regulation)["regulatory_separation_policy"]
    assert policy["minimum_frontage_gate_separation"] is None
    assert policy["numeric_value_not_invented"] is True
    assert policy["evidence_records"][0]["provenance"] == "primary regulation text"
