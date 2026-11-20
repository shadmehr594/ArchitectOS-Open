# ==========================================================
# PHASE 11 — SPATIAL DIAGRAM INTELLIGENCE CONTRACT TESTS
#
# ISOLATED CONTRACT tests. They are NOT the acceptance proof: real
# acceptance runs against the live runtime path
# (tools/run_spatial_diagram_11_acceptance.py).
#
# Scope under test:
#   SPACE + RELATIONSHIP -> ZONE MODEL -> BUBBLE DIAGRAM
#
# Deliberately NOT tested here because the phase forbids them:
#   geometry, coordinates, walls, openings, CAD, BIM, IFC, renders.
#
# Run either way:
#   .venv/Scripts/python.exe -m pytest tests/test_spatial_diagram_11.py
#   .venv/Scripts/python.exe tests/test_spatial_diagram_11.py
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
    tempfile.gettempdir(), "architectos_phase11_contract"
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
    category_display,
)

from core.curriculum.adjacency_model_v1 import (
    adjacency_model,
    ALL_RELATION_TYPES,
    REL_STRONG,
    REL_NORMAL,
    REL_WEAK,
    REL_AVOID,
    REL_FORBIDDEN,
    relation_display,
)

from core.curriculum.privacy_logic_v1 import privacy_logic

from core.curriculum.space_query_v1 import (
    space_query,
    QUERY_POSITIVE_RELATION,
    QUERY_NEGATIVE_RELATION,
    VERDICT_ACCEPTABLE,
    VERDICT_CONFIRMED,
    VERDICT_NO_EVIDENCE,
)

from core.curriculum.zone_model_v1 import (
    zone_model,
    ALL_ZONES,
    ZONE_BY_CATEGORY,
    ZONE_PUBLIC,
    ZONE_SEMI_PUBLIC,
    ZONE_PRIVATE,
    ZONE_SERVICE,
    ZONE_CIRCULATION,
    ZONE_EXTERNAL,
    zone_display,
)

from core.curriculum.site_intent_v1 import (
    site_intent,
    EDGE_ACCESS,
    EDGE_OPEN,
    DIRECTIONS,
)

from core.curriculum.spatial_case_reasoning_v1 import (
    spatial_case_reasoning,
    QUESTION_WHY_ADJACENT,
    QUESTION_WHY_NOT_ADJACENT,
    QUESTION_WHY_CATEGORY,
    CONCLUSION_SUPPORTED,
    CONCLUSION_NOT_SUPPORTED,
    CONCLUSION_INSUFFICIENT,
)

from core.curriculum.diagram_curriculum_v1 import (
    diagram_curriculum,
    DIAGRAM_TEACHING_ASPECTS,
    diagram_aspects,
)

from core.curriculum.bubble_diagram_v1 import (
    bubble_diagram_builder,
    CONTRACT as BUBBLE_CONTRACT,
    VERSION as BUBBLE_VERSION,
    SHORT_RELATION,
    DIAGRAM_TYPE,
)

from core.conversation.knowledge_read_bridge_v1 import (
    knowledge_read_bridge,
)

from core.conversation.knowledge_promotion_bridge_v1 import (
    PROMOTION_IMPLEMENTED,
)

from core.conversation.teaching_candidate_v1 import (
    ALLOWED_STATUSES,
    PERMANENT_LEARNING_IMPLEMENTED,
)


_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))

    return bool(passed)


# ==========================================================
# PART 3 — ZONE MODEL
# ==========================================================

def test_six_zones_defined():

    report = zone_model.report()

    ok = (
        report["zone_count"] == 6
        and set(report["zones"]) == set(ALL_ZONES)
        and report["zone_source"] == "derived_from_phase10_category"
        and report["read_only"] is True
        and report["writes_performed"] == 0
    )

    return _check(
        "11 zone model defines the six semantic zones",
        ok,
        report["zones"],
    )


def test_zone_is_one_to_one_from_phase10_category():

    """Phase 10 stays the single source of truth for what a space IS."""

    ok = (
        len(ZONE_BY_CATEGORY) == 6
        and set(ZONE_BY_CATEGORY.keys()) == set(ALL_CATEGORIES)
        and len(set(ZONE_BY_CATEGORY.values())) == 6
    )

    # and the mapping is really what zone_of() uses
    for space_id in space_types.spaces():

        record = space_types.space(space_id)

        expected = ZONE_BY_CATEGORY.get(record.get("category"))

        if zone_model.zone_of(space_id) != expected:

            ok = False

            break

    return _check(
        "11 zone is derived 1:1 from the Phase 10 category",
        ok,
        ZONE_BY_CATEGORY,
    )


def test_every_space_resolves_to_a_zone():

    unresolved = []

    for space_id in space_types.spaces():

        if not zone_model.zone_of(space_id):

            unresolved.append(space_id)

    return _check(
        "11 every known space resolves to a zone",
        not unresolved,
        {"unresolved": unresolved[:8]},
    )


def test_zone_containment_has_no_geometry():

    report = zone_model.report()

    ok = (
        report["contains_geometry"] is False
        and report["contains_coordinates"] is False
    )

    return _check(
        "11 zones are semantic groupings, not shapes",
        ok,
        None,
    )


