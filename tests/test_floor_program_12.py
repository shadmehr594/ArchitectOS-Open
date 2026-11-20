# ==========================================================
# PHASE 12 — FLOOR PROGRAM REASONING CONTRACT TESTS
#
# ISOLATED CONTRACT tests. They are NOT the acceptance proof: real
# acceptance runs against the live runtime path
# (tools/run_floor_program_12_acceptance.py).
#
# Scope under test:
#   requirement -> building program understanding
#               -> FLOOR PROGRAM MODEL
#               -> REASONED PROGRAM + trace
#
# Deliberately NOT tested here because the phase forbids them:
#   floor plans, coordinates, walls, doors, CAD, BIM, IFC, renders.
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_floor_program_12.py
#   .venv/Scripts/python.exe tests/test_floor_program_12.py
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
    tempfile.gettempdir(), "architectos_phase12_contract"
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


from core.curriculum.space_types_v1 import space_types

from core.curriculum.adjacency_model_v1 import adjacency_model

from core.curriculum.privacy_logic_v1 import privacy_logic

from core.curriculum.zone_model_v1 import (
    zone_model,
    ALL_ZONES,
    ZONE_PUBLIC,
    ZONE_SEMI_PUBLIC,
    ZONE_PRIVATE,
    ZONE_SERVICE,
    ZONE_CIRCULATION,
    ZONE_EXTERNAL,
)

from core.curriculum.bubble_diagram_v1 import (
    bubble_diagram_builder,
    PROGRAM_SPACE_MAP,
)

from core.curriculum.program_model_v1 import (
    program_model,
    CONTRACT as MODEL_CONTRACT,
    VERSION as MODEL_VERSION,
    ALL_BUILDING_TYPES,
    PRIMARY_BUILDING_TYPES,
    BUILDING_TYPE_RESIDENTIAL,
    BUILDING_TYPE_COMMERCIAL,
    BUILDING_TYPE_MIXED_USE,
    BUILDING_TYPE_VILLA,
    ALL_PRIORITIES,
    PRIORITY_P1,
    PRIORITY_P2,
    PRIORITY_P3,
    ALL_CONSTRAINT_KINDS,
    CONSTRAINT_FORBIDDEN_OPENING,
    CONSTRAINT_BUFFERED_CONNECTION,
    CONSTRAINT_PRIVACY_SEPARATION,
    CONSTRAINT_CONTROLLED_ACCESS,
    CONSTRAINT_CAPACITY,
    PROGRAM_ZONE_TO_PHASE11,
)

from core.curriculum.program_classifier_v1 import (
    program_classifier,
    CONTRACT as CLASSIFIER_CONTRACT,
)

from core.curriculum.floor_program_v1 import (
    floor_program_reasoning,
    CONTRACT as REASONING_CONTRACT,
)

from core.curriculum.program_curriculum_v1 import (
    program_curriculum,
    PROGRAM_TEACHING_ASPECTS,
    program_aspects,
)

from core.conversation.teaching_candidate_v1 import (
    ALLOWED_STATUSES,
    PERMANENT_LEARNING_IMPLEMENTED,
)

from core.conversation.knowledge_promotion_bridge_v1 import (
    PROMOTION_IMPLEMENTED,
)


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))

    return bool(passed)


# ----------------------------------------------------------
# CANONICAL INPUTS
# ----------------------------------------------------------

FA_RESIDENTIAL = (
    "\u062e\u0627\u0646\u0647 \u0633\u0647 \u062e\u0648\u0627\u0628\u0647 "
    "\u0628\u0631\u0627\u06cc \u062e\u0627\u0646\u0648\u0627\u062f\u0647 "
    "\u0686\u0647\u0627\u0631 \u0646\u0641\u0631\u0647"
)

FA_COMMERCIAL = (
    "\u0645\u062c\u062a\u0645\u0639 \u062a\u062c\u0627\u0631\u06cc "
    "\u0628\u0627 \u0641\u0631\u0648\u0634\u06af\u0627\u0647 \u0648 "
    "\u0631\u0633\u062a\u0648\u0631\u0627\u0646"
)

