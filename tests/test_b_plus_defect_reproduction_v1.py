# ==========================================================
# ArchitectOS B+ INDEPENDENT CORRECTION — Defect Reproduction
#
# Every test in this file asserts the CORRECT behaviour.
# Against the pre-correction code they FAIL, which is the
# evidence that the four reported defects are real.
#
# After correction the same file must pass unchanged.
#
# No GPU. No ComfyUI submission. A local aiohttp WebSocket
# server stands in for ComfyUI's /ws endpoint so the transport
# is exercised for real over TCP.
# ==========================================================

import asyncio
import base64
import hashlib
import json
import os
import socket
import struct
import sys
import threading
import time

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from aiohttp import web, WSMsgType

from core.render.comfy_ws_listener import (
    ComfyProgressListener,
    identify_sampler_nodes,
    SAMPLER_NODE_TYPES,
    make_client_id,
    build_ws_url,
)


# ==========================================================
# HARNESS
# ==========================================================

_PASS = 0
_FAIL = 0
_FAILURES = []


def check(condition, name, detail=""):
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print("  PASS: %s" % name)
    else:
        _FAIL += 1
        _FAILURES.append("%s :: %s" % (name, detail))
        print("  FAIL: %s -- %s" % (name, detail))


def listener(prompt_id="prompt-A", samplers=("10",), client_id="cid"):
    return ComfyProgressListener(
        "ws://127.0.0.1:9/ws?clientId=" + client_id,
        prompt_id=prompt_id,
        client_id=client_id,
        sampler_node_ids=set(samplers) if samplers is not None else None,
    )


def send(lst, msg_type, data):
    lst._handle_text(json.dumps({"type": msg_type, "data": data}).encode("utf-8"))


# ==========================================================
# LOCAL FAKE COMFYUI WEBSOCKET SERVER
# ==========================================================

