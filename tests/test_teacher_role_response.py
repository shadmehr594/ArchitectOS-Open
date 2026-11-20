# ==========================================================
# TEACHER ROLE RESPONSE — CONTRACT TESTS
#
# Covers the TEACHER ROLE RESPONSE FIX.
#
# Before the fix, "سلام میخوایم اولین جلسه آموزش معماری رو شروع کنیم"
# was classified correctly (OFFER_TO_TEACH) but PRESENTED with the
# roles inverted: the reply thanked the user for "wanting to learn"
# and then asked which aspect they wanted to TEACH.
#
# After the fix the reply presents the ROLE CONTRACT:
#   - the USER is the teacher
#   - the assistant is the learner
#   - nothing is learned automatically
#   - the system asks which concept/aspect the teacher will explain
#
# SCOPE: response wording / intent presentation ONLY.
#   - turn_kind classification is UNCHANGED (asserted below)
#   - core/conversation/turn_semantics_v1.py is NOT modified
#   - no lesson, no promotion, no curriculum, no storage change
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_teacher_role_response.py
#   .venv/Scripts/python.exe tests/test_teacher_role_response.py
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
    tempfile.gettempdir(), "architectos_teacher_role_response"
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

from core.conversation.turn_semantics_v1 import (  # noqa: E402
    extract_features,
    classify_turn,
    TURN_OFFER_TO_TEACH,
    TURN_TEACHING_STATEMENT,
)

from core.conversation.teaching_candidate_v1 import (  # noqa: E402
    PERMANENT_LEARNING_IMPLEMENTED,
)

from core.conversation.knowledge_promotion_bridge_v1 import (  # noqa: E402
    PROMOTION_IMPLEMENTED,
)

from core.curriculum.curriculum_sequencer_v1 import (  # noqa: E402
    LESSONS,
)


# ----------------------------------------------------------
# THE EXACT MESSAGES FROM THE BRIEF
# ----------------------------------------------------------

MSG_A = (
    "\u0633\u0644\u0627\u0645 \u0645\u06cc\u062e\u0648\u0627\u06cc\u0645 "
    "\u0627\u0648\u0644\u06cc\u0646 \u062c\u0644\u0633\u0647 "
    "\u0622\u0645\u0648\u0632\u0634 \u0645\u0639\u0645\u0627\u0631\u06cc "
    "\u0631\u0648 \u0634\u0631\u0648\u0639 \u06a9\u0646\u06cc\u0645"
)

MSG_B = (
    "\u0642\u0631\u0627\u0631\u0647 \u0645\u0646 \u06cc\u0627\u062f\u062a "
    "\u0628\u062f\u0645 \u0637\u0631\u0627\u062d\u06cc \u06a9\u0631\u062f\u0646 "
    "\u0631\u0648 \u0648 \u0641\u0636\u0627\u0647\u0627\u06cc "
    "\u0645\u0639\u0645\u0627\u0631\u06cc \u0631\u0648"
)

MSG_B_FULL = (
    "\u0642\u0631\u0627\u0631\u0647 \u0645\u0646 \u06cc\u0627\u062f\u062a "
    "\u0628\u062f\u0645 \u0637\u0631\u0627\u062d\u06cc \u06a9\u0631\u062f\u0646 "
    "\u0631\u0648 \u0648 \u0641\u0636\u0627\u0647\u0627\u06cc "
    "\u0645\u0639\u0645\u0627\u0631\u06cc \u0631\u0648 \u0648 \u0645\u0646 "
    "\u0627\u0632\u062a \u0645\u06cc\u200c\u067e\u0631\u0633\u0645"
)

# The brief's first example of an OFFER.
MSG_OFFER_ADDRESSEE = (
    "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645 \u0628\u0647 "
    "\u062a\u0648 \u0637\u0631\u0627\u062d\u06cc \u0645\u0639\u0645\u0627\u0631\u06cc "
    "\u06cc\u0627\u062f \u0628\u062f\u0647\u0645"
)

