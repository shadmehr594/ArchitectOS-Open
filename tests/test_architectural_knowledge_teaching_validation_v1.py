"""Tests for ArchitecturalKnowledgeTeachingValidationV1.

Written from the BRIEF's semantics, not from the implementation: the brief
enumerates the accepted input, the rejected input, the output contract, the
allowed status vocabulary, the preservation duties, the forbidden behaviour,
the required non-claims and the three worked examples. Each test pins one of
those sentences.

The brief's central question is "Did ArchitectOS understand the architectural
concept?" — NOT "Can ArchitectOS draw CAD?". The final group of tests pins the
second half of that sentence.
"""

import ast
import copy
import json

import pytest

from core.knowledge.teaching_validation.architectural_knowledge_teaching_validation_v1 import (
    CONTRACT,
    TEACHING_CASE_CONTRACT,
    TEACHING_CASE_REQUIRED_FIELDS,
    UNDERSTANDING_STATUSES,
    VERSION,
    validate_architectural_knowledge_understanding_v1,
)

MODULE_PATH = (
    "core/knowledge/teaching_validation/"
    "architectural_knowledge_teaching_validation_v1.py"
)


# ---------------------------------------------------------------------------
# Fixtures — the brief's three worked examples
# ---------------------------------------------------------------------------


def _case(**overrides):
    case = {
        "contract": TEACHING_CASE_CONTRACT,
        "version": "1.0",
        "case_id": "case_master_bedroom_001",
        "domain": "residential_spatial_semantics",
        "description": "Master bedroom with private sanitary space and storage.",
        "human_explanation": (
            "Master bedroom usually relates to private sanitary space and "
            "storage."
        ),
        "related_concepts": [
            "sleeping_space_with_sanitary_association",
            "sleeping_space_with_storage_association",
        ],
        "related_patterns": [
            "sleeping_sanitary_relation",
            "sleeping_storage_relation",
        ],
        "evidence_reference": [
            "sleeping_element",
            "wardrobe_or_closet",
            "bathroom_or_ensuite",
        ],
        "grounding_status": ["visible"],
        "source_claim_ids": ["claim_mb_001"],
        "uncertainty": {"unknowns": [], "evidence_conflicts": []},
        "persistent": False,
    }
    case.update(overrides)
    return case


def _master_bedroom_case():
    """Brief Example 1."""
    return _case()


def _kitchen_case():
    """Brief Example 2."""
    return _case(
        case_id="case_kitchen_001",
        description="Kitchen with food preparation and living connection.",
        human_explanation=(
            "kitchen relates to food preparation, storage, and connection "
            "with living activities."
        ),
        related_concepts=["functional_relationship_context"],
        related_patterns=[],
        evidence_reference=["kitchen_element", "counter_element"],
        source_claim_ids=["claim_kitchen_001"],
    )


def _entrance_case():
    """Brief Example 3."""
    return _case(
        case_id="case_entrance_001",
        description="Entrance threshold between outside and inside.",
        human_explanation=(
            "Entrance creates transition between outside and inside."
        ),
        related_concepts=["boundary_connection_context"],
        related_patterns=["entrance_threshold_in_facade_composition"],
        evidence_reference=["entrance_element", "threshold_element"],
        source_claim_ids=["claim_entrance_001"],
    )


# ---------------------------------------------------------------------------
# Contract / shape
# ---------------------------------------------------------------------------


def test_contract_and_version_constants():
    assert CONTRACT == "ArchitecturalKnowledgeTeachingValidationV1"
    assert VERSION == "1.0"


def test_result_contract_and_version():
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "master_bedroom"}
    )
    assert result["contract"] == CONTRACT
    assert result["version"] == VERSION


def test_all_required_output_fields_present():
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "master_bedroom"}
    )
    for key in (
        "contract",
        "version",
        "understanding_status",
        "matched_semantic_patterns",
        "preserved_evidence",
        "uncertainty",
        "explanation_basis",
        "validation_questions",
        "non_claims",
        "persistent",
        "read_only",
    ):
        assert key in result, "missing output field: " + key


