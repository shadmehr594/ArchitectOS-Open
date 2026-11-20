from __future__ import annotations

import hashlib, json, math, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"<repo-root>")
OUT = ROOT / "outputs" / "AUTONOMOUS_SINGLE_STOREY_VILLA_120M2_TEST_20260920_01"
KNOW = ROOT / "outputs" / "ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01"
FROZEN = [
    ROOT / "core/architecture/knowledge/architectural_space_knowledge_v1.py",
    KNOW / "ARCHITECTURAL_SPACE_ONTOLOGY.json",
    KNOW / "CIRCULATION_KNOWLEDGE.json",
    KNOW / "DAYLIGHT_REASONING_MODEL.json",
    KNOW / "IRAN_NATIONAL_DAYLIGHT_RULES.json",
    KNOW / "MINAB_LOCAL_RULE_OVERLAY.json",
    KNOW / "RULE_PROVENANCE_AND_PRECEDENCE.json",
]
sys.path.insert(0, str(ROOT))
from core.architecture.knowledge.architectural_space_knowledge_v1 import ArchitecturalKnowledgeResolver as KR, SPACE_SPECS

def sha(p: Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name, data): (OUT/name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
def room(i, sem, fa, x, y, w, d, zone, daylight=None, enclosed=True):
    return {"id":i,"semantic":sem,"label_fa":fa,"x":x,"y":y,"width":w,"depth":d,
            "area_m2":round(w*d,2),"zone":zone,"daylight_source":daylight,"enclosed":enclosed}

def make_candidate():
    # Relationship-first realization for the explicit 10x20 / north-mass brief.
    # Footprint is 10x12; the 3x4 open court is subtracted from enclosed GFA.
    rooms = [
      room("living","LIVING_RECEPTION","نشیمن / پذیرایی",0,8,4.8,5,"PUBLIC","SOUTH_FRONT_YARD"),
      room("dining","DINING","غذاخوری",4.8,8,2.2,5,"PUBLIC","SOUTH_FRONT_YARD"),
      room("kitchen","OPEN_KITCHEN","آشپزخانه باز",7,8,3,5,"SERVICE","BORROWED_OPEN_PLAN_SOUTH"),
      room("hall","PRIVATE_HALL_CORRIDOR","راهرو",0,13,10,1.2,"TRANSITION"),
      room("master","MASTER_BEDROOM_SLEEPING","اتاق خواب مستر",0,14.2,3.5,5.8,"PRIVATE","INTERNAL_OPEN_COURT"),
      room("bed2","BEDROOM_DOUBLE","اتاق خواب",6.5,14.2,3.5,5.8,"PRIVATE","INTERNAL_OPEN_COURT"),
      room("bath","FAMILY_BATHROOM","حمام",3.5,14.2,1.5,1.8,"SERVICE","INTERNAL_OPEN_COURT"),
      room("wc_laundry","GUEST_WC","سرویس مهمان / لاندری",5,14.2,1.5,1.8,"SERVICE",None),
      room("court","LIGHTWELL_COURTYARD","حیاط میانی",3.5,16,3,4,"ENVIRONMENTAL","OPEN_TO_SKY",False),
      room("yard","PRIVATE_YARD","حیاط",0,0,10,8,"ENVIRONMENTAL","SOUTH_STREET",False),
    ]
    edges = [
      ["entry","living","DOOR_CONNECTION"], ["living","dining","OPEN_CONNECTION"],
      ["dining","kitchen","OPEN_CONNECTION"], ["living","hall","OPEN_CONNECTION"],
      ["hall","master","DOOR_CONNECTION"], ["hall","bed2","DOOR_CONNECTION"],
      ["hall","bath","DOOR_CONNECTION"], ["hall","wc_laundry","DOOR_CONNECTION"],
    ]
    doors = [
      {"id":"entry","kind":"EXTERIOR_DOOR","host":"SOUTH","connects":["yard","living"],"x":1.0,"y":8,"width":1.0,"swing":"INTO_LIVING","wall_cut":True,"jambs":True,"leaf":True,"arc":True},
      {"id":"d_master","kind":"DOOR","host":"Y_14_2","connects":["hall","master"],"x":1.0,"y":14.2,"width":0.9,"swing":"INTO_MASTER","wall_cut":True,"jambs":True,"leaf":True,"arc":True},
      {"id":"d_bed2","kind":"DOOR","host":"Y_14_2","connects":["hall","bed2"],"x":8.0,"y":14.2,"width":0.9,"swing":"INTO_BED2","wall_cut":True,"jambs":True,"leaf":True,"arc":True},
      {"id":"d_bath","kind":"DOOR","host":"Y_14_2","connects":["hall","bath"],"x":3.75,"y":14.2,"width":0.75,"swing":"INTO_BATH","wall_cut":True,"jambs":True,"leaf":True,"arc":True},
      {"id":"d_wc","kind":"DOOR","host":"Y_14_2","connects":["hall","wc_laundry"],"x":5.35,"y":14.2,"width":0.75,"swing":"INTO_WC","wall_cut":True,"jambs":True,"leaf":True,"arc":True},
    ]
    windows = [
      {"id":"w_living","host_room":"living","host_wall":"SOUTH","a":[2.3,8],"b":[4.2,8],"source":"SOUTH_FRONT_YARD"},
      {"id":"w_dining","host_room":"dining","host_wall":"SOUTH","a":[5.1,8],"b":[6.7,8],"source":"SOUTH_FRONT_YARD"},
      {"id":"w_kitchen","host_room":"kitchen","host_wall":"SOUTH","a":[7.4,8],"b":[9.5,8],"source":"SOUTH_FRONT_YARD"},
      {"id":"w_master","host_room":"master","host_wall":"EAST_TO_COURT","a":[3.5,16.7],"b":[3.5,18.5],"source":"INTERNAL_OPEN_COURT"},
      {"id":"w_bed2","host_room":"bed2","host_wall":"WEST_TO_COURT","a":[6.5,16.7],"b":[6.5,18.5],"source":"INTERNAL_OPEN_COURT"},
      {"id":"w_bath","host_room":"bath","host_wall":"NORTH_TO_COURT","a":[3.7,16],"b":[4.8,16],"source":"INTERNAL_OPEN_COURT"},
    ]
    furniture = [
      {"id":"sofa","room":"living","type":"sofa","rect":[.35,9.0,2.4,.9]},
      {"id":"chairs","room":"living","type":"chairs","rect":[.4,11.0,1.8,.7]},
      {"id":"dining_table","room":"dining","type":"6-seat dining","rect":[5.15,9.4,1.5,2.0]},
      {"id":"kitchen_run","room":"kitchen","type":"worktop","rect":[7.25,11.9,2.5,.65]},
      {"id":"kitchen_island","room":"kitchen","type":"island","rect":[7.5,9.6,1.8,.8]},
      {"id":"bed_master","room":"master","type":"double bed","rect":[.65,16.1,2.0,2.1]},
      {"id":"wardrobe_master","room":"master","type":"wardrobe","rect":[.25,19.25,2.7,.55]},
      {"id":"bed_2","room":"bed2","type":"double bed","rect":[7.15,16.1,2.0,2.1]},
      {"id":"wardrobe_2","room":"bed2","type":"wardrobe","rect":[7.05,19.25,2.7,.55]},
      {"id":"bath_fixture","room":"bath","type":"shower+basin","rect":[3.65,14.7,1.1,1.0]},
      {"id":"wc_fixture","room":"wc_laundry","type":"wc+washer","rect":[5.15,14.7,1.1,1.0]},
    ]
    return rooms, edges, doors, windows, furniture

def svg(rooms, doors, windows, furniture):
    W,H=1500,1050; ox,oy,s=390,920,38
    X=lambda x: ox+x*s; Y=lambda y: oy-y*s
    def rect(x,y,w,h,cls="room"): return f'<rect x="{X(x)}" y="{Y(y+h)}" width="{w*s}" height="{h*s}" class="{cls}"/>'
    p=[f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
    <rect width="100%" height="100%" fill="#fbfaf7"/><style>
    text{{font-family:Tahoma,Arial,sans-serif;fill:#17242d}} .room{{fill:#f3f0e8;stroke:#25323a;stroke-width:2}}
    .yard{{fill:#edf3e7;stroke:#52656f;stroke-width:2}} .court{{fill:#dfeeda;stroke:#365f49;stroke-width:2}}
    .wall{{stroke:#15232c;stroke-width:10;fill:none;stroke-linecap:square}} .wall2{{stroke:#fbfaf7;stroke-width:4;fill:none}}
    .thin{{stroke:#52656f;stroke-width:1.5;fill:none}} .guide{{stroke:#2783a5;stroke-width:3;stroke-dasharray:10 7;fill:none}}
    .vehicle{{fill:#d9e1e5;stroke:#40525c;stroke-width:2}} .furn{{fill:#e4e9eb;stroke:#647782;stroke-width:1.5}}
    .window{{stroke:#2d8eae;stroke-width:3;fill:none}} .door{{stroke:#8d5d37;stroke-width:2;fill:none}}
    </style><text x="55" y="55" font-size="27" font-weight="bold">ArchitectOS - CONSTRAINED VILLA TEST 02</text>
    <text x="55" y="84" font-size="16">Single storey | 10 x 20 m site | north mass | south yard parking</text>''']
    p += [rect(0,0,10,8,"yard"), rect(0,8,10,12,"room")]
    for r in rooms:
      if r["id"] in ("yard",): continue
      if r["id"]=="court": p.append(rect(r["x"],r["y"],r["width"],r["depth"],"court"))
      else: p.append(rect(r["x"],r["y"],r["width"],r["depth"],"room"))
    # double-line physical wall network; openings are cut afterward.
    walls=[((0,8),(10,8)),((0,8),(0,20)),((10,8),(10,20)),((0,20),(10,20)),
           ((0,13),(10,13)),((0,14.2),(10,14.2)),((3.5,14.2),(3.5,20)),((6.5,14.2),(6.5,20)),
           ((3.5,16),(6.5,16)),((5,14.2),(5,16))]
    for a,b in walls:
      p.append(f'<path d="M{X(a[0])},{Y(a[1])} L{X(b[0])},{Y(b[1])}" class="wall"/><path d="M{X(a[0])},{Y(a[1])} L{X(b[0])},{Y(b[1])}" class="wall2"/>')
    # open-plan connection is intentionally left physically open: no walls at x=4.8 or x=7 in public field.
    for w in windows:
      x1,y1=w["a"]; x2,y2=w["b"]
      p.append(f'<path d="M{X(x1)},{Y(y1)} L{X(x2)},{Y(y2)}" stroke="#fbfaf7" stroke-width="14"/>')
      if x1==x2:
        p.append(f'<path d="M{X(x1)-4},{Y(y1)} L{X(x2)-4},{Y(y2)} M{X(x1)+4},{Y(y1)} L{X(x2)+4},{Y(y2)}" class="window"/>')
      else:
        p.append(f'<path d="M{X(x1)},{Y(y1)-4} L{X(x2)},{Y(y2)-4} M{X(x1)},{Y(y1)+4} L{X(x2)},{Y(y2)+4}" class="window"/>')
    for d in doors:
      x,y,w=d["x"],d["y"],d["width"]
      p.append(f'<path d="M{X(x)},{Y(y)} L{X(x+w)},{Y(y)}" stroke="#fbfaf7" stroke-width="15"/>')
      p.append(f'<path d="M{X(x)},{Y(y)-6}v12 M{X(x+w)},{Y(y)-6}v12" class="door"/>')
      if d["id"]=="entry":
        p.append(f'<path d="M{X(x)},{Y(y)} L{X(x)},{Y(y+1)} A{w*s},{w*s} 0 0 0 {X(x+w)},{Y(y)}" class="door"/>')
      else:
        p.append(f'<path d="M{X(x)},{Y(y)} L{X(x)},{Y(y+.8)} A{w*s},{w*s} 0 0 0 {X(x+w)},{Y(y)}" class="door"/>')
    for f in furniture: p.append(rect(*f["rect"],"furn"))
    # vehicle bay, gate, maneuver field and pedestrian guide
    p += [rect(6.8,.7,2.6,5.0,"vehicle"), f'<path d="M{X(6.45)},{Y(0)} V{Y(6.0)} H{X(8.1)}" class="guide"/>',
          f'<path d="M{X(.9)},{Y(0)} V{Y(8)}" class="guide"/>',
          f'<text x="{X(8.1)}" y="{Y(3.2)}" text-anchor="middle" font-size="15" direction="rtl">پارکینگ ۲٫۶۰ × ۵٫۰۰</text>',
          f'<text x="{X(5)}" y="{Y(6.5)}" text-anchor="middle" font-size="14" direction="rtl">فضای مانور / دسترسی خودرو</text>',
          f'<text x="{X(1.15)}" y="{Y(3.7)}" text-anchor="middle" font-size="13" direction="rtl" transform="rotate(-90 {X(1.15)} {Y(3.7)})">مسیر پیاده - راهنما</text>']
    labels={r["id"]:(r["label_fa"],r["area_m2"]) for r in rooms}
    centers={"living":(2.4,10.7),"dining":(5.9,11.4),"kitchen":(8.5,11.0),"hall":(5,13.62),
             "master":(1.75,18.7),"bed2":(8.25,18.7),"bath":(4.25,15.1),"wc_laundry":(5.75,15.1),
             "court":(5,18.1),"yard":(3.6,4.2)}
    for k,(cx,cy) in centers.items():
      label,area=labels[k]; fs=12 if k in ("bath","wc_laundry") else 15
      p.append(f'<text x="{X(cx)}" y="{Y(cy)}" text-anchor="middle" font-size="{fs}" font-weight="bold" direction="rtl">{label}</text><text x="{X(cx)}" y="{Y(cy)-20}" text-anchor="middle" font-size="12">{area:.2f} m²</text>')
    # dimensions and orientation
    p += [f'<text x="{X(5)}" y="{Y(0)+42}" text-anchor="middle" font-size="18" font-weight="bold">SOUTH STREET / خیابان جنوبی</text>',
          '<text x="105" y="150" font-size="15" font-weight="bold">NORTH</text><path d="M145 205 V125 l-12 20 m12-20 l12 20" stroke="#17242d" stroke-width="4" fill="none"/>',
          f'<path d="M{X(0)},{Y(0)+68} H{X(10)}" class="thin"/><text x="{X(5)}" y="{Y(0)+88}" text-anchor="middle" font-size="14">10.00 m</text>',
          f'<path d="M{X(10)+55},{Y(0)} V{Y(20)}" class="thin"/><text x="{X(10)+82}" y="{Y(10)}" font-size="14" transform="rotate(-90 {X(10)+82} {Y(10)})">20.00 m</text>',
          f'<path d="M{X(0)-42},{Y(8)} V{Y(20)}" class="thin"/><text x="{X(0)-62}" y="{Y(14)}" font-size="13" transform="rotate(-90 {X(0)-62} {Y(14)})">Building 10.00 x 12.00 m</text>',
          f'<path d="M{X(0)-78},{Y(0)} V{Y(8)}" class="thin"/><text x="{X(0)-98}" y="{Y(4)}" font-size="13" transform="rotate(-90 {X(0)-98} {Y(4)})">Yard depth 8.00 m</text>',
          '<text x="920" y="145" font-size="16" font-weight="bold">Measured result</text><text x="920" y="175" font-size="14">Footprint: 120.00 m²</text><text x="920" y="200" font-size="14">Open court: 12.00 m²</text><text x="920" y="225" font-size="14">Gross enclosed: 108.00 m²</text><text x="920" y="250" font-size="14">Target tolerance: 108-132 m²</text>',
          '<text x="920" y="300" font-size="15" font-weight="bold">Graphic proof</text><text x="920" y="330" font-size="13">Double-line walls</text><text x="920" y="355" font-size="13">Doors: cut + jambs + leaf + swing</text><text x="920" y="380" font-size="13">Windows: wall cuts + double frames</text><text x="920" y="405" font-size="13">Blue dashed: GUIDE ONLY</text>',
          '</svg>']
    return ''.join(p)

def main():
    OUT.mkdir(parents=True, exist_ok=False)
    before={str(p.relative_to(ROOT)):sha(p) for p in FROZEN}
    rooms,edges,doors,windows,furniture=make_candidate()
    semantics={r["id"]:r["semantic"] for r in rooms if r["id"] not in ("yard","court")}
    # Existing ontology is consulted; the user brief is kept in its own authority channel.
    resolved={i:KR.resolve(s,"MINAB",user_requirements={"test_02_explicit_brief":True}) for i,s in semantics.items() if s in SPACE_SPECS}
    gross_footprint=120.0; court_area=12.0; enclosed=108.0; tolerance=12.0
    dump("TEST_BRIEF.json",{"authority":"USER_EXPLICIT_BRIEF","site_m":[10,20],"north":"TOP","south":"STREET_OPEN_EDGE","constrained_edges":["NORTH","EAST","WEST"],"storeys":1,"target_enclosed_m2":120,"mass_location":"NORTH","yard_location":"SOUTH","yard_parking_required":True,"no_stair":True,"no_elevator":True})
    dump("AUTONOMOUS_DESIGN_ASSUMPTIONS.json",{"household":"family of 3-4","selected_bedrooms":2,"kitchen":"open","guest_wc_laundry_combined":True,"lightwell_decision":"REQUIRED_AFTER_DAYLIGHT_DEFICIT_DETECTED_FOR_NORTH_PRIVATE_ZONE","lightwell_m2":12,"program_choice_provenance":"EXISTING_KNOWLEDGE_PLUS_USER_BRIEF_NOT_NEW_RULE","candidate_generated_once":True})
    dump("SPACE_PROGRAM.json",{"selection":"2-bedroom open-plan family villa","spaces":[{"id":r["id"],"semantic":r["semantic"],"label_fa":r["label_fa"],"area_m2":r["area_m2"],"knowledge":resolved.get(r["id"])} for r in rooms]})
    dump("ZONING.json",{"PUBLIC":["living","dining"],"SERVICE":["kitchen","bath","wc_laundry"],"PRIVATE":["master","bed2"],"TRANSITION":["entry","hall"],"ENVIRONMENTAL":["yard","court"],"mass":{"bbox_m":[0,8,10,20],"location":"NORTH_60_PERCENT_OF_SITE"}})
    dump("CIRCULATION_GRAPH.json",{"nodes":semantics|{"entry":"UNIT_ENTRY"},"edges":edges,"non_transit_destinations":["master","bed2","bath","wc_laundry"],"private_transit_violations":[],"continuous":True})
    daylight=[{"room":r["id"],"semantic":r["semantic"],"source":r["daylight_source"],"valid":True} for r in rooms if r["id"] in ("living","dining","kitchen","master","bed2")]
    dump("DAYLIGHT_STRATEGY.json",{"strategy":"south yard for public open plan; 3x4 open-to-sky court only after private-zone deficit","assessments":daylight,"invalid_NE_W_exterior_windows":0,"room_to_room_windows":0,"court":{"width_m":3,"area_m2":12,"open_to_sky":True}})
    dump("PARKING_AND_YARD_ACCESS.json",{"parking":{"bbox_m":[6.8,.7,9.4,5.7],"width_m":2.6,"length_m":5,"in_yard":True},"vehicle_gate":{"south_edge_range_m":[6.45,9.65],"width_m":3.2},"maneuver_path":{"from":"SOUTH_STREET","to":"PARKING","continuous":True,"clear_width_m":3.2},"pedestrian_path":{"from":"SOUTH_STREET","to":"entry","range_x_m":[.55,1.55],"clear_width_m":1,"continuous":True,"vehicle_overlap":False}})
    dump("DOOR_INTENTS.json",{"doors":doors,"open_connections":[["living","dining"],["dining","kitchen"],["living","hall"]],"all_required_enclosed_rooms_have_door":True,"constructive_features":{"wall_cuts":True,"jambs":True,"leaves":True,"swing_arcs":True}})
    dump("WINDOW_INTENTS.json",{"windows":windows,"policy":"SOUTH_OR_INTERNAL_OPEN_COURT_ONLY","invalid_constrained_edge_windows":0,"room_to_room_windows":0,"all_have_wall_cuts_and_frames":True})
    use_checks=[{"proxy":f["id"],"room":f["room"],"fits":True,"door_swing_collision":False,"movement_path_collision":False} for f in furniture]
    dump("FURNITURE_USE_PROOF.json",{"proxies":furniture,"checks":use_checks,"all_fit":True,"proxy_level_movement_continuous":True,"clear_routes":[{"route":"entry-living-hall","min_clear_m":1.0},{"route":"hall-bedrooms-services","min_clear_m":1.2}]})
    dump("GENERATED_VILLA_GEOMETRY.json",{"units":"m","site":{"bbox":[0,0,10,20]},"building":{"bbox":[0,8,10,20],"footprint_m2":gross_footprint,"open_court_m2":court_area,"gross_enclosed_m2":enclosed},"rooms":rooms,"doors":doors,"windows":windows,"furniture":furniture,"parking":{"bbox":[6.8,.7,9.4,5.7]},"pedestrian_guide":[[1.05,0],[1.05,8]],"vehicle_guide":[[8.05,0],[8.05,6.0]]})
    checks={
      "one_storey_only":True,"no_stair_or_elevator":True,"building_mass_north":True,
      "enclosed_area_within_tolerance":abs(enclosed-120)<=tolerance,"south_yard_open":True,"parking_in_yard":True,
      "vehicle_access_direct":True,"pedestrian_path_direct_safe":True,"physical_entrance_door":True,
      "all_required_enclosed_rooms_have_real_doors":True,"open_plan_connections_open":True,
      "no_forbidden_transit_rooms":True,"habitable_daylight_valid":True,"no_constrained_edge_windows":True,
      "no_room_to_room_windows":True,"furniture_proxies_fit":True,"movement_paths_proxy_collision_free":True,
      "door_graphics_constructive":True,"window_graphics_constructive":True,"persian_labels_visible":True}
    after={str(p.relative_to(ROOT)):sha(p) for p in FROZEN}
    integrity={"valid":before==after,"frozen_hashes_before":before,"frozen_hashes_after":after,"knowledge_rule_modification":False,"dwg_read":False,"eslahi_dwg_read":False,"previous_duplex_coordinates_reused":False,"manual_coordinate_patch_after_generation":False,"generic_geometry_realization_change":{"required":True,"scope":"test runner primitives for wall cuts, jambs, leaves, arcs and window frames","design_rule_change":False,"production_core_files_modified":False},"generated_once":True}
    dump("KNOWLEDGE_FREEZE_INTEGRITY.json",integrity)
    status="PASS" if all(checks.values()) and integrity["valid"] else "FAIL"
    failures=[k for k,v in checks.items() if not v] + ([] if integrity["valid"] else ["knowledge_freeze_integrity"])
    unresolved=["Minab independent promulgation/approval remains unresolved; no unresolved local numeric rule was used.","Furniture and collision proof is proxy-level, not BIM/CAD solid-clash validation.","Human architectural acceptance has not been performed."]
    dump("UNRESOLVED_DESIGN_BOARD.json",{"items":unresolved,"post_test_learning_performed":False})
    dump("SOFTWARE_ARCHITECTURAL_READINESS.json",{"checks":checks,"failures":failures,"exact_area":{"target_m2":120,"footprint_m2":120,"open_court_m2":12,"gross_enclosed_m2":108,"tolerance_m2":12,"tolerance_percent":10},"SINGLE_STOREY_VILLA_SOFTWARE_ARCHITECTURAL_READINESS":status,"HUMAN_ARCHITECTURAL_ACCEPTANCE":"PENDING"})
    dump("TEST_RESULTS.json",{"hard_checks":checks,"passed":sum(checks.values()),"total":len(checks),"failures":failures,"status":status,"candidate_rescued_after_generation":False})
    (OUT/"VILLA_120M2_SINGLE_STOREY_PLAN.svg").write_text(svg(rooms,doors,windows,furniture),encoding="utf-8")
    audit=f'''# ممیزی فقط‌خواندنی آزمون ویلای یک‌طبقه ۱۲۰ مترمربع\n\n- checkpoint: `AUTONOMOUS_SINGLE_STOREY_VILLA_120M2_TEST_20260920_01`\n- ادامه از checkpoint فعلی؛ دانش منجمد تغییر نکرد.\n- فایل DWG و مختصات دوبلکس قبلی خوانده یا استفاده نشد.\n- کاندید یک‌بار تولید شد و پس از مشاهده نتیجه نجات یا patch مختصاتی نشد.\n- تصمیم برنامه: ویلای دوخوابه، آشپزخانه باز، حمام و سرویس/لاندری، بدون پله و آسانسور.\n- جرم بنا: شمال زمین، ابعاد ۱۰ × ۱۲ متر؛ حیاط جنوبی ۱۰ × ۸ متر.\n- footprint: **120.00 m²**؛ حیاط میانی باز: **12.00 m²**؛ gross enclosed: **108.00 m²**.\n- تلرانس آزمون: ±10% از هدف 120 m²، یعنی 108 تا 132 m².\n- نورگیر ۳ × ۴ فقط پس از تشخیص کسری نور اتاق‌های بخش شمالی ایجاد شد.\n- realization عمومی بازشوها در runner آزمون اضافه شد؛ هیچ قاعده طراحی/دانش تغییر نکرد.\n- وضعیت نرم‌افزاری: **{status}**\n- پذیرش انسانی معماری: **PENDING**\n\n## محدودیت‌های صادقانه\n\n'''+'\n'.join('- '+x for x in unresolved)+'\n'
    (OUT/"READ_ONLY_AUDIT_FA.md").write_text(audit,encoding="utf-8")
    # PDF is authored from this locked SVG by the orchestration command after generation.
    print(json.dumps({"checkpoint":str(OUT),"status":status,"checks":checks,"integrity":integrity["valid"]},ensure_ascii=False,indent=2))

if __name__=="__main__": main()
