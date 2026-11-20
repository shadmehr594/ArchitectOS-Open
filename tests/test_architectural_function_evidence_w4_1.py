"""W4.1 — ARCHITECTURAL FUNCTION EVIDENCE CONTRACT (shadow mode).

The tests are written from the BRIEF's semantics, not from the implementation.
They pin: the evidence contract's provenance, its strength model, its
independence model, the corresponding-panel policy, the conflict/unknown
contract, and the fact that A/B/C/D behaviour is unchanged.
"""

import ast
import copy
import os
from pathlib import Path

import pytest

from core.vision.architectural_function_evidence_v1 import (
    AMBIGUOUS,
    CONFLICTED,
    CONTRACT,
    CONTRADICTING,
    CORRESPONDING_PANEL,
    DIRECT,
    DIRECT_SEMANTIC,
    EVIDENCE_STRENGTHS,
    EVIDENCE_TYPES,
    FIXTURE,
    FURNITURE,
    GEOMETRY,
    INSUFFICIENT,
    NEGATIVE_OR_CONFLICTING,
    OPENING_ACCESS,
    PROBABLE,
    RESOLUTION_STATES,
    STRONG,
    SUPPORTED,
    SUPPORTING,
    UNKNOWN,
    VERSION,
    WEAK,
    build_architectural_function_evidence,
    evidence_state_for,
)
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)
from core.vision.image_understanding_v1 import build_understanding
from core.vision.local_plan_reader_v1 import read_local_plan
from core.vision.vision_report_v1 import render_vision_report

MODULE = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "vision"
    / "architectural_function_evidence_v1.py"
)

REGION = {
    "region_id": "r1",
    "bbox_pixels": [0, 0, 200, 200],
    "confidence": "MEDIUM",
    "stable_across_gap_scales": True,
    "wall_levels": [165],
}


def _region(region_id, bbox, confidence="MEDIUM", stable=True):
    return {
        "region_id": region_id,
        "bbox_pixels": list(bbox),
        "confidence": confidence,
        "stable_across_gap_scales": stable,
        "wall_levels": [165],
    }


def _item(symbol_class, region_ids, item_id, patch, box=(10, 10, 40, 40), native=False):
    return {
        "item_id": item_id,
        "class": symbol_class,
        "supported_function": None,
        "supports_space": None,
        "region_ids": list(region_ids),
        "usable_for_space_inference": bool(region_ids),
        "evidence_type": "furniture",
        "bbox_pixels": list(box),
        "confidence": "MEDIUM",
        "source": "local_raster_symbol_topology",
        "provider_independent": True,
        "status": "visible",
        "corroboration": ["a", "b", "c"],
        "raster_patch_sha256": patch,
        "native_symbol_pass": native,
    }


def _plan(
    regions=(),
    furniture=(),
    labels=(),
    named_spaces=(),
    openings=(),
    panel_readings=None,
    fusion=None,
):
    plan = {
        "geometry_spaces": list(regions),
        "furniture": list(furniture),
        "named_spaces": list(named_spaces),
        "openings": list(openings),
        "relations": [],
        "circulation": [],
        "local_plan_reading": {"labels": list(labels)},
    }
    if panel_readings is not None:
        plan["panel_readings"] = list(panel_readings)
    if fusion is not None:
        plan["fusion"] = fusion
    return plan


def _evidence_for(plan, evidence_type=None):
    contract = build_architectural_function_evidence(plan)
    items = contract["evidence_items"]
    if evidence_type is None:
        return contract, items
    return contract, [i for i in items if i["evidence_type"] == evidence_type]


def _region_record(contract, region_id, panel_id="p1"):
    for panel in contract["panels"]:
        if panel["panel_id"] != panel_id:
            continue
        for region in panel["regions"]:
            if region["region_id"] == region_id:
                return region
    raise AssertionError("region %s not found" % region_id)


# ==================================================
# 1 — PROVENANCE
# ==================================================


