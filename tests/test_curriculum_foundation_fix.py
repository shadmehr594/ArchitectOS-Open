# ==========================================================
# ARCHITECTURAL CURRICULUM FOUNDATION FIX — CONTRACT TESTS
#
# ISOLATED CONTRACT tests for:
#   1. knowledge_class taxonomy separation (incl. DEFINITION)
#   2. Persian teaching statement classification
#   3. PATTERN detection without a normative marker
#   4. Persian definitional detection (است / هست / یعنی)
#   5. Curriculum Sequencer foundation
#
# These are NOT the acceptance proof: acceptance runs against the live
# runtime path (tools/run_curriculum_foundation_fix_acceptance.py).
#
# Deliberately NOT tested here because the phase forbids them:
#   geometry, CAD, BIM, IFC, renders, layout generation.
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_curriculum_foundation_fix.py
#   .venv/Scripts/python.exe tests/test_curriculum_foundation_fix.py
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
    tempfile.gettempdir(), "architectos_curriculum_foundation"
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
    extract_features,
    TURN_TEACHING_STATEMENT,
    PATTERN_MARKERS,
    DECISION_MARKERS,
    PERSIAN_COPULA_TOKENS,
    MIN_COPULA_DEFINITION_TOKENS,
    contains_any,
)

from core.conversation.teaching_meaning_v1 import (
    extract_meaning,
    ALL_KNOWLEDGE_CLASSES,
    ALL_SCOPES,
    KNOWLEDGE_ARCHITECTURAL_FACT,
    KNOWLEDGE_DESIGN_RULE,
    KNOWLEDGE_PATTERN,
    KNOWLEDGE_DEFINITION,
    KNOWLEDGE_PREFERENCE,
    KNOWLEDGE_PROJECT_DECISION,
    KNOWLEDGE_OBSERVATION,
    KNOWLEDGE_UNKNOWN,
    SCOPE_GENERAL,
    SCOPE_CURRENT_PROJECT,
    knowledge_class_display,
)

from core.conversation.teaching_foundation_v1 import (
    teaching_foundation,
)

from core.conversation.teaching_candidate_v1 import (
    ALLOWED_STATUSES,
    PERMANENT_LEARNING_IMPLEMENTED,
)

from core.conversation.knowledge_promotion_bridge_v1 import (
    PROMOTION_IMPLEMENTED,
)

from core.curriculum.curriculum_sequencer_v1 import (
    curriculum_sequencer,
    CURRICULUM_STEPS,
    STEP_KEYS,
    LESSONS,
    ALL_STEP_STATUSES,
    FORBIDDEN_STEP_STATUSES,
    STEP_NOT_STARTED,
    STEP_IN_PROGRESS,
    STEP_COMPLETED,
)


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))

    return bool(passed)


# ----------------------------------------------------------
# CANONICAL INPUTS
# ----------------------------------------------------------

# customary rules -> PATTERN
CUSTOMARY = (
    ("\u0645\u0639\u0645\u0648\u0644\u0627\u064b "
     "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0646\u0632\u062f\u06cc\u06a9 "
     "\u0646\u0634\u06cc\u0645\u0646 \u0627\u0633\u062a",
     "\u0645\u0639\u0645\u0648\u0644\u0627\u064b \u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 "
     "\u0646\u0632\u062f\u06cc\u06a9 \u0646\u0634\u06cc\u0645\u0646 \u0627\u0633\u062a"),

    ("\u062f\u0631 \u062e\u0627\u0646\u0647 \u0627\u06cc\u0631\u0627\u0646\u06cc "
     "\u0645\u0639\u0645\u0648\u0644\u0627\u064b \u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 "
     "\u0646\u0632\u062f\u06cc\u06a9 \u0641\u0636\u0627\u06cc \u0646\u0634\u06cc\u0645\u0646 "
     "\u0627\u0633\u062a",
     "\u062f\u0631 \u062e\u0627\u0646\u0647 \u0627\u06cc\u0631\u0627\u0646\u06cc "
     "\u0645\u0639\u0645\u0648\u0644\u0627\u064b \u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 "
     "\u0646\u0632\u062f\u06cc\u06a9 \u0641\u0636\u0627\u06cc \u0646\u0634\u06cc\u0645\u0646 "
     "\u0627\u0633\u062a"),

    ("\u0627\u0644\u06af\u0648\u06cc \u0631\u0627\u06cc\u062c \u0627\u06cc\u0646 "
     "\u0627\u0633\u062a \u06a9\u0647 \u0648\u0631\u0648\u062f\u06cc \u0628\u0627 "
     "\u0647\u0634\u062a\u06cc \u0628\u0647 \u0646\u0634\u06cc\u0645\u0646 \u0648\u0635\u0644 "
     "\u0634\u0648\u062f",
     "\u0627\u0644\u06af\u0648\u06cc \u0631\u0627\u06cc\u062c \u0627\u06cc\u0646 "
     "\u0627\u0633\u062a \u06a9\u0647 \u0648\u0631\u0648\u062f\u06cc \u0628\u0627 "
     "\u0647\u0634\u062a\u06cc \u0628\u0647 \u0646\u0634\u06cc\u0645\u0646 \u0648\u0635\u0644 "
     "\u0634\u0648\u062f"),

    ("\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u0647\u0627 "
     "\u0645\u0639\u0645\u0648\u0644\u0627\u064b \u0628\u0627\u06cc\u062f \u0627\u0632 "
     "\u0641\u0636\u0627\u0647\u0627\u06cc \u0639\u0645\u0648\u0645\u06cc \u062c\u062f\u0627 "
     "\u0628\u0627\u0634\u0646\u062f",
     "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u0647\u0627 "
     "\u0645\u0639\u0645\u0648\u0644\u0627\u064b \u0628\u0627\u06cc\u062f \u0627\u0632 "
     "\u0641\u0636\u0627\u0647\u0627\u06cc \u0639\u0645\u0648\u0645\u06cc \u062c\u062f\u0627 "
     "\u0628\u0627\u0634\u0646\u062f"),
)

