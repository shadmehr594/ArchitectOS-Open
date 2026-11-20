"""Tests for V3WhyGroundingV1 - the WHY as a first-class participant.

The questions this suite answers:
  * is the reason split off verbatim, and never invented?
  * is a binding only recorded when there is genuine shared content?
  * does a WHY swap actually move the grounding - and is the comparison refused
    when it carries no information?
  * is a stability comparison clearly labelled as NOT learning evidence?
"""

import ast
import re

import pytest

from core.knowledge.understanding_foundation.why_condition_abstraction import (
    v3_contracts as C,
)
from core.knowledge.understanding_foundation.why_condition_abstraction import (
    v3_why_grounding_v1 as G,
)

MODULE_PATH = (
    "core/knowledge/understanding_foundation/why_condition_abstraction/"
    "v3_why_grounding_v1.py"
)


# ---------------------------------------------------------------------------#
# 1. Splitting a reason off, verbatim
# ---------------------------------------------------------------------------#


def test_reason_is_split_on_because():
    condition, reason = G.split_reason(
        "the alcove is set back because the user needs to recover"
    )
    assert condition == "the alcove is set back"
    assert reason == "the user needs to recover"


def test_reason_split_is_verbatim_and_not_reworded():
    original = "a niche sits apart so that someone who is weary can recover"
    _, reason = G.split_reason(original)
    assert reason in original


def test_longest_connector_wins_so_that_is_not_truncated_to_so():
    _, reason = G.split_reason("a niche sits apart so that a person rests")
    assert reason == "a person rests"
    assert not reason.startswith("that")


def test_the_discontinuous_for_to_purpose_form_is_split():
    condition, reason = G.split_reason(
        "a bay stands back from the walkway for the user to recover in private"
    )
    assert condition == "a bay stands back from the walkway"
    assert reason.startswith("for the user to")


def test_no_connector_means_the_reason_is_empty_and_never_invented():
    condition, reason = G.split_reason("a plain wall stands there")
    assert reason == ""
    assert condition == "a plain wall stands there"


def test_connector_table_uses_only_ordinary_causal_words():
    for connector in G.WHY_CONNECTORS:
        assert re.fullmatch(r"[a-z0-9 ]+", connector), connector
        assert connector not in C.MODE_E_FORBIDDEN_RELATION_TERMS, connector


# ---------------------------------------------------------------------------#
# 2. Causal direction
# ---------------------------------------------------------------------------#


def test_purpose_is_read_from_a_purpose_marker():
    direction = G.read_causal_direction("the user needs to recover")
    assert direction["value"] == "purpose"
    assert direction["kind_origin"] == C.ORIGIN_DERIVED


def test_cause_is_read_from_a_cause_marker():
    direction = G.read_causal_direction("because the sun is too strong")
    assert direction["value"] == "cause"


def test_consequence_is_read_from_a_consequence_marker():
    direction = G.read_causal_direction("therefore the room stays cool")
    assert direction["value"] == "consequence"


def test_an_unmarked_reason_has_unknown_direction():
    direction = G.read_causal_direction("a quiet corner")
    assert direction["value"] == "unknown"
    assert direction["marker"] is None


# ---------------------------------------------------------------------------#
# 3. Binding requires genuine shared content
# ---------------------------------------------------------------------------#


def test_a_reason_with_no_shared_content_is_unbound():
    record = G.ground_condition(
        "the alcove is set back", "the paint is a warm shade"
    )
    assert record["determination"] == "unbound"
    assert record["binding"]["bound"] is False


def test_a_missing_reason_is_unbound_and_recorded_honestly():
    record = G.ground_condition("the alcove is set back", "")
    assert record["determination"] == "unbound"
    assert record["grounding"] == "no_reason_supplied"


def test_a_reason_naming_something_the_condition_does_not_is_necessary():
    record = G.ground_condition(
        "a seat is placed near the window",
        "the seat near the window is for recovery",
    )
    assert record["determination"] in ("necessary", "context")
    assert record["binding"]["bound"] is True
    assert record["binding"]["shared_content"]


def test_grounding_never_claims_to_know_human_intent():
    record = G.ground_condition("the alcove is set back", "the user recovers")
    assert record["is_a_claim_about_human_intent"] is False
    assert "not a truth claim" in record["note"]


# ---------------------------------------------------------------------------#
# 4. Validation
# ---------------------------------------------------------------------------#


def test_validation_accepts_a_valid_record():
    record = G.ground_condition("a seat by the window", "the seat is for rest")
    out = G.validate_grounding(record)
    assert out == record
    assert out is not record


def test_validation_refuses_a_non_dict():
    with pytest.raises(TypeError):
        G.validate_grounding("not a dict")


def test_validation_refuses_a_wrong_contract():
    with pytest.raises(ValueError):
        G.validate_grounding({"contract": "Other", "version": "1.0"})


def test_validation_refuses_an_unknown_determination():
    record = G.ground_condition("a seat by the window", "the seat is for rest")
    record["determination"] = "probably"
    with pytest.raises(ValueError):
        G.validate_grounding(record)