def test_zone_reasoning_places_spaces_correctly():

    """The six zones must reason the way the brief describes them."""

    expected = {
        "UNIT_ENTRY": ZONE_PUBLIC,
        "LIVING_RECEPTION": ZONE_PUBLIC,
        "OPEN_KITCHEN": ZONE_SEMI_PUBLIC,
        "BEDROOM_DOUBLE": ZONE_PRIVATE,
        "MASTER_BEDROOM_SLEEPING": ZONE_PRIVATE,
        "FAMILY_BATHROOM": ZONE_SERVICE,
        "STAIR": ZONE_CIRCULATION,
    }

    wrong = {
        space_id: zone_model.zone_of(space_id)
        for space_id, zone in expected.items()
        if zone_model.zone_of(space_id) != zone
    }

    return _check(
        "11 zone reasoning places entry/public/private/service/"
        "circulation correctly",
        not wrong,
        wrong,
    )


def test_zone_behaviour_is_language_aware():

    public = zone_model.behaviour(ZONE_PUBLIC, "fa")

    private = zone_model.behaviour(ZONE_PRIVATE, "en")

    ok = (
        public["access_affinity"] == 1
        and public["separation"] is False
        and bool(public["reason"])
        and any("\u0600" <= ch <= "\u06ff" for ch in public["reason"])
        and private["access_affinity"] == -1
        and private["separation"] is True
        and zone_display(ZONE_PRIVATE, "fa") != zone_display(
            ZONE_PRIVATE, "en"
        )
    )

    return _check(
        "11 zone behaviour + labels work in Persian and English",
        ok,
        {"fa": public["reason"][:40], "en": private["reason"][:40]},
    )


# ==========================================================
# PART 2 — ADJACENCY MATRIX
# ==========================================================

def test_adjacency_is_graded_with_reason_and_provenance():

    report = adjacency_model.report()

    relations = adjacency_model.relations()

    missing = [
        r["relation_id"] for r in relations
        if not r.get("reason") or not r.get("provenance")
        or r.get("relation_type") not in ALL_RELATION_TYPES
    ]

    ok = (
        report["boolean_relations"] is False
        and set(report["by_relation_type"]) == set(ALL_RELATION_TYPES)
        and report["relation_count"] >= 100
        and not missing
    )

    return _check(
        "11 adjacency matrix is graded, with reason + provenance",
        ok,
        {"missing": missing[:5],
         "by_type": report["by_relation_type"]},
    )


def test_adjacency_grades_are_all_reachable():

    """STRONG / NORMAL / WEAK / AVOID / FORBIDDEN must all be real."""

    seen = set()

    for relation in adjacency_model.relations():

        seen.add(relation["relation_type"])

    return _check(
        "11 all five grades are represented in the matrix",
        seen == set(ALL_RELATION_TYPES),
        {"seen": sorted(seen)},
    )


def test_adjacency_kitchen_dining_is_strong():

    relation = adjacency_model.relation("OPEN_KITCHEN", "DINING")

    return _check(
        "11 kitchen <-> dining is STRONG (brief example)",
        bool(relation) and relation["relation_type"] == REL_STRONG,
        relation,
    )


def test_adjacency_bedroom_living_is_weak():

    relation = adjacency_model.relation(
        "BEDROOM_DOUBLE", "LIVING_RECEPTION"
    )

    return _check(
        "11 bedroom <-> living is WEAK (brief example)",
        bool(relation) and relation["relation_type"] == REL_WEAK,
        relation,
    )


def test_adjacency_bedroom_entrance_is_avoid():

    relation = adjacency_model.relation("BEDROOM_DOUBLE", "UNIT_ENTRY")

    return _check(
        "11 bedroom <-> entrance is AVOID (brief example)",
        bool(relation) and relation["relation_type"] == REL_AVOID,
        relation,
    )


def test_adjacency_bathroom_living_is_forbidden():

    relation = adjacency_model.relation(
        "FAMILY_BATHROOM", "LIVING_RECEPTION"
    )

    return _check(
        "11 bathroom <-> living is FORBIDDEN",
        bool(relation) and relation["relation_type"] == REL_FORBIDDEN,
        relation,
    )


def test_adjacency_symmetry():

    """A relation must read the same in both directions."""

    asymmetric = []

    for relation in adjacency_model.relations():

        reverse = adjacency_model.relation(
            relation["target_space"], relation["source_space"]
        )

        if not reverse or reverse["relation_type"] != relation["relation_type"]:

            asymmetric.append(relation["relation_id"])

    return _check(
        "11 adjacency relations are symmetric",
        not asymmetric,
        {"asymmetric": asymmetric[:5]},
    )


