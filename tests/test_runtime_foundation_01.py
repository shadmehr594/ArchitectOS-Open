# ==========================================================
# ArchitectOS RUNTIME FOUNDATION 01 - Contract Tests
#
# Covers:
#   1. single runtime config source
#   2. preflight structure + truthful reporting
#   3. stale ComfyUI config references removed
#   4. FAILURE-PATH RENDER: a failed ComfyUI run / workflow /
#      output must NEVER be reported as status="success"
#
# NO REAL IMAGE GENERATION IS PERFORMED.
# ==========================================================


import os
import sys


ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if ROOT not in sys.path:

    sys.path.insert(
        0,
        ROOT
    )


from config import runtime_config as RC
from config import comfy_config as CC

from core.runtime.runtime_preflight import run_preflight

from core.render.render_runtime import RenderRuntime
from core.render.comfy_http_runtime import ComfyHTTPRuntime



PASS = []



def ok(label):

    PASS.append(label)

    print("  [ OK ] " + label)



# ==========================================================
# 1. RUNTIME CONFIG = SINGLE SOURCE OF TRUTH
# ==========================================================

def test_runtime_config_values():

    print("\n[1] Runtime config single source")

    assert RC.CORE_API_URL == "http://127.0.0.1:5000", RC.CORE_API_URL
    assert RC.CORE_API_PORT == 5000

    assert RC.UI_URL == "http://127.0.0.1:3000", RC.UI_URL
    assert RC.UI_PORT == 3000

    assert RC.COMFYUI_URL == "http://127.0.0.1:8188", RC.COMFYUI_URL
    assert RC.COMFYUI_PORT == 8188

    assert RC.COMFYUI_ROOT.replace("\\", "/") == "C:/ComfyUI-Zluda", RC.COMFYUI_ROOT

    assert RC.OLLAMA_URL == "http://127.0.0.1:11434", RC.OLLAMA_URL
    assert RC.OLLAMA_PORT == 11434

    ok("core api / ui / comfyui / ollama values match the runtime spec")


def test_comfy_config_shim():

    print("\n[2] comfy_config compat shim")

    # public names preserved
    assert hasattr(CC, "COMFY_URL")
    assert hasattr(CC, "WORKFLOW_PATH")
    assert hasattr(CC, "OUTPUT_DIR")

    assert CC.COMFY_URL == RC.COMFYUI_URL

    # stale "C:/ComfyUI/output/" must be gone
    assert "C:/ComfyUI/" not in CC.OUTPUT_DIR.replace("\\", "/"), CC.OUTPUT_DIR
    assert CC.OUTPUT_DIR.replace("\\", "/").startswith(
        "C:/ComfyUI-Zluda/"
    ), CC.OUTPUT_DIR

    # stale "workflows/comfy/flux.json" must be gone
    assert "workflows/comfy" not in CC.WORKFLOW_PATH.replace("\\", "/")
    assert os.path.isfile(CC.WORKFLOW_PATH), CC.WORKFLOW_PATH

    ok("stale C:/ComfyUI and workflows/comfy references removed")


def test_required_workflow_files_exist():

    print("\n[3] Required workflow files")

    for name, path in RC.required_workflow_paths().items():

        assert os.path.isfile(path), "missing workflow: " + path

    ok(
        str(len(RC.REQUIRED_WORKFLOW_FILES))
        + " required workflow files present"
    )



# ==========================================================
# 4. PREFLIGHT
# ==========================================================

def test_preflight_structure():

    print("\n[4] Preflight structure")

    result = run_preflight()

    for key in (
        "CORE_API",
        "UI",
        "COMFYUI",
        "OLLAMA",
    ):

        assert key in result["services"], key

        service = result["services"][key]

        assert "ok" in service

        assert "reachable" in service

        assert "url" in service

    for key in (
        "WORKFLOWS",
        "COMFY_PATHS",
    ):

        assert key in result["files"], key

    assert "blockers" in result

    assert "external_degraded" in result

    assert "chat_ready" in result

    assert "render_ready" in result

    ok("preflight reports CORE_API / UI / COMFYUI / OLLAMA + workflows + comfy paths")

    return result


