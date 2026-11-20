# ==========================================================
# ArchitectOS FACADE-04D.3C-5B — SAFE VISION-TO-RENDER GPU MEMORY HANDOFF
#
# One AMD Radeon RX 6900 XT (~16 GiB). The Ollama vision model and the
# FLUX/ComfyUI render stack cannot be resident at the same time. The GPU must
# therefore be used SEQUENTIALLY:
#
#     H1  safe ComfyUI cache release   (before the A/B architectural vision)
#     ->  vision A + vision B          (Ollama qwen3.8:27b)
#     H2  safe Ollama model release    (after the last dependent inference,
#                                       before the ComfyUI render submit)
#     ->  ComfyUI render
#
# WHY A CROSS-PROCESS LEASE IS REQUIRED
# -------------------------------------
# The Core API (app.py) is a threaded Flask app, the UI is a second process,
# and acceptance/teaching runners are further processes. An in-process mutex
# therefore proves nothing about the OTHER processes that can use the same
# Ollama model. `msvcrt.locking` / `fcntl.flock` on a shared lock file gives
# ONE primitive that is exclusive BOTH across threads of one process AND
# across processes (verified empirically on this machine: a second handle in
# the same process and a handle in a child process are both refused).
#
# Every ArchitectOS Ollama call for a model takes that model's lease for the
# duration of the call. H2 takes the same lease EXCLUSIVELY, so acquiring it
# proves no ArchitectOS call to that model is in flight, and holding it keeps
# it that way across the unload. If the lease cannot be acquired the handoff
# FAILS CLOSED — it never unloads a model another request is using.
#
# FACADE-04D.3C-5B.1 — TWO MORE RACES, TWO MORE LEASES
# ---------------------------------------------------
# Releasing H2's model lease is NOT enough to protect the render itself:
#
#   * RACE A — once H2 releases the model lease, any later ArchitectOS Ollama
#     call can reload the model into VRAM while ComfyUI is still rendering.
#     Worse, `RenderRuntime.render()` itself calls
#     `semantic_intent.extract()` (mode img2img) BETWEEN H2 and the ComfyUI
#     submit, so the unload was undone by the very same request.
#     => the `gpu_render` lease: taken by EVERY Ollama inference and by the
#        protected dual-image render for its whole period.
#
#   * RACE B — H1's `GET /queue` and `POST /free` are not atomic: an
#     ArchitectOS render can submit in between and have its models freed.
#     => the `comfyui` lease: taken by H1 across that window and by every
#        ArchitectOS `POST /prompt`.
#
# THE ONLY LEGAL ACQUISITION ORDER (any other order can deadlock):
#
#     gpu_render  ->  comfyui  ->  ollama_model__<model>
#
# Every acquisition is bounded and every release happens in a `finally`.
# The handoff module's own /api/ps and /free/unload calls deliberately do NOT
# go through `ollama_model_call`, so they can never self-deadlock.
#
# SCOPE / LIMITS (do not overstate)
#   * The lease coordinates ArchitectOS processes. A third-party client that
#     talks to Ollama directly, outside ArchitectOS, is not covered; H2
#     additionally re-checks /api/ps, but that cannot see in-flight requests.
#   * Ollama and ComfyUI are EXTERNALLY managed. This module never starts,
#     stops or signals either service. It only uses their documented HTTP
#     APIs (/free, /api/ps, /api/generate with keep_alive=0).
#   * Nothing here renders, submits a ComfyUI job or runs GPU inference.
# ==========================================================

from __future__ import annotations

import os
import re
import time

import requests

from config import runtime_config as RC


CONTRACT = "GpuHandoffV1"
VERSION = "1.0"


# ==========================================================
# ERRORS
# ==========================================================

class GpuHandoffError(RuntimeError):
    """Base error for the GPU handoff layer."""


class GpuHandoffLockError(GpuHandoffError):
    """A cross-process lease could not be acquired."""


