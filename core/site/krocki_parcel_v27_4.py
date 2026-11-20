"""KROCKI_PARCEL_V27_4 — pick the LOT, and measure it in its own frame.

Two defects made a multi-lot UTM survey unusable:

1. **Wrong shape.** The reader ranked candidates by `area x layer bonus`, so on
   `عمار ذاکری.dxf` it returned the 1280 m² `tirbarq` BLOCK outline instead of
   the 200 m² lot. A lot map has block boundaries, road edges, service lines
   and the lots themselves; "biggest" selects the block every time.

2. **Wrong dimensions.** Width/length came from the axis-aligned bounding box.
   Survey parcels are rotated to the local street grid (here −161.72°), so a
   true 10 x 20 m lot reported as 15.77 x 22.13 m — and the AABB area is not
   the parcel area either.

This module fixes both: it selects a lot using the drawing's own parcel
labels plus shape quality, and measures any ring by its MINIMUM-AREA
RECTANGLE, which is rotation-invariant.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

CONTRACT = "KrockiParcelSelectionV274"
VERSION = "2.7.4"

Point = Tuple[float, float]

#: Layers whose text is a parcel number. Anything else is annotation noise.
PARCEL_LABEL_LAYERS = ("code", "parcel", "lot", "قطعه", "پلاک", "کروکی")

#: Text on these layers is never a parcel number (phones, dimensions, block ids).
NON_PARCEL_LABEL_LAYERS = ("kol kadr", "dim", "dimension", "blok", "block", "text_dim")

#: A buildable lot, in square metres. Used only as a soft preference.
PLAUSIBLE_LOT_MIN_M2 = 30.0
#: Above this a ring is a block, a compound or the drawing frame, not a lot.
PLAUSIBLE_LOT_MAX_M2 = 1500.0

#: HARD floor. A title-block logo or a symbol hatch is 0.1–4 m²; no parcel is.
#: Without this, `اسحاق کمالی4.dwg` returned the 0.43 m² logo rectangle on
#: layer `Cadr` because it carried a label and was perfectly rectangular.
#:
#: Expressed in SQUARE METRES. Raw DXF areas are in the drawing's own units,
#: so callers pass `min_area_raw` after applying `unit_scale_for_span`.
MIN_PARCEL_AREA_M2 = 20.0


def unit_scale_for_span(span_x: float, span_y: float) -> float:
    """Raw-units-to-metres scale for a drawing of this overall span.

    KROCKI_UNITS_V28 — the old rule was `>4500 -> mm, >120 -> cm, else m`,
    which read a 198 m cadastral map as 198 CENTIMETRES and made every area
    filter meaningless. A lot map spans roughly 10–2000 m, so the scale is
    chosen to put the span in that band:

        span > 4500        -> millimetres (a 198 000 mm site is 198 m)
        otherwise          -> metres      (a 198 unit site is 198 m)

    Centimetres are no longer inferred: a cm drawing of a real parcel spans
    < 4500 AND > 120, which is indistinguishable from a metres drawing of the
    same size — and metres is far more common. Callers that know better can
    pass an explicit scale.

    Kept identical to `krocki_cad_reader_v27._normalize_unit_scale_to_meters`;
    any threshold change must be made in both places.
    """

    span = max(abs(span_x), abs(span_y))

    if span > 4500.0:
        return 0.001

    return 1.0


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def _shoelace(points: Sequence[Point]) -> float:
    if len(points) < 3:
        return 0.0
    total = 0.0
    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def convex_hull(points: Sequence[Point]) -> List[Point]:
    """Andrew's monotone chain."""

    pts = sorted(set((round(x, 6), round(y, 6)) for x, y in points))

    if len(pts) <= 2:
        return list(pts)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: List[Point] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper: List[Point] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]


