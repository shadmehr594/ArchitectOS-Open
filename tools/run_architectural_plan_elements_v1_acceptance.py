"""Private-image offline acceptance. Does not substitute for real Windows UI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.vision.local_plan_reader_v1 import read_local_plan
from core.vision.image_understanding_v1 import build_understanding
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)
from core.vision.vision_report_v1 import render_vision_report

PROMPT = "خودتو جای یه معمار بزار و این پلان رو آنالیز کن"


def run(image_a, image_b):
    results = {
        "real_ui_response": None,
        "real_ui_status": "not_executed",
        "prompt": PROMPT,
    }
    for name, path in (("A", image_a), ("B", image_b)):
        local = read_local_plan(path)
        raw = {
            "image_type": "floor_plan_or_sketch",
            "confidence": "HIGH",
            "observed": [
                "floor plan",
                "window stairs column duct axis visible",
                "bed sofa table visible",
            ],
            "architectural_elements": ["window", "stairs", "column", "duct", "axis"],
            "furniture_elements": ["bed", "sofa", "table", "wardrobe", "desk"],
            "local_plan_reading": local,
        }
        understanding = build_understanding(
            raw, provider="adversarial-offline-stub", model="stub"
        )
        interpretation = interpret_architectural_vision(understanding, user_text=PROMPT)
        plan = interpretation["plan_reading"]
        results[name] = {
            "local": local,
            "plan": plan,
            "offline_report": render_vision_report(interpretation, "fa"),
        }
    assert results["A"]["plan"]["furniture"] == []
    assert len(results["B"]["plan"]["furniture"]) == 11
    b = results["B"]["plan"]
    items = b["architectural_elements"]
    assert len([e for e in items if e["type"] == "window"]) == 5
    assert len([e for e in items if e["type"] == "stair"]) == 2
    assert all(
        e["attributes"]["step_count"] == 7 for e in items if e["type"] == "stair"
    )
    assert {e["attributes"]["elevation_m"] for e in items if e["type"] == "level"} == {
        0.0,
        1.26,
    }
    assert all(
        "riser_height_m" not in e["attributes"] for e in items if e["type"] == "stair"
    )
    derived = next(
        m for m in b["element_interpretation"] if m["type"] == "derived_stair_riser"
    )
    assert derived["derived_riser_cm"] == 18
    assert derived["provenance"] == "computed_from_grounded_evidence"
    assert derived["association"] == "general_unassigned"
    assert derived["run_id"] is None and derived["assigned_run_ids"] == []
    assert {e["type"] for e in items} >= {"duct", "column", "axis", "door"}
    assert {f["space"] for f in b["inferred_functions"]} == {
        "bedroom",
        "living room",
        "kitchen",
        "bathroom",
        "dining",
    }
    return results


def main():
    fixture = ROOT / "tests/fixtures/vision/furnished_plan_v1"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image-a",
        type=Path,
        default=Path(
            os.environ.get("ARCHITECTOS_PLAN_A", str(fixture / "unfurnished.png"))
        ),
    )
    parser.add_argument(
        "--image-b",
        type=Path,
        default=Path(
            os.environ.get("ARCHITECTOS_PLAN_B", str(fixture / "furnished.jpg"))
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "exports/architectural_plan_elements_v1/acceptance_results.json",
    )
    args = parser.parse_args()
    if not args.image_a.is_file() or not args.image_b.is_file():
        parser.error(
            "Private acceptance inputs required: --image-a/--image-b or ARCHITECTOS_PLAN_A/B"
        )
    results = run(args.image_a, args.image_b)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Offline contrast verified; real UI acceptance remains pending.")
    print(results["B"]["offline_report"])


if __name__ == "__main__":
    main()
