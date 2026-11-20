"""Focused tests for the declarative mesh transform spec builder (Phase 3D-L)."""

import copy
import math
from pathlib import Path

import pytest

from core.asset.mesh_transform_spec import (
    TRANSFORM_ORDER,
    _compose_final_affine,
    _compose_mesh_alignment_matrix,
    _cross_check_phi_result,
    _matmul3,
    _matvec3,
    build_mesh_transform_spec,
)

BASIS_VERSION = "diffuscene_y_up_to_architectos_z_up_v1"


def _loader_result(**overrides):
    result = {
        "format_version": "raw_obj_mesh_v1",
        "source": "3D-FUTURE",
        "model_id": "model-a",
        "raw_model_path": "D:/dataset/part1/model-a/raw_model.obj",
        "mesh_frame": "raw_mesh_local_frame",
        "geometry": {
            "index_base": 0,
            "vertices_xyz": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [0.0, 0.0, 0.0]],
            "faces": [[0, 1, 2]],
        },
        "bounds": {
            "min_xyz": [0.0, 0.0, 0.0],
            "max_xyz": [4.0, 5.0, 6.0],
            "dims_xyz": [4.0, 5.0, 6.0],
            "center_xyz": [2.0, 2.5, 3.0],
        },
        "counts": {
            "vertices": 3,
            "faces": 1,
            "face_degree_max": 3,
            "ignored_lines": 0,
        },
        "pivot": {
            "mesh_origin_xyz": [0.0, 0.0, 0.0],
            "bbox_center_xyz": [2.0, 2.5, 3.0],
        },
        "materials": {"mtllib": None, "usemtl": [], "groups": []},
        "validation": {"reference": "absent"},
        "warnings": [],
        "status": {"state": "mesh_loaded_valid", "reasons": []},
    }
    result.update(overrides)

    return result


def _candidate(**overrides):
    candidate = {
        "type": "furniture_asset_placement",
        "source_engine": "DiffuScene",
        "slot": 3,
        "category": "chair",
        "mesh_source": {
            "source": "3D-FUTURE",
            "model_id": "model-a",
            "raw_model_path": "D:/dataset/part1/model-a/raw_model.obj",
        },
        "position": {
            "source_center_xyz": [0.0, 2.0, 3.0],
            "room_local_xyz": [1.0, -3.0, 2.0],
            "world_xyz": None,
            "basis": BASIS_VERSION,
        },
        "rotation": {
            "source_y_rad": 0.0,
            "yaw_rad": 0.0,
            "axis": "+Z",
            "mapping_status": "resolved",
            "mesh_forward_status": "unresolved",
        },
        "dimensions": {
            "source_asset_xyz": [4.0, 5.0, 6.0],
            "target_diffuscene_xyz": [4.0, 5.0, 6.0],
            "axis_mapping_status": "unresolved",
            "fit_status": "fit_pending_axis_mapping",
        },
        "units": {"status": "assumed_meters"},
        "scale": {
            "policy": "no_deformation",
            "scale_xyz": [1.0, 1.0, 1.0],
            "instance_scale_status": "unresolved_training_data_convention",
        },
        "anchor": {"support_status": "unresolved", "contact_z": None},
        "status": {"state": "ready_transform_metadata", "reasons": []},
    }
    candidate.update(overrides)

    return candidate


def _with_yaw(yaw):
    candidate = _candidate()
    candidate["rotation"]["yaw_rad"] = yaw
    candidate["rotation"]["source_y_rad"] = yaw

    return candidate


def _apply(matrix, vector):
    return [sum(row[i] * vector[i] for i in range(3)) for row in matrix]


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


def _build(mesh=None, candidate=None):
    return build_mesh_transform_spec(
        _loader_result() if mesh is None else mesh,
        _candidate() if candidate is None else candidate,
    )


# ---------------------------------------------------------------------------
# 1 + 2. input immutability and no geometry in the output
# ---------------------------------------------------------------------------

def test_loader_input_vertices_are_not_mutated():
    mesh = _loader_result()
    candidate = _candidate()
    mesh_before = copy.deepcopy(mesh)
    candidate_before = copy.deepcopy(candidate)
    vertices_identity = mesh["geometry"]["vertices_xyz"]

    build_mesh_transform_spec(mesh, candidate)

    assert mesh == mesh_before
    assert candidate == candidate_before
    assert mesh["geometry"]["vertices_xyz"] is vertices_identity


def test_spec_contains_no_transformed_geometry():
    spec = _build()

    keys = _all_keys(spec)

    assert "vertices_xyz" not in keys
    assert "faces" not in keys
    assert "geometry" not in keys
    assert "bounds_after" not in keys


# ---------------------------------------------------------------------------
# 3 + 4. basis is not reapplied
# ---------------------------------------------------------------------------

def test_placement_basis_is_not_reapplied():
    spec = _build()

    assert spec["pivot"]["target_bbox_center_xyz"] == [1.0, -3.0, 2.0]
    # Applying B a second time would yield [1.0, -2.0, -3.0].
    assert spec["pivot"]["target_bbox_center_xyz"] != [1.0, -2.0, -3.0]
    assert spec["source_center_is_basis_mapped"] is True
    assert spec["basis"] == {"version": BASIS_VERSION, "already_applied": True}


def test_room_local_xyz_is_copied_directly():
    candidate = _candidate()
    candidate["position"]["room_local_xyz"] = [7.5, -0.25, 12.0]

    spec = _build(candidate=candidate)

    assert spec["pivot"]["target_bbox_center_xyz"] == [7.5, -0.25, 12.0]


# ---------------------------------------------------------------------------
# 5, 6, 7. placement rotation
# ---------------------------------------------------------------------------

def test_zero_yaw_gives_identity_rotation():
    spec = _build(candidate=_with_yaw(0.0))

    assert spec["transform"]["placement_rotation_matrix"] == [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]


def test_positive_quarter_turn_maps_plus_x_to_plus_y():
    spec = _build(candidate=_with_yaw(math.pi / 2))
    matrix = spec["transform"]["placement_rotation_matrix"]

    assert _apply(matrix, [1.0, 0.0, 0.0]) == pytest.approx([0.0, 1.0, 0.0])
    assert _apply(matrix, [0.0, 1.0, 0.0]) == pytest.approx([-1.0, 0.0, 0.0])


def test_negative_quarter_turn_maps_plus_x_to_minus_y():
    spec = _build(candidate=_with_yaw(-math.pi / 2))
    matrix = spec["transform"]["placement_rotation_matrix"]

    assert _apply(matrix, [1.0, 0.0, 0.0]) == pytest.approx([0.0, -1.0, 0.0])
    assert _apply(matrix, [0.0, 1.0, 0.0]) == pytest.approx([1.0, 0.0, 0.0])


def test_rotation_axis_is_the_world_vertical():
    spec = _build(candidate=_with_yaw(0.7))
    matrix = spec["transform"]["placement_rotation_matrix"]

    assert matrix[2] == [0.0, 0.0, 1.0]
    assert matrix[0][2] == 0.0
    assert matrix[1][2] == 0.0


# ---------------------------------------------------------------------------
# 8, 9, 10. unresolved alignment stays null
# ---------------------------------------------------------------------------

def test_unresolved_alignment_and_final_transform_stay_null():
    transform = _build()["transform"]

    assert transform["mesh_alignment_matrix"] is None
    assert transform["translation_xyz"] is None
    assert transform["matrix4x4"] is None


def test_alignment_is_never_substituted_with_identity():
    transform = _build()["transform"]

    assert transform["mesh_alignment_matrix"] != [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]


def test_transform_order_is_the_canonical_order():
    assert _build()["transform"]["order"] == list(TRANSFORM_ORDER)


# ---------------------------------------------------------------------------
# 11. scale stays identity
# ---------------------------------------------------------------------------

def test_scale_remains_identity():
    spec = _build()

    assert spec["transform"]["scale_xyz"] == [1.0, 1.0, 1.0]
    assert spec["status"]["state"] == "pending_mesh_alignment"


@pytest.mark.parametrize(
    "scale_xyz",
    [[2.0, 1.0, 1.0], [1.0, 1.0, 0.5], [0.999, 1.0, 1.0]],
)
def test_non_identity_scale_blocks_the_transform(scale_xyz):
    candidate = _candidate()
    candidate["scale"]["scale_xyz"] = scale_xyz

    spec = _build(candidate=candidate)

    assert spec["status"]["state"] == "pending_scale_contract"
    assert spec["status"]["reasons"] == ["scale_not_identity"]
    # No transform is calculated at all for a non-identity scale.
    assert spec["transform"]["placement_rotation_matrix"] is None
    assert spec["transform"]["scale_xyz"] == scale_xyz
    assert spec["transform"]["translation_xyz"] is None
    assert spec["transform"]["matrix4x4"] is None


def test_integer_identity_scale_is_accepted():
    candidate = _candidate()
    candidate["scale"]["scale_xyz"] = [1, 1, 1]

    spec = _build(candidate=candidate)

    assert spec["status"]["state"] == "pending_mesh_alignment"
    assert spec["transform"]["scale_xyz"] == [1.0, 1.0, 1.0]


# ---------------------------------------------------------------------------
# 12. OBJ origin vs bbox center
# ---------------------------------------------------------------------------

def test_obj_origin_is_kept_separate_from_bbox_center():
    spec = _build()

    assert spec["pivot"]["mesh_origin_xyz"] == [0.0, 0.0, 0.0]
    assert spec["pivot"]["local_bbox_center_xyz"] == [2.0, 2.5, 3.0]
    assert spec["pivot"]["mesh_origin_xyz"] != spec["pivot"]["local_bbox_center_xyz"]
    assert spec["pivot"]["target_bbox_center_xyz"] != spec["pivot"]["mesh_origin_xyz"]


def test_non_zero_obj_origin_is_preserved_verbatim():
    mesh = _loader_result()
    mesh["pivot"]["mesh_origin_xyz"] = [0.5, -1.5, 2.5]

    spec = _build(mesh=mesh)

    assert spec["pivot"]["mesh_origin_xyz"] == [0.5, -1.5, 2.5]


# ---------------------------------------------------------------------------
# 13. invalid loader state blocks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "state",
    ["mesh_empty", "mesh_nonfinite_vertices", "mesh_invalid_faces", "mesh_parse_failed"],
)
def test_invalid_loader_state_blocks_the_spec(state):
    mesh = _loader_result()
    mesh["status"] = {"state": state, "reasons": []}

    spec = _build(mesh=mesh)

    assert spec["status"]["state"] == "transform_blocked"
    assert spec["status"]["reasons"] == [f"loader_state_not_valid:{state}"]
    assert spec["transform"] is None
    assert spec["pivot"] is None
    assert spec["bounds_before"] is None


def test_wrong_mesh_frame_blocks_the_spec():
    mesh = _loader_result()
    mesh["mesh_frame"] = "architectos_world_frame"

    spec = _build(mesh=mesh)

    assert spec["status"]["state"] == "transform_blocked"
    assert "mesh_frame_not_raw_mesh_local_frame" in spec["status"]["reasons"]


def test_wrong_index_base_blocks_the_spec():
    mesh = _loader_result()
    mesh["geometry"]["index_base"] = 1

    spec = _build(mesh=mesh)

    assert spec["status"]["state"] == "transform_blocked"
    assert "geometry_index_base_not_zero" in spec["status"]["reasons"]


def test_missing_pivot_blocks_the_spec():
    mesh = _loader_result()
    mesh["pivot"] = None

    spec = _build(mesh=mesh)

    assert spec["status"]["state"] == "transform_blocked"
    assert "loader_pivot_missing" in spec["status"]["reasons"]


def test_missing_bounds_blocks_the_spec():
    mesh = _loader_result()
    mesh["bounds"] = None

    spec = _build(mesh=mesh)

    assert spec["status"]["state"] == "transform_blocked"
    assert "loader_bounds_missing" in spec["status"]["reasons"]


