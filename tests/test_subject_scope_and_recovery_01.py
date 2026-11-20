# ==========================================================
# SUBJECT_SCOPE_AND_TURN_RECOVERY_01 — CONTRACT / ACCEPTANCE TESTS
#
# TWO user-reported defects, reported together:
#
#   1. "هنوز نمیتونه فقط قاعده هایی که راجب اتاق مستر بوده رو بگه
#      مثلا حرف هایی که راجب نشیمن هم زدیم اوره تو این جواب"
#      A question about the MASTER BEDROOM was answered with a rule the
#      teacher had stated about the LIVING AREA ("نشیمن هم باید پنجره
#      داشته باشه"), because a recorded message that mixes spaces was
#      listed wholesale.
#
#   2. "عکس رو قبلا مفرستادم میتونست بخونه الان نتونست"
#      The image turn failed with
#      `Request failed: TypeError: NetworkError when attempting to fetch
#      resource.` while the Core had ALREADY answered and stored the
#      analysis — the turn was dropped from the user's view.
#
# Nothing here is allowed to write, learn, promote or render.
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_subject_scope_and_recovery_01.py
#   .venv/Scripts/python.exe tests/test_subject_scope_and_recovery_01.py
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
    tempfile.gettempdir(), "architectos_subject_scope_01"
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


from core.conversation.teach_back_v1 import (  # noqa: E402
    build_grounded_answer,
    _in_subject_scope,
    _space_band,
)

from core.conversation.teaching_candidate_v1 import (  # noqa: E402
    teaching_candidate_store,
)

from core.project.project_session_v1 import (  # noqa: E402
    project_session,
    last_assistant_message,
)


# ----------------------------------------------------------
# THE TEACHER'S OWN MESSAGES (verbatim, from the live project)
# ----------------------------------------------------------

# One recorded message that mixes the master bedroom WITH the living
# area. The last rule is about the LIVING AREA only.
MIXED_MESSAGE = (
    "اینم باز اشتباه فهمیدی : فهمیدم: پنجره باید دور از اتاق خواب و "
    "نشیمن باشد. ، من گفتم تخت دور از پنجره باشه بهتره تو برای اتاق "
    "خواب حتما پنجره داشته باشی اتاق خواب به نور طبیعی و تهویه نیاز "
    "داره ، نشیمن هم باید پنجره داشته باشه"
)

BEDROOM_RULE = "تخت دور از پنجره باشه بهتره"

BEDROOM_WINDOW_RULE = "تو برای اتاق خواب حتما پنجره داشته باشی"

LIVING_ONLY_RULE = "نشیمن هم باید پنجره داشته باشه"

# A BEDROOM rule that HAPPENS to name the living area — it must stay.
CROSS_RULE = (
    "اتاق خواب ها باید دور از پذیرایی و فضاهای نشیمن باشن"
)

# A rule that names no space at all — it inherits its message's subject.
SUBJECTLESS_RULE = (
    "تخت باید جایی گذاشته شود که در باز میشود دیدی به تخت نداشته باشه"
)


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))


def _project():

    manifest = project_workspace.create("Subject Scope")

    return manifest.get("project_id") or (
        manifest.get("project") or {}
    ).get("project_id")


def _record(project_id, statement, **extra):

    payload = {
        "raw_statement": statement,
        "domain": "space",
        "status": "observed",
        "provenance": "HUMAN_TEACHER",
        "space_topic": "MASTER_BEDROOM_SLEEPING",
        "entities": ["bed", "window"],
        "relations": ["far"],
        "polarity": "require",
        "knowledge_class": "DESIGN_RULE",
        "scope": "GENERAL",
    }

    payload.update(extra)

    return teaching_candidate_store.record(project_id, payload)


# ==========================================================
# 1. THE REPORTED CASE — A LIVING-AREA RULE IS NOT A BEDROOM RULE
# ==========================================================

def test_a_living_area_rule_is_not_listed_for_the_master_bedroom():

    project_id = _project()

    _record(project_id, MIXED_MESSAGE)

    grounded = build_grounded_answer(
        project_id=project_id,
        space_topic="MASTER_BEDROOM_SLEEPING",
        language="fa",
    )

    text = (grounded or {}).get("result") or ""

    return _check(
        "S1. the living-area rule ('نشیمن هم باید پنجره داشته باشه') is "
        "NOT part of a master-bedroom answer",
        LIVING_ONLY_RULE not in text,
        {"text": text[:600]},
    )


