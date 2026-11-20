"""Offline Persian plan-label OCR and lightweight perimeter opening grounding.

This module is deliberately independent of the multimodal provider.  It reads
the source raster itself, keeps the OCR engine's raw text, and publishes a
separate lexicon-grounded source-label transcription.  Provider output is not
an input to any function in this file.

The implementation is intentionally narrow for the first acceptance slice:
non-interlaced PNG and JPEG, Persian plan labels, localized furniture and
architectural plan symbols. Unsupported formats fail closed and leave the provider
path available as a semantic assistant.
"""

from __future__ import annotations

from core.vision.local_plan_symbols_v1 import analyze_plan_symbols, filter_symbol_overlapping_labels

from collections import deque
from difflib import SequenceMatcher
from pathlib import Path
import re
import struct
import unicodedata
import zlib

import numpy as np


CONTRACT = "LocalPlanReadingV1"
VERSION = "1.3"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


# Source labels are kept distinct even when two labels map to the same space.
# This is a general architectural-plan lexicon, not a per-image answer table.
PLAN_LABEL_LEXICON = (
    ("اتاق خواب", "bedroom"),
    ("آشپزخانه", "kitchen"),
    ("مطبخ", "kitchen"),
    ("حمام", "bathroom"),
    ("سرویس", "wc"),
    ("پذیرایی", "living room"),
    ("نشیمن", "living room"),
    ("تراس", "balcony"),
    ("ایوان", "balcony"),
    ("بالکن", "balcony"),
    ("راهرو", "corridor"),
    ("دالان", "corridor"),
    ("ورودی", "entrance"),
    ("انباری", "storage"),
    ("آبدارخانه", "pantry"),
    ("غذاخوری", "dining"),
)


_CHAR_TRANSLATION = str.maketrans({
    "ك": "ک", "ي": "ی", "ى": "ی", "ۀ": "ه", "ة": "ه",
    "ؤ": "و", "إ": "ا", "أ": "ا", "ٱ": "ا",
})


# ARCHITECTURAL_SEMANTIC_READING_W3 — the label path is language-neutral.
# `PLAN_LABEL_LEXICON` above stays the Persian surface table (unchanged, and it
# still drives the existing Persian acceptance thresholds). This second table
# adds the Latin architectural terms a drawing may carry, so a plan is no longer
# structurally blind to a label simply because it is not written in Persian.
# Only STRUCTURALLY SPECIFIC terms are listed: a bare "AREA" or "ROOM" is not a
# space and is deliberately absent, so it can never name one on its own.
ARCHITECTURAL_LABEL_LEXICON = (
    ("MASTER BEDROOM", "master bedroom"),
    ("BED ROOM", "bedroom"),
    ("BEDROOM", "bedroom"),
    ("LIVING AREA", "living room"),
    ("LIVING ROOM", "living room"),
    ("LIVING", "living room"),
    ("KITCHEN", "kitchen"),
    ("KITCHENETTE", "kitchen"),
    ("DINING AREA", "dining"),
    ("DINING ROOM", "dining"),
    ("DINING", "dining"),
    ("BATHROOM", "bathroom"),
    ("BATH ROOM", "bathroom"),
    ("BATH", "bathroom"),
    ("TOILET", "wc"),
    ("W.C.", "wc"),
    ("W.C", "wc"),
    ("WC", "wc"),
    ("PATIO", "patio"),
    ("COURTYARD", "courtyard"),
    ("LIGHTWELL", "lightwell"),
    ("LIGHT WELL", "lightwell"),
    ("VOID", "void"),
    ("HALL", "hall"),
    ("CORRIDOR", "corridor"),
    ("ENTRANCE", "entrance"),
    ("ENTRY", "entrance"),
    ("BALCONY", "balcony"),
    ("TERRACE", "terrace"),
    ("STORAGE", "storage"),
    ("STORE ROOM", "storage"),
)

# A reading that is nothing but an axis identifier is grid evidence, never a
# room name. Single letters and short bare numbers are excluded outright.
_AXIS_ONLY = re.compile(r"^[A-Za-z]$|^\d{1,2}[.,]?$")


# ==========================================================
# ARCHITECTURAL_SEMANTIC_READING_W3R — A DRAWING GRAPHIC IS NOT TEXT.
#
# A printed room label is a row of SHORT strokes. Wall, hatch, dimension and
# axis geometry is LONG straight strokes; where two of them cross, the OCR
# engine can fit a short Persian word to the junction, and a fuzzy lexicon
# match then turns that junction into a room. Measured on D: a wall junction
# produced `ترس`, which scored 0.857 against `تراس` and became the plan's only
# named space, although its bbox contains no readable text at all.
#
# The matcher therefore requires that a candidate label's source region is not
# a line STRUCTURE: a region whose ink carries a horizontal run spanning half
# its width AND a vertical run spanning half its height at the same time is a
# junction, never printed text. Measured separation on the acceptance images:
# every genuine Persian label on A has at most 0.32 of its width in one run
# (and at most 0.16 when it also has a long vertical run), while every
# junction-derived reading on D has at least 0.58 in both directions.
# ==========================================================
LABEL_TEXT_INK_LEVEL = 190
LABEL_GRAPHIC_RUN_FRACTION = 0.5
LABEL_GRAPHIC_MIN_WIDTH = 12
LABEL_GRAPHIC_MIN_HEIGHT = 8


def _longest_run(mask):
    """Longest True run over every line of a 2-D boolean mask."""

    best = 0
    for line in mask:
        padded = np.pad(line.astype(np.int8), (1, 1))
        changes = np.flatnonzero(np.diff(padded))
        for start, end in zip(changes[0::2], changes[1::2]):
            if end - start > best:
                best = end - start
    return best


def _drawing_line_structure(gray, box):
    """True when `box` is dominated by a drawing junction rather than text.

    Rejection-only: it can never admit a reading, so it cannot invent a label.
    """

    if gray is None:
        return False
    image_height, image_width = gray.shape
    x0, y0, x1, y1 = (int(round(value)) for value in box)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(image_width, x1), min(image_height, y1)
    if x1 - x0 < LABEL_GRAPHIC_MIN_WIDTH or y1 - y0 < LABEL_GRAPHIC_MIN_HEIGHT:
        return False
    ink = gray[y0:y1, x0:x1] < LABEL_TEXT_INK_LEVEL
    if not ink.any():
        return False
    horizontal = _longest_run(ink) / float(x1 - x0)
    vertical = _longest_run(ink.T) / float(y1 - y0)
    return bool(
        horizontal >= LABEL_GRAPHIC_RUN_FRACTION
        and vertical >= LABEL_GRAPHIC_RUN_FRACTION
    )



def _script_of(text):
    """The dominant writing system of a normalised reading."""
    persian = _persian_count(text)
    latin = sum(1 for ch in text if "A" <= ch.upper() <= "Z")
    if persian >= 2 and persian >= latin:
        return "persian"
    if latin >= 2:
        return "latin"
    return "other"


