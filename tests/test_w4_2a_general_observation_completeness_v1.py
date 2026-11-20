# ==========================================================
# W4.2A-8 — GENERAL RAW-RASTER ARCHITECTURAL OBSERVATION COMPLETENESS
#
# The observation layer used to answer a Persian "report the architectural
# observations" turn with three objects (entrance / window / kitchen) and
# leaked internal English evidence IDs into Persian prose.
#
# These tests pin the general behaviour. They build GROUNDED LOCAL raster
# evidence (the same validated contract shape the local reader emits) and
# assert what the observation layer does with it. They never reference the
# acceptance image, its filename, its hash or its coordinates.
#
#   .venv/Scripts/python.exe -m pytest tests/test_w4_2a_general_observation_completeness_v1.py
#   .venv/Scripts/python.exe tests/test_w4_2a_general_observation_completeness_v1.py
# ==========================================================


import copy
import json
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if ROOT not in sys.path:

    sys.path.insert(0, ROOT)


from core.vision.vision_observation_mode_v1 import (  # noqa: E402
    build_observation,
    render_observation,
    detect_observation_request,
    detect_interpretation_request,
)


_SHA = "a" * 64

_RESULTS = []


def _check(name, passed, detail=None):

    _RESULTS.append((name, bool(passed), detail))


# ----------------------------------------------------------
# SYNTHETIC GROUNDED LOCAL EVIDENCE (validated contract shape)
# ----------------------------------------------------------

def _element(type_, box, *, status="visible", geometry=None, attributes=None,
             corroboration=None):

    return {
        "type": type_,
        "class": type_,
        "kind": type_,
        "bbox_pixels": list(box),
        "bbox_normalized": [0.1, 0.1, 0.2, 0.2],
        "geometry": geometry if geometry is not None else {"orientation": "vertical"},
        "attributes": attributes if attributes is not None else {"side": "top"},
        "source": "local_raster_geometry",
        "producer": "core.vision.local_plan_elements_v1._record",
        "evidence_type": "local_raster_geometry",
        "provider_independent": True,
        "confidence": "MEDIUM",
        "status": status,
        "corroboration": corroboration or ["c1", "c2", "c3"],
        "evidence": "localized_swing_arc; leaf_segment; two_wall_jambs",
        "element_id": "e_%s_%s" % (type_, box[0]),
        "raster_patch_sha256": _SHA,
    }


def _item(class_, box, name=None):

    return {
        "class": class_,
        "bbox_pixels": list(box),
        "corroboration": ["c1", "c2", "c3"],
        "name": name or class_.replace("_", " "),
        "status": "visible",
        "confidence": "MEDIUM",
        "evidence_type": "fixture",
        "source": "local_raster_symbol_topology",
        "provider_independent": True,
        "item_id": "f_%s_%s" % (class_, box[0]),
        "raster_patch_sha256": _SHA,
    }


def _local(elements=(), items=(), regions=0, labels=()):

    return {
        "contract": "LocalPlanReadingV1",
        "version": "1.3",
        "status": "grounded",
        "source": "local_offline_raster",
        "provider_independent": True,
        "image_size": {"width": 1000, "height": 1000},
        "labels": list(labels),
        "openings": [],
        "furniture_evidence": list(items),
        "furniture_observed": bool(items),
        "symbol_analysis_status": "analyzed",
        "element_evidence": list(elements),
        "element_analysis_status": "analyzed",
        "ocr_status": "analyzed",
        "enclosure_geometry": {
            "source": "local_raster_wall_boundaries",
            "regions": [
                {"region_id": "r%d" % (i + 1), "bbox_pixels": [10, 10, 100, 100]}
                for i in range(regions)
            ],
            "count": regions or None,
            "count_status": "per_panel" if regions else "unknown",
            "multiple_spaces": regions > 1,
        },
    }


def _understanding(local, image_type="floor_plan_or_sketch", verified_ocr=()):

    return {
        "image_type": image_type,
        "confidence": "MEDIUM",
        "observed": [],
        "inferred": [],
        "unresolved": [],
        "architectural_elements": [],
        "text_labels_if_visible": [],
        "safety": {"supports_region_grounding": False},
        "local_plan_reading": local,
        # VISION_RETENTION_FIX_V2 — texts an INDEPENDENT source corroborated.
        "verified_ocr": list(verified_ocr),
    }


