"""Focused tests for asset-specific forward resolution (Phase 3D-W)."""

import copy
import inspect
import json
from pathlib import Path

import pytest

from core.asset.asset_forward_resolver import (
    RULE_STATUSES,
    OUTCOME_FAMILY_UNKNOWN,
    OUTCOME_GEOMETRY_AGREED,
    OUTCOME_GEOMETRY_AMBIGUOUS,
    OUTCOME_GEOMETRY_DISAGREED,
    OUTCOME_GEOMETRY_UNOBSERVABLE,
    OUTCOME_GATE_NOT_EVALUATED_NO_GEOMETRY,
    OUTCOME_NO_FAMILY_SUPPLIED,
    OUTCOME_RULE_UNRESOLVED,
    OUTCOME_RULE_UNSUPPORTED,
    OUTCOME_SUPPORTED_NO_GATE_REQUIRED,
    resolve_asset_forward,
    rule_to_forward_contract,
)
from core.asset.mesh_transform_spec import build_mesh_transform_spec

FAMILY_ID = "seating_and_adult_beds"


def _rule(**overrides):
    rule = {
        "status": "supported",
        "semantic_forward_axis": "+Z",
        "expected_geometry_direction": "-Z",
        "geometry_gate_required": True,
        "scope": {"include_categories": ["chair"]},
        "evidence": {
            "rule_id": "forward_family_rule_v1",
            "source_checkpoint": "phase_3d_q_bounded_audit",
            "agreement": 0.95,
            "notes": ["seating_and_adult_beds_only"],
        },
    }
    rule.update(overrides)

    return rule


def _evidence(state="observable", axis="Z", sign="-"):
    observable = state == "observable"

    return {
        "state": state,
        "axis": axis if observable else None,
        "sign": sign if observable else None,
        "offset_x": 0.0,
        "offset_z": -0.4 if observable else 0.0,
        "magnitude": 0.4 if observable else 0.0,
        "threshold": 0.02,
    }


def _resolve(rule=None, family_id=FAMILY_ID, evidence=None):
    return resolve_asset_forward(
        rule=rule, family_id=family_id, geometry_evidence=evidence
    )


# ---------------------------------------------------------------------------
# 1 - 3. rule -> contract mapping
# ---------------------------------------------------------------------------

def test_supported_rule_contract_carries_declared_axis():
    contract = rule_to_forward_contract(_rule(), FAMILY_ID)

    assert contract["status"] == "supported"
    assert contract["axis"] == "+Z"
    assert contract["source"] == "family_rule"
    assert contract["family"] == FAMILY_ID
    assert contract["evidence"]["rule_id"] == "forward_family_rule_v1"
    assert contract["evidence"]["agreement"] == pytest.approx(0.95)
    assert contract["evidence"]["geometry_gate"] == "not_evaluated"


def test_unresolved_rule_contract_has_null_axis():
    contract = rule_to_forward_contract(_rule(status="unresolved"), FAMILY_ID)

    assert contract["status"] == "unresolved"
    assert contract["axis"] is None
    assert contract["source"] == "family_rule"
    assert contract["family"] == FAMILY_ID


def test_unsupported_rule_contract_is_not_unsupported_with_an_axis():
    contract = rule_to_forward_contract(_rule(status="unsupported"), FAMILY_ID)

    assert contract["status"] == "unresolved"
    assert contract["axis"] is None
    assert contract["status"] != "unsupported"


def test_contract_mapping_does_not_include_geometry_gate_required():
    contract = rule_to_forward_contract(_rule(), FAMILY_ID)

    assert "geometry_gate_required" not in contract
    assert set(contract) == {
        "status",
        "axis",
        "axis_frame",
        "source",
        "family",
        "evidence",
    }
    assert contract["axis_frame"] == "raw_mesh_local_frame"


# ---------------------------------------------------------------------------
# 4 - 5. missing / unknown family
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("family_id", [None, "", "   "])
def test_missing_family_id_yields_no_family_supplied(family_id):
    result = _resolve(rule=_rule(), family_id=family_id)

    assert result["outcome"] == OUTCOME_NO_FAMILY_SUPPLIED
    assert result["geometry_gate"] == "not_evaluated"
    contract = result["forward_contract"]
    assert contract["status"] == "unresolved"
    assert contract["axis"] is None
    assert contract["source"] == "none"
    assert contract["family"] is None


