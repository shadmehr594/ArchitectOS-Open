"""Area-accounting and explicit residual classification for buildable floors."""
from shapely.geometry import Polygon
from shapely.ops import unary_union


class BuildableSpaceUtilizationIntelligenceV1:
    ALLOWED = {
        "PRIVATE_UNIT", "COMMON", "VERTICAL_CIRCULATION", "DAYLIGHT_COURT",
        "PRIVATE_TERRACE", "SERVICE", "STRUCTURAL_OR_SHAFT_RESERVATION",
        "UNALLOCATED_RESIDUAL",
    }

    def resolve(self, buildable_envelope, classified_spaces, projection_area=0.0):
        envelope = Polygon(buildable_envelope)
        spaces = []
        for item in classified_spaces:
            if item["classification"] not in self.ALLOWED - {"UNALLOCATED_RESIDUAL"}:
                raise ValueError("unsupported_space_classification")
            geometry = Polygon(item["polygon"]).intersection(envelope)
            if not geometry.is_empty:
                spaces.append({**item, "area": geometry.area, "_shape": geometry})
        allocated_shape = unary_union([x["_shape"] for x in spaces]) if spaces else Polygon()
        residual = envelope.difference(allocated_shape)
        pieces = list(residual.geoms) if residual.geom_type == "MultiPolygon" else ([] if residual.is_empty else [residual])
        usable = [g for g in pieces if g.area >= 1.0 and min(g.bounds[2]-g.bounds[0], g.bounds[3]-g.bounds[1]) >= 0.9]
        unusable = [g for g in pieces if g not in usable]
        by_type = {key: sum(x["area"] for x in spaces if x["classification"] == key) for key in self.ALLOWED}
        residual_contract = [{"classification":"UNALLOCATED_RESIDUAL", "polygon":self._poly(g), "area":g.area,
                              "usability":"usable" if g in usable else "unusable"} for g in pieces]
        unallocated = residual.area
        ratio = unallocated / envelope.area if envelope.area else 1.0
        penalties = []
        if ratio > 0.08: penalties += ["large_unallocated_buildable_area", "unusable_white_space", "space_without_programmatic_role"]
        if len(pieces) > 2: penalties.append("fragmented_residual_area")
        return {
            "contract":"BuildableSpaceUtilizationIntelligenceV1",
            "gross_buildable_floor_area":envelope.area,
            "unit_1_area":sum(x["area"] for x in spaces if x.get("space_id","").startswith("UNIT-SOUTH")),
            "unit_2_area":sum(x["area"] for x in spaces if x.get("space_id","").startswith("UNIT-NORTH")),
            "common_area":by_type["COMMON"], "stair_area":sum(x["area"] for x in spaces if x.get("space_id") == "STAIR"),
            "elevator_area":sum(x["area"] for x in spaces if x.get("space_id") == "ELEVATOR"),
            "shared_daylight_court_area":by_type["DAYLIGHT_COURT"], "terrace_area":by_type["PRIVATE_TERRACE"],
            "projection_area_if_any":projection_area, "allocated_buildable_area":allocated_shape.area,
            "unallocated_buildable_area":unallocated, "unallocated_buildable_area_ratio":ratio,
            "usable_residual_area":sum(g.area for g in usable), "unusable_residual_area":sum(g.area for g in unusable),
            "residual_fragmentation_count":len(pieces), "classified_spaces":[{k:v for k,v in x.items() if k != "_shape"} for x in spaces] + residual_contract,
            "unallocated_residual_polygons":residual_contract, "architectural_quality_penalties":penalties,
            "utilization_status":"architectural_waste_failure" if ratio > 0.08 else "explicitly_accounted",
        }

    @staticmethod
    def _poly(g):
        return [[float(x), float(y)] for x, y in list(g.exterior.coords)[:-1]]