def test_bedroom_bathroom_nuance_is_architectural():

    """The brief's "Bedroom: Bathroom NORMAL" is a simplification.

    The corpus distinguishes a SHARED family bathroom (must come off the
    circulation, not off a bedroom) from an ENSUITE (belongs to the
    sleeping suite). Asserting that distinction proves the model reasons
    architecturally rather than pattern-matching the brief's example.
    """

    shared = adjacency_model.relation(
        "BEDROOM_DOUBLE", "FAMILY_BATHROOM"
    )

    ensuite = adjacency_model.relation(
        "MASTER_BEDROOM_SLEEPING", "ENSUITE"
    )

    ok = (
        bool(shared) and shared["relation_type"] == REL_AVOID
        and bool(ensuite) and ensuite["relation_type"] == REL_STRONG
    )

    return _check(
        "11 shared bathroom vs ensuite are graded differently",
        ok,
        {
            "shared": (shared or {}).get("relation_type"),
            "ensuite": (ensuite or {}).get("relation_type"),
        },
    )


# ==========================================================
# PART 1 — BUBBLE DIAGRAM CONTRACT
# ==========================================================

BRIEF_BUBBLE_FIELDS = (
    "space_id",
    "space_type",
    "zone",
    "privacy",
    "required_connections",
    "forbidden_connections",
    "adjacency_weight",
    "reasoning",
    "provenance",
)


def _diagram():

    return bubble_diagram_builder.build(
        "\u062e\u0627\u0646\u0647 \u06f3 \u062e\u0648\u0627\u0628\u0647 "
        "\u0628\u0627 \u0646\u0634\u06cc\u0645\u0646\u060c "
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647\u060c "
        "\u0646\u0627\u0647\u0627\u0631\u062e\u0648\u0631\u06cc "
        "\u0648 \u062f\u0648 \u0633\u0631\u0648\u06cc\u0633",
        site_text="\u062e\u06cc\u0627\u0628\u0627\u0646 \u062c\u0646\u0648\u0628\u060c "
                  "\u062d\u06cc\u0627\u0637 \u062e\u0644\u0648\u062a \u0634\u0645\u0627\u0644",
        language="fa",
        project_id="contract_project",
    )


def test_bubble_contract_fields():

    diagram = _diagram()

    missing = []

    for bubble in diagram["bubbles"]:

        for field in BRIEF_BUBBLE_FIELDS:

            if field not in bubble:

                missing.append((bubble["bubble_id"], field))

    return _check(
        "11 every bubble carries the full brief contract",
        not missing,
        {"missing": missing[:8],
         "bubble_count": len(diagram["bubbles"])},
    )


def test_bubble_contract_is_populated():

    """Not just present -- actually filled with real reasoning.

    `reasoning` may legitimately be EMPTY for a bubble that has nothing
    to warn about (no AVOID/FORBIDDEN relation, no controlled access);
    an empty list is an honest answer, so the contract is that it is a
    list and that it is genuinely used somewhere in the diagram.
    """

    diagram = _diagram()

    empty = []

    reasoned = 0

    for bubble in diagram["bubbles"]:

        if bubble.get("reasoning"):

            reasoned += 1

        if (
            not bubble.get("space_id")
            or not bubble.get("space_type")
            or not bubble.get("zone")
            or bubble.get("privacy") is None
            or bubble.get("adjacency_weight") is None
            or not isinstance(bubble.get("provenance"), dict)
            or not isinstance(bubble.get("reasoning"), list)
        ):

            empty.append(bubble["bubble_id"])

    return _check(
        "11 bubble fields are populated, not placeholders",
        not empty and reasoned > 0,
        {"empty": empty[:8], "bubbles_with_reasoning": reasoned},
    )


def test_bubble_id_is_stable_and_unique():

    first = _diagram()

    second = _diagram()

    ids_first = [b["bubble_id"] for b in first["bubbles"]]

    ids_second = [b["bubble_id"] for b in second["bubbles"]]

    return _check(
        "11 bubble ids are unique and deterministic across runs",
        len(ids_first) == len(set(ids_first))
        and ids_first == ids_second,
        {"ids": ids_first},
    )


def test_required_and_forbidden_connections_partition():

    """required = STRONG/NORMAL, forbidden = AVOID/FORBIDDEN, and the
    partition must agree with the underlying graded `connections`."""

    diagram = _diagram()

    problems = []

    for bubble in diagram["bubbles"]:

        expected_required = {
            c["to_bubble"] for c in bubble["connections"]
            if c["relation_type"] in (REL_STRONG, REL_NORMAL)
        }

        expected_forbidden = {
            c["to_bubble"] for c in bubble["connections"]
            if c["relation_type"] in (REL_AVOID, REL_FORBIDDEN)
        }

        got_required = {
            c["to_bubble"] for c in bubble["required_connections"]
        }

        got_forbidden = {
            c["to_bubble"] for c in bubble["forbidden_connections"]
        }

        if got_required != expected_required:

            problems.append(("required", bubble["bubble_id"]))

        if got_forbidden != expected_forbidden:

            problems.append(("forbidden", bubble["bubble_id"]))

    return _check(
        "11 required/forbidden connections partition the graded relations",
        not problems,
        {"problems": problems[:6]},
    )


