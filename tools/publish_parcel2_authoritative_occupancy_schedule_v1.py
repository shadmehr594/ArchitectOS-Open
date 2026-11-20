"""Publish the architecture-only Parcel 2 occupancy schedule from confirmed inputs."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.architecture.reasoning.authoritative_occupancy_schedule_v1 import (  # noqa: E402
    AuthoritativeOccupancyScheduleV1,
)


BRIEF = ROOT / "core/architecture/contracts/parcel2_occupancy_design_brief_v1.json"
AUTHORITY = ROOT / "core/architecture/contracts/parcel2_occupancy_research_authority_v1.json"
PREVIOUS_AUTHORITATIVE = ROOT / "exports/DEFAULT/parcel2_authoritative_occupancy_schedule_v1_20260912_122553_440024/PARCEL2_AUTHORITATIVE_OCCUPANCY_SCHEDULE_V1.json"


def mark_superseded(previous_path, replacement_path, reason):
    previous = json.loads(previous_path.read_text(encoding="utf-8"))
    previous["publication_lifecycle"] = {
        "status": "SUPERSEDED",
        "superseded_by": str(replacement_path),
        "reason": reason,
    }
    previous_path.write_text(json.dumps(previous, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    brief = json.loads(BRIEF.read_text(encoding="utf-8"))
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    result = AuthoritativeOccupancyScheduleV1().build(
        project_id="parcel_2", design_brief=brief, authority_registry=authority)
    result["planning_dependencies"] = {
        "mixed_use_allowed_FAR": "unresolved_not_a_logical_dependency_of_confirmed_occupancy_schedule",
        "coverage_controls": "resolved_floor_and_use_aware_project_specific_100_100",
    }
    result["workflow_readiness"] = {
        "elevator_traffic": "READY_INPUTS_ONLY_NOT_EXECUTED" if result["status"] == "authoritative_resolved" else "BLOCKED_UNRESOLVED_OCCUPANCY_INPUTS",
        "downstream_work_executed": False,
    }
    result["elevator_traffic_status"] = "READY" if result["status"] == "authoritative_resolved" else "BLOCKED"
    result["scope"] = "architecture_only_occupancy_diagnostic_publication"
    result["publication_kind"] = "authoritative_schedule" if result["status"] == "authoritative_resolved" else "corrected_unresolved_diagnostic"
    if PREVIOUS_AUTHORITATIVE.exists():
        result["supersedes"] = str(PREVIOUS_AUTHORITATIVE)
        result["supersession_reason"] = "previous_schedule_depended_on_superseded_100_60_coverage_and_unconfirmed_30_25_area_retail_shop_population_4_4_4"
    result.pop("contract_fingerprint", None)
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    result["contract_fingerprint"] = sha256(encoded.encode("utf-8")).hexdigest()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    output_dir = ROOT / "exports/DEFAULT" / ("parcel2_authoritative_occupancy_schedule_v1_" + stamp)
    output_dir.mkdir(parents=True, exist_ok=False)
    path = output_dir / "PARCEL2_AUTHORITATIVE_OCCUPANCY_SCHEDULE_V1.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if PREVIOUS_AUTHORITATIVE.exists():
        mark_superseded(PREVIOUS_AUTHORITATIVE, path, result["supersession_reason"])
    print(path)


if __name__ == "__main__":
    main()
