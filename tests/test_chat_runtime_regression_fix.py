# ==========================================================
# CHAT RUNTIME REGRESSION FIX — CONTRACT / REGRESSION TESTS
#
# Covers the two defects fixed:
#
#   1. core/brain.py GENERAL_CHAT_FALLBACK called
#      self._chat_response(), a method that has never existed on Brain,
#      so a non-design turn raised:
#        AttributeError: 'Brain' object has no attribute '_chat_response'
#
#   2. The teaching-intent lexicon lacked the first-person / colloquial
#      Persian forms, so real teaching offers were not recognised and
#      fell through to that fallback instead of the teaching path.
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_chat_runtime_regression_fix.py
#   .venv/Scripts/python.exe tests/test_chat_runtime_regression_fix.py
# ==========================================================


import ast
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
    tempfile.gettempdir(), "architectos_chat_regression"
)

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = _TEMP_ROOT

os.environ.setdefault("ARCHITECTOS_PROJECTS_ROOT",
                      os.path.join(_TEMP_ROOT, "projects"))

os.environ.setdefault("ARCHITECTOS_PROJECT_TRASH_ROOT",
                      os.path.join(_TEMP_ROOT, "trash"))


from core.project.project_workspace_v1 import project_workspace

project_workspace.projects_root = os.path.join(_TEMP_ROOT, "projects")

project_workspace.trash_root = os.path.join(_TEMP_ROOT, "trash")

os.makedirs(project_workspace.projects_root, exist_ok=True)

os.makedirs(project_workspace.trash_root, exist_ok=True)


from core.brain import Brain

from core.registry.engine_registry import EngineRegistry

from core.conversation.turn_semantics_v1 import (
    extract_features,
    TURN_OFFER_TO_TEACH,
    TURN_NORMAL_CONVERSATION,
    TEACH_VERB_MARKERS,
    VOLITION_MARKERS,
)

from core.conversation.teaching_foundation_v1 import (
    teaching_foundation,
)

from core.conversation.teaching_candidate_v1 import (
    PERMANENT_LEARNING_IMPLEMENTED,
)

from core.conversation.knowledge_promotion_bridge_v1 import (
    PROMOTION_IMPLEMENTED,
)

from core.curriculum.curriculum_sequencer_v1 import (
    curriculum_sequencer,
    LESSONS,
)


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))

    return bool(passed)


# ----------------------------------------------------------
# THE EXACT MESSAGES FROM THE BUG REPORT
# ----------------------------------------------------------

MSG_TEACHING_SESSION = (
    "\u0633\u0644\u0627\u0645 \u0645\u06cc\u062e\u0648\u0627\u06cc\u0645 "
    "\u0627\u0648\u0644\u06cc\u0646 \u062c\u0644\u0633\u0647 \u0622\u0645\u0648\u0632\u0634 "
    "\u0645\u0639\u0645\u0627\u0631\u06cc \u0631\u0648 \u0634\u0631\u0648\u0639 \u06a9\u0646\u06cc\u0645"
)

MSG_TEACH_YOU = (
    "\u0642\u0631\u0627\u0631\u0647 \u0645\u0646 \u06cc\u0627\u062f\u062a "
    "\u0628\u062f\u0645 \u0637\u0631\u0627\u062d\u06cc \u06a9\u0631\u062f\u0646 \u0631\u0648 "
    "\u0648 \u0641\u0636\u0627\u0647\u0627\u06cc \u0645\u0639\u0645\u0627\u0631\u06cc \u0631\u0648"
)

MSG_PLAIN_CHAT = "\u0627\u0645\u0631\u0648\u0632 \u0647\u0648\u0627 \u062e\u0648\u0628\u0647"


def _project():

    manifest = project_workspace.create("Chat Regression")

    return manifest.get("project_id") or (
        manifest.get("project") or {}
    ).get("project_id")


def _observe(text, project_id=None):

    return teaching_foundation.observe_turn(
        session_id=project_id or _project(),
        text=text,
        input_type="typed",
    )


# ==========================================================
# DEFECT 1 — the phantom Brain._chat_response call
# ==========================================================

