from copy import deepcopy
import json

from shapely.geometry import LineString, Point, Polygon

from core.architecture.reasoning.evidence_based_site_resource_region_derivation_v1 import EvidenceBasedSiteResourceRegionDerivationV1


def test_source_evidence_is_recursively_json_safe_complete_and_non_mutating():
    parcel=Polygon([(0,0),(8,0),(8,6),(0,6)])
    edge=LineString([(0,0),(8,0)])
    nested_point=Point(2,3)
    evidence=[{
        "evidence_id":"frontage",
        "geometry":edge,
        "floor_scope":["ground"],
        "usable_fraction":1.0,
        "is_frontage":True,
        "provenance":[{"contract":"EvidenceV1","nested":{"items":["a",{"geometry":nested_point}]}}],
        "confidence":1.0,
    }]
    interior={"evidence_id":"interior","geometry_metadata":{"reference":Point(4,4)},
              "floor_scope":["ground"],"provenance":[{"contract":"InteriorV1"}]}
    edge_before=edge.wkb; point_before=nested_point.wkb; evidence_before=deepcopy(evidence); interior_before=deepcopy(interior)
    result=EvidenceBasedSiteResourceRegionDerivationV1().derive(parcel,evidence,["ground"],interior)
    published=[resource["source_evidence"] for resource in result["resource_regions"]]
    serialized=json.dumps(published,ensure_ascii=False,sort_keys=True)
    serialized_again=json.dumps(published,ensure_ascii=False,sort_keys=True)
    assert serialized==serialized_again
    source=result["resource_regions"][0]["source_evidence"]
    assert source["geometry"]["type"]=="LineString"
    assert source["geometry"]["coordinates"]==((0.0,0.0),(8.0,0.0)) or source["geometry"]["coordinates"]==[[0.0,0.0],[8.0,0.0]]
    assert source["provenance"][0]["nested"]["items"][1]["geometry"]["type"]=="Point"
    interior_source=result["resource_regions"][-1]["source_evidence"]
    assert interior_source["geometry_metadata"]["reference"]["type"]=="Point"
    assert edge.wkb==edge_before and nested_point.wkb==point_before
    assert evidence==evidence_before and interior==interior_before
