"""Focused tests for the strict asset scene-instance container (Phase 3D-AH)."""

import copy
import inspect
import math
from pathlib import Path

import pytest

import core.asset.asset_scene_instance as instance_module
from core.asset.asset_scene_instance import build_asset_scene_instance
from core.asset.mesh_transform_spec import build_mesh_transform_spec
from core.asset.mesh_transform_executor import execute_mesh_transform
from core.asset.raw_obj_loader import load_raw_obj


BASIS_VERSION = "diffuscene_y_up_to_architectos_z_up_v1"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _transformed_mesh(**overrides):
    """A valid, world-space ``transformed_mesh`` (already transformed)."""

    result = {
        "type": "transformed_mesh",
        "source": {
            "source": "3D-FUTURE",
            "model_id": "model-a",
            "raw_model_path": "D:/dataset/part1/model-a/raw_model.obj",
        },
        "frames": {
            "source": "raw_mesh_local_frame",
            "destination": "architectos_world_frame",
        },
        # Phase 3D-AH.1: the executor propagates the placement identity, so a
        # real ``transformed_mesh`` always carries this block. It is the scene
        # instance identity source - NOT model_id.
        "placement_identity": {
            "status": "resolved",
            "scope": "scene-a",
            "ordinal": 0,
            "source_engine": "DiffuScene",
            "source_slot": 3,
            "instance_id": "scene-a:placement:000000",
        },
        "geometry": {
            "vertices_xyz": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [0.0, 0.0, 0.0]],
            "faces": [[0, 1, 2]],
        },
        "bounds": {
            "min_xyz": [0.0, 0.0, 0.0],
            "max_xyz": [4.0, 5.0, 6.0],
            "center_xyz": [2.0, 2.5, 3.0],
            "full_dims_xyz": [4.0, 5.0, 6.0],
        },
        "transform": {
            "final_rotation_matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "translation_xyz": [0.0, 0.0, 0.0],
            "matrix4x4": [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            "scale_xyz": [1.0, 1.0, 1.0],
        },
        "topology": {
            "face_order_preserved": True,
            "vertex_count": 3,
            "face_count": 1,
        },
        "semantics": {
            "position_transform_executed": True,
            "reflection_introduced": False,
            "normals_transformed": False,
            "face_winding_reversed": False,
            "external_raw_frame_handedness_inferred": False,
        },
        "status": {"state": "transformed_vertices_ready", "reasons": []},
    }
    result.update(overrides)

    return result


def _without(key, **overrides):
    mesh = _transformed_mesh(**overrides)
    del mesh[key]

    return mesh


def _build(mesh=None, **kwargs):
    return build_asset_scene_instance(
        _transformed_mesh() if mesh is None else mesh, **kwargs
    )


# ---------------------------------------------------------------------------
# positive contract
# ---------------------------------------------------------------------------

def test_minimal_instance_has_the_expected_shape():
    instance = _build()

    assert instance["type"] == "asset_scene_instance"
    assert instance["version"] == "asset_scene_instance_v1"
    assert instance["status"] == {"state": "scene_instance_ready", "reasons": []}
    assert sorted(instance.keys()) == [
        "asset",
        "bounds",
        "classification",
        "frames",
        "geometry",
        "instance_id",
        "material",
        "provenance",
        "scene_transform",
        "status",
        "support",
        "topology",
        "type",
        "units",
        "version",
    ]


def test_geometry_keeps_the_asset_domain_key():
    instance = _build()

    assert sorted(instance["geometry"].keys()) == ["faces", "vertices_xyz"]
    assert "vertices" not in instance["geometry"]


def test_instance_id_comes_from_the_propagated_placement_identity():
    """The old ``source:model_id`` default is gone (Phase 3D-AH.1).

    ``model_id`` is ASSET MODEL identity; the scene instance identity is the
    resolved placement identity propagated by the executor.
    """

    instance = _build()

    assert instance["instance_id"] == "scene-a:placement:000000"
    assert instance["instance_id"] != "3d_future:model-a"
    # model_id is preserved separately as ASSET MODEL identity.
    assert instance["asset"]["model_id"] == "model-a"


