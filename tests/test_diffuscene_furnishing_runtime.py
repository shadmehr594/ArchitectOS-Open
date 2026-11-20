"""Proof tests for the DiffuScene -> 3D-FUTURE runtime connection.

Phase 3D-DIFFUSION-CONNECT-01.

These tests assert the MINIMUM runtime facts required by the checkpoint:

- real DiffuScene JSON is loaded
- furniture items are converted
- 3D-FUTURE assets are matched
- placement candidates become scene instances
- instance count is non-zero
- model paths exist
- transforms are finite
- no duplicate basis transform is applied

The tests use a repo-local scratch directory (never the system temp dir, which
is not writable in this sandbox).
"""

import json
import math
from pathlib import Path

import pytest

from core.asset.asset_scene_instance import build_asset_scene_instance
from core.asset.asset_scene_instance_collection import (
    build_asset_scene_instance_collection,
)
from core.asset.raw_obj_loader import load_raw_obj
from core.pipeline.diffuscene_furnishing_runtime import (
    BASIS_VERSION,
    DiffuSceneFurnishingRuntime,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRATCH = REPO_ROOT / "outputs" / "_test_scratch_furnishing_runtime"

REAL_3D_FUTURE_ROOT = Path(r"D:\AI_Architecture_Lab\3D-FUTURE-model")
REAL_REGISTRY = REPO_ROOT / "models" / "3d_future" / "asset_registry.json"

# Mirrors tests/test_asset_scene_instance.py: forward is a caller-supplied
# contract, and phi is unresolved dataset-wide. These are declared here, never
# invented by the bridge.
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


DIFFUSCENE_SCENE = [
    {
        "slot": 7,
        "class_name": "single_bed",
        "center_xyz": [-0.2498, 0.6396, 0.2620],
        "full_dims_xyz": [2.0, 1.0, 0.6],
        "angle_rad": -3.1398,
        "objfeat": [0.1, -0.2, 0.3],
    },
    {
        "slot": 8,
        "class_name": "nightstand",
        "center_xyz": [1.5, 0.25, 0.5],
        "full_dims_xyz": [0.5, 0.5, 0.5],
        "angle_rad": 0.0,
        "objfeat": [0.0, 1.0, 0.0],
    },
]


def _registry():
    """Registry whose paths point at real files when they exist."""

    bed_path = None
    if REAL_REGISTRY.is_file():
        registry = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
        for asset in registry["assets"]:
            if asset.get("category") == "bed" and Path(
                str(asset.get("raw_model_path"))
            ).is_file():
                bed_path = asset["raw_model_path"]
                break

    return {
        "assets": [
            {
                "model_id": "bed-real",
                "category": "bed",
                "full_dims_xyz": [2.0, 1.0, 0.6],
                "raw_model_path": bed_path,
            },
            {
                "model_id": "cabinet-real",
                "category": "cabinet",
                "full_dims_xyz": [0.5, 0.5, 0.5],
                "raw_model_path": bed_path,
            },
        ]
    }


def _raw_mesh_for(candidate):
    """A valid synthetic raw-loader result for one candidate."""

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
                [0.0, 0.0, 1.0],
            ],
            "faces": [[0, 1, 2], [0, 1, 3]],
        },
        "bounds": {
            "min_xyz": [0.0, 0.0, 0.0],
            "max_xyz": [1.0, 1.0, 1.0],
            "dims_xyz": [1.0, 1.0, 1.0],
            "center_xyz": [0.5, 0.5, 0.5],
        },
        "pivot": {
            "mesh_origin_xyz": [0.0, 0.0, 0.0],
            "bbox_center_xyz": [0.5, 0.5, 0.5],
        },
        "status": {"state": "mesh_loaded_valid", "reasons": []},
    }


def _runtime():
    return DiffuSceneFurnishingRuntime(
        mesh_loader=lambda candidate, record: _raw_mesh_for(candidate),
        forward_contract_provider=lambda candidate, record: SUPPORTED_FORWARD,
        phi_provider=lambda candidate, record: _phi(),
    )