def test_no_relation_is_never_invented():

    """Every connection must exist in the adjacency model with the same
    grade -- the diagram may not invent a relationship."""

    diagram = _diagram()

    invented = []

    for bubble in diagram["bubbles"]:

        for connection in bubble["connections"]:

            relation = adjacency_model.relation(
                bubble["space_id"], connection["to_space"]
            )

            if (
                not relation
                or relation["relation_type"] != connection["relation_type"]
            ):

                invented.append(
                    (bubble["space_id"], connection["to_space"])
                )

    return _check(
        "11 the diagram invents no relationship",
        not invented,
        {"invented": invented[:5]},
    )


def test_bubble_diagram_output_shape():

    diagram = _diagram()

    ok = (
        diagram["contract"] == BUBBLE_CONTRACT
        and diagram["version"] == BUBBLE_VERSION
        and diagram["diagram_type"] == DIAGRAM_TYPE
        and diagram["language"] == "fa"
        and len(diagram["zones"]) >= 4
        and len(diagram["bubbles"]) >= 8
        and len(diagram["relations"]) > 0
        and bool(diagram["reasoning"])
        and diagram["deterministic"] is True
    )

    return _check(
        "11 bubble diagram output has the expected shape",
        ok,
        {
            "zones": len(diagram["zones"]),
            "bubbles": len(diagram["bubbles"]),
            "relations": len(diagram["relations"]),
        },
    )


def test_relation_types_are_the_five_grades():

    diagram = _diagram()

    seen = {r["type"] for r in diagram["relations"]}

    allowed = set(SHORT_RELATION.values())

    return _check(
        "11 relation types use the five short grades",
        seen and seen <= allowed,
        {"seen": sorted(seen)},
    )


def test_diagram_is_semantic_only():

    diagram = _diagram()

    ok = (
        diagram["semantic_only"] is True
        and diagram["contains_geometry"] is False
        and diagram["contains_coordinates"] is False
        and diagram["contains_walls"] is False
        and diagram["contains_openings"] is False
        and diagram["render_requested"] is False
        and diagram["comfy_invoked"] is False
        and diagram["llm_used"] is False
        and diagram["network_used"] is False
    )

    return _check(
        "11 the diagram is semantic only (no geometry/render/LLM/network)",
        ok,
        {
            "geometry": diagram["contains_geometry"],
            "render": diagram["render_requested"],
        },
    )


def test_no_coordinates_anywhere_in_the_payload():

    """Belt and braces: scan the serialized payload for coordinate-like
    keys, so a future edit cannot smuggle geometry in."""

    payload = json.dumps(_diagram(), ensure_ascii=False).lower()

    forbidden = (
        "polygon", "vertex", "vertices", "bounding_box", "boundingbox",
        "centroid", "x_mm", "y_mm", "wall_segment", "door_swing",
    )

    hits = [token for token in forbidden if token in payload]

    return _check(
        "11 the serialized diagram contains no coordinate vocabulary",
        not hits,
        {"hits": hits},
    )


# ==========================================================
# PART 4 — PROGRAM -> SPATIAL GRAPH (REASONING ENGINE)
# ==========================================================

def test_bedroom_count_requires_adjacency():

    """Regression: a bare number word elsewhere in the sentence must not
    be read as a bedroom count. "دو سرویس" means two bathrooms."""

    cases = [
        ("\u062e\u0627\u0646\u0647 \u06f3 \u062e\u0648\u0627\u0628\u0647 "
         "\u0628\u0627 \u062f\u0648 \u0633\u0631\u0648\u06cc\u0633", 3),
        ("\u062e\u0627\u0646\u0647 \u062f\u0648 \u062e\u0648\u0627\u0628\u0647", 2),
        ("\u0622\u067e\u0627\u0631\u062a\u0645\u0627\u0646 4 \u062e\u0648\u0627\u0628\u0647", 4),
        ("a house with 3 bedrooms", 3),
        ("a house with two bedrooms", 2),
        ("\u062e\u0627\u0646\u0647 \u0628\u0627 \u0646\u0634\u06cc\u0645\u0646 "
         "\u0648 \u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647", None),
        ("\u0648\u06cc\u0644\u0627 \u06f5 \u062e\u0648\u0627\u0628\u0647 "
         "\u0628\u0627 \u062f\u0648 \u067e\u0627\u0631\u06a9\u06cc\u0646\u06af", 5),
    ]

    wrong = []

    for text, expected in cases:

        got = bubble_diagram_builder.parse_program(text)["bedrooms"]

        if got != expected:

            wrong.append({"text": text, "got": got, "want": expected})

    return _check(
        "11 bedroom count needs a number ADJACENT to a bedroom word",
        not wrong,
        wrong,
    )


