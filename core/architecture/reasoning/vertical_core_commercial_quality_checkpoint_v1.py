from copy import deepcopy
from shapely.geometry import Polygon
from core.architecture.reasoning.commercial_spatial_quality_evaluation_v1 import CommercialSpatialQualityEvaluationV1
from core.architecture.reasoning.whole_building_architectural_tradeoff_advisor_v1 import WholeBuildingArchitecturalTradeoffAdvisorV1

class VerticalCoreCommercialQualityCheckpointV1:
 def resolve(self,usability_contract,clear_face,ramp_polygon):
  clear=clear_face if isinstance(clear_face,Polygon) else Polygon(clear_face);ramp=ramp_polygon if isinstance(ramp_polygon,Polygon) else Polygon(ramp_polygon);ev=CommercialSpatialQualityEvaluationV1();candidates=[]
  for source in usability_contract['candidates']:
   c=deepcopy(source);q=ev.evaluate(c,clear);c['commercial_spatial_quality']=q;c['architecture_selection_status']='quality_valid' if q['architectural_quality_status']=='quality_valid' else 'valid_geometry_but_commercial_quality_failed';candidates.append(c)
  current_id=usability_contract['selected_candidate']['candidate_id'];current=next(c for c in candidates if c['candidate_id']==current_id);current['human_review_status']='rejected_commercial_architectural_quality';current['diagnostic_counterexample_preserved']=True
  def score(c):
   q=c['commercial_spatial_quality'];return (-len(q['architectural_quality_failures']),-q['neck_and_tail']['tail_area_ratio'],round(q['neck_width'],4),q['usable_rectangular_field_area'],q['commercial_space_compactness'],q['effective_storefront_width'],q['commercial_total_area'],-c['ground_floor']['corridor_length'])
  best=max(candidates,key=score);quality_valid=[c for c in candidates if c['commercial_spatial_quality']['architectural_quality_status']=='quality_valid'];selected=max(quality_valid,key=score) if quality_valid else None;advisor=WholeBuildingArchitecturalTradeoffAdvisorV1().advise(current,current['commercial_spatial_quality'],ramp.area)
  return {'contract':'VerticalCoreCommercialQualityCheckpointV1','source_contract':usability_contract['contract'],'current_rejected_candidate_id':current_id,'current_diagnostic_counterexample':current,'candidate_count':len(candidates),'quality_valid_count':len(quality_valid),'candidates':candidates,'best_local_commercial_quality_candidate':best,'selected_candidate':selected,'architecture_selection_status':'candidate_found' if selected else 'no_architecturally_quality_valid_local_candidate','whole_building_tradeoff_advisor':advisor,'ranking_priority':['usable_main_commercial_field','frontage_quality','absence_of_narrow_necks','absence_of_rear_tails','compactness','largest_inscribed_usable_field','commercial_area','corridor_efficiency'],'area_only_ranking':False,'renderer_authority':'production_contract_only','program_changed':False,'basement_decision_changed':False,'human_decision_required':True}