FA_MIXED = (
    "\u0633\u0627\u062e\u062a\u0645\u0627\u0646 \u062a\u0631\u06a9\u06cc\u0628\u06cc "
    "\u062a\u062c\u0627\u0631\u06cc \u0648 \u0645\u0633\u06a9\u0648\u0646\u06cc"
)

EN_RESIDENTIAL = "A house with 3 bedrooms for a family of four"

EN_COMMERCIAL = "A commercial building with retail and offices"

EN_MIXED = "A mixed-use building with retail and apartments"


def _residential():
    return floor_program_reasoning.reason(FA_RESIDENTIAL, "fa")


def _commercial():
    return floor_program_reasoning.reason(FA_COMMERCIAL, "fa")


def _mixed():
    return floor_program_reasoning.reason(FA_MIXED, "fa")


# ==========================================================
# PART 1 — BUILDING PROGRAM UNDERSTANDING
# ==========================================================

def test_residential_classification():

    result = program_classifier.classify(FA_RESIDENTIAL)

    return _check(
        "12 residential is recognised (Persian)",
        result["building_type"] == BUILDING_TYPE_RESIDENTIAL
        and result["is_primary_type"] is True,
        {"type": result["building_type"], "src": result["building_type_source"]},
    )


def test_commercial_classification():

    result = program_classifier.classify(FA_COMMERCIAL)

    return _check(
        "12 commercial is recognised (Persian)",
        result["building_type"] == BUILDING_TYPE_COMMERCIAL,
        {"type": result["building_type"], "src": result["building_type_source"]},
    )


def test_mixed_use_classification():

    result = program_classifier.classify(FA_MIXED)

    return _check(
        "12 mixed use is recognised (Persian)",
        result["building_type"] == BUILDING_TYPE_MIXED_USE
        and BUILDING_TYPE_RESIDENTIAL in result["building_type_components"]
        and BUILDING_TYPE_COMMERCIAL in result["building_type_components"],
        {"type": result["building_type"], "src": result["building_type_source"]},
    )


def test_mixed_use_needs_both_fields():

    """One field alone must NOT be read as mixed use."""

    residential = program_classifier.classify(
        "\u062e\u0627\u0646\u0647 \u0645\u0633\u06a9\u0648\u0646\u06cc"
    )

    commercial = program_classifier.classify(
        "\u0645\u062c\u062a\u0645\u0639 \u062a\u062c\u0627\u0631\u06cc"
    )

    return _check(
        "12 mixed use requires BOTH residential and commercial evidence",
        residential["building_type"] == BUILDING_TYPE_RESIDENTIAL
        and commercial["building_type"] == BUILDING_TYPE_COMMERCIAL,
        {
            "residential": residential["building_type"],
            "commercial": commercial["building_type"],
        },
    )


def test_building_type_english():

    cases = [
        (EN_RESIDENTIAL, BUILDING_TYPE_RESIDENTIAL),
        (EN_COMMERCIAL, BUILDING_TYPE_COMMERCIAL),
        (EN_MIXED, BUILDING_TYPE_MIXED_USE),
    ]

    wrong = [
        {"text": text, "got": program_classifier.classify(text)["building_type"],
         "want": want}
        for text, want in cases
        if program_classifier.classify(text)["building_type"] != want
    ]

    return _check(
        "12 English classification agrees with Persian",
        not wrong,
        wrong,
    )


def test_occupancy_requires_adjacency():

    """A number is an OCCUPANCY only when next to a person word."""

    cases = [
        (FA_RESIDENTIAL, 4),
        (EN_RESIDENTIAL, 4),
        ("\u062e\u0627\u0646\u0647 \u06f3 \u062e\u0648\u0627\u0628\u0647 "
         "\u0628\u0631\u0627\u06cc \u06f4 \u0646\u0641\u0631", 4),
        ("A house with 2 bedrooms for 5 people", 5),
        # no person word -> no occupancy, even though numbers exist
        ("\u0648\u06cc\u0644\u0627 \u06f5 \u062e\u0648\u0627\u0628\u0647", None),
        ("A 4 bedroom house", None),
    ]

    wrong = []

    for text, want in cases:

        got = program_classifier.classify(text)["occupancy"].get(
            "household_size"
        )

        if got != want:

            wrong.append({"text": text, "got": got, "want": want})

    return _check(
        "12 occupancy needs a number ADJACENT to a person word",
        not wrong,
        wrong,
    )


