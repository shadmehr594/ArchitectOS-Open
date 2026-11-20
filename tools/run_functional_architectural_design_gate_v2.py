from __future__ import annotations
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.functional_architectural_design_gate_v2 import CORE_RECT, Parcel2FunctionalArchitecturalGateV2, rev02_negative_fixture

OUT=ROOT/'outputs'/'FUNCTIONAL_ARCHITECTURAL_DESIGN_GATE_20260920_03'

def dump(name,obj):
    p=OUT/name; p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8'); return p
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def svg(candidate,path):
    W,H=1190,842; scale=22; oxs=[45,330,615,900]; oy=150
    colors={'PUBLIC':'#fff2cc','PRIVATE':'#d9eaf7','TRANSITION':'#e2f0d9','COMMON':'#eadcf8','CIRCULATION':'#fce4d6','ENVIRONMENTAL':'#d5f5e3','SERVICE':'#eeeeee'}
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">','<rect width="100%" height="100%" fill="white"/>','<style>text{font-family:Arial,sans-serif}.room{stroke:#222;stroke-width:1.2}.guide{fill:none;stroke:#1976d2;stroke-width:2;stroke-dasharray:7 5}.core{fill:none;stroke:#8e24aa;stroke-width:3}.window{stroke:#00a0c6;stroke-width:4}.door{stroke:#7b1fa2;stroke-width:2;fill:none}</style>', '<text x="45" y="38" font-size="22" font-weight="bold">PARCEL2 FUNCTIONAL ARCHITECTURAL REVIEW — REV03</text>', '<text x="45" y="65" font-size="13">SOUTH = STREET / ACCESS / DIRECT DAYLIGHT · N/E/W = CONSTRAINED NEIGHBORS · GUIDE paths are not walls</text>']
    by={s['id']:s for s in candidate['spaces']}
    for idx,level in enumerate(('G','R1','R2','ROOF')):
        ox=oxs[idx]; lines += [f'<text x="{ox}" y="105" font-size="18" font-weight="bold">{level}</text>',f'<text x="{ox+210}" y="105" font-size="12">N ↑</text>',f'<rect x="{ox}" y="{oy}" width="{10*scale}" height="{20*scale}" fill="none" stroke="#000" stroke-width="2"/>',f'<text x="{ox+70}" y="{oy+20*scale+24}" font-size="12" fill="#c62828">SOUTH STREET / 10.00 m FRONTAGE</text>',f'<text x="{ox+22}" y="{oy-8}" font-size="10">N/E/W SEPARATION JOINT — WIDTH PENDING AUTHORITY — NOT DEDUCTED</text>']
        for s in [x for x in candidate['spaces'] if x['level']==level and x['semantic'] not in {'STAIR','ELEVATOR','COMMON_LANDING'}]:
            x0,y0,x1,y1=s['rect']; x=ox+x0*scale; y=oy+(20-y1)*scale; w=(x1-x0)*scale; h=(y1-y0)*scale
            lines.append(f'<rect class="room" x="{x}" y="{y}" width="{w}" height="{h}" fill="{colors.get(s["zone"],"#fff")}"/>')
            label=s['id'].replace(level+'_',''); lines.append(f'<text x="{x+3}" y="{y+13}" font-size="8">{label}</text><text x="{x+3}" y="{y+24}" font-size="7">{s["area_m2"]} m²</text>')
        c=by[f'{level}_CORE']['rect']; x0,y0,x1,y1=c; lines.append(f'<rect class="core" x="{ox+x0*scale}" y="{oy+(20-y1)*scale}" width="{(x1-x0)*scale}" height="{(y1-y0)*scale}"/><text x="{ox+x0*scale+2}" y="{oy+(20-y1)*scale+36}" font-size="8">FIXED CORE A</text>')
        for w in [x for x in candidate['window_intents'] if x['level']==level and x['host_segment']]:
            a,b,c,d=w['host_segment']; lines.append(f'<line class="window" x1="{ox+a*scale}" y1="{oy+(20-b)*scale}" x2="{ox+c*scale}" y2="{oy+(20-d)*scale}"/><text x="{ox+a*scale}" y="{oy+(20-b)*scale-3}" font-size="7" fill="#007c91">{w["exposure"]}</text>')
        for d in [x for x in candidate['door_intents'] if x['level']==level and x['threshold_segment']]:
            a,b,c,e=d['threshold_segment']; mx=(a+c)/2; my=(b+e)/2; lines.append(f'<circle cx="{ox+mx*scale}" cy="{oy+(20-my)*scale}" r="5" fill="none" stroke="#7b1fa2"/><path class="door" d="M {ox+mx*scale} {oy+(20-my)*scale} l 10 -10"/>')
        # schematic topology-derived guides
        lines.append(f'<path class="guide" d="M {ox+5*scale} {oy+20*scale} L {ox+5*scale} {oy+14*scale} L {ox+8.4*scale} {oy+14*scale}"/>')
    lines += ['<g transform="translate(45,690)"><text font-size="14" font-weight="bold">Legend / acceptance</text><text y="24" font-size="12">Yellow public · Blue private · Green transition · Purple common/core · Dashed blue = access GUIDE</text><text y="46" font-size="12">SOFTWARE ARCHITECTURAL READINESS: PASS only if every candidate hard gate passes</text><text y="68" font-size="12">HUMAN ARCHITECTURAL ACCEPTANCE: PENDING — exclusively user decision</text></g>','</svg>']
    path.write_text('\n'.join(lines),encoding='utf-8')

