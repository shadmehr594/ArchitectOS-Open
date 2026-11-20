"""Conservative, model-free architectural symbol evidence from plan pixels.

No provider text, room labels, acceptance filenames or image coordinates enter
this module. Repeated cushion/mattress cells, terminal pillow shapes, seating
rows, sink/counter assemblies and cistern/bowl assemblies are the supported
symbol families. Unrecognised drawing conventions remain unknown.
"""

from __future__ import annotations

import hashlib

import numpy as np

VERSION = "furnished-plan-symbols-v1"
FUNCTIONS = {
    "bed": "bedroom",
    "sofa": "living room",
    "seating": "living room",
    "chair": None,
    "dining_surface": "dining",
    "kitchen_counter": "kitchen",
    "kitchen_sink_arrangement": "kitchen",
    "sanitary_fixture": "bathroom",
    "storage_cabinet": None,
}

# LIGHT-LINE SYMBOL FAMILIES — plan renderings often draw furniture lighter
# than the walls. Only the structurally specific families below may be
# accepted from a light-line pass, and only when they survive two light
# thresholds; the loose upholstery classes (sofa/seating/chair) stay on
# dark-line evidence so a light quilt/hatch texture cannot invent seating.
LIGHT_LINE_CLASSES = frozenset(
    {
        "bed",
        "dining_surface",
        "kitchen_counter",
        "kitchen_sink_arrangement",
        "sanitary_fixture",
    }
)

# ENCLOSURE WALL-LEVEL LADDER — the first level is the historical dark mask and
# defines the baseline region set. A drawing whose INTERIOR partitions are
# lighter than its perimeter walls leaves those partitions outside the dark
# mask, so rooms merge into one another. The higher levels are therefore
# evaluated as additional SUPPORT for extra regions, never as a replacement:
# an extra region must be spatially stable at every higher level, stable across
# the existing gap-repair scales, large enough to be a space rather than a
# sliver, and must not be a furniture symbol. A raised threshold alone can
# never add a room.
ENCLOSURE_WALL_LEVELS = (165, 190, 215)

# A level-admitted region must be a substantial space, not a sliver created by
# the extra strokes a higher level admits (hatching, texture, annotation).
ENCLOSURE_LEVEL_MIN_AREA_FRACTION = 0.01


