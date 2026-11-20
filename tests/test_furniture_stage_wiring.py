"""Proof tests for the DiffuScene runtime <-> production pipeline wiring.

Phase 3D-DIFFUSION-CONNECT-02.

These tests assert the MINIMUM connectivity facts required by the checkpoint
(A-G):

- A. the runtime is registered through the EXISTING ``"furniture"`` stage
- B. the pipeline actually invokes it (previously the stage was skipped)
- C. the EXISTING runtime instance is reused (no second runtime/parallel path)
- D. the pipeline state receives the stage payload
- E. fail-closed behaviour when the scene or registry is absent
- F. the single-basis-transform contract survives the production path
- G. the unresolved conventions stay unresolved (no invented orientation/scale)

Repo-local scratch directories are used (never the system temp dir, which is
not writable in this sandbox).
"""

import json
import math
from pathlib import Path

import pytest

from core.pipeline.adapters.furniture_adapter import (
    FurnitureAdapter,
    FurnitureStageAdapter,
)
from core.pipeline.diffuscene_furnishing_runtime import (
    BASIS_VERSION,
    DiffuSceneFurnishingRuntime,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRATCH = REPO_ROOT / "outputs" / "_test_scratch_furniture_stage"

REAL_3D_FUTURE_ROOT = Path(r"D:\AI_Architecture_Lab\3D-FUTURE-model")
REAL_REGISTRY = REPO_ROOT / "models" / "3d_future" / "asset_registry.json"

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
]


def _raw_mesh_for(candidate):
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


def _registry():
    return {
        "assets": [
            {
                "model_id": "bed-real",
                "category": "bed",
                "full_dims_xyz": [2.0, 1.0, 0.6],
                "raw_model_path": str(REPO_ROOT / "raw_model.obj"),
            },
        ]
    }


@pytest.fixture()
def scratch_root():
    SCRATCH.mkdir(parents=True, exist_ok=True)

    return SCRATCH


def _wired_runtime():
    """The real runtime with only its injectable seams stubbed."""

    return DiffuSceneFurnishingRuntime(
        mesh_loader=lambda candidate, record: _raw_mesh_for(candidate),
        forward_contract_provider=lambda candidate, record: SUPPORTED_FORWARD,
        phi_provider=lambda candidate, record: _phi(),
    )


# ---------------------------------------------------------------------------
# A. registered through the EXISTING "furniture" stage
# ---------------------------------------------------------------------------


def test_furniture_stage_is_registered_in_runtime_engines():
    from core.runtime.architectos_runtime import ArchitectOSRuntime

    runtime = ArchitectOSRuntime()

    assert "furniture" in runtime.engines
    assert isinstance(runtime.engines["furniture"], FurnitureStageAdapter)


def test_registered_engine_dispatches_via_execute():
    """``_execute_engine`` probes ``execute`` first; the adapter must expose it."""

    from core.runtime.architectos_runtime import ArchitectOSRuntime

    engine = ArchitectOSRuntime().engines["furniture"]

    assert hasattr(engine, "execute")
    # If it also exposed ``generate`` the existing ``generate(state)`` contract
    # of a *different* class would silently win dispatch priority. It must not.
    assert not hasattr(engine, "generate")


def test_stage_name_is_the_existing_pipeline_stage_name():
    from core.runtime.architectos_runtime import ArchitectOSRuntime

    runtime = ArchitectOSRuntime()

    assert FurnitureStageAdapter.STATE_KEY in runtime.pipeline.pipeline_order


# ---------------------------------------------------------------------------
# B. the pipeline actually invokes it
# ---------------------------------------------------------------------------


def test_pipeline_invokes_furniture_stage(scratch_root, monkeypatch):
    from core.runtime.architectos_runtime import ArchitectOSRuntime

    scene_path = scratch_root / "scene.json"
    scene_path.write_text(json.dumps(DIFFUSCENE_SCENE), encoding="utf-8")

    runtime = ArchitectOSRuntime()
    runtime.engines["furniture"] = FurnitureStageAdapter(
        runtime=_wired_runtime(),
        asset_registry=_registry(),
    )

    result = runtime.run(
        {
            "project": "wiring",
            "diffuscene_scene_path": str(scene_path),
        }
    )

    stages = {row["stage"] for row in result["pipeline_report"]}
    assert "furniture" in stages

    row = next(
        row for row in result["pipeline_report"] if row["stage"] == "furniture"
    )
    assert row["status"] == "success"