def test_bedroom_count_is_delegated_to_phase11():

    """Phase 12 must NOT re-implement the bedroom parser."""

    result = program_classifier.classify(FA_RESIDENTIAL)

    return _check(
        "12 bedroom count is delegated to the Phase 11 parser",
        result["occupancy"]["bedrooms"] == 3
        and result["occupancy"]["bedrooms_source"]
        == "PHASE_11_PROGRAM_PARSER"
        and program_classifier.report()["bedroom_count_delegated_to"]
        == "core/curriculum/bubble_diagram_v1.py",
        result["occupancy"],
    )


# ==========================================================
# PART 2 — FLOOR PROGRAM MODEL
# ==========================================================

PROGRAM_SECTIONS = (
    "zones",
    "spaces",
    "relationships",
    "priorities",
    "constraints",
)


def test_program_contract_has_all_sections():

    program = _residential()["floor_program"]

    missing = [key for key in PROGRAM_SECTIONS if key not in program]

    return _check(
        "12 the floor program carries zones/spaces/relationships/"
        "priorities/constraints",
        not missing
        and program["contract"] == MODEL_CONTRACT
        and program["version"] == MODEL_VERSION,
        {"missing": missing},
    )


def test_program_is_semantic_only():

    program = _residential()["floor_program"]

    return _check(
        "12 the floor program is semantic only",
        program["semantic_only"] is True
        and program["contains_geometry"] is False
        and program["contains_coordinates"] is False
        and program["contains_walls"] is False
        and program["contains_openings"] is False
        and program["render_requested"] is False
        and program["comfy_invoked"] is False
        and program["llm_used"] is False
        and program["network_used"] is False,
        {"geometry": program["contains_geometry"]},
    )


def test_every_space_resolves_and_declares_its_zone():

    program = _residential()["floor_program"]

    unresolved = program["unresolved_spaces"]

    no_zone = [
        s["program_name"] for s in program["spaces"] if not s["zone"]
    ]

    return _check(
        "12 every program space resolves to a space id and a zone",
        not unresolved and not no_zone,
        {"unresolved": unresolved, "no_zone": no_zone},
    )


def test_zone_comes_from_phase10_category():

    """Phase 10 stays the single source of truth for a space's zone."""

    program = _residential()["floor_program"]

    wrong = [
        s["space_id"] for s in program["spaces"]
        if s["space_id"]
        and s["zone"] != zone_model.zone_of(s["space_id"])
    ]

    sources = {s["zone_source"] for s in program["spaces"] if s["space_id"]}

    return _check(
        "12 zone is taken from the Phase 10 category, not re-derived",
        not wrong and sources == {"phase10_category"},
        {"wrong": wrong, "sources": sorted(sources)},
    )


def test_zone_fallback_is_flagged_as_approximation():

    """The frozen program's own zone word is a FALLBACK only, and the
    one approximated value must say so."""

    report = program_model.report()

    return _check(
        "12 program-zone fallback is marked, and approximations are flagged",
        report["program_zone_fallback"].get("public") == ZONE_PUBLIC
        and report["program_zone_fallback"].get("performance") == ZONE_PUBLIC
        and "performance" in report["approximated_program_zones"],
        report["program_zone_fallback"],
    )