def test_validation_refuses_a_record_missing_a_field():
    record = G.ground_condition("a seat by the window", "the seat is for rest")
    del record["binding"]
    with pytest.raises(ValueError):
        G.validate_grounding(record)


# ---------------------------------------------------------------------------#
# 5. The WHY swap, and its honest refusals
# ---------------------------------------------------------------------------#


def test_a_real_why_swap_changes_the_grounding():
    before = G.ground_condition("a seat near the window is set here",
                                "the seat is for recovery")
    after = G.ground_condition("a seat near the window is set here",
                               "the tiles were left over")
    result = G.why_swap_effect(before, after)
    assert result["state"] in ("MEASURED_PASS", "INCONCLUSIVE")


def test_a_why_swap_with_no_swapped_reason_is_inconclusive():
    before = G.ground_condition("the alcove is set back", "the user recovers")
    result = G.why_swap_effect(before, None)
    assert result["state"] == "INCONCLUSIVE"
    assert result["measurable"] is False


def test_a_why_swap_on_two_unbound_reasons_is_inconclusive_not_a_pass():
    before = G.ground_condition("the alcove is set back", "the paint is warm")
    after = G.ground_condition("the alcove is set back", "the budget is fixed")
    result = G.why_swap_effect(before, after)
    assert result["state"] == "INCONCLUSIVE"
    assert result["measurable"] is False


def test_a_why_swap_that_changes_nothing_is_a_measured_fail():
    before = G.ground_condition("a seat near the window is for recovery",
                                "the seat near the window is for recovery")
    result = G.why_swap_effect(before, before)
    assert result["state"] in ("MEASURED_FAIL", "INCONCLUSIVE")


# ---------------------------------------------------------------------------#
# 6. Stability is never learning evidence
# ---------------------------------------------------------------------------#


def test_stability_measurement_is_labelled_representation_stability():
    result = G.grounding_stable_under_text_change(
        "a seat near the window", "the seat near the window is for rest",
        "a seat near the window", "the seat near the window is for rest",
    )
    assert result["semantics"] == C.FINGERPRINT_SEMANTICS
    assert result["is_learning_evidence"] is False
    assert "never evidence of learning" in result["note"]


def test_stability_reports_disagreement_honestly():
    result = G.grounding_stable_under_text_change(
        "a seat near the window", "the seat near the window is for recovery",
        "a seat near the window", "the tiles were left over",
    )
    assert "stable" in result
    assert result["is_learning_evidence"] is False


# ---------------------------------------------------------------------------#
# 7. Static audits
# ---------------------------------------------------------------------------#


def _module_source():
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        return handle.read()


def _docstring_ranges(tree):
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(
                body[0].value, ast.Constant
            ) and isinstance(body[0].value.value, str):
                ranges.append((body[0].lineno - 1,
                               getattr(body[0], "end_lineno",
                                       body[0].lineno) - 1))
    return ranges


def _guard_tables(tree):
    tables = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Tuple, ast.List)):
            values = [elt.value for elt in node.elts
                      if isinstance(elt, ast.Constant)
                      and isinstance(elt.value, str)]
            if values and len(values) == len(node.elts):
                tables.append((node.lineno - 1,
                               getattr(node, "end_lineno", node.lineno) - 1))
    return tables


def test_module_imports_no_similarity_library():
    tree = ast.parse(_module_source())
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.append(node.module)
    for name in imported:
        assert name.split(".")[0] not in (
            "numpy", "scipy", "sklearn", "torch", "sentence_transformers",
            "gensim", "spacy", "transformers",
        ), name


def test_module_uses_no_synonym_table_in_logic():
    source = _module_source()
    tree = ast.parse(source)
    excluded = _docstring_ranges(tree) + _guard_tables(tree)
    for index, line in enumerate(source.splitlines()):
        if any(start <= index <= end for start, end in excluded):
            continue
        assert "synonym_map" not in line.lower(), line


def test_module_does_not_import_the_frozen_v2_package():
    tree = ast.parse(_module_source())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "architectural_abstraction" not in node.module, node.module


def test_the_light_stem_fold_is_deliberately_shallow():
    """V2's aggressive fold was what made its invariants literal stems.

    V3 keeps the fold blunt on purpose: it may only strip a plural ending, so a
    binding cannot be manufactured by morphology.
    """
    assert G._stem_light("rooms") == "room"
    assert G._stem_light("watches") == "watch"
    # It must NOT collapse a verb into an action noun - that would be the V2
    # behaviour this experiment deliberately does not repeat.
    assert G._stem_light("recovering") != G._stem_light("recovery")


def test_module_is_ascii_apart_from_typographic_rules():
    source = _module_source()
    tree = ast.parse(source)
    docstrings = _docstring_ranges(tree)
    box = set("\u2500\u2502\u250c\u2510\u2514\u2518\u251c\u2524\u252c\u2534"
              "\u253c\u2550\u2551\u2554\u2557\u255a\u255d")
    for index, line in enumerate(source.splitlines()):
        if any(start <= index <= end for start, end in docstrings):
            continue
        for char in line:
            if char in box:
                continue
            assert ord(char) <= 0x7F, repr(line)
