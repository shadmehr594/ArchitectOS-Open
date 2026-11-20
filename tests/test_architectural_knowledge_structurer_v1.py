# ==========================================================
# ARCHITECTURAL_KNOWLEDGE_STRUCTURER_V1 — CONTRACT / ACCEPTANCE TESTS
#
# The teacher's statements were retrieved as a LIST OF SENTENCES. This
# phase adds a REPRESENTATION layer that turns them into an
# architectural structure for one space — without learning, promoting,
# or touching the curriculum, the teaching memory or the corpus.
#
# The five tests the brief names, plus the guarantees that make the
# layer safe: the contract shape, per-item provenance, subject scope,
# and "nothing is written".
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_architectural_knowledge_structurer_v1.py
#   .venv/Scripts/python.exe tests/test_architectural_knowledge_structurer_v1.py
# ==========================================================


import json
import os
import sys
import tempfile

import pytest


ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if ROOT not in sys.path:

    sys.path.insert(0, ROOT)


_TEMP_ROOT = os.path.join(
    tempfile.gettempdir(), "architectos_knowledge_structurer_v1"
)

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = _TEMP_ROOT

os.environ.setdefault(
    "ARCHITECTOS_PROJECTS_ROOT", os.path.join(_TEMP_ROOT, "projects")
)

os.environ.setdefault(
    "ARCHITECTOS_PROJECT_TRASH_ROOT", os.path.join(_TEMP_ROOT, "trash")
)

os.environ["ARCHITECTOS_COMFY_PORT"] = "9"


from core.project.project_workspace_v1 import project_workspace  # noqa: E402

project_workspace.projects_root = os.path.join(_TEMP_ROOT, "projects")

project_workspace.trash_root = os.path.join(_TEMP_ROOT, "trash")

os.makedirs(project_workspace.projects_root, exist_ok=True)

os.makedirs(project_workspace.trash_root, exist_ok=True)


from core.knowledge.architectural_knowledge_structurer_v1 import (  # noqa: E402
    build_architectural_knowledge_structure_v1,
    structure_space_knowledge,
    render_structured_answer,
    CONTRACT,
)
from core.knowledge.architectural_knowledge_v1 import (
    build_architectural_knowledge_candidate_v1,
)
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)

from core.conversation.teaching_candidate_v1 import (  # noqa: E402
    teaching_candidate_store,
)


MASTER = "MASTER_BEDROOM_SLEEPING"

# The contract the brief pins, key by key.
REQUIRED_KEYS = (
    "space_id",
    "space_category",
    "definition",
    "users",
    "primary_goals",
    "privacy_level",
    "required_elements",
    "optional_elements",
    "spatial_relations",
    "design_rules",
    "size_dependency",
    "uncertainties",
    "provenance",
)


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))


def _project():

    manifest = project_workspace.create("Knowledge Structurer")

    return manifest.get("project_id") or (
        manifest.get("project") or {}
    ).get("project_id")


_RECORDED = {"n": 0}


def _record(project_id, statement, **extra):

    # The live teaching path always stamps an id and a confidence on a
    # candidate, so the fixtures do the same (brief rule 3: every
    # structured item keeps its source and its confidence/status).
    _RECORDED["n"] += 1

    payload = {
        "raw_statement": statement,
        "domain": "space",
        "status": "observed",
        "provenance": "HUMAN_TEACHER",
        "space_topic": MASTER,
        "entities": [],
        "relations": [],
        "polarity": "neutral",
        "knowledge_class": "OBSERVATION",
        "scope": "GENERAL",
        "candidate_id": "tc_struct_%04d" % _RECORDED["n"],
        "confidence": 0.9,
    }

    payload.update(extra)

    return teaching_candidate_store.record(project_id, payload)


def _structure(project_id, language="fa", **kwargs):

    return structure_space_knowledge(
        project_id=project_id,
        space_id=MASTER,
        language=language,
        **kwargs
    )


# ==========================================================
# TEST 1 — MASTER BEDROOM, PARENTS
# ==========================================================

