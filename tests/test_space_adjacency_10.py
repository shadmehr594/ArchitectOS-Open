# ==========================================================
# PHASE 10 — SPACE TYPES + ADJACENCY INTELLIGENCE CONTRACT TESTS
#
# ISOLATED CONTRACT tests. They are NOT the acceptance proof: real
# acceptance runs against the live runtime path
# (tools/run_space_adjacency_10_acceptance.py).
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_space_adjacency_10.py
#   .venv/Scripts/python.exe tests/test_space_adjacency_10.py
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
    tempfile.gettempdir(), "architectos_phase10_contract"
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


from core.curriculum.space_types_v1 import (
    space_types,
    ALL_CATEGORIES,
    CATEGORY_PUBLIC,
    CATEGORY_SEMI_PUBLIC,
    CATEGORY_PRIVATE,
    CATEGORY_SERVICE,
    CATEGORY_CIRCULATION,
    CATEGORY_EXTERNAL,
    PREFERRED_TERM,
    OVERLAY_SPACES,
)

from core.curriculum.adjacency_model_v1 import (
    adjacency_model,
    ALL_RELATION_TYPES,
    REL_STRONG,
    REL_NORMAL,
    REL_WEAK,
    REL_AVOID,
    REL_FORBIDDEN,
    RELATION_OVERLAY,
)

from core.curriculum.privacy_logic_v1 import privacy_logic

from core.curriculum.space_query_v1 import (
    space_query,
    QUERY_CLASSIFICATION,
    QUERY_POSITIVE_RELATION,
    QUERY_NEGATIVE_RELATION,
    VERDICT_CORRECT,
    VERDICT_ACCEPTABLE,
    VERDICT_CONFIRMED,
)

from core.curriculum.space_curriculum_v1 import (
    space_curriculum,
    SPACE_TEACHING_ASPECTS,
    space_aspects,
)

from core.conversation.knowledge_read_bridge_v1 import (
    knowledge_read_bridge,
)

from core.conversation.knowledge_promotion_bridge_v1 import (
    PROMOTION_IMPLEMENTED,
)

from core.conversation.teaching_candidate_v1 import (
    teaching_candidate_store,
    ALLOWED_STATUSES,
)


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))

    return bool(passed)


# ==========================================================
# PART 1 — SPACE TYPE MODEL
# ==========================================================

REQUIRED_SPACE_FIELDS = (
    "space_id",
    "name",
    "aliases",
    "category",
    "zone",
    "privacy_level",
    "circulation_role",
    "functional_role",
    "typical_adjacent",
    "discouraged_adjacent",
    "access_requirements",
    "examples",
    "provenance",
    "sources",
)


def test_space_record_contract():

    spaces = space_types.spaces()

    missing = []

    for space_id, record in spaces.items():

        for field in REQUIRED_SPACE_FIELDS:

            if field not in record:

                missing.append(space_id + "." + field)

    return _check(
        "10-1 every space carries the Part 1 contract fields",
        spaces and not missing,
        {"count": len(spaces), "missing": missing[:8]},
    )


def test_space_categories_closed():

    spaces = space_types.spaces()

    used = sorted({r.get("category") for r in spaces.values()})

    ok = (
        set(used).issubset(set(ALL_CATEGORIES))
        and len(set(used)) == len(ALL_CATEGORIES)
    )

    return _check(
        "10-1 all six curriculum categories are used",
        ok,
        {"used": used, "allowed": list(ALL_CATEGORIES)},
    )


def test_space_reuses_existing_corpus():

    report = space_types.report()

    origins = report.get("by_origin") or {}

    ok = (
        report["space_count"] >= 80
        and origins.get("SPACE_SPECS", 0) >= 40
        and origins.get("ONTOLOGY", 0) >= 40
        and report["read_only"] is True
        and report["writes_performed"] == 0
    )

    return _check(
        "10-1 registry ADAPTS the existing corpus (no duplication)",
        ok,
        {"origins": origins, "count": report["space_count"]},
    )