def test_program_becomes_a_spatial_graph():

    """The brief's example program must produce the brief's structure:
    entry -> public zone (living/kitchen/dining) -> privacy transition
    -> private zone (bedroom/master bedroom)."""

    diagram = _diagram()

    by_space = {}

    for bubble in diagram["bubbles"]:

        by_space.setdefault(bubble["space_id"], []).append(bubble)

    zones = {z["name"]: z["spaces"] for z in diagram["zones"]}

    public = set(zones.get(ZONE_PUBLIC, []))

    private = set(zones.get(ZONE_PRIVATE, []))

    ok = (
        "UNIT_ENTRY" in by_space
        and by_space["UNIT_ENTRY"][0]["zone"] == ZONE_PUBLIC
        and "LIVING_RECEPTION" in public
        and "OPEN_KITCHEN" in zones.get(ZONE_SEMI_PUBLIC, [])
        and "DINING" in zones.get(ZONE_SEMI_PUBLIC, [])
        + zones.get(ZONE_PUBLIC, [])
        and "MASTER_BEDROOM_SLEEPING" in private
        and "BEDROOM_DOUBLE" in private
        and len(by_space.get("BEDROOM_DOUBLE", [])) == 2
    )

    return _check(
        "11 program -> entry -> public -> transition -> private graph",
        ok,
        {z: len(v) for z, v in zones.items()},
    )


def test_privacy_transition_is_reasoned():

    """There must be a real boundary between the public field and the
    private field, i.e. a circulation space mediating them."""

    diagram = _diagram()

    corridor = [
        b for b in diagram["bubbles"]
        if b["zone"] == ZONE_CIRCULATION
    ]

    private = [
        b for b in diagram["bubbles"] if b["zone"] == ZONE_PRIVATE
    ]

    ok = bool(corridor) and bool(private)

    if ok:

        # each private bubble must be connected to circulation or to
        # something that is, i.e. not floating
        for bubble in private:

            if not bubble["connections"]:

                ok = False

                break

    return _check(
        "11 a circulation zone mediates the privacy transition",
        ok,
        {
            "circulation": [b["bubble_id"] for b in corridor],
            "private": [b["bubble_id"] for b in private],
        },
    )


def test_separation_rules_surface_forbidden_pairs():

    diagram = _diagram()

    forbidden_pairs = {
        tuple(sorted([r["from"], r["to"]]))
        for r in diagram["separation_rules"]
    }

    from_bubbles = {
        tuple(sorted([c["to_bubble"], b["bubble_id"]]))
        for b in diagram["bubbles"]
        for c in b["forbidden_connections"]
    }

    return _check(
        "11 separation rules are deduplicated and complete",
        forbidden_pairs == from_bubbles and len(forbidden_pairs) > 0,
        {"rules": len(forbidden_pairs)},
    )


# ==========================================================
# PART 4 (SITE) — SEMANTIC SITE INTENT
# ==========================================================

def test_site_intent_assigns_edges():

    result = site_intent.parse(
        "\u062e\u06cc\u0627\u0628\u0627\u0646 \u062c\u0646\u0648\u0628\u060c "
        "\u062d\u06cc\u0627\u0637 \u062e\u0644\u0648\u062a \u0634\u0645\u0627\u0644"
    )

    ok = (
        result["access_edge"] == "south"
        and result["open_edge"] == "north"
        and "north" in result["protected_edges"]
        and result["contains_coordinates"] is False
        and result["contains_geometry"] is False
        and result["semantic_only"] is True
    )

    return _check(
        "11 site intent maps street/rear-yard to semantic edges",
        ok,
        {"access": result["access_edge"], "open": result["open_edge"]},
    )


def test_site_dimensions_are_semantic():

    result = site_intent.parse(
        "\u0632\u0645\u06cc\u0646 \u06f1\u06f0\u00d7\u06f2\u06f0 "
        "\u062e\u06cc\u0627\u0628\u0627\u0646 \u062c\u0646\u0648\u0628"
    )

    dimensions = result["site"]["dimensions"]

    ok = (
        bool(dimensions)
        and dimensions["width"] == 10.0
        and dimensions["depth"] == 20.0
        and result["site"]["has_coordinates"] is False
    )

    return _check(
        "11 site dimensions are semantic (no coordinates)",
        ok,
        dimensions,
    )


def test_site_intent_produces_zone_directions():

    result = site_intent.parse(
        "\u062e\u06cc\u0627\u0628\u0627\u0646 \u062c\u0646\u0648\u0628\u060c "
        "\u062d\u06cc\u0627\u0637 \u062e\u0644\u0648\u062a \u0634\u0645\u0627\u0644",
        "fa",
    )

    intents = {i["zone"]: i["toward"] for i in result["intents"]}

    ok = (
        intents.get("PUBLIC_ZONE") == "south"
        and intents.get("PRIVATE_ZONE") == "north"
        and intents.get("EXTERNAL_ZONE") == "north"
        and all(bool(i["reason_fa"]) for i in result["intents"])
    )

    return _check(
        "11 site intent derives zone directions with Persian reasons",
        ok,
        intents,
    )


def test_diagram_position_intent_uses_the_site():

    diagram = _diagram()

    entry = [
        b for b in diagram["bubbles"] if b["space_id"] == "UNIT_ENTRY"
    ][0]

    private = [
        b for b in diagram["bubbles"]
        if b["space_id"] == "BEDROOM_DOUBLE"
    ][0]

    ok = (
        entry["position_intent"]["determined"] is True
        and entry["position_intent"]["edge"] == "south"
        and private["position_intent"]["edge"] == "north"
    )

    return _check(
        "11 position intent places public on access and private on "
        "protected edge",
        ok,
        {
            "entry": entry["position_intent"]["edge"],
            "bedroom": private["position_intent"]["edge"],
        },
    )


