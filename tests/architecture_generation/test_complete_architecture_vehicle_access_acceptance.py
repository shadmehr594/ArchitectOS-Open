from pathlib import Path

import ezdxf
import ifcopenshell
import math
import pytest

from core.architecture.brain.architectural_brain import ArchitecturalBrain
from core.architecture.geometry.vehicle_access_geometry_resolver_v1 import VehicleAccessGeometryResolverV1
from core.integration.design_bim_bridge import DesignBIMBridge
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent


PARCEL = [[0.0, 0.0], [20.0, 0.0], [20.0, 30.0], [0.0, 30.0]]

# ---------------------------------------------------------------------------
# Architecture-first vehicle access evidence (fixture repair).
#
# The active resolver publishes physical geometry ONLY from an explicitly
# coordinated entrance interval on the selected parcel edge, and it requires
# the parking arrival to coincide with the resolved ramp exit
# ("parking_arrival_must_equal_resolved_ramp_exit").  A hand-built acceptance
# selection must therefore carry that interval and keep the parking program
# internally consistent; it may not rely on the retired 25/50/75 sampler or on
# an arrival point that is unrelated to the ramp run.
# ---------------------------------------------------------------------------
SOUTH_RAMP_RUN = 16.0
SOUTH_ENTRANCE_INTERVAL = [[0.25, 0.0], [3.75, 0.0]]
SOUTH_ENTRANCE_CENTER = [2.0, 0.0]
NORTH_ENTRANCE_INTERVAL = [[13.25, 30.0], [16.75, 30.0]]
SOUTH_AISLE_Y = 7.5


def _south_parking_arrival(vehicle_ramp_run):
    offset = math.sqrt(max(vehicle_ramp_run ** 2 - SOUTH_AISLE_Y ** 2, 0.0))
    return [SOUTH_ENTRANCE_CENTER[0] + offset, SOUTH_AISLE_Y]


def _south_required_run(target_point):
    """Ramp run implied by a south parking target.

    The active resolver requires the parking arrival to coincide with the
    resolved ramp exit, so for a south entrance the run is exactly the distance
    from the (coordinated) entrance centre to the target.
    """
    return math.hypot(float(target_point[0]) - SOUTH_ENTRANCE_CENTER[0],
                      float(target_point[1]) - SOUTH_ENTRANCE_CENTER[1])



def _site(access_edge_index):
    return {
        "source": "parcel", "source_type": "polygon",
        "boundary": {"type": "polygon", "points": PARCEL},
        "area": 600.0, "coordinate_system": "local_normalized",
        "building_height": 3.6,
        "neighbors": {"north": False, "south": False, "east": True, "west": True},
        "separation_joint_requirement": {"enabled": True},
        "site_constraints": {
            "access": {"confirmed": True, "edge_index": access_edge_index, "road_width": 8.0},
            "adjacency": [
                {"edge_index": 0, "type": "road", "confirmed": True},
                {"edge_index": 1, "type": "neighbor_parcel", "confirmed": True},
                {"edge_index": 2, "type": "road", "confirmed": True},
                {"edge_index": 3, "type": "neighbor_parcel", "confirmed": True},
            ],
        },
    }


