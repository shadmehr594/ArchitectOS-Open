"""Contract tests for the ArchitecturalKnowledgeAcquisitionBoundaryV1.

Written from the BRIEF's semantics, not from the implementation: the brief
enumerates the accepted input, the rejected input, the output contract, the
acquisition status vocabulary, the preservation duties, the forbidden
behaviour and the required non-claims. Each test pins one of those sentences.
"""

import json
import os
import sys
import tempfile

import pytest

from core.knowledge.acquisition.architectural_knowledge_acquisition_boundary_v1 import (
    ACQUISITION_STATUSES,
    CONTRACT,
    EXAMPLE_REQUIRED_FIELDS,
    SOURCE_CONTRACT,
    VERSION,
    build_architectural_knowledge_acquisition_candidate_v1,
)
from core.knowledge.foundation.architectural_semantic_graph_v1 import (
    build_architectural_semantic_graph_v1,
)

MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "core",
    "knowledge",
    "acquisition",
    "architectural_knowledge_acquisition_boundary_v1.py",
)


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
def _ontology():
    return {
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
        "evidence_basis": [
            {
                "source_pattern": "sleeping_storage_relation",
                "evidence_reference": ["sleeping_element", "wardrobe_or_closet"],
            }
        ],
        "uncertainty": {"matched_concepts": 2},
        "non_claims": {},
        "persistent": False,
        "read_only": True,
    }


def _graph():
    return build_architectural_semantic_graph_v1(_ontology())


def _example():
    return {
        "example_id": "au2_example_001",
        "domain": "residential_sleeping_space",
        "description": "A sleeping space associated with a wardrobe zone.",
        "human_explanation": (
            "In this human-provided example the wardrobe sits with the "
            "sleeping zone, as observed in the referenced project."
        ),
        "related_concepts": [
            "sleeping_space_with_storage_association",
            "sleeping_space_with_sanitary_association",
        ],
        "related_patterns": [
            "sleeping_storage_relation",
            "sleeping_sanitary_relation",
        ],
    }


def _module_source():
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        return handle.read()


# --------------------------------------------------------------------------- #
# 1. contract validation
# --------------------------------------------------------------------------- #
def test_contract_and_version_and_required_output_fields():
    result = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), _example()
    )

    assert result["contract"] == CONTRACT
    assert CONTRACT == "ArchitecturalKnowledgeAcquisitionBoundaryV1"
    assert result["version"] == VERSION == "1.0"

    for field in (
        "contract",
        "version",
        "source_graph_reference",
        "architectural_example",
        "linked_concepts",
        "linked_patterns",
        "evidence_basis",
        "uncertainty",
        "acquisition_status",
        "non_claims",
        "persistent",
        "read_only",
    ):
        assert field in result, "missing output field: " + field


def test_source_graph_reference_is_a_reference_and_not_a_copy():
    graph = _graph()
    result = build_architectural_knowledge_acquisition_candidate_v1(
        graph, _example()
    )
    reference = result["source_graph_reference"]

    assert reference["contract"] == SOURCE_CONTRACT == "ArchitecturalSemanticGraphV1"
    assert reference["version"] == "1.0"
    assert reference["reference_only"] is True
    assert reference["read_only"] is True
    assert reference["node_references"] == [node["node_id"] for node in graph["nodes"]]
    # A reference must not carry a mutable duplicate of the graph's nodes.
    assert "nodes" not in reference
    assert "edges" not in reference


def test_acquisition_status_is_in_the_allowed_vocabulary():
    result = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), _example()
    )
    assert result["acquisition_status"] in ACQUISITION_STATUSES
    assert set(ACQUISITION_STATUSES) == {
        "candidate_received",
        "bounded_association",
        "requires_validation",
    }


def test_status_requires_validation_when_an_example_reference_is_unresolved():
    example = _example()
    example["related_patterns"] = ["a_pattern_the_graph_does_not_hold"]
    result = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), example
    )
    assert result["acquisition_status"] == "requires_validation"
    assert result["uncertainty"]["unresolved_count"] >= 1


