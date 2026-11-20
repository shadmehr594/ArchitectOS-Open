"""HumanActToken V1 — isolated self-checks.

Proves the runtime-owned one-shot human-act boundary:

    1. issue creates a valid, runtime-local token
    2. the token is immutable and declares no authority
    3. consume works exactly once; a second consume is rejected
    4. release works exactly once; consuming a released token is rejected
    5. unknown / forged tokens are rejected
    6. governance identity prefixes are rejected
    7. no governance import, no governance identity generation
    8. no confidence / truth / approval / status field
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.runtime.human_act_token_v1 import (
    ALLOWED_TURN_KINDS,
    FORBIDDEN_REFERENCE_PREFIXES,
    HumanActToken,
    HumanActTokenError,
    HumanActTokenLedger,
    REASON_CONSUMED,
    REASON_FORBIDDEN_REFERENCE,
    REASON_NOT_A_TOKEN,
    REASON_RELEASED,
    REASON_UNKNOWN,
    REASON_UNKNOWN_STATE,
    REASON_UNKNOWN_TURN_KIND,
    REFERENCE_PREFIX,
    STATES,
    STATE_CONSUMED,
    STATE_ISSUED,
    STATE_RELEASED,
    consume_human_act_token,
    human_act_token_ledger,
    human_act_token_state,
    issue_human_act_token,
    new_token_reference,
    release_human_act_token,
)


MODULE = Path(__file__).resolve().parents[1] / "human_act_token_v1.py"


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
# 1. issue
# ==========================================================

def test_issue_creates_a_valid_runtime_local_token():

    token = issue_human_act_token(turn_kind="TEACHING_STATEMENT", language="fa")

    assert isinstance(token, HumanActToken)

    assert token.token_reference.startswith(REFERENCE_PREFIX)

    assert token.turn_kind == "TEACHING_STATEMENT"

    assert token.language == "fa"

    assert token.state == STATE_ISSUED

    assert human_act_token_state(token.token_reference) == STATE_ISSUED


def test_issued_references_are_unique():

    first = issue_human_act_token(turn_kind="CORRECTION")

    second = issue_human_act_token(turn_kind="CORRECTION")

    assert first.token_reference != second.token_reference


def test_the_reference_prefix_is_not_a_governance_prefix():

    for prefix in FORBIDDEN_REFERENCE_PREFIXES:

        assert not REFERENCE_PREFIX.startswith(prefix)

    assert new_token_reference().startswith(REFERENCE_PREFIX)


def test_only_teaching_and_correction_turn_kinds_are_accepted():

    assert ALLOWED_TURN_KINDS == ("TEACHING_STATEMENT", "CORRECTION")

    for turn_kind in ("QUESTION", "INSTRUCTION", "NORMAL_CONVERSATION", "UNKNOWN"):

        with pytest.raises(HumanActTokenError) as error:

            issue_human_act_token(turn_kind=turn_kind)

        assert REASON_UNKNOWN_TURN_KIND in str(error.value)


def test_the_state_vocabulary_is_closed():

    assert STATES == ("issued", "consumed", "released")

    with pytest.raises(HumanActTokenError) as error:

        HumanActToken(
            token_reference="hat_x",
            turn_kind="TEACHING_STATEMENT",
            state="made_up",
        )

    assert REASON_UNKNOWN_STATE in str(error.value)


# ==========================================================
# 2. immutability and declarations
# ==========================================================

def test_the_token_is_immutable():

    token = issue_human_act_token(turn_kind="TEACHING_STATEMENT")

    with pytest.raises(FrozenInstanceError):

        token.state = STATE_CONSUMED


def test_the_token_declares_no_authority():

    assert HumanActToken.CREATES_IDENTITY is False

    assert HumanActToken.GRANTS_AUTHORITY is False

    assert HumanActToken.CARRIES_CONFIDENCE is False

    assert HumanActToken.DECIDES_TRUTH is False


# ==========================================================
# 3. consume
# ==========================================================

def test_consume_works_exactly_once():

    ledger = HumanActTokenLedger()

    token = ledger.issue(turn_kind="TEACHING_STATEMENT")

    consumed = ledger.consume(token)

    assert consumed.state == STATE_CONSUMED

    assert ledger.is_consumed(token.token_reference) is True

    assert ledger.is_issued(token.token_reference) is False


def test_double_consume_is_rejected():

    ledger = HumanActTokenLedger()

    token = ledger.issue(turn_kind="TEACHING_STATEMENT")

    ledger.consume(token)

    with pytest.raises(HumanActTokenError) as error:

        ledger.consume(token)

    assert REASON_CONSUMED in str(error.value)


def test_the_shared_ledger_consume_helper_works():

    token = issue_human_act_token(turn_kind="CORRECTION")

    assert consume_human_act_token(token).state == STATE_CONSUMED

    assert human_act_token_state(token.token_reference) == STATE_CONSUMED


# ==========================================================
# 4. release
# ==========================================================

def test_release_works_exactly_once():

    ledger = HumanActTokenLedger()

    token = ledger.issue(turn_kind="TEACHING_STATEMENT")

    released = ledger.release(token)

    assert released.state == STATE_RELEASED

    assert ledger.is_released(token.token_reference) is True


def test_consuming_a_released_token_is_rejected():

    ledger = HumanActTokenLedger()

    token = ledger.issue(turn_kind="TEACHING_STATEMENT")

    ledger.release(token)

    with pytest.raises(HumanActTokenError) as error:

        ledger.consume(token)

    assert REASON_RELEASED in str(error.value)


def test_release_twice_is_rejected():

    ledger = HumanActTokenLedger()

    token = ledger.issue(turn_kind="TEACHING_STATEMENT")

    ledger.release(token)

    with pytest.raises(HumanActTokenError) as error:

        ledger.release(token)

    assert REASON_RELEASED in str(error.value)


def test_releasing_a_consumed_token_is_rejected():

    ledger = HumanActTokenLedger()

    token = ledger.issue(turn_kind="TEACHING_STATEMENT")

    ledger.consume(token)

    with pytest.raises(HumanActTokenError) as error:

        ledger.release(token)

    assert REASON_CONSUMED in str(error.value)


def test_the_shared_ledger_release_helper_works():

    token = issue_human_act_token(turn_kind="CORRECTION")

    assert release_human_act_token(token).state == STATE_RELEASED


# ==========================================================
# 5. unknown / forged
# ==========================================================

def test_an_unknown_token_is_rejected():

    ledger = HumanActTokenLedger()

    forged = HumanActToken(
        token_reference="hat_never_issued",
        turn_kind="TEACHING_STATEMENT",
    )

    with pytest.raises(HumanActTokenError) as error:

        ledger.consume(forged)

    assert REASON_UNKNOWN in str(error.value)


def test_a_forged_token_is_rejected_even_with_a_valid_shape():

    ledger = HumanActTokenLedger()

    ledger.issue(turn_kind="TEACHING_STATEMENT")

    forged = HumanActToken(
        token_reference="hat_forged_handle",
        turn_kind="TEACHING_STATEMENT",
        state=STATE_ISSUED,
    )

    with pytest.raises(HumanActTokenError):

        ledger.consume(forged)

    with pytest.raises(HumanActTokenError):

        ledger.release(forged)


def test_a_non_token_is_rejected():

    ledger = HumanActTokenLedger()

    for value in ("hat_x", {"token_reference": "hat_x"}, None, 42):

        with pytest.raises(HumanActTokenError) as error:

            ledger.consume(value)

        assert REASON_NOT_A_TOKEN in str(error.value)


# ==========================================================
# 6. governance identity prefixes
# ==========================================================

def test_governance_identity_prefixes_are_rejected_as_references():

    for prefix in FORBIDDEN_REFERENCE_PREFIXES:

        with pytest.raises(HumanActTokenError) as error:

            HumanActToken(
                token_reference=prefix + "abc",
                turn_kind="TEACHING_STATEMENT",
            )

        assert REASON_FORBIDDEN_REFERENCE in str(error.value)


def test_a_governance_identity_is_rejected_as_a_session_reference():

    for prefix in FORBIDDEN_REFERENCE_PREFIXES:

        with pytest.raises(HumanActTokenError):

            issue_human_act_token(
                turn_kind="TEACHING_STATEMENT",
                session_reference=prefix + "abc",
            )


def test_a_conversation_local_session_reference_is_accepted():

    token = issue_human_act_token(
        turn_kind="TEACHING_STATEMENT",
        session_reference="turn_abc123",
    )

    assert token.session_reference == "turn_abc123"


# ==========================================================
# 7. dependency / identity generation
# ==========================================================

def test_no_governance_import():

    roots = _imported_roots(MODULE)

    for forbidden in (
        "core.governance",
        "core.conversation",
        "core.vision",
        "core.knowledge",
        "core.architecture.reasoning",
        "core.prompt_intelligence",
        "core.bim",
        "core.structure",
    ):

        assert forbidden not in roots

    for root in roots:

        assert not root.startswith("core."), "imported %r" % (root,)


def test_no_governance_identity_generation():

    called = _called_names(MODULE)

    for name in (
        "mint_id",
        "new_claim_id",
        "new_licence_id",
        "new_derivation_event_id",
        "new_endorsement_event_id",
    ):

        assert name not in called

    # the reference is generated with the standard library, not governance
    assert "uuid4" in called


def test_the_module_does_not_persist():

    source = MODULE.read_text(encoding="utf-8")

    for token in ("open(", "json.dump", "pickle", "sqlite3", "shelve"):

        assert token not in source


# ==========================================================
# 8. no forbidden fields
# ==========================================================

def test_no_confidence_truth_or_approval_field():

    token = issue_human_act_token(turn_kind="TEACHING_STATEMENT")

    payload = token.to_dict()

    for field in (
        "truth",
        "confidence",
        "confidence_kind",
        "certainty",
        "probability",
        "approval",
        "approved",
        "status",
        "knowledge_status",
    ):

        assert field not in payload


def test_the_payload_carries_exactly_the_required_fields():

    token = issue_human_act_token(turn_kind="TEACHING_STATEMENT")

    payload = token.to_dict()

    required = {
        "token_reference",
        "turn_kind",
        "language",
        "session_reference",
        "state",
    }

    assert required <= set(payload)

    for extra in ("claim_reference", "licence_reference", "candidate_reference"):

        assert extra not in payload


def test_the_ledger_tracks_state_without_minting_identities():

    ledger = HumanActTokenLedger()

    before = ledger.count()

    token = ledger.issue(turn_kind="TEACHING_STATEMENT")

    assert ledger.count() == before + 1

    assert ledger.state_of(token.token_reference) == STATE_ISSUED

    assert ledger.state_of("hat_absent") is None
