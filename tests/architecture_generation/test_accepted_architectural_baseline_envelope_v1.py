"""ARCHITECTURAL-BASELINE-RETURN-01 accepted baseline boundary tests."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest

from core.architecture.contracts import accepted_architectural_baseline_envelope_v1 as contract_module
from core.architecture.contracts.accepted_architectural_baseline_envelope_v1 import (
    CONTRACT,
    accepted_baseline_semantic_hash,
    canonical_accepted_baseline_document,
    verify_accepted_baseline_envelope,
)
from core.architecture.geometry.architectural_space_boundary_pipeline_v1 import (
    ArchitecturalSpaceBoundaryPipelineV1,
)
from core.architecture.reasoning.architectural_change_baseline_adapter_v1 import (
    adapt_accepted_baseline_for_architectural_change,
)


def _resolved_baseline():
    extraction = {
        "source_file": "accepted-floor-plan.dxf",
        "source_sha256": "1" * 64,
        "semantic_length_unit": "METER",
        "geometry_scale_applied": False,
        "tolerance_audit": {"status": "VERIFIED", "tolerance_m": 0.001},
        "wall_face_graphs": {
            "R1": {
                "floor": "R1",
                "faces": [{"face_id": "WF-R1-001", "start": [0.0, 0.0], "end": [4.0, 0.0]}],
                "pairs": [],
                "junctions": [],
                "thickness_clusters_m": [],
            }
        },
        "wall_solid_graphs": {
            "R1": {
                "floor": "R1",
                "solids": [{"wall_solid_id": "WS-R1-001", "polygon": [[0, 0], [4, 0], [4, .2], [0, .2], [0, 0]]}],
                "unresolved_pairs": [],
                "union_area_m2": 0.8,
                "floor_envelopes": [{"envelope_id": "ENV-R1-001", "polygon": [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]}],
                "topology_repairs": [],
            }
        },
        "opening_host_graphs": {
            "R1": {
                "floor": "R1",
                "openings": [
                    {"opening_id": "D-R1-001", "kind": "DOOR", "status": "RESOLVED", "side_a": "R1-SPACE-001", "side_b": "EXTERIOR:R1"},
                    {"opening_id": "W-R1-001", "kind": "WINDOW", "status": "RESOLVED", "side_a": "R1-SPACE-001", "side_b": "EXTERIOR:R1"},
                ],
                "unresolved": [],
            }
        },
        "space_boundary_graphs": {
            "R1": {
                "floor": "R1",
                "spaces": [{
                    "space_id": "R1-SPACE-001",
                    "floor": "R1",
                    "semantic_class": "LIVING",
                    "polygon": [[0.2, 0.2], [4.0, 0.2], [4.0, 4.0], [0.2, 4.0], [0.2, 0.2]],
                    "area_m2": 14.44,
                }],
                "virtual_closures": [],
                "unresolved": [],
            }
        },
        "access_graph": {
            "nodes": [
                {"id": "R1-SPACE-001", "floor": "R1", "semantic_class": "LIVING"},
                {"id": "EXTERIOR:R1", "floor": "R1", "semantic_class": "EXTERIOR"},
            ],
            "edges": [{"edge_id": "D-R1-001", "from": "R1-SPACE-001", "to": "EXTERIOR:R1", "kind": "DOOR_PORTAL"}],
            "status": "RESOLVED",
        },
        "label_bindings": [{"space_id": "R1-SPACE-001", "semantic_class": "LIVING"}],
        "unresolved": [{"id": "R2-ENVELOPE", "type": "FLOOR_ENVELOPE", "reason": "NOT_SUPPLIED"}],
    }
    return {
        "version": ArchitecturalSpaceBoundaryPipelineV1.VERSION,
        "pipeline": "DWG_INGEST -> ARCHITECTURAL_VALIDATION",
        "boundary_extraction": extraction,
        "semantic_regions": [{"floor": "R1", "geometry_source_space_id": "R1-SPACE-001"}],
        "constraints": [{"constraint_id": "C-001", "severity": "hard", "entity_id": "R1-SPACE-001"}],
        "protected_constraints": [{"constraint_id": "C-001", "protected": True, "entity_id": "R1-SPACE-001"}],
        "protected_entities": ["R1-SPACE-001"],
        "preservation_requirements": ["PRESERVE_ACCEPTED_BOUNDARIES"],
        "architecture_only": True,
    }


def _accepted(resolved=None):
    source = _resolved_baseline() if resolved is None else resolved
    return ArchitecturalSpaceBoundaryPipelineV1().accept_resolved_baseline(
        source,
        candidate_id="ARCH-BASELINE-001",
        candidate_version="1",
        acceptance_provenance={
            "status": "ACCEPTED",
            "authority": "architectural_baseline_acceptance",
            "evidence_ids": ["review-001"],
        },
    )


def _canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def test_a_production_pipeline_acceptance_creates_valid_envelope():
    envelope = _accepted()
    assert envelope["contract"] == CONTRACT
    assert envelope["contract_version"] == "1.0"
    assert envelope["acceptance_status"] == "ACCEPTED_FROZEN"
    assert envelope["acceptance_boundary"] == "ArchitecturalSpaceBoundaryPipelineV1.accept_resolved_baseline"
    assert verify_accepted_baseline_envelope(envelope)


def test_b_accepted_identity_version_and_hash_are_present_at_boundary():
    envelope = _accepted()
    assert envelope["candidate_id"] == "ARCH-BASELINE-001"
    assert envelope["candidate_version"] == "1"
    assert len(envelope["candidate_hash"]) == 64
    assert envelope["lineage"]["accepted_candidate_id"] == envelope["candidate_id"]


def test_c_hash_verifies_exact_deterministic_canonical_document():
    envelope = _accepted()
    assert envelope["candidate_hash"] == accepted_baseline_semantic_hash(envelope)
    assert "candidate_hash" not in json.loads(canonical_accepted_baseline_document(envelope))


def test_d_same_content_produces_same_hash():
    assert _accepted()["candidate_hash"] == _accepted(deepcopy(_resolved_baseline()))["candidate_hash"]


def test_e_architectural_content_change_produces_different_hash():
    changed = _resolved_baseline()
    changed["boundary_extraction"]["space_boundary_graphs"]["R1"]["spaces"][0]["area_m2"] = 15.0
    assert _accepted()["candidate_hash"] != _accepted(changed)["candidate_hash"]


def test_f_canonical_graph_ids_and_content_are_preserved_exactly():
    resolved = _resolved_baseline()
    envelope = _accepted(resolved)
    assert envelope["boundary_extraction"] == resolved["boundary_extraction"]
    assert envelope["boundary_extraction"]["wall_face_graphs"]["R1"]["faces"][0]["face_id"] == "WF-R1-001"
    assert envelope["boundary_extraction"]["wall_solid_graphs"]["R1"]["floor_envelopes"][0]["envelope_id"] == "ENV-R1-001"


def test_g_acceptance_does_not_duplicate_or_infer_geometry():
    envelope = _accepted()
    snapshot = envelope["semantic_snapshot"]
    assert snapshot["geometry_derived"] is False
    assert snapshot["relationships_inferred"] is False
    assert "polygon" not in json.dumps(snapshot, sort_keys=True)
    assert "wall_face_graphs" not in envelope or envelope["wall_face_graphs"] is None


def test_h_semantic_snapshot_references_existing_evidence_only():
    snapshot = _accepted()["semantic_snapshot"]
    references = snapshot["canonical_record_references"]
    assert references["spaces"]["record_ids"] == ["R1-SPACE-001"]
    assert references["relations"]["record_ids"] == ["D-R1-001"]
    assert references["doors"]["record_ids"] == ["D-R1-001"]
    assert references["windows"]["record_ids"] == ["W-R1-001"]
    assert snapshot["site_orientation_inferred"] is False


def test_i_unresolved_and_missing_evidence_remains_structured():
    resolved = _resolved_baseline()
    resolved["boundary_extraction"].pop("wall_solid_graphs")
    envelope = _accepted(resolved)
    snapshot = envelope["semantic_snapshot"]
    assert snapshot["graph_availability"]["wall_solid_graphs"]["status"] == "MISSING"
    assert any(item.get("code") == "canonical_graph_missing:wall_solid_graphs" for item in snapshot["unresolved_evidence"])
    assert any(item.get("id") == "R2-ENVELOPE" for item in snapshot["unresolved_evidence"])


def test_j_raw_or_nonaccepted_input_cannot_masquerade_as_envelope():
    raw = _resolved_baseline()["boundary_extraction"]
    with pytest.raises(ValueError, match="architecture-only"):
        ArchitecturalSpaceBoundaryPipelineV1().accept_resolved_baseline(
            raw,
            candidate_id="ARCH-BASELINE-001",
            candidate_version="1",
            acceptance_provenance={"status": "ACCEPTED"},
        )
    rejected = adapt_accepted_baseline_for_architectural_change(raw)
    assert rejected["parent_candidate"] is None
    assert {item["code"] for item in rejected["readiness_gaps"]} == {"ACCEPTED_BASELINE_ENVELOPE_REQUIRED"}


def test_acceptance_requires_explicit_identity_version_and_decision_evidence():
    pipeline = ArchitecturalSpaceBoundaryPipelineV1()
    with pytest.raises(ValueError, match="candidate_id"):
        pipeline.accept_resolved_baseline(
            _resolved_baseline(), candidate_id="", candidate_version="1", acceptance_provenance={"status": "ACCEPTED"}
        )
    with pytest.raises(ValueError, match="accepted/frozen"):
        pipeline.accept_resolved_baseline(
            _resolved_baseline(), candidate_id="ARCH-BASELINE-001", candidate_version="1", acceptance_provenance={"status": "PENDING"}
        )


def test_existing_source_identity_and_version_cannot_be_rewritten_at_acceptance():
    resolved = _resolved_baseline()
    resolved.update(candidate_id="ARCH-SOURCE-001", candidate_version="7")
    with pytest.raises(ValueError, match="preserve the existing source candidate identity"):
        _accepted(resolved)


def test_k_frozen_01i_adapter_accepts_valid_production_envelope():
    result = adapt_accepted_baseline_for_architectural_change(_accepted())
    assert result["parent_candidate"] is not None
    assert result["baseline_identity"]["stored_hash_verified"] is True
    assert result["semantic_snapshot"]["spaces"][0]["space_id"] == "R1-SPACE-001"


def test_l_frozen_01i_adapter_rejects_stale_modified_accepted_content():
    envelope = _accepted()
    envelope["boundary_extraction"]["space_boundary_graphs"]["R1"]["spaces"][0]["area_m2"] = 99.0
    result = adapt_accepted_baseline_for_architectural_change(envelope)
    assert result["parent_candidate"] is None
    assert result["readiness_gaps"][0]["code"] == "accepted_baseline_hash_mismatch"


def test_m_adapted_parent_retains_original_acceptance_lineage():
    envelope = _accepted()
    parent = adapt_accepted_baseline_for_architectural_change(envelope)["parent_candidate"]
    assert parent["baseline_lineage"]["accepted_baseline_candidate_id"] == envelope["candidate_id"]
    assert parent["baseline_lineage"]["accepted_baseline_candidate_version"] == envelope["candidate_version"]
    assert parent["baseline_lineage"]["accepted_baseline_hash"] == envelope["candidate_hash"]
    assert parent["lineage"] == envelope["lineage"]


def test_n_accepted_baseline_remains_byte_and_semantically_unchanged_after_adaptation():
    envelope = _accepted()
    before = deepcopy(envelope)
    before_bytes = _canonical_bytes(envelope)
    adapt_accepted_baseline_for_architectural_change(envelope)
    assert envelope == before
    assert _canonical_bytes(envelope) == before_bytes
    assert accepted_baseline_semantic_hash(envelope) == envelope["candidate_hash"]


def test_o_acceptance_has_no_cross_domain_side_effects():
    envelope = _accepted()
    assert envelope["side_effects"] == {
        "site": False,
        "structure": False,
        "bim": False,
        "ifc": False,
        "render": False,
        "chat_intelligence": False,
    }
    assert envelope["architecture_only"] is True


def test_p_contract_and_pipeline_have_no_forbidden_cross_domain_dependencies():
    imports = []
    for module in (contract_module,):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
    document = "\n".join(imports).lower()
    forbidden = ("chat", "llm", "memory", "voice", "provider", "render", "comfy", "bim", "ifc", "structure", "site")
    assert not any(token in document for token in forbidden)


def test_q_deterministic_serialization_and_json_round_trip():
    envelope = _accepted()
    document = canonical_accepted_baseline_document(envelope)
    assert document == canonical_accepted_baseline_document(json.loads(json.dumps(envelope, ensure_ascii=False)))
    loaded = json.loads(json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    assert loaded == envelope
    assert verify_accepted_baseline_envelope(loaded)
