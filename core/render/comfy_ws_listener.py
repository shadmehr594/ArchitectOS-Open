# ==========================================================
# ArchitectOS ComfyUI WebSocket Listener v2.0
#
# REAL_SAMPLING_PROGRESS_B_PLUS — CORRECTED
#
# Transport: aiohttp's WebSocket client, which is ALREADY INSTALLED
# in the production Core interpreter (aiohttp 3.14.3, verified).
# No dependency was added. The previous hand-rolled RFC 6455 stack
# was removed because it could not transmit a close frame, could
# not bound frame size, and dropped bytes that arrived in the same
# TCP segment as the 101 response. See the correction report for
# the full justification.
#
# Contract (unchanged for callers):
#   listener = ComfyProgressListener(url, prompt_id, client_id, sampler_node_ids)
#   ready   = listener.start()     # blocks until the handshake resolves
#   latest  = listener.latest()    # {"step", "max", "node", ...} or None
#   listener.stop()                # close handshake + bounded join
#
# Hard rules enforced here:
#   * PROMPT CORRELATION IS STRICT. A non-empty bound prompt_id AND a
#     non-empty incoming prompt_id AND exact equality are required for
#     EVERY event type, including the broadcast execution_interrupted.
#     An uncorrelated event changes nothing at all.
#   * SAMPLER VERIFICATION FAILS CLOSED. No verified sampler node means
#     no progress is ever accepted. Non-sampler nodes are always
#     rejected, and step/max values must be sane.
#   * NOTHING HERE CAN BREAK A RENDER. Every failure path degrades to
#     "no sampling progress" while the existing poll-based lifecycle
#     in wait_for_result() continues untouched.
# ==========================================================

import asyncio
import json
import threading
import time
import uuid

try:  # pragma: no cover - exercised implicitly by every import
    import aiohttp
    from aiohttp import WSMsgType
    AIOHTTP_AVAILABLE = True
    AIOHTTP_IMPORT_ERROR = None
except Exception as _aiohttp_error:  # pragma: no cover
    aiohttp = None
    WSMsgType = None
    AIOHTTP_AVAILABLE = False
    AIOHTTP_IMPORT_ERROR = "%s: %s" % (
        type(_aiohttp_error).__name__, _aiohttp_error
    )


CONTRACT = "ComfyProgressListenerV2"
VERSION = "2.0"


# ==========================================================
# BOUNDS
# ==========================================================

DEFAULT_CONNECT_TIMEOUT = 10.0
DEFAULT_READ_TIMEOUT = 0.5          # receive slice; stop is honoured each slice
DEFAULT_STOP_JOIN_TIMEOUT = 5.0
DEFAULT_MAX_MESSAGE_BYTES = 8 * 1024 * 1024


# ==========================================================
# SAMPLER CLASSIFICATION — EVIDENCE BASED
#
# Only node classes that BOTH exist in the installed ComfyUI
# (C:\ComfyUI-Zluda) AND actually execute a sampling loop that
# reports step progress are listed.
#
# Verified chain for the two KSampler families:
#   KSampler / KSamplerAdvanced
#     -> nodes.common_ksampler (callback = latent_preview.prepare_callback)
#     -> comfy.sample.sample
#     -> comfy.samplers.CFGGuider.sample -> KSAMPLER.sample
#     -> k_callback(x) -> callback(x["i"], ..., total_steps)
#     -> comfy.utils.ProgressBar -> main.py hook -> "progress" event
#
# Verified chain for the custom-sampler family:
#   SamplerCustom / SamplerCustomAdvanced
#     -> comfy.sample.sample_custom / guider.sample
#     -> comfy.samplers (same KSAMPLER.sample callback path)
#
# DELIBERATELY EXCLUDED:
#   KSamplerSelect  — installed, but it only SELECTS a sampler object;
#                     it never samples, so it emits no step progress.
#   KScheduler      — NOT installed in this ComfyUI at all.
#   FastSampler, CFGGuidedSampler, "KSampler (Efficient)"
#                   — NOT installed in this ComfyUI; including them
#                     would be a guess, not evidence.
#
# Adding a class requires evidence that it emits sampler step
# progress in THIS installation. A wrong entry would let a
# non-sampling node drive the "Step X / Y" label.
# ==========================================================

SAMPLER_NODE_TYPES = frozenset({
    "KSampler",
    "KSamplerAdvanced",
    "SamplerCustom",
    "SamplerCustomAdvanced",
})


def identify_sampler_nodes(workflow):
    """Return {node_id: class_type} for executing sampler nodes only.

    The submitted workflow is the ONLY authoritative source: node ids
    are read from the graph, never guessed. A malformed graph yields an
    empty mapping, and an empty mapping makes the listener fail closed
    (no progress is accepted at all).
    """
    samplers = {}

    if not isinstance(workflow, dict):
        return samplers

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type") or "")
        if class_type in SAMPLER_NODE_TYPES:
            samplers[str(node_id)] = class_type

    return samplers


def sampler_node_ids(workflow):
    """Convenience: the verified sampler node ids of a workflow."""
    return frozenset(identify_sampler_nodes(workflow).keys())