CUSTOMARY_EN = (
    "A common pattern is a central corridor serving the bedrooms",
    "Usually the kitchen sits next to the living room",
)

# general architectural rules -> DESIGN_RULE
DESIGN_RULES = (
    "\u0631\u0627\u0647 \u067e\u0644\u0647 \u0628\u0627\u06cc\u062f "
    "\u0646\u0632\u062f\u06cc\u06a9 \u0648\u0631\u0648\u062f\u06cc \u0628\u0627\u0634\u062f",

    "\u0628\u0627\u0645 \u0628\u0627\u06cc\u062f \u0634\u06cc\u0628 "
    "\u0645\u0646\u0627\u0633\u0628 \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u062f",
)

DESIGN_RULES_EN = (
    "The stair should be near the entrance",
    "The roof must have an appropriate slope",
)

# definitions -> DEFINITION
DEFINITIONS = (
    # copula: ... است
    "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u0641\u0636\u0627\u06cc "
    "\u062e\u0635\u0648\u0635\u06cc \u0627\u0633\u062a",

    # copula: ... است
    "\u0631\u0627\u0647 \u067e\u0644\u0647 \u0627\u0631\u062a\u0628\u0627\u0637 "
    "\u0628\u06cc\u0646 \u0637\u0628\u0642\u0627\u062a \u0627\u0633\u062a",

    # copula: ... هست
    "\u062d\u06cc\u0627\u0637 \u062e\u0644\u0648\u062a \u0641\u0636\u0627\u06cc "
    "\u0628\u0627\u0632 \u062e\u0635\u0648\u0635\u06cc \u0647\u0633\u062a",

    # explicit: یعنی
    "\u062d\u0631\u06cc\u0645 \u062e\u0635\u0648\u0635\u06cc \u06cc\u0639\u0646\u06cc "
    "\u062c\u062f\u0627\u06cc\u06cc \u0641\u0636\u0627\u06cc \u062e\u0635\u0648\u0635\u06cc "
    "\u0627\u0632 \u0639\u0645\u0648\u0645\u06cc",
)

DEFINITIONS_EN = (
    "Privacy means separating the private zone from the public one",
)

# project decisions -> PROJECT_DECISION / CURRENT_PROJECT
PROJECT_DECISIONS = (
    "\u062f\u0631 \u0627\u06cc\u0646 \u067e\u0631\u0648\u0698\u0647 "
    "\u062a\u0635\u0645\u06cc\u0645 \u06af\u0631\u0641\u062a\u06cc\u0645 "
    "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0627\u0632 \u0628\u0627\u0634\u062f",

    "\u062f\u0631 \u0627\u06cc\u0646 \u067e\u0631\u0648\u0698\u0647 "
    "\u0642\u0631\u0627\u0631 \u0634\u062f \u0648\u0631\u0648\u062f\u06cc "
    "\u062c\u062f\u0627\u06af\u0627\u0646\u0647 \u0628\u0627\u0634\u062f",
)

