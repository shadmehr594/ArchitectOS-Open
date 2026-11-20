"""Tests for ArchitecturalUnderstandingFoundationV1.

Written from the BRIEF's semantics, not from the implementation.

The brief's central demand for this stage is that ArchitectOS must extract
ARCHITECTURAL MEANING from a human example:

    Master Bedroom is NOT  `bedroom + bathroom + closet`.
    Master Bedroom IS      privacy, personal territory, the relation between
                           sleeping and storage, the relation between sleeping
                           and service, user experience, movement and access,
                           and its difference from public space.

The brief also forbids:

    fixed rules · design formulas · definitive patterns ·
    the claim that there is always one correct way

Later the brief tightens this further: the declared concept vocabulary must be
EXTENSIBLE and is explicitly NOT the source of truth. It is a starting semantic
index only. Concepts are grounded in the human example — its architectural
evidence, reasoning and context — never selected from a fixed list. Each case
may:

    * introduce a NEW concept the index does not know;
    * enrich an existing concept;
    * add new evidence for an existing concept;
    * show a concept does NOT apply in a particular context.

The final group of tests pins those duties, together with the standing
requirement that uncertainty, alternative interpretations and context
dependencies are preserved and that multiple valid solutions remain possible.
"""

import ast
import copy
import json

import pytest

from core.knowledge.understanding_foundation.architectural_understanding_foundation_v1 import (
    CASE_OPERATIONS,
    CONTRACT,
    INTERPRETATION_STATUSES,
    TEACHING_EXAMPLE_CONTRACT,
    TEACHING_EXAMPLE_VERSION,
    VERSION,
    _CONCEPT_INDEX,
    understand_architectural_example_v1,
)

MODULE_PATH = (
    "core/knowledge/understanding_foundation/"
    "architectural_understanding_foundation_v1.py"
)

REQUIRED_TOP_LEVEL = (
    "contract",
    "version",
    "concept_understanding",
    "observed_elements",
    "spatial_relations",
    "concept_rationale_and_context",
    "uncertainty",
    "rationale_basis",
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
    "not_fixed_truth",
    "not_single_correct_way",
)


# ---------------------------------------------------------------------------
# Fixtures — the brief's first experimental lesson: Master Bedroom
# ---------------------------------------------------------------------------


def _meaningful_example(**overrides):
    """Master Bedroom taught as CONCEPT, not as components.

    Observation and MEANING are deliberately separated: `observed_elements`
    and `description` carry what is seen; `human_explanation` / `reason` /
    `context` carry what the human says it MEANS. Only the latter can ground a
    concept.
    """
    example = {
        "contract": TEACHING_EXAMPLE_CONTRACT,
        "version": TEACHING_EXAMPLE_VERSION,
        "example_id": "ex_master_bedroom_meaning_01",
        "teaching_topic": "master_bedroom",
        "description": (
            "A room at the end of a corridor with a bed, a bathroom and a closet."
        ),
        "observed_elements": [
            "a bed",
            "a bathroom",
            "a closet",
            "a corridor",
            "a door",
        ],
        "human_explanation": (
            "The master bedroom is private: it is withdrawn from the shared "
            "life of the house so the occupant can retreat and recover. It is "
            "personal territory that the occupant controls, where their own "
            "order holds. It is quiet and restful. It is separated from guests "
            "and is unlike the public living room. It is reached through a "
            "corridor, and washing and dressing happen in sequence without "
            "leaving."
        ),
        "reason": "The household needs somewhere to withdraw to.",
        "context": "A family home in which guests are received.",
    }
    example.update(overrides)
    return example


def _component_only_example(**overrides):
    """The ANTI-example the brief explicitly rejects.

    It names the physical pieces and explains no meaning at all.
    """
    example = {
        "contract": TEACHING_EXAMPLE_CONTRACT,
        "version": TEACHING_EXAMPLE_VERSION,
        "example_id": "ex_master_bedroom_components_01",
        "teaching_topic": "master_bedroom",
        "description": "A bedroom, a bathroom and a closet.",
        "human_explanation": (
            "A master bedroom consists of a bedroom, a bathroom and a closet."
        ),
    }
    example.update(overrides)
    return example


def _concepts_by_name(result):
    return {
        c["concept"]: c
        for c in result["concept_understanding"]["extracted_concepts"]
    }


