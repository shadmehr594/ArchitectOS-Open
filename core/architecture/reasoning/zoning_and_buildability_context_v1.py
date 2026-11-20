"""Current-case zoning/buildability context without citywide inference."""
from shapely.geometry import Polygon
from core.architecture.reasoning.zoning_rule_applicability_v1 import ZoningRuleApplicabilityV1

class ZoningAndBuildabilityContextV1:
    def resolve(self,site,case_definition):
        parcel=Polygon(site["parcel"]);xs=[p[0] for p in site["frontage"]]
        coverage=case_definition.get("max_site_coverage")
        far=case_definition.get("allowed_far")
        coverage_resolved=coverage is not None
        context={"parcel_area":parcel.area,"parcel_width":abs(xs[1]-xs[0]) or site.get("frontage_length"),"road_width":site.get("road_width"),
         "zoning_code":case_definition.get("zoning_code"),"urban_fabric_status":case_definition.get("urban_fabric_status","unresolved"),
         "ground_coverage_mode":case_definition.get("ground_coverage_mode") if coverage_resolved else "unresolved_human_input_required",
         "ground_coverage_percent":coverage,"allowed_far":far,
         "planning_input_status":{"allowed_far":"project_requirement" if far is not None else "unresolved_human_input_required",
          "max_site_coverage":"project_requirement" if coverage_resolved else "unresolved_human_input_required"},
         "human_input_required":[name for name,value in (("allowed_far",far),("max_site_coverage",coverage)) if value is None],
         "allowed_floor_count":case_definition.get("allowed_floor_count"),"open_space_percentage_requirement":None,
         "pilot_status":"study_not_approved","basement_status":"preserved_baseline","mixed_use_status":True,
         "special_existing_parcel_conditions":case_definition.get("special_existing_parcel_conditions",[])}
        app=ZoningRuleApplicabilityV1().evaluate("open_space_per_unit_reduced_coverage","open-space-per-unit reduced-coverage rule",
          "local_rule_exact_clause_pending_attachment",None,{"ground_coverage_mode":"reduced_coverage"},{"ground_coverage_mode":"full_coverage_100_percent"},context)
        context.update({"contract":"ZoningAndBuildabilityContextV1","open_space_per_unit_requirement":{"value":None,
         "current_case_status":"unresolved_pending_project_coverage_input" if not coverage_resolved else app["current_case_status"],
         "current_case_source":"project_case_definition" if coverage_resolved else None,"rule_applicability":app},
         "lightwell_requirement":{"current_case_status":"applicable_independently_of_site_open_space","concept":"daylight_and_ventilation_open_space"},
         "edge_context":{"south":"public_frontage_10m_road","north":"adjacent_private_parcel","west":"adjacent_private_parcel","east":"site_evidence_unresolved"},
         "rule_applicability":[app]})
        return context
