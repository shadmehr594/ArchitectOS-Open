"""T1.1 — teaching candidate visibility, confirmation safety, contextual applicability.

CPU only. No model, no vision, no GPU, no ComfyUI. Every provider seam raises.
All ledger writes go to isolated temporary files.
"""

import json
import os
from copy import deepcopy
from types import SimpleNamespace

import pytest

from core.architecture.knowledge.human_learning_ledger_v1 import (
    APPLICABLE,
    NEEDS_REVIEW,
    NOT_APPLICABLE,
    PROVENANCE_HUMAN_ACCEPTED_RULE,
    append_accepted_rule,
    evaluate_rule_applicability,
    load_ledger,
    named_styles,
)
from core.prompt_intelligence.geometry_authority_handoff_v1 import (
    decision_instruction_block,
    resolve_design_decision,
)
from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta

PRESERVE = (
    "number_of_floors",
    "overall_massing",
    "building_silhouette",
    "main_window_positions",
    "main_door_positions",
    "roofline",
)

TEACHING_FA = "در نمای کلاسیک بهتر است تناسب ستون‌ها با ارتفاع نما رعایت شود."

#: A turn the EXISTING conversation-intent boundary classifies as TEACHING.
#: The Persian sentence above is classified ARCHITECTURE_CONVERSATION by that
#: boundary, which then nulls the candidate — a pre-existing classifier
#: disagreement, recorded as a limitation rather than silently changed here.
TEACHING_EN = (
    "Remember this rule: on a classical facade the column proportion should "
    "follow the facade height."
)


def _element(name, kinds, quote):
    return {
        "element": name,
        "kind": list(kinds),
        "context_kinds": [],
        "kind_basis": "subject_explicit",
        "source_quote": quote,
        "evidence_class": "MODEL_REPORTED",
        "verification_status": "UNVERIFIED",
        "confidence": None,
        "position": None,
        "relations": [],
    }


FACADE = {
    "contract": "ImageUnderstandingV1",
    "analysis_status": "ANALYZED_WITH_UNCERTAINTY",
    "image_type": "facade_or_elevation",
    "element_evidence": {
        "contract": "ArchitecturalElementEvidenceV1",
        "source_image": {"image_id": "facade-1", "sha256": "a" * 64},
        "elements": [
            _element("facade wall", ("wall",), "A pale facade wall plane."),
            _element("windows", ("window", "opening"), "Regular window openings."),
            _element("columns", ("column",), "Columns frame the entrance."),
            _element("entrance", ("entrance", "door"), "A central entrance door."),
        ],
    },
}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import socket

    def _blocked(self, address, *a, **k):
        raise AssertionError("network access attempted: %r" % (address,))

    monkeypatch.setattr(socket.socket, "connect", _blocked)


def _rule(**overrides):
    rule = {
        "id": "T11-RULE-001",
        "human_observation_fa": TEACHING_FA,
        "generalized_rule": "CLASSICAL_COLUMN_PROPORTION_TO_FACADE_HEIGHT",
        "scope": "FACADE",
        "date": "2026-10-24",
        "provenance": PROVENANCE_HUMAN_ACCEPTED_RULE,
        "active": True,
        "superseded_by": None,
    }
    rule.update(overrides)
    return rule


def _decision(text, *, rules=None, style=None, image_type=None, preserve=PRESERVE):
    delta = compile_edit_delta(text, image_edit=True)
    understanding = deepcopy(FACADE)
    if image_type:
        understanding["image_type"] = image_type
    return resolve_design_decision(
        user_text=text,
        edit_delta=delta,
        image_understanding=understanding,
        resolved_facade_knowledge=None,
        preserve_geometry=True,
        preserve_constraints=preserve,
        human_learning_rules=rules,
        design_context={"text": text, "style": style},
    )


# ==========================================================
# 1. TEACHING CANDIDATE VISIBILITY (HTTP)
# ==========================================================

