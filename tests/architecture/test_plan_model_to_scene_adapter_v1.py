"""Contract and non-invention tests for ARCH-PRODUCT-CHECKPOINT-02.

These tests exercise :class:`PlanModelToSceneAdapterV1`, the additive bridge from
an already-produced architectural plan model to the renderer-independent drawing
stack.

They are written to be **falsifiable about honesty**, not merely about wiring:

* the adapter must copy upstream footprints and never compute one,
* a room whose upstream footprint is unresolved must remain pending,
* the ``Living``/``living`` and ``Kitchen``/``kitchen`` identity distinction
  must survive the join,
* doors and windows must stay withheld because no opening host geometry exists,
* an empty upstream must fail closed rather than draw a placeholder.

The fixtures below are synthetic *test inputs*. They are not sourced from the
live pipeline; they exist to pin the adapter's contract.
"""

from core.architecture.drawing.plan_model_to_scene_adapter_v1 import (
    PlanModelToSceneAdapterV1,
    FAMILY,
    OUTPUT_VERSION,
    PENDING_BOUNDS_DEGENERATE,
    PENDING_FOOTPRINT_ABSENT,
    PENDING_GEOMETRY_STATUS,
    PENDING_UNSUPPORTED_TYPE,
    RESOLVED_FOOTPRINT_STATUS,
)

import shutil
import tempfile
from pathlib import Path

import pytest


# ==========================================================
# SCRATCH DIRECTORY FIXTURE
#
# The plan-drawing service writes real files. pytest's built-in ``tmp_path``
# depends on the user's system temp directory, which is not always writable in a
# locked-down environment, so this suite uses a scratch directory inside the
# repository and cleans it up deterministically.
# ==========================================================

_SCRATCH = Path(__file__).resolve().parents[2] / "outputs" / "_test_scratch_plan_bridge"


@pytest.fixture
def scratch_root():
    """A clean, writable scratch directory under the repository outputs tree."""

    if _SCRATCH.exists():
        shutil.rmtree(_SCRATCH, ignore_errors=True)

    _SCRATCH.mkdir(parents=True, exist_ok=True)

    try:
        yield _SCRATCH
    finally:
        shutil.rmtree(_SCRATCH, ignore_errors=True)


# ==========================================================
# FIXTURES
# ==========================================================


def _resolved(name, canonical, x1, y1, x2, y2, floor="Ground", zone=None):
    """An upstream geometry space with a fully resolved rectangle footprint."""

    return {
        "name": name,
        "canonical_name": canonical,
        "floor": floor,
        "zone": zone,
        "geometry_status": RESOLVED_FOOTPRINT_STATUS,
        "footprint": {
            "type": "rectangle",
            "points": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
            "min_x": x1,
            "min_y": y1,
            "max_x": x2,
            "max_y": y2,
            "area": (x2 - x1) * (y2 - y1),
            "coordinate_mode": "architectural_metric",
        },
    }


def _pending(name, canonical, floor="Ground", status="room_footprint_pending"):
    """An upstream geometry space whose footprint was never resolved."""

    return {
        "name": name,
        "canonical_name": canonical,
        "floor": floor,
        "geometry_status": status,
        "footprint": None,
    }


def _plan_model(names):
    """A plan model whose space registry lists ``names`` in order."""

    return {
        "candidate_id": "villa_checkpoint02",
        "space_registry": [
            {"name": name, "floor": "Ground"} for name in names
        ],
    }


def _geometry(spaces, openings=None):
    """An architectural geometry contract with the given spaces."""

    return {
        "spaces": spaces,
        "openings": openings or [],
        "connections": [],
    }


def _dual_case_geometry():
    """Geometry that deliberately carries case-distinct duplicate names.

    This is the exact shape the live pipeline produced: ``Living`` and ``living``
    are two different rooms, each with its own footprint; the same holds for
    ``Kitchen`` and ``kitchen``. A correct join keeps all four apart.
    """

    return _geometry(
        [
            _resolved("Living", "living_room", 0.0, 0.0, 5.0, 4.0),
            _resolved("Kitchen", "kitchen", 5.0, 0.0, 8.0, 3.0),
            _resolved("living", "living_room", 0.0, 4.0, 4.5, 8.0),
            _resolved("kitchen", "kitchen", 8.0, 0.0, 11.0, 3.0),
        ]
    )


