# ==========================================================
# ArchitectOS — V4.3D GPU SAFETY REGRESSION TESTS
#
# Exercises the REAL RenderRuntime.render() guard with simulated leases,
# simulated H2 traces and simulated VRAM telemetry.
#
# NO GPU. NO COMFYUI SUBMISSION. The executor is a capture stub.
#
# Scope note (honest limitation): these tests prove the GUARD — when the
# lease is taken, when H2 runs, when the VRAM gate blocks, and when the lease
# is released. They do NOT prove the real ComfyUI job lifecycle; that is
# established separately by reading WorkflowExecutor.execute(), which calls
# comfy.wait_for_result() and therefore blocks until the sampler produces
# images (see the V4.3D report, §4).
# ==========================================================

import os
import socket

import pytest

import core.runtime.gpu_handoff_v1 as gh
from core.render.render_runtime import RenderRuntime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_IMAGE = os.path.join(
    ROOT, "runs", "architectos_product_integration_v3", "p3a_transfer_output.png"
)

GIB = 1024 ** 3


# ==========================================================
# STUBS
# ==========================================================

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
    def __init__(self, raise_exc=None):
        self.calls = []
        self.raise_exc = raise_exc

    def execute(self, injected_workflow, engine):
        self.calls.append({"engine": engine, "workflow": injected_workflow})
        if self.raise_exc is not None:
            raise self.raise_exc
        return {"status": "dry_run_capture", "engine": engine}


def _h2_ok(free_bytes=16 * GIB):
    return {
        "status": "unloaded",
        "reason": None,
        "ownership": "exclusive",
        "loaded_before": ["qwen3.8:27b"],
        "unloaded": ["qwen3.8:27b"],
        "failed": [],
        "skipped_in_use": [],
        "vram_free_before": free_bytes,
        "vram_free_after": free_bytes,
    }


def _design(**over):
    design = {
        "prompt": "same tower, night",
        "original_prompt": "same tower, night",
        "mode": "img2img",
        "architectural_intent": {
            "building_type": "tower",
            "style": "modern",
            "materials": [],
            "levels": {
                "basement": 0, "ground": 1, "above_ground": 5,
                "mezzanine": 0, "total": 5,
            },
        },
        "compiled_render_prompt": "REFERENCE: r, DELTA: d, PRESERVE: p, QUALITY: q",
        "preservation": {"level": "high_preservation", "denoise": 0.3},
        "edit_conflict_terms": [],
        "seed": 7,
    }
    design.update(over)
    return design


@pytest.fixture
def runtime():
    return RenderRuntime()


# ==========================================================
# V4.3G.2 — TEST ISOLATION
#
# V4.3G added a cache-release attempt on the insufficient-VRAM path. This
# helper stubbed the lease, H2 and the VRAM reader but NOT
# `release_comfyui_for_vision`, so the REAL H1 ran against whatever ComfyUI
# happened to be listening on 127.0.0.1:8188: a real `POST /free` and a real
# `/system_stats` read. Two consequences, both observed:
#
#   * the suite became machine-state dependent - on an idle GPU the release
#     genuinely freed the cache and "insufficient VRAM must block" turned into
#     a successful recovery, so the test failed for the right reason but at
#     the wrong layer;
#   * a unit test reached the live GPU stack, which is exactly what these
#     suites claim never to do.
#
# The release is now ALWAYS replaced by a deterministic stub, and every socket
# connection is blocked so a regression fails loudly instead of quietly
# touching ComfyUI. The default verdict is "recovery unavailable", which is a
# legitimate H1 outcome and keeps the preflight gate itself under test.
# Successful recovery is covered by tests/test_gpu_cache_recovery_v4_3g.py.
# ==========================================================

TEST_RECOVERY_REASON = "test_recovery_unavailable"


class RecoveryStub:
    """Deterministic stand-in for release_comfyui_for_vision(). Never network."""

    def __init__(self, status="blocked", reason=TEST_RECOVERY_REASON):
        self.status = status
        self.reason = reason
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return {
            "contract": "GpuHandoffV1",
            "version": "1.0",
            "stage": "H1",
            "stage_name": "comfyui_release_before_vision",
            "status": self.status,
            "reason": self.reason,
            "release_confirmed": False,
            "released_bytes": None,
            "vram_free_before": None,
            "vram_free_after": None,
        }


