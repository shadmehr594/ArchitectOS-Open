"""ClaimRequestMaterialAdapter V1 — isolated self-checks.

Proves the single producer of ClaimRequestMaterial:

    1. the conversation branch maps correctly (provenance "interactive")
    2. the vision branch maps correctly (provenance "vision")
    3. a missing / empty statement is rejected
    4. a forbidden truth / confidence / proposal field is rejected
    5. `claim_type_hint` is COPIED only — never derived
    6. `candidate_kind` is NEVER converted into a claim type
    7. the output is immutable and carries exactly five fields
    8. dropped fields are ignored
    9. no governance / conversation / vision import
   10. no second producer
"""

from __future__ import annotations


import ast
from pathlib import Path

import pytest

from core.runtime.claim_request_material_adapter_v1 import (
    CONVERSATION_STATEMENT_FIELDS,
    FORBIDDEN_SOURCE_FIELDS,
    PROVENANCE_INTERACTIVE,
    PROVENANCE_VISION,
    REASON_FORBIDDEN_FIELD,
    REASON_MISSING_STATEMENT,
    REASON_NOT_A_SOURCE,
    REASON_UNKNOWN_SOURCE,
    ClaimRequestMaterial,
    ClaimRequestMaterialAdapter,
    ClaimRequestMaterialError,
    claim_request_material_adapter,
    to_claim_request_material,
)


MODULE = (
    Path(__file__).resolve().parents[1] / "claim_request_material_adapter_v1.py"
)


def _conversation_source(**overrides):

    fields = {
        "raw_statement": "a bed exists in this space",
        "claim_type_hint": "existence",
        "basis": ["observed"],
        "limitations": ["no geometry asserted"],
    }

    fields.update(overrides)

    return fields


def _vision_source(**overrides):

    fields = {
        "claim_trace": [
            {
                "claim_id": "au2_claim_001",
                "label": "a bed exists",
                "claim_type": "existence",
                "interpretation_basis": ["observed"],
            }
        ],
        "non_claims": ["no dimension asserted"],
        "semantic_space": {"label": "sleeping area"},
        "interpretation_states": {"primary": {"claim_id": "au2_claim_001"}},
    }

    fields.update(overrides)

    return fields


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
# 1-2. the two branches
# ==========================================================

def test_the_conversation_branch_maps_correctly():

    material = to_claim_request_material(_conversation_source())

    assert isinstance(material, ClaimRequestMaterial)

    assert material.provenance == PROVENANCE_INTERACTIVE

    assert material.statement == "a bed exists in this space"

    assert material.claim_type_hint == "existence"

    assert material.basis == ("observed",)

    assert material.limitations == ("no geometry asserted",)


def test_the_conversation_branch_accepts_each_statement_key():

    for key in CONVERSATION_STATEMENT_FIELDS:

        material = to_claim_request_material({key: "a bed exists"})

        assert material.statement == "a bed exists"

        assert material.provenance == PROVENANCE_INTERACTIVE


def test_the_conversation_branch_reads_an_object_structurally():

    class _Source:

        raw_statement = "a bed exists"

        basis = ("observed",)

    material = to_claim_request_material(_Source())

    assert material.statement == "a bed exists"

    assert material.basis == ("observed",)

    assert material.provenance == PROVENANCE_INTERACTIVE


def test_the_vision_branch_maps_correctly():

    material = to_claim_request_material(_vision_source())

    assert material.provenance == PROVENANCE_VISION

    assert material.statement == "a bed exists"

    assert material.claim_type_hint == "existence"

    assert material.basis == ("observed",)

    assert material.limitations == ("no dimension asserted",)


def test_the_vision_branch_falls_back_to_the_semantic_space_label():

    source = _vision_source()

    source["claim_trace"] = [{"claim_id": "au2_claim_001", "claim_type": "existence"}]

    material = to_claim_request_material(source)

    assert material.statement == "sleeping area"


def test_the_vision_branch_uses_the_primary_trace():

    source = _vision_source(
        claim_trace=[
            {"claim_id": "au2_a", "label": "first", "claim_type": "existence"},
            {"claim_id": "au2_b", "label": "second", "claim_type": "semantic_space"},
        ],
        interpretation_states={"primary": {"claim_id": "au2_b"}},
    )

    material = to_claim_request_material(source)

    assert material.statement == "second"

    assert material.claim_type_hint == "semantic_space"


def test_the_adapter_instance_works():

    assert claim_request_material_adapter.to_material(_conversation_source()) is not None

    assert ClaimRequestMaterialAdapter().to_material(_vision_source()) is not None


# ==========================================================
# 3. missing statement
# ==========================================================

def test_a_source_with_no_statement_key_is_unknown():

    with pytest.raises(ClaimRequestMaterialError) as error:

        to_claim_request_material({"candidate_kind": "observation"})

    assert REASON_UNKNOWN_SOURCE in str(error.value)


def test_an_empty_statement_is_rejected():

    for value in ("", "   ", "\n"):

        with pytest.raises(ClaimRequestMaterialError) as error:

            to_claim_request_material({"raw_statement": value})

        assert REASON_MISSING_STATEMENT in str(error.value)


def test_a_vision_trace_without_a_label_is_rejected():

    with pytest.raises(ClaimRequestMaterialError) as error:

        to_claim_request_material({"claim_trace": [{"claim_id": "au2_a"}]})

    assert REASON_MISSING_STATEMENT in str(error.value)


def test_a_non_source_is_rejected():

    for value in (None, "a string", 42, True):

        with pytest.raises(ClaimRequestMaterialError) as error:

            to_claim_request_material(value)

        assert REASON_NOT_A_SOURCE in str(error.value)