def test_preflight_detects_external_services():

    print("\n[5] Preflight detects externally managed services")

    result = run_preflight()

    comfy = result["services"]["COMFYUI"]

    ollama = result["services"]["OLLAMA"]

    assert comfy["managed_by"] == "external"
    assert ollama["managed_by"] == "external"

    if comfy["ok"]:

        ok("ComfyUI detected on " + comfy["url"])

    else:

        print("  [WARN] ComfyUI not reachable: " + str(comfy["error"]))

    if ollama["ok"]:

        ok("Ollama detected on " + ollama["url"])

    else:

        print("  [WARN] Ollama not reachable: " + str(ollama["error"]))

    # external services must never be reported as blockers of Chat
    for blocker in result["blockers"]:

        assert "COMFYUI" not in blocker, blocker

        assert "OLLAMA" not in blocker, blocker

    ok("external services are detected, never auto-started, never hard blockers")



# ==========================================================
# 6. TRUTHFUL STATUS HELPER (positive control)
# ==========================================================

def test_status_helper_positive_control():

    print("\n[6] Status helper positive control")

    runtime = RenderRuntime()

    # completed execution + real output asset  -> success
    assert runtime._resolve_render_status(
        {"status": "completed"},
        {"status": "success", "image_asset": {"filename": "a.png"}}
    ) == "success"

    # completed execution + video output -> success
    assert runtime._resolve_render_status(
        {"status": "completed", "videos": [{"filename": "a.mp4"}]},
        {}
    ) == "success"

    # completed execution but NO output -> not success
    assert runtime._resolve_render_status(
        {"status": "completed"},
        {"status": "completed_no_image"}
    ) == "completed_no_image"

    # failed executions keep their real reason
    for status in (
        "execution_error",
        "timeout",
        "submit_error",
        "missing_prompt_id",
        "unknown_engine",
    ):

        assert runtime._resolve_render_status(
            {"status": status},
            {}
        ) == status

    ok("success requires completed execution AND a real output asset")



# ==========================================================
# 7. FAILURE-PATH RENDER (the core requirement)
# ==========================================================

class StubComfy:
    """Deterministic ComfyUI stand-in. No network, no generation."""

    def __init__(
        self,
        submit_result,
        wait_result=None,
        history_result=None
    ):

        self.submit_result = submit_result

        self.wait_result = wait_result

        self.history_result = history_result or {}


    def submit(self, workflow):

        return self.submit_result


    def wait_for_result(self, prompt_id):

        return self.wait_result


    def history(self, prompt_id):

        return self.history_result


DESIGN = {
    "prompt": "modern villa architectural visualization, glass facade",
}


def _render_with(runtime, comfy):

    runtime.executor.comfy = comfy

    runtime.result_bridge.comfy = comfy

    return runtime.render(
        "runtime_foundation_01_test",
        dict(DESIGN),
        engine="flux"
    )


def test_failure_path_unreachable_comfyui():

    print("\n[7] FAILURE PATH - ComfyUI unreachable (real connection refusal)")

    runtime = RenderRuntime()

    # port 9 = discard: guaranteed connection refusal, no real render
    dead = ComfyHTTPRuntime(
        endpoint="http://127.0.0.1:9"
    )

    result = _render_with(
        runtime,
        dead
    )

    print("  status =", result.get("status"))

    assert result.get("status") != "success", (
        "FALSE SUCCESS: unreachable ComfyUI reported as success"
    )

    assert result.get("status") in (
        "submit_error",
        "missing_prompt_id",
        "execution_unknown",
    ), result.get("status")

    ok(
        "unreachable ComfyUI reported as '"
        + str(result.get("status"))
        + "' (NOT success)"
    )