def test_supplied_instance_id_is_preserved_exactly():
    """An explicit instance_id is allowed when no resolved identity is present."""

    mesh = _transformed_mesh()
    mesh["placement_identity"] = {
        "status": "unresolved",
        "scope": None,
        "ordinal": 0,
        "source_engine": "DiffuScene",
        "source_slot": None,
        "instance_id": None,
        "reasons": ["placement_scope_missing"],
    }

    instance = build_asset_scene_instance(mesh, instance_id="custom-id-123")

    assert instance["instance_id"] == "custom-id-123"


def test_classification_defaults_to_none():
    instance = _build()

    assert instance["classification"] == {"category": None, "slot": None}


def test_classification_values_are_preserved():
    instance = _build(category="chair", slot="slot-3")

    assert instance["classification"] == {"category": "chair", "slot": "slot-3"}


def test_default_units_material_support_are_truthful():
    instance = _build()

    assert instance["units"] == {"status": "unspecified"}
    assert instance["material"] == {"status": "unresolved"}
    assert instance["support"] == {"status": "unresolved"}


def test_supplied_units_material_support_are_copied_verbatim():
    instance = _build(
        units={"status": "assumed_meters"},
        material={"status": "unresolved", "mtllib": "model.mtl"},
        support={"status": "unresolved", "contact_z": None},
    )

    assert instance["units"] == {"status": "assumed_meters"}
    assert instance["material"]["mtllib"] == "model.mtl"
    assert instance["support"]["contact_z"] is None


def test_provenance_carries_the_executor_blocks():
    mesh = _transformed_mesh()
    instance = _build(mesh=mesh)

    assert instance["provenance"]["executor_transform"] == mesh["transform"]
    assert instance["provenance"]["executor_semantics"] == mesh["semantics"]
    assert instance["provenance"]["executor_status"] == mesh["status"]


def test_frames_are_declared_world_space():
    instance = _build()

    assert instance["frames"] == {
        "geometry_frame": "architectos_world_frame",
        "scene_transform_frame": "architectos_world_frame",
    }


# ---------------------------------------------------------------------------
# 20. validation edge cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [None, "x", 3, []])
def test_non_mapping_input_is_rejected(bad):
    with pytest.raises(ValueError, match="transformed_mesh must be a mapping"):
        build_asset_scene_instance(bad)


def test_wrong_type_is_rejected():
    with pytest.raises(ValueError, match="type must be 'transformed_mesh'"):
        _build(_transformed_mesh(type="something_else"))


def test_wrong_status_is_rejected():
    with pytest.raises(ValueError, match="transformed_vertices_ready"):
        _build(_transformed_mesh(status={"state": "pending"}))


def test_wrong_destination_frame_is_rejected():
    with pytest.raises(ValueError, match="architectos_world_frame"):
        _build(
            _transformed_mesh(
                frames={
                    "source": "raw_mesh_local_frame",
                    "destination": "some_other_frame",
                }
            )
        )


@pytest.mark.parametrize(
    "block",
    ["source", "frames", "geometry", "bounds", "transform", "topology", "semantics", "status"],
)
def test_missing_required_block_is_rejected(block):
    with pytest.raises(ValueError, match="is missing"):
        build_asset_scene_instance(_without(block))


def test_missing_geometry_mapping_is_rejected():
    with pytest.raises(ValueError, match="geometry must be a mapping"):
        _build(_transformed_mesh(geometry=None))


def test_missing_vertices_xyz_is_rejected():
    with pytest.raises(ValueError, match="missing: vertices_xyz"):
        _build(_transformed_mesh(geometry={"faces": [[0, 1, 2]]}))


def test_missing_faces_is_rejected():
    with pytest.raises(ValueError, match="missing: faces"):
        _build(_transformed_mesh(geometry={"vertices_xyz": [[0.0, 0.0, 0.0]]}))


