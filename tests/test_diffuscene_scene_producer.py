"""Proof tests for the DiffuScene scene producer stage.

Phase 3D-DIFFUSION-CONNECT-03.

Two clearly separated layers, as the directive requires:

* **Unit tests** use an injected ``runner`` so they never pay for 1000 DDPM
  steps. They cover the contract, the fail-closed matrix and the wiring.
* **ONE integration proof** uses the REAL external DiffuScene runtime through
  the producer's DEFAULT runner. It is skipped (not faked) when the external
  environment is unavailable, so a mock can never stand in for it.

Required facts A-H are covered at the bottom of this file.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from core.pipeline.diffuscene_scene_producer import (
    DEFAULT_DIFFUSCENE_ROOT,
    DEFAULT_INTERPRETER,
    DEFAULT_SCRIPT,
    DIFFUSCENE_ROOT_ENV_VAR,
    SCENE_STATE_KEY,
    STAGE_NAME,
    STATE_BLOCKED,
    STATE_EMPTY,
    STATE_PRODUCED,
    DiffuSceneSceneProducer,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRATCH = REPO_ROOT / "outputs" / "_test_scratch_diffuscene_producer"


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def scratch_root():
    SCRATCH.mkdir(parents=True, exist_ok=True)

    return SCRATCH


def _native_scene(n=2):
    """The native DiffuScene contract FurnitureAdapter already accepts."""

    return [
        {
            "slot": index,
            "class_index": 10 + index,
            "class_name": "single_bed" if index == 0 else "nightstand",
            "center_xyz": [0.1 * index, 0.5, 0.2],
            "half_size_xyz": [1.0, 0.5, 0.3],
            "full_dims_xyz": [2.0, 1.0, 0.6],
            "angle_pair": [1.0, 0.0],
            "angle_rad": 0.0,
            "angle_deg": 0.0,
            "objfeat": [0.1, 0.2, 0.3],
        }
        for index in range(n)
    ]


def _runner_returning(scene, invoked=True):
    def runner(request):
        return {
            "scene": scene,
            "status": "ok",
            "blockers": [],
            "invoked": invoked,
            "source": "injected_runner",
        }

    return runner


def _producer(**kwargs):
    return DiffuSceneSceneProducer(**kwargs)


# ---------------------------------------------------------------------------
# stage registration / ordering
# ---------------------------------------------------------------------------


def test_stage_is_registered_and_runs_before_furniture():
    from core.runtime.architectos_runtime import ArchitectOSRuntime

    runtime = ArchitectOSRuntime()

    assert STAGE_NAME in runtime.engines
    assert isinstance(runtime.engines[STAGE_NAME], DiffuSceneSceneProducer)

    order = runtime.pipeline.pipeline_order
    assert STAGE_NAME in order
    assert order.index(STAGE_NAME) < order.index("furniture")
    assert order.index("furniture") - order.index(STAGE_NAME) == 1


def test_producer_exposes_execute_for_pipeline_dispatch():
    producer = _producer()

    assert hasattr(producer, "execute")
    # Must not collide with the furniture adapter's ``generate`` contract.
    assert not hasattr(producer, "generate")


def test_producer_writes_the_exact_key_connect02_reads():
    from core.pipeline.adapters.furniture_adapter import FurnitureStageAdapter

    assert SCENE_STATE_KEY == FurnitureStageAdapter().scene_key


# ---------------------------------------------------------------------------
# state population
# ---------------------------------------------------------------------------


def test_state_key_populated_on_success():
    producer = _producer(runner=_runner_returning(_native_scene()))

    state = {}
    payload = producer.execute(state)

    assert payload["status"]["state"] == STATE_PRODUCED
    assert payload["state_key_written"] is True
    assert state[SCENE_STATE_KEY] == _native_scene()
    assert payload["counts"]["scene_items"] == 2


def test_state_key_not_written_when_blocked():
    producer = _producer(
        runner=lambda request: {
            "scene": None,
            "status": STATE_BLOCKED,
            "blockers": [{"code": "diffuscene_inference_failed", "detail": "x"}],
            "invoked": True,
        }
    )

    state = {}
    payload = producer.execute(state)

    assert payload["status"]["state"] == STATE_BLOCKED
    assert payload["state_key_written"] is False
    assert SCENE_STATE_KEY not in state


def test_empty_scene_is_reported_as_empty_not_success():
    """An empty list is a real outcome, never a fabricated success."""

    producer = _producer(runner=_runner_returning([]))

    payload = producer.execute({})

    assert payload["status"]["state"] == STATE_EMPTY
    assert payload["semantics"]["empty_scene_returned_as_success"] is False


# ---------------------------------------------------------------------------
# scene contract validation (native schema only)
# ---------------------------------------------------------------------------


def test_valid_native_scene_passes_validation():
    producer = _producer()

    assert producer._validate_scene(_native_scene()) == []


def test_non_list_scene_is_blocked():
    producer = _producer(runner=_runner_returning({"not": "a list"}))

    payload = producer.execute({})

    assert payload["status"]["state"] == STATE_BLOCKED
    assert payload["blockers"][0]["code"] == "diffuscene_scene_not_a_list"


def test_item_missing_required_keys_is_blocked():
    broken = [{"slot": 0, "class_name": "bed"}]
    producer = _producer(runner=_runner_returning(broken))

    payload = producer.execute({})

    assert payload["status"]["state"] == STATE_BLOCKED
    blocker = payload["blockers"][0]
    assert blocker["code"] == "diffuscene_scene_item_missing_keys"
    assert "center_xyz" in blocker["detail"]["missing"]


def test_scene_keeps_extra_native_fields():
    """Extra DiffuScene fields must survive; no schema narrowing."""

    scene = _native_scene(1)
    scene[0]["angle_pair"] = [1.0, 0.0]
    scene[0]["class_index"] = 42

    producer = _producer(runner=_runner_returning(scene))
    state = {}
    producer.execute(state)

    assert state[SCENE_STATE_KEY][0]["angle_pair"] == [1.0, 0.0]
    assert state[SCENE_STATE_KEY][0]["class_index"] == 42


# ---------------------------------------------------------------------------
# fail-closed matrix
# ---------------------------------------------------------------------------


def test_root_unavailable_fails_closed(scratch_root):
    producer = _producer(diffuscene_root=scratch_root / "nope")

    out = producer._invoke_external({})

    assert out["status"] == STATE_BLOCKED
    assert out["blockers"][0]["code"] == "diffuscene_root_unavailable"
    assert out["scene"] is None


def test_interpreter_unavailable_fails_closed(scratch_root):
    root = scratch_root / "fake_root"
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts" / "infer.py").write_text("", encoding="utf-8")

    producer = _producer(diffuscene_root=root)

    out = producer._invoke_external({})

    assert out["status"] == STATE_BLOCKED
    assert out["blockers"][0]["code"] == "diffuscene_interpreter_unavailable"


def test_entry_point_unavailable_fails_closed(scratch_root):
    root = scratch_root / "fake_root2"
    (root / ".venv" / "Scripts").mkdir(parents=True, exist_ok=True)
    (root / ".venv" / "Scripts" / "python.exe").write_text("", encoding="utf-8")

    producer = _producer(diffuscene_root=root)

    out = producer._invoke_external({})

    assert out["status"] == STATE_BLOCKED
    assert out["blockers"][0]["code"] == "diffuscene_entry_point_unavailable"


def test_unsupported_room_input_fails_closed():
    producer = _producer(
        runner=lambda request: pytest.fail("runner must not be reached")
    )

    payload = producer.execute({"diffuscene_room": {"shape": [128, 128]}})

    assert payload["status"]["state"] == STATE_BLOCKED
    assert payload["blockers"][0]["code"] == "diffuscene_room_input_unsupported"
    assert payload["semantics"]["invoked"] is False


def test_supported_64_room_input_is_accepted():
    producer = _producer(runner=_runner_returning(_native_scene()))

    payload = producer.execute({"diffuscene_room": {"shape": [1, 1, 64, 64]}})

    assert payload["status"]["state"] == STATE_PRODUCED


def test_runner_exception_fails_closed():
    def boom(request):
        raise RuntimeError("gpu exploded")

    producer = _producer(runner=boom)

    payload = producer.execute({})

    assert payload["status"]["state"] == STATE_BLOCKED
    assert payload["blockers"][0]["code"] == "diffuscene_runner_failed"


def test_non_mapping_runner_result_fails_closed():
    producer = _producer(runner=lambda request: "not a mapping")

    payload = producer.execute({})

    assert payload["status"]["state"] == STATE_BLOCKED
    assert (
        payload["blockers"][0]["code"]
        == "diffuscene_runner_contract_violation"
    )


def test_missing_output_file_fails_closed(scratch_root, monkeypatch):
    """A successful subprocess with no written scene is a failure."""

    root = scratch_root / "fake_root3"
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / ".venv" / "Scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts" / DEFAULT_SCRIPT.name).write_text(
        "import sys; sys.exit(0)", encoding="utf-8"
    )

    interpreter = root / DEFAULT_INTERPRETER
    interpreter.write_text("", encoding="utf-8")

    real_run = subprocess.run

    def fake_run(*args, **kwargs):
        class Done:
            returncode = 0
            stdout = ""
            stderr = ""

        return Done()

    monkeypatch.setattr(subprocess, "run", fake_run)

    producer = _producer(diffuscene_root=root)

    out = producer._invoke_external({})

    assert out["status"] == STATE_BLOCKED
    assert out["blockers"][0]["code"] == "diffuscene_output_missing"
    assert out["invoked"] is True


def test_fail_closed_does_not_raise_from_the_pipeline():
    from core.pipeline.master_architect_pipeline import MasterArchitectPipeline

    pipeline = MasterArchitectPipeline(
        {STAGE_NAME: _producer(diffuscene_root=Path("Z:/definitely/missing"))}
    )
    # Keep the producer as the only stage.
    pipeline.pipeline_order = [STAGE_NAME]

    result = pipeline.run({"project": "blocked"})

    row = next(
        r for r in result["pipeline_report"] if r["stage"] == STAGE_NAME
    )
    assert row["status"] == "success"
    assert result[STAGE_NAME]["status"]["state"] == STATE_BLOCKED


def test_no_fixture_is_loaded_by_the_producer():
    producer = _producer()

    assert producer.runner is None
    assert producer._diffuscene_root is None


def test_semantics_declare_no_reimplementation():
    producer = _producer(runner=_runner_returning(_native_scene()))

    semantics = producer.execute({})["semantics"]

    assert semantics["external_runtime_reused"] is True
    assert semantics["inference_reimplemented_here"] is False
    assert semantics["model_weights_modified"] is False
    assert semantics["fixture_loaded"] is False
    assert semantics["scene_schema_introduced"] is False
    assert semantics["downstream_conventions_touched"] == []


# ---------------------------------------------------------------------------
# REAL INTEGRATION PROOF — uses the DEFAULT runner, never a mock.
# ---------------------------------------------------------------------------


def _real_environment_available():
    root = DEFAULT_DIFFUSCENE_ROOT
    if not root.is_dir():
        return False
    if not (root / DEFAULT_INTERPRETER).is_file():
        return False
    if not (root / DEFAULT_SCRIPT).is_file():
        return False
    if not (
        root
        / "pretrained_diffusion"
        / "bedrooms_uncond"
        / "model_30000"
    ).is_file():
        return False

    return True


REAL_ENV_AVAILABLE = _real_environment_available()

real_env_required = pytest.mark.skipif(
    not REAL_ENV_AVAILABLE,
    reason="external DiffuScene environment not available",
)


@real_env_required
def test_real_diffuscene_inference_produces_a_scene(tmp_path_factory):
    """THE integration proof: real external runtime, real model, real scene.

    Deliberately NOT mocked. If the external environment were unavailable this
    test is SKIPPED, never replaced by a fixture.
    """

    producer = _producer()  # default runner == real external invocation

    assert producer.runner is None

    payload = producer.execute({})

    assert payload["status"]["state"] == STATE_PRODUCED, (
        f"real inference failed: {payload['blockers']}"
    )
    assert payload["semantics"]["invoked"] is True
    assert payload["semantics"]["fixture_loaded"] is False
    assert payload["counts"]["scene_items"] > 0

    scene = payload["scene"]
    assert isinstance(scene, list)

    # A real item must carry the native contract the adapter consumes.
    first = scene[0]
    for key in (
        "slot",
        "class_name",
        "center_xyz",
        "full_dims_xyz",
        "angle_rad",
        "objfeat",
    ):
        assert key in first, f"real scene item missing {key}"

    assert len(first["center_xyz"]) == 3
    assert len(first["full_dims_xyz"]) == 3


@real_env_required
def test_real_scene_is_consumed_by_the_existing_furniture_stage():
    """End-to-end: producer -> state -> CONNECT-02 furniture stage."""

    from core.pipeline.adapters.furniture_adapter import FurnitureStageAdapter
    from core.pipeline.adapters.furniture_adapter import FurnitureAdapter

    runtime_scene = {}
    original = FurnitureAdapter.match_3d_future

    def spy(self, contract, registry):
        runtime_scene["items"] = len(contract["furniture"])
        runtime_scene["first_category"] = contract["furniture"][0]["category"]
        return original(self, contract, registry)

    FurnitureAdapter.match_3d_future = spy
    try:
        producer = _producer()
        state = {}
        producer_payload = producer.execute(state)

        assert producer_payload["status"]["state"] == STATE_PRODUCED
        assert state[SCENE_STATE_KEY]

        # Now run the EXISTING CONNECT-02 consumer over that exact state.
        from core.runtime.architectos_runtime import ArchitectOSRuntime

        runtime = ArchitectOSRuntime()
        furniture_payload = runtime.engines["furniture"].execute(state)

        assert furniture_payload["semantics"]["invoked"] is True
        assert furniture_payload["counts"]["source_items"] == len(
            state[SCENE_STATE_KEY]
        )
        assert runtime_scene["items"] == len(state[SCENE_STATE_KEY])
        assert furniture_payload["counts"]["matched_to_3d_future"] > 0
    finally:
        FurnitureAdapter.match_3d_future = original


@real_env_required
def test_real_production_pipeline_runs_producer_then_furniture():
    """The full product path, with the real external runtime in the middle."""

    from core.runtime.architectos_runtime import ArchitectOSRuntime

    runtime = ArchitectOSRuntime()
    result = runtime.run({"project": "connect03-proof", "request": "villa"})

    stages = [row["stage"] for row in result["pipeline_report"]]

    assert STAGE_NAME in stages
    assert "furniture" in stages
    assert stages.index(STAGE_NAME) < stages.index("furniture")

    producer_payload = result[STAGE_NAME]
    assert producer_payload["status"]["state"] == STATE_PRODUCED
    assert producer_payload["state_key_written"] is True

    # The scene the producer wrote is the scene in the shared state.
    assert isinstance(result[SCENE_STATE_KEY], list)
    assert len(result[SCENE_STATE_KEY]) == producer_payload["counts"]["scene_items"]

    # CONNECT-02's runtime actually executed over that scene.
    furniture_payload = result["furniture"]
    assert furniture_payload["semantics"]["invoked"] is True
    assert furniture_payload["semantics"]["runtime_reused"] is True
    assert (
        furniture_payload["counts"]["source_items"]
        == len(result[SCENE_STATE_KEY])
    )
    assert furniture_payload["counts"]["matched_to_3d_future"] > 0
