"""Conversation interpretation adapter (V1) — isolated integration self-checks.

Proves the clean carrier wiring:

    1. the hint from the conversation interpretation REACHES the material adapter
    2. an absent hint stays None end to end (no default, no `existence` fallback)
    3. basis / limitations are forwarded
    4. no candidate_kind / knowledge_class / domain mapping
    5. no confidence leakage
    6. no governance import
    7. the adapter agrees with the interpretation layer and the singleton
    8. the frozen packages do not reference the new layer
"""

from __future__ import annotations


import ast
from pathlib import Path

import pytest

from core.interpretation.conversation_interpretation_adapter_v1 import (
    CONTRACT,
    ConversationInterpretationAdapter,
    conversation_interpretation_adapter,
    to_interaction_carrier,
)
from core.interpretation.conversation_interaction_carrier_v1 import (
    ConversationInteractionCarrier,
)
from core.runtime.claim_request_material_adapter_v1 import (
    to_claim_request_material,
)


MODULE = (
    Path(__file__).resolve().parents[1] / "conversation_interpretation_adapter_v1.py"
)

ROOT = Path(__file__).resolve().parents[3]


FORBIDDEN_NAMES = (
    "candidate_kind",
    "knowledge_class",
    "domain",
    "confidence",
    "confidence_kind",
    "score",
    "truth",
    "truth_status",
    "status",
    "approval",
    "is_true",
    "verified_truth",
    "claim_id",
    "licence_id",
    "candidate_id",
)


FROZEN_PACKAGES = ("conversation", "vision", "governance")

NEW_LAYER_TOKENS = (
    "core.interpretation",
    "conversation_claim_type_hint",
    "conversation_interaction_carrier",
    "conversation_interpretation_adapter",
)


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


# ==========================================================
# 1. the hint reaches the material adapter
# ==========================================================

def test_the_hint_reaches_the_material_adapter():

    carrier = to_interaction_carrier(
        "the bedroom is next to the living room",
        basis=["interpreter"],
        limitations=["no scale"],
    )

    assert isinstance(carrier, ConversationInteractionCarrier)

    assert carrier.claim_type_hint == "spatial_relationship"

    material = to_claim_request_material(carrier)

    assert material.claim_type_hint == "spatial_relationship"

    assert material.statement == "the bedroom is next to the living room"

    assert material.basis == ("interpreter",)

    assert material.limitations == ("no scale",)

    # the material adapter labels the conversation branch itself
    assert material.provenance == "interactive"


@pytest.mark.parametrize(
    "statement,expected",
    [
        ("the bedroom is next to the living room", "spatial_relationship"),
        ("this space is used for sleeping", "functional_role"),
        ("the corridor connects to the kitchen", "functional_relationship"),
        ("the master bedroom means the parents room", "semantic_space"),
        ("it is not a bedroom but rather a study", "alternative_interpretation"),
        ("there is a bed in this space", "existence"),
    ],
)
def test_each_claim_type_reaches_the_material_adapter(statement, expected):

    carrier = to_interaction_carrier(statement)

    assert carrier.claim_type_hint == expected

    assert to_claim_request_material(carrier).claim_type_hint == expected


# ==========================================================
# 2. an absent hint stays None
# ==========================================================

def test_an_absent_hint_stays_none_end_to_end():

    carrier = to_interaction_carrier("a random sentence about nothing at all")

    assert carrier.claim_type_hint is None

    material = to_claim_request_material(carrier)

    assert material.claim_type_hint is None


def test_there_is_no_existence_default():

    # a statement that carries no marker must NOT become `existence`
    carrier = to_interaction_carrier("the architect considered several options")

    assert carrier.claim_type_hint is None


# ==========================================================
# 3. basis / limitations are forwarded
# ==========================================================

def test_basis_and_limitations_are_forwarded():

    carrier = to_interaction_carrier(
        "there is a bed",
        basis=("statement_only",),
        limitations=("no drawing",),
    )

    material = to_claim_request_material(carrier)

    assert material.basis == ("statement_only",)

    assert material.limitations == ("no drawing",)


# ==========================================================
# 4. no taxonomy mapping
# ==========================================================