def _windowed_match(compact, term):
    """Best similarity between `term` and any window of `compact`.

    The window is never SHORTER than the term: a short stray fragment such as
    "all" inside "wall" must not score against "HALL". The window is bounded
    above to the term length plus a small slack, so a long unreadable run
    cannot score highly by containing the letters somewhere. Both directions
    are tried because OCR may reverse a short label.
    """
    compact = compact.upper()
    target = re.sub(r"[^A-Z0-9]", "", term.upper())
    if not compact or not target or len(compact) < len(target):
        return 0.0
    best = 0.0
    for source in (compact, compact[::-1]):
        low = len(target)
        high = min(len(source), len(target) + 3)
        for length in range(low, high + 1):
            for start in range(0, max(1, len(source) - length + 1)):
                candidate = source[start:start + length]
                if not candidate:
                    continue
                best = max(
                    best, SequenceMatcher(None, candidate, target).ratio()
                )
    return best


# Localized Latin-label passes. The historical passes ask the engine in
# `fas+eng` together, which biases its glyph decisions on short Latin labels;
# a plan whose room labels are Latin therefore reads as 1-3 character
# fragments. These passes ask the SAME localized tight crops in `eng` alone, on
# the lighter band small Latin labels are drawn in. Bounded to those crops.
ARCHITECTURAL_LATIN_SCALE = 8
ARCHITECTURAL_LATIN_THRESHOLDS = (210, 235)

# A Latin reading is accepted as an architectural label only when the matched
# term occupies essentially the whole reading, so a stray fragment inside a
# longer unreadable run cannot name a space.
ARCHITECTURAL_LABEL_MIN_SCORE = 0.84
ARCHITECTURAL_LABEL_MAX_SLACK = 5



def _normalise_text(value):
    value = unicodedata.normalize("NFKC", str(value or ""))
    value = value.translate(_CHAR_TRANSLATION)
    value = "".join(
        ch for ch in value
        if unicodedata.category(ch) not in ("Mn", "Cf")
    )
    value = re.sub(r"[^\u0600-\u06ffA-Za-z0-9]+", " ", value)
    return " ".join(value.split())


def _persian_count(value):
    return sum("\u0600" <= ch <= "\u06ff" for ch in value)


def _similarity(raw, target):
    """Best OCR-to-label similarity, tolerant of bidi reversal and clutter."""

    raw_norm = _normalise_text(raw)
    target_norm = _normalise_text(target)
    raw_compact = raw_norm.replace(" ", "")
    target_compact = target_norm.replace(" ", "")

    if not raw_compact or not target_compact:
        return 0.0

    variants = {raw_compact, raw_compact[::-1]}
    words = raw_norm.split()

    for start in range(len(words)):
        for end in range(start + 1, min(len(words), start + 3) + 1):
            phrase = "".join(words[start:end])
            variants.add(phrase)
            variants.add(phrase[::-1])

    # A Tesseract line often includes a wall mark or dimension beside the
    # actual label.  Compare bounded substrings, but never fewer than half of
    # the target's Persian characters.
    for source in (raw_compact, raw_compact[::-1]):
        for length in range(max(2, len(target_compact) - 2), len(target_compact) + 3):
            for start in range(0, max(1, len(source) - length + 1)):
                variants.add(source[start:start + length])

    scores = [
        SequenceMatcher(None, value, target_compact).ratio()
        for value in variants
        if value
    ]

    score = max(scores, default=0.0)

    # Compound Persian labels may be split by bidi segmentation.  Requiring
    # both the distinctive خواب stem and an اتاق-like fragment is much more
    # specific than generic edit distance and prevents the two words from
    # being mapped independently to unrelated short labels.
    if target_norm == "اتاق خواب":
        has_sleep_stem = "خوا" in raw_compact or "اوخ" in raw_compact
        has_room_fragment = any(
            fragment in raw_compact
            for fragment in ("اتاق", "اتا", "قاتا", "یاتا", "تا")
        )
        if has_sleep_stem and has_room_fragment:
            score = max(score, 0.88)

    return score


def _reject_graphic_labels(gray, labels):
    """Split labels into (grounded, graphic) by the line-structure test.

    Rejection only: a label is moved out when its source region is a drawing
    junction, never added.
    """

    grounded, graphic = [], []
    for label in labels:
        if _drawing_line_structure(gray, label["bbox_pixels"]):
            graphic.append(label)
        else:
            grounded.append(label)
    return grounded, graphic


def _unfilter(filter_type, line, previous, bpp, stride):
    if filter_type == 0:
        return line
    if filter_type == 1:
        out = line.copy()
        for index in range(bpp, stride):
            out[index] = (out[index] + out[index - bpp]) & 0xFF
        return out
    if filter_type == 2:
        return (line + previous.astype(np.int16)) & 0xFF
    if filter_type == 3:
        out = line.copy()
        for index in range(stride):
            left = int(out[index - bpp]) if index >= bpp else 0
            out[index] = (
                out[index] + ((left + int(previous[index])) >> 1)
            ) & 0xFF
        return out
    if filter_type == 4:
        out = line.copy()
        prev = previous.astype(np.int16)
        for index in range(stride):
            left = int(out[index - bpp]) if index >= bpp else 0
            above = int(prev[index])
            upper_left = int(prev[index - bpp]) if index >= bpp else 0
            estimate = left + above - upper_left
            distances = (
                abs(estimate - left),
                abs(estimate - above),
                abs(estimate - upper_left),
            )
            predictor = (left, above, upper_left)[distances.index(min(distances))]
            out[index] = (out[index] + predictor) & 0xFF
        return out
    raise ValueError("png_filter_unsupported")


def _read_png(path):
    """Decode an 8/16-bit, non-interlaced PNG without Pillow/OpenCV."""

    with open(path, "rb") as handle:
        data = handle.read()

    if data[:8] != PNG_SIGNATURE:
        raise ValueError("local_plan_reader_png_only")

    position = 8
    header = None
    palette = None
    compressed = []

    while position + 8 <= len(data):
        length = struct.unpack(">I", data[position:position + 4])[0]
        chunk_type = data[position + 4:position + 8]
        body = data[position + 8:position + 8 + length]
        position += 12 + length

        if chunk_type == b"IHDR":
            header = struct.unpack(">IIBBBBB", body[:13])
        elif chunk_type == b"PLTE":
            palette = np.frombuffer(body, dtype=np.uint8).reshape(-1, 3)
        elif chunk_type == b"IDAT":
            compressed.append(body)
        elif chunk_type == b"IEND":
            break

    if header is None:
        raise ValueError("png_missing_ihdr")

    width, height, bit_depth, colour_type, compression, filtering, interlace = header
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(colour_type)

    if interlace or compression or filtering or channels is None:
        raise ValueError("png_layout_unsupported")
    if bit_depth not in (8, 16):
        raise ValueError("png_bit_depth_unsupported")

    sample_bytes = bit_depth // 8
    bytes_per_pixel = channels * sample_bytes
    stride = width * bytes_per_pixel
    raw = zlib.decompress(b"".join(compressed))

    if len(raw) < (stride + 1) * height:
        raise ValueError("png_truncated")

    output = np.zeros((height, stride), dtype=np.uint8)
    previous = np.zeros(stride, dtype=np.uint8)
    offset = 0

    for row in range(height):
        filter_type = raw[offset]
        offset += 1
        line = np.frombuffer(
            raw[offset:offset + stride], dtype=np.uint8
        ).astype(np.int16)
        offset += stride
        rebuilt = _unfilter(
            filter_type, line, previous, bytes_per_pixel, stride
        )
        output[row] = rebuilt.astype(np.uint8)
        previous = output[row]

    array = output.reshape(height, width, bytes_per_pixel)

    if bit_depth == 16:
        array = array.reshape(height, width, channels, 2)[:, :, :, 0]
    if colour_type == 3:
        if palette is None:
            raise ValueError("png_palette_missing")
        array = palette[array.reshape(height, width)]

    if array.shape[2] == 1:
        return array[:, :, 0]

    # Alpha is deliberately ignored: uploaded architectural sheets are
    # flattened against their visible RGB values before thresholding.
    return np.rint(array[:, :, :3].mean(axis=2)).astype(np.uint8)