# ==========================================================
# PART 6 — CASE REASONING (EVIDENCE, NOT OPINION)
# ==========================================================

def test_case_reasoning_persian():

    result = spatial_case_reasoning.analyze(
        "\u0686\u0631\u0627 \u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 "
        "\u06a9\u0646\u0627\u0631 \u0648\u0631\u0648\u062f\u06cc \u0646\u06cc\u0633\u062a\u061f"
    )

    ok = (
        result["question_type"] == QUESTION_WHY_NOT_ADJACENT
        and result["conclusion"] == CONCLUSION_SUPPORTED
        and bool(result["evidence"])
        and bool(result["answer"])
        and result["llm_used"] is False
    )

    return _check(
        "11 why-not-adjacent reasoning works in Persian",
        ok,
        {"conclusion": result["conclusion"],
         "answer": result["answer"][:90]},
    )


def test_case_reasoning_english():

    result = spatial_case_reasoning.analyze(
        "Why is the kitchen next to the living room?"
    )

    ok = (
        result["question_type"] == QUESTION_WHY_ADJACENT
        and result["conclusion"] in (
            CONCLUSION_SUPPORTED, CONCLUSION_NOT_SUPPORTED
        )
        and bool(result["answer"])
    )

    return _check(
        "11 why-adjacent reasoning works in English",
        ok,
        {"conclusion": result["conclusion"]},
    )


def test_case_reasoning_refuses_to_invent():

    """A question with no recognised space must return insufficient
    evidence rather than a fabricated explanation."""

    result = spatial_case_reasoning.analyze(
        "\u0686\u0631\u0627 \u0627\u06cc\u0646 \u0637\u0648\u0631 \u0627\u0633\u062a\u061f"
    )

    return _check(
        "11 case reasoning returns insufficient_evidence, not a guess",
        result["conclusion"] == CONCLUSION_INSUFFICIENT
        and bool(result["answer"]),
        {"conclusion": result["conclusion"]},
    )


def test_case_reasoning_evidence_is_traceable():

    result = spatial_case_reasoning.analyze(
        "\u0686\u0631\u0627 \u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 "
        "\u06a9\u0646\u0627\u0631 \u0646\u0634\u06cc\u0645\u0646 \u0645\u0646\u0627\u0633\u0628 \u0627\u0633\u062a\u061f"
    )

    evidence = result.get("evidence") or {}

    relation = evidence.get("relation") or {}

    ok = (
        bool(relation.get("type"))
        and bool(relation.get("reason"))
        and relation.get("provenance") is not None
        and (evidence.get("source") or {}).get("zone") is not None
        and (evidence.get("target") or {}).get("zone") is not None
    )

    return _check(
        "11 case reasoning cites relation + zone + provenance",
        ok,
        {"relation": relation.get("type")},
    )


def test_no_evidence_is_not_reported_as_a_negative_verdict():

    """Regression: a pair with NO recorded relation must not be answered
    as "not acceptable", and the literal string "None" must never leak
    into the answer text."""

    result = space_query.analyze(
        "\u0631\u0627\u0647 \u067e\u0644\u0647 \u0628\u0627\u06cc\u062f "
        "\u0646\u0632\u062f\u06cc\u06a9 \u0648\u0631\u0648\u062f\u06cc \u0628\u0627\u0634\u062f"
    )

    ok = (
        result["query_type"] == QUERY_POSITIVE_RELATION
        and result["verdict"] == VERDICT_NO_EVIDENCE
        and result["has_relation"] is False
        and result["relation_label"] is None
        and "None" not in str(result.get("answer"))
    )

    return _check(
        "11 missing relation is NO_EVIDENCE, never a false negative",
        ok,
        {"verdict": result["verdict"],
         "answer": str(result.get("answer"))[:90]},
    )


def test_known_relations_still_verdict_normally():

    """The added NO_EVIDENCE verdict must not have replaced the real
    verdicts for pairs the model does know."""

    positive = space_query.analyze(
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u06a9\u0646\u0627\u0631 "
        "\u0646\u0634\u06cc\u0645\u0646 \u0645\u0646\u0627\u0633\u0628 \u0627\u0633\u062a"
    )

    negative = space_query.analyze(
        "\u0648\u0631\u0648\u062f\u06cc \u0645\u0633\u062a\u0642\u06cc\u0645 \u0628\u0647 "
        "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u0645\u0646\u0627\u0633\u0628 \u0646\u06cc\u0633\u062a"
    )

    ok = (
        positive["verdict"] == VERDICT_ACCEPTABLE
        and positive["has_relation"] is True
        and negative["query_type"] == QUERY_NEGATIVE_RELATION
        and negative["verdict"] == VERDICT_CONFIRMED
    )

    return _check(
        "11 known relations keep their original verdicts",
        ok,
        {"positive": positive["verdict"], "negative": negative["verdict"]},
    )


# ==========================================================
# PART 5 — HUMAN TEACHING COMPATIBILITY
# ==========================================================

