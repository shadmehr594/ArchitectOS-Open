"""Produce the Architecture-only Human Program Confirmation V1 checkpoint."""
from datetime import datetime, timezone
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from core.architecture.reasoning.human_program_confirmation_v1 import (  # noqa: E402
    HumanProgramConfirmationV1, ProgramConfirmationSemanticConsistencyAudit)

BASE = ROOT / "exports/DEFAULT/parcel2_authoritative_program_audit_v1_20260911_104452_613173/PARCEL2_AUTHORITATIVE_MIXED_USE_PROGRAM_AUDIT_V1.json"
EVIDENCE = ROOT / "core/architecture/contracts/parcel2_human_program_evidence_v1.json"

def main(output_root=None):
    result = HumanProgramConfirmationV1().build(
        authoritative_contract=json.loads(BASE.read_text(encoding="utf-8")),
        evidence_contract=json.loads(EVIDENCE.read_text(encoding="utf-8")),
        daylight_deficit_state="UNKNOWN")
    semantic_audit = ProgramConfirmationSemanticConsistencyAudit().audit(result["program_items"])
    if not semantic_audit["passed"]:
        raise ValueError("ProgramConfirmationSemanticConsistencyAudit failed")
    result.update(
        audit_scope="architecture_only_human_program_confirmation",
        semantic_consistency_audit=semantic_audit,
        checkpoint_status=("PASSED_READY_FOR_CLEAN_RESOLVE_PREPARATION"
                           if result["clean_parcel_2_resolve_ready"]
                           else "BLOCKED_PENDING_REQUIRED_HUMAN_INPUT"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    root = Path(output_root) if output_root else ROOT / "exports/DEFAULT" / ("parcel2_human_program_confirmation_v1_" + stamp)
    root.mkdir(parents=True, exist_ok=False)
    path = root / "PARCEL2_HUMAN_PROGRAM_CONFIRMATION_V1.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path); return path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--output-root")
    main(parser.parse_args().output_root)