class OllamaModelBusy(GpuHandoffError):
    """Another ArchitectOS request holds the lease for this Ollama model.

    Raised by :func:`ollama_model_call` so the caller can fail truthfully
    instead of running an inference the handoff cannot account for.
    """


# ==========================================================
# SETTINGS (read at call time — never frozen at import)
# ==========================================================

def _setting(name, default, cast=float):
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return cast(default)
    value = cast(raw)
    if isinstance(value, float) and value != value:  # NaN
        return cast(default)
    if value < 0:
        raise ValueError(name + " must be >= 0")
    return value


def handoff_dir():
    """Shared, cross-process directory holding the advisory lock files."""
    configured = os.environ.get("ARCHITECTOS_GPU_HANDOFF_DIR")
    path = configured or os.path.join(
        RC.REPO_ROOT, "logs", "runtime", "gpu_handoff"
    )
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


def _lock_poll_interval():
    return _setting("ARCHITECTOS_GPU_HANDOFF_LOCK_POLL", 0.05)


# ==========================================================
# CROSS-PROCESS ADVISORY LEASE
# ==========================================================

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize(name):
    cleaned = _SAFE_NAME.sub("_", str(name)).strip("_")
    return cleaned or "unnamed"


def lock_path(kind, name):
    return os.path.join(
        handoff_dir(), "%s__%s.lock" % (_sanitize(kind), _sanitize(name))
    )


def ollama_model_lock_path(model):
    """One lock file per Ollama model — calls to DIFFERENT models never block."""
    return lock_path("ollama_model", model)


def comfyui_lock_path():
    """One lock file for the ArchitectOS-controlled ComfyUI submission window.

    Makes H1's [GET /queue -> POST /free] window atomic with respect to every
    ArchitectOS ``POST /prompt``: a queue-empty observation plus this lease is
    an actual guarantee, not a hopeful one.
    """
    return lock_path("comfyui", "submission")


def gpu_render_lock_path():
    """One lock file for the exclusive PROTECTED RENDERING PERIOD.

    Held for the whole time the FLUX/ComfyUI stack owns the GPU, so that no
    Ollama inference can reload a model into the same ~16 GiB while the render
    is running. Releasing H2's model lease alone does NOT provide this.
    """
    return lock_path("gpu_render", "protected")


class CrossProcessLock:
    """Exclusive advisory lock shared by every process on this machine.

    Windows uses ``msvcrt.locking`` (a byte-range lock on the first byte);
    POSIX uses ``fcntl.flock``. The lock is released by :meth:`release` and
    by the OS when the handle closes or the process dies, so a crashed holder
    can never deadlock the system permanently.
    """

    def __init__(self, path, timeout=0.0, poll_interval=None):
        self.path = path
        self.timeout = float(timeout)
        self.poll_interval = float(
            poll_interval if poll_interval is not None else _lock_poll_interval()
        )
        self._handle = None
        self._locked = False
        self.acquire_attempts = 0

    # ------------------------------------------------------
    @property
    def held(self):
        return self._locked

    def _try_lock(self):
        try:
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False
        except Exception:
            return False

    def _unlock(self):
        try:
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass

    def acquire(self):
        """Try to take the lease for at most ``timeout`` seconds."""
        if self._locked:
            return True
        try:
            self._handle = open(self.path, "a+b")
        except Exception:
            self._handle = None
            return False
        deadline = time.monotonic() + self.timeout
        while True:
            self.acquire_attempts += 1
            if self._try_lock():
                self._locked = True
                return True
            if time.monotonic() >= deadline:
                self.close()
                return False
            time.sleep(self.poll_interval)

    def release(self):
        if self._handle is not None and self._locked:
            self._unlock()
        self._locked = False
        self.close()

    def close(self):
        try:
            if self._handle is not None:
                self._handle.close()
        except Exception:
            pass
        self._handle = None
        self._locked = False

    def __enter__(self):
        if not self.acquire():
            raise GpuHandoffLockError(
                "lock_not_acquired:" + os.path.basename(self.path)
            )
        return self

    def __exit__(self, *exc_info):
        self.release()
        return False