def test_brain_has_no_chat_response_method():

    """The method was never part of Brain's contract, so the fallback
    must NOT have been "restored" — it must have been redirected."""

    brain = Brain(registry=EngineRegistry())

    return _check(
        "CR-1 Brain still defines no _chat_response (it never did)",
        not hasattr(brain, "_chat_response")
        and not hasattr(brain, "_chat_response".lstrip("_")),
        {"methods": [
            m for m in dir(brain) if "chat" in m.lower()
        ]},
    )


def test_no_source_calls_chat_response():

    """No live code may reference the phantom method — only the fix
    comment may mention it."""

    offenders = []

    for folder in ("core", "ui", "chats"):

        base = os.path.join(ROOT, folder)

        if not os.path.isdir(base):

            continue

        for dirpath, dirs, files in os.walk(base):

            dirs[:] = [
                d for d in dirs
                if d not in ("__pycache__", ".venv")
            ]

            for name in files:

                if not name.endswith(".py"):

                    continue

                path = os.path.join(dirpath, name)

                with open(path, "r", encoding="utf-8",
                          errors="replace") as handle:

                    for lineno, line in enumerate(handle, 1):

                        stripped = line.strip()

                        if stripped.startswith("#"):

                            continue

                        if "._chat_response(" in line:

                            offenders.append(
                                "%s:%d" % (
                                    os.path.relpath(path, ROOT), lineno
                                )
                            )

    return _check(
        "CR-1 no live code CALLS _chat_response",
        not offenders,
        {"offenders": offenders[:6]},
    )


def test_brain_run_does_not_raise_for_a_non_design_intent():

    """The regression itself: this used to raise AttributeError."""

    brain = Brain(registry=EngineRegistry())

    raised = None

    result = None

    try:

        result = brain.run(MSG_TEACH_YOU, context={})

    except AttributeError as error:

        raised = "AttributeError: " + str(error)

    except Exception as error:

        raised = type(error).__name__ + ": " + str(error)

    return _check(
        "CR-1 Brain.run() no longer raises for a non-design turn",
        raised is None
        and isinstance(result, dict)
        and result.get("status") == "GENERAL_CHAT_FALLBACK"
        and result.get("brain_chat_response_available") is False,
        {"raised": raised,
         "status": (result or {}).get("status")},
    )


def test_fallback_envelope_shape_is_preserved():

    """The redirect must keep the envelope ChatArchitect expects."""

    brain = Brain(registry=EngineRegistry())

    result = brain.run(MSG_PLAIN_CHAT, context={})

    return _check(
        "CR-1 the fallback envelope keeps type/engine/status",
        result.get("type") == "chat"
        and result.get("engine") == "brain"
        and result.get("status") == "GENERAL_CHAT_FALLBACK"
        and "result" in result,
        {"keys": sorted(result.keys())},
    )


# ==========================================================
# DEFECT 2 — teaching intent for real user phrasings
# ==========================================================

def test_teaching_session_message_is_a_teaching_intent():

    features = extract_features(MSG_TEACHING_SESSION)

    observation = _observe(MSG_TEACHING_SESSION)

    return _check(
        "CR-2 'میخوایم ... آموزش ... شروع کنیم' is a teaching intent",
        features["teach_verb"] is True
        and features["volition"] is True
        and observation.get("turn_kind") == TURN_OFFER_TO_TEACH
        and observation.get("short_circuit") is True,
        {"turn_kind": observation.get("turn_kind"),
         "volition": features.get("volition")},
    )


def test_teach_you_message_is_a_teaching_intent():

    features = extract_features(MSG_TEACH_YOU)

    observation = _observe(MSG_TEACH_YOU)

    return _check(
        "CR-2 'قراره من یادت بدم ...' is a teaching intent (an OFFER)",
        features["teach_verb"] is True
        and features["teaching_intent_direction"]
        == "user_offers_to_teach"
        and observation.get("turn_kind") == TURN_OFFER_TO_TEACH
        and observation.get("short_circuit") is True,
        {"turn_kind": observation.get("turn_kind"),
         "direction": features.get("teaching_intent_direction")},
    )


