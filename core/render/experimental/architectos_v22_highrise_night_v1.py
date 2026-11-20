#!/usr/bin/env python3
"""ArchitectOS v22 high-rise floor control + zero-drift night relighting.

File: core/render/experimental/architectos_v22_highrise_night_v1.py

STATUS: ``V22_HIGHRISE_NIGHT_ROUTED_CPU_PASS -- GPU_UNVERIFIED``

Routing (authorized 2026-11-08)
------------------------------
``workflow_selector.WorkflowSelector`` resolves an explicit
``request["v22_mode"]`` to this module's base graph and refuses every
combination it cannot honour; ``RenderRuntime.render(v22_mode=...)`` applies
``build_mode_specific_stage2_workflow`` to the loaded graph and fails closed
when the ControlNet asset or the graph is unavailable. Both modes are opt-in:
a request that does not set ``v22_mode`` is byte-for-byte unchanged.
No GPU render of either mode has been executed.

What this module is
-------------------
Two render capabilities that the project's own evidence base already
identified as the correct root-cause fixes, but which had no producer:

1. ``MODE_1_TXT2IMG_EXACT_FLOORS``
   ``ARCHITECTOS_R1_CONTROLNET_AB_GPU_RESULT_V1.md`` section 8 concluded that
   attaching a real reference depth map to a text-to-image graph transfers the
   *reference building's identity* (it reproduced a cylindrical corner tower at
   strength 0.8) rather than controlling floor *count*. The same report named
   the correct fix and declared it absent from the project:

       "A synthetic structural scaffold. A depth map containing only three
        horizontal bands and no building identity would give count without
        identity. No producer for that exists in the project."

   ``synthesize_exact_n_story_tower_controlnet`` is that producer. It draws a
   deterministic 2-point-perspective wireframe with exactly ``N`` floor tiers
   and *no* building identity - no windows, no balconies, no ornament, no
   material. Nothing in the image can be cloned except the tier rhythm.

2. ``MODE_3_DAY_TO_NIGHT_RELIGHT``
   ``ARCHITECTOS_R3_NIGHT_05_DENOISE_ISOLATION_V1.md`` section 8 established
   that geometry and material survive source-latent img2img across denoise
   0.30-0.50 (all band edges within 2 px) and that the *only* remaining failure
   is the sky: sky mean luma stayed 187-190 against a target of <= 40. The
   daylight sky latent dominates the prompt at denoise <= 0.50.

   ``synthesize_day_to_night_prepass`` removes that dominant daylight sky
   *before* the sampler ever sees the latent, and installs a blue-hour ambient
   floor so the facade cannot be crushed to black - the documented Kontext
   failure mode (``RGB(5,5,8)``). ``lock_night_render_to_day_geometry`` then
   restores the day render's high-frequency geometry into the sampler output.

Boundaries honoured by this file
--------------------------------
* No workflow JSON under ``core/render/workflows/`` is modified, and no
  existing render route changes: ``v22_mode`` is an explicit opt-in and
  every other caller keeps its current graph, denoise and prompt.
* No GPU job, no ComfyUI POST, no model load and no network call originates
  here. The selector and runtime that now call into this module are
  CPU-verified only; neither mode has been rendered.
* ``TIME_OF_DAY_DENOISE = 0.30`` is not read, shadowed or changed. Each mode
  states its own denoise, and the runtime withholds the caller's value while
  a mode is active.
* Every function is deterministic and side-effect free except for the explicit
  ``write_png`` helpers.

Evidence discipline
-------------------
These functions are CPU-verified. CPU PASS is not visual PASS: a wireframe that
counts tiers correctly is not proof that FLUX renders that many storeys, and a
luminance floor is not proof of a convincing night image. GPU visual acceptance
remains pending and unauthorised.
"""
from __future__ import annotations

import hashlib
import math
import pathlib
import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

__all__ = [
    "MIN_HIGH_RISE_FLOORS",
    "FloorCountReading",
    "parse_requested_floor_count",
    "parse_requested_floor_count_detail",
    "requires_exact_floor_control",
    "TowerScaffoldGeometry",
    "synthesize_exact_n_story_tower_controlnet",
    "kelvin_to_bgr",
    "synthesize_day_to_night_prepass",
    "lock_night_render_to_day_geometry",
    "attach_controlnet_to_t2i_graph",
    "build_mode_specific_stage2_workflow",
    "MissingControlNetNodeError",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: A building is "high-rise" for exact-floor-control purposes at this count.
MIN_HIGH_RISE_FLOORS = 5

MODE_TXT2IMG_EXACT_FLOORS = "MODE_1_TXT2IMG_EXACT_FLOORS"
MODE_DAY_TO_NIGHT_RELIGHT = "MODE_3_DAY_TO_NIGHT_RELIGHT"

#: Real-world scaffold proportions. These are deliberately architectural
#: (metres), not normalised, because the ratio of height to footprint is what
#: decides whether a 25-storey tower reads as a tower or as a slab.
FLOOR_HEIGHT_M = 3.2
TOWER_HALF_WIDTH_M = 14.0
TOWER_HALF_DEPTH_M = 12.0
PODIUM_SCALE = 1.55
EYE_HEIGHT_M = 1.6
CAMERA_DISTANCE_RATIO = 2.2
YAW_DEGREES = 32.0

#: Requested frame margins for the exact-floor scaffold.
TOP_SKY_MARGIN_RATIO = 0.12
BOTTOM_STREET_MARGIN_RATIO = 0.10
SIDE_MARGIN_RATIO = 0.06

#: Documented denoise/conditioning settings for the two modes.
TXT2IMG_EXACT_FLOORS_PARAMS: Dict[str, float] = {
    "denoise": 0.96,
    "controlnet_strength": 0.86,
    "controlnet_start_percent": 0.0,
    "controlnet_end_percent": 0.88,
}
DAY_TO_NIGHT_RELIGHT_PARAMS: Dict[str, float] = {
    "denoise": 0.34,
    "controlnet_strength": 0.96,
    "controlnet_start_percent": 0.0,
    "controlnet_end_percent": 1.00,
}

#: Colour temperatures named in the requirement.
INTERIOR_GLOW_KELVIN = 2900
EXTERIOR_WASHER_KELVIN = 3000


class MissingControlNetNodeError(RuntimeError):
    """Raised when a graph is asked for ControlNet control but has no such node.

    This is deliberately fatal rather than silently degrading to an
    unconditioned render - the same fail-closed principle the production
    conditioned-render gate already enforces.
    """


# ---------------------------------------------------------------------------
# 1. Floor-count parsing
# ---------------------------------------------------------------------------

_PERSIAN_DIGITS = str.maketrans(
    "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9"
    "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669",
    "01234567890123456789",
)

#: Story nouns across the languages this product accepts.
_STORY_NOUN = (
    r"(?:"
    r"story|stories|storey|storeys|storeyed|floor|floors|floored"
    r"|طبقه|طبقات|اشکوب"
    r")"
)

#: A number immediately followed by a story noun, or an "N-story" compound.
_COUNT_PATTERNS: Tuple[re.Pattern, ...] = (
    # "25-story", "12 storey", "8-storeyed"
    re.compile(r"(?<![\d.,])(\d{1,3})\s*[-\u2010-\u2015]?\s*" + _STORY_NOUN,
               re.IGNORECASE),
    # "25 floors", "twenty five floors" is out of scope (no word numerals)
    re.compile(r"(?<![\d.,])(\d{1,3})\s*(?:طَبَقه|طبقه|طبقات)"),
)

#: A bare number that is clearly a storey count in an architectural sentence.
#: Only used when no direct noun match exists, and only for Persian/Arabic
#: script input where the noun commonly precedes the numeral.
_COUNT_PRECEDING_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"(?:ساختمان|برج|بلوک|سازه)\s*(?:با\s*)?(\d{1,3})\s*" + _STORY_NOUN),
)

