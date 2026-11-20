"""Create the additive functional-design checkpoint and vector review sheet."""
from __future__ import annotations

import hashlib, json, math, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from core.architecture.contracts.functional_space_ontology_v1 import ontology_document
from core.architecture.reasoning.functional_architectural_design_gate_v1 import FunctionalArchitecturalDesignGateV1

OUT=ROOT/"outputs"/"FUNCTIONAL_ARCHITECTURAL_DESIGN_GATE_20260920_02"


def dump(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def esc(value): return str(value).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")


COLORS={"COMMON":"#d8e8ee","R1_U1":"#f7ead4","R2_U1":"#e5f0dc","R2_U2":"#efe1f2"}


def make_svg(candidate,path):
    width,height=1684,1191; scale=22; panels={"G":(70,120),"R1":(520,120),"R2":(970,120),"ROOF":(520,650)}
    items=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="#fbfaf6"/>','<style>text{font-family:Arial,sans-serif;fill:#17232a}.t{font-size:24px;font-weight:700}.s{font-size:11px}.n{font-size:9px}.wall{fill:none;stroke:#182329;stroke-width:4.4}.joint{fill:none;stroke:#b33;stroke-width:2;stroke-dasharray:8 5}.window{stroke:#1987a5;stroke-width:5}.door{stroke:#805026;stroke-width:2;fill:none}.dim{stroke:#65737a;stroke-width:1}.common{fill:#d8e8ee}</style>',
           '<text x="70" y="55" class="t">ArchitectOS - Functional Architectural Design Gate</text>',
           '<text x="70" y="85" class="s">Four-level architecture-first candidate | human approval remains PENDING</text>']
    by={s["id"]:s for s in candidate["spaces"]}
    for level,(ox,oy) in panels.items():
        items.append(f'<text x="{ox}" y="{oy-24}" class="t">{level}</text>')
        items.append(f'<rect x="{ox}" y="{oy}" width="{10*scale}" height="{20*scale}" class="wall"/>')
        items.append(f'<path d="M {ox} {oy} H {ox+10*scale} M {ox} {oy} V {oy+20*scale} M {ox+10*scale} {oy} V {oy+20*scale}" class="joint"/>')
        for s in [x for x in candidate["spaces"] if x["level"]==level]:
            x0,y0,x1,y1=s["rect"]; x=ox+x0*scale; y=oy+y0*scale; w=(x1-x0)*scale; h=(y1-y0)*scale
            color=COLORS.get(s["owner"],"#f1efe7")
            items.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{color}" stroke="#263238" stroke-width="{max(1.2,.2*scale):.1f}"/>')
            label=s["id"].replace("R1_","").replace("R2_U1_","U1 ").replace("R2_U2_","U2 ").replace("G_","").replace("ROOF_","")
            items.append(f'<text x="{x+w/2:.1f}" y="{y+h/2-2:.1f}" text-anchor="middle" class="n">{esc(label)}</text><text x="{x+w/2:.1f}" y="{y+h/2+10:.1f}" text-anchor="middle" class="n">{s["area_m2"]:.1f} m2</text>')
        items.append(f'<text x="{ox+5*scale}" y="{oy+20*scale+24}" text-anchor="middle" class="s">SOUTH STREET / ACCESS</text>')
        items.append(f'<path d="M {ox+10*scale+25} {oy+75} V {oy+15} l -8 14 m 8 -14 l 8 14" class="dim"/><text x="{ox+10*scale+18}" y="{oy+10}" class="s">N</text>')
        items.append(f'<text x="{ox}" y="{oy+20*scale+43}" class="n">10.00 m x 20.00 m | walls shown at 0.20 m graphic thickness</text>')
    # Door intent symbols are abstracted at source/target centroids; they remain tied to typed edges.
    for d in candidate["door_intents"]:
        a,b=by[d["from_space"]],by[d["to_space"]]
        if a["level"]!=b["level"]: continue
        ox,oy=panels[a["level"]]; ca=((a["rect"][0]+a["rect"][2])/2,(a["rect"][1]+a["rect"][3])/2); cb=((b["rect"][0]+b["rect"][2])/2,(b["rect"][1]+b["rect"][3])/2)
        mx,my=ox+(ca[0]+cb[0])/2*scale,oy+(ca[1]+cb[1])/2*scale
        items.append(f'<path d="M {mx:.1f} {my:.1f} l 13 0 a 13 13 0 0 1 -13 13" class="door"/>')
    for w in candidate["window_intents"]:
        s=by[w["space"]]; ox,oy=panels[s["level"]]; x0,y0,x1,y1=s["rect"]
        # Window intent is drawn on the relevant room boundary, not as a free symbol.
        x=ox+(x0+x1)/2*scale; y=oy+(y0 if w["exposure"]=="SOUTH_STREET" else y1)*scale
        items.append(f'<line x1="{x-11:.1f}" y1="{y:.1f}" x2="{x+11:.1f}" y2="{y:.1f}" class="window"/>')
    items += ['<rect x="970" y="650" width="640" height="350" fill="#fff" stroke="#87939a"/>',
              '<text x="995" y="685" class="t">Readiness status</text>',
              f'<text x="995" y="720" class="s">{esc(candidate["proofs"]["composition"]["status"])}</text>',
              '<text x="995" y="752" class="s">Previous candidate: HUMAN ARCHITECTURAL ACCEPTANCE - REJECTED</text>',
              '<text x="995" y="780" class="s">Reason: MECHANICAL_GRID_PACKING_WITHOUT_ARCHITECTURAL_FUNCTIONAL_COMPOSITION</text>',
              '<text x="995" y="820" class="s">Legend: blue = COMMON | tan/green/purple = private unit ownership</text>',
              '<text x="995" y="850" class="s">Dashed N/E/W: SEPARATION JOINT - WIDTH PENDING AUTHORITY - NOT DEDUCTED</text>',
              '<text x="995" y="880" class="s">No CAD fallback. No Structure/BIM/IFC assumptions. No render/image generation.</text>',
              '<text x="995" y="930" class="s">Functional proxies: bed/wardrobe, seating route, dining, kitchen, wet fixtures, vehicle.</text>',
              '<text x="995" y="960" class="s">Human architectural approval is exclusively the user/architect decision.</text>', '</svg>']
    path.write_text("\n".join(items),encoding="utf-8")


def make_pdf(candidate,path):
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.pdfgen.canvas import Canvas
    c=Canvas(str(path),pagesize=landscape(A3)); W,H=landscape(A3); scale=12.8; panels={"G":(38,330),"R1":(335,330),"R2":(632,330),"ROOF":(335,26)}
    c.setTitle("ArchitectOS Functional Architectural Design Gate")
    c.setFont("Helvetica-Bold",18); c.drawString(38,H-32,"ArchitectOS - Functional Architectural Design Gate")
    c.setFont("Helvetica",8); c.drawString(38,H-48,"Four-level vector review sheet | SOFTWARE ARCHITECTURAL READINESS: PASS | HUMAN ACCEPTANCE: PENDING")
    rgb={"COMMON":(.84,.91,.94),"R1_U1":(.97,.91,.82),"R2_U1":(.90,.94,.86),"R2_U2":(.94,.88,.95)}
    for level,(ox,oy) in panels.items():
        c.setFont("Helvetica-Bold",14); c.drawString(ox,oy+20*scale+10,level)
        for s in [x for x in candidate["spaces"] if x["level"]==level]:
            x0,y0,x1,y1=s["rect"]; x=ox+x0*scale; y=oy+(20-y1)*scale; w=(x1-x0)*scale; h=(y1-y0)*scale
            c.setFillColorRGB(*rgb.get(s["owner"],(.94,.93,.9))); c.setStrokeColorRGB(.12,.17,.19); c.setLineWidth(2.56); c.rect(x,y,w,h,fill=1,stroke=1)
            c.setFillColorRGB(.08,.12,.14); c.setFont("Helvetica",5.5); label=s["id"].replace("R2_U1_","U1 ").replace("R2_U2_","U2 ")
            c.drawCentredString(x+w/2,y+h/2+2,label); c.drawCentredString(x+w/2,y+h/2-5,f'{s["area_m2"]:.1f} m2')
        c.setDash(4,3); c.setStrokeColorRGB(.7,.1,.1); c.setLineWidth(1); c.line(ox,oy+20*scale,ox+10*scale,oy+20*scale); c.line(ox,oy,ox,oy+20*scale); c.line(ox+10*scale,oy,ox+10*scale,oy+20*scale); c.setDash()
        c.setFillColorRGB(.08,.12,.14); c.setFont("Helvetica",6); c.drawCentredString(ox+5*scale,oy-9,"SOUTH STREET / ACCESS | 10.00 m x 20.00 m")
    by={s["id"]:s for s in candidate["spaces"]}
    c.setStrokeColorRGB(.50,.30,.12); c.setLineWidth(1)
    for d in candidate["door_intents"]:
        a,b=by[d["from_space"]],by[d["to_space"]]
        if a["level"]!=b["level"]: continue
        ox,oy=panels[a["level"]]; ca=((a["rect"][0]+a["rect"][2])/2,(a["rect"][1]+a["rect"][3])/2); cb=((b["rect"][0]+b["rect"][2])/2,(b["rect"][1]+b["rect"][3])/2)
        mx=ox+(ca[0]+cb[0])/2*scale; my=oy+(20-(ca[1]+cb[1])/2)*scale
        c.line(mx,my,mx+8,my); c.arc(mx-8,my-8,mx+8,my+8,0,90)
    c.setStrokeColorRGB(.05,.52,.68); c.setLineWidth(3)
    for w in candidate["window_intents"]:
        s=by[w["space"]]; ox,oy=panels[s["level"]]; x0,y0,x1,y1=s["rect"]
        x=ox+(x0+x1)/2*scale; boundary=y0 if w["exposure"]=="SOUTH_STREET" else y1; y=oy+(20-boundary)*scale
        c.line(x-7,y,x+7,y)
    c.setFont("Helvetica-Bold",13); c.drawString(632,260,"Readiness and negative learning")
    lines=[candidate["proofs"]["composition"]["status"],"Previous candidate: HUMAN ARCHITECTURAL ACCEPTANCE - REJECTED","Reason: MECHANICAL_GRID_PACKING_WITHOUT_ARCHITECTURAL_FUNCTIONAL_COMPOSITION","Dashed N/E/W: SEPARATION JOINT - WIDTH PENDING AUTHORITY - NOT DEDUCTED","No CAD fallback / Structure / BIM / IFC / render / image generation.","Human architectural approval remains exclusively the user decision."]
    c.setFont("Helvetica",8)
    for i,line in enumerate(lines): c.drawString(632,240-i*16,line)
    c.showPage(); c.save()


def main():
    if OUT.exists(): raise SystemExit(f"Refusing to overwrite historical artifact: {OUT}")
    OUT.mkdir(parents=True); (OUT/"snapshots_prechange").mkdir()
    candidate=FunctionalArchitecturalDesignGateV1().build()
    if not candidate["proofs"]["composition"]["passed"]: raise SystemExit(candidate["proofs"]["composition"]["failures"])
    dump(OUT/"FULL_BUILDING_CANDIDATE.json",candidate); dump(OUT/"FUNCTIONAL_SPACE_ONTOLOGY.json",ontology_document())
    dump(OUT/"HUMAN_REJECTION_NEGATIVE_PRECEDENT.json",candidate["human_verdict_on_previous_candidate"])
    dump(OUT/"SOFTWARE_ARCHITECTURAL_READINESS.json",candidate["proofs"])
    make_svg(candidate,OUT/"PARCEL2_FUNCTIONAL_ARCHITECTURAL_REVIEW.svg"); make_pdf(candidate,OUT/"PARCEL2_FUNCTIONAL_ARCHITECTURAL_REVIEW.pdf")
    sources=[ROOT/"core/architecture/contracts/functional_space_ontology_v1.py",ROOT/"core/architecture/contracts/parcel2_human_rejection_20260920_v1.json",ROOT/"core/architecture/reasoning/architectural_topology_grammar_v1.py",ROOT/"core/architecture/reasoning/functional_architectural_design_gate_v1.py",ROOT/"tools/run_functional_architectural_design_gate_v1.py",ROOT/"tests/architecture_generation/test_functional_architectural_design_gate_v1.py"]
    snapshot={"created_utc":datetime.now(timezone.utc).isoformat(),"policy":"NEW_FILE_NO_PREIMAGE; existing historical files not modified","files":[{"path":str(p.relative_to(ROOT)),"preimage":"NEW_FILE_NO_PREIMAGE","bytes":p.stat().st_size,"sha256":sha(p)} for p in sources]}
    dump(OUT/"snapshots_prechange/NEW_FILES_PREIMAGE_MANIFEST.json",snapshot)
    outputs=[]
    for p in sorted(x for x in OUT.iterdir() if x.is_file()): outputs.append({"file":p.name,"bytes":p.stat().st_size,"sha256":sha(p)})
    manifest={"artifact":OUT.name,"created_utc":datetime.now(timezone.utc).isoformat(),"software_acceptance_previous":"PASS","human_architectural_acceptance_previous":"REJECTED","reason_previous":"MECHANICAL_GRID_PACKING_WITHOUT_ARCHITECTURAL_FUNCTIONAL_COMPOSITION","software_architectural_readiness":"PASS","human_architectural_acceptance":"PENDING","human_approval_is_user_decision":True,"historical_artifacts_overwritten":False,"outputs":outputs}
    dump(OUT/"FINAL_MANIFEST.json",manifest)
    print(json.dumps({"output":str(OUT),"status":candidate["proofs"]["composition"]["status"],"files":len(outputs)+1},ensure_ascii=False))


if __name__=="__main__": main()
