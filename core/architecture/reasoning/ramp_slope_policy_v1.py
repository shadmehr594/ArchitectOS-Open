class RampSlopePolicyV1:
    """Separates regulatory permission from geometry and ranking."""
    def resolve(self,parking_class,regulation_context):
        allowed=[];evidence=[]
        small_private_covered=(regulation_context.get('small_private_covered_parking') is True or regulation_context.get('parking_use')=='small_private_covered_parking')
        if parking_class=='small' and small_private_covered and regulation_context.get('project_allows_17_percent'):
            allowed=[.15,.16,.17];evidence.append('active_project_small_private_parking_slope_envelope')
        elif regulation_context.get('explicit_maximum_slope') is not None:
            cap=float(regulation_context['explicit_maximum_slope']);allowed=[s for s in (.15,.16,.17) if s<=cap+1e-9];evidence.append('explicit_regulation_maximum_slope')
        else:
            allowed=[.15];evidence.append('fail_closed_default_without_17_percent_authority')
        transitions={s:{'required':s>.16,'entry_length':1.0 if s>.16 else 0.0,'exit_length':1.0 if s>.16 else 0.0,'transition_grade':s/2 if s>.16 else s,'source':'active_project_transition_policy' if s>.16 else 'not_required'} for s in allowed}
        return {'contract':'RampSlopePolicyResult','parking_class':parking_class,'regulation_context':regulation_context,
            'preferred_slope':.15,'allowed_max_slope':max(allowed),'slope_candidates':allowed,
            'transition_requirements':transitions,'evidence':evidence,'global_17_percent_enable':False}
