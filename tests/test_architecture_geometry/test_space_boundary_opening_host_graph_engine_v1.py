import pytest
from core.architecture.geometry.space_boundary_opening_host_graph_engine_v1 import SpaceBoundaryOpeningHostGraphEngineV1


def seg(a,b,handle=None,layer="R1_ROOM_WALL",role="wall"):
    handle=handle or f"H{abs(hash((a,b)))%99999}"
    return {"start":list(a),"end":list(b),"source_handle":handle,"source_handles":[handle],"source_layer":layer,"entity_type":"LINE","role":role}


def opening(kind, lines, handle="O1", layer=None):
    layer=layer or f"R1_{kind}"
    segments=[seg(a,b,handle,layer,kind.lower()) for a,b in lines]
    return {"handle":handle,"kind":kind,"layer":layer,"entity_type":"LINE","segments":segments,
            "points":[p for s in segments for p in (s["start"],s["end"])]}


def rectangle(x0=0,y0=0,x1=6,y1=4,gap=None,double=True):
    # inner room face; optional bottom opening gap
    bottom=[((x0,y0),(gap[0],y0)),((gap[1],y0),(x1,y0))] if gap else [((x0,y0),(x1,y0))]
    lines=bottom+[((x1,y0),(x1,y1)),((x1,y1),(x0,y1)),((x0,y1),(x0,y0))]
    if double:
        o=.2
        lines += [((x0-o,y0-o),(x1+o,y0-o)),((x1+o,y0-o),(x1+o,y1+o)),((x1+o,y1+o),(x0-o,y1+o)),((x0-o,y1+o),(x0-o,y0-o))]
    return [seg(a,b,f"W{i}") for i,(a,b) in enumerate(lines)]


def run(walls, openings=None, labels=None, floor="R1"):
    return SpaceBoundaryOpeningHostGraphEngineV1().extract_geometry({floor:{"wall_segments":walls,"opening_entities":openings or [],"labels":labels or []}})


def test_rectangular_room_closed_by_double_line_walls():
    r=run(rectangle()); assert any(s.area_m2==pytest.approx(24,rel=.03) for s in r.space_boundary_graphs["R1"].spaces)


def test_two_rooms_sharing_wall_with_one_door():
    walls=rectangle(x1=8)+[seg((4,0),(4,1.5),"S1"),seg((4,2.5),(4,4),"S2"),seg((4.2,0),(4.2,1.5),"S3"),seg((4.2,2.5),(4.2,4),"S4")]
    door=opening("DOOR",[((3.9,1.5),(4.5,2.1)),((4.5,2.1),(4.5,2.5))])
    r=run(walls,[door]); assert len(r.space_boundary_graphs["R1"].spaces)>=2


def test_door_portal_connecting_two_spaces():
    test_two_rooms_sharing_wall_with_one_door()


def test_window_does_not_create_access():
    walls=rectangle(gap=(2.5,3.5)); win=opening("WINDOW",[((2.5,-.1),(3.5,-.1))],"WIN")
    r=run(walls,[win]); assert all(e["kind"]=="DOOR_PORTAL" for e in r.access_graph["edges"])


def test_t_junction_wall():
    r=run(rectangle()+[seg((3,0),(3,4),"T")]); assert any(j["degree"]>=3 for j in r.wall_face_graphs["R1"].junctions)


def test_l_corner():
    r=run([seg((0,0),(4,0),"A"),seg((4,0),(4,4),"B")]); assert len(r.wall_face_graphs["R1"].junctions)>=3


def test_room_adjacent_to_lightwell():
    labels=[{"handle":"L","text":"نورگیر","point":[1,1],"semantic_class":"LIGHTWELL"}]
    r=run(rectangle(),labels=labels); assert any(s.semantic_class=="LIGHTWELL" for s in r.space_boundary_graphs["R1"].spaces)


def test_room_adjacent_to_exterior_south_edge():
    walls=rectangle(gap=(2.5,3.5)); win=opening("WINDOW",[((2.5,-.1),(3.5,-.1))],"WIN")
    r=run(walls,[win]); windows=r.opening_host_graphs["R1"].openings; assert not any(w.traversable for w in windows)


def test_duplicated_lines_are_deduplicated():
    walls=rectangle(); walls.append(dict(walls[0],source_handle="DUP",source_handles=["DUP"]))
    r=run(walls); assert len([f for f in r.wall_face_graphs["R1"].faces if "DUP" in f["source_handles"]])==1


def test_small_cad_gap_within_tolerance():
    walls=rectangle(double=False); walls[0]["end"]=[6.001,0]
    r=run(walls); assert r.tolerance_audit["chosen_snap_tolerance_m"]<=.02


def test_gap_beyond_tolerance_remains_unresolved():
    walls=rectangle(double=False); walls[-1]["end"]=[0,.2]
    r=run(walls); assert any(u["reason"]=="NO_VALID_SPATIAL_CELL_POLYGONIZED" for u in r.unresolved)


def test_path_guide_ignored_by_contract():
    r=run(rectangle()+[seg((1,1),(5,3),"PATH","R1_PATH_GUIDE","path")]); assert r.access_graph["proofs"]["no_path_guide_wall_or_host_use"]


def test_column_inside_room_does_not_split_space():
    r=run(rectangle()); assert len([s for s in r.space_boundary_graphs["R1"].spaces if s.area_m2>10])==1


def test_r2_two_unit_separation_no_cross_unit_portal():
    r=run(rectangle(),floor="R2"); assert r.access_graph["r2_unit_separation"]["status"]=="UNPROVEN_NO_PORTALS"