def test_bedrooms_are_expanded_by_phase11():

    """3 bedrooms must become one master + two bedrooms, and the
    curriculum completion must add dining + storage."""

    result = _residential()

    program = result["floor_program"]

    bedrooms = len(
        [
            s for s in program["spaces"]
            if s["space_id"] in (
                "MASTER_BEDROOM_SLEEPING", "BEDROOM_DOUBLE"
            )
        ]
    )

    ids = [s["space_id"] for s in program["spaces"]]

    return _check(
        "12 the bedroom count expands into real sleeping spaces",
        bedrooms == 3
        and "DINING" in ids
        and "STORAGE_LINEN" in ids
        and result["program_source"] == "PHASE_11_PROGRAM_SPACES",
        {"bedrooms": bedrooms, "ids": ids},
    )


def test_priorities_are_assigned():

    program = _residential()["floor_program"]

    priorities = {s["priority"] for s in program["spaces"]}

    summary = program["priorities"]

    return _check(
        "12 every space has a priority and the summary is complete",
        priorities <= set(ALL_PRIORITIES)
        and priorities
        and [p["priority"] for p in summary] == list(ALL_PRIORITIES)
        and sum(p["count"] for p in summary) == len(program["spaces"]),
        {"priorities": sorted(priorities)},
    )


def test_priority_p3_only_for_optional():

    """A required space must never be P3; an optional one must be."""

    program = _mixed()["floor_program"]

    wrong = [
        s["program_name"] for s in program["spaces"]
        if (s["required"] and s["priority"] == PRIORITY_P3)
        or ((not s["required"]) and s["priority"] != PRIORITY_P3)
    ]

    return _check(
        "12 optional spaces are P3 and required spaces never are",
        not wrong,
        {"wrong": wrong},
    )


def test_constraints_are_derived_from_phase10():

    program = _residential()["floor_program"]

    kinds = {c["kind"] for c in program["constraints"]}

    ok = (
        bool(program["constraints"])
        and kinds <= set(ALL_CONSTRAINT_KINDS)
        and all(c.get("geometric") is False
                for c in program["constraints"])
    )

    # a FORBIDDEN/AVOID pair must really exist in the adjacency model
    pair = [
        c for c in program["constraints"]
        if c["kind"] in (
            CONSTRAINT_FORBIDDEN_OPENING, CONSTRAINT_BUFFERED_CONNECTION
        )
    ]

    if pair:

        source, target = pair[0]["spaces"]

        relation = adjacency_model.relation(source, target)

        ok = ok and bool(relation) and (
            relation["relation_type"]
            == pair[0]["relation_type"]
        )

    return _check(
        "12 constraints are derived from the Phase 10 adjacency model",
        ok,
        {"kinds": sorted(kinds), "count": len(program["constraints"])},
    )


def test_capacity_constraint_fires_only_when_under_provided():

    """An ADEQUATE program must raise NO capacity warning; an
    under-provided one must raise one.

    Testing both directions matters: an empty constraint list is the
    honest answer when nothing is wrong, so asserting "a constraint
    exists" for the adequate case would pin a bug, not a behaviour.
    """

    adequate = _residential()

    under = floor_program_reasoning.reason(
        "\u062e\u0627\u0646\u0647 \u062f\u0648 \u062e\u0648\u0627\u0628\u0647 "
        "\u0628\u0631\u0627\u06cc \u062e\u0627\u0646\u0648\u0627\u062f\u0647 "
        "\u0634\u0634 \u0646\u0641\u0631\u0647",
        "fa",
    )

    adequate_capacity = [
        c for c in adequate["floor_program"]["constraints"]
        if c["kind"] == CONSTRAINT_CAPACITY
    ]

    under_capacity = [
        c for c in under["floor_program"]["constraints"]
        if c["kind"] == CONSTRAINT_CAPACITY
    ]

    return _check(
        "12 CAPACITY fires only when the program is under-provided",
        not adequate_capacity
        and bool(under_capacity)
        and all(c.get("geometric") is False for c in under_capacity)
        and all("demand" in c and "provided" in c for c in under_capacity),
        {
            "adequate_capacity": len(adequate_capacity),
            "under_capacity": len(under_capacity),
            "under_occupancy": under["occupancy"],
        },
    )