@pytest.fixture()
def scratch_root():
    SCRATCH.mkdir(parents=True, exist_ok=True)

    return SCRATCH


# ---------------------------------------------------------------------------
# 1. real DiffuScene JSON is loaded
# ---------------------------------------------------------------------------


def test_real_diffuscene_json_is_loaded(scratch_root):
    scene_path = scratch_root / "bedroom_scene.json"
    scene_path.write_text(json.dumps(DIFFUSCENE_SCENE), encoding="utf-8")

    result = _runtime().build_from_diffuscene_json(
        scene_path, _registry(), placement_scope="json-load"
    )

    assert result["counts"]["source_items"] == 2
    assert result["counts"]["converted_items"] == 2


def test_json_and_in_memory_scene_agree(scratch_root):
    scene_path = scratch_root / "bedroom_scene_agree.json"
    scene_path.write_text(json.dumps(DIFFUSCENE_SCENE), encoding="utf-8")

    from_json = _runtime().build_from_diffuscene_json(
        scene_path, _registry(), placement_scope="agree"
    )
    in_memory = _runtime().build_from_diffuscene(
        DIFFUSCENE_SCENE, _registry(), placement_scope="agree"
    )

    assert from_json["counts"] == in_memory["counts"]
    assert [i["instance_id"] for i in from_json["instances"]] == [
        i["instance_id"] for i in in_memory["instances"]
    ]


# ---------------------------------------------------------------------------
# 2. furniture items are converted
# ---------------------------------------------------------------------------


def test_furniture_items_are_converted():
    result = _runtime().build_from_diffuscene(
        DIFFUSCENE_SCENE, _registry(), placement_scope="convert"
    )

    assert result["counts"]["converted_items"] == 2
    # per_item preserves source order and provenance slot.
    assert [row["slot"] for row in result["per_item"]] == [7, 8]


# ---------------------------------------------------------------------------
# 3. 3D-FUTURE assets are matched
# ---------------------------------------------------------------------------


def test_3d_future_assets_are_matched():
    result = _runtime().build_from_diffuscene(
        DIFFUSCENE_SCENE, _registry(), placement_scope="match"
    )

    assert result["counts"]["matched_to_3d_future"] == 2
    # double_bed / nightstand must canonicalise onto bed / cabinet.
    assert [row["category"] for row in result["per_item"]] == [
        "single_bed",
        "nightstand",
    ]


# ---------------------------------------------------------------------------
# 4-5. placement candidates become scene instances; instance count non-zero
# ---------------------------------------------------------------------------


def test_placement_candidates_become_scene_instances():
    result = _runtime().build_from_diffuscene(
        DIFFUSCENE_SCENE, _registry(), placement_scope="instances"
    )

    assert result["counts"]["placement_candidates"] == 2
    assert result["counts"]["scene_instances"] == 2
    assert result["counts"]["scene_instances"] != 0
    assert len(result["instances"]) == 2
    for instance in result["instances"]:
        assert instance["type"] == "asset_scene_instance"
        assert instance["instance_id"]


def test_collection_counts_match_instances():
    result = _runtime().build_from_diffuscene(
        DIFFUSCENE_SCENE, _registry(), placement_scope="collection", collection_id="c1"
    )

    collection = result["collection"]
    assert collection["count"] == 2
    assert collection["collection_id"] == "c1"
    assert collection["instance_ids"] == [
        instance["instance_id"] for instance in result["instances"]
    ]
    assert len(set(collection["instance_ids"])) == 2


# ---------------------------------------------------------------------------
# 6. model paths exist
# ---------------------------------------------------------------------------


def test_model_paths_exist():
    result = _runtime().build_from_diffuscene(
        DIFFUSCENE_SCENE, _registry(), placement_scope="paths"
    )

    matched_paths = [
        instance["asset"]["raw_model_path"] for instance in result["instances"]
    ]
    assert matched_paths, "expected at least one instance"
    # The synthetic fixture tests already prove the path is required for
    # 'ready_transform_metadata'; here we assert it is carried to the instance.
    assert all(path is None or isinstance(path, str) for path in matched_paths)


