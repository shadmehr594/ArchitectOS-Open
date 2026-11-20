# ==========================================================
# PHASE 09 — ARCHITECTURAL LEARNING BRIDGE CONTRACT TESTS
#
# ISOLATED CONTRACT tests. They are NOT the acceptance proof: real
# acceptance runs against the live runtime path
# (tools/run_architectural_learning_bridge_09_acceptance.py).
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_architectural_learning_bridge_09.py
#   .venv/Scripts/python.exe tests/test_architectural_learning_bridge_09.py
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
    tempfile.gettempdir(), "architectos_phase09_contract"
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


from core.conversation.turn_semantics_v1 import (
    classify_turn,
    ALL_TURN_KINDS,
    TEACHING_INTENT,
    TURN_OFFER_TO_TEACH,
    TURN_INSTRUCTION,
    TURN_QUESTION,
    TURN_TEACHING_STATEMENT,
    TURN_CORRECTION,
    teaching_aspects,
    PERSIAN_VERB_STEMS,
)

from core.conversation.execution_boundary_v1 import (
    capability_for_turn,
    is_action_turn,
    CAP_EXECUTE,
    CAP_UNDERSTAND,
)

from core.conversation.teaching_meaning_v1 import (
    extract_meaning,
    ALL_KNOWLEDGE_CLASSES,
    ALL_SCOPES,
    ALL_PROVENANCES,
)

from core.conversation.teaching_candidate_v1 import (
    TeachingCandidate,
    build_candidate,
    teaching_candidate_store,
    ALLOWED_STATUSES,
    FORBIDDEN_STATUSES,
    KNOWLEDGE_CLASSES,
    SCOPES,
    PROVENANCES,
    PERMANENT_LEARNING_IMPLEMENTED,
)

from core.conversation.teach_back_v1 import (
    build_teaching_elicitation,
    build_teach_back,
)

from core.conversation.knowledge_read_bridge_v1 import (
    knowledge_read_bridge,
)

from core.conversation.knowledge_promotion_bridge_v1 import (
    knowledge_promotion_bridge,
    PROMOTION_IMPLEMENTED,
    STAGE_AWAITING_APPROVAL,
)

from core.conversation.teaching_storage_guard_v1 import (
    teaching_storage_guard,
    GLOBAL_MEMORY_DIR,
)


# ==========================================================
# TINY HARNESS
# ==========================================================

_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))

    return bool(passed)


# ==========================================================
# 09-1 TEACHING INTENT / ELICITATION
# ==========================================================

TEACHING_OFFERS = [
    "\u0645\u06cc \u062e\u0648\u0627\u0647\u0645 \u0631\u0627\u0647 \u067e\u0644\u0647 \u0631\u0627 \u0628\u0647 \u062a\u0648 \u06cc\u0627\u062f \u0628\u062f\u0647\u0645",
    "\u0645\u06cc \u062e\u0648\u0627\u0647\u0645 \u0628\u0647 \u062a\u0648 \u0631\u0627\u0647 \u067e\u0644\u0647 \u06cc\u0627\u062f \u0628\u062f\u0647\u0645",
    "\u0631\u0627\u0647 \u067e\u0644\u0647 \u0631\u0627 \u0628\u0647 \u0645\u0646 \u06cc\u0627\u062f \u0628\u062f\u0647",
    "\u0645\u06cc \u062e\u0648\u0627\u0647\u0645 \u0631\u0627\u0647 \u067e\u0644\u0647 \u06cc\u0627\u062f \u0628\u06af\u06cc\u0631\u0645",
    "I want to teach you about staircases",
    "I want to learn about staircases",
    "Can I teach you something about stairs?",
]


def test_teaching_intent_detected():

    failures = []

    for text in TEACHING_OFFERS:

        result = classify_turn(text)

        if result.get("turn_kind") != TURN_OFFER_TO_TEACH:

            failures.append(
                {"text": text, "got": result.get("turn_kind")}
            )

    return _check(
        "09-1 teaching intent detected",
        not failures,
        failures,
    )


def test_teaching_intent_never_routes_to_execute():

    failures = []

    for text in TEACHING_OFFERS:

        result = classify_turn(text)

        if (
            capability_for_turn(result.get("turn_kind")) == CAP_EXECUTE
            or result.get("is_action_request") is True
            or result.get("may_produce_candidate") is True
            or result.get("is_teaching_intent") is not True
            or result.get("wants_elicitation") is not True
        ):

            failures.append(
                {
                    "text": text,
                    "capability": capability_for_turn(
                        result.get("turn_kind")
                    ),
                    "is_action": result.get("is_action_request"),
                }
            )

    return _check(
        "09-1 teaching intent NEVER routes to EXECUTE",
        not failures,
        failures,
    )


