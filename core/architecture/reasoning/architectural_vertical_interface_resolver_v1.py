"""Resolve stair-to-circulation interfaces from stair endpoints and room geometry."""

from __future__ import annotations


class ArchitecturalVerticalInterfaceResolverV1:
    VERSION = "1.0"
    EPS = 1e-7

    def resolve(self, spaces, vertical_geometry, requirements):
        spaces = [s for s in spaces or [] if isinstance(s, dict)]
        requirements = requirements if isinstance(requirements, dict) else {}
        stair_requirements = requirements.get("vertical_transport", {}).get("stairs", [])
        by_id = {r.get("id"): r for r in stair_requirements if isinstance(r, dict) and r.get("id")}
        interfaces = []
        for stair in vertical_geometry or []:
            if not isinstance(stair, dict) or stair.get("type") != "stair_geometry" or stair.get("geometry_status") != "resolved":
                continue
            stair_id = stair.get("stair_id") or stair.get("id") or stair.get("name")
            requirement = by_id.get(stair_id, {})
            if not requirement:
                served = set(stair.get("served_levels", []))
                matching_requirements = [r for r in stair_requirements if isinstance(r, dict)
                                         and {r.get("from_level"), r.get("to_level")} == served]
                requirement = matching_requirements[0] if len(matching_requirements) == 1 else {}
            declared = requirement.get("circulation_interfaces", [])
            stair_interfaces = []
            for index, item in enumerate(declared if isinstance(declared, list) else []):
                if not isinstance(item, dict): continue
                level = item.get("level")
                space_id = item.get("circulation_space_id")
                point = self._endpoint(stair, level)
                matching = [s for s in spaces if self._space_id(s) == space_id and s.get("floor") == level]
                status = "pending"
                unresolved = []
                if item.get("evidence_status") not in ("authoritative", "resolved"):
                    unresolved.append("authoritative_stair_interface_requirement")
                elif len(matching) != 1:
                    unresolved.append("unique_circulation_space")
                elif point is None:
                    unresolved.append("stair_endpoint_for_level")
                elif not self._inside_or_edge(point, self._points(matching[0].get("footprint"))):
                    unresolved.append("stair_endpoint_within_circulation_space")
                else:
                    status = "resolved"
                contract = {
                    "interface_id": item.get("interface_id") or f"{stair_id}-INTERFACE-{index+1}",
                    "vertical_system_id": stair_id,
                    "requirement_id": requirement.get("id"), "served_level": level,
                    "circulation_space_id": space_id, "interface_role": item.get("interface_role"),
                    "interface_point": point, "geometry_status": status,
                    "source": item.get("source", "project_vertical_interface_requirement"),
                    "evidence_status": item.get("evidence_status"), "unresolved_evidence": unresolved,
                }
                interfaces.append(contract); stair_interfaces.append(contract)
            stair["circulation_interfaces"] = stair_interfaces
            stair["interface_status"] = "resolved" if stair_interfaces and all(i["geometry_status"] == "resolved" for i in stair_interfaces) else "pending"
        return {"version": self.VERSION, "interfaces": interfaces,
                "status": "resolved" if interfaces and all(i["geometry_status"] == "resolved" for i in interfaces) else "pending",
                "source": "resolved_stair_endpoints_plus_explicit_circulation_membership"}

    @staticmethod
    def _space_id(space): return space.get("space_id") or space.get("id") or space.get("name")

    @staticmethod
    def _endpoint(stair, level):
        if level == stair.get("start_level"):
            return list(stair.get("start_point", [])[:2]) or None
        if level == stair.get("end_level"):
            return list(stair.get("end_point", [])[:2]) or None
        return None

    @staticmethod
    def _points(value):
        if isinstance(value, dict): value = value.get("points") or value.get("polygon")
        return [[float(p[0]), float(p[1])] for p in value or [] if isinstance(p, (list, tuple)) and len(p) >= 2]

    @classmethod
    def _inside_or_edge(cls, point, poly):
        if len(poly) < 3: return False
        for a, b in zip(poly, poly[1:] + poly[:1]):
            cross = abs((b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0]))
            if cross <= cls.EPS and min(a[0],b[0])-cls.EPS <= point[0] <= max(a[0],b[0])+cls.EPS and min(a[1],b[1])-cls.EPS <= point[1] <= max(a[1],b[1])+cls.EPS:
                return True
        inside = False; j = len(poly)-1
        for i, (xi, yi) in enumerate(poly):
            xj, yj = poly[j]
            if (yi > point[1]) != (yj > point[1]) and point[0] < (xj-xi)*(point[1]-yi)/(yj-yi)+xi: inside = not inside
            j = i
        return inside
