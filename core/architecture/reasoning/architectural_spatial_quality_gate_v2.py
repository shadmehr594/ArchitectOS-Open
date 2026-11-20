"""Evidence-driven final spatial quality gate; it never generates geometry."""

from __future__ import annotations

from collections import defaultdict, deque


class ArchitecturalSpatialQualityGateV2:
    VERSION = "2.0"

    REGENERABLE = {
        "required_shared_boundary_missing", "privacy_violation", "isolated_space",
        "dead_end_circulation", "circulation_interface_missing",
        "room_outside_buildable_boundary", "room_overlap",
    }

    def evaluate(self, geometry, requirements=None):
        geometry = geometry if isinstance(geometry, dict) else {}
        requirements = requirements if isinstance(requirements, dict) else {}
        result = self._base()
        if requirements.get("enforce") is not True:
            self._unresolved(result, "explicit_spatial_quality_enforcement")
            return self._finish(result)

        spaces = [s for s in geometry.get("spaces", []) if isinstance(s, dict)]
        space_ids, aliases = self._space_registry(spaces)
        connections = self._connections(geometry)
        openings = [o for o in geometry.get("openings", []) if isinstance(o, dict)]
        walls = {w.get("wall_id"): w for w in geometry.get("physical_walls", [])
                 if isinstance(w, dict) and w.get("wall_id")}
        protected = [z for z in geometry.get("architectural_protected_zones", []) if isinstance(z, dict)]
        graph = {sid: set() for sid in space_ids}

        self._required_connections(result, connections, openings, walls, graph, aliases)
        self._physical_doors(result, openings, space_ids, aliases, walls)
        if requirements.get("required_main_entrance") is True:
            main = [opening for opening in openings
                    if opening.get("category") == "main_entrance"
                    and opening.get("geometry_status") == "resolved"
                    and self._opening_is_physical(opening, walls)]
            if len(main) == 1:
                self._pass(result, "required_main_entrance")
            else:
                self._critical(result, "required_main_entrance_unresolved", opening=(main[0].get("opening_id") if len(main) > 1 else None))
        self._windows(result, geometry, openings, walls)
        self._privacy(result, connections, requirements, graph, aliases)
        self._reachability(result, graph, spaces, requirements, aliases)
        self._circulation(result, graph, spaces, requirements, aliases)
        self._parking(result, geometry)
        self._protected_zone_conflicts(result, geometry, protected)
        self._geometric_quality(result, geometry, spaces, openings, walls, requirements)

        result["evidence_summary"] = {
            "space_count": len(spaces), "connection_count": len(connections),
            "physical_opening_count": len([o for o in openings if o.get("geometry_status") == "resolved"]),
            "traversable_edge_count": sum(len(v) for v in graph.values()) // 2,
            "protected_zone_count": len(protected),
        }
        return self._finish(result)

    def _required_connections(self, out, connections, openings, walls, graph, aliases):
        for c in connections:
            if c.get("required") is not True:
                continue
            cid = c.get("connection_id")
            a, b = self._resolve_space(c.get("from_space_id") or c.get("from"), aliases), self._resolve_space(c.get("to_space_id") or c.get("to"), aliases)
            out["affected_connections"].append(cid)
            if not a or not b:
                self._unresolved(out, "required_connection_space_endpoints", connection=cid)
                continue
            status = str(c.get("geometry_status", ""))
            if status == "resolved_vertical":
                vertical_id = c.get("vertical_system_id")
                out["affected_vertical_systems"].append(vertical_id)
                if not (c.get("from_vertical_interface_status") == "resolved"
                        and c.get("to_vertical_interface_status") == "resolved"):
                    self._critical(out, "vertical_system_interface_disconnected", [a, b], cid,
                                   regenerable=False)
                    continue
                graph[a].add(b); graph[b].add(a)
                self._pass(out, f"vertical_connection:{cid}")
                continue
            if c.get("door_required") is True:
                opening = next((o for o in openings if o.get("connection_id") == cid and self._opening_is_physical(o, walls)), None)
                if (not status.startswith("resolved") or c.get("physical_connection_status") != "resolved" or not opening):
                    self._critical(out, "required_connection_without_physical_opening", [a, b], cid,
                                   c.get("opening_id"), regenerable=False)
                    continue
                graph[a].add(b); graph[b].add(a)
                self._pass(out, f"required_connection:{cid}")
            elif status in ("semantic_only", "resolved_shared_boundary", "resolved_circulation_interface", "resolved_vertical"):
                graph[a].add(b); graph[b].add(a)
                self._pass(out, f"required_connection:{cid}")
            elif c.get("unresolved_evidence"):
                self._unresolved(out, "required_connection_geometry", connection=cid)
            else:
                self._critical(out, "required_shared_boundary_missing", [a, b], cid, regenerable=True)

    def _physical_doors(self, out, openings, space_ids, aliases, walls):
        for opening in openings:
            if opening.get("type") not in ("door", "vehicle_entrance") or opening.get("geometry_status") != "resolved":
                continue
            oid = opening.get("opening_id") or opening.get("id")
            if not self._opening_is_physical(opening, walls):
                self._critical(out, "resolved_door_without_physical_wall_interruption", opening=oid)
                continue
            a = self._resolve_space(opening.get("connects_from") or opening.get("from_space_id"), aliases)
            b = self._resolve_space(opening.get("connects_to") or opening.get("to_space_id"), aliases)
            exterior = opening.get("exterior_host_status") == "resolved" or opening.get("opening_role") in (
                "main_entrance", "exterior_entrance", "vehicle_entrance") or opening.get("type") == "vehicle_entrance"
            if opening.get("type") == "vehicle_entrance" and exterior:
                self._pass(out, f"vehicle_opening_endpoint:{oid}")
                continue
            if not ((a in space_ids and b in space_ids) or ((a in space_ids or b in space_ids) and exterior)):
                self._critical(out, "door_to_nowhere", [v for v in (a, b) if v], opening=oid)
            else:
                self._pass(out, f"door_endpoint:{oid}")

    def _windows(self, out, geometry, openings, walls):
        physical = [o for o in openings if o.get("type") == "window" and o.get("geometry_status") == "resolved"]
        for window in physical:
            oid = window.get("opening_id") or window.get("id")
            wall = walls.get(window.get("host_wall_id"), {})
            if wall.get("is_exterior") is not True or not window.get("served_space_id") or window.get("exterior_host_status") != "resolved" or not self._opening_is_physical(window, walls):
                self._critical(out, "invalid_physical_exterior_window", [window.get("served_space_id")], opening=oid)
            else:
                self._pass(out, f"exterior_window:{oid}")
        reqs = geometry.get("project_requirements", {}).get("window_requirements", [])
        for req in reqs if isinstance(reqs, list) else []:
            if not isinstance(req, dict) or req.get("required") is not True:
                continue
            if not any(w.get("served_space_id") == req.get("space_id") for w in physical):
                if req.get("evidence_status") in ("authoritative", "resolved"):
                    self._critical(out, "required_exterior_window_unresolved", [req.get("space_id")], regenerable=False)
                else:
                    self._unresolved(out, "required_exterior_window_evidence", space=req.get("space_id"))

    def _privacy(self, out, connections, requirements, graph, aliases):
        forbidden = requirements.get("privacy_forbidden_direct_connections", [])
        forbidden_pairs = {frozenset(self._resolve_space(v, aliases) for v in pair) for pair in forbidden
                           if isinstance(pair, (list, tuple)) and len(pair) == 2}
        for c in connections:
            a, b = self._resolve_space(c.get("from_space_id") or c.get("from"), aliases), self._resolve_space(c.get("to_space_id") or c.get("to"), aliases)
            violation = c.get("privacy_violation") is True or (a and b and frozenset((a, b)) in forbidden_pairs and b in graph.get(a, set()))
            if violation:
                self._critical(out, "privacy_violation", [a, b], c.get("connection_id"), regenerable=True)

    def _reachability(self, out, graph, spaces, requirements, aliases):
        entrance = self._resolve_space(requirements.get("entrance_space"), aliases)
        required = {self._space_id(s) for s in spaces if s.get("required") is True}
        required.update(self._resolve_space(v, aliases) for v in requirements.get("required_reachable_spaces", []))
        required.discard(None)
        if entrance:
            reached = self._walk(graph, entrance)
            if not graph.get(entrance):
                self._critical(out, "entrance_disconnected_from_circulation", [entrance], regenerable=True)
            for sid in sorted(required - reached):
                self._critical(out, "required_space_unreachable", [sid], regenerable=True)
        exempt = {self._resolve_space(v, aliases) for v in requirements.get("isolation_exempt_spaces", [])}
        for sid in sorted(graph):
            if not graph[sid] and sid not in exempt:
                self._critical(out, "isolated_space", [sid], regenerable=True)

    def _circulation(self, out, graph, spaces, requirements, aliases):
        circulation = [self._space_id(s) for s in spaces if self._is_circulation(s)]
        max_dead = requirements.get("maximum_dead_end_connections")
        dead = [sid for sid in circulation if len(graph.get(sid, ())) <= 1]
        if isinstance(max_dead, int) and len(dead) > max_dead:
            self._critical(out, "dead_end_circulation", dead, regenerable=True)
        for sid in circulation:
            if not graph.get(sid):
                self._critical(out, "isolated_circulation", [sid], regenerable=True)

    def _parking(self, out, geometry):
        reqs = geometry.get("project_requirements", {}).get("parking_pedestrian_requirements", [])
        if not reqs:
            return
        p = geometry.get("site_geometry", {}).get("parking_pedestrian_connection", {})
        complete = (p.get("parking_to_building_status") == "resolved" and p.get("geometry_status") == "resolved"
                    and p.get("wall_conflict_status") == "clear" and p.get("stall_conflict_status") == "clear"
                    and p.get("ramp_conflict_status") == "clear" and p.get("protected_zone_status") == "clear"
                    and bool(p.get("target_circulation_space_id") or p.get("target_stair_core_id"))
                    and p.get("vertical_connection_status") in ("resolved", "not_required"))
        if complete:
            self._pass(out, "parking_to_building_chain")
        elif p.get("unresolved_evidence") or p.get("geometry_status") in (None, "pending", "pending_tie"):
            self._unresolved(out, "parking_to_building_chain_evidence")
            out["affected_parking_connections"].append(p.get("connection_id"))
        else:
            self._critical(out, "parking_to_building_chain_invalid", parking=p.get("connection_id"), regenerable=False)

    def _protected_zone_conflicts(self, out, geometry, zones):
        paths = []
        p = geometry.get("site_geometry", {}).get("parking_pedestrian_connection", {})
        paths.extend(p.get("path_corridor") or [])
        paths.extend(x.get("polygon") for x in geometry.get("circulation_paths", []) if isinstance(x, dict) and x.get("polygon"))
        for path in paths:
            for zone in zones:
                poly = zone.get("polygon") or zone.get("points")
                if poly and self._polygons_intersect(path, poly):
                    conflict = {"path": p.get("connection_id"), "zone": zone.get("id") or zone.get("type")}
                    out["protected_zone_conflicts"].append(conflict)
                    self._critical(out, "circulation_intersects_protected_zone", parking=p.get("connection_id"), regenerable=False)

    def _geometric_quality(self, out, geometry, spaces, openings, walls, requirements):
        polygons = [(self._space_id(s), s.get("floor"), self._points(s.get("footprint"))) for s in spaces]
        for i, (a, floor_a, pa) in enumerate(polygons):
            for b, floor_b, pb in polygons[i + 1:]:
                if floor_a == floor_b and pa and pb and self._polygons_overlap_area(pa, pb):
                    self._critical(out, "room_overlap", [a, b], regenerable=True)
        boundary = self._points(geometry.get("buildable_boundary") or requirements.get("buildable_boundary"))
        if boundary:
            for sid, _floor, poly in polygons:
                if poly and not all(self._inside_or_edge(p, boundary) for p in poly):
                    self._critical(out, "room_outside_buildable_boundary", [sid], regenerable=True)
        minimum = requirements.get("minimum_usable_dimensions", {})
        for s in spaces:
            rule = minimum.get(s.get("name"), minimum.get(self._space_id(s), {})) if isinstance(minimum, dict) else {}
            fp = s.get("footprint", {})
            if rule and isinstance(fp, dict):
                for key in ("width", "depth"):
                    if isinstance(rule.get(key), (int, float)) and (not isinstance(fp.get(key), (int, float)) or fp[key] < rule[key]):
                        self._critical(out, "minimum_usable_dimension", [self._space_id(s)], regenerable=False)
        for o in openings:
            if o.get("geometry_status") == "resolved" and not self._opening_is_physical(o, walls):
                self._critical(out, "unresolved_or_outside_host_opening_published", opening=o.get("opening_id") or o.get("id"))
        for path in geometry.get("circulation_paths", []):
            if not isinstance(path, dict): continue
            line = path.get("path_centerline") or path.get("centerline") or []
            for a, b in zip(line, line[1:]):
                for wall in walls.values():
                    hit = self._line_intersection(a, b, wall.get("start"), wall.get("end"))
                    allowed = hit and any(self._point_on_segment(hit, o.get("opening_start"), o.get("opening_end"))
                                          for o in openings if o.get("geometry_status") == "resolved"
                                          and o.get("host_wall_id") == wall.get("wall_id"))
                    if hit and not allowed:
                        self._critical(out, "circulation_path_through_solid_wall", opening=path.get("id"), regenerable=False)

    def _finish(self, out):
        out["affected_spaces"] = self._unique(out["affected_spaces"])
        out["affected_connections"] = self._unique(out["affected_connections"])
        out["affected_openings"] = self._unique(out["affected_openings"])
        out["affected_parking_connections"] = self._unique(out["affected_parking_connections"])
        out["affected_vertical_systems"] = self._unique(out["affected_vertical_systems"])
        total = len(out["passed_constraints"]) + len(out["critical_failures"]) + len(out["unresolved_constraints"])
        out["quality_score"] = round(100.0 * len(out["passed_constraints"]) / total, 3) if total else 0.0
        out["status"] = "failed" if out["critical_failures"] else "unresolved" if out["unresolved_constraints"] else "passed"
        out["architectural_authority"] = out["status"] == "passed"
        out["regeneration_recommended"] = bool(out["regeneration_requests"])
        return out

    @staticmethod
    def _base():
        return {"version": "2.0", "status": "unresolved", "quality_score": 0.0,
                "critical_failures": [], "noncritical_failures": [], "unresolved_constraints": [],
                "passed_constraints": [], "affected_spaces": [], "affected_connections": [],
                "affected_openings": [], "affected_vertical_systems": [], "affected_parking_connections": [],
                "protected_zone_conflicts": [], "regeneration_recommended": False,
                "regeneration_requests": [], "evidence_summary": {}, "architectural_authority": False,
                "source": "architectural_spatial_quality_gate_v2", "fail_closed": True}

    def _critical(self, out, kind, spaces=None, connection=None, opening=None, parking=None, regenerable=False):
        item = {"type": kind, "affected_spaces": [s for s in spaces or [] if s]}
        if connection: item["connection_id"] = connection; out["affected_connections"].append(connection)
        if opening: item["opening_id"] = opening; out["affected_openings"].append(opening)
        if parking: item["parking_connection_id"] = parking; out["affected_parking_connections"].append(parking)
        out["affected_spaces"].extend(item["affected_spaces"]); out["critical_failures"].append(item)
        if regenerable and kind in self.REGENERABLE:
            out["regeneration_requests"].append({"failed_constraint": kind, "affected_spaces": item["affected_spaces"],
                                                  "connection_id": connection, "source_evidence": "spatial_quality_gate_v2"})

    @staticmethod
    def _unresolved(out, kind, **evidence): out["unresolved_constraints"].append({"type": kind, **evidence})
    @staticmethod
    def _pass(out, name): out["passed_constraints"].append(name)
    @staticmethod
    def _unique(values): return list(dict.fromkeys(v for v in values if v is not None))
    @staticmethod
    def _space_id(space): return space.get("space_id") or space.get("id") or space.get("name")

    def _space_registry(self, spaces):
        ids = {self._space_id(s) for s in spaces if self._space_id(s)}; aliases = {}
        for s in spaces:
            sid = self._space_id(s)
            for value in (sid, s.get("id"), s.get("name"), s.get("canonical_name")):
                if value: aliases[str(value).lower()] = sid
        return ids, aliases

    @staticmethod
    def _resolve_space(value, aliases): return aliases.get(str(value).lower()) if value is not None else None
    @staticmethod
    def _connections(geometry):
        contract = geometry.get("spatial_connection_contract", {})
        return [c for c in (contract.get("connections") if isinstance(contract, dict) else None) or geometry.get("connections", []) if isinstance(c, dict)]

    @staticmethod
    def _is_circulation(space):
        return space.get("circulation_role") is not None or str(space.get("type", "")).lower() in ("corridor", "circulation", "lobby") or "corridor" in str(space.get("name", "")).lower()

    @staticmethod
    def _walk(graph, start):
        seen = {start}; queue = deque([start])
        while queue:
            for nxt in graph.get(queue.popleft(), ()):
                if nxt not in seen: seen.add(nxt); queue.append(nxt)
        return seen

    @staticmethod
    def _opening_is_physical(opening, walls):
        wall = walls.get(opening.get("host_wall_id"))
        oid = opening.get("opening_id") or opening.get("id")
        if not wall or not opening.get("opening_center") or not opening.get("opening_start") or not opening.get("opening_end"):
            return False
        return any((p.get("opening_id") or p.get("id")) == oid and p.get("geometry_status", "resolved") == "resolved"
                   for p in wall.get("physical_openings", []))

    @staticmethod
    def _points(value):
        if isinstance(value, dict): value = value.get("points") or value.get("polygon")
        return [[float(p[0]), float(p[1])] for p in value or [] if isinstance(p, (list, tuple)) and len(p) >= 2]

    @classmethod
    def _polygons_intersect(cls, a, b):
        a, b = cls._points(a), cls._points(b)
        return bool(a and b and (any(cls._inside_or_edge(p, b) for p in a) or any(cls._inside_or_edge(p, a) for p in b)
               or any(cls._segments(a[i], a[(i+1)%len(a)], b[j], b[(j+1)%len(b)]) for i in range(len(a)) for j in range(len(b)))))

    @classmethod
    def _polygons_overlap_area(cls, a, b):
        # Boundary contact is allowed; strict interior containment or proper crossing means area overlap.
        return any(cls._inside_strict(p, b) for p in a) or any(cls._inside_strict(p, a) for p in b) or any(
            cls._segments(a[i], a[(i+1)%len(a)], b[j], b[(j+1)%len(b)]) for i in range(len(a)) for j in range(len(b)))

    @staticmethod
    def _segments(a, b, c, d):
        def orient(p, q, r): return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
        return orient(a,b,c)*orient(a,b,d) < -1e-9 and orient(c,d,a)*orient(c,d,b) < -1e-9

    @classmethod
    def _inside_strict(cls, point, poly):
        if cls._on_boundary(point, poly): return False
        return cls._inside(point, poly)

    @classmethod
    def _inside_or_edge(cls, point, poly): return cls._on_boundary(point, poly) or cls._inside(point, poly)

    @staticmethod
    def _on_boundary(point, poly):
        for a, b in zip(poly, poly[1:] + poly[:1]):
            cross = abs((b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0]))
            if cross <= 1e-7 and min(a[0],b[0])-1e-7 <= point[0] <= max(a[0],b[0])+1e-7 and min(a[1],b[1])-1e-7 <= point[1] <= max(a[1],b[1])+1e-7:
                return True
        return False

    @staticmethod
    def _inside(point, poly):
        inside = False; j = len(poly)-1
        for i in range(len(poly)):
            xi, yi = poly[i]; xj, yj = poly[j]
            if (yi > point[1]) != (yj > point[1]) and point[0] < (xj-xi)*(point[1]-yi)/(yj-yi)+xi: inside = not inside
            j = i
        return inside

    @classmethod
    def _line_intersection(cls, a, b, c, d):
        if not all(isinstance(p, (list, tuple)) and len(p) >= 2 for p in (a, b, c, d)): return None
        x1,y1=a[:2]; x2,y2=b[:2]; x3,y3=c[:2]; x4,y4=d[:2]
        den=(x1-x2)*(y3-y4)-(y1-y2)*(x3-x4)
        if abs(den) <= 1e-9: return None
        p=[((x1*y2-y1*x2)*(x3-x4)-(x1-x2)*(x3*y4-y3*x4))/den,
           ((x1*y2-y1*x2)*(y3-y4)-(y1-y2)*(x3*y4-y3*x4))/den]
        return p if cls._point_on_segment(p,a,b) and cls._point_on_segment(p,c,d) else None

    @staticmethod
    def _point_on_segment(p, a, b):
        if not all(isinstance(v, (list, tuple)) and len(v) >= 2 for v in (p, a, b)): return False
        return (abs((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])) <= 1e-7
                and min(a[0],b[0])-1e-7 <= p[0] <= max(a[0],b[0])+1e-7
                and min(a[1],b[1])-1e-7 <= p[1] <= max(a[1],b[1])+1e-7)
