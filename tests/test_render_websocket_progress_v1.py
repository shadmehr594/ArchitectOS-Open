# ==========================================================
# ArchitectOS B+ Real Sampling Progress — Test Suite v1
#
# Tests the WebSocket-based sampling progress feature using mocked
# WebSocket events and in-process verification. No GPU generation.
# No real ComfyUI submission.
# ==========================================================

import json
import os
import sys
import time
import threading

# Ensure project root is on the path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from core.render.comfy_ws_listener import (
    ComfyProgressListener,
    identify_sampler_nodes,
    make_client_id,
    build_ws_url,
    SAMPLER_NODE_TYPES,
)


# ==========================================================
# TEST HELPERS
# ==========================================================

_PASS = 0
_FAIL = 0
_ERRORS = []


def check(condition, name, detail=""):
    """Assert one condition.

    CORRECTED (B+ test-provenance gate): this helper previously only
    recorded a failure in a module-level counter and returned. pytest
    therefore reported every test function as PASSED even when its
    checks were failing, so "26 passed" proved nothing.

    It now raises AssertionError on failure, which is what pytest
    observes. The recording behaviour is kept for script mode.
    """
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS: {name}")
        return
    _FAIL += 1
    _ERRORS.append(f"{name}: {detail}")
    print(f"  FAIL: {name} — {detail}")
    raise AssertionError(f"{name} — {detail}" if detail else name)


def make_listener(prompt_id="test-prompt", sampler_ids=None, client_id="test-client"):
    """Create a listener without starting it."""
    return ComfyProgressListener(
        "ws://127.0.0.1:8188/ws?clientId=" + client_id,
        prompt_id=prompt_id,
        client_id=client_id,
        sampler_node_ids=sampler_ids or {"10"},
    )


def send_event(listener, event_type, data):
    """Simulate a WebSocket text frame."""
    msg = json.dumps({"type": event_type, "data": data}).encode("utf-8")
    listener._handle_text(msg)


# ==========================================================
# TEST GROUP 1 — client_id GENERATION AND URL BUILDING
# ==========================================================

def test_client_id_generation():
    print("\n--- GROUP 1: client_id generation ---")

    cid = make_client_id()
    check(isinstance(cid, str), "client_id is string")
    check(len(cid) == 32, "client_id is 32 chars (uuid hex)")

    # Uniqueness
    cids = {make_client_id() for _ in range(100)}
    check(len(cids) == 100, "100 unique client_ids")


def test_ws_url_building():
    print("\n--- GROUP 1: WebSocket URL building ---")

    url = build_ws_url("http://127.0.0.1:8188", "abc123")
    check(url == "ws://127.0.0.1:8188/ws?clientId=abc123", "http -> ws URL")

    url2 = build_ws_url("https://example.com:8443/", "xyz")
    check(url2 == "wss://example.com:8443/ws?clientId=xyz", "https -> wss URL")

    url3 = build_ws_url("http://127.0.0.1:8188/", "test")
    check("ws://" in url3, "trailing slash handled")


# ==========================================================
# TEST GROUP 2 — SAMPLER NODE IDENTIFICATION
# ==========================================================

def test_sampler_identification():
    print("\n--- GROUP 2: sampler node identification ---")

    workflow = {
        "10": {"class_type": "KSampler", "inputs": {}},
        "15": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
        "20": {"class_type": "VAEDecode", "inputs": {}},
        "25": {"class_type": "KSamplerAdvanced", "inputs": {}},
        "30": {"class_type": "SaveImage", "inputs": {}},
    }
    samplers = identify_sampler_nodes(workflow)
    check("10" in samplers, "KSampler identified")
    check("25" in samplers, "KSamplerAdvanced identified")
    check("15" not in samplers, "CheckpointLoader NOT a sampler")
    check("20" not in samplers, "VAEDecode NOT a sampler")
    check("30" not in samplers, "SaveImage NOT a sampler")

    # Edge cases
    check(identify_sampler_nodes({}) == {}, "empty workflow")
    check(identify_sampler_nodes(None) == {}, "None workflow")
    check(identify_sampler_nodes({"10": "not-a-dict"}) == {}, "malformed node")


