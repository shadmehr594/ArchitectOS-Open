"""Focused tests for the versioned forward rule registry (Phase 3D-U)."""

import copy
import json
from pathlib import Path

import pytest

from core.asset.forward_rule_registry import (
    DEFAULT_REGISTRY_PATH,
    FORMAT_VERSION,
    ForwardRuleRegistry,
)

FAMILY_ID = "seating_and_adult_beds"
SAMPLE_MODEL_ID = "003a85cc-1a58-4b93-8b5c-11ad960aded5"


def _rule(**overrides):
    rule = {
        "status": "supported",
        "semantic_forward_axis": "+Z",
        "expected_geometry_direction": "-Z",
        "geometry_gate_required": True,
        "scope": {
            "include_categories": ["chair"],
            "exclude_categories": ["kids_bed"],
        },
        "evidence": {
            "rule_id": "rule_v1",
            "source_checkpoint": "checkpoint_v1",
            "agreement": 0.95,
            "notes": ["note_one"],
        },
    }
    rule.update(overrides)

    return rule


def _registry(rules=None, **top_level):
    data = {"format_version": FORMAT_VERSION, "rules": rules or {"fam": _rule()}}
    data.update(top_level)

    return data


def _load_default():
    return ForwardRuleRegistry.from_file(DEFAULT_REGISTRY_PATH)


# ---------------------------------------------------------------------------
# 1 - 7. registry V1 content
# ---------------------------------------------------------------------------

def test_registry_v1_loads_successfully():
    registry = _load_default()

    assert registry.family_ids == (FAMILY_ID,)


def test_format_version_is_exact():
    registry = _load_default()

    assert registry.format_version == FORMAT_VERSION
    assert FORMAT_VERSION == "forward_rule_registry_v1"


def test_known_family_lookup_succeeds():
    rule = _load_default().get_forward_rule(FAMILY_ID)

    assert rule is not None
    assert rule["evidence"]["rule_id"] == "forward_family_rule_v1"


def test_unknown_family_returns_none():
    registry = _load_default()

    assert registry.get_forward_rule("no_such_family") is None
    assert registry.get_forward_rule("") is None
    assert registry.get_forward_rule(None) is None


def test_supported_rule_declares_plus_z_forward():
    rule = _load_default().get_forward_rule(FAMILY_ID)

    assert rule["status"] == "supported"
    assert rule["semantic_forward_axis"] == "+Z"


def test_expected_geometry_direction_is_minus_z():
    rule = _load_default().get_forward_rule(FAMILY_ID)

    assert rule["expected_geometry_direction"] == "-Z"
    # Declared explicitly, not derived from the forward axis.
    assert rule["expected_geometry_direction"] != rule["semantic_forward_axis"]


def test_geometry_gate_is_required_for_the_accepted_rule():
    rule = _load_default().get_forward_rule(FAMILY_ID)

    assert rule["geometry_gate_required"] is True


# ---------------------------------------------------------------------------
# 8 - 13. category scope
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "category",
    [
        "chair",
        "bed",
        "king_size_bed",
        "classic_chinese_chair",
        "dressing_chair",
        "loveseat_sofa",
        "l_shaped_sofa",
        "three_seat_/_multi_seat_sofa",
        "lounge_chair_/_cafe_chair_/_office_chair",
        "lounge_chair_/_book_chair_/_computer_chair",
    ],
)
def test_include_scope_contains_expected_categories(category):
    rule = _load_default().get_forward_rule(FAMILY_ID)

    assert category in rule["scope"]["include_categories"]


@pytest.mark.parametrize("category", ["kids_bed", "bunk_bed"])
def test_kids_and_bunk_beds_are_excluded(category):
    rule = _load_default().get_forward_rule(FAMILY_ID)

    assert category in rule["scope"]["exclude_categories"]
    assert category not in rule["scope"]["include_categories"]


def test_include_and_exclude_are_disjoint():
    rule = _load_default().get_forward_rule(FAMILY_ID)

    include = set(rule["scope"]["include_categories"])
    exclude = set(rule["scope"]["exclude_categories"])

    assert include & exclude == set()