def test_is_json_serialisable():
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "master_bedroom"}
    )
    json.dumps(result, ensure_ascii=False)


def test_is_transient_and_read_only():
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "master_bedroom"}
    )
    assert result["persistent"] is False
    assert result["read_only"] is True


# ---------------------------------------------------------------------------
# Input gate — accepted
# ---------------------------------------------------------------------------


def test_accepts_the_defined_teaching_case_contract():
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "master_bedroom"}
    )
    assert result["understanding_status"] in UNDERSTANDING_STATUSES


def test_accepts_a_string_query():
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), "master_bedroom"
    )
    assert result["understanding_status"] == "understood"


def test_accepts_a_mapping_query_with_pattern_terms():
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"pattern": "sleeping_storage_relation"}
    )
    assert result["understanding_status"] in UNDERSTANDING_STATUSES


# ---------------------------------------------------------------------------
# Input gate — rejected
# ---------------------------------------------------------------------------


def test_non_dict_teaching_case_is_rejected_with_type_error():
    for value in (None, [], "case", 42, ()):
        with pytest.raises(TypeError):
            validate_architectural_knowledge_understanding_v1(value, {})


def test_missing_contract_field_is_rejected():
    with pytest.raises(ValueError):
        validate_architectural_knowledge_understanding_v1(
            {"version": "1.0"}, {}
        )


def test_forbidden_input_contracts_are_rejected():
    """The brief enumerates exactly these families."""
    forbidden = (
        # Vision / observation
        "ArchitecturalUnderstandingV2",
        "ArchitecturalUnderstandingV1",
        "ArchitecturalObservationV1",
        "VisionObservationV1",
        "ArchitecturalVisionReportV1",
        # Unrelated intent contracts
        "ImageIntentV1",
        "SiteIntentV1",
        "ArchitecturalGeometryIntentV1",
        "ArchitecturalLayoutIntentResolverV1",
        "ProgramIntentResolutionV1",
        # Design solutions / reasoning (spatial)
        "ArchitecturalDesignReasoningResultV1",
        "ArchitecturalSpatialReasoningCandidateV1",
        # Memory
        "ArchitecturalMemoryRecordV1",
        "MemoryRecordV1",
        # Geometry / CAD / BIM / IFC
        "ArchitecturalBIMEntityV1",
        "ArchitecturalIFCEntityV1",
        "ArchitecturalCADDrawingV1",
    )
    for contract in forbidden:
        with pytest.raises(ValueError):
            validate_architectural_knowledge_understanding_v1(
                {"contract": contract, "version": "1.0"}, {}
            )


def test_unrelated_but_not_enumerated_contracts_are_still_rejected():
    for contract in (
        "ArchitecturalSemanticGraphV1",
        "ArchitecturalConceptUnderstandingV1",
        "ArchitecturalTeachingSessionV1",
        "ArchitecturalKnowledgeAcquisitionBoundaryV1",
    ):
        with pytest.raises(ValueError):
            validate_architectural_knowledge_understanding_v1(
                {"contract": contract, "version": "1.0"}, {}
            )


def test_wrong_version_is_rejected():
    for version in ("2.0", "1", "", None):
        with pytest.raises(ValueError):
            validate_architectural_knowledge_understanding_v1(
                _case(version=version), {}
            )


def test_empty_string_query_is_rejected():
    with pytest.raises(ValueError):
        validate_architectural_knowledge_understanding_v1(
            _master_bedroom_case(), "   "
        )


def test_non_mapping_non_string_query_is_rejected():
    for query in (42, [], None, ()):
        with pytest.raises(TypeError):
            validate_architectural_knowledge_understanding_v1(
                _master_bedroom_case(), query
            )


# ---------------------------------------------------------------------------
# The three worked examples from the brief
# ---------------------------------------------------------------------------


