"""Focused tests for the pure vertex transform executor (Phase 3D-AF)."""

import copy
import inspect
import math
from pathlib import Path

import pytest

import core.asset.mesh_transform_executor as executor_module
from core.asset.mesh_transform_executor import execute_mesh_transform
from core.asset.mesh_transform_spec import build_mesh_transform_spec
from core.asset.raw_obj_loader import load_raw_obj


BASIS_VERSION = "diffuscene_y_up_to_architectos_z_up_v1"


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------

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


SUPPORTED_FORWARD = {
    "status": "supported",
    "axis": "+Z",
    "axis_frame": "raw_mesh_local_frame",
    "source": "family_rule",
    "family": "seating_and_adult_beds",
    "evidence": {
        "rule_id": "forward_family_rule_v1",
        "geometry_gate": "agreed",
        "agreement": 0.95,
        "notes": ["seating_and_adult_beds_only", "kids_and_bunk_beds_excluded"],
    },
}


def _valid_spec(mesh=None, yaw=0.0, phi_rad=math.pi / 2.0, forward_axis="+Z"):
    """A REAL TransformSpec built by the production builder (resolved phi)."""

    candidate = _candidate()
    candidate["rotation"]["yaw_rad"] = yaw
    candidate["rotation"]["source_y_rad"] = yaw
    contract = dict(SUPPORTED_FORWARD)
    contract["axis"] = forward_axis

    return build_mesh_transform_spec(
        _loader_result() if mesh is None else mesh,
        candidate,
        forward_contract=contract,
        phi_result=_phi_result(forward_axis=forward_axis, phi_rad=phi_rad),
    )


def _rz(angle):
    c = math.cos(angle)
    s = math.sin(angle)

    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


IDENTITY3 = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _spec(
    rotation=None,
    translation=None,
    scale=(1.0, 1.0, 1.0),
    state="pending_mesh_alignment",
    matrix4x4=None,
    source_frame="raw_mesh_local_frame",
    destination_frame="architectos_world_frame",
    local_center=(0.0, 0.0, 0.0),
    target_center=(0.0, 0.0, 0.0),
):
    """A minimal, directly-controlled TransformSpec-shaped mapping."""

    # Fresh identity per call: callers mutate the returned spec in place, so a
    # shared constant here would leak state between tests.
    rotation = [list(row) for row in IDENTITY3] if rotation is None else rotation
    translation = [0.0, 0.0, 0.0] if translation is None else translation
    if matrix4x4 is None:
        matrix4x4 = [
            [rotation[0][0], rotation[0][1], rotation[0][2], translation[0]],
            [rotation[1][0], rotation[1][1], rotation[1][2], translation[1]],
            [rotation[2][0], rotation[2][1], rotation[2][2], translation[2]],
            [0.0, 0.0, 0.0, 1.0],
        ]

    return {
        "format_version": "mesh_transform_v1",
        "source_mesh_frame": source_frame,
        "destination_frame": destination_frame,
        "mesh_reference": {
            "model_id": "model-a",
            "raw_model_path": "D:/dataset/part1/model-a/raw_model.obj",
        },
        "pivot": {
            "mesh_origin_xyz": [0.0, 0.0, 0.0],
            "local_bbox_center_xyz": list(local_center),
            "target_bbox_center_xyz": list(target_center),
        },
        "transform": {
            "order": [
                "subtract_local_bbox_center",
                "scale",
                "mesh_alignment",
                "placement_rotation",
                "translate_to_target",
            ],
            "scale_xyz": list(scale),
            "up_alignment_matrix": [
                [1.0, 0.0, 0.0],
                [0.0, 0.0, -1.0],
                [0.0, 1.0, 0.0],
            ],
            "mesh_alignment_matrix": None,
            "placement_rotation_matrix": None,
            "final_rotation_matrix": rotation,
            "translation_xyz": translation,
            "matrix4x4": matrix4x4,
        },
        "bounds_before": None,
        "bounds_after_partial": None,
        "rotation_completeness": "placement_only",
        "status": {"state": state, "reasons": []},
    }


