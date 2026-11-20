# ==========================================================
# PHASE 08 — TEACHING FOUNDATION CONTRACT TESTS
#
# These are ISOLATED CONTRACT tests.  They are NOT the acceptance
# proof: real acceptance runs against the live runtime path
# (tools/run_teaching_foundation_08_acceptance.py).
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_teaching_foundation_08.py
#   .venv/Scripts/python.exe tests/test_teaching_foundation_08.py
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


# Isolate all project storage for this test run.
_TEMP_ROOT = os.path.join(
    tempfile.gettempdir(), "architectos_phase08_contract"
)

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = _TEMP_ROOT

os.environ.setdefault("ARCHITECTOS_PROJECTS_ROOT",
                      os.path.join(_TEMP_ROOT, "projects"))

os.environ.setdefault("ARCHITECTOS_PROJECT_TRASH_ROOT",
                      os.path.join(_TEMP_ROOT, "trash"))


from core.project.project_workspace_v1 import project_workspace

# Defensive: point the singleton at the temp root even if it was
# imported before the environment was set.
project_workspace.projects_root = os.path.join(_TEMP_ROOT, "projects")

project_workspace.trash_root = os.path.join(_TEMP_ROOT, "trash")

os.makedirs(project_workspace.projects_root, exist_ok=True)

os.makedirs(project_workspace.trash_root, exist_ok=True)


from core.conversation.turn_semantics_v1 import (
    classify_turn,
    ALL_TURN_KINDS,
    TURN_QUESTION,
    TURN_INSTRUCTION,
    TURN_CORRECTION,
    TURN_TEACHING_STATEMENT,
    TURN_CONFIRMATION_REQUEST,
    TURN_NORMAL_CONVERSATION,
    TURN_UNKNOWN,
)

from core.conversation.teaching_candidate_v1 import (
    TeachingCandidate,
    TeachingCandidateStoreV1,
    build_candidate,
    teaching_candidate_store,
    ALLOWED_STATUSES,
    FORBIDDEN_STATUSES,
    STATUS_OBSERVED,
    STATUS_REJECTED,
    PERMANENT_LEARNING_IMPLEMENTED,
)

from core.conversation.teach_back_v1 import build_teach_back

from core.conversation.conversation_language_v1 import (
    resolve_conversation_language,
    set_project_language,
    project_language_record,
)

from core.conversation.execution_boundary_v1 import (
    capability_for_turn,
    is_action_turn,
    is_knowledge_turn,
    describe as boundary_describe,
    CAP_EXECUTE,
    CAP_LEARN,
    CAP_VERIFY,
    CAP_UNDERSTAND,
)

from core.conversation.interruption_audit_v1 import audit as interruption

from core.conversation.teaching_meaning_v1 import extract_meaning


# ==========================================================
# TINY HARNESS
# ==========================================================

_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))

    return bool(passed)


# ==========================================================
# 08B — TURN SEMANTICS
# ==========================================================