def ollama_model_lease(model, wait=None):
    """An unacquired lease for ``model`` (see :class:`CrossProcessLock`)."""
    return CrossProcessLock(
        ollama_model_lock_path(model),
        timeout=(
            _setting("ARCHITECTOS_GPU_HANDOFF_LEASE_WAIT", 600)
            if wait is None
            else float(wait)
        ),
    )


def comfyui_lease(wait=None):
    """An unacquired ComfyUI submission-window lease (see H1)."""
    return CrossProcessLock(
        comfyui_lock_path(),
        timeout=(
            _setting("ARCHITECTOS_GPU_HANDOFF_COMFYUI_WAIT", 30)
            if wait is None
            else float(wait)
        ),
    )


def gpu_render_lease(wait=None):
    """An unacquired PROTECTED-RENDER lease (see :func:`gpu_render_lock_path`)."""
    return CrossProcessLock(
        gpu_render_lock_path(),
        timeout=(
            _setting("ARCHITECTOS_GPU_HANDOFF_RENDER_WAIT", 30)
            if wait is None
            else float(wait)
        ),
    )


#: The ONLY legal acquisition order. Taking these locks in any other order can
#: deadlock, so every caller must follow it:
#:
#:     gpu_render  ->  comfyui  ->  ollama_model__<model>
#:
#: * an Ollama inference  : gpu_render -> ollama_model
#: * a protected render   : gpu_render -> (comfyui during submit) -> ollama_model (H2)
#: * H1 cache release     : comfyui only
LOCK_ORDER = ("gpu_render", "comfyui", "ollama_model")


class ollama_model_call:
    """Hold the GPU exclusively for ONE Ollama inference.

    Acquires the protected-render lease FIRST (so an inference can never start
    while a render owns the GPU), then the model's own lease. Every ArchitectOS
    Ollama call goes through this, which is what makes H2's exclusive
    acquisition a real proof of ownership and what keeps the model unloaded for
    the whole protected rendering period.

    Raises :class:`OllamaModelBusy` when either lease cannot be taken in time —
    the caller must then fail truthfully rather than inferring outside the
    handoff's accounting. Both leases are always released.
    """

    def __init__(self, model, wait=None):
        self.model = model
        self._wait = wait
        self._render = gpu_render_lease(wait=wait)
        self._lock = ollama_model_lease(model, wait=wait)

    @property
    def held(self):
        return self._lock.held

    def __enter__(self):
        if not self._render.acquire():
            raise OllamaModelBusy("gpu_render_busy:" + str(self.model))
        if not self._lock.acquire():
            self._render.release()
            raise OllamaModelBusy("ollama_model_busy:" + str(self.model))
        return self

    def __exit__(self, *exc_info):
        self._lock.release()
        self._render.release()
        return False


# ==========================================================
# HTTP TRANSPORT (injectable so the test suite can mock it)
# ==========================================================

def _session():
    """A localhost-safe requests session (an ambient HTTP_PROXY must not
    route 127.0.0.1 calls away from the local services)."""
    session = requests.Session()
    session.trust_env = False
    return session


def _error_kind(exc):
    """Classify a transport failure.

    "connection" means the service is NOT LISTENING (refused / unreachable).
    That is materially different from a service that is up but unhealthy: a
    service that is not running holds no VRAM, so there is nothing to release
    and proceeding is safe. Every other failure fails closed.
    """
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "connection"
    return "other"


def _get_json(session, url, timeout):
    """Read a JSON endpoint. Returns ``(payload, error_kind)``.

    ``error_kind`` is ``None`` on a successful 200 JSON read.
    """
    try:
        response = session.get(url, timeout=timeout)
    except Exception as exc:
        return None, _error_kind(exc)
    if getattr(response, "status_code", None) != 200:
        return None, "http"
    try:
        return response.json(), None
    except Exception:
        return None, "invalid"


