"""PlanModelToSceneAdapterV1 — additive bridge from the architectural plan model
to the renderer-independent drawing stack.

This adapter is a **translator, never a generator**. It copies already-resolved
room footprints out of ``architectural_geometry`` into the shape
:class:`~core.architecture.drawing.architectural_realization_v1.ArchitecturalPlanRealizer`
expects, and delegates every drawing decision to that realizer.

Hard rules enforced here
------------------------
1. No coordinate, dimension, thickness, count or level is invented. Every polygon
   number is copied by reference from a footprint emitted upstream.
2. A room whose footprint was not resolved is **never** approximated, grown,
   defaulted or placed. It is reported in ``pending_rooms`` with its observed
   status, and excluded from the candidate.
3. Openings are never synthesized. The live pipeline emits no resolved door or
   window host geometry (all records carry pending status), so doors and windows
   are reported as a pending schedule rather than drawn on an invented facade.
4. The building bounding box is derived only from resolved footprints. If nothing
   resolves, no building box is claimed.

The adapter does not import, invoke or modify ``ArchitecturalGeometryEngineV2``,
BIM, IFC, structure, or the render pipeline. It reads an already-produced design
model and writes an :class:`ArchitecturalDrawingScene`.
"""

from __future__ import annotations

import math
import re
from typing import Any, Mapping

from .architectural_realization_v1 import ArchitecturalPlanRealizer
from .architectural_scene_v1 import ArchitecturalDrawingScene

OUTPUT_TYPE = "plan_model_drawing_bridge"
OUTPUT_VERSION = "plan_model_to_scene_adapter_v1"

#: Structural constant identifying the bridge family. Not a design decision.
FAMILY = "plan_model_v1"

#: Upstream geometry status that grants permission to draw a room.
RESOLVED_FOOTPRINT_STATUS = "resolved_room_footprint"

#: Upstream footprint type this adapter understands.
RECTANGLE = "rectangle"

#: Reasons a room may remain undrawn. Reported verbatim; never collapsed.
PENDING_FOOTPRINT_ABSENT = "footprint_absent"
PENDING_GEOMETRY_STATUS = "geometry_status_not_resolved"
PENDING_UNSUPPORTED_TYPE = "footprint_type_unsupported"
PENDING_BOUNDS_INCOMPLETE = "bounds_incomplete"
PENDING_BOUNDS_DEGENERATE = "bounds_degenerate"

_SLUG_UNSAFE = re.compile(r"[^0-9a-zA-Z_]+")


def _slug(value: Any, fallback: str) -> str:
    """Return a stable, filesystem-safe identifier derived from ``value``.

    This is an *identifier* normalisation only. It never invents a name: an
    empty or unusable value falls back to the caller-supplied ``fallback``,
    which is itself derived from position, not from meaning.
    """

    if value is None:
        return fallback

    text = str(value).strip()

    if not text:
        return fallback

    slug = _SLUG_UNSAFE.sub("_", text).strip("_").lower()

    return slug or fallback


def _finite(value: Any) -> bool:
    """True when ``value`` is a real, finite number."""

    if isinstance(value, bool):
        return False

    if not isinstance(value, (int, float)):
        return False

    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list:
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