def test_evidence_preserves_provenance():
    plan = _plan(
        regions=[_region("r1", (0, 0, 200, 200))],
        furniture=[_item("bed", ["r1"], "f1", "a" * 64)],
    )
    contract, items = _evidence_for(plan, FURNITURE)
    assert len(items) == 1
    item = items[0]
    for field in (
        "evidence_id",
        "evidence_type",
        "architectural_signal",
        "source_panel_id",
        "source_region_id",
        "source_item_id",
        "source_bbox",
        "source",
        "producer",
        "confidence",
        "grounding_status",
        "transport_status",
        "supporting_functions",
        "contradicting_functions",
        "evidence_strength",
        "independence_key",
        "same_underlying_evidence",
        "notes",
    ):
        assert field in item, field
    assert item["source_region_id"] == "r1"
    assert item["source_item_id"] == "f1"
    assert item["source_bbox"] == [10, 10, 40, 40]
    assert item["producer"] == "local_plan_symbols_v1"
    assert item["evidence_strength"] == SUPPORTING
    # the contract itself is versioned and declares its provenance
    assert contract["contract"] == CONTRACT
    assert contract["version"] == VERSION
    assert contract["provider_independent"] is True
    assert contract["model_independent"] is True


# ==================================================
# 2 — UNBOUND FURNITURE STAYS UNBOUND
# ==================================================


def test_unbound_furniture_remains_unbound():
    plan = _plan(
        regions=[_region("r1", (0, 0, 200, 200))],
        furniture=[_item("seating", [], "f1", "b" * 64, native=True)],
    )
    contract, items = _evidence_for(plan, FURNITURE)
    assert len(items) == 1
    item = items[0]
    assert item["source_region_id"] is None
    assert item["region_attribution_status"] == "not_transported"
    assert item["transport_status"] == "transported"
    assert item["evidence_strength"] == SUPPORTING
    assert item["evidence_id"] in contract["evidence_without_region"]
    # the item is published as UNBOUND architectural evidence, never assigned
    assert any("UNBOUND" in note for note in item["notes"])
    region = _region_record(contract, "r1")
    assert item["evidence_id"] not in region["evidence_ids"]
    assert region["furniture_evidence"] is False
    assert region["hypotheses"] == []
    assert region["region_state"] == UNKNOWN


# ==================================================
# 3 — NO REGION ID IS INVENTED
# ==================================================


def test_no_region_id_is_invented():
    plan = _plan(
        regions=[_region("r7", (0, 0, 200, 200))],
        furniture=[
            _item("bed", ["r7"], "f1", "c" * 64, box=(10, 10, 40, 40)),
            _item("seating", [], "f2", "d" * 64, box=(120, 120, 160, 160)),
        ],
    )
    contract, items = _evidence_for(plan)
    known = {"r7"}
    for item in items:
        if item["source_region_id"] is not None:
            assert item["source_region_id"] in known
    for panel in contract["panels"]:
        assert {r["region_id"] for r in panel["regions"]} == known
    # a region that the evidence does not name is never created
    assert contract["creates_region_bindings"] is False
    assert contract["creates_correspondences"] is False


# ==================================================
# 4 — INDEPENDENCE
# ==================================================


def test_duplicate_observations_from_same_source_are_not_independent():
    # Two fixture symbols backed by the SAME raster patch: one underlying
    # object, therefore ONE independent vote.
    plan = _plan(
        regions=[_region("r1", (0, 0, 200, 200))],
        furniture=[
            _item("sanitary_fixture", ["r1"], "f1", "e" * 64, box=(10, 10, 40, 40)),
            _item("sanitary_fixture", ["r1"], "f2", "e" * 64, box=(50, 50, 80, 80)),
        ],
    )
    contract = build_architectural_function_evidence(plan)
    region = _region_record(contract, "r1")
    hypothesis = region["hypotheses"][0]
    assert hypothesis["function"] == "bathroom"
    assert hypothesis["independent_sources"] == 1
    # a duplicate observation must NOT reach the fixture-cluster strength
    assert hypothesis["evidence_strength"] == SUPPORTING
    assert hypothesis["state"] == INSUFFICIENT