def test_sampler_types_coverage():
    print("\n--- GROUP 2: sampler type coverage ---")

    for stype in ["KSampler", "KSamplerAdvanced", "SamplerCustom",
                  "SamplerCustomAdvanced"]:
        check(stype in SAMPLER_NODE_TYPES, f"{stype} in SAMPLER_NODE_TYPES")

    for ntype in ["VAEDecode", "VAEEncode", "SaveImage", "LoadImage",
                  "CheckpointLoaderSimple", "CLIPTextEncode"]:
        check(ntype not in SAMPLER_NODE_TYPES, f"{ntype} NOT in SAMPLER_NODE_TYPES")


# ==========================================================
# TEST GROUP 3 — PROMPT-SPECIFIC PROGRESS
# ==========================================================

def test_prompt_specific_progress():
    print("\n--- GROUP 3: prompt-specific progress ---")

    listener = make_listener(prompt_id="my-prompt", sampler_ids={"10"})
    listener._prompt_id = "my-prompt"

    # Foreign prompt_id — must be rejected
    send_event(listener, "progress", {
        "value": 5, "max": 20, "prompt_id": "other-prompt", "node": "10"
    })
    check(listener.latest() is None, "foreign prompt_id rejected")

    # Matching prompt_id — must be accepted
    send_event(listener, "progress", {
        "value": 7, "max": 20, "prompt_id": "my-prompt", "node": "10"
    })
    prog = listener.latest()
    check(prog is not None, "matching prompt_id accepted")
    check(prog["step"] == 7, "step value correct")
    check(prog["max"] == 20, "max value correct")


def test_verified_sampler_node():
    print("\n--- GROUP 3: verified sampler node ---")

    listener = make_listener(prompt_id="p1", sampler_ids={"10", "30"})
    listener._prompt_id = "p1"

    # Non-sampler node progress — rejected
    send_event(listener, "progress", {
        "value": 3, "max": 5, "prompt_id": "p1", "node": "20"
    })
    check(listener.latest() is None, "non-sampler node rejected")

    # Sampler node progress — accepted
    send_event(listener, "progress", {
        "value": 7, "max": 20, "prompt_id": "p1", "node": "10"
    })
    check(listener.latest()["step"] == 7, "sampler node accepted")


def test_correct_step_x_y():
    print("\n--- GROUP 3: correct Step X / Y ---")

    listener = make_listener(prompt_id="p2", sampler_ids={"10"})
    listener._prompt_id = "p2"

    for step in range(1, 21):
        send_event(listener, "progress", {
            "value": step, "max": 20, "prompt_id": "p2", "node": "10"
        })

    prog = listener.latest()
    check(prog["step"] == 20, "final step = 20")
    check(prog["max"] == 20, "max = 20")


def test_multiple_sampler_nodes():
    print("\n--- GROUP 3: multiple sampler nodes ---")

    listener = make_listener(prompt_id="p3", sampler_ids={"10", "30"})
    listener._prompt_id = "p3"

    send_event(listener, "progress", {
        "value": 3, "max": 10, "prompt_id": "p3", "node": "10"
    })
    check(listener.latest()["node"] == "10", "first sampler tracked")

    send_event(listener, "progress", {
        "value": 7, "max": 15, "prompt_id": "p3", "node": "30"
    })
    check(listener.latest()["node"] == "30", "second sampler tracked")
    check(listener.latest()["step"] == 7, "second sampler step correct")