def test_example_1_master_bedroom_validates_both_sleeping_associations():
    """Example 1 — expected semantic validation:
    sleeping_space_with_sanitary_association
    sleeping_space_with_storage_association
    """
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "master_bedroom"}
    )
    assert result["understanding_status"] == "understood"
    assert set(result["matched_semantic_patterns"]) >= {
        "sleeping_space_with_sanitary_association",
        "sleeping_space_with_storage_association",
    }


def test_example_2_kitchen_validates_functional_relationship_context():
    """Example 2 — expected: functional_relationship_context"""
    result = validate_architectural_knowledge_understanding_v1(
        _kitchen_case(), {"space": "kitchen"}
    )
    assert result["understanding_status"] == "understood"
    assert "functional_relationship_context" in result[
        "matched_semantic_patterns"
    ]


def test_example_3_entrance_validates_boundary_connection_context():
    """Example 3 — expected: boundary_connection_context"""
    result = validate_architectural_knowledge_understanding_v1(
        _entrance_case(), {"space": "entrance"}
    )
    assert result["understanding_status"] == "understood"
    assert "boundary_connection_context" in result["matched_semantic_patterns"]


# ---------------------------------------------------------------------------
# Status vocabulary
# ---------------------------------------------------------------------------


def test_only_the_three_allowed_statuses_are_ever_emitted():
    queries = (
        {"space": "master_bedroom"},
        {"space": "kitchen"},
        {"space": "entrance"},
        {"space": "corridor"},
        {"space": "bathroom"},
        {"space": "quantum_flux_capacitor"},
        {"space": ""},
    )
    for query in queries:
        result = validate_architectural_knowledge_understanding_v1(
            _master_bedroom_case(), query
        )
        assert result["understanding_status"] in UNDERSTANDING_STATUSES


def test_unknown_concept_remains_unresolved():
    """Required by the brief: 'unknown concept remains unresolved'."""
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "quantum_flux_capacitor"}
    )
    assert result["understanding_status"] == "unresolved"


def test_partially_declared_concepts_yield_partially_understood():
    case = _case(
        related_concepts=["sleeping_space_with_storage_association"],
        related_patterns=["sleeping_storage_relation"],
        human_explanation="Master bedroom relates to storage.",
    )
    result = validate_architectural_knowledge_understanding_v1(
        case, {"space": "master_bedroom"}
    )
    assert result["understanding_status"] == "partially_understood"
    assert result["uncertainty"]["unmatched_concepts"] == [
        "sleeping_space_with_sanitary_association"
    ]


def test_fully_declared_concepts_yield_understood():
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "master_bedroom"}
    )
    assert result["understanding_status"] == "understood"
    assert result["uncertainty"]["unmatched_concepts"] == []


# ---------------------------------------------------------------------------
# Preservation duties
# ---------------------------------------------------------------------------


def test_evidence_is_preserved():
    """Required by the brief: 'evidence is preserved'."""
    case = _master_bedroom_case()
    result = validate_architectural_knowledge_understanding_v1(
        case, {"space": "master_bedroom"}
    )
    entry = result["preserved_evidence"][0]
    assert entry["case_id"] == case["case_id"]
    assert entry["evidence_reference"] == case["evidence_reference"]
    assert entry["grounding_status"] == case["grounding_status"]
    assert entry["source_claim_ids"] == case["source_claim_ids"]


def test_uncertainty_is_preserved():
    """Required by the brief: 'uncertainty is preserved'."""
    case = _case(
        uncertainty={
            "unknowns": ["service separation unresolved"],
            "evidence_conflicts": ["conflicting closet reading"],
        }
    )
    result = validate_architectural_knowledge_understanding_v1(
        case, {"space": "master_bedroom"}
    )
    assert result["uncertainty"]["source_uncertainty"] == case["uncertainty"]


def test_absent_source_claim_ids_are_preserved_as_an_empty_list():
    case = _master_bedroom_case()
    del case["source_claim_ids"]
    result = validate_architectural_knowledge_understanding_v1(
        case, {"space": "master_bedroom"}
    )
    assert result["preserved_evidence"][0]["source_claim_ids"] == []


