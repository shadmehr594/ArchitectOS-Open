from copy import deepcopy
from pathlib import Path
import importlib.util, json, sys

ROOT=Path(r"<repo-root>")
sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.parcel2_room_level_design_v1 import Parcel2RoomLevelDesignV1

V8=ROOT/"exports/DEFAULT/parcel2_h1_upper_floor_design_around_current_core_v8_20260912_212949/PARCEL2_H1_UPPER_FLOOR_DESIGN_AROUND_CURRENT_CORE_V8.json"

def sample():
    d=json.loads(V8.read_text(encoding="utf-8"));t=d["core_hypotheses"][0];f=t["floors"][0];return t,f,f["units"][0]

def test_determinism_no_mutation_and_provenance():
    t,f,u=sample();original=deepcopy(u);e=Parcel2RoomLevelDesignV1();a=e.solve_unit(unit_record=u,public_corridor=f["public_corridor"],topology_id=t["topology_id"],floor_id=f["floor_id"]);b=e.solve_unit(unit_record=u,public_corridor=f["public_corridor"],topology_id=t["topology_id"],floor_id=f["floor_id"])
    assert a==b and u==original
    assert all(h["program_hypothesis"]["authority_class"]=="DESIGN_ASSUMPTION_NON_AUTHORITATIVE" for h in a["hypotheses"])
    assert all(h["winner"] is None and not h["authoritative_ranking"] for h in a["hypotheses"])

def test_room_contract_threshold_containment_overlap_daylight_service_and_agi_gate():
    from shapely.geometry import Polygon
    t,f,u=sample();out=Parcel2RoomLevelDesignV1().solve_unit(unit_record=u,public_corridor=f["public_corridor"],topology_id=t["topology_id"],floor_id=f["floor_id"]);unit=Polygon(out["unit_boundary"])
    for h in out["hypotheses"]:
        assert Parcel2RoomLevelDesignV1.REQUIRED_USES <= {r["use"] for r in h["rooms"]}
        assert all(unit.buffer(1e-6).covers(Polygon(r["boundary"])) for r in h["rooms"] if len(r["boundary"])>=3)
        assert h["evaluation"]["before"]["physical_room_overlap_m2"]==0
        assert h["public_corridor_stops_at_threshold"]
        assert h["evaluation"]["before"]["daylight_opening_opportunity_m"]
        assert "service_plumbing_cluster_distance_m" in h["evaluation"]["before"]
        assert (h["intervention"] is None)==(not h["spatial_problem_detection"])
        if h["intervention"]:
            assert h["intervention"]["precedent_geometry_visible"] is False
            assert h["intervention"]["agi_adapter"]=="defensive_copy"

def test_no_parcel2_geometry_or_special_shape_hardcode():
    src=(ROOT/"core/architecture/reasoning/parcel2_room_level_design_v1.py").read_text(encoding="utf-8").lower()
    assert "h1-v6" not in src and "curve" not in src and "radial" not in src and "pentagon" not in src