def test_frozen_privacy_level_preserved():

    """The curriculum category must not overwrite the frozen value."""

    kitchen = space_types.space("OPEN_KITCHEN")

    bathroom = space_types.space("FAMILY_BATHROOM")

    ok = (
        kitchen
        and kitchen["category"] == CATEGORY_SEMI_PUBLIC
        and kitchen["privacy_level"] == "SERVICE"
        and kitchen["category_source"] == "CURRICULUM_OVERLAY"
        and bathroom
        and bathroom["category"] == CATEGORY_SERVICE
        and bathroom["privacy_level"] == "PRIVATE"
    )

    return _check(
        "10-1 curriculum category coexists with the frozen privacy_level",
        ok,
        {
            "kitchen": (kitchen or {}).get("category"),
            "kitchen_privacy": (kitchen or {}).get("privacy_level"),
            "bathroom": (bathroom or {}).get("category"),
            "bathroom_privacy": (bathroom or {}).get("privacy_level"),
        },
    )


def test_brief_example_spaces_resolve():

    expectations = {
        "\u0648\u0631\u0648\u062f\u06cc": "UNIT_ENTRY",
        "\u0646\u0634\u06cc\u0645\u0646": "LIVING_RECEPTION",
        "\u063a\u0630\u0627\u062e\u0648\u0631\u06cc": "DINING",
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647": "OPEN_KITCHEN",
        "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628": "BEDROOM_DOUBLE",
        "\u0627\u062a\u0627\u0642 \u06a9\u0627\u0631": "STUDY",
        "\u062d\u0645\u0627\u0645": "FAMILY_BATHROOM",
        "\u0631\u0627\u0647\u0631\u0648": "PRIVATE_HALL_CORRIDOR",
        "\u0631\u0627\u0647 \u067e\u0644\u0647": "STAIR",
        "\u0628\u0627\u0644\u06a9\u0646": "TERRACE_BALCONY",
        "\u062d\u06cc\u0627\u0637": "PRIVATE_YARD",
        "\u0627\u0646\u0628\u0627\u0631\u06cc": "STORAGE_LINEN",
        "kitchen": "OPEN_KITCHEN",
        "bedroom": "BEDROOM_DOUBLE",
        "entrance": "UNIT_ENTRY",
        "bathroom": "FAMILY_BATHROOM",
        "study": "STUDY",
    }

    failures = []

    for term, expected in expectations.items():

        got = space_types.find(term)

        if got != expected:

            failures.append(
                {"term": term, "expected": expected, "got": got}
            )

    return _check(
        "10-1 the brief's example spaces resolve to the richest record",
        not failures,
        failures,
    )


def test_study_space_was_missing_and_is_now_added():

    study = space_types.space("STUDY")

    ok = (
        "STUDY" in OVERLAY_SPACES
        and study
        and study["origin"] == "CURRICULUM_OVERLAY"
        and study["category"] == CATEGORY_PRIVATE
        and study["name"]["fa"]
        and study["examples"]
    )

    return _check(
        "10-1 STUDY (missing from both models) is added additively",
        ok,
        {"study": study},
    )


# ==========================================================
# PART 2 — ADJACENCY MODEL
# ==========================================================

def test_relation_vocabulary_is_five_grades():

    ok = set(ALL_RELATION_TYPES) == {
        REL_STRONG, REL_NORMAL, REL_WEAK, REL_AVOID, REL_FORBIDDEN
    }

    return _check(
        "10-2 five relation grades exist",
        ok,
        {"types": list(ALL_RELATION_TYPES)},
    )


def test_relations_are_not_boolean():

    report = adjacency_model.report()

    used = report.get("by_relation_type") or {}

    ok = (
        report["relation_count"] >= 50
        and len(used) >= 4
        and report["boolean_relations"] is False
    )

    return _check(
        "10-2 relationships are graded, not boolean",
        ok,
        {"by_type": used},
    )


def test_relation_record_contract():

    required = (
        "source_space",
        "target_space",
        "relation_type",
        "reason",
        "confidence",
        "provenance",
    )

    relations = adjacency_model.relations()

    missing = []

    for record in relations:

        for field in required:

            if field not in record:

                missing.append(record.get("relation_id", "?") + "." + field)

    return _check(
        "10-2 every relation carries reason + confidence + provenance",
        relations and not missing,
        {"count": len(relations), "missing": missing[:8]},
    )


