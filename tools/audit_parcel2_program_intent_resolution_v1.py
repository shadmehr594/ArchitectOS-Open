"""Produce a contract-only Parcel 2 program-intent resolution audit."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.architecture.reasoning.program_intent_resolution_v1 import ProgramIntentResolutionV1  # noqa: E402


BASE_CONTRACT = ROOT / "exports/DEFAULT/parcel2_authoritative_program_audit_v1_20260911_104452_613173/PARCEL2_AUTHORITATIVE_MIXED_USE_PROGRAM_AUDIT_V1.json"
RECOMMENDATION = ROOT / "exports/DEFAULT/parcel2_basement_v2_20260909_143231_229427/program_alternative_recommendation_v1_20260910_153650/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json"


def collect_resolution_evidence():
    records = []
    if RECOMMENDATION.exists():
        data = json.loads(RECOMMENDATION.read_text(encoding="utf-8"))
        records.append({
            "id": "commercial", "requirement_type": "preferred",
            "source_kind": "human_preference", "confirmation_status": "unconfirmed",
            "source": "pending_architectural_recommendation",
            "source_contract": data["contract"], "source_path": str(RECOMMENDATION) + "#preferred_program_direction",
            "key": "preferred_program_direction",
            "provenance": [{"contract": data["contract"], "key": "preferred_program_direction",
                            "publication_status": data.get("publication_status")}],
            "confidence": 0.0, "applicability": {"project_id": "parcel_2"},
            "value": data.get("preferred_program_direction"),
            "note": "Pending recommendation only; it does not establish a commercial requirement.",
        })
    return records


def main(output_root=None):
    base = json.loads(BASE_CONTRACT.read_text(encoding="utf-8"))
    result = ProgramIntentResolutionV1().build(
        authoritative_contract=base, evidence_records=collect_resolution_evidence())
    open_items = [item["id"] for item in result["program_items"]
                  if item["downstream_demand_state"] == "unknown"]
    result.update({
        "audit_scope": "architecture_only_program_intent_contract_and_evidence",
        "resolved_from_existing_evidence": result["status_index"]["authoritative_resolved"]
                                           + result["status_index"]["human_design_intent_resolved"],
        "still_open_for_human_confirmation": open_items,
        "source_contracts_read_only": [str(BASE_CONTRACT), str(RECOMMENDATION)],
        "parcel_2_resolve_executed": False, "final_selection_performed": False, "winner": None,
        "room_layout_generated": False, "final_windows_generated": False,
        "structure_executed": False, "bim_executed": False,
        "ifc_executed": False, "render_executed": False,
    })
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    root = Path(output_root) if output_root else ROOT / "exports/DEFAULT" / ("parcel2_program_intent_resolution_audit_v1_" + stamp)
    root.mkdir(parents=True, exist_ok=False)
    path = root / "PARCEL2_PROGRAM_INTENT_RESOLUTION_AUDIT_V1.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root")
    args = parser.parse_args()
    main(args.output_root)
