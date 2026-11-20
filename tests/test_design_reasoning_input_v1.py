"""Tests for the transient ArchitecturalDesignReasoningInputV1 boundary.

Updated for the V1 context integration: the boundary now consumes the already
joined ``ArchitecturalDesignReasoningContextV1`` instead of
``ArchitecturalIntentResolutionV1``.
"""

import ast
import json
import os

import pytest

from core.design.architectural_intent.architectural_intent_resolution_v1 import (
    resolve_architectural_intent_v1,
)
from core.design.architectural_intent.architectural_intent_v1 import (
    build_architectural_intent_candidate_v1,
)
from core.design.design_reasoning.architectural_design_reasoning_context_v1 import (
    build_architectural_design_reasoning_context_v1,
)
from core.design.design_reasoning.design_reasoning_input_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    build_design_reasoning_input_v1,
)
from core.knowledge.architectural_semantic_library_v1 import (
    build_architectural_semantic_library_candidate_v1,
)
from core.knowledge.architectural_semantic_retrieval_v1 import (
    retrieve_architectural_semantic_patterns_v1,
)
from core.knowledge.foundation.architectural_semantic_graph_v1 import (
    build_architectural_semantic_graph_v1,
)
from core.teaching.architectural_teaching_record_v1 import (
    build_architectural_teaching_record_v1,
)
from core.teaching.architectural_teaching_session_v1 import (
    build_architectural_teaching_session_v1,
)

MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "core",
    "design",
    "design_reasoning",
    "design_reasoning_input_v1.py",
)


# --------------------------------------------------------------------------- #
# fixtures — built through the REAL upstream boundaries
# --------------------------------------------------------------------------- #
def _teaching_record(topic, pattern, evidence, claim_id):
    record = build_architectural_teaching_record_v1(
        {
            "contract": "ArchitecturalTeachingCandidateV1",
            "version": "1.0",
            "teaching_units": [
                {
                    "topic": topic,
                    "source_pattern": pattern,
                    "evidence_reference": evidence,
                    "source_claim_ids": [claim_id],
                    "grounding_status": ["visible"],
                    "uncertainty": {"unknowns": [], "evidence_conflicts": []},
                }
            ],
            "uncertainty": {
                "confidence": "bounded",
                "unknowns": [],
                "evidence_conflicts": [],
            },
        },
        "bounded human explanation of an observed association",
    )
    record["source_claim_ids"] = [claim_id]
    record["grounding_status"] = ["visible"]
    return record


def _resolution():
    library = build_architectural_semantic_library_candidate_v1(
        build_architectural_teaching_session_v1(
            [
                _teaching_record(
                    "sleeping_space_and_storage_association",
                    "sleeping_storage_relation",
                    ["sleeping_element", "wardrobe_or_closet"],
                    "au2_claim_001",
                ),
                _teaching_record(
                    "sleeping_space_and_sanitary_service_association",
                    "sleeping_sanitary_relation",
                    ["sleeping_element", "bathroom_or_ensuite"],
                    "au2_claim_002",
                ),
            ]
        )
    )
    retrieval = retrieve_architectural_semantic_patterns_v1(
        library, "sleeping_space_association"
    )
    return resolve_architectural_intent_v1(
        build_architectural_intent_candidate_v1(retrieval)
    )


def _graph():
    return build_architectural_semantic_graph_v1(
        {
            "contract": "ArchitecturalConceptOntologyV1",
            "version": "1.0",
            "concept_nodes": [
                {
                    "concept_id": "sleeping_space_with_storage_association",
                    "semantic_label": "sleeping_space_with_storage_association",
                    "source_patterns": ["sleeping_storage_relation"],
                    "evidence_reference": ["sleeping_element", "wardrobe_or_closet"],
                    "uncertainty": [],
                },
                {
                    "concept_id": "sleeping_space_with_sanitary_association",
                    "semantic_label": "sleeping_space_with_sanitary_association",
                    "source_patterns": ["sleeping_sanitary_relation"],
                    "evidence_reference": ["sleeping_element", "bathroom_or_ensuite"],
                    "uncertainty": [{"unknowns": ["service unresolved"]}],
                },
            ],
            "relationship_edges": [
                {
                    "relationship_type": "private_sleeping_concept_context",
                    "source_concepts": [
                        "sleeping_space_with_storage_association",
                        "sleeping_space_with_sanitary_association",
                    ],
                }
            ],
            "evidence_basis": [{"source_pattern": "sleeping_storage_relation"}],
            "uncertainty": {"matched_concepts": 2},
            "non_claims": {},
            "persistent": False,
            "read_only": True,
        }
    )