def test_include_and_exclude_overlap_is_rejected():
    rule = _rule(
        scope={
            "include_categories": ["chair"],
            "exclude_categories": ["chair"],
        }
    )

    with pytest.raises(ValueError, match="must be disjoint"):
        ForwardRuleRegistry(_registry({"fam": rule}))


# ---------------------------------------------------------------------------
# 14 - 18. structural validation
# ---------------------------------------------------------------------------

def test_duplicate_included_category_is_rejected():
    rule = _rule(
        scope={"include_categories": ["chair", "chair"]},
    )

    with pytest.raises(ValueError, match="duplicate entry"):
        ForwardRuleRegistry(_registry({"fam": rule}))


def test_duplicate_excluded_category_is_rejected():
    rule = _rule(
        scope={
            "include_categories": ["chair"],
            "exclude_categories": ["kids_bed", "kids_bed"],
        }
    )

    with pytest.raises(ValueError, match="duplicate entry"):
        ForwardRuleRegistry(_registry({"fam": rule}))


def test_category_included_by_two_families_is_rejected():
    rules = {
        "fam_a": _rule(),
        "fam_b": _rule(scope={"include_categories": ["chair"]}),
    }

    with pytest.raises(ValueError, match="included by two families"):
        ForwardRuleRegistry(_registry(rules))


def test_empty_include_list_is_rejected():
    rule = _rule(scope={"include_categories": []})

    with pytest.raises(ValueError, match="at least one entry"):
        ForwardRuleRegistry(_registry({"fam": rule}))


@pytest.mark.parametrize("family_id", ["", "   "])
def test_blank_family_id_is_rejected(family_id):
    with pytest.raises(ValueError, match="family id must be a non-empty string"):
        ForwardRuleRegistry(_registry({family_id: _rule()}))


def test_family_id_with_surrounding_whitespace_is_rejected():
    with pytest.raises(ValueError, match="surrounding whitespace"):
        ForwardRuleRegistry(_registry({" fam ": _rule()}))


# ---------------------------------------------------------------------------
# 19 - 23. axis and status validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("axis", ["+Y", "Z", "forward", "", 0, None])
def test_invalid_semantic_forward_axis_is_rejected(axis):
    with pytest.raises(ValueError, match="semantic_forward_axis must be one of"):
        ForwardRuleRegistry(_registry({"fam": _rule(semantic_forward_axis=axis)}))


@pytest.mark.parametrize("axis", ["+Y", "Z", "back", "", None])
def test_invalid_expected_geometry_direction_is_rejected(axis):
    with pytest.raises(
        ValueError, match="expected_geometry_direction must be one of"
    ):
        ForwardRuleRegistry(
            _registry({"fam": _rule(expected_geometry_direction=axis)})
        )


def test_verified_family_rule_status_is_rejected():
    with pytest.raises(ValueError, match="not a valid family-rule authority state"):
        ForwardRuleRegistry(_registry({"fam": _rule(status="verified")}))


@pytest.mark.parametrize("status", ["ambiguous", "unobservable"])
def test_per_asset_result_states_are_rejected_as_rule_status(status):
    with pytest.raises(ValueError, match="not a valid family-rule authority state"):
        ForwardRuleRegistry(_registry({"fam": _rule(status=status)}))


def test_unknown_rule_status_is_rejected():
    with pytest.raises(ValueError, match="rule status must be one of"):
        ForwardRuleRegistry(_registry({"fam": _rule(status="maybe")}))


def test_geometry_gate_required_must_be_boolean():
    with pytest.raises(ValueError, match="geometry_gate_required must be a boolean"):
        ForwardRuleRegistry(
            _registry({"fam": _rule(geometry_gate_required="yes")})
        )


# ---------------------------------------------------------------------------
# 24 - 32. evidence and forbidden fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("agreement", [1.5, -0.1, 2, float("inf")])
def test_out_of_range_agreement_is_rejected(agreement):
    evidence = _rule()["evidence"]
    evidence = dict(evidence, agreement=agreement)

    with pytest.raises(ValueError, match="agreement must be"):
        ForwardRuleRegistry(_registry({"fam": _rule(evidence=evidence)}))


