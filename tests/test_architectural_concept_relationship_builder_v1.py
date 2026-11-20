"""Tests for ArchitecturalConceptRelationshipBuilderV1.

This suite covers the dedicated producer boundary that connects
ArchitecturalConceptUnderstandingV1 to ArchitecturalConceptRelationshipV1.
It asserts:
  - the gate accepts ONLY ArchitecturalConceptUnderstandingV1
  - the produced envelope is accepted by the downstream relationship boundary
  - concepts / source_patterns / evidence / uncertainty survive
  - grounding status and source claim IDs are reported honestly (see the
    ABSENCE tests — the understanding boundary drops both fields)
  - the boundary is deterministic, transient, read-only and non-mutating
  - no rules / layout / geometry / Memory / reasoning leakage exists
  - the structure spine runs end-to-end on real teaching data
"""

import ast
import copy
import json

import pytest

from core.knowledge.foundation.architectural_concept_relationship_builder_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    SOURCE_VERSION,
    TARGET_CONTRACT,
    VERSION,
    build_architectural_concept_relationship_input_v1,
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
    "core.knowledge.foundation.architectural_concept_relationship_builder_v1"
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def _concept(label, patterns, evidence=None, uncertainty=None, **extra):
    concept = {
        "concept_type": "functional_association_concept",
        "semantic_label": label,
        "source_patterns": list(patterns),
        "evidence_reference": evidence or [],
        "uncertainty": uncertainty or {},
        "status": "bounded_concept_understanding",
    }
    concept.update(extra)
    return concept


def _understanding_two_sleeping():
    """The canonical private-sleeping pair — the only case that yields the
    multi-concept `private_sleeping_concept_context` relationship."""
    return {
        "contract": SOURCE_CONTRACT,
        "version": SOURCE_VERSION,
        "concepts": [
            _concept(
                "sleeping_space_with_storage_association",
                ["sleeping_storage_relation"],
                ["sleeping_element", "wardrobe_or_closet"],
                {"unknowns": []},
            ),
            _concept(
                "sleeping_space_with_sanitary_association",
                ["sleeping_sanitary_relation"],
                ["sleeping_element", "bathroom_or_ensuite"],
                {"unknowns": ["exact service separation is unresolved"]},
            ),
        ],
        "source_patterns": [
            "sleeping_storage_relation",
            "sleeping_sanitary_relation",
        ],
        "evidence_basis": [
            {"source_pattern": "sleeping_storage_relation"},
            {"source_pattern": "sleeping_sanitary_relation"},
        ],
        "uncertainty": {"matched_groups": 2},
        "non_claims": {},
        "persistent": False,
        "read_only": True,
    }


def _understanding_circulation():
    return {
        "contract": SOURCE_CONTRACT,
        "version": SOURCE_VERSION,
        "concepts": [
            _concept(
                "circulation_related_semantic_context",
                ["circulation_connection_relation"],
                ["corridor_element"],
            )
        ],
        "source_patterns": ["circulation_connection_relation"],
        "evidence_basis": [],
        "uncertainty": {},
        "non_claims": {},
        "persistent": False,
        "read_only": True,
    }


def _teaching_session():
    """A real, upstream-valid TeachingSessionV1 for the live seam test."""
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
            "evidence_reference": ["sleeping_element", "wardrobe_or_closet"],
        },
        "uncertainty": {"record_count": 2, "records": []},
        "non_claims": [],
        "persistent": False,
    }