def _block_network(monkeypatch):
    """Fail fast on any socket connect; returns the recorded attempts."""

    attempts = []

    def _blocked_connect(self, address, *args, **kwargs):
        attempts.append(address)
        raise AssertionError(
            "real network access attempted during an isolated GPU test: %r"
            % (address,)
        )

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
    return attempts


def _install(monkeypatch, lease=None, h2=None, vram_reader=None, recovery=None):
    lease = lease if lease is not None else FakeLease(True)
    recovery = recovery if recovery is not None else RecoveryStub()
    monkeypatch.setattr(gh, "gpu_render_lease", lambda wait=None: lease)
    monkeypatch.setattr(
        gh, "unload_ollama_models_for_render",
        lambda **kwargs: h2 if h2 is not None else _h2_ok(),
    )
    # V4.3G.2 — the real H1 must never run from a unit test.
    monkeypatch.setattr(gh, "release_comfyui_for_vision", recovery)
    if vram_reader is not None:
        monkeypatch.setattr(gh, "_vram_free", vram_reader)

    lease.recovery = recovery
    lease.network_attempts = _block_network(monkeypatch)
    return lease


# ==========================================================
# 1 / 2 / 13 — WHICH PATHS TAKE THE LEASE
# ==========================================================

def test_single_image_i2i_acquires_the_lease(runtime, monkeypatch):
    lease = _install(monkeypatch)
    executor = CapturingExecutor()
    runtime.executor = executor

    runtime.render(
        "test", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )

    assert lease.acquires == 1
    assert lease.releases == 1
    assert len(executor.calls) == 1
    assert runtime.last_gpu_handoff_render["status"] == "acquired"


def test_dual_image_path_still_protected(runtime, monkeypatch):
    lease = _install(monkeypatch)
    executor = CapturingExecutor()
    runtime.executor = executor

    runtime.render(
        "test", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
        image_bindings={"A": {"path": BASE_IMAGE}, "B": {"path": BASE_IMAGE}},
    )

    assert lease.acquires == 1
    assert lease.releases == 1
    assert len(executor.calls) == 1
    assert runtime.last_gpu_handoff_render["status"] == "acquired"


def test_conditioned_path_still_protected(runtime, monkeypatch):
    """`conditioned` alone is refused before the lease (dual binding is
    mandatory), so a VALID conditioned request must carry bindings too."""

    import core.render.dual_image_conditioning_v1 as cond

    monkeypatch.setattr(
        cond, "verify_conditioning_models",
        lambda: {"status": "ready", "reason": None},
    )

    lease = _install(monkeypatch)
    executor = CapturingExecutor()
    runtime.executor = executor

    runtime.render(
        "test", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
        image_bindings={"A": {"path": BASE_IMAGE}, "B": {"path": BASE_IMAGE}},
        conditioned=True,
    )

    assert lease.acquires == 1
    assert len(executor.calls) == 1


def test_conditioned_without_binding_is_refused_before_the_lease(runtime, monkeypatch):
    lease = _install(monkeypatch)
    executor = CapturingExecutor()
    runtime.executor = executor

    result = runtime.render(
        "test", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
        conditioned=True,
    )

    assert result["status"] == "conditioning_requires_dual_binding"
    assert lease.acquires == 0
    assert executor.calls == []


def test_text_to_image_is_now_protected(runtime, monkeypatch):
    """V4.3D pinned T2I as a residual risk; V4.3F closed it.

    Pure text-to-image supplies neither `image_asset` nor `image_bindings` nor
    `conditioned`, so V4.3D's predicate left it unprotected. V4.3F extended the
    predicate with `engine == "flux"`, which is the discriminator every FLUX
    call site passes and WAN does not. The old assertion (`acquires == 0`) is
    now the defect, so it is inverted rather than deleted.
    """

    lease = _install(monkeypatch)
    executor = CapturingExecutor()
    runtime.executor = executor

    runtime.render("test", _design(mode="text2img"), "flux", None)

    assert lease.acquires == 1
    assert lease.releases == 1
    assert len(executor.calls) == 1
    assert runtime.last_gpu_handoff_render["status"] == "acquired"


