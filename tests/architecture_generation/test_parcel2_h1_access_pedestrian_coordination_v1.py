import json
from pathlib import Path
from tools.run_parcel2_h1_access_pedestrian_coordination_v1 import main

def test_frozen_h1_access_diagnostic_is_fail_closed_and_non_selecting(tmp_path):
    result=main(tmp_path)
    report=json.loads(Path(result["json"]).read_text(encoding="utf-8"))
    assert len(report["candidates"]) == 19
    assert len({c["candidate_id"] for c in report["candidates"]}) == 19
    assert report["input_checkpoint"]["geometry_reused"] is True
    assert report["input_checkpoint"]["regenerated"] is False
    assert report["stable_frontage_binding"]["cardinal_assumption_used"] is False
    assert report["numeric_policy"]["old_3m_fixture_used_as_authority"] is False
    assert report["numeric_policy"]["minimum_clear_separation"] is None
    assert report["final_selection_performed"] is False
    assert sum(report["outcome_counts"].values()) == 19
    assert all(c["rejected_vehicle_access_insertions"] or c["vehicle_access_candidates"] for c in report["candidates"])
    assert all(c["commercial_residual_candidate_area_m2"] is None for c in report["candidates"] if c["outcome_group"] != "resolved")
    assert Path(result["svg"]).read_text(encoding="utf-8").startswith("<svg")
