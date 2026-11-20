"""Claim Governance transition validator V1 — isolated boundary self-checks.

PASS expected
    * valid claim creation accepted
    * invalid licence rejected
    * forbidden truth licence rejected
    * valid event accepted
    * invalid event rejected
    * missing lineage rejected
    * composition decisions returned as NOT_IMPLEMENTED

FAIL expected (the guard must raise)
    * validator mutation attempt
    * validator creating a claim
    * validator assigning a licence
"""

from __future__ import annotations


import ast
from pathlib import Path

import pytest

from core.governance import FORBIDDEN_IMPORT_ROOTS
from core.governance.claim import mint_claim
from core.governance.licence import mint_licence_record
from core.governance.validation import (
    RULE_NOT_IMPLEMENTED,
    TransitionResult,
    TransitionValidator,
    transition_validator,
)
from core.governance.validation.transition_validator_v1 import (
    ALLOWED_LICENCE_TRANSITIONS,
)


GOVERNANCE_DIR = Path(__file__).resolve().parents[1]

VALIDATION_DIR = GOVERNANCE_DIR / "validation"


# ----------------------------------------------------------
# A) claim creation
# ----------------------------------------------------------

def _valid_creation(**overrides):

    fields = {
        "identity": "clm_0123456789abcdef",
        "origin": "provider_payload",
        "source_type": "observation_evidence",
        "claim_type": "existence",
        "licence_reference": "lic_0123456789abcdef",
        "creation_event": "dev_0123456789abcdef",
        "lineage_reference": (),
    }

    fields.update(overrides)

    return fields


def test_valid_claim_creation_accepted():

    result = transition_validator.validate_claim_creation(**_valid_creation())

    assert isinstance(result, TransitionResult)

    assert result.allowed is True

    assert result.rule_code == "allowed"


def test_missing_licence_rejected():

    result = transition_validator.validate_claim_creation(
        **_valid_creation(licence_reference=None)
    )

    assert result.allowed is False

    assert result.rule_code == "missing_licence_reference"


def test_missing_origin_rejected():

    result = transition_validator.validate_claim_creation(
        **_valid_creation(origin=None)
    )

    assert result.allowed is False

    assert result.rule_code == "missing_origin"


def test_missing_identity_rejected():

    result = transition_validator.validate_claim_creation(
        **_valid_creation(identity=None)
    )

    assert result.allowed is False

    assert result.rule_code == "missing_identity"


def test_missing_creation_event_rejected():

    result = transition_validator.validate_claim_creation(
        **_valid_creation(creation_event=None)
    )

    assert result.allowed is False

    assert result.rule_code == "missing_creation_event"


def test_forbidden_truth_field_rejected():

    result = transition_validator.validate_claim_creation(
        **_valid_creation(payload={"truth_score": 1.0})
    )

    assert result.allowed is False

    assert result.rule_code == "forbidden_truth_field"


def test_missing_lineage_rejected():

    result = transition_validator.validate_claim_creation(
        **_valid_creation(lineage_reference=("observation_element",))
    )

    assert result.allowed is False

    assert result.rule_code == "invalid_lineage"


def test_self_referential_lineage_rejected():

    result = transition_validator.validate_claim_creation(
        **_valid_creation(
            identity="clm_0123456789abcdef",
            lineage_reference=("clm_0123456789abcdef",),
        )
    )

    assert result.allowed is False

    assert result.rule_code == "invalid_lineage"


# ----------------------------------------------------------
# B) licence transition
# ----------------------------------------------------------

def test_valid_licence_transition_accepted():

    result = transition_validator.validate_licence_transition(
        previous_licence="unlicensed_hypothesis",
        new_licence="human_endorsed_hypothesis",
    )

    assert result.allowed is True


def test_invalid_licence_rejected():

    result = transition_validator.validate_licence_transition(
        previous_licence="unlicensed_hypothesis",
        new_licence="made_up_state",
    )

    assert result.allowed is False

    assert result.rule_code == "unknown_new_licence"


