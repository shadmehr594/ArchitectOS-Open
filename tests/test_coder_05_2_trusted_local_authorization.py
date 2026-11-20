"""CODER-05.2 trusted-local authorization and session isolation.

All source is inert text.  Tests use temporary project roots and refusal probes;
generated Python is never imported or executed.
"""

import contextlib
import io
import time
import os
import threading

import pytest

import app as application
from config import runtime_config as RC
import core.chat.code_file_staging_v1 as staging
import core.chat.project_code_file_writer_v1 as writer
from core.chat.session_registry_v1 import session_registry
from core.project.project_workspace_v1 import project_workspace


SOURCE = "def add(a, b):\n    return a + b\n"


def _auth(actor="lsa_actor_a", session="lss_session_a", project="project_a"):
    return {
        "trusted": True,
        "actor_id": actor,
        "session_id": session,
        "project_id": project,
        "source": "trusted_local_ui_proxy",
    }


@pytest.fixture(autouse=True)
def _clean_state():
    staging.reset_staging()
    session_registry.end()
    yield
    staging.reset_staging()
    session_registry.end()


@pytest.fixture
def isolated_projects(tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    trash = tmp_path / "trash"
    projects.mkdir()
    trash.mkdir()
    monkeypatch.setattr(project_workspace, "projects_root", str(projects))
    monkeypatch.setattr(project_workspace, "trash_root", str(trash))
    return projects


def test_default_owned_services_are_loopback_only():
    assert RC.CORE_API_BIND_HOST in {"127.0.0.1", "::1", "localhost"}
    assert RC.UI_BIND_HOST in {"127.0.0.1", "::1", "localhost"}


def test_proxy_signature_is_unforgeable_and_replay_bounded(monkeypatch):
    from core.runtime.local_authorization_v1 import (
        LocalRequestNonceLedger,
        sign_proxy_request,
        verify_proxy_request,
    )

    secret = "s" * 48
    payload = {"text": "approve", "project_id": "project_a"}
    headers = sign_proxy_request(
        secret,
        actor_id="lsa_actor_a",
        session_id="lss_session_a",
        payload=payload,
        path="/chat",
        now=1000,
        nonce="nonce_" + "a" * 32,
    )
    ledger = LocalRequestNonceLedger()
    verified = verify_proxy_request(
        secret,
        headers,
        payload,
        path="/chat",
        remote_addr="127.0.0.1",
        now=1000,
        nonce_ledger=ledger,
    )
    assert verified["trusted"] is True

    replay = verify_proxy_request(
        secret,
        headers,
        payload,
        path="/chat",
        remote_addr="127.0.0.1",
        now=1000,
        nonce_ledger=ledger,
    )
    assert replay["trusted"] is False
    assert replay["reason"] == "proxy_nonce_replayed"

    forged_headers = dict(headers)
    forged_headers["X-ArchitectOS-Local-Session"] = "lss_forged_session"
    forged = verify_proxy_request(
        secret, forged_headers, payload, path="/chat",
        remote_addr="127.0.0.1", now=1000,
        nonce_ledger=LocalRequestNonceLedger(),
    )
    assert forged["reason"] == "proxy_signature_invalid"

    remote = verify_proxy_request(
        secret, headers, payload, path="/chat",
        remote_addr="192.0.2.10", now=1000,
        nonce_ledger=LocalRequestNonceLedger(),
    )
    assert remote["reason"] == "proxy_not_loopback"


def test_unauthenticated_http_cannot_reach_writer(isolated_projects, monkeypatch):
    manifest = project_workspace.create("Owner")
    project_id = manifest["project_id"]
    staging.stage_code_file(project_id, "calculator.py", SOURCE)

    calls = []

    def _probe(**kwargs):
        calls.append(kwargs)
        return {"status": "failed", "reason": "probe", "verified_on_disk": False}

    monkeypatch.setattr(writer, "create_project_code_file", _probe)
    client = application.app.test_client()
    with contextlib.redirect_stdout(io.StringIO()):
        response = client.post(
            "/api/chat",
            json={"text": "Approve and save calculator.py.", "project_id": project_id},
        )

    assert response.status_code in (200, 401, 403)
    assert calls == []
    assert staging.pending_proposal(project_id) is not None


def test_unauthenticated_http_cannot_stage_or_mint_capability(isolated_projects, monkeypatch):
    import core.chat.chat_architect as chat_module

    manifest = project_workspace.create("Unsigned caller")
    project_id = manifest["project_id"]
    coder_calls = []

    def _coder_forbidden():
        coder_calls.append(True)
        raise AssertionError("untrusted request reached coder")

    monkeypatch.setattr(chat_module, "coder_gateway", _coder_forbidden)
    with contextlib.redirect_stdout(io.StringIO()):
        response = application.app.test_client().post(
            "/api/chat",
            json={
                "text": "یک فایل واقعی blocked.py در پروژه بساز.",
                "project_id": project_id,
            },
        )
    assert response.status_code == 200
    assert coder_calls == []
    assert staging.pending_proposal(project_id) is None
    assert "مورد اعتماد" in response.get_json()["response"]["message"]


def test_authorized_capability_is_actor_session_project_and_digest_bound(tmp_path):
    documents = tmp_path / "documents"
    documents.mkdir()
    auth = _auth()
    proposal = staging.stage_code_file(
        "project_a", "calculator.py", SOURCE,
        documents_root=str(documents), authorization=auth, now=1000,
    )
    token = proposal["approval_token"]

    wrong_actor = staging.approve_staged_file(
        "project_a", "approve and save", documents_root=str(documents),
        authorization=_auth(actor="lsa_actor_b"), approval_token=token, now=1001,
    )
    assert wrong_actor["reason"] == "approval_actor_mismatch"
    assert staging.pending_proposal("project_a") is not None

    wrong_session = staging.approve_staged_file(
        "project_a", "approve and save", documents_root=str(documents),
        authorization=_auth(session="lss_session_b"), approval_token=token, now=1001,
    )
    assert wrong_session["reason"] == "approval_session_mismatch"
    assert staging.pending_proposal("project_a") is not None

    wrong_project = staging.approve_staged_file(
        "project_b", "approve and save", documents_root=str(documents),
        authorization=_auth(project="project_b"), approval_token=token, now=1001,
    )
    assert wrong_project["reason"] == "no_pending_proposal"
    assert staging.pending_proposal("project_a") is not None

    written = staging.approve_staged_file(
        "project_a", "approve and save", documents_root=str(documents),
        authorization=auth, approval_token=token, now=1001,
    )
    assert written["status"] == "written"
    assert (documents / "code" / "calculator.py").read_text(encoding="utf-8") == SOURCE

    replay = staging.approve_staged_file(
        "project_a", "approve and save", documents_root=str(documents),
        authorization=auth, approval_token=token, now=1001,
    )
    assert replay["reason"] == "no_pending_proposal"


def test_expired_and_forged_capabilities_fail_without_write(tmp_path):
    documents = tmp_path / "documents"
    documents.mkdir()
    auth = _auth()
    proposal = staging.stage_code_file(
        "project_a", "calculator.py", SOURCE,
        documents_root=str(documents), authorization=auth, now=1000,
        approval_ttl_seconds=30,
    )

    forged = staging.approve_staged_file(
        "project_a", "approve and save", documents_root=str(documents),
        authorization=auth, approval_token="stg_forged", now=1001,
    )
    assert forged["reason"] == "approval_capability_invalid"
    assert staging.pending_proposal("project_a") is not None

    expired = staging.approve_staged_file(
        "project_a", "approve and save", documents_root=str(documents),
        authorization=auth, approval_token=proposal["approval_token"], now=1031,
    )
    assert expired["reason"] == "approval_capability_expired"
    assert not (documents / "code" / "calculator.py").exists()


def test_changed_source_or_digest_fails_closed_under_authorization(tmp_path):
    documents = tmp_path / "documents"
    documents.mkdir()
    auth = _auth()
    proposal = staging.stage_code_file(
        "project_a", "calculator.py", SOURCE,
        documents_root=str(documents), authorization=auth, now=1000,
    )
    staging._STAGED["project_a"]["content"] = "print('changed')\n"

    outcome = staging.approve_staged_file(
        "project_a", "approve and save", documents_root=str(documents),
        authorization=auth, approval_token=proposal["approval_token"], now=1001,
    )
    assert outcome["reason"] == "staged_content_integrity_failed"
    assert not (documents / "code" / "calculator.py").exists()


def test_overwrite_requires_rotated_overwrite_capability(tmp_path):
    documents = tmp_path / "documents"
    code = documents / "code"
    code.mkdir(parents=True)
    target = code / "calculator.py"
    target.write_text("# original\n", encoding="utf-8")
    auth = _auth()
    proposal = staging.stage_code_file(
        "project_a", "calculator.py", SOURCE,
        documents_root=str(documents), authorization=auth, now=1000,
    )

    first = staging.approve_staged_file(
        "project_a", "approve and overwrite", documents_root=str(documents),
        authorization=auth, approval_token=proposal["approval_token"],
        overwrite_confirmed=True, now=1001,
    )
    assert first["reason"] == "overwrite_capability_required"
    assert target.read_text(encoding="utf-8") == "# original\n"

    overwrite = staging.public_approval_capability("project_a", auth)
    assert overwrite["scope"] == "overwrite"
    assert overwrite["token"] != proposal["approval_token"]

    written = staging.approve_staged_file(
        "project_a", "approve and overwrite", documents_root=str(documents),
        authorization=auth, approval_token=overwrite["token"],
        overwrite_confirmed=True, now=1002,
    )
    assert written["status"] == "written"
    assert target.read_text(encoding="utf-8") == SOURCE


def test_authorized_rejection_consumes_and_later_approval_fails(tmp_path):
    auth = _auth()
    proposal = staging.stage_code_file(
        "project_a", "calculator.py", SOURCE,
        documents_root=str(tmp_path), authorization=auth, now=1000,
    )
    rejected = staging.reject_staged_file(
        "project_a", reason="user_rejected", authorization=auth,
        approval_token=proposal["approval_token"], now=1001,
    )
    assert rejected["status"] == "rejected"
    assert staging.pending_proposal("project_a") is None
    assert staging.approve_staged_file(
        "project_a", "approve and save", documents_root=str(tmp_path),
        authorization=auth, approval_token=proposal["approval_token"], now=1002,
    )["reason"] == "no_pending_proposal"


def test_flask_request_teardown_releases_thread_local_session(monkeypatch):
    def _leaking_handle(*_args, **_kwargs):
        session_registry.begin("session_a")
        return {"type": "chat", "status": "success", "result": "ok"}

    monkeypatch.setattr(application.chat, "handle", _leaking_handle)
    client = application.app.test_client()
    with contextlib.redirect_stdout(io.StringIO()):
        response = client.post("/api/chat", json={"text": "hello"})
    assert response.status_code == 200
    assert session_registry.current() is None


def test_untrusted_origin_cannot_become_trusted_proxy_request():
    from core.runtime.local_authorization_v1 import ui_request_is_trusted_origin

    assert ui_request_is_trusted_origin(
        origin="https://evil.example",
        host="127.0.0.1:3000",
        remote_addr="127.0.0.1",
        ui_url="http://127.0.0.1:3000",
    ) is False
    assert ui_request_is_trusted_origin(
        origin="http://127.0.0.1:3000",
        host="127.0.0.1:3000",
        remote_addr="127.0.0.1",
        ui_url="http://127.0.0.1:3000",
    ) is True

    preflight = application.app.test_client().options(
        "/api/chat",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "Access-Control-Allow-Origin" not in preflight.headers


def test_ui_bootstrap_is_same_origin_one_shot_and_cookie_hardened(monkeypatch):
    import ui.app as ui_application

    token = "bootstrap-" + "b" * 48
    monkeypatch.setattr(ui_application, "_LOCAL_BOOTSTRAP_TOKEN", token)
    monkeypatch.setattr(ui_application, "_LOCAL_BOOTSTRAP_CONSUMED", False)
    client = ui_application.app.test_client()
    good_headers = {"Origin": RC.UI_URL, "Host": "127.0.0.1:3000"}

    accepted = client.post(
        "/api/local-session/bootstrap", json={"token": token},
        headers=good_headers,
    )
    assert accepted.status_code == 200
    cookie = accepted.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie

    replay = client.post(
        "/api/local-session/bootstrap", json={"token": token},
        headers=good_headers,
    )
    assert replay.status_code == 403

    monkeypatch.setattr(ui_application, "_LOCAL_BOOTSTRAP_CONSUMED", False)
    cross_origin = ui_application.app.test_client().post(
        "/api/local-session/bootstrap", json={"token": token},
        headers={"Origin": "https://evil.example", "Host": "127.0.0.1:3000"},
    )
    assert cross_origin.status_code == 403


def test_ui_proxy_keeps_approval_capability_out_of_browser_payload(monkeypatch):
    import ui.app as ui_application
    import ui.routes.chat_routes as proxy
    from core.runtime.local_authorization_v1 import verify_proxy_request

    secret = "proxy-" + "p" * 48
    monkeypatch.setenv("ARCHITECTOS_LOCAL_PROXY_SECRET", secret)
    payload = {"text": "approve", "project_id": "project_a"}
    with ui_application.app.test_request_context(
        "/api/chat", method="POST", json=payload,
        headers={"Origin": RC.UI_URL, "Host": "127.0.0.1:3000"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    ):
        from flask import session
        session["trusted_local"] = True
        session["actor_id"] = "lsa_proxy_actor"
        session["local_session_id"] = "lss_proxy_session"
        headers = proxy._trusted_proxy_headers(payload)
        verified = verify_proxy_request(
            secret, headers, payload, path="/chat", remote_addr="127.0.0.1",
        )
        assert verified["trusted"] is True

        core_payload = {
            "response": {
                "message": "staged",
                "code_approval": {"token": "stg_private", "pending": True},
            }
        }
        proxy._capture_private_capability(core_payload, "project_a")
        assert "code_approval" not in core_payload["response"]
        assert proxy._inject_private_capability(payload)["approval_capability"] == "stg_private"


def _signed_post(client, secret, payload, nonce_suffix):
    from core.runtime.local_authorization_v1 import sign_proxy_request

    headers = sign_proxy_request(
        secret,
        actor_id="lsa_acceptance_actor",
        session_id="lss_acceptance_session",
        payload=payload,
        path="/api/chat",
        nonce="nonce_" + str(nonce_suffix).zfill(32),
    )
    return client.post("/api/chat", json=payload, headers=headers)


def test_signed_http_calculator_then_new_file_end_to_end(isolated_projects, monkeypatch):
    """Recorded source only: no provider, render, shell, or execution call."""
    import core.chat.chat_architect as chat_module
    from core.llm.llm_gateway import LLMGateway

    class _RecordedCoder:
        source = SOURCE

        def generate(self, _prompt, **_kwargs):
            return "```python\n" + self.source + "```"

    recorded = _RecordedCoder()
    monkeypatch.setattr(chat_module, "coder_gateway", lambda: recorded)
    monkeypatch.setattr(
        LLMGateway, "generate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("unexpected live/general LLM call")
        ),
    )
    monkeypatch.setattr(
        application.chat.render_runtime, "render",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("unexpected render call")
        ),
    )
    secret = "acceptance-secret-" + "x" * 40
    monkeypatch.setenv("ARCHITECTOS_LOCAL_PROXY_SECRET", secret)
    manifest = project_workspace.create("Signed owner")
    project_id = manifest["project_id"]
    client = application.app.test_client()

    create = {
        "text": "یک فایل واقعی calculator.py در پروژه بساز.",
        "project_id": project_id,
    }
    with contextlib.redirect_stdout(io.StringIO()):
        staged = _signed_post(client, secret, create, "1")
    staged_payload = staged.get_json()
    capability = staged_payload["response"]["code_approval"]
    assert capability["pending"] is True
    assert capability["filename"] == "calculator.py"
    assert not (isolated_projects / project_id / "documents" / "code" / "calculator.py").exists()

    approve = {
        "text": "Approve and save calculator.py.",
        "project_id": project_id,
        "approval_capability": capability["token"],
    }
    with contextlib.redirect_stdout(io.StringIO()):
        saved = _signed_post(client, secret, approve, "2")
    saved_payload = saved.get_json()
    assert saved_payload["response"]["code_approval"] == {"pending": False}
    target = isolated_projects / project_id / "documents" / "code" / "calculator.py"
    assert target.read_bytes() == SOURCE.rstrip("\n").encode("utf-8")

    second_source = "def greet(name):\n    return f'Hello, {name}'\n"
    recorded.source = second_source
    second_project = project_workspace.create("Signed owner second project")["project_id"]
    create_second = {
        "text": "یک فایل واقعی greeter.py در پروژه بساز.",
        "project_id": second_project,
    }
    with contextlib.redirect_stdout(io.StringIO()):
        staged_second = _signed_post(client, secret, create_second, "3").get_json()
    second_capability = staged_second["response"]["code_approval"]["token"]
    with contextlib.redirect_stdout(io.StringIO()):
        _signed_post(client, secret, {
            "text": "Approve and save greeter.py.",
            "project_id": second_project,
            "approval_capability": second_capability,
        }, "4")
    assert (
        isolated_projects / second_project / "documents" / "code" / "greeter.py"
    ).read_bytes() == second_source.rstrip("\n").encode("utf-8")


def test_model_generated_approval_text_has_no_authority(tmp_path):
    auth = _auth()
    proposal = staging.stage_code_file(
        "project_a", "calculator.py", SOURCE,
        documents_root=str(tmp_path), authorization=auth,
    )
    refused = staging.approve_staged_file(
        "project_a", "approve and save", documents_root=str(tmp_path),
        approval_source="model", authorization=auth,
        approval_token=proposal["approval_token"],
    )
    assert refused["reason"] == staging.APPROVAL_BLOCKED_MODEL_TEXT
    assert not (tmp_path / "code" / "calculator.py").exists()


def test_concurrent_replay_crosses_writer_boundary_at_most_once(tmp_path, monkeypatch):
    auth = _auth()
    proposal = staging.stage_code_file(
        "project_a", "calculator.py", SOURCE,
        documents_root=str(tmp_path), authorization=auth,
    )
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def _blocked_writer(**kwargs):
        calls.append(kwargs)
        entered.set()
        release.wait(timeout=5)
        return {"status": "failed", "reason": "test_probe", "verified_on_disk": False}

    monkeypatch.setattr(writer, "create_project_code_file", _blocked_writer)
    outcomes = []

    def _approve():
        outcomes.append(staging.approve_staged_file(
            "project_a", "approve and save", documents_root=str(tmp_path),
            authorization=auth, approval_token=proposal["approval_token"],
        ))

    first = threading.Thread(target=_approve)
    first.start()
    assert entered.wait(timeout=5)
    second = threading.Thread(target=_approve)
    second.start()
    second.join(timeout=5)
    release.set()
    first.join(timeout=5)

    assert len(calls) == 1
    assert any(item["reason"] == "approval_capability_consumed" for item in outcomes)


def test_untrusted_general_chat_remains_available(monkeypatch):
    seen = []

    def _ordinary(text, context=None):
        seen.append((text, context))
        return {"type": "chat", "status": "success", "result": "ordinary-ok"}

    monkeypatch.setattr(application.chat, "handle", _ordinary)
    with contextlib.redirect_stdout(io.StringIO()):
        response = application.app.test_client().post(
            "/api/chat", json={"text": "hello"}
        )
    assert response.status_code == 200
    assert response.get_json()["response"]["message"] == "ordinary-ok"
    assert seen and seen[0][1]["trusted_local_authorization"]["trusted"] is False
