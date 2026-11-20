"""Focused tests for the pure forward geometry agreement gate (Phase 3D-S)."""

import copy

import pytest

from core.asset.forward_geometry_gate import (
    GEOMETRY_GATE_AGREED,
    GEOMETRY_GATE_DISAGREED,
    GEOMETRY_GATE_NOT_EVALUATED,
    UPPER_STRUCTURE_THRESHOLD,
    evaluate_geometry_agreement,
    measure_upper_structure,
)
from core.asset.mesh_transform_spec import (
    build_mesh_transform_spec,
    resolve_forward_contract,
)

# The accepted Phase 3D-Q rule, supplied EXPLICITLY by the caller. No category or
# family detection exists anywhere in the implementation.
SEATING_RULE = {
    "status": "supported",
    "axis": "+Z",
    "axis_frame": "raw_mesh_local_frame",
    "source": "family_rule",
    "family": "seating_and_adult_beds",
    "evidence": {
        "rule_id": "forward_family_rule_v1",
        "notes": ["seating_and_adult_beds_only", "kids_and_bunk_beds_excluded"],
    },
}
EXPECTED_GEOMETRY_DIRECTION = "-Z"

AMBIGUOUS_EVIDENCE = {
    "state": "ambiguous",
    "axis": None,
    "sign": None,
    "offset_x": 0.0,
    "offset_z": 0.0,
    "magnitude": 0.0,
    "threshold": UPPER_STRUCTURE_THRESHOLD,
}


# ---------------------------------------------------------------------------
# synthetic fixtures: a 1x1x1 box footprint with a small upper cluster
# ---------------------------------------------------------------------------

def _mesh(offset_x=0.0, offset_z=0.0):
    vertices = []
    for x in (-0.5, 0.5):
        for z in (-0.5, 0.5):
            vertices.append([x, 0.0, z])
    for dx in (-0.01, 0.01):
        for dz in (-0.01, 0.01):
            vertices.append([offset_x + dx, 1.0, offset_z + dz])

    return vertices


def _degenerate_x_mesh(offset_z=0.0):
    return [[0.0, 0.0, -0.5], [0.0, 0.0, 0.5], [0.0, 1.0, offset_z]]


def _degenerate_z_mesh(offset_x=0.0):
    return [[-0.5, 0.0, 0.0], [0.5, 0.0, 0.0], [offset_x, 1.0, 0.0]]


# ---------------------------------------------------------------------------
# 1 - 5. URHCO measurement
# ---------------------------------------------------------------------------

def test_minus_z_upper_structure_is_observable():
    evidence = measure_upper_structure(_mesh(0.0, -0.4))

    assert evidence["state"] == "observable"
    assert evidence["axis"] == "Z"
    assert evidence["sign"] == "-"
    assert evidence["offset_z"] == pytest.approx(-0.4)
    assert evidence["magnitude"] == pytest.approx(0.4)
    assert evidence["threshold"] == pytest.approx(UPPER_STRUCTURE_THRESHOLD)


def test_plus_z_upper_structure_is_observable():
    evidence = measure_upper_structure(_mesh(0.0, 0.4))

    assert (evidence["state"], evidence["axis"], evidence["sign"]) == (
        "observable",
        "Z",
        "+",
    )


def test_plus_x_upper_structure_is_observable():
    evidence = measure_upper_structure(_mesh(0.4, 0.0))

    assert (evidence["state"], evidence["axis"], evidence["sign"]) == (
        "observable",
        "X",
        "+",
    )
    assert evidence["offset_x"] == pytest.approx(0.4)


def test_minus_x_upper_structure_is_observable():
    evidence = measure_upper_structure(_mesh(-0.4, 0.0))

    assert (evidence["state"], evidence["axis"], evidence["sign"]) == (
        "observable",
        "X",
        "-",
    )


def test_centered_upper_structure_is_unobservable():
    evidence = measure_upper_structure(_mesh(0.0, 0.0))

    assert evidence["state"] == "unobservable"
    assert evidence["axis"] is None
    assert evidence["sign"] is None
    assert evidence["magnitude"] < UPPER_STRUCTURE_THRESHOLD


