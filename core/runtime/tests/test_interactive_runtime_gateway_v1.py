"""InteractiveRuntimeGateway V1 — isolated self-checks.

Proves the runtime-owned interactive entry:

    1. a successful full flow reaches `admitted`
    2. an invalid request is refused at G1
    2b. the gateway DELEGATES materialisation to the single producer (G1M) and
        never assembles the material itself
    2c. a material failure is refused / errored at G1M and does NOT burn the nonce
    3. a nonce failure does NOT burn the nonce
    4. an issuer failure is refused / mapped
    5. an adapter failure consumes the token (the act is spent)
    6. an executor / governance denial is preserved VERBATIM
    7. an exception is mapped to `error` with `error_type`
    8. the token is NEVER exposed
    9. no governance dependency; no app.py / conversation coupling
   10. the outputs are immutable
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import core.runtime.interactive_runtime_gateway_v1 as gateway_module
from core.runtime.interactive_runtime_gateway_v1 import (
    ALLOWED_REQUEST_FIELDS,
    FORBIDDEN_REQUEST_FIELDS,
    GatewayResult,
    InteractiveGatewayError,
    InteractiveGatewayRequest,
    InteractiveRuntimeGateway,
    STAGE_G1,
    STAGE_G1M,
    STAGE_G3,
    STAGE_G4,
    STAGE_G5,
    STATUS_ADMITTED,
    STATUS_DENIED,
    STATUS_ERROR,
    STATUS_REFUSED,
    build_gateway_request,
    interactive_runtime_gateway,
)
from core.runtime.claim_request_material_adapter_v1 import (
    to_claim_request_material as _real_to_claim_request_material,
)
from core.runtime.human_act_token_v1 import human_act_token_ledger
from core.runtime.interaction_nonce_v1 import (
    InteractionNonce,
    interaction_nonce_state,
    issue_interaction_nonce,
)


MODULE = Path(__file__).resolve().parents[1] / "interactive_runtime_gateway_v1.py"

ROOT = Path(__file__).resolve().parents[3]

SESSION = "session_alpha"


def _request(gateway, **overrides):

    fields = {
        "session_reference": SESSION,
        "raw_statement": "a bed exists in this space",
        "turn_kind": "TEACHING_STATEMENT",
        "language": "en",
        "interaction_nonce": gateway.request_nonce(SESSION),
    }

    fields.update(overrides)

    return build_gateway_request(**fields)


def _imported_roots(path):

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    roots = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            roots.extend(alias.name for alias in node.names)

        elif isinstance(node, ast.ImportFrom):

            if node.module:

                roots.append(node.module)

    return roots


# The real interactive source (the transport request) carries NO claim-type
# hint, so the gateway's real material has `claim_type_hint = None`. To exercise
# the SUCCESSFUL pipeline end to end, a test supplies a material that DOES carry
# an advisory hint. The material is REAL (built by the real adapter); only the
# source it is built from is supplied by the test.
HINTED_CLAIM_TYPE = "existence"


@pytest.fixture
def hinted_material(monkeypatch):
    """Make the single producer yield a material that carries a claim-type hint."""

    def _producer(source):

        return _real_to_claim_request_material(
            {
                "raw_statement": source.raw_statement,
                "claim_type_hint": HINTED_CLAIM_TYPE,
            }
        )

    monkeypatch.setattr(gateway_module, "to_claim_request_material", _producer)

    return _producer


# ==========================================================
# 1. the full flow
# ==========================================================

def test_a_successful_full_flow_is_admitted(hinted_material):

    gateway = InteractiveRuntimeGateway()

    result = gateway.submit(_request(gateway))

    assert result.completed is True

    assert result.status == STATUS_ADMITTED

    assert result.stage == STAGE_G5

    assert result.lifecycle_result is not None

    assert result.lifecycle_result.claim_reference.startswith("clm_")

    assert result.lifecycle_result.candidate_reference.startswith("kcd_")


def test_the_singleton_gateway_works(hinted_material):

    result = interactive_runtime_gateway.submit(
        _request(interactive_runtime_gateway)
    )

    assert result.completed is True


def test_the_nonce_is_consumed_by_a_successful_flow():

    gateway = InteractiveRuntimeGateway()

    request = _request(gateway)

    gateway.submit(request)

    assert interaction_nonce_state(request.interaction_nonce) == "consumed"


def test_a_mapping_request_is_accepted(hinted_material):

    gateway = InteractiveRuntimeGateway()

    result = gateway.submit(
        {
            "session_reference": SESSION,
            "raw_statement": "a bed exists",
            "turn_kind": "CORRECTION",
            "language": "fa",
            "interaction_nonce": gateway.request_nonce(SESSION),
        }
    )

    assert result.completed is True


# ==========================================================
# 1b. materialisation (G1M) — the gateway delegates, never assembles
# ==========================================================

def test_the_material_adapter_is_called(monkeypatch):

    calls = []

    def _spy(source):

        calls.append(source)

        return _real_to_claim_request_material(source)

    monkeypatch.setattr(gateway_module, "to_claim_request_material", _spy)

    gateway = InteractiveRuntimeGateway()

    gateway.submit(_request(gateway))

    assert len(calls) == 1

    assert isinstance(calls[0], InteractiveGatewayRequest)


def test_the_gateway_does_not_assemble_the_material():

    source = MODULE.read_text(encoding="utf-8")

    tree = ast.parse(source, filename=str(MODULE))

    # 1. the gateway never CALLS a material constructor
    for node in ast.walk(tree):

        if isinstance(node, ast.Call):

            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)

            assert name != "ClaimRequestMaterial", "the gateway constructs a material"

    # 2. it imports the producer FUNCTION and the error type — never the class
    imported = set()

    for node in ast.walk(tree):

        if isinstance(node, ast.ImportFrom):

            imported.update(alias.name for alias in node.names)

    assert "to_claim_request_material" in imported

    assert "ClaimRequestMaterialError" in imported

    assert "ClaimRequestMaterial" not in imported

    # 3. no claim-type constant / fallback survives
    assert "INTERACTIVE_CLAIM_TYPE" not in source

    # 4. the producer is called with the request object — never a constructed
    #    statement mapping (a dict literal)
    for node in ast.walk(tree):

        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == (
            "to_claim_request_material"
        ):

            for argument in node.args:

                assert not isinstance(argument, ast.Dict), (
                    "the gateway builds a statement mapping"
                )


def test_a_material_refusal_does_not_burn_the_nonce(monkeypatch):

    def _refuse(source):

        raise gateway_module.ClaimRequestMaterialError("material refused")

    monkeypatch.setattr(gateway_module, "to_claim_request_material", _refuse)

    gateway = InteractiveRuntimeGateway()

    request = _request(gateway)

    before = human_act_token_ledger.count()

    result = gateway.submit(request)

    assert result.status == STATUS_REFUSED

    assert result.stage == STAGE_G1M

    # the nonce is untouched and NO token was issued
    assert interaction_nonce_state(request.interaction_nonce) == "issued"

    assert human_act_token_ledger.count() == before


def test_a_material_error_is_mapped_to_error(monkeypatch):

    def _boom(source):

        raise RuntimeError("material adapter exploded")

    monkeypatch.setattr(gateway_module, "to_claim_request_material", _boom)

    gateway = InteractiveRuntimeGateway()

    request = _request(gateway)

    before = human_act_token_ledger.count()

    result = gateway.submit(request)

    assert result.status == STATUS_ERROR

    assert result.stage == STAGE_G1M

    assert result.error_type == "RuntimeError"

    assert interaction_nonce_state(request.interaction_nonce) == "issued"

    assert human_act_token_ledger.count() == before


def test_an_absent_hint_is_forwarded_verbatim(monkeypatch):

    """No fallback: the material's `claim_type_hint` is passed through as-is."""

    from core.runtime.lifecycle_executor_v1 import LifecycleResult

    captured = {}

    class _CapturingExecutor:

        def run(self, **kwargs):

            captured.update(kwargs)

            return LifecycleResult(
                completed=True,
                stage="A8_admission",
                status="admitted",
                reason="captured",
            )

    monkeypatch.setattr(gateway_module, "LifecycleExecutor", _CapturingExecutor)

    gateway = InteractiveRuntimeGateway()

    gateway.submit(_request(gateway))

    # the real material carries NO hint; the gateway substituted nothing
    assert captured["proposal_fields"]["proposed_claim_type"] is None


