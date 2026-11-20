"""Claim Governance minting boundary V1 — isolated boundary self-checks.

PASS expected
    * a valid accepted proposal mints a Claim
    * the claim id starts with the governance prefix
    * AUv2 ids are discarded and can never become lineage
    * the creation event exists
    * the result is immutable

FAIL expected
    * a rejected proposal cannot mint
    * missing content cannot mint
    * forbidden authority fields cannot mint
    * an invalid claim type cannot mint
    * a client supplied claim_id cannot survive
    * no licence is assigned
    * no truth field exists
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError, dataclass
from pathlib import Path

import pytest

from core.governance import FORBIDDEN_IMPORT_ROOTS
from core.governance.claim import Claim
from core.governance.intake import proposal_intake_service
from core.governance.minting import (
    ClaimMintResult,
    ClaimMintResultError,
    build_claim_mint_result,
    claim_minting_service,
)
from core.governance.proposal import (
    InterpretationProposal,
    build_proposal,
)


GOVERNANCE_DIR = Path(__file__).resolve().parents[1]

MINTING_DIR = GOVERNANCE_DIR / "minting"


MINT_KWARGS = {
    "source_type": "generated_hypothesis",
    "origin": "vision_proposal",
}


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


def _accepted(**overrides):

    proposal = _proposal(**overrides)

    receipt = proposal_intake_service.submit_proposal(proposal)

    assert receipt.accepted is True

    return proposal, receipt


@dataclass(frozen=True)
class _WithClaimId(InterpretationProposal):

    claim_id: str = "clm_forged"


# ----------------------------------------------------------
# PASS: minting
# ----------------------------------------------------------

def test_valid_accepted_proposal_mints_a_claim():

    proposal, receipt = _accepted()

    result = claim_minting_service.mint_claim_from_proposal(
        proposal, receipt, **MINT_KWARGS
    )

    assert isinstance(result, ClaimMintResult)

    assert result.created is True

    assert isinstance(result.claim, Claim)

    assert result.claim.claim_id == result.claim_reference

    assert result.claim.content == "this space may be a sleeping area"

    assert result.claim.claim_type == "semantic_space"

    assert result.claim.source_type == "generated_hypothesis"

    assert result.claim.origin == "vision_proposal"


def test_claim_id_starts_with_the_governance_prefix():

    proposal, receipt = _accepted()

    result = claim_minting_service.mint_claim_from_proposal(
        proposal, receipt, **MINT_KWARGS
    )

    assert str(result.claim_reference).startswith("clm_")

    assert str(result.creation_event_reference).startswith("dev_")


def test_minting_never_widens_scope():

    proposal, receipt = _accepted()

    result = claim_minting_service.mint_claim_from_proposal(
        proposal, receipt, **MINT_KWARGS
    )

    assert result.claim.original_scope == "single_case"


def test_creation_event_exists():

    proposal, receipt = _accepted()

    result = claim_minting_service.mint_claim_from_proposal(
        proposal, receipt, **MINT_KWARGS
    )

    assert result.creation_event_reference is not None

    assert result.creation_event_reference.startswith("dev_")


def test_result_is_immutable():

    proposal, receipt = _accepted()

    result = claim_minting_service.mint_claim_from_proposal(
        proposal, receipt, **MINT_KWARGS
    )

    with pytest.raises(FrozenInstanceError):

        result.created = False


def test_result_declares_its_boundary():

    assert ClaimMintResult.ASSIGNS_LICENCE is False

    assert ClaimMintResult.APPROVES_TRUTH is False

    assert ClaimMintResult.CREATES_KNOWLEDGE is False

    assert ClaimMintResult.CARRIES_CONFIDENCE_AS_TRUTH is False

    proposal, receipt = _accepted()

    payload = claim_minting_service.mint_claim_from_proposal(
        proposal, receipt, **MINT_KWARGS
    ).to_dict()

    for key in (
        "assigns_licence",
        "approves_truth",
        "creates_knowledge",
        "carries_confidence_as_truth",
    ):

        assert payload[key] is False


# ----------------------------------------------------------
# PASS: AUv2 ids are discarded
# ----------------------------------------------------------

def _contains_projection_id(value):

    if isinstance(value, str):

        return value.startswith("au2_")

    if isinstance(value, dict):

        return any(
            _contains_projection_id(key) or _contains_projection_id(item)
            for key, item in value.items()
        )

    if isinstance(value, (list, tuple)):

        return any(_contains_projection_id(item) for item in value)

    return False


def test_auv2_ids_are_discarded():

    proposal, receipt = _accepted()

    result = claim_minting_service.mint_claim_from_proposal(
        proposal, receipt, **MINT_KWARGS
    )

    assert not _contains_projection_id(result.claim.to_dict())

    assert not _contains_projection_id(result.to_dict())


def test_auv2_id_can_never_become_lineage():

    proposal, receipt = _accepted()

    result = claim_minting_service.mint_claim_from_proposal(
        proposal,
        receipt,
        lineage_reference=("au2_claim_001",),
        **MINT_KWARGS,
    )

    assert result.created is False

    assert "not a claim reference" in result.reason

    assert result.claim is None


# ----------------------------------------------------------
# FAIL expected: denial paths
# ----------------------------------------------------------

def test_rejected_proposal_cannot_mint():

    proposal = _proposal()

    rejected = proposal_intake_service.submit_proposal("not a proposal")

    assert rejected.accepted is False

    result = claim_minting_service.mint_claim_from_proposal(
        proposal, rejected, **MINT_KWARGS
    )

    assert result.created is False

    assert "not accepted" in result.reason

    assert result.claim is None

    assert result.claim_reference is None

    assert result.creation_event_reference is None


def test_missing_content_cannot_mint():

    proposal, receipt = _accepted()

    object.__setattr__(proposal, "proposed_content", "")

    result = claim_minting_service.mint_claim_from_proposal(
        proposal, receipt, **MINT_KWARGS
    )

    assert result.created is False

    assert "no content" in result.reason


def test_forbidden_authority_field_cannot_mint():

    proposal = _WithClaimId(
        proposed_content="x",
        trigger_references=("sleeping_element",),
        uncertainty={},
    )

    receipt = proposal_intake_service.submit_proposal(proposal)

    # intake already rejects it; minting must reject it independently too
    assert receipt.accepted is False

    result = claim_minting_service.mint_claim_from_proposal(
        proposal, receipt, **MINT_KWARGS
    )

    assert result.created is False


def test_invalid_claim_type_cannot_mint():

    proposal, receipt = _accepted()

    result = claim_minting_service.mint_claim_from_proposal(
        proposal, receipt, claim_type="made_up_type", **MINT_KWARGS
    )

    assert result.created is False

    assert "invalid claim type" in result.reason


def test_invalid_source_type_cannot_mint():

    proposal, receipt = _accepted()

    result = claim_minting_service.mint_claim_from_proposal(
        proposal,
        receipt,
        source_type="made_up_source",
        origin="vision_proposal",
    )

    assert result.created is False

    assert "invalid source type" in result.reason


def test_missing_origin_cannot_mint():

    proposal, receipt = _accepted()

    result = claim_minting_service.mint_claim_from_proposal(
        proposal, receipt, source_type="generated_hypothesis", origin=None
    )

    assert result.created is False

    assert "origin must be explicit" in result.reason


def test_invalid_scope_cannot_mint():

    proposal, receipt = _accepted()

    result = claim_minting_service.mint_claim_from_proposal(
        proposal, receipt, scope="made_up_scope", **MINT_KWARGS
    )

    assert result.created is False

    assert "invalid scope" in result.reason


def test_client_supplied_claim_id_cannot_survive():

    proposal, receipt = _accepted()

    with pytest.raises(TypeError):

        claim_minting_service.mint_claim_from_proposal(
            proposal,
            receipt,
            claim_id="clm_client_supplied",
            **MINT_KWARGS,
        )

    result = claim_minting_service.mint_claim_from_proposal(
        proposal, receipt, **MINT_KWARGS
    )

    assert result.claim_reference != "clm_client_supplied"


# ----------------------------------------------------------
# FAIL expected: no licence, no truth
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


def test_no_licence_is_assigned():

    offenders = []

    for path in sorted(MINTING_DIR.rglob("*.py")):

        for name in _identifiers(_parse(path)):

            if name in ("mint_licence_record", "LicenceRecord", "new_licence_id"):

                offenders.append((str(path), name))

    assert offenders == [], (
        "the minting boundary assigned a licence: %r" % (offenders,)
    )

    proposal, receipt = _accepted()

    result = claim_minting_service.mint_claim_from_proposal(
        proposal, receipt, **MINT_KWARGS
    )

    # no licence reference is created or decided by this boundary
    assert result.claim.licence_reference is None

    for field in ("licence", "licence_state", "licence_reference"):

        assert field not in result.to_dict()


def test_no_truth_field_exists():

    offenders = []

    for path in sorted(MINTING_DIR.rglob("*.py")):

        for name in _identifiers(_parse(path)):

            if name in (
                "truth",
                "truth_status",
                "is_true",
                "truth_score",
                "confidence_as_truth",
                "approval_as_fact",
                "human_validated_truth",
            ):

                offenders.append((str(path), name))

    assert offenders == [], (
        "the minting boundary carries a truth identifier: %r" % (offenders,)
    )

    proposal, receipt = _accepted()

    result = claim_minting_service.mint_claim_from_proposal(
        proposal, receipt, **MINT_KWARGS
    )

    for field in ("truth", "truth_status", "is_true"):

        assert field not in result.to_dict()

        assert field not in result.claim.to_dict()


def test_result_rejects_authority_fields():

    for field in (
        "truth",
        "approved",
        "knowledge_status",
        "confidence",
        "licence",
        "scope",
    ):

        with pytest.raises(ClaimMintResultError):

            build_claim_mint_result(
                created=True,
                claim_reference="clm_x",
                creation_event_reference="dev_x",
                reason="ok",
                **{field: "forged"},
            )


def test_minting_has_no_mutable_state():

    from core.governance.minting import ClaimMintingService

    service = ClaimMintingService()

    with pytest.raises(AttributeError):

        service.some_new_state = 1


# ----------------------------------------------------------
# dependency proof
# ----------------------------------------------------------

def _called_names(path):

    names = []

    for node in ast.walk(_parse(path)):

        if isinstance(node, ast.Call):

            func = node.func

            if isinstance(func, ast.Name):

                names.append(func.id)

            elif isinstance(func, ast.Attribute):

                names.append(func.attr)

    return names


def _imported_modules(path):

    modules = []

    for node in ast.walk(_parse(path)):

        if isinstance(node, ast.Import):

            modules.extend(alias.name for alias in node.names)

        elif isinstance(node, ast.ImportFrom):

            if node.module:

                modules.append(node.module)

    return modules


def test_minting_calls_the_event_factory():

    offenders = []

    for path in sorted(MINTING_DIR.rglob("*.py")):

        if "record_derivation_event" in _called_names(path):

            offenders.append(str(path))

    assert offenders, (
        "the minting boundary must create the creation event"
    )


def test_minting_creates_no_knowledge_or_candidate_object():

    forbidden = (
        "mint_claim",
        "mint_licence_record",
        "KnowledgeCandidate",
        "TeachingCandidate",
    )

    offenders = []

    for path in sorted(MINTING_DIR.rglob("*.py")):

        for name in _identifiers(_parse(path)):

            if name in forbidden[1:]:

                offenders.append((str(path), name))

    assert offenders == [], (
        "the minting boundary created a forbidden object: %r" % (offenders,)
    )

    # mint_claim IS expected — exactly once, in the service
    calls = []

    for path in sorted(MINTING_DIR.rglob("*.py")):

        calls.extend(
            name for name in _called_names(path) if name == "mint_claim"
        )

    assert calls == ["mint_claim"]


def test_minting_imports_no_client_subsystem():

    offenders = []

    for path in sorted(MINTING_DIR.rglob("*.py")):

        for module in _imported_modules(path):

            for forbidden in FORBIDDEN_IMPORT_ROOTS:

                if module == forbidden or module.startswith(forbidden + "."):

                    offenders.append((str(path), module))

    assert offenders == [], (
        "the minting boundary imported a client subsystem: %r" % (offenders,)
    )


def test_minting_imports_only_the_allowed_governance_areas():

    allowed = (
        "core.governance.claim",
        "core.governance.events",
        "core.governance.identity",
        "core.governance.identity_v1",
        "core.governance.licence",
        "core.governance.lineage",
        "core.governance.minting",
        "core.governance.proposal",
        "core.governance.validation",
    )

    offenders = []

    for path in sorted(MINTING_DIR.rglob("*.py")):

        for module in _imported_modules(path):

            if not module.startswith("core."):

                continue

            if not any(
                module == area or module.startswith(area + ".")
                for area in allowed
            ):

                offenders.append((str(path), module))

    assert offenders == [], (
        "the minting boundary imported outside its allowed areas: %r"
        % (offenders,)
    )
