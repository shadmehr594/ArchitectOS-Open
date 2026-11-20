# ==========================================================
# ArchitectOS — V4.3F T2I GPU PROTECTION TESTS
#
# V4.3D protected single-image I2I, dual-image and Kontext by extending the
# lease predicate with `image_asset`. Text-to-image supplies none of the three
# original signals, so it kept loading the same FLUX graph with no lease, no H2
# and no VRAM preflight.
#
# These tests pin the `or engine == "flux"` extension and, equally importantly,
# pin that WAN does NOT inherit it.
#
# NO GPU. NO COMFYUI. NO OLLAMA. The executor is a capture stub.
# ==========================================================

import socket

import pytest

import core.runtime.gpu_handoff_v1 as gh
from core.render.render_runtime import RenderRuntime

GIB = 1024 ** 3

# FINAL_SAMPLER_AUTHORITY_FIX_V1 — refreshed after the independently authorized
# prompt contract change: unspecified floors no longer become one floor and
# ResolvedFacadeKnowledgeV1 evidence metadata is no longer flattened into the
# fallback sampler prompt.  The GPU lease change remains prompt-neutral against
# this accepted semantic baseline.
T2I_PROMPT_SHA256 = (
    "e056288e2ed5c0c8342e02ce7b00611abf662f0fc8f48512adc82de5f0383ab6"
)

T2I_DESIGN = {
    "prompt": "modern villa exterior, south facade",
    "original_prompt": "modern villa exterior, south facade",
    "mode": "text2img",
    "architectural_intent": {
        "building_type": "villa",
        "style": "modern",
        "materials": ["glass"],
        "levels": {"basement": 0, "ground": 1, "above_ground": 2,
                   "mezzanine": 0, "total": 3},
    },
    "compiled_render_prompt": "REFERENCE: r, DELTA: d, PRESERVE: p, QUALITY: q",
    "preservation": {"level": "high_preservation", "denoise": 0.3},
    "edit_conflict_terms": [],
    "seed": 7,
}


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
        self.calls.append(engine)
        if self.raise_exc is not None:
            raise self.raise_exc
        return {"status": "dry_run_capture", "engine": engine}


def _h2(free_bytes=16 * GIB, with_vram=True):
    trace = {
        "status": "unloaded",
        "reason": None,
        "ownership": "exclusive",
        "loaded_before": ["qwen3.8:27b"],
        "unloaded": ["qwen3.8:27b"],
        "failed": [],
        "skipped_in_use": [],
    }
    if with_vram:
        trace["vram_free_before"] = free_bytes
        trace["vram_free_after"] = free_bytes
    return trace


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    target = tmp_path / "gpu_handoff"
    target.mkdir()
    monkeypatch.setenv("ARCHITECTOS_GPU_HANDOFF_DIR", str(target))
    monkeypatch.delenv("ARCHITECTOS_RENDER_MIN_FREE_VRAM_MIB", raising=False)
    return target


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
#   * a unit test reached the live GPU stack, which is exactly what this suite
#     claims never to do.
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
        lambda **kwargs: h2 if h2 is not None else _h2(),
    )
    # V4.3G.2 — the real H1 must never run from a unit test.
    monkeypatch.setattr(gh, "release_comfyui_for_vision", recovery)
    if vram_reader is not None:
        monkeypatch.setattr(gh, "_vram_free", vram_reader)

    lease.recovery = recovery
    lease.network_attempts = _block_network(monkeypatch)
    return lease


def _run(monkeypatch, engine="flux", lease=None, h2=None, vram_reader=None,
         raise_exc=None, design=None):
    lease = _install(monkeypatch, lease=lease, h2=h2, vram_reader=vram_reader)
    runtime = RenderRuntime()
    executor = CapturingExecutor(raise_exc=raise_exc)
    runtime.executor = executor

    result = runtime.render(
        "v43f-t2i",
        dict(design or T2I_DESIGN),
        engine,
        None,
    )

    return runtime, executor, lease, result


# ==========================================================
# 1 / 2 — T2I NOW TAKES THE LEASE AND RUNS H2
# ==========================================================

def test_t2i_acquires_the_lease(isolated, monkeypatch):
    runtime, executor, lease, result = _run(monkeypatch)

    assert lease.acquires == 1
    assert lease.releases == 1
    assert runtime.last_gpu_handoff_render["status"] == "acquired"
    assert executor.calls  # it still reached the executor


def test_t2i_runs_h2_before_dispatch(isolated, monkeypatch):
    calls = []

    monkeypatch.setattr(
        gh, "gpu_render_lease", lambda wait=None: FakeLease(True)
    )
    monkeypatch.setattr(
        gh, "unload_ollama_models_for_render",
        lambda **kwargs: calls.append("h2") or _h2(),
    )

    runtime = RenderRuntime()
    executor = CapturingExecutor()
    runtime.executor = executor

    # Wrap the executor so the ordering is observable.
    original = executor.execute

    def _execute(workflow, engine):
        calls.append("execute")
        return original(workflow, engine)

    executor.execute = _execute

    runtime.render("v43f-t2i", dict(T2I_DESIGN), "flux", None)

    assert calls == ["h2", "execute"]


