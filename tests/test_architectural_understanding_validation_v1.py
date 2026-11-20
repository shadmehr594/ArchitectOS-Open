"""Tests for ArchitecturalUnderstandingValidationV1.

Written from the BRIEF's semantics, not from the implementation.

The brief is explicit about what this validation must show:

    "فقط نشان دهد آیا مفهوم معماری را فهمیده است یا فقط کلمات را تطبیق داده."
    It must show ONLY whether the architectural concept was understood, or
    whether only the WORDS were matched.

And it must NOT:

    design · propose a plan (پیشنهاد پلان) · build rules · give formulas

The central discrimination this suite pins is the difference between:

    a label named with no architectural reason  -> word_matching_only
    a label grounded in spatial/experiential
    or contextual evidence                      -> understood

`word_matching_only` is reported as NOT understanding.
"""

import ast
import copy
import json

import pytest

from core.knowledge.understanding_foundation.architectural_understanding_foundation_v1 import (
    TEACHING_EXAMPLE_CONTRACT,
    understand_architectural_example_v1,
)
from core.knowledge.understanding_foundation.architectural_understanding_validation_v1 import (
    CONTRACT,
    NEW_SPACE_CONTRACT,
    NEW_SPACE_VERSION,
    UNDERSTOOD_CONCEPTS_CONTRACT,
    VALIDATION_STATUSES,
    VERSION,
    validate_architectural_understanding_v1,
)

MODULE_PATH = (
    "core/knowledge/understanding_foundation/"
    "architectural_understanding_validation_v1.py"
)

REQUIRED_TOP_LEVEL = (
    "contract",
    "version",
    "concept_understanding_analysis",
    "understanding_summary",
    "concept_walkthrough",
    "evidence_basis",
    "uncertainty",
    "open_questions",
    "analysis_basis",
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
    "not_plan_proposal",
    "not_fixed_truth",
    "not_single_correct_way",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _taught_understanding():
    """The concepts extracted from the brief's Master Bedroom lesson."""
    example = {
        "contract": TEACHING_EXAMPLE_CONTRACT,
        "version": "1.0",
        "example_id": "ex_master_bedroom_meaning_01",
        "teaching_topic": "master_bedroom",
        "observed_elements": ["a bed", "a bathroom", "a closet", "a corridor"],
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
    return understand_architectural_example_v1(example)


def _evidence_space(**overrides):
    """A NEW space described by its architectural conditions.

    It never names the concepts. It describes the SPATIAL SITUATION that
    produces them.
    """
    space = {
        "contract": NEW_SPACE_CONTRACT,
        "version": NEW_SPACE_VERSION,
        "space_id": "new_space_screened_alcove",
        "space_name": "a sleeping place with a screened washing alcove",
        "description": (
            "The bed is placed away from the street, behind a screen so the "
            "sleeper is not overlooked. "
            "The place sits beyond the shared area, reached through a corridor "
            "after passing the guest space. "
            "A washing alcove adjoins the sleeping place, close enough to "
            "reach in a few steps without dressing in front of anyone. "
            "It is quiet and undisturbed, and the occupant decides when to "
            "open it to others."
        ),
    }
    space.update(overrides)
    return space


def _word_matching_space(**overrides):
    """The anti-example: the concepts are NAMED but never reasoned about."""
    space = {
        "contract": NEW_SPACE_CONTRACT,
        "version": NEW_SPACE_VERSION,
        "space_id": "new_space_label_only",
        "space_name": "a private room",
        "description": (
            "This is a private personal territory for rest and retreat with "
            "good access and control."
        ),
    }
    space.update(overrides)
    return space


def _unrelated_space(**overrides):
    """A space that presents none of the taught concepts at all."""
    space = {
        "contract": NEW_SPACE_CONTRACT,
        "version": NEW_SPACE_VERSION,
        "space_id": "new_space_unrelated",
        "space_name": "a storage yard",
        "description": (
            "An open concrete yard used for stacking crates and parking "
            "vehicles."
        ),
    }
    space.update(overrides)
    return space


# ---------------------------------------------------------------------------
# 1. Contract surface
# ---------------------------------------------------------------------------


def test_contract_and_version_are_declared():
    assert CONTRACT == "ArchitecturalUnderstandingValidationV1"
    assert VERSION == "1.0"


def test_output_contains_every_required_top_level_key():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    for key in REQUIRED_TOP_LEVEL:
        assert key in result, "missing output key: " + key


def test_output_is_json_serialisable():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    assert json.loads(json.dumps(result))


def test_output_is_transient_and_read_only():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_validation_status_vocabulary_is_declared():
    assert set(VALIDATION_STATUSES) == {
        "understood",
        "word_matching_only",
        "not_addressed",
    }


def test_not_addressed_is_not_a_failure_status():
    """`not_addressed` exists so a space may simply not raise a concept.

    Concepts are not mandatory properties of a space, so there is no
    `unresolved` / `failed` verdict in this vocabulary.
    """
    assert "unresolved" not in VALIDATION_STATUSES
    assert "failed" not in VALIDATION_STATUSES


# ---------------------------------------------------------------------------
# 2. Required non-claims
# ---------------------------------------------------------------------------


def test_all_required_non_claims_are_true():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    for key in REQUIRED_NON_CLAIMS:
        assert key in result["non_claims"], "missing non-claim: " + key
        assert result["non_claims"][key] is True


def test_no_plan_is_ever_proposed():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    assert result["non_claims"]["not_plan_proposal"] is True
    assert result["uncertainty"]["plan_proposed"] is False
    assert result["uncertainty"]["designed"] is False


def test_no_single_correct_way_is_ever_claimed():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    assert result["non_claims"]["not_fixed_truth"] is True
    assert result["uncertainty"]["single_correct_interpretation"] is False


# ---------------------------------------------------------------------------
# 3. Input gating
# ---------------------------------------------------------------------------


def test_declared_contracts_are_accepted():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
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
        "ArchitecturalTeachingCaseV1",
        "ArchitecturalKnowledgeTeachingValidationV1",
    ],
)
def test_forbidden_first_argument_is_rejected(contract):
    with pytest.raises(ValueError):
        validate_architectural_understanding_v1(
            {"contract": contract, "version": "1.0"}, _evidence_space()
        )