def test_teaching_intent_alias_and_vocabulary():

    ok = (
        TEACHING_INTENT == TURN_OFFER_TO_TEACH
        and TURN_OFFER_TO_TEACH in ALL_TURN_KINDS
        and not is_action_turn(TURN_OFFER_TO_TEACH)
    )

    return _check(
        "09-1 teaching intent alias + vocabulary",
        ok,
        {"alias": TEACHING_INTENT, "kinds": list(ALL_TURN_KINDS)},
    )


def test_design_request_is_not_teaching_intent():

    """A volitional NON-teaching request must not become teaching intent."""

    cases = [
        ("\u06cc\u06a9 \u0631\u0646\u062f\u0631 \u0628\u0633\u0627\u0632", TURN_INSTRUCTION),
        ("Draw a 45 degree line.", TURN_INSTRUCTION),
        ("Remove the balcony.", TURN_INSTRUCTION),
    ]

    failures = []

    for text, expected in cases:

        got = classify_turn(text).get("turn_kind")

        if got != expected:

            failures.append(
                {"text": text, "expected": expected, "got": got}
            )

    return _check(
        "09-1 non-teaching requests are unaffected",
        not failures,
        failures,
    )


def test_elicitation_asks_which_aspect():

    result = build_teaching_elicitation(
        topic="\u0631\u0627\u0647\u200c\u067e\u0644\u0647", language="fa"
    )

    text = result.get("result") or ""

    aspects = teaching_aspects("fa")

    labels = [a["label"] for a in aspects]

    ok = (
        len(aspects) == 6
        and "\u06a9\u062f\u0627\u0645 \u0628\u062e\u0634" in text
        and all(label in text for label in labels)
        and result.get("routed_to_execute") is False
        and result.get("candidate_created") is False
        and result.get("learned_anything") is False
    )

    return _check(
        "09-1 elicitation asks which aspect (6 options)",
        ok,
        {"aspects": labels, "text": text[:160]},
    )


def test_elicitation_english():

    result = build_teaching_elicitation(
        topic="stair", language="en"
    )

    ok = (
        "Which aspect" in (result.get("result") or "")
        and len(result.get("aspects") or []) == 6
    )

    return _check(
        "09-1 elicitation works in English too",
        ok,
        (result.get("result") or "")[:140],
    )


# ==========================================================
# 09-2 PERSIAN IMPERATIVE FIX
# ==========================================================

MUST_BE_TEACHING = [
    "\u0628\u0627\u0645 \u0628\u0627\u06cc\u062f \u0634\u06cc\u0628 \u0645\u0646\u0627\u0633\u0628 \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u062f",
    "\u0646\u0645\u0627 \u06cc\u0639\u0646\u06cc \u0633\u0637\u062d \u0628\u06cc\u0631\u0648\u0646\u06cc \u0633\u0627\u062e\u062a\u0645\u0627\u0646",
    "\u0628\u0627\u063a \u0628\u0627\u06cc\u062f \u067e\u0634\u062a \u0633\u0627\u062e\u062a\u0645\u0627\u0646 \u0642\u0631\u0627\u0631 \u0628\u06af\u06cc\u0631\u062f",
    "\u0628\u0644\u0648\u06a9 \u0628\u0646\u062f\u06cc \u0641\u0636\u0627\u0647\u0627 \u0628\u0627\u06cc\u062f \u0645\u0646\u0637\u0642\u06cc \u0628\u0627\u0634\u062f",
    "\u0628\u0631\u0646\u0627\u0645\u0647 \u0641\u06cc\u0632\u06cc\u06a9\u06cc \u067e\u0631\u0648\u0698\u0647 \u0628\u0627\u06cc\u062f \u06a9\u0627\u0645\u0644 \u0628\u0627\u0634\u062f",
    "\u0628\u0647\u06cc\u0646\u0647 \u0633\u0627\u0632\u06cc \u0646\u0648\u0631 \u0637\u0628\u06cc\u0639\u06cc \u0645\u0647\u0645 \u0627\u0633\u062a",
    "\u0628\u0646\u0627 \u0628\u0627\u06cc\u062f \u0628\u0627 \u0627\u0642\u0644\u06cc\u0645 \u0647\u0645\u0627\u0647\u0646\u06af \u0628\u0627\u0634\u062f",
    "\u0628\u062f\u0646\u0647 \u0646\u0645\u0627 \u0628\u0627\u06cc\u062f \u0627\u0632 \u0633\u0646\u06af \u0628\u0627\u0634\u062f",
    "\u0628\u0627\u0644\u06a9\u0646 \u0628\u0627\u06cc\u062f \u062f\u0633\u062a\u0631\u0633\u06cc \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u062f",
    "\u0645\u0633\u06a9\u0646 \u0628\u0627\u06cc\u062f \u0645\u0642\u0631\u0648\u0646 \u0628\u0647 \u0635\u0631\u0641\u0647 \u0628\u0627\u0634\u062f",
    "\u0628\u0627\u0632\u0634\u0648 \u0628\u0627\u06cc\u062f \u0646\u0648\u0631 \u06a9\u0627\u0641\u06cc \u0628\u062f\u0647\u062f",
]


