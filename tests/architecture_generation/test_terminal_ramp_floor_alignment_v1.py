import json
from functools import lru_cache
from pathlib import Path

from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.terminal_ramp_floor_alignment_v1 import TerminalRampFloorAlignmentV1


ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / "exports/DEFAULT/parcel2_basement_v2_20260909_143231_229427/edge_controlled_v3_20260909_230806/PARCEL2_15_EDGE_CONTROLLED_TOPOLOGY_V3.json"


@lru_cache(maxsize=1)
def real_result():
    recorded = json.loads(V3.read_text(encoding="utf-8"))
    source = sorted((ROOT / "exports/DEFAULT").glob("parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json"))[-1]
    base = json.loads(source.read_text(encoding="utf-8"))
    helper = BasementRampParkingDesignReasonerV2()
    frame = helper._frame(base["site"]["parcel"], base["site"]["frontage"])
    inner = helper._to_local_polygon(base["physical_basement_wall"]["inner_face"], frame)
    return TerminalRampFloorAlignmentV1().resolve(recorded["new_search"]["candidates"], inner)


def test_consumes_recorded_v3_without_rerunning_search():
    result = real_result()
    assert result["source"] == "recorded_edge_controlled_v3_hard_valid_candidates"
    assert result["v3_search_rerun"] is False


def test_maneuver_overlap_is_never_accepted():
    result = real_result()
    for candidate in result["candidates"]:
        if candidate["ramp_maneuver_overlap_area"] > 1e-7:
            assert "maneuvering_field_overlaps_sloped_ramp" in candidate["failure_reasons"]


def test_hard_valid_terminal_contract_is_level_downstream_and_line_connected():
    result = real_result()
    valid = [c for c in result["candidates"] if c["geometry_status"] == "hard_valid"]
    for candidate in valid:
        a = candidate["alignment"]
        assert a["end_left"][2] == a["end_midpoint"][2] == a["end_right"][2] == -2.4
        assert candidate["end_interface_width"] >= 3.0 - 1e-7
        assert candidate["downstream_half_plane_valid"]
        assert candidate["ramp_maneuver_overlap_area"] <= 1e-7
        assert candidate["terminal_maneuver_overlap_area"] <= 1e-7


def test_parking_remains_out_of_scope():
    result = real_result()
    assert result["parking_search_status"] == "not_run_terminal_arrival_validation"
    assert all(c["parking_search_status"] == "not_run_terminal_arrival_validation" for c in result["candidates"])


def test_repeat_is_deterministic():
    a, b = real_result(), real_result()
    assert a["hard_valid_candidates"] == b["hard_valid_candidates"]
    assert [c["candidate_id"] for c in a["candidates"]] == [c["candidate_id"] for c in b["candidates"]]