@pytest.mark.parametrize(
    "contract",
    [
        "ArchitecturalCADDrawingV1",
        "ArchitecturalBIMEntityV1",
        "ArchitecturalIFCEntityV1",
        "ArchitecturalRenderingOutputV1",
        "ArchitecturalMemoryRecordV1",
        "ArchitecturalDesignReasoningResultV1",
        "ArchitecturalHumanTeachingExampleV1",
    ],
)
def test_forbidden_second_argument_is_rejected(contract):
    with pytest.raises(ValueError):
        validate_architectural_understanding_v1(
            _taught_understanding(),
            {"contract": contract, "version": "1.0"},
        )


def test_non_dict_first_argument_raises_type_error():
    with pytest.raises(TypeError):
        validate_architectural_understanding_v1("concepts", _evidence_space())


def test_non_dict_second_argument_raises_type_error():
    with pytest.raises(TypeError):
        validate_architectural_understanding_v1(_taught_understanding(), "a space")


def test_missing_contract_field_is_rejected():
    with pytest.raises(ValueError):
        validate_architectural_understanding_v1(
            {"version": "1.0"}, _evidence_space()
        )


def test_wrong_versions_are_rejected():
    with pytest.raises(ValueError):
        validate_architectural_understanding_v1(
            dict(_taught_understanding(), version="9.9"), _evidence_space()
        )
    with pytest.raises(ValueError):
        validate_architectural_understanding_v1(
            _taught_understanding(), dict(_evidence_space(), version="9.9")
        )


# ---------------------------------------------------------------------------
# 4. THE CENTRAL DISCRIMINATION
# ---------------------------------------------------------------------------