@pytest.mark.parametrize(
    "vertices",
    [[[1.0, 2.0]], [[1.0, 2.0, 3.0], [float("nan"), 0.0, 0.0]], "nope", [], [[True, 0.0, 0.0]]],
    ids=["short-vertex", "nan", "not-a-list", "empty", "bool"],
)
def test_malformed_vertices_are_rejected(vertices):
    with pytest.raises(ValueError):
        _build(_transformed_mesh(geometry={"vertices_xyz": vertices, "faces": []}))


@pytest.mark.parametrize(
    "faces",
    ["nope", [[0, 1.5]], [[]], [[0, 1, True]]],
    ids=["not-a-list", "float", "empty-face", "bool"],
)
def test_malformed_faces_container_is_rejected(faces):
    with pytest.raises(ValueError):
        _build(
            _transformed_mesh(
                geometry={"vertices_xyz": [[0.0, 0.0, 0.0]], "faces": faces}
            )
        )


def test_topology_vertex_count_mismatch_is_rejected():
    with pytest.raises(ValueError, match="vertex_count"):
        _build(
            _transformed_mesh(
                topology={"face_order_preserved": True, "vertex_count": 9, "face_count": 1}
            )
        )


def test_topology_face_count_mismatch_is_rejected():
    with pytest.raises(ValueError, match="face_count"):
        _build(
            _transformed_mesh(
                topology={"face_order_preserved": True, "vertex_count": 3, "face_count": 9}
            )
        )


def test_face_order_not_preserved_is_rejected():
    with pytest.raises(ValueError, match="face_order_preserved"):
        _build(
            _transformed_mesh(
                topology={"face_order_preserved": False, "vertex_count": 3, "face_count": 1}
            )
        )


def test_missing_bounds_mapping_is_rejected():
    with pytest.raises(ValueError, match="bounds must be a mapping"):
        _build(_transformed_mesh(bounds=None))


def test_non_finite_bounds_value_is_rejected():
    with pytest.raises(ValueError, match="finite"):
        _build(
            _transformed_mesh(
                bounds={
                    "min_xyz": [0.0, 0.0, 0.0],
                    "max_xyz": [4.0, float("inf"), 6.0],
                    "center_xyz": [2.0, 2.5, 3.0],
                    "full_dims_xyz": [4.0, 5.0, 6.0],
                }
            )
        )


def test_max_below_min_is_rejected():
    with pytest.raises(ValueError, match="max_xyz"):
        _build(
            _transformed_mesh(
                bounds={
                    "min_xyz": [5.0, 0.0, 0.0],
                    "max_xyz": [4.0, 5.0, 6.0],
                    "center_xyz": [2.0, 2.5, 3.0],
                    "full_dims_xyz": [4.0, 5.0, 6.0],
                }
            )
        )


def test_negative_full_dimension_is_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        _build(
            _transformed_mesh(
                bounds={
                    "min_xyz": [0.0, 0.0, 0.0],
                    "max_xyz": [4.0, 5.0, 6.0],
                    "center_xyz": [2.0, 2.5, 3.0],
                    "full_dims_xyz": [-1.0, 5.0, 6.0],
                }
            )
        )


@pytest.mark.parametrize(
    "transform",
    [
        {"final_rotation_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "translation_xyz": [0, 0, 0]},
        {"matrix4x4": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], "translation_xyz": [0, 0, 0]},
        {"matrix4x4": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], "final_rotation_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
    ],
    ids=["missing-matrix4x4", "missing-rotation", "missing-translation"],
)
def test_missing_transform_parts_are_rejected(transform):
    with pytest.raises(ValueError, match="is required"):
        _build(_transformed_mesh(transform=transform))


def test_non_identity_scale_is_rejected():
    mesh = _transformed_mesh()
    mesh["transform"]["scale_xyz"] = [2.0, 1.0, 1.0]

    with pytest.raises(ValueError, match="scale_xyz must be identity"):
        build_asset_scene_instance(mesh)