def test_1_master_bedroom_users_contain_parents():

    project_id = _project()

    _record(
        project_id,
        "اتاق خواب مستر برای والدین هست",
        knowledge_class="DEFINITION",
        polarity="define",
    )

    structure = _structure(project_id) or {}

    return _check(
        "T1. 'اتاق خواب مستر برای والدین هست' -> users contains parents",
        "parents" in (structure.get("users") or []),
        {"users": structure.get("users")},
    )


def test_1b_the_user_is_reported_with_its_source():

    project_id = _project()

    _record(
        project_id,
        "اتاق خواب مستر برای والدین هست",
        knowledge_class="DEFINITION",
        polarity="define",
    )

    structure = _structure(project_id) or {}

    entries = [
        item for item in structure.get("items") or []
        if item.get("field") == "users"
    ]

    return _check(
        "T1b. the user entry carries its source candidate, statement and "
        "status",
        bool(entries)
        and entries[0].get("candidate_id")
        and entries[0].get("statement") == "اتاق خواب مستر برای والدین هست"
        and entries[0].get("status") == "observed"
        and entries[0].get("confidence") is not None,
        {"entry": entries[0] if entries else None},
    )


def test_1c_a_contrasting_room_does_not_become_a_user():

    project_id = _project()

    _record(
        project_id,
        "اتاق خواب مستر داریم که مخصوص والدین هست و اتاق خواب بچه ها",
    )

    structure = _structure(project_id) or {}

    return _check(
        "T1c. naming the CHILDREN'S room does not make children users of "
        "the master bedroom",
        "children" not in (structure.get("users") or [])
        and "parents" in (structure.get("users") or []),
        {"users": structure.get("users")},
    )


# ==========================================================
# TEST 2 — PRIVACY RULE
# ==========================================================

def test_2_privacy_rule_is_structured():

    project_id = _project()

    _record(project_id, "در باز شود دید به تخت نداشته باشد")

    structure = _structure(project_id) or {}

    rules = structure.get("design_rules") or []

    privacy = [
        rule for rule in rules
        if rule.get("type") == "privacy"
        and rule.get("rule") == "avoid_direct_view_to_bed_from_entry"
    ]

    return _check(
        "T2. 'در باز شود دید به تخت نداشته باشد' -> a privacy design rule",
        bool(privacy),
        {"rules": rules},
    )


def test_2b_the_rule_keeps_its_source():

    project_id = _project()

    _record(project_id, "در باز شود دید به تخت نداشته باشد")

    structure = _structure(project_id) or {}

    rules = structure.get("design_rules") or []

    sources = (rules[0] or {}).get("sources") if rules else None

    return _check(
        "T2b. every rule keeps its source statement, candidate and status",
        bool(sources)
        and sources[0].get("statement") == "در باز شود دید به تخت نداشته باشد"
        and sources[0].get("candidate_id")
        and sources[0].get("status") == "observed",
        {"sources": sources},
    )


# ==========================================================
# TEST 3 — WINDOW CORRECTION
# ==========================================================

def test_3_window_correction():

    project_id = _project()

    _record(
        project_id,
        "تخت دور از پنجره بهتر است، ولی اتاق خواب نیاز به نور و تهویه دارد",
        knowledge_class="DESIGN_RULE",
        polarity="require",
    )

    structure = _structure(project_id) or {}

    required = structure.get("required_elements") or []

    rules = [rule.get("rule") for rule in structure.get("design_rules") or []]

    return _check(
        "T3. the correction gives required window/light/ventilation AND "
        "the bed-relative-to-window placement rule",
        "daylight" in required
        and "ventilation" in required
        and "window" in required
        and "bed_away_from_window" in rules,
        {"required": required, "rules": rules},
    )


def test_3b_an_implied_element_says_it_is_implied():

    project_id = _project()

    _record(
        project_id,
        "اتاق خواب نیاز به نور و تهویه دارد",
        knowledge_class="DESIGN_RULE",
        polarity="require",
    )

    structure = _structure(project_id) or {}

    implied = [
        item for item in structure.get("items") or []
        if item.get("field") == "required_elements"
        and item.get("value") == "window"
    ]

    return _check(
        "T3b. an element derived from a NEED says what implied it — it is "
        "never presented as something the teacher said",
        bool(implied) and implied[0].get("kind") == "implied_element"
        and implied[0].get("implied_by") == "daylight",
        {"implied": implied[0] if implied else None},
    )