def test_privacy_separation_constraint_present():

    program = _residential()["floor_program"]

    kinds = {c["kind"] for c in program["constraints"]}

    return _check(
        "12 private spaces raise a PRIVACY_SEPARATION constraint",
        CONSTRAINT_PRIVACY_SEPARATION in kinds,
        sorted(kinds),
    )


def test_relationships_are_graded_where_known():

    program = _mixed()["floor_program"]

    relationships = program["relationships"]

    graded = [r for r in relationships if r["grade"]]

    return _check(
        "12 declared relationships are graded through Phase 10",
        bool(relationships)
        and bool(graded)
        and all(r.get("geometric") is False for r in relationships),
        {"total": len(relationships), "graded": len(graded)},
    )


def test_program_does_not_duplicate_the_space_map():

    """The program layer must REUSE Phase 11's map, not copy it."""

    import core.curriculum.program_model_v1 as module

    source = open(module.__file__, "r", encoding="utf-8").read()

    return _check(
        "12 the space map is imported from Phase 11, never redefined",
        "PROGRAM_SPACE_MAP" in source
        and "from core.curriculum.bubble_diagram_v1 import" in source
        and "PROGRAM_SPACE_MAP = {" not in source,
        {"map_size": len(PROGRAM_SPACE_MAP)},
    )


# ==========================================================
# PART 3 — PROGRAM REASONING
# ==========================================================

def test_reasoning_trace_is_produced():

    result = _residential()

    steps = [line["step"] for line in result["reasoning"]]

    return _check(
        "12 the reasoning trace names every step",
        steps == [
            "building_type",
            "occupancy",
            "required_spaces",
            "curriculum_completion",
            "zones",
            "privacy_hierarchy",
            "priorities",
            "constraints",
            "scope",
        ]
        and bool(result["narrative"]),
        {"steps": steps},
    )


def test_reasoning_matches_the_brief_example():

    """The brief's example: a 3-bedroom house for four people must
    reason out living/kitchen/dining/3 bedrooms/bathroom/circulation/
    storage across the public, semi-public, private and service zones."""

    result = _residential()

    program = result["floor_program"]

    ids = {s["space_id"] for s in program["spaces"]}

    zones = {z["name"] for z in program["zones"]}

    ok = (
        "LIVING_RECEPTION" in ids
        and "OPEN_KITCHEN" in ids
        and "DINING" in ids
        and "FAMILY_BATHROOM" in ids
        and "PRIVATE_HALL_CORRIDOR" in ids
        and "STORAGE_LINEN" in ids
        and zones >= {ZONE_PUBLIC, ZONE_SEMI_PUBLIC, ZONE_PRIVATE,
                      ZONE_SERVICE}
    )

    return _check(
        "12 the brief's residential example reasons out correctly",
        ok,
        {"zones": sorted(zones), "spaces": len(ids)},
    )


def test_reasoning_is_deterministic_and_offline():

    first = _residential()

    second = _residential()

    ok = (
        first["narrative"] == second["narrative"]
        and first["floor_program"]["counts"]
        == second["floor_program"]["counts"]
        and first["deterministic"] is True
        and first["llm_used"] is False
        and first["network_used"] is False
        and first["render_requested"] is False
    )

    return _check(
        "12 reasoning is deterministic and offline",
        ok,
        None,
    )


def test_space_summary_collapses_repeats():

    result = _residential()

    summary = result["space_summary"]

    bedrooms = [
        item for item in summary
        if item["space_id"] == "BEDROOM_DOUBLE"
    ]

    return _check(
        "12 the space summary collapses repeated instances",
        len(bedrooms) == 1 and bedrooms[0]["count"] == 2,
        {"bedroom_rows": len(bedrooms)},
    )


def test_required_names_is_human_readable():

    result = _residential()

    names = floor_program_reasoning.required_names(
        result["space_summary"], "en"
    )

    return _check(
        "12 required spaces render as a readable list",
        "2 x" in names and "," in names and len(names) > 20,
        {"names": names[:120]},
    )


# ==========================================================
# PART 4 — EXAMPLES: RESIDENTIAL / COMMERCIAL / MIXED USE
# ==========================================================