def test_wrong_rotation_axis_blocks_the_spec():
    candidate = _candidate()
    candidate["rotation"]["axis"] = "+Y"

    spec = _build(candidate=candidate)

    assert spec["status"]["state"] == "transform_blocked"
    assert "rotation_axis_not_plus_z" in spec["status"]["reasons"]


def test_missing_scale_blocks_the_spec():
    candidate = _candidate()
    candidate["scale"]["scale_xyz"] = None

    spec = _build(candidate=candidate)

    assert spec["status"]["state"] == "transform_blocked"
    assert any(reason.startswith("invalid_scale:") for reason in spec["status"]["reasons"])


# ---------------------------------------------------------------------------
# placement candidate status gate
# ---------------------------------------------------------------------------

def test_valid_placement_candidate_status_is_accepted():
    candidate = _candidate()
    assert candidate["status"]["state"] == "ready_transform_metadata"

    spec = _build(candidate=candidate)

    assert spec["status"]["state"] == "pending_mesh_alignment"
    assert not any(
        reason.startswith("placement_candidate_")
        for reason in spec["status"]["reasons"]
    )


@pytest.mark.parametrize(
    "status",
    [None, "ready_transform_metadata", [], 0],
    ids=["none", "bare-string", "list", "int"],
)
def test_missing_placement_candidate_status_blocks(status):
    candidate = _candidate()
    candidate["status"] = status

    spec = _build(candidate=candidate)

    assert spec["status"]["state"] == "transform_blocked"
    assert spec["status"]["reasons"] == ["placement_candidate_status_missing"]
    assert spec["transform"] is None
    assert spec["pivot"] is None
    assert spec["bounds_before"] is None


@pytest.mark.parametrize(
    "status",
    [{}, {"reasons": []}, {"state": None}],
    ids=["empty", "no-state-key", "null-state"],
)
def test_placement_candidate_status_without_state_blocks(status):
    candidate = _candidate()
    candidate["status"] = status

    spec = _build(candidate=candidate)

    assert spec["status"]["state"] == "transform_blocked"
    assert spec["status"]["reasons"] == [
        "placement_candidate_status_state_missing"
    ]


@pytest.mark.parametrize(
    "state",
    [
        "pending_asset_match",
        "pending_raw_model_path",
        "invalid_source_position",
        "invalid_source_rotation",
        "invalid_source_dimensions",
    ],
)
def test_non_ready_placement_candidate_state_blocks(state):
    candidate = _candidate()
    candidate["status"] = {"state": state, "reasons": []}

    spec = _build(candidate=candidate)

    assert spec["status"]["state"] == "transform_blocked"
    assert spec["status"]["reasons"] == [
        f"placement_candidate_state_not_transform_ready:{state}"
    ]
    assert spec["transform"] is None


# ---------------------------------------------------------------------------
# 14. non-finite inputs block
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_placement_center_blocks(bad):
    candidate = _candidate()
    candidate["position"]["room_local_xyz"] = [1.0, bad, 2.0]

    spec = _build(candidate=candidate)

    assert spec["status"]["state"] == "transform_blocked"
    assert any(
        reason.startswith("invalid_placement_center:")
        for reason in spec["status"]["reasons"]
    )


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_yaw_blocks(bad):
    spec = _build(candidate=_with_yaw(bad))

    assert spec["status"]["state"] == "transform_blocked"
    assert any(
        reason.startswith("invalid_placement_rotation:")
        for reason in spec["status"]["reasons"]
    )


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_bbox_center_blocks(bad):
    mesh = _loader_result()
    mesh["pivot"]["bbox_center_xyz"] = [1.0, bad, 2.0]

    spec = _build(mesh=mesh)

    assert spec["status"]["state"] == "transform_blocked"
    assert any(
        reason.startswith("invalid_pivot:") for reason in spec["status"]["reasons"]
    )


def test_missing_placement_center_blocks():
    candidate = _candidate()
    candidate["position"]["room_local_xyz"] = None

    spec = _build(candidate=candidate)

    assert spec["status"]["state"] == "transform_blocked"


def test_non_finite_world_reference_blocks():
    candidate = _candidate()
    candidate["position"]["world_xyz"] = [1.0, float("nan"), 3.0]

    spec = _build(candidate=candidate)

    assert spec["status"]["state"] == "transform_blocked"
    assert any(
        reason.startswith("invalid_world_reference:")
        for reason in spec["status"]["reasons"]
    )


def test_non_mapping_arguments_raise():
    with pytest.raises(ValueError, match="mesh_result must be a mapping"):
        build_mesh_transform_spec(None, _candidate())
    with pytest.raises(ValueError, match="placement_candidate must be a mapping"):
        build_mesh_transform_spec(_loader_result(), None)


# ---------------------------------------------------------------------------
# 15. determinism
# ---------------------------------------------------------------------------

def test_spec_is_deterministic():
    first = _build(candidate=_with_yaw(1.2345))
    second = _build(candidate=_with_yaw(1.2345))

    assert first == second


# ---------------------------------------------------------------------------
# 16. no filesystem access
# ---------------------------------------------------------------------------

def test_builder_performs_no_filesystem_access(monkeypatch):
    import builtins

    def _forbidden(*args, **kwargs):
        raise AssertionError("the spec builder must not touch the filesystem")

    monkeypatch.setattr(builtins, "open", _forbidden)

    spec = _build()

    assert spec["status"]["state"] == "pending_mesh_alignment"


# ---------------------------------------------------------------------------
# world reference handling
# ---------------------------------------------------------------------------

def test_world_reference_is_preserved_but_not_authoritative():
    candidate = _candidate()
    candidate["position"]["world_xyz"] = [11.0, 17.0, 2.0]

    spec = _build(candidate=candidate)

    assert spec["world_reference"] == {"world_xyz": [11.0, 17.0, 2.0], "authoritative": False}
    # room_local_xyz stays the authoritative target and is unaltered.
    assert spec["pivot"]["target_bbox_center_xyz"] == [1.0, -3.0, 2.0]
    assert "world_reference_recorded_not_applied" in spec["status"]["reasons"]


def test_absent_world_reference_is_null():
    spec = _build()

    assert spec["world_reference"] == {"world_xyz": None, "authoritative": False}


# ---------------------------------------------------------------------------
# Phase 3D-P: verified up-axis metadata + forward-unresolved contract
# ---------------------------------------------------------------------------

UP_ALIGNMENT = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]
IDENTITY_MATRIX = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def test_verified_raw_y_up_metadata_is_emitted():
    orientation = _build()["orientation"]

    assert orientation["raw_mesh_up_axis"] == "+Y"
    assert orientation["raw_mesh_up_sign"] == "+"
    assert orientation["raw_mesh_up_status"] == "verified"
    assert orientation["world_up_axis"] == "+Z"
    assert orientation["up_alignment_status"] == "verified"


def test_verified_up_alignment_matrix_maps_mesh_y_onto_world_z():
    transform = _build()["transform"]

    assert transform["up_alignment_matrix"] == UP_ALIGNMENT
    assert _apply(transform["up_alignment_matrix"], [0.0, 1.0, 0.0]) == pytest.approx(
        [0.0, 0.0, 1.0]
    )
    assert _apply(transform["up_alignment_matrix"], [1.0, 0.0, 0.0]) == pytest.approx(
        [1.0, 0.0, 0.0]
    )


def test_forward_axis_remains_null():
    orientation = _build()["orientation"]

    assert orientation["forward_axis"] is None
    assert orientation["forward_status"] == "unresolved"


def test_world_zero_facing_axis_is_declared():
    orientation = _build()["orientation"]

    assert orientation["world_zero_facing_axis"] == "+X"
    assert orientation["world_zero_facing_axis_frame"] == (
        "architectos_world_frame"
    )


def test_legacy_zero_facing_fields_are_removed():
    orientation = _build()["orientation"]

    assert "zero_facing_axis" not in orientation
    assert "zero_facing_status" not in orientation


def test_intrinsic_phi_remains_null():
    orientation = _build()["orientation"]

    assert orientation["intrinsic_yaw_phi_rad"] is None
    assert orientation["intrinsic_yaw_status"] == "unresolved"


def test_full_mesh_alignment_matrix_remains_null():
    transform = _build()["transform"]

    assert transform["mesh_alignment_matrix"] is None
    assert _build()["orientation"]["full_alignment_status"] == "unresolved_forward"


def test_final_executable_matrix_remains_null():
    transform = _build()["transform"]

    assert transform["matrix4x4"] is None
    assert transform["translation_xyz"] is None


def test_verified_up_plus_unresolved_forward_stays_pending():
    spec = _build()

    # Verified up-axis does NOT make the spec transform-ready.
    assert spec["status"]["state"] == "pending_mesh_alignment"
    assert "mesh_alignment_unresolved" in spec["status"]["reasons"]
    assert spec["rotation_completeness"] == "placement_only"


def test_no_implicit_identity_or_phi_zero_substitution():
    spec = _build()
    orientation = spec["orientation"]
    transform = spec["transform"]

    # No default raw forward axis; the world target is a declared constant.
    assert orientation["forward_axis"] != "+X"
    assert orientation["forward_axis_frame"] == "raw_mesh_local_frame"
    assert orientation["world_zero_facing_axis"] == "+X"
    assert orientation["world_zero_facing_axis_frame"] == (
        "architectos_world_frame"
    )
    # No default phi.
    assert orientation["intrinsic_yaw_phi_rad"] is None
    assert orientation["intrinsic_yaw_phi_rad"] != 0.0
    # The full alignment is neither identity nor the partial up component.
    assert transform["mesh_alignment_matrix"] is None
    assert transform["mesh_alignment_matrix"] != IDENTITY_MATRIX
    assert transform["mesh_alignment_matrix"] != UP_ALIGNMENT
    assert transform["matrix4x4"] is None


def test_forward_evidence_is_compact_and_non_executable():
    evidence = _build()["orientation"]["evidence"]

    assert evidence["state"] == "unresolved"
    assert evidence["dataset_wide_constant"] is False
    assert evidence["numeric_phi_verified"] is False
    assert evidence["notes"] == [
        "dataset_wide_forward_constant_not_verified",
        "seating_and_bed_plus_z_candidate_supported_but_unverified",
        "symmetric_assets_may_be_forward_unobservable",
    ]
    # No sample model_ids or audit payload leaked into runtime state.
    assert not any("003a85cc" in note for note in evidence["notes"])
    assert all(isinstance(note, str) for note in evidence["notes"])


def test_placement_candidate_status_gate_still_blocks_and_withholds_orientation():
    candidate = _candidate()
    candidate["status"] = {"state": "pending_asset_match", "reasons": []}

    spec = _build(candidate=candidate)

    assert spec["status"]["state"] == "transform_blocked"
    assert spec["status"]["reasons"] == [
        "placement_candidate_state_not_transform_ready:pending_asset_match"
    ]
    assert spec["orientation"] is None
    assert spec["transform"] is None


def test_non_identity_scale_behaviour_unchanged_and_withholds_up_component():
    candidate = _candidate()
    candidate["scale"]["scale_xyz"] = [2.0, 1.0, 1.0]

    spec = _build(candidate=candidate)

    assert spec["status"]["state"] == "pending_scale_contract"
    assert spec["status"]["reasons"] == ["scale_not_identity"]
    assert spec["transform"]["scale_xyz"] == [2.0, 1.0, 1.0]
    # No transform component is calculated on this path.
    assert spec["transform"]["up_alignment_matrix"] is None
    assert spec["transform"]["mesh_alignment_matrix"] is None
    assert spec["transform"]["placement_rotation_matrix"] is None
    assert spec["orientation"] is None


def test_rz_placement_rotation_unchanged_by_up_component():
    spec = _build(candidate=_with_yaw(math.pi / 2))
    transform = spec["transform"]

    expected = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    for index in range(3):
        assert transform["placement_rotation_matrix"][index] == pytest.approx(
            expected[index]
        )
    # Rz is about world +Z; the up component does not alter it.
    assert transform["placement_rotation_matrix"][2] == [0.0, 0.0, 1.0]
    assert _apply(transform["placement_rotation_matrix"], [1.0, 0.0, 0.0]) == pytest.approx(
        [0.0, 1.0, 0.0]
    )