def test_null_agreement_is_allowed():
    evidence = dict(_rule()["evidence"], agreement=None)
    registry = ForwardRuleRegistry(_registry({"fam": _rule(evidence=evidence)}))

    assert registry.get_forward_rule("fam")["evidence"]["agreement"] is None


def test_non_list_notes_are_rejected():
    evidence = dict(_rule()["evidence"], notes="a note")

    with pytest.raises(ValueError, match="notes must be an array of strings"):
        ForwardRuleRegistry(_registry({"fam": _rule(evidence=evidence)}))


def test_over_long_notes_are_rejected():
    evidence = dict(_rule()["evidence"], notes=["x" * 400])

    with pytest.raises(ValueError, match="notes must stay compact"):
        ForwardRuleRegistry(_registry({"fam": _rule(evidence=evidence)}))


@pytest.mark.parametrize(
    "field", ["confidence", "enabled", "priority", "geometry_gate_result"]
)
def test_unknown_rule_field_is_rejected(field):
    with pytest.raises(ValueError, match=field):
        ForwardRuleRegistry(_registry({"fam": _rule(**{field: True})}))


@pytest.mark.parametrize(
    "field",
    ["phi", "intrinsic_yaw_phi_rad", "mesh_alignment_matrix", "matrix4x4",
     "translation_xyz", "transform"],
)
def test_phi_matrix_and_transform_fields_are_rejected(field):
    with pytest.raises(ValueError, match=field):
        ForwardRuleRegistry(_registry({"fam": _rule(**{field: None})}))


def test_sample_model_id_is_rejected():
    evidence = dict(_rule()["evidence"], notes=[SAMPLE_MODEL_ID])

    with pytest.raises(ValueError, match="sample model id"):
        ForwardRuleRegistry(_registry({"fam": _rule(evidence=evidence)}))


def test_sample_model_id_as_category_is_rejected():
    rule = _rule(scope={"include_categories": [SAMPLE_MODEL_ID]})

    with pytest.raises(ValueError, match="sample model id"):
        ForwardRuleRegistry(_registry({"fam": rule}))


def test_machine_specific_path_is_rejected():
    evidence = dict(
        _rule()["evidence"], source_checkpoint=r"D:\dataset\part1\checkpoint"
    )

    with pytest.raises(ValueError, match="machine-specific path"):
        ForwardRuleRegistry(_registry({"fam": _rule(evidence=evidence)}))


def test_unknown_top_level_and_scope_and_evidence_fields_are_rejected():
    with pytest.raises(ValueError, match="unknown registry field"):
        ForwardRuleRegistry(_registry(rules={"fam": _rule()}, extra=1))
    with pytest.raises(ValueError, match="unknown scope field"):
        ForwardRuleRegistry(
            _registry({"fam": _rule(scope={"include_categories": ["chair"], "x": 1})})
        )
    with pytest.raises(ValueError, match="unknown evidence field"):
        ForwardRuleRegistry(
            _registry(
                {"fam": _rule(evidence=dict(_rule()["evidence"], rows=[1]))}
            )
        )


def test_format_version_mismatch_is_rejected():
    with pytest.raises(ValueError, match="format_version must be"):
        ForwardRuleRegistry(_registry(format_version="forward_rule_registry_v2"))


def test_missing_required_fields_are_rejected():
    for key in ("status", "scope", "evidence", "geometry_gate_required"):
        rule = _rule()
        del rule[key]
        with pytest.raises(ValueError, match="is missing"):
            ForwardRuleRegistry(_registry({"fam": rule}))


# ---------------------------------------------------------------------------
# 33 - 37. lookup behaviour
# ---------------------------------------------------------------------------

def test_lookup_does_not_modify_the_source_registry():
    source = _registry()
    before = copy.deepcopy(source)
    registry = ForwardRuleRegistry(source)

    returned = registry.get_forward_rule("fam")
    returned["status"] = "unsupported"
    returned["scope"]["include_categories"].append("mutated")

    assert source == before
    assert registry.get_forward_rule("fam")["status"] == "supported"
    assert registry.get_forward_rule("fam")["scope"]["include_categories"] == ["chair"]