# ==========================================================
# TEST 4 — AREA DEPENDENCY
# ==========================================================

def test_4_area_dependency():

    project_id = _project()

    _record(
        project_id,
        "اگر زیربنا کم بود تخت دونفره با کمد کافی است، "
        "اگر فضا بیشتر باشد کلوزت و حمام اضافه می‌شود",
    )

    structure = _structure(project_id) or {}

    dependencies = {
        entry.get("condition"): entry.get("elements") or []
        for entry in structure.get("size_dependency") or []
    }

    return _check(
        "T4. a small/large area statement becomes size_dependency",
        "small_area" in dependencies
        and "large_area" in dependencies
        and "bed" in dependencies.get("small_area", [])
        and "wardrobe" in dependencies.get("small_area", [])
        and "bathroom" in dependencies.get("large_area", []),
        {"size_dependency": structure.get("size_dependency")},
    )


def test_4b_a_dependency_is_not_a_law():

    project_id = _project()

    _record(
        project_id,
        "اگر زیربنا کم بود تخت دونفره با کمد کافی است",
    )

    structure = _structure(project_id) or {}

    required = structure.get("required_elements") or []

    return _check(
        "T4b. a conditional statement never lands in required_elements "
        "(brief rule 2: observation, rule and dependency stay apart)",
        "bed" not in required and "wardrobe" not in required,
        {"required": required},
    )


# ==========================================================
# TEST 5 — NO HALLUCINATION
# ==========================================================

def test_5_an_unknown_property_is_not_invented():

    project_id = _project()

    _record(project_id, "اتاق خواب مستر باید همیشه ارغوانی باشد")

    structure = _structure(project_id) or {}

    uncertainties = [
        entry.get("statement")
        for entry in structure.get("uncertainties") or []
    ]

    return _check(
        "T5. an unstructurable statement goes to uncertainties, and no "
        "field is invented for it",
        "اتاق خواب مستر باید همیشه ارغوانی باشد" in uncertainties
        and not structure.get("required_elements")
        and not structure.get("optional_elements")
        and not structure.get("design_rules")
        and not structure.get("users")
        and not structure.get("primary_goals"),
        {
            "uncertainties": uncertainties,
            "required": structure.get("required_elements"),
            "rules": structure.get("design_rules"),
        },
    )


def test_5b_nothing_is_learned_promoted_or_rendered():

    project_id = _project()

    _record(project_id, "اتاق خواب مستر برای والدین هست",
            knowledge_class="DEFINITION")

    structure = _structure(project_id) or {}

    return _check(
        "T5b. the layer is read-only: no learning, no promotion, no "
        "curriculum / memory / corpus change, no LLM, no render",
        structure.get("is_knowledge") is False
        and structure.get("learned_anything") is False
        and structure.get("permanent_learning_implemented") is False
        and structure.get("promoted") is False
        and structure.get("curriculum_modified") is False
        and structure.get("architecture_rules_modified") is False
        and structure.get("teaching_memory_modified") is False
        and structure.get("llm_used") is False
        and structure.get("network_used") is False
        and structure.get("render_requested") is False
        and structure.get("comfy_invoked") is False,
        {
            "learned": structure.get("learned_anything"),
            "promoted": structure.get("promoted"),
        },
    )


def test_5c_the_store_is_untouched():

    project_id = _project()

    _record(project_id, "اتاق خواب مستر برای والدین هست",
            knowledge_class="DEFINITION")

    before = json.dumps(
        teaching_candidate_store.candidates(project_id),
        ensure_ascii=False, sort_keys=True, default=str,
    )

    _structure(project_id)

    after = json.dumps(
        teaching_candidate_store.candidates(project_id),
        ensure_ascii=False, sort_keys=True, default=str,
    )

    return _check(
        "T5c. structuring rewrites NOTHING in the teaching store",
        before == after
        and len(teaching_candidate_store.candidates(project_id)) == 1,
        {"count": len(teaching_candidate_store.candidates(project_id))},
    )


