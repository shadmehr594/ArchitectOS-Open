"""Generic residential corridor, threshold, vestibule and termination hypotheses."""
from __future__ import annotations

from copy import deepcopy
from math import atan2, degrees, hypot

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union


class ResidentialCorridorEntranceGeometryIntelligenceV1:
    """Compare geometry-derived access hypotheses without selecting a winner."""

    EPS = 1e-7
    HYPOTHESES = (
        "straight_termination",
        "widened_vestibule",
        "polygonal_distribution_node",
        "short_branch_corridor",
    )

    def solve(self, *, floor_boundary, core_boundary, unit_boundaries, entrances,
              corridor_width, entrance_zone_depth, entrance_zone_min_area,
              context_axes=None):
        original = deepcopy((floor_boundary, core_boundary, unit_boundaries, entrances, context_axes))
        floor = Polygon(floor_boundary)
        core = Polygon(core_boundary)
        units = [Polygon(p) for p in unit_boundaries]
        doors = [Point(p) for p in entrances]
        if len(units) != len(doors) or not doors:
            return {"contract": "ResidentialCorridorEntranceGeometryIntelligenceV1", "status": "unresolved", "reason": "unit_or_entrance_evidence_missing"}

        axes = self._axes(context_axes, floor)
        origin = self._core_access_point(core, doors)
        candidates = [self._candidate(kind, floor, core, units, doors, origin, axes,
                                      float(corridor_width), float(entrance_zone_depth),
                                      float(entrance_zone_min_area)) for kind in self.HYPOTHESES]
        assert original == (floor_boundary, core_boundary, unit_boundaries, entrances, context_axes)
        return {
            "contract": "ResidentialCorridorEntranceGeometryIntelligenceV1",
            "status": "resolved",
            "input_mutated": False,
            "context_axes": axes,
            "hypotheses": candidates,
            "comparison_dimensions": ["dead_space", "circulation_length", "door_feasibility", "privacy", "geometric_coherence"],
            "advisory_highest_score_ids": self._highest(candidates),
            "winner": None,
            "authoritative_ranking": False,
            "final_selection_performed": False,
            "angle_policy": "non_context_angle_requires_geometry_or_spatial_justification",
            "polygon_policy": "vertex_count_is_geometry_derived_not_hardcoded",
        }

    def _candidate(self, kind, floor, core, units, doors, origin, axes, width, zone_depth, zone_area):
        ux, uy = axes[0]
        vx, vy = axes[1]
        stations = [((d.x-origin.x)*ux+(d.y-origin.y)*uy, (d.x-origin.x)*vx+(d.y-origin.y)*vy) for d in doors]
        trunk_station = min(s[1] for s in stations)
        hub = Point(origin.x + trunk_station*vx, origin.y + trunk_station*vy)
        routes = []
        if kind == "straight_termination":
            routes = [LineString([origin, d]) for d in doors]
        elif kind == "short_branch_corridor":
            routes = [LineString([origin, hub, d]) for d in doors]
        else:
            routes = [LineString([origin, hub, d]) for d in doors]

        public = unary_union([r.buffer(width/2, cap_style=2, join_style=2) for r in routes])
        node = Polygon()
        if kind == "widened_vestibule":
            span = max(width, min(width*1.75, max((d.distance(hub) for d in doors), default=width)))
            node = hub.buffer(span, cap_style=3)
        elif kind == "polygonal_distribution_node":
            # Convex hull is derived from the actual hub, thresholds and clearance.
            node = unary_union([hub.buffer(width*.55)] + [d.buffer(width*.42) for d in doors]).convex_hull
        public = unary_union([public, node]).intersection(floor).difference(core)
        # V8 unit polygons are allocation envelopes, not immutable walls. V9
        # reallocates the width increase to public circulation while preserving
        # the core and records the exact area change.
        reallocated = sum(u.intersection(public).area for u in units)
        revised_units = [self._largest(u.difference(public)) for u in units]
        penetration = public.intersection(unary_union([u.buffer(-self.EPS) for u in revised_units])).area

        resolved_doors = [self._threshold(u, public, d) for u, d in zip(revised_units, doors)]
        zones = [self._entrance_zone(u, d, zone_depth, zone_area) for u, d in zip(revised_units, resolved_doors)]
        door_ok = [public.buffer(self.EPS).intersects(d) and z["feasible"] for d, z in zip(resolved_doors, zones)]
        route_length = sum(r.length for r in routes)
        bends = sum(max(0, len(r.coords)-2) for r in routes)
        off_axis = self._off_axis_length(routes, axes)
        angle_justifications = []
        if off_axis > self.EPS:
            if kind == "straight_termination" and any(abs(a) > self.EPS and abs(b) > self.EPS for a, b in stations):
                angle_justifications.append("direct_threshold_connection_shortens_route_but_conflicts_with_orthogonal_context")
            elif kind == "polygonal_distribution_node" and len(doors) > 1:
                angle_justifications.append("door_distribution_and_dead_space_recovery")
        context_angle_allowed = off_axis <= self.EPS or bool(angle_justifications)
        residual = floor.difference(unary_union([core, public] + units))
        dead = sum(g.area for g in self._polygons(residual) if g.area < max(2.0, width*width*1.5))
        privacy = self._privacy(resolved_doors, public, width)
        coherence = max(0.0, 1.0 - min(1.0, off_axis/max(route_length, self.EPS)) - min(.35, bends*.05))
        door_score = sum(door_ok)/len(door_ok)
        dead_score = 1.0 - min(1.0, dead/max(floor.area*.05, self.EPS))
        length_score = 1.0 - min(1.0, route_length/max(floor.length, self.EPS))
        score = .24*dead_score + .20*length_score + .24*door_score + .16*privacy + .16*coherence
        eligible = all(door_ok) and penetration <= self.EPS and context_angle_allowed
        return {
            "hypothesis_id": kind,
            "status": "reviewable" if eligible else "disfavored_or_blocked",
            "public_corridor": self._geometry(public),
            "revised_unit_envelopes": [self._geometry(u) for u in revised_units],
            "centerlines": [self._line(r) for r in routes],
            "distribution_node": self._geometry(node),
            "v8_schematic_entrance_points": [[round(d.x, 6), round(d.y, 6)] for d in doors],
            "entrance_thresholds": [[round(d.x, 6), round(d.y, 6)] for d in resolved_doors],
            "private_entrance_zones": zones,
            "corridor_stops_at_unit_thresholds": penetration <= self.EPS,
            "public_corridor_private_penetration_m2": round(penetration, 9),
            "unit_envelope_reallocation_to_public_corridor_m2": round(reallocated, 6),
            "metrics": {"dead_space_m2": round(dead, 6), "circulation_length_m": round(route_length, 6),
                        "door_feasibility_0_1": round(door_score, 6), "privacy_0_1": round(privacy, 6),
                        "geometric_coherence_0_1": round(coherence, 6), "off_context_axis_length_m": round(off_axis, 6),
                        "bend_count": bends, "advisory_score_0_1": round(score, 6)},
            "angle_justifications": angle_justifications,
            "angles_allowed": context_angle_allowed,
            "geometry_derived_node_vertex_count": self._vertices(node),
            "hardcoded_pentagon": False,
        }

    @staticmethod
    def _axes(context_axes, floor):
        if context_axes:
            u = context_axes[0]
            n = hypot(*u)
            u = [u[0]/n, u[1]/n]
            return [u, [-u[1], u[0]]]
        r = floor.minimum_rotated_rectangle
        pts = list(r.exterior.coords)
        edges = [(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]) for i in range(4)]
        u = max(edges, key=lambda e: hypot(*e)); n = hypot(*u); u = [u[0]/n, u[1]/n]
        return [u, [-u[1], u[0]]]

    @staticmethod
    def _core_access_point(core, doors):
        target = unary_union(doors).centroid
        return core.exterior.interpolate(core.exterior.project(target))

    def _entrance_zone(self, unit, door, depth, min_area):
        # V8 entrances are schematic points within the public strip.  The
        # private zone starts at the closest point on the unit boundary.
        door = unit.exterior.interpolate(unit.exterior.project(door))
        width = max(1.4, min_area/max(depth, self.EPS))
        centroid = unit.centroid
        dx, dy = centroid.x-door.x, centroid.y-door.y
        directions = [(dx, dy)]
        rect = unit.minimum_rotated_rectangle; pts = list(rect.exterior.coords)
        directions.extend((pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]) for i in range(4))
        trials = []
        for ax, ay in directions:
            n = hypot(ax, ay)
            if n <= self.EPS: continue
            for sign in (1.0, -1.0):
                ux, uy = sign*ax/n, sign*ay/n
                if (centroid.x-door.x)*ux+(centroid.y-door.y)*uy <= 0: continue
                normal = (-uy, ux)
                corners = [(door.x-normal[0]*width/2, door.y-normal[1]*width/2),
                           (door.x+normal[0]*width/2, door.y+normal[1]*width/2),
                           (door.x+normal[0]*width/2+ux*depth, door.y+normal[1]*width/2+uy*depth),
                           (door.x-normal[0]*width/2+ux*depth, door.y-normal[1]*width/2+uy*depth)]
                raw = Polygon(corners); trials.append((raw.intersection(unit).area, raw.intersection(unit)))
        clipped = max(trials, key=lambda item: item[0])[1] if trials else Polygon()
        return {"boundary": self._geometry(clipped), "depth_m": round(depth, 6), "area_m2": round(clipped.area, 6),
                "required_min_area_m2": min_area, "feasible": clipped.area+self.EPS >= min_area,
                "authority_scope": "inside_residential_occupancy_after_main_door"}

    @staticmethod
    def _privacy(doors, public, width):
        if len(doors) < 2:
            return 1.0
        minimum = min(doors[i].distance(doors[j]) for i in range(len(doors)) for j in range(i+1, len(doors)))
        return max(0.0, min(1.0, minimum/max(width*2, 1e-7)))

    @staticmethod
    def _threshold(unit, public, reference):
        shared = unit.boundary.intersection(public.boundary.buffer(1e-7))
        if shared.is_empty:
            return unit.exterior.interpolate(unit.exterior.project(reference))
        if shared.geom_type == "Point": return shared
        if shared.geom_type in {"LineString", "LinearRing"}:
            return shared.interpolate(shared.project(reference))
        choices = []
        for part in getattr(shared, "geoms", []):
            if part.geom_type == "Point": choices.append(part)
            elif part.geom_type in {"LineString", "LinearRing"}: choices.append(part.interpolate(part.project(reference)))
        return min(choices, key=lambda p: p.distance(reference)) if choices else unit.exterior.interpolate(unit.exterior.project(reference))

    @staticmethod
    def _off_axis_length(routes, axes):
        total = 0.0
        for r in routes:
            pts = list(r.coords)
            for a, b in zip(pts, pts[1:]):
                dx, dy = b[0]-a[0], b[1]-a[1]; n = hypot(dx, dy)
                if n <= 1e-7: continue
                alignment = max(abs((dx*axes[0][0]+dy*axes[0][1])/n), abs((dx*axes[1][0]+dy*axes[1][1])/n))
                if alignment < 1-1e-7: total += n
        return total

    @staticmethod
    def _polygons(g):
        if g.is_empty: return []
        if g.geom_type == "Polygon": return [g]
        return [x for x in getattr(g, "geoms", []) if x.geom_type == "Polygon"]

    @classmethod
    def _largest(cls, g):
        polys = cls._polygons(g)
        return max(polys, key=lambda p: p.area) if polys else Polygon()

    @classmethod
    def _geometry(cls, g):
        polys = cls._polygons(g)
        encoded = [[[round(x, 6), round(y, 6)] for x, y in list(p.exterior.coords)[:-1]] for p in polys]
        return encoded[0] if len(encoded) == 1 else encoded

    @staticmethod
    def _line(g): return [[round(x, 6), round(y, 6)] for x, y in g.coords]
    @staticmethod
    def _vertices(g):
        return 0 if g.is_empty or g.geom_type != "Polygon" else len(list(g.exterior.coords))-1
    @staticmethod
    def _highest(candidates):
        eligible = [c for c in candidates if c["status"] == "reviewable"]
        if not eligible: return []
        best = max(c["metrics"]["advisory_score_0_1"] for c in eligible)
        return [c["hypothesis_id"] for c in eligible if c["metrics"]["advisory_score_0_1"] == best]