# --------------------------------------------------------------------------- #
# 2. semantic graph only input acceptance
# --------------------------------------------------------------------------- #
def test_accepts_only_the_semantic_graph_as_primary_input():
    result = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), _example()
    )
    assert result["source_graph_reference"]["contract"] == SOURCE_CONTRACT
    assert result["architectural_example"]["example_id"] == "au2_example_001"


def test_rejects_non_dict_primary_input():
    for bad in (None, "raw image bytes", b"\x89PNG", 42, 3.14, True, ["graph"]):
        with pytest.raises(TypeError):
            build_architectural_knowledge_acquisition_candidate_v1(bad, _example())


# --------------------------------------------------------------------------- #
# 3. invalid input rejection
# --------------------------------------------------------------------------- #
def test_rejects_every_named_forbidden_primary_input():
    for contract in (
        "ArchitecturalUnderstandingV2",
        "ArchitecturalKnowledgeCandidateV1",
        "ArchitecturalTeachingRecordV1",
        "ArchitecturalTeachingSessionV1",
        "ArchitecturalDesignReasoningResultV1",
        "ArchitecturalVisionInterpreterV1",
        "VisionObservationV1",
        "ArchitecturalObservationV1",
        "GeometryV1",
        "CADModelV1",
        "BIMModelV1",
        "IFCProjectV1",
    ):
        with pytest.raises(ValueError):
            build_architectural_knowledge_acquisition_candidate_v1(
                {"contract": contract, "version": "1.0"}, _example()
            )


def test_rejects_wrong_graph_version():
    graph = _graph()
    graph["version"] = "2.0"
    with pytest.raises(ValueError):
        build_architectural_knowledge_acquisition_candidate_v1(graph, _example())


def test_rejects_example_missing_required_fields():
    for field in EXAMPLE_REQUIRED_FIELDS:
        example = _example()
        del example[field]
        with pytest.raises(ValueError):
            build_architectural_knowledge_acquisition_candidate_v1(
                _graph(), example
            )


def test_rejects_non_dict_example():
    with pytest.raises(TypeError):
        build_architectural_knowledge_acquisition_candidate_v1(_graph(), "example")


# --------------------------------------------------------------------------- #
# 4. concept linking preservation
# --------------------------------------------------------------------------- #
def test_concept_link_preserves_ids_labels_patterns_and_evidence():
    graph = _graph()
    result = build_architectural_knowledge_acquisition_candidate_v1(
        graph, _example()
    )
    links = {link["concept_id"]: link for link in result["linked_concepts"]}

    assert set(links) == {
        "sleeping_space_with_storage_association",
        "sleeping_space_with_sanitary_association",
    }
    storage = links["sleeping_space_with_storage_association"]
    node = graph["nodes"][0]
    assert storage["concept_id"] == node["node_id"]
    assert storage["semantic_label"] == node["semantic_label"]
    assert storage["source_patterns"] == node["source_patterns"]
    assert storage["evidence_reference"] == node["evidence_reference"]
    assert storage["uncertainty"] == node["uncertainty"]
    assert storage["status"] == "bounded_concept_link"


def test_concept_linking_generates_no_unrequested_links():
    example = _example()
    example["related_concepts"] = ["sleeping_space_with_storage_association"]
    result = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), example
    )
    assert [link["concept_id"] for link in result["linked_concepts"]] == [
        "sleeping_space_with_storage_association"
    ]


# --------------------------------------------------------------------------- #
# 5. pattern linking preservation
# --------------------------------------------------------------------------- #
def test_pattern_link_preserves_pattern_and_concept_references():
    result = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), _example()
    )
    patterns = {link["pattern_id"]: link for link in result["linked_patterns"]}

    assert set(patterns) == {
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    }
    sanitary = patterns["sleeping_sanitary_relation"]
    assert sanitary["concept_id"] == "sleeping_space_with_sanitary_association"
    assert sanitary["evidence_reference"] == [
        "sleeping_element",
        "bathroom_or_ensuite",
    ]
    assert sanitary["status"] == "bounded_pattern_link"


def test_unresolved_pattern_is_not_guessed():
    example = _example()
    example["related_patterns"] = ["place_bed_near_window"]
    result = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), example
    )
    assert result["linked_patterns"] == []
    assert result["uncertainty"]["unresolved_example_references"]["patterns"] == [
        "place_bed_near_window"
    ]


