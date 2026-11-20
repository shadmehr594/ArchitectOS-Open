"""Read-only acceptance gate for an executable basement vehicle system."""

from copy import deepcopy
from math import hypot


class BasementVehicleArchitecturalAcceptanceV2:
    VERSION = "2.0"
    EPS = 1e-6

    def evaluate(self, geometry, vehicle_result=None):
        geometry = geometry if isinstance(geometry, dict) else {}
        result = vehicle_result if isinstance(vehicle_result, dict) else {}
        ramp = result.get("ramp")
        opening = result.get("vehicle_wall_opening")
        arrival = result.get("parking_arrival") or {}
        parking = result.get("parking_layout") or {}
        clearance = result.get("ramp_clearance") or {}
        checks = {
            "resolved_vehicle_access": result.get("status") == "resolved",
            "physical_ramp_surface": self._surface(ramp),
            "ramp_vertical_profile": self._profile(ramp),
            "vehicle_wall_opening": isinstance(opening, dict) and opening.get("geometry_status") == "resolved",
            "ramp_to_arrival_continuity": self._continuity(ramp, arrival),
            "maneuvering_zone": arrival.get("geometry_status") == "resolved",
            "parking_topology": parking.get("geometry_status") == "resolved",
            "stall_ingress_egress": parking.get("ingress_egress_connectivity") == "resolved",
            "ramp_clearance": clearance.get("geometry_status") == "resolved",
            "slab_void": self._slab_void(geometry, clearance),
            "basement_footprint": self._floor(geometry, "basement") is not None,
            "f1_footprint": self._floor(geometry, "F1") is not None,
        }
        failed = [name for name, passed in checks.items() if not passed]
        candidate_id = result.get("candidate_id")
        stalls = parking.get("parking_stalls")
        achieved_capacity = len(stalls) if isinstance(stalls, list) else None
        return {
            "type": "basement_ramp_parking_architectural_acceptance",
            "version": self.VERSION,
            "automated_geometry_pass": not failed,
            "human_visual_acceptance": "pending",
            "checks": checks,
            "failed_checks": failed,
            "geometry_status": "resolved" if not failed else "unresolved",
            "validation_status": "accepted" if not failed else "failed",
            "candidate_id": candidate_id,
            "achieved_parking_capacity": achieved_capacity if not failed else None,
            "accepted_result_evidence": ([{
                "source": self.__class__.__name__,
                "candidate_id": candidate_id,
                "checks": deepcopy(checks),
                "parking_stall_count": achieved_capacity,
            }] if not failed and candidate_id and achieved_capacity is not None else []),
            "producer_provenance": deepcopy(result.get("provenance") or []),
            "source": self.__class__.__name__,
        }

    def _surface(self, ramp):
        surface = ramp.get("surface") if isinstance(ramp, dict) else None
        return (isinstance(surface, dict) and surface.get("geometry_status") == "resolved"
                and len(surface.get("vertices", [])) >= 4 and len(surface.get("faces", [])) >= 2)

    def _profile(self, ramp):
        if not isinstance(ramp, dict):
            return False
        line = ramp.get("centerline_3d", [])
        return (len(line) >= 2 and ramp.get("start_z") != ramp.get("end_z")
                and hypot(line[-1][0]-line[0][0], line[-1][1]-line[0][1]) > self.EPS)

    def _continuity(self, ramp, arrival):
        if not isinstance(ramp, dict) or arrival.get("geometry_status") != "resolved":
            return False
        exit_point, point = ramp.get("exit_point"), arrival.get("arrival_point")
        return (isinstance(exit_point, list) and isinstance(point, list)
                and hypot(exit_point[0]-point[0], exit_point[1]-point[1]) <= self.EPS)

    @staticmethod
    def _floor(geometry, name):
        matches = [item for item in geometry.get("floor_geometry", [])
                   if isinstance(item, dict) and item.get("floor") == name]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _slab_void(geometry, clearance):
        opening = clearance.get("slab_opening") if isinstance(clearance, dict) else None
        if not isinstance(opening, dict) or opening.get("geometry_status") != "resolved":
            return False
        return any(item.get("opening_id") == opening.get("opening_id")
                   for item in geometry.get("slab_openings", []) if isinstance(item, dict))