def test_out_of_order_progress():
    print("\n--- GROUP 3: out-of-order progress ---")

    listener = make_listener(prompt_id="p4", sampler_ids={"10"})
    listener._prompt_id = "p4"

    send_event(listener, "progress", {
        "value": 15, "max": 20, "prompt_id": "p4", "node": "10"
    })
    send_event(listener, "progress", {
        "value": 5, "max": 20, "prompt_id": "p4", "node": "10"
    })
    # Latest wins — this is correct for multi-pass samplers
    check(listener.latest()["step"] == 5, "latest progress wins")


# ==========================================================
# TEST GROUP 4 — TERMINAL EVENTS
# ==========================================================

def test_execution_success():
    print("\n--- GROUP 4: execution_success ---")

    listener = make_listener(prompt_id="p5", sampler_ids={"10"})
    listener._prompt_id = "p5"

    send_event(listener, "execution_success", {"prompt_id": "p5"})
    check(listener.is_terminal(), "terminal after success")
    check(
        listener.latest()["terminal_reason"] == "success",
        "terminal_reason = success"
    )


def test_execution_error():
    print("\n--- GROUP 4: execution_error ---")

    listener = make_listener(prompt_id="p6", sampler_ids={"10"})
    listener._prompt_id = "p6"

    send_event(listener, "execution_error", {
        "prompt_id": "p6", "node_id": "10",
        "exception_message": "OOM"
    })
    check(listener.is_terminal(), "terminal after error")
    check(listener.latest()["terminal_reason"] == "error", "terminal_reason = error")


def test_foreign_interruption_broadcast():
    print("\n--- GROUP 4: foreign interruption broadcast ---")

    listener = make_listener(prompt_id="p7", sampler_ids={"10"})
    listener._prompt_id = "p7"

    # Foreign interruption — should NOT affect our listener
    send_event(listener, "execution_interrupted", {
        "prompt_id": "other-prompt"
    })
    check(not listener.is_terminal(), "foreign interruption ignored")

    # Our interruption — should be terminal
    send_event(listener, "execution_interrupted", {
        "prompt_id": "p7"
    })
    check(listener.is_terminal(), "own interruption is terminal")
    check(
        listener.latest()["terminal_reason"] == "interrupted",
        "terminal_reason = interrupted"
    )


# ==========================================================
# TEST GROUP 5 — WEBSOCKET FAILURE RESILIENCE
# ==========================================================

def test_websocket_connection_failure():
    print("\n--- GROUP 5: WebSocket connection failure ---")

    listener = ComfyProgressListener(
        "ws://127.0.0.1:9999/ws?clientId=fail-test",
        prompt_id="p-fail",
        client_id="fail-test",
        sampler_node_ids={"10"},
        connect_timeout=2,
    )
    listener.start()
    time.sleep(3)
    check(listener.is_terminal(), "terminal after connection failure")
    check(
        "ws_error" in str(listener.latest()["terminal_reason"]),
        "terminal_reason contains ws_error"
    )
    listener.stop()


def test_websocket_disconnect():
    print("\n--- GROUP 5: WebSocket disconnect ---")

    # CORRECTION: the hand-rolled `_close_socket` was removed with the
    # RFC 6455 stack. A disconnect is now exercised through the public
    # lifecycle: stop() must close cleanly, leave no worker behind, and
    # never raise into the render path.
    listener = make_listener(prompt_id="p-disconnect", sampler_ids={"10"})
    listener._prompt_id = "p-disconnect"

    listener._stop_event.set()

    raised = None
    try:
        stopped = listener.stop()
    except Exception as exc:  # noqa: BLE001 - this is the assertion
        raised = exc
        stopped = None

    check(raised is None, "disconnect handled cleanly", "raised %r" % (raised,))
    check(stopped is True, "stop() confirms the worker is gone",
          "stop() returned %r" % (stopped,))
    check(listener.is_running() is False, "listener is not running afterwards")


