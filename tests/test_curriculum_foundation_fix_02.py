# ==========================================================
# CURRICULUM_FOUNDATION_FIX_02 — CONTRACT TESTS
#
# ISOLATED CONTRACT tests for:
#   1. zone assignment teaching support
#   2. the seven-step curriculum sequencer
#   3. the pattern curriculum boundary
#
# These are NOT the acceptance proof: acceptance runs against the live
# runtime path (tools/run_curriculum_foundation_fix_02_acceptance.py).
#
# Deliberately NOT tested here because the phase forbids them:
#   lessons, curriculum content, geometry, layout, CAD, BIM, IFC, render.
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_curriculum_foundation_fix_02.py
#   .venv/Scripts/python.exe tests/test_curriculum_foundation_fix_02.py
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
    tempfile.gettempdir(), "architectos_curriculum_foundation_02"
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
    ZONE_WORDS,
    ZONE_ASSIGNMENT_PHRASES,
    is_zone_assignment,
    zone_word_in,
)

from core.conversation.teaching_meaning_v1 import (
    extract_meaning,
    ZONE_PHRASE_TO_ZONE,
    resolve_zone_phrase,
    KNOWLEDGE_ARCHITECTURAL_FACT,
    ALL_KNOWLEDGE_CLASSES,
)

from core.conversation.teaching_foundation_v1 import (
    teaching_foundation,
)

from core.conversation.teaching_candidate_v1 import (
    ALLOWED_STATUSES,
    PERMANENT_LEARNING_IMPLEMENTED,
    TeachingCandidate,
)

from core.conversation.knowledge_promotion_bridge_v1 import (
    PROMOTION_IMPLEMENTED,
)

from core.curriculum.zone_model_v1 import (
    ALL_ZONES,
    ZONE_PUBLIC,
    ZONE_SEMI_PUBLIC,
    ZONE_PRIVATE,
    ZONE_SERVICE,
    ZONE_CIRCULATION,
    ZONE_EXTERNAL,
)

from core.curriculum.curriculum_sequencer_v1 import (
    curriculum_sequencer,
    CURRICULUM_STEPS,
    STEP_KEYS,
    LESSONS,
    ALL_STEP_STATUSES,
    FORBIDDEN_STEP_STATUSES,
    STEP_COMPLETED,
)

from core.curriculum.pattern_curriculum_v1 import (
    pattern_curriculum,
    PatternCurriculumV1,
    PATTERN_FAMILIES,
    FAMILY_KEYS,
    FAMILY_RESIDENTIAL,
    FAMILY_COMMERCIAL,
    FAMILY_MIXED_USE,
    STATUS_AVAILABLE,
    STATUS_BLOCKED,
    PATTERNS,
    PATTERN_TEACHING_ASPECTS,
    pattern_aspects,
)


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))

    return bool(passed)


# ----------------------------------------------------------
# CANONICAL INPUTS
# ----------------------------------------------------------

BRIEF_ZONE_STATEMENT = (
    "\u0648\u0631\u0648\u062f\u06cc \u0648 \u0646\u0634\u06cc\u0645\u0646 "
    "\u062f\u0631 \u0645\u0646\u0637\u0642\u0647 \u0639\u0645\u0648\u0645\u06cc "
    "\u0642\u0631\u0627\u0631 \u0645\u06cc \u06af\u06cc\u0631\u0646\u062f"
)