RICH = _understanding(
    _local(
        elements=[
            _element("window", [10, 10, 40, 12],
                     geometry={"orientation": "horizontal", "rail_count": 3}),
            _element("window", [50, 10, 80, 12],
                     geometry={"orientation": "horizontal", "rail_count": 2}),
            _element("door", [90, 40, 110, 42],
                     geometry={"orientation": "vertical"}),
            _element("stair", [120, 120, 200, 260],
                     geometry={"orientation": "horizontal", "direction": "right"},
                     attributes={"step_count": 12}),
            _element("axis", [5, 5, 995, 7],
                     geometry={"orientation": "horizontal"},
                     attributes={"axis_id": "A"}),
        ],
        items=[
            _item("bed", [300, 300, 420, 460]),
            _item("dining_surface", [500, 500, 620, 600]),
            _item("kitchen_counter", [700, 700, 900, 730]),
        ],
        regions=4,
        labels=[{
            # VISION_RETENTION_FIX_V2 — INDEPENDENTLY corroborated (see
            # `verified_ocr` below): the only tier that reaches `text`.
            "text": "پذیرایی", "semantic_function": "living room",
            "raw_ocr": "پذیرایی",
            "bbox_pixels": [50, 50, 90, 70], "bbox_normalized": [0.05, 0.05, 0.09, 0.07],
            "confidence": "HIGH", "ocr_confidence": 91.0, "match_score": 1.0,
            "independent_passes": 3, "evidence_type": "local_ocr",
            "status": "grounded_ocr", "correction": None,
            "occurrence": 1,
        }, {
            # … an exact but NOT independently corroborated reading is STABLE
            # local OCR: reportable as OCR, never architectural truth.
            "text": "آشپزخانه", "semantic_function": "kitchen",
            "raw_ocr": "آشپزخانه",
            "bbox_pixels": [100, 50, 140, 70], "bbox_normalized": [0.1, 0.05, 0.14, 0.07],
            "confidence": "MEDIUM", "ocr_confidence": 84.0, "match_score": 1.0,
            "independent_passes": 4, "evidence_type": "local_ocr",
            "status": "grounded_ocr", "correction": None,
            "occurrence": 1,
        }, {
            # … and a LEXICON SUBSTITUTION is a low-trust OCR candidate.
            "text": "تراس", "semantic_function": "balcony", "raw_ocr": "راس",
            "bbox_pixels": [10, 10, 40, 30], "bbox_normalized": [0.1, 0.1, 0.2, 0.2],
            "confidence": "MEDIUM", "ocr_confidence": 68.8, "match_score": 0.857,
            "independent_passes": 2, "evidence_type": "local_ocr",
            "status": "grounded_ocr", "correction": "architectural_lexicon_match",
            "occurrence": 1,
        }],
    ),
    verified_ocr=[{
        "verification": {
            "reason": "verbatim_independent_local_ocr",
            "local_evidence": [{"text": "پذیرایی"}],
        },
    }],
)


def _fa(understanding, include_interpretation=False):

    observation = build_observation(
        understanding, language="fa",
        include_interpretation=include_interpretation,
    )

    return observation, render_observation(observation, "fa")


# ==========================================================
# A1 — multiple grounded categories survive into the output
# ==========================================================

def test_a1_multiple_grounded_categories_survive():

    observation, text = _fa(RICH)

    categories = observation.get("grounded_categories") or {}

    return _check(
        "A1. every grounded local category reaches the observation contract "
        "(geometry / openings / vertical movement / structure / furniture / text)",
        set(categories) >= {
            "geometry", "openings", "vertical_circulation",
            "structure", "furniture", "text",
            "stable_local_ocr", "low_trust_ocr",
        }
        and "هندسه و فضاهای محصور" in text
        and "بازشوها" in text
        and "گردش عمودی" in text
        and "مبلمان و تجهیزات" in text,
        {"categories": sorted(categories)},
    )


# ==========================================================
# A2 — observation-only does not truncate to a tiny subset
# ==========================================================

