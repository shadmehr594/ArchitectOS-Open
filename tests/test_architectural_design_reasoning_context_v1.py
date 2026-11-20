"""Contract tests for ArchitecturalDesignReasoningContextV1.

Written from the BRIEF's requirements, not from the implementation. Each test
pins one requirement sentence: accepted inputs, validation, the six preservation
duties, determinism, read-only/transient, the canonical key, and the forbidden
language / no-interpretation rules.
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
    CANONICAL_KEY,
    CONTRACT,
    GRAPH_CONTRACT,
    RESOLUTION_CONTRACT,
    VERSION,
    build_architectural_design_reasoning_context_v1,
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
    "architectural_design_reasoning_context_v1.py",
)


# --------------------------------------------------------------------------- #
# fixtures — built through the REAL upstream boundaries, never hand-rolled
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
    intent = build_architectural_intent_candidate_v1(retrieval)
    return resolve_architectural_intent_v1(intent)


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
# contract validation
# --------------------------------------------------------------------------- #
def test_contract_version_and_required_output_fields():
    result = _context()

    assert result["contract"] == CONTRACT
    assert CONTRACT == "ArchitecturalDesignReasoningContextV1"
    assert result["version"] == VERSION == "1.0"
    for field in (
        "contract",
        "version",
        "intent_groups",
        "source_intents",
        "canonical_key",
        "canonical_patterns",
        "context_links",
        "semantic_graph_nodes",
        "semantic_graph_edges",
        "evidence_basis",
        "uncertainty",
        "non_claims",
        "persistent",
        "read_only",
    ):
        assert field in result, "missing output field: " + field


def test_accepts_only_the_two_declared_contracts():
    result = _context()
    assert result["canonical_key"] == CANONICAL_KEY == "source_patterns"
    # both declared inputs contributed
    assert result["intent_groups"]
    assert result["semantic_graph_nodes"]


def test_rejects_every_other_contract_in_both_positions():
    forbidden = (
        "ArchitecturalSemanticRetrievalResultV1",
        "ArchitecturalIntentCandidateV1",
        "ArchitecturalDesignReasoningInputV1",
        "ArchitecturalDesignReasoningResultV1",
        "ArchitecturalSpatialReasoningCandidateV1",
        "ArchitecturalKnowledgeAcquisitionBoundaryV1",
        "ArchitecturalConceptOntologyV1",
        "ArchitecturalConceptRelationshipV1",
        "ArchitecturalConceptUnderstandingV1",
        "ArchitecturalFoundationKnowledgeAccessV1",
        "ArchitecturalFoundationKnowledgeSetV1",
        "ArchitecturalKnowledgeCurriculumV1",
        "ArchitecturalTeachingSessionV1",
        "SiteIntentV1",
        "ImageIntentV1",
    )
    for contract in forbidden:
        payload = {"contract": contract, "version": "1.0"}
        with pytest.raises(ValueError):
            build_architectural_design_reasoning_context_v1(payload, _graph())
        with pytest.raises(ValueError):
            build_architectural_design_reasoning_context_v1(_resolution(), payload)


def test_rejects_non_dict_inputs_in_both_positions():
    for bad in (None, "raw", b"bytes", 42, 3.14, True, ["x"]):
        with pytest.raises(TypeError):
            build_architectural_design_reasoning_context_v1(bad, _graph())
        with pytest.raises(TypeError):
            build_architectural_design_reasoning_context_v1(_resolution(), bad)


def test_rejects_wrong_versions():
    resolution = _resolution()
    resolution["version"] = "2.0"
    with pytest.raises(ValueError):
        build_architectural_design_reasoning_context_v1(resolution, _graph())

    graph = _graph()
    graph["version"] = "2.0"
    with pytest.raises(ValueError):
        build_architectural_design_reasoning_context_v1(_resolution(), graph)


def test_declared_source_contracts_match_the_real_upstream_modules():
    from core.design.architectural_intent.architectural_intent_resolution_v1 import (
        CONTRACT as REAL_RESOLUTION,
    )
    from core.knowledge.foundation.architectural_semantic_graph_v1 import (
        CONTRACT as REAL_GRAPH,
    )

    assert RESOLUTION_CONTRACT == REAL_RESOLUTION
    assert GRAPH_CONTRACT == REAL_GRAPH


# --------------------------------------------------------------------------- #
# preservation: intent groups / source intents
# --------------------------------------------------------------------------- #
def test_preserves_intent_groups():
    resolution = _resolution()
    result = build_architectural_design_reasoning_context_v1(resolution, _graph())

    source_groups = resolution["intent_groups"]
    assert len(result["intent_groups"]) == len(source_groups)
    for produced, source in zip(result["intent_groups"], source_groups):
        assert produced["intent_group"] == source["intent_group"]
        assert produced["status"] == source["status"]
        assert produced["source_intents"] == source["source_intents"]
        assert produced["source_patterns"] == source["source_patterns"]
        assert produced["evidence_reference"] == source["evidence_reference"]
        assert produced["uncertainty"] == source["uncertainty"]


def test_preserves_source_intents_and_semantic_components():
    resolution = _resolution()
    result = build_architectural_design_reasoning_context_v1(resolution, _graph())

    assert result["source_intents"] == resolution["source_intents"]
    assert result["semantic_components"] == resolution["semantic_components"]


def test_preserves_nested_uncertainty_structure_exactly():
    """Resolution uncertainty is deeply nested; it must not be flattened."""
    resolution = _resolution()
    result = build_architectural_design_reasoning_context_v1(resolution, _graph())

    assert result["intent_groups"][0]["uncertainty"] == (
        resolution["intent_groups"][0]["uncertainty"]
    )
    assert result["uncertainty"]["intent_resolution"] == resolution["uncertainty"]


# --------------------------------------------------------------------------- #
# canonical key: source_patterns
# --------------------------------------------------------------------------- #
def test_canonical_patterns_are_collected_from_intent_groups():
    result = _context()
    assert result["canonical_patterns"] == [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    ]
    assert result["canonical_patterns"] == result["intent_groups"][0]["source_patterns"]


def test_join_uses_source_patterns_and_links_the_matching_nodes():
    result = _context()
    assert len(result["context_links"]) == len(result["intent_groups"])
    link = result["context_links"][0]
    assert link["canonical_key"] == "source_patterns"
    assert link["status"] == "bounded_context_link"
    assert set(link["linked_node_ids"]) == {
        "sleeping_space_with_storage_association",
        "sleeping_space_with_sanitary_association",
    }
    assert link["unlinked_patterns"] == []


def test_identity_is_never_established_by_label_or_group_name():
    """Concept labels are contextual: renaming every label must not change links."""
    graph = _graph()
    for node in graph["nodes"]:
        node["semantic_label"] = "renamed_" + str(node["semantic_label"])
        node["node_id"] = node["node_id"]  # ids stay; labels are contextual
    result = build_architectural_design_reasoning_context_v1(_resolution(), graph)
    assert result["context_links"][0]["status"] == "bounded_context_link"
    assert result["context_links"][0]["unlinked_patterns"] == []


def test_unlinked_pattern_is_reported_not_invented():
    resolution = _resolution()
    resolution["intent_groups"][0]["source_patterns"] = [
        "a_pattern_absent_from_the_graph"
    ]
    result = build_architectural_design_reasoning_context_v1(resolution, _graph())

    link = result["context_links"][0]
    assert link["linked_node_ids"] == []
    assert link["status"] == "unlinked_context"
    assert link["unlinked_patterns"] == ["a_pattern_absent_from_the_graph"]
    assert result["uncertainty"]["unlinked_patterns"] == [
        "a_pattern_absent_from_the_graph"
    ]
    assert result["uncertainty"]["unlinked_pattern_count"] == 1


# --------------------------------------------------------------------------- #
# preservation: graph nodes and edges
# --------------------------------------------------------------------------- #
def test_preserves_graph_nodes():
    graph = _graph()
    result = build_architectural_design_reasoning_context_v1(_resolution(), graph)

    assert result["semantic_graph_nodes"] == graph["nodes"]


def test_preserves_graph_edges_including_absence_of_fields():
    graph = _graph()
    result = build_architectural_design_reasoning_context_v1(_resolution(), graph)

    assert result["semantic_graph_edges"] == graph["edges"]
    for edge in result["semantic_graph_edges"]:
        # upstream edges declare neither, so the boundary must not invent them
        assert "uncertainty" not in edge
        assert "evidence_reference" not in edge


def test_node_uncertainty_is_a_faithful_passthrough_of_the_graph():
    """The graph boundary normalises an empty list to ``{}``; the context
    boundary must not re-normalise — it passes through exactly what it received.
    This is asserted against the live graph, not against a hardcoded shape."""
    graph = _graph()
    result = build_architectural_design_reasoning_context_v1(_resolution(), graph)

    for produced, source in zip(result["semantic_graph_nodes"], graph["nodes"]):
        assert produced["uncertainty"] == source["uncertainty"]

    nodes = {node["node_id"]: node for node in result["semantic_graph_nodes"]}
    # non-empty uncertainty is preserved structurally, not flattened
    assert nodes["sleeping_space_with_sanitary_association"]["uncertainty"] == [
        {"unknowns": ["service unresolved"]}
    ]


# --------------------------------------------------------------------------- #
# preservation: evidence and uncertainty
# --------------------------------------------------------------------------- #
def test_preserves_evidence_references_from_both_inputs():
    resolution = _resolution()
    graph = _graph()
    result = build_architectural_design_reasoning_context_v1(resolution, graph)

    kinds = [entry["evidence_type"] for entry in result["evidence_basis"]]
    assert kinds == ["intent_resolution", "semantic_graph"]

    by_kind = {entry["evidence_type"]: entry for entry in result["evidence_basis"]}
    assert by_kind["intent_resolution"]["basis"] == resolution["evidence_basis"]
    assert by_kind["semantic_graph"]["basis"] == graph["evidence_basis"]
    assert by_kind["semantic_graph"]["reference"]["contract"] == GRAPH_CONTRACT
    assert by_kind["intent_resolution"]["reference"]["contract"] == RESOLUTION_CONTRACT


def test_preserves_graph_uncertainty_verbatim():
    graph = _graph()
    result = build_architectural_design_reasoning_context_v1(_resolution(), graph)
    assert result["uncertainty"]["semantic_graph"] == graph["uncertainty"]


def test_declares_no_interpretation_or_reasoning():
    result = _context()
    assert result["uncertainty"]["interpreted"] is False
    assert result["uncertainty"]["reasoned"] is False


# --------------------------------------------------------------------------- #
# determinism, read-only, transient
# --------------------------------------------------------------------------- #
def test_deterministic_for_the_same_inputs():
    first = build_architectural_design_reasoning_context_v1(_resolution(), _graph())
    second = build_architectural_design_reasoning_context_v1(_resolution(), _graph())
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_output_is_json_serialisable():
    json.dumps(_context(), sort_keys=True)


def test_read_only_and_not_persistent():
    result = _context()
    assert result["read_only"] is True
    assert result["persistent"] is False


def test_inputs_are_never_mutated_and_output_is_disjoint():
    resolution = _resolution()
    graph = _graph()
    frozen_resolution = json.loads(json.dumps(resolution))
    frozen_graph = json.loads(json.dumps(graph))

    result = build_architectural_design_reasoning_context_v1(resolution, graph)

    assert resolution == frozen_resolution
    assert graph == frozen_graph

    result["semantic_graph_nodes"][0]["semantic_label"] = "mutated"
    result["intent_groups"][0]["source_intents"].append("injected")
    assert graph["nodes"][0]["semantic_label"] != "mutated"
    assert resolution["intent_groups"][0]["source_intents"] == [
        "sleeping_private_space_intent",
        "storage_associated_intent",
        "sanitary_service_associated_intent",
    ]


# --------------------------------------------------------------------------- #
# forbidden behaviour
# --------------------------------------------------------------------------- #
def test_non_claims_declared():
    result = _context()
    assert result["non_claims"]["not_design_reasoning"] is True
    assert result["non_claims"]["not_layout"] is True
    assert result["non_claims"]["not_spatial_decision"] is True
    assert result["non_claims"]["not_geometry"] is True
    assert result["non_claims"]["not_memory"] is True
    assert result["non_claims"]["not_authoritative_knowledge"] is True


def test_no_forbidden_language_in_the_authored_payload():
    result = _context()
    import copy

    payload = copy.deepcopy(result)
    payload.pop("non_claims", None)
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for term in (
        "should",
        "must",
        "required",
        "optimal",
        "best",
        "recommended",
        "design solution",
        "design rule",
        "geometry",
        "cad",
        "bim",
        "ifc",
    ):
        assert term not in serialized, "forbidden term present: " + term


def test_no_geometry_or_spatial_output_fields():
    result = _context()
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


def test_forbidden_language_scanner_is_not_vacuous():
    """Negative control: the check must fire on a normative payload."""
    from core.design.design_reasoning.architectural_design_reasoning_context_v1 import (
        _assert_safe,
    )

    with pytest.raises(AssertionError):
        _assert_safe({"note": "the wardrobe should sit adjacent"}, "probe")
    with pytest.raises(AssertionError):
        _assert_safe({"note": "this is the best arrangement"}, "probe")


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-q"]))