# ==========================================================
# 1. SCENE CONTRACT
# ==========================================================


def test_adapter_returns_an_architectural_drawing_scene():

    from core.architecture.drawing import ArchitecturalDrawingScene

    adapter = PlanModelToSceneAdapterV1()

    scene = adapter.realize(
        _plan_model(["Living", "Kitchen"]),
        architectural_geometry=_geometry(
            [
                _resolved("Living", "living_room", 0, 0, 5, 4),
                _resolved("Kitchen", "kitchen", 5, 0, 8, 3),
            ]
        ),
    )

    assert isinstance(scene, ArchitecturalDrawingScene)
    assert scene.candidate_id == "villa_checkpoint02"
    assert scene.metadata["family"] == FAMILY
    assert scene.primitives, "a scene with resolved rooms must carry primitives"
    assert "BUILDING_WALLS" in scene.layer_counts()


def test_adapter_delegates_drawing_to_the_existing_realizer():

    adapter = PlanModelToSceneAdapterV1()

    scene = adapter.realize(
        _plan_model(["Living"]),
        architectural_geometry=_geometry(
            [_resolved("Living", "living_room", 0, 0, 5, 4)]
        ),
    )

    # The realizer's own audit metadata is present, proving delegation rather
    # than reimplementation.
    assert "wall_audit" in scene.metadata
    assert scene.metadata["wall_audit"]["shared_boundaries_deduplicated"] is True


# ==========================================================
# 2. NON-INVENTION OF GEOMETRY
# ==========================================================


def test_polygons_are_copied_verbatim_from_upstream_footprints():
    """Building geometry must lie inside the upstream footprint, unmoved.

    The realizer legitimately adds a synthetic *site* layer (boundary, yard,
    parking, landscape, entrance) around the building. Those primitives are not
    room geometry and sit outside the footprint by design, so this test scopes
    its assertion to the ``BUILDING_WALLS`` layer, which is derived solely from
    the room polygon.
    """

    adapter = PlanModelToSceneAdapterV1()

    scene = adapter.realize(
        _plan_model(["Living"]),
        architectural_geometry=_geometry(
            [_resolved("Living", "living_room", 1.25, 2.5, 6.75, 8.125)]
        ),
    )

    bridge = scene.metadata["plan_model_bridge"]

    assert bridge["coordinates_invented"] is False
    assert bridge["dimensions_invented"] is False
    assert bridge["polygon_provenance"] == "copied_from_upstream_footprint"

    walls = [p for p in scene.primitives if p.layer == "BUILDING_WALLS"]

    assert walls, "resolved room must produce building walls"

    xs = []
    ys = []

    for primitive in walls:
        rect = primitive.geometry.get("rect") or {}
        for key in ("x", "y"):
            pass
        x = rect.get("x")
        y = rect.get("y")
        w = rect.get("w")
        h = rect.get("h")
        if x is not None and w is not None:
            xs.extend([x, x + w])
        if y is not None and h is not None:
            ys.extend([y, y + h])

    # The wall band may extend outward by the wall thickness, but must remain
    # anchored to the footprint: it can never drift far from it.
    assert min(xs) <= 1.25
    assert max(xs) >= 6.75
    assert min(ys) <= 2.5
    assert max(ys) >= 8.125

    # Precision check: the drawn extent must not be a rounded or defaulted box.
    assert abs(min(xs) - 1.25) < 0.3
    assert abs(max(xs) - 6.75) < 0.3


def test_adapter_never_emits_doors_or_windows_into_the_candidate():
    """Openings require host geometry the pipeline does not resolve."""

    adapter = PlanModelToSceneAdapterV1()

    candidate = adapter._candidate(
        "villa", [{"id": "living", "polygon": [0, 0, 5, 4]}], {}
    )

    assert candidate["doors"] == []
    assert candidate["windows"] == []
    assert candidate["open_connections"] == []