def test_repeated_ocr_passes_are_not_independent_evidence():
    plan = _plan(
        regions=[_region("r1", (0, 0, 200, 200))],
        labels=[
            {
                "text": "اتاق خواب",
                "semantic_function": "bedroom",
                "bbox_pixels": [20, 20, 80, 40],
                "confidence": "HIGH",
                "independent_passes": 7,
                "associated_region_id": "r1",
            }
        ],
    )
    contract, items = _evidence_for(plan, DIRECT_SEMANTIC)
    assert len(items) == 1, "seven OCR passes are ONE evidence item, not seven"
    assert items[0]["ocr_passes"] == 7
    assert items[0]["ocr_passes_are_independent_evidence"] is False


def test_distinct_classes_are_independent_and_region_geometry_is_independent():
    plan = _plan(
        regions=[_region("r1", (0, 0, 200, 200))],
        furniture=[
            _item("bed", ["r1"], "f1", "f" * 64, box=(10, 10, 60, 40)),
            _item("storage_cabinet", ["r1"], "f2", "g" * 64, box=(10, 60, 60, 90)),
        ],
    )
    contract = build_architectural_function_evidence(plan)
    region = _region_record(contract, "r1")
    hypothesis = region["hypotheses"][0]
    assert hypothesis["function"] == "bedroom"
    assert hypothesis["independent_sources"] == 2
    keys = {
        i["independence_key"]
        for i in contract["evidence_items"]
        if i["evidence_type"] in (FURNITURE, FIXTURE, GEOMETRY)
    }
    assert len(keys) == 3, "bed, wardrobe and the region geometry are independent"


# ==================================================
# 5 — CORRESPONDING PANEL TRANSPORT
# ==================================================


def test_corresponding_transport_preserves_source_identity():
    plan = _plan(
        regions=[_region("r6", (0, 0, 200, 200))],
        fusion={
            "status": "corresponding_pair",
            "geometry_panel_id": "p1",
            "corresponding_label_transfers": [
                {
                    "space": "balcony",
                    "zone": "open_semi_open",
                    "evidence": ["تراس"],
                    "evidence_type": "label",
                    "status": "label",
                    "confidence": "MEDIUM",
                    "source_panel_id": "p2",
                    "associated_region_id": "r2",
                    "corresponding_region_id": "r6",
                    "transfer": "corresponding_panel_geometric_region_match",
                }
            ],
        },
    )
    contract, items = _evidence_for(plan, CORRESPONDING_PANEL)
    assert len(items) == 1
    item = items[0]
    correspondence = item["correspondence"]
    assert correspondence["source_panel_id"] == "p2"
    assert correspondence["source_region_id"] == "r2"
    assert correspondence["target_panel_id"] == "p1"
    assert correspondence["target_region_id"] == "r6"
    assert correspondence["correspondence_method"]
    assert correspondence["same_underlying_evidence"] is True
    assert item["same_underlying_evidence"] is True
    assert item["transport_status"] == "transported"
    # W4.1 creates no new correspondence
    assert contract["creates_correspondences"] is False
    assert contract["corresponding_panel"]["created_new_correspondences"] is False


def test_existing_correspondences_are_reported_read_only():
    plan = _plan(
        regions=[_region("r6", (0, 0, 200, 200))],
        fusion={"status": "corresponding_pair", "geometry_panel_id": "p1"},
    )
    plan["local_plan_reading"] = {
        "labels": [],
        "sheet_structure": {
            "corresponding_regions": [
                {
                    "panel_ids": ["p1", "p2"],
                    "pairs": [
                        {
                            "left_region_id": "r6",
                            "right_region_id": "r2",
                            "centroid_distance_normalized": 0.11,
                            "area_ratio": 0.4,
                            "mutual_centroid_containment": True,
                        }
                    ],
                    "source": "local_normalized_region_geometry",
                }
            ]
        },
    }
    contract = build_architectural_function_evidence(plan)
    records = contract["corresponding_panel"]["existing_correspondences"]
    assert len(records) == 1
    assert records[0]["pairs"][0]["left_region_id"] == "r6"
    assert records[0]["correspondence_method"] == "local_normalized_region_geometry"


# ==================================================
# 6 — GEOMETRY ALONE CANNOT RESOLVE
# ==================================================


