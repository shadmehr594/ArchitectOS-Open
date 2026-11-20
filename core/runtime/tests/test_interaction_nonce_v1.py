"""InteractionNonce V1 — isolated self-checks.

Proves the runtime-owned, single-use, session-bound interaction nonce:

    1. issue creates a valid, runtime-local, session-bound nonce
    2. nonces are unique and immutable
    3. consume works exactly once; a replay is rejected
    4. a session mismatch is rejected
    5. unknown / forged / wrong-type nonces are rejected
    6. expire works exactly once; consuming an expired nonce is rejected
    7. governance identity prefixes are rejected
    8. no governance import, no governance identity generation
    9. no confidence / truth / approval / status field
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.runtime.interaction_nonce_v1 import (
    FORBIDDEN_REFERENCE_PREFIXES,
    InteractionNonce,
    InteractionNonceError,
    InteractionNonceLedger,
    REASON_CONSUMED,
    REASON_EXPIRED,
    REASON_FORBIDDEN_REFERENCE,
    REASON_MISSING_FIELD,
    REASON_NOT_A_NONCE,
    REASON_SESSION_MISMATCH,
    REASON_UNKNOWN,
    REASON_UNKNOWN_STATE,
    REFERENCE_PREFIX,
    STATES,
    STATE_CONSUMED,
    STATE_EXPIRED,
    STATE_ISSUED,
    consume_interaction_nonce,
    expire_interaction_nonce,
    interaction_nonce_state,
    issue_interaction_nonce,
    new_nonce_reference,
)


MODULE = Path(__file__).resolve().parents[1] / "interaction_nonce_v1.py"

SESSION = "session_alpha"

OTHER_SESSION = "session_beta"


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

def test_issue_creates_a_valid_runtime_local_nonce():

    nonce = issue_interaction_nonce(SESSION)

    assert isinstance(nonce, InteractionNonce)

    assert nonce.nonce_reference.startswith(REFERENCE_PREFIX)

    assert nonce.session_reference == SESSION

    assert nonce.state == STATE_ISSUED

    assert interaction_nonce_state(nonce) == STATE_ISSUED


def test_the_reference_prefix_is_not_a_governance_prefix():

    for prefix in FORBIDDEN_REFERENCE_PREFIXES:

        assert not REFERENCE_PREFIX.startswith(prefix)

    assert new_nonce_reference().startswith(REFERENCE_PREFIX)


def test_the_state_vocabulary_is_closed():

    assert STATES == ("issued", "consumed", "expired")

    with pytest.raises(InteractionNonceError) as error:

        InteractionNonce(
            nonce_reference="inx_x",
            session_reference=SESSION,
            state="made_up",
        )

    assert REASON_UNKNOWN_STATE in str(error.value)


def test_a_missing_session_reference_is_rejected():

    for value in (None, "", "   "):

        with pytest.raises(InteractionNonceError) as error:

            issue_interaction_nonce(value)

        assert REASON_MISSING_FIELD in str(error.value)


# ==========================================================
# 2. uniqueness and immutability
# ==========================================================

def test_nonces_are_unique():

    first = issue_interaction_nonce(SESSION)

    second = issue_interaction_nonce(SESSION)

    assert first.nonce_reference != second.nonce_reference


def test_the_nonce_is_immutable():

    nonce = issue_interaction_nonce(SESSION)

    with pytest.raises(FrozenInstanceError):

        nonce.state = STATE_CONSUMED


def test_the_nonce_declares_no_authority():

    assert InteractionNonce.CREATES_IDENTITY is False

    assert InteractionNonce.GRANTS_AUTHORITY is False

    assert InteractionNonce.CARRIES_CONFIDENCE is False

    assert InteractionNonce.DECIDES_TRUTH is False


# ==========================================================
# 3. consume / replay
# ==========================================================

def test_consume_works_exactly_once():

    ledger = InteractionNonceLedger()

    nonce = ledger.issue(SESSION)

    consumed = ledger.consume(nonce, SESSION)

    assert consumed.state == STATE_CONSUMED

    assert ledger.is_consumed(nonce.nonce_reference) is True

    assert ledger.is_issued(nonce.nonce_reference) is False


def test_a_replayed_nonce_is_rejected():

    ledger = InteractionNonceLedger()

    nonce = ledger.issue(SESSION)

    ledger.consume(nonce, SESSION)

    with pytest.raises(InteractionNonceError) as error:

        ledger.consume(nonce, SESSION)

    assert REASON_CONSUMED in str(error.value)


def test_the_shared_consume_helper_works():

    nonce = issue_interaction_nonce(SESSION)

    assert consume_interaction_nonce(nonce, SESSION).state == STATE_CONSUMED

    assert interaction_nonce_state(nonce) == STATE_CONSUMED


# ==========================================================
# 4. session binding
# ==========================================================

def test_a_session_mismatch_is_rejected():

    ledger = InteractionNonceLedger()

    nonce = ledger.issue(SESSION)

    with pytest.raises(InteractionNonceError) as error:

        ledger.consume(nonce, OTHER_SESSION)

    assert REASON_SESSION_MISMATCH in str(error.value)

    # the nonce is untouched by a mismatched attempt
    assert ledger.is_issued(nonce.nonce_reference) is True


def test_the_bound_session_is_recorded():

    ledger = InteractionNonceLedger()

    nonce = ledger.issue(SESSION)

    assert ledger.session_of(nonce.nonce_reference) == SESSION

    assert ledger.session_of("inx_absent") is None


# ==========================================================
# 5. unknown / forged / wrong type
# ==========================================================

def test_an_unknown_nonce_is_rejected():

    ledger = InteractionNonceLedger()

    forged = InteractionNonce(
        nonce_reference="inx_never_issued",
        session_reference=SESSION,
    )

    with pytest.raises(InteractionNonceError) as error:

        ledger.consume(forged, SESSION)

    assert REASON_UNKNOWN in str(error.value)


def test_a_non_nonce_is_rejected():

    ledger = InteractionNonceLedger()

    for value in ("inx_x", {"nonce_reference": "inx_x"}, None, 42):

        with pytest.raises(InteractionNonceError) as error:

            ledger.consume(value, SESSION)

        assert REASON_NOT_A_NONCE in str(error.value)

    for value in ("inx_x", None, 42):

        with pytest.raises(InteractionNonceError):

            ledger.expire(value)


# ==========================================================
# 6. expiry
# ==========================================================

def test_expire_works_exactly_once():

    ledger = InteractionNonceLedger()

    nonce = ledger.issue(SESSION)

    expired = ledger.expire(nonce)

    assert expired.state == STATE_EXPIRED

    assert ledger.is_expired(nonce.nonce_reference) is True


def test_consuming_an_expired_nonce_is_rejected():

    ledger = InteractionNonceLedger()

    nonce = ledger.issue(SESSION)

    ledger.expire(nonce)

    with pytest.raises(InteractionNonceError) as error:

        ledger.consume(nonce, SESSION)

    assert REASON_EXPIRED in str(error.value)


def test_expiring_twice_is_rejected():

    ledger = InteractionNonceLedger()

    nonce = ledger.issue(SESSION)

    ledger.expire(nonce)

    with pytest.raises(InteractionNonceError) as error:

        ledger.expire(nonce)

    assert REASON_EXPIRED in str(error.value)


def test_expiring_a_consumed_nonce_is_rejected():

    ledger = InteractionNonceLedger()

    nonce = ledger.issue(SESSION)

    ledger.consume(nonce, SESSION)

    with pytest.raises(InteractionNonceError) as error:

        ledger.expire(nonce)

    assert REASON_CONSUMED in str(error.value)


def test_the_shared_expire_helper_works():

    nonce = issue_interaction_nonce(SESSION)

    assert expire_interaction_nonce(nonce).state == STATE_EXPIRED


# ==========================================================
# 7. governance identity prefixes
# ==========================================================

def test_governance_identity_prefixes_are_rejected_as_references():

    for prefix in FORBIDDEN_REFERENCE_PREFIXES:

        with pytest.raises(InteractionNonceError) as error:

            InteractionNonce(
                nonce_reference=prefix + "abc",
                session_reference=SESSION,
            )

        assert REASON_FORBIDDEN_REFERENCE in str(error.value)


def test_a_governance_identity_is_rejected_as_a_session_reference():

    for prefix in FORBIDDEN_REFERENCE_PREFIXES:

        with pytest.raises(InteractionNonceError):

            issue_interaction_nonce(prefix + "abc")


# ==========================================================
# 8. dependency / identity generation
# ==========================================================

def test_no_governance_dependency():

    roots = _imported_roots(MODULE)

    for root in roots:

        assert not root.startswith("core."), "imported %r" % (root,)

    for forbidden in (
        "core.governance",
        "core.conversation",
        "core.vision",
        "core.knowledge",
    ):

        assert forbidden not in roots


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
    assert "token_hex" in called


def test_the_module_does_not_persist():

    source = MODULE.read_text(encoding="utf-8")

    for token in ("open(", "json.dump", "pickle", "sqlite3", "shelve"):

        assert token not in source


# ==========================================================
# 9. no forbidden fields
# ==========================================================

def test_no_confidence_truth_or_approval_field():

    nonce = issue_interaction_nonce(SESSION)

    payload = nonce.to_dict()

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

    nonce = issue_interaction_nonce(SESSION)

    payload = nonce.to_dict()

    required = {"nonce_reference", "session_reference", "state"}

    assert required <= set(payload)

    for extra in ("claim_reference", "licence_reference", "candidate_reference"):

        assert extra not in payload


def test_the_ledger_tracks_state_without_minting_identities():

    ledger = InteractionNonceLedger()

    before = ledger.count()

    nonce = ledger.issue(SESSION)

    assert ledger.count() == before + 1

    assert ledger.state_of(nonce.nonce_reference) == STATE_ISSUED

    assert ledger.state_of("inx_absent") is None
