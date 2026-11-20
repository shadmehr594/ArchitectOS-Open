"""Jurisdiction- and user-gated projection opportunities."""
class ProjectionAndOverhangOpportunityIntelligenceV1:
 def resolve(self,jurisdiction,road_width,rules,preferences,underside_projection_elevation=None,road_reference_elevation=0.0,ground_coverage_mode=None):
  allowed=bool(preferences.get("allow_public_road_projection",False));min_h=rules["rules"]["projection_public_road_min_clear_height"]["value"] if jurisdiction=="Minab" else None
  clearance=None if underside_projection_elevation is None else underside_projection_elevation-road_reference_elevation
  vertical="vertical_clearance_unresolved" if clearance is None else "vertical_clearance_passed" if clearance>=min_h else "vertical_clearance_failed"
  exact10=abs(float(road_width)-10.0)<1e-6 if road_width is not None else False
  applicable=jurisdiction=="Minab" and allowed
  status="projection_disabled_by_user" if not allowed else "not_applicable_outside_jurisdiction" if jurisdiction!="Minab" else "pending_exact_boundary_condition_and_local_approval_interpretation" if exact10 else "candidate_pending_local_approval_and_applicability"
  width=.8 if applicable and road_width is not None and 10<=road_width<=20 else None
  return {"contract":"ProjectionAndOverhangOpportunityIntelligenceV1","jurisdiction":jurisdiction,"road_width":road_width,"user_allows_projection":allowed,
   "no_projection_fallback_available":True,"public_road_projection":{"projection_width":width,"projection_status":status,"projection_applicability_status":status,"minimum_clear_height":min_h,
    "underside_projection_elevation":underside_projection_elevation,"road_reference_elevation":road_reference_elevation,"actual_clear_height":clearance,"projection_geometry_status":vertical,
    "approval_requirement":"local_approval_and_clause_applicability_resolution","rule_source":rules["source_document"] if jurisdiction=="Minab" else None},
   "inside_property_projection":{"maximum_width":rules["rules"]["projection_inside_property_max_width"]["value"] if jurisdiction=="Minab" else None,"minimum_clear_height":rules["rules"]["projection_inside_property_min_clear_height"]["value"] if jurisdiction=="Minab" else None,
    "status":"conditional_infrastructure_not_applied_current_100_percent_case" if ground_coverage_mode=="full_coverage_100_percent" else "pending_context_validation"},
   "over_20m_rule_variants":rules["rules"]["projection_public_road_over_20m_variants"] if jurisdiction=="Minab" else None,"conditional_architectural_opportunity":applicable and vertical!="vertical_clearance_failed"}