def _iou(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x1 - x0) * max(0, y1 - y0)
    return intersection / max(
        1, (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    )


def _inside(box, outer, margin=0):
    return (
        box[0] >= outer[0] + margin
        and box[1] >= outer[1] + margin
        and box[2] <= outer[2] - margin
        and box[3] <= outer[3] - margin
    )


def _box(cv2, contour):
    x, y, w, h = cv2.boundingRect(contour)
    return [int(x), int(y), int(x + w), int(y + h)]


def _children(hierarchy, index):
    children = []
    child = int(hierarchy[index, 2])
    while child >= 0:
        children.append(child)
        child = int(hierarchy[child, 0])
    return children


def _interior_holes(hierarchy, root):
    """White interiors at odd nesting depths, including detached pillows."""
    holes = []
    pending = [(child, 1) for child in _children(hierarchy, root)]
    while pending:
        index, depth = pending.pop()
        if depth % 2:
            holes.append(index)
        pending.extend((child, depth + 1) for child in _children(hierarchy, index))
    return holes


def _walls(cv2, ink, box, include_windows=False):
    """Long, thick orthogonal strokes, not symbol/text/stair hairlines."""
    w, h = box[2] - box[0], box[3] - box[1]
    horizontal_wall = cv2.morphologyEx(
        ink, cv2.MORPH_OPEN, np.ones((3, max(20, int(w * 0.10))), np.uint8)
    )
    vertical_wall = cv2.morphologyEx(
        ink, cv2.MORPH_OPEN, np.ones((max(20, int(h * 0.08)), 3), np.uint8)
    )
    walls = horizontal_wall | vertical_wall
    if include_windows:
        # Thin perimeter windows join thick wall rails, not furniture edges.
        horizontal = cv2.morphologyEx(
            ink, cv2.MORPH_OPEN, np.ones((1, max(20, int(w * 0.12))), np.uint8)
        )
        vertical = cv2.morphologyEx(
            ink, cv2.MORPH_OPEN, np.ones((max(20, int(h * 0.12)), 1), np.uint8)
        )
        horizontal_bands = cv2.dilate(
            (horizontal_wall.sum(axis=1) > w * 0.06).astype(np.uint8)[:, None],
            np.ones((9, 1), np.uint8),
        )
        vertical_bands = cv2.dilate(
            (vertical_wall.sum(axis=0) > h * 0.06).astype(np.uint8)[None, :],
            np.ones((1, 9), np.uint8),
        )
        walls |= horizontal * horizontal_bands | vertical * vertical_bands
    return walls


def _repair_free(cv2, walls, box, fraction):
    """Repaired wall mask plus the 4-connected free-space labelling.

    Shared by `_enclosures` (which scores regions at ONE gap scale) and by
    `_enclosure_consensus` (which needs the raw free-space COMPONENTS, not the
    filtered regions, to tell when a level merged a room with the exterior).
    """
    pw, ph = box[2] - box[0], box[3] - box[1]
    horizontal_walls = cv2.morphologyEx(
        walls, cv2.MORPH_OPEN, np.ones((1, max(15, int(pw * 0.07))), np.uint8)
    )
    vertical_walls = cv2.morphologyEx(
        walls, cv2.MORPH_OPEN, np.ones((max(15, int(ph * 0.07)), 1), np.uint8)
    )
    horizontal = cv2.morphologyEx(
        horizontal_walls,
        cv2.MORPH_CLOSE,
        np.ones((1, max(3, int(pw * fraction))), np.uint8),
    )
    vertical = cv2.morphologyEx(
        vertical_walls,
        cv2.MORPH_CLOSE,
        np.ones((max(3, int(ph * fraction)), 1), np.uint8),
    )
    repaired = walls | horizontal | vertical
    count, labels, stats, centres = cv2.connectedComponentsWithStats(
        1 - repaired, 4
    )
    return repaired, count, labels, stats, centres


def _exterior_free_mask(cv2, walls, box, fraction=0.14):
    """Free-space pixels belonging to the drawing's exterior/background.

    A free-space component whose bounding box is NOT contained in the plan box
    is the exterior. When an interior room merges with it at one binarization
    level, that level simply failed to CLOSE the room's boundary; it did not
    observe a different room. The level is therefore uninformative about that
    room rather than evidence against it (see `_enclosure_consensus`).
    """
    repaired, count, labels, stats, _ = _repair_free(cv2, walls, box, fraction)
    mask = np.zeros(repaired.shape, dtype=bool)
    for i in range(1, count):
        x, y, w, h, _area = (int(v) for v in stats[i])
        if not _inside([x, y, x + w, y + h], box):
            mask |= labels == i
    return mask


def _enclosures(cv2, walls, box):
    """Bounded free raster components after limited door/window gap repair.

    An opening is not treated as a path-quality measurement. Different repair
    scales are kept as count uncertainty, never resolved with semantic labels.
    """
    pw, ph = box[2] - box[0], box[3] - box[1]
    variants = []
    for fraction in (0.10, 0.14, 0.18):
        _, count, labels, stats, centres = _repair_free(cv2, walls, box, fraction)
        regions = []
        for i in range(1, count):
            x, y, w, h, area = map(int, stats[i])
            bbox = [x, y, x + w, y + h]
            if not _inside(bbox, box) or area < pw * ph * 0.004:
                continue
            if min(w, h) < min(pw, ph) * 0.035:
                continue
            regions.append(
                {
                    "bbox_pixels": bbox,
                    "pixel_area": area,
                    "centroid_pixels": [float(v) for v in centres[i]],
                    "label": i,
                }
            )
        variants.append((regions, labels, fraction))
    # The middle scale localises regions; count variation is preserved below.
    selected, labels, fraction = variants[1]
    region_list = []
    for i, region in enumerate(
        sorted(selected, key=lambda r: (r["bbox_pixels"][1], r["bbox_pixels"][0]))
    ):
        stable = all(
            any(
                _iou(region["bbox_pixels"], other["bbox_pixels"]) > 0.65 for other in rs
            )
            for rs, _, _ in variants
        )
        region_list.append(
            {
                **region,
                "region_id": f"r{i + 1}",
                "source": "local_raster_wall_boundaries",
                "status": "enclosed_region_candidate",
                "confidence": "MEDIUM" if stable else "LOW",
                "corroboration": [
                    "thick_wall_boundaries",
                    "bounded_free_raster_region",
                    "opening_gap_repair",
                ],
                "stable_across_gap_scales": stable,
            }
        )
    counts = [len(rs) for rs, _, _ in variants]
    # Door closures and missed thin partitions prevent a justified exact count.
    return {
        "source": "local_raster_wall_boundaries",
        "regions": region_list,
        "count": None,
        "count_status": "uncertain",
        "multiple_spaces": sum(r["stable_across_gap_scales"] for r in region_list) > 1,
        "stable_region_count": sum(r["stable_across_gap_scales"] for r in region_list),
        "candidate_count_range": [min(counts), max(counts)],
        "gap_scale_counts": counts,
        "opening_repair_fraction": fraction,
        "limitations": [
            "door/window gaps are repaired conservatively",
            "thin/curved partitions or open zones may be unresolved",
        ],
    }, labels


def _level_supports(box, centre, other, per_level, exterior):
    """Does level `other` corroborate this region, or is it uninformative?

    Corroboration is the historical IoU match. The W3R addition: when the
    region's centre at `other` lies in the EXTERIOR free space, that level
    merged the room with the background — its boundary was not closed at that
    threshold — so the level says nothing about the room instead of
    contradicting it. A level that instead shows a DIFFERENT bounded room
    there is a genuine subdivision and still contradicts.
    """
    if any(_iou(box, region["bbox_pixels"]) > 0.65 for region in per_level[other]):
        return True
    mask = exterior[other]
    x = min(max(int(centre[0]), 0), mask.shape[1] - 1)
    y = min(max(int(centre[1]), 0), mask.shape[0] - 1)
    return bool(mask[y, x])


def _enclosure_consensus(cv2, gray, plan_box, furniture_candidates):
    """Baseline dark-mask regions plus level-corroborated extra regions.

    The dark mask (`ENCLOSURE_WALL_LEVELS[0]`) is unchanged and remains the
    baseline: its regions keep their order, ids, labels and gap-scale stability
    exactly as before. Extra regions are admitted only from the higher levels
    and only when every one of these holds:

    - they are not already covered by a baseline region,
    - they are stable across the existing gap-repair scales,
    - no other higher level contradicts them (cross-level corroboration, so one
      level's texture cannot create a room); a level at which the room merged
      with the drawing's exterior is uninformative, not a contradiction,
    - they are a substantial share of the plan footprint,
    - they do not coincide with a furniture symbol candidate.

    Extra regions deliberately carry no connected-component `label`, so the
    furniture-to-region binding in `emit` stays limited to the baseline regions
    and a level-admitted region can never attract a furniture item.
    """
    baseline, labels = _enclosures(
        cv2,
        _walls(cv2, (gray < ENCLOSURE_WALL_LEVELS[0]).astype(np.uint8), plan_box, True),
        plan_box,
    )
    higher_levels = ENCLOSURE_WALL_LEVELS[1:]
    per_level = {}
    exterior = {}
    for level in higher_levels:
        walls = _walls(cv2, (gray < level).astype(np.uint8), plan_box, True)
        per_level[level] = _enclosures(cv2, walls, plan_box)[0]["regions"]
        exterior[level] = _exterior_free_mask(cv2, walls, plan_box)
    width, height = plan_box[2] - plan_box[0], plan_box[3] - plan_box[1]
    minimum_area = width * height * ENCLOSURE_LEVEL_MIN_AREA_FRACTION
    baseline_boxes = [r["bbox_pixels"] for r in baseline["regions"]]
    candidates = []
    for level in higher_levels:
        others = [o for o in higher_levels if o != level]
        for region in per_level[level]:
            box = region["bbox_pixels"]
            if any(_iou(box, other) > 0.65 for other in baseline_boxes):
                continue
            if not region["stable_across_gap_scales"]:
                continue
            centre = (
                (box[0] + box[2]) / 2.0,
                (box[1] + box[3]) / 2.0,
            )
            if not all(
                _level_supports(box, centre, other, per_level, exterior)
                for other in others
            ):
                continue
            if region["pixel_area"] < minimum_area:
                continue
            if any(
                _iou(box, item["bbox_pixels"]) > 0.5 for item in furniture_candidates
            ):
                continue
            candidates.append((level, region))
    admitted = []
    for level, region in sorted(
        candidates, key=lambda entry: (entry[1]["bbox_pixels"][1], entry[1]["bbox_pixels"][0])
    ):
        if any(_iou(region["bbox_pixels"], kept[1]["bbox_pixels"]) > 0.65 for kept in admitted):
            continue
        admitted.append((level, region))
    if not admitted:
        return {
            **baseline,
            "regions": [
                {**region, "wall_levels": [ENCLOSURE_WALL_LEVELS[0]]}
                for region in baseline["regions"]
            ],
            "wall_levels": list(ENCLOSURE_WALL_LEVELS),
            "level_admitted_count": 0,
        }, labels
    combined = [
        {**region, "wall_levels": [ENCLOSURE_WALL_LEVELS[0]]}
        for region in baseline["regions"]
    ]
    for level, region in admitted:
        combined.append(
            {
                **{k: v for k, v in region.items() if k != "label"},
                "confidence": "MEDIUM",
                "stable_across_gap_scales": True,
                "corroboration": [
                    "thick_wall_boundaries",
                    "bounded_free_raster_region",
                    "opening_gap_repair",
                    "cross_level_wall_support",
                    "substantial_space",
                ],
                "wall_levels": [
                    lv for lv in higher_levels if lv <= level
                ],
            }
        )
    combined.sort(key=lambda r: (r["bbox_pixels"][1], r["bbox_pixels"][0]))
    for index, region in enumerate(combined):
        region["region_id"] = f"r{index + 1}"
    geometry = {
        **baseline,
        "regions": combined,
        "multiple_spaces": sum(
            r["stable_across_gap_scales"] for r in combined
        ) > 1,
        "stable_region_count": sum(
            r["stable_across_gap_scales"] for r in combined
        ),
        "wall_levels": list(ENCLOSURE_WALL_LEVELS),
        "level_admitted_count": len(admitted),
    }
    return geometry, labels


def _candidates(cv2, gray, box, threshold):
    pw, ph = box[2] - box[0], box[3] - box[1]
    area_scale = pw * ph
    # SCALE NORMALIZATION — the symbol families below describe line-drawing
    # conventions, not absolute pixel sizes. Morphology kernels and the
    # minimum interior-cell size are therefore expressed in plan-relative
    # units: `unit` is 1.0 for the calibrated reference plan box and scales
    # the absolute constants with the drawing. Without this, an upscaled
    # panel (multi-plan sheets) or a differently resolved plan silently
    # loses every symbol because the kernels no longer match the stroke width.
    unit = max(pw, ph) / 380.0
    k3 = max(3, int(round(3 * unit)))
    ink = (gray < threshold).astype(np.uint8)
    walls = _walls(cv2, ink, box)
    symbols = ink.copy()
    symbols[cv2.dilate(walls, np.ones((k3, k3), np.uint8)) > 0] = 0
    contours, tree = cv2.findContours(symbols, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if tree is None:
        return [], walls
    tree = tree[0]
    candidates = []

    def add(kind, bbox, cues):
        if not _inside(bbox, box, 3):
            return
        if any(
            item["class"] == kind and _iou(item["bbox_pixels"], bbox) > 0.65
            for item in candidates
        ):
            return
        candidates.append(
            {
                "class": kind,
                "bbox_pixels": bbox,
                "corroboration": cues,
                "supported_function": FUNCTIONS[kind],
            }
        )

    # Mattress / upholstered seating: enclosed outline + repeated interior
    # cells, with a larger terminal pillow compartment distinguishing beds.
    # A bare rectangle, dashed room annotation, text or a stair row is insufficient.
    for i, contour in enumerate(contours):
        if tree[i, 3] >= 0:
            continue
        bbox = _box(cv2, contour)
        x0, y0, x1, y1 = bbox
        w, h = x1 - x0, y1 - y0
        outer_area = cv2.contourArea(contour)
        if not _inside(bbox, box, 3) or outer_area < area_scale * 0.002:
            continue
        if max(w, h) > max(pw, ph) * 0.32 or min(w, h) < min(pw, ph) * 0.04:
            continue
        holes = _interior_holes(tree, i)
        regular = []
        pillows = []
        for j in holes:
            hb = _box(cv2, contours[j])
            hw, hh = hb[2] - hb[0], hb[3] - hb[1]
            a = cv2.contourArea(contours[j])
            if (
                a >= outer_area * 0.002
                and a <= outer_area * 0.085
                and min(hw, hh) >= k3
                and 0.45 < hw / hh < 2.2
            ):
                regular.append(j)
            if outer_area * 0.13 < a < outer_area * 0.50 and min(hw, hh) > 0.25 * min(
                w, h
            ):
                pillows.append(j)
        # A plain outlined mattress with a separate terminal pillow row is
        # another common convention; neither an empty room nor a desk has it.
        panels = []
        pillow_boxes = []
        for j in holes:
            hb = _box(cv2, contours[j])
            a = cv2.contourArea(contours[j])
            hw, hh = hb[2] - hb[0], hb[3] - hb[1]
            if (
                outer_area * 0.40 < a < outer_area * 0.83
                and min(hw, hh) > min(w, h) * 0.60
            ):
                panels.append(hb)
            if (
                outer_area * 0.04 < a < outer_area * 0.22
                and 0.6 < hw / hh < 2.0
                and min(hw, hh) > min(w, h) * 0.18
            ):
                pillow_boxes.append(hb)
        plain_bed = False
        if 1.25 < max(w, h) / min(w, h) < 2.4 and panels and pillow_boxes:
            for panel in panels:
                for pillow in pillow_boxes:
                    # Disjoint body and pillow compartments on the long axis.
                    separated = (
                        (pillow[3] <= panel[1] + 2 or pillow[1] >= panel[3] - 2)
                        if h > w
                        else (pillow[2] <= panel[0] + 2 or pillow[0] >= panel[2] - 2)
                    )
                    if separated:
                        plain_bed = True
        if plain_bed:
            add(
                "bed",
                bbox,
                [
                    "closed_mattress_outline",
                    "separate_mattress_panel",
                    "terminal_pillow_compartment",
                ],
            )
            continue
        # A second common convention: a closed rectangular outline with one
        # or two pillow rectangles grouped at a terminal end (frequently
        # drawn with a folded-quilt line). No repeated mattress cells and no
        # large interior panel are required. Guarded by aspect, pillow area
        # share, terminal grouping across the bed width, and the absence of
        # the repeated-cell patterns that mark stair treads or floor tiling.
        if (
            1.2 < max(w, h) / min(w, h) < 2.8
            and 1 <= len(pillow_boxes) <= 2
            and len(regular) < 8
            and outer_area >= area_scale * 0.004
        ):
            pillow_area = sum(
                (b[2] - b[0]) * (b[3] - b[1]) for b in pillow_boxes
            )
            if outer_area * 0.06 <= pillow_area <= outer_area * 0.45:
                long_axis = 0 if w >= h else 1
                short_axis = 1 - long_axis
                bed_lo = bbox[long_axis]
                bed_len = float(w if long_axis == 0 else h)
                bed_short = float(h if long_axis == 0 else w)
                rel = [
                    ((b[long_axis] + b[long_axis + 2]) / 2 - bed_lo) / max(1.0, bed_len)
                    for b in pillow_boxes
                ]
                short_span = max(
                    b[short_axis + 2] for b in pillow_boxes
                ) - min(b[short_axis] for b in pillow_boxes)
                terminal = max(rel) <= 0.45 or min(rel) >= 0.55
                if terminal and short_span >= bed_short * 0.40:
                    add(
                        "bed",
                        bbox,
                        [
                            "closed_sleeping_outline",
                            "terminal_pillow_compartment",
                            "no_repeated_cell_texture",
                        ],
                    )
                    continue
        cushion_boxes = []
        for j in holes:
            hb = _box(cv2, contours[j])
            a = cv2.contourArea(contours[j])
            hw, hh = hb[2] - hb[0], hb[3] - hb[1]
            if (
                outer_area * 0.08 < a < outer_area * 0.30
                and 0.65 < hw / hh < 1.7
                and a > hw * hh * 0.65
            ):
                cushion_boxes.append(hb)
        if 1.6 < max(w, h) / min(w, h) < 4.0 and len(cushion_boxes) >= 3:
            centres = np.array(
                [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in cushion_boxes]
            )
            major, minor = (0, 1) if w > h else (1, 0)
            if (
                np.ptp(centres[:, major]) > max(w, h) * 0.35
                and np.ptp(centres[:, minor]) < min(w, h) * 0.15
            ):
                add(
                    "sofa",
                    bbox,
                    [
                        "closed_upholstered_outline",
                        "aligned_square_cushions",
                        "outline_around_cushion_row",
                    ],
                )
                continue
        if len(regular) < 8:
            continue
        centres = np.array(
            [
                (
                    (_box(cv2, contours[j])[0] + _box(cv2, contours[j])[2]) / 2,
                    (_box(cv2, contours[j])[1] + _box(cv2, contours[j])[3]) / 2,
                )
                for j in regular
            ]
        )
        # A two-dimensional repeated pattern is not a set of stair treads.
        if np.ptp(centres[:, 0]) < w * 0.3 or np.ptp(centres[:, 1]) < h * 0.3:
            continue
        if len(regular) >= 25 and pillows and max(w, h) >= pw * 0.12:
            add(
                "bed",
                bbox,
                [
                    "closed_mattress_outline",
                    "repeated_mattress_cells",
                    "terminal_pillow_compartment",
                ],
            )
        elif len(regular) >= 8 and not pillows:
            add(
                "sofa" if max(w, h) / min(w, h) >= 1.4 else "seating",
                bbox,
                [
                    "closed_upholstered_outline",
                    "repeated_cushion_cells",
                    "two_dimensional_cushion_layout",
                ],
            )

    # Sanitary symbol: a compact cistern + oval bowl assembly. This is NOT
    # triggered by the word "toilet" or by a lone circular hole.
    for i, contour in enumerate(contours):
        if tree[i, 3] >= 0:
            continue
        bbox = _box(cv2, contour)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        children = _children(tree, i)
        a = cv2.contourArea(contour)
        if not (
            pw * 0.025 <= min(w, h) <= pw * 0.075
            and 1.35 <= max(w, h) / min(w, h) <= 2.4
            and a > w * h * 0.55
        ):
            continue
        large = [j for j in children if cv2.contourArea(contours[j]) > a * 0.10]
        if len(large) >= 3:
            add(
                "sanitary_fixture",
                bbox,
                ["cistern_and_bowl_assembly", "multiple_nested_fixture_contours"],
            )

    # Kitchen: paired rectangular bowls/drainer in an elongated sink outline,
    # with a surrounding horizontal AND vertical counter run. Sink tokens or
    # a generic rectangle cannot meet this combined rule.
    sinks = []
    for i, contour in enumerate(contours):
        bbox = _box(cv2, contour)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        a = cv2.contourArea(contour)
        children = _children(tree, i)
        if not (
            pw * 0.035 <= min(w, h) <= pw * 0.10
            and 1.6 < max(w, h) / min(w, h) < 3.2
            and a > w * h * 0.35
        ):
            continue
        bowls = []
        for j in children:
            bb = _box(cv2, contours[j])
            ww, hh = bb[2] - bb[0], bb[3] - bb[1]
            aa = cv2.contourArea(contours[j])
            if aa > a * 0.065 and aa < w * h * 0.35 and aa > ww * hh * 0.6:
                bowls.append(j)
        # Some line drawings connect the bowls to the outer rim; sibling
        # contours immediately within the localized sink box count as well.
        if len(bowls) < 2:
            bowls = [
                j
                for j, c in enumerate(contours)
                if j != i
                and _inside(_box(cv2, c), bbox)
                and cv2.contourArea(c) > a * 0.10
                and cv2.contourArea(c) < w * h * 0.35
            ]
        if len(bowls) < 2:
            continue
        root = i
        while tree[root, 3] >= 0:
            root = int(tree[root, 3])
        assembly = _box(cv2, contours[root])
        aw, ah = assembly[2] - assembly[0], assembly[3] - assembly[1]
        if (
            aw > pw * 0.22
            and ah > ph * 0.18
            and aw * ah < area_scale * 0.20
            and _inside(assembly, box, 3)
        ):
            sinks.append(bbox)
            add(
                "kitchen_sink_arrangement",
                bbox,
                ["paired_bowl_drainer_contours", "counter_assembly"],
            )
            add(
                "kitchen_counter",
                assembly,
                [
                    "horizontal_counter_run",
                    "vertical_counter_run",
                    "localized_sink_arrangement",
                ],
            )

    for root, c in enumerate(contours):
        if tree[root, 3] >= 0:
            continue
        assembly = _box(cv2, c)
        aw, ah = assembly[2] - assembly[0], assembly[3] - assembly[1]
        if not (
            aw > pw * 0.22
            and ah > ph * 0.18
            and aw * ah < area_scale * 0.20
            and _inside(assembly, box, 3)
        ):
            continue
        bowls = []
        for j in _children(tree, root):
            bb = _box(cv2, contours[j])
            w, h = bb[2] - bb[0], bb[3] - bb[1]
            a = cv2.contourArea(contours[j])
            if (
                pw * 0.027 <= w <= pw * 0.10
                and ph * 0.019 <= h <= ph * 0.10
                and a > w * h * 0.65
            ):
                bowls.append(bb)
        for a in bowls:
            for b in bowls:
                if a is b:
                    continue
                if abs(a[0] - b[0]) + abs(a[2] - b[2]) > pw * 0.018:
                    continue
                if not 0 <= b[1] - a[3] < ph * 0.025:
                    continue
                bbox = [min(a[0], b[0]), a[1], max(a[2], b[2]), b[3]]
                add(
                    "kitchen_sink_arrangement",
                    bbox,
                    [
                        "paired_rectangular_bowls",
                        "aligned_bowl_rims",
                        "surrounding_counter_runs",
                    ],
                )
                add(
                    "kitchen_counter",
                    assembly,
                    [
                        "horizontal_counter_run",
                        "vertical_counter_run",
                        "localized_sink_arrangement",
                    ],
                )

    # Dining surface: two parallel long surface edges with at least two
    # compact seat symbols aligned beside them. A coffee table alone does
    # not support dining and arbitrary isolated round marks do not make chairs.
    joined = cv2.morphologyEx(
        symbols, cv2.MORPH_CLOSE, np.ones((1, max(7, int(round(7 * unit)))), np.uint8)
    )
    lines = cv2.morphologyEx(
        joined, cv2.MORPH_OPEN, np.ones((1, max(20, int(pw * 0.16))), np.uint8)
    )
    line_contours, _ = cv2.findContours(
        lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    horizontal = []
    for c in line_contours:
        x, y, w, h = cv2.boundingRect(c)
        if h <= k3:
            horizontal.append((x, x + w, y + h / 2))
    compact = []
    for i, c in enumerate(contours):
        if tree[i, 3] >= 0:
            continue
        bb = _box(cv2, c)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        if (
            pw * 0.025 <= w <= pw * 0.075
            and ph * 0.018 <= h <= ph * 0.065
            and 0.65 < w / h < 1.7
            and cv2.contourArea(c) > w * h * 0.025
        ):
            compact.append(bb)
    for a in horizontal:
        for b in horizontal:
            if not pw * 0.025 <= b[2] - a[2] <= pw * 0.075:
                continue
            left, right = max(a[0], b[0]), min(a[1], b[1])
            if right - left < pw * 0.16:
                continue
            seats = [
                bb
                for bb in compact
                if left - pw * 0.035 < (bb[0] + bb[2]) / 2 < right + pw * 0.035
                and 0 < a[2] - bb[3] < pw * 0.075
            ]
            seats.sort(key=lambda bb: bb[0])
            independent = []
            for bb in seats:
                if not any(_iou(bb, other) > 0.25 for other in independent):
                    independent.append(bb)
            if len(independent) < 2:
                continue
            if (
                max(bb[3] for bb in independent) - min(bb[3] for bb in independent)
                > pw * 0.035
            ):
                continue
            bbox = [int(left), int(a[2]) - 1, int(right) + 1, int(b[2]) + 1]
            patch = symbols[
                bbox[1] : bbox[3], max(0, bbox[0] - int(pw * 0.05)) : bbox[2]
            ]
            # Need the return/curved short edge connecting the parallel rails.
            if patch.size == 0 or patch.sum() < (right - left) * 1.6:
                continue
            add(
                "dining_surface",
                bbox,
                [
                    "parallel_surface_edges",
                    "aligned_seat_row",
                    "localized_surface_return",
                ],
            )
            for bb in independent:
                add(
                    "chair",
                    bb,
                    [
                        "compact_seat_outline",
                        "aligned_seat_row",
                        "adjacent_dining_surface",
                    ],
                )
    return candidates, walls


def _furniture_symbol_items(cv2, gray, plan_box):
    """Furniture/fixture symbol evidence only.

    Shared by the full plan analysis and by the native-resolution panel
    transport. Enclosure geometry is still computed because every emitted item
    records the regions it overlaps, but no architectural element work and no
    OCR happens here.
    """
    first, _ = _candidates(cv2, gray, plan_box, 165)
    second, _ = _candidates(cv2, gray, plan_box, 180)
    third, _ = _candidates(cv2, gray, plan_box, 155)
    corroborating = [(c, 180) for c in second] + [(c, 155) for c in third]
    # The light-line passes are pure and are needed as enclosure exclusions, so
    # they are evaluated before the enclosure consensus. A light-line symbol
    # must never be admitted as a room.
    light_first, _ = _candidates(cv2, gray, plan_box, 210)
    light_second, _ = _candidates(cv2, gray, plan_box, 220)
    geometry, labels = _enclosure_consensus(
        cv2,
        gray,
        plan_box,
        first + second + third + light_first + light_second,
    )
    items = []

    def emit(candidate, thresholds):
        bb = candidate["bbox_pixels"]
        x0, y0, x1, y1 = bb
        ys, xs = np.nonzero(gray[y0:y1, x0:x1] < 165)
        region_ids = []
        if len(xs):
            values = labels[ys + y0, xs + x0]
            for r in geometry["regions"]:
                # Level-admitted regions carry no baseline component label and
                # therefore never attract a furniture item.
                if "label" not in r:
                    continue
                fraction = float(np.mean(values == r["label"]))
                if fraction > 0.40:
                    region_ids.append(r["region_id"])
        items.append(
            {
                **candidate,
                "item_id": f"f{len(items) + 1}",
                "name": candidate["class"].replace("_", " "),
                "status": "visible",
                "confidence": "MEDIUM",
                "evidence_type": "fixture"
                if candidate["class"]
                in ("sanitary_fixture", "kitchen_sink_arrangement", "kitchen_counter")
                else "furniture",
                "source": "local_raster_symbol_topology",
                "provider_independent": True,
                # Distinct raster support at two binarization thresholds is
                # additional corroboration, not semantic certainty.
                "corroboration": candidate["corroboration"]
                + ["stable_at_two_thresholds"],
                "thresholds": list(thresholds),
                "region_ids": region_ids,
                "raster_patch_sha256": hashlib.sha256(
                    gray[y0:y1, x0:x1].tobytes()
                ).hexdigest(),
            }
        )

    for candidate in first:
        matches = [
            (c, threshold)
            for c, threshold in corroborating
            if c["class"] == candidate["class"]
            and _iou(c["bbox_pixels"], candidate["bbox_pixels"])
            > (0.30 if candidate["class"] == "chair" else 0.65)
        ]
        if not matches:
            continue
        emit(candidate, (165, matches[0][1]))

    # Light-line pass: the same structural symbol families drawn lighter than
    # the walls (common in rendered furniture layers). A light candidate is
    # accepted only for a structurally specific class, only when it survives
    # both light thresholds, and never when a dark-line item already covers it.
    for candidate in light_first:
        if candidate["class"] not in LIGHT_LINE_CLASSES:
            continue
        if not any(
            c["class"] == candidate["class"]
            and _iou(c["bbox_pixels"], candidate["bbox_pixels"]) > 0.65
            for c in light_second
        ):
            continue
        if any(
            c["class"] == candidate["class"]
            and _iou(c["bbox_pixels"], candidate["bbox_pixels"]) > 0.65
            for c in items
        ):
            continue
        emit(candidate, (210, 220))
    for region in geometry["regions"]:
        region.pop("label", None)
    return items, geometry


def analyze_furniture_symbols(gray, plan_box):
    """Furniture/fixture items for one raster, without enclosure/element work.

    The sheet pipeline analyses an upscaled copy of every panel crop so OCR and
    wall geometry have a usable resolution. That resampling can change light
    symbol strokes enough to lose furniture, so this entry point lets the
    symbol families run against the panel's ORIGINAL raster instead.
    """
    try:
        import cv2
    except ImportError:
        return []
    items, _ = _furniture_symbol_items(cv2, gray, plan_box)
    return items


def analyze_plan_symbols(gray, plan_box, *, tessdata_path=None):
    """Return auditable item-local evidence; never return provider guesses."""
    try:
        import cv2
    except ImportError:
        return {
            "version": VERSION,
            "status": "unavailable",
            "reason": "symbol_backend_unavailable",
            "furniture_evidence": [],
            "enclosure_geometry": {
                "count": None,
                "count_status": "unknown",
                "regions": [],
            },
        }
    items, geometry = _furniture_symbol_items(cv2, gray, plan_box)
    # Architectural elements share the same raster and evidence pipeline.
    # Element-backend failures must not erase validated furniture observations.
    try:
        from core.vision.local_plan_elements_v1 import analyze_plan_elements
        elements = analyze_plan_elements(gray, plan_box, items, geometry, tessdata_path)
    except Exception as exc:
        elements = {"status": "unavailable", "element_evidence": [],
                    "reason": "%s:%s" % (type(exc).__name__, exc)}
    return {
        "version": VERSION,
        "status": "analyzed",
        "furniture_evidence": items,
        "enclosure_geometry": geometry,
        "element_evidence": elements.get("element_evidence", []),
        "element_analysis_status": elements["status"],
        "element_pipeline_version": elements.get("version"),
        "element_reason": elements.get("reason"),
        "limitations": [
            "recognition is limited to supported line-drawing symbol conventions",
            "semantic class confidence is conservative; no physical dimensions inferred",
        ],
    }


def grounded_plan_items(local):
    """Validate the independent evidence contract at every consumer boundary."""
    if not isinstance(local, dict) or local.get("symbol_analysis_status") != "analyzed":
        return []
    size = local.get("image_size") or {}
    width, height = size.get("width"), size.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        return []
    valid = []
    for entry in local.get("furniture_evidence") or []:
        if not isinstance(entry, dict) or entry.get("class") not in FUNCTIONS:
            continue
        box = entry.get("bbox_pixels")
        if (
            not isinstance(box, (list, tuple))
            or len(box) != 4
            or not all(isinstance(v, int) for v in box)
        ):
            continue
        if not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
            continue
        if (
            entry.get("source") != "local_raster_symbol_topology"
            or entry.get("provider_independent") is not True
            or entry.get("status") != "visible"
            or entry.get("confidence") not in ("MEDIUM", "HIGH")
            or len(entry.get("corroboration") or []) < 3
            or len(str(entry.get("raster_patch_sha256") or "")) != 64
        ):
            continue
        valid.append({**entry, "supported_function": FUNCTIONS[entry["class"]]})
    return valid


def filter_symbol_overlapping_labels(gray, labels):
    """A grid/cushion texture is not Persian text, even if OCR fits a lexicon.

    Only repetitive localized cells quarantine the OCR claim; ordinary source
    labels retain the historical OCR matching and multiplicity unchanged.
    """
    try:
        import cv2
    except ImportError:
        return labels, []
    accepted, rejected = [], []
    for label in labels:
        x0, y0, x1, y1 = [round(v) for v in label["bbox_pixels"]]
        patch = (gray[max(0, y0) : y1, max(0, x0) : x1] < 165).astype(np.uint8)
        contours, tree = cv2.findContours(patch, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        cells = []
        if tree is not None:
            for i, c in enumerate(contours):
                x, y, w, h = cv2.boundingRect(c)
                a = cv2.contourArea(c)
                if (
                    tree[0, i, 3] >= 0
                    and 3 <= min(w, h)
                    and 0.45 < w / h < 2.2
                    and a > 3
                    and a < patch.size * 0.20
                ):
                    cells.append((x + w / 2, y + h / 2))
        if len(cells) >= 8 and np.ptp(np.array(cells), axis=0).min() > 3:
            rejected.append(
                dict(
                    label,
                    status="unverified",
                    reason="repetitive_symbol_texture_not_text",
                )
            )
        else:
            accepted.append(label)
    return accepted, rejected