def test_teaching_messages_ask_for_clarification():

    """Both must ACKNOWLEDGE and ask, never execute."""

    failures = []

    for text in (MSG_TEACHING_SESSION, MSG_TEACH_YOU):

        observation = _observe(text)

        response = observation.get("response") or {}

        teaching = response.get("teaching") or {}

        elicitation = teaching.get("elicitation") or {}

        reply = str(response.get("result") or "")

        if (
            response.get("capability") != "UNDERSTAND"
            or teaching.get("action") != "elicit_teaching_aspect"
            or len(elicitation.get("aspects") or []) == 0
            or not reply
            or response.get("render_requested") is not False
            or teaching.get("routed_to_execute") is not False
            or teaching.get("candidate") is not None
        ):

            failures.append(
                {
                    "capability": response.get("capability"),
                    "action": teaching.get("action"),
                    "aspects": len(elicitation.get("aspects") or []),
                    "render": response.get("render_requested"),
                }
            )

    return _check(
        "CR-2 both teaching messages acknowledge and ask (no EXECUTE, "
        "no render)",
        not failures,
        failures,
    )


def test_plain_chat_is_not_captured():

    """The added markers must not turn ordinary chat into teaching."""

    features = extract_features(MSG_PLAIN_CHAT)

    observation = _observe(MSG_PLAIN_CHAT)

    return _check(
        "CR-2 plain chat is still NORMAL_CONVERSATION",
        features["teaching_intent"] is False
        and observation.get("turn_kind") != TURN_OFFER_TO_TEACH
        and observation.get("short_circuit") is False,
        {"turn_kind": observation.get("turn_kind")},
    )


def test_volition_singular_forms_still_work():

    """The pre-existing forms must not have been broken."""

    missing = [
        marker for marker in (
            "\u0645\u06cc \u062e\u0648\u0627\u0647\u0645",   # می خواهم
            "\u0645\u06cc\u062e\u0648\u0627\u0645",         # میخوام
        )
        if marker not in VOLITION_MARKERS
    ]

    return _check(
        "CR-2 the original singular volition markers are still present",
        not missing,
        {"missing": missing},
    )


def test_teach_verb_original_forms_still_work():

    missing = [
        marker for marker in (
            "\u06cc\u0627\u062f \u0628\u062f\u0647\u0645",   # یاد بدهم
            "\u06cc\u0627\u062f \u0628\u062f\u0647",         # یاد بده
            "\u0622\u0645\u0648\u0632\u0634",               # آموزش
        )
        if marker not in TEACH_VERB_MARKERS
    ]

    return _check(
        "CR-2 the original teach-verb markers are still present",
        not missing,
        {"missing": missing},
    )


# ==========================================================
# CURRICULUM MUST STILL NOT BE STARTED
# ==========================================================

def test_curriculum_still_not_started():

    return _check(
        "CR-3 curriculum is still NOT started",
        LESSONS == ()
        and curriculum_sequencer.report()["lesson_count"] == 0
        and PROMOTION_IMPLEMENTED is False
        and PERMANENT_LEARNING_IMPLEMENTED is False,
        {"lessons": curriculum_sequencer.report()["lesson_count"]},
    )


def test_no_learning_from_a_teaching_offer():

    project_id = _project()

    observation = _observe(MSG_TEACH_YOU, project_id)

    return _check(
        "CR-3 a teaching offer creates no candidate and learns nothing",
        (observation.get("candidate")) is None
        and (observation.get("response") or {}).get("teaching", {}).get(
            "permanent_learning"
        ) is False,
        {"candidate": observation.get("candidate")},
    )


# ==========================================================
# MAIN
# ==========================================================

def _all_tests():

    return [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]


def main():

    print("\n" + "=" * 70)
    print("  CHAT RUNTIME REGRESSION FIX")
    print("=" * 70)

    for test in _all_tests():

        test()

    failed = [r for r in _RESULTS if not r[1]]

    for name, passed, detail in _RESULTS:

        print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

        if not passed:

            print(
                "        ",
                json.dumps(detail, ensure_ascii=False, default=str)[:420],
            )

    print("-" * 70)
    print(
        "  %d/%d PASS" % (len(_RESULTS) - len(failed), len(_RESULTS))
    )
    print("=" * 70 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())