def _context():
    return build_architectural_design_reasoning_context_v1(_resolution(), _graph())


def _module_source():
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        return handle.read()


# --------------------------------------------------------------------------- #
# contract and shape
# --------------------------------------------------------------------------- #
def test_contract_version_source_and_output_shape():
    result = build_design_reasoning_input_v1(_context())

    assert result["contract"] == CONTRACT == "ArchitecturalDesignReasoningInputV1"
    assert result["version"] == VERSION == "1.0"
    assert SOURCE_CONTRACT == "ArchitecturalDesignReasoningContextV1"
    for field in (
        "intent_context",
        "semantic_context",
        "semantic_graph_context",
        "source_patterns",
        "source_evidence",
        "uncertainty",
        "open_questions",
        "non_claims",
        "persistent",
        "read_only",
    ):
        assert field in result, "missing output field: " + field


def test_source_contract_matches_the_real_context_module():
    from core.design.design_reasoning.architectural_design_reasoning_context_v1 import (
        CONTRACT as REAL_CONTEXT,
    )

    assert SOURCE_CONTRACT == REAL_CONTEXT


# --------------------------------------------------------------------------- #
# input boundary
# --------------------------------------------------------------------------- #
def test_accepts_only_the_joined_context():
    result = build_design_reasoning_input_v1(_context())
    assert result["intent_context"]
    assert result["semantic_graph_context"]["nodes"]


def test_rejects_the_old_resolution_input():
    """The previous accepted input must now be rejected."""
    with pytest.raises(ValueError):
        build_design_reasoning_input_v1(_resolution())


def test_rejects_every_other_contract():
    for contract in (
        "ArchitecturalIntentResolutionV1",
        "ArchitecturalIntentCandidateV1",
        "ArchitecturalSemanticRetrievalResultV1",
        "ArchitecturalSemanticGraphV1",
        "ArchitecturalKnowledgeCandidateV1",
        "ArchitecturalDesignReasoningResultV1",
        "ArchitecturalSpatialReasoningCandidateV1",
        "ArchitecturalKnowledgeAcquisitionBoundaryV1",
        "SiteIntentV1",
        "ImageIntentV1",
    ):
        with pytest.raises(ValueError):
            build_design_reasoning_input_v1({"contract": contract, "version": "1.0"})


def test_rejects_non_dict_and_wrong_version():
    for bad in (None, "raw", b"bytes", 42, 3.14, True, ["x"]):
        with pytest.raises(TypeError):
            build_design_reasoning_input_v1(bad)

    context = _context()
    context["version"] = "2.0"
    with pytest.raises(ValueError):
        build_design_reasoning_input_v1(context)


# --------------------------------------------------------------------------- #
# preservation
# --------------------------------------------------------------------------- #
def test_preserves_intent_context():
    context = _context()
    result = build_design_reasoning_input_v1(context)

    assert result["intent_context"] == [
        {
            "intent_group": group["intent_group"],
            "source_intents": group["source_intents"],
            "status": group["status"],
        }
        for group in context["intent_groups"]
    ]


def test_preserves_semantic_graph_context():
    context = _context()
    result = build_design_reasoning_input_v1(context)
    graph_context = result["semantic_graph_context"]

    assert graph_context["canonical_key"] == "source_patterns"
    assert graph_context["canonical_patterns"] == context["canonical_patterns"]
    assert graph_context["nodes"] == context["semantic_graph_nodes"]
    assert graph_context["edges"] == context["semantic_graph_edges"]
    assert graph_context["context_links"] == context["context_links"]


