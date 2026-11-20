"""Focused tests for the pure intrinsic yaw (phi) resolver (Phase 3D-Y)."""

import copy
import inspect
import math
from pathlib import Path

import pytest

from core.asset.mesh_alignment_resolver import (
    PHI_BY_RAW_FORWARD,
    PHI_STATUS_BLOCKED,
    PHI_STATUS_RESOLVED,
    PHI_STATUS_UNRESOLVED,
    SUPPORTED_WORLD_ZERO_FACING_AXIS,
    resolve_intrinsic_yaw_phi,
)
from core.asset.mesh_transform_spec import (
    FORWARD_AXES,
    WORLD_ZERO_FACING_FRAME,
    build_mesh_transform_spec,
)

RAW_FRAME = "raw_mesh_local_frame"

R_UP = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]
RAW_FORWARD_VECTORS = {
    "+X": [1.0, 0.0, 0.0],
    "-X": [-1.0, 0.0, 0.0],
    "+Z": [0.0, 0.0, 1.0],
    "-Z": [0.0, 0.0, -1.0],
}


def _matmul(left, right):
    return [
        [sum(left[row][k] * right[k][col] for k in range(3)) for col in range(3)]
        for row in range(3)
    ]


def _matvec(matrix, vector):
    return [sum(matrix[row][k] * vector[k] for k in range(3)) for row in range(3)]


def _rz(phi):
    return [
        [math.cos(phi), -math.sin(phi), 0.0],
        [math.sin(phi), math.cos(phi), 0.0],
        [0.0, 0.0, 1.0],
    ]


def _contract(axis="+Z", status="supported", **overrides):
    contract = {
        "status": status,
        "axis": axis,
        "axis_frame": RAW_FRAME,
        "source": "family_rule",
        "family": "seating_and_adult_beds",
        "evidence": {
            "rule_id": "forward_family_rule_v1",
            "geometry_gate": "agreed",
            "agreement": 0.95,
            "notes": [],
        },
    }
    contract.update(overrides)

    return contract


def _no_forward(status):
    return {
        "status": status,
        "axis": None,
        "axis_frame": RAW_FRAME,
        "source": "none",
        "family": None,
        "evidence": {
            "rule_id": None,
            "geometry_gate": "not_evaluated",
            "agreement": None,
            "notes": [],
        },
    }


def _resolve(contract, up="verified", world=SUPPORTED_WORLD_ZERO_FACING_AXIS):
    return resolve_intrinsic_yaw_phi(
        forward_contract=contract,
        up_alignment_status=up,
        world_zero_facing_axis=world,
    )


# ---------------------------------------------------------------------------
# 1 - 4. phi lookup values
# ---------------------------------------------------------------------------

def test_plus_x_forward_yields_phi_zero():
    result = _resolve(_contract("+X"))

    assert result["phi_status"] == PHI_STATUS_RESOLVED
    assert result["phi_rad"] == 0.0


def test_minus_x_forward_yields_phi_pi():
    result = _resolve(_contract("-X"))

    assert result["phi_status"] == PHI_STATUS_RESOLVED
    assert result["phi_rad"] == pytest.approx(math.pi)


def test_plus_z_forward_yields_phi_plus_half_pi():
    result = _resolve(_contract("+Z"))

    assert result["phi_status"] == PHI_STATUS_RESOLVED
    assert result["phi_rad"] == pytest.approx(math.pi / 2.0)


def test_minus_z_forward_yields_phi_minus_half_pi():
    result = _resolve(_contract("-Z"))

    assert result["phi_status"] == PHI_STATUS_RESOLVED
    assert result["phi_rad"] == pytest.approx(-math.pi / 2.0)


def test_phi_table_covers_exactly_the_permitted_forward_axes():
    assert set(PHI_BY_RAW_FORWARD) == set(FORWARD_AXES)


# ---------------------------------------------------------------------------
# 5. direct matrix verification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("axis", ["+X", "-X", "+Z", "-Z"])
def test_matrix_verification_maps_every_raw_forward_onto_world_plus_x(axis):
    phi = _resolve(_contract(axis))["phi_rad"]

    aligned = _matvec(_matmul(_rz(phi), R_UP), RAW_FORWARD_VECTORS[axis])

    assert aligned == pytest.approx([1.0, 0.0, 0.0], abs=1e-12)


