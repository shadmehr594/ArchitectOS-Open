#!/usr/bin/env python3
"""
ArchitectOS v2.0 Complete Furnished Floor Plan & Multi-Floor CLI (`cli.py`).
Supports natural language Persian prompts or preset scenarios, and saves `.svg`, `.dxf`, and `.json`
while printing exact file paths and audit results.
"""

from __future__ import annotations
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from engine import (
    ArchitecturalPlanSynthesizer,
    export_project_to_dxf,
    export_project_to_json,
    export_project_to_svg,
)

DEFAULT_USER_PROMPT = (
    "60 درصد محل احداث تو شمال با یه حیاط خلوت به عمق 1.7 متر با مساحت 12 متر مربع "
    "برای نورگیری بزاره زمین هم 10*20 سه طرف پلاک هست شمال شرق و غرب پلاک و جنوب کوچه 10 متری"
)


def run_and_save(prompt_text: str, out_dir: pathlib.Path, prefix: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    synth = ArchitecturalPlanSynthesizer()
    project = synth.synthesize_from_text(prompt_text)

    svg_path = (out_dir / f"{prefix}.svg").resolve()
    dxf_path = (out_dir / f"{prefix}.dxf").resolve()
    json_path = (out_dir / f"{prefix}.json").resolve()

    svg_str = export_project_to_svg(project)
    dxf_str = export_project_to_dxf(project)

    svg_path.write_text(svg_str, encoding="utf-8")
    dxf_path.write_text(dxf_str, encoding="utf-8")

    project.saved_files = {
        "svg": str(svg_path),
        "dxf": str(dxf_path),
        "json": str(json_path),
    }
    json_path.write_text(export_project_to_json(project), encoding="utf-8")

    return {
        "project_id": project.project_id,
        "title_fa": project.project_title_fa,
        "prompt": prompt_text,
        "audit_status": project.audit.status.value,
        "checks_passed": project.audit.checks_passed,
        "metrics": project.audit.summary_metrics,
        "saved_files": project.saved_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="ArchitectOS v2 Furnished CAD Plan Synthesizer")
    parser.add_argument("--prompt", type=str, default="", help="Persian natural language architectural prompt")
    parser.add_argument("--out-dir", type=pathlib.Path, default=ROOT / "output_artifacts")
    args = parser.parse_args()

    if args.prompt:
        res = run_and_save(args.prompt, args.out_dir, "custom_prompt_plan")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    prompts = {
        "Plan_10x20_North60_Lightwell12m2": DEFAULT_USER_PROMPT,
        "Plan_Villa_1Floor_10x20": "یک ساختمان یک طبقه ویلایی طراحی کن",
        "Plan_Duplex_120m2_2Floors": "یک ساختمان دوبلکس 120 متری در هر طبقه طراحی کن",
        "Plan_MixedUse_MultiFloor": "یک ساختمان 4 طبقه مختلط تجاری مسکونی با زیرزمین پارکینگ و سطح اشغال متفاوت طراحی کن",
    }
    summary = {}
    for prefix, p_text in prompts.items():
        summary[prefix] = run_and_save(p_text, args.out_dir, prefix)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
