"""Tests for ArchitecturalConceptUnderstandingBuilderV1.

This suite covers the producer boundary that connects
ArchitecturalFoundationKnowledgeAccessV1 to ArchitecturalConceptUnderstandingV1.
It asserts:
  - the gate accepts ONLY ArchitecturalFoundationKnowledgeAccessV1
  - the produced envelope is accepted by the downstream understanding boundary
  - source patterns / evidence / grounding / claim IDs / uncertainty survive
  - the boundary is deterministic, transient, read-only and non-mutating
  - no design / geometry / Memory / reasoning leakage exists
  - the structure spine runs end-to-end on real teaching data (the seam
    this module was created to close)
"""

import ast
import copy
import json

import pytest

from core.knowledge.foundation.architectural_concept_understanding_builder_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    SOURCE_VERSION,
    TARGET_CONTRACT,
    VERSION,
    build_architectural_concept_understanding_input_v1,
)
from core.knowledge.foundation.architectural_concept_understanding_v1 import (
    build_architectural_concept_understanding_v1,
)
from core.knowledge.foundation.architectural_concept_relationship_v1 import (
    build_architectural_concept_relationship_v1,
)
from core.knowledge.foundation.architectural_concept_ontology_v1 import (
    build_architectural_concept_ontology_v1,
)
from core.knowledge.foundation.architectural_semantic_graph_v1 import (
    build_architectural_semantic_graph_v1,
)