# ---------------------------------------------------------------------------
# Phase 3D-R: non-executable forward contract
# ---------------------------------------------------------------------------

SUPPORTED_FORWARD = {
    "status": "supported",
    "axis": "+Z",
    "source": "family_rule",
    "family": "seating_and_adult_beds",
    "evidence": {
        "rule_id": "forward_family_rule_v1",
        "geometry_gate": "agreed",
        "agreement": 0.95,
        "notes": ["seating_and_adult_beds_only", "kids_and_bunk_beds_excluded"],
    },
}


def _with_frame(forward_contract):
    """Inject the required axis_frame declaration.

    Phase 3D-Y made ``axis_frame`` a required contract key. The tests in this
    file target other validation paths (status, axis, family, evidence), so the
    frame declaration is supplied here to keep them focused. Frame validation
    itself is covered explicitly in tests/test_mesh_alignment_resolver.py and by
    test_contract_without_axis_frame_is_rejected below.
    """

    if not isinstance(forward_contract, dict):
        return forward_contract
    contract = dict(forward_contract)
    contract.setdefault("axis_frame", "raw_mesh_local_frame")

    return contract


def _forward_spec(forward_contract=None, candidate=None, phi_result=None):
    return build_mesh_transform_spec(
        _loader_result(),
        _candidate() if candidate is None else candidate,
        forward_contract=_with_frame(forward_contract),
        phi_result=phi_result,
    )


def test_default_forward_remains_unresolved():
    orientation = _build()["orientation"]

    assert orientation["forward_axis"] is None
    assert orientation["forward_status"] == "unresolved"
    assert orientation["forward_source"] == "none"
    assert orientation["forward_family"] is None
    assert orientation["forward_evidence"] == {
        "rule_id": None,
        "geometry_gate": "not_evaluated",
        "agreement": None,
        "notes": [],
    }


def test_supported_family_rule_metadata_is_representable():
    orientation = _forward_spec(SUPPORTED_FORWARD)["orientation"]

    assert orientation["forward_axis"] == "+Z"
    assert orientation["forward_status"] == "supported"
    assert orientation["forward_source"] == "family_rule"
    assert orientation["forward_family"] == "seating_and_adult_beds"
    assert orientation["forward_evidence"] == {
        "rule_id": "forward_family_rule_v1",
        "geometry_gate": "agreed",
        "agreement": pytest.approx(0.95),
        "notes": ["seating_and_adult_beds_only", "kids_and_bunk_beds_excluded"],
    }


def test_supported_forward_contract_does_not_make_the_spec_executable():
    spec = _forward_spec(SUPPORTED_FORWARD)

    assert spec["status"]["state"] == "pending_mesh_alignment"
    assert spec["transform"]["mesh_alignment_matrix"] is None
    assert spec["transform"]["matrix4x4"] is None
    assert spec["transform"]["translation_xyz"] is None
    assert spec["orientation"]["intrinsic_yaw_phi_rad"] is None


@pytest.mark.parametrize("status", ["unresolved", "unobservable", "ambiguous", "unsupported"])
def test_non_observable_states_require_null_axis(status):
    assert _forward_spec({"status": status})["orientation"]["forward_status"] == status

    with pytest.raises(ValueError, match="requires forward_axis to be null"):
        _forward_spec({"status": status, "axis": "+Z"})


def test_supported_requires_a_real_axis():
    with pytest.raises(ValueError, match="requires a concrete forward axis"):
        _forward_spec({"status": "supported", "source": "family_rule", "family": "seating"})


@pytest.mark.parametrize("axis", ["+Y", "forward", "X", ""])
def test_supported_rejects_non_contract_axes(axis):
    with pytest.raises(ValueError, match="forward_axis must be one of"):
        _forward_spec({"status": "supported", "axis": axis, "source": "geometry_measured"})


def test_supported_family_rule_requires_a_family_id():
    with pytest.raises(ValueError, match="requires a non-null forward_family"):
        _forward_spec({"status": "supported", "axis": "+Z", "source": "family_rule"})


def test_family_rule_must_not_be_marked_verified():
    with pytest.raises(ValueError, match="must not be marked 'verified'"):
        _forward_spec(
            {
                "status": "verified",
                "axis": "+Z",
                "source": "family_rule",
                "family": "seating_and_adult_beds",
            }
        )


def test_source_none_must_not_carry_an_axis():
    with pytest.raises(ValueError, match="must not carry a forward axis"):
        _forward_spec({"status": "supported", "axis": "+Z", "source": "none"})


def test_verified_is_never_assigned_by_default():
    orientation = _build()["orientation"]

    assert orientation["forward_status"] != "verified"
    assert orientation["raw_mesh_up_status"] == "verified"
    assert orientation["forward_evidence"]["geometry_gate"] == "not_evaluated"


def test_forward_contract_rejects_unknown_keys_and_bad_shape():
    with pytest.raises(ValueError, match="unknown forward_contract key"):
        _forward_spec({"status": "unresolved", "confidence": 0.9})
    with pytest.raises(ValueError, match="forward_contract must be a mapping"):
        _forward_spec("supported")


def test_forward_evidence_rejects_audit_payload():
    with pytest.raises(ValueError, match="unknown forward evidence key"):
        _forward_spec(
            {"status": "unresolved", "evidence": {"sample_model_ids": ["003a85cc"]}}
        )
    with pytest.raises(ValueError, match="must be a list of strings"):
        _forward_spec({"status": "unresolved", "evidence": {"notes": "a long report"}})
    with pytest.raises(ValueError, match="must stay compact"):
        _forward_spec({"status": "unresolved", "evidence": {"notes": ["x" * 400]}})
    with pytest.raises(ValueError, match="ratio within"):
        _forward_spec({"status": "unresolved", "evidence": {"agreement": 38}})


def test_forward_evidence_rejects_unknown_gate_state():
    with pytest.raises(ValueError, match="geometry_gate must be one of"):
        _forward_spec({"status": "unresolved", "evidence": {"geometry_gate": "maybe"}})


def test_phi_and_full_alignment_stay_null_with_a_supported_contract():
    spec = _forward_spec(SUPPORTED_FORWARD)
    orientation = spec["orientation"]
    transform = spec["transform"]

    assert orientation["intrinsic_yaw_phi_rad"] is None
    assert orientation["intrinsic_yaw_status"] == "unresolved"
    assert orientation["world_zero_facing_axis"] == "+X"
    assert orientation["world_zero_facing_axis_frame"] == (
        "architectos_world_frame"
    )
    assert orientation["full_alignment_status"] == "unresolved_forward"
    assert transform["mesh_alignment_matrix"] is None
    assert transform["matrix4x4"] is None
    assert transform["translation_xyz"] is None


def test_raw_and_world_facing_concepts_stay_separate():
    default = _build()["orientation"]
    supported = _forward_spec(SUPPORTED_FORWARD)["orientation"]

    # Raw semantic facing is null while forward is unresolved, and is declared
    # to live in the raw mesh frame.
    assert default["forward_axis"] is None
    assert default["forward_axis_frame"] == "raw_mesh_local_frame"

    # A supported forward contract populates ONLY the raw-facing field.
    assert supported["forward_axis"] == "+Z"
    assert supported["forward_axis_frame"] == "raw_mesh_local_frame"

    # The world target is a separate value in a separate frame, and a raw axis
    # must never leak into it.
    assert supported["world_zero_facing_axis"] == "+X"
    assert supported["world_zero_facing_axis_frame"] == (
        "architectos_world_frame"
    )
    assert supported["world_zero_facing_axis"] != supported["forward_axis"]


def test_supported_forward_contract_does_not_unblock_status_gate():
    candidate = _candidate()
    candidate["status"] = {"state": "pending_raw_model_path", "reasons": []}

    spec = _forward_spec(SUPPORTED_FORWARD, candidate=candidate)

    assert spec["status"]["state"] == "transform_blocked"
    assert spec["status"]["reasons"] == [
        "placement_candidate_state_not_transform_ready:pending_raw_model_path"
    ]
    assert spec["orientation"] is None
    assert spec["transform"] is None


def test_supported_forward_contract_does_not_change_scale_path():
    candidate = _candidate()
    candidate["scale"]["scale_xyz"] = [1.0, 2.0, 1.0]

    spec = _forward_spec(SUPPORTED_FORWARD, candidate=candidate)

    assert spec["status"]["state"] == "pending_scale_contract"
    assert spec["status"]["reasons"] == ["scale_not_identity"]
    assert spec["transform"]["scale_xyz"] == [1.0, 2.0, 1.0]
    assert spec["transform"]["up_alignment_matrix"] is None
    assert spec["orientation"] is None


def test_supported_forward_contract_does_not_alter_rz_or_up_component():
    spec = _forward_spec(SUPPORTED_FORWARD, candidate=_with_yaw(math.pi / 2))
    transform = spec["transform"]

    assert transform["up_alignment_matrix"] == UP_ALIGNMENT
    expected = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    for index in range(3):
        assert transform["placement_rotation_matrix"][index] == pytest.approx(
            expected[index]
        )
    assert spec["rotation_completeness"] == "placement_only"


def test_forward_contract_does_not_leak_into_geometry_or_bounds():
    spec = _forward_spec(SUPPORTED_FORWARD)

    assert "vertices_xyz" not in _all_keys(spec)
    assert "faces" not in _all_keys(spec)
    assert spec["pivot"]["local_bbox_center_xyz"] == [2.0, 2.5, 3.0]
    assert spec["bounds_before"]["dims_xyz"] == [4.0, 5.0, 6.0]


def test_contract_without_axis_frame_is_rejected():
    with pytest.raises(ValueError, match="is missing: axis_frame"):
        build_mesh_transform_spec(
            _loader_result(),
            _candidate(),
            forward_contract={"status": "unresolved"},
        )


def test_contract_with_wrong_axis_frame_is_rejected():
    with pytest.raises(ValueError, match="axis_frame must be"):
        build_mesh_transform_spec(
            _loader_result(),
            _candidate(),
            forward_contract={
                "status": "unresolved",
                "axis_frame": "architectos_world_frame",
            },
        )


def test_orientation_declares_the_forward_axis_frame():
    orientation = _build()["orientation"]

    assert orientation["forward_axis_frame"] == "raw_mesh_local_frame"
    assert orientation["raw_mesh_up_axis"] == "+Y"
    assert orientation["world_up_axis"] == "+Z"


def test_default_unresolved_contract_carries_the_frame_tag():
    spec = build_mesh_transform_spec(_loader_result(), _candidate())

    assert spec["orientation"]["forward_status"] == "unresolved"
    assert spec["orientation"]["forward_axis_frame"] == "raw_mesh_local_frame"


# ---------------------------------------------------------------------------
# schema shape
# ---------------------------------------------------------------------------

def test_spec_reports_frames_and_mesh_reference():
    spec = _build()

    assert spec["format_version"] == "mesh_transform_v1"
    assert spec["source_mesh_frame"] == "raw_mesh_local_frame"
    assert spec["destination_frame"] == "architectos_world_frame"
    assert spec["mesh_reference"] == {
        "model_id": "model-a",
        "raw_model_path": "D:/dataset/part1/model-a/raw_model.obj",
    }
    assert spec["rotation_completeness"] == "placement_only"
    assert spec["bounds_after_partial"] is None
    assert spec["bounds_before"]["dims_xyz"] == [4.0, 5.0, 6.0]


# ---------------------------------------------------------------------------
# ONE integration-style test using the already validated real loader output
# ---------------------------------------------------------------------------

REAL_ROOT = Path(r"D:\AI_Architecture_Lab\3D-FUTURE-model")
REAL_MODEL_ID = "27059911-89f4-3e78-a511-4c9b8cf51fb3"
REAL_OBJ = REAL_ROOT / "3D-FUTURE-model-part1" / REAL_MODEL_ID / "raw_model.obj"


