"""ARCHITECTOS_LAUNCHER_PERSISTENCE_V1 — launcher process-ownership tests.

These pin the two defects that made the double-click entry point unreliable:

1. The project venv's ``python.exe`` is a DELEGATING launcher: it re-executes
   the base interpreter as a child with the same argv (measured: 45640 -> 26548,
   and killing 45640 killed 26548). So the pid the launcher recorded was a shim,
   not the server — observed pid files held 14248/43260 while ports 5000/3000
   were held by 43108/11100.
2. ``stop_services`` trusted those pid files and called ``taskkill /T /F``
   blindly.

No service is started and no process is terminated here: every OS-facing
helper is monkeypatched.
"""

import os

import pytest

import launcher


class _Completed:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


# --------------------------------------------------------------------------
# port / interpreter resolution
# --------------------------------------------------------------------------


def test_url_port_resolves_the_configured_ports():
    assert launcher._url_port(launcher.RC.CORE_API_URL) == 5000
    assert launcher._url_port(launcher.RC.UI_URL) == 3000


def test_url_port_defaults_are_sane():
    assert launcher._url_port("http://127.0.0.1") == 80
    assert launcher._url_port("https://example.invalid") == 443
    assert launcher._url_port(None) == 80


def test_listening_pid_is_none_for_an_unused_port():
    # 5999 is not an ArchitectOS port and is not bound in this environment.
    assert launcher._listening_pid(5999) is None


def test_real_interpreter_unwraps_the_venv_launcher():
    venv_python = os.path.join(launcher.ROOT, ".venv", "Scripts", "python.exe")
    if not os.path.isfile(venv_python):
        pytest.skip("project venv interpreter not present")

    real = launcher._real_interpreter(venv_python)

    assert real, "a venv with pyvenv.cfg must resolve to its base interpreter"
    assert os.path.normcase(real) != os.path.normcase(venv_python)
    assert os.path.isfile(real)


def test_real_interpreter_returns_none_outside_a_venv():
    assert launcher._real_interpreter(os.path.join(launcher.ROOT, "launcher.py")) is None
    assert launcher._real_interpreter("") is None


def test_service_interpreter_adds_venv_site_packages_and_root():
    venv_python = os.path.join(launcher.ROOT, ".venv", "Scripts", "python.exe")
    if not os.path.isfile(venv_python):
        pytest.skip("project venv interpreter not present")

    interpreter, pythonpath = launcher.service_interpreter(venv_python)

    assert interpreter != venv_python
    assert pythonpath
    parts = pythonpath.split(os.pathsep)
    assert any(part.endswith("site-packages") for part in parts)
    assert launcher.ROOT in parts


def test_service_interpreter_falls_back_unchanged(monkeypatch):
    monkeypatch.setattr(launcher, "_real_interpreter", lambda p: None)

    interpreter, pythonpath = launcher.service_interpreter("C:/nowhere/python.exe")

    assert interpreter == "C:/nowhere/python.exe"
    assert pythonpath is None


def test_localhost_env_carries_secrets_and_pythonpath(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "C:/already/there")

    env = launcher.localhost_env("C:/site-packages" + os.pathsep + "C:/site-packages")

    assert env["ARCHITECTOS_LOCAL_PROXY_SECRET"] == launcher._LOCAL_PROXY_SECRET
    assert env["ARCHITECTOS_LOCAL_BOOTSTRAP_TOKEN"] == launcher._LOCAL_BOOTSTRAP_TOKEN
    parts = env["PYTHONPATH"].split(os.pathsep)
    assert parts[0] == "C:/already/there"
    assert parts.count("C:/site-packages") == 1, "duplicates must collapse"
    assert "NO_PROXY" in env


def test_localhost_env_without_pythonpath_does_not_invent_one(monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)

    env = launcher.localhost_env()

    assert "PYTHONPATH" not in env


# --------------------------------------------------------------------------
# pid recording
# --------------------------------------------------------------------------


def test_record_service_pid_prefers_the_socket_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "_listening_pid", lambda port: 4242)

    chosen = launcher._record_service_pid("CORE_API", "http://127.0.0.1:5000", spawned_pid=111)

    assert chosen == 4242
    with open(launcher._pid_path("CORE_API"), encoding="utf-8") as handle:
        assert handle.read().strip() == "4242"


def test_record_service_pid_falls_back_to_the_spawned_pid(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "_listening_pid", lambda port: None)

    chosen = launcher._record_service_pid("UI", "http://127.0.0.1:3000", spawned_pid=777)

    assert chosen == 777
    with open(launcher._pid_path("UI"), encoding="utf-8") as handle:
        assert handle.read().strip() == "777"