def _box_mesh():
    return _loader_result(
        geometry={
            "index_base": 0,
            "vertices_xyz": [
                [0.0, 0.0, 0.0],
                [2.0, 0.0, 0.0],
                [2.0, 1.0, 0.0],
                [0.0, 1.0, 0.0],
            ],
            "faces": [[0, 1, 2, 3]],
        }
    )


def _flat(vertices):
    return [value for vertex in vertices for value in vertex]


def _apply(matrix, vector):
    return [sum(matrix[row][col] * vector[col] for col in range(3)) for row in range(3)]


def _execute(mesh=None, spec=None):
    return execute_mesh_transform(
        _loader_result() if mesh is None else mesh,
        _spec() if spec is None else spec,
    )


# ---------------------------------------------------------------------------
# 1 - 4. transform math
# ---------------------------------------------------------------------------

def test_identity_rotation_and_zero_translation_preserve_vertices():
    mesh = _loader_result()
    out = _execute(mesh=mesh, spec=_spec())

    assert out["status"]["state"] == "transformed_vertices_ready"
    assert _flat(out["geometry"]["vertices_xyz"]) == pytest.approx(
        _flat(mesh["geometry"]["vertices_xyz"]), abs=1e-12
    )


def test_identity_rotation_with_translation_moves_all_vertices():
    mesh = _loader_result()
    out = _execute(mesh=mesh, spec=_spec(translation=[10.0, -2.0, 0.5]))

    expected = [
        [vertex[0] + 10.0, vertex[1] - 2.0, vertex[2] + 0.5]
        for vertex in mesh["geometry"]["vertices_xyz"]
    ]
    assert _flat(out["geometry"]["vertices_xyz"]) == pytest.approx(
        _flat(expected), abs=1e-12
    )


def test_quarter_turn_about_z_maps_basis_points():
    mesh = _loader_result(
        geometry={
            "index_base": 0,
            "vertices_xyz": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "faces": [[0, 1, 2]],
        }
    )
    out = _execute(mesh=mesh, spec=_spec(rotation=_rz(math.pi / 2.0)))
    vertices = out["geometry"]["vertices_xyz"]

    assert vertices[0] == pytest.approx([0.0, 1.0, 0.0], abs=1e-12)
    assert vertices[1] == pytest.approx([-1.0, 0.0, 0.0], abs=1e-12)
    assert vertices[2] == pytest.approx([0.0, 0.0, 1.0], abs=1e-12)


def test_combined_rotation_and_translation():
    rotation = _rz(0.7)
    translation = [1.5, -0.25, 3.0]
    mesh = _loader_result()
    out = _execute(
        mesh=mesh, spec=_spec(rotation=rotation, translation=translation)
    )

    expected = [
        [value + translation[index] for index, value in enumerate(_apply(rotation, vertex))]
        for vertex in mesh["geometry"]["vertices_xyz"]
    ]
    assert _flat(out["geometry"]["vertices_xyz"]) == pytest.approx(
        _flat(expected), abs=1e-12
    )


# ---------------------------------------------------------------------------
# 5 - 10. topology and immutability
# ---------------------------------------------------------------------------

def test_input_vertices_are_not_mutated():
    mesh = _loader_result()
    before = copy.deepcopy(mesh)

    _execute(mesh=mesh, spec=_spec(rotation=_rz(0.9), translation=[1.0, 2.0, 3.0]))

    assert mesh == before


def test_input_faces_are_not_mutated():
    mesh = _box_mesh()
    before = copy.deepcopy(mesh["geometry"]["faces"])

    _execute(mesh=mesh, spec=_spec(rotation=_rz(0.3)))

    assert mesh["geometry"]["faces"] == before


def test_face_index_order_is_preserved():
    faces = [[0, 1, 2], [2, 3, 0], [3, 1, 2]]
    mesh = _loader_result(
        geometry={
            "index_base": 0,
            "vertices_xyz": [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
                [0.0, 1.0, 0.0],
            ],
            "faces": faces,
        }
    )
    out = _execute(mesh=mesh, spec=_spec(rotation=_rz(1.1)))

    assert out["geometry"]["faces"] == faces