@pytest.mark.parametrize("bad", ["", "   ", None, 3])
def test_empty_source_is_rejected(bad):
    with pytest.raises(ValueError, match="source.source"):
        _build(
            _transformed_mesh(
                source={"source": bad, "model_id": "model-a", "raw_model_path": None}
            )
        )


@pytest.mark.parametrize("bad", ["", "   ", None, 3])
def test_empty_model_id_is_rejected(bad):
    with pytest.raises(ValueError, match="source.model_id"):
        _build(
            _transformed_mesh(
                source={"source": "3D-FUTURE", "model_id": bad, "raw_model_path": None}
            )
        )


@pytest.mark.parametrize("bad", ["", "   ", 3, object()])
def test_invalid_instance_id_is_rejected(bad):
    with pytest.raises(ValueError, match="instance_id"):
        _build(instance_id=bad)


@pytest.mark.parametrize("bad", ["", "   ", 3])
def test_invalid_category_is_rejected(bad):
    with pytest.raises(ValueError, match="category"):
        _build(category=bad)


@pytest.mark.parametrize("bad", ["", "   ", 1.5, True, object()])
def test_invalid_slot_is_rejected(bad):
    with pytest.raises(ValueError, match="slot"):
        _build(slot=bad)


@pytest.mark.parametrize("slot", [3, 0, 17, -1])
def test_integer_diffuscene_slot_is_accepted_as_provenance(slot):
    """DiffuScene slots are numeric in real data; the slot is provenance only."""

    instance = _build(slot=slot)

    assert instance["classification"]["slot"] == slot
    # The slot never leaks into the instance identity.
    assert instance["instance_id"] == "scene-a:placement:000000"


def test_duplicate_slot_values_are_allowed_and_do_not_change_identity():
    first = _build(slot=7)
    second = _build(slot=7)

    assert first["classification"]["slot"] == 7
    assert second["classification"]["slot"] == 7
    assert first["instance_id"] == second["instance_id"]


@pytest.mark.parametrize("field", ["units", "material", "support"])
@pytest.mark.parametrize("bad", ["x", 3, []])
def test_invalid_optional_mapping_types_are_rejected(field, bad):
    with pytest.raises(ValueError, match=f"{field} must be a mapping"):
        _build(**{field: bad})


def test_units_must_not_carry_executable_scale_metadata():
    with pytest.raises(ValueError, match="executable scale metadata"):
        _build(units={"status": "assumed_meters", "scale_xyz": [2.0, 2.0, 2.0]})


def test_unresolved_material_and_support_do_not_block_creation():
    instance = _build(material={"status": "unresolved"}, support={"status": "unresolved"})

    assert instance["status"]["state"] == "scene_instance_ready"


# ---------------------------------------------------------------------------
# 19. immutability / aliasing
# ---------------------------------------------------------------------------

def test_input_is_not_mutated():
    mesh = _transformed_mesh()
    before = copy.deepcopy(mesh)

    _build(mesh=mesh)

    assert mesh == before


def test_output_geometry_does_not_alias_input():
    mesh = _transformed_mesh()
    instance = _build(mesh=mesh)

    assert instance["geometry"]["vertices_xyz"] is not mesh["geometry"]["vertices_xyz"]
    assert instance["geometry"]["faces"] is not mesh["geometry"]["faces"]
    assert (
        instance["geometry"]["vertices_xyz"][0]
        is not mesh["geometry"]["vertices_xyz"][0]
    )
    assert instance["geometry"]["faces"][0] is not mesh["geometry"]["faces"][0]


def test_output_bounds_do_not_alias_input():
    mesh = _transformed_mesh()
    instance = _build(mesh=mesh)

    for key in ("min_xyz", "max_xyz", "center_xyz", "full_dims_xyz"):
        assert instance["bounds"][key] is not mesh["bounds"][key]


def test_output_provenance_does_not_alias_input():
    mesh = _transformed_mesh()
    instance = _build(mesh=mesh)

    assert instance["provenance"]["executor_transform"] is not mesh["transform"]
    assert instance["provenance"]["executor_semantics"] is not mesh["semantics"]
    assert instance["provenance"]["executor_status"] is not mesh["status"]


