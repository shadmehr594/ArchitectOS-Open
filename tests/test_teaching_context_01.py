# ==========================================================
# TEACHING_CONTEXT_01 — CONTRACT / ACCEPTANCE TESTS
#
# The audit (`docs/audit/TEACHING_SUBJECT_RESOLUTION_AUDIT.md`) found
# that a teaching statement was attached to the WRONG architectural
# space: `subject` was `entities[0]`, and `entities` was ordered by the
# LEXICON, so "living" always beat "bedroom" — while the corpus resolver
# would have returned MASTER_BEDROOM_SLEEPING for the very same text.
#
# Three bounded corrections:
#   1. ENTITY ORDER  — hits ordered by their position in the user's text
#   2. COMPOSITE     — an explicit composite space wins
#                      ("اتاق خواب مستر" -> MASTER_BEDROOM_SLEEPING)
#   3. ACTIVE TOPIC  — the teaching conversation keeps its space, but an
#                      explicit DIFFERENT space is never overridden
#
# SCOPE: no new space ids, no curriculum change, no lesson, no
# promotion, no global memory.
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_teaching_context_01.py
#   .venv/Scripts/python.exe tests/test_teaching_context_01.py
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
    tempfile.gettempdir(), "architectos_teaching_context_01"
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

from core.conversation.teaching_meaning_v1 import (  # noqa: E402
    extract_meaning,
    entity_display,
    resolve_teaching_subject,
    is_space_id,
)

from core.conversation.teaching_candidate_v1 import (  # noqa: E402
    TeachingCandidate,
    PERMANENT_LEARNING_IMPLEMENTED,
)

from core.conversation.knowledge_promotion_bridge_v1 import (  # noqa: E402
    PROMOTION_IMPLEMENTED,
)

from core.conversation.turn_semantics_v1 import (  # noqa: E402
    extract_features,
    classify_turn,
    TURN_TEACHING_STATEMENT,
    TURN_NORMAL_CONVERSATION,
)

from core.curriculum.curriculum_sequencer_v1 import (  # noqa: E402
    LESSONS,
)


# ----------------------------------------------------------
# THE MESSAGES FROM THE AUDIT AND THE BRIEF
# ----------------------------------------------------------

MSG_A = "اتاق خواب مستر باید فضای نشیمن داشته باشد"

MSG_B = "فضای نشیمن اتاق خواب مستر باید بزرگ باشد"

MSG_C = "اتاق خواب مستر فقط محل خواب نیست"

MSG_D = (
    "ویژگی مشترک تمام اتاق خواب‌های مستر یا مستر روم داشتن حمام و "
    "سرویس بهداشتی است"
)

MSG_E = (
    "اگر مساحت زمین و زیربنا اجازه بدهد، کلوزت روم هم می‌تواند داشته باشد"
)

MSG_F = "نشیمن باید در فضای عمومی و نزدیک ورودی باشد"

MSG_PLAIN = "اتاق خواب فضای خصوصی است"

MSG_LIVING = "نشیمن باید نزدیک اتاق خواب باشد"

# A plain conditional with NO architectural allowance — must NOT be a
# teaching statement.
MSG_PLAIN_CONDITIONAL = "اگر باران بیاید می رویم"


MASTER = "MASTER_BEDROOM_SLEEPING"

LIVING = "LIVING_RECEPTION"


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))

    return bool(passed)


def _project():

    manifest = project_workspace.create("Teaching Context 01")

    return manifest.get("project_id") or (
        manifest.get("project") or {}
    ).get("project_id")


def _observe(text, project_id, context=None):

    return teaching_foundation.observe_turn(
        session_id=project_id,
        text=text,
        context=context or {"session_id": project_id},
        input_type="typed",
    )


def _candidate(text, project_id, context=None):

    observation = _observe(text, project_id, context=context)

    response = observation.get("response") or {}

    return observation, (response.get("teaching") or {}).get("candidate")


def _subject(meaning):

    return meaning.get("subject")


# ==========================================================
# A / B — ENTITY ORDER REGRESSION
# ==========================================================

