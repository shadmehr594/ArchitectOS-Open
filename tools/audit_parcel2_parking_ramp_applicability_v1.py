"""Run the Architecture-only Parking Classification & Ramp Enclosure checkpoint."""
from datetime import datetime, timezone
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.architecture.reasoning.parcel2_parking_ramp_applicability_audit_v1 import (  # noqa: E402
    Parcel2ParkingRampApplicabilityAuditV1,
)

PROJECT = ROOT / "core/architecture/contracts/parcel2_human_program_evidence_v1.json"
REGULATION = ROOT / "core/architecture/contracts/iran_topic4_vehicle_parking_ramp_slope_evidence_v1.json"


def main(output_root=None):
    result = Parcel2ParkingRampApplicabilityAuditV1().resolve(
        json.loads(PROJECT.read_text(encoding="utf-8")),
        json.loads(REGULATION.read_text(encoding="utf-8")),
        None,
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    root = Path(output_root) if output_root else ROOT / "exports/DEFAULT" / ("parcel2_parking_ramp_applicability_v1_" + stamp)
    root.mkdir(parents=True, exist_ok=False)
    path = root / "PARCEL2_PARKING_RAMP_APPLICABILITY_AUDIT_V1.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--output-root")
    main(parser.parse_args().output_root)