def test_a2_no_arbitrary_truncation():

    observation, text = _fa(RICH)

    headers = [
        key for key in ("هندسه و فضاهای محصور", "بازشوها", "گردش عمودی",
                        "عناصر سازه‌ای و محورها", "مبلمان و تجهیزات",
                        "متن، ابعاد و کدها")
        if key in text
    ]

    return _check(
        "A2. the observation is not truncated to three objects: several "
        "grounded categories and many report lines are emitted",
        len(headers) >= 5
        and len([line for line in text.splitlines() if line.startswith("•")]) >= 8,
        {"headers": headers, "lines": len(text.splitlines())},
    )


# ==========================================================
# A3 — grounded stair is reportable without semantic room labels
# ==========================================================

def test_a3_stair_reported_without_room_labels():

    understanding = _understanding(
        _local(elements=[
            _element("stair", [100, 100, 200, 300],
                     geometry={"orientation": "horizontal", "direction": "up"},
                     attributes={"step_count": 14}),
        ])
    )

    observation, text = _fa(understanding)

    return _check(
        "A3. a grounded stair is reported even though no room label exists "
        "and no space was classified",
        "پله" in text
        and observation.get("space_type") is None
        and "vertical_circulation" in (observation.get("grounded_categories") or {}),
        {"text": text},
    )


# ==========================================================
# A4 — furniture survives when the room function is unknown
# ==========================================================

def test_a4_furniture_survives_unknown_function():

    understanding = _understanding(_local(items=[_item("bed", [300, 300, 420, 460])]))

    observation, text = _fa(understanding)

    names = [e.get("name") for e in observation.get("elements") or []]

    return _check(
        "A4. a grounded bed is reported as furniture evidence even though no "
        "room function is resolved",
        "sleeping_element" in names
        and "تخت" in text
        and observation.get("space_type") is None,
        {"names": names},
    )


# ==========================================================
# A5 — geometry/enclosures reported without semantic naming
# ==========================================================

def test_a5_geometry_without_semantic_naming():

    observation, text = _fa(_understanding(_local(regions=5)))

    geometry = (observation.get("grounded_categories") or {}).get("geometry") or {}

    return _check(
        "A5. enclosed geometric regions are reported as a GEOMETRY count, "
        "never as named rooms",
        geometry.get("region_count") == 5
        and "هندسه و فضاهای محصور" in text
        and observation.get("space_type") is None
        and (observation.get("elements") or []) == [],
        {"geometry": geometry},
    )


# ==========================================================
# A6 — internal tags are NOT exposed in the Persian UI text
# ==========================================================

def test_a6_internal_tags_not_exposed():

    _observation, text = _fa(RICH)

    leaked = [
        tag for tag in (
            "localized_swing_arc", "leaf_segment", "two_wall_jambs",
            "parallel_glazing_rails", "thick_wall_flanks", "perimeter_wall_band",
            "historical_local_raster_window", "kitchen sink arrangement",
            "kitchen counter", "c1", "c2", "c3",
        )
        if tag in text
    ]

    return _check(
        "A6. no internal English evidence ID appears in the normal Persian "
        "observation text",
        not leaked,
        {"leaked": leaked, "text": text},
    )


# ==========================================================
# A7 — internal tags remain available in structured output
# ==========================================================

def test_a7_internal_tags_kept_in_structured_output():

    observation, _text = _fa(RICH)

    blob = json.dumps(observation, ensure_ascii=False)

    return _check(
        "A7. the raw evidence IDs are preserved in the structured contract "
        "(diagnostics / provenance), only the presentation is translated",
        "localized_swing_arc" in blob
        and any(
            "localized_swing_arc" in phrase
            for entry in observation.get("elements") or []
            for phrase in entry.get("evidence") or []
        ),
        {"elements": observation.get("elements")},
    )


# ==========================================================
# A8 — Persian request -> Persian response
# ==========================================================

def test_a8_persian_request_persian_response():

    observation, text = _fa(RICH, include_interpretation=True)

    # No line may be pure English prose.
    english_lines = [
        line for line in text.splitlines()
        if line.strip()
        and not any("\u0600" <= ch <= "\u06FF" for ch in line)
        and line.strip() not in ("-",)
    ]

    return _check(
        "A8. a Persian request yields a fully Persian response (labels and "
        "explanations), including the interpretation section",
        not english_lines and "احتمالاً" in text,
        {"english_lines": english_lines, "text": text},
    )