def test_supplied_mappings_do_not_alias_caller_objects():
    units = {"status": "assumed_meters"}
    material = {"status": "unresolved"}
    support = {"status": "unresolved", "contact_z": None}

    instance = _build(units=units, material=material, support=support)

    assert instance["units"] is not units
    assert instance["material"] is not material
    assert instance["support"] is not support
    units["status"] = "mutated"
    assert instance["units"]["status"] == "assumed_meters"


# ---------------------------------------------------------------------------
# 21. anti-double-transform
# ---------------------------------------------------------------------------

def test_builder_does_not_reapply_any_transform():
    mesh = _transformed_mesh()
    before = copy.deepcopy(mesh)

    instance = _build(mesh=mesh)

    assert (
        instance["geometry"]["vertices_xyz"] == before["geometry"]["vertices_xyz"]
    )
    assert instance["geometry"]["faces"] == before["geometry"]["faces"]

    scene_transform = instance["scene_transform"]
    assert scene_transform["status"] == "identity_world_space_mesh"
    assert scene_transform["position_xyz"] == [0.0, 0.0, 0.0]
    assert scene_transform["rotation_xyz_rad"] == [0.0, 0.0, 0.0]
    assert scene_transform["scale_xyz"] == [1.0, 1.0, 1.0]
    assert scene_transform["must_not_reapply_asset_transform"] is True

    assert mesh == before


def test_builder_has_no_transform_machinery():
    source = inspect.getsource(instance_module)

    # No rotation recomposition of any kind.
    for token in ("math.cos", "math.sin", "math.tan", "math.radians"):
        assert token not in source

    # No imports from the transform / asset-resolution domain.
    import_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    forbidden = (
        "mesh_transform_executor",
        "mesh_transform_spec",
        "raw_obj_loader",
        "mesh_alignment_resolver",
        "asset_forward_resolver",
        "forward_geometry_gate",
        "forward_rule_registry",
        "furniture_adapter",
    )
    assert import_lines
    for line in import_lines:
        for name in forbidden:
            assert name not in line

    # No hardcoded asset transform matrices.
    for name in ("BASIS", "UP_ALIGNMENT_MATRIX", "R_UP", "PHI_BY_RAW_FORWARD"):
        assert not hasattr(instance_module, name)


def test_scene_transform_is_metadata_only():
    instance = _build()
    scene_transform = instance["scene_transform"]

    assert set(scene_transform.keys()) == {
        "status",
        "position_xyz",
        "rotation_xyz_rad",
        "scale_xyz",
        "must_not_reapply_asset_transform",
    }
    # It is never multiplied into geometry: vertices are untouched world-space.
    assert instance["geometry"]["vertices_xyz"] == _transformed_mesh()["geometry"]["vertices_xyz"]


# ---------------------------------------------------------------------------
# 22. real 3D-FUTURE asset smoke test
# ---------------------------------------------------------------------------

REAL_ROOT = Path(r"D:\AI_Architecture_Lab\3D-FUTURE-model")
REAL_MODEL_ID = "27059911-89f4-3e78-a511-4c9b8cf51fb3"
REAL_OBJ = REAL_ROOT / "3D-FUTURE-model-part1" / REAL_MODEL_ID / "raw_model.obj"

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
        "notes": ["seating_and_adult_beds_only"],
    },
}