#: Tokens that, appearing *before* the numeral, negate the count.
_NEGATION_BEFORE = (
    "نمی", "نمی\u200c", "نه ", "نه\u200c", "بدون", "نباشد", "نخواه",
    "not ", "no ", "without ", "avoid ", "except ", "don't ", "dont ",
    "rather than ", "instead of ",
)

#: Negative-verb forms that negate a count *after* it. Restricted to the
#: unambiguous negative-verb family so that ordinary post-numeral qualifiers
#: such as "25 floors, not more" are not misread as negations.
_NEGATION_AFTER = (
    "نمی\u200cخواهم", "نمیخواهم", "نخواهم", "نمی\u200cخواستم",
    "نمیخواستم", "لازم نیست", "نیازی نیست",
)

_BEFORE_WINDOW = 22
_AFTER_WINDOW = 26
_CLAUSE_BREAKS = ".،,;؛\n!?"


def _normalize_digits(text: str) -> str:
    return text.translate(_PERSIAN_DIGITS)


def _has_negation_before(text: str, start: int) -> bool:
    window = text[max(0, start - _BEFORE_WINDOW):start]
    # A clause boundary resets negation scope: "3 floors. 25 floors" is not
    # negated by a "no" in the previous sentence.
    for brk in _CLAUSE_BREAKS:
        idx = window.rfind(brk)
        if idx != -1:
            window = window[idx + 1:]
    low = window.lower()
    return any(tok in low for tok in _NEGATION_BEFORE)


def _has_negation_after(text: str, end: int) -> bool:
    window = text[end:end + _AFTER_WINDOW]
    for brk in _CLAUSE_BREAKS:
        idx = window.find(brk)
        if idx != -1:
            window = window[:idx]
    # A second numeral inside the window means the negative verb belongs to a
    # different clause ("25 floors but not 30").
    if re.search(r"\d", window):
        return False
    return any(tok in window for tok in _NEGATION_AFTER)


@dataclass(frozen=True)
class FloorCountReading:
    """Structured result of floor-count parsing.

    ``count`` is ``None`` whenever the text does not state a usable exact
    storey count, including when a stated count is negated.
    """

    count: Optional[int]
    raw_match: str = ""
    span: Tuple[int, int] = (-1, -1)
    negated: bool = False
    source: str = "none"
    notes: List[str] = field(default_factory=list)

    @property
    def is_exact(self) -> bool:
        return self.count is not None and not self.negated


def parse_requested_floor_count_detail(user_prompt: str) -> FloorCountReading:
    """Parse an exact storey count out of a user prompt.

    Returns a :class:`FloorCountReading`. Negated counts (Persian
    ``نمی‌خواهم``, English ``not``/``without``) are reported with
    ``count=None`` and ``negated=True`` rather than being silently accepted -
    the failure mode recorded for the older ``_floor_count()`` helper, which
    ignores ``is_affirmed``.

    Limits, stated plainly: this is a lexical reader, not a semantic parser. It
    handles a numeral adjacent to a story noun. It does not read word numerals
    ("twenty five storeys"), it does not resolve "the top 5 floors of a 25
    storey tower" to a building height, and it does not consult zoning data.
    """
    if not isinstance(user_prompt, str) or not user_prompt.strip():
        return FloorCountReading(count=None, source="empty")

    text = _normalize_digits(user_prompt)
    notes: List[str] = []

    for pattern in _COUNT_PATTERNS + _COUNT_PRECEDING_PATTERNS:
        for match in pattern.finditer(text):
            raw = int(match.group(1))
            if raw < 1 or raw > 200:
                notes.append("out_of_range:%d" % raw)
                continue
            start, end = match.span()
            negated = _has_negation_before(text, start) or _has_negation_after(text, end)
            if negated:
                return FloorCountReading(
                    count=None,
                    raw_match=match.group(0),
                    span=(start, end),
                    negated=True,
                    source="negated",
                    notes=notes + ["negation_detected"],
                )
            return FloorCountReading(
                count=raw,
                raw_match=match.group(0),
                span=(start, end),
                negated=False,
                source="numeral_adjacent_to_story_noun",
                notes=notes,
            )

    return FloorCountReading(count=None, source="no_exact_count", notes=notes)


def parse_requested_floor_count(user_prompt: str) -> Optional[int]:
    """Return the exact storey count stated in ``user_prompt``, else ``None``."""
    return parse_requested_floor_count_detail(user_prompt).count


def requires_exact_floor_control(num_floors: Optional[int],
                                 minimum: int = MIN_HIGH_RISE_FLOORS) -> bool:
    """True when a text-to-image request must not run unconditioned."""
    return num_floors is not None and num_floors >= minimum


