"""CODER-07C.1 Defect B — bounded output-reader liveness.

Pure offline tests.  Docker and subprocess spawning are replaced by scripted
objects; no engine, container, or generated source is contacted or executed.

The defect is that ``Thread.join(timeout)`` is only a wait: it does not prove
the thread stopped.  A reader that remains blocked can therefore leave capture
incomplete while the old adapter reports ``ok=True``.
"""

import os
import subprocess
import sys
import types

import pytest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPPORT = os.path.join(ROOT, "tests", "support")
for _path in (ROOT, SUPPORT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import bounded_docker_orchestrator_v1 as orch  # noqa: E402


CID = "d" * 64


def completed(returncode=0, stdout=b"", stderr=b""):
    return subprocess.CompletedProcess(
        args=["docker"], returncode=returncode, stdout=stdout, stderr=stderr)


class _Stream(object):
    def __init__(self, label, events):
        self.label = label
        self.events = events
        self.closed = False

    def fileno(self):
        return 100 if self.label == "stdout" else 101

    def close(self):
        self.closed = True
        self.events.append("close_%s" % self.label)


class _Proc(object):
    """Scripted attach client with no operating-system process."""

    def __init__(self, events, running=False, wait_error=None):
        self.events = events
        self.running = running
        self.wait_error = wait_error
        self.stdout = _Stream("stdout", events)
        self.stderr = _Stream("stderr", events)

    def poll(self):
        self.events.append("proc_poll")
        return None if self.running else 0

    def wait(self, timeout=None):
        self.events.append("proc_wait:%s" % timeout)
        if self.wait_error is not None:
            raise self.wait_error
        self.running = False
        return 0

    def kill(self):
        self.events.append("proc_kill")
        if self.wait_error is None:
            self.running = False


class _FakeThread(object):
    def __init__(self, events, label, alive_sequence):
        self.events = events
        self.label = label
        self._alive_sequence = list(alive_sequence)
        self._last_alive = bool(self._alive_sequence[-1])
        self.join_calls = []
        self.alive_checks = 0

    def start(self):
        self.events.append("start_%s" % self.label)

    def join(self, timeout=None):
        self.join_calls.append(timeout)
        self.events.append("join_%s" % self.label)

    def is_alive(self):
        self.alive_checks += 1
        self.events.append("alive_%s" % self.label)
        if self._alive_sequence:
            self._last_alive = bool(self._alive_sequence.pop(0))
        return self._last_alive


class _ThreadFactory(object):
    def __init__(self, events, sequences):
        self.events = events
        self.sequences = list(sequences)
        self.threads = []

    def __call__(self, target=None, args=(), daemon=None, name=None):
        label = args[1]
        sequence = self.sequences.pop(0)
        thread = _FakeThread(self.events, label, sequence)
        self.threads.append(thread)
        return thread


class _ScriptedOrchestrator(orch.BoundedDockerOrchestrator):
    def __init__(self, proc, events):
        super().__init__()
        self.proc = proc
        self.events = events
        self.calls = []

    def _run_docker(self, args, timeout=10800):
        args = list(args)
        self.calls.append(args)
        verb = args[0]
        if verb == "ps":
            return completed()
        if verb == "create":
            return completed(stdout=CID.encode("ascii"))
        if verb == "rm":
            self.events.append("container_cleanup")
            return completed()
        if verb == "inspect" and "{{json .State}}" in args:
            return completed(stdout=b'{"OOMKilled": false, "ExitCode": 0}')
        if verb == "inspect":
            return completed(1, stderr=b"Error: No such object: " + CID.encode("ascii"))
        return completed()

    def _popen(self, args):
        self.events.append("attach_started")
        return self.proc


def _run(monkeypatch, sequences=((True, True), (True, True)), proc=None):
    events = []
    proc = proc or _Proc(events)
    factory = _ThreadFactory(events, sequences)
    monkeypatch.setattr(orch.threading, "Thread", factory)
    adapter = _ScriptedOrchestrator(proc, events)
    result = adapter.run(
        orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=5))
    return adapter, result, factory, proc, events