def test_geometry_only_evidence_cannot_become_a_resolved_function():
    plan = _plan(regions=[_region("r1", (0, 0, 400, 100))])
    contract = build_architectural_function_evidence(plan)
    region = _region_record(contract, "r1")
    assert region["geometry_only"] is True
    assert region["no_semantic_evidence"] is True
    assert region["hypotheses"] == []
    assert region["region_state"] == UNKNOWN
    assert region["resolved_function"] is None

    geometry_only = [
        i for i in contract["evidence_items"] if i["evidence_type"] == GEOMETRY
    ]
    state = evidence_state_for(geometry_only)
    assert state["state"] == UNKNOWN
    assert state["resolved_function"] is None
    assert state["hypotheses"] == []


def test_geometry_never_determines_a_function_and_position_is_excluded():
    plan = _plan(regions=[_region("r1", (0, 0, 400, 100))])
    contract, items = _evidence_for(plan, GEOMETRY)
    item = items[0]
    assert item["evidence_strength"] == WEAK
    assert item["supporting_functions"] == []
    assert item["position_used_for_function"] is False
    assert "aspect_ratio" in item
    assert contract["counts"]["region_states"] == {UNKNOWN: 1}


# ==================================================
# 7 — A SINGLE OBJECT CANNOT RESOLVE
# ==================================================


def test_single_furniture_object_cannot_become_a_resolved_function():
    plan = _plan(
        regions=[_region("r1", (0, 0, 200, 200))],
        furniture=[_item("bed", ["r1"], "f1", "h" * 64)],
    )
    contract = build_architectural_function_evidence(plan)
    region = _region_record(contract, "r1")
    hypothesis = region["hypotheses"][0]
    assert hypothesis["function"] == "bedroom"
    assert hypothesis["evidence_strength"] == SUPPORTING
    assert hypothesis["state"] == INSUFFICIENT
    assert region["region_state"] == INSUFFICIENT
    assert region["resolved_function"] is None
    assert contract["resolved_functions"] == {}
    assert contract["resolves_functions"] is False
    assert contract["resolution_withheld"] is True


def test_single_sofa_is_supportive_only():
    plan = _plan(
        regions=[_region("r1", (0, 0, 200, 200))],
        furniture=[_item("sofa", ["r1"], "f1", "i" * 64)],
    )
    contract = build_architectural_function_evidence(plan)
    region = _region_record(contract, "r1")
    hypothesis = region["hypotheses"][0]
    assert hypothesis["function"] == "living room"
    assert hypothesis["evidence_strength"] == SUPPORTING
    assert region["region_state"] == INSUFFICIENT
    assert region["resolved_function"] is None


# ==================================================
# 8 — CONFLICT IS REPRESENTABLE
# ==================================================


def test_conflicting_evidence_is_representable():
    plan = _plan(
        regions=[_region("r1", (0, 0, 200, 200))],
        furniture=[
            _item("bed", ["r1"], "f1", "j" * 64, box=(10, 10, 60, 40)),
            _item("sanitary_fixture", ["r1"], "f2", "k" * 64, box=(100, 10, 130, 40)),
            _item("sanitary_fixture", ["r1"], "f3", "l" * 64, box=(100, 60, 130, 90)),
        ],
    )
    contract = build_architectural_function_evidence(plan)
    region = _region_record(contract, "r1")
    functions = {h["function"] for h in region["hypotheses"]}
    assert functions == {"bedroom", "bathroom"}
    assert region["region_state"] == CONFLICTED
    # CONFLICTED is representable but is NEVER resolved
    assert region["resolved_function"] is None
    assert contract["resolved_functions"] == {}
    assert CONFLICTED in RESOLUTION_STATES
    # the conflict itself is published as evidence, at CONTRADICTING strength
    conflicts = [
        i
        for i in contract["evidence_items"]
        if i["evidence_type"] == NEGATIVE_OR_CONFLICTING
    ]
    assert len(conflicts) == 1
    assert conflicts[0]["evidence_strength"] == CONTRADICTING
    assert conflicts[0]["supporting_functions"] == []
    assert set(conflicts[0]["contradicting_functions"]) == {"bedroom", "bathroom"}
    assert conflicts[0]["source_region_id"] == "r1"
    assert conflicts[0]["evidence_id"] in region["evidence_ids"]
    assert NEGATIVE_OR_CONFLICTING in EVIDENCE_TYPES
    assert CONTRADICTING in EVIDENCE_STRENGTHS