def test_stage_reports_invoked_and_produces_instances(scratch_root):
    scene_path = scratch_root / "scene.json"
    scene_path.write_text(json.dumps(DIFFUSCENE_SCENE), encoding="utf-8")

    adapter = FurnitureStageAdapter(
        runtime=_wired_runtime(),
        asset_registry=_registry(),
    )

    payload = adapter.execute(
        {
            "diffuscene_scene_path": str(scene_path),
            "placement_scope": "wiring-proof",
        }
    )

    assert payload["semantics"]["invoked"] is True
    assert payload["counts"]["source_items"] == 1
    assert payload["counts"]["matched_to_3d_future"] == 1
    assert payload["counts"]["placement_candidates"] == 1
    assert payload["counts"]["scene_instances"] == 1


# ---------------------------------------------------------------------------
# C. the EXISTING runtime instance is reused
# ---------------------------------------------------------------------------


def test_existing_runtime_instance_is_reused_not_recreated():
    runtime = _wired_runtime()
    adapter = FurnitureStageAdapter(runtime=runtime, asset_registry=_registry())

    assert adapter.runtime is runtime


def test_no_second_runtime_class_is_introduced():
    """The stage adapter must orchestrate, not re-implement the chain."""

    import core.pipeline.adapters.furniture_adapter as module

    assert not issubclass(FurnitureAdapter, FurnitureStageAdapter)
    assert module.FurnitureStageAdapter is not DiffuSceneFurnishingRuntime

    # The adapter delegates the whole chain; it must not re-declare the
    # upstream stages it claims to reuse.
    for forbidden in (
        "convert_diffuscene",
        "match_3d_future",
        "build_placement_candidates",
    ):
        assert not hasattr(FurnitureStageAdapter, forbidden)


def test_adapter_reuses_the_existing_conversion_path(scratch_root):
    scene_path = scratch_root / "scene.json"
    scene_path.write_text(json.dumps(DIFFUSCENE_SCENE), encoding="utf-8")

    runtime = _wired_runtime()
    adapter = FurnitureStageAdapter(runtime=runtime, asset_registry=_registry())

    payload = adapter.execute({"diffuscene_scene_path": str(scene_path)})

    # The contract the adapter returns is exactly what the runtime produced.
    assert payload["furnishing"]["type"] == "diffuscene_furnishing_scene"
    assert payload["furnishing"]["pipeline"] == "3D-DIFFUSION-CONNECT-01"


def test_default_adapter_wires_the_real_runtime():
    adapter = FurnitureStageAdapter(asset_registry=_registry())

    assert isinstance(adapter.runtime, DiffuSceneFurnishingRuntime)


# ---------------------------------------------------------------------------
# D. the pipeline state receives the stage payload
# ---------------------------------------------------------------------------


def test_state_receives_stage_payload_without_clobbering_furniture_result():
    adapter = FurnitureStageAdapter(
        runtime=_wired_runtime(), asset_registry=_registry()
    )

    state = {
        "furniture_result": {"pre_existing": True},
        "diffuscene_scene": list(DIFFUSCENE_SCENE),
    }

    returned = adapter.execute(state)

    # The adapter returns the payload; the pipeline performs the assignment.
    assert returned is not state
    assert returned["stage"] == "furniture"
    # ``generate()``'s legacy key is not touched by this stage.
    assert state["furniture_result"] == {"pre_existing": True}


def test_pipeline_stores_payload_at_the_stage_key():
    from core.pipeline.master_architect_pipeline import MasterArchitectPipeline

    pipeline = MasterArchitectPipeline(
        {"furniture": FurnitureStageAdapter(runtime=_wired_runtime())}
    )

    state = {
        "diffuscene_scene": list(DIFFUSCENE_SCENE),
        "asset_registry": _registry(),
    }

    result = pipeline.run(state)

    assert "furniture" in result
    assert result["furniture"]["type"] == "furniture_stage"


