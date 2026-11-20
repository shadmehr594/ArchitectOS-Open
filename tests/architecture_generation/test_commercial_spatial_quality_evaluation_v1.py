import json
from pathlib import Path
from shapely.geometry import Polygon
from core.architecture.reasoning.vertical_core_commercial_quality_checkpoint_v1 import VerticalCoreCommercialQualityCheckpointV1
ROOT=Path(__file__).resolve().parents[2]
def result():
 p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/vertical_core_architectural_usability_v3_*/PARCEL2_VERTICAL_CORE_ARCHITECTURAL_USABILITY_V3.json'))[-1];v=json.loads(p.read_text());return VerticalCoreCommercialQualityCheckpointV1().resolve(v,Polygon(v['context_geometry']['clear_face']),Polygon(v['context_geometry']['ramp']))
def test_current_candidate_preserved_as_human_rejected_counterexample():
 r=result();c=r['current_diagnostic_counterexample'];assert c['candidate_id']=='VC-LA2-006-3.586' and c['geometry_status']=='hard_valid';assert c['human_review_status']=='rejected_commercial_architectural_quality';assert c['diagnostic_counterexample_preserved']
def test_quality_is_polygon_based_and_not_area_only():
 r=result();q=r['current_diagnostic_counterexample']['commercial_spatial_quality'];assert q['geometry_source']=='production_commercial_space_polygons';assert q['commercial_total_area']>100;assert q['architectural_quality_status']=='quality_failed';assert not r['area_only_ranking']
def test_neck_tail_and_shape_metrics_exist():
 q=result()['current_diagnostic_counterexample']['commercial_spatial_quality'];assert q['neck_and_tail']['detected'];assert q['neck_width']>0 and q['neck_length']>0;assert q['rear_area_reachable_only_through_narrow_neck']>0;assert q['usable_rectangular_field_area']>0;assert q['commercial_space_compactness']>0
def test_ranking_prioritizes_quality_before_area():
 r=result();assert r['ranking_priority'][-2:] == ['commercial_area','corridor_efficiency'];assert r['best_local_commercial_quality_candidate']['commercial_spatial_quality']
def test_advisor_is_evidence_based_and_non_mutating():
 a=result()['whole_building_tradeoff_advisor'];assert a['measured_evidence_supports_tradeoff_advisory'];assert a['human_decision_required'];assert not a['program_changed'] and not a['basement_deleted'] and not a['ground_floor_parking_designed'];assert a['scenario_b']['parking_capacity']=='not_generated_first_order_advisory_only'
def test_no_structure_bim_ifc_or_redesign():
 r=result();s=json.dumps(r);assert r['program_changed'] is False and r['basement_decision_changed'] is False;assert 'physical_ramp_published' not in s