@pytest.mark.skipif(not REAL_OBJ.is_file(), reason="real 3D-FUTURE asset absent")
def test_real_3d_future_asset_scene_instance():
    mesh = load_raw_obj(
        {
            "source": "3D-FUTURE",
            "model_id": REAL_MODEL_ID,
            "raw_model_path": str(REAL_OBJ),
        },
        allowed_roots=[REAL_ROOT],
    )
    assert mesh["status"]["state"] == "mesh_loaded_valid"

    candidate = {
        "type": "furniture_asset_placement",
        "placement_identity": {
            "status": "resolved",
            "scope": "scene-real",
            "ordinal": 0,
            "source_engine": "DiffuScene",
            "source_slot": 3,
            "instance_id": "scene-real:placement:000000",
        },
        "mesh_source": {
            "source": "3D-FUTURE",
            "model_id": REAL_MODEL_ID,
            "raw_model_path": str(REAL_OBJ),
        },
        "position": {
            "source_center_xyz": [0.0, 2.0, 3.0],
            "room_local_xyz": [1.0, -3.0, 2.0],
            "world_xyz": None,
            "basis": BASIS_VERSION,
        },
        "rotation": {"source_y_rad": 0.4, "yaw_rad": 0.4, "axis": "+Z"},
        "scale": {"scale_xyz": [1.0, 1.0, 1.0]},
        "status": {"state": "ready_transform_metadata", "reasons": []},
    }
    phi = {
        "phi_status": "resolved",
        "phi_rad": math.pi / 2.0,
        "forward_status": "supported",
        "forward_axis": "+Z",
        "forward_axis_frame": "raw_mesh_local_frame",
        "world_zero_facing_axis": "+X",
        "world_zero_facing_axis_frame": "architectos_world_frame",
        "reasons": [],
    }

    spec = build_mesh_transform_spec(
        mesh, candidate, forward_contract=SUPPORTED_FORWARD, phi_result=phi
    )
    transformed = execute_mesh_transform(mesh, spec)
    assert transformed["status"]["state"] == "transformed_vertices_ready"

    instance = build_asset_scene_instance(
        transformed, category="chair", slot="slot-3"
    )

    assert instance["type"] == "asset_scene_instance"
    assert instance["version"] == "asset_scene_instance_v1"
    assert instance["status"]["state"] == "scene_instance_ready"

    # The placement identity survived candidate -> spec -> executor -> instance.
    assert instance["instance_id"] == "scene-real:placement:000000"
    assert instance["provenance"]["placement_identity"]["instance_id"] == (
        "scene-real:placement:000000"
    )
    assert instance["asset"]["model_id"] == REAL_MODEL_ID

    assert len(instance["geometry"]["vertices_xyz"]) == 475
    assert len(instance["geometry"]["faces"]) == 884
    assert instance["frames"]["geometry_frame"] == "architectos_world_frame"

    scene_transform = instance["scene_transform"]
    assert scene_transform["position_xyz"] == [0.0, 0.0, 0.0]
    assert scene_transform["rotation_xyz_rad"] == [0.0, 0.0, 0.0]
    assert scene_transform["scale_xyz"] == [1.0, 1.0, 1.0]

    assert instance["provenance"]["executor_transform"] is not None
    assert instance["material"]["status"] == "unresolved"
    assert instance["support"]["status"] == "unresolved"

    # world-space vertices preserved exactly
    assert (
        instance["geometry"]["vertices_xyz"]
        == transformed["geometry"]["vertices_xyz"]
    )


# ---------------------------------------------------------------------------
# Phase 3D-AH.1: instance identity is CONSUMED, never derived from model_id
# ---------------------------------------------------------------------------

def _mesh_with_identity(identity):
    mesh = _transformed_mesh()
    mesh["placement_identity"] = identity

    return mesh


def _resolved_identity(instance_id="scene-a:placement:000000"):
    return {
        "status": "resolved",
        "scope": "scene-a",
        "ordinal": 0,
        "source_engine": "DiffuScene",
        "source_slot": 3,
        "instance_id": instance_id,
    }


def _unresolved_identity():
    return {
        "status": "unresolved",
        "scope": None,
        "ordinal": 0,
        "source_engine": "DiffuScene",
        "source_slot": None,
        "instance_id": None,
        "reasons": ["placement_scope_missing"],
    }


def test_explicit_matching_instance_id_is_accepted():
    instance = build_asset_scene_instance(
        _transformed_mesh(), instance_id="scene-a:placement:000000"
    )

    assert instance["instance_id"] == "scene-a:placement:000000"


