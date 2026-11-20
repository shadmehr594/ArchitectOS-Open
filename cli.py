"""
ArchitectOS v3.0 — CLI Entrypoint for Parametric Architectural Synthesis
Usage:
    python3 cli.py --prompt "زمین 10 در 20 سه طبقه روی پیلوت با آشپزخانه اپن و جزیره و مطبخ" --out-dir ./output
"""
import argparse
import os
from engine import (
    ParametricArchitecturalSynthesizer,
    export_project_to_svg,
    export_project_to_dxf,
    export_project_to_json,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="ArchitectOS Parametric Multi-Floor Engine v3.0")
    parser.add_argument(
        "--prompt",
        type=str,
        default=(
            "زمین 10*20 سه طرف پلاک شمال شرق و غرب و جنوب کوچه 10 متری، "
            "60 درصد محل احداث تو شمال با حیاط خلوت به عمق 1.7 متر با مساحت 12 متر مربع، "
            "ساختمان 2 طبقه روی پیلوت با آسانسور و آشپزخانه اپن و جزیره و مطبخ"
        ),
    )
    parser.add_argument("--out-dir", type=str, default="/tmp/architectos_plan_output")
    parser.add_argument("--prefix", type=str, default="Plan_V3_MultiFloor_10x20_AllFloors")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    synth = ParametricArchitecturalSynthesizer()
    project = synth.synthesize_from_text(args.prompt)

    svg_path = os.path.join(args.out_dir, f"{args.prefix}.svg")
    dxf_path = os.path.join(args.out_dir, f"{args.prefix}.dxf")
    json_path = os.path.join(args.out_dir, f"{args.prefix}.json")

    export_project_to_svg(project, svg_path)
    export_project_to_dxf(project, dxf_path)
    export_project_to_json(project, json_path)

    print(f"[ArchitectOS v3.0] Successfully synthesized: {project.project_title_fa}")
    print(f"  -> SVG : {os.path.abspath(svg_path)}")
    print(f"  -> DXF : {os.path.abspath(dxf_path)}")
    print(f"  -> JSON: {os.path.abspath(json_path)}")


if __name__ == "__main__":
    main()
