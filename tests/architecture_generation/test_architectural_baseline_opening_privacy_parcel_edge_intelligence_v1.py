"""ARCHITECTURAL-BASELINE-DESIGN-03 acceptance tests."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path

from core.architecture.contracts.architectural_opening_privacy_parcel_edge_intelligence_v1 import (
    canonical_design_03_document,
    design_03_semantic_hash,
    verify_design_03_candidate,
)
from core.architecture.geometry.architectural_space_boundary_pipeline_v1 import (
    ArchitecturalSpaceBoundaryPipelineV1,
)
from core.architecture.reasoning import (
    architectural_baseline_opening_privacy_parcel_edge_intelligence_v1 as design_03_module,
)
from core.architecture.reasoning.architectural_baseline_derived_candidate_refinement_v1 import (
    derive_architectural_candidate_v1,
)
from core.architecture.reasoning.architectural_baseline_opening_privacy_parcel_edge_intelligence_v1 import (
    enrich_opening_privacy_parcel_edge_intelligence_v1,
)


def _resolved_baseline():
    spaces = [
        {"space_id": "BED-1", "semantic_class": "BEDROOM_SINGLE", "boundary_ids": ["FACE-BED"], "polygon": [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]},
        {"space_id": "BATH-1", "semantic_class": "FAMILY_BATHROOM", "boundary_ids": ["FACE-BATH"], "polygon": [[2, 0], [3, 0], [3, 2], [2, 2], [2, 0]]},
        {"space_id": "LIVING-1", "semantic_class": "LIVING_RECEPTION", "boundary_ids": ["FACE-LIVING"], "polygon": [[0, 2], [3, 2], [3, 4], [0, 4], [0, 2]]},
        {"space_id": "UNKNOWN-1", "boundary_ids": ["FACE-UNKNOWN"], "polygon": [[3, 0], [4, 0], [4, 2], [3, 2], [3, 0]]},
    ]
    openings = [
        {"opening_id": "W-BED", "kind": "WINDOW", "status": "RESOLVED", "host_face_a": "FACE-BED", "side_a": "BED-1", "side_b": "EXTERIOR:R1"},
        {"opening_id": "D-IN", "kind": "DOOR", "status": "RESOLVED", "host_wall_solid_id": "WALL-IN", "side_a": "BED-1", "side_b": "LIVING-1"},
        {"opening_id": "W-BATH", "kind": "WINDOW", "status": "RESOLVED", "host_face_a": "FACE-BATH", "side_a": "BATH-1", "side_b": "EXTERIOR:R1"},
        {"opening_id": "W-UNKNOWN", "kind": "WINDOW", "status": "RESOLVED", "host_face_a": "FACE-UNKNOWN", "side_a": "UNKNOWN-1", "side_b": "EXTERIOR:R1"},
        {"opening_id": "W-NOHOST", "kind": "WINDOW", "status": "UNRESOLVED", "side_a": "BED-1", "side_b": "EXTERIOR:R1"},
    ]
    return {
        "version": ArchitecturalSpaceBoundaryPipelineV1.VERSION,
        "pipeline": "CONTROLLED_DESIGN_03_BASELINE",
        "boundary_extraction": {
            "source_file": "controlled-design-03.dxf",
            "source_sha256": "3" * 64,
            "wall_face_graphs": {"R1": {"floor": "R1", "faces": [
                {"face_id": value, "start": [index, 0], "end": [index + 1, 0]}
                for index, value in enumerate(("FACE-BED", "FACE-BATH", "FACE-LIVING", "FACE-UNKNOWN"))
            ]}},
            "wall_solid_graphs": {"R1": {"floor": "R1", "solids": [
                {"wall_solid_id": "WALL-IN", "polygon": [[0, 2], [3, 2], [3, 2.2], [0, 2.2], [0, 2]]}
            ], "floor_envelopes": [{"envelope_id": "ENV-1", "polygon": [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]}]}},
            "opening_host_graphs": {"R1": {"floor": "R1", "openings": openings, "unresolved": [{"opening_id": "W-NOHOST"}]}},
            "space_boundary_graphs": {"R1": {"floor": "R1", "spaces": spaces, "unresolved": []}},
            "access_graph": {
                "nodes": [
                    {"id": "BED-1", "semantic_class": "BEDROOM_SINGLE"},
                    {"id": "BATH-1", "semantic_class": "FAMILY_BATHROOM"},
                    {"id": "LIVING-1", "semantic_class": "LIVING_RECEPTION"},
                    {"id": "UNKNOWN-1"},
                    {"id": "EXTERIOR:R1", "semantic_class": "EXTERIOR"},
                ],
                "edges": [{"edge_id": "D-IN", "from": "BED-1", "to": "LIVING-1", "kind": "DOOR_PORTAL"}],
                "status": "RESOLVED",
            },
            "unresolved": [{"opening_id": "W-NOHOST", "code": "host_missing"}],
        },
        "semantic_regions": [],
        "constraints": [{"constraint_id": "HC-1", "entity_id": "BED-1"}],
        "protected_constraints": [{"constraint_id": "PC-OPEN", "entity_id": "W-BED"}],
        "protected_entities": ["BED-1", "W-BED", "FACE-BED"],
        "preservation_requirements": ["PRESERVE_ACCEPTED_GEOMETRY"],
        "architecture_only": True,
    }


def _accepted():
    return ArchitecturalSpaceBoundaryPipelineV1().accept_resolved_baseline(
        _resolved_baseline(),
        candidate_id="ARCH-BASELINE-003",
        candidate_version="8",
        acceptance_provenance={"status": "ACCEPTED", "authority": "controlled_design_03_acceptance", "evidence_ids": ["acceptance-03"]},
    )


def _design_02(accepted=None):
    return derive_architectural_candidate_v1(
        _accepted() if accepted is None else accepted,
        derivation_provenance={"decision": "DESIGN_02_DERIVATION", "evidence_ids": ["design-02-frozen"]},
    )


def _site():
    return {
        "contract": "CanonicalParcelSiteEvidenceV1",
        "status": "VERIFIED",
        "parcel_id": 2,
        "parcel_edges": [
            {"edge_id": "EDGE-ROAD", "relation": "road", "confirmed": True, "road_width": 10.0},
            {"edge_id": "EDGE-NEIGHBOR", "relation": "neighbor_parcel", "confirmed": True, "parcel_id": 29},
        ],
        "boundary_edge_bindings": [
            {"boundary_ref": "FACE-BED", "parcel_edge_ref": "EDGE-NEIGHBOR", "status": "VERIFIED"},
            {"boundary_ref": "FACE-BATH", "parcel_edge_ref": "EDGE-ROAD", "status": "VERIFIED"},
        ],
    }


def _enrich(parent=None, site=None):
    return enrich_opening_privacy_parcel_edge_intelligence_v1(
        _design_02() if parent is None else parent,
        site_evidence=site,
        enrichment_provenance={"decision": "DESIGN_03_INTELLIGENCE", "evidence_ids": ["design-03-review"]},
    )


def _by_id(records, key, value):
    return next(item for item in records if item.get(key) == value)


def test_a_existing_exterior_window_is_classified_without_geometry_mutation():
    result = _enrich(site=_site())
    opening = _by_id(result["opening_intelligence"], "opening_id", "W-BED")
    assert opening["opening_type"] == "window"
    assert opening["host_relation"] == "EXTERIOR"
    assert opening["host_refs"] == ["FACE-BED"]
    assert opening["geometry_mutated"] is False
    assert opening["daylight_view_opportunity"] == "EXTERIOR_OPPORTUNITY_NO_PERFORMANCE_CLAIM"
    assert result["provenance"]["daylight_performance_claimed"] is False


def test_b_internal_door_connecting_two_spaces_has_verified_access_role():
    result = _enrich()
    opening = _by_id(result["opening_intelligence"], "opening_id", "D-IN")
    assert opening["host_relation"] == "INTERIOR"
    assert opening["connected_spaces"] == ["BED-1", "LIVING-1"]
    assert opening["access_role"] == "VERIFIED_ACCESS_CONNECTION"


def test_c_unresolved_host_is_structured_and_never_guessed():
    result = _enrich()
    opening = _by_id(result["opening_intelligence"], "opening_id", "W-NOHOST")
    assert opening["status"] == "OPENING_HOST_UNRESOLVED"
    assert opening["host_refs"] == []
    assert any(item["classification"] == "OPENING_HOST_UNRESOLVED" and item["opening_id"] == "W-NOHOST" for item in result["unresolved_evidence"])


def test_d_private_bedroom_exterior_opening_without_site_evidence_is_partial_not_neighbor_facing():
    result = _enrich()
    privacy = _by_id(result["privacy_assessments"], "opening_id", "W-BED")
    assert privacy["privacy_class"] == "PRIVATE"
    assert privacy["status"] == "PRIVACY_RISK_IDENTIFIED"
    assert "BEDROOM_EXPOSURE" in privacy["privacy_risks"]
    assert "NEIGHBOR_FACING_EXPOSURE" not in privacy["privacy_risks"]
    assert "opening_parcel_edge_relation_unresolved" in privacy["unresolved_evidence"]


def test_e_verified_neighbor_edge_produces_evidence_bound_neighbor_exposure():
    result = _enrich(site=_site())
    relation = _by_id(result["opening_parcel_relations"], "opening_id", "W-BED")
    privacy = _by_id(result["privacy_assessments"], "opening_id", "W-BED")
    assert relation["relation_type"] == "NEIGHBOR_EDGE"
    assert relation["neighbor_parcel_id"] == 29
    assert "NEIGHBOR_FACING_EXPOSURE" in privacy["privacy_risks"]
    assert any(ref["source_class"] == "SITE_EVIDENCE" for ref in privacy["evidence_refs"])


def test_f_verified_road_edge_has_no_compass_or_front_yard_inference():
    result = _enrich(site=_site())
    relation = _by_id(result["opening_parcel_relations"], "opening_id", "W-BATH")
    assert relation["relation_type"] == "ROAD_EDGE"
    assert relation["orientation_inferred"] is False
    document = json.dumps(relation).lower()
    assert not any(token in document for token in ("north", "south", "east", "west", "front_yard", "rear", "side_yard"))


def test_g_bathroom_exterior_opening_is_assessed_conservatively():
    result = _enrich(site=_site())
    privacy = _by_id(result["privacy_assessments"], "opening_id", "W-BATH")
    assert privacy["privacy_class"] == "PRIVATE"
    assert "BATHROOM_EXPOSURE" in privacy["privacy_risks"]
    assert privacy["direct_view_risk"] == "POTENTIAL_NOT_GEOMETRICALLY_VERIFIED"


def test_h_missing_semantic_identity_stays_unknown_without_room_role_assumption():
    result = _enrich(site=_site())
    privacy = _by_id(result["privacy_assessments"], "opening_id", "W-UNKNOWN")
    assert privacy["privacy_class"] == "UNKNOWN"
    assert privacy["privacy_risks"] == []
    assert "canonical_room_semantic_identity_or_ontology_entry_missing" in privacy["unresolved_evidence"]


def test_i_protected_opening_and_boundary_constraints_carry_forward_unchanged():
    parent = _design_02()
    result = _enrich(parent, _site())
    opening = _by_id(result["opening_intelligence"], "opening_id", "W-BED")
    assert result["constraints"] == parent["constraints"]
    assert opening["protected_constraint_refs"] == ["FACE-BED", "W-BED"]


def test_j_neighbor_parcel_identifier_type_and_value_are_preserved_exactly():
    result = _enrich(site=_site())
    edge = _by_id(result["parcel_edge_relations"], "parcel_edge_ref", "EDGE-NEIGHBOR")
    assert edge["neighbor_parcel_id"] == 29
    assert isinstance(edge["neighbor_parcel_id"], int)


def test_k_site_orientation_is_never_inferred_when_unavailable():
    result = _enrich(site=_site())
    assert result["provenance"]["site_orientation_inferred"] is False
    assert result["provenance"]["front_rear_side_inferred"] is False
    assert all(item["orientation"] is None for item in result["parcel_edge_relations"])


def test_l_same_input_is_deterministic_and_round_trip_hash_verifies():
    first = _enrich(site=_site())
    second = _enrich(site=deepcopy(_site()))
    assert first == second
    assert first["candidate_hash"] == second["candidate_hash"]
    loaded = json.loads(json.dumps(first, ensure_ascii=False, sort_keys=True))
    assert canonical_design_03_document(loaded) == canonical_design_03_document(first)
    assert design_03_semantic_hash(loaded) == first["candidate_hash"]
    assert verify_design_03_candidate(loaded)


def test_m_changed_verified_evidence_changes_identity_version_and_hash():
    first = _enrich(site=_site())
    changed = _site()
    changed["parcel_edges"][1]["parcel_id"] = 3
    second = _enrich(site=changed)
    assert first["candidate_id"] != second["candidate_id"]
    assert first["candidate_version"] != second["candidate_version"]
    assert first["candidate_hash"] != second["candidate_hash"]


def test_n_design_02_parent_and_accepted_baseline_remain_unchanged():
    accepted = _accepted()
    accepted_before = deepcopy(accepted)
    parent = _design_02(accepted)
    parent_before = deepcopy(parent)
    result = _enrich(parent, _site())
    assert parent == parent_before
    assert accepted == accepted_before
    assert result["boundary_extraction"] == parent["boundary_extraction"] == accepted["boundary_extraction"]
    assert result["lineage"]["design_02_parent_mutated"] is False
    assert result["lineage"]["accepted_parent_mutated"] is False


def test_o_site_evidence_gate_allows_partial_opening_and_privacy_results():
    result = _enrich()
    assert result["opening_intelligence"]
    assert result["privacy_assessments"]
    assert result["parcel_edge_relations"] == []
    assert result["design_04_readiness"]["parcel_edge_intelligence"] == "INSUFFICIENT_SITE_EVIDENCE"
    assert any(item["classification"] == "PARCEL_EDGE_ANALYSIS_PENDING" for item in result["unresolved_evidence"])


def test_p_design_03_has_no_forbidden_structure_bim_ifc_render_or_chat_dependency():
    contract_module = __import__(
        "core.architecture.contracts.architectural_opening_privacy_parcel_edge_intelligence_v1",
        fromlist=["architectural_opening_privacy_parcel_edge_intelligence_v1"],
    )
    imports = []
    for module in (design_03_module, contract_module):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
    document = "\n".join(imports).lower()
    forbidden = ("chat", "llm", "memory", "voice", "provider", "render", "comfyui", ".structure", ".bim", "ifc")
    assert not any(token in document for token in forbidden)


def test_q_unverified_site_records_are_rejected_without_fabricated_edges():
    site = _site()
    site["status"] = "DRAFT"
    result = _enrich(site=site)
    assert result["parcel_edge_relations"] == []
    assert result["opening_parcel_relations"] == []
    assert result["design_04_readiness"]["parcel_edge_intelligence"] == "INSUFFICIENT_SITE_EVIDENCE"


def test_r_parent_unresolved_evidence_is_carried_separately_and_unchanged():
    parent = _design_02()
    result = _enrich(parent, _site())
    assert result["parent_unresolved_evidence"] == parent["unresolved_evidence"]
    assert result["parent_unresolved_evidence"] is not parent["unresolved_evidence"]