@pytest.mark.skipif(not REAL_OBJ.is_file(), reason="real 3D-FUTURE asset absent")
def test_spec_from_real_loader_output():
    from core.asset.raw_obj_loader import load_raw_obj

    mesh = load_raw_obj(
        {
            "source": "3D-FUTURE",
            "model_id": REAL_MODEL_ID,
            "raw_model_path": str(REAL_OBJ),
        },
        allowed_roots=[REAL_ROOT],
    )
    assert mesh["status"]["state"] == "mesh_loaded_valid"

    candidate = _candidate()
    candidate["mesh_source"] = {
        "source": "3D-FUTURE",
        "model_id": REAL_MODEL_ID,
        "raw_model_path": str(REAL_OBJ),
    }

    spec = build_mesh_transform_spec(mesh, candidate)

    assert spec["status"]["state"] == "pending_mesh_alignment"
    assert spec["mesh_reference"]["model_id"] == REAL_MODEL_ID
    assert spec["pivot"]["mesh_origin_xyz"] == [0.0, 0.0, 0.0]
    assert spec["pivot"]["local_bbox_center_xyz"] == pytest.approx(
        [0.002331, 0.4322, 0.0093535], abs=1e-6
    )
    assert spec["pivot"]["local_bbox_center_xyz"] != spec["pivot"]["mesh_origin_xyz"]
    assert spec["transform"]["mesh_alignment_matrix"] is None
    assert spec["transform"]["translation_xyz"] is None
    assert spec["transform"]["matrix4x4"] is None
    assert "vertices_xyz" not in _all_keys(spec)


# ---------------------------------------------------------------------------
# Phase 3D-AB: phi_result injection
# ---------------------------------------------------------------------------

def _phi_result(**overrides):
    result = {
        "phi_status": "resolved",
        "phi_rad": math.pi / 2.0,
        "forward_status": "supported",
        "forward_axis": "+Z",
        "forward_axis_frame": "raw_mesh_local_frame",
        "world_zero_facing_axis": "+X",
        "world_zero_facing_axis_frame": "architectos_world_frame",
        "reasons": [],
    }
    result.update(overrides)

    return result


def _spec_with_phi(phi_result=None, candidate=None, forward_contract=None):
    return _forward_spec(
        SUPPORTED_FORWARD if forward_contract is None else forward_contract,
        candidate=candidate,
        phi_result=phi_result,
    )


# --- 1 - 7. storage behaviour ---------------------------------------------

def test_phi_result_omitted_keeps_old_behavior():
    spec = _forward_spec(SUPPORTED_FORWARD)

    assert spec["orientation"]["intrinsic_yaw_phi_rad"] is None
    assert spec["orientation"]["intrinsic_yaw_status"] == "unresolved"
    assert spec["orientation"]["full_alignment_status"] == "unresolved_forward"


def test_resolved_phi_result_stores_phi_rad():
    spec = _spec_with_phi(_phi_result())

    assert spec["orientation"]["intrinsic_yaw_phi_rad"] == pytest.approx(
        math.pi / 2.0
    )


def test_resolved_phi_result_sets_status_resolved():
    spec = _spec_with_phi(_phi_result())

    assert spec["orientation"]["intrinsic_yaw_status"] == "resolved"


def test_resolved_phi_result_sets_matrix_constructed():
    spec = _spec_with_phi(_phi_result())

    assert spec["orientation"]["full_alignment_status"] == "matrix_constructed"


def test_unresolved_phi_result_keeps_phi_null():
    spec = _spec_with_phi(
        _phi_result(
            phi_status="unresolved",
            phi_rad=None,
            forward_status="unresolved",
            forward_axis=None,
            reasons=["forward_unresolved"],
        ),
        forward_contract={"status": "unresolved"},
    )

    assert spec["orientation"]["intrinsic_yaw_phi_rad"] is None
    assert spec["orientation"]["intrinsic_yaw_status"] == "unresolved"
    assert spec["orientation"]["full_alignment_status"] == "unresolved_forward"


def test_blocked_phi_result_keeps_phi_null():
    spec = _spec_with_phi(
        _phi_result(phi_status="blocked", phi_rad=None, reasons=["invalid_forward_axis"])
    )

    assert spec["orientation"]["intrinsic_yaw_phi_rad"] is None


def test_blocked_phi_result_sets_status_blocked():
    spec = _spec_with_phi(
        _phi_result(phi_status="blocked", phi_rad=None, reasons=["invalid_forward_axis"])
    )

    assert spec["orientation"]["intrinsic_yaw_status"] == "blocked"
    assert spec["orientation"]["full_alignment_status"] == "blocked_phi"


# --- 8 - 15. structural validation -----------------------------------------

@pytest.mark.parametrize("bad", ["resolved", [], 3])
def test_malformed_phi_result_mapping_raises(bad):
    with pytest.raises(ValueError, match="phi_result must be a mapping"):
        _spec_with_phi(bad)


def test_unknown_phi_key_raises():
    with pytest.raises(ValueError, match="unknown phi_result key"):
        _spec_with_phi(_phi_result(confidence=0.9))


def test_missing_required_phi_key_raises():
    for key in ("phi_status", "phi_rad", "forward_axis", "reasons"):
        result = _phi_result()
        del result[key]
        with pytest.raises(ValueError, match="is missing"):
            _spec_with_phi(result)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_phi_raises(bad):
    with pytest.raises(ValueError, match="finite phi_rad"):
        _spec_with_phi(_phi_result(phi_rad=bad))


@pytest.mark.parametrize("bad", [True, False])
def test_bool_phi_rad_is_rejected(bad):
    """bool subclasses int, so it must be rejected explicitly (test 20)."""

    with pytest.raises(ValueError, match="numeric phi_rad"):
        _spec_with_phi(_phi_result(phi_rad=bad))


def test_resolved_phi_with_null_phi_rad_raises():
    with pytest.raises(ValueError, match="requires a numeric phi_rad"):
        _spec_with_phi(_phi_result(phi_rad=None))


def test_unresolved_phi_with_numeric_phi_rad_raises():
    with pytest.raises(ValueError, match="requires phi_rad to be null"):
        _spec_with_phi(
            _phi_result(
                phi_status="unresolved",
                forward_status="unresolved",
                forward_axis=None,
                reasons=["forward_unresolved"],
            )
        )


def test_blocked_phi_with_numeric_phi_rad_raises():
    with pytest.raises(ValueError, match="requires phi_rad to be null"):
        _spec_with_phi(
            _phi_result(phi_status="blocked", reasons=["invalid_forward_axis"])
        )


def test_blocked_phi_with_empty_reasons_raises():
    with pytest.raises(ValueError, match="requires non-empty reasons"):
        _spec_with_phi(
            _phi_result(phi_status="blocked", phi_rad=None, reasons=[])
        )


@pytest.mark.parametrize(
    "reasons",
    [
        ("reason",),
        (),
        "reason",
        {"reason"},
        {"reason": True},
        None,
        3,
        iter(["reason"]),
    ],
    ids=["tuple-1", "tuple-0", "str", "set", "dict", "none", "int", "generator"],
)
def test_non_list_phi_reasons_raise(reasons):
    """Strictly a list: tuples and every other container are rejected."""

    with pytest.raises(ValueError, match="reasons must be a list"):
        _spec_with_phi(_phi_result(reasons=reasons))


def test_empty_reasons_list_is_accepted_for_resolved_phi():
    spec = _spec_with_phi(_phi_result(reasons=[]))

    assert spec["orientation"]["intrinsic_yaw_status"] == "resolved"


def test_resolved_phi_with_nonempty_reasons_raises():
    """A resolved phi carries no reasons (Phase 3D-AB section 10, test 16)."""

    with pytest.raises(ValueError, match="requires empty reasons"):
        _spec_with_phi(_phi_result(reasons=["should_not_be_here"]))


def test_non_empty_reasons_list_is_accepted_for_blocked_phi():
    spec = _spec_with_phi(
        _phi_result(
            phi_status="blocked", phi_rad=None, reasons=["invalid_forward_axis"]
        )
    )

    assert spec["orientation"]["intrinsic_yaw_status"] == "blocked"


def test_tuple_reasons_are_not_normalized_into_a_list():
    with pytest.raises(ValueError, match="reasons must be a list"):
        _spec_with_phi(
            _phi_result(phi_status="blocked", phi_rad=None, reasons=("why",))
        )


def test_unknown_phi_status_raises():
    with pytest.raises(ValueError, match="phi_status must be one of"):
        _spec_with_phi(_phi_result(phi_status="maybe"))


# --- 16 - 18. frame and target validation ----------------------------------

def test_wrong_raw_frame_raises():
    with pytest.raises(ValueError, match="forward_axis_frame must be"):
        _spec_with_phi(_phi_result(forward_axis_frame="architectos_world_frame"))


@pytest.mark.parametrize("axis", ["+Y", "-X", "", "Z"])
def test_wrong_world_axis_raises(axis):
    with pytest.raises(ValueError, match="world_zero_facing_axis must be"):
        _spec_with_phi(_phi_result(world_zero_facing_axis=axis))


@pytest.mark.parametrize("frame", ["raw_mesh_local_frame", "world_frame", ""])
def test_wrong_world_frame_raises(frame):
    with pytest.raises(ValueError, match="world_zero_facing_axis_frame must be"):
        _spec_with_phi(_phi_result(world_zero_facing_axis_frame=frame))


# --- 19 - 23. cross-checks against the resolved contract -------------------

def test_mismatched_forward_status_raises():
    with pytest.raises(ValueError, match="does not match the resolved forward"):
        _spec_with_phi(_phi_result(forward_status="verified"))


def test_mismatched_forward_axis_raises():
    with pytest.raises(ValueError, match="forward_axis"):
        _spec_with_phi(_phi_result(forward_axis="+X"))


def test_mismatched_forward_axis_frame_is_rejected():
    """The public path cannot reach this: both sides are pinned to the raw frame.

    The guard is exercised directly so the cross-check is provably present.
    """

    phi = _phi_result()
    forward_metadata = {
        "forward_status": "supported",
        "forward_axis": "+Z",
        "forward_axis_frame": "raw_mesh_local_frame",
    }

    # Sanity: an exact match passes.
    assert _cross_check_phi_result(phi, forward_metadata) is phi

    doctored = dict(phi, forward_axis_frame="architectos_world_frame")
    with pytest.raises(ValueError, match="forward_axis_frame"):
        _cross_check_phi_result(doctored, forward_metadata)


def test_mismatched_world_axis_is_rejected():
    phi = _phi_result()
    forward_metadata = {"forward_status": "supported", "forward_axis": "+Z",
                        "forward_axis_frame": "raw_mesh_local_frame"}

    assert _cross_check_phi_result(phi, forward_metadata) is phi

    doctored = dict(phi, world_zero_facing_axis="+Y")
    with pytest.raises(ValueError, match="world_zero_facing_axis"):
        _cross_check_phi_result(doctored, forward_metadata)


def test_mismatched_world_frame_is_rejected():
    phi = _phi_result()
    forward_metadata = {"forward_status": "supported", "forward_axis": "+Z",
                        "forward_axis_frame": "raw_mesh_local_frame"}

    doctored = dict(phi, world_zero_facing_axis_frame="world_frame")
    with pytest.raises(ValueError, match="world_zero_facing_axis_frame"):
        _cross_check_phi_result(doctored, forward_metadata)


# --- 24 - 25. accepted combinations ----------------------------------------

def test_supported_raw_plus_z_with_half_pi_is_accepted():
    spec = _spec_with_phi(_phi_result())

    assert spec["orientation"]["forward_axis"] == "+Z"
    assert spec["orientation"]["intrinsic_yaw_phi_rad"] == pytest.approx(
        math.pi / 2.0
    )


def test_verified_raw_plus_x_with_phi_zero_is_accepted():
    spec = _spec_with_phi(
        _phi_result(
            phi_rad=0.0,
            forward_status="verified",
            forward_axis="+X",
        ),
        forward_contract={
            "status": "verified",
            "axis": "+X",
            "source": "geometry_measured",
        },
    )

    assert spec["orientation"]["forward_status"] == "verified"
    assert spec["orientation"]["intrinsic_yaw_phi_rad"] == 0.0


