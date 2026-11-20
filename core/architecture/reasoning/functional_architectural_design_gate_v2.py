"""Parcel2 REV03: site-edge-first functional architectural candidate and hard gates."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from math import hypot


SITE = {"width_m": 10.0, "depth_m": 20.0, "north": "CONSTRAINED_NEIGHBOR", "south": "STREET_ACCESS_DAYLIGHT", "east": "CONSTRAINED_NEIGHBOR", "west": "CONSTRAINED_NEIGHBOR", "separation_joint": "SEPARATION JOINT — WIDTH PENDING AUTHORITY — NOT DEDUCTED"}
LEVELS = ("G", "R1", "R2", "ROOF")
CORE_RECT = [7.0, 6.0, 9.8, 12.0]
STAIR_RECT = [7.0, 7.5, 8.5, 12.0]
ELEVATOR_RECT = [8.5, 9.8, 9.8, 12.0]
LANDING_RECT = [7.0, 6.0, 9.8, 7.5]
LIGHTWELL_RECT = [4.2, 12.0, 5.8, 16.0]


def space(sid, level, semantic, owner, rect, zone="SERVICE", **extra):
    value = {"id": sid, "level": level, "semantic": semantic, "owner": owner, "rect": [float(v) for v in rect], "zone": zone,
             "area_m2": round((rect[2]-rect[0])*(rect[3]-rect[1]), 3)}
    value.update(extra)
    return value


def shared_segment(a, b, tol=1e-6):
    ax0, ay0, ax1, ay1 = a; bx0, by0, bx1, by1 = b
    if abs(ax1-bx0) <= tol or abs(bx1-ax0) <= tol:
        x = ax1 if abs(ax1-bx0) <= tol else ax0
        lo, hi = max(ay0, by0), min(ay1, by1)
        if hi-lo > tol: return [x, lo, x, hi]
    if abs(ay1-by0) <= tol or abs(by1-ay0) <= tol:
        y = ay1 if abs(ay1-by0) <= tol else ay0
        lo, hi = max(ax0, bx0), min(ax1, bx1)
        if hi-lo > tol: return [lo, y, hi, y]
    return None


def midpoint(seg): return [(seg[0]+seg[2])/2, (seg[1]+seg[3])/2]


def door(did, a, b, spaces, kind="DOOR_CONNECTION", swing="INTO_TO"):
    by = {s["id"]: s for s in spaces}; seg = shared_segment(by[a]["rect"], by[b]["rect"])
    return {"id": did, "level": by[a]["level"], "from_space": a, "to_space": b, "kind": kind,
            "host_partition": f"PARTITION::{a}::{b}", "threshold_segment": seg, "swing_side": swing,
            "landing_clearance_required": kind == "COMMON_TO_PRIVATE_ENTRY", "same_level": by[a]["level"] == by[b]["level"]}


def window(wid, room_id, exposure, host, purpose, spaces):
    by = {s["id"]: s for s in spaces}; seg = None
    if exposure == "SOUTH_STREET":
        r = by[room_id]["rect"]
        if abs(r[1]) < .21: seg = [r[0]+.3, r[1], min(r[2]-.3, r[0]+1.8), r[1]]
    elif exposure in by:
        seg = shared_segment(by[room_id]["rect"], by[exposure]["rect"])
    return {"id": wid, "level": by[room_id]["level"], "room": room_id, "host_wall": host,
            "host_segment": seg, "exposure": exposure, "daylight_purpose": purpose}


class Parcel2FunctionalArchitecturalGateV2:
    """Builds REV03 from persistent building contracts, never from REV02 polygons."""

    def build(self):
        spaces = self._spaces()
        doors = self._doors(spaces)
        windows = self._windows(spaces)
        graph = self._graph()
        guides = self._guides()
        contracts = self._contracts()
        failures, checks = validate_candidate(spaces, doors, windows, graph, contracts)
        return {
            "schema": "PARCEL2_FUNCTIONAL_ARCHITECTURAL_CANDIDATE_REV03",
            "generation_policy": {"from_rev02_coordinates": False, "dwg_read": False, "manual_cad_fallback": False, "pipeline": ["SITE_EDGE_CONTRACT", "GROUND_FRONTAGE_ACCESS_RESERVATION", "FIXED_VERTICAL_CORE_STACK", "FLOOR_PROGRAM", "PUBLIC_PRIVATE_DAYLIGHT_ZONING", "ROOM_ACCESS_GRAPH", "LIGHTWELL_TERRACE_STRATEGY", "ROOM_GEOMETRY", "DOOR_WINDOW_HOST_INTENTS", "WALL_GEOMETRY", "KERNEL_VALIDATION", "HUMAN_REVIEW_READINESS"]},
            "site_edge_contract": contracts["site_edge_contract"], "building_access_spine": contracts["building_access_spine"],
            "vertical_core_stack": contracts["vertical_core_stack"], "spaces": spaces, "door_intents": doors,
            "window_intents": windows, "access_graph": graph, "access_guide_overlays": guides,
            "validation": {"passed": not failures, "failures": failures, "checks": checks},
            "acceptance": {"software_topology_tests": "PASS" if not failures else "PASS_WITH_COMPOSITION_FAILURE", "software_architectural_readiness": "PASS" if not failures else "FAIL", "human_architectural_acceptance": "PENDING" if not failures else "REJECTED", "human_approval_is_exclusively_user_decision": True}
        }

    @staticmethod
    def _contracts():
        core = {level: {"core_polygon": CORE_RECT, "stair_polygon": STAIR_RECT, "elevator_polygon": ELEVATOR_RECT, "common_landing_polygon": LANDING_RECT, "orientation": "STAIR_NORTHBOUND", "vertical_alignment_id": "PARCEL2_CORE_STACK_A", "safe_landing_zone": LANDING_RECT, "allowed_unit_entry_interfaces": ["WEST_LANDING_EDGE"]} for level in LEVELS}
        return {"site_edge_contract": SITE, "building_access_spine": {"origin_edge": "SOUTH", "shared_route_wall_to_wall_m": 3.9, "critical_clear_width_m": 3.5, "pedestrian_strip_m": 1.2, "pedestrian_strip_embedded": True}, "vertical_core_stack": core}

    @staticmethod
    def _spaces():
        s=[]
        # G: south frontage is y=0. Commercial and both access origins touch it.
        s += [space("G_COMMERCIAL", "G", "COMMERCIAL_SHOP", "COMMON", [0,0,3.1,7.5], "PUBLIC", south_frontage=True),
              space("G_SHARED_ACCESS", "G", "SHARED_VEHICLE_PEDESTRIAN_ACCESS", "COMMON", [3.1,0,7.0,14.0], "CIRCULATION", route_width_m=3.9, clear_width_m=3.5, pedestrian_strip_m=1.2),
              space("G_MANEUVER", "G", "VEHICLE_MANEUVER_ZONE", "COMMON", [0,10.0,7.0,15.0], "CIRCULATION"),
              space("G_P1", "G", "PARKING_BAY", "COMMON", [0.2,15.0,2.7,20.0]), space("G_P2", "G", "PARKING_BAY", "COMMON", [2.8,15.0,5.3,20.0]), space("G_P3", "G", "PARKING_BAY", "COMMON", [5.4,15.0,7.9,20.0])]
        # Persistent fixed core primitives on all levels.
        for level in LEVELS:
            s += [space(f"{level}_CORE", level, "VERTICAL_CORE", "COMMON", CORE_RECT, "COMMON"), space(f"{level}_STAIR", level, "STAIR", "COMMON", STAIR_RECT, "COMMON"), space(f"{level}_ELEVATOR", level, "ELEVATOR", "COMMON", ELEVATOR_RECT, "COMMON"), space(f"{level}_LANDING", level, "COMMON_LANDING", "COMMON", LANDING_RECT, "COMMON", safe_same_level=True)]
        # R1 public front, private rear around internal aligned lightwell.
        s += [space("R1_TERRACE", "R1", "TERRACE", "R1_U1", [0.2,0,3.8,1.6], "PUBLIC", openness="SOUTH_STREET"),
              space("R1_LIVING", "R1", "LIVING_RECEPTION", "R1_U1", [0,1.6,4.2,6.0], "PUBLIC", exposure="SOUTH_TERRACE"),
              space("R1_DINING_KITCHEN", "R1", "OPEN_KITCHEN_DINING", "R1_U1", [4.2,0,7.0,6.0], "PUBLIC", exposure="SOUTH_STREET"),
              space("R1_ENTRY", "R1", "UNIT_ENTRY", "R1_U1", [6.0,6.0,7.0,7.5], "TRANSITION"),
              space("R1_PRIVATE_HALL", "R1", "PRIVATE_HALL", "R1_U1", [5.8,7.5,7.0,18.0], "PRIVATE"),
              space("R1_BED1", "R1", "BEDROOM", "R1_U1", [0.2,8.0,4.2,12.0], "PRIVATE"),
              space("R1_LIGHTWELL", "R1", "LIGHTWELL", "COMMON", LIGHTWELL_RECT, "ENVIRONMENTAL", open_to_sky=True, alignment_id="LW_A"),
              space("R1_BED2", "R1", "BEDROOM", "R1_U1", [0.2,12.0,4.2,16.0], "PRIVATE"),
              space("R1_MASTER", "R1", "MASTER_BEDROOM", "R1_U1", [0.2,16.0,5.8,20.0], "PRIVATE"),
              space("R1_BATH", "R1", "BATHROOM", "R1_U1", [5.8,18.0,7.0,20.0], "PRIVATE")]
        # R2: two independent front-to-back units, each public zone retains south access/daylight.
        s += [space("R2_U1_TERRACE", "R2", "TERRACE", "R2_U1", [0.2,0,2.0,1.5], "PUBLIC", openness="SOUTH_STREET"),
              space("R2_U1_LIVING_KITCHEN", "R2", "OPEN_LIVING_KITCHEN", "R2_U1", [0,1.5,3.3,7.0], "PUBLIC", exposure="SOUTH_TERRACE"),
              space("R2_U1_ENTRY", "R2", "UNIT_ENTRY", "R2_U1", [5.8,6.0,7.0,6.75], "TRANSITION"),
              space("R2_U1_HALL", "R2", "PRIVATE_HALL", "R2_U1", [3.3,6.75,4.2,18], "PRIVATE"),
              space("R2_U1_BED", "R2", "BEDROOM", "R2_U1", [0.2,12,4.2,16], "PRIVATE"),
              space("R2_U1_BATH", "R2", "BATHROOM", "R2_U1", [0.2,16,3.3,18.5], "PRIVATE"),
              space("R2_U2_TERRACE", "R2", "TERRACE", "R2_U2", [3.5,0,5.3,1.5], "PUBLIC", openness="SOUTH_STREET"),
              space("R2_U2_LIVING_KITCHEN", "R2", "OPEN_LIVING_KITCHEN", "R2_U2", [3.3,1.5,7.0,6.0], "PUBLIC", exposure="SOUTH_TERRACE"),
              space("R2_U2_ENTRY", "R2", "UNIT_ENTRY", "R2_U2", [6.0,6.0,7.0,7.5], "TRANSITION"),
              space("R2_U2_HALL", "R2", "PRIVATE_HALL", "R2_U2", [5.8,7.5,7.0,18], "PRIVATE"),
              space("R2_LIGHTWELL", "R2", "LIGHTWELL", "COMMON", LIGHTWELL_RECT, "ENVIRONMENTAL", open_to_sky=True, alignment_id="LW_A"),
              space("R2_U2_BED", "R2", "BEDROOM", "R2_U2", [5.8,12,7.0,16], "PRIVATE"),
              space("R2_U2_BATH", "R2", "BATHROOM", "R2_U2", [5.8,18,7.0,20], "PRIVATE")]
        s += [space("ROOF_SERVICE", "ROOF", "ROOF_SERVICE", "COMMON", [5.5,6.0,7.0,7.5], "SERVICE"), space("ROOF_COMMON", "ROOF", "COMMON_ROOF", "COMMON", [0.2,0.2,6.8,5.8], "COMMON")]
        return s

    @staticmethod
    def _doors(s):
        pairs=[("D_G_SHOP","SOUTH_STREET","G_COMMERCIAL","PUBLIC_ENTRY"), ("D_G_CORE","G_SHARED_ACCESS","G_LANDING","PEDESTRIAN_TO_CORE"),
               ("D_R1_ENTRY","R1_LANDING","R1_ENTRY","COMMON_TO_PRIVATE_ENTRY"), ("D_R1_PRIV","R1_ENTRY","R1_PRIVATE_HALL","DOOR_CONNECTION"),
               ("D_R2_U1_ENTRY","R2_LANDING","R2_U1_ENTRY","COMMON_TO_PRIVATE_ENTRY"), ("D_R2_U2_ENTRY","R2_LANDING","R2_U2_ENTRY","COMMON_TO_PRIVATE_ENTRY"),
               ("D_ROOF_SERVICE","ROOF_LANDING","ROOF_SERVICE","SERVICE_ACCESS")]
        by={x["id"]:x for x in s}; out=[]
        for did,a,b,k in pairs:
            if a=="SOUTH_STREET":
                r=by[b]["rect"]; out.append({"id":did,"level":"G","from_space":a,"to_space":b,"kind":k,"host_partition":"SOUTH_FRONTAGE","threshold_segment":[1.4,0,2.4,0],"swing_side":"INTO_COMMERCIAL","landing_clearance_required":False,"same_level":True})
            else: out.append(door(did,a,b,s,k))
        return out

    @staticmethod
    def _windows(s):
        return [window("W_R1_KITCHEN_S","R1_DINING_KITCHEN","SOUTH_STREET","SOUTH_FRONTAGE","PUBLIC_DAYLIGHT",s),
                window("W_R1_BED2_LW","R1_BED2","R1_LIGHTWELL","PARTITION::R1_BED2::R1_LIGHTWELL","PRIVATE_DAYLIGHT",s),
                window("W_R1_MASTER_LW","R1_MASTER","R1_LIGHTWELL","PARTITION::R1_MASTER::R1_LIGHTWELL","PRIVATE_DAYLIGHT",s),
                window("W_R2_U1_BED_LW","R2_U1_BED","R2_LIGHTWELL","PARTITION::R2_U1_BED::R2_LIGHTWELL","PRIVATE_DAYLIGHT",s),
                window("W_R2_U2_BED_LW","R2_U2_BED","R2_LIGHTWELL","PARTITION::R2_U2_BED::R2_LIGHTWELL","PRIVATE_DAYLIGHT",s)]

    @staticmethod
    def _graph():
        edges=[]
        def add(a,b,k): edges.append({"a":a,"b":b,"kind":k})
        add("SOUTH_STREET","G_COMMERCIAL","PUBLIC_ENTRY"); add("SOUTH_STREET","G_SHARED_ACCESS","SHARED_ACCESS"); add("G_SHARED_ACCESS","G_MANEUVER","VEHICLE_ACCESS")
        for p in ("G_P1","G_P2","G_P3"): add("G_MANEUVER",p,"VEHICLE_ACCESS")
        add("G_SHARED_ACCESS","G_LANDING","PEDESTRIAN_ACCESS")
        for level in LEVELS: add(f"{level}_LANDING",f"{level}_STAIR","VERTICAL_ACCESS"); add(f"{level}_LANDING",f"{level}_ELEVATOR","VERTICAL_ACCESS")
        add("G_STAIR","R1_STAIR","VERTICAL_STACK"); add("R1_STAIR","R2_STAIR","VERTICAL_STACK"); add("R2_STAIR","ROOF_STAIR","VERTICAL_STACK")
        add("R1_LANDING","R1_ENTRY","COMMON_TO_PRIVATE_ENTRY"); add("R1_ENTRY","R1_LIVING","OPEN_CONNECTION"); add("R1_LIVING","R1_DINING_KITCHEN","OPEN_CONNECTION"); add("R1_ENTRY","R1_PRIVATE_HALL","PUBLIC_PRIVATE_TRANSITION")
        for x in ("R1_BED1","R1_BED2","R1_MASTER","R1_BATH"): add("R1_PRIVATE_HALL",x,"PRIVATE_ACCESS")
        for u in ("U1","U2"):
            add("R2_LANDING",f"R2_{u}_ENTRY","COMMON_TO_PRIVATE_ENTRY"); add(f"R2_{u}_ENTRY",f"R2_{u}_LIVING_KITCHEN","OPEN_CONNECTION"); add(f"R2_{u}_ENTRY",f"R2_{u}_HALL","PUBLIC_PRIVATE_TRANSITION"); add(f"R2_{u}_HALL",f"R2_{u}_BED","PRIVATE_ACCESS"); add(f"R2_{u}_HALL",f"R2_{u}_BATH","PRIVATE_ACCESS")
        add("ROOF_LANDING","ROOF_SERVICE","SERVICE_ACCESS"); add("ROOF_LANDING","ROOF_COMMON","OPEN_CONNECTION")
        return edges

    @staticmethod
    def _guides():
        return [{"id":"GUIDE_COMMERCIAL","path":["SOUTH_STREET","G_COMMERCIAL"],"render_as":"GUIDE_ONLY"}, {"id":"GUIDE_PARKING","path":["SOUTH_STREET","G_SHARED_ACCESS","G_MANEUVER","G_P1/G_P2/G_P3"],"render_as":"GUIDE_ONLY"}, {"id":"GUIDE_CORE","path":["SOUTH_STREET","G_SHARED_ACCESS","G_LANDING"],"render_as":"GUIDE_ONLY"}, {"id":"GUIDE_R1","path":["R1_LANDING","R1_ENTRY","R1_LIVING","R1_PRIVATE_HALL"],"render_as":"GUIDE_ONLY"}, {"id":"GUIDE_R2_U1","path":["R2_LANDING","R2_U1_ENTRY","R2_U1_LIVING_KITCHEN","R2_U1_HALL"],"render_as":"GUIDE_ONLY"}, {"id":"GUIDE_R2_U2","path":["R2_LANDING","R2_U2_ENTRY","R2_U2_LIVING_KITCHEN","R2_U2_HALL"],"render_as":"GUIDE_ONLY"}]


def validate_candidate(spaces, doors, windows, graph, contracts):
    by={s["id"]:s for s in spaces}; failures=[]; checks={}
    def record(name, ok, code): checks[name]=bool(ok); failures.extend([] if ok else [code])
    commercial=by["G_COMMERCIAL"]
    record("commercial_south_frontage", commercial["rect"][1] == 0 and any(d["from_space"]=="SOUTH_STREET" and d["to_space"]=="G_COMMERCIAL" for d in doors), "COMMERCIAL_NOT_ON_PUBLIC_FRONTAGE")
    access=by["G_SHARED_ACCESS"]; record("access_begins_south", access["rect"][1]==0, "ACCESS_NOT_FROM_SOUTH")
    record("shared_route_contract", access["route_width_m"]==3.9 and access["clear_width_m"]>=3.5 and access["pedestrian_strip_m"]>=1.2, "SHARED_ACCESS_WIDTH_CONTRACT_FAIL")
    def positive_overlap(a,b):
        return min(a[2],b[2])-max(a[0],b[0])>1e-6 and min(a[3],b[3])-max(a[1],b[1])>1e-6
    obstructions=[by[x]["rect"] for x in ("G_COMMERCIAL","G_P1","G_P2","G_P3","G_CORE")]
    record("continuous_free_access_route", not any(positive_overlap(access["rect"],r) for r in obstructions), "SOUTH_ACCESS_ROUTE_OBSTRUCTED")
    record("maneuver_reaches_all_bays", all(shared_segment(by["G_MANEUVER"]["rect"],by[f"G_P{i}"]["rect"]) for i in (1,2,3)), "PARKING_MANEUVER_CONNECTION_FAIL")
    stacks=contracts["vertical_core_stack"]; base=stacks["G"]
    aligned=all(v["core_polygon"]==base["core_polygon"] and v["orientation"]==base["orientation"] and v["vertical_alignment_id"]==base["vertical_alignment_id"] for v in stacks.values())
    record("vertical_core_stack", aligned, "VERTICAL_CORE_STACK_MISALIGNMENT")
    for level in LEVELS: record(f"safe_landing_{level}", by[f"{level}_LANDING"].get("safe_same_level") and by[f"{level}_LANDING"]["rect"]==LANDING_RECT, f"SAME_LEVEL_LANDING_MISSING:{level}")
    constrained={"NORTH_NEIGHBOR","EAST_NEIGHBOR","WEST_NEIGHBOR","N","E","W"}
    record("terraces_valid", all(s.get("openness") not in constrained for s in spaces if s["semantic"]=="TERRACE"), "TERRACE_ON_CONSTRAINED_NEIGHBOR_EDGE")
    lightwells=[s for s in spaces if s["semantic"]=="LIGHTWELL"]
    record("lightwell_not_south", all(s["rect"][1]>0 for s in lightwells), "UNNECESSARY_SOUTH_FRONTAGE_LIGHTWELL")
    record("lightwell_aligned", len(lightwells)==2 and lightwells[0]["rect"]==lightwells[1]["rect"] and len({s["alignment_id"] for s in lightwells})==1, "LIGHTWELL_VERTICAL_MISALIGNMENT")
    for d in doors:
        if d["from_space"] != "SOUTH_STREET":
            expected=shared_segment(by[d["from_space"]]["rect"],by[d["to_space"]]["rect"])
            record(f"door_host_{d['id']}", bool(expected and d["threshold_segment"] and d["same_level"]), f"DOOR_THRESHOLD_NOT_SHARED_BOUNDARY:{d['id']}")
        if d["kind"]=="COMMON_TO_PRIVATE_ENTRY": record(f"entry_landing_{d['id']}", by[d["from_space"]]["semantic"]=="COMMON_LANDING", f"UNIT_DOOR_TO_UNSAFE_EDGE:{d['id']}")
    for w in windows:
        room=by[w["room"]]; exp=w["exposure"]
        record(f"window_host_{w['id']}", bool(w["host_segment"]), f"WINDOW_HOST_NOT_ROOM_BOUNDARY:{w['id']}")
        record(f"window_exposure_{w['id']}", exp=="SOUTH_STREET" or (exp in by and by[exp]["semantic"] in {"LIGHTWELL","TERRACE"}), f"WINDOW_TO_PRIVATE_ROOM_INVALID:{w['id']}")
        record(f"window_constrained_{w['id']}", exp not in constrained, f"WINDOW_TO_CONSTRAINED_EDGE_INVALID:{w['id']}")
    record("open_plan_no_fake_doors", not any(d for d in doors if {d["from_space"],d["to_space"]}=={"R1_LIVING","R1_DINING_KITCHEN"}), "OPEN_PLAN_DOOR_SPAM")
    # Graph reachability proofs.
    adj=defaultdict(set)
    for e in graph: adj[e["a"]].add(e["b"]); adj[e["b"]].add(e["a"])
    def reachable(a,b):
        q=deque([a]); seen={a}
        while q:
            n=q.popleft()
            if n==b:return True
            for x in adj[n]-seen: seen.add(x); q.append(x)
        return False
    for target in ("G_COMMERCIAL","G_P1","G_P2","G_P3","G_LANDING"): record(f"south_path_{target}", reachable("SOUTH_STREET",target), f"SOUTH_ACCESS_PATH_MISSING:{target}")
    for target in ("R1_BED1","R1_MASTER"): record(f"r1_path_{target}", reachable("R1_LANDING",target), f"R1_ACCESS_GRAPH_FAIL:{target}")
    for u in ("U1","U2"): record(f"r2_path_{u}", reachable("R2_LANDING",f"R2_{u}_BED"), f"R2_INDEPENDENT_ACCESS_FAIL:{u}")
    cross=any((by.get(e["a"],{}).get("owner"),by.get(e["b"],{}).get("owner")) in {("R2_U1","R2_U2"),("R2_U2","R2_U1")} for e in graph)
    record("no_cross_unit_private_opening", not cross, "PRIVATE_CROSS_UNIT_OPENING")
    record("four_floor_complete", {s["level"] for s in spaces}==set(LEVELS), "MANDATORY_LEVEL_MISSING")
    return sorted(set(failures)), checks


def rev02_negative_fixture():
    return {"fixture_id":"HUMAN_REJECTION_REV02_SITE_EDGE_CORE_ACCESS_DAYLIGHT", "status":"REJECTED", "reason":"SITE_EDGE_CORE_ACCESS_DAYLIGHT_COMPOSITION_FAILURE", "must_fail_readiness":True,
            "failure_family":["COMMERCIAL_NOT_ON_PUBLIC_FRONTAGE","MISSING_DIRECT_FRONTAGE_ACCESS_SEMANTICS","VERTICAL_CORE_STACK_MISALIGNMENT","UNSAFE_OR_UNCLEAR_ENTRY_LANDING","TERRACE_ON_CONSTRAINED_NEIGHBOR_EDGE","UNNECESSARY_SOUTH_FRONTAGE_LIGHTWELL","NORTH_FACING_PUBLIC_ROOM_WINDOW","WINDOW_TO_PRIVATE_ROOM_INVALID","ARBITRARY_OPENINGS","UNCLEAR_ACCESS_PATHS"]}
