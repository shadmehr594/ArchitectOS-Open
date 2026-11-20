"""Architectural Knowledge Artifact (V1) — isolated self-checks.

Proves the neutral artifact and its single producer:

    1. the fields EXACTLY match the contract (five, no more)
    2. no forbidden field (confidence / truth / status / id / authority)
    3. the object is immutable and SEALED
    4. only the module may construct it (no second producer)
    5. the vision branch maps AUv2 structurally (primary label, fallback)
    6. the conversation branch maps the carrier structurally
    7. an absent hint stays None; a bad hint / bad source_kind is rejected
    8. an empty content is rejected
    9. a source exposing a forbidden key is REFUSED
   10. the module imports stdlib only (no core.*)
   11. the frozen packages and app.py do not reference the new layer
"""

from __future__ import annotations


import ast
import dataclasses
from pathlib import Path

import pytest

from core.interpretation.architectural_knowledge_artifact_v1 import (
    ARTIFACT_FIELDS,
    CONTRACT,
    KNOWLEDGE_HINT_VOCABULARY,
    REASON_FORBIDDEN_FIELD,
    REASON_MISSING_CONTENT,
    REASON_SECOND_PRODUCER,
    REASON_UNKNOWN_KNOWLEDGE_HINT,
    REASON_UNKNOWN_SOURCE,
    REASON_UNKNOWN_SOURCE_KIND,
    SOURCE_KINDS,
    ArchitecturalKnowledgeArtifact,
    ArchitecturalKnowledgeArtifactError,
    architectural_knowledge_artifact_adapter,
    to_architectural_knowledge_artifact,
)

import core.interpretation.architectural_knowledge_artifact_v1 as aka


MODULE = (
    Path(__file__).resolve().parents[1] / "architectural_knowledge_artifact_v1.py"
)

ROOT = Path(__file__).resolve().parents[3]


FORBIDDEN_NAMES = (
    "confidence",
    "confidence_kind",
    "score",
    "probability",
    "certainty",
    "truth",
    "truth_status",
    "is_true",
    "verified_truth",
    "status",
    "knowledge_status",
    "fact_status",
    "approval",
    "approved",
    "admission",
    "admitted",
    "licence",
    "candidate_reference",
    "candidate_id",
    "claim_id",
    "scope",
    "session",
    "nonce",
    "token",
    "proposal_fields",
    "evidence_reference",
)


FROZEN_PACKAGES = ("conversation", "vision", "governance", "runtime")

# The NEW layer's own module name. (The generic package token `core.interpretation`
# is deliberately NOT used: `core/runtime` already references that package for the
# pre-existing carrier/material path, which is unrelated to this new layer.)
NEW_LAYER_TOKENS = (
    "architectural_knowledge_artifact",
)


# ==========================================================
# fixtures (structural — no core.vision / core.conversation import)
# ==========================================================

def _auv2(**overrides):

    understanding = {
        "contract": "ArchitecturalUnderstandingV2",
        "version": "2.0",
        "semantic_space": {
            "label": "master bedroom",
            "status": "bounded_interpretation",
            "basis": ["visible sleeping element"],
            "claim_id": "au2_claim_001",
        },
        "functional_understanding": {
            "role_candidates": [],
            "associated_elements": [],
            "functional_relationships": [],
        },
        "spatial_relationships": [],
        "claim_trace": [
            {
                "claim_id": "au2_claim_001",
                "claim_type": "semantic_space",
                "source_evidence": ["sleeping_element"],
                "grounding_status": ["visible"],
                "interpretation_basis": ["visible sleeping element"],
                "uncertainty": {
                    "confidence": 0.82,
                    "grounding_status": ["visible"],
                    "unknowns": [],
                    "evidence_conflicts": [],
                },
            },
            {
                "claim_id": "au2_claim_002",
                "claim_type": "functional_role",
                "source_evidence": ["sleeping_element"],
                "grounding_status": ["visible"],
                "interpretation_basis": ["visible sleeping element"],
                "uncertainty": {
                    "confidence": 0.82,
                    "grounding_status": ["visible"],
                    "unknowns": [],
                    "evidence_conflicts": [],
                },
            },
        ],
        "interpretation_states": {
            "primary": {
                "label": "master bedroom",
                "status": "bounded_interpretation",
                "claim_id": "au2_claim_001",
            },
            "alternatives": [],
            "unresolved": [],
            "conflicts": [],
        },
        "evidence_basis": {
            "observed_elements": ["sleeping element visible"],
            "grounding_status": {"visible": ["sleeping_element"]},
            "classification_basis": ["visible sleeping element"],
        },
        "uncertainty": {
            "confidence": 0.82,
            "unknowns": [],
            "expected_gaps": [],
            "evidence_conflicts": [],
            "unverified_claims": [],
        },
        "non_claims": [
            "not_permanent_knowledge",
            "not_design_reasoning",
        ],
        "geometry_authoritative": False,
        "read_only": True,
        "persistent": False,
    }

    understanding.update(overrides)

    return understanding


