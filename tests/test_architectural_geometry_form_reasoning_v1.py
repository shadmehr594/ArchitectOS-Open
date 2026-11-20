from copy import deepcopy
from pathlib import Path
import inspect, json

from core.architecture.reasoning.architectural_geometry_form_reasoning_v1 import ArchitecturalGeometryFormReasoningV1


def scenario(kind="orthogonal"):
    boundary = [[0,0],[12,0],[12,10],[0,10]]
    if kind == "angled": boundary = [[0,0],[12,0],[11,10],[0,10]]
    spaces = [
        {"id":"FOYER","use":"foyer","boundary":[[0,0],[3,0],[3,2],[0,2]],"privacy":"public"},
        {"id":"LIVING","use":"living","boundary":[[3,0],[12,0],[12,5],[3,5]],"privacy":"public"},
        {"id":"BED","use":"bedroom","boundary":[[0,6],[5,6],[4,10],[0,10]],"privacy":"private"},
        {"id":"CORE","use":"core","boundary":[[6,6],[9,6],[9,10],[6,10]],"privacy":"neutral"},
    ]
    return dict(plan_boundary=boundary, spaces=spaces, connections=[["FOYER","LIVING"],["LIVING","BED"]],
                exterior_edges=[[[0,0],[12,0]]], entrances=[[1,0]])


def test_determinism_and_no_mutation():
    data=scenario(); before=deepcopy(data); engine=ArchitecturalGeometryFormReasoningV1()
    assert engine.analyze(**data)==engine.analyze(**data)
    assert data==before and engine.analyze(**data)["input_mutated"] is False


def test_generic_contract_no_winner_and_metrics():
    result=ArchitecturalGeometryFormReasoningV1().analyze(**scenario("angled"))
    assert result["selection"]=={"winner":None,"authoritative_ranking":False,"final_selection_performed":False}
    assert len(result["comparison_dimensions"])==10
    assert result["proposals"][0]["geometry_family_descriptor"]=="orthogonal"
    assert all(not p["is_winner"] for p in result["proposals"])
    assert all((not p["non_orthogonal_or_curved"]) or p["justification_gate_passed"] for p in result["proposals"])


def test_no_parcel2_hardcode_no_fixed_pentagon_or_shape_catalog_selection():
    text=inspect.getsource(ArchitecturalGeometryFormReasoningV1).lower()
    assert "parcel2" not in text and "parcel 2" not in text and "pentagon" not in text
    result=ArchitecturalGeometryFormReasoningV1().analyze(**scenario())
    assert result["policy"]["shape_catalog_selection"] is False
    assert result["policy"]["fixed_vertex_count"] is False


def test_synthetic_rotated_context_and_spatial_uses():
    engine=ArchitecturalGeometryFormReasoningV1()
    results=[engine.analyze(**scenario(k)) for k in ("orthogonal","angled")]
    assert results[0]["context_axes"] != [] and results[1]["detected_geometry_language"]["primary"].startswith("hybrid")
    required={"foyer","living","dining","corridor","stair_hall","bedroom_transition","service","core","balcony","courtyard","unit_shape"}
    assert required==set(results[0]["supported_spatial_uses"])


def test_precedent_contract_is_non_regulatory():
    p=Path(__file__).resolve().parents[1]/"core/architecture/contracts/architectural_geometry_form_precedent_knowledge_v1.json"
    data=json.loads(p.read_text(encoding="utf-8"))
    assert data["authority_class"]=="PRECEDENT_NON_REGULATORY"
    assert data["may_resolve_regulatory_requirement"] is False
    assert len(data["precedents"])>=6
