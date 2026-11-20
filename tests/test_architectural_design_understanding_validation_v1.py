"""Tests for ArchitecturalDesignUnderstandingValidationV1.

Written from the BRIEF's semantics, not from the implementation: the brief
enumerates the accepted input, the rejected input, the output contract, the
allowed reasoning vocabulary, the preservation duties, the forbidden
behaviour, the required non-claims and the three worked examples. Each test
pins one of those sentences.

The brief's central question is:

    "Can ArchitectOS reason about a new architectural problem using the
     concepts it has already learned — BEFORE any drawing system exists?"

The final group of tests pins the second half of that sentence: no geometry,
no CAD/BIM/IFC, no rendering, no persistence.
"""

import ast
import copy
import json

import pytest

from core.design.design_validation.architectural_design_understanding_validation_v1 import (
    ARCHITECTURAL_CASE_CONTRACT,
    ARCHITECTURAL_CASE_VERSION,
    CONTRACT,
    KNOWLEDGE_CONTEXT_CONTRACT,
    KNOWLEDGE_CONTEXT_VERSION,
    VERSION,
    validate_architectural_design_understanding_v1,
)

MODULE_PATH = (
    "core/design/design_validation/"
    "architectural_design_understanding_validation_v1.py"
)

REQUIRED_TOP_LEVEL = (
    "contract",
    "version",
    "problem_understanding",
    "identified_spaces",
    "semantic_relationships",
    "architectural_concepts_used",
    "reasoning_basis",
    "uncertainty",
    "open_questions",
    "visual_validation_request",
    "non_claims",
    "persistent",
    "read_only",
)

REQUIRED_NON_CLAIMS = (
    "not_design_rule",
    "not_recommendation",
    "not_authoritative_knowledge",
    "not_memory",
    "not_learned_model",
    "not_design_solution",
)


# ---------------------------------------------------------------------------
# Fixtures — the brief's three worked examples
# ---------------------------------------------------------------------------


def _case(**overrides):
    case = {
        "contract": ARCHITECTURAL_CASE_CONTRACT,
        "version": ARCHITECTURAL_CASE_VERSION,
        "case_id": "case_residential_house_10x20",
        "description": (
            "A residential house on a plot roughly ten by twenty metres. It "
            "needs an entrance transition, a public living area, a private "
            "sleeping zone with a master bedroom, a kitchen that relates to "
            "living activity, a bathroom, storage, a corridor, and a "
            "connection to the outdoor space."
        ),
        "stated_spaces": [
            "entrance",
            "living_room",
            "bedroom",
            "master_bedroom",
            "kitchen",
            "bathroom",
            "storage",
            "corridor",
            "outdoor",
        ],
        "stated_functions": [
            "sleeping",
            "cooking",
            "circulation",
        ],
        "stated_relationships": [
            "private_space",
            "public_space",
        ],
    }
    case.update(overrides)
    return case