def test_a_subject_is_not_living_when_bedroom_comes_first():

    meaning = extract_meaning(MSG_A, turn_kind=TURN_TEACHING_STATEMENT)

    return _check(
        "A. 'اتاق خواب مستر باید فضای نشیمن داشته باشد' -> subject is "
        "NOT living",
        _subject(meaning) != "living",
        {
            "subject": _subject(meaning),
            "entities": meaning.get("entities"),
            "normalized": meaning.get("normalized_meaning"),
        },
    )


def test_b_subject_is_not_living_when_living_comes_first():

    meaning = extract_meaning(MSG_B, turn_kind=TURN_TEACHING_STATEMENT)

    return _check(
        "B. 'فضای نشیمن اتاق خواب مستر باید بزرگ باشد' -> subject is "
        "NOT living",
        _subject(meaning) != "living",
        {
            "subject": _subject(meaning),
            "entities": meaning.get("entities"),
            "normalized": meaning.get("normalized_meaning"),
        },
    )


def test_entity_order_follows_the_text_not_the_lexicon():

    first = extract_meaning(MSG_A, turn_kind=TURN_TEACHING_STATEMENT)

    second = extract_meaning(MSG_B, turn_kind=TURN_TEACHING_STATEMENT)

    # Same two entities, opposite word order -> opposite list order.
    return _check(
        "A1. entity ORDER follows the text (bedroom-first vs living-first "
        "now differ)",
        first.get("entities") == ["bedroom", "living"]
        and second.get("entities") == ["living", "bedroom"],
        {
            "A_entities": first.get("entities"),
            "B_entities": second.get("entities"),
        },
    )


def test_the_entity_set_and_normalisation_are_unchanged():

    meaning = extract_meaning(MSG_A, turn_kind=TURN_TEACHING_STATEMENT)

    # Membership, not order: the SET of hits and their canonical
    # normalisation must be exactly as before.
    return _check(
        "A2. the entity SET is unchanged (bedroom + living, canonical)",
        sorted(meaning.get("entities") or []) == ["bedroom", "living"]
        and meaning.get("domain") == "space",
        {
            "entities": meaning.get("entities"),
            "domain": meaning.get("domain"),
        },
    )


def test_domain_behaviour_is_preserved():

    meaning = extract_meaning(MSG_LIVING, turn_kind=TURN_TEACHING_STATEMENT)

    return _check(
        "A3. domain resolution unchanged (relation + entities -> "
        "spatial_relationship)",
        meaning.get("domain") == "spatial_relationship"
        and meaning.get("primary_relation") == "near",
        {
            "domain": meaning.get("domain"),
            "relation": meaning.get("primary_relation"),
        },
    )


# ==========================================================
# C — COMPOSITE SPACE RESOLUTION
# ==========================================================

def test_c_composite_space_resolves_to_the_existing_corpus_id():

    meaning = extract_meaning(MSG_C, turn_kind=TURN_TEACHING_STATEMENT)

    return _check(
        "C. 'اتاق خواب مستر' -> the EXISTING MASTER_BEDROOM space id",
        meaning.get("space_topic") == MASTER
        and meaning.get("subject") == MASTER
        and meaning.get("subject_source") == "explicit_composite",
        {
            "space_topic": meaning.get("space_topic"),
            "subject_source": meaning.get("subject_source"),
        },
    )


def test_c_no_new_space_id_was_invented():

    from core.curriculum.space_types_v1 import space_types

    return _check(
        "C1. the resolved id exists in the frozen corpus (nothing invented)",
        MASTER in space_types.spaces()
        and space_types.space(MASTER) is not None,
        {"space_id": MASTER},
    )


def test_plain_space_statements_keep_their_historical_subject():

    meaning = extract_meaning(MSG_PLAIN, turn_kind=TURN_TEACHING_STATEMENT)

    return _check(
        "C2. a plain 'اتاق خواب' statement keeps the flat entity subject",
        meaning.get("subject") == "bedroom"
        and meaning.get("space_topic") is None,
        {
            "subject": meaning.get("subject"),
            "space_topic": meaning.get("space_topic"),
        },
    )


