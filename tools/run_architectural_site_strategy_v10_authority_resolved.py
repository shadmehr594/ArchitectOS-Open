from __future__ import annotations

import json
import sys
from datetime import datetime
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "architecture" / "reasoning"))
from architectural_site_strategy_v10 import ArchitecturalSiteStrategyV10, poly

EXCLUDED = ["H2", "ELEVATOR_TRAFFIC", "STRUCTURE", "BIM", "IFC", "RENDER", "IMAGE_GENERATION"]


def _parcel2():
    site = {
        "parcel_polygon": [[0, 0], [20, 0], [20, 10], [0, 10]],
        "buildable_zone": [[0, 0], [20, 0], [20, 10], [0, 10]],
        "placement_mode": "FULL_DERIVED_100_PERCENT",
        "coverage_source": "CURRENT_PROJECT_REQUIREMENT",
        "edge_evidence": [
            {"edge_index": 1, "relation": "STREET", "vehicle_suitability": "SUITABLE", "pedestrian_suitability": "SUITABLE", "noise_exposure": "HIGH", "provenance": "PARCEL2_PROJECT_CONTEXT"},
            {"edge_index": 0, "relation": "PARTY_WALL", "provenance": "PARCEL2_PROJECT_CONTEXT"},
            {"edge_index": 2, "relation": "PARTY_WALL", "privacy_quietness": "QUIET", "provenance": "PARCEL2_PROJECT_CONTEXT"},
            {"edge_index": 3, "relation": "PARTY_WALL", "provenance": "PARCEL2_PROJECT_CONTEXT"}
        ],
        "provenance": "PARCEL2_CURRENT_CONTEXT"
    }
    program = {
        "ground_commercial_frontage_important": True,
        "vehicle_access_from_street": True,
        "parking_required": True,
        "upper_unit_count": 2,
        "upper_program_options": ["RF2", "RF1"],
        "stair_required": True,
        "elevator_required": True,
        "residential_floor_count": 2,
        "provenance": "USER_CONFIRMED_PROGRAM_AND_PROJECT_LEVEL_CONTRACT"
    }
    return site, program


def _svg(result, strategy):
    pts = result["buildable_zone"]
    x_values = [p[0] for p in pts]
    y_values = [p[1] for p in pts]
    x0, x1, y0, y1 = min(x_values), max(x_values), min(y_values), max(y_values)
    scale, pad = 35, 45
    width, height = (x1 - x0) * scale + 2 * pad, (y1 - y0) * scale + 2 * pad

    def points(poly):
        return " ".join(f"{pad + (x-x0)*scale:.1f},{height-pad-(y-y0)*scale:.1f}" for x, y in poly)

    core = next(x for x in result["core_candidate_zones"] if x["candidate_id"] == strategy["core_candidate_id"])
    lightwell = next(x for x in result["lightwell_candidate_zones"] if x["candidate_id"] == strategy["lightwell_candidate_id"])
    lw = f'<polygon points="{points(lightwell["polygon"])}" fill="#8ed1c6" stroke="#157a6e" stroke-width="2"/>' if lightwell.get("polygon") else ""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">
<rect width="100%" height="100%" fill="#f7f4ed"/>
<polygon points="{points(pts)}" fill="#fff" stroke="#242424" stroke-width="3"/>
{lw}
<polygon points="{points(core["polygon"])}" fill="#e88f70" stroke="#963f29" stroke-width="2"/>
<text x="{pad}" y="24" font-family="Arial" font-size="15">{strategy["strategy_id"]}</text>
<text x="{pad}" y="{height-12:.0f}" font-family="Arial" font-size="13">coral=core | teal=shared lightwell | candidate only | no winner</text>
</svg>'''


def main(out_root):
    authority_path = ROOT / "core" / "architecture" / "contracts" / "parcel2_minab_lightwell_window_authority_profile_v10_1.json"
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    site, program = _parcel2()
    engine = ArchitecturalSiteStrategyV10()
    result = engine.analyze(site, program, authority["resolved_engine_profile"])
    # V10 intentionally caps its normal handoff list at four.  For this authority
    # re-evaluation, exercise every generic core family without changing V10.
    all_strategies = []
    for core in result["core_candidate_zones"]:
        all_strategies.extend(engine._hypotheses(
            poly(result["buildable_zone"]),
            result["edge_metadata"],
            [core],
            result["lightwell_candidate_zones"],
            result["site_coverage_strategy"]["ratio"],
            program,
            result["jurisdiction_authority"]
        ))
    result["strategy_candidates"] = all_strategies
    feasible = [x for x in result["strategy_candidates"] if x["hard_feasible"]]
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(out_root) / f"parcel2_site_strategy_joint_topology_v10_authority_resolved_{now}"
    out.mkdir(parents=True)
    topology = {
        "contract": "JointBuildingTopologyV10AuthorityResolved",
        "scope": "ARCHITECTURE_ONLY",
        "source_engine_contract": result["contract"],
        "authority_profile_id": authority["profile_id"],
        "candidates": result["strategy_candidates"],
        "hard_feasible_candidates": feasible,
        "room_packing_handoff": {"status": "READY_FOR_ROOM_PACKING" if feasible else "ROOM_PACKING_BLOCKED", "blocker_layer": None if feasible else "SITE_STRATEGY", "validators_not_relaxed": True},
        "software_acceptance": {"status": "PASS", "meaning": "V10_CONTRACT_AND_AUTHORITY_GATES_EXECUTED"},
        "human_architectural_acceptance": {"status": "PENDING_HUMAN_REVIEW", "independent": True},
        "authoritative_winner": None,
        "ranking_performed": False
    }
    payload = {
        "contract": "ArchitecturalSiteStrategyV10AuthorityResolvedRun",
        "scope": "ARCHITECTURE_ONLY",
        "excluded": EXCLUDED,
        "authority_profile": authority,
        "site_strategy": result,
        "render_executed": False,
        "reviewable_svg_generated": bool(feasible),
        "image_generation_executed": False,
        "authoritative_winner": None
    }
    outputs = {
        "AUTHORITY_PROFILE_V10_1.json": authority,
        "ARCHITECTURAL_SITE_STRATEGY_V10_AUTHORITY_RESOLVED.json": payload,
        "JOINT_BUILDING_TOPOLOGY_V10_AUTHORITY_RESOLVED.json": topology
    }
    for name, data in outputs.items():
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if feasible:
        for i, strategy in enumerate(feasible, 1):
            (out / f"SITE_STRATEGY_CANDIDATE_{i:02d}.svg").write_text(_svg(result, strategy), encoding="utf-8")
    entries = []
    for path in sorted(out.iterdir()):
        entries.append({"file": path.name, "size": path.stat().st_size, "sha256": sha256(path.read_bytes()).hexdigest()})
    manifest = {"contract": "ArtifactManifestV10AuthorityResolved", "created_at": datetime.now().astimezone().isoformat(), "scope": "ARCHITECTURE_ONLY", "excluded": EXCLUDED, "entries": entries}
    (out / "ARTIFACT_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
