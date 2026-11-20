"""Deterministic, evidence-driven repair of failed pre-geometry relationships."""
from copy import deepcopy
from core.architecture.reasoning.pre_geometry_spatial_constraint_evaluator_v1 import PreGeometrySpatialConstraintEvaluatorV1

# =============================================================================
# NOT THE PRIMARY ARCHITECTOS PLAN GENERATOR.
# HouseDiffusion is the locked primary plan generator under
# HOUSE_DIFFUSION_GENERATION_POLICY_V1.
# Do not extend this branch as the normal product design path.
#
# Entrypoint: LayoutRegenerationReasonerV1.regenerate
#             (internal plan synthesis branch - re-synthesises placements)
# Enforced by core/architecture/routing/generation_policy_guard_v1.py
# =============================================================================
ARCHITECTOS_GENERATION_ROLE = "DIAGNOSTIC_OR_EXPLICIT_FALLBACK"
PRODUCTION_PRIMARY = False


class LayoutRegenerationReasonerV1:
    def __init__(self):self.evaluator=PreGeometrySpatialConstraintEvaluatorV1()
    def regenerate(self,placements,connections,buildable_boundary,protected_zones=None,max_attempts=1):
        before=self.evaluator.evaluate(placements,connections,buildable_boundary,protected_zones)
        requests=[{'request_id':f'LR-{i+1:03d}','failed_constraint':f['constraint_id'],'failure_type':'required_shared_boundary_missing',
                   'affected_spaces':f['affected_spaces'],'required_relationship':f['relationship'],'current_geometry':deepcopy(placements),
                   'floor':f['relationship'].get('floor'),'allowed_actions':['align_edge_to_target_shared_boundary'],
                   'forbidden_zones':deepcopy(protected_zones or []),'protected_spaces':[p.get('name') for p in placements if p.get('protected_zone')],
                   'preserved_spaces':[p.get('name') for p in placements if p.get('name') not in f['affected_spaces']],
                   'buildable_boundary':deepcopy(buildable_boundary),'attempt_index':0,'source_evidence':'failed_pre_geometry_constraint'}
                  for i,f in enumerate(before['failed_constraints'])]
        requests.extend({'request_id':f'LR-P{i+1:03d}','failed_constraint':f['constraint_id'],'failure_type':'privacy_violation',
                   'affected_spaces':f['affected_spaces'],'required_relationship':f['relationship'],'current_geometry':deepcopy(placements),
                   'floor':f['relationship'].get('floor'),'allowed_actions':['translate_by_explicit_privacy_clearance'],
                   'forbidden_zones':deepcopy(protected_zones or []),'protected_spaces':[p.get('name') for p in placements if p.get('protected_zone')],
                   'preserved_spaces':[p.get('name') for p in placements if p.get('name') not in f['affected_spaces']],
                   'buildable_boundary':deepcopy(buildable_boundary),'attempt_index':0,'source_evidence':'failed_pre_geometry_privacy_constraint'}
                  for i,f in enumerate(before['privacy_violations']))
        candidates=[]
        if max_attempts>0:
            for request in requests:
                a,b=request['affected_spaces']; anchor=next((p for p in placements if p.get('name')==a),None); moving=next((p for p in placements if p.get('name')==b),None)
                if not anchor or not moving or anchor.get('floor')!=moving.get('floor'):continue
                A=self.evaluator.box(anchor);w,d=moving.get('width'),moving.get('depth')
                if not A or not isinstance(w,(int,float)) or not isinstance(d,(int,float)):continue
                if request['failure_type']=='privacy_violation':
                    clearance=request['required_relationship'].get('privacy_clearance')
                    if not isinstance(clearance,(int,float)) or clearance<=0:continue
                    positions=[(A[0]-w-clearance,A[1],'privacy_left'),(A[2]+clearance,A[1],'privacy_right'),
                               (A[0],A[1]-d-clearance,'privacy_below'),(A[0],A[3]+clearance,'privacy_above')]
                else:
                    positions=[(A[0]-w,A[1],'align_left'),(A[2],A[1],'align_right'),(A[0],A[1]-d,'align_below'),(A[0],A[3],'align_above')]
                for n,(x,y,action) in enumerate(positions):
                    layout=deepcopy(placements); target=next(p for p in layout if p.get('name')==b);target['x'],target['y']=x,y
                    after=self.evaluator.evaluate(layout,connections,buildable_boundary,protected_zones)
                    feasible=not after['buildable_boundary_violations'] and not after['protected_zone_conflicts'] and not after['overlap_conflicts']
                    candidates.append({'candidate_id':f"{request['request_id']}-C{n+1}",'changed_spaces':[b],
                      'preserved_spaces':request['preserved_spaces'],'action_sequence':[{'action':action,'space':b,'anchor':a}],
                      'resulting_layout':layout,'evidence_preserved':True,'new_conflicts':after['failure_reasons'],
                      'resolved_failures':len(before['failed_constraints'])+len(before['privacy_violations'])-len(after['failed_constraints'])-len(after['privacy_violations']),
                      'unresolved_failures':[f['constraint_id'] for f in after['failed_constraints']+after['privacy_violations']],
                      'quality_score':after['quality_score'],'movement_magnitude':abs(x-float(moving['x']))+abs(y-float(moving['y'])),
                      'geometry_status':'feasible' if feasible else 'rejected'})
        feasible=[c for c in candidates if c['geometry_status']=='feasible' and c['quality_score']>before['quality_score'] and not c['unresolved_failures']]
        ranked=sorted(feasible,key=lambda c:(-c['quality_score'],c['movement_magnitude'],c['candidate_id']))
        selected=None;status='unresolved_no_feasible_layout'
        if ranked:
            best=[c for c in ranked if c['quality_score']==ranked[0]['quality_score'] and c['movement_magnitude']==ranked[0]['movement_magnitude']]
            if len(best)==1:selected=best[0];status='resolved'
            else:status='pending_tie'
        return {'status':status,'requests':requests,'candidates':candidates,'selected_candidate_id':selected['candidate_id'] if selected else None,
                'selected_layout':selected['resulting_layout'] if selected else None,'quality_score_before':before['quality_score'],
                'quality_score_after':selected['quality_score'] if selected else None,'max_attempts':max_attempts,
                'provenance':'deterministic_pre_geometry_regeneration_v1'}