# ==================================================
# 9 — UNKNOWN / INSUFFICIENT ARE REPRESENTABLE
# ==================================================


def test_unknown_and_insufficient_are_representable():
    assert set(RESOLUTION_STATES) == {
        SUPPORTED,
        PROBABLE,
        AMBIGUOUS,
        CONFLICTED,
        INSUFFICIENT,
        UNKNOWN,
    }
    empty = _plan(regions=[])
    contract = build_architectural_function_evidence(empty)
    assert contract["panels"][0]["regions"] == []

    geometry_only = _plan(regions=[_region("r1", (0, 0, 100, 100))])
    assert _region_record(
        build_architectural_function_evidence(geometry_only), "r1"
    )["region_state"] == UNKNOWN

    single = _plan(
        regions=[_region("r1", (0, 0, 200, 200))],
        furniture=[_item("bed", ["r1"], "f1", "m" * 64)],
    )
    assert _region_record(
        build_architectural_function_evidence(single), "r1"
    )["region_state"] == INSUFFICIENT

    assert evidence_state_for([])["state"] == UNKNOWN
    assert evidence_state_for([])["resolved_function"] is None


# ==================================================
# 10 — GROUNDED LABEL IS DIRECT
# ==================================================


def test_grounded_label_evidence_can_be_direct():
    plan = _plan(
        regions=[_region("r1", (0, 0, 200, 200))],
        labels=[
            {
                "text": "آشپزخانه",
                "semantic_function": "kitchen",
                "bbox_pixels": [20, 20, 80, 40],
                "confidence": "MEDIUM",
                "independent_passes": 6,
                "associated_region_id": "r1",
            }
        ],
    )
    contract, items = _evidence_for(plan, DIRECT_SEMANTIC)
    assert items[0]["evidence_strength"] == DIRECT
    assert items[0]["grounding_status"] == "grounded"
    assert items[0]["region_attribution_status"] == "bound"
    region = _region_record(contract, "r1")
    assert region["grounded_text_evidence"] is True
    assert region["hypotheses"][0]["function"] == "kitchen"
    assert region["hypotheses"][0]["evidence_strength"] == DIRECT
    assert region["hypotheses"][0]["state"] == SUPPORTED
    # SUPPORTED is a representable state, never a resolution
    assert region["resolved_function"] is None
    assert contract["resolved_functions"] == {}


def test_grounded_label_without_recorded_enclosure_binding_stays_unattributed():
    plan = _plan(
        regions=[_region("r1", (0, 0, 200, 200))],
        labels=[
            {
                "text": "پذیرایی",
                "semantic_function": "living room",
                "bbox_pixels": [20, 20, 80, 40],
                "confidence": "HIGH",
                "independent_passes": 4,
                "associated_region_id": None,
            }
        ],
    )
    contract, items = _evidence_for(plan, DIRECT_SEMANTIC)
    assert items[0]["source_region_id"] is None
    assert items[0]["region_attribution_status"] == "not_recorded_in_trusted_data"
    assert items[0]["evidence_id"] in contract["evidence_without_region"]
    region = _region_record(contract, "r1")
    assert region["grounded_text_evidence"] is False
    assert region["hypotheses"] == []


# ==================================================
# 11 — STRONG COMBINATIONS ARE REPRESENTABLE WITHOUT RESOLVING
# ==================================================


def test_bed_plus_wardrobe_is_strong_sleeping_without_resolving():
    plan = _plan(
        regions=[_region("r1", (0, 0, 200, 200))],
        furniture=[
            _item("bed", ["r1"], "f1", "n" * 64, box=(10, 10, 60, 40)),
            _item("storage_cabinet", ["r1"], "f2", "o" * 64, box=(10, 60, 60, 90)),
        ],
    )
    contract = build_architectural_function_evidence(plan)
    region = _region_record(contract, "r1")
    hypothesis = region["hypotheses"][0]
    assert hypothesis["function"] == "bedroom"
    assert hypothesis["evidence_strength"] == STRONG
    assert hypothesis["state"] == SUPPORTED
    assert hypothesis["independent_sources"] == 2
    assert region["resolved_function"] is None
    assert contract["resolved_functions"] == {}