BUILDER_MODULE = (
    "core.knowledge.foundation.architectural_concept_understanding_builder_v1"
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def _case(pattern, claim_id, evidence, grounding, uncertainty=None):
    return {
        "source_pattern": pattern,
        "source_claim_ids": [claim_id],
        "evidence_reference": evidence,
        "grounding_status": grounding,
        "uncertainty": uncertainty or {},
    }


def _access_matches():
    """Mirrors what the real access boundary emits: one match per AREA,
    several patterns collapsed into it."""
    return [
        {
            "knowledge_area": "functional_relationship",
            "source_cases": [
                _case(
                    "sleeping_storage_relation",
                    "au2_claim_001",
                    ["sleeping_element", "wardrobe_or_closet"],
                    ["visible"],
                ),
                _case(
                    "sleeping_sanitary_relation",
                    "au2_claim_002",
                    ["sleeping_element", "bathroom_or_ensuite"],
                    ["visible"],
                    {"unknowns": ["exact service separation is unresolved"]},
                ),
            ],
            "source_patterns": [
                "sleeping_storage_relation",
                "sleeping_sanitary_relation",
            ],
            "evidence_reference": [
                "sleeping_element",
                "wardrobe_or_closet",
                "sleeping_element",
                "bathroom_or_ensuite",
            ],
            "uncertainty": [
                {"unknowns": ["exact service separation is unresolved"]}
            ],
            "status": "bounded_access_match",
        }
    ]


def _access():
    return {
        "contract": SOURCE_CONTRACT,
        "version": SOURCE_VERSION,
        "matches": _access_matches(),
        "source_evidence": [
            {
                "source_pattern": "sleeping_storage_relation",
                "source_claim_ids": ["au2_claim_001"],
                "evidence_reference": ["sleeping_element", "wardrobe_or_closet"],
                "grounding_status": ["visible"],
            },
            {
                "source_pattern": "sleeping_sanitary_relation",
                "source_claim_ids": ["au2_claim_002"],
                "evidence_reference": ["sleeping_element", "bathroom_or_ensuite"],
                "grounding_status": ["visible"],
            },
        ],
        "uncertainty": {"matched_groups": 1},
        "non_claims": {},
        "persistent": False,
        "read_only": True,
    }


def _teaching_session():
    """A real, upstream-valid TeachingSessionV1 used for the live seam test."""
    return {
        "contract": "ArchitecturalTeachingSessionV1",
        "version": "1.0",
        "session_topic": "architectural_teaching_session",
        "teaching_records": [
            {
                "contract": "ArchitecturalTeachingRecordV1",
                "version": "1.0",
                "teaching_topic": "sleeping_space_and_storage_association",
                "source_pattern": "sleeping_storage_relation",
                "human_explanation": (
                    "Storage is associated with a sleeping-space pattern."
                ),
                "evidence_reference": ["sleeping_element", "wardrobe_or_closet"],
                "grounding_status": ["visible"],
                "source_claim_ids": ["au2_claim_001"],
                "uncertainty": {"unknowns": [], "evidence_conflicts": []},
            },
            {
                "contract": "ArchitecturalTeachingRecordV1",
                "version": "1.0",
                "teaching_topic": "sleeping_space_and_sanitary_service_association",
                "source_pattern": "sleeping_sanitary_relation",
                "human_explanation": (
                    "Sanitary service is associated with a sleeping-space pattern."
                ),
                "evidence_reference": ["sleeping_element", "bathroom_or_ensuite"],
                "grounding_status": ["visible"],
                "source_claim_ids": ["au2_claim_002"],
                "uncertainty": {
                    "unknowns": ["exact service separation is unresolved"],
                    "evidence_conflicts": [],
                },
            },
        ],
        "source_patterns": [
            "sleeping_storage_relation",
            "sleeping_sanitary_relation",
        ],
        "evidence_basis": {
            "source_contract": "ArchitecturalTeachingRecordV1",
            "source_version": "1.0",
            "evidence_reference": [
                "sleeping_element",
                "wardrobe_or_closet",
                "bathroom_or_ensuite",
            ],
        },
        "uncertainty": {
            "record_count": 2,
            "records": [
                {"unknowns": []},
                {"unknowns": ["exact service separation is unresolved"]},
            ],
        },
        "non_claims": [],
        "persistent": False,
    }


# --------------------------------------------------------------------------
# Contract / shape
# --------------------------------------------------------------------------


def test_contract_version_and_module_constants():
    assert CONTRACT == "ArchitecturalConceptUnderstandingBuilderV1"
    assert VERSION == "1.0"
    assert SOURCE_CONTRACT == "ArchitecturalFoundationKnowledgeAccessV1"
    assert SOURCE_VERSION == "1.0"
    assert TARGET_CONTRACT == "ArchitecturalConceptUnderstandingV1"

    result = build_architectural_concept_understanding_input_v1(_access())
    assert result["contract"] == SOURCE_CONTRACT == TARGET_CONTRACT.replace(
        "ArchitecturalConceptUnderstandingV1",
        "ArchitecturalFoundationKnowledgeAccessV1",
    )
    assert result["version"] == SOURCE_VERSION
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_source_contract_matches_the_real_access_module():
    """The declared upstream must be the contract the real module emits."""
    import core.knowledge.foundation.architectural_foundation_knowledge_access_v1 as access_module

    assert access_module.CONTRACT == SOURCE_CONTRACT
    assert access_module.VERSION == SOURCE_VERSION


def test_source_contract_matches_the_real_understanding_module():
    """The declared target must be the contract the real boundary accepts."""
    import core.knowledge.foundation.architectural_concept_understanding_v1 as understanding

    assert understanding.SOURCE_CONTRACT == SOURCE_CONTRACT
    assert understanding.SOURCE_VERSION == SOURCE_VERSION


def test_required_output_fields_exist():
    result = build_architectural_concept_understanding_input_v1(_access())
    for key in (
        "contract",
        "version",
        "matches",
        "source_evidence",
        "uncertainty",
        "non_claims",
        "persistent",
        "read_only",
        "source_patterns",
        "source_claim_ids",
        "grounding_status",
        "knowledge_area_groups",
        "produced_by",
    ):
        assert key in result, "missing output field: " + key


def test_is_json_serialisable():
    result = build_architectural_concept_understanding_input_v1(_access())
    json.dumps(result, ensure_ascii=False)


# --------------------------------------------------------------------------
# Input gate
# --------------------------------------------------------------------------


def test_accepts_only_the_declared_source_contract():
    result = build_architectural_concept_understanding_input_v1(_access())
    assert result["contract"] == SOURCE_CONTRACT


def test_non_dict_input_is_rejected_with_type_error():
    for value in (None, [], "access", 42, ()):
        with pytest.raises(TypeError):
            build_architectural_concept_understanding_input_v1(value)


def test_foreign_contracts_are_rejected_with_value_error():
    foreign = (
        "ArchitecturalFoundationKnowledgeSetV1",
        "ArchitecturalKnowledgeCurriculumV1",
        "ArchitecturalConceptUnderstandingV1",
        "ArchitecturalConceptRelationshipV1",
        "ArchitecturalConceptOntologyV1",
        "ArchitecturalSemanticGraphV1",
        "ArchitecturalTeachingSessionV1",
        "ArchitecturalTeachingRecordV1",
        "ArchitecturalSemanticRetrievalResultV1",
        "ArchitecturalIntentCandidateV1",
        "ArchitecturalIntentResolutionV1",
        "ArchitecturalDesignReasoningInputV1",
        "ArchitecturalDesignReasoningResultV1",
        "ArchitecturalKnowledgeAcquisitionBoundaryV1",
    )
    for contract in foreign:
        with pytest.raises(ValueError):
            build_architectural_concept_understanding_input_v1(
                {"contract": contract, "version": "1.0"}
            )


def test_wrong_version_is_rejected():
    for version in ("2.0", "1", "", None):
        with pytest.raises(ValueError):
            build_architectural_concept_understanding_input_v1(
                {"contract": SOURCE_CONTRACT, "version": version}
            )


# --------------------------------------------------------------------------
# The seam: downstream acceptance
# --------------------------------------------------------------------------


def test_produced_envelope_is_accepted_by_downstream_understanding():
    produced = build_architectural_concept_understanding_input_v1(_access())
    understanding = build_architectural_concept_understanding_v1(produced)

    assert understanding["contract"] == "ArchitecturalConceptUnderstandingV1"
    assert understanding["concepts"]


def test_pattern_level_grouping_yields_one_concept_per_pattern():
    """The load-bearing behaviour: one pattern -> one bounded group."""
    access = _access()
    assert len(access["matches"]) == 1  # area-level upstream

    produced = build_architectural_concept_understanding_input_v1(access)
    assert len(produced["matches"]) == 2  # pattern-level downstream
    assert [match["source_patterns"] for match in produced["matches"]] == [
        ["sleeping_storage_relation"],
        ["sleeping_sanitary_relation"],
    ]

    understanding = build_architectural_concept_understanding_v1(produced)
    assert [concept["semantic_label"] for concept in understanding["concepts"]] == [
        "sleeping_space_with_storage_association",
        "sleeping_space_with_sanitary_association",
    ]


def test_downstream_relationship_and_graph_become_non_empty():
    """Before this producer existed the chain could not reach relationships."""
    produced = build_architectural_concept_understanding_input_v1(_access())
    understanding = build_architectural_concept_understanding_v1(produced)
    relationships = build_architectural_concept_relationship_v1(understanding)

    assert relationships["relationships"]
    assert relationships["relationships"][0]["relationship_type"] == (
        "private_sleeping_concept_context"
    )

    ontology = build_architectural_concept_ontology_v1(relationships)
    graph = build_architectural_semantic_graph_v1(ontology)
    assert graph["nodes"]
    assert graph["edges"]
    assert graph["edges"][0]["edge_type"] == "private_sleeping_concept_context"


# --------------------------------------------------------------------------
# Preservation duties
# --------------------------------------------------------------------------


def test_source_patterns_are_preserved_exactly():
    access = _access()
    produced = build_architectural_concept_understanding_input_v1(access)

    expected = ["sleeping_storage_relation", "sleeping_sanitary_relation"]
    assert produced["source_patterns"] == expected
    assert [
        pattern
        for match in produced["matches"]
        for pattern in match["source_patterns"]
    ] == expected

    understanding = build_architectural_concept_understanding_v1(produced)
    assert understanding["source_patterns"] == expected


def test_evidence_references_are_preserved_exactly():
    access = _access()
    produced = build_architectural_concept_understanding_input_v1(access)

    produced_evidence = [
        evidence
        for match in produced["matches"]
        for evidence in match["evidence_reference"]
    ]
    assert produced_evidence == [
        "sleeping_element",
        "wardrobe_or_closet",
        "sleeping_element",
        "bathroom_or_ensuite",
    ]
    assert produced["source_evidence"] == access["source_evidence"]


def test_grounding_status_is_preserved_and_moved_to_contract_surface():
    """Grounding lived only inside source_cases upstream; it must survive."""
    access = _access()
    for match in access["matches"]:
        for case in match["source_cases"]:
            assert case["grounding_status"] == ["visible"]

    produced = build_architectural_concept_understanding_input_v1(access)
    assert produced["grounding_status"] == ["visible"]
    for match in produced["matches"]:
        assert match["grounding_status"] == ["visible"]


def test_grounding_status_is_collected_per_group_not_globally():
    access = _access()
    access["matches"][0]["source_cases"][0]["grounding_status"] = ["inferred"]
    access["matches"][0]["source_cases"][1]["grounding_status"] = ["visible"]

    produced = build_architectural_concept_understanding_input_v1(access)
    assert produced["matches"][0]["grounding_status"] == ["inferred"]
    assert produced["matches"][1]["grounding_status"] == ["visible"]
    assert produced["grounding_status"] == ["inferred", "visible"]


def test_source_claim_ids_are_preserved_per_group():
    access = _access()
    produced = build_architectural_concept_understanding_input_v1(access)

    assert produced["source_claim_ids"] == ["au2_claim_001", "au2_claim_002"]
    assert [
        claim_id
        for match in produced["matches"]
        for claim_id in match["source_claim_ids"]
    ] == ["au2_claim_001", "au2_claim_002"]


def test_uncertainty_is_preserved_verbatim():
    access = _access()
    produced = build_architectural_concept_understanding_input_v1(access)

    assert produced["uncertainty"] == access["uncertainty"]
    # Per-group uncertainty is a verbatim copy of the case uncertainty.
    assert produced["matches"][1]["uncertainty"] == [
        {"unknowns": ["exact service separation is unresolved"]}
    ]


def test_source_cases_are_passthrough_not_rewritten():
    access = _access()
    produced = build_architectural_concept_understanding_input_v1(access)

    for source_match, produced_match in zip(
        access["matches"], produced["matches"]
    ):
        assert produced_match["source_cases"] == [
            case
            for case in source_match["source_cases"]
            if case["source_pattern"] == produced_match["source_patterns"][0]
        ]


# --------------------------------------------------------------------------
# Semantics: grouping only
# --------------------------------------------------------------------------


def test_grouping_preserves_first_seen_order():
    access = _access()
    produced = build_architectural_concept_understanding_input_v1(access)
    assert [match["source_patterns"][0] for match in produced["matches"]] == [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    ]


def test_missing_knowledge_area_is_reported_not_invented():
    access = _access()
    access["matches"][0]["knowledge_area"] = "unmapped_area"

    produced = build_architectural_concept_understanding_input_v1(access)
    assert produced["knowledge_area_groups"][0]["unresolved_knowledge_areas"] == [
        "unmapped_area"
    ]
    assert (
        produced["knowledge_area_groups"][0]["knowledge_area"] == "unmapped_area"
    )


def test_declared_pattern_without_a_case_is_not_fabricated():
    access = _access()
    access["matches"][0]["source_patterns"] = [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
        "declared_but_absent_relation",
    ]

    produced = build_architectural_concept_understanding_input_v1(access)
    absent = [
        match
        for match in produced["matches"]
        if match["source_patterns"] == ["declared_but_absent_relation"]
    ]
    assert len(absent) == 1
    assert absent[0]["source_cases"] == []


# --------------------------------------------------------------------------
# Recovery path (empty access result)
# --------------------------------------------------------------------------


def test_empty_matches_without_session_recovers_nothing():
    access = _access()
    access["matches"] = []
    produced = build_architectural_concept_understanding_input_v1(access)
    assert produced["matches"] == []


def test_empty_matches_recovers_from_the_lineage_teaching_session():
    access = _access()
    access["matches"] = []
    access["source_session"] = _teaching_session()

    produced = build_architectural_concept_understanding_input_v1(access)
    assert produced["produced_by"]["recovered_from"] == "teaching_session"
    assert [match["source_patterns"] for match in produced["matches"]] == [
        ["sleeping_storage_relation"],
        ["sleeping_sanitary_relation"],
    ]
    assert produced["grounding_status"] == ["visible"]

    # And it must still be consumed downstream.
    understanding = build_architectural_concept_understanding_v1(produced)
    assert len(understanding["concepts"]) == 2


def test_recovery_rejects_a_foreign_session_contract():
    access = _access()
    access["matches"] = []
    access["source_session"] = {"contract": "ArchitecturalSemanticGraphV1", "version": "1.0"}
    with pytest.raises(ValueError):
        build_architectural_concept_understanding_input_v1(access)


# --------------------------------------------------------------------------
# Determinism / transience / non-mutation
# --------------------------------------------------------------------------


def test_deterministic_across_calls():
    access = _access()
    first = build_architectural_concept_understanding_input_v1(access)
    second = build_architectural_concept_understanding_input_v1(access)
    assert first == second


def test_input_is_not_mutated():
    access = _access()
    original = copy.deepcopy(access)
    build_architectural_concept_understanding_input_v1(access)
    assert access == original


def test_output_is_disjoint_from_input():
    access = _access()
    produced = build_architectural_concept_understanding_input_v1(access)

    produced["matches"][0]["source_patterns"].append("MUTATED")
    produced["source_evidence"].append("MUTATED")
    produced["matches"][0]["source_cases"][0]["source_claim_ids"].append("MUTATED")

    assert access["matches"][0]["source_patterns"] == [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    ]
    assert len(access["source_evidence"]) == 2
    assert access["matches"][0]["source_cases"][0]["source_claim_ids"] == [
        "au2_claim_001"
    ]


def test_is_transient_and_read_only():
    produced = build_architectural_concept_understanding_input_v1(_access())
    assert produced["persistent"] is False
    assert produced["read_only"] is True


# --------------------------------------------------------------------------
# Boundary discipline
# --------------------------------------------------------------------------


def test_non_claims_are_declared_and_true():
    produced = build_architectural_concept_understanding_input_v1(_access())
    for key in (
        "not_authoritative_ontology",
        "not_permanent_knowledge",
        "not_design_rule",
        "not_recommendation",
        "not_layout",
        "not_geometry",
        "not_design_solution",
        "not_design_reasoning",
        "not_memory",
        "not_learned_model",
    ):
        assert produced["non_claims"][key] is True


def test_no_geometry_layout_or_physical_fields_are_emitted():
    produced = build_architectural_concept_understanding_input_v1(_access())
    for forbidden_key in (
        "geometry",
        "dimensions",
        "coordinates",
        "cad",
        "bim",
        "ifc",
        "layout",
        "placement",
        "walls",
    ):
        assert forbidden_key not in produced


def test_no_forbidden_language_in_authored_payload():
    produced = build_architectural_concept_understanding_input_v1(_access())
    authored = json.dumps(
        {
            "source_patterns": produced["source_patterns"],
            "source_claim_ids": produced["source_claim_ids"],
            "grounding_status": produced["grounding_status"],
            "produced_by": produced["produced_by"],
        },
        ensure_ascii=False,
    ).lower()

    for term in (
        "should",
        "must",
        "required",
        "optimal",
        "best",
        "recommended",
        "design_solution",
        "design_rule",
        "layout_rule",
        "geometry",
        "dimension",
        "cad",
        "bim",
        "ifc",
    ):
        assert term not in authored


def test_forbidden_language_scanner_is_not_vacuous():
    """Negative control: the scanner must actually fire on a bad payload."""
    import core.knowledge.foundation.architectural_concept_understanding_builder_v1 as builder

    with pytest.raises(AssertionError):
        builder._assert_no_forbidden_language(
            {
                "source_patterns": ["the wardrobe should sit adjacent"],
                "source_claim_ids": [],
                "grounding_status": [],
                "produced_by": {},
                "knowledge_area_groups": [],
            }
        )


def test_module_has_no_io_memory_or_network_imports():
    """AST-based: a text grep would false-positive on the module docstring,
    which names Memory and geometry only in order to disclaim them."""
    path = (
        "core/knowledge/foundation/architectural_concept_understanding_builder_v1.py"
    )
    with open(path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])

    for forbidden in (
        "requests",
        "socket",
        "subprocess",
        "sqlite3",
        "os",
        "pathlib",
        "shutil",
        "pickle",
        "shelve",
        "comfy",
        "memory",
    ):
        assert forbidden not in imported