ZONE_CASES = (
    (
        "\u0648\u0631\u0648\u062f\u06cc \u0648 \u0646\u0634\u06cc\u0645\u0646 "
        "\u062f\u0631 \u0645\u0646\u0637\u0642\u0647 \u0639\u0645\u0648\u0645\u06cc "
        "\u0642\u0631\u0627\u0631 \u0645\u06cc \u06af\u06cc\u0631\u0646\u062f",
        ZONE_PUBLIC,
    ),
    (
        "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u062f\u0631 "
        "\u0645\u0646\u0637\u0642\u0647 \u062e\u0635\u0648\u0635\u06cc "
        "\u0642\u0631\u0627\u0631 \u062f\u0627\u0631\u062f",
        ZONE_PRIVATE,
    ),
    (
        "\u062d\u0645\u0627\u0645 \u062f\u0631 \u0645\u0646\u0637\u0642\u0647 "
        "\u062e\u062f\u0645\u0627\u062a\u06cc \u0648\u0627\u0642\u0639 \u0634\u062f\u0647 \u0627\u0633\u062a",
        ZONE_SERVICE,
    ),
    (
        "\u0646\u0634\u06cc\u0645\u0646 \u062c\u0632\u0621 \u0645\u0646\u0637\u0642\u0647 "
        "\u0646\u06cc\u0645\u0647 \u0639\u0645\u0648\u0645\u06cc \u0627\u0633\u062a",
        ZONE_SEMI_PUBLIC,
    ),
    (
        "\u0631\u0627\u0647\u0631\u0648 \u062f\u0631 \u0645\u0646\u0637\u0642\u0647 "
        "\u06af\u0631\u062f\u0634 \u0642\u0631\u0627\u0631 \u0645\u06cc \u06af\u06cc\u0631\u062f",
        ZONE_CIRCULATION,
    ),
    (
        "\u062d\u06cc\u0627\u0637 \u062f\u0631 \u0645\u0646\u0637\u0642\u0647 "
        "\u0628\u06cc\u0631\u0648\u0646\u06cc \u0642\u0631\u0627\u0631 \u062f\u0627\u0631\u062f",
        ZONE_EXTERNAL,
    ),
)


def _project():

    manifest = project_workspace.create("Foundation 02 Contract")

    return manifest.get("project_id") or (
        manifest.get("project") or {}
    ).get("project_id")


def _candidate_for(text, project_id=None):

    observation = teaching_foundation.observe_turn(
        session_id=project_id or _project(),
        text=text,
        input_type="typed",
    )

    candidate = observation.get("candidate")

    if hasattr(candidate, "to_dict"):

        candidate = candidate.to_dict()

    return observation, (candidate or {})


# ==========================================================
# FIX 1 — ZONE ASSIGNMENT TEACHING SUPPORT
# ==========================================================

def test_brief_zone_statement_becomes_a_candidate():

    """The exact sentence the start audit found unteachable."""

    observation, candidate = _candidate_for(BRIEF_ZONE_STATEMENT)

    return _check(
        "F2-1 the brief's zoning statement becomes a teaching candidate",
        observation.get("turn_kind") == TURN_TEACHING_STATEMENT
        and candidate.get("knowledge_class") == KNOWLEDGE_ARCHITECTURAL_FACT
        and bool(candidate.get("candidate_id")),
        {
            "turn_kind": observation.get("turn_kind"),
            "kc": candidate.get("knowledge_class"),
        },
    )


def test_all_six_zones_resolve():

    failures = []

    for text, expected in ZONE_CASES:

        observation, candidate = _candidate_for(text)

        zone = (candidate.get("zone_assignment") or {}).get("zone")

        if (
            observation.get("turn_kind") != TURN_TEACHING_STATEMENT
            or candidate.get("knowledge_class") != KNOWLEDGE_ARCHITECTURAL_FACT
            or zone != expected
        ):

            failures.append(
                {
                    "expected": expected,
                    "got": zone,
                    "turn_kind": observation.get("turn_kind"),
                }
            )

    return _check(
        "F2-1 all six zones resolve from a Persian zoning statement",
        not failures,
        failures,
    )


def test_english_zone_statement():

    observation, candidate = _candidate_for(
        "The entry belongs to the public zone"
    )

    zone = (candidate.get("zone_assignment") or {}).get("zone")

    return _check(
        "F2-1 an English zoning statement resolves too",
        observation.get("turn_kind") == TURN_TEACHING_STATEMENT
        and zone == ZONE_PUBLIC,
        {"zone": zone, "turn_kind": observation.get("turn_kind")},
    )


def test_zone_candidate_is_candidate_only():

    observation, candidate = _candidate_for(BRIEF_ZONE_STATEMENT)

    return _check(
        "F2-1 a zone candidate is still candidate-only (no learning)",
        candidate.get("status") in ALLOWED_STATUSES
        and candidate.get("is_learned_knowledge") is False
        and candidate.get("is_permanent") is False
        and observation.get("capability") == "UNDERSTAND",
        {"status": candidate.get("status")},
    )