PROJECT_DECISIONS_EN = (
    "For this project we decided the kitchen is open",
)


def _classify(text):

    return extract_meaning(text, turn_kind=TURN_TEACHING_STATEMENT)


# ==========================================================
# PART 1 — KNOWLEDGE CLASS TAXONOMY
# ==========================================================

BRIEF_CLASSES = (
    "ARCHITECTURAL_FACT",
    "DESIGN_RULE",
    "PATTERN",
    "OBSERVATION",
    "PREFERENCE",
    "PROJECT_DECISION",
    "DEFINITION",
)


def test_brief_classes_all_exist():

    missing = [c for c in BRIEF_CLASSES if c not in ALL_KNOWLEDGE_CLASSES]

    return _check(
        "CF-1 all seven brief knowledge classes exist",
        not missing,
        {"missing": missing, "all": list(ALL_KNOWLEDGE_CLASSES)},
    )


def test_definition_is_its_own_class():

    return _check(
        "CF-1 DEFINITION is a distinct class, not folded into "
        "ARCHITECTURAL_FACT",
        KNOWLEDGE_DEFINITION == "DEFINITION"
        and KNOWLEDGE_DEFINITION in ALL_KNOWLEDGE_CLASSES
        and KNOWLEDGE_DEFINITION != KNOWLEDGE_ARCHITECTURAL_FACT,
        None,
    )


def test_unknown_is_preserved():

    """Additive change: the vocabulary may GROW, nothing was deleted."""

    return _check(
        "CF-1 UNKNOWN is preserved (vocabulary grew, nothing removed)",
        KNOWLEDGE_UNKNOWN in ALL_KNOWLEDGE_CLASSES
        and len(ALL_KNOWLEDGE_CLASSES) >= len(BRIEF_CLASSES),
        list(ALL_KNOWLEDGE_CLASSES),
    )


def test_definition_has_a_display_label():

    fa = knowledge_class_display(KNOWLEDGE_DEFINITION, "fa")

    en = knowledge_class_display(KNOWLEDGE_DEFINITION, "en")

    return _check(
        "CF-1 DEFINITION has Persian and English labels",
        bool(fa) and bool(en) and fa != en,
        {"fa": fa, "en": en},
    )


# ==========================================================
# PART 2 — PERSIAN TEACHING STATEMENT CLASSIFICATION
# ==========================================================

def test_customary_rules_are_patterns():

    failures = []

    for text, _ in CUSTOMARY:

        got = _classify(text)

        if got.get("knowledge_class") != KNOWLEDGE_PATTERN:

            failures.append(
                {"text": text, "got": got.get("knowledge_class")}
            )

    for text in CUSTOMARY_EN:

        got = _classify(text)

        if got.get("knowledge_class") != KNOWLEDGE_PATTERN:

            failures.append(
                {"text": text, "got": got.get("knowledge_class")}
            )

    return _check(
        "CF-2 customary rules classify as PATTERN (fa + en)",
        not failures,
        failures,
    )


def test_general_rules_are_design_rules():

    failures = []

    for text in DESIGN_RULES + DESIGN_RULES_EN:

        got = _classify(text)

        if got.get("knowledge_class") != KNOWLEDGE_DESIGN_RULE:

            failures.append(
                {"text": text, "got": got.get("knowledge_class")}
            )

    return _check(
        "CF-2 general architectural rules classify as DESIGN_RULE "
        "(fa + en)",
        not failures,
        failures,
    )


def test_definitions_are_definitions():

    failures = []

    for text in DEFINITIONS + DEFINITIONS_EN:

        got = _classify(text)

        if got.get("knowledge_class") != KNOWLEDGE_DEFINITION:

            failures.append(
                {"text": text, "got": got.get("knowledge_class")}
            )

    return _check(
        "CF-2 definitions classify as DEFINITION (fa + en)",
        not failures,
        failures,
    )


def test_project_decisions_are_project_scoped_only():

    failures = []

    for text in PROJECT_DECISIONS + PROJECT_DECISIONS_EN:

        got = _classify(text)

        if got.get("knowledge_class") != KNOWLEDGE_PROJECT_DECISION:

            failures.append(
                {"text": text, "got": got.get("knowledge_class")}
            )

        elif got.get("scope") != SCOPE_CURRENT_PROJECT:

            failures.append(
                {"text": text, "scope": got.get("scope"),
                 "problem": "project decision was generalised"}
            )

    return _check(
        "CF-2 project decisions are PROJECT_DECISION / CURRENT_PROJECT only",
        not failures,
        failures,
    )