def _carrier(**overrides):

    carrier = {
        "statement": "the bedroom is next to the living room",
        "claim_type_hint": "spatial_relationship",
        "basis": ["interpreter"],
        "limitations": ["no scale"],
        "provenance": "conversation",
    }

    carrier.update(overrides)

    return carrier


# ==========================================================
# 1. the exact contract
# ==========================================================

def test_the_fields_exactly_match_the_contract():

    assert ARTIFACT_FIELDS == (
        "content",
        "knowledge_hint",
        "basis",
        "limitations",
        "source_kind",
    )

    assert ArchitecturalKnowledgeArtifact.FIELDS == ARTIFACT_FIELDS

    assert ArchitecturalKnowledgeArtifact.__slots__ == (
        "_content",
        "_knowledge_hint",
        "_basis",
        "_limitations",
        "_source_kind",
        "_sealed",
    )

    assert not dataclasses.is_dataclass(ArchitecturalKnowledgeArtifact)


def test_the_payload_carries_exactly_the_five_fields():

    artifact = to_architectural_knowledge_artifact(_auv2())

    payload = artifact.to_dict()

    data_keys = {
        key
        for key in payload
        if key not in ("contract", "version")
        and not isinstance(payload[key], bool)
    }

    assert data_keys == set(ARTIFACT_FIELDS)

    assert payload["contract"] == CONTRACT


# ==========================================================
# 2. no forbidden field
# ==========================================================

def test_no_forbidden_field_in_the_payload():

    payload = to_architectural_knowledge_artifact(_auv2()).to_dict()

    for forbidden in FORBIDDEN_NAMES:

        assert forbidden not in payload


def test_no_forbidden_attribute_on_the_artifact():

    artifact = to_architectural_knowledge_artifact(_auv2())

    for forbidden in FORBIDDEN_NAMES:

        assert not hasattr(artifact, forbidden)


def test_the_declaration_flags_are_clean():

    assert ArchitecturalKnowledgeArtifact.IS_ADVISORY is True

    assert ArchitecturalKnowledgeArtifact.CREATES_IDENTITY is False

    assert ArchitecturalKnowledgeArtifact.GRANTS_AUTHORITY is False

    assert ArchitecturalKnowledgeArtifact.CARRIES_CONFIDENCE is False

    assert ArchitecturalKnowledgeArtifact.DECIDES_TRUTH is False


# ==========================================================
# 3. immutability and sealing
# ==========================================================

def test_the_artifact_is_immutable():

    artifact = to_architectural_knowledge_artifact(_auv2())

    with pytest.raises(ArchitecturalKnowledgeArtifactError):

        artifact.content = "changed"

    with pytest.raises(ArchitecturalKnowledgeArtifactError):

        artifact.source_kind = "conversation"

    with pytest.raises(ArchitecturalKnowledgeArtifactError):

        del artifact._content


# ==========================================================
# 4. sealed construction / no second producer
# ==========================================================

def test_a_second_producer_is_refused():

    with pytest.raises(ArchitecturalKnowledgeArtifactError) as error:

        ArchitecturalKnowledgeArtifact(content="x", source_kind="vision")

    assert REASON_SECOND_PRODUCER in str(error.value)


def test_a_forged_authority_is_refused():

    with pytest.raises(ArchitecturalKnowledgeArtifactError) as error:

        ArchitecturalKnowledgeArtifact(
            content="x",
            source_kind="vision",
            _authority=object(),
        )

    assert REASON_SECOND_PRODUCER in str(error.value)


def test_only_the_adapter_constructs_the_artifact():

    # the public producer is the single entry point
    assert callable(to_architectural_knowledge_artifact)

    assert isinstance(
        to_architectural_knowledge_artifact(_auv2()),
        ArchitecturalKnowledgeArtifact,
    )

    # the adapter delegates to the same single producer
    assert (
        architectural_knowledge_artifact_adapter.to_artifact(_auv2()).content
        == to_architectural_knowledge_artifact(_auv2()).content
    )