def test_explicit_mismatching_instance_id_is_rejected():
    with pytest.raises(ValueError, match="does not match"):
        build_asset_scene_instance(
            _transformed_mesh(), instance_id="scene-b:placement:000009"
        )


def test_missing_identity_without_explicit_instance_id_raises():
    mesh = _transformed_mesh()
    del mesh["placement_identity"]

    with pytest.raises(ValueError, match="instance_id is required"):
        build_asset_scene_instance(mesh)


def test_unresolved_identity_without_explicit_instance_id_raises():
    mesh = _mesh_with_identity(_unresolved_identity())

    with pytest.raises(ValueError, match="instance_id is required"):
        build_asset_scene_instance(mesh)


def test_model_id_is_never_used_as_an_instance_id_fallback():
    mesh = _mesh_with_identity(_unresolved_identity())

    with pytest.raises(ValueError) as error:
        build_asset_scene_instance(mesh)

    # The old source:model_id fallback is gone - model_id never appears.
    assert "model-a" not in str(error.value)
    assert "3d_future" not in str(error.value)


def test_same_model_at_two_ordinals_yields_distinct_instance_ids():
    first = build_asset_scene_instance(
        _mesh_with_identity(_resolved_identity("scene-a:placement:000000"))
    )
    second = build_asset_scene_instance(
        _mesh_with_identity(_resolved_identity("scene-a:placement:000001"))
    )

    assert first["asset"]["model_id"] == second["asset"]["model_id"] == "model-a"
    assert first["instance_id"] != second["instance_id"]


def test_unresolved_identity_with_explicit_instance_id_is_accepted():
    instance = build_asset_scene_instance(
        _mesh_with_identity(_unresolved_identity()), instance_id="explicit-id"
    )

    assert instance["instance_id"] == "explicit-id"


def test_provenance_preserves_the_placement_identity():
    mesh = _transformed_mesh()
    instance = _build(mesh=mesh)

    assert instance["provenance"]["placement_identity"] == (
        mesh["placement_identity"]
    )
    assert instance["provenance"]["placement_identity"] is not (
        mesh["placement_identity"]
    )


def test_provenance_records_a_null_identity_when_absent():
    mesh = _transformed_mesh()
    del mesh["placement_identity"]

    instance = build_asset_scene_instance(mesh, instance_id="explicit-id")

    assert instance["provenance"]["placement_identity"] is None


def test_unresolved_identity_must_not_carry_an_instance_id():
    mesh = _mesh_with_identity(
        {
            "status": "unresolved",
            "scope": None,
            "ordinal": 0,
            "source_engine": "DiffuScene",
            "source_slot": None,
            "instance_id": "should-not-be-here",
        }
    )

    with pytest.raises(ValueError, match="must not carry an instance_id"):
        build_asset_scene_instance(mesh, instance_id="explicit-id")


def test_unknown_identity_status_is_rejected():
    mesh = _mesh_with_identity(
        {
            "status": "maybe",
            "scope": None,
            "ordinal": 0,
            "source_engine": "DiffuScene",
            "source_slot": None,
            "instance_id": None,
        }
    )

    with pytest.raises(ValueError, match="status must be"):
        build_asset_scene_instance(mesh, instance_id="explicit-id")


def test_non_mapping_placement_identity_is_rejected():
    mesh = _mesh_with_identity("scene-a:placement:000000")

    with pytest.raises(ValueError, match="placement_identity must be a mapping"):
        build_asset_scene_instance(mesh, instance_id="explicit-id")


def test_source_model_id_default_is_removed():
    """The old ``source:model_id`` default helper must be gone."""

    source = inspect.getsource(instance_module)

    assert "_default_instance_id" not in source


# ---------------------------------------------------------------------------
# Phase 3D-AH.1: full chain (adapter -> spec -> executor -> instance)
# ---------------------------------------------------------------------------