# --------------------------------------------------------------------------- #
# 6. evidence preservation
# --------------------------------------------------------------------------- #
def test_evidence_basis_preserves_graph_evidence_and_example_provenance():
    graph = _graph()
    example = _example()
    result = build_architectural_knowledge_acquisition_candidate_v1(graph, example)

    kinds = [entry["evidence_type"] for entry in result["evidence_basis"]]
    assert "source_semantic_graph" in kinds
    assert "human_provided_example" in kinds

    graph_entry = next(
        entry
        for entry in result["evidence_basis"]
        if entry["evidence_type"] == "source_semantic_graph"
    )
    assert graph_entry["basis"] == graph["evidence_basis"]

    example_entry = next(
        entry
        for entry in result["evidence_basis"]
        if entry["evidence_type"] == "human_provided_example"
    )
    assert example_entry["reference"]["example_id"] == "au2_example_001"
    assert example_entry["reference"]["domain"] == "residential_sleeping_space"


# --------------------------------------------------------------------------- #
# 7. uncertainty preservation
# --------------------------------------------------------------------------- #
def test_uncertainty_preserves_graph_and_node_uncertainty():
    graph = _graph()
    result = build_architectural_knowledge_acquisition_candidate_v1(
        graph, _example()
    )
    uncertainty = result["uncertainty"]

    assert uncertainty["graph_uncertainty"] == graph["uncertainty"]
    node_uncertainty = {
        entry["node_id"]: entry["uncertainty"]
        for entry in uncertainty["node_uncertainty"]
    }
    assert node_uncertainty["sleeping_space_with_sanitary_association"] == [
        {"unknowns": ["service unresolved"]}
    ]
    assert uncertainty["validated"] is False


def test_uncertainty_declares_no_interpretation_was_generated():
    result = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), _example()
    )
    assert result["uncertainty"]["explanation_interpreted"] is False
    assert result["uncertainty"]["example_interpretation_generated"] is False


# --------------------------------------------------------------------------- #
# 8. no persistence
# --------------------------------------------------------------------------- #
def test_candidate_is_transient_and_read_only():
    result = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), _example()
    )
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_no_file_is_written_anywhere():
    before = set(os.listdir(tempfile.gettempdir()))
    workdir = tempfile.mkdtemp(prefix="acq_no_persist_")
    cwd = os.getcwd()
    os.chdir(workdir)
    try:
        build_architectural_knowledge_acquisition_candidate_v1(
            _graph(), _example()
        )
        assert os.listdir(workdir) == []
    finally:
        os.chdir(cwd)
        os.rmdir(workdir)
    after = set(os.listdir(tempfile.gettempdir()))
    assert after - before == set()


def test_module_contains_no_persistence_or_memory_calls():
    source = _module_source().lower()
    for token in (
        "open(",
        ".write(",
        ".record(",
        "json.dump",
        "pickle",
        "sqlite",
        "save(",
        "requests.",
        "import comfy",
        "os.makedirs",
        "pathlib.",
    ):
        if token == "open(":
            # `open(` only appears in the test-facing docstrings; assert on the
            # call shape instead of a bare substring.
            assert ".open(" not in source
            continue
        assert token not in source, "module performs forbidden operation: " + token


# --------------------------------------------------------------------------- #
# 9. no Memory connection
# --------------------------------------------------------------------------- #
def test_module_does_not_import_or_touch_memory():
    """Parsed with ``ast``, never grepped: the module's own docstring names
    Memory in order to disclaim it, so a text scan would flag its own prose."""
    import ast

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

    for forbidden in ("memory", "learning", "learner", "persistence", "database"):
        assert forbidden not in imported, "module imports " + forbidden

    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            name = getattr(target, "attr", None) or getattr(target, "id", None)
            if name:
                called.add(name)
    for forbidden_call in ("write", "dump", "dumps", "save", "record", "open", "makedirs"):
        assert forbidden_call not in called, "module calls " + forbidden_call


def test_output_declares_not_memory_and_not_learned_model():
    result = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), _example()
    )
    assert result["non_claims"]["not_memory"] is True
    assert result["non_claims"]["not_learned_model"] is True