def test_diagram_teaching_aspects():

    aspects = diagram_aspects("fa")

    english = diagram_aspects("en")

    ok = (
        len(DIAGRAM_TEACHING_ASPECTS) == 5
        and len(aspects) == 5
        and len(english) == 5
        and all(a["label"] != b["label"] for a, b in zip(aspects, english))
        and diagram_curriculum.report()["candidate_only"] is True
        and diagram_curriculum.report()["promotion_implemented"] is False
    )

    return _check(
        "11 five diagram teaching aspects in Persian and English",
        ok,
        [a["key"] for a in aspects],
    )


def test_diagram_topic_resolution():

    persian = diagram_curriculum.resolve_diagram_topic(
        "\u0645\u06cc \u062e\u0648\u0627\u0647\u0645 \u062f\u06cc\u0627\u06af\u0631\u0627\u0645 "
        "\u0641\u0636\u0627\u06cc\u06cc \u0631\u0627 \u06cc\u0627\u062f \u0628\u062f\u0647\u0645",
        "fa",
    )

    english = diagram_curriculum.resolve_diagram_topic(
        "I want to teach you about the bubble diagram", "en"
    )

    none_for_space = diagram_curriculum.resolve_diagram_topic(
        "\u0645\u06cc \u062e\u0648\u0627\u0647\u0645 \u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 "
        "\u0631\u0627 \u06cc\u0627\u062f \u0628\u062f\u0647\u0645",
        "fa",
    )

    ok = (
        bool(persian) and persian["topic"] == "spatial_diagram"
        and len(persian["aspects"]) == 5
        and bool(english) and english["language"] == "en"
        and none_for_space is None
    )

    return _check(
        "11 diagram topic resolves (and does not swallow space topics)",
        ok,
        {"persian": bool(persian), "english": bool(english),
         "space_is_none": none_for_space is None},
    )


# ==========================================================
# PART 6 — READS THE EXISTING LIBRARIES (NO DUPLICATION)
# ==========================================================

def test_reuses_the_existing_corpus_through_the_phase09_bridge():

    read_report = knowledge_read_bridge.read_report()

    space_report = space_types.report()

    ok = (
        read_report["read_only"] is True
        and read_report["writes_performed"] == 0
        and (space_report["by_origin"] or {}).get("SPACE_SPECS", 0) >= 40
        and (space_report["by_origin"] or {}).get("ONTOLOGY", 0) >= 40
        and space_report["space_count"] >= 80
    )

    return _check(
        "11 reuses the existing corpus through the Phase 09 read bridge",
        ok,
        space_report["by_origin"],
    )


def test_diagram_layer_is_a_consumer_not_a_second_knowledge_base():

    """The Phase 11 modules must contain no new space/relation tables."""

    diagram = _diagram()

    provenance = diagram["provenance"]

    ok = (
        provenance["spaces"] == "core/curriculum/space_types_v1.py"
        and provenance["zones"] == "core/curriculum/zone_model_v1.py"
        and provenance["relations"]
        == "core/curriculum/adjacency_model_v1.py"
        and provenance["privacy"] == "core/curriculum/privacy_logic_v1.py"
        and provenance["program"] in (
            "BUILDING_PROGRAM_KNOWLEDGE", "CURRICULUM_FALLBACK"
        )
    )

    return _check(
        "11 the diagram layer consumes the corpus, it does not copy it",
        ok,
        provenance,
    )


# ==========================================================
# SCOPE — NO PERMANENT LEARNING, NO RENDER, NO GEOMETRY, NO BIM/IFC
# ==========================================================

def test_no_permanent_learning_path_exists():

    ok = (
        PROMOTION_IMPLEMENTED is False
        and PERMANENT_LEARNING_IMPLEMENTED is False
        and set(ALLOWED_STATUSES) == {
            "observed", "needs_confirmation", "rejected"
        }
        and diagram_curriculum.report()["promotion_implemented"] is False
    )

    return _check(
        "11 no promotion / permanent-learning path exists",
        ok,
        list(ALLOWED_STATUSES),
    )


def test_phase11_modules_contain_no_geometry_vocabulary():

    """Static scan of the Phase 11 modules' IMPORT graph for geometry /
    render / BIM / CAD libraries.

    Parsed with `ast`, not a text grep: these modules legitimately *talk*
    about geometry in their comments ("no polygons", "no coordinates")
    and expose a `comfy_invoked: False` flag, so a naive substring scan
    would produce false positives.
    """

    import ast

    module_dir = os.path.join(ROOT, "core", "curriculum")

    phase11 = (
        "zone_model_v1.py",
        "bubble_diagram_v1.py",
        "site_intent_v1.py",
        "spatial_case_reasoning_v1.py",
        "diagram_curriculum_v1.py",
    )

    forbidden = (
        "ezdxf", "ifcopenshell", "shapely", "trimesh", "pyautocad",
        "comfy", "diffusers", "torch", "numpy", "matplotlib",
        "requests", "urllib", "httpx", "flask",
    )

    hits = []

    for name in phase11:

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

                root = module.split(".")[0].lower()

                if root in forbidden:

                    hits.append({"module": name, "import": module})

    return _check(
        "11 Phase 11 modules import no geometry / render / BIM / network "
        "library",
        not hits,
        {"hits": hits[:6]},
    )