# ==========================================================
# 5. the vision branch
# ==========================================================

def test_the_vision_branch_maps_auv2_structurally():

    artifact = to_architectural_knowledge_artifact(_auv2())

    assert artifact.content == "master bedroom"

    assert artifact.knowledge_hint == "semantic_space"

    assert artifact.basis == ("visible sleeping element",)

    assert artifact.limitations == (
        "not_permanent_knowledge",
        "not_design_reasoning",
    )

    assert artifact.source_kind == "vision"


def test_the_primary_label_is_selected():

    understanding = _auv2()

    understanding["interpretation_states"]["primary"]["label"] = "guest bedroom"

    artifact = to_architectural_knowledge_artifact(understanding)

    assert artifact.content == "guest bedroom"


def test_the_semantic_space_label_is_the_fallback():

    understanding = _auv2()

    del understanding["interpretation_states"]

    artifact = to_architectural_knowledge_artifact(understanding)

    assert artifact.content == "master bedroom"


def test_the_nested_confidence_is_dropped_not_refused():

    # the AUv2 source carries `uncertainty` (with a nested confidence) — it is
    # ACCEPTED (the key is not top-level `confidence`) and the confidence is
    # never carried onto the artifact.
    artifact = to_architectural_knowledge_artifact(_auv2())

    payload = artifact.to_dict()

    assert "uncertainty" not in payload

    assert "confidence" not in payload


def test_the_basis_falls_back_to_the_semantic_space_basis():

    understanding = _auv2()

    understanding["claim_trace"] = []

    understanding["semantic_space"]["basis"] = ["space basis"]

    artifact = to_architectural_knowledge_artifact(understanding)

    assert artifact.basis == ("space basis",)


# ==========================================================
# 6. the conversation branch
# ==========================================================

def test_the_conversation_branch_maps_the_carrier_structurally():

    artifact = to_architectural_knowledge_artifact(_carrier())

    assert artifact.content == "the bedroom is next to the living room"

    assert artifact.knowledge_hint == "spatial_relationship"

    assert artifact.basis == ("interpreter",)

    assert artifact.limitations == ("no scale",)

    assert artifact.source_kind == "conversation"


def test_the_conversation_branch_does_not_copy_provenance():

    payload = to_architectural_knowledge_artifact(_carrier()).to_dict()

    assert "provenance" not in payload

    assert payload["source_kind"] == "conversation"


def test_the_real_carrier_is_recognised_structurally():

    from core.interpretation.conversation_interaction_carrier_v1 import (
        ConversationInteractionCarrier,
    )

    carrier = ConversationInteractionCarrier(
        statement="the window faces south",
        claim_type_hint="spatial_relationship",
        basis=("interpreter",),
        limitations=("no scale",),
    )

    artifact = to_architectural_knowledge_artifact(carrier)

    assert artifact.content == "the window faces south"

    assert artifact.knowledge_hint == "spatial_relationship"

    assert artifact.source_kind == "conversation"


# ==========================================================
# 7. absent hint / validation
# ==========================================================

def test_a_missing_hint_stays_none():

    assert to_architectural_knowledge_artifact(
        _carrier(claim_type_hint=None)
    ).knowledge_hint is None

    understanding = _auv2()

    understanding["claim_trace"] = []

    assert to_architectural_knowledge_artifact(
        understanding
    ).knowledge_hint is None


def test_an_unknown_knowledge_hint_is_rejected():

    with pytest.raises(ArchitecturalKnowledgeArtifactError) as error:

        ArchitecturalKnowledgeArtifact(
            content="x",
            knowledge_hint="not_a_claim_type",
            source_kind="vision",
            _authority=aka._CONSTRUCTION_AUTHORITY,
        )

    assert REASON_UNKNOWN_KNOWLEDGE_HINT in str(error.value)


def test_the_knowledge_hint_vocabulary_is_closed():

    for token in KNOWLEDGE_HINT_VOCABULARY:

        ArchitecturalKnowledgeArtifact(
            content="x",
            knowledge_hint=token,
            source_kind="vision",
            _authority=aka._CONSTRUCTION_AUTHORITY,
        )

    assert "not_a_claim_type" not in KNOWLEDGE_HINT_VOCABULARY


