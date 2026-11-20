import hashlib
import json
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.architecture.reasoning.pilot_parking_feasibility_study_v1 import (
    PilotParkingFeasibilityStudyV1,
)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def main():
    baseline_path = sorted((ROOT / "exports" / "DEFAULT").glob("parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json"))[-1]
    recommendation_path = sorted((ROOT / "exports" / "DEFAULT").glob("parcel2_basement_v2_*/program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json"))[-1]
    baseline_contract = json.loads(baseline_path.read_text(encoding="utf-8"))
    recommendation = json.loads(recommendation_path.read_text(encoding="utf-8"))
    protected = deepcopy(baseline_contract)
    before = fingerprint(protected)
    result = PilotParkingFeasibilityStudyV1().resolve(
        baseline_contract["site"], baseline_contract["requirements"],
        recommendation["baseline_scenario_a"],
    )
    if fingerprint(baseline_contract) != before:
        raise RuntimeError("Scenario A baseline mutation detected")
    result["source_baseline_contract_path"] = str(baseline_path)
    result["source_recommendation_contract_path"] = str(recommendation_path)
    result["baseline_contract_preservation_fingerprint"] = before
    folder = baseline_path.parent / ("pilot_parking_feasibility_study_v1_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    folder.mkdir()
    output = folder / "PARCEL2_PILOT_PARKING_FEASIBILITY_STUDY_V1.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "json": str(output),
        "candidate_count": result["candidate_count"],
        "families": result["candidate_families_explored"],
        "best_candidate": (result["best_pilot_candidate"] or {}).get("candidate_id"),
        "diagnostic_candidate": result["best_diagnostic_candidate_id"],
        "parking_capacity": result["pilot_parking_capacity"],
        "independently_usable": result["independently_usable_parking_count"],
        "worthy": result["scenario_b_worthy_of_final_comparison"],
        "program_changed": result["program_changed"],
        "basement_deleted": result["basement_deleted"],
    }))


if __name__ == "__main__":
    main()
