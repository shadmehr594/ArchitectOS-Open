"""Fail-closed completion audit over resolved architectural contracts."""

from __future__ import annotations


class ArchitecturalCompletionGateV1:
    VERSION = "1.0"

    def evaluate(self, geometry):
        checks = {}
        failures = []

        openings = [item for item in geometry.get("openings", []) if isinstance(item, dict)]
        fabricated = [item.get("id") or item.get("opening_id") for item in openings
                      if item.get("geometry_generation_allowed") is True
                      and (item.get("geometry_status") != "resolved" or not item.get("host_wall_id"))]
        checks["physical_openings"] = self._check(not fabricated, fabricated)

        requirements = geometry.get("project_requirements", {})
        stair_requirements = (requirements.get("vertical_transport", {}).get("stairs", [])
                              if isinstance(requirements, dict) else [])
        stairs = [item for item in geometry.get("vertical_geometry", [])
                  if isinstance(item, dict) and item.get("type") == "stair_geometry"
                  and item.get("geometry_status") == "resolved"]
        required_stairs = [item for item in stair_requirements if isinstance(item, dict) and item.get("required") is True]
        missing_stairs = [item.get("id") for item in required_stairs
                          if not any(stair.get("stair_id") == item.get("id") or
                                     (item.get("from_level") in stair.get("served_levels", []) and
                                      item.get("to_level") in stair.get("served_levels", []))
                                     for stair in stairs)]
        checks["served_level_circulation"] = self._check(not missing_stairs, missing_stairs)

        slab_openings = [item for item in geometry.get("slab_openings", [])
                         if isinstance(item, dict) and item.get("geometry_status") == "resolved"]
        stair_void_ok = not required_stairs or any("stair" in str(item.get("type", "")) for item in slab_openings)
        checks["stair_slab_void"] = self._check(stair_void_ok, [] if stair_void_ok else ["resolved_stair_slab_opening"])

        site = geometry.get("site_geometry", {}) if isinstance(geometry.get("site_geometry"), dict) else {}
        vehicle = site.get("vehicle_access", {}) if isinstance(site.get("vehicle_access"), dict) else {}
        entrances = requirements.get("vehicle_access", {}).get("entrances", []) if isinstance(requirements, dict) else []
        vehicle_required = bool(entrances)
        entrance = vehicle.get("entrance", {}) if isinstance(vehicle.get("entrance"), dict) else {}
        driveway = vehicle.get("driveway", {}) if isinstance(vehicle.get("driveway"), dict) else {}
        vehicle_openings = [item for item in openings if item.get("type") == "vehicle_entrance"
                            and item.get("geometry_status") == "resolved" and item.get("host_wall_id")]
        vehicle_ok = (not vehicle_required or
                      (entrance.get("entrance_status") == "resolved"
                       and driveway.get("geometry_status") == "resolved"
                       and bool(vehicle_openings)))
        checks["vehicle_entrance_and_driveway"] = self._check(vehicle_ok, [] if vehicle_ok else ["resolved_vehicle_entry_interface"])

        ramps = [item for item in geometry.get("vertical_geometry", [])
                 if isinstance(item, dict) and item.get("type") == "vehicle_ramp"
                 and item.get("geometry_status") == "resolved"]
        clearance = geometry.get("ramp_clearance", {})
        ramp_ok = not ramps or (isinstance(clearance, dict) and clearance.get("geometry_status") == "resolved")
        checks["ramp_headroom"] = self._check(ramp_ok, [] if ramp_ok else ["resolved_ramp_clearance"])
        ramp_void_ok = not ramps or any(item.get("type") == "vehicle_ramp_clearance_slab_opening" for item in slab_openings)
        checks["ramp_slab_void"] = self._check(ramp_void_ok, [] if ramp_void_ok else ["resolved_ramp_slab_opening"])

        parking_requirements = requirements.get("parking_requirements", []) if isinstance(requirements, dict) else []
        parking_required = any(isinstance(item, dict) and item.get("required") is True for item in parking_requirements)
        arrival = site.get("parking_arrival", {}) if isinstance(site.get("parking_arrival"), dict) else {}
        layout = site.get("parking_layout", {}) if isinstance(site.get("parking_layout"), dict) else {}
        parking_ok = not parking_required or (arrival.get("geometry_status") == "resolved"
                                               and layout.get("geometry_status") == "resolved"
                                               and all(stall.get("aisle_access") is True for stall in layout.get("parking_stalls", [])))
        checks["parking_arrival_turning_stalls"] = self._check(parking_ok, [] if parking_ok else ["resolved_accessible_parking_topology"])

        quality = geometry.get("spatial_quality_gate", {})
        quality_ok = isinstance(quality, dict) and quality.get("status") == "passed"
        checks["room_circulation_quality"] = self._check(quality_ok, [] if quality_ok else ["passed_spatial_quality_gate"])

        cad = geometry.get("cad_drawing_contract", {})
        section = geometry.get("architectural_section", {})
        checks["core_cad_geometry"] = self._check(cad.get("geometry_status") == "resolved", ["resolved_cad_drawing_contract"] if cad.get("geometry_status") != "resolved" else [])
        checks["functional_section"] = self._check(section.get("geometry_status") == "resolved", ["resolved_functional_section"] if section.get("geometry_status") != "resolved" else [])

        walls = [item for item in geometry.get("physical_walls", []) if isinstance(item, dict)]
        separation_ok = bool(walls) and all(wall.get("outer_face_clearance_status") != "violated" for wall in walls)
        checks["separation_outer_face"] = self._check(separation_ok, [] if separation_ok else ["physical_wall_outer_face_clearance"])

        for name, result in checks.items():
            if result["status"] != "passed":
                failures.append({"check": name, "unresolved_evidence": result["unresolved_evidence"]})
        return {"version": self.VERSION, "architecture_complete": not failures,
                "status": "complete" if not failures else "incomplete",
                "checks": checks, "critical_failures": failures,
                "source": "resolved_architectural_contracts", "fail_closed": True}

    @staticmethod
    def _check(ok, unresolved):
        return {"status": "passed" if ok else "failed", "unresolved_evidence": unresolved}
