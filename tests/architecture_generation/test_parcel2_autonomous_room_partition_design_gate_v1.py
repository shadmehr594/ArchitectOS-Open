from shapely.geometry import Polygon

from core.architecture.geometry.space_boundary_opening_host_graph_engine_v1 import SpaceBoundaryOpeningHostGraphEngineV1
from core.architecture.reasoning.parcel2_autonomous_room_partition_design_gate_v1 import Parcel2AutonomousRoomPartitionDesignGateV1


def gate():
    design=Parcel2AutonomousRoomPartitionDesignGateV1().generate()
    return design,SpaceBoundaryOpeningHostGraphEngineV1().extract_geometry(design["geometry"])


def test_01_r1_room_program_contains_required_room_nodes():
    d,_=gate(); classes={x["semantic_class"] for x in d["r1_room_program"]}
    assert {"ENTRY_SHOE_OFF","LIVING_RECEPTION","OPEN_KITCHEN_DINING","MASTER_BEDROOM_SLEEPING","MASTER_DRESSING","MASTER_ENSUITE","BEDROOM","FAMILY_BATHROOM","GUEST_WC","STORAGE_LINEN","PRIVATE_TERRACE"}<=classes


def test_02_r2_exactly_two_independent_unit_graphs():
    d,_=gate(); assert set(x["unit_id"] for x in d["r2_room_program"])=={"R2_U1","R2_U2"}
    assert all(d["unit_layout_graph"][u]["entry_node"] for u in ("R2_U1","R2_U2"))


def test_03_private_rooms_are_not_circulation_through_rooms():
    d,_=gate(); forbidden={x["room_id"] for x in d["r1_room_program"]+d["r2_room_program"] if any(k in x["semantic_class"] for k in ("BEDROOM","BATH","WC"))}
    edges=[e for e in d["adjacency_graph"] if e["relation"] in {"MUST_CONNECT","PUBLIC_TO_PRIVATE_TRANSITION"}]
    degree={n:sum(n in (e["from_space"],e["to_space"]) for e in edges) for n in forbidden}
    assert all(v<=1 for v in degree.values())


def test_04_open_kitchen_subzone_does_not_collapse_private_rooms():
    d,_=gate(); open_cells=[p for p in d["partition_plan_r2"] if p["open_plan_subzones"]]
    assert len(open_cells)==2 and all(len(p["open_plan_subzones"])==2 for p in open_cells)
    assert all(p["semantic_class"]!="PUBLIC_OPEN_PLAN" for p in d["partition_plan_r2"] if "BEDROOM" in p["room_id"] or p["room_id"].endswith(("_BATH","_WC")))


def test_05_every_required_room_has_polygon_or_explicit_open_plan_subzone_before_walls():
    d,_=gate(); plans=d["partition_plan_r1"]+d["partition_plan_r2"]
    represented={p["room_id"] for p in plans}|{s for p in plans for s in p["open_plan_subzones"]}
    required={x["room_id"] for x in d["r1_room_program"]+d["r2_room_program"] if "LIGHTWELL" not in x["semantic_class"]}
    assert required<=represented and all(p["generated_before_walls"] for p in plans)


def test_06_polygons_do_not_overlap():
    d,_=gate()
    for plan in (d["partition_plan_r1"],d["partition_plan_r2"]):
        geoms=[Polygon(p["polygon"]) for p in plan]
        assert all(geoms[i].intersection(geoms[j]).area<1e-8 for i in range(len(geoms)) for j in range(i+1,len(geoms)))


def test_07_every_door_intent_connects_distinct_spaces():
    d,_=gate(); assert d["door_intents"] and all(x["from_space"]!=x["to_space"] for x in d["door_intents"])


def test_08_every_internal_door_has_expected_host_partition():
    d,r=gate(); portals=[p for f in ("R1","R2") for p in r.opening_host_graphs[f].openings if p.kind=="DOOR"]
    assert all(p.expected_host_partition and p.host_wall_pair_id for p in portals)


def test_09_wall_geometry_preserves_partition_topology():
    d,r=gate(); assert all(len(r.wall_face_graphs[f].pairs)>10 and len(r.space_boundary_graphs[f].spaces)>10 for f in ("R1","R2"))


def test_10_kernel_door_sides_are_distinct_and_intent_confirmed():
    _,r=gate(); portals=[p for f in ("R1","R2") for p in r.opening_host_graphs[f].openings if p.kind=="DOOR"]
    assert all(p.status=="RESOLVED" and p.side_a!=p.side_b and p.intent_assertion_status=="CONFIRMED_GEOMETRICALLY" for p in portals)


def test_11_r2_has_no_private_cross_unit_door():
    d,_=gate(); assert not any("R2_U1" in x["from_space"] and "R2_U2" in x["to_space"] or "R2_U2" in x["from_space"] and "R2_U1" in x["to_space"] for x in d["door_intents"])


def test_12_every_unit_has_private_terrace_relation():
    d,_=gate(); ids={x["room_id"] for x in d["r1_room_program"]+d["r2_room_program"]}
    assert all(f"{u}_TERRACE" in ids for u in ("R1_U1","R2_U1","R2_U2"))


def test_13_no_neighbor_edge_windows():
    d,_=gate(); assert all(x["allowed_exposure"] in {"SOUTH_STREET","LIGHTWELL","TERRACE"} for x in d["window_intents"])


def test_14_bedrooms_without_south_use_lightwell_and_kernel_confirms():
    d,r=gate(); bedroom_windows=[x for x in d["window_intents"] if "BED" in x["room_id"] or "MASTER" in x["room_id"]]
    assert bedroom_windows and all(x["allowed_exposure"]=="LIGHTWELL" for x in bedroom_windows)
    assert all(p.status=="RESOLVED" and p.exposure=="LIGHTWELL" for f in ("R1","R2") for p in r.opening_host_graphs[f].openings if p.kind=="WINDOW" and p.expected_exposure=="LIGHTWELL")


def test_15_access_from_entries_reaches_required_rooms_without_private_room_transit():
    d,r=gate(); assert r.access_graph["r1_reachability"]["status"]=="PROVEN_FROM_PORTALS"
    assert r.access_graph["r2_unit_separation"]["status"]=="PROVEN_FROM_PORTALS"
    assert all(not x["room_through_room_edges"] for x in d["unit_layout_graph"].values())


def test_16_zero_portal_cannot_pass():
    _,r=gate(); assert r.access_graph["edges"] and r.access_graph["status"]=="RESOLVED"


def test_authoritative_contract_and_no_dwg_fallback():
    d,_=gate(); c=d["project_contract"]
    assert (c["width_m"],c["depth_m"],c["levels_m"]["R1"],c["levels_m"]["R2"],c["levels_m"]["ROOF"],c["levels_m"]["PENTHOUSE_TOP"])==(10.0,20.0,5.2,8.44,11.68,14.38)
    assert d["provenance"]["room_coordinates_from_dwg"] is False and d["provenance"]["manual_geometry_fallback"] is False
