from copy import deepcopy
from pathlib import Path

import pytest
from shapely.geometry import box

from core.architecture.reasoning.authoritative_ramp_endpoint_binding_contract_v1 import AuthoritativeRampEndpointBindingContractV1
from core.architecture.reasoning.edge_controlled_curved_ramp_topology_v3 import EdgeControlledCurvedRampTopologyV3
from core.architecture.reasoning.far_end_operational_turn_v2 import FarEndOperationalTurnV2, RampOperationalEndV1
from core.architecture.reasoning.project_level_contract_v1 import ProjectLevelContractV1


ROOT = Path(__file__).resolve().parents[2]


def elevation(level, value, provenance=None):
    return {"kind": "level_elevation", "level": level, "value": value, "unit": "m",
            "authority_class": "PROJECT_REQUIREMENT",
            "provenance": ["human_confirmed_project_requirement"] if provenance is None else provenance}


def resolved_levels(start=0.35, end=-3.10):
    return ProjectLevelContractV1().resolve(confirmations=[
        elevation("ramp_start", start), elevation("ramp_arrival", end)])


def test_nonstandard_endpoints_and_project_evidence_propagate_without_mutation():
    levels = resolved_levels()
    frozen = deepcopy(levels)
    first = AuthoritativeRampEndpointBindingContractV1().resolve(levels)
    second = AuthoritativeRampEndpointBindingContractV1().resolve(levels)
    assert first == second and levels == frozen
    assert first["status"] == "resolved" and first["binding_resolved"] is True
    assert first["expected_start_z"] == pytest.approx(0.35)
    assert first["expected_end_z"] == pytest.approx(-3.10)
    assert first["endpoints"]["start"]["source_contract"] == "ProjectLevelContractV1"
    assert first["endpoints"]["end"]["source_path"] == "level_evidence.ramp_arrival"
    assert first["endpoints"]["end"]["key"] == "ramp_arrival"
    assert first["endpoints"]["end"]["provenance"] == ["human_confirmed_project_requirement"]
    assert first["level_dependency_resolved"] is True
    assert first["placement_slope_parking_integration_validated"] is False


def test_missing_legacy_fallback_and_invalid_provenance_fail_closed():
    resolver = AuthoritativeRampEndpointBindingContractV1()
    assert resolver.resolve(None)["binding_resolved"] is False
    legacy = ProjectLevelContractV1().resolve(confirmations=[
        elevation("ground", 0.0), elevation("basement", -2.4)])
    assert resolver.resolve(legacy)["failure_reasons"] == ["explicit_ramp_endpoints_required_no_fallback"]
    invalid = resolved_levels()
    invalid["level_evidence"]["ramp_start"][0]["provenance"] = []
    assert resolver.resolve(invalid)["failure_reasons"] == ["ramp_start_provenance_invalid"]


def test_conflicting_endpoint_evidence_fails_closed():
    levels = resolved_levels()
    conflict = deepcopy(levels["level_evidence"]["ramp_arrival"][0])
    conflict["value"] = -3.25
    levels["level_evidence"]["ramp_arrival"].append(conflict)
    result = AuthoritativeRampEndpointBindingContractV1().resolve(levels)
    assert result["status"] == "conflicted"
    assert result["binding_resolved"] is False
    assert result["expected_end_z"] is None
    assert "ramp_arrival_conflicting_evidence" in result["failure_reasons"]


def test_validator_uses_contract_expected_end_not_basement_literal():
    field = box(5, 0, 10, 5)
    validator = RampOperationalEndV1()
    accepted = validator.resolve([[5, 1], [5, 4]], list(field.exterior.coords)[:-1], 3, -3.10, [1, 0], -3.10)
    rejected = validator.resolve([[5, 1], [5, 4]], list(field.exterior.coords)[:-1], 3, -2.40, [1, 0], -3.10)
    assert accepted["geometry_status"] == "resolved"
    assert rejected["geometry_status"] == "not_feasible"
    assert "end_elevation_not_at_authoritative_endpoint" in rejected["failure_reasons"]


@pytest.mark.parametrize("resolver", [FarEndOperationalTurnV2(), EdgeControlledCurvedRampTopologyV3()])
def test_generators_fail_closed_before_geometry_without_binding(resolver):
    result = resolver.resolve([], {}, {}, {}, {"status": "required", "slope": 0.15})
    assert result["status"] == "pending_requirement"
    assert result["candidates"] == []
    assert result["failure_reasons"] == ["authoritative_ramp_endpoint_binding_missing_or_unresolved"]


def test_patched_production_files_have_no_raw_endpoint_defaults_or_literals():
    files = [ROOT / "core/architecture/reasoning/far_end_operational_turn_v2.py",
             ROOT / "core/architecture/reasoning/edge_controlled_curved_ramp_topology_v3.py"]
    for path in files:
        source = path.read_text(encoding="utf-8")
        assert "end_z+2.4" not in source
        assert "start_z=0" not in source
        assert "end_z=-2.4" not in source
        assert "requirements[\"levels\"][\"ground\"]" not in source
        assert "requirements[\"levels\"][\"basement\"]" not in source
        assert "requirements['levels']['ground']" not in source
        assert "requirements['levels']['basement']" not in source