def test_all_reports_declare_read_only():

    reports = {
        "zones": zone_model.report(),
        "site": site_intent.report(),
        "case": spatial_case_reasoning.report(),
        "diagram": bubble_diagram_builder.report(),
    }

    bad = {
        name: report.get("writes_performed")
        for name, report in reports.items()
        if report.get("read_only") is not True
        or report.get("writes_performed") != 0
    }

    return _check(
        "11 every Phase 11 surface reports read-only / zero writes",
        not bad,
        bad,
    )


def test_project_isolation_of_the_diagram():

    """A diagram built for one project must not carry another project's
    id, and the layer must hold no cross-project state."""

    first = bubble_diagram_builder.build(
        "\u062e\u0627\u0646\u0647 \u062f\u0648 \u062e\u0648\u0627\u0628\u0647",
        language="fa",
        project_id="project_aaa",
    )

    second = bubble_diagram_builder.build(
        "\u062e\u0627\u0646\u0647 \u062f\u0648 \u062e\u0648\u0627\u0628\u0647",
        language="fa",
        project_id="project_bbb",
    )

    ok = (
        first["project_id"] == "project_aaa"
        and second["project_id"] == "project_bbb"
        and first["bubbles"] == second["bubbles"]
    )

    return _check(
        "11 the diagram is project-scoped and stateless",
        ok,
        {"a": first["project_id"], "b": second["project_id"]},
    )


def test_english_and_persian_produce_equivalent_graphs():

    persian = bubble_diagram_builder.build(
        "\u062e\u0627\u0646\u0647 \u06f2 \u062e\u0648\u0627\u0628\u0647 "
        "\u0628\u0627 \u0646\u0634\u06cc\u0645\u0646\u060c "
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0648 "
        "\u0646\u0627\u0647\u0627\u0631\u062e\u0648\u0631\u06cc",
        language="fa",
    )

    english = bubble_diagram_builder.build(
        "A house with 2 bedrooms, a living room, a kitchen and a "
        "dining room",
        language="en",
    )

    ok = (
        [b["space_id"] for b in persian["bubbles"]]
        == [b["space_id"] for b in english["bubbles"]]
        and persian["language"] == "fa"
        and english["language"] == "en"
        and len(persian["relations"]) == len(english["relations"])
    )

    return _check(
        "11 Persian and English programs yield the same graph",
        ok,
        {
            "fa": [b["space_id"] for b in persian["bubbles"]][:6],
            "en": [b["space_id"] for b in english["bubbles"]][:6],
        },
    )


def test_bare_term_and_language_term_resolve_to_one_record():

    """Regression: the frozen ontology ALSO carries a flatter record under
    the literal id "bedroom". A literal-id lookup therefore returned the
    flat record for `term=bedroom` while `term=اتاق خواب` returned the
    richer curriculum record -- the same concept, two different answers,
    depending on the language the user typed.

    Both must resolve to ONE record, and the flat record must stay
    reachable by its own id (no knowledge is hidden).
    """

    english = space_types.find("bedroom")

    persian = space_types.find("\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628")

    flat = space_types.space("bedroom")

    rich = space_types.space("BEDROOM_DOUBLE")

    ok = (
        english == persian == "BEDROOM_DOUBLE"
        and space_types.find("BEDROOM_DOUBLE") == "BEDROOM_DOUBLE"
        and bool(flat)
        and flat is not rich
        and flat.get("origin") == "ONTOLOGY"
    )

    return _check(
        "11 a bare term and its Persian equivalent resolve to ONE record",
        ok,
        {"en": english, "fa": persian,
         "flat_origin": (flat or {}).get("origin")},
    )


def test_space_resolution_persian_and_english():

    from core.curriculum.space_query_v1 import scan_spaces

    persian = scan_spaces(
        "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u0648 "
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647"
    )

    english = scan_spaces("bedroom and kitchen")

    ok = (
        {s[0] for s in persian} == {s[0] for s in english}
        and len(persian) == 2
    )

    return _check(
        "11 space resolution agrees across Persian and English",
        ok,
        {"fa": [s[0] for s in persian], "en": [s[0] for s in english]},
    )


def test_category_and_relation_display_bilingual():

    ok = (
        category_display(CATEGORY_PRIVATE, "fa")
        != category_display(CATEGORY_PRIVATE, "en")
        and relation_display(REL_STRONG, "fa")
        != relation_display(REL_STRONG, "en")
        and category_display(CATEGORY_SERVICE, "en")
        and relation_display(REL_FORBIDDEN, "en")
    )

    return _check(
        "11 category + relation labels are bilingual",
        ok,
        {
            "category_fa": category_display(CATEGORY_PRIVATE, "fa"),
            "relation_fa": relation_display(REL_STRONG, "fa"),
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
    print("  PHASE 11 — SPATIAL DIAGRAM INTELLIGENCE")
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