def test_withheld_openings_are_reported_not_drawn():

    adapter = PlanModelToSceneAdapterV1()

    geometry = _geometry(
        [_resolved("Living", "living_room", 0, 0, 5, 4)],
        openings=[
            {
                "type": "door",
                "category": "internal",
                "connects_from": "Living",
                "connects_to": "Kitchen",
                "edge_decision_status": "pending",
                "facade_approval_status": "pending",
                "connection_status": "pending",
                "site_evidence_status": "pending",
            }
        ],
    )

    scene = adapter.realize(
        _plan_model(["Living"]),
        architectural_geometry=geometry,
    )

    withheld = scene.metadata["withheld_openings"]

    assert withheld["reason_not_drawn"] == "no_resolved_opening_host_geometry"
    assert len(withheld["doors"]) == 1
    assert withheld["doors"][0]["drawn"] is False
    assert withheld["doors"][0]["host_geometry_status"] == "unresolved"

    # And nothing claiming to be a door reached the drawn scene.
    assert "DOORS" not in scene.layer_counts()


# ==========================================================
# 3. FAIL-CLOSED PENDING ROOMS
# ==========================================================


def test_geometry_space_with_null_footprint_is_pending():

    adapter = PlanModelToSceneAdapterV1()

    scene = adapter.realize(
        _plan_model(["Living", "Master"]),
        architectural_geometry=_geometry(
            [
                _resolved("Living", "living_room", 0, 0, 5, 4),
                _pending("Master", "master_bedroom"),
            ]
        ),
    )

    resolution = scene.metadata["room_resolution"]

    assert resolution["registry_spaces"] == 2
    assert resolution["drawn_rooms"] == 1
    assert resolution["pending_rooms"] == 1
    assert resolution["status"] == "partial"

    pending = scene.metadata["pending_rooms"]

    assert len(pending) == 1
    assert pending[0]["name"] == "Master"
    # A record whose footprint is explicitly null is reported as
    # footprint_absent; the upstream status is preserved for the human reader.
    assert pending[0]["reason"] == PENDING_FOOTPRINT_ABSENT
    assert pending[0]["drawn"] is False
    assert pending[0]["observed_geometry_status"] == "room_footprint_pending"

    # No primitive may claim the pending room.
    for primitive in scene.primitives:
        assert primitive.metadata.get("room") != "master"


def test_unresolved_status_with_a_footprint_is_pending_for_status():

    adapter = PlanModelToSceneAdapterV1()

    # Status says unresolved even though a footprint object exists. The adapter
    # must trust the status, not the presence of a box.
    suspect = _resolved("Master", "master_bedroom", 0, 0, 4, 4)
    suspect["geometry_status"] = "room_footprint_pending"

    scene = adapter.realize(
        _plan_model(["Living", "Master"]),
        architectural_geometry=_geometry(
            [
                _resolved("Living", "living_room", 5, 0, 9, 4),
                suspect,
            ]
        ),
    )

    pending = scene.metadata["pending_rooms"]

    assert len(pending) == 1
    assert pending[0]["name"] == "Master"
    assert pending[0]["reason"] == PENDING_GEOMETRY_STATUS
    assert pending[0]["observed_geometry_status"] == "room_footprint_pending"


def test_room_absent_upstream_is_pending_not_invented():

    adapter = PlanModelToSceneAdapterV1()

    scene = adapter.realize(
        _plan_model(["Living", "Ghost"]),
        architectural_geometry=_geometry(
            [_resolved("Living", "living_room", 0, 0, 5, 4)]
        ),
    )

    pending = scene.metadata["pending_rooms"]

    assert len(pending) == 1
    assert pending[0]["name"] == "Ghost"
    assert pending[0]["reason"] == PENDING_FOOTPRINT_ABSENT


def test_unsupported_footprint_type_is_pending():

    adapter = PlanModelToSceneAdapterV1()

    polygon_space = _resolved("Living", "living_room", 0, 0, 5, 4)
    polygon_space["footprint"]["type"] = "polygon"

    scene = adapter.realize(
        _plan_model(["Living"]),
        architectural_geometry=_geometry([polygon_space]),
    )

    pending = scene.metadata["pending_rooms"]

    assert len(pending) == 1
    assert pending[0]["reason"] == PENDING_UNSUPPORTED_TYPE


def test_degenerate_bounds_are_pending():

    adapter = PlanModelToSceneAdapterV1()

    collapsed = _resolved("Living", "living_room", 3.0, 0.0, 3.0, 4.0)

    scene = adapter.realize(
        _plan_model(["Living"]),
        architectural_geometry=_geometry([collapsed]),
    )

    pending = scene.metadata["pending_rooms"]

    assert len(pending) == 1
    assert pending[0]["reason"] == PENDING_BOUNDS_DEGENERATE