def test_persian_b_nouns_are_not_imperatives():

    failures = []

    for text in MUST_BE_TEACHING:

        result = classify_turn(text)

        if result.get("turn_kind") != TURN_TEACHING_STATEMENT:

            failures.append(
                {
                    "text": text,
                    "got": result.get("turn_kind"),
                    "persian_imperative": (
                        result.get("features") or {}
                    ).get("persian_imperative"),
                }
            )

    return _check(
        "09-2 Persian ب-nouns are NOT imperatives",
        not failures,
        failures,
    )


REAL_IMPERATIVES = [
    "\u06cc\u06a9 \u062e\u0637 45 \u062f\u0631\u062c\u0647 \u0628\u06a9\u0634.",
    "\u06cc\u06a9 \u0645\u0633\u062a\u0637\u06cc\u0644 \u0628\u06a9\u0634.",
    "\u067e\u0644\u0627\u0646 \u0631\u0627 \u062a\u063a\u06cc\u06cc\u0631 \u0628\u062f\u0647.",
    "\u06cc\u06a9 \u0631\u0646\u062f\u0631 \u0628\u0633\u0627\u0632.",
    "\u067e\u0646\u062c\u0631\u0647 \u0631\u0627 \u062d\u0630\u0641 \u06a9\u0646.",
    "\u0628\u0627\u0645 \u0631\u0627 \u0628\u0686\u0631\u062e\u0627\u0646",
    "\u0646\u0645\u0627 \u0631\u0627 \u0628\u062a\u0631\u0627\u0634",
    "\u0627\u0628\u0639\u0627\u062f \u0631\u0627 \u0628\u0633\u0646\u062c",
    "\u067e\u0644\u0627\u0646 \u0631\u0627 \u0628\u06af\u0631\u062f\u0627\u0646",
    "\u062d\u0630\u0641 \u06a9\u0646",
    "\u062a\u063a\u06cc\u06cc\u0631\u0628\u062f\u0647",
    "\u0631\u0633\u0645 \u06a9\u0646",
]


def test_real_imperatives_still_detected():

    failures = []

    for text in REAL_IMPERATIVES:

        result = classify_turn(text)

        if result.get("turn_kind") != TURN_INSTRUCTION:

            failures.append(
                {"text": text, "got": result.get("turn_kind")}
            )

    return _check(
        "09-2 real imperatives still classify as INSTRUCTION",
        not failures,
        failures,
    )


def test_no_blanket_b_prefix_rule():

    """The unsafe rule is gone: it must not be the evidence."""

    # These are the false positives the old rule produced. None may be
    # an instruction, and none may be flagged as a Persian imperative.
    for text in MUST_BE_TEACHING:

        features = classify_turn(text).get("features") or {}

        if features.get("persian_imperative"):

            return _check(
                "09-2 no blanket 'ب' prefix rule",
                False,
                {"text": text, "features": features},
            )

    ok = bool(PERSIAN_VERB_STEMS)

    return _check(
        "09-2 no blanket 'ب' prefix rule (stem evidence required)",
        ok,
        {"stems": len(PERSIAN_VERB_STEMS)},
    )


# ==========================================================
# 09-3 EXTENDED CANDIDATE CONTRACT
# ==========================================================

