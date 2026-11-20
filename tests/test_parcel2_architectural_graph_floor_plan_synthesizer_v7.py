from copy import deepcopy
import json, sys
from pathlib import Path
ROOT=Path(r"<repo-root>"); LOCAL=Path(__file__).resolve().parent; sys.path.insert(0,str(ROOT/"core/architecture/reasoning" if ROOT.exists() else LOCAL))
from parcel2_architectural_graph_floor_plan_synthesizer_v7 import ArchitecturalGraphFloorPlanSynthesizerV7,verify_topic4
SRC=ROOT/"exports/DEFAULT/parcel2_residential_room_planning_daylight_v4_20260913_131505/PARCEL2_RESIDENTIAL_ROOM_PLANNING_DAYLIGHT_V4.json"
EV=ROOT/"core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json"; PAT=ROOT/"core/architecture/knowledge/residential_floor_precedent_patterns_v1.json"
def engine(): return ArchitecturalGraphFloorPlanSynthesizerV7(json.loads(EV.read_text(encoding='utf-8')),json.loads(PAT.read_text(encoding='utf-8')))
def source(): return json.loads(SRC.read_text(encoding='utf-8'))
def plans(): return [p for _,g in engine().group(source()) for p in engine().synthesize_group(g)]
def test_authority_pipeline_graph_first():
 assert verify_topic4(json.loads(EV.read_text(encoding='utf-8')))['status']=='PASS'; p=engine().pipeline
 assert p.index('unit_zoning_graph')<p.index('graph_constrained_room_polygon_synthesis')<p.index('derive_minimal_private_circulation')
def test_deterministic_no_mutation_and_bounded_alternatives():
 data=source(); frozen=deepcopy(data); groups=engine().group(data); assert len(groups)==12
 for _,g in groups: assert engine().synthesize_group(g)==engine().synthesize_group(g) and len(engine().synthesize_group(g))==2
 assert data==frozen
def test_frame_access_rf2_and_no_spine():
 for p in plans():
  assert p['floor_envelope_resolution']['dominant_design_frame_degrees']==0 and p['floor_envelope_resolution']['frame_source']=='BUILDABLE_FLOOR_ENVELOPE'
  assert p['regression_gates']['no_longitudinal_spine_default'] and p['regression_gates']['no_equal_or_weighted_slice_then_label']
  if p['identity']['floor_id']=='RESIDENTIAL_FLOOR_2': assert len(p['units'])==2 and p['whole_floor_model']['rf2_single_sheet']
  for uid,r in p['core_common_access']['unit_reachability'].items():
   assert r['stair_chain']==[f'{uid}_THRESHOLD','COMMON_LANDING','STAIR_ACCESS']; assert r['elevator_chain']==[f'{uid}_THRESHOLD','COMMON_LANDING','ELEVATOR_ACCESS']
def test_room_validity_residual_daylight_precedent_fail_closed():
 for p in plans():
  assert p['search']['winner'] is None and not p['search']['authoritative_ranking']; assert not p['precedent_repair']['geometry_copied']
  assert p['REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN']==p['resolved_floor_hypothesis']
  for u in p['units']:
   assert u['space_organization']['circulation_derived_after_door_graph']
   for r in u['rooms']: assert r['area_m2']<=r['target_range_m2'][1]+1e-5
   for c in u['daylight_chains']: assert {'room','source','window','ratio_rule','max_depth_pass','valid'}<=set(c)
   assert u['lightwell']['created'] or u['lightwell']['polygon'] is None