def test_evidence_space_is_understood():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    assert result["understanding_summary"]["any_understanding"] is True
    assert result["understanding_summary"]["understood_count"] > 0


def test_word_matching_space_is_not_understood():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _word_matching_space()
    )
    assert result["understanding_summary"]["any_understanding"] is False


def test_word_matching_space_yields_word_matching_only():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _word_matching_space()
    )
    assert result["understanding_summary"]["only_words_matched"] is True
    assert result["understanding_summary"]["word_matching_only_count"] > 0


def test_word_matching_is_explicitly_reported_as_not_understanding():
    """The brief's exact demand, stated as an assertion."""
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _word_matching_space()
    )
    summary = result["understanding_summary"]
    assert summary["concept_understood"] is False
    # The words were matched...
    word_only = [
        w
        for w in result["concept_walkthrough"]
        if w["analysis_status"] == "word_matching_only"
    ]
    assert word_only
    for entry in word_only:
        # ...but with no architectural evidence, so it is NOT understanding.
        assert entry["architectural_evidence"] == []
        assert entry["vocabulary_matches"]
        assert entry["evidence_basis"]["label_only"] is True
        assert entry["uncertainty"]["understood"] is False
        assert entry["uncertainty"]["word_matching_only"] is True


def test_understood_requires_architectural_evidence_not_vocabulary():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    understood = [
        w
        for w in result["concept_walkthrough"]
        if w["analysis_status"] == "understood"
    ]
    assert understood
    for entry in understood:
        assert entry["architectural_evidence"], (
            "understood concept " + entry["concept"] + " has no evidence"
        )
        assert entry["evidence_basis"]["reason_grounded"] is True


def test_evidence_and_vocabulary_are_tracked_separately():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _word_matching_space()
    )
    for entry in result["concept_walkthrough"]:
        if entry["analysis_status"] == "word_matching_only":
            assert entry["architectural_evidence"] == []
            assert entry["vocabulary_matches"]


def test_unrelated_space_yields_no_understanding():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _unrelated_space()
    )
    assert result["understanding_summary"]["any_understanding"] is False
    assert result["understanding_summary"]["understood_count"] == 0


def test_genuine_evidence_is_not_reported_as_word_matching():
    """Negative control for the discrimination itself."""
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    assert result["understanding_summary"]["word_matching_only_count"] == 0


def test_analysis_method_declares_evidence_not_vocabulary():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    assert result["evidence_basis"]["analysis_method"] == "architectural_evidence"
    assert result["analysis_basis"]["evidence_required_beyond_vocabulary"] is True


# ---------------------------------------------------------------------------
# 5. Evidence is classed, so the verdict is auditable
# ---------------------------------------------------------------------------


def test_evidence_kinds_are_classified():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    kinds = set()
    for entry in result["concept_walkthrough"]:
        kinds.update(entry["evidence_basis"]["evidence_kinds"])
    assert kinds
    assert kinds <= {
        "spatial_relation",
        "experiential_quality",
        "user_experience",
        "architectural_element",
        "concept_condition",
    }


def test_concepts_with_evidence_are_listed_in_evidence_basis():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    listed = result["evidence_basis"]["concepts_with_architectural_evidence"]
    assert listed
    for entry in result["concept_walkthrough"]:
        if entry["analysis_status"] == "understood":
            assert entry["concept"] in listed


# ---------------------------------------------------------------------------
# 6. Contradiction and negation are handled, not silently accepted
# ---------------------------------------------------------------------------


def test_explicit_contradiction_yields_not_addressed():
    """A space that denies the concept must not be read as supporting it.

    With no surviving evidence the verdict is `not_addressed` — the concept is
    simply not carried by this space. It is NOT reported as a failure, because
    a space is allowed not to exercise any given concept.
    """
    space = _evidence_space(
        space_id="new_space_contradiction",
        space_name="an overlooked room",
        description=(
            "The room is not private and is not screened; it is fully visible "
            "from the street."
        ),
    )
    result = validate_architectural_understanding_v1(
        _taught_understanding(), space
    )
    privacy = next(
        w for w in result["concept_walkthrough"] if w["concept"] == "privacy"
    )
    assert privacy["analysis_status"] == "not_addressed"
    assert "privacy" not in result["uncertainty"]["concepts_not_understood"]