def test_the_real_interactive_material_carries_no_hint():

    """The documented consequence of removing the claim-type fallback.

    The interactive source (the transport request) carries no claim-type hint, so
    the material's `claim_type_hint` is None; with the fallback removed, governance
    refuses the absent type at mint. The exit condition is a conversation-provided
    hint (see CLAIM_TYPE_OWNERSHIP_BOUNDARY_DECISION_V1.md).
    """

    gateway = InteractiveRuntimeGateway()

    result = gateway.submit(_request(gateway))

    assert result.status == STATUS_ERROR

    assert "unknown claim_type" in result.reason


# ==========================================================
# 2. G1 validation
# ==========================================================

def test_a_forbidden_field_is_refused_at_g1():

    gateway = InteractiveRuntimeGateway()

    for field in ("confidence", "truth", "claim_id", "licence_id", "proposal",
                  "proposal_fields", "auv2", "projection", "scope", "status"):

        assert field in FORBIDDEN_REQUEST_FIELDS

        payload = {
            "session_reference": SESSION,
            "raw_statement": "a bed exists",
            "turn_kind": "TEACHING_STATEMENT",
            "language": "en",
            "interaction_nonce": gateway.request_nonce(SESSION),
            field: "forged",
        }

        result = gateway.submit(payload)

        assert result.status == STATUS_REFUSED

        assert result.stage == STAGE_G1

        assert "may not carry" in result.reason


