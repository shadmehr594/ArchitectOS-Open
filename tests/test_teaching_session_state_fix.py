# ==========================================================
# TEACHING SESSION STATE — CONTRACT TESTS
#
# Covers the TEACHING SESSION STATE FIX.
#
# Two defects were reported from a real interaction:
#
#   1. "می‌خواهم اولین درس معماری را شروع کنم. موضوع: اتاق خواب. قبل از
#      اینکه من چیزی آموزش بدهم، بگو برداشت فعلی تو از این فضا چیست؟"
#      was classified OFFER_TO_TEACH and answered with the elicitation.
#      The user was NOT teaching yet — they asked for a BASELINE
#      statement of what ArchitectOS already knows.
#
#   2. "بگو برداشت فعلی تو از این فضا چیست ...؟" was answered from the
#      TEACHING-CANDIDATE store:
#        "در این پروژه هنوز جملهٔ آموزشی ... ثبت نشده است"
#      which is wrong: the user did not ask about previous teaching.
#
# The fix adds a READ-ONLY knowledge-reflection intent that states what
# the existing corpus already contains, and makes the teach-back empty
# message DISTINGUISH "nothing recorded from you" from "no architectural
# knowledge at all".
#
# SCOPE: nothing is created, stored, promoted or started.
#   - no candidate, no teaching storage, no knowledge promotion
#   - no lesson, no curriculum change, no render, no geometry/BIM/IFC
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_teaching_session_state_fix.py
#   .venv/Scripts/python.exe tests/test_teaching_session_state_fix.py
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
    tempfile.gettempdir(), "architectos_teaching_session_state"
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

from core.conversation.knowledge_reflection_v1 import (  # noqa: E402
    knowledge_reflection,
)

from core.conversation.turn_semantics_v1 import (  # noqa: E402
    classify_turn,
    extract_features,
    TURN_KNOWLEDGE_REFLECTION,
    TURN_OFFER_TO_TEACH,
    TURN_TEACHING_STATEMENT,
    TURN_CONFIRMATION_REQUEST,
    TURN_QUESTION,
)

from core.conversation.execution_boundary_v1 import (  # noqa: E402
    capability_for_turn,
    CAP_RECALL,
)

from core.conversation.teaching_candidate_v1 import (  # noqa: E402
    PERMANENT_LEARNING_IMPLEMENTED,
)

from core.conversation.knowledge_promotion_bridge_v1 import (  # noqa: E402
    PROMOTION_IMPLEMENTED,
)

from core.conversation.teach_back_v1 import (  # noqa: E402
    build_acknowledgement,
    build_teach_back,
)

from core.curriculum.curriculum_sequencer_v1 import (  # noqa: E402
    LESSONS,
)


# ----------------------------------------------------------
# THE EXACT MESSAGES FROM THE BUG REPORT
# ----------------------------------------------------------

MSG_M1 = (
    "می‌خواهم اولین درس معماری را شروع کنم. موضوع: اتاق خواب. "
    "قبل از اینکه من چیزی آموزش بدهم، بگو برداشت فعلی تو از این فضا "
    "چیست و چه چیزهایی درباره آن می‌دانی؟"
)

MSG_M2 = (
    "بگو برداشت فعلی تو از این فضا چیست و چه چیزهایی درباره آن "
    "می‌دانی؟"
)

MSG_A = "برداشت فعلی تو از اتاق خواب چیست؟"

MSG_B = "می‌خواهم اتاق خواب را به تو آموزش بدهم"

MSG_C = "اتاق خواب فضای خصوصی است"

# Negative controls — these must NOT be captured as reflection.
MSG_N1 = "چه چیزهایی برای اتاق خواب لازم است؟"

MSG_N2 = "برداشت من این است که اتاق خواب خصوصی است"

MSG_TEACH_BACK = "چه فهمیدی؟"


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))

    return bool(passed)


def _project():

    manifest = project_workspace.create("Teaching Session State")

    return manifest.get("project_id") or (
        manifest.get("project") or {}
    ).get("project_id")


def _observe(text, project_id=None):

    return teaching_foundation.observe_turn(
        session_id=project_id or _project(),
        text=text,
        input_type="typed",
    )


def _turn(text, project_id=None):

    observation = _observe(text, project_id=project_id)

    response = observation.get("response") or {}

    return (
        observation,
        response,
        response.get("teaching") or {},
        response.get("result") or "",
    )


# ==========================================================
# AUDIT — the reflection intent exists and is read-only
# ==========================================================

def test_a_is_a_knowledge_reflection_not_a_teaching_offer():

    observation, _response, teaching, _text = _turn(MSG_A)

    return _check(
        "TS-1 MSG A -> KNOWLEDGE_REFLECTION (not OFFER_TO_TEACH, "
        "not CONFIRMATION_REQUEST)",
        observation.get("turn_kind") == TURN_KNOWLEDGE_REFLECTION
        and teaching.get("action") == "reflect_existing_knowledge",
        {
            "turn_kind": observation.get("turn_kind"),
            "action": teaching.get("action"),
        },
    )