def test_b_surviving_reader_prevents_success(monkeypatch):
    adapter, result, factory, proc, events = _run(monkeypatch)

    assert result.ok is False
    assert result.reason == orch.R_SUPERVISION_UNRESOLVED
    assert result.supervision_unresolved is True
    assert result.unresolved_supervision


def test_b_every_reader_is_checked_after_its_bounded_join(monkeypatch):
    adapter, result, factory, proc, events = _run(monkeypatch)

    assert len(factory.threads) == 2
    for thread in factory.threads:
        assert thread.join_calls
        assert all(timeout is not None for timeout in thread.join_calls)
        assert thread.alive_checks >= 1


def test_b_surviving_reader_does_not_hide_confirmed_container_removal(monkeypatch):
    adapter, result, factory, proc, events = _run(monkeypatch)

    assert "container_cleanup" in events
    assert result.removal_state == orch.REMOVAL_CONFIRMED
    assert result.removal_verified is True
    assert adapter.unresolved_container_ids() == []


def test_b_reader_is_rechecked_after_pipe_close(monkeypatch):
    adapter, result, factory, proc, events = _run(
        monkeypatch, sequences=((True, False), (True, False)))

    assert proc.stdout.closed is True
    assert proc.stderr.closed is True
    for thread in factory.threads:
        assert len(thread.join_calls) >= 2
        assert thread.alive_checks >= 2
    assert result.supervision_unresolved is False


def test_b_unresolved_reader_blocks_later_run_without_engine_contact(monkeypatch):
    adapter, result, factory, proc, events = _run(monkeypatch)
    before = len(adapter.calls)

    with pytest.raises(orch.OrchestrationRefused) as caught:
        adapter.run(orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=5))

    assert caught.value.reason == orch.R_UNRESOLVED_SUPERVISION
    assert len(adapter.calls) == before


def test_b_attach_is_boundedly_reaped_before_reader_join(monkeypatch):
    events = []
    proc = _Proc(events, running=True)
    factory = _ThreadFactory(events, ((False,), (False,)))
    monkeypatch.setattr(orch.threading, "Thread", factory)
    adapter = _ScriptedOrchestrator(proc, events)

    def fault():
        raise RuntimeError("TEST-ONLY injected post-start fault")

    with pytest.raises(RuntimeError, match="TEST-ONLY"):
        adapter.run(
            orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=5),
            _fault_after_start=fault)

    assert "proc_kill" in events
    assert "container_cleanup" in events
    first_join = min(i for i, item in enumerate(events) if item.startswith("join_"))
    assert events.index("proc_kill") < first_join


def test_b_unreaped_attach_client_is_an_unresolved_supervision_liability(monkeypatch):
    events = []
    proc = _Proc(
        events,
        running=True,
        wait_error=subprocess.TimeoutExpired(cmd="docker start -a", timeout=10),
    )
    factory = _ThreadFactory(events, ((False,), (False,)))
    monkeypatch.setattr(orch.threading, "Thread", factory)
    adapter = _ScriptedOrchestrator(proc, events)

    def attach_failure():
        raise orch._AttachFailed("TEST-ONLY attach supervision fault")

    result = adapter.run(
        orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=5),
        _fault_after_start=attach_failure)

    assert result.ok is False
    assert result.supervision_unresolved is True
    assert "attach_client" in result.unresolved_supervision
    assert result.reap_error


def test_b_boundary_declares_liveness_and_fail_closed_reuse(monkeypatch):
    boundary = orch.describe_boundary()

    assert boundary["reader_liveness_checked"] is True
    assert boundary["unresolved_supervision_blocks_reuse"] is True
    assert orch.R_SUPERVISION_UNRESOLVED in boundary["outcome_reasons"]