def _get_json_ok(session, url, timeout):
    """Best-effort JSON read (any failure -> None)."""
    payload, _ = _get_json(session, url, timeout)
    return payload


def _post_json(session, url, payload, timeout):
    """POST JSON. Returns ``(response, error_kind)``."""
    try:
        return session.post(url, json=payload, timeout=timeout), None
    except Exception as exc:
        return None, _error_kind(exc)


def _vram_free(session, endpoint, timeout):
    stats = _get_json_ok(session, endpoint + "/system_stats", timeout)
    if not isinstance(stats, dict):
        return None
    devices = stats.get("devices")
    if isinstance(devices, list) and devices and isinstance(devices[0], dict):
        value = devices[0].get("vram_free")
        if isinstance(value, (int, float)):
            return int(value)
    value = stats.get("vram_free")
    return int(value) if isinstance(value, (int, float)) else None


# ==========================================================
# H1 — SAFE COMFYUI CACHE RELEASE (BEFORE VISION)
# ==========================================================

def _comfy_queue_state(session, endpoint, timeout, result):
    """Returns True when the ComfyUI queue is provably empty.

    Sets ``status``/``reason`` on ``result`` for every non-proceed outcome.
    """
    queue, kind = _get_json(session, endpoint + "/queue", timeout)
    if queue is None:
        if kind == "connection":
            # ComfyUI is not listening: it holds no VRAM, so there is nothing
            # to release and proceeding is safe.
            result["status"] = "not_running"
            result["reason"] = "comfyui_not_running"
            return False
        result["status"] = "blocked"
        result["reason"] = "comfy_queue_unreadable"
        return False
    if not isinstance(queue, dict):
        result["status"] = "blocked"
        result["reason"] = "comfy_queue_unreadable"
        return False
    running = queue.get("queue_running") or []
    pending = queue.get("queue_pending") or []
    result["queue_running"] = len(running)
    result["queue_pending"] = len(pending)
    if running or pending:
        result["status"] = "blocked"
        result["reason"] = "comfy_queue_not_empty"
        return False
    return True