# An EXPLICIT learner request — the user asks to BE TAUGHT. This must
# NOT be re-roled as the teacher.
MSG_LEARN_REQUEST = (
    "\u0628\u0647 \u0645\u0646 \u0631\u0627\u0647 \u067e\u0644\u0647 "
    "\u0631\u0627 \u06cc\u0627\u062f \u0628\u062f\u0647"
)

MSG_C = (
    "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u0641\u0636\u0627\u06cc "
    "\u067e\u0631\u06cc\u0648\u06cc\u062a \u0627\u0633\u062a"
)


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))

    return bool(passed)


def _project():

    manifest = project_workspace.create("Teacher Role Response")

    return manifest.get("project_id") or (
        manifest.get("project") or {}
    ).get("project_id")


def _observe(text, project_id=None):

    return teaching_foundation.observe_turn(
        session_id=project_id or _project(),
        text=text,
        input_type="typed",
    )


def _teaching(text, project_id=None):

    observation = _observe(text, project_id=project_id)

    response = observation.get("response") or {}

    return (
        observation,
        response,
        response.get("teaching") or {},
        (response.get("teaching") or {}).get("elicitation") or {},
        response.get("result") or "",
    )


# ==========================================================
# A — the message from the bug report
# ==========================================================

def test_a_is_a_teaching_intent_and_user_is_the_teacher():

    observation, response, teaching, elicitation, text = _teaching(MSG_A)

    return _check(
        "TR-A1 MSG A: OFFER_TO_TEACH + user_as_teacher",
        observation.get("turn_kind") == TURN_OFFER_TO_TEACH
        and teaching.get("action") == "elicit_teaching_aspect"
        and teaching.get("user_as_teacher") is True
        and response.get("capability") == "UNDERSTAND",
        {
            "turn_kind": observation.get("turn_kind"),
            "action": teaching.get("action"),
            "user_as_teacher": teaching.get("user_as_teacher"),
            "direction": elicitation.get("direction"),
        },
    )


def test_a_acknowledges_the_teacher_role_and_the_learner_role():

    _observation, _response, _teaching_, _elicitation, text = _teaching(MSG_A)

    # "شما مدرس هستید" — the user is named as the teacher.
    # "من یاد می‌گیرم"  — the assistant is named as the learner.
    return _check(
        "TR-A2 MSG A: reply names the user as teacher and the assistant "
        "as learner",
        "\u0645\u062f\u0631\u0633" in text
        and "\u0645\u0646 \u06cc\u0627\u062f \u0645\u06cc\u200c\u06af\u06cc\u0631\u0645"
        in text,
        {"lead": text.split("\n")[0]},
    )


def test_a_no_longer_claims_the_user_wants_to_learn():

    _observation, _response, _teaching_, _elicitation, text = _teaching(MSG_A)

    inverted = (
        "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u06cc\u062f \u06cc\u0627\u062f "
        "\u0628\u06af\u06cc\u0631\u06cc\u062f"
    )

    return _check(
        "TR-A3 MSG A: the inverted 'you want to learn' lead is gone",
        inverted not in text,
        {"lead": text.split("\n")[0]},
    )


def test_a_still_asks_which_aspect_the_teacher_will_explain():

    _observation, _response, _teaching_, _elicitation, text = _teaching(MSG_A)

    return _check(
        "TR-A4 MSG A: still asks which aspect the teacher will explain",
        "\u06a9\u062f\u0627\u0645 \u0628\u062e\u0634" in text
        and "\u0622\u0645\u0648\u0632\u0634 \u062f\u0647\u06cc\u062f" in text,
        {"lead": text.split("\n")[1] if "\n" in text else text},
    )


def test_a_says_nothing_is_learned_automatically():

    observation, response, teaching, _elicitation, text = _teaching(MSG_A)

    return _check(
        "TR-A5 MSG A: no automatic learning",
        teaching.get("permanent_learning") is False
        and teaching.get("candidate") is None
        and response.get("render_requested") is False
        and "\u062f\u0627\u0646\u0634 \u062f\u0627\u0626\u0645\u06cc" in text,
        {
            "permanent_learning": teaching.get("permanent_learning"),
            "candidate": teaching.get("candidate"),
        },
    )


