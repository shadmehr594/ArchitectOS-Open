from pathlib import Path

from core.architecture.drawing import (
    ArchitecturalDrawingScene, SvgArchitecturalRenderer, PdfArchitecturalRenderer,
    SYMBOL_LIBRARY, INTERIOR_FIXTURE_KNOWLEDGE, InteriorFixtureFinishValidator,
    FurnitureClearanceValidator, add_review_graphics,
)


def wet_fixture(sid, fid, box, approach=None):
    return {"semantic_id": sid, "id": fid, "footprint": box, "approach_zone": approach}


def valid_wet():
    room={"id":"bath","type":"FAMILY_BATHROOM","polygon":[0,0,5,4],"ventilation_required":True}
    fixtures=[wet_fixture("BATHTUB","tub",[.2,.2,1.9,.95],[.2,.95,1.9,1.65]),
              wet_fixture("WASHBASIN","basin",[2.2,.2,2.8,.7],[2.1,.7,2.9,1.4]),
              wet_fixture("WC_IRANIAN","wc",[3.2,.2,3.8,1.0],[3.1,1.0,3.9,1.8]),
              wet_fixture("FLOOR_DRAIN","drain",[4.3,.2,4.45,.35]),
              wet_fixture("WET_SHAFT","shaft",[4.5,.2,4.9,.6])]
    finishes=[{"id":"floor","type":"FLOOR_TILE_ZONE","extent":[0,0,5,4]},
              {"id":"wall","type":"WALL_TILE_ZONE","extent":[0,0,5,.1],"host_wall_id":"south"}]
    return room,fixtures,finishes


def test_01_iranian_and_western_are_distinct(): assert INTERIOR_FIXTURE_KNOWLEDGE["WC_IRANIAN"] != INTERIOR_FIXTURE_KNOWLEDGE["WC_WESTERN"]
def test_02_bathtub_symbol_and_footprint(): assert "BATHTUB" in SYMBOL_LIBRARY and INTERIOR_FIXTURE_KNOWLEDGE["BATHTUB"]["nominal_footprint_m"]
def test_03_shower_zone_and_tray(): assert {"SHOWER_ZONE","SHOWER_TRAY"} <= SYMBOL_LIBRARY.keys()
def test_04_basin_exists(): assert "WASHBASIN" in INTERIOR_FIXTURE_KNOWLEDGE
def test_05_floor_drain_exists(): assert "FLOOR_DRAIN" in SYMBOL_LIBRARY
def test_06_wet_shaft_intent(): assert INTERIOR_FIXTURE_KNOWLEDGE["WET_SHAFT"]["ventilation_intent"].startswith("REQUIRED")


def test_07_wet_fixture_overlap_fails():
    room,fixtures,finishes=valid_wet(); fixtures[1]["footprint"]=[.5,.3,1.1,.8]
    assert "WET_FIXTURE_OVERLAP" in {x["code"] for x in InteriorFixtureFinishValidator().validate(room,fixtures,finishes=finishes,room_walls=["south"])["findings"]}


def test_08_door_swing_conflict_fails():
    room,fixtures,finishes=valid_wet(); result=InteriorFixtureFinishValidator().validate(room,fixtures,door_swings=[[.1,.1,1,1]],finishes=finishes,room_walls=["south"])
    assert "DOOR_SWING_FIXTURE_CONFLICT" in {x["code"] for x in result["findings"]}


def test_09_approach_required():
    room,fixtures,finishes=valid_wet(); fixtures[1].pop("approach_zone")
    assert "NO_CLEAR_APPROACH_TO_FIXTURE" in {x["code"] for x in InteriorFixtureFinishValidator().validate(room,fixtures,finishes=finishes,room_walls=["south"])["findings"]}


def test_10_shower_entry_clearance_required():
    room,fixtures,finishes=valid_wet(); fixtures.append(wet_fixture("SHOWER_TRAY","shower",[.2,2.5,1.1,3.4]))
    assert "NO_CLEAR_APPROACH_TO_FIXTURE" in {x["code"] for x in InteriorFixtureFinishValidator().validate(room,fixtures,finishes=finishes,room_walls=["south"])["findings"]}


