# tests/test_coder_draft_verification_v1.py
"""DraftVerificationV1 — unsaved-draft verification adapter (Tier 2, no execution).

Nothing here runs Docker, imports a model-generated application, or saves a
project file. Two focused tests run explicitly trusted fixture source in an
isolated child interpreter; every service-level executor remains a fake.

The four hardened axes under test:
  * independent per-scenario application state
  * actor/session-bound, one-shot, digest-bound consent
  * harness result integrity (fail closed on forged/ambiguous/malformed)
  * sandbox / integrity / functional / per-scenario verdicts kept separate
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

from core.execution import draft_verification_v1 as dv
from core.chat import code_file_staging_v1 as staging

PROJECT = "project_tier2_tests"
ACTOR = "local_user"
SESSION = "sess_tier2"
AUTH = {
    "trusted": True,
    "actor_id": ACTOR,
    "session_id": SESSION,
    "project_id": PROJECT,
}

CONTROL = (
    "class Control:\n"
    "    def __init__(self, root):\n"
    "        self.root = root\n"
    "        self.value = 0\n"
)

SCENARIOS = [
    {"name": "alpha", "steps": []},
    {"name": "beta", "steps": []},
]


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _run_trusted_harness(harness: str, tmp_path):
    """Run only test-authored fixture source; never a staged/model draft."""
    draft_path = tmp_path / "trusted_fixture.py"
    local_harness = harness.replace(
        'path = "/tmp/architectos_draft.py"',
        "path = " + repr(str(draft_path)),
    )
    completed = subprocess.run(
        [sys.executable, "-c", local_harness],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload, reason = dv.parse_harness_output(
        completed.stdout, completed.stderr
    )
    assert reason is None
    return payload


def _stage(tmp_path, monkeypatch, source=CONTROL, project=PROJECT):
    from core.project.project_workspace_v1 import project_workspace

    documents = tmp_path / "documents"
    documents.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        project_workspace, "subdir", lambda project_id, name: str(documents)
    )
    staging.reset_staging()
    return staging.stage_code_file(
        project_id=project,
        filename="app.py",
        content=source,
        documents_root=str(documents),
        origin="coder_model",
        authorization=dict(AUTH, project_id=project),
    )


@pytest.fixture()
def staged(tmp_path, monkeypatch):
    proposal = _stage(tmp_path, monkeypatch)
    yield proposal
    staging.reset_staging()


def _patch_verified(monkeypatch, trusted=True, actor=ACTOR, session=SESSION):
    import core.runtime.local_authorization_v1 as authz

    def fake(secret, headers, payload, path=None, remote_addr=None, now=None,
             nonce_ledger=None):
        if not trusted:
            return {"trusted": False, "reason": "proxy_signature_invalid"}
        return {"trusted": True, "actor_id": actor, "session_id": session}

    monkeypatch.setattr(authz, "verify_proxy_request", fake)


def _consent_and_token(monkeypatch, digest, *, actor=ACTOR, session=SESSION,
                       project=PROJECT, now=None, ttl=120, consent_flag=True,
                       operation=dv.DRAFT_OPERATION, path=dv.DRAFT_CONSENT_PATH,
                       extra=None):
    store = dv.DraftVerificationConsent()
    _patch_verified(monkeypatch, actor=actor, session=session)
    payload = {
        "operation": operation,
        "project_id": project,
        "proposal_id": dv.staged_proposal_id(digest),
        "source_sha256": digest,
        "consent": consent_flag,
    }
    if extra:
        payload.update(extra)
    minted = store.mint(
        proxy_secret="s" * 48,
        headers={},
        payload=payload,
        path=path,
        remote_addr="127.0.0.1",
        nonce_ledger=set(),
        project_id=project,
        now=now,
        ttl_seconds=ttl,
    )
    return store, minted


def _mint(monkeypatch, digest, **kwargs):
    return _consent_and_token(monkeypatch, digest, **kwargs)[1]


# ---------------------------------------------------------------------------
# 1. Consent — identity binding, one-shot, fail-closed
# ---------------------------------------------------------------------------

class TestDraftConsent:

    def test_mints_for_the_exact_staged_digest(self, staged, monkeypatch) -> None:
        result = _mint(monkeypatch, staged["digest"])
        assert result["ok"] is True
        assert result["source_sha256"] == staged["digest"]
        assert result["scope"] == dv.DRAFT_SCOPE
        assert result["executed"] is False
        assert result["token"].startswith("dv_")

    def test_untrusted_signature_is_refused(self, staged, monkeypatch) -> None:
        _patch_verified(monkeypatch, trusted=False)
        result = dv.DraftVerificationConsent().mint(
            proxy_secret="s" * 48, headers={},
            payload={
                "operation": dv.DRAFT_OPERATION, "project_id": PROJECT,
                "proposal_id": dv.staged_proposal_id(staged["digest"]),
                "source_sha256": staged["digest"], "consent": True,
            },
            path=dv.DRAFT_CONSENT_PATH, remote_addr="127.0.0.1",
            nonce_ledger=set(), project_id=PROJECT,
        )
        assert result["ok"] is False
        assert result["reason"] == "proxy_signature_invalid"

    def test_wrong_path_is_refused(self, staged, monkeypatch) -> None:
        result = _mint(monkeypatch, staged["digest"],
                       path="/api/coder/execution/consent")
        assert result["ok"] is False
        assert result["reason"] == "draft_consent_path_invalid"

    def test_consent_must_be_explicitly_true(self, staged, monkeypatch) -> None:
        result = _mint(monkeypatch, staged["digest"], consent_flag=False)
        assert result["ok"] is False
        assert result["reason"] == "draft_consent_payload_invalid"

    def test_extra_payload_field_is_refused(self, staged, monkeypatch) -> None:
        result = _mint(monkeypatch, staged["digest"], extra={"save": True})
        assert result["ok"] is False
        assert result["reason"] == "draft_consent_payload_invalid"

    def test_operation_must_be_draft_verification(self, staged, monkeypatch) -> None:
        result = _mint(monkeypatch, staged["digest"],
                       operation="approve_and_run_python")
        assert result["ok"] is False

    def test_digest_must_match_the_staged_proposal(self, staged, monkeypatch) -> None:
        result = _mint(monkeypatch, "0" * 64)
        assert result["ok"] is False
        assert result["reason"] == "draft_consent_digest_mismatch"

    def test_proposal_id_is_bound_to_the_digest(self, staged, monkeypatch) -> None:
        consent = dv.DraftVerificationConsent()
        _patch_verified(monkeypatch)
        result = consent.mint(
            proxy_secret="s" * 48, headers={},
            payload={
                "operation": dv.DRAFT_OPERATION, "project_id": PROJECT,
                "proposal_id": "staged:" + "1" * 64,
                "source_sha256": staged["digest"], "consent": True,
            },
            path=dv.DRAFT_CONSENT_PATH, remote_addr="127.0.0.1",
            nonce_ledger=set(), project_id=PROJECT,
        )
        assert result["ok"] is False
        assert result["reason"] == "draft_consent_proposal_mismatch"

    def test_no_staged_proposal_fails_closed(self, monkeypatch) -> None:
        staging.reset_staging()
        result = _mint(monkeypatch, "a" * 64)
        assert result["ok"] is False
        assert result["reason"] == "draft_consent_no_staged_proposal"

    def test_claim_is_one_shot(self, staged, monkeypatch) -> None:
        consent, minted = _consent_and_token(monkeypatch, staged["digest"])
        first = consent.claim(token=minted["token"], project_id=PROJECT,
                              source_sha256=staged["digest"],
                              actor_id=ACTOR, session_id=SESSION)
        second = consent.claim(token=minted["token"], project_id=PROJECT,
                               source_sha256=staged["digest"],
                               actor_id=ACTOR, session_id=SESSION)
        assert first["ok"] is True
        assert second["ok"] is False
        assert second["reason"] == "draft_capability_consumed"

    def test_expired_capability_is_refused(self, staged, monkeypatch) -> None:
        consent, minted = _consent_and_token(
            monkeypatch, staged["digest"], now=1000.0, ttl=60
        )
        late = consent.claim(token=minted["token"], project_id=PROJECT,
                             source_sha256=staged["digest"],
                             actor_id=ACTOR, session_id=SESSION, now=2000.0)
        assert late["ok"] is False
        assert late["reason"] == "draft_capability_expired"

    def test_project_binding_is_enforced(self, staged, monkeypatch) -> None:
        consent, minted = _consent_and_token(monkeypatch, staged["digest"])
        stolen = consent.claim(token=minted["token"], project_id="another_project",
                               source_sha256=staged["digest"],
                               actor_id=ACTOR, session_id=SESSION)
        assert stolen["ok"] is False
        assert stolen["reason"] == "draft_capability_binding_mismatch"

    def test_cross_actor_use_is_refused(self, staged, monkeypatch) -> None:
        """Possessing the token string is not authority."""
        consent, minted = _consent_and_token(monkeypatch, staged["digest"])
        stolen = consent.claim(token=minted["token"], project_id=PROJECT,
                               source_sha256=staged["digest"],
                               actor_id="another_actor", session_id=SESSION)
        assert stolen["ok"] is False
        assert stolen["reason"] == "draft_capability_binding_mismatch"

    def test_cross_session_use_is_refused(self, staged, monkeypatch) -> None:
        consent, minted = _consent_and_token(monkeypatch, staged["digest"])
        stolen = consent.claim(token=minted["token"], project_id=PROJECT,
                               source_sha256=staged["digest"],
                               actor_id=ACTOR, session_id="another_session")
        assert stolen["ok"] is False
        assert stolen["reason"] == "draft_capability_binding_mismatch"

    def test_claim_requires_identity_arguments(self, staged, monkeypatch) -> None:
        consent, minted = _consent_and_token(monkeypatch, staged["digest"])
        missing_actor = consent.claim(token=minted["token"], project_id=PROJECT,
                                      source_sha256=staged["digest"],
                                      actor_id="", session_id=SESSION)
        assert missing_actor["ok"] is False
        assert missing_actor["reason"] == "draft_capability_actor_missing"

    def test_digest_binding_is_enforced_on_claim(self, staged, monkeypatch) -> None:
        consent, minted = _consent_and_token(monkeypatch, staged["digest"])
        wrong = consent.claim(token=minted["token"], project_id=PROJECT,
                              source_sha256="f" * 64,
                              actor_id=ACTOR, session_id=SESSION)
        assert wrong["ok"] is False
        assert wrong["reason"] == "draft_capability_digest_mismatch"

    def test_save_capability_token_is_not_accepted(self, staged) -> None:
        """The two stores are disjoint: a staging token cannot verify a draft."""
        consent = dv.DraftVerificationConsent()
        result = consent.claim(
            token=staged["approval_token"], project_id=PROJECT,
            source_sha256=staged["digest"], actor_id=ACTOR, session_id=SESSION,
        )
        assert result["ok"] is False
        assert result["reason"] == "draft_capability_invalid"

    def test_minting_never_changes_the_staged_proposal(self, staged, monkeypatch) -> None:
        before = dict(staging.pending_proposal(PROJECT))
        _mint(monkeypatch, staged["digest"])
        after = staging.pending_proposal(PROJECT)
        assert after["status"] == before["status"]
        assert after["digest"] == before["digest"]
        assert after["content"] == before["content"]


# ---------------------------------------------------------------------------
# 2. Harness builder — independent state, digest-bound, compile-only
# ---------------------------------------------------------------------------

class TestHarnessBuilder:

    @staticmethod
    def _constructor_scenarios():
        return [
            {
                "name": "mouse_callback",
                "steps": [
                    {"action": "click", "label": "1"},
                    {"action": "expect_display", "value": "1"},
                ],
            },
            {
                "name": "fresh_keyboard_state",
                "steps": [
                    {"action": "expect_display", "value": "0"},
                    {"action": "key", "keysym": "2"},
                    {"action": "expect_display", "value": "2"},
                ],
            },
        ]

    @staticmethod
    def _constructor_fixture(argument_style):
        constructor = (
            "    def __init__(self, root):\n"
            "        self.root = root\n"
            if argument_style == "root"
            else
            "    def __init__(self):\n"
            "        self.root = tk.Tk()\n"
        )
        return (
            "import tkinter as tk\n"
            "class TrustedConstructorFixture:\n"
            + constructor
            + "        self.value = tk.StringVar()\n"
            "        self.value.set('0')\n"
            "        tk.Entry(self.root, textvariable=self.value)\n"
            "        tk.Button(self.root, text='1', command=lambda: self.value.set('1'))\n"
            "        self.root.bind('<Key>', self.on_key)\n"
            "    def on_key(self, event):\n"
            "        if event.keysym == '2':\n"
            "            self.value.set('2')\n"
        )

    @pytest.mark.parametrize("argument_style", ["root", "no_argument"])
    def test_harness_selects_constructor_form_from_signature(
        self,
        tmp_path,
        argument_style,
    ) -> None:
        """Trusted fixtures cover both conventional Tkinter ownership styles."""
        source = self._constructor_fixture(argument_style)
        scenarios = self._constructor_scenarios()
        payload = _run_trusted_harness(
            dv.build_harness_source(source, _digest(source), scenarios),
            tmp_path,
        )

        assert payload["app_sha256"] == _digest(source)
        assert [item["status"] for item in payload["scenarios"]] == [
            "PASS",
            "PASS",
        ]

    def test_internal_constructor_type_error_is_not_retried_without_root(
        self,
        tmp_path,
    ) -> None:
        """A TypeError raised inside a selected constructor remains a failure.

        The optional parameter makes both calls signature-compatible.  Root
        injection is the compatibility-preserving choice; retrying with no
        argument after its internal TypeError would hide a genuine app defect.
        """
        source = (
            "class TrustedInternalTypeError:\n"
            "    def __init__(self, root=None):\n"
            "        if root is not None:\n"
            "            raise TypeError('trusted internal constructor failure')\n"
            "        self.retry_would_hide_the_bug = True\n"
        )
        scenarios = [{"name": "construct", "steps": []}]
        payload = _run_trusted_harness(
            dv.build_harness_source(source, _digest(source), scenarios),
            tmp_path,
        )

        scenario = payload["scenarios"][0]
        assert scenario["status"] == "NOT_RUN"
        assert "trusted internal constructor failure" in scenario["detail"]

    def test_harness_uses_signature_binding_before_constructor_call(self) -> None:
        harness = dv.build_harness_source(CONTROL, _digest(CONTROL), SCENARIOS)

        assert "inspect.signature(candidate)" in harness
        assert ".bind(root)" in harness
        assert ".bind()" in harness

    @pytest.mark.parametrize(
        "source,expected_count,expected_status",
        [
            (
                "import tkinter as tk\n"
                "class NoRootFixture:\n"
                "    def __init__(self):\n"
                "        self.value = 'constructed without a Tk root'\n",
                0,
                "PASS",
            ),
            (
                "import tkinter as tk\n"
                "class MultipleRootsFixture:\n"
                "    def __init__(self):\n"
                "        self.first = tk.Tk()\n"
                "        self.second = tk.Tk()\n",
                2,
                "NOT_RUN",
            ),
        ],
    )
    def test_no_argument_constructor_requires_one_unambiguous_actual_root(
        self,
        tmp_path,
        source,
        expected_count,
        expected_status,
    ) -> None:
        payload = _run_trusted_harness(
            dv.build_harness_source(
                source,
                _digest(source),
                [{"name": "construct", "steps": []}],
            ),
            tmp_path,
        )

        scenario = payload["scenarios"][0]
        assert scenario["status"] == expected_status
        if expected_status == "NOT_RUN":
            assert "ambiguous_tk_root_count:%d" % expected_count in scenario["detail"]

    def test_harness_tracks_and_resets_actual_tk_roots(self) -> None:
        harness = dv.build_harness_source(CONTROL, _digest(CONTROL), SCENARIOS)

        assert "roots = []" in harness
        assert "roots.append(self)" in harness
        reset_body = harness.split("def reset_stub_state():")[1].split(
            "def constructor_form"
        )[0]
        assert "del roots[:]" in reset_body
        assert "ambiguous_tk_root_count" in harness

    def test_default_scenarios_require_real_precondition_state_changes(self) -> None:
        scenarios = {item["name"]: item["steps"] for item in dv.default_scenarios()}

        duplicate = scenarios["duplicate_decimal_rejected"]
        duplicate_assertions = [
            step
            for step in duplicate
            if step.get("action") == "expect_display"
            and step.get("value") == "1."
        ]
        assert len(duplicate_assertions) >= 2

        division = scenarios["division_by_zero_resets"]
        assert division[:2] == [
            {"action": "click", "label": "5"},
            {"action": "expect_display", "value": "5"},
        ]

        clear = scenarios["clear_buttons_reset_display"]
        assert {"action": "expect_display", "value": "123"} in clear

    @pytest.mark.parametrize(
        "method_name",
        ["grid_rowconfigure", "grid_columnconfigure"],
    )
    def test_tkinter_stub_supports_standard_grid_configuration(
        self, method_name
    ) -> None:
        """A trusted fixture may configure the root grid during construction."""
        source = (
            "class GridConfiguredApp:\n"
            "    def __init__(self, root):\n"
            "        root.%s(0, weight=1)\n" % method_name
        )
        harness = dv.build_harness_source(
            source,
            _digest(source),
            [{"name": "construct", "steps": []}],
        )
        stub_start = harness.index("errors = []")
        stub_end = harness.index("def _string_var")
        namespace = {}
        exec(
            compile(
                harness[stub_start:stub_end],
                "<trusted-tkinter-stub-fixture>",
                "exec",
            ),
            namespace,
        )

        class TrustedGridConfiguredApp:
            def __init__(self, root):
                getattr(root, method_name)(0, weight=1)

        root = namespace["_Root"]()
        instance = TrustedGridConfiguredApp(root)
        assert instance is not None

    def test_harness_constructs_trusted_grid_configured_fixture(
        self, tmp_path
    ) -> None:
        source = (
            "class GridConfiguredApp:\n"
            "    def __init__(self, root):\n"
            "        root.grid_rowconfigure(0, weight=1)\n"
            "        root.grid_columnconfigure(0, weight=1)\n"
        )
        scenarios = [{"name": "construct", "steps": []}]
        payload = _run_trusted_harness(
            dv.build_harness_source(source, _digest(source), scenarios),
            tmp_path,
        )

        assert payload["app_sha256"] == _digest(source)
        assert payload["scenarios"] == [
            {
                "id": "construct",
                "status": "PASS",
                "detail": "",
                "expected": None,
                "actual": None,
            }
        ]

    def test_genuine_instantiation_failure_remains_not_run(
        self, tmp_path
    ) -> None:
        source = (
            "class BrokenTrustedFixture:\n"
            "    def __init__(self, root):\n"
            "        raise RuntimeError('trusted fixture construction failed')\n"
        )
        scenarios = [{"name": "construct", "steps": []}]
        payload = _run_trusted_harness(
            dv.build_harness_source(source, _digest(source), scenarios),
            tmp_path,
        )

        scenario = payload["scenarios"][0]
        assert scenario["status"] == "NOT_RUN"
        assert "instantiation_failed" in scenario["detail"]

    def test_refuses_digest_mismatch(self) -> None:
        with pytest.raises(ValueError):
            dv.build_harness_source(CONTROL, "0" * 64, SCENARIOS)

    def test_refuses_empty_source(self) -> None:
        with pytest.raises(ValueError):
            dv.build_harness_source("  ", _digest("  "), SCENARIOS)

    def test_refuses_empty_scenarios(self) -> None:
        with pytest.raises(ValueError):
            dv.build_harness_source(CONTROL, _digest(CONTROL), [])

    def test_generated_harness_compiles(self) -> None:
        """Compile only — the harness is never executed here."""
        harness = dv.build_harness_source(CONTROL, _digest(CONTROL), SCENARIOS)
        ast.parse(harness)

    def test_harness_embeds_the_exact_source_and_digest(self) -> None:
        harness = dv.build_harness_source(CONTROL, _digest(CONTROL), SCENARIOS)
        assert json.dumps(CONTROL, ensure_ascii=False) in harness
        assert _digest(CONTROL) in harness

    def test_harness_verifies_the_digest_inside_the_container(self) -> None:
        harness = dv.build_harness_source(CONTROL, _digest(CONTROL), SCENARIOS)
        assert "staged_source_digest_mismatch" in harness
        assert "hashlib.sha256(data).hexdigest()" in harness

    def test_gui_stub_is_installed_before_the_app_is_imported(self) -> None:
        harness = dv.build_harness_source(CONTROL, _digest(CONTROL), SCENARIOS)
        assert harness.index('sys.modules["tkinter"] = tk') < harness.index(
            "spec.loader.exec_module(module)"
        )

    def test_application_main_block_cannot_run(self) -> None:
        harness = dv.build_harness_source(CONTROL, _digest(CONTROL), SCENARIOS)
        assert "spec_from_file_location" in harness
        assert "mainloop()" not in harness.split("spec.loader.exec_module")[1]

    # ---- independent scenario state -------------------------------------

    def test_stub_state_is_reset_between_scenarios(self) -> None:
        harness = dv.build_harness_source(CONTROL, _digest(CONTROL), SCENARIOS)
        assert "def reset_stub_state():" in harness
        for marker in ("del errors[:]", "del buttons[:]", "del entries[:]",
                       "del vars_created[:]", "bound.clear()"):
            assert marker in harness, marker

    def test_every_scenario_gets_a_new_instance(self) -> None:
        harness = dv.build_harness_source(CONTROL, _digest(CONTROL), SCENARIOS)
        call_site = "root, instance, instantiation_error = new_instance()"
        assert harness.count(call_site) == 1
        assert harness.index(call_site) > harness.index("for scenario in SCENARIOS:")

    def test_no_instance_is_created_before_the_loop(self) -> None:
        harness = dv.build_harness_source(CONTROL, _digest(CONTROL), SCENARIOS)
        before_loop = harness.split("for scenario in SCENARIOS:")[0]
        # The factory is only DEFINED before the loop; it is never CALLED there.
        assert "= new_instance()" not in before_loop

    def test_reset_does_not_rely_on_the_application_clear_button(self) -> None:
        harness = dv.build_harness_source(CONTROL, _digest(CONTROL), SCENARIOS)
        reset_body = harness.split("def reset_stub_state():")[1].split("def new_instance")[0]
        assert "click(" not in reset_body
        assert "scenario" not in reset_body.lower()


# ---------------------------------------------------------------------------
# 3. Result integrity — fail closed
# ---------------------------------------------------------------------------

def _valid_payload(digest, scenarios=None, count=None):
    scenarios = scenarios if scenarios is not None else [
        {"id": "alpha", "status": "PASS", "detail": ""},
        {"id": "beta", "status": "PASS", "detail": ""},
    ]
    return {
        "ok": True,
        "app_sha256": digest,
        "harness": "DraftVerificationHarness/1.1",
        "scenario_count": len(scenarios) if count is None else count,
        "scenarios": scenarios,
    }


class TestResultIntegrity:

    def test_parse_picks_the_marker_and_ignores_noise(self) -> None:
        payload = _valid_payload("a" * 64)
        stdout = "hello\n" + dv.RESULT_MARKER + json.dumps(payload) + "\nnoise\n"
        parsed, reason = dv.parse_harness_output(stdout)
        assert parsed == payload
        assert reason is None

    def test_parse_returns_none_without_a_marker(self) -> None:
        parsed, reason = dv.parse_harness_output("nothing here")
        assert parsed is None
        assert reason == "no_harness_result"

    def test_two_markers_are_ambiguous(self) -> None:
        payload = _valid_payload("a" * 64)
        line = dv.RESULT_MARKER + json.dumps(payload)
        parsed, reason = dv.parse_harness_output(line + "\n" + line)
        assert parsed is None
        assert reason == "ambiguous_result_multiple_markers"

    def test_a_forged_extra_marker_is_rejected(self) -> None:
        """An application print cannot smuggle a second 'result' past us."""
        real = _valid_payload("a" * 64)
        fake = _valid_payload("a" * 64, scenarios=[
            {"id": "alpha", "status": "PASS", "detail": ""},
            {"id": "beta", "status": "PASS", "detail": ""},
        ])
        stdout = (dv.RESULT_MARKER + json.dumps(fake) + "\n"
                  + "app noise\n"
                  + dv.RESULT_MARKER + json.dumps(real) + "\n")
        parsed, reason = dv.parse_harness_output(stdout)
        assert parsed is None
        assert reason == "ambiguous_result_multiple_markers"

    def test_malformed_payload_is_rejected(self) -> None:
        parsed, reason = dv.parse_harness_output(dv.RESULT_MARKER + "{not json")
        assert parsed is None
        assert reason == "result_payload_malformed"

    def test_valid_payload_passes_validation(self) -> None:
        digest = "a" * 64
        result = dv.validate_harness_result(_valid_payload(digest), digest, SCENARIOS)
        assert result["integrity"] == dv.INTEGRITY_VALID

    def test_digest_mismatch_invalidates(self) -> None:
        result = dv.validate_harness_result(_valid_payload("b" * 64), "a" * 64, SCENARIOS)
        assert result["integrity"] == dv.INTEGRITY_INVALID
        assert result["reason"] == "result_digest_mismatch"

    def test_missing_scenario_invalidates(self) -> None:
        digest = "a" * 64
        payload = _valid_payload(digest, scenarios=[
            {"id": "alpha", "status": "PASS", "detail": ""}
        ])
        result = dv.validate_harness_result(payload, digest, SCENARIOS)
        assert result["integrity"] == dv.INTEGRITY_INVALID
        assert result["reason"] == "result_scenario_count_mismatch"

    def test_extra_scenario_invalidates(self) -> None:
        digest = "a" * 64
        payload = _valid_payload(digest, scenarios=[
            {"id": "alpha", "status": "PASS", "detail": ""},
            {"id": "beta", "status": "PASS", "detail": ""},
            {"id": "gamma", "status": "PASS", "detail": ""},
        ])
        result = dv.validate_harness_result(payload, digest, SCENARIOS)
        assert result["integrity"] == dv.INTEGRITY_INVALID

    def test_duplicate_scenario_id_invalidates(self) -> None:
        digest = "a" * 64
        payload = _valid_payload(digest, scenarios=[
            {"id": "alpha", "status": "PASS", "detail": ""},
            {"id": "alpha", "status": "PASS", "detail": ""},
        ])
        result = dv.validate_harness_result(payload, digest, SCENARIOS)
        assert result["integrity"] == dv.INTEGRITY_INVALID
        assert result["reason"] == "result_scenario_duplicate"

    def test_unknown_status_invalidates(self) -> None:
        digest = "a" * 64
        payload = _valid_payload(digest, scenarios=[
            {"id": "alpha", "status": "MAYBE", "detail": ""},
            {"id": "beta", "status": "PASS", "detail": ""},
        ])
        result = dv.validate_harness_result(payload, digest, SCENARIOS)
        assert result["integrity"] == dv.INTEGRITY_INVALID
        assert result["reason"] == "result_status_unknown"

    def test_renamed_scenario_invalidates(self) -> None:
        digest = "a" * 64
        payload = _valid_payload(digest, scenarios=[
            {"id": "alpha", "status": "PASS", "detail": ""},
            {"id": "omega", "status": "PASS", "detail": ""},
        ])
        result = dv.validate_harness_result(payload, digest, SCENARIOS)
        assert result["integrity"] == dv.INTEGRITY_INVALID
        assert result["reason"] == "result_scenario_set_mismatch"

    def test_count_field_mismatch_invalidates(self) -> None:
        digest = "a" * 64
        payload = _valid_payload(digest, count=5)
        result = dv.validate_harness_result(payload, digest, SCENARIOS)
        assert result["integrity"] == dv.INTEGRITY_INVALID
        assert result["reason"] == "result_scenario_count_mismatch"

    def test_missing_scenario_count_invalidates(self) -> None:
        """The count is mandatory: without it the set cannot be cross-checked."""
        digest = "a" * 64
        payload = _valid_payload(digest)
        payload.pop("scenario_count")
        result = dv.validate_harness_result(payload, digest, SCENARIOS)
        assert result["integrity"] == dv.INTEGRITY_INVALID
        assert result["reason"] == "result_scenario_count_invalid"

    @pytest.mark.parametrize("bad_count", ["2", 2.0, None, True, False, [], {}])
    def test_non_integer_scenario_count_invalidates(self, bad_count) -> None:
        digest = "a" * 64
        payload = _valid_payload(digest)
        payload["scenario_count"] = bad_count
        result = dv.validate_harness_result(payload, digest, SCENARIOS)
        assert result["integrity"] == dv.INTEGRITY_INVALID
        assert result["reason"] == "result_scenario_count_invalid"


# ---------------------------------------------------------------------------
# 4. Functional verdict — never promoted from partial evidence
# ---------------------------------------------------------------------------

class TestFunctionalVerdict:

    def _scenarios(self, *statuses):
        return [
            {"id": SCENARIOS[i]["name"], "status": status, "detail": ""}
            for i, status in enumerate(statuses)
        ]

    def test_all_pass_is_pass(self) -> None:
        assert dv.decide_functional(
            dv.INTEGRITY_VALID, self._scenarios("PASS", "PASS"), ["alpha", "beta"]
        ) == dv.FUNCTIONAL_PASS

    def test_any_failure_is_fail(self) -> None:
        assert dv.decide_functional(
            dv.INTEGRITY_VALID, self._scenarios("PASS", "FAIL"), ["alpha", "beta"]
        ) == dv.FUNCTIONAL_FAIL

    def test_mandatory_unsupported_is_incomplete(self) -> None:
        assert dv.decide_functional(
            dv.INTEGRITY_VALID, self._scenarios("PASS", "NOT_SUPPORTED"),
            ["alpha", "beta"]
        ) == dv.FUNCTIONAL_INCOMPLETE

    def test_not_run_is_incomplete(self) -> None:
        assert dv.decide_functional(
            dv.INTEGRITY_VALID, self._scenarios("NOT_RUN", "PASS"), ["alpha", "beta"]
        ) == dv.FUNCTIONAL_INCOMPLETE

    def test_invalid_integrity_cannot_be_pass(self) -> None:
        assert dv.decide_functional(
            dv.INTEGRITY_INVALID, self._scenarios("PASS", "PASS"), ["alpha", "beta"]
        ) == dv.FUNCTIONAL_NOT_RUN

    def test_optional_gap_still_not_pass(self) -> None:
        """An unsupported OPTIONAL scenario must not silently become PASS."""
        assert dv.decide_functional(
            dv.INTEGRITY_VALID, self._scenarios("PASS", "NOT_SUPPORTED"), ["alpha"]
        ) == dv.FUNCTIONAL_INCOMPLETE

    def test_sandbox_failure_cannot_be_pass(self) -> None:
        """A failed container must never yield a functional PASS, even when the
        harness left a structurally valid all-PASS result behind."""
        assert dv.decide_functional(
            dv.INTEGRITY_VALID, self._scenarios("PASS", "PASS"),
            ["alpha", "beta"], sandbox_ok=False,
        ) == dv.FUNCTIONAL_NOT_RUN

    def test_sandbox_failure_overrides_a_failing_scenario_too(self) -> None:
        assert dv.decide_functional(
            dv.INTEGRITY_VALID, self._scenarios("FAIL", "PASS"),
            ["alpha", "beta"], sandbox_ok=False,
        ) == dv.FUNCTIONAL_NOT_RUN

    def test_sandbox_flag_defaults_to_success_for_existing_callers(self) -> None:
        assert dv.decide_functional(
            dv.INTEGRITY_VALID, self._scenarios("PASS", "PASS"), ["alpha", "beta"]
        ) == dv.FUNCTIONAL_PASS


# ---------------------------------------------------------------------------
# 5. Service — fake executor only
# ---------------------------------------------------------------------------

class _FakeExecutor:
    calls = []
    scenarios = None

    def __init__(self):
        self.backend_verified = True

    def run_source(self, source_bytes, source_sha256, resource_limits):
        _FakeExecutor.calls.append(
            {"bytes": source_bytes, "digest": source_sha256, "limits": resource_limits}
        )
        payload = {
            "ok": True,
            "app_sha256": _FakeExecutor.app_digest,
            "harness": "DraftVerificationHarness/1.1",
            "scenario_count": len(_FakeExecutor.scenarios),
            "scenarios": _FakeExecutor.scenarios,
        }
        return {
            "ok": True,
            "reason": None,
            "stdout": dv.RESULT_MARKER + json.dumps(payload) + "\n",
            "stderr": "",
            "source_digest_verified": True,
            "removal_verified": True,
        }


def _service(consent, scenarios, opt_in=True):
    _FakeExecutor.calls = []
    _FakeExecutor.scenarios = scenarios
    return dv.DraftVerificationService(
        consent=consent,
        executor_factory=_FakeExecutor,
        opt_in_reader=lambda: opt_in,
    )


def _verify(service, staged, token, scenarios):
    _FakeExecutor.app_digest = staged["digest"]
    return service.verify_draft(
        project_id=PROJECT,
        token=token,
        scenarios=scenarios,
        actor_id=ACTOR,
        session_id=SESSION,
    )


class TestService:

    def test_no_staged_proposal_never_calls_the_executor(self, monkeypatch) -> None:
        staging.reset_staging()
        service = _service(dv.DraftVerificationConsent(), [], opt_in=True)
        result = service.verify_draft(
            project_id=PROJECT, token="dv_x", scenarios=SCENARIOS,
            actor_id=ACTOR, session_id=SESSION,
        )
        assert result["ok"] is False
        assert result["reason"] == "no_staged_proposal"
        assert _FakeExecutor.calls == []

    def test_opt_in_is_enforced_at_dispatch(self, staged, monkeypatch) -> None:
        consent, minted = _consent_and_token(monkeypatch, staged["digest"])
        service = _service(consent, [], opt_in=False)
        result = _verify(service, staged, minted["token"], SCENARIOS)
        assert result["ok"] is False
        assert result["reason"] == "execution_disabled"
        assert _FakeExecutor.calls == []

    def test_runs_once_and_separates_the_two_digests(self, staged, monkeypatch) -> None:
        consent, minted = _consent_and_token(monkeypatch, staged["digest"])
        service = _service(consent, [
            {"id": "alpha", "status": "PASS", "detail": ""},
            {"id": "beta", "status": "PASS", "detail": ""},
        ])
        result = _verify(service, staged, minted["token"], SCENARIOS)

        assert len(_FakeExecutor.calls) == 1
        call = _FakeExecutor.calls[0]
        assert hashlib.sha256(call["bytes"]).hexdigest() == call["digest"]
        assert result["source_sha256"] == staged["digest"]
        assert result["harness_sha256"] == call["digest"]
        assert result["harness_sha256"] != result["source_sha256"]
        assert call["limits"]["max_memory_mb"] == 512
        assert result["sandbox"] == dv.SANDBOX_SUCCESS
        assert result["integrity"] == dv.INTEGRITY_VALID
        assert result["functional"] == dv.FUNCTIONAL_PASS

    def test_failing_scenario_yields_functional_fail(self, staged, monkeypatch) -> None:
        consent, minted = _consent_and_token(monkeypatch, staged["digest"])
        service = _service(consent, [
            {"id": "alpha", "status": "PASS", "detail": ""},
            {"id": "beta", "status": "FAIL", "detail": "display mismatch"},
        ])
        result = _verify(service, staged, minted["token"], SCENARIOS)
        assert result["sandbox"] == dv.SANDBOX_SUCCESS
        assert result["integrity"] == dv.INTEGRITY_VALID
        assert result["functional"] == dv.FUNCTIONAL_FAIL

    def test_unsupported_mandatory_scenario_cannot_pass(self, staged, monkeypatch) -> None:
        consent, minted = _consent_and_token(monkeypatch, staged["digest"])
        service = _service(consent, [
            {"id": "alpha", "status": "PASS", "detail": ""},
            {"id": "beta", "status": "NOT_SUPPORTED", "detail": "button_not_found"},
        ])
        result = _verify(service, staged, minted["token"], SCENARIOS)
        assert result["functional"] == dv.FUNCTIONAL_INCOMPLETE
        assert result["functional"] != dv.FUNCTIONAL_PASS

    def test_forged_result_is_rejected(self, staged, monkeypatch) -> None:
        consent, minted = _consent_and_token(monkeypatch, staged["digest"])

        class _Double(_FakeExecutor):
            def run_source(self, source_bytes, source_sha256, resource_limits):
                payload = _valid_payload(staged["digest"])
                line = dv.RESULT_MARKER + json.dumps(payload)
                return {"ok": True, "reason": None,
                        "stdout": line + "\n" + line + "\n", "stderr": ""}

        service = dv.DraftVerificationService(
            consent=consent, executor_factory=_Double, opt_in_reader=lambda: True
        )
        result = _verify(service, staged, minted["token"], SCENARIOS)
        assert result["ok"] is False
        assert result["integrity"] == dv.INTEGRITY_INVALID
        assert result["functional"] == dv.FUNCTIONAL_NOT_RUN

    def test_silent_executor_fails_closed(self, staged, monkeypatch) -> None:
        consent, minted = _consent_and_token(monkeypatch, staged["digest"])

        class _Silent(_FakeExecutor):
            def run_source(self, source_bytes, source_sha256, resource_limits):
                return {"ok": True, "reason": None, "stdout": "", "stderr": ""}

        service = dv.DraftVerificationService(
            consent=consent, executor_factory=_Silent, opt_in_reader=lambda: True
        )
        result = _verify(service, staged, minted["token"], SCENARIOS)
        assert result["ok"] is False
        assert result["reason"] == "no_harness_result"
        assert result["functional"] == dv.FUNCTIONAL_NOT_RUN

    def test_sandbox_failure_is_reported_separately_from_integrity(
        self, staged, monkeypatch
    ) -> None:
        """A failed container + a structurally valid result must stay separate:
        sandbox FAILED, integrity VALID, functional NOT_RUN."""
        consent, minted = _consent_and_token(monkeypatch, staged["digest"])

        class _SandboxFailed(_FakeExecutor):
            def run_source(self, source_bytes, source_sha256, resource_limits):
                payload = {
                    "ok": True,
                    "app_sha256": staged["digest"],
                    "harness": "DraftVerificationHarness/1.1",
                    "scenario_count": 2,
                    "scenarios": [
                        {"id": "alpha", "status": "PASS", "detail": ""},
                        {"id": "beta", "status": "PASS", "detail": ""},
                    ],
                }
                return {
                    "ok": False,
                    "reason": "removal_unverified",
                    "stdout": dv.RESULT_MARKER + json.dumps(payload) + "\n",
                    "stderr": "",
                }

        service = dv.DraftVerificationService(
            consent=consent, executor_factory=_SandboxFailed,
            opt_in_reader=lambda: True,
        )
        result = _verify(service, staged, minted["token"], SCENARIOS)

        assert result["sandbox"] == dv.SANDBOX_FAILED
        assert result["integrity"] == dv.INTEGRITY_VALID
        assert result["functional"] == dv.FUNCTIONAL_NOT_RUN
        assert result["ok"] is False

    def test_consent_is_consumed_even_before_execution(self, staged, monkeypatch) -> None:
        consent, minted = _consent_and_token(monkeypatch, staged["digest"])
        service = _service(consent, [
            {"id": "alpha", "status": "PASS", "detail": ""},
            {"id": "beta", "status": "PASS", "detail": ""},
        ])
        _verify(service, staged, minted["token"], SCENARIOS)
        second = _verify(service, staged, minted["token"], SCENARIOS)
        assert second["ok"] is False
        assert second["reason"] == "draft_capability_consumed"

    def test_cross_actor_verification_is_refused(self, staged, monkeypatch) -> None:
        consent, minted = _consent_and_token(monkeypatch, staged["digest"])
        service = _service(consent, [])
        _FakeExecutor.app_digest = staged["digest"]
        result = service.verify_draft(
            project_id=PROJECT, token=minted["token"], scenarios=SCENARIOS,
            actor_id="another_actor", session_id=SESSION,
        )
        assert result["ok"] is False
        assert result["reason"] == "draft_capability_binding_mismatch"
        assert _FakeExecutor.calls == []

    def test_draft_is_never_written(self, staged, monkeypatch) -> None:
        consent, minted = _consent_and_token(monkeypatch, staged["digest"])
        service = _service(consent, [
            {"id": "alpha", "status": "PASS", "detail": ""},
            {"id": "beta", "status": "PASS", "detail": ""},
        ])
        _verify(service, staged, minted["token"], SCENARIOS)
        pending = staging.pending_proposal(PROJECT)
        assert pending["status"] == "awaiting_approval"
        assert pending["writes_performed"] == 0


# ---------------------------------------------------------------------------
# 6. Disjointness and scope guards
# ---------------------------------------------------------------------------

class TestDisjointness:

    def _module_source(self) -> str:
        path = os.path.join(
            _PROJECT_ROOT, "core", "execution", "draft_verification_v1.py"
        )
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def test_module_never_touches_the_save_ledger(self) -> None:
        """Scan CODE, not prose: docstrings legitimately name the ledger."""
        tree = ast.parse(self._module_source())
        identifiers = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                identifiers.add(node.id)
            elif isinstance(node, ast.Attribute):
                identifiers.add(node.attr)
        for forbidden in (
            "ExecutionApprovalLedger",
            "approve_staged_file",
            "create_project_code_file",
            "record_trusted_local_consent",
            "mint_execution_capability",
        ):
            assert forbidden not in identifiers, (
                "draft verification must not reach the save path: %r" % forbidden
            )

    def test_module_imports_only_standard_library_at_module_level(self) -> None:
        tree = ast.parse(self._module_source())
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert imported <= {"ast", "hashlib", "hmac", "json", "os", "re", "secrets",
                            "threading", "time", "__future__"}

    def test_module_does_not_import_the_execution_contract(self) -> None:
        """07b0 forbids a production edge to the declarative contract module.

        Checked on the IMPORT graph, not on prose: the docstring legitimately
        explains why the import is avoided.
        """
        tree = ast.parse(self._module_source())
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
        assert not any("execution_contract_v1" in name for name in modules)


# ---------------------------------------------------------------------------
# 7. Tier 1 criteria echo — raw text preservation
# ---------------------------------------------------------------------------

class TestCriteriaEchoRawText:

    def _chat(self, monkeypatch, tmp_path, session):
        from core.chat.chat_architect import ChatArchitect
        from core.project.project_workspace_v1 import project_workspace

        documents = tmp_path / "documents"
        documents.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            project_workspace, "subdir", lambda project_id, name: str(documents)
        )
        staging.reset_staging()

        chat = object.__new__(ChatArchitect)
        chat.context = {"trusted_local_authorization": dict(AUTH, project_id=session)}
        chat._generate_code_with_coder = lambda text: CONTROL
        return chat

    def test_raw_text_restores_the_numbered_criteria(self, tmp_path, monkeypatch) -> None:
        session = "project_echo_tests"
        chat = self._chat(monkeypatch, tmp_path, session)
        raw = (
            "یک برنامه جدید بساز و فایل app.py را تولید کن.\n\n"
            "۱. دکمه C باید همه چیز را پاک کند.\n"
            "۲. `5 + 2 =` باید `7` بدهد.\n"
            "۳. تقسیم بر صفر باید خطا بدهد.\n"
        )
        normalized = " ".join(raw.split())
        try:
            message = chat._authorized_code_file_creation(
                normalized, session, raw_text=raw
            )
            assert "معیارهای تأییدشدهٔ شما" in message
            assert "5 + 2 =` باید `7`" in message
        finally:
            staging.reset_staging()

    def test_without_raw_text_the_echo_degrades_honestly(self, tmp_path, monkeypatch) -> None:
        session = "project_echo_tests2"
        chat = self._chat(monkeypatch, tmp_path, session)
        try:
            message = chat._authorized_code_file_creation(
                "یک برنامه جدید بساز و فایل app.py را تولید کن. ۱. اول ۲. دوم",
                session,
            )
            assert "NOT_RUN" in message
            assert "معیارهای تأییدشدهٔ شما" not in message
        finally:
            staging.reset_staging()