def test_the_briefs_own_example_now_classifies_as_a_pattern():

    """The exact sentence the readiness audit flagged."""

    text = (
        "\u062f\u0631 \u062e\u0627\u0646\u0647 \u0627\u06cc\u0631\u0627\u0646\u06cc "
        "\u0645\u0639\u0645\u0648\u0644\u0627\u064b \u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 "
        "\u0646\u0632\u062f\u06cc\u06a9 \u0641\u0636\u0627\u06cc \u0646\u0634\u06cc\u0645\u0646 "
        "\u0627\u0633\u062a"
    )

    got = _classify(text)

    return _check(
        "CF-2 the brief's customary example is PATTERN / GENERAL "
        "(was OBSERVATION / CURRENT_PROJECT)",
        got.get("knowledge_class") == KNOWLEDGE_PATTERN
        and got.get("scope") == SCOPE_GENERAL,
        {"kc": got.get("knowledge_class"), "scope": got.get("scope")},
    )


def test_scope_vocabulary_unchanged():

    return _check(
        "CF-2 scope vocabulary is still GENERAL / CURRENT_PROJECT",
        set(ALL_SCOPES) == {"GENERAL", "CURRENT_PROJECT"},
        list(ALL_SCOPES),
    )


# ==========================================================
# PART 3 — PATTERN WITHOUT A NORMATIVE MARKER
# ==========================================================

def test_pattern_marker_feature_exists():

    features = extract_features(
        "\u0645\u0639\u0645\u0648\u0644\u0627\u064b "
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0646\u0632\u062f\u06cc\u06a9 "
        "\u0646\u0634\u06cc\u0645\u0646 \u0627\u0633\u062a"
    )

    return _check(
        "CF-3 the turn classifier exposes a pattern_marker feature",
        "pattern_marker" in features
        and features["pattern_marker"] is True
        and features["normative"] is False,
        {"pattern": features.get("pattern_marker"),
         "normative": features.get("normative")},
    )


def test_pattern_words_are_recognised():

    """'الگو' (pattern) itself was missing from the marker list."""

    markers = (
        "\u0627\u0644\u06af\u0648\u06cc \u0631\u0627\u06cc\u062c",
        "\u0631\u0648\u06cc\u0647\u0654 \u0645\u0639\u0645\u0648\u0644",
    )

    missing = [
        m for m in markers
        if not contains_any(m, PATTERN_MARKERS)
    ]

    return _check(
        "CF-3 pattern vocabulary includes الگو / رویه (and English "
        "'pattern')",
        not missing and "pattern" in PATTERN_MARKERS,
        {"missing": missing, "marker_count": len(PATTERN_MARKERS)},
    )


def test_pattern_needs_no_normative_marker():

    """The core of fix 3: a customary statement with NO deontic word."""

    text = (
        "\u0645\u0639\u0645\u0648\u0644\u0627\u064b \u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 "
        "\u0646\u0632\u062f\u06cc\u06a9 \u0646\u0634\u06cc\u0645\u0646 \u0627\u0633\u062a"
    )

    features = extract_features(text)

    got = _classify(text)

    return _check(
        "CF-3 PATTERN is reachable WITHOUT a normative marker",
        features["normative"] is False
        and got.get("knowledge_class") == KNOWLEDGE_PATTERN,
        {"normative": features["normative"],
         "kc": got.get("knowledge_class")},
    )


def test_pattern_outranks_normative_and_copula():

    """A customary deontic statement is still a PATTERN, not a rule."""

    text = (
        "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u0647\u0627 "
        "\u0645\u0639\u0645\u0648\u0644\u0627\u064b \u0628\u0627\u06cc\u062f \u0627\u0632 "
        "\u0641\u0636\u0627\u0647\u0627\u06cc \u0639\u0645\u0648\u0645\u06cc \u062c\u062f\u0627 "
        "\u0628\u0627\u0634\u0646\u062f"
    )

    features = extract_features(text)

    got = _classify(text)

    return _check(
        "CF-3 a customary statement outranks both normative and copula",
        features["normative"] is True
        and got.get("knowledge_class") == KNOWLEDGE_PATTERN,
        {"normative": features["normative"],
         "kc": got.get("knowledge_class")},
    )


# ==========================================================
# PART 4 — PERSIAN DEFINITIONAL DETECTION
# ==========================================================