def _architectural_intent(access_edge_index, vehicle_ramp_run=SOUTH_RAMP_RUN):
    intent = ArchitecturalIntent().extract(
        {
            "prompt": "ساختمان مسکونی یک طبقه با زیرزمین",
            "architectural_intent": {
                "building_type": "residential", "functions": ["residential"],
                "spaces": ["basement"],
                "levels": {"above_ground": 1, "ground": 1, "basement": 1, "mezzanine": 0, "total": 2},
                "vertical_transport": {"elevators": [], "ramps": [], "escalators": [], "stairs": [{
                    "id": "project_main_stair", "from_level": "basement", "to_level": "F1",
                    "required": True, "clear_width": 1.2,
                    "allowed_zone": {"points": (
                        [[0.2, 2.2], [7.2, 2.2], [7.2, 5.2], [0.2, 5.2]]
                        if access_edge_index == 0 else
                        [[2.2, 3.2], [9.2, 3.2], [9.2, 6.2], [2.2, 6.2]]
                    )},
                    "flight_count": 2, "landing_required": True, "landing_depth": 1.2,
                    "maximum_riser": 0.18, "minimum_tread": 0.28, "headroom": 2.1,
                    "conflict_evidence_complete": True, "conflict_zones": [],
                    "source": "project_requirement", "evidence_status": "authoritative",
                    "circulation_interfaces": [
                        {"interface_id":"stair-basement", "level":"basement", "circulation_space_id":"basement",
                         "interface_role":"parking_lobby_entry", "source":"project_requirement", "evidence_status":"authoritative"},
                        {"interface_id":"stair-F1", "level":"F1", "circulation_space_id":"corridor",
                         "interface_role":"ground_circulation_exit", "source":"project_requirement", "evidence_status":"authoritative"},
                    ],
                }]},
                "vehicle_access": {"entrances": [
                    {"access_id": "south_road", "served_level": "basement",
                     "opening_role": "basement_vehicle_entrance", "clear_width": 3.5,
                     "clear_height": 2.4, "source": "project_requirement", "evidence_status": "authoritative"},
                    {"access_id": "north_road", "served_level": "basement",
                     "opening_role": "basement_vehicle_entrance", "clear_width": 3.5,
                     "clear_height": 2.4, "source": "project_requirement", "evidence_status": "authoritative"},
                ]},
                "vehicle_ramp_requirements": [{
                    "access_id": "south_road", "required_headroom": 2.20,
                    "source": "project_requirement", "evidence_status": "authoritative",
                }],
                "parking_requirements": [{
                    "served_level": "basement", "required": True,
                    "minimum_turning_radius": 2.0, "required_clear_width": 3.5,
                    "source": "project_requirement", "evidence_status": "authoritative",
                }],
            },
        },
        {"site": _site(access_edge_index)},
    )
    # Project-authoritative program evidence; walls/openings/slabs remain generated.
    intent["explicit_program_complete"] = True
    intent["spaces"] = [
        {"name":"basement","floor":"basement","zone":"circulation","space_type":"parking_circulation",
         "resolved_dimensions":{"width":19.8,"depth":15.0,"area":297.0}},
        {"name":"entrance","floor":"ground_floor","zone":"public","space_type":"entrance",
         "resolved_dimensions":{"width":2.0,"depth":2.0,"area":4.0}},
        {"name":"corridor","floor":"ground_floor","zone":"circulation","space_type":"circulation",
         "resolved_dimensions":{"width":1.5,"depth":6.0,"area":9.0}},
        {"name":"living","floor":"ground_floor","zone":"public","space_type":"living",
         "resolved_dimensions":{"width":4.0,"depth":4.0,"area":16.0}},
        {"name":"dining","floor":"ground_floor","zone":"public","space_type":"dining",
         "resolved_dimensions":{"width":3.0,"depth":3.0,"area":9.0}},
        {"name":"kitchen","floor":"ground_floor","zone":"service","space_type":"kitchen",
         "resolved_dimensions":{"width":3.0,"depth":3.0,"area":9.0}},
        {"name":"guest_wc","floor":"ground_floor","zone":"private","space_type":"bathroom",
         "resolved_dimensions":{"width":2.0,"depth":2.0,"area":4.0}},
    ]
    intent["floor_heights"] = {"basement": 2.4, "F1": 3.6}
    intent["site_conflict_inventory"] = {
        "zones": [], "evidence_complete": True,
        "source": "project_site_requirement", "evidence_status": "authoritative",
    }
    intent["pedestrian_site_access_requirements"] = {
        "required": True, "clear_width": 1.2, "access_edge_reference": access_edge_index,
        "setbacks": [], "protected_zones": [], "pedestrian_conflict_zones": [],
        "vehicle_access_zones": [], "vehicle_circulation_zones": [], "parking_access_zones": [],
        "source": "project_site_requirement", "evidence_status": "authoritative",
    }
    door = {"required":True, "door_required":True, "direct_connection_required":True,
            "shared_boundary_required":True, "required_clear_width":0.8, "required_clear_height":2.1,
            "opening_offset_from_interface_start":0.75, "end_clearance":0.1,
            "source":"project_requirement", "evidence_status":"authoritative"}
    intent["relationships"] = [
        {**door,"connection_id":"entrance-corridor","from":"entrance","to":"corridor","access_role":"main_internal_arrival"},
        {**door,"connection_id":"corridor-living","from":"corridor","to":"living","opening_offset_from_interface_start":1.0},
        {"connection_id":"living-dining","from":"living","to":"dining","required":True,"door_required":False,
         "direct_connection_required":True,"shared_boundary_required":True,"source":"project_requirement","evidence_status":"authoritative"},
        {**door,"connection_id":"dining-kitchen","from":"dining","to":"kitchen","opening_offset_from_interface_start":1.0},
        {**door,"connection_id":"guest-wc-corridor","from":"corridor","to":"guest_wc","privacy_class":"privacy_controlled","opening_offset_from_interface_start":1.0},
        {"connection_id":"basement-F1-circulation","from":"basement","to":"corridor","required":True,"door_required":False,
         "circulation_role":"vertical","source":"project_requirement","evidence_status":"authoritative"},
    ]
    intent["layout_regeneration"] = {"enabled":True,"max_attempts":1,"protected_zones":[]}
    intent["spatial_quality_requirements"] = {
        "enforce":True, "required_space_connectivity":True, "required_physical_openings":True,
        "required_vertical_connectivity":True, "required_parking_pedestrian_connection":True,
        "privacy_enforcement":True, "entrance_space":"entrance",
        "required_reachable_spaces":["entrance","corridor","living","dining","kitchen","guest_wc","basement"],
        "source":"project_requirement", "evidence_status":"authoritative",
    }
    intent["parking_pedestrian_requirements"] = [{
        "connection_id":"parking-to-stair", "required":True, "served_level":"basement",
        "required_clear_width":1.0, "destination_interface_role":"parking_lobby_entry",
        "orthogonal_paths_allowed":True, "source":"project_requirement", "evidence_status":"authoritative",
    }]
    parking = intent["parking_requirements"][0]
    if access_edge_index == 0:
        arrival = _south_parking_arrival(vehicle_ramp_run)
        parking.update({"required_parking_count": 2, "stall_width": 2.5,
                        "parking_target_reference": "basement_parking_arrival",
                        "parking_target_point": list(arrival),
                        "parking_target_source": "project_requirement",
                        "stall_depth": 3.0, "aisle_width": 3.0,
                        "aisle_centerline": [list(arrival), [3.0, SOUTH_AISLE_Y]],
                        "stall_sides": ["right"]})
    else:
        parking.update({"required_parking_count": 2, "stall_width": 2.5,
                        "parking_target_reference": "basement_parking_arrival",
                        "parking_target_point": [10.0, 22.5],
                        "parking_target_source": "project_requirement",
                        "stall_depth": 3.0, "aisle_width": 3.0,
                        "aisle_centerline": [[10.0, 22.5], [17.0, 22.5]],
                        "stall_sides": ["left"]})
    return intent


