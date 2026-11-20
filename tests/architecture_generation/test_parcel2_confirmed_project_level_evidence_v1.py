import json
from pathlib import Path

from core.architecture.reasoning.project_level_contract_v1 import ProjectLevelContractV1


EVIDENCE = (Path(__file__).parents[2] / "core" / "architecture" / "contracts" /
            "parcel2_project_level_contract_v1.json")


def test_parcel2_human_confirmed_project_level_evidence_resolves_without_authority_leakage():
    source = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert source["authority_class"] == "PROJECT_REQUIREMENT"
    assert source["source_kind"] == "human_confirmed_project_requirement"
    assert "regulation" not in source["source_kind"]
    out = ProjectLevelContractV1().resolve(
        confirmations=source["human_level_confirmations"],
        project_semantics=source["project_semantics"])
    assert out["status"] == "resolved" and out["conflicts"] == []
    assert out["ramp_level_dependency"]["level_span"] == 2.4
    assert out["ramp_level_dependency"]["placement_slope_parking_integration_validated"] is False
    assert out["project_semantics"]["facts"]["residential_floor_count"] == 2