# ---------------------------------------------------------------------------
# 1. Contract surface
# ---------------------------------------------------------------------------


def test_contract_and_version_are_declared():
    assert CONTRACT == "ArchitecturalUnderstandingFoundationV1"
    assert VERSION == "1.0"


def test_output_contains_every_required_top_level_key():
    result = understand_architectural_example_v1(_meaningful_example())
    for key in REQUIRED_TOP_LEVEL:
        assert key in result, "missing output key: " + key


def test_output_is_json_serialisable():
    result = understand_architectural_example_v1(_meaningful_example())
    assert json.loads(json.dumps(result))


def test_output_is_transient_and_read_only():
    result = understand_architectural_example_v1(_meaningful_example())
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_interpretation_status_vocabulary_is_declared():
    assert set(INTERPRETATION_STATUSES) == {
        "supported",
        "weakly_supported",
        "unresolved",
    }


def test_case_operation_vocabulary_covers_the_four_operations():
    """The brief allows exactly four things a case may do with a concept."""
    assert set(CASE_OPERATIONS) >= {
        "introduced",
        "enriched",
        "evidence_added",
        "not_applicable",
    }


# ---------------------------------------------------------------------------
# 2. Required non-claims
# ---------------------------------------------------------------------------


def test_all_required_non_claims_are_true():
    result = understand_architectural_example_v1(_meaningful_example())
    for key in REQUIRED_NON_CLAIMS:
        assert key in result["non_claims"], "missing non-claim: " + key
        assert result["non_claims"][key] is True


def test_no_single_correct_way_is_ever_claimed():
    result = understand_architectural_example_v1(_meaningful_example())
    assert result["non_claims"]["not_fixed_truth"] is True
    assert result["non_claims"]["not_single_correct_way"] is True
    assert result["uncertainty"]["single_correct_interpretation"] is False


# ---------------------------------------------------------------------------
# 3. Input gating
# ---------------------------------------------------------------------------


def test_declared_contract_is_accepted():
    result = understand_architectural_example_v1(_meaningful_example())
    assert result["contract"] == CONTRACT


@pytest.mark.parametrize(
    "contract",
    [
        "ArchitecturalCADDrawingV1",
        "ArchitecturalDXFDrawingV1",
        "ArchitecturalDWGDrawingV1",
        "ArchitecturalBIMEntityV1",
        "ArchitecturalIFCEntityV1",
        "ArchitecturalRenderingOutputV1",
        "ArchitecturalGeometryIntentV1",
        "ArchitecturalMemoryRecordV1",
        "ArchitecturalVisionReportV1",
        "ArchitecturalDesignReasoningResultV1",
        "ArchitecturalSemanticGraphV1",
        "ImageIntentV1",
        "SiteIntentV1",
    ],
)
def test_forbidden_input_contract_is_rejected(contract):
    example = _meaningful_example(contract=contract)
    with pytest.raises(ValueError):
        understand_architectural_example_v1(example)


def test_non_dict_input_raises_type_error():
    with pytest.raises(TypeError):
        understand_architectural_example_v1("a master bedroom")


def test_missing_contract_field_raises_value_error():
    example = _meaningful_example()
    del example["contract"]
    with pytest.raises(ValueError):
        understand_architectural_example_v1(example)


def test_wrong_version_is_rejected():
    with pytest.raises(ValueError):
        understand_architectural_example_v1(_meaningful_example(version="2.0"))


def test_unknown_contract_string_is_rejected():
    with pytest.raises(ValueError):
        understand_architectural_example_v1(
            _meaningful_example(contract="SomethingElseV1")
        )


# ---------------------------------------------------------------------------
# 4. The brief's core requirement: concept, NOT components
# ---------------------------------------------------------------------------


def test_meaningful_example_extracts_architectural_meaning():
    result = understand_architectural_example_v1(_meaningful_example())
    assert result["concept_understanding"]["meaning_extracted"] is True


def test_meaningful_example_yields_supported_concepts():
    result = understand_architectural_example_v1(_meaningful_example())
    assert result["concept_understanding"]["supported_concept_count"] > 0