def _selection(access_id, side, mode, access_z, required_run):
    edge_index = 0 if side == "south" else 2
    interval = ([list(point) for point in SOUTH_ENTRANCE_INTERVAL] if side == "south"
                else [list(point) for point in NORTH_ENTRANCE_INTERVAL])
    return {
        "status": "resolved", "selected_system": mode, "selected_access_id": access_id,
        "selected_access_candidate": {
            "access_id": access_id, "side": side, "access_mode": mode,
            "edge_index": edge_index,
            "access_elevation": access_z, "target_elevation": -2.4,
            "target_level": "basement", "delta_z": -2.4 - access_z,
            "absolute_level_difference": abs(-2.4 - access_z),
            "required_run": required_run, "ramp_geometry_required": mode == "vehicle_ramp",
            "site_fit": True, "source": "user_selected_access_acceptance",
            "entrance_interval": interval,
        },
        "geometry_generation_allowed": True, "driveway_geometry_allowed": True,
        "ramp_geometry_allowed": mode == "vehicle_ramp",
    }


def _generate_and_export(access_id, side, mode, access_z, required_run, label):
    edge_index = 0 if side == "south" else 2
    model = ArchitecturalBrain().design(
        _architectural_intent(edge_index, required_run)
    ).to_dict()
    intelligence = model["architectural_intelligence"]
    geometry = intelligence["architectural_geometry"]
    stair = next(item for item in geometry["vertical_geometry"] if item.get("type") == "stair_geometry")
    assert stair["geometry_status"] == "resolved"
    assert stair["parameters"]["requirement_source"] == "project_requirement"
    resolved = VehicleAccessGeometryResolverV1().resolve(
        _selection(access_id, side, mode, access_z, required_run),
        geometry, {"slope": 0.15},
    )
    assert resolved["status"] == "resolved", resolved.get("parking_arrival", {}).get("unresolved_evidence", resolved)
    geometry = resolved["architectural_geometry"]
    assert geometry["spatial_quality_gate"]["status"] == "passed"
    assert geometry["spatial_quality_gate"]["architectural_authority"] is True
    assert geometry["architecture_completion_gate"]["architecture_complete"] is True
    result = DesignBIMBridge().run_bim({
        "architecture_first": True, "architectural_geometry": geometry, "geometry": geometry,
        "vertical_section": intelligence["vertical_section"],
        "geometry_intent": intelligence["geometry_intent"],
        "generate_structure": False, "run_id": label, "export_session": "DEFAULT",
    })["bim_result"]
    assert result["exports"]["status"] == "completed", result["exports"]
    return model, resolved, result


