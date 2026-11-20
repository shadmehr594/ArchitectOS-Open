"""Audit Parcel 2 program evidence without running any design or geometry stage."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.architecture.reasoning.authoritative_mixed_use_program_contract_v1 import (  # noqa: E402
    AuthoritativeMixedUseProgramContractV1,
)


BASEMENT = ROOT / "exports/DEFAULT/parcel2_basement_v2_20260909_143231_229427/PARCEL2_BASEMENT_V2_CONTRACT.json"
RECOMMENDATION = ROOT / "exports/DEFAULT/parcel2_basement_v2_20260909_143231_229427/program_alternative_recommendation_v1_20260910_153650/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json"


REQUESTED_ITEMS = [
    {"id": "commercial", "function": "commercial"},
    {"id": "residential_floors", "function": "residential"},
    {"id": "residential_units_per_floor", "function": "residential_unit"},
    {"id": "terrace_per_unit", "function": "terrace", "semantics": {"ownership": "unit"}},
    {"id": "parking", "function": "parking", "semantics": {"access": "vehicle"}},
    {"id": "stair", "function": "stair", "semantics": {"common_circulation": True}},
    {"id": "elevator", "function": "elevator", "semantics": {"common_circulation": True}},
    {"id": "lobby_common_circulation", "function": "lobby"},
    {"id": "dedicated_pedestrian_entrance", "function": "public_pedestrian_entrance"},
    {"id": "storage", "function": "storage"},
    {"id": "service", "function": "service"},
    {"id": "mechanical", "function": "mechanical"},
    {"id": "electrical", "function": "electrical"},
    {"id": "wc", "function": "wc"},
    {"id": "caretaker", "function": "caretaker"},
    {"id": "guard_unit", "function": "guard_unit"},
    {"id": "residential_daylight", "function": "principal_daylight_function"},
]


def record(item_id, value, path, *, function=None):
    return {
        "id": item_id, "function": function or item_id, "requirement_type": "hard",
        **value, "source": "user_project_requirement", "source_contract": "PARCEL2_BASEMENT_V2_CONTRACT",
        "source_path": str(BASEMENT) + "#" + path,
        "provenance": [{"contract": "PARCEL2_BASEMENT_V2_CONTRACT", "path": path}],
        "confidence": 1.0, "applicability": {"project_id": "parcel_2", "status": "authoritative_for_current_test"},
        "authoritative": True, "human_decision_required": False,
    }


def collect_evidence():
    data = json.loads(BASEMENT.read_text(encoding="utf-8"))
    req = data["requirements"]
    if req.get("source") != "user_project_requirement" or req.get("evidence_status") != "authoritative_for_current_test":
        raise ValueError("Parcel 2 source contract is not marked authoritative")
    parking = req["parking"]
    core = req["core"]
    evidence = [
        record("parking", {"count": parking["minimum_count"], "quantity": {"minimum": parking["minimum_count"]},
                           "capacity": parking["minimum_count"],
                           "semantics": {"stall_width": parking["stall_width"], "stall_depth": parking["stall_depth"],
                                         "aisle_width": parking["aisle_width"],
                                         "minimum_turning_radius": parking["minimum_turning_radius"]}},
               "requirements.parking"),
        record("stair", {"count": 1, "semantics": {"clear_width": core["stair_clear_width"],
                                                      "common_circulation": True}}, "requirements.core.stair_clear_width"),
        record("elevator", {"count": 1, "semantics": {"required": core["elevator_required"],
                                                         "shaft_clear": core["elevator_shaft_clear"],
                                                         "common_circulation": True}}, "requirements.core.elevator_required"),
        record("lobby_common_circulation", {"count": 1, "semantics": {"lobby_clear": core["lobby_clear"],
                                                                         "common_circulation": True}},
               "requirements.core.lobby_clear", function="lobby"),
    ]
    if RECOMMENDATION.exists():
        recommendation = json.loads(RECOMMENDATION.read_text(encoding="utf-8"))
        evidence.append({
            "id": "commercial", "function": "commercial", "requirement_type": "preferred",
            "source": "human_review_recommendation", "source_contract": recommendation.get("contract", "ProgramAlternativeRecommendationV1"),
            "source_path": str(RECOMMENDATION) + "#preferred_program_direction",
            "provenance": [{"contract": recommendation.get("contract"), "publication_status": recommendation.get("publication_status")}],
            "confidence": 0.0, "applicability": {"project_id": "parcel_2"}, "authoritative": False,
            "human_decision_required": True,
            "note": "Pending recommendation is context only; it does not establish commercial as a requirement.",
        })
    return evidence


def main(output_root=None):
    contract = AuthoritativeMixedUseProgramContractV1().build(
        project_id="parcel_2", requested_items=REQUESTED_ITEMS, evidence_records=collect_evidence())
    contract.update({
        "audit_scope": "architecture_only_authoritative_program_evidence",
        "source_contracts_read_only": [str(BASEMENT), str(RECOMMENDATION)],
        "final_selection_performed": False, "winner": None,
        "room_layout_generated": False, "final_windows_generated": False,
        "parcel_2_resolve_executed": False, "structure_executed": False,
        "bim_executed": False, "ifc_executed": False, "render_executed": False,
    })
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    root = Path(output_root) if output_root else ROOT / "exports/DEFAULT" / ("parcel2_authoritative_program_audit_v1_" + stamp)
    root.mkdir(parents=True, exist_ok=False)
    path = root / "PARCEL2_AUTHORITATIVE_MIXED_USE_PROGRAM_AUDIT_V1.json"
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root")
    args = parser.parse_args()
    main(args.output_root)