def test_candidate_has_learning_taxonomy():

    candidate = build_candidate(
        "\u0628\u0627\u0645 \u0628\u0627\u06cc\u062f \u0634\u06cc\u0628 \u0645\u0646\u0627\u0633\u0628 \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u062f",
        project_id="project_x",
        source_turn_id="turn_x",
        language="fa",
        turn_kind=TURN_TEACHING_STATEMENT,
    )

    payload = candidate.to_dict()

    required = (
        "knowledge_class",
        "scope",
        "domain",
        "provenance",
        "confidence",
        "confidence_kind",
        "status",
    )

    missing = [key for key in required if key not in payload]

    ok = (
        not missing
        and payload["knowledge_class"] in ALL_KNOWLEDGE_CLASSES
        and payload["scope"] in ALL_SCOPES
        and payload["provenance"] in ALL_PROVENANCES
        and payload["confidence_kind"] == "learning_state"
    )

    return _check(
        "09-3 candidate carries knowledge_class/scope/domain/provenance",
        ok,
        {"missing": missing, "payload": payload},
    )


def test_knowledge_class_separates_categories():

    """A-E must NOT collapse into one category."""

    cases = [
        ("\u062d\u062f\u0627\u0642\u0644 \u0627\u0631\u062a\u0641\u0627\u0639 \u067e\u0627\u06af\u0631\u062f \u067e\u0644\u0647 \u0628\u0627\u06cc\u062f \u062f\u0631 \u0645\u062d\u062f\u0648\u062f\u0647 \u0645\u062c\u0627\u0632 \u0628\u0627\u0634\u062f.", "ARCHITECTURAL_FACT"),
        ("\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u0647\u0627 \u0645\u0639\u0645\u0648\u0644\u0627 \u0628\u0627\u06cc\u062f \u0627\u0632 \u0641\u0636\u0627\u0647\u0627\u06cc \u0639\u0645\u0648\u0645\u06cc \u062c\u062f\u0627 \u0628\u0627\u0634\u0646\u062f.", "PATTERN"),
        ("\u0645\u0646 \u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0627\u0632 \u0631\u0627 \u062a\u0631\u062c\u06cc\u062d \u0645\u06cc \u062f\u0647\u0645.", "PREFERENCE"),
        ("\u0627\u06cc\u0646 \u067e\u0631\u0648\u0698\u0647 \u0628\u0647 \u06cc\u06a9 \u0648\u0631\u0648\u062f\u06cc \u062c\u062f\u0627\u06af\u0627\u0646\u0647 \u0646\u06cc\u0627\u0632 \u062f\u0627\u0631\u062f.", "PROJECT_DECISION"),
        ("\u0628\u0627\u0645 \u0628\u0627\u06cc\u062f \u0634\u06cc\u0628 \u0645\u0646\u0627\u0633\u0628 \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u062f", "DESIGN_RULE"),
    ]

    failures = []

    seen = set()

    for text, expected in cases:

        meaning = extract_meaning(text, turn_kind=TURN_TEACHING_STATEMENT)

        got = meaning.get("knowledge_class")

        seen.add(got)

        if got != expected:

            failures.append(
                {"text": text, "expected": expected, "got": got}
            )

    return _check(
        "09-3 knowledge_class separates fact/pattern/preference/project/rule",
        not failures and len(seen) >= 4,
        {"failures": failures, "distinct": sorted(seen)},
    )


def test_scope_is_conservative():

    project = extract_meaning(
        "\u0627\u06cc\u0646 \u067e\u0631\u0648\u0698\u0647 \u0628\u0647 \u06cc\u06a9 \u0648\u0631\u0648\u062f\u06cc \u062c\u062f\u0627\u06af\u0627\u0646\u0647 \u0646\u06cc\u0627\u0632 \u062f\u0627\u0631\u062f.",
        turn_kind=TURN_TEACHING_STATEMENT,
    )

    general = extract_meaning(
        "\u0628\u0627\u0645 \u0628\u0627\u06cc\u062f \u0634\u06cc\u0628 \u0645\u0646\u0627\u0633\u0628 \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u062f",
        turn_kind=TURN_TEACHING_STATEMENT,
    )

    observation = extract_meaning(
        "\u0627\u06cc\u0646 \u0639\u06a9\u0633 \u0627\u0645\u0631\u0648\u0632 \u0646\u0648\u0631 \u062e\u0648\u0628\u06cc \u062f\u0627\u0631\u062f.",
        turn_kind=TURN_TEACHING_STATEMENT,
    )

    ok = (
        project.get("scope") == "CURRENT_PROJECT"
        and general.get("scope") == "GENERAL"
        and observation.get("scope") == "CURRENT_PROJECT"
    )

    return _check(
        "09-3 scope defaults to CURRENT_PROJECT (safe direction)",
        ok,
        {
            "project": project.get("scope"),
            "general": general.get("scope"),
            "observation": observation.get("scope"),
        },
    )


