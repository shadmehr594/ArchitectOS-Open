"""Geometric privacy separation between a shared court and private terraces."""
from shapely.geometry import LineString, Polygon


class SharedCourtTerracePrivacySeparationV1:
    def resolve(self, court_polygon, unit_polygons, terraces, maintenance, rules,
                wall_thickness=0.12, wall_start_level=0.0, wall_end_level=None):
        court = Polygon(court_polygon)
        units = [Polygon(p) for p in unit_polygons]
        served = [u.boundary.intersection(court.boundary).length > 0.1 for u in units]
        case = "CASE_A_SHARED_BY_BOTH_UNITS" if all(served) else "CASE_B_SINGLE_UNIT_COURT"
        bordering = []
        for terrace in terraces:
            shape = Polygon(terrace["terrace_polygon"]) if terrace.get("terrace_polygon") else Polygon()
            if not shape.is_empty and shape.boundary.intersection(court.boundary).length > 0.1:
                bordering.append((terrace, shape))
        required = case.startswith("CASE_A") and bool(bordering)
        conflict = required and all(served)
        centerline = None
        wall = Polygon()
        if conflict:
            shared = bordering[0][1].boundary.intersection(court.boundary)
            lines = [shared] if shared.geom_type == "LineString" else [g for g in getattr(shared, "geoms", []) if g.geom_type == "LineString"]
            if lines:
                source = max(lines, key=lambda g:g.length)
                length = min(source.length, max(0.8, source.length * 0.45))
                mid = source.interpolate(source.length / 2)
                a = source.interpolate(max(0, source.length/2-length/2)); b = source.interpolate(min(source.length, source.length/2+length/2))
                centerline = LineString([a, mid, b]); wall = centerline.buffer(wall_thickness/2, cap_style=2).intersection(court)
        clear = court.difference(wall)
        primary = max(clear.geoms, key=lambda g:g.area) if clear.geom_type == "MultiPolygon" else clear
        width = min(primary.bounds[2]-primary.bounds[0], primary.bounds[3]-primary.bounds[1]) if not primary.is_empty else 0
        min_area = rules["rules"]["main_space_lightwell_min_area"]["value"]
        min_width = rules["rules"]["main_space_lightwell_min_width"]["value"]
        area_ok, width_ok = clear.area + 1e-6 >= min_area, width + 1e-6 >= min_width
        airflow = "credible_open_court_flow" if not wall.is_empty and not wall.crosses(court) and area_ok and width_ok else "unchanged_no_divider" if not required else "airflow_failure"
        daylight_edges = [u.boundary.intersection(clear.boundary).length for u in units]
        maintenance_ok = maintenance.get("maintenance_source") == "COMMON" and not maintenance.get("private_unit_crossing", True)
        accepted = required and not wall.is_empty and area_ok and width_ok and airflow != "airflow_failure" and all(x > 0.1 for x in daylight_edges) and maintenance_ok
        failures = []
        if required and not area_ok: failures.append("lightwell_area_failure")
        if required and not width_ok: failures.append("lightwell_width_failure")
        if required and airflow == "airflow_failure": failures.append("airflow_failure")
        if required and not all(x > 0.1 for x in daylight_edges): failures.append("daylight_failure")
        if required and not maintenance_ok: failures.append("maintenance_access_failure")
        return {
            "contract":"SharedCourtTerracePrivacySeparationV1", "privacy_case":case,
            "privacy_divider_required":required, "privacy_conflict_detected":conflict,
            "privacy_wall_centerline":self._line(centerline), "privacy_wall_polygon":self._poly(wall),
            "privacy_wall_thickness":wall_thickness if required else None,
            "privacy_wall_thickness_source":"engineering_assumption" if required else None,
            "regulatory_status":"pending_rule_resolution" if required else "not_applicable",
            "privacy_wall_height":None if wall_end_level is None else wall_end_level-wall_start_level,
            "privacy_wall_start_level":wall_start_level if required else None, "privacy_wall_end_level":wall_end_level if required else None,
            "clear_daylight_court_polygon":self._poly(primary), "clear_daylight_court_area":clear.area,
            "clear_daylight_court_min_width":width, "natural_airflow_status":airflow,
            "useful_daylight_edges_after_wall":daylight_edges, "maintenance_access_remains_common":maintenance_ok,
            "divider_topology_status":"accepted" if accepted else "not_required" if not required else "rejected",
            "failure_reasons":failures,
            "alternative_privacy_strategies":[] if accepted or not required else ["offset_terrace", "staggered_terrace", "partial_visual_barrier", "alternative_daylight_court_relationship"],
            "final_windows_generated":False,
        }

    @staticmethod
    def _poly(g):
        return [] if g.is_empty else [[float(x),float(y)] for x,y in list(g.exterior.coords)[:-1]]
    @staticmethod
    def _line(g):
        return [] if g is None or g.is_empty else [[float(x),float(y)] for x,y in g.coords]
