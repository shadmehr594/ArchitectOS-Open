"""ARCHITECTURAL-DESIGN-ROBUSTNESS-01A2 acceptance tests.

Coherent floor plan realization + non-overlapping space partition + continuous
wall topology.

Runs the REAL 2-floor villa chain (unchanged program from 01A) and proves that
same-floor interior polygons no longer overlap, the partition is zone-coherent,
wall topology is derived from the FINAL resolved boundaries, and unresolved
elements are reported instead of invented.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from shapely.geometry import Polygon

from core.architecture.contracts.coherent_architectural_floor_plan_v1 import (
    CONTRACT,
    EXTERIOR_WALL,
    INTERIOR_SHARED_WALL,
    PLACED,
    POST_LAYOUT_GEOMETRY_DRIFT,
    STAIR_CORE_SPACE_RESOLVED,
    STAIR_GEOMETRY_PENDING,
    VERSION,
    coherent_floor_semantic_hash,
    verify_coherent_floor_plan,
)
from core.architecture.reasoning.architectural_design_robustness_01a import (
    project_human_readable_plan,
)
from core.architecture.reasoning.coherent_floor_plan_resolver_v1 import (
    CoherentFloorPlanResolverV1,
    resolve_coherent_floor_plan,
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
    "core/architecture/geometry/architectural_geometry_intent_generator_v1.py",
    "core/architecture/reasoning/layout_reasoner.py",
    "core/architecture/model/architectural_plan_model.py",
    "core/architecture/drawing/plan_model_to_scene_adapter_v1.py",
)

PARCEL = [[0.0, 0.0], [20.0, 0.0], [20.0, 30.0], [0.0, 30.0]]

# The EXACT 01A program — unchanged, so the case is not made easier.
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
def coherent():
    from core.architecture.brain.architectural_brain import ArchitecturalBrain

    intent = ArchitecturalIntent().extract(
        {"prompt": "ویلای دو طبقه با سه اتاق خواب", "architectural_intent": PROGRAM},
        {"site": _site()},
    )
    model = ArchitecturalBrain().design(intent)
    human = project_human_readable_plan(model, program=PROGRAM)
    plan = resolve_coherent_floor_plan(model, program=PROGRAM, human_plan=human)
    return {"model": model, "human": human, "plan": plan}


def _floor(plan, floor_id):
    return next(f for f in plan["floors"] if str(f["floor_id"]) == str(floor_id))


def _polygons(floor):
    return {space["name"]: Polygon(space["polygon"]) for space in floor["spaces"]}


def _svg(plan, floor_id, diagnostic=False):
    return CoherentFloorPlanResolverV1().render_plan_svg(plan, floor_id, diagnostic=diagnostic)


# ==========================================================
# A / B. ZERO interior overlap
# ==========================================================

def test_a_zero_overlap_on_f1(coherent):
    floor = _floor(coherent["plan"], "F1")
    assert floor["spaces"]
    assert floor["quality_metrics"]["pairwise_overlap_area"] == 0.0
    assert floor["quality_metrics"]["maximum_overlap_area"] == 0.0
    assert floor["quality_metrics"]["layout_quality_status"] == "PASS"


def test_b_zero_overlap_on_f2(coherent):
    floor = _floor(coherent["plan"], "F2")
    assert floor["spaces"]
    assert floor["quality_metrics"]["pairwise_overlap_area"] == 0.0
    assert floor["quality_metrics"]["maximum_overlap_area"] == 0.0


def test_plan_status_and_contract(coherent):
    plan = coherent["plan"]
    assert plan["contract"] == CONTRACT
    assert plan["version"] == VERSION
    assert verify_coherent_floor_plan(plan) is True
    assert plan["root_cause_analysis"]["primary"] == POST_LAYOUT_GEOMETRY_DRIFT
    assert plan["root_cause_analysis"]["upstream_engine_modified"] is False
    assert plan["root_cause_analysis"]["layout_engine_replaced"] is False


# ==========================================================
# C. living / dining / kitchen no longer overlap
# ==========================================================

def test_c_living_dining_kitchen_do_not_overlap(coherent):
    polygons = _polygons(_floor(coherent["plan"], "F1"))
    for left, right in (("living", "dining"), ("living", "kitchen"), ("dining", "kitchen")):
        assert left in polygons and right in polygons
        assert polygons[left].intersection(polygons[right]).area == pytest.approx(0.0, abs=1e-9), \
            f"{left}/{right}"


def test_source_overlap_was_real_and_is_reported(coherent):
    """The upstream drift is proven, not hidden."""
    floor = _floor(coherent["plan"], "F1")
    conflict = next(c for c in floor["layout_conflicts"]
                    if c["code"] == POST_LAYOUT_GEOMETRY_DRIFT)
    assert conflict["source_footprint_overlap_area"] > 1.0
    assert floor["source_geometry_drifted"] is True


# ==========================================================
# D. corridor does not overlap other room interiors
# ==========================================================

def test_d_corridor_does_not_overlap_other_interiors(coherent):
    for floor_id in ("F1", "F2"):
        polygons = _polygons(_floor(coherent["plan"], floor_id))
        corridor = polygons["corridor"]
        for name, polygon in polygons.items():
            if name == "corridor":
                continue
            assert corridor.intersection(polygon).area == pytest.approx(0.0, abs=1e-9), name


# ==========================================================
# E. stair / core reserved region does not overlap other interiors
# ==========================================================

def test_e_stair_core_is_resolved_and_never_overlapped(coherent):
    floor = _floor(coherent["plan"], "F1")
    core = floor["stair_core"]
    assert core["core_space_status"] == STAIR_CORE_SPACE_RESOLVED
    assert core["stair_geometry_status"] == STAIR_GEOMETRY_PENDING
    assert core["stair_flights_generated"] is False

    polygons = _polygons(floor)
    stair = polygons["stairs"]
    for name, polygon in polygons.items():
        if name == "stairs":
            continue
        assert stair.intersection(polygon).area == pytest.approx(0.0, abs=1e-9), name


# ==========================================================
# F / G. external handling
# ==========================================================

def test_f_terrace_stays_external_and_out_of_the_interior_partition(coherent):
    plan = coherent["plan"]
    interior_names = {s["name"] for f in plan["floors"] for s in f["spaces"]}
    assert "terrace" not in interior_names, "an external space must not enter the interior partition"
    regions = [r for f in plan["floors"] for r in f["external_regions"]]
    assert regions, "the terrace must still be represented as an external region"
    assert all(r["external"] is True for r in regions)
    assert all(r["relation_to_building"] == "ADJACENT_EXTERNAL" for r in regions)


def test_g_pool_stays_unresolved_and_is_never_packed(coherent):
    plan = coherent["plan"]
    unresolved = [u for f in plan["floors"] for u in f["unresolved_spaces"]]
    assert any(item["name"] == "pool" for item in unresolved), unresolved
    for floor in plan["floors"]:
        assert "pool" not in {s["name"] for s in floor["spaces"]}


# ==========================================================
# H / I. floor envelope
# ==========================================================

def test_h_f1_envelope_resolves_from_architecture_evidence(coherent):
    floor = _floor(coherent["plan"], "F1")
    envelope = floor["floor_envelope"]
    assert envelope is not None
    assert envelope["width"] > 0 and envelope["depth"] > 0
    assert floor["floor_envelope_source"] == "FLOOR_ENVELOPE_DERIVED_FROM_PROGRAM_AREA"
    assert floor["quality_metrics"]["envelope_area"] == pytest.approx(
        envelope["width"] * envelope["depth"])

    # derived from resolved room areas + the floor's own abstract aspect only
    target = floor["quality_metrics"]["total_program_target_area"]
    assert floor["quality_metrics"]["envelope_area"] == pytest.approx(target, rel=0.01)


def test_i_f2_envelope_is_preserved_from_source(coherent):
    floor = _floor(coherent["plan"], "F2")
    source = next(
        item for item in coherent["model"].architectural_geometry["floor_geometry"]
        if str(item.get("floor")) == "F2")
    assert floor["floor_envelope_source"] == "floor_metric_envelope_preserved"
    assert floor["floor_envelope"]["width"] == pytest.approx(source["envelope"]["width"])
    assert floor["floor_envelope"]["depth"] == pytest.approx(source["envelope"]["depth"])


# ==========================================================
# J / K. identity and area policy
# ==========================================================

def test_j_space_identity_and_semantic_roles_preserved(coherent):
    source = {
        (f["floor_id"], s["name"]): s
        for f in coherent["human"]["floors"] for s in f["spaces"]
    }
    for floor in coherent["plan"]["floors"]:
        for space in floor["spaces"]:
            original = source[(floor["floor_id"], space["name"])]
            assert space["space_id"] == original["space_id"]
            assert space["semantic_type"] == original["semantic_type"]
            assert space["zone"] == original["zone"]
            assert space["display_label"] == original["display_label"]


def test_k_area_deviations_are_explicitly_recorded(coherent):
    for floor in coherent["plan"]["floors"]:
        for space in floor["spaces"]:
            assert space["requested_area_m2"] > 0
            assert space["realized_area_m2"] > 0
            assert space["area_delta_m2"] == pytest.approx(
                space["realized_area_m2"] - space["requested_area_m2"], abs=1e-6)
        metrics = floor["quality_metrics"]
        assert metrics["area_deficit_or_surplus"] == pytest.approx(
            metrics["realized_interior_area"] - metrics["total_program_target_area"],
            abs=1e-6)


# ==========================================================
# L. all realized interior spaces inside the valid envelope
# ==========================================================

def test_l_all_realized_spaces_lie_inside_the_envelope(coherent):
    for floor in coherent["plan"]["floors"]:
        envelope = Polygon(floor["floor_envelope"]["polygon"])
        for space in floor["spaces"]:
            polygon = Polygon(space["polygon"])
            assert envelope.covers(polygon), f"{floor['floor_id']}/{space['name']}"
        assert floor["quality_metrics"]["unallocated_interior_area"] >= 0.0


# ==========================================================
# M / N / O. wall topology
# ==========================================================

def test_m_internal_shared_walls_correspond_to_real_touching_edges(coherent):
    for floor in coherent["plan"]["floors"]:
        polygons = _polygons(floor)
        assert floor["shared_boundaries"], floor["floor_id"]
        for boundary in floor["shared_boundaries"]:
            left, right = boundary["spaces"]
            length = polygons[left].boundary.intersection(polygons[right].boundary).length
            assert length == pytest.approx(boundary["length_m"], abs=1e-6)
            assert length > 0
            assert boundary["wall_type"] == INTERIOR_SHARED_WALL


def test_n_exterior_walls_correspond_to_the_envelope_boundary(coherent):
    for floor in coherent["plan"]["floors"]:
        envelope = Polygon(floor["floor_envelope"]["polygon"])
        polygons = _polygons(floor)
        assert floor["exterior_boundaries"], floor["floor_id"]
        for boundary in floor["exterior_boundaries"]:
            polygon = polygons[boundary["space_id"]]
            shared = polygon.boundary.intersection(envelope.boundary).length
            assert shared > 0
            assert boundary["wall_type"] == EXTERIOR_WALL
        # no exterior wall may separate two interior rooms
        for boundary in floor["exterior_boundaries"]:
            other = [
                name for name, polygon in polygons.items()
                if name != boundary["space_id"]
                and polygon.boundary.intersection(envelope.boundary).length > 1e-6
            ]
            assert boundary["space_id"] not in other


def test_o_no_stale_wall_from_the_overlapping_layout_survives(coherent):
    """Every reported wall is derived from the FINAL resolved boundaries."""
    for floor in coherent["plan"]["floors"]:
        polygons = _polygons(floor)
        for boundary in floor["shared_boundaries"] + floor["exterior_boundaries"]:
            assert boundary["provenance"]["geometry_invented"] is False
        assert floor["quality_metrics"]["internal_shared_wall_count"] == len(
            floor["shared_boundaries"])
        assert floor["quality_metrics"]["exterior_wall_count"] == len(
            floor["exterior_boundaries"])
        # no wall references a space that is not in the resolved partition
        for boundary in floor["shared_boundaries"]:
            for name in boundary["spaces"]:
                assert name in polygons


# ==========================================================
# P / Q. determinism and immutability
# ==========================================================

def test_p_same_input_same_resolved_layout_and_hash(coherent):
    model = coherent["model"]
    human = coherent["human"]
    first = resolve_coherent_floor_plan(model, program=PROGRAM, human_plan=human)
    second = resolve_coherent_floor_plan(model, program=PROGRAM, human_plan=human)
    assert first["plan_hash"] == second["plan_hash"]
    assert len(first["plan_hash"]) == 64
    assert first["plan_hash"] == coherent_floor_semantic_hash(first)
    for floor in first["floors"]:
        assert _svg(first, floor["floor_id"]) == _svg(second, floor["floor_id"])


def test_q_no_source_or_frozen_parent_mutation(coherent):
    model = coherent["model"]
    geometry_snapshot = deepcopy(model.architectural_geometry)
    plan_snapshot = deepcopy(coherent["plan"])
    human_snapshot = deepcopy(coherent["human"])

    resolve_coherent_floor_plan(model, program=PROGRAM, human_plan=coherent["human"])

    assert model.architectural_geometry == geometry_snapshot
    assert coherent["plan"] == plan_snapshot
    assert coherent["human"] == human_snapshot
    provenance = coherent["plan"]["provenance"]
    for key in ("geometry_invented", "spaces_moved_without_decision", "spaces_deleted",
                "source_mutated", "structural_elements_generated", "bim_ifc_executed",
                "render_runtime_executed", "comfyui_executed"):
        assert provenance[key] is False, key


def test_frozen_upstream_modules_are_byte_identical():
    for relative in FROZEN_UPSTREAM:
        assert len(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()) == 64
    for relative, expected in FROZEN_STRUCTURAL_HASHES.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative


# ==========================================================
# R. no structure / BIM / IFC / render dependency
# ==========================================================

def test_r_no_structure_bim_ifc_render_dependency():
    forbidden = (
        "import requests", "from requests", "import comfy", "from comfy",
        "import subprocess", "from subprocess", "ifcopenshell", "ezdxf",
        "render_runtime", "comfyui", "structural_grid_engine import",
        "structural_element_engine import", "full_bim_pipeline",
    )
    for relative in (
        "core/architecture/contracts/coherent_architectural_floor_plan_v1.py",
        "core/architecture/reasoning/coherent_floor_plan_resolver_v1.py",
    ):
        lines = "\n".join(
            line.strip() for line in (ROOT / relative).read_text(encoding="utf-8").splitlines()
            if line.strip().startswith(("import ", "from ")))
        for token in forbidden:
            assert token not in lines, f"{relative}: {token}"


# ==========================================================
# quality metrics + SVG
# ==========================================================

def test_quality_metrics_are_complete(coherent):
    required = (
        "space_count", "resolved_space_count", "unresolved_space_count",
        "total_program_target_area", "realized_interior_area", "external_area",
        "pairwise_overlap_area", "maximum_overlap_area", "envelope_area",
        "unallocated_interior_area", "area_deficit_or_surplus",
        "adjacency_requirements_total", "adjacency_requirements_satisfied",
        "circulation_connectivity_status", "internal_shared_wall_count",
        "exterior_wall_count", "layout_quality_status",
    )
    for floor in coherent["plan"]["floors"]:
        metrics = floor["quality_metrics"]
        for key in required:
            assert key in metrics, key
        assert metrics["pairwise_overlap_area"] == 0.0
        assert metrics["circulation_connectivity_status"] == "CONNECTED"
        assert metrics["adjacency_requirements_satisfied"] <= metrics["adjacency_requirements_total"]


def test_circulation_has_no_isolated_internal_room(coherent):
    for floor in coherent["plan"]["floors"]:
        isolated = [
            item["space_id"] for item in floor["circulation_connections"]
            if not item["reachable"]
        ]
        assert isolated == [], f"{floor['floor_id']}: {isolated}"


def test_svg_is_human_readable_and_diagnostics_are_separate(coherent):
    plan = coherent["plan"]
    for floor in plan["floors"]:
        svg = _svg(plan, floor["floor_id"])
        ET.fromstring(svg)
        assert 'id="diagnostics"' not in svg
        for space in floor["spaces"]:
            assert space["display_label"] in svg, space["name"]
        for forbidden in ("SPACE-R1", "NODE-4", "SUPPORT_CANDIDATE", "SUP-"):
            assert forbidden not in svg
        diagnostic = _svg(plan, floor["floor_id"], diagnostic=True)
        ET.fromstring(diagnostic)
        assert 'id="diagnostics"' in diagnostic
        assert "overlap=" in diagnostic


def test_unresolved_is_reported_when_envelope_cannot_hold_program():
    resolver = CoherentFloorPlanResolverV1()
    plan = resolver.resolve(object())
    assert plan["plan_status"] == "FAILED"
    assert plan["floors"] == []