# --- 26 - 33. execution boundary -------------------------------------------

def test_phi_injection_composes_metadata_without_execution():
    spec = _spec_with_phi(_phi_result())

    # Transform metadata is composed (Phase 3D-AC / 3D-AD)...
    assert spec["transform"]["mesh_alignment_matrix"] is not None
    assert spec["transform"]["final_rotation_matrix"] is not None
    assert spec["transform"]["matrix4x4"] is not None
    # ...but nothing executable is produced.
    assert spec["bounds_after_partial"] is None
    assert "vertices_xyz" not in _all_keys(spec)
    assert spec["status"]["state"] == "pending_mesh_alignment"


def test_phi_injection_leaves_up_alignment_matrix_unchanged():
    spec = _spec_with_phi(_phi_result())

    assert spec["transform"]["up_alignment_matrix"] == [
        [1.0, 0.0, 0.0],
        [0.0, 0.0, -1.0],
        [0.0, 1.0, 0.0],
    ]


def test_phi_injection_leaves_placement_rotation_unchanged():
    spec = _spec_with_phi(_phi_result(), candidate=_with_yaw(math.pi / 2))

    expected = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    for index in range(3):
        assert spec["transform"]["placement_rotation_matrix"][index] == (
            pytest.approx(expected[index])
        )


def test_phi_injection_does_not_add_phi_to_placement_yaw():
    spec = _spec_with_phi(_phi_result(), candidate=_with_yaw(0.0))

    # phi stays intrinsic; the placement yaw is untouched.
    assert spec["transform"]["placement_rotation_matrix"] == [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    assert spec["orientation"]["intrinsic_yaw_phi_rad"] != 0.0


def test_phi_injection_leaves_status_and_completeness_unchanged():
    spec = _spec_with_phi(_phi_result())

    assert spec["status"]["state"] == "pending_mesh_alignment"
    assert spec["rotation_completeness"] == "placement_only"
    assert "vertices_xyz" not in _all_keys(spec)


# --- 34 - 35. gate precedence ---------------------------------------------

def test_placement_status_gate_precedence_is_preserved():
    candidate = _candidate()
    candidate["status"] = {"state": "pending_asset_match", "reasons": []}

    # Even a malformed phi_result must not change the placement gate outcome.
    spec = _spec_with_phi({"phi_status": "nonsense"}, candidate=candidate)

    assert spec["status"]["state"] == "transform_blocked"
    assert spec["orientation"] is None
    assert spec["transform"] is None


def test_scale_status_gate_precedence_is_preserved():
    candidate = _candidate()
    candidate["scale"]["scale_xyz"] = [1.0, 3.0, 1.0]

    spec = _spec_with_phi({"phi_status": "nonsense"}, candidate=candidate)

    assert spec["status"]["state"] == "pending_scale_contract"
    assert spec["status"]["reasons"] == ["scale_not_identity"]
    assert spec["orientation"] is None


# --- 36 - 38. purity -------------------------------------------------------

def test_transform_spec_does_not_call_the_phi_resolver():
    """The spec validates and stores phi; the caller owns derivation.

    The module docstring names the resolver for documentation, so the check is
    for an actual import or a bound reference, not for the bare token.
    """

    import core.asset.mesh_transform_spec as module

    source = Path(module.__file__).read_text(encoding="utf-8")

    assert "from core.asset.mesh_alignment_resolver import" not in source
    assert "import mesh_alignment_resolver" not in source
    assert not hasattr(module, "resolve_intrinsic_yaw_phi")

    resolver_names = [
        name for name in vars(module) if name == "mesh_alignment_resolver"
    ]
    assert resolver_names == []


def test_phi_result_input_is_not_mutated():
    phi_result = _phi_result()
    before = copy.deepcopy(phi_result)

    _spec_with_phi(phi_result)

    assert phi_result == before


def test_forward_contract_input_is_not_mutated_by_phi_injection():
    forward_contract = dict(SUPPORTED_FORWARD)
    before = copy.deepcopy(forward_contract)

    _forward_spec(forward_contract, phi_result=_phi_result())

    assert forward_contract == before


# ---------------------------------------------------------------------------
# Phase 3D-AC: intrinsic mesh alignment matrix composition
# ---------------------------------------------------------------------------

R_UP = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]
RAW_FORWARD_VECTORS = {
    "+X": [1.0, 0.0, 0.0],
    "-X": [-1.0, 0.0, 0.0],
    "+Z": [0.0, 0.0, 1.0],
    "-Z": [0.0, 0.0, -1.0],
}
RAW_UP_VECTOR = [0.0, 1.0, 0.0]
WORLD_FORWARD = [1.0, 0.0, 0.0]
WORLD_UP = [0.0, 0.0, 1.0]
PHI_BY_FORWARD = {
    "+X": 0.0,
    "-X": math.pi,
    "+Z": math.pi / 2.0,
    "-Z": -math.pi / 2.0,
}

# Explicit expected products, derived by hand from Rz(phi) * R_up.
EXPECTED_BY_FORWARD = {
    "+X": [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]],
    "-X": [[-1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]],
    "+Z": [[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
    "-Z": [[0.0, 0.0, -1.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
}


def _matmul(left, right):
    return [
        [sum(left[row][k] * right[k][col] for k in range(3)) for col in range(3)]
        for row in range(3)
    ]


def _matvec(matrix, vector):
    return [sum(matrix[row][k] * vector[k] for k in range(3)) for row in range(3)]


def _transpose(matrix):
    return [[matrix[col][row] for col in range(3)] for row in range(3)]


def _det3(matrix):
    (a, b, c), (d, e, f), (g, h, i) = matrix
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def _rz(phi):
    return [
        [math.cos(phi), -math.sin(phi), 0.0],
        [math.sin(phi), math.cos(phi), 0.0],
        [0.0, 0.0, 1.0],
    ]


def _rows_approx(actual, expected):
    for index in range(3):
        assert actual[index] == pytest.approx(expected[index], abs=1e-12)


def _composed(axis):
    return _compose_mesh_alignment_matrix(PHI_BY_FORWARD[axis], R_UP)


def _contract_for_axis(axis):
    """Synthetic caller-supplied override for arbitrary-axis matrix tests.

    Deliberately NOT the accepted seating/adult-bed family rule: that family's
    semantic forward is raw ``+Z`` only, and it is SUPPORTED, not verified. Using
    it for ``+X``/``-X``/``-Z`` would fabricate semantics the evidence does not
    support, so an explicit per-asset override is used instead.
    """

    return {
        "status": "supported",
        "axis": axis,
        "source": "per_asset_override",
    }


def _flatten(matrix):
    return [value for row in matrix for value in row]


# --- 1 - 4. explicit matrices ---------------------------------------------

def test_phi_zero_composes_to_r_up_exactly():
    matrix = _composed("+X")

    _rows_approx(matrix, R_UP)
    assert matrix == R_UP


def test_phi_plus_half_pi_composes_to_expected_matrix():
    _rows_approx(_composed("+Z"), EXPECTED_BY_FORWARD["+Z"])


def test_phi_minus_half_pi_composes_to_expected_matrix():
    _rows_approx(_composed("-Z"), EXPECTED_BY_FORWARD["-Z"])


def test_phi_pi_composes_to_expected_matrix():
    _rows_approx(_composed("-X"), EXPECTED_BY_FORWARD["-X"])


def test_small_floating_point_values_are_preserved_not_snapped():
    """Part L: raw float output is preserved; tests use approx."""

    matrix = _composed("+Z")

    assert matrix[0][0] == pytest.approx(6.123233995736766e-17, abs=1e-18)
    assert matrix[0][0] != 0.0


# --- 5 - 8. semantic and algebraic properties -----------------------------

@pytest.mark.parametrize("axis", ["+X", "-X", "+Z", "-Z"])
def test_every_matrix_maps_raw_forward_to_world_plus_x(axis):
    matrix = _composed(axis)

    assert _matvec(matrix, RAW_FORWARD_VECTORS[axis]) == pytest.approx(
        WORLD_FORWARD, abs=1e-12
    )


@pytest.mark.parametrize("axis", ["+X", "-X", "+Z", "-Z"])
def test_every_matrix_maps_raw_up_to_world_plus_z(axis):
    matrix = _composed(axis)

    assert _matvec(matrix, RAW_UP_VECTOR) == pytest.approx(WORLD_UP, abs=1e-12)


@pytest.mark.parametrize("axis", ["+X", "-X", "+Z", "-Z"])
def test_every_matrix_is_orthonormal(axis):
    matrix = _composed(axis)

    product = _matmul(_transpose(matrix), matrix)
    for index in range(3):
        expected = [0.0, 0.0, 0.0]
        expected[index] = 1.0
        assert product[index] == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("axis", ["+X", "-X", "+Z", "-Z"])
def test_every_matrix_has_determinant_plus_one(axis):
    # A proper rotation: no reflection is introduced. This does NOT establish
    # raw mesh handedness, which remains unresolved.
    assert _det3(_composed(axis)) == pytest.approx(1.0, abs=1e-12)


# --- 9 - 12. when the matrix is populated ---------------------------------

@pytest.mark.parametrize("axis", ["+X", "-X", "+Z", "-Z"])
def test_matrix_populated_for_resolved_phi(axis):
    spec = _spec_with_phi(
        _phi_result(phi_rad=PHI_BY_FORWARD[axis], forward_axis=axis),
        forward_contract=_contract_for_axis(axis),
    )

    matrix = spec["transform"]["mesh_alignment_matrix"]
    assert matrix is not None
    _rows_approx(matrix, EXPECTED_BY_FORWARD[axis])


def test_unresolved_phi_keeps_matrix_null():
    spec = _spec_with_phi(
        _phi_result(
            phi_status="unresolved",
            phi_rad=None,
            forward_status="unresolved",
            forward_axis=None,
            reasons=["forward_unresolved"],
        ),
        forward_contract={"status": "unresolved"},
    )

    assert spec["transform"]["mesh_alignment_matrix"] is None
    assert spec["orientation"]["full_alignment_status"] == "unresolved_forward"


def test_blocked_phi_keeps_matrix_null():
    spec = _spec_with_phi(
        _phi_result(phi_status="blocked", phi_rad=None, reasons=["invalid_forward_axis"])
    )

    assert spec["transform"]["mesh_alignment_matrix"] is None
    assert spec["orientation"]["full_alignment_status"] == "blocked_phi"


def test_omitted_phi_result_keeps_matrix_null():
    spec = _forward_spec(SUPPORTED_FORWARD)

    assert spec["transform"]["mesh_alignment_matrix"] is None
    assert spec["orientation"]["full_alignment_status"] == "unresolved_forward"


# --- 13 - 15. purity of the helper ----------------------------------------

def test_composition_does_not_modify_its_inputs():
    up = [list(row) for row in R_UP]
    up_before = [list(row) for row in up]

    _compose_mesh_alignment_matrix(math.pi / 2.0, up)

    assert up == up_before


def test_composition_returns_a_new_nested_list():
    up = [list(row) for row in R_UP]

    matrix = _compose_mesh_alignment_matrix(math.pi / 2.0, up)

    assert matrix is not up
    assert all(matrix[index] is not up[index] for index in range(3))


def test_matrix_composition_does_not_modify_phi_result():
    phi_result = _phi_result()
    before = copy.deepcopy(phi_result)

    _spec_with_phi(phi_result)

    assert phi_result == before


# --- 16 - 22. helper input validation -------------------------------------

@pytest.mark.parametrize("bad", [None, "zero", [0.0], {}, object()])
def test_helper_rejects_malformed_phi(bad):
    with pytest.raises(ValueError, match="phi_rad must be a real number"):
        _compose_mesh_alignment_matrix(bad, R_UP)


def test_helper_rejects_bool_phi():
    with pytest.raises(ValueError, match="phi_rad must be a real number"):
        _compose_mesh_alignment_matrix(True, R_UP)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_helper_rejects_non_finite_phi(bad):
    with pytest.raises(ValueError, match="phi_rad must be finite"):
        _compose_mesh_alignment_matrix(bad, R_UP)


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "matrix",
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        [[1.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0, 0.0]],
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], "row"],
    ],
)
def test_helper_rejects_malformed_up_matrix(bad):
    with pytest.raises(ValueError, match="must be a 3x3 matrix"):
        _compose_mesh_alignment_matrix(0.0, bad)