SPEC_EXAMPLES = [
    # (expected, text)
    (TURN_QUESTION, "\u0631\u0627\u0628\u0637\u0647 \u0641\u0636\u0627\u06cc\u06cc \u06cc\u0639\u0646\u06cc \u0686\u06cc\u061f"),
    (TURN_QUESTION, "\u0631\u0627\u0628\u0637\u0647 \u0641\u0636\u0627\u06cc\u06cc \u06cc\u0639\u0646\u06cc \u0686\u06cc"),
    (TURN_TEACHING_STATEMENT, "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0627\u06cc\u062f \u0628\u0647 \u063a\u0630\u0627\u062e\u0648\u0631\u06cc \u0646\u0632\u062f\u06cc\u06a9 \u0628\u0627\u0634\u062f."),
    (TURN_TEACHING_STATEMENT, "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0647\u062a\u0631\u0647 \u0628\u0647 \u063a\u0630\u0627\u062e\u0648\u0631\u06cc \u0646\u0632\u062f\u06cc\u06a9 \u0628\u0627\u0634\u0647."),
    (TURN_CORRECTION, "\u0646\u0647\u060c \u0627\u06cc\u0646 \u0627\u0634\u062a\u0628\u0627\u0647\u0647."),
    (TURN_CORRECTION, "\u0646\u0647\u060c \u0627\u06cc\u0646 \u0642\u0633\u0645\u062a \u0627\u0634\u062a\u0628\u0627\u0647\u0647. \u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u062f\u0631 \u0627\u06cc\u0646 \u0645\u062b\u0627\u0644 \u0628\u0627\u06cc\u062f \u0628\u0647 \u063a\u0630\u0627\u062e\u0648\u0631\u06cc \u0646\u0632\u062f\u06cc\u06a9 \u0628\u0627\u0634\u0647."),
    (TURN_INSTRUCTION, "\u06cc\u06a9 \u062e\u0637 45 \u062f\u0631\u062c\u0647 \u0628\u06a9\u0634."),
    (TURN_CONFIRMATION_REQUEST, "\u0686\u06cc \u0627\u0632 \u062d\u0631\u0641 \u0645\u0646 \u0641\u0647\u0645\u06cc\u062f\u06cc\u061f"),
    (TURN_CONFIRMATION_REQUEST, "\u062d\u0627\u0644\u0627 \u0628\u06af\u0648 \u0627\u0632 \u0686\u06cc\u0632\u06cc \u06a9\u0647 \u06af\u0641\u062a\u0645 \u0686\u06cc \u0641\u0647\u0645\u06cc\u062f\u06cc."),
    (TURN_NORMAL_CONVERSATION, "\u0633\u0644\u0627\u0645\u060c \u0645\u0645\u0646\u0648\u0646 \u0627\u0632 \u06a9\u0645\u06a9\u062a"),
    (TURN_UNKNOWN, ""),
    # English equivalents
    (TURN_QUESTION, "What does spatial relationship mean?"),
    (TURN_TEACHING_STATEMENT, "The kitchen should be near the dining room."),
    (TURN_CORRECTION, "No, this is wrong."),
    (TURN_INSTRUCTION, "Draw a 45 degree line."),
    (TURN_CONFIRMATION_REQUEST, "What did you understand from what I said?"),
]


def test_spec_examples_classified():

    failures = []

    for expected, text in SPEC_EXAMPLES:

        result = classify_turn(text)

        if result.get("turn_kind") != expected:

            failures.append(
                {
                    "text": text,
                    "expected": expected,
                    "got": result.get("turn_kind"),
                }
            )

    return _check(
        "08B spec examples classified",
        not failures,
        failures,
    )


PARAPHRASES = {
    TURN_TEACHING_STATEMENT: [
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0627\u06cc\u062f \u062c\u0644\u0648\u06cc \u063a\u0630\u0627\u062e\u0648\u0631\u06cc \u0628\u0627\u0634\u0647.",
        "\u0628\u0647\u062a\u0631 \u0627\u0633\u062a \u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u062f\u0648\u0631 \u0627\u0632 \u067e\u0630\u06cc\u0631\u0627\u06cc\u06cc \u0628\u0627\u0634\u062f.",
        "\u0646\u0645\u0627\u06cc \u0634\u0645\u0627\u0644\u06cc \u0628\u0627\u06cc\u062f \u0627\u0632 \u0633\u0646\u06af \u0631\u0648\u0634\u0646 \u0628\u0627\u0634\u062f.",
        "\u0631\u0627\u0628\u0637\u0647 \u0641\u0636\u0627\u06cc\u06cc \u06cc\u0639\u0646\u06cc \u0627\u0631\u062a\u0628\u0627\u0637 \u0628\u06cc\u0646 \u0641\u0636\u0627\u0647\u0627.",
        "The entrance must be connected to the lobby.",
        "A bedroom should be away from the living room.",
        "Natural lighting is important in the living room.",
    ],
    TURN_INSTRUCTION: [
        "\u06cc\u06a9 \u0645\u0633\u062a\u0637\u06cc\u0644 \u0628\u06a9\u0634.",
        "\u067e\u0644\u0627\u0646 \u0631\u0627 \u062a\u063a\u06cc\u06cc\u0631 \u0628\u062f\u0647.",
        "\u06cc\u06a9 \u0631\u0646\u062f\u0631 \u0628\u0633\u0627\u0632.",
        "\u067e\u0646\u062c\u0631\u0647 \u0631\u0627 \u062d\u0630\u0641 \u06a9\u0646.",
        "Create a site plan.",
        "Remove the balcony.",
        "Summarize the current project.",
    ],
    TURN_CORRECTION: [
        "\u0627\u06cc\u0646 \u063a\u0644\u0637\u0647.",
        "\u0646\u0647\u060c \u062f\u0631\u0633\u062a \u0646\u06cc\u0633\u062a.",
        "\u0627\u06cc\u0646 \u0642\u0633\u0645\u062a \u0646\u0627\u062f\u0631\u0633\u062a \u0627\u0633\u062a.",
        "That is incorrect.",
        "This part is not correct.",
        "No, it is not right.",
    ],
    TURN_CONFIRMATION_REQUEST: [
        "\u0686\u06cc \u0641\u0647\u0645\u06cc\u062f\u06cc\u061f",
        "\u0627\u0632 \u062d\u0631\u0641 \u0645\u0646 \u0686\u0647 \u0641\u0647\u0645\u06cc\u062f\u06cc\u061f",
        "\u0645\u062a\u0648\u062c\u0647 \u0634\u062f\u06cc \u0686\u06cc \u06af\u0641\u062a\u0645\u061f",
        "What do you understand?",
        "Tell me what you understood.",
        "Repeat back what I said.",
    ],
}


