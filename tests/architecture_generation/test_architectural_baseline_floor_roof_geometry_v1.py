"""ARCHITECTURAL-BASELINE-DESIGN-04 acceptance tests."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest

from core.architecture.contracts.architectural_floor_roof_geometry_v1 import (
    canonical_design_04_document,
    design_04_semantic_hash,
    verify_design_04_candidate,
)
from core.architecture.geometry.architectural_space_boundary_pipeline_v1 import (
    ArchitecturalSpaceBoundaryPipelineV1,
)
from core.architecture.reasoning.architectural_baseline_derived_candidate_refinement_v1 import (
    derive_architectural_candidate_v1,
)
from core.architecture.reasoning.architectural_baseline_opening_privacy_parcel_edge_intelligence_v1 import (
    enrich_opening_privacy_parcel_edge_intelligence_v1,
)
from core.architecture.reasoning import architectural_baseline_floor_roof_geometry_v1 as design_04_module
from core.architecture.reasoning.architectural_baseline_floor_roof_geometry_v1 import (
    Design04GeometryDerivationError,
    derive_architectural_floor_roof_geometry_v1,
)


def _resolved(*, floors=("R1",), envelopes=True):
    wall_faces = {}
    wall_solids = {}
    opening_hosts = {}
    space_boundaries = {}
    nodes = []
    for index, floor in enumerate(floors):
        x = index * 10
        polygon = [[x, 0], [x + 4, 0], [x + 4, 4], [x, 4], [x, 0]]
        space_id = f"SPACE-{floor}"
        face_id = f"FACE-{floor}"
        wall_faces[floor] = {"floor": floor, "faces": [{"face_id": face_id, "start": [x, 0], "end": [x + 4, 0]}]}
        wall_solids[floor] = {
            "floor": floor,
            "solids": [],
            "floor_envelopes": ([{"envelope_id": f"ENV-{floor}", "polygon": polygon}] if envelopes else []),
        }
        opening_hosts[floor] = {
            "floor": floor,
            "openings": ([{
                "opening_id": "D-R1", "kind": "DOOR", "status": "RESOLVED",
                "host_face_a": face_id, "side_a": space_id, "side_b": "EXTERIOR:R1",
            }] if index == 0 else []),
            "unresolved": [],
        }
        space_boundaries[floor] = {
            "floor": floor,
            "spaces": [{
                "space_id": space_id, "semantic_class": "LIVING_RECEPTION",
                "boundary_ids": [face_id], "polygon": polygon,
            }],
            "unresolved": [],
        }
        nodes.append({"id": space_id, "semantic_class": "LIVING_RECEPTION"})
    return {
        "version": ArchitecturalSpaceBoundaryPipelineV1.VERSION,
        "pipeline": "CONTROLLED_DESIGN_04_BASELINE",
        "boundary_extraction": {
            "source_file": "controlled-design-04.dxf", "source_sha256": "4" * 64,
            "tolerance_audit": {"chosen_snap_tolerance_m": 0.001},
            "wall_face_graphs": wall_faces, "wall_solid_graphs": wall_solids,
            "opening_host_graphs": opening_hosts, "space_boundary_graphs": space_boundaries,
            "access_graph": {"nodes": nodes, "edges": [], "status": "RESOLVED"},
            "unresolved": [],
        },
        "semantic_regions": [], "constraints": [],
        "protected_constraints": [{"constraint_id": "PC-D-R1", "entity_id": "D-R1"}],
        "protected_entities": ["D-R1", "FACE-R1"],
        "preservation_requirements": ["PRESERVE_ACCEPTED_GEOMETRY"],
        "architecture_only": True,
    }


def _lineage(resolved=None):
    accepted = ArchitecturalSpaceBoundaryPipelineV1().accept_resolved_baseline(
        _resolved() if resolved is None else resolved,
        candidate_id="ARCH-BASELINE-004", candidate_version="9",
        acceptance_provenance={"status": "ACCEPTED", "evidence_ids": ["acceptance-04"]},
    )
    design_02 = derive_architectural_candidate_v1(
        accepted, derivation_provenance={"decision": "DESIGN_02", "evidence_ids": ["d02"]},
    )
    design_03 = enrich_opening_privacy_parcel_edge_intelligence_v1(
        design_02, enrichment_provenance={"decision": "DESIGN_03", "evidence_ids": ["d03"]},
    )
    return accepted, design_02, design_03


def _evidence(*, floors=("R1",), roof=True, void=None):
    value = {
        "contract": "ApprovedArchitecturalGeometryEvidenceV1", "status": "VERIFIED",
        "levels": [{"floor_id": floor, "order": index} for index, floor in enumerate(floors)],
        "vertical_circulation": [] if void is None else [void],
    }
    if roof:
        value["roof"] = {
            "status": "VERIFIED", "source_floor_id": floors[-1],
            "use_source_floor_envelope": True,
        }
    return value


def _derive(parent=None, evidence=None):
    if parent is None:
        parent = _lineage()[2]
    return derive_architectural_floor_roof_geometry_v1(
        parent, geometry_evidence=evidence,
        derivation_provenance={"decision": "DESIGN_04", "evidence_ids": ["d04"]},
    )


def test_a_valid_single_floor_envelope_is_derived_and_parent_unchanged():
    parent = _lineage()[2]
    before = deepcopy(parent)
    result = _derive(parent, _evidence())
    assert result["floor_geometries"][0]["envelope_ref"] == "ENV-R1"
    assert result["slab_geometries"][0]["structural_sizing_performed"] is False
    assert parent == before


def test_b_multi_floor_identity_order_and_geometry_records_are_unique():
    parent = _lineage(_resolved(floors=("R2", "R1")))[2]
    result = _derive(parent, _evidence(floors=("R1", "R2")))
    assert [item["floor_id"] for item in result["floor_geometries"]] == ["R1", "R2"]
    assert len({item["geometry_id"] for item in result["floor_geometries"]}) == 2
    assert all(item["elevation"] is None for item in result["floor_geometries"])


def test_c_closed_space_boundary_is_safe_second_priority_fallback():
    parent = _lineage(_resolved(envelopes=False))[2]
    result = _derive(parent, _evidence())
    floor = result["floor_geometries"][0]
    assert floor["source_priority"] == 2
    assert floor["source_classification"] == "CANONICAL_ACTIVE_CLOSED_BOUNDARY_FALLBACK"


def test_d_missing_all_safe_floor_evidence_is_structured_failure_without_candidate():
    resolved = _resolved(envelopes=False)
    resolved["boundary_extraction"]["space_boundary_graphs"]["R1"]["spaces"] = []
    parent = _lineage(resolved)[2]
    with pytest.raises(Design04GeometryDerivationError) as caught:
        _derive(parent, _evidence())
    assert caught.value.status == "INSUFFICIENT_FLOOR_EVIDENCE"
    assert caught.value.to_dict()["candidate_committed"] is False


def test_e_verified_top_floor_binding_derives_roof_envelope():
    result = _derive(evidence=_evidence())
    assert result["roof_geometries"][0]["boundary_ref"] == "ENV-R1"
    assert result["roof_geometries"][0]["source_floor_id"] == "R1"


def test_f_absent_roof_type_and_slope_remain_unknown_not_defaulted():
    result = _derive(evidence=_evidence())
    roof = result["roof_geometries"][0]
    assert roof["roof_type"] == "UNKNOWN" and roof["slope"] is None
    assert result["provenance"]["roof_properties_defaulted"] is False


def test_g_roof_terrace_stays_external_and_is_not_enclosed():
    evidence = _evidence()
    evidence["roof"]["terraces"] = [{
        "terrace_id": "T-1", "external": True,
        "polygon": [[0, 0], [2, 0], [2, 1], [0, 1], [0, 0]],
    }]
    terrace = _derive(evidence=evidence)["roof_geometries"][0]["terraces"][0]
    assert terrace["external"] is True and terrace["enclosed_interior"] is False


def test_h_known_stair_void_is_carried_as_open_slab_void():
    void = {
        "id": "STAIR-VOID", "type": "stair", "status": "VERIFIED", "floor_ids": ["R1"],
        "polygon": [[1, 1], [2, 1], [2, 2], [1, 2], [1, 1]],
    }
    result = _derive(evidence=_evidence(void=void))
    assert result["vertical_voids"][0]["status"] == "PRESERVED_OPEN"
    assert result["slab_geometries"][0]["void_refs"] == ["STAIR-VOID"]


def test_i_vertical_record_without_dimensions_is_pending_and_not_guessed():
    void = {"id": "ELEVATOR-VOID", "type": "elevator", "status": "VERIFIED", "floor_ids": ["R1"]}
    result = _derive(evidence=_evidence(void=void))
    assert result["vertical_voids"] == []
    pending = next(item for item in result["unresolved_evidence"] if item["classification"] == "VERTICAL_VOID_GEOMETRY_PENDING")
    assert pending["void_id"] == "ELEVATOR-VOID"


def test_j_protected_void_crossing_floor_boundary_is_transactional_conflict():
    void = {
        "id": "RAMP-VOID", "type": "ramp", "status": "VERIFIED", "floor_ids": ["R1"],
        "polygon": [[3, 1], [5, 1], [5, 2], [3, 2], [3, 1]],
    }
    with pytest.raises(Design04GeometryDerivationError) as caught:
        _derive(evidence=_evidence(void=void))
    assert caught.value.status == "PROTECTED_ZONE_CONFLICT"


def test_k_opening_access_and_boundary_graphs_are_preserved_by_reference_snapshot():
    parent = _lineage()[2]
    result = _derive(parent, _evidence())
    assert result["preserved_graph_refs"]["opening_references"] == parent["opening_references"]
    assert result["preserved_graph_refs"]["access_references"] == parent["access_references"]
    assert result["immutability"]["canonical_wall_opening_access_geometry"] == "PRESERVED_EXACTLY"


def test_l_self_intersecting_envelope_is_rejected_without_repair():
    resolved = _resolved()
    resolved["boundary_extraction"]["wall_solid_graphs"]["R1"]["floor_envelopes"][0]["polygon"] = [
        [0, 0], [4, 4], [0, 4], [4, 0], [0, 0],
    ]
    parent = _lineage(resolved)[2]
    with pytest.raises(Design04GeometryDerivationError) as caught:
        _derive(parent, _evidence())
    assert caught.value.status == "REJECTED_GEOMETRY"
    assert caught.value.conflicts[0]["code"] == "ZERO_AREA_POLYGON" or "INVALID" in caught.value.conflicts[0]["code"]


def test_m_same_input_has_deterministic_identity_hash_and_serialization():
    parent = _lineage()[2]
    first = _derive(parent, _evidence())
    second = _derive(parent, deepcopy(_evidence()))
    assert first == second
    loaded = json.loads(json.dumps(first, ensure_ascii=False, sort_keys=True))
    assert canonical_design_04_document(loaded) == canonical_design_04_document(first)
    assert design_04_semantic_hash(loaded) == first["candidate_hash"]
    assert verify_design_04_candidate(loaded)


def test_n_changed_valid_roof_evidence_changes_identity_version_and_hash():
    first = _derive(evidence=_evidence())
    changed = _evidence()
    changed["roof"]["roof_type"] = "FLAT"
    second = _derive(evidence=changed)
    assert first["candidate_id"] != second["candidate_id"]
    assert first["candidate_version"] != second["candidate_version"]
    assert first["candidate_hash"] != second["candidate_hash"]


def test_o_design03_and_accepted_baseline_stay_unchanged():
    accepted, _, parent = _lineage()
    accepted_before, parent_before = deepcopy(accepted), deepcopy(parent)
    result = _derive(parent, _evidence())
    assert accepted == accepted_before and parent == parent_before
    assert result["lineage"]["design_03_parent_mutated"] is False
    assert result["lineage"]["accepted_baseline_mutated"] is False


def test_p_missing_roof_evidence_returns_floor_candidate_with_warning_not_guess():
    result = _derive(evidence=_evidence(roof=False))
    assert result["derivation_status"] == "DERIVED_WITH_WARNINGS"
    assert result["roof_geometries"] == []
    assert any(item["classification"] == "INSUFFICIENT_ROOF_EVIDENCE" for item in result["unresolved_evidence"])


def test_q_no_structure_bim_ifc_render_chat_or_site_orientation_dependency():
    contract_module = __import__(
        "core.architecture.contracts.architectural_floor_roof_geometry_v1",
        fromlist=["architectural_floor_roof_geometry_v1"],
    )
    imports = []
    for module in (design_04_module, contract_module):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
    document = "\n".join(imports).lower()
    forbidden = ("chat", "llm", "memory", "voice", "provider", "render", "comfyui", ".structure", ".bim", "ifc")
    assert not any(token in document for token in forbidden)
    result = _derive(evidence=_evidence())
    assert result["provenance"]["site_orientation_inferred"] is False
    assert result["side_effects"] == {
        "site": False, "structure": False, "bim": False, "ifc": False,
        "render": False, "chat_intelligence": False,
    }


def test_r_stale_parent_is_rejected_before_geometry_derivation():
    parent = _lineage()[2]
    parent["candidate_version"] = "tampered"
    with pytest.raises(Design04GeometryDerivationError) as caught:
        _derive(parent, _evidence())
    assert caught.value.status == "STALE_PARENT"