@pytest.fixture
def client(monkeypatch):
    import app as application
    from core.llm.llm_gateway import LLMGateway

    monkeypatch.setattr(LLMGateway, "generate", lambda self, *a, **k: "recorded reply")

    def _forbidden(*a, **k):
        raise AssertionError("unexpected model/provider call")

    import core.vision.vision_provider_ollama_v1 as provider_module

    monkeypatch.setattr(provider_module.OllamaVisionProvider, "analyze", _forbidden)
    monkeypatch.setattr(provider_module.OllamaVisualObserver, "observe", _forbidden)
    monkeypatch.setattr(provider_module.OllamaTextNormalizer, "normalize", _forbidden)

    return application.app.test_client()


def _teaching_response(client, text=TEACHING_EN):
    response = client.post("/api/chat", json={"text": text})
    assert response.status_code == 200
    return (response.get_json() or {}).get("response") or {}


def test_teaching_turn_exposes_the_candidate_even_when_turn_semantics_exists(client):
    result = _teaching_response(client)

    assert result.get("turn_semantics"), "established field must still be present"
    teaching = result.get("teaching") or {}

    assert teaching, "the candidate must be visible on the teaching turn"
    assert teaching.get("confirmation_required") is True
    assert teaching.get("accepted") is False
    assert teaching.get("permanent_learning") is False


def test_teaching_review_shows_meaning_modality_and_applicability(client):
    teaching = (_teaching_response(client).get("teaching") or {})
    review = teaching.get("review") or {}

    assert review.get("original_statement") == TEACHING_EN
    assert review.get("modality") in ("RECOMMENDATION", "MANDATORY", "UNSPECIFIED")
    assert review.get("modality") == "RECOMMENDATION"
    assert review.get("confirmation_status") in ("observed", "needs_confirmation", "proposed")
    assert "applicability" in review
    assert review.get("proposition")


def test_persian_teaching_classifier_disagreement_is_recorded(client):
    """Known limitation: the boundary routes this Persian teaching as chat.

    Recorded explicitly so the behaviour is visible, not hidden. The boundary
    is the routing authority and was not changed here.
    """

    from core.chat.conversation_intent_boundary_v1 import (
        classify_conversation_intent,
    )

    decision = classify_conversation_intent(TEACHING_FA)

    assert decision.get("intent") != "TEACHING"

    result = _teaching_response(client, TEACHING_FA)

    assert result.get("teaching") is None or result.get("teaching") == {}


def test_displayed_candidate_is_not_learned_knowledge(client):
    teaching = (_teaching_response(client).get("teaching") or {})
    candidate = teaching.get("candidate") or {}

    # both existing candidate contracts state "not knowledge" in their own way
    assert candidate.get("is_learned_knowledge") is not True
    assert candidate.get("is_permanent") is not True
    assert candidate.get("persistent") is not True
    assert candidate.get("status") in ("observed", "needs_confirmation", "proposed")

    assert teaching.get("accepted") is False
    assert teaching.get("permanent_learning") is False
    assert teaching.get("confirmation_required") is True


def test_teaching_turn_does_not_write_the_ledger(client):
    from core.architecture.knowledge.human_learning_ledger_v1 import DEFAULT_PATH
    import hashlib

    before = hashlib.sha256(open(DEFAULT_PATH, "rb").read()).hexdigest()

    _teaching_response(client)

    after = hashlib.sha256(open(DEFAULT_PATH, "rb").read()).hexdigest()

    assert before == after


# ==========================================================
# 2. CONFIRMATION AUTHORIZATION BOUNDARY
# ==========================================================

def test_no_unprotected_confirmation_mutation_route_exists():
    import app as application

    mutation_rules = [
        str(rule)
        for rule in application.app.url_map.iter_rules()
        if any(
            token in str(rule).lower()
            for token in ("/confirm-accept", "/accept-rule", "/learning/confirm", "/ledger/append")
        )
    ]

    assert mutation_rules == [], (
        "no writable confirmation endpoint may exist without authenticated identity"
    )