def _real_understanding():
    """Drive the REAL upstream chain to a genuine understanding envelope."""
    from core.knowledge.curriculum.architectural_knowledge_curriculum_v1 import (
        build_architectural_knowledge_curriculum_v1,
    )
    from core.knowledge.foundation.architectural_foundation_knowledge_set_v1 import (
        build_architectural_foundation_knowledge_set_v1,
    )
    from core.knowledge.foundation.architectural_foundation_knowledge_access_v1 import (
        access_architectural_foundation_knowledge_v1,
    )
    from core.knowledge.foundation.architectural_concept_understanding_builder_v1 import (
        build_architectural_concept_understanding_input_v1,
    )
    from core.knowledge.foundation.architectural_concept_understanding_v1 import (
        build_architectural_concept_understanding_v1,
    )

    session = _teaching_session()
    curriculum = build_architectural_knowledge_curriculum_v1(session)
    foundation = build_architectural_foundation_knowledge_set_v1(curriculum)
    access = access_architectural_foundation_knowledge_v1(foundation, {})
    produced = build_architectural_concept_understanding_input_v1(access)
    return build_architectural_concept_understanding_v1(produced)


# --------------------------------------------------------------------------
# Contract / shape
# --------------------------------------------------------------------------


def test_contract_version_and_module_constants():
    assert CONTRACT == "ArchitecturalConceptRelationshipBuilderV1"
    assert VERSION == "1.0"
    assert SOURCE_CONTRACT == "ArchitecturalConceptUnderstandingV1"
    assert SOURCE_VERSION == "1.0"
    assert TARGET_CONTRACT == "ArchitecturalConceptRelationshipV1"


def test_source_contract_matches_the_real_understanding_module():
    import core.knowledge.foundation.architectural_concept_understanding_v1 as understanding

    assert understanding.CONTRACT == SOURCE_CONTRACT
    assert understanding.VERSION == SOURCE_VERSION


def test_target_contract_matches_the_real_relationship_module():
    import core.knowledge.foundation.architectural_concept_relationship_v1 as relationship

    assert relationship.SOURCE_CONTRACT == SOURCE_CONTRACT
    assert relationship.CONTRACT == TARGET_CONTRACT


def test_output_preserves_the_source_contract_surface():
    """The downstream boundary is name-pinned, so the producer must emit an
    ArchitecturalConceptUnderstandingV1 envelope, not one of its own."""
    produced = build_architectural_concept_relationship_input_v1(
        _understanding_two_sleeping()
    )
    assert produced["contract"] == SOURCE_CONTRACT
    assert produced["version"] == SOURCE_VERSION


def test_required_output_fields_exist():
    produced = build_architectural_concept_relationship_input_v1(
        _understanding_two_sleeping()
    )
    for key in (
        "contract",
        "version",
        "concepts",
        "semantic_groups",
        "source_patterns",
        "evidence_basis",
        "uncertainty",
        "grounding_status",
        "source_claim_ids",
        "grounding_status_present",
        "source_claim_ids_present",
        "non_claims",
        "persistent",
        "read_only",
        "produced_by",
    ):
        assert key in produced, "missing output field: " + key


def test_is_json_serialisable():
    produced = build_architectural_concept_relationship_input_v1(
        _understanding_two_sleeping()
    )
    json.dumps(produced, ensure_ascii=False)


# --------------------------------------------------------------------------
# Input gate
# --------------------------------------------------------------------------


def test_non_dict_input_is_rejected_with_type_error():
    for value in (None, [], "understanding", 42, ()):
        with pytest.raises(TypeError):
            build_architectural_concept_relationship_input_v1(value)