def test_zone_field_round_trips():

    """The new candidate field must survive to_dict / from_dict."""

    _, candidate = _candidate_for(BRIEF_ZONE_STATEMENT)

    rebuilt = TeachingCandidate.from_dict(candidate).to_dict()

    return _check(
        "F2-1 zone_assignment round-trips through the candidate contract",
        "zone_assignment" in candidate
        and rebuilt.get("zone_assignment")
        == candidate.get("zone_assignment")
        and (rebuilt.get("zone_assignment") or {}).get("zone")
        == ZONE_PUBLIC,
        {"zone": (rebuilt.get("zone_assignment") or {}).get("zone")},
    )


def test_zone_assignment_needs_both_parts():

    """A zone word alone, or an assignment phrase alone, is NOT enough."""

    zone_word_only = extract_features(
        "\u0645\u0646\u0637\u0642\u0647 \u0639\u0645\u0648\u0645\u06cc "
        "\u0628\u0632\u0631\u06af \u0627\u0633\u062a"
    )

    phrase_only = extract_features(
        "\u0627\u06cc\u0646 \u062f\u0631 \u0642\u0631\u0627\u0631 \u062f\u0627\u0631\u062f"
    )

    return _check(
        "F2-1 a zone word alone or a phrase alone is not an assignment",
        zone_word_only["zone_assignment"] is False
        and phrase_only["zone_assignment"] is False,
        {
            "zone_only": zone_word_only.get("zone_assignment"),
            "phrase_only": phrase_only.get("zone_assignment"),
        },
    )


def test_plain_descriptive_statement_is_still_not_a_teaching_turn():

    """The fix must not turn ordinary conversation into teaching."""

    observation, candidate = _candidate_for(
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0633\u0647 "
        "\u0628\u062e\u0634 \u062f\u0627\u0631\u062f"
    )

    return _check(
        "F2-1 a plain descriptive statement still yields no candidate",
        observation.get("turn_kind") != TURN_TEACHING_STATEMENT
        and not candidate,
        {"turn_kind": observation.get("turn_kind")},
    )


def test_zone_vocabulary_has_one_source_of_truth():

    """The zone map must resolve to the SAME six constants as Phase 11."""

    ok = (
        set(ZONE_PHRASE_TO_ZONE.values()) <= set(ALL_ZONES)
        and len(set(ZONE_PHRASE_TO_ZONE.values())) == 6
        and all(
            resolve_zone_phrase(marker) is not None
            for marker in ZONE_PHRASE_TO_ZONE
        )
    )

    return _check(
        "F2-1 the zone vocabulary resolves to the Phase 11 zone constants",
        ok,
        sorted(set(ZONE_PHRASE_TO_ZONE.values())),
    )


def test_zone_assignment_is_not_a_definition():

    """A copular zoning sentence must be a FACT, not a DEFINITION."""

    meaning = extract_meaning(
        "\u0648\u0631\u0648\u062f\u06cc \u062f\u0631 \u0645\u0646\u0637\u0642\u0647 "
        "\u0639\u0645\u0648\u0645\u06cc \u0627\u0633\u062a",
        turn_kind=TURN_TEACHING_STATEMENT,
    )

    return _check(
        "F2-1 a copular zoning statement is ARCHITECTURAL_FACT, "
        "not DEFINITION",
        meaning.get("knowledge_class") == KNOWLEDGE_ARCHITECTURAL_FACT
        and meaning.get("candidate_kind") == "observation"
        and meaning.get("polarity") == "state",
        {
            "kc": meaning.get("knowledge_class"),
            "kind": meaning.get("candidate_kind"),
            "polarity": meaning.get("polarity"),
        },
    )


# ==========================================================
# FIX 2 — THE SEVEN-STEP SEQUENCER
# ==========================================================

ORIGINAL_FIVE = (
    "space_types",
    "relationships",
    "privacy",
    "zoning",
    "bubble_diagram",
)

