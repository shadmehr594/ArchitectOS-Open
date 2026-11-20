"""Turn semantic relationships into fail-closed, floor-aware spatial connections."""

from __future__ import annotations


class ArchitecturalSpatialConnectivityReasonerV1:
    VERSION = "1.0"
    EPSILON = 1e-7

    def resolve(self, geometry, spatial_contract, intent=None):
        intent = intent if isinstance(intent, dict) else {}
        spaces = [item for item in geometry.get("spaces", []) if isinstance(item, dict)]
        registry = {}
        for space in spaces:
            for key in (space.get("id"), space.get("name"), space.get("canonical_name")):
                if key:
                    bucket = registry.setdefault(str(key).lower(), [])
                    if not any(item is space for item in bucket):
                        bucket.append(space)
        explicit = intent.get("relationships", [])
        # Authoritative project relations take precedence over a non-binding
        # knowledge relation for the same pair during de-duplication.
        relations = [item for item in explicit if isinstance(item, dict)] if isinstance(explicit, list) else []
        relations.extend((spatial_contract or {}).get("adjacency", []))
        result = []
        seen = set()
        vertical = [item for item in geometry.get("vertical_geometry", []) if isinstance(item, dict)
                    and item.get("geometry_status") == "resolved"]
        for index, relation in enumerate(relations):
            a = relation.get("from_space_id", relation.get("from"))
            b = relation.get("to_space_id", relation.get("to"))
            if not a or not b or str(a).lower() == str(b).lower():
                continue
            key = tuple(sorted((str(a).lower(), str(b).lower())))
            if key in seen:
                continue
            seen.add(key)
            left = registry.get(str(a).lower(), [])
            right = registry.get(str(b).lower(), [])
            contract = {
                "connection_id": relation.get("connection_id") or f"SC-{index+1:03d}",
                "from_space_id": a, "to_space_id": b,
                "from": a, "to": b,
                "relation_type": relation.get("relation_type", relation.get("relationship", relation.get("type", "adjacent"))),
                "required": relation.get("required") is True,
                "access_role": relation.get("access_role"),
                "privacy_class": relation.get("privacy_class"),
                "circulation_role": relation.get("circulation_role"),
                "direct_connection_required": relation.get("direct_connection_required") is True,
                "door_required": relation.get("door_required") is True,
                "shared_boundary_required": relation.get("shared_boundary_required") is True,
                "required_clear_width": relation.get("required_clear_width"),
                "required_clear_height": relation.get("required_clear_height"),
                "preferred_opening_point": relation.get("preferred_opening_point"),
                "opening_point_candidates": relation.get("opening_point_candidates", []),
                "opening_offset_from_interface_start": relation.get("opening_offset_from_interface_start"),
                "end_clearance": relation.get("end_clearance"),
                "privacy_violation": relation.get("privacy_violation") is True,
                "source": relation.get("source", "architectural_spatial_contract"),
                "evidence_status": relation.get("evidence_status", "inferred_program_relationship"),
                "geometry_status": "unresolved", "shared_boundary": None,
                "unresolved_evidence": [],
            }
            if len(left) != 1 or len(right) != 1:
                contract["unresolved_evidence"].append("unique_space_endpoints")
                result.append(contract); continue
            floor_a, floor_b = left[0].get("floor"), right[0].get("floor")
            contract["from_floor"], contract["to_floor"] = floor_a, floor_b
            if floor_a != floor_b:
                systems = [item for item in vertical if floor_a in item.get("served_levels", []) and floor_b in item.get("served_levels", [])]
                if len(systems) == 1:
                    system_id = systems[0].get("stair_id") or systems[0].get("id")
                    interfaces = systems[0].get("circulation_interfaces", [])
                    from_interface = next((i for i in interfaces if i.get("served_level") == floor_a and i.get("circulation_space_id") in (a, left[0].get("id"), left[0].get("name"))), None)
                    to_interface = next((i for i in interfaces if i.get("served_level") == floor_b and i.get("circulation_space_id") in (b, right[0].get("id"), right[0].get("name"))), None)
                    contract.update({"geometry_status": "resolved_vertical", "vertical_system_id": system_id,
                                     "from_vertical_interface_id": from_interface.get("interface_id") if from_interface else None,
                                     "to_vertical_interface_id": to_interface.get("interface_id") if to_interface else None,
                                     "from_vertical_interface_status": from_interface.get("geometry_status") if from_interface else "pending",
                                     "to_vertical_interface_status": to_interface.get("geometry_status") if to_interface else "pending"})
                else:
                    contract["unresolved_evidence"].append("unique_resolved_vertical_system")
                result.append(contract); continue
            shared = self._shared_boundary(left[0], right[0])
            if shared:
                contract.update({"shared_boundary": shared, "geometry_status": "resolved_shared_boundary"})
                offset = contract.get("opening_offset_from_interface_start")
                if isinstance(offset, (int, float)) and offset >= 0 and shared.get("length", 0) > 0:
                    start, end = shared["start"], shared["end"]
                    ratio = float(offset) / float(shared["length"])
                    if ratio <= 1.0:
                        contract["preferred_opening_point"] = [
                            start[0] + (end[0] - start[0]) * ratio,
                            start[1] + (end[1] - start[1]) * ratio,
                        ]
                        contract["opening_point_source"] = "explicit_offset_from_resolved_interface_start"
            elif contract["direct_connection_required"] or contract["shared_boundary_required"] or contract["door_required"]:
                contract["unresolved_evidence"].append("shared_boundary_or_connector_geometry")
            else:
                contract["geometry_status"] = "semantic_only"
            result.append(contract)
        unresolved = [item["connection_id"] for item in result if item["required"] and not str(item["geometry_status"]).startswith("resolved")]
        return {"version": self.VERSION, "connections": result,
                "status": "resolved" if not unresolved else "pending_required_connections",
                "unresolved_required_connections": unresolved,
                "source": "program_relationships_plus_generated_geometry"}

    def _shared_boundary(self, a, b):
        pa, pb = self._points(a), self._points(b)
        if len(pa) < 3 or len(pb) < 3:
            return None
        ba, bb = self._bbox(pa), self._bbox(pb)
        y0, y1 = max(ba[1], bb[1]), min(ba[3], bb[3])
        if y1-y0 > self.EPSILON and (abs(ba[2]-bb[0]) <= self.EPSILON or abs(bb[2]-ba[0]) <= self.EPSILON):
            x = bb[0] if abs(ba[2]-bb[0]) <= self.EPSILON else ba[0]
            return {"start": [x, y0], "end": [x, y1], "length": y1-y0}
        x0, x1 = max(ba[0], bb[0]), min(ba[2], bb[2])
        if x1-x0 > self.EPSILON and (abs(ba[3]-bb[1]) <= self.EPSILON or abs(bb[3]-ba[1]) <= self.EPSILON):
            y = bb[1] if abs(ba[3]-bb[1]) <= self.EPSILON else ba[1]
            return {"start": [x0, y], "end": [x1, y], "length": x1-x0}
        return None

    @staticmethod
    def _points(space):
        footprint = space.get("footprint")
        value = footprint.get("points") if isinstance(footprint, dict) else footprint
        return [[float(p[0]), float(p[1])] for p in value or [] if isinstance(p, (list, tuple)) and len(p) >= 2]

    @staticmethod
    def _bbox(points):
        return [min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)]