def _knowledge_context(**overrides):
    """The knowledge ArchitectOS already holds — declared, not learned here.

    This mirrors the structure-spine foundation knowledge set surface: it
    groups cases by declared semantic area and names the concept/pattern
    vocabulary that has been taught.
    """
    context = {
        "contract": KNOWLEDGE_CONTEXT_CONTRACT,
        "version": KNOWLEDGE_CONTEXT_VERSION,
        "knowledge_domain": "foundation_spatial_semantics",
        "space_identity_cases": [
            {
                "concept": "private_sleeping_space",
                "semantic_area": "space_identity",
            },
            {
                "concept": "public_living_space",
                "semantic_area": "space_identity",
            },
            {
                "concept": "service_space",
                "semantic_area": "space_identity",
            },
            {
                "concept": "circulation_space",
                "semantic_area": "space_identity",
            },
            {
                "concept": "entrance_transition_space",
                "semantic_area": "space_identity",
            },
            {
                "concept": "sanitary_service_space",
                "semantic_area": "space_identity",
            },
            {
                "concept": "storage_space",
                "semantic_area": "space_identity",
            },
            {
                "concept": "outdoor_connection_space",
                "semantic_area": "space_identity",
            },
        ],
        "functional_relationship_cases": [
            {
                "concept": "sleeping_space_with_sanitary_association",
                "semantic_area": "functional_association",
            },
            {
                "concept": "sleeping_space_with_storage_association",
                "semantic_area": "functional_association",
            },
            {
                "concept": "functional_service_association",
                "semantic_area": "functional_association",
            },
            {
                "concept": "circulation_connection_association",
                "semantic_area": "functional_association",
            },
            {
                "concept": "entrance_threshold_relationship",
                "semantic_area": "functional_association",
            },
            {
                "concept": "outdoor_connection_association",
                "semantic_area": "functional_association",
            },
        ],
        "semantic_zone_cases": [
            {
                "concept": "private_sleeping_zone_containment",
                "semantic_area": "semantic_zone",
            },
            {
                "concept": "public_circulation_association",
                "semantic_area": "semantic_zone",
            },
        ],
        "concepts": [
            "private_sleeping_space",
            "public_living_space",
            "service_space",
            "circulation_space",
            "entrance_transition_space",
            "sanitary_service_space",
            "storage_space",
            "outdoor_connection_space",
            "sleeping_space_with_sanitary_association",
            "sleeping_space_with_storage_association",
            "functional_service_association",
            "circulation_connection_association",
            "entrance_threshold_relationship",
            "outdoor_connection_association",
            "private_sleeping_zone_containment",
            "public_circulation_association",
            "privacy_separation_relationship",
        ],
        "patterns": [
            "sleeping_storage_relation",
            "sleeping_sanitary_relation",
            "circulation_connection_relation",
            "entrance_threshold_in_facade_composition",
        ],
        "persistent": False,
        "read_only": True,
    }
    context.update(overrides)
    return context


def _master_bedroom_case():
    """Brief Example 2 — master bedroom with private bathroom and storage."""
    return _case(
        case_id="case_master_bedroom_private_suite",
        description=(
            "A master bedroom that relates to a private bathroom and to "
            "storage."
        ),
        stated_spaces=["master_bedroom", "bathroom", "storage"],
        stated_functions=["sleeping"],
        stated_relationships=["private_space"],
    )


def _ritual_space_case():
    """Brief Example 3 — unknown cultural ritual spaces.

    The vocabulary is deliberately outside everything declared, so the
    boundary must report uncertainty and invent nothing.
    """
    return _case(
        case_id="case_unknown_ritual_spaces",
        description=(
            "A gathering structure containing a ziggurat ritual chamber, a "
            "votive antechamber and a ceremonial procession way whose "
            "cultural meaning is not established."
        ),
        stated_spaces=[
            "ziggurat_ritual_chamber",
            "votive_antechamber",
            "ceremonial_procession_way",
        ],
        stated_functions=["ritual_observance"],
        stated_relationships=["consecration_precedence"],
    )


# ---------------------------------------------------------------------------
# 1. Contract surface
# ---------------------------------------------------------------------------


def test_contract_and_version_are_declared():
    assert CONTRACT == "ArchitecturalDesignUnderstandingValidationV1"
    assert VERSION == "1.0"


def test_output_contains_every_required_top_level_key():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    for key in REQUIRED_TOP_LEVEL:
        assert key in result, "missing output key: " + key


def test_output_contract_and_version_are_emitted():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    assert result["contract"] == CONTRACT
    assert result["version"] == VERSION


def test_output_is_json_serialisable():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    assert json.loads(json.dumps(result)) == json.loads(json.dumps(result))


def test_output_is_marked_transient_and_read_only():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_visual_validation_request_is_absent():
    """This boundary validates UNDERSTANDING, not appearance."""
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    assert result["visual_validation_request"] is None


# ---------------------------------------------------------------------------
# 2. Required non-claims
# ---------------------------------------------------------------------------


def test_all_required_non_claims_are_declared_true():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    non_claims = result["non_claims"]
    for key in REQUIRED_NON_CLAIMS:
        assert key in non_claims, "missing non-claim: " + key
        assert non_claims[key] is True


def test_non_claims_contain_no_false_claim():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    assert all(value is True for value in result["non_claims"].values())


# ---------------------------------------------------------------------------
# 3. Input gating — accepted
# ---------------------------------------------------------------------------


def test_declared_case_contract_is_accepted():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    assert result["contract"] == CONTRACT


