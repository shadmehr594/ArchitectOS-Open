"""One architecture-only diagnostic run on frozen Parcel 2/V8."""
from __future__ import annotations

import hashlib
import html
import json
import sys
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.architecture.reasoning.architectural_geometric_intervention_reasoning_v2 import ArchitecturalGeometricInterventionReasoningV2

V6 = ROOT / "exports/DEFAULT/parcel2_h1_circulation_core_topology_v6_20260912_210133"
V7 = ROOT / "exports/DEFAULT/parcel2_h1_human_architectural_quality_review_v7_20260912_211316"
V8 = ROOT / "exports/DEFAULT/parcel2_h1_upper_floor_design_around_current_core_v8_20260912_212949"
V9 = ROOT / "exports/DEFAULT/parcel2_h1_residential_corridor_entrance_geometry_v9_20260913_000244"
V8_JSON = V8 / "PARCEL2_H1_UPPER_FLOOR_DESIGN_AROUND_CURRENT_CORE_V8.json"
EVIDENCE = ROOT / "core/architecture/contracts/architectural_geometric_intervention_precedent_v2.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(folder):
    return {p.name: {"sha256": sha(p), "size_bytes": p.stat().st_size} for p in sorted(folder.iterdir()) if p.is_file()}


def polygons(value):
    if not value:
        return []
    return [value] if isinstance(value[0][0], (int, float)) else value


def transform(boundary):
    xs = [p[0] for p in boundary]; ys = [p[1] for p in boundary]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    scale = min(650/max(x1-x0, .001), 760/max(y1-y0, .001))
    return lambda p: (55+(p[0]-x0)*scale, 870-(55+(p[1]-y0)*scale))


def poly(points, tr, fill, stroke, opacity, dash=""):
    coords = " ".join(f"{tr(p)[0]:.1f},{tr(p)[1]:.1f}" for p in points)
    return f'<polygon points="{coords}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="2" {dash}/>'