def test_the_bedroom_rules_are_still_there():

    project_id = _project()

    _record(project_id, MIXED_MESSAGE)

    grounded = build_grounded_answer(
        project_id=project_id,
        space_topic="MASTER_BEDROOM_SLEEPING",
        language="fa",
    )

    text = (grounded or {}).get("result") or ""

    return _check(
        "S2. every rule the message stated about the bedroom survives "
        "(scoping removes nothing that belongs)",
        BEDROOM_RULE in text and BEDROOM_WINDOW_RULE in text,
        {"text": text[:600]},
    )


def test_a_bedroom_rule_that_names_the_living_area_is_kept():

    project_id = _project()

    _record(project_id, CROSS_RULE)

    grounded = build_grounded_answer(
        project_id=project_id,
        space_topic="MASTER_BEDROOM_SLEEPING",
        language="fa",
    )

    text = (grounded or {}).get("result") or ""

    return _check(
        "S3. 'bedrooms must be far from the reception/living areas' is a "
        "BEDROOM rule and is kept, even though it names the living area",
        CROSS_RULE in text,
        {"text": text[:400]},
    )


def test_a_rule_that_names_no_space_is_kept():

    project_id = _project()

    _record(project_id, SUBJECTLESS_RULE)

    grounded = build_grounded_answer(
        project_id=project_id,
        space_topic="MASTER_BEDROOM_SLEEPING",
        language="fa",
    )

    text = (grounded or {}).get("result") or ""

    return _check(
        "S4. a rule that names no space at all is kept (it inherits the "
        "subject of the message it came from)",
        SUBJECTLESS_RULE in text,
        {"text": text[:400]},
    )


def test_the_heading_does_not_quote_the_other_space_rule():

    project_id = _project()

    _record(project_id, MIXED_MESSAGE)

    grounded = build_grounded_answer(
        project_id=project_id,
        space_topic="MASTER_BEDROOM_SLEEPING",
        language="fa",
    )

    text = (grounded or {}).get("result") or ""

    heading = [
        line for line in text.splitlines()
        if line.startswith("• ") and BEDROOM_RULE in line
    ]

    return _check(
        "S5. the recorded message is shown WITHOUT the other space's "
        "wording — and every word that remains is verbatim",
        bool(heading)
        and LIVING_ONLY_RULE not in heading[0]
        and BEDROOM_WINDOW_RULE in heading[0],
        {"heading": heading[0][:400] if heading else None},
    )


def test_the_omission_is_reported_not_hidden():

    project_id = _project()

    _record(project_id, MIXED_MESSAGE)

    grounded = build_grounded_answer(
        project_id=project_id,
        space_topic="MASTER_BEDROOM_SLEEPING",
        language="fa",
    )

    text = (grounded or {}).get("result") or ""

    return _check(
        "S6. the answer SAYS that a recorded item about another space "
        "was left out (never a silent deletion)",
        (grounded or {}).get("omitted_items") == 1
        and "فضای دیگری" in text,
        {
            "omitted_items": (grounded or {}).get("omitted_items"),
            "text": text[:300],
        },
    )


def test_a_message_that_is_only_about_another_space_is_omitted():

    project_id = _project()

    _record(project_id, LIVING_ONLY_RULE)

    _record(project_id, BEDROOM_RULE)

    grounded = build_grounded_answer(
        project_id=project_id,
        space_topic="MASTER_BEDROOM_SLEEPING",
        language="fa",
    )

    text = (grounded or {}).get("result") or ""

    return _check(
        "S7. a record that is only about another space is left out "
        "entirely, and the bedroom record is still answered",
        LIVING_ONLY_RULE not in text and BEDROOM_RULE in text,
        {"text": text[:400]},
    )