def _read_raster(path):
    """Keep the historical PNG decoder; decode JPEG to the same uint8 gray."""

    with open(path, "rb") as handle:
        signature = handle.read(8)
    if signature == PNG_SIGNATURE:
        return _read_png(path)
    if signature[:3] == b"\xff\xd8\xff":
        from PIL import Image

        with Image.open(path) as image:
            if image.format != "JPEG":
                raise ValueError("raster_format_unsupported")
            rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
            return np.rint(rgb.mean(axis=2)).astype(np.uint8)
    raise ValueError("raster_format_unsupported")


def _long_runs(mask, minimum, axis):
    marked = np.zeros_like(mask, dtype=bool)
    rows = mask if axis == 1 else mask.T
    target = marked if axis == 1 else marked.T

    for row_index, row in enumerate(rows):
        padded = np.pad(row.astype(np.int8), (1, 1))
        changes = np.flatnonzero(np.diff(padded))
        for start, end in zip(changes[0::2], changes[1::2]):
            if end - start >= minimum:
                target[row_index, start:end] = True

    return marked


def _dilate(mask, radius_x, radius_y):
    height, width = mask.shape
    padded = np.pad(mask, ((radius_y, radius_y), (radius_x, radius_x)))
    result = np.zeros_like(mask, dtype=bool)

    for delta_y in range(2 * radius_y + 1):
        for delta_x in range(2 * radius_x + 1):
            result |= padded[
                delta_y:delta_y + height,
                delta_x:delta_x + width,
            ]

    return result


def _components(mask):
    seen = np.zeros_like(mask, dtype=bool)
    height, width = mask.shape

    for source_y, source_x in np.argwhere(mask):
        source_y = int(source_y)
        source_x = int(source_x)
        if seen[source_y, source_x]:
            continue

        queue = deque([(source_y, source_x)])
        seen[source_y, source_x] = True
        xs = []
        ys = []

        while queue:
            y, x = queue.popleft()
            xs.append(x)
            ys.append(y)
            for nearby_y in range(max(0, y - 1), min(height, y + 2)):
                for nearby_x in range(max(0, x - 1), min(width, x + 2)):
                    if mask[nearby_y, nearby_x] and not seen[nearby_y, nearby_x]:
                        seen[nearby_y, nearby_x] = True
                        queue.append((nearby_y, nearby_x))

        yield (
            min(xs), min(ys), max(xs) + 1, max(ys) + 1, len(xs)
        )


def _plan_bbox(gray):
    height, width = gray.shape
    ink = gray < 165
    minimum_h = max(16, int(width * 0.055))
    minimum_v = max(16, int(height * 0.04))
    lines = (
        _long_runs(ink, minimum_h, 1)
        | _long_runs(ink, minimum_v, 0)
    )
    joined = _dilate(lines, 2, 2)

    candidates = []
    for x0, y0, x1, y1, area in _components(joined):
        box_width = x1 - x0
        box_height = y1 - y0
        if box_width < width * 0.35 or box_height < height * 0.25:
            continue
        if box_width > width * 0.98 and box_height > height * 0.95:
            continue
        candidates.append((area * box_width * box_height, (x0, y0, x1, y1)))

    if candidates:
        component_box = max(candidates, key=lambda item: item[0])[1]
        return _main_enclosure_bbox(gray, component_box)

    ys, xs = np.nonzero(ink)
    if not len(xs):
        raise ValueError("empty_raster")
    return int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)


def _main_enclosure_bbox(gray, component_box):
    """Trim site/porch lines below the dominant closed plan enclosure."""

    image_height, image_width = gray.shape
    x0, y0, x1, y1 = component_box
    ink = gray < 165
    side_width = max(5, min(12, int((x1 - x0) * 0.045)))
    side_presence = (
        ink[y0:y1, x0:min(x1, x0 + side_width)].sum(axis=1)
        + ink[y0:y1, max(x0, x1 - side_width):x1].sum(axis=1)
    ) >= 2

    # Windows may interrupt an outer wall briefly; a site/platform line sits
    # after a substantially larger blank gap and must not extend the plan box.
    side_presence = _close_small_gaps(side_presence, maximum_gap=22)
    runs = list(_runs(side_presence))
    if runs:
        start, end = max(runs, key=lambda run: run[1] - run[0])
        if end - start >= (y1 - y0) * 0.45:
            y0 = max(0, y0 + start - 2)
            y1 = min(image_height, y0 + (end - start) + 4)

    component_x0, component_x1 = component_box[0], component_box[2]
    column_counts = ink[y0:y1, component_x0:component_x1].sum(axis=0)
    strong = column_counts >= max(12, int((y1 - y0) * 0.58))
    strong_runs = [
        (start + component_x0, end + component_x0)
        for start, end in _runs(strong)
        if end - start <= 16
    ]
    if len(strong_runs) >= 2:
        left = strong_runs[0]
        right = strong_runs[-1]
        if right[0] - left[1] >= (component_box[2] - component_box[0]) * 0.55:
            x0 = max(0, left[0] - 2)
            x1 = min(image_width, right[1] + 2)

    return int(x0), int(y0), int(x1), int(y1)


def _clip_box(box, width, height):
    x0, y0, x1, y1 = box
    return (
        max(0, min(width - 1, int(round(x0)))),
        max(0, min(height - 1, int(round(y0)))),
        max(1, min(width, int(round(x1)))),
        max(1, min(height, int(round(y1)))),
    )


