from __future__ import annotations

"""Furniture-aware door/window intent solving and hard acceptance gates."""

from collections import defaultdict, deque
from copy import deepcopy

EPS = 1e-6
BEDROOMS = {"master", "bed2", "bed3"}
WET = {"bath", "guest_wc", "wc", "bathroom"}
VALID_SOURCES = {"SOUTH_YARD", "NORTH_REAR_YARD", "EAST_SERVICE_YARD", "COURTYARD"}


def _shared(a, b):
    ax1, ay1, ax2, ay2 = a; bx1, by1, bx2, by2 = b
    if abs(ax2-bx1) < EPS or abs(bx2-ax1) < EPS:
        fixed = ax2 if abs(ax2-bx1) < EPS else ax1
        lo, hi = max(ay1, by1), min(ay2, by2)
        return ("V", fixed, lo, hi) if hi-lo > EPS else None
    if abs(ay2-by1) < EPS or abs(by2-ay1) < EPS:
        fixed = ay2 if abs(ay2-by1) < EPS else ay1
        lo, hi = max(ax1, bx1), min(ax2, bx2)
        return ("H", fixed, lo, hi) if hi-lo > EPS else None
    return None


def _point_in_rect(p, r, pad=0.0):
    return r[0]-pad <= p[0] <= r[2]+pad and r[1]-pad <= p[1] <= r[3]+pad


def _swing_box(axis, fixed, hinge, width, side):
    if axis == "H":
        return [hinge-width, fixed, hinge+width, fixed+side*width]
    return [fixed, hinge-width, fixed+side*width, hinge+width]


def _normalize_rect(r):
    return [min(r[0],r[2]), min(r[1],r[3]), max(r[0],r[2]), max(r[1],r[3])]


def _overlap(a, b):
    a=_normalize_rect(a); b=_normalize_rect(b)
    return min(a[2],b[2])-max(a[0],b[0]) > EPS and min(a[3],b[3])-max(a[1],b[1]) > EPS


def _room_side(axis, fixed, room):
    cx=(room[0]+room[2])/2; cy=(room[1]+room[3])/2
    return 1 if (cy > fixed if axis == "H" else cx > fixed) else -1


def furniture_proxies(candidate):
    out=[]
    for r in candidate["rooms"]:
        rid=r["id"]; x1,y1,x2,y2=r["polygon"]; w=x2-x1; h=y2-y1
        if rid in BEDROOMS:
            out += [{"room":rid,"kind":"BED","rect":[x1+.25,y1+.35,min(x2-.9,x1+2.25),min(y2-.35,y1+2.45)]},
                    {"room":rid,"kind":"WARDROBE","rect":[x2-.75,y1+.2,x2-.15,min(y2-.2,y1+1.9)]}]
        elif rid == "kitchen":
            out += [{"room":rid,"kind":"BASE_CABINET","rect":[x1+.1,y1+.1,min(x2-.1,x1+2.3),y1+.7]},
                    {"room":rid,"kind":"TALL_CABINET","rect":[x2-.85,y1+.1,x2-.15,y1+.9]}]
        elif rid in WET:
            out += [{"room":rid,"kind":"FIXTURE","rect":[x1+.15,y1+.15,min(x2-.1,x1+1.0),min(y2-.1,y1+1.05)]}]
        elif rid == "living":
            out += [{"room":rid,"kind":"SOFA","rect":[x1+.25,y1+.4,min(x2-.2,x1+2.5),y1+1.3]},
                    {"room":rid,"kind":"TV_WALL","rect":[max(x1+.1,x2-2.1),y2-.7,x2-.1,y2-.15]}]
    return out


def solve_contract(candidate):
    c=deepcopy(candidate); rooms={r["id"]:r for r in c["rooms"]}; proxies=furniture_proxies(c)
    by_room=defaultdict(list)
    for p in proxies: by_room[p["room"]].append(p)
    for d in c.get("doors",[]):
        src,dst=d["connects"]; target=dst if dst in rooms else src
        if src == "SITE_ENTRY": target=dst
        host=d.get("geometry")
        shared = host if src == "SITE_ENTRY" else _shared(rooms[src]["polygon"],rooms[dst]["polygon"])
        d.update({"class":d["type"],"from_space":src,"to_space":dst,"host_segment":list(shared) if shared else None,
                  "arrival_side":src,"swing_direction":"INTO_SERVED_ROOM","swing_into_space":target})
        if not shared:
            d.update(hinge_side="UNRESOLVED", conflict_score=999, swing_collision_free=False); continue
        axis,fixed,a,b=shared; width=float(d["clear_width_m"])
        usable_lo=a+.10+width/2; usable_hi=b-.10-width/2
        mids=[(a+b)/2] if usable_hi < usable_lo else [usable_lo,(usable_lo+usable_hi)/2,usable_hi]
        candidates=[]
        for mid in mids:
            for hinge_side,hinge in (("START",mid-width/2),("END",mid+width/2)):
                for swing_space in (target,src if src in rooms else target):
                    side=_room_side(axis,fixed,rooms[swing_space]["polygon"])
                    box=_swing_box(axis,fixed,hinge,width,side)
                    conflicts=[p["kind"] for p in by_room[swing_space] if _overlap(box,p["rect"])]
                    score=len(conflicts)*100 + (0 if swing_space==target else 20) + abs(mid-(a+b)/2)
                    candidates.append((score,hinge_side,swing_space,box,conflicts,mid))
        best=min(candidates,key=lambda x:x[0]); d.update(hinge_side=best[1],swing_into_space=best[2],
            swing_direction="INTO_SERVED_ROOM" if best[2]==target else "OUT_OF_SERVED_ROOM",
            conflict_score=round(best[0],3),swing_box=_normalize_rect(best[3]),swing_conflicts=best[4],swing_collision_free=not best[4],
            swing_resolution_reason="PREFERRED_INTO_SERVED_ROOM" if best[2]==target else "OUTSWING_SELECTED_TO_AVOID_SERVED_ROOM_FURNITURE_OR_JOINERY",
            geometry=[axis,fixed,best[5]-width/2,best[5]+width/2])
    for w in c.get("windows",[]):
        room=rooms[w["room"]]; src=w["source"]; geom=w.get("geometry")
        axis,fixed,a,b=geom if geom else (None,None,None,None)
        boundary_ok=False; outward=None
        x1,y1,x2,y2=room["polygon"]
        if axis=="H" and abs(fixed-y1)<EPS and src=="SOUTH_YARD": boundary_ok=True; outward=[0,-1]
        elif axis=="H" and abs(fixed-y2)<EPS and src=="NORTH_REAR_YARD": boundary_ok=True; outward=[0,1]
        elif axis=="V" and abs(fixed-x2)<EPS and src=="EAST_SERVICE_YARD": boundary_ok=True; outward=[1,0]
        elif src=="COURTYARD": boundary_ok=True
        conflict=[p["kind"] for p in by_room[w["room"]] if axis and _overlap(([a,fixed-.15,b,fixed+.15] if axis=="H" else [fixed-.15,a,fixed+.15,b]),p["rect"])]
        w.update(window_class=w["type"],host_segment=list(geom) if geom else None,daylight_source=src,
                 outward_normal=outward,source_adjacency_proof={"room_boundary":list(geom) if geom else None,"source":src,"exact_shared_boundary":boundary_ok},
                 furniture_conflicts=conflict,valid_exposure=boundary_ok and src in VALID_SOURCES)
    c["furniture_opening_proxies"]=proxies
    return c


