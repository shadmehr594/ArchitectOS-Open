"""Claim Governance endorsement wiring V1 — isolated boundary self-checks.

PASS expected
    * an endorsement classification prepares a valid event request
    * non-endorsement acts (preference / judgement / decision / outcome /
      unknown) are rejected
    * an invalid or unresolved claim target is rejected
    * a validator denial blocks event creation
    * the successful path creates an EndorsementEvent

FAIL expected (the guard must hold)
    * no module outside governance/endorsement calls record_endorsement_event
    * the service creates no claim
    * the service assigns no truth
    * the service does not bypass the validator
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.governance import FORBIDDEN_IMPORT_ROOTS
from core.governance.act_classifier import act_classifier
from core.governance.endorsement import (
    ENDORSEMENT_LICENCE,
    EndorsementRequest,
    EndorsementRequestError,
    build_endorsement_request,
    endorsement_service,
)
from core.governance.events import EndorsementEvent


GOVERNANCE_DIR = Path(__file__).resolve().parents[1]

CORE_DIR = GOVERNANCE_DIR.parent

ENDORSEMENT_DIR = GOVERNANCE_DIR / "endorsement"


TARGET = "clm_0123456789abcdef"


def _request(target=TARGET, text="Yes, this interpretation is appropriate."):

    return build_endorsement_request(
        actor_reference="human:teacher",
        target_claim_reference=target,
        act_classification=act_classifier.classify(text),
        requested_scope="single_case",
    )


# ----------------------------------------------------------
# PASS: the happy path
# ----------------------------------------------------------

def test_endorsement_classification_prepares_a_valid_request():

    request = _request()

    assert isinstance(request, EndorsementRequest)

    assert request.act_classification.act_type == "endorsement"

    assert request.REQUESTS_LICENCE is False

    assert request.DECIDES_TRUTH is False

    assert request.APPROVES_CLAIMS is False

    assert request.MUTATES_CLAIMS is False


def test_successful_path_creates_an_endorsement_event():

    result = endorsement_service.prepare_endorsement_event(
        _request(),
        ordering=1,
        previous_licence="unlicensed_hypothesis",
    )

    assert result.allowed is True

    assert result.rule_code == "allowed"

    assert isinstance(result.event, EndorsementEvent)

    assert result.event.new_licence == ENDORSEMENT_LICENCE

    assert result.event.act_type == "endorsement"

    assert result.event.target_claim_reference == TARGET


# ----------------------------------------------------------
# PASS: non-endorsement acts are denied
# ----------------------------------------------------------

@pytest.mark.parametrize(
    "text,expected_act",
    (
        ("I prefer this layout.", "preference"),
        ("This circulation strategy is better.", "judgement"),
        ("Change the entrance location.", "decision"),
        ("This design worked well for this family.", "outcome"),
        ("The weather is nice today.", "unknown"),
    ),
)
def test_non_endorsement_acts_are_rejected(text, expected_act):

    request = _request(text=text)

    assert request.act_classification.act_type == expected_act

    result = endorsement_service.prepare_endorsement_event(
        request,
        ordering=1,
        previous_licence="unlicensed_hypothesis",
    )

    assert result.allowed is False

    assert result.rule_code == "act_not_endorsement"

    assert result.event is None


# ----------------------------------------------------------
# PASS: invalid targets
# ----------------------------------------------------------

def test_observation_target_is_rejected():

    result = endorsement_service.prepare_endorsement_event(
        _request(target="sleeping_element"),
        ordering=1,
        previous_licence="unlicensed_hypothesis",
    )

    assert result.allowed is False

    assert result.rule_code == "event_targets_observation"

    assert result.event is None


def test_unresolved_target_is_rejected():

    result = endorsement_service.prepare_endorsement_event(
        _request(),
        ordering=1,
        previous_licence="unlicensed_hypothesis",
        known_claim_references=("clm_other",),
    )

    assert result.allowed is False

    assert result.rule_code == "unresolved_reference"


def test_missing_ordering_is_rejected():

    result = endorsement_service.prepare_endorsement_event(
        _request(),
        ordering=None,
        previous_licence="unlicensed_hypothesis",
    )

    assert result.allowed is False

    assert result.rule_code == "missing_ordering"


# ----------------------------------------------------------
# PASS: the validator decides
# ----------------------------------------------------------

def test_validator_denial_blocks_event_creation():

    # heuristic_candidate -> human_endorsed_hypothesis is NOT a defined
    # transition, so the validator must deny and no event may be created.
    result = endorsement_service.prepare_endorsement_event(
        _request(),
        ordering=1,
        previous_licence="heuristic_candidate",
    )

    assert result.allowed is False

    assert result.rule_code == "undefined_transition"

    assert result.event is None

    assert result.validation is not None


def test_unknown_previous_licence_is_rejected():

    result = endorsement_service.prepare_endorsement_event(
        _request(),
        ordering=1,
        previous_licence="made_up_state",
    )

    assert result.allowed is False

    assert result.rule_code == "unknown_previous_licence"


# ----------------------------------------------------------
# PASS: the licence candidate must not be invented
# ----------------------------------------------------------

def test_forbidden_licence_candidate_is_rejected():

    for forbidden in ("truth", "fact", "probability", "confidence"):

        result = endorsement_service.prepare_endorsement_event(
            _request(),
            ordering=1,
            previous_licence="unlicensed_hypothesis",
            new_licence_candidate=forbidden,
        )

        assert result.allowed is False

        assert result.rule_code == "forbidden_licence"


def test_non_endorsement_licence_candidate_is_rejected():

    result = endorsement_service.prepare_endorsement_event(
        _request(),
        ordering=1,
        previous_licence="unlicensed_hypothesis",
        new_licence_candidate="candidate_for_learning",
    )

    assert result.allowed is False

    assert result.rule_code == "licence_candidate_not_permitted"


# ----------------------------------------------------------
# PASS: the request carries no authority
# ----------------------------------------------------------

def test_request_is_immutable():

    request = _request()

    with pytest.raises(FrozenInstanceError):

        request.actor_reference = "someone_else"


def test_request_rejects_authority_fields():

    classification = act_classifier.classify("Yes, this is appropriate.")

    for field in (
        "new_licence",
        "licence",
        "truth",
        "approved",
        "content",
        "knowledge_status",
    ):

        with pytest.raises(EndorsementRequestError):

            build_endorsement_request(
                actor_reference="human:teacher",
                target_claim_reference=TARGET,
                act_classification=classification,
                **{field: "forged"},
            )


def test_non_request_is_rejected():

    result = endorsement_service.prepare_endorsement_event(
        "not a request",
        ordering=1,
        previous_licence="unlicensed_hypothesis",
    )

    assert result.allowed is False

    assert result.rule_code == "not_a_request"


def test_service_has_no_mutable_state():

    from core.governance.endorsement import EndorsementService

    service = EndorsementService()

    with pytest.raises(AttributeError):

        service.some_new_state = 1


# ----------------------------------------------------------
# FAIL expected: nobody outside the endorsement service creates events
# ----------------------------------------------------------

def _parse(path):

    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _calls_named(tree, name):

    found = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Call):

            func = node.func

            if isinstance(func, ast.Name) and func.id == name:

                found.append(node)

            elif isinstance(func, ast.Attribute) and func.attr == name:

                found.append(node)

    return found


def test_only_the_endorsement_service_creates_endorsement_events():

    offenders = []

    for path in sorted(CORE_DIR.rglob("*.py")):

        if "__pycache__" in str(path):

            continue

        text = path.read_text(encoding="utf-8", errors="ignore")

        if "record_endorsement_event" not in text:

            continue

        try:

            tree = _parse(path)

        except SyntaxError:

            continue

        if not _calls_named(tree, "record_endorsement_event"):

            continue

        relative = str(path.relative_to(CORE_DIR)).replace("\\", "/")

        if relative.startswith("governance/endorsement/"):

            continue

        if relative.startswith("governance/tests/"):

            continue

        offenders.append(relative)

    assert offenders == [], (
        "a module outside governance/endorsement created an endorsement event: %r"
        % (offenders,)
    )


# ----------------------------------------------------------
# FAIL expected: the service must not act beyond preparing an event
# ----------------------------------------------------------

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


_CREATION_CALLS = (
    "mint_claim",
    "mint_licence_record",
    "record_derivation_event",
    "Claim",
    "LicenceRecord",
    "DerivationEvent",
)


_TRUTH_IDENTIFIERS = (
    "truth_score",
    "confidence_as_truth",
    "approval_as_fact",
    "human_validated_truth",
    "truth",
    "is_true",
    "truth_status",
)


def test_service_creates_no_claim_and_no_licence_record():

    offenders = []

    for path in sorted(ENDORSEMENT_DIR.rglob("*.py")):

        tree = _parse(path)

        for name in _identifiers(tree):

            if name in _CREATION_CALLS:

                offenders.append((str(path), name))

    assert offenders == [], (
        "the endorsement service created an object: %r" % (offenders,)
    )


def test_service_assigns_no_truth():

    offenders = []

    for path in sorted(ENDORSEMENT_DIR.rglob("*.py")):

        tree = _parse(path)

        for name in _identifiers(tree):

            if name in _TRUTH_IDENTIFIERS:

                offenders.append((str(path), name))

    assert offenders == [], (
        "the endorsement service carries a truth identifier: %r"
        % (offenders,)
    )


def test_service_does_not_bypass_the_validator():

    source = (ENDORSEMENT_DIR / "endorsement_service_v1.py").read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "validate_licence_transition" in called

    assert "validate_endorsement_event" in called


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


def test_endorsement_imports_no_client_subsystem():

    offenders = []

    for path in sorted(ENDORSEMENT_DIR.rglob("*.py")):

        for module in _imported_modules(path):

            for forbidden in FORBIDDEN_IMPORT_ROOTS:

                if module == forbidden or module.startswith(forbidden + "."):

                    offenders.append((str(path), module))

    assert offenders == [], (
        "the endorsement wiring imported a client subsystem: %r"
        % (offenders,)
    )


def test_endorsement_imports_governance_internal_only():

    offenders = []

    for path in sorted(ENDORSEMENT_DIR.rglob("*.py")):

        for module in _imported_modules(path):

            if module.startswith("core.") and not module.startswith(
                "core.governance."
            ):

                offenders.append((str(path), module))

    assert offenders == [], (
        "the endorsement wiring imported outside governance: %r" % (offenders,)
    )