def test_matrix_verification_confirms_r_up_semantics():
    assert _matvec(R_UP, [0.0, 1.0, 0.0]) == pytest.approx([0.0, 0.0, 1.0])
    assert _matvec(R_UP, [1.0, 0.0, 0.0]) == pytest.approx([1.0, 0.0, 0.0])
    assert _matvec(R_UP, [0.0, 0.0, 1.0]) == pytest.approx([0.0, -1.0, 0.0])
    assert _matvec(R_UP, [0.0, 0.0, -1.0]) == pytest.approx([0.0, 1.0, 0.0])


def test_phi_is_unique_modulo_two_pi():
    for axis in FORWARD_AXES:
        phi = _resolve(_contract(axis))["phi_rad"]
        shifted = _matvec(_matmul(_rz(phi + 2 * math.pi), R_UP), RAW_FORWARD_VECTORS[axis])
        assert shifted == pytest.approx([1.0, 0.0, 0.0], abs=1e-12)


# ---------------------------------------------------------------------------
# 6 - 8. no forward => no phi
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["unresolved", "unobservable", "ambiguous", "unsupported"])
def test_no_forward_status_yields_unresolved_phi(status):
    result = _resolve(_no_forward(status))

    assert result["phi_status"] == PHI_STATUS_UNRESOLVED
    assert result["phi_rad"] is None
    assert result["reasons"] == [f"forward_{status}"]


# ---------------------------------------------------------------------------
# 9 - 11. verified status, invalid and missing axis
# ---------------------------------------------------------------------------

def test_verified_status_with_a_valid_axis_is_accepted():
    result = _resolve(_contract("+Z", status="verified"))

    assert result["phi_status"] == PHI_STATUS_RESOLVED
    assert result["phi_rad"] == pytest.approx(math.pi / 2.0)


@pytest.mark.parametrize("axis", ["+Y", "-Y", "X", "forward", ""])
def test_invalid_axis_is_blocked(axis):
    result = _resolve(_contract(axis))

    assert result["phi_status"] == PHI_STATUS_BLOCKED
    assert result["phi_rad"] is None
    assert result["reasons"] == ["invalid_forward_axis"]


def test_missing_axis_is_blocked_for_supported_status():
    result = _resolve(_contract(None))

    assert result["phi_status"] == PHI_STATUS_BLOCKED
    assert result["phi_rad"] is None
    assert result["reasons"] == ["invalid_forward_axis"]


def test_non_string_axis_is_rejected_as_malformed():
    with pytest.raises(ValueError, match="axis must be a string or None"):
        _resolve(_contract(3))


# ---------------------------------------------------------------------------
# 12 - 13. precondition blockers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("up", ["unresolved", "pending", "", "VERIFIED"])
def test_unverified_up_alignment_is_blocked(up):
    result = _resolve(_contract("+Z"), up=up)

    assert result["phi_status"] == PHI_STATUS_BLOCKED
    assert result["phi_rad"] is None
    assert result["reasons"] == ["up_alignment_not_verified"]


def test_non_string_up_alignment_is_rejected():
    with pytest.raises(ValueError, match="up_alignment_status must be a string"):
        _resolve(_contract("+Z"), up=None)


@pytest.mark.parametrize("world", ["+Y", "-X", "world_+X", ""])
def test_unsupported_world_zero_facing_axis_is_blocked(world):
    result = _resolve(_contract("+Z"), world=world)

    assert result["phi_status"] == PHI_STATUS_BLOCKED
    assert result["phi_rad"] is None
    assert result["reasons"] == ["world_zero_facing_axis_unsupported"]


def test_non_string_world_zero_facing_axis_is_rejected():
    with pytest.raises(ValueError, match="world_zero_facing_axis must be a string"):
        _resolve(_contract("+Z"), world=1)