def test_ngon_faces_are_preserved():
    mesh = _loader_result(
        geometry={
            "index_base": 0,
            "vertices_xyz": [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.5, 0.5, 0.5],
            ],
            "faces": [[0, 1, 2, 3, 4]],
        }
    )
    out = _execute(mesh=mesh, spec=_spec())

    assert out["geometry"]["faces"] == [[0, 1, 2, 3, 4]]


def test_vertex_and_face_counts_are_preserved():
    mesh = _box_mesh()
    out = _execute(mesh=mesh, spec=_spec(rotation=_rz(0.2)))

    assert out["topology"]["vertex_count"] == len(mesh["geometry"]["vertices_xyz"])
    assert out["topology"]["face_count"] == len(mesh["geometry"]["faces"])
    assert len(out["geometry"]["vertices_xyz"]) == len(
        mesh["geometry"]["vertices_xyz"]
    )
    assert len(out["geometry"]["faces"]) == len(mesh["geometry"]["faces"])


# ---------------------------------------------------------------------------
# 11 - 15. bounds and the center invariant
# ---------------------------------------------------------------------------

def test_transformed_bounds_min():
    out = _execute(mesh=_box_mesh(), spec=_spec(translation=[1.0, 1.0, 1.0]))

    assert out["bounds"]["min_xyz"] == pytest.approx([1.0, 1.0, 1.0], abs=1e-12)


def test_transformed_bounds_max():
    out = _execute(mesh=_box_mesh(), spec=_spec(translation=[1.0, 1.0, 1.0]))

    assert out["bounds"]["max_xyz"] == pytest.approx([3.0, 2.0, 1.0], abs=1e-12)


def test_transformed_bounds_dimensions():
    out = _execute(mesh=_box_mesh(), spec=_spec(translation=[1.0, 1.0, 1.0]))

    assert out["bounds"]["full_dims_xyz"] == pytest.approx([2.0, 1.0, 0.0], abs=1e-12)


def test_transformed_bounds_center():
    out = _execute(mesh=_box_mesh(), spec=_spec(translation=[1.0, 1.0, 1.0]))

    assert out["bounds"]["center_xyz"] == pytest.approx([2.0, 1.5, 1.0], abs=1e-12)


def test_local_bbox_center_maps_to_target_center():
    spec = _valid_spec(yaw=0.6, phi_rad=math.pi / 2.0)
    rotation = spec["transform"]["final_rotation_matrix"]
    translation = spec["transform"]["translation_xyz"]
    c_m = spec["pivot"]["local_bbox_center_xyz"]
    c_w = spec["pivot"]["target_bbox_center_xyz"]

    mapped = [
        value + translation[index]
        for index, value in enumerate(_apply(rotation, c_m))
    ]
    assert mapped == pytest.approx(c_w, abs=1e-9)

    out = execute_mesh_transform(_loader_result(), spec)
    assert out["status"]["state"] == "transformed_vertices_ready"


# ---------------------------------------------------------------------------
# 16 - 19. matrix4x4 consistency
# ---------------------------------------------------------------------------

def test_consistent_matrix4x4_is_accepted():
    out = _execute(spec=_spec(rotation=_rz(0.4), translation=[1.0, 2.0, 3.0]))

    assert out["status"]["state"] == "transformed_vertices_ready"


def test_inconsistent_matrix4x4_rotation_is_rejected():
    bad = _spec()
    bad["transform"]["matrix4x4"][0][0] = 2.0

    with pytest.raises(ValueError, match="upper-left 3x3"):
        _execute(spec=bad)


def test_inconsistent_matrix4x4_translation_is_rejected():
    bad = _spec(translation=[1.0, 0.0, 0.0])
    bad["transform"]["matrix4x4"][0][3] = 5.0

    with pytest.raises(ValueError, match="translation column"):
        _execute(spec=bad)


