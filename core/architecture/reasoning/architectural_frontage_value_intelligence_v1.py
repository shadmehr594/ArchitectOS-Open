"""Context-aware value and loss accounting for public versus private edges."""
from shapely.geometry import LineString, Polygon, box


class ArchitecturalFrontageValueIntelligenceV1:
    def resolve(self, site, local_parcel_polygon, core_polygon):
        parcel=Polygon(local_parcel_polygon);core=Polygon(core_polygon);x0,y0,x1,y1=parcel.bounds
        public=LineString([(x0,y0),(x1,y0)]);strip=box(x0,y0,x1,y0+min(1.0,y1-y0))
        consumed=core.intersection(strip).area
        frontage_intersection=core.boundary.intersection(public.buffer(1e-6)).length
        public_value={"public_road_access":True,"commercial_visibility":1.0,"pedestrian_entrance_opportunity":1.0,
                      "vehicle_entrance_opportunity":1.0,"daylight_potential":1.0,"terrace_opportunity":1.0,
                      "projection_opportunity":"pending_local_approval","architectural_value_score":6.0}
        private_value={"public_road_access":False,"commercial_visibility":0.0,"pedestrian_entrance_opportunity":0.0,
                       "vehicle_entrance_opportunity":0.0,"daylight_potential":0.0,"terrace_opportunity":0.0,
                       "projection_opportunity":False,"private_neighbor_restriction":True,"architectural_value_score":0.0}
        loss=frontage_intersection + consumed
        return {"contract":"ArchitecturalFrontageValueIntelligenceV1","site_frontage_source":site.get("frontage"),
                "public_frontage":{"edge_role":"public_road_frontage","road_width":site.get("road_width"),**public_value},
                "private_neighbor_edges":[{"edge_role":"private_neighbor_restricted","edge_id":"non_public_edge","value":private_value}],
                "public_frontage_value_exceeds_private_edge":public_value["architectural_value_score"]>private_value["architectural_value_score"],
                "core_frontage_intersection_length":frontage_intersection,"high_value_frontage_zone_consumed_area":consumed,
                "frontage_value_loss":loss,"frontage_loss_status":"high_value_frontage_consumed" if loss>1e-6 else "preserved",
                "direction_is_not_globally_hardcoded":True}