def test_a_clause_candidate_about_another_space_is_not_used():

    project_id = _project()

    _record(
        project_id,
        LIVING_ONLY_RULE,
        clause_role="RULE",
        clause_index=0,
        clause_count=1,
    )

    _record(
        project_id,
        BEDROOM_RULE,
        clause_role="RULE",
        clause_index=1,
        clause_count=2,
    )

    grounded = build_grounded_answer(
        project_id=project_id,
        space_topic="MASTER_BEDROOM_SLEEPING",
        language="fa",
    )

    text = (grounded or {}).get("result") or ""

    return _check(
        "S8. a CLAUSE candidate about another space is not used either",
        LIVING_ONLY_RULE not in text and BEDROOM_RULE in text,
        {"text": text[:400]},
    )


def test_the_english_answer_is_scoped_too():

    project_id = _project()

    _record(project_id, MIXED_MESSAGE)

    grounded = build_grounded_answer(
        project_id=project_id,
        space_topic="MASTER_BEDROOM_SLEEPING",
        language="en",
    )

    text = (grounded or {}).get("result") or ""

    return _check(
        "S9. the English rendering is scoped as well, and says so in "
        "English",
        LIVING_ONLY_RULE not in text
        and "DIFFERENT space" in text
        and "None" not in text,
        {"text": text[:400]},
    )


def test_the_mirror_case_a_bedroom_rule_is_not_used_for_a_living_question():

    project_id = _project()

    # A BEDROOM-named rule filed under the living area (the record's own
    # topic can be wrong — the wording still says which space it is
    # about).
    _record(
        project_id,
        BEDROOM_WINDOW_RULE,
        space_topic="LIVING_RECEPTION",
    )

    _record(
        project_id,
        LIVING_ONLY_RULE,
        space_topic="LIVING_RECEPTION",
    )

    grounded = build_grounded_answer(
        project_id=project_id,
        space_topic="LIVING_RECEPTION",
        language="fa",
    )

    text = (grounded or {}).get("result") or ""

    return _check(
        "S10. the axis works BOTH ways: a bedroom-named rule is not "
        "listed in a living-area answer",
        BEDROOM_WINDOW_RULE not in text and LIVING_ONLY_RULE in text,
        {"text": text[:400]},
    )


# ==========================================================
# 2. THE RECORD IS NEVER REWRITTEN
# ==========================================================

def test_the_recorded_candidates_are_untouched():

    project_id = _project()

    _record(project_id, MIXED_MESSAGE)

    before = json.dumps(
        teaching_candidate_store.candidates(project_id),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )

    build_grounded_answer(
        project_id=project_id,
        space_topic="MASTER_BEDROOM_SLEEPING",
        language="fa",
    )

    after = json.dumps(
        teaching_candidate_store.candidates(project_id),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )

    stored = teaching_candidate_store.candidates(project_id)

    return _check(
        "S11. answering a question rewrites NOTHING on disk (the "
        "projection is display-time only)",
        before == after
        and len(stored) == 1
        and stored[0].get("raw_statement") == MIXED_MESSAGE,
        {"count": len(stored)},
    )


def test_nothing_is_learned_promoted_or_rendered():

    project_id = _project()

    _record(project_id, MIXED_MESSAGE)

    grounded = build_grounded_answer(
        project_id=project_id,
        space_topic="MASTER_BEDROOM_SLEEPING",
        language="fa",
    ) or {}

    return _check(
        "S12. no render, no promotion, no learning, no network",
        grounded.get("is_knowledge") is False
        and grounded.get("learned_anything") is False
        and grounded.get("permanent_learning_implemented") is False
        and grounded.get("render_requested") is False
        and grounded.get("comfy_invoked") is False
        and grounded.get("network_used") is False
        and grounded.get("llm_used") is False,
        {
            "render": grounded.get("render_requested"),
            "learned": grounded.get("learned_anything"),
        },
    )


def test_an_untaught_space_still_returns_none():

    project_id = _project()

    _record(project_id, MIXED_MESSAGE)

    grounded = build_grounded_answer(
        project_id=project_id,
        space_topic="KITCHEN",
        language="fa",
    )

    return _check(
        "S13. a space with NO recorded teaching still returns None, so "
        "the caller keeps its existing behaviour",
        grounded is None,
        {"grounded": grounded},
    )