def test_copula_vocabulary_covers_persian():

    required = (
        "\u0627\u0633\u062a",        # است
        "\u0647\u0633\u062a",        # هست
    )

    missing = [t for t in required if t not in PERSIAN_COPULA_TOKENS]

    return _check(
        "CF-4 the copula vocabulary covers است / هست",
        not missing,
        {"missing": missing},
    )


def test_copula_definition_requires_length():

    """A short conversational copula must NOT be a definition."""

    short = extract_features("\u0628\u062f \u0627\u0633\u062a")

    long_enough = extract_features(
        "\u0631\u0627\u0647 \u067e\u0644\u0647 \u0627\u0631\u062a\u0628\u0627\u0637 "
        "\u0628\u06cc\u0646 \u0637\u0628\u0642\u0627\u062a \u0627\u0633\u062a"
    )

    return _check(
        "CF-4 a short copula is not a definition; a full one is",
        short["copula_definition"] is False
        and long_enough["copula_definition"] is True
        and MIN_COPULA_DEFINITION_TOKENS == 4,
        {"short": short["copula_definition"],
         "long": long_enough["copula_definition"]},
    )


def test_meaning_exposes_is_definitional():

    got = _classify(
        "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u0641\u0636\u0627\u06cc "
        "\u062e\u0635\u0648\u0635\u06cc \u0627\u0633\u062a"
    )

    return _check(
        "CF-4 the meaning exposes is_definitional + copula_definition",
        got.get("is_definitional") is True
        and got.get("copula_definition") is True
        and got.get("candidate_kind") == "definition"
        and got.get("polarity") == "define",
        {"is_definitional": got.get("is_definitional"),
         "kind": got.get("candidate_kind")},
    )


def test_explicit_definition_marker_still_works():

    got = _classify(
        "\u062d\u0631\u06cc\u0645 \u062e\u0635\u0648\u0635\u06cc \u06cc\u0639\u0646\u06cc "
        "\u062c\u062f\u0627\u06cc\u06cc \u0641\u0636\u0627\u06cc \u062e\u0635\u0648\u0635\u06cc "
        "\u0627\u0632 \u0639\u0645\u0648\u0645\u06cc"
    )

    return _check(
        "CF-4 the explicit marker یعنی still yields a DEFINITION",
        got.get("knowledge_class") == KNOWLEDGE_DEFINITION
        and got.get("is_definitional") is True,
        {"kc": got.get("knowledge_class")},
    )


def test_copula_definition_is_general_not_project_scoped():

    got = _classify(
        "\u0631\u0627\u0647 \u067e\u0644\u0647 \u0627\u0631\u062a\u0628\u0627\u0637 "
        "\u0628\u06cc\u0646 \u0637\u0628\u0642\u0627\u062a \u0627\u0633\u062a"
    )

    return _check(
        "CF-4 a definition is GENERAL knowledge",
        got.get("scope") == SCOPE_GENERAL,
        {"scope": got.get("scope")},
    )


# ==========================================================
# PART 2 (cont.) — TURN CLASSIFICATION GATE
# ==========================================================

def test_customary_statement_is_a_teaching_turn():

    features = extract_features(
        "\u0645\u0639\u0645\u0648\u0644\u0627\u064b \u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 "
        "\u0646\u0632\u062f\u06cc\u06a9 \u0646\u0634\u06cc\u0645\u0646 \u0627\u0633\u062a"
    )

    return _check(
        "CF-2 a customary statement is not rejected by the turn gate",
        features["pattern_marker"] is True,
        {"pattern_marker": features.get("pattern_marker")},
    )


def test_decision_marker_feature_exists():

    features = extract_features(
        "\u062f\u0631 \u0627\u06cc\u0646 \u067e\u0631\u0648\u0698\u0647 "
        "\u062a\u0635\u0645\u06cc\u0645 \u06af\u0631\u0641\u062a\u06cc\u0645 "
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0627\u0632 \u0628\u0627\u0634\u062f"
    )

    return _check(
        "CF-2 a project decision raises a decision_marker feature",
        features["decision_marker"] is True
        and "decision_marker" in features,
        {"decision_marker": features.get("decision_marker")},
    )


def test_decision_marker_is_a_decision_verb_not_the_bare_project_word():

    """'این پروژه' alone appears in ordinary conversation; it must NOT
    by itself turn a sentence into a teaching turn."""

    bare = extract_features(
        "\u0627\u06cc\u0646 \u067e\u0631\u0648\u0698\u0647 \u0633\u0647 "
        "\u0637\u0628\u0642\u0647 \u062f\u0627\u0631\u062f"
    )

    return _check(
        "CF-2 the bare project word is not a decision marker",
        bare["decision_marker"] is False
        and not contains_any(
            "\u0627\u06cc\u0646 \u067e\u0631\u0648\u0698\u0647",
            DECISION_MARKERS,
        ),
        {"decision_marker": bare.get("decision_marker")},
    )


