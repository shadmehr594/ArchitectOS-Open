from __future__ import annotations

import hashlib, json
from datetime import datetime, timezone
from pathlib import Path


class AppendOnlyHumanLearningRegistry:
    REQUIRED={"human_comment","generalized_rule","scope","provenance","negative_precedent","positive_pattern","regression_test"}
    def __init__(self,path): self.path=Path(path)
    def read(self):
        if not self.path.exists(): return []
        return [json.loads(x) for x in self.path.read_text(encoding="utf-8").splitlines() if x.strip()]
    def append(self,entry):
        missing=self.REQUIRED-set(entry)
        if missing: raise ValueError(f"missing learning fields: {sorted(missing)}")
        previous=self.read(); prior_hash=hashlib.sha256(self.path.read_bytes()).hexdigest() if self.path.exists() else None
        row=dict(entry,created_at=datetime.now(timezone.utc).isoformat(),prior_ledger_sha256=prior_hash)
        with self.path.open("a",encoding="utf-8") as f: f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n")
        assert self.read()[:len(previous)]==previous
        return row