def test_11_floor_tile_belongs_to_wet_room():
    room,fixtures,finishes=valid_wet(); room["type"]="BEDROOM"
    assert "FLOOR_TILE_ZONE_NOT_IN_WET_ROOM" in {x["code"] for x in InteriorFixtureFinishValidator().validate(room,fixtures,finishes=finishes,room_walls=["south"])["findings"]}


def test_12_wall_tile_is_hosted():
    room,fixtures,finishes=valid_wet()
    assert "WALL_TILE_ZONE_NOT_HOSTED" in {x["code"] for x in InteriorFixtureFinishValidator().validate(room,fixtures,finishes=finishes,room_walls=[])["findings"]}


def test_13_finish_hatches_are_vector(tmp_path):
    room,fixtures,finishes=valid_wet(); scene=ArchitecturalDrawingScene("SYNTH")
    add_review_graphics(scene,fixtures,finishes); svg=tmp_path/"x.svg"; SvgArchitecturalRenderer().render(scene,svg)
    pdf_ok=True
    if PdfArchitecturalRenderer is not None:
        pdf=tmp_path/"x.pdf"; PdfArchitecturalRenderer().render(scene,pdf); pdf_ok=pdf.read_bytes().startswith(b"%PDF")
    assert b"<line" in svg.read_bytes() and pdf_ok and all(p.kind != "IMAGE" for p in scene.primitives)


def _furniture(objects,routes=()): return FurnitureClearanceValidator().validate(objects,routes)
def test_14_bed_wardrobe_clearance_validated():
    o=[{"id":"bed","semantic_id":"DOUBLE_BED","footprint":[0,0,2,2],"activity_zone":[0,0,2.6,2.6]}, {"id":"ward","semantic_id":"WARDROBE","footprint":[2.2,2.2,3.5,2.8],"activity_zone":[2.2,1.3,3.5,2.2]}]
    assert _furniture(o)["status"]=="FAIL"
def test_15_dining_chair_pullout_validated():
    o=[{"id":"d","semantic_id":"DINING_TABLE_6","footprint":[0,0,2,1],"activity_zone":[-.7,-.7,2.7,1.7]}, {"id":"s","semantic_id":"SOFA_1","footprint":[2.2,1.2,3,2]}]
    assert "DINING_CHAIR_USE_ZONE_CONFLICT" in {x["code"] for x in _furniture(o)["findings"]}
def test_16_kitchen_aisle_validated():
    o=[{"id":"island","semantic_id":"ISLAND","footprint":[1,1,2.8,1.9],"activity_zone":[.2,.2,3.6,2.7]}, {"id":"cab","semantic_id":"KITCHEN_BASE_CABINET","footprint":[.3,.3,1,.9]}]
    assert _furniture(o)["status"]=="FAIL"
def test_17_living_circulation_validated():
    o=[{"id":"sofa","semantic_id":"SOFA_3","footprint":[1,1,3,2],"activity_zone":[.4,.4,3.6,2.6]}]
    route=[{"id":"entry-private","critical":True,"segments":[[.2,.8,4,.9]]}]
    assert "ACTIVITY_ZONE_BLOCKS_PRIMARY_ROUTE" in {x["code"] for x in _furniture(o,route)["findings"]}
def test_18_primary_route_cannot_intersect_solids():
    o=[{"id":"bed","semantic_id":"DOUBLE_BED","footprint":[1,1,3,3]}]; route=[{"id":"door-bed","segments":[[0,1.5,4,1.7]]}]
    assert "PRIMARY_ROUTE_INTERSECTS_FURNITURE" in {x["code"] for x in _furniture(o,route)["findings"]}
def test_19_clearance_guides_not_walls_or_openings():
    scene=ArchitecturalDrawingScene("S"); add_review_graphics(scene,[],clearance_guides=[{"id":"z","extent":[0,0,1,1]}])
    p=scene.primitives[0]; assert p.layer=="CLEARANCE_GUIDES" and not p.metadata["extract_as_wall"] and not p.metadata["extract_as_opening"]
def test_20_valid_wet_composition_passes():
    room,fixtures,finishes=valid_wet(); result=InteriorFixtureFinishValidator().validate(room,fixtures,finishes=finishes,room_walls=["south"])
    assert result["status"]=="PASS"