class FakeComfyWS:
    """A real TCP WebSocket server that records what the client does."""

    def __init__(self, on_connect_message=None, abrupt=False):
        self.on_connect_message = on_connect_message
        self.abrupt = abrupt
        self.port = None
        self.connected = threading.Event()
        self.close_frame_seen = threading.Event()
        self.client_messages = []
        self._loop = None
        self._runner = None
        self._thread = None
        self._ws = None

    def start(self, timeout=10):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        self.port = probe.getsockname()[1]
        probe.close()

        ready = threading.Event()

        def _run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            app = web.Application()
            app.router.add_get("/ws", self._handle)
            self._runner = web.AppRunner(app)
            self._loop.run_until_complete(self._runner.setup())
            site = web.TCPSite(self._runner, "127.0.0.1", self.port)
            self._loop.run_until_complete(site.start())
            ready.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        ready.wait(timeout)
        return self.port

    def push(self, message):
        """Send one JSON text frame to the connected client."""
        ws = self._ws
        loop = self._loop
        if ws is None or loop is None:
            return False
        payload = json.dumps(message)
        asyncio.run_coroutine_threadsafe(ws.send_str(payload), loop)
        return True

    async def _handle(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._ws = ws
        self.connected.set()

        if self.on_connect_message is not None:
            await ws.send_str(json.dumps(self.on_connect_message))

        if self.abrupt:
            # Tear the TCP connection down without a close handshake.
            await ws.close(code=1006, message=b"abrupt")
            return ws

        try:
            async for msg in ws:
                if msg.type == WSMsgType.CLOSE:
                    self.close_frame_seen.set()
                    break
                if msg.type == WSMsgType.ERROR:
                    break
                if msg.type == WSMsgType.TEXT:
                    self.client_messages.append(msg.data)
        except Exception:
            pass

        return ws

    def stop(self):
        if self._loop is not None:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None


# ==========================================================
# DEFECT 1 — STRICT PROMPT CORRELATION
# ==========================================================

def d1_progress_without_prompt_id_is_rejected():
    print("\n--- DEFECT 1: progress without prompt_id must be rejected ---")

    lst = listener(prompt_id="prompt-A")
    send(lst, "progress", {"value": 5, "max": 20, "node": "10"})

    check(
        lst.latest() is None,
        "progress with no prompt_id is dropped",
        "got %r" % (lst.latest(),),
    )


def d1_foreign_prompt_id_is_rejected():
    print("\n--- DEFECT 1: foreign prompt_id must be rejected ---")

    lst = listener(prompt_id="prompt-A")
    send(lst, "progress",
         {"value": 5, "max": 20, "node": "10", "prompt_id": "prompt-B"})

    check(
        lst.latest() is None,
        "foreign prompt_id progress is dropped",
        "got %r" % (lst.latest(),),
    )


def d1_interrupted_without_prompt_id_is_rejected():
    print("\n--- DEFECT 1: interrupted without prompt_id must be rejected ---")

    lst = listener(prompt_id="prompt-A")
    send(lst, "execution_interrupted", {})

    check(
        not lst.is_terminal(),
        "interrupted with no prompt_id cannot terminate our listener",
        "terminal=%r" % (lst.is_terminal(),),
    )


def d1_foreign_interrupted_cannot_terminate():
    print("\n--- DEFECT 1: foreign interrupted cannot terminate ---")

    lst = listener(prompt_id="prompt-A")
    send(lst, "execution_interrupted", {"prompt_id": "prompt-B"})

    check(
        not lst.is_terminal(),
        "foreign interrupted is ignored",
        "terminal=%r" % (lst.is_terminal(),),
    )


def d1_correct_prompt_id_works():
    print("\n--- DEFECT 1: correct prompt_id still works ---")

    lst = listener(prompt_id="prompt-A")
    send(lst, "progress",
         {"value": 7, "max": 20, "node": "10", "prompt_id": "prompt-A"})

    prog = lst.latest()
    check(prog is not None and prog.get("step") == 7,
          "correct prompt_id progress accepted",
          "got %r" % (prog,))

    send(lst, "execution_success", {"prompt_id": "prompt-A"})
    check(lst.is_terminal(), "correct prompt_id success terminates")


def d1_unbound_listener_accepts_nothing():
    print("\n--- DEFECT 1: listener with no bound prompt_id accepts nothing ---")

    lst = listener(prompt_id="", samplers=("10",))

    send(lst, "progress", {"value": 5, "max": 20, "node": "10"})
    check(
        lst.latest() is None,
        "unbound listener rejects progress with empty prompt_id",
        "got %r" % (lst.latest(),),
    )

    send(lst, "execution_interrupted", {})
    check(
        not lst.is_terminal(),
        "unbound listener rejects interrupted with empty prompt_id",
        "terminal=%r" % (lst.is_terminal(),),
    )


def d1_success_without_prompt_id_is_rejected():
    print("\n--- DEFECT 1: success without prompt_id must be rejected ---")

    lst = listener(prompt_id="prompt-A")
    send(lst, "execution_success", {})

    check(
        not lst.is_terminal(),
        "success with no prompt_id cannot terminate our listener",
        "terminal=%r" % (lst.is_terminal(),),
    )


# ==========================================================
# DEFECT 2 — SAMPLER VERIFICATION MUST FAIL CLOSED
# ==========================================================

def d2_empty_allowlist_accepts_nothing():
    print("\n--- DEFECT 2: empty sampler allowlist accepts nothing ---")

    lst = listener(prompt_id="prompt-A", samplers=())
    send(lst, "progress",
         {"value": 5, "max": 20, "node": "10", "prompt_id": "prompt-A"})

    check(
        lst.latest() is None,
        "empty allowlist rejects all progress",
        "got %r" % (lst.latest(),),
    )


def d2_none_allowlist_accepts_nothing():
    print("\n--- DEFECT 2: None sampler allowlist accepts nothing ---")

    lst = listener(prompt_id="prompt-A", samplers=None)
    send(lst, "progress",
         {"value": 5, "max": 20, "node": "10", "prompt_id": "prompt-A"})

    check(
        lst.latest() is None,
        "None allowlist rejects all progress",
        "got %r" % (lst.latest(),),
    )


def d2_non_sampler_node_rejected():
    print("\n--- DEFECT 2: non-sampler node rejected ---")

    lst = listener(prompt_id="prompt-A", samplers=("10",))
    send(lst, "progress",
         {"value": 3, "max": 5, "node": "20", "prompt_id": "prompt-A"})

    check(
        lst.latest() is None,
        "non-sampler node progress dropped",
        "got %r" % (lst.latest(),),
    )


def d2_non_positive_max_rejected():
    print("\n--- DEFECT 2: non-positive max rejected ---")

    for bad_max in (0, -1):
        lst = listener(prompt_id="prompt-A", samplers=("10",))
        send(lst, "progress",
             {"value": 0, "max": bad_max, "node": "10",
              "prompt_id": "prompt-A"})
        check(
            lst.latest() is None,
            "max=%d rejected" % bad_max,
            "got %r" % (lst.latest(),),
        )


def d2_step_outside_range_rejected():
    print("\n--- DEFECT 2: step outside 0..max rejected ---")

    lst = listener(prompt_id="prompt-A", samplers=("10",))
    send(lst, "progress",
         {"value": 21, "max": 20, "node": "10", "prompt_id": "prompt-A"})
    check(lst.latest() is None, "step > max rejected",
          "got %r" % (lst.latest(),))

    lst = listener(prompt_id="prompt-A", samplers=("10",))
    send(lst, "progress",
         {"value": -1, "max": 20, "node": "10", "prompt_id": "prompt-A"})
    check(lst.latest() is None, "negative step rejected",
          "got %r" % (lst.latest(),))


def d2_select_and_schedule_classes_are_not_samplers():
    print("\n--- DEFECT 2: selector/scheduler classes are not executing samplers ---")

    check("KSamplerSelect" not in SAMPLER_NODE_TYPES,
          "KSamplerSelect removed from SAMPLER_NODE_TYPES",
          "still present")
    check("KScheduler" not in SAMPLER_NODE_TYPES,
          "KScheduler removed from SAMPLER_NODE_TYPES",
          "still present")

    workflow = {
        "10": {"class_type": "KSamplerSelect"},
        "11": {"class_type": "KScheduler"},
        "12": {"class_type": "KSampler"},
    }
    samplers = identify_sampler_nodes(workflow)
    check(samplers == {"12": "KSampler"},
          "only the executing sampler is identified",
          "got %r" % (samplers,))


def d2_real_workflow_sampler_identification():
    print("\n--- DEFECT 2: real ArchitectOS workflow sampler identification ---")

    path = os.path.join(_PROJECT_ROOT, "core", "render", "workflows",
                        "flux_img2img.json")
    if not os.path.isfile(path):
        check(False, "flux_img2img.json present", "missing")
        return

    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)

    # Workflow files are either the bare graph or {"prompt": graph}.
    graph = raw.get("prompt", raw) if isinstance(raw, dict) else raw

    samplers = identify_sampler_nodes(graph)
    check(len(samplers) >= 1,
          "at least one executing sampler found in flux_img2img.json",
          "got %r" % (samplers,))

    for node_id, class_type in samplers.items():
        check("Sampler" in class_type or class_type in ("SamplerCustom",),
              "identified node %s is a sampler class (%s)" % (node_id, class_type))


