"""Generic architecture-only reasoning about geometry as a spatial design instrument."""
from __future__ import annotations

from copy import deepcopy
from math import atan2, cos, degrees, hypot, pi, sin

from shapely.affinity import rotate, scale
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import nearest_points, unary_union


class ArchitecturalGeometryFormReasoningV1:
    """Diagnose a plan and propose context-derived transformations, without a winner."""

    EPS = 1e-7
    METRICS = (
        "dead_space", "circulation", "door_feasibility", "privacy",
        "daylight_frontage_opportunity", "adjacency", "furniture_room_usability",
        "geometric_coherence", "hierarchy_sequence", "multi_problem_benefit",
    )
    SUPPORTED_USES = (
        "foyer", "living", "dining", "corridor", "stair_hall", "bedroom_transition",
        "service", "core", "balcony", "courtyard", "unit_shape",
    )

    def analyze(self, *, plan_boundary, spaces, connections=(), exterior_edges=(),
                entrances=(), context_axes=None, max_proposals=8):
        original = deepcopy((plan_boundary, spaces, connections, exterior_edges, entrances, context_axes))
        boundary = Polygon(plan_boundary)
        parsed = self._spaces(spaces)
        axes = self._axes(context_axes, boundary, parsed)
        language = self._language(boundary, parsed, axes)
        issues = self._issues(boundary, parsed, connections, exterior_edges, entrances, axes)
        proposals = self._proposals(boundary, parsed, issues, axes, int(max_proposals))
        assert original == (plan_boundary, spaces, connections, exterior_edges, entrances, context_axes)
        return {
            "contract": "ArchitecturalGeometryFormReasoningV1",
            "scope": "architecture_only",
            "status": "diagnostic_complete",
            "input_mutated": False,
            "context_axes": axes,
            "detected_geometry_language": language,
            "supported_spatial_uses": list(self.SUPPORTED_USES),
            "detected_issues": issues,
            "proposals": proposals,
            "comparison_dimensions": list(self.METRICS),
            "selection": {"winner": None, "authoritative_ranking": False, "final_selection_performed": False},
            "policy": {
                "default": "prefer_simple_axis_aligned_solution",
                "non_orthogonal_or_curved_gate": "requires_explicit_spatial_or_functional_justification_and_multi_problem_evidence",
                "shape_catalog_selection": False,
                "fixed_vertex_count": False,
                "precedent_is_regulation": False,
            },
        }

    def _spaces(self, spaces):
        result = []
        for idx, item in enumerate(spaces):
            geom = Polygon(item["boundary"])
            result.append({"id": str(item.get("id", f"SPACE-{idx+1}")),
                           "use": str(item.get("use", "unresolved")), "geometry": geom,
                           "doors": [Point(p) for p in item.get("doors", [])],
                           "privacy": str(item.get("privacy", "neutral"))})
        return result

    def _axes(self, supplied, boundary, spaces):
        vectors = []
        if supplied:
            vectors.extend(supplied)
        else:
            for geom in [boundary] + [s["geometry"] for s in spaces]:
                pts = list(geom.minimum_rotated_rectangle.exterior.coords)
                vectors.extend((pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]) for i in range(4))
        angles = []
        for x, y in vectors:
            if hypot(x, y) <= self.EPS:
                continue
            angle = atan2(y, x) % (pi/2)
            angles.append(angle)
        base = sorted(angles)[len(angles)//2] if angles else 0.0
        u = [round(cos(base), 9), round(sin(base), 9)]
        return [u, [-u[1], u[0]]]

    def _language(self, boundary, spaces, axes):
        edges = []
        for geom in [boundary] + [s["geometry"] for s in spaces]:
            pts = list(geom.exterior.coords)
            edges.extend((a, b) for a, b in zip(pts, pts[1:]))
        off = 0
        for a, b in edges:
            dx, dy = b[0]-a[0], b[1]-a[1]; n = hypot(dx, dy)
            if n <= self.EPS:
                continue
            align = max(abs((dx*axes[0][0]+dy*axes[0][1])/n), abs((dx*axes[1][0]+dy*axes[1][1])/n))
            off += align < .985
        compactness = [4*pi*s["geometry"].area/max(s["geometry"].length**2, self.EPS) for s in spaces]
        return {
            "primary": "orthogonal" if off == 0 else "hybrid_orthogonal_and_angled",
            "off_axis_edge_ratio": round(off/max(len(edges), 1), 6),
            "curvilinear_proxy_present": any(v > .82 and len(list(s["geometry"].exterior.coords)) > 12 for v, s in zip(compactness, spaces)),
            "coherence_basis": "dominant_axes_and_repeated_relations_not_named_shape",
        }

    def _issues(self, boundary, spaces, connections, exterior_edges, entrances, axes):
        union = unary_union([s["geometry"] for s in spaces]) if spaces else Polygon()
        residual = boundary.difference(union)
        small = sum(g.area for g in self._polys(residual) if g.area < max(2.0, boundary.area*.03))
        issues = []
        if small > self.EPS:
            issues.append(self._issue("fragmented_residual_space", ["dead_space", "furniture_room_usability"], small))
        byid = {s["id"]: s for s in spaces}
        for a, b in connections:
            if a in byid and b in byid and byid[a]["geometry"].distance(byid[b]["geometry"]) > self.EPS:
                issues.append(self._issue("weak_required_adjacency", ["adjacency", "circulation"], byid[a]["geometry"].distance(byid[b]["geometry"]), [a, b]))
        private = [s for s in spaces if s["privacy"] == "private"]
        public = [s for s in spaces if s["privacy"] == "public"]
        if entrances and private and public:
            entry = unary_union([Point(p) for p in entrances])
            if min(entry.distance(s["geometry"]) for s in private) + self.EPS < min(entry.distance(s["geometry"]) for s in public):
                issues.append(self._issue("privacy_sequence_conflict", ["privacy", "hierarchy_sequence"], 1.0))
        ext = [LineString(e) for e in exterior_edges]
        for s in spaces:
            if s["use"] in {"living", "dining", "bedroom"} and ext and min(s["geometry"].distance(e) for e in ext) > self.EPS:
                issues.append(self._issue("weak_daylight_frontage_opportunity", ["daylight_frontage_opportunity", "adjacency"], min(s["geometry"].distance(e) for e in ext), [s["id"]]))
            rect = s["geometry"].minimum_rotated_rectangle
            usability = s["geometry"].area/max(rect.area, self.EPS)
            if usability < .78:
                issues.append(self._issue("low_room_fit_efficiency", ["furniture_room_usability", "geometric_coherence"], 1-usability, [s["id"]]))
        if len(spaces) > 2 and not any(s["use"] in {"foyer", "stair_hall", "courtyard", "living"} for s in spaces):
            issues.append(self._issue("weak_spatial_hierarchy", ["hierarchy_sequence", "circulation"], 1.0))
        return sorted(issues, key=lambda x: (-x["severity_proxy"], x["issue_id"], x["affected_space_ids"]))

    @staticmethod
    def _issue(name, metrics, severity, ids=None):
        return {"issue_id": name, "affected_space_ids": sorted(ids or []),
                "affected_metrics": metrics, "severity_proxy": round(float(severity), 6)}

    def _proposals(self, boundary, spaces, issues, axes, limit):
        proposals = []
        issue_names = {i["issue_id"] for i in issues}
        center = boundary.centroid
        # First proposal is always the least-complex alignment/partition repair.
        strip = self._axis_strip(boundary, axes, center, max(boundary.bounds[2]-boundary.bounds[0], boundary.bounds[3]-boundary.bounds[1])*.06)
        proposals.append(self._proposal("axis_aligned_partition_repair", "orthogonal", strip,
            ["reduce_fragmented_residuals", "preserve_furniture_edges"], issue_names,
            ["dead_space", "furniture_room_usability", "geometric_coherence"], 1.0, axes))
        targets = [s for s in spaces if s["use"] in self.SUPPORTED_USES or s["use"] in {"bedroom", "unresolved"}]
        target = min(targets or spaces, key=lambda s: s["geometry"].distance(center)) if spaces else None
        if target and issue_names & {"weak_required_adjacency", "fragmented_residual_space", "low_room_fit_efficiency"}:
            chord = nearest_points(target["geometry"].boundary, center)[0]
            chamfer = Polygon([p for p in list(target["geometry"].minimum_rotated_rectangle.exterior.coords)[:-1]] + [[chord.x, chord.y]]).convex_hull.intersection(boundary)
            proposals.append(self._proposal("context_derived_chamfer_transition", "chamfer_or_angled", chamfer,
                ["join_misaligned_adjacencies", "recover_residual_wedge"], issue_names,
                ["adjacency", "circulation", "dead_space"], 2.0, axes))
        if issue_names & {"weak_spatial_hierarchy", "privacy_sequence_conflict", "weak_required_adjacency"}:
            radius = max(boundary.area**.5*.08, .5)
            arc = center.buffer(radius, resolution=12).intersection(boundary)
            proposals.append(self._proposal("distribution_focus_from_connection_field", "circular_or_arc", arc,
                ["clarify_distribution", "mediate_public_private_sequence"], issue_names,
                ["circulation", "privacy", "hierarchy_sequence"], 3.0, axes))
        if issue_names & {"weak_daylight_frontage_opportunity", "weak_spatial_hierarchy"}:
            oval = scale(center.buffer(max(boundary.area**.5*.07, .5), resolution=16), 1.65, .75, origin=center)
            oval = rotate(oval, degrees(atan2(axes[0][1], axes[0][0])), origin=center).intersection(boundary)
            proposals.append(self._proposal("daylight_or_courtyard_oval_focus", "ellipse_or_oval", oval,
                ["increase_shared_frontage_or_courtyard_edge", "create_orientation_focus"], issue_names,
                ["daylight_frontage_opportunity", "hierarchy_sequence", "adjacency"], 3.5, axes))
        if len(spaces) >= 3 and issue_names & {"weak_required_adjacency", "weak_spatial_hierarchy"}:
            centroids = [s["geometry"].centroid for s in spaces]
            hub = unary_union(centroids).centroid
            radial = unary_union([LineString([hub, p]).buffer(boundary.area**.5*.015, cap_style=2) for p in centroids]).intersection(boundary)
            proposals.append(self._proposal("connection_field_radial_distribution", "radial", radial,
                ["connect_multiple_destinations", "establish_center_and_sequence"], issue_names,
                ["circulation", "adjacency", "hierarchy_sequence"], 4.0, axes))
        for index, p in enumerate(proposals[:limit]):
            p["proposal_id"] = f"GEO-{index+1:02d}-{p['operation']}"
        return proposals[:limit]

    def _proposal(self, operation, family, geom, justifications, issues, benefits, complexity, axes):
        addressed = sorted(set(issues) & {
            "fragmented_residual_space", "weak_required_adjacency", "privacy_sequence_conflict",
            "weak_daylight_frontage_opportunity", "low_room_fit_efficiency", "weak_spatial_hierarchy"})
        nonlinear = family != "orthogonal"
        gate = (not nonlinear) or (len(benefits) >= 2 and bool(addressed))
        score = {m: 0.0 for m in self.METRICS}
        for metric in benefits:
            score[metric] = round(min(1.0, .35 + .12*len(addressed)), 3)
        score["multi_problem_benefit"] = round(min(1.0, len(benefits)*len(addressed)/10), 3)
        score["geometric_coherence"] = max(score["geometric_coherence"], round(max(0.0, 1-complexity*.12), 3))
        return {"proposal_id": None, "operation": operation, "geometry_family_descriptor": family,
                "target_geometry": self._geometry(geom), "context_axes_used": axes,
                "spatial_justifications": justifications, "addressed_issue_ids": addressed,
                "non_orthogonal_or_curved": nonlinear, "justification_gate_passed": gate,
                "complexity_proxy": complexity, "metric_evidence_0_1": score,
                "eligible_for_human_review": gate, "is_winner": False}

    @staticmethod
    def _axis_strip(boundary, axes, center, width):
        span = max(boundary.bounds[2]-boundary.bounds[0], boundary.bounds[3]-boundary.bounds[1])*2
        a = (center.x-axes[0][0]*span, center.y-axes[0][1]*span)
        b = (center.x+axes[0][0]*span, center.y+axes[0][1]*span)
        return LineString([a, b]).buffer(width/2, cap_style=2).intersection(boundary)

    @staticmethod
    def _polys(g):
        if g.is_empty: return []
        if g.geom_type == "Polygon": return [g]
        return [x for x in getattr(g, "geoms", []) if x.geom_type == "Polygon"]

    @classmethod
    def _geometry(cls, g):
        polys = cls._polys(g)
        values = [[[round(x, 6), round(y, 6)] for x, y in list(p.exterior.coords)[:-1]] for p in polys]
        return values[0] if len(values) == 1 else values
