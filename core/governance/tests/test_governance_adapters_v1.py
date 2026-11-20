"""Claim Governance adapters V1 — isolated boundary self-checks.

PASS expected
    * an AUv2 projection converts to proposals
    * the AUv2 id is discarded (never preserved as claim identity)
    * a projection carrying authority fields is rejected
    * a TeachingCandidate becomes ADVISORY material
    * no Claim and no LicenceRecord is created by any adapter

FAIL expected
    * an adapter creating a Claim
    * an adapter preserving au2_claim identity
    * an adapter assigning scope or licence
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.governance import FORBIDDEN_IMPORT_ROOTS
from core.governance.adapters import (
    Auv2AdapterError,
    TeachingCandidateAdapterError,
    TeachingProposalMaterial,
    prepare_endorsement_request,
    to_proposal,
    to_proposal_material,
    to_proposals,
)
from core.governance.endorsement import EndorsementRequest
from core.governance.proposal import InterpretationProposal


GOVERNANCE_DIR = Path(__file__).resolve().parents[1]

ADAPTERS_DIR = GOVERNANCE_DIR / "adapters"


def _auv2(extra=None):

    projection = {
        "contract": "ArchitecturalUnderstandingV2",
        "version": "2.0",
        "semantic_space": {
            "label": "bedroom",
            "status": "bounded_interpretation",
            "basis": ["sleeping element"],
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
                "source_evidence": ["sleeping_element", "window"],
                "grounding_status": ["visible"],
                "interpretation_basis": ["sleeping element"],
                "uncertainty": {
                    "confidence": "MEDIUM",
                    "grounding_status": ["visible"],
                    "unknowns": ["exact floor count is not determinable"],
                    "evidence_conflicts": ["au2_claim_002"],
                },
            },
            {
                "claim_id": "au2_claim_002",
                "claim_type": "functional_role",
                "source_evidence": ["sleeping_element"],
                "grounding_status": ["visible"],
                "interpretation_basis": ["sleeping element"],
                "uncertainty": {
                    "confidence": "MEDIUM",
                    "grounding_status": ["visible"],
                    "unknowns": [],
                    "evidence_conflicts": [],
                },
            },
        ],
        "interpretation_states": {
            "primary": {
                "label": "bedroom",
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
            "classification_basis": [],
        },
        "uncertainty": {"confidence": "MEDIUM", "unknowns": []},
        "non_claims": [
            "not_permanent_knowledge",
            "not_design_reasoning",
            "not_geometry",
            "not_cad_or_bim",
            "not_authoritative_space_identity",
        ],
        "geometry_authoritative": False,
        "read_only": True,
        "persistent": False,
    }

    if extra:

        projection.update(extra)

    return projection


# ----------------------------------------------------------
# ADAPTER 1: AUv2 -> InterpretationProposal
# ----------------------------------------------------------

def test_auv2_converts_to_proposals():

    proposals = to_proposals(_auv2(), language="en")

    assert len(proposals) == 2

    for proposal in proposals:

        assert isinstance(proposal, InterpretationProposal)

        assert proposal.AUTHORITY is False

    assert proposals[0].proposed_content == "bedroom"

    assert proposals[0].proposed_claim_type == "semantic_space"

    assert proposals[0].trigger_references == ("sleeping_element", "window")

    assert proposals[0].language == "en"

    assert "not_permanent_knowledge" in proposals[0].limitations


def test_auv2_primary_proposal_is_selected():

    proposal = to_proposal(_auv2())

    assert proposal.proposed_claim_type == "semantic_space"


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


def test_auv2_id_is_discarded():

    for proposal in to_proposals(_auv2()):

        payload = proposal.to_dict()

        assert not _contains_projection_id(payload), (
            "a projection-local au2_ id leaked into a proposal: %r" % (payload,)
        )

        # the id nested inside uncertainty is stripped too
        assert "au2_claim_002" not in str(payload)


def test_auv2_projection_carrying_authority_is_rejected():

    for key in ("claim_id", "licence", "scope", "truth_status", "knowledge_status"):

        with pytest.raises(Auv2AdapterError):

            to_proposals(_auv2({key: "forged"}))


def test_auv2_non_mapping_is_rejected():

    with pytest.raises(Auv2AdapterError):

        to_proposals("not a projection")

    with pytest.raises(Auv2AdapterError):

        to_proposals({"contract": "ArchitecturalUnderstandingV2"})


# ----------------------------------------------------------
# ADAPTER 2: TeachingCandidate -> advisory material
# ----------------------------------------------------------

def test_teaching_candidate_becomes_advisory_material():

    candidate = {
        "candidate_id": "tc_abc",
        "raw_statement": "پنجره باید دور از اتاق خواب باشد",
        "normalized_meaning": "the window must be away from the bedroom",
        "candidate_kind": "rule",
        "knowledge_class": "DESIGN_RULE",
        "scope": "CURRENT_PROJECT",
        "provenance": "HUMAN_TEACHER",
        "status": "observed",
    }

    material = to_proposal_material(candidate)

    assert isinstance(material, TeachingProposalMaterial)

    assert material.ADVISORY is True

    assert material.candidate_text == "the window must be away from the bedroom"

    assert material.advisory_category == "rule"

    assert material.provenance_reference == "HUMAN_TEACHER"

    payload = material.to_dict()

    # no scope authority, no licence, no knowledge-class authority
    assert "scope" not in payload

    assert "licence" not in payload

    assert payload["grants_scope"] is False

    assert payload["grants_knowledge_class"] is False

    assert payload["status_is_licence"] is False


def test_teaching_candidate_object_form_is_supported():

    candidate = SimpleNamespace(
        raw_statement="prefer a north-facing entrance",
        normalized_meaning="",
        candidate_kind="preference",
        provenance="HUMAN_TEACHER",
        status="observed",
    )

    material = to_proposal_material(candidate)

    assert material.advisory_category == "preference"

    assert material.candidate_text == "prefer a north-facing entrance"


def test_teaching_candidate_status_as_licence_is_rejected():

    with pytest.raises(TeachingCandidateAdapterError):

        to_proposal_material(
            {
                "raw_statement": "x",
                "status": "unlicensed_hypothesis",
            }
        )


def test_teaching_material_is_immutable():

    material = to_proposal_material(
        {"raw_statement": "x", "candidate_kind": "rule", "status": "observed"}
    )

    with pytest.raises(FrozenInstanceError):

        material.candidate_text = "rewritten"


# ----------------------------------------------------------
# ADAPTER 3: endorsement preparation (preparation only)
# ----------------------------------------------------------

def test_endorsement_preparation_builds_a_request():

    request = prepare_endorsement_request(
        "Yes, this interpretation is appropriate.",
        actor_reference="human:teacher",
        target_claim_reference="clm_0123456789abcdef",
        requested_scope="single_case",
    )

    assert isinstance(request, EndorsementRequest)

    assert request.act_classification.act_type == "endorsement"

    assert request.REQUESTS_LICENCE is False


def test_endorsement_preparation_does_not_call_the_service():

    source = (
        ADAPTERS_DIR / "endorsement_preparation_adapter_v1.py"
    ).read_text(encoding="utf-8")

    assert "prepare_endorsement_event" not in source

    assert "record_endorsement_event" not in source


# ----------------------------------------------------------
# FAIL expected: adapters never create governed objects
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
)


_AUTHORITY_IDENTIFIERS = (
    "truth_score",
    "confidence_as_truth",
    "approval_as_fact",
    "human_validated_truth",
    "truth_status",
    "knowledge_status",
)


def test_adapters_create_no_claim_and_no_licence():

    offenders = []

    for path in sorted(ADAPTERS_DIR.rglob("*.py")):

        for name in _identifiers(_parse(path)):

            if name in _CREATION_IDENTIFIERS:

                offenders.append((str(path), name))

    assert offenders == [], (
        "an adapter created a governed object: %r" % (offenders,)
    )


def test_adapters_assign_no_truth_or_knowledge_status():

    offenders = []

    for path in sorted(ADAPTERS_DIR.rglob("*.py")):

        for name in _identifiers(_parse(path)):

            if name in _AUTHORITY_IDENTIFIERS:

                offenders.append((str(path), name))

    assert offenders == [], (
        "an adapter carried a truth or knowledge-status identifier: %r"
        % (offenders,)
    )


def test_adapters_preserve_no_projection_identity_as_claim_identity():

    for proposal in to_proposals(_auv2()):

        assert not _contains_projection_id(proposal.to_dict())

    # the adapter names the prefix only to DISCARD it
    source = (ADAPTERS_DIR / "auv2_proposal_adapter_v1.py").read_text(
        encoding="utf-8"
    )

    assert "PROJECTION_ID_PREFIX" in source

    assert "_strip_projection_ids" in source


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


def test_adapters_import_no_client_subsystem():

    offenders = []

    for path in sorted(ADAPTERS_DIR.rglob("*.py")):

        for module in _imported_modules(path):

            for forbidden in FORBIDDEN_IMPORT_ROOTS:

                if module == forbidden or module.startswith(forbidden + "."):

                    offenders.append((str(path), module))

    assert offenders == [], (
        "an adapter imported a client subsystem: %r" % (offenders,)
    )


def test_adapters_import_governance_only():

    offenders = []

    for path in sorted(ADAPTERS_DIR.rglob("*.py")):

        for module in _imported_modules(path):

            if module.startswith("core.") and not module.startswith(
                "core.governance."
            ):

                offenders.append((str(path), module))

    assert offenders == [], (
        "an adapter imported outside governance: %r" % (offenders,)
    )


def test_governance_does_not_import_the_adapters_backwards():

    offenders = []

    for area in (
        "claim",
        "licence",
        "events",
        "proposal",
        "lineage",
        "validation",
        "act_classifier",
        "endorsement",
    ):

        for path in sorted((GOVERNANCE_DIR / area).rglob("*.py")):

            for module in _imported_modules(path):

                if module.startswith("core.governance.adapters"):

                    offenders.append((str(path), module))

    assert offenders == [], (
        "a core governance module imported an adapter (direction reversed): %r"
        % (offenders,)
    )
