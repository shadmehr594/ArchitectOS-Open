"""KROCKI_DXF_GEOMETRY_V27_1 — strict DXF tokenization and parcel extraction.

Why this module exists
----------------------
The v27.0 reader walked the ENTITIES section as a flat list of stripped lines
and looked for polygons only there. Three real surveyor exports broke it:

1. **Geometry inside a BLOCK, referenced by INSERT.** Extremely common in
   surveyor exports. The reader found no polygon and no line, and the upload
   failed with «هیچ پلی‌لاین یا خط مرزی معتبری …».
2. **No entities at all, only HEADER `$EXTMIN`/`$EXTMAX`.** Also common when a
   CAD vendor exports a "drawing frame" file. Same failure.
3. **Disconnected `LINE` segments.** v27.0 fell back to the bounding box of all
   lines, which is correct for a rectangle and WRONG for any L-shaped or
   chamfered parcel — it silently reports the bbox area instead of the parcel.

The reader also paired DXF lines by scanning, so a *value* that happened to
equal a group code (a coordinate of `10` is routine) could mis-pair.

Everything here is pure: pairs in, geometry out. No I/O beyond reading the
file, no CAD libraries.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

CONTRACT = "KrockiDxfGeometryV271"
VERSION = "1.1"

Point = Tuple[float, float]

#: Layers that name the parcel, used only to RANK candidates.
SITE_LAYER_KEYWORDS = (
    "site", "bound", "parcel", "krocki", "lot", "land",
    "پلاک", "زمین", "کروکی", "ملک", "قطعه",
)


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

def _to_float(value: Any) -> Optional[float]:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def tokenize_pairs(raw_lines: Sequence[str]) -> List[Tuple[str, str]]:
    """Pair the file into ``(group_code, value)`` records.

    A DXF is strictly two lines per record. Pairing by INDEX is the only
    correct reading; scanning for a code anywhere in the stream mis-pairs as
    soon as a value equals a code.
    """

    lines = [str(line).rstrip("\r\n") for line in raw_lines]

    pairs: List[Tuple[str, str]] = []

    for i in range(0, len(lines) - 1, 2):

        pairs.append((lines[i].strip(), lines[i + 1].strip()))

    return pairs


def split_sections(pairs: Sequence[Tuple[str, str]]) -> Dict[str, List[Tuple[str, str]]]:
    """Return ``{SECTION_NAME: records}`` for every SECTION … ENDSEC block."""

    sections: Dict[str, List[Tuple[str, str]]] = {}

    name: Optional[str] = None

    buffer: List[Tuple[str, str]] = []

    i = 0

    n = len(pairs)

    while i < n:

        code, value = pairs[i]

        upper = value.strip().upper()

        if code == "0" and upper == "SECTION":

            if i + 1 < n and pairs[i + 1][0] == "2":

                name = pairs[i + 1][1].strip().upper()

                buffer = []

                i += 2

                continue

        if code == "0" and upper == "ENDSEC":

            if name is not None:

                sections.setdefault(name, []).extend(buffer)

            name = None

            buffer = []

            i += 1

            continue

        if name is not None:

            buffer.append((code, value))

        i += 1

    return sections


# ---------------------------------------------------------------------------
# Entity reading
# ---------------------------------------------------------------------------

def _prop(props: Sequence[Tuple[str, str]], code: str) -> Optional[str]:
    for c, v in props:

        if c == code:

            return v

    return None


def _props_all(props: Sequence[Tuple[str, str]], code: str) -> List[str]:
    return [v for c, v in props if c == code]


def collect_entities(records: Sequence[Tuple[str, str]]) -> List[Dict[str, Any]]:
    """Group records into ``{"type": …, "props": [(code, value), …]}``."""

    entities: List[Dict[str, Any]] = []

    current: Optional[Dict[str, Any]] = None

    for code, value in records:

        if code == "0":

            if current is not None:

                entities.append(current)

            current = {"type": value.strip().upper(), "props": []}

        elif current is not None:

            current["props"].append((code, value))

    if current is not None:

        entities.append(current)

    return entities


def collect_blocks(block_records: Sequence[Tuple[str, str]]) -> Dict[str, List[Dict[str, Any]]]:
    """``{block_name: [entities]}`` from the BLOCKS section."""

    blocks: Dict[str, List[Dict[str, Any]]] = {}

    name: Optional[str] = None

    current: List[Dict[str, Any]] = []

    for entity in collect_entities(block_records):

        kind = entity["type"]

        if kind == "BLOCK":

            raw_name = _prop(entity["props"], "2") or _prop(entity["props"], "3") or ""

            name = str(raw_name).strip()

            current = []

        elif kind == "ENDBLK":

            if name:

                blocks[name] = current

            name = None

            current = []

        elif name is not None:

            current.append(entity)

    return blocks


def _transform(points: Sequence[Point], tx: float, ty: float, sx: float, sy: float,
               rotation_deg: float) -> List[Point]:
    """Apply an INSERT transform: scale, then rotate, then translate."""

    import math

    rad = math.radians(rotation_deg or 0.0)

    cos_r, sin_r = math.cos(rad), math.sin(rad)

    out: List[Point] = []

    for x, y in points:

        px, py = x * sx, y * sy

        out.append((px * cos_r - py * sin_r + tx, px * sin_r + py * cos_r + ty))

    return out


def _block_points(entity: Dict[str, Any]) -> List[Point]:
    """Raw points of one entity, used only when transforming a block child."""

    kind = entity["type"]

    props = entity["props"]

    if kind == "LWPOLYLINE":

        xs = [_to_float(v) for v in _props_all(props, "10")]

        ys = [_to_float(v) for v in _props_all(props, "20")]

        return [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]

    if kind == "LINE":

        x1 = _to_float(_prop(props, "10"))

        y1 = _to_float(_prop(props, "20"))

        x2 = _to_float(_prop(props, "11"))

        y2 = _to_float(_prop(props, "21"))

        if None not in (x1, y1, x2, y2):

            return [(x1, y1), (x2, y2)]

    return []


def flatten_entities(records: Sequence[Tuple[str, str]],
                     blocks: Dict[str, List[Dict[str, Any]]],
                     depth: int = 0) -> List[Dict[str, Any]]:
    """ENTITIES with every ``INSERT`` expanded (translate + scale + rotate)."""

    flattened: List[Dict[str, Any]] = []

    pending: List[Tuple[float, float, float, float, float]] = []

    for entity in collect_entities(records):

        kind = entity["type"]

        if kind == "INSERT":

            if depth >= 3:

                continue

            name = str(_prop(entity["props"], "2") or "").strip()

            tx = _to_float(_prop(entity["props"], "10")) or 0.0

            ty = _to_float(_prop(entity["props"], "20")) or 0.0

            sx = _to_float(_prop(entity["props"], "41")) or 1.0

            sy = _to_float(_prop(entity["props"], "42")) or 1.0

            rot = _to_float(_prop(entity["props"], "50")) or 0.0

            children = blocks.get(name) or []

            for child in children:

                moved = dict(child)

                moved["points_override"] = _transform(
                    _block_points(child), tx, ty, sx, sy, rot
                )

                if child["type"] == "POLYLINE":

                    # A block-scoped polyline keeps its VERTEX grouping; the
                    # override carries the transformed vertices.
                    moved["points_override"] = _transform(
                        _polyline_points(children, child), tx, ty, sx, sy, rot
                    )

                flattened.append(moved)

            continue

        if kind in ("SEQEND", "BLOCK", "ENDBLK"):

            continue

        flattened.append(entity)

    return flattened


def _polyline_points(entities: Sequence[Dict[str, Any]],
                     start_entity: Dict[str, Any]) -> List[Point]:
    """Vertices following a POLYLINE until its SEQEND."""

    points: List[Point] = []

    started = False

    for entity in entities:

        if entity is start_entity:

            started = True

            continue

        if not started:

            continue

        if entity["type"] == "SEQEND":

            break

        if entity["type"] != "VERTEX":

            continue

        x = _to_float(_prop(entity["props"], "10"))

        y = _to_float(_prop(entity["props"], "20"))

        if x is not None and y is not None:

            points.append((x, y))

    return points


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def extract_geometry(entities: Sequence[Dict[str, Any]]) -> Tuple[
    List[Tuple[str, List[Point]]], List[Tuple[str, Point, Point]]
]:
    """Return ``(polygons, segments)`` from a flattened entity list."""

    polygons: List[Tuple[str, List[Point]]] = []

    segments: List[Tuple[str, Point, Point]] = []

    i = 0

    n = len(entities)

    while i < n:

        entity = entities[i]

        kind = entity["type"]

        layer = str(_prop(entity["props"], "8") or "0")

        override = entity.get("points_override")

        if kind == "LWPOLYLINE":

            points = override if override is not None else _block_points(entity)

            if len(points) >= 3:

                polygons.append((layer, list(points)))

            i += 1

            continue

        if kind == "POLYLINE":

            points = override if override is not None else _polyline_points(entities, entity)

            if len(points) >= 3:

                polygons.append((layer, list(points)))

            while i < n and entities[i]["type"] not in ("SEQEND",):

                i += 1

            i += 1

            continue

        if kind == "LINE":

            points = override if override is not None else _block_points(entity)

            if len(points) == 2:

                segments.append((layer, points[0], points[1]))

            i += 1

            continue

        i += 1

    return polygons, segments


def read_header_extents(pairs: Sequence[Tuple[str, str]]) -> Optional[Tuple[float, float, float, float]]:
    """``$EXTMIN``/``$EXTMAX`` as ``(minx, miny, maxx, maxy)``, or ``None``."""

    exmin: Optional[Point] = None

    exmax: Optional[Point] = None

    i = 0

    n = len(pairs)

    while i < n:

        code, value = pairs[i]

        if code == "9":

            name = value.strip().upper()

            if name in ("$EXTMIN", "$EXTMAX"):

                x = y = None

                j = i + 1

                while j < n and pairs[j][0] in ("10", "20", "30"):

                    if pairs[j][0] == "10":

                        x = _to_float(pairs[j][1])

                    elif pairs[j][0] == "20":

                        y = _to_float(pairs[j][1])

                    j += 1

                if x is not None and y is not None:

                    if name == "$EXTMIN":

                        exmin = (x, y)

                    else:

                        exmax = (x, y)

                i = j

                continue

        i += 1

    if exmin and exmax and exmax[0] > exmin[0] and exmax[1] > exmin[1]:

        return (exmin[0], exmin[1], exmax[0], exmax[1])

    return None


def _key(point: Point, tol: float) -> Tuple[int, int]:
    return (int(round(point[0] / tol)), int(round(point[1] / tol)))


def stitch_segments(
    segments: Sequence[Tuple[str, Point, Point]],
    tol: float = 1.0,
) -> Optional[List[Point]]:
    """Join disconnected LINE segments into the largest closed loop.

    This is what makes an L-shaped or chamfered parcel come out as its REAL
    polygon instead of its bounding box. Returns ``None`` when no loop closes.
    """

    if not segments:

        return None

    edges: List[Tuple[Tuple[int, int], Tuple[int, int], Point, Point]] = []

    for _layer, p1, p2 in segments:

        k1, k2 = _key(p1, tol), _key(p2, tol)

        if k1 == k2:

            continue

        edges.append((k1, k2, p1, p2))

    adjacency: Dict[Tuple[int, int], List[int]] = {}

    for idx, (k1, k2, _p1, _p2) in enumerate(edges):

        adjacency.setdefault(k1, []).append(idx)

        adjacency.setdefault(k2, []).append(idx)

    used: set = set()

    best: Optional[List[Point]] = None

    best_area = 0.0

    for start_idx in range(len(edges)):

        if start_idx in used:

            continue

        k_start, k_next, p_start, p_next = edges[start_idx]

        loop: List[Point] = [p_start, p_next]

        local_used = {start_idx}

        current_key = k_next

        guard = 0

        while guard < len(edges) + 2:

            guard += 1

            if current_key == k_start:

                break

            next_idx = None

            for candidate in adjacency.get(current_key, []):

                if candidate not in local_used:

                    next_idx = candidate

                    break

            if next_idx is None:

                break

            k1, k2, p1, p2 = edges[next_idx]

            local_used.add(next_idx)

            if _key(p1, tol) == current_key:

                current_key = k2

                loop.append(p2)

            else:

                current_key = k1

                loop.append(p1)

        if current_key == k_start and len(loop) >= 4:

            if loop[0] == loop[-1]:

                loop = loop[:-1]

            area = abs(_shoelace(loop))

            if area > best_area:

                best_area = area

                best = loop

            used |= local_used

    return best


def _shoelace(points: Sequence[Point]) -> float:
    if len(points) < 3:

        return 0.0

    total = 0.0

    for i in range(len(points)):

        x1, y1 = points[i]

        x2, y2 = points[(i + 1) % len(points)]

        total += x1 * y2 - x2 * y1

    return total / 2.0


def choose_polygon(
    candidates: Sequence[Tuple[str, List[Point]]],
) -> Tuple[Optional[List[Point]], str]:
    """Rank candidate polygons: area, weighted by a site-layer bonus."""

    best: Optional[List[Point]] = None

    best_layer = "0"

    best_score = -1.0

    for layer, points in candidates:

        clean = list(points)

        if len(clean) > 3 and _distance(clean[0], clean[-1]) < 1e-3:

            clean.pop()

        if len(clean) < 3:

            continue

        area = abs(_shoelace(clean))

        if area <= 1e-3:

            continue

        lowered = layer.lower()

        bonus = 10.0 if any(k in lowered for k in SITE_LAYER_KEYWORDS) else 1.0

        score = area * bonus

        if score > best_score:

            best_score = score

            best = clean

            best_layer = layer

    return best, best_layer


def _distance(a: Point, b: Point) -> float:
    import math

    return math.hypot(a[0] - b[0], a[1] - b[1])


def extents_polygon(
    extents: Tuple[float, float, float, float],
) -> List[Point]:
    minx, miny, maxx, maxy = extents

    return [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)]


def read_dxf_geometry(
    dxf_path: str,
    parcel_number: Optional[str] = None,
) -> Dict[str, Any]:
    """Read one DXF and return the chosen parcel polygon plus provenance.

    ``parcel_number`` selects a specific lot by the number printed inside it
    ("قطعه 2"). Without it, the lot is chosen by parcel label and shape
    quality rather than by raw area — a lot map's largest ring is the BLOCK
    outline, never the lot.

    Raises ``ValueError`` with a Persian explanation when nothing usable is
    present — the caller turns that into a 422 the user can act on.
    """

    with open(dxf_path, "r", encoding="utf-8", errors="ignore") as handle:

        raw_lines = handle.readlines()

    pairs = tokenize_pairs(raw_lines)

    sections = split_sections(pairs)

    blocks = collect_blocks(sections.get("BLOCKS", []))

    entities = flatten_entities(sections.get("ENTITIES", []), blocks)

    polygons, segments = extract_geometry(entities)

    from core.site.krocki_parcel_v27_4 import (
        extract_labels,
        select_parcel,
        unit_scale_for_span,
        MIN_PARCEL_AREA_M2,
        PLAUSIBLE_LOT_MAX_M2,
    )

    labels = extract_labels(entities)

    # ==========================================================
    # KROCKI_PARCEL_V28 — the minimum-lot floor must be unit-aware.
    #
    # Raw DXF areas are in the drawing's own units, so a 0.43 m² title-block
    # logo measures 435 600 "m²" in a millimetre drawing and sails through an
    # absolute m² filter. The drawing's units cannot be read from its overall
    # span either — a 198 m map trips the `>120 -> centimetres` rule.
    #
    # Two passes instead: pick once to learn the drawing's scale from a real
    # ring, convert the floor with THAT scale, then pick again.
    # ==========================================================

    first_choice = select_parcel(polygons, labels, parcel_number=parcel_number)

    choice = first_choice

    _first_polygon = first_choice.get("polygon")

    if _first_polygon:

        _fx = [p[0] for p in _first_polygon]
        _fy = [p[1] for p in _first_polygon]

        _scale = unit_scale_for_span(max(_fx) - min(_fx), max(_fy) - min(_fy))

        _min_area_raw = MIN_PARCEL_AREA_M2 / (_scale * _scale)

        _max_area_raw = PLAUSIBLE_LOT_MAX_M2 / (_scale * _scale)

        choice = select_parcel(
            polygons,
            labels,
            parcel_number=parcel_number,
            min_area_raw=_min_area_raw,
            max_area_raw=_max_area_raw,
        )

    polygon = choice.get("polygon")

    layer = choice.get("layer") or "0"

    parcel_label = choice.get("parcel_number")

    selection_method = choice.get("method") or "none"

    source = "polygon"

    if polygon is None:

        polygon = stitch_segments(segments)

        layer = segments[0][0] if segments else "0"

        source = "stitched_lines" if polygon is not None else "none"

        selection_method = "stitched_lines" if polygon is not None else "none"

    if polygon is None:

        extents = read_header_extents(pairs)

        if extents is not None:

            polygon = extents_polygon(extents)

            layer = "HEADER_EXTENTS"

            source = "header_extents"

            selection_method = "header_extents"

    if polygon is None:

        raise ValueError(
            "هیچ پلی‌لاین یا خط مرزی معتبری در فایل کروکی یافت نشد. "
            "فایل باید شامل یک پلی‌لاین بسته یا چهار خط پیوسته دور زمین باشد."
        )

    from core.site.krocki_parcel_v27_4 import min_area_rect

    short_side, long_side, rotation = min_area_rect(polygon)

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "polygon": polygon,
        "layer": layer,
        "source": source,
        # KROCKI_PARCEL_V27_4 — the lot's own frame, not the axis-aligned box.
        "dimensions": {
            "width": short_side,
            "length": long_side,
            "rotation_deg": rotation,
        },
        "parcel_number": parcel_label,
        "selection_method": selection_method,
        "label_count": len(labels),
        "polygon_count": len(polygons),
        "segment_count": len(segments),
        "block_count": len(blocks),
        "entity_count": len(entities),
    }