def test_counter_plus_basin_is_strong_kitchen_without_resolving():
    plan = _plan(
        regions=[_region("r1", (0, 0, 200, 200))],
        furniture=[
            _item("kitchen_counter", ["r1"], "f1", "p" * 64, box=(10, 10, 80, 30)),
            _item(
                "kitchen_sink_arrangement",
                ["r1"],
                "f2",
                "q" * 64,
                box=(90, 10, 120, 30),
            ),
        ],
    )
    contract = build_architectural_function_evidence(plan)
    region = _region_record(contract, "r1")
    hypothesis = region["hypotheses"][0]
    assert hypothesis["function"] == "kitchen"
    assert hypothesis["evidence_strength"] == STRONG
    assert hypothesis["independent_sources"] == 2
    assert region["resolved_function"] is None


def test_dining_surface_plus_seating_is_strong_dining_without_resolving():
    plan = _plan(
        regions=[_region("r1", (0, 0, 200, 200))],
        furniture=[
            _item("dining_surface", ["r1"], "f1", "r" * 64, box=(10, 10, 80, 60)),
            _item("chair", ["r1"], "f2", "s" * 64, box=(10, 70, 30, 90)),
            _item("chair", ["r1"], "f3", "t" * 64, box=(60, 70, 80, 90)),
        ],
    )
    contract = build_architectural_function_evidence(plan)
    region = _region_record(contract, "r1")
    dining = [h for h in region["hypotheses"] if h["function"] == "dining"][0]
    assert dining["evidence_strength"] == STRONG
    assert dining["state"] == SUPPORTED
    assert region["resolved_function"] is None


def test_untrusted_enclosure_caps_strength_at_supporting():
    plan = _plan(
        regions=[_region("r1", (0, 0, 200, 200), confidence="LOW")],
        furniture=[
            _item("bed", ["r1"], "f1", "u" * 64, box=(10, 10, 60, 40)),
            _item("storage_cabinet", ["r1"], "f2", "v" * 64, box=(10, 60, 60, 90)),
        ],
    )
    contract = build_architectural_function_evidence(plan)
    region = _region_record(contract, "r1")
    assert region["trusted_region"] is False
    hypothesis = region["hypotheses"][0]
    assert hypothesis["evidence_strength"] == SUPPORTING
    assert hypothesis["state"] == INSUFFICIENT
    assert "capped" in hypothesis["reason"]


# ==================================================
# VOCABULARY / ENVELOPE
# ==================================================


def test_contract_declares_every_required_evidence_type_and_strength():
    assert set(EVIDENCE_TYPES) == {
        "direct_semantic",
        "furniture",
        "fixture",
        "opening_access",
        "adjacency",
        "circulation",
        "geometry",
        "corresponding_panel",
        "negative_or_conflicting",
    }
    assert set(EVIDENCE_STRENGTHS) == {
        DIRECT,
        STRONG,
        SUPPORTING,
        WEAK,
        CONTRADICTING,
    }


def test_opening_and_relation_evidence_never_resolve_a_function():
    plan = _plan(
        regions=[_region("r1", (0, 0, 200, 200))],
        openings=[
            {
                "kind": "door",
                "instances": [
                    {
                        "kind": "door",
                        "bbox_pixels": [90, 90, 110, 110],
                        "confidence": "MEDIUM",
                        "raster_patch_sha256": "w" * 64,
                    }
                ],
            }
        ],
    )
    contract, items = _evidence_for(plan, OPENING_ACCESS)
    assert len(items) == 1
    assert items[0]["evidence_strength"] == WEAK
    assert items[0]["supporting_functions"] == []
    assert items[0]["source_region_id"] == "r1"
    region = _region_record(contract, "r1")
    assert region["access_opening_evidence"] is True
    assert region["hypotheses"] == []
    assert region["resolved_function"] is None