# --------------------------------------------------------------------------
# safe shutdown
# --------------------------------------------------------------------------


def _forbid_taskkill(monkeypatch):
    """Replace launcher's subprocess REFERENCE, not the shared module.

    Patching ``launcher.subprocess.run`` mutates the global ``subprocess``
    module and captures unrelated calls (pytest's own, for example).
    """
    calls = []

    class _FakeSubprocess:
        DEVNULL = -3
        DETACHED_PROCESS = 0
        CREATE_NEW_PROCESS_GROUP = 0
        CREATE_BREAKAWAY_FROM_JOB = 0

        def run(self, args, **kwargs):
            calls.append(list(args))
            return _Completed(0)

        def Popen(self, *args, **kwargs):
            raise AssertionError("stop_services must not spawn processes")

    monkeypatch.setattr(launcher, "subprocess", _FakeSubprocess())
    return calls


def test_stop_does_nothing_when_the_port_is_not_listening(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "_listening_pid", lambda port: None)
    calls = _forbid_taskkill(monkeypatch)

    with open(launcher._pid_path("CORE_API"), "w", encoding="utf-8") as handle:
        handle.write("999999")

    assert launcher.stop_services() == 0
    assert calls == [], "a stale pid file must never reach taskkill"
    assert not os.path.isfile(launcher._pid_path("CORE_API")), "stale pid removed"


def test_stop_refuses_an_unverified_process(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "_listening_pid", lambda port: 1234)
    monkeypatch.setattr(
        launcher, "_verify_service_identity",
        lambda name, pid: (False, "command line does not run 'app.py'"),
    )
    calls = _forbid_taskkill(monkeypatch)

    launcher.stop_services()

    assert calls == [], "an unverified process must never be terminated"


def test_stop_uses_the_socket_owner_not_the_pid_file(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "_listening_pid", lambda port: 4321)
    monkeypatch.setattr(
        launcher, "_verify_service_identity", lambda name, pid: (True, "verified")
    )
    calls = _forbid_taskkill(monkeypatch)

    with open(launcher._pid_path("CORE_API"), "w", encoding="utf-8") as handle:
        handle.write("1111")

    launcher.stop_services()

    killed = [c for c in calls if c and c[0] == "taskkill"]
    assert killed, "the verified socket owner must be stopped"
    assert str(4321) in killed[0]
    assert "1111" not in killed[0], "the stale pid file must not be obeyed"
    assert "/T" not in killed[0], "no tree kill: it killed the real server"


def test_stop_never_uses_a_tree_kill(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "_listening_pid", lambda port: 5555)
    monkeypatch.setattr(
        launcher, "_verify_service_identity", lambda name, pid: (True, "verified")
    )
    calls = _forbid_taskkill(monkeypatch)

    launcher.stop_services()

    for call in calls:
        assert "/T" not in call


# --------------------------------------------------------------------------
# identity: owning the port with a python.exe image is NOT proof
# --------------------------------------------------------------------------

RECENT = 1792947000  # a plausible 2026 creation time


def _identity(monkeypatch, exe, cmdline, created=RECENT, allowed=None):
    monkeypatch.setattr(
        launcher, "_process_identity", lambda pid: (exe, cmdline, created)
    )
    monkeypatch.setattr(
        launcher,
        "_allowed_interpreters",
        lambda: allowed if allowed is not None else {os.path.normcase(exe)},
    )