def test_spec_examples_are_not_hardcoded_rules():

    """Different wordings of the same intent must classify the same.

    This is the proof that the classifier uses FEATURES, not the exact
    example sentences from the brief.
    """

    failures = []

    for expected, texts in PARAPHRASES.items():

        for text in texts:

            got = classify_turn(text).get("turn_kind")

            if got != expected:

                failures.append(
                    {"text": text, "expected": expected, "got": got}
                )

    return _check(
        "08B classifier is feature-based (paraphrases agree)",
        not failures,
        failures,
    )


def test_turn_kinds_complete():

    """PHASE 08 vocabulary must remain available.

    The vocabulary is allowed to GROW additively (Phase 09 added
    OFFER_TO_TEACH for teaching intent), so this asserts that every
    Phase 08 kind is still present rather than pinning the exact set.
    """

    required = {
        TURN_QUESTION,
        TURN_INSTRUCTION,
        TURN_CORRECTION,
        TURN_TEACHING_STATEMENT,
        TURN_CONFIRMATION_REQUEST,
        TURN_NORMAL_CONVERSATION,
        TURN_UNKNOWN,
    }

    missing = required - set(ALL_TURN_KINDS)

    return _check(
        "08B turn-kind vocabulary complete (additive growth allowed)",
        not missing,
        {"missing": sorted(missing), "all": list(ALL_TURN_KINDS)},
    )


def test_classifier_is_deterministic_and_provider_free():

    text = "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0627\u06cc\u062f \u0628\u0647 \u063a\u0630\u0627\u062e\u0648\u0631\u06cc \u0646\u0632\u062f\u06cc\u06a9 \u0628\u0627\u0634\u062f."

    runs = [json.dumps(classify_turn(text), sort_keys=True) for _ in range(5)]

    result = classify_turn(text)

    ok = (
        len(set(runs)) == 1
        and result.get("llm_used") is False
        and result.get("network_used") is False
        and result.get("provider") == "deterministic"
    )

    return _check(
        "08B deterministic + provider-free",
        ok,
        {"runs": len(set(runs))},
    )


# ==========================================================
# 08C — TEACHING CANDIDATE CONTRACT
# ==========================================================