def test_brief_canonical_relations():

    expectations = [
        ("\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647",
         "\u063a\u0630\u0627\u062e\u0648\u0631\u06cc", REL_STRONG),
        ("\u0646\u0634\u06cc\u0645\u0646",
         "\u062a\u0631\u0627\u0633", REL_NORMAL),
        ("\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628",
         "\u0646\u0634\u06cc\u0645\u0646", REL_WEAK),
        ("\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628",
         "\u0648\u0631\u0648\u062f\u06cc", REL_AVOID),
        ("\u062d\u0645\u0627\u0645",
         "\u0646\u0634\u06cc\u0645\u0646", REL_FORBIDDEN),
    ]

    failures = []

    for source, target, expected in expectations:

        record = adjacency_model.relation_between(source, target)

        got = (record or {}).get("relation_type")

        if got != expected:

            failures.append(
                {"pair": source + "/" + target,
                 "expected": expected, "got": got}
            )

    return _check(
        "10-2 the brief's five canonical relations are exact",
        not failures,
        failures,
    )


def test_relation_overlay_is_authoritative():

    record = adjacency_model.relation_between(
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647", "\u063a\u0630\u0627\u062e\u0648\u0631\u06cc"
    )

    ok = (
        record
        and record["provenance"] == "CURRICULUM_OVERLAY"
        and record["confidence"] >= 0.9
        and bool(record["reason"])
        and record["derived"] is False
    )

    return _check(
        "10-2 curated relations carry a reason and provenance",
        ok,
        record,
    )


def test_derived_relations_exist():

    derived = [
        r for r in adjacency_model.relations()
        if r["provenance"] != "CURRICULUM_OVERLAY"
    ]

    return _check(
        "10-2 the long tail is DERIVED from the existing corpus",
        len(derived) >= 30,
        {"derived": len(derived)},
    )


# ==========================================================
# PART 3 — PRIVACY LOGIC
# ==========================================================

def test_privacy_bedroom_entrance():

    result = privacy_logic.separation_required(
        "BEDROOM_DOUBLE", "UNIT_ENTRY"
    )

    ok = (
        result["required"] is True
        and result["relation_type"] == REL_AVOID
        and result["privacy_relation"] == "CONFLICT"
    )

    return _check(
        "10-3 bedroom must not open directly to the entrance",
        ok,
        result,
    )


def test_privacy_kitchen_living():

    result = privacy_logic.direct_open_connection_allowed(
        "OPEN_KITCHEN", "LIVING_RECEPTION"
    )

    return _check(
        "10-3 kitchen can connect to the living room",
        result["allowed"] is True,
        result,
    )


def test_privacy_bathroom_controlled_access():

    result = privacy_logic.requires_controlled_access("FAMILY_BATHROOM")

    living = privacy_logic.requires_controlled_access("LIVING_RECEPTION")

    ok = (
        result["required"] is True
        and bool(result["reasons"])
        and living["required"] is False
    )

    return _check(
        "10-3 bathroom requires controlled access",
        ok,
        {"bathroom": result, "living": living},
    )


def test_privacy_bathroom_living_forbidden():

    result = privacy_logic.direct_open_connection_allowed(
        "FAMILY_BATHROOM", "LIVING_RECEPTION"
    )

    return _check(
        "10-3 a bathroom must not open onto the living room",
        result["allowed"] is False
        and result["relation_type"] == REL_FORBIDDEN,
        result,
    )


# ==========================================================
# PART 6 — SPACE / RELATIONSHIP REASONING (A / B / C / D / E)
# ==========================================================

def test_query_space_classification():

    result = space_query.analyze(
        "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 "
        "\u0641\u0636\u0627\u06cc \u062e\u0635\u0648\u0635\u06cc \u0627\u0633\u062a"
    )

    ok = (
        result["query_type"] == QUERY_CLASSIFICATION
        and result["verdict"] == VERDICT_CORRECT
        and result["actual_category"] == CATEGORY_PRIVATE
    )

    return _check(
        "10-6 A space classification works (Persian)",
        ok,
        result,
    )


def test_query_positive_adjacency():

    result = space_query.analyze(
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u06a9\u0646\u0627\u0631 "
        "\u0646\u0634\u06cc\u0645\u0646 \u0645\u0646\u0627\u0633\u0628 \u0627\u0633\u062a"
    )

    ok = (
        result["query_type"] == QUERY_POSITIVE_RELATION
        and result["verdict"] == VERDICT_ACCEPTABLE
        and result["relation_type"] == REL_NORMAL
    )

    return _check(
        "10-6 B positive adjacency reasoning works (Persian)",
        ok,
        result,
    )