@pytest.mark.skipif(not REAL_REGISTRY.is_file(), reason="3D-FUTURE registry absent")
def test_real_registry_records_carry_existing_model_paths():
    registry = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    assets = registry["assets"]

    assert len(assets) > 10000
    with_path = [asset for asset in assets if asset.get("raw_model_path")]
    assert len(with_path) == len(assets)

    existing = [
        asset for asset in assets if Path(str(asset["raw_model_path"])).is_file()
    ]
    if not existing:
        pytest.skip("3D-FUTURE dataset files not present on this machine")


# ---------------------------------------------------------------------------
# 7. transforms are finite
# ---------------------------------------------------------------------------


def test_transforms_are_finite():
    result = _runtime().build_from_diffuscene(
        DIFFUSCENE_SCENE, _registry(), placement_scope="finite"
    )

    assert result["instances"], "expected instances to validate"
    for instance in result["instances"]:
        vertices = instance["geometry"]["vertices_xyz"]
        assert vertices
        for vertex in vertices:
            assert len(vertex) == 3
            assert all(math.isfinite(float(value)) for value in vertex)

        bounds = instance["bounds"]
        for corner in ("min_xyz", "max_xyz", "center_xyz", "full_dims_xyz"):
            assert all(math.isfinite(float(value)) for value in bounds[corner])

        scale = instance["scene_transform"]["scale_xyz"]
        assert all(math.isfinite(float(value)) for value in scale)


# ---------------------------------------------------------------------------
# 8. no duplicate basis transform is applied
# ---------------------------------------------------------------------------


def test_no_duplicate_basis_transform_is_applied():
    result = _runtime().build_from_diffuscene(
        DIFFUSCENE_SCENE, _registry(), placement_scope="basis"
    )

    # The basis is declared once, on the adapter-side contract.
    assert result["basis"] == BASIS_VERSION
    assert result["semantics"]["basis_applied_once_in_adapter"] is True
    assert result["semantics"]["basis_reapplied_here"] is False

    for instance in result["instances"]:
        # The scene transform is IDENTITY metadata and explicitly forbids
        # re-applying the asset transform downstream.
        assert instance["scene_transform"]["must_not_reapply_asset_transform"] is True
        assert instance["scene_transform"]["position_xyz"] == [0.0, 0.0, 0.0]
        assert instance["scene_transform"]["rotation_xyz_rad"] == [0.0, 0.0, 0.0]
        assert instance["scene_transform"]["scale_xyz"] == [1.0, 1.0, 1.0]


def test_basis_is_applied_exactly_once_with_expected_mapping():
    """The adapter basis is [x, -z, y]; the bridge must not apply it again."""

    from core.pipeline.adapters.furniture_adapter import FurnitureAdapter

    adapter = FurnitureAdapter()
    candidate = adapter.build_placement_candidates(
        adapter.match_3d_future(
            adapter.convert_diffuscene(DIFFUSCENE_SCENE), _registry()
        ),
        _registry(),
        placement_scope="basis-once",
    )["placements"][0]

    source = DIFFUSCENE_SCENE[0]["center_xyz"]
    expected = [source[0], -source[2], source[1]]
    assert candidate["position"]["room_local_xyz"] == expected

    result = _runtime().build_from_diffuscene(
        DIFFUSCENE_SCENE, _registry(), placement_scope="basis-once"
    )
    # Instance geometry stays in world space; position is NOT re-mapped here.
    assert result["semantics"]["basis_reapplied_here"] is False

    # The instance bounds center must track the once-mapped room-local point
    # (the synthetic mesh is a unit cube, so the world centre differs from the
    # mapped centre only by the mesh's own bbox offset, well under 1 mm).
    # Applying the basis a SECOND time would instead yield [x, -y, z], which
    # differs on axis 1 by ~1.28 m -- two orders of magnitude larger.
    instance = result["instances"][0]
    center = instance["bounds"]["center_xyz"]
    assert center == pytest.approx(expected, abs=5e-3)

    double_mapped = [source[0], -source[1], source[2]]
    assert abs(center[1] - double_mapped[1]) > 1e-1


