"""Source-aware Minab residential rules used by the current study."""


class MinabResidentialArchitecturalRulesV1:
    DOCUMENT = "طرح تفصیلی شهر میناب، جلد 4 — ضوابط و مقررات، بهار 1400"

    def resolve(self):
        return {"contract":"MinabResidentialArchitecturalRulesV1","source_document":self.DOCUMENT,
                "source_document_attachment_status":"exact_document_not_present_in_current_repository_or_task_attachment",
                "rules":{
         "main_space_lightwell_min_area":self._rule(12.0,"m2","daylight of principal residential spaces; exact_page_reference_pending_source_attachment",{"building_floor_count_max":5}),
         "main_space_lightwell_min_width":self._rule(3.0,"m","daylight of principal residential spaces; exact_page_reference_pending_source_attachment",{"building_floor_count_max":5}),
         "kitchen_lightwell_min_area":self._rule(6.0,"m2","kitchen-only daylight; exact_page_reference_pending_source_attachment",{"space_use":"kitchen_only"}),
         "kitchen_lightwell_min_width":self._rule(2.0,"m","kitchen-only daylight; exact_page_reference_pending_source_attachment",{"space_use":"kitchen_only"}),
         "central_lightwell_natural_airflow_required":self._rule(True,"boolean","central lightwell natural airflow; exact_page_reference_pending_source_attachment",{"lightwell_type":"central"}),
         "adjacent_property_opening_prohibited":self._rule(True,"boolean","openings toward adjacent private property; exact_page_reference_pending_source_attachment",{"edge_adjacency":"private_property"}),
         "adjacent_property_balcony_prohibited":self._rule(True,"boolean","balconies toward adjacent private property; exact_page_reference_pending_source_attachment",{"edge_adjacency":"private_property"}),
         "public_road_upper_floor_daylight_allowed":self._pending("upper-floor daylight toward public road"),
         "opposing_independent_unit_windows_min_distance":self._rule(3.0,"m","opposing windows of independent units at shared lightwell; exact_page_reference_pending_source_attachment",{"opposing_openings":True,"independent_units":True}),
         "opposing_unit_windows_privacy_height":self._rule(1.70,"m","privacy-sensitive opening installation height; exact_page_reference_pending_source_attachment",{"opposing_openings":True,"independent_units":True},status="authoritative_clause_semantic_normalization_required"),
         "projection_public_road_min_clear_height":self._rule(3.50,"m","public-road projection clear height; exact_page_reference_pending_source_attachment",{"projection_context":"public_road"},{"local_approval_required":True}),
         "projection_public_road_10_20m_max_width":self._rule(0.80,"m","10–20 m road projection category; exact_page_reference_pending_source_attachment",{"jurisdiction":"Minab","road_width_category":"10_to_20m"},{"exact_10m_boundary_interpretation":True,"local_approval_required":True}),
         "projection_public_road_over_20m_variants":{"value":[1.00,1.20],"unit":"m","jurisdiction":"Minab","source_document":self.DOCUMENT,"source_page_or_section":"multiple public-road projection clauses; exact pages pending source attachment","applicability_conditions":{"road_width":"over_20m"},"approval_conditions":{"technical_committee_for_1_20_variant":True},"rule_status":"requires_clause_applicability_resolution"},
         "projection_inside_property_max_width":self._rule(1.20,"m","inside-property projection; exact_page_reference_pending_source_attachment",{"projection_context":"inside_property"}),
         "projection_inside_property_min_clear_height":self._rule(2.70,"m","inside-property projection clear height; exact_page_reference_pending_source_attachment",{"projection_context":"inside_property"}),
         "mixed_use_independent_access_requirement":self._pending("mixed-use independent access"),
         "balcony_terrace_far_calculation_rules":self._pending("balcony/terrace FAR calculation"),
        }}

    def _rule(self,value,unit,section,conditions,approval=None,status="authoritative_value_page_reference_pending_attachment"):
        return {"value":value,"unit":unit,"jurisdiction":"Minab","source_document":self.DOCUMENT,"source_page_or_section":section,
                "applicability_conditions":conditions,"approval_conditions":approval or {},"rule_status":status}
    def _pending(self,section):
        return {"value":None,"unit":None,"jurisdiction":"Minab","source_document":self.DOCUMENT,"source_page_or_section":f"{section}; exact clause not present in current attachment",
                "applicability_conditions":{},"approval_conditions":{},"rule_status":"pending_rule_resolution"}
