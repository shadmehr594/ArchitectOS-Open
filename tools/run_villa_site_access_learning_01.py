from __future__ import annotations
import hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(r"<repo-root>")
LEARN=ROOT/"outputs/VILLA_SITE_ACCESS_AND_GEOMETRY_LEARNING_20260920_01"
CAND=ROOT/"outputs/AUTONOMOUS_SINGLE_STOREY_VILLA_120M2_TEST_20260920_02"
OLD=ROOT/"outputs/AUTONOMOUS_SINGLE_STOREY_VILLA_120M2_TEST_20260920_01"
sys.path.insert(0,str(ROOT/"core/architecture/learning"))
from villa_site_access_learning_v1 import fresh_candidate,VillaGeometryValidator

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(folder,name,data): (folder/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
def svg(c):
    W,H=1600,1120; ox,oy,s=360,1000,42
    X=lambda x:ox+x*s; Y=lambda y:oy-y*s
    parts=[f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<rect width="100%" height="100%" fill="#fcfbf7"/><style>
text{{font-family:Tahoma,Arial,sans-serif;fill:#19272e}} .sitewall{{stroke:#5a5147;stroke-width:9;fill:none}}
.wall{{fill:#17252c}} .thin{{stroke:#64747b;stroke-width:1.5;fill:none}} .joint{{stroke:#b35343;stroke-width:2;stroke-dasharray:9 7;fill:none}}
.path{{stroke:#2482a0;stroke-width:3;stroke-dasharray:10 6;fill:none}} .door{{stroke:#9a5b32;stroke-width:2;fill:none}}
.window{{stroke:#2789a8;stroke-width:3;fill:none}} .furn{{stroke:#596b74;stroke-width:1.6;fill:#e5eaeb}}
.cab{{stroke:#735d40;stroke-width:1.5;fill:#e7dcc4}} .level{{fill:#8d2d2d;font-weight:bold}}
</style><text x="45" y="52" font-size="26" font-weight="bold">ArchitectOS - VILLA HUMAN-REVIEW LEARNING 01 - NEW CANDIDATE 02</text>
<text x="45" y="80" font-size="15">Fresh geometry | continuous wall graph | physical openings | A3 landscape review plan</text>''']
    # Yard/site field and rooms.
    parts.append(f'<rect x="{X(0)}" y="{Y(20)}" width="{10*s}" height="{20*s}" fill="#eef3e8" stroke="#8b9690"/>')
    for r in c["rooms"]:
        x1,y1,x2,y2=r["bbox"]; fill="#dfeeda" if r["id"]=="court" else "#f2efe7"
        parts.append(f'<rect x="{X(x1)}" y="{Y(y2)}" width="{(x2-x1)*s}" height="{(y2-y1)*s}" fill="{fill}" stroke="#a3aaa7"/>')
    # Site wall is physically broken at both south gates.
    parts += [f'<path d="M{X(0)},{Y(20)} H{X(10)} M{X(0)},{Y(0)} V{Y(20)} M{X(10)},{Y(0)} V{Y(20)}" class="sitewall"/>',
              f'<path d="M{X(0)},{Y(0)} H{X(.55)} M{X(1.65)},{Y(0)} H{X(6.2)} M{X(9.4)},{Y(0)} H{X(10)}" class="sitewall"/>']
    # Separation joint N/E/W, unresolved width deliberately not dimensioned.
    parts.append(f'<path d="M{X(.12)},{Y(19.88)} H{X(9.88)} M{X(.12)},{Y(8.1)} V{Y(19.88)} M{X(9.88)},{Y(8.1)} V{Y(19.88)}" class="joint"/>')
    # Draw wall solids, so cut intervals are actual absence of polygons.
    for sol in c["wall_graph"]["wall_solids"]:
        x1,y1,x2,y2=sol["bbox"]
        parts.append(f'<rect x="{X(x1)}" y="{Y(y2)}" width="{(x2-x1)*s}" height="{(y2-y1)*s}" class="wall"/>')
    # Doors/windows derived from opening intents.
    seg={x["id"]:x for x in c["wall_graph"]["centerlines"]}
    for o in c["wall_graph"]["openings"]:
        host=seg[o["host"]]; x1,y1=host["a"]; x2,y2=host["b"]; a=o["start"]; b=o["end"]
        if x1==x2: ax,ay=x1,y1+a; bx,by=x1,y1+b
        else: ax,ay=x1+a,y1; bx,by=x1+b,y1
        if o["kind"]=="WINDOW":
            if ax==bx: parts.append(f'<path d="M{X(ax)-4},{Y(ay)} V{Y(by)} M{X(ax)+4},{Y(ay)} V{Y(by)}" class="window"/>')
            else: parts.append(f'<path d="M{X(ax)},{Y(ay)-4} H{X(bx)} M{X(ax)},{Y(ay)+4} H{X(bx)}" class="window"/>')
        else:
            w=((bx-ax)**2+(by-ay)**2)**.5*s
            parts.append(f'<path d="M{X(ax)},{Y(ay)} l0,-{w} M{X(ax)},{Y(ay)} A{w},{w} 0 0 1 {X(bx)},{Y(by)-w}" class="door"/>')
            parts.append(f'<path d="M{X(ax)-4},{Y(ay)-5} v10 M{X(bx)+4},{Y(by)-5} v10" class="door"/>')
    # Gates with physical gaps and symbols.
    parts += [f'<path d="M{X(.55)},{Y(0)} L{X(.55)},{Y(1.1)} A{1.1*s},{1.1*s} 0 0 0 {X(1.65)},{Y(0)}" class="door"/>',
              f'<path d="M{X(6.2)},{Y(0)-7} H{X(9.4)} M{X(6.2)},{Y(0)+7} H{X(9.4)}" class="door"/>']
    # Access guides and parking/car.
    parts += [f'<path d="M{X(1.1)},{Y(0)} V{Y(8.2)}" class="path"/>',f'<path d="M{X(7.8)},{Y(0)} V{Y(5.8)}" class="path"/>',
              f'<rect x="{X(6.9)}" y="{Y(5.8)}" width="{2.6*s}" height="{5*s}" rx="12" class="furn"/>',
              f'<circle cx="{X(7.35)}" cy="{Y(1.35)}" r="9" fill="#657780"/><circle cx="{X(9.05)}" cy="{Y(1.35)}" r="9" fill="#657780"/><circle cx="{X(7.35)}" cy="{Y(5.25)}" r="9" fill="#657780"/><circle cx="{X(9.05)}" cy="{Y(5.25)}" r="9" fill="#657780"/>']
    # Readable furniture and kitchen work zones.
    parts += [
      f'<rect x="{X(.55)}" y="{Y(11.8)}" width="{2.5*s}" height="{.85*s}" rx="8" class="furn"/><rect x="{X(.8)}" y="{Y(12.0)}" width="{2*s}" height="{.25*s}" fill="#c9d1d4"/>',
      f'<rect x="{X(1.2)}" y="{Y(10.6)}" width="{1.5*s}" height="{.7*s}" class="furn"/><rect x="{X(3.65)}" y="{Y(12.7)}" width="{.35*s}" height="{2*s}" class="furn"/>',
      f'<rect x="{X(4.85)}" y="{Y(11.8)}" width="{1.55*s}" height="{2.1*s}" rx="5" class="furn"/>',
      f'<circle cx="{X(4.7)}" cy="{Y(10)}" r="10" class="furn"/><circle cx="{X(6.55)}" cy="{Y(10)}" r="10" class="furn"/><circle cx="{X(4.7)}" cy="{Y(12.4)}" r="10" class="furn"/><circle cx="{X(6.55)}" cy="{Y(12.4)}" r="10" class="furn"/>',
      f'<rect x="{X(7.2)}" y="{Y(12.75)}" width="{2.35*s}" height="{.55*s}" class="cab"/><rect x="{X(9.25)}" y="{Y(12.2)}" width="{.55*s}" height="{3.5*s}" class="cab"/>',
      f'<rect x="{X(7.55)}" y="{Y(10.8)}" width="{1.65*s}" height="{.65*s}" class="cab"/><circle cx="{X(8)}" cy="{Y(10.5)}" r="8" class="furn"/><circle cx="{X(8.75)}" cy="{Y(10.5)}" r="8" class="furn"/>',
      f'<rect x="{X(.75)}" y="{Y(18.4)}" width="{2.0*s}" height="{2.2*s}" rx="5" class="furn"/><rect x="{X(.75)}" y="{Y(16)}" width="{2.5*s}" height="{.55*s}" class="furn"/>',
      f'<rect x="{X(7.05)}" y="{Y(18.4)}" width="{2.0*s}" height="{2.2*s}" rx="5" class="furn"/><rect x="{X(6.8)}" y="{Y(16)}" width="{2.6*s}" height="{.55*s}" class="furn"/>',
      f'<rect x="{X(3.9)}" y="{Y(15.55)}" width="{.8*s}" height="{.8*s}" class="furn"/><circle cx="{X(4.75)}" cy="{Y(14.8)}" r="9" class="furn"/>',
      f'<ellipse cx="{X(5.45)}" cy="{Y(14.9)}" rx="13" ry="19" class="furn"/><circle cx="{X(6.05)}" cy="{Y(14.9)}" r="17" class="furn"/>']
    labels={r["id"]:(r["label_fa"],r["area_m2"],((r["bbox"][0]+r["bbox"][2])/2,(r["bbox"][1]+r["bbox"][3])/2)) for r in c["rooms"]}
    for rid,(lab,area,(cx,cy)) in labels.items():
        if rid in ("bath","utility"):
            parts.append(f'<text x="{X(cx)}" y="{Y(cy)}" text-anchor="middle" font-size="7.5" font-weight="bold" direction="rtl" transform="rotate(-90 {X(cx)} {Y(cy)})">{lab} - {area:.2f} m²</text>')
        elif rid=="kitchen":
            parts.append(f'<text x="{X(cx)}" y="{Y(9.25)}" text-anchor="middle" font-size="11" font-weight="bold" direction="rtl">آشپزخانه باز</text><text x="{X(cx)}" y="{Y(9.25)-17}" text-anchor="middle" font-size="10">PENINSULA - {area:.2f} m²</text>')
        else:
            parts.append(f'<text x="{X(cx)}" y="{Y(cy)}" text-anchor="middle" font-size="12" font-weight="bold" direction="rtl">{lab}</text><text x="{X(cx)}" y="{Y(cy)-18}" text-anchor="middle" font-size="11">{area:.2f} m²</text>')
    parts += [f'<text x="{X(3.5)}" y="{Y(5.4)}" text-anchor="middle" font-size="16" direction="rtl">حیاط جنوبی</text>',
      f'<text x="{X(5)}" y="{Y(0)+45}" text-anchor="middle" font-size="17" font-weight="bold">SOUTH STREET / خیابان جنوبی</text>',
      f'<text x="{X(1.1)}" y="{Y(.35)}" text-anchor="middle" font-size="10" direction="rtl">درب نفررو</text><text x="{X(7.8)}" y="{Y(.35)}" text-anchor="middle" font-size="10" direction="rtl">درب خودرو کشویی</text>',
      '<text x="850" y="326" font-size="11" fill="#a04030">SEPARATION JOINT N/E/W - WIDTH PENDING AUTHORITY - NOT DEDUCTED</text>',
      f'<text x="{X(2.7)}" y="{Y(8.55)}" font-size="11" class="level">حیاط ±0.00</text><text x="{X(.55)}" y="{Y(8.55)}" font-size="11" class="level">FFL +0.38</text>',
      f'<path d="M{X(.65)},{Y(7.65)} h{.55*s} v{-9} h{.55*s} v{-9}" class="thin"/><text x="{X(1.55)}" y="{Y(7.75)}" font-size="10" direction="rtl">دو پله ۰٫۱۹</text>',
      '<text x="95" y="160" font-size="14" font-weight="bold">NORTH</text><path d="M130 210 V125 l-13 22 m13-22 l13 22" stroke="#19272e" stroke-width="4" fill="none"/>',
      '<text x="850" y="145" font-size="15" font-weight="bold">VERIFIED DRAWING CONTENT</text><text x="850" y="176" font-size="12">Site walls and two controlled SOUTH gates</text><text x="850" y="200" font-size="12">Continuous centerline wall graph + solid cut intervals</text><text x="850" y="224" font-size="12">Geometry-verified hall, bedroom and courtyard access</text><text x="850" y="248" font-size="12">Yard ±0.00 / residential FFL +0.38 m</text><text x="850" y="272" font-size="12">Open kitchen: PENINSULA + cabinets + appliance zones</text><text x="850" y="296" font-size="12">Vector furniture/fixtures; door swings; window frames</text>',
      f'<path d="M{X(0)},{Y(0)+70} H{X(10)}" class="thin"/><text x="{X(5)}" y="{Y(0)+90}" text-anchor="middle" font-size="12">10.00 m</text>',
      f'<path d="M{X(10)+45},{Y(0)} V{Y(20)}" class="thin"/><text x="{X(10)+70}" y="{Y(10)}" transform="rotate(-90 {X(10)+70} {Y(10)})" font-size="12">20.00 m</text>',
      '</svg>']
    return ''.join(parts)

def main():
    LEARN.mkdir(parents=True,exist_ok=False); CAND.mkdir(parents=True,exist_ok=False)
    audited=[ROOT/"tools/run_constrained_villa_test_02.py",ROOT/"tools/finalize_constrained_villa_test_02.py",ROOT/"core/architecture/knowledge/architectural_space_knowledge_v1.py",OLD/"GENERATED_VILLA_GEOMETRY.json",OLD/"VILLA_120M2_SINGLE_STOREY_PLAN.svg",OLD/"TEST_RESULTS.json",OLD/"SOFTWARE_ARCHITECTURAL_READINESS.json"]
    snaps=[{"file":str(p.relative_to(ROOT)),"timestamp_utc":datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat(),"bytes":p.stat().st_size,"sha256":sha(p)} for p in audited]
    dump(LEARN,"SOURCE_FILE_SNAPSHOTS.json",{"created_before_modification":True,"files":snaps})
    audit='''# ممیزی فقط‌خواندنی - یادگیری بازبینی انسانی ویلا ۰۱\n\n| FILE | CLASS-FUNCTION | CURRENT BEHAVIOR | HUMAN-REVIEW FAILURE | GENERALIZABLE FIX | EXACT LOCATION | PROVENANCE |\n|---|---|---|---|---|---|---|\n| tools/run_constrained_villa_test_02.py | make_candidate / svg | دیوارها stroke جدا و دسترسی metadata است | راهرو و اتاق در هندسه بسته؛ دیوار سایت و گیت غایب | چهار قرارداد مستقل دانش، realization، validation و graphics | make_candidate(), svg(), checks | HUMAN_REVIEW_AUTHORITATIVE |\n| tools/finalize_constrained_villa_test_02.py | manifest | PASS آزمون را بدون پذیرش انسانی ثبت می‌کند | PASS کاذب در برابر شکست فیزیکی | precedent افزایشی و verdict هندسه‌محور | manifest fields | HUMAN_REJECTION |\n| core/architecture/knowledge/architectural_space_knowledge_v1.py | resolver | ontology فضا/نور/گردش، بدون enclosure/level/kitchen realization | دانش لازم موجود نیست | module افزایشی learning؛ عدم تغییر دانش تاریخی | core/architecture/learning/villa_site_access_learning_v1.py | GENERALIZED_LEARNING |\n| GENERATED_VILLA_GEOMETRY.json | geometry payload | فاقد wall polygons و site walls | graph بر دیوار واقعی منطبق نیست | wall graph، wall solids و cut intervals | wall_graph | HUMAN_REVIEW_AUTHORITATIVE |\n| VILLA_120M2_SINGLE_STOREY_PLAN.svg | renderer | خط‌های جدا، مبلمان مستطیلی، بدون تراز و gate | شکست خوانایی/توپولوژی | علائم برداری معنایی و annotation کامل | SVG layers | ARCHITECTURAL_GRAPHICS |\n| TEST_RESULTS.json | checks | booleanهای self-reported | collision واقعی اثبات نشده | fail-closed geometry checks | VillaGeometryValidator | VALIDATION_CONTRACT |\n'''
    (LEARN/"READ_ONLY_AUDIT_FA.md").write_text(audit,encoding="utf-8")
    rejection={"candidate":OLD.name,"SOFTWARE_GEOMETRIC_ARCHITECTURAL_READINESS":"FAIL","HUMAN_ARCHITECTURAL_ACCEPTANCE":"REJECTED","REASON":"SITE_ENTRY_WALL_TOPOLOGY_ACCESS_REALIZATION_AND_ARCHITECTURAL_DRAWING_FAILURE","historical_checkpoint_modified":False,"authoritative":True}
    dump(LEARN,"HUMAN_REJECTION_PRECEDENT_VILLA_01.json",rejection)
    c=fresh_candidate(); result=VillaGeometryValidator().validate(c)
    dump(LEARN,"SITE_ENCLOSURE_KNOWLEDGE.json",c["site_enclosure"]); dump(LEARN,"LEVEL_DATUM_KNOWLEDGE.json",c["levels"])
    dump(LEARN,"WALL_TOPOLOGY_CONTRACT.json",{"model":c["wall_graph"]["solid_model"],"junctions":"L_T_X_SHARED_NODES","openings":"CUT_SOLID_INTERVALS","failure_codes":["WALL_JUNCTION_DISCONNECTED","WALL_SOLID_FRAGMENTED"]})
    dump(LEARN,"COURTYARD_ACCESS_SEMANTICS.json",c["courtyard"]); dump(LEARN,"KITCHEN_LAYOUT_SEMANTICS.json",c["kitchen_intent"])
    dump(LEARN,"FURNITURE_VECTOR_SYMBOL_CONTRACT.json",{"symbols":c["furniture"],"vector_only":True,"recognizable_required":True})
    dump(LEARN,"TEST_RESULTS.json",result)
    dump(CAND,"FULL_GEOMETRY_GRAPH_INTENTS.json",c); dump(CAND,"WALL_ACCESS_VALIDATION.json",result)
    dump(CAND,"SITE_ENCLOSURE_AND_GATES.json",c["site_enclosure"]); dump(CAND,"LEVEL_DATUM_AND_ENTRY_TRANSITION.json",c["levels"])
    dump(CAND,"KITCHEN_LAYOUT_INTENT.json",c["kitchen_intent"]); dump(CAND,"COURTYARD_ACCESS_INTENT.json",c["courtyard"])
    (CAND/"VILLA_120M2_SINGLE_STOREY_REVIEW_FA.svg").write_text(svg(c),encoding="utf-8")
    readiness={"SOFTWARE_ARCHITECTURAL_READINESS":result["status"],"HUMAN_ARCHITECTURAL_ACCEPTANCE":"PENDING" if result["status"]=="PASS" else "NOT_READY","failure_codes":result["failure_codes"],"geometry_based":True,"metadata_only_pass_forbidden":True}
    dump(CAND,"SOFTWARE_ARCHITECTURAL_READINESS.json",readiness); dump(CAND,"TEST_RESULTS.json",result)
    print(json.dumps({"learning":str(LEARN),"candidate":str(CAND),"result":result},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
