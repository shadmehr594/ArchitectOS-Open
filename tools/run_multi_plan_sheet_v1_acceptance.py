"""Private A/B/C/D offline acceptance; never a substitute for Windows UI."""

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.vision.local_plan_reader_v1 import read_local_plan
from core.vision.image_understanding_v1 import build_understanding
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)
from core.vision.vision_report_v1 import render_vision_report

PROMPT = "خودتو جای یه معمار بزار و این پلان رو آنالیز کن"


def run(paths):
    result = {
        "prompt": PROMPT,
        "real_ui_status": "not_executed",
        "real_ui_response": None,
        "full_pass": False,
        "acceptance_gaps": [
            "D individual furniture/fixture classes and supported function recall remain incomplete",
            "D elevator/shaft identity remains unconfirmed",
            "D exact column inventory and title transcription remain incomplete",
            "real Windows UI acceptance required",
        ],
    }
    for name, path in paths.items():
        local = read_local_plan(path)
        raw = {
            "image_type": "floor_plan_or_sketch",
            "confidence": "HIGH",
            "observed": [
                "floor plan",
                "bed sofa table stairs elevator windows column visible",
            ],
            "furniture_elements": ["bed", "sofa", "table"],
            "architectural_elements": [
                "stairs",
                "elevator",
                "windows",
                "column",
                "axis",
            ],
            "local_plan_reading": local,
        }
        u = build_understanding(raw, provider="adversarial-offline-stub", model="stub")
        v = interpret_architectural_vision(u, user_text=PROMPT)
        plan = v["plan_reading"]
        result[name] = {
            "local": local,
            "plan": plan,
            "offline_report": render_vision_report(v, "fa"),
            "summary": {
                "sheet_type": local["sheet_structure"]["sheet_type"],
                "panel_count": len(local["sheet_structure"]["panels"]),
                "furniture_count": len(plan.get("furniture", [])),
                "opening_counts": {
                    o["kind"]: o["instance_count"] for o in plan.get("openings", [])
                },
                "elements": dict(
                    Counter(e["type"] for e in plan.get("architectural_elements", []))
                ),
            },
        }
    assert all(result[k]["summary"]["panel_count"] == 1 for k in "ABC")
    assert result["A"]["plan"]["furniture"] == []
    assert len(result["B"]["plan"]["furniture"]) == 11
    assert result["D"]["summary"]["panel_count"] == 2
    assert result["D"]["plan"]["fusion"]["status"] == "corresponding_pair"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in "ABCD":
        parser.add_argument(
            "--image-" + key.lower(),
            type=Path,
            default=os.environ.get("ARCHITECTOS_PLAN_" + key),
        )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    paths = {k: getattr(args, "image_" + k.lower()) for k in "ABCD"}
    if not all(p and p.is_file() for p in paths.values()):
        parser.error(
            "All four real private image inputs are required; no synthetic substitution."
        )
    result = run(paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: result[k]["summary"] for k in "ABCD"}, ensure_ascii=False))
    print(result["D"]["offline_report"])
    print("FULL PASS withheld: explicit recall gaps and Windows UI acceptance remain.")


if __name__ == "__main__":
    main()