def test_kontext_edit_is_covered_by_image_asset(runtime, monkeypatch):
    """Kontext edits go through handle_image_edit and DO supply image_asset."""

    lease = _install(monkeypatch)
    executor = CapturingExecutor()
    runtime.executor = executor

    runtime.render(
        "test", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
        mask_asset={"path": BASE_IMAGE},
        kontext_edit=True,
    )

    assert lease.acquires == 1
    assert len(executor.calls) == 1


# ==========================================================
# 3 / 4 — LEASE AND H2 REFUSALS
# ==========================================================

def test_lease_failure_prevents_submission(runtime, monkeypatch):
    lease = _install(monkeypatch, lease=FakeLease(ok=False))
    executor = CapturingExecutor()
    runtime.executor = executor

    result = runtime.render(
        "test", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )

    assert result["status"] == "gpu_handoff_blocked"
    assert result["reason"] == "render_lease_unavailable"
    assert executor.calls == []
    assert lease.releases == 0  # never acquired, nothing to release


def test_h2_failure_prevents_submission(runtime, monkeypatch):
    blocked = _h2_ok()
    blocked.update({"status": "blocked", "reason": "ollama_model_busy"})
    lease = _install(monkeypatch, h2=blocked)
    executor = CapturingExecutor()
    runtime.executor = executor

    result = runtime.render(
        "test", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )

    assert result["status"] == "gpu_handoff_blocked"
    assert result["reason"].startswith("gpu_handoff_h2_")
    assert executor.calls == []
    assert lease.releases == 1


# ==========================================================
# 5 / 6 / 7 — VRAM GATE
# ==========================================================

def test_insufficient_vram_prevents_submission(runtime, monkeypatch):
    """Insufficient VRAM blocks when cache recovery cannot reclaim memory.

    V4.3G.2 — recovery is stubbed as unavailable, so this pins the PREFLIGHT
    gate alone. It does NOT claim that every insufficient measurement must
    block: a successful authorized release is a legitimate way past this gate
    and is covered by the V4.3G.1 suite. Here the release is unavailable, so
    the original measurement stands and the render must not be submitted.
    """

    lease = _install(monkeypatch, h2=_h2_ok(free_bytes=int(2.23 * GIB)))
    executor = CapturingExecutor()
    runtime.executor = executor

    result = runtime.render(
        "test", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )

    assert result["status"] == "gpu_handoff_blocked"
    assert result["reason"] == "insufficient_vram"

    # The initial measurement was insufficient, and it is the H2 snapshot.
    assert result["vram"]["ok"] is False
    assert result["vram"]["free_mib"] < result["vram"]["min_free_mib"]
    assert result["vram"]["measurement_source"] == "h2.vram_free_after"

    # Recovery was attempted, was stubbed, and reclaimed nothing.
    assert lease.recovery.calls == 1
    assert lease.recovery.status == "blocked"
    assert lease.recovery.reason == TEST_RECOVERY_REASON

    # No submission, lease released, and not one real socket connection.
    assert executor.calls == []
    assert lease.releases == 1
    assert lease.network_attempts == []


def test_unmeasured_vram_prevents_submission(runtime, monkeypatch):
    """Fail closed: an unreadable GPU is not an empty one."""

    h2 = _h2_ok()
    h2["vram_free_after"] = None
    lease = _install(monkeypatch, h2=h2, vram_reader=lambda *a, **k: None)
    executor = CapturingExecutor()
    runtime.executor = executor

    result = runtime.render(
        "test", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )

    assert result["status"] == "gpu_handoff_blocked"
    assert result["reason"] == "vram_unmeasured"
    assert result["vram"]["ok"] is False
    assert executor.calls == []
    assert lease.releases == 1


def test_sufficient_vram_dispatches(runtime, monkeypatch):
    lease = _install(monkeypatch, h2=_h2_ok(free_bytes=15 * GIB))
    executor = CapturingExecutor()
    runtime.executor = executor

    runtime.render(
        "test", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )

    assert len(executor.calls) == 1
    vram = runtime.last_gpu_handoff_render["vram"]
    assert vram["ok"] is True
    assert vram["measurement_source"] == "h2.vram_free_after"
    assert vram["measurement_units"].startswith("MiB")
    assert lease.releases == 1