def test_identity_accepts_the_real_service_shape(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    _identity(monkeypatch, "C:/py/python.exe", '"C:/py/python.exe" app.py')

    ok, detail = launcher._verify_service_identity("CORE_API", 100)

    assert ok, detail


def test_identity_rejects_a_foreign_interpreter(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    _identity(
        monkeypatch,
        "C:/Ollama/ollama.exe",
        "ollama serve",
        allowed={"c:\\some\\other\\python.exe"},
    )

    ok, detail = launcher._verify_service_identity("CORE_API", 100)

    assert not ok
    assert "not a project interpreter" in detail


def test_identity_rejects_a_wrong_entry_point(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    _identity(monkeypatch, "C:/py/python.exe", '"C:/py/python.exe" something_else.py')

    ok, detail = launcher._verify_service_identity("CORE_API", 100)

    assert not ok
    assert "does not run 'app.py'" in detail


def test_identity_rejects_core_claiming_the_ui_entry_point(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    _identity(monkeypatch, "C:/py/python.exe", '"C:/py/python.exe" ui/app.py')

    ok, detail = launcher._verify_service_identity("CORE_API", 100)

    assert not ok, "ui/app.py must never satisfy the Core entry point"


def test_identity_fails_closed_when_the_process_is_unreadable(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "_process_identity", lambda pid: None)

    ok, detail = launcher._verify_service_identity("CORE_API", 100)

    assert not ok
    assert "could not be established" in detail


def test_identity_rejects_an_implausible_creation_time(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    _identity(monkeypatch, "C:/py/python.exe", '"C:/py/python.exe" app.py', created=1)

    ok, detail = launcher._verify_service_identity("CORE_API", 100)

    assert not ok
    assert "implausible creation time" in detail


def test_identity_rejects_a_recycled_pid(monkeypatch, tmp_path):
    """Same pid number, different process lifetime -> refuse."""
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    _identity(monkeypatch, "C:/py/python.exe", '"C:/py/python.exe" app.py')

    with open(launcher._owner_path("CORE_API"), "w", encoding="utf-8") as handle:
        handle.write('{"pid": 100, "created": %d}' % (RECENT - 5000))

    ok, detail = launcher._verify_service_identity("CORE_API", 100)

    assert not ok
    assert "recycled" in detail


def test_identity_rejects_a_mismatched_recorded_pid(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    _identity(monkeypatch, "C:/py/python.exe", '"C:/py/python.exe" app.py')

    with open(launcher._owner_path("CORE_API"), "w", encoding="utf-8") as handle:
        handle.write('{"pid": 999, "created": %d}' % RECENT)

    ok, detail = launcher._verify_service_identity("CORE_API", 100)

    assert not ok
    assert "recorded owner" in detail


def test_unrelated_python_on_port_5000_is_never_killed(tmp_path, monkeypatch):
    """The exact scenario: a foreign python.exe happens to own the port."""
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "_listening_pid", lambda port: 7777)
    _identity(monkeypatch, "C:/py/python.exe", '"C:/py/python.exe" my_own_script.py')
    calls = _forbid_taskkill(monkeypatch)

    launcher.stop_services()

    assert calls == [], "a foreign python on the ArchitectOS port must survive"


def test_cmdline_entry_matching_is_exact():
    match = launcher._cmdline_matches_entry

    assert match('"C:/py/python.exe" app.py', "app.py")
    assert match('"C:/py/python.exe" ui/app.py', "ui/app.py")
    assert not match('"C:/py/python.exe" ui/app.py', "app.py")
    assert not match('"C:/py/python.exe" app.py', "ui/app.py")
    assert not match("", "app.py")


def test_owner_sidecar_is_written_and_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "_listening_pid", lambda port: 4321)
    monkeypatch.setattr(
        launcher, "_process_identity", lambda pid: ("C:/py/python.exe", "x", RECENT)
    )
    monkeypatch.setattr(
        launcher, "_verify_service_identity", lambda name, pid: (True, "verified")
    )
    _forbid_taskkill(monkeypatch)

    launcher._record_service_pid("CORE_API", "http://127.0.0.1:5000")

    assert os.path.isfile(launcher._owner_path("CORE_API"))

    launcher.stop_services()

    assert not os.path.isfile(launcher._owner_path("CORE_API"))


# --------------------------------------------------------------------------
# bootstrap token exposure
# --------------------------------------------------------------------------


def test_trusted_ui_url_requires_a_freshly_started_stack():
    token = "t" * 64

    assert launcher.trusted_ui_url("http://127.0.0.1:3000", token, False) is None
    assert launcher.trusted_ui_url("http://127.0.0.1:3000", "short", True) is None
    assert launcher.trusted_ui_url("", token, True) is None


def test_trusted_ui_url_uses_a_fragment_not_a_query_string():
    token = "t" * 64

    url = launcher.trusted_ui_url("http://127.0.0.1:3000", token, True)

    assert url == "http://127.0.0.1:3000/#local-bootstrap=" + token
    assert "?" not in url, "a query string would land in access logs"


def test_owner_sidecar_contains_no_secret(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "_listening_pid", lambda port: 4321)
    monkeypatch.setattr(
        launcher, "_process_identity", lambda pid: ("C:/py/python.exe", "x", RECENT)
    )

    launcher._record_service_pid("CORE_API", "http://127.0.0.1:5000")

    with open(launcher._owner_path("CORE_API"), encoding="utf-8") as handle:
        body = handle.read()

    assert launcher._LOCAL_BOOTSTRAP_TOKEN not in body
    assert launcher._LOCAL_PROXY_SECRET not in body
    assert "local-bootstrap" not in body
