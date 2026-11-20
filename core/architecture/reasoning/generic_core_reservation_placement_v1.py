"""Generic non-authoritative placement search for a space-reservation proxy."""

from __future__ import annotations

from math import atan2, cos, isfinite, pi, sin, sqrt

from shapely.affinity import rotate, translate
from shapely.geometry import Polygon, box


class GenericCoreReservationPlacementV1:
    """Derive placement hypotheses from domain geometry without choosing one."""

    EPS = 1e-7

    def produce(self, domain_evidence=None, reservation_contract=None):
        domain_evidence = domain_evidence if isinstance(domain_evidence, dict) else {}
        reservation_contract = reservation_contract if isinstance(reservation_contract, dict) else {}
        domain = self._polygon(domain_evidence.get("polygon"))
        area = reservation_contract.get("total_vertical_core_reservation_target_area_m2")
        failures = []
        if domain is None or domain.area <= self.EPS:
            failures.append("valid_buildable_domain")
        if domain_evidence.get("evidence_status") not in ("authoritative", "resolved"):
            failures.append("buildable_domain_provenance")
        if not self._positive(area):
            failures.append("positive_reservation_area")
        if reservation_contract.get("authority_class") != "DESIGN_ASSUMPTION":
            failures.append("design_assumption_authority_class")
        if reservation_contract.get("assumption_scope") != "DESIGN_ASSUMPTION_FOR_SPACE_RESERVATION_ONLY":
            failures.append("space_reservation_only_scope")
        result = {
            "contract": "GenericCoreReservationPlacementV1",
            "status": "pending_evidence" if failures else "candidates_produced",
            "authority_class": "NON_AUTHORITATIVE_DESIGN_CANDIDATES",
            "selection": False,
            "selected_candidate": None,
            "shape_proxy": True,
            "final_geometry": False,
            "candidate_count": 0,
            "candidates": [],
            "unresolved_dependencies": failures,
        }
        if failures:
            return result

        side = sqrt(float(area))
        angles = self._edge_angles(domain)
        found = {}
        for angle in angles:
            rotated_domain = rotate(domain, -angle * 180.0 / pi, origin=(0, 0))
            feasible_centers = rotated_domain.buffer(-side / 2.0, join_style=2)
            for component in self._polygons(feasible_centers):
                events = list(component.exterior.coords)[:-1]
                events += [[component.centroid.x, component.centroid.y]]
                for cx, cy in events:
                    proxy = translate(box(-side / 2.0, -side / 2.0, side / 2.0, side / 2.0), cx, cy)
                    proxy = rotate(proxy, angle * 180.0 / pi, origin=(0, 0))
                    if not domain.buffer(self.EPS).covers(proxy):
                        continue
                    coords = self._coords(proxy)
                    key = tuple((round(x, 7), round(y, 7)) for x, y in coords)
                    found[key] = {
                        "polygon": coords,
                        "area_m2": round(proxy.area, 9),
                        "placement_basis": "domain_inset_boundary_or_centroid_geometry_event",
                    }
        for index, item in enumerate((found[key] for key in sorted(found)), 1):
            result["candidates"].append({
                "candidate_id": f"CORE-RESERVATION-PROXY-{index:03d}",
                "polygon": item["polygon"],
                "area_m2": item["area_m2"],
                "placement_basis": item["placement_basis"],
                "assumption_contract": reservation_contract.get("contract"),
                "authority_class": "DESIGN_ASSUMPTION",
                "selection": False,
                "shape_proxy": True,
                "final_geometry": False,
            })
        result["candidate_count"] = len(result["candidates"])
        if not result["candidates"]:
            result["status"] = "no_feasible_candidates"
            result["unresolved_dependencies"] = ["reservation_proxy_does_not_fit_buildable_domain"]
        return result

    def _edge_angles(self, polygon):
        values = set()
        points = list(polygon.exterior.coords)
        for a, b in zip(points, points[1:]):
            if (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 > self.EPS:
                values.add(round(atan2(b[1] - a[1], b[0] - a[0]) % (pi / 2.0), 12))
        return sorted(values)

    @staticmethod
    def _positive(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(float(value)) and value > 0

    @staticmethod
    def _polygon(value):
        try:
            polygon = Polygon(value)
            return polygon if polygon.is_valid else polygon.buffer(0)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _polygons(geometry):
        if geometry.is_empty:
            return []
        return [geometry] if geometry.geom_type == "Polygon" else list(getattr(geometry, "geoms", []))

    @staticmethod
    def _coords(polygon):
        return [[round(float(x), 9), round(float(y), 9)] for x, y in list(polygon.exterior.coords)[:-1]]