# ==========================================================
# THE CONTRACT ITSELF
# ==========================================================

def test_the_contract_shape_is_exact():

    project_id = _project()

    _record(project_id, "اتاق خواب مستر برای والدین هست",
            knowledge_class="DEFINITION")

    structure = _structure(project_id) or {}

    missing = [key for key in REQUIRED_KEYS if key not in structure]

    relations = structure.get("spatial_relations") or {}

    return _check(
        "C1. the output contract has every key the brief pins, with the "
        "right types",
        structure.get("contract") == CONTRACT
        and not missing
        and isinstance(structure.get("users"), list)
        and isinstance(structure.get("primary_goals"), list)
        and isinstance(structure.get("required_elements"), list)
        and isinstance(structure.get("optional_elements"), list)
        and isinstance(structure.get("design_rules"), list)
        and isinstance(structure.get("size_dependency"), list)
        and isinstance(structure.get("uncertainties"), list)
        and isinstance(relations.get("near"), list)
        and isinstance(relations.get("avoid"), list)
        and structure.get("provenance") == "HUMAN_TEACHER",
        {"missing": missing, "contract": structure.get("contract")},
    )


def test_every_field_records_which_layer_produced_it():

    project_id = _project()

    _record(project_id, "اتاق خواب مستر برای والدین هست",
            knowledge_class="DEFINITION")

    structure = _structure(project_id) or {}

    sources = structure.get("field_sources") or {}

    return _check(
        "C2. every populated field says whether it came from the TEACHER "
        "or from the frozen CORPUS",
        sources.get("definition") == "HUMAN_TEACHER"
        and sources.get("users") == "HUMAN_TEACHER"
        and sources.get("privacy_level") == "CORPUS"
        and sources.get("space_category") in ("HUMAN_TEACHER", "CORPUS"),
        {"field_sources": sources},
    )


def test_the_space_id_is_the_frozen_corpus_id():

    project_id = _project()

    _record(project_id, "اتاق خواب مستر برای والدین هست",
            knowledge_class="DEFINITION")

    structure = _structure(project_id) or {}

    return _check(
        "C3. the space id is the frozen corpus id (MASTER_BEDROOM_SLEEPING), "
        "never a new identifier",
        structure.get("space_id") == MASTER
        and structure.get("space_category") == "private"
        and structure.get("privacy_level") == "private",
        {
            "space_id": structure.get("space_id"),
            "category": structure.get("space_category"),
        },
    )


def test_a_rule_about_another_space_never_enters_the_structure():

    project_id = _project()

    _record(
        project_id,
        "تخت دور از پنجره باشه بهتره ، نشیمن هم باید پنجره داشته باشه",
        knowledge_class="DESIGN_RULE",
    )

    structure = _structure(project_id) or {}

    rendered = render_structured_answer(structure, "fa")

    return _check(
        "C4. the subject-scope rule of the previous phase still holds: a "
        "living-area rule does not appear in the master-bedroom structure",
        "نشیمن هم باید پنجره داشته باشه" not in rendered
        and "window" not in (structure.get("required_elements") or []),
        {
            "rendered": rendered[:400],
            "required": structure.get("required_elements"),
        },
    )


def test_an_untaught_space_returns_none():

    project_id = _project()

    _record(project_id, "اتاق خواب مستر برای والدین هست",
            knowledge_class="DEFINITION")

    structure = structure_space_knowledge(
        project_id=project_id,
        space_id="KITCHEN",
        language="fa",
    )

    return _check(
        "C5. a space with no recorded teaching returns None, so the "
        "caller keeps its existing behaviour",
        structure is None,
        {"structure": structure},
    )


