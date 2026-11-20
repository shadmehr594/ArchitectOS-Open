"""Sheet structure around the existing raster/observation/plan-reading path.

No provider semantics establish panels, correspondence or physical instances.
Coordinates are explicit: sheet pixels, panel analysis pixels, or footprint units.
"""

from __future__ import annotations

import math
import re
from copy import deepcopy

import numpy as np

VERSION = "multi-plan-sheet-v1"

# ARCHITECTURAL_SEMANTIC_READING_W3 — grounded panel roles.
#
# `dimension_plan`          the panel that carries the dimensioned architectural
#                           setting-out (axes, dimension chains, measurements)
#                           with NO furniture symbol.  Persian: پلان اندازه‌گذاری
# `architectural_plan`      an architectural layout panel with neither a
#                           dominant dimension set nor furniture symbols
# `furnished_architectural_plan`
#                           the architectural layout WITH furniture symbols.
#                           Persian: پلان معماری / پلان مبلمان
# `structural_plan`         a structural framing drawing
#
# The furnished panel is no longer called merely `furnished_plan`: the role now
# says it is an architectural plan that carries furniture.
DIMENSION_PLAN = "dimension_plan"
ARCHITECTURAL_PLAN = "architectural_plan"
FURNISHED_ARCHITECTURAL_PLAN = "furnished_architectural_plan"
STRUCTURAL_PLAN = "structural_plan"
UNKNOWN_PLAN = "unknown"

LAYOUT_ROLES = (ARCHITECTURAL_PLAN, FURNISHED_ARCHITECTURAL_PLAN)
GEOMETRY_ROLES = (DIMENSION_PLAN,) + LAYOUT_ROLES

# Script-neutral title lexicon. OCR of a title strip is noisy, so each surface
# is matched with a bounded fuzzy window rather than exact equality.
TITLE_ROLE_TERMS = (
    ("FURNITURE", FURNISHED_ARCHITECTURAL_PLAN),
    ("FURNISHED", FURNISHED_ARCHITECTURAL_PLAN),
    ("FURNISHING", FURNISHED_ARCHITECTURAL_PLAN),
    ("MOBILIER", FURNISHED_ARCHITECTURAL_PLAN),
    ("STRUCTURE", STRUCTURAL_PLAN),
    ("STRUCTURAL", STRUCTURAL_PLAN),
    ("DIMENSION", DIMENSION_PLAN),
    ("MEASUREMENT", DIMENSION_PLAN),
    ("SETTING OUT", DIMENSION_PLAN),
    ("TYPICAL FLOOR", ARCHITECTURAL_PLAN),
    ("FLOOR PLAN", ARCHITECTURAL_PLAN),
    ("ARCHITECTURAL", ARCHITECTURAL_PLAN),
    ("LAYOUT", ARCHITECTURAL_PLAN),
)
TITLE_MIN_SCORE = 0.65
TITLE_MIN_CONFIDENCE = 10.0
# A title may be recorded from a single weak read, but it only FORCES a role
# when it is corroborated: two agreeing reads, or one strong read.
TITLE_STRONG_SCORE = 0.85


def _term_window_match(compact, surface):
    """Best fuzzy similarity between `surface` and any window of `compact`."""
    from difflib import SequenceMatcher

    compact = compact.upper()
    target = re.sub(r"[^A-Z0-9]", "", surface.upper())
    if not compact or not target:
        return 0.0
    best = 0.0
    for source in (compact, compact[::-1]):
        low = max(1, len(target) - 1)
        high = min(len(source), len(target) + 3)
        for length in range(low, high + 1):
            for start in range(0, max(1, len(source) - length + 1)):
                candidate = source[start:start + length]
                if candidate:
                    best = max(
                        best, SequenceMatcher(None, candidate, target).ratio()
                    )
    return best


def classify_plan_role(evidence):
    """Grounded panel role from independent local evidence.

    Furniture presence alone never decides. A panel is a `dimension_plan` only
    when it carries NO furniture symbol AND no furnishing texture AND an axis
    grid AND bounded enclosure regions, so an empty or failed panel can never be
    promoted into a measured plan. A specific title vote may force the
    structural / furnished / dimension role, but a generic "floor plan" title
    does not override the content-based dimension-vs-layout distinction, because
    both panels of a dimensioned pair are legitimately titled floor plans.
    """
    furniture = int(evidence.get("furniture_symbols") or 0)
    patterns = int(evidence.get("furnishing_patterns") or 0)
    axes = int(evidence.get("axis_count") or 0)
    regions = int(evidence.get("enclosure_regions") or 0)
    labels = int(evidence.get("space_labels") or 0)
    title_role = evidence.get("title_role")
    if title_role == STRUCTURAL_PLAN:
        return STRUCTURAL_PLAN
    if title_role == FURNISHED_ARCHITECTURAL_PLAN:
        return FURNISHED_ARCHITECTURAL_PLAN
    if title_role == DIMENSION_PLAN:
        return DIMENSION_PLAN
    if furniture == 0 and patterns == 0 and axes >= 2 and regions >= 1:
        return DIMENSION_PLAN
    if furniture > 0 or patterns > 0:
        return FURNISHED_ARCHITECTURAL_PLAN
    if regions >= 1 or labels >= 1:
        return ARCHITECTURAL_PLAN
    return UNKNOWN_PLAN


def _line_mask(cv2, gray, fraction=0.06):
    h, w = gray.shape
    ink = (gray < 150).astype(np.uint8)
    return cv2.morphologyEx(
        ink, cv2.MORPH_OPEN, np.ones((1, max(8, round(w * fraction))), np.uint8)
    ) | cv2.morphologyEx(
        ink, cv2.MORPH_OPEN, np.ones((max(8, round(h * fraction)), 1), np.uint8)
    )