def _candidate_crops(gray, plan_box):
    """Return de-duplicated tight, context and overlapping plan crops."""

    height, width = gray.shape
    px0, py0, px1, py1 = plan_box
    plan_width = px1 - px0
    plan_height = py1 - py0
    search_box = _clip_box(
        (
            px0 - plan_width * 0.05,
            py0 - plan_height * 0.05,
            px1 + plan_width * 0.05,
            py1 + plan_height * 0.27,
        ),
        width,
        height,
    )
    sx0, sy0, sx1, sy1 = search_box
    candidates = []

    # Text components survive after long wall strokes are removed.  Three
    # thresholds protect faint antialiasing without adding another library.
    for threshold in (160, 205, 235):
        ink = gray < threshold
        lines = (
            _long_runs(ink, max(14, int(plan_width * 0.055)), 1)
            | _long_runs(ink, max(14, int(plan_height * 0.055)), 0)
        )
        residual = ink & ~_dilate(lines, 2, 2)
        joined = _dilate(residual, 4, 1)

        for x0, y0, x1, y1, area in _components(joined):
            box_width = x1 - x0
            box_height = y1 - y0
            if not (5 <= box_width <= plan_width * 0.48):
                continue
            if not (3 <= box_height <= max(34, plan_height * 0.13)):
                continue
            if not (5 <= area <= plan_width * plan_height * 0.08):
                continue
            if x1 < sx0 or x0 > sx1 or y1 < sy0 or y0 > sy1:
                continue

            tight = _clip_box((x0 - 10, y0 - 7, x1 + 10, y1 + 7), width, height)
            candidates.append(("component_t%d" % threshold, tight, "tight"))

            centre_x = (x0 + x1) / 2.0
            centre_y = (y0 + y1) / 2.0
            context_width = max(86, min(118, int(plan_width * 0.40)))
            context_height = max(48, min(66, int(plan_height * 0.22)))
            context = _clip_box(
                (
                    centre_x - context_width / 2,
                    centre_y - context_height / 2,
                    centre_x + context_width / 2,
                    centre_y + context_height / 2,
                ),
                width,
                height,
            )
            candidates.append(("context_t%d" % threshold, context, "context"))

            micro_width = max(70, min(84, int(plan_width * 0.29)))
            micro_height = max(44, min(54, int(plan_height * 0.19)))
            micro = _clip_box(
                (
                    centre_x - micro_width / 2,
                    centre_y - micro_height / 2,
                    centre_x + micro_width / 2,
                    centre_y + micro_height / 2,
                ),
                width,
                height,
            )
            candidates.append(("micro_t%d" % threshold, micro, "micro"))

    # Overlapping tiles recover labels split into multiple residual components.
    body_x0, body_y0, body_x1, body_y1 = search_box
    body_width = body_x1 - body_x0
    body_height = body_y1 - body_y0
    x_windows = ((0.00, 0.46), (0.24, 0.76), (0.54, 1.00))
    y_windows = ((0.00, 0.34), (0.18, 0.55), (0.38, 0.76), (0.62, 1.00))

    for row, (y_start, y_end) in enumerate(y_windows):
        for column, (x_start, x_end) in enumerate(x_windows):
            candidates.append((
                "tile_%d_%d" % (row, column),
                _clip_box((
                    body_x0 + x_start * body_width,
                    body_y0 + y_start * body_height,
                    body_x0 + x_end * body_width,
                    body_y0 + y_end * body_height,
                ), width, height),
                "tile",
            ))

    # De-duplicate dense component/context proposals by box quantisation while
    # retaining different threshold families as independent OCR evidence.
    output = []
    seen = set()
    for pass_name, box, kind in candidates:
        key = (
            kind,
            pass_name,
            *(int(round(value / 4.0)) for value in box),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append((pass_name, box, kind))

    # Persian multi-word labels are often split into two residual components.
    # Merge only same-baseline, nearby component crops; this reconstructs the
    # label line without using any target word or image-specific coordinate.
    line_context = []
    tight_source = [item for item in output if item[2] == "tight"]
    for index, left in enumerate(tight_source):
        left_name, left_box, _ = left
        for right_name, right_box, _ in tight_source[index + 1:]:
            if left_name != right_name:
                continue
            left_y = (left_box[1] + left_box[3]) / 2.0
            right_y = (right_box[1] + right_box[3]) / 2.0
            if abs(left_y - right_y) > 13:
                continue
            horizontal_gap = max(
                left_box[0], right_box[0]
            ) - min(left_box[2], right_box[2])
            if horizontal_gap > 24:
                continue
            union = _clip_box((
                min(left_box[0], right_box[0]) - 8,
                min(left_box[1], right_box[1]) - 15,
                max(left_box[2], right_box[2]) + 8,
                max(left_box[3], right_box[3]) + 15,
            ), width, height)
            if union[2] - union[0] > max(120, plan_width * 0.46):
                continue
            line_context.append((
                left_name.replace("component", "linecontext"),
                union,
                "line_context",
            ))

    line_seen = set()
    compact_line_context = []
    for item in line_context:
        key = (item[0], *(int(round(value / 5.0)) for value in item[1]))
        if key not in line_seen:
            line_seen.add(key)
            compact_line_context.append(item)

    # Bound runtime on highly annotated sheets.  Spatial order keeps coverage
    # deterministic instead of choosing candidates by OCR result.
    def threshold_sample(kind, per_threshold):
        items = [item for item in output if item[2] == kind]
        sampled = []
        for threshold in (160, 205, 235):
            sampled.extend([
                item for item in items
                if "t%d" % threshold in item[0]
            ][:per_threshold])
        return sampled

    tight = threshold_sample("tight", 40)
    context = threshold_sample("context", 20)
    micro = threshold_sample("micro", 20)
    line_context = []
    for threshold in (160, 205, 235):
        line_context.extend([
            item for item in compact_line_context
            if "t%d" % threshold in item[0]
        ][:24])
    tiles = [item for item in output if item[2] == "tile"]
    return tight + context + micro + line_context + tiles


def _remove_plan_lines(gray, plan_box, minimum_scale=0.055):
    plan_width = plan_box[2] - plan_box[0]
    plan_height = plan_box[3] - plan_box[1]
    ink = gray < 205
    lines = (
        _long_runs(ink, max(14, int(plan_width * minimum_scale)), 1)
        | _long_runs(ink, max(14, int(plan_height * minimum_scale)), 0)
    )
    return np.where(ink & ~_dilate(lines, 2, 2), 0, 255).astype(np.uint8)


def _ocr_crop(api, source, box, *, scale, threshold, psm, pass_name):
    from tesserocr import RIL

    x0, y0, x1, y1 = box
    crop = source[y0:y1, x0:x1]
    if not crop.size:
        return []

    enlarged = np.repeat(np.repeat(crop, scale, axis=0), scale, axis=1)
    binary = np.where(enlarged < threshold, 0, 255).astype(np.uint8)
    image_height, image_width = binary.shape

    api.SetPageSegMode(psm)
    api.SetImageBytes(
        binary.tobytes(), image_width, image_height, 1, image_width
    )
    # SetImageBytes has no embedded DPI.  Tesseract's file loader uses its
    # conservative fallback (70 DPI) for these plan snippets; pinning the same
    # value prevents resolution state leaking between reused API calls.
    api.SetSourceResolution(70)
    api.Recognize()
    full_text = " ".join((api.GetUTF8Text() or "").split())
    full_confidence = float(api.MeanTextConf())
    iterator = api.GetIterator()
    readings = []

    # For Persian, Tesseract's logical full-page text can join bidi fragments
    # which its TEXTLINE iterator exposes separately.  Keep both records; the
    # full record is bounded to small crops so its location remains useful.
    if full_text and (x1 - x0) <= 140 and (y1 - y0) <= 100:
        readings.append({
            "raw_text": full_text,
            "ocr_confidence": round(
                max(0.0, min(100.0, full_confidence)), 1
            ),
            "bbox_pixels": [float(x0), float(y0), float(x1), float(y1)],
            "pass": pass_name + "_full",
        })

    while iterator:
        try:
            raw_text = (iterator.GetUTF8Text(RIL.TEXTLINE) or "").strip()
            local_box = iterator.BoundingBox(RIL.TEXTLINE)
            confidence = float(iterator.Confidence(RIL.TEXTLINE))
        except RuntimeError:
            raw_text, local_box, confidence = "", None, 0.0

        if raw_text and local_box:
            local_x0, local_y0, local_x1, local_y1 = local_box
            readings.append({
                "raw_text": " ".join(raw_text.split()),
                "ocr_confidence": round(max(0.0, min(100.0, confidence)), 1),
                "bbox_pixels": [
                    round(x0 + local_x0 / scale, 1),
                    round(y0 + local_y0 / scale, 1),
                    round(x0 + local_x1 / scale, 1),
                    round(y0 + local_y1 / scale, 1),
                ],
                "pass": pass_name,
            })

        if not iterator.Next(RIL.TEXTLINE):
            break

    return readings


def _ocr_readings(gray, plan_box, tessdata_path):
    try:
        from tesserocr import OEM, PSM, PyTessBaseAPI
    except Exception as exc:
        raise RuntimeError("tesserocr_unavailable") from exc

    tessdata_path = str(tessdata_path)
    if not Path(tessdata_path, "fas.traineddata").is_file():
        raise RuntimeError("fas_traineddata_missing")

    cleaned_16 = _remove_plan_lines(gray, plan_box, 0.050)
    cleaned_22 = _remove_plan_lines(gray, plan_box, 0.075)
    readings = []

    with PyTessBaseAPI(
        path=tessdata_path,
        lang="fas+eng",
        psm=PSM.SPARSE_TEXT,
        oem=OEM.LSTM_ONLY,
    ) as api:
        for pass_name, box, kind in _candidate_crops(gray, plan_box):
            if kind == "tight":
                readings.extend(_ocr_crop(
                    api, gray, box,
                    scale=8, threshold=225, psm=PSM.SINGLE_LINE,
                    pass_name=pass_name + "_line",
                ))
                readings.extend(_ocr_crop(
                    api, gray, box,
                    scale=8, threshold=190, psm=PSM.SINGLE_LINE,
                    pass_name=pass_name + "_line190",
                ))
                readings.extend(_ocr_crop(
                    api, gray, box,
                    scale=8, threshold=190, psm=PSM.SINGLE_WORD,
                    pass_name=pass_name + "_word",
                ))
                readings.extend(_ocr_crop(
                    api, gray, box,
                    scale=8, threshold=225, psm=PSM.SINGLE_WORD,
                    pass_name=pass_name + "_word225",
                ))
            elif kind == "context":
                readings.extend(_ocr_crop(
                    api, gray, box,
                    scale=8, threshold=225, psm=PSM.SPARSE_TEXT,
                    pass_name=pass_name + "_raw",
                ))
            elif kind in ("micro", "line_context"):
                for threshold in (200, 225):
                    readings.extend(_ocr_crop(
                        api, gray, box,
                        scale=8, threshold=threshold, psm=PSM.SPARSE_TEXT,
                        pass_name=pass_name + "_raw%d" % threshold,
                    ))
            else:
                for cleaned, suffix in ((cleaned_16, "r16"), (cleaned_22, "r22")):
                    readings.extend(_ocr_crop(
                        api, cleaned, box,
                        scale=6, threshold=128, psm=PSM.SPARSE_TEXT,
                        pass_name=pass_name + "_" + suffix,
                    ))

        # One global cleaned pass adds evidence for labels near a tile edge.
        readings.extend(_ocr_crop(
            api, cleaned_16, (0, 0, gray.shape[1], gray.shape[0]),
            scale=6, threshold=128, psm=PSM.SINGLE_BLOCK,
            pass_name="global_cleaned",
        ))

    readings.extend(_architectural_latin_readings(gray, plan_box, tessdata_path))

    return readings


def _architectural_latin_readings(gray, plan_box, tessdata_path):
    """Localized Latin architectural-label passes over the tight crops."""
    try:
        from tesserocr import OEM, PSM, PyTessBaseAPI
    except Exception:
        return []
    readings = []
    try:
        api = PyTessBaseAPI(
            path=str(tessdata_path), lang="eng", psm=PSM.SINGLE_LINE,
            oem=OEM.LSTM_ONLY,
        )
    except Exception:
        return []
    with api:
        for pass_name, box, kind in _candidate_crops(gray, plan_box):
            if kind != "tight":
                continue
            for threshold in ARCHITECTURAL_LATIN_THRESHOLDS:
                for psm, suffix in (
                    (PSM.SINGLE_LINE, "line"),
                    (PSM.SINGLE_WORD, "word"),
                ):
                    readings.extend(_ocr_crop(
                        api, gray, box,
                        scale=ARCHITECTURAL_LATIN_SCALE,
                        threshold=threshold,
                        psm=psm,
                        pass_name="%s_latin%s%d" % (pass_name, suffix, threshold),
                    ))
    return readings


def _architectural_label_matches(readings, plan_box, image_shape):
    """Latin architectural labels, grounded without a language-specific gate.

    The historical matcher dropped every reading with fewer than two Persian
    characters before looking at any lexicon, so a Latin plan could not label a
    space at all. This path is script-neutral: it keeps the readings the
    Persian path does not own, rejects anything that is only an axis
    identifier, and requires a structurally specific architectural term to
    occupy essentially the whole reading.
    """
    candidates = []
    for reading in readings:
        raw = _normalise_text(reading.get("raw_text"))
        if not raw or _persian_count(raw) >= 2:
            continue
        compact = raw.replace(" ", "").upper()
        if len(compact) < 3 or not any("A" <= ch <= "Z" for ch in compact):
            continue
        if _AXIS_ONLY.match(compact):
            continue
        score, term, semantic = 0.0, None, None
        for surface, function in ARCHITECTURAL_LABEL_LEXICON:
            value = _windowed_match(compact, surface)
            if value > score:
                score, term, semantic = value, surface, function
        if term is None or score < ARCHITECTURAL_LABEL_MIN_SCORE:
            continue
        if len(compact) > len(re.sub(r"[^A-Z0-9]", "", term)) + (
            ARCHITECTURAL_LABEL_MAX_SLACK
        ):
            continue
        candidates.append({
            "reading": reading,
            "term": term,
            "semantic_function": semantic,
            "score": score,
            "bbox_pixels": list(reading["bbox_pixels"]),
        })
    candidates.sort(key=lambda item: (item["bbox_pixels"][1], item["bbox_pixels"][0]))
    clusters = []
    for item in candidates:
        cluster = next(
            (
                entry for entry in clusters
                if entry["term"] == item["term"]
                and _centres_close(entry["representative"], item["reading"], plan_box)
            ),
            None,
        )
        if cluster is None:
            clusters.append({
                "term": item["term"],
                "semantic_function": item["semantic_function"],
                "items": [item],
                "representative": item,
            })
            continue
        cluster["items"].append(item)
        if item["score"] > cluster["representative"]["score"]:
            cluster["representative"] = item
    height, width = image_shape
    accepted = []
    for cluster in clusters:
        best = max(cluster["items"], key=lambda i: i["reading"]["ocr_confidence"])
        score = cluster["representative"]["score"]
        confidence = best["reading"]["ocr_confidence"]
        support = len({i["reading"]["pass"] for i in cluster["items"]})
        if not (
            (score >= 0.96 and confidence >= 20)
            or (score >= 0.88 and confidence >= 35)
            or (score >= 0.84 and confidence >= 25 and support >= 2)
        ):
            continue
        box = cluster["representative"]["bbox_pixels"]
        accepted.append({
            "text": cluster["term"],
            "semantic_function": cluster["semantic_function"],
            "raw_ocr": cluster["representative"]["reading"]["raw_text"],
            "normalized_ocr": _normalise_text(
                cluster["representative"]["reading"]["raw_text"]
            ),
            "script": "latin",
            "matched_term": cluster["term"],
            "bbox_pixels": [round(value, 1) for value in box],
            "bbox_normalized": [
                round(box[0] / width, 4),
                round(box[1] / height, 4),
                round(box[2] / width, 4),
                round(box[3] / height, 4),
            ],
            "confidence": (
                "HIGH" if score >= 0.96 and confidence >= 50 and support >= 2
                else "MEDIUM" if score >= 0.90 or support >= 2
                else "LOW"
            ),
            "ocr_confidence": round(confidence, 1),
            "match_score": round(score, 3),
            "independent_passes": support,
            "evidence_type": "local_ocr",
            "status": "grounded_ocr",
            "language": "latin_architectural_lexicon",
            "correction": (
                None
                if _normalise_text(cluster["representative"]["reading"]["raw_text"])
                .replace(" ", "").upper()
                == re.sub(r"[^A-Z0-9]", "", cluster["term"].upper())
                else "architectural_lexicon_match"
            ),
        })
    accepted.sort(key=lambda item: (item["bbox_pixels"][1], item["bbox_pixels"][0]))
    seen_occurrences = {}
    for item in accepted:
        seen_occurrences[item["text"]] = seen_occurrences.get(item["text"], 0) + 1
        item["occurrence"] = seen_occurrences[item["text"]]
    return accepted


def _centres_close(left, right, plan_box):
    left_box = left["bbox_pixels"]
    right_box = right["bbox_pixels"]
    left_x = (left_box[0] + left_box[2]) / 2.0
    left_y = (left_box[1] + left_box[3]) / 2.0
    right_x = (right_box[0] + right_box[2]) / 2.0
    right_y = (right_box[1] + right_box[3]) / 2.0
    plan_width = plan_box[2] - plan_box[0]
    plan_height = plan_box[3] - plan_box[1]
    horizontal_overlap = min(left_box[2], right_box[2]) - max(
        left_box[0], right_box[0]
    )
    vertical_overlap = min(left_box[3], right_box[3]) - max(
        left_box[1], right_box[1]
    )
    overlapping_line = horizontal_overlap > 0 and vertical_overlap >= -4

    return overlapping_line or (
        abs(left_x - right_x) <= max(22.0, plan_width * 0.10)
        and abs(left_y - right_y) <= max(16.0, plan_height * 0.075)
    )


def _label_matches(readings, plan_box, image_shape):
    scored = []

    for reading in readings:
        raw_norm = _normalise_text(reading.get("raw_text"))
        if _persian_count(raw_norm) < 2:
            continue

        rankings = sorted(
            (
                (_similarity(raw_norm, source_text), source_text, semantic)
                for source_text, semantic in PLAN_LABEL_LEXICON
            ),
            reverse=True,
        )
        best_score, source_text, semantic = rankings[0]
        next_score = rankings[1][0] if len(rankings) > 1 else 0.0

        if best_score < 0.62:
            continue
        if str(reading.get("pass", "")).endswith("_full") and best_score < 0.90:
            bedroom_fragment = (
                source_text == "اتاق خواب"
                and best_score >= 0.70
                and "خوا" in raw_norm
                and "تا" in raw_norm
            )
            if not bedroom_fragment:
                continue
        if best_score < 0.94 and best_score - next_score < 0.07:
            continue

        item = dict(reading)
        item.update({
            "text": source_text,
            "semantic_function": semantic,
            "match_score": round(float(best_score), 3),
        })
        scored.append(item)

    clusters = []
    for item in sorted(
        scored,
        key=lambda entry: (
            entry["text"], entry["bbox_pixels"][1], entry["bbox_pixels"][0],
            -entry["match_score"], -entry["ocr_confidence"],
        ),
    ):
        cluster = next(
            (
                entry for entry in clusters
                if entry["text"] == item["text"]
                and _centres_close(entry["representative"], item, plan_box)
            ),
            None,
        )
        if cluster is None:
            clusters.append({
                "text": item["text"],
                "semantic_function": item["semantic_function"],
                "items": [item],
                "passes": {item["pass"]},
                "representative": item,
            })
            continue

        cluster["items"].append(item)
        cluster["passes"].add(item["pass"])
        current = cluster["representative"]
        if (
            item["match_score"], item["ocr_confidence"]
        ) > (
            current["match_score"], current["ocr_confidence"]
        ):
            cluster["representative"] = item

    accepted = []
    image_height, image_width = image_shape

    for cluster in clusters:
        representative = cluster["representative"]
        score = representative["match_score"]
        max_confidence = max(item["ocr_confidence"] for item in cluster["items"])
        support = len(cluster["passes"])
        target_length = len(_normalise_text(cluster["text"]).replace(" ", ""))
        raw_persian = _persian_count(_normalise_text(representative["raw_text"]))

        is_accepted = (
            (score >= 0.96 and (max_confidence >= 8 or support >= 2))
            or (score >= 0.84 and (max_confidence >= 35 or support >= 2))
            or (
                score >= 0.73 and max_confidence >= 20 and support >= 2
                and raw_persian >= target_length * 0.72
            )
            or (
                cluster["text"] == "حمام" and target_length <= 5 and score >= 0.64
                and max_confidence >= 20 and support >= 3
                and raw_persian <= 3
            )
            or (
                cluster["text"] == "اتاق خواب" and score >= 0.70
                and max_confidence >= 20
                and raw_persian >= target_length * 0.65
                and "خوا" in _normalise_text(representative["raw_text"])
                and "تا" in _normalise_text(representative["raw_text"])
            )
        )

        if not is_accepted:
            continue

        box = representative["bbox_pixels"]
        confidence = (
            "HIGH"
            if score >= 0.96 and max_confidence >= 50 and support >= 2
            else "MEDIUM"
            if score >= 0.80 or support >= 3
            else "LOW"
        )
        accepted.append({
            "text": cluster["text"],
            "semantic_function": cluster["semantic_function"],
            "raw_ocr": representative["raw_text"],
            "bbox_pixels": [round(value, 1) for value in box],
            "bbox_normalized": [
                round(box[0] / image_width, 4),
                round(box[1] / image_height, 4),
                round(box[2] / image_width, 4),
                round(box[3] / image_height, 4),
            ],
            "confidence": confidence,
            "ocr_confidence": round(max_confidence, 1),
            "match_score": round(score, 3),
            "independent_passes": support,
            "evidence_type": "local_ocr",
            "status": "grounded_ocr",
            "correction": (
                None
                if _normalise_text(representative["raw_text"]).replace(" ", "")
                in {
                    _normalise_text(cluster["text"]).replace(" ", ""),
                    _normalise_text(cluster["text"]).replace(" ", "")[::-1],
                }
                else "architectural_lexicon_match"
            ),
        })

    accepted.sort(key=lambda item: (item["bbox_pixels"][1], item["bbox_pixels"][0]))
    seen_occurrences = {}
    for item in accepted:
        seen_occurrences[item["text"]] = seen_occurrences.get(item["text"], 0) + 1
        item["occurrence"] = seen_occurrences[item["text"]]

    return accepted


def _close_small_gaps(values, maximum_gap=3):
    values = values.copy()
    index = 0
    while index < len(values):
        if values[index]:
            index += 1
            continue
        start = index
        while index < len(values) and not values[index]:
            index += 1
        if (
            start > 0 and index < len(values)
            and index - start <= maximum_gap
        ):
            values[start:index] = True
    return values


def _runs(values):
    start = None
    for index, value in enumerate(values):
        if value and start is None:
            start = index
        elif not value and start is not None:
            yield start, index
            start = None
    if start is not None:
        yield start, len(values)


def _perimeter_windows(gray, plan_box):
    """Conservatively ground horizontal-edge window symbols.

    A candidate must be a non-empty thin interruption, have thick perimeter
    strokes on both sides, and span a plausible architectural opening.  Empty
    gaps (typical doorway/entrance symbols) are deliberately rejected.
    """

    image_height, image_width = gray.shape
    x0, y0, x1, y1 = plan_box
    plan_width = x1 - x0
    ink = gray < 150
    output = []

    top_rows = range(max(0, y0 - 2), min(image_height, y0 + 11))
    bottom_rows = range(max(0, y1 - 12), min(image_height, y1 + 2))
    top_edge = max(top_rows, key=lambda row: int(ink[row, x0:x1].sum()))
    bottom_edge = max(bottom_rows, key=lambda row: int(ink[row, x0:x1].sum()))

    for side, edge_y in (("top", top_edge), ("bottom", bottom_edge)):
        band_y0 = max(0, edge_y - 5)
        band_y1 = min(image_height, edge_y + 6)
        profile = ink[band_y0:band_y1, x0:x1].sum(axis=0)
        thin = (profile >= 1) & (profile <= 4)
        thin = _close_small_gaps(thin, 3)

        for local_start, local_end in _runs(thin):
            length = local_end - local_start
            if length < max(12, int(plan_width * 0.045)):
                continue
            if length > plan_width * 0.32:
                continue

            flank = max(5, int(plan_width * 0.025))
            left = profile[max(0, local_start - flank):local_start]
            right = profile[local_end:min(len(profile), local_end + flank)]
            if len(left) < 3 or len(right) < 3:
                continue
            if float(np.median(left)) < 5 or float(np.median(right)) < 5:
                continue

            segment = profile[local_start:local_end]
            if float(np.mean(segment)) < 1.0:
                continue
            start = x0 + local_start
            end = x0 + local_end
            row_activity = ink[
                band_y0:band_y1, start:end
            ].sum(axis=1)
            if int((row_activity >= max(2, length * 0.05)).sum()) > 3:
                continue

            box = [start, band_y0, end, band_y1]
            output.append({
                "kind": "window",
                "producer": "core.vision.local_plan_reader_v1._perimeter_windows",
                "side": side,
                "bbox_pixels": box,
                "bbox_normalized": [
                    round(box[0] / image_width, 4),
                    round(box[1] / image_height, 4),
                    round(box[2] / image_width, 4),
                    round(box[3] / image_height, 4),
                ],
                "confidence": "MEDIUM",
                "status": "visible",
                "evidence_type": "local_raster_geometry",
                "evidence": (
                    "thin non-empty perimeter interruption bounded by "
                    "thick wall strokes (%s edge)" % side
                ),
            })

    return output


def _default_tessdata_path():
    return Path(__file__).resolve().parents[2] / "models" / "ocr" / "tessdata_fast"


# ==========================================================
# LOCAL OCR ENVIRONMENT FINGERPRINT
#
# LOCAL_PLAN_READING_V1 — an analysis produced while the OCR environment was
# degraded must not be served as a CURRENT result once the environment is
# repaired.  The cache layer stores this fingerprint beside the evidence
# pipeline version and refuses to reuse an analysis whose fingerprint no
# longer matches the running process.
#
# It deliberately separates ENVIRONMENT from IMAGE: an unsupported raster
# (e.g. a non-PNG upload) is a property of the image and is unaffected by
# this fingerprint, while a missing compiled backend or missing Persian
# language data means the local reader could not run at all.
# ==========================================================

def ocr_backend_importable():
    """True when the compiled OCR backend (tesserocr) can be imported."""

    try:
        from tesserocr import PyTessBaseAPI  # noqa: F401
    except Exception:
        return False

    return True


def ocr_language_data_present(tessdata_path=None):
    """True when the Persian language model the reader needs is on disk."""

    directory = Path(tessdata_path) if tessdata_path else _default_tessdata_path()

    return Path(directory, "fas.traineddata").is_file()


def local_ocr_environment(tessdata_path=None):
    """Compact fingerprint of the local OCR environment.

    Compared verbatim by the cache layer; any change forces a re-read.
    """

    try:
        import cv2
        symbol_backend = cv2.__version__
    except ImportError:
        symbol_backend = "off"
    try:
        from PIL import __version__ as pillow_version
    except ImportError:
        pillow_version = "off"
    return "tesserocr=%s;tessdata=%s;symbols=%s;jpeg=%s" % (
        "on" if ocr_backend_importable() else "off",
        "on" if ocr_language_data_present(tessdata_path) else "off",
        symbol_backend, pillow_version,
    )



def _read_plan_raster(gray, *, tessdata_path=None, native_gray=None, native_scale=None):
    """Read a plan raster without using or consulting the vision provider.

    ``native_gray``/``native_scale`` let a caller that already resampled the
    panel (``local_plan_sheet_v1.analyze_sheet``) hand the recovery layer the
    ORIGINAL, highest-resolution crop instead of the INTER_CUBIC resample.
    Both default to ``None``, which preserves the historical single-frame
    behaviour exactly.
    """

    result = {
        "contract": CONTRACT, "version": VERSION, "status": "unavailable",
        "source": "local_offline_raster", "provider_independent": True,
        "labels": [], "openings": [], "furniture_observed": None,
        "furniture_evidence": [], "symbol_analysis_status": "unavailable",
        "element_evidence": [], "element_analysis_status": "unavailable",
        "enclosure_geometry": {"count": None, "count_status": "unknown", "regions": []},
        "limitations": [
            "PNG and JPEG/JPG raster input",
            "element recognition is conservative and limited to supported plan-symbol conventions",
            "no north direction, unread dimensions, materials, structural design or hidden geometry inferred",
        ],
    }
    try:
        plan_box = _plan_bbox(gray)
    except Exception as exc:
        result["reason"] = "%s:%s" % (type(exc).__name__, exc)
        return result

    # OCR availability must not suppress independent raster symbols/geometry.
    readings, labels = [], []
    tessdata = Path(tessdata_path) if tessdata_path else _default_tessdata_path()
    try:
        readings = _ocr_readings(gray, plan_box, tessdata)
        # W3.5 — a bounded, targeted recovery for architectural text that is too
        # small for the single-pass ladder. It emits READINGS only; the existing
        # W3 matchers below remain the only path that can name a space.
        #
        # W3R — the recovery is DISABLED by default. Measured on the real
        # acceptance set it cost 480 OCR calls per panel (+26% on D) and yielded
        # no reading any matcher accepted; recoverability is not predictable
        # from candidate geometry, so it is opt-in rather than speculative.
        from core.vision.small_architectural_text_v1 import (
            SMALL_TEXT_RECOVERY_ENABLED,
            recovery_disabled_audit,
            recover_small_architectural_readings,
        )
        if not SMALL_TEXT_RECOVERY_ENABLED:
            small_readings, small_audit = [], recovery_disabled_audit()
        elif native_gray is not None and native_scale is not None:
            native_box = _plan_bbox(native_gray)
            small_readings, small_audit = recover_small_architectural_readings(
                native_gray, native_box, tessdata, bbox_scale=native_scale,
            )
        else:
            small_readings, small_audit = recover_small_architectural_readings(
                gray, plan_box, tessdata,
            )
        result["small_architectural_text"] = small_audit
        readings = readings + small_readings
        labels = _label_matches(readings, plan_box, gray.shape)
        labels = labels + _architectural_label_matches(readings, plan_box, gray.shape)
        # W3R — a drawing junction is not a printed label, however well a fuzzy
        # lexicon match fits it. Rejection only; never admits a reading.
        labels, graphic = _reject_graphic_labels(gray, labels)
        if graphic:
            result["rejected_graphic_ocr_labels"] = graphic
        labels.sort(key=lambda item: (item["bbox_pixels"][1], item["bbox_pixels"][0]))
        result["ocr_status"] = "analyzed"
    except Exception as exc:
        result["ocr_status"] = "unavailable"
        result["ocr_reason"] = "%s:%s" % (type(exc).__name__, exc)
    openings = _perimeter_windows(gray, plan_box)
    try:
        symbols = analyze_plan_symbols(gray, plan_box, tessdata_path=tessdata)
    except Exception as exc:
        symbols = {"status": "unavailable", "furniture_evidence": [],
                   "reason": "%s:%s" % (type(exc).__name__, exc)}
    labels, rejected_labels = filter_symbol_overlapping_labels(gray, labels)
    result["rejected_symbol_ocr_labels"] = rejected_labels
    furniture = symbols.get("furniture_evidence") or []
    geometry = symbols.get("enclosure_geometry") or result["enclosure_geometry"]
    elements = symbols.get("element_evidence") or []
    if symbols.get("element_analysis_status") == "analyzed":
        from core.vision.local_plan_elements_v1 import merge_local_openings
        openings, elements = merge_local_openings(gray, openings, elements)
    result.update({
        "status": "grounded" if labels or openings or furniture or elements or geometry.get("regions") else "no_grounded_evidence",
        "image_size": {"width": int(gray.shape[1]), "height": int(gray.shape[0])},
        "plan_bbox_pixels": list(plan_box), "labels": labels, "openings": openings,
        "furniture_observed": bool(furniture) if symbols.get("status") == "analyzed" else None,
        "furniture_evidence": furniture, "symbol_analysis_status": symbols.get("status"),
        "symbol_pipeline_version": symbols.get("version"), "enclosure_geometry": geometry,
        "element_evidence": elements, "element_analysis_status": symbols.get("element_analysis_status", "unavailable"),
        "element_pipeline_version": symbols.get("element_pipeline_version"),
        "element_reason": symbols.get("element_reason"),
        "ocr_candidate_count": len(readings), "ocr_engine": "tesseract-5.5/tesserocr-2.10",
        "ocr_language": "fas+eng", "geometry_engine": "numpy-raster-v1",
    })
    result["limitations"].extend(symbols.get("limitations") or [])
    if symbols.get("reason"):
        result["symbol_reason"] = symbols["reason"]
    return result


def read_local_plan(path, *, tessdata_path=None):
    """Detect sheet structure before any OCR or plan-symbol interpretation."""
    try:
        gray = _read_raster(str(path))
    except Exception as exc:
        result = _read_plan_raster(None, tessdata_path=tessdata_path)
        result["reason"] = "%s:%s" % (type(exc).__name__, exc)
        return result
    from core.vision.local_plan_sheet_v1 import detect_sheet, analyze_sheet
    sheet = detect_sheet(gray)
    if sheet["sheet_type"] == "multi_plan":
        tessdata = Path(tessdata_path) if tessdata_path else _default_tessdata_path()
        return analyze_sheet(gray, sheet, _read_plan_raster, tessdata)
    from core.vision.local_plan_sheet_v1 import classify_plan_role

    result = _read_plan_raster(gray, tessdata_path=tessdata_path)
    elements = result.get("element_evidence") or []
    role_evidence = {
        "furniture_symbols": len(result.get("furniture_evidence") or []),
        "furnishing_patterns": 0,
        "axis_count": sum(1 for e in elements if e.get("type") == "axis"),
        "axis_orientations": sorted({
            (e.get("geometry") or {}).get("orientation")
            for e in elements
            if e.get("type") == "axis"
        }),
        "enclosure_regions": len(
            (result.get("enclosure_geometry") or {}).get("regions") or []
        ),
        "space_labels": len(result.get("labels") or []),
        "title_role": None,
    }
    sheet["panels"][0]["role_evidence"] = role_evidence
    sheet["panels"][0]["role"] = classify_plan_role(role_evidence)
    result["sheet_structure"] = sheet
    return result



__all__ = [
    "read_local_plan",
    "local_ocr_environment",
    "ocr_backend_importable",
    "ocr_language_data_present",
    "CONTRACT",
    "VERSION",
]


# ==========================================================
# STARTUP BANNER
#
# Deliberately ASCII-only.  The Core's stdout is a log FILE opened with the
# locale encoding, so a non-ASCII character here could kill the process
# before it binds its port — which is exactly how a degraded local reader
# used to pass unnoticed.
# ==========================================================

print(
    "LOCAL PLAN READER %s ONLINE (%s)"
    % (VERSION, local_ocr_environment())
)