def test_query_negative_relationship():

    result = space_query.analyze(
        "\u0648\u0631\u0648\u062f\u06cc \u0645\u0633\u062a\u0642\u06cc\u0645 \u0628\u0647 "
        "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u0645\u0646\u0627\u0633\u0628 \u0646\u06cc\u0633\u062a"
    )

    ok = (
        result["query_type"] == QUERY_NEGATIVE_RELATION
        and result["verdict"] == VERDICT_CONFIRMED
        and result["relation_type"] == REL_AVOID
    )

    return _check(
        "10-6 C negative relationship reasoning works (Persian)",
        ok,
        result,
    )


def test_query_english():

    cases = [
        ("Bedroom is a private space", QUERY_CLASSIFICATION,
         VERDICT_CORRECT),
        ("Kitchen next to the living room is appropriate",
         QUERY_POSITIVE_RELATION, VERDICT_ACCEPTABLE),
        ("The entrance should not open directly to the bedroom",
         QUERY_NEGATIVE_RELATION, VERDICT_CONFIRMED),
    ]

    failures = []

    for text, query_type, verdict in cases:

        result = space_query.analyze(text)

        if (
            result["query_type"] != query_type
            or result["verdict"] != verdict
        ):

            failures.append(
                {"text": text, "query": result["query_type"],
                 "verdict": result["verdict"]}
            )

    return _check(
        "10-6 E English language works",
        not failures,
        failures,
    )


def test_query_is_deterministic_and_offline():

    text = (
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u06a9\u0646\u0627\u0631 "
        "\u0646\u0634\u06cc\u0645\u0646 \u0645\u0646\u0627\u0633\u0628 \u0627\u0633\u062a"
    )

    runs = [
        json.dumps(space_query.analyze(text), sort_keys=True,
                   ensure_ascii=False, default=str)
        for _ in range(3)
    ]

    result = space_query.analyze(text)

    ok = (
        len(set(runs)) == 1
        and result["llm_used"] is False
        and result["network_used"] is False
        and result["render_requested"] is False
    )

    return _check(
        "10-6 reasoning is deterministic, offline, render-free",
        ok,
        {"variants": len(set(runs))},
    )


# ==========================================================
# PART 4 — TEACHING COMPATIBILITY
# ==========================================================

def test_space_teaching_aspects():

    aspects = space_aspects("fa")

    ok = (
        len(SPACE_TEACHING_ASPECTS) == 5
        and len(aspects) == 5
        and all(a.get("label") for a in aspects)
    )

    return _check(
        "10-4 five space teaching aspects defined",
        ok,
        {"aspects": [a["label"] for a in aspects]},
    )


def test_space_aspects_only_for_spaces():

    space_topic = space_curriculum.resolve_space_topic(
        "\u0645\u06cc \u062e\u0648\u0627\u0647\u0645 \u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 "
        "\u0631\u0627 \u06cc\u0627\u062f \u0628\u062f\u0647\u0645",
        "fa",
    )

    aspects = space_curriculum.aspects_for_topic(space_topic, "fa")

    generic = space_curriculum.aspects_for_topic(None, "fa")

    ok = (
        space_topic is not None
        and space_topic["space_id"] == "OPEN_KITCHEN"
        and aspects is not None
        and len(aspects) == 5
        and generic is None
    )

    return _check(
        "10-4 space aspects are used only when the topic is a space",
        ok,
        {"topic": space_topic, "aspects": len(aspects or [])},
    )


def test_teaching_still_candidate_only():

    ok = (
        space_curriculum.report()["candidate_only"] is True
        and space_curriculum.report()["promotion_implemented"] is False
        and PROMOTION_IMPLEMENTED is False
    )

    return _check(
        "10-4 teaching stays candidate-only, no promotion",
        ok,
        None,
    )


# ==========================================================
# SAFETY / SCOPE
# ==========================================================

def test_read_only_and_no_writes():

    space_report = space_types.report()

    adjacency_report = adjacency_model.report()

    privacy_report = privacy_logic.report()

    ok = (
        space_report["writes_performed"] == 0
        and adjacency_report["writes_performed"] == 0
        and privacy_report["writes_performed"] == 0
        and knowledge_read_bridge.assert_read_only() is True
    )

    return _check(
        "10 read-only: the curriculum layer writes nothing",
        ok,
        None,
    )