ADDED_TWO = ("patterns", "design_reasoning")


def test_sequence_has_seven_steps():

    got = [step["key"] for step in curriculum_sequencer.sequence("en")]

    return _check(
        "F2-2 the sequence is Space Types -> ... -> Bubble Diagram -> "
        "Patterns -> Design Reasoning",
        got == list(ORIGINAL_FIVE) + list(ADDED_TWO),
        {"got": got},
    )


def test_original_five_survive_as_a_prefix():

    got = [step["key"] for step in curriculum_sequencer.sequence("en")]

    return _check(
        "F2-2 the original five steps are unchanged, in order (relax+add)",
        got[: len(ORIGINAL_FIVE)] == list(ORIGINAL_FIVE)
        and len(got) == 7,
        {"got": got},
    )


def test_gating_still_holds_across_seven_steps():

    progress = curriculum_sequencer.progress_template()

    walk = []

    for key in list(ORIGINAL_FIVE) + list(ADDED_TWO):

        walk.append(curriculum_sequencer.available_steps(progress))

        progress[key] = STEP_COMPLETED

    return _check(
        "F2-2 full-order gating holds across all seven steps",
        all(
            available == [key]
            for available, key in zip(
                walk, list(ORIGINAL_FIVE) + list(ADDED_TWO)
            )
        )
        and curriculum_sequencer.is_complete(progress) is True
        and curriculum_sequencer.progress_ratio(progress) == 1.0,
        {"walk": walk},
    )


def test_new_steps_are_gated_behind_the_diagram():

    progress = curriculum_sequencer.progress_template()

    for key in ORIGINAL_FIVE:

        progress[key] = STEP_COMPLETED

    return _check(
        "F2-2 patterns unlocks only after the bubble diagram",
        curriculum_sequencer.available_steps(progress) == ["patterns"]
        and curriculum_sequencer.is_available(
            progress, "design_reasoning"
        ) is False,
        {"available": curriculum_sequencer.available_steps(progress)},
    )


def test_new_steps_declare_their_aspect_sets():

    patterns = curriculum_sequencer.step("patterns")

    reasoning = curriculum_sequencer.step("design_reasoning")

    return _check(
        "F2-2 the new steps declare a pattern / program aspect set",
        patterns.get("aspect_set") == "pattern"
        and reasoning.get("aspect_set") == "program"
        and patterns.get("backing_module", "").endswith(
            "pattern_curriculum_v1.py"
        )
        and reasoning.get("backing_module", "").endswith(
            "floor_program_v1.py"
        ),
        {
            "patterns": patterns.get("aspect_set"),
            "reasoning": reasoning.get("aspect_set"),
        },
    )


def test_every_step_is_backed_by_an_existing_module():

    missing = [
        step["backing_module"] for step in CURRICULUM_STEPS
        if not os.path.isfile(os.path.join(ROOT, step["backing_module"]))
    ]

    return _check(
        "F2-2 every sequenced step is backed by an existing module",
        not missing,
        {"missing": missing},
    )


def test_seven_steps_have_bilingual_labels():

    fa = curriculum_sequencer.sequence("fa")

    en = curriculum_sequencer.sequence("en")

    return _check(
        "F2-2 all seven steps have Persian and English labels",
        len(fa) == len(en) == 7
        and all(
            a["label"] != b["label"] and a["label"] and b["label"]
            for a, b in zip(fa, en)
        ),
        {"fa": [s["label"] for s in fa][-2:]},
    )


def test_sequencer_still_has_no_lessons():

    return _check(
        "F2-2 the seven-step sequencer still contains NO lessons",
        LESSONS == ()
        and curriculum_sequencer.report()["lesson_count"] == 0
        and all(
            step["has_lesson"] is False
            for step in curriculum_sequencer.sequence("en")
        ),
        None,
    )


def test_sequencer_status_vocabulary_unchanged():

    return _check(
        "F2-2 progress statuses are still progress, never knowledge",
        set(ALL_STEP_STATUSES) == {
            "not_started", "in_progress", "completed"
        }
        and "learned" in FORBIDDEN_STEP_STATUSES
        and curriculum_sequencer.validate_progress(
            {"patterns": "learned"}
        )["valid"] is False,
        None,
    )


