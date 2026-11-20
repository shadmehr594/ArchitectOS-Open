"""HumanActIssuer V1 — isolated self-checks.

Proves the single runtime issuer:

    1. a valid event issues a HumanActToken
    2. the nonce is consumed only after every validation passes
    3. a replay is rejected; a wrong session is rejected
    4. an unknown / expired nonce is rejected
    5. a wrong turn kind is rejected; a missing session / nonce is rejected
    6. a FAILED validation never consumes the nonce
    7. no governance dependency; no identity generation
    8. the issued token remains one-shot
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.runtime.human_act_issuer_v1 import (
    HumanActIssuer,
    HumanActIssuerError,
    HumanActIssuerEvent,
    REASON_MISSING_NONCE,
    REASON_MISSING_SESSION,
    REASON_NONCE_CONSUMED,
    REASON_NONCE_EXPIRED,
    REASON_NOT_AN_EVENT,
    REASON_SESSION_MISMATCH,
    REASON_UNKNOWN_NONCE,
    REASON_UNKNOWN_TURN_KIND,
    human_act_issuer,
)
from core.runtime.human_act_token_v1 import (
    HumanActToken,
    HumanActTokenError,
    consume_human_act_token,
    human_act_token_state,
)
from core.runtime.interaction_nonce_v1 import (
    InteractionNonce,
    STATE_ISSUED,
    expire_interaction_nonce,
    interaction_nonce_state,
    issue_interaction_nonce,
)


MODULE = Path(__file__).resolve().parents[1] / "human_act_issuer_v1.py"

SESSION = "session_alpha"

OTHER_SESSION = "session_beta"


def _event(nonce, **overrides):

    fields = {
        "turn_kind": "TEACHING_STATEMENT",
        "language": "en",
        "session_reference": SESSION,
        "interaction_nonce": nonce,
    }

    fields.update(overrides)

    return HumanActIssuerEvent(**fields)


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


def _called_names(path):

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    names = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Call):

            func = node.func

            if isinstance(func, ast.Name):

                names.append(func.id)

            elif isinstance(func, ast.Attribute):

                names.append(func.attr)

    return names


# ==========================================================
# 1. valid event
# ==========================================================

def test_a_valid_event_issues_a_token():

    nonce = issue_interaction_nonce(SESSION)

    token = HumanActIssuer().issue(_event(nonce))

    assert isinstance(token, HumanActToken)

    assert token.state == STATE_ISSUED

    assert token.turn_kind == "TEACHING_STATEMENT"

    assert token.language == "en"

    assert token.session_reference == SESSION


def test_the_shared_issuer_singleton_works():

    nonce = issue_interaction_nonce(SESSION)

    token = human_act_issuer.issue(_event(nonce, turn_kind="CORRECTION"))

    assert token.turn_kind == "CORRECTION"


def test_the_event_carries_exactly_the_required_fields():

    nonce = issue_interaction_nonce(SESSION)

    payload = _event(nonce).to_dict()

    for field in ("turn_kind", "language", "session_reference", "interaction_nonce"):

        assert field in payload


def test_the_event_is_immutable():

    nonce = issue_interaction_nonce(SESSION)

    event = _event(nonce)

    with pytest.raises(FrozenInstanceError):

        event.turn_kind = "CORRECTION"


# ==========================================================
# 2. nonce consumption
# ==========================================================

def test_the_nonce_is_consumed_after_success():

    nonce = issue_interaction_nonce(SESSION)

    assert interaction_nonce_state(nonce) == STATE_ISSUED

    HumanActIssuer().issue(_event(nonce))

    assert interaction_nonce_state(nonce) == "consumed"


def test_a_replayed_nonce_is_rejected():

    nonce = issue_interaction_nonce(SESSION)

    HumanActIssuer().issue(_event(nonce))

    with pytest.raises(HumanActIssuerError) as error:

        HumanActIssuer().issue(_event(nonce))

    assert REASON_NONCE_CONSUMED in str(error.value)


# ==========================================================
# 3-5. rejections
# ==========================================================

def test_a_wrong_session_is_rejected():

    nonce = issue_interaction_nonce(SESSION)

    with pytest.raises(HumanActIssuerError) as error:

        HumanActIssuer().issue(_event(nonce, session_reference=OTHER_SESSION))

    assert REASON_SESSION_MISMATCH in str(error.value)

    # the nonce is untouched by a mismatched attempt
    assert interaction_nonce_state(nonce) == STATE_ISSUED


def test_an_unknown_nonce_is_rejected():

    forged = InteractionNonce(
        nonce_reference="inx_never_issued",
        session_reference=SESSION,
    )

    with pytest.raises(HumanActIssuerError) as error:

        HumanActIssuer().issue(_event(forged))

    assert REASON_UNKNOWN_NONCE in str(error.value)


def test_an_expired_nonce_is_rejected():

    nonce = issue_interaction_nonce(SESSION)

    expire_interaction_nonce(nonce)

    with pytest.raises(HumanActIssuerError) as error:

        HumanActIssuer().issue(_event(nonce))

    assert REASON_NONCE_EXPIRED in str(error.value)


def test_a_wrong_turn_kind_is_rejected():

    for turn_kind in ("QUESTION", "INSTRUCTION", "NORMAL_CONVERSATION", "UNKNOWN"):

        nonce = issue_interaction_nonce(SESSION)

        with pytest.raises(HumanActIssuerError) as error:

            HumanActIssuer().issue(_event(nonce, turn_kind=turn_kind))

        assert REASON_UNKNOWN_TURN_KIND in str(error.value)

        assert interaction_nonce_state(nonce) == STATE_ISSUED


def test_a_missing_session_is_rejected():

    nonce = issue_interaction_nonce(SESSION)

    for value in (None, "", "   "):

        with pytest.raises(HumanActIssuerError) as error:

            HumanActIssuer().issue(_event(nonce, session_reference=value))

        assert REASON_MISSING_SESSION in str(error.value)


def test_a_missing_nonce_is_rejected():

    with pytest.raises(HumanActIssuerError) as error:

        HumanActIssuer().issue(_event(None))

    assert REASON_MISSING_NONCE in str(error.value)


def test_a_non_event_is_rejected():

    for value in (None, "event", {"turn_kind": "TEACHING_STATEMENT"}, 42):

        with pytest.raises(HumanActIssuerError) as error:

            HumanActIssuer().issue(value)

        assert REASON_NOT_AN_EVENT in str(error.value)


# ==========================================================
# 6. a failed validation never consumes the nonce
# ==========================================================

def test_a_failed_validation_does_not_consume_the_nonce():

    nonce = issue_interaction_nonce(SESSION)

    with pytest.raises(HumanActIssuerError):

        HumanActIssuer().issue(_event(nonce, turn_kind="QUESTION"))

    assert interaction_nonce_state(nonce) == STATE_ISSUED

    # a corrected event then succeeds
    token = HumanActIssuer().issue(_event(nonce))

    assert isinstance(token, HumanActToken)

    assert interaction_nonce_state(nonce) == "consumed"


# ==========================================================
# 7. dependency / identity generation
# ==========================================================

def test_no_governance_dependency():

    roots = _imported_roots(MODULE)

    for root in roots:

        assert not root.startswith("core.governance"), "imported %r" % (root,)

    for forbidden in (
        "core.governance",
        "core.conversation",
        "core.vision",
        "core.knowledge",
    ):

        assert forbidden not in roots


def test_the_issuer_imports_only_runtime_modules():

    roots = _imported_roots(MODULE)

    core_roots = sorted({r for r in roots if r.startswith("core.")})

    assert core_roots == [
        "core.runtime.human_act_token_v1",
        "core.runtime.interaction_nonce_v1",
    ]


def test_no_identity_generation():

    called = _called_names(MODULE)

    for name in (
        "uuid4",
        "uuid1",
        "mint_id",
        "new_claim_id",
        "new_licence_id",
        "new_derivation_event_id",
        "new_endorsement_event_id",
        "build_proposal",
        "mint_claim",
        "mint_licence_record",
        "record_derivation_event",
        "record_endorsement_event",
        "build_knowledge_candidate",
    ):

        assert name not in called


def test_the_module_does_not_persist():

    source = MODULE.read_text(encoding="utf-8")

    for token in ("open(", "json.dump", "pickle", "sqlite3", "shelve"):

        assert token not in source


# ==========================================================
# 8. the issued token remains one-shot
# ==========================================================

def test_the_issued_token_remains_one_shot():

    nonce = issue_interaction_nonce(SESSION)

    token = HumanActIssuer().issue(_event(nonce))

    consumed = consume_human_act_token(token)

    assert consumed.state == "consumed"

    assert human_act_token_state(token.token_reference) == "consumed"

    with pytest.raises(HumanActTokenError):

        consume_human_act_token(token)


def test_no_confidence_truth_or_status_is_transferred():

    nonce = issue_interaction_nonce(SESSION)

    token = HumanActIssuer().issue(_event(nonce))

    payload = token.to_dict()

    for field in ("truth", "confidence", "certainty", "approval", "status"):

        assert field not in payload