def release_comfyui_for_vision(endpoint=None, session=None):
    """H1 — release ComfyUI's cached models before the A/B vision analysis.

    Fails closed (``status="blocked"``) when the release is not provably safe:
    the queue cannot be read, the queue is not empty (another render is
    running or pending), /free fails, or the release cannot be confirmed by a
    bounded /system_stats read.

    ``status="not_running"`` (ComfyUI is not listening, so it holds no VRAM)
    is ALSO safe and the caller proceeds. ComfyUI is never stopped or
    signalled and no job is ever interrupted or cancelled.

    RACE CONDITION B — the whole [GET /queue -> POST /free] window is held
    under the ComfyUI submission lease. A queue-empty observation alone is NOT
    atomic: an ArchitectOS render could submit between the two calls and have
    its models freed underneath it. Holding the lease makes the window atomic
    with respect to every ArchitectOS ``POST /prompt``; a submission that
    arrives in between either finished before the queue read (and is therefore
    visible) or waits until the release is complete.
    """
    endpoint = (endpoint or RC.COMFYUI_URL).rstrip("/")
    session = session or _session()

    http_timeout = _setting("ARCHITECTOS_GPU_HANDOFF_COMFY_TIMEOUT", 10)
    poll_timeout = _setting("ARCHITECTOS_GPU_HANDOFF_COMFY_POLL_TIMEOUT", 15)
    poll_interval = _setting("ARCHITECTOS_GPU_HANDOFF_COMFY_POLL_INTERVAL", 0.5)

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "stage": "H1",
        "stage_name": "comfyui_release_before_vision",
        "endpoint": endpoint,
        "status": None,
        "reason": None,
        "queue_running": None,
        "queue_pending": None,
        "vram_free_before": None,
        "vram_free_after": None,
        "released_bytes": None,
        "release_confirmed": False,
        "poll_attempts": 0,
        "elapsed_s": None,
        "comfyui_lease": "not_acquired",
    }
    started = time.monotonic()

    def _finish():
        result["elapsed_s"] = round(time.monotonic() - started, 3)
        return result

    # ---- RACE B: own the submission window before reading the queue ----
    lease = comfyui_lease()
    if not lease.acquire():
        result["status"] = "blocked"
        result["reason"] = "comfyui_busy"
        return _finish()
    result["comfyui_lease"] = "exclusive"

    try:
        if not _comfy_queue_state(session, endpoint, http_timeout, result):
            return _finish()

        result["vram_free_before"] = _vram_free(session, endpoint, http_timeout)

        response, kind = _post_json(
            session,
            endpoint + "/free",
            {"unload_models": True, "free_memory": True},
            http_timeout,
        )
        status_code = getattr(response, "status_code", None)
        result["free_http_status"] = status_code
        if status_code is None or status_code >= 400:
            result["status"] = "blocked"
            result["reason"] = "comfy_free_failed"
            return _finish()

        deadline = time.monotonic() + poll_timeout
        after = None
        while True:
            result["poll_attempts"] += 1
            after = _vram_free(session, endpoint, http_timeout)
            if after is not None:
                break
            if time.monotonic() >= deadline:
                break
            time.sleep(poll_interval)

        if after is None:
            result["status"] = "blocked"
            result["reason"] = "comfy_release_unconfirmed"
            return _finish()

        result["vram_free_after"] = after
        result["release_confirmed"] = True
        if isinstance(result["vram_free_before"], int):
            result["released_bytes"] = max(0, after - result["vram_free_before"])
        result["status"] = "released"
        return _finish()
    finally:
        lease.release()


# ==========================================================
# H2 — SAFE OLLAMA MODEL RELEASE (AFTER VISION, BEFORE RENDER)
# ==========================================================

def _ollama_ps(session, endpoint, timeout):
    """Returns ``(names_or_None, error_kind)``."""
    body, kind = _get_json(session, endpoint + "/api/ps", timeout)
    if body is None:
        return None, kind
    if not isinstance(body, dict):
        return None, "invalid"
    models = body.get("models")
    if not isinstance(models, list):
        return None, "invalid"
    names = []
    for item in models:
        if isinstance(item, dict) and item.get("name"):
            names.append(item["name"])
    return names, None


def _ollama_unload(session, endpoint, model, timeout):
    response, _ = _post_json(
        session,
        endpoint + "/api/generate",
        {"model": model, "keep_alive": 0},
        timeout,
    )
    status_code = getattr(response, "status_code", None)
    return status_code is not None and status_code < 400


def _wait_model_gone(session, endpoint, model, timeout, interval, http_timeout):
    deadline = time.monotonic() + timeout
    attempts = 0
    while True:
        attempts += 1
        loaded, _ = _ollama_ps(session, endpoint, http_timeout)
        if loaded is not None and model not in loaded:
            return attempts
        if time.monotonic() >= deadline:
            return None
        time.sleep(interval)