# --------------------------------------------------------------------------- #
# 10. no automatic learning
# --------------------------------------------------------------------------- #
def test_no_graph_mutation_and_no_promotion():
    graph = _graph()
    example = _example()
    frozen_graph = json.loads(json.dumps(graph))
    frozen_example = json.loads(json.dumps(example))

    build_architectural_knowledge_acquisition_candidate_v1(graph, example)

    assert graph == frozen_graph
    assert example == frozen_example


def test_candidate_is_disjoint_from_its_sources():
    graph = _graph()
    result = build_architectural_knowledge_acquisition_candidate_v1(
        graph, _example()
    )
    result["linked_concepts"][0]["semantic_label"] = "changed"
    result["source_graph_reference"]["node_references"].append("injected")
    assert graph["nodes"][0]["semantic_label"] == (
        "sleeping_space_with_storage_association"
    )
    assert len(graph["nodes"]) == 2


def test_output_non_claims_full_set():
    result = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), _example()
    )
    assert result["non_claims"] == {
        "not_memory": True,
        "not_learned_model": True,
        "not_authoritative_knowledge": True,
        "not_design_rule": True,
        "not_recommendation": True,
        "not_design_solution": True,
    }


# --------------------------------------------------------------------------- #
# 11. deterministic output
# --------------------------------------------------------------------------- #
def test_deterministic_for_the_same_inputs():
    first = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), _example()
    )
    second = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), _example()
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_output_is_json_serialisable():
    result = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), _example()
    )
    json.dumps(result, sort_keys=True)


# --------------------------------------------------------------------------- #
# forbidden language
# --------------------------------------------------------------------------- #
def test_structural_payload_contains_no_forbidden_language():
    result = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), _example()
    )
    structural = {
        key: value
        for key, value in result.items()
        if key not in ("non_claims", "architectural_example", "evidence_basis")
    }
    serialized = json.dumps(structural, ensure_ascii=False).lower()
    for term in (
        "should",
        "must",
        "required",
        "optimal",
        "best",
        "recommended",
        "design rule",
        "design solution",
        "layout rule",
        "placement",
        "geometry",
    ):
        assert term not in serialized


def test_human_narrative_is_preserved_verbatim_even_when_normative():
    example = _example()
    example["human_explanation"] = (
        "In this example the wardrobe is the best placement next to the bed."
    )
    result = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), example
    )
    # Preserved verbatim (the human's words are not edited) ...
    assert result["architectural_example"]["human_explanation"] == (
        "In this example the wardrobe is the best placement next to the bed."
    )
    # ... and it never enters the structural payload.
    assert "best" not in json.dumps(
        {k: v for k, v in result.items() if k != "architectural_example"}
    ).lower()


def test_no_geometry_or_bim_or_cad_fields_in_output():
    result = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), _example()
    )
    for key in ("geometry", "coordinates", "dimensions", "polygons", "cad", "bim", "ifc"):
        assert key not in result


def test_forbidden_language_scanner_is_not_vacuous():
    """Negative control: the check must FIRE on a genuinely normative payload.

    Without this, a scanner that never matches anything would pass every other
    assertion in this file.
    """
    from core.knowledge.acquisition.architectural_knowledge_acquisition_boundary_v1 import (
        _forbidden_language_check,
    )

    with pytest.raises(AssertionError):
        _forbidden_language_check(
            {
                "contract": "X",
                "version": "1.0",
                "note": "the wardrobe should sit adjacent to the bed",
                "non_claims": {"not_design_rule": True},
            }
        )
    # ... and it must be word-bounded, so ordinary words never trip it.
    with pytest.raises(AssertionError):
        _forbidden_language_check({"note": "this is the best arrangement"})
    _forbidden_language_check({"note": "a mustard coloured surface and to bestow"})


def test_non_claim_flags_do_not_trip_their_own_check():
    """The scan reads VALUES it authored and never the non-claim flags, whose
    keys literally contain the forbidden terms (`not_design_rule`)."""
    result = build_architectural_knowledge_acquisition_candidate_v1(
        _graph(), _example()
    )
    assert result["non_claims"]["not_design_rule"] is True
    assert result["non_claims"]["not_recommendation"] is True
    assert result["non_claims"]["not_design_solution"] is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