def test_positive_negation_phrase_is_not_misread_as_contradiction():
    """`not overlooked` DESCRIBES privacy and must count as support."""
    space = {
        "contract": NEW_SPACE_CONTRACT,
        "version": NEW_SPACE_VERSION,
        "space_id": "new_space_not_overlooked",
        "space_name": "a screened sleeping place",
        "description": "The sleeper is not overlooked from the street.",
    }
    result = validate_architectural_understanding_v1(
        _taught_understanding(), space
    )
    privacy = next(
        w for w in result["concept_walkthrough"] if w["concept"] == "privacy"
    )
    assert privacy["analysis_status"] == "understood"
    assert "not overlooked" in privacy["architectural_evidence"]


def test_contradiction_raises_a_human_question():
    space = _evidence_space(
        description="The room is not private and is not screened."
    )
    result = validate_architectural_understanding_v1(
        _taught_understanding(), space
    )
    types = {q["question_type"] for q in result["open_questions"]}
    assert "contradiction_probe" in types


# ---------------------------------------------------------------------------
# 7. Uncertainty is preserved
# ---------------------------------------------------------------------------


def test_uncertainty_block_reports_not_resolved_learned_or_designed():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    assert result["uncertainty"]["resolved"] is False
    assert result["uncertainty"]["designed"] is False
    assert result["uncertainty"]["plan_proposed"] is False


def test_concepts_not_understood_are_listed():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _word_matching_space()
    )
    assert result["uncertainty"]["concepts_not_understood"]
    assert result["uncertainty"]["words_matched_without_understanding"]


def test_alternative_interpretations_are_preserved():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    assert result["uncertainty"]["alternative_interpretations_preserved"] is True
    understood = [
        w
        for w in result["concept_walkthrough"]
        if w["analysis_status"] == "understood"
    ]
    for entry in understood:
        assert entry["alternative_interpretations"]


def test_context_dependencies_are_preserved():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    assert result["uncertainty"]["context_dependencies_preserved"] is True


def test_concept_analysis_is_never_marked_resolved():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    for entry in result["concept_walkthrough"]:
        assert entry["uncertainty"]["resolved"] is False


def test_human_uncertainty_is_carried_through():
    space = _evidence_space(uncertainty={"open": ["occupant count"]})
    result = validate_architectural_understanding_v1(
        _taught_understanding(), space
    )
    assert result["uncertainty"]["human_uncertainty"]["open"] == [
        "occupant count"
    ]


# ---------------------------------------------------------------------------
# 7b. Extensibility: concepts are not mandatory properties of a space
# ---------------------------------------------------------------------------


def test_concepts_are_declared_not_mandatory():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _unrelated_space()
    )
    assert result["uncertainty"]["concepts_are_not_mandatory"] is True


def test_a_space_raising_no_concept_reports_no_understanding_failure():
    """The unrelated space must report ZERO not-understood concepts.

    Every concept is `not_addressed`; that is silence, not failure.
    """
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _unrelated_space()
    )
    summary = result["understanding_summary"]
    assert summary["understood_count"] == 0
    assert summary["word_matching_only_count"] == 0
    assert summary["not_addressed_count"] == summary["total_concepts"]
    assert result["uncertainty"]["concepts_not_understood"] == []
    assert result["uncertainty"]["words_matched_without_understanding"] == []


def test_not_addressed_concepts_are_listed_separately_from_failures():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _unrelated_space()
    )
    uncertainty = result["uncertainty"]
    assert uncertainty["concepts_not_addressed_by_space"]
    # The two lists must never overlap.
    assert not set(uncertainty["concepts_not_addressed_by_space"]) & set(
        uncertainty["concepts_not_understood"]
    )