def test_vram_gate_converts_bytes_to_mib():
    """The V4.3C proposal compared BYTES against 9000 MB — always true.

    This pins the unit conversion so the mistake cannot come back.
    """

    # 15.98 GiB exactly as ComfyUI reports it.
    verdict = gh.require_render_vram({"vram_free_after": 17163091968})

    assert verdict["ok"] is True
    assert 16300 < verdict["free_mib"] < 16400

    low = gh.require_render_vram({"vram_free_after": 2398670848})
    assert low["ok"] is False
    assert low["reason"] == "insufficient_vram"
    assert 2280 < low["free_mib"] < 2300


def test_vram_gate_blocks_when_unmeasurable():
    verdict = gh.require_render_vram(
        {}, endpoint="http://127.0.0.1:1", timeout=0.2
    )

    assert verdict["ok"] is False
    assert verdict["reason"] == "vram_unmeasured"


# ==========================================================
# 8 / 9 / 10 — CLEANUP
# ==========================================================

def test_exception_releases_the_lease(runtime, monkeypatch):
    lease = _install(monkeypatch)
    runtime.executor = CapturingExecutor(raise_exc=RuntimeError("boom"))

    with pytest.raises(RuntimeError):
        runtime.render(
            "test", _design(), "flux",
            {"path": BASE_IMAGE, "filename": "base.png"},
        )

    assert lease.releases == 1
    assert lease.held is False


def test_cancellation_releases_the_lease(runtime, monkeypatch):
    lease = _install(monkeypatch)
    runtime.executor = CapturingExecutor(raise_exc=KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        runtime.render(
            "test", _design(), "flux",
            {"path": BASE_IMAGE, "filename": "base.png"},
        )

    assert lease.releases == 1
    assert lease.held is False


def test_early_return_releases_the_lease(runtime, monkeypatch):
    blocked = _h2_ok()
    blocked.update({"status": "blocked", "reason": "ollama_unload_failed"})
    lease = _install(monkeypatch, h2=blocked)
    runtime.executor = CapturingExecutor()

    runtime.render(
        "test", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )

    assert lease.releases == 1
    assert lease.held is False


# ==========================================================
# 11 / 12 — MUTUAL EXCLUSION WITH OLLAMA (real lock files)
# ==========================================================

@pytest.fixture
def isolated_handoff_dir(tmp_path, monkeypatch):
    """V4.3E — keep the REAL lock semantics, drop the shared namespace.

    `handoff_dir()` resolves `ARCHITECTOS_GPU_HANDOFF_DIR` on every call, so
    redirecting it to a `tmp_path` child leaves `CrossProcessLock` (the real
    `msvcrt`/`fcntl` advisory lock) completely unchanged while removing the
    dependency on whatever the production tree happens to be holding.

    Without this, these two tests fail whenever a legitimate render owns the
    production lease — a false failure that makes the suite unusable as a
    safety gate exactly when the system is busy.
    """

    target = tmp_path / "gpu_handoff"
    target.mkdir()
    monkeypatch.setenv("ARCHITECTOS_GPU_HANDOFF_DIR", str(target))
    return target


def test_ollama_cannot_take_the_gpu_while_a_render_holds_it(isolated_handoff_dir):
    lease = gh.gpu_render_lease(wait=0)

    # The isolation must be real, not assumed.
    assert gh.gpu_render_lock_path().startswith(str(isolated_handoff_dir))

    assert lease.acquire() is True

    try:
        with pytest.raises(gh.OllamaModelBusy):
            with gh.ollama_model_call("qwen3.8:27b", wait=0):
                pass
    finally:
        lease.release()


def test_lease_is_reacquirable_after_release(isolated_handoff_dir):
    assert gh.gpu_render_lock_path().startswith(str(isolated_handoff_dir))

    first = gh.gpu_render_lease(wait=0)
    assert first.acquire() is True
    first.release()

    second = gh.gpu_render_lease(wait=0)
    assert second.acquire() is True
    second.release()