def min_area_rect(points: Sequence[Point]) -> Tuple[float, float, float]:
    """``(short_side, long_side, rotation_deg)`` of the minimum-area rectangle.

    Rotation-invariant: a 10x20 lot drawn at any angle reports 10 x 20. The
    axis-aligned bounding box does not, which is exactly the bug this
    replaces.
    """

    if len(points) < 3:
        return (0.0, 0.0, 0.0)

    hull = convex_hull(points)

    if len(hull) < 3:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        return (round(min(w, h), 2), round(max(w, h), 2), 0.0)

    best_area = None
    best = (0.0, 0.0, 0.0)

    for i in range(len(hull)):

        x1, y1 = hull[i]
        x2, y2 = hull[(i + 1) % len(hull)]

        edge = math.hypot(x2 - x1, y2 - y1)

        if edge <= 0:
            continue

        angle = math.atan2(y2 - y1, x2 - x1)
        cos_a, sin_a = math.cos(-angle), math.sin(-angle)

        rotated = [
            (px * cos_a - py * sin_a, px * sin_a + py * cos_a)
            for px, py in hull
        ]

        xs = [p[0] for p in rotated]
        ys = [p[1] for p in rotated]

        w = max(xs) - min(xs)
        h = max(ys) - min(ys)

        area = w * h

        if best_area is None or area < best_area - 1e-9:

            best_area = area

            best = (w, h, math.degrees(angle))

    width, height, rotation = best

    return (
        round(min(width, height), 2),
        round(max(width, height), 2),
        round(rotation, 2),
    )


def rectangularity(points: Sequence[Point]) -> float:
    """1.0 for a perfect rectangle, 0.0 for a degenerate ring.

    A survey lot is drawn as a rectangle far more often than a block outline
    or a road wedge is, so this separates them without hard-coding layer
    names.
    """

    pts = list(points)

    if len(pts) > 3 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-6:
        pts.pop()

    if len(pts) != 4:
        return 0.0

    worst = 0.0

    for i in range(4):

        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % 4]

        v1 = (p0[0] - p1[0], p0[1] - p1[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])

        norm = (math.hypot(*v1) * math.hypot(*v2)) or 1.0

        cos_angle = (v1[0] * v2[0] + v1[1] * v2[1]) / norm

        angle = math.degrees(math.acos(max(-1.0, min(1.0, cos_angle))))

        worst = max(worst, abs(angle - 90.0))

    edge_score = max(0.0, 1.0 - worst / 45.0)

    e = [
        math.hypot(pts[(i + 1) % 4][0] - pts[i][0], pts[(i + 1) % 4][1] - pts[i][1])
        for i in range(4)
    ]

    if min(e) <= 0:
        return 0.0

    opposite = abs(e[0] - e[2]) / max(e[0], e[2]) + abs(e[1] - e[3]) / max(e[1], e[3])

    opposite_score = max(0.0, 1.0 - opposite)

    return round(0.6 * edge_score + 0.4 * opposite_score, 4)


def _centroid(points: Sequence[Point]) -> Point:
    """Vertex mean. Good enough to test containment for convex-ish rings."""

    n = len(points) or 1

    return (
        sum(p[0] for p in points) / n,
        sum(p[1] for p in points) / n,
    )


def point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    x, y = point
    inside = False
    n = len(polygon)

    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            denom = (y2 - y1) or 1e-12
            if x < (x2 - x1) * (y - y1) / denom + x1:
                inside = not inside

    return inside


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

def _clean_label(raw: Any) -> str:
    """Strip MTEXT formatting: `{\\fArial|b0;2}` -> `2`."""

    text = str(raw or "")

    text = re.sub(r"\\[A-Za-z][^;]*;", "", text)
    text = text.replace("{", "").replace("}", "")

    return text.strip()