# ==========================================================
# B — the second message from the brief
# ==========================================================

def test_b_is_a_teaching_intent_and_user_is_the_teacher():

    observation, _response, teaching, elicitation, _text = _teaching(MSG_B)

    return _check(
        "TR-B1 MSG B: OFFER_TO_TEACH + user_as_teacher",
        observation.get("turn_kind") == TURN_OFFER_TO_TEACH
        and teaching.get("user_as_teacher") is True
        and teaching.get("action") == "elicit_teaching_aspect",
        {
            "turn_kind": observation.get("turn_kind"),
            "user_as_teacher": teaching.get("user_as_teacher"),
            "direction": elicitation.get("direction"),
        },
    )


def test_b_acknowledges_the_teacher_role():

    _observation, _response, _teaching_, _elicitation, text = _teaching(MSG_B)

    return _check(
        "TR-B2 MSG B: reply acknowledges the teacher role",
        "\u0645\u062f\u0631\u0633" in text
        and "\u0645\u0646 \u06cc\u0627\u062f \u0645\u06cc\u200c\u06af\u06cc\u0631\u0645"
        in text,
        {"lead": text.split("\n")[0]},
    )


def test_b_full_message_acknowledges_the_teacher_role():

    _observation, _response, teaching, _elicitation, text = _teaching(MSG_B_FULL)

    return _check(
        "TR-B3 MSG B (full long form): user_as_teacher + teacher "
        "acknowledgement",
        teaching.get("user_as_teacher") is True
        and "\u0645\u062f\u0631\u0633" in text,
        {"lead": text.split("\n")[0]},
    )


def test_brief_offer_example_is_a_teacher_offer():

    _observation, _response, teaching, _elicitation, text = _teaching(
        MSG_OFFER_ADDRESSEE
    )

    return _check(
        "TR-B4 'می‌خواهم به تو طراحی معماری یاد بدهم' -> user_as_teacher",
        teaching.get("user_as_teacher") is True
        and "\u0645\u062f\u0631\u0633" in text,
        {"user_as_teacher": teaching.get("user_as_teacher")},
    )


# ==========================================================
# The learner direction must NOT be re-roled (no regression)
# ==========================================================

def test_explicit_learner_request_is_still_a_learner_request():

    _observation, _response, teaching, elicitation, text = _teaching(
        MSG_LEARN_REQUEST
    )

    return _check(
        "TR-C1 explicit 'یاد بده' stays a LEARNER request",
        teaching.get("user_as_teacher") is False
        and teaching.get("assistant_as_learner") is False
        and elicitation.get("direction") == "user_requests_teaching",
        {
            "user_as_teacher": teaching.get("user_as_teacher"),
            "direction": elicitation.get("direction"),
            "lead": text.split("\n")[0],
        },
    )


# ==========================================================
# Contract shape
# ==========================================================

def test_role_flags_are_exposed_on_both_contracts():

    _observation, _response, teaching, elicitation, _text = _teaching(MSG_A)

    return _check(
        "TR-D1 user_as_teacher + assistant_as_learner are on BOTH the "
        "teaching block and the elicitation contract",
        teaching.get("user_as_teacher") is True
        and teaching.get("assistant_as_learner") is True
        and elicitation.get("user_as_teacher") is True
        and elicitation.get("assistant_as_learner") is True,
        {
            "teaching": {
                "user_as_teacher": teaching.get("user_as_teacher"),
                "assistant_as_learner": teaching.get("assistant_as_learner"),
            },
            "elicitation": {
                "user_as_teacher": elicitation.get("user_as_teacher"),
                "assistant_as_learner": elicitation.get("assistant_as_learner"),
            },
        },
    )


