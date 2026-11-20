"""Final fail-closed architectural completion authority."""

from __future__ import annotations

from core.architecture.reasoning.architectural_completion_gate_v1 import ArchitecturalCompletionGateV1


class ArchitecturalCompletionGateV2:
    VERSION = "2.0"

    def evaluate(self, geometry):
        geometry = geometry if isinstance(geometry, dict) else {}
        legacy = ArchitecturalCompletionGateV1().evaluate(geometry)
        checks = dict(legacy.get("checks", {}))
        quality = geometry.get("spatial_quality_gate", {})
        checks["spatial_quality_v2_authority"] = self._check(
            quality.get("version") == "2.0" and quality.get("status") == "passed"
            and quality.get("architectural_authority") is True,
            [] if quality.get("status") == "passed" else ["passed_spatial_quality_gate_v2"],
        )
        checks["required_room_reachability"] = self._check(
            not any(x.get("type") in ("required_space_unreachable", "isolated_space", "entrance_disconnected_from_circulation")
                    for x in quality.get("critical_failures", [])),
            ["resolved_required_room_reachability"],
        )
        checks["opening_endpoint_integrity"] = self._check(
            not any(x.get("type") in ("door_to_nowhere", "invalid_physical_exterior_window",
                                       "required_connection_without_physical_opening")
                    for x in quality.get("critical_failures", [])),
            ["resolved_opening_endpoints_and_hosts"],
        )
        stair_requirements = geometry.get("project_requirements", {}).get("vertical_transport", {}).get("stairs", [])
        interfaces = geometry.get("vertical_interfaces", [])
        required_stairs = [r for r in stair_requirements if isinstance(r, dict) and r.get("required") is True]
        interface_ok = not required_stairs or all(
            len([i for i in interfaces
                 if (i.get("requirement_id") == r.get("id") or i.get("vertical_system_id") == r.get("id"))
                 and i.get("geometry_status") == "resolved"]) >= 2
            for r in required_stairs
        )
        checks["stair_circulation_interfaces"] = self._check(interface_ok, [] if interface_ok else ["resolved_stair_interfaces_per_served_level"])
        parking_required = bool(geometry.get("project_requirements", {}).get("parking_pedestrian_requirements", []))
        parking = geometry.get("site_geometry", {}).get("parking_pedestrian_connection", {})
        parking_ok = not parking_required or (parking.get("geometry_status") == "resolved" and parking.get("parking_to_building_status") == "resolved")
        checks["parking_pedestrian_chain"] = self._check(parking_ok, [] if parking_ok else ["resolved_parking_to_building_chain"])

        failures = [{"check": name, "unresolved_evidence": value.get("unresolved_evidence", [])}
                    for name, value in checks.items() if value.get("status") != "passed"]
        complete = not failures
        return {"version": self.VERSION, "architecture_complete": complete,
                "status": "complete" if complete else "incomplete", "checks": checks,
                "critical_failures": failures, "spatial_quality_status": quality.get("status"),
                "manual_override_allowed": False, "source": "spatial_quality_v2_plus_resolved_architectural_contracts",
                "fail_closed": True}

    @staticmethod
    def _check(ok, unresolved):
        return {"status": "passed" if ok else "failed", "unresolved_evidence": [] if ok else unresolved}