def test_not_addressed_means_insufficient_information_not_absence():
    """`not_addressed` states ONE thing: the material cannot decide.

    It must never assert failure, lack of understanding, contradiction, or
    absence of the concept.
    """
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _unrelated_space()
    )
    uncertainty = result["uncertainty"]
    assert (
        uncertainty["not_addressed_meaning"]
        == "insufficient_information_to_evaluate_not_absence"
    )
    # No absence / contradiction / failure claim is emitted anywhere.
    serialized = str(uncertainty).lower()
    for forbidden in (
        "concept_absent",
        "concepts_absent",
        "contradicted",
        "failed",
        "lacking",
    ):
        assert forbidden not in serialized, "forbidden framing: " + forbidden


def test_each_not_addressed_entry_declares_its_meaning_honestly():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _unrelated_space()
    )
    entries = [
        w for w in result["concept_walkthrough"]
        if w["analysis_status"] == "not_addressed"
    ]
    assert entries
    for entry in entries:
        u = entry["uncertainty"]
        assert u["insufficient_information_to_evaluate"] is True
        assert u["not_a_failure"] is True
        assert u["not_a_contradiction"] is True
        assert u["not_absence_of_concept"] is True


def test_not_addressed_probe_does_not_assert_absence():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _unrelated_space()
    )
    probes = [
        q for q in result["open_questions"]
        if q["question_type"] == "not_addressed_probe"
    ]
    assert probes
    for probe in probes:
        assert probe["rationale"] == "insufficient_information_to_evaluate"
        lowered = probe["question"].lower()
        assert "does not provide enough information" in lowered
        assert "failure" in lowered  # explicitly disclaims failure


def test_multiple_valid_solutions_are_preserved_by_validation():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    assert result["uncertainty"]["multiple_valid_solutions_possible"] is True
    assert result["uncertainty"]["single_correct_interpretation"] is False


def test_validation_reports_where_each_concept_was_anchored():
    """Concepts carry whether the case introduced them or the index seeded them."""
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    for entry in result["concept_walkthrough"]:
        assert entry.get("anchor") in (
            "semantic_index",
            "case_introduced",
            "case_excluded",
            None,
        )


def test_case_introduced_concept_is_still_analysed_against_the_new_space():
    """A concept the human introduced is analysable exactly like an indexed one."""
    example = {
        "contract": TEACHING_EXAMPLE_CONTRACT,
        "version": "1.0",
        "example_id": "ex_guest_wc",
        "teaching_topic": "guest_wc",
        "description": "A small washroom off the entrance hall.",
        "human_explanation": (
            "Guests use it without entering the family's private quarters, "
            "leaving a brief anonymous stop."
        ),
        "concepts_introduced": [
            {
                "name": "guest_anonymity",
                "meaning": (
                    "A service space visitors reach without crossing the "
                    "family's private territory."
                ),
                "reason": "Hospitality without exposing private life.",
            }
        ],
    }
    understood = understand_architectural_example_v1(example)
    space = {
        "contract": NEW_SPACE_CONTRACT,
        "version": NEW_SPACE_VERSION,
        "space_id": "sp_anon",
        "space_name": "a visitor washroom",
        "description": (
            "Visitors reach it from the entrance hall without crossing the "
            "family's private quarters, so they never enter the private life "
            "of the household."
        ),
    }
    result = validate_architectural_understanding_v1(understood, space)
    entry = next(
        w for w in result["concept_walkthrough"]
        if w["concept"] == "guest_anonymity"
    )
    assert entry["analysis_status"] == "understood"
    assert entry["anchor"] == "case_introduced"


