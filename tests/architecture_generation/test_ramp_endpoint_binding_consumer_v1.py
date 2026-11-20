import json
from pathlib import Path

import pytest

from core.architecture.reasoning.authoritative_ramp_endpoint_binding_contract_v1 import AuthoritativeRampEndpointBindingContractV1
from core.architecture.reasoning.edge_controlled_curved_ramp_topology_v3 import EdgeControlledCurvedRampTopologyV3
from core.architecture.reasoning.project_level_contract_v1 import ProjectLevelContractV1


ROOT = Path(__file__).resolve().parents[2]


def test_edge_generator_z_profile_consumes_nonstandard_authoritative_start_and_end():
    source = sorted((ROOT / "exports/DEFAULT").glob(
        "parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json"))[-1]
    data = json.loads(source.read_text(encoding="utf-8"))
    data["requirements"]["ramp"]["minimum_inner_turn_radius"] = 5.0
    confirmations = [
        {"kind": "level_elevation", "level": "ramp_start", "value": 0.35, "unit": "m",
         "authority_class": "PROJECT_REQUIREMENT", "provenance": ["synthetic_nonstandard_endpoint"]},
        {"kind": "level_elevation", "level": "ramp_arrival", "value": -3.10, "unit": "m",
         "authority_class": "PROJECT_REQUIREMENT", "provenance": ["synthetic_nonstandard_endpoint"]},
    ]
    binding = AuthoritativeRampEndpointBindingContractV1().resolve(
        ProjectLevelContractV1().resolve(confirmations=confirmations))
    result = EdgeControlledCurvedRampTopologyV3().resolve(
        data["site"]["parcel"], data["site"]["frontage"], data["physical_basement_wall"],
        data["requirements"], {"status": "required", "slope": 0.15,
                               "authoritative_ramp_endpoint_binding": binding})

    assert result["candidates"]
    assert result["authoritative_ramp_endpoint_binding"]["expected_start_z"] == pytest.approx(0.35)
    assert result["authoritative_ramp_endpoint_binding"]["expected_end_z"] == pytest.approx(-3.10)
    for candidate in result["candidates"]:
        profile = candidate["topology"]["z_profile"]
        assert profile["start_z"] == pytest.approx(0.35)
        assert profile["end_z"] == pytest.approx(-3.10)