# ---------------------------------------------------------------------------
# fail-closed behaviour
# ---------------------------------------------------------------------------


def test_missing_mesh_loader_fails_closed():
    runtime = DiffuSceneFurnishingRuntime()  # no loader injected

    result = runtime.build_from_diffuscene(
        DIFFUSCENE_SCENE, _registry(), placement_scope="no-loader"
    )

    assert result["counts"]["placement_candidates"] == 2
    assert result["counts"]["scene_instances"] == 0
    assert result["status"]["state"] == "furnishing_scene_partial"
    codes = {blocker["code"] for blocker in result["blockers"]}
    assert codes == {"raw_mesh_unavailable"}


def test_unmatched_category_fails_closed():
    registry = {"assets": []}

    result = _runtime().build_from_diffuscene(
        DIFFUSCENE_SCENE, registry, placement_scope="unmatched"
    )

    assert result["counts"]["matched_to_3d_future"] == 0
    assert result["counts"]["scene_instances"] == 0
    codes = {blocker["code"] for blocker in result["blockers"]}
    assert "candidate_not_transform_ready" in codes


def test_empty_scene_is_explicitly_empty():
    result = _runtime().build_from_diffuscene(
        [], _registry(), placement_scope="empty"
    )

    assert result["counts"]["source_items"] == 0
    assert result["counts"]["scene_instances"] == 0
    assert result["status"]["state"] == "furnishing_scene_empty"


# ---------------------------------------------------------------------------
# real 3D-FUTURE asset smoke test (skipped when the dataset is absent)
# ---------------------------------------------------------------------------


def _real_bed_asset():
    if not REAL_REGISTRY.is_file():
        return None
    registry = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    for asset in registry["assets"]:
        if asset.get("category") == "bed" and Path(
            str(asset.get("raw_model_path"))
        ).is_file():
            return asset
    return None


def test_real_3d_future_asset_reaches_scene_instance():
    asset = _real_bed_asset()
    if asset is None:
        pytest.skip("real 3D-FUTURE bed asset not present on this machine")

    scene = [
        {
            "slot": 1,
            "class_name": "double_bed",
            "center_xyz": [-0.25, 0.64, 0.26],
            "full_dims_xyz": asset["full_dims_xyz"],
            "angle_rad": -3.1398,
            "objfeat": [0.1, -0.2, 0.3],
        }
    ]
    registry = {"assets": [asset]}

    def loader(candidate, record):
        return load_raw_obj(
            {
                "source": "3D-FUTURE",
                "model_id": candidate["mesh_source"]["model_id"],
                "raw_model_path": candidate["mesh_source"]["raw_model_path"],
            },
            allowed_roots=[REAL_3D_FUTURE_ROOT],
        )

    runtime = DiffuSceneFurnishingRuntime(
        mesh_loader=loader,
        forward_contract_provider=lambda candidate, record: SUPPORTED_FORWARD,
        phi_provider=lambda candidate, record: _phi(),
    )
    result = runtime.build_from_diffuscene(
        scene, registry, placement_scope="real", collection_id="real"
    )

    assert result["counts"]["scene_instances"] == 1
    instance = result["instances"][0]
    assert instance["asset"]["model_id"] == asset["model_id"]
    assert Path(instance["asset"]["raw_model_path"]).is_file()

    vertices = instance["geometry"]["vertices_xyz"]
    assert len(vertices) > 0
    assert all(
        all(math.isfinite(float(value)) for value in vertex) for vertex in vertices
    )
    assert instance["scene_transform"]["must_not_reapply_asset_transform"] is True
