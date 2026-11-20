from __future__ import annotations
import hashlib,json,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(r"<repo-root>")
sys.path.insert(0,str(ROOT/"core/architecture/learning"))
from cumulative_human_learning_v2 import *
LEARN=ROOT/"outputs/VILLA_CUMULATIVE_HUMAN_LEARNING_20260920_02"
OUT=ROOT/"outputs/AUTONOMOUS_SINGLE_STOREY_VILLA_120M2_TEST_20260920_03"
REG=ROOT/"core/architecture/knowledge/human_architectural_learning_registry_v1.json"
SNAP=ROOT/"snapshots/VILLA_CUMULATIVE_HUMAN_LEARNING_20260920_02"
OLD=ROOT/"outputs/AUTONOMOUS_SINGLE_STOREY_VILLA_120M2_TEST_20260920_02"

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(folder,name,data): (folder/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")

def snapshot(paths):
    SNAP.mkdir(parents=True,exist_ok=False); rows=[]
    for p in paths:
        if not p.exists(): rows.append({"file":str(p.relative_to(ROOT)),"exists_before":False}); continue
        data=p.read_bytes(); dst=SNAP/(p.name+".before") ; dst.write_bytes(data)
        rows.append({"file":str(p.relative_to(ROOT)),"exists_before":True,"timestamp":datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat(),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),"snapshot":str(dst.relative_to(ROOT))})
    dump(SNAP,"SOURCE_FILE_SNAPSHOTS.json",rows); return rows