@pytest.mark.parametrize("bad", ["a", None, [1.0]])
def test_helper_rejects_non_numeric_up_entries(bad):
    up = [list(row) for row in R_UP]
    up[1][1] = bad

    with pytest.raises(ValueError, match="must be a real number"):
        _compose_mesh_alignment_matrix(0.0, up)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_helper_rejects_non_finite_up_entries(bad):
    up = [list(row) for row in R_UP]
    up[2][0] = bad

    with pytest.raises(ValueError, match="must be finite"):
        _compose_mesh_alignment_matrix(0.0, up)


# --- 23 - 25. placement yaw separation ------------------------------------

def test_mesh_alignment_matrix_excludes_placement_yaw():
    spec = _spec_with_phi(_phi_result(), candidate=_with_yaw(math.pi / 2))

    matrix = spec["transform"]["mesh_alignment_matrix"]
    _rows_approx(matrix, EXPECTED_BY_FORWARD["+Z"])

    # Folding the placement yaw in would produce this different matrix.
    folded = _matmul(_rz(math.pi / 2), EXPECTED_BY_FORWARD["+Z"])
    assert _flatten(matrix) != pytest.approx(_flatten(folded), abs=1e-6)


def test_changing_placement_yaw_does_not_change_mesh_alignment_matrix():
    first = _spec_with_phi(_phi_result(), candidate=_with_yaw(0.0))
    second = _spec_with_phi(_phi_result(), candidate=_with_yaw(1.2345))

    assert first["transform"]["mesh_alignment_matrix"] == (
        second["transform"]["mesh_alignment_matrix"]
    )


def test_changing_phi_does_not_change_placement_rotation_matrix():
    first = _spec_with_phi(
        _phi_result(forward_axis="+X", phi_rad=0.0),
        forward_contract=_contract_for_axis("+X"),
    )
    second = _spec_with_phi(_phi_result())

    assert first["transform"]["placement_rotation_matrix"] == (
        second["transform"]["placement_rotation_matrix"]
    )
    assert first["transform"]["mesh_alignment_matrix"] != (
        second["transform"]["mesh_alignment_matrix"]
    )


# --- 26 - 32. execution boundary and status ------------------------------

def test_matrix_composition_leaves_execution_fields_null():
    spec = _spec_with_phi(_phi_result())

    # Transform metadata exists; execution artefacts do not.
    assert spec["transform"]["matrix4x4"] is not None
    assert spec["bounds_after_partial"] is None
    assert "world_vertices_xyz" not in _all_keys(spec)
    assert spec["status"]["state"] == "pending_mesh_alignment"


def test_matrix_composition_adds_no_vertices():
    spec = _spec_with_phi(_phi_result())

    assert "vertices_xyz" not in _all_keys(spec)
    assert "world_vertices_xyz" not in _all_keys(spec)


def test_matrix_composition_keeps_status_pending():
    spec = _spec_with_phi(_phi_result())

    assert spec["status"]["state"] == "pending_mesh_alignment"
    assert spec["status"]["state"] not in (
        "ready",
        "transform_ready",
        "executable",
        "complete",
        "placed",
    )


def test_matrix_composition_keeps_rotation_completeness_placement_only():
    spec = _spec_with_phi(_phi_result())

    assert spec["rotation_completeness"] == "placement_only"


def test_matrix_constructed_only_after_successful_composition():
    composed = _spec_with_phi(_phi_result())
    omitted = _forward_spec(SUPPORTED_FORWARD)

    assert composed["orientation"]["full_alignment_status"] == "matrix_constructed"
    assert composed["transform"]["mesh_alignment_matrix"] is not None
    assert omitted["orientation"]["full_alignment_status"] == "unresolved_forward"
    assert omitted["transform"]["mesh_alignment_matrix"] is None


# --- 33 - 34. gate precedence with a resolved phi -------------------------

def test_blocked_placement_gate_wins_with_resolved_phi():
    candidate = _candidate()
    candidate["status"] = {"state": "pending_asset_match", "reasons": []}

    spec = _spec_with_phi(_phi_result(), candidate=candidate)

    assert spec["status"]["state"] == "transform_blocked"
    assert spec["orientation"] is None
    assert spec["transform"] is None


def test_scale_gate_wins_with_resolved_phi():
    candidate = _candidate()
    candidate["scale"]["scale_xyz"] = [1.0, 4.0, 1.0]

    spec = _spec_with_phi(_phi_result(), candidate=candidate)

    assert spec["status"]["state"] == "pending_scale_contract"
    # The scale path keeps its own all-null transform skeleton; nothing is composed.
    assert spec["orientation"] is None
    assert spec["transform"]["mesh_alignment_matrix"] is None
    assert spec["transform"]["up_alignment_matrix"] is None
    assert spec["transform"]["matrix4x4"] is None


# --- 35 - 38. no forbidden composition -----------------------------------

def test_composition_does_not_use_the_adapter_basis_or_resolver():
    """The composition helper must not import or bind the adapter or resolver.

    ``FurnitureAdapter`` and the resolver are named in comments/docstrings, so
    the check is for an actual import or a bound module/attribute.
    """

    import types

    import core.asset.mesh_transform_spec as module

    source = Path(module.__file__).read_text(encoding="utf-8")

    assert "from core.asset.mesh_alignment_resolver import" not in source
    assert "import furniture_adapter" not in source
    assert "from core.pipeline.adapters.furniture_adapter import" not in source
    assert not hasattr(module, "resolve_intrinsic_yaw_phi")
    assert not hasattr(module, "FurnitureAdapter")

    imported_modules = [
        value.__name__
        for value in vars(module).values()
        if isinstance(value, types.ModuleType)
    ]
    assert "core.pipeline.adapters.furniture_adapter" not in imported_modules
    assert "core.asset.mesh_alignment_resolver" not in imported_modules


def test_final_matrix_metadata_is_produced_but_never_applied():
    spec = _spec_with_phi(_phi_result(), candidate=_with_yaw(math.pi / 2))
    keys = _all_keys(spec)

    # Phase 3D-AD produces explicit transform METADATA...
    assert spec["transform"]["final_rotation_matrix"] is not None
    assert spec["transform"]["matrix4x4"] is not None
    # ...but no vertex-level artefact is ever produced.
    for forbidden in (
        "world_vertices_xyz",
        "transformed_vertices",
        "vertices_world",
        "vertices_xyz",
    ):
        assert forbidden not in keys


def test_composed_matrix_is_a_proper_rotation_not_a_reflection():
    """No reflection is introduced; handedness remains unresolved."""

    for axis in ["+X", "-X", "+Z", "-Z"]:
        matrix = _composed(axis)
        assert _det3(matrix) == pytest.approx(1.0, abs=1e-12)
        # No axis negation or reflection shortcut.
        assert matrix[1][2] in (0.0, pytest.approx(0.0, abs=1e-12)) or abs(
            matrix[1][2]
        ) < 1e-12 or abs(matrix[1][2]) == pytest.approx(1.0, abs=1e-12)


# --- 40. preserved behaviour ----------------------------------------------

def test_behaviour_without_phi_result_is_unchanged():
    spec = _forward_spec(SUPPORTED_FORWARD)

    assert spec["orientation"]["intrinsic_yaw_phi_rad"] is None
    assert spec["orientation"]["intrinsic_yaw_status"] == "unresolved"
    assert spec["transform"]["mesh_alignment_matrix"] is None
    assert spec["transform"]["matrix4x4"] is None
    assert spec["transform"]["translation_xyz"] is None
    assert spec["rotation_completeness"] == "placement_only"
    assert spec["status"]["state"] == "pending_mesh_alignment"


# ---------------------------------------------------------------------------
# Phase 3D-AH.1: the placement identity is COPIED, never recreated
# ---------------------------------------------------------------------------

def _identity(**overrides):
    identity = {
        "status": "resolved",
        "scope": "scene-a",
        "ordinal": 1,
        "source_engine": "DiffuScene",
        "source_slot": 3,
        "instance_id": "scene-a:placement:000001",
    }
    identity.update(overrides)

    return identity


def _candidate_with_identity(identity):
    candidate = _candidate()
    candidate["placement_identity"] = identity

    return candidate


def test_spec_copies_the_placement_identity_unchanged():
    identity = _identity()

    spec = _build(candidate=_candidate_with_identity(identity))

    assert spec["placement_identity"] == identity
    # Copied, not aliased: the spec owns its own container.
    assert spec["placement_identity"] is not identity


def test_spec_does_not_derive_identity_from_model_id():
    spec = _build(candidate=_candidate_with_identity(_identity()))

    # The ASSET MODEL id stays in the mesh reference...
    assert spec["mesh_reference"]["model_id"] == "model-a"
    # ...and never leaks into the PLACEMENT identity.
    assert spec["placement_identity"]["instance_id"] == "scene-a:placement:000001"
    assert "model-a" not in spec["placement_identity"]["instance_id"]


def test_spec_preserves_an_unresolved_placement_identity():
    identity = _identity(
        status="unresolved",
        scope=None,
        instance_id=None,
        reasons=["placement_scope_missing"],
    )

    spec = _build(candidate=_candidate_with_identity(identity))

    assert spec["placement_identity"]["status"] == "unresolved"
    assert spec["placement_identity"]["instance_id"] is None
    assert spec["placement_identity"]["reasons"] == ["placement_scope_missing"]


def test_spec_without_identity_stays_explicitly_absent():
    spec = _build()

    assert spec["placement_identity"] is None


def test_placement_identity_does_not_alter_transform_math():
    without = _build(candidate=_candidate_with_identity(None))
    with_identity = _build(candidate=_candidate_with_identity(_identity()))

    assert with_identity["transform"] == without["transform"]
    assert with_identity["pivot"] == without["pivot"]
    assert with_identity["orientation"] == without["orientation"]
    assert with_identity["status"] == without["status"]


def test_identity_survives_the_blocked_paths():
    identity = _identity()
    blocked = _candidate_with_identity(identity)
    blocked["status"] = {"state": "pending_asset_match", "reasons": []}

    spec = _build(candidate=blocked)

    assert spec["status"]["state"] == "transform_blocked"
    assert spec["transform"] is None
    # Identity is provenance, so it is still copied through.
    assert spec["placement_identity"] == identity


def test_spec_does_not_mutate_the_candidate_identity():
    identity = _identity()
    candidate = _candidate_with_identity(identity)
    before = copy.deepcopy(candidate)

    _build(candidate=candidate)

    assert candidate == before


# ---------------------------------------------------------------------------
# Phase 3D-AC.1: contract semantics hardening
# ---------------------------------------------------------------------------

def test_composed_matrix_does_not_report_alignment_unresolved():
    spec = _spec_with_phi(_phi_result())

    assert spec["transform"]["mesh_alignment_matrix"] is not None
    assert "mesh_alignment_unresolved" not in spec["status"]["reasons"]


def test_composed_matrix_reports_not_executable():
    spec = _spec_with_phi(_phi_result())

    assert spec["status"]["reasons"] == [
        "mesh_transform_not_executable",
        "mesh_handedness_unresolved",
    ]


def test_composed_matrix_reports_handedness_unresolved():
    spec = _spec_with_phi(_phi_result())

    assert "mesh_handedness_unresolved" in spec["status"]["reasons"]