def test_preserves_source_patterns():
    context = _context()
    result = build_design_reasoning_input_v1(context)

    assert result["source_patterns"] == context["canonical_patterns"]
    assert result["source_patterns"] == [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    ]


def test_preserves_evidence_references():
    context = _context()
    result = build_design_reasoning_input_v1(context)

    assert result["source_evidence"] == [
        {
            "intent_group": group["intent_group"],
            "source_intents": group["source_intents"],
            "source_patterns": group["source_patterns"],
            "evidence_reference": group["evidence_reference"],
        }
        for group in context["intent_groups"]
    ]
    assert result["source_evidence"][0]["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
        "bathroom_or_ensuite",
    ]


def test_preserves_uncertainty():
    context = _context()
    result = build_design_reasoning_input_v1(context)
    assert result["uncertainty"] == context["uncertainty"]


def test_preserves_open_questions_behavior():
    result = build_design_reasoning_input_v1(_context())
    assert result["open_questions"] == []


# --------------------------------------------------------------------------- #
# transience and determinism
# --------------------------------------------------------------------------- #
def test_transient_and_read_only():
    result = build_design_reasoning_input_v1(_context())
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_deterministic_and_non_mutating():
    context = _context()
    original = json.loads(json.dumps(context))

    first = build_design_reasoning_input_v1(context)
    second = build_design_reasoning_input_v1(context)

    assert first == second
    assert context == original


def test_output_is_disjoint_from_its_source():
    context = _context()
    result = build_design_reasoning_input_v1(context)
    result["semantic_graph_context"]["nodes"][0]["semantic_label"] = "mutated"
    result["intent_context"][0]["source_intents"].append("injected")
    assert context["semantic_graph_nodes"][0]["semantic_label"] != "mutated"
    assert "injected" not in context["intent_groups"][0]["source_intents"]


def test_output_is_json_serialisable():
    json.dumps(build_design_reasoning_input_v1(_context()), sort_keys=True)


# --------------------------------------------------------------------------- #
# forbidden behaviour
# --------------------------------------------------------------------------- #
def test_non_claims_declared():
    result = build_design_reasoning_input_v1(_context())
    for key in (
        "not_design_reasoning",
        "not_design_solution",
        "not_recommendation",
        "not_design_rule",
        "not_layout",
        "not_spatial_decision",
        "not_geometry",
        "not_memory",
    ):
        assert result["non_claims"][key] is True


def test_no_forbidden_language_in_authored_payload():
    result = build_design_reasoning_input_v1(_context())
    payload = {
        key: value
        for key, value in result.items()
        if key
        not in ("non_claims", "semantic_graph_context", "source_evidence")
    }
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for term in (
        "should",
        "must",
        "required",
        "optimal",
        "best",
        "recommended",
        "adjacent",
        "layout",
        "geometry",
        "design solution",
        "design_solution",
    ):
        assert term not in serialized, "forbidden term present: " + term


def test_no_geometry_layout_or_spatial_output_fields():
    result = build_design_reasoning_input_v1(_context())
    for key in (
        "geometry",
        "coordinates",
        "dimensions",
        "polygons",
        "layout",
        "placement",
        "spatial_decisions",
        "recommendations",
        "rules",
    ):
        assert key not in result


def test_module_performs_no_io_and_no_memory_access():
    tree = ast.parse(_module_source())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0].lower())
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0].lower())
            for alias in node.names:
                imported.add(alias.name.split(".")[0].lower())
    for forbidden in ("memory", "learning", "database", "sqlite", "requests", "socket"):
        assert forbidden not in imported

    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            name = getattr(target, "attr", None) or getattr(target, "id", None)
            if name:
                called.add(name)
    for forbidden_call in ("write", "dump", "dumps", "save", "record", "open", "makedirs"):
        assert forbidden_call not in called


def test_module_does_not_import_the_declared_upstream_contracts():
    """The boundary must consume the CONTEXT contract, not reach back to the
    resolution or graph contracts directly."""
    source = _module_source()
    for forbidden in (
        "architectural_intent_resolution_v1",
        "architectural_semantic_graph_v1",
    ):
        assert forbidden not in source


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-q"]))