# ==========================================================
# FIX 3 — PATTERN CURRICULUM BOUNDARY
# ==========================================================

def test_three_pattern_families_exist():

    return _check(
        "F2-3 the three brief pattern families exist",
        set(FAMILY_KEYS) == {
            FAMILY_RESIDENTIAL, FAMILY_COMMERCIAL, FAMILY_MIXED_USE
        }
        and len(PATTERN_FAMILIES) == 3,
        list(FAMILY_KEYS),
    )


def test_residential_available_commercial_and_mixed_blocked():

    coverage = pattern_curriculum.coverage()

    return _check(
        "F2-3 residential is AVAILABLE; commercial and mixed-use are BLOCKED",
        coverage["available_families"] == [FAMILY_RESIDENTIAL]
        and set(coverage["blocked_families"]) == {
            FAMILY_COMMERCIAL, FAMILY_MIXED_USE
        }
        and coverage["partial"] is True,
        {
            "available": coverage["available_families"],
            "blocked": coverage["blocked_families"],
        },
    )


def test_blocked_families_say_why():

    blocked = pattern_curriculum.blocked()

    return _check(
        "F2-3 every blocked family states a reason",
        len(blocked) == 2
        and all(f.get("blocked_reason") for f in blocked)
        and all(f.get("pattern_count") == 0 for f in blocked),
        [f.get("key") for f in blocked],
    )


def test_residential_has_a_corpus():

    coverage = pattern_curriculum.coverage()

    residential = [
        f for f in coverage["families"]
        if f["key"] == FAMILY_RESIDENTIAL
    ][0]

    return _check(
        "F2-3 residential patterns are backed by a real corpus",
        residential["available"] is True
        and residential["pattern_count"] > 0
        and len(residential["sources"]) >= 1,
        {
            "count": residential["pattern_count"],
            "sources": residential["sources"],
        },
    )


def test_availability_is_derived_not_hardcoded():

    """Registering a commercial corpus must open the family with NO code
    change here — proof that the boundary is evidence-driven."""

    class _StubBridge:

        def read_report(self):

            return {
                "sources": [
                    {
                        "id": "residential_pattern_library",
                        "exists": True,
                        "counts": {"patterns": 18},
                    },
                    {
                        "id": "commercial_pattern_library",
                        "exists": True,
                        "counts": {"patterns": 7},
                    },
                ]
            }

    stub = PatternCurriculumV1(read_bridge=_StubBridge())

    return _check(
        "F2-3 availability is DERIVED from the read bridge, not hardcoded",
        stub.is_available(FAMILY_COMMERCIAL) is True
        and stub.count_for(FAMILY_COMMERCIAL) == 7
        and stub.is_available(FAMILY_MIXED_USE) is False,
        {"commercial": stub.status_for(FAMILY_COMMERCIAL)},
    )


def test_pattern_module_holds_no_patterns_or_lessons():

    report = pattern_curriculum.report()

    return _check(
        "F2-3 the pattern module holds no patterns and no lessons",
        PATTERNS == ()
        and report["pattern_count"] == 0
        and report["has_patterns"] is False
        and report["lesson_count"] == 0
        and report["has_lessons"] is False
        and report["promotion_implemented"] is False,
        None,
    )


def test_pattern_aspects_are_bilingual():

    fa = pattern_aspects("fa")

    en = pattern_aspects("en")

    return _check(
        "F2-3 the pattern elicitation vocabulary is bilingual",
        len(fa) == len(en) == len(PATTERN_TEACHING_ASPECTS) == 5
        and all(
            a["label"] != b["label"] and a["label"] and b["label"]
            for a, b in zip(fa, en)
        ),
        [a["key"] for a in fa],
    )