def test_reflection_capability_is_read_only_recall():

    return _check(
        "TS-2 reflection capability is RECALL (read-only, never EXECUTE)",
        capability_for_turn(TURN_KNOWLEDGE_REFLECTION) == CAP_RECALL,
        {"capability": capability_for_turn(TURN_KNOWLEDGE_REFLECTION)},
    )


def test_reflection_states_the_existing_corpus_knowledge():

    _observation, _response, teaching, text = _turn(MSG_A)

    return _check(
        "TS-3 MSG A states the EXISTING corpus knowledge for the space",
        "\u0628\u0631\u062f\u0627\u0634\u062a \u0641\u0639\u0644\u06cc \u0645\u0646 \u0627\u0632"
        in text
        and teaching.get("space_id") == "BEDROOM_DOUBLE"
        and teaching.get("has_existing_knowledge") is True,
        {
            "space_id": teaching.get("space_id"),
            "has_existing_knowledge": teaching.get("has_existing_knowledge"),
            "lead": text.split("\n")[0],
        },
    )


def test_reflection_creates_nothing():

    observation, response, teaching, _text = _turn(MSG_A)

    return _check(
        "TS-4 MSG A creates no candidate, learns nothing, renders nothing",
        teaching.get("candidate") is None
        and teaching.get("permanent_learning") is False
        and teaching.get("lesson_started") is False
        and teaching.get("read_only") is True
        and response.get("render_requested") is False
        and observation.get("candidate") is None,
        {
            "candidate": teaching.get("candidate"),
            "permanent_learning": teaching.get("permanent_learning"),
            "render_requested": response.get("render_requested"),
        },
    )


def test_reflection_module_reports_read_only():

    report = knowledge_reflection.report()

    return _check(
        "TS-5 reflection module declares read-only, no writes, no lesson",
        report["read_only"] is True
        and report["writes_performed"] is False
        and report["creates_candidate"] is False
        and report["stores_teaching"] is False
        and report["promotes_knowledge"] is False
        and report["starts_lesson"] is False
        and report["touches_curriculum"] is False
        and report["renders"] is False
        and report["corpus_space_count"] > 0,
        report,
    )


# ==========================================================
# The two messages from the report
# ==========================================================

def test_mixed_message_does_not_enter_the_elicitation_flow():

    observation, _response, teaching, _text = _turn(MSG_M1)

    return _check(
        "TS-6 M1 (mixed: 'می‌خواهم درس را شروع کنم' + 'برداشت فعلی تو "
        "چیست؟') -> KNOWLEDGE_REFLECTION, NOT the elicitation",
        observation.get("turn_kind") == TURN_KNOWLEDGE_REFLECTION
        and teaching.get("action") == "reflect_existing_knowledge"
        and teaching.get("user_as_teacher") is None,
        {
            "turn_kind": observation.get("turn_kind"),
            "action": teaching.get("action"),
        },
    )


def test_m1_still_resolves_the_named_space():

    _observation, _response, teaching, _text = _turn(MSG_M1)

    return _check(
        "TS-7 M1 still resolves the named space (اتاق خواب)",
        teaching.get("space_id") == "BEDROOM_DOUBLE",
        {"space_id": teaching.get("space_id")},
    )


def test_second_message_is_a_reflection_not_a_teach_back():

    observation, _response, teaching, text = _turn(MSG_M2)

    return _check(
        "TS-8 M2 -> KNOWLEDGE_REFLECTION (not the candidate store)",
        observation.get("turn_kind") == TURN_KNOWLEDGE_REFLECTION
        and "\u062c\u0645\u0644\u0647\u0654 \u0622\u0645\u0648\u0632\u0634\u06cc"
        not in text,
        {
            "turn_kind": observation.get("turn_kind"),
            "lead": text.split("\n")[0],
        },
    )


def test_reflection_without_a_named_space_reports_the_inventory():

    _observation, _response, teaching, text = _turn(MSG_M2)

    return _check(
        "TS-9 a topic-less reflection reports the corpus inventory instead "
        "of claiming ignorance",
        teaching.get("has_existing_knowledge") is False
        and "\u06af\u0648\u0646\u0647\u0654 \u0641\u0636\u0627" in text,
        {"text": text[:200]},
    )


# ==========================================================
# The teach-back fallback must distinguish the two cases
# ==========================================================

def test_teach_back_empty_distinguishes_user_statements_from_knowledge():

    project_id = _project()

    teach_back = build_teach_back(
        project_id=project_id, language="fa",
        store=teaching_foundation.store,
    )

    result = teach_back.get("result") or ""

    return _check(
        "TS-10 teach-back empty message distinguishes 'nothing from YOU' "
        "from the existing architectural knowledge",
        "\u062c\u0645\u0644\u0647\u0654 \u0622\u0645\u0648\u0632\u0634\u06cc"
        in result
        and "\u062f\u0627\u0646\u0634 \u0645\u0639\u0645\u0627\u0631\u06cc \u0645\u0648\u062c\u0648\u062f"
        in result
        and "\u0628\u0631\u062f\u0627\u0634\u062a \u0641\u0639\u0644\u06cc \u062a\u0648"
        in result,
        {"result": result},
    )


