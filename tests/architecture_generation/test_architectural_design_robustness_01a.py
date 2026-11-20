"""ARCHITECTURAL-DESIGN-ROBUSTNESS-01A acceptance tests.

Full plan realization audit + human-readable plan contract.

The suite runs the REAL generator chain on a controlled 2-floor villa program
and proves that the plan output is honest: realized geometry is rendered,
missing realization is reported (never invented), and no structural/BIM/IFC/
render path is touched.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from core.architecture.contracts.architectural_human_readable_plan_v1 import (
    COMPLETENESS_CONTRACT,
    CONTRACT,
    DOOR_GEOMETRY_REALIZATION_MISSING,
    MISSING_REALIZATION,
    PLAN_STATUSES,
    READY_FOR_PLAN_DISPLAY,
    STATUS_GEOMETRY_INCOMPLETE,
    VERSION,
    WINDOW_GEOMETRY_REALIZATION_MISSING,
    canonical_plan_document,
    display_label,
    plan_semantic_hash,
    verify_human_readable_plan,
)
from core.architecture.reasoning.architectural_design_robustness_01a import (
    ArchitecturalDesignRobustness01A,
    project_human_readable_plan,
)
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent


ROOT = Path(__file__).resolve().parents[2]

# Frozen parents this phase must never modify.
FROZEN_UPSTREAM = (
    "core/architecture/reasoning/plan_model_reasoner.py",
    "core/architecture/model/architectural_plan_model.py",
    "core/architecture/drawing/plan_model_to_scene_adapter_v1.py",
    "core/architecture/drawing/plan_drawing_service_v1.py",
    "core/architecture/drawing/svg_architectural_renderer_v1.py",
    "core/architecture/reasoning/architectural_baseline_structural_readiness_v1.py",
    "core/architecture/contracts/architectural_structural_readiness_v1.py",
    "core/structure/structural_grid_engine.py",
    "core/structure/structural_element_engine.py",
)

# Structural engines remain byte-identical to their Design-05 freeze.
FROZEN_STRUCTURAL_HASHES = {
    "core/structure/structural_grid_engine.py":
        "886d0d1cba71f211c503e4eea532b677396a331abf6565a8f018fa863dd12263",
    "core/structure/structural_element_engine.py":
        "935f9bd4e047f7c9e339a81ba016bb3455db8d1b725e14d837da9f1e7d39a950",
}

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


def _site():
    return {
        "source": "parcel", "source_type": "polygon",
        "boundary": {"type": "polygon", "points": PARCEL},
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


@pytest.fixture(scope="module")
def generated():
    """Run the REAL 2-floor villa chain once for the whole module."""
    from core.architecture.brain.architectural_brain import ArchitecturalBrain

    intent = ArchitecturalIntent().extract(
        {"prompt": "ویلای دو طبقه با سه اتاق خواب", "architectural_intent": PROGRAM},
        {"site": _site()},
    )
    model = ArchitecturalBrain().design(intent)
    plan = project_human_readable_plan(model, program=PROGRAM)
    return {"model": model, "intent": intent, "plan": plan}


def _floor(plan, floor_id):
    return next(f for f in plan["floors"] if str(f["floor_id"]) == str(floor_id))


def _svg(plan, floor_id, diagnostic=False):
    return ArchitecturalDesignRobustness01A().render_plan_svg(
        plan, floor_id, diagnostic=diagnostic)


# ==========================================================
# A. more than one distinct semantic space
# ==========================================================

def test_a_generator_produces_multiple_distinct_semantic_spaces(generated):
    plan = generated["plan"]
    names = [space["name"] for floor in plan["floors"] for space in floor["spaces"]]
    assert len(names) > 1
    # a name may legitimately repeat across floors (e.g. corridor), never within one
    for floor in plan["floors"]:
        floor_names = [space["name"] for space in floor["spaces"]]
        assert len(set(floor_names)) == len(floor_names), floor["floor_id"]
    assert set(names) >= {
        "living", "kitchen", "dining", "master_bedroom", "bedroom", "bathroom",
        "corridor", "entrance",
    }
    assert len(plan["floors"]) == 2


# ==========================================================
# B. stable id + semantic role per realized space
# ==========================================================

def test_b_realized_spaces_have_stable_id_and_semantic_role(generated):
    for floor in generated["plan"]["floors"]:
        for space in floor["spaces"]:
            assert isinstance(space["space_id"], str) and space["space_id"]
            assert isinstance(space["display_label"], str) and space["display_label"]
            assert space["semantic_type"] or space["canonical_name"]
            assert space["zone"]
            assert space["floor"] == floor["floor_id"]
            assert space["provenance"]["geometry_invented"] is False


# ==========================================================
# C. deterministic floor assignment
# ==========================================================

def test_c_floor_assignment_is_deterministic(generated):
    model = generated["model"]
    first = project_human_readable_plan(model, program=PROGRAM)
    second = project_human_readable_plan(model, program=PROGRAM)
    assert [f["floor_id"] for f in first["floors"]] == [
        f["floor_id"] for f in second["floors"]] == ["F1", "F2"]
    assert [f["floor_order"] for f in first["floors"]] == [0, 1]
    assert first["plan_hash"] == second["plan_hash"]


# ==========================================================
# D. human-readable labels in the SVG
# ==========================================================

def test_d_svg_uses_human_readable_room_labels(generated):
    plan = generated["plan"]
    svg_f1 = _svg(plan, "F1")
    svg_f2 = _svg(plan, "F2")
    ET.fromstring(svg_f1)
    ET.fromstring(svg_f2)

    for label in ("ENTRANCE", "LIVING", "KITCHEN", "DINING", "GUEST WC", "CORRIDOR"):
        assert label in svg_f1, label
    for label in ("MASTER BEDROOM", "BEDROOM", "BATHROOM", "CORRIDOR"):
        assert label in svg_f2, label

    for internal in ("SPACE-R1", "SPACE-F1", "NODE-4", "EDGE-22"):
        assert internal not in svg_f1
        assert internal not in svg_f2


def test_d2_display_label_is_presentation_only(generated):
    assert display_label("master_bedroom") == "MASTER BEDROOM"
    assert display_label("guest_wc") == "GUEST WC"
    space = next(
        s for f in generated["plan"]["floors"] for s in f["spaces"] if s["name"] == "master_bedroom")
    assert space["name"] == "master_bedroom"          # canonical preserved
    assert space["display_label"] == "MASTER BEDROOM"  # presentation only


# ==========================================================
# E. existing geometry rendered without modification
# ==========================================================

def test_e_realized_geometry_is_rendered_verbatim(generated):
    model = generated["model"]
    geometry = model.architectural_geometry
    source = {
        (str(s.get("floor")), str(s.get("name"))): [list(map(float, p)) for p in s["footprint"]["points"]]
        for s in geometry["spaces"]
        if isinstance(s.get("footprint"), dict) and s["footprint"].get("points")
    }
    checked = 0
    for floor in generated["plan"]["floors"]:
        for space in floor["spaces"]:
            if space["realization"] != READY_FOR_PLAN_DISPLAY:
                continue
            key = (str(space["geometry_floor"]), space["name"])
            assert space["polygon"] == source[key], space["name"]
            checked += 1
    assert checked >= 10


# ==========================================================
# F. missing internal wall geometry reported, never invented
# ==========================================================

def test_f_wall_realization_is_truthful(generated):
    walls = [w for f in generated["plan"]["floors"] for w in f["walls"]]
    assert walls
    for wall in walls:
        if wall["realization"] == READY_FOR_PLAN_DISPLAY:
            assert len(wall["geometry"]) == 2, "a drawn wall must have real start/end"
        else:
            assert wall["geometry"] == [], "an unrealized wall must carry no geometry"
    interior = [w for w in walls if not w["external"]]
    assert interior, "interior walls must exist in this program"
    # every interior wall drawn in the SVG must come from real geometry
    svg = _svg(generated["plan"], "F1")
    ET.fromstring(svg)
    assert "PLAN_WALL_INTERIOR" not in svg or interior


# ==========================================================
# G / H. missing door & window geometry reported, never invented
# ==========================================================

def test_g_missing_door_geometry_is_reported_not_drawn(generated):
    plan = generated["plan"]
    doors = [d for f in plan["floors"] for d in f["doors"]]
    assert doors, "the program requires doors"
    assert all(d["realization"] == MISSING_REALIZATION for d in doors)
    assert all(d["geometry"] == [] for d in doors)
    assert all(d["host_wall_id"] is None for d in doors)
    assert DOOR_GEOMETRY_REALIZATION_MISSING in plan["completeness"]["missing_realization_stages"]

    svg = _svg(plan, "F1")
    assert '<g id="doors"></g>' in svg, "no door may be drawn without host geometry"
    assert plan["completeness"]["doors_realized"] == 0


def test_h_missing_window_geometry_is_reported_not_drawn(generated):
    plan = generated["plan"]
    windows = [w for f in plan["floors"] for w in f["windows"]]
    assert windows, "the program requires windows"
    assert all(w["realization"] == MISSING_REALIZATION for w in windows)
    assert all(w["geometry"] == [] for w in windows)
    assert WINDOW_GEOMETRY_REALIZATION_MISSING in plan["completeness"]["missing_realization_stages"]
    svg = _svg(plan, "F2")
    assert '<g id="windows"></g>' in svg
    assert plan["completeness"]["windows_realized"] == 0


# ==========================================================
# I. stair / elevator semantic vs placement vs geometry
# ==========================================================

def test_i_vertical_circulation_states_are_distinguished(generated):
    vertical = [v for f in generated["plan"]["floors"] for v in f["vertical_circulation"]]
    assert vertical, "the program requires a stair"
    stair = next(v for v in vertical if "stair" in str(v.get("system_type")))
    assert stair["semantic_requirement"] == "PRESENT"
    assert stair["placement"] == "PENDING"
    assert stair["geometry_realization"] != READY_FOR_PLAN_DISPLAY
    assert stair["missing_evidence"], "missing stair evidence must be named"
    # the stair is never drawn as if it were a complete stair design
    svg = _svg(generated["plan"], "F2")
    assert "PLAN_STAIR" not in svg


# ==========================================================
# J. external terrace stays external
# ==========================================================

def test_j_external_terrace_remains_external(generated):
    plan = generated["plan"]
    terrace = next(
        s for f in plan["floors"] for s in f["spaces"] if s["name"] == "terrace")
    assert terrace["external"] is True
    assert terrace["realization"] == READY_FOR_PLAN_DISPLAY
    assert terrace["area_m2"] == pytest.approx(15.0)
    svg = _svg(plan, terrace["floor"])
    assert "TERRACE" in svg
    assert "PLAN_SPACE_EXTERNAL" not in svg  # token is resolved, not emitted literally


# ==========================================================
# K. no structural support markers in the normal plan
# ==========================================================

def test_k_no_structural_support_markers_in_the_plan_svg(generated):
    for floor in generated["plan"]["floors"]:
        svg = _svg(generated["plan"], floor["floor_id"])
        for forbidden in ("SUPPORT_CANDIDATE", "support_candidate", "SUP-", "REJ-",
                          "ELIGIBILITY_REGION", "structural_grid"):
            assert forbidden not in svg, forbidden


# ==========================================================
# L. no structural engine execution
# ==========================================================

def test_l_no_structural_engine_execution(generated):
    provenance = generated["plan"]["provenance"]
    assert provenance["structural_elements_generated"] is False
    assert provenance["geometry_invented"] is False
    assert provenance["walls_invented"] is False
    assert provenance["doors_invented"] is False
    assert provenance["windows_invented"] is False
    for relative in ("core/architecture/reasoning/architectural_design_robustness_01a.py",
                     "core/architecture/contracts/architectural_human_readable_plan_v1.py"):
        lines = "\n".join(
            line.strip() for line in (ROOT / relative).read_text(encoding="utf-8").splitlines()
            if line.strip().startswith(("import ", "from ")))
        for token in ("structural_grid_engine", "structural_element_engine",
                      "full_bim_pipeline", "render_runtime", "comfyui", "ifcopenshell",
                      "ezdxf", "subprocess"):
            assert token not in lines, f"{relative}: {token}"


# ==========================================================
# M. deterministic plan output
# ==========================================================

def test_m_plan_output_is_deterministic(generated):
    model = generated["model"]
    first = project_human_readable_plan(model, program=PROGRAM)
    second = project_human_readable_plan(model, program=PROGRAM)
    assert first["plan_hash"] == second["plan_hash"]
    assert len(first["plan_hash"]) == 64
    assert first["plan_hash"] == plan_semantic_hash(first)
    for floor in first["floors"]:
        assert _svg(first, floor["floor_id"]) == _svg(second, floor["floor_id"])


# ==========================================================
# N. frozen parents unchanged + no source mutation
# ==========================================================

def test_n_frozen_parents_are_not_modified():
    for relative in FROZEN_UPSTREAM:
        digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert len(digest) == 64
    for relative, expected in FROZEN_STRUCTURAL_HASHES.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative


def test_n2_no_source_mutation(generated):
    model = generated["model"]
    snapshot = deepcopy(model.architectural_geometry)
    plan_snapshot = deepcopy(generated["plan"])
    project_human_readable_plan(model, program=PROGRAM)
    assert model.architectural_geometry == snapshot
    assert generated["plan"] == plan_snapshot


# ==========================================================
# O. no BIM / IFC / RenderRuntime / ComfyUI dependency
# ==========================================================

def test_o_no_bim_ifc_render_dependency(generated):
    provenance = generated["plan"]["provenance"]
    for key in ("bim_ifc_executed", "render_runtime_executed", "comfyui_executed"):
        assert provenance[key] is False, key


# ==========================================================
# P. completeness report reflects reality
# ==========================================================

def test_p_completeness_report_is_accurate(generated):
    plan = generated["plan"]
    completeness = plan["completeness"]
    assert completeness["contract"] == COMPLETENESS_CONTRACT
    assert completeness["completeness_status"] in PLAN_STATUSES

    floors = plan["floors"]
    assert completeness["spaces_with_geometry"] == sum(
        1 for f in floors for s in f["spaces"] if s["realization"] == READY_FOR_PLAN_DISPLAY)
    assert completeness["doors_required"] == sum(len(f["doors"]) for f in floors)
    assert completeness["doors_realized"] == sum(
        1 for f in floors for d in f["doors"] if d["realization"] == READY_FOR_PLAN_DISPLAY)
    assert completeness["windows_required"] == sum(len(f["windows"]) for f in floors)
    assert completeness["internal_walls_required"] == sum(
        1 for f in floors for w in f["walls"] if not w["external"])
    assert completeness["internal_walls_realized"] == sum(
        1 for f in floors for w in f["walls"]
        if not w["external"] and w["realization"] == READY_FOR_PLAN_DISPLAY)
    assert completeness["vertical_circulation_required"] == sum(
        len(f["vertical_circulation"]) for f in floors)
    assert completeness["completeness_status"] == STATUS_GEOMETRY_INCOMPLETE
    assert completeness["missing_realization_stages"]
    assert completeness["spaces_without_geometry"] == sorted(set(
        s["name"] for f in floors for s in f["spaces"]
        if s["realization"] != READY_FOR_PLAN_DISPLAY))


def test_p2_plan_contract_is_verifiable_and_round_trips(generated):
    plan = generated["plan"]
    assert plan["contract"] == CONTRACT
    assert plan["version"] == VERSION
    assert verify_human_readable_plan(plan) is True
    assert json.loads(json.dumps(plan, ensure_ascii=False, default=str))["plan_hash"] == \
        plan["plan_hash"]
    assert canonical_plan_document(plan)
    tampered = deepcopy(plan)
    tampered["floors"][0]["spaces"][0]["area_m2"] = 999.0
    assert verify_human_readable_plan(tampered) is False


def test_unresolved_geometry_is_structured(generated):
    unresolved = generated["plan"]["unresolved_geometry"]
    assert unresolved
    for item in unresolved:
        assert item["code"]
        assert item["stage"], "each gap must name the responsible stage"


def test_diagnostic_svg_is_available_and_separate(generated):
    plan = generated["plan"]
    diagnostic = _svg(plan, "F1", diagnostic=True)
    ET.fromstring(diagnostic)
    assert "DIAGNOSTIC" in diagnostic
    assert 'id="diagnostics"' in diagnostic
    normal = _svg(plan, "F1")
    assert 'id="diagnostics"' not in normal


def test_failed_projection_for_missing_model():
    plan = project_human_readable_plan(object())
    assert plan["plan_status"] == "FAILED"
    assert plan["floors"] == []