def test_an_unknown_field_is_refused_at_g1():

    gateway = InteractiveRuntimeGateway()

    payload = {
        "session_reference": SESSION,
        "raw_statement": "a bed exists",
        "turn_kind": "TEACHING_STATEMENT",
        "language": "en",
        "interaction_nonce": gateway.request_nonce(SESSION),
        "made_up": 1,
    }

    result = gateway.submit(payload)

    assert result.status == STATUS_REFUSED

    assert result.stage == STAGE_G1

    assert "unknown gateway request field" in result.reason


def test_a_non_request_is_refused_at_g1():

    gateway = InteractiveRuntimeGateway()

    for value in ("request", 42, None, ["x"]):

        result = gateway.submit(value)

        assert result.status == STATUS_REFUSED

        assert result.stage == STAGE_G1


def test_the_builder_rejects_forbidden_and_unknown_fields():

    with pytest.raises(InteractiveGatewayError):

        build_gateway_request(
            session_reference=SESSION,
            raw_statement="x",
            turn_kind="TEACHING_STATEMENT",
            language="en",
            interaction_nonce=issue_interaction_nonce(SESSION),
            truth="yes",
        )

    with pytest.raises(InteractiveGatewayError):

        build_gateway_request(
            session_reference=SESSION,
            raw_statement="x",
            turn_kind="TEACHING_STATEMENT",
            language="en",
            interaction_nonce=issue_interaction_nonce(SESSION),
            made_up=1,
        )


def test_the_request_carries_exactly_five_allowed_fields():

    assert ALLOWED_REQUEST_FIELDS == (
        "session_reference",
        "raw_statement",
        "turn_kind",
        "language",
        "interaction_nonce",
    )


def test_the_request_is_immutable():

    request = _request(InteractiveRuntimeGateway())

    with pytest.raises(FrozenInstanceError):

        request.turn_kind = "CORRECTION"


def test_a_governance_identity_session_is_rejected():

    with pytest.raises(InteractiveGatewayError):

        build_gateway_request(
            session_reference="clm_x",
            raw_statement="x",
            turn_kind="TEACHING_STATEMENT",
            language="en",
            interaction_nonce=issue_interaction_nonce(SESSION),
        )


# ==========================================================
# 3. nonce failure does not burn the nonce
# ==========================================================

