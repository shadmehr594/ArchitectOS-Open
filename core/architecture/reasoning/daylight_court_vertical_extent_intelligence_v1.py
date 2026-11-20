"""Rule-first vertical extent alternatives for residential daylight courts."""
class DaylightCourtVerticalExtentIntelligenceV1:
 def resolve(self,court_area,lowest_residential_level,ground_program,rule_status="pending_rule_resolution"):
  return {"contract":"DaylightCourtVerticalExtentIntelligenceV1","lowest_residential_level":lowest_residential_level,"alternatives":[
   {"extent_type":"full_height_lightwell","starts_at_level":"ground","ends_at_level":"top_residential_level","ground_floor_void_area_loss":court_area,"commercial_area_loss":court_area,"parking_conflict":"requires_ground_geometry_test","natural_airflow_status":"potentially_supported","maintenance_status":"common_access_required"},
   {"extent_type":"residential_level_daylight_void","starts_at_level":lowest_residential_level,"ends_at_level":"top_residential_level","ground_floor_void_area_loss":0.0,"commercial_area_loss":0.0,"parking_conflict":"none_from_void_if_structurally_supported","natural_airflow_status":"upper_open_airflow_geometry_pending","maintenance_status":"common_access_required"}],
   "selected_extent":None,"regulatory_vertical_extent_status":rule_status,"architectural_selection_deferred_until_rule_resolution":True,"caretaker_unit_generated":False}