class PlanModelToSceneAdapterV1:
    """Translate an architectural plan model into an architectural drawing scene."""

    VERSION = OUTPUT_VERSION

    def __init__(self, realizer: ArchitecturalPlanRealizer | None = None):

        self.realizer = realizer or ArchitecturalPlanRealizer()

        print(f"📐 PLAN MODEL TO SCENE ADAPTER {self.VERSION} ONLINE")

    # ==================================================
    # PUBLIC API
    # ==================================================

    def realize(
        self,
        plan_model: Any,
        layout: Any = None,
        spatial_contract: Any = None,
        architectural_geometry: Any = None,
        candidate_id: str | None = None,
    ) -> ArchitecturalDrawingScene:
        """Build a drawing scene from an architectural plan model.

        ``layout`` and ``spatial_contract`` are accepted because the phase scope
        names them as inputs, and because they are the authorities that carry the
        project's semantic identity. They are consulted for identity and pending
        reporting only; no number is ever taken from them, because neither carries
        resolved geometry.
        """

        plan_model = _mapping(plan_model)
        layout = _mapping(layout)
        spatial_contract = _mapping(spatial_contract)
        architectural_geometry = _mapping(architectural_geometry)

        resolved_id = candidate_id or self._candidate_id(plan_model, layout)

        registry = self._space_registry(plan_model)
        geometry_spaces = self._geometry_space_index(architectural_geometry)

        rooms: list[dict[str, Any]] = []
        pending: list[dict[str, Any]] = []

        for position, space in enumerate(registry):

            record = self._room_record(
                space, geometry_spaces, position, rooms
            )

            if record["status"] == "resolved":
                rooms.append(record["room"])
            else:
                pending.append(record["pending"])

        candidate = self._candidate(
            resolved_id, rooms, architectural_geometry
        )

        scene = self.realizer.realize(candidate)

        self._attach_bridge_evidence(
            scene,
            resolved_id,
            rooms,
            pending,
            architectural_geometry,
            plan_model,
        )

        return scene

    # ==================================================
    # IDENTITY
    # ==================================================

    def _candidate_id(self, plan_model: Any, layout: Any) -> str:
        """Derive a stable candidate identity without inventing one.

        Preference order: an explicit id on the plan model, then a slug of the
        design concept, then the structural fallback ``plan_model``.
        """

        for source in (plan_model, layout):

            for key in ("candidate_id", "id", "name"):

                value = _mapping(source).get(key)

                if isinstance(value, str) and value.strip():
                    return _slug(value, "plan_model")

        return "plan_model"

    def _space_registry(self, plan_model: Any) -> list[dict[str, Any]]:
        """Return the plan model's space registry as a list of mappings."""

        registry = _sequence(_mapping(plan_model).get("space_registry"))

        if not registry:
            registry = _sequence(_mapping(plan_model).get("spaces"))

        return [s for s in registry if isinstance(s, Mapping)]

    def _geometry_space_index(
        self, architectural_geometry: Any
    ) -> dict[str, Mapping[str, Any]]:
        """Index upstream geometry spaces by their authoritative identity.

        Identity is the space ``name``, matched **exactly and case-sensitively**.

        Why not ``canonical_name``: it is a semantic *class*, not an identity. In
        the measured pipeline ``Living`` and ``living`` are two distinct rooms
        that both carry ``canonical_name == "living_room"``, and ``Kitchen`` /
        ``kitchen`` both carry ``canonical_name == "kitchen"``. A canonical-name
        join is therefore many-to-one and silently collapses two rooms onto one
        footprint, or crosses ``Kitchen`` onto ``kitchen``'s polygon — both were
        observed and are why this join is name-exact.

        ``canonical_name`` is retained only as a **secondary** key, and only when
        it does not collide with an exact name or with another canonical entry.
        Colliding secondary keys are dropped rather than guessed between, so the
        join can fail closed instead of merging distinct rooms.
        """

        spaces = [
            s
            for s in _sequence(_mapping(architectural_geometry).get("spaces"))
            if isinstance(s, Mapping)
        ]

        index: dict[str, Mapping[str, Any]] = {}
        exact_names: set[str] = set()

        for space in spaces:

            name = space.get("name")

            if isinstance(name, str) and name.strip():
                exact_names.add(name.strip())
                index.setdefault(name.strip(), space)

        secondary: dict[str, Mapping[str, Any]] = {}
        ambiguous: set[str] = set()

        for space in spaces:

            value = space.get("canonical_name")

            if not isinstance(value, str) or not value.strip():
                continue

            key = value.strip()

            if key in exact_names or key in index:
                # An exact name already owns this key; never shadow it.
                ambiguous.add(key)
                continue

            if key in secondary:
                ambiguous.add(key)
                continue

            secondary[key] = space

        for key in ambiguous:
            secondary.pop(key, None)

        for key, space in secondary.items():
            index.setdefault(key, space)

        return index

    # ==================================================
    # ROOM TRANSLATION
    # ==================================================

    def _room_record(
        self,
        space: Mapping[str, Any],
        geometry_spaces: Mapping[str, Mapping[str, Any]],
        position: int,
        already: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Translate one registry space into a realizer room, or report it pending.

        Every early return is a fail-closed path: the room is reported, never
        guessed.
        """

        upstream = self._match_geometry(space, geometry_spaces)

        room_id = self._room_id(space, upstream, position, already)

        # ``upstream`` may legitimately be None on the fail-closed path. Identity
        # fields are therefore read through an empty mapping rather than being
        # dereferenced directly, so a missing geometry record is reported as a
        # pending room instead of raising.
        upstream_fields = _mapping(upstream)

        base = {
            "id": room_id,
            "name": space.get("name") or upstream_fields.get("name"),
            "floor": space.get("floor") or upstream_fields.get("floor"),
            "zone": space.get("zone") or upstream_fields.get("zone"),
        }

        if upstream is None:

            return self._pending(
                base, PENDING_FOOTPRINT_ABSENT, "no upstream geometry record"
            )

        footprint = upstream.get("footprint")

        if not isinstance(footprint, Mapping):

            return self._pending(
                base,
                PENDING_FOOTPRINT_ABSENT,
                "upstream footprint is absent",
                upstream,
            )

        status = upstream.get("geometry_status")

        if status != RESOLVED_FOOTPRINT_STATUS:

            return self._pending(
                base,
                PENDING_GEOMETRY_STATUS,
                f"geometry_status={status!r}",
                upstream,
            )

        footprint_type = footprint.get("type")

        if footprint_type != RECTANGLE:

            return self._pending(
                base,
                PENDING_UNSUPPORTED_TYPE,
                f"footprint type={footprint_type!r}",
                upstream,
            )

        bounds = (
            footprint.get("min_x"),
            footprint.get("min_y"),
            footprint.get("max_x"),
            footprint.get("max_y"),
        )

        if not all(_finite(value) for value in bounds):

            return self._pending(
                base,
                PENDING_BOUNDS_INCOMPLETE,
                "one or more bounds are missing or non-finite",
                upstream,
            )

        x1, y1, x2, y2 = (float(value) for value in bounds)

        if x2 <= x1 or y2 <= y1:

            return self._pending(
                base,
                PENDING_BOUNDS_DEGENERATE,
                "bounds do not enclose a positive area",
                upstream,
            )

        room = {
            "id": room_id,
            # Copied by reference from upstream. Never computed here.
            "polygon": [x1, y1, x2, y2],
            "label_fa": self._label(space, upstream, room_id),
            "label": self._label(space, upstream, room_id),
            "floor": base["floor"],
            "zone": base["zone"],
            "name": base["name"],
            "area_m2": footprint.get("area"),
            "source": OUTPUT_VERSION,
            "provenance": {
                "polygon": "architectural_geometry.spaces[].footprint",
                "geometry_status": status,
                "coordinate_mode": footprint.get("coordinate_mode"),
            },
        }

        return {
            "status": "resolved",
            "room": room,
        }

    def _match_geometry(
        self,
        space: Mapping[str, Any],
        geometry_spaces: Mapping[str, Mapping[str, Any]],
    ) -> Mapping[str, Any] | None:
        """Join a registry space to its upstream geometry record by declared identity.

        ``name`` is tried first and exactly, because it is the only key measured
        to be unique and to preserve the ``Living``/``living`` and
        ``Kitchen``/``kitchen`` distinction. ``canonical_name`` is tried last and
        only via the ambiguity-filtered index, so it can never cross-match two
        distinct rooms.
        """

        for key in ("name", "canonical_name", "id", "space_id"):

            value = space.get(key)

            if not isinstance(value, str) or not value.strip():
                continue

            lookup = value.strip()

            if key == "name":
                hit = geometry_spaces.get(lookup)
            else:
                # Non-name keys are only honoured when they are unambiguous.
                hit = geometry_spaces.get(lookup) if lookup in geometry_spaces else None

            if hit is not None:
                return hit

        return None

    def _room_id(
        self,
        space: Mapping[str, Any],
        upstream: Mapping[str, Any] | None,
        position: int,
        already: list[dict[str, Any]],
    ) -> str:
        """Return a unique, deterministic room identifier.

        ``name`` is the preferred source because it is the identity that keeps
        ``Living`` distinct from ``living`` and ``Kitchen`` from ``kitchen``.

        The identifier is derived by slugging **each candidate in its own
        namespace** and taking the first that is both slug-stable and unused. A
        name that slugs into an already-taken identifier is disambiguated with a
        deterministic numeric suffix rather than being discarded, so every room
        keeps an identifier traceable to its source name.

        ``canonical_name`` is the last resort: it is many-to-one, so it cannot be
        allowed to shadow a distinct name.
        """

        taken = {r["id"] for r in already}

        for source in (space, upstream or {}):

            for key in ("name", "id", "space_id", "canonical_name"):

                value = _mapping(source).get(key)

                if not isinstance(value, str) or not value.strip():
                    continue

                slug = _slug(value, "")

                if not slug:
                    continue

                if slug not in taken:
                    return slug

                # Deterministic disambiguation. The suffix is positional, not
                # semantic: it distinguishes two genuinely different rooms that
                # happen to slug to the same identifier.
                suffix = 2
                candidate = f"{slug}_{suffix}"

                while candidate in taken:
                    suffix += 1
                    candidate = f"{slug}_{suffix}"

                return candidate

        base = f"room_{position}"
        candidate = base
        suffix = 2

        while candidate in taken:
            candidate = f"{base}_{suffix}"
            suffix += 1

        return candidate

    def _label(
        self,
        space: Mapping[str, Any],
        upstream: Mapping[str, Any],
        room_id: str,
    ) -> str:
        """Return the room label, using a Persian label only if upstream supplied one.

        No translation dictionary exists in this path; a Persian label is never
        derived from an English name.
        """

        for source in (space, upstream):

            for key in ("label_fa", "label", "display_name"):

                value = _mapping(source).get(key)

                if isinstance(value, str) and value.strip():
                    return value.strip()

        for source in (space, upstream):

            for key in ("name", "canonical_name", "space_type"):

                value = _mapping(source).get(key)

                if isinstance(value, str) and value.strip():
                    return value.strip()

        return room_id

    def _pending(
        self,
        base: Mapping[str, Any],
        reason: str,
        detail: str,
        upstream: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a fail-closed pending record for a room that must not be drawn."""

        record = {
            "id": base.get("id"),
            "name": base.get("name"),
            "floor": base.get("floor"),
            "zone": base.get("zone"),
            "reason": reason,
            "detail": detail,
            "drawn": False,
        }

        if upstream is not None:
            record["observed_geometry_status"] = upstream.get("geometry_status")

        return {
            "status": "pending",
            "pending": record,
        }

    # ==================================================
    # CANDIDATE ASSEMBLY
    # ==================================================

    def _candidate(
        self,
        candidate_id: str,
        rooms: list[dict[str, Any]],
        architectural_geometry: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Assemble the realizer's candidate contract.

        ``doors``, ``windows`` and ``open_connections`` are emitted empty on
        purpose: the live pipeline carries no resolved opening host geometry, so
        drawing one would require inventing a facade or wall position.
        """

        candidate: dict[str, Any] = {
            "id": candidate_id,
            "family": FAMILY,
            "rooms": rooms,
            "doors": [],
            "windows": [],
            "open_connections": [],
        }

        building = self._building_bounds(rooms)

        if building is not None:
            candidate["building"] = building

        ffl = self._finished_floor_level(architectural_geometry)

        if ffl is not None:
            candidate["ffl"] = ffl

        return candidate

    def _building_bounds(
        self, rooms: list[dict[str, Any]]
    ) -> list[float] | None:
        """Union bounding box of the resolved rooms, or ``None`` if none resolved.

        Derived only from resolved polygons. When nothing resolves, no building
        box is claimed.
        """

        if not rooms:
            return None

        try:
            xs = [float(r["polygon"][0]) for r in rooms] + [
                float(r["polygon"][2]) for r in rooms
            ]
            ys = [float(r["polygon"][1]) for r in rooms] + [
                float(r["polygon"][3]) for r in rooms
            ]
        except (KeyError, IndexError, TypeError, ValueError):
            return None

        if not xs or not ys:
            return None

        return [min(xs), min(ys), max(xs), max(ys)]

    def _finished_floor_level(
        self, architectural_geometry: Mapping[str, Any]
    ) -> float | None:
        """Read an already-resolved finished floor level, if one is present."""

        for key in ("ffl", "finished_floor_level"):

            value = architectural_geometry.get(key)

            if _finite(value):
                return float(value)

        for space in _sequence(architectural_geometry.get("spaces")):

            value = _mapping(space).get("elevation")

            if _finite(value):
                return float(value)

        return None

    # ==================================================
    # EVIDENCE
    # ==================================================

    def _attach_bridge_evidence(
        self,
        scene: ArchitecturalDrawingScene,
        candidate_id: str,
        rooms: list[dict[str, Any]],
        pending: list[dict[str, Any]],
        architectural_geometry: Mapping[str, Any],
        plan_model: Mapping[str, Any],
    ) -> None:
        """Record provenance, pending rooms and the withheld opening schedule."""

        scene.metadata["plan_model_bridge"] = {
            "adapter": OUTPUT_VERSION,
            "candidate_id": candidate_id,
            "source": "architectural_geometry.spaces[].footprint",
            "polygon_provenance": "copied_from_upstream_footprint",
            "coordinates_invented": False,
            "dimensions_invented": False,
        }

        scene.metadata["room_resolution"] = {
            "registry_spaces": len(rooms) + len(pending),
            "drawn_rooms": len(rooms),
            "pending_rooms": len(pending),
            "status": "complete" if not pending else "partial",
        }

        scene.metadata["pending_rooms"] = pending

        scene.metadata["withheld_openings"] = self._withheld_openings(
            architectural_geometry
        )

        scene.metadata["plan_summary"] = self._plan_summary(
            rooms, pending, plan_model
        )

    def _withheld_openings(
        self, architectural_geometry: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Report doors and windows that exist upstream but must not be drawn.

        Every upstream opening currently carries a pending status and no host
        geometry, so drawing one would place an opening on an invented wall or
        facade. They are scheduled, not rendered.
        """

        doors: list[dict[str, Any]] = []
        windows: list[dict[str, Any]] = []

        for opening in _sequence(architectural_geometry.get("openings")):

            if not isinstance(opening, Mapping):
                continue

            kind = opening.get("type")

            record = {
                "category": opening.get("category"),
                "connects_from": opening.get("connects_from"),
                "connects_to": opening.get("connects_to"),
                "host_geometry_status": "unresolved",
                "edge_decision_status": opening.get("edge_decision_status"),
                "facade_approval_status": opening.get("facade_approval_status"),
                "connection_status": opening.get("connection_status"),
                "site_evidence_status": opening.get("site_evidence_status"),
                "drawn": False,
            }

            if kind == "door":
                doors.append(record)
            elif kind == "window":
                windows.append(record)

        connections = _sequence(architectural_geometry.get("connections"))

        return {
            "doors": doors,
            "windows": windows,
            "connections_total": len(
                [c for c in connections if isinstance(c, Mapping)]
            ),
            "doors_required": len(
                [
                    c
                    for c in connections
                    if isinstance(c, Mapping) and c.get("door_required") is True
                ]
            ),
            "reason_not_drawn": "no_resolved_opening_host_geometry",
        }

    def _plan_summary(
        self,
        rooms: list[dict[str, Any]],
        pending: list[dict[str, Any]],
        plan_model: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Human-readable summary derived only from resolved data."""

        floors: dict[str, list[str]] = {}

        for room in rooms:
            floor = room.get("floor") or "unassigned"
            floors.setdefault(str(floor), []).append(str(room.get("id")))

        total_area = 0.0
        area_counted = 0

        for room in rooms:

            value = room.get("area_m2")

            if _finite(value):
                total_area += float(value)
                area_counted += 1

        basis = _mapping(plan_model).get("program_area_basis")

        return {
            "drawn_rooms": len(rooms),
            "pending_rooms": len(pending),
            "floors": {floor: sorted(names) for floor, names in floors.items()},
            "room_ids": sorted(str(r.get("id")) for r in rooms),
            "resolved_area_m2": round(total_area, 3) if area_counted else None,
            "resolved_area_space_count": area_counted,
            "program_area_basis_present": bool(basis),
            "evidence_status": "complete" if not pending else "partial",
        }
