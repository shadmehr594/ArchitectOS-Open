"""Program meaningful residual polygons without inventing regulations."""
from shapely.geometry import Polygon, box
from shapely.ops import unary_union


class ResidualSpaceProgramAllocatorV1:
    EPS = 1e-6

    def resolve(self, parcel, occupied, priorities, preferences):
        parcel = Polygon(parcel)
        occupied_union = unary_union([Polygon(p) for p in occupied if p])
        residual = parcel.difference(occupied_union)
        meaningful = [p for p in self._parts(residual) if p.area >= 1.0]
        available = unary_union(meaningful)
        allocations = []
        storage_count = 0
        wc_generated = False
        for use in priorities:
            if use == "storage" and preferences.get("require_residential_storage", False):
                for index in range(2):
                    shape = self._place_rectangle(available, 2.0, 2.5)
                    if shape is None:
                        break
                    allocations.append(self._allocation(f"storage_unit_{index+1:02d}", "residential_storage", shape,
                                                        "user_design_requirement_max_6.0_m2_per_unit"))
                    available = available.difference(shape)
                    storage_count += 1
            elif use == "wc" and preferences.get("require_common_wc", False) and not wc_generated:
                shape = self._place_rectangle(available, 1.5, 1.8)
                if shape is not None:
                    allocations.append(self._allocation("common_wc_01", "common_wc", shape,
                                                        "engineering_space_search_pending_rule_resolution"))
                    available = available.difference(shape)
                    wc_generated = True
            elif use == "commercial":
                anchor = Polygon(preferences["commercial_anchor"]) if preferences.get("commercial_anchor") else None
                for index, shape in enumerate(self._parts(available)):
                    touches_anchor = anchor is None or shape.buffer(self.EPS).intersects(anchor)
                    if shape.area >= 2.0 and touches_anchor:
                        allocations.append(self._allocation(f"commercial_extension_{index+1:02d}", "commercial", shape,
                                                            "residual_program_reallocation"))
                available = available.difference(unary_union([Polygon(a["polygon"]) for a in allocations
                                                               if a["program"] == "commercial"]))
        unallocated = self._parts(available)
        by_program = {name: sum(a["area"] for a in allocations if a["program"] == name)
                      for name in ("parking", "residential_storage", "common_wc", "commercial")}
        return {
            "contract": "ResidualSpaceProgramAllocatorV1",
            "residual_area_total": sum(p.area for p in meaningful),
            "allocations": allocations,
            "residential_storage_count": storage_count,
            "residential_storage_total_area": by_program["residential_storage"],
            "residential_storage_max_area_per_unit": 6.0,
            "residential_storage_constraint_source": "user_design_requirement",
            "common_wc_generated": wc_generated,
            "common_wc_regulatory_status": "pending_rule_resolution" if wc_generated else "not_generated",
            "residual_area_allocated_to_parking": by_program["parking"],
            "residual_area_allocated_to_storage": by_program["residential_storage"],
            "residual_area_allocated_to_wc": by_program["common_wc"],
            "residual_area_allocated_to_commercial": by_program["commercial"],
            "unallocated_residual_polygons": [self._poly(p) for p in unallocated],
            "unallocated_residual_area": sum(p.area for p in unallocated),
        }

    def _place_rectangle(self, geometry, width, depth):
        for region in sorted(self._parts(geometry), key=lambda p: p.area, reverse=True):
            x0, y0, x1, y1 = region.bounds
            for w, d in ((width, depth), (depth, width)):
                for x in (x0, x1-w):
                    for y in (y0, y1-d):
                        candidate = box(x, y, x+w, y+d)
                        if region.buffer(self.EPS).covers(candidate):
                            return candidate
        return None

    @staticmethod
    def _parts(geometry):
        if geometry.is_empty:
            return []
        if geometry.geom_type == "Polygon":
            return [geometry]
        return [p for p in getattr(geometry, "geoms", []) if p.geom_type == "Polygon"]

    @staticmethod
    def _allocation(identifier, program, polygon, source):
        return {"space_id": identifier, "program": program,
                "polygon": ResidualSpaceProgramAllocatorV1._poly(polygon), "area": polygon.area, "source": source}

    @staticmethod
    def _poly(polygon):
        return [[float(x), float(y)] for x, y in list(polygon.exterior.coords)[:-1]]