def detect_sheet(gray):
    """Separate substantial independent orthogonal drawings, not room cells.

    OCR is intentionally absent here. Marginal text, leaders and page frames
    cannot create panels. A connected single-plan footprint stays one instance.
    """
    h, w = gray.shape
    single = {
        "contract": "LocalPlanSheetV1",
        "version": VERSION,
        "sheet_type": "single_plan",
        "source": "local_raster_geometry",
        "confidence": "MEDIUM",
        "panels": [
            {
                "panel_id": "p1",
                "bbox_pixels": [0, 0, w, h],
                "role": "unknown",
                "confidence": "MEDIUM",
            }
        ],
    }
    try:
        import cv2
    except ImportError:
        return dict(
            single,
            sheet_type="unknown",
            confidence="LOW",
            reason="symbol_backend_unavailable",
        )
    scale = min(1.0, 1600 / max(h, w))
    small = (
        cv2.resize(gray, (round(w * scale), round(h * scale))) if scale < 1 else gray
    )
    sh, sw = small.shape
    lines = _line_mask(cv2, small, 0.04)
    joined = cv2.dilate(
        lines, np.ones((max(3, round(sh * 0.015)), max(3, round(sw * 0.015))), np.uint8)
    )
    _, _, stats, _ = cv2.connectedComponentsWithStats(joined, 8)
    boxes = []
    for x, y, bw, bh, area in stats[1:]:
        if bw < sw * 0.18 or bh < sh * 0.22 or area < sw * sh * 0.012:
            continue
        # A sheet border is not a plan: require interior partition activity.
        if bw > sw * 0.92 and bh > sh * 0.92:
            continue
        patch = lines[y : y + bh, x : x + bw]
        interior = patch[
            round(bh * 0.15) : round(bh * 0.85), round(bw * 0.15) : round(bw * 0.85)
        ]
        if not interior.size or np.mean(interior) < 0.025:
            continue
        boxes.append(
            [
                math.floor(x / scale),
                math.floor(y / scale),
                math.ceil((x + bw) / scale),
                math.ceil((y + bh) / scale),
            ]
        )
    boxes.sort(key=lambda b: (b[1], b[0]))
    if len(boxes) < 2:
        return single
    # Independent panel extents must have a genuine gutter in at least one axis.
    if any(
        not (
            a[2] + w * 0.03 < b[0]
            or b[2] + w * 0.03 < a[0]
            or a[3] + h * 0.03 < b[1]
            or b[3] + h * 0.03 < a[1]
        )
        for i, a in enumerate(boxes)
        for b in boxes[i + 1 :]
    ):
        return dict(single, segmentation_uncertain=True)
    panels = []
    for i, b in enumerate(boxes):
        bw, bh = b[2] - b[0], b[3] - b[1]
        crop = [
            max(0, round(b[0] - bw * 0.23)),
            max(0, round(b[1] - bh * 0.14)),
            min(w, round(b[2] + bw * 0.23)),
            min(h, round(b[3] + bh * 0.18)),
        ]
        for other in boxes:
            if other is b:
                continue
            if b[2] < other[0]:
                crop[2] = min(crop[2], (b[2] + other[0]) // 2)
            if other[2] < b[0]:
                crop[0] = max(crop[0], (other[2] + b[0]) // 2)
            if b[3] < other[1]:
                crop[3] = min(crop[3], (b[3] + other[1]) // 2)
            if other[3] < b[1]:
                crop[1] = max(crop[1], (other[3] + b[1]) // 2)
        panels.append(
            {
                "panel_id": f"p{i + 1}",
                "bbox_pixels": crop,
                "drawing_bbox_pixels": b,
                "role": "unknown",
                "confidence": "MEDIUM",
                "source": "local_raster_geometry",
                "corroboration": [
                    "independent_long_line_cluster",
                    "substantial_drawing_extent",
                    "interior_partition_activity",
                    "whitespace_gutter",
                ],
            }
        )
    return dict(single, sheet_type="multi_plan", panels=panels)


def _title(gray, panel, tessdata):
    """Read a title strip only after geometry has independently found a panel."""
    import cv2

    if not tessdata:
        return None
    b = panel["drawing_bbox_pixels"]
    c = panel["bbox_pixels"]
    height = b[3] - b[1]
    bb = [
        c[0],
        b[3] + max(1, round(height * 0.05)),
        c[2],
        min(gray.shape[0], b[3] + round(height * 0.30)),
    ]
    patch = gray[bb[1] : bb[3], bb[0] : bb[2]]
    if not patch.size:
        return None
    try:
        from tesserocr import OEM, PSM, PyTessBaseAPI

        reads = []
        from core.vision.local_plan_elements_v1 import _runs

        active = ((patch < 210).sum(axis=1) > patch.shape[1] * 0.06).astype(np.uint8)
        active = cv2.morphologyEx(
            active[:, None], cv2.MORPH_CLOSE, np.ones((3, 1), np.uint8)
        ).ravel()
        strips = [(a, b) for a, b in _runs(active) if b - a >= 4]
        # The whole strip is read as a block as well: a title whose glyph rows
        # fall below the row-activity threshold, or whose words sit on more than
        # one detected strip, would otherwise be invisible.
        spans = [(start, end, PSM.SINGLE_LINE) for start, end in strips]
        spans.append((0, patch.shape[0], PSM.SINGLE_BLOCK))
        with PyTessBaseAPI(
            path=str(tessdata), lang="eng", psm=PSM.SPARSE_TEXT, oem=OEM.LSTM_ONLY
        ) as api:
            for start, end, page_mode in spans:
                # A small scale/threshold ladder: title lettering is larger than
                # a room label but its binarisation band varies between sheets.
                for scale, threshold in (
                    (4, 150), (4, 170), (6, 170), (6, 190), (8, 150), (8, 210),
                ):
                    line = patch[max(0, start - 2) : min(patch.shape[0], end + 2)]
                    im = cv2.resize(
                        line, None, fx=scale, fy=scale,
                        interpolation=cv2.INTER_CUBIC,
                    )
                    im = np.where(im < threshold, 0, 255).astype(np.uint8)
                    api.SetPageSegMode(page_mode)
                    api.SetImageBytes(
                        im.tobytes(), im.shape[1], im.shape[0], 1, im.shape[1]
                    )
                    text, confidence = (
                        (api.GetUTF8Text() or "").strip(),
                        float(api.MeanTextConf()),
                    )
                    if text and confidence >= TITLE_MIN_CONFIDENCE:
                        reads.append((text, round(confidence, 1), scale, threshold))
        votes = {}
        for text, confidence, scale, threshold in reads:
            compact = re.sub(r"[^A-Z0-9]", "", text.upper())
            if len(compact) < 4:
                continue
            score, term, role = 0.0, None, None
            for surface, candidate in TITLE_ROLE_TERMS:
                value = _term_window_match(compact, surface)
                if value > score:
                    score, term, role = value, surface, candidate
            if term is None or score < TITLE_MIN_SCORE:
                continue
            entry = votes.setdefault(
                role, {"votes": 0, "terms": set(), "best": (0.0, None)}
            )
            entry["votes"] += 1
            entry["terms"].add(term)
            if score > entry["best"][0]:
                entry["best"] = (score, term)
        if not votes:
            return None
        role = max(votes, key=lambda key: (votes[key]["votes"], votes[key]["best"][0]))
        entry = votes[role]
        corroborated = entry["votes"] >= 2 or entry["best"][0] >= TITLE_STRONG_SCORE
        return {
            "text": reads[0][0],
            "role": role,
            "matched_term": entry["best"][1],
            "match_score": round(entry["best"][0], 3),
            "agreeing_reads": entry["votes"],
            "corroborated": corroborated,
            "bbox_pixels": bb,
            "source": "local_title_ocr",
            "confidence": (
                "MEDIUM"
                if corroborated
                else "LOW"
            ),
            "corroboration": [
                "geometry_panel_exists",
                "proximal_title",
                "script_neutral_title_lexicon",
            ],
            "reads": [
                {"text": text, "confidence": confidence,
                 "scale": scale, "threshold": threshold}
                for text, confidence, scale, threshold in reads
            ],
        }
    except (ImportError, RuntimeError, OSError, ValueError):
        return None
    return None


def _descriptor(cv2, gray, box):
    x0, y0, x1, y1 = box
    patch = gray[y0:y1, x0:x1]
    if not patch.size:
        return None
    # Repair limited opening/dash gaps before comparing major partitions.
    # The semantic title and furniture texture never enter correspondence.
    h, w = patch.shape
    ink = (patch < 200).astype(np.uint8)
    horizontal = cv2.morphologyEx(
        ink, cv2.MORPH_CLOSE, np.ones((1, max(1, round(w * 0.07))), np.uint8)
    )
    vertical = cv2.morphologyEx(
        ink, cv2.MORPH_CLOSE, np.ones((max(1, round(h * 0.07)), 1), np.uint8)
    )
    lines = cv2.morphologyEx(
        horizontal, cv2.MORPH_OPEN, np.ones((1, max(8, round(w * 0.22))), np.uint8)
    ) | cv2.morphologyEx(
        vertical, cv2.MORPH_OPEN, np.ones((max(8, round(h * 0.22)), 1), np.uint8)
    )
    # Compare thickened normalized major partitions, excluding the perimeter.
    mask = (
        cv2.resize(lines.astype(np.float32), (128, 128), interpolation=cv2.INTER_AREA)
        > 0.08
    )
    mask[:10] = mask[-10:] = False
    mask[:, :10] = mask[:, -10:] = False
    return {
        "aspect_ratio": (x1 - x0) / (y1 - y0),
        "partition_mask": mask.astype(np.uint8).tolist(),
        "partition_ink": int(mask.sum()),
        "coordinate_frame": "normalized_footprint",
    }


def correspondence(left, right):
    """Require shared internal partitions, not merely matching rectangles/titles."""
    import cv2

    a, b = left.get("geometry_descriptor"), right.get("geometry_descriptor")
    if not a or not b or min(a["partition_ink"], b["partition_ink"]) < 120:
        return {"supported": False, "reason": "insufficient_partition_evidence"}
    ar = abs(a["aspect_ratio"] - b["aspect_ratio"]) / max(
        a["aspect_ratio"], b["aspect_ratio"]
    )
    am, bm = (
        np.array(a["partition_mask"], np.uint8),
        np.array(b["partition_mask"], np.uint8),
    )
    if am.shape != (128, 128) or bm.shape != (128, 128):
        return {"supported": False, "reason": "invalid_descriptor"}
    ad, bd = (
        cv2.dilate(am, np.ones((7, 7), np.uint8)),
        cv2.dilate(bm, np.ones((7, 7), np.uint8)),
    )
    scores = [
        float((am * bd).sum() / max(1, am.sum())),
        float((bm * ad).sum() / max(1, bm.sum())),
    ]
    # Both directions prevent a sparsely drawn unrelated plan matching a dense grid.
    return {
        "supported": ar < 0.12 and min(scores) > 0.76,
        "panel_ids": [left["panel_id"], right["panel_id"]],
        "partition_agreement": scores,
        "aspect_difference": ar,
        "source": "local_normalized_wall_topology",
        "confidence": "MEDIUM",
        "corroboration": [
            "normalized_footprint",
            "bidirectional_major_partition_match",
        ],
        "provider_independent": True,
    }


def _panel_context(cv2, gray, box, door_evidence=()):
    """Sheet-local context: quilted symbols and bounded paired stair flights.

    A texture is only panel-role corroboration, never a bed/sofa classifier.
    A central regular row alone cannot establish stairs without stringers and
    an intermediate separator. Shaft identity remains a candidate.
    """
    from core.vision.local_plan_elements_v1 import _iou, _record, _thin_segments
    from core.vision.local_plan_symbols_v1 import _box, _interior_holes

    pw, ph = box[2] - box[0], box[3] - box[1]
    ink = (gray < 190).astype(np.uint8)
    contours, tree = cv2.findContours(ink, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    patterns, core, shafts = [], [], []
    if tree is not None:
        tree = tree[0]
        for i, contour in enumerate(contours):
            bb = _box(cv2, contour)
            bw, bh = bb[2] - bb[0], bb[3] - bb[1]
            holes = _interior_holes(tree, i)
            if not (
                pw * 0.06 < bw < pw * 0.23
                and ph * 0.025 < bh < ph * 0.15
                and len(holes) >= 12
            ):
                continue
            if not (
                box[0] <= bb[0] < bb[2] <= box[2] and box[1] <= bb[1] < bb[3] <= box[3]
            ):
                continue
            centres = np.array(
                [
                    (
                        (_box(cv2, contours[j])[0] + _box(cv2, contours[j])[2]) / 2,
                        (_box(cv2, contours[j])[1] + _box(cv2, contours[j])[3]) / 2,
                    )
                    for j in holes
                ]
            )
            if (
                np.ptp(centres[:, 0]) > bw * 0.45
                and np.ptp(centres[:, 1]) > bh * 0.45
                and not any(_iou(bb, p["bbox_pixels"]) > 0.6 for p in patterns)
            ):
                patterns.append(
                    {
                        "bbox_pixels": bb,
                        "source": "local_raster_geometry",
                        "confidence": "MEDIUM",
                        "semantic_class": None,
                        "corroboration": [
                            "closed_patterned_symbol",
                            "two_dimensional_quilt_cells",
                            "interior_drawing_location",
                        ],
                    }
                )
    for transpose in (False, True):
        im = ink.T if transpose else ink
        b = [box[1], box[0], box[3], box[2]] if transpose else box
        width, height = b[2] - b[0], b[3] - b[1]
        raw_segs = _thin_segments(cv2, im, False, max(6, round(width * 0.05)))
        segs = []
        for row, lo, hi in raw_segs:
            if (
                segs
                and abs(row - segs[-1][0]) <= 1
                and 0 <= lo - segs[-1][2] < width * 0.025
            ):
                previous = segs.pop()
                segs.append((row, previous[1], hi))
            else:
                segs.append((row, lo, hi))
        for seed in segs:
            if not width * 0.08 < seed[2] - seed[1] < width * 0.28:
                continue
            if abs((seed[1] + seed[2]) / 2 - (b[0] + b[2]) / 2) > width * 0.12:
                continue
            compatible = [
                s
                for s in segs
                if abs(s[1] - seed[1]) < width * 0.025
                and abs(s[2] - seed[2]) < width * 0.025
            ]
            groups, group = [], []
            for s in compatible:
                if group and not 2 <= s[0] - group[-1][0] <= height * 0.04:
                    groups.append(group)
                    group = []
                group.append(s)
            groups.append(group)
            for group in groups:
                if len(group) < 5:
                    continue
                gaps = np.diff([s[0] for s in group])
                if gaps.std() / gaps.mean() > 0.4:
                    continue
                lo, hi = (
                    round(np.median([s[1] for s in group])),
                    round(np.median([s[2] for s in group])),
                )
                top, bottom = group[0][0], group[-1][0]
                strip = im[top : bottom + 1, max(0, lo - 2) : hi + 3]
                columns = strip.mean(axis=0)
                edges = [columns[:5].max(), columns[-5:].max()]
                middle = columns[len(columns) // 2 - 2 : len(columns) // 2 + 3].max()
                crosses = _thin_segments(
                    cv2, strip, True, max(6, round((bottom - top) * 0.7))
                )
                if min(edges) < 0.5 or middle < 0.5 or len(crosses) > 7:
                    continue
                bb = (
                    [top - 2, lo - 2, bottom + 3, hi + 2]
                    if transpose
                    else [lo - 2, top - 2, hi + 2, bottom + 3]
                )
                if any(_iou(bb, c["bbox_pixels"]) > 0.4 for c in core):
                    continue
                core.append(
                    _record(
                        gray,
                        "stair",
                        bb,
                        [
                            "regular_countable_tread_rows",
                            "two_outer_stringers",
                            "intermediate_flight_separator",
                            "central_drawing_context",
                        ],
                        geometry={
                            "orientation": "horizontal" if transpose else "vertical",
                            "direction": "unknown",
                        },
                        attributes={
                            "step_count": None,
                            "step_count_status": "partial",
                            "counted_tread_rows": len(group),
                            "count_convention": "visible_parallel_rows_not_total_flight_steps",
                            "paired_flight_context": True,
                            "direction_status": "unread",
                        },
                    )
                )
    if core and tree is not None:
        for contour in contours:
            bb = _box(cv2, contour)
            bw, bh = bb[2] - bb[0], bb[3] - bb[1]
            if not (
                0.05 * pw < min(bw, bh)
                and bw < pw * 0.22
                and bh < ph * 0.12
                and 0.55 < bw / bh < 1.8
            ):
                continue
            if abs((bb[0] + bb[2]) / 2 - (box[0] + box[2]) / 2) > pw * 0.12:
                continue
            if not any(
                math.dist(
                    [(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2],
                    [
                        (c["bbox_pixels"][0] + c["bbox_pixels"][2]) / 2,
                        (c["bbox_pixels"][1] + c["bbox_pixels"][3]) / 2,
                    ],
                )
                < ph * 0.26
                for c in core
            ):
                continue
            poly = cv2.approxPolyDP(contour, cv2.arcLength(contour, True) * 0.035, True)
            if len(poly) != 4 or cv2.contourArea(contour) < bw * bh * 0.65:
                continue
            patch = ink[bb[1] : bb[3], bb[0] : bb[2]]
            diag = cv2.HoughLinesP(
                patch * 255,
                1,
                np.pi / 180,
                max(5, round(min(bw, bh) * 0.4)),
                minLineLength=round(min(bw, bh) * 0.6),
                maxLineGap=2,
            )
            slopes = set()
            for line in [] if diag is None else diag[:, 0]:
                x, y, xx, yy = map(int, line)
                if xx != x and 0.4 < abs((yy - y) / (xx - x)) < 2.5:
                    slopes.add(1 if (yy - y) / (xx - x) > 0 else -1)
            if slopes == {-1, 1} and not any(
                _iou(bb, x["bbox_pixels"]) > 0.4 for x in shafts
            ):
                shafts.append(
                    _record(
                        gray,
                        "shaft",
                        bb,
                        [
                            "compact_enclosed_core_void",
                            "crossed_diagonal_void_symbol",
                            "adjacent_grounded_paired_flight",
                        ],
                        candidate=True,
                        attributes={
                            "likely_type": "core_shaft_or_void",
                            "elevator_confirmed": False,
                        },
                    )
                )
    # Core rows need independently localized entrances/landing context.
    # A regular grid by itself never becomes a stair, and no stair rectangle
    # is promoted into a shaft. Unread void symbols remain unresolved.
    supported = []
    for run in core:
        bb = run["bbox_pixels"]
        center = [(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2]
        doors = [
            d
            for d in door_evidence
            if _iou(d["bbox_pixels"], bb) == 0
            and math.dist(
                center,
                [
                    (d["bbox_pixels"][0] + d["bbox_pixels"][2]) / 2,
                    (d["bbox_pixels"][1] + d["bbox_pixels"][3]) / 2,
                ],
            )
            < ph * 0.22
        ]
        if len(doors) >= 2:
            run["corroboration"].append("paired_local_door_symbols")
            run["attributes"]["adjacent_door_ids"] = [d["element_id"] for d in doors]
            supported.append(run)
    return patterns, supported + (shafts if supported else [])


def _clamp_box(box, width, height):
    """Keep a bbox inside a raster frame with a strictly positive extent."""
    x0 = max(0, min(width - 1, int(round(box[0]))))
    y0 = max(0, min(height - 1, int(round(box[1]))))
    x1 = max(x0 + 1, min(width, int(round(box[2]))))
    y1 = max(y0 + 1, min(height, int(round(box[3]))))
    return [x0, y0, x1, y1]


def native_box_to_panel(box, scale_x, scale_y, panel_size):
    """Native panel-crop pixels -> panel-analysis pixels, clamped to frame."""
    width, height = panel_size
    return _clamp_box(
        [box[0] * scale_x, box[1] * scale_y, box[2] * scale_x, box[3] * scale_y],
        width,
        height,
    )


def panel_box_to_native(box, scale_x, scale_y):
    """Panel-analysis pixels -> native panel-crop pixels (inverse transport)."""
    return [
        int(round(box[0] / scale_x)),
        int(round(box[1] / scale_y)),
        int(round(box[2] / scale_x)),
        int(round(box[3] / scale_y)),
    ]


def panel_box_to_normalized(box, panel_size):
    """Panel-analysis pixels -> normalized [0, 1] panel coordinates."""
    width, height = panel_size
    return [box[0] / width, box[1] / height, box[2] / width, box[3] / height]


def panel_box_to_sheet(box, raster_transform):
    """Panel-analysis pixels -> sheet pixels through the panel transform."""
    origin_x, origin_y = raster_transform["sheet_origin"]
    scale_x, scale_y = raster_transform["scale_x"], raster_transform["scale_y"]
    return [
        int(round(origin_x + box[0] / scale_x)),
        int(round(origin_y + box[1] / scale_y)),
        int(round(origin_x + box[2] / scale_x)),
        int(round(origin_y + box[3] / scale_y)),
    ]


def _native_furniture_transport(cv2, local, panel, crop, native_box, raster_shape):
    """Detect furniture/fixture symbols on the NATIVE panel crop and remap them.

    Every panel crop is upscaled before the legacy reading so OCR and wall
    geometry work at a usable resolution. That resampling changes light symbol
    strokes enough that the furniture/fixture families can disappear. The
    symbols are therefore read again on the ORIGINAL crop and transported into
    the panel-analysis frame, which is the frame every existing consumer
    already uses. Valid legacy items are never overwritten: a native item is
    appended only when no existing item of the same class already covers it.
    """
    from core.vision.local_plan_symbols_v1 import _iou, analyze_furniture_symbols

    native_height, native_width = crop.shape
    analysis_height, analysis_width = raster_shape
    if native_width < 1 or native_height < 1:
        return
    scale_x = analysis_width / native_width
    scale_y = analysis_height / native_height
    try:
        detected = analyze_furniture_symbols(crop, native_box)
    except Exception:
        return
    if not detected:
        return
    panel_size = (analysis_width, analysis_height)
    existing = list(local.get("furniture_evidence") or [])
    accepted = []
    for item in detected:
        native = [int(v) for v in item["bbox_pixels"]]
        mapped = native_box_to_panel(native, scale_x, scale_y, panel_size)
        if any(
            other.get("class") == item["class"]
            and _iou(other["bbox_pixels"], mapped) > 0.5
            for other in existing + accepted
        ):
            continue
        accepted.append(
            dict(
                item,
                bbox_pixels=mapped,
                bbox_normalized=panel_box_to_normalized(mapped, panel_size),
                native_bbox_pixels=native,
                native_raster_size={"width": native_width, "height": native_height},
                native_scale={"scale_x": scale_x, "scale_y": scale_y},
                sheet_bbox_pixels=panel_box_to_sheet(
                    mapped, panel["raster_transform"]
                ),
                coordinate_frame="panel_analysis_pixels",
                native_coordinate_frame="panel_native_pixels",
                source_panel_id=panel["panel_id"],
                native_symbol_pass=True,
                # The native enclosure regions are not transported, so no
                # region is claimed for a native item: it is grounded furniture
                # evidence that cannot by itself promote a space function.
                region_ids=[],
                corroboration=list(item.get("corroboration") or [])
                + ["native_resolution_symbol_pass"],
            )
        )
    if not accepted:
        merged = existing
    else:
        merged = existing + accepted
        for index, entry in enumerate(merged):
            entry["item_id"] = "f%d" % (index + 1)
        local["furniture_evidence"] = merged
        local["furniture_observed"] = True
    panel["native_furniture_transport"] = {
        "source": "local_native_symbol_topology",
        "provider_independent": True,
        "native_raster_size": {"width": native_width, "height": native_height},
        "analysis_raster_size": {
            "width": analysis_width,
            "height": analysis_height,
        },
        "scale_x": scale_x,
        "scale_y": scale_y,
        "coordinate_frame": "panel_analysis_pixels",
        "native_coordinate_frame": "panel_native_pixels",
        "detected": len(detected),
        "appended": len(accepted),
        "suppressed_as_duplicate": len(detected) - len(accepted),
    }


def _region_correspondences(left_local, right_local, tolerance=0.12):
    """One-to-one enclosure-region correspondence between two panels.

    Regions are compared in normalised panel coordinates, so the mapping is
    geometric and scale-free. Two panels of the same floor plan rarely segment
    into the same regions — the dimensioned panel resolves finer rooms than the
    furniture panel — so an area ratio alone would reject a true match. A pair
    is admitted when the normalised centroids are within `tolerance` AND each
    centroid lies inside the other region's normalised extent AND the areas are
    within a factor of four. Assignment is greedy by distance and strictly
    one-to-one, so no region is matched twice and no index order is ever used.
    """
    def normalized(region, plan_box):
        x0, y0, x1, y1 = region["bbox_pixels"]
        width = max(1, plan_box[2] - plan_box[0])
        height = max(1, plan_box[3] - plan_box[1])
        return {
            "centre": [
                ((x0 + x1) / 2 - plan_box[0]) / width,
                ((y0 + y1) / 2 - plan_box[1]) / height,
            ],
            "extent": [
                (x0 - plan_box[0]) / width,
                (y0 - plan_box[1]) / height,
                (x1 - plan_box[0]) / width,
                (y1 - plan_box[1]) / height,
            ],
            "area": float((x1 - x0) * (y1 - y0)),
        }

    left_box = left_local.get("plan_bbox_pixels") or [0, 0, 1, 1]
    right_box = right_local.get("plan_bbox_pixels") or [0, 0, 1, 1]
    left_regions = (left_local.get("enclosure_geometry") or {}).get("regions") or []
    right_regions = (right_local.get("enclosure_geometry") or {}).get("regions") or []
    candidates = []
    for left in left_regions:
        a = normalized(left, left_box)
        for right in right_regions:
            b = normalized(right, right_box)
            distance = math.hypot(
                a["centre"][0] - b["centre"][0], a["centre"][1] - b["centre"][1]
            )
            if distance > tolerance:
                continue
            inside_b = (
                b["extent"][0] <= a["centre"][0] <= b["extent"][2]
                and b["extent"][1] <= a["centre"][1] <= b["extent"][3]
            )
            inside_a = (
                a["extent"][0] <= b["centre"][0] <= a["extent"][2]
                and a["extent"][1] <= b["centre"][1] <= a["extent"][3]
            )
            if not (inside_a and inside_b):
                continue
            ratio = a["area"] / max(1.0, b["area"])
            if not 0.25 <= ratio <= 4.0:
                continue
            candidates.append(
                (round(distance, 6), left["region_id"], right["region_id"], ratio)
            )
    candidates.sort()
    used_left, used_right, pairs = set(), set(), []
    for distance, left_id, right_id, ratio in candidates:
        if left_id in used_left or right_id in used_right:
            continue
        used_left.add(left_id)
        used_right.add(right_id)
        pairs.append(
            {
                "left_region_id": left_id,
                "right_region_id": right_id,
                "centroid_distance_normalized": round(distance, 4),
                "area_ratio": round(ratio, 3),
                "mutual_centroid_containment": True,
                "source": "local_normalized_region_geometry",
            }
        )
    return pairs


def analyze_sheet(gray, sheet, read_raster, tessdata):
    """Crop first; every legacy analysis sees only its own panel pixels."""
    import cv2

    sheet = deepcopy(sheet)
    for panel in sheet["panels"]:
        x0, y0, x1, y1 = panel["bbox_pixels"]
        crop = gray[y0:y1, x0:x1].copy()
        scale = max(1.0, 900 / max(crop.shape))
        raster = cv2.resize(
            crop,
            (round(crop.shape[1] * scale), round(crop.shape[0] * scale)),
            interpolation=cv2.INTER_CUBIC,
        )
        panel["raster_transform"] = {
            "sheet_origin": [x0, y0],
            "scale_x": raster.shape[1] / crop.shape[1],
            "scale_y": raster.shape[0] / crop.shape[0],
            "coordinate_frame": "panel_analysis_pixels",
        }
        local = read_raster(
            raster,
            tessdata_path=tessdata,
            # W3.5 — hand the recovery layer the ORIGINAL panel crop (highest
            # genuine resolution) and the native->analysis scale, so small
            # architectural text is read from source pixels, not from the
            # INTER_CUBIC resample. Callers that do not accept these keywords
            # are unaffected (all existing readers take **kwargs).
            native_gray=crop,
            native_scale=(
                raster.shape[1] / crop.shape[1],
                raster.shape[0] / crop.shape[0],
            ),
        )
        panel["local_plan_reading"] = local
        pb = local.get("plan_bbox_pixels", [0, 0, 0, 0])
        regions = local.get("enclosure_geometry", {}).get("regions", [])
        accepted, quarantined = [], []
        for label in local.get("labels", []):
            lb = label["bbox_pixels"]
            center = [(lb[0] + lb[2]) / 2, (lb[1] + lb[3]) / 2]
            inside = pb[0] <= lb[0] < lb[2] <= pb[2] and pb[1] <= lb[1] < lb[3] <= pb[3]
            region = next(
                (
                    r
                    for r in regions
                    if r.get("confidence") == "MEDIUM"
                    and r["bbox_pixels"][0] < center[0] < r["bbox_pixels"][2]
                    and r["bbox_pixels"][1] < center[1] < r["bbox_pixels"][3]
                ),
                None,
            )
            readable = (lb[3] - lb[1]) / scale >= 3
            if inside and region is not None and readable:
                # A label becomes a grounded named space only inside a
                # bounded, MEDIUM-confidence enclosure region of this panel.
                accepted.append(
                    dict(
                        label,
                        source_panel_id=panel["panel_id"],
                        associated_region_id=region["region_id"],
                        association="label_centroid_inside_enclosure_region",
                    )
                )
                continue
            if not inside:
                reason = "label_outside_plan_enclosure"
            elif region is None:
                reason = "no_enclosure_region_contains_label_centroid"
            elif not readable:
                reason = "native_glyph_height_below_readable_floor"
            else:
                reason = "unassociated"
            quarantined.append(
                dict(label, status="unverified", reason=reason)
            )
        local["labels"] = accepted
        panel["quarantined_annotations"] = quarantined
        b = panel["drawing_bbox_pixels"]
        native_box = [b[0] - x0, b[1] - y0, b[2] - x0, b[3] - y0]
        sx, sy = (
            panel["raster_transform"]["scale_x"],
            panel["raster_transform"]["scale_y"],
        )
        doors = [
            dict(
                e,
                bbox_pixels=[
                    round(v / (sx if i % 2 == 0 else sy))
                    for i, v in enumerate(e["bbox_pixels"])
                ],
            )
            for e in local["element_evidence"]
            if e["type"] == "door"
        ]
        patterns, core = _panel_context(cv2, crop, native_box, doors)
        panel["furnishing_pattern_evidence"] = patterns
        # Furniture/fixture symbols are re-read at the panel's NATIVE
        # resolution and remapped into the analysis frame. The upscale above is
        # retained unchanged for OCR, walls and the legacy local-plan reading.
        _native_furniture_transport(cv2, local, panel, crop, native_box, raster.shape)
        sx, sy = (
            panel["raster_transform"]["scale_x"],
            panel["raster_transform"]["scale_y"],
        )
        for entry in core:
            native = deepcopy(entry)
            entry["bbox_pixels"] = [
                round(v * (sx if i % 2 == 0 else sy))
                for i, v in enumerate(native["bbox_pixels"])
            ]
            entry["bbox_normalized"] = [
                v / (raster.shape[1] if i % 2 == 0 else raster.shape[0])
                for i, v in enumerate(entry["bbox_pixels"])
            ]
            entry["element_id"] = "context-" + str(len(local["element_evidence"]) + 1)
            entry["native_raster_evidence"] = native
            entry["coordinate_frame"] = "panel_analysis_pixels"
            local["element_evidence"].append(entry)
        title = _title(gray, panel, tessdata)
        if title:
            panel["title_evidence"] = title
        axes = [e for e in local["element_evidence"] if e["type"] == "axis"]
        role_evidence = {
            "furniture_symbols": len(local.get("furniture_evidence") or []),
            "furnishing_patterns": len(patterns),
            "axis_count": len(axes),
            "axis_orientations": sorted(
                {e["geometry"].get("orientation") for e in axes}
            ),
            "enclosure_regions": len(local.get("enclosure_geometry", {}).get("regions") or []),
            "space_labels": len(local.get("labels") or []),
            "title_role": (
                title["role"] if title and title.get("corroborated") else None
            ),
            "title_role_weak": title["role"] if title else None,
            "title_term": title.get("matched_term") if title else None,
        }
        panel["role_evidence"] = role_evidence
        panel["role"] = classify_plan_role(role_evidence)
        panel["role_source"] = (
            "grounded_title_ocr_and_local_evidence"
            if title
            else "grounded_local_evidence"
        )
        # Descriptors use independent drawing extents, never OCR title bounds.
        panel["geometry_descriptor"] = _descriptor(cv2, gray, b)
    sheet["correspondences"] = [
        correspondence(a, b)
        for i, a in enumerate(sheet["panels"])
        for b in sheet["panels"][i + 1 :]
    ]
    if len(sheet["panels"]) == 2 and sheet["correspondences"][0]["supported"]:
        sheet["sheet_type"] = "plan_pair"
    # W3.4 — a grounded label may annotate the matching region of the OTHER
    # corresponding panel, but only through geometric correspondence: never by
    # index, and it never creates a space on its own.
    sheet["corresponding_regions"] = []
    for record in sheet["correspondences"]:
        if not record.get("supported"):
            continue
        panels = {
            panel["panel_id"]: panel
            for panel in sheet["panels"]
            if panel["panel_id"] in record["panel_ids"]
        }
        if len(panels) != 2:
            continue
        left, right = (panels[pid] for pid in record["panel_ids"])
        pairs = _region_correspondences(
            left["local_plan_reading"], right["local_plan_reading"]
        )
        if not pairs:
            continue
        by_left = {pair["left_region_id"]: pair for pair in pairs}
        by_right = {pair["right_region_id"]: pair for pair in pairs}
        for panel, other, lookup, key, mirrored in (
            (left, right, by_left, "right_region_id", "left_region_id"),
            (right, left, by_right, "left_region_id", "right_region_id"),
        ):
            for label in panel["local_plan_reading"].get("labels") or []:
                pair = lookup.get(label.get("associated_region_id"))
                if not pair:
                    continue
                label["corresponding_panel_id"] = other["panel_id"]
                label["corresponding_region_id"] = pair[key]
                label["corresponding_region_source"] = pair["source"]
        sheet["corresponding_regions"].append(
            {
                "panel_ids": list(record["panel_ids"]),
                "source": "local_normalized_region_geometry",
                "provider_independent": True,
                "pairs": pairs,
            }
        )
    # No flat whole-sheet OCR/symbol/enclosure analysis after a successful split.
    return {
        "contract": "LocalPlanReadingV1",
        "version": "1.3",
        "status": "grounded",
        "source": "local_offline_raster",
        "provider_independent": True,
        "image_size": {"width": gray.shape[1], "height": gray.shape[0]},
        "sheet_structure": sheet,
        "labels": [],
        "openings": [],
        "furniture_evidence": [],
        "furniture_observed": None,
        "symbol_analysis_status": "analyzed",
        "element_evidence": [],
        "element_analysis_status": "analyzed",
        "enclosure_geometry": {
            "count": None,
            "count_status": "per_panel",
            "regions": [],
        },
        "limitations": [
            "physical correspondence is conservative; unresolved panels remain separate"
        ],
    }


def grounded_sheet_structure(local):
    """Reject provider-only or malformed sheet localization at the consumer."""
    if (
        not isinstance(local, dict)
        or local.get("provider_independent") is not True
        or local.get("source") != "local_offline_raster"
    ):
        return None
    sheet = local.get("sheet_structure") or {}
    if sheet.get("source") != "local_raster_geometry" or sheet.get(
        "confidence"
    ) not in ("MEDIUM", "HIGH"):
        return None
    if sheet.get("sheet_type") not in ("multi_plan", "plan_pair"):
        return None
    size = local.get("image_size") or {}
    width, height = size.get("width", 0), size.get("height", 0)
    panels = sheet.get("panels") or []
    if len(panels) < 2 or len({p.get("panel_id") for p in panels}) != len(panels):
        return None
    for panel in panels:
        bb = panel.get("bbox_pixels") or []
        if len(bb) != 4 or not all(type(v) is int for v in bb):
            return None
        if not (0 <= bb[0] < bb[2] <= width and 0 <= bb[1] < bb[3] <= height):
            return None
        if panel.get("source") != "local_raster_geometry" or panel.get(
            "confidence"
        ) not in ("MEDIUM", "HIGH"):
            return None
        if len(panel.get("corroboration") or []) < 3:
            return None
        child = panel.get("local_plan_reading") or {}
        if (
            child.get("provider_independent") is not True
            or child.get("source") != "local_offline_raster"
            or "sheet_structure" in child
        ):
            return None
    return sheet


def _unit_support(function_positions, entrance_positions, axis):
    """Count supported functional wings, never apartments from symmetry alone."""
    groups = [{"functions": set(), "entrances": []} for _ in ("negative", "positive")]
    for function, point in function_positions:
        if abs(point[axis] - 0.5) < 0.08:
            continue
        groups[int(point[axis] > 0.5)]["functions"].add(function)
    for ref, point in entrance_positions:
        if 0.05 < abs(point[axis] - 0.5) < 0.23:
            groups[int(point[axis] > 0.5)]["entrances"].append(ref)
    qualified = [
        g
        for g in groups
        if {"bedroom", "living room"} <= g["functions"]
        and g["functions"] & {"kitchen", "bathroom"}
        and g["entrances"]
    ]
    return {
        "unit_count_candidate": len(qualified) if len(qualified) > 1 else None,
        "unit_status": "likely_functional_wings_with_independent_entrances"
        if len(qualified) > 1
        else "insufficient_functional_and_entrance_corroboration",
    }


def build_sheet_plan_reading(local, build_plan):
    """Project each panel through the existing architectural plan interpreter."""
    from core.vision.architectural_observation_v1 import build_architectural_observation

    sheet = local["sheet_structure"]
    readings = []
    for panel in sheet["panels"]:
        obs = build_architectural_observation(
            {
                "image_type": "floor_plan_or_sketch",
                "local_plan_reading": panel["local_plan_reading"],
            },
            provider="independent-local-panel",
        )
        readings.append(
            {
                "panel_id": panel["panel_id"],
                "role": panel["role"],
                "plan_reading": build_plan(obs),
            }
        )
    paired = len(readings) == 2 and correspondence(*sheet["panels"])["supported"]
    if not paired:
        # This is a collection of plan readings, not a physical floor reading.
        # Preserve every child interpretation; there are no sheet-wide room or
        # element aggregates and no selected canonical panel in this branch.
        independent = []
        for reading, panel in zip(readings, sheet["panels"], strict=True):
            independent.append(
                {
                    **deepcopy(reading["plan_reading"]),
                    "panel_id": reading["panel_id"],
                    "role": reading["role"],
                    "provenance": {
                        "source_panel_id": reading["panel_id"],
                        "source": panel["source"],
                        "confidence": panel["confidence"],
                        "corroboration": deepcopy(panel["corroboration"]),
                        "sheet_bbox_pixels": deepcopy(panel["bbox_pixels"]),
                        "raster_transform": deepcopy(panel.get("raster_transform")),
                        "coordinate_frame": "panel_analysis_pixels",
                        "provider_independent": True,
                    },
                }
            )
        collection = {
            "contract": "MultiPlanSheetReadingV1",
            "version": "1.0",
            "representation": "independent_plan_collection",
            "physical_plan_aggregation": False,
            "count_scope": "per_panel",
            "plans": independent,
            "panel_readings": readings,
            "sheet_structure": sheet,
            "local_plan_reading": local,
            "fusion": {
                "status": "separate_panels",
                "geometry_panel_id": None,
                "source": "local_normalized_wall_topology",
                "provider_independent": True,
            },
            "observation_only": True,
            "read_only": True,
        }
        # W4.1 — SHADOW MODE ONLY. Additive evidence contract; nothing resolved.
        from core.vision.architectural_function_evidence_v1 import (
            build_architectural_function_evidence,
        )

        collection["architectural_function_evidence"] = (
            build_architectural_function_evidence(collection)
        )
        return collection
    canonical = max(
        readings,
        key=lambda p: (
            p["role"] in GEOMETRY_ROLES,
            len(p["plan_reading"].get("geometry_spaces", [])),
        ),
    )
    plan = deepcopy(canonical["plan_reading"])
    plan["sheet_structure"] = sheet
    plan["panel_readings"] = readings
    plan["local_plan_reading"] = local
    plan["fusion"] = {
        "status": "corresponding_pair" if paired else "separate_panels",
        "geometry_panel_id": canonical["panel_id"] if paired else None,
        "source": "local_normalized_wall_topology",
        "provider_independent": True,
    }
    all_core = [
        e
        for e in plan.get("architectural_elements", [])
        if e.get("attributes", {}).get("paired_flight_context")
    ]
    shafts = [e for e in plan.get("architectural_elements", []) if e["type"] == "shaft"]
    plan["central_core"] = {
        "status": "grounded_candidate" if all_core else "unconfirmed",
        "stair_ids": [e["element_id"] for e in all_core],
        "shaft_ids": [e["element_id"] for e in shafts],
        "source_panel_id": canonical["panel_id"],
        "elevator_confirmed": False,
    }
    descriptor = next(
        p["geometry_descriptor"]
        for p in sheet["panels"]
        if p["panel_id"] == canonical["panel_id"]
    )
    mask = np.array(descriptor["partition_mask"], np.uint8)
    reflections = [
        float(np.logical_and(mask, np.fliplr(mask)).sum() / max(1, mask.sum())),
        float(np.logical_and(mask, np.flipud(mask)).sum() / max(1, mask.sum())),
    ]
    axis = int(reflections[1] > reflections[0])
    reflection = reflections[axis]
    plan["spatial_organization"] = {
        "reflection_support": reflection,
        "repeated_spatial_groups": bool(all_core and reflection > 0.65),
        "unit_count_candidate": None,
        "unit_status": "insufficient_functional_and_entrance_corroboration",
        "source": "local_wall_topology_and_central_core",
        "reflection_axis": "horizontal_position" if axis == 0 else "vertical_position",
    }
    # One geometry instance; activities preserve their own independent panel
    # region support and are not asserted to create extra physical rooms.
    # The panel that actually carries furniture symbols supplies the furniture
    # and the functions it supports. This is decided from the evidence, never
    # from a role name.
    furniture_panel = max(
        readings,
        key=lambda p: len(p["plan_reading"].get("furniture", [])),
    )
    for key in ("furniture", "inferred_functions"):
        plan[key] = [
            dict(
                deepcopy(item),
                source_panel_id=furniture_panel["panel_id"],
                coordinate_frame="panel_analysis_pixels",
            )
            for item in furniture_panel["plan_reading"].get(key, [])
        ]
    plan["furniture_observed"] = bool(plan["furniture"])
    plan["fusion"]["furniture_panel_id"] = furniture_panel["panel_id"]
    if plan["spatial_organization"]["repeated_spatial_groups"]:

        def points(entries, pb):
            return [
                (
                    e,
                    [
                        (e["bbox_pixels"][0] + e["bbox_pixels"][2]) / 2 - pb[0],
                        (e["bbox_pixels"][1] + e["bbox_pixels"][3]) / 2 - pb[1],
                    ],
                )
                for e in entries
                if e.get("bbox_pixels")
            ]

        fp = furniture_panel["plan_reading"]["local_plan_reading"]["plan_bbox_pixels"]
        cp = canonical["plan_reading"]["local_plan_reading"]["plan_bbox_pixels"]
        funcs = [
            (e["space"], [p[0] / (fp[2] - fp[0]), p[1] / (fp[3] - fp[1])])
            for e, p in points(plan["inferred_functions"], fp)
        ]
        doors = [
            (e["element_id"], [p[0] / (cp[2] - cp[0]), p[1] / (cp[3] - cp[1])])
            for e, p in points(
                [
                    e
                    for e in canonical["plan_reading"]["architectural_elements"]
                    if e["type"] == "door"
                ],
                cp,
            )
        ]
        plan["spatial_organization"].update(_unit_support(funcs, doors, axis))
    # Opening identity is in a shared footprint frame, with per-panel origins.
    merged = []
    ordered = [canonical] + [p for p in readings if p is not canonical]
    unmatched = []
    for reading in ordered:
        lp = next(
            p["local_plan_reading"]
            for p in sheet["panels"]
            if p["panel_id"] == reading["panel_id"]
        )
        pb = lp["plan_bbox_pixels"]
        for group in reading["plan_reading"].get("openings", []):
            for item in group.get("instances", []):
                bb = item["bbox_pixels"]
                normal = [
                    (bb[0] - pb[0]) / (pb[2] - pb[0]),
                    (bb[1] - pb[1]) / (pb[3] - pb[1]),
                    (bb[2] - pb[0]) / (pb[2] - pb[0]),
                    (bb[3] - pb[1]) / (pb[3] - pb[1]),
                ]
                centre = [(normal[0] + normal[2]) / 2, (normal[1] + normal[3]) / 2]
                matched = next(
                    (
                        m
                        for m in merged
                        if m["kind"] == group["kind"]
                        and reading["panel_id"]
                        not in {r["panel_id"] for r in m["source_refs"]}
                        and math.dist(m["centre"], centre) < 0.045
                    ),
                    None,
                )
                ref = {
                    "panel_id": reading["panel_id"],
                    "bbox_pixels": bb,
                    "coordinate_frame": "panel_analysis_pixels",
                    "source": item.get("source"),
                    "confidence": item.get("confidence"),
                }
                if matched:
                    matched["source_refs"].append(ref)
                elif reading is canonical:
                    merged.append(
                        {
                            **deepcopy(item),
                            "kind": group["kind"],
                            "centre": centre,
                            "bbox_normalized_footprint": normal,
                            "source_refs": [ref],
                            "source_panel_id": reading["panel_id"],
                            "coordinate_frame": "panel_analysis_pixels",
                        }
                    )
                else:
                    unmatched.append(ref)
    plan["fusion"]["unmatched_opening_source_refs"] = unmatched
    if not any(e["type"] == "axis" for e in plan["architectural_elements"]):
        for reading in readings:
            if reading is canonical:
                continue
            plan["architectural_elements"].extend(
                dict(
                    deepcopy(e),
                    source_panel_id=reading["panel_id"],
                    coordinate_frame="panel_analysis_pixels",
                )
                for e in reading["plan_reading"]["architectural_elements"]
                if e["type"] == "axis"
            )
    plan["openings"] = [
        {
            "kind": kind,
            "status": "visible",
            "confidence": "MEDIUM",
            "instances": [m for m in merged if m["kind"] == kind],
            "instance_count": sum(m["kind"] == kind for m in merged),
        }
        for kind in sorted({m["kind"] for m in merged})
    ]
    # W3.4 — a grounded label on the CORRESPONDING panel annotates the matching
    # region of this geometry panel. The mapping is geometric
    # (`sheet["corresponding_regions"]`), never index based, and a space is
    # published once only, so no physical space is duplicated.
    canonical_id = canonical["panel_id"]
    transfer_map = {}
    for record in sheet.get("corresponding_regions") or []:
        if canonical_id not in record["panel_ids"] or len(record["panel_ids"]) != 2:
            continue
        first, second = record["panel_ids"]
        for pair in record["pairs"]:
            if canonical_id == first:
                transfer_map[(second, pair["right_region_id"])] = pair["left_region_id"]
            else:
                transfer_map[(first, pair["left_region_id"])] = pair["right_region_id"]
    transfers = []
    published = {entry["space"] for entry in plan.get("named_spaces", [])}
    try:
        from core.vision.architectural_vision_interpreter_v1 import SPACE_ZONE
    except Exception:
        SPACE_ZONE = {}
    for reading in readings:
        if reading["panel_id"] == canonical_id:
            continue
        for label in (
            reading["plan_reading"].get("local_plan_reading", {}).get("labels") or []
        ):
            target = transfer_map.get(
                (reading["panel_id"], label.get("associated_region_id"))
            )
            if target is None:
                continue
            space = label.get("semantic_function")
            if not space:
                continue
            entry = {
                "space": space,
                "zone": SPACE_ZONE.get(space),
                "evidence": [label.get("text")],
                "evidence_type": "label",
                "status": "label",
                "confidence": label.get("confidence") or "MEDIUM",
                "reasoning_source": (
                    "grounded label on the corresponding panel, mapped to the "
                    "matching geometry region"
                ),
                "source_panel_id": reading["panel_id"],
                "associated_region_id": label.get("associated_region_id"),
                "corresponding_region_id": target,
                "transfer": "corresponding_panel_geometric_region_match",
            }
            transfers.append(entry)
            if space in published:
                continue
            published.add(space)
            plan.setdefault("named_spaces", []).append(entry)
    plan["fusion"]["corresponding_label_transfers"] = transfers
    for item in plan.get("geometry_spaces", []) + plan.get(
        "architectural_elements", []
    ):
        item.setdefault("source_panel_id", canonical["panel_id"])
        item["coordinate_frame"] = "panel_analysis_pixels"
    # W4.1 — SHADOW MODE ONLY. Additive evidence contract for the fused plan.
    # No field above is modified and no function is resolved.
    from core.vision.architectural_function_evidence_v1 import (
        build_architectural_function_evidence,
    )

    plan["architectural_function_evidence"] = (
        build_architectural_function_evidence(plan)
    )
    return plan


def _render_independent_plan_report(plan):
    """Describe each plan separately, without floor-wide counts or relations."""
    roles = {
        DIMENSION_PLAN: "پلان اندازه‌گذاری",
        ARCHITECTURAL_PLAN: "پلان معماری",
        FURNISHED_ARCHITECTURAL_PLAN: "پلان معماری / پلان مبلمان",
        STRUCTURAL_PLAN: "پلان سازه‌ای",
        UNKNOWN_PLAN: "نوع نمایش نامشخص",
    }
    functions = [
        ("bedroom", "فضاهای خواب و خصوصی"),
        ("living room", "نشیمن"),
        ("dining", "فعالیت غذاخوری"),
        ("kitchen", "آشپزخانه و بخش خدماتی"),
        ("bathroom", "حمام یا سرویس بهداشتی"),
    ]
    elements = [
        ("stair", "نشانه‌های پلکان"),
        ("duct", "داکت خدماتی احتمالی"),
        ("shaft", "چاهک یا فضای خالی احتمالی"),
        ("column", "نشانه‌های ستون احتمالی"),
        ("axis", "نشانه‌های محورهای شبکه"),
    ]
    paragraphs = ["این شیت شامل چند پلان مستقل است که به‌صورت جداگانه تحلیل شده‌اند."]
    for index, reading in enumerate(plan["plans"], 1):
        supported = {
            entry.get("space")
            for key in ("named_spaces", "inferred_functions")
            for entry in reading.get(key, [])
        }
        phrases = [phrase for kind, phrase in functions if kind in supported]
        evidence = []
        if phrases:
            evidence.append("شواهد از " + "، ".join(phrases) + " پشتیبانی می‌کنند.")
        elif reading.get("geometry_spaces"):
            evidence.append("فضاهای محصور قابل تشخیص‌اند؛ کارکرد آن‌ها قطعی نیست.")
        if reading.get("furniture"):
            evidence.append("مبلمان یا تجهیزات با شواهد محلی قابل تشخیص است.")
        kinds = {o.get("kind") for o in reading.get("openings", [])}
        if "window" in kinds:
            evidence.append("پنجره با شواهد محلی قابل تشخیص است.")
        elif kinds & {"door", "opening", "entrance"}:
            evidence.append("نشانه‌های بازشو قابل تشخیص‌اند.")
        types = {e.get("type") for e in reading.get("architectural_elements", [])}
        symbols = [phrase for kind, phrase in elements if kind in types]
        if symbols:
            evidence.append("، ".join(symbols) + " قابل تشخیص است.")
        if not evidence:
            evidence.append("شواهد برای تعیین کارکرد و عناصر این پلان کافی نیست.")
        number = str(index).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
        paragraphs.append(
            "پلان "
            + number
            + " ("
            + roles.get(reading.get("role"), roles["unknown"])
            + "): "
            + " ".join(evidence)
        )
    return "\n\n".join(paragraphs)


def render_sheet_report(plan):
    """Concise sheet-level Persian projection, never thresholds or debug IDs."""
    if plan.get("representation") == "independent_plan_collection":
        return _render_independent_plan_report(plan)
    paired = plan["fusion"]["status"] == "corresponding_pair"
    roles = {p["role"] for p in plan["panel_readings"]}
    if paired and DIMENSION_PLAN in roles and (set(LAYOUT_ROLES) & roles):
        paragraphs = [
            "این شیت شامل دو نمایش متناظر از یک پلان طبقه است؛ یکی پلان اندازه‌گذاری و دیگری پلان معماری (پلان مبلمان)."
        ]
    elif paired:
        paragraphs = ["این شیت دو نمایش با هندسهٔ متناظر از یک پلان را نشان می‌دهد."]
    else:
        paragraphs = [
            "این شیت چند پلان مستقل دارد؛ یکسان‌بودن هندسهٔ آن‌ها هنوز قطعی نیست."
        ]
    sources = [plan] if paired else [p["plan_reading"] for p in plan["panel_readings"]]
    functions = {f["space"] for p in sources for f in p.get("inferred_functions", [])}
    phrases = [
        phrase
        for kind, phrase in [
            ("bedroom", "فضاهای خواب و خصوصی"),
            ("living room", "نشیمن"),
            ("dining", "فعالیت غذاخوری"),
            ("kitchen", "آشپزخانه و بخش خدماتی"),
            ("bathroom", "حمام یا سرویس بهداشتی"),
        ]
        if kind in functions
    ]
    if phrases:
        paragraphs.append(
            "شواهد مبلمان و تجهیزات از " + "، ".join(phrases) + " پشتیبانی می‌کنند."
        )
    elif set(LAYOUT_ROLES) & roles:
        paragraphs.append(
            "در نمای مبلمان، چند مجموعهٔ مبلمان قابل تشخیص است؛ نوع و کارکرد همهٔ فضاها از این خوانش هنوز قطعی نیست."
        )
    core = plan.get("central_core") or {}
    if core.get("status") == "grounded_candidate":
        paragraphs.append(
            "نشانه‌های پلکان در بخش مرکزی پلان و بازشوهای دسترسی در کنار آن قابل تشخیص‌اند."
        )
        if core.get("shaft_ids"):
            paragraphs.append(
                "یک چاهک یا فضای خالی محصور در کنار هستهٔ مرکزی قابل تشخیص است؛ آسانسوربودن آن قطعی نیست."
            )
    organization = plan.get("spatial_organization") or {}
    if organization.get("repeated_spatial_groups"):
        paragraphs.append(
            "دو بخش فضایی تقریباً متقارن پیرامون هستهٔ مرکزی دیده می‌شود؛ "
            + (
                "تکرار کارکردها و ورودی‌های مستقل، دو واحد احتمالی را مطرح می‌کند."
                if organization.get("unit_count_candidate")
                else "مستقل‌بودن آن‌ها به‌عنوان دو واحد هنوز قطعی نیست."
            )
        )
    count = sum(
        o.get("instance_count", 0)
        for p in sources
        for o in p.get("openings", [])
        if o["kind"] == "window"
    )
    elements = [e for p in sources for e in p.get("architectural_elements", [])]
    visible = []
    if count > 1:
        visible.append("چند پنجره در جداره‌های پلان قابل تشخیص است.")
    elif count:
        visible.append(
            "یک پنجره با شواهد محلی قابل تشخیص است؛ شمار کل پنجره‌ها قطعی نیست."
        )
    if any(e["type"] == "axis" for e in elements):
        visible.append("نشانه‌های محورهای شبکه دیده می‌شوند.")
    if any(e["type"] == "column" for e in elements):
        visible.append("نشانه‌های ستون احتمالی نیز قابل تشخیص‌اند.")
    if visible:
        paragraphs.append(" ".join(visible))
    paragraphs.append(
        "تعداد دقیق فضاها و واحدها، ابعاد و سیستم سازه‌ای از این تصویر قطعی نیست."
    )
    return "\n\n".join(paragraphs)