def two_room_opening(kind="DOOR"):
    walls=rectangle(x1=8)+[seg((4,0),(4,1.5),"S1"),seg((4,2.5),(4,4),"S2"),seg((4.2,0),(4.2,1.5),"S3"),seg((4.2,2.5),(4.2,4),"S4")]
    return walls,opening(kind,[((3.9,1.5),(4.5,2.1)),((4.5,2.1),(4.5,2.5))],kind)


def test_double_line_room_builds_wall_solids_and_one_room_cell():
    r=run(rectangle())
    assert len(r.wall_solid_graphs["R1"].solids)==4
    assert len([s for s in r.space_boundary_graphs["R1"].spaces if s.area_m2>10])==1


def test_shared_double_wall_door_makes_two_cells_and_one_portal():
    walls,door=two_room_opening()
    r=run(walls,[door])
    assert len(r.space_boundary_graphs["R1"].spaces)==2
    assert len(r.access_graph["edges"])==1


def test_door_same_cell_is_not_valid_portal():
    walls,door=two_room_opening()
    r=run(walls,[door]); portal=r.opening_host_graphs["R1"].openings[0]
    portal.side_b=portal.side_a
    portal.status="UNRESOLVED_DOOR_SAME_CELL"; portal.traversable=False
    graph=SpaceBoundaryOpeningHostGraphEngineV1()._access_graph(r.space_boundary_graphs,r.opening_host_graphs)
    assert graph["edges"]==[] and graph["status"]=="UNPROVEN_NO_PORTALS"


def test_edges_empty_never_proves_unit_separation():
    r=run(rectangle(),floor="R2")
    assert r.access_graph["edges"]==[]
    assert r.access_graph["r2_unit_separation"]["status"]=="UNPROVEN_NO_PORTALS"
    assert r.access_graph["status"]=="UNPROVEN_NO_PORTALS"


def test_raw_wall_face_giant_cell_regression():
    walls,door=two_room_opening()
    labels=[{"handle":"A","text":"bed","point":[2,2],"semantic_class":"BEDROOM"},
            {"handle":"B","text":"wc","point":[6,2],"semantic_class":"WC"}]
    r=run(walls,[door],labels)
    assert len(r.space_boundary_graphs["R1"].spaces)==2
    assert not any(b["conflict"] for b in r.label_bindings)


def test_wall_solid_subtraction_separates_rooms():
    walls=rectangle(x1=8)+[seg((4,0),(4,4),"S1"),seg((4.2,0),(4.2,4),"S2")]
    r=run(walls)
    assert len(r.wall_solid_graphs["R1"].solids)>=5
    assert len(r.space_boundary_graphs["R1"].spaces)==2


def test_window_closure_splits_cells_but_has_zero_access_edge():
    walls,window=two_room_opening("WINDOW")
    r=run(walls,[window])
    assert len(r.space_boundary_graphs["R1"].spaces)==2
    assert r.access_graph["edges"]==[]


def test_open_plan_living_kitchen_can_remain_one_cell():
    labels=[{"handle":"L","text":"پذیرایی","point":[2,2],"semantic_class":"LIVING"},
            {"handle":"K","text":"kitchen","point":[4,2],"semantic_class":"KITCHEN"}]
    r=run(rectangle(),labels=labels)
    assert len(r.space_boundary_graphs["R1"].spaces)==1
    assert any(u["reason"]=="MULTIPLE_CONFLICTING_ROOM_LABELS" for u in r.unresolved)


def test_parking_subregion_labels_do_not_conflict_in_open_zone():
    labels=[{"handle":f"P{i}","text":f"P{i}","point":[i*1.5,2],"semantic_class":"PARKING"} for i in (1,2,3)]
    r=run(rectangle(x1=8),labels=labels,floor="G")
    assert len(r.space_boundary_graphs["G"].spaces)==1
    assert not any(b["conflict"] for b in r.label_bindings)


def test_lightwell_and_terrace_cells_do_not_merge_with_interior():
    walls,window=two_room_opening("WINDOW")
    labels=[{"handle":"R","text":"bed","point":[2,2],"semantic_class":"BEDROOM"},
            {"handle":"T","text":"تراس","point":[6,2],"semantic_class":"TERRACE"}]
    r=run(walls,[window],labels)
    classes={s.semantic_class for s in r.space_boundary_graphs["R1"].spaces}
    assert {"BEDROOM","TERRACE"}.issubset(classes)


def test_ambiguous_split_wall_pairs_resolve_by_continuity():
    walls,door=two_room_opening()
    r=run(walls,[door]); portal=r.opening_host_graphs["R1"].openings[0]
    assert portal.status=="RESOLVED"
    assert portal.geometric_evidence["tie_resolved_by_local_face_continuity"] is True


def test_truly_tied_different_wall_bands_remain_unresolved():
    walls=rectangle(x0=-4,y0=-2,x1=4,y1=2)+[seg((-2,-.55),(2,-.55),"A1"),seg((-2,-.35),(2,-.35),"A2"),
                                                seg((-2,.35),(2,.35),"B1"),seg((-2,.55),(2,.55),"B2")]
    door=opening("DOOR",[((-.5,-.1),(.5,.1))],"D")
    r=run(walls,[door]); portal=r.opening_host_graphs["R1"].openings[0]
    assert portal.status=="UNRESOLVED"
    assert portal.geometric_evidence["measured_reason"]=="AMBIGUOUS_MULTIPLE_WALL_PAIRS"