def test_candidate_fields_present():

    candidate = build_candidate(
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0627\u06cc\u062f \u0628\u0647 \u063a\u0630\u0627\u062e\u0648\u0631\u06cc \u0646\u0632\u062f\u06cc\u06a9 \u0628\u0627\u0634\u062f.",
        project_id="project_test",
        source_turn_id="turn_test",
        source_type="text",
        language="fa",
        turn_kind=TURN_TEACHING_STATEMENT,
    )

    payload = candidate.to_dict()

    required = (
        "candidate_id",
        "project_id",
        "source_turn_id",
        "source_type",
        "language",
        "raw_statement",
        "normalized_meaning",
        "domain",
        "candidate_kind",
        "confidence",
        "status",
    )

    missing = [key for key in required if key not in payload]

    return _check(
        "08C candidate contract fields present",
        not missing,
        {"missing": missing},
    )


def test_candidate_status_vocabulary_is_closed():

    ok_allowed = set(ALLOWED_STATUSES) == {
        "observed", "needs_confirmation", "rejected"
    }

    rejected = []

    for status in FORBIDDEN_STATUSES:

        try:

            TeachingCandidate(status=status)

            rejected.append(status)

        except ValueError:

            pass

    return _check(
        "08C no learned / accepted_as_truth status",
        ok_allowed and not rejected,
        {"allowed_ok": ok_allowed, "accepted_forbidden": rejected},
    )


def test_candidate_only_for_teaching_and_correction():

    instruction = build_candidate(
        "\u06cc\u06a9 \u062e\u0637 45 \u062f\u0631\u062c\u0647 \u0628\u06a9\u0634.",
        turn_kind=TURN_INSTRUCTION,
    )

    question = build_candidate(
        "\u0631\u0627\u0628\u0637\u0647 \u0641\u0636\u0627\u06cc\u06cc \u06cc\u0639\u0646\u06cc \u0686\u06cc\u061f",
        turn_kind=TURN_QUESTION,
    )

    teaching = build_candidate(
        "The kitchen should be near the dining room.",
        turn_kind=TURN_TEACHING_STATEMENT,
    )

    return _check(
        "08C instruction/question produce no candidate",
        instruction is None and question is None and teaching is not None,
        {
            "instruction": instruction,
            "question": question,
            "teaching_is_none": teaching is None,
        },
    )


def test_no_promotion_path_exists():

    store = TeachingCandidateStoreV1()

    raised = False

    try:

        store.promote("project_test", "tc_x")

    except NotImplementedError:

        raised = True

    return _check(
        "08C promotion to permanent knowledge is refused",
        raised and PERMANENT_LEARNING_IMPLEMENTED is False,
        {"raised": raised},
    )


def test_store_records_and_never_learns():

    project = project_workspace.create("Phase08 Contract Store")

    project_id = project["project_id"]

    store = TeachingCandidateStoreV1()

    for text in (
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0627\u06cc\u062f \u0628\u0647 \u063a\u0630\u0627\u062e\u0648\u0631\u06cc \u0646\u0632\u062f\u06cc\u06a9 \u0628\u0627\u0634\u062f.",
        "The entrance must be connected to the lobby.",
    ):

        kind = classify_turn(text)["turn_kind"]

        candidate = build_candidate(
            text,
            project_id=project_id,
            language="fa",
            turn_kind=kind,
        )

        store.record(project_id, candidate, turn_kind=kind)

    candidates = store.candidates(project_id)

    ok = (
        len(candidates) == 2
        and all(
            c.get("status") in ALLOWED_STATUSES for c in candidates
        )
        and store.learned_count(project_id) == 0
        and store.assert_not_learned(project_id) is True
    )

    return _check(
        "08C store records candidates and never learns",
        ok,
        {
            "count": len(candidates),
            "learned": store.learned_count(project_id),
        },
    )


def test_store_project_isolation():

    project_a = project_workspace.create("Phase08 Isolation A")

    project_b = project_workspace.create("Phase08 Isolation B")

    store = TeachingCandidateStoreV1()

    store.record(
        project_a["project_id"],
        build_candidate(
            "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0627\u06cc\u062f \u0646\u0632\u062f\u06cc\u06a9 \u063a\u0630\u0627\u062e\u0648\u0631\u06cc \u0628\u0627\u0634\u062f.",
            project_id=project_a["project_id"],
            turn_kind=TURN_TEACHING_STATEMENT,
        ),
    )

    ok = (
        store.count(project_a["project_id"]) == 1
        and store.count(project_b["project_id"]) == 0
    )

    return _check(
        "08C/H project isolation (A cannot leak into B)",
        ok,
        {
            "a": store.count(project_a["project_id"]),
            "b": store.count(project_b["project_id"]),
        },
    )


