"""CODER MVP V1 offline integration tests.

No Docker command is launched and no Python artifact is executed. The source
below is inert test data; the executor is always a controlled fake.
"""

import hashlib
import json
import os

import pytest

from core.chat.project_code_file_writer_v1 import create_project_code_file
from core.runtime.local_authorization_v1 import (
    LocalRequestNonceLedger,
    sign_proxy_request,
)
from core.execution.python_execution_mvp_v1 import (
    CONSENT_PATH,
    PREVIEW_PATH,
    ExecutionMvpService,
    PinnedPythonDockerExecutor,
)


SECRET = "mvp-synthetic-secret-" + "x" * 40
ACTOR = "lsa_mvp_actor"
SESSION = "lss_mvp_session"
PROJECT = "project_mvp"
SOURCE = b'print("ArchitectOS MVP OK")\n'
DIGEST = hashlib.sha256(SOURCE).hexdigest()
LIMIT_VALUES = {
    "max_runtime_seconds": 10,
    "max_memory_mb": 256,
    "max_cpus": 1.0,
    "max_output_bytes": 65536,
    "max_pids": 32,
}


class FakeExecutor(object):
    backend_verified = True

    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "ok": True,
            "reason": "completed",
            "stdout": "ArchitectOS MVP OK\n",
            "stderr": "",
            "exit_code": 0,
            "source_digest_verified": True,
            "removal_state": "confirmed_absent",
            "removal_verified": True,
            "container_id": "a" * 64,
        }

    def run_source(self, source_bytes, source_sha256, resource_limits):
        self.calls.append((source_bytes, source_sha256, dict(resource_limits)))
        return dict(self.result)


def _sign(payload, path, nonce, now=1000, actor=ACTOR, session=SESSION):
    return sign_proxy_request(
        SECRET, actor_id=actor, session_id=session, payload=payload,
        path=path, nonce="nonce_" + str(nonce).zfill(32), now=now,
    )


def _service(tmp_path, *, enabled=True, executor=None):
    documents = tmp_path / "documents"
    documents.mkdir(parents=True)
    write = create_project_code_file(
        PROJECT, "calculator.py", SOURCE.decode("utf-8"),
        documents_root=str(documents),
    )
    assert write["verified_on_disk"] is True
    fake = executor or FakeExecutor()
    service = ExecutionMvpService(
        code_root_resolver=lambda project_id: str(documents / "code"),
        executor_factory=lambda: fake,
        opt_in_reader=lambda: enabled,
    )
    return service, fake, documents / "code" / "calculator.py"


def _preview(service, ledger, *, nonce=1, now=1000, project=PROJECT,
             filename="calculator.py"):
    payload = {
        "operation": "prepare_execution_preview",
        "project_id": project,
        "filename": filename,
    }
    return service.prepare_preview(
        proxy_secret=SECRET, headers=_sign(payload, PREVIEW_PATH, nonce, now),
        payload=payload, path=PREVIEW_PATH, remote_addr="127.0.0.1",
        nonce_ledger=ledger, now=now,
    )


def _consent(service, ledger, preview, *, nonce=2, now=1001,
             project=PROJECT, digest=DIGEST):
    payload = {
        "operation": "approve_and_run_python",
        "project_id": project,
        "proposal_id": preview["proposal_id"],
        "filename": "calculator.py",
        "source_sha256": digest,
        "action": "run_python",
        "scope": "execute",
        "consent": True,
    }
    return service.approve_and_run(
        proxy_secret=SECRET, headers=_sign(payload, CONSENT_PATH, nonce, now),
        payload=payload, path=CONSENT_PATH, remote_addr="127.0.0.1",
        nonce_ledger=ledger, now=now,
    )


def test_saved_file_and_preview_do_not_execute(tmp_path):
    service, executor, artifact = _service(tmp_path)
    result = _preview(service, LocalRequestNonceLedger())

    assert artifact.read_bytes() == SOURCE
    assert result["ok"] is True
    assert result["preview"]["source"] == SOURCE.decode("utf-8")
    assert result["preview"]["source_sha256"] == DIGEST
    assert result["preview"]["network_policy"] == "none"
    assert result["preview"]["host_mounts"] == []
    assert result["preview"]["save_and_run_require_separate_approvals"] is True
    assert result["capability_minted"] is False
    assert executor.calls == []