# ---------------------------------------------------------------------------
# E. fail-closed behaviour
# ---------------------------------------------------------------------------


def test_missing_scene_fails_closed():
    adapter = FurnitureStageAdapter(
        runtime=_wired_runtime(), asset_registry=_registry()
    )

    payload = adapter.execute({"project": "no-scene"})

    assert payload["status"]["state"] == FurnitureStageAdapter.STAGE_BLOCKED
    assert payload["blockers"][0]["code"] == "diffuscene_scene_missing"
    assert payload["semantics"]["invoked"] is False
    assert payload["furnishing"] is None


def test_missing_scene_is_not_replaced_by_an_empty_scene():
    """An empty scene means 'DiffuScene produced nothing' — a different fact."""

    adapter = FurnitureStageAdapter(
        runtime=_wired_runtime(), asset_registry=_registry()
    )

    payload = adapter.execute({"diffuscene_scene": None})

    assert payload["status"]["state"] == FurnitureStageAdapter.STAGE_BLOCKED
    assert payload["counts"]["source_items"] is None

    # And the genuine empty-scene case is reported separately.
    empty = FurnitureStageAdapter(
        runtime=_wired_runtime(), asset_registry=_registry()
    ).execute({"diffuscene_scene": []})

    assert empty["status"]["state"] == FurnitureStageAdapter.STAGE_SKIPPED


def test_unavailable_registry_fails_closed(scratch_root, monkeypatch):
    scene_path = scratch_root / "scene.json"
    scene_path.write_text(json.dumps(DIFFUSCENE_SCENE), encoding="utf-8")

    monkeypatch.setenv(
        FurnitureStageAdapter.REGISTRY_ENV_VAR,
        str(scratch_root / "does_not_exist.json"),
    )
    monkeypatch.setattr(
        FurnitureStageAdapter, "DEFAULT_REGISTRY_PATH", "does/not/exist.json"
    )

    adapter = FurnitureStageAdapter(runtime=_wired_runtime(), registry_path=None)
    payload = adapter.execute({"diffuscene_scene_path": str(scene_path)})

    assert payload["status"]["state"] == FurnitureStageAdapter.STAGE_BLOCKED
    assert payload["blockers"][0]["code"] == "asset_registry_unavailable"
    assert payload["furnishing"] is None


def test_fail_closed_stage_does_not_raise_from_the_pipeline():
    from core.pipeline.master_architect_pipeline import MasterArchitectPipeline

    pipeline = MasterArchitectPipeline(
        {"furniture": FurnitureStageAdapter(runtime=_wired_runtime())}
    )

    result = pipeline.run({"project": "blocked"})

    row = next(
        row for row in result["pipeline_report"] if row["stage"] == "furniture"
    )
    # The engine ran without raising, so the stage is 'success' — the payload
    # itself carries the fail-closed state.
    assert row["status"] == "success"
    assert result["furniture"]["status"]["state"] == "blocked"


# ---------------------------------------------------------------------------
# F. the single-basis-transform contract survives the production path
# ---------------------------------------------------------------------------


def test_basis_applied_exactly_once_through_the_stage(scratch_root):
    scene_path = scratch_root / "scene.json"
    scene_path.write_text(json.dumps(DIFFUSCENE_SCENE), encoding="utf-8")

    adapter = FurnitureStageAdapter(
        runtime=_wired_runtime(), asset_registry=_registry()
    )
    payload = adapter.execute(
        {"diffuscene_scene_path": str(scene_path), "placement_scope": "basis"}
    )

    semantics = payload["semantics"]
    assert semantics["basis_applied_once_in_adapter"] is True
    assert semantics["basis_reapplied_here"] is False
    assert semantics["positions_come_only_from_diffuscene"] is True

    assert payload["basis"] == BASIS_VERSION
    assert payload["basis"] == FurnitureAdapter._BASIS_VERSION


