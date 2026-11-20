from pathlib import Path

import pytest

from core.reference_acceptance.reference_dxf_evidence_adapter import (
    ReferenceDXFEvidenceAdapter,
)
from core.reference_acceptance.reference_acceptance_comparator import (
    ReferenceAcceptanceComparator,
)


REFERENCE = (
    Path(__file__).resolve().parents[2]
    / "exports"
    / "DEFAULT"
    / "reference_analysis"
    / "آلبوم نقشه ها.dxf"
)


@pytest.fixture(scope="module")
def contract():
    return ReferenceDXFEvidenceAdapter().extract(
        REFERENCE,
        user_metadata={
            "building_type": "villa",
            "storeys": 1,
            "site_datum": {"elevation": 0.0},
            "finished_floor": {"level": "F1", "elevation": 0.4},
            "entrance_platform": {"elevation": 0.4},
            "exterior_steps": {
                "total_rise": 0.4,
                "riser_count": 2,
                "riser_height": 0.2,
            },
        },
    )


def test_file_identity_header_and_raw_inventory_are_authoritative(contract):
    assert contract["mode"] == "read_only_evidence_extraction"
    assert contract["file_identity"]["sha256"] == (
        "5f9448821acb078cbbcf71e0fa48de7741def8965cf2e24d68cc6c8c4588889c"
    )
    assert contract["dxf"]["version"]["value"] == "AC1032"
    assert contract["dxf"]["declared_units"]["value"] == {
        "code": 6,
        "name": "meters",
    }
    assert contract["modelspace"]["entity_count"] == 3143
    assert contract["modelspace"]["entity_counts"]["DIMENSION"] == 43


def test_geometry_insert_transforms_and_provenance_are_preserved(contract):
    assert contract["modelspace"]["inserts"]
    insert = contract["modelspace"]["inserts"][0]
    assert len(insert["geometry"]["transform_matrix"]) == 4
    assert insert["provenance"]["handle"] == insert["handle"]
    assert insert["provenance"]["source_file"] == str(REFERENCE.resolve())

    lines = [
        entity
        for entity in contract["modelspace"]["entities"]
        if entity["entity_type"] == "LINE"
    ]
    assert lines and lines[0]["geometry"]["start"] and lines[0]["geometry"]["end"]
    assert all(entity["geometry_status"] == "AUTHORITATIVE" for entity in lines)


def test_text_dimensions_hatches_blocks_and_sources_survive(contract):
    texts = contract["modelspace"]["texts"]
    assert any(item["geometry"]["plain_text"] == "FLOOR PLAN" for item in texts)
    assert all("encoding" in item for item in texts)
    measurements = {
        round(item["geometry"]["measurement"], 2)
        for item in contract["modelspace"]["dimensions"]
        if item["geometry"]["measurement"] is not None
    }
    assert {8.65, 13.25, 6.05, 5.2, 2.0} <= measurements
    assert len(contract["modelspace"]["hatches"]) == 2
    assert len(contract["blocks"]) == 101
    assert contract["xrefs"] == []


def test_views_are_clustered_without_inventing_a_second_storey(contract):
    views = contract["views"]
    assert [view["probable_view_type"] for view in views].count("floor_plan") == 2
    assert [view["probable_view_type"] for view in views].count("elevation") == 2
    assert {view["title_text"] for view in views} == {
        "FLOOR PLAN",
        "SOUTH ELEVATION",
        "NORTH ELEVATION",
    }
    metadata = {
        fact["fact_type"]: fact
        for fact in contract["facts"]
        if fact["provenance"]["source_entity"] == "USER_METADATA"
    }
    assert metadata["storeys"]["value"] == 1
    assert metadata["storeys"]["status"] == "AUTHORITATIVE"
    relationship = contract["view_relationships"][0]
    assert relationship["status"] == "UNRESOLVED"
    assert relationship["classification"] != "distinct_storeys"


def test_normalized_frames_forbid_deformation(contract):
    for view in contract["views"]:
        frame = view["normalized_frame"]
        assert frame["scale"] == 1.0
        assert frame["deformation_allowed"] is False
        assert frame["allowed_alignment"] == ["translation", "rotation"]


def test_benchmark_level_and_step_evidence_keeps_full_provenance(contract):
    texts = {item["handle"]: item for item in contract["modelspace"]["texts"]}
    assert texts["4E47"]["geometry"]["plain_text"] == "+0.00"
    assert texts["4E7B"]["geometry"]["plain_text"] == "+0.40"
    assert texts["4EC7"]["geometry"]["plain_text"] == "n:2"
    assert texts["4EC8"]["geometry"]["plain_text"] == "h:0.20"
    assert texts["4EC7"]["provenance"]["source_layer"] == "0"

    metadata = {
        fact["fact_type"]: fact for fact in contract["facts"]
        if fact["provenance"]["source_entity"] == "USER_METADATA"
    }
    assert metadata["site_datum"]["status"] == "AUTHORITATIVE"
    assert metadata["finished_floor"]["value"]["elevation"] == pytest.approx(0.4)
    assert metadata["exterior_steps"]["value"]["riser_count"] == 2


def test_only_authoritative_facts_are_hard_assertions(contract):
    assert contract["evidence_policy"] == {
        "hard_assertion_status": "AUTHORITATIVE",
        "soft_score_status": "INFERRED",
        "excluded_from_acceptance_status": "UNRESOLVED",
    }
    assert all(
        fact["status"] in {"AUTHORITATIVE", "INFERRED", "UNRESOLVED"}
        for fact in contract["facts"]
    )


def test_comparison_is_evidence_gated_and_does_not_assert_unresolved_topology(contract):
    comparison = ReferenceAcceptanceComparator().compare(
        contract,
        {
            "prompt": "one-storey villa",
            "architectural_intent": {
                "building_type": "villa",
                "levels": {"total": 1},
            },
            "architecture_first": False,
            "geometry": {"rooms": []},
            "exports": {"status": "failed", "error": "acceptance probe"},
            "export_files": {},
        },
    )
    semantic = comparison["sections"]["Semantic"]
    assert semantic["hard_failures"] == 0
    topology = comparison["sections"]["Topological"]["checks"][0]
    assert topology["result"] == "NOT_ASSERTED"
    assert topology["reference_status"] == "UNRESOLVED"
    assert comparison["sections"]["Geometric"]["hard_failures"] == 1
    assert comparison["sections"]["Representational"]["hard_failures"] == 3