def test_store_persists_across_instances():

    project = project_workspace.create("Phase08 Persistence")

    project_id = project["project_id"]

    TeachingCandidateStoreV1().record(
        project_id,
        build_candidate(
            "The kitchen should be near the dining room.",
            project_id=project_id,
            turn_kind=TURN_TEACHING_STATEMENT,
        ),
    )

    reloaded = TeachingCandidateStoreV1().candidates(project_id)

    ok = (
        len(reloaded) == 1
        and reloaded[0].get("status") in ALLOWED_STATUSES
    )

    return _check(
        "08H candidates persist and stay candidates",
        ok,
        {"count": len(reloaded)},
    )


# ==========================================================
# 08D — TEACH-BACK
# ==========================================================

def test_teach_back_distinguishes_understanding_from_learning():

    project = project_workspace.create("Phase08 TeachBack")

    project_id = project["project_id"]

    store = TeachingCandidateStoreV1()

    store.record(
        project_id,
        build_candidate(
            "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0647\u062a\u0631\u0647 \u0628\u0647 \u063a\u0630\u0627\u062e\u0648\u0631\u06cc \u0646\u0632\u062f\u06cc\u06a9 \u0628\u0627\u0634\u0647.",
            project_id=project_id,
            turn_kind=TURN_TEACHING_STATEMENT,
        ),
    )

    result = build_teach_back(
        project_id=project_id, language="fa", store=store
    )

    ok = (
        result.get("learned_anything") is False
        and result.get("permanent_learning_implemented") is False
        and result.get("distinguishes_understanding_from_learning") is True
        and bool(result.get("understanding_statement"))
        and bool(result.get("learning_statement"))
        and "permanent" in json.dumps(result, ensure_ascii=False).lower()
    )

    return _check(
        "08D teach-back separates 'understood' from 'learned'",
        ok,
        {
            "learned_anything": result.get("learned_anything"),
            "candidates": result.get("candidates_considered"),
        },
    )


def test_teach_back_is_truthful_when_empty():

    project = project_workspace.create("Phase08 TeachBack Empty")

    result = build_teach_back(
        project_id=project["project_id"], language="en"
    )

    ok = (
        result.get("candidates_considered") == 0
        and result.get("learned_anything") is False
        and bool(result.get("result"))
    )

    return _check(
        "08D teach-back is truthful with no candidates",
        ok,
        {"result": str(result.get("result"))[:80]},
    )


# ==========================================================
# 08E — LANGUAGE
# ==========================================================

def test_language_explicit_wins():

    project = project_workspace.create("Phase08 Lang Explicit")

    decision = resolve_conversation_language(
        project_id=project["project_id"],
        explicit="en",
        text="\u0633\u0644\u0627\u0645",
        stt_language="fa",
    )

    return _check(
        "08E explicit language wins",
        decision.get("language") == "en"
        and decision.get("source") == "explicit_request",
        decision,
    )


def test_language_project_state_beats_stt():

    project = project_workspace.create("Phase08 Lang Project")

    project_id = project["project_id"]

    set_project_language(project_id, "fa", source="explicit", locked=True)

    decision = resolve_conversation_language(
        project_id=project_id,
        text="hello there",
        stt_language="en",
    )

    return _check(
        "08E canonical project language beats STT",
        decision.get("language") == "fa"
        and decision.get("source") == "project_conversation_state",
        decision,
    )


def test_stt_is_lowest_trust():

    project = project_workspace.create("Phase08 Lang STT")

    decision = resolve_conversation_language(
        project_id=project["project_id"],
        text="",
        stt_language="fa",
        input_type="voice",
    )

    return _check(
        "08E STT language is lowest trust",
        decision.get("language") == "fa"
        and decision.get("low_trust") is True
        and decision.get("stt_dependent") is True,
        decision,
    )


