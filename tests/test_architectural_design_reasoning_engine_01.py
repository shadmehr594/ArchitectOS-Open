from __future__ import annotations

import json
from pathlib import Path
import pytest

from core.architecture.reasoning_engine import ArchitecturalDesignReasoningEngine
from core.architecture.reasoning_engine.architectural_constraint_engine_v1 import ArchitecturalConstraintEngine
from core.architecture.reasoning_engine.cross_layer_consistency_validator import CrossLayerConsistencyValidator
from core.architecture.reasoning_engine.human_learning import AppendOnlyHumanLearningRegistry
from core.architecture.reasoning_engine.operators import *
from core.architecture.reasoning_engine.state import *
from core.architecture.drawing import ArchitecturalPlanRealizer


BRIEF={"site_width_m":10,"site_depth_m":20,"north":"TOP","street":"SOUTH","storeys":1,"target_area_m2":120,"ffl_m":.38,"jurisdiction":"MINAB","minab_overlay":"CONDITIONAL_EVIDENCE_REQUIRED"}

@pytest.fixture(scope="module")
def states(): return ArchitecturalDesignReasoningEngine().synthesize(BRIEF,4)

def test_at_least_three_distinct(states):
    assert len(states)>=3
    assert len({tuple(sorted(s.circulation_graph)) for s in states})==len(states)

@pytest.mark.parametrize("field",QUALITY_FIELDS)
def test_explainable_quality_vector(states,field):
    assert all(field in s.quality_vector.components and s.quality_vector.reasons[field] for s in states)

def test_one_shared_world_model(states):
    s=states[0]; assert s.spaces and s.wall_graph and s.daylight_source_graph and s.opening_intents and s.free_space_navigation_graph

def test_topology_precedes_geometry_trace(states):
    stages=[x["stage"] for x in states[0].trace]; assert stages.index("TOPOLOGY")<stages.index("GEOMETRY_SYNTHESIS")

def test_hard_constraints_pass(states): assert all(ArchitecturalConstraintEngine().hard_pass(s) for s in states)

def test_openings_exact_shared_boundary(states):
    for s in states:
        for o in s.opening_intents:
            if o.kind in {"DOOR","OPEN"}: assert s.spaces[o.space_a].rect.shared_boundary(s.spaces[o.space_b_or_source].rect)==o.host

def test_geometric_daylight_source_proof(states):
    for s in states:
        for sid,src in s.daylight_source_graph.items(): assert s.spaces[sid].rect.shared_boundary(s.setbacks_yards_courtyards[src].rect)

def test_no_window_to_internal_room_regression(states):
    for s in states:
        for o in s.opening_intents:
            if o.kind=="WINDOW": assert o.space_b_or_source in s.setbacks_yards_courtyards

def test_navigation_and_northern_bedroom(states):
    for s in states:
        assert all(x in s.free_space_navigation_graph for x in s.spaces)
        assert all(s.navigation_paths[x][-1]==s.spaces[x].rect.center for x in s.spaces)

def test_no_room_through_room(states):
    for s in states:
        bad=[r for r in s.constraint_results if r.id=="H_NO_ROOM_THROUGH_ROOM"]; assert bad[0].status=="PASS"

def test_private_zone_entry(states):
    for s in states: assert next(r for r in s.constraint_results if r.id=="H_PRIVATE_ZONE_ENTRANCE").status=="PASS"

def test_furniture_drives_acceptance(states):
    for s in states:
        assert s.furniture_use_zones
        assert all(s.spaces[f.space_id].rect.contains(f.clearance_rect) for f in s.furniture_use_zones)

def test_entrance_and_levels(states):
    for s in states:
        assert s.rules["arrival_sequence"][-1]=="ENTRY" and .36<=s.level_datums["FFL"]<=.40 and s.rules["canopy_depth_m"]==1.2

def test_spatial_operators_are_geometry_independent():
    ops=[place_adjacent("a","b"),place_near("a","b"),place_far("a","b"),place_between("a","b","c"),place_on_frontage("a","SOUTH"),place_on_valid_daylight_source("a","yard"),create_transition("a","b"),create_short_private_hall("a"),create_entry_bifurcation("a","b"),cluster_wet_spaces("a","b"),reserve_furniture_wall("a",2),create_open_connection("a","b"),create_courtyard_for("a"),reserve_parking_access_maneuver()]
    assert len({x.operator for x in ops})==14 and all(not hasattr(x,"geometry") for x in ops)

def test_negative_pattern_pruned(states): assert all("ROOM_CHAIN" not in s.pattern_provenance for s in states)

def test_cross_layer_consistency_with_scene(states):
    e=ArchitecturalDesignReasoningEngine(); v=CrossLayerConsistencyValidator()
    for s in states:
        s.drawing_scene=ArchitecturalPlanRealizer().realize(e.to_candidate_contract(s)); assert v.validate(s)["status"]=="PASS"

def test_separation_joint_only_building_exterior(states):
    e=ArchitecturalDesignReasoningEngine(); scene=ArchitecturalPlanRealizer().realize(e.to_candidate_contract(states[0]))
    assert all(p.metadata.get("edge") in {"N","E","W"} for p in scene.primitives if p.layer=="SEPARATION_JOINT")

def test_scene_has_platform_canopy_levels_and_north(states):
    e=ArchitecturalDesignReasoningEngine(); scene=ArchitecturalPlanRealizer().realize(e.to_candidate_contract(states[0]))
    assert any(p.layer=="LEVEL_MARKS" for p in scene.primitives)
    assert any(p.geometry.get("symbol")=="NORTH_ARROW" for p in scene.primitives)

def test_pdf_orientation_contract(states):
    e=ArchitecturalDesignReasoningEngine(); scene=ArchitecturalPlanRealizer().realize(e.to_candidate_contract(states[0])); assert scene.sheet=={"size":"A3","orientation":"LANDSCAPE","scale":50}

def test_human_learning_append_only(tmp_path):
    p=tmp_path/"ledger.jsonl"; r=AppendOnlyHumanLearningRegistry(p)
    base={"human_comment":"window must not face kitchen","generalized_rule":"habitable window source is legal open space only","scope":"residential","provenance":"human review 2026-09-20","negative_precedent":"internal-room-as-yard","positive_pattern":"exact source boundary proof","regression_test":"test_no_window_to_internal_room_regression"}
    r.append(base); first=p.read_bytes(); r.append(dict(base,human_comment="private zone requires explicit entrance")); assert p.read_bytes().startswith(first) and len(r.read())==2

def test_trace_is_program_trace_not_hidden_reasoning(states):
    required={"PROGRAM_REASONING","PATTERN_BEAM","TOPOLOGY","DAYLIGHT_ALLOCATION","FURNITURE_USE_PROOF","NAVIGATION_PROOF","QUALITY_EVALUATION"}
    assert all(required<={x["stage"] for x in s.trace} for s in states)