# ---------------------------------------------------------------------------
# 6. threshold boundary
# ---------------------------------------------------------------------------

def test_threshold_boundary_is_deterministic():
    magnitude = measure_upper_structure(_mesh(0.4, 0.0))["magnitude"]

    at_boundary = measure_upper_structure(_mesh(0.4, 0.0), threshold=magnitude)
    just_above = measure_upper_structure(
        _mesh(0.4, 0.0), threshold=magnitude + 1e-12
    )

    # Strictly below the threshold is unobservable; exactly at it is observable.
    assert at_boundary["state"] == "observable"
    assert just_above["state"] == "unobservable"


# ---------------------------------------------------------------------------
# 7 - 8. degenerate horizontal dimensions
# ---------------------------------------------------------------------------

def test_degenerate_x_dimension_is_handled_safely():
    evidence = measure_upper_structure(_degenerate_x_mesh(0.4))

    assert evidence["state"] == "observable"
    assert evidence["axis"] == "Z"
    assert evidence["sign"] == "+"
    assert evidence["offset_x"] == 0.0


def test_degenerate_z_dimension_is_handled_safely():
    evidence = measure_upper_structure(_degenerate_z_mesh(0.4))

    assert evidence["state"] == "observable"
    assert evidence["axis"] == "X"
    assert evidence["sign"] == "+"
    assert evidence["offset_z"] == 0.0


# ---------------------------------------------------------------------------
# 9 - 10. input validation
# ---------------------------------------------------------------------------

def test_empty_vertex_input_is_rejected():
    with pytest.raises(ValueError, match="must not be empty"):
        measure_upper_structure([])


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_vertex_input_is_rejected(bad):
    with pytest.raises(ValueError, match="must be finite"):
        measure_upper_structure([[0.0, 0.0, 0.0], [1.0, bad, 1.0]])


def test_malformed_vertex_input_is_rejected():
    with pytest.raises(ValueError, match="must contain three values"):
        measure_upper_structure([[0.0, 0.0]])
    with pytest.raises(ValueError, match="must be a sequence"):
        measure_upper_structure("0 0 0")
    with pytest.raises(ValueError, match="must be a real number"):
        measure_upper_structure([[True, 0.0, 0.0]])


def test_measurement_does_not_mutate_input_vertices():
    vertices = _mesh(0.3, -0.2)
    before = copy.deepcopy(vertices)

    measure_upper_structure(vertices)

    assert vertices == before


# ---------------------------------------------------------------------------
# 11 - 15. agreement gate
# ---------------------------------------------------------------------------

def test_expected_minus_z_with_measured_minus_z_agrees():
    evidence = measure_upper_structure(_mesh(0.0, -0.4))

    assert (
        evaluate_geometry_agreement(evidence, EXPECTED_GEOMETRY_DIRECTION)
        == GEOMETRY_GATE_AGREED
    )


def test_expected_minus_z_with_measured_plus_z_disagrees():
    evidence = measure_upper_structure(_mesh(0.0, 0.4))

    assert (
        evaluate_geometry_agreement(evidence, EXPECTED_GEOMETRY_DIRECTION)
        == GEOMETRY_GATE_DISAGREED
    )


@pytest.mark.parametrize("offset_x", [0.4, -0.4])
def test_expected_minus_z_with_measured_x_disagrees(offset_x):
    evidence = measure_upper_structure(_mesh(offset_x, 0.0))

    assert (
        evaluate_geometry_agreement(evidence, EXPECTED_GEOMETRY_DIRECTION)
        == GEOMETRY_GATE_DISAGREED
    )


def test_unobservable_evidence_is_not_evaluated():
    evidence = measure_upper_structure(_mesh(0.0, 0.0))

    assert (
        evaluate_geometry_agreement(evidence, EXPECTED_GEOMETRY_DIRECTION)
        == GEOMETRY_GATE_NOT_EVALUATED
    )


def test_ambiguous_evidence_is_not_evaluated():
    assert (
        evaluate_geometry_agreement(AMBIGUOUS_EVIDENCE, EXPECTED_GEOMETRY_DIRECTION)
        == GEOMETRY_GATE_NOT_EVALUATED
    )