def test_unknown_family_yields_family_unknown_and_echoes_id():
    result = _resolve(rule=None, family_id="not_a_family")

    assert result["outcome"] == OUTCOME_FAMILY_UNKNOWN
    assert result["family_id"] == "not_a_family"
    contract = result["forward_contract"]
    assert contract["status"] == "unresolved"
    assert contract["axis"] is None
    assert contract["source"] == "none"
    assert contract["family"] is None


# ---------------------------------------------------------------------------
# 6 - 10. gated supported rule
# ---------------------------------------------------------------------------

def test_gated_rule_without_geometry_is_unresolved():
    result = _resolve(rule=_rule())

    assert result["outcome"] == OUTCOME_GATE_NOT_EVALUATED_NO_GEOMETRY
    assert result["geometry_gate"] == "not_evaluated"
    assert result["forward_contract"]["status"] == "unresolved"
    assert result["forward_contract"]["axis"] is None


def test_gated_rule_with_unobservable_geometry_is_unobservable():
    result = _resolve(rule=_rule(), evidence=_evidence(state="unobservable"))

    assert result["outcome"] == OUTCOME_GEOMETRY_UNOBSERVABLE
    assert result["geometry_gate"] == "not_evaluated"
    assert result["forward_contract"]["status"] == "unobservable"
    assert result["forward_contract"]["axis"] is None


def test_gated_rule_with_ambiguous_geometry_is_ambiguous():
    result = _resolve(rule=_rule(), evidence=_evidence(state="ambiguous"))

    assert result["outcome"] == OUTCOME_GEOMETRY_AMBIGUOUS
    assert result["geometry_gate"] == "not_evaluated"
    assert result["forward_contract"]["status"] == "ambiguous"
    assert result["forward_contract"]["axis"] is None


def test_gated_rule_with_agreeing_geometry_keeps_rule_axis():
    result = _resolve(rule=_rule(), evidence=_evidence("observable", "Z", "-"))

    assert result["outcome"] == OUTCOME_GEOMETRY_AGREED
    assert result["geometry_gate"] == "agreed"
    assert result["forward_contract"]["status"] == "supported"
    assert result["forward_contract"]["axis"] == "+Z"


def test_gated_rule_with_disagreeing_geometry_falls_back_to_unresolved():
    result = _resolve(rule=_rule(), evidence=_evidence("observable", "Z", "+"))

    assert result["outcome"] == OUTCOME_GEOMETRY_DISAGREED
    assert result["geometry_gate"] == "disagreed"
    assert result["forward_contract"]["status"] == "unresolved"
    assert result["forward_contract"]["axis"] is None


# ---------------------------------------------------------------------------
# 11 - 12. non-gated supported rule
# ---------------------------------------------------------------------------

def test_non_gated_rule_needs_no_geometry():
    result = _resolve(rule=_rule(geometry_gate_required=False))

    assert result["outcome"] == OUTCOME_SUPPORTED_NO_GATE_REQUIRED
    assert result["geometry_gate"] == "not_evaluated"
    assert result["forward_contract"]["status"] == "supported"
    assert result["forward_contract"]["axis"] == "+Z"
    assert result["reasons"] == ["rule_does_not_require_geometry_gate"]


def test_non_gated_rule_ignores_supplied_geometry():
    # Geometry that would DISAGREE with a gated rule must not affect a
    # non-gated rule, and must never replace the declared axis.
    result = _resolve(
        rule=_rule(geometry_gate_required=False),
        evidence=_evidence("observable", "Z", "+"),
    )

    assert result["outcome"] == OUTCOME_SUPPORTED_NO_GATE_REQUIRED
    assert result["forward_contract"]["status"] == "supported"
    assert result["forward_contract"]["axis"] == "+Z"
    assert result["forward_contract"]["axis"] != "+Z"[::-1]
    assert "geometry_not_required_by_rule" in result["reasons"]


def test_non_gated_rule_keeps_axis_even_with_contradicting_geometry():
    result = _resolve(
        rule=_rule(geometry_gate_required=False),
        evidence=_evidence("observable", "X", "-"),
    )

    assert result["forward_contract"]["axis"] == "+Z"