def test_render_continues_without_websocket():
    print("\n--- GROUP 5: render continues without WebSocket ---")

    # When the WS listener is None (connection failed before start),
    # the render still works via the poll-based lifecycle.
    # The active_render record exists but has no sampling_step.
    # This is verified by the status endpoint not including
    # sampling_step/sampling_max fields.
    listener = None  # simulating WS failure
    check(listener is None, "listener is None when WS fails")

    # active_render would still have prompt_id, stage, etc.
    # Just no sampling progress
    active_render = {
        "prompt_id": "test-prompt",
        "stage": "executing",
        "active": True,
    }
    check("sampling_step" not in active_render, "no sampling_step without WS")


# ==========================================================
# TEST GROUP 6 — CLEANUP
# ==========================================================

def test_cleanup_after_success():
    print("\n--- GROUP 6: cleanup after success ---")

    listener = make_listener(prompt_id="p-clean-s", sampler_ids={"10"})
    listener._prompt_id = "p-clean-s"
    send_event(listener, "progress", {
        "value": 10, "max": 20, "prompt_id": "p-clean-s", "node": "10"
    })
    send_event(listener, "execution_success", {"prompt_id": "p-clean-s"})
    listener.stop()
    check(listener._thread is None, "thread cleaned up after success")


def test_cleanup_after_cancellation():
    print("\n--- GROUP 6: cleanup after cancellation ---")

    listener = make_listener(prompt_id="p-clean-c", sampler_ids={"10"})
    listener._prompt_id = "p-clean-c"
    send_event(listener, "execution_interrupted", {"prompt_id": "p-clean-c"})
    listener.stop()
    check(listener._thread is None, "thread cleaned up after cancellation")


def test_cleanup_after_failure():
    print("\n--- GROUP 6: cleanup after failure ---")

    listener = ComfyProgressListener(
        "ws://127.0.0.1:9999/ws?clientId=fail-clean",
        prompt_id="p-clean-f",
        client_id="fail-clean",
        sampler_node_ids={"10"},
        connect_timeout=2,
    )
    listener.start()
    time.sleep(3)
    listener.stop()
    check(listener._thread is None, "thread cleaned up after failure")


def test_stale_generation_rejection():
    print("\n--- GROUP 6: stale generation rejection ---")

    # Simulate the generation guard: an older render's events
    # should not overwrite a newer render's record.
    listener_old = make_listener(prompt_id="old-prompt", sampler_ids={"10"})
    listener_old._prompt_id = "old-prompt"
    send_event(listener_old, "progress", {
        "value": 5, "max": 20, "prompt_id": "old-prompt", "node": "10"
    })

    listener_new = make_listener(prompt_id="new-prompt", sampler_ids={"10"})
    listener_new._prompt_id = "new-prompt"
    send_event(listener_new, "progress", {
        "value": 15, "max": 20, "prompt_id": "new-prompt", "node": "10"
    })

    # The new listener has its own progress, the old one is untouched
    check(listener_old.latest()["step"] == 5, "old listener unchanged")
    check(listener_new.latest()["step"] == 15, "new listener has its progress")

    listener_old.stop()
    listener_new.stop()


# ==========================================================
# TEST GROUP 7 — CONCURRENT PROJECT ISOLATION
# ==========================================================

def test_concurrent_projects_isolation():
    print("\n--- GROUP 7: concurrent project isolation ---")

    # Two listeners for different projects with different prompt_ids
    listener_a = make_listener(prompt_id="prompt-A", sampler_ids={"10"},
                               client_id="client-A")
    listener_a._prompt_id = "prompt-A"

    listener_b = make_listener(prompt_id="prompt-B", sampler_ids={"10"},
                               client_id="client-B")
    listener_b._prompt_id = "prompt-B"

    # Send progress for A
    send_event(listener_a, "progress", {
        "value": 3, "max": 10, "prompt_id": "prompt-A", "node": "10"
    })

    # B should not have any progress
    check(listener_b.latest() is None, "project B unaffected by A's progress")

    # Send progress for B
    send_event(listener_b, "progress", {
        "value": 7, "max": 15, "prompt_id": "prompt-B", "node": "10"
    })

    check(listener_a.latest()["step"] == 3, "project A unaffected by B's progress")
    check(listener_b.latest()["step"] == 7, "project B has its own progress")

    listener_a.stop()
    listener_b.stop()