def test_brief_named_concepts_are_grounded_by_the_master_bedroom_lesson():
    """The brief enumerates the concepts the lesson must convey.

    They must be GROUNDED by the case's own meaning evidence, not merely
    present because the index lists them.
    """
    result = understand_architectural_example_v1(_meaningful_example())
    grounded = {
        c["concept"]
        for c in result["concept_understanding"]["extracted_concepts"]
        if c["grounded_in_case"]
    }
    assert "privacy" in grounded
    assert "personal_territory" in grounded
    assert "retreat" in grounded
    assert "separation_from_public_activity" in grounded
    assert "personal_control" in grounded
    assert "sleeping_rest_experience" in grounded
    assert "relation_to_intimate_functions" in grounded
    assert "movement_and_access" in grounded
    assert "contrast_with_public_space" in grounded


def test_master_bedroom_is_not_reduced_to_its_components():
    """The brief's central prohibition.

    The concept is NOT `bedroom + bathroom + closet`.
    """
    result = understand_architectural_example_v1(_meaningful_example())
    for concept in result["concept_understanding"]["extracted_concepts"]:
        if not concept["grounded_in_case"]:
            continue
        # A grounded concept must be carried by MEANING evidence, never by the
        # mere presence of its physical components.
        assert concept["evidence_reference"], (
            "concept " + concept["concept"] + " has no meaning evidence"
        )


def test_component_only_example_extracts_no_meaning():
    """The anti-example: naming the pieces is NOT understanding."""
    result = understand_architectural_example_v1(_component_only_example())
    assert result["concept_understanding"]["meaning_extracted"] is False
    assert result["concept_understanding"]["supported_concept_count"] == 0


def test_component_only_example_reports_concepts_without_meaning():
    result = understand_architectural_example_v1(_component_only_example())
    unresolved = result["uncertainty"]["concepts_without_meaning_evidence"]
    assert unresolved, "components-only example must leave concepts unresolved"
    assert "privacy" in unresolved


def test_component_only_example_flags_components_without_meaning():
    result = understand_architectural_example_v1(_component_only_example())
    flagged = [
        c
        for c in result["concept_understanding"]["extracted_concepts"]
        if c["case_operation"] == "component_mentioned_only"
    ]
    assert flagged
    for concept in flagged:
        assert concept["component_mention"]
        assert concept["evidence_reference"] == []
        assert concept["grounded_in_case"] is False
        assert concept["uncertainty"]["resolved"] is False


def test_components_alone_do_not_establish_meaning_is_declared():
    result = understand_architectural_example_v1(_component_only_example())
    assert (
        result["concept_understanding"][
            "components_alone_do_not_establish_meaning"
        ]
        is True
    )


# ---------------------------------------------------------------------------
# 5. The index is a starting semantic index, NOT the source of truth
# ---------------------------------------------------------------------------


def test_index_role_is_declared_as_starting_semantic_index():
    result = understand_architectural_example_v1(_meaningful_example())
    summary = result["concept_understanding"]
    assert summary["index_role"] == "starting_semantic_index"
    assert summary["index_is_source_of_truth"] is False
    assert summary["index_is_rule_set"] is False


def test_index_entries_are_not_emitted_as_understood_without_case_grounding():
    """An index entry the case never grounds is NOT understood for this case."""
    result = understand_architectural_example_v1(_component_only_example())
    grounded = [
        c
        for c in result["concept_understanding"]["extracted_concepts"]
        if c["grounded_in_case"]
    ]
    assert grounded == []


def test_concepts_grounded_in_case_are_counted_separately_from_index():
    result = understand_architectural_example_v1(_meaningful_example())
    summary = result["concept_understanding"]
    assert summary["grounded_in_case_count"] == summary["supported_concept_count"]
    assert summary["grounded_in_case_count"] <= len(_CONCEPT_INDEX)


def test_meaning_origin_distinguishes_case_from_index():
    """Every concept states WHERE its meaning came from."""
    result = understand_architectural_example_v1(_meaningful_example())
    for concept in result["concept_understanding"]["extracted_concepts"]:
        assert concept["meaning_origin"] in (
            "case_provided",
            "case_extended",
            "index_seed",
            "not_stated",
        )


# ---------------------------------------------------------------------------
# 6. The four per-case operations
# ---------------------------------------------------------------------------


