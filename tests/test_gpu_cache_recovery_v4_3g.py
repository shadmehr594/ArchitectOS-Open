# ==========================================================
# ArchitectOS — V4.3G GPU CACHE RECOVERY REGRESSION TESTS
#
# The VRAM preflight measures FREE memory only. A completed render can leave a
# large reclaimable ComfyUI model cache resident, which then blocks the next
# render even though nothing is executing.
#
# V4.3G adds ONE controlled recovery attempt at that branch, reusing the
# existing H1 release, and then RE-APPLIES the original gate.
#
# These tests pin: when recovery is attempted, when it is forbidden, and that
# it can never lower the bar.
#
# NO GPU. NO COMFYUI. NO REAL /free. Deterministic stubs, isolated locks.
# ==========================================================

import pytest

import core.runtime.gpu_handoff_v1 as gh
from core.render.render_runtime import RenderRuntime

GIB = 1024 ** 3
BASE_IMAGE = "runs/architectos_product_integration_v3/p3a_transfer_output.png"


# ----------------------------------------------------------
# STUBS
# ----------------------------------------------------------

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
    def __init__(self, status="dry_run_capture"):
        self.calls = []
        self.status = status

    def execute(self, injected_workflow, engine):
        self.calls.append(engine)
        return {"status": self.status, "engine": engine, "prompt_id": "cache-prompt"}


def _verdict_ok(free_mib=16227.6):
    return {
        "contract": "RenderVramGateV1", "version": "1.0", "ok": True,
        "reason": "ok", "free_mib": free_mib, "min_free_mib": 11264.0,
        "measurement_source": "comfyui_system_stats",
        "measurement_units": "MiB", "raw_bytes": int(free_mib * 1048576),
    }


def _verdict_insufficient(free_mib=4307.2):
    return {
        "contract": "RenderVramGateV1", "version": "1.0", "ok": False,
        "reason": "insufficient_vram", "free_mib": free_mib,
        "min_free_mib": 11264.0,
        "measurement_source": "comfyui_system_stats",
        "measurement_units": "MiB", "raw_bytes": int(free_mib * 1048576),
    }


def _verdict_unmeasured():
    return {
        "contract": "RenderVramGateV1", "version": "1.0", "ok": False,
        "reason": "vram_unmeasured", "free_mib": None, "min_free_mib": 11264.0,
        "measurement_source": None, "measurement_units": "MiB", "raw_bytes": None,
    }


class VramScript:
    """Returns scripted verdicts in order; counts how often it was asked."""

    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.calls = 0

    def __call__(self, h2=None, *args, **kwargs):
        index = min(self.calls, len(self.verdicts) - 1)
        self.calls += 1
        return dict(self.verdicts[index])


class ReleaseStub:
    def __init__(self, result=None, raises=None):
        self.result = result or {"status": "released", "reason": None,
                                 "released_bytes": 11920}
        self.raises = raises
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.raises is not None:
            raise self.raises
        return dict(self.result)


def _h2(**kwargs):
    return {
        "status": "unloaded", "reason": None, "ownership": "exclusive",
        "loaded_before": [], "unloaded": [], "failed": [], "skipped_in_use": [],
        "vram_free_before": 16 * GIB, "vram_free_after": 16 * GIB,
    }