def test_default_world_zero_facing_axis_is_world_plus_x():
    result = _resolve(_contract("+Z"))

    assert SUPPORTED_WORLD_ZERO_FACING_AXIS == "+X"
    assert result["world_zero_facing_axis"] == "+X"
    assert result["world_zero_facing_axis_frame"] == "architectos_world_frame"
    assert WORLD_ZERO_FACING_FRAME == "architectos_world_frame"


def test_old_zero_facing_axis_keyword_is_rejected():
    """The old frame-blind keyword must fail visibly, with no alias retained."""

    with pytest.raises(TypeError, match="zero_facing_axis"):
        resolve_intrinsic_yaw_phi(
            forward_contract=_contract("+Z"),
            up_alignment_status="verified",
            zero_facing_axis="+X",
        )


def test_raw_and_world_facing_cannot_be_mixed():
    """The raw semantic facing and the world target are separate, tagged values."""

    result = _resolve(_contract("+Z"), world="+X")

    assert result["phi_rad"] == pytest.approx(math.pi / 2)

    assert result["forward_axis"] == "+Z"
    assert result["forward_axis_frame"] == "raw_mesh_local_frame"
    assert result["world_zero_facing_axis"] == "+X"
    assert result["world_zero_facing_axis_frame"] == "architectos_world_frame"

    # Different values, different frames: they cannot be confused.
    assert result["world_zero_facing_axis"] != result["forward_axis"]
    assert result["forward_axis_frame"] != result["world_zero_facing_axis_frame"]


# ---------------------------------------------------------------------------
# 14 - 16. frame and structural validation
# ---------------------------------------------------------------------------

def test_missing_axis_frame_raises():
    contract = _contract("+Z")
    del contract["axis_frame"]

    with pytest.raises(ValueError, match="is missing: axis_frame"):
        _resolve(contract)


@pytest.mark.parametrize("frame", ["architectos_world_frame", "world_frame", "", None])
def test_wrong_axis_frame_raises(frame):
    with pytest.raises(ValueError, match="axis_frame must be"):
        _resolve(_contract("+Z", axis_frame=frame))


def test_malformed_frame_raises_even_when_forward_is_unresolved():
    contract = _no_forward("unresolved")
    contract["axis_frame"] = "architectos_world_frame"

    with pytest.raises(ValueError, match="axis_frame must be"):
        _resolve(contract)


@pytest.mark.parametrize("contract", [None, "supported", [], 3])
def test_malformed_contract_raises(contract):
    with pytest.raises(ValueError, match="forward_contract must be a mapping"):
        _resolve(contract)


def test_unknown_contract_field_raises():
    with pytest.raises(ValueError, match="unknown forward_contract field"):
        _resolve(_contract("+Z", phi=0.0))


def test_unknown_status_raises():
    with pytest.raises(ValueError, match="status must be one of"):
        _resolve(_contract("+Z", status="maybe"))


# ---------------------------------------------------------------------------
# 17 - 21. anti-inversion and boundary
# ---------------------------------------------------------------------------

def test_signature_accepts_only_orientation_metadata():
    parameters = inspect.signature(resolve_intrinsic_yaw_phi).parameters

    assert set(parameters) == {
        "forward_contract",
        "up_alignment_status",
        "world_zero_facing_axis",
    }
    for forbidden in (
        "vertices",
        "vertices_xyz",
        "mesh",
        "mesh_result",
        "geometry_evidence",
        "expected_geometry_direction",
        "category",
        "family_id",
        "registry",
        "path",
        "asset_path",
    ):
        assert forbidden not in parameters


def test_no_forbidden_imports_in_the_resolver_module():
    import core.asset.mesh_alignment_resolver as module

    source = Path(module.__file__).read_text(encoding="utf-8")

    for token in (
        "forward_geometry_gate",
        "asset_forward_resolver",
        "forward_rule_registry",
        "raw_obj_loader",
        "furniture_adapter",
        "FurnitureAdapter",
        "measure_upper_structure",
        "evaluate_geometry_agreement",
        "ForwardRuleRegistry",
        "load_raw_obj",
    ):
        assert token not in source

    # The module docstring names the forbidden derivation in prose, so the
    # parameter itself is checked structurally instead.
    assert "def resolve_intrinsic_yaw_phi" in source
    assert not hasattr(module, "expected_geometry_direction")