def test_case_may_introduce_a_concept_the_index_does_not_know():
    example = _meaningful_example(
        concepts_introduced=[
            {
                "name": "threshold_dignity",
                "meaning": "The arrival is given ceremony.",
                "reason": "Guests are received formally.",
                "context": "Homes that receive visitors.",
                "alternative_interpretations": ["Could be mere weather shelter."],
            }
        ]
    )
    result = understand_architectural_example_v1(example)
    concepts = _concepts_by_name(result)
    assert "threshold_dignity" in concepts
    introduced = concepts["threshold_dignity"]
    assert introduced["case_operation"] == "introduced"
    assert introduced["anchor"] == "case_introduced"
    assert introduced["grounded_in_case"] is True
    assert introduced["meaning_origin"] == "case_provided"
    assert introduced["meaning"] == "The arrival is given ceremony."
    assert result["uncertainty"]["concepts_introduced_by_case"] == [
        "threshold_dignity"
    ]


def test_introduced_concept_appears_in_case_operations_summary():
    example = _meaningful_example(
        concepts_introduced=[
            {"name": "threshold_dignity", "meaning": "Arrival is given ceremony."}
        ]
    )
    result = understand_architectural_example_v1(example)
    ops = result["concept_understanding"]["case_operations"]
    assert ops["introduced"] == ["threshold_dignity"]


def test_case_may_enrich_an_existing_index_concept():
    example = _meaningful_example(
        concepts_enriched=[
            {
                "name": "privacy",
                "meaning_extension": (
                    "Privacy here is produced by depth and a turn, not by a "
                    "locked door."
                ),
                "reason": "A single approach path is easier to monitor.",
            }
        ]
    )
    result = understand_architectural_example_v1(example)
    concepts = _concepts_by_name(result)
    privacy = concepts["privacy"]
    assert privacy["case_operation"] == "enriched"
    assert privacy["anchor"] == "semantic_index"
    assert privacy["grounded_in_case"] is True
    assert privacy["meaning_origin"] in ("case_provided", "case_extended")
    assert result["uncertainty"]["concepts_enriched_by_case"] == ["privacy"]


def test_enriched_concept_may_carry_the_case_extended_meaning():
    example = _meaningful_example(
        concepts_enriched=[
            {"name": "privacy", "meaning": "Privacy as guarded sightlines."}
        ]
    )
    result = understand_architectural_example_v1(example)
    privacy = _concepts_by_name(result)["privacy"]
    assert privacy["meaning"] == "Privacy as guarded sightlines."
    assert privacy["meaning_origin"] == "case_extended"


def test_case_may_add_evidence_for_an_existing_concept():
    example = _meaningful_example(
        concepts_evidence=[
            {"concept": "retreat", "evidence": "a screened alcove off the room"}
        ]
    )
    result = understand_architectural_example_v1(example)
    retreat = _concepts_by_name(result)["retreat"]
    assert retreat["case_operation"] == "evidence_added"
    assert retreat["grounded_in_case"] is True
    assert "a screened alcove off the room" in retreat["evidence_reference"]
    assert result["uncertainty"]["evidence_added_by_case"] == ["retreat"]


def test_case_may_mark_a_concept_not_applicable():
    example = _meaningful_example(
        concepts_not_applicable=["relation_to_intimate_functions"]
    )
    result = understand_architectural_example_v1(example)
    concept = _concepts_by_name(result)["relation_to_intimate_functions"]
    assert concept["case_operation"] == "not_applicable"
    assert concept["not_applicable_in_this_context"] is True
    assert concept["grounded_in_case"] is False
    assert concept["anchor"] == "semantic_index"
    assert result["uncertainty"]["concepts_not_applicable_in_this_context"] == [
        "relation_to_intimate_functions"
    ]


def test_not_applicable_concept_is_not_reported_as_introduced():
    """Explicitly declining a concept must not re-anchor it as case-authored."""
    example = _meaningful_example(
        concepts_not_applicable=[
            {"name": "brand_new_idea", "reason": "does not apply here"}
        ]
    )
    result = understand_architectural_example_v1(example)
    concept = _concepts_by_name(result)["brand_new_idea"]
    assert concept["anchor"] == "case_excluded"
    assert concept["case_operation"] == "not_applicable"
    assert concept["grounded_in_case"] is False
    assert "brand_new_idea" not in result["uncertainty"][
        "concepts_introduced_by_case"
    ]