# ==========================================================
# A9 — a door is not promoted to a main entrance
# ==========================================================

def test_a9_door_is_not_an_entrance():

    understanding = _understanding(_local(elements=[
        _element("door", [90, 40, 110, 42], geometry={"orientation": "vertical"}),
    ]))

    observation, text = _fa(understanding)

    kinds = [e.get("observed_kind") for e in observation.get("elements") or []]

    return _check(
        "A9. a grounded DOOR is reported as a door and never silently "
        "promoted to 'entrance' in observation-only mode",
        "door" in kinds and "در" in text and "ورودی" not in text,
        {"kinds": kinds, "text": text},
    )


# ==========================================================
# A10 — counter/sink is not promoted to a certain kitchen
# ==========================================================

def test_a10_counter_is_not_a_certain_kitchen():

    understanding = _understanding(_local(items=[
        _item("kitchen_counter", [700, 700, 900, 730]),
        _item("kitchen_sink_arrangement", [700, 740, 780, 780]),
    ]))

    observation, text = _fa(understanding)

    kinds = [e.get("observed_kind") for e in observation.get("elements") or []]

    labels = [e.get("display_label_fa") for e in observation.get("elements") or []]

    return _check(
        "A10. a counter/sink is reported as kitchen EQUIPMENT, never as a "
        "certain 'آشپزخانه' inside observation-only mode",
        any(k in ("kitchen_counter", "kitchen_sink_arrangement") for k in kinds)
        and "کانتر" in text
        and all((label or "") != "آشپزخانه" for label in labels),
        {"kinds": kinds, "labels": labels, "text": text},
    )


# ==========================================================
# A11 — UNKNOWN remains UNKNOWN
# ==========================================================

def test_a11_unknown_stays_unknown():

    observation, text = _fa(_understanding(_local()))

    return _check(
        "A11. with no grounded evidence the observation lists no element, "
        "reports no category and says the state is unknown",
        (observation.get("elements") or []) == []
        and (observation.get("grounded_categories") or {}) == {}
        and bool(observation.get("unknowns"))
        and "نامشخص" in text,
        {"observation": observation.get("unknowns")},
    )


# ==========================================================
# A12 — provider-only text stays distinct from grounded evidence
# ==========================================================

def test_a12_provider_only_text_stays_provider_only():

    understanding = {
        "image_type": "floor_plan_or_sketch",
        "confidence": "HIGH",
        "observed": [],
        "inferred": [],
        "unresolved": [],
        "architectural_elements": [],
        "text_labels_if_visible": ["BEDROOM", "KITCHEN", "LIFT"],
        "safety": {"supports_region_grounding": False},
    }

    observation, text = _fa(understanding)

    return _check(
        "A12. provider-only labels never become grounded local evidence: no "
        "element, no category, and the labels are not presented as readings",
        (observation.get("elements") or []) == []
        and (observation.get("grounded_categories") or {}) == {}
        and "BEDROOM" not in text,
        {"observation": observation.get("elements")},
    )


# ==========================================================
# A13 — multi-panel behaviour preserved (no mutation, no flattening)
# ==========================================================