def test_residential_example():

    result = _residential()

    return _check(
        "12 residential example produces a full program",
        result["building_type"] == BUILDING_TYPE_RESIDENTIAL
        and result["floor_program"]["counts"]["spaces"] >= 9
        and result["floor_program"]["counts"]["zones"] >= 4
        and result["language"] == "fa",
        result["floor_program"]["counts"],
    )


def test_commercial_example():

    result = _commercial()

    ids = {s["space_id"] for s in result["floor_program"]["spaces"]}

    return _check(
        "12 commercial example produces retail + office + service",
        result["building_type"] == BUILDING_TYPE_COMMERCIAL
        and "retail" in ids
        and "office_room" in ids
        and "service_core" in ids,
        {"spaces": sorted(i for i in ids if i)},
    )


def test_mixed_use_example():

    result = _mixed()

    ids = {s["space_id"] for s in result["floor_program"]["spaces"]}

    return _check(
        "12 mixed-use example carries BOTH a commercial and a "
        "residential component",
        result["building_type"] == BUILDING_TYPE_MIXED_USE
        and "retail" in ids
        and "LIVING_RECEPTION" in ids
        and "BEDROOM_DOUBLE" in ids,
        {"spaces": sorted(i for i in ids if i)},
    )


def test_optional_spaces_are_marked():

    result = _mixed()

    program = result["floor_program"]

    optional = [s for s in program["spaces"] if not s["required"]]

    return _check(
        "12 optional spaces are distinguished from required ones",
        program["counts"]["optional"] == len(optional)
        and program["counts"]["required"]
        + program["counts"]["optional"]
        == program["counts"]["spaces"]
        and bool(optional),
        {"required": program["counts"]["required"],
         "optional": program["counts"]["optional"]},
    )


# ==========================================================
# PART 5 — PERSIAN + ENGLISH
# ==========================================================

def test_persian_and_english_agree():

    fa = floor_program_reasoning.reason(FA_RESIDENTIAL, "fa")

    en = floor_program_reasoning.reason(EN_RESIDENTIAL, "en")

    fa_ids = sorted(s["space_id"] for s in fa["floor_program"]["spaces"])

    en_ids = sorted(s["space_id"] for s in en["floor_program"]["spaces"])

    return _check(
        "12 Persian and English requirements produce the same program",
        fa_ids == en_ids
        and fa["building_type"] == en["building_type"]
        and fa["language"] == "fa"
        and en["language"] == "en",
        {"fa": fa_ids, "en": en_ids},
    )


def test_narrative_language_follows_the_request():

    fa = floor_program_reasoning.reason(FA_RESIDENTIAL, "fa")

    en = floor_program_reasoning.reason(EN_RESIDENTIAL, "en")

    def persian(text):

        return any("\u0600" <= ch <= "\u06ff" for ch in str(text or ""))

    return _check(
        "12 the narrative is written in the requested language",
        persian(fa["narrative"])
        and not persian(en["narrative"]),
        {"fa": fa["narrative"][:60], "en": en["narrative"][:60]},
    )


def test_zone_and_priority_labels_are_bilingual():

    from core.curriculum.program_model_v1 import priority_display

    ok = (
        priority_display(PRIORITY_P1, "fa")
        != priority_display(PRIORITY_P1, "en")
        and priority_display(PRIORITY_P1, "en")
        and program_aspects("fa")[0]["label"]
        != program_aspects("en")[0]["label"]
    )

    return _check(
        "12 zone/priority/aspect labels are bilingual",
        ok,
        {"p1_fa": priority_display(PRIORITY_P1, "fa")},
    )


# ==========================================================
# PART 5 — TEACHING COMPATIBILITY
# ==========================================================

def test_program_teaching_aspects():

    report = program_curriculum.report()

    ok = (
        report["aspect_count"] == 5
        and len(program_aspects("fa")) == 5
        and len(program_aspects("en")) == 5
        and report["candidate_only"] is True
        and report["promotion_implemented"] is False
    )

    return _check(
        "12 five program teaching aspects exist, candidate only",
        ok,
        [a[0] for a in PROGRAM_TEACHING_ASPECTS],
    )