def test_typed_persian_needs_no_stt():

    project = project_workspace.create("Phase08 Lang Typed")

    decision = resolve_conversation_language(
        project_id=project["project_id"],
        text="\u0631\u0627\u0628\u0637\u0647 \u0641\u0636\u0627\u06cc\u06cc \u06cc\u0639\u0646\u06cc \u0686\u06cc\u061f",
        stt_language=None,
    )

    return _check(
        "08E typed Persian resolves without STT",
        decision.get("language") == "fa"
        and decision.get("source") == "text_script"
        and decision.get("stt_dependent") is False,
        decision,
    )


# ==========================================================
# 08G — EXECUTION BOUNDARY
# ==========================================================

def test_execution_boundary_declaration():

    declaration = boundary_describe()

    ok = (
        declaration["declaration"][CAP_LEARN]["implemented"] is False
        and declaration["declaration"][CAP_VERIFY]["implemented"] is False
        and declaration["declaration"][CAP_UNDERSTAND]["implemented"] is True
        and declaration["declaration"][CAP_EXECUTE].get(
            "owned_by_phase_08"
        ) is False
        and declaration["phase_08_execution_implemented"] is False
    )

    return _check(
        "08G execution boundary declared, not implemented",
        ok,
        {
            "learn": declaration["declaration"][CAP_LEARN]["implemented"],
            "execute_owner_08": declaration["declaration"][CAP_EXECUTE].get(
                "owned_by_phase_08"
            ),
        },
    )


def test_instruction_is_action_not_knowledge():

    ok = (
        capability_for_turn(TURN_INSTRUCTION) == CAP_EXECUTE
        and is_action_turn(TURN_INSTRUCTION) is True
        and is_knowledge_turn(TURN_INSTRUCTION) is False
        and capability_for_turn(TURN_TEACHING_STATEMENT) == CAP_UNDERSTAND
        and is_knowledge_turn(TURN_TEACHING_STATEMENT) is True
    )

    return _check(
        "08G instruction != knowledge",
        ok,
        {
            "instruction": capability_for_turn(TURN_INSTRUCTION),
            "teaching": capability_for_turn(TURN_TEACHING_STATEMENT),
        },
    )


# ==========================================================
# 08F — INTERRUPTION AUDIT
# ==========================================================

def test_interruption_audit_is_honest():

    result = interruption()

    ok = (
        result.get("barge_in_supported") is False
        and result.get("fake_interruption_built") is False
        and result.get("voice_07_redesigned") is False
        and len(result.get("missing_pieces") or []) >= 3
    )

    return _check(
        "08F interruption audit is read-only and honest",
        ok,
        {"missing": len(result.get("missing_pieces") or [])},
    )


# ==========================================================
# MEANING
# ==========================================================

def test_meaning_is_deterministic_restatement():

    text = "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0627\u06cc\u062f \u0628\u0647 \u063a\u0630\u0627\u062e\u0648\u0631\u06cc \u0646\u0632\u062f\u06cc\u06a9 \u0628\u0627\u0634\u062f."

    meaning = extract_meaning(text, turn_kind=TURN_TEACHING_STATEMENT)

    ok = (
        meaning.get("domain") == "spatial_relationship"
        and "kitchen" in (meaning.get("entities") or [])
        and "dining" in (meaning.get("entities") or [])
        and meaning.get("deterministic") is True
        and meaning.get("llm_used") is False
    )

    return _check(
        "08C deterministic meaning normalization",
        ok,
        {
            "domain": meaning.get("domain"),
            "entities": meaning.get("entities"),
        },
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
    print("  PHASE 08 — TEACHING FOUNDATION CONTRACT TESTS")
    print("=" * 70)

    for test in _all_tests():

        test()

    failed = [r for r in _RESULTS if not r[1]]

    for name, passed, detail in _RESULTS:

        print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

        if not passed:

            print("        ", json.dumps(detail, ensure_ascii=False)[:400])

    print("-" * 70)
    print(
        "  %d/%d PASS" % (len(_RESULTS) - len(failed), len(_RESULTS))
    )
    print("=" * 70 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())