def test_find_rules_for_category_uses_exact_membership():
    registry = _load_default()

    matches = registry.find_rules_for_category("chair")

    assert len(matches) == 1
    assert matches[0]["family_id"] == FAMILY_ID
    assert matches[0]["rule"]["semantic_forward_axis"] == "+Z"


@pytest.mark.parametrize("category", ["kids_bed", "bunk_bed"])
def test_excluded_categories_do_not_match(category):
    registry = _load_default()

    assert registry.find_rules_for_category(category) == []


def test_no_substring_lookup():
    registry = _load_default()

    for category in ["chair_extra", "chai", "classic_chinese_chair_old"]:
        assert registry.find_rules_for_category(category) == []


def test_no_fuzzy_or_case_insensitive_lookup():
    registry = _load_default()

    for category in ["chairs", "Chair", "CHAIR", "chairs_"]:
        assert registry.find_rules_for_category(category) == []


def test_unknown_category_returns_empty_list():
    registry = _load_default()

    assert registry.find_rules_for_category("not_a_real_category") == []
    assert registry.find_rules_for_category(None) == []


# ---------------------------------------------------------------------------
# 38 - 41. execution boundary
# ---------------------------------------------------------------------------

def _registry_source():
    import core.asset.forward_rule_registry as module

    return Path(module.__file__).read_text(encoding="utf-8")


def test_registry_does_not_import_furniture_adapter():
    assert "FurnitureAdapter" not in _registry_source()
    assert "furniture_adapter" not in _registry_source()


def test_registry_does_not_import_raw_obj_loader_or_geometry_gate():
    source = _registry_source()

    assert "raw_obj_loader" not in source
    assert "forward_geometry_gate" not in source
    assert "measure_upper_structure" not in source
    assert "evaluate_geometry_agreement" not in source


def test_registry_does_not_touch_transform_construction():
    import core.asset.forward_rule_registry as module

    # None of these are imported or reachable from the registry module. They may
    # only appear in the docstring's illustrative caller chain.
    for name in (
        "build_mesh_transform_spec",
        "resolve_forward_contract",
        "mesh_alignment_matrix",
        "matrix4x4",
        "translation_xyz",
        "intrinsic_yaw_phi_rad",
    ):
        assert not hasattr(module, name)

    source = _registry_source()

    # The only import from the transform-spec module is the axis vocabulary.
    assert "from core.asset.mesh_transform_spec import FORWARD_AXES" in source
    for token in (
        "mesh_alignment_matrix",
        "matrix4x4",
        "translation_xyz",
        "intrinsic_yaw_phi_rad",
    ):
        assert token not in source


def test_registry_has_no_category_heuristic_matching():
    source = _registry_source()

    for token in ("re.match", "re.search", "startswith", "endswith", " in category"):
        assert token not in source


def test_registry_module_performs_no_filesystem_write():
    source = _registry_source()

    assert "open(" in source  # the read-only loader
    assert '"w"' not in source
    assert "'w'" not in source


def test_registry_does_not_measure_geometry():
    import core.asset.forward_rule_registry as module

    assert not hasattr(module, "measure_upper_structure")
    assert not hasattr(module, "evaluate_geometry_agreement")
    assert not hasattr(module, "build_mesh_transform_spec")


def test_schema_file_matches_the_loader_contract():
    schema = json.loads(
        Path(DEFAULT_REGISTRY_PATH).with_name("forward_rules.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert schema["properties"]["format_version"]["const"] == FORMAT_VERSION
    rule_schema = schema["properties"]["rules"]["additionalProperties"]
    assert rule_schema["additionalProperties"] is False
    assert set(rule_schema["required"]) == {
        "status",
        "semantic_forward_axis",
        "expected_geometry_direction",
        "geometry_gate_required",
        "scope",
        "evidence",
    }
    assert rule_schema["properties"]["status"]["enum"] == [
        "supported",
        "unresolved",
        "unsupported",
    ]
