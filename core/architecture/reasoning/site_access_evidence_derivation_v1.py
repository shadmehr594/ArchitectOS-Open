"""Derive site-access evidence without selecting or solving access geometry."""

from copy import deepcopy
import hashlib
import json
import math


class SiteAccessEvidenceDerivationV1:
    """Fail-closed, project-neutral evidence derivation for site access."""

    VERSION = "1.0"
    EPS = 1e-9
    INVENTORY_SOURCES = (
        "protected_zones", "pedestrian_conflict_zones", "vehicle_access_zones",
        "vehicle_circulation_zones", "parking_access_zones", "setback_zones",
        "reserved_site_regions", "fixed_obstacles",
    )

    def derive(self, site_geometry, program=None, regulation=None, hypotheses=None):
        site = deepcopy(site_geometry) if isinstance(site_geometry, dict) else {}
        program = deepcopy(program) if isinstance(program, dict) else {}
        regulation = deepcopy(regulation) if isinstance(regulation, dict) else {}
        hypotheses = deepcopy(hypotheses) if isinstance(hypotheses, dict) else {}
        polygon, failure = self._valid_polygon(
            site.get("parcel_boundary") or self._nested(site, "boundary", "points")
        )
        result = {
            "contract": "SiteAccessEvidenceDerivationV1", "version": self.VERSION,
            "derivation_status": "unresolved", "parcel_edges": [],
            "road_frontages": [], "public_access_candidate_regions": [],
            "commercial_entrance_candidate_regions": [],
            "conflict_inventory": self._inventory(site, program),
            "hypothesis_scoped_target_regions": [],
            "coordination_selection_authority": {"status": "unresolved"},
            "regulatory_separation_policy": self._policy(regulation),
            "unresolved_evidence": [], "provenance": [],
        }
        if failure:
            result["unresolved_evidence"].append(failure)
            return result

        edges = self._edges(polygon)
        result["parcel_edges"] = edges
        road_indices, road_failure = self._road_indices(site, len(edges))
        if road_failure:
            result["unresolved_evidence"].append(road_failure)
        else:
            for index in road_indices:
                edge = edges[index]
                result["road_frontages"].append({
                    "edge_id": edge["edge_id"], "edge_index": index,
                    "eligible_interval": [0.0, 1.0], "start": edge["start"],
                    "end": edge["end"], "length": edge["length"],
                    "authority_class": "AUTO_DERIVED_AUTHORITATIVE",
                    "source": "confirmed_road_frontage_bound_to_authoritative_parcel_edge",
                })
        result["provenance"] = [
            {"field": "parcel_edges", "source": "authoritative_parcel_polygon", "method": "ordered_boundary_edge_enumeration"},
            {"field": "road_frontages", "source": "confirmed_access_edge_index", "method": "stable_edge_identity_binding"},
        ]

        public_required = self._truth(program, "commercial_required") or self._truth(program, "public_access_required")
        commercial_required = self._truth(program, "commercial_required")
        frontage_priority = self._truth(program, "commercial_frontage_priority")
        for frontage in result["road_frontages"]:
            region = self._region(frontage)
            if public_required:
                result["public_access_candidate_regions"].append(region)
            if commercial_required and frontage_priority:
                result["commercial_entrance_candidate_regions"].append(region)
        result["dedicated_pedestrian_entrance"] = {
            "mandatory": False,
            "status": "optional_independent_alternative",
            "merged_with_public_access_point": False,
        }

        candidates = result["public_access_candidate_regions"]
        if len(candidates) == 1:
            result["coordination_selection_authority"] = {
                "status": "resolved_unique_region", "selected_region_id": candidates[0]["region_id"],
                "selected_point": None, "point_selection_status": "not_derived",
            }
        elif len(candidates) > 1:
            result["coordination_selection_authority"] = {
                "status": "DESIGN_CONFIRMATION_REQUIRED", "reason": "equivalent_eligible_regions_remain",
                "candidate_region_ids": [item["region_id"] for item in candidates],
            }
        else:
            result["coordination_selection_authority"] = {
                "status": "unresolved", "reason": "eligible_public_frontage_region_missing",
            }

        result["hypothesis_scoped_target_regions"] = self._hypothesis_regions(site, hypotheses)
        result["derivation_status"] = "resolved" if not result["unresolved_evidence"] else "partial"
        return result

    def _valid_polygon(self, value):
        if not isinstance(value, list) or len(value) < 3:
            return None, "authoritative_parcel_polygon_missing"
        points = []
        for raw in value:
            if not isinstance(raw, (list, tuple)) or len(raw) < 2:
                return None, "authoritative_parcel_polygon_invalid"
            try:
                point = [float(raw[0]), float(raw[1])]
            except (TypeError, ValueError):
                return None, "authoritative_parcel_polygon_invalid"
            if not all(math.isfinite(item) for item in point):
                return None, "authoritative_parcel_polygon_invalid"
            points.append(point)
        if points[0] == points[-1]:
            points.pop()
        if len(points) < 3 or len({tuple(point) for point in points}) != len(points):
            return None, "authoritative_parcel_polygon_invalid_or_ambiguous"
        area2 = sum(self._cross(a, b, [0.0, 0.0]) for a, b in self._segments(points))
        if abs(area2) <= self.EPS:
            return None, "authoritative_parcel_polygon_invalid_or_ambiguous"
        segments = self._segments(points)
        for i, first in enumerate(segments):
            for j, second in enumerate(segments):
                if j <= i or j in ((i + 1) % len(segments), (i - 1) % len(segments)):
                    continue
                if self._intersects(first, second):
                    return None, "authoritative_parcel_polygon_invalid_or_ambiguous"
        return points, None

    def _edges(self, polygon):
        area2 = sum(a[0] * b[1] - b[0] * a[1] for a, b in self._segments(polygon))
        winding = "counterclockwise" if area2 > 0 else "clockwise"
        identities = []
        for start, end in self._segments(polygon):
            canonical = sorted([self._canonical_point(start), self._canonical_point(end)])
            digest = hashlib.sha256(json.dumps(canonical, separators=(",", ":")).encode()).hexdigest()[:16]
            identities.append("PARCEL-EDGE-" + digest.upper())
        return [{
            "edge_id": identities[index], "edge_index": index,
            "start": list(start), "end": list(end),
            "length": math.hypot(end[0] - start[0], end[1] - start[1]),
            "winding": winding,
            "adjacency": {"previous_edge_id": identities[index - 1], "next_edge_id": identities[(index + 1) % len(identities)]},
            "source": "authoritative_parcel_polygon",
            "provenance": {"method": "deterministic_boundary_enumeration", "coordinate_mutation": False},
        } for index, (start, end) in enumerate(self._segments(polygon))]

    def _road_indices(self, site, edge_count):
        access = site.get("site_constraints", {}).get("access", {}) if isinstance(site.get("site_constraints"), dict) else {}
        raw = site.get("confirmed_road_access_edge_indices")
        if raw is None:
            raw = site.get("access_edge_index", access.get("edge_index"))
        values = raw if isinstance(raw, list) else [raw]
        if not values or values == [None]:
            return [], "confirmed_road_access_edge_index_missing"
        if any(not isinstance(item, int) or isinstance(item, bool) or not 0 <= item < edge_count for item in values):
            return [], "confirmed_road_access_edge_index_invalid_or_ambiguous"
        return sorted(set(values)), None

    def _inventory(self, site, program):
        scope = site.get("conflict_inventory_scope", list(self.INVENTORY_SOURCES))
        if not isinstance(scope, list) or any(item not in self.INVENTORY_SOURCES for item in scope):
            return {"status": "partial_unresolved", "items": [], "unknown_sources": scope, "authoritative_empty": False}
        items, missing, unknown = [], [], []
        for key in scope:
            if key not in site:
                missing.append(key)
                continue
            values = site.get(key)
            if not isinstance(values, list):
                unknown.append(key)
                continue
            for index, value in enumerate(values):
                items.append({"source": key, "source_index": index, "value": deepcopy(value)})
        if self._truth(program, "public_private_separation"):
            items.append({"source": "program.public_private_separation", "constraint_type": "qualitative_separation", "geometry_status": "not_assigned"})
        complete = not missing and not unknown
        return {
            "status": "complete" if complete else "partial_unresolved", "items": items,
            "scanned_sources": scope, "missing_sources": missing, "unknown_sources": unknown,
            "authoritative_empty": complete and not items,
        }

    def _hypothesis_regions(self, site, hypotheses):
        domains = site.get("parking_domains", {}) if isinstance(site.get("parking_domains"), dict) else {}
        specs = {
            "H1": ("pilotis", "pilotis_parking_domain"),
            "H2": ("basement_arrival", "basement_ramp_arrival_or_circulation_domain"),
        }
        enabled = hypotheses.get("enabled", ["H1", "H2"])
        output = []
        for branch, (key, semantic) in specs.items():
            if branch not in enabled:
                continue
            value = domains.get(key)
            polygon, failure = self._valid_polygon(value)
            output.append({
                "hypothesis_id": branch, "authority_class": "HYPOTHESIS_SCOPED",
                "target_semantic": semantic,
                "status": "derived_target_region" if not failure else "target_region_pending_geometry",
                "region": polygon if not failure else None,
                "circular_dependency": bool(failure),
                "unresolved_evidence": [] if not failure else [key + "_geometry_not_yet_resolved"],
                "project_authority": False,
            })
        return output

    @staticmethod
    def _policy(regulation):
        records = regulation.get("evidence_records", []) if isinstance(regulation, dict) else []
        applicable = [deepcopy(item) for item in records if isinstance(item, dict) and item.get("applicability_status") != "not_applicable"]
        return {
            "status": "resolved_qualitative_or_conditional" if applicable else "unresolved",
            "minimum_frontage_gate_separation": None,
            "numeric_value_not_invented": True,
            "evidence_records": applicable,
        }

    @staticmethod
    def _region(frontage):
        return {
            "region_id": "FRONTAGE-REGION-" + frontage["edge_id"],
            "edge_id": frontage["edge_id"], "parameter_interval": list(frontage["eligible_interval"]),
            "segment": [list(frontage["start"]), list(frontage["end"])],
            "selected_point": None, "selection_status": "candidate_region_not_point",
            "authority_class": "AUTO_DERIVED_AUTHORITATIVE",
        }

    @staticmethod
    def _truth(source, key):
        value = source.get(key)
        if isinstance(value, dict):
            return value.get("value") is True or value.get("required") is True or value.get("priority") in ("high", "frontage")
        return value is True or value in ("required", "high", "frontage")

    @staticmethod
    def _nested(source, first, second):
        value = source.get(first, {})
        return value.get(second) if isinstance(value, dict) else None

    @staticmethod
    def _canonical_point(point):
        return [format(point[0], ".15g"), format(point[1], ".15g")]

    @staticmethod
    def _segments(points):
        return [(points[index], points[(index + 1) % len(points)]) for index in range(len(points))]

    @staticmethod
    def _cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def _intersects(self, first, second):
        a, b = first
        c, d = second
        o1, o2 = self._cross(a, b, c), self._cross(a, b, d)
        o3, o4 = self._cross(c, d, a), self._cross(c, d, b)
        return o1 * o2 < -self.EPS and o3 * o4 < -self.EPS
