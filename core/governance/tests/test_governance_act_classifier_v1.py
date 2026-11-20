"""Claim Governance act classifier V1 — isolated boundary self-checks.

PASS expected
    * endorsement text classified as endorsement
    * preference classified separately
    * judgement / decision / outcome classified separately
    * unknown handled safely (including ties)
    * the classification object is immutable
    * the classifier creates no claim, no licence, no event

FAIL expected (the guard must raise)
    * a classification carrying claim_id / licence / scope / truth_status
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.governance import FORBIDDEN_IMPORT_ROOTS
from core.governance.act_classifier import (
    ACT_TYPES,
    CONFIDENCE_DESCRIPTORS,
    FORBIDDEN_CLASSIFICATION_FIELDS,
    ActClassification,
    ActClassificationError,
    ActClassifier,
    act_classifier,
    build_act_classification,
)
from core.governance.events import ACT_TYPES as EVENT_ACT_TYPES


GOVERNANCE_DIR = Path(__file__).resolve().parents[1]

CLASSIFIER_DIR = GOVERNANCE_DIR / "act_classifier"


# ----------------------------------------------------------
# classification of acts
# ----------------------------------------------------------

def test_endorsement_text_is_classified_as_endorsement():

    result = act_classifier.classify(
        "Yes, this interpretation is appropriate."
    )

    assert isinstance(result, ActClassification)

    assert result.act_type == "endorsement"

    assert result.confidence_descriptor in CONFIDENCE_DESCRIPTORS

    assert result.language == "en"


def test_preference_is_classified_separately():

    result = act_classifier.classify("I prefer this layout.")

    assert result.act_type == "preference"


def test_judgement_decision_outcome_are_separate():

    assert (
        act_classifier.classify(
            "This circulation strategy is better."
        ).act_type
        == "judgement"
    )

    assert (
        act_classifier.classify(
            "Change the entrance location."
        ).act_type
        == "decision"
    )

    assert (
        act_classifier.classify(
            "This design worked well for this family."
        ).act_type
        == "outcome"
    )


def test_unknown_is_handled_safely():

    assert act_classifier.classify("The weather is nice today.").act_type == "unknown"

    assert act_classifier.classify("").act_type == "unknown"

    assert act_classifier.classify(None).act_type == "unknown"

    assert act_classifier.classify(12345).act_type == "unknown"


def test_ambiguous_text_is_not_guessed():

    # endorsement ("yes") ties with judgement ("better") -> unknown, never a guess
    result = act_classifier.classify("Yes, this is better.")

    assert result.act_type == "unknown"

    assert result.confidence_descriptor == "none"


def test_persian_text_is_classified_and_language_detected():

    result = act_classifier.classify("بله، این تفسیر مناسب است.")

    assert result.act_type == "endorsement"

    assert result.language == "fa"


# ----------------------------------------------------------
# the value object
# ----------------------------------------------------------

def test_classification_is_immutable():

    result = act_classifier.classify("Yes, this is appropriate.")

    with pytest.raises(FrozenInstanceError):

        result.act_type = "preference"


def test_classification_declares_its_boundary():

    assert ActClassification.DECIDES_TRUTH is False

    assert ActClassification.CREATES_CLAIMS is False

    assert ActClassification.CREATES_LICENCES is False

    assert ActClassification.CREATES_EVENTS is False

    assert ActClassification.APPROVES_CLAIMS is False

    payload = act_classifier.classify("Yes, appropriate.").to_dict()

    for key in (
        "decides_truth",
        "creates_claims",
        "creates_licences",
        "creates_events",
        "approves_claims",
    ):

        assert payload[key] is False


def test_classification_carries_no_authority_fields():

    payload = act_classifier.classify("Yes, appropriate.").to_dict()

    for field in FORBIDDEN_CLASSIFICATION_FIELDS:

        assert field not in payload

    result = act_classifier.classify("Yes, appropriate.")

    for field in ("claim_id", "licence", "scope", "truth_status", "knowledge_status"):

        assert not hasattr(result, field)


def test_build_classification_rejects_authority_fields():

    for field in ("claim_id", "licence", "scope", "truth_status", "knowledge_status"):

        with pytest.raises(ActClassificationError):

            build_act_classification(
                act_type="endorsement",
                **{field: "forged"},
            )


def test_unknown_act_type_is_refused():

    with pytest.raises(ActClassificationError):

        build_act_classification(act_type="made_up_act")

    with pytest.raises(ActClassificationError):

        build_act_classification(
            act_type="endorsement",
            confidence_descriptor="99_percent",
        )


# ----------------------------------------------------------
# vocabulary consistency with the event layer
# ----------------------------------------------------------

def test_classifier_vocabulary_is_compatible_with_the_event_layer():

    # every act the classifier can emit (except `unknown`) must be a valid
    # event act type, so a classification can never become an unknown event.
    assert set(ACT_TYPES) - {"unknown"} <= set(EVENT_ACT_TYPES)


# ----------------------------------------------------------
# FAIL expected: the classifier must not act
# ----------------------------------------------------------

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


def test_classifier_creates_no_claim_licence_or_event():

    offenders = []

    for path in sorted(CLASSIFIER_DIR.rglob("*.py")):

        for name in _called_names(path):

            if name in _CREATION_CALLS:

                offenders.append((str(path), name))

    assert offenders == [], (
        "the classifier created an object: %r" % (offenders,)
    )


def test_classifier_never_imports_the_event_creation_module():

    offenders = []

    for path in sorted(CLASSIFIER_DIR.rglob("*.py")):

        for module in _imported_modules(path):

            if module.startswith("core.governance.events"):

                offenders.append((str(path), module))

    assert offenders == [], (
        "the classifier imported the event module: %r" % (offenders,)
    )


def test_classifier_has_no_mutable_state():

    classifier = ActClassifier()

    with pytest.raises(AttributeError):

        classifier.some_new_state = 1


# ----------------------------------------------------------
# dependency proof
# ----------------------------------------------------------

def test_classifier_imports_no_client_subsystem():

    offenders = []

    for path in sorted(CLASSIFIER_DIR.rglob("*.py")):

        for module in _imported_modules(path):

            for forbidden in FORBIDDEN_IMPORT_ROOTS:

                if module == forbidden or module.startswith(forbidden + "."):

                    offenders.append((str(path), module))

    assert offenders == [], (
        "the classifier imported a client subsystem: %r" % (offenders,)
    )


def test_no_reverse_import_of_the_classifier():

    offenders = []

    for area in ("claim", "licence", "events", "proposal", "lineage", "validation"):

        for path in sorted((GOVERNANCE_DIR / area).rglob("*.py")):

            for module in _imported_modules(path):

                if module.startswith("core.governance.act_classifier"):

                    offenders.append((str(path), module))

    assert offenders == [], (
        "a governance module imported the classifier (direction reversed): %r"
        % (offenders,)
    )