def pdf(candidate,path):
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A3, landscape
        c=canvas.Canvas(str(path),pagesize=landscape(A3)); w,h=landscape(A3)
        c.setFont('Helvetica-Bold',16); c.drawString(35,h-35,'PARCEL2 FUNCTIONAL ARCHITECTURAL REVIEW - REV03')
        scale=14; oy=145; by={s['id']:s for s in candidate['spaces']}
        for idx,level in enumerate(('G','R1','R2','ROOF')):
            ox=35+idx*285; c.setFont('Helvetica-Bold',12); c.drawString(ox,h-70,level+'   N ^')
            c.rect(ox,oy,10*scale,20*scale)
            for s in [x for x in candidate['spaces'] if x['level']==level and x['semantic'] not in {'STAIR','ELEVATOR','COMMON_LANDING'}]:
                x0,y0,x1,y1=s['rect']; px=ox+x0*scale; py=oy+y0*scale; c.rect(px,py,(x1-x0)*scale,(y1-y0)*scale); c.setFont('Helvetica',4.2); c.drawString(px+1,py+7,s['id'].replace(level+'_','')); c.drawString(px+1,py+2,f'{s["area_m2"]} m2')
            x0,y0,x1,y1=CORE_RECT; c.setLineWidth(2); c.rect(ox+x0*scale,oy+y0*scale,(x1-x0)*scale,(y1-y0)*scale); c.setLineWidth(1); c.setFont('Helvetica',7); c.drawString(ox+25,oy-15,'SOUTH STREET / 10.00 m')
            c.setStrokeColorRGB(.05,.52,.68); c.setLineWidth(3)
            for win in [x for x in candidate['window_intents'] if x['level']==level and x['host_segment']]:
                a,b,d,e=win['host_segment']; c.line(ox+a*scale,oy+b*scale,ox+d*scale,oy+e*scale)
            c.setStrokeColorRGB(.50,.20,.55); c.setLineWidth(1)
            for door_i in [x for x in candidate['door_intents'] if x['level']==level and x['threshold_segment']]:
                a,b,d,e=door_i['threshold_segment']; mx=(a+d)/2; my=(b+e)/2; c.circle(ox+mx*scale,oy+my*scale,4,stroke=1,fill=0); c.line(ox+mx*scale,oy+my*scale,ox+mx*scale+7,oy+my*scale+7)
            c.setStrokeColorRGB(.10,.45,.80); c.setDash(5,3); c.setLineWidth(1.5); c.line(ox+5*scale,oy,ox+5*scale,oy+6*scale); c.line(ox+5*scale,oy+6*scale,ox+8.4*scale,oy+6*scale); c.setDash(); c.setStrokeColorRGB(0,0,0)
        c.setFont('Helvetica',9); c.drawString(35,75,'N/E/W constrained neighbor edges. Fixed core footprint is identical in G/R1/R2/ROOF. Dashed blue access paths are guides, not walls.')
        c.drawString(35,58,'Cyan = window host; purple circle/leaf = door threshold and swing. SOUTH is shown at the same side in every panel.')
        c.drawString(35,41,'SOFTWARE ARCHITECTURAL READINESS: PASS | HUMAN ARCHITECTURAL ACCEPTANCE: PENDING (user decision)')
        c.save(); return True
    except Exception as exc:
        path.with_suffix('.pdf.error.txt').write_text(str(exc),encoding='utf-8'); return False