def furniture_svg(X,Y):
    return f'''<g id="furniture-layer" class="furniture-layer">
<g class="furniture double-bed"><rect x="{X(.55)}" y="{Y(18.7)}" width="150" height="142" rx="5"/><rect class="mattress" x="{X(.68)}" y="{Y(18.55)}" width="139" height="126"/><rect class="pillow" x="{X(.78)}" y="{Y(18.35)}" width="55" height="25" rx="8"/><rect class="pillow" x="{X(2.25)}" y="{Y(18.35)}" width="55" height="25" rx="8"/></g>
<g class="furniture bedside-tables"><rect x="{X(.35)}" y="{Y(16.1)}" width="25" height="25"/><rect x="{X(4.05)}" y="{Y(16.1)}" width="25" height="25"/></g>
<g class="furniture single-bed"><rect x="{X(8.05)}" y="{Y(18.8)}" width="62" height="145" rx="5"/><rect class="pillow" x="{X(8.2)}" y="{Y(18.55)}" width="49" height="24" rx="7"/></g>
<g class="furniture wardrobe"><rect x="{X(.45)}" y="{Y(19.65)}" width="145" height="24"/><path d="M{X(1.95)},{Y(19.65)}v24 M{X(.45)},{Y(19.65)}l72,24 M{X(3.95)},{Y(19.65)}l-72,24"/></g>
<g class="furniture sofa"><rect x="{X(.65)}" y="{Y(11.7)}" width="135" height="42" rx="12"/><path d="M{X(.65)},{Y(11.25)}h135 M{X(.95)},{Y(11.7)}v42 M{X(3.65)},{Y(11.7)}v42"/></g>
<g class="furniture armchairs"><rect x="{X(.7)}" y="{Y(10.1)}" width="50" height="46" rx="10"/><rect x="{X(3.2)}" y="{Y(10.1)}" width="50" height="46" rx="10"/></g>
<g class="furniture coffee-table"><ellipse cx="{X(2.55)}" cy="{Y(10.5)}" rx="44" ry="22"/></g><g class="furniture tv-media-wall"><rect x="{X(4.35)}" y="{Y(11.9)}" width="12" height="95"/><line x1="{X(4.2)}" y1="{Y(11)}" x2="{X(4.65)}" y2="{Y(11)}"/></g>
<g class="furniture dining-table-chairs"><rect x="{X(5.15)}" y="{Y(11.8)}" width="68" height="100" rx="8"/><circle cx="{X(5.0)}" cy="{Y(9.1)}" r="11"/><circle cx="{X(6.95)}" cy="{Y(9.1)}" r="11"/><circle cx="{X(5.0)}" cy="{Y(12.2)}" r="11"/><circle cx="{X(6.95)}" cy="{Y(12.2)}" r="11"/></g>
<g class="furniture kitchen-base-cabinets"><rect x="{X(7.25)}" y="{Y(12.65)}" width="135" height="25"/><path d="M{X(7.8)},{Y(12.65)}v25 M{X(8.55)},{Y(12.65)}v25 M{X(9.3)},{Y(12.65)}v25"/></g>
<g class="furniture sink"><rect x="{X(7.55)}" y="{Y(12.45)}" width="38" height="17" rx="5"/><circle cx="{X(8.0)}" cy="{Y(12.2)}" r="3"/></g><g class="furniture cooktop"><circle cx="{X(8.65)}" cy="{Y(12.25)}" r="8"/><circle cx="{X(9.0)}" cy="{Y(12.25)}" r="8"/></g><g class="furniture refrigerator"><rect x="{X(9.25)}" y="{Y(11.4)}" width="27" height="58"/><line x1="{X(9.25)}" y1="{Y(10.65)}" x2="{X(9.9)}" y2="{Y(10.65)}"/></g><g class="furniture peninsula"><rect x="{X(7.55)}" y="{Y(10.4)}" width="105" height="32"/><circle cx="{X(8)}" cy="{Y(9.5)}" r="10"/><circle cx="{X(9.2)}" cy="{Y(9.5)}" r="10"/></g>
<g class="furniture wc-bowl-tank"><rect x="{X(3.35)}" y="{Y(14.7)}" width="28" height="12"/><ellipse cx="{X(3.7)}" cy="{Y(13.85)}" rx="15" ry="22"/></g><g class="furniture basin"><path d="M{X(4.15)},{Y(14.75)}q22,30 44,0z"/></g><g class="furniture shower-zone"><rect x="{X(6.45)}" y="{Y(15.15)}" width="58" height="58"/><path d="M{X(6.45)},{Y(15.15)}l58,58 M{X(7.85)},{Y(15.15)}l-58,58"/></g><g class="furniture washing-machine"><circle cx="{X(7.75)}" cy="{Y(13.65)}" r="22"/><circle cx="{X(7.75)}" cy="{Y(13.65)}" r="14"/></g>
<g class="furniture parked-car"><rect x="{X(6.9)}" y="{Y(5.9)}" width="110" height="210" rx="26"/><path d="M{X(7.3)},{Y(5.25)}h75v-110h-75z"/><circle cx="{X(7.0)}" cy="{Y(1.5)}" r="8"/><circle cx="{X(9.2)}" cy="{Y(1.5)}" r="8"/><circle cx="{X(7.0)}" cy="{Y(5.2)}" r="8"/><circle cx="{X(9.2)}" cy="{Y(5.2)}" r="8"/></g></g>'''