# ==========================================================
# DEFECT 3 — TRANSPORT AND CLEANUP
# ==========================================================

def d3_ready_before_submit():
    print("\n--- DEFECT 3: listener is ready before submission ---")

    server = FakeComfyWS()
    server.start()
    try:
        lst = ComfyProgressListener(
            "ws://127.0.0.1:%d/ws?clientId=ready-test" % server.port,
            prompt_id="prompt-A",
            client_id="ready-test",
            sampler_node_ids={"10"},
        )
        ready = lst.start()
        check(ready is True, "start() reports a completed handshake",
              "returned %r" % (ready,))
        check(server.connected.is_set(), "server observed the connection")
        lst.stop()
    finally:
        server.stop()


class RawWSPeer:
    """A minimal raw-TCP WebSocket peer that records frame opcodes.

    aiohttp's SERVER-side iterator does not surface an incoming CLOSE
    frame as a message in this version, so a close handshake cannot be
    observed through it. This peer speaks the wire protocol directly and
    therefore proves exactly what the client transmitted.
    """

    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    def __init__(self):
        self.port = None
        self.opcodes = []
        self.handshake_done = threading.Event()
        self.close_seen = threading.Event()
        self._srv = None
        self._thread = None

    def start(self, timeout=10):
        self._srv = socket.socket()
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(1)
        self.port = self._srv.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self.port

    @staticmethod
    def _recv_exact(conn, n):
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def _serve(self):
        try:
            conn, _addr = self._srv.accept()
        except OSError:
            return

        try:
            conn.settimeout(10)

            request = b""
            while b"\r\n\r\n" not in request:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                request += chunk

            key = ""
            for line in request.decode("latin-1").split("\r\n"):
                if line.lower().startswith("sec-websocket-key:"):
                    key = line.split(":", 1)[1].strip()

            accept = base64.b64encode(
                hashlib.sha1((key + self.GUID).encode("ascii")).digest()
            ).decode("ascii")

            conn.sendall((
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                "Sec-WebSocket-Accept: %s\r\n"
                "\r\n" % accept
            ).encode("ascii"))

            self.handshake_done.set()

            while True:
                header = self._recv_exact(conn, 2)
                if header is None:
                    break

                b1, b2 = header[0], header[1]
                opcode = b1 & 0x0F
                masked = (b2 & 0x80) != 0
                length = b2 & 0x7F

                if length == 126:
                    ext = self._recv_exact(conn, 2)
                    if ext is None:
                        break
                    length = struct.unpack("!H", ext)[0]
                elif length == 127:
                    ext = self._recv_exact(conn, 8)
                    if ext is None:
                        break
                    length = struct.unpack("!Q", ext)[0]

                if masked:
                    if self._recv_exact(conn, 4) is None:
                        break

                if length and self._recv_exact(conn, length) is None:
                    break

                self.opcodes.append(opcode)

                if opcode == 0x8:
                    self.close_seen.set()
                    break
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def stop(self):
        try:
            if self._srv is not None:
                self._srv.close()
        except Exception:
            pass


