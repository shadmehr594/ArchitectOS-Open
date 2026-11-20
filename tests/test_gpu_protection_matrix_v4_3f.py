# ==========================================================
# ArchitectOS — V4.3F COMBINED GPU PROTECTION MATRIX
#
# Every protected FLUX path must behave consistently: same lease, same H2,
# same VRAM preflight, same timeout treatment, same cleanup, same status.
# WAN must stay outside all of it.
#
# NO GPU. NO COMFYUI. NO OLLAMA. Executors are stubs.
# ==========================================================

import pytest

import core.runtime.gpu_handoff_v1 as gh
from core.render.render_runtime import RenderRuntime

GIB = 1024 ** 3

BASE_IMAGE = "runs/architectos_product_integration_v3/p3a_transfer_output.png"


class FakeLease:
    def __init__(self, ok=True):
        self.ok = ok
        self.held = False
        self.acquires = 0
        self.releases = 0

    def acquire(self):
        self.acquires += 1
        self.held = self.ok
        return self.ok

    def release(self):
        self.releases += 1
        self.held = False


class CapturingExecutor:
    def __init__(self, status="dry_run_capture", prompt_id="matrix-prompt"):
        self.calls = []
        self.status = status
        self.prompt_id = prompt_id

    def execute(self, injected_workflow, engine):
        self.calls.append(engine)
        return {
            "status": self.status,
            "prompt_id": self.prompt_id,
            "engine": engine,
        }


class ActiveQueue:
    """A ComfyUI queue that keeps reporting `prompt_id` as running."""

    def __init__(self, prompt_id):
        self.prompt_id = prompt_id
        self.running = True
        self.reads = 0

    def queue_state(self):
        self.reads += 1
        return {
            "ok": True,
            "running": [self.prompt_id] if self.running else [],
            "pending": [],
            "reason": None,
        }


class TimeoutExecutor(CapturingExecutor):
    """Simulates the corrected timeout classification from wait_for_result()."""

    def __init__(self, comfy, prompt_id="matrix-prompt"):
        super().__init__("timeout_unconfirmed", prompt_id)
        self.comfy = comfy


def _design(mode):
    return {
        "prompt": "same tower, night",
        "original_prompt": "same tower, night",
        "mode": mode,
        "architectural_intent": {
            "building_type": "tower",
            "style": "modern",
            "materials": [],
            "levels": {"basement": 0, "ground": 1, "above_ground": 5,
                       "mezzanine": 0, "total": 5},
        },
        "compiled_render_prompt": "REFERENCE: r, DELTA: d, PRESERVE: p, QUALITY: q",
        "preservation": {"level": "high_preservation", "denoise": 0.3},
        "edit_conflict_terms": [],
        "seed": 7,
    }


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    target = tmp_path / "gpu_handoff"
    target.mkdir()
    monkeypatch.setenv("ARCHITECTOS_GPU_HANDOFF_DIR", str(target))
    monkeypatch.delenv("ARCHITECTOS_RENDER_MIN_FREE_VRAM_MIB", raising=False)
    return target


def _install(monkeypatch, lease=None, real_lease=False):
    h2_calls = []

    def _h2(**kwargs):
        h2_calls.append(1)
        return {
            "status": "unloaded", "reason": None, "ownership": "exclusive",
            "loaded_before": [], "unloaded": [], "failed": [],
            "skipped_in_use": [],
            "vram_free_before": 16 * GIB, "vram_free_after": 16 * GIB,
        }

    if not real_lease:
        lease = lease if lease is not None else FakeLease(True)
        monkeypatch.setattr(gh, "gpu_render_lease", lambda wait=None: lease)

    monkeypatch.setattr(gh, "unload_ollama_models_for_render", _h2)
    return lease, h2_calls


PATHS = [
    # id,              engine, mode,      image_asset, bindings, conditioned, kontext, lease
    ("single_image_i2i", "flux", "img2img", True, False, False, False, 1),
    ("dual_image_i2i", "flux", "img2img", True, True, False, False, 1),
    ("conditioned_i2i", "flux", "img2img", True, True, True, False, 1),
    ("kontext", "flux", "img2img", True, False, False, True, 1),
    ("flux_t2i", "flux", "text2img", False, False, False, False, 1),
    ("wan_i2v", "wan", "i2v", False, False, False, False, 0),
]