def unload_ollama_models_for_render(
    vision_model=None, endpoint=None, session=None, comfy_endpoint=None
):
    """H2 — release Ollama models between the vision stage and the render.

    ``vision_model`` (the configured vision model, ``qwen3.8:27b``) is
    MANDATORY: if it cannot be exclusively leased, unloaded and confirmed
    gone, the whole handoff fails closed. Every OTHER loaded model is released
    best-effort, and only when its own lease is free — a model another request
    is using is skipped, never unloaded.

    Returns a trace dict. ``status`` is ``"unloaded"``, ``"not_loaded"``
    (nothing was resident), ``"not_running"`` (Ollama is not listening, so
    nothing can be resident — also safe) or ``"blocked"`` with a ``reason``.

    MUST be called while the caller already holds the ``gpu_render`` lease
    (FACADE-04D.3C-5B.1), so that the model stays unloaded for the whole
    protected rendering period and not merely until the next inference.
    """
    from config.vision_config import VisionConfig

    endpoint = (endpoint or RC.OLLAMA_URL).rstrip("/")
    session = session or _session()
    vision_model = vision_model or VisionConfig.from_env().model

    # The card-level VRAM reading comes from ComfyUI's /system_stats: it is the
    # only local endpoint that reports the whole adapter, and Ollama serves no
    # equivalent. Best-effort — an unreadable value is recorded, never fatal.
    vram_endpoint = (comfy_endpoint or RC.COMFYUI_URL).rstrip("/")

    http_timeout = _setting("ARCHITECTOS_GPU_HANDOFF_OLLAMA_TIMEOUT", 10)
    acquire_wait = _setting("ARCHITECTOS_GPU_HANDOFF_UNLOAD_WAIT", 120)
    poll_timeout = _setting("ARCHITECTOS_GPU_HANDOFF_OLLAMA_POLL_TIMEOUT", 45)
    poll_interval = _setting("ARCHITECTOS_GPU_HANDOFF_OLLAMA_POLL_INTERVAL", 0.5)

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "stage": "H2",
        "stage_name": "ollama_unload_after_vision",
        "endpoint": endpoint,
        "vision_model": vision_model,
        "status": None,
        "reason": None,
        "ownership": "not_acquired",
        "loaded_before": None,
        "unloaded": [],
        "failed": [],
        "skipped_in_use": [],
        "target_released": False,
        "vram_free_before": None,
        "vram_free_after": None,
        "elapsed_s": None,
    }
    started = time.monotonic()

    def _finish():
        result["elapsed_s"] = round(time.monotonic() - started, 3)
        return result

    lease = ollama_model_lease(vision_model, wait=acquire_wait)
    if not lease.acquire():
        # Another ArchitectOS request is using the same model right now.
        # NEVER unload under it — fail closed instead.
        result["status"] = "blocked"
        result["reason"] = "ollama_model_busy"
        return _finish()

    try:
        result["ownership"] = "exclusive"

        loaded, kind = _ollama_ps(session, endpoint, http_timeout)
        if loaded is None:
            if kind == "connection":
                # Ollama is not listening: no model can be resident, so there
                # is nothing to release and proceeding is safe.
                result["status"] = "not_running"
                result["reason"] = "ollama_not_running"
                return _finish()
            result["status"] = "blocked"
            result["reason"] = "ollama_ps_unreadable"
            return _finish()

        result["loaded_before"] = sorted(loaded)
        result["vram_free_before"] = _vram_free(session, vram_endpoint, http_timeout)

        if vision_model not in loaded:
            result["target_released"] = True
        else:
            if not _ollama_unload(session, endpoint, vision_model, http_timeout):
                result["status"] = "blocked"
                result["reason"] = "ollama_unload_failed"
                return _finish()
            if _wait_model_gone(
                session, endpoint, vision_model, poll_timeout, poll_interval,
                http_timeout,
            ) is None:
                result["status"] = "blocked"
                result["reason"] = "ollama_unload_unconfirmed"
                return _finish()
            result["target_released"] = True
            result["unloaded"].append(vision_model)

        # Best-effort: free every OTHER resident model whose lease is free.
        for model in result["loaded_before"]:
            if model == vision_model:
                continue
            other = ollama_model_lease(model, wait=0)
            if not other.acquire():
                result["skipped_in_use"].append(model)
                continue
            try:
                if _ollama_unload(session, endpoint, model, http_timeout) and (
                    _wait_model_gone(
                        session, endpoint, model, poll_timeout, poll_interval,
                        http_timeout,
                    ) is not None
                ):
                    result["unloaded"].append(model)
                else:
                    result["failed"].append(model)
            finally:
                other.release()

        result["vram_free_after"] = _vram_free(session, vram_endpoint, http_timeout)
        result["status"] = "unloaded" if result["loaded_before"] else "not_loaded"
        return _finish()
    finally:
        lease.release()