def test_builder_is_pure_and_does_not_mutate_the_plan():
    plan = _plan(
        regions=[_region("r1", (0, 0, 200, 200))],
        furniture=[_item("bed", ["r1"], "f1", "x" * 64)],
    )
    snapshot = copy.deepcopy(plan)
    build_architectural_function_evidence(plan)
    assert plan == snapshot


def test_empty_and_malformed_input_is_safe():
    assert build_architectural_function_evidence(None)["evidence_items"] == []
    assert build_architectural_function_evidence("nope")["evidence_items"] == []
    assert build_architectural_function_evidence({})["contract"] == CONTRACT


# ==================================================
# 12-18 — REAL A/B/C/D BEHAVIOUR UNCHANGED
# ==================================================

PATHS = {
    key: Path(os.environ.get("ARCHITECTOS_PLAN_" + key, "__missing_private_image__"))
    for key in "ABCD"
}

PROMPT = "خودتو جای یه معمار بزار و این پلان رو آنالیز کن"


@pytest.fixture(scope="module")
def four_images():
    if not all(p.is_file() for p in PATHS.values()):
        pytest.skip(
            "Provide private ARCHITECTOS_PLAN_A/B/C/D; synthetic tests are not "
            "real acceptance"
        )
    out = {}
    for key, path in PATHS.items():
        local = read_local_plan(path)
        raw = {
            "image_type": "floor_plan_or_sketch",
            "confidence": "HIGH",
            "observed": ["floor plan"],
            "furniture_elements": [],
            "architectural_elements": [],
            "local_plan_reading": local,
        }
        understanding = build_understanding(raw, provider="w4-1-acceptance", model="stub")
        out[key] = interpret_architectural_vision(understanding, user_text=PROMPT)
    return out


def _signature(plan):
    return [
        (entry.get("space"), entry.get("region_id"), entry.get("evidence"))
        for entry in plan.get("inferred_functions") or []
    ]


def test_A_behaviour_unchanged(four_images):
    plan = four_images["A"]["plan_reading"]
    assert plan["inferred_functions"] == []
    assert [e.get("space") for e in plan["named_spaces"]] == [
        "balcony",
        "bedroom",
        "kitchen",
        "bathroom",
        "wc",
        "living room",
    ]
    assert len(plan["geometry_spaces"]) == 9
    assert plan["furniture"] == []
    assert plan["local_plan_reading"]["status"] == "grounded"
    assert len(plan["local_plan_reading"]["labels"]) == 9
    assert plan["architectural_function_evidence"]["contract"] == CONTRACT


def test_B_behaviour_unchanged(four_images):
    plan = four_images["B"]["plan_reading"]
    assert _signature(plan) == [
        ("bedroom", "r6", ["f1"]),
        ("living room", "r1", ["f2", "f3", "f4"]),
        ("bedroom", "r2", ["f5"]),
        ("bathroom", "r5", ["f6"]),
        ("kitchen", "r1", ["f7", "f8"]),
        ("dining", "r1", ["f9"]),
    ]
    assert len(plan["furniture"]) == 11
    assert len(plan["geometry_spaces"]) == 6
    assert plan["architectural_function_evidence"]["contract"] == CONTRACT


def test_C_behaviour_unchanged(four_images):
    plan = four_images["C"]["plan_reading"]
    assert _signature(plan) == [
        ("living room", "r4", ["f1"]),
        ("bathroom", "r3", ["f2", "f4"]),
        ("bedroom", "r4", ["f3"]),
    ]
    assert len(plan["furniture"]) == 4
    assert len(plan["geometry_spaces"]) == 4
    assert plan["architectural_function_evidence"]["contract"] == CONTRACT


def test_D_inferred_functions_empty_native_furniture_unbound_and_unit_none(
    four_images,
):
    plan = four_images["D"]["plan_reading"]
    assert plan["inferred_functions"] == []
    assert [
        entry.get("region_ids") for entry in plan.get("furniture") or []
    ] == [[], []]
    assert (plan["spatial_organization"] or {}).get("unit_count_candidate") is None
    evidence = plan["architectural_function_evidence"]
    assert evidence["contract"] == CONTRACT
    # the two native items are published as UNBOUND evidence
    unbound = [
        item
        for item in evidence["evidence_items"]
        if item["evidence_type"] in (FURNITURE, FIXTURE)
    ]
    assert len(unbound) == 2
    assert all(item["source_region_id"] is None for item in unbound)
    assert all(item["region_attribution_status"] == "not_transported" for item in unbound)


