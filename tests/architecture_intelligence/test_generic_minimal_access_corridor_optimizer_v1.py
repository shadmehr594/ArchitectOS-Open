from copy import deepcopy

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from core.architecture.reasoning.generic_access_first_pilotis_search_v1 import GenericAccessFirstPilotisSearchV1
from core.architecture.reasoning.generic_minimal_access_corridor_optimizer_v1 import GenericMinimalAccessCorridorOptimizerV1


def _fixture():
    domain = {"polygon": [[0,0],[10,0],[10,20],[0,20]], "floor_scope": "ground_pilotis", "evidence_status": "resolved"}
    frontage = {"segment": [[0,0],[10,0]], "status": "confirmed"}
    access = {"vehicle_clear_width": 3.5, "pedestrian_clear_width": 1.2, "commercial_candidate_depth": 4.0}
    cores = [{"candidate_id": "CORE-A", "polygon": [[5.5,13],[9.5,13],[9.5,17],[5.5,17]]}]
    parking = {"minimum_required_capacity": 3, "stall_width": 2.5, "stall_depth": 5.0, "aisle_width": 5.0, "vehicle_clear_width": 3.5}
    candidates = GenericAccessFirstPilotisSearchV1().produce(domain, frontage, access, cores, parking)["candidates"]
    return domain, frontage, candidates


def test_optimizer_is_deterministic_non_mutating_and_does_not_select_winner():
    args = _fixture()
    frozen = deepcopy(args)
    worker = GenericMinimalAccessCorridorOptimizerV1()
    first, second = worker.optimize(*args), worker.optimize(*args)
    assert args == frozen and first == second and first["input_mutated"] is False
    assert first["selected_candidate"] is None and first["final_selection_performed"] is False


def test_minimal_corridor_reachability_conflicts_pedestrian_and_commercial_gates():
    domain, frontage, candidates = _fixture()
    result = GenericMinimalAccessCorridorOptimizerV1().optimize(domain, frontage, candidates)
    assert result["candidate_count"] >= 1
    front = LineString(frontage["segment"])
    for candidate in result["candidates"]:
        corridor = Polygon(candidate["vehicle_corridor"])
        aisle = Polygon(candidate["aisle_manoeuvre"])
        stalls = [Polygon(item["polygon"]) for item in candidate["stalls"]]
        core = Polygon(candidate["temp_core"])
        commercial = Polygon(candidate["direct_commercial_street_frontage_region"])
        ped = Polygon(candidate["public_pedestrian_path"])
        ped_exclusive_coords = candidate["pedestrian_exclusive_region"]
        ped_exclusive = Polygon(ped_exclusive_coords) if ped_exclusive_coords and isinstance(ped_exclusive_coords[0][0], (int,float)) else Polygon()
        mandatory = unary_union(stalls + [aisle, core, ped_exclusive])
        assert candidate["parking_count"] >= 3 and candidate["all_gates_pass"]
        assert candidate["metrics"]["new_minimal_vehicle_corridor_length_m"] < candidate["metrics"]["old_vehicle_corridor_length_m"]
        assert candidate["metrics"]["new_minimal_vehicle_corridor_area_m2"] < candidate["metrics"]["old_vehicle_corridor_area_m2"]
        assert corridor.buffer(1e-7).intersects(front) and corridor.buffer(1e-7).intersects(aisle)
        assert all(corridor.intersection(zone).area <= 1e-7 for zone in stalls + [core])
        assert all(stall.distance(aisle) <= 1e-7 for stall in stalls)
        assert ped.buffer(1e-7).intersects(front)
        assert commercial.buffer(1e-7).intersection(front).length > 1e-7
        assert commercial.intersection(mandatory).area <= 1e-7