def _assert_complete_exports(model, result, expected_ramps, label):
    intelligence = model["architectural_intelligence"]
    geometry = result["geometry"]
    site_analysis = model["site_analysis"]
    application = site_analysis["separation_joint_application"]
    joints = site_analysis["separation"]["separation_joints"]
    assert application["status"] == "resolved"
    assert application["parcel_boundary"] == PARCEL
    assert application["buildable_boundary"] == [[0.1, 0.0], [19.9, 0.0], [19.9, 30.0], [0.1, 30.0]]
    assert joints["east"]["joint"] == pytest.approx(0.10)
    assert joints["west"]["joint"] == pytest.approx(0.10)
    assert joints["north"]["joint"] == joints["south"]["joint"] == 0
    assert intelligence["geometry_intent"]["parcel_placement"]["status"] == "resolved"

    walls, openings, slabs = geometry["physical_walls"], geometry["openings"], geometry["slabs"]
    assert walls and slabs and geometry["floor_geometry"]
    assert sum(item.get("type") == "door" and item.get("geometry_status") == "resolved" for item in openings) > 0
    assert all(item.get("geometry_status") == "resolved" for item in openings if item.get("geometry_generation_allowed") is True)
    assert all(item.get("host_wall_id") for item in openings if item.get("type") in ("door", "window") and item.get("geometry_status") == "resolved")
    assert all(item.get("geometry_status") != "pending" for item in openings if item.get("geometry_generation_allowed") is True)
    wall_xs = [float(p[0]) for wall in walls for p in (wall.get("start"), wall.get("end"))
               if isinstance(p, (list, tuple)) and len(p) >= 2]
    vertical_walls = [wall for wall in walls if wall.get("is_exterior") and abs(wall["start"][0] - wall["end"][0]) <= 1e-7]
    west = min(float(wall["start"][0]) - float(wall["thickness"]) / 2.0 for wall in vertical_walls)
    east = max(float(wall["start"][0]) + float(wall["thickness"]) / 2.0 for wall in vertical_walls)
    assert west >= 0.10 - 1e-7
    assert east <= 19.90 + 1e-7
    assert geometry["slab_openings"] and any(slab.get("physical_openings") for slab in slabs)
    assert any(item.get("type") == "stair_geometry" and item.get("geometry_status") == "resolved" for item in geometry["vertical_geometry"])

    levels = {item["name"]: item for item in intelligence["vertical_section"]["levels"]}
    assert levels["basement"]["bottom"] == pytest.approx(-2.4)
    assert levels["F1"]["bottom"] == pytest.approx(0.0)

    exports = result["exports"]
    output_dir = Path(exports["output_dir"])
    assert output_dir.parent.name == "DEFAULT" and output_dir.name.startswith(label + "_")
    ifc_model = ifcopenshell.open(exports["ifc"]["path"])
    assert len(ifc_model.by_type("IfcWall")) > 0
    assert len(ifc_model.by_type("IfcDoor")) > 0
    assert len(ifc_model.by_type("IfcWindow")) == sum(item.get("type") == "window" and item.get("geometry_status") == "resolved" for item in openings)
    assert len(ifc_model.by_type("IfcSlab")) > 0
    assert len(ifc_model.by_type("IfcRamp")) == expected_ramps

    doc = ezdxf.readfile(exports["cad"]["file"]["file"])
    msp = doc.modelspace()
    joint_entities = list(msp.query('*[layer=="SITE_SEPARATION_JOINT"]'))
    joint_lines = [entity for entity in joint_entities if entity.dxftype() == "LINE"]
    assert len(joint_lines) == 2
    joint_xs = sorted(round(float(line.dxf.start.x), 6) for line in joint_lines
                      if float(line.dxf.start.x) == pytest.approx(float(line.dxf.end.x)))
    assert joint_xs == pytest.approx([0.10, 19.90])
    assert len(list(msp.query('*[layer=="PARKING_PEDESTRIAN"]'))) >= 2
    assert len(list(msp.query('*[layer=="SECTION_STAIR"]'))) == 1
    assert len(list(msp.query('DIMENSION'))) > 0
    dwg = Path(exports["dwg"]["file"])
    assert dwg.is_file() and dwg.stat().st_size > 0 and dwg.read_bytes()[:6] == b"AC1032"
    return ifc_model, msp, output_dir


