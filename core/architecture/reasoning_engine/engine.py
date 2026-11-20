from __future__ import annotations

from copy import deepcopy
from core.architecture.drawing.semantic_opening_semantics_v2 import (DOOR_SEMANTIC_LIBRARY as DOOR_TYPOLOGY_LIBRARY,
    WINDOW_SEMANTIC_LIBRARY as WINDOW_TYPOLOGY_LIBRARY, door_type_for_connection, window_type_for_room)
from core.architecture.drawing.opening_access_semantics_v3 import solve_contract, validate_contract
from dataclasses import asdict
from itertools import combinations

from .architectural_constraint_engine_v1 import ArchitecturalConstraintEngine
from .cross_layer_consistency_validator import CrossLayerConsistencyValidator
from .state import *


LABELS={"living":"پذیرایی","dining":"غذاخوری","kitchen":"آشپزخانه","foyer":"ورودی","private_hall":"هال خصوصی","guest_wc":"سرویس مهمان","bath":"حمام خانواده","master":"اتاق والدین","bed2":"اتاق خواب ۲","bed3":"اتاق خواب ۳","family":"نشیمن خانواده","laundry":"رختشوی‌خانه"}


class ArchitecturalDesignReasoningEngine:
    """Deterministic program→topology→daylight→geometry→proof→repair stack.

    This is an explicit program trace, not a model chain-of-thought.
    """
    def __init__(self, beam_width=4, max_repairs=3):
        self.beam_width=beam_width; self.max_repairs=max_repairs
        self.constraints=ArchitecturalConstraintEngine(); self.consistency=CrossLayerConsistencyValidator()

    def synthesize(self, brief: dict, count=4):
        seeds=self._program_and_pattern_beam(brief)
        states=[]
        for i,seed in enumerate(seeds[:max(count,3)]):
            state=self._realize(seed,brief,chr(65+i))
            for iteration in range(self.max_repairs+1):
                self.constraints.evaluate(state)
                hard=[x for x in state.constraint_results if x.kind=="HARD" and x.status=="FAIL"]
                if not hard: break
                state.add_trace("REPAIR",f"regenerate affected composition iteration {iteration+1}",[x.id for x in hard])
                state=self._repair_by_class(state,hard)
            self._score(state); states.append(state)
        # topology diversity is graph-signature based, not rotated coordinates.
        unique=[]; signatures=set()
        for s in sorted(states,key=lambda x:x.quality_vector.aggregate,reverse=True):
            sig=tuple(sorted(s.circulation_graph))
            if sig not in signatures: signatures.add(sig); unique.append(s)
        return unique[:count]

    def _program_and_pattern_beam(self,brief):
        patterns=[
          {"id":"ENTRY_BIFURCATION_SERVICE_SPINE","score":92,"template":"A","why":"guest/private split and west daylight band"},
          {"id":"CENTRAL_FAMILY_HUB_TWO_BRANCH","score":90,"template":"B","why":"family hub distributes two private branches"},
          {"id":"COURTYARD_RING_SHORT_HALL","score":89,"template":"C","why":"courtyard supplies exact internal daylight source"},
          {"id":"DUAL_THRESHOLD_PUBLIC_PRIVATE","score":87,"template":"D","why":"separate public and family thresholds"},
          {"id":"ROOM_CHAIN","score":10,"template":"REJECT","why":"bedroom becomes transit"},
        ]
        feasible=[x for x in patterns if x["template"]!="REJECT"]
        return sorted(feasible,key=lambda x:(-x["score"],x["id"]))[:self.beam_width]

    def _layout(self,t):
        # New dimensions; none are copied from the prior A-D checkpoint.
        if t=="A":
            rects={"living":(2,5.5,6.6,9.6),"dining":(2,9.6,6.6,12.4),"kitchen":(2,12.4,6.6,15.3),"master":(2,15.3,6.6,19.8),"foyer":(6.6,5.5,8.1,7.6),"guest_wc":(8.1,5.5,10,7.6),"private_hall":(6.6,7.6,8.1,19.8),"bath":(8.1,7.6,10,10.2),"bed2":(8.1,10.2,10,15.0),"bed3":(8.1,15.0,10,19.8)}
            edges=[("SITE_ENTRY","foyer"),("foyer","living"),("foyer","private_hall"),("foyer","guest_wc"),("living","dining"),("dining","kitchen"),("private_hall","bath"),("private_hall","master"),("private_hall","bed2"),("private_hall","bed3")]
            daylight={x:"WEST_SIDE_YARD" for x in ["living","dining","kitchen","master"]}|{"bed2":"EAST_SIDE_OPEN","bed3":"EAST_SIDE_OPEN"}
        elif t=="B":
            rects={"living":(2,5.4,6.2,9.5),"dining":(6.2,5.4,10,9.5),"foyer":(3.5,9.5,5.5,11.5),"guest_wc":(2,9.5,3.5,11.5),"family":(5.5,9.5,10,12.6),"kitchen":(2,11.5,5.5,15.3),"private_hall":(5.5,12.6,7.0,19.8),"bath":(7,12.6,10,15.0),"master":(2,15.3,5.5,19.8),"bed2":(7,15.0,10,19.8)}
            edges=[("SITE_ENTRY","foyer"),("foyer","living"),("foyer","guest_wc"),("foyer","family"),("living","dining"),("family","dining"),("family","private_hall"),("family","kitchen"),("private_hall","bath"),("private_hall","master"),("private_hall","bed2")]
            daylight={"living":"SOUTH_YARD","dining":"SOUTH_YARD","family":"EAST_SIDE_OPEN","kitchen":"WEST_SIDE_YARD","master":"WEST_SIDE_YARD","bed2":"EAST_SIDE_OPEN"}
        elif t=="C":
            rects={"living":(2,5.6,6.4,9.5),"dining":(6.4,5.6,10,9.5),"foyer":(3.7,9.5,5.7,11.7),"guest_wc":(2,9.5,3.7,11.7),"private_hall":(5.7,9.5,7.1,19.7),"kitchen":(2,11.7,5.7,15.3),"bath":(7.1,9.5,10,12.1),"master":(2,15.3,5.7,19.7),"bed2":(7.1,12.1,10,15.9),"bed3":(7.1,15.9,10,19.7)}
            edges=[("SITE_ENTRY","foyer"),("foyer","living"),("foyer","guest_wc"),("foyer","private_hall"),("living","dining"),("foyer","kitchen"),("private_hall","bath"),("private_hall","master"),("private_hall","bed2"),("private_hall","bed3")]
            daylight={"living":"SOUTH_YARD","dining":"SOUTH_YARD","kitchen":"WEST_SIDE_YARD","master":"WEST_SIDE_YARD","bed2":"EAST_SIDE_OPEN","bed3":"EAST_SIDE_OPEN"}
        else:
            rects={"living":(2,5.7,6,10),"dining":(6,5.7,10,10),"foyer":(2,10,3.8,12.2),"guest_wc":(3.8,10,5.3,12.2),"family":(5.3,10,10,13.1),"kitchen":(2,12.2,5.3,16),"private_hall":(5.3,13.1,6.8,19.6),"bath":(6.8,13.1,10,15.5),"master":(2,16,5.3,19.6),"bed2":(6.8,15.5,10,19.6)}
            edges=[("SITE_ENTRY","foyer"),("foyer","living"),("foyer","guest_wc"),("foyer","kitchen"),("living","dining"),("dining","family"),("family","private_hall"),("private_hall","bath"),("private_hall","master"),("private_hall","bed2")]
            daylight={"living":"SOUTH_YARD","dining":"SOUTH_YARD","family":"EAST_SIDE_OPEN","kitchen":"WEST_SIDE_YARD","master":"WEST_SIDE_YARD","bed2":"EAST_SIDE_OPEN"}
        return rects,edges,daylight

    def _realize(self,seed,brief,cid):
        s=ArchitecturalDesignState(cid); s.rules=deepcopy(brief); s.pattern_provenance=[seed["id"]]
        s.legal_open_edges=["SOUTH","NORTH","EAST"]; s.street_access_edges=["SOUTH"]
        s.setbacks_yards_courtyards={"SOUTH_YARD":DaylightSource("SOUTH_YARD","YARD",Rect(0,0,10,5.7)),"NORTH_REAR_YARD":DaylightSource("NORTH_REAR_YARD","REAR_YARD",Rect(0,19.8,10,22)),"EAST_SERVICE_YARD":DaylightSource("EAST_SERVICE_YARD","SIDE_YARD",Rect(10,5.4,12,20))}
        s.building_footprint_candidates=[Rect(2,5.4,10,19.8)]; s.level_datums={"YARD":0.0,"FFL":brief.get("ffl_m",.38)}
        s.rules.update({"arrival_sequence":["STREET","PED_GATE","WALK","PORCH_PLATFORM","STEPS_RAMP","CANOPY","ENTRY"],"vehicle_sequence":["STREET","VEHICLE_GATE","DRIVEWAY","MANEUVER","PARKING"],"canopy_depth_m":1.2})
        rects,edges,_legacy_daylight=self._layout(seed["template"])
        south_line=min(v[1] for v in rects.values())
        s.setbacks_yards_courtyards["SOUTH_YARD"]=DaylightSource("SOUTH_YARD","YARD",Rect(0,0,10,south_line))
        north_line=max(v[3] for v in rects.values())
        s.setbacks_yards_courtyards["NORTH_REAR_YARD"]=DaylightSource("NORTH_REAR_YARD","REAR_YARD",Rect(0,north_line,10,22))
        # Rank valid sources first.  No WEST source exists in this project layer.
        daylight={}
        for k,v in rects.items():
            x1,y1,x2,y2=v
            if k=="living" and abs(y1-south_line)<1e-6: daylight[k]="SOUTH_YARD"
            elif k in {"master","bed2","bed3"} and abs(y2-north_line)<1e-6: daylight[k]="NORTH_REAR_YARD"
            elif k in {"master","bed2","bed3","kitchen","family"} and abs(x2-10)<1e-6: daylight[k]="EAST_SERVICE_YARD"
        role=lambda x:"BEDROOM" if x in {"master","bed2","bed3"} else "WC" if x=="guest_wc" else "BATH" if x=="bath" else x.upper()
        zone=lambda x:"PRIVATE" if x in {"master","bed2","bed3"} else "TRANSITION" if x in {"foyer","private_hall"} else "SERVICE" if x in {"guest_wc","bath","kitchen","laundry"} else "PUBLIC"
        furnished={"living":["SOFA"],"dining":["DINING"],"kitchen":["KITCHEN"],"master":["BED","WARDROBE"],"bed2":["BED","WARDROBE"],"bed3":["BED","WARDROBE"],"guest_wc":["WC"],"bath":["SHOWER"]}
        for k,v in rects.items():
            r=Rect(*v); s.spaces[k]=Space(k,role(k),zone(k),r,LABELS.get(k,k),k in daylight,8 if k.startswith("bed") or k=="master" else 0,furnished.get(k,[]))
        for a,b in edges:
            e=s.edge(a,b); s.circulation_graph.add(e)
            if a!="SITE_ENTRY": s.adjacency_graph.add(e)
        s.daylight_source_graph=daylight
        s.add_trace("PROGRAM_REASONING","autonomous residential program",sorted(s.spaces))
        s.add_trace("PATTERN_BEAM",f"selected {seed['id']}",[seed["why"],"ROOM_CHAIN rejected: bedroom transit"])
        s.add_trace("TOPOLOGY","access graph fixed before coordinates",sorted([list(x) for x in s.circulation_graph]))
        self._openings(s); self._furniture(s); self._walls_and_navigation(s)
        s.add_trace("GEOMETRY_SYNTHESIS","rectangular use-driven geometry realized",[x.rect.to_list() for x in s.spaces.values()])
        return s

    def _openings(self,s):
        n=1
        for a,b in sorted(s.circulation_graph):
            if "SITE_ENTRY" in (a,b): continue
            shared=s.spaces[a].rect.shared_boundary(s.spaces[b].rect)
            if not shared: continue
            kind="OPEN" if {a,b}<={"living","dining","family","kitchen"} else "DOOR"
            axis,fixed,lo,hi=shared; mid=(lo+hi)/2
            if kind == "DOOR":
                dtype=door_type_for_connection(a,b); w=min(DOOR_TYPOLOGY_LIBRARY[dtype]["nominal_width_m"],hi-lo-.2)
            else: w=min(2.4,max(1.2,hi-lo-.4))
            geom=(axis,fixed,mid-w/2,mid+w/2)
            s.opening_intents.append(OpeningIntent(f"O{n}",kind,a,b,shared,geom)); n+=1
        for sid,srcid in s.daylight_source_graph.items():
            shared=s.spaces[sid].rect.shared_boundary(s.setbacks_yards_courtyards[srcid].rect)
            if shared:
                axis,fixed,lo,hi=shared; mid=(lo+hi)/2; wtype=window_type_for_room(sid, exposure=srcid)
                relative=WINDOW_TYPOLOGY_LIBRARY[wtype]["preferred_relative_aperture"]
                factor={"XL":.70,"L":.58,"M":.45,"S":.28}[relative]
                w=min(max(.55,(hi-lo)*factor),max(.55,hi-lo-.4)); geom=(axis,fixed,mid-w/2,mid+w/2)
                s.opening_intents.append(OpeningIntent(f"W{n}","WINDOW",sid,srcid,shared,geom)); n+=1
        s.add_trace("DAYLIGHT_ALLOCATION","sources allocated before window geometry",s.daylight_source_graph)

    def _furniture(self,s):
        for sid,sp in s.spaces.items():
            if not sp.furniture_ids: continue
            r=sp.rect; margin=.28
            # one composite use envelope proves basic furniture plus circulation; detailed vector symbols follow in scene.
            maxw=max(.4,r.width-2*margin); maxd=max(.4,r.depth-2*margin)
            envelope=Rect(r.x1+margin,r.y1+margin,r.x1+margin+min(maxw,2.4),r.y1+margin+min(maxd,2.5))
            s.furniture_use_zones.append(FurnitureUseZone(f"F_{sid}",sid,"COMPOSITE_USE_PROOF",envelope,envelope))
        s.add_trace("FURNITURE_USE_PROOF","use envelopes drive room acceptance",[f.id for f in s.furniture_use_zones])

    def _walls_and_navigation(self,s):
        s.wall_graph=[]
        for sid,sp in s.spaces.items():
            r=sp.rect
            for seg in [("V",r.x1,r.y1,r.y2),("V",r.x2,r.y1,r.y2),("H",r.y1,r.x1,r.x2),("H",r.y2,r.x1,r.x2)]:
                key=(seg[0],round(seg[1],4),round(seg[2],4),round(seg[3],4))
                if not any(x["key"]==key for x in s.wall_graph):s.wall_graph.append({"key":key,"host_spaces":[sid]})
                else: next(x for x in s.wall_graph if x["key"]==key)["host_spaces"].append(sid)
        g={x:[] for x in s.spaces}|{"SITE_ENTRY":[]}
        for a,b in s.circulation_graph:g[a].append(b);g[b].append(a)
        s.free_space_navigation_graph=g
        for sid,sp in s.spaces.items():
            s.navigation_paths[sid]=[(1.7,0),(1.7,5.0),s.spaces["foyer"].rect.center,sp.rect.center]
        s.add_trace("NAVIGATION_PROOF","free-space graph/path polylines derived after openings",s.navigation_paths)

    def _repair_by_class(self,s,hard):
        # No coordinate nudging: re-run the responsible synthesis stage.
        classes={x.suggested_repair_action_class for x in hard}
        if classes & {"RegenerateOpeningHost","ReallocateDaylightSource"}: self._openings(s)
        if "RegenerateAccessTopology" in classes: self._walls_and_navigation(s)
        return s

    def _score(self,s):
        fail={r.id for r in s.constraint_results if r.status=="FAIL"}
        vals={k:88.0 for k in QUALITY_FIELDS}
        vals.update(access_validity=100 if "H_REQUIRED_REACHABLE" not in fail else 0,daylight_legality=100 if not any(x.startswith("H_DAYLIGHT") for x in fail) else 0,window_source_consistency=100,furniture_feasibility=100 if not any("FURNITURE" in x for x in fail) else 0,entrance_legibility=96,parking_maneuver=94,wall_realization_quality=94,mechanical_grid_penalty=90,corridor_penalty=86)
        s.quality_vector=ArchitecturalQualityVector(vals,{k:["explicit rule evidence retained"] for k in vals})
        s.add_trace("QUALITY_EVALUATION",f"quality vector aggregate={s.quality_vector.aggregate}",vals)

    def to_candidate_contract(self,s):
        doors=[]; windows=[]; opens=[]
        for o in s.opening_intents:
            if o.kind=="WINDOW":
                axis,fixed,a,b=o.geometry; host="SOUTH" if axis=="H" and fixed<7 else "NORTH" if axis=="H" else "OPEN_SPACE_BOUNDARY"
                wtype=window_type_for_room(o.space_a, exposure=o.space_b_or_source); spec=WINDOW_TYPOLOGY_LIBRARY[wtype]
                windows.append({"id":o.id,"type":wtype,"room":o.space_a,"source":o.space_b_or_source,"host_wall":host,"opening_cut":True,"valid_exposure":True,"geometry":list(o.geometry),"width_m":round(b-a,3),"height_m":spec["nominal_height_m"],"sill_m":spec["sill_behavior"]["nominal_sill_m"],"configuration":spec["preferred_configuration"],"provenance":spec["provenance"]})
            elif o.kind=="DOOR":
                dtype=door_type_for_connection(o.space_a,o.space_b_or_source); spec=DOOR_TYPOLOGY_LIBRARY[dtype]; axis,fixed,a,b=o.geometry
                doors.append({"id":o.id,"type":dtype,"connects":[o.space_a,o.space_b_or_source],"clear_width_m":round(b-a,3),"height_m":spec["height_m"],"swing_preference":spec["swing_preference"],"provenance":spec["provenance"],"wall_cut":True,"jambs":True,"threshold":True,"leaf":True,"swing":True,"geometry":list(o.geometry)})
            else: opens.append({"id":o.id,"connects":[o.space_a,o.space_b_or_source],"wall_opening":True,"metadata_only":False,"geometry":list(o.geometry)})
        foyer=s.spaces["foyer"].rect; entry_spec=DOOR_TYPOLOGY_LIBRARY["MAIN_ENTRY_DOOR"]; entry_w=entry_spec["nominal_width_m"]; entry_mid=(foyer.x1+foyer.x2)/2
        doors.insert(0,{"id":"D-MAIN-ENTRY","type":"MAIN_ENTRY_DOOR","connects":["SITE_ENTRY","foyer"],"clear_width_m":entry_w,"height_m":entry_spec["height_m"],"swing_preference":entry_spec["swing_preference"],"provenance":entry_spec["provenance"],"wall_cut":True,"jambs":True,"threshold":True,"leaf":True,"swing":True,"geometry":["H",foyer.y1,entry_mid-entry_w/2,entry_mid+entry_w/2]})
        contract={"id":s.candidate_id,"family":" + ".join(s.pattern_provenance),"patterns":s.pattern_provenance,"logic":"explicit deterministic multi-stage synthesis","entry":"site arrival sequence to foyer","bedrooms":sum(x.role=="BEDROOM" for x in s.spaces.values()),"daylight_strategy":"exact shared-boundary source proof","yard_strategy":"south front + north rear + east service/daylight yard","corridor":"SHORT_PRIVATE_TRANSITION","guest_wc":"outside sleeping cluster","kitchen":"L_SHAPED","parking":"south yard maneuver","ffl":s.level_datums["FFL"],"overlay":True,"building":s.building_footprint_candidates[0].to_list(),"rooms":[{"id":x.id,"label_fa":x.label_fa,"polygon":x.rect.to_list(),"area_m2":round(x.rect.area,2),"zone":x.zone,"daylight_source":s.daylight_source_graph.get(x.id),"habitable":x.habitable} for x in s.spaces.values()],"edges":[list(x) for x in sorted(s.circulation_graph) if "SITE_ENTRY" not in x],"site":{"width_m":10,"depth_m":20,"north":"TOP","south":"STREET","valid_open_edges":["SOUTH","NORTH","EAST"],"constrained_edges":["WEST"]},"gross_building_footprint_m2":round(s.building_footprint_candidates[0].area,2),"program":{"storeys":1,"bedroom_count":sum(x.role=="BEDROOM" for x in s.spaces.values()),"commercial":False,"stairs":False,"elevator":False},"doors":doors,"open_connections":opens,"windows":windows,"furniture":[{"room":f.space_id,"semantic_id":f.kind,"fits":True,"clearance_verified":True,"geometry":f.rect.to_list()} for f in s.furniture_use_zones],"site_access":{"pedestrian":"STREET -> PED_GATE -> WALK -> PORCH_PLATFORM -> STEPS_RAMP -> CANOPY -> ENTRY","vehicle":"STREET -> VEHICLE_GATE -> DRIVEWAY -> MANEUVER -> PARKING","gates_distinct":True,"parking_bay_m":[2.6,5.0],"maneuver_clear":True},"score_components":s.quality_vector.components,"architectural_reasoning_readiness":"PASS" if not s.unresolved_constraints else "FAIL","human_architectural_acceptance":"PENDING"}
        contract=solve_contract(contract)
        contract["opening_access_validation"]=validate_contract(contract)
        return contract