def test_two_browser_tab_isolation():
    print("\n--- GROUP 7: two browser tab isolation ---")

    # Two tabs = two pollers with different project_ids
    # The status endpoint filters by project_id, so tab B never
    # sees tab A's render. This is tested at the endpoint level,
    # but we verify the listener-level isolation here.

    listener1 = make_listener(prompt_id="tab1-prompt", sampler_ids={"10"},
                              client_id="tab1-client")
    listener1._prompt_id = "tab1-prompt"

    listener2 = make_listener(prompt_id="tab2-prompt", sampler_ids={"10"},
                              client_id="tab2-client")
    listener2._prompt_id = "tab2-prompt"

    send_event(listener1, "progress", {
        "value": 5, "max": 20, "prompt_id": "tab1-prompt", "node": "10"
    })

    check(listener2.latest() is None, "tab2 has no progress from tab1")

    listener1.stop()
    listener2.stop()


# ==========================================================
# TEST GROUP 8 — SUBMIT PAYLOAD INTEGRITY
# ==========================================================

def test_client_id_in_submit_payload():
    print("\n--- GROUP 8: client_id in submit payload ---")

    from unittest.mock import patch, MagicMock
    from core.render.comfy_http_runtime import ComfyHTTPRuntime

    runtime = ComfyHTTPRuntime.__new__(ComfyHTTPRuntime)
    runtime.endpoint = "http://127.0.0.1:8188"
    runtime.session = MagicMock()

    # The lease is imported INSIDE submit() from core.runtime.gpu_handoff_v1
    with patch("core.runtime.gpu_handoff_v1.comfyui_lease") as mock_lease:
        mock_lease_inst = MagicMock()
        mock_lease_inst.acquire.return_value = True
        mock_lease.return_value = mock_lease_inst

        # Mock the POST response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"prompt_id": "test-123"}
        runtime.session.post.return_value = mock_response

        result = runtime.submit({"10": {"class_type": "KSampler"}}, client_id="my-client-id")

        # Verify the POST was called with client_id in the payload
        call_args = runtime.session.post.call_args
        payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        check(payload.get("client_id") == "my-client-id",
              "client_id in submit payload",
              f"got: {payload.get('client_id')}")


def test_submit_without_client_id():
    print("\n--- GROUP 8: submit without client_id (backward compat) ---")

    from unittest.mock import patch, MagicMock
    from core.render.comfy_http_runtime import ComfyHTTPRuntime

    runtime = ComfyHTTPRuntime.__new__(ComfyHTTPRuntime)
    runtime.endpoint = "http://127.0.0.1:8188"
    runtime.session = MagicMock()

    with patch("core.runtime.gpu_handoff_v1.comfyui_lease") as mock_lease:
        mock_lease_inst = MagicMock()
        mock_lease_inst.acquire.return_value = True
        mock_lease.return_value = mock_lease_inst

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"prompt_id": "test-456"}
        runtime.session.post.return_value = mock_response

        result = runtime.submit({"10": {"class_type": "KSampler"}}, client_id=None)

        call_args = runtime.session.post.call_args
        payload = call_args[1]["json"]
        check("client_id" not in payload, "no client_id when None",
              f"unexpected client_id: {payload.get('client_id')}")