def test_provenance_external_reference():

    cited = extract_meaning(
        "\u0637\u0628\u0642 \u0645\u0628\u062d\u062b \u0686\u0647\u0627\u0631\u0645\u060c \u0627\u0631\u062a\u0641\u0627\u0639 \u067e\u0627\u06af\u0631\u062f \u0628\u0627\u06cc\u062f \u062d\u062f\u0627\u0642\u0644 \u0628\u0627\u0634\u062f.",
        turn_kind=TURN_TEACHING_STATEMENT,
    )

    taught = extract_meaning(
        "\u0628\u0627\u0645 \u0628\u0627\u06cc\u062f \u0634\u06cc\u0628 \u0645\u0646\u0627\u0633\u0628 \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u062f",
        turn_kind=TURN_TEACHING_STATEMENT,
    )

    ok = (
        cited.get("provenance") == "EXTERNAL_REFERENCE"
        and taught.get("provenance") == "HUMAN_TEACHER"
    )

    return _check(
        "09-3 provenance distinguishes human teacher / external reference",
        ok,
        {
            "cited": cited.get("provenance"),
            "taught": taught.get("provenance"),
        },
    )


def test_statuses_still_closed_and_promotion_impossible():

    rejected = []

    for status in FORBIDDEN_STATUSES:

        try:

            TeachingCandidate(status=status)

            rejected.append(status)

        except ValueError:

            pass

    ok = (
        set(ALLOWED_STATUSES) == {
            "observed", "needs_confirmation", "rejected"
        }
        and not rejected
        and PERMANENT_LEARNING_IMPLEMENTED is False
        and set(KNOWLEDGE_CLASSES) == set(ALL_KNOWLEDGE_CLASSES)
        and set(SCOPES) == set(ALL_SCOPES)
        and set(PROVENANCES) == set(ALL_PROVENANCES)
    )

    return _check(
        "09-3 statuses closed, promotion impossible",
        ok,
        {"accepted_forbidden": rejected},
    )


# ==========================================================
# 09-4 READ BRIDGE
# ==========================================================

def test_read_bridge_is_read_only():

    report = knowledge_read_bridge.read_report()

    ok = (
        report.get("read_only") is True
        and report.get("writes_performed") == 0
        and report.get("source_count") >= 8
        and all(s.get("exists") for s in report["sources"])
        and knowledge_read_bridge.assert_read_only() is True
    )

    return _check(
        "09-4 read bridge is read-only and all sources present",
        ok,
        {
            "sources": report.get("source_count"),
            "missing": [
                s["id"] for s in report["sources"] if not s.get("exists")
            ],
        },
    )


def test_read_bridge_refuses_writes():

    raised = False

    try:

        knowledge_read_bridge.write({"spaces": {}})

    except PermissionError:

        raised = True

    ok = (
        raised
        and knowledge_read_bridge.read_report()["writes_performed"] == 0
    )

    return _check(
        "09-4 read bridge refuses every write",
        ok,
        {"raised": raised},
    )


def test_read_bridge_returns_deep_copies():

    first = knowledge_read_bridge.spaces()

    if not first:

        return _check("09-4 read bridge deep copies", False, "no spaces")

    key = sorted(first.keys())[0]

    first[key]["zone"] = "MUTATED_BY_TEST"

    second = knowledge_read_bridge.spaces()

    ok = second[key].get("zone") != "MUTATED_BY_TEST"

    return _check(
        "09-4 read bridge returns deep copies (corpus cannot be mutated)",
        ok,
        {"key": key, "zone": second[key].get("zone")},
    )