def test_a_nonce_failure_does_not_burn_the_nonce():

    gateway = InteractiveRuntimeGateway()

    nonce = gateway.request_nonce(SESSION)

    # a wrong turn kind is refused by the issuer BEFORE consuming the nonce
    result = gateway.submit(
        build_gateway_request(
            session_reference=SESSION,
            raw_statement="a bed exists",
            turn_kind="QUESTION",
            language="en",
            interaction_nonce=nonce,
        )
    )

    assert result.status == STATUS_REFUSED

    assert result.stage == STAGE_G3

    assert interaction_nonce_state(nonce) == "issued"


def test_a_session_mismatch_does_not_burn_the_nonce():

    gateway = InteractiveRuntimeGateway()

    nonce = gateway.request_nonce(SESSION)

    result = gateway.submit(
        build_gateway_request(
            session_reference="session_other",
            raw_statement="a bed exists",
            turn_kind="TEACHING_STATEMENT",
            language="en",
            interaction_nonce=nonce,
        )
    )

    assert result.status == STATUS_REFUSED

    assert result.stage == STAGE_G3

    assert interaction_nonce_state(nonce) == "issued"


# ==========================================================
# 4. issuer failure
# ==========================================================

def test_an_unknown_nonce_is_refused_at_g3():

    gateway = InteractiveRuntimeGateway()

    forged = InteractionNonce(
        nonce_reference="inx_never_issued",
        session_reference=SESSION,
    )

    result = gateway.submit(
        build_gateway_request(
            session_reference=SESSION,
            raw_statement="a bed exists",
            turn_kind="TEACHING_STATEMENT",
            language="en",
            interaction_nonce=forged,
        )
    )

    assert result.status == STATUS_REFUSED

    assert result.stage == STAGE_G3


def test_an_issuer_exception_is_mapped_to_error(monkeypatch):

    class _RaisingIssuer:

        def issue(self, event):

            raise RuntimeError("issuer exploded")

    monkeypatch.setattr(gateway_module, "HumanActIssuer", _RaisingIssuer)

    gateway = InteractiveRuntimeGateway()

    result = gateway.submit(_request(gateway))

    assert result.status == STATUS_ERROR

    assert result.error_type == "RuntimeError"


# ==========================================================
# 5. adapter failure consumes the token
# ==========================================================

def test_an_adapter_failure_consumes_the_token(monkeypatch):

    def _raise(*args, **kwargs):

        raise gateway_module.ConversationAdapterError("adapter refused")

    monkeypatch.setattr(gateway_module, "to_claim_request_input", _raise)

    gateway = InteractiveRuntimeGateway()

    request = _request(gateway)

    result = gateway.submit(request)

    assert result.status == STATUS_REFUSED

    assert result.stage == STAGE_G4

    # the act is spent: the nonce was consumed at G3
    assert interaction_nonce_state(request.interaction_nonce) == "consumed"


# ==========================================================
# 6. executor / governance denial preserved verbatim
# ==========================================================

def test_an_executor_denial_is_preserved(monkeypatch):

    from core.runtime.lifecycle_executor_v1 import LifecycleResult

    denial = LifecycleResult(
        completed=False,
        stage="A5_licence",
        status="denied",
        reason="executor denied the act",
    )

    class _DenyingExecutor:

        def run(self, **kwargs):

            return denial

    monkeypatch.setattr(gateway_module, "LifecycleExecutor", _DenyingExecutor)

    gateway = InteractiveRuntimeGateway()

    result = gateway.submit(_request(gateway))

    assert result.status == STATUS_DENIED

    assert result.stage == STAGE_G5

    assert result.reason == "executor denied the act"


def test_a_governance_denial_is_preserved_verbatim(monkeypatch):

    from core.runtime.lifecycle_executor_v1 import LifecycleResult

    governance_reason = (
        "transition 'unlicensed_hypothesis' -> 'heuristic_candidate' is not defined"
    )

    denial = LifecycleResult(
        completed=False,
        stage="A5_licence",
        status="denied",
        reason=governance_reason,
    )

    class _DenyingExecutor:

        def run(self, **kwargs):

            return denial

    monkeypatch.setattr(gateway_module, "LifecycleExecutor", _DenyingExecutor)

    gateway = InteractiveRuntimeGateway()

    result = gateway.submit(_request(gateway))

    assert result.reason == governance_reason