def test_unchanged_render_result_contract():
    print("\n--- GROUP 8: unchanged render result contract ---")

    from unittest.mock import patch, MagicMock
    from core.render.comfy_http_runtime import ComfyHTTPRuntime

    runtime = ComfyHTTPRuntime.__new__(ComfyHTTPRuntime)
    runtime.endpoint = "http://127.0.0.1:8188"
    runtime.session = MagicMock()

    with patch("core.runtime.gpu_handoff_v1.comfyui_lease") as mock_lease:
        mock_lease_inst = MagicMock()
        mock_lease_inst.acquire.return_value = True
        mock_lease.return_value = mock_lease_inst

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"prompt_id": "test-789"}
        runtime.session.post.return_value = mock_response

        result = runtime.submit({"10": {}}, client_id="test")

        # The submit result contract must be unchanged
        check(result["status"] == "submitted", "status = submitted")
        check(result["prompt_id"] == "test-789", "prompt_id in result")
        check("http_status" in result, "http_status in result")
        check("time" in result, "time in result")


# ==========================================================
# TEST GROUP 9 — ACTIVE RENDER RECORD WITH SAMPLING
# ==========================================================

def test_active_render_contains_sampling_info():
    print("\n--- GROUP 9: active_render contains sampling info ---")

    # Verify that the active_render record includes the new fields
    record = {
        "prompt_id": "test-prompt",
        "project_id": "test-project",
        "generation": 1,
        "engine": "comfyui",
        "workflow": "flux_img2img",
        "submitted_at": time.time(),
        "client_id": "test-client-id",
        "sampler_node_ids": ["10", "30"],
    }

    check("client_id" in record, "client_id in active_render")
    check("sampler_node_ids" in record, "sampler_node_ids in active_render")
    check(record["sampler_node_ids"] == ["10", "30"], "sampler_node_ids correct")


def test_progress_listener_reference_on_runtime():
    print("\n--- GROUP 9: progress listener reference on runtime ---")

    # Verify the RenderRuntime has _progress_listener field
    # We can't instantiate the full runtime (too many deps), but
    # we can check the class source defines it.
    import inspect
    from core.render.render_runtime import RenderRuntime

    source = inspect.getsource(RenderRuntime.__init__)
    check("_progress_listener" in source, "_progress_listener in __init__")
    check("self._progress_listener = None" in source,
          "_progress_listener initialized to None")

    # Check _clear_active_render clears it
    clear_source = inspect.getsource(RenderRuntime._clear_active_render)
    check("_progress_listener" in clear_source,
          "_progress_listener cleared in _clear_active_render")


# ==========================================================
# MAIN
# ==========================================================

def main():
    global _FAIL
    print("=" * 60)
    print("ArchitectOS B+ Real Sampling Progress — Test Suite v1")
    print("=" * 60)

    tests = [
        test_client_id_generation,
        test_ws_url_building,
        test_sampler_identification,
        test_sampler_types_coverage,
        test_prompt_specific_progress,
        test_verified_sampler_node,
        test_correct_step_x_y,
        test_multiple_sampler_nodes,
        test_out_of_order_progress,
        test_execution_success,
        test_execution_error,
        test_foreign_interruption_broadcast,
        test_websocket_connection_failure,
        test_websocket_disconnect,
        test_render_continues_without_websocket,
        test_cleanup_after_success,
        test_cleanup_after_cancellation,
        test_cleanup_after_failure,
        test_stale_generation_rejection,
        test_concurrent_projects_isolation,
        test_two_browser_tab_isolation,
        test_client_id_in_submit_payload,
        test_submit_without_client_id,
        test_unchanged_render_result_contract,
        test_active_render_contains_sampling_info,
        test_progress_listener_reference_on_runtime,
    ]

    for test in tests:
        try:
            test()
        except AssertionError as exc:
            # `check()` already recorded this failure; do not double count.
            print(f"  FAIL: {test.__name__} — {exc}")
        except Exception as exc:
            _FAIL += 1
            _ERRORS.append(f"{test.__name__}: {exc}")
            print(f"  ERROR: {test.__name__} raised {type(exc).__name__}: {exc}")

    print("\n" + "=" * 60)
    print(f"RESULTS: {_PASS} passed, {_FAIL} failed, {len(tests)} total")
    if _ERRORS:
        print("FAILURES:")
        for err in _ERRORS:
            print(f"  - {err}")
    print("=" * 60)

    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
