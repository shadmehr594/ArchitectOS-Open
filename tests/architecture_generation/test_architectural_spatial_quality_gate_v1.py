from core.architecture.reasoning.architectural_spatial_quality_gate_v1 import ArchitecturalSpatialQualityGateV1


def _geometry(edges):
    spaces=[{"name":name,"footprint":{"width":3,"depth":3}} for name in ("entrance","living","dining","kitchen","corridor","bedroom")]
    openings=[{"geometry_status":"resolved","connects_from":a,"connects_to":b} for a,b in edges]
    return {"spaces":spaces,"openings":openings,"vertical_geometry":[],"site_geometry":{}}


def _requirements():
    return {"enforce":True,"entrance_space":"entrance","required_connections":[
        ["entrance","living"],["living","dining"],["dining","kitchen"],["living","corridor"],["corridor","bedroom"]],
        "privacy_forbidden_direct_connections":[["entrance","bedroom"]],
        "maximum_dead_end_connections":0,
        "minimum_usable_dimensions":{"bedroom":{"width":2.8,"depth":3.0}}}


def test_valid_connected_layout_passes_quality_gate():
    edges=[("entrance","living"),("living","dining"),("dining","kitchen"),("living","corridor"),("corridor","bedroom")]
    assert ArchitecturalSpatialQualityGateV1().evaluate(_geometry(edges),_requirements())["status"]=="passed"


def test_disconnected_room_and_entrance_are_rejected():
    result=ArchitecturalSpatialQualityGateV1().evaluate(_geometry([("living","dining")]),_requirements())
    kinds={v["type"] for v in result["violations"]}
    assert "isolated_space" in kinds and "entrance_without_internal_connection" in kinds


def test_privacy_violation_and_kitchen_dining_disconnect_are_rejected():
    edges=[("entrance","living"),("entrance","bedroom"),("living","corridor"),("corridor","bedroom")]
    result=ArchitecturalSpatialQualityGateV1().evaluate(_geometry(edges),_requirements())
    kinds={v["type"] for v in result["violations"]}
    assert "privacy_connection_violation" in kinds and "required_connection_missing" in kinds


def test_excessive_dead_corridor_and_small_room_are_detected():
    geometry=_geometry([("entrance","living"),("living","dining"),("dining","kitchen"),("living","corridor")])
    next(s for s in geometry["spaces"] if s["name"]=="bedroom")["footprint"]["width"]=2.0
    result=ArchitecturalSpatialQualityGateV1().evaluate(geometry,_requirements())
    kinds={v["type"] for v in result["violations"]}
    assert "excessive_dead_end_circulation" in kinds and "minimum_usable_dimension" in kinds