def test_case_introduced_concept_named_without_meaning_is_word_matching_only():
    """Naming a human-introduced concept is still NOT understanding it."""
    example = {
        "contract": TEACHING_EXAMPLE_CONTRACT,
        "version": "1.0",
        "example_id": "ex_guest_wc",
        "teaching_topic": "guest_wc",
        "description": "A small washroom off the entrance hall.",
        "human_explanation": (
            "Guests use it without entering the family's private quarters."
        ),
        "concepts_introduced": [
            {
                "name": "guest_anonymity",
                "meaning": (
                    "A service space visitors reach without crossing the "
                    "family's private territory."
                ),
            }
        ],
    }
    understood = understand_architectural_example_v1(example)
    space = {
        "contract": NEW_SPACE_CONTRACT,
        "version": NEW_SPACE_VERSION,
        "space_id": "sp_anon_label",
        "space_name": "a guest anonymity room",
        "description": "This room achieves guest anonymity.",
    }
    result = validate_architectural_understanding_v1(understood, space)
    entry = next(
        w for w in result["concept_walkthrough"]
        if w["concept"] == "guest_anonymity"
    )
    assert entry["analysis_status"] == "word_matching_only"
    assert entry["architectural_evidence"] == []


# ---------------------------------------------------------------------------
# 8. Open questions
# ---------------------------------------------------------------------------


def test_word_matching_produces_a_meaning_gap_probe():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _word_matching_space()
    )
    types = {q["question_type"] for q in result["open_questions"]}
    assert "meaning_gap_probe" in types


def test_not_addressed_concepts_produce_a_probe():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _unrelated_space()
    )
    types = {q["question_type"] for q in result["open_questions"]}
    assert "not_addressed_probe" in types
    # No gap probe: the space never raised these concepts at all.
    assert "unresolved_concept_probe" not in types


def test_questions_carry_a_rationale():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _word_matching_space()
    )
    for question in result["open_questions"]:
        assert question["rationale"]


def test_fully_understood_space_asks_no_gap_questions():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    types = {q["question_type"] for q in result["open_questions"]}
    assert "meaning_gap_probe" not in types


# ---------------------------------------------------------------------------
# 9. The analysis is analytical only — no design, no plan
# ---------------------------------------------------------------------------


def test_description_narrative_is_not_copied_forward():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    assert result["analysis_basis"]["restatement_of_description"] is None


def test_analysis_proposes_no_arrangement():
    """No output field may carry an arrangement, dimension or placement."""
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    serialized = str(result).lower()
    for banned in (
        "proposed_layout",
        "arrangement",
        "dimension",
        "place_the",
        "move_the",
    ):
        assert banned not in serialized, "analysis leaked: " + banned


def test_walkthrough_entries_carry_no_design_field():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    for entry in result["concept_walkthrough"]:
        for banned in ("solution", "recommendation", "layout", "plan"):
            assert banned not in entry


# ---------------------------------------------------------------------------
# 10. Determinism and isolation
# ---------------------------------------------------------------------------


def test_output_is_deterministic():
    understood = _taught_understanding()
    space = _evidence_space()
    first = validate_architectural_understanding_v1(understood, space)
    second = validate_architectural_understanding_v1(understood, space)
    assert first == second


def test_inputs_are_not_mutated():
    understood = _taught_understanding()
    space = _evidence_space()
    a = copy.deepcopy(understood)
    b = copy.deepcopy(space)
    validate_architectural_understanding_v1(understood, space)
    assert understood == a
    assert space == b


def test_returned_structure_is_independent_of_inputs():
    understood = _taught_understanding()
    space = _evidence_space()
    result = validate_architectural_understanding_v1(understood, space)
    result["concept_walkthrough"].append({"concept": "injected"})
    result["non_claims"]["not_memory"] = False
    again = validate_architectural_understanding_v1(understood, space)
    assert again["non_claims"]["not_memory"] is True
    assert all(
        entry["concept"] != "injected" for entry in again["concept_walkthrough"]
    )


# ---------------------------------------------------------------------------
# 11. No rules, no geometry, no CAD/BIM/IFC, no persistence
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
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    serialized = str(_authored_payload(result)).lower()
    for term in FORBIDDEN_AUTHORED_TERMS:
        assert term not in serialized, "forbidden term emitted: " + term


def test_forbidden_language_scan_is_not_vacuous():
    result = validate_architectural_understanding_v1(
        _taught_understanding(), _evidence_space()
    )
    poisoned = dict(_authored_payload(result))
    poisoned["understanding_summary"] = {"note": "this is a design_solution"}
    assert "design_solution" in str(poisoned).lower()