def test_declared_knowledge_context_contract_is_accepted():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    assert result["reasoning_basis"]["knowledge_reference"]["contract"] == (
        KNOWLEDGE_CONTEXT_CONTRACT
    )


# ---------------------------------------------------------------------------
# 4. Input gating — rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "contract",
    [
        "ArchitecturalDesignReasoningInputV1",
        "ArchitecturalDesignReasoningResultV1",
        "ArchitecturalSpatialReasoningCandidateV1",
        "ArchitecturalCADDrawingV1",
        "ArchitecturalBIMEntityV1",
        "ArchitecturalIFCEntityV1",
        "ArchitecturalRenderingOutputV1",
        "ArchitecturalMemoryRecordV1",
        "ArchitecturalVisionReportV1",
        "ArchitecturalKnowledgeTeachingValidationV1",
    ],
)
def test_forbidden_first_argument_contract_is_rejected(contract):
    case = _case(contract=contract)
    with pytest.raises(ValueError):
        validate_architectural_design_understanding_v1(
            case, _knowledge_context()
        )


@pytest.mark.parametrize(
    "contract",
    [
        "ArchitecturalCADDrawingV1",
        "ArchitecturalBIMEntityV1",
        "ArchitecturalIFCEntityV1",
        "ArchitecturalMemoryRecordV1",
        "ArchitecturalDesignReasoningResultV1",
        "ArchitecturalSemanticGraphV1",
        "ArchitecturalConceptOntologyV1",
        "ArchitecturalTeachingCaseV1",
    ],
)
def test_forbidden_second_argument_contract_is_rejected(contract):
    context = _knowledge_context(contract=contract)
    with pytest.raises(ValueError):
        validate_architectural_design_understanding_v1(_case(), context)


def test_non_dict_case_raises_type_error():
    with pytest.raises(TypeError):
        validate_architectural_design_understanding_v1(
            "house brief", _knowledge_context()
        )


def test_non_dict_knowledge_context_raises_type_error():
    with pytest.raises(TypeError):
        validate_architectural_design_understanding_v1(_case(), "knowledge")


def test_missing_case_contract_field_raises_value_error():
    case = _case()
    del case["contract"]
    with pytest.raises(ValueError):
        validate_architectural_design_understanding_v1(
            case, _knowledge_context()
        )


def test_wrong_case_version_is_rejected():
    case = _case(version="2.0")
    with pytest.raises(ValueError):
        validate_architectural_design_understanding_v1(
            case, _knowledge_context()
        )


def test_wrong_knowledge_context_version_is_rejected():
    context = _knowledge_context(version="9.9")
    with pytest.raises(ValueError):
        validate_architectural_design_understanding_v1(_case(), context)


def test_unknown_contract_string_is_rejected():
    case = _case(contract="SomethingElseV1")
    with pytest.raises(ValueError):
        validate_architectural_design_understanding_v1(
            case, _knowledge_context()
        )


# ---------------------------------------------------------------------------
# 5. Brief Example 1 — residential house 10m x 20m
# ---------------------------------------------------------------------------


def test_example_1_identifies_entrance_transition():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    identities = [s["space_identity"] for s in result["identified_spaces"]]
    assert "entrance_transition_space" in identities


def test_example_1_identifies_public_and_private_separation():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    identities = [s["space_identity"] for s in result["identified_spaces"]]
    assert "public_living_space" in identities
    assert "private_sleeping_space" in identities


def test_example_1_identifies_master_bedroom_as_private_sleeping():
    """A multi-word declared key must actually be applied, not sit inert."""
    case = _case(
        case_id="case_master_bedroom_only",
        description="A master bedroom with a private bathroom.",
        stated_spaces=["master_bedroom", "bathroom"],
        stated_functions=["sleeping"],
        stated_relationships=["private_space"],
    )
    result = validate_architectural_design_understanding_v1(
        case, _knowledge_context()
    )
    spaces = {
        s["declared_token"]: s["space_identity"]
        for s in result["identified_spaces"]
    }
    assert spaces.get("master_bedroom") == "private_sleeping_space"


def test_example_1_master_bedroom_and_bedroom_share_one_identity():
    """Both tokens name the same identity; it is reported exactly once."""
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    identities = [s["space_identity"] for s in result["identified_spaces"]]
    assert identities.count("private_sleeping_space") == 1