@pytest.mark.parametrize(
    "name,engine,mode,has_asset,bindings,conditioned,kontext,expect_lease",
    PATHS,
)
def test_paths_share_one_protection_contract(
    isolated, monkeypatch, name, engine, mode,
    has_asset, bindings, conditioned, kontext, expect_lease,
):
    if conditioned:
        import core.render.dual_image_conditioning_v1 as cond
        monkeypatch.setattr(
            cond, "verify_conditioning_models",
            lambda: {"status": "ready", "reason": None},
        )

    lease, h2_calls = _install(monkeypatch)

    runtime = RenderRuntime()
    executor = CapturingExecutor()
    runtime.executor = executor

    kwargs = {"conditioned": conditioned, "kontext_edit": kontext}
    if bindings:
        kwargs["image_bindings"] = {
            "A": {"path": BASE_IMAGE}, "B": {"path": BASE_IMAGE}
        }

    runtime.render(
        "v43f-matrix",
        _design(mode),
        engine,
        {"path": BASE_IMAGE, "filename": "base.png"} if has_asset else None,
        **kwargs
    )

    assert lease.acquires == expect_lease, name
    assert lease.releases == expect_lease, name
    assert len(h2_calls) == expect_lease, name
    assert executor.calls, name

    if expect_lease:
        assert runtime.last_gpu_handoff_render["status"] == "acquired", name
        assert runtime.last_gpu_handoff_render["vram"]["ok"] is True, name
    else:
        assert runtime.last_gpu_handoff_render is None, name


PROTECTED_PATHS = [p for p in PATHS if p[7] == 1]


@pytest.mark.parametrize(
    "name,engine,mode,has_asset,bindings,conditioned,kontext,expect_lease",
    PROTECTED_PATHS,
)
def test_timeout_treatment_is_consistent_across_protected_paths(
    isolated, monkeypatch, name, engine, mode,
    has_asset, bindings, conditioned, kontext, expect_lease,
):
    """An unconfirmed timeout must orphan the lease on every protected path."""

    if conditioned:
        import core.render.dual_image_conditioning_v1 as cond
        monkeypatch.setattr(
            cond, "verify_conditioning_models",
            lambda: {"status": "ready", "reason": None},
        )

    lease, _ = _install(monkeypatch)

    queue = ActiveQueue("matrix-prompt")
    runtime = RenderRuntime()
    runtime.executor = TimeoutExecutor(queue)

    kwargs = {"conditioned": conditioned, "kontext_edit": kontext}
    if bindings:
        kwargs["image_bindings"] = {
            "A": {"path": BASE_IMAGE}, "B": {"path": BASE_IMAGE}
        }

    result = runtime.render(
        "v43f-timeout",
        _design(mode),
        engine,
        {"path": BASE_IMAGE, "filename": "base.png"} if has_asset else None,
        **kwargs
    )

    assert result["status"] == "gpu_handoff_orphaned", name
    assert result["reason"] == "job_state_unconfirmed", name
    assert result["prompt_id"] == "matrix-prompt", name
    assert lease.acquires == 1, name
    assert lease.releases == 0, name          # retained, not released
    assert lease.held is True, name
    assert runtime._orphaned_render_guard is not None, name


@pytest.mark.parametrize(
    "name,engine,mode,has_asset,bindings,conditioned,kontext,expect_lease",
    PROTECTED_PATHS,
)
def test_orphaned_path_blocks_ollama(
    isolated, monkeypatch, name, engine, mode,
    has_asset, bindings, conditioned, kontext, expect_lease,
):
    if conditioned:
        import core.render.dual_image_conditioning_v1 as cond
        monkeypatch.setattr(
            cond, "verify_conditioning_models",
            lambda: {"status": "ready", "reason": None},
        )

    _install(monkeypatch, real_lease=True)

    queue = ActiveQueue("matrix-prompt")
    runtime = RenderRuntime()
    runtime.executor = TimeoutExecutor(queue)

    kwargs = {"conditioned": conditioned, "kontext_edit": kontext}
    if bindings:
        kwargs["image_bindings"] = {
            "A": {"path": BASE_IMAGE}, "B": {"path": BASE_IMAGE}
        }

    runtime.render(
        "v43f-ollama",
        _design(mode),
        engine,
        {"path": BASE_IMAGE, "filename": "base.png"} if has_asset else None,
        **kwargs
    )

    with pytest.raises(gh.OllamaModelBusy):
        with gh.ollama_model_call("qwen3.8:27b", wait=0):
            pass


def test_wan_timeout_does_not_create_an_orphan(isolated, monkeypatch):
    """WAN never takes the FLUX lease, so it can never orphan it."""

    lease, _ = _install(monkeypatch)

    runtime = RenderRuntime()
    runtime.executor = TimeoutExecutor(ActiveQueue("matrix-prompt"))

    result = runtime.render("v43f-wan", _design("i2v"), "wan", None)

    assert lease.acquires == 0
    assert runtime._orphaned_render_guard is None
    assert result.get("status") != "gpu_handoff_orphaned"