# ---------------------------------------------------------------------------
# 2. Deterministic N-storey tower scaffold
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TowerScaffoldGeometry:
    """Geometry contract used to draw the scaffold."""

    num_floors: int
    podium_floors: int
    floor_height_m: float = FLOOR_HEIGHT_M
    tower_half_width_m: float = TOWER_HALF_WIDTH_M
    tower_half_depth_m: float = TOWER_HALF_DEPTH_M
    podium_scale: float = PODIUM_SCALE
    eye_height_m: float = EYE_HEIGHT_M
    yaw_degrees: float = YAW_DEGREES
    camera_distance_ratio: float = CAMERA_DISTANCE_RATIO

    @property
    def total_height_m(self) -> float:
        return self.num_floors * self.floor_height_m

    @property
    def tower_floors(self) -> int:
        return self.num_floors - self.podium_floors

    @property
    def podium_height_m(self) -> float:
        return self.podium_floors * self.floor_height_m

    def validate(self) -> None:
        if self.num_floors < 1:
            raise ValueError("num_floors must be >= 1, got %r" % (self.num_floors,))
        if self.podium_floors < 0:
            raise ValueError("podium_floors must be >= 0")
        if self.podium_floors > self.num_floors:
            raise ValueError(
                "podium_floors (%d) cannot exceed num_floors (%d)"
                % (self.podium_floors, self.num_floors)
            )
        if self.floor_height_m <= 0:
            raise ValueError("floor_height_m must be > 0")


def _rotate_y(points: np.ndarray, yaw_rad: float) -> np.ndarray:
    c, s = math.cos(yaw_rad), math.sin(yaw_rad)
    out = np.empty_like(points)
    out[:, 0] = points[:, 0] * c + points[:, 2] * s
    out[:, 1] = points[:, 1]
    out[:, 2] = -points[:, 0] * s + points[:, 2] * c
    return out


def _project(points: np.ndarray, yaw_rad: float, cam_dist: float,
             eye_h: float) -> np.ndarray:
    """Project world points to image-plane coordinates.

    Camera sits on +Z looking toward -Z with zero pitch and zero roll. With
    pitch and roll at zero, world-vertical edges remain image-vertical, so the
    result is a true two-point perspective rather than a three-point one.
    """
    rotated = _rotate_y(points, yaw_rad)
    denom = cam_dist - rotated[:, 2]
    if np.any(denom <= 1e-6):
        raise ValueError("geometry crosses the camera plane")
    u = rotated[:, 0] / denom
    v = -(rotated[:, 1] - eye_h) / denom
    return np.stack([u, v], axis=1)


def _box_ring(half_x: float, half_z: float, y: float) -> np.ndarray:
    return np.array(
        [
            [-half_x, y, -half_z],
            [half_x, y, -half_z],
            [half_x, y, half_z],
            [-half_x, y, half_z],
        ],
        dtype=np.float64,
    )


def _face_visible(centre: np.ndarray, normal: Tuple[float, float, float],
                  yaw_rad: float, cam_pos: np.ndarray) -> bool:
    """Back-face test in camera space."""
    rn = _rotate_y(np.array([normal], dtype=np.float64), yaw_rad)[0]
    rc = _rotate_y(np.array([centre], dtype=np.float64), yaw_rad)[0]
    return float(np.dot(rn, cam_pos - rc)) > 0.0


def _visible_ring_edges(half_x: float, half_z: float, y_sample: float,
                        yaw_rad: float, cam_pos: np.ndarray
                        ) -> Tuple[np.ndarray, List[Tuple[int, int]], set]:
    """Return the ring corners, its camera-visible edges and visible corners.

    Only the faces actually turned toward the camera are drawn. Drawing all
    four edges of every ring produces a chevron/zigzag pattern in two-point
    perspective - spurious diagonal structure that a ControlNet branch can
    easily mistake for real building articulation.
    """
    corners = _box_ring(half_x, half_z, y_sample)
    faces = (
        ((0.0, 0.0, -half_z), (0.0, 0.0, -1.0), (0, 1)),
        ((half_x, 0.0, 0.0), (1.0, 0.0, 0.0), (1, 2)),
        ((0.0, 0.0, half_z), (0.0, 0.0, 1.0), (2, 3)),
        ((-half_x, 0.0, 0.0), (-1.0, 0.0, 0.0), (3, 0)),
    )
    edges: List[Tuple[int, int]] = []
    visible_corners: set = set()
    for (cx, _, cz), normal, (a, b) in faces:
        centre = np.array([cx, y_sample, cz], dtype=np.float64)
        if _face_visible(centre, normal, yaw_rad, cam_pos):
            edges.append((a, b))
            visible_corners.add(a)
            visible_corners.add(b)
    return corners, edges, visible_corners