def test_without_the_corpus_the_teacher_owns_everything():

    project_id = _project()

    _record(project_id, "اتاق خواب مستر برای والدین هست",
            knowledge_class="DEFINITION")

    structure = _structure(project_id, include_corpus=False) or {}

    relations = structure.get("spatial_relations") or {}

    return _check(
        "C6. with include_corpus=False the structure is built ONLY from "
        "the teacher (brief: this layer structures HUMAN_TEACHER "
        "knowledge)",
        not relations.get("near")
        and not relations.get("avoid")
        and not structure.get("privacy_level")
        and "parents" in (structure.get("users") or []),
        {
            "near": relations.get("near"),
            "privacy_level": structure.get("privacy_level"),
            "users": structure.get("users"),
        },
    )


# ==========================================================
# THE ANSWER STYLE
# ==========================================================

def test_the_rendered_answer_follows_the_brief_style():

    project_id = _project()

    _record(
        project_id,
        "اتاق خواب مستر برای والدین هست",
        knowledge_class="DEFINITION",
    )

    _record(project_id, "در باز شود دید به تخت نداشته باشد")

    _record(project_id, "اتاق خواب مستر باید همیشه ارغوانی باشد")

    structure = _structure(project_id) or {}

    rendered = render_structured_answer(structure, "fa")

    return _check(
        "R1. the rendered answer opens with the taught structure and ends "
        "with what is NOT yet a definitive rule — and never prints 'None'",
        rendered.startswith("بر اساس آموزش‌های دریافت‌شده")
        and "والدین" in rendered
        and "مواردی که هنوز" in rendered
        and "ارغوانی" in rendered
        and "None" not in rendered,
        {"rendered": rendered[:500]},
    )


def test_the_english_rendering_is_english():

    project_id = _project()

    _record(
        project_id,
        "اتاق خواب مستر برای والدین هست",
        knowledge_class="DEFINITION",
    )

    _record(project_id, "در باز شود دید به تخت نداشته باشد")

    structure = _structure(project_id) or {}

    rendered = render_structured_answer(structure, "en")

    return _check(
        "R2. the English rendering uses the corpus's English space name "
        "and English labels",
        rendered.startswith("From what you have taught me")
        and "Master Bedroom Sleeping" in rendered
        and "parents" in rendered
        and "None" not in rendered,
        {"rendered": rendered[:400]},
    )


def test_an_empty_structure_renders_nothing():

    return _check(
        "R3. nothing to render -> empty text (never a bare header)",
        render_structured_answer(None, "fa") == ""
        and render_structured_answer({}, "fa") == "",
        {},
    )


# ==========================================================
# RUNNER
# ==========================================================

def main():

    print("\n" + "=" * 70)
    print("ARCHITECTURAL_KNOWLEDGE_STRUCTURER_V1 — CONTRACT TESTS")
    print("=" * 70)

    tests = [
        test_1_master_bedroom_users_contain_parents,
        test_1b_the_user_is_reported_with_its_source,
        test_1c_a_contrasting_room_does_not_become_a_user,
        test_2_privacy_rule_is_structured,
        test_2b_the_rule_keeps_its_source,
        test_3_window_correction,
        test_3b_an_implied_element_says_it_is_implied,
        test_4_area_dependency,
        test_4b_a_dependency_is_not_a_law,
        test_5_an_unknown_property_is_not_invented,
        test_5b_nothing_is_learned_promoted_or_rendered,
        test_5c_the_store_is_untouched,
        test_the_contract_shape_is_exact,
        test_every_field_records_which_layer_produced_it,
        test_the_space_id_is_the_frozen_corpus_id,
        test_a_rule_about_another_space_never_enters_the_structure,
        test_an_untaught_space_returns_none,
        test_without_the_corpus_the_teacher_owns_everything,
        test_the_rendered_answer_follows_the_brief_style,
        test_the_english_rendering_is_english,
        test_an_empty_structure_renders_nothing,
    ]

    for test in tests:

        try:

            test()

        except Exception as error:

            _check(
                test.__name__ + " (raised)",
                False,
                "%s: %s" % (type(error).__name__, error),
            )

    failed = [item for item in _RESULTS if not item[1]]

    for name, passed, detail in _RESULTS:

        print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

        if not passed:

            print(
                "        ",
                json.dumps(detail, ensure_ascii=False, default=str)[:700],
            )

    print("-" * 70)
    print("  %d/%d PASS" % (len(_RESULTS) - len(failed), len(_RESULTS)))
    print("=" * 70 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())