def test_a13_multi_panel_preserved_and_not_mutated():

    local = _local(elements=[_element("window", [10, 10, 40, 12],
                                      geometry={"orientation": "horizontal"})],
                   regions=2)
    local["sheet_structure"] = {
        "contract": "LocalPlanSheetV1", "version": "multi-plan-sheet-v1",
        "sheet_type": "plan_pair", "source": "local_raster_geometry",
        "confidence": "MEDIUM",
        "panels": [
            {"panel_id": "p1", "bbox_pixels": [0, 0, 400, 400], "role": "unknown",
             "confidence": "MEDIUM", "source": "local_raster_geometry",
             "corroboration": ["a", "b", "c"],
             "local_plan_reading": {"provider_independent": True,
                                    "source": "local_offline_raster"}},
            {"panel_id": "p2", "bbox_pixels": [400, 0, 800, 400], "role": "unknown",
             "confidence": "MEDIUM", "source": "local_raster_geometry",
             "corroboration": ["a", "b", "c"],
             "local_plan_reading": {"provider_independent": True,
                                    "source": "local_offline_raster"}},
        ],
    }

    understanding = _understanding(local)

    before = copy.deepcopy(understanding)

    observation = build_observation(understanding, language="fa")

    preserved = (
        understanding == before
        and understanding["local_plan_reading"]["sheet_structure"]["sheet_type"]
        == "plan_pair"
        and len(understanding["local_plan_reading"]["sheet_structure"]["panels"]) == 2
    )

    return _check(
        "A13. the multi-panel sheet structure is untouched (no flattening, no "
        "mutation) and the observation invents no panel count",
        preserved
        and observation.get("space_type") is None
        and "panel_count" not in json.dumps(observation, ensure_ascii=False),
        {"preserved": preserved},
    )


# ==========================================================
# A14 — no image-specific hardcode
# ==========================================================

def test_a14_no_image_specific_hardcode():

    forbidden = (
        "c9821bc88bcc", "87adb7eace81", "5d95a28e35d9", "774c94336f50",
        "namplan", "namaspace", "morteza", "sodani", "212.jpg",
        "6a0aeabb", "3aa53401", "73148ed3",
    )

    hits = []

    for relative in (
        "core/vision/vision_observation_mode_v1.py",
        "core/vision/architectural_vision_grounding_v1.py",
        "core/chat/chat_architect.py",
    ):

        source = open(os.path.join(ROOT, relative), encoding="utf-8").read().lower()

        hits.extend(
            "%s:%s" % (relative, token) for token in forbidden if token in source
        )

    return _check(
        "A14. no filename / hash / acceptance-image token exists in the "
        "changed modules",
        not hits,
        {"hits": hits},
    )


# ==========================================================
# DETECTION CONTRACT
# ==========================================================

def test_detection_contract():

    acceptance = (
        "فقط بر اساس چیزهایی که واقعاً در تصویر می‌بینی، مشاهدات معماری را "
        "کامل گزارش بده. مشاهده را از تفسیر جدا کن و موارد نامشخص را حدس نزن."
    )

    return _check(
        "A8b. the natural Persian observation request is detected as "
        "observation, and its interpretation request is detected separately "
        "('تفسیر نکن' never turns it on)",
        detect_observation_request(acceptance) is True
        and detect_interpretation_request(acceptance) is True
        and detect_observation_request("این تصویر را فقط تحلیل کن") is False
        and detect_interpretation_request("فقط مشاهده کن، تفسیر نکن") is False,
        {},
    )


# ==========================================================
# RUNNER
# ==========================================================

def main():

    print("\n" + "=" * 70)
    print("W4.2A-8 — GENERAL OBSERVATION COMPLETENESS TESTS")
    print("=" * 70)

    tests = [
        test_a1_multiple_grounded_categories_survive,
        test_a2_no_arbitrary_truncation,
        test_a3_stair_reported_without_room_labels,
        test_a4_furniture_survives_unknown_function,
        test_a5_geometry_without_semantic_naming,
        test_a6_internal_tags_not_exposed,
        test_a7_internal_tags_kept_in_structured_output,
        test_a8_persian_request_persian_response,
        test_a9_door_is_not_an_entrance,
        test_a10_counter_is_not_a_certain_kitchen,
        test_a11_unknown_stays_unknown,
        test_a12_provider_only_text_stays_provider_only,
        test_a13_multi_panel_preserved_and_not_mutated,
        test_a14_no_image_specific_hardcode,
        test_detection_contract,
    ]

    for test in tests:

        try:

            test()

        except Exception as error:

            _check(
                test.__name__ + " (raised)",
                False,
                "%s: %s" % (type(error).__name__, error),
            )

    failed = [item for item in _RESULTS if not item[1]]

    for name, passed, detail in _RESULTS:

        print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

        if not passed:

            print("        ", json.dumps(detail, ensure_ascii=False, default=str)[:700])

    print("-" * 70)
    print("  %d/%d PASS" % (len(_RESULTS) - len(failed), len(_RESULTS)))
    print("=" * 70 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())