@pytest.mark.parametrize(
    "phi_result",
    [
        None,
        _phi_result(
            phi_status="unresolved",
            phi_rad=None,
            forward_status="unresolved",
            forward_axis=None,
            reasons=["forward_unresolved"],
        ),
        _phi_result(
            phi_status="blocked", phi_rad=None, reasons=["invalid_forward_axis"]
        ),
    ],
    ids=["omitted", "unresolved", "blocked"],
)
def test_uncomposed_matrix_may_still_report_alignment_unresolved(phi_result):
    contract = None if phi_result is None else (
        {"status": "unresolved"}
        if phi_result["phi_status"] == "unresolved"
        else SUPPORTED_FORWARD
    )

    spec = _spec_with_phi(phi_result, forward_contract=contract)

    assert spec["transform"]["mesh_alignment_matrix"] is None
    assert "mesh_alignment_unresolved" in spec["status"]["reasons"]
    assert "mesh_alignment_not_executable" not in spec["status"]["reasons"]


def test_world_reference_reason_is_preserved_when_composed():
    candidate = _candidate()
    candidate["position"]["world_xyz"] = [11.0, 17.0, 2.0]

    spec = _spec_with_phi(_phi_result(), candidate=candidate)

    assert spec["status"]["reasons"] == [
        "mesh_transform_not_executable",
        "mesh_handedness_unresolved",
        "world_reference_recorded_not_applied",
    ]


def test_world_reference_reason_is_preserved_when_not_composed():
    candidate = _candidate()
    candidate["position"]["world_xyz"] = [11.0, 17.0, 2.0]

    spec = _forward_spec(SUPPORTED_FORWARD, candidate=candidate)

    assert spec["status"]["reasons"] == [
        "mesh_alignment_unresolved",
        "world_reference_recorded_not_applied",
    ]


@pytest.mark.parametrize("composed", [True, False])
def test_state_remains_pending_with_or_without_composition(composed):
    spec = (
        _spec_with_phi(_phi_result()) if composed
        else _forward_spec(SUPPORTED_FORWARD)
    )

    assert spec["status"]["state"] == "pending_mesh_alignment"
    assert spec["status"]["state"] not in (
        "ready",
        "transform_ready",
        "executable",
        "complete",
        "placed",
    )


# --- family-rule semantics must not be fabricated --------------------------

@pytest.mark.parametrize("axis", ["+X", "-X", "+Z", "-Z"])
def test_arbitrary_axis_contracts_do_not_use_the_family_rule(axis):
    contract = _contract_for_axis(axis)

    assert contract["source"] == "per_asset_override"
    assert contract["source"] != "family_rule"
    assert contract.get("family") is None


def test_accepted_family_rule_declares_only_plus_z():
    from core.asset.forward_rule_registry import ForwardRuleRegistry

    rule = ForwardRuleRegistry.load_default().get_forward_rule(
        "seating_and_adult_beds"
    )

    assert rule is not None
    assert rule["semantic_forward_axis"] == "+Z"
    assert rule["expected_geometry_direction"] == "-Z"
    assert rule["status"] == "supported"
    assert rule["status"] != "verified"


def test_seating_family_rule_with_plus_z_is_accepted():
    spec = _forward_spec(SUPPORTED_FORWARD, phi_result=_phi_result())

    assert spec["orientation"]["forward_source"] == "family_rule"
    assert spec["orientation"]["forward_family"] == "seating_and_adult_beds"
    assert spec["orientation"]["forward_axis"] == "+Z"
    assert spec["orientation"]["intrinsic_yaw_status"] == "resolved"
    assert spec["transform"]["mesh_alignment_matrix"] is not None
    _rows_approx(spec["transform"]["mesh_alignment_matrix"], EXPECTED_BY_FORWARD["+Z"])


# --- handedness wording ----------------------------------------------------

def test_det_plus_one_matrix_is_not_claimed_to_mirror_geometry():
    """The matrix is orthonormal with det +1 and introduces no reflection.

    The execution blocker is the unresolved raw-frame handedness / semantic
    frame authorization boundary - NOT a reflection inside the matrix.
    """

    for axis in ["+X", "-X", "+Z", "-Z"]:
        matrix = _composed(axis)
        assert _det3(matrix) == pytest.approx(1.0, abs=1e-12)
        # A reflection would require det = -1.
        assert _det3(matrix) != pytest.approx(-1.0, abs=1e-6)

    spec = _spec_with_phi(_phi_result())
    assert "mesh_handedness_unresolved" in spec["status"]["reasons"]
    # The composed matrix is metadata; no execution artefact follows from it.
    assert spec["transform"]["matrix4x4"] is not None
    assert spec["bounds_after_partial"] is None


# ---------------------------------------------------------------------------
# Phase 3D-AD: final affine / matrix4x4 metadata composition
# ---------------------------------------------------------------------------

