"""Offline real A/B acceptance; no live provider, render or design calls."""
from __future__ import annotations

import argparse
import os
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.vision.local_plan_reader_v1 import read_local_plan
from core.vision.image_understanding_v1 import build_understanding
from core.vision.architectural_vision_interpreter_v1 import interpret_architectural_vision
from core.vision.vision_report_v1 import render_vision_report


def run(image_a, image_b):
    results = {}
    for name, path in (("A", image_a), ("B", image_b)):
        local = read_local_plan(path)
        raw = {"image_type": "floor_plan_or_sketch", "confidence": "HIGH",
               "observed": ["floor plan", "bed sofa table wardrobe visible"],
               "furniture_elements": ["bed", "sofa", "table", "wardrobe", "desk"],
               "local_plan_reading": local}
        understanding = build_understanding(raw, provider="adversarial-offline-stub", model="stub")
        interpretation = interpret_architectural_vision(understanding)
        plan = interpretation["plan_reading"]
        results[name] = {
            "image": path.name, "local_status": local["status"], "ocr_status": local.get("ocr_status"),
            "local_labels": local["labels"], "local_openings": local["openings"],
            "rejected_symbol_ocr_labels": local.get("rejected_symbol_ocr_labels", []),
            "furniture_observed": plan["furniture_observed"],
            "furniture_classes": [item["class"] for item in plan["furniture"]],
            "furniture_evidence": plan["furniture"], "functions": plan["inferred_functions"],
            "enclosure_geometry": plan["enclosure_geometry"],
            "report": render_vision_report(interpretation, "fa")}
    assert results["A"]["furniture_evidence"] == []
    classes = set(results["B"]["furniture_classes"])
    assert {"bed", "sofa", "chair", "dining_surface", "sanitary_fixture",
            "kitchen_counter", "kitchen_sink_arrangement"} <= classes
    assert "storage_cabinet" not in classes
    assert {f["space"] for f in results["B"]["functions"]} >= {
        "bedroom", "living room", "kitchen", "bathroom", "dining"}
    assert results["B"]["enclosure_geometry"]["multiple_spaces"]
    assert results["B"]["enclosure_geometry"]["count"] is None
    return results


def main():
    fixture = ROOT / "tests" / "fixtures" / "vision" / "furnished_plan_v1"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-a", type=Path, default=Path(os.environ.get("ARCHITECTOS_PLAN_A", str(fixture / "unfurnished.png"))))
    parser.add_argument("--image-b", type=Path, default=Path(os.environ.get("ARCHITECTOS_PLAN_B", str(fixture / "furnished.jpg"))))
    parser.add_argument("--output", type=Path, default=ROOT / "exports" / "furnished_plan_visual_understanding_v1" / "acceptance_results.json")
    args = parser.parse_args()
    if not args.image_a.is_file() or not args.image_b.is_file():
        parser.error("Acceptance images are private; supply --image-a and --image-b, or ARCHITECTOS_PLAN_A/B")
    results = run(args.image_a, args.image_b)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("A/B contrast PASS: A=0; B=%d grounded items; five supported functions." % len(results["B"]["furniture_evidence"]))
    print(results["B"]["report"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
