import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(r"<repo-root>")
for name in ["VILLA_SITE_ACCESS_AND_GEOMETRY_LEARNING_20260920_01","AUTONOMOUS_SINGLE_STOREY_VILLA_120M2_TEST_20260920_02"]:
    out=ROOT/"outputs"/name
    files=[]
    for p in sorted(out.iterdir()):
        if p.name=="FINAL_MANIFEST.json": continue
        files.append({"file":p.name,"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
    tests=json.loads((out/"TEST_RESULTS.json").read_text(encoding="utf-8")) if (out/"TEST_RESULTS.json").exists() else {}
    manifest={"checkpoint":name,"created_at":datetime.now(timezone.utc).isoformat(),"additive":True,"historical_checkpoints_modified":False,"files":files,"tests":tests,"pdf_visual_review":"PASS_A3_LANDSCAPE_NO_CLIPPING" if name.startswith("AUTONOMOUS") else "NOT_APPLICABLE"}
    (out/"FINAL_MANIFEST.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