def test_english_lead_states_the_role_contract():

    _observation, _response, teaching, _elicitation, text = _teaching(MSG_A)

    english = teaching_foundation.build_response({
        "turn_id": "t",
        "turn_kind": TURN_OFFER_TO_TEACH,
        "semantics": {"features": {}},
        "candidate": None,
        "meaning": None,
        "language": "en",
        "language_decision": {},
        "session_id": None,
        "capability": "UNDERSTAND",
        "teaching_topic": None,
        "teaching_space": None,
        "teaching_diagram": None,
        "teaching_program": None,
    }).get("result") or ""

    return _check(
        "TR-D2 English lead states teacher/learner roles",
        "teacher" in english.lower() and "learner" in english.lower(),
        {"lead": english.split("\n")[0]},
    )


# ==========================================================
# SCOPE — classification and curriculum must be untouched
# ==========================================================

def test_turn_kind_classification_is_unchanged():

    a = classify_turn(MSG_A).get("turn_kind")
    b = classify_turn(MSG_B).get("turn_kind")
    c = classify_turn(MSG_C).get("turn_kind")

    return _check(
        "TR-E1 turn_kind classification UNCHANGED (A/B OFFER_TO_TEACH, "
        "C TEACHING_STATEMENT)",
        a == TURN_OFFER_TO_TEACH
        and b == TURN_OFFER_TO_TEACH
        and c == TURN_TEACHING_STATEMENT,
        {"A": a, "B": b, "C": c},
    )


def test_the_classifier_verdict_is_untouched_so_the_fix_is_presentation_only():
    """Documents the fix boundary.

    The CLASSIFIER still reports `user_requests_teaching` for MSG A —
    the fix lives entirely in the response layer and OVERRIDES that
    verdict for presentation. This test exists to prove
    core/conversation/turn_semantics_v1.py was not modified.

    If a later phase corrects the classifier itself, RELAX this test
    (assert the response outcome, not the raw verdict) — do not delete
    it.
    """

    features = extract_features(MSG_A)

    return _check(
        "TR-E2 classifier verdict untouched (fix is response-only)",
        features.get("teaching_intent") is True
        and features.get("teach_request") is False
        and features.get("teaching_intent_direction")
        == "user_requests_teaching",
        {
            "teaching_intent": features.get("teaching_intent"),
            "teach_request": features.get("teach_request"),
            "direction": features.get("teaching_intent_direction"),
        },
    )


def test_teaching_statement_still_produces_a_candidate_only():

    observation, response, teaching, _elicitation, _text = _teaching(MSG_C)

    return _check(
        "TR-E3 MSG C is still a TEACHING_STATEMENT candidate only",
        observation.get("turn_kind") == TURN_TEACHING_STATEMENT
        and teaching.get("permanent_learning") is False
        and teaching.get("candidate") is not None
        and response.get("render_requested") is False,
        {"turn_kind": observation.get("turn_kind")},
    )


def test_nothing_is_learned_or_promoted():

    project_id = _project()

    _teaching(MSG_A, project_id=project_id)

    _teaching(MSG_B, project_id=project_id)

    _teaching(MSG_C, project_id=project_id)

    return _check(
        "TR-F1 no permanent learning, no promotion",
        PERMANENT_LEARNING_IMPLEMENTED is False
        and PROMOTION_IMPLEMENTED is False
        and teaching_foundation.learned_count(project_id) == 0,
        {
            "learned_count": teaching_foundation.learned_count(project_id),
            "permanent_learning_implemented": PERMANENT_LEARNING_IMPLEMENTED,
            "promotion_implemented": PROMOTION_IMPLEMENTED,
        },
    )


def test_curriculum_is_still_not_started():

    return _check(
        "TR-F2 curriculum still NOT started (LESSONS empty)",
        LESSONS == () or len(LESSONS) == 0,
        {"lessons": LESSONS},
    )


# ==========================================================
# RUNNER
# ==========================================================

def main():

    print("\n" + "=" * 70)
    print("TEACHER ROLE RESPONSE — CONTRACT TESTS")
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
