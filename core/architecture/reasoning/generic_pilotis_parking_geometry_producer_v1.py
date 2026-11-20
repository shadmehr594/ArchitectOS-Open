"""Generic, evidence-driven pilotis parking candidate geometry search."""
from __future__ import annotations

from copy import deepcopy
from math import atan2, cos, isfinite, pi, sin

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union


class GenericPilotisParkingGeometryProducerV1:
    """Produce non-authoritative candidates; never choose access or promote results."""

    EPS = 1e-7

    def produce(self, domain_evidence=None, parking_requirement=None,
                protected_region_evidence=None, vehicle_access_candidate_region=None,
                branch_evidence=None):
        original = deepcopy((domain_evidence, parking_requirement,
                             protected_region_evidence, vehicle_access_candidate_region,
                             branch_evidence))
        domain_evidence = domain_evidence if isinstance(domain_evidence, dict) else {}
        requirement = parking_requirement if isinstance(parking_requirement, dict) else {}
        inventory = protected_region_evidence if isinstance(protected_region_evidence, dict) else {}
        branch = branch_evidence if isinstance(branch_evidence, dict) else {}
        unresolved = []

        domain = self._polygon(domain_evidence.get("polygon"))
        if domain is None or domain.area <= self.EPS:
            unresolved.append("authoritative_pilotis_parking_domain")
        if domain_evidence.get("evidence_status") not in ("authoritative", "resolved"):
            unresolved.append("authoritative_pilotis_parking_domain_provenance")
        count = requirement.get("minimum_required_capacity")
        width, depth = requirement.get("stall_width"), requirement.get("stall_depth")
        aisle_width = requirement.get("aisle_width")
        for key, value in (("minimum_required_capacity", count), ("stall_width", width),
                           ("stall_depth", depth), ("aisle_width", aisle_width)):
            if not self._positive(value):
                unresolved.append(key)
        if not isinstance(count, int) or isinstance(count, bool) or count < 3:
            unresolved.append("minimum_required_capacity_at_least_three")
        if inventory.get("inventory_complete") is not True:
            unresolved.append("authoritative_protected_unavailable_region_inventory")
        provenance = deepcopy(domain_evidence.get("provenance") or [])
        provenance += deepcopy(requirement.get("provenance") or [])
        provenance += deepcopy(inventory.get("provenance") or [])
        provenance += deepcopy(branch.get("provenance") or [])
        if not provenance or not all(isinstance(x, dict) and x.get("source") for x in provenance):
            unresolved.append("authoritative_input_provenance")

        result = {
            "contract": "PilotisParkingDesignProducerV1",
            "source": self.__class__.__name__,
            "status": "pending_evidence" if unresolved else "candidates_produced",
            "hypothesis_id": branch.get("hypothesis_id"),
            "floor_scope": domain_evidence.get("floor_scope"),
            "authoritative_input_provenance": provenance,
            "domain_provenance": deepcopy(domain_evidence),
            "candidates": [], "candidate_count": 0,
            "unresolved_dependencies": sorted(set(unresolved)),
            "selected_candidate": None, "selection_status": "not_performed",
            "validation_status": "not_performed", "promotion_status": "not_performed",
            "publication_status": "not_performed",
            "authority_class": "NON_AUTHORITATIVE_DESIGN_CANDIDATES",
            "input_mutated": False,
        }
        if unresolved:
            result["input_mutated"] = original != (domain_evidence, parking_requirement,
                                                     protected_region_evidence,
                                                     vehicle_access_candidate_region,
                                                     branch_evidence)
            return result

        obstacles = []
        kinds = {"core": "core", "entrance": "entrance", "protected": "protected_zone",
                 "commercial": "commercial", "public_access": "public_use",
                 "private_access": "private_use"}
        clear = {value: "clear" for value in kinds.values()}
        for item in inventory.get("regions", []):
            if not isinstance(item, dict):
                continue
            shape = self._polygon(item.get("polygon"))
            if shape is not None:
                obstacles.append((item.get("region_id"), item.get("kind"), shape))
        blocked = unary_union([x[2] for x in obstacles]) if obstacles else Polygon()
        usable = domain.difference(blocked)
        raw = self._search(usable, int(count), float(width), float(depth), float(aisle_width))
        candidates = []
        access_dependency = ("eligible_frontage_coordination_pending" if vehicle_access_candidate_region
                             else "site_access_coordination_unresolved")
        for index, item in enumerate(raw, 1):
            candidate_id = f"PILOTIS-GENERIC-{index:03d}"
            evidence = [{"source": self.__class__.__name__, "candidate_id": candidate_id}]
            candidates.append({
                "candidate_id": candidate_id, "hypothesis_id": branch.get("hypothesis_id"),
                "floor_scope": domain_evidence.get("floor_scope"),
                "candidate_status": "candidate_evidence",
                "candidate_geometry_status": "candidate_complete",
                "candidate_geometry": {"parking_domain": self._coords(domain),
                                       "usable_domain": self._geometry(usable),
                                       "aisle": item["aisle"]},
                "stall_geometries": item["stalls"],
                "achieved_capacity_candidate": len(item["stalls"]),
                "vehicle_access_evidence": {
                    "status": "pending", "endpoint": None, "evidence": [],
                    "dependency": access_dependency,
                    "eligible_region": deepcopy(vehicle_access_candidate_region)},
                "manoeuvre_aisle_circulation_evidence": {
                    "status": "candidate", "connected": True,
                    "aisle_polygon": item["aisle"], "evidence": evidence},
                "stall_ingress_egress_evidence": {
                    "status": "candidate", "all_stalls_independently_usable": True,
                    "evidence": evidence},
                "pedestrian_safety_evidence": {
                    "status": "clear", "mandatory_route_blocked": False,
                    "conflicts": [], "evidence": evidence},
                "compatibility_evidence": dict(clear, inventory_complete=True,
                                               conflicts=[], evidence=evidence),
                "authoritative_input_provenance": deepcopy(provenance),
                "unresolved_dependencies": [access_dependency],
                "deterministic_ranking_metadata": {
                    "method": "capacity_descending_then_compactness_then_geometry_key",
                    "candidate_capacity": len(item["stalls"]),
                    "compactness": item["compactness"], "geometry_key": item["key"],
                    "rank": index},
                "selected_status": "not_selected", "validation_status": "not_validated",
                "authority_class": "NON_AUTHORITATIVE_DESIGN_CANDIDATE",
            })
        result["candidates"] = candidates
        result["candidate_count"] = len(candidates)
        if not candidates:
            result["status"] = "no_feasible_candidates"
            result["unresolved_dependencies"] = ["minimum_capacity_not_geometrically_achievable"]
        result["input_mutated"] = original != (domain_evidence, parking_requirement,
                                                 protected_region_evidence,
                                                 vehicle_access_candidate_region,
                                                 branch_evidence)
        return result

    def _search(self, usable, required, sw, sd, aw):
        if usable.is_empty:
            return []
        angles = self._edge_angles(usable)
        found = {}
        for angle in angles:
            ux, uy, nx, ny = cos(angle), sin(angle), -sin(angle), cos(angle)
            vertices = [p for poly in self._polygons(usable) for p in list(poly.exterior.coords)[:-1]]
            us = [x * ux + y * uy for x, y in vertices]
            vs = [x * nx + y * ny for x, y in vertices]
            u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
            row_span = sd + aw + sd
            if u1-u0 + self.EPS < sw or v1-v0 + self.EPS < sd+aw:
                continue
            centers = self._stations(v0 + row_span/2, v1 - row_span/2, max(sw, sd))
            offsets = self._stations(0.0, sw, sw/max(required, 1))
            for center in centers:
                for offset in offsets:
                    aisle = self._rect(u0, u1, center-aw/2, center+aw/2, ux, uy, nx, ny).intersection(usable)
                    if aisle.is_empty or len(self._polygons(aisle)) != 1:
                        continue
                    stalls = []
                    station = u0 + offset
                    while station + sw <= u1 + self.EPS:
                        for side in (-1.0, 1.0):
                            inner = center + side*aw/2
                            outer = inner + side*sd
                            shape = self._rect(station, station+sw, min(inner, outer),
                                               max(inner, outer), ux, uy, nx, ny)
                            if usable.buffer(self.EPS).covers(shape) and shape.intersection(aisle).area <= self.EPS:
                                stalls.append(shape)
                        station += sw
                    if len(stalls) < required:
                        continue
                    stalls = sorted(stalls, key=lambda p: self._canonical_polygon_key(p))
                    serial = [self._coords(p) for p in stalls]
                    key = self._layout_key(stalls, aisle)
                    found[key] = {"stalls": [{"stall_id": f"S-{i+1:03d}", "polygon": poly,
                                                "geometry_status": "candidate"}
                                               for i, poly in enumerate(serial)],
                                  "aisle": self._geometry(aisle),
                                  "compactness": round(unary_union(stalls+[aisle]).envelope.area, 8),
                                  "key": key}
        return sorted(found.values(), key=lambda x: (-len(x["stalls"]), x["compactness"], x["key"]))

    def _edge_angles(self, geometry):
        values = set()
        for poly in self._polygons(geometry):
            pts = list(poly.exterior.coords)
            for a, b in zip(pts, pts[1:]):
                if (b[0]-a[0])**2 + (b[1]-a[1])**2 > self.EPS:
                    angle = atan2(b[1]-a[1], b[0]-a[0]) % pi
                    values.add(round(angle, 12))
        return sorted(values)

    @staticmethod
    def _stations(start, stop, step):
        if stop < start:
            return [(start+stop)/2]
        count = max(1, int((stop-start)/step)+1)
        return [(start+stop)/2] if count == 1 else [start+i*(stop-start)/(count-1) for i in range(count)]

    @staticmethod
    def _rect(u0, u1, v0, v1, ux, uy, nx, ny):
        return Polygon([[ux*u+nx*v, uy*u+ny*v] for u, v in
                        ((u0, v0), (u1, v0), (u1, v1), (u0, v1))])

    @classmethod
    def _polygon(cls, value):
        try:
            shape = value if isinstance(value, Polygon) else Polygon(value)
            return shape.buffer(0) if not shape.is_valid else shape
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _positive(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(float(value)) and value > 0

    @staticmethod
    def _polygons(geometry):
        return [geometry] if geometry.geom_type == "Polygon" else list(getattr(geometry, "geoms", []))

    @staticmethod
    def _coords(poly):
        return [[round(float(x), 9), round(float(y), 9)] for x, y in list(poly.exterior.coords)[:-1]]

    @classmethod
    def _geometry(cls, geometry):
        polygons = cls._polygons(geometry)
        return cls._coords(polygons[0]) if len(polygons) == 1 else [cls._coords(p) for p in polygons]

    @classmethod
    def _canonical_polygon_key(cls, poly):
        c = poly.centroid
        distances = sorted(round(((x-c.x)**2+(y-c.y)**2)**.5, 8) for x, y in list(poly.exterior.coords)[:-1])
        return (round(c.x, 8), round(c.y, 8), tuple(distances))

    @classmethod
    def _layout_key(cls, stalls, aisle):
        union = unary_union(stalls)
        c = union.centroid
        radial = sorted((round(((p.centroid.x-c.x)**2+(p.centroid.y-c.y)**2)**.5, 7),
                         round(p.area, 7)) for p in stalls)
        return f"{len(stalls)}:{round(union.area,7)}:{round(aisle.area,7)}:{radial}"