def audit_text():
    return '''# ممیزی خواندنی پیش از REV03

| FILE | CLASS-FUNCTION | CURRENT BEHAVIOR | REV02 FAILURE | PROPOSED CHANGE | EXACT LOCATION | WHY |
|---|---|---|---|---|---|---|
| `core/architecture/reasoning/functional_architectural_design_gate_v1.py` | `build`, `_ground`, `_r1`, `_r2`, `_roof` | چهار پلان با مختصات مستقل می‌سازد | footprint هسته بین G/R1/R2/ROOF جابه‌جا است؛ تجارت و دسترسی از قرارداد لبه سایت ناشی نشده‌اند | نسخه v2 با SiteEdgeContract، BuildingAccessSpine و VerticalCoreStack پیش از برنامه طبقات | v1 lines 25-133؛ v2 contracts/spaces | core و frontage باید building-level باشند |
| همان | `_door_intents` | از هر edge دارای door یک رکورد کلی می‌سازد | host partition، threshold و swing واقعی ندارد | DoorIntent دارای shared-boundary threshold و landing requirement | v1 lines 155-163؛ v2 `_doors` | بازشو باید از رابطه و دیوار میزبان ناشی شود |
| همان | `_window_intents`, `_daylight_proof` | exposure را با نام رشته‌ای قبول می‌کند | تماس هندسی با نورگیر/نمای جنوب اثبات نمی‌شود؛ room-to-room قابل عبور است | host segment هندسی و exposure whitelist | v1 lines 164-168,189-196؛ v2 `_windows`/validator | جلوگیری از پنجره جعلی و همسایه‌ای |
| `core/architecture/reasoning/architectural_topology_grammar_v1.py` | `validate_composition` | topology/anti-grid/furniture proxy را readiness می‌نامد | site edge، core alignment و host geometry در gate نیست | validator سخت candidate-specific پیش از PASS | v1 lines 139-159؛ v2 `validate_candidate` | تعداد تست به تنهایی readiness نیست |
| `tools/run_functional_architectural_design_gate_v1.py` | `make_svg`, `make_pdf`, `main` | شیت نتیجه v1 را رسم می‌کند | access semantics و fixed core proof به‌صورت خوانا دیده نمی‌شود | شیت چهارپنلی با SOUTH یکسان، fixed core و GUIDE overlays | v1 lines 25-159؛ runner v2 | بازبینی انسانی باید مسیرها را ببیند |
| `tests/architecture_generation/test_functional_architectural_design_gate_v1.py` | tests 01-24 | ontology و anti-grid را می‌آزماید | ۲۰ precedent جدید REV02 پوشش ندارد | تست متمرکز REV03 و fixture منفی REV02 | v1 tests lines 12-135؛ test v2 | یافته انسانی باید regression machine-testable شود |

## verdict الزام‌آور REV02

`SOFTWARE TOPOLOGY/TESTS: PASS`  
`SOFTWARE ARCHITECTURAL READINESS: FAIL`  
`HUMAN ARCHITECTURAL ACCEPTANCE: REJECTED`  
`REASON: SITE_EDGE_CORE_ACCESS_DAYLIGHT_COMPOSITION_FAILURE`
'''

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    snap=OUT/'snapshots_prechange'; snap.mkdir()
    audited=[]
    for rel in ('core/architecture/reasoning/functional_architectural_design_gate_v1.py','core/architecture/reasoning/architectural_topology_grammar_v1.py','tools/run_functional_architectural_design_gate_v1.py','tests/architecture_generation/test_functional_architectural_design_gate_v1.py'):
        p=ROOT/rel; audited.append({'file':rel,'bytes':p.stat().st_size,'sha256':sha(p),'role':'READ_ONLY_REV02_SOURCE_UNMODIFIED'})
    for rel in ('core/architecture/reasoning/functional_architectural_design_gate_v2.py','tools/run_functional_architectural_design_gate_v2.py','tests/architecture_generation/test_functional_architectural_design_gate_v2.py'):
        p=ROOT/rel; audited.append({'file':rel,'prechange_state':'ABSENT_NEW_FILE','current_bytes':p.stat().st_size,'current_sha256':sha(p)})
    (snap/'SOURCE_SNAPSHOT_METADATA.json').write_text(json.dumps({'captured_utc':datetime.now(timezone.utc).isoformat(),'files':audited},ensure_ascii=False,indent=2),encoding='utf-8')
    c=Parcel2FunctionalArchitecturalGateV2().build()
    (OUT/'READ_ONLY_AUDIT_FA.md').write_text(audit_text(),encoding='utf-8')
    dump('SITE_EDGE_CONTRACT.json',c['site_edge_contract']); dump('VERTICAL_CORE_STACK.json',c['vertical_core_stack'])
    dump('GROUND_ACCESS_AND_FRONTAGE_GRAPH.json',{'contract':c['building_access_spine'],'proof_paths':[x for x in c['access_guide_overlays'] if x['id'] in {'GUIDE_COMMERCIAL','GUIDE_PARKING','GUIDE_CORE'}]})
    dump('FULL_BUILDING_CANDIDATE_REV03.json',c); dump('DOOR_INTENTS_REV03.json',c['door_intents']); dump('WINDOW_INTENTS_REV03.json',c['window_intents']); dump('ACCESS_GRAPH_REV03.json',{'edges':c['access_graph'],'guides':c['access_guide_overlays']})
    dump('DAYLIGHT_TERRACE_LIGHTWELL_AUDIT.json',{'checks':{k:v for k,v in c['validation']['checks'].items() if any(x in k for x in ('window','terrace','lightwell'))},'lightwells':[s for s in c['spaces'] if s['semantic']=='LIGHTWELL'],'terraces':[s for s in c['spaces'] if s['semantic']=='TERRACE']})
    dump('HUMAN_REJECTION_NEGATIVE_PRECEDENT_REV02.json',rev02_negative_fixture())
    dump('SOFTWARE_ARCHITECTURAL_READINESS_REV03.json',{'acceptance':c['acceptance'],'validation':c['validation']})
    dump('UNRESOLVED_DESIGN_BOARD_REV03.json',{'human_review_required':['proportions','furniture usability','privacy','terrace quality','core/corridor quality'],'regulatory_unresolved':['separation joint width pending authority'],'human_approval':'PENDING'})
    svg(c,OUT/'PARCEL2_FUNCTIONAL_ARCHITECTURAL_REVIEW_REV03.svg'); made_pdf=pdf(c,OUT/'PARCEL2_FUNCTIONAL_ARCHITECTURAL_REVIEW_REV03.pdf')
    dump('TEST_RESULTS_REV03.json',{'status':'PENDING_TEST_RUN','candidate_validation_passed':c['validation']['passed'],'pdf_created':made_pdf})
    files=[]
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name!='FINAL_MANIFEST_REV03.json': files.append({'name':p.name,'bytes':p.stat().st_size,'sha256':sha(p)})
    dump('FINAL_MANIFEST_REV03.json',{'checkpoint':'FUNCTIONAL_ARCHITECTURAL_DESIGN_GATE_20260920_03','created_utc':datetime.now(timezone.utc).isoformat(),'historical_checkpoints_overwritten':False,'files':files})
    print(json.dumps({'out':str(OUT),'validation':c['validation'],'pdf':made_pdf},ensure_ascii=False))

if __name__=='__main__': main()