def test_teaching_flow_produces_candidates_for_all_four_categories():

    """End-to-end through the teaching foundation, on the PERSISTED path."""

    manifest = project_workspace.create("Curriculum Foundation Contract")

    project_id = manifest.get("project_id") or (
        manifest.get("project") or {}
    ).get("project_id")

    cases = (
        (CUSTOMARY[1][0], KNOWLEDGE_PATTERN),
        (DESIGN_RULES[0], KNOWLEDGE_DESIGN_RULE),
        (DEFINITIONS[0], KNOWLEDGE_DEFINITION),
        (PROJECT_DECISIONS[0], KNOWLEDGE_PROJECT_DECISION),
    )

    failures = []

    for text, expected in cases:

        observation = teaching_foundation.observe_turn(
            session_id=project_id, text=text, input_type="typed"
        )

        candidate = observation.get("candidate")

        if hasattr(candidate, "to_dict"):

            candidate = candidate.to_dict()

        candidate = candidate or {}

        if (
            observation.get("turn_kind") != TURN_TEACHING_STATEMENT
            or candidate.get("knowledge_class") != expected
        ):

            failures.append(
                {
                    "expected": expected,
                    "turn_kind": observation.get("turn_kind"),
                    "got": candidate.get("knowledge_class"),
                }
            )

    return _check(
        "CF-2 all four categories produce candidates end-to-end",
        not failures,
        failures,
    )


def test_teaching_still_learns_nothing():

    manifest = project_workspace.create("Curriculum Foundation No Learn")

    project_id = manifest.get("project_id") or (
        manifest.get("project") or {}
    ).get("project_id")

    observation = teaching_foundation.observe_turn(
        session_id=project_id,
        text=DESIGN_RULES[0],
        input_type="typed",
    )

    candidate = observation.get("candidate")

    if hasattr(candidate, "to_dict"):

        candidate = candidate.to_dict()

    candidate = candidate or {}

    return _check(
        "CF-2 a taught rule is still a candidate only (no learning)",
        candidate.get("status") in ALLOWED_STATUSES
        and candidate.get("is_learned_knowledge") is False
        and candidate.get("is_permanent") is False
        and observation.get("capability") == "UNDERSTAND",
        {"status": candidate.get("status")},
    )


# ==========================================================
# PART 5 — CURRICULUM SEQUENCER FOUNDATION
# ==========================================================

def test_sequence_order_matches_the_brief():

    """RELAXED by CURRICULUM_FOUNDATION_FIX_02 (relax + add, never delete).

    The original five steps must still be present, in this order, as the
    PREFIX of the sequence. The sequence may GROW: fix 02 appended
    `patterns` and `design_reasoning` so the order matches the seven
    teaching parts the curriculum defines.
    """

    original_five = [
        "space_types",
        "relationships",
        "privacy",
        "zoning",
        "bubble_diagram",
    ]

    got = [step["key"] for step in curriculum_sequencer.sequence("en")]

    return _check(
        "CF-5 the sequence begins Space Types -> Relationships -> Privacy "
        "-> Zoning -> Bubble Diagram (and may grow)",
        got[: len(original_five)] == original_five
        and len(got) >= len(original_five),
        {"got": got},
    )


def test_sequence_grew_to_seven_steps():

    """The added half of the relax + add pair."""

    got = [step["key"] for step in curriculum_sequencer.sequence("en")]

    return _check(
        "CF-5 the sequence now carries Patterns and Design Reasoning",
        got == [
            "space_types", "relationships", "privacy", "zoning",
            "bubble_diagram", "patterns", "design_reasoning",
        ],
        {"got": got},
    )


def test_sequencer_contains_no_lessons():

    return _check(
        "CF-5 the sequencer contains NO lesson content",
        LESSONS == ()
        and curriculum_sequencer.report()["lesson_count"] == 0
        and curriculum_sequencer.report()["has_lessons"] is False
        and all(
            step["has_lesson"] is False
            for step in curriculum_sequencer.sequence("en")
        ),
        {"lesson_count": curriculum_sequencer.report()["lesson_count"]},
    )


