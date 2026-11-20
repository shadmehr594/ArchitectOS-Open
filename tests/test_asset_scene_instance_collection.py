"""Focused tests for the asset scene-instance collection contract (Phase 3D-AJ)."""

import copy
import inspect
from pathlib import Path

import pytest

import core.asset.asset_scene_instance_collection as collection_module
from core.asset.asset_scene_instance import build_asset_scene_instance
from core.asset.asset_scene_instance_collection import (
    build_asset_scene_instance_collection,
)


BASIS_VERSION = "diffuscene_y_up_to_architectos_z_up_v1"

IDENTITY3 = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
IDENTITY4 = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
]

DEFAULT_VERTICES = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [0.0, 0.0, 0.0]]
DEFAULT_FACES = [[0, 1, 2]]


# ---------------------------------------------------------------------------
# helpers - genuine instances built by the real Phase 3D-AH builder
# ---------------------------------------------------------------------------

def _bounds(vertices):
    minimum = [min(vertex[index] for vertex in vertices) for index in range(3)]
    maximum = [max(vertex[index] for vertex in vertices) for index in range(3)]

    return {
        "min_xyz": minimum,
        "max_xyz": maximum,
        "center_xyz": [
            (minimum[index] + maximum[index]) / 2.0 for index in range(3)
        ],
        "full_dims_xyz": [
            maximum[index] - minimum[index] for index in range(3)
        ],
    }