def test_distinct_signed_consent_executes_once_and_returns_visible_output(tmp_path):
    service, executor, artifact = _service(tmp_path)
    ledger = LocalRequestNonceLedger()
    preview = _preview(service, ledger)
    result = _consent(service, ledger, preview)

    assert result["ok"] is True
    assert result["execution"]["stdout"] == "ArchitectOS MVP OK\n"
    assert result["execution"]["exit_code"] == 0
    assert result["execution"]["source_digest_verified"] is True
    assert result["execution"]["removal_verified"] is True
    assert executor.calls == [(SOURCE, DIGEST, LIMIT_VALUES)]
    assert "token" not in json.dumps(result).lower()

    replay = _consent(service, ledger, preview, nonce=3, now=1002)
    assert replay["ok"] is False
    assert executor.calls == [(SOURCE, DIGEST, LIMIT_VALUES)]


def test_changed_source_after_preview_is_refused_before_executor(tmp_path):
    service, executor, artifact = _service(tmp_path)
    ledger = LocalRequestNonceLedger()
    preview = _preview(service, ledger)
    artifact.write_bytes(b'print("changed")\n')

    result = _consent(service, ledger, preview)

    assert result["ok"] is False
    assert result["reason"] == "execution_source_changed_before_approval"
    assert executor.calls == []


def test_default_disabled_gate_refuses_without_consuming_or_running(tmp_path):
    service, executor, artifact = _service(tmp_path, enabled=False)
    ledger = LocalRequestNonceLedger()
    preview = _preview(service, ledger)

    result = _consent(service, ledger, preview)

    assert result["ok"] is False
    assert result["reason"] == "execution_disabled"
    assert executor.calls == []


def test_cleanup_uncertainty_and_nonzero_exit_are_visible_failures(tmp_path):
    executor = FakeExecutor({
        "ok": False,
        "reason": "cleanup_unverified",
        "stdout": "partial\n",
        "stderr": "trace\n",
        "exit_code": 1,
        "source_digest_verified": True,
        "removal_state": "unverified",
        "removal_verified": False,
        "container_id": "b" * 64,
    })
    service, executor, artifact = _service(tmp_path, executor=executor)
    ledger = LocalRequestNonceLedger()
    preview = _preview(service, ledger)

    result = _consent(service, ledger, preview)

    assert result["ok"] is False
    assert result["execution"]["reason"] == "cleanup_unverified"
    assert result["execution"]["exit_code"] == 1
    assert result["execution"]["removal_verified"] is False


@pytest.mark.parametrize("field,value", [
    ("scope", "save"),
    ("project_id", "project_other"),
    ("filename", "other.py"),
    ("source_sha256", "0" * 64),
])
def test_consent_binding_mismatches_never_reach_executor(tmp_path, field, value):
    service, executor, artifact = _service(tmp_path)
    ledger = LocalRequestNonceLedger()
    preview = _preview(service, ledger)
    payload = {
        "operation": "approve_and_run_python",
        "project_id": PROJECT,
        "proposal_id": preview["proposal_id"],
        "filename": "calculator.py",
        "source_sha256": DIGEST,
        "action": "run_python",
        "scope": "execute",
        "consent": True,
    }
    payload[field] = value
    result = service.approve_and_run(
        proxy_secret=SECRET, headers=_sign(payload, CONSENT_PATH, 20),
        payload=payload, path=CONSENT_PATH, remote_addr="127.0.0.1",
        nonce_ledger=ledger, now=1000,
    )
    assert result["ok"] is False
    assert executor.calls == []


def test_pinned_executor_has_fixed_guest_bootstrap_and_no_mounts(monkeypatch):
    import core.execution.python_execution_mvp_v1 as module

    monkeypatch.setattr(module, "verify_docker_binary_identity", lambda *_a, **_k: {
        "trusted": True, "actual_sha256": "f" * 64,
    })
    executor = PinnedPythonDockerExecutor()
    spec = executor._source_spec(LIMIT_VALUES)
    executor._source_bytes = SOURCE
    executor._source_sha256 = DIGEST
    args = executor._fixed_create_args(spec, "architectos-mvp-fixed")

    assert "--network" in args and args[args.index("--network") + 1] == "none"
    assert "--read-only" in args
    assert "--cap-drop" in args and args[args.index("--cap-drop") + 1] == "ALL"
    assert "--user" in args and args[args.index("--user") + 1] == "65534:65534"
    assert "--interactive" in args
    assert not any(arg in ("-v", "--volume", "--mount") for arg in args)
    assert DIGEST in args
    assert "python3" in args
    assert executor._attach_command("a" * 64) == ["start", "-a", "-i", "a" * 64]