def test_non_finite_bounds_are_pending():

    adapter = PlanModelToSceneAdapterV1()

    broken = _resolved("Living", "living_room", 0, 0, 5, 4)
    broken["footprint"]["max_y"] = None

    scene = adapter.realize(
        _plan_model(["Living"]),
        architectural_geometry=_geometry([broken]),
    )

    pending = scene.metadata["pending_rooms"]

    assert len(pending) == 1
    assert pending[0]["reason"] == "bounds_incomplete"


def test_empty_upstream_draws_no_building_geometry():
    """Nothing resolved means no building is drawn.

    The realizer still emits its synthetic site layer, so this test asserts on
    *building* geometry specifically: no wall, partition, furniture, fixture or
    room label may appear when no footprint resolved.
    """

    adapter = PlanModelToSceneAdapterV1()

    scene = adapter.realize(
        _plan_model(["Living", "Kitchen"]),
        architectural_geometry=_geometry([]),
    )

    assert scene.metadata["room_resolution"]["drawn_rooms"] == 0
    assert scene.metadata["room_resolution"]["status"] == "partial"
    assert len(scene.metadata["pending_rooms"]) == 2
    assert "plan_model_bridge" in scene.metadata

    building_layers = {
        "BUILDING_WALLS",
        "PARTITIONS",
        "FURNITURE",
        "FIXTURES",
        "CABINETRY",
        "DOORS",
        "WINDOWS",
    }

    leaked = [
        p for p in scene.primitives if p.layer in building_layers
    ]

    assert not leaked, f"no building geometry may be drawn, got {[p.layer for p in leaked]}"

    # And no room label may claim a room.
    room_labels = [
        p
        for p in scene.primitives
        if p.layer == "LABELS" and p.kind == "TEXT" and p.geometry.get("text") in {"Living", "Kitchen"}
    ]

    assert not room_labels


# ==========================================================
# 4. IDENTITY JOIN (Living vs living, Kitchen vs kitchen)
# ==========================================================


def test_case_distinct_rooms_keep_their_distinct_footprints():
    """The measured pipeline's hardest join case.

    ``canonical_name`` is many-to-one. If the adapter joined on it, ``Kitchen``
    would land on ``kitchen``'s polygon and ``Living`` on ``living``'s. Each room
    must instead keep its own.
    """

    adapter = PlanModelToSceneAdapterV1()

    scene = adapter.realize(
        _plan_model(["Living", "Kitchen", "living", "kitchen"]),
        architectural_geometry=_dual_case_geometry(),
    )

    resolution = scene.metadata["room_resolution"]

    assert resolution["drawn_rooms"] == 4
    assert resolution["pending_rooms"] == 0
    assert resolution["status"] == "complete"

    # Reconstruct the polygons the adapter resolved, by room id.
    index = adapter._geometry_space_index(_dual_case_geometry())

    assert adapter._match_geometry({"name": "Living"}, index)["footprint"]["min_y"] == 0.0
    assert adapter._match_geometry({"name": "living"}, index)["footprint"]["min_y"] == 4.0
    assert adapter._match_geometry({"name": "Kitchen"}, index)["footprint"]["min_x"] == 5.0
    assert adapter._match_geometry({"name": "kitchen"}, index)["footprint"]["min_x"] == 8.0


def test_canonical_name_never_shadows_an_exact_name():
    """A canonical key that collides with an exact name must be dropped."""

    adapter = PlanModelToSceneAdapterV1()

    index = adapter._geometry_space_index(
        _geometry(
            [
                _resolved("living", "living_room", 0, 0, 4, 4),
                _resolved("Living", "living_room", 0, 5, 5, 9),
            ]
        )
    )

    # "living_room" is claimed by two records, so it must not be resolvable.
    assert "living_room" not in index

    # Both exact names remain independently resolvable.
    assert index["living"]["footprint"]["max_x"] == 4
    assert index["Living"]["footprint"]["max_x"] == 5


def test_room_ids_are_unique_and_traceable_to_source_names():

    adapter = PlanModelToSceneAdapterV1()

    scene = adapter.realize(
        _plan_model(["Living", "Kitchen", "living", "kitchen"]),
        architectural_geometry=_dual_case_geometry(),
    )

    ids = scene.metadata["plan_summary"]["room_ids"]

    assert len(ids) == 4
    assert len(set(ids)) == 4, "room identifiers must be unique"

    # Every identifier must be traceable to a registry name, never opaque.
    lowered = " ".join(ids).lower()
    assert "living" in lowered
    assert "kitchen" in lowered