def test_invalid_homogeneous_last_row_is_rejected():
    bad = _spec()
    bad["transform"]["matrix4x4"][3] = [0.0, 0.0, 0.0, 2.0]

    with pytest.raises(ValueError, match="last row"):
        _execute(spec=bad)


# ---------------------------------------------------------------------------
# 20 - 22. numeric strictness
# ---------------------------------------------------------------------------

def test_non_finite_vertex_is_rejected():
    mesh = _loader_result(
        geometry={
            "index_base": 0,
            "vertices_xyz": [[float("nan"), 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            "faces": [[0, 1, 2]],
        }
    )

    with pytest.raises(ValueError, match="finite"):
        _execute(mesh=mesh, spec=_spec())


def test_non_finite_matrix_is_rejected():
    bad = _spec()
    bad["transform"]["final_rotation_matrix"][0][0] = float("inf")

    with pytest.raises(ValueError, match="finite"):
        _execute(spec=bad)


def test_bool_as_number_is_rejected():
    mesh = _loader_result(
        geometry={
            "index_base": 0,
            "vertices_xyz": [[True, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            "faces": [[0, 1, 2]],
        }
    )

    with pytest.raises(ValueError, match="real number"):
        _execute(mesh=mesh, spec=_spec())


# ---------------------------------------------------------------------------
# 23 - 25. scale and rotation quality
# ---------------------------------------------------------------------------

def test_non_identity_scale_is_blocked():
    out = _execute(spec=_spec(scale=(2.0, 1.0, 1.0)))

    assert out["status"]["state"] == "transform_execution_blocked"
    assert "non_identity_scale_not_executable" in out["status"]["reasons"]
    assert out["geometry"] is None


def test_reflection_matrix_is_rejected():
    reflection = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]]

    with pytest.raises(ValueError, match="proper rotation"):
        _execute(spec=_spec(rotation=reflection))


def test_non_orthonormal_matrix_is_rejected():
    bad = [[1.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 1.0]]

    with pytest.raises(ValueError, match="orthonormal"):
        _execute(spec=_spec(rotation=bad))


# ---------------------------------------------------------------------------
# 26 - 29. malformed inputs
# ---------------------------------------------------------------------------

def test_malformed_rotation_matrix_is_rejected():
    with pytest.raises(ValueError, match="3x3"):
        _execute(
            spec=_spec(
                rotation=[[1.0, 0.0], [0.0, 1.0]],
                matrix4x4=[
                    [1.0, 0.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ],
            )
        )


def test_malformed_matrix4x4_is_rejected():
    with pytest.raises(ValueError, match="4x4"):
        _execute(
            spec=_spec(
                matrix4x4=[
                    [1.0, 0.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0, 0.0],
                ]
            )
        )


def test_empty_vertices_are_rejected():
    mesh = _loader_result(
        geometry={"index_base": 0, "vertices_xyz": [], "faces": []}
    )

    with pytest.raises(ValueError, match="must not be empty"):
        _execute(mesh=mesh, spec=_spec())


@pytest.mark.parametrize(
    "faces",
    [[[0, 1, 99]], [[0, 1.5, 2]], [[0, 1, True]], [[]], "not-a-list"],
    ids=["out-of-range", "float", "bool", "empty-face", "not-a-list"],
)
def test_malformed_face_indices_are_rejected(faces):
    mesh = _loader_result(
        geometry={
            "index_base": 0,
            "vertices_xyz": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            "faces": faces,
        }
    )

    with pytest.raises(ValueError):
        _execute(mesh=mesh, spec=_spec())


def test_non_mapping_arguments_raise():
    with pytest.raises(ValueError, match="mesh_result must be a mapping"):
        execute_mesh_transform(None, _spec())
    with pytest.raises(ValueError, match="transform_spec must be a mapping"):
        execute_mesh_transform(_loader_result(), None)


# ---------------------------------------------------------------------------
# 30 - 33. container freshness and semantics flags
# ---------------------------------------------------------------------------

def test_returned_geometry_is_a_new_container():
    mesh = _loader_result()
    out = _execute(mesh=mesh, spec=_spec(rotation=_rz(0.4)))

    assert out["geometry"]["vertices_xyz"] is not mesh["geometry"]["vertices_xyz"]
    assert out["geometry"]["faces"] is not mesh["geometry"]["faces"]
    assert out["geometry"]["vertices_xyz"][0] is not mesh["geometry"]["vertices_xyz"][0]


def test_reflection_flag_is_false_for_accepted_proper_rotation():
    out = _execute(spec=_spec(rotation=_rz(0.3)))

    assert out["semantics"]["reflection_introduced"] is False
    assert out["semantics"]["position_transform_executed"] is True


def test_no_normals_are_output_or_generated():
    out = _execute(spec=_spec())

    assert out["semantics"]["normals_transformed"] is False
    assert "normals" not in out["geometry"]
    assert "normals_xyz" not in out["geometry"]


def test_face_winding_is_not_reversed():
    mesh = _loader_result(
        geometry={
            "index_base": 0,
            "vertices_xyz": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            "faces": [[0, 1, 2]],
        }
    )
    out = _execute(mesh=mesh, spec=_spec(rotation=_rz(2.0)))

    assert out["semantics"]["face_winding_reversed"] is False
    assert out["geometry"]["faces"] == [[0, 1, 2]]


# ---------------------------------------------------------------------------
# 34 - 37. no double application (structural proof)
# ---------------------------------------------------------------------------

def test_executor_has_no_asset_domain_imports():
    source = inspect.getsource(executor_module)
    import_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    forbidden = (
        "furniture_adapter",
        "mesh_alignment_resolver",
        "asset_forward_resolver",
        "forward_geometry_gate",
        "forward_rule_registry",
        "mesh_transform_spec",
        "raw_obj_loader",
    )

    assert import_lines
    for line in import_lines:
        for name in forbidden:
            assert name not in line


def test_executor_does_not_recompose_any_rotation():
    source = inspect.getsource(executor_module)

    for token in ("math.cos", "math.sin", "math.tan", "math.radians", "math.degrees"):
        assert token not in source


def test_executor_defines_no_hardcoded_transform_matrices():
    for name in (
        "BASIS",
        "BASIS_B",
        "UP_ALIGNMENT_MATRIX",
        "R_UP",
        "IDENTITY_MATRIX",
        "PHI_BY_RAW_FORWARD",
    ):
        assert not hasattr(executor_module, name)


def test_executor_output_depends_only_on_the_final_affine():
    rotation = _rz(0.8)
    translation = [0.5, -1.0, 2.0]
    first = _spec(
        rotation=rotation,
        translation=translation,
        local_center=(0.0, 0.0, 0.0),
        target_center=(9.0, 9.0, 9.0),
    )
    second = _spec(
        rotation=rotation,
        translation=translation,
        local_center=(5.0, 5.0, 5.0),
        target_center=(-9.0, -9.0, -9.0),
    )
    second["orientation"] = {"forward_axis": "+Z", "intrinsic_yaw_phi_rad": 1.23}
    second["mesh_reference"] = {"model_id": "a-completely-different-model"}

    out_first = _execute(spec=first)
    out_second = _execute(spec=second)

    assert out_first["geometry"] == out_second["geometry"]
    assert out_first["bounds"] == out_second["bounds"]


# ---------------------------------------------------------------------------
# 38 - 40. output boundary and determinism
# ---------------------------------------------------------------------------

def test_output_is_not_a_scene_instance():
    out = _execute(spec=_spec())

    assert out["type"] == "transformed_mesh"
    for key in ("scene", "scene_instance", "instance", "room", "renderer"):
        assert key not in out


def test_output_is_not_renderer_ready():
    out = _execute(spec=_spec())

    assert out["status"]["state"] == "transformed_vertices_ready"
    assert "render" not in out["status"]["state"]
    assert "ready_for_render" not in out


def test_repeated_calls_are_deterministic():
    mesh = _loader_result()
    spec = _spec(rotation=_rz(0.35), translation=[1.0, 2.0, 3.0])

    assert _execute(mesh=mesh, spec=spec) == _execute(mesh=mesh, spec=spec)


# ---------------------------------------------------------------------------
# blocked (valid-but-not-executable) states
# ---------------------------------------------------------------------------

def test_spec_without_transform_is_blocked():
    spec = _spec()
    spec["transform"] = None
    spec["status"] = {"state": "transform_blocked", "reasons": ["whatever"]}

    out = _execute(spec=spec)

    assert out["status"]["state"] == "transform_execution_blocked"
    assert "spec_transform_missing" in out["status"]["reasons"]
    assert out["geometry"] is None


def test_non_executable_spec_state_is_blocked():
    out = _execute(spec=_spec(state="pending_scale_contract"))

    assert out["status"]["state"] == "transform_execution_blocked"
    assert out["geometry"] is None


def test_absent_final_affine_is_blocked():
    spec = _spec()
    spec["transform"]["final_rotation_matrix"] = None
    spec["transform"]["translation_xyz"] = None
    spec["transform"]["matrix4x4"] = None

    out = _execute(spec=spec)

    assert out["status"]["state"] == "transform_execution_blocked"
    assert "final_affine_metadata_absent" in out["status"]["reasons"]


def test_unresolved_phi_spec_is_blocked():
    spec = build_mesh_transform_spec(
        _loader_result(), _candidate(), forward_contract=SUPPORTED_FORWARD
    )
    assert spec["transform"]["matrix4x4"] is None

    out = execute_mesh_transform(_loader_result(), spec)

    assert out["status"]["state"] == "transform_execution_blocked"


# ---------------------------------------------------------------------------
# Phase 3D-AH.1: the placement identity is PROPAGATED unchanged
# ---------------------------------------------------------------------------

def _identity(**overrides):
    identity = {
        "status": "resolved",
        "scope": "scene-a",
        "ordinal": 2,
        "source_engine": "DiffuScene",
        "source_slot": 4,
        "instance_id": "scene-a:placement:000002",
    }
    identity.update(overrides)

    return identity


def test_executor_propagates_a_resolved_placement_identity():
    spec = _valid_spec()
    spec["placement_identity"] = _identity()

    out = _execute(spec=spec)

    assert out["status"]["state"] == "transformed_vertices_ready"
    assert out["placement_identity"] == _identity()
    # Propagated, not aliased.
    assert out["placement_identity"] is not spec["placement_identity"]


def test_executor_propagates_an_unresolved_placement_identity():
    spec = _valid_spec()
    spec["placement_identity"] = _identity(
        status="unresolved",
        scope=None,
        instance_id=None,
        reasons=["placement_scope_missing"],
    )

    out = _execute(spec=spec)

    assert out["placement_identity"]["status"] == "unresolved"
    assert out["placement_identity"]["instance_id"] is None


def test_executor_reports_a_null_identity_when_the_spec_has_none():
    out = _execute(spec=_spec())

    assert out["placement_identity"] is None


def test_executor_propagates_identity_on_the_blocked_path():
    spec = _spec(state="pending_scale_contract")
    spec["placement_identity"] = _identity()

    out = _execute(spec=spec)

    assert out["status"]["state"] == "transform_execution_blocked"
    assert out["placement_identity"] == _identity()
    assert out["geometry"] is None


def test_placement_identity_does_not_change_the_transform_result():
    plain = _spec(rotation=_rz(0.5), translation=[1.0, 2.0, 3.0])
    tagged = _spec(rotation=_rz(0.5), translation=[1.0, 2.0, 3.0])
    tagged["placement_identity"] = _identity()

    plain_out = _execute(spec=plain)
    tagged_out = _execute(spec=tagged)

    assert plain_out["geometry"] == tagged_out["geometry"]
    assert plain_out["bounds"] == tagged_out["bounds"]
    assert plain_out["transform"] == tagged_out["transform"]


def test_production_spec_propagates_the_candidate_placement_identity():
    """candidate -> spec -> executor keeps the identity byte-identical."""

    candidate = _candidate()
    candidate["placement_identity"] = _identity()

    spec = build_mesh_transform_spec(
        _loader_result(),
        candidate,
        forward_contract=SUPPORTED_FORWARD,
        phi_result=_phi_result(),
    )
    out = execute_mesh_transform(_loader_result(), spec)

    assert out["status"]["state"] == "transformed_vertices_ready"
    assert spec["placement_identity"] == _identity()
    assert out["placement_identity"] == _identity()


def test_same_model_at_two_ordinals_yields_distinct_propagated_ids():
    outputs = []
    for ordinal in (0, 1):
        candidate = _candidate()
        candidate["placement_identity"] = _identity(
            ordinal=ordinal,
            instance_id=f"scene-a:placement:{ordinal:06d}",
        )
        spec = build_mesh_transform_spec(
            _loader_result(),
            candidate,
            forward_contract=SUPPORTED_FORWARD,
            phi_result=_phi_result(),
        )
        outputs.append(execute_mesh_transform(_loader_result(), spec))

    assert outputs[0]["source"]["model_id"] == outputs[1]["source"]["model_id"]
    assert outputs[0]["placement_identity"]["instance_id"] != (
        outputs[1]["placement_identity"]["instance_id"]
    )


# ---------------------------------------------------------------------------
# ONE real 3D-FUTURE mesh execution test
# ---------------------------------------------------------------------------

REAL_ROOT = Path(r"D:\AI_Architecture_Lab\3D-FUTURE-model")
REAL_MODEL_ID = "27059911-89f4-3e78-a511-4c9b8cf51fb3"
REAL_OBJ = REAL_ROOT / "3D-FUTURE-model-part1" / REAL_MODEL_ID / "raw_model.obj"


@pytest.mark.skipif(not REAL_OBJ.is_file(), reason="real 3D-FUTURE asset absent")
def test_real_3d_future_mesh_transform_executes():
    mesh = load_raw_obj(
        {
            "source": "3D-FUTURE",
            "model_id": REAL_MODEL_ID,
            "raw_model_path": str(REAL_OBJ),
        },
        allowed_roots=[REAL_ROOT],
    )
    assert mesh["status"]["state"] == "mesh_loaded_valid"

    spec = _valid_spec(mesh=mesh, yaw=0.4, phi_rad=math.pi / 2.0)
    assert spec["transform"]["matrix4x4"] is not None

    raw_vertices = copy.deepcopy(mesh["geometry"]["vertices_xyz"])
    raw_faces = copy.deepcopy(mesh["geometry"]["faces"])

    out = execute_mesh_transform(mesh, spec)

    assert out["status"]["state"] == "transformed_vertices_ready"
    assert len(out["geometry"]["vertices_xyz"]) == len(raw_vertices)
    assert len(out["geometry"]["faces"]) == len(raw_faces)
    assert out["geometry"]["faces"] == raw_faces

    rotation = spec["transform"]["final_rotation_matrix"]
    translation = spec["transform"]["translation_xyz"]
    for index in (0, 1, len(raw_vertices) // 2, len(raw_vertices) - 1):
        expected = [
            value + translation[row]
            for row, value in enumerate(_apply(rotation, raw_vertices[index]))
        ]
        assert out["geometry"]["vertices_xyz"][index] == pytest.approx(
            expected, abs=1e-9
        )

    for key in ("min_xyz", "max_xyz", "center_xyz", "full_dims_xyz"):
        assert all(math.isfinite(value) for value in out["bounds"][key])

    c_m = spec["pivot"]["local_bbox_center_xyz"]
    c_w = spec["pivot"]["target_bbox_center_xyz"]
    mapped = [
        value + translation[index]
        for index, value in enumerate(_apply(rotation, c_m))
    ]
    assert mapped == pytest.approx(c_w, abs=1e-9)

    # no source mutation
    assert mesh["geometry"]["vertices_xyz"] == raw_vertices
    assert mesh["geometry"]["faces"] == raw_faces