def test_pinned_executor_sends_exact_bytes_and_requires_guest_digest_marker(monkeypatch):
    import core.execution.python_execution_mvp_v1 as module

    monkeypatch.setattr(module, "verify_docker_binary_identity", lambda *_a, **_k: {
        "trusted": True, "actual_sha256": "f" * 64,
    })
    executor = PinnedPythonDockerExecutor()

    class _Run(object):
        def as_dict(self):
            return {
                "ok": True, "reason": "completed", "stdout": "expected\n",
                "stderr": module.DIGEST_MARKER + DIGEST + "\n", "exit_code": 0,
                "removal_verified": True, "removal_state": "confirmed_absent",
            }

    observed = {}

    def fake_run(owner, spec):
        observed["bytes"] = owner._source_bytes
        observed["digest"] = owner._source_sha256
        observed["limits"] = {
            "runtime": spec.deadline_seconds,
            "memory": spec.memory_mb,
            "cpus": spec.cpus,
            "pids": spec.pids_limit,
            "output": spec.max_output_bytes,
        }
        return _Run()

    monkeypatch.setattr(module.BoundedDockerOrchestrator, "run", fake_run)
    result = executor.run_source(SOURCE, DIGEST, LIMIT_VALUES)

    assert observed["bytes"] == SOURCE
    assert observed["digest"] == DIGEST
    assert observed["limits"] == {
        "runtime": 10, "memory": 256, "cpus": 1.0,
        "pids": 32, "output": 65536,
    }
    assert result["ok"] is True
    assert result["source_digest_verified"] is True
    assert module.DIGEST_MARKER not in result["stderr"]

    class _UnverifiedRun(_Run):
        def as_dict(self):
            result = super().as_dict()
            result["stderr"] = "ordinary stderr\n"
            return result

    monkeypatch.setattr(
        module.BoundedDockerOrchestrator, "run", lambda *_a, **_k: _UnverifiedRun())
    unverified = executor.run_source(SOURCE, DIGEST, LIMIT_VALUES)
    assert unverified["ok"] is False
    assert unverified["reason"] == "source_digest_unverified"


def test_pinned_executor_stdin_handoff_writes_exact_approved_bytes(monkeypatch):
    import core.execution.python_execution_mvp_v1 as module

    monkeypatch.setattr(module, "verify_docker_binary_identity", lambda *_a, **_k: {
        "trusted": True, "actual_sha256": "f" * 64,
    })
    executor = PinnedPythonDockerExecutor()

    class _Input(object):
        def __init__(self):
            self.data = b""
            self.flushed = False
            self.closed = False

        def write(self, value):
            self.data += value

        def flush(self):
            self.flushed = True

        def close(self):
            self.closed = True

    stream = _Input()
    executor._source_bytes = SOURCE
    executor._supply_input(type("Proc", (), {"stdin": stream})())

    assert stream.data == SOURCE
    assert stream.flushed is True
    assert stream.closed is True