def validate_contract(c):
    findings=[]; rooms={r["id"]:r for r in c["rooms"]}; graph=defaultdict(set)
    for o in c.get("open_connections",[]):
        a,b=o["connects"]; graph[a].add(b); graph[b].add(a)
    for d in c.get("doors",[]):
        a,b=d["connects"]
        if d.get("host_segment") is None: findings.append({"code":"DOOR_NOT_ON_SHARED_BOUNDARY","id":d["id"]})
        if d.get("swing_conflicts"): findings.append({"code":"DOOR_SWING_COLLISION","id":d["id"],"conflicts":d["swing_conflicts"]})
        if d.get("swing_direction")!="INTO_SERVED_ROOM" and b in BEDROOMS: findings.append({"code":"DOOR_OPENS_TO_WRONG_SIDE","id":d["id"]})
        graph[a].add(b); graph[b].add(a)
        if "kitchen" in (a,b) and any(x in {"BASE_CABINET","TALL_CABINET"} for x in d.get("swing_conflicts",[])):
            findings.append({"code":"KITCHEN_ENTRY_BLOCKED_BY_JOINERY","id":d["id"]})
    if "private_hall" not in graph or not (graph["private_hall"] & {"foyer","family","living"}): findings.append({"code":"PRIVATE_HALL_NO_INGRESS"})
    reachable=set(); q=deque(["SITE_ENTRY"])
    while q:
        n=q.popleft()
        if n in reachable: continue
        reachable.add(n); q.extend(graph[n]-reachable)
    if "private_hall" not in reachable: findings.append({"code":"PRIVATE_WING_SEALED"})
    for bid in BEDROOMS & set(rooms):
        direct=graph[bid] & {"private_hall","family","foyer"}
        if not direct: findings.append({"code":"BEDROOM_NO_INDEPENDENT_DOOR","room":bid})
        if graph[bid] & BEDROOMS: findings.append({"code":"BEDROOM_THROUGH_BEDROOM_ACCESS","room":bid})
    for w in c.get("windows",[]):
        if not w.get("source_adjacency_proof",{}).get("exact_shared_boundary"):
            findings.append({"code":"WINDOW_SOURCE_NOT_ADJACENT","id":w["id"]})
        if w.get("source") not in VALID_SOURCES: findings.append({"code":"WINDOW_TO_NEIGHBOR_PLOT","id":w["id"]})
        if w.get("furniture_conflicts"): findings.append({"code":"WINDOW_FURNITURE_COLLISION","id":w["id"]})
    groups={"ACCESS":{"PRIVATE_HALL_NO_INGRESS","PRIVATE_WING_SEALED","BEDROOM_NO_INDEPENDENT_DOOR","BEDROOM_THROUGH_BEDROOM_ACCESS"},
            "DOOR SEMANTICS":{"DOOR_NOT_ON_SHARED_BOUNDARY","DOOR_SWING_COLLISION","DOOR_OPENS_TO_WRONG_SIDE","KITCHEN_ENTRY_BLOCKED_BY_JOINERY"},
            "WINDOW/DAYLIGHT SEMANTICS":{"WINDOW_SOURCE_NOT_ADJACENT","WINDOW_TO_NEIGHBOR_PLOT","WINDOW_TO_INTERNAL_ROOM","WINDOW_HOST_WRONG_WALL"},
            "FURNITURE/OPENING COMPATIBILITY":{"DOOR_SWING_COLLISION","KITCHEN_ENTRY_BLOCKED_BY_JOINERY","WINDOW_FURNITURE_COLLISION"}}
    codes={x["code"] for x in findings}; verdict={k:("FAIL" if codes&v else "PASS") for k,v in groups.items()}
    verdict["PLAN REALIZATION"]="FAIL" if findings else "PASS"; verdict["HUMAN ARCHITECTURAL ACCEPTANCE"]="PENDING"
    return {"status":"FAIL" if findings else "PASS","findings":findings,"verdict":verdict}
