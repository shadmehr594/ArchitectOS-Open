"""ARCHITECTURAL-BASELINE-DESIGN-02 acceptance tests."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest

from core.architecture.contracts.derived_architectural_candidate_v1 import (
    canonical_derived_candidate_document,
    derived_candidate_semantic_hash,
    verify_derived_architectural_candidate,
)
from core.architecture.geometry.architectural_space_boundary_pipeline_v1 import (
    ArchitecturalSpaceBoundaryPipelineV1,
)
from core.architecture.reasoning import architectural_baseline_derived_candidate_refinement_v1 as refiner_module
from core.architecture.reasoning.architectural_baseline_derived_candidate_refinement_v1 import (
    derive_architectural_candidate_v1,
)


def _resolved_baseline():
    return {
        "version": ArchitecturalSpaceBoundaryPipelineV1.VERSION,
        "pipeline": "CONTROLLED_DESIGN_02_BASELINE",
        "boundary_extraction": {
            "source_file": "controlled-design-02.dxf",
            "source_sha256": "2" * 64,
            "wall_face_graphs": {
                "R1": {"floor": "R1", "faces": [{"face_id": "WF-1", "start": [0, 0], "end": [4, 0]}]}
            },
            "wall_solid_graphs": {
                "R1": {
                    "floor": "R1",
                    "solids": [{"wall_solid_id": "WS-1", "polygon": [[0, 0], [4, 0], [4, .2], [0, .2], [0, 0]]}],
                    "floor_envelopes": [{"envelope_id": "ENV-1", "polygon": [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]}],
                }
            },
            "opening_host_graphs": {
                "R1": {
                    "floor": "R1",
                    "openings": [
                        {
                            "opening_id": "D-1", "kind": "DOOR", "status": "RESOLVED",
                            "host_wall_solid_id": "WS-1", "side_a": "S-1", "side_b": "EXTERIOR:R1",
                        },
                        {
                            "opening_id": "W-1", "kind": "WINDOW", "status": "RESOLVED",
                            "host_face_a": "WF-1", "side_a": "S-1", "side_b": "EXTERIOR:R1",
                        },
                    ],
                    "unresolved": [],
                }
            },
            "space_boundary_graphs": {
                "R1": {
                    "floor": "R1",
                    "spaces": [{
                        "space_id": "S-1",
                        "floor": "R1",
                        "semantic_class": " living-room ",
                        "boundary_ids": ["WF-1"],
                        "polygon": [[.2, .2], [4, .2], [4, 4], [.2, 4], [.2, .2]],
                        "area_m2": 14.44,
                    }],
                    "unresolved": [],
                }
            },
            "access_graph": {
                "nodes": [
                    {"id": "S-1", "semantic_class": "LIVING_ROOM"},
                    {"id": "EXTERIOR:R1", "semantic_class": "EXTERIOR"},
                ],
                "edges": [{"edge_id": "D-1", "from": "S-1", "to": "EXTERIOR:R1", "kind": "DOOR_PORTAL"}],
                "status": "RESOLVED",
            },
            "unresolved": [],
        },
        "semantic_regions": [{"floor": "R1", "geometry_source_space_id": "S-1"}],
        "constraints": [{"constraint_id": "HC-1", "entity_id": "S-1"}],
        "protected_constraints": [{"constraint_id": "PC-1", "entity_id": "S-1"}],
        "protected_entities": ["S-1", "WS-1"],
        "preservation_requirements": ["PRESERVE_ACCEPTED_GEOMETRY"],
        "architecture_only": True,
    }


def _accepted():
    return ArchitecturalSpaceBoundaryPipelineV1().accept_resolved_baseline(
        _resolved_baseline(),
        candidate_id="ARCH-BASELINE-002",
        candidate_version="7",
        acceptance_provenance={
            "status": "ACCEPTED",
            "authority": "controlled_design_02_acceptance",
            "evidence_ids": ["acceptance-02"],
        },
    )


def _derive(baseline=None, requests=()):
    return derive_architectural_candidate_v1(
        _accepted() if baseline is None else baseline,
        refinement_requests=requests,
        derivation_provenance={"decision": "DESIGN_02_DERIVATION", "evidence_ids": ["design-02-review"]},
    )


def _normalization():
    return {
        "refinement_id": "REF-LABEL-1",
        "opportunity_type": "SEMANTIC_LABEL_NORMALIZATION",
        "target_id": "S-1",
        "field": "semantic_class",
        "normalized_value": "LIVING_ROOM",
    }


def _relation():
    return {
        "refinement_id": "REF-REL-1",
        "opportunity_type": "PROVEN_RELATION_BINDING",
        "target_id": "D-1",
    }


def test_a_accepted_baseline_creates_new_derived_shell_with_exact_lineage_and_no_parent_mutation():
    parent = _accepted()
    before = deepcopy(parent)
    derived = _derive(parent)
    assert derived["candidate_id"] != parent["candidate_id"]
    assert derived["candidate_version"] != parent["candidate_version"]
    assert derived["parent_baseline_id"] == parent["candidate_id"]
    assert derived["parent_baseline_version"] == parent["candidate_version"]
    assert derived["parent_baseline_hash"] == parent["candidate_hash"]
    assert derived["lineage"]["parent_baseline_hash"] == parent["candidate_hash"]
    assert parent == before
    assert verify_derived_architectural_candidate(derived)


def test_b_semantic_label_normalizes_in_overlay_without_geometry_mutation():
    parent = _accepted()
    derived = _derive(parent, [_normalization()])
    applied = derived["applied_refinements"][0]
    assert applied["source_value"] == " living-room "
    assert applied["normalized_value"] == "LIVING_ROOM"
    assert applied["change_class"] == "SEMANTICS_ONLY"
    assert derived["semantic_state"]["spaces"][0]["semantic_labels"]["semantic_class"] == "LIVING_ROOM"
    assert derived["semantic_state"]["spaces"][0]["source_semantic_labels"]["semantic_class"] == " living-room "
    assert derived["semantic_state"]["spaces"][0]["geometry_copied"] is False
    assert derived["boundary_extraction"] == parent["boundary_extraction"]
    assert derived["boundary_extraction"]["space_boundary_graphs"]["R1"]["spaces"][0]["semantic_class"] == " living-room "


def test_c_proven_relation_binding_uses_existing_edge_and_nodes_without_coordinates_or_adjacency_inference():
    derived = _derive(requests=[_relation()])
    applied = derived["applied_refinements"][0]
    assert applied["bound_endpoint_ids"] == ["S-1", "EXTERIOR:R1"]
    assert applied["source_evidence"]["source_record_ids"] == ["D-1", "EXTERIOR:R1", "S-1"]
    assert applied["change_class"] == "REFERENCES_ONLY"
    assert derived["semantic_state"]["relation_bindings"] == [applied]
    assert "polygon" not in json.dumps(applied)
    assert derived["provenance"]["relationships_inferred"] is False


def test_d_missing_evidence_becomes_structured_unresolved_refinement_not_fake_success():
    request = {
        "refinement_id": "REF-MISSING-1",
        "opportunity_type": "PROVEN_RELATION_BINDING",
        "target_id": "NOT-AN-EDGE",
    }
    derived = _derive(requests=[request])
    assert derived["applied_refinements"] == []
    assert derived["rejected_refinements"] == [{
        "refinement_id": "REF-MISSING-1",
        "code": "canonical_relation_evidence_incomplete",
    }]
    assert any(item["code"] == "canonical_relation_evidence_incomplete" for item in derived["unresolved_evidence"])


def test_e_protected_constraints_and_entities_carry_forward_unchanged():
    parent = _accepted()
    derived = _derive(parent)
    assert derived["constraints"]["hard_constraints"] == parent["hard_constraints"]
    assert derived["constraints"]["protected_constraints"] == parent["protected_constraints"]
    assert derived["constraints"]["protected_entities"] == parent["protected_entities"]
    assert derived["constraints"]["preservation_requirements"] == parent["preservation_requirements"]


def test_f_opening_window_and_access_references_are_preserved_and_source_bound():
    derived = _derive(requests=[{
        "refinement_id": "REF-HOST-1",
        "opportunity_type": "OPENING_HOST_REFERENCE_REPAIR",
        "target_id": "W-1",
    }])
    assert {item["opening_id"] for item in derived["opening_references"]} == {"D-1", "W-1"}
    assert {item["relation_id"] for item in derived["access_references"]} == {"D-1"}
    assert derived["applied_refinements"][0]["bound_host_ids"] == ["WF-1"]
    assert derived["design_03_readiness"]["verified_window_hosts"] == ["W-1"]


def test_g_all_canonical_geometry_graph_content_and_ids_are_exactly_unchanged():
    parent = _accepted()
    derived = _derive(parent, [_normalization(), _relation()])
    assert derived["boundary_extraction"] == parent["boundary_extraction"]
    assert derived["canonical_graph_references"]["space_boundary_graphs"]["record_ids"] == ["S-1"]
    assert derived["canonical_graph_references"]["wall_face_graphs"]["record_ids"] == ["WF-1"]
    assert derived["canonical_graph_references"]["wall_solid_graphs"]["record_ids"] == ["ENV-1", "WS-1"]
    assert derived["provenance"]["geometry_modified"] is False


def test_h_same_input_and_refinement_set_are_deterministic_independent_of_request_order():
    first = _derive(requests=[_normalization(), _relation()])
    second = _derive(requests=[_relation(), _normalization()])
    assert first == second
    assert first["candidate_hash"] == second["candidate_hash"]
    assert first["candidate_id"] == second["candidate_id"]


def test_i_different_semantic_refinement_changes_identity_version_and_hash():
    shell = _derive()
    refined = _derive(requests=[_normalization()])
    assert shell["candidate_id"] != refined["candidate_id"]
    assert shell["candidate_version"] != refined["candidate_version"]
    assert shell["candidate_hash"] != refined["candidate_hash"]


def test_j_stale_or_invalid_accepted_baseline_is_rejected_before_derivation():
    stale = _accepted()
    stale["boundary_extraction"]["space_boundary_graphs"]["R1"]["spaces"][0]["area_m2"] = 99
    with pytest.raises(ValueError, match="valid non-stale"):
        _derive(stale)


def test_k_design_02_modules_have_no_forbidden_cross_domain_dependencies():
    modules = (
        refiner_module,
        __import__(
            "core.architecture.contracts.derived_architectural_candidate_v1",
            fromlist=["derived_architectural_candidate_v1"],
        ),
    )
    imports = []
    for module in modules:
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
    document = "\n".join(imports).lower()
    forbidden = (
        "chat", "llm", "memory", "voice", "provider", "render", "comfyui",
        ".site", ".structure", ".bim", "ifc",
    )
    assert not any(token in document for token in forbidden)


def test_l_serialization_round_trip_and_hash_are_stable():
    derived = _derive(requests=[_normalization(), _relation()])
    document = json.dumps(derived, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    loaded = json.loads(document)
    assert loaded == derived
    assert canonical_derived_candidate_document(loaded) == canonical_derived_candidate_document(derived)
    assert derived_candidate_semantic_hash(loaded) == derived["candidate_hash"]
    assert verify_derived_architectural_candidate(loaded)


def test_design_03_readiness_distinguishes_verified_records_from_pending_domains_without_guessing():
    derived = _derive()
    readiness = derived["design_03_readiness"]
    assert readiness["verified_exterior_boundaries"] == []
    assert readiness["verified_openings"] == ["D-1", "W-1"]
    assert readiness["protected_entities"] == ["S-1", "WS-1"]
    assert readiness["privacy_evidence"] == "UNRESOLVED_NO_INFERENCE"
    assert readiness["parcel_edge_site_evidence"] == "UNRESOLVED_NO_INFERENCE"
    assert derived["provenance"]["site_orientation_inferred"] is False
    statuses = {(item["opportunity_type"], item["status"]) for item in derived["refinement_opportunities"]}
    assert ("SEMANTIC_LABEL_NORMALIZATION", "READY") in statuses
    assert ("PROVEN_RELATION_BINDING", "READY") in statuses
    assert ("PRIVACY_ANALYSIS_PENDING", "PENDING_EVIDENCE") in statuses
    assert ("PARCEL_EDGE_ANALYSIS_PENDING", "PENDING_EVIDENCE") in statuses


def test_unproven_label_rewrite_is_rejected_as_readiness_gap():
    request = _normalization()
    request["normalized_value"] = "BEDROOM"
    derived = _derive(requests=[request])
    assert derived["applied_refinements"] == []
    assert derived["rejected_refinements"][0]["code"] == "requested_label_not_proven_by_normalization"


def test_frozen_01i_adapter_is_used_read_only_for_compatibility_and_readiness():
    parent = _accepted()
    before = deepcopy(parent)
    derived = _derive(parent)
    adapter = derived["provenance"]["frozen_01i_adapter"]
    assert adapter["usage"] == "READ_ONLY_COMPATIBILITY_AND_READINESS"
    assert adapter["baseline_identity"]["accepted_baseline_hash"] == parent["candidate_hash"]
    assert adapter["revision_paths"]
    assert parent == before