def test_ui_proxy_requires_trusted_session_and_signs_server_owned_action(monkeypatch):
    import ui.app as ui_application
    import ui.routes.chat_routes as proxy
    from config import runtime_config as runtime_config
    from flask import session
    from core.runtime.local_authorization_v1 import verify_proxy_request

    secret = "mvp-ui-proxy-" + "p" * 48
    monkeypatch.setenv("ARCHITECTOS_LOCAL_PROXY_SECRET", secret)
    posted = []

    class _Response(object):
        status_code = 200

        @staticmethod
        def json():
            return {"ok": True, "stage": "execution_finished"}

    def fake_post(url, json=None, headers=None, timeout=None):
        posted.append((url, json, headers, timeout))
        return _Response()

    monkeypatch.setattr(proxy.requests, "post", fake_post)
    browser_payload = {
        "project_id": PROJECT,
        "proposal_id": "eap_" + "a" * 24,
        "filename": "calculator.py",
        "source_sha256": DIGEST,
        "confirm_run": True,
    }
    request_args = dict(
        method="POST", json=browser_payload,
        headers={"Origin": runtime_config.UI_URL, "Host": "127.0.0.1:3000"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    with ui_application.app.test_request_context(
            CONSENT_PATH, **request_args):
        refused, status = proxy.coder_execution_consent_proxy()
        assert status == 403
        assert refused.get_json()["reason"] == "trusted_local_session_required"
        assert posted == []

    with ui_application.app.test_request_context(
            CONSENT_PATH, **request_args):
        session["trusted_local"] = True
        session["actor_id"] = ACTOR
        session["local_session_id"] = SESSION
        response, status = proxy.coder_execution_consent_proxy()
        assert status == 200 and response.get_json()["ok"] is True

    assert len(posted) == 1
    _url, signed_payload, signed_headers, timeout = posted[0]
    assert signed_payload == {
        "operation": "approve_and_run_python",
        "project_id": PROJECT,
        "proposal_id": browser_payload["proposal_id"],
        "filename": "calculator.py",
        "source_sha256": DIGEST,
        "action": "run_python",
        "scope": "execute",
        "consent": True,
    }
    verified = verify_proxy_request(
        secret, signed_headers, signed_payload, path=CONSENT_PATH,
        remote_addr="127.0.0.1",
    )
    assert verified["trusted"] is True
    assert timeout == 180


def test_ui_proxy_blocks_nested_execution_token_regression():
    import ui.routes.chat_routes as proxy

    assert proxy._contains_execution_secret({"nested": {"token": "exc_secret"}})
    assert proxy._contains_execution_secret({"nested": ["exc_secret"]})
    assert not proxy._contains_execution_secret({
        "capability_consumed": True, "proposal_id": "eap_public",
    })


def test_real_ui_and_core_flask_boundaries_complete_offline_with_fake_executor(
        tmp_path, monkeypatch):
    """Real Flask routes and HMAC verification; Docker remains impossible."""
    import app as core_application
    import ui.app as ui_application
    import ui.routes.chat_routes as proxy
    from config import runtime_config as runtime_config
    from urllib.parse import urlparse

    documents = tmp_path / "documents"
    documents.mkdir(parents=True)
    write = create_project_code_file(
        PROJECT, "calculator.py", SOURCE.decode("utf-8"),
        documents_root=str(documents),
    )
    assert write["verified_on_disk"] is True
    assert (documents / "code" / "calculator.py").read_bytes() == SOURCE
    executor = FakeExecutor()
    service = ExecutionMvpService(
        code_root_resolver=lambda _project_id: str(documents / "code"),
        executor_factory=lambda: executor,
        opt_in_reader=lambda: True,
    )
    monkeypatch.setattr(core_application, "_execution_mvp_service", service)
    secret = "mvp-two-flask-boundaries-" + "s" * 40
    monkeypatch.setenv("ARCHITECTOS_LOCAL_PROXY_SECRET", secret)
    core_client = core_application.app.test_client()

    class _ProxyResponse(object):
        def __init__(self, response):
            self._response = response
            self.status_code = response.status_code

        def json(self):
            return self._response.get_json()

    def into_core(url, json=None, headers=None, timeout=None):
        assert timeout in (30, 180)
        response = core_client.post(
            urlparse(url).path, json=json, headers=headers,
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        return _ProxyResponse(response)

    monkeypatch.setattr(proxy.requests, "post", into_core)
    ui_client = ui_application.app.test_client()
    origin = runtime_config.UI_URL
    with ui_client.session_transaction(base_url=origin) as local_session:
        local_session["trusted_local"] = True
        local_session["actor_id"] = ACTOR
        local_session["local_session_id"] = SESSION
    host = urlparse(origin).netloc
    headers = {"Origin": origin, "Host": host}

    preview_response = ui_client.post(
        PREVIEW_PATH,
        json={"project_id": PROJECT, "filename": "calculator.py"},
        headers=headers,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    preview = preview_response.get_json()
    assert preview_response.status_code == 200
    assert preview["preview"]["source"] == SOURCE.decode("utf-8")
    assert preview["preview"]["source_sha256"] == DIGEST
    assert executor.calls == []

    browser_consent = {
        "project_id": PROJECT,
        "proposal_id": preview["proposal_id"],
        "filename": "calculator.py",
        "source_sha256": DIGEST,
        "confirm_run": True,
    }
    executed_response = ui_client.post(
        CONSENT_PATH, json=browser_consent, headers=headers,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    executed = executed_response.get_json()
    assert executed_response.status_code == 200
    assert executed["ok"] is True
    assert executed["execution"]["stdout"] == "ArchitectOS MVP OK\n"
    assert "token" not in json.dumps(executed).lower()
    assert executor.calls == [(SOURCE, DIGEST, LIMIT_VALUES)]

    replay_response = ui_client.post(
        CONSENT_PATH, json=browser_consent, headers=headers,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert replay_response.status_code in (400, 409)
    assert replay_response.get_json()["ok"] is False
    assert executor.calls == [(SOURCE, DIGEST, LIMIT_VALUES)]


def test_real_ui_assets_expose_preview_and_explicit_run_but_no_chat_autorun():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html = open(os.path.join(root, "ui", "templates", "index.html"), encoding="utf-8").read()
    js = open(os.path.join(root, "ui", "static", "app.js"), encoding="utf-8").read()

    assert 'id="runPythonBtn"' in html
    assert 'id="executionPreview"' in html
    assert 'id="confirmRunBtn"' in html
    assert "/api/coder/execution/preview" in js
    assert "/api/coder/execution/consent" in js
    assert "confirmRunBtn" in js
    assert "approve_and_run_python" not in js  # UI server, not browser, owns signed action shape
