import os

import ezdxf
import ifcopenshell
import pytest

from core.architecture.geometry.architectural_geometry_engine_v2 import (
    ArchitecturalGeometryEngineV2,
)
from core.architecture.geometry.architectural_geometry_intent_generator_v1 import (
    ArchitecturalGeometryIntentGeneratorV1,
)
from core.integration.design_bim_bridge import DesignBIMBridge


def _build_stair(levels, zone, *, flight_count=1, landing_depth=None, conflicts=None,
                 maximum_riser=0.18, minimum_tread=0.28, clear_width=1.2):
    parameters = {
        "stair_type": "private_stair",
        "maximum_riser": maximum_riser,
        "minimum_tread": minimum_tread,
        "clear_width": clear_width,
        "flight_count": flight_count,
        "landing_required": flight_count > 1,
        "headroom": 2.1,
        "conflict_evidence_complete": True,
        "conflict_zones": conflicts or [],
    }
    if landing_depth is not None:
        parameters["landing_depth"] = landing_depth
    placement = {
        "vertical_core": [{
            "id": "main_stair",
            "type": "stairs",
            "connects": [levels[0]["name"], levels[-1]["name"]],
            "placement_intent": {"protected_zone": {"points": zone}},
            "protected_zone": True,
            "parameters": parameters,
            "source_evidence": {"system": "test_explicit_architectural_contract"},
        }]
    }
    vertical = {"levels": levels, "roof_level": levels[-1]["top"]}
    intent = ArchitecturalGeometryIntentGeneratorV1().generate(
        placement, vertical_section=vertical
    )
    geometry = ArchitecturalGeometryEngineV2().generate(intent)
    geometry["vertical_section"] = vertical
    geometry["architectural_authority"] = True
    geometry["geometry_source"] = "ArchitecturalGeometryEngineV2"
    return intent, geometry, vertical


def test_simple_stair_uses_level_evidence_and_exact_riser_sum():
    levels = [
        {"name": "ground", "bottom": 0.0, "top": 3.2, "height": 3.2},
        {"name": "upper", "bottom": 3.2, "top": 6.4, "height": 3.2},
    ]
    _, geometry, _ = _build_stair(
        levels, [[10, 10], [20, 10], [20, 12], [10, 12]]
    )
    stair = geometry["vertical_geometry"][0]
    assert stair["geometry_status"] == "resolved"
    assert stair["start_z"] == pytest.approx(0.0)
    assert stair["end_z"] == pytest.approx(3.2)
    assert stair["total_rise"] == pytest.approx(3.2)
    assert stair["riser_count"] == 18
    assert stair["riser_height"] == pytest.approx(3.2 / 18)
    assert stair["riser_count"] * stair["riser_height"] == pytest.approx(stair["total_rise"])
    assert stair["tread_count"] == 17
    assert stair["tread_depth"] == pytest.approx(0.28)
    assert stair["start_point"] and stair["end_point"]
    assert stair["start_point"] != [0, 0]
    assert stair["slab_opening"]["host_level"] == "upper"
    assert geometry["slab_openings"] == [stair["slab_opening"]]


def test_nonstandard_elevations_and_two_flights_have_real_landing():
    levels = [
        {"name": "split_low", "bottom": 0.60, "top": 3.64, "height": 3.04},
        {"name": "split_high", "bottom": 3.64, "top": 6.60, "height": 2.96},
    ]
    _, geometry, _ = _build_stair(
        levels, [[11, 7], [17, 7], [17, 11], [11, 11]],
        flight_count=2, landing_depth=1.2,
    )
    stair = geometry["vertical_geometry"][0]
    assert (stair["start_z"], stair["end_z"], stair["total_rise"]) == pytest.approx((0.60, 3.64, 3.04))
    assert stair["flight_count"] == 2
    assert len(stair["flights"]) == 2
    assert len(stair["landings"]) == 1
    assert sum(flight["riser_count"] for flight in stair["flights"]) == stair["riser_count"]
    assert sum(flight["end_z"] - flight["start_z"] for flight in stair["flights"]) == pytest.approx(3.04)
    assert stair["landings"][0]["polygon"]