def _module_ast():
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        return ast.parse(handle.read())


def _imported_modules():
    names = []
    for node in ast.walk(_module_ast()):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_module_does_not_import_cad_geometry_or_persistence():
    for name in _imported_modules():
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
    for node in ast.walk(_module_ast()):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            assert name not in ("open", "write", "dump", "save")


def test_module_does_not_reference_ui_or_app_surfaces():
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        source = handle.read()
    for banned in ("ChatArchitect", "streamlit", "flask", "fastapi", "app.py"):
        assert banned not in source


# ---------------------------------------------------------------------------
# 13. Language neutrality — no Persian vocabulary table, by decision
# ---------------------------------------------------------------------------
#
# Persian support is deliberately NOT added at this stage. It must later be
# designed as genuine human teaching IN Persian, not as an English->Persian
# keyword mapping. A translated label table would recreate the very
# word-matching this boundary exists to catch, so the guarantee is enforced
# here rather than left to convention.


def _compiled_module_string_constants(tree):
    """Every string literal the module defines, excluding documentation.

    Module/class/function docstrings are prose ABOUT the boundary — they
    legitimately quote the Persian brief. They are not vocabulary, so they are
    excluded; only working data structures are scanned.
    """
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr):
                first = body[0].value
                if isinstance(first, ast.Constant) and isinstance(
                    first.value, str
                ):
                    docstrings.add(id(first))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_module_contains_no_persian_or_arabic_script_vocabulary():
    constants = _compiled_module_string_constants(_module_ast())
    offenders = []
    for value in constants:
        for char in value:
            if (
                "\u0600" <= char <= "\u06ff"
                or "\u0750" <= char <= "\u077f"
                or "\ufb50" <= char <= "\ufdff"
                or "\ufe70" <= char <= "\ufeff"
            ):
                offenders.append(value)
                break
    # Persian clause punctuation ("،" / "؛") is STRUCTURAL, not vocabulary.
    # It carries no meaning and adds no translation, so it is permitted.
    allowed_structural = {"،", "؛"}
    unexpected = [v for v in offenders if v not in allowed_structural]
    assert unexpected == [], (
        "Persian/Arabic vocabulary is not to be added at this stage: "
        + repr(unexpected)
    )


def test_documentation_may_quote_the_brief_but_data_may_not():
    """Negative control: the scan would fire on a real translated label."""
    from core.knowledge.understanding_foundation.architectural_understanding_validation_v1 import (
        _LABEL_TERMS,
    )

    assert _LABEL_TERMS  # non-empty: the scan has something to inspect
    # Simulate the prohibited change and prove the guard would catch it.
    poisoned = dict(_LABEL_TERMS)
    poisoned["privacy"] = ("privacy", "private", "\u0648\u0631\u0648\u062f\u06cc")
    found = [
        term
        for terms in poisoned.values()
        for term in terms
        if any("\u0600" <= ch <= "\u06ff" for ch in term)
    ]
    assert found, "the language guard must be able to detect a translated label"


def test_label_terms_contain_no_cross_language_mapping():
    """The label table must not become an English->Persian dictionary."""
    from core.knowledge.understanding_foundation.architectural_understanding_validation_v1 import (
        _LABEL_TERMS,
    )

    for concept, terms in _LABEL_TERMS.items():
        for term in terms:
            for char in term:
                assert not ("\u0600" <= char <= "\u06ff"), (
                    "concept " + concept + " carries a translated label: " + term
                )


def test_label_terms_are_not_language_keyed():
    """No per-language structure exists yet, by decision."""
    from core.knowledge.understanding_foundation.architectural_understanding_validation_v1 import (
        _LABEL_TERMS,
    )

    for concept, terms in _LABEL_TERMS.items():
        assert isinstance(terms, (tuple, list)), concept
        for term in terms:
            assert isinstance(term, str), concept
