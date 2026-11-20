from copy import deepcopy
from pathlib import Path

from shapely.geometry import Polygon, box

from core.architecture.reasoning.architectural_generalization_study_v1 import (
    IndependentGeneralizationStudyV1, RequirementSeededTopologyGeneratorV1)
from core.architecture.reasoning.reservation_aware_placement_v1 import ReservationAwarePlacementV1
from core.architecture.reasoning.spatial_reservation_exclusivity_v1 import ReservationZone, SpatialReservationExclusivityV1


def context():
    return IndependentGeneralizationStudyV1().context()


def test_generated_core_is_never_admitted_inside_reserved_vehicle_zone():
    for candidate in RequirementSeededTopologyGeneratorV1().generate(context()):
        core=Polygon(candidate["core"]); vehicle=Polygon(candidate["vehicle_reserved_zone"])
        assert core.intersection(vehicle).area < 1e-7
        assert candidate["core_topology"]["status"] == "placed_in_feasible_region"


def test_court_is_not_generated_inside_core_vertical_reservation():
    for candidate in RequirementSeededTopologyGeneratorV1().generate(context()):
        assert Polygon(candidate["daylight_court"]).intersection(Polygon(candidate["core"])).area < 1e-7
        assert candidate["daylight_court_placement"]["status"] == "placed_from_daylight_demand"


def test_daylight_demand_change_relocates_court():
    generator=RequirementSeededTopologyGeneratorV1(); base=context()
    north=generator.generate(base,{"element_type":"daylight_court","daylight_demand_targets":["north"]})
    south=generator.generate(base,{"element_type":"daylight_court","daylight_demand_targets":["south"]})
    assert [c["daylight_court"] for c in north] != [c["daylight_court"] for c in south]
    assert all(c["daylight_court_placement"]["useful_daylight_benefit"] > 0 for c in north+south)


def test_ew_searches_real_terrace_edge_alternatives():
    ew=next(c for c in RequirementSeededTopologyGeneratorV1().generate(context()) if c["topology_family"]=="EW")
    assert ew["terrace_search"]
    assert all(t["searched_edges"] and t["alternative_count"] > 0 and t["polygon"] for t in ew["terrace_search"])


def test_post_gate_remains_fail_closed():
    result=SpatialReservationExclusivityV1().evaluate([
        ReservationZone("CORE","vertical_core","ground",[[0,0],[3,0],[3,3],[0,3]],("ground","first")),
        ReservationZone("VEHICLE","vehicle_circulation","ground",[[1,1],[4,1],[4,4],[1,4]])])
    assert result["hard_validation_status"] == "not_feasible"
    assert "core_overlaps_vehicle_circulation" in result["hard_failure_codes"]


def test_regeneration_never_seeds_historical_geometry_and_has_invalidation_contract():
    ctx=context();ctx["prior_geometry"]=[{"core":[[999,999],[1000,999],[1000,1000],[999,1000]]}]
    candidates=RequirementSeededTopologyGeneratorV1().generate(ctx,{"element_type":"core","new_anchor":"north"})
    assert all(not c["prior_geometry_used_as_seed"] for c in candidates)
    assert all(c["dependency_invalidation"]["regeneration"]=="clean_from_requirements" for c in candidates)
    assert all([999,999] not in c["core"] for c in candidates)


def test_no_parcel_two_coordinate_or_offset_hardcode_in_placement_module():
    source=Path(ReservationAwarePlacementV1.__module__.replace(".","/") + ".py")
    text=(Path.cwd()/source).read_text(encoding="utf-8")
    assert "Parcel 2" not in text and "PARCEL2" not in text


def test_generated_candidates_publish_authoritative_floor_ownership_and_pass_it():
    for candidate in RequirementSeededTopologyGeneratorV1().generate(context()):
        ownership=candidate["floor_program_ownership"]
        assert ownership["contract"]=="FloorProgramSpatialOwnershipV1"
        assert all(item["balanced"] for item in ownership["area_accounting"].values())
        assert candidate["hard_validation_status"]==ownership["hard_validation_status"]
        assert candidate["hard_validation_status"]==("not_feasible" if ownership["hard_failures"] else "hard_valid")


def test_commercial_is_generated_after_and_outside_all_prior_ground_reservations():
    for candidate in RequirementSeededTopologyGeneratorV1().generate(context()):
        commercial=Polygon(candidate["commercial_viable"])
        forbidden=[candidate["core"],candidate["stair"],candidate["elevator"],candidate["lobby"],
                   *candidate["parking_stalls"],candidate["vehicle_reserved_zone"],
                   candidate["ground_common"],candidate["ground_service"]]
        assert all(not polygon or commercial.intersection(Polygon(polygon)).area < 1e-7 for polygon in forbidden)


def test_court_semantics_and_core_components_are_continuous_across_scope():
    candidate=RequirementSeededTopologyGeneratorV1().generate(context())[0]
    records={s["space_id"]:s for s in candidate["floor_program_ownership"]["spaces"]}
    assert records["DAYLIGHT-COURT"]["vertical_extent"]=="RESIDENTIAL_LEVEL_DAYLIGHT_VOID"
    assert "ground" not in records["DAYLIGHT-COURT"]["floor_scope"]
    for role in ("CORE","STAIR","ELEVATOR"):
        assert records[role]["floor_scope"]==["ground","first","second","third"]
        assert records[role]["vertical_extent"].startswith("CONTINUOUS:")


def test_topology_change_cleanly_regenerates_program_and_ownership_not_local_patch():
    base=context(); generator=RequirementSeededTopologyGeneratorV1()
    before=generator.generate(base)
    after=generator.generate(base,{"element_type":"core","new_anchor":"north"})
    assert all(c["dependency_invalidation"]["regeneration"]=="clean_from_requirements" for c in after)
    assert all(c["floor_program_ownership"]["spaces"] for c in after)
    assert [c["geometry_fingerprint"] for c in before] != [c["geometry_fingerprint"] for c in after]


def test_generation_queries_ownership_in_required_order_and_terraces_have_parent_edge():
    required=["floor_buildable_envelope","vertical_core_stack","parking_and_vehicle_field",
        "pedestrian_common_service_reserves","daylight_void","residential_unit_envelopes",
        "terraces","commercial_remaining_ground_field","void_unallocated_accounting",
        "authoritative_ownership_validation","architectural_critic"]
    for candidate in RequirementSeededTopologyGeneratorV1().generate(context()):
        assert candidate["ownership_queries_before_creation"]
        assert candidate["generation_sequence"]==required
        assert all(item["parent_unit_compatible_edge"] for item in candidate["terrace_search"])