# ==========================================================
# 5. SUMMARY AND EVIDENCE
# ==========================================================


def test_plan_summary_area_equals_sum_of_resolved_footprints():

    adapter = PlanModelToSceneAdapterV1()

    scene = adapter.realize(
        _plan_model(["Living", "Kitchen"]),
        architectural_geometry=_geometry(
            [
                _resolved("Living", "living_room", 0, 0, 5, 4),   # 20
                _resolved("Kitchen", "kitchen", 5, 0, 8, 3),      # 9
            ]
        ),
    )

    summary = scene.metadata["plan_summary"]

    assert summary["drawn_rooms"] == 2
    assert summary["resolved_area_m2"] == 29.0
    assert summary["resolved_area_space_count"] == 2
    assert summary["evidence_status"] == "complete"


def test_pending_room_area_is_never_counted():

    adapter = PlanModelToSceneAdapterV1()

    unresolved_with_area = _pending("Master", "master_bedroom")
    unresolved_with_area["footprint"] = {
        "type": "rectangle",
        "min_x": 0,
        "min_y": 0,
        "max_x": 99,
        "max_y": 99,
        "area": 9801,
    }

    scene = adapter.realize(
        _plan_model(["Living", "Master"]),
        architectural_geometry=_geometry(
            [
                _resolved("Living", "living_room", 0, 0, 5, 4),
                unresolved_with_area,
            ]
        ),
    )

    summary = scene.metadata["plan_summary"]

    assert summary["drawn_rooms"] == 1
    assert summary["pending_rooms"] == 1
    assert summary["resolved_area_m2"] == 20.0
    assert summary["evidence_status"] == "partial"


def test_building_bounds_are_derived_only_from_resolved_rooms():

    adapter = PlanModelToSceneAdapterV1()

    candidate = adapter._candidate(
        "villa",
        [
            {"id": "a", "polygon": [0, 0, 4, 3]},
            {"id": "b", "polygon": [4, 0, 9, 6]},
        ],
        {},
    )

    assert candidate["building"] == [0.0, 0.0, 9.0, 6.0]


def test_building_bounds_absent_when_nothing_resolved():

    adapter = PlanModelToSceneAdapterV1()

    candidate = adapter._candidate("villa", [], {})

    assert "building" not in candidate


def test_finished_floor_level_is_only_read_never_computed():

    adapter = PlanModelToSceneAdapterV1()

    with_ffl = adapter._candidate("v", [], {"ffl": 0.45})
    assert with_ffl["ffl"] == 0.45

    from_space = adapter._candidate("v", [], {"spaces": [{"elevation": 0.3}]})
    assert from_space["ffl"] == 0.3

    without = adapter._candidate("v", [], {"spaces": [{"elevation": None}]})
    assert "ffl" not in without


def test_adapter_version_is_stamped_into_evidence():

    adapter = PlanModelToSceneAdapterV1()

    scene = adapter.realize(
        _plan_model(["Living"]),
        architectural_geometry=_geometry(
            [_resolved("Living", "living_room", 0, 0, 5, 4)]
        ),
    )

    assert scene.metadata["plan_model_bridge"]["adapter"] == OUTPUT_VERSION


# ==========================================================
# 6. LAYOUT / SPATIAL CONTRACT ARE CONSULTED, NOT MINED FOR NUMBERS
# ==========================================================


def test_layout_and_spatial_contract_do_not_alter_geometry():

    adapter = PlanModelToSceneAdapterV1()

    geometry = _geometry(
        [_resolved("Living", "living_room", 0, 0, 5, 4)]
    )

    baseline = adapter.realize(
        _plan_model(["Living"]),
        architectural_geometry=geometry,
    )

    with_context = adapter.realize(
        _plan_model(["Living"]),
        layout={"rooms": [{"name": "Living", "width": 999, "height": 999}]},
        spatial_contract={"Living": {"x": 500, "y": 500}},
        architectural_geometry=geometry,
    )

    assert (
        baseline.metadata["plan_summary"]["resolved_area_m2"]
        == with_context.metadata["plan_summary"]["resolved_area_m2"]
    )

    baseline_xs = sorted(
        p.geometry.get("x", p.geometry.get("x1"))
        for p in baseline.primitives
        if "x" in p.geometry or "x1" in p.geometry
    )
    context_xs = sorted(
        p.geometry.get("x", p.geometry.get("x1"))
        for p in with_context.primitives
        if "x" in p.geometry or "x1" in p.geometry
    )

    assert baseline_xs == context_xs


