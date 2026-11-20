# ==========================================================
# TEACHING_QUESTION_RETRIEVAL — CONTRACT / ACCEPTANCE TESTS
#
# Before this fix, a QUESTION about a taught space bypassed the teaching
# store and went straight to the LLM. Measured on a real session:
#
#   teacher : "اتاق خواب مستر برای والدین هست"
#   question: "اتاق خواب مستر برای چه افرادی در خانه استفاده میشه؟"
#   LLM     : "برای خانواده ها و کسانی که می خواهند یک اتاق خواب آرام و
#              comfy داشته باشند"          <-- contradicts the teaching
#
# The fix adds a retrieval path for QUESTION turns ONLY:
#   - detect the referenced architectural space (corpus scanner)
#   - search teaching candidates by `space_topic`
#   - if HUMAN_TEACHER observed knowledge exists -> answer from it,
#     with provenance and uncertainty
#   - never invent anything
#   - if NO teaching knowledge exists -> keep the existing LLM behaviour
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_teaching_question_retrieval.py
#   .venv/Scripts/python.exe tests/test_teaching_question_retrieval.py
# ==========================================================


import json
import os
import sys
import tempfile


ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if ROOT not in sys.path:

    sys.path.insert(0, ROOT)


_TEMP_ROOT = os.path.join(
    tempfile.gettempdir(), "architectos_question_retrieval"
)

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = _TEMP_ROOT

os.environ.setdefault(
    "ARCHITECTOS_PROJECTS_ROOT", os.path.join(_TEMP_ROOT, "projects")
)

os.environ.setdefault(
    "ARCHITECTOS_PROJECT_TRASH_ROOT", os.path.join(_TEMP_ROOT, "trash")
)

# Render-stop guard: acceptance must never reach ComfyUI.
os.environ["ARCHITECTOS_COMFY_PORT"] = "9"


from core.project.project_workspace_v1 import project_workspace  # noqa: E402

project_workspace.projects_root = os.path.join(_TEMP_ROOT, "projects")

project_workspace.trash_root = os.path.join(_TEMP_ROOT, "trash")

os.makedirs(project_workspace.projects_root, exist_ok=True)

os.makedirs(project_workspace.trash_root, exist_ok=True)


from core.conversation.teaching_foundation_v1 import (  # noqa: E402
    teaching_foundation,
)

from core.conversation.teach_back_v1 import (  # noqa: E402
    build_grounded_answer,
)

from core.conversation.teaching_candidate_v1 import (  # noqa: E402
    teaching_candidate_store,
    PERMANENT_LEARNING_IMPLEMENTED,
)

from core.conversation.knowledge_promotion_bridge_v1 import (  # noqa: E402
    PROMOTION_IMPLEMENTED,
)

from core.conversation.turn_semantics_v1 import (  # noqa: E402
    classify_turn,
    TURN_QUESTION,
)

from core.curriculum.curriculum_sequencer_v1 import (  # noqa: E402
    LESSONS,
)


# ----------------------------------------------------------
# THE EXACT MESSAGES
# ----------------------------------------------------------

TEACHING = "اتاق خواب مستر برای والدین هست"

QUESTION_WHO = "اتاق خواب مستر برای چه افرادی در خانه استفاده میشه؟"

# A master-bedroom property that was never taught.
QUESTION_UNTAUGHT = "رنگ دیوارهای اتاق خواب مستر چیست؟"

# A question about a space with NO teaching history at all.
QUESTION_OTHER_SPACE = "نشیمن برای چه کسانی است؟"

# A plain question with no architectural space.
QUESTION_PLAIN = "امروز هوا خوبه؟"


MASTER = "MASTER_BEDROOM_SLEEPING"


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))

    return bool(passed)


def _project():

    manifest = project_workspace.create("Question Retrieval")

    return manifest.get("project_id") or (
        manifest.get("project") or {}
    ).get("project_id")


def _turn(text, project_id):

    observation = teaching_foundation.observe_turn(
        session_id=project_id,
        text=text,
        context={"session_id": project_id},
        input_type="typed",
    )

    response = observation.get("response") or {}

    return observation, response, (response.get("teaching") or {})


def _teach_master(project_id):

    return _turn(TEACHING, project_id)


# ==========================================================
# 1. MASTER_BEDROOM + parent statement -> answer parents
# ==========================================================

