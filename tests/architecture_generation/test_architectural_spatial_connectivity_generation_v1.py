from core.architecture.reasoning.architectural_spatial_connectivity_reasoner_v1 import ArchitecturalSpatialConnectivityReasonerV1
from core.architecture.reasoning.architectural_spatial_quality_gate_v1 import ArchitecturalSpatialQualityGateV1


def _space(name, floor, x0, y0, x1, y1):
    return {"id": name, "name": name, "floor": floor,
            "footprint": {"points": [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]}}


def _relation(a, b, **extra):
    return {"from": a, "to": b, "type": "adjacent", "required": True,
            "direct_connection_required": True, "door_required": True,
            "source": "project_requirement", "evidence_status": "authoritative", **extra}


def test_required_program_connections_resolve_only_on_real_shared_boundaries():
    geometry = {"spaces": [_space("entrance","F1",0,0,2,2), _space("living","F1",2,0,5,2),
                           _space("dining","F1",5,0,7,2), _space("kitchen","F1",5,2,7,4),
                           _space("corridor","F1",0,2,5,3), _space("bedroom","F1",0,3,3,5),
                           _space("bathroom","F1",3,3,5,5)]}
    relations = [_relation("entrance","living"), _relation("living","dining"),
                 _relation("dining","kitchen"), _relation("bedroom","corridor",privacy_class="private"),
                 _relation("bathroom","corridor",privacy_class="privacy_controlled")]
    result = ArchitecturalSpatialConnectivityReasonerV1().resolve(geometry,{"adjacency":relations})
    assert result["status"] == "resolved"
    assert len(result["connections"]) == 5
    assert all(item["geometry_status"] == "resolved_shared_boundary" for item in result["connections"])


def test_cross_floor_connection_requires_resolved_vertical_system():
    geometry={"spaces":[_space("parking","basement",0,0,2,2),_space("corridor","F1",0,0,2,2)],"vertical_geometry":[]}
    result=ArchitecturalSpatialConnectivityReasonerV1().resolve(geometry,{"adjacency":[_relation("parking","corridor")]})
    assert result["status"] == "pending_required_connections"
    geometry["vertical_geometry"]=[{"id":"S","geometry_status":"resolved","served_levels":["basement","F1"]}]
    result=ArchitecturalSpatialConnectivityReasonerV1().resolve(geometry,{"adjacency":[_relation("parking","corridor")]})
    assert result["connections"][0]["geometry_status"] == "resolved_vertical"


def test_distant_required_connection_remains_unresolved_and_quality_rejects_it():
    geometry={"spaces":[_space("entrance","F1",0,0,2,2),_space("living","F1",5,0,7,2)]}
    relation=_relation("entrance","living")
    result=ArchitecturalSpatialConnectivityReasonerV1().resolve(geometry,{"adjacency":[relation]})
    assert result["status"] == "pending_required_connections"
    geometry["connections"]=result["connections"]
    gate=ArchitecturalSpatialQualityGateV1().evaluate(geometry,{"enforce":True,"required_connections":[["entrance","living"]],"entrance_space":"entrance"})
    assert gate["status"] == "rejected"