def test_curriculum_scope_respected():

    """No adjacency matrix / RPLAN / layout generation / geometry.

    RELAXED TWICE (relax + add, never delete):

      * Phase 11 legitimately added the bubble-diagram / zone layer, so
        "bubble" left this list;
      * Phase 12 legitimately added the FLOOR PROGRAM layer, so
        "floor_program" leaves it too.

    Note the deliberate near-miss: "floorplan" (a floor PLAN) stays
    forbidden, "floor_program" (a semantic program) does not. Those are
    different artefacts and the boundary between them is exactly what
    this assertion now protects.

    The constraint that still matters -- no geometry, no layout
    generation, no RPLAN, no floor plan -- is asserted here, and the new
    layers' semantic-only guarantee is asserted by the added tests below.
    """

    forbidden = (
        "adjacency_matrix", "rplan", "layout_generation",
        "floorplan", "floor_plan", "geometry", "cad", "bim", "ifc",
        "render",
    )

    curriculum_dir = os.path.join(ROOT, "core", "curriculum")

    hits = [
        name for name in os.listdir(curriculum_dir)
        if name.endswith(".py")
        and any(token in name.lower() for token in forbidden)
    ]

    return _check(
        "10 no layout / RPLAN / geometry layer exists",
        not hits,
        {"hits": hits},
    )


def test_bubble_layer_stays_semantic():

    """Phase 11's new layer is SEMANTIC ONLY.

    This is the added half of the relax + add pair: the bubble-diagram
    modules may exist, but they must contain no geometry, no coordinates
    and must not request a render.
    """

    from core.curriculum.bubble_diagram_v1 import (
        bubble_diagram_builder,
    )

    from core.curriculum.zone_model_v1 import zone_model

    report = bubble_diagram_builder.report()

    zone_report = zone_model.report()

    ok = (
        report["contains_geometry"] is False
        and report["contains_coordinates"] is False
        and zone_report["contains_geometry"] is False
        and zone_report["contains_coordinates"] is False
    )

    diagram = bubble_diagram_builder.build(
        "\u062e\u0627\u0646\u0647 \u06f3 \u062e\u0648\u0627\u0628\u0647",
        language="fa",
    )

    ok = ok and (
        diagram["contains_geometry"] is False
        and diagram["contains_coordinates"] is False
        and diagram["render_requested"] is False
        and diagram["comfy_invoked"] is False
        and diagram["semantic_only"] is True
    )

    return _check(
        "10 bubble layer is semantic only (no geometry, no render)",
        ok,
        {
            "geometry": diagram["contains_geometry"],
            "render": diagram["render_requested"],
        },
    )


def test_program_layer_stays_semantic():

    """The added half of the Phase 12 relax + add pair.

    The floor-program layer may exist, but it must be SEMANTIC ONLY:
    no geometry, no coordinates, no walls, no doors, no render.
    """

    from core.curriculum.floor_program_v1 import (
        floor_program_reasoning,
    )

    report = floor_program_reasoning.report()

    result = floor_program_reasoning.reason(
        "\u062e\u0627\u0646\u0647 \u06f3 \u062e\u0648\u0627\u0628\u0647",
        "fa",
    )

    program = result["floor_program"]

    ok = (
        report["contains_geometry"] is False
        and report["contains_coordinates"] is False
        and result["semantic_only"] is True
        and result["contains_geometry"] is False
        and result["contains_coordinates"] is False
        and result["contains_walls"] is False
        and result["contains_openings"] is False
        and result["render_requested"] is False
        and result["comfy_invoked"] is False
        and program["contains_walls"] is False
        and program["contains_openings"] is False
    )

    return _check(
        "10 floor program layer is semantic only (no geometry, no render)",
        ok,
        {
            "geometry": result["contains_geometry"],
            "walls": result["contains_walls"],
            "render": result["render_requested"],
        },
    )


def test_candidate_statuses_untouched():

    ok = set(ALLOWED_STATUSES) == {
        "observed", "needs_confirmation", "rejected"
    }

    return _check(
        "10 candidate status vocabulary unchanged",
        ok,
        list(ALLOWED_STATUSES),
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
    print("  PHASE 10 — SPACE TYPES + ADJACENCY INTELLIGENCE")
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
