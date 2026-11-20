"""Pure upper-structure geometry measurement and agreement gate (Phase 3D-S).

Answers exactly one question: does this asset's measured geometry agree with an
expected geometry direction?

It does NOT answer what the asset's semantic forward direction is. Geometry is a
consistency gate only - it never originates a semantic forward direction.

The metric is the Upper-Region Horizontal Centroid Offset (URHCO) already
validated in Phase 3D-O / 3D-Q: raw meshes are Y-up, so the top 25 % of the raw
Y range is taken and its horizontal centroid is compared with the horizontal
bbox centre, normalised by the horizontal dimensions.

This module is pure and filesystem-free: it consumes already-loaded raw
vertices. No OBJ reading, no registry, no vertex transformation, no rendering.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from core.asset.mesh_transform_spec import FORWARD_AXES, GEOMETRY_EVIDENCE_STATES


UPPER_STRUCTURE_TOP_FRACTION = 0.25
# Default observability threshold from the Phase 3D-O / 3D-Q audits: below this
# there is no distinct upper directional structure.
UPPER_STRUCTURE_THRESHOLD = 0.02

UPPER_STRUCTURE_AXES = ("X", "Z")
UPPER_STRUCTURE_SIGNS = ("+", "-")

GEOMETRY_GATE_AGREED = "agreed"
GEOMETRY_GATE_DISAGREED = "disagreed"
GEOMETRY_GATE_NOT_EVALUATED = "not_evaluated"

GEOMETRY_EVIDENCE_KEYS = (
    "state",
    "axis",
    "sign",
    "offset_x",
    "offset_z",
    "magnitude",
    "threshold",
)

_EPSILON = 1e-9


def _finite_scalar(value, label):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a real number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a real number")
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")

    return number


def _validate_vertices(vertices_xyz):
    """Validate already-loaded raw vertices. Never mutates the input."""

    if isinstance(vertices_xyz, (str, bytes)) or not isinstance(
        vertices_xyz, Sequence
    ):
        raise ValueError(
            "vertices_xyz must be a sequence of three-value vertices"
        )
    if len(vertices_xyz) == 0:
        raise ValueError("vertices_xyz must not be empty")

    cleaned = []
    for index, vertex in enumerate(vertices_xyz):
        if (
            isinstance(vertex, (str, bytes))
            or not isinstance(vertex, Sequence)
            or len(vertex) != 3
        ):
            raise ValueError(
                f"vertex at index {index} must contain three values"
            )
        values = []
        for value in vertex:
            number = _finite_scalar(value, f"vertex at index {index}")
            values.append(number)
        cleaned.append(values)

    return cleaned


def _validate_geometry_evidence(evidence):
    """Validate a geometry evidence mapping, including caller-supplied ones."""

    if not isinstance(evidence, Mapping):
        raise ValueError("geometry evidence must be a mapping")

    unknown = set(evidence) - set(GEOMETRY_EVIDENCE_KEYS)
    if unknown:
        raise ValueError(
            "unknown geometry evidence key(s): " + ", ".join(sorted(unknown))
        )

    state = evidence.get("state")
    if state not in GEOMETRY_EVIDENCE_STATES:
        raise ValueError(
            "geometry evidence state must be one of: "
            + ", ".join(GEOMETRY_EVIDENCE_STATES)
        )

    axis = evidence.get("axis")
    sign = evidence.get("sign")
    if state == "observable":
        if axis not in UPPER_STRUCTURE_AXES:
            raise ValueError(
                "observable geometry evidence requires an axis in "
                + ", ".join(UPPER_STRUCTURE_AXES)
            )
        if sign not in UPPER_STRUCTURE_SIGNS:
            raise ValueError(
                "observable geometry evidence requires a sign in "
                + ", ".join(UPPER_STRUCTURE_SIGNS)
            )
    elif axis is not None or sign is not None:
        raise ValueError(
            f"geometry evidence state {state!r} requires a null axis and sign"
        )

    threshold = _finite_scalar(
        evidence.get("threshold"), "geometry evidence threshold"
    )
    if threshold < 0.0:
        raise ValueError("geometry evidence threshold must be non-negative")

    return {
        "state": state,
        "axis": axis,
        "sign": sign,
        "offset_x": _finite_scalar(
            evidence.get("offset_x"), "geometry evidence offset_x"
        ),
        "offset_z": _finite_scalar(
            evidence.get("offset_z"), "geometry evidence offset_z"
        ),
        "magnitude": _finite_scalar(
            evidence.get("magnitude"), "geometry evidence magnitude"
        ),
        "threshold": threshold,
    }


def measure_upper_structure(
    vertices_xyz,
    top_fraction=UPPER_STRUCTURE_TOP_FRACTION,
    threshold=UPPER_STRUCTURE_THRESHOLD,
):
    """Measure the upper-region horizontal centroid offset (URHCO).

    Returns ``observable`` or ``unobservable`` geometry evidence. It never
    returns ``ambiguous``: ambiguity is a family-level property, not something a
    single mesh measurement can establish. It never returns a semantic forward
    direction, a phi value, or a matrix.
    """

    if isinstance(top_fraction, bool) or not isinstance(top_fraction, (int, float)):
        raise ValueError("top_fraction must be a real number in (0, 1)")
    top_fraction = float(top_fraction)
    if not 0.0 < top_fraction < 1.0:
        raise ValueError("top_fraction must be a real number in (0, 1)")

    threshold = _finite_scalar(threshold, "threshold")
    if threshold < 0.0:
        raise ValueError("threshold must be non-negative")

    vertices = _validate_vertices(vertices_xyz)

    minimum = [min(vertex[index] for vertex in vertices) for index in range(3)]
    maximum = [max(vertex[index] for vertex in vertices) for index in range(3)]
    dims = [maximum[index] - minimum[index] for index in range(3)]
    center = [
        (maximum[index] + minimum[index]) / 2.0 for index in range(3)
    ]

    cut = minimum[1] + (1.0 - top_fraction) * max(dims[1], _EPSILON)
    top = [vertex for vertex in vertices if vertex[1] >= cut]
    if not top:
        # Unreachable in practice: the y maximum always satisfies the cut.
        top = [vertex for vertex in vertices if vertex[1] == maximum[1]]

    top_count = len(top)
    top_mean_x = sum(vertex[0] for vertex in top) / top_count
    top_mean_z = sum(vertex[2] for vertex in top) / top_count

    offset_x = (top_mean_x - center[0]) / max(dims[0], _EPSILON)
    offset_z = (top_mean_z - center[2]) / max(dims[2], _EPSILON)
    magnitude = max(abs(offset_x), abs(offset_z))

    if magnitude < threshold:
        axis = None
        sign = None
        state = "unobservable"
    else:
        axis = "X" if abs(offset_x) > abs(offset_z) else "Z"
        value = offset_x if axis == "X" else offset_z
        sign = "+" if value > 0.0 else "-"
        state = "observable"

    return {
        "state": state,
        "axis": axis,
        "sign": sign,
        "offset_x": offset_x,
        "offset_z": offset_z,
        "magnitude": magnitude,
        "threshold": threshold,
    }


def evaluate_geometry_agreement(evidence, expected_direction):
    """Compare measured geometry evidence against an expected direction.

    Returns only ``agreed``, ``disagreed`` or ``not_evaluated``. No alternative
    direction is ever inferred.
    """

    if expected_direction not in FORWARD_AXES:
        raise ValueError(
            "expected_direction must be one of: " + ", ".join(FORWARD_AXES)
        )

    checked = _validate_geometry_evidence(evidence)
    if checked["state"] != "observable":
        return GEOMETRY_GATE_NOT_EVALUATED

    # Direction tokens are sign-first ("-Z"), matching FORWARD_AXES.
    measured = f"{checked['sign']}{checked['axis']}"

    return (
        GEOMETRY_GATE_AGREED
        if measured == expected_direction
        else GEOMETRY_GATE_DISAGREED
    )