def synthesize_exact_n_story_tower_controlnet(
    num_floors: int,
    canvas_width: int = 896,
    canvas_height: int = 1344,
    podium_floors: int = 2,
    *,
    geometry: Optional[TowerScaffoldGeometry] = None,
    line_thickness: int = 2,
    ring_thickness: int = 2,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Draw a deterministic N-tier tower wireframe for ControlNet.

    The image contains exactly ``num_floors`` horizontal floor tiers
    (``podium_floors`` podium tiers plus ``num_floors - podium_floors`` tower
    tiers) and carries no building identity of any kind - no windows, doors,
    balconies, ornament or material. That is the point: the R1 A/B experiment
    showed that a *real* reference map clones the reference building, whereas a
    pure tier scaffold can only communicate count and rhythm.

    Args:
        num_floors: Storeys to draw. Must be >= 1 and >= ``podium_floors``.
        canvas_width: Output width in pixels.
        canvas_height: Output height in pixels.
        podium_floors: Wide base tiers, drawn at ``PODIUM_SCALE`` footprint.
        geometry: Optional override of the scaffold proportions.
        line_thickness: Vertical edge thickness in pixels.
        ring_thickness: Horizontal tier ring thickness in pixels.

    Returns:
        ``(cn_img, meta)`` where ``cn_img`` is a uint8 BGR lineart image
        (white background, dark lines) and ``meta`` records the measured
        margins, tier count, fit constraint and image digest.
    """
    if canvas_width < 64 or canvas_height < 64:
        raise ValueError("canvas must be at least 64x64")
    if canvas_width % 8 or canvas_height % 8:
        raise ValueError(
            "canvas dimensions must be multiples of 8 for latent alignment, got %dx%d"
            % (canvas_width, canvas_height)
        )

    geom = geometry or TowerScaffoldGeometry(
        num_floors=num_floors, podium_floors=podium_floors
    )
    if geometry is not None and geometry.num_floors != num_floors:
        raise ValueError("geometry.num_floors disagrees with num_floors")
    geom.validate()

    yaw_rad = math.radians(geom.yaw_degrees)
    cam_dist = geom.camera_distance_ratio * geom.total_height_m
    cam_pos = np.array([0.0, geom.eye_height_m, cam_dist], dtype=np.float64)

    tower_hx = geom.tower_half_width_m
    tower_hz = geom.tower_half_depth_m
    podium_hx = tower_hx * geom.podium_scale
    podium_hz = tower_hz * geom.podium_scale

    tower_mid_y = (geom.podium_height_m + geom.total_height_m) * 0.5
    _, tower_edges, tower_visible = _visible_ring_edges(
        tower_hx, tower_hz, tower_mid_y, yaw_rad, cam_pos
    )
    if geom.podium_floors > 0:
        _, podium_edges, podium_visible = _visible_ring_edges(
            podium_hx, podium_hz, geom.podium_height_m * 0.5, yaw_rad, cam_pos
        )
    else:
        podium_edges, podium_visible = [], set()
    visible_faces = len(tower_edges)

    fh = geom.floor_height_m
    tower_base_y = geom.podium_height_m
    top_y = geom.total_height_m

    # --- collect rings -----------------------------------------------------
    rings: List[Tuple[np.ndarray, str]] = []
    if geom.podium_floors > 0:
        for i in range(geom.podium_floors + 1):
            rings.append((_box_ring(podium_hx, podium_hz, i * fh), "podium"))
    for i in range(geom.podium_floors, geom.num_floors + 1):
        rings.append((_box_ring(tower_hx, tower_hz, i * fh), "tower"))

    # Vertical edges, restricted to corners that bound a visible face.
    verticals: List[Tuple[np.ndarray, np.ndarray, str]] = []
    if geom.podium_floors > 0:
        podium_base = _box_ring(podium_hx, podium_hz, 0.0)
        for idx in sorted(podium_visible):
            corner = podium_base[idx]
            verticals.append((
                corner.copy(),
                np.array([corner[0], tower_base_y, corner[2]]),
                "podium",
            ))
    tower_base = _box_ring(tower_hx, tower_hz, tower_base_y)
    for idx in sorted(tower_visible):
        corner = tower_base[idx]
        verticals.append((
            np.array([corner[0], tower_base_y, corner[2]]),
            np.array([corner[0], top_y, corner[2]]),
            "tower",
        ))

    # --- project everything ------------------------------------------------
    all_world = np.vstack([r for r, _ in rings] + [p for p, _, _ in verticals] + [q for _, q, _ in verticals])
    proj_all = _project(all_world, yaw_rad, cam_dist, geom.eye_height_m)

    u_min, v_min = proj_all.min(axis=0)
    u_max, v_max = proj_all.max(axis=0)
    if u_max - u_min <= 1e-9 or v_max - v_min <= 1e-9:
        raise ValueError("degenerate projection")

    # --- fit into the requested frame margins ------------------------------
    # Lines are drawn with thickness and antialiasing, so the *ink* extends
    # beyond the geometric bbox by roughly half a stroke. Inset the fit by that
    # amount so the measured ink respects the requested margin rather than
    # merely the underlying geometry. Without this the top margin lands ~2 px
    # short of 12 % and the guarantee is cosmetic rather than real.
    inset_px = max(ring_thickness, line_thickness) * 0.5 + 1.5
    band_top_px = TOP_SKY_MARGIN_RATIO * canvas_height + inset_px
    band_bottom_px = (1.0 - BOTTOM_STREET_MARGIN_RATIO) * canvas_height - inset_px
    band_h_px = band_bottom_px - band_top_px
    avail_w_px = (1.0 - 2.0 * SIDE_MARGIN_RATIO) * canvas_width

    scale_h = band_h_px / float(v_max - v_min)
    scale_w = avail_w_px / float(u_max - u_min)
    scale = min(scale_h, scale_w)
    fit_bound = "height" if scale_h <= scale_w else "width"

    # Bottom of the building is pinned to the street margin line so the ground
    # plane never floats; if the width constrained the fit, the top margin
    # simply grows, which can only reduce cropping risk.
    def to_px(proj: np.ndarray) -> np.ndarray:
        u = (proj[:, 0] - (u_min + u_max) * 0.5) * scale + canvas_width * 0.5
        v = band_bottom_px - (v_max - proj[:, 1]) * scale
        return np.stack([u, v], axis=1)

    canvas = np.full((canvas_height, canvas_width, 3), 255, dtype=np.uint8)
    strong = (28, 28, 28)

    # --- draw rings --------------------------------------------------------
    drawn_ring_heights: List[float] = []
    for ring_world, kind in rings:
        pts = to_px(_project(ring_world, yaw_rad, cam_dist, geom.eye_height_m))
        edges = podium_edges if kind == "podium" else tower_edges
        for a, b in edges:
            cv2.line(
                canvas,
                (int(round(pts[a][0])), int(round(pts[a][1]))),
                (int(round(pts[b][0])), int(round(pts[b][1]))),
                strong, ring_thickness, cv2.LINE_AA,
            )
        drawn_ring_heights.append(float(ring_world[0, 1]))

    # --- draw verticals ----------------------------------------------------
    for p_world, q_world, kind in verticals:
        p = to_px(_project(p_world[None, :], yaw_rad, cam_dist, geom.eye_height_m))[0]
        q = to_px(_project(q_world[None, :], yaw_rad, cam_dist, geom.eye_height_m))[0]
        colour = strong if kind == "tower" else (70, 70, 70)
        cv2.line(canvas,
                 (int(round(p[0])), int(round(p[1]))),
                 (int(round(q[0])), int(round(q[1]))),
                 colour, line_thickness, cv2.LINE_AA)

    # --- measure the result ------------------------------------------------
    ys, xs = np.where(canvas.min(axis=2) < 250)
    if ys.size == 0:
        raise RuntimeError("scaffold produced no visible geometry")
    ink_top, ink_bottom = int(ys.min()), int(ys.max())
    ink_left, ink_right = int(xs.min()), int(xs.max())

    top_margin = ink_top / float(canvas_height)
    bottom_margin = (canvas_height - 1 - ink_bottom) / float(canvas_height)
    left_margin = ink_left / float(canvas_width)
    right_margin = (canvas_width - 1 - ink_right) / float(canvas_width)

    # The podium/tower junction ring is drawn twice (podium roof edge and tower
    # base are different rectangles), so tiers must be counted over *distinct*
    # ring heights, not over the ring list length.
    distinct_heights = sorted({round(hy, 6) for hy in drawn_ring_heights})
    tier_count = len(distinct_heights) - 1

    ok, buf = cv2.imencode(".png", canvas)
    if not ok:
        raise RuntimeError("PNG encoding failed")
    digest = hashlib.sha256(buf.tobytes()).hexdigest()

    meta: Dict[str, Any] = {
        "kind": "exact_n_story_tower_controlnet",
        "num_floors": int(num_floors),
        "podium_floors": int(podium_floors),
        "tower_floors": int(geom.tower_floors),
        "tier_count": int(tier_count),
        "tier_count_matches_request": bool(tier_count == int(num_floors)),
        "ring_count": len(rings),
        "canvas": [int(canvas_width), int(canvas_height)],
        "total_height_m": round(geom.total_height_m, 3),
        "camera_distance_m": round(cam_dist, 3),
        "yaw_degrees": geom.yaw_degrees,
        "perspective": "two_point",
        "visible_faces": int(visible_faces),
        "horizontal_edges_per_ring": len(tower_edges),
        "fit_bound": fit_bound,
        "margins_actual": {
            "top": round(top_margin, 6),
            "bottom": round(bottom_margin, 6),
            "left": round(left_margin, 6),
            "right": round(right_margin, 6),
        },
        "margins_requested": {
            "top": TOP_SKY_MARGIN_RATIO,
            "bottom": BOTTOM_STREET_MARGIN_RATIO,
            "side": SIDE_MARGIN_RATIO,
        },
        "top_margin_satisfied": bool(top_margin >= TOP_SKY_MARGIN_RATIO - 1e-3),
        "bottom_margin_satisfied": bool(bottom_margin >= BOTTOM_STREET_MARGIN_RATIO - 1e-3),
        "cropped": bool(
            ink_top <= 0 or ink_bottom >= canvas_height - 1
            or ink_left <= 0 or ink_right >= canvas_width - 1
        ),
        "ink_bbox": [ink_left, ink_top, ink_right, ink_bottom],
        "carries_building_identity": False,
        "sha256_png": digest,
    }
    return canvas, meta


# ---------------------------------------------------------------------------
# 3. Day -> night prepass
# ---------------------------------------------------------------------------


def kelvin_to_bgr(kelvin: float) -> Tuple[float, float, float]:
    """Approximate blackbody colour temperature as an OpenCV BGR triple.

    Uses the standard Planckian-locus approximation. Values are 0-255 floats
    suitable for additive/multiplicative lighting maths.
    """
    t = max(1000.0, min(40000.0, float(kelvin))) / 100.0
    if t <= 66.0:
        r = 255.0
    else:
        r = 329.698727446 * ((t - 60.0) ** -0.1332047592)
    if t <= 66.0:
        g = 99.4708025861 * math.log(t) - 161.1195681661
    else:
        g = 288.1221695283 * ((t - 60.0) ** -0.0755148492)
    if t >= 66.0:
        b = 255.0
    elif t <= 19.0:
        b = 0.0
    else:
        b = 138.5177312231 * math.log(t - 10.0) - 305.0447927307
    return (
        float(max(0.0, min(255.0, b))),
        float(max(0.0, min(255.0, g))),
        float(max(0.0, min(255.0, r))),
    )


def _luma(bgr: np.ndarray) -> np.ndarray:
    """BT.709 luma on a float BGR array."""
    return (
        0.0722 * bgr[..., 0]
        + 0.7152 * bgr[..., 1]
        + 0.2126 * bgr[..., 2]
    )


def _as_mask(mask: Optional[np.ndarray], shape: Tuple[int, int]) -> np.ndarray:
    if mask is None:
        return np.zeros(shape, dtype=bool)
    m = np.asarray(mask)
    if m.ndim == 3:
        m = m[..., 0]
    if m.shape != shape:
        raise ValueError("mask shape %r does not match image %r" % (m.shape, shape))
    return m > 0


def synthesize_day_to_night_prepass(
    day_render_bgr: np.ndarray,
    mask_S: np.ndarray,
    mask_O: np.ndarray,
    mask_sky: Optional[np.ndarray] = None,
    min_facade_luminance_floor: float = 0.38,
    *,
    facade_luma_ceiling_ratio: float = 1.0,
    interior_kelvin: float = INTERIOR_GLOW_KELVIN,
    exterior_kelvin: float = EXTERIOR_WASHER_KELVIN,
    ambient_gain: float = 0.42,
    sky_top_bgr: Tuple[float, float, float] = (74.0, 40.0, 22.0),
    sky_bottom_bgr: Tuple[float, float, float] = (46.0, 24.0, 13.0),
    uplight_axes: Tuple[float, ...] = (0.10, 0.34, 0.62, 0.88),
    uplight_strength: float = 0.30,
    eaves_strength: float = 0.28,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Deterministically relight a day render toward blue hour.

    This is the fix for the failure recorded in
    ``ARCHITECTOS_R3_NIGHT_05_DENOISE_ISOLATION_V1.md``: at denoise <= 0.50 the
    daylight sky latent dominates the prompt and the result stays a daylight
    building with lamps added. Removing the daylight sky *before* encoding
    gives the sampler no bright sky to preserve.

    ``min_facade_luminance_floor`` is a *relative* floor: the facade's mean luma
    after the transform must be at least this fraction of its original mean
    luma. If the twilight maths would fall below it, a uniform ambient lift is
    added inside the facade mask until the floor is met. This is what prevents
    the Kontext failure mode of a facade crushed to ``RGB(5,5,8)``.

    Returns:
        ``(night_pre, meta)`` with the achieved luminance ratio and the
        measured light contribution of each layer.
    """
    if day_render_bgr.ndim != 3 or day_render_bgr.shape[2] != 3:
        raise ValueError("day_render_bgr must be an HxWx3 BGR image")
    if not 0.0 <= min_facade_luminance_floor <= 1.0:
        raise ValueError("min_facade_luminance_floor must be within [0, 1]")
    if facade_luma_ceiling_ratio < min_facade_luminance_floor:
        raise ValueError(
            "facade_luma_ceiling_ratio (%r) must be >= min_facade_luminance_floor (%r)"
            % (facade_luma_ceiling_ratio, min_facade_luminance_floor)
        )

    img = day_render_bgr.astype(np.float32)
    h, w = img.shape[:2]
    facade = _as_mask(mask_S, (h, w))
    openings = _as_mask(mask_O, (h, w))
    sky = _as_mask(mask_sky, (h, w))

    facade_luma_before = float(_luma(img)[facade].mean()) if facade.any() else 0.0

    # 1. Twilight ambient: cool, low, blue-dominant.
    night = np.empty_like(img)
    night[..., 0] = img[..., 0] * ambient_gain + 20.0
    night[..., 1] = img[..., 1] * (ambient_gain * 0.72) + 8.0
    night[..., 2] = img[..., 2] * (ambient_gain * 0.55) + 5.0

    # 2. Blue-hour sky gradient, replacing daylight entirely.
    if sky.any():
        ramp = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
        for ch in range(3):
            top = sky_top_bgr[ch]
            bot = sky_bottom_bgr[ch]
            grad = top + (bot - top) * ramp
            plane = np.broadcast_to(grad, (h, w))
            night[..., ch] = np.where(sky, plane, night[..., ch])

    # 3. Warm interior glow through the openings.
    interior_bgr = np.array(kelvin_to_bgr(interior_kelvin), dtype=np.float32)
    interior_added = 0.0
    if openings.any():
        soft = cv2.GaussianBlur(openings.astype(np.float32), (0, 0), 6.0)[..., None]
        soft = np.clip(soft, 0.0, 1.0)
        before = night.copy()
        night = night * (1.0 - 0.80 * soft) + interior_bgr[None, None, :] * (0.80 * soft)
        interior_added = float(np.abs(night - before)[openings].mean())

    # 4. Exterior 3000K wall-washers plus eaves downlights on the facade.
    exterior_bgr = np.array(kelvin_to_bgr(exterior_kelvin), dtype=np.float32)
    uplight_added = 0.0
    eaves_added = 0.0
    if facade.any():
        ys, xs = np.where(facade)
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        bw = max(1, x1 - x0)
        bh = max(1, y1 - y0)

        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

        field = np.zeros((h, w), dtype=np.float32)
        sigma_x = 0.045 * bw
        for rel in uplight_axes:
            cx = x0 + rel * bw
            horiz = np.exp(-((xx - cx) ** 2) / (2.0 * sigma_x ** 2))
            # Wall-washers throw light upward from the base of each tier.
            for tier in range(6):
                fy = y0 + bh * (0.20 + tier * 0.16)
                vert = np.exp(-((yy - fy) ** 2) / (2.0 * (0.07 * bh) ** 2))
                field = np.maximum(field, horiz * vert)

        field *= facade.astype(np.float32)
        field *= (1.0 - openings.astype(np.float32) * 0.65)
        before = night.copy()
        night += field[..., None] * exterior_bgr[None, None, :] * uplight_strength
        uplight_added = float(np.abs(night - before)[facade].mean())

        # Eaves downlights: a narrow bright band under the top tier ring.
        eaves_y = y0 + 0.035 * bh
        eaves = np.exp(-((yy - eaves_y) ** 2) / (2.0 * (0.012 * bh) ** 2))
        eaves *= facade.astype(np.float32)
        before = night.copy()
        night += eaves[..., None] * exterior_bgr[None, None, :] * eaves_strength
        eaves_added = float(np.abs(night - before)[facade].mean())

    night = np.clip(night, 0.0, 255.0)

    # 5. Enforce the non-dark facade floor.
    floor_applied = 0.0
    facade_luma_after = float(_luma(night)[facade].mean()) if facade.any() else 0.0
    required = min_facade_luminance_floor * facade_luma_before
    if facade.any() and facade_luma_after < required:
        lift = required - facade_luma_after
        # Lift proportionally in luma terms; a flat add preserves hue balance
        # better than per-channel scaling when the deficit is small.
        night[facade] = np.clip(night[facade] + lift, 0.0, 255.0)
        floor_applied = lift
        facade_luma_after = float(_luma(night)[facade].mean())

    # 6. Enforce the plausibility ceiling: a night facade whose mean luminance
    #    exceeds the day render is not a night image, it is a day image with
    #    lamps. A floor alone cannot catch that overshoot.
    ceiling_scale = 1.0
    if facade.any() and facade_luma_before > 1e-6:
        ceiling_target = facade_luma_ceiling_ratio * facade_luma_before
        if facade_luma_after > ceiling_target:
            ceiling_scale = ceiling_target / facade_luma_after
            night *= ceiling_scale
            facade_luma_after = float(_luma(night)[facade].mean())

    out = np.clip(night, 0.0, 255.0).astype(np.uint8)

    ratio = (facade_luma_after / facade_luma_before) if facade_luma_before > 1e-6 else None

    sky_luma_before = float(_luma(img)[sky].mean()) if sky.any() else None
    sky_luma_after = float(_luma(out.astype(np.float32))[sky].mean()) if sky.any() else None

    meta: Dict[str, Any] = {
        "kind": "day_to_night_prepass",
        "min_facade_luminance_floor": min_facade_luminance_floor,
        "facade_luma_ceiling_ratio": facade_luma_ceiling_ratio,
        "ceiling_scale_applied": round(ceiling_scale, 6),
        "ceiling_bound": bool(ceiling_scale < 1.0 - 1e-9),
        "facade_pixels": int(facade.sum()),
        "opening_pixels": int(openings.sum()),
        "sky_pixels": int(sky.sum()),
        "facade_luma_before": round(facade_luma_before, 4),
        "facade_luma_after": round(facade_luma_after, 4),
        "facade_luma_ratio": round(ratio, 6) if ratio is not None else None,
        "facade_floor_satisfied": bool(ratio is None or ratio >= min_facade_luminance_floor - 1e-6),
        "facade_not_brighter_than_day": bool(
            ratio is None or ratio <= facade_luma_ceiling_ratio + 1e-6
        ),
        "floor_lift_applied": round(floor_applied, 4),
        "sky_luma_before": round(sky_luma_before, 4) if sky_luma_before is not None else None,
        "sky_luma_after": round(sky_luma_after, 4) if sky_luma_after is not None else None,
        "sky_darkened": bool(
            sky_luma_before is not None and sky_luma_after is not None
            and sky_luma_after < sky_luma_before
        ),
        "interior_kelvin": interior_kelvin,
        "exterior_kelvin": exterior_kelvin,
        "interior_glow_delta": round(interior_added, 4),
        "uplight_delta": round(uplight_added, 4),
        "eaves_delta": round(eaves_added, 4),
        "clipped_pixels": int(((night <= 0.0) | (night >= 255.0)).sum()),
        "source_clipped_pixels": int(
            ((day_render_bgr <= 0) | (day_render_bgr >= 255)).sum()
        ),
        "output_sha256": hashlib.sha256(out.tobytes()).hexdigest(),
    }
    return out, meta


# ---------------------------------------------------------------------------
# 4. Geometry lock
# ---------------------------------------------------------------------------


def lock_night_render_to_day_geometry(
    day_render_bgr: np.ndarray,
    comfy_night_bgr: np.ndarray,
    mask_S: np.ndarray,
    detail_preservation_weight: float = 0.65,
    *,
    low_frequency_sigma: float = 3.0,
    feather_sigma: float = 2.0,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Re-impose the day render's high-frequency geometry on a night render.

    Frequency separation, not masking-by-blending:

    * the night render keeps its *low* frequencies - that is its lighting,
      colour temperature and atmosphere;
    * the day render supplies the *high* frequencies - that is the skylight
      frames, roof gables, mullions, shutters and brick coursing.

    ``detail_preservation_weight`` = 1.0 would copy the day detail exactly;
    0.0 would leave the sampler output untouched. 0.65 keeps the day geometry
    dominant while retaining some of the sampler's own micro-texture.

    Args:
        day_render_bgr: The approved day render (geometry authority).
        comfy_night_bgr: The sampler's night output.
        mask_S: Facade mask; the lock is applied only inside it.
        detail_preservation_weight: Weight of day detail in the mix.
        low_frequency_sigma: Gaussian sigma separating detail from lighting.
        feather_sigma: Edge feather applied to the mask.

    Returns:
        ``(locked_bgr, meta)`` where ``meta`` reports the measured change in
        high-frequency correlation with the day render - the actual claim that
        geometry was preserved, rather than an assertion that it was.
    """
    if not 0.0 <= detail_preservation_weight <= 1.0:
        raise ValueError("detail_preservation_weight must be within [0, 1]")
    if day_render_bgr.shape != comfy_night_bgr.shape:
        raise ValueError(
            "day and night images must share dimensions, got %r vs %r"
            % (day_render_bgr.shape, comfy_night_bgr.shape)
        )
    if day_render_bgr.ndim != 3 or day_render_bgr.shape[2] != 3:
        raise ValueError("inputs must be HxWx3 BGR images")

    day = day_render_bgr.astype(np.float32)
    night = comfy_night_bgr.astype(np.float32)
    h, w = day.shape[:2]
    facade = _as_mask(mask_S, (h, w))

    wgt = float(detail_preservation_weight)

    def split(channel: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        low = cv2.GaussianBlur(channel, (0, 0), low_frequency_sigma)
        return low, channel - low

    rebuilt = np.empty_like(night)
    for ch in range(3):
        day_low, day_high = split(day[..., ch])
        night_low, night_high = split(night[..., ch])
        mixed_high = (1.0 - wgt) * night_high + wgt * day_high
        rebuilt[..., ch] = night_low + mixed_high

    # Feather so the lock does not create a visible seam at the facade edge.
    alpha = facade.astype(np.float32)
    if feather_sigma > 0:
        alpha = cv2.GaussianBlur(alpha, (0, 0), feather_sigma)
    alpha = np.clip(alpha, 0.0, 1.0)[..., None]

    out_f = night * (1.0 - alpha) + np.clip(rebuilt, 0.0, 255.0) * alpha
    out = np.clip(out_f, 0.0, 255.0).astype(np.uint8)

    # --- measured claim ----------------------------------------------------
    def hf(channel: np.ndarray) -> np.ndarray:
        low = cv2.GaussianBlur(channel, (0, 0), low_frequency_sigma)
        return channel - low

    def corr(a: np.ndarray, b: np.ndarray, m: np.ndarray) -> Optional[float]:
        if not m.any():
            return None
        av = a[m] - a[m].mean()
        bv = b[m] - b[m].mean()
        denom = float(np.sqrt((av ** 2).sum() * (bv ** 2).sum()))
        if denom < 1e-9:
            return None
        return float((av * bv).sum() / denom)

    day_hf = _luma(day)
    day_hf = hf(day_hf)
    night_hf = hf(_luma(night))
    out_hf = hf(_luma(out.astype(np.float32)))

    corr_before = corr(night_hf, day_hf, facade)
    corr_after = corr(out_hf, day_hf, facade)

    # Low-frequency identity with the sampler output must survive: this proves
    # the operation preserved lighting rather than replacing the night render.
    lf_before = cv2.GaussianBlur(_luma(night), (0, 0), low_frequency_sigma)
    lf_after = cv2.GaussianBlur(_luma(out.astype(np.float32)), (0, 0), low_frequency_sigma)
    lf_delta = float(np.abs(lf_after - lf_before)[facade].mean()) if facade.any() else 0.0

    meta: Dict[str, Any] = {
        "kind": "night_geometry_lock",
        "detail_preservation_weight": wgt,
        "low_frequency_sigma": low_frequency_sigma,
        "facade_pixels": int(facade.sum()),
        "hf_correlation_with_day_before": None if corr_before is None else round(corr_before, 6),
        "hf_correlation_with_day_after": None if corr_after is None else round(corr_after, 6),
        "hf_correlation_gain": (
            None if corr_before is None or corr_after is None
            else round(corr_after - corr_before, 6)
        ),
        "hf_dominated_by_day": bool(
            corr_after is not None
            and corr_after >= 0.90
            and (corr_before is None or corr_after >= corr_before + 0.20)
        ),
        "exact_detail_copy": bool(wgt >= 0.999),
        "claim_note": (
            "At detail_preservation_weight = 1.0 the sampler contributes no "
            "micro-detail and the day detail dominates completely; measured "
            "correlation still falls slightly short of 1.0 because the "
            "reconstruction re-blurs the night low-frequency band and clips "
            "at the 0-255 bounds. At 0.65 the day detail is deliberately "
            "mixed with the sampler's own texture, so preservation is "
            "dominant, not literally 100%. The measured correlation is the "
            "evidence; do not restate it as an exact-geometry guarantee."
        ),
        "low_frequency_delta_vs_sampler": round(lf_delta, 4),
        "clipped_pixels": int(
            ((out_f <= 0.0) | (out_f >= 255.0)).sum()
        ),
        "output_sha256": hashlib.sha256(out.tobytes()).hexdigest(),
    }
    return out, meta


# ---------------------------------------------------------------------------
# 5. Graph construction
# ---------------------------------------------------------------------------

_CONTROLNET_APPLY = "ControlNetApplyAdvanced"


def attach_controlnet_to_t2i_graph(
    base_workflow: Dict[str, Any],
    control_image_name: str,
    *,
    control_net_name: str = "flux1-dev-controlnet-union-pro-2.0-fp8.safetensors",
    control_node_id: str = "310",
    apply_node_id: str = "311",
    image_node_id: str = "312",
    vae_node_id: str = "205",
    sampler_node_id: str = "210",
    positive_node_id: str = "206",
    negative_node_id: str = "212",
) -> Dict[str, Any]:
    """Insert a ControlNet branch into a text-to-image graph.

    Mirrors the contract already proven in
    ``flux_img2img_dual_conditioned.json``: ``ControlNetApplyAdvanced`` takes
    positive/negative/control_net/image/strength/start_percent/end_percent/vae
    and the sampler reads its outputs ``[0]`` and ``[1]``.

    Raises:
        MissingControlNetNodeError: if the required source nodes are absent.
    """
    wf = deepcopy(base_workflow)
    for nid in (sampler_node_id, positive_node_id, negative_node_id, vae_node_id):
        if nid not in wf:
            raise MissingControlNetNodeError(
                "graph has no node %s required to attach ControlNet" % nid
            )

    wf[control_node_id] = {
        "class_type": "ControlNetLoader",
        "inputs": {"control_net_name": control_net_name},
    }
    wf[image_node_id] = {
        "class_type": "LoadImage",
        "inputs": {"image": control_image_name},
    }
    wf[apply_node_id] = {
        "class_type": _CONTROLNET_APPLY,
        "inputs": {
            "positive": [positive_node_id, 0],
            "negative": [negative_node_id, 0],
            "control_net": [control_node_id, 0],
            "image": [image_node_id, 0],
            "strength": 0.86,
            "start_percent": 0.0,
            "end_percent": 0.88,
            "vae": [vae_node_id, 0],
        },
    }
    sampler_inputs = dict(wf[sampler_node_id].get("inputs", {}))
    sampler_inputs["positive"] = [apply_node_id, 0]
    sampler_inputs["negative"] = [apply_node_id, 1]
    wf[sampler_node_id] = dict(wf[sampler_node_id])
    wf[sampler_node_id]["inputs"] = sampler_inputs
    return wf


def _require(wf: Dict[str, Any], nid: str, field_name: str) -> None:
    node = wf.get(nid)
    if not isinstance(node, dict):
        raise MissingControlNetNodeError("graph has no node %s" % nid)
    if field_name not in node.get("inputs", {}):
        raise MissingControlNetNodeError(
            "node %s has no input %r (class %s)"
            % (nid, field_name, node.get("class_type"))
        )


def build_mode_specific_stage2_workflow(
    base_workflow: Dict[str, Any],
    mode: str,
    positive_prompt: str,
    negative_prompt: str,
    seed: int = 123456789,
    *,
    control_image_name: Optional[str] = None,
    source_image_name: Optional[str] = None,
    control_net_name: str = "flux1-dev-controlnet-union-pro-2.0-fp8.safetensors",
) -> Dict[str, Any]:
    """Configure a graph for one of the v22 modes.

    Supported modes:
        ``MODE_1_TXT2IMG_EXACT_FLOORS`` - denoise 0.96, ControlNet 0.86,
        end_percent 0.88. Requires a control image; if the base graph has no
        ControlNet branch one is attached and the latent stays an
        ``EmptyLatentImage`` (text-to-image, not img2img).
        ``MODE_3_DAY_TO_NIGHT_RELIGHT`` - denoise 0.34, ControlNet 0.96,
        end_percent 1.00. ``source_image_name`` stages the pre-passed night
        image as the img2img source latent; ``control_image_name`` supplies the
        geometry control map.

    Fails closed: a mode that needs ControlNet never silently degrades to an
    unconditioned render.
    """
    wf = deepcopy(base_workflow)

    if mode == MODE_TXT2IMG_EXACT_FLOORS:
        if control_image_name is None:
            raise MissingControlNetNodeError(
                "MODE_1_TXT2IMG_EXACT_FLOORS requires control_image_name"
            )
        if "311" not in wf or wf.get("311", {}).get("class_type") != _CONTROLNET_APPLY:
            wf = attach_controlnet_to_t2i_graph(
                wf, control_image_name, control_net_name=control_net_name
            )
        else:
            wf["312"] = {"class_type": "LoadImage",
                         "inputs": {"image": control_image_name}}
            wf["311"]["inputs"]["image"] = ["312", 0]
        params = TXT2IMG_EXACT_FLOORS_PARAMS
    elif mode == MODE_DAY_TO_NIGHT_RELIGHT:
        params = DAY_TO_NIGHT_RELIGHT_PARAMS
        if control_image_name is not None:
            # A source-latent relight still needs a geometry control map, and
            # the base graph this mode is routed on (`flux_img2img.json`)
            # carries NO ControlNet branch. Without the attach below the
            # `_require` would raise on every real request, so the documented
            # contract ("`control_image_name` supplies the geometry control
            # map") would be unimplementable. The attach is the SAME one MODE_1
            # uses and it is equally fail-closed: a graph without the sampler
            # or the CLIP terminals still raises MissingControlNetNodeError.
            if wf.get("311", {}).get("class_type") != _CONTROLNET_APPLY:
                wf = attach_controlnet_to_t2i_graph(
                    wf, control_image_name, control_net_name=control_net_name
                )
            wf["312"] = {"class_type": "LoadImage",
                         "inputs": {"image": control_image_name}}
            _require(wf, "311", "image")
            wf["311"]["inputs"]["image"] = ["312", 0]
        if source_image_name is not None:
            _require(wf, "300", "image")
            wf["300"]["inputs"]["image"] = source_image_name
    else:
        raise ValueError("unsupported mode %r" % (mode,))

    _require(wf, "206", "text")
    _require(wf, "212", "text")
    _require(wf, "210", "seed")

    wf["206"]["inputs"]["text"] = positive_prompt
    wf["212"]["inputs"]["text"] = negative_prompt
    wf["210"]["inputs"]["seed"] = seed
    wf["210"]["inputs"]["denoise"] = params["denoise"]

    _require(wf, "311", "strength")
    wf["311"]["inputs"]["strength"] = params["controlnet_strength"]
    wf["311"]["inputs"]["start_percent"] = params["controlnet_start_percent"]
    wf["311"]["inputs"]["end_percent"] = params["controlnet_end_percent"]
    wf["_architectos_mode"] = mode
    return wf


# ---------------------------------------------------------------------------
# 6. Small I/O helpers
# ---------------------------------------------------------------------------


def write_png(path: str, image_bgr: np.ndarray) -> str:
    """Write a PNG and return its sha256. Refuses to overwrite."""
    target = pathlib.Path(path)
    if target.exists():
        raise FileExistsError("refusing to overwrite %s" % target)
    target.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", image_bgr)
    if not ok:
        raise RuntimeError("PNG encoding failed")
    target.write_bytes(buf.tobytes())
    return hashlib.sha256(buf.tobytes()).hexdigest()