# ==========================================================
# 3 / 4 / 5 — T2I IS NOW FAIL-CLOSED
# ==========================================================

def test_t2i_blocked_when_lease_held(isolated, monkeypatch):
    runtime, executor, lease, result = _run(
        monkeypatch, lease=FakeLease(ok=False)
    )

    assert result["status"] == "gpu_handoff_blocked"
    assert result["reason"] == "render_lease_unavailable"
    assert executor.calls == []
    assert lease.releases == 0


def test_t2i_blocked_on_insufficient_vram(isolated, monkeypatch):
    """T2I blocks on insufficient VRAM when recovery cannot reclaim memory.

    V4.3G.2 — recovery is stubbed as unavailable, so this pins the PREFLIGHT
    gate alone. It does NOT claim that every insufficient measurement must
    block: a successful authorized release is a legitimate way past this gate
    and is covered by the V4.3G.1 suite.
    """

    runtime, executor, lease, result = _run(
        monkeypatch, h2=_h2(free_bytes=int(2.23 * GIB))
    )

    assert result["status"] == "gpu_handoff_blocked"
    assert result["reason"] == "insufficient_vram"

    # Recovery was attempted, was stubbed, and reclaimed nothing.
    assert lease.recovery.calls == 1
    assert lease.recovery.status == "blocked"
    assert lease.recovery.reason == TEST_RECOVERY_REASON

    # No submission, lease released, and not one real socket connection.
    assert executor.calls == []
    assert lease.releases == 1
    assert lease.network_attempts == []


def test_t2i_blocked_when_vram_unmeasured(isolated, monkeypatch):
    runtime, executor, lease, result = _run(
        monkeypatch,
        h2=_h2(with_vram=False),
        vram_reader=lambda *a, **k: None,
    )

    assert result["status"] == "gpu_handoff_blocked"
    assert result["reason"] == "vram_unmeasured"
    assert executor.calls == []
    assert lease.releases == 1


# ==========================================================
# 6 — T2I RELEASES ON EXCEPTION
# ==========================================================

def test_t2i_releases_on_executor_exception(isolated, monkeypatch):
    lease = FakeLease(True)
    _install(monkeypatch, lease=lease)

    runtime = RenderRuntime()
    executor = CapturingExecutor(raise_exc=RuntimeError("simulated executor failure"))
    runtime.executor = executor

    with pytest.raises(RuntimeError):
        runtime.render("v43f-t2i", dict(T2I_DESIGN), "flux", None)

    assert lease.acquires == 1
    assert lease.releases == 1
    assert lease.held is False


# ==========================================================
# 7 — WAN MUST NOT INHERIT THE FLUX LEASE OR THRESHOLD
# ==========================================================

def test_wan_takes_no_flux_lease(isolated, monkeypatch):
    wan_design = dict(T2I_DESIGN)
    wan_design["mode"] = "i2v"

    runtime, executor, lease, result = _run(
        monkeypatch, engine="wan", design=wan_design
    )

    assert lease.acquires == 0
    assert lease.releases == 0


def test_wan_does_not_consult_the_vram_gate(isolated, monkeypatch):
    consulted = []

    def _vram(*a, **k):
        consulted.append(1)
        return None

    wan_design = dict(T2I_DESIGN)
    wan_design["mode"] = "i2v"

    _run(monkeypatch, engine="wan", design=wan_design, vram_reader=_vram)

    assert consulted == []


# ==========================================================
# 9 — THE PROMPT IS UNCHANGED BY THE LEASE EXTENSION
# ==========================================================

def test_t2i_prompt_is_unaffected_by_the_lease(isolated, monkeypatch):
    """The lease gates dispatch; it must not touch prompt composition."""

    runtime_a, _, _, _ = _run(monkeypatch)

    # Same request with the lease unavailable: the prompt the runtime resolved
    # before refusing must be identical, because nothing about the gate feeds
    # the prompt builder.
    runtime_b, _, _, blocked = _run(monkeypatch, lease=FakeLease(ok=False))

    assert blocked["status"] == "gpu_handoff_blocked"

    prompt_a = (runtime_a.last_render_request or {}).get("resolved_prompt")
    prompt_b = (runtime_b.last_render_request or {}).get("resolved_prompt")

    assert prompt_a is not None
    assert prompt_a == prompt_b


def test_t2i_prompt_matches_the_sampler_authority_baseline(isolated, monkeypatch):
    """GPU handoff leaves the accepted sampler-authority prompt unchanged."""

    import hashlib

    runtime, _, _, _ = _run(monkeypatch)

    prompt = (runtime.last_render_request or {}).get("resolved_prompt") or ""
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    assert digest == T2I_PROMPT_SHA256
    assert "single floor building" not in prompt.lower()
    assert "french classical" not in prompt.lower()
    assert "beaux arts" not in prompt.lower()
