from __future__ import annotations

from collections import deque
from .state import ConstraintKind, ConstraintResult, ArchitecturalDesignState


def _r(cid, kind, ok, spaces, evidence, reason, repair, source="ARCHITECTOS_EXPLICIT_RULE"):
    return ConstraintResult(cid,kind.value,"PASS" if ok else "FAIL","BLOCKING" if kind==ConstraintKind.HARD else "QUALITY",spaces,evidence,source,repair,reason)


class ArchitecturalConstraintEngine:
    """Explainable constraints; every result includes evidence and repair class."""
    TRANSIT_FORBIDDEN={"BEDROOM","BATH","WC"}
    def evaluate(self, state: ArchitecturalDesignState):
        results=[]
        results += self._reachability(state)
        results += self._transit(state)
        results += self._openings(state)
        results += self._daylight(state)
        results += self._furniture(state)
        results += self._site(state)
        state.constraint_results=results
        state.unresolved_constraints=[x.id for x in results if x.status=="FAIL"]
        return results

    def hard_pass(self,state): return not any(r.kind=="HARD" and r.status=="FAIL" for r in self.evaluate(state))

    def _reachable(self,g,start):
        seen={start}; q=deque([start])
        while q:
            n=q.popleft()
            for nxt in g.get(n,[]):
                if nxt not in seen: seen.add(nxt); q.append(nxt)
        return seen

    def _reachability(self,s):
        g={x:[] for x in s.spaces}|{"SITE_ENTRY":[]}
        for a,b in s.circulation_graph: g.setdefault(a,[]).append(b); g.setdefault(b,[]).append(a)
        reached=self._reachable(g,"SITE_ENTRY")
        required=[x for x in s.spaces]
        missing=[x for x in required if x not in reached]
        return [_r("H_REQUIRED_REACHABLE",ConstraintKind.HARD,not missing,missing,[],"همه فضاهای الزامی از ورودی سایت قابل دسترس‌اند" if not missing else "فضاهای غیرقابل دسترس: "+",".join(missing),"RegenerateAccessTopology")]

    def _transit(self,s):
        g={x:[] for x in s.spaces}|{"SITE_ENTRY":[]}
        for a,b in s.circulation_graph:g.setdefault(a,[]).append(b);g.setdefault(b,[]).append(a)
        bad=[]
        for sid,sp in s.spaces.items():
            if sp.role in self.TRANSIT_FORBIDDEN and len(g.get(sid,[]))>1: bad.append(sid)
        private_nodes=[x for x,v in s.spaces.items() if v.zone=="PRIVATE"]
        has_private_transition=any(v.zone=="TRANSITION" and any(n in private_nodes for n in g.get(k,[])) for k,v in s.spaces.items())
        return [_r("H_NO_ROOM_THROUGH_ROOM",ConstraintKind.HARD,not bad,bad,[s.spaces[x].rect.to_list() for x in bad],"اتاق خواب/سرویس مسیر عبوری نیست","RegeneratePrivateTopology"),
                _r("H_PRIVATE_ZONE_ENTRANCE",ConstraintKind.HARD,has_private_transition,private_nodes,[],"ورودی مستقل حوزه خصوصی وجود دارد","CreatePrivateTransition")]

    def _openings(self,s):
        out=[]
        for o in s.opening_intents:
            if o.kind not in {"DOOR","OPEN"}: continue
            a,b=s.spaces.get(o.space_a),s.spaces.get(o.space_b_or_source)
            shared=a.rect.shared_boundary(b.rect) if a and b and a.rect and b.rect else None
            out.append(_r(f"H_OPENING_HOST_{o.id}",ConstraintKind.HARD,bool(shared and o.geometry),[o.space_a,o.space_b_or_source],[shared] if shared else [],"بازشو روی مرز مشترک واقعی قرار دارد","RegenerateOpeningHost"))
        return out

    def _daylight(self,s):
        out=[]
        wins={o.space_a:o for o in s.opening_intents if o.kind=="WINDOW"}
        for sid,sp in s.spaces.items():
            if not sp.habitable: continue
            src=s.setbacks_yards_courtyards.get(s.daylight_source_graph.get(sid,"")); win=wins.get(sid)
            shared=sp.rect.shared_boundary(src.rect) if src and sp.rect else None
            ok=bool(src and src.legal and src.open_to_sky and win and shared and win.geometry and win.space_b_or_source==src.id)
            out.append(_r(f"H_DAYLIGHT_SOURCE_{sid}",ConstraintKind.HARD,ok,[sid],[sp.rect.to_list(),src.rect.to_list()] if src else [sp.rect.to_list()],"پنجره مستقیماً روی مرز منبع نور قانونی و باز به آسمان است","ReallocateDaylightSource"))
        return out

    def _furniture(self,s):
        out=[]
        by_space={x:[] for x in s.spaces}
        for f in s.furniture_use_zones: by_space.setdefault(f.space_id,[]).append(f)
        for sid,sp in s.spaces.items():
            zones=by_space.get(sid,[]); inside=bool(zones) and all(sp.rect.contains(f.clearance_rect) for f in zones) if sp.furniture_ids else True
            collisions=any(a.clearance_rect.intersects(b.clearance_rect) for i,a in enumerate(zones) for b in zones[i+1:])
            ok=inside and not collisions
            out.append(_r(f"H_FURNITURE_USE_{sid}",ConstraintKind.HARD,ok,[sid],[f.clearance_rect.to_list() for f in zones],"چیدمان و فضای استفاده داخل اتاق و بدون برخورد است","ResizeOrRegenerateRoom"))
        return out

    def _site(self,s):
        seq=s.rules.get("arrival_sequence",[]); expected=["STREET","PED_GATE","WALK","PORCH_PLATFORM","STEPS_RAMP","CANOPY","ENTRY"]
        ok=seq==expected and .36<=s.level_datums.get("FFL",-1)<=.40 and abs(s.rules.get("canopy_depth_m",0)-1.2)<=.1
        veh=s.rules.get("vehicle_sequence",[])==["STREET","VEHICLE_GATE","DRIVEWAY","MANEUVER","PARKING"]
        return [_r("P_ARRIVAL_SEQUENCE",ConstraintKind.PROJECT,ok,[],[],"توالی ورود، تراز و سایبان پیش از ترسیم حل شده‌اند","RegenerateArrivalSequence","USER_PROJECT_RULE"),
                _r("H_VEHICLE_SEQUENCE",ConstraintKind.HARD,veh,[],[],"مسیر خودرو تا مانور و پارک پیوسته است","RegenerateParkingAccess")]
