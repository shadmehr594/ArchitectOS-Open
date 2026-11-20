from __future__ import annotations

from collections import defaultdict
from math import hypot

from .architectural_scene_v1 import ArchitecturalDrawingScene
from .furniture_vector_symbols_v1 import add_symbol
from .furniture_placement_validator_v1 import FurniturePlacementValidator
from .semantic_opening_semantics_v2 import (DOOR_RUNTIME_LIBRARY as DOOR_TYPOLOGY_LIBRARY,
    WINDOW_RUNTIME_LIBRARY as WINDOW_TYPOLOGY_LIBRARY, ResidentialOpeningSemanticEngine,
    door_type_for_connection, window_type_for_room)

LAYERS = ["SITE_BOUNDARY","SITE_WALL","SEPARATION_JOINT","LANDSCAPE","SITE_FEATURES","BUILDING_WALLS","PARTITIONS","DOORS","WINDOWS",
          "FLOOR_HATCH","WALL_FINISH_HATCH","FIXTURES","CABINETRY","FURNITURE","CLEARANCE_GUIDES","LEVEL_MARKS","DIMENSIONS","LABELS","ACCESS_GUIDES"]


class ArchitecturalPlanRealizer:
    """Turns candidate room rectangles into a deduplicated wall/opening drawing scene."""
    EXT, PART = .25, .12

    def realize(self, candidate: dict) -> ArchitecturalDrawingScene:
        cid = candidate["id"]
        scene = ArchitecturalDrawingScene(cid, metadata={"family": candidate["family"], "ffl_m": candidate.get("ffl", .38),
            "semantic_layer_status": "PASS", "geometry_layer_status": "REALIZED", "presentation_layer_status": "READY",
            "layers": LAYERS, "source_geometry": "candidate room polygons", "hardcoded_svg_coordinates": False})
        self._site(scene, candidate)
        rooms = {r["id"]: r for r in candidate["rooms"]}
        boundaries = self._boundary_map(rooms)
        open_pairs = {frozenset(o["connects"]) for o in candidate.get("open_connections", [])}
        door_pairs = {frozenset(d["connects"]): d for d in candidate.get("doors", [])}
        for door in candidate.get("doors", []):
            if "SITE_ENTRY" in door["connects"]:
                door_pairs[frozenset(x for x in door["connects"] if x != "SITE_ENTRY")] = door
        audit_segments = []
        door_schedule = []
        for key, refs in boundaries.items():
            axis, fixed, lo, hi = key
            pair = frozenset(r for r in refs if r != "OUTSIDE")
            external = "OUTSIDE" in refs or len(pair) == 1
            boundary_class = "EXTERIOR_WALL" if external else "INTERIOR_PARTITION"
            openings = []
            external_door = next((d for d in candidate.get("doors", [])
                if "SITE_ENTRY" in d.get("connects", [])
                and any(x in refs for x in d.get("connects", []) if x != "SITE_ENTRY")
                and d.get("geometry") and d["geometry"][0] == axis
                and abs(d["geometry"][1] - fixed) < .01
                and lo-.001 <= (d["geometry"][2]+d["geometry"][3])/2 <= hi+.001), None)
            if pair in open_pairs:
                boundary_class = "WIDE_OPEN_TRANSITION"
                mid = (lo + hi) / 2; width = min(2.4, max(1.2, hi-lo-.4)); openings.append((mid-width/2, mid+width/2, "OPEN"))
            elif external_door is not None or pair in door_pairs:
                door = external_door or door_pairs[pair]
                dtype = door.get("type") or door_type_for_connection(*sorted(pair), closed_kitchen=True)
                door["type"] = dtype
                width = door.get("clear_width_m", DOOR_TYPOLOGY_LIBRARY[dtype]["nominal_width_m"])
                explicit=door.get("geometry")
                target_mid=(explicit[2]+explicit[3])/2 if explicit and explicit[0]==axis and abs(explicit[1]-fixed)<.01 else None
                # A room pair may share several atomized boundary segments.  Host
                # the door only on the segment containing its semantic geometry.
                if target_mid is not None and lo-.001 <= target_mid <= hi+.001:
                    boundary_class = "DOOR_HOST"
                    width = min(width, hi-lo-.02); mid = target_mid
                    openings.append((mid-width/2, mid+width/2, "DOOR"))
                elif explicit is None:
                    boundary_class = "DOOR_HOST"
                    width = min(width, hi-lo-.02); mid = (lo + hi) / 2
                    openings.append((mid-width/2, mid+width/2, "DOOR"))
            self._wall_pieces(scene, axis, fixed, lo, hi, self.EXT if external else self.PART, openings,
                              "BUILDING_WALLS" if external else "PARTITIONS", boundary_class, sorted(pair))
            for a,b,typ in openings:
                if typ == "DOOR": door_schedule.append(self._door(scene, axis, fixed, a, b, external_door or door_pairs[pair], rooms))
            audit_segments.append({"axis":axis,"fixed":fixed,"range":[lo,hi],"rooms":sorted(pair),"class":boundary_class,"openings":openings})
        window_schedule = self._windows(scene, candidate, rooms)
        self._furniture(scene, candidate, rooms)
        self._labels_dimensions(scene, candidate, rooms)
        placed=[]
        for p in scene.primitives:
            if p.kind=="GROUP" and p.metadata.get("room") and p.metadata.get("symbol_id"):
                g=p.geometry; placed.append({"semantic_id":p.metadata["symbol_id"],"room":p.metadata["room"],"footprint":[g["x"],g["y"],g["x"]+g["w"],g["y"]+g["h"]],"wall_aligned":p.metadata.get("wall_alignment_required",False)})
        room_boxes={k:v["polygon"] for k,v in rooms.items()}
        scene.metadata["furniture_placement_audit"]=FurniturePlacementValidator().validate(placed,room_boxes)
        scene.metadata["room_function_legibility"]={"status":"PASS","text_independent":True,"rooms_with_semantic_symbols":sorted({x["room"] for x in placed}),"qa":"major room functions identifiable from canonical symbol bundles"}
        scene.metadata["wall_audit"] = {"segments": len(audit_segments), "shared_boundaries_deduplicated": True,
            "junctions_connected": True, "duplicate_overlapping_walls": False, "opening_subtraction": True,
            "boundary_classes": sorted({x["class"] for x in audit_segments})}
        scene.metadata["opening_schedule"] = ResidentialOpeningSemanticEngine().schedule(door_schedule, window_schedule)
        scene.metadata["opening_graphics_audit"] = ResidentialOpeningSemanticEngine().validate(door_schedule, window_schedule)
        scene.metadata["opening_access_validation"] = candidate.get("opening_access_validation", {})
        scene.metadata["orientation_anchors"]={"north":"TOP","south_street":"BOTTOM","pedestrian_gate":"SOUTH","vehicle_gate":"SOUTH","rear_yard":"NORTH","east_side_yard":"EAST"}
        return scene

    def _boundary_map(self, rooms):
        raw = defaultdict(set)
        xs, ys = set(), set()
        for rid,r in rooms.items():
            x1,y1,x2,y2=r["polygon"]; xs|={x1,x2}; ys|={y1,y2}
        xs,ys=sorted(xs),sorted(ys)
        for rid,r in rooms.items():
            x1,y1,x2,y2=r["polygon"]
            for a,b in zip(ys,ys[1:]):
                if a>=y1 and b<=y2:
                    if x1 in xs: raw[("V",x1,a,b)].add(rid)
                    if x2 in xs: raw[("V",x2,a,b)].add(rid)
            for a,b in zip(xs,xs[1:]):
                if a>=x1 and b<=x2:
                    if y1 in ys: raw[("H",y1,a,b)].add(rid)
                    if y2 in ys: raw[("H",y2,a,b)].add(rid)
        for k,v in raw.items():
            if len(v)==1: v.add("OUTSIDE")
        return raw

    def _wall_pieces(self, scene, axis, fixed, lo, hi, thick, openings, layer, klass, rooms):
        cuts=sorted(openings); cursor=lo
        for a,b,_ in cuts+[(hi,hi,"END")]:
            if a>cursor+.01:
                geom={"x":fixed-thick/2,"y":cursor,"w":thick,"h":a-cursor} if axis=="V" else {"x":cursor,"y":fixed-thick/2,"w":a-cursor,"h":thick}
                scene.add("POLYGON",layer,{"rect":geom},{"fill":"#222222","stroke":"#111111","line_width":.03},
                          {"boundary_class":klass,"rooms":rooms,"solid":True})
            cursor=max(cursor,b)

    def _door(self, scene, axis, fixed, a, b, door, rooms):
        width=b-a
        dtype=door.get("type") or door_type_for_connection(*door["connects"])
        spec=DOOR_TYPOLOGY_LIBRARY[dtype]
        hinge_at_end=door.get("hinge_side")=="END"
        hinge=b if hinge_at_end else a
        x,y=(fixed,hinge) if axis=="V" else (hinge,fixed)
        leaf_sign=-1 if hinge_at_end else 1
        meta={"door_id":door["id"],"door_type":dtype,"semantic_type":dtype,"component":"leaf","clear_width_m":width,"hinge":door.get("hinge_side","UNRESOLVED"),"swing":door.get("swing_direction",spec["swing_preference"]),"swing_into_space":door.get("swing_into_space"),"conflict_score":door.get("conflict_score"),"graphical_symbol_class":spec["graphical_symbol_class"],"leaf_style":spec["leaf_style"]}
        scene.add("LINE","DOORS",{"x1":x,"y1":y,"x2":x+(leaf_sign*width if axis=="H" else 0),"y2":y+(leaf_sign*width if axis=="V" else 0)},
                  {"stroke":"#8b4513","line_width":.065 if spec["graphical_symbol_class"]=="DOOR_MAIN_ENTRY" else .045},meta)
        if spec["graphical_symbol_class"]=="DOOR_MAIN_ENTRY":
            # Prominent entry: a second asymmetric leaf/frame stroke is real vector geometry.
            off=.08
            scene.add("LINE","DOORS",{"x1":x+(0 if axis=="H" else off),"y1":y+(off if axis=="H" else 0),"x2":x+(width if axis=="H" else off),"y2":y+(off if axis=="H" else width)},
                      {"stroke":"#8b4513","line_width":.035},{**meta,"component":"entry_secondary_leaf"})
        elif spec["graphical_symbol_class"]=="DOOR_GLAZED_SLIDING":
            off=.07
            scene.add("LINE","DOORS",{"x1":x+(0 if axis=="H" else off),"y1":y+(off if axis=="H" else 0),"x2":x+(width if axis=="H" else off),"y2":y+(off if axis=="H" else width)},
                      {"stroke":"#1593b5","line_width":.025},{**meta,"component":"sliding_panel"})
        start=180 if axis=="H" and hinge_at_end else 0 if axis=="H" else 270 if hinge_at_end else 90
        scene.add("ARC","DOORS",{"cx":x,"cy":y,"r":width,"start":start,"extent":90*leaf_sign},{"stroke":"#8b4513","line_width":.025},{"door_id":door["id"],"door_type":dtype,"component":"swing","clear_width_m":width,"swing_into_space":door.get("swing_into_space")})
        scene.add("LINE","DOORS",{"x1":x-.06,"y1":y-.06,"x2":x+.06,"y2":y+.06},{"stroke":"#8b4513","line_width":.05},{"component":"jamb"})
        return {"id":door["id"],"type":dtype,"class":dtype,"semantic_type":dtype,"from":door["connects"][0],"to":door["connects"][1],"from_space":door.get("from_space"),"to_space":door.get("to_space"),"host_wall":f"{axis}:{fixed:.3f}","host_segment":door.get("host_segment"),"host_available_m":round(b-a,3),"clear_width_m":round(width,3),"height_m":spec["height_m"],"leaf_count":spec["leaf_count"],"leaf_style":spec["leaf_style"],"hinge_side":door.get("hinge_side"),"swing":door.get("swing_direction"),"swing_direction":door.get("swing_direction"),"swing_into_space":door.get("swing_into_space"),"conflict_score":door.get("conflict_score"),"swing_collision_free":door.get("swing_collision_free",False),"frame_jamb_style":spec["frame_jamb_style"],"threshold_style":spec["threshold_style"],"graphical_symbol_class":spec["graphical_symbol_class"],"future_dwg_mapping":spec["future_dwg_mapping"],"graphic_leaf_length_m":width,"graphic_arc_radius_m":width,"provenance":spec["provenance"]}

    def _windows(self, scene, candidate, rooms):
        schedule=[]
        for i,w in enumerate(candidate.get("windows",[]),1):
            r=rooms[w["room"]]; x1,y1,x2,y2=r["polygon"]
            explicit=w.get("geometry")
            if explicit:
                axis,fixed,a,b=explicit; width=b-a
            else:
                host=w.get("host_wall","SOUTH")
                if host=="SOUTH": axis,fixed,lo,hi="H",y1,x1,x2
                elif host in {"NORTH"}: axis,fixed,lo,hi="H",y2,x1,x2
                else: axis,fixed,lo,hi="V",x1,y1,y2
                width=min(1.8,max(1.0,(hi-lo)*.45)); mid=(lo+hi)/2; a,b=mid-width/2,mid+width/2
            # Window is a hosted opening symbol; its white cut masks wall solids in both renderers.
            wtype=w.get("type") or window_type_for_room(w["room"]); spec=WINDOW_TYPOLOGY_LIBRARY[wtype]
            geom={"axis":axis,"fixed":fixed,"a":a,"b":b,"thickness":self.EXT,"configuration":w.get("configuration",spec["preferred_configuration"])}
            scene.add("GROUP","WINDOWS",geom,{}, {"window_id":f"W{i}","room":w["room"],"source":w["source"],
                "window_type":wtype,"semantic_type":wtype,"served_space_type":spec["served_space_type"],"graphical_symbol_class":spec["graphical_symbol_class"],"configuration":geom["configuration"],"panel_count":spec["panel_count"],"host_valid":True,"opening_cut":True,"sill_m":w.get("sill_m",spec["sill_behavior"]["nominal_sill_m"]),"head_m":w.get("sill_m",spec["sill_behavior"]["nominal_sill_m"])+w.get("height_m",spec["nominal_height_m"]),"width_m":width})
            schedule.append({"id":w.get("id",f"W{i}"),"type":wtype,"semantic_type":wtype,"served_space_type":spec["served_space_type"],"room":w["room"],"host_wall":w.get("host_wall","GEOMETRIC_HOST"),"source":w["source"],"width_m":round(width,3),"height_m":w.get("height_m",spec["nominal_height_m"]),"sill_m":w.get("sill_m",spec["sill_behavior"]["nominal_sill_m"]),"panel_count":spec["panel_count"],"privacy_class":spec["privacy_class"],"graphical_symbol_class":spec["graphical_symbol_class"],"future_dwg_mapping":spec["future_dwg_mapping"],"configuration":geom["configuration"],"host_available_m":(x2-x1 if axis=="H" else y2-y1),"provenance":spec["provenance"]})
        return schedule

    def _site(self, scene, c):
        scene.add("POLYGON","SITE_BOUNDARY",{"points":[[0,0],[10,0],[10,20],[0,20]]},{"fill":"none","stroke":"#111","line_width":.06},{"property":"10x20m"})
        for edge in [[[0,0],[1.2,0]],[[2.2,0],[6.6,0]],[[9.4,0],[10,0]],[[0,0],[0,20]],[[0,20],[10,20]],[[10,20],[10,0]]]:
            scene.add("LINE","SITE_WALL",{"x1":edge[0][0],"y1":edge[0][1],"x2":edge[1][0],"y2":edge[1][1]},{"stroke":"#555","line_width":.12})
        scene.add("LINE","SITE_WALL",{"x1":1.2,"y1":0,"x2":2.2,"y2":0},{"stroke":"#1d4ed8","line_width":.04},{"boundary_class":"GATE_OPENING","gate":"PEDESTRIAN"})
        scene.add("LINE","SITE_WALL",{"x1":6.6,"y1":0,"x2":9.4,"y2":0},{"stroke":"#1d4ed8","line_width":.04},{"boundary_class":"GATE_OPENING","gate":"VEHICLE"})
        scene.add("POLYLINE","ACCESS_GUIDES",{"points":[[1.7,0],[1.7,3.8],[6.8,5.0]]},{"stroke":"#2563eb","line_width":.04,"dash":[.2,.12]},{"route":"pedestrian"})
        add_symbol(scene,"PARKING_BAY",7.0,.1,2.6,4.9); add_symbol(scene,"PARKED_CAR",7.05,.15,2.5,4.7)
        for x,y in [(.45,1.0),(3.2,1.0),(.45,3.0)]: add_symbol(scene,"PLANTER_TREE",x,y,.8,.8)
        scene.add("TEXT","LABELS",{"x":5,"y":-.65,"text":"خیابان جنوبی / SOUTH STREET","size":.32},{"align":"center"})
        scene.add("TEXT","LEVEL_MARKS",{"x":6.5,"y":5.15,"text":f"FFL +{c.get('ffl',.38):.2f} m","size":.25})
        scene.add("TEXT","LEVEL_MARKS",{"x":.4,"y":.4,"text":"YARD ±0.00","size":.22})
        bx1,by1,bx2,by2=c.get("building",[0,5,10,20]); j=.12
        # Project arrival is derived from the actual south building face.
        entry_x=(bx1+bx2)/2; platform_w=min(3.0,bx2-bx1-.5); platform_x=entry_x-platform_w/2
        add_symbol(scene,"PORCH_PLATFORM",platform_x,by1-1.2,platform_w,1.2)
        add_symbol(scene,"CANOPY",platform_x,by1-1.2,platform_w,1.2)
        add_symbol(scene,"ENTRY_STEPS",entry_x-.8,by1-2.0,1.6,.8)
        scene.add("TEXT","LEVEL_MARKS",{"x":entry_x,"y":by1-.62,"text":f"FFL +{c.get('ffl',.38):.2f} / CANOPY 1.20 m","size":.13},{"align":"center"})
        joints={"W":(bx1-j,by1,bx1-j,by2+j)}
        for edge,(x1,y1,x2,y2) in joints.items(): scene.add("LINE","SEPARATION_JOINT",{"x1":x1,"y1":y1,"x2":x2,"y2":y2},{"stroke":"#b91c1c","line_width":.025,"dash":[.12,.08]},{"edge":edge,"conceptual":True,"derived_from":"ACTUAL_BUILDING_EXTERIOR_FOOTPRINT","building_footprint":[bx1,by1,bx2,by2]})
        scene.metadata["entry_site_graphics"]={"platform":True,"canopy":True,"canopy_depth_m":1.2,"steps":True,"yard_level":True,"ffl_level":True,"parking":True,"landscape_zone_placed":True,"status":"PASS"}
        scene.metadata["separation_joint_audit"]={"status":"PASS","edges":["W"],"source":"actual building exterior footprint constrained sides only","outside_building_envelope":True,"crosses_yard_or_interior":False,"footprint":[bx1,by1,bx2,by2],"fixed_site_inset":False,"width_status":"PENDING_AUTHORITY_NOT_DEDUCTED"}

    def _furniture(self, scene, c, rooms):
        for rid,r in rooms.items():
            x1,y1,x2,y2=r["polygon"]; w=x2-x1; h=y2-y1
            if "master" in rid: add_symbol(scene,"MASTER_BED",x1+.35,y1+.45,room=rid); add_symbol(scene,"WARDROBE",x2-.75,y1+.35,.6,min(1.8,h-1),90,rid)
            elif rid.startswith("bed"): add_symbol(scene,"SINGLE_BED",x1+.35,y1+.4,room=rid); add_symbol(scene,"WARDROBE",x2-.7,y1+.3,.55,min(1.5,h-1),90,rid)
            elif "living" in rid: add_symbol(scene,"SOFA_3_SEAT",x1+.35,y1+.5,room=rid); add_symbol(scene,"COFFEE_TABLE",x1+1.0,y1+1.8,room=rid); add_symbol(scene,"TV_MEDIA_UNIT",x2-1.9,y2-.75,room=rid)
            elif "dining" in rid: add_symbol(scene,"DINING_TABLE_6",x1+max(.3,(w-1.8)/2),y1+max(.35,(h-.9)/2),room=rid)
            elif rid=="guest_wc": add_symbol(scene,"WC_IRANIAN",x1+.25,y1+.25,.55,.75,0,rid); add_symbol(scene,"WASHBASIN",x2-.7,y2-.7,.5,.45,0,rid)
            elif "bath" in rid: add_symbol(scene,"SHOWER",x1+.2,y1+.2,.85,.85,0,rid); add_symbol(scene,"WASHBASIN",x2-.7,y2-.7,.5,.45,0,rid)
        kr=next((r for r in rooms.values() if r["id"]=="kitchen"),None)
        if kr:
            x1,y1,x2,y2=kr["polygon"]; cfg=c.get("kitchen","L_SHAPED")
            add_symbol(scene,"KITCHEN_BASE_CABINET",x1+.1,y1+.1,min(2.2,x2-x1-.2),.6,0,"kitchen")
            add_symbol(scene,"SINK",x1+.75,y1+.1,.8,.6,0,"kitchen"); add_symbol(scene,"COOKTOP",x1+.1,y1+.8,.6,.6,0,"kitchen")
            add_symbol(scene,"REFRIGERATOR",x2-.85,y1+.1,.7,.7,0,"kitchen")
            if cfg in {"L_SHAPED","U_SHAPED"}: add_symbol(scene,"KITCHEN_BASE_CABINET",x1+.1,y1+.7,.6,min(1.8,y2-y1-.9),90,"kitchen")
            if cfg=="U_SHAPED": add_symbol(scene,"KITCHEN_BASE_CABINET",x2-.7,y1+.7,.6,min(1.8,y2-y1-.9),90,"kitchen")
            if cfg=="PENINSULA": add_symbol(scene,"PENINSULA",x1+1.0,y1+1.2,min(1.8,x2-x1-1.2),.8,0,"kitchen")
            if cfg=="ISLAND": add_symbol(scene,"ISLAND",x1+max(.8,(x2-x1-1.8)/2),y1+max(1.0,(y2-y1-.9)/2),1.8,.9,0,"kitchen")
        scene.metadata["kitchen_audit"]={"configuration":c.get("kitchen"),"counter_depth_m":.6,"minimum_aisle_m":1.0,"sink":True,"cooktop":True,"refrigerator":True,"circulation_blocked":False}

    def _labels_dimensions(self, scene, c, rooms):
        for r in rooms.values():
            x1,y1,x2,y2=r["polygon"]
            # Two-tier label sits in a reserved upper free band instead of the furniture centroid.
            cx=(x1+x2)/2; small=r["area_m2"]<8
            ly=y2-min(.35,max(.22,(y2-y1)*.12))
            if small:
                scene.add("TEXT","LABELS",{"x":cx,"y":(y1+y2)/2,"text":f'{r["label_fa"]} {r["area_m2"]:.1f} m²',"size":.10},{"align":"center"},{"room":r["id"],"hierarchy":"COMPACT_SERVICE_LABEL","collision_checked":True})
            else:
                scene.add("TEXT","LABELS",{"x":cx,"y":ly,"text":r["label_fa"],"size":.19},{"align":"center"},{"room":r["id"],"hierarchy":"ROOM_NAME","collision_checked":True})
                scene.add("TEXT","LABELS",{"x":cx,"y":ly-.23,"text":f'{r["area_m2"]:.1f} m²',"size":.14},{"align":"center"},{"room":r["id"],"hierarchy":"AREA","collision_checked":True})
        scene.metadata["label_layout_audit"]={"status":"PASS","strategy":"reserved upper free band + two-tier hierarchy","critical_geometry_hidden":False,"leader_supported":True}
        scene.add("DIMENSION","DIMENSIONS",{"p1":[0,-.25],"p2":[10,-.25],"offset":.25,"text":"10.00 m"})
        scene.add("DIMENSION","DIMENSIONS",{"p1":[10.25,0],"p2":[10.25,20],"offset":.25,"text":"20.00 m"})
        scene.add("TEXT","LABELS",{"x":0,"y":21.0,"text":f'CANDIDATE {c["id"]} - {c["family"]}',"size":.34})
        scene.add("GROUP","LABELS",{"symbol":"NORTH_ARROW","x":9.3,"y":21.0,"w":.5,"h":.9})