def test_gate_rejects_unknown_expected_direction():
    with pytest.raises(ValueError, match="expected_direction must be one of"):
        evaluate_geometry_agreement(_mesh(0.0, -0.4), "-Y")


def test_gate_rejects_malformed_evidence():
    with pytest.raises(ValueError, match="state must be one of"):
        evaluate_geometry_agreement({"state": "maybe"}, "-Z")
    with pytest.raises(ValueError, match="unknown geometry evidence key"):
        evaluate_geometry_agreement(
            dict(AMBIGUOUS_EVIDENCE, sample_ids=["003a85cc"]), "-Z"
        )
    with pytest.raises(ValueError, match="requires a null axis and sign"):
        evaluate_geometry_agreement(
            dict(AMBIGUOUS_EVIDENCE, axis="Z"), "-Z"
        )
    with pytest.raises(ValueError, match="requires an axis in"):
        evaluate_geometry_agreement(
            dict(AMBIGUOUS_EVIDENCE, state="observable", axis="Y", sign="+"), "-Z"
        )


# ---------------------------------------------------------------------------
# 16 - 19. forward contract state transitions
# ---------------------------------------------------------------------------

def _resolve(vertices, expected=EXPECTED_GEOMETRY_DIRECTION):
    evidence = measure_upper_structure(vertices)
    gate = evaluate_geometry_agreement(evidence, expected)

    return resolve_forward_contract(SEATING_RULE, gate, evidence["state"]), gate


def test_agreed_gate_keeps_supported_family_axis():
    resolved, gate = _resolve(_mesh(0.0, -0.4))

    assert gate == GEOMETRY_GATE_AGREED
    assert resolved["status"] == "supported"
    assert resolved["axis"] == "+Z"
    assert resolved["family"] == "seating_and_adult_beds"
    assert resolved["evidence"]["geometry_gate"] == "agreed"
    assert "geometry_agrees_with_family_rule" in resolved["evidence"]["notes"]


def test_disagreed_gate_falls_back_to_unresolved():
    resolved, gate = _resolve(_mesh(0.0, 0.4))

    assert gate == GEOMETRY_GATE_DISAGREED
    assert resolved["status"] == "unresolved"
    assert resolved["axis"] is None
    assert resolved["evidence"]["geometry_gate"] == "disagreed"
    assert (
        "geometry_disagrees_family_rule_rejected"
        in resolved["evidence"]["notes"]
    )


def test_unobservable_geometry_yields_unobservable_state():
    resolved, gate = _resolve(_mesh(0.0, 0.0))

    assert gate == GEOMETRY_GATE_NOT_EVALUATED
    assert resolved["status"] == "unobservable"
    assert resolved["axis"] is None
    assert resolved["evidence"]["geometry_gate"] == "not_evaluated"


def test_ambiguous_geometry_yields_ambiguous_state():
    resolved = resolve_forward_contract(
        SEATING_RULE, GEOMETRY_GATE_NOT_EVALUATED, "ambiguous"
    )

    assert resolved["status"] == "ambiguous"
    assert resolved["axis"] is None
    assert "geometry_ambiguous" in resolved["evidence"]["notes"]


def test_missing_geometry_never_leaves_a_family_rule_supported():
    resolved = resolve_forward_contract(SEATING_RULE)

    assert resolved["status"] == "unresolved"
    assert resolved["axis"] is None
    assert resolved["evidence"]["geometry_gate"] == "not_evaluated"


def test_non_supported_contract_is_returned_unchanged():
    contract = {
        "status": "unresolved",
        "axis": None,
        "axis_frame": "raw_mesh_local_frame",
        "source": "none",
    }

    resolved = resolve_forward_contract(contract, GEOMETRY_GATE_AGREED, "observable")

    assert resolved["status"] == "unresolved"
    assert resolved["axis"] is None


def test_resolver_rejects_unknown_keys_and_bad_gate_values():
    with pytest.raises(ValueError, match="unknown family_contract key"):
        resolve_forward_contract({"status": "supported", "axis": "+Z", "x": 1})
    with pytest.raises(ValueError, match="geometry_gate must be one of"):
        resolve_forward_contract(SEATING_RULE, "maybe")
    with pytest.raises(ValueError, match="geometry_state must be one of"):
        resolve_forward_contract(SEATING_RULE, GEOMETRY_GATE_NOT_EVALUATED, "weird")