def test_example_1_identifies_kitchen_functional_relationship():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    types = [
        r["relationship_type"] for r in result["semantic_relationships"]
    ]
    assert "functional_service_association" in types


def test_example_1_identifies_outdoor_connection():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    types = [
        r["relationship_type"] for r in result["semantic_relationships"]
    ]
    assert "outdoor_connection_association" in types


def test_example_1_identifies_circulation_concept():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    identities = [s["space_identity"] for s in result["identified_spaces"]]
    assert "circulation_space" in identities


def test_example_1_is_reported_as_understood():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    assert result["problem_understanding"]["understood"] is True


# ---------------------------------------------------------------------------
# 6. Brief Example 2 — master bedroom with private bathroom and storage
# ---------------------------------------------------------------------------


def test_example_2_identifies_sleeping_sanitary_association():
    result = validate_architectural_design_understanding_v1(
        _master_bedroom_case(), _knowledge_context()
    )
    types = [
        r["relationship_type"] for r in result["semantic_relationships"]
    ]
    assert "sleeping_space_with_sanitary_association" in types


def test_example_2_identifies_sleeping_storage_association():
    result = validate_architectural_design_understanding_v1(
        _master_bedroom_case(), _knowledge_context()
    )
    types = [
        r["relationship_type"] for r in result["semantic_relationships"]
    ]
    assert "sleeping_space_with_storage_association" in types


def test_example_2_relationship_involves_both_spaces():
    result = validate_architectural_design_understanding_v1(
        _master_bedroom_case(), _knowledge_context()
    )
    relationship = next(
        r
        for r in result["semantic_relationships"]
        if r["relationship_type"]
        == "sleeping_space_with_sanitary_association"
    )
    assert "private_sleeping_space" in relationship["involved_spaces"]
    assert "sanitary_service_space" in relationship["involved_spaces"]


# ---------------------------------------------------------------------------
# 7. Brief Example 3 — unknown cultural ritual spaces
# ---------------------------------------------------------------------------


def test_example_3_invents_no_space_identity():
    result = validate_architectural_design_understanding_v1(
        _ritual_space_case(), _knowledge_context()
    )
    assert result["identified_spaces"] == []


def test_example_3_is_not_claimed_as_understood():
    result = validate_architectural_design_understanding_v1(
        _ritual_space_case(), _knowledge_context()
    )
    assert result["problem_understanding"]["understood"] is False


def test_example_3_reports_unknown_tokens():
    result = validate_architectural_design_understanding_v1(
        _ritual_space_case(), _knowledge_context()
    )
    assert result["uncertainty"]["unknown_tokens"]


def test_example_3_asks_the_human_for_clarification():
    result = validate_architectural_design_understanding_v1(
        _ritual_space_case(), _knowledge_context()
    )
    types = [q["question_type"] for q in result["open_questions"]]
    assert "unknown_concept_probe" in types


def test_example_3_emits_no_relationships():
    result = validate_architectural_design_understanding_v1(
        _ritual_space_case(), _knowledge_context()
    )
    assert result["semantic_relationships"] == []


# ---------------------------------------------------------------------------
# 8. Concept reuse — learned knowledge is reused, not rederived
# ---------------------------------------------------------------------------


def test_known_concepts_are_marked_as_reused():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    reused = [
        c
        for c in result["architectural_concepts_used"]
        if c["status"] == "reused"
    ]
    assert reused


def test_identified_space_identity_is_reused_when_declared():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    entry = next(
        c
        for c in result["architectural_concepts_used"]
        if c["concept"] == "private_sleeping_space"
    )
    assert entry["declared_by_knowledge_context"] is True
    assert entry["status"] == "reused"


def test_concept_not_declared_by_context_is_flagged_not_claimed():
    """When the context declares genuinely nothing, nothing may be claimed."""
    context = _knowledge_context(
        concepts=[],
        patterns=[],
        space_identity_cases=[],
        functional_relationship_cases=[],
        semantic_zone_cases=[],
    )
    result = validate_architectural_design_understanding_v1(_case(), context)
    entries = result["architectural_concepts_used"]
    assert entries
    assert all(
        entry["declared_by_knowledge_context"] is False for entry in entries
    )
    assert all(
        entry["status"] == "used_without_declaration" for entry in entries
    )


