from copy import deepcopy
from core.architecture.reasoning.frontage_relative_architectural_quality_v1 import FrontageRelativeArchitecturalQualityV1

def candidate(core, commercial=None):
    return {"candidate_id":"C","parking_count":3,"temp_core":core,"stalls":[],"aisle_manoeuvre":[[4,0],[7,0],[7,20],[4,20]],
            "public_pedestrian_path":[[0,0],[1,0],[1,20],[0,20]],"pedestrian_shared_with_manoeuvre_region":[],
            "vehicle_entrance":[[4,0],[7,0]],"direct_commercial_street_frontage_region":commercial or [],"selection_status":"not_selected"}

def test_frontage_relative_depth_is_direction_agnostic_and_no_winner():
    domain={"polygon":[[0,0],[10,0],[10,20],[0,20]]}; front={"segment":[[0,0],[10,0]]}
    args=(domain,front,[candidate([[1,14],[4,14],[4,18],[1,18]])]); frozen=deepcopy(args)
    out=FrontageRelativeArchitecturalQualityV1().evaluate(*args)
    assert args==frozen and out["input_mutated"] is False and out["selected_candidate"] is None
    assert out["candidates"][0]["architectural_quality"]["core_position"]=="rear_interior"
    rotated={"polygon":[[0,0],[0,10],[-20,10],[-20,0]]}; rfront={"segment":[[0,0],[0,10]]}
    rout=FrontageRelativeArchitecturalQualityV1().evaluate(rotated,rfront,[candidate([[-14,1],[-14,4],[-18,4],[-18,1]])])
    assert rout["candidates"][0]["architectural_quality"]["core_position"]=="rear_interior"

def test_front_core_is_architecturally_disfavored_while_geometry_can_remain_valid():
    out=FrontageRelativeArchitecturalQualityV1().evaluate({"polygon":[[0,0],[10,0],[10,20],[0,20]]},{"segment":[[0,0],[10,0]]},[candidate([[1,1],[4,1],[4,5],[1,5]])])
    q=out["candidates"][0]["architectural_quality"]
    assert q["status"]=="architecturally_disfavored" and "FRONT_CORE_BLOCKS_COMMERCIAL_FRONTAGE" in q["reasons"]