# ==========================================================
# 4. forbidden fields
# ==========================================================

def test_every_forbidden_field_is_rejected():

    for field in FORBIDDEN_SOURCE_FIELDS:

        with pytest.raises(ClaimRequestMaterialError) as error:

            to_claim_request_material(_conversation_source(**{field: "x"}))

        assert REASON_FORBIDDEN_FIELD in str(error.value)


def test_a_truth_field_is_rejected():

    with pytest.raises(ClaimRequestMaterialError) as error:

        to_claim_request_material(_conversation_source(truth_status="verified"))

    assert REASON_FORBIDDEN_FIELD in str(error.value)


def test_a_confidence_field_is_rejected():

    with pytest.raises(ClaimRequestMaterialError):

        to_claim_request_material(_conversation_source(confidence=0.9))

    with pytest.raises(ClaimRequestMaterialError):

        to_claim_request_material(_conversation_source(confidence_kind="learning_state"))


def test_a_proposal_field_is_rejected():

    for field in ("proposal", "proposal_fields", "interpretation_proposal"):

        with pytest.raises(ClaimRequestMaterialError):

            to_claim_request_material(_conversation_source(**{field: {}}))


def test_a_governance_identity_field_is_rejected():

    for field in ("claim_id", "licence_id", "candidate_reference", "scope_authority"):

        with pytest.raises(ClaimRequestMaterialError):

            to_claim_request_material(_conversation_source(**{field: "clm_x"}))


# ==========================================================
# 5-6. copied only / never derived
# ==========================================================

def test_claim_type_hint_is_copied_only():

    assert (
        to_claim_request_material(_conversation_source()).claim_type_hint
        == "existence"
    )

    # absent -> None (never fabricated)
    assert (
        to_claim_request_material({"raw_statement": "a bed exists"}).claim_type_hint
        is None
    )


def test_candidate_kind_is_never_converted_to_a_claim_type():

    for kind in ("preference", "rule", "constraint", "definition", "correction", "observation"):

        material = to_claim_request_material(
            {"raw_statement": "a bed exists", "candidate_kind": kind}
        )

        assert material.claim_type_hint is None


def test_knowledge_class_is_never_converted_to_a_claim_type():

    material = to_claim_request_material(
        {"normalized_meaning": "a closet is storage", "knowledge_class": "definition"}
    )

    assert material.claim_type_hint is None


def test_the_adapter_derives_nothing():

    called = _called_names(MODULE)

    for name in ("uuid4", "mint_id", "new_claim_id", "build_proposal", "mint_claim"):

        assert name not in called


# ==========================================================
# 7. immutability and exact fields
# ==========================================================

def test_the_material_is_immutable():

    material = to_claim_request_material(_conversation_source())

    for field in ("statement", "claim_type_hint", "basis", "limitations", "provenance"):

        with pytest.raises(ClaimRequestMaterialError):

            setattr(material, field, "changed")

    with pytest.raises(ClaimRequestMaterialError):

        del material.statement


def test_the_material_carries_exactly_five_fields():

    material = to_claim_request_material(_conversation_source())

    payload = material.to_dict()

    for field in ("statement", "claim_type_hint", "basis", "limitations", "provenance"):

        assert field in payload

    for extra in (
        "confidence",
        "truth",
        "status",
        "scope",
        "claim_id",
        "licence_id",
        "candidate_reference",
        "admission",
    ):

        assert extra not in payload


def test_the_material_declares_no_authority():

    assert ClaimRequestMaterial.CREATES_IDENTITY is False

    assert ClaimRequestMaterial.GRANTS_AUTHORITY is False

    assert ClaimRequestMaterial.CARRIES_CONFIDENCE is False

    assert ClaimRequestMaterial.DECIDES_TRUTH is False


# ==========================================================
# 8. dropped fields
# ==========================================================

def test_dropped_fields_are_ignored():

    source = _conversation_source(
        status="observed",
        scope="current_project",
        candidate_id="tc_abc",
        source_turn_id="turn_xyz",
        domain="storage",
        domain_tags=["storage"],
        zone_assignment={"zone": "storage"},
        space_topic="closet",
        entities=["closet"],
        relations=[],
        polarity="neutral",
        clause_role="rule",
        rationale="because storage",
        created_at=1.0,
        updated_at=1.0,
        uncertainty={"note": "hedged"},
    )

    material = to_claim_request_material(source)

    payload = material.to_dict()

    blob = repr(payload)

    assert "tc_abc" not in blob

    assert "turn_xyz" not in blob

    assert "closet" not in blob

    assert "because storage" not in blob

    assert set(payload) >= {
        "statement",
        "claim_type_hint",
        "basis",
        "limitations",
        "provenance",
    }


# ==========================================================
# 9. dependency direction
# ==========================================================

def test_no_governance_conversation_or_vision_import():

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


def test_the_module_does_not_persist():

    source = MODULE.read_text(encoding="utf-8")

    for token in ("open(", "json.dump", "pickle", "sqlite3", "shelve"):

        assert token not in source


# ==========================================================
# 10. single producer
# ==========================================================

def test_no_second_producer_can_build_a_material():

    with pytest.raises(ClaimRequestMaterialError) as error:

        ClaimRequestMaterial(statement="a bed exists")

    assert "only by the adapter" in str(error.value)


def test_the_adapter_is_the_only_public_producer():

    material = to_claim_request_material(_conversation_source())

    assert isinstance(material, ClaimRequestMaterial)