# ==========================================================
# CANDIDATE-TO-STRUCTURE V1 — NEW TRANSIENT CONTRACT TESTS
# ==========================================================


def _candidate_v1():
    interpretation = interpret_architectural_vision(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["bed visible", "wardrobe visible", "bathroom visible"],
            "inferred": [],
            "unresolved": [],
            "confidence": "MEDIUM",
            "architectural_elements": ["bed", "wardrobe", "bathroom"],
        }
    )
    return build_architectural_knowledge_candidate_v1(
        interpretation["architectural_understanding_v2"]
    )


def test_candidate_structure_contract_and_shape():
    structure = build_architectural_knowledge_structure_v1(_candidate_v1())

    assert structure["contract"] == "ArchitecturalKnowledgeStructureV1"
    assert structure["version"] == "1.0"
    assert isinstance(structure["patterns"], list)
    assert isinstance(structure["space_models"], list)
    assert isinstance(structure["element_models"], list)
    assert isinstance(structure["relationship_models"], list)
    assert structure["is_training_ready"] is True
    assert structure["persistent"] is False


def test_candidate_structure_preserves_patterns_and_associations():
    structure = build_architectural_knowledge_structure_v1(_candidate_v1())

    assert {item["pattern"] for item in structure["patterns"]} == {
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    }
    assert all(item["status"] == "observed_pattern" for item in structure["patterns"])
    assert {item["element"] for item in structure["element_models"]} == {
        "wardrobe_or_closet",
        "bathroom_or_ensuite",
    }
    assert all(
        item["evidence_reference"]
        for item in structure["element_models"]
    )


def test_candidate_structure_preserves_evidence_claims_and_uncertainty():
    candidate = _candidate_v1()
    structure = build_architectural_knowledge_structure_v1(candidate)

    evidence = structure["evidence_basis"]
    chain = candidate["evidence_chain"]
    assert evidence["source_contract"] == "ArchitecturalUnderstandingV2"
    assert evidence["source_version"] == "2.0"
    assert evidence["claim_ids"] == chain["claim_ids"]
    assert evidence["source_evidence"] == chain["source_evidence"]
    assert evidence["grounding_status"] == chain["grounding_status"]
    assert evidence["interpretation_basis"] == chain["interpretation_basis"]
    assert structure["uncertainty"]["unknowns"] == candidate["uncertainty"]["unknowns"]

    for model in (
        structure["patterns"]
        + structure["space_models"]
        + structure["element_models"]
        + structure["relationship_models"]
    ):
        assert model["source_claim_ids"]
        assert model["evidence_reference"]


def test_candidate_structure_has_no_promotion_or_design_semantics():
    structure = build_architectural_knowledge_structure_v1(_candidate_v1())
    payload = {
        key: value
        for key, value in structure.items()
        if key != "non_claims"
    }
    text = str(payload).lower()

    assert structure["non_claims"] == [
        "not_design_rule",
        "not_permanent_knowledge",
        "not_memory",
        "not_geometry",
    ]
    assert "design_rule" not in text
    assert "should" not in text
    assert "must" not in text
    assert "recommended" not in text
    assert "optimal" not in text
    assert "best" not in text
    assert "promotion" not in text
    assert "persistent" in structure and structure["persistent"] is False


def test_candidate_structure_validates_candidate_only_and_is_deterministic():
    candidate = _candidate_v1()
    first = build_architectural_knowledge_structure_v1(candidate)
    second = build_architectural_knowledge_structure_v1(candidate)

    assert first == second
    with pytest.raises(TypeError):
        build_architectural_knowledge_structure_v1(None)
    with pytest.raises(ValueError):
        build_architectural_knowledge_structure_v1(
            {"contract": "ArchitecturalUnderstandingV2", "version": "2.0"}
        )