def test_sequencer_gates_steps():

    progress = curriculum_sequencer.progress_template()

    first = curriculum_sequencer.available_steps(progress)

    # complete the first two, then only privacy should open
    progress["space_types"] = STEP_COMPLETED

    after_first = curriculum_sequencer.available_steps(progress)

    progress["relationships"] = STEP_COMPLETED

    after_second = curriculum_sequencer.available_steps(progress)

    return _check(
        "CF-5 the sequencer gates each step behind its prerequisite",
        first == ["space_types"]
        and after_first == ["relationships"]
        and after_second == ["privacy"],
        {"first": first, "after_first": after_first,
         "after_second": after_second},
    )


def test_sequencer_refuses_out_of_order_start():

    """zoning must NOT be available before privacy is completed."""

    progress = curriculum_sequencer.progress_template()

    return _check(
        "CF-5 a later step is unavailable before its prerequisite",
        curriculum_sequencer.is_available(progress, "zoning") is False
        and curriculum_sequencer.is_available(
            progress, "bubble_diagram"
        ) is False
        and curriculum_sequencer.is_available(
            progress, "space_types"
        ) is True,
        None,
    )


def test_sequencer_enforces_the_full_order():

    """Completing a LATER step on its own must not unlock its dependents.

    Without this, marking `zoning` complete would unlock
    `bubble_diagram`, and a teacher could reach the diagram having
    covered none of the basics.
    """

    progress = curriculum_sequencer.progress_template()

    progress["zoning"] = STEP_COMPLETED

    available = curriculum_sequencer.available_steps(progress)

    return _check(
        "CF-5 an out-of-order completion unlocks nothing downstream",
        available == ["space_types"]
        and curriculum_sequencer.is_available(
            progress, "bubble_diagram"
        ) is False
        and curriculum_sequencer.is_available(
            progress, "relationships"
        ) is False,
        {"available": available},
    )


def test_sequencer_walks_to_completion():

    progress = curriculum_sequencer.progress_template()

    for key in STEP_KEYS:

        progress[key] = STEP_COMPLETED

    return _check(
        "CF-5 the sequence completes and reports 1.0",
        curriculum_sequencer.is_complete(progress) is True
        and curriculum_sequencer.progress_ratio(progress) == 1.0
        and curriculum_sequencer.next_step(progress) is None,
        {"ratio": curriculum_sequencer.progress_ratio(progress)},
    )


def test_sequencer_status_vocabulary_refuses_learning():

    return _check(
        "CF-5 progress statuses are progress, never knowledge",
        set(ALL_STEP_STATUSES) == {
            "not_started", "in_progress", "completed"
        }
        and "learned" in FORBIDDEN_STEP_STATUSES
        and curriculum_sequencer.validate_progress(
            {"space_types": "learned"}
        )["valid"] is False,
        list(FORBIDDEN_STEP_STATUSES),
    )


def test_sequencer_rejects_unknown_steps():

    return _check(
        "CF-5 unknown steps are rejected",
        curriculum_sequencer.validate_progress(
            {"not_a_step": "completed"}
        )["valid"] is False
        and curriculum_sequencer.step("not_a_step") is None,
        None,
    )


def test_sequencer_persists_nothing():

    report = curriculum_sequencer.report()

    plan = curriculum_sequencer.plan(curriculum_sequencer.progress_template())

    return _check(
        "CF-5 the sequencer persists no progress and learns nothing",
        report["writes_performed"] == 0
        and report["read_only"] is True
        and report["persists_progress"] is False
        and report["permanent_learning"] is False
        and plan["persists_progress"] is False
        and plan["permanent_learning"] is False,
        None,
    )


def test_sequencer_steps_name_existing_modules():

    """Every step must point at a module that actually exists — the
    sequencer orders the corpus, it does not restate it."""

    missing = []

    for step in CURRICULUM_STEPS:

        path = os.path.join(ROOT, step["backing_module"])

        if not os.path.isfile(path):

            missing.append(step["backing_module"])

    return _check(
        "CF-5 every sequenced step is backed by an existing module",
        not missing,
        {"missing": missing},
    )


def test_sequencer_labels_are_bilingual():

    fa = curriculum_sequencer.sequence("fa")

    en = curriculum_sequencer.sequence("en")

    ok = (
        len(fa) == len(en) == len(CURRICULUM_STEPS)
        and all(
            a["label"] != b["label"] and a["label"] and b["label"]
            for a, b in zip(fa, en)
        )
    )

    return _check(
        "CF-5 every step has Persian and English labels",
        ok,
        {"fa": [s["label"] for s in fa][:3]},
    )