def test_resolver_does_not_expose_geometry_helpers():
    import core.asset.mesh_alignment_resolver as module

    assert not hasattr(module, "measure_upper_structure")
    assert not hasattr(module, "evaluate_geometry_agreement")
    assert not hasattr(module, "ForwardRuleRegistry")


def test_resolver_has_no_filesystem_access(monkeypatch):
    import builtins

    def _forbidden(*args, **kwargs):
        raise AssertionError("the phi resolver must not touch the filesystem")

    monkeypatch.setattr(builtins, "open", _forbidden)

    assert _resolve(_contract("+Z"))["phi_rad"] == pytest.approx(math.pi / 2.0)


def test_same_contract_always_yields_the_same_phi():
    contract = _contract("+Z")

    first = _resolve(contract)
    second = _resolve(contract)
    third = _resolve(copy.deepcopy(contract))

    assert first == second == third


def test_phi_does_not_depend_on_anything_outside_the_signature():
    """There is no geometry parameter, so anti-inversion is structural.

    The only variability available to a caller is the contract, the up-alignment
    status and the zero-facing axis; changing unrelated evidence content must not
    move phi.
    """

    base = _contract("+Z")
    other = _contract("+Z")
    other["evidence"] = {
        "rule_id": "a_different_rule",
        "geometry_gate": "disagreed",
        "agreement": 0.5,
        "notes": ["completely_different_evidence"],
    }
    other["source"] = "geometry_measured"
    other["family"] = "some_other_family"

    assert _resolve(base)["phi_rad"] == _resolve(other)["phi_rad"]


# ---------------------------------------------------------------------------
# 22 - 27. output purity and immutability
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


def test_output_has_no_matrix_translation_vertices_or_placement_yaw():
    result = _resolve(_contract("+Z"))
    keys = _all_keys(result)

    for forbidden in (
        "mesh_alignment_matrix",
        "matrix4x4",
        "matrix",
        "translation_xyz",
        "translation",
        "vertices_xyz",
        "faces",
        "yaw_rad",
        "placement_rotation_matrix",
        "rotation",
    ):
        assert forbidden not in keys

    assert set(result) == {
        "phi_status",
        "phi_rad",
        "forward_status",
        "forward_axis",
        "forward_axis_frame",
        "world_zero_facing_axis",
        "world_zero_facing_axis_frame",
        "reasons",
    }
    assert "zero_facing_axis" not in result


def test_resolver_does_not_mutate_the_forward_contract():
    contract = _contract("+Z")
    before = copy.deepcopy(contract)

    _resolve(contract)

    assert contract == before


def test_resolver_does_not_mutate_the_lookup_table():
    before = dict(PHI_BY_RAW_FORWARD)

    _resolve(_contract("-Z"))

    assert dict(PHI_BY_RAW_FORWARD) == before


# ---------------------------------------------------------------------------
# 28 - 29. orientation frame mirror
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


def _candidate(yaw=0.0):
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
        "rotation": {"yaw_rad": yaw, "axis": "+Z", "mapping_status": "resolved"},
        "scale": {"policy": "no_deformation", "scale_xyz": [1.0, 1.0, 1.0]},
        "status": {"state": "ready_transform_metadata", "reasons": []},
    }


def test_orientation_carries_the_forward_axis_frame():
    spec = build_mesh_transform_spec(
        _loader_result(), _candidate(), forward_contract=_contract("+Z")
    )

    assert spec["orientation"]["forward_axis_frame"] == RAW_FRAME
    assert spec["orientation"]["forward_axis"] == "+Z"


def test_default_orientation_carries_the_frame_tag():
    spec = build_mesh_transform_spec(_loader_result(), _candidate())

    assert spec["orientation"]["forward_status"] == "unresolved"
    assert spec["orientation"]["forward_axis"] is None
    assert spec["orientation"]["forward_axis_frame"] == RAW_FRAME