# ---------------------------------------------------------------------------
# 13 - 15. provenance and immutability
# ---------------------------------------------------------------------------

def test_source_checkpoint_is_preserved_as_one_compact_note():
    contract = rule_to_forward_contract(_rule(), FAMILY_ID)
    notes = contract["evidence"]["notes"]

    assert "seating_and_adult_beds_only" in notes
    assert "source_checkpoint:phase_3d_q_bounded_audit" in notes
    assert sum(note.startswith("source_checkpoint:") for note in notes) == 1


def test_source_checkpoint_note_is_not_duplicated():
    rule = _rule()
    rule["evidence"]["notes"] = [
        "seating_and_adult_beds_only",
        "source_checkpoint:phase_3d_q_bounded_audit",
    ]

    notes = rule_to_forward_contract(rule, FAMILY_ID)["evidence"]["notes"]

    assert sum(note.startswith("source_checkpoint:") for note in notes) == 1


def test_rule_and_evidence_are_not_mutated():
    rule = _rule()
    before = copy.deepcopy(rule)
    evidence = _evidence()

    contract = rule_to_forward_contract(rule, FAMILY_ID)
    contract["evidence"]["notes"].append("mutated")
    _resolve(rule=rule, evidence=evidence)

    assert rule == before
    assert evidence == _evidence()


def test_resolution_result_is_independent_of_later_rule_mutation():
    rule = _rule()
    result = _resolve(rule=rule, evidence=_evidence("observable", "Z", "-"))

    rule["semantic_forward_axis"] = "-X"

    assert result["forward_contract"]["axis"] == "+Z"


# ---------------------------------------------------------------------------
# 16 - 20. malformed input
# ---------------------------------------------------------------------------

def test_malformed_rule_status_is_rejected():
    with pytest.raises(ValueError, match="rule status must be one of"):
        _resolve(rule=_rule(status="maybe"))


@pytest.mark.parametrize("axis", ["+Y", "Z", "", 1, None])
def test_malformed_semantic_axis_is_rejected(axis):
    with pytest.raises(ValueError, match="semantic_forward_axis must be one of"):
        _resolve(rule=_rule(semantic_forward_axis=axis))


@pytest.mark.parametrize("direction", ["+Y", "back", "", None])
def test_malformed_expected_geometry_direction_is_rejected(direction):
    with pytest.raises(
        ValueError, match="expected_geometry_direction must be one of"
    ):
        _resolve(rule=_rule(expected_geometry_direction=direction))


@pytest.mark.parametrize("flag", ["true", 1, None])
def test_malformed_geometry_gate_required_is_rejected(flag):
    with pytest.raises(ValueError, match="geometry_gate_required must be a boolean"):
        _resolve(rule=_rule(geometry_gate_required=flag))


def test_missing_rule_evidence_is_rejected():
    with pytest.raises(ValueError, match="rule evidence must be a mapping"):
        _resolve(rule=_rule(evidence=None))


def test_unknown_rule_field_is_rejected():
    with pytest.raises(ValueError, match="unknown rule field"):
        _resolve(rule=_rule(confidence=0.9))


@pytest.mark.parametrize(
    "evidence",
    [
        {"state": "maybe"},
        {"state": "observable", "axis": "Z", "sign": "-"},
        "observable",
        None,
    ],
)
def test_malformed_geometry_evidence_is_rejected(evidence):
    if evidence is None:
        # None means "no geometry" and is valid; assert the valid path instead.
        assert _resolve(rule=_rule(), evidence=None)["outcome"] == (
            OUTCOME_GATE_NOT_EVALUATED_NO_GEOMETRY
        )
        return
    with pytest.raises(ValueError):
        _resolve(rule=_rule(), evidence=evidence)


def test_malformed_family_id_is_rejected():
    with pytest.raises(ValueError, match="family_id must be a non-empty string"):
        _resolve(rule=_rule(), family_id=123)


def test_rule_without_family_id_is_rejected():
    with pytest.raises(ValueError, match="family_id is required"):
        rule_to_forward_contract(_rule(), None)


# ---------------------------------------------------------------------------
# 28. mandatory anti-inversion test
# ---------------------------------------------------------------------------