def _transformed_mesh(model_id="model-a", vertices=None, faces=None):
    vertices = DEFAULT_VERTICES if vertices is None else vertices
    faces = DEFAULT_FACES if faces is None else faces

    return {
        "type": "transformed_mesh",
        "source": {
            "source": "3D-FUTURE",
            "model_id": model_id,
            "raw_model_path": f"D:/dataset/part1/{model_id}/raw_model.obj",
        },
        "frames": {
            "source": "raw_mesh_local_frame",
            "destination": "architectos_world_frame",
        },
        "geometry": {"vertices_xyz": vertices, "faces": faces},
        "bounds": _bounds(vertices),
        "transform": {
            "final_rotation_matrix": [list(row) for row in IDENTITY3],
            "translation_xyz": [0.0, 0.0, 0.0],
            "matrix4x4": [list(row) for row in IDENTITY4],
            "scale_xyz": [1.0, 1.0, 1.0],
        },
        "topology": {
            "face_order_preserved": True,
            "vertex_count": len(vertices),
            "face_count": len(faces),
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


def _instance(
    instance_id="scene-a:placement:000000",
    *,
    model_id="model-a",
    slot=3,
    category="chair",
    ordinal=0,
    scope="scene-a",
    vertices=None,
    faces=None,
):
    """A GENUINE asset_scene_instance built through the real Phase 3D-AH builder."""

    mesh = _transformed_mesh(
        model_id=model_id, vertices=vertices, faces=faces
    )
    mesh["placement_identity"] = {
        "status": "resolved",
        "scope": scope,
        "ordinal": ordinal,
        "source_engine": "DiffuScene",
        "source_slot": slot,
        "instance_id": instance_id,
    }

    return build_asset_scene_instance(mesh, category=category, slot=slot)


def _two_instances():
    """Two placements sharing ONE model_id AND ONE source slot."""

    return [
        _instance(
            "scene-a:placement:000000", model_id="chair-X", slot=7, ordinal=0
        ),
        _instance(
            "scene-a:placement:000001", model_id="chair-X", slot=7, ordinal=1
        ),
    ]


def _import_lines(module):
    source = inspect.getsource(module)

    return [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]


def _imported_modules(module):
    """Top-level module names imported by ``module`` (no substring guessing)."""

    names = set()
    for line in _import_lines(module):
        if line.startswith("from "):
            names.add(line[len("from "):].split()[0].split(".")[0])
        else:
            for part in line[len("import "):].split(","):
                names.add(part.strip().split()[0].split(".")[0])

    return names


# ---------------------------------------------------------------------------
# 1 - 3. positive contract
# ---------------------------------------------------------------------------

def test_empty_collection_is_accepted():
    collection = build_asset_scene_instance_collection([])

    assert collection["type"] == "asset_scene_instance_collection"
    assert collection["instances"] == []
    assert collection["count"] == 0
    assert collection["instance_ids"] == []
    assert collection["collection_id"] is None
    assert collection["context"] is None
    assert collection["status"] == {
        "state": "asset_instance_collection_ready",
        "reasons": [],
    }


def test_single_valid_instance():
    instance = _instance("scene-a:placement:000000")

    collection = build_asset_scene_instance_collection([instance])

    assert collection["count"] == 1
    assert collection["instance_ids"] == ["scene-a:placement:000000"]
    assert collection["instances"][0]["type"] == "asset_scene_instance"


def test_multiple_valid_instances():
    instances = [
        _instance(f"scene-a:placement:{index:06d}", ordinal=index)
        for index in range(4)
    ]

    collection = build_asset_scene_instance_collection(instances)

    assert collection["count"] == 4
    assert collection["instance_ids"] == [
        f"scene-a:placement:{index:06d}" for index in range(4)
    ]


def test_collection_has_the_expected_shape():
    collection = build_asset_scene_instance_collection(_two_instances())

    assert sorted(collection.keys()) == [
        "collection_id",
        "context",
        "count",
        "instance_ids",
        "instances",
        "semantics",
        "status",
        "type",
        "version",
    ]


def test_collection_version_is_declared():
    collection = build_asset_scene_instance_collection([])

    assert collection["version"] == "asset_scene_instance_collection_v1"


# ---------------------------------------------------------------------------
# 4. ordering contract
# ---------------------------------------------------------------------------

def test_input_order_is_preserved_exactly():
    ids = [
        "scene-z:placement:000002",
        "scene-a:placement:000000",
        "scene-m:placement:000001",
    ]
    instances = [
        _instance(instance_id, ordinal=index, scope=instance_id.split(":")[0])
        for index, instance_id in enumerate(ids)
    ]

    collection = build_asset_scene_instance_collection(instances)

    assert collection["instance_ids"] == ids
    assert [item["instance_id"] for item in collection["instances"]] == ids
    # Explicitly NOT canonicalized into sorted order.
    assert collection["instance_ids"] != sorted(ids)


def test_input_order_is_preserved_for_mixed_models():
    instances = [
        _instance("scene-a:placement:000000", model_id="zzz", ordinal=0),
        _instance("scene-a:placement:000001", model_id="aaa", ordinal=1),
        _instance("scene-a:placement:000002", model_id="mmm", ordinal=2),
    ]

    collection = build_asset_scene_instance_collection(instances)

    # No sorting by model_id, category, slot or position.
    assert [item["asset"]["model_id"] for item in collection["instances"]] == [
        "zzz",
        "aaa",
        "mmm",
    ]


def test_input_list_is_not_reordered_in_place():
    instances = [
        _instance("scene-c:placement:000000", ordinal=0),
        _instance("scene-b:placement:000001", ordinal=1),
        _instance("scene-a:placement:000002", ordinal=2),
    ]
    before = [item["instance_id"] for item in instances]

    build_asset_scene_instance_collection(instances)

    assert [item["instance_id"] for item in instances] == before


# ---------------------------------------------------------------------------
# 5 - 6, 25 - 26. identity vs model_id vs slot
# ---------------------------------------------------------------------------

def test_same_model_id_may_appear_multiple_times():
    collection = build_asset_scene_instance_collection(_two_instances())

    assert collection["count"] == 2
    assert {item["asset"]["model_id"] for item in collection["instances"]} == {
        "chair-X"
    }
    assert len(set(collection["instance_ids"])) == 2


def test_duplicate_source_slot_is_allowed():
    collection = build_asset_scene_instance_collection(_two_instances())

    assert [
        item["classification"]["slot"] for item in collection["instances"]
    ] == [7, 7]
    assert len(set(collection["instance_ids"])) == 2


def test_same_model_and_slot_but_distinct_instance_ids_is_valid():
    instances = [
        _instance("scene-a:placement:000000", model_id="chair-X", slot=7, ordinal=0),
        _instance("scene-a:placement:000001", model_id="chair-X", slot=7, ordinal=1),
    ]

    collection = build_asset_scene_instance_collection(instances)

    assert collection["count"] == 2
    assert collection["instance_ids"] == [
        "scene-a:placement:000000",
        "scene-a:placement:000001",
    ]


def test_many_models_may_share_one_slot():
    instances = [
        _instance(f"scene-a:placement:{index:06d}", model_id=f"model-{index}", slot=1, ordinal=index)
        for index in range(3)
    ]

    collection = build_asset_scene_instance_collection(instances)

    assert collection["count"] == 3
    assert {item["classification"]["slot"] for item in collection["instances"]} == {1}


# ---------------------------------------------------------------------------
# 7 - 9. duplicate and malformed member identity
# ---------------------------------------------------------------------------

def test_duplicate_instance_id_is_rejected():
    instances = [
        _instance("scene-a:placement:000000", ordinal=0),
        _instance("scene-a:placement:000000", ordinal=1),
    ]

    with pytest.raises(ValueError, match="duplicate instance_id"):
        build_asset_scene_instance_collection(instances)


def test_duplicate_instance_id_error_names_the_id():
    instances = [
        _instance("dup-id", ordinal=0),
        _instance("dup-id", ordinal=1),
    ]

    with pytest.raises(ValueError) as error:
        build_asset_scene_instance_collection(instances)

    assert "dup-id" in str(error.value)


def test_duplicate_instance_id_is_not_deduplicated_or_renamed():
    instances = [
        _instance("scene-a:placement:000000", ordinal=0),
        _instance("scene-a:placement:000000", ordinal=1),
    ]
    before = copy.deepcopy(instances)

    with pytest.raises(ValueError):
        build_asset_scene_instance_collection(instances)

    # The caller's list is untouched: no dedup, no rename, no overwrite.
    assert instances == before
    assert len(instances) == 2


@pytest.mark.parametrize(
    "bad",
    ["", "   ", None, 3, 1.5, True, False, [], {}, object()],
    ids=[
        "empty",
        "whitespace",
        "none",
        "int",
        "float",
        "true",
        "false",
        "list",
        "dict",
        "object",
    ],
)
def test_malformed_instance_id_is_rejected(bad):
    instance = _instance()
    instance["instance_id"] = bad

    with pytest.raises(ValueError, match="instance_id"):
        build_asset_scene_instance_collection([instance])


@pytest.mark.parametrize("bad", ["transformed_mesh", "asset_scene_instance_collection", "instance", ""])
def test_wrong_instance_type_is_rejected(bad):
    instance = _instance()
    instance["type"] = bad

    with pytest.raises(ValueError, match="type must be"):
        build_asset_scene_instance_collection([instance])


def test_missing_instance_type_is_rejected():
    instance = _instance()
    del instance["type"]

    with pytest.raises(ValueError, match="type must be"):
        build_asset_scene_instance_collection([instance])


def test_missing_instance_id_is_rejected():
    instance = _instance()
    del instance["instance_id"]

    with pytest.raises(ValueError, match="instance_id"):
        build_asset_scene_instance_collection([instance])


# ---------------------------------------------------------------------------
# 10 - 11. container integrity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad",
    [None, "x", 3, 1.5, {}, (), set(), object()],
    ids=["none", "str", "int", "float", "dict", "tuple", "set", "object"],
)
def test_non_list_input_is_rejected(bad):
    with pytest.raises(ValueError, match="instances must be a list"):
        build_asset_scene_instance_collection(bad)


@pytest.mark.parametrize(
    "bad",
    ["nope", 3, None, ["x"], (), 1.5],
    ids=["str", "int", "none", "list", "tuple", "float"],
)
def test_non_mapping_member_is_rejected(bad):
    with pytest.raises(ValueError, match=r"instances\[1\] must be a mapping"):
        build_asset_scene_instance_collection([_instance(), bad])


def test_member_error_reports_the_offending_index():
    bad = _instance("scene-a:placement:000009")
    bad["instance_id"] = ""

    with pytest.raises(ValueError, match=r"instances\[2\]"):
        build_asset_scene_instance_collection(
            [_instance(), _instance("scene-a:placement:000001"), bad]
        )


def test_container_integrity_only_is_validated():
    """Member internals are NOT re-validated: that is the instance's job."""

    minimal = {"type": "asset_scene_instance", "instance_id": "minimal-1"}

    collection = build_asset_scene_instance_collection([minimal])

    assert collection["count"] == 1
    assert collection["instance_ids"] == ["minimal-1"]
    assert collection["instances"][0] == minimal


# ---------------------------------------------------------------------------
# 12 - 14. collection id
# ---------------------------------------------------------------------------

def test_collection_id_none_is_preserved():
    collection = build_asset_scene_instance_collection([])

    assert collection["collection_id"] is None


def test_explicit_collection_id_is_preserved_exactly():
    collection = build_asset_scene_instance_collection(
        _two_instances(), collection_id="room-101-batch-A"
    )

    assert collection["collection_id"] == "room-101-batch-A"


@pytest.mark.parametrize(
    "bad",
    ["", "   ", 3, 1.5, True, False, [], {}, object()],
    ids=[
        "empty",
        "whitespace",
        "int",
        "float",
        "true",
        "false",
        "list",
        "dict",
        "object",
    ],
)
def test_invalid_collection_id_is_rejected(bad):
    with pytest.raises(ValueError, match="collection_id"):
        build_asset_scene_instance_collection([], collection_id=bad)


def test_collection_id_is_not_invented():
    """No UUID / timestamp / hash / counter is generated for the collection."""

    first = build_asset_scene_instance_collection(_two_instances())
    second = build_asset_scene_instance_collection(_two_instances())

    assert first["collection_id"] is None
    assert second["collection_id"] is None
    assert first == second


# ---------------------------------------------------------------------------
# 15 - 16. context
# ---------------------------------------------------------------------------

def test_optional_context_is_accepted_and_preserved():
    context = {
        "room_id": "room-101",
        "space_id": "living",
        "floor_id": "f1",
        "level": 1,
        "source_scene_id": "scene-a",
    }

    collection = build_asset_scene_instance_collection([], context=context)

    assert collection["context"] == context
    assert collection["context"] is not context


def test_partial_context_is_accepted_without_inference():
    collection = build_asset_scene_instance_collection(
        [], context={"room_id": "room-101"}
    )

    assert collection["context"] == {"room_id": "room-101"}
    # Missing context is never invented.
    assert set(collection["context"]) == {"room_id"}


def test_empty_context_mapping_is_accepted():
    collection = build_asset_scene_instance_collection([], context={})

    assert collection["context"] == {}


def test_absent_context_stays_none():
    collection = build_asset_scene_instance_collection(_two_instances())

    assert collection["context"] is None


def test_context_is_deep_copied():
    context = {
        "room_id": "room-101",
        "tags": ["a", "b"],
        "meta": {"keys": [1, 2]},
    }

    collection = build_asset_scene_instance_collection([], context=context)

    context["room_id"] = "mutated"
    context["tags"].append("c")
    context["meta"]["keys"].append(3)

    assert collection["context"] == {
        "room_id": "room-101",
        "tags": ["a", "b"],
        "meta": {"keys": [1, 2]},
    }
    assert collection["context"]["tags"] is not context["tags"]


@pytest.mark.parametrize(
    "bad",
    ["x", 3, 1.5, [], (), set(), True],
    ids=["str", "int", "float", "list", "tuple", "set", "bool"],
)
def test_non_mapping_context_is_rejected(bad):
    with pytest.raises(ValueError, match="context must be a mapping"):
        build_asset_scene_instance_collection([], context=bad)


def test_context_does_not_change_identity_or_geometry():
    instances = _two_instances()
    without = build_asset_scene_instance_collection(instances)
    with_context = build_asset_scene_instance_collection(
        instances, context={"room_id": "room-101", "level": 2}
    )

    assert with_context["instance_ids"] == without["instance_ids"]
    assert with_context["instances"] == without["instances"]
    assert with_context["count"] == without["count"]


# ---------------------------------------------------------------------------
# 17 - 18. memory ownership
# ---------------------------------------------------------------------------

def test_instances_are_deep_copied():
    instances = _two_instances()

    collection = build_asset_scene_instance_collection(instances)

    # Equal by value, but never the same objects.
    assert collection["instances"] == instances
    assert collection["instances"][0] is not instances[0]
    assert collection["instances"][1] is not instances[1]
    assert collection["instances"][0]["geometry"] is not instances[0]["geometry"]
    assert (
        collection["instances"][0]["geometry"]["vertices_xyz"]
        is not instances[0]["geometry"]["vertices_xyz"]
    )
    assert (
        collection["instances"][0]["geometry"]["vertices_xyz"][0]
        is not instances[0]["geometry"]["vertices_xyz"][0]
    )
    assert collection["instances"][0]["provenance"] is not instances[0]["provenance"]
    assert (
        collection["instances"][0]["scene_transform"]
        is not instances[0]["scene_transform"]
    )


def test_mutating_the_input_after_build_does_not_change_the_collection():
    instances = _two_instances()

    collection = build_asset_scene_instance_collection(instances)
    snapshot = copy.deepcopy(collection)

    instances[0]["geometry"]["vertices_xyz"][0][0] = 999.0
    instances[0]["instance_id"] = "hacked"
    instances[0]["asset"]["model_id"] = "hacked"
    instances[0]["classification"]["slot"] = 999

    assert collection == snapshot
    assert collection["instance_ids"] == [
        "scene-a:placement:000000",
        "scene-a:placement:000001",
    ]


def test_source_inputs_are_not_mutated():
    instances = _two_instances()
    before = copy.deepcopy(instances)

    build_asset_scene_instance_collection(
        instances, collection_id="c-1", context={"room_id": "room-101"}
    )

    assert instances == before


def test_source_inputs_are_not_mutated_on_failure():
    instances = [
        _instance("scene-a:placement:000000", ordinal=0),
        _instance("scene-a:placement:000000", ordinal=1),
    ]
    before = copy.deepcopy(instances)

    with pytest.raises(ValueError):
        build_asset_scene_instance_collection(instances)

    assert instances == before


def test_members_do_not_alias_each_other():
    collection = build_asset_scene_instance_collection(_two_instances())
    first, second = collection["instances"]

    assert first is not second
    assert first["geometry"] is not second["geometry"]
    assert first["geometry"]["vertices_xyz"] is not second["geometry"]["vertices_xyz"]
    assert (
        first["geometry"]["vertices_xyz"][0]
        is not second["geometry"]["vertices_xyz"][0]
    )
    assert first["asset"] is not second["asset"]
    assert first["provenance"] is not second["provenance"]


def test_mutating_one_member_does_not_affect_another():
    collection = build_asset_scene_instance_collection(_two_instances())

    collection["instances"][0]["geometry"]["vertices_xyz"][0][0] = 42.0
    collection["instances"][0]["instance_id"] = "changed"

    assert collection["instances"][1]["geometry"]["vertices_xyz"][0][0] != 42.0
    assert collection["instances"][1]["instance_id"] == "scene-a:placement:000001"


# ---------------------------------------------------------------------------
# 19 - 24. world-space / no double transform
# ---------------------------------------------------------------------------

def test_geometry_coordinates_are_unchanged():
    instances = _two_instances()

    collection = build_asset_scene_instance_collection(instances)

    for member, source in zip(collection["instances"], instances):
        assert member["geometry"]["vertices_xyz"] == source["geometry"]["vertices_xyz"]


def test_faces_are_unchanged():
    instances = _two_instances()

    collection = build_asset_scene_instance_collection(instances)

    for member, source in zip(collection["instances"], instances):
        assert member["geometry"]["faces"] == source["geometry"]["faces"]


def test_executor_transform_metadata_is_unchanged():
    instances = _two_instances()

    collection = build_asset_scene_instance_collection(instances)

    for member, source in zip(collection["instances"], instances):
        assert member["provenance"]["executor_transform"] == (
            source["provenance"]["executor_transform"]
        )
        assert member["provenance"]["executor_semantics"] == (
            source["provenance"]["executor_semantics"]
        )
        assert member["provenance"]["executor_status"] == (
            source["provenance"]["executor_status"]
        )


def test_placement_identity_provenance_is_unchanged():
    instances = _two_instances()

    collection = build_asset_scene_instance_collection(instances)

    for member, source in zip(collection["instances"], instances):
        assert member["provenance"]["placement_identity"] == (
            source["provenance"]["placement_identity"]
        )


def test_scene_transform_is_unchanged_and_still_identity():
    instances = _two_instances()

    collection = build_asset_scene_instance_collection(instances)

    for member, source in zip(collection["instances"], instances):
        assert member["scene_transform"] == source["scene_transform"]
        scene_transform = member["scene_transform"]
        assert scene_transform["status"] == "identity_world_space_mesh"
        assert scene_transform["position_xyz"] == [0.0, 0.0, 0.0]
        assert scene_transform["rotation_xyz_rad"] == [0.0, 0.0, 0.0]
        assert scene_transform["scale_xyz"] == [1.0, 1.0, 1.0]
        assert scene_transform["must_not_reapply_asset_transform"] is True


def test_collection_never_applies_the_scene_transform():
    """Vertices, bounds and topology are byte-identical to the inputs."""

    instances = _two_instances()

    collection = build_asset_scene_instance_collection(instances)

    for member, source in zip(collection["instances"], instances):
        assert member["geometry"]["vertices_xyz"] == source["geometry"]["vertices_xyz"]
        assert member["geometry"]["faces"] == source["geometry"]["faces"]
        assert member["bounds"] == source["bounds"]
        assert member["topology"] == source["topology"]


def test_collection_does_not_reapply_any_asset_transform():
    """A non-trivial input must survive the collection untouched."""

    vertices = [[10.0, -20.0, 5.5], [11.0, -20.0, 5.5], [10.0, -19.0, 5.5]]
    faces = [[0, 1, 2]]
    instance = _instance("scene-a:placement:000000", vertices=vertices, faces=faces)

    collection = build_asset_scene_instance_collection([instance])

    member = collection["instances"][0]
    assert member["geometry"]["vertices_xyz"] == vertices
    assert member["geometry"]["faces"] == faces
    assert member["bounds"] == instance["bounds"]


def test_collection_declares_world_space_semantics():
    semantics = build_asset_scene_instance_collection([])["semantics"]

    assert semantics["world_space_geometry"] is True
    assert semantics["transforms_already_applied"] is True
    assert semantics["scene_transform_application_required"] is False


def test_semantics_flags_are_exact():
    semantics = build_asset_scene_instance_collection([])["semantics"]

    assert semantics == {
        "world_space_geometry": True,
        "transforms_already_applied": True,
        "scene_transform_application_required": False,
        "duplicate_instance_ids_allowed": False,
        "input_order_preserved": True,
        "room_context_required": False,
        "physical_validation_complete": False,
        "render_ready": False,
        "export_ready": False,
    }


def test_no_physical_validation_or_readiness_is_claimed():
    semantics = build_asset_scene_instance_collection(_two_instances())["semantics"]

    assert semantics["physical_validation_complete"] is False
    assert semantics["render_ready"] is False
    assert semantics["export_ready"] is False
    assert semantics["room_context_required"] is False


# ---------------------------------------------------------------------------
# 27. determinism
# ---------------------------------------------------------------------------

def test_repeated_builds_are_deterministic():
    instances = _two_instances()

    first = build_asset_scene_instance_collection(
        instances, collection_id="c-1", context={"room_id": "room-101"}
    )
    second = build_asset_scene_instance_collection(
        instances, collection_id="c-1", context={"room_id": "room-101"}
    )

    assert first == second
    assert first is not second
    assert first["instances"] is not second["instances"]


def test_status_block_is_exact():
    collection = build_asset_scene_instance_collection(_two_instances())

    assert collection["status"] == {
        "state": "asset_instance_collection_ready",
        "reasons": [],
    }


# ---------------------------------------------------------------------------
# 28 - 32. purity (structural)
# ---------------------------------------------------------------------------

def test_collection_module_imports_only_pure_modules():
    """The whole purity claim rests on this: only pure stdlib is imported."""

    assert _imported_modules(collection_module) <= {"__future__", "copy", "typing"}


def test_collection_module_uses_no_nondeterministic_source():
    imported = _imported_modules(collection_module)

    for name in (
        "uuid",
        "random",
        "secrets",
        "datetime",
        "hashlib",
        "os",
        "pathlib",
        "io",
        "time",
        "itertools",
    ):
        assert name not in imported

    source = inspect.getsource(collection_module)
    for call in (
        "uuid4",
        "urandom",
        "getrandbits",
        "datetime.now",
        "time.time",
        "monotonic",
        "itertools.count",
        "sha256",
        "md5",
    ):
        assert call not in source


def test_collection_module_does_not_touch_the_filesystem():
    imported = _imported_modules(collection_module)

    for name in ("os", "pathlib", "io", "shutil", "tempfile", "glob", "json"):
        assert name not in imported

    source = inspect.getsource(collection_module)
    assert "open(" not in source


def test_collection_module_does_not_import_the_asset_transform_stage():
    imported = _imported_modules(collection_module)

    for name in (
        "furniture_adapter",
        "mesh_transform_spec",
        "mesh_transform_executor",
        "mesh_alignment_resolver",
        "raw_obj_loader",
        "asset_forward_resolver",
        "asset_scene_instance",
    ):
        assert name not in imported


def test_collection_module_does_not_call_the_asset_transform_stage():
    source = inspect.getsource(collection_module)

    for call in (
        "FurnitureAdapter(",
        "build_mesh_transform_spec(",
        "execute_mesh_transform(",
        "load_raw_obj(",
        "build_asset_scene_instance(",
        "resolve_intrinsic_yaw_phi(",
    ):
        assert call not in source


def test_collection_module_has_no_transform_machinery():
    source = inspect.getsource(collection_module)

    for token in ("math.cos", "math.sin", "math.tan", "math.radians", "math.degrees"):
        assert token not in source

    for name in ("BASIS", "BASIS_B", "UP_ALIGNMENT_MATRIX", "R_UP", "PHI_BY_RAW_FORWARD"):
        assert not hasattr(collection_module, name)


def test_collection_module_does_not_import_math():
    assert "math" not in _imported_modules(collection_module)


# ---------------------------------------------------------------------------
# 33. no runtime / scene / BIM / export wiring
# ---------------------------------------------------------------------------

def test_collection_output_has_no_scene_or_bim_wiring():
    collection = build_asset_scene_instance_collection(_two_instances())

    for key in (
        "scene",
        "scene_result",
        "bim",
        "renderer",
        "export",
        "export_result",
        "runtime",
        "pipeline",
        "room",
        "serialized",
    ):
        assert key not in collection


def test_collection_module_does_not_import_runtime_scene_or_bim():
    imported = _imported_modules(collection_module)

    for name in (
        "scene_builder",
        "scene_exporter",
        "bim",
        "runtime",
        "pipeline",
        "renderer",
        "collision",
        "clearance",
    ):
        assert name not in imported


def test_raw_model_path_is_preserved_internally_only():
    collection = build_asset_scene_instance_collection(_two_instances())

    # Preserved internally, unsanitized...
    assert collection["instances"][0]["asset"]["raw_model_path"] == (
        "D:/dataset/part1/chair-X/raw_model.obj"
    )
    # ...but never surfaced as an export/serialization artifact.
    assert "export" not in collection
    assert "serialized" not in collection


# ---------------------------------------------------------------------------
# 34 - 36. counts and ids
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("count", [0, 1, 2, 5])
def test_count_matches_len_instances(count):
    instances = [
        _instance(f"scene-a:placement:{index:06d}", ordinal=index)
        for index in range(count)
    ]

    collection = build_asset_scene_instance_collection(instances)

    assert collection["count"] == len(collection["instances"]) == count
    assert len(collection["instance_ids"]) == count


def test_instance_ids_follow_input_order_exactly():
    ids = [
        "scene-a:placement:000003",
        "scene-a:placement:000001",
        "scene-a:placement:000002",
        "scene-a:placement:000000",
    ]
    instances = [_instance(instance_id, ordinal=index) for index, instance_id in enumerate(ids)]

    collection = build_asset_scene_instance_collection(instances)

    assert collection["instance_ids"] == ids


def test_instance_ids_are_derived_from_the_validated_copies():
    instances = _two_instances()

    collection = build_asset_scene_instance_collection(instances)

    assert collection["instance_ids"] == [
        item["instance_id"] for item in collection["instances"]
    ]


# ---------------------------------------------------------------------------
# API shape
# ---------------------------------------------------------------------------

def test_api_signature_is_keyword_only_for_options():
    signature = inspect.signature(build_asset_scene_instance_collection)

    assert list(signature.parameters) == [
        "instances",
        "collection_id",
        "context",
    ]
    assert signature.parameters["instances"].kind is (
        inspect.Parameter.POSITIONAL_OR_KEYWORD
    )
    for name in ("collection_id", "context"):
        assert signature.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert signature.parameters[name].default is None


# ---------------------------------------------------------------------------
# REAL 3D-FUTURE full-chain integration test (two placements, one model)
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


def _phi():
    import math

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


@pytest.mark.skipif(not REAL_OBJ.is_file(), reason="real 3D-FUTURE asset absent")
def test_real_two_placement_collection_end_to_end():
    """Two placements of ONE real model -> one collection.

    Exercises the full chain: candidate -> raw OBJ loader -> forward/phi/spec ->
    executor -> asset_scene_instance -> collection.
    """

    from core.pipeline.adapters.furniture_adapter import FurnitureAdapter
    from core.asset.raw_obj_loader import load_raw_obj
    from core.asset.mesh_transform_spec import build_mesh_transform_spec
    from core.asset.mesh_transform_executor import execute_mesh_transform

    mesh_source = {
        "source": "3D-FUTURE",
        "model_id": REAL_MODEL_ID,
        "raw_model_path": str(REAL_OBJ),
    }
    mesh = load_raw_obj(mesh_source, allowed_roots=[REAL_ROOT])
    assert mesh["status"]["state"] == "mesh_loaded_valid"

    adapter = FurnitureAdapter()
    scene = [
        {
            "slot": 3,
            "class_name": "chair",
            "center_xyz": [0.0, 2.0, 3.0],
            "full_dims_xyz": [0.5, 0.5, 0.5],
            "angle_rad": 0.4,
            "objfeat": [1.0, 0.0],
        },
        {
            "slot": 3,
            "class_name": "chair",
            "center_xyz": [1.0, 2.0, 3.0],
            "full_dims_xyz": [0.5, 0.5, 0.5],
            "angle_rad": 0.4,
            "objfeat": [1.0, 0.0],
        },
    ]
    registry = {
        "assets": [
            {
                "model_id": REAL_MODEL_ID,
                "category": "chair",
                "full_dims_xyz": [0.5, 0.5, 0.5],
                "raw_model_path": str(REAL_OBJ),
            }
        ]
    }

    matched = adapter.match_3d_future(adapter.convert_diffuscene(scene), registry)
    candidates = adapter.build_placement_candidates(
        matched, registry, placement_scope="scene-real"
    )["placements"]
    assert len(candidates) == 2
    assert {item["mesh_source"]["model_id"] for item in candidates} == {REAL_MODEL_ID}

    instances = []
    for candidate in candidates:
        spec = build_mesh_transform_spec(
            mesh,
            candidate,
            forward_contract=SUPPORTED_FORWARD,
            phi_result=_phi(),
        )
        transformed = execute_mesh_transform(mesh, spec)
        assert transformed["status"]["state"] == "transformed_vertices_ready"
        instances.append(
            build_asset_scene_instance(
                transformed, category="chair", slot=candidate["slot"]
            )
        )

    instances_before = copy.deepcopy(instances)
    mesh_vertices_before = copy.deepcopy(mesh["geometry"]["vertices_xyz"])

    collection = build_asset_scene_instance_collection(
        instances,
        collection_id="real-two-placement",
        context={"room_id": "room-real", "source_scene_id": "scene-real"},
    )

    # count / identity
    assert collection["type"] == "asset_scene_instance_collection"
    assert collection["count"] == 2
    assert collection["instance_ids"] == [
        "scene-real:placement:000000",
        "scene-real:placement:000001",
    ]
    assert len(set(collection["instance_ids"])) == 2

    members = collection["instances"]
    # SAME real asset model, DIFFERENT scene instance identity.
    assert {member["asset"]["model_id"] for member in members} == {REAL_MODEL_ID}
    assert members[0]["instance_id"] != members[1]["instance_id"]

    for member, source in zip(members, instances):
        # vertex / face counts preserved
        assert len(member["geometry"]["vertices_xyz"]) == 475
        assert len(member["geometry"]["faces"]) == 884
        # no geometry mutation, no second transform
        assert member["geometry"]["vertices_xyz"] == source["geometry"]["vertices_xyz"]
        assert member["geometry"]["faces"] == source["geometry"]["faces"]
        assert member["bounds"] == source["bounds"]
        assert member["topology"] == source["topology"]
        assert member["scene_transform"] == source["scene_transform"]
        assert member["provenance"]["executor_transform"] == (
            source["provenance"]["executor_transform"]
        )
        assert member["provenance"]["placement_identity"] == (
            source["provenance"]["placement_identity"]
        )

    # inputs untouched
    assert instances == instances_before
    assert mesh["geometry"]["vertices_xyz"] == mesh_vertices_before

    # no scene insertion and no world-space re-application
    for key in ("scene", "scene_result", "bim", "renderer", "export_result"):
        assert key not in collection
    assert collection["semantics"]["transforms_already_applied"] is True
    assert collection["semantics"]["scene_transform_application_required"] is False
    assert collection["semantics"]["world_space_geometry"] is True