def test_module_does_not_call_persistence_or_generation_helpers():
    path = (
        "core/knowledge/foundation/architectural_concept_understanding_builder_v1.py"
    )
    with open(path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.add(node.func.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)

    for forbidden in (
        "open",
        "write",
        "dump",
        "dumps",
        "save",
        "record",
        "makedirs",
        "mkdir",
        "remove",
        "unlink",
    ):
        assert forbidden not in called


def test_module_declares_no_classes():
    path = (
        "core/knowledge/foundation/architectural_concept_understanding_builder_v1.py"
    )
    with open(path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    assert [node for node in tree.body if isinstance(node, ast.ClassDef)] == []


# --------------------------------------------------------------------------
# The live seam — real upstream, real downstream
# --------------------------------------------------------------------------


def test_structure_spine_runs_end_to_end_on_real_teaching_data():
    """The whole point of this module: Chain B is now drivable from a real
    TeachingSessionV1 through the real upstream boundaries."""
    from core.knowledge.curriculum.architectural_knowledge_curriculum_v1 import (
        build_architectural_knowledge_curriculum_v1,
    )
    from core.knowledge.foundation.architectural_foundation_knowledge_set_v1 import (
        build_architectural_foundation_knowledge_set_v1,
    )
    from core.knowledge.foundation.architectural_foundation_knowledge_access_v1 import (
        access_architectural_foundation_knowledge_v1,
    )
    from core.knowledge.acquisition.architectural_knowledge_acquisition_boundary_v1 import (
        build_architectural_knowledge_acquisition_candidate_v1,
    )

    session = _teaching_session()
    curriculum = build_architectural_knowledge_curriculum_v1(session)
    foundation = build_architectural_foundation_knowledge_set_v1(curriculum)
    access = access_architectural_foundation_knowledge_v1(foundation, {})

    assert access["contract"] == SOURCE_CONTRACT

    produced = build_architectural_concept_understanding_input_v1(access)
    understanding = build_architectural_concept_understanding_v1(produced)
    relationships = build_architectural_concept_relationship_v1(understanding)
    ontology = build_architectural_concept_ontology_v1(relationships)
    graph = build_architectural_semantic_graph_v1(ontology)

    assert len(understanding["concepts"]) == 2
    assert relationships["relationships"]
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1

    candidate = build_architectural_knowledge_acquisition_candidate_v1(
        graph,
        {
            "example_id": "example_understanding_builder_001",
            "domain": "foundation_spatial_semantics",
            "description": "A sleeping space with associated storage.",
            "human_explanation": (
                "Storage sits beside the sleeping space in this example."
            ),
            "related_concepts": [
                "sleeping_space_with_storage_association",
                "sleeping_space_with_sanitary_association",
            ],
            "related_patterns": [
                "sleeping_storage_relation",
                "sleeping_sanitary_relation",
            ],
        },
    )
    assert (
        candidate["contract"]
        == "ArchitecturalKnowledgeAcquisitionBoundaryV1"
    )
