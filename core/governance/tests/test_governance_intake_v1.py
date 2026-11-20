"""Claim Governance proposal intake V1 — isolated boundary self-checks.

PASS expected
    * a valid proposal is accepted
    * an invalid proposal is rejected
    * a proposal carrying authority fields is rejected
    * no claim, no licence and no event is created

FAIL expected
    * the intake creating a Claim
    * the intake assigning identity
    * the intake assigning a licence
    * the intake assigning a scope
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError, dataclass
from pathlib import Path

import pytest

from core.governance import FORBIDDEN_IMPORT_ROOTS
from core.governance.intake import (
    PROPOSAL_REFERENCE_PREFIX,
    ProposalReceipt,
    ProposalReceiptError,
    build_proposal_receipt,
    proposal_intake_service,
)
from core.governance.proposal import (
    InterpretationProposal,
    build_proposal,
)


GOVERNANCE_DIR = Path(__file__).resolve().parents[1]

INTAKE_DIR = GOVERNANCE_DIR / "intake"


# ----------------------------------------------------------
# fixtures
# ----------------------------------------------------------

def _proposal(**overrides):

    fields = {
        "proposed_content": "this space may be a sleeping area",
        "proposed_claim_type": "semantic_space",
        "trigger_references": ("sleeping_element",),
        "basis": ("sleeping element",),
        "uncertainty": {"confidence": "MEDIUM", "unknowns": []},
        "limitations": ("not_permanent_knowledge",),
        "language": "en",
    }

    fields.update(overrides)

    return build_proposal(**fields)


@dataclass(frozen=True)
class _WithClaimId(InterpretationProposal):

    claim_id: str = "clm_forged"


@dataclass(frozen=True)
class _WithLicence(InterpretationProposal):

    licence: str = "lic_forged"


@dataclass(frozen=True)
class _WithScope(InterpretationProposal):

    scope: str = "general"


@dataclass(frozen=True)
class _WithTruth(InterpretationProposal):

    truth_status: str = "true"


# ----------------------------------------------------------
# PASS: intake
# ----------------------------------------------------------

def test_valid_proposal_is_accepted():

    receipt = proposal_intake_service.submit_proposal(_proposal())

    assert isinstance(receipt, ProposalReceipt)

    assert receipt.accepted is True

    assert str(receipt.proposal_reference).startswith(
        PROPOSAL_REFERENCE_PREFIX
    )

    assert "received" in receipt.reason


def test_proposal_reference_is_deterministic_and_not_claim_identity():

    first = proposal_intake_service.submit_proposal(_proposal())

    second = proposal_intake_service.submit_proposal(_proposal())

    assert first.proposal_reference == second.proposal_reference

    # a reference, not a governance claim id
    assert not str(first.proposal_reference).startswith("clm_")


def test_invalid_proposal_is_rejected():

    for value in ("not a proposal", None, 42, {"proposed_content": "x"}):

        receipt = proposal_intake_service.submit_proposal(value)

        assert receipt.accepted is False

        assert receipt.proposal_reference is None

        assert "not an InterpretationProposal" in receipt.reason


def test_proposal_missing_content_is_rejected():

    proposal = _proposal()

    # bypass the constructor guard to simulate a malformed instance
    object.__setattr__(proposal, "proposed_content", "")

    receipt = proposal_intake_service.submit_proposal(proposal)

    assert receipt.accepted is False

    assert "proposed_content" in receipt.reason


def test_proposal_with_bad_uncertainty_is_rejected():

    proposal = _proposal()

    object.__setattr__(proposal, "uncertainty", "not a mapping")

    receipt = proposal_intake_service.submit_proposal(proposal)

    assert receipt.accepted is False

    assert "uncertainty" in receipt.reason


def test_proposal_with_bad_trigger_references_is_rejected():

    proposal = _proposal()

    object.__setattr__(proposal, "trigger_references", "not a sequence")

    receipt = proposal_intake_service.submit_proposal(proposal)

    assert receipt.accepted is False

    assert "trigger_references" in receipt.reason


# ----------------------------------------------------------
# PASS: authority fields are rejected
# ----------------------------------------------------------

@pytest.mark.parametrize(
    "factory,field",
    (
        (_WithClaimId, "claim_id"),
        (_WithLicence, "licence"),
        (_WithScope, "scope"),
        (_WithTruth, "truth_status"),
    ),
)
def test_proposal_carrying_authority_is_rejected(factory, field):

    proposal = factory(
        proposed_content="x",
        trigger_references=(),
        uncertainty={},
    )

    receipt = proposal_intake_service.submit_proposal(proposal)

    assert receipt.accepted is False

    assert field in receipt.reason


# ----------------------------------------------------------
# PASS: the receipt carries no authority
# ----------------------------------------------------------

def test_receipt_is_immutable():

    receipt = proposal_intake_service.submit_proposal(_proposal())

    with pytest.raises(FrozenInstanceError):

        receipt.accepted = False


def test_receipt_declares_its_boundary():

    assert ProposalReceipt.CREATES_CLAIMS is False

    assert ProposalReceipt.CREATES_LICENCES is False

    assert ProposalReceipt.CREATES_EVENTS is False

    assert ProposalReceipt.ASSIGNS_SCOPE is False

    assert ProposalReceipt.CARRIES_TRUTH is False

    payload = proposal_intake_service.submit_proposal(_proposal()).to_dict()

    for key in (
        "creates_claims",
        "creates_licences",
        "creates_events",
        "assigns_scope",
        "carries_truth",
    ):

        assert payload[key] is False


def test_receipt_carries_no_authority_fields():

    payload = proposal_intake_service.submit_proposal(_proposal()).to_dict()

    for field in ("claim_id", "licence", "scope", "truth", "knowledge_status"):

        assert field not in payload


def test_receipt_rejects_authority_fields():

    for field in ("claim_id", "licence", "scope", "truth", "knowledge_status"):

        with pytest.raises(ProposalReceiptError):

            build_proposal_receipt(
                proposal_reference="prp_x",
                accepted=True,
                reason="ok",
                **{field: "forged"},
            )


def test_intake_has_no_mutable_state():

    from core.governance.intake import ProposalIntakeService

    service = ProposalIntakeService()

    with pytest.raises(AttributeError):

        service.some_new_state = 1


# ----------------------------------------------------------
# FAIL expected: the intake must not act
# ----------------------------------------------------------

def _parse(path):

    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _identifiers(tree):

    names = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Name):

            names.append(node.id)

        elif isinstance(node, ast.Attribute):

            names.append(node.attr)

        elif isinstance(node, ast.keyword):

            if node.arg:

                names.append(node.arg)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):

            names.append(node.name)

            names.extend(arg.arg for arg in node.args.args)

    return names


_CREATION_IDENTIFIERS = (
    "mint_claim",
    "mint_licence_record",
    "record_derivation_event",
    "record_endorsement_event",
    "Claim",
    "LicenceRecord",
    "DerivationEvent",
    "EndorsementEvent",
    "KnowledgeCandidate",
)


_IDENTITY_IDENTIFIERS = (
    "mint_id",
    "new_claim_id",
    "new_licence_id",
    "new_derivation_event_id",
    "new_endorsement_event_id",
)


def test_intake_creates_no_claim_licence_or_event():

    offenders = []

    for path in sorted(INTAKE_DIR.rglob("*.py")):

        for name in _identifiers(_parse(path)):

            if name in _CREATION_IDENTIFIERS:

                offenders.append((str(path), name))

    assert offenders == [], (
        "the intake created a governed object: %r" % (offenders,)
    )


def test_intake_assigns_no_identity():

    offenders = []

    for path in sorted(INTAKE_DIR.rglob("*.py")):

        for name in _identifiers(_parse(path)):

            if name in _IDENTITY_IDENTIFIERS:

                offenders.append((str(path), name))

    assert offenders == [], (
        "the intake minted an identity: %r" % (offenders,)
    )


def test_intake_assigns_no_licence():

    # scanned as IDENTIFIERS, so a docstring mention is not a false positive
    offenders = []

    for path in sorted(INTAKE_DIR.rglob("*.py")):

        for name in _identifiers(_parse(path)):

            if name in ("mint_licence_record", "LicenceRecord"):

                offenders.append((str(path), name))

    assert offenders == [], (
        "the intake assigned a licence: %r" % (offenders,)
    )


def test_intake_assigns_no_scope():

    # a receipt carries no scope field at all
    payload = proposal_intake_service.submit_proposal(_proposal()).to_dict()

    assert "scope" not in payload

    assert "scope_authority" not in payload


# ----------------------------------------------------------
# dependency proof
# ----------------------------------------------------------

def _imported_modules(path):

    tree = _parse(path)

    modules = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            modules.extend(alias.name for alias in node.names)

        elif isinstance(node, ast.ImportFrom):

            if node.module:

                modules.append(node.module)

    return modules


def test_intake_imports_no_client_subsystem():

    offenders = []

    for path in sorted(INTAKE_DIR.rglob("*.py")):

        for module in _imported_modules(path):

            for forbidden in FORBIDDEN_IMPORT_ROOTS:

                if module == forbidden or module.startswith(forbidden + "."):

                    offenders.append((str(path), module))

    assert offenders == [], (
        "the intake imported a client subsystem: %r" % (offenders,)
    )


def test_intake_imports_governance_only():

    offenders = []

    for path in sorted(INTAKE_DIR.rglob("*.py")):

        for module in _imported_modules(path):

            if module.startswith("core.") and not module.startswith(
                "core.governance."
            ):

                offenders.append((str(path), module))

    assert offenders == [], (
        "the intake imported outside governance: %r" % (offenders,)
    )