def test_forbidden_truth_licence_rejected():

    for forbidden in ("fact", "truth", "probability", "confidence"):

        result = transition_validator.validate_licence_transition(
            previous_licence="unlicensed_hypothesis",
            new_licence=forbidden,
        )

        assert result.allowed is False

        assert result.rule_code == "forbidden_licence"


def test_undefined_transition_rejected():

    result = transition_validator.validate_licence_transition(
        previous_licence="unlicensed_hypothesis",
        new_licence="heuristic_candidate",
    )

    assert result.allowed is False

    assert result.rule_code == "undefined_transition"

    assert (
        "unlicensed_hypothesis",
        "heuristic_candidate",
    ) not in ALLOWED_LICENCE_TRANSITIONS


# ----------------------------------------------------------
# C) events
# ----------------------------------------------------------

def test_valid_derivation_event_accepted():

    result = transition_validator.validate_derivation_event(
        input_references=("clm_parent", "sleeping_element"),
        output_claim_reference="clm_child",
        operation_type="mint_from_proposal",
        licence_check_result="allowed",
    )

    assert result.allowed is True


def test_invalid_derivation_event_rejected():

    result = transition_validator.validate_derivation_event(
        input_references=(),
        output_claim_reference="clm_child",
        operation_type="mint_from_proposal",
        licence_check_result="allowed",
    )

    assert result.allowed is False

    assert result.rule_code == "missing_event_field"


def test_unresolved_derivation_input_rejected():

    result = transition_validator.validate_derivation_event(
        input_references=("clm_missing",),
        output_claim_reference="clm_child",
        operation_type="mint_from_proposal",
        licence_check_result="allowed",
        known_references=("clm_child",),
    )

    assert result.allowed is False

    assert result.rule_code == "unresolved_reference"


def test_valid_endorsement_event_accepted():

    result = transition_validator.validate_endorsement_event(
        actor="human:teacher",
        target_claim_reference="clm_child",
        previous_licence="unlicensed_hypothesis",
        new_licence="human_endorsed_hypothesis",
        act_type="endorsement",
        ordering=1,
    )

    assert result.allowed is True


def test_endorsement_targeting_observation_rejected():

    result = transition_validator.validate_endorsement_event(
        actor="human:teacher",
        target_claim_reference="sleeping_element",
        previous_licence="unlicensed_hypothesis",
        new_licence="human_endorsed_hypothesis",
        act_type="endorsement",
        ordering=1,
    )

    assert result.allowed is False

    assert result.rule_code == "event_targets_observation"


def test_endorsement_creating_truth_rejected():

    result = transition_validator.validate_endorsement_event(
        actor="human:teacher",
        target_claim_reference="clm_child",
        previous_licence="unlicensed_hypothesis",
        new_licence="truth",
        act_type="endorsement",
        ordering=1,
    )

    assert result.allowed is False

    assert result.rule_code == "event_creates_truth"


def test_endorsement_mutating_content_rejected():

    result = transition_validator.validate_endorsement_event(
        actor="human:teacher",
        target_claim_reference="clm_child",
        previous_licence="unlicensed_hypothesis",
        new_licence="human_endorsed_hypothesis",
        act_type="endorsement",
        ordering=1,
        payload={"new_content": "rewritten"},
    )

    assert result.allowed is False

    assert result.rule_code == "event_mutates_content"


def test_unknown_act_type_rejected():

    result = transition_validator.validate_endorsement_event(
        actor="human:teacher",
        target_claim_reference="clm_child",
        previous_licence="unlicensed_hypothesis",
        new_licence="human_endorsed_hypothesis",
        act_type="made_up_act",
        ordering=1,
    )

    assert result.allowed is False

    assert result.rule_code == "unknown_act_type"


# ----------------------------------------------------------
# D) candidate eligibility helper
# ----------------------------------------------------------