def test_a_space_id_renders_as_its_corpus_name():

    return _check(
        "C3. a resolved space id renders as its corpus name, not the raw id",
        entity_display(MASTER, "fa") == "بخش خواب مستر"
        and entity_display("bedroom", "fa") == "اتاق خواب",
        {
            "space_display": entity_display(MASTER, "fa"),
            "entity_display": entity_display("bedroom", "fa"),
        },
    )


# ==========================================================
# D / E / F — TOPIC CONTINUITY (one real conversation)
# ==========================================================

def test_d_e_f_topic_continuity_in_one_conversation():

    project_id = _project()

    # C — the conversation starts about the master bedroom.
    _observation_c, candidate_c = _candidate(MSG_C, project_id)

    # D — a long follow-up with NO composite alias ("خواب‌های مستر" is
    # plural, so the corpus scanner finds only the flat "اتاق خواب").
    _observation_d, candidate_d = _candidate(MSG_D, project_id)

    # E — a conditional allowance that names no space at all.
    _observation_e, candidate_e = _candidate(MSG_E, project_id)

    # F — an explicit statement about a DIFFERENT space.
    _observation_f, candidate_f = _candidate(MSG_F, project_id)

    return _check(
        "D/E/F. topic continuity: MASTER -> MASTER -> MASTER, then an "
        "explicit living-room switch",
        (candidate_c or {}).get("space_topic") == MASTER
        and (candidate_d or {}).get("space_topic") == MASTER
        and (candidate_e or {}).get("space_topic") == MASTER
        and (candidate_f or {}).get("space_topic") != MASTER,
        {
            "C": (candidate_c or {}).get("space_topic"),
            "D": (candidate_d or {}).get("space_topic"),
            "E": (candidate_e or {}).get("space_topic"),
            "F": (candidate_f or {}).get("space_topic"),
        },
    )


def test_d_candidate_stays_attached_to_master_bedroom():

    project_id = _project()

    _candidate(MSG_C, project_id)

    _observation, candidate = _candidate(MSG_D, project_id)

    return _check(
        "D. the long follow-up stays attached to MASTER_BEDROOM",
        (candidate or {}).get("space_topic") == MASTER
        and MASTER in str((candidate or {}).get("normalized_meaning")),
        {
            "space_topic": (candidate or {}).get("space_topic"),
            "normalized": (candidate or {}).get("normalized_meaning"),
        },
    )


def test_e_follow_up_is_attached_and_conditional_is_preserved():

    project_id = _project()

    _candidate(MSG_C, project_id)

    _candidate(MSG_D, project_id)

    _observation, candidate = _candidate(MSG_E, project_id)

    candidate = candidate or {}

    return _check(
        "E. the conditional follow-up stays attached to MASTER_BEDROOM "
        "and keeps its conditional nature",
        candidate.get("space_topic") == MASTER
        and candidate.get("polarity") == "conditional"
        and "conditional=true" in str(candidate.get("normalized_meaning")),
        {
            "space_topic": candidate.get("space_topic"),
            "polarity": candidate.get("polarity"),
            "normalized": candidate.get("normalized_meaning"),
        },
    )


def test_f_an_explicit_different_space_is_never_overridden():

    project_id = _project()

    _candidate(MSG_C, project_id)

    _observation, candidate = _candidate(MSG_F, project_id)

    return _check(
        "F. an explicit living-room statement does NOT inherit "
        "MASTER_BEDROOM",
        (candidate or {}).get("space_topic") != MASTER
        and "living" in ((candidate or {}).get("entities") or []),
        {
            "space_topic": (candidate or {}).get("space_topic"),
            "entities": (candidate or {}).get("entities"),
        },
    )


