"""ARCHITECTOS_NO_CONSOLE_WINDOW_V1 — background services must not flash consoles.

Root cause, measured 2026-10-25: Core (started DETACHED, so it has no console)
spawned

    C:\\...\\Python311\\python.exe -c "import whisper"

on every /api/voice/status poll — every ~15 s — and each spawn made Windows
allocate a NEW console window (a conhost.exe child of that python). Ten
occurrences were captured in 150 s, all parented to the Core pid.

The fix is CREATE_NO_WINDOW on every console child spawned by a service. These
tests pin the helper and, more importantly, pin that the call sites keep using
it — a missing kwarg silently reintroduces the visible window.
"""

import ast
import os
import subprocess

import pytest

from core.runtime.subprocess_no_window_v1 import (
    CREATE_NO_WINDOW,
    no_window_kwargs,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------
# the helper
# --------------------------------------------------------------------------


@pytest.mark.skipif(os.name != "nt", reason="Windows-only mechanism")
def test_no_window_kwargs_requests_a_console_free_child():
    kwargs = no_window_kwargs()

    assert kwargs["creationflags"] & CREATE_NO_WINDOW
    assert "startupinfo" in kwargs
    assert kwargs["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW
    assert kwargs["startupinfo"].wShowWindow == subprocess.SW_HIDE


def test_no_window_kwargs_is_empty_off_windows(monkeypatch):
    import core.runtime.subprocess_no_window_v1 as module

    monkeypatch.setattr(module.os, "name", "posix")

    assert module.no_window_kwargs() == {}


def test_no_window_kwargs_does_not_disturb_capture():
    """Redirection must keep working: the flag only removes the console."""
    completed = subprocess.run(
        [os.sys.executable, "-c", "print('ok')"],
        capture_output=True,
        text=True,
        **no_window_kwargs(),
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "ok"


# --------------------------------------------------------------------------
# the call sites must keep using it
# --------------------------------------------------------------------------


def _spawn_calls(path):
    """Every ``subprocess.<fn>(...)`` call in ``path``."""

    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    calls = []

    for node in ast.walk(tree):

        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if not isinstance(func, ast.Attribute):
            continue

        owner = func.value

        if not isinstance(owner, ast.Name) or owner.id != "subprocess":
            continue

        if func.attr not in ("run", "Popen", "call", "check_output", "check_call"):
            continue

        calls.append(node)

    return calls


def _passes_no_window(call):
    """True when the call splats ``**no_window_kwargs()``."""

    for keyword in call.keywords:

        if keyword.arg is not None:
            continue

        value = keyword.value

        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "no_window_kwargs"
        ):
            return True

    return False


@pytest.mark.parametrize(
    "relative",
    [
        "core/voice/voice_capability_v1.py",
        "core/voice/voice_stt_whisper_v1.py",
        "core/chat/project_code_syntax_checker_v1.py",
    ],
)
def test_every_service_spawn_is_console_free(relative):
    path = os.path.join(ROOT, relative)

    calls = _spawn_calls(path)

    assert calls, "expected at least one subprocess call in %s" % relative

    offenders = [call.lineno for call in calls if not _passes_no_window(call)]

    assert not offenders, (
        "%s spawns a console child without no_window_kwargs() at lines %s — "
        "that flashes a black window when the parent service has no console"
        % (relative, offenders)
    )


def test_voice_capability_imports_the_helper():
    path = os.path.join(ROOT, "core", "voice", "voice_capability_v1.py")

    with open(path, encoding="utf-8") as handle:
        source = handle.read()

    assert "no_window_kwargs" in source