# ---------------------------------------------------------------------------
# 30 - 34. execution boundary
# ---------------------------------------------------------------------------

def test_transform_spec_still_leaves_phi_and_matrices_null():
    spec = build_mesh_transform_spec(
        _loader_result(), _candidate(), forward_contract=_contract("+Z")
    )

    assert spec["orientation"]["intrinsic_yaw_phi_rad"] is None
    assert spec["orientation"]["intrinsic_yaw_status"] == "unresolved"
    assert spec["orientation"]["world_zero_facing_axis"] == "+X"
    assert spec["orientation"]["world_zero_facing_axis_frame"] == (
        "architectos_world_frame"
    )
    assert spec["transform"]["mesh_alignment_matrix"] is None
    assert spec["transform"]["matrix4x4"] is None
    assert spec["transform"]["translation_xyz"] is None
    assert spec["rotation_completeness"] == "placement_only"
    assert spec["status"]["state"] == "pending_mesh_alignment"


def test_resolved_phi_is_not_injected_into_the_transform_spec():
    phi = _resolve(_contract("+Z"))
    assert phi["phi_status"] == PHI_STATUS_RESOLVED

    spec = build_mesh_transform_spec(
        _loader_result(), _candidate(), forward_contract=_contract("+Z")
    )

    # The phi metadata is deliberately NOT written into the spec in this phase.
    assert spec["orientation"]["intrinsic_yaw_phi_rad"] is None
    assert spec["orientation"]["intrinsic_yaw_phi_rad"] != phi["phi_rad"]


def test_placement_yaw_is_unchanged_and_separate_from_phi():
    spec = build_mesh_transform_spec(
        _loader_result(),
        _candidate(yaw=math.pi / 2),
        forward_contract=_contract("+Z"),
    )
    transform = spec["transform"]

    assert transform["up_alignment_matrix"] == R_UP
    assert transform["placement_rotation_matrix"][2] == [0.0, 0.0, 1.0]
    assert transform["placement_rotation_matrix"][0] == pytest.approx(
        [0.0, -1.0, 0.0]
    )
    assert transform["placement_rotation_matrix"][1] == pytest.approx(
        [1.0, 0.0, 0.0]
    )
    assert "yaw_rad" not in _all_keys(_resolve(_contract("+Z")))


def test_placement_yaw_and_phi_compose_additively_without_being_merged():
    phi = _resolve(_contract("+Z"))["phi_rad"]
    yaw = 0.7

    composed = _matmul(_rz(yaw), _rz(phi))

    for index in range(3):
        assert composed[index] == pytest.approx(_rz(yaw + phi)[index])

    # Production code keeps them in separate fields: phi intrinsic, yaw placed.
    spec = build_mesh_transform_spec(
        _loader_result(), _candidate(yaw=yaw), forward_contract=_contract("+Z")
    )
    expected = _rz(yaw)
    for index in range(3):
        assert spec["transform"]["placement_rotation_matrix"][index] == pytest.approx(
            expected[index]
        )
    assert spec["orientation"]["intrinsic_yaw_phi_rad"] is None


def test_phi_status_vocabulary_matches_the_transform_spec():
    """The spec duplicates the phi vocabulary to avoid importing this module."""

    from core.asset import mesh_transform_spec as spec

    assert tuple(spec.PHI_STATUSES) == (
        PHI_STATUS_RESOLVED,
        PHI_STATUS_UNRESOLVED,
        PHI_STATUS_BLOCKED,
    )
    assert spec.PHI_STATUS_RESOLVED == PHI_STATUS_RESOLVED
    assert spec.PHI_STATUS_BLOCKED == PHI_STATUS_BLOCKED


def test_up_alignment_matrix_is_not_the_adapter_basis_by_import():
    """R_up is numerically equal to the adapter basis B, but must not be reused.

    The resolver module must not import FurnitureAdapter or its basis.
    """

    import core.asset.mesh_alignment_resolver as module

    source = Path(module.__file__).read_text(encoding="utf-8")

    assert "FurnitureAdapter" not in source
    assert "_BASIS_VERSION" not in source
    assert "already_applied" not in source