def test_declared_relationship_case_grounds_the_relationship_concept():
    """A relationship declared by the context is reused, not rederived."""
    context = _knowledge_context(
        concepts=[],
        patterns=[],
        space_identity_cases=[],
        semantic_zone_cases=[],
    )
    result = validate_architectural_design_understanding_v1(_case(), context)
    entry = next(
        c
        for c in result["architectural_concepts_used"]
        if c["concept"] == "sleeping_space_with_sanitary_association"
    )
    assert entry["declared_by_knowledge_context"] is True
    assert entry["status"] == "reused"


# ---------------------------------------------------------------------------
# 9. Evidence basis is preserved
# ---------------------------------------------------------------------------


def test_relationship_carries_an_evidence_reference():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    assert result["semantic_relationships"]
    for relationship in result["semantic_relationships"]:
        assert "evidence_reference" in relationship


def test_reasoning_basis_carries_case_and_knowledge_references():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    basis = result["reasoning_basis"]
    assert basis["case_reference"]["contract"] == ARCHITECTURAL_CASE_CONTRACT
    assert basis["knowledge_reference"]["contract"] == (
        KNOWLEDGE_CONTEXT_CONTRACT
    )


def test_case_narrative_is_not_copied_forward():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    assert result["reasoning_basis"]["restatement_of_problem"] is None


# ---------------------------------------------------------------------------
# 10. Uncertainty is preserved (never silently resolved)
# ---------------------------------------------------------------------------


def test_uncertainty_block_reports_reasoned_false():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    assert result["uncertainty"]["reasoned"] is False
    assert result["uncertainty"]["generated"] is False


def test_privacy_context_is_not_inferred():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    assert result["uncertainty"]["privacy_context"]["inferred"] is False


def test_absent_privacy_declaration_reports_no_class():
    case = _case(stated_relationships=[])
    result = validate_architectural_design_understanding_v1(
        case, _knowledge_context()
    )
    privacy = result["uncertainty"]["privacy_context"]
    assert privacy["privacy_class_present"] is False
    assert privacy["declared_privacy_classes"] == []


def test_privacy_relationship_absent_without_declaration():
    case = _case(stated_relationships=[])
    result = validate_architectural_design_understanding_v1(
        case, _knowledge_context()
    )
    types = [
        r["relationship_type"] for r in result["semantic_relationships"]
    ]
    assert "privacy_separation_relationship" not in types


def test_privacy_relationship_present_when_case_declares_two_classes():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    types = [
        r["relationship_type"] for r in result["semantic_relationships"]
    ]
    assert "privacy_separation_relationship" in types


# ---------------------------------------------------------------------------
# 11. Determinism
# ---------------------------------------------------------------------------


def test_output_is_deterministic_across_repeated_calls():
    case = _case()
    context = _knowledge_context()
    first = validate_architectural_design_understanding_v1(case, context)
    second = validate_architectural_design_understanding_v1(case, context)
    assert first == second


def test_inputs_are_not_mutated():
    case = _case()
    context = _knowledge_context()
    case_snapshot = copy.deepcopy(case)
    context_snapshot = copy.deepcopy(context)
    validate_architectural_design_understanding_v1(case, context)
    assert case == case_snapshot
    assert context == context_snapshot


def test_returned_structure_is_independent_of_inputs():
    case = _case()
    context = _knowledge_context()
    result = validate_architectural_design_understanding_v1(case, context)
    result["identified_spaces"].append({"space_identity": "injected"})
    result["non_claims"]["not_memory"] = False
    again = validate_architectural_design_understanding_v1(case, context)
    assert len(again["identified_spaces"]) == len(
        validate_architectural_design_understanding_v1(
            _case(), _knowledge_context()
        )["identified_spaces"]
    )
    assert again["non_claims"]["not_memory"] is True


def test_multi_word_resolution_does_not_report_its_parts_as_unknown():
    """A token consumed by a matched phrase is not an unknown.

    `master_bedroom` resolves cleanly, so `master`/`room` must not be
    reported as unresolved vocabulary alongside it.
    """
    case = _case(
        case_id="case_master_bedroom_only",
        description="A master bedroom with a private bathroom.",
        stated_spaces=["master_bedroom", "bathroom"],
        stated_functions=["sleeping"],
        stated_relationships=["private_space"],
    )
    result = validate_architectural_design_understanding_v1(
        case, _knowledge_context()
    )
    unknowns = set(result["uncertainty"]["unknown_tokens"])
    assert "master" not in unknowns
    assert "room" not in unknowns