# ==========================================================
# V4.3D — VRAM PREFLIGHT GATE FOR A RENDER
#
# UNITS (read this before touching the numbers)
# ---------------------------------------------
# ComfyUI `/system_stats` reports `devices[0].vram_free` in BYTES.
# `_vram_free()` returns that value unchanged. Every comparison here is done in
# MiB, with an explicit conversion, and the trace records the unit. The V4.3C
# proposal compared raw BYTES against `9000` MB, which would have passed on any
# machine — the gate would have been decorative.
#
# THRESHOLD
# ---------
# `ARCHITECTOS_RENDER_MIN_FREE_VRAM_MIB`, default 11264 MiB (11 GiB).
# This is a POLICY FLOOR, not a validated requirement: the V4.3B measurement of
# the FLUX fp8 workflow needs ~11 GB and no real render has yet recorded
# `vram_free_before/after` and peak usage. It must be revised from that trace.
#
# FAIL-CLOSED
# -----------
# An unmeasurable value BLOCKS. There is no "assume it is fine" path.
# ==========================================================

RENDER_VRAM_CONTRACT = "RenderVramGateV1"
RENDER_VRAM_VERSION = "1.0"

DEFAULT_MIN_FREE_VRAM_MIB = 11264.0

_BYTES_PER_MIB = 1024.0 * 1024.0


def require_render_vram(h2_trace=None, min_free_mib=None, endpoint=None,
                        session=None, timeout=None):
    """Return the render VRAM verdict. Never raises; never guesses.

    Measurement source, in order:
      1. ``h2_trace["vram_free_after"]`` — already measured by H2 under the
         render lease, in bytes;
      2. one read of ComfyUI ``/system_stats`` when H2 has no value.

    ``ok`` is True only when a numeric measurement is >= the threshold.
    """

    threshold_mib = float(
        _setting(
            "ARCHITECTOS_RENDER_MIN_FREE_VRAM_MIB",
            DEFAULT_MIN_FREE_VRAM_MIB if min_free_mib is None else min_free_mib,
        )
    )

    result = {
        "contract": RENDER_VRAM_CONTRACT,
        "version": RENDER_VRAM_VERSION,
        "ok": False,
        "reason": None,
        "free_mib": None,
        "min_free_mib": round(threshold_mib, 1),
        "measurement_source": None,
        "measurement_units": "MiB (converted from bytes reported by ComfyUI /system_stats)",
        "raw_bytes": None,
    }

    raw_bytes = None

    if isinstance(h2_trace, dict):
        candidate = h2_trace.get("vram_free_after")
        if isinstance(candidate, (int, float)):
            raw_bytes = int(candidate)
            result["measurement_source"] = "h2.vram_free_after"

    if raw_bytes is None:
        http_timeout = (
            _setting("ARCHITECTOS_GPU_HANDOFF_OLLAMA_TIMEOUT", 10)
            if timeout is None else float(timeout)
        )
        try:
            measured = _vram_free(
                session or _session(),
                (endpoint or RC.COMFYUI_URL).rstrip("/"),
                http_timeout,
            )
        except BaseException:
            measured = None
        if isinstance(measured, (int, float)):
            raw_bytes = int(measured)
            result["measurement_source"] = "comfyui_system_stats"

    if raw_bytes is None:
        # Fail closed: an unmeasurable GPU must not be treated as an empty one.
        result["reason"] = "vram_unmeasured"
        return result

    free_mib = raw_bytes / _BYTES_PER_MIB
    result["raw_bytes"] = raw_bytes
    result["free_mib"] = round(free_mib, 1)

    if free_mib < threshold_mib:
        result["reason"] = "insufficient_vram"
        return result

    result["ok"] = True
    result["reason"] = "ok"
    return result