def test_an_executor_error_status_is_mapped(monkeypatch):

    from core.runtime.lifecycle_executor_v1 import LifecycleResult

    failure = LifecycleResult(
        completed=False,
        stage="A6_mint",
        status="error",
        reason="unknown source_type: 'x'",
        error_type="ClaimVocabularyError",
    )

    class _FailingExecutor:

        def run(self, **kwargs):

            return failure

    monkeypatch.setattr(gateway_module, "LifecycleExecutor", _FailingExecutor)

    gateway = InteractiveRuntimeGateway()

    result = gateway.submit(_request(gateway))

    assert result.status == STATUS_ERROR

    assert result.error_type == "ClaimVocabularyError"


# ==========================================================
# 7. exception mapping
# ==========================================================

def test_an_executor_exception_is_mapped_to_error(monkeypatch):

    class _RaisingExecutor:

        def run(self, **kwargs):

            raise ValueError("executor exploded")

    monkeypatch.setattr(gateway_module, "LifecycleExecutor", _RaisingExecutor)

    gateway = InteractiveRuntimeGateway()

    result = gateway.submit(_request(gateway))

    assert result.status == STATUS_ERROR

    assert result.stage == STAGE_G5

    assert result.error_type == "ValueError"


# ==========================================================
# 8. the token is never exposed
# ==========================================================

def test_the_token_is_never_exposed():

    gateway = InteractiveRuntimeGateway()

    result = gateway.submit(_request(gateway))

    payload = result.to_dict()

    blob = repr(payload).lower()

    assert "hat_" not in blob

    assert "token_reference" not in blob

    for field in ("token", "human_act_token", "intent"):

        assert field not in payload


def test_the_gateway_result_declares_no_authority():

    assert GatewayResult.CREATES_IDENTITY is False

    assert GatewayResult.DECIDES_TRUTH is False

    assert GatewayResult.PERSISTS is False

    assert InteractiveRuntimeGateway.CREATES_IDENTITY is False


def test_the_result_is_immutable():

    gateway = InteractiveRuntimeGateway()

    result = gateway.submit(_request(gateway))

    with pytest.raises(FrozenInstanceError):

        result.completed = False


def test_an_unknown_stage_or_status_is_rejected():

    with pytest.raises(InteractiveGatewayError):

        GatewayResult(True, "G9", STATUS_ADMITTED, "x")

    with pytest.raises(InteractiveGatewayError):

        GatewayResult(True, STAGE_G1, "made_up", "x")


# ==========================================================
# 9. dependency direction
# ==========================================================

def test_no_governance_dependency():

    roots = _imported_roots(MODULE)

    for root in roots:

        assert not root.startswith("core.governance"), "imported %r" % (root,)

    for forbidden in (
        "core.conversation",
        "core.vision",
        "core.knowledge",
    ):

        assert forbidden not in roots


def test_the_gateway_imports_only_runtime_modules():

    roots = _imported_roots(MODULE)

    core_roots = sorted({r for r in roots if r.startswith("core.")})

    assert core_roots == [
        "core.runtime.claim_request_material_adapter_v1",
        "core.runtime.conversation_adapter_v1",
        "core.runtime.human_act_issuer_v1",
        "core.runtime.interaction_nonce_v1",
        "core.runtime.lifecycle_executor_v1",
    ]


def test_app_py_does_not_import_the_gateway():

    source = (ROOT / "app.py").read_text(encoding="utf-8", errors="ignore")

    assert "interactive_runtime_gateway" not in source


def test_no_conversation_module_imports_the_gateway():

    offenders = []

    for path in sorted((ROOT / "core" / "conversation").rglob("*.py")):

        for root in _imported_roots(path):

            if "interactive_runtime_gateway" in root:

                offenders.append(path.name)

    assert offenders == []


def test_the_gateway_does_not_persist():

    source = MODULE.read_text(encoding="utf-8")

    for token in ("open(", "json.dump", "pickle", "sqlite3", "shelve"):

        assert token not in source