# Hand-derived constants. phi = +pi/2 and yaw = +pi/2.
R_MESH_HALF_PI = [[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
R_PLACE_HALF_PI = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
R_FINAL_HAND_DERIVED = [[-1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]]

PIVOT_LOCAL = [1.25, 0.5, -2.0]
PIVOT_TARGET = [8.0, 3.5, 1.2]
# t = c_w - R_final * c_m, computed by hand:
#   R_final * c_m = [-1.25, -2.0, 0.5]
#   t             = [8.0 + 1.25, 3.5 + 2.0, 1.2 - 0.5]
TRANSLATION_HAND_DERIVED = [9.25, 5.5, 0.7]


def _affine_spec(yaw=math.pi / 2.0):
    return _spec_with_phi(_phi_result(), candidate=_with_yaw(yaw))


# --- 1 - 7. rotation composition ------------------------------------------

def test_final_rotation_is_placement_times_mesh():
    spec = _affine_spec()
    transform = spec["transform"]

    expected = _matmul(
        transform["placement_rotation_matrix"], transform["mesh_alignment_matrix"]
    )
    _rows_approx(transform["final_rotation_matrix"], expected)


def test_zero_yaw_gives_final_rotation_equal_to_mesh():
    spec = _affine_spec(yaw=0.0)

    assert _flatten(spec["transform"]["final_rotation_matrix"]) == pytest.approx(
        _flatten(spec["transform"]["mesh_alignment_matrix"]), abs=1e-12
    )


def test_zero_phi_gives_mesh_equal_to_r_up():
    spec = _spec_with_phi(
        _phi_result(phi_rad=0.0, forward_axis="+X"),
        forward_contract=_contract_for_axis("+X"),
        candidate=_with_yaw(math.pi / 2.0),
    )
    transform = spec["transform"]

    assert transform["mesh_alignment_matrix"] == R_UP
    expected = _matmul(_rz(math.pi / 2.0), R_UP)
    _rows_approx(transform["final_rotation_matrix"], expected)


def test_non_zero_phi_and_yaw_match_hand_derived_matrix():
    """Independently derived expected matrix - not produced by the helper."""

    affine = _compose_final_affine(
        R_MESH_HALF_PI, R_PLACE_HALF_PI, PIVOT_LOCAL, PIVOT_TARGET
    )

    _rows_approx(affine["final_rotation_matrix"], R_FINAL_HAND_DERIVED)
    # Sanity: the hand-derived matrix maps raw forward (+Z) to world +Y after the
    # placement yaw of +pi/2, and raw up (+Y) to world +Z.
    assert _matvec(R_FINAL_HAND_DERIVED, [0.0, 0.0, 1.0]) == pytest.approx(
        [0.0, 1.0, 0.0], abs=1e-12
    )
    assert _matvec(R_FINAL_HAND_DERIVED, [0.0, 1.0, 0.0]) == pytest.approx(
        [0.0, 0.0, 1.0], abs=1e-12
    )


def test_changing_placement_yaw_changes_final_rotation():
    first = _affine_spec(yaw=0.0)["transform"]["final_rotation_matrix"]
    second = _affine_spec(yaw=1.1)["transform"]["final_rotation_matrix"]

    assert _flatten(first) != pytest.approx(_flatten(second), abs=1e-6)


def test_changing_phi_changes_final_rotation():
    first = _spec_with_phi(
        _phi_result(phi_rad=0.0, forward_axis="+X"),
        forward_contract=_contract_for_axis("+X"),
    )["transform"]["final_rotation_matrix"]
    second = _affine_spec()["transform"]["final_rotation_matrix"]

    assert _flatten(first) != pytest.approx(_flatten(second), abs=1e-6)


def test_placement_yaw_applied_exactly_once():
    spec = _affine_spec(yaw=math.pi / 2.0)
    transform = spec["transform"]

    once = _matmul(
        _rz(math.pi / 2.0), transform["mesh_alignment_matrix"]
    )
    twice = _matmul(
        _rz(math.pi), transform["mesh_alignment_matrix"]
    )

    _rows_approx(transform["final_rotation_matrix"], once)
    assert _flatten(transform["final_rotation_matrix"]) != pytest.approx(
        _flatten(twice), abs=1e-6
    )


# --- 8 - 10. no reapplication ---------------------------------------------

def test_basis_b_is_not_reapplied():
    final = _affine_spec()["transform"]["final_rotation_matrix"]

    # Reapplying B (numerically equal to R_up) would change the result.
    with_b = _matmul(R_UP, final)
    assert _flatten(final) != pytest.approx(_flatten(with_b), abs=1e-6)


def test_r_up_is_not_reapplied():
    spec = _spec_with_phi(
        _phi_result(phi_rad=0.0, forward_axis="+X"),
        forward_contract=_contract_for_axis("+X"),
    )

    # With phi = 0 the mesh alignment IS R_up, applied exactly once.
    assert spec["transform"]["mesh_alignment_matrix"] == R_UP
    assert spec["transform"]["mesh_alignment_matrix"] != _matmul(R_UP, R_UP)


def test_phi_is_not_reapplied():
    mesh = _affine_spec()["transform"]["mesh_alignment_matrix"]

    _rows_approx(mesh, R_MESH_HALF_PI)
    # Applying phi twice would give Rz(pi) * R_up.
    assert _flatten(mesh) != pytest.approx(
        _flatten(_matmul(_rz(math.pi), R_UP)), abs=1e-6
    )


# --- 11 - 15. pivot and translation ---------------------------------------

def test_local_bbox_center_is_the_pivot():
    affine = _compose_final_affine(
        R_MESH_HALF_PI, R_PLACE_HALF_PI, PIVOT_LOCAL, PIVOT_TARGET
    )

    rotated = _matvec(R_FINAL_HAND_DERIVED, PIVOT_LOCAL)
    expected = [PIVOT_TARGET[i] - rotated[i] for i in range(3)]
    assert affine["translation_xyz"] == pytest.approx(expected, abs=1e-12)
    assert affine["translation_xyz"] == pytest.approx(
        TRANSLATION_HAND_DERIVED, abs=1e-12
    )


def test_obj_origin_is_not_used_as_pivot():
    affine = _compose_final_affine(
        R_MESH_HALF_PI, R_PLACE_HALF_PI, PIVOT_LOCAL, PIVOT_TARGET
    )

    # Using the OBJ origin ([0,0,0]) as the pivot would give t == c_w.
    assert affine["translation_xyz"] != pytest.approx(PIVOT_TARGET, abs=1e-6)

    spec = _affine_spec()
    assert spec["pivot"]["mesh_origin_xyz"] == [0.0, 0.0, 0.0]
    assert spec["pivot"]["local_bbox_center_xyz"] != [0.0, 0.0, 0.0]


def test_translation_formula():
    transform = _affine_spec()["transform"]

    rotated = _matvec(
        transform["final_rotation_matrix"],
        [2.0, 2.5, 3.0],  # the fixture's local bbox center
    )
    expected = [1.0 - rotated[0], -3.0 - rotated[1], 2.0 - rotated[2]]

    assert transform["translation_xyz"] == pytest.approx(expected, abs=1e-12)


def test_center_mapping_lands_on_the_target():
    spec = _affine_spec()
    transform = spec["transform"]
    c_m = spec["pivot"]["local_bbox_center_xyz"]
    c_w = spec["pivot"]["target_bbox_center_xyz"]

    mapped = [
        value + translation
        for value, translation in zip(
            _matvec(transform["final_rotation_matrix"], c_m),
            transform["translation_xyz"],
        )
    ]

    assert mapped == pytest.approx(c_w, abs=1e-12)


def test_affine_equivalence_on_a_synthetic_vector():
    """Synthetic math only - no transformed vertex is added to the spec."""

    spec = _affine_spec()
    transform = spec["transform"]
    c_m = spec["pivot"]["local_bbox_center_xyz"]
    c_w = spec["pivot"]["target_bbox_center_xyz"]
    vertex = [0.4, -1.7, 2.2]

    form_b = [
        value + translation
        for value, translation in zip(
            _matvec(transform["final_rotation_matrix"], vertex),
            transform["translation_xyz"],
        )
    ]
    form_a = [
        value + target
        for value, target in zip(
            _matvec(
                transform["final_rotation_matrix"],
                [vertex[i] - c_m[i] for i in range(3)],
            ),
            c_w,
        )
    ]

    assert form_b == pytest.approx(form_a, abs=1e-12)
    assert "vertices_xyz" not in _all_keys(spec)


# --- 16 - 20. matrix4x4 shape and purity ----------------------------------

def test_matrix4x4_top_left_is_the_final_rotation():
    transform = _affine_spec()["transform"]
    matrix = transform["matrix4x4"]

    for row in range(3):
        assert matrix[row][:3] == pytest.approx(
            transform["final_rotation_matrix"][row], abs=1e-12
        )


def test_matrix4x4_last_column_is_the_translation():
    transform = _affine_spec()["transform"]
    matrix = transform["matrix4x4"]

    for row in range(3):
        assert matrix[row][3] == pytest.approx(
            transform["translation_xyz"][row], abs=1e-12
        )


def test_matrix4x4_bottom_row_is_homogeneous():
    matrix = _affine_spec()["transform"]["matrix4x4"]

    assert matrix[3] == [0.0, 0.0, 0.0, 1.0]


def test_matrix4x4_is_a_fresh_nested_list():
    mesh = [list(row) for row in R_MESH_HALF_PI]
    place = [list(row) for row in R_PLACE_HALF_PI]

    affine = _compose_final_affine(mesh, place, PIVOT_LOCAL, PIVOT_TARGET)

    assert affine["final_rotation_matrix"] is not mesh
    assert affine["final_rotation_matrix"] is not place
    assert affine["matrix4x4"] is not affine["final_rotation_matrix"]
    assert all(
        affine["matrix4x4"][row] is not affine["final_rotation_matrix"][row]
        for row in range(3)
    )


def test_affine_composition_does_not_mutate_inputs():
    mesh = [list(row) for row in R_MESH_HALF_PI]
    place = [list(row) for row in R_PLACE_HALF_PI]
    c_m = list(PIVOT_LOCAL)
    c_w = list(PIVOT_TARGET)
    before = (copy.deepcopy(mesh), copy.deepcopy(place), list(c_m), list(c_w))

    _compose_final_affine(mesh, place, c_m, c_w)

    assert (mesh, place, c_m, c_w) == before


# --- 21 - 24. algebra and handedness -------------------------------------

@pytest.mark.parametrize("yaw", [0.0, 0.7, math.pi / 2.0])
def test_final_rotation_is_orthonormal(yaw):
    final = _affine_spec(yaw=yaw)["transform"]["final_rotation_matrix"]

    product = _matmul(_transpose(final), final)
    for index in range(3):
        expected = [0.0, 0.0, 0.0]
        expected[index] = 1.0
        assert product[index] == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("yaw", [0.0, 0.7, math.pi / 2.0])
def test_final_rotation_determinant_is_plus_one(yaw):
    final = _affine_spec(yaw=yaw)["transform"]["final_rotation_matrix"]

    assert _det3(final) == pytest.approx(1.0, abs=1e-12)


def test_composition_introduces_no_reflection():
    final = _affine_spec()["transform"]["final_rotation_matrix"]

    assert _det3(final) == pytest.approx(1.0, abs=1e-12)
    assert _det3(final) != pytest.approx(-1.0, abs=1e-6)


def test_handedness_remains_unresolved_despite_det_plus_one():
    spec = _affine_spec()

    assert _det3(spec["transform"]["final_rotation_matrix"]) == pytest.approx(
        1.0, abs=1e-12
    )
    assert "mesh_handedness_unresolved" in spec["status"]["reasons"]
    assert "mesh_transform_not_executable" in spec["status"]["reasons"]


# --- 25 - 28. execution boundary -----------------------------------------

def test_bounds_after_partial_remains_none():
    assert _affine_spec()["bounds_after_partial"] is None


def test_no_vertices_are_added():
    keys = _all_keys(_affine_spec())

    for forbidden in (
        "vertices_xyz",
        "world_vertices_xyz",
        "transformed_vertices",
        "vertices_world",
    ):
        assert forbidden not in keys


def test_status_remains_pending():
    assert _affine_spec()["status"]["state"] == "pending_mesh_alignment"


def test_no_ready_or_executable_state_is_introduced():
    state = _affine_spec()["status"]["state"]

    assert state not in (
        "ready",
        "transform_ready",
        "executable",
        "complete",
        "placed",
    )
    assert _affine_spec()["rotation_completeness"] == "placement_only"


# --- 29 - 33. gate precedence and null cases -----------------------------

def test_non_identity_scale_gate_still_wins():
    candidate = _candidate()
    candidate["scale"]["scale_xyz"] = [1.0, 2.5, 1.0]

    spec = _spec_with_phi(_phi_result(), candidate=candidate)

    assert spec["status"]["state"] == "pending_scale_contract"
    assert spec["orientation"] is None
    assert spec["transform"]["final_rotation_matrix"] is None
    assert spec["transform"]["translation_xyz"] is None
    assert spec["transform"]["matrix4x4"] is None


def test_blocked_placement_gate_still_wins():
    candidate = _candidate()
    candidate["status"] = {"state": "pending_asset_match", "reasons": []}

    spec = _spec_with_phi(_phi_result(), candidate=candidate)

    assert spec["status"]["state"] == "transform_blocked"
    assert spec["orientation"] is None
    assert spec["transform"] is None


@pytest.mark.parametrize(
    "phi_result, contract",
    [
        (None, None),
        (
            _phi_result(
                phi_status="unresolved",
                phi_rad=None,
                forward_status="unresolved",
                forward_axis=None,
                reasons=["forward_unresolved"],
            ),
            {"status": "unresolved"},
        ),
        (
            _phi_result(
                phi_status="blocked", phi_rad=None, reasons=["invalid_forward_axis"]
            ),
            SUPPORTED_FORWARD,
        ),
    ],
    ids=["omitted", "unresolved", "blocked"],
)
def test_uncomposed_phi_keeps_final_affine_null(phi_result, contract):
    spec = _spec_with_phi(phi_result, forward_contract=contract)
    transform = spec["transform"]

    assert transform["mesh_alignment_matrix"] is None
    assert transform["final_rotation_matrix"] is None
    assert transform["translation_xyz"] is None
    assert transform["matrix4x4"] is None
    assert spec["status"]["state"] == "pending_mesh_alignment"


# --- 34 - 36. helper validation ------------------------------------------

@pytest.mark.parametrize(
    "bad",
    [
        None,
        "matrix",
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0, 0.0]],
    ],
)
def test_affine_rejects_malformed_matrices(bad):
    with pytest.raises(ValueError, match="must be a 3x3 matrix"):
        _compose_final_affine(bad, R_PLACE_HALF_PI, PIVOT_LOCAL, PIVOT_TARGET)
    with pytest.raises(ValueError, match="must be a 3x3 matrix"):
        _compose_final_affine(R_MESH_HALF_PI, bad, PIVOT_LOCAL, PIVOT_TARGET)


@pytest.mark.parametrize(
    "bad",
    [None, "0,0,0", [1.0, 2.0], [1.0, 2.0, 3.0, 4.0]],
)
def test_affine_rejects_malformed_pivots(bad):
    with pytest.raises(ValueError, match="must be a three-value vector"):
        _compose_final_affine(R_MESH_HALF_PI, R_PLACE_HALF_PI, bad, PIVOT_TARGET)
    with pytest.raises(ValueError, match="must be a three-value vector"):
        _compose_final_affine(R_MESH_HALF_PI, R_PLACE_HALF_PI, PIVOT_LOCAL, bad)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_affine_rejects_non_finite_pivots(bad):
    with pytest.raises(ValueError, match="must be finite"):
        _compose_final_affine(
            R_MESH_HALF_PI, R_PLACE_HALF_PI, [bad, 0.0, 0.0], PIVOT_TARGET
        )


@pytest.mark.parametrize("bad", [True, False])
def test_affine_rejects_bools_as_numbers(bad):
    with pytest.raises(ValueError, match="must be a real number"):
        _compose_final_affine(
            R_MESH_HALF_PI, R_PLACE_HALF_PI, [bad, 0.0, 0.0], PIVOT_TARGET
        )
    with pytest.raises(ValueError, match="must be a real number"):
        _compose_final_affine(
            [[bad, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            R_PLACE_HALF_PI,
            PIVOT_LOCAL,
            PIVOT_TARGET,
        )


def test_matrix_helpers_reject_malformed_inputs():
    with pytest.raises(ValueError, match="must be a 3x3 matrix"):
        _matmul3(R_UP, [[1.0, 0.0, 0.0]])
    with pytest.raises(ValueError, match="must be a three-value vector"):
        _matvec3(R_UP, [1.0, 2.0])


# --- 37 - 45. boundaries --------------------------------------------------

def test_no_numpy_is_used():
    import core.asset.mesh_transform_spec as module

    source = Path(module.__file__).read_text(encoding="utf-8")

    assert "import numpy" not in source
    assert "np." not in source


def test_no_filesystem_access_is_introduced():
    import core.asset.mesh_transform_spec as module

    source = Path(module.__file__).read_text(encoding="utf-8")

    assert "open(" not in source
    assert "Path(" not in source


@pytest.mark.parametrize(
    "module_name, token",
    [
        ("furniture_adapter", "from core.pipeline.adapters.furniture_adapter import"),
        ("mesh_alignment_resolver", "from core.asset.mesh_alignment_resolver import"),
        ("raw_obj_loader", "from core.asset.raw_obj_loader import"),
    ],
)
def test_no_forbidden_module_imports(module_name, token):
    import types

    import core.asset.mesh_transform_spec as module

    source = Path(module.__file__).read_text(encoding="utf-8")

    assert token not in source
    imported = [
        value.__name__
        for value in vars(module).values()
        if isinstance(value, types.ModuleType)
    ]
    assert module_name not in " ".join(imported)


def test_no_vertex_transform_helper_is_introduced():
    import core.asset.mesh_transform_spec as module

    for name in (
        "transform_vertices",
        "apply_transform",
        "world_vertices",
        "vertices_world",
    ):
        assert not hasattr(module, name)


def test_no_scene_insertion_is_introduced():
    import core.asset.mesh_transform_spec as module

    for name in ("insert_asset", "insert_scene_asset", "add_to_scene"):
        assert not hasattr(module, name)

    keys = _all_keys(_affine_spec())
    assert "scene" not in keys
    assert "scene_object" not in keys


def test_no_bounds_recomputation_is_introduced():
    spec = _affine_spec()
    keys = _all_keys(spec)

    assert spec["bounds_after_partial"] is None
    for forbidden in ("bounds_after", "bounds_after_xyz", "transformed_bounds"):
        assert forbidden not in keys


def test_family_semantics_remain_unchanged():
    from core.asset.forward_rule_registry import ForwardRuleRegistry

    rule = ForwardRuleRegistry.load_default().get_forward_rule(
        "seating_and_adult_beds"
    )

    assert rule["semantic_forward_axis"] == "+Z"
    assert rule["status"] == "supported"
    assert rule["status"] != "verified"

    # The +Z family rule still composes the +Z mesh alignment.
    spec = _affine_spec()
    assert spec["orientation"]["forward_axis"] == "+Z"
    _rows_approx(spec["transform"]["mesh_alignment_matrix"], R_MESH_HALF_PI)