def test_question_is_answered_from_the_teaching_memory():

    project_id = _project()

    _teach_master(project_id)

    observation, response, teaching = _turn(QUESTION_WHO, project_id)

    return _check(
        "Q1. the question is answered by the TEACHING layer, not the LLM",
        observation.get("turn_kind") == TURN_QUESTION
        and observation.get("short_circuit") is True
        and teaching.get("action") == "answer_from_teaching_memory"
        and response.get("engine") == "architectos_turn_semantics",
        {
            "turn_kind": observation.get("turn_kind"),
            "action": teaching.get("action"),
            "engine": response.get("engine"),
        },
    )


def test_answer_contains_the_taught_parents_statement():

    project_id = _project()

    _teach_master(project_id)

    _observation, _response, teaching = _turn(QUESTION_WHO, project_id)

    text = (teaching.get("grounded_answer") or {}).get("result") or ""

    return _check(
        "Q2. the answer states the taught content (والدین / parents)",
        "والدین" in text
        and "اتاق خواب مستر برای والدین هست" in text
        and teaching.get("space_topic") == MASTER,
        {
            "space_topic": teaching.get("space_topic"),
            "text": text,
        },
    )


def test_answer_includes_provenance_and_uncertainty():

    project_id = _project()

    _teach_master(project_id)

    _observation, _response, teaching = _turn(QUESTION_WHO, project_id)

    grounded = teaching.get("grounded_answer") or {}

    text = grounded.get("result") or ""

    return _check(
        "Q3. the answer carries provenance AND uncertainty",
        grounded.get("provenance") == "HUMAN_TEACHER"
        and grounded.get("source") == "TEACHING_CANDIDATE_STORE"
        and "مدرس انسانی" in text
        and "دریافت‌شده" in text
        and "دانش دائمی" in text
        and grounded.get("learned_anything") is False
        and grounded.get("candidate_created") is False,
        {
            "provenance": grounded.get("provenance"),
            "source": grounded.get("source"),
        },
    )


def test_answering_a_question_creates_nothing():

    project_id = _project()

    _teach_master(project_id)

    before = len(teaching_candidate_store.candidates(project_id))

    observation, response, teaching = _turn(QUESTION_WHO, project_id)

    after = len(teaching_candidate_store.candidates(project_id))

    return _check(
        "Q4. answering creates no candidate, learns nothing, renders nothing",
        before == after
        and observation.get("candidate") is None
        and teaching.get("candidate") is None
        and teaching.get("permanent_learning") is False
        and response.get("render_requested") is False
        and teaching.get("llm_used") is False,
        {
            "candidates_before": before,
            "candidates_after": after,
            "candidate": teaching.get("candidate"),
        },
    )


# ==========================================================
# 2. Unknown master-bedroom property -> say not taught
# ==========================================================

def test_an_untaught_property_is_not_invented():

    project_id = _project()

    _teach_master(project_id)

    observation, response, teaching = _turn(QUESTION_UNTAUGHT, project_id)

    grounded = teaching.get("grounded_answer") or {}

    text = grounded.get("result") or ""

    return _check(
        "Q5. an untaught property is answered with 'not taught', never "
        "invented",
        observation.get("short_circuit") is True
        and teaching.get("action") == "answer_from_teaching_memory"
        and "یاد نگرفته‌ام" in text
        # the recorded knowledge is still reported honestly
        and "والدین" in text,
        {
            "action": teaching.get("action"),
            "text": text,
        },
    )


def test_the_builder_returns_none_for_an_untaught_space():

    project_id = _project()

    _teach_master(project_id)

    return _check(
        "Q6. build_grounded_answer returns None when the space has no "
        "recorded teaching",
        build_grounded_answer(
            project_id=project_id,
            space_topic="LIVING_RECEPTION",
            language="fa",
            store=teaching_candidate_store,
        )
        is None,
        {"space_topic": "LIVING_RECEPTION"},
    )


# ==========================================================
# 3. Normal questions unaffected
# ==========================================================

def test_a_question_about_an_untaught_space_keeps_the_llm_path():

    project_id = _project()

    _teach_master(project_id)

    observation, _response, teaching = _turn(
        QUESTION_OTHER_SPACE, project_id
    )

    return _check(
        "Q7. a question about a space with NO teaching keeps the existing "
        "LLM path (no short-circuit)",
        observation.get("turn_kind") == TURN_QUESTION
        and observation.get("short_circuit") is False
        and teaching.get("action") is None,
        {
            "turn_kind": observation.get("turn_kind"),
            "short_circuit": observation.get("short_circuit"),
            "action": teaching.get("action"),
        },
    )