def test_sequencer_plan_is_deterministic():

    progress = curriculum_sequencer.progress_template()

    first = curriculum_sequencer.plan(progress, "en")

    second = curriculum_sequencer.plan(progress, "en")

    return _check(
        "CF-5 the plan is deterministic",
        json.dumps(first, sort_keys=True)
        == json.dumps(second, sort_keys=True)
        and first["deterministic"] is True,
        None,
    )


# ==========================================================
# SHARED VOCABULARY (no duplication)
# ==========================================================

def test_pattern_vocabulary_has_one_source_of_truth():

    """PATTERN_MARKERS lives in turn_semantics_v1 and is IMPORTED by
    teaching_meaning_v1 — a second literal copy is how the two layers
    would drift apart."""

    import core.conversation.teaching_meaning_v1 as meaning_module

    source = open(
        meaning_module.__file__, "r", encoding="utf-8"
    ).read()

    return _check(
        "CF-3 PATTERN_MARKERS has ONE definition (imported, not copied)",
        "PATTERN_MARKERS" in source
        and "from core.conversation.turn_semantics_v1 import" in source
        and "PATTERN_MARKERS = (" not in source,
        None,
    )


# ==========================================================
# SCOPE — NO GEOMETRY / CAD / BIM / IFC / RENDER
# ==========================================================

def test_sequencer_imports_no_forbidden_library():

    path = os.path.join(
        ROOT, "core", "curriculum", "curriculum_sequencer_v1.py"
    )

    with open(path, "r", encoding="utf-8") as handle:

        tree = ast.parse(handle.read(), filename=path)

    forbidden = (
        "ezdxf", "ifcopenshell", "shapely", "trimesh", "pyautocad",
        "comfy", "diffusers", "torch", "numpy", "matplotlib",
        "requests", "urllib", "httpx", "flask",
    )

    hits = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            modules = [alias.name for alias in node.names]

        elif isinstance(node, ast.ImportFrom):

            modules = [node.module or ""]

        else:

            continue

        for module in modules:

            if module.split(".")[0].lower() in forbidden:

                hits.append(module)

    return _check(
        "CF-6 the sequencer imports no geometry / render / BIM / network "
        "library",
        not hits,
        {"hits": hits},
    )


def test_no_geometry_vocabulary_in_the_plan():

    """Scan the STRUCTURAL plan, pruning the scope guarantee flags.

    `"contains_coordinates": false` IS the guarantee, not a violation of
    it — a naive substring scan trips on its own safety field.
    """

    def prune(node):

        if isinstance(node, dict):

            return {
                key: prune(value)
                for key, value in node.items()
                if key not in (
                    "contains_geometry",
                    "contains_coordinates",
                    "contains_walls",
                    "contains_openings",
                    "semantic_only",
                    "render_requested",
                    "comfy_invoked",
                    "geometric",
                )
            }

        if isinstance(node, list):

            return [prune(item) for item in node]

        return node

    payload = json.dumps(
        prune(
            curriculum_sequencer.plan(
                curriculum_sequencer.progress_template()
            )
        ),
        ensure_ascii=False,
    ).lower()

    forbidden = (
        "polygon", "vertex", "bounding_box", "centroid",
        "wall_segment", "door_swing", "ifc", "dwg", "dxf", "coordinate",
    )

    hits = [token for token in forbidden if token in payload]

    return _check(
        "CF-6 the plan contains no geometry vocabulary",
        not hits,
        {"hits": hits},
    )


def test_no_permanent_learning_anywhere():

    return _check(
        "CF-6 no promotion / permanent-learning path exists",
        PROMOTION_IMPLEMENTED is False
        and PERMANENT_LEARNING_IMPLEMENTED is False
        and set(ALLOWED_STATUSES) == {
            "observed", "needs_confirmation", "rejected"
        },
        list(ALLOWED_STATUSES),
    )


def test_no_lesson_or_layout_module_created():

    module_dir = os.path.join(ROOT, "core", "curriculum")

    forbidden = (
        "lesson", "layout_generation", "floorplan", "floor_plan",
        "geometry", "wall", "opening", "cad", "bim", "ifc", "render",
    )

    hits = [
        name for name in os.listdir(module_dir)
        if name.endswith(".py")
        and any(token in name.lower() for token in forbidden)
    ]

    return _check(
        "CF-6 no lesson / layout / floor-plan / geometry module exists",
        not hits,
        {"hits": hits},
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
    print("  ARCHITECTURAL CURRICULUM FOUNDATION FIX")
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
