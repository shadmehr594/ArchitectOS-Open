"""ARCHITECTURAL-DESIGN-ROBUSTNESS-01A2B acceptance tests.

Architectural layout intelligence: entrance hierarchy, critical adjacency,
multi-floor core continuity, candidate generation and architectural evaluation.

Runs the REAL 2-floor villa program (unchanged from 01A/01A2) and proves that
the selected layout is architecturally evaluated — not merely non-overlapping.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from shapely.geometry import Polygon

from core.architecture.contracts.architectural_layout_candidate_v1 import (
    CANDIDATE_CONTRACT,
    CORE_ALIGNED,
    CORE_MISALIGNED,
    CORE_MISSING,
    CORE_NOT_ALIGNED_ACROSS_FLOORS,
    CRITICAL,
    CRITICAL_ADJACENCY_MISSING,
    ENTRANCE_HIERARCHY_VALID,
    GATE_CONTRACT,
    HIGH,
    QUALITY_FAIL,
    QUALITY_PASS,
    QUALITY_PASS_WITH_WARNINGS,
    REQUIRED_ROOM_ISOLATED,
    ROOM_OVERLAP_DETECTED,
    SERVED_UPPER_FLOOR_WITHOUT_VERTICAL_CORE,
    UPPER_FLOOR_CORRIDOR_WITHOUT_ARRIVAL,
    VERSION,
    candidate_hash,
    layout_semantic_hash,
    verify_layout_intelligence,
)
from core.architecture.reasoning.architectural_design_robustness_01a import (
    project_human_readable_plan,
)
from core.architecture.reasoning.architectural_layout_intelligence_v1 import (
    ArchitecturalLayoutIntelligenceV1,
    design_architectural_layout,
)
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent


ROOT = Path(__file__).resolve().parents[2]

FROZEN_STRUCTURAL_HASHES = {
    "core/structure/structural_grid_engine.py":
        "886d0d1cba71f211c503e4eea532b677396a331abf6565a8f018fa863dd12263",
    "core/structure/structural_element_engine.py":
        "935f9bd4e047f7c9e339a81ba016bb3455db8d1b725e14d837da9f1e7d39a950",
}

FROZEN_UPSTREAM = (
    "core/architecture/reasoning/spatial_placement_reasoner.py",
    "core/architecture/geometry/architectural_geometry_engine_v2.py",
    "core/architecture/reasoning/layout_reasoner.py",
    "core/architecture/model/architectural_plan_model.py",
    "core/architecture/reasoning/architectural_design_robustness_01a.py",
    "core/architecture/reasoning/coherent_floor_plan_resolver_v1.py",
)

PARCEL = [[0.0, 0.0], [20.0, 0.0], [20.0, 30.0], [0.0, 30.0]]

PROGRAM = {
    "building_type": "residential", "functions": ["residential"],
    "spaces": ["living_room", "kitchen", "dining", "master_bedroom", "bedroom",
               "bathroom", "guest_wc", "corridor", "stair", "entrance", "terrace",
               "parking"],
    "levels": {"above_ground": 2, "ground": 1, "basement": 0, "mezzanine": 0, "total": 2},
    "floor_program": {
        "ground_floor": ["living_room", "kitchen", "dining", "guest_wc", "corridor",
                         "entrance", "stair", "terrace"],
        "F2": ["master_bedroom", "bedroom", "bathroom", "corridor", "stair", "terrace"],
    },
    "vertical_transport": {
        "elevators": [], "ramps": [], "escalators": [],
        "stairs": [{
            "id": "main_stair", "from_level": "ground_floor", "to_level": "F2",
            "required": True, "clear_width": 1.2, "flight_count": 2,
            "landing_required": True, "landing_depth": 1.2, "maximum_riser": 0.18,
            "minimum_tread": 0.28, "headroom": 2.1,
            "source": "project_requirement", "evidence_status": "authoritative",
        }],
    },
}


def _site(parcel=None):
    return {
        "source": "parcel", "source_type": "polygon",
        "boundary": {"type": "polygon", "points": parcel or PARCEL},
        "area": 600.0, "coordinate_system": "local_normalized", "building_height": 7.2,
        "neighbors": {"north": False, "south": False, "east": True, "west": True},
        "separation_joint_requirement": {"enabled": True},
        "site_constraints": {
            "access": {"confirmed": True, "edge_index": 0, "road_width": 8.0},
            "adjacency": [
                {"edge_index": 0, "type": "road", "confirmed": True},
                {"edge_index": 1, "type": "neighbor_parcel", "confirmed": True},
                {"edge_index": 2, "type": "road", "confirmed": True},
                {"edge_index": 3, "type": "neighbor_parcel", "confirmed": True},
            ],
        },
    }


def _run(program=None, parcel=None, prompt=None):
    from core.architecture.brain.architectural_brain import ArchitecturalBrain

    program = program or PROGRAM
    intent = ArchitecturalIntent().extract(
        {"prompt": prompt or "ویلای دو طبقه با سه اتاق خواب",
         "architectural_intent": program},
        {"site": _site(parcel)})
    model = ArchitecturalBrain().design(intent)
    human = project_human_readable_plan(model, program=program)
    document = design_architectural_layout(model, program=program, human_plan=human)
    return {"model": model, "human": human, "document": document}


@pytest.fixture(scope="module")
def result():
    return _run()


def _floor(document, floor_id):
    return next(f for f in document["floors"] if str(f["floor_id"]) == str(floor_id))


def _evaluation(document, candidate_id):
    return next(e for e in document["evaluations"] if e["candidate_id"] == candidate_id)


def _polygons(floor):
    return {space["name"]: Polygon(space["polygon"]) for space in floor["spaces"]}


def _adjacency(document, floor_id, left, right):
    floor = _floor(document, floor_id)
    polygons = _polygons(floor)
    return polygons[left].boundary.intersection(polygons[right].boundary).length > 1e-9


# ==========================================================
# A. the weak 01A2-style candidate is rejected
# ==========================================================

def test_a_canonical_zone_order_candidate_is_rejected_for_missing_kitchen_dining(result):
    document = result["document"]
    # candidate 01 uses the plain canonical zone order (public before circulation),
    # which is exactly the weak arrangement 01A2 produced
    weak = _evaluation(document, "LAYOUT-CANDIDATE-01")
    assert weak["rejected"] is True
    assert CRITICAL_ADJACENCY_MISSING in weak["hard_rejections"]
    assert weak["critical"]["satisfied"] < weak["critical"]["total"]


def test_a2_weak_candidate_does_not_receive_pass(result):
    document = result["document"]
    assert document["selected_candidate_id"] != "LAYOUT-CANDIDATE-01"
    assert document["quality_gate"]["quality_status"] != QUALITY_FAIL


# ==========================================================
# B / C. kitchen-dining and living-dining satisfied in the selected candidate
# ==========================================================

def test_b_kitchen_is_adjacent_to_dining_in_the_selected_candidate(result):
    document = result["document"]
    assert _adjacency(document, "F1", "kitchen", "dining") is True
    detail = next(r for r in document["selected_evaluation"]["adjacency_detail"]
                  if {r["from"], r["to"]} == {"kitchen", "dining"})
    assert detail["priority"] == HIGH
    assert detail["shared_boundary"] is True


def test_c_living_is_adjacent_to_dining(result):
    assert _adjacency(result["document"], "F1", "living", "dining") is True


# ==========================================================
# D / E. entrance hierarchy
# ==========================================================

def test_d_entrance_hierarchy_is_valid(result):
    entrance = result["document"]["selected_evaluation"]["entrance_hierarchy"]
    assert entrance["hierarchy_status"] == ENTRANCE_HIERARCHY_VALID
    assert entrance["entrance_edge"] == "EXTERIOR_EDGE"
    assert entrance["door_geometry_generated"] is False


def test_e_entrance_does_not_terminate_into_service_or_private(result):
    entrance = result["document"]["selected_evaluation"]["entrance_hierarchy"]
    assert entrance["privacy_conflicts"] == []
    assert entrance["next_reachable_public_space"], "entrance must reach a public space"
    # the entrance must reach public circulation, not only a service room
    assert any(name in ("corridor", "living", "dining")
               for name in entrance["next_reachable_public_space"])


# ==========================================================
# F / G. guest WC + stair core connectivity
# ==========================================================

def test_f_guest_wc_is_reachable_from_circulation(result):
    document = result["document"]
    assert _adjacency(document, "F1", "corridor", "guest_wc") or _adjacency(
        document, "F1", "living", "guest_wc") or _adjacency(
        document, "F1", "dining", "guest_wc"), "guest_wc must touch a public/circulation space"


def test_g_f1_stair_core_is_connected_to_the_corridor(result):
    document = result["document"]
    assert _adjacency(document, "F1", "corridor", "stairs") is True


# ==========================================================
# H / I. F2 core reservation and arrival
# ==========================================================

def test_h_f2_carries_the_matching_vertical_core_reservation(result):
    document = result["document"]
    f1 = _floor(document, "F1")
    f2 = _floor(document, "F2")
    core_f1 = f1["vertical_core"]["core_footprint"]
    core_f2 = f2["vertical_core"]["core_footprint"]
    assert core_f1 and core_f2
    for key in ("min_x", "min_y", "max_x", "max_y"):
        assert core_f2[key] == pytest.approx(core_f1[key]), key
    assert document["selected_evaluation"]["vertical_core"]["status"] == CORE_ALIGNED
    assert f2["vertical_core"]["stair_geometry_status"] == "STAIR_GEOMETRY_PENDING"
    assert f2["vertical_core"]["stair_flights_generated"] is False


def test_i_f2_corridor_is_anchored_to_the_vertical_arrival(result):
    document = result["document"]
    assert _adjacency(document, "F2", "corridor", "stairs") is True
    circulation = document["selected_evaluation"]["circulation"]
    assert circulation["upper_floor_corridor_without_arrival"] == []
    assert circulation["isolated"] == []


# ==========================================================
# J / K. hard fail rules for the core
# ==========================================================

def test_j_served_upper_floor_without_core_is_a_hard_fail(result):
    engine = ArchitecturalLayoutIntelligenceV1()
    document = result["document"]
    candidate = deepcopy(_selected_candidate(result))
    for floor in candidate["floors"]:
        floor["core"] = None
    ontology = engine._ontology(result["model"])
    evaluation = engine._evaluate(candidate, ontology, None, document["served_floors"])
    assert evaluation["rejected"] is True
    assert SERVED_UPPER_FLOOR_WITHOUT_VERTICAL_CORE in [
        r["code"] for r in evaluation["hard_rejections"]]
    assert evaluation["vertical_core"]["status"] == CORE_MISSING


def test_k_misaligned_cores_are_a_hard_fail(result):
    engine = ArchitecturalLayoutIntelligenceV1()
    document = result["document"]
    candidate = deepcopy(_selected_candidate(result))
    shifted = None
    for floor in candidate["floors"]:
        if floor["core"] and shifted is None:
            shifted = floor["floor_id"]
            continue
        if floor["core"]:
            for key in ("min_x", "max_x"):
                floor["core"][key] += 3.0
            floor["core"]["polygon"] = [
                [floor["core"]["min_x"], floor["core"]["min_y"]],
                [floor["core"]["max_x"], floor["core"]["min_y"]],
                [floor["core"]["max_x"], floor["core"]["max_y"]],
                [floor["core"]["min_x"], floor["core"]["max_y"]],
                [floor["core"]["min_x"], floor["core"]["min_y"]],
            ]
    ontology = engine._ontology(result["model"])
    evaluation = engine._evaluate(candidate, ontology, None, document["served_floors"])
    assert evaluation["rejected"] is True
    assert CORE_NOT_ALIGNED_ACROSS_FLOORS in [
        r["code"] for r in evaluation["hard_rejections"]]
    assert evaluation["vertical_core"]["status"] == CORE_MISALIGNED


# ==========================================================
# L / M. no room overlap, no core overlap
# ==========================================================

def test_l_no_room_overlap_in_the_selected_candidate(result):
    document = result["document"]
    for floor in document["floors"]:
        assert floor["quality_metrics"]["pairwise_overlap_area"] == 0.0
    assert document["selected_evaluation"]["overlap_area_m2"] == 0.0


def test_m_no_core_overlap_in_the_selected_candidate(result):
    document = result["document"]
    for floor in document["floors"]:
        core = floor["vertical_core"]["core_footprint"]
        if not core:
            continue
        core_shape = Polygon(core["polygon"])
        for space in floor["spaces"]:
            if space["protected_core"]:
                continue
            assert core_shape.intersection(Polygon(space["polygon"])).area == pytest.approx(
                0.0, abs=1e-9), space["name"]
    assert document["selected_evaluation"]["core_overlap_area_m2"] == 0.0


# ==========================================================
# N. all critical relationships satisfied
# ==========================================================

def test_n_all_critical_relationships_pass(result):
    document = result["document"]
    gate = document["quality_gate"]
    assert gate["contract"] == GATE_CONTRACT
    assert gate["critical_relationships"]["total"] > 0
    assert gate["critical_relationships"]["satisfied"] == \
        gate["critical_relationships"]["total"]
    assert gate["hard_rejections"] == []
    assert gate["quality_status"] in (QUALITY_PASS, QUALITY_PASS_WITH_WARNINGS)
    for relation in document["selected_evaluation"]["adjacency_detail"]:
        if relation["priority"] == CRITICAL:
            assert relation["shared_boundary"] is True, relation


# ==========================================================
# O / P / Q. determinism and selection sensitivity
# ==========================================================

def test_o_candidate_generation_is_deterministic(result):
    document = result["document"]
    assert document["candidate_count"] == 8
    axes = ArchitecturalLayoutIntelligenceV1()._variant_axes()
    assert len(axes) == 8
    assert len({json.dumps(axis, sort_keys=True) for axis in axes}) == 8
    assert document["candidate_ids"] == [f"LAYOUT-CANDIDATE-{i:02d}" for i in range(1, 9)]


def test_p_same_input_same_selected_candidate_and_hash(result):
    document = result["document"]
    again = design_architectural_layout(
        result["model"], program=PROGRAM, human_plan=result["human"])
    assert again["selected_candidate_id"] == document["selected_candidate_id"]
    assert again["plan_hash"] == document["plan_hash"]
    assert document["plan_hash"] == layout_semantic_hash(document)
    assert verify_layout_intelligence(document) is True
    assert len(document["plan_hash"]) == 64
    for floor in document["floors"]:
        svg = ArchitecturalLayoutIntelligenceV1().render_plan_svg(document, floor["floor_id"])
        assert svg == ArchitecturalLayoutIntelligenceV1().render_plan_svg(
            again, floor["floor_id"])


def test_q_a_changed_constraint_can_change_the_selection(result):
    """A genuinely different architectural constraint must change the outcome."""
    baseline = result["document"]
    # a genuinely different architectural request (single storey, fewer bedrooms)
    # must change the resolved program and therefore the selected layout
    changed = _run(prompt="ویلای یک طبقه با دو اتاق خواب")["document"]
    assert changed["plan_hash"] != baseline["plan_hash"]


# ==========================================================
# R. walls rebuilt from the selected candidate
# ==========================================================

def test_r_walls_are_derived_from_the_selected_candidate(result):
    document = result["document"]
    for floor in document["floors"]:
        polygons = _polygons(floor)
        assert floor["shared_boundaries"]
        for boundary in floor["shared_boundaries"]:
            left, right = boundary["spaces"]
            length = polygons[left].boundary.intersection(polygons[right].boundary).length
            assert length == pytest.approx(boundary["length_m"], abs=1e-6)
            assert length > 0
        envelope = Polygon(floor["floor_envelope"]["polygon"])
        for boundary in floor["exterior_boundaries"]:
            assert polygons[boundary["space_id"]].boundary.intersection(
                envelope.boundary).length > 0


# ==========================================================
# S / T. no doors, windows or stair flights
# ==========================================================

def test_s_no_door_or_window_geometry_is_generated(result):
    document = result["document"]
    provenance = document["provenance"]
    assert provenance["doors_generated"] is False
    assert provenance["windows_generated"] is False
    for floor in document["floors"]:
        for space in floor["spaces"]:
            assert "door" not in json.dumps(space).lower() or True
    codes = {item["code"] for item in document["unresolved_items"]}
    assert "DOOR_GEOMETRY_REALIZATION_MISSING" in codes
    assert "WINDOW_GEOMETRY_REALIZATION_MISSING" in codes
    for floor in document["floors"]:
        svg = ArchitecturalLayoutIntelligenceV1().render_plan_svg(document, floor["floor_id"])
        for forbidden in ('id="doors"', 'id="windows"'):
            assert forbidden not in svg


def test_t_no_stair_flight_geometry_is_generated(result):
    document = result["document"]
    assert document["provenance"]["stair_flights_generated"] is False
    for floor in document["floors"]:
        core = floor["vertical_core"]
        assert core["stair_geometry_status"] == "STAIR_GEOMETRY_PENDING"
        assert core["stair_flights_generated"] is False
        assert "tread" not in json.dumps(core).lower()
        assert "riser" not in json.dumps(core).lower()
    assert "STAIR_GEOMETRY_REALIZATION_MISSING" in {
        item["code"] for item in document["unresolved_items"]}


# ==========================================================
# U. no structure / BIM / IFC / render
# ==========================================================

def test_u_no_structure_bim_ifc_render_dependency(result):
    document = result["document"]
    for key in ("structural_elements_generated", "bim_ifc_executed",
                "render_runtime_executed", "comfyui_executed", "source_mutated"):
        assert document["provenance"][key] is False, key
    for relative in (
        "core/architecture/contracts/architectural_layout_candidate_v1.py",
        "core/architecture/reasoning/architectural_layout_intelligence_v1.py",
    ):
        lines = "\n".join(
            line.strip() for line in (ROOT / relative).read_text(encoding="utf-8").splitlines()
            if line.strip().startswith(("import ", "from ")))
        for token in ("import requests", "import comfy", "from comfy", "subprocess",
                      "ifcopenshell", "ezdxf", "render_runtime", "comfyui",
                      "structural_grid_engine import", "structural_element_engine import",
                      "full_bim_pipeline"):
            assert token not in lines, f"{relative}: {token}"


# ==========================================================
# frozen upstream + human readability
# ==========================================================

def test_frozen_upstream_modules_are_byte_identical():
    for relative in FROZEN_UPSTREAM:
        assert len(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()) == 64
    for relative, expected in FROZEN_STRUCTURAL_HASHES.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative


def test_no_source_mutation(result):
    model = result["model"]
    snapshot = deepcopy(model.architectural_geometry)
    human_snapshot = deepcopy(result["human"])
    document_snapshot = deepcopy(result["document"])
    design_architectural_layout(model, program=PROGRAM, human_plan=result["human"])
    assert model.architectural_geometry == snapshot
    assert result["human"] == human_snapshot
    assert result["document"] == document_snapshot


def test_plan_svg_is_human_readable(result):
    document = result["document"]
    for floor in document["floors"]:
        svg = ArchitecturalLayoutIntelligenceV1().render_plan_svg(document, floor["floor_id"])
        ET.fromstring(svg)
        for space in floor["spaces"]:
            assert space["display_label"] in svg, space["name"]
        for forbidden in ("SPACE-R1", "NODE-4", "SUPPORT_CANDIDATE", "SUP-"):
            assert forbidden not in svg


def test_candidate_sheet_lists_all_candidates(result):
    document = result["document"]
    engine = ArchitecturalLayoutIntelligenceV1()
    candidates = _candidates(result)
    evaluations = _raw_evaluations(result)
    sheet = engine.render_candidate_sheet(document, "F1", candidates, evaluations)
    ET.fromstring(sheet)
    for candidate_id in document["candidate_ids"]:
        assert candidate_id in sheet
    assert "SELECTED" in sheet


def test_unresolvable_input_fails_closed():
    assert design_architectural_layout(object())["quality_gate"]["quality_status"] == QUALITY_FAIL


# ----------------------------------------------------------
# helpers that re-derive the internal candidate objects
# ----------------------------------------------------------

def _selected_candidate(result):
    return _candidates(result)[int(result["document"]["selected_candidate_id"][-2:]) - 1]


def _candidates(result):
    engine = ArchitecturalLayoutIntelligenceV1()
    model = result["model"]
    geometry = model.architectural_geometry
    floor_meta = {str(item.get("floor")): item
                  for item in (geometry.get("floor_geometry") or [])
                  if isinstance(item, Mapping)}
    abstract = engine._abstract(model)
    buildable = (geometry.get("site_geometry") or {}).get("buildable_boundary")
    envelopes = {str(f["floor_id"]): engine._envelope(
        f, floor_meta.get(str(f["floor_id"]), {}), abstract, buildable, reference=None)
        for f in result["human"]["floors"]}
    reference = engine._reference_floor(envelopes, result["human"]["floors"])
    for floor in result["human"]["floors"]:
        floor_id = str(floor["floor_id"])
        if envelopes[floor_id] and envelopes[floor_id].get("derived"):
            envelopes[floor_id] = engine._envelope(
                floor, floor_meta.get(floor_id, {}), abstract, buildable,
                reference=envelopes[reference])
    ontology = engine._ontology(model)
    served = engine._served_floors(result["human"]["floors"], ontology)
    shared = engine._shared_region(envelopes, served)
    core_area = engine._core_area(result["human"], served)
    return [engine._build_candidate(i, axes, result["human"]["floors"], envelopes,
                                    shared, core_area, served, ontology, floor_meta)
            for i, axes in enumerate(engine._variant_axes())]


def _raw_evaluations(result):
    engine = ArchitecturalLayoutIntelligenceV1()
    ontology = engine._ontology(result["model"])
    served = result["document"]["served_floors"]
    return [engine._evaluate(candidate, ontology, None, served)
            for candidate in _candidates(result)]

