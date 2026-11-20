import copy
import json
from pathlib import Path
import pytest
import importlib.util

from core.architecture.reasoning.authoritative_occupancy_schedule_v1 import AuthoritativeOccupancyScheduleV1

ROOT = Path(__file__).resolve().parents[2]
BRIEF = json.loads((ROOT / "core/architecture/contracts/parcel2_occupancy_design_brief_v1.json").read_text(encoding="utf-8"))
REGISTRY = json.loads((ROOT / "core/architecture/contracts/parcel2_occupancy_research_authority_v1.json").read_text(encoding="utf-8"))

HISTORICAL_KEYS = {"superseded_assistant_suggestions", "superseded_non_authoritative_suggestion"}
UNCONFIRMED_ACTIVE_FRAGMENTS = ('"area_m2": 25', '"area_m2": 30', '"retail_shop"', '"total": 12')


def active_only(value):
    """Remove only explicitly historical branches; keep every active/default-producing path."""
    if isinstance(value, dict):
        return {key: active_only(child) for key, child in value.items() if key not in HISTORICAL_KEYS}
    if isinstance(value, list):
        return [active_only(child) for child in value]
    return value


def assert_no_unconfirmed_values_in_active_paths(value):
    encoded = json.dumps(active_only(value), ensure_ascii=False)
    for fragment in UNCONFIRMED_ACTIVE_FRAGMENTS:
        assert fragment not in encoded


def build(brief=BRIEF):
    return AuthoritativeOccupancyScheduleV1().build(project_id="parcel_2", design_brief=brief, authority_registry=REGISTRY)


def authoritative(value):
    return {"value": value, "evidence_status": "authoritative", "authority_class": "TEST_AUTHORITY",
            "source_reference": "test://authoritative", "provenance": ["test_fixture"],
            "applicability": {"project_id": "parcel_2", "status": "explicit"}}


def test_current_parcel2_brief_fails_closed_after_unconfirmed_inputs_are_removed():
    result = build()
    assert result["status"] == "unresolved_authoritative_occupancy_inputs"
    assert result["occupancy_schedule"] is None
    assert result["required_human_or_authoritative_inputs"] == ["commercial_occupiable_area", "residential_design_population", "occupancy_conversion_rule"]
    assert BRIEF["occupancy_inputs"]["commercial_use_type"]["value"] == "generic_commercial"
    assert result["defaults_applied"] is False and result["geometry_generated"] is False
    controls = BRIEF["planning_control_inputs"]
    assert controls["allowed_FAR"]["value"] is None and controls["allowed_FAR"]["human_input_required"]
    assert controls["max_site_coverage"]["value"] is None
    assert [x["value_percent"] for x in controls["coverage_controls"]["value"]] == [100, 100]
    assert controls["commercial_area_target"]["value"] is None
    assert BRIEF["occupancy_inputs"]["commercial_use_type"]["status"] == "resolved_generic_until_explicit_subtype_selection"
    assert BRIEF["occupancy_inputs"]["residential_design_population"]["value"] is None


def test_complete_authoritative_fixture_is_deterministic_and_non_mutating():
    brief = copy.deepcopy(BRIEF)
    values = {"commercial_floor_scope": ["ground"], "commercial_use_type": "retail_shop",
              "commercial_occupiable_area": {"area_m2": 50.0, "basis": "net"},
              "residential_design_population": {"unit_1": 3, "unit_2": 2, "unit_3": 2},
              "occupancy_conversion_rule": {"method": "explicit_design_population"}}
    brief["occupancy_inputs"] = {key: authoritative(value) for key, value in values.items()}
    before = copy.deepcopy(brief)
    first, second = build(brief), build(brief)
    assert brief == before and first == second
    assert first["status"] == "authoritative_resolved" and first["occupancy_schedule"] is not None


def test_area_requires_explicit_net_or_gross_basis():
    brief = copy.deepcopy(BRIEF)
    brief["occupancy_inputs"]["commercial_occupiable_area"] = authoritative({"area_m2": 50.0, "basis": "unknown"})
    assert build(brief)["fields"]["commercial_occupiable_area"]["status"] == "unresolved_authoritative_input"


def test_conflict_and_forbidden_sizing_fail_closed():
    brief = copy.deepcopy(BRIEF)
    brief["occupancy_inputs"]["commercial_use_type"] = {"status": "conflict", "conflicting_evidence": ["retail", "office"]}
    assert build(brief)["fields"]["commercial_use_type"]["status"] == "conflict"
    brief["shaft"] = {"width": 1.8}
    with pytest.raises(ValueError, match="forbidden geometry/sizing"):
        build(brief)


def test_unconfirmed_values_never_leak_as_defaults_or_authority():
    result = build()
    assert result["defaults_applied"] is False
    assert_no_unconfirmed_values_in_active_paths({
        "project_inputs": BRIEF["occupancy_inputs"],
        "planning_inputs": BRIEF["planning_control_inputs"],
        "resolver_fields": result["fields"],
        "validator_output": result.get("validator_output"),
        "occupancy_schedule": result["occupancy_schedule"],
        "defaults": result.get("defaults"),
    })


def test_superseded_history_is_allowed_only_with_explicit_non_authoritative_lifecycle():
    project_record = REGISTRY["records"][0]
    history = project_record["superseded_assistant_suggestions"]
    assert history
    for entry in history.values():
        assert entry["lifecycle_status"] == "SUPERSEDED"
        assert entry["authority_status"] == "NON_AUTHORITATIVE"
        assert entry["active"] is False
        assert entry["may_feed_active_resolvers"] is False
    assert project_record["default_value_authority"] is False
    result = build()
    assert result["occupancy_schedule"] is None
    assert result["defaults_applied"] is False


@pytest.mark.parametrize("active_surface", [
    {"project_input": {"area_m2": 25, "basis": "net"}},
    {"validator_output": {"commercial_use_type": "retail_shop"}},
    {"occupancy_schedule": {"residential": {"design_population": {"total": 12}}}},
    {"default_path": {"commercial_area_target": {"area_m2": 30, "basis": "gross"}}},
])
def test_historical_values_are_rejected_if_surfaced_through_an_active_path(active_surface):
    with pytest.raises(AssertionError):
        assert_no_unconfirmed_values_in_active_paths(active_surface)


def test_supersession_lifecycle_is_explicit_and_preserves_old_payload(tmp_path):
    module_path = ROOT / "tools/publish_parcel2_authoritative_occupancy_schedule_v1.py"
    spec = importlib.util.spec_from_file_location("parcel2_publisher", module_path)
    publisher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(publisher)
    old = tmp_path / "old.json"
    replacement = tmp_path / "corrected.json"
    old.write_text(json.dumps({"status": "authoritative_resolved", "occupancy_schedule": {"legacy": True}}), encoding="utf-8")
    replacement.write_text("{}", encoding="utf-8")
    publisher.mark_superseded(old, replacement, "unconfirmed_inputs")
    lifecycle = json.loads(old.read_text(encoding="utf-8"))
    assert lifecycle["occupancy_schedule"] == {"legacy": True}
    assert lifecycle["publication_lifecycle"] == {"status": "SUPERSEDED", "superseded_by": str(replacement), "reason": "unconfirmed_inputs"}