def test_the_scope_predicate_uses_the_frozen_registry():

    return _check(
        "S14. the privacy bands come from the frozen space registry "
        "(master bedroom and bedroom are private; living is public)",
        _space_band("MASTER_BEDROOM_SLEEPING") == "private"
        and _space_band("BEDROOM_DOUBLE") == "private"
        and _space_band("LIVING_RECEPTION") == "public"
        and _in_subject_scope(LIVING_ONLY_RULE, "MASTER_BEDROOM_SLEEPING")
        is False
        and _in_subject_scope(CROSS_RULE, "MASTER_BEDROOM_SLEEPING") is True
        and _in_subject_scope(SUBJECTLESS_RULE, "MASTER_BEDROOM_SLEEPING")
        is True,
        {
            "master": _space_band("MASTER_BEDROOM_SLEEPING"),
            "living": _space_band("LIVING_RECEPTION"),
        },
    )


# ==========================================================
# 3. A LOST RESPONSE MUST NOT LOSE THE ANSWER
# ==========================================================

def test_the_workspace_can_recover_the_last_answer():

    project_id = _project()

    summary = project_session.recovery_summary(project_id)

    return _check(
        "R1. the project recovery summary carries the last stored "
        "assistant reply, so a lost HTTP response can be recovered",
        "last_assistant_message" in (summary or {}),
        {"keys": sorted((summary or {}).keys())},
    )


def test_recovery_is_none_without_a_reply():

    return _check(
        "R2. with no stored reply the recovery value is None (it never "
        "invents one)",
        last_assistant_message({"messages": []}) is None
        and last_assistant_message(None) is None
        and last_assistant_message(
            {"messages": [{"role": "user", "text": "سلام"}]}
        ) is None,
        {},
    )


def test_recovery_returns_the_newest_assistant_reply():

    chat = {
        "messages": [
            {"role": "user", "text": "a"},
            {"role": "assistant", "text": "old"},
            {"role": "user", "text": "b"},
            {"role": "assistant", "text": "newest"},
        ]
    }

    return _check(
        "R3. the NEWEST assistant reply is the one recovered (never an "
        "older turn's answer)",
        last_assistant_message(chat) == "newest",
        {"got": last_assistant_message(chat)},
    )


def test_the_recovery_key_is_additive():

    project_id = _project()

    summary = project_session.recovery_summary(project_id) or {}

    required = (
        "contract",
        "version",
        "project_id",
        "project_name",
        "message_count",
        "asset_count",
        "ordinals",
        "active_asset_id",
        "lineage",
        "save_state",
        "storage_path",
    )

    missing = [key for key in required if key not in summary]

    return _check(
        "R4. every pre-existing recovery key is still present (the new "
        "one is additive only)",
        not missing,
        {"missing": missing},
    )


# ==========================================================
# RUNNER
# ==========================================================

def main():

    print("\n" + "=" * 70)
    print("SUBJECT_SCOPE_AND_TURN_RECOVERY_01 — CONTRACT TESTS")
    print("=" * 70)

    tests = [
        test_a_living_area_rule_is_not_listed_for_the_master_bedroom,
        test_the_bedroom_rules_are_still_there,
        test_a_bedroom_rule_that_names_the_living_area_is_kept,
        test_a_rule_that_names_no_space_is_kept,
        test_the_heading_does_not_quote_the_other_space_rule,
        test_the_omission_is_reported_not_hidden,
        test_a_message_that_is_only_about_another_space_is_omitted,
        test_a_clause_candidate_about_another_space_is_not_used,
        test_the_english_answer_is_scoped_too,
        test_the_mirror_case_a_bedroom_rule_is_not_used_for_a_living_question,
        test_the_recorded_candidates_are_untouched,
        test_nothing_is_learned_promoted_or_rendered,
        test_an_untaught_space_still_returns_none,
        test_the_scope_predicate_uses_the_frozen_registry,
        test_the_workspace_can_recover_the_last_answer,
        test_recovery_is_none_without_a_reply,
        test_recovery_returns_the_newest_assistant_reply,
        test_the_recovery_key_is_additive,
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
                json.dumps(detail, ensure_ascii=False, default=str)[:600],
            )

    print("-" * 70)
    print("  %d/%d PASS" % (len(_RESULTS) - len(failed), len(_RESULTS)))
    print("=" * 70 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())