def test_the_four_operations_compose_without_ordering():
    """A concept the case introduces may also carry evidence and alternatives."""
    example = _meaningful_example(
        concepts_introduced=[
            {
                "concept": "layered_threshold",
                "meaning": "Arrival happens through more than one layer.",
                "evidence": ["an outer gate, then a court, then the door"],
                "alternatives": ["Could be read as simple security."],
                "dependencies": ["climate", "street exposure"],
            }
        ]
    )
    result = understand_architectural_example_v1(example)
    concept = _concepts_by_name(result)["layered_threshold"]
    assert concept["grounded_in_case"] is True
    assert "an outer gate, then a court, then the door" in concept[
        "evidence_reference"
    ]
    assert "Could be read as simple security." in concept[
        "alternative_interpretations"
    ]
    assert "climate" in concept["context_dependencies"]


# ---------------------------------------------------------------------------
# 7. Observable elements and spatial relations
# ---------------------------------------------------------------------------


def test_observed_elements_are_detected_from_the_observation():
    result = understand_architectural_example_v1(_meaningful_example())
    assert result["observed_elements"]
    for element in result["observed_elements"]:
        assert element["status"] == "observed"
        assert element["evidence_reference"]


def test_spatial_relations_are_read_when_the_human_asserts_them():
    example = _meaningful_example(
        human_explanation=(
            "The sleeping place is withdrawn within a private zone and "
            "separated from the shared area, reached through a corridor."
        )
    )
    result = understand_architectural_example_v1(example)
    relations = {r["relation"] for r in result["spatial_relations"]}
    assert relations, "asserted spatial relations must be reported"
    assert "separated_from" in relations or "withdrawn_within" in relations


def test_no_spatial_relation_is_invented_when_none_is_asserted():
    example = _meaningful_example(
        human_explanation="The room is quiet.",
        description="A bed.",
    )
    result = understand_architectural_example_v1(example)
    for relation in result["spatial_relations"]:
        assert relation["asserted_by_human"] is True


# ---------------------------------------------------------------------------
# 8. Reason and context are preserved
# ---------------------------------------------------------------------------


def test_reason_and_context_are_carried_with_each_concept():
    result = understand_architectural_example_v1(_meaningful_example())
    assert result["concept_rationale_and_context"]
    entry = result["concept_rationale_and_context"][0]
    assert "concept" in entry
    assert "reason_and_context" in entry


def test_human_reason_is_preserved_when_supplied():
    result = understand_architectural_example_v1(_meaningful_example())
    reasons = [
        item["reason_and_context"]
        for item in result["concept_rationale_and_context"]
    ]
    assert any(r["reason_present"] for r in reasons)


def test_absent_reason_is_reported_honestly_not_invented():
    example = _meaningful_example()
    del example["reason"]
    del example["context"]
    result = understand_architectural_example_v1(example)
    for item in result["concept_rationale_and_context"]:
        assert item["reason_and_context"]["reason"] is None
        assert item["reason_and_context"]["reason_present"] is False


def test_explanation_narrative_is_not_copied_forward():
    result = understand_architectural_example_v1(_meaningful_example())
    assert result["rationale_basis"]["restatement_of_explanation"] is None


# ---------------------------------------------------------------------------
# 9. Uncertainty and alternative interpretations are preserved
# ---------------------------------------------------------------------------


def test_uncertainty_block_reports_not_resolved_and_not_learned():
    result = understand_architectural_example_v1(_meaningful_example())
    assert result["uncertainty"]["resolved"] is False
    assert result["uncertainty"]["learned"] is False


def test_alternative_interpretations_are_preserved():
    result = understand_architectural_example_v1(_meaningful_example())
    assert result["uncertainty"]["alternative_interpretations_preserved"] is True
    supported = [
        c
        for c in result["concept_understanding"]["extracted_concepts"]
        if c["grounded_in_case"]
    ]
    assert supported
    for concept in supported:
        assert concept["alternative_interpretations"], (
            "concept " + concept["concept"] + " declares no alternative"
        )


def test_context_dependencies_are_preserved():
    result = understand_architectural_example_v1(_meaningful_example())
    assert result["uncertainty"]["context_dependencies_preserved"] is True
    supported = [
        c
        for c in result["concept_understanding"]["extracted_concepts"]
        if c["grounded_in_case"]
    ]
    for concept in supported:
        assert concept["context_dependencies"], (
            "concept " + concept["concept"] + " declares no context dependency"
        )