def test_failure_path_execution_error():

    print("\n[8] FAILURE PATH - ComfyUI execution_error")

    runtime = RenderRuntime()

    stub = StubComfy(
        submit_result={"status": "submitted", "prompt_id": "FAIL_001"},
        wait_result={
            "status": "execution_error",
            "prompt_id": "FAIL_001",
            "error": ["execution_error", {"node": "3"}],
        },
    )

    result = _render_with(
        runtime,
        stub
    )

    print("  status =", result.get("status"))

    assert result.get("status") == "execution_error", result.get("status")

    ok("execution_error reported as 'execution_error' (NOT success)")


def test_failure_path_rejected_submit():

    print("\n[9] FAILURE PATH - ComfyUI rejected the workflow")

    runtime = RenderRuntime()

    stub = StubComfy(
        submit_result={
            "status": "rejected",
            "http_status": 400,
            "message": "invalid prompt",
            "prompt_id": None,
        }
    )

    result = _render_with(
        runtime,
        stub
    )

    print("  status =", result.get("status"))

    assert result.get("status") == "submit_error", result.get("status")

    ok("rejected workflow reported as 'submit_error' (NOT success)")


def test_failure_path_completed_without_output():

    print("\n[10] FAILURE PATH - completed but NO output generated")

    runtime = RenderRuntime()

    # keep the history fallback fast for the test
    runtime.result_bridge.retry_count = 0

    stub = StubComfy(
        submit_result={"status": "submitted", "prompt_id": "EMPTY_001"},
        wait_result={"status": "completed", "prompt_id": "EMPTY_001"},
        history_result={},
    )

    result = _render_with(
        runtime,
        stub
    )

    print("  status =", result.get("status"))

    assert result.get("status") != "success", (
        "FALSE SUCCESS: completed run with no output reported as success"
    )

    assert result.get("status") == "completed_no_image", result.get("status")

    ok("completed-without-output reported as 'completed_no_image' (NOT success)")


def test_no_hardcoded_success_literal():

    print("\n[11] RenderRuntime.render status is DERIVED, not hardcoded")

    import ast

    source_path = os.path.join(
        ROOT,
        "core",
        "render",
        "render_runtime.py"
    )

    with open(
        source_path,
        "r",
        encoding="utf-8"
    ) as f:

        source = f.read()

    tree = ast.parse(
        source
    )

    render_fn = None

    for node in ast.walk(
        tree
    ):

        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "render"
        ):

            render_fn = node

            break

    assert render_fn is not None, "render() not found"

    # only the final response is returned at the top level of render()
    top_level_returns = [
        node
        for node in render_fn.body
        if isinstance(node, ast.Return)
    ]

    assert len(top_level_returns) == 1, (
        "expected exactly one top-level return in render(), got "
        + str(len(top_level_returns))
    )

    final = top_level_returns[0]

    assert isinstance(final.value, ast.Dict), (
        "final response is not a dict literal"
    )

    status_value = None

    for key, value in zip(
        final.value.keys,
        final.value.values
    ):

        if (
            isinstance(key, ast.Constant)
            and key.value == "status"
        ):

            status_value = value

    assert status_value is not None, "no 'status' key in final response"

    assert (
        isinstance(status_value, ast.Name)
        and status_value.id == "render_status"
    ), (
        "final render status is not derived from render_status: "
        + ast.dump(status_value)
    )

    ok('render() returns status=render_status (derived), not a "success" literal')



# ==========================================================
# RUNNER
# ==========================================================

def run_all():

    print("=" * 62)
    print("  ARCHITECTOS RUNTIME FOUNDATION 01 - TESTS")
    print("=" * 62)

    test_runtime_config_values()

    test_comfy_config_shim()

    test_required_workflow_files_exist()

    test_preflight_structure()

    test_preflight_detects_external_services()

    test_status_helper_positive_control()

    test_failure_path_unreachable_comfyui()

    test_failure_path_execution_error()

    test_failure_path_rejected_submit()

    test_failure_path_completed_without_output()

    test_no_hardcoded_success_literal()

    print("\n" + "=" * 62)
    print("  " + str(len(PASS)) + " CHECKS PASSED")
    print("  RESULT: RUNTIME_FOUNDATION_01_TESTS_PASS")
    print("=" * 62)

    return 0



if __name__ == "__main__":

    sys.exit(
        run_all()
    )
