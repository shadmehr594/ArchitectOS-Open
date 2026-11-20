"""ARCHITECTURAL-DESIGN-VISUAL-VALIDATION-01 acceptance tests.

Read-only visual inspection of the current architectural design chain.  Proves
the artifact is a pure, deterministic projection: no geometry invention, no
source mutation, no BIM/IFC/render, no structural engine execution.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from core.architecture.contracts.architectural_visual_validation_v1 import (
    CONTRACT,
    STYLE_TOKENS,
    VALIDATION_LAYERS,
    VERSION,
    canonical_visual_validation_document,
    verify_visual_validation_artifact,
    visual_validation_semantic_hash,
)
from core.architecture.geometry.architectural_space_boundary_pipeline_v1 import (
    ArchitecturalSpaceBoundaryPipelineV1,
)
from core.architecture.reasoning.architectural_baseline_derived_candidate_refinement_v1 import (
    derive_architectural_candidate_v1,
)
from core.architecture.reasoning.architectural_baseline_floor_roof_geometry_v1 import (
    derive_architectural_floor_roof_geometry_v1,
)
from core.architecture.reasoning.architectural_baseline_opening_privacy_parcel_edge_intelligence_v1 import (
    enrich_opening_privacy_parcel_edge_intelligence_v1,
)
from core.architecture.reasoning.architectural_baseline_structural_readiness_v1 import (
    analyze_architectural_structural_readiness_v1,
)
from core.architecture.reasoning.architectural_design_visual_validation_v1 import (
    VIEW_LAYERS,
    ArchitecturalDesignVisualValidationV1,
    build_architectural_visual_validation,
)
from core.structure.structural_support_candidate_analysis_v1 import (
    analyze_structural_support_candidates_v1,
)


ROOT = Path(__file__).resolve().parents[2]

# Upstream frozen modules this phase must never modify.
FROZEN_UPSTREAM_HASHES = {
    "core/architecture/contracts/architectural_floor_roof_geometry_v1.py":
        "04edb851a56bd12bd859b48b8aacc84ec4141d8baa3c066260965020ea467329",
    "core/architecture/reasoning/architectural_baseline_floor_roof_geometry_v1.py":
        "c1316dbff842103a2453eb51ff76c48dcdea0cd9b6fc20b907ae1b3c28e16eb6",
    "core/architecture/contracts/architectural_structural_readiness_v1.py":
        "e0702cef93e89fb72b8074e7a549ac0bf119f6e8c225f47ed0320b03985ea772",
    "core/architecture/reasoning/architectural_baseline_structural_readiness_v1.py":
        "15996aeb9ed981d1604016d1453e14d72a6ebaf48b01798a30e1493475abb75f",
    "core/structure/structural_architecture_input_adapter_v1.py":
        "7397e9c9aa1b1ceb3af1869b0b0d18eaa0c0499165da6919265e5da57208aa60",
    "core/structure/structural_support_candidate_analysis_v1.py":
        "ed66c3e8d0869c2c9533bad48fa735bc9c4b52c8db7c9716fe1a5d9aa1bc1936",
    "core/structure/structural_grid_engine.py":
        "886d0d1cba71f211c503e4eea532b677396a331abf6565a8f018fa863dd12263",
    "core/structure/structural_element_engine.py":
        "935f9bd4e047f7c9e339a81ba016bb3455db8d1b725e14d837da9f1e7d39a950",
    "core/structure/architecture_structure_handoff_v1.py":
        "3f146069d91b51a2c681edd889e985bf22cb1ddc6df28177ae277c48812587a3",
}

RECT_10x12 = [[0, 0], [10, 0], [10, 12], [0, 12], [0, 0]]
L_SHAPE = [[0, 0], [10, 0], [10, 6], [4, 6], [4, 12], [0, 12], [0, 0]]
STAIR_VOID = {"id": "STAIR-1", "type": "stair", "status": "VERIFIED", "floor_ids": ["R1"],
              "polygon": [[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]}


# ==========================================================
# CONTROLLED CHAIN FIXTURE (real Design-02 → Design-05 + Synthesis-01)
# ==========================================================

def _resolved(polygons, external=False):
    faces, solids, hosts, spaces, nodes, edges = {}, {}, {}, {}, [], []
    for floor, polygon in polygons.items():
        space_id, face_id = f"SPACE-{floor}", f"FACE-{floor}"
        faces[floor] = {"floor": floor, "faces": [
            {"face_id": face_id, "start": polygon[0], "end": polygon[1]}]}
        solids[floor] = {"floor": floor, "solids": [], "floor_envelopes": [
            {"envelope_id": f"ENV-{floor}", "polygon": polygon}]}
        hosts[floor] = {"floor": floor, "unresolved": [], "openings": [{
            "opening_id": f"D-{floor}", "kind": "DOOR", "status": "RESOLVED",
            "host_face_a": face_id, "side_a": space_id, "side_b": f"EXTERIOR:{floor}"}]}
        spaces[floor] = {"floor": floor, "unresolved": [], "spaces": [{
            "space_id": space_id,
            "semantic_class": "EXTERNAL_TERRACE" if external else "LIVING_RECEPTION",
            "external": external, "boundary_ids": [face_id], "polygon": polygon}]}
        nodes.extend([
            {"id": space_id, "semantic_class": "EXTERNAL" if external else "LIVING_RECEPTION"},
            {"id": f"EXTERIOR:{floor}", "semantic_class": "EXTERIOR"},
        ])
        edges.append({"id": f"D-{floor}", "from": space_id, "to": f"EXTERIOR:{floor}",
                      "kind": "DOOR_ACCESS"})
    return {
        "version": ArchitecturalSpaceBoundaryPipelineV1.VERSION,
        "pipeline": "CONTROLLED_VISUAL_VALIDATION_01",
        "boundary_extraction": {
            "source_file": "controlled-visual-01.dxf", "source_sha256": "5" * 64,
            "tolerance_audit": {"chosen_snap_tolerance_m": 0.001},
            "wall_face_graphs": faces, "wall_solid_graphs": solids,
            "opening_host_graphs": hosts, "space_boundary_graphs": spaces,
            "access_graph": {"nodes": nodes, "edges": edges, "status": "RESOLVED"},
            "unresolved": [],
        },
        "semantic_regions": [], "constraints": [],
        "protected_constraints": [{"constraint_id": "PC-D-R1", "entity_id": "D-R1"}],
        "protected_entities": ["D-R1", "FACE-R1"],
        "preservation_requirements": ["PRESERVE_ACCEPTED_GEOMETRY"],
        "architecture_only": True,
    }


def _chain(polygons=None, *, void=None, external=False, readiness_evidence=None):
    polygons = polygons or {"R1": RECT_10x12}
    floors = list(polygons.keys())

    accepted = ArchitecturalSpaceBoundaryPipelineV1().accept_resolved_baseline(
        _resolved(polygons, external=external), candidate_id="ARCH-BASELINE-VIS01",
        candidate_version="10",
        acceptance_provenance={"status": "ACCEPTED", "evidence_ids": ["vis-01"]})
    design_02 = derive_architectural_candidate_v1(
        accepted, derivation_provenance={"decision": "DESIGN_02", "evidence_ids": ["d02"]})
    design_03 = enrich_opening_privacy_parcel_edge_intelligence_v1(
        design_02, enrichment_provenance={"decision": "DESIGN_03", "evidence_ids": ["d03"]})

    evidence = {
        "contract": "ApprovedArchitecturalGeometryEvidenceV1", "status": "VERIFIED",
        "levels": [{"floor_id": floor, "order": index, "elevation": index * 3.2}
                   for index, floor in enumerate(floors)],
        "vertical_circulation": [] if void is None else [void],
        "roof": {"status": "VERIFIED", "source_floor_id": floors[-1],
                 "use_source_floor_envelope": True},
    }
    if external:
        evidence["roof"]["terraces"] = [{
            "terrace_id": "T-1", "external": True,
            "polygon": [[0, 0], [2, 0], [2, 1], [0, 1], [0, 0]]}]

    design_04 = derive_architectural_floor_roof_geometry_v1(
        design_03, geometry_evidence=evidence,
        derivation_provenance={"decision": "DESIGN_04", "evidence_ids": ["d04"]})
    design_05 = analyze_architectural_structural_readiness_v1(
        design_04, readiness_evidence=readiness_evidence,
        analysis_provenance={"decision": "DESIGN_05", "evidence_ids": ["d05"]})
    support = analyze_structural_support_candidates_v1(design_05)

    return {
        "accepted_baseline": accepted, "design_02": design_02, "design_03": design_03,
        "design_04": design_04, "design_05": design_05, "support_analysis": support,
    }


def _artifact(**kwargs):
    return build_architectural_visual_validation(_chain(**kwargs))


def _verified(**collections):
    return {"contract": "ApprovedArchitecturalStructuralReadinessEvidenceV1",
            "status": "VERIFIED", **collections}


def _inside(polygon, point):
    from shapely.geometry import Point, Polygon

    return Polygon(polygon).contains(Point(point[0], point[1]))


# ==========================================================
# 1. contract creation / serialization / round-trip
# ==========================================================

def test_contract_creation_and_round_trip():
    artifact = _artifact()
    assert artifact["contract"] == CONTRACT
    assert artifact["version"] == VERSION
    assert artifact["artifact_kind"] == "READ_ONLY_INSPECTION_OUTPUT"
    assert artifact["validation_layers"] == list(VALIDATION_LAYERS)
    assert artifact["floor_artifacts"]

    payload = json.loads(json.dumps(artifact, ensure_ascii=False))
    assert payload == artifact
    assert verify_visual_validation_artifact(artifact) is True
    assert canonical_visual_validation_document(artifact)


def test_contract_rejects_tampered_artifact():
    artifact = _artifact()
    tampered = deepcopy(artifact)
    tampered["floor_artifacts"][0]["geometry_checks"]["envelope_area_m2"] = 999.0
    assert verify_visual_validation_artifact(tampered) is False


# ==========================================================
# 2 / J. deterministic artifact hash
# ==========================================================

def test_deterministic_artifact_hash_and_svg():
    first = _artifact()
    second = _artifact()
    assert first["artifact_hash"] == second["artifact_hash"]
    assert len(first["artifact_hash"]) == 64
    assert first["artifact_hash"] == visual_validation_semantic_hash(first)
    for left, right in zip(first["floor_artifacts"], second["floor_artifacts"]):
        assert left["svg"] == right["svg"]
        assert left["svg_sha256"] == right["svg_sha256"]


def test_changed_geometry_changes_the_hash():
    assert _artifact()["artifact_hash"] != _artifact(polygons={"R1": L_SHAPE})["artifact_hash"]


def test_svg_is_well_formed_and_styles_are_fixed():
    artifact = _artifact(polygons={"R1": RECT_10x12, "R2": L_SHAPE})
    for floor in artifact["floor_artifacts"]:
        ET.fromstring(floor["svg"])
        for view in VALIDATION_LAYERS:
            ET.fromstring(floor["view_svgs"][view])
        assert floor["svg"].startswith("<svg ")
    for token, style in STYLE_TOKENS.items():
        assert style["stroke"].startswith("#"), token


# ==========================================================
# 3 / 18. no mutation of any source
# ==========================================================

def test_no_source_mutation():
    chain = _chain(void=STAIR_VOID)
    snapshots = deepcopy(chain)
    artifact = build_architectural_visual_validation(chain)

    assert chain == snapshots, "no source candidate may be mutated"
    assert artifact["provenance"]["source_mutated"] is False
    assert artifact["visualization_policy"]["inspection_output_only"] is True
    for key in ("geometry_invented", "geometry_smoothed", "geometry_snapped",
                "geometry_repaired", "envelope_enlarged", "missing_polygons_inferred",
                "automatic_merge", "layout_beautification", "random_colour_used",
                "runtime_theme_used"):
        assert artifact["visualization_policy"][key] is False, key


# ==========================================================
# 4 / A. 10×12 exact envelope visualisation
# ==========================================================

def test_ten_by_twelve_envelope_is_exact():
    artifact = _artifact()
    floor = artifact["floor_artifacts"][0]
    checks = floor["geometry_checks"]

    envelope = floor["layers"]["floor_envelope"][0]
    assert envelope["style_token"] == "FLOOR_ENVELOPE"
    assert envelope["coordinates"] == [[0.0, 0.0], [10.0, 0.0], [10.0, 12.0], [0.0, 12.0], [0.0, 0.0]]
    assert checks["envelope_bounds"]["width"] == pytest.approx(10.0)
    assert checks["envelope_bounds"]["depth"] == pytest.approx(12.0)
    assert checks["envelope_area_m2"] == pytest.approx(120.0)
    assert checks["envelope_matches_source"] is True
    assert checks["rectangularisation_detected"] is False
    assert (checks["envelope_bounds"]["width"], checks["envelope_bounds"]["depth"]) != (8.0, 12.0)


# ==========================================================
# 5 / B. L-shape preserved
# ==========================================================

def test_l_shape_is_not_rectangularised():
    artifact = _artifact(polygons={"R1": L_SHAPE})
    floor = artifact["floor_artifacts"][0]
    checks = floor["geometry_checks"]

    assert floor["layers"]["floor_envelope"][0]["coordinates"] == [
        [0.0, 0.0], [10.0, 0.0], [10.0, 6.0], [4.0, 6.0], [4.0, 12.0], [0.0, 12.0], [0.0, 0.0]]
    assert len(floor["layers"]["floor_envelope"][0]["coordinates"]) == 7
    assert checks["envelope_area_m2"] == pytest.approx(84.0)
    assert checks["bounding_box_area_m2"] == pytest.approx(120.0)
    assert checks["envelope_area_m2"] != pytest.approx(checks["bounding_box_area_m2"])
    assert checks["rectangularisation_detected"] is False


# ==========================================================
# 6 / C. void + protected zone rendering
# ==========================================================

def test_void_and_protected_zone_are_rendered_as_exclusions():
    artifact = _artifact(void=STAIR_VOID)
    floor = artifact["floor_artifacts"][0]
    checks = floor["geometry_checks"]

    assert checks["vertical_void_count"] == 1
    assert checks["protected_zone_count"] == 1
    assert checks["exclusion_region_count"] == 1

    void = floor["layers"]["vertical_voids"][0]
    assert void["style_token"] == "VERTICAL_VOID"
    assert void["coordinates"] == STAIR_VOID["polygon"]
    assert void["source_record_id"] == "STAIR-1"
    assert "layer-vertical_voids" in floor["view_svgs"]["VOIDS_PROTECTED_ZONES"]

    protected = floor["layers"]["protected_zones"][0]
    assert protected["style_token"] == "PROTECTED_ZONE"
    assert protected["coordinates"] == STAIR_VOID["polygon"]


# ==========================================================
# 7 / D. support candidates never inside exclusions
# ==========================================================

def test_support_candidates_are_never_inside_protected_voids():
    artifact = _artifact(void=STAIR_VOID)
    floor = artifact["floor_artifacts"][0]
    assert floor["geometry_checks"]["support_candidates_inside_exclusions"] == 0
    assert floor["layers"]["support_candidates"], "candidates required"

    exclusion = STAIR_VOID["polygon"]
    for record in floor["layers"]["support_candidates"]:
        assert not _inside(exclusion, record["coordinates"]), record


def test_support_candidates_avoid_opening_clearance_regions():
    evidence = _verified(opening_clearances=[{
        "constraint_id": "D-R1-CLEAR", "opening_id": "D-R1", "floor_id": "R1",
        "status": "VERIFIED", "polygon": [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]}])
    artifact = _artifact(readiness_evidence=evidence)
    floor = artifact["floor_artifacts"][0]
    assert floor["geometry_checks"]["support_candidates_inside_exclusions"] == 0
    for record in floor["layers"]["support_candidates"]:
        assert not _inside([[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]], record["coordinates"])


# ==========================================================
# 8 / I. rejected regions distinguishable
# ==========================================================

def test_rejected_support_regions_are_recorded_and_distinguishable():
    evidence = _verified(opening_clearances=[{
        "constraint_id": "D-R1-CLEAR", "opening_id": "D-R1", "floor_id": "R1",
        "status": "VERIFIED", "polygon": [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]}])
    artifact = _artifact(readiness_evidence=evidence)
    floor = artifact["floor_artifacts"][0]

    rejected = floor["layers"]["rejected_support_regions"]
    assert rejected, "rejected regions must be recorded"
    assert floor["geometry_checks"]["rejected_support_region_count"] == len(rejected)

    candidate_tokens = {item["style_token"] for item in floor["layers"]["support_candidates"]}
    rejected_tokens = {item["style_token"] for item in rejected}
    assert rejected_tokens == {"REJECTED_SUPPORT_REGION"}
    assert not (rejected_tokens & candidate_tokens)
    assert rejected[0]["committed"] is False
    # a rejected corner is either strictly inside a proven exclusion or falls
    # outside the eligible region once the exclusion has been cut out
    assert rejected[0]["reason"] in (
        "INSIDE_PROVEN_EXCLUSION", "OUTSIDE_ELIGIBLE_SUPPORT_REGION")
    assert rejected[0]["excluded_by"] in ("D-R1-CLEAR", None)


# ==========================================================
# 9 / F. external spaces remain external
# ==========================================================

def test_external_spaces_remain_external():
    artifact = _artifact(external=True)
    floor = artifact["floor_artifacts"][0]
    external = floor["layers"]["external_spaces"]
    assert external, "external space layer must not be empty"
    assert all(item["style_token"] == "EXTERNAL_SPACE" for item in external)
    assert floor["geometry_checks"]["external_space_count"] == len(external)
    for record in floor["layers"]["support_candidates"]:
        assert not _inside([[0, 0], [2, 0], [2, 1], [0, 1], [0, 0]], record["coordinates"])


# ==========================================================
# 10 / G. multi-floor deterministic ordering
# ==========================================================

def test_multi_floor_is_separate_and_deterministically_ordered():
    polygons = {"R1": RECT_10x12, "R2": [[0, 0], [8, 0], [8, 10], [0, 10], [0, 0]]}
    artifact = _artifact(polygons=polygons)
    floors = artifact["floor_artifacts"]

    assert [floor["floor_id"] for floor in floors] == ["R1", "R2"]
    assert [floor["floor_order"] for floor in floors] == [0, 1]
    assert floors[0]["svg"] != floors[1]["svg"]
    assert [floor["geometry_checks"]["envelope_area_m2"] for floor in floors] == [
        pytest.approx(120.0), pytest.approx(80.0)]
    assert artifact["summary"]["floor_count"] == 2
    assert artifact["summary"]["total_floor_area_m2"] == pytest.approx(200.0)

    again = _artifact(polygons=polygons)
    assert [floor["floor_id"] for floor in again["floor_artifacts"]] == ["R1", "R2"]
    assert again["artifact_hash"] == artifact["artifact_hash"]


# ==========================================================
# 11 / H. unresolved roof evidence → warning, no invented geometry
# ==========================================================

def test_unresolved_roof_evidence_is_a_warning_not_invented_geometry():
    artifact = _artifact()
    assert artifact["artifact_status"] == "READY_WITH_UNRESOLVED"
    warning = next(item for item in artifact["warnings"] if item["code"] == "ROOF_EVIDENCE_UNRESOLVED")
    assert warning["roof_geometry_invented"] is False
    assert warning["roof_type"] == "UNKNOWN"
    assert warning["slope"] is None
    # no roof layer is fabricated for the plan views
    for floor in artifact["floor_artifacts"]:
        assert "roof" not in floor["layers"]


# ==========================================================
# 12. opening / access displayed read-only
# ==========================================================

def test_opening_and_access_layers_are_read_only_projections():
    chain = _chain()
    artifact = build_architectural_visual_validation(chain)
    floor = artifact["floor_artifacts"][0]

    opening = floor["layers"]["openings"][0]
    assert opening["style_token"] == "OPENING"
    assert opening["coordinates"] == [chain["accepted_baseline"]["boundary_extraction"][
        "wall_face_graphs"]["R1"]["faces"][0]["start"],
        chain["accepted_baseline"]["boundary_extraction"]["wall_face_graphs"]["R1"]["faces"][0]["end"]]
    assert opening["kind"] == "DOOR"
    assert opening["provenance"]["geometry_invented"] is False

    access = floor["layers"]["access"][0]
    assert access["geometry_type"] == "RELATION_MARKER"
    assert access["coordinates"] == []
    assert access["representable"] is False
    assert access["from_node"] == "SPACE-R1"


def test_missing_boundary_source_is_structured_unresolved_evidence():
    chain = _chain()
    artifact = build_architectural_visual_validation({"design_04": chain["design_04"]})
    codes = {item["code"] for item in artifact["unresolved_visual_evidence"]}
    assert "CANONICAL_BOUNDARY_EXTRACTION_NOT_SUPPLIED" in codes
    assert "DESIGN_05_READINESS_NOT_SUPPLIED" in codes
    assert "SUPPORT_CANDIDATE_ANALYSIS_NOT_SUPPLIED" in codes
    assert artifact["artifact_status"] == "READY_WITH_UNRESOLVED"
    # nothing was invented to fill the gap
    assert artifact["floor_artifacts"][0]["layers"]["spaces"] == []


def test_no_floor_geometry_is_insufficient_visual_source():
    assert build_architectural_visual_validation(
        {"design_04": {"floor_geometries": []}})["artifact_status"] == "INSUFFICIENT_VISUAL_SOURCE"
    assert build_architectural_visual_validation("not-a-chain")["artifact_status"] == "FAILED"


# ==========================================================
# 13 / 14. compile, import, forbidden dependency scan
# ==========================================================

def test_new_modules_have_no_forbidden_dependency():
    forbidden = (
        "import requests", "from requests", "import comfy", "from comfy",
        "import subprocess", "from subprocess", "ifcopenshell", "ezdxf",
        "render_runtime", "comfyui", "openai", "anthropic", "diffusers",
        "structural_grid_engine import", "structural_element_engine import",
        "full_bim_pipeline",
    )
    for relative in (
        "core/architecture/contracts/architectural_visual_validation_v1.py",
        "core/architecture/reasoning/architectural_design_visual_validation_v1.py",
    ):
        lines = [
            line.strip() for line in (ROOT / relative).read_text(encoding="utf-8").splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        joined = "\n".join(lines)
        for token in forbidden:
            assert token not in joined, f"{relative}: {token}"


# ==========================================================
# 15. frozen upstream module hashes
# ==========================================================

@pytest.mark.parametrize("relative", sorted(FROZEN_UPSTREAM_HASHES))
def test_frozen_upstream_modules_are_byte_identical(relative):
    digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    assert digest == FROZEN_UPSTREAM_HASHES[relative], relative


# ==========================================================
# 16 / 17. no BIM / IFC / render / structural engine execution
# ==========================================================

def test_no_render_bim_ifc_or_structural_engine_execution():
    artifact = _artifact()
    provenance = artifact["provenance"]
    for key in ("render_runtime_executed", "comfyui_executed", "bim_ifc_executed",
                "image_generation_executed", "structural_engine_executed"):
        assert provenance[key] is False, key


def test_artifact_commits_no_structural_elements():
    artifact = _artifact()
    for floor in artifact["floor_artifacts"]:
        assert floor["support_summary"]["committed_columns"] == []
        assert floor["support_summary"]["committed_beams"] == []
    for record in artifact["floor_artifacts"][0]["layers"]["support_candidates"]:
        assert record["committed"] is False
        assert record["is_column"] is False


# ==========================================================
# OPTIONAL SUMMARY PANEL
# ==========================================================

def test_summary_panel_counts_are_derived_not_fabricated():
    artifact = _artifact(void=STAIR_VOID)
    summary = artifact["summary"]
    floor = artifact["floor_artifacts"][0]
    checks = floor["geometry_checks"]

    assert summary["space_count"] == checks["space_count"]
    assert summary["opening_count"] == checks["opening_count"]
    assert summary["protected_zone_count"] == checks["protected_zone_count"]
    assert summary["support_candidate_count"] == checks["support_candidate_count"]
    assert summary["rejected_region_count"] == checks["rejected_support_region_count"]
    assert summary["floors"][0]["area_m2"] == checks["envelope_area_m2"]
    assert summary["unresolved_count"] == len(artifact["unresolved_visual_evidence"])


def test_required_views_are_all_present_per_floor():
    artifact = _artifact()
    for floor in artifact["floor_artifacts"]:
        assert set(floor["views"]) == set(VALIDATION_LAYERS)
        assert set(floor["view_svgs"]) == set(VALIDATION_LAYERS)
        for view, layers in VIEW_LAYERS.items():
            assert floor["views"][view] == list(layers)
        assert floor["view_svgs"]["ARCHITECTURAL_PLAN"].count("<svg") == 1
