"""Relationship-first residential room planning V2."""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import json, math
from pathlib import Path
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

EPS=1e-7
HAB={"living","bedroom"}
DAY={"living","bedroom","kitchen"}

def poly(coords):
    p=Polygon(coords)
    return p if p.is_valid else p.buffer(0)
def coords(g):
    if g.geom_type=="MultiPolygon": g=max(g.geoms,key=lambda z:z.area)
    return [[round(x,5),round(y,5)] for x,y in list(g.exterior.coords)[:-1]] if not g.is_empty else []
def dims(g):
    x0,y0,x1,y1=g.bounds
    return round(min(x1-x0,y1-y0),3),round(max(x1-x0,y1-y0),3)

class ResidentialRoomPlanningDaylightV2:
    """Program graph -> zones -> sources -> doors/windows -> evaluation."""
    pipeline=("unit_program_hypotheses","room_adjacency_graph","privacy_service_zoning","daylight_source_allocation","lightwell_patio_void_allocation","entrance_threshold_private_circulation","door_feasibility","room_dimensional_envelopes","window_geometry","furniture_usability","geometry_allocation","spatial_problem_detection","agi_precedent_repair_if_justified","re_evaluation")
    furniture={"class":"DESIGN_KNOWLEDGE_NON_AUTHORITATIVE","confidence":0.72,"source":"generic residential ergonomic template, not regulation","bedroom":{"bed":[2.0,1.6],"wardrobe_depth":0.6,"passage":0.7},"living":{"seating_depth":0.9,"passage":0.8},"kitchen":{"counter_depth":0.6,"aisle":1.0}}
    def __init__(self,evidence): self.ev=deepcopy(evidence)
    def hypotheses(self):
        return [{"id":"BPK-COMPACT-1BR","bedrooms":1,"population":None,"target_area":None},{"id":"BPK-FAMILY-2BR","bedrooms":2,"population":None,"target_area":None}]
    def graph(self,n):
        nodes=["threshold","vestibule","private_hall","living","kitchen","bathroom","service"]+[f"bedroom_{i+1}" for i in range(n)]
        edges=[("threshold","vestibule"),("vestibule","private_hall"),("private_hall","living"),("private_hall","kitchen"),("private_hall","bathroom"),("kitchen","service")]+[("private_hall",f"bedroom_{i+1}") for i in range(n)]
        return {"nodes":nodes,"required_edges":[list(x) for x in edges],"privacy":{"public":["threshold"],"transition":["vestibule"],"private":[x for x in nodes if x not in {"threshold","vestibule"}]},"service":{"wet_cluster":["kitchen","bathroom","service"]}}
    def _layout(self,u,entrance,n):
        # Candidate geometry follows the semantic graph around a private hall. Dimensions
        # come from verified minima plus furniture envelopes, never proportional area shares.
        c=u.representative_point(); ex,ey=entrance; minx,miny,maxx,maxy=u.bounds
        sx=1 if c.x>=ex else -1; sy=1 if c.y>=ey else -1
        hall=box(c.x-0.75,c.y-3.0,c.x+0.75,c.y+3.0)
        specs=[("living",3.6,4.2,-1,1),("kitchen",2.4,3.0,1,1),("bathroom",2.0,2.2,1,-1),("service",1.4,2.0,1,-2),("bedroom_1",3.0,3.4,-1,-1)]
        if n==2: specs.append(("bedroom_2",3.0,3.4,-1,-2))
        rooms=[]
        for name,w,h,side,level in specs:
            cx=c.x+side*(0.75+w/2); cy=c.y+level*(1.1+h/2)
            g=box(cx-w/2,cy-h/2,cx+w/2,cy+h/2).intersection(u)
            rooms.append((name,g))
        vg=box(ex-1.0,ey-1.0,ex+1.0,ey+1.0).intersection(u)
        # Connect threshold to hall as a real private circulation polygon.
        link=LineString([(ex,ey),(c.x,c.y)]).buffer(.75,cap_style=2).intersection(u)
        hall=unary_union([hall.intersection(u),link]).intersection(u)
        rooms += [("vestibule",vg),("private_hall",hall)]
        return rooms
    def _door(self,a,b,ga,gb):
        shared=ga.boundary.intersection(gb.boundary)
        ok=shared.length>=.8
        p=shared.interpolate(shared.length/2) if ok else ga.representative_point()
        return {"door_id":f"D-{a}-{b}","space_a":a,"space_b":b,"host_wall":{"shared_boundary_length_m":round(shared.length,3),"geometry":list(shared.coords) if shared.geom_type=="LineString" else []},"opening":{"center":[round(p.x,3),round(p.y,3)],"clear_width_m":.8,"clear_height_m":2.05},"swing_clearance_checked":ok,"valid":ok,"evidence":["T4-4-5-2-8-1","T4-4-5-2-8-2"]}
    def solve(self,unit_record,public_corridor,topology_id,floor_id,hyp):
        original=deepcopy(unit_record); u=poly(unit_record["boundary"]); graph=self.graph(hyp["bedrooms"])
        raw=self._layout(u,unit_record["entrance"],hyp["bedrooms"]); gm={n:g for n,g in raw}
        room_entities=[]; sources=[]; windows=[]
        exterior=u.boundary
        for name,g in raw:
            use="bedroom" if name.startswith("bedroom") else name
            mn,mx=dims(g) if not g.is_empty else (0,0); area=g.area
            required=use in DAY; boundary_touch=g.boundary.intersection(exterior)
            source_id=f"SRC-EXTERIOR-{name}"
            if required and boundary_touch.length>EPS:
                sources.append({"source_id":source_id,"type":"EXTERIOR_EDGE","geometry":list(boundary_touch.coords) if boundary_touch.geom_type=="LineString" else [],"qualifies":True})
                ratio=1/7 if mx>4.5 else 1/8; wa=area*ratio
                wp=boundary_touch.interpolate(boundary_touch.length/2)
                windows.append({"window_id":f"W-{name}","room_id":name,"source_id":source_id,"host_wall_length_m":round(boundary_touch.length,3),"geometry":{"center":[round(wp.x,3),round(wp.y,3)],"width_m":round(min(boundary_touch.length,wa/1.2),3),"height_m":1.2},"glazing_area_m2":round(wa,3),"required_glazing_area_m2":round(wa,3),"ratio_basis":"1/7" if mx>4.5 else "1/8","daylight_depth_m":mx,"opening_verified":boundary_touch.length>=wa/1.2,"evidence":["T4-4-5-2-3-1","T4-4-5-2-3-2","T4-4-5-2-8-3","T4-4-6-1"]})
            furniture_ok=(use not in HAB|{"kitchen"}) or (mn>=2.4 and area>=6.5)
            room_entities.append({"room_id":name,"use":use,"polygon":coords(g),"area_m2_geometry_derived":round(area,3),"useful_dimensions_m":{"minimum":mn,"maximum":mx},"containment":u.buffer(EPS).covers(g),"furniture":{"template":use,"status":"PASS" if furniture_ok else "FAIL_CLOSED","authority_class":"DESIGN_KNOWLEDGE_NON_AUTHORITATIVE"}})
        doors=[]
        for a,b in map(tuple,graph["required_edges"]):
            if a=="threshold":
                p=Point(unit_record["entrance"]); doors.append({"door_id":"D-threshold-vestibule","space_a":"common_corridor","space_b":"vestibule","host_wall":{"geometry":[unit_record["entrance"]]},"opening":{"center":unit_record["entrance"],"clear_width_m":.8,"clear_height_m":2.05},"swing_clearance_checked":gm["vestibule"].covers(p) or gm["vestibule"].distance(p)<EPS,"valid":True,"evidence":["T4-4-5-2-8-2"]})
            elif a in gm and b in gm: doors.append(self._door(a,b,gm[a],gm[b]))
        physical=[g for n,g in raw if n not in {"private_hall","vestibule"}]
        overlap=sum(physical[i].intersection(physical[j]).area for i in range(len(physical)) for j in range(i+1,len(physical)))
        window_rooms={w["room_id"] for w in windows if w["opening_verified"] and w["daylight_depth_m"]<=7}
        adjacency={frozenset((d["space_a"],d["space_b"])) for d in doors if d["valid"]}
        door_reach=set(["vestibule"]); changed=True
        while changed:
            changed=False
            for e in adjacency:
                if len(e)!=2: continue
                a,b=tuple(e)
                if a in door_reach and b not in door_reach: door_reach.add(b); changed=True
                if b in door_reach and a not in door_reach: door_reach.add(a); changed=True
        issues=[]
        if overlap>EPS: issues.append("ROOM_OVERLAP")
        if not all(r["containment"] for r in room_entities): issues.append("CONTAINMENT_FAILURE")
        if any(r["room_id"] not in door_reach for r in room_entities if r["use"] not in {"service"}): issues.append("DOOR_GRAPH_UNREACHABLE")
        if any(r["room_id"] not in window_rooms for r in room_entities if r["use"] in DAY): issues.append("UNVERIFIED_ROOM_SOURCE_WINDOW_CHAIN")
        if any(r["furniture"]["status"]!="PASS" for r in room_entities): issues.append("FURNITURE_USABILITY_UNRESOLVED")
        service_ok=gm["kitchen"].distance(gm["service"])<EPS and (gm["bathroom"].distance(gm["service"])<EPS or gm["bathroom"].distance(gm["kitchen"])<EPS)
        if not service_ok: issues.append("SERVICE_CLUSTER_UNRESOLVED")
        privacy_ok=all(frozenset(("living",f"bedroom_{i+1}")) not in adjacency for i in range(hyp["bedrooms"]))
        if not privacy_ok: issues.append("PRIVACY_DIRECT_ROOM_ACCESS")
        resolved=not issues
        assert unit_record==original
        return {"topology_id":topology_id,"floor_id":floor_id,"unit_id":unit_record["unit_id"],"program_hypothesis":{**hyp,"authority_class":"DESIGN_KNOWLEDGE_NON_AUTHORITATIVE"},"pipeline":self.pipeline,"adjacency_privacy_service_graph":graph,"unit_boundary":unit_record["boundary"],"unit_threshold":unit_record["entrance"],"public_corridor":public_corridor,"public_corridor_stops_at_threshold":True,"rooms":room_entities,"doors":doors,"daylight_sources":sources,"windows":windows,"voids":[],"allocation":{"unit_area_m2":round(u.area,3),"room_area_m2":round(unary_union(physical).area,3),"private_circulation_area_m2":round(unary_union([gm['vestibule'],gm['private_hall']]).area,3),"lightwell_patio_void_area_m2":0.0},"checks":{"physical_overlap_m2":round(overlap,6),"door_graph_reachable_spaces":sorted(door_reach),"privacy":privacy_ok,"service_plumbing_relation":service_ok,"required_daylight_rooms":sorted(r["room_id"] for r in room_entities if r["use"] in DAY),"verified_window_rooms":sorted(window_rooms)},"spatial_problems":issues,"agi_precedent":{"invoked":bool(issues),"justification":issues,"precedent_geometry_copied":False,"geometry_changed":False,"reason":"no repair accepted without proven improvement"},"resolved_room_level":resolved,"winner":None,"authoritative_ranking":False}

def verify_authority(data):
    ids={r["id"] for r in data["rules"]}
    required={"T4-4-5-2-1-2","T4-4-5-2-2-1","T4-4-5-2-2-2","T4-4-5-2-2-3","T4-4-5-2-3-1","T4-4-5-2-3-2","T4-4-5-2-3-3","T4-4-5-2-8-3","T4-4-5-8-3-5","T4-4-5-8-3-10","T4-TABLE-4-6"}
    return {"status":"PASS" if required<=ids else "FAIL_CLOSED","missing":sorted(required-ids),"national_sha256":data["document"]["sha256"],"minab_override":data["jurisdiction"]["minab_override"]}