def test_caller_supplied_provenance_is_not_authorization():
    """A caller string is provenance metadata, not proof of a human action."""

    with pytest.raises(ValueError):
        append_accepted_rule(_rule(), path=None, confirmed_by="")

    # even a well-formed string cannot be validated by the writer itself
    import inspect

    from core.architecture.knowledge import human_learning_ledger_v1 as ledger

    source = inspect.getsource(ledger.append_accepted_rule)

    assert "actor" not in source.lower() or "authenticated" in source.lower()


# ==========================================================
# 3. CONTEXTUAL APPLICABILITY
# ==========================================================

def test_named_styles_uses_the_existing_style_ontology():
    assert "classic" in named_styles(TEACHING_FA)
    assert "classic" in named_styles("a classical facade")
    assert named_styles("a plain wall") == set()


def test_control_a_classical_proportion_request_is_applicable():
    rule = _rule()
    context = {"text": "adjust the column proportions on this classical facade", "style": "classical",
               "image_type": "facade_or_elevation", "operation": "style_change"}

    evaluation = evaluate_rule_applicability(rule, context)

    assert evaluation["status"] == APPLICABLE


def test_control_b_classical_rule_does_not_apply_to_a_modern_lighting_request():
    rule = _rule()
    context = {
        "text": "make this modern facade a night render, keep materials",
        "style": "modern",
        "image_type": "facade_or_elevation",
        "operation": "time_of_day_change",
    }

    evaluation = evaluate_rule_applicability(rule, context)

    assert evaluation["status"] == NOT_APPLICABLE
    assert evaluation["reason"] == "style_conflict"


def test_control_b_unknown_style_is_not_guessed():
    rule = _rule(applies_to={"styles": ["classic"]})
    context = {"text": "make the facade a night render", "style": None,
               "image_type": "facade_or_elevation", "operation": "time_of_day_change"}

    evaluation = evaluate_rule_applicability(rule, context)

    assert evaluation["status"] == NEEDS_REVIEW
    assert evaluation["reason"] == "style_unknown"


def test_control_c_preserved_subject_excludes_the_rule():
    rule = _rule()
    context = {
        "text": "replace the facade finish with travertine, preserve the columns",
        "style": None,
        "image_type": "facade_or_elevation",
        "operation": "material_change",
        "fixed_elements": ["columns", "windows", "entrance"],
    }

    evaluation = evaluate_rule_applicability(rule, context)

    assert evaluation["status"] == NOT_APPLICABLE
    assert evaluation["reason"] == "subject_preserved"


def test_control_d_generic_facade_principle_applies_when_domain_matches():
    rule = _rule(
        id="T11-RULE-GENERIC",
        human_observation_fa="در نما، تناسبات کلی باید با مقیاس ساختمان هماهنگ باشد",
        generalized_rule="FACADE_SCALE_HARMONY",
        applies_to={"domains": ["facade"]},
    )
    context = {
        "text": "adjust the facade composition",
        "style": None,
        "image_type": "facade_or_elevation",
        "operation": "style_change",
    }

    evaluation = evaluate_rule_applicability(rule, context)

    assert evaluation["status"] == APPLICABLE


def test_domain_mismatch_is_not_applicable():
    rule = _rule(applies_to={"domains": ["floor_plan"]})
    context = {"text": "facade edit", "style": None, "image_type": "facade_or_elevation",
               "operation": "material_change"}

    evaluation = evaluate_rule_applicability(rule, context)

    assert evaluation["status"] == NOT_APPLICABLE
    assert evaluation["reason"] == "domain_mismatch"


# ==========================================================
# 4. DECISION EFFECT — RELEVANT VS IRRELEVANT
# ==========================================================

MATERIAL_TEXT = (
    "Use light travertine on the facade walls, but preserve the columns, "
    "windows and entrance."
)
CLASSICAL_TEXT = (
    "Adjust the column proportions on this classical facade, keep the mass unchanged."
)
MODERN_NIGHT_TEXT = "این نمای مدرن را شب کن؛ معماری و مصالح تغییر نکنند."


