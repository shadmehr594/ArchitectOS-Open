"""Conservative plan-element helpers used by the existing local symbol reader.

No provider input, model weights, design rules or circulation evaluation.
All coordinates come from the current raster, never an acceptance layout.
"""

from __future__ import annotations

import hashlib
import math
import re

import numpy as np

VERSION = "plan-elements-v1"
TYPES = {"window", "door", "opening", "stair", "duct", "column", "axis", "level", "shaft"}

# An axis leader is routinely interrupted by the dimension chain's tick marks,
# witness lines and numerals. The required covered length is unchanged; only
# interruptions up to this fraction of the marker diameter are repaired before
# that length is measured, so a marker with no leader still fails.
AXIS_LEADER_MAX_GAP_FRACTION = 0.5


def _runs(values):
    changes = np.flatnonzero(np.diff(np.pad(np.asarray(values, dtype=np.int8), (1, 1))))
    return list(zip(changes[::2], changes[1::2]))


def _iou(a, b):
    area = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0, min(a[3], b[3]) - max(a[1], b[1])
    )
    return area / max(
        1, (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - area
    )


def _near(a, b):
    return math.hypot(
        max(0, a[0] - b[2], b[0] - a[2]), max(0, a[1] - b[3], b[1] - a[3])
    )


def _leader_support(profile, max_gap):
    """Gap-tolerant aligned support along one axis leader.

    `profile` is the ink profile of a narrow strip running from a marker towards
    the drawing. A real leader is frequently interrupted by dimension ticks,
    witness lines and annotation, so a single uninterrupted run understates it.
    This aggregates collinear runs separated by gaps of at most `max_gap` and
    returns `(covered, support)`: the length of the longest aggregated span and
    the number of REAL ink pixels inside it. A sparse strip cannot pass on gap
    repair alone, and a strip crossed by a perpendicular dimension line
    contributes only a few pixels, so an arbitrary dimension line is still
    rejected.
    """
    runs = _runs(profile)
    if not runs:
        return 0, 0
    best = (0, 0)
    for index, (start, end) in enumerate(runs):
        covered = end - start
        support = end - start
        cursor = end
        for later_start, later_end in runs[index + 1:]:
            if later_start - cursor > max_gap:
                break
            covered = later_end - start
            support += later_end - later_start
            cursor = later_end
        if covered > best[0]:
            best = (covered, support)
    return best


def _record(gray, kind, box, cues, *, geometry=None, attributes=None, candidate=False):
    height, width = gray.shape
    x0, y0, x1, y1 = map(int, box)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(width, x1), min(height, y1)
    return {
        "type": kind,
        "class": kind,
        "kind": kind,
        "bbox_pixels": [x0, y0, x1, y1],
        "bbox_normalized": [
            round(x0 / width, 4),
            round(y0 / height, 4),
            round(x1 / width, 4),
            round(y1 / height, 4),
        ],
        "geometry": geometry or {},
        "attributes": attributes or {},
        "source": "local_raster_geometry",
        "producer": "core.vision.local_plan_elements_v1._record",
        "evidence_type": "local_raster_geometry",
        "provider_independent": True,
        "confidence": "MEDIUM",
        "status": "candidate" if candidate else "visible",
        "corroboration": cues,
        "evidence": "; ".join(cues),
        "raster_patch_sha256": hashlib.sha256(gray[y0:y1, x0:x1].tobytes()).hexdigest(),
    }


def _windows(cv2, gray, box):
    """Find rail-filled wall interruptions on either orientation.

    Wall bands come from thick line support, not the sheet/porch bounding edge.
    The narrow band excludes planting/furniture drawn outside the wall.
    """
    found = []
    for transpose in (False, True):
        source = gray.T if transpose else gray
        bounds = (box[1], box[0], box[3], box[2]) if transpose else box
        x0, y0, x1, y1 = bounds
        width = x1 - x0
        ink = (source < 165).astype(np.uint8)
        thick = cv2.morphologyEx(
            ink, cv2.MORPH_OPEN, np.ones((3, max(16, int(width * 0.09))), np.uint8)
        )
        bands = _runs(thick[:, x0:x1].sum(axis=1) >= width * 0.20)
        for start, end in bands:
            if not y0 - 4 <= (start + end) / 2 <= y1 + 4:
                continue
            # Perimeter on both sides: internal partitions are not perimeter windows.
            edge = start + int(np.argmax(thick[start:end, x0:x1].sum(axis=1)))
            if not (
                abs(edge - y0) < (y1 - y0) * 0.17 or abs(edge - y1) < (y1 - y0) * 0.08
            ):
                continue
            by0, by1 = max(0, start - 1), min(source.shape[0], end + 1)
            profile = ink[by0:by1, x0:x1].sum(axis=0)
            wall_depth = float(np.percentile(profile, 80))
            thin = (profile >= 1) & (profile <= min(5, max(2, wall_depth - 2)))
            thin = cv2.morphologyEx(
                thin.astype(np.uint8)[None, :],
                cv2.MORPH_CLOSE,
                np.ones((1, 3), np.uint8),
            )[0].astype(bool)
            for a, b in _runs(thin):
                length = b - a
                if not max(12, width * 0.04) <= length <= width * 0.34:
                    continue
                flank = max(5, int(width * 0.025))
                left, right = (
                    profile[max(0, a - flank) : a],
                    profile[b : min(width, b + flank)],
                )
                if min(len(left), len(right)) < 3 or min(
                    np.median(left), np.median(right)
                ) < max(4, wall_depth * 0.7):
                    continue
                patch = ink[by0:by1, x0 + a : x0 + b]
                rails = _runs(patch.sum(axis=1) >= length * 0.80)
                if len(rails) < 2 or any(v - u > 2 for u, v in rails):
                    continue
                bb = [x0 + a, by0, x0 + b, by1]
                if transpose:
                    bb = [bb[1], bb[0], bb[3], bb[2]]
                side = (
                    ("left" if edge < (y0 + y1) / 2 else "right")
                    if transpose
                    else ("top" if edge < (y0 + y1) / 2 else "bottom")
                )
                item = _record(
                    gray,
                    "window",
                    bb,
                    [
                        "parallel_glazing_rails",
                        "thick_wall_flanks",
                        "perimeter_wall_band",
                    ],
                    geometry={
                        "orientation": "vertical" if transpose else "horizontal",
                        "rail_count": len(rails),
                    },
                    attributes={"side": side},
                )
                item["side"] = side
                found.append(item)
    return found


def _thin_segments(cv2, ink, vertical, minimum):
    mask = cv2.morphologyEx(
        ink,
        cv2.MORPH_OPEN,
        np.ones((minimum, 1) if vertical else (1, minimum), np.uint8),
    )
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    segments = []
    for x, y, w, h, _ in stats[1:]:
        if (w if vertical else h) > 2:
            continue
        segments.append(
            (
                int(x + w / 2) if vertical else int(y + h / 2),
                int(y) if vertical else int(x),
                int(y + h) if vertical else int(x + w),
            )
        )
    return sorted(segments)


def _arrow(cv2, ink, bbox, orientation):
    x0, y0, x1, y1 = bbox
    crop = ink[y0:y1, x0:x1].copy()
    # Remove the hairline treads/shaft, leaving the solid arrow head.
    small = cv2.morphologyEx(crop, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(small, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    choices = []
    for c in contours:
        area = cv2.contourArea(c)
        x, y, w, h = cv2.boundingRect(c)
        if (
            not 3 <= area <= crop.size * 0.08
            or min(w, h) < 3
            or max(w, h) > min(crop.shape) * 0.5
        ):
            continue
        poly = cv2.approxPolyDP(c, cv2.arcLength(c, True) * 0.12, True).reshape(-1, 2)
        if len(poly) not in (3, 4):
            continue
        centre = poly.mean(axis=0)
        axis = 0 if orientation == "horizontal" else 1
        if abs(centre[1 - axis] - crop.shape[axis] / 2) > crop.shape[axis] * 0.28:
            continue
        head = small[y : y + h, x : x + w]
        profile = head.sum(axis=1 if axis == 1 else 0)
        if len(poly) == 4 and abs(float(profile[:2].mean() - profile[-2:].mean())) < 1:
            continue
        low = profile[:2].mean() < profile[-2:].mean()
        tip = (
            [x + (0 if low else w - 1), y + h // 2]
            if axis == 0
            else [x + w // 2, y + (0 if low else h - 1)]
        )
        direction = (
            ("left" if low else "right") if axis == 0 else ("up" if low else "down")
        )
        choices.append((area, direction, [int(x0 + tip[0]), int(y0 + tip[1])]))
    return max(choices, default=None)


def _stairs(cv2, gray, box):
    ink = (gray < 165).astype(np.uint8)
    scale = min(box[2] - box[0], box[3] - box[1])
    output = []
    for vertical in (False, True):
        segments = _thin_segments(cv2, ink, vertical, max(18, int(scale * 0.06)))
        for seed in segments:
            compatible = [
                s
                for s in segments
                if abs(s[1] - seed[1]) <= scale * 0.035
                and abs(s[2] - seed[2]) <= scale * 0.035
            ]
            groups = []
            group = []
            for s in compatible:
                if group and not 4 <= s[0] - group[-1][0] <= scale * 0.055:
                    groups.append(group)
                    group = []
                group.append(s)
            groups.append(group)
            for group in groups:
                if len(group) < 4:
                    continue
                gaps = np.diff([s[0] for s in group])
                if np.std(gaps) / np.mean(gaps) > 0.18:
                    continue
                lo = int(np.median([s[1] for s in group]))
                hi = int(np.median([s[2] for s in group]))
                a, b = group[0][0], group[-1][0]
                bb = (
                    [a - 2, lo - 2, b + 3, hi + 2]
                    if vertical
                    else [lo - 2, a - 2, hi + 2, b + 3]
                )
                if min(bb) < 0 or bb[2] > gray.shape[1] or bb[3] > gray.shape[0]:
                    continue
                if any(_iou(bb, x["bbox_pixels"]) > 0.55 for x in output):
                    continue
                orientation = "horizontal" if vertical else "vertical"
                # A two-dimensional cell grid with an arrow is still not a run.
                cross_lines = _thin_segments(
                    cv2,
                    ink[bb[1] : bb[3], bb[0] : bb[2]],
                    not vertical,
                    max(18, int((b - a) * 0.60)),
                )
                cross_extent = bb[3] - bb[1] if vertical else bb[2] - bb[0]
                cross_margin = max(4, int(cross_extent * 0.10))
                interior_cross_lines = [
                    line
                    for line in cross_lines
                    if cross_margin < line[0] < cross_extent - cross_margin
                ]
                if len(interior_cross_lines) >= 4:
                    continue
                arrow = _arrow(cv2, ink, bb, orientation)
                if arrow is None:
                    continue  # Parallel lines alone, blinds, grids and hatch are insufficient.
                cross = (
                    ink[max(0, lo - 3) : hi + 3, a : b + 1].T
                    if vertical
                    else ink[a : b + 1, max(0, lo - 3) : hi + 3]
                )
                side_support = [
                    float(
                        np.mean(
                            cross[:, max(0, k - 4) : min(cross.shape[1], k + 5)].max(
                                axis=1
                            )
                        )
                    )
                    for k in (3, cross.shape[1] - 4)
                ]
                if min(side_support) < 0.70:
                    continue
                # A thick end rail can hide the last counted riser from the thin-line mask.
                delta = round(float(np.median(gaps)))
                predicted = b + delta
                section = (
                    ink[max(0, lo) : hi, max(0, predicted - 1) : predicted + 2]
                    if vertical
                    else ink[max(0, predicted - 1) : predicted + 2, max(0, lo) : hi]
                )
                count = len(group)
                if (
                    section.size
                    and float(section.max(axis=1 if vertical else 0).mean()) > 0.90
                ):
                    count += 1
                    bb[2 if vertical else 3] = min(
                        gray.shape[1 if vertical else 0], predicted + 3
                    )
                output.append(
                    _record(
                        gray,
                        "stair",
                        bb,
                        [
                            "regular_parallel_riser_lines",
                            "bounded_stair_run",
                            "localized_direction_arrow",
                        ],
                        geometry={
                            "orientation": orientation,
                            "direction": arrow[1],
                            "arrow_tip_pixels": arrow[2],
                        },
                        attributes={
                            "step_count": count,
                            "riser_line_count": count,
                            "count_convention": "countable_drawn_riser_lines",
                            "step_count_confidence": "MEDIUM",
                        },
                    )
                )
    return output


def _axes(cv2, gray, box):
    ink = (gray < 205).astype(np.uint8)
    contours, _ = cv2.findContours(ink, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    pw, ph = box[2] - box[0], box[3] - box[1]
    output = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        cx, cy = x + w / 2, y + h / 2
        if (
            not min(pw, ph) * 0.045 <= min(w, h) <= min(pw, ph) * 0.12
            or not 0.8 < w / h < 1.2
        ):
            continue
        circularity = (
            4 * math.pi * cv2.contourArea(c) / max(1, cv2.arcLength(c, True) ** 2)
        )
        # Labels or a watermark can join the inner/outer contours. Retain
        # only a separately corroborated circular boundary and attached leader.
        radius = (w + h) / 4 - 1
        angles = np.linspace(0, 2 * math.pi, 60, endpoint=False)
        points = [
            (
                round(cx - 0.5 + radius * math.cos(a)),
                round(cy - 0.5 + radius * math.sin(a)),
            )
            for a in angles
        ]
        circular_support = np.mean(
            [
                ink[max(0, yy - 1) : yy + 2, max(0, xx - 1) : xx + 2].max(initial=0)
                for xx, yy in points
            ]
        )
        circular_boundary = circularity >= 0.72 or (
            circular_support >= 0.80 and cv2.contourArea(c) / (w * h) >= 0.60
        )
        if not circular_boundary or (box[0] < cx < box[2] and box[1] < cy < box[3]):
            continue
        # Only external markers with an attached line towards the drawing.
        top = cy < box[1]
        bottom = cy > box[3]
        left = cx < box[0]
        right = cx > box[2]
        if top or bottom:
            strip = (
                ink[
                    max(0, y + h - 1) : min(gray.shape[0], int(box[1]) + 2),
                    max(0, int(cx) - 1) : int(cx) + 2,
                ]
                if top
                else ink[box[3] : y + 1, int(cx) - 1 : int(cx) + 2]
            )
            active = strip.max(axis=1) if strip.size else []
            runs = _runs(active)
            required = h * 0.55
            covered, support = _leader_support(
                active, max(2, round(max(w, h) * AXIS_LEADER_MAX_GAP_FRACTION))
            )
            if covered < required or support < max(2, round(required * 0.5)):
                continue
            a, b = max(runs, key=lambda ab: ab[1] - ab[0])
            origin = y + h - 1 if top else box[3]
            line = [[round(cx, 1), int(origin + a)], [round(cx, 1), int(origin + b)]]
            ori = "vertical"
        elif left or right:
            origin = x + w - 1 if left else box[2]
            strip = (
                ink[int(cy) - 1 : int(cy) + 2, origin : box[0] + 2]
                if left
                else ink[int(cy) - 1 : int(cy) + 2, origin : x + 1]
            )
            active = strip.max(axis=0) if strip.size else []
            runs = _runs(active)
            required = w * 0.55
            covered, support = _leader_support(
                active, max(2, round(max(w, h) * AXIS_LEADER_MAX_GAP_FRACTION))
            )
            if covered < required or support < max(2, round(required * 0.5)):
                continue
            a, b = max(runs, key=lambda ab: ab[1] - ab[0])
            line = [[int(origin + a), round(cy, 1)], [int(origin + b), round(cy, 1)]]
            ori = "horizontal"
        else:
            continue
        if any(_iou([x, y, x + w, y + h], o["bbox_pixels"]) > 0.5 for o in output):
            continue
        output.append(
            _record(
                gray,
                "axis",
                [x, y, x + w, y + h],
                [
                    "external_circular_axis_marker",
                    "attached_axis_line",
                    "orthogonal_plan_alignment",
                ],
                geometry={
                    "orientation": ori,
                    "line_pixels": line,
                    "marker_center_pixels": [cx, cy],
                },
                attributes={"label": None, "label_status": "unread"},
            )
        )
    # A single circle/leader is not a structural grid.
    return [
        item
        for item in output
        if sum(
            x["geometry"]["orientation"] == item["geometry"]["orientation"]
            for x in output
        )
        >= 2
    ]


def _columns(cv2, gray, box, axes):
    from core.vision.local_plan_symbols_v1 import _walls

    ink = (gray < 150).astype(np.uint8)
    wall_mask = _walls(cv2, ink, box)
    pw, ph = box[2] - box[0], box[3] - box[1]
    # Compact solid blocks, not L-shaped wall intersections or outline fixtures.
    size = max(9, int(min(pw, ph) * 0.026))
    blocks = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((size, size), np.uint8))
    _, _, stats, _ = cv2.connectedComponentsWithStats(blocks)
    xs = [
        a["geometry"]["marker_center_pixels"][0]
        for a in axes
        if a["geometry"]["orientation"] == "vertical"
    ]
    ys = [
        a["geometry"]["marker_center_pixels"][1]
        for a in axes
        if a["geometry"]["orientation"] == "horizontal"
    ]
    output = []
    for x, y, w, h, area in stats[1:]:
        if (
            not size <= min(w, h) <= min(pw, ph) * 0.06
            or max(w, h) > min(pw, ph) * 0.075
            or not 0.5 < w / h < 2
            or area / (w * h) < 0.78
        ):
            continue
        if not (
            box[0] - 2 <= x < x + w <= box[2] + 2
            and box[1] - 2 <= y < y + h <= box[3] + 2
        ):
            continue
        cx, cy = x + w / 2, y + h / 2
        margin = max(8, int(min(pw, ph) * 0.04))
        context_x0, context_y0 = max(0, x - margin), max(0, y - margin)
        context = wall_mask[
            context_y0 : y + h + margin, context_x0 : x + w + margin
        ].copy()
        context[
            y - context_y0 : y - context_y0 + h, x - context_x0 : x - context_x0 + w
        ] = 0
        if int(context.sum()) < margin * 3:
            continue
        matched = [
            a
            for a in axes
            if abs(
                (cx if a["geometry"]["orientation"] == "vertical" else cy)
                - (
                    a["geometry"]["marker_center_pixels"][0]
                    if a["geometry"]["orientation"] == "vertical"
                    else a["geometry"]["marker_center_pixels"][1]
                )
            )
            <= max(w, h) * 0.8
        ]
        if (
            not xs
            or not ys
            or min(abs(cx - v) for v in xs) > max(w, h) * 0.8
            or min(abs(cy - v) for v in ys) > max(w, h) * 0.8
        ):
            continue
        output.append(
            _record(
                gray,
                "column",
                [x, y, x + w, y + h],
                [
                    "compact_solid_structural_symbol",
                    "two_axis_alignment",
                    "repeated_block_dimensions",
                    "wall_join_context",
                ],
                attributes={
                    "candidate": True,
                    "matched_axis_ids": [a["element_id"] for a in matched],
                },
                candidate=True,
            )
        )
    return [
        item
        for item in output
        if sum(
            0.6
            < (o["bbox_pixels"][2] - o["bbox_pixels"][0])
            / (item["bbox_pixels"][2] - item["bbox_pixels"][0])
            < 1.6
            for o in output
        )
        >= 3
    ]


def _ducts(cv2, gray, box, furniture, regions):
    ink = (gray < 165).astype(np.uint8)
    contours, tree = cv2.findContours(ink, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if tree is None:
        return []
    pw, ph = box[2] - box[0], box[3] - box[1]
    fixtures = [f for f in furniture if f["class"] == "sanitary_fixture"]
    output = []
    for i, c in enumerate(contours):
        if tree[0, i, 3] < 0:
            continue
        x, y, w, h = cv2.boundingRect(c)
        bb = [x, y, x + w, y + h]
        if (
            min(w, h) < max(8, min(pw, ph) * 0.022)
            or max(w, h) > max(pw, ph) * 0.13
            or w * h > pw * ph * 0.009
            or max(w, h) / min(w, h) < 1.6
        ):
            continue
        if (
            cv2.contourArea(c) / (w * h) < 0.65
            or float(ink[y + 2 : y + h - 2, x + 2 : x + w - 2].mean()) > 0.10
        ):
            continue
        surround = [
            ink[max(0, y) : y + h, max(0, x - 3) : x].mean(),
            ink[y : y + h, x + w : x + w + 3].mean(),
            ink[max(0, y - 3) : y, x : x + w].mean(),
            ink[y + h : y + h + 3, x : x + w].mean(),
        ]
        if sum(v > 0.50 for v in surround) < 2:
            continue
        if any(_iou(bb, f["bbox_pixels"]) > 0.12 for f in furniture):
            continue
        nearby = [
            f for f in fixtures if _near(bb, f["bbox_pixels"]) < min(pw, ph) * 0.055
        ]
        valid_regions = {
            r["region_id"] for r in regions if r.get("confidence") == "MEDIUM"
        }
        service_ids = sorted(
            {r for f in nearby for r in f.get("region_ids", []) if r in valid_regions}
        )
        if not nearby or not service_ids:
            continue
        output.append(
            _record(
                gray,
                "duct",
                bb,
                [
                    "small_enclosed_empty_void",
                    "adjacent_sanitary_fixture",
                    "independent_service_region",
                ],
                attributes={
                    "likely_type": "service_shaft",
                    "adjacent_service_region_ids": service_ids,
                    "adjacent_fixture_ids": [f["item_id"] for f in nearby],
                    "shared_service_supported": len(service_ids) > 1,
                },
                candidate=True,
            )
        )
    return output


def _doors(cv2, gray, box, furniture, stairs):
    from core.vision.local_plan_symbols_v1 import _walls

    ink = (gray < 205).astype(np.uint8)
    walls = _walls(cv2, ink, box)
    scale = min(box[2] - box[0], box[3] - box[1])
    protected = [x["bbox_pixels"] for x in furniture + stairs]
    output = []
    lines = []
    # Local line proposals preserve faint diagonal leaves missed by global Hough voting.
    tile = max(30, int(scale * 0.12))
    stride = tile // 2
    for y in range(box[1], box[3], stride):
        for x in range(box[0], box[2], stride):
            patch = ink[
                y : min(gray.shape[0], y + tile), x : min(gray.shape[1], x + tile)
            ]
            proposals = cv2.HoughLinesP(
                patch,
                1,
                np.pi / 180,
                threshold=7,
                minLineLength=max(10, int(scale * 0.03)),
                maxLineGap=2,
            )
            if proposals is not None:
                lines.extend(
                    (int(a + x), int(b + y), int(c + x), int(d + y))
                    for a, b, c, d in proposals[:, 0]
                )
    seen = set()
    for x0, y0, x1, y1 in lines:
        key = (x0 // 2, y0 // 2, x1 // 2, y1 // 2)
        if key in seen:
            continue
        seen.add(key)
        length = math.hypot(x1 - x0, y1 - y0)
        if not max(12, scale * 0.035) <= length <= scale * 0.115:
            continue
        angle = math.atan2(y1 - y0, x1 - x0)
        for hx, hy, base in ((x0, y0, angle), (x1, y1, angle + math.pi)):
            if (
                walls[max(0, hy - 5) : hy + 6, max(0, hx - 5) : hx + 6].max(initial=0)
                == 0
            ):
                continue
            for closed in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
                sweep = (closed - base + math.pi) % (2 * math.pi) - math.pi
                if not 0.5 <= abs(sweep) <= math.pi / 2 + 0.15:
                    continue
                endx, endy = (
                    round(hx + length * math.cos(closed)),
                    round(hy + length * math.sin(closed)),
                )
                if (
                    walls[max(0, endy - 5) : endy + 6, max(0, endx - 5) : endx + 6].max(
                        initial=0
                    )
                    == 0
                ):
                    continue
                angles = base + np.linspace(sweep * 0.10, sweep * 0.90, 24)
                px = np.rint(hx + length * np.cos(angles)).astype(int)
                py = np.rint(hy + length * np.sin(angles)).astype(int)
                if (
                    min(px) < 2
                    or min(py) < 2
                    or max(px) >= gray.shape[1] - 2
                    or max(py) >= gray.shape[0] - 2
                ):
                    continue
                support = np.array(
                    [ink[y - 1 : y + 2, x - 1 : x + 2].max() for x, y in zip(px, py)]
                )
                if support.mean() < 0.94:
                    continue
                ix = np.rint(hx + length * 0.65 * np.cos(angles)).astype(int)
                iy = np.rint(hy + length * 0.65 * np.sin(angles)).astype(int)
                if ink[iy, ix].mean() > 0.15:
                    continue
                bb = [
                    min(hx, endx, x0, x1, int(px.min())) - 2,
                    min(hy, endy, y0, y1, int(py.min())) - 2,
                    max(hx, endx, x0, x1, int(px.max())) + 3,
                    max(hy, endy, y0, y1, int(py.max())) + 3,
                ]
                if not (
                    box[0] <= bb[0] < bb[2] <= box[2]
                    and box[1] <= bb[1] < bb[3] <= box[3]
                ):
                    continue
                patch = ink[bb[1] : bb[3], bb[0] : bb[2]]
                hatch = False
                for vert in (False, True):
                    runs = _thin_segments(
                        cv2, patch, vert, max(8, int(min(patch.shape) * 0.4))
                    )
                    if len(runs) >= 3 and np.median(np.diff([s[0] for s in runs])) <= 5:
                        hatch = True
                if hatch:
                    continue
                if any(_near(bb, p) < 3 for p in protected) or any(
                    _iou(bb, o["bbox_pixels"]) > 0.30 for o in output
                ):
                    continue
                output.append(
                    _record(
                        gray,
                        "door",
                        bb,
                        ["localized_swing_arc", "leaf_segment", "two_wall_jambs"],
                        geometry={
                            "hinge_pixels": [hx, hy],
                            "swing_angle_degrees": round(abs(sweep) * 180 / math.pi, 1),
                        },
                        attributes={"opening_type": "swing_door"},
                    )
                )
    return output


def _level_marks(cv2, gray, box):
    ink = (gray < 165).astype(np.uint8)
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        1,
        minDist=15,
        param1=100,
        param2=12,
        minRadius=5,
        maxRadius=max(6, int(min(gray.shape) * 0.025)),
    )
    output = []
    if circles is None:
        return output
    for cx, cy, r in np.rint(circles[0]).astype(int):
        # Refine the Hough centre using the opposite filled quadrants.
        refinements = []
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                xx, yy = cx + dx, cy + dy
                if (
                    xx - r < 0
                    or yy - r < 0
                    or xx + r >= gray.shape[1]
                    or yy + r >= gray.shape[0]
                ):
                    continue
                q = [
                    ink[yy - r + 2 : yy - 1, xx - r + 2 : xx - 1].mean(),
                    ink[yy - r + 2 : yy - 1, xx + 1 : xx + r - 1].mean(),
                    ink[yy + 1 : yy + r - 1, xx - r + 2 : xx - 1].mean(),
                    ink[yy + 1 : yy + r - 1, xx + 1 : xx + r - 1].mean(),
                ]
                score = (
                    abs(q[0] + q[3] - q[1] - q[2]) - abs(q[0] - q[3]) - abs(q[1] - q[2])
                )
                refinements.append((score, xx, yy))
        if refinements:
            _, cx, cy = max(refinements)
        if (
            cx - r < 0
            or cy - r < 0
            or cx + r >= gray.shape[1]
            or cy + r >= gray.shape[0]
        ):
            continue
        quads = [
            ink[cy - r + 2 : cy - 1, cx - r + 2 : cx - 1].mean(),
            ink[cy - r + 2 : cy - 1, cx + 1 : cx + r - 1].mean(),
            ink[cy + 1 : cy + r - 1, cx - r + 2 : cx - 1].mean(),
            ink[cy + 1 : cy + r - 1, cx + 1 : cx + r - 1].mean(),
        ]
        if any(not math.isfinite(v) for v in quads) or not (
            max(quads) > 0.65 and min(quads) < 0.35
        ):
            continue
        if not (
            abs(quads[0] - quads[3]) < 0.3
            and abs(quads[1] - quads[2]) < 0.3
            and abs(quads[0] - quads[1]) > 0.35
        ):
            continue
        arms = [
            ink[max(0, cy - 1) : cy + 2, max(0, cx - r * 2) : cx - r]
            .max(axis=0)
            .mean(),
            ink[cy - 1 : cy + 2, cx + r : min(gray.shape[1], cx + r * 3)]
            .max(axis=0)
            .mean(),
            ink[max(0, cy - r * 2) : cy - r, cx - 1 : cx + 2].max(axis=1).mean(),
            ink[cy + r : min(gray.shape[0], cy + r * 2), cx - 1 : cx + 2]
            .max(axis=1)
            .mean(),
        ]
        if min(arms) < 0.20 or sum(a > 0.6 for a in arms) < 3:
            continue
        output.append(
            _record(
                gray,
                "level",
                [cx - r, cy - r, cx + r + 1, cy + r + 1],
                [
                    "quartered_elevation_marker",
                    "orthogonal_cross_hairs",
                    "localized_numeric_annotation_required",
                ],
                geometry={"center_pixels": [int(cx), int(cy)]},
                attributes={"elevation_m": None, "annotation_status": "unread"},
            )
        )
    return output


def _numeric_ocr(gray, levels, stairs, axes, tessdata_path):
    """Separate localized numeric passes; historical Persian label OCR is untouched."""
    try:
        import cv2
        from tesserocr import OEM, PSM, PyTessBaseAPI

        with PyTessBaseAPI(
            path=str(tessdata_path), lang="eng", psm=PSM.SINGLE_LINE, oem=OEM.LSTM_ONLY
        ) as api:
            for item in levels:
                x0, y0, x1, y1 = item["bbox_pixels"]
                r = (x1 - x0) / 2
                cy = item["geometry"]["center_pixels"][1]
                bb = [
                    x1,
                    max(0, round(cy - r * 1.7)),
                    min(gray.shape[1], round(x1 + r * 5)),
                    cy,
                ]
                reads = []
                for threshold in (145, 155, 165, 190, 210):
                    crop = gray[bb[1] : bb[3], bb[0] : bb[2]]
                    data = cv2.resize(
                        crop, None, fx=8, fy=8, interpolation=cv2.INTER_CUBIC
                    )
                    data = np.pad(
                        np.where(data < threshold, 0, 255).astype(np.uint8),
                        12,
                        constant_values=255,
                    )
                    api.SetVariable("tessedit_char_whitelist", "0123456789.+-±")
                    api.SetImageBytes(
                        data.tobytes(), data.shape[1], data.shape[0], 1, data.shape[1]
                    )
                    api.SetSourceResolution(70)
                    text = (api.GetUTF8Text() or "").strip()
                    confidence = api.MeanTextConf()
                    match = re.fullmatch(r"([+\-±])?(\d{1,2}\.\d{2})", text)
                    if match and confidence >= 30:
                        value = float(match[2]) * (-1 if match[1] == "-" else 1)
                        # Zero can be corroborated by the marker even if ± was segmented.
                        if match[1] or value == 0:
                            reads.append((value, text, confidence, threshold))
                if len(reads) >= 2 and len({r[0] for r in reads}) == 1:
                    item["attributes"].update(
                        elevation_m=reads[0][0],
                        annotation_status="grounded_ocr",
                        annotation={
                            "bbox_pixels": bb,
                            "raw_text": reads[0][1],
                            "source": "local_numeric_ocr",
                            "confidence": "MEDIUM",
                            "ocr_confidence": min(r[2] for r in reads),
                            "independent_thresholds": [r[3] for r in reads],
                        },
                    )
                    item["corroboration"].append("signed_decimal_level_ocr_agreement")
            # Read axis identifiers separately; never infer a sequence of names.
            for item in axes:
                x0, y0, x1, y1 = item["bbox_pixels"]
                margin = max(3, round(min(x1 - x0, y1 - y0) * 0.15))
                bb = [x0 + margin, y0 + margin, x1 - margin, y1 - margin]
                reads = []
                for threshold in (165, 205):
                    crop = gray[bb[1] : bb[3], bb[0] : bb[2]]
                    data = cv2.resize(
                        crop, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC
                    )
                    data = np.pad(
                        np.where(data < threshold, 0, 255).astype(np.uint8),
                        12,
                        constant_values=255,
                    )
                    api.SetPageSegMode(PSM.SINGLE_CHAR)
                    api.SetVariable(
                        "tessedit_char_whitelist",
                        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                    )
                    api.SetImageBytes(
                        data.tobytes(), data.shape[1], data.shape[0], 1, data.shape[1]
                    )
                    api.SetSourceResolution(70)
                    text = (api.GetUTF8Text() or "").strip()
                    if re.fullmatch(r"[A-Z0-9]", text) and api.MeanTextConf() >= 45:
                        reads.append(text)
                if len(reads) == 2 and reads[0] == reads[1]:
                    item["attributes"].update(
                        label=reads[0],
                        label_status="grounded_ocr",
                        label_source="local_marker_ocr",
                    )
            # Riser text is accepted only with an explicit riser cue and units.
            api.SetVariable("tessedit_char_whitelist", "")
            for item in stairs:
                x0, y0, x1, y1 = item["bbox_pixels"]
                margin = max(x1 - x0, y1 - y0) * 0.5
                bb = [
                    max(0, round(x0 - margin)),
                    max(0, round(y0 - margin)),
                    min(gray.shape[1], round(x1 + margin)),
                    min(gray.shape[0], round(y1 + margin)),
                ]
                reads = []
                for threshold in (165, 190, 210, 220):
                    crop = gray[bb[1] : bb[3], bb[0] : bb[2]].copy()
                    # The run's lines are not annotation glyphs. Keep nearby
                    # text separate rather than OCR-ing treads as digits.
                    crop[y0 - bb[1] : y1 - bb[1], x0 - bb[0] : x1 - bb[0]] = 255
                    data = cv2.resize(
                        crop, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC
                    )
                    data = np.pad(
                        np.where(data < threshold, 0, 255).astype(np.uint8),
                        12,
                        constant_values=255,
                    )
                    api.SetPageSegMode(PSM.SPARSE_TEXT)
                    api.SetImageBytes(
                        data.tobytes(), data.shape[1], data.shape[0], 1, data.shape[1]
                    )
                    api.SetSourceResolution(70)
                    text = api.GetUTF8Text() or ""
                    match = re.search(
                        r"(?<![A-Za-z])(?:riser|r|h)\s*[:=]?\s*(\d{1,2}(?:\.\d+)?)\s*(cm|mm|m)\b",
                        text,
                        re.IGNORECASE,
                    )
                    if match and api.MeanTextConf() >= 40:
                        value = (
                            float(match[1])
                            * {"cm": 0.01, "mm": 0.001, "m": 1}[match[2].lower()]
                        )
                        if 0.03 < value < 0.5:
                            reads.append(
                                (value, match[0], threshold, api.MeanTextConf())
                            )
                if len(reads) >= 2 and len({r[0] for r in reads}) == 1:
                    item["attributes"].update(
                        riser_height_m=reads[0][0],
                        riser_annotation={
                            "raw_text": reads[0][1],
                            "bbox_pixels": bb,
                            "source": "local_numeric_ocr",
                            "confidence": "MEDIUM",
                            "independent_thresholds": [r[2] for r in reads],
                            "ocr_confidence": min(r[3] for r in reads),
                        },
                    )
    except (ImportError, RuntimeError):
        return


def analyze_plan_elements(
    gray, plan_box, furniture, enclosure_geometry, tessdata_path=None
):
    import cv2

    axes = _axes(cv2, gray, plan_box)
    for i, item in enumerate(axes):
        item["element_id"] = f"axis{i + 1}"
    stairs = _stairs(cv2, gray, plan_box)
    levels = _level_marks(cv2, gray, plan_box)
    if tessdata_path:
        _numeric_ocr(gray, levels, stairs, axes, tessdata_path)
    found = (
        _windows(cv2, gray, plan_box)
        + stairs
        + levels
        + axes
        + _columns(cv2, gray, plan_box, axes)
        + _ducts(cv2, gray, plan_box, furniture, enclosure_geometry.get("regions", []))
        + _doors(cv2, gray, plan_box, furniture, stairs)
    )
    for i, item in enumerate(found):
        if "element_id" not in item:
            item["element_id"] = f"e{i + 1}"
    return {"version": VERSION, "status": "analyzed", "element_evidence": found}


def merge_local_openings(gray, legacy, elements):
    """Retain previous PNG openings; add new localized instances without doubling."""
    result = list(elements)
    for old in legacy:
        bb = old["bbox_pixels"]
        matched = next(
            (
                e
                for e in result
                if e["type"] == "window"
                and e.get("side") == old.get("side")
                and min(bb[2], e["bbox_pixels"][2]) - max(bb[0], e["bbox_pixels"][0])
                >= min(bb[2] - bb[0], e["bbox_pixels"][2] - e["bbox_pixels"][0]) * 0.75
                and abs((bb[1] + bb[3] - e["bbox_pixels"][1] - e["bbox_pixels"][3]) / 2)
                < 10
            ),
            None,
        )
        if matched:
            matched["legacy_opening_evidence"] = old
            continue
        item = _record(
            gray,
            "window",
            bb,
            [
                "thin_nonempty_perimeter_interruption",
                "thick_wall_flanks",
                "historical_local_raster_window",
            ],
            geometry={
                "orientation": "horizontal",
                "window_symbol_convention": "thin_perimeter_interruption",
            },
            attributes={"side": old.get("side")},
        )
        # This is a wrapper around an existing detection, not a new producer.
        item["producer"] = old.get("producer") or "UNKNOWN"
        item["side"] = old.get("side")
        item["legacy_opening_evidence"] = old
        item["element_id"] = f"legacy_window_{len(result) + 1}"
        result.append(item)
    openings = [
        {**e, "status": "visible"}
        for e in result
        if e["type"] in ("window", "door", "opening") and e["status"] == "visible"
    ]
    return openings, result


def grounded_plan_elements(local):
    """Only independently supplied, localized local contracts can be consumed."""
    if (
        not isinstance(local, dict)
        or local.get("element_analysis_status") != "analyzed"
    ):
        return []
    size = local.get("image_size") or {}
    width, height = size.get("width"), size.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        return []
    output = []
    for entry in local.get("element_evidence") or []:
        if not isinstance(entry, dict) or entry.get("type") not in TYPES:
            continue
        bb = entry.get("bbox_pixels")
        if (
            not isinstance(bb, (tuple, list))
            or len(bb) != 4
            or not all(type(v) is int for v in bb)
        ):
            continue
        if not (0 <= bb[0] < bb[2] <= width and 0 <= bb[1] < bb[3] <= height):
            continue
        if (
            entry.get("source") != "local_raster_geometry"
            or entry.get("provider_independent") is not True
            or entry.get("status") not in ("visible", "candidate")
            or entry.get("confidence") not in ("MEDIUM", "HIGH")
            or len(entry.get("corroboration") or []) < 3
            or not re.fullmatch(
                r"[0-9a-f]{64}", str(entry.get("raster_patch_sha256") or "")
            )
        ):
            continue
        if not isinstance(entry.get("geometry"), dict) or not isinstance(
            entry.get("attributes"), dict
        ):
            continue
        geometry, attrs = entry["geometry"], entry["attributes"]
        if entry["type"] in ("window", "stair", "axis") and geometry.get(
            "orientation"
        ) not in ("horizontal", "vertical"):
            continue
        if entry["type"] == "stair" and (
            not ((type(attrs.get("step_count")) is int and 1 <= attrs["step_count"] <= 100)
                 or (attrs.get("step_count") is None and attrs.get("step_count_status") == "partial"
                     and attrs.get("paired_flight_context") is True))
            or (geometry.get("direction") not in ("left", "right", "up", "down")
                and not (geometry.get("direction") == "unknown"
                         and attrs.get("paired_flight_context") is True
                         and {"two_outer_stringers", "intermediate_flight_separator"} <= set(entry.get("corroboration", []))))
        ):
            continue
        if entry["type"] == "shaft" and not (
            entry.get("status") == "candidate"
            and attrs.get("likely_type") == "core_shaft_or_void"
            and attrs.get("elevator_confirmed") is False
            and {"compact_enclosed_core_void", "crossed_diagonal_void_symbol",
                 "adjacent_grounded_paired_flight"} <= set(entry.get("corroboration", []))
        ):
            continue
        if entry["type"] == "column" and (
            attrs.get("candidate") is not True
            or len(attrs.get("matched_axis_ids", [])) < 2
        ):
            continue
        if entry["type"] == "duct" and not (
            attrs.get("adjacent_service_region_ids")
            and attrs.get("adjacent_fixture_ids")
        ):
            continue
        if (
            entry["type"] == "level"
            and attrs.get("annotation_status") == "grounded_ocr"
        ):
            annotation = attrs.get("annotation") or {}
            if (
                annotation.get("source") != "local_numeric_ocr"
                or len(set(annotation.get("independent_thresholds", []))) < 2
                or annotation.get("ocr_confidence", 0) < 30
            ):
                entry = {
                    **entry,
                    "attributes": {
                        **attrs,
                        "elevation_m": None,
                        "annotation_status": "unverified",
                    },
                }
        output.append(entry)
    return output


def _derived_general_riser(stairs, levels):
    """Compute a conditional plan-level value, without assigning either run.

    Grounded endpoints alone do not establish a particular stair connection.
    Equal grounded counts permit a general conclusion; differing or missing
    counts leave even that conclusion ambiguous. This adds no observed label.
    """
    if not stairs or len(levels) != 2:
        return None
    for item in [*stairs, *levels]:
        if (
            item.get("source") != "local_raster_geometry"
            or item.get("provider_independent") is not True
            or item.get("confidence") not in ("MEDIUM", "HIGH")
            or item.get("status") != "visible"
        ):
            return None
    counts = [s["attributes"].get("step_count") for s in stairs]
    if not all(type(n) is int and 1 <= n <= 100 for n in counts):
        return None
    if len(set(counts)) != 1:
        return None
    values = []
    for level in levels:
        attrs = level["attributes"]
        annotation = attrs.get("annotation") or {}
        value = attrs.get("elevation_m")
        if (
            attrs.get("annotation_status") != "grounded_ocr"
            or annotation.get("source") != "local_numeric_ocr"
            or annotation.get("confidence") not in ("MEDIUM", "HIGH")
            or annotation.get("ocr_confidence", 0) < 30
            or len(set(annotation.get("independent_thresholds", []))) < 2
            or type(value) not in (int, float)
            or not math.isfinite(value)
            or abs(value) >= 100
        ):
            return None
        values.append(value)
    rise = round(abs(values[1] - values[0]), 4)
    if rise == 0:
        return None
    riser = round(rise / counts[0], 6)
    return {
        "type": "derived_stair_riser",
        "status": "computed",
        "confidence": "MEDIUM",
        "step_count": counts[0],
        "lower_level": min(values),
        "upper_level": max(values),
        "total_rise_m": rise,
        "derived_riser_m": riser,
        "derived_riser_cm": round(riser * 100, 4),
        "derivation": "level_difference / grounded_step_count",
        "provenance": "computed_from_grounded_evidence",
        "association": "general_unassigned",
        "run_id": None,
        "assigned_run_ids": [],
        "candidate_step_evidence_ids": [s["element_id"] for s in stairs],
        "level_evidence_ids": [l["element_id"] for l in levels],
    }


def interpret_plan_elements(elements, functions):
    """Architectural meaning without evaluating routes, safety or design."""
    stairs = [x for x in elements if x["type"] == "stair"]
    levels = [
        x
        for x in elements
        if x["type"] == "level"
        and x["attributes"].get("annotation_status") == "grounded_ocr"
    ]
    meanings = []
    derived = _derived_general_riser(stairs, levels)
    if derived:
        meanings.append(derived)
    # A pair of level annotations describes plan levels, not a proven
    # connection through every nearby stair. Keep this relationship independent.
    if len(levels) == 2:
        a, b = levels
        av, bv = a["attributes"].get("elevation_m"), b["attributes"].get("elevation_m")
        if (
            all(
                isinstance(v, (int, float)) and math.isfinite(v) and abs(v) < 100
                for v in (av, bv)
            )
            and av != bv
        ):
            meanings.append(
                {
                    "type": "floor_elevation_relationship",
                    "confidence": "MEDIUM",
                    "plan_level_relationship": {
                        "level_ids": [a["element_id"], b["element_id"]],
                        "from_m": min(av, bv),
                        "to_m": max(av, bv),
                        "difference_m": round(abs(bv - av), 4),
                        "source": "two_grounded_plan_level_annotations",
                        "association": "plan_level_context_only",
                    },
                }
            )
    for stair in stairs:
        attrs = stair["attributes"]
        count = attrs.get("step_count")
        meaning = {
            "element_id": stair["element_id"],
            "type": "vertical_access",
            "confidence": stair["confidence"],
            "step_count": count,
            "role": None,
            "total_rise_m": None,
            "source": "grounded_plan_elements",
        }
        riser = attrs.get("riser_height_m")
        annotation = attrs.get("riser_annotation") or {}
        if (
            type(count) is int
            and 1 <= count <= 100
            and isinstance(riser, (int, float))
            and 0.03 < riser < 0.5
            and annotation.get("source") == "local_numeric_ocr"
            and len(set(annotation.get("independent_thresholds", []))) >= 2
            and annotation.get("ocr_confidence", 0) >= 40
            and annotation.get("confidence") in ("MEDIUM", "HIGH")
        ):
            meaning.update(
                total_rise_m=round(count * riser, 4),
                rise_basis="grounded_step_count_times_grounded_riser",
                riser_height_m=riser,
            )
        meanings.append(meaning)
    for item in elements:
        if item["type"] == "duct":
            attrs = item["attributes"]
            ids = attrs.get("adjacent_service_region_ids", [])
            supported = [
                f
                for f in functions
                if f.get("region_id") in ids
                and f.get("space") in ("bathroom", "wc", "kitchen")
            ]
            if supported:
                meanings.append(
                    {
                        "element_id": item["element_id"],
                        "type": "service_shaft_candidate",
                        "adjacent_service_region_ids": ids,
                        "supported_adjacent_functions": sorted(
                            {f["space"] for f in supported}
                        ),
                        "shared_service_supported": len(
                            {f["region_id"] for f in supported}
                        )
                        > 1,
                        "confidence": item["confidence"],
                    }
                )
    axes = [x for x in elements if x["type"] == "axis"]
    columns = [x for x in elements if x["type"] == "column"]
    if axes and columns:
        meanings.append(
            {
                "type": "structural_grid_organization_candidate",
                "axis_ids": [a["element_id"] for a in axes],
                "column_ids": [c["element_id"] for c in columns],
                "confidence": "MEDIUM",
            }
        )
    return meanings