def _phi():
    return {
        "phi_status": "resolved",
        "phi_rad": math.pi / 2.0,
        "forward_status": "supported",
        "forward_axis": "+Z",
        "forward_axis_frame": "raw_mesh_local_frame",
        "world_zero_facing_axis": "+X",
        "world_zero_facing_axis_frame": "architectos_world_frame",
        "reasons": [],
    }


def _raw_mesh_for(candidate):
    """A valid synthetic raw-loader result for one placement candidate."""

    return {
        "format_version": "raw_obj_mesh_v1",
        "source": "3D-FUTURE",
        "model_id": candidate["mesh_source"]["model_id"],
        "raw_model_path": candidate["mesh_source"]["raw_model_path"],
        "mesh_frame": "raw_mesh_local_frame",
        "geometry": {
            "index_base": 0,
            "vertices_xyz": [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
            ],
            "faces": [[0, 1, 2]],
        },
        "bounds": {
            "min_xyz": [0.0, 0.0, 0.0],
            "max_xyz": [1.0, 1.0, 0.0],
            "dims_xyz": [1.0, 1.0, 0.0],
            "center_xyz": [0.5, 0.5, 0.0],
        },
        "pivot": {
            "mesh_origin_xyz": [0.0, 0.0, 0.0],
            "bbox_center_xyz": [0.5, 0.5, 0.0],
        },
        "status": {"state": "mesh_loaded_valid", "reasons": []},
    }


def test_full_chain_one_model_two_placements_get_distinct_instance_ids():
    """The identity is created once and only ever copied / propagated.

    Two placements share ONE asset model and even the SAME DiffuScene slot, so
    only the ordinal can distinguish them - exactly the case a model_id-based
    identity got wrong.
    """

    from core.pipeline.adapters.furniture_adapter import FurnitureAdapter

    scene = [
        {
            "slot": 7,
            "class_name": "chair",
            "center_xyz": [1.0, 2.0, 3.0],
            "full_dims_xyz": [1.0, 1.0, 1.0],
            "angle_rad": 0.0,
            "objfeat": [1.0, 0.0],
        },
        {
            "slot": 7,
            "class_name": "chair",
            "center_xyz": [4.0, 5.0, 6.0],
            "full_dims_xyz": [1.0, 1.0, 1.0],
            "angle_rad": 0.5,
            "objfeat": [1.0, 0.0],
        },
    ]
    registry = {
        "assets": [
            {
                "model_id": "model-a",
                "category": "chair",
                "full_dims_xyz": [1.0, 1.0, 1.0],
                "raw_model_path": "D:/dataset/part1/model-a/raw_model.obj",
            }
        ]
    }

    adapter = FurnitureAdapter()
    matched = adapter.match_3d_future(adapter.convert_diffuscene(scene), registry)
    candidates = adapter.build_placement_candidates(
        matched, registry, placement_scope="scene-a"
    )["placements"]

    assert len(candidates) == 2
    assert {c["mesh_source"]["model_id"] for c in candidates} == {"model-a"}
    assert [c["slot"] for c in candidates] == [7, 7]

    instances = []
    for candidate in candidates:
        mesh = _raw_mesh_for(candidate)
        spec = build_mesh_transform_spec(
            mesh,
            candidate,
            forward_contract=SUPPORTED_FORWARD,
            phi_result=_phi(),
        )
        # The spec COPIED the candidate identity...
        assert spec["placement_identity"] == candidate["placement_identity"]

        transformed = execute_mesh_transform(mesh, spec)
        assert transformed["status"]["state"] == "transformed_vertices_ready"
        # ...and the executor PROPAGATED it unchanged.
        assert transformed["placement_identity"] == candidate["placement_identity"]

        instances.append(
            build_asset_scene_instance(transformed, slot=candidate["slot"])
        )

    assert [instance["instance_id"] for instance in instances] == [
        "scene-a:placement:000000",
        "scene-a:placement:000001",
    ]
    assert instances[0]["instance_id"] != instances[1]["instance_id"]
    assert {instance["classification"]["slot"] for instance in instances} == {7}
    assert {instance["asset"]["model_id"] for instance in instances} == {"model-a"}