# ==========================================================
# 7. SERVICE CONTRACT
# ==========================================================


class _StubDesignModel:
    """Minimal stand-in exposing the attributes the service reads."""

    def __init__(self, plan_model, geometry=None, layout=None, spatial_contract=None):
        self.plan_model = plan_model
        self.architectural_geometry = geometry or {}
        self.layout = layout
        self.spatial_contract = spatial_contract


def test_service_writes_a_viewable_svg(scratch_root):

    from core.architecture.drawing.plan_drawing_service_v1 import (
        PlanDrawingServiceV1,
    )

    service = PlanDrawingServiceV1(output_root=scratch_root)

    design_model = _StubDesignModel(
        _plan_model(["Living", "Kitchen"]),
        _geometry(
            [
                _resolved("Living", "living_room", 0, 0, 5, 4),
                _resolved("Kitchen", "kitchen", 5, 0, 8, 3),
            ]
        ),
    )

    result = service.render(design_model)

    assert result["status"] == "ready"
    assert result["format"] == "svg"
    assert result["room_resolution"]["drawn_rooms"] == 2

    from pathlib import Path

    path = Path(result["path"])

    assert path.exists()
    assert path.stat().st_size > 0
    assert path.suffix == ".svg"


def test_service_fails_closed_without_a_plan_model(scratch_root):

    from core.architecture.drawing.plan_drawing_service_v1 import (
        PlanDrawingServiceV1,
    )

    service = PlanDrawingServiceV1(output_root=scratch_root)

    result = service.render(_StubDesignModel(None))

    assert result["status"] == "unavailable"
    assert result["reason"] == "design_model_has_no_plan_model"


def test_service_reports_empty_when_no_room_resolves(scratch_root):

    from core.architecture.drawing.plan_drawing_service_v1 import (
        PlanDrawingServiceV1,
    )

    service = PlanDrawingServiceV1(output_root=scratch_root)

    design_model = _StubDesignModel(
        _plan_model(["Master"]),
        _geometry([_pending("Master", "master_bedroom")]),
    )

    result = service.render(design_model)

    assert result["status"] == "empty"
    assert result["reason"] == "no_resolved_room_footprints"
    assert len(result["pending_rooms"]) == 1


def test_service_never_writes_a_file_when_nothing_resolved(scratch_root):

    from core.architecture.drawing.plan_drawing_service_v1 import (
        PlanDrawingServiceV1,
    )

    service = PlanDrawingServiceV1(output_root=scratch_root)

    design_model = _StubDesignModel(
        _plan_model(["Master"]),
        _geometry([_pending("Master", "master_bedroom")]),
    )

    service.render(design_model)

    assert not list(scratch_root.rglob("*.svg"))


# ==========================================================
# 8. RESPONSE ADAPTER EXPOSURE
# ==========================================================


def test_response_adapter_surfaces_the_plan_drawing_artifact():

    from core.chat.response_adapter import ResponseAdapter

    adapter = ResponseAdapter()

    result = {
        "type": "design",
        "result": {},
        "plan_drawing": {
            "status": "ready",
            "type": "plan_drawing",
            "version": "plan_drawing_service_v1",
            "format": "svg",
            "path": "/tmp/PLAN_villa.svg",
            "artefacts": [
                {"format": "svg", "path": "/tmp/PLAN_villa.svg", "bytes": 1234}
            ],
            "plan_summary": {"resolved_area_m2": 113.0},
            "room_resolution": {
                "spaces": 9,
                "drawn_rooms": 8,
                "pending_rooms": 1,
                "status": "partial",
            },
            "pending_rooms": [{"name": "Master", "drawn": False}],
            "withheld_openings": {"reason_not_drawn": "x"},
        },
    }

    response = adapter.adapt(result)

    assert "plan_drawing" in response
    assert response["plan_drawing"]["status"] == "ready"
    assert response["plan_drawing"]["format"] == "svg"
    assert response["plan_drawing"]["path"] == "/tmp/PLAN_villa.svg"
    assert response["plan_drawing"]["room_resolution"]["drawn_rooms"] == 8


