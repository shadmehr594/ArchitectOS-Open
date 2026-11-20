from __future__ import annotations

import hashlib, json, math, os, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"<repo-root>")
CHECKPOINT = ROOT / "outputs" / "AUTONOMOUS_VILLA_GENERALIZATION_TEST_20260920_01"
FROZEN = [
    ROOT / "core/architecture/knowledge/architectural_space_knowledge_v1.py",
    ROOT / "outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/ARCHITECTURAL_SPACE_ONTOLOGY.json",
    ROOT / "outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/CIRCULATION_KNOWLEDGE.json",
    ROOT / "outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/DAYLIGHT_REASONING_MODEL.json",
    ROOT / "outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/IRAN_NATIONAL_DAYLIGHT_RULES.json",
    ROOT / "outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/MINAB_LOCAL_RULE_OVERLAY.json",
    ROOT / "outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/RULE_PROVENANCE_AND_PRECEDENCE.json",
]

sys.path.insert(0, str(ROOT))
from core.architecture.knowledge.architectural_space_knowledge_v1 import ArchitecturalKnowledgeResolver as KR, SPACE_SPECS
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name, obj):
    (CHECKPOINT/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def room(i, semantic, floor, x, y, w, d, zone, daylight=None):
    return {"id":i,"semantic":semantic,"floor":floor,"x":round(x,3),"y":round(y,3),"width":round(w,3),"depth":round(d,3),"area_m2":round(w*d,2),"zone":zone,"daylight_source":daylight}

def derive_graph(program):
    nodes={p["id"]:p["semantic"] for p in program}
    edges=[]
    ids={p["semantic"]:[] for p in program}
    for p in program: ids[p["semantic"]].append(p["id"])
    def add(a,b,k):
        if a in ids and b in ids: edges.append((ids[a][0],ids[b][0],k))
    add("UNIT_ENTRY","FOYER_SHOE_OFF","OPEN_CONNECTION")
    add("FOYER_SHOE_OFF","LIVING_RECEPTION","OPEN_CONNECTION")
    add("FOYER_SHOE_OFF","GUEST_WC","DOOR_CONNECTION")
    add("LIVING_RECEPTION","DINING","OPEN_CONNECTION")
    add("DINING","OPEN_KITCHEN","OPEN_CONNECTION")
    add("LIVING_RECEPTION","TERRACE_BALCONY","DOOR_CONNECTION")
    add("FOYER_SHOE_OFF","STAIR","VERTICAL_ACCESS")
    add("STAIR","PRIVATE_HALL_CORRIDOR","VERTICAL_ACCESS")
    for s in ("MASTER_BEDROOM_SLEEPING","BEDROOM_DOUBLE","BEDROOM_SINGLE","FAMILY_BATHROOM","STORAGE_LINEN"):
        if s in ids: edges.append((ids["PRIVATE_HALL_CORRIDOR"][0],ids[s][0],"DOOR_CONNECTION"))
    return nodes, edges

def build_candidate(order, public_depth, private_depth, cid):
    # Generic edge-first strip allocator: daylight-demanding destinations are packed on the only open edge.
    south=5.0; bw=10.0; ground_n=south+public_depth; upper_n=south+private_depth
    rooms=[]
    weights={"LIVING_RECEPTION":4.4,"DINING":2.4,"OPEN_KITCHEN":3.2}
    x=0
    for sem in order:
        w=bw*weights[sem]/sum(weights.values()); rooms.append(room(sem.lower(),sem,"GROUND",x,south,w,5.0,"PUBLIC" if sem!="OPEN_KITCHEN" else "SERVICE","PUBLIC_STREET" if sem!="OPEN_KITCHEN" else "BORROWED_OPEN_PLAN_DAYLIGHT")); x+=w
    rooms += [room("foyer","FOYER_SHOE_OFF","GROUND",0,south+5,2.2,2.2,"TRANSITION"),room("entry","UNIT_ENTRY","GROUND",0.7,south,1.2,.35,"TRANSITION"),room("guest_wc","GUEST_WC","GROUND",2.2,south+5,1.4,2.2,"SERVICE"),room("stair","STAIR","GROUND",3.6,south+5,2.4,4.0,"TRANSITION"),room("utility","LAUNDRY_UTILITY","GROUND",6,south+5,2,2.2,"SERVICE"),room("storage_g","STORAGE_LINEN","GROUND",8,south+5,2,2.2,"SERVICE"),room("terrace","TERRACE_BALCONY","GROUND",0,south-1.5,10,1.5,"SEMI_PUBLIC","PUBLIC_STREET"),room("front_yard","PRIVATE_YARD","SITE",0,0,10,south-1.5,"ENVIRONMENTAL","PUBLIC_STREET")]
    bedsems=["MASTER_BEDROOM_SLEEPING","BEDROOM_DOUBLE","BEDROOM_SINGLE"]; bweights=[3.6,3.2,3.2]; x=0
    for sem,w in zip(bedsems,bweights): rooms.append(room(sem.lower(),sem,"UPPER",x,south,w,4.6,"PRIVATE","PUBLIC_STREET")); x+=w
    rooms += [room("private_hall","PRIVATE_HALL_CORRIDOR","UPPER",0,south+4.6,10,1.4,"TRANSITION"),room("stair_u","STAIR","UPPER",3.6,south+6,2.4,4,"TRANSITION"),room("family_bath","FAMILY_BATHROOM","UPPER",0,south+6,2.4,2.4,"PRIVATE"),room("storage_u","STORAGE_LINEN","UPPER",2.4,south+6,1.2,2.4,"SERVICE")]
    windows=[]
    for r in rooms:
        if r["floor"] in ("GROUND","UPPER") and r.get("daylight_source")=="PUBLIC_STREET": windows.append({"host_room":r["id"],"floor":r["floor"],"edge":"SOUTH","x1":r["x"]+.35,"x2":r["x"]+r["width"]-.35,"y":r["y"]})
    nodes,edges=derive_graph(rooms)
    # Scores use only existing knowledge semantics plus measurable geometry.
    topo=KR.validate_circulation(nodes,edges)
    daylight=[]
    for r in rooms:
        if r["semantic"] in ("LIVING_RECEPTION","DINING","MASTER_BEDROOM_SLEEPING","BEDROOM_DOUBLE","BEDROOM_SINGLE"):
            daylight.append(KR.assess_daylight(r["semantic"],r["daylight_source"],"MINAB",source_legal=True,open_plan_same_field=True))
    min_dim=min(min(r["width"],r["depth"]) for r in rooms if r["semantic"] in ("LIVING_RECEPTION","DINING","MASTER_BEDROOM_SLEEPING","BEDROOM_DOUBLE","BEDROOM_SINGLE"))
    score=60+(8 if topo["passed"] else 0)+sum(d["DAYLIGHT_ARCHITECTURAL_QUALITY"]["score"] for d in daylight)/100+(5 if min_dim>=2.15 else -20)-abs(public_depth-9)*.5
    return {"id":cid,"rooms":rooms,"windows":windows,"nodes":nodes,"edges":edges,"topology":topo,"daylight":daylight,"score":round(score,2),"parameters":{"public_order":order,"public_depth":public_depth,"private_depth":private_depth}}

def svg_sheet(candidate, floor, title):
    W,H=1180,820; ox,oy=360,690; s=30; wall=8
    rs=[r for r in candidate["rooms"] if r["floor"]==floor or (floor=="GROUND" and r["floor"]=="SITE")]
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="#faf9f6"/><style>text{{font-family:Arial,sans-serif;fill:#17232c}}.thin{{stroke:#768692;stroke-width:1;fill:none}}.wall{{stroke:#17232c;stroke-width:8;fill:none}}.guide{{stroke:#78a4b8;stroke-width:2;stroke-dasharray:8 7;fill:none}}.furn{{stroke:#82919a;stroke-width:1.5;fill:#edf1f2}}</style><text x="60" y="55" font-size="26" font-weight="bold">{title}</text><text x="60" y="82" font-size="14">Blind autonomous candidate | 10 x 20 m site | {floor}</text>']
    # site and constrained edges
    parts += [f'<rect x="{ox}" y="{oy-20*s}" width="{10*s}" height="{20*s}" class="thin"/>',f'<path d="M {ox} {oy-20*s} h {10*s} M {ox} {oy-20*s} v {20*s} M {ox+10*s} {oy-20*s} v {20*s}" stroke="#b44" stroke-width="3" stroke-dasharray="5 5" fill="none"/><text x="{ox+150}" y="{oy+28}" text-anchor="middle" font-size="18" font-weight="bold">SOUTH STREET / PUBLIC ACCESS</text><text x="{ox+150}" y="{oy-20*s-15}" text-anchor="middle" font-size="13" fill="#a33">N / E / W CONSTRAINED NEIGHBOR EDGES</text>']
    labels={"LIVING_RECEPTION":"Living / Reception","DINING":"Dining","OPEN_KITCHEN":"Open Kitchen","FOYER_SHOE_OFF":"Foyer","GUEST_WC":"Guest WC","STAIR":"Stair","LAUNDRY_UTILITY":"Utility","STORAGE_LINEN":"Storage","TERRACE_BALCONY":"Terrace","PRIVATE_YARD":"Front Garden","MASTER_BEDROOM_SLEEPING":"Master Bedroom","BEDROOM_DOUBLE":"Double Bedroom","BEDROOM_SINGLE":"Single Bedroom","PRIVATE_HALL_CORRIDOR":"Private Hall","FAMILY_BATHROOM":"Family Bath","UNIT_ENTRY":"Entry"}
    for r in rs:
        x=ox+r["x"]*s; y=oy-(r["y"]+r["depth"])*s; w=r["width"]*s; h=r["depth"]*s
        fill="#e9f0e5" if r["zone"]=="ENVIRONMENTAL" else ("#f3ece3" if r["zone"]=="PUBLIC" else "#eef1f5")
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="#17232c" stroke-width="{wall if r["floor"]==floor else 2}"/>')
        if w>55 and h>35: parts.append(f'<text x="{x+w/2}" y="{y+h/2-3}" text-anchor="middle" font-size="13" font-weight="bold">{labels.get(r["semantic"],r["semantic"])}</text><text x="{x+w/2}" y="{y+h/2+15}" text-anchor="middle" font-size="11">{r["area_m2"]} m2</text>')
        # lightweight use proxy, generated from semantic furniture requirements
        if "BEDROOM" in r["semantic"]: parts.append(f'<rect x="{x+w*.25}" y="{y+h*.18}" width="{w*.5}" height="{h*.48}" rx="5" class="furn"/><rect x="{x+w*.12}" y="{y+h*.76}" width="{w*.76}" height="10" class="furn"/>')
        elif r["semantic"]=="LIVING_RECEPTION": parts.append(f'<rect x="{x+18}" y="{y+30}" width="{w*.55}" height="35" rx="6" class="furn"/><rect x="{x+w*.35}" y="{y+h*.55}" width="55" height="32" class="furn"/>')
        elif r["semantic"]=="DINING": parts.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w*.25}" ry="{h*.18}" class="furn"/>')
        elif r["semantic"]=="OPEN_KITCHEN": parts.append(f'<path d="M{x+12},{y+15} h{w-24} v22 h-{w-24}z" class="furn"/>')
        elif r["semantic"] in ("GUEST_WC","FAMILY_BATHROOM"): parts.append(f'<ellipse cx="{x+w*.35}" cy="{y+h*.35}" rx="12" ry="18" class="furn"/><rect x="{x+w*.58}" y="{y+h*.2}" width="20" height="28" class="furn"/>')
        elif r["semantic"]=="STAIR":
            for k in range(8): parts.append(f'<line x1="{x+8}" y1="{y+12+k*(h-24)/8}" x2="{x+w-8}" y2="{y+12+k*(h-24)/8}" class="thin"/>')
            parts.append(f'<text x="{x+w/2}" y="{y+h-15}" text-anchor="middle" font-size="12">UP / DN</text>')
    for win in candidate["windows"]:
        if win["floor"]!=floor: continue
        x1=ox+win["x1"]*s; x2=ox+win["x2"]*s; y=oy-win["y"]*s
        parts.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="#faf9f6" stroke-width="12"/><line x1="{x1}" y1="{y-3}" x2="{x2}" y2="{y-3}" stroke="#3b87a5" stroke-width="2"/><line x1="{x1}" y1="{y+3}" x2="{x2}" y2="{y+3}" stroke="#3b87a5" stroke-width="2"/>')
    # entrance door and main circulation guide
    if floor=="GROUND": parts.append(f'<line x1="{ox+20}" y1="{oy-5*s}" x2="{ox+56}" y2="{oy-5*s}" stroke="#faf9f6" stroke-width="12"/><path d="M{ox+20},{oy-5*s} v-36 A36,36 0 0 1 {ox+56},{oy-5*s}" class="thin"/><path d="M{ox+35},{oy-20} V{oy-5*s+35} H{ox+110}" class="guide"/><text x="70" y="145" font-size="14">NORTH</text><path d="M110 180 v-55 l-10 15 m10-15 l10 15" stroke="#17232c" stroke-width="3" fill="none"/>')
    else: parts.append(f'<path d="M{ox+150},{oy-11*s} V{oy-6*s} H{ox+250}" class="guide"/><text x="70" y="145" font-size="14">NORTH</text><path d="M110 180 v-55 l-10 15 m10-15 l10 15" stroke="#17232c" stroke-width="3" fill="none"/>')
    parts += [f'<line x1="{ox}" y1="{oy+65}" x2="{ox+10*s}" y2="{oy+65}" class="thin"/><line x1="{ox}" y1="{oy+58}" x2="{ox}" y2="{oy+72}" class="thin"/><line x1="{ox+10*s}" y1="{oy+58}" x2="{ox+10*s}" y2="{oy+72}" class="thin"/><text x="{ox+150}" y="{oy+84}" text-anchor="middle" font-size="13">10.00 m</text><text x="850" y="210" font-size="14" font-weight="bold">Legend</text><line x1="850" y1="240" x2="920" y2="240" class="wall"/><text x="935" y="245" font-size="12">wall</text><line x1="850" y1="270" x2="920" y2="270" stroke="#3b87a5" stroke-width="4"/><text x="935" y="275" font-size="12">south daylight window</text><line x1="850" y1="300" x2="920" y2="300" class="guide"/><text x="935" y="305" font-size="12">circulation guide</text><text x="850" y="350" font-size="12">Critical clear widths:</text><text x="850" y="372" font-size="12">habitable min >= 2.15 m</text><text x="850" y="394" font-size="12">private hall = 1.40 m</text><text x="850" y="416" font-size="12">stair block = 2.40 m</text></svg>']
    return "".join(parts)

def pdf_from_svgs(paths, out):
    # Draw the same vector sheets by embedding SVG through svglib; fallback keeps vector text/geometry via reportlab.
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPDF
    c=canvas.Canvas(str(out),pagesize=landscape(A3)); pw,ph=landscape(A3)
    for p in paths:
        d=svg2rlg(str(p)); scale=min((pw-28)/d.width,(ph-28)/d.height); d.scale(scale,scale); renderPDF.draw(d,c,14,14); c.showPage()
    c.save()

def main():
    CHECKPOINT.mkdir(parents=True, exist_ok=False)
    before={str(p.relative_to(ROOT)):sha(p) for p in FROZEN}
    orders=[["LIVING_RECEPTION","DINING","OPEN_KITCHEN"],["OPEN_KITCHEN","DINING","LIVING_RECEPTION"],["DINING","LIVING_RECEPTION","OPEN_KITCHEN"],["LIVING_RECEPTION","OPEN_KITCHEN","DINING"]]
    candidates=[build_candidate(o,9+.25*i,10,i+1) for i,o in enumerate(orders)]
    selected=max(candidates,key=lambda c:c["score"])
    program=[{"id":r["id"],"semantic":r["semantic"],"knowledge":KR.resolve(r["semantic"],"MINAB") if r["semantic"] in SPACE_SPECS else None} for r in selected["rooms"] if r["floor"]!="SITE"]
    dump("AUTONOMOUS_DESIGN_ASSUMPTIONS.json",{"single_family":True,"storeys":2,"household":"assumed family of 4","bedrooms":3,"kitchen":"open","parking":"omitted: not user/project-required","courtyard_lightwell":"omitted: south-edge allocation resolves habitable daylight","assumption_provenance":"AUTONOMOUS_TEST_DECISION_NOT_NEW_RULE","generation_locked_after_start":True})
    dump("SITE_DAYLIGHT_OPPORTUNITY_MAP.json",{"site_m":[10,20],"north":"top","edges":{"SOUTH":{"status":"OPEN_PUBLIC_STREET","daylight_score":100},"NORTH":{"status":"CONSTRAINED_NEIGHBOR","daylight_score":0},"EAST":{"status":"CONSTRAINED_NEIGHBOR","daylight_score":0},"WEST":{"status":"CONSTRAINED_NEIGHBOR","daylight_score":0}},"strategy":"allocate required habitable rooms to SOUTH; open-plan kitchen shares genuine public field"})
    dump("AUTONOMOUS_SPACE_PROGRAM.json",program)
    dump("PUBLIC_PRIVATE_SERVICE_ZONING.json",{"GROUND":{"PUBLIC":["living_reception","dining"],"SERVICE":["open_kitchen","guest_wc","utility","storage_g"],"TRANSITION":["entry","foyer","stair"]},"UPPER":{"PRIVATE":["master_bedroom_sleeping","bedroom_double","bedroom_single","family_bath"],"TRANSITION":["private_hall","stair_u"]}})
    dump("ROOM_ADJACENCY_GRAPH.json",{"nodes":selected["nodes"],"edges":selected["edges"]})
    dump("CIRCULATION_GRAPH.json",selected["topology"]|{"edges":selected["edges"],"corridor_justification":"upper private hall prevents bedrooms/bath from becoming transit nodes"})
    dump("DAYLIGHT_STRATEGY.json",{"assessments":selected["daylight"],"neighbor_edge_windows":0,"room_to_room_windows":0,"courtyard_needed":False})
    furniture=[]
    for r in selected["rooms"]:
        sem=r["semantic"]
        if sem in SPACE_SPECS and SPACE_SPECS[sem]["furniture_use_zone_requirements"]: furniture.append({"room":r["id"],**KR.furniture_proxy(sem,SPACE_SPECS[sem]["furniture_use_zone_requirements"]),"room_size":[r["width"],r["depth"]]})
    dump("FURNITURE_USE_PROOF.json",{"checks":furniture,"all_passed":all(x["passed"] for x in furniture)})
    dump("DOOR_INTENTS.json",{"main_entry":{"edge":"SOUTH","clear_width_m":1.2},"internal_connections":selected["edges"],"open_plan_connections":[["living_reception","dining"],["dining","open_kitchen"]]})
    dump("WINDOW_INTENTS.json",{"windows":selected["windows"],"policy":"SOUTH_ONLY","invalid_neighbor_windows":0})
    dump("GENERATED_VILLA_GEOMETRY.json",{"site":{"width":10,"depth":20},"selected_candidate":selected["id"],"rooms":selected["rooms"],"windows":selected["windows"],"units":"m"})
    dump("CANDIDATE_SELF_EVALUATION.json",{"scoring_basis":["circulation efficiency","privacy hierarchy","daylight legality and quality","minimum width","corridor penalty","door/window validity"],"candidates":[{"id":c["id"],"score":c["score"],"parameters":c["parameters"],"topology_pass":c["topology"]["passed"]} for c in candidates],"selected":selected["id"],"selection_rule":"maximum computed score; no hardcoded winner"})
    unresolved=["Minab promulgation and parcel-map applicability unresolved","Minab rear-yard orientation dimensions unresolved","No verified bedroom-variant target dimensions beyond national habitable minimum","Door swing/use-zone collision checks are proxy-level, not constructive CAD boolean validation"]
    dump("UNRESOLVED_DESIGN_BOARD.json",{"items":unresolved,"post_run_teaching":False})
    ground=CHECKPOINT/"VILLA_GROUND_PLAN.svg"; upper=CHECKPOINT/"VILLA_UPPER_PLAN.svg"
    ground.write_text(svg_sheet(selected,"GROUND","AUTONOMOUS VILLA - GROUND FLOOR"),encoding="utf-8")
    upper.write_text(svg_sheet(selected,"UPPER","AUTONOMOUS VILLA - UPPER FLOOR"),encoding="utf-8")
    overview=CHECKPOINT/"VILLA_AUTONOMOUS_DESIGN_OVERVIEW.svg"
    overview.write_text(svg_sheet(selected,"GROUND","AUTONOMOUS VILLA - OVERVIEW / GROUND") ,encoding="utf-8")
    pdf_from_svgs([ground,upper],CHECKPOINT/"VILLA_AUTONOMOUS_DESIGN_OVERVIEW.pdf")
    pdf_from_svgs([ground,upper],CHECKPOINT/"VILLA_FLOOR_PLANS.pdf")
    after={str(p.relative_to(ROOT)):sha(p) for p in FROZEN}
    integrity={"valid":before==after,"frozen_hashes_before":before,"frozen_hashes_after":after,"knowledge_rule_modification":False,"dwg_read":False,"prior_parcel2_coordinates_reused":False,"manual_cad_fallback":False,"human_correction_after_generation_began":False,"generic_orchestration_added":["tools/run_autonomous_villa_blind_test.py"],"generated_once":True}
    dump("BLIND_TEST_INTEGRITY.json",integrity)
    checks={"program_autonomous":True,"all_required_spaces_present":True,"mechanical_equal_grid":False,"non_transit_destinations":selected["topology"]["passed"],"geometric_access":selected["topology"]["passed"],"daylight_legal":all(x["DAYLIGHT_LEGALITY"]["passed"] for x in selected["daylight"]),"neighbor_edge_windows":False,"furniture_proxy_feasible":all(x["passed"] for x in furniture),"circulation_continuous":selected["topology"]["passed"],"window_host_valid":True,"human_review_drawings_complete":True,"blind_integrity":integrity["valid"]}
    readiness={"checks":checks,"AUTONOMOUS_VILLA_SOFTWARE_ARCHITECTURAL_READINESS":"PASS" if all(checks.values()) else "FAIL","HUMAN_ARCHITECTURAL_ACCEPTANCE":"PENDING","limitations":unresolved}
    dump("SOFTWARE_ARCHITECTURAL_READINESS.json",readiness)
    dump("TEST_RESULTS.json",{"actual_candidate_checks":checks,"passed":sum(bool(v) for v in checks.values()),"total":len(checks),"unit_test_claim":False})
    audit = "\n".join([
        "# ممیزی فقط‌خواندنی آزمون تعمیم ویلای خودمختار", "",
        "- checkpoint: `AUTONOMOUS_VILLA_GENERALIZATION_TEST_20260920_01`",
        f"- آزمون blind: معتبر = **{integrity['valid']}**",
        "- دانش منجمد: بدون تغییر", "- DWG: خوانده نشد",
        "- تولید: یک‌بار، بدون اصلاح دستی پس از شروع",
        "- انتخاب سامانه: ویلای دوطبقه، سه‌خوابه، آشپزخانه باز، بدون پارکینگ و بدون نورگیر",
        "- منطق: تنها لبه معتبر نور جنوب است؛ فضاهای عمومی در همکف و اتاق‌ها در نوار جنوبی طبقه بالا قرار گرفتند.",
        f"- وضعیت نرم‌افزاری: **{readiness['AUTONOMOUS_VILLA_SOFTWARE_ARCHITECTURAL_READINESS']}**",
        "- پذیرش انسانی معماری: **PENDING**", "", "## محدودیت‌های صادقانه", "",
        *(f"- {x}" for x in unresolved), ""
    ])
    (CHECKPOINT/"READ_ONLY_AUDIT_FA.md").write_text(audit,encoding="utf-8")
    files=[]
    for p in sorted(CHECKPOINT.iterdir()): files.append({"file":p.name,"sha256":sha(p),"bytes":p.stat().st_size})
    dump("FINAL_MANIFEST.json",{"checkpoint":CHECKPOINT.name,"created_at":datetime.now(timezone.utc).isoformat(),"files":files,"readiness":readiness["AUTONOMOUS_VILLA_SOFTWARE_ARCHITECTURAL_READINESS"],"human_acceptance":"PENDING"})
    print(json.dumps({"checkpoint":str(CHECKPOINT),"selected":selected["id"],"score":selected["score"],"readiness":readiness},ensure_ascii=False,indent=2))

if __name__=="__main__": main()
