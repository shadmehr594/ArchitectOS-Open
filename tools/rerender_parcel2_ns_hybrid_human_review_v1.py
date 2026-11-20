"""Render frozen NS/HYBRID contracts for human review without design mutation."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PACKAGE = ROOT / "exports" / "DEFAULT" / "architectural_generalization_clean_parcel2_v1_20260911_015101"
SOURCE_REPORT = SOURCE_PACKAGE / "ARCHITECTURAL_GENERALIZATION_AND_CLEAN_PARCEL2_V1.json"
GEOMETRY_KEYS = ("core", "daylight_court", "parking_stalls", "vehicle_circulation_field",
                 "vehicle_entrance", "commercial_viable", "commercial_nonviable_fragments",
                 "residential_unit_envelopes", "zoning_geometry", "terraces", "residual")


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _geometry(candidate):
    return {key: deepcopy(candidate.get(key)) for key in GEOMETRY_KEYS}


def load_frozen_candidates(path=SOURCE_REPORT):
    report=json.loads(Path(path).read_text(encoding="utf-8"))
    by_family={c["topology_family"]:c for c in report["phase_2"]["shortlist"]}
    if set(by_family)!={"NS","HYBRID"}: raise RuntimeError("frozen shortlist is not exactly NS and HYBRID")
    return report, deepcopy(by_family)


def _bounds(candidate):
    points=candidate.get("site_polygon") or [p for key in GEOMETRY_KEYS for shape in ([candidate.get(key)] if key not in ("parking_stalls","commercial_nonviable_fragments","residential_unit_envelopes","terraces") else candidate.get(key) or []) for p in (shape or [])]
    return min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)


def _polygon(points,frame,fill,opacity=.35,stroke="#26364a",dash=None):
    if not points:return ""
    scale,ox,oy=frame; pts=" ".join(f"{ox+x*scale:.2f},{oy-y*scale:.2f}" for x,y in points)
    dashed=f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polygon points="{pts}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="1.3"{dashed}/>'


def _line(points,frame,color="#b43c3c",width=2,dash=None):
    if not points:return ""
    scale,ox,oy=frame; pts=" ".join(f"{ox+x*scale:.2f},{oy-y*scale:.2f}" for x,y in points); d=f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}"{d}/>'


def _commercial_component(candidate):
    return (candidate.get("commercial_evidence",{}).get("components") or [{}])[0]


def _text(x,y,value,size=13,weight="normal",color="#26364a"):
    return f'<text x="{x}" y="{y}" font-family="Arial" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(str(value))}</text>'


def render_candidate_review(candidate):
    x0,y0,x1,y1=_bounds(candidate); scale=min(335/max(x1-x0,1),440/max(y1-y0,1)); ground=(scale,65-x0*scale,520+y0*scale); upper=(scale,465-x0*scale,520+y0*scale)
    body=['<rect width="980" height="700" fill="#fbfcfe"/>',_text(28,32,f'Parcel 2 {candidate["topology_family"]} — frozen human review',21,"bold"),_text(65,58,"GROUND FLOOR",14,"bold"),_text(465,58,"RESIDENTIAL ENVELOPES",14,"bold")]
    site=candidate.get("site_polygon") or []
    for frame in (ground,upper): body.append(_polygon(site,frame,"#f7f8fa",1,"#111b2a"))
    # Ground: decision-review geometry only; no movement/swept line.
    body.append(_polygon(candidate.get("vehicle_circulation_field"),ground,"#91a0af",.42))
    for stall in candidate.get("parking_stalls",[]):body.append(_polygon(stall,ground,"#71a777",.62))
    body.append(_polygon(candidate.get("commercial_viable"),ground,"#f2b84b",.58))
    component=_commercial_component(candidate); body.append(_polygon(component.get("usable_rectangle"),ground,"none",0,"#d47700","6 3"))
    body.append(_line(candidate.get("vehicle_entrance"),ground,"#286aa6",4))
    body.append(_polygon(candidate.get("core"),ground,"#62518f",.72))
    for fragment in candidate.get("commercial_nonviable_fragments",[]):body.append(_polygon(fragment,ground,"#cc6a6a",.35))
    body.append(_polygon(candidate.get("residual"),ground,"#c9cdd2",.22,"#7c8793","3 3"))
    # Upper: only contract-produced envelopes and zoning.
    for i,unit in enumerate(candidate.get("residential_unit_envelopes",[])):body.append(_polygon(unit,upper,"#e79a77" if i==0 else "#d98dab",.30))
    colors={"PUBLIC":"#efb44d","PRIVATE":"#b987c7","SERVICE":"#7e9bb3","TRANSITION":"#8b98a6"}
    for zone,shapes in candidate.get("zoning_geometry",{}).items():
        for shape in shapes:body.append(_polygon(shape,upper,colors.get(zone,"#aab1ba"),.34))
    body.append(_polygon(candidate.get("core"),upper,"#62518f",.72));body.append(_polygon(candidate.get("daylight_court"),upper,"#61c6df",.52))
    for terrace in candidate.get("terraces",[]):body.append(_polygon(terrace,upper,"#55aa67",.65))
    body.append(_polygon(candidate.get("residual"),upper,"#c9cdd2",.22,"#7c8793","3 3"))
    ped=candidate.get("brain",{}).get("reasoner_evidence",{}).get("pedestrian",{}); mode=ped.get("mode","not recorded")
    missing=[]
    for name,key in (("stair","stair"),("elevator","elevator"),("lobby","lobby"),("pedestrian entrance","pedestrian_entrance"),("pedestrian path","pedestrian_path"),("service/common polygon","service_common_zones")):
        if not candidate.get(key):missing.append(name)
    legend=["parking stalls","full vehicle circulation field","commercial viable polygon","largest usable commercial rectangle (dashed)","commercial frontage: south/public edge","lobby/core: aggregate core polygon only",f"pedestrian mode: {mode}","upper: unit envelopes + contract zoning + daylight court + terraces","residual/nonviable: grey/red"]
    for i,item in enumerate(legend):body.append(_text(28,570+i*17,item,12))
    body.append(_text(510,570,"NOT PRESENT AS SEPARATE GEOMETRY IN CONTRACT:",12,"bold","#9d3434"));body.append(_text(510,589,", ".join(missing) if missing else "none",11,"normal","#9d3434"))
    body.append(_text(510,612,"Core continuity shown by identical frozen core polygon on both panels.",11))
    body.append(_text(510,631,"Vehicle movement and swept-path lines intentionally omitted.",11))
    body.append(_text(510,650,"No rooms, windows, regenerated geometry, or selected winner.",11,"bold"))
    return '<svg xmlns="http://www.w3.org/2000/svg" width="980" height="700">'+''.join(body)+'</svg>'


def render_comparison(candidates):
    body=['<rect width="1100" height="430" fill="#fbfcfe"/>',_text(24,34,"Parcel 2 NS / HYBRID — frozen human-review comparison",22,"bold")]
    columns=[("metric",24),("NS",375),("HYBRID",715)];
    for label,x in columns:body.append(_text(x,75,label,15,"bold"))
    metrics=[]
    for label,fn in (("commercial area",lambda c:round(__import__('shapely').geometry.Polygon(c["commercial_viable"]).area,3) if c.get("commercial_viable") else 0),
                     ("commercial frontage",lambda c:round(c["decision_metrics"]["commercial_viability"]["frontage"],3)),
                     ("parking count",lambda c:c["decision_metrics"]["parking_count"]),
                     ("pedestrian mode",lambda c:c["brain"]["reasoner_evidence"]["pedestrian"]["mode"]),
                     ("daylight",lambda c:c["decision_metrics"]["daylight_resolution"]),
                     ("terrace satisfied",lambda c:c["decision_metrics"]["terrace_satisfaction"]),
                     ("hard failures",lambda c:", ".join(x["code"] for x in c["decision_metrics"]["critic_failures"] if x.get("severity")=="hard") or "none")):
        metrics.append((label,fn(candidates["NS"]),fn(candidates["HYBRID"])))
    for i,(label,ns,hybrid) in enumerate(metrics):
        y=112+i*42;body.append(f'<rect x="18" y="{y-23}" width="1060" height="34" fill="{"#eef2f6" if i%2==0 else "#f8f9fb"}"/>');body.extend((_text(24,y,label,13,"bold"),_text(375,y,str(ns)[:42],12),_text(715,y,str(hybrid)[:42],12)))
    body.extend((_text(24,402,"winner = null",13,"bold"),_text(375,402,"final_selection_performed = false",13,"bold"),_text(715,402,"Geometry is frozen; comparison is review-only.",13,"bold")))
    return '<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="430">'+''.join(body)+'</svg>'


def render_vehicle_diagnostic(candidates):
    body=['<rect width="1000" height="590" fill="#fbfcfe"/>',_text(24,32,"DIAGNOSTIC ONLY — vehicle validation overlays do not shape architecture",20,"bold","#9d3434")]
    for index,family in enumerate(("NS","HYBRID")):
        c=candidates[family];x0,y0,x1,y1=_bounds(c);scale=min(360/max(x1-x0,1),450/max(y1-y0,1));frame=(scale,65+index*480-x0*scale,530+y0*scale)
        body.append(_polygon(c.get("site_polygon"),frame,"#f7f8fa",1));body.append(_polygon(c.get("vehicle_circulation_field"),frame,"#91a0af",.42))
        for stall in c.get("parking_stalls",[]):body.append(_polygon(stall,frame,"#71a777",.55))
        body.append(_line(c.get("swept_validation_overlay"),frame,"#d33e3e",2,"7 4"));body.append(_text(65+index*480,62,family,14,"bold"))
    return '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="590">'+''.join(body)+'</svg>'


def build_audit(report,candidates,before,after,outputs):
    source=json.loads(Path(report["source_contract"]).read_text(encoding="utf-8"));parking=source["requirements"]["parking"]
    invariant={family:{"before":before[family],"after":after[family],"unchanged":before[family]==after[family],"stored_candidate_fingerprint":candidates[family].get("geometry_fingerprint")} for family in candidates}
    passed=all(x["unchanged"] for x in invariant.values())
    return {"contract":"Parcel2FrozenCandidateRerenderAuditV1","source_package":str(SOURCE_PACKAGE),"source_report":str(SOURCE_REPORT),
            "parking_requirement_trace":{"source_contract":report["source_contract"],"requirements_source":source["requirements"].get("source"),"evidence_status":source["requirements"].get("evidence_status"),"minimum_count":parking["minimum_count"],"mapping":"parking.minimum_count -> parking_required_count -> generated stall count","value_changed":False},
            "candidate_ids":[candidates[x]["candidate_id"] for x in ("NS","HYBRID")],"geometry_fingerprint_audit":invariant,"geometry_invariance_passed":passed,
            "output_manifest":outputs,"winner":None,"final_selection_performed":False,"room_layout_generated":False,"final_windows_generated":False,
            "structure_executed":False,"bim_executed":False,"ifc_executed":False,"render_pipeline_executed":False}


def main(output_root=None):
    report,candidates=load_frozen_candidates();before={k:_digest(_geometry(v)) for k,v in candidates.items()}
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S");out=Path(output_root) if output_root else ROOT/"exports"/"DEFAULT"/f"parcel2_frozen_ns_hybrid_review_v1_{stamp}";out.mkdir(parents=True,exist_ok=False)
    files={"comparison":"PARCEL2_NS_HYBRID_HUMAN_REVIEW_COMPARISON.svg","NS":"PARCEL2_NS_HUMAN_REVIEW.svg","HYBRID":"PARCEL2_HYBRID_HUMAN_REVIEW.svg","vehicle_diagnostic":"DIAGNOSTIC_VEHICLE_VALIDATION.svg","audit":"PARCEL2_NS_HYBRID_VISUALIZATION_AUDIT.json"}
    (out/files["comparison"]).write_text(render_comparison(candidates),encoding="utf-8")
    for family in ("NS","HYBRID"):(out/files[family]).write_text(render_candidate_review(candidates[family]),encoding="utf-8")
    (out/files["vehicle_diagnostic"]).write_text(render_vehicle_diagnostic(candidates),encoding="utf-8")
    after={k:_digest(_geometry(v)) for k,v in candidates.items()};audit=build_audit(report,candidates,before,after,list(files.values()))
    if not audit["geometry_invariance_passed"]:raise RuntimeError("FAIL: visualization mutated candidate geometry")
    (out/files["audit"]).write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"output":str(out),"geometry_invariance_passed":True,"winner":None,"file_count":len(files)},ensure_ascii=False))


if __name__=="__main__":main()