def test_no_active_topic_means_the_historical_behaviour():

    project_id = _project()

    meaning = extract_meaning(MSG_LIVING, turn_kind=TURN_TEACHING_STATEMENT)

    subject, source = resolve_teaching_subject(
        meaning.get("entities"), "نشیمن باید نزدیک اتاق خواب باشد", None
    )

    return _check(
        "F1. with no active topic the earliest entity is used (unchanged)",
        subject == "living" and source == "earliest_entity",
        {"subject": subject, "source": source},
    )


# ==========================================================
# THE CONDITIONAL MARKER MUST NOT OVER-CAPTURE
# ==========================================================

def test_a_plain_conditional_is_not_a_teaching_statement():

    features = extract_features(MSG_PLAIN_CONDITIONAL)

    kind = classify_turn(MSG_PLAIN_CONDITIONAL).get("turn_kind")

    return _check(
        "G1. a plain conditional ('اگر باران بیاید می رویم') is NOT a "
        "teaching statement",
        features.get("conditional_allowance") is False
        and kind == TURN_NORMAL_CONVERSATION,
        {"conditional_allowance": features.get("conditional_allowance"),
         "turn_kind": kind},
    )


def test_the_allowance_marker_is_two_part():

    features = extract_features(MSG_E)

    # The opener alone, and the modal alone, must each be insufficient.
    opener_only = extract_features("اگر فردا وقت داشتی")

    modal_only = extract_features("اتاق خواب مستر می تواند بزرگ باشد")

    return _check(
        "G2. the conditional marker requires BOTH parts",
        features.get("conditional_allowance") is True
        and opener_only.get("conditional_allowance") is False
        and modal_only.get("conditional_allowance") is False,
        {
            "E": features.get("conditional_allowance"),
            "opener_only": opener_only.get("conditional_allowance"),
            "modal_only": modal_only.get("conditional_allowance"),
        },
    )


# ==========================================================
# CONTRACT / SAFETY
# ==========================================================

def test_candidate_round_trip_preserves_space_topic():

    candidate = TeachingCandidate(
        raw_statement=MSG_C,
        project_id="p",
        source_turn_id="t",
        space_topic=MASTER,
    )

    payload = candidate.to_dict()

    restored = TeachingCandidate.from_dict(payload)

    return _check(
        "G3. space_topic survives the candidate round trip",
        payload.get("space_topic") == MASTER
        and restored.space_topic == MASTER,
        {
            "payload": payload.get("space_topic"),
            "restored": restored.space_topic,
        },
    )


def test_nothing_is_learned_promoted_or_lessoned():

    project_id = _project()

    for message in (MSG_C, MSG_D, MSG_E, MSG_F):

        _candidate(message, project_id)

    return _check(
        "G4. no permanent learning, no promotion, curriculum NOT started",
        PERMANENT_LEARNING_IMPLEMENTED is False
        and PROMOTION_IMPLEMENTED is False
        and teaching_foundation.learned_count(project_id) == 0
        and len(LESSONS) == 0,
        {
            "learned_count": teaching_foundation.learned_count(project_id),
            "lessons": LESSONS,
        },
    )


def test_the_active_topic_is_project_scoped_not_global():

    project_a = _project()

    project_b = _project()

    _candidate(MSG_C, project_a)

    # Project B has no teaching history, so it must NOT inherit A's topic.
    _observation, candidate_b = _candidate(MSG_E, project_b)

    return _check(
        "G5. the inherited topic is project-scoped (no global memory)",
        (candidate_b or {}).get("space_topic") is None,
        {"project_b_space_topic": (candidate_b or {}).get("space_topic")},
    )


def test_space_id_guard_rejects_generic_words():

    return _check(
        "G6. only corpus-shaped ids count as a space id",
        is_space_id(MASTER) is True
        and is_space_id("architecture") is False
        and is_space_id(None) is False
        and is_space_id("") is False,
        {
            "space": is_space_id(MASTER),
            "generic": is_space_id("architecture"),
        },
    )


# ==========================================================
# RUNNER
# ==========================================================

def main():

    print("\n" + "=" * 70)
    print("TEACHING_CONTEXT_01 — CONTRACT / ACCEPTANCE TESTS")
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