def test_an_unknown_source_kind_is_rejected():

    with pytest.raises(ArchitecturalKnowledgeArtifactError) as error:

        ArchitecturalKnowledgeArtifact(
            content="x",
            source_kind="audio",
            _authority=aka._CONSTRUCTION_AUTHORITY,
        )

    assert REASON_UNKNOWN_SOURCE_KIND in str(error.value)


def test_the_allowed_source_kinds_are_fixed():

    assert SOURCE_KINDS == ("vision", "conversation")


def test_an_empty_content_is_rejected():

    for content in ("", "   ", None):

        with pytest.raises(ArchitecturalKnowledgeArtifactError) as error:

            ArchitecturalKnowledgeArtifact(
                content=content,
                source_kind="vision",
                _authority=aka._CONSTRUCTION_AUTHORITY,
            )

        assert REASON_MISSING_CONTENT in str(error.value)


def test_an_unknown_source_shape_is_refused():

    with pytest.raises(ArchitecturalKnowledgeArtifactError) as error:

        to_architectural_knowledge_artifact({"something": "else"})

    assert REASON_UNKNOWN_SOURCE in str(error.value)


def test_a_non_source_is_refused():

    for source in (None, "a string", 3, 3.5, True):

        with pytest.raises(ArchitecturalKnowledgeArtifactError):

            to_architectural_knowledge_artifact(source)


# ==========================================================
# 8. forbidden source fields are refused
# ==========================================================

def test_a_forbidden_confidence_is_refused():

    with pytest.raises(ArchitecturalKnowledgeArtifactError) as error:

        to_architectural_knowledge_artifact(_carrier(confidence=0.9))

    assert REASON_FORBIDDEN_FIELD in str(error.value)


def test_a_forbidden_truth_is_refused():

    for key in ("truth", "truth_status", "is_true", "verified_truth"):

        with pytest.raises(ArchitecturalKnowledgeArtifactError) as error:

            to_architectural_knowledge_artifact(_carrier(**{key: True}))

        assert REASON_FORBIDDEN_FIELD in str(error.value)


def test_a_forbidden_status_is_refused():

    for key in ("status", "knowledge_status", "fact_status", "admission"):

        with pytest.raises(ArchitecturalKnowledgeArtifactError) as error:

            to_architectural_knowledge_artifact(_carrier(**{key: "x"}))

        assert REASON_FORBIDDEN_FIELD in str(error.value)


def test_a_forbidden_id_is_refused():

    for key in ("claim_id", "candidate_id", "candidate_reference", "licence"):

        with pytest.raises(ArchitecturalKnowledgeArtifactError) as error:

            to_architectural_knowledge_artifact(_carrier(**{key: "abc"}))

        assert REASON_FORBIDDEN_FIELD in str(error.value)


def test_a_forbidden_authority_key_is_refused():

    for key in ("scope", "session", "nonce", "token", "proposal_fields"):

        with pytest.raises(ArchitecturalKnowledgeArtifactError) as error:

            to_architectural_knowledge_artifact(_carrier(**{key: "x"}))

        assert REASON_FORBIDDEN_FIELD in str(error.value)


def test_a_vision_source_exposing_a_forbidden_key_is_refused():

    with pytest.raises(ArchitecturalKnowledgeArtifactError) as error:

        to_architectural_knowledge_artifact(_auv2(claim_id="au2_claim_001"))

    assert REASON_FORBIDDEN_FIELD in str(error.value)


# ==========================================================
# 9. symmetry
# ==========================================================

def test_the_two_branches_share_the_shape_and_differ_by_source_kind():

    vision = to_architectural_knowledge_artifact(_auv2())

    conversation = to_architectural_knowledge_artifact(_carrier())

    assert set(vision.to_dict()) == set(conversation.to_dict())

    assert vision.source_kind == "vision"

    assert conversation.source_kind == "conversation"

    assert vision.source_kind != conversation.source_kind


# ==========================================================
# 10. dependency direction
# ==========================================================

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


def test_the_module_imports_stdlib_only():

    for root in _imported_roots(MODULE):

        assert not root.startswith("core"), root


def test_the_module_does_not_import_the_frozen_packages():

    for root in _imported_roots(MODULE):

        for frozen in (
            "core.runtime",
            "core.governance",
            "core.conversation",
            "core.vision",
        ):

            assert not root.startswith(frozen), root


# ==========================================================
# 11. the frozen surfaces are unchanged
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