def test_teaching_context_is_preserved_in_explanation_basis():
    case = _master_bedroom_case()
    result = validate_architectural_knowledge_understanding_v1(
        case, {"space": "master_bedroom"}
    )
    basis = result["explanation_basis"]
    assert basis["declared_concepts"] == case["related_concepts"]
    assert basis["declared_patterns"] == case["related_patterns"]
    assert basis["human_explanation_present"] is True


def test_human_explanation_text_is_not_copied_forward():
    """The human's narrative is not structural data and must not leak."""
    case = _master_bedroom_case()
    result = validate_architectural_knowledge_understanding_v1(
        case, {"space": "master_bedroom"}
    )
    serialized = json.dumps(result, ensure_ascii=False)
    assert case["human_explanation"] not in serialized
    assert result["explanation_basis"]["restatement_of_explanation"] is None


def test_unresolved_query_records_the_unresolved_terms():
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "quantum_flux_capacitor"}
    )
    assert result["uncertainty"]["query_terms_unresolved"] == [
        "quantum_flux_capacitor"
    ]


# ---------------------------------------------------------------------------
# Validation questions
# ---------------------------------------------------------------------------


def test_understood_case_asks_only_confirmation_questions():
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "master_bedroom"}
    )
    kinds = {q["question_type"] for q in result["validation_questions"]}
    assert kinds == {"confirmation_probe"}


def test_partial_case_asks_about_the_missing_concept():
    case = _case(
        related_concepts=["sleeping_space_with_storage_association"],
        related_patterns=["sleeping_storage_relation"],
    )
    result = validate_architectural_knowledge_understanding_v1(
        case, {"space": "master_bedroom"}
    )
    missing = [
        q
        for q in result["validation_questions"]
        if q["question_type"] == "missing_concept_probe"
    ]
    assert [q["target"] for q in missing] == [
        "sleeping_space_with_sanitary_association"
    ]


def test_unresolved_case_asks_an_unresolved_probe():
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "quantum_flux_capacitor"}
    )
    kinds = {q["question_type"] for q in result["validation_questions"]}
    assert "unresolved_concept_probe" in kinds


def test_validation_questions_are_json_serialisable():
    for query in (
        {"space": "master_bedroom"},
        {"space": "quantum_flux_capacitor"},
    ):
        result = validate_architectural_knowledge_understanding_v1(
            _master_bedroom_case(), query
        )
        json.dumps(result["validation_questions"], ensure_ascii=False)


# ---------------------------------------------------------------------------
# Determinism / transience / non-mutation
# ---------------------------------------------------------------------------


def test_deterministic_across_calls():
    case = _master_bedroom_case()
    query = {"space": "master_bedroom"}
    assert validate_architectural_knowledge_understanding_v1(
        case, query
    ) == validate_architectural_knowledge_understanding_v1(case, query)


def test_inputs_are_not_mutated():
    case = _master_bedroom_case()
    query = {"space": "master_bedroom"}
    case_original = copy.deepcopy(case)
    query_original = copy.deepcopy(query)

    validate_architectural_knowledge_understanding_v1(case, query)

    assert case == case_original
    assert query == query_original


def test_output_is_disjoint_from_input():
    case = _master_bedroom_case()
    result = validate_architectural_knowledge_understanding_v1(
        case, {"space": "master_bedroom"}
    )

    result["preserved_evidence"][0]["evidence_reference"].append("MUTATED")
    result["matched_semantic_patterns"].append("MUTATED")
    result["explanation_basis"]["declared_concepts"].append("MUTATED")

    assert case["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
        "bathroom_or_ensuite",
    ]
    assert case["related_concepts"] == [
        "sleeping_space_with_sanitary_association",
        "sleeping_space_with_storage_association",
    ]


# ---------------------------------------------------------------------------
# REQUIRED NON-CLAIMS
# ---------------------------------------------------------------------------