def extract_labels(entities: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every TEXT/MTEXT with a usable insertion point."""

    from core.site.krocki_dxf_geometry_v27_1 import _prop, _to_float

    labels: List[Dict[str, Any]] = []

    for entity in entities:

        if entity["type"] not in ("TEXT", "MTEXT"):
            continue

        text = _clean_label(_prop(entity["props"], "1"))

        if not text:
            continue

        x = _to_float(_prop(entity["props"], "10"))
        y = _to_float(_prop(entity["props"], "20"))

        if x is None or y is None:
            continue

        layer = str(_prop(entity["props"], "8") or "").strip()

        labels.append({"text": text, "x": x, "y": y, "layer": layer})

    return labels


def _parcel_number_from_label(label: Dict[str, Any]) -> Optional[str]:
    """A bare integer 1..9999 on a non-noise layer is a parcel number."""

    layer = label["layer"].lower()

    if any(bad in layer for bad in NON_PARCEL_LABEL_LAYERS):
        return None

    text = label["text"].strip()

    if not re.fullmatch(r"\d{1,4}", text):
        return None

    if layer and not any(good in layer for good in PARCEL_LABEL_LAYERS):
        # A bare number on an unlabelled layer is still a candidate: many
        # exports put everything on layer 0.
        pass

    return text


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def select_parcel(
    candidates: Sequence[Tuple[str, List[Point]]],
    labels: Sequence[Dict[str, Any]],
    parcel_number: Optional[str] = None,
    min_area_raw: Optional[float] = None,
    max_area_raw: Optional[float] = None,
) -> Dict[str, Any]:
    """Choose the lot, not the block.

    Ranking, highest first:
      1. an explicit ``parcel_number`` that this ring contains
      2. a ring that contains ANY integer parcel label
      3. shape quality (rectangularity)
      4. a plausible lot area
      5. layer name bonus

    Returns a dict with ``polygon``, ``layer``, ``parcel_number``, ``method``
    and the scores that produced the decision, so the choice is auditable
    rather than magic.
    """

    wanted = str(parcel_number).strip() if parcel_number is not None else None

    # The caller converts MIN_PARCEL_AREA_M2 into the drawing's own units.
    # Defaulting to the raw value would reject every lot in a millimetre
    # drawing (20 mm²) or accept every logo in a metre drawing.
    _min_area = (
        float(min_area_raw)
        if min_area_raw is not None
        else MIN_PARCEL_AREA_M2
    )

    _max_area = (
        float(max_area_raw)
        if max_area_raw is not None
        else PLAUSIBLE_LOT_MAX_M2
    )

    scored: List[Dict[str, Any]] = []

    for layer, points in candidates:

        ring = list(points)

        if len(ring) > 3 and math.hypot(
            ring[0][0] - ring[-1][0], ring[0][1] - ring[-1][1]
        ) < 1e-6:
            ring.pop()

        if len(ring) < 3:
            continue

        area = abs(_shoelace(ring))

        if area <= 1e-3:
            continue

        # A ring this small is a title-block logo, a symbol, or a hatch
        # boundary — never a lot. Rejected outright so no label bonus can
        # promote it.
        if area < _min_area:
            continue

        contained = [
            label
            for label in labels
            if point_in_polygon((label["x"], label["y"]), ring)
        ]

        numbers = []
        for label in contained:
            number = _parcel_number_from_label(label)
            if number:
                numbers.append(number)

        matched = bool(wanted) and wanted in numbers

        # A ring bigger than a lot is a BLOCK outline that happens to contain
        # several parcel numbers. Granting it the label bonus made the block
        # beat every lot on `اسحاق کمالی4.dwg` (26 967 m² vs 166 m²).
        _plausible = _min_area <= area <= _max_area

        score = 0.0

        if matched:
            score += 100000.0

        if numbers and _plausible:
            score += 1000.0

        score += 100.0 * rectangularity(ring)

        if _plausible:
            score += 10.0

        lowered = layer.lower()
        if any(good in lowered for good in PARCEL_LABEL_LAYERS):
            score += 5.0

        # A tiny bias toward smaller rings only among otherwise-equal
        # candidates: a block outline is never preferred over a lot.
        score -= area / 1e6

        scored.append({
            "polygon": ring,
            "layer": layer,
            "area": round(area, 2),
            "parcel_number": (wanted if matched else (numbers[0] if numbers else None)),
            "matched": matched,
            "labels": numbers,
            "score": round(score, 3),
            "rectangularity": rectangularity(ring),
        })

    if not scored:
        return {"polygon": None, "layer": "0", "method": "none"}

    # ==========================================================
    # KROCKI_CONTAINER_V28 — a ring that ENCLOSES other candidate rings is a
    # block outline or the drawing frame, never a lot. This is the structural
    # difference the scores alone could not see: on `اسحاق کمالی4.dwg` the
    # 26 967 m² block and the 4 307 m² UTM frame both out-scored the real
    # 166 m² parcel until containers were penalised.
    # ==========================================================

    centroids = [
        (_centroid(row["polygon"]), row) for row in scored
    ]

    for point, row in centroids:

        contained = sum(
            1
            for other_point, other_row in centroids
            if other_row is not row
            and point_in_polygon(other_point, row["polygon"])
        )

        row["contains"] = contained

        if contained:
            row["score"] = round(row["score"] - 500.0 * contained, 3)

    if wanted:

        matched_rows = [row for row in scored if row["matched"]]

        if matched_rows:
            best = max(matched_rows, key=lambda row: row["score"])
            best["method"] = "parcel_number_label"
            return best

    best = max(scored, key=lambda row: row["score"])

    best["method"] = (
        "labelled_parcel" if best["labels"] else "shape_and_size"
    )

    return best