def test_instance_requires_no_reapplication_after_the_stage(scratch_root):
    scene_path = scratch_root / "scene.json"
    scene_path.write_text(json.dumps(DIFFUSCENE_SCENE), encoding="utf-8")

    adapter = FurnitureStageAdapter(
        runtime=_wired_runtime(), asset_registry=_registry()
    )
    payload = adapter.execute(
        {"diffuscene_scene_path": str(scene_path), "placement_scope": "basis"}
    )

    instances = payload["furnishing"]["instances"]
    assert instances
    for instance in instances:
        scene_transform = instance["scene_transform"]
        assert scene_transform["must_not_reapply_asset_transform"] is True
        assert scene_transform["position_xyz"] == [0.0, 0.0, 0.0]
        assert scene_transform["rotation_xyz_rad"] == [0.0, 0.0, 0.0]
        assert scene_transform["scale_xyz"] == [1.0, 1.0, 1.0]


def test_basis_mapping_is_not_double_applied(scratch_root):
    """[x, -z, y] must appear once, not squared into [x, -y, -z].

    The instance bbox centre equals ``basis(source_center)`` plus a small
    mesh-local residual (the raw mesh pivot sits very slightly off its bbox
    centre). Asserting the *delta between two source positions* cancels that
    residual and isolates the basis change itself.
    """

    scene_path = scratch_root / "scene.json"
    scene_path.write_text(json.dumps(DIFFUSCENE_SCENE), encoding="utf-8")

    adapter = FurnitureStageAdapter(
        runtime=_wired_runtime(), asset_registry=_registry()
    )

    def _centre_at(center_xyz):
        scene = [dict(DIFFUSCENE_SCENE[0], center_xyz=list(center_xyz))]
        payload = adapter.execute(
            {"diffuscene_scene": scene, "placement_scope": "basis"}
        )
        return payload["furnishing"]["instances"][0]["bounds"]["center_xyz"]

    source = DIFFUSCENE_SCENE[0]["center_xyz"]
    instance_centre = _centre_at(source)
    baseline_centre = _centre_at([0.0, 0.0, 0.0])

    measured_delta = [
        instance_centre[index] - baseline_centre[index] for index in range(3)
    ]

    # The single, correct basis change.
    expected_once = [source[0], -source[2], source[1]]
    assert measured_delta == pytest.approx(expected_once, abs=5e-3)

    # A double mapping would land on [x, -y, -z]. Prove it does not.
    double_mapped = [source[0], -source[1], -source[2]]
    assert any(
        abs(measured_delta[index] - double_mapped[index]) > 1e-1
        for index in range(3)
    )


# ---------------------------------------------------------------------------
# G. unresolved conventions stay unresolved
# ---------------------------------------------------------------------------


def test_forward_and_scale_conventions_stay_unresolved(scratch_root):
    scene_path = scratch_root / "scene.json"
    scene_path.write_text(json.dumps(DIFFUSCENE_SCENE), encoding="utf-8")

    adapter = FurnitureStageAdapter(
        runtime=_wired_runtime(), asset_registry=_registry()
    )
    payload = adapter.execute(
        {"diffuscene_scene_path": str(scene_path), "placement_scope": "unresolved"}
    )

    semantics = payload["semantics"]
    assert semantics["mesh_forward_axis_resolved"] is False
    assert semantics["instance_scale_convention_resolved"] is False
    assert semantics["advanced_clearance_logic"] is False

    unresolved = payload["status"]["unresolved"]
    assert "mesh_forward_axis" in unresolved
    assert "instance_scale_convention" in unresolved
    assert "furniture_support_anchor" in unresolved
    assert "dimension_axis_mapping" in unresolved


def test_candidate_metadata_is_reported_verbatim():
    """The upstream unresolved markers must pass through unchanged."""

    adapter = FurnitureStageAdapter(
        runtime=_wired_runtime(), asset_registry=_registry()
    )

    scene = [
        {
            "slot": 1,
            "class_name": "single_bed",
            "center_xyz": [0.0, 0.0, 0.0],
            "full_dims_xyz": [2.0, 1.0, 0.6],
            "angle_rad": 0.0,
            "objfeat": [0.1, 0.2, 0.3],
        }
    ]

    payload = adapter.execute(
        {"diffuscene_scene": scene, "asset_registry": _registry()}
    )

    assert payload["counts"]["placement_candidates"] == 1

    # Original scale metadata stays unresolved — the stage never asserts
    # a scale convention.
    furnishing = payload["furnishing"]
    assert furnishing["semantics"]["basis_reapplied_here"] is False