def test_sequencer_exposes_the_pattern_boundary():

    plan = curriculum_sequencer.plan(
        curriculum_sequencer.progress_template()
    )

    patterns = [
        step for step in plan["steps"] if step["key"] == "patterns"
    ][0]

    coverage = patterns.get("coverage") or {}

    return _check(
        "F2-3 the patterns step carries its coverage boundary",
        coverage.get("available_families") == [FAMILY_RESIDENTIAL]
        and set(coverage.get("blocked_families") or []) == {
            FAMILY_COMMERCIAL, FAMILY_MIXED_USE
        }
        and "patterns" in curriculum_sequencer.report()[
            "coverage_boundary_steps"
        ],
        {"coverage": coverage.get("available_families")},
    )


def test_only_patterns_step_has_a_coverage_boundary():

    plan = curriculum_sequencer.plan(
        curriculum_sequencer.progress_template()
    )

    with_coverage = [
        step["key"] for step in plan["steps"] if step.get("coverage")
    ]

    return _check(
        "F2-3 only the patterns step declares a coverage boundary",
        with_coverage == ["patterns"],
        {"with_coverage": with_coverage},
    )


# ==========================================================
# SCOPE — NO GEOMETRY / CAD / BIM / IFC / RENDER
# ==========================================================

def test_new_modules_import_no_forbidden_library():

    module_dir = os.path.join(ROOT, "core", "curriculum")

    forbidden = (
        "ezdxf", "ifcopenshell", "shapely", "trimesh", "pyautocad",
        "comfy", "diffusers", "torch", "numpy", "matplotlib",
        "requests", "urllib", "httpx", "flask",
    )

    hits = []

    for name in ("pattern_curriculum_v1.py", "curriculum_sequencer_v1.py"):

        path = os.path.join(module_dir, name)

        with open(path, "r", encoding="utf-8") as handle:

            tree = ast.parse(handle.read(), filename=path)

        for node in ast.walk(tree):

            if isinstance(node, ast.Import):

                modules = [alias.name for alias in node.names]

            elif isinstance(node, ast.ImportFrom):

                modules = [node.module or ""]

            else:

                continue

            for module in modules:

                if module.split(".")[0].lower() in forbidden:

                    hits.append({"module": name, "import": module})

    return _check(
        "F2-6 the new modules import no geometry / render / BIM / network "
        "library",
        not hits,
        {"hits": hits},
    )


def test_no_geometry_vocabulary_in_the_boundary_payload():

    def prune(node):

        if isinstance(node, dict):

            return {
                key: prune(value)
                for key, value in node.items()
                if key not in (
                    "contains_geometry", "contains_coordinates",
                    "contains_walls", "contains_openings",
                    "semantic_only", "render_requested",
                    "comfy_invoked", "geometric",
                )
            }

        if isinstance(node, list):

            return [prune(item) for item in node]

        return node

    payload = json.dumps(
        prune({
            "coverage": pattern_curriculum.coverage(),
            "plan": curriculum_sequencer.plan(
                curriculum_sequencer.progress_template()
            ),
        }),
        ensure_ascii=False,
    ).lower()

    forbidden = (
        "polygon", "vertex", "bounding_box", "centroid",
        "wall_segment", "door_swing", "ifc", "dwg", "dxf", "coordinate",
    )

    hits = [token for token in forbidden if token in payload]

    return _check(
        "F2-6 the boundary payload contains no geometry vocabulary",
        not hits,
        {"hits": hits},
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
        "F2-6 no lesson / layout / floor-plan / geometry module exists",
        not hits,
        {"hits": hits},
    )


def test_no_permanent_learning_anywhere():

    return _check(
        "F2-6 no promotion / permanent-learning path exists",
        PROMOTION_IMPLEMENTED is False
        and PERMANENT_LEARNING_IMPLEMENTED is False
        and set(ALLOWED_STATUSES) == {
            "observed", "needs_confirmation", "rejected"
        }
        and pattern_curriculum.report()["permanent_learning"] is False
        and curriculum_sequencer.report()["permanent_learning"] is False,
        None,
    )


def test_pattern_curriculum_is_read_only():

    report = pattern_curriculum.report()

    return _check(
        "F2-6 the pattern curriculum reports read-only / zero writes",
        report["read_only"] is True
        and report["writes_performed"] == 0
        and report["availability_is_derived"] is True,
        None,
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
    print("  CURRICULUM_FOUNDATION_FIX_02")
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
