"""Resolve selected vehicle access against authoritative site geometry."""

from copy import deepcopy
from math import hypot

from core.spatial.ramp_spatial_placement_engine import RampSpatialPlacementEngine
from core.geometry.ramp_3d_geometry_engine import Ramp3DGeometryEngine
from core.architecture.geometry.architectural_physical_opening_resolver_v1 import (
    ArchitecturalPhysicalOpeningResolverV1,
)
from core.architecture.geometry.architectural_ramp_clearance_resolver_v1 import (
    ArchitecturalRampClearanceResolverV1,
)
from core.architecture.geometry.parking_arrival_maneuvering_resolver_v1 import (
    ParkingArrivalManeuveringResolverV1,
)
from core.architecture.geometry.parking_aisle_stall_topology_resolver_v1 import (
    ParkingAisleStallTopologyResolverV1,
)
from core.architecture.geometry.architectural_cad_drawing_resolver_v1 import ArchitecturalCadDrawingResolverV1
from core.architecture.geometry.architectural_section_intelligence_v1 import ArchitecturalSectionIntelligenceV1
from core.architecture.geometry.parking_pedestrian_connection_resolver_v1 import ParkingPedestrianConnectionResolverV1
from core.architecture.reasoning.architectural_completion_gate_v2 import ArchitecturalCompletionGateV2
from core.architecture.reasoning.architectural_spatial_quality_gate_v2 import ArchitecturalSpatialQualityGateV2