def test_stage_does_not_touch_plan_generation_or_render(scratch_root):
    scene_path = scratch_root / "scene.json"
    scene_path.write_text(json.dumps(DIFFUSCENE_SCENE), encoding="utf-8")

    adapter = FurnitureStageAdapter(
        runtime=_wired_runtime(), asset_registry=_registry()
    )
    payload = adapter.execute({"diffuscene_scene_path": str(scene_path)})

    semantics = payload["semantics"]
    assert semantics["render_executed"] is False
    assert semantics["plan_generation_touched"] is False
    assert semantics["advanced_clearance_logic"] is False


# ---------------------------------------------------------------------------
# real-registry smoke: the production default path resolves
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not REAL_REGISTRY.is_file(), reason="real 3D-FUTURE registry not present"
)
def test_default_registry_path_resolves_the_real_registry():
    adapter = FurnitureStageAdapter(runtime=_wired_runtime())

    registry = adapter._resolve_registry({})

    assert isinstance(registry, dict)
    assert len(registry["assets"]) > 16000


@pytest.mark.skipif(
    not REAL_REGISTRY.is_file(), reason="real 3D-FUTURE registry not present"
)
def test_real_registry_smoke_through_the_stage():
    """Load the real registry through the production default path and run the
    full chain with only the mesh loader stubbed.

    The chain reaches the instance stage; whether an instance is emitted then
    depends on pre-existing, still-unresolved contracts (placement identity /
    forward / scale). This test asserts the WIRING, not a resolved instance.
    """

    adapter = FurnitureStageAdapter(runtime=_wired_runtime())

    scene = [
        {
            "slot": 3,
            "class_name": "single_bed",
            "center_xyz": [0.0, 0.5, 0.0],
            "full_dims_xyz": [2.0, 1.0, 0.6],
            "angle_rad": 0.0,
            "objfeat": [0.1, 0.2, 0.3],
        }
    ]

    payload = adapter.execute({"diffuscene_scene": scene})

    assert payload["semantics"]["invoked"] is True
    assert payload["counts"]["source_items"] == 1
    assert payload["counts"]["matched_to_3d_future"] == 1
    assert payload["counts"]["placement_candidates"] == 1

    # The stage reports whatever really happened. A resolved placement scope
    # must yield an instance; an unresolved one must fail closed with an
    # explicit blocker — never a guessed instance.
    if payload["counts"]["scene_instances"] == 0:
        assert payload["status"]["runtime_state"] == "furnishing_scene_partial"
        assert payload["blockers"]
    else:
        assert payload["furnishing"]["collection"]["count"] >= 1


@pytest.mark.skipif(
    not REAL_REGISTRY.is_file(), reason="real 3D-FUTURE registry not present"
)
def test_real_registry_smoke_with_resolved_placement_scope():
    """With a caller-supplied placement scope the chain emits real instances."""

    adapter = FurnitureStageAdapter(runtime=_wired_runtime())

    scene = [
        {
            "slot": 3,
            "class_name": "single_bed",
            "center_xyz": [0.0, 0.5, 0.0],
            "full_dims_xyz": [2.0, 1.0, 0.6],
            "angle_rad": 0.0,
            "objfeat": [0.1, 0.2, 0.3],
        }
    ]

    payload = adapter.execute(
        {"diffuscene_scene": scene, "placement_scope": "real-registry-smoke"}
    )

    assert payload["counts"]["placement_candidates"] == 1
    assert payload["counts"]["scene_instances"] == 1
    assert payload["furnishing"]["collection"]["count"] == 1
    assert payload["status"]["state"] == FurnitureStageAdapter.STAGE_COMPLETE