def test_can_be_candidate_accepts_a_complete_claim():

    claim = mint_claim(
        content="a bed exists",
        origin="provider_payload",
        source_type="observation_evidence",
        claim_type="existence",
        original_scope="single_case",
        licence_reference="lic_0123456789abcdef",
    )

    result = transition_validator.can_be_candidate(claim)

    assert result.allowed is True


def test_can_be_candidate_rejects_an_unlicensed_claim():

    claim = mint_claim(
        content="a bed exists",
        origin="provider_payload",
        source_type="observation_evidence",
        claim_type="existence",
        original_scope="single_case",
    )

    result = transition_validator.can_be_candidate(claim)

    assert result.allowed is False

    assert result.rule_code == "claim_not_licensed"


def test_can_be_candidate_creates_nothing():

    claim = mint_claim(
        content="a bed exists",
        origin="provider_payload",
        source_type="observation_evidence",
        claim_type="existence",
        original_scope="single_case",
        licence_reference="lic_0123456789abcdef",
    )

    result = transition_validator.can_be_candidate(claim)

    # A result only — no candidate object is produced.
    assert isinstance(result, TransitionResult)

    assert not hasattr(result, "candidate_id")


# ----------------------------------------------------------
# composition rules are explicitly NOT implemented
# ----------------------------------------------------------

def test_composition_decisions_are_not_implemented():

    for method in (
        "validate_scope_widening",
        "validate_experience_aggregation",
        "validate_heuristic_promotion",
        "validate_multiple_endorsement_aggregation",
    ):

        result = getattr(transition_validator, method)()

        assert result.allowed is False

        assert result.rule_code == RULE_NOT_IMPLEMENTED


# ----------------------------------------------------------
# FAIL expected: the validator must not act
# ----------------------------------------------------------

def test_validator_mutation_attempt_raises():

    validator = TransitionValidator()

    with pytest.raises(AttributeError):

        validator.some_new_state = 1


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


def _imported_modules(path):

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    modules = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            modules.extend(alias.name for alias in node.names)

        elif isinstance(node, ast.ImportFrom):

            if node.module:

                modules.append(node.module)

    return modules


_CREATION_CALLS = (
    "mint_claim",
    "mint_licence_record",
    "record_derivation_event",
    "record_endorsement_event",
    "Claim",
    "LicenceRecord",
    "DerivationEvent",
    "EndorsementEvent",
)


def test_validator_creates_no_objects():

    offenders = []

    for path in sorted(VALIDATION_DIR.rglob("*.py")):

        for name in _called_names(path):

            if name in _CREATION_CALLS:

                offenders.append((str(path), name))

    assert offenders == [], (
        "the validator created an object: %r" % (offenders,)
    )


def test_validator_assigns_no_licence():

    offenders = []

    for path in sorted(VALIDATION_DIR.rglob("*.py")):

        text = path.read_text(encoding="utf-8")

        for marker in ("mint_licence_record", "LicenceRecord("):

            if marker in text:

                offenders.append((str(path), marker))

    assert offenders == [], (
        "the validator assigned a licence: %r" % (offenders,)
    )


# ----------------------------------------------------------
# dependency proof
# ----------------------------------------------------------

def test_validation_imports_no_client_subsystem():

    offenders = []

    for path in sorted(VALIDATION_DIR.rglob("*.py")):

        for module in _imported_modules(path):

            for forbidden in FORBIDDEN_IMPORT_ROOTS:

                if module == forbidden or module.startswith(forbidden + "."):

                    offenders.append((str(path), module))

    assert offenders == [], (
        "validation imported a client subsystem: %r" % (offenders,)
    )


def test_no_reverse_import_of_validation():

    offenders = []

    for area in ("claim", "licence", "events", "proposal", "lineage"):

        for path in sorted((GOVERNANCE_DIR / area).rglob("*.py")):

            for module in _imported_modules(path):

                if module.startswith("core.governance.validation"):

                    offenders.append((str(path), module))

    assert offenders == [], (
        "a source module imported validation (direction reversed): %r"
        % (offenders,)
    )