def test_foreign_contracts_are_rejected_with_value_error():
    foreign = (
        "ArchitecturalFoundationKnowledgeAccessV1",
        "ArchitecturalFoundationKnowledgeSetV1",
        "ArchitecturalKnowledgeCurriculumV1",
        "ArchitecturalConceptUnderstandingBuilderV1",
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
            build_architectural_concept_relationship_input_v1(
                {"contract": contract, "version": "1.0"}
            )


def test_wrong_version_is_rejected():
    for version in ("2.0", "1", "", None):
        with pytest.raises(ValueError):
            build_architectural_concept_relationship_input_v1(
                {"contract": SOURCE_CONTRACT, "version": version}
            )


# --------------------------------------------------------------------------
# The seam: downstream acceptance
# --------------------------------------------------------------------------


def test_produced_envelope_is_accepted_by_downstream_relationship():
    produced = build_architectural_concept_relationship_input_v1(
        _understanding_two_sleeping()
    )
    relationship = build_architectural_concept_relationship_v1(produced)
    assert relationship["contract"] == TARGET_CONTRACT
    assert relationship["relationships"]


def test_private_sleeping_pair_yields_the_expected_relationship():
    produced = build_architectural_concept_relationship_input_v1(
        _understanding_two_sleeping()
    )
    relationship = build_architectural_concept_relationship_v1(produced)

    assert [rel["relationship_type"] for rel in relationship["relationships"]] == [
        "private_sleeping_concept_context"
    ]
    assert relationship["relationships"][0]["related_concepts"] == [
        "sleeping_space_with_storage_association",
        "sleeping_space_with_sanitary_association",
    ]
    assert relationship["relationships"][0]["status"] == (
        "bounded_concept_relationship"
    )


def test_circulation_yields_the_movement_relationship():
    produced = build_architectural_concept_relationship_input_v1(
        _understanding_circulation()
    )
    relationship = build_architectural_concept_relationship_v1(produced)
    assert [rel["relationship_type"] for rel in relationship["relationships"]] == [
        "movement_related_concept_context"
    ]


def test_opening_yields_the_boundary_connection_relationship():
    understanding = {
        "contract": SOURCE_CONTRACT,
        "version": SOURCE_VERSION,
        "concepts": [
            _concept(
                "opening_related_semantic_context",
                ["opening_space_relation"],
                ["opening_element"],
            )
        ],
        "source_patterns": ["opening_space_relation"],
        "evidence_basis": [],
        "uncertainty": {},
        "non_claims": {},
        "persistent": False,
        "read_only": True,
    }
    produced = build_architectural_concept_relationship_input_v1(understanding)
    relationship = build_architectural_concept_relationship_v1(produced)
    assert [rel["relationship_type"] for rel in relationship["relationships"]] == [
        "boundary_connection_concept_context"
    ]


def test_unknown_labels_produce_no_relationship_and_no_error():
    understanding = {
        "contract": SOURCE_CONTRACT,
        "version": SOURCE_VERSION,
        "concepts": [_concept("mystery_relation", ["mystery_pattern"])],
        "source_patterns": ["mystery_pattern"],
        "evidence_basis": [],
        "uncertainty": {},
        "non_claims": {},
        "persistent": False,
        "read_only": True,
    }
    produced = build_architectural_concept_relationship_input_v1(understanding)
    relationship = build_architectural_concept_relationship_v1(produced)
    assert relationship["relationships"] == []


def test_empty_concepts_is_handled_without_error():
    understanding = {
        "contract": SOURCE_CONTRACT,
        "version": SOURCE_VERSION,
        "concepts": [],
        "source_patterns": [],
        "evidence_basis": [],
        "uncertainty": {},
        "non_claims": {},
        "persistent": False,
        "read_only": True,
    }
    produced = build_architectural_concept_relationship_input_v1(understanding)
    assert produced["semantic_groups"] == []
    relationship = build_architectural_concept_relationship_v1(produced)
    assert relationship["relationships"] == []


def test_downstream_ontology_and_graph_stay_non_empty():
    produced = build_architectural_concept_relationship_input_v1(
        _understanding_two_sleeping()
    )
    relationship = build_architectural_concept_relationship_v1(produced)
    ontology = build_architectural_concept_ontology_v1(relationship)
    graph = build_architectural_semantic_graph_v1(ontology)

    assert len(graph["nodes"]) == 2
    assert [edge["edge_type"] for edge in graph["edges"]] == [
        "private_sleeping_concept_context"
    ]


# --------------------------------------------------------------------------
# Preservation duties
# --------------------------------------------------------------------------


def test_concepts_are_preserved_verbatim():
    understanding = _understanding_two_sleeping()
    produced = build_architectural_concept_relationship_input_v1(understanding)
    assert produced["concepts"] == understanding["concepts"]


def test_source_patterns_are_preserved_across_concepts():
    understanding = _understanding_two_sleeping()
    produced = build_architectural_concept_relationship_input_v1(understanding)
    assert produced["source_patterns"] == [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    ]
    assert produced["source_patterns"] == understanding["source_patterns"]


def test_evidence_references_are_preserved_per_concept_and_per_group():
    understanding = _understanding_two_sleeping()
    produced = build_architectural_concept_relationship_input_v1(understanding)

    assert produced["concepts"][0]["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
    ]
    group = produced["semantic_groups"][0]
    assert group["evidence_reference"] == ["sleeping_element", "wardrobe_or_closet"]


def test_uncertainty_is_preserved_verbatim():
    understanding = _understanding_two_sleeping()
    produced = build_architectural_concept_relationship_input_v1(understanding)

    assert produced["uncertainty"] == understanding["uncertainty"]
    assert produced["semantic_groups"][1]["uncertainty"] == [
        {"unknowns": ["exact service separation is unresolved"]}
    ]


def test_evidence_basis_is_passed_through():
    understanding = _understanding_two_sleeping()
    produced = build_architectural_concept_relationship_input_v1(understanding)
    assert produced["evidence_basis"] == understanding["evidence_basis"]


# --------------------------------------------------------------------------
# Grounding status / source claim IDs — HONEST ABSENCE
# --------------------------------------------------------------------------


def test_grounding_status_absent_is_reported_as_none_not_empty():
    """ArchitecturalConceptUnderstandingV1 does NOT copy grounding_status onto
    its concepts. The producer must not fabricate it, and must not present an
    empty list as though the value were genuinely empty."""
    understanding = _understanding_two_sleeping()
    for concept in understanding["concepts"]:
        assert "grounding_status" not in concept

    produced = build_architectural_concept_relationship_input_v1(understanding)
    entry = produced["semantic_groups"][0]["concept_provenance"][0]
    assert entry["grounding_status"] is None
    assert produced["grounding_status_present"] is False


def test_source_claim_ids_absent_is_reported_as_none_not_empty():
    understanding = _understanding_two_sleeping()
    for concept in understanding["concepts"]:
        assert "source_claim_ids" not in concept

    produced = build_architectural_concept_relationship_input_v1(understanding)
    entry = produced["semantic_groups"][0]["concept_provenance"][0]
    assert entry["source_claim_ids"] is None
    assert produced["source_claim_ids_present"] is False


def test_grounding_status_is_preserved_when_the_concept_carries_it():
    understanding = _understanding_two_sleeping()
    understanding["concepts"][0]["grounding_status"] = ["visible"]
    understanding["concepts"][1]["grounding_status"] = ["inferred"]

    produced = build_architectural_concept_relationship_input_v1(understanding)
    assert produced["grounding_status"] == ["visible", "inferred"]
    assert produced["grounding_status_present"] is True
    entries = produced["semantic_groups"][0]["concept_provenance"]
    assert entries[0]["grounding_status"] == ["visible"]


def test_source_claim_ids_are_preserved_when_the_concept_carries_them():
    understanding = _understanding_two_sleeping()
    understanding["concepts"][0]["source_claim_ids"] = ["au2_claim_001"]
    understanding["concepts"][1]["source_claim_ids"] = ["au2_claim_002"]

    produced = build_architectural_concept_relationship_input_v1(understanding)
    assert produced["source_claim_ids"] == ["au2_claim_001", "au2_claim_002"]
    assert produced["source_claim_ids_present"] is True


def test_provenance_is_recovered_when_concepts_carry_source_cases():
    """The only recovery path available without violating the input gate."""
    understanding = _understanding_two_sleeping()
    understanding["concepts"][0]["source_cases"] = [
        {
            "source_pattern": "sleeping_storage_relation",
            "source_claim_ids": ["au2_claim_001"],
            "grounding_status": ["visible"],
        }
    ]

    produced = build_architectural_concept_relationship_input_v1(understanding)
    assert produced["grounding_status"] == ["visible"]
    assert produced["source_claim_ids"] == ["au2_claim_001"]
    assert produced["grounding_status_present"] is True


def test_provenance_is_keyed_by_semantic_label():
    produced = build_architectural_concept_relationship_input_v1(
        _understanding_two_sleeping()
    )
    labels = [
        entry["semantic_label"]
        for group in produced["semantic_groups"]
        for entry in group["concept_provenance"]
    ]
    assert labels == [
        "sleeping_space_with_storage_association",
        "sleeping_space_with_sanitary_association",
    ]


# --------------------------------------------------------------------------
# Grouping semantics
# --------------------------------------------------------------------------


def test_grouping_is_one_group_per_relationship_context():
    produced = build_architectural_concept_relationship_input_v1(
        _understanding_two_sleeping()
    )
    assert [
        group["relationship_context"] for group in produced["semantic_groups"]
    ] == [
        "sleeping_space_with_storage_association",
        "sleeping_space_with_sanitary_association",
    ]


def test_grouping_preserves_first_seen_order():
    understanding = _understanding_two_sleeping()
    understanding["concepts"] = list(reversed(understanding["concepts"]))
    produced = build_architectural_concept_relationship_input_v1(understanding)
    assert [
        group["relationship_context"] for group in produced["semantic_groups"]
    ] == [
        "sleeping_space_with_sanitary_association",
        "sleeping_space_with_storage_association",
    ]


def test_concept_without_a_declared_context_is_reported_not_dropped():
    understanding = _understanding_two_sleeping()
    understanding["concepts"].append(_concept("unmapped_label", ["some_pattern"]))

    produced = build_architectural_concept_relationship_input_v1(understanding)
    unresolved = [
        group
        for group in produced["semantic_groups"]
        if group["relationship_context"] is None
    ]
    assert len(unresolved) == 1
    assert unresolved[0]["related_concepts"] == ["unmapped_label"]


def test_group_related_concepts_are_deduplicated():
    understanding = {
        "contract": SOURCE_CONTRACT,
        "version": SOURCE_VERSION,
        "concepts": [
            _concept(
                "sleeping_space_with_storage_association",
                ["sleeping_storage_relation"],
            ),
            _concept(
                "sleeping_space_with_storage_association",
                ["sleeping_storage_relation"],
            ),
        ],
        "source_patterns": ["sleeping_storage_relation"],
        "evidence_basis": [],
        "uncertainty": {},
        "non_claims": {},
        "persistent": False,
        "read_only": True,
    }
    produced = build_architectural_concept_relationship_input_v1(understanding)
    assert produced["semantic_groups"][0]["related_concepts"] == [
        "sleeping_space_with_storage_association"
    ]


def test_grouping_unit_and_rule_ownership_are_stamped():
    produced = build_architectural_concept_relationship_input_v1(
        _understanding_two_sleeping()
    )
    assert produced["produced_by"]["grouping_unit"] == "relationship_context"
    assert produced["produced_by"]["grouping_only"] is True
    assert produced["produced_by"]["relationship_rules_owned_by"] == TARGET_CONTRACT


def test_producer_does_not_emit_relationship_types_itself():
    """Relationship truth must stay in the downstream boundary, not be
    duplicated here where it could silently drift."""
    produced = build_architectural_concept_relationship_input_v1(
        _understanding_two_sleeping()
    )
    serialized = json.dumps(produced, ensure_ascii=False)
    assert "private_sleeping_concept_context" not in serialized
    assert "movement_related_concept_context" not in serialized
    assert "boundary_connection_concept_context" not in serialized
    assert "relationship_type" not in produced


# --------------------------------------------------------------------------
# Determinism / transience / non-mutation
# --------------------------------------------------------------------------


def test_deterministic_across_calls():
    understanding = _understanding_two_sleeping()
    first = build_architectural_concept_relationship_input_v1(understanding)
    second = build_architectural_concept_relationship_input_v1(understanding)
    assert first == second


def test_input_is_not_mutated():
    understanding = _understanding_two_sleeping()
    original = copy.deepcopy(understanding)
    build_architectural_concept_relationship_input_v1(understanding)
    assert understanding == original


def test_output_is_disjoint_from_input():
    understanding = _understanding_two_sleeping()
    produced = build_architectural_concept_relationship_input_v1(understanding)

    produced["concepts"][0]["source_patterns"].append("MUTATED")
    produced["semantic_groups"][0]["evidence_reference"].append("MUTATED")
    produced["source_patterns"].append("MUTATED")

    assert understanding["concepts"][0]["source_patterns"] == [
        "sleeping_storage_relation"
    ]
    assert understanding["concepts"][0]["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
    ]
    assert understanding["source_patterns"] == [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    ]


def test_is_transient_and_read_only():
    produced = build_architectural_concept_relationship_input_v1(
        _understanding_two_sleeping()
    )
    assert produced["persistent"] is False
    assert produced["read_only"] is True


# --------------------------------------------------------------------------
# Boundary discipline
# --------------------------------------------------------------------------


def test_non_claims_are_declared_and_true():
    produced = build_architectural_concept_relationship_input_v1(
        _understanding_two_sleeping()
    )
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
    produced = build_architectural_concept_relationship_input_v1(
        _understanding_two_sleeping()
    )
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
    produced = build_architectural_concept_relationship_input_v1(
        _understanding_two_sleeping()
    )
    authored = json.dumps(
        {
            "source_patterns": produced["source_patterns"],
            "grounding_status": produced["grounding_status"],
            "source_claim_ids": produced["source_claim_ids"],
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
    import core.knowledge.foundation.architectural_concept_relationship_builder_v1 as builder

    with pytest.raises(AssertionError):
        builder._assert_no_forbidden_language(
            {
                "source_patterns": ["the wardrobe should sit adjacent"],
                "grounding_status": [],
                "source_claim_ids": [],
                "produced_by": {},
                "semantic_groups": [],
            }
        )


def test_module_has_no_io_memory_or_network_imports():
    """AST-based: a text grep would false-positive on the module docstring,
    which names Memory and geometry only in order to disclaim them."""
    path = (
        "core/knowledge/foundation/architectural_concept_relationship_builder_v1.py"
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
        "core/knowledge/foundation/architectural_concept_relationship_builder_v1.py"
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
        "core/knowledge/foundation/architectural_concept_relationship_builder_v1.py"
    )
    with open(path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    assert [node for node in tree.body if isinstance(node, ast.ClassDef)] == []


# --------------------------------------------------------------------------
# The live seam — real upstream, real downstream
# --------------------------------------------------------------------------


def test_structure_spine_runs_end_to_end_on_real_teaching_data():
    """Drive the REAL upstream chain and carry it through to acquisition."""
    from core.knowledge.acquisition.architectural_knowledge_acquisition_boundary_v1 import (
        build_architectural_knowledge_acquisition_candidate_v1,
    )

    understanding = _real_understanding()
    assert len(understanding["concepts"]) == 2

    produced = build_architectural_concept_relationship_input_v1(understanding)
    relationship = build_architectural_concept_relationship_v1(produced)
    ontology = build_architectural_concept_ontology_v1(relationship)
    graph = build_architectural_semantic_graph_v1(ontology)

    assert [rel["relationship_type"] for rel in relationship["relationships"]] == [
        "private_sleeping_concept_context"
    ]
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1

    candidate = build_architectural_knowledge_acquisition_candidate_v1(
        graph,
        {
            "example_id": "example_relationship_builder_001",
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
    assert candidate["contract"] == "ArchitecturalKnowledgeAcquisitionBoundaryV1"


def test_real_chain_reports_grounding_absence_honestly():
    """On the real chain the understanding boundary has already dropped
    grounding and claim IDs — the producer must say so, not invent values."""
    produced = build_architectural_concept_relationship_input_v1(
        _real_understanding()
    )
    assert produced["grounding_status_present"] is False
    assert produced["source_claim_ids_present"] is False
    assert produced["grounding_status"] == []
    assert produced["source_claim_ids"] == []
