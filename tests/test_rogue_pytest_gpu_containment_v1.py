import ast
import importlib.util
import socket
import sys
import types
from pathlib import Path


MODULE_PATH = Path(__file__).parent / "archive" / "test_render_img2img_debug.py"


def test_archive_debug_import_and_unauthorized_main_are_gpu_inert(monkeypatch):
    events = []

    class FailFastRenderRuntime:
        def __init__(self, *args, **kwargs):
            events.append("RenderRuntime constructed")
            raise AssertionError("RenderRuntime must not be constructed")

    fake_runtime_module = types.ModuleType("core.render.render_runtime")
    fake_runtime_module.RenderRuntime = FailFastRenderRuntime
    monkeypatch.setitem(
        sys.modules, "core.render.render_runtime", fake_runtime_module
    )

    def fail_network(*args, **kwargs):
        events.append("network attempted")
        raise AssertionError("No ComfyUI or model-service request is permitted")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket.socket, "connect", fail_network)
    monkeypatch.delenv("ARCHITECTOS_LIVE_DEBUG_GPU_AUTHORIZATION", raising=False)

    spec = importlib.util.spec_from_file_location(
        "archive_img2img_debug_import_safety_v1", MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert events == []
    outcome = module.main()
    assert outcome == {
        "status": "blocked",
        "reason": "live_debug_gpu_authorization_required",
        "runtime_initialized": False,
        "render_submitted": False,
    }
    assert events == []


def test_runtime_import_and_render_call_exist_only_inside_main():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))

    top_level_runtime_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "core.render.render_runtime"
    ]
    top_level_render_calls = [
        node
        for statement in tree.body
        for node in ast.walk(statement)
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
        and isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "render"
    ]

    assert top_level_runtime_imports == []
    assert top_level_render_calls == []

    main = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    executable_body = [
        node
        for node in main.body
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    ]
    guard = executable_body[0]
    assert isinstance(guard, ast.If)
    assert any(isinstance(node, ast.Return) for node in ast.walk(guard))
    runtime_import_index = next(
        index
        for index, node in enumerate(executable_body)
        if isinstance(node, ast.ImportFrom)
        and node.module == "core.render.render_runtime"
    )
    assert runtime_import_index > 0