def test_stair_fails_closed_when_core_is_too_small_or_rules_are_missing():
    levels = [
        {"name": "ground", "bottom": 0.0, "top": 3.2, "height": 3.2},
        {"name": "upper", "bottom": 3.2, "top": 6.4, "height": 3.2},
    ]
    _, geometry, _ = _build_stair(
        levels, [[20, 20], [22, 20], [22, 21], [20, 21]]
    )
    stair = geometry["vertical_geometry"][0]
    assert stair["geometry_status"] == "core_footprint_insufficient"
    assert stair["placement_status"] == "failed_closed"
    assert not geometry["slab_openings"]

    _, missing, _ = _build_stair(
        levels, [[20, 20], [30, 20], [30, 23], [20, 23]],
        maximum_riser=None,
    )
    assert missing["vertical_geometry"][0]["geometry_status"] == "insufficient_evidence"
    assert "maximum_riser" in missing["vertical_geometry"][0]["missing_evidence"]

    _, conflicted, _ = _build_stair(
        levels, [[20, 20], [30, 20], [30, 23], [20, 23]],
        conflicts=[{"id": "protected_core", "polygon": [[20, 20], [30, 20], [30, 23], [20, 23]]}],
    )
    assert conflicted["vertical_geometry"][0]["geometry_status"] == "placement_conflict"
    assert conflicted["vertical_geometry"][0]["placement_status"] == "failed_closed"
    assert not conflicted["slab_openings"]


def test_authoritative_stair_survives_bim_and_real_exports():
    levels = [
        {"name": "ground", "bottom": 0.0, "top": 3.2, "height": 3.2},
        {"name": "upper", "bottom": 3.2, "top": 6.4, "height": 3.2},
    ]
    intent, geometry, vertical = _build_stair(
        levels, [[14, 9], [20, 9], [20, 13], [14, 13]],
        flight_count=2, landing_depth=1.2,
    )
    result = DesignBIMBridge().run_bim({
        "architectural_geometry": geometry,
        "geometry": geometry,
        "geometry_intent": intent,
        "vertical_section": vertical,
        "generate_structure": False,
        "run_id": "authoritative_stair_acceptance",
        "export_session": "DEFAULT",
    })["bim_result"]
    stair = result["geometry"]["stairs"][0]
    assert stair == geometry["vertical_geometry"][0]
    assert result["geometry"]["slab_openings"] == geometry["slab_openings"]
    exports = result["exports"]
    assert exports["status"] == "completed"
    assert "authoritative_stair_acceptance_" in exports["run_id"]
    assert os.path.isdir(exports["output_dir"])

    model = ifcopenshell.open(exports["ifc"]["path"])
    stairs = model.by_type("IfcStair")
    flights = model.by_type("IfcStairFlight")
    assert len(stairs) == 1 and stairs[0].Representation is not None
    assert len(flights) == 2
    assert all(flight.Representation is not None for flight in flights)
    assert [flight.NumberOfRisers for flight in flights] == [9, 9]
    assert all(flight.ContainedInStructure for flight in flights)
    assert [(storey.Name, storey.Elevation) for storey in model.by_type("IfcBuildingStorey")] == [
        ("Level ground", 0.0),
        ("Level upper", 3.2),
    ]

    document = ezdxf.readfile(exports["cad"]["file"]["file"])
    modelspace = document.modelspace()
    layers = {entity.dxf.layer for entity in modelspace}
    assert {"STAIR", "STAIR_FLIGHT", "STAIR_LANDING", "STAIR_DIRECTION", "STAIR_TEXT"} <= layers
    assert len(modelspace.query('LWPOLYLINE[layer=="STAIR_FLIGHT"]')) == 2
    labels = [entity.dxf.text for entity in modelspace.query('TEXT[layer=="STAIR_TEXT"]')]
    assert any(label == "UP" for label in labels)
    assert any("START +0.00" in label for label in labels)
    assert any("END +3.20" in label for label in labels)
    if exports.get("dwg", {}).get("file"):
        with open(exports["dwg"]["file"], "rb") as stream:
            assert stream.read(2) == b"AC"