# ==========================================================
# LISTENER
# ==========================================================

class ComfyProgressListener:

    VERSION = VERSION

    def __init__(
        self,
        ws_url,
        prompt_id,
        client_id,
        sampler_node_ids=None,
        connect_timeout=DEFAULT_CONNECT_TIMEOUT,
        read_timeout=DEFAULT_READ_TIMEOUT,
        stop_join_timeout=DEFAULT_STOP_JOIN_TIMEOUT,
        max_message_bytes=DEFAULT_MAX_MESSAGE_BYTES,
    ):
        self._ws_url = str(ws_url or "")
        self._prompt_id = str(prompt_id or "")
        self._client_id = str(client_id or "")

        # An absent/empty allowlist is a legitimate state and means
        # "accept nothing". It is never treated as "accept anything".
        self._sampler_node_ids = frozenset(
            str(n) for n in (sampler_node_ids or ())
        )

        self._connect_timeout = float(connect_timeout)
        self._read_timeout = float(read_timeout)
        self._stop_join_timeout = float(stop_join_timeout)
        self._max_message_bytes = int(max_message_bytes)

        self._lock = threading.RLock()

        self._thread = None
        self._ready = threading.Event()
        self._ready_ok = False
        self._stop_event = threading.Event()
        self._stop_incomplete = False

        self._latest = None
        self._terminal = False
        self._terminal_reason = None

        # Observability only.
        self._events_seen = 0
        self._events_accepted = 0
        self._events_rejected = 0
        self._last_error = None

    # ==================================================
    # PUBLIC API
    # ==================================================

    def start(self, timeout=None):
        """Open the listener and block until the handshake resolves.

        Returns True only when the WebSocket is genuinely connected, so
        the caller can decide to submit AFTER the socket is ready. A
        False return is honest: no progress will arrive and the render
        proceeds on the existing poll-based lifecycle.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self._ready_ok

            if not self._ws_url:
                self._ready_ok = False
                self._ready.set()
                return False

            if not AIOHTTP_AVAILABLE:
                self._last_error = "aiohttp_unavailable: %s" % AIOHTTP_IMPORT_ERROR
                self._set_terminal("ws_unavailable")
                self._ready_ok = False
                self._ready.set()
                return False

            self._thread = threading.Thread(
                target=self._run,
                name="ComfyProgressListener-%s" % (self._client_id[:8] or "anon"),
                daemon=True,
            )
            self._thread.start()

        budget = self._connect_timeout if timeout is None else float(timeout)

        # The handshake is bounded by sock_connect; this wait is the
        # outer guard so start() can never block indefinitely.
        self._ready.wait(budget + 1.0)

        return bool(self._ready_ok)

    def stop(self):
        """Close the socket and join the worker, honestly.

        Returns True only when the worker thread is provably gone. A
        False return means the thread did not exit within the join
        budget and is reported as still running rather than pretended
        to be cleaned up.
        """
        self._stop_event.set()

        thread = self._thread

        if thread is None:
            return True

        if thread.is_alive():
            thread.join(timeout=self._stop_join_timeout)

        if thread.is_alive():
            self._stop_incomplete = True
            return False

        with self._lock:
            self._thread = None

        return True

    def is_running(self):
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def bind_prompt_id(self, prompt_id):
        """Bind the prompt this listener is allowed to report on.

        Returns False when the id is empty: an unbound listener accepts
        nothing, so binding can never widen the filter.
        """
        value = str(prompt_id or "")

        if not value:
            return False

        with self._lock:
            self._prompt_id = value

        return True

    def latest(self):
        with self._lock:
            return dict(self._latest) if self._latest else None

    def is_terminal(self):
        with self._lock:
            return bool(self._terminal)

    def stats(self):
        """Read-only observability for tests and diagnostics."""
        with self._lock:
            return {
                "contract": CONTRACT,
                "version": VERSION,
                "connected": bool(self._ready_ok),
                "running": self.is_running(),
                "stop_incomplete": bool(self._stop_incomplete),
                "bound_prompt_id": self._prompt_id,
                "sampler_node_ids": sorted(self._sampler_node_ids),
                "events_seen": self._events_seen,
                "events_accepted": self._events_accepted,
                "events_rejected": self._events_rejected,
                "terminal": bool(self._terminal),
                "terminal_reason": self._terminal_reason,
                "last_error": self._last_error,
            }

    # ==================================================
    # THREAD / ASYNC PLUMBING
    # ==================================================

    def _run(self):
        try:
            asyncio.run(self._async_run())
        except BaseException as exc:  # noqa: BLE001 - never propagate
            self._last_error = "%s: %s" % (type(exc).__name__, exc)
            self._set_terminal("ws_error: %s" % type(exc).__name__)
        finally:
            self._ready.set()

    async def _async_run(self):
        # trust_env=False is mandatory on this machine: HTTP_PROXY is
        # set globally and a proxied connection to 127.0.0.1 fails.
        timeout = aiohttp.ClientTimeout(
            total=None,
            sock_connect=self._connect_timeout,
            sock_read=None,
        )

        connector = aiohttp.TCPConnector(force_close=True, limit=1)

        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            trust_env=False,
        ) as session:

            try:
                ws = await session.ws_connect(
                    self._ws_url,
                    max_msg_size=self._max_message_bytes,
                    heartbeat=None,
                    autoping=True,
                    compress=0,
                )
            except Exception as exc:  # noqa: BLE001 - honest fallback
                self._last_error = "%s: %s" % (type(exc).__name__, exc)
                self._set_terminal("ws_error: %s" % type(exc).__name__)
                return

            self._ready_ok = True
            self._ready.set()

            try:
                await self._consume(ws)
            finally:
                # Closing inside the event loop sends a real close frame.
                try:
                    await ws.close()
                except Exception:
                    pass

    async def _consume(self, ws):
        while not self._stop_event.is_set():

            try:
                msg = await ws.receive(timeout=self._read_timeout)
            except asyncio.TimeoutError:
                # No frame in this slice. The stop event is re-checked
                # at the top of the loop, so shutdown stays bounded.
                continue
            except Exception as exc:  # noqa: BLE001
                self._last_error = "%s: %s" % (type(exc).__name__, exc)
                self._set_terminal("ws_error: %s" % type(exc).__name__)
                break

            if msg.type == WSMsgType.TEXT:
                self._handle_text(msg.data)
            elif msg.type == WSMsgType.BINARY:
                # ComfyUI streams preview images here; they carry no
                # sampling information and are ignored.
                continue
            elif msg.type == WSMsgType.ERROR:
                self._last_error = str(ws.exception())
                self._set_terminal("ws_error")
                break
            elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED):
                break

            if self.is_terminal():
                break

    # ==================================================
    # EVENT HANDLING
    # ==================================================

    def _is_correlated(self, data):
        """Strict correlation. All three conditions are mandatory."""
        bound = str(self._prompt_id or "")

        if not bound:
            return False

        incoming = str((data or {}).get("prompt_id") or "")

        if not incoming:
            return False

        return incoming == bound

    def _handle_text(self, payload):
        """Route ONE text frame. Uncorrelated events change nothing."""
        try:
            if isinstance(payload, (bytes, bytearray)):
                payload = payload.decode("utf-8")
            msg = json.loads(payload)
        except (ValueError, UnicodeDecodeError, TypeError):
            return

        if not isinstance(msg, dict):
            return

        with self._lock:
            self._events_seen += 1

        data = msg.get("data")

        if not isinstance(data, dict):
            data = {}

        if not self._is_correlated(data):
            with self._lock:
                self._events_rejected += 1
            return

        with self._lock:
            self._events_accepted += 1

        msg_type = str(msg.get("type") or "")

        if msg_type == "execution_success":
            self._set_terminal("success")
        elif msg_type == "execution_error":
            self._set_terminal("error")
        elif msg_type == "execution_interrupted":
            self._set_terminal("interrupted")
        elif msg_type == "progress":
            self._handle_progress(data)

    def _handle_progress(self, data):
        """Accept progress ONLY for a verified sampler node.

        Fails closed in every direction:
          * no verified sampler allowlist  -> reject
          * node missing / not in allowlist -> reject
          * non-numeric, non-positive max   -> reject
          * step outside 0..max             -> reject
        """
        node_id = str(data.get("node") or "")

        if not self._sampler_node_ids:
            return

        if not node_id or node_id not in self._sampler_node_ids:
            return

        raw_value = data.get("value")
        raw_max = data.get("max")

        if raw_value is None or raw_max is None:
            return

        try:
            value = int(raw_value)
            max_value = int(raw_max)
        except (TypeError, ValueError):
            return

        if max_value <= 0:
            return

        if value < 0 or value > max_value:
            return

        with self._lock:
            self._latest = {
                "step": value,
                "max": max_value,
                "node": node_id,
                "verified_sampler": True,
                "updated_at": time.time(),
                "terminal": False,
                "terminal_reason": None,
            }

    def _set_terminal(self, reason):
        with self._lock:
            self._terminal = True
            self._terminal_reason = reason

            if self._latest:
                self._latest["terminal"] = True
                self._latest["terminal_reason"] = reason
            else:
                self._latest = {
                    "step": None,
                    "max": None,
                    "node": None,
                    "verified_sampler": False,
                    "updated_at": time.time(),
                    "terminal": True,
                    "terminal_reason": reason,
                }


# ==========================================================
# HELPERS
# ==========================================================

def make_client_id():
    """A unique ComfyUI client id for one render."""
    return uuid.uuid4().hex


def build_ws_url(comfyui_url, client_id):
    """Build the /ws URL from the existing HTTP ComfyUI endpoint."""
    url = str(comfyui_url or "").rstrip("/")

    if url.startswith("https://"):
        url = "wss://" + url[8:]
    elif url.startswith("http://"):
        url = "ws://" + url[7:]
    elif not url.startswith(("ws://", "wss://")):
        url = "ws://" + url

    return url + "/ws?clientId=" + str(client_id)