def test_anti_inversion_semantic_axis_comes_from_the_rule_not_geometry():
    """The declared forward is "+X" while the expected geometry is "-Z".

    Measured geometry agrees with "-Z". If any code derived semantic forward by
    inverting the measured geometry it would produce "+Z". The correct result is
    the rule's "+X".
    """

    rule = _rule(
        semantic_forward_axis="+X",
        expected_geometry_direction="-Z",
        geometry_gate_required=True,
    )

    result = _resolve(rule=rule, evidence=_evidence("observable", "Z", "-"))

    assert result["geometry_gate"] == "agreed"
    assert result["forward_contract"]["status"] == "supported"
    assert result["forward_contract"]["axis"] == "+X"
    assert result["forward_contract"]["axis"] != "+Z"


def test_declared_axis_and_expected_geometry_are_independent():
    rule = _rule(
        semantic_forward_axis="-Z",
        expected_geometry_direction="+X",
    )

    agreed = _resolve(rule=rule, evidence=_evidence("observable", "X", "+"))
    disagreed = _resolve(rule=rule, evidence=_evidence("observable", "X", "-"))

    assert agreed["forward_contract"]["axis"] == "-Z"
    assert disagreed["forward_contract"]["axis"] is None


# ---------------------------------------------------------------------------
# 29 - 30. non-agreeing outcomes never carry an axis
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "rule, evidence",
    [
        (_rule(), None),
        (_rule(), _evidence(state="unobservable")),
        (_rule(), _evidence(state="ambiguous")),
        (_rule(), _evidence("observable", "Z", "+")),
        (_rule(status="unresolved"), None),
        (_rule(status="unsupported"), None),
        (None, None),
    ],
)
def test_non_agreeing_outcomes_have_null_axis(rule, evidence):
    result = _resolve(rule=rule, evidence=evidence)

    assert result["forward_contract"]["axis"] is None
    assert result["forward_contract"]["status"] != "supported"


def test_no_outcome_populates_verified():
    cases = [
        (_rule(), None),
        (_rule(), _evidence("observable", "Z", "-")),
        (_rule(), _evidence("observable", "Z", "+")),
        (_rule(geometry_gate_required=False), None),
        (_rule(status="unsupported"), None),
        (None, None),
    ]

    for rule, evidence in cases:
        result = _resolve(rule=rule, evidence=evidence)
        assert result["forward_contract"]["status"] != "verified"
        assert result["forward_contract"]["status"] != "unsupported"


# ---------------------------------------------------------------------------
# 31 - 34. execution boundary
# ---------------------------------------------------------------------------

def _all_keys(value):
    keys = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(key)
            keys |= _all_keys(item)
    elif isinstance(value, list):
        for item in value:
            keys |= _all_keys(item)

    return keys


def test_no_phi_matrix_translation_or_vertices_in_output():
    result = _resolve(rule=_rule(), evidence=_evidence("observable", "Z", "-"))
    keys = _all_keys(result)

    for forbidden in (
        "intrinsic_yaw_phi_rad",
        "mesh_alignment_matrix",
        "matrix4x4",
        "translation_xyz",
        "vertices_xyz",
        "faces",
    ):
        assert forbidden not in keys


# ---------------------------------------------------------------------------
# 21 - 27. structural boundary
# ---------------------------------------------------------------------------

def test_resolver_signature_accepts_no_vertices_or_registry():
    parameters = inspect.signature(resolve_asset_forward).parameters

    assert set(parameters) == {"rule", "family_id", "geometry_evidence"}
    for forbidden in ("vertices", "vertices_xyz", "mesh", "mesh_result",
                      "registry", "category", "path", "obj_path"):
        assert forbidden not in parameters
    assert parameters["geometry_evidence"].kind is inspect.Parameter.KEYWORD_ONLY


def _resolver_source():
    import core.asset.asset_forward_resolver as module

    return Path(module.__file__).read_text(encoding="utf-8")


def test_resolver_has_no_filesystem_access(monkeypatch):
    import builtins

    def _forbidden(*args, **kwargs):
        raise AssertionError("the resolver must not touch the filesystem")

    monkeypatch.setattr(builtins, "open", _forbidden)

    result = _resolve(rule=_rule(), evidence=_evidence("observable", "Z", "-"))

    assert result["forward_contract"]["axis"] == "+Z"
    assert "open(" not in _resolver_source()