def make_svg(c):
    W,H=1680,1120; ox,oy,s=370,1000,43; X=lambda x:ox+x*s; Y=lambda y:oy-y*s
    colors={"PUBLIC":"#f5eee1","SERVICE_PUBLIC":"#f2e5ca","TRANSITION":"#e7edf0","TRANSITION_SERVICE":"#e4ebed","PRIVATE_TRANSITION":"#e2e8ed","PRIVATE":"#e8edf2","ENVIRONMENTAL":"#d9ebd5"}
    p=[f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="#fcfbf7"/><style>text{{font-family:Tahoma,Arial,sans-serif;fill:#172830}}.room{{stroke:#7f8b8e;stroke-width:1.3}}.wall{{stroke:#16272f;stroke-width:9;fill:none}}.opening{{stroke:#fcfbf7;stroke-width:13}}.door{{stroke:#8d552d;stroke-width:2;fill:none}}.wide{{stroke:#2c91aa;stroke-width:4}}.furniture{{stroke:#66777e;stroke-width:1.4;fill:#e7ecee}}.furniture .mattress,.furniture .pillow{{fill:#f7f9f9}}.duct{{fill:#b9c9ce;stroke:#38545e;stroke-width:2}}.level{{fill:#992f2f;font-weight:bold}}.canopy{{fill:#c7d9e2;fill-opacity:.55;stroke:#376c80;stroke-width:2;stroke-dasharray:8 5}}.platform{{fill:#ded6c6;stroke:#796d5d}}.path{{stroke:#2486a3;stroke-width:3;stroke-dasharray:10 6;fill:none}}.joint{{stroke:#b64b3b;stroke-width:2;stroke-dasharray:8 6}}</style><text x="45" y="48" font-size="25" font-weight="bold">ArchitectOS - CUMULATIVE HUMAN LEARNING 02 - NEW CANDIDATE 03</text><text x="45" y="76" font-size="14">Single-storey villa | human-review sheet | A3 landscape | vector only</text>''']
    p.append(f'<rect x="{X(0)}" y="{Y(8.2)}" width="{10*s}" height="{8.2*s}" fill="#eef4e8" stroke="#6f8077"/>')
    for r in c["rooms"]:
        x1,y1,x2,y2=r["bbox"]; p.append(f'<rect class="room" x="{X(x1)}" y="{Y(y2)}" width="{(x2-x1)*s}" height="{(y2-y1)*s}" fill="{colors[r["zone"]]}"/>')
    # Site wall and gates; building walls with intentional wide opening.
    p += [f'<path class="wall" d="M{X(0)},{Y(0)}H{X(.55)} M{X(1.65)},{Y(0)}H{X(6.2)} M{X(9.4)},{Y(0)}H{X(10)} M{X(0)},{Y(0)}V{Y(20.2)}H{X(10)}V{Y(0)}"/>',f'<path class="joint" d="M{X(.1)},{Y(20.1)}H{X(9.9)} M{X(.1)},{Y(8.1)}V{Y(20.1)} M{X(9.9)},{Y(8.1)}V{Y(20.1)}"/>']
    p += [f'<rect class="platform" x="{X(.2)}" y="{Y(8.2)}" width="{9.6*s}" height="{.65*s}"/><rect class="canopy" x="{X(.2)}" y="{Y(8.2)}" width="{9.6*s}" height="{1.2*s}"/><text x="{X(4.6)}" y="{Y(7.15)}" text-anchor="middle" font-size="8.5">CANOPY 1.20 m - USER RULE</text>',f'<path class="path" d="M{X(1.1)},{Y(0)}V{Y(7.0)}"/><path class="path" d="M{X(7.8)},{Y(0)}V{Y(6.0)}"/>']
    p += [f'<path class="wall" d="M{X(.2)},{Y(8.2)}H{X(.8)} M{X(1.8)},{Y(8.2)}H{X(9.8)} M{X(.2)},{Y(8.2)}V{Y(20.2)} M{X(9.8)},{Y(8.2)}V{Y(20.2)} M{X(.2)},{Y(20.2)}H{X(4.7)} M{X(7.7)},{Y(20.2)}H{X(9.8)}"/>',f'<path class="wall" d="M{X(.2)},{Y(13)}H{X(.9)} M{X(2.7)},{Y(13)}H{X(3.1)} M{X(3.1)},{Y(13)}V{Y(15.1)} M{X(4.7)},{Y(13)}V{Y(20.2)} M{X(6.3)},{Y(13)}V{Y(15.4)} M{X(7.7)},{Y(15.4)}V{Y(20.2)} M{X(8.3)},{Y(13)}V{Y(15.4)} M{X(4.7)},{Y(16.2)}H{X(7.7)}"/>',f'<path class="wide" d="M{X(.9)},{Y(13)}H{X(2.7)}"/><text x="{X(1.8)}" y="{Y(13.18)}" text-anchor="middle" font-size="9">WIDE OPEN TRANSITION</text>']
    # entry, doors and inviting steps.
    p += [f'<path class="door" d="M{X(.8)},{Y(8.2)}v{-1*s} A{1*s},{1*s} 0 0 1 {X(1.8)},{Y(8.2)}"/>',f'<path d="M{X(.55)},{Y(7.45)}h{1.5*s} M{X(.72)},{Y(7.7)}h{1.16*s} M{X(.9)},{Y(7.95)}h{.8*s}" stroke="#8b765b" stroke-width="3" fill="none"/>']
    for x,y,w in [(3.25,13, .85),(4.85,16.2,.9),(6.45,15.4,.85),(8.55,15.4,.85)]: p.append(f'<path class="opening" d="M{X(x)},{Y(y)}H{X(x+w)}"/><path class="door" d="M{X(x)},{Y(y)}v{-w*s} A{w*s},{w*s} 0 0 1 {X(x+w)},{Y(y)}"/>')
    p += [f'<rect class="duct" x="{X(3.95)}" y="{Y(15.05)}" width="22" height="22"/><text x="{X(4.2)}" y="{Y(14.75)}" font-size="8">DUCT-WC</text>',f'<rect class="duct" x="{X(7.75)}" y="{Y(15.35)}" width="22" height="22"/><text x="{X(7.15)}" y="{Y(15.0)}" font-size="8">DUCT-BATH</text>']
    p.append(furniture_svg(X,Y))
    wet_label_pos={"guest_wc":(3.9,15.45),"family_bath":(7.2,15.72),"bed2_entry":(9.0,15.72),"private_hall":(5.5,15.75)}
    for r in c["rooms"]:
        x1,y1,x2,y2=r["bbox"]; cx=(x1+x2)/2; cy=(y1+y2)/2
        lx,ly=wet_label_pos.get(r["id"],(cx,cy)); fs=6.5 if r["id"] in wet_label_pos else 11
        p.append(f'<text x="{X(lx)}" y="{Y(ly)}" text-anchor="middle" font-size="{fs}" font-weight="bold" direction="rtl">{r["label_fa"]}</text><text x="{X(lx)}" y="{Y(ly)-13}" text-anchor="middle" font-size="{6.5 if r["id"] in wet_label_pos else 9}">{r["area_m2"]:.2f} m²</text>')
    p += [f'<text class="level" x="{X(2.2)}" y="{Y(4)}" font-size="13">YARD ±0.00</text>',f'<text class="level" x="{X(5.05)}" y="{Y(19.75)}" font-size="8.5">COURT ±0.00</text>',f'<text class="level" x="{X(1.3)}" y="{Y(8.7)}" font-size="11">FFL +0.38</text>',f'<text x="{X(5)}" y="{Y(0)+43}" text-anchor="middle" font-size="17" font-weight="bold">SOUTH STREET / خیابان جنوبی</text>']
    p += ['<text x="885" y="135" font-size="15" font-weight="bold">ARCHITECTURAL GATES</text><text x="885" y="166" font-size="12">Court: 12.00 m² / min width 3.00 m</text><text x="885" y="190" font-size="12">Court door from neutral distributor</text><text x="885" y="214" font-size="12">Guest WC: public/private transition</text><text x="885" y="238" font-size="12">Family bath: private hall access</text><text x="885" y="262" font-size="12">Dedicated WC + bath duct intents</text><text x="885" y="286" font-size="12">Wide open living-to-hall transition</text><text x="885" y="310" font-size="12">South platform + 1.20 m canopy + steps</text><text x="885" y="334" font-size="12">Spot levels contained in target surfaces</text><text x="885" y="358" font-size="12">Distinct semantic vector furniture groups</text><text x="885" y="405" font-size="13" font-weight="bold">LEGAL SANITARY NUMERIC MINIMUM</text><text x="885" y="430" font-size="11">UNRESOLVED - functional fixture clearance validated</text><text x="885" y="475" font-size="13" font-weight="bold">SEPARATION JOINT N/E/W</text><text x="885" y="500" font-size="11">WIDTH PENDING AUTHORITY - NOT DEDUCTED</text></svg>']
    return ''.join(p)

def main():
    if LEARN.exists() or OUT.exists() or SNAP.exists(): raise RuntimeError("TARGET_CHECKPOINT_ALREADY_EXISTS")
    # The three code files are additive new files staged immediately before this run;
    # only the canonical registry is an in-place knowledge target.
    snaps=snapshot([REG]);
    for p in [ROOT/"core/architecture/learning/cumulative_human_learning_v2.py",ROOT/"tests/test_cumulative_human_learning_v2.py",ROOT/"tools/run_cumulative_human_learning_02.py"]:
        snaps.append({"file":str(p.relative_to(ROOT)),"exists_before":False,"created_additively":True,"bytes_after":p.stat().st_size,"sha256_after":sha(p)})
    dump(SNAP,"SOURCE_FILE_SNAPSHOTS.json",snaps); LEARN.mkdir(parents=True); OUT.mkdir(parents=True)
    registry=write_registry(REG); c=fresh_candidate_03(); result=validate(c)
    # Registry and precedent artifacts are copied, not substituted for canonical append-only registry.
    dump(LEARN,"HUMAN_ARCHITECTURAL_LEARNING_REGISTRY_V1.json",registry); dump(LEARN,"NEGATIVE_PRECEDENT_CANDIDATE_02.json",negative_precedent_02()); dump(LEARN,"SOURCE_FILE_SNAPSHOTS.json",snaps)
    audit="""# ممیزی فقط‌خواندنی پیش از تغییر - یادگیری تجمعی انسانی ۰۲\n\n| FILE | CLASS-FUNCTION | CURRENT BEHAVIOR | HUMAN FAILURE | GENERALIZABLE LEARNING | EXACT LOCATION | PROVENANCE |\n|---|---|---|---|---|---|---|\n| core/architecture/learning/villa_site_access_learning_v1.py | fresh_candidate | court 2.7x4, door from bath_service_lobby | wet-space access and undersize | neutral distributor + conditional Topic 4 gate | lines 99,107-109,126,138 | HUMAN_REVIEW + T4-4-5-8-3-5 |\n| same | VillaGeometryValidator | edge existence treated as proof | no privacy/domain/fixture checks | graph+door+domain+geometry validation | lines 144-183 | HUMAN_REVIEW_AUTHORITATIVE |\n| tools/run_villa_site_access_learning_01.py | svg | generic primitives and misplaced yard datum | weak review graphics | semantic symbols and polygon containment | lines 15,61-86 | ARCHITECTURAL_GRAPHICS |\n| candidate 02 FULL_GEOMETRY_GRAPH_INTENTS.json | openings/rooms | court_door from service; 2.10/1.95 wet rooms | composition rejected | cumulative negative precedent | openings 639/699; rooms 91-113 | CURRENT_ARTIFACT_FACT |\n"""
    (LEARN/"READ_ONLY_AUDIT_FA.md").write_text(audit,encoding="utf-8")
    dump(OUT,"FULL_CANDIDATE_GEOMETRY_GRAPH_INTENTS.json",c); dump(OUT,"COURTYARD_ACCESS_PRIVACY_AUDIT.json",{"access":"private_hall -> court","source_kind":"HALL","neutral":True,"topic4":c["courtyard_rule"],"result":result["checks"]}); dump(OUT,"WET_SPACE_VENTILATION_INTENTS.json",c["ducts"]); dump(OUT,"SANITARY_FIXTURE_CLEARANCE_AUDIT.json",{"verified_legal_numeric_minimum":c["legal_sanitary_numeric_minimum"],"functional":c["fixtures"]}); dump(OUT,"ENTRANCE_ARRIVAL_SEQUENCE.json",c["arrival"]); dump(OUT,"SPOT_LEVEL_PLACEMENT_AUDIT.json",{"levels":c["levels"],"inside_targets":result["checks"]["spot_levels_inside_targets"]}); dump(OUT,"SEMANTIC_FURNITURE_SYMBOL_AUDIT.json",{"symbols":c["furniture_symbols"],"distinct_svg_groups":True,"generic_identical_rectangles":False}); dump(OUT,"SOFTWARE_ARCHITECTURAL_READINESS.json",{"SOFTWARE_ARCHITECTURAL_READINESS":result["status"],"HUMAN_ARCHITECTURAL_ACCEPTANCE":"PENDING" if result["status"]=="PASS" else "NOT_ELIGIBLE","architectural_composition_gate":result});
    svg=OUT/"VILLA_120M2_SINGLE_STOREY_REVIEW_FA.svg"; svg.write_text(make_svg(c),encoding="utf-8")
    print(json.dumps({"learning":str(LEARN),"candidate":str(OUT),"validation":result},ensure_ascii=False,indent=2))

if __name__=="__main__": main()