# ---------------------------------------------------------------------------
# 20 - 28. transform safety with a resolved contract
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
        "scale": {
            "policy": "no_deformation",
            "scale_xyz": [1.0, 1.0, 1.0],
        },
        "status": {"state": "ready_transform_metadata", "reasons": []},
    }


def _spec(forward_contract=None, candidate=None):
    return build_mesh_transform_spec(
        _loader_result(),
        _candidate() if candidate is None else candidate,
        forward_contract=forward_contract,
    )


def test_resolved_contract_leaves_phi_and_matrices_null():
    resolved, _ = _resolve(_mesh(0.0, -0.4))
    spec = _spec(forward_contract=resolved)

    assert spec["orientation"]["forward_status"] == "supported"
    assert spec["orientation"]["forward_axis"] == "+Z"
    assert spec["orientation"]["intrinsic_yaw_phi_rad"] is None
    assert spec["orientation"]["intrinsic_yaw_status"] == "unresolved"
    assert spec["orientation"]["world_zero_facing_axis"] == "+X"
    assert spec["orientation"]["world_zero_facing_axis_frame"] == (
        "architectos_world_frame"
    )
    assert spec["transform"]["mesh_alignment_matrix"] is None
    assert spec["transform"]["matrix4x4"] is None
    assert spec["transform"]["translation_xyz"] is None


def test_resolved_contract_leaves_status_pending():
    resolved, _ = _resolve(_mesh(0.0, -0.4))
    spec = _spec(forward_contract=resolved)

    assert spec["status"]["state"] == "pending_mesh_alignment"
    assert "mesh_alignment_unresolved" in spec["status"]["reasons"]
    assert spec["rotation_completeness"] == "placement_only"


def test_resolved_contract_does_not_unblock_the_status_gate():
    resolved, _ = _resolve(_mesh(0.0, -0.4))
    candidate = _candidate()
    candidate["status"] = {"state": "pending_asset_match", "reasons": []}

    spec = _spec(forward_contract=resolved, candidate=candidate)

    assert spec["status"]["state"] == "transform_blocked"
    assert spec["orientation"] is None
    assert spec["transform"] is None


def test_resolved_contract_does_not_change_the_scale_path():
    resolved, _ = _resolve(_mesh(0.0, -0.4))
    candidate = _candidate()
    candidate["scale"]["scale_xyz"] = [1.0, 3.0, 1.0]

    spec = _spec(forward_contract=resolved, candidate=candidate)

    assert spec["status"]["state"] == "pending_scale_contract"
    assert spec["transform"]["up_alignment_matrix"] is None
    assert spec["orientation"] is None


def test_resolved_contract_leaves_rz_and_up_component_unchanged():
    resolved, _ = _resolve(_mesh(0.0, -0.4))
    candidate = _candidate()
    candidate["rotation"]["yaw_rad"] = 1.5707963267948966

    spec = _spec(forward_contract=resolved, candidate=candidate)
    transform = spec["transform"]

    assert transform["up_alignment_matrix"] == [
        [1.0, 0.0, 0.0],
        [0.0, 0.0, -1.0],
        [0.0, 1.0, 0.0],
    ]
    assert transform["placement_rotation_matrix"][2] == [0.0, 0.0, 1.0]
    assert transform["placement_rotation_matrix"][0] == pytest.approx(
        [0.0, -1.0, 0.0]
    )
    assert transform["placement_rotation_matrix"][1] == pytest.approx(
        [1.0, 0.0, 0.0]
    )


def test_gate_module_has_no_filesystem_or_family_detection():
    import core.asset.forward_geometry_gate as gate_module

    source = __import__("pathlib").Path(gate_module.__file__).read_text(
        encoding="utf-8"
    )

    assert "open(" not in source
    assert "category" not in source
    assert "FurnitureAdapter" not in source
    # The gate never populates the intrinsic yaw field.
    assert "intrinsic_yaw_phi_rad" not in source