def test_full_architecture_south_basement_access_exports_one_16m_ramp():
    label = "final_architecture_south"
    model, resolved, result = _generate_and_export(
        "south_road", "south", "vehicle_ramp", 0.0, 16.0, label
    )
    ifc_model, msp, _ = _assert_complete_exports(model, result, 1, label)
    assert resolved["ramp"]["required_run"] == pytest.approx(16.0)
    assert resolved["ramp"]["start_z"] == pytest.approx(0.0)
    assert resolved["ramp"]["end_z"] == pytest.approx(-2.4)
    assert len(list(msp.query('*[layer=="VEHICLE_RAMP"]'))) >= 3
    assert len(list(msp.query('*[layer=="SECTION_RAMP"]'))) == 1
    assert len([item for item in ifc_model.by_type("IfcRamp") if item.Tag == "south_road"]) == 1


def test_full_architecture_north_basement_access_is_direct_at_minus_2_4():
    label = "final_architecture_north"
    model, resolved, result = _generate_and_export(
        "north_road", "north", "direct_at_grade", -2.4, 0.0, label
    )
    _, msp, _ = _assert_complete_exports(model, result, 0, label)
    assert resolved["ramp"] is None
    assert resolved["driveway"]["start_z"] == pytest.approx(-2.4)
    assert resolved["driveway"]["end_z"] == pytest.approx(-2.4)
    assert len(list(msp.query('*[layer=="VEHICLE_RAMP"]'))) == 0
    assert len(list(msp.query('*[layer=="SECTION_RAMP"]'))) == 0
    assert len(list(msp.query('*[layer=="DRIVEWAY"]'))) >= 1