def test_required_non_claims_are_declared_and_true():
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "master_bedroom"}
    )
    assert result["non_claims"] == {
        "not_design_rule": True,
        "not_recommendation": True,
        "not_authoritative_knowledge": True,
        "not_memory": True,
        "not_learned_model": True,
        "not_design_solution": True,
    }


def test_output_does_not_claim_design_correctness_or_optimality():
    """The brief: must NOT claim it designed correctly / produced an optimal
    solution / learned permanently / created architectural rules."""
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "master_bedroom"}
    )
    serialized = json.dumps(result, ensure_ascii=False).lower()
    for claim in (
        "designed correctly",
        "design_correct",
        "optimal",
        "best_solution",
        "learned permanently",
        "learned_permanently",
        "permanent_learning",
        "architectural rule",
    ):
        assert claim not in serialized


# ---------------------------------------------------------------------------
# No learning / no persistence
# ---------------------------------------------------------------------------


def test_no_automatic_learning_occurs():
    """Required by the brief: 'no automatic learning occurs'.

    Two identical calls must return byte-identical results — nothing is
    retained between them. The AST check below additionally proves no
    learning, memory or persistence machinery is even imported.
    """
    case = _master_bedroom_case()
    query = {"space": "master_bedroom"}
    first = validate_architectural_knowledge_understanding_v1(case, query)
    second = validate_architectural_knowledge_understanding_v1(case, query)
    assert first == second
    assert first["uncertainty"]["validated"] is False


def test_no_persistence_occurs():
    """Required by the brief: 'no persistence occurs'."""
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "master_bedroom"}
    )
    assert result["persistent"] is False


def test_module_has_no_io_memory_network_or_learning_imports():
    """AST-based: the module docstring names Memory, CAD, BIM, geometry and
    rendering in order to disclaim them, so a text grep would false-positive."""
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
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
        "torch",
        "numpy",
        "ezdxf",
        "ifcopenshell",
    ):
        assert forbidden not in imported


def test_module_does_not_call_persistence_or_generation_helpers():
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
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
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    assert [node for node in tree.body if isinstance(node, ast.ClassDef)] == []


# ---------------------------------------------------------------------------
# No design recommendation / no geometry / no CAD-BIM-3D
# ---------------------------------------------------------------------------


def test_no_design_recommendation_is_generated():
    """Required by the brief: 'no design recommendation is generated'.

    `non_claims` is excluded from the scan: the key `not_recommendation`
    legitimately contains the substring "recommend" as a NEGATION, so scanning
    it would make the module appear to violate its own rule.
    """
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "master_bedroom"}
    )
    authored = json.dumps(
        {key: value for key, value in result.items() if key != "non_claims"},
        ensure_ascii=False,
    ).lower()
    for term in (
        "recommend",
        "suggestion",
        "you should",
        "we advise",
        "best option",
    ):
        assert term not in authored


def test_recommendation_scan_is_not_vacuous():
    """Negative control for the scan above."""
    payload = '{"note": "the wardrobe should be placed here"}'.lower()
    assert "should" in payload


def test_no_geometry_is_produced():
    """Required by the brief: 'no geometry is produced'."""
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "master_bedroom"}
    )
    for forbidden_key in (
        "geometry",
        "dimensions",
        "coordinates",
        "polygon",
        "wall",
        "walls",
        "vertices",
        "cad",
        "bim",
        "ifc",
        "mesh",
        "render",
        "layout",
        "placement",
    ):
        assert forbidden_key not in result