def test_program_topic_resolution_does_not_swallow_other_topics():

    program_topics = (
        "\u0645\u06cc \u062e\u0648\u0627\u0647\u0645 "
        "\u0628\u0631\u0646\u0627\u0645\u0647\u0654 \u0641\u0636\u0627\u06cc\u06cc "
        "\u0631\u0627 \u06cc\u0627\u062f \u0628\u062f\u0647\u0645",
        "I want to teach you about the floor program",
    )

    other_topics = (
        "\u0645\u06cc \u062e\u0648\u0627\u0647\u0645 "
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0631\u0627 "
        "\u06cc\u0627\u062f \u0628\u062f\u0647\u0645",
        "\u0645\u06cc \u062e\u0648\u0627\u0647\u0645 "
        "\u062f\u06cc\u0627\u06af\u0631\u0627\u0645 \u0641\u0636\u0627\u06cc\u06cc "
        "\u0631\u0627 \u06cc\u0627\u062f \u0628\u062f\u0647\u0645",
        "\u0645\u06cc \u062e\u0648\u0627\u0647\u0645 \u0628\u0627\u0645 "
        "\u0631\u0627 \u06cc\u0627\u062f \u0628\u062f\u0647\u0645",
    )

    ok = all(
        program_curriculum.resolve_program_topic(text, "fa")
        for text in program_topics
    ) and not any(
        program_curriculum.resolve_program_topic(text, "fa")
        for text in other_topics
    )

    return _check(
        "12 program topics resolve, and space/diagram topics are NOT "
        "swallowed",
        ok,
        None,
    )


def test_teaching_stays_candidate_only():

    ok = (
        PROMOTION_IMPLEMENTED is False
        and PERMANENT_LEARNING_IMPLEMENTED is False
        and set(ALLOWED_STATUSES) == {
            "observed", "needs_confirmation", "rejected"
        }
        and program_curriculum.report()["promotion_implemented"] is False
    )

    return _check(
        "12 no promotion / permanent-learning path exists",
        ok,
        list(ALLOWED_STATUSES),
    )


# ==========================================================
# SCOPE — NO RENDER / GEOMETRY / BIM / IFC / CAD
# ==========================================================

def test_phase12_modules_import_no_geometry_library():

    """Parse IMPORTS with ast, not the file text: these modules discuss
    geometry in their comments ("no polygons")."""

    module_dir = os.path.join(ROOT, "core", "curriculum")

    phase12 = (
        "program_model_v1.py",
        "program_classifier_v1.py",
        "floor_program_v1.py",
        "program_curriculum_v1.py",
    )

    forbidden = (
        "ezdxf", "ifcopenshell", "shapely", "trimesh", "pyautocad",
        "comfy", "diffusers", "torch", "numpy", "matplotlib",
        "requests", "urllib", "httpx", "flask",
    )

    hits = []

    for name in phase12:

        path = os.path.join(module_dir, name)

        if not os.path.isfile(path):

            hits.append({"missing": name})

            continue

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
        "12 Phase 12 modules import no geometry / render / BIM / network "
        "library",
        not hits,
        {"hits": hits[:6]},
    )


def test_no_geometry_vocabulary_in_the_payload():

    """Scan the STRUCTURAL payload for coordinate vocabulary.

    Two legitimate sources of the words are excluded, and both are
    excluded for a reason:

      * the scope guarantee flags - `"contains_coordinates": false` IS
        the guarantee, not a violation of it;
      * the reasoning trace and narrative - their whole job is to STATE
        that no geometry was produced ("no coordinates, no walls").

    What is actually being tested is that no coordinate DATA appears in
    the spaces, zones, relationships, priorities or constraints.
    """

    def prune(node):

        if isinstance(node, dict):

            return {
                key: prune(value)
                for key, value in node.items()
                if key not in (
                    # scope guarantee flags
                    "contains_geometry",
                    "contains_coordinates",
                    "contains_walls",
                    "contains_openings",
                    "semantic_only",
                    "render_requested",
                    "comfy_invoked",
                    "geometric",
                    # prose that states the absence of geometry
                    "reasoning",
                    "narrative",
                )
            }

        if isinstance(node, list):

            return [prune(item) for item in node]

        return node

    payload = json.dumps(
        prune(_residential()), ensure_ascii=False
    ).lower()

    forbidden = (
        "polygon", "vertex", "vertices", "bounding_box", "centroid",
        "wall_segment", "door_swing", "ifc", "dwg", "dxf", "coordinate",
    )

    hits = [token for token in forbidden if token in payload]

    return _check(
        "12 the structural program payload contains no geometry "
        "vocabulary",
        not hits,
        {"hits": hits},
    )