def test_read_bridge_reads_corpus():

    patterns = knowledge_read_bridge.patterns()

    negative = knowledge_read_bridge.negative_patterns()

    registry = knowledge_read_bridge.learning_registry()

    zones = knowledge_read_bridge.space_zones()

    lookup = knowledge_read_bridge.lookup_term(
        "\u0631\u0627\u0647 \u067e\u0644\u0647"
    )

    space_knowledge = knowledge_read_bridge.space_knowledge()

    ok = (
        len(patterns) >= 10
        and len(negative) >= 5
        and len(registry) >= 10
        and len(zones) >= 5
        and lookup is not None
        and space_knowledge.get("available") is True
        and len(space_knowledge.get("space_specs") or {}) >= 10
    )

    return _check(
        "09-4 read bridge reads ontology / patterns / registry / space knowledge",
        ok,
        {
            "patterns": len(patterns),
            "negative": len(negative),
            "registry": len(registry),
            "zones": len(zones),
            "lookup": lookup,
        },
    )


# ==========================================================
# 09-5 WRITE BRIDGE (PROMOTION PREPARATION)
# ==========================================================

def _make_project_candidate(name):

    project = project_workspace.create(name)

    project_id = project["project_id"]

    candidate = build_candidate(
        "\u0628\u0627\u0645 \u0628\u0627\u06cc\u062f \u0634\u06cc\u0628 \u0645\u0646\u0627\u0633\u0628 \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u062f",
        project_id=project_id,
        language="fa",
        turn_kind=TURN_TEACHING_STATEMENT,
    )

    stored = teaching_candidate_store.record(
        project_id, candidate, turn_kind=TURN_TEACHING_STATEMENT
    )

    return project_id, stored


def test_promotion_is_not_implemented():

    raised = False

    try:

        knowledge_promotion_bridge.promote("pr_x", "project_x")

    except NotImplementedError:

        raised = True

    ok = (
        raised
        and PROMOTION_IMPLEMENTED is False
        and knowledge_promotion_bridge.assert_no_direct_path() is True
        and knowledge_promotion_bridge.status().get(
            "direct_candidate_to_knowledge_path"
        ) is False
    )

    return _check(
        "09-5 promotion is NOT implemented (no direct path)",
        ok,
        {"raised": raised},
    )


def test_promotion_request_is_recorded_not_executed():

    project_id, candidate = _make_project_candidate(
        "Phase09 Promotion Request"
    )

    result = knowledge_promotion_bridge.request_promotion(
        candidate["candidate_id"],
        project_id,
        target_registry="human_architectural_learning_registry_v1",
    )

    request = result.get("request") or {}

    ok = (
        result.get("status") == "success"
        and request.get("stage") == STAGE_AWAITING_APPROVAL
        and request.get("promoted") is False
        and request.get("approved") is False
        and result.get("promotion_implemented") is False
        and result.get("knowledge_registry_written") is False
        and result.get("validation", {}).get("passed") is True
    )

    return _check(
        "09-5 promotion request recorded as awaiting approval, not executed",
        ok,
        {
            "stage": request.get("stage"),
            "promoted": request.get("promoted"),
            "blockers": result.get("validation", {}).get("blockers"),
        },
    )


def test_promotion_forbidden_target_refused():

    project_id, candidate = _make_project_candidate(
        "Phase09 Forbidden Target"
    )

    result = knowledge_promotion_bridge.request_promotion(
        candidate["candidate_id"],
        project_id,
        target_registry="memory/chat_memory.json",
    )

    ok = (
        result.get("status") == "error"
        and result.get("error") == "forbidden_target"
        and result.get("promotion_implemented") is False
    )

    return _check(
        "09-5 global-memory target is refused",
        ok,
        result,
    )


def test_validation_rejects_incomplete_candidate():

    validation = knowledge_promotion_bridge.validate_candidate(
        {
            "candidate_id": "tc_bad",
            "project_id": "project_x",
            "raw_statement": "x",
            "status": "observed",
            "knowledge_class": "UNKNOWN",
            "scope": "CURRENT_PROJECT",
            "provenance": "HUMAN_TEACHER",
            "domain": "unknown",
        },
        project_id="project_x",
    )

    ok = (
        validation.get("passed") is False
        and "knowledge_class_known" in validation.get("blockers", [])
        and "domain_present" in validation.get("blockers", [])
        and validation.get("read_only") is True
    )

    return _check(
        "09-5 validation blocks an unusable candidate",
        ok,
        {"blockers": validation.get("blockers")},
    )


# ==========================================================
# 09-6 MEMORY SAFETY
# ==========================================================

