"""Architecture-only, problem-led geometric intervention reasoning.

The engine emits review hypotheses, never a selected shape or a winner.
"""
from __future__ import annotations

from copy import deepcopy
from math import atan2, cos, hypot, pi, sin

from shapely.affinity import rotate, translate
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points, unary_union


class ArchitecturalGeometricInterventionReasoningV2:
    EPS = 1e-7
    OPERATIONS = (
        "shift_boundary", "rotate_boundary", "chamfer_corner", "widen_node",
        "bend_circulation", "curve_transition", "radial_distribute",
        "merge_residual_pocket", "align_neighboring_spaces", "relocate_doorway",
        "reshape_service_cluster", "reorganize_around_core",
    )
    METRICS = (
        "dead_space", "circulation", "door_feasibility", "privacy",
        "daylight_frontage_opportunity", "adjacency", "furniture_room_usability",
        "geometric_coherence", "hierarchy_sequence", "multi_problem_benefit",
    )

    def analyze(self, *, plan_boundary, spaces, connections=(), exterior_edges=(),
                entrances=(), context_axes=None, max_hypotheses=10):
        original = deepcopy((plan_boundary, spaces, connections, exterior_edges, entrances, context_axes))
        boundary = Polygon(plan_boundary)
        parsed = self._parse_spaces(spaces)
        geometry = self._dominant_geometry(boundary, parsed, context_axes)
        problems = self._detect_problems(boundary, parsed, connections, exterior_edges, entrances)
        scopes = self._scope_problems(problems, parsed)
        hypotheses = self._generate(boundary, parsed, problems, scopes, geometry)[:int(max_hypotheses)]
        assert original == (plan_boundary, spaces, connections, exterior_edges, entrances, context_axes)
        return {
            "contract": "ArchitecturalGeometricInterventionReasoningV2",
            "scope": "architecture_only",
            "pipeline": ["spatial_problem_detection", "dominant_geometry_detection",
                         "intervention_scope", "geometric_operation_generation",
                         "spatial_reallocation", "multi_criteria_evaluation"],
            "input_mutated": False,
            "dominant_geometry": geometry,
            "spatial_problems": problems,
            "intervention_scopes": scopes,
            "intervention_hypotheses": hypotheses,
            "supported_operations": list(self.OPERATIONS),
            "comparison_dimensions": list(self.METRICS),
            "selection": {"winner": None, "authoritative_ranking": False, "final_selection_performed": False},
            "policy": {
                "default": "prefer_simple_orthogonal_or_context_axis_conforming_operation",
                "exception_gate": "angle_curve_radial_or_ellipse_requires_explicit_justification_and_multi_problem_benefit",
                "local_exception_may_remain_local": True,
                "shape_catalog_selection": False,
                "fixed_vertex_count": False,
                "precedent_is_regulation": False,
            },
        }

    def _parse_spaces(self, spaces):
        out = []
        for index, item in enumerate(spaces):
            out.append({
                "id": str(item.get("id", f"SPACE-{index+1}")),
                "use": str(item.get("use", "unresolved")),
                "geometry": Polygon(item["boundary"]),
                "doors": [Point(p) for p in item.get("doors", [])],
                "privacy": str(item.get("privacy", "neutral")),
            })
        return out

    def _dominant_geometry(self, boundary, spaces, supplied):
        vectors = []
        if supplied:
            vectors.extend((float(v[0]), float(v[1]), 1.0, "supplied") for v in supplied)
        else:
            for source, geom in [("envelope", boundary)] + [("space", s["geometry"]) for s in spaces]:
                pts = list(geom.exterior.coords)
                for a, b in zip(pts, pts[1:]):
                    dx, dy = b[0]-a[0], b[1]-a[1]
                    length = hypot(dx, dy)
                    if length > self.EPS:
                        # The envelope defines the global field; repeated internal
                        # partitions inform it without being allowed to erase it.
                        weight = length * (4.0 if source == "envelope" else 1.0)
                        vectors.append((dx, dy, weight, source))
        bins = {}
        for dx, dy, weight, source in vectors:
            angle = atan2(dy, dx) % (pi/2)
            key = round(angle/(pi/180*2)) * 2
            bins[key] = bins.get(key, 0.0) + weight
        degree = max(sorted(bins), key=lambda k: (bins[k], -k)) if bins else 0
        base = degree*pi/180
        axes = [[round(cos(base), 9), round(sin(base), 9)],
                [round(-sin(base), 9), round(cos(base), 9)]]
        total = sum(bins.values()) or 1.0
        conformity = sum(v for k, v in bins.items() if min(abs(k-degree), 90-abs(k-degree)) <= 4)/total
        envelope_pts = list(boundary.exterior.coords)
        envelope_off = self._off_axis_ratio(envelope_pts, axes)
        global_family = "context_orthogonal" if envelope_off <= .08 else "envelope_led_oblique"
        return {
            "global": {"family": global_family, "axes": axes, "confidence_0_1": round(conformity, 3),
                       "source": "context_edges_weighted_by_length"},
            "zones": [{"zone_id": s["id"], "family": "axis_conforming" if self._off_axis_ratio(list(s["geometry"].exterior.coords), axes) <= .12 else "local_mixed",
                       "axes": axes} for s in spaces],
            "local_exceptions": [],
        }

    def _detect_problems(self, boundary, spaces, connections, exterior_edges, entrances):
        issues = []
        union = unary_union([s["geometry"] for s in spaces]) if spaces else Polygon()
        residual = boundary.difference(union)
        pockets = [p for p in self._polys(residual) if p.area < max(2.0, boundary.area*.04)]
        if pockets:
            issues.append(self._problem("fragmented_residual_pocket", ["dead_space", "furniture_room_usability"],
                                        [s["id"] for s in spaces if any(s["geometry"].distance(p) <= self.EPS for p in pockets)],
                                        sum(p.area for p in pockets)))
        by_id = {s["id"]: s for s in spaces}
        for a, b in connections:
            if a in by_id and b in by_id and by_id[a]["geometry"].distance(by_id[b]["geometry"]) > self.EPS:
                issues.append(self._problem("disconnected_required_adjacency", ["adjacency", "circulation"], [a, b], by_id[a]["geometry"].distance(by_id[b]["geometry"])))
        for s in spaces:
            fit = s["geometry"].area/max(s["geometry"].minimum_rotated_rectangle.area, self.EPS)
            if fit < .8:
                issues.append(self._problem("low_space_fit_efficiency", ["furniture_room_usability", "geometric_coherence"], [s["id"]], 1-fit))
            if s["doors"] and any(not s["geometry"].buffer(.2).contains(d) for d in s["doors"]):
                issues.append(self._problem("doorway_boundary_conflict", ["door_feasibility", "circulation"], [s["id"]], 1.0))
        private = [s for s in spaces if s["privacy"] == "private"]
        public = [s for s in spaces if s["privacy"] == "public"]
        if entrances and private and public:
            entry = unary_union([Point(p) for p in entrances])
            if min(entry.distance(s["geometry"]) for s in private) < min(entry.distance(s["geometry"]) for s in public):
                issues.append(self._problem("privacy_sequence_conflict", ["privacy", "hierarchy_sequence"], [s["id"] for s in private], 1.0))
        ext = [LineString(e) for e in exterior_edges]
        for s in spaces:
            if s["use"] in {"living", "dining", "bedroom", "unit_shape"} and ext and min(s["geometry"].distance(e) for e in ext) > self.EPS:
                issues.append(self._problem("weak_exterior_frontage_relation", ["daylight_frontage_opportunity", "adjacency"], [s["id"]], min(s["geometry"].distance(e) for e in ext)))
        if len(spaces) >= 3 and not any(s["use"] in {"foyer", "corridor", "stair_hall"} for s in spaces):
            issues.append(self._problem("missing_distribution_hierarchy", ["circulation", "hierarchy_sequence", "door_feasibility"], [s["id"] for s in spaces], 1.0))
        return sorted(issues, key=lambda x: (-x["severity_proxy"], x["problem_id"], x["affected_space_ids"]))

    @staticmethod
    def _problem(name, metrics, ids, severity):
        return {"problem_id": name, "affected_metrics": metrics, "affected_space_ids": sorted(set(ids)), "severity_proxy": round(float(severity), 6)}

    def _scope_problems(self, problems, spaces):
        total = max(len(spaces), 1)
        scopes = []
        for p in problems:
            ratio = len(p["affected_space_ids"])/total
            scope = "global" if ratio >= .75 and len(p["affected_space_ids"]) >= 3 else "zone" if ratio >= .35 or len(p["affected_space_ids"]) == 2 else "local"
            scopes.append({"problem_id": p["problem_id"], "scope": scope, "affected_space_ids": p["affected_space_ids"],
                           "scope_reason": "affected_relation_extent_not_shape_type"})
        return scopes

    def _generate(self, boundary, spaces, problems, scopes, geometry):
        scope_by_problem = {s["problem_id"]: s["scope"] for s in scopes}
        by_id = {s["id"]: s for s in spaces}
        hypotheses = []
        mapping = {
            "fragmented_residual_pocket": ["merge_residual_pocket", "shift_boundary", "align_neighboring_spaces"],
            "disconnected_required_adjacency": ["shift_boundary", "widen_node", "bend_circulation"],
            "low_space_fit_efficiency": ["align_neighboring_spaces", "chamfer_corner"],
            "doorway_boundary_conflict": ["relocate_doorway", "chamfer_corner"],
            "privacy_sequence_conflict": ["relocate_doorway", "bend_circulation", "curve_transition"],
            "weak_exterior_frontage_relation": ["shift_boundary", "rotate_boundary"],
            "missing_distribution_hierarchy": ["widen_node", "radial_distribute", "reorganize_around_core"],
        }
        seen = set()
        for problem in problems:
            for operation in mapping.get(problem["problem_id"], []):
                target_ids = problem["affected_space_ids"]
                key = (operation, tuple(target_ids), scope_by_problem[problem["problem_id"]])
                if key in seen:
                    continue
                seen.add(key)
                geom, allocation = self._operation_geometry(operation, boundary, [by_id[x] for x in target_ids if x in by_id], spaces, geometry)
                addressed = [p for p in problems if set(p["affected_space_ids"]) & set(target_ids) or p["problem_id"] == problem["problem_id"]]
                addressed_ids = sorted({p["problem_id"] for p in addressed})
                affected_metrics = sorted({m for p in addressed for m in p["affected_metrics"]})
                exceptional = operation in {"rotate_boundary", "chamfer_corner", "bend_circulation", "curve_transition", "radial_distribute"}
                multi = len(addressed_ids) >= 2 and len(affected_metrics) >= 2
                gate = not exceptional or (bool(addressed_ids) and multi)
                hypotheses.append({
                    "hypothesis_id": None, "operation": operation,
                    "operation_is_problem_derived": True, "intervention_scope": scope_by_problem[problem["problem_id"]],
                    "target_space_ids": target_ids, "trigger_problem_ids": [problem["problem_id"]],
                    "addressed_problem_ids": addressed_ids, "dominant_axes_used": geometry["global"]["axes"],
                    "dominant_geometry_conformity": "exception_justified" if exceptional else "conforms",
                    "non_orthogonal_or_curved_exception": exceptional,
                    "justification": self._justification(operation, addressed_ids, affected_metrics),
                    "multi_problem_benefit": multi, "justification_gate_passed": gate,
                    "spatial_reallocation": allocation, "review_geometry": self._geometry(geom),
                    "metric_evidence": {m: {"direction": "improve" if m in affected_metrics else "not_evaluated", "basis": "diagnostic_proxy_not_final_design"} for m in self.METRICS},
                    "risks": self._risks(operation), "eligible_for_human_review": gate, "is_winner": False,
                })
        order = {op: i for i, op in enumerate(self.OPERATIONS)}
        hypotheses.sort(key=lambda h: (h["non_orthogonal_or_curved_exception"], order[h["operation"]], h["target_space_ids"]))
        for i, h in enumerate(hypotheses):
            h["hypothesis_id"] = f"AGI-{i+1:02d}-{h['operation']}"
        return hypotheses

    def _operation_geometry(self, operation, boundary, targets, spaces, geometry):
        target = unary_union([s["geometry"] for s in targets]) if targets else boundary.centroid.buffer(boundary.area**.5*.04)
        center = target.centroid
        width = max(boundary.area**.5*.025, .2)
        allocation = {"mode": operation, "from_space_ids": [s["id"] for s in targets], "to_space_ids": [],
                      "boundary_change_status": "hypothesis_only", "topology_change": operation == "reorganize_around_core"}
        if operation in {"shift_boundary", "merge_residual_pocket", "align_neighboring_spaces", "reshape_service_cluster"}:
            geom = target.buffer(width, join_style=2).intersection(boundary)
        elif operation == "relocate_doorway":
            geom = nearest_points(target.boundary, boundary.centroid)[0].buffer(width).intersection(boundary)
        elif operation == "widen_node":
            geom = center.buffer(width*2, resolution=4).intersection(boundary)
        elif operation == "chamfer_corner":
            geom = center.buffer(width*2, resolution=2).intersection(boundary)
        elif operation == "rotate_boundary":
            geom = rotate(target, 5, origin=center).intersection(boundary)
        elif operation == "bend_circulation":
            geom = LineString([center, boundary.centroid]).buffer(width, cap_style=2, join_style=2).intersection(boundary)
        elif operation == "curve_transition":
            geom = LineString([center, boundary.centroid]).buffer(width, resolution=12).intersection(boundary)
        elif operation == "radial_distribute":
            hub = unary_union([s["geometry"].centroid for s in spaces]).centroid
            geom = unary_union([LineString([hub, s["geometry"].centroid]).buffer(width, cap_style=2) for s in spaces]).intersection(boundary)
        else:  # reorganize_around_core
            core = next((s for s in spaces if s["use"] == "core"), None)
            anchor = core["geometry"].centroid if core else boundary.centroid
            geom = unary_union([LineString([anchor, s["geometry"].centroid]).buffer(width, cap_style=2) for s in spaces if s is not core]).intersection(boundary)
            allocation["requires_whole_plan_revalidation"] = True
        allocation["delta_geometry"] = self._geometry(geom)
        return geom, allocation

    @staticmethod
    def _justification(operation, problems, metrics):
        return {"operation": operation, "because_spatial_problems": problems,
                "expected_benefits": metrics, "not_style_or_named_shape": True}

    @staticmethod
    def _risks(operation):
        risks = ["requires_dimensional_validation", "may_shift_area_between_adjacent_spaces"]
        if operation in {"rotate_boundary", "chamfer_corner", "bend_circulation", "curve_transition", "radial_distribute"}:
            risks += ["construction_complexity", "furniture_edge_loss", "exception_may_spread_beyond_needed_scope"]
        if operation == "reorganize_around_core":
            risks += ["whole_building_core_and_access_tradeoff", "all_affected_floors_require_revalidation"]
        return risks

    @staticmethod
    def _off_axis_ratio(points, axes):
        off = total = 0.0
        for a, b in zip(points, points[1:]):
            dx, dy = b[0]-a[0], b[1]-a[1]
            length = hypot(dx, dy)
            if length <= 1e-7:
                continue
            total += length
            align = max(abs((dx*axes[0][0]+dy*axes[0][1])/length), abs((dx*axes[1][0]+dy*axes[1][1])/length))
            if align < .985:
                off += length
        return off/max(total, 1e-7)

    @staticmethod
    def _polys(geom):
        if geom.is_empty:
            return []
        if geom.geom_type == "Polygon":
            return [geom]
        return [g for g in getattr(geom, "geoms", []) if g.geom_type == "Polygon"]

    @classmethod
    def _geometry(cls, geom):
        polygons = cls._polys(geom)
        values = [[[round(x, 6), round(y, 6)] for x, y in list(p.exterior.coords)[:-1]] for p in polygons]
        return values[0] if len(values) == 1 else values