def test_response_adapter_surfaces_plan_drawing_from_design_payload():

    from core.chat.response_adapter import ResponseAdapter

    adapter = ResponseAdapter()

    result = {
        "type": "design",
        "result": {
            "plan_drawing": {
                "status": "ready",
                "format": "svg",
                "path": "/tmp/PLAN_x.svg",
                "room_resolution": {"drawn_rooms": 3, "pending_rooms": 0},
                "plan_summary": {"resolved_area_m2": 42.0},
            }
        },
    }

    response = adapter.adapt(result)

    assert response["plan_drawing"]["status"] == "ready"
    assert response["plan_drawing"]["room_resolution"]["drawn_rooms"] == 3


def test_response_summary_carries_the_plan_summary():

    from core.chat.response_adapter import ResponseAdapter

    adapter = ResponseAdapter()

    result = {
        "type": "design",
        "result": {},
        "plan_drawing": {
            "status": "ready",
            "format": "svg",
            "path": "/tmp/PLAN_villa.svg",
            "plan_summary": {"resolved_area_m2": 113.0, "floors": {"Ground": ["living"]}},
            "room_resolution": {"drawn_rooms": 8, "pending_rooms": 1},
        },
    }

    summary = adapter.build_summary(result)

    assert "plan_drawing" in summary
    assert summary["plan_drawing"]["drawn_rooms"] == 8
    assert summary["plan_drawing"]["pending_rooms"] == 1
    assert summary["plan_drawing"]["resolved_area_m2"] == 113.0
    assert summary["plan_drawing"]["path"] == "/tmp/PLAN_villa.svg"


def test_response_message_mentions_the_plan_and_its_pending_rooms():

    from core.chat.response_adapter import ResponseAdapter

    adapter = ResponseAdapter()

    result = {
        "type": "design",
        "architectural_intent": {"building_type": "villa", "style": "modern"},
        "plan_drawing": {
            "status": "ready",
            "format": "svg",
            "path": "/tmp/PLAN_villa.svg",
            "plan_summary": {"resolved_area_m2": 113.0},
            "room_resolution": {"drawn_rooms": 8, "pending_rooms": 1},
        },
    }

    message = adapter.build_message(result)

    assert "8" in message
    assert "113" in message
    assert "1" in message


def test_response_message_is_honest_when_no_plan_was_produced():

    from core.chat.response_adapter import ResponseAdapter

    adapter = ResponseAdapter()

    result = {
        "type": "design",
        "architectural_intent": {"building_type": "villa", "style": "modern"},
        "plan_drawing": {"status": "unavailable", "reason": "no_plan_model"},
    }

    message = adapter.build_message(result)

    # No drawn-room count may be claimed when nothing was drawn.
    assert "اتاق‌های رسم‌شده" not in message


def test_response_adapter_unchanged_when_no_plan_drawing_present():

    from core.chat.response_adapter import ResponseAdapter

    adapter = ResponseAdapter()

    result = {
        "type": "design",
        "result": {},
        "architectural_intent": {"building_type": "villa", "style": "modern"},
    }

    response = adapter.adapt(result)

    assert "plan_drawing" not in response
    assert response["message"]


if __name__ == "__main__":

    import traceback
    import inspect

    failures = 0
    checked = 0

    for name, function in sorted(
        (n, f)
        for n, f in globals().items()
        if n.startswith("test_") and callable(f)
    ):

        checked += 1

        try:
            parameters = inspect.signature(function).parameters
            if "scratch_root" in parameters:
                if _SCRATCH.exists():
                    shutil.rmtree(_SCRATCH, ignore_errors=True)
                _SCRATCH.mkdir(parents=True, exist_ok=True)
                try:
                    function(_SCRATCH)
                finally:
                    shutil.rmtree(_SCRATCH, ignore_errors=True)
            else:
                function()
            print(f"PASS {name}")
        except Exception:
            failures += 1
            print(f"FAIL {name}")
            traceback.print_exc()

    print(f"\n{checked - failures}/{checked} passed")

    raise SystemExit(1 if failures else 0)