class VehicleAccessGeometryResolverV1:
    VERSION = "1.0"

    @staticmethod
    def _point(value):
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            if all(isinstance(item, (int, float)) for item in value[:2]):
                return [float(value[0]), float(value[1])]
        return None

    def _resolve_edge(self, access_id, candidate, site):
        edges = site.get("parcel_edges", [])
        if not isinstance(edges, list):
            return None
        requested_edge_id = candidate.get("parcel_edge_id")
        requested_index = candidate.get("edge_index")
        for index, edge in enumerate(edges):
            if not isinstance(edge, dict):
                continue
            identity_match = (
                edge.get("access_id") == access_id
                or (requested_edge_id is not None and edge.get("id") == requested_edge_id)
                or (requested_index is not None and edge.get("edge_index", index) == requested_index)
            )
            if not identity_match:
                continue
            start = self._point(edge.get("start") or edge.get("edge_start"))
            end = self._point(edge.get("end") or edge.get("edge_end"))
            edge_index = edge.get("edge_index", index)
            boundary = site.get("parcel_boundary", [])
            if (start is None or end is None) and isinstance(boundary, list) and len(boundary) >= 3:
                try:
                    start = self._point(boundary[int(edge_index)])
                    end = self._point(boundary[(int(edge_index) + 1) % len(boundary)])
                except (TypeError, ValueError, IndexError):
                    start = end = None
            if start is None or end is None or edge.get("confirmed") is False:
                return None
            length = hypot(end[0] - start[0], end[1] - start[1])
            if length <= 0:
                return None
            return {
                "access_id": access_id,
                "parcel_edge_id": edge.get("id"),
                "edge_index": edge_index,
                "side": candidate.get("side"),
                "edge_start": start,
                "edge_end": end,
                "edge_length": length,
                "access_elevation": candidate.get("access_elevation"),
                "target_elevation": candidate.get("target_elevation"),
                "access_mode": candidate.get("access_mode"),
                "geometry_resolution_status": "resolved",
                "geometry_resolution_reason": "selected_access_id_matched_authoritative_parcel_edge",
                "source_evidence": {"candidate": candidate, "parcel_edge": edge},
            }
        return None

    @staticmethod
    def _bbox_intersects(a, b):
        return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])

    def _entrance(self, edge, width, conflict_zones):
        if not isinstance(width, (int, float)) or width <= 0 or width > edge["edge_length"]:
            return {"entrance_status": "pending", "reason": "clear_width_unresolved_or_exceeds_edge"}
        start, end = edge["edge_start"], edge["edge_end"]
        ux = (end[0] - start[0]) / edge["edge_length"]
        uy = (end[1] - start[1]) / edge["edge_length"]
        half = width / 2.0
        candidates = [0.25, 0.5, 0.75]
        for ratio in candidates:
            distance = max(half, min(edge["edge_length"] - half, edge["edge_length"] * ratio))
            center = [start[0] + ux * distance, start[1] + uy * distance]
            entrance_start = [center[0] - ux * half, center[1] - uy * half]
            entrance_end = [center[0] + ux * half, center[1] + uy * half]
            entrance_bbox = [
                min(entrance_start[0], entrance_end[0]) - 0.01,
                min(entrance_start[1], entrance_end[1]) - 0.01,
                max(entrance_start[0], entrance_end[0]) + 0.01,
                max(entrance_start[1], entrance_end[1]) + 0.01,
            ]
            blocked = False
            for zone in conflict_zones:
                bbox = zone.get("bbox") if isinstance(zone, dict) else None
                if isinstance(bbox, (list, tuple)) and len(bbox) == 4 and self._bbox_intersects(entrance_bbox, bbox):
                    blocked = True
                    break
            if not blocked:
                return {
                    "entrance_center": center,
                    "entrance_start": entrance_start,
                    "entrance_end": entrance_end,
                    "clear_width": float(width),
                    "entrance_status": "resolved",
                    "evidence_used": ["authoritative_parcel_edge", "corner_clearance", "conflict_zones_checked"],
                }
        return {"entrance_status": "pending", "reason": "no_conflict_free_entrance_window"}

    def _coordinated_entrance(self, edge, candidate, minimum_width):
        interval = candidate.get("entrance_interval") or candidate.get("access_interval")
        if not isinstance(interval, (list, tuple)) or len(interval) != 2:
            return {"entrance_status": "pending", "reason": "coordinated_entrance_interval_missing"}
        start, end = self._point(interval[0]), self._point(interval[1])
        if start is None or end is None:
            return {"entrance_status": "pending", "reason": "coordinated_entrance_interval_invalid"}
        edge_start, edge_end = edge["edge_start"], edge["edge_end"]
        def on_edge(point):
            cross = ((point[0] - edge_start[0]) * (edge_end[1] - edge_start[1])
                     - (point[1] - edge_start[1]) * (edge_end[0] - edge_start[0]))
            return abs(cross) <= 1e-7 and (
                min(edge_start[0], edge_end[0]) - 1e-7 <= point[0] <= max(edge_start[0], edge_end[0]) + 1e-7
                and min(edge_start[1], edge_end[1]) - 1e-7 <= point[1] <= max(edge_start[1], edge_end[1]) + 1e-7
            )
        width = hypot(end[0] - start[0], end[1] - start[1])
        if not on_edge(start) or not on_edge(end) or width <= 0:
            return {"entrance_status": "pending", "reason": "coordinated_interval_not_on_selected_edge"}
        if isinstance(minimum_width, (int, float)) and width + 1e-7 < minimum_width:
            return {"entrance_status": "pending", "reason": "coordinated_interval_below_required_clear_width"}
        return {
            "entrance_center": [(start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0],
            "entrance_start": start,
            "entrance_end": end,
            "clear_width": width,
            "entrance_status": "resolved",
            "evidence_used": ["resolved_site_access_coordination", "coordinated_entrance_interval"],
        }

    @staticmethod
    def _corridor_polygon(start, end, width):
        length = hypot(end[0] - start[0], end[1] - start[1])
        if length <= 0:
            return None
        nx = -(end[1] - start[1]) / length * width / 2.0
        ny = (end[0] - start[0]) / length * width / 2.0
        return [[start[0]+nx, start[1]+ny], [end[0]+nx, end[1]+ny],
                [end[0]-nx, end[1]-ny], [start[0]-nx, start[1]-ny]]

    def _pending(self, geometry, status, reason, edge=None, conflict_status="conflict_check_pending"):
        return {
            "status": status,
            "reason": reason,
            "selected_access_geometry": edge,
            "entrance": None,
            "driveway": None,
            "ramp": None,
            "conflict_validation": {"status": conflict_status},
            "geometry_generation_allowed": False,
            "driveway_geometry_allowed": False,
            "ramp_geometry_allowed": False,
            "architectural_geometry": geometry,
        }

    def resolve(self, selection, architectural_geometry, technical=None):
        selection = selection or {}
        geometry = deepcopy(architectural_geometry or {})
        technical = technical or {}
        project_requirements = geometry.get("project_requirements", {})
        vehicle_requirements = (
            project_requirements.get("vehicle_access", {})
            if isinstance(project_requirements, dict) else {}
        )
        if not isinstance(vehicle_requirements, dict):
            vehicle_requirements = {}
        selected_access_id = selection.get("selected_access_id")
        requirement_items = vehicle_requirements.get("entrances", [])
        if isinstance(requirement_items, list):
            matches = [item for item in requirement_items if isinstance(item, dict)
                       and item.get("access_id") == selected_access_id]
            if len(matches) == 1 and matches[0].get("evidence_status") in ("authoritative", "resolved"):
                requirement = matches[0]
                technical = dict(technical)
                technical.setdefault("clear_width", requirement.get("clear_width"))
                technical.setdefault("vehicle_opening_height", requirement.get("clear_height"))
        if selection.get("status") != "resolved" or not selection.get("geometry_generation_allowed"):
            return self._pending(geometry, "selected_access_geometry_unresolved", "access_selection_not_resolved")
        site = geometry.get("site_geometry", {})
        if not isinstance(site, dict):
            return self._pending(geometry, "selected_access_geometry_unresolved", "authoritative_site_geometry_missing")
        candidate = selection.get("selected_access_candidate", {}) or {}
        access_id = selection.get("selected_access_id") or candidate.get("access_id")
        edge = self._resolve_edge(access_id, candidate, site)
        if edge is None:
            return self._pending(geometry, "selected_access_geometry_unresolved", "selected_access_id_not_matched_to_parcel_edge")
        if "conflict_zones" not in site:
            return self._pending(geometry, "conflict_check_pending", "conflict_evidence_missing", edge)
        zones = site.get("conflict_zones")
        if not isinstance(zones, list):
            return self._pending(geometry, "conflict_check_pending", "conflict_evidence_invalid", edge)
        zones = list(zones)
        for zone_key in (
            "protected_zones",
            "separation_zones",
            "pedestrian_access_zones",
            "commercial_entrance_zones",
            "residential_entrance_zones",
            "parking_circulation_zones",
        ):
            available_zones = site.get(zone_key, [])
            if isinstance(available_zones, list):
                zones.extend(available_zones)
        vertical_geometry = geometry.get("vertical_geometry", [])
        if isinstance(vertical_geometry, list):
            zones.extend(
                item for item in vertical_geometry
                if isinstance(item, dict)
                and item.get("protected_zone") is True
                and isinstance(item.get("bbox"), (list, tuple))
            )
        width = technical.get("clear_width") or technical.get("minimum_vehicle_ramp_width")
        coordination = selection.get("site_access_coordination")
        # Architecture-first publication requires an interval designed by the
        # upstream candidate/co-ordination contracts.  The historical 25/50/75
        # sampler is intentionally not an authority for physical geometry.
        entrance = self._coordinated_entrance(edge, candidate, width)
        if entrance.get("entrance_status") != "resolved":
            return self._pending(geometry, "vehicle_entrance_pending", entrance.get("reason"), edge, "conflict_detected")
        width = entrance.get("clear_width", width)
        targets = site.get("parking_access_points", {})
        target = targets.get(candidate.get("target_level")) if isinstance(targets, dict) else None
        if target is None:
            parking_target_requirements = [item for item in project_requirements.get("parking_requirements", [])
                                           if isinstance(item, dict)
                                           and item.get("served_level") == candidate.get("target_level")
                                           and item.get("evidence_status") in ("authoritative", "resolved")
                                           and item.get("parking_target_source")]
            if len(parking_target_requirements) == 1:
                target = parking_target_requirements[0].get("parking_target_point")
        target = self._point(target or candidate.get("target_point"))
        if target is None:
            return self._pending(geometry, "driveway_geometry_unresolved", "parking_access_point_missing", edge)
        start = entrance["entrance_center"]
        if selection.get("ramp_geometry_allowed"):
            required_run = candidate.get("required_run")
            target_distance = hypot(target[0]-start[0], target[1]-start[1])
            if (not isinstance(required_run, (int, float)) or required_run <= 0
                    or abs(target_distance-float(required_run)) > 1e-6):
                return self._pending(
                    geometry, "ramp_geometry_unresolved",
                    "parking_arrival_must_equal_resolved_ramp_exit", edge,
                )
        polygon = self._corridor_polygon(start, target, width)
        driveway = {
            "type": "vehicle_driveway", "access_id": access_id,
            "start_point": start, "end_point": target, "centerline": [start, target],
            "width": float(width), "polygon": polygon,
            "start_z": candidate.get("access_elevation"), "end_z": candidate.get("target_elevation"),
            "access_mode": candidate.get("access_mode"), "geometry_status": "resolved",
            "protected_zone": True, "served_level": candidate.get("target_level"),
            "source": "selected_access_geometry_resolver_v1",
        }
        opening_height = technical.get("vehicle_opening_height")
        wall_opening = ArchitecturalPhysicalOpeningResolverV1().vehicle_opening(
            geometry.get("physical_walls", []), driveway, width, opening_height
        )
        if wall_opening.get("geometry_status") != "resolved":
            return self._pending(
                geometry, "vehicle_wall_opening_pending",
                wall_opening.get("reason") or wall_opening.get("physical_resolution_reason"), edge,
            )
        geometry["physical_walls"] = wall_opening.pop("physical_walls")
        geometry.setdefault("openings", []).append(wall_opening)
        driveway_bbox = [
            min(point[0] for point in polygon),
            min(point[1] for point in polygon),
            max(point[0] for point in polygon),
            max(point[1] for point in polygon),
        ]
        conflicts = []
        for zone in zones:
            bbox = zone.get("bbox") if isinstance(zone, dict) else None
            if (
                isinstance(bbox, (list, tuple))
                and len(bbox) == 4
                and self._bbox_intersects(driveway_bbox, bbox)
            ):
                conflicts.append(zone.get("id") or zone.get("type") or "protected_zone")
        if conflicts:
            pending = self._pending(
                geometry,
                "vehicle_access_conflict_detected",
                "driveway_intersects_protected_zone",
                edge,
                "conflict_detected",
            )
            pending["conflict_validation"]["conflicts"] = conflicts
            return pending
        ramp = None
        if selection.get("ramp_geometry_allowed"):
            run = candidate.get("required_run")
            if not isinstance(run, (int, float)) or run <= 0 or candidate.get("site_fit") is not True:
                return self._pending(geometry, "ramp_geometry_unresolved", "verified_ramp_placement_evidence_missing", edge)
            direction_length = hypot(target[0]-start[0], target[1]-start[1])
            if direction_length <= 0:
                return self._pending(geometry, "ramp_geometry_unresolved", "ramp_direction_unresolved", edge)
            direction = [(target[0]-start[0])/direction_length, (target[1]-start[1])/direction_length]
            placed = RampSpatialPlacementEngine().generate({
                "type": "vehicle_ramp", "shape": "straight", "length": run,
                "width": width, "entry_point": start, "entry_direction": direction,
                "authoritative_placement": True,
            })
            ramp3d = Ramp3DGeometryEngine().generate(placed, {
                "width": width, "start_z": candidate.get("access_elevation"),
                "end_z": candidate.get("target_elevation"), "slope": technical.get("slope"),
            })
            ramp = dict(placed)
            ramp.update(ramp3d)
            ramp.update({"type": "vehicle_ramp", "access_id": access_id,
                         "required_run": run, "protected_zone": True,
                         "geometry_status": "resolved", "served_levels": [candidate.get("target_level")],
                         "source": "selected_access_geometry_resolver_v1"})
            if ramp.get("surface", {}).get("geometry_status") != "resolved":
                return self._pending(geometry, "ramp_geometry_unresolved",
                                     "physical_ramp_surface_unresolved", edge)
            ramp["arrival_interface"] = {
                "point": ramp.get("exit_point"),
                "elevation": ramp.get("end_z"),
                "geometry_status": "resolved",
                "source": "resolved_ramp_surface_exit",
            }
            driveway.update({
                "centerline": list(ramp.get("centerline", [])),
                "polygon": list(ramp.get("polygon", [])),
                "end_point": list(ramp.get("exit_point", target)),
                "movement_surface_reference": "resolved_vehicle_ramp_surface",
            })
        site["vehicle_access"] = {"access_geometry": edge, "entrance": entrance, "driveway": driveway}
        geometry["site_geometry"] = site
        if ramp is not None:
            geometry.setdefault("vertical_geometry", []).append(ramp)
        ramp_requirements = project_requirements.get("vehicle_ramp_requirements", []) if isinstance(project_requirements, dict) else []
        matched_ramp_requirements = [item for item in ramp_requirements if isinstance(item, dict)
                                     and item.get("access_id") == access_id]
        if ramp is None:
            clearance = {"access_id": access_id, "geometry_status": "not_required",
                         "unresolved_evidence": [], "source": "direct_at_grade_has_no_ramp"}
        else:
            requirement = matched_ramp_requirements[0] if len(matched_ramp_requirements) == 1 else None
            clearance = ArchitecturalRampClearanceResolverV1().resolve(
                ramp, geometry.get("slabs", []), requirement
            )
            if clearance.get("geometry_status") == "resolved":
                opening = clearance["slab_opening"]
                geometry.setdefault("slab_openings", []).append(opening)
                for slab in geometry.get("slabs", []):
                    if slab.get("floor") == clearance.get("affected_floor"):
                        slab.setdefault("physical_openings", []).append(opening)
                        slab["opening_aware_geometry"] = True
                geometry.setdefault("architectural_protected_zones", []).append(clearance["protected_zone"])
        geometry["ramp_clearance"] = clearance
        geometry["ramp_clearance_status"] = clearance.get("geometry_status")
        parking_requirements = project_requirements.get("parking_requirements", []) if isinstance(project_requirements, dict) else []
        matched_parking = [item for item in parking_requirements if isinstance(item, dict)
                           and item.get("served_level") == driveway.get("served_level")]
        if matched_parking:
            parking_arrival = ParkingArrivalManeuveringResolverV1().resolve(
                driveway, wall_opening, geometry.get("slabs", geometry.get("floor_geometry", [])),
                geometry.get("physical_walls", []),
                list(geometry.get("architectural_protected_zones", [])) + [
                    item.get("protected_zone") for item in geometry.get("vertical_geometry", [])
                    if isinstance(item, dict) and isinstance(item.get("protected_zone"), dict)
                ], matched_parking[0] if len(matched_parking) == 1 else None,
            )
            if parking_arrival.get("geometry_status") != "resolved":
                pending = self._pending(geometry, "parking_arrival_pending",
                                        parking_arrival.get("unresolved_evidence"), edge)
                pending["parking_arrival"] = parking_arrival
                return pending
            site["parking_arrival"] = parking_arrival
            geometry.setdefault("architectural_protected_zones", []).append(parking_arrival["arrival_zone"])
            parking_layout = ParkingAisleStallTopologyResolverV1().resolve(
                parking_arrival, matched_parking[0],
                [item for item in geometry.get("architectural_protected_zones", [])
                 if item is not parking_arrival.get("arrival_zone")],
            )
            if matched_parking[0].get("required_parking_count") is not None and parking_layout.get("geometry_status") != "resolved":
                pending = self._pending(geometry, "parking_layout_pending",
                                        parking_layout.get("unresolved_evidence"), edge)
                pending["parking_arrival"] = parking_arrival
                pending["parking_layout"] = parking_layout
                return pending
            site["parking_layout"] = parking_layout
        else:
            parking_arrival = {"geometry_status": "not_required", "unresolved_evidence": []}
            parking_layout = {"geometry_status": "not_required", "unresolved_evidence": []}
        pedestrian_requirements = project_requirements.get("parking_pedestrian_requirements", []) if isinstance(project_requirements, dict) else []
        matched_pedestrian = [item for item in pedestrian_requirements if isinstance(item,dict) and item.get("served_level")==driveway.get("served_level")]
        if len(matched_pedestrian)==1:
            if not matched_pedestrian[0].get("destination_interfaces"):
                derived = [{"point": item.get("interface_point"), "floor": item.get("served_level"),
                            "circulation_space_id": item.get("circulation_space_id"),
                            "stair_core_id": item.get("vertical_system_id"),
                            "stair_requirement_id": item.get("requirement_id"),
                            "stair_interface_status": item.get("geometry_status"),
                            "interface_status": item.get("geometry_status"),
                            "source": "resolved_vertical_interface_contract"}
                           for item in geometry.get("vertical_interfaces", [])
                           if item.get("served_level") == driveway.get("served_level") and item.get("geometry_status") == "resolved"]
                matched_pedestrian[0] = dict(matched_pedestrian[0])
                matched_pedestrian[0]["destination_interfaces"] = derived
            vehicle_zones=[{"id":"driveway","type":"vehicle_driveway","polygon":driveway.get("polygon")}]
            if ramp is not None:vehicle_zones.append({"id":"ramp","type":"vehicle_ramp","polygon":ramp.get("polygon")})
            if clearance.get("geometry_status")=="resolved":vehicle_zones.append({"id":"ramp_clearance","type":"vehicle_ramp_clearance","polygon":clearance.get("ramp_surface")})
            parking_pedestrian=ParkingPedestrianConnectionResolverV1().resolve(
                parking_arrival,parking_layout,matched_pedestrian[0],geometry.get("physical_walls",[]),geometry.get("openings",[]),
                geometry.get("vertical_geometry",[]),vehicle_zones,geometry.get("architectural_protected_zones",[]))
            site["parking_pedestrian_connection"]=parking_pedestrian
            geometry.setdefault("connections",[]).append({"connection_id":parking_pedestrian.get("connection_id"),
                "from":"parking_arrival","to":parking_pedestrian.get("target_circulation_space_id") or parking_pedestrian.get("target_stair_core_id"),
                "geometry_status":parking_pedestrian.get("geometry_status"),"parking_to_building_status":parking_pedestrian.get("parking_to_building_status"),
                "physical_opening_ids":parking_pedestrian.get("physical_opening_ids",[]),"source":"parking_pedestrian_connection_resolver_v1"})
        else:
            parking_pedestrian={"geometry_status":"not_required" if not matched_pedestrian else "pending_tie","unresolved_evidence":[] if not matched_pedestrian else ["unique_parking_pedestrian_requirement"]}
        geometry["spatial_quality_gate"] = ArchitecturalSpatialQualityGateV2().evaluate(
            geometry, project_requirements.get("spatial_quality_requirements", {})
        )
        geometry["architectural_section"] = ArchitecturalSectionIntelligenceV1().resolve(geometry)
        geometry["cad_drawing_contract"] = ArchitecturalCadDrawingResolverV1().resolve(geometry)
        geometry["architecture_completion_gate"] = ArchitecturalCompletionGateV2().evaluate(geometry)
        return {
            "status": "resolved", "selected_access_geometry": edge,
            "entrance": entrance, "driveway": driveway, "ramp": ramp,
            "conflict_validation": {"status": "clear", "checked_zones": len(zones)},
            "geometry_generation_allowed": True,
            "driveway_geometry_allowed": True,
            "ramp_geometry_allowed": ramp is not None,
            "vehicle_wall_opening": wall_opening,
            "ramp_clearance_status": geometry["ramp_clearance_status"],
            "ramp_clearance": clearance,
            "parking_arrival": parking_arrival,
            "parking_layout": parking_layout,
            "parking_pedestrian_connection": parking_pedestrian,
            "architectural_geometry": geometry,
        }