def test_teach_back_is_still_reachable_for_a_real_teach_back_question():

    observation = _observe(MSG_TEACH_BACK)

    return _check(
        "TS-11 'چه فهمیدی؟' is still a CONFIRMATION_REQUEST (teach-back)",
        observation.get("turn_kind") == TURN_CONFIRMATION_REQUEST,
        {"turn_kind": observation.get("turn_kind")},
    )


# ==========================================================
# NOTHING ELSE MOVED
# ==========================================================

def test_teaching_offer_is_unchanged():

    observation, _response, teaching, _text = _turn(MSG_B)

    return _check(
        "TS-12 MSG B is still OFFER_TO_TEACH + elicitation + "
        "user_as_teacher",
        observation.get("turn_kind") == TURN_OFFER_TO_TEACH
        and teaching.get("action") == "elicit_teaching_aspect"
        and teaching.get("user_as_teacher") is True,
        {
            "turn_kind": observation.get("turn_kind"),
            "action": teaching.get("action"),
        },
    )


def test_teaching_statement_is_unchanged():

    observation, _response, teaching, _text = _turn(MSG_C)

    return _check(
        "TS-13 MSG C is still TEACHING_STATEMENT with a candidate",
        observation.get("turn_kind") == TURN_TEACHING_STATEMENT
        and teaching.get("action") == "record_teaching_statement"
        and teaching.get("candidate") is not None
        and teaching.get("permanent_learning") is False,
        {
            "turn_kind": observation.get("turn_kind"),
            "candidate": bool(teaching.get("candidate")),
        },
    )


def test_negative_controls_are_not_captured_as_reflection():

    n1 = classify_turn(MSG_N1).get("turn_kind")
    n2 = classify_turn(MSG_N2).get("turn_kind")

    return _check(
        "TS-14 negative controls are NOT reflection "
        "(ordinary question + ordinary statement)",
        n1 == TURN_QUESTION and n2 == TURN_TEACHING_STATEMENT,
        {"N1": n1, "N2": n2},
    )


def test_reflection_markers_require_two_parts_where_it_matters():

    f1 = extract_features(MSG_N1)

    f2 = extract_features(MSG_N2)

    f3 = extract_features(MSG_A)

    return _check(
        "TS-15 a bare opener / bare 'برداشت' does not trigger reflection",
        f1.get("knowledge_reflection") is False
        and f2.get("knowledge_reflection") is False
        and f3.get("knowledge_reflection") is True,
        {
            "N1": f1.get("knowledge_reflection"),
            "N2": f2.get("knowledge_reflection"),
            "A": f3.get("knowledge_reflection"),
        },
    )


def test_non_persisted_candidate_no_longer_crashes():

    """The build_acknowledgement AttributeError, fixed in the same pass."""

    from core.conversation.teaching_candidate_v1 import (
        TeachingCandidate,
    )

    candidate = TeachingCandidate(
        raw_statement="اتاق خواب فضای خصوصی است",
        project_id=None,
        source_turn_id="t",
    )

    try:

        result = build_acknowledgement(
            TURN_TEACHING_STATEMENT,
            meaning=None,
            language="fa",
            candidate=candidate,
        )

        ok = isinstance(result, str) and bool(result)

        error = None

    except Exception as caught:

        ok = False

        error = type(caught).__name__ + ": " + str(caught)

    return _check(
        "TS-16 a NON-persisted TeachingCandidate object no longer raises "
        "AttributeError",
        ok,
        {"error": error},
    )


def test_nothing_was_learned_or_promoted_and_curriculum_not_started():

    project_id = _project()

    _observe(MSG_A, project_id=project_id)

    _observe(MSG_B, project_id=project_id)

    _observe(MSG_C, project_id=project_id)

    return _check(
        "TS-17 no permanent learning, no promotion, curriculum NOT started",
        PERMANENT_LEARNING_IMPLEMENTED is False
        and PROMOTION_IMPLEMENTED is False
        and teaching_foundation.learned_count(project_id) == 0
        and len(LESSONS) == 0,
        {
            "learned_count": teaching_foundation.learned_count(project_id),
            "lessons": LESSONS,
            "promotion": PROMOTION_IMPLEMENTED,
        },
    )


# ==========================================================
# RUNNER
# ==========================================================

def main():

    print("\n" + "=" * 70)
    print("TEACHING SESSION STATE — CONTRACT TESTS")
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
                json.dumps(detail, ensure_ascii=False, default=str)[:420],
            )

    print("-" * 70)
    print("  %d/%d PASS" % (len(_RESULTS) - len(failed), len(_RESULTS)))
    print("=" * 70 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())