def _design():
    return {
        "prompt": "same tower, night",
        "original_prompt": "same tower, night",
        "mode": "img2img",
        "architectural_intent": {
            "building_type": "tower", "style": "modern", "materials": [],
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
    monkeypatch.setattr(gh, "unload_ollama_models_for_render", _h2)
    return target


def _install(monkeypatch, vram_script, release=None, lease=None):
    monkeypatch.setattr(gh, "require_render_vram", vram_script)
    release = release if release is not None else ReleaseStub()
    monkeypatch.setattr(gh, "release_comfyui_for_vision", release)
    lease = lease if lease is not None else FakeLease(True)
    monkeypatch.setattr(gh, "gpu_render_lease", lambda wait=None: lease)
    return lease, release


def _run(monkeypatch, vram_script, release=None, lease=None):
    lease, release = _install(monkeypatch, vram_script, release, lease)
    runtime = RenderRuntime()
    executor = CapturingExecutor()
    runtime.executor = executor

    result = runtime.render(
        "v43g", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )

    return runtime, executor, lease, release, result


# ==========================================================
# 1 — SUFFICIENT VRAM: NO RECOVERY WORK AT ALL
# ==========================================================

def test_sufficient_vram_does_not_attempt_release(isolated, monkeypatch):
    script = VramScript([_verdict_ok()])
    runtime, executor, lease, release, result = _run(monkeypatch, script)

    assert release.calls == 0
    assert script.calls == 1
    assert lease.acquires == 1 and lease.releases == 1
    assert len(executor.calls) == 1


# ==========================================================
# 2 — INSUFFICIENT + IDLE CACHE: RECOVER, THEN RE-APPLY THE GATE
# ==========================================================

def test_insufficient_vram_with_idle_cache_recovers_then_passes(isolated, monkeypatch):
    script = VramScript([_verdict_insufficient(), _verdict_ok()])
    release = ReleaseStub({"status": "released", "reason": None,
                           "released_bytes": 11920})
    runtime, executor, lease, release, result = _run(
        monkeypatch, script, release=release
    )

    assert release.calls == 1              # exactly one attempt
    assert script.calls == 2               # gate re-applied
    assert len(executor.calls) == 1        # exactly one submission
    assert lease.releases == 1

    trace = runtime.last_gpu_handoff_render
    assert trace["vram_release"]["status"] == "released"
    assert trace["vram"]["ok"] is True


def test_recovery_succeeds_only_if_the_original_threshold_passes(isolated, monkeypatch):
    """The second gate is the SAME gate — a lower free value still blocks."""

    script = VramScript([_verdict_insufficient(4307.2), _verdict_insufficient(11263.9)])
    release = ReleaseStub({"status": "released", "released_bytes": 0})
    runtime, executor, lease, release, result = _run(
        monkeypatch, script, release=release
    )

    assert result["status"] == "gpu_handoff_blocked"
    assert result["reason"] == "insufficient_vram"
    assert executor.calls == []
    assert lease.releases == 1


# ==========================================================
# 3 — RECOVERY REPORTS SUCCESS BUT MEMORY IS UNCHANGED
# ==========================================================

def test_release_success_with_unchanged_memory_blocks(isolated, monkeypatch):
    script = VramScript([_verdict_insufficient(4307.2), _verdict_insufficient(4307.2)])
    release = ReleaseStub({"status": "released", "reason": None, "released_bytes": 0})
    runtime, executor, lease, release, result = _run(
        monkeypatch, script, release=release
    )

    assert release.calls == 1
    assert script.calls == 2
    assert result["status"] == "gpu_handoff_blocked"
    assert executor.calls == []

    trace = runtime.last_gpu_handoff_render
    assert trace["vram_release"]["status"] == "released"
    assert trace["vram_release"]["released_bytes"] == 0
    assert trace["vram"]["free_mib"] == 4307.2


# ==========================================================
# 4 — UNREADABLE VRAM: NO RELEASE WORKAROUND
# ==========================================================

def test_unmeasured_vram_does_not_attempt_release(isolated, monkeypatch):
    script = VramScript([_verdict_unmeasured()])
    runtime, executor, lease, release, result = _run(monkeypatch, script)

    assert release.calls == 0
    assert result["status"] == "gpu_handoff_blocked"
    assert result["reason"] == "vram_unmeasured"
    assert executor.calls == []


def test_insufficient_reason_without_readable_measurement_does_not_release(
    isolated, monkeypatch
):
    """`insufficient_vram` with a missing number is not a measured failure."""

    broken = _verdict_insufficient()
    broken["free_mib"] = None
    broken["raw_bytes"] = None

    script = VramScript([broken])
    runtime, executor, lease, release, result = _run(monkeypatch, script)

    assert release.calls == 0
    assert result["status"] == "gpu_handoff_blocked"
    assert executor.calls == []


# ==========================================================
# 5 / 6 — A BUSY QUEUE FORBIDS RELEASE
# ==========================================================

@pytest.mark.parametrize("busy_reason", [
    "comfy_queue_not_empty",   # running or pending job
    "comfy_queue_unreadable",  # cannot prove the queue is empty
    "comfyui_busy",            # the comfyui lease could not be taken
])
def test_busy_or_unprovable_queue_blocks_without_release(
    isolated, monkeypatch, busy_reason
):
    script = VramScript([_verdict_insufficient()])
    release = ReleaseStub({"status": "blocked", "reason": busy_reason})
    runtime, executor, lease, release, result = _run(
        monkeypatch, script, release=release
    )

    assert release.calls == 1
    assert script.calls == 1          # no second measurement: nothing changed
    assert result["status"] == "gpu_handoff_blocked"
    assert result["reason"] == "insufficient_vram"
    assert executor.calls == []
    assert runtime.last_gpu_handoff_render["vram_release"]["reason"] == busy_reason


# ==========================================================
# 7 — AN UNCONFIRMED PREVIOUS JOB FORBIDS RELEASE
# ==========================================================

def test_orphaned_job_does_not_attempt_release(isolated, monkeypatch):
    script = VramScript([_verdict_insufficient()])
    release = ReleaseStub()
    runtime, executor, lease, release, result = _run(
        monkeypatch, script, release=release
    )

    # Force the orphan state the gate would have set, then ask the helper
    # directly: it must refuse, because the GPU is not provably idle.
    runtime._orphaned_render_guard = FakeLease(True)
    verdict = runtime._reclaim_idle_comfyui_cache(_verdict_insufficient())

    assert verdict["status"] == "skipped"
    assert verdict["reason"] == "orphaned_job_unconfirmed"


def test_second_render_with_active_orphan_never_releases(isolated, monkeypatch):
    from core.render.workflow_executor import WorkflowExecutor

    script = VramScript([_verdict_insufficient()])
    release = ReleaseStub()
    lease, release = _install(monkeypatch, script, release)

    runtime = RenderRuntime()
    runtime.executor = WorkflowExecutor()

    # A parked guard blocks at the orphan gate before the VRAM branch.
    runtime._orphaned_render_guard = FakeLease(True)
    runtime._orphaned_prompt_id = "still-running"
    runtime._orphaned_reason = "timeout_unconfirmed"

    class _ActiveQueue:
        def queue_state(self):
            return {"ok": True, "running": ["still-running"], "pending": [],
                    "reason": None}

    runtime.executor.comfy = _ActiveQueue()

    result = runtime.render(
        "v43g-orphan", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )

    assert result["status"] == "gpu_handoff_orphaned"
    assert release.calls == 0


# ==========================================================
# 8 — AN OCCUPIED RENDER LEASE PREVENTS RECOVERY
# ==========================================================

def test_occupied_lease_prevents_recovery(isolated, monkeypatch):
    script = VramScript([_verdict_insufficient()])
    release = ReleaseStub()
    runtime, executor, lease, release, result = _run(
        monkeypatch, script, release=release, lease=FakeLease(ok=False)
    )

    assert result["status"] == "gpu_handoff_blocked"
    assert result["reason"] == "render_lease_unavailable"
    assert release.calls == 0
    assert script.calls == 0
    assert executor.calls == []


# ==========================================================
# 9 — AN UNEXPECTED H1 FAILURE BLOCKS WITH A REASON
# ==========================================================

def test_release_exception_blocks_with_reason(isolated, monkeypatch):
    script = VramScript([_verdict_insufficient()])
    release = ReleaseStub(raises=RuntimeError("simulated /free transport failure"))
    runtime, executor, lease, release, result = _run(
        monkeypatch, script, release=release
    )

    assert release.calls == 1
    assert script.calls == 1                 # no re-measure: nothing released
    assert result["status"] == "gpu_handoff_blocked"

    trace = runtime.last_gpu_handoff_render["vram_release"]
    assert trace["status"] == "blocked"
    assert trace["reason"].startswith("release_exception:")
    assert executor.calls == []


# ==========================================================
# 10 — NO RETRY LOOPS, NO EXTRA SUBMISSIONS
# ==========================================================

def test_recovery_is_attempted_at_most_once(isolated, monkeypatch):
    script = VramScript([_verdict_insufficient(), _verdict_insufficient()])
    release = ReleaseStub({"status": "released", "released_bytes": 0})
    runtime, executor, lease, release, result = _run(
        monkeypatch, script, release=release
    )

    assert release.calls == 1        # one attempt, never a loop
    assert script.calls == 2         # initial + one re-measure
    assert executor.calls == []      # nothing submitted


def test_successful_recovery_submits_exactly_one_job(isolated, monkeypatch):
    script = VramScript([_verdict_insufficient(), _verdict_ok()])
    runtime, executor, lease, release, result = _run(monkeypatch, script)

    assert len(executor.calls) == 1
    assert lease.acquires == 1
    assert lease.releases == 1


# ==========================================================
# V4.3G.1 — POST-RELEASE MEASUREMENT FRESHNESS
#
# The tests above replace `require_render_vram` with `VramScript`. That pins
# call SEQUENCING but cannot see which measurement the gate actually consumed,
# which is precisely why the stale post-release re-measurement survived V4.3G:
# the re-gate was re-passing H2's pre-release snapshot and nothing noticed.
#
# The tests below use the REAL `require_render_vram()` and script only
# `gh._vram_free`, the single measurement primitive. The real precedence,
# threshold and fail-closed branches all execute.
#
# NO GPU. NO COMFYUI. NO REAL /free. NO RENDER.
# ==========================================================

MIB = 1024 * 1024


class FreshMeasure:
    """Stands in for gh._vram_free(session, endpoint, timeout) -> bytes|None."""

    def __init__(self, values):
        self.values = list(values)
        self.calls = 0

    def __call__(self, session=None, endpoint=None, timeout=None):
        index = min(self.calls, len(self.values) - 1)
        self.calls += 1
        value = self.values[index]
        return None if value is None else int(value * MIB)


def _h2_with(free_mib):
    """H2 trace whose snapshot reports `free_mib` (None = unreadable)."""

    trace = _h2()
    trace["vram_free_after"] = None if free_mib is None else int(free_mib * MIB)
    trace["vram_free_before"] = trace["vram_free_after"]
    return trace


def _run_real_gate(monkeypatch, h2_trace, release_trace, fresh_values, lease=None):
    """Render with the REAL gate; only the measurement primitive is scripted."""

    monkeypatch.setattr(
        gh, "unload_ollama_models_for_render", lambda *a, **k: dict(h2_trace)
    )
    monkeypatch.setattr(
        gh, "release_comfyui_for_vision", lambda *a, **k: dict(release_trace)
    )
    lease = lease if lease is not None else FakeLease(True)
    monkeypatch.setattr(gh, "gpu_render_lease", lambda wait=None: lease)

    measure = FreshMeasure(fresh_values)
    monkeypatch.setattr(gh, "_vram_free", measure)

    runtime = RenderRuntime()
    runtime.executor = CapturingExecutor()
    result = runtime.render(
        "v43g1", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )
    return runtime, runtime.executor, lease, measure, result


_RELEASED = {"status": "released", "reason": None, "release_confirmed": True,
             "released_bytes": int((16227.6 - 4307.2) * MIB)}


# ----------------------------------------------------------
# 1 — STALE SNAPSHOT INSUFFICIENT, RELEASE HELPS, FRESH IS SUFFICIENT
# ----------------------------------------------------------

def test_post_release_measurement_is_fresh_and_admits_render(isolated, monkeypatch):
    """The defect: re-passing `_h2` re-applied the pre-release 4307.2 MiB."""

    runtime, executor, lease, measure, result = _run_real_gate(
        monkeypatch,
        _h2_with(4307.2),          # H2 snapshot, taken BEFORE the release
        _RELEASED,                 # H1 released ComfyUI's idle cache
        [16227.6],                 # fresh /system_stats after the release
    )

    trace = runtime.last_gpu_handoff_render
    assert result.get("status") != "gpu_handoff_blocked"
    assert len(executor.calls) == 1

    assert trace["vram_release"]["status"] == "released"
    assert trace["vram"]["ok"] is True
    assert trace["vram"]["free_mib"] == 16227.6
    assert measure.calls == 1


# ----------------------------------------------------------
# 2 — RELEASE REPORTS SUCCESS BUT MEMORY IS STILL INSUFFICIENT
# ----------------------------------------------------------

def test_post_release_measurement_still_insufficient_blocks(isolated, monkeypatch):
    runtime, executor, lease, measure, result = _run_real_gate(
        monkeypatch,
        _h2_with(4307.2),
        _RELEASED,
        [4307.2],                  # fresh measurement: nothing was actually freed
    )

    assert result["status"] == "gpu_handoff_blocked"
    assert result["reason"] == "insufficient_vram"
    assert executor.calls == []
    assert measure.calls == 1

    trace = runtime.last_gpu_handoff_render
    assert trace["vram"]["free_mib"] == 4307.2
    assert trace["vram"]["ok"] is False


def test_release_success_at_the_threshold_boundary_still_blocks(isolated, monkeypatch):
    """11 263.9 MiB must still block — the floor is not lowered by recovery."""

    runtime, executor, lease, measure, result = _run_real_gate(
        monkeypatch,
        _h2_with(4307.2),
        _RELEASED,
        [11263.9],
    )

    assert result["status"] == "gpu_handoff_blocked"
    assert result["reason"] == "insufficient_vram"
    assert runtime.last_gpu_handoff_render["vram"]["free_mib"] == 11263.9
    assert executor.calls == []


# ----------------------------------------------------------
# 3 — FRESH MEASUREMENT UNAVAILABLE: FAIL CLOSED
# ----------------------------------------------------------

def test_unavailable_post_release_measurement_blocks(isolated, monkeypatch):
    """An unreadable card after a release is unknown, not empty."""

    runtime, executor, lease, measure, result = _run_real_gate(
        monkeypatch,
        _h2_with(4307.2),
        _RELEASED,
        [None],                    # /system_stats unreadable
    )

    assert result["status"] == "gpu_handoff_blocked"
    assert result["reason"] == "vram_unmeasured"
    assert executor.calls == []
    assert measure.calls == 1
    assert runtime.last_gpu_handoff_render["vram"]["free_mib"] is None


# ----------------------------------------------------------
# 4 — BUSY QUEUE / ORPHAN PROTECTIONS UNCHANGED
# ----------------------------------------------------------

def test_busy_queue_blocks_without_any_fresh_read(isolated, monkeypatch):
    runtime, executor, lease, measure, result = _run_real_gate(
        monkeypatch,
        _h2_with(4307.2),
        {"status": "blocked", "reason": "comfy_queue_not_empty"},
        [16227.6],                 # must never be consulted
    )

    assert result["status"] == "gpu_handoff_blocked"
    assert result["reason"] == "insufficient_vram"
    assert measure.calls == 0
    assert executor.calls == []
    assert (runtime.last_gpu_handoff_render["vram_release"]["reason"]
            == "comfy_queue_not_empty")


def test_orphan_guard_blocks_before_any_release_or_fresh_read(isolated, monkeypatch):
    from core.render.workflow_executor import WorkflowExecutor

    runtime, executor, lease, measure, result = _run_real_gate(
        monkeypatch,
        _h2_with(4307.2),
        _RELEASED,
        [16227.6],
    )

    # A parked guard must stop the render at the orphan gate, before VRAM work.
    runtime2 = RenderRuntime()
    runtime2.executor = WorkflowExecutor()
    runtime2._orphaned_render_guard = FakeLease(True)
    runtime2._orphaned_prompt_id = "still-running"
    runtime2._orphaned_reason = "timeout_unconfirmed"

    class _ActiveQueue:
        def queue_state(self):
            return {"ok": True, "running": ["still-running"], "pending": [],
                    "reason": None}

    runtime2.executor.comfy = _ActiveQueue()

    result2 = runtime2.render(
        "v43g1-orphan", _design(), "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )

    assert result2["status"] == "gpu_handoff_orphaned"
    assert measure.calls == 1     # only the first render's gate measured


# ----------------------------------------------------------
# 5 — THE FIRST H2 MEASUREMENT KEEPS ITS ACCEPTED SEMANTICS
# ----------------------------------------------------------

def test_first_gate_still_uses_the_h2_snapshot(isolated, monkeypatch):
    """H2 measures under the lease immediately before dispatch. No live read."""

    runtime, executor, lease, measure, result = _run_real_gate(
        monkeypatch,
        _h2_with(16227.6),         # sufficient
        _RELEASED,                 # must never be called
        [4307.2],                  # would be insufficient if consulted
    )

    assert result.get("status") != "gpu_handoff_blocked"
    assert measure.calls == 0
    assert len(executor.calls) == 1

    trace = runtime.last_gpu_handoff_render
    assert trace["vram"]["measurement_source"] == "h2.vram_free_after"
    assert "vram_release" not in trace


# ----------------------------------------------------------
# 6 — NO EXTRA SUBMISSION, NO RETRY, NO SECOND RELEASE
# ----------------------------------------------------------

def test_recovery_submits_once_and_never_retries(isolated, monkeypatch):
    runtime, executor, lease, measure, result = _run_real_gate(
        monkeypatch,
        _h2_with(4307.2),
        _RELEASED,
        [16227.6, 16227.6],
    )

    assert len(executor.calls) == 1
    assert measure.calls == 1      # exactly one post-release read, no loop
    assert lease.acquires == 1
    assert lease.releases == 1


# ----------------------------------------------------------
# 7 — THE POST-RELEASE SOURCE IS REPORTED AS FRESH
# ----------------------------------------------------------

def test_post_release_source_is_reported_as_comfyui_system_stats(
    isolated, monkeypatch
):
    runtime, executor, lease, measure, result = _run_real_gate(
        monkeypatch,
        _h2_with(4307.2),
        _RELEASED,
        [16227.6],
    )

    vram = runtime.last_gpu_handoff_render["vram"]
    assert vram["measurement_source"] == "comfyui_system_stats"
    assert vram["measurement_source"] != "h2.vram_free_after"
    assert vram["raw_bytes"] == int(16227.6 * MIB)
    assert vram["min_free_mib"] == 11264.0


def test_stale_snapshot_can_no_longer_mask_a_successful_release(
    isolated, monkeypatch
):
    """Regression guard: the exact defect. H2 stale < floor < fresh."""

    runtime, executor, lease, measure, result = _run_real_gate(
        monkeypatch,
        _h2_with(4307.2),
        _RELEASED,
        [15962.7],
    )

    vram = runtime.last_gpu_handoff_render["vram"]
    assert vram["free_mib"] == 15962.7
    assert vram["free_mib"] != 4307.2
    assert vram["ok"] is True
    assert len(executor.calls) == 1
