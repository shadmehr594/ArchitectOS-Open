from pathlib import Path

import pytest

from core.architecture.reasoning.site_reasoner import SiteReasoner
from core.cad.cad_import_engine import CADImportEngine


SOURCE = Path(__file__).parents[1] / "data" / "site_polygon_test.dxf"


def test_closed_lwpolyline_parcel_2_site_contract():
    imported = CADImportEngine().load(
        {"file_object": str(SOURCE)},
        target_parcel=2,
    )

    parcel = imported["parcel"]
    assert parcel["source"] == "closed_lwpolyline"
    assert parcel["handle"] == "1176"
    assert parcel["closed"] is True
    assert parcel["valid"] is True
    assert parcel["target_parcel"] == 2
    assert parcel["area"] == pytest.approx(200.0, abs=0.01)
    assert parcel["perimeter"] == pytest.approx(60.0, abs=0.01)
    assert parcel["elevation_ignored_for_2d"] == pytest.approx(45.46)
    assert all(len(point) == 2 for point in parcel["points"])

    assert imported["scale"] == 1.0
    assert imported["geometry"]["unit_resolution"]["header_insunits"] == 1
    assert imported["geometry"]["unit_resolution"]["header_ignored"] is True

    adjacency = imported["constraints"]["constraints"]["adjacency"]
    neighbors = {
        edge["parcel_id"]
        for edge in adjacency
        if edge["type"] == "neighbor_parcel"
    }
    assert neighbors == {"1", "3", "29"}

    site = imported["site"]
    assert site["boundary"]["type"] == "polygon"
    assert len(site["boundary"]["points"]) == 4

    analysis = SiteReasoner().analyze(site)
    strategy = analysis["building_strategy"]
    assert strategy["target_parcel"] == 2
    assert strategy["parcel_area"] == pytest.approx(200.0, abs=0.01)
    assert strategy["parcel_geometry_status"] == "resolved"
    assert len(strategy["parcel_boundary"]) == 4
    assert analysis["access_strategy"]["access_status"] == "resolved_from_cad"
    assert analysis["access_strategy"]["road_width"] == pytest.approx(10.0)