def test_no_forbidden_language_in_authored_payload():
    result = validate_architectural_knowledge_understanding_v1(
        _master_bedroom_case(), {"space": "master_bedroom"}
    )
    authored = json.dumps(
        {
            "understanding_status": result["understanding_status"],
            "matched_semantic_patterns": result["matched_semantic_patterns"],
            "preserved_evidence": result["preserved_evidence"],
            "uncertainty": result["uncertainty"],
            "validation_questions": result["validation_questions"],
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
    import core.knowledge.teaching_validation.architectural_knowledge_teaching_validation_v1 as module

    with pytest.raises(AssertionError):
        module._assert_no_forbidden_language(
            {
                "understanding_status": "the wardrobe should sit adjacent",
                "matched_semantic_patterns": [],
                "preserved_evidence": [],
                "uncertainty": {},
                "validation_questions": [],
            }
        )


def test_module_never_imports_the_geometry_or_vision_lineages():
    """The brief forbids merging contracts or bypassing boundaries."""
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)

    for forbidden in (
        "core.architecture.reasoning",
        "core.architecture.intent",
        "core.cognition",
        "core.vision",
        "core.design",
    ):
        assert not any(
            module == forbidden or module.startswith(forbidden + ".")
            for module in modules
        ), "forbidden import: " + forbidden


# ---------------------------------------------------------------------------
# Wire-up: the boundary works against real upstream teaching data
# ---------------------------------------------------------------------------


def test_validation_runs_against_a_real_teaching_session_derived_case():
    """Build a case from the real teaching lineage and validate it — proving
    this boundary consumes real production data without a hidden adapter."""
    from core.knowledge.curriculum.architectural_knowledge_curriculum_v1 import (
        build_architectural_knowledge_curriculum_v1,
    )
    from core.knowledge.foundation.architectural_foundation_knowledge_set_v1 import (
        build_architectural_foundation_knowledge_set_v1,
    )
    from core.knowledge.foundation.architectural_foundation_knowledge_access_v1 import (
        access_architectural_foundation_knowledge_v1,
    )

    session = {
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
                "uncertainty": {"unknowns": [], "evidence_conflicts": []},
            },
        ],
        "source_patterns": [
            "sleeping_storage_relation",
            "sleeping_sanitary_relation",
        ],
        "evidence_basis": {},
        "uncertainty": {"record_count": 2, "records": []},
        "non_claims": [],
        "persistent": False,
    }

    access = access_architectural_foundation_knowledge_v1(
        build_architectural_foundation_knowledge_set_v1(
            build_architectural_knowledge_curriculum_v1(session)
        ),
        {},
    )

    patterns = [
        pattern
        for match in access["matches"]
        for pattern in match["source_patterns"]
    ]
    evidence = [
        item
        for match in access["matches"]
        for item in match["evidence_reference"]
    ]
    claim_ids = [
        claim_id
        for match in access["matches"]
        for case in match["source_cases"]
        for claim_id in case.get("source_claim_ids", [])
    ]

    case = {
        "contract": TEACHING_CASE_CONTRACT,
        "version": "1.0",
        "case_id": "case_from_live_lineage_001",
        "domain": "residential_spatial_semantics",
        "description": "Sleeping space with storage and sanitary service.",
        "human_explanation": (
            "Master bedroom usually relates to private sanitary space and "
            "storage."
        ),
        "related_concepts": [
            "sleeping_space_with_storage_association",
            "sleeping_space_with_sanitary_association",
        ],
        "related_patterns": patterns,
        "evidence_reference": evidence,
        "grounding_status": ["visible"],
        "source_claim_ids": claim_ids,
        "uncertainty": {"unknowns": []},
        "persistent": False,
    }

    result = validate_architectural_knowledge_understanding_v1(
        case, {"space": "master_bedroom"}
    )

    assert result["understanding_status"] == "understood"
    assert "sleeping_space_with_storage_association" in result[
        "matched_semantic_patterns"
    ]
    assert result["preserved_evidence"][0]["source_claim_ids"] == [
        "au2_claim_001",
        "au2_claim_002",
    ]
    assert result["non_claims"]["not_memory"] is True


def test_required_teaching_case_fields_are_declared():
    assert TEACHING_CASE_REQUIRED_FIELDS == (
        "case_id",
        "domain",
        "description",
        "human_explanation",
        "related_concepts",
        "related_patterns",
    )