def render(item):
    floor = item["source_floor"]; result = item["diagnostic"]; boundary = floor["floor_boundary"]; tr = transform(boundary)
    base = [poly(boundary, tr, "#ffffff", "#0f172a", .95)]
    palette = ["#dbeafe", "#dcfce7", "#fce7f3"]
    for i, unit in enumerate(floor["units"]):
        base.append(poly(unit["boundary"], tr, palette[i % len(palette)], "#334155", .55))
    base.append(poly(floor["core_boundary_unchanged"], tr, "#e9d5ff", "#6b21a8", .75))
    for corridor in polygons(floor.get("public_corridor", [])):
        base.append(poly(corridor, tr, "#fef3c7", "#a16207", .75))
    colors = ["#2563eb", "#059669", "#dc2626", "#7c3aed", "#ea580c", "#0891b2"]
    overlays = []
    cards = []
    for i, hypothesis in enumerate(result["intervention_hypotheses"]):
        color = colors[i % len(colors)]
        for shape in polygons(hypothesis["review_geometry"]):
            overlays.append(poly(shape, tr, color, color, .12, 'stroke-dasharray="8 5"'))
        y = 145+i*78
        cards.append(f'<rect x="755" y="{y-25}" width="805" height="66" fill="white" stroke="{color}"/><text x="773" y="{y}" class="h">{html.escape(hypothesis["hypothesis_id"])} · {html.escape(hypothesis["intervention_scope"])} · gate {str(hypothesis["justification_gate_passed"]).lower()}</text><text x="773" y="{y+23}" class="t">problems: {html.escape(", ".join(hypothesis["addressed_problem_ids"])[:105])}</text>')
    problems = ", ".join(p["problem_id"] for p in result["spatial_problems"]) or "none at envelope/distribution resolution"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="940"><defs><style>.h{{font:700 13px Arial}}.t{{font:12px Arial}}</style></defs><rect width="100%" height="100%" fill="#f8fafc"/><text x="40" y="36" font-family="Arial" font-size="21" font-weight="bold">Architectural Geometric Intervention · {html.escape(item["topology_id"])} · {html.escape(item["floor_id"])}</text><text x="40" y="64" class="t">BASE: solid filled plan/core/corridor · INTERVENTION: transparent dashed delta · V8 frozen · no winner</text><text x="40" y="90" class="t">Detected problems: {html.escape(problems[:175])}</text>{''.join(base)}{''.join(overlays)}<rect x="740" y="105" width="835" height="780" fill="none" stroke="#94a3b8"/>{''.join(cards)}<text x="760" y="915" class="t">Diagnostic geometry only; no final rooms, dimensions, structure, BIM, IFC or render.</text></svg>'''


def build(output):
    frozen = {"v6": V6, "v7": V7, "v8": V8, "v9": V9}
    before = {key: inventory(folder) for key, folder in frozen.items()}
    source = json.loads(V8_JSON.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    engine = ArchitecturalGeometricInterventionReasoningV2()
    evaluations = []
    for topology in source["core_hypotheses"]:
        for floor in topology["floors"]:
            spaces = [{"id": u["unit_id"], "use": "unit_shape", "boundary": u["boundary"], "doors": [u["entrance"]], "privacy": "private"} for u in floor["units"]]
            spaces.append({"id": "CORE", "use": "core", "boundary": floor["core_boundary_unchanged"], "privacy": "neutral"})
            connections = [["CORE", u["unit_id"]] for u in floor["units"]]
            boundary = floor["floor_boundary"]
            diagnostic = engine.analyze(plan_boundary=boundary, spaces=spaces, connections=connections,
                                        exterior_edges=[[boundary[i], boundary[(i+1) % len(boundary)]] for i in range(len(boundary))],
                                        entrances=[u["entrance"] for u in floor["units"]], max_hypotheses=8)
            evaluations.append({"topology_id": topology["topology_id"], "floor_id": floor["floor_id"],
                                "resolution": "envelope_and_distribution_only", "source_floor": floor, "diagnostic": diagnostic})
    report = {
        "contract": "Parcel2ArchitecturalGeometricInterventionDiagnosticV2",
        "run_count": 1, "scope": "architecture_only", "source_checkpoint": "V8",
        "limitations": ["room_level_program_absent_in_V8", "hypotheses_are_not_final_geometry", "no_winner"],
        "lineage": {"v8_json_sha256": sha(V8_JSON), "frozen_inventories_before": before},
        "precedent_evidence": {"path": str(EVIDENCE), "sha256": sha(EVIDENCE), "authority_class": evidence["authority_class"], "used_as_regulation": False},
        "evaluations": evaluations,
        "selection": {"winner": None, "authoritative_ranking": False, "final_selection_performed": False},
        "prohibited_workflows_executed": {"H2": False, "elevator_traffic": False, "structure": False, "BIM": False, "IFC": False, "render": False, "image_generation": False},
    }
    output.mkdir(parents=True, exist_ok=False)
    artifacts = []
    json_path = output / "PARCEL2_ARCHITECTURAL_GEOMETRIC_INTERVENTION_DIAGNOSTIC_V2.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    artifacts.append(json_path)
    for item in evaluations:
        svg_path = output / f'{item["topology_id"]}-{item["floor_id"]}-GEOMETRIC-INTERVENTION.svg'
        svg_path.write_text(render(item), encoding="utf-8"); ET.parse(svg_path); artifacts.append(svg_path)
    after = {key: inventory(folder) for key, folder in frozen.items()}
    assert before == after
    manifest_path = output / "ARTIFACT_MANIFEST.json"
    manifest = {"contract": "Parcel2ArchitecturalGeometricInterventionDiagnosticV2Manifest",
                "artifacts": [{"file": p.name, "sha256": sha(p), "size_bytes": p.stat().st_size} for p in sorted(artifacts)],
                "frozen_inventories_before": before, "frozen_inventories_after": after, "source_immutable": True,
                "selection": report["selection"]}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    destination = ROOT / "exports/DEFAULT" / f"parcel2_architectural_geometric_intervention_diagnostic_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(build(destination))
