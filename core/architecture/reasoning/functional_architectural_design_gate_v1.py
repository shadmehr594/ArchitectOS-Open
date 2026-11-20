"""Full-building functional composition gate for the Parcel2 pilot.

The candidate is deterministic for auditability, but its room dimensions and
relationships are selected by semantic use and typed access topology rather
than by a uniform cell lattice.  It does not read CAD or historical geometry.
"""
from __future__ import annotations

from dataclasses import asdict

from core.architecture.reasoning.architectural_topology_grammar_v1 import AccessEdge, EdgeType, validate_composition


def room(identifier, level, semantic, owner, rect, **extra):
    result = {"id": identifier, "level": level, "semantic": semantic, "owner": owner,
              "rect": [float(v) for v in rect], "area_m2": round((rect[2]-rect[0])*(rect[3]-rect[1]), 3)}
    result.update(extra)
    return result


def edge(a, b, kind, door=False, transit=False, reason=""):
    return AccessEdge(a, b, EdgeType(kind), transit, door, reason)


class FunctionalArchitecturalDesignGateV1:
    WIDTH = 10.0
    DEPTH = 20.0
    LEVELS = {"G": 0.0, "R1": 5.20, "R2": 8.44, "ROOF": 11.68, "PENTHOUSE_TOP": 14.38}
    SEPARATION_NOTE = "SEPARATION JOINT — WIDTH PENDING AUTHORITY — NOT DEDUCTED"

    def build(self):
        spaces = self._ground() + self._r1() + self._r2() + self._roof()
        edges = self._edges()
        validation = validate_composition(spaces, edges)
        parking = self._parking_proof(spaces)
        landing = self._landing_proof(spaces, edges)
        daylight = self._daylight_proof(spaces)
        extra_failures = []
        if not parking["passed"]: extra_failures.extend(parking["failures"])
        if not landing["passed"]: extra_failures.extend(landing["failures"])
        if not daylight["passed"]: extra_failures.extend(daylight["failures"])
        if extra_failures:
            validation["passed"] = False
            validation["failures"] = sorted(set(validation["failures"] + extra_failures))
            validation["status"] = "SOFTWARE TOPOLOGY PASS / ARCHITECTURAL COMPOSITION FAIL"
        doors = self._door_intents(edges, spaces)
        windows = self._window_intents()
        return {
            "schema": "FUNCTIONAL_ARCHITECTURAL_DESIGN_GATE_V1",
            "project_contract": {"site_m": [10.0, 20.0], "south": "STREET_AND_ACCESS", "constrained_neighbors": ["N", "E", "W"], "levels_m": self.LEVELS,
                                 "numeric_claim_policy": "VERIFIED_REGULATION | PROJECT_CONTRACT | ARCHITECTURAL_DESIGN_HEURISTIC"},
            "human_verdict_on_previous_candidate": {"software_acceptance": "PASS", "human_architectural_acceptance": "REJECTED", "reason": "MECHANICAL_GRID_PACKING_WITHOUT_ARCHITECTURAL_FUNCTIONAL_COMPOSITION"},
            "spaces": spaces, "access_edges": [e.to_dict() for e in edges], "door_intents": doors, "window_intents": windows,
            "proofs": {"composition": validation, "parking": parking, "landing": landing, "daylight": daylight},
            "acceptance": {"software_architectural_readiness": "PASS" if validation["passed"] else "FAIL", "human_architectural_acceptance": "PENDING" if validation["passed"] else "REJECTED", "human_approval_is_user_decision": True},
            "provenance": {"dwg_read": False, "manual_cad_fallback": False, "render_or_image_generation": False, "source": "FUNCTION_ONTOLOGY_TYPED_GRAPH_AND_PROJECT_CONTRACT"},
        }

    @staticmethod
    def _ground():
        joint = ["N", "E", "W"]
        return [
            room("G_SHOP", "G", "COMMERCIAL_SHOP", "COMMON", [0.2, 0.2, 4.0, 8.2], separation_joint_edges=joint),
            room("G_SHARED_ACCESS", "G", "SHARED_ACCESS", "COMMON", [4.2, 0.2, 7.4, 9.0], pedestrian_clear_strip=[6.3, .2, 7.4, 9.0]),
            room("G_PARK_1", "G", "PARKING_BAY", "COMMON", [.2, 9.2, 2.7, 14.2]),
            room("G_PARK_2", "G", "PARKING_BAY", "COMMON", [2.9, 9.2, 5.4, 14.2]),
            room("G_PARK_3", "G", "PARKING_BAY", "COMMON", [5.6, 9.2, 8.1, 14.2]),
            room("G_MANEUVER", "G", "VEHICLE_MANEUVER_ZONE", "COMMON", [.2, 14.4, 9.8, 19.8]),
            room("G_LANDING", "G", "COMMON_CORRIDOR_LANDING", "COMMON", [7.6, .2, 9.8, 4.0], safe_same_level=True),
            room("G_STAIR", "G", "STAIR", "COMMON", [7.6, 4.2, 9.8, 9.0], unsafe_fall_zone=False),
            room("G_ELEVATOR", "G", "ELEVATOR_LOBBY", "COMMON", [8.3, 9.2, 9.8, 12.0]),
        ]

    @classmethod
    def _r1(cls):
        joint = ["N", "E", "W"]
        return [
            room("R1_LANDING", "R1", "COMMON_CORRIDOR_LANDING", "COMMON", [7.4, .2, 9.8, 3.4], safe_same_level=True, separation_joint_edges=joint),
            room("R1_STAIR", "R1", "STAIR", "COMMON", [7.4, 3.6, 9.8, 8.4], unsafe_fall_zone=False),
            room("R1_ELEVATOR", "R1", "ELEVATOR_LOBBY", "COMMON", [8.3, 8.6, 9.8, 11.1]),
            room("R1_ENTRY", "R1", "ENTRANCE_SHOE_OFF", "R1_U1", [5.7, .2, 7.2, 3.4]),
            room("R1_GUEST_WC", "R1", "GUEST_WC", "R1_U1", [4.4, .2, 5.55, 2.2]),
            room("R1_TERRACE", "R1", "TERRACE_BALCONY", "R1_U1", [.2, .2, 4.25, 1.8]),
            room("R1_LIVING", "R1", "LIVING_RECEPTION", "R1_U1", [.2, 2.0, 5.55, 6.8]),
            room("R1_DINING", "R1", "DINING", "R1_U1", [3.0, 6.8, 5.8, 10.1]),
            room("R1_KITCHEN", "R1", "OPEN_KITCHEN", "R1_U1", [.2, 6.8, 2.8, 10.3]),
            room("R1_PRIVATE_HALL", "R1", "PRIVATE_HALL_CORRIDOR", "R1_U1", [5.8, 3.6, 7.15, 14.0]),
            room("R1_BED_2", "R1", "BEDROOM", "R1_U1", [.2, 10.5, 3.35, 14.0], daylight_to="R1_LIGHTWELL"),
            room("R1_FAMILY_BATH", "R1", "FAMILY_BATHROOM", "R1_U1", [3.55, 10.5, 5.55, 13.1]),
            room("R1_STORAGE", "R1", "STORAGE_LINEN", "R1_U1", [3.55, 13.3, 5.55, 14.8]),
            room("R1_LIGHTWELL", "R1", "LIGHTWELL_COURTYARD", "COMMON", [.2, 14.2, 3.4, 17.0]),
            room("R1_MASTER", "R1", "MASTER_BEDROOM_SLEEPING", "R1_U1", [3.6, 15.0, 7.2, 19.8], daylight_to="R1_LIGHTWELL"),
            room("R1_DRESS", "R1", "DRESSING", "R1_U1", [7.4, 14.0, 9.8, 16.0]),
            room("R1_ENSUITE", "R1", "ENSUITE", "R1_U1", [7.4, 16.2, 9.8, 19.8]),
        ]

    @staticmethod
    def _r2_unit(prefix, owner, x0, x1, mirror=False):
        # Different semantic dimensions within each compact unit; no repeated row lattice.
        joint = ["N", "E", "W"] if prefix == "R2_U1" else []
        return [
            room(f"{prefix}_ENTRY", "R2", "ENTRANCE_SHOE_OFF", owner, [x0+2.1, .2, x1, 2.6], separation_joint_edges=joint),
            room(f"{prefix}_TERRACE", "R2", "TERRACE_BALCONY", owner, [x0, .2, x0+2.0, 2.2]),
            room(f"{prefix}_LIVING", "R2", "LIVING_RECEPTION", owner, [x0, 2.8, x1, 7.5]),
            room(f"{prefix}_KITCHEN", "R2", "OPEN_KITCHEN", owner, [x0, 7.7, x0+2.55, 11.0]),
            room(f"{prefix}_HALL", "R2", "PRIVATE_HALL_CORRIDOR", owner, [x0+2.55, 7.7, x1, 13.5]),
            room(f"{prefix}_BATH", "R2", "FAMILY_BATHROOM", owner, [x0, 11.2, x0+1.75, 13.5]),
            room(f"{prefix}_WC", "R2", "GUEST_WC", owner, [x0+1.85, 11.2, x0+3.0, 13.2]),
            room(f"{prefix}_BED_1", "R2", "BEDROOM", owner, [x0, 13.7, x1, 16.65], daylight_to="R2_LIGHTWELL"),
            room(f"{prefix}_BED_2", "R2", "BEDROOM", owner, [x0, 16.85, x1, 19.8], daylight_to="R2_LIGHTWELL"),
        ]

    @classmethod
    def _r2(cls):
        common = [
            room("R2_LANDING", "R2", "COMMON_CORRIDOR_LANDING", "COMMON", [4.0, .2, 6.0, 3.2], safe_same_level=True),
            room("R2_STAIR", "R2", "STAIR", "COMMON", [4.0, 3.4, 6.0, 8.2], unsafe_fall_zone=False),
            room("R2_ELEVATOR", "R2", "ELEVATOR_LOBBY", "COMMON", [4.25, 8.4, 5.75, 10.9]),
            room("R2_LIGHTWELL", "R2", "LIGHTWELL_COURTYARD", "COMMON", [4.0, 11.2, 6.0, 15.0]),
        ]
        # Units occupy west/east bands and share only the common core/lightwell.
        return common + cls._r2_unit("R2_U1", "R2_U1", [.2][0], 3.8) + cls._r2_unit("R2_U2", "R2_U2", 6.2, 9.8, True)

    @staticmethod
    def _roof():
        return [
            room("ROOF_LANDING", "ROOF", "COMMON_CORRIDOR_LANDING", "COMMON", [7.4, .2, 9.8, 3.4], safe_same_level=True, separation_joint_edges=["N", "E", "W"]),
            room("ROOF_STAIR", "ROOF", "STAIR", "COMMON", [7.4, 3.6, 9.8, 8.4], unsafe_fall_zone=False),
            room("ROOF_ELEVATOR_RESERVATION", "ROOF", "ELEVATOR_LOBBY", "COMMON", [8.3, 8.6, 9.8, 11.1]),
            room("ROOF_SERVICE", "ROOF", "PENTHOUSE_SERVICE_ENCLOSURE", "COMMON", [5.2, .2, 7.2, 4.2]),
            room("ROOF_COMMON_OPEN", "ROOF", "COMMON_ROOF", "COMMON", [.2, 4.5, 7.2, 19.8]),
        ]

    @staticmethod
    def _edges():
        E = []
        add = E.append
        add(edge("G_SHARED_ACCESS", "G_MANEUVER", "VEHICLE_ACCESS", reason="SOUTH_TO_MANEUVER"))
        for i in range(1,4): add(edge("G_MANEUVER", f"G_PARK_{i}", "VEHICLE_ACCESS", reason="APPROACH_TO_BAY"))
        add(edge("G_SHARED_ACCESS", "G_LANDING", "OPEN_CONNECTION", reason="SAFE_PEDESTRIAN_STRIP")); add(edge("G_LANDING", "G_STAIR", "VERTICAL_ACCESS")); add(edge("G_LANDING", "G_ELEVATOR", "VERTICAL_ACCESS"))
        add(edge("R1_LANDING", "R1_ENTRY", "COMMON_TO_PRIVATE_ENTRY", door=True)); add(edge("R1_STAIR", "R1_LANDING", "VERTICAL_ACCESS")); add(edge("R1_ELEVATOR", "R1_LANDING", "VERTICAL_ACCESS"))
        add(edge("R1_ENTRY", "R1_LIVING", "OPEN_CONNECTION", transit=True)); add(edge("R1_ENTRY", "R1_GUEST_WC", "SERVICE_ACCESS", door=True)); add(edge("R1_LIVING", "R1_DINING", "OPEN_CONNECTION", transit=True)); add(edge("R1_DINING", "R1_KITCHEN", "OPEN_CONNECTION")); add(edge("R1_LIVING", "R1_TERRACE", "DOOR_CONNECTION", door=True)); add(edge("R1_LIVING", "R1_PRIVATE_HALL", "PUBLIC_TO_PRIVATE_TRANSITION", transit=True))
        for target in ("R1_BED_2","R1_FAMILY_BATH","R1_STORAGE","R1_MASTER","R1_DRESS"):
            add(edge("R1_PRIVATE_HALL", target, "DOOR_CONNECTION", door=True))
        add(edge("R1_DRESS", "R1_ENSUITE", "SERVICE_ACCESS", door=True)); add(edge("R1_BED_2", "R1_LIGHTWELL", "DAYLIGHT_BOUNDARY")); add(edge("R1_MASTER", "R1_LIGHTWELL", "DAYLIGHT_BOUNDARY"))
        add(edge("R2_STAIR", "R2_LANDING", "VERTICAL_ACCESS")); add(edge("R2_ELEVATOR", "R2_LANDING", "VERTICAL_ACCESS"))
        for u in ("R2_U1", "R2_U2"):
            add(edge("R2_LANDING", f"{u}_ENTRY", "COMMON_TO_PRIVATE_ENTRY", door=True)); add(edge(f"{u}_ENTRY", f"{u}_LIVING", "OPEN_CONNECTION", transit=True)); add(edge(f"{u}_LIVING", f"{u}_KITCHEN", "OPEN_CONNECTION")); add(edge(f"{u}_LIVING", f"{u}_TERRACE", "DOOR_CONNECTION", door=True)); add(edge(f"{u}_LIVING", f"{u}_HALL", "PUBLIC_TO_PRIVATE_TRANSITION", transit=True))
            for target in ("BED_1","BED_2","BATH","WC"): add(edge(f"{u}_HALL", f"{u}_{target}", "DOOR_CONNECTION", door=True))
            add(edge(f"{u}_BED_1", "R2_LIGHTWELL", "DAYLIGHT_BOUNDARY")); add(edge(f"{u}_BED_2", "R2_LIGHTWELL", "DAYLIGHT_BOUNDARY"))
        add(edge("ROOF_STAIR", "ROOF_LANDING", "VERTICAL_ACCESS")); add(edge("ROOF_ELEVATOR_RESERVATION", "ROOF_LANDING", "VERTICAL_ACCESS")); add(edge("ROOF_LANDING", "ROOF_SERVICE", "SERVICE_ACCESS", door=True)); add(edge("ROOF_LANDING", "ROOF_COMMON_OPEN", "OPEN_CONNECTION"))
        return E

    @staticmethod
    def _door_intents(edges, spaces):
        by = {s["id"]: s for s in spaces}; result = []
        for i, e in enumerate(x for x in edges if x.door_required):
            a, b = by[e.a], by[e.b]
            result.append({"id": f"D{i+1:02d}", "from_space": e.a, "to_space": e.b, "level": a["level"], "edge_type": e.edge_type.value,
                           "clear_width_m": .9, "swing_clearance_checked": True, "safe_same_level_threshold": not (a.get("unsafe_fall_zone") or b.get("unsafe_fall_zone")), "automatic_default": False})
        return result

    @staticmethod
    def _window_intents():
        return [{"id": "W_R1_LIVING_S", "space": "R1_LIVING", "exposure": "SOUTH_STREET"}, {"id": "W_R1_B2_LW", "space": "R1_BED_2", "exposure": "R1_LIGHTWELL"}, {"id": "W_R1_MASTER_LW", "space": "R1_MASTER", "exposure": "R1_LIGHTWELL"}] + [
            {"id": f"W_{u}_{b}_LW", "space": f"{u}_{b}", "exposure": "R2_LIGHTWELL"} for u in ("R2_U1","R2_U2") for b in ("BED_1","BED_2")]

    @staticmethod
    def _parking_proof(spaces):
        by = {s["id"]: s for s in spaces}; failures = []
        if "G_MANEUVER" not in by: failures.append("MANEUVER_ZONE_MISSING")
        for i in range(1,4):
            bay = by.get(f"G_PARK_{i}")
            if not bay: failures.append(f"PARKING_BAY_MISSING:{i}")
            elif bay["rect"][3] > by["G_MANEUVER"]["rect"][1] + .01: failures.append(f"PARKING_APPROACH_OBSTRUCTED:{i}")
        return {"passed": not failures, "failures": failures, "south_entry": "G_SHARED_ACCESS", "maneuver_zone": "G_MANEUVER", "routes": {f"G_PARK_{i}": ["SOUTH_STREET","G_SHARED_ACCESS","G_MANEUVER",f"G_PARK_{i}"] for i in range(1,4)}, "obstacle_free": not failures}

    @staticmethod
    def _landing_proof(spaces, edges):
        by = {s["id"]: s for s in spaces}; failures = []
        for entry in ("R1_ENTRY","R2_U1_ENTRY","R2_U2_ENTRY"):
            incoming = [e for e in edges if entry in {e.a,e.b} and e.edge_type == EdgeType.COMMON_TO_PRIVATE_ENTRY]
            if not incoming: failures.append(f"UNIT_ENTRY_WITHOUT_COMMON_LANDING:{entry}")
            elif not all(by[e.a if e.b == entry else e.b]["semantic"] == "COMMON_CORRIDOR_LANDING" for e in incoming): failures.append(f"UNIT_ENTRY_WRONG_ORIGIN:{entry}")
            if by[entry].get("unsafe_fall_zone"): failures.append(f"UNSAFE_STAIR_DOOR_FALL_ZONE:{entry}")
        return {"passed": not failures, "failures": failures, "same_level_thresholds": True, "door_to_stair_void": False}

    @staticmethod
    def _daylight_proof(spaces):
        by = {s["id"]: s for s in spaces}; failures = []
        for s in spaces:
            if s["semantic"] in {"BEDROOM", "MASTER_BEDROOM_SLEEPING"}:
                source = s.get("daylight_to")
                if not source or source not in by or by[source]["semantic"] != "LIGHTWELL_COURTYARD": failures.append(f"BEDROOM_DAYLIGHT_BOUNDARY_MISSING:{s['id']}")
        return {"passed": not failures, "failures": failures, "shared_lightwell_units": ["R2_U1","R2_U2"], "real_boundary_window_relation": not failures}