def test_all_reports_declare_read_only():

    reports = {
        "model": program_model.report(),
        "classifier": program_classifier.report(),
        "reasoning": floor_program_reasoning.report(),
        "curriculum": program_curriculum.report(),
    }

    bad = {
        name: report.get("writes_performed")
        for name, report in reports.items()
        if report.get("read_only") is not True
        or report.get("writes_performed") != 0
    }

    return _check(
        "12 every Phase 12 surface reports read-only / zero writes",
        not bad,
        bad,
    )


def test_no_layout_or_floorplan_module_created():

    module_dir = os.path.join(ROOT, "core", "curriculum")

    forbidden = (
        "layout_generation", "floorplan", "floor_plan", "geometry",
        "wall", "opening", "cad", "bim", "ifc", "render",
    )

    hits = [
        name for name in os.listdir(module_dir)
        if name.endswith(".py")
        and any(token in name.lower() for token in forbidden)
    ]

    return _check(
        "12 no layout / floor-plan / geometry module was created",
        not hits,
        {"hits": hits},
    )


# ==========================================================
# PROJECT ISOLATION
# ==========================================================

def test_program_is_project_scoped_and_stateless():

    first = floor_program_reasoning.reason(
        FA_RESIDENTIAL, "fa", project_id="project_aaa"
    )

    second = floor_program_reasoning.reason(
        FA_RESIDENTIAL, "fa", project_id="project_bbb"
    )

    return _check(
        "12 the program is project-scoped and stateless",
        first["project_id"] == "project_aaa"
        and second["project_id"] == "project_bbb"
        and first["floor_program"]["counts"]
        == second["floor_program"]["counts"]
        and first["narrative"] == second["narrative"],
        {"a": first["project_id"], "b": second["project_id"]},
    )


def test_program_reads_the_corpus_without_writing_it():

    from core.conversation.knowledge_read_bridge_v1 import (
        knowledge_read_bridge,
    )

    report = knowledge_read_bridge.read_report()

    return _check(
        "12 the corpus is read through the Phase 09 bridge, never written",
        report["read_only"] is True
        and report["writes_performed"] == 0,
        None,
    )


def test_program_consumes_phase11_not_a_second_knowledge_base():

    result = _residential()

    provenance = result["floor_program"]["provenance"]

    return _check(
        "12 the program layer consumes the Phase 10/11 corpus",
        provenance["spaces"] == "core/curriculum/space_types_v1.py"
        and provenance["zones"] == "core/curriculum/zone_model_v1.py"
        and provenance["relationships"]
        == "core/curriculum/adjacency_model_v1.py"
        and provenance["space_map"]
        == "core/curriculum/bubble_diagram_v1.py",
        provenance,
    )


def test_unknown_building_type_falls_back_honestly():

    """An empty requirement must still produce a program, and must say
    that it defaulted."""

    result = floor_program_reasoning.reason("", "en")

    return _check(
        "12 an unclassifiable requirement defaults and says so",
        result["classification"]["building_type_source"]
        == "DEFAULT_RESIDENTIAL"
        and result["classification"]["building_type_confidence"] < 0.9
        and result["floor_program"]["counts"]["spaces"] > 0,
        {"src": result["classification"]["building_type_source"]},
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
    print("  PHASE 12 - FLOOR PROGRAM REASONING")
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