def test_the_adapter_references_no_taxonomy_name():

    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))

    offenders = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Constant) and isinstance(node.value, str):

            if node.value.strip().lower() in FORBIDDEN_NAMES:

                offenders.append(node.value)

        if isinstance(node, ast.Attribute):

            if node.attr in FORBIDDEN_NAMES:

                offenders.append(node.attr)

    assert offenders == []


def test_no_candidate_kind_mapping():

    statement = "the bedroom is next to the living room"

    plain = to_interaction_carrier(statement)

    with_taxonomy = to_interaction_carrier(
        statement,
        meaning={"candidate_kind": "preference"},
    )

    assert with_taxonomy.claim_type_hint == plain.claim_type_hint

    assert plain.claim_type_hint == "spatial_relationship"


def test_no_knowledge_class_mapping():

    statement = "there is a bed"

    plain = to_interaction_carrier(statement)

    with_taxonomy = to_interaction_carrier(
        statement,
        meaning={"knowledge_class": "ARCHITECTURAL_FACT"},
    )

    assert with_taxonomy.claim_type_hint == plain.claim_type_hint

    assert plain.claim_type_hint == "existence"


def test_no_domain_mapping():

    statement = "a random sentence about nothing at all"

    plain = to_interaction_carrier(statement)

    with_domain = to_interaction_carrier(
        statement,
        meaning={"domain": "spatial_relationship"},
    )

    # the domain says `spatial_relationship`, but the layer must NOT read it
    assert plain.claim_type_hint is None

    assert with_domain.claim_type_hint is None


# ==========================================================
# 5. no confidence leakage
# ==========================================================

def test_no_confidence_leakage():

    statement = "the bedroom is next to the living room"

    carrier = to_interaction_carrier(
        statement,
        meaning={"confidence": 0.99, "confidence_kind": "float"},
    )

    payload = carrier.to_dict()

    for forbidden in ("confidence", "confidence_kind", "score", "truth", "status"):

        assert forbidden not in payload

    material = to_claim_request_material(carrier)

    assert "confidence" not in material.to_dict()

    assert "confidence_kind" not in material.to_dict()

    assert not hasattr(material, "confidence")


# ==========================================================
# 6. no governance import
# ==========================================================

def test_no_governance_import():

    roots = _imported_roots(MODULE)

    for root in roots:

        assert not root.startswith("core.governance"), root

        for frozen in ("core.conversation", "core.vision", "core.runtime"):

            assert not root.startswith(frozen), root

    assert "core.governance" not in roots


def test_the_adapter_imports_only_the_interpretation_layer():

    core_roots = sorted(
        {root for root in _imported_roots(MODULE) if root.startswith("core.")}
    )

    assert core_roots == [
        "core.interpretation.conversation_claim_type_hint_v1",
        "core.interpretation.conversation_interaction_carrier_v1",
    ]


# ==========================================================
# 7. agreement
# ==========================================================

def test_the_class_agrees_with_the_function():

    statement = "there is a bed"

    assert (
        ConversationInterpretationAdapter().to_carrier(statement).claim_type_hint
        == to_interaction_carrier(statement).claim_type_hint
    )


def test_the_singleton_works():

    carrier = conversation_interpretation_adapter.to_carrier("there is a bed")

    assert carrier.claim_type_hint == "existence"

    assert "copies_only=True" in repr(conversation_interpretation_adapter)


def test_the_contract_is_declared():

    assert CONTRACT == "ConversationInterpretationAdapterV1"


# ==========================================================
# 8. the frozen surfaces are unchanged
# ==========================================================

def test_the_frozen_packages_do_not_reference_the_new_layer():

    for package in FROZEN_PACKAGES:

        for path in sorted((ROOT / "core" / package).rglob("*.py")):

            source = path.read_text(encoding="utf-8", errors="ignore")

            for token in NEW_LAYER_TOKENS:

                assert token not in source, (str(path), token)


def test_app_py_does_not_reference_the_new_layer():

    source = (ROOT / "app.py").read_text(encoding="utf-8", errors="ignore")

    for token in NEW_LAYER_TOKENS:

        assert token not in source, token


def test_the_new_layer_does_not_import_the_frozen_packages():

    for path in sorted((ROOT / "core" / "interpretation").glob("*.py")):

        for root in _imported_roots(path):

            for frozen in (
                "core.conversation",
                "core.vision",
                "core.governance",
                "core.runtime",
            ):

                assert not root.startswith(frozen), (str(path), root)
