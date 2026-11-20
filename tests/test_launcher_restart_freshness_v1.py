# tests/test_launcher_restart_freshness_v1.py
"""ARCHITECTOS_LAUNCHER_RESTART_FRESHNESS_V1 — launcher verdict contract.

The user-facing failure this guards against:

  double-click OPEN_ARCHITECTOS_UI.bat -> "restart? Y" -> the console closes,
  no browser opens, and the UI has no trusted session.

Root cause in code, not in the shell script:

* ``ensure_service()`` returns ``(True, None)`` for a service it found ALREADY
  listening, so ``_fresh = core_process is not None and ui_process is not None``
  becomes False;
* ``trusted_ui_url(..., freshly_started=False)`` returns None, so the launcher
  prints "TRUSTED LOCAL UI: UNAVAILABLE" and opens no browser;
* ``main()`` still returned 0, and the BAT treated "port 3000 answers" as
  success — so it printed "ready" and closed.

These tests pin the three links that must never regress: the freshness wait,
the URL gate, and the exit-code contract.
"""
from __future__ import annotations

import inspect
import os
import sys
import textwrap

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

import launcher


TOKEN = "t" * 48


# ---------------------------------------------------------------------------
# 1. A reused service must never yield a trusted URL
# ---------------------------------------------------------------------------

class TestTrustedUrlGate:

    def test_reused_services_yield_no_url(self) -> None:
        assert launcher.trusted_ui_url("http://127.0.0.1:3000", TOKEN, False) is None

    def test_freshly_started_services_yield_the_fragment_url(self) -> None:
        url = launcher.trusted_ui_url("http://127.0.0.1:3000", TOKEN, True)
        assert url == "http://127.0.0.1:3000/#local-bootstrap=" + TOKEN

    def test_short_token_is_refused(self) -> None:
        assert launcher.trusted_ui_url("http://127.0.0.1:3000", "short", True) is None

    def test_token_stays_in_the_fragment(self) -> None:
        url = launcher.trusted_ui_url("http://127.0.0.1:3000", TOKEN, True)
        assert url is not None
        # A fragment is never sent to the server, so the token cannot reach
        # an access log or a request line.
        assert url.split("#", 1)[1].startswith("local-bootstrap=")
        assert "?" not in url


# ---------------------------------------------------------------------------
# 2. The restart must PROVE the ports were released
# ---------------------------------------------------------------------------

class TestWaitPortsReleased:

    def test_reports_released_when_both_ports_are_free(self, monkeypatch) -> None:
        monkeypatch.setattr(launcher, "_listening_pid", lambda port: None)
        released, busy = launcher._wait_ports_released(timeout=0.3)
        assert released is True
        assert busy == []

    def test_reports_busy_when_a_port_is_still_held(self, monkeypatch) -> None:
        # Core port still owned by a dying process -> must NOT be reused.
        monkeypatch.setattr(
            launcher,
            "_listening_pid",
            lambda port: 1234 if port == launcher._url_port(launcher.RC.CORE_API_URL) else None,
        )
        released, busy = launcher._wait_ports_released(timeout=0.3)
        assert released is False
        assert busy == ["CORE_API"]

    def test_waits_for_a_port_to_be_released(self, monkeypatch) -> None:
        """The race this exists for: busy on the first probe, free afterwards."""
        calls = {"n": 0}

        def fake_listening_pid(port):
            calls["n"] += 1
            return 999 if calls["n"] <= 2 else None

        monkeypatch.setattr(launcher, "_listening_pid", fake_listening_pid)
        released, busy = launcher._wait_ports_released(timeout=5.0)
        assert released is True
        assert calls["n"] > 2


# ---------------------------------------------------------------------------
# 3. Diagnostics are retained, and never carry a secret
# ---------------------------------------------------------------------------

class TestLauncherLog:

    def test_writes_a_line(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
        launcher._launcher_log("restart: ports released")
        text = (tmp_path / "launcher.log").read_text(encoding="utf-8")
        assert "restart: ports released" in text

    def test_never_logs_the_bootstrap_url_or_token(self, tmp_path, monkeypatch) -> None:
        """Guard the call sites: no log statement may pass a URL/token."""
        monkeypatch.setattr(launcher, "LOG_DIR", str(tmp_path))
        launcher._launcher_log("verdict: OK (overall=True open_failed=False)")
        text = (tmp_path / "launcher.log").read_text(encoding="utf-8")
        assert "local-bootstrap" not in text
        assert TOKEN not in text

    def test_logging_failure_never_breaks_the_launch(self, monkeypatch) -> None:
        monkeypatch.setattr(launcher, "LOG_DIR", "\0invalid\0path")
        launcher._launcher_log("must not raise")  # no exception expected


# ---------------------------------------------------------------------------
# 4. Static guards on the verdict wiring
# ---------------------------------------------------------------------------

class TestVerdictContract:

    def test_open_failed_is_assigned_before_it_can_be_read(self) -> None:
        """AST rule A5 — an unbound local would crash the launcher."""
        source = textwrap.dedent(inspect.getsource(launcher.main))
        assert "_open_failed = False" in source, (
            "_open_failed must be initialised before the overall branch"
        )
        assert source.index("_open_failed = False") < source.index("if overall:"), (
            "_open_failed must be initialised BEFORE 'if overall:'"
        )

    def test_main_returns_failure_when_the_browser_session_failed(self) -> None:
        source = textwrap.dedent(inspect.getsource(launcher.main))
        assert "_open_failed" in source
        assert "return 0 if _ok else 1" in source, (
            "main must return a non-zero code when a requested trusted session "
            "could not be issued"
        )

    def test_restart_waits_for_released_ports(self) -> None:
        source = textwrap.dedent(inspect.getsource(launcher.main))
        assert "_wait_ports_released()" in source

    def test_stop_never_uses_taskkill_tree(self) -> None:
        """``/T`` is how killing a venv shim took the real server down."""
        source = textwrap.dedent(inspect.getsource(launcher.stop_services))
        assert '"/T"' not in source
        assert "'/T'" not in source

    def test_stop_still_verifies_identity(self) -> None:
        source = textwrap.dedent(inspect.getsource(launcher.stop_services))
        assert "_verify_service_identity" in source


# ---------------------------------------------------------------------------
# 5. The BATs consume the exit code
# ---------------------------------------------------------------------------

class TestBatContract:

    def _read(self, name: str) -> str:
        with open(os.path.join(_PROJECT_ROOT, name), encoding="utf-8", errors="replace") as fh:
            return fh.read()

    def test_ui_bat_checks_launcher_exit_code_on_restart(self) -> None:
        text = self._read("OPEN_ARCHITECTOS_UI.bat")
        assert "launcher.py --restart --open-ui" in text
        assert "if errorlevel 1 goto restart_failed" in text

    def test_ui_bat_checks_exit_code_after_startup_batch(self) -> None:
        text = self._read("OPEN_ARCHITECTOS_UI.bat")
        assert "if errorlevel 1 goto start_failed" in text

    def test_start_bat_propagates_the_exit_code(self) -> None:
        text = self._read("START_ARCHITECTOS.bat")
        assert "set \"LAUNCH_RC=%ERRORLEVEL%\"" in text
        assert "exit /b %LAUNCH_RC%" in text

    def test_ui_bat_still_offers_the_no_restart_path(self) -> None:
        text = self._read("OPEN_ARCHITECTOS_UI.bat")
        assert "if errorlevel 2 goto keep_running" in text
        assert ":keep_running" in text