def d3_close_frame_is_transmitted():
    print("\n--- DEFECT 3: close frame is transmitted on stop ---")

    peer = RawWSPeer()
    peer.start()
    try:
        lst = ComfyProgressListener(
            "ws://127.0.0.1:%d/ws?clientId=close-test" % peer.port,
            prompt_id="prompt-A",
            client_id="close-test",
            sampler_node_ids={"10"},
        )
        ready = lst.start()
        check(ready is True, "handshake completed against the raw peer",
              "start() returned %r" % (ready,))

        lst.stop()

        seen = peer.close_seen.wait(5)
        check(seen, "peer received a WebSocket CLOSE (opcode 0x8) frame",
              "opcodes observed: %r" % (peer.opcodes,))
        check(0x8 in peer.opcodes, "opcode 0x8 present in the frame stream",
              "opcodes observed: %r" % (peer.opcodes,))
    finally:
        peer.stop()


def d3_no_thread_left_alive_after_stop():
    print("\n--- DEFECT 3: no thread remains after stop ---")

    server = FakeComfyWS()
    server.start()
    try:
        lst = ComfyProgressListener(
            "ws://127.0.0.1:%d/ws?clientId=join-test" % server.port,
            prompt_id="prompt-A",
            client_id="join-test",
            sampler_node_ids={"10"},
        )
        lst.start()
        time.sleep(0.3)
        lst.stop()

        check(not lst.is_running(), "listener reports not running after stop",
              "is_running()=%r" % (lst.is_running(),))
    finally:
        server.stop()


def d3_message_sent_immediately_after_handshake_is_received():
    print("\n--- DEFECT 3: message coalesced with handshake is received ---")

    # ComfyUI sends a `status` frame the moment the socket opens. It can
    # arrive in the same TCP segment as the 101 response; the old parser
    # discarded those bytes.
    server = FakeComfyWS(on_connect_message={
        "type": "status",
        "data": {"status": {"exec_info": {"queue_remaining": 0}}, "sid": "x"},
    })
    server.start()
    try:
        lst = ComfyProgressListener(
            "ws://127.0.0.1:%d/ws?clientId=coalesce-test" % server.port,
            prompt_id="prompt-A",
            client_id="coalesce-test",
            sampler_node_ids={"10"},
        )
        lst.start()

        # A real progress frame must still reach the handler afterwards.
        server.push({
            "type": "progress",
            "data": {"value": 4, "max": 20, "node": "10",
                     "prompt_id": "prompt-A"},
        })

        deadline = time.time() + 5
        prog = None
        while time.time() < deadline:
            prog = lst.latest()
            if prog is not None:
                break
            time.sleep(0.05)

        check(prog is not None and prog.get("step") == 4,
              "frames after the handshake-adjacent data are processed",
              "got %r" % (prog,))
        check(lst.stats().get("events_seen", 0) >= 2,
              "both the status frame and the progress frame were seen",
              "stats=%r" % (lst.stats(),))
        lst.stop()
    finally:
        server.stop()


def d3_abnormal_disconnect_does_not_raise():
    print("\n--- DEFECT 3: abnormal disconnect never breaks the caller ---")

    server = FakeComfyWS(abrupt=True)
    server.start()
    try:
        lst = ComfyProgressListener(
            "ws://127.0.0.1:%d/ws?clientId=abrupt-test" % server.port,
            prompt_id="prompt-A",
            client_id="abrupt-test",
            sampler_node_ids={"10"},
        )
        raised = None
        try:
            lst.start()
            time.sleep(0.5)
            lst.stop()
        except Exception as exc:  # noqa: BLE001 - this is the assertion
            raised = exc

        check(raised is None, "abnormal disconnect raised nothing",
              "raised %r" % (raised,))
    finally:
        server.stop()