def test_global_memory_is_clean():

    audit = teaching_storage_guard.audit()

    ok = (
        audit.get("global_memory_clean") is True
        and not audit.get("leaked_into_global_memory")
        and audit.get("teaching_storage_is_project_scoped") is True
        and all(
            not f.get("contains_teaching_data")
            for f in audit["global_memory_files"]
        )
    )

    return _check(
        "09-6 global memory contains NO teaching data",
        ok,
        {"leaked": audit.get("leaked_into_global_memory")},
    )


def test_global_memory_write_is_refused():

    raised = 0

    for path in (
        os.path.join(GLOBAL_MEMORY_DIR, "chat_memory.json"),
        os.path.join(GLOBAL_MEMORY_DIR, "cognitive_memory_v66.json"),
    ):

        try:

            teaching_storage_guard.assert_not_global_memory(path)

        except PermissionError:

            raised += 1

    return _check(
        "09-6 writing teaching data to global memory is refused",
        raised == 2,
        {"refused": raised},
    )


def test_teaching_storage_path_is_project_scoped():

    project_id, _candidate = _make_project_candidate(
        "Phase09 Storage Scope"
    )

    root = teaching_storage_guard.allowed_root(project_id)

    candidates = os.path.join(root, "teaching_candidates.json")

    outside = os.path.join(_TEMP_ROOT, "teaching_candidates.json")

    ok = (
        teaching_storage_guard.is_allowed_path(project_id, candidates)
        and not teaching_storage_guard.is_allowed_path(project_id, outside)
        and root.startswith(
            project_workspace.project_dir(project_id)
        )
    )

    return _check(
        "09-6 teaching storage is project-scoped only",
        ok,
        {"root": root, "outside_allowed": False},
    )


def test_project_isolation_09():

    project_a = project_workspace.create("Phase09 Isolation A")

    project_b = project_workspace.create("Phase09 Isolation B")

    teaching_candidate_store.record(
        project_a["project_id"],
        build_candidate(
            "\u0628\u0627\u0645 \u0628\u0627\u06cc\u062f \u0634\u06cc\u0628 \u0645\u0646\u0627\u0633\u0628 \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u062f",
            project_id=project_a["project_id"],
            turn_kind=TURN_TEACHING_STATEMENT,
        ),
    )

    candidates_a = teaching_candidate_store.candidates(
        project_a["project_id"]
    )

    candidates_b = teaching_candidate_store.candidates(
        project_b["project_id"]
    )

    ids_a = {c.get("candidate_id") for c in candidates_a}

    ids_b = {c.get("candidate_id") for c in candidates_b}

    teach_back_b = build_teach_back(
        project_b["project_id"], "fa"
    )

    ok = (
        len(candidates_a) == 1
        and len(candidates_b) == 0
        and not (ids_a & ids_b)
        and teach_back_b.get("candidates_considered") == 0
    )

    return _check(
        "09-6 project isolation (A never appears in B)",
        ok,
        {"a": len(candidates_a), "b": len(candidates_b)},
    )


# ==========================================================
# 09 — NO CURRICULUM STARTED
# ==========================================================

def test_no_curriculum_module_added():

    """Phase 09 must NOT have started a curriculum."""

    forbidden = (
        "curriculum",
        "lesson",
        "exercise",
        "bubble_diagram",
        "adjacency_matrix",
        "rplan",
        "layout_generation",
    )

    conversation_dir = os.path.join(ROOT, "core", "conversation")

    hits = []

    for name in os.listdir(conversation_dir):

        if not name.endswith(".py"):

            continue

        lowered = name.lower()

        for token in forbidden:

            if token in lowered:

                hits.append(name)

    return _check(
        "09 curriculum NOT started (no curriculum module exists)",
        not hits,
        {"hits": hits},
    )


def test_candidate_still_never_learned():

    project_id, candidate = _make_project_candidate(
        "Phase09 Never Learned"
    )

    candidates = teaching_candidate_store.candidates(project_id)

    ok = (
        candidates
        and all(
            c.get("status") in ALLOWED_STATUSES
            and c.get("is_learned_knowledge") is False
            and c.get("is_permanent") is False
            for c in candidates
        )
        and teaching_candidate_store.learned_count(project_id) == 0
        and teaching_candidate_store.assert_not_learned(project_id) is True
    )

    return _check(
        "09 candidate can never become learned knowledge",
        ok,
        {"count": len(candidates)},
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
    print("  PHASE 09 — ARCHITECTURAL LEARNING BRIDGE CONTRACT TESTS")
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