def test_multiple_valid_solutions_remain_possible():
    result = understand_architectural_example_v1(_meaningful_example())
    assert result["uncertainty"]["multiple_valid_solutions_possible"] is True


def test_human_uncertainty_is_carried_through():
    example = _meaningful_example(
        uncertainty={"unknowns": ["occupant count"], "conflicts": []}
    )
    result = understand_architectural_example_v1(example)
    assert result["uncertainty"]["human_uncertainty"]["unknowns"] == [
        "occupant count"
    ]


def test_concept_interpretation_is_never_marked_resolved():
    result = understand_architectural_example_v1(_meaningful_example())
    for concept in result["concept_understanding"]["extracted_concepts"]:
        assert concept["uncertainty"]["resolved"] is False


# ---------------------------------------------------------------------------
# 10. Index-listed-only concepts are not treated as understood
# ---------------------------------------------------------------------------


def test_index_listed_concepts_are_reported_as_not_grounded():
    """A case that grounds only some concepts hides none of the rest."""
    example = _meaningful_example(
        human_explanation=(
            "The master bedroom is private: it is withdrawn from shared life."
        )
    )
    result = understand_architectural_example_v1(example)
    listed_only = [
        c
        for c in result["concept_understanding"]["extracted_concepts"]
        if c["case_operation"] == "component_mentioned_only"
    ]
    assert listed_only
    for concept in listed_only:
        assert concept["grounded_in_case"] is False
        assert concept["evidence_reference"] == []


def test_index_listed_only_count_is_declared():
    result = understand_architectural_example_v1(_meaningful_example())
    assert "index_listed_only_count" in result["concept_understanding"]


# ---------------------------------------------------------------------------
# 11. Determinism and isolation
# ---------------------------------------------------------------------------


def test_output_is_deterministic():
    example = _meaningful_example()
    first = understand_architectural_example_v1(example)
    second = understand_architectural_example_v1(example)
    assert first == second


def test_input_is_not_mutated():
    example = _meaningful_example()
    snapshot = copy.deepcopy(example)
    understand_architectural_example_v1(example)
    assert example == snapshot


def test_returned_structure_is_independent_of_input():
    example = _meaningful_example()
    result = understand_architectural_example_v1(example)
    result["concept_understanding"]["extracted_concepts"].append({"concept": "x"})
    result["non_claims"]["not_memory"] = False
    again = understand_architectural_example_v1(_meaningful_example())
    assert again["non_claims"]["not_memory"] is True
    assert len(again["concept_understanding"]["extracted_concepts"]) == len(
        understand_architectural_example_v1(
            _meaningful_example()
        )["concept_understanding"]["extracted_concepts"]
    )


# ---------------------------------------------------------------------------
# 12. No rules, no formulas, no patterns, no geometry, no persistence
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
    return {k: v for k, v in result.items() if k != "non_claims"}


def test_authored_payload_contains_no_forbidden_language():
    result = understand_architectural_example_v1(_meaningful_example())
    serialized = str(_authored_payload(result)).lower()
    for term in FORBIDDEN_AUTHORED_TERMS:
        assert term not in serialized, "forbidden term emitted: " + term


def test_forbidden_language_scan_is_not_vacuous():
    """Negative control: the scan would fire on real forbidden language."""
    result = understand_architectural_example_v1(_meaningful_example())
    poisoned = dict(_authored_payload(result))
    poisoned["concept_understanding"] = {"note": "this is a design_solution"}
    assert "design_solution" in str(poisoned).lower()


def test_module_does_not_import_any_cad_or_geometry_library():
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    for name in names:
        for banned in (
            "ezdxf",
            "ifcopenshell",
            "pythonocc",
            "trimesh",
            "open3d",
            "shapely",
            "PIL",
            "cv2",
            "torch",
            "comtypes",
            "win32com",
            "sqlite3",
            "pickle",
            "shelve",
            "os",
            "subprocess",
            "shutil",
        ):
            assert not name.startswith(banned), "module imports: " + name


def test_module_does_not_open_or_write_files():
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            assert name not in ("open", "write", "dump", "save"), (
                "module performs file I/O: " + str(name)
            )


def test_module_does_not_reference_ui_or_app_surfaces():
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        source = handle.read()
    for banned in ("ChatArchitect", "streamlit", "flask", "fastapi", "app.py"):
        assert banned not in source