def d3_unreachable_endpoint_falls_back_honestly():
    print("\n--- DEFECT 3: unreachable endpoint falls back honestly ---")

    lst = ComfyProgressListener(
        "ws://127.0.0.1:9/ws?clientId=dead-test",
        prompt_id="prompt-A",
        client_id="dead-test",
        sampler_node_ids={"10"},
        connect_timeout=2,
    )
    ready = lst.start()
    check(ready is False, "start() returns False when the handshake fails",
          "returned %r" % (ready,))

    prog = lst.latest()
    check(
        prog is None or prog.get("step") is None,
        "no sampling step is invented on failure",
        "got %r" % (prog,),
    )
    lst.stop()


# ==========================================================
# DEFECT 4 — REQUEST OWNERSHIP
# ==========================================================

def d4_no_singleton_ownership_fallback():
    print("\n--- DEFECT 4: ownership is never guessed from the singleton ---")

    import inspect
    from core.render.render_runtime import RenderRuntime

    source = inspect.getsource(RenderRuntime.render)

    check(
        "current_project_id()" not in source,
        "render() does not read the process-wide project_session",
        "singleton still used as an ownership source",
    )
    check(
        "g.project_id" in source or "_flask_g" in source or "request_project_id" in source,
        "render() reads a request-scoped owner",
        "no request-scoped owner found",
    )


def d4_publication_requires_verified_owner():
    print("\n--- DEFECT 4: publication requires a verified owner ---")

    import inspect
    from core.render.render_runtime import RenderRuntime

    source = inspect.getsource(RenderRuntime.render)
    check(
        "if not _owner_project_id" in source,
        "publish path is gated on a non-empty owner",
        "no owner gate found",
    )


# ==========================================================
# DEFECT 5 — CHAT-MODE RENDER COVERAGE
# ==========================================================

def d5_watcher_not_limited_to_generation_modes():
    print("\n--- DEFECT 5: watcher is not limited to generation modes ---")

    path = os.path.join(_PROJECT_ROOT, "ui", "static", "app.js")
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()

    check(
        "mayRender = isGenerating || attachIsImage" not in source,
        "old mayRender condition removed",
        "old condition still present",
    )
    check(
        "startRenderStatusPoller" in source,
        "status poller still used",
        "poller missing",
    )
    # The watcher must be started for every in-flight chat turn, not
    # only for turns the client already classifies as a render.
    check(
        "watchRender" in source or "startRenderWatcher" in source
        or "renderWatch" in source,
        "a dedicated in-flight render watcher exists",
        "no watcher abstraction found",
    )


# ==========================================================
# MAIN
# ==========================================================

def main():
    print("=" * 66)
    print("B+ INDEPENDENT CORRECTION — DEFECT REPRODUCTION")
    print("Every test asserts CORRECT behaviour; failures prove the defect.")
    print("=" * 66)

    tests = [
        d1_progress_without_prompt_id_is_rejected,
        d1_foreign_prompt_id_is_rejected,
        d1_interrupted_without_prompt_id_is_rejected,
        d1_foreign_interrupted_cannot_terminate,
        d1_correct_prompt_id_works,
        d1_unbound_listener_accepts_nothing,
        d1_success_without_prompt_id_is_rejected,
        d2_empty_allowlist_accepts_nothing,
        d2_none_allowlist_accepts_nothing,
        d2_non_sampler_node_rejected,
        d2_non_positive_max_rejected,
        d2_step_outside_range_rejected,
        d2_select_and_schedule_classes_are_not_samplers,
        d2_real_workflow_sampler_identification,
        d3_ready_before_submit,
        d3_close_frame_is_transmitted,
        d3_no_thread_left_alive_after_stop,
        d3_message_sent_immediately_after_handshake_is_received,
        d3_abnormal_disconnect_does_not_raise,
        d3_unreachable_endpoint_falls_back_honestly,
        d4_no_singleton_ownership_fallback,
        d4_publication_requires_verified_owner,
        d5_watcher_not_limited_to_generation_modes,
    ]

    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 - report, do not abort
            global _FAIL
            _FAIL += 1
            _FAILURES.append("%s :: raised %s: %s"
                             % (test.__name__, type(exc).__name__, exc))
            print("  ERROR: %s raised %s: %s"
                  % (test.__name__, type(exc).__name__, exc))

    print("\n" + "=" * 66)
    print("RESULT: %d passed, %d failed (%d tests)"
          % (_PASS, _FAIL, len(tests)))
    if _FAILURES:
        print("\nFAILURES (these are the reproduced defects):")
        for item in _FAILURES:
            print("  - %s" % item)
    print("=" * 66)

    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