def test_D_roles_unchanged(four_images):
    plan = four_images["D"]["plan_reading"]
    assert [p["role"] for p in plan["panel_readings"]] == [
        "dimension_plan",
        "furnished_architectural_plan",
    ]
    assert plan["fusion"]["status"] == "corresponding_pair"
    assert plan["local_plan_reading"]["sheet_structure"]["sheet_type"] == "plan_pair"


@pytest.mark.parametrize("name", list("ABCD"))
def test_evidence_contract_does_not_change_the_rendered_report(four_images, name):
    interpretation = four_images[name]
    plan = interpretation["plan_reading"]
    with_evidence = render_vision_report(interpretation, "fa")
    stripped = copy.deepcopy(interpretation)
    stripped["plan_reading"].pop("architectural_function_evidence", None)
    without_evidence = render_vision_report(stripped, "fa")
    assert with_evidence == without_evidence
    assert plan["architectural_function_evidence"]["resolves_functions"] is False


@pytest.mark.parametrize("name", list("ABCD"))
def test_every_region_is_published_without_a_resolved_function(four_images, name):
    evidence = four_images[name]["plan_reading"]["architectural_function_evidence"]
    assert evidence["resolved_functions"] == {}
    assert evidence["resolution_withheld"] is True
    assert evidence["changes_inferred_functions"] is False
    assert evidence["changes_named_spaces"] is False
    assert evidence["changes_unit_count"] is False
    assert evidence["changes_role_classification"] is False
    for panel in evidence["panels"]:
        for region in panel["regions"]:
            assert region["resolved_function"] is None
            assert region["resolution_withheld"] is True


# ==================================================
# 19 — W3.5 REMAINS DISABLED
# ==================================================


def test_w3_5_small_text_recovery_remains_disabled():
    from core.vision.small_architectural_text_v1 import SMALL_TEXT_RECOVERY_ENABLED

    assert SMALL_TEXT_RECOVERY_ENABLED is False


# ==================================================
# 20 — NO FROZEN SUBSYSTEM IMPORT / DEPENDENCY ADDED
# ==================================================

FORBIDDEN_MODULE_TOKENS = (
    "comfy",
    "house_diffusion",
    "housediffusion",
    "rplan",
    "bim",
    "ifc",
    "cad",
    "autocad",
    "structure",
    "voice",
    "teaching",
    "knowledge_promotion",
    "render",
)


def test_no_frozen_subsystem_import_or_dependency_added():
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    for module in imported:
        lowered = module.lower()
        for token in FORBIDDEN_MODULE_TOKENS:
            assert token not in lowered, "%s imports a frozen subsystem (%s)" % (
                MODULE.name,
                module,
            )

    # The module must not reach the network, write state, or call a renderer.
    # `dict.get` is ubiquitous and legitimate, so the check is on the module
    # that owns the call, not on the attribute name alone.
    for module in imported:
        assert not module.lower().startswith(("requests", "urllib", "http")), module
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            calls.add(node.func.attr)
    for forbidden in ("post", "save", "record", "imwrite", "write_text", "render"):
        assert forbidden not in calls, "unexpected call: %s" % forbidden
    # The contract must define no assistant / agent / service class.
    for node in ast.walk(tree):
        assert not isinstance(node, ast.ClassDef), "unexpected class definition"


def test_shadow_wiring_is_additive_only():
    """The interpreter and the sheet module attach the contract additively."""
    interpreter = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "vision"
        / "architectural_vision_interpreter_v1.py"
    ).read_text(encoding="utf-8")
    sheet = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "vision"
        / "local_plan_sheet_v1.py"
    ).read_text(encoding="utf-8")
    for source in (interpreter, sheet):
        assert "build_architectural_function_evidence" in source
        assert '["architectural_function_evidence"]' in source
    # the evidence is attached to the plan reading, never to a frozen field
    assert 'plan_reading["architectural_function_evidence"]' in interpreter