def test_relevant_rule_changes_the_decision_and_instruction():
    baseline = _decision(CLASSICAL_TEXT, rules=[], style="classical")
    with_rule = _decision(CLASSICAL_TEXT, rules=[_rule()], style="classical")

    assert baseline["applied_human_rules"] == []
    assert [item["id"] for item in with_rule["applied_human_rules"]] == ["T11-RULE-001"]
    assert with_rule != baseline

    block = decision_instruction_block(with_rule)["constraint_block"]
    assert "T11-RULE-001" in block


def test_irrelevant_rule_leaves_the_decision_identical():
    baseline = _decision(MODERN_NIGHT_TEXT, rules=[], style="modern")
    with_rule = _decision(MODERN_NIGHT_TEXT, rules=[_rule()], style="modern")

    assert with_rule["applied_human_rules"] == []
    assert with_rule["editable_elements"] == baseline["editable_elements"]
    assert with_rule["intended_changes"] == baseline["intended_changes"]

    block = decision_instruction_block(with_rule)
    assert "T11-RULE-001" not in (block or {}).get("constraint_block", "")


def test_decision_reports_why_a_rule_was_not_applied():
    decision = _decision(MODERN_NIGHT_TEXT, rules=[_rule()], style="modern")

    evaluations = decision.get("rule_evaluations") or []
    assert evaluations, "the decision must record the applicability verdict"
    assert evaluations[0]["status"] == NOT_APPLICABLE
    assert evaluations[0]["reason"] == "style_conflict"


def test_pending_rule_has_no_effect():
    pending = _rule(status="needs_confirmation", candidate_id="cand_1")
    baseline = _decision(CLASSICAL_TEXT, rules=[], style="classical")
    with_pending = _decision(CLASSICAL_TEXT, rules=[pending], style="classical")

    assert with_pending["applied_human_rules"] == []
    assert with_pending["editable_elements"] == baseline["editable_elements"]


def test_superseded_rule_has_no_effect():
    superseded = _rule(active=False, superseded_by="T11-RULE-002")
    decision = _decision(CLASSICAL_TEXT, rules=[superseded], style="classical")

    assert decision["applied_human_rules"] == []


def test_rule_never_creates_an_edit_target_or_a_visible_element():
    baseline = _decision(CLASSICAL_TEXT, rules=[], style="classical")
    with_rule = _decision(CLASSICAL_TEXT, rules=[_rule()], style="classical")

    # the rule IS applied here, so the assertions below are not vacuous
    assert [item["id"] for item in with_rule["applied_human_rules"]] == ["T11-RULE-001"]

    assert with_rule["editable_elements"] == baseline["editable_elements"]
    assert [item["element"] for item in with_rule["image_supported_context"]] == [
        item["element"] for item in baseline["image_supported_context"]
    ]
    for item in with_rule["applied_human_rules"]:
        assert item["provenance"] == PROVENANCE_HUMAN_ACCEPTED_RULE


# ==========================================================
# 5. LEDGER SAFETY
# ==========================================================

def test_duplicate_confirmation_cannot_insert_twice(tmp_path):
    path = str(tmp_path / "ledger.json")

    append_accepted_rule(_rule(), path=path, confirmed_by="human:test")

    with pytest.raises(ValueError):
        append_accepted_rule(_rule(), path=path, confirmed_by="human:test")

    assert len(load_ledger(path)["items"]) == 1


def test_rejection_creates_no_active_knowledge(tmp_path):
    path = str(tmp_path / "ledger.json")

    append_accepted_rule(_rule(), path=path, confirmed_by="human:test")

    from core.architecture.knowledge.human_learning_ledger_v1 import supersede_rule

    append_accepted_rule(
        _rule(id="T11-RULE-002", generalized_rule="REPLACEMENT"), path=path, confirmed_by="human:test"
    )
    supersede_rule("T11-RULE-001", "T11-RULE-002", path=path)

    active = [item for item in load_ledger(path)["items"] if item.get("active")]
    assert [item["id"] for item in active] == ["T11-RULE-002"]