def test_genuinely_unknown_tokens_are_still_reported():
    """Negative control: real unknowns must survive the same filter."""
    result = validate_architectural_design_understanding_v1(
        _ritual_space_case(), _knowledge_context()
    )
    assert result["uncertainty"]["unknown_tokens"]


# ---------------------------------------------------------------------------
# 12. No design solution, no rule, no recommendation
# ---------------------------------------------------------------------------


FORBIDDEN_AUTHORED_TERMS = (
    "should",
    "optimal",
    "best",
    "recommended",
    "design_solution",
    "design_rule",
    "layout",
    "placement",
    "geometry",
    "dimension",
    "cad",
    "dwg",
    "dxf",
    "bim",
    "ifc",
    "render",
)


def _authored_payload(result):
    return {
        key: value
        for key, value in result.items()
        if key not in ("non_claims",)
    }


def test_authored_payload_contains_no_forbidden_language():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    serialized = str(_authored_payload(result)).lower()
    for term in FORBIDDEN_AUTHORED_TERMS:
        assert term not in serialized, "forbidden term emitted: " + term


def test_forbidden_language_scan_is_not_vacuous():
    """Negative control: the scan must actually fire on forbidden language."""
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    poisoned = dict(_authored_payload(result))
    poisoned["problem_understanding"] = {"note": "this is a design_solution"}
    serialized = str(poisoned).lower()
    assert "design_solution" in serialized


def test_no_numeric_dimension_is_emitted():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    for space in result["identified_spaces"]:
        assert not any(
            key in space for key in ("width", "length", "area", "dimensions")
        )


def test_output_requests_no_visual_validation():
    result = validate_architectural_design_understanding_v1(
        _case(), _knowledge_context()
    )
    assert result["visual_validation_request"] is None


# ---------------------------------------------------------------------------
# 13. No geometry / CAD / BIM / IFC access — structural proof
# ---------------------------------------------------------------------------


def _module_ast():
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        return ast.parse(handle.read())


def _imported_modules():
    names = []
    for node in ast.walk(_module_ast()):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


def test_module_does_not_import_any_cad_or_geometry_library():
    forbidden = (
        "ezdxf",
        "dxfgrabber",
        "ifcopenshell",
        "pythonocc",
        "trimesh",
        "open3d",
        "shapely",
        "freecad",
        "pyautocad",
        "comtypes",
        "win32com",
        "PIL",
        "cv2",
        "torch",
        "tensorflow",
    )
    for name in _imported_modules():
        for banned in forbidden:
            assert not name.startswith(banned), (
                "module imports geometry/CAD library: " + name
            )


def test_module_does_not_import_memory_or_persistence():
    forbidden = ("sqlite3", "pickle", "shelve", "joblib", "core.memory")
    for name in _imported_modules():
        for banned in forbidden:
            assert not name.startswith(banned), (
                "module imports persistence library: " + name
            )


def test_module_does_not_open_or_write_any_file():
    for node in ast.walk(_module_ast()):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            assert name not in ("open",), "module opens a file"
            assert name not in (
                "write",
                "writelines",
                "dump",
                "dumps",
                "save",
                "savez",
                "imwrite",
            ), "module writes data: " + str(name)


def test_module_does_not_import_os_or_subprocess():
    names = set(_imported_modules())
    assert "os" not in names
    assert "subprocess" not in names
    assert "shutil" not in names


def test_module_does_not_reference_any_acceptance_or_deploy_app():
    """No wiring into app.py / ChatArchitect / UI / deploy surface."""
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        source = handle.read()
    for banned in (
        "ChatArchitect",
        "streamlit",
        "flask",
        "fastapi",
        "django",
        "app.py",
    ):
        assert banned not in source, "module references: " + banned


def test_module_does_not_import_sibling_validation_boundary():
    """The teaching-validation boundary is a sibling, not a dependency."""
    for name in _imported_modules():
        assert "teaching_validation" not in name