def test_a_plain_question_in_a_project_without_teaching_is_unaffected():

    project_id = _project()

    observation, _response, teaching = _turn(QUESTION_PLAIN, project_id)

    return _check(
        "Q8. with no teaching history at all, questions behave exactly as "
        "before",
        observation.get("short_circuit") is False
        and teaching.get("action") is None,
        {"short_circuit": observation.get("short_circuit")},
    )


def test_a_question_with_no_space_is_unaffected_even_with_teaching():

    project_id = _project()

    _teach_master(project_id)

    observation, _response, teaching = _turn(QUESTION_PLAIN, project_id)

    return _check(
        "Q9. a question naming no space is unaffected even when teaching "
        "exists",
        observation.get("short_circuit") is False
        and teaching.get("action") is None,
        {
            "short_circuit": observation.get("short_circuit"),
            "action": teaching.get("action"),
        },
    )


# ==========================================================
# SCOPE / SAFETY
# ==========================================================

def test_the_retrieval_is_project_scoped():

    project_a = _project()

    project_b = _project()

    _teach_master(project_a)

    # Project B was taught nothing, so its question must NOT be grounded.
    observation, _response, teaching = _turn(QUESTION_WHO, project_b)

    return _check(
        "Q10. retrieval is project-scoped (no cross-project leakage)",
        observation.get("short_circuit") is False
        and teaching.get("action") is None,
        {"short_circuit": observation.get("short_circuit")},
    )


def test_rejected_knowledge_is_not_used():

    project_id = _project()

    _teach_master(project_id)

    # Reject every recorded candidate, then ask the same question again.
    payload = teaching_candidate_store.load(project_id)

    for entry in payload.get("candidates") or []:

        entry["status"] = "rejected"

    teaching_candidate_store.save(project_id, payload)

    observation, _response, teaching = _turn(QUESTION_WHO, project_id)

    return _check(
        "Q11. a REJECTED candidate is not used as teaching knowledge",
        observation.get("short_circuit") is False
        and teaching.get("action") is None,
        {
            "short_circuit": observation.get("short_circuit"),
            "action": teaching.get("action"),
        },
    )


def test_nothing_is_learned_promoted_or_lessoned():

    project_id = _project()

    _teach_master(project_id)

    _turn(QUESTION_WHO, project_id)

    _turn(QUESTION_UNTAUGHT, project_id)

    return _check(
        "Q12. no permanent learning, no promotion, curriculum NOT started",
        PERMANENT_LEARNING_IMPLEMENTED is False
        and PROMOTION_IMPLEMENTED is False
        and teaching_foundation.learned_count(project_id) == 0
        and len(LESSONS) == 0,
        {
            "learned_count": teaching_foundation.learned_count(project_id),
            "lessons": LESSONS,
        },
    )


def test_teaching_statement_behaviour_is_unchanged():

    project_id = _project()

    observation, response, teaching = _teach_master(project_id)

    return _check(
        "Q13. a teaching statement is still recorded, not learned",
        observation.get("turn_kind") == "TEACHING_STATEMENT"
        and teaching.get("action") == "record_teaching_statement"
        and teaching.get("permanent_learning") is False
        and response.get("render_requested") is False,
        {
            "turn_kind": observation.get("turn_kind"),
            "action": teaching.get("action"),
        },
    )


# ==========================================================
# RUNNER
# ==========================================================

def main():

    print("\n" + "=" * 70)
    print("TEACHING_QUESTION_RETRIEVAL — CONTRACT / ACCEPTANCE TESTS")
    print("=" * 70)

    for name, function in sorted(
        (name, value)
        for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ):

        try:

            function()

        except Exception as error:

            _check(
                name,
                False,
                {"exception": type(error).__name__ + ": " + str(error)},
            )

    failed = [item for item in _RESULTS if not item[1]]

    for name, passed, detail in _RESULTS:

        print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

        if not passed:

            print(
                "        ",
                json.dumps(detail, ensure_ascii=False, default=str)[:500],
            )

    print("-" * 70)
    print("  %d/%d PASS" % (len(_RESULTS) - len(failed), len(_RESULTS)))
    print("=" * 70 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())