def test_resolver_imports_no_forbidden_modules():
    source = _resolver_source()

    for token in (
        "raw_obj_loader",
        "furniture_adapter",
        "FurnitureAdapter",
        "forward_rule_registry",
        "ForwardRuleRegistry",
        "find_rules_for_category",
        "measure_upper_structure",
        "build_mesh_transform_spec",
    ):
        assert token not in source


def test_resolver_does_not_measure_geometry():
    import core.asset.asset_forward_resolver as module

    assert not hasattr(module, "measure_upper_structure")
    assert not hasattr(module, "ForwardRuleRegistry")
    assert not hasattr(module, "load_raw_obj")


def test_resolver_rule_status_vocabulary_matches_registry():
    from core.asset.forward_rule_registry import RULE_STATUSES as REGISTRY_STATUSES

    assert tuple(RULE_STATUSES) == tuple(REGISTRY_STATUSES)


# ---------------------------------------------------------------------------
# 35. integration with the existing transform spec
# ---------------------------------------------------------------------------

def _loader_result():
    return {
        "format_version": "raw_obj_mesh_v1",
        "model_id": "model-a",
        "raw_model_path": "D:/dataset/part1/model-a/raw_model.obj",
        "mesh_frame": "raw_mesh_local_frame",
        "geometry": {"index_base": 0, "vertices_xyz": [[1.0, 2.0, 3.0]], "faces": []},
        "bounds": {
            "min_xyz": [0.0, 0.0, 0.0],
            "max_xyz": [4.0, 5.0, 6.0],
            "dims_xyz": [4.0, 5.0, 6.0],
            "center_xyz": [2.0, 2.5, 3.0],
        },
        "pivot": {
            "mesh_origin_xyz": [0.0, 0.0, 0.0],
            "bbox_center_xyz": [2.0, 2.5, 3.0],
        },
        "status": {"state": "mesh_loaded_valid", "reasons": []},
    }


def _candidate():
    return {
        "source_engine": "DiffuScene",
        "slot": 3,
        "category": "chair",
        "mesh_source": {"model_id": "model-a", "raw_model_path": "x/raw_model.obj"},
        "position": {
            "room_local_xyz": [1.0, -3.0, 2.0],
            "world_xyz": None,
            "basis": "diffuscene_y_up_to_architectos_z_up_v1",
        },
        "rotation": {"yaw_rad": 0.0, "axis": "+Z", "mapping_status": "resolved"},
        "scale": {"policy": "no_deformation", "scale_xyz": [1.0, 1.0, 1.0]},
        "status": {"state": "ready_transform_metadata", "reasons": []},
    }


def test_resolved_contract_is_accepted_by_the_transform_spec_and_stays_pending():
    result = _resolve(rule=_rule(), evidence=_evidence("observable", "Z", "-"))
    contract = result["forward_contract"]
    assert contract["status"] == "supported"

    spec = build_mesh_transform_spec(
        _loader_result(), _candidate(), forward_contract=contract
    )

    assert spec["orientation"]["forward_status"] == "supported"
    assert spec["orientation"]["forward_axis"] == "+Z"
    # The transform remains non-executable.
    assert spec["orientation"]["intrinsic_yaw_phi_rad"] is None
    assert spec["transform"]["mesh_alignment_matrix"] is None
    assert spec["transform"]["matrix4x4"] is None
    assert spec["transform"]["translation_xyz"] is None
    assert spec["transform"]["up_alignment_matrix"] == [
        [1.0, 0.0, 0.0],
        [0.0, 0.0, -1.0],
        [0.0, 1.0, 0.0],
    ]
    assert spec["rotation_completeness"] == "placement_only"
    assert spec["status"]["state"] == "pending_mesh_alignment"


def test_default_contract_is_also_accepted_by_the_transform_spec():
    result = _resolve(rule=None, family_id=None)

    spec = build_mesh_transform_spec(
        _loader_result(), _candidate(), forward_contract=result["forward_contract"]
    )

    assert spec["orientation"]["forward_status"] == "unresolved"
    assert spec["orientation"]["forward_axis"] is None
    assert spec["status"]["state"] == "pending_mesh_alignment"
